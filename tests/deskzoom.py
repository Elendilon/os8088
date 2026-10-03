#!/usr/bin/env python3
"""A zoomed window's RESTORE puts the whole desktop back (SPEC.md 11.91.6)

    make && python3 tests/deskzoom.py               # Hercules and VGA
    python3 tests/deskzoom.py --machine os8088_5150_cga_gla

Two Disk windows, the second double-clicked on its title bar to zoom over the
whole desktop band - drive cells included - and double-clicked again to
restore. The restore's damage is the union of the two rects, which is most of
the screen with two windows in it and the cells, and that region OVERFLOWS
wm_clip_tab's sixteen fragments: so this is the one ordinary gesture that
takes wm_dmg_gray's `.whole` fallback, which no other desktop row reaches.
The screen it leaves must match a forced whole repaint (tools/deskclip.py's
verify).

**BREAK IT ON PURPOSE** (docs/WRITING-TESTS.md 1), measured: put the
`call COLD_SEG:desk_dmg_zones_x` at `.whole` back BELOW its pops, where it
first landed - it spends AX, the damage's x1 the bands are re-seeded from -
and Hercules reads 39,565 pixels stale, the dither laid only right of x 618.
That was the field's report: maximize, restore, and the desktop the window
had covered left showing its title bar, listing and status line.

THE DRAG LEG is the same fallback reached by a DRAG, which arms SPEC.md
11.91.2's vacated rect: a window clear of where the dragged one WAS is not
repainted. The drop-shadow Ls and the zones (11.91.6) made the region
overflow on an ordinary drag, `.whole` then dithered EVERY band - windows
included - and the Calculator below kept the dither laid over the strip the
dragged window no longer covers. Three windows at a layout per machine that
overflows sixteen fragments (found off a model of wm_clip_split and confirmed
on the machine), one drag, and the same verify. BREAK IT ON PURPOSE,
measured: take `mov word [wm_dmg_stwin], 0` out of `.whole` and Hercules
reads 1,019 px stale in (239,224)-(464,232) and VGA 1,588 in
(410,30)-(432,166); the kernel before 11.91.6's L and zone subtraction does
not overflow at the Hercules layout and reads 0. The VGA layout keeps every
y EVEN: a Disk window moved by an odd total delta brings its scroll trough
back in the other dither phase from a whole repaint's, which is not this
row's subject and read 1,416 px on the fixed kernel at the first layout tried.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import os88ui               # noqa: E402
import deskclip as dc       # noqa: E402

BDIR = os.environ.get("OS88_BUILD", os.path.join(ROOT, "build"))


# Per machine: the Calculator, Disk A and Disk B placed, then Disk B dragged
# to `to`. The Calculator overlaps neither where Disk B was nor Disk A, and
# reaches neither the dock nor a drive cell, so nothing but 11.91.2's own
# rule decides whether it is repainted. The fragment count is a property of
# the GEOMETRY, which is why there is a layout per screen: 720x348 and
# 640x480 overflow at different places (none was found that does both).
DRAG = {
    "os8088_5150_herc_gla": dict(calc=(239, 96), a=(263, 252), b=(327, 249),
                                 to=(207, 23)),
    "os8088_xt_vga": dict(calc=(207, 30), a=(103, 210), b=(223, 238),
                          to=(87, 26)),
}


def run_drag(machine):
    lay = DRAG.get(machine)
    if lay is None:
        print("  drag: no layout for %s - skipped" % machine)
        return 0
    with os88ui.boot(os.path.join(BDIR, "os8088-360.img"),
                     apps=os.path.join(BDIR, "apps360.img"),
                     machine=machine) as ui:
        calc = ui.path("B:/APPS/CALC.O88")
        for o in ui.windows():          # the folder window path() opened on
            if o.title.startswith("APPS"):  # the way: it would sit under the
                ui.close(o)             # Calculator and mark it from below
        a = ui.open_drive("A")
        b = ui.open_drive("B")
        calc = ui.move_window(calc, *lay["calc"])
        a = ui.move_window(a, *lay["a"])
        b = ui.move_window(b, *lay["b"])
        b = ui.move_window(b, *lay["to"])
        ui.settle()
        bad = dc.verify(ui)
        print("   %s  a drag that overflows the region leaves a whole repaint"
              % ("ok " if not bad else "FAIL"))
        return bad


def run(machine):
    print(machine)
    with os88ui.boot(os.path.join(BDIR, "os8088-360.img"),
                     apps=os.path.join(BDIR, "apps360.img"),
                     machine=machine) as ui:
        ui.open_drive("A")
        w = ui.open_drive("B")
        w = ui.move_window(w, 300, 120)
        was = (w.x, w.y, w.w, w.h)
        ui.mo.dblclick(w.x + 40, w.y + 5)
        ui.settle()
        w = ui._refresh(w)
        zoomed = (w.x, w.y, w.w, w.h)
        ui.mo.dblclick(w.x + 40, w.y + 5)
        ui.settle()
        w = ui._refresh(w)
        back = (w.x, w.y, w.w, w.h)
        print("  %s -> zoomed %s -> restored %s" % (was, zoomed, back))
        bad = 0
        if zoomed == was or back != was:
            print("   FAIL  the zoom and its restore did not both happen")
            bad = 1
        bad += dc.verify(ui)
        print("   %s  the restore matches a whole repaint"
              % ("ok " if not bad else "FAIL"))
        return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", action="append")
    a = ap.parse_args()
    fails = [m for m in a.machine or ["os8088_5150_herc_gla", "os8088_xt_vga"]
             if run(m) + run_drag(m)]
    print("deskzoom: %s" % ("PASS" if not fails else "FAIL: " + " ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
