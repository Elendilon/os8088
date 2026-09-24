#!/usr/bin/env python3
"""TITHE's BOLTS: do they go OVER the characters and leave nothing behind?

SPEC.md 97.4.5. `A` sustains the resolution's worst ranged case - one bolt a
side in the same lane, P1's flying right and P2's left, crossing - and each
bolt's band is composed from the board AS THE GLASS SHOWS IT: the strips, the
band every cell last committed, and its numbers over the bolt. The bolt used
to carry the ground alone, so crossing a cell painted the ground over the
figure standing in it.

WHAT IT ASSERTS, on all three adapters, and it went red on purpose first:

  1. MID-FLIGHT, THE ONLY PIXELS THAT ARE NOT THE BOARD ARE THE BOLTS. With
     the wheel paused, the glass against a whole repaint (which draws no bolt)
     differs by at most two bolts' worth of pixels - so nothing a band carried
     is anything but the board it crossed - and at one of three moments at
     least half a bolt shows, so the bolts are really up. A moment may show
     none: a pair that has just arrived, or a bolt under a digit. A band of
     ground alone fails by hundreds of pixels, a figure's worth each time.

  2. WHEN THE ARM IS OFF, NOTHING IS LEFT: the glass is exactly a whole
     repaint - which is the arriving bolt's last, bolt-less band doing its job.

    make && make tithedisk && python3 tests/tithepj.py
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402
import titheterr as te                                    # noqa: E402
import titherv as tv                                      # noqa: E402

ART = 32                          # lit pixels in ti_pj_art, the eight-row bolt
fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


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
        te.fill(m, seg, off)             # the bolts cross FIGURES: a full board

        def rw(name):
            return struct.unpack("<H", bytes(m.readseg(seg, off[name], 2)))[0]

        w, h, _ = te.mono(m)
        box = (max(0, win.x), rw("ti_by"), min(w, win.x + win.w),
               min(h, win.y + win.h))

        def repaint_diff():
            """Pause, read the glass, repaint the whole board (`ti_rpq`) and
            read it again: what differs."""
            m.key("KeyP")
            os88marty.guest_sleep(m, 0.3)
            _, _, a = te.mono(m)
            tv.whole_repaint(m, seg, off)
            _, _, b = te.mono(m)
            m.key("KeyP")
            return [(x, y) for y in range(box[1], box[3])
                    for x in range(box[0], box[2]) if a[y][x] != b[y][x]]

        m.key("KeyA")
        seen = []
        for k, t in enumerate((0.3, 0.5, 0.4)):
            os88marty.guest_sleep(m, t)
            d = repaint_diff()
            seen.append(len(d))
            check(len(d) <= 2 * ART,
                  "mid-flight %d: the glass is the board and the bolts, and "
                  "nothing else" % k, "%d px, first %s" % (len(d), d[:4]))
        check(max(seen) >= ART // 2, "...and the bolts are up",
              "differences %s" % seen)
        m.key("KeyA")
        os88marty.guest_sleep(m, 3.0)
        d = repaint_diff()
        check(not d, "the arm off, the glass is exactly a whole repaint",
              "%d px, first %s" % (len(d), d[:4]))


def main():
    off = tv.offsets()
    for mach in (sys.argv[1:] or te.MACHINES):
        run(mach, off)
    print("tithepj: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
