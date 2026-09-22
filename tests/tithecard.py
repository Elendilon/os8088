#!/usr/bin/env python3
"""TITHE's card composer: does the card stay INSIDE its own frame?

SPEC.md 97.4.1's gate. The panel is one `OSAPI_GFX_BLIT1` a card now - a band
composed by the package, in the package's OWN face - and the two defects that
cost a screenshot round each are both a line crossing a boundary:

  1. A ROW THAT DOES NOT FIT IS NOT DRAWN. The flow's bottom test was off by
     one row, so a VGA card started a fourth line of text and the card's foot
     cut it in half. The frame's bottom line is what it cut through, so the
     assertion is that the frame's four lines are UNBROKEN.

  2. THE FIGURE OWNS A COLUMN. Before the flow had a right margin the stat
     row ran under the mini unit and off the card's right-hand edge - into
     the pad byte, which the blit then carried onto the screen. The right
     upright is what that breaks, and the same four-line check catches it.

  3. NOTHING LEAVES THE BAND. A one-pixel ring outside each card must stay
     clear: the band is padded by a byte so `ti_glyph` can shift a glyph
     across a byte pair, and a blit told the wrong width puts that pad on the
     glass.

  4. THE FACE KEY CHANGES THE CARD. `T` cycles the faces and the whole point
     of the second one is that a 6x6 fits FOUR rows where 8x8 fits three -
     so `ti_crows` must go UP, and the panel's pixels must actually differ.
     A face table that is emitted but never rebuilt into the package reads
     exactly like a glyph change that did nothing, which is what happened:
     the Makefile had no dependency on tifaces.inc.

Every check runs on all three adapters, because the card's height is a
geometry-table field and the flow's answer differs on each.
"""
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SYMS = ("ti_cardx", "ti_cardw", "ti_cardh", "ti_cardpitch", "ti_cardn",
        "ti_by", "ti_crows", "ti_face", "ti_cpad", "TI_FACES", "TI_UNITW")
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
    tmp = os.path.join(ROOT, "build", "tithecard-off.asm")
    out = os.path.join(ROOT, "build", "tithecard-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp], cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def mono(m):
    """The screen as rows of booleans - lit or not.

    ON 1bpp IT IS THE GUEST'S OWN FRAMEBUFFER and not the rendered frame.
    `fbuf` asks the CARD what it rasterised, and MartyPC's Hercules raster
    carries two rows of overscan above the picture - so every rect read two
    pixels low there and the card's own frame line looked broken. `vram` is
    the byte-exact route on both 1bpp adapters (and is what the assertion is
    really about: did the kernel put these bits at this address). VGA has no
    flat framebuffer to read at all - mode 12h is four planes behind the
    Graphics Controller - so it stays on `fbuf`, where the origin is exact.
    """
    if m.cmd(cmd="video")["type"] in ("cga", "herc", "mda"):
        w, h, rows = m.vram()
        return w, h, [[bool(b) for b in r] for r in rows]
    w, h, d = m.fbuf()
    return w, h, [[d[(y * w + x) * 3] > 127 for x in range(w)] for y in range(h)]


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
        os88marty.guest_sleep(m, 4.0)
        rw = lambda n: struct.unpack("<H", bytes(m.readseg(seg, off[n], 2)))[0]

        rows_seen, panels = [], []
        for face in range(off["TI_FACES"]):
            if face:
                m.key("KeyT")
                os88marty.guest_sleep(m, 2.5)
            name = "face %d" % rw("ti_face")
            rows_seen.append(rw("ti_crows"))
            w, h, px = mono(m)
            # THE PACKAGE'S COORDINATES ARE THE SCREEN'S. A kernel drawing
            # slot takes a screen x and y, so what the package banks is one
            # too - adding the window's content origin here put every rect a
            # whole HUD lower and read the desktop as a broken card. It is
            # the trap ti_basey carries its own note about, one file along.
            x, cw, ch = rw("ti_cardx"), rw("ti_cardw"), rw("ti_cardh")
            pitch, n, by = rw("ti_cardpitch"), rw("ti_cardn"), rw("ti_by")
            panels.append([r[x:x + cw] for r in px])

            broke, leaked = [], []
            for i in range(n):
                x0, x1 = x, x + cw - 1
                y0, y1 = by + i * pitch, by + i * pitch + ch - 1
                if y1 >= h or x1 + 1 >= w or x0 < 1:
                    continue
                # THE FRAME IS ASSERTED UNIFORM AND NOT LIT. A resting card is
                # the package's pen the other way round - black ink on white
                # paper (SPEC.md 5.4.2.2) - so its frame is the same colour as
                # the panel's ground and a "the frame is lit" test passes on
                # the hovered card and fails on the other six.
                ink = px[y0][x0]
                for xx in range(x0, x1 + 1):
                    if px[y0][xx] != ink:
                        broke.append((i, xx, "top"))
                    if px[y1][xx] != ink:
                        broke.append((i, xx, "foot"))
                for yy in range(y0, y1 + 1):
                    if px[yy][x0] != ink:
                        broke.append((i, yy, "left"))
                    if px[yy][x1] != ink:
                        broke.append((i, yy, "right"))
                # ...and the row inside each upright is PAPER: the flow's
                # margin starts at x=3 and the figure ends before the pad, so
                # a glyph in either column is one that ran past its line.
                for yy in range(y0 + 1, y1):
                    if px[yy][x0 + 1] == ink or px[yy][x1 - 1] == ink:
                        leaked.append((i, yy, "inside the upright"))
                # THE ROW ABOVE THE FOOT IS BLANK, which is how a PARTIAL row
                # is caught. The obvious assertion - that the foot's frame
                # line is unbroken - cannot see one: the band is composed by
                # OR, the frame is drawn first and is already set, so a glyph
                # landing on it changes no pixel at all. What a row too many
                # DOES leave is the top of a glyph in the rows just above the
                # foot, and the flow's grid puts nothing there: lines start at
                # 2+cpad and step by the face's height, so the last legal one
                # ends at cardh-3-cpad or higher.
                for xx in range(x0 + 1, x1):
                    if px[y1 - 1][xx] == ink:
                        leaked.append((i, xx, "a partial row above the foot"))
                # ...AND THE GUTTER TO THE FIGURE IS CLEAR, which is how the
                # other one is caught. Text running under the mini unit and
                # off the card is invisible to the upright check for the same
                # OR reason; what it cannot avoid is crossing the three
                # columns between the flow's right margin and the figure's
                # own, which nothing is ever drawn in.
                gut = x0 + cw - off["TI_UNITW"] - 11
                for yy in range(y0 + 1, y1):
                    for xx in range(gut, gut + 3):
                        if px[yy][xx] == ink:
                            leaked.append((i, yy, "in the figure's gutter"))
            check(not broke, "%s: every card's frame is unbroken" % name,
                  "%d break(s), first %s" % (len(broke), broke[:3]))
            check(not leaked, "%s: nothing is drawn outside the flow's grid" % name,
                  "%d pixel(s), first %s" % (len(leaked), leaked[:3]))

        check(rows_seen[1] > rows_seen[0],
              "the 6x6 face fits more rows than the 8x8",
              "%d vs %d" % (rows_seen[1], rows_seen[0]))
        diff = sum(1 for a, b in zip(panels[0], panels[1])
                   for p, q in zip(a, b) if p != q)
        check(diff > 200, "...and the panel is actually redrawn in it",
              "%d differing pixel(s)" % diff)


def main():
    off = offsets()
    for mach in MACHINES:
        run(mach, off)
    print("tithecard: %d check(s) FAILED" % len(fails) if fails else "tithecard: ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
