#!/usr/bin/env python3
"""DOT DELIRIUM's WINDOW: opening, moving, being covered, Thin and Full.

Every position in this package is ABSOLUTE (SPEC.md 93.3.4), and NOTHING TELLS
A PACKAGE ITS WINDOW MOVED: the kernel's drag cache (SPEC.md 11.96.12) banks a
window's pixels and replays them at the new position, so a drag calls no
W_PAINT, no OSAPI_WM_ONRESIZE and no handler of the package's at all.  Measured
before the fix, across a full drag: 0, 0 and 0, with [dd_cx]/[dd_cy] still
naming where the window used to be, and every partial draw afterwards going
there.  The field's word for it was "hopelessly broken".

So dd_render ASKS every frame, and the four legs here are the four shapes that
question has to answer:

  A  ONE FULL REDRAW ON OPEN.  The field counted three - the window opened at
     the Full size and resized itself, and the entry proc asked for a fit the
     preferred size had already given it.  [dd_fulls] is the package's own
     counter and this reads it.
  B  A MOVE COSTS NO REDRAW AT ALL.  The cache has already moved the pixels
     and they are correct where they are; what went stale is the arithmetic.
     So the content after a drag must be the SAME PICTURE, translated - and
     [dd_fulls] must not have moved.
  C  BEING COVERED AND UNCOVERED OWES EXACTLY ONE.  dd_render's .skip arm
     marks a whole frame owed when not one pixel of us is showing, which is
     what makes a re-exposed window correct rather than a frame behind.
  D  THIN AND FULL, both ways, re-cut the tile and come back.

BREAK IT ON PURPOSE: take dd_geom_win/dd_relayout_ck out of dd_render and leg B
reads a picture that did not follow the window.  Put [dd_full] back in
dd_relayout_ck's .move arm and leg B counts a redraw that buys nothing.  Ask
for a fit from the entry proc again and leg A reads 3.

One adapter is enough: none of the four is about the surface.  It runs on the
Hercules 5150 because that is the machine the reports came from.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88build                                              # noqa: E402
import os88ui                                                 # noqa: E402
from dotdel import PKG, bss, Probe                            # noqa: E402

MACHINE = "os8088_5150_herc_gla"


def content(ui, p):
    """The window's STATIC content - title, table, play line - and where it is.

    NOT the whole box.  The strip below carries the demo - its actors and
    blinking pellets move between any two captures - and the PLAY LINE blinks
    on its own clock.  Comparing either would be asking whether the game had
    stopped, which is a different question and one leg B does not want.
    [dd_ply] is where the still part ends: the title and the score table.

    AND THE POINTER IS PARKED FIRST.  The arrow is drawn by the mouse ISR over
    whatever is under it, so a capture with it inside the window compares the
    cursor as well as the picture - which is how this leg first read eleven
    differing rows for a move that was pixel-perfect.
    """
    m = ui.m
    ui.mo.to(712, 170)
    time.sleep(0.4)
    m.pause()
    x, y, w, h = (p.w("dd_cx"), p.w("dd_cy"), p.w("dd_cw"), p.w("dd_ch"))
    top = p.w("dd_ply") - y
    m.go()
    if not 8 <= top <= h:
        top = h                             # no play line: it is all still
    _, _, rows = m.vram(None)
    return (x, y, w, h), [bytes(r[x:x + w]) for r in rows[y:y + top]]


def leg_a(ui, p, say):
    fulls = p.w("dd_fulls")
    tile = (p.w("dd_tw"), p.w("dd_th"))
    if fulls != 1:
        say("A  FAIL: opening cost %d full redraws, not 1 (SPEC.md 93.3.4.2)"
            % fulls)
        return 1
    if tile != (8, 9):
        say("A  FAIL: opened at tile %dx%d, not the Thin 8x9 (SPEC.md 93.3.3.1)"
            % tile)
        return 1
    say("A  ok: one full redraw, tile %dx%d" % tile)
    return 0


def leg_b(ui, p, say):
    before_r, before = content(ui, p)
    f0 = p.w("dd_fulls")
    w = ui.window("Dot Delirium")
    ui.move_window(w, w.x + 160, w.y + 40)
    time.sleep(2.0)
    after_r, after = content(ui, p)
    f1 = p.w("dd_fulls")
    if after_r[:2] == before_r[:2]:
        say("B  FAIL: the content box did not move (%s) - dd_render is not "
            "asking where it is (SPEC.md 93.3.4.2)" % (after_r,))
        return 1
    if after_r[2:] != before_r[2:]:
        say("B  FAIL: the move changed the SIZE %s -> %s" % (before_r, after_r))
        return 1
    if after != before:
        bad = sum(1 for u, v in zip(before, after) if u != v)
        say("B  FAIL: %d of %d STATIC content rows differ after a move that should "
            "have translated the picture unchanged - the drag cache moved the "
            "pixels and the arithmetic did not follow (SPEC.md 93.3.4.2)"
            % (bad, len(before)))
        return 1
    if f1 != f0:
        say("B  FAIL: a move cost %d full redraw(s). The cache has already "
            "moved the pixels; only the arithmetic was stale (SPEC.md 93.3.4.2)"
            % (f1 - f0))
        return 1
    say("B  ok: %s -> %s, the same picture, %d full redraws"
        % (before_r[:2], after_r[:2], f1 - f0))
    return 0


def leg_c(ui, p, say):
    f0 = p.w("dd_fulls")
    others = [w for w in ui.windows() if w.title != "Dot Delirium"]
    if not others:
        say("C  FAIL: nothing else is open to cover us with")
        return 1
    ui.raise_window(others[0])
    time.sleep(2.0)
    ui.raise_window(ui.window("Dot Delirium"))
    time.sleep(2.5)
    f1 = p.w("dd_fulls")
    if f1 <= f0:
        say("C  FAIL: covering and uncovering cost %d full redraws - a "
            "re-exposed window that draws only its parts is a frame behind "
            "for ever (SPEC.md 93.5.6)" % (f1 - f0))
        return 1
    say("C  ok: covered by %r and raised again, %d full redraw(s)"
        % (others[0].title, f1 - f0))
    return 0


def leg_d(ui, p, say):
    t0 = (p.w("dd_tw"), p.w("dd_th"))
    ui.menu_pick("Window", "Full")
    time.sleep(3.5)
    t1 = (p.w("dd_tw"), p.w("dd_th"))
    if t1[0] <= t0[0]:
        say("D  FAIL: Full left the tile at %dx%d, not wider than %dx%d"
            % (t1 + t0))
        return 1
    ui.menu_pick("Window", "Thin")
    time.sleep(3.5)
    t2 = (p.w("dd_tw"), p.w("dd_th"))
    if t2 != t0:
        say("D  FAIL: Thin came back as %dx%d, not the %dx%d it opened at"
            % (t2 + t0))
        return 1
    say("D  ok: %dx%d -> %dx%d -> %dx%d" % (t0 + t1 + t2))
    return 0


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default=os88build.at("build/os8088-360.img"))
    ap.add_argument("--apps", default=os88build.at("build/apps360.img"))
    ap.add_argument("--machine", default=MACHINE)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    out = []

    def say(s):
        out.append(s)
        if a.verbose:
            print(s, flush=True)

    names = bss()
    fail = 0
    with os88ui.boot(a.img, apps=a.apps, machine=a.machine) as ui:
        ui.path(PKG)
        p = Probe(ui, names)
        time.sleep(3.0)
        fail += leg_a(ui, p, say)
        fail += leg_b(ui, p, say)
        fail += leg_c(ui, p, say)
        fail += leg_d(ui, p, say)

    # --- and leg D again on a VGA, which is where it was WRONG -------------
    # THE TWO ASPECT TABLES AGREE AT 100 THERE (SPEC.md 93.3.3.1), so the tile
    # is the only thing left to separate the two modes - and a 1.2 tolerance
    # refused the wide one by one part in fifty, so Full came out as Thin's own
    # 8x9 with a bigger window round it. Leg D's test is exactly the right one
    # and it had simply never run on the adapter that failed it.
    if a.machine == MACHINE:
        with os88ui.boot(a.img, apps=a.apps, machine="os8088_xt_vga") as ui:
            ui.path(PKG)
            p = Probe(ui, bss())
            time.sleep(3.0)
            fail += leg_d(ui, p, lambda s: say(s.replace("D  ", "D/vga  ", 1)))

    if not a.verbose:
        for s in out:
            print(s)
    print("dotdelwin: %s" % ("ok" if not fail else "%d leg(s) FAILED" % fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
