#!/usr/bin/env python3
"""TITHE's RULES, as a reference implementation and a balance harness.

    python3 tools/duelsim.py --selfcheck
    python3 tools/duelsim.py report [--n 300] [--seed 1]
    python3 tools/duelsim.py match BULWARK CHOIR [--seed 7] [--out m.tmf]
                                   [--log m.log] [--text]
    python3 tools/duelsim.py replay m.tmf [--log m.log] [--text]

TITHE-PLAN 14.1, and SPEC.md 97.11 is the contract. It is the SECOND READER
of the rules: the package's `tirule.inc` and this must agree, and
tests/titherules.py plays a match file on the machine and compares the state
record this writes after every round to the machine's, byte for byte.

A MATCH IS A PURE FUNCTION OF SIX INPUTS (TITHE-PLAN 5.0.1): two decks, two
shuffle seeds - one generator a side, the opening shuffle and every reshuffle
off the same stream - and two AI seeds. Nothing in RESOLUTION is random. So a
match file is the decks, the seeds, the two mulligans and the plans, and
`replay` reproduces the log byte for byte; the AI seeds are not in it at all,
because what the AI decided is the plans.

EVERY RULE IS WRITTEN THE WAY THE ENGINE RUNS IT - small integers, fixed
iteration orders, no dictionary order, no floats - because the assembly has to
make the same decisions in the same order. Where TITHE-PLAN left an order open
(which of a lane's hits lands first, when an aura is read) the answer is here
and in SPEC.md 97.11.4, and it is the same answer in both.
"""
import copy
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88tithecards as tc                               # noqa: E402

LANES, COLS = 5, 2
FRONT, REAR = 0, 1
STANCE_FRONT, STANCE_SNIPE = 0, 1
EMPTY = 0xFF
HAND, HANDMAX, OPENING = 7, 7, 4
START_HP, START_GOLD, INCOME, SWAPS = 20, 4, 2, 2
CAP = 99                            # gold and souls: the HUD's two digits
ROUNDMAX = 60                       # a match past this is a stalemate
REAR_BONUS = 1
HEALCHAIN = ((0, 0), (1, 0), (0, -1), (0, 1), (1, -1), (1, 1))  # (other col?, dr)

A_PLAY, A_ORDER, A_SWAP, A_STANCE = 1, 2, 3, 4
RES_NONE, RES_A, RES_B, RES_DRAW, RES_STALE = 0, 1, 2, 3, 4

K = tc.KWID
CARDS, DECKS = None, None
FIRED = set()                       # the keywords that actually DID something


def fire(name):
    FIRED.add(name)


def cards():
    global CARDS, DECKS
    if CARDS is None:
        CARDS, DECKS = tc.load()
    return CARDS


class Rng:
    """xorshift16 (7, 9, 8): the engine's, one a side (SPEC.md 97.11.5)."""
    def __init__(self, seed):
        self.x = (seed & 0xFFFF) or 1

    def next(self):
        x = self.x
        x ^= (x << 7) & 0xFFFF
        x ^= x >> 9
        x ^= (x << 8) & 0xFFFF
        self.x = x
        return x


def shuffle(pile, rng):
    for i in range(len(pile) - 1, 0, -1):
        j = rng.next() % (i + 1)
        pile[i], pile[j] = pile[j], pile[i]


class Cell:
    __slots__ = ("card", "inst", "hp", "sh", "st", "bm", "br", "mark", "kk",
                 "om", "orr", "os", "og", "oh", "opi", "osc", "owd", "used")

    def __init__(self):
        self.clear()

    def clear(self):
        self.card = EMPTY
        self.inst = self.hp = self.sh = self.st = self.bm = self.br = 0
        self.mark = self.kk = self.used = 0
        self.clear_orders()

    def clear_orders(self):
        self.om = self.orr = self.os = self.og = self.oh = self.opi = 0
        self.osc = self.owd = 0


class Side:
    def __init__(self, deck, seed):
        self.hp, self.gold, self.souls = START_HP, START_GOLD, 0
        self.rng = Rng(seed)
        self.draw = list(deck)
        self.discard, self.hand = [], []
        self.inst = 1
        self.swaps = SWAPS
        self.deaths = 0
        self.cells = [[Cell() for _ in range(LANES)] for _ in range(COLS)]

    def draw1(self):
        if not self.draw:
            if not self.discard:
                return                          # a dry draw, not a loss
            self.draw, self.discard = self.discard, []
            shuffle(self.draw, self.rng)
        c = self.draw.pop()                     # the top is the END
        if len(self.hand) >= HANDMAX:
            self.discard.append(c)              # over the limit: discarded
        else:
            self.hand.append(c)


def blk(cell, col):
    c = cards()[cell.card]
    return c.front if col == FRONT else c.rear


