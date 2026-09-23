#!/usr/bin/env python3
"""TITHE's CARD TABLE: apps/tithe/cards.txt -> the package and the simulator.

    python3 tools/os88tithecards.py emit        # apps/tithe/ticards.inc
    python3 tools/os88tithecards.py --selfcheck # TITHE-PLAN 15.3's t_tithecards
    python3 tools/os88tithecards.py list        # the table, as the engine reads it

ONE SOURCE (TITHE-PLAN 14.1, SPEC.md 97.11). The package's rules engine reads
the table this emits and tools/duelsim.py imports `load()` from here, so the
assembly and the Python read the same bytes and cannot drift - a card whose
number moves moves in both at the next `make`.

THE RECORD IS THE ENGINE'S, byte for byte (SPEC.md 97.11.2): 24 bytes a card,
two nine-byte stat blocks, and a keyword a byte - its id in the low five bits
and its number in the high three. `record()` builds it and the simulator reads
its stats back OUT of the record rather than out of the parse, so a field the
emitter packs wrongly is wrong in the simulator too and the selfcheck's own
matches see it.

THE SELFCHECK IS THE SHAPE, NOT THE NUMBERS (TITHE-PLAN 7.1, 15.3). Every
number here is a first draft the wave-11 harness exists to replace; what it
holds is that a faction is a whole set - every role, the cost tiers spread,
exactly three commanders, at most eight pure specialists - that a stat is in
TITHE-PLAN 5.2's range and a single integer, that HP is one number on both
blocks, that every name prints in the package's own faces, and that every
starter deck is legal under TITHE-PLAN 9.3.
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(ROOT, "apps/tithe/cards.txt")
OUT = os.path.join(ROOT, "apps/tithe/ticards.inc")

FACTIONS = ["BULWARK", "CHOIR", "COVENANT"]
ROLES = ["melee", "ranged", "shield", "gen", "ident", "order", "cmdr"]
KIND_CHAR, KIND_ORDER, KIND_CMDR = 0, 1, 2

# THE KEYWORDS (SPEC.md 97.11.3). The id is the engine's: never renumber one,
# append. `n` says whether it takes a number; `order` whether an ORDER may
# grant it (the engine carries an order's grants as a pierce count and two
# flags, and nothing else).
KEYWORDS = [
    # name        id  n      order
    ("GUARD",      1, False, False),
    ("BULWARK",    2, True,  False),
    ("RAMPART",    3, False, False),
    ("LEVY",       4, True,  False),
    ("PYRE",       5, True,  False),
    ("PIERCE",     6, True,  True),
    ("VOLLEY",     7, False, False),
    ("SCORCH",     8, False, True),
    ("KINDLE",     9, False, False),
    ("VIGIL",     10, False, False),
    ("BLESS",     11, True,  False),
    ("INTERCEDE", 12, False, False),
    ("ABSOLVE",   13, False, False),
    ("MUSTER",    14, False, False),
    ("STANDFAST", 15, False, False),
    ("STEWARD",   16, False, False),
    ("HYMN",      17, False, False),
    ("CHORUS",    18, False, False),
    ("REQUIEM",   19, False, False),
    ("SANCTUARY", 20, False, False),
    ("MERCY",     21, False, False),
    ("MARTYR",    22, False, False),
    ("WARD",      23, False, True),
]
KW = {k[0]: k for k in KEYWORDS}
KWID = {k[0]: k[1] for k in KEYWORDS}
COMMANDER_KW = {"MUSTER", "STANDFAST", "STEWARD", "HYMN", "CHORUS", "REQUIEM",
                "SANCTUARY", "MERCY", "MARTYR"}

# TITHE-PLAN 5.2's ranges, the record's stat order
STATS = ("m", "r", "hp", "s", "g", "h")
RANGE = {"m": (0, 6), "r": (0, 5), "hp": (1, 12), "s": (0, 4), "g": (0, 4),
         "h": (0, 6)}
POWER = (1, 10)
KWMAX = 3                           # keywords a block
NAMEMAX = 12
NAMECHARS = set(" 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-.+/,:")

REC = 24                            # the card record (SPEC.md 97.11.2)
BLK = 9                             # ...and a stat block in it

# TITHE-PLAN 7.1's template: role -> the cost tiers it fills
TEMPLATE = {"melee": [1, 2, 3, 4, 5], "ranged": [1, 2, 3, 4, 5],
            "shield": [2, 3, 3, 4, 5], "gen": [1, 1, 2, 3, 4],
            "ident": [3, 4, 5, 6], "order": [1, 2, 3]}
PUREMAX = 8
DECKMIN, DECKMAX, COPIES = 14, 50, 2


class Card:
    pass


def cost_parse(t):
    m = re.fullmatch(r"(?:(\d+)g)?(?:(\d+)s)?", t)
    if not m or not t:
        raise ValueError("cost %r is not like 3g, 2s or 5g1s" % t)
    return int(m.group(1) or 0), int(m.group(2) or 0)


def kw_parse(tok):
    m = re.fullmatch(r"([A-Z]+)(\d*)", tok)
    if not m or m.group(1) not in KW:
        raise ValueError("no keyword %r" % tok)
    name, n = m.group(1), m.group(2)
    if KW[name][2] != bool(n):
        raise ValueError("%s %s a number" % (name, "takes" if KW[name][2]
                                             else "does not take"))
    n = int(n or 0)
    if n > 7:
        raise ValueError("%s%d: a keyword's number is three bits" % (name, n))
    return name, n


def block_parse(text, order=False):
    toks = text.split()
    nstat = 5 if order else 6
    if len(toks) < nstat or not all(t.isdigit() for t in toks[:nstat]):
        raise ValueError("block %r wants %d numbers" % (text, nstat))
    vals = [int(t) for t in toks[:nstat]]
    if order:                       # +m +r +s +g +h: no HP of its own
        vals = vals[:2] + [0] + vals[2:]
    kws = [kw_parse(t) for t in toks[nstat:]]
    return dict(zip(STATS, vals)), kws


def load(path=SRC):
    """The table: (cards, decks). A card's stats are read back OUT of its
    record, so the simulator plays the bytes the package carries."""
    cards, decks, faction = [], {}, None
    for n, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            if line.startswith("faction "):
                faction = line.split()[1]
                if faction not in FACTIONS:
                    raise ValueError("no faction %r" % faction)
                continue
            if line.startswith("deck "):
                head, body = line[5:].split(":", 1)
                decks[head.strip()] = [x.strip() for x in body.split(",")]
                continue
            f = [x.strip() for x in line.split("|")]
            c = Card()
            c.line = n
            c.name, c.role = f[0], f[1]
            if c.role not in ROLES:
                raise ValueError("no role %r" % c.role)
            c.faction = FACTIONS.index(faction)
            c.cg, c.cs = cost_parse(f[2])
            if c.role == "order":
                if len(f) != 5 or f[3] != "-":
                    raise ValueError("an order is name|order|cost|-|effect")
                c.kind, c.power = KIND_ORDER, 0
                c.blocks = [block_parse(f[4], order=True), ({}, [])]
                c.blocks[1] = (dict.fromkeys(STATS, 0), [])
            else:
                if len(f) != 6:
                    raise ValueError("a character is name|role|cost|power|"
                                     "FRONT|REAR")
                c.kind = KIND_CMDR if c.role == "cmdr" else KIND_CHAR
                c.power = int(f[3])
                c.blocks = [block_parse(f[4]), block_parse(f[5])]
            c.id = len(cards)
            cards.append(c)
        except (ValueError, IndexError) as e:
            raise SystemExit("%s:%d: %s" % (path, n, e))
    for c in cards:
        c.rec = record(c)
        c.front, c.rear = unpack_block(c.rec, 6), unpack_block(c.rec, 6 + BLK)
    names = {c.name: c for c in cards}
    out = {}
    for fac, items in decks.items():
        ids = []
        for it in items:
            m = re.fullmatch(r"(.+?)(?:\*(\d+))?", it)
            if m.group(1) not in names:
                raise SystemExit("deck %s: no card %r" % (fac, m.group(1)))
            ids += [names[m.group(1)].id] * int(m.group(2) or 1)
        out[fac] = ids
    return cards, out


def record(c):
    rec = bytearray(REC)
    rec[0], rec[1], rec[2] = c.cg, c.cs, c.power
    rec[3], rec[4], rec[5] = c.kind, c.faction, ROLES.index(c.role)
    for b, (st, kws) in enumerate(c.blocks):
        o = 6 + b * BLK
        for i, k in enumerate(STATS):
            rec[o + i] = st.get(k, 0)
        for i, (name, n) in enumerate(kws):
            rec[o + 6 + i] = KWID[name] | (n << 5)
    return bytes(rec)


def unpack_block(rec, o):
    """A block as the ENGINE sees it: the six stats and {keyword id: n}."""
    st = dict(zip(STATS, rec[o:o + 6]))
    kws = {}
    for b in rec[o + 6:o + BLK]:
        if b & 31:
            kws[b & 31] = b >> 5
    st["kw"] = kws
    return st


def pure(c):
    """TITHE-PLAN 7.1.2: exactly one of MELEE RANGED SHIELD GOLD HEAL non-zero
    across BOTH blocks together - HP never counts."""
    live = {k for k in ("m", "r", "s", "g", "h")
            for b in (c.front, c.rear) if b[k]}
    return len(live) == 1


def deck_problems(ids, cards, faction):
    bad = []
    if not DECKMIN <= len(ids) <= DECKMAX:
        bad.append("%d cards, and a deck is %d to %d" % (len(ids), DECKMIN, DECKMAX))
    for i in set(ids):
        if ids.count(i) > COPIES:
            bad.append("%d copies of %s" % (ids.count(i), cards[i].name))
        if cards[i].faction != faction:
            bad.append("%s is not the deck's faction" % cards[i].name)
    if sum(1 for i in ids if cards[i].kind == KIND_CMDR) > 1:
        bad.append("more than one commander")
    return bad


def selfcheck():
    cards, decks = load()
    bad = []
    for c in cards:
        where = "%s (line %d)" % (c.name, c.line)
        if len(c.name) > NAMEMAX or set(c.name.upper()) - NAMECHARS:
            bad.append("%s: a name is %d printable characters" % (where, NAMEMAX))
        if c.cg + c.cs == 0:
            bad.append("%s costs nothing" % where)
        if c.kind == KIND_ORDER:
            for name, n in c.blocks[0][1]:
                if not KW[name][3]:
                    bad.append("%s: an order cannot grant %s" % (where, name))
            continue
        if not POWER[0] <= c.power <= POWER[1]:
            bad.append("%s: POWER %d" % (where, c.power))
        for b, (st, kws) in enumerate(c.blocks):
            for k, (lo, hi) in RANGE.items():
                if not lo <= st[k] <= hi:
                    bad.append("%s: %s %s %d outside %d..%d" % (
                        where, "FRONT REAR".split()[b], k, st[k], lo, hi))
            if len(kws) > KWMAX:
                bad.append("%s: more than %d keywords a block" % (where, KWMAX))
            for name, n in kws:
                if name in COMMANDER_KW and c.kind != KIND_CMDR:
                    bad.append("%s: %s is a commander's" % (where, name))
                if name == "WARD":
                    bad.append("%s: WARD is an order's" % where)
        # A COMMANDER'S UNIQUE ABILITY (TITHE-PLAN 7.1.1) is the one thing
        # that makes it one, so a commander without one is a mislabelled card
        if c.kind == KIND_CMDR and not any(
                name in COMMANDER_KW for _, kws in c.blocks for name, n in kws):
            bad.append("%s: a commander with no commander's ability" % where)
        # HP IS ONE NUMBER (TITHE-PLAN 5.2: "normally the same"). The engine
        # carries one HP a character and a swap would otherwise have to decide
        # what a wound is worth on the other block.
        if c.front["hp"] != c.rear["hp"]:
            bad.append("%s: FRONT and REAR HP differ" % where)
        # ...and the two blocks are DIFFERENT, which is the card's whole point
        if c.front == c.rear:
            bad.append("%s: FRONT and REAR are the same block" % where)
    for f, fname in enumerate(FACTIONS):
        fc = [c for c in cards if c.faction == f]
        for role, tiers in TEMPLATE.items():
            got = sorted(c.cg + c.cs for c in fc if c.role == role)
            if got != tiers:
                bad.append("%s %s: cost tiers %s, the template's %s"
                           % (fname, role, got, tiers))
        cmdr = [c for c in fc if c.kind == KIND_CMDR]
        if len(cmdr) != 3:
            bad.append("%s: %d commanders, and a faction has three"
                       % (fname, len(cmdr)))
        elif min(c.cg + c.cs for c in cmdr) > 3:
            bad.append("%s: no early commander" % fname)
        np = sum(1 for c in fc if c.kind != KIND_ORDER and pure(c))
        if np > PUREMAX:
            bad.append("%s: %d pure specialists, at most %d" % (fname, np, PUREMAX))
        if fname not in decks:
            bad.append("%s: no starter deck" % fname)
        else:
            for p in deck_problems(decks[fname], cards, f):
                bad.append("%s starter deck: %s" % (fname, p))
            if any(cards[i].kind == KIND_CMDR for i in decks[fname]):
                bad.append("%s starter deck: a starter deck has no commander"
                           % fname)
        # ...and a faction can build a FIFTY-card deck at all (9.3's ceiling)
        room = sum(COPIES for c in fc if c.kind != KIND_CMDR) + 1
        if room < DECKMAX:
            bad.append("%s: %d cards at two copies cannot make %d" % (
                fname, room, DECKMAX))
    # THE INCLUDE IS COMMITTED, so it can be older than the table it was made
    # from - and the package assembles the old one without a word
    if not os.path.exists(OUT) or open(OUT).read() != emit(write=False):
        bad.append("apps/tithe/ticards.inc is not cards.txt's: "
                   "python3 tools/os88tithecards.py emit")
    for line in bad:
        print("  FAIL %s" % line)
    counts = ", ".join("%s %d (%d pure)" % (
        f, sum(1 for c in cards if c.faction == i),
        sum(1 for c in cards if c.faction == i and c.kind != KIND_ORDER and pure(c)))
        for i, f in enumerate(FACTIONS))
    print("os88tithecards: %d cards - %s, %s" % (
        len(cards), counts, "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


def emit(path=OUT, write=True):
    """The include as text; written unless `write` is False, which is how the
    selfcheck asks whether the committed one is stale."""
    cards, decks = load()
    L = ["; GENERATED by tools/os88tithecards.py from apps/tithe/cards.txt -",
         "; do not edit. TITHE's card table (SPEC.md 97.11.2): the rules engine",
         "; and tools/duelsim.py read the same records.", "",
         "TI_NCARDS   equ %d" % len(cards),
         "TI_CR_SIZE  equ %d" % REC,
         "TI_CR_COSTG equ 0",
         "TI_CR_COSTS equ 1",
         "TI_CR_POWER equ 2",
         "TI_CR_KIND  equ 3               ; 0 character, 1 order, 2 commander",
         "TI_CR_FACT  equ 4",
         "TI_CR_ROLE  equ 5",
         "TI_CR_FRONT equ 6               ; m r hp s g h, then three keywords",
         "TI_CR_REAR  equ %d" % (6 + BLK),
         "TI_BLK      equ %d" % BLK,
         "TI_B_M      equ 0",
         "TI_B_R      equ 1",
         "TI_B_HP     equ 2",
         "TI_B_S      equ 3",
         "TI_B_G      equ 4",
         "TI_B_H      equ 5",
         "TI_B_KW     equ 6               ; id in bits 0-4, its number in 5-7",
         "TI_KIND_CHAR equ %d" % KIND_CHAR,
         "TI_KIND_ORDER equ %d" % KIND_ORDER,
         "TI_KIND_CMDR equ %d" % KIND_CMDR, ""]
    for name, kid, _, _ in KEYWORDS:
        L.append("TI_KW_%-10s equ %d" % (name, kid))
    L += ["", "ti_cardtab:"]
    for c in cards:
        L.append("    db " + ", ".join("%d" % b for b in c.rec)
                 + "   ; %d %s" % (c.id, c.name))
    L += ["", "ti_cardname:"]
    for i in range(0, len(cards), 8):
        L.append("    dw " + ", ".join("ti_cn_%d" % c.id for c in cards[i:i + 8]))
    for c in cards:
        L.append("ti_cn_%d: db '%s', 0" % (c.id, c.name.upper()))
    L += ["", "; THE STARTER DECKS (TITHE-PLAN 9.1), a faction each: a count, then",
          "; the card ids"]
    for f in FACTIONS:
        ids = decks[f]
        L.append("ti_deck_%s: db %d" % (f.lower(), len(ids)))
        for i in range(0, len(ids), 16):
            L.append("    db " + ", ".join("%d" % x for x in ids[i:i + 16]))
    text = "\n".join(L) + "\n"
    if not write:
        return text
    open(path, "w").write(text)
    print("%s: %d cards, %d bytes of records" % (os.path.relpath(path, ROOT),
                                                 len(cards), len(cards) * REC))
    return text


def main():
    a = sys.argv[1:]
    if "--selfcheck" in a:
        return selfcheck()
    if a[:1] == ["emit"]:
        emit()
        return 0
    if a[:1] == ["list"]:
        cards, decks = load()
        for c in cards:
            print("%2d %-12s %-6s %s %dg%ds P%d  F %s  R %s%s" % (
                c.id, c.name, c.role, FACTIONS[c.faction][:3], c.cg, c.cs,
                c.power, c.rec[6:15].hex(), c.rec[15:24].hex(),
                "  PURE" if c.kind != KIND_ORDER and pure(c) else ""))
        for f, ids in decks.items():
            print("deck %s: %d cards" % (f, len(ids)))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
