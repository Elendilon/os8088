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


def run(machine):
    print(machine)
    with os88ui.boot(os.path.join(BDIR, "os8088-360.img"),
                     apps=os.path.join(BDIR, "apps360.img"),
                     machine=machine) as ui:
        ui.open_drive("A")
        w = ui.open_drive("B")
        # move_window waits for the drag to FINISH and not just for the record
        # to read the drop: wm_dc_take puts the record back at the old place
        # for the length of its pixel save (SPEC.md 11.96.12), and a soak once
        # read it there - the zoom's double-click then landed in the OTHER
        # window's listing and opened APPS in it
        w = ui.move_window(w, 300, 120)
        was = (w.x, w.y, w.w, w.h)

        def toggled(frm):
            """double-click the title bar and WAIT for the record to change,
            on the guest's clock - a settle proves the screen still, not that
            the gesture was acted on"""
            ui.mo.dblclick(frm.x + 40, frm.y + 5)
            try:
                ui._wait(lambda: ui._rect(frm.i) != (frm.x, frm.y, frm.w,
                                                      frm.h),
                         "the title-bar double-click to zoom or restore %r"
                         % (frm.title,), 15.0)
            except os88ui.UIError as e:
                print("   %s" % e)
            ui.settle()
            return ui._refresh(frm)
        w = toggled(w)
        zoomed = (w.x, w.y, w.w, w.h)
        w = toggled(w)
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
             if run(m)]
    print("deskzoom: %s" % ("PASS" if not fails else "FAIL: " + " ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