def kw(cell, col, kid):
    """The number of keyword `kid` on the cell's LIVE block, or None."""
    return blk(cell, col)["kw"].get(kid)


def alive(cell):
    return cell.card != EMPTY and not cell.mark


class Match:
    def __init__(self, deck_a, deck_b, seed_a, seed_b):
        self.sides = [Side(deck_a, seed_a), Side(deck_b, seed_b)]
        self.round = 0
        self.result = RES_NONE
        for s in self.sides:
            shuffle(s.draw, s.rng)
            for _ in range(OPENING):
                s.draw1()

    def mulligan(self, side):
        """TITHE-PLAN 6.1: the whole hand back, one reshuffle, and as many
        again. It is taken after the FIRST upkeep (SPEC.md 97.11.5) - a
        hot-seat player decides at their own first turn - so that is five."""
        s = self.sides[side]
        n = len(s.hand)
        s.draw += s.hand
        s.hand = []
        shuffle(s.draw, s.rng)
        for _ in range(n):
            s.draw1()

    # --- the board's auras (SPEC.md 97.11.3), read where the rule reads them --
    def any_kw(self, side, kid):
        for c in range(COLS):
            for r in range(LANES):
                cell = self.sides[side].cells[c][r]
                if alive(cell) and kw(cell, c, kid) is not None:
                    return True
        return False

    def shield_max(self, side, c, r, orders=True):
        cells = self.sides[side].cells
        cell = cells[c][r]
        v = blk(cell, c)["s"] + (cell.os if orders else 0)
        for dr in (-1, 1):
            rr = r + dr
            if 0 <= rr < LANES:
                n = cells[c][rr]
                if alive(n) and kw(n, c, K["RAMPART"]) is not None:
                    v += 1
                    fire("RAMPART")
        n = cells[1 - c][r]
        if alive(n) and kw(n, 1 - c, K["VIGIL"]) is not None:
            v += 1
            fire("VIGIL")
        if c == FRONT and self.any_kw(side, K["MUSTER"]):
            v += 1
            fire("MUSTER")
        return v

    def refill(self, orders):
        for side in (0, 1):
            for c in range(COLS):
                for r in range(LANES):
                    cell = self.sides[side].cells[c][r]
                    if cell.card != EMPTY:
                        cell.sh = self.shield_max(side, c, r, orders)

    def melee(self, side, c, r):
        cells = self.sides[side].cells
        cell = cells[c][r]
        v = blk(cell, c)["m"] + cell.bm + cell.om
        for dr in (-1, 1):
            rr = r + dr
            if 0 <= rr < LANES:
                n = cells[c][rr]
                if alive(n):
                    b = kw(n, c, K["BLESS"])
                    if b is not None:
                        v += b
                        fire("BLESS")
        return v

    def ranged(self, side, c, r):
        cells = self.sides[side].cells
        cell = cells[c][r]
        v = blk(cell, c)["r"] + cell.br + cell.orr
        for dr in (-1, 1):
            rr = r + dr
            if 0 <= rr < LANES:
                for cc in range(COLS):
                    n = cells[cc][rr]
                    if alive(n) and kw(n, cc, K["CHORUS"]) is not None:
                        v += 1
                        fire("CHORUS")
        return v

    # --- PHASE 1: UPKEEP (TITHE-PLAN 6.2) -------------------------------------
    def upkeep(self):
        self.round += 1
        for s in self.sides:
            s.draw1()
            s.gold = min(CAP, s.gold + INCOME)
            s.swaps = SWAPS
            s.deaths = 0
        self.refill(orders=False)

    # --- PHASE 2: a PLAN, applied to its own half (TITHE-PLAN 6.0, 6.3) -------
    def apply(self, side, plan):
        s = self.sides[side]
        for act in plan:
            op, a, b = act
            if op == A_PLAY:
                self.play(s, a, b)
            elif op == A_ORDER:
                self.order(s, a, b)
            elif op == A_SWAP:
                if s.swaps <= 0:
                    raise ValueError("no swaps left")
                ca, ra, cb, rb = a // LANES, a % LANES, b // LANES, b % LANES
                s.cells[ca][ra], s.cells[cb][rb] = s.cells[cb][rb], s.cells[ca][ra]
                s.swaps -= 1
            elif op == A_STANCE:
                cell = s.cells[a // LANES][a % LANES]
                if cell.card == EMPTY:
                    raise ValueError("a stance on an empty cell")
                cell.st = b
            else:
                raise ValueError("no action %d" % op)

    def pay(self, s, card):
        c = cards()[card]
        if card not in s.hand:
            raise ValueError("%s is not in the hand" % c.name)
        if s.gold < c.cg or s.souls < c.cs:
            raise ValueError("cannot afford %s" % c.name)
        s.hand.remove(card)                     # the FIRST copy
        s.gold -= c.cg
        s.souls -= c.cs
        return c

    def play(self, s, card, col):
        if cards()[card].kind == tc.KIND_ORDER:
            raise ValueError("an order is not placed")
        for r in range(LANES):                  # the TOPMOST empty cell
            if s.cells[col][r].card == EMPTY:
                break
        else:
            raise ValueError("the column is full")
        c = self.pay(s, card)
        cell = s.cells[col][r]
        cell.clear()
        cell.card = card
        cell.inst = s.inst
        s.inst = s.inst % 255 + 1
        b = c.front if col == FRONT else c.rear
        cell.hp = b["hp"]
        cell.sh = b["s"]

    def order(self, s, card, inst):
        c = cards()[card]
        if c.kind != tc.KIND_ORDER:
            raise ValueError("%s is not an order" % c.name)
        for col in range(COLS):
            for r in range(LANES):
                cell = s.cells[col][r]
                if cell.card != EMPTY and cell.inst == inst:
                    self.pay(s, card)
                    e = c.front
                    cell.om += e["m"]
                    cell.orr += e["r"]
                    cell.os += e["s"]
                    cell.og += e["g"]
                    cell.oh += e["h"]
                    cell.opi += e["kw"].get(K["PIERCE"], 0)
                    if K["SCORCH"] in e["kw"]:
                        cell.osc = 1
                    if K["WARD"] in e["kw"]:
                        cell.owd = 1
                    s.discard.append(card)      # spent the round it is played
                    return
        raise ValueError("no character %d" % inst)

    # --- PHASE 4: COMBAT, lane by lane (TITHE-PLAN 6.5, SPEC.md 97.11.4) ------
    def resolve(self):
        self.refill(orders=True)                # after BOTH plans
        for r in range(LANES):
            self.lane(r)
        self.casualties()
        self.spoils()
        a, b = self.sides[0].hp <= 0, self.sides[1].hp <= 0
        self.result = (RES_DRAW if a and b else RES_B if a else RES_A if b
                       else RES_NONE)
        for s in self.sides:
            for c in range(COLS):
                for rr in range(LANES):
                    s.cells[c][rr].clear_orders()
        if self.result == RES_NONE and self.round >= ROUNDMAX:
            self.result = RES_STALE

    def lane(self, r):
        # every hit is DECIDED from the state at the lane's start...
        hits = []
        for side in (0, 1):
            e = 1 - side
            me, them = self.sides[side].cells, self.sides[e].cells
            for c in range(COLS):
                cell = me[c][r]
                if not alive(cell):
                    continue
                pierce = (kw(cell, c, K["PIERCE"]) or 0) + cell.opi
                kindle = 1 if kw(cell, c, K["KINDLE"]) is not None else 0
                if c == FRONT:
                    m = self.melee(side, c, r)
                    if m > 0:
                        hits.append((e, self.melee_target(e, r), m, pierce,
                                     0, 0, 0, kindle))
                rg = self.ranged(side, c, r)
                if rg > 0:
                    t = self.ranged_target(e, r, cell.st, pierce)
                    if c == REAR and t == (FRONT, r):
                        rg += REAR_BONUS
                    volley = 1 if kw(cell, c, K["VOLLEY"]) is not None else 0
                    scorch = 1 if (kw(cell, c, K["SCORCH"]) is not None
                                   or cell.osc) else 0
                    hits.append((e, t, rg, pierce, 1, volley, scorch, kindle))
        # ...and APPLIED in that order: side 0's front melee, front ranged,
        # rear ranged, then side 1's
        for e, t, dmg, pierce, rng, volley, scorch, kindle in hits:
            if t is None:
                self.player_hit(e, r, dmg)
                continue
            tcol, tr = t
            them = self.sides[e].cells
            ov = self.hit(e, tcol, tr, dmg, pierce, rng, kindle)
            if scorch and ov > 0 and tcol == FRONT and them[REAR][tr].card != EMPTY:
                fire("SCORCH")
                self.hit(e, REAR, tr, ov, 0, rng, kindle)
            if volley:
                for dr in (-1, 1):
                    rr = tr + dr
                    if 0 <= rr < LANES and them[tcol][rr].card != EMPTY:
                        fire("VOLLEY")
                        self.hit(e, tcol, rr, 1, pierce, 1, kindle)
        # ...and then the lane's healers, the unmarked ones (TITHE-PLAN 5.5.2)
        for side in (0, 1):
            for c in range(COLS):
                self.heal(side, c, r)

    def melee_target(self, e, r):
        them = self.sides[e].cells
        if them[FRONT][r].card != EMPTY:
            return (FRONT, r)
        if them[REAR][r].card != EMPTY:
            # GUARD (SPEC.md 97.11.3): a guard in the front of the lane above
            # or below steps across and takes the gap-punish itself
            for rr in (r - 1, r + 1):
                if 0 <= rr < LANES:
                    g = them[FRONT][rr]
                    if alive(g) and kw(g, FRONT, K["GUARD"]) is not None:
                        fire("GUARD")
                        return (FRONT, rr)
            return (REAR, r)
        return None

    def ranged_target(self, e, r, stance, pierce):
        them = self.sides[e].cells
        f, b = them[FRONT][r], them[REAR][r]
        if stance == STANCE_SNIPE:
            if f.card != EMPTY and f.sh - pierce > 0:
                return (FRONT, r)               # WALLED: it falls back
            return (REAR, r) if b.card != EMPTY else None
        if f.card != EMPTY:
            return (FRONT, r)
        if b.card != EMPTY:
            return (REAR, r)
        return None

    def player_hit(self, e, r, dmg):
        """STANDFAST guards the lanes ABOVE AND BELOW its own: a player is
        only hit through a lane with nobody in it, so a keyword that guarded
        its own lane could never fire."""
        cells = self.sides[e].cells
        for rr in (r - 1, r + 1):
            if 0 <= rr < LANES:
                for c in range(COLS):
                    cell = cells[c][rr]
                    if alive(cell) and kw(cell, c, K["STANDFAST"]) is not None:
                        fire("STANDFAST")
                        return
        self.sides[e].hp -= dmg

    def hit(self, e, c, r, dmg, pierce, rng, kindle):
        """One hit: shield first, then HP. Returns the OVERKILL - what went
        past a death - for SCORCH."""
        cells = self.sides[e].cells
        cell = cells[c][r]
        if cell.mark:
            return 0
        eff = max(0, cell.sh - pierce)
        if pierce and cell.sh:
            fire("PIERCE")
        ab = min(dmg, eff)
        cell.sh -= ab
        rest = dmg - ab
        b = kw(cell, c, K["BULWARK"])
        if b is not None and cell.sh < b:
            cell.sh = b
            fire("BULWARK")
        floor = 0
        if rng:
            for cc in range(COLS):
                n = cells[cc][r]
                if alive(n) and kw(n, cc, K["SANCTUARY"]) is not None:
                    floor = 1
        if rest <= 0:
            return 0
        if cell.hp - rest > floor:
            cell.hp -= rest
            return 0
        if floor:
            cell.hp = 1
            fire("SANCTUARY")
            return 0
        ov = rest - cell.hp
        cell.hp = 0
        cell.mark = 1
        cell.kk = kindle
        return ov

    def heal(self, side, c, r):
        cells = self.sides[side].cells
        cell = cells[c][r]
        if not alive(cell):
            return
        pool = blk(cell, c)["h"] + cell.oh
        if pool <= 0:
            return
        if self.any_kw(side, K["MERCY"]):
            pool += 1
            fire("MERCY")
        for other, dr in HEALCHAIN:
            cc, rr = (1 - c if other else c), r + dr
            if not 0 <= rr < LANES:
                continue
            t = cells[cc][rr]
            if t.card == EMPTY:
                continue
            top = blk(t, cc)["hp"]
            if t.hp >= top:
                continue
            amt = min(pool, top - t.hp)
            t.hp += amt
            if t.mark:
                t.mark = t.kk = 0               # pulled back from zero
            pool -= amt
            if pool == 0:
                break

    # --- PHASE 5: CASUALTIES (TITHE-PLAN 6.6) ---------------------------------
    def casualties(self):
        dying = []
        for r in range(LANES):
            for side in (0, 1):
                cells = self.sides[side].cells
                for c in range(COLS):
                    cell = cells[c][r]
                    if cell.card == EMPTY or not cell.mark:
                        continue
                    if cell.owd:                # WARD: it holds at 1
                        cell.hp, cell.mark = 1, 0
                        fire("WARD")
                        continue
                    saved = False
                    for cc, rr in ((c, r - 1), (c, r + 1), (1 - c, r)):
                        if not 0 <= rr < LANES:
                            continue
                        n = cells[cc][rr]
                        if (alive(n) and not n.used
                                and kw(n, cc, K["INTERCEDE"]) is not None):
                            n.used = 1          # INTERCEDE: it dies instead
                            fire("INTERCEDE")
                            cell.hp, cell.mark = 1, 0
                            dying.append((side, cc, rr, 0))
                            saved = True
                            break
                    if not saved:
                        dying.append((side, c, r, cell.kk))
        doomed = {(s, c, r) for s, c, r, _ in dying}
        hymn = []
        for side in (0, 1):
            h = False
            for c in range(COLS):
                for r in range(LANES):
                    cell = self.sides[side].cells[c][r]
                    if (cell.card != EMPTY and not cell.mark
                            and (side, c, r) not in doomed
                            and kw(cell, c, K["HYMN"]) is not None):
                        h = True
            hymn.append(h)
        martyrs = [0, 0]
        for side, c, r, kk in dying:
            s = self.sides[side]
            cell = s.cells[c][r]
            card = cards()[cell.card]
            if kw(cell, c, K["MARTYR"]) is not None:
                martyrs[side] += 1
                fire("MARTYR")
            if kk:
                fire("KINDLE")
            if hymn[1 - side]:
                fire("HYMN")
            e = 1 - side
            self.sides[e].souls = min(CAP, self.sides[e].souls + card.power
                                      + kk + (1 if hymn[e] else 0))
            s.discard.append(cell.card)
            s.deaths += 1
            cell.clear()
            for rr in (r - 1, r, r + 1):        # ABSOLVE: its lane and the
                if not 0 <= rr < LANES:         # two beside it
                    continue
                for cc in range(COLS):
                    n = s.cells[cc][rr]
                    if (n.card != EMPTY and (side, cc, rr) not in doomed
                            and kw(n, cc, K["ABSOLVE"]) is not None):
                        fire("ABSOLVE")
                        n.bm = min(9, n.bm + 1)
                        n.br = min(9, n.br + 1)
        for side in (0, 1):                     # MARTYR: the rest heal 3
            for _ in range(martyrs[side]):
                for c in range(COLS):
                    for r in range(LANES):
                        n = self.sides[side].cells[c][r]
                        if n.card != EMPTY:
                            n.hp = min(blk(n, c)["hp"], n.hp + 3)

    # --- PHASE 6: SPOILS (TITHE-PLAN 6.7) --------------------------------------
    def spoils(self):
        for s in self.sides:
            rear = sum(1 for r in range(LANES) if s.cells[REAR][r].card != EMPTY)
            for c in range(COLS):
                for r in range(LANES):
                    cell = s.cells[c][r]
                    if cell.card == EMPTY:
                        continue
                    b = blk(cell, c)
                    g = b["g"] + cell.og + (kw(cell, c, K["LEVY"]) or 0)
                    so = kw(cell, c, K["PYRE"]) or 0
                    if kw(cell, c, K["LEVY"]):
                        fire("LEVY")
                    if so:
                        fire("PYRE")
                    if kw(cell, c, K["STEWARD"]) is not None:
                        g += rear
                        fire("STEWARD")
                    if kw(cell, c, K["REQUIEM"]) is not None:
                        so += s.deaths
                        if s.deaths:
                            fire("REQUIEM")
                    s.gold = min(CAP, s.gold + g)
                    s.souls = min(CAP, s.souls + so)

    # --- THE STATE RECORD (SPEC.md 97.11.6) ------------------------------------
    def record(self):
        out = bytearray([self.round & 0xFF])
        for s in self.sides:
            out += bytes([max(0, min(255, s.hp)), s.gold, s.souls, s.inst,
                          s.rng.x & 0xFF, s.rng.x >> 8, s.swaps])
            for pile, n in ((s.hand, HAND), (s.draw, 50), (s.discard, 50)):
                out.append(len(pile))
                out += bytes(pile) + bytes([EMPTY] * (n - len(pile)))
        for s in self.sides:
            for c in range(COLS):
                for r in range(LANES):
                    cell = s.cells[c][r]
                    if cell.card == EMPTY:
                        out += bytes([EMPTY, 0, 0, 0, 0, 0, 0])
                    else:
                        out += bytes([cell.card, cell.inst, cell.hp, cell.sh,
                                      cell.st, cell.bm, cell.br])
        out.append(self.result)
        return bytes(out)


RECSIZE = 1 + 2 * (7 + 1 + HAND + 1 + 50 + 1 + 50) + 2 * COLS * LANES * 7 + 1


# --- THE MATCH FILE (SPEC.md 97.11.6) ----------------------------------------
def tmf_pack(deck_a, deck_b, seed_a, seed_b, mull, rounds):
    out = bytearray(b"TMF1")
    for d in (deck_a, deck_b):
        out.append(len(d))
        out += bytes(d)
    out += struct.pack("<HH", seed_a, seed_b)
    out += bytes(mull)
    out.append(len(rounds))
    for pa, pb in rounds:
        for p in (pa, pb):
            out.append(len(p))
            for op, a, b in p:
                out += bytes([op, a, b])
    return bytes(out)


def tmf_unpack(data):
    if data[:4] != b"TMF1":
        raise ValueError("not a match file")
    i = 4
    decks = []
    for _ in range(2):
        n = data[i]
        decks.append(list(data[i + 1:i + 1 + n]))
        i += 1 + n
    seed_a, seed_b = struct.unpack("<HH", data[i:i + 4])
    i += 4
    mull = list(data[i:i + 2])
    i += 2
    n = data[i]
    i += 1
    rounds = []
    for _ in range(n):
        pair = []
        for _ in range(2):
            k = data[i]
            i += 1
            pair.append([tuple(data[i + 3 * j:i + 3 * j + 3]) for j in range(k)])
            i += 3 * k
        rounds.append(tuple(pair))
    return decks[0], decks[1], seed_a, seed_b, mull, rounds


def replay(data):
    """The log a match file produces: a record after setup, one a round."""
    da, db, sa, sb, mull, rounds = tmf_unpack(data)
    m = Match(da, db, sa, sb)
    log = [m.record()]
    for pa, pb in rounds:
        m.upkeep()
        if m.round == 1:
            for side in (0, 1):
                if mull[side]:
                    m.mulligan(side)
        m.apply(0, pa)
        m.apply(1, pb)
        m.resolve()
        log.append(m.record())
        if m.result:
            break
    return b"".join(log), m


# --- THE SIMULATOR'S PLAYER (not wave 4's AI: enough to play a match) --------
def value(card, col, m, side, lane):
    c = cards()[card]
    b = c.front if col == FRONT else c.rear
    v = b["r"] * 3 + b["g"] * 3 + b["h"] * 2 + b["hp"]
    v += 3 * ((b["kw"].get(K["PYRE"]) or 0) + (b["kw"].get(K["LEVY"]) or 0))
    if col == FRONT:
        v += b["m"] * 3 + b["s"] * 2
        e = m.sides[1 - side].cells
        if e[FRONT][lane].card != EMPTY or e[REAR][lane].card != EMPTY:
            v += 4                              # a lane that is being fought
    return v


def ai_mulligan(m, side, rng):
    h = m.sides[side].hand
    cheap = sum(1 for x in h if cards()[x].kind != tc.KIND_ORDER
                and cards()[x].cg <= START_GOLD + INCOME and cards()[x].cs == 0)
    return 1 if cheap < 2 and rng.next() % 4 else 0


def ai_plan(m, side, rng):
    """A legal plan against the frozen board: plays by a crude value and a
    jitter, an order if there is gold left, a swap to fill an empty front,
    and the stances the frozen board argues for."""
    sim = copy.deepcopy(m)
    s = sim.sides[side]
    plan = []

    def do(act):
        sim.apply(side, [act])
        plan.append(act)

    for _ in range(HAND):
        best = None
        for card in sorted(set(s.hand)):
            c = cards()[card]
            if c.kind == tc.KIND_ORDER or s.gold < c.cg or s.souls < c.cs:
                continue
            for col in (FRONT, REAR):
                lane = next((r for r in range(LANES)
                             if s.cells[col][r].card == EMPTY), None)
                if lane is None:
                    continue
                v = value(card, col, sim, side, lane) + (rng.next() & 7)
                if best is None or v > best[0]:
                    best = (v, card, col)
        if best is None or best[0] < 6:
            break
        do((A_PLAY, best[1], best[2]))
    # a front cell left empty is a gap-punish: fill it from behind
    for r in range(LANES):
        if s.swaps and s.cells[FRONT][r].card == EMPTY:
            b = s.cells[REAR][r]
            if b.card != EMPTY and cards()[b.card].front["m"] >= 3:
                do((A_SWAP, FRONT * LANES + r, REAR * LANES + r))
    for card in sorted(set(s.hand)):
        c = cards()[card]
        if c.kind != tc.KIND_ORDER or s.gold < c.cg or s.souls < c.cs:
            continue
        live = [(s.cells[col][r].inst, col, r) for col in range(COLS)
                for r in range(LANES) if s.cells[col][r].card != EMPTY]
        if live and rng.next() % 3:
            inst, col, r = live[rng.next() % len(live)]
            do((A_ORDER, card, inst))
    them = sim.sides[1 - side].cells
    for col in range(COLS):
        for r in range(LANES):
            cell = s.cells[col][r]
            if cell.card == EMPTY or blk(cell, col)["r"] == 0:
                continue
            pierce = (kw(cell, col, K["PIERCE"]) or 0) + cell.opi
            f, b = them[FRONT][r], them[REAR][r]
            want = (STANCE_SNIPE if f.card != EMPTY and b.card != EMPTY
                    and f.sh - pierce <= 0 else STANCE_FRONT)
            if want != cell.st:
                do((A_STANCE, col * LANES + r, want))
    return plan


def play_match(deck_a, deck_b, seed_a, seed_b, ai_a, ai_b, check=False):
    """AI against AI. Returns (match file, log, match). With `check`, every
    round is also applied the OTHER way round and the boards compared
    (TITHE-PLAN 14.3's confluence)."""
    m = Match(deck_a, deck_b, seed_a, seed_b)
    ras, rbs = Rng(ai_a), Rng(ai_b)
    mull = [0, 0]
    rounds = []
    while not m.result:
        m.upkeep()
        if not rounds:                          # after the FIRST upkeep
            mull = [ai_mulligan(m, 0, ras), ai_mulligan(m, 1, rbs)]
            for side in (0, 1):
                if mull[side]:
                    m.mulligan(side)
        pa = ai_plan(m, 0, ras)
        pb = ai_plan(m, 1, rbs)
        if check:
            x = copy.deepcopy(m)
            x.apply(1, pb)
            x.apply(0, pa)
        m.apply(0, pa)
        m.apply(1, pb)
        if check and x.record() != m.record():
            raise AssertionError("round %d is not confluent" % m.round)
        m.resolve()
        rounds.append((pa, pb))
    data = tmf_pack(deck_a, deck_b, seed_a, seed_b, mull, rounds)
    return data, replay(data)[0], m


# --- the selfcheck and the report ---------------------------------------------
def random_deck(faction, size, seed, force=(), commander=None):
    """A legal deck of `size` from a faction's cards, at most two copies -
    the named cards first, twice each, and a commander past twenty cards."""
    rng = Rng(seed)
    names = {c.name: c.id for c in cards()}
    forced = [names[n] for n in force for _ in range(2)]
    pool = [c.id for c in cards() if c.faction == faction
            and c.kind != tc.KIND_CMDR and c.name not in force]
    pool = pool + pool
    shuffle(pool, rng)
    deck = (forced + pool)[:size]
    cm = [c.id for c in cards() if c.faction == faction and c.kind == tc.KIND_CMDR]
    if commander:
        deck[-1] = names[commander]
    elif size > 20:
        deck[-1] = cm[rng.next() % len(cm)]
    return deck


def text(log):
    """The log as lines, for a person."""
    names = cards()
    out = []
    for i in range(0, len(log), RECSIZE):
        rec = log[i:i + RECSIZE]
        p = 1
        line = ["R%-2d" % rec[0]]
        sides = []
        for _ in range(2):
            hp, g, so = rec[p], rec[p + 1], rec[p + 2]
            hand = rec[p + 7]
            draw = rec[p + 7 + 1 + HAND]
            disc = rec[p + 7 + 1 + HAND + 1 + 50]
            sides.append("hp %2d g %2d s %2d hand %d draw %2d disc %2d" % (
                hp, g, so, hand, draw, disc))
            p += 7 + 1 + HAND + 1 + 50 + 1 + 50
        line.append(" | ".join(sides))
        cellpart = []
        for side in range(2):
            for c in range(COLS):
                for r in range(LANES):
                    card, inst, hp, sh = rec[p], rec[p + 1], rec[p + 2], rec[p + 3]
                    p += 7
                    if card != EMPTY:
                        cellpart.append("%s%s%d %s %d/%d" % (
                            "AB"[side], "FR"[c], r, names[card].name, hp, sh))
        out.append(" ".join(line) + ("  result %d" % rec[-1] if rec[-1] else ""))
        out.append("    " + ", ".join(cellpart))
    return "\n".join(out)


def selfcheck():
    t0 = __import__("time").time()
    cards()
    bad = []
    lengths = []
    n = 0
    fac = range(3)
    for a in fac:
        for b in fac:
            for seed in (1, 2):
                da = DECKS[tc.FACTIONS[a]]
                db = DECKS[tc.FACTIONS[b]]
                data, log, m = play_match(da, db, 17 * seed + a, 31 * seed + b,
                                          seed * 5 + 1, seed * 7 + 2, check=True)
                n += 1
                lengths.append(m.round)
                if m.result == RES_STALE:
                    bad.append("%s v %s seed %d: a stalemate at %d rounds"
                               % (tc.FACTIONS[a], tc.FACTIONS[b], seed, m.round))
                again, _ = replay(data)
                if again != log:
                    bad.append("%s v %s seed %d: a replay differs"
                               % (tc.FACTIONS[a], tc.FACTIONS[b], seed))
                if len(log) % RECSIZE:
                    bad.append("the log is not whole records")
    # THE DECK SIZES' TWO ENDS (TITHE-PLAN 9.3): fourteen and fifty both finish
    for size in (14, 50):
        for f in fac:
            deck = random_deck(f, size, 99 + size + f)
            probs = tc.deck_problems(deck, cards(), f)
            if probs:
                bad.append("the %d-card deck is not legal: %s" % (size, probs))
            other = DECKS[tc.FACTIONS[(f + 1) % 3]]
            data, log, m = play_match(deck, other, 5 + f, 9 + f, 3, 4, check=True)
            n += 1
            lengths.append(m.round)
            if m.result == RES_STALE:
                bad.append("a %d-card %s deck stalemated" % (size, tc.FACTIONS[f]))
    for line in bad:
        print("  FAIL %s" % line)
    lengths.sort()
    print("duelsim: %d matches, confluent and replayed, rounds %d-%d (median %d) "
          "in %.1fs, %s" % (n, lengths[0], lengths[-1], lengths[len(lengths) // 2],
                           __import__("time").time() - t0,
                           "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


def report(n, seed):
    cards()
    wins = {f: [0, 0] for f in tc.FACTIONS}
    lengths = []
    stale = 0
    k = 0
    for i in range(n):
        a, b = i % 3, (i // 3) % 3
        if a == b:
            continue
        da, db = DECKS[tc.FACTIONS[a]], DECKS[tc.FACTIONS[b]]
        _, _, m = play_match(da, db, seed + 3 * i, seed + 5 * i + 1,
                             seed + 7 * i, seed + 11 * i + 1)
        k += 1
        lengths.append(m.round)
        if m.result == RES_STALE:
            stale += 1
            continue
        for f, won in ((a, m.result == RES_A), (b, m.result == RES_B)):
            wins[tc.FACTIONS[f]][0] += won
            wins[tc.FACTIONS[f]][1] += 1
    lengths.sort()
    print("%d matches (mirrors excluded), rounds median %d, 10%%-90%% %d-%d, "
          "stalemates %d" % (k, lengths[len(lengths) // 2],
                             lengths[len(lengths) // 10],
                             lengths[len(lengths) * 9 // 10], stale))
    for f, (w, t) in wins.items():
        print("  %-9s won %3d of %3d  %5.1f%%" % (f, w, t, 100.0 * w / max(t, 1)))


def bake(out):
    """THE MACHINE'S TEST MATCHES (tests/titherules.py): a count, then each
    match file as a word length and its bytes. Chosen GREEDILY for keyword
    coverage - a match joins the set only if it makes a keyword fire that the
    set had not - so the machine is asked about every rule and not just the
    common ones, and the set is small enough to replay in seconds there."""
    cards()
    chosen, have = [], set()
    want = {k[0] for k in tc.KEYWORDS}
    # the three starter pairings always, then random decks with commanders
    cands = []
    for a in range(3):
        cands.append((DECKS[tc.FACTIONS[a]], DECKS[tc.FACTIONS[(a + 1) % 3]],
                      11 + a, 23 + a, 5, 6))
    cands.append((random_deck(0, 14, 401), random_deck(1, 50, 402), 3, 4, 7, 8))
    # ...and decks that CARRY the rare ones: a lane's death beside an ABSOLVE,
    # and a 5g 2s commander a player has to live long enough to afford
    for i in range(24):
        cands.append((random_deck(2, 24, 600 + i, force=("Templar", "Intercessor",
                                                          "Novice", "Zealot")),
                      random_deck(1, 24, 700 + i), 40 + i, 50 + i, 60 + i, 70 + i))
        cands.append((random_deck(0, 24, 800 + i, force=("Tollkeeper", "Reeve"),
                                  commander="Old Guard"),
                      random_deck(2, 24, 900 + i), 80 + i, 90 + i, 5 + i, 9 + i))
    for i in range(400):
        fa, fb = i % 3, (i // 3) % 3
        cands.append((random_deck(fa, 30 + i % 21, 1000 + i),
                      random_deck(fb, 30 + (i * 7) % 21, 2000 + i),
                      i * 3 + 1, i * 5 + 2, i + 3, i + 4))
    for n, (da, db, sa, sb, aa, ab) in enumerate(cands):
        FIRED.clear()
        data, log, m = play_match(da, db, sa, sb, aa, ab)
        if m.result == RES_STALE:
            continue
        if n < 4 or FIRED - have:
            chosen.append(data)
            have |= FIRED
        if have >= want and len(chosen) >= 6:
            break
    blob = bytearray([len(chosen)])
    for d in chosen:
        blob += struct.pack("<H", len(d)) + d
    open(out, "wb").write(blob)
    missing = sorted(want - have)
    print("%s: %d matches, %d bytes, keywords %d of %d%s" % (
        out, len(chosen), len(blob), len(have), len(want),
        " - never fired: %s" % ", ".join(missing) if missing else ""))
    return 1 if missing else 0


def main():
    a = sys.argv[1:]
    if "--selfcheck" in a:
        return selfcheck()

    def opt(name, default):
        if name in a:
            return type(default)(a[a.index(name) + 1])
        return default
    if a[:1] == ["bake"]:
        return bake(a[1])
    if a[:1] == ["report"]:
        report(opt("--n", 300), opt("--seed", 1))
        return 0
    if a[:1] == ["match"]:
        cards()
        fa, fb = a[1], a[2]
        seed = opt("--seed", 7)
        data, log, m = play_match(DECKS[fa], DECKS[fb], seed, seed + 1,
                                  seed + 2, seed + 3)
    elif a[:1] == ["replay"]:
        data = open(a[1], "rb").read()
        log, m = replay(data)
    else:
        print(__doc__)
        return 2
    if opt("--out", ""):
        open(opt("--out", ""), "wb").write(data)
    if opt("--log", ""):
        open(opt("--log", ""), "wb").write(log)
    if "--text" in a:
        print(text(log))
    print("%d rounds, result %d, %d bytes of match file, %d of log"
          % (m.round, m.result, len(data), len(log)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
