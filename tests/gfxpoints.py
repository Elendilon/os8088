#!/usr/bin/env python3
"""SPEC.md 5.6.9: gfx_points draws the SAME pixels as a gfx_pixel loop.

THE ONLY CLAIM WORTH GATING.  The slot exists to replace a per-point
OSAPI_GFX_PIXEL loop, so what has to be true is that it IS that loop - the same
pixels, under the same clip, with the same dither.  Anything weaker passes a
slot that plots at the wrong address, skips the wrong points, or draws through
a clip nobody set.

tests/ptstest draws one coordinate set TWICE into its window: band A through
OSAPI_GFX_POINTS and band B, PT_DY rows lower, one gfx_pixel a point.  This
reads the two bands off the framebuffer and requires them equal.  No golden
image and no reference build: the comparison is inside one frame.

Three cases, stacked down the window - a solid ink, a DITHER ink (the (x+y)
parity arm), and a solid ink with the window's own clip region ARMED.  The
third is SPEC.md 5.6.9.1's: gfx_ls_bx1..by2 still holds the box case 2 left at
case 2's y, and a slot that trusted it would draw outside the clip.

BREAK IT ON PURPOSE (docs/WRITING-TESTS.md 1) - all three were run:

  * draw every OTHER point:      cases 1, 2 and 3 all red.  RED.
  * drop the dither arm:         case 2 red, 1 and 3 green.  RED, and targeted.
  * remove the box invalidation
    (SPEC.md 5.6.9.1):           ALL THREE STAY GREEN.

THE THIRD ONE IS THE HONEST LIMIT OF THIS ROW, and it is written here rather
than discovered later.  The invalidation guards against a stale box that is too
BIG - the `.miss` arm re-resolves a box that is too small, so only an
over-large one draws through a clip nobody set.  That needs a call with the
region DISARMED (box = the whole screen) followed by one with it ARMED whose
points fall outside the armed region.  Every point here is inside the window's
content, so the stale box and the correct one give the same pixels.

Covering it wants a fourth case whose pattern reaches PAST the content's right
edge with the clip armed: band B goes through gfx_pixel and is clipped
properly, band A with a stale whole-screen box would draw the overflow, and the
two would differ.  It also wants a wider crop than PT_W to see the overflow.
Left undone deliberately - it is a separate shape, and a row that claims
coverage it has not got is worse than one that names the gap.

THE FIRST VERSION OF THIS ROW WAS A FALSE GREEN, twice over, which is why the
`lit` bound below is not decoration:

  * the ink was white on the window's white content, so both bands were solid
    and identical and all three cases passed on any kernel at all;
  * the pattern's second twelve points REPEATED the first twelve in reverse, so
    a kernel patched to draw every other point still drew every position.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))

import os88marty                                        # noqa: E402
import os88ui                                           # noqa: E402

SYS = "build/os8088-360.img"
APP = "build/ptstest360.img"

PT_DY   = 40        # all four must match tests/ptstest/ptstest.asm
PT_W    = 120
PT_H    = 18
PT_STEP = 60
CASES = ("solid ink", "dither ink", "solid ink, clip ARMED")


def band(rows, x0, y0, w, h):
    """`w` pixels of `h` rows, off m.vram's rows-of-bits."""
    return [tuple(rows[y][x0:x0 + w]) for y in range(y0, y0 + h)]


def main():
    machine = "os8088_5150_herc_gla"
    for i, a in enumerate(sys.argv[1:]):
        if a == "--machine":
            machine = sys.argv[i + 2]

    with os88ui.boot(SYS, apps=APP, machine=machine) as ui:
        m = ui.m
        w = ui.path("B:/PTSTEST.O88")
        ui.settle()

        # the content origin off the guest's OWN window record - a remembered
        # coordinate is what docs/WRITING-TESTS.md 1 is about
        w = ui.window("PtsTest")
        cx, cy = w.content[0], w.content[1]
        _, _, rows = m.vram()

        bad = 0
        for n, name in enumerate(CASES):
            x0 = cx + 8
            ya = cy + 4 + n * PT_STEP
            yb = ya + PT_DY
            A = band(rows, x0, ya, PT_W, PT_H)
            B = band(rows, x0, yb, PT_W, PT_H)
            lit = sum(1 for row in A for v in row if v)
            if A == B:
                print("  ok   case %d (%-22s) %4d lit pixels agree" % (n + 1, name, lit))
            else:
                bad += 1
                diff = sum(1 for ra, rb in zip(A, B)
                           for va, vb in zip(ra, rb) if va != vb)
                print("  FAIL case %d (%-22s) %4d lit, %d pixels differ"
                      % (n + 1, name, lit, diff))
                for r, (ra, rb) in enumerate(zip(A, B)):
                    if ra != rb:
                        cols = [c for c in range(PT_W) if ra[c] != rb[c]]
                        print("        row %2d: %d columns, first %r"
                              % (r, len(cols), cols[:8]))
            # A BAND THAT IS ALL GROUND OR ALL INK PROVES NOTHING, and the
            # first version of this row was green for exactly that reason: the
            # ink was white on the window's white content, so both bands were
            # solid and identical. The package lays a BLACK ground now, so a
            # real pattern is a small minority of lit pixels.
            if not (8 <= lit <= PT_W * PT_H // 4):
                bad += 1
                print("  FAIL case %d: %d lit of %d - that is not a PATTERN, so"
                      " equal bands prove nothing"
                      % (n + 1, lit, PT_W * PT_H))

        if bad:
            print("gfxpoints: %d of %d cases FAILED" % (bad, len(CASES)))
            return 1
        print("gfxpoints: %d cases, gfx_points == a gfx_pixel loop" % len(CASES))
        return 0


if __name__ == "__main__":
    sys.exit(main())
