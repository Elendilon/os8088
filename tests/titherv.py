#!/usr/bin/env python3
"""TITHE's REVEAL: does a played card land in its cell and leave nothing behind?

SPEC.md 97.4.11. `V` plays a card: a trail of XOR sparks from the card to the
cell, the character dissolving in over its column's ground, and the card
dissolving out of the hand. XOR is its own erase only if the order holds -
sparks off first in a frame, on last - so the thing to prove is not that it
animates (look at it) but that it ENDS where it should, on all three adapters.

WHAT IT ASSERTS, and each one went red on purpose first:

  1. THE CARD WENT WHERE THE KEY SAYS: the first card in the hand (nothing is
     hovered) into lane 0 of P1's column for the toggle's row, and the cell
     table names it there.

  2. THE CELL IS THE NEW CHARACTER, TO THE BYTE: its four idle poses and four
     attack frames are the model's for the card that now stands there - so
     the one-cell composition a reveal does is the same composition a whole
     board does.

  3. THE CARD'S SLOT IS EMPTY on the glass: every pixel of its row dark.

  4. NOTHING IS LEFT ON THE BOARD OR THE HAND: with the wheel paused, the
     glass the reveal left is the glass a whole repaint draws - a spark the
     erase missed, a dissolve that stopped short of whole, numbers that never
     arrived, all differ here.

  5. NOTHING IS LEFT IN THE GAP between the board and the hand, which no
     repaint of the package's own redraws: it is the glass it was before the
     key, bar P2's base, which animates on a clock of its own.

    make && make tithedisk && python3 tests/titherv.py
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
import os88tithebg as bg                                  # noqa: E402
import titheterr as te                                    # noqa: E402

SYMS = te.SYMS + ("ti_rv", "ti_rvcell", "ti_rvcard", "ti_played", "ti_cellcard",
                  "ti_hover", "ti_row", "ti_boardw", "ti_panx", "ti_b2x",
                  "ti_basew", "ti_cardx", "ti_cardw", "ti_cardh",
                  "ti_cardpitch", "ti_nframe")
EQUS = te.EQUS

fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    """Assembled from the SOURCE, as tests/titheterr.py's are."""
    src = open(os.path.join(ROOT, "apps/tithe/tithe.asm"), encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "titherv-off.asm")
    out = os.path.join(ROOT, "build", "titherv-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp], cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def dump(stem, a, b, diff):
    """TITHERV_DUMP=<stem>: the two pictures a failed compare had, and the
    box the difference is in - for looking, not for asserting."""
    from PIL import Image
    xs = [d[0] for d in diff]
    ys = [d[1] for d in diff]
    x0, y0, x1, y1 = min(xs) - 20, min(ys) - 20, max(xs) + 20, max(ys) + 20
    for tag, px in (("glass", a), ("repaint", b)):
        im = Image.new("L", (x1 - x0, y1 - y0))
        im.putdata([255 if px[y][x] else 0
                    for y in range(y0, y1) for x in range(x0, x1)])
        im.resize(((x1 - x0) * 3, (y1 - y0) * 3)).save(
            "%s-%s.png" % (stem, tag))
    print("       dumped %s-*.png, box %d,%d-%d,%d" % (stem, x0, y0, x1, y1))


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
        os88marty.guest_sleep(m, 8.0)

        def rw(name):
            return struct.unpack("<H", bytes(m.readseg(seg, off[name], 2)))[0]

        def rb(name, i=0):
            return m.readseg(seg, off[name] + i, 1)[0]

        g = {s: (off[s] if s in EQUS else rw(s)) for s in SYMS}
        geo = bg.GEO[g["ti_gidx"]]
        rows = g["TI_ROWS"]
        hover = g["ti_hover"]
        card = hover if hover != 0xFFFF else 0
        col = 1 if g["ti_row"] == 0 else 0
        cell = col * rows                        # the first reveal takes lane 0
        print("       %s: card %d into cell %d (column %d)"
              % (geo[0], card, cell, col))

        w, h, before = te.mono(m)
        n0 = rw("ti_nframe")
        m.key("KeyV")
        # THE FRAME COUNT AND NOT THE FLAGS: the guest is read RUNNING, and
        # the key handler sets the played bit before it sets ti_rv - so a poll
        # can land between the two, see "played and not revealing", and press
        # the next key into the reveal, which ignores keys by design
        os88marty.until(
            m, lambda _: (rw("ti_nframe") - n0) & 0xFFFF > 12
            and rb("ti_rv") == 0, "the reveal to finish", poll=0.2)
        os88marty.guest_sleep(m, 0.5)
        m.key("KeyP")                            # the wheel holds still
        os88marty.guest_sleep(m, 0.5)
        w, h, after = te.mono(m)

        # 1. the card went where the key says
        check(rw("ti_rvcell") == cell and rw("ti_rvcard") == card
              and rb("ti_cellcard", cell) == card,
              "card %d is in cell %d, and the cell table says so" % (card, cell),
              "rvcell %d rvcard %d table %d" % (rw("ti_rvcell"), rw("ti_rvcard"),
                                                rb("ti_cellcard", cell)))

        # 2. the cell's eight frames are the new character's
        strip = bg.strip(geo, g["ti_terr"], col)
        bad = []
        for pi in range(4):
            for seg_, attack in ((g["ti_aseg"], False), (g["ti_kseg"], True)):
                got = bytes(m.readseg(seg_, (cell * 4 + pi) * g["ti_cslot"],
                                      g["ti_cslot"]))
                want = te.model_pose(geo, g["ti_terr"], strip, g, cell, pi,
                                     attack, card=card)
                if got != want:
                    bad.append("%s %d" % ("attack" if attack else "pose", pi))
        check(not bad, "the cell's eight frames are the new character's, to "
              "the byte", bad)

        # 3. the card's slot is empty
        cy = g["ti_by"] + card * g["ti_cardpitch"]
        lit = sum(1 for y in range(cy, cy + g["ti_cardh"])
                  for x in range(g["ti_cardx"], g["ti_cardx"] + g["ti_cardw"])
                  if after[y][x])
        check(lit == 0, "the card's slot in the hand is empty", "%d lit" % lit)

        # 4. the board and the hand are what a whole repaint draws
        m.key("KeyD")                            # D twice: Flat, Banded, Flat -
        os88marty.guest_sleep(m, 2.0)            # each one ti_paint_now
        m.key("KeyD")
        os88marty.guest_sleep(m, 2.0)
        w, h, repaint = te.mono(m)
        x0, x1 = max(0, win.x), min(w, win.x + win.w)
        y1 = min(h, win.y + win.h)
        diff = [(x, y) for y in range(g["ti_by"], y1) for x in range(x0, x1)
                if after[y][x] != repaint[y][x]]
        if diff and os.environ.get("TITHERV_DUMP"):
            dump(os.environ["TITHERV_DUMP"] + "-" + mach, after, repaint, diff)
        check(not diff, "the board and the hand are exactly a whole repaint",
              "%d px, first %s" % (len(diff), diff[:4]))

        # 5. the gap between them is what it was before the key
        gx0 = g["ti_bx"] + g["ti_boardw"]
        base = range(g["ti_b2x"], g["ti_b2x"] + g["ti_basew"])
        gap = [(x, y) for y in range(g["ti_by"], y1)
               for x in range(gx0, g["ti_panx"])
               if x not in base and before[y][x] != after[y][x]]
        check(not gap, "the gap between the board and the hand is as it was",
              "%d px, first %s" % (len(gap), gap[:4]))


def main():
    off = offsets()
    for mach in (sys.argv[1:] or te.MACHINES):
        run(mach, off)
    print("titherv: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
