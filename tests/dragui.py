#!/usr/bin/env python3
"""Every control a package laid out answers where its window IS after a drag.

    python3 tests/dragui.py [--machine os8088_5150_cga_gla]

SPEC.md 11.96.12.2. A window dragged by its title is replayed from the drag
cache (11.96.12) and its W_PAINT was never called - so every rect a package
laid out in its paint went on naming where the window WAS. 20.5.1.3.5 fixed
the standard button record and nothing else. The kernel now runs the
package's paint after the replay with every primitive disarmed, so the
package re-lays itself out and nothing is drawn.

Clear Skies is the subject because it is the report (*"dragging Clear Skies
makes it so I can't click any of its buttons or dropdowns"*) and because it
reaches NONE of the library's fixes: its Fly button is one rect it stages by
hand, and its two drop-downs are os88ui_drop records whose OS88UI_DR_RECT is
written in cs_paint and nowhere else. Two drags, each followed by:

1. the plane drop-down's and the Fly button's rects read back at the window's
   NEW place - the same offset from the frame they had before the drag;
2. a press on the plane drop-down at the place it is DRAWN opens its list
   (OS88UI_DR_OPEN), and a second press there closes it again;
3. a press on Fly arms it ([cs_flydn] = 1), where the build has a mode to
   fly in - the release is taken OFF the button, a cancel, so the row never
   leaves the desktop.

And the drag must still be a REPLAY: the window's content after the drop is
the content before it, pixel for pixel, at the new place - a relayout paint
that drew would be visible here as soon as any of it differed, and the
drag cache's whole point is that nothing is drawn twice.

Red with the relayout out (`make NODRAGCACHE=1` is the reference build
where it never arises): "the plane drop-down's rect still reads the window's
OLD place".
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88marty as M                                       # noqa: E402
import os88ui                                               # noqa: E402
import os88geom as geom                                     # noqa: E402
import dispapps                                             # noqa: E402

DR_OPEN = 16                    # OS88UI_DR_OPEN: rect 0, items 8, n 10,
                                # sel 12, win 14, open 16 (apps/os88ui.inc)
CSB_NONE = 0


def fail(msg):
    sys.exit("dragui: FAIL - " + msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_cga_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    a = ap.parse_args()
    for f in (a.image, a.apps, "build/skies.o88"):
        if not os.path.exists(f):
            sys.exit("dragui: no %s - `make` first" % f)
    drplane = dispapps.sym("skies", "cs_drplane")
    flyrect = dispapps.sym("skies", "cs_flyrect")
    flydn = dispapps.bss_off("skies", "cs_flydn")
    want = dispapps.bss_off("skies", "cs_want")

    with os88ui.boot(a.image, apps=a.apps, machine=a.machine) as ui:
        m = ui.m
        w = ui.path("B:/GAMES/SKIES.O88")
        base = ui._S("wm_wins") + w.i * geom.WIN_SIZE
        seg = struct.unpack("<H", bytes(m.read(base + geom.W_SEG, 2)))[0]
        # the bss starts at the image's end, which the LOADED header says
        # (SKIES.O88 is a loader and parts, so the file's +8 is the stub's -
        # tests/skies.py reads it the same way)
        bss = struct.unpack("<H", bytes(m.readseg(seg, 8, 2)))[0]
        flydn_o, want_o = bss + flydn, bss + want

        def rect(off):
            return struct.unpack("<4h", bytes(m.readseg(seg, off, 8)))

        def byte(off):
            return m.readseg(seg, off, 1)[0]

        M.until(m, lambda _: any(rect(drplane)) and any(rect(flyrect)),
                "Clear Skies' first paint to lay its controls out",
                limit=30.0)
        ui.still()
        rel = {}
        for name, off in (("plane drop-down", drplane), ("Fly", flyrect)):
            x1, y1, x2, y2 = rect(off)
            rel[name] = (off, x1 - w.x, y1 - w.y, x2 - w.x, y2 - w.y)
        print("  Skies at %d,%d: plane %r, Fly %r"
              % (w.x, w.y, rect(drplane), rect(flyrect)))

        for leg, (dx, dy) in (("one", (-48, 32)), ("two", (40, -16))):
            x0, y0 = w.x, w.y
            w = ui._refresh(ui.drag_window(w, dx, dy))
            if (w.x, w.y) == (x0, y0):
                fail("leg %s: the drag did not move the window" % leg)
            ui.still()
            print("  leg %s: dragged %d,%d -> %d,%d"
                  % (leg, x0, y0, w.x, w.y))
            # 1. the rects followed the window
            for name, (off, rx1, ry1, rx2, ry2) in rel.items():
                got = rect(off)
                exp = (w.x + rx1, w.y + ry1, w.x + rx2, w.y + ry2)
                if got != exp:
                    fail("leg %s: the %s's rect reads %r, want %r - %s"
                         % (leg, name, got, exp,
                            "the window's OLD place (SPEC.md 11.96.12.2)"
                            if got == (x0 + rx1, y0 + ry1, x0 + rx2, y0 + ry2)
                            else "somewhere else again"))
            # 2. the drop-down opens and closes at the place it is drawn
            x1, y1, x2, y2 = rect(drplane)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            ui.mo.click(cx, cy)
            try:
                M.until(m, lambda _: byte(drplane + DR_OPEN) != 0,
                        "the plane list to open", limit=20.0)
            except Exception as e:
                fail("leg %s: a press on the plane drop-down at %d,%d did "
                     "not open it: %s" % (leg, cx, cy, e))
            ui.still()
            ui.mo._sep()
            ui.mo.click(cx, cy)
            M.until(m, lambda _: byte(drplane + DR_OPEN) == 0,
                    "the plane list to close", limit=20.0)
            ui.still()
            print("  leg %s: the plane drop-down opened and closed at %d,%d"
                  % (leg, cx, cy))
            # 3. Fly arms where it is drawn (a release elsewhere cancels)
            if byte(want_o) == CSB_NONE:
                print("  leg %s: Fly is greyed on this machine - not pressed"
                      % leg)
                continue
            x1, y1, x2, y2 = rect(flyrect)
            fx, fy = (x1 + x2) // 2, (y1 + y2) // 2
            ui.mo.to(fx, fy)
            ui.mo._sep()
            ui.mo._edge(True)
            try:
                M.until(m, lambda _: byte(flydn_o) == 1,
                        "[cs_flydn] to read 1", limit=20.0)
            except Exception as e:
                ui.mo._edge(False)
                fail("leg %s: a press on Fly at %d,%d did not arm it: %s"
                     % (leg, fx, fy, e))
            ui.mo.to(w.x + w.w + 40 if w.x + w.w + 40 < 600 else 8, fy, l=True)
            ui.mo._edge(False)
            M.until(m, lambda _: byte(flydn_o) == 0,
                    "[cs_flydn] to read 0 after a cancel", limit=20.0)
            ui.still()
            print("  leg %s: Fly armed at %d,%d and cancelled" % (leg, fx, fy))
    print("dragui: ok")


if __name__ == "__main__":
    main()
