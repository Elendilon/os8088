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
     from the hand and placed on a character, that character's STANCE badge,
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
        "ti_hty", "ti_rowst", "TI_C_FI1", "TI_C_RI1",
        "TI_C_SIZE", "TI_C_CARD", "TI_C_HP", "TI_HAND")
EQUS = ("TI_C_SIZE", "TI_C_CARD", "TI_C_HP", "TI_HAND", "TI_C_FI1",
        "TI_C_RI1")
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

        def badge(c, lane):             # a P1 cell's numbers are LEFT of it
            x0, y0 = cell_at(c, lane)
            return (x0 + 3 * g["ti_fw"] + g["ti_fw"] // 2,
                    y0 + g["ti_insy"] + g["ti_fh"] // 2)

        def play(slot):
            n0 = rw("ti_nframe")
            mo.click(*card_at(slot), settle=0.2)
            os88marty.until(m, lambda _: (rw("ti_nframe") - n0) & 0xFFFF > 12
                            and rb("ti_rv") == 0, "the reveal", poll=0.2)
            settle(0.8)

        def click(xy, t=1.0):
            mo.click(*xy, settle=0.2)
            settle(t)

        # 2. every action, by click
        play(0)                                  # Axeman, FRONT lane 0
        play(2)                                  # Slinger, FRONT lane 1
        click(card_at(1))                        # Brace, armed...
        click(fig(1, 1))                         # ...onto the Slinger
        click(badge(1, 1))                       # the Slinger's stance
        click(fig(1, 0))                         # a swap: the Axeman...
        click(fig(0, 2))                         # ...and an empty rear cell
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


def main():
    off = offsets()
    for mach in (sys.argv[1:] or ("os8088_5150_herc_gla", "os8088_5150_cga_gla")):
        run(mach, off)
    print("tithegame: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
