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
        "ti_cslot", "ti_bs", "ti_bh", "ti_insx", "ti_insy",
        "TI_COLS", "TI_ROWS", "tg_fillq", "ti_cards", "TI_C_SIZE",
        "TI_C_FLAGS", "TI_HAND")
EQUS = ("TI_COLS", "TI_ROWS", "ti_cards", "TI_C_SIZE", "TI_C_FLAGS", "TI_HAND")
MACHINES = ("os8088_xt_vga", "os8088_5150_herc_gla", "os8088_5150_cga_gla")

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


def marks():
    """THE STANCE MARKS (SPEC.md 97.12.10.1), read out of the SOURCE rather
    than restated: tiplace.inc's `ti_mk_*` figures, `db wb, rows` and then an
    (ink, mask) pair a byte - as rows of 'I' (ink), 'M' (black halo) and '.'."""
    src = open(os.path.join(ROOT, "apps/tithe/tiplace.inc"),
               encoding="utf-8").read().splitlines()
    out = {}
    for i, line in enumerate(src):
        if not line.startswith("ti_mk_") or not line.rstrip().endswith(":") \
                or line.startswith("ti_mk_tab"):
            continue
        name = line.strip()[len("ti_mk_"):-1]
        vals = []
        j = i + 1
        while j < len(src) and src[j].strip().startswith("db "):
            vals += [int(v.strip().rstrip("h"), 16) if v.strip().endswith("h")
                     else int(v) for v in src[j].strip()[3:].split(",")]
            j += 1
        wb, h = vals[0], vals[1]
        rows = []
        for y in range(h):
            row = ""
            for b in range(wb):
                ink, msk = vals[2 + (y * wb + b) * 2], vals[3 + (y * wb + b) * 2]
                for k in range(8):
                    bit = 0x80 >> k
                    row += "I" if ink & bit else ("M" if msk & bit else ".")
            rows.append(row)
        out[name] = rows
    return out


MARKS = marks()


def cell_flags(m, seg, g, ci):
    """Cell ci's view flags - TI_CF_RANGED (1), TI_CF_SNIPE (2) - off the guest."""
    return m.readseg(seg, g["ti_cards"] + (g["TI_HAND"] + ci) * g["TI_C_SIZE"]
                     + g["TI_C_FLAGS"], 1)[0]


def model_pose(geo, terr, strip, g, ci, pi, attack=False, card=None, flags=0):
    """A cell's composed pose - or attack frame - as the machine should have
    it: the card's body, the item for its column (FRONT in 1 and 2, REAR in 0
    and 3), over the column's own ground - and under it, a shooter's STANCE
    MARK (`flags`, the view's TI_CF_*). `card` is the ART that stands there -
    art N in cell N on the tests' full board (fill), until a reveal
    (tests/titherv.py) puts one there."""
    c, r = divmod(ci, g["TI_ROWS"])
    x0 = g["ti_insx"]
    rows = []
    stance = tc.FRONT if c in (1, 2) else tc.REAR
    fig = tc.compose(ci if card is None else card, stance,
                     [s for s in tc.SURFACES if s[0] == geo[0]][0], pi, attack)
    bw = g["ti_bs"] * 8
    mark = [["."] * bw for _ in range(g["ti_bh"])]
    if flags & 1:
        mk = MARKS[("short_" if geo[0] == "cga" else "tall_")
                   + ("snipe" if flags & 2 else "front")]
        mx = (bw - len(mk[0])) // 16 * 8
        my = g["ti_bh"] - len(mk)
        for y, mrow in enumerate(mk):
            for x, v in enumerate(mrow):
                if 0 <= mx + x < bw:
                    mark[my + y][mx + x] = v
    if c >= g["TI_COLS"] // 2:          # P2: the band MIRRORED, at CW-INSX-BW
        x0 = g["ti_cw"] - g["ti_insx"] - g["ti_bs"] * 8
        fig = [row[::-1] for row in fig]
        mark = [row[::-1] for row in mark]
    for by in range(g["ti_bh"]):
        gr = strip[r * g["ti_ch"] + g["ti_insy"] + by][x0:x0 + g["ti_bs"] * 8]
        row = []
        for bx in range(g["ti_bs"] * 8):
            v = fig[by][bx]
            under = {"I": 1, "M": 0}.get(mark[by][bx], gr[bx])
            row.append(under if v == tc.T else (1 if v == tc.I else 0))
        rows.append(row)
    return pack(rows)


def fill(m, seg, off, mode=1):
    """THE TESTS' FULL BOARD (SPEC.md 97.12.6). A match starts empty, and
    every check here is about twenty figures: `tg_fillq` is a byte the worker
    services, standing the first card of art N in cell N and seven of them in
    each hand. Mode 2 leaves P1's FRONT column empty for a row that plays."""
    m.write(seg * 16 + off["tg_fillq"], bytes([mode]))
    os88marty.until(m, lambda _: m.readseg(seg, off["tg_fillq"], 1)[0] == 0,
                    "the full board", poll=0.2, limit=60.0)
    os88marty.guest_sleep(m, 1.0)


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

        fill(m, seg, off)

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

        # 2. every cell, every pose
        badc = []
        for ci in range(g["TI_COLS"] * g["TI_ROWS"]):
            for pi in range(4):
                got = arena((ci * 4 + pi) * g["ti_cslot"], g["ti_cslot"])
                want = model_pose(geo, g["ti_terr"],
                                  models[ci // g["TI_ROWS"]], g, ci, pi,
                                  flags=cell_flags(m, seg, g, ci))
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
                                  attack=True, flags=cell_flags(m, seg, g, ci))
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
