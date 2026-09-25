#!/usr/bin/env python3
"""TITHE's ROUND LOOP, played by hand: the plan, hot-seat, a round (SPEC.md 97.12).

Wave 3's gate is three sentences - two humans play a match; neither learns
anything of the other's plan before the reveal; any entry of a plan can be
removed and the board is right afterwards - and this row is the part of each
that a machine can hold. It deals a SEEDED match (`tg_fillq` = 3, the one mode
`tools/duelsim.py` deals the same way), plans P1's round with the mouse as a
player does, and holds every plan, board and pool to the simulator.

WHAT IT ASSERTS, and each one went red on purpose first:

  1. THE DEAL IS THE SIMULATOR'S: both hands, card for card, slot for slot.

  2. EVERY ACTION A PLAYER HAS, BY CLICK: two PLAYS into FRONT, an ORDER armed
     from the hand and placed on a character, the STANCE MARK under that character's feet,
     and a SWAP of two cells. The plan the package holds is exactly the
     actions the simulator applies, and the board the planner sees is the
     simulator's board after them.

  3. ANY ENTRY CAN BE REMOVED, AND THE REST FOLLOW IT (TITHE-PLAN 5.0.2). The
     FIRST play is taken out of the list: the second play moves up a lane
     and is numbered again, and the order and the stance that named it follow
     it there rather than landing on whoever took its place. The plan is the
     simulator's, the board is, the pool is - and the glass is exactly a whole
     repaint, so nothing the edit moved was left behind.

  4. NEITHER PLANNER LEARNS THE OTHER'S PLAN (TITHE-PLAN 6.3.1). The pass
     screen is two lines and nothing else; P2 then plans on the FROZEN board -
     no P1 character on it, P1's pool unspent.

  5. THE ROUND IS THE SIMULATOR'S: both commits, the resolution and the next
     upkeep - HP, pools, the next hand and every cell.

  6. A REFUSAL IS SAID AND GREYED (SPEC.md 97.12.10.3).

  7. THE FULL CARD (SPEC.md 97.12.10.8): a right click puts it up with the
     glass under it saved, and a key puts back exactly what it covered.

  8. THE MULLIGAN (SPEC.md 97.12.10.9): offered, modal, REDRAW the
     simulator's mulligan, KEEP exact.

    make && make tithedisk && python3 tests/tithegame.py [machine]
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402
import os88mouse                                          # noqa: E402
import duelsim                                            # noqa: E402
import os88tithecards as tcards                           # noqa: E402
import titheterr as te                                    # noqa: E402

SEEDS = (8, 777)        # P1: Axeman, Brace, Slinger, Shieldbearer, Rally
SYMS = ("tg_fillq", "tg_tseed", "tg_plan0", "tg_plan1", "ti_cards",
        "tg_lx", "tg_ly", "tg_list", "tg_ph", "tg_side",
        "ti_p1gold", "ti_p2gold", "ti_p1hp", "ti_p2hp", "ti_p1soul", "ti_p2soul",
        "ti_cardx", "ti_cardw", "ti_cardh", "ti_cardpitch", "ti_by", "ti_bx",
        "ti_cw", "ti_ch", "ti_rise", "ti_insx", "ti_insy", "ti_bs", "ti_bh",
        "ti_fw", "ti_fh", "ti_ox", "ti_oy", "ti_cw_box", "ti_ch_box",
        "ti_rpq", "ti_row", "ti_rv", "ti_nframe", "ti_hx", "ti_tg1x",
        "ti_hty", "ti_rowst", "tg_tgt", "tg_arm", "TI_C_FI1", "TI_C_RI1",
        "ti_shg", "ti_shs", "tg_prompt", "ti_played", "ti_s_ngold",
        "ti_s_nsoul", "TI_C_COST", "tg_frz", "ti_s_cconf", "tg_incbuf", "tg_newslot",
        "ti_rv_trail", "ti_card_fadein", "tg_fcard", "ti_fwseg", "ti_fwx",
        "ti_fwy", "ti_fwh", "ti_fwcard", "tg_mull", "ti_mbup", "ti_mbx",
        "ti_mby", "ti_mbseg", "tg_cart", "tg_dsync", "tg_pvd1", "tg_pvd2",
        "tr_cells", "ti_hudbuf",
        "TI_C_SIZE", "TI_C_CARD", "TI_C_HP", "TI_HAND")
EQUS = ("tr_cells", "ti_hudbuf", "TI_C_SIZE", "TI_C_CARD", "TI_C_HP", "TI_HAND", "TI_C_FI1",
        "TI_C_RI1", "ti_s_ngold", "ti_s_nsoul", "TI_C_COST", "tg_frz", "ti_s_cconf", "tg_incbuf", "ti_rv_trail",
        "ti_card_fadein")
BCOL = (1, 0, 2, 3)     # side x 2 + column -> the board's column (tg_bcol)
fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    src = open(os.path.join(ROOT, "apps/tithe/tithe.asm"), encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "tithegame-off.asm")
    out = os.path.join(ROOT, "build", "tithegame-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp], cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def sim_match():
    cards, decks = tcards.load()
    m = duelsim.Match(decks["BULWARK"], decks["CHOIR"], *SEEDS)
    m.upkeep()
    return m


def sim_board(m):
    """{board cell: (card, hp)} for every occupied cell."""
    out = {}
    for s in (0, 1):
        for col in (0, 1):
            for lane in range(duelsim.LANES):
                c = m.sides[s].cells[col][lane]
                if c.card != duelsim.EMPTY:
                    out[BCOL[s * 2 + col] * duelsim.LANES + lane] = (c.card, c.hp)
    return out


def run(mach, off):
    print("  --- %s" % mach)
    with os88ui.boot("build/os8088-360.img", apps="build/tithe360.img",
                     machine=mach) as ui:
        m = ui.m
        ui.path("B:/TITHE.O88")
        win = [w for w in os88geom.windows(m) if w.title == "Tithe"][0]
        seg = struct.unpack(
            "<H", bytes(m.read(os88geom.winptr(m, win) + os88geom.W_SEG, 2)))[0]
        ui.raise_window(win)
        os88marty.guest_sleep(m, 6.0)

        def rw(name):
            return struct.unpack("<H", bytes(m.readseg(seg, off[name], 2)))[0]

        def rb(name, i=0):
            return m.readseg(seg, off[name] + i, 1)[0]

        def view(v, field):
            return rb("ti_cards", v * off["TI_C_SIZE"] + off[field])

        def hand():
            return [view(k, "TI_C_CARD") for k in range(off["TI_HAND"])]

        def board():
            out = {}
            for c in range(20):
                card = view(off["TI_HAND"] + c, "TI_C_CARD")
                if card != 0xFF:
                    out[c] = (card, view(off["TI_HAND"] + c, "TI_C_HP"))
            return out

        def plan(side=0):
            b = bytes(m.readseg(seg, off["tg_plan%d" % side], 1 + 16 * 3))
            return [tuple(b[1 + i * 3:4 + i * 3]) for i in range(b[0])]

        # the seeded deal
        m.write(seg * 16 + off["tg_tseed"], struct.pack("<HH", *SEEDS))
        m.write(seg * 16 + off["tg_fillq"], bytes([3]))
        os88marty.until(m, lambda _: rb("tg_fillq") == 0, "the deal",
                        poll=0.2, limit=60.0)
        os88marty.guest_sleep(m, 2.0)
        g = {s: (off[s] if s in EQUS else rw(s)) for s in SYMS}
        sm = sim_match()
        want = sm.sides[0].hand + [0xFF] * (7 - len(sm.sides[0].hand))
        check(hand() == want, "1. P1's hand is the simulator's deal",
              "%s against %s" % (hand(), want))
        # ...and an ORDER has no position: slot 1 is Brace, and its REAR pair
        # is its one block, as its FRONT pair is (SPEC.md 97.4.8.2) - where
        # REAR showed the empty rear block the table never gives an order
        pair = lambda f: [view(1, f) if i == 0 else
                          rb("ti_cards", off["TI_C_SIZE"] + off[f] + i)
                          for i in range(4)]
        check(view(1, "TI_C_HP") == 0 and pair("TI_C_FI1") == pair("TI_C_RI1")
              and any(pair("TI_C_FI1")), "an order card shows the same stats "
              "in either row", "hp %d front %s rear %s" % (
                  view(1, "TI_C_HP"), pair("TI_C_FI1"), pair("TI_C_RI1")))

        mo = os88mouse.Mouse(marty=m)
        park = (win.x + 4, max(0, win.y - 6))

        def settle(t=1.0):
            mo.to(*park)
            os88marty.guest_sleep(m, t)

        def card_at(slot):
            return (g["ti_cardx"] + g["ti_cardw"] // 2,
                    g["ti_by"] + slot * g["ti_cardpitch"] + g["ti_cardh"] // 2)

        def cell_at(c, lane):
            x0 = g["ti_bx"] + c * g["ti_cw"]
            y0 = g["ti_by"] + (3 - c) * g["ti_rise"] + lane * g["ti_ch"]
            return x0, y0

        def fig(c, lane):
            x0, y0 = cell_at(c, lane)
            return (x0 + g["ti_insx"] + g["ti_bs"] * 4,
                    y0 + g["ti_insy"] + g["ti_bh"] // 2)

        def mark(c, lane):              # the STANCE MARK under a P1 figure's
            x0, y0 = cell_at(c, lane)   # feet (SPEC.md 97.12.10.1)
            return (x0 + g["ti_insx"] + 12,
                    y0 + g["ti_insy"] + g["ti_bh"] - 3)

        def play(slot):
            n0 = rw("ti_nframe")
            mo.click(*card_at(slot), settle=0.2)
            os88marty.until(m, lambda _: (rw("ti_nframe") - n0) & 0xFFFF > 12
                            and rb("ti_rv") == 0, "the reveal", poll=0.2)
            settle(0.8)

        def click(xy, t=1.0):
            mo.click(*xy, settle=0.2)
            settle(t)

        # THE DESTINATION MARK (SPEC.md 97.12.10.10): the one empty cell whose
        # key is 80h is where the next PLAY lands - P1's FRONT is board
        # column 1, so lane 0 is cell 5 - and a play moves it on a lane
        def dests():
            os88marty.until(m, lambda _: rb("tg_dsync") == 0, "the mark",
                            poll=0.2, limit=30.0)
            cart = m.readseg(seg, off["tg_cart"], 20)
            return [c for c in range(20) if cart[c] == 0x80]

        check(dests() == [5], "the next PLAY's cell is marked", dests())

        # 2. every action, by click
        play(0)                                  # Axeman, FRONT lane 0
        check(dests() == [6], "...and a play moves the mark on a lane",
              dests())
        play(2)                                  # Slinger, FRONT lane 1
        click(card_at(1))                        # Brace, armed...
        # ...AND IT STAYS LIT with the pointer parked off it (SPEC.md
        # 97.12.10.2): a resting card is white paper and a lit one black
        _, _, px = te.mono(m)
        top = g["ti_by"] + g["ti_cardpitch"]
        lit = sum(1 for y in range(top, top + g["ti_cardh"])
                  for x in range(g["ti_cardx"], g["ti_cardx"] + g["ti_cardw"])
                  if px[y][x])
        area = g["ti_cardh"] * g["ti_cardw"]
        check(rb("tg_arm") == 1 and lit * 2 < area, "an armed ORDER stays "
              "lit with the pointer off it", "arm %d, %d of %d lit"
              % (rb("tg_arm"), lit, area))
        mo.to(*fig(1, 1))
        os88marty.guest_sleep(m, 0.6)
        check(rw("tg_tgt") == 1 * 5 + 1, "...and the character under the "
              "pointer is its target", "tg_tgt %d" % rw("tg_tgt"))
        click(fig(1, 1))                         # ...onto the Slinger
        check(rb("tg_arm") == 0xFF and rw("tg_tgt") == 0xFFFF, "...and "
              "placing it lets both go", "arm %d tgt %d"
              % (rb("tg_arm"), rw("tg_tgt")))
        click(mark(1, 1))                        # the Slinger's stance
        click(fig(1, 0))                         # a swap: the Axeman...
        with os88marty.bp_trace(m, seg * 16 + off["ti_rv_trail"]) as tr:
            click(fig(0, 2), 2.0)                # ...and an empty rear cell
        check(tr.n >= 8, "a SWAP's sparks cross before the cells are drawn "
              "(SPEC.md 97.12.10.7)", "%d trail draws" % tr.n)
        A, S, B = 1, 5, 24
        full = [(1, A, 0), (1, S, 0), (2, B, 2), (4, 1, 1), (3, 0, 7)]
        check(plan() == full, "2. every action by click is in the plan, as "
              "the engine names it", "%s" % plan())
        sm = sim_match()
        sm.apply(0, full)
        check(board() == sim_board(sm), "...and the board is the simulator's "
              "after it", "%s against %s" % (board(), sim_board(sm)))
        check(rb("ti_p1gold") == sm.sides[0].gold, "...and so is the pool",
              "%d against %d" % (rb("ti_p1gold"), sm.sides[0].gold))

        # THE SHORTFALLS (SPEC.md 97.12.10.3): every card in the hand against
        # the pool the plan LEAVES, gold and souls, the simulator's
        cs = duelsim.cards()
        want, got = [], []
        for k in range(7):
            cid = view(k, "TI_C_CARD")
            if cid == 0xFF:
                want.append((0, 0))
            else:
                want.append((max(0, cs[cid].cg - sm.sides[0].gold),
                             max(0, cs[cid].cs - sm.sides[0].souls)))
            got.append((rb("ti_shg", k), rb("ti_shs", k)))
        check(got == want, "the hand's shortfalls are the pool's after "
              "the plan", "%s against %s" % (got, want))

        # 3. the first entry out
        m.key("KeyL")
        settle(1.5)
        check(rb("tg_list") == 1, "the plan is shown as a list", rb("tg_list"))
        click((rw("tg_lx") + 16, rw("tg_ly") + 4), 2.0)
        cut = [(1, S, 0), (2, B, 1), (4, 0, 1), (3, 0, 7)]
        check(plan() == cut, "3. the first play removed: the rest re-applied, "
              "the order and the stance FOLLOWING the play they named",
              "%s" % plan())
        sm = sim_match()
        sm.apply(0, cut)
        check(board() == sim_board(sm), "...the board is the simulator's",
              "%s against %s" % (board(), sim_board(sm)))
        check(rb("ti_p1gold") == sm.sides[0].gold, "...the pool came back",
              "%d against %d" % (rb("ti_p1gold"), sm.sides[0].gold))
        m.key("KeyP")
        os88marty.guest_sleep(m, 0.4)
        _, _, a = te.mono(m)
        m.write(seg * 16 + off["ti_rpq"], b"\x01")
        os88marty.until(m, lambda _: rb("ti_rpq") == 0, "a repaint", poll=0.1)
        os88marty.guest_sleep(m, 0.3)
        _, _, b = te.mono(m)
        m.key("KeyP")
        box = (g["ti_ox"], g["ti_by"], g["ti_ox"] + g["ti_cw_box"],
               g["ti_oy"] + g["ti_ch_box"])
        d = [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2])
             if a[y][x] != b[y][x]]
        check(not d, "...and the glass is exactly a whole repaint",
              "%d px, first %s" % (len(d), d[:4]))
        m.key("KeyL")
        settle(1.5)
        # ...P1 leaves the toggle on REAR, by its own box on the HUD
        mo.click(rw("ti_hx") + rw("ti_tg1x") + 4, rw("ti_oy") + rw("ti_hty") + 3,
                 settle=0.2)
        os88marty.until(m, lambda _: rb("ti_rowst") == 0, "the toggle's "
                        "redraw", poll=0.2, limit=30.0)
        check(rw("ti_row") == 1, "P1 can leave the toggle on REAR",
              "row %d" % rw("ti_row"))
        check(dests() == [0], "...and the mark goes to REAR's first empty "
              "cell with it", dests())

        # 4. the pass screen, and P2 on the frozen board
        m.key("Enter")
        settle(2.0)
        check(rb("tg_ph") == 1 and rb("tg_side") == 1, "P1's commit hands "
              "the machine over", "phase %d side %d" % (rb("tg_ph"), rb("tg_side")))
        _, _, px = te.mono(m)
        y1 = g["ti_oy"] + g["ti_ch_box"] // 2 - 12
        text = set(range(y1 - 1, y1 + 9)) | set(range(y1 + 15, y1 + 25))
        lit = [(x, y) for y in range(box[1] - 40 if box[1] > 40 else 0, box[3])
               for x in range(box[0], box[2])
               if y >= g["ti_oy"] and y not in text and px[y][x]]
        check(not lit, "4. the pass screen is two lines and nothing else",
              "%d lit px, first %s" % (len(lit), lit[:4]))
        m.key("Enter")
        settle(4.0)
        check(board() == {}, "...P2 plans on the FROZEN board: none of P1's "
              "characters on it", "%s" % board())
        check(rw("ti_row") == 0, "...and starts on FRONT, not on P1's REAR "
              "(SPEC.md 97.4.8.2): the row is where a played card goes",
              "row %d" % rw("ti_row"))
        check(rb("ti_p1gold") == 6, "...and P1's pool unspent",
              "%d" % rb("ti_p1gold"))
        sm = sim_match()
        want = sm.sides[1].hand + [0xFF] * (7 - len(sm.sides[1].hand))
        check(hand() == want, "...with P2's own hand", "%s against %s"
              % (hand(), want))
        # AN EMPTY PLAN IS ASKED ABOUT ONCE (SPEC.md 97.12.10.4): Enter does
        # not commit it, and says so - and a play after it is not asked
        m.key("Enter")
        settle(1.0)
        check(rb("tg_ph") == 0 and rb("tg_side") == 1
              and rw("tg_prompt") == off["ti_s_cconf"], "an EMPTY plan's "
              "commit asks first", "phase %d side %d prompt %04x"
              % (rb("tg_ph"), rb("tg_side"), rw("tg_prompt")))
        play(0)                                  # P2's first card, FRONT
        p2 = plan(1)

        # 5. the round, FOUGHT ON THE GLASS a lane at a time (97.12.8): the
        # commit starts it, and the pass screen is where it ends
        m.key("Enter")
        os88marty.until(m, lambda _: rb("tg_ph") == 3, "the round to begin",
                        poll=0.1, limit=20.0)
        check(rb("tg_list") == 2, "the panel is the round's LOG while it is "
              "fought", rb("tg_list"))
        if os.environ.get("TITHEGAME_SHOT"):
            os88marty.guest_sleep(m, 3.0)
            w, h, rows = m.vram()
            os88marty.write_png(os.environ["TITHEGAME_SHOT"] + "-" + mach + ".png",
                                w, h, rows)
        os88marty.until(m, lambda _: rb("tg_ph") == 1, "the round to end",
                        poll=0.2, limit=90.0)
        m.key("Enter")
        settle(4.0)
        sm = sim_match()
        sm.apply(0, cut)
        sm.apply(1, p2)
        kept = (sm.sides[0].gold, sm.sides[0].souls, len(sm.sides[0].hand))
        sm.resolve()
        sm.upkeep()
        check(plan(1) == [] and p2 == [(1, want[0], 0)],
              "P2's plan was the one play, and both plans are spent", p2)
        got = (rb("ti_p1hp"), rb("ti_p2hp"), rb("ti_p1gold"), rb("ti_p2gold"),
               rb("ti_p1soul"), rb("ti_p2soul"))
        exp = (sm.sides[0].hp, sm.sides[1].hp, sm.sides[0].gold,
               sm.sides[1].gold, sm.sides[0].souls, sm.sides[1].souls)
        check(got == exp, "5. the round: HP, gold and souls are the "
              "simulator's", "%s against %s" % (got, exp))
        check(board() == sim_board(sm), "...every cell is",
              "%s against %s" % (board(), sim_board(sm)))
        want = sm.sides[0].hand + [0xFF] * (7 - len(sm.sides[0].hand))
        check(hand() == want, "...and P1's next hand is",
              "%s against %s" % (hand(), want))
        # THE UPKEEP, SAID (SPEC.md 97.12.10.5): what P1's pool gained since
        # they committed, and the card the upkeep drew - which is NEW
        dg = sm.sides[0].gold - kept[0]
        ds = sm.sides[0].souls - kept[1]
        txt = "INCOME %+dG" % dg + (" %+dS" % ds if ds else "")
        if len(sm.sides[0].hand) > kept[2]:
            txt += "  DREW " + duelsim.cards()[sm.sides[0].hand[-1]].name
        got = bytes(m.readseg(seg, off["tg_incbuf"], 56)).split(b"\0")[0]
        check(got.decode().upper() == txt.upper(), "the next turn says its "
              "income and the card it drew", "%r against %r" % (got, txt))
        check(rw("tg_newslot") == len(sm.sides[0].hand) - 1, "...and that "
              "card is NEW in its slot", "slot %d" % rw("tg_newslot"))

        # AN UNDONE PLAY FADES (SPEC.md 97.12.10.7): its character dissolves
        # out and its card comes home at three levels, and the board and the
        # hand are then exactly what a whole repaint draws
        n0 = plan()
        play(next(i for i in range(7) if view(i, "TI_C_CARD") != 0xFF
                  and not rb("ti_shg", i) and not rb("ti_shs", i)))
        with os88marty.bp_trace(m, seg * 16 + off["ti_card_fadein"]) as tr:
            m.key("KeyU")
            settle(2.0)
        check(tr.n == 3 and plan() == n0, "an undone PLAY fades: its card "
              "comes home in three steps", "%d steps, plan %s" % (tr.n, plan()))
        m.key("KeyP")
        os88marty.guest_sleep(m, 0.4)
        _, _, a = te.mono(m)
        m.write(seg * 16 + off["ti_rpq"], b"\x01")
        os88marty.until(m, lambda _: rb("ti_rpq") == 0, "a repaint", poll=0.1)
        os88marty.guest_sleep(m, 0.3)
        _, _, b = te.mono(m)
        m.key("KeyP")
        d = [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2])
             if a[y][x] != b[y][x]]
        check(not d, "...and leaves the glass exactly a whole repaint",
              "%d px, first %s" % (len(d), d[:4]))

        # 6. A REFUSAL (SPEC.md 97.12.10.3), which the seeded match never
        # meets: P1's frozen gold goes to NOTHING, and a card is clicked
        settle(1.0)
        cs = duelsim.cards()
        k = next(i for i in range(7) if view(i, "TI_C_CARD") != 0xFF
                 and cs[view(i, "TI_C_CARD")].cg > 0)
        top = g["ti_by"] + k * g["ti_cardpitch"]
        rect = lambda px: sum(1 for y in range(top, top + g["ti_cardh"])
                              for x in range(g["ti_cardx"],
                                             g["ti_cardx"] + g["ti_cardw"])
                              if px[y][x])
        before = rect(te.mono(m)[2])
        m.write(seg * 16 + off["tg_frz"] + 2, b"\x00")      # SD_GOLD
        n = plan()
        mo.click(*card_at(k), settle=0.2)
        os88marty.guest_sleep(m, 0.5)
        say = rw("tg_prompt")
        check(plan() == n and say == off["ti_s_ngold"], "6. a card that "
              "cannot be paid for is refused, and the HUD says why",
              "prompt %04x, plan %s" % (say, plan()))
        check(rb("ti_shg", k) == cs[view(k, "TI_C_CARD")].cg,
              "...its shortfall is its whole cost", rb("ti_shg", k))
        settle(1.0)
        check(rw("tg_prompt") == 0, "...until the pointer moves",
              "%04x" % rw("tg_prompt"))
        after = rect(te.mono(m)[2])
        check(after * 100 < before * 85, "...and the card is GREYED on the "
              "glass", "%d lit against %d" % (after, before))

        # 7. THE FULL CARD (SPEC.md 97.12.10.8): a RIGHT click puts the whole
        # card over the board, framed, with the glass under it SAVED - and a
        # key takes it away and puts back exactly what was there. The wheel
        # is paused so the only thing that can differ is what the card did
        k = next(i for i in range(7) if view(i, "TI_C_CARD") != 0xFF)
        m.key("KeyP")
        mo.to(*card_at(k))
        os88marty.guest_sleep(m, 0.8)
        _, _, a = te.mono(m)
        mo._edge(True, btn=2)
        mo._edge(False, btn=2)
        os88marty.guest_sleep(m, 1.0)
        fx, fy, fh = rw("ti_fwx"), rw("ti_fwy"), rw("ti_fwh")
        _, _, px = te.mono(m)
        top = sum(1 for x in range(fx, fx + 352) if px[fy][x])
        check(rb("tg_fcard") == 1 and rw("ti_fwseg") != 0
              and rb("ti_fwcard") == view(k, "TI_C_CARD") and top == 352
              and fh > 24, "7. a RIGHT click puts the whole card up, framed, "
              "with the glass under it saved",
              "up %d seg %04x card %d/%d top %d rows %d" % (
                  rb("tg_fcard"), rw("ti_fwseg"), rb("ti_fwcard"),
                  view(k, "TI_C_CARD"), top, fh))
        m.key("KeyX")
        os88marty.guest_sleep(m, 0.8)
        _, _, b = te.mono(m)
        m.key("KeyP")
        d = [(x, y) for y in range(20, len(a)) for x in range(len(a[0]))
             if a[y][x] != b[y][x]]
        check(rb("tg_fcard") == 0 and rw("ti_fwseg") == 0 and not d,
              "...and a key takes it away: the claim freed and the glass "
              "EXACTLY what it covered", "up %d seg %04x, %d px, first %s" % (
                  rb("tg_fcard"), rw("ti_fwseg"), len(d), d[:4]))

        # A HOVERED CHARACTER SAYS WHAT IT WILL DO (SPEC.md 97.12.10.11), on
        # the tests' FULL board: the engine's cells copied into a simulator
        # match, and every character's inverted cells and its line against
        # the simulator's own targeting - both sides', P1 planning
        m.write(seg * 16 + off["tg_fillq"], bytes([1]))
        os88marty.until(m, lambda _: rb("tg_fillq") == 0, "the full board",
                        poll=0.2, limit=60.0)
        settle(1.0)
        fb = sim_match()
        raw = m.readseg(seg, off["tr_cells"], 20 * 20)
        names = {c.id: c.name.upper() for c in duelsim.cards()}
        for i in range(20):
            e = raw[i * 20:i * 20 + 20]
            side, rest = divmod(i, 10)
            col, lane = divmod(rest, 5)
            c = fb.sides[side].cells[col][lane]
            (c.card, c.inst, c.hp, c.sh, c.st, c.bm, c.br, c.mark, c.kk,
             c.om, c.orr, c.os, c.og, c.oh, c.opi, c.osc, c.owd, c.used) = \
                tuple(e[:18])

        def bcell(side, col, lane):
            return BCOL[side * 2 + col] * duelsim.LANES + lane

        def want_pv(side, col, lane):
            cell = fb.sides[side].cells[col][lane]
            pierce = (duelsim.kw(cell, col, duelsim.K["PIERCE"]) or 0) + cell.opi
            out, words = [0xFFFF, 0xFFFF], []
            for k, dmg, t in (
                    (0, col == duelsim.FRONT and fb.melee(side, col, lane),
                     lambda: fb.melee_target(1 - side, lane)),
                    (1, fb.ranged(side, col, lane),
                     lambda: fb.ranged_target(1 - side, lane, cell.st, pierce))):
                if dmg:
                    tt = t()
                    if tt:
                        out[k] = bcell(1 - side, *tt)
                        tc = fb.sides[1 - side].cells[tt[0]][tt[1]].card
                        words.append("ON " + names[tc])
                    else:
                        words.append("ON P%d" % (2 - side))
            return tuple(out), words

        bad, n_cell = [], 0
        for side in (0, 1):
            for col in (0, 1):
                for lane in range(duelsim.LANES):
                    if fb.sides[side].cells[col][lane].card == duelsim.EMPTY:
                        continue
                    bc = bcell(side, col, lane)
                    mo.to(*fig(bc // duelsim.LANES, lane))
                    os88marty.guest_sleep(m, 1.2)
                    got = (rw("tg_pvd1"), rw("tg_pvd2"))
                    line = bytes(m.readseg(seg, off["ti_hudbuf"], 64)) \
                        .split(b"\0")[0].decode("latin-1")
                    want, words = want_pv(side, col, lane)
                    n_cell += sum(1 for w in want if w != 0xFFFF)
                    if got != want or any(w not in line for w in words):
                        bad.append("cell %d: %s %r against %s %s" % (
                            bc, got, line, want, words))
        settle(0.8)
        check(not bad and n_cell >= 8 and (rw("tg_pvd1"), rw("tg_pvd2")) ==
              (0xFFFF, 0xFFFF), "a hovered character's line and inverted "
              "cells are the simulator's targeting, both sides', and go back "
              "when the pointer leaves", "%s (%d cells aimed at)" % (
                  bad[:3], n_cell))

        # 8. THE MULLIGAN (SPEC.md 97.12.10.9): a fresh deal of the same seeds,
        # and the offer a real match makes at P1's first turn. Nothing else
        # answers under it; REDRAW's hand is the simulator's mulligan; and
        # KEEP leaves the glass exactly a whole repaint
        def deal_offer():
            m.write(seg * 16 + off["tg_tseed"], struct.pack("<HH", *SEEDS))
            m.write(seg * 16 + off["tg_fillq"], bytes([3]))
            os88marty.until(m, lambda _: rb("tg_fillq") == 0, "the deal",
                            poll=0.2, limit=60.0)
            settle(1.0)
            m.write(seg * 16 + off["tg_mull"], b"\x01")
            os88marty.until(m, lambda _: rb("ti_mbup") == 1, "the offer",
                            poll=0.2, limit=30.0)
            settle(0.5)
            return rw("ti_mbx"), rw("ti_mby")

        bx0, by0 = deal_offer()
        _, _, px = te.mono(m)
        top = sum(1 for x in range(bx0, bx0 + 352) if px[by0][x])
        n = plan()
        click(card_at(0))
        m.key("KeyU")
        m.key("KeyL")
        settle(0.5)
        check(top == 352 and rw("ti_mbseg") != 0 and plan() == n
              and rb("tg_mull") == 1 and rb("tg_list") == 0,
              "8. P1's first turn offers a MULLIGAN, and nothing else answers "
              "under it", "top %d seg %04x plan %s offer %d list %d" % (
                  top, rw("ti_mbseg"), plan(), rb("tg_mull"), rb("tg_list")))
        click((bx0 + 24 * 8 + 56, by0 + 34 + 5), 0.5)
        os88marty.until(m, lambda _: rb("ti_rowst") == 0, "the new hand",
                        poll=0.2, limit=30.0)
        sm = sim_match()
        sm.mulligan(0)
        want = sm.sides[0].hand + [0xFF] * (7 - len(sm.sides[0].hand))
        check(hand() == want and rb("tg_mull") == 0 and rb("ti_mbup") == 0
              and rw("ti_mbseg") == 0, "...REDRAW deals the simulator's "
              "mulligan, and the offer and its claim are gone",
              "%s against %s, offer %d up %d seg %04x" % (
                  hand(), want, rb("tg_mull"), rb("ti_mbup"), rw("ti_mbseg")))
        bx0, by0 = deal_offer()
        click((bx0 + 6 * 8 + 56, by0 + 34 + 5), 0.5)
        sm = sim_match()
        want = sm.sides[0].hand + [0xFF] * (7 - len(sm.sides[0].hand))
        m.key("KeyP")
        os88marty.guest_sleep(m, 0.4)
        _, _, a = te.mono(m)
        m.write(seg * 16 + off["ti_rpq"], b"\x01")
        os88marty.until(m, lambda _: rb("ti_rpq") == 0, "a repaint", poll=0.1)
        os88marty.guest_sleep(m, 0.3)
        _, _, b = te.mono(m)
        m.key("KeyP")
        d = [(x, y) for y in range(box[1], box[3]) for x in range(box[0], box[2])
             if a[y][x] != b[y][x]]
        check(hand() == want and rb("tg_mull") == 0 and not d,
              "...and KEEP keeps the hand and leaves the glass exactly a whole "
              "repaint", "%s against %s, offer %d, %d px, first %s" % (
                  hand(), want, rb("tg_mull"), len(d), d[:4]))


def main():
    off = offsets()
    for mach in (sys.argv[1:] or ("os8088_5150_herc_gla", "os8088_5150_cga_gla")):
        run(mach, off)
    print("tithegame: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
