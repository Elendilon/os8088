#!/usr/bin/env python3
"""DOT DELIRIUM on a TWO-CARD desktop (SPEC.md 93.4): straddle, move between
displays, and go fullscreen from each.

`xt-multimon`'s question, asked of a game. Four things, and three of them can
only go wrong here:

  A  STRADDLING, BOTH DISPLAYS CARRY CONTENT.  The window sits across the
     seam and each card has a real share of the picture on it. A package that
     got this wrong would draw its whole face onto the primary and leave the
     monitor it is actually on showing the desktop.
  B  MOVING BETWEEN DISPLAYS RE-CUTS THE BOARD.  The window manager gives a
     window moved onto the Hercules a taller box, and SPEC.md 93.3 says the
     tile comes out of the live content box and that adapter's PIXEL SHAPE -
     so the tile has to CHANGE, and change back.
  C  THE BRACKET FOLLOWS THE WINDOW.  A same-mode fullscreen owns ONE display
     and must ask which (SPEC.md 53.7.1); both consumers in this tree got that
     wrong first, drawing the whole game onto the monitor they were not on.
     So the surface the bracket takes has to differ between the two displays,
     and be the one the window is on.
  D  ...AND LEAVING PUTS THE WINDOW'S OWN TILE BACK.

BREAK IT ON PURPOSE: replace `OSAPI_FSX_SURF` with (0,0) plus `OSAPI_VIDEO`'s
size and leg C goes red naming both surfaces as 640x200; stop dd_relayout_ck
re-cutting on a size change and leg B goes red with the CGA's 8x4 tile still
in place on a 347-row window.

WHAT IT DOES NOT COVER, and this was checked rather than assumed: taking the
ADAPTER KIND out of dd_relayout_ck's bank leaves this row green, because the
window manager also changes the window's SIZE when it moves onto the Hercules
and the size comparison catches it first. The bank is for a move between two
displays that does not resize - which no machine in this tree has - so it
stands on its reasoning and not on this row.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import dispcp                                               # noqa: E402
import os88marty                                            # noqa: E402
import os88mouse                                            # noqa: E402
import os88sym                                              # noqa: E402
import os88ui                                               # noqa: E402
from dotdel import PKG, Probe, bss                          # noqa: E402

S = os88sym.linear
SEAM = 640                              # the CGA primary's own width


def lit(m, card):
    w, h, data = m.fbuf(0, card=card)
    return sum(1 for j in range(0, len(data), 3)
               if data[j:j + 3] != b"\x00\x00\x00")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_both_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/media360.img")
    a = ap.parse_args(argv)
    say = lambda s: print("  " + s)
    fail = []
    names = bss()

    with os88marty.launch(a.image, apps=a.apps, machine=a.machine,
                          boot=False) as m:
        cards = m.cards()
        if len(cards) != 2:
            sys.exit("dotdelmd: %s has %d video card(s), not 2"
                     % (a.machine, len(cards)))
        m.run()
        os88marty.settle(m, gate=os88marty.desktop_up)
        mo = os88mouse.Mouse(marty=m)
        dispcp.open_panel(m, mo, S, os88marty.settle)
        dispcp.set_mode(m, mo, S, os88marty.settle, "right")
        dispcp.close_panel(m, mo, S, os88marty.settle)
        if m.read(S("vid_ndisp"), 1)[0] != 2:
            sys.exit("dotdelmd: the Control Panel did not turn Extend on")

        ui = os88ui.UI(m)
        ui.path(PKG)
        time.sleep(2)
        p = Probe(ui, names)

        def now(tag):
            w = ui.window("Dot Delirium")
            t = (p.w("dd_tw"), p.w("dd_th"))
            c = (lit(m, 0), lit(m, 1))
            say("%-24s win (%d,%d) %dx%d  tile %dx%d  lit %d/%d"
                % (tag, w.x, w.y, w.w, w.h, t[0], t[1], c[0], c[1]))
            return w, t, c

        w0, t0, _ = now("on the primary")

        # --- A: straddling, both cards carry a share -----------------------
        ui.move_window(w0, SEAM - w0.w // 2, 20)
        time.sleep(3)
        w1, t1, c1 = now("straddling the seam")
        if w1.x >= SEAM or w1.x + w1.w <= SEAM:
            fail.append("the window at (%d..%d) does not cross the seam at %d "
                        "- leg A never ran" % (w1.x, w1.x + w1.w, SEAM))
        elif min(c1) < 20000:
            fail.append("straddling, one display has %d lit against the "
                        "other's %d - the content is not being cut at the seam"
                        % (min(c1), max(c1)))
        if not p.b("dd_ok"):
            fail.append("the layout gave up while straddling")

        # --- C: the bracket takes the display the window is on --------------
        m.key("KeyF")
        time.sleep(4)
        surf = (p.w("dd_cw"), p.w("dd_ch"), p.w("dd_cx"), p.w("dd_cy"))
        say("bracket from a straddle: %dx%d at (%d,%d)" % surf)
        if surf[:2] not in ((640, 200), (720, 348)):
            fail.append("the bracket's surface is %dx%d - a same-mode bracket "
                        "owns ONE display and must ask which (SPEC.md 53.7.1)"
                        % surf[:2])
        m.key("Escape")
        time.sleep(4)
        _, t2, _ = now("back from fullscreen")
        if t2 != t1:
            fail.append("leaving the bracket left the tile at %dx%d, not the "
                        "window's %dx%d" % (t2 + t1))

        # --- B: wholly onto display 1, and the tile follows ----------------
        w = ui.window("Dot Delirium")
        ui.move_window(w, SEAM + 55, 20)
        time.sleep(3)
        w3, t3, _ = now("wholly on display 1")
        if t3 == t0:
            fail.append("the tile is still %dx%d on the Hercules - a window "
                        "moved between two adapters of different PIXEL SHAPE "
                        "must be re-cut (SPEC.md 93.3, 93.4)" % t0)
        m.key("KeyF")
        time.sleep(4)
        s1 = (p.w("dd_cw"), p.w("dd_ch"))
        say("bracket on display 1: %dx%d at (%d,%d)"
            % (s1[0], s1[1], p.w("dd_cx"), p.w("dd_cy")))
        m.key("Escape")
        time.sleep(4)

        # --- D: ...and all the way home ------------------------------------
        w = ui.window("Dot Delirium")
        ui.move_window(w, 40, 20)
        time.sleep(3)
        _, t4, _ = now("back on the primary")
        if t4 != t0:
            fail.append("home again, the tile is %dx%d and not the %dx%d it "
                        "opened with" % (t4 + t0))
        m.key("KeyF")
        time.sleep(4)
        s0 = (p.w("dd_cw"), p.w("dd_ch"))
        say("bracket on display 0: %dx%d at (%d,%d)"
            % (s0[0], s0[1], p.w("dd_cx"), p.w("dd_cy")))
        m.key("Escape")
        time.sleep(3)
        if s0 == s1:
            fail.append("the bracket took the SAME %dx%d surface from both "
                        "displays - it is not following the window "
                        "(SPEC.md 53.7.1)" % s0)
        else:
            say("the bracket followed the window: %dx%d on display 1, "
                "%dx%d on display 0" % (s1 + s0))

    if fail:
        print("dotdelmd: %d FAILED" % len(fail))
        for f in fail:
            print("    FAIL: %s" % f)
        return 1
    print("dotdelmd: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
