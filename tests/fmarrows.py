#!/usr/bin/env python3
"""SPEC.md 22.26: in a Disk window the arrows move a SELECTION (kern_big).

Driven in B:\\APPS, which holds more packages than the window shows rows, so
the view has to FOLLOW:

  1. with nothing selected Down SCROLLS, as it always did;
  2. a click selects row 0, and Down x N walks the selection off the bottom
     of the view - FS_SEL is the row, and FS_SCRL has moved just far enough
     that it is the last visible one;
  3. PgUp brings it back up a page, Up to the top;
  4. after every leg exactly ONE row band is inverted on the glass, and it
     is the selected row's - which is what catches a band left behind,
     because the move takes the old band off itself, parks [fm_lsel] across
     fm_scroll_by and puts the new one on afterwards. (A comparison against
     a full repaint cannot be had here: the view toggle that forces one also
     scrolls back to the top.)

VERIFIED TO FAIL: taking `call fm_sel_bar ; the old band off` out of
.selmove leaves the old band on screen and reds the picture checks.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
import os88geom as geom                                     # noqa: E402
import os88ui                                               # noqa: E402

fails = []


def check(name, cond, note=""):
    print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, note))
    if not cond:
        fails.append(name)


def word(ui, blk, off):
    return int.from_bytes(ui.m.read(blk + off, 2), "little")


def bands(ui, w, fit):
    """Which visible rows are drawn INVERTED: a row whose band is mostly
    dark is a selection band (SPEC.md 22.2's XOR), text alone never is."""
    x0 = w.x + 1 + 2
    x1 = w.x + w.w - 2 - 18                 # clear of the scroll bar
    y0 = w.y + geom.TITLE_H + 1 + geom.FM_ROW_Y0
    W, H, px = ui.m.fbuf()
    out = []
    for r in range(fit):
        dark = tot = 0
        for y in range(y0 + r * geom.FM_ROW_H + 2,
                       y0 + (r + 1) * geom.FM_ROW_H - 2):
            for x in range(x0, x1, 2):
                dark += px[(y * W + x) * 3] < 0x40
                tot += 1
        if dark * 2 > tot:
            out.append(r)
    return out


with os88ui.boot("build/os8088-360.img", apps="build/apps360.img") as ui:
    m = ui.m
    w = ui.path("B:/APPS")
    ui.settle()
    blk = ui._fsblk(w)
    n = word(ui, blk, geom.FS_N)
    print("== SPEC.md 22.26: the arrows move a selection (B:\\APPS, %d "
          "entries) ==" % n)

    # --- 1: nothing selected - Down scrolls ----------------------------------
    m.key("ArrowDown")
    ui.settle()
    check("with nothing selected Down scrolls",
          word(ui, blk, geom.FS_SEL) == 0xFFFF
          and word(ui, blk, geom.FS_SCRL) == 1,
          "(sel %04X, scrl %d)" % (word(ui, blk, geom.FS_SEL),
                                   word(ui, blk, geom.FS_SCRL)))
    m.key("ArrowUp")
    ui.settle()

    # --- 2: a click selects; Down walks it off the bottom, the view follows --
    x, y = ui.row_xy(w, 0)
    ui.mo.click(x, y, settle=0)
    ui.settle()
    check("a click selects row 0", word(ui, blk, geom.FS_SEL) == 0)
    fit = ui._word("fm_fit")
    steps = min(n - 1, fit + 2)
    for _ in range(steps):
        m.key("ArrowDown")
    ui.settle()
    sel = word(ui, blk, geom.FS_SEL)
    scrl = word(ui, blk, geom.FS_SCRL)
    check("Down x %d moves the selection to row %d" % (steps, steps),
          sel == steps, "(%d)" % sel)
    check("...and the view follows it to the last visible row",
          scrl == steps - fit + 1, "(scrl %d, fit %d)" % (scrl, fit))
    b = bands(ui, w, fit)
    check("ONE band on the glass, on the selected row", b == [sel - scrl],
          "(inverted rows %r, want [%d])" % (b, sel - scrl))

    # --- 3: PgUp a page, Up to the top ---------------------------------------
    m.key("PageUp")
    ui.settle()
    check("PgUp moves it a page", word(ui, blk, geom.FS_SEL) == steps - fit,
          "(%d)" % word(ui, blk, geom.FS_SEL))
    for _ in range(steps):
        m.key("ArrowUp")
    ui.settle()
    check("Up stops at the first row", word(ui, blk, geom.FS_SEL) == 0
          and word(ui, blk, geom.FS_SCRL) == 0,
          "(sel %d, scrl %d)" % (word(ui, blk, geom.FS_SEL),
                                 word(ui, blk, geom.FS_SCRL)))
    b = bands(ui, w, fit)
    check("...and ONE band, on row 0", b == [0], "(inverted rows %r)" % b)

print()
if fails:
    print("FAILURES:")
    for f in fails:
        print("  " + f)
    sys.exit(1)
print("all pass")
