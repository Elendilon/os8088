#!/usr/bin/env python3
"""TITHE's FULLSCREEN HAND: seven portrait cards along the bottom (SPEC.md 97.4.12).

On VGA and Hercules fullscreen the hand leaves the strip down the right and
becomes a row of portrait cards under a centred board, in the tall face, with
the character at the board's own size. What can go wrong is a picture that
looks right once and is not the picture the package would draw again - so most
of what this asserts is a comparison against a WHOLE REPAINT (`ti_rpq`), taken
after each thing that draws part of the hand on its own.

WHAT IT ASSERTS, and each one went red on purpose first:

  1. THE LAYOUT IS TAKEN, AND ONLY WHERE IT SHOULD BE: `ti_horiz` on VGA and
     Hercules fullscreen, off on CGA fullscreen (whose pixels would make a
     portrait read as a letterbox), off windowed. And the geometry is sane:
     seven bands side by side with a byte of ground between them, the COMMIT
     column after the seventh, the hand under the board and inside the screen.

  2. A HOVERED CARD RISES. The top TI_HLIFT rows of a card's band are ground
     for a resting card and the hovered card's own frame when it is hovered.

  3. THE HOVERED CARD ANIMATES AND LEAVES THE CARD WHOLE. Its figure is
     redrawn on the wheel by `ti_pic_anim` (the figure's rows, the uprights
     through them), and paused mid-cycle the glass is exactly a whole repaint.

  4. A CLICKED CARD IS PLAYED FROM THE BOTTOM ROW: the reveal runs, the card's
     band ends dark, and the glass is exactly a whole repaint.

  5. LEAVING FULLSCREEN PUTS THE STRIP BACK.

    make && make tithedisk && python3 tests/tithefs.py
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
import titheterr as te                                    # noqa: E402

SYMS = ("ti_horiz", "ti_hy", "ti_cardh", "ti_cardw", "ti_cardpitch",
        "ti_panx", "ti_cmx", "ti_cmw", "ti_cbrows", "ti_by", "ti_boardh",
        "ti_ox", "ti_oy", "ti_cw_box", "ti_ch_box", "ti_nlay", "ti_rpq",
        "ti_hover", "ti_rv", "ti_nframe", "ti_rvcard", "ti_played",
        "ti_cardn", "TI_HLIFT", "tg_fillq")
EQUS = ("TI_HLIFT",)
MACHINES = ("os8088_xt_vga", "os8088_5150_herc_gla", "os8088_5150_cga_gla")

fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    """Assembled from the SOURCE, as tests/titheterr.py's are."""
    src = open(os.path.join(ROOT, "apps/tithe/tithe.asm"), encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "tithefs-off.asm")
    out = os.path.join(ROOT, "build", "tithefs-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp], cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def run(mach, off):
    print("  --- %s" % mach)
    cga = "cga" in mach
    with os88ui.boot("build/os8088-360.img", apps="build/tithe360.img",
                     machine=mach) as ui:
        m = ui.m
        ui.path("B:/TITHE.O88")
        win = [w for w in os88geom.windows(m) if w.title == "Tithe"][0]
        seg = struct.unpack(
            "<H", bytes(m.read(os88geom.winptr(m, win) + os88geom.W_SEG, 2)))[0]
        ui.raise_window(win)
        os88marty.guest_sleep(m, 6.0)
        te.fill(m, seg, off, mode=2)     # seven cards, and room to play one

        def rw(name):
            return struct.unpack("<H", bytes(m.readseg(seg, off[name], 2)))[0]

        def rb(name):
            return m.readseg(seg, off[name], 1)[0]

        def relayout(key):
            n0 = rw("ti_nlay")
            m.key(key)
            os88marty.until(m, lambda _: rw("ti_nlay") != n0,
                            "the relayout %s asks for" % key, poll=0.3,
                            limit=90.0)
            # ...AND THE WHEEL RUNNING AGAIN, not a fixed wait: the relayout
            # composes every pose and portrait before the paint, which on an
            # 8088 is seconds, and a read inside it sees the hand undrawn
            f0 = rw("ti_nframe")
            os88marty.until(m, lambda _: (rw("ti_nframe") - f0) & 0xFFFF > 10,
                            "the wheel after the relayout", poll=0.3,
                            limit=90.0)

        def repaint():
            m.write(seg * 16 + off["ti_rpq"], b"\x01")
            os88marty.until(m, lambda _: rb("ti_rpq") == 0,
                            "the requested repaint", poll=0.1)
            os88marty.guest_sleep(m, 0.3)

        def diff(a, b, box):
            x0, y0, x1, y1 = box
            return [(x, y) for y in range(y0, y1) for x in range(x0, x1)
                    if a[y][x] != b[y][x]]

        check(rb("ti_horiz") == 0, "windowed, the hand is the strip",
              "%d" % rb("ti_horiz"))
        relayout("KeyF")
        horiz = rb("ti_horiz")
        if cga:
            check(horiz == 0, "CGA fullscreen keeps the strip", "%d" % horiz)
            relayout("KeyF")
            return
        check(horiz == 1, "fullscreen, the hand is along the bottom",
              "%d" % horiz)
        if not horiz:
            return
        g = {s: (off[s] if s in EQUS else rw(s)) for s in SYMS}
        lift = g["TI_HLIFT"]
        w, h, px = te.mono(m)
        # 1. the geometry
        bands = [(g["ti_panx"] + i * g["ti_cardpitch"], g["ti_cardw"])
                 for i in range(7)]
        ok = (g["ti_cardn"] == 7
              and all(x % 8 == 0 and cw % 8 == 0 for x, cw in bands)
              and all(bands[i][0] + bands[i][1] + 8 <= bands[i + 1][0]
                      for i in range(6))
              and bands[6][0] + bands[6][1] <= g["ti_cmx"]
              and g["ti_cmx"] + g["ti_cmw"] <= g["ti_ox"] + g["ti_cw_box"]
              and g["ti_hy"] >= g["ti_by"] + g["ti_boardh"]
              and g["ti_hy"] + g["ti_cbrows"] <= g["ti_oy"] + g["ti_ch_box"]
              and g["ti_cbrows"] == g["ti_cardh"] + lift)
        check(ok, "seven aligned bands a byte apart, COMMIT after them, "
              "under the board and on the screen",
              "bands %s cmx %d cmw %d hy %d rows %d by %d boardh %d"
              % (bands, g["ti_cmx"], g["ti_cmw"], g["ti_hy"],
                 g["ti_cbrows"], g["ti_by"], g["ti_boardh"]))
        check(g["ti_cardh"] > g["ti_cardw"] * (0.6 if "herc" in mach else 1.0),
              "the cards are portraits on the glass",
              "%d x %d" % (g["ti_cardw"], g["ti_cardh"]))
        # ...and every resting card is DRAWN: its paper is white
        hy = g["ti_hy"]
        drawn = [sum(1 for x in range(bx + 2, bx + cw - 2)
                     if px[hy + lift + g["ti_cardh"] // 2][x])
                 for bx, cw in bands]
        check(all(d > 10 for d in drawn), "every card is on the glass",
              "%s" % drawn)
        # 2. a hovered card rises
        mo = os88mouse.Mouse(marty=m)
        park = (g["ti_ox"] + 4, g["ti_oy"] + 4)
        k = 2
        bx, cw = bands[k]
        mo.to(bx + cw // 2, hy + g["ti_cbrows"] // 2)
        os88marty.until(m, lambda _: rw("ti_hover") == k, "the hover",
                        poll=0.2, limit=20.0)
        os88marty.guest_sleep(m, 2.0)
        w, h, px = te.mono(m)
        risen = sum(1 for x in range(bx, bx + cw) if px[hy][x])
        rest = sum(1 for i, (x0, c) in enumerate(bands) if i != k
                   for x in range(x0, x0 + c) for y in range(hy, hy + lift)
                   if px[y][x])
        check(risen > cw // 2 and rest == 0,
              "the hovered card has risen and the others have not",
              "risen %d of %d, lit above the rest %d" % (risen, cw, rest))
        # 3. it animates, and a pause mid-cycle is exactly a repaint
        n0 = rw("ti_nframe")
        os88marty.until(m, lambda _: (rw("ti_nframe") - n0) & 0xFFFF > 20,
                        "frames", poll=0.2)
        m.key("KeyP")
        os88marty.guest_sleep(m, 0.5)
        _, _, a = te.mono(m)
        repaint()
        _, _, b = te.mono(m)
        box = (g["ti_ox"], hy, g["ti_ox"] + g["ti_cw_box"],
               hy + g["ti_cbrows"])
        d = diff(a, b, box)
        check(not d, "hovered and animating, the hand is exactly a repaint",
              "%d px, first %s" % (len(d), d[:4]))
        m.key("KeyP")
        os88marty.guest_sleep(m, 1.0)
        # 4. a click plays it
        n0 = rw("ti_nframe")
        mo.click(bx + cw // 2, hy + g["ti_cbrows"] // 2, settle=0.2)
        os88marty.until(
            m, lambda _: (rw("ti_nframe") - n0) & 0xFFFF > 12
            and rb("ti_rv") == 0, "the reveal to finish", poll=0.2)
        mo.to(*park)
        os88marty.guest_sleep(m, 1.0)
        check(rw("ti_rvcard") == k and rb("ti_played") & (1 << k),
              "the clicked card is the one played",
              "rvcard %d played %02x" % (rw("ti_rvcard"), rb("ti_played")))
        m.key("KeyP")
        os88marty.guest_sleep(m, 0.5)
        _, _, a = te.mono(m)
        lit = sum(1 for y in range(hy, hy + g["ti_cbrows"])
                  for x in range(bx, bx + cw) if a[y][x])
        check(lit == 0, "...and its band is dark", "%d lit" % lit)
        repaint()
        _, _, b = te.mono(m)
        full = (g["ti_ox"], g["ti_by"], g["ti_ox"] + g["ti_cw_box"],
                g["ti_oy"] + g["ti_ch_box"])
        d = diff(a, b, full)
        check(not d, "...and the board and the hand are exactly a repaint",
              "%d px, first %s" % (len(d), d[:4]))
        m.key("KeyP")
        # 5. and back
        relayout("KeyF")
        check(rb("ti_horiz") == 0, "leaving fullscreen puts the strip back",
              "%d" % rb("ti_horiz"))


def main():
    off = offsets()
    for mach in (sys.argv[1:] or MACHINES):
        run(mach, off)
    print("tithefs: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
