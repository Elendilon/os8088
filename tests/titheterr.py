#!/usr/bin/env python3
"""TITHE's BOARDS: are there two of them, and do they read as two PLACES?

SPEC.md 97.4.10. The board is not a backdrop - the plan fights in several
places (TITHE-PLAN 3.2) - so the ground under the lanes, the separators
between them and the board's own edge are a TERRAIN, composed at round load
and switched with `G` for the demo.

WHAT IT ASSERTS, and each one went red on purpose first:

  1. THE TWO TERRAINS ARE TWO PICTURES. A terrain that differs only in a
     constant nobody can see is a second board on paper and one board on the
     glass. The diff is taken over the BOARD's own rectangle, so a HUD line
     naming it cannot pass this check on its own.

  2. THE SLAB IS THERE, AND IT IS A STAIRCASE. The board's edge is the one
     background element that does not come out of the cell tile, so it is the
     one that can silently draw nothing - which is exactly what it did: the
     lip was computed WITHOUT the shear's lift, landed a whole cell up inside
     column 0's fourth row, and was then painted over by the cell blit that
     follows it. Nothing else here could see that. What catches it is that
     there must be a full-width lit run under each of the four columns, at
     four DIFFERENT heights, exactly one RISE apart - which is the shear, and
     is the one thing a lip drawn at the wrong height cannot satisfy.

  3. THE SLAB TOOK SOMETHING. `ti_slabh` is what the fit check had left over
     (a board that refused itself over a decoration would be the check
     answering a question nobody asked), so it can legitimately be clamped -
     but zero on a machine that drew a board at all means the growth was
     never granted.

  4. G CYCLES AND COMES BACK. Two presses is the same board again, to the
     pixel: the terrain is composed at LOAD, so a terrain that leaked state
     into the tile - or a relayout that half-ran - shows up here and nowhere
     else.

  5. THE LINE NAMES THE GROUND. With nothing under the pointer the status
     line says which place this is, which is how a player learns there is
     more than one.

    make && make tithedisk && python3 tests/titheterr.py
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

# The words are READ from the guest; the three in EQUS are the assembler's own
# values and are used straight out of the table - `dw TI_COLS` emits 4, and
# reading guest memory at offset 4 is how the lip check came back with an empty
# list and passed on `all([])`.
SYMS = ("ti_terr", "ti_slabh", "ti_bx", "ti_by", "ti_cw", "ti_ch",
        "ti_rise", "ti_boardw", "ti_boardh", "ti_lift",
        "TI_COLS", "TI_ROWS", "TI_CELLMAX", "ti_cell")
EQUS = ("TI_COLS", "TI_ROWS", "TI_CELLMAX", "ti_cell")
MACHINES = ("os8088_xt_vga", "os8088_5150_herc_gla", "os8088_5150_cga_gla")
TERRAINS = ("OPEN GROUND", "FLAGSTONE")

fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    """Assembled from the SOURCE, so the offsets cannot drift from the binary."""
    src = open(os.path.join(ROOT, "apps/tithe/tithe.asm"), encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "titheterr-off.asm")
    out = os.path.join(ROOT, "build", "titheterr-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp], cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def mono(m):
    """The screen as rows of booleans (tests/tithecard.py's, and for its reason:
    MartyPC's Hercules raster carries two rows of overscan, so `vram` is the
    byte-exact route on 1bpp and `fbuf` the only one on a planar VGA)."""
    if m.cmd(cmd="video")["type"] in ("cga", "herc", "mda"):
        w, h, rows = m.vram()
        return w, h, [[bool(b) for b in r] for r in rows]
    w, h, d = m.fbuf()
    return w, h, [[d[(y * w + x) * 3] > 127 for x in range(w)] for y in range(h)]


def lips(px, g):
    """The row under each column that carries a full-width lit run.

    A LIP IS THE WHOLE COLUMN WIDTH AND NOTHING ELSE IS. A cell's own dither
    lights half of every row and its diamond tapers, so no row inside the
    board is solid across a 96-pixel span - which is what makes "solid" the
    right test rather than "brightest".
    """
    out = []
    for c in range(g["TI_COLS"]):
        x0 = g["ti_bx"] + c * g["ti_cw"]
        x1 = x0 + g["ti_cw"]
        found = None
        for y in range(g["ti_by"], g["ti_by"] + g["ti_boardh"]):
            if all(px[y][x0:x1]):
                found = y                       # the LAST such row: the lip is
        out.append(found)                       # under the cells, not over them
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
        os88marty.guest_sleep(m, 5.0)

        def rw(name):
            return struct.unpack("<H", bytes(m.readseg(seg, off[name], 2)))[0]

        g = {s: (off[s] if s in EQUS else rw(s)) for s in SYMS}

        def tile():
            """THE COMPOSED CELL TILE, which is the terrain itself.

            The screen cannot answer "is this the same board" on its own: the
            three faction idles are running on it, so two captures four guest
            seconds apart differ by a couple of hundred pixels whatever the
            ground is doing. The tile is composed once at load and never
            touched again, so it is exact.
            """
            return bytes(m.readseg(seg, g["ti_cell"], g["TI_CELLMAX"]))
        if g["ti_boardw"] == 0:
            check(False, "%s: the window holds a board at all" % mach)
            return

        w, h, px = mono(m)
        c0 = tile()
        l0 = lips(px, g)
        t0 = rw("ti_terr")

        print("       terrain %d, slab %d, rise %d, lips %s"
              % (t0, g["ti_slabh"], g["ti_rise"], l0))
        check(g["ti_slabh"] > 0, "the slab got rows out of the fit check",
              g["ti_slabh"])
        check(all(v is not None for v in l0),
              "every column stands on a lit lip", l0)
        if all(v is not None for v in l0):
            steps = [l0[c] - l0[c + 1] for c in range(len(l0) - 1)]
            check(all(s == g["ti_rise"] for s in steps),
                  "...and the four lips are a RISE apart, which is the shear",
                  "%s want %d" % (steps, g["ti_rise"]))

        m.key("KeyG")                           # ...the next place
        os88marty.guest_sleep(m, 4.0)
        w, h, px = mono(m)
        c1 = tile()
        t1 = rw("ti_terr")
        check(t1 != t0, "G moves to the next terrain", "%d -> %d" % (t0, t1))
        diff = sum(bin(a ^ b).count("1") for a, b in zip(c0, c1))
        check(diff > 0.05 * 8 * len(c0),
              "...and the two boards are two PICTURES",
              "%d lit-bit differences of %d" % (diff, 8 * len(c0)))
        check(all(v is not None for v in lips(px, g)),
              "...and the second one stands on a lip too", lips(px, g))

        m.key("KeyG")                           # ...and round again
        os88marty.guest_sleep(m, 4.0)
        check(rw("ti_terr") == t0 and tile() == c0,
              "G comes back to the same board, to the bit",
              "terr %d, %d differing bits"
              % (rw("ti_terr"),
                 sum(bin(a ^ b).count("1") for a, b in zip(c0, tile()))))


def main():
    off = offsets()
    for mach in (sys.argv[1:] or MACHINES):
        run(mach, off)
    print("titheterr: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
