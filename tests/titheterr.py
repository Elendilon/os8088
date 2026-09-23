#!/usr/bin/env python3
"""TITHE's BOARD: is it the PLACE the model says, strip for strip and cell for cell?

SPEC.md 97.4.10 and 97.4.9. The board is a location - a sparse texture per
COLUMN, a fence between the LANES on the shear's own slope, a wall along the
back and a cliff under the front - composed at round load into four column
strips in a heap claim, and every cell's four idle poses and four attack frames
are cut from its column's strip with the card's BODY and its column's ITEM
(front in columns 1 and 2, rear in 0 and 3) MASKED over them. tools/os88tithebg.py and
tools/os88tithechar.py are the model of both, and this row holds the machine to
the model EXACTLY. Nothing here is a tolerance.

WHAT IT ASSERTS, and each one went red on purpose first:

  1. EVERY STRIP IS THE MODEL'S, TO THE BYTE, on all three adapters and both
     terrains. A strip is a function of (surface, terrain, column) and nothing
     else, so the arena's bytes and the host's are the same bytes or one of
     them is wrong. A fence walked one row off, a pattern read from the wrong
     byte of its word, a gap between fences mis-sized - each is a handful of
     pixels in a busy picture and a failed compare here.

  2. EVERY CELL'S POSES ARE THE MODEL'S, TO THE BYTE: the strip's rows under
     the band, and the figure masked over them - MIRRORED in P2's two
     columns, whose band sits CW - INSX - BW in so the figure stands against
     the numbers on its right. The ATTACK frames are held the same
     way, out of the second claim, with the strike's lunge inside the band.
     That is the whole of what the pixel art is for - a black detail line kept black over a lit ground - and
     an ORed figure (the old composition) or a mask applied the wrong way
     round fails it at the first figure with a visor.

  3. THE STRIPS REACHED THE GLASS: under the front lane, where no figure and
     no number is ever drawn, each column's lip and cliff on screen are the
     model's - at four heights one RISE apart, which is the shear. A strip
     blitted at the wrong y, or not at all, fails here and nowhere else.

  4. G CYCLES AND COMES BACK: the second terrain is the model's second
     terrain, and two presses are the first board again, to the bit.

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
import os88tithebg as bg                                  # noqa: E402
import os88tithechar as tc                                # noqa: E402

# The words are READ from the guest; the names in EQUS are the assembler's own
# values and are used straight out of the table - `dw TI_COLS` emits 4, and
# reading guest memory at offset 4 is how a check once came back with an empty
# list and passed on `all([])`.
SYMS = ("ti_terr", "ti_gidx", "ti_aseg", "ti_kseg", "ti_bx", "ti_by", "ti_cw", "ti_ch",
        "ti_rise", "ti_boardh", "ti_sb", "ti_sh", "ti_spitch", "ti_sbase",
        "ti_cslot", "ti_bs", "ti_bh", "ti_insx", "ti_insy", "ti_arm",
        "TI_COLS", "TI_ROWS")
EQUS = ("TI_COLS", "TI_ROWS")
MACHINES = ("os8088_xt_vga", "os8088_5150_herc_gla", "os8088_5150_cga_gla")
HAND = 7                          # a cell plays card (index mod the hand)

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


def pack(rows):
    out = bytearray()
    for r in rows:
        for b in range(0, len(r), 8):
            v = 0
            for i in range(8):
                if b + i < len(r) and r[b + i]:
                    v |= 0x80 >> i
            out.append(v)
    return bytes(out)


def model_pose(geo, terr, strip, g, ci, pi, attack=False):
    """A cell's composed pose - or attack frame - as the machine should have
    it: the card's body, the item for its column (FRONT in 1 and 2, REAR in 0
    and 3), over the column's own ground."""
    c, r = divmod(ci, g["TI_ROWS"])
    x0 = g["ti_insx"]
    rows = []
    stance = tc.FRONT if c in (1, 2) else tc.REAR
    fig = tc.compose(ci % HAND, stance,
                     [s for s in tc.SURFACES if s[0] == geo[0]][0], pi, attack)
    if c >= g["TI_COLS"] // 2:          # P2: the band MIRRORED, at CW-INSX-BW
        x0 = g["ti_cw"] - g["ti_insx"] - g["ti_bs"] * 8
        fig = [row[::-1] for row in fig]
    for by in range(g["ti_bh"]):
        gr = strip[r * g["ti_ch"] + g["ti_insy"] + by][x0:x0 + g["ti_bs"] * 8]
        row = []
        for bx in range(g["ti_bs"] * 8):
            v = fig[by][bx]
            row.append(gr[bx] if v == tc.T else (1 if v == tc.I else 0))
        rows.append(row)
    return pack(rows)


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

        def state():
            return {s: (off[s] if s in EQUS else rw(s)) for s in SYMS}

        g = state()
        if g["ti_sh"] == 0 or g["ti_aseg"] == 0:
            check(False, "%s: the window holds a board at all" % mach, g)
            return
        geo = bg.GEO[g["ti_gidx"]]
        print("       %s, terrain %d, arena %04x, strip %dx%d, slot %d"
              % (geo[0], g["ti_terr"], g["ti_aseg"], g["ti_sb"], g["ti_sh"],
                 g["ti_cslot"]))

        def arena(o, n):
            return bytes(m.readseg(g["ti_aseg"], o, n))

        def strips_ok(terr):
            bad = []
            models = []
            for c in range(g["TI_COLS"]):
                s = bg.strip(geo, terr, c)
                models.append(s)
                got = arena(g["ti_sbase"] + c * g["ti_spitch"], g["ti_spitch"])
                want = pack(s)
                if got != want:
                    n = sum(bin(a ^ b).count("1") for a, b in zip(got, want))
                    first = next(i for i in range(len(want)) if got[i] != want[i])
                    bad.append("col %d: %d bits differ, first at row %d"
                               % (c, n, first // g["ti_sb"]))
            return bad, models

        bad, models = strips_ok(g["ti_terr"])
        check(not bad, "the four strips are the model's, to the byte", bad)

        # 2. every cell, every pose (the sprite arm must be the table's)
        if g["ti_arm"] == 2:
            badc = []
            for ci in range(g["TI_COLS"] * g["TI_ROWS"]):
                for pi in range(4):
                    got = arena((ci * 4 + pi) * g["ti_cslot"], g["ti_cslot"])
                    want = model_pose(geo, g["ti_terr"],
                                      models[ci // g["TI_ROWS"]], g, ci, pi)
                    if got != want:
                        badc.append("cell %d pose %d" % (ci, pi))
            check(not badc, "all eighty poses are ground + body + item, "
                  "to the byte", badc[:6])
            bada = []
            for ci in range(g["TI_COLS"] * g["TI_ROWS"]):
                for pi in range(4):
                    got = bytes(m.readseg(g["ti_kseg"],
                                          (ci * 4 + pi) * g["ti_cslot"],
                                          g["ti_cslot"]))
                    want = model_pose(geo, g["ti_terr"],
                                      models[ci // g["TI_ROWS"]], g, ci, pi,
                                      attack=True)
                    if got != want:
                        bada.append("cell %d frame %d" % (ci, pi))
            check(not bada, "...and all eighty ATTACK frames, the strike's "
                  "lunge inside the band", bada[:6])

        # 3. the glass, under the front lane where nothing else is drawn
        w, h, px = mono(m)
        badg = []
        for c in range(g["TI_COLS"]):
            x0 = g["ti_bx"] + c * g["ti_cw"]
            y0 = g["ti_by"] + (g["TI_COLS"] - 1 - c) * g["ti_rise"]
            for ly in range(g["TI_ROWS"] * g["ti_ch"], g["ti_sh"]):
                row = [int(px[y0 + ly][x0 + x]) for x in range(g["ti_cw"])]
                if row != models[c][ly]:
                    badg.append("col %d row %d" % (c, ly))
                    break
        check(not badg, "every column's lip and cliff are on the glass, a "
              "RISE apart", badg)

        # 4. G, and G again
        t0 = g["ti_terr"]
        m.key("KeyG")
        os88marty.guest_sleep(m, 8.0)
        g = state()
        check(g["ti_terr"] != t0, "G moves to the next terrain",
              "%d -> %d" % (t0, g["ti_terr"]))
        bad, _ = strips_ok(g["ti_terr"])
        check(not bad, "...and its strips are THAT terrain's model", bad)
        m.key("KeyG")
        os88marty.guest_sleep(m, 8.0)
        g = state()
        bad, _ = strips_ok(t0)
        check(g["ti_terr"] == t0 and not bad,
              "G comes back to the first board, to the bit",
              "terr %d, %s" % (g["ti_terr"], bad))


def main():
    off = offsets()
    for mach in (sys.argv[1:] or MACHINES):
        run(mach, off)
    print("titheterr: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
