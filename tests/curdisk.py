#!/usr/bin/env python3
"""SPEC.md 7.4: the arrow TRACKS the hand through a disk transfer.

    make && python3 tests/curdisk.py

A file operation freezes the machine (SPEC.md 12.8, 18) and the pointer used
to freeze with it - worse than freeze, once the operation moved FPG_WARM = 3
sectors the progress widget armed, `fpg_paint` spent `gfx_lock`'s promised
hide, and the arrow LEFT THE SCREEN for the rest of the freeze.

THIS ROW BUILDS `make NOCURDISK=1` ITSELF and puts the default kernel back,
because a one-armed reading here is worth very little.  Both claims below are
about a DIFFERENCE - "the arrow moved while the lock was held" is only
interesting against a kernel where it provably cannot - and dispseam.py's
record is the reason the A/B is not optional: a null result is evidence about
the TEST until the test is shown to contain the case.

WHY IT IS NOT A SCREENSHOT.  What changed is not what a frame looks like but
WHEN it changes, and both kernels draw the identical arrow at the identical
place given the identical mouse position.  So this samples the kernel's own
state through the freeze instead - `[gfx_lock_flag]`, `[fpg_on]`,
`[cur_level]` and `[cur_drawn_x]`/`[cur_drawn_y]` - and asks two questions of
the samples:

  1. IS THE ARROW STILL ON THE GLASS while the widget is up?  `[cur_level]`
     < 0 is hidden.  On the old kernel this is 0% by construction: fpg_paint
     hides unconditionally at arm time, BEFORE any of the operation's disk
     work.  On the new one the hide is owed only when the arrow could reach
     the menu bar (SPEC.md 7.4.3), and this test parks it far below.
  2. DOES IT MOVE while `[gfx_lock_flag]` is set?  A change in
     `[cur_drawn_x]`/`[cur_drawn_y]` between two consecutive samples that both
     saw the lock held is a cursor move inside a lock hold, which mou_apply's
     first compare makes unreachable on every kernel before SPEC.md 7.4.

Question 2 is the headline and question 1 is what a person actually reports.

ON MARTYPC, because QEMU cannot time anything (docs/TESTING.md) and because
the whole claim is about what happens while the CPU sits inside the ROM.
Nothing here is a TIMING assertion, though: every figure is a count of
samples, so an oversubscribed host changes none of it.
"""
import atexit
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import os88marty                                             # noqa: E402
import os88mouse                                             # noqa: E402
import os88sym                                               # noqa: E402
import dispcp                                                # noqa: E402

MACHINE = "os8088_5150_cga_gla"
IMAGE = "build/os8088-360.img"
APPS = "build/apps360.img"

# How long to watch, and how finely.  One frame is ~16.7 ms of guest time; a
# mount plus a directory walk plus an icon harvest is seconds of it, so this
# is a generous ceiling rather than a tight one - the loop stops as soon as
# the widget goes away.
SAMPLES = 400
DEADBAND = 12           # consecutive samples with the widget down = finished

# Guest frames per sample.  A 1200-baud report is 3 bytes of 7N1 - 22.5 ms,
# which does NOT fit in one 16.7 ms frame (SPEC.md 7.1.4.3's "~25-40 ms"), so
# a one-frame step samples faster than the mouse can possibly report and every
# other sample sees a packet still in flight.
PACKET = 2

# What the default arm has to beat.  Measured on os8088_5150_cga_gla opening
# B:\SYSTEM - 29 moves under the lock and the arrow lit for 18 of 24 widget
# samples (75%) - against NOCURDISK=1's 0 and 0%.  These are a third of that
# and a quarter of it: what they have to separate is "tracking" from "cannot
# move at all", and the tail of any operation legitimately hides the arrow
# again the moment a painter that is NOT confined to the menu bar runs
# (SPEC.md 7.1.4), which here is the window repainting its list.
MOVES_MIN = 5
LIT_MIN = 25.0          # % of the widget-up samples

# The pointer is walked up and down by this much per sample.  Small enough
# that it stays well clear of the menu bar (SPEC.md 7.4.2 refuses a move whose
# cell could reach it, and that refusal would read exactly like the defect).
STEP = 3
SWING = 20              # samples per direction


def say(*a):
    print(*a)
    sys.stdout.flush()


def sample(m, S):
    """(lock, fpg, level, x, y) - one look at the cursor's world."""
    return (m.read(S("gfx_lock_flag"), 1)[0],
            m.read(S("fpg_on"), 1)[0],
            m.read(S("cur_level"), 1)[0],
            int.from_bytes(m.read(S("cur_drawn_x"), 2), "little"),
            int.from_bytes(m.read(S("cur_drawn_y"), 2), "little"))


def watch(m, S, mo, rx, ry):
    """Start a file operation and sample the cursor's state through it."""
    mo.to(rx, ry)
    m.advance(frames=4)
    base = sample(m, S)
    m.run()                     # `advance` STOPS the guest, and a stopped
                                # guest shifts no UART bits - so the presses
                                # below would never be decoded
    say("  pointer parked at (%d,%d), cur_level %d"
        % (base[3], base[4], base[2] - 256 if base[2] > 127 else base[2]))

    # THE OPERATION, and deliberately not settled: everything interesting
    # happens while it runs.  settle=0 makes dblclick issue the two presses
    # and return instead of sleeping through the very window under test.
    mo.dblclick(rx, ry, settle=0)

    out, quiet, up, seen = [], 0, True, False
    for i in range(SAMPLES):
        m.advance(frames=PACKET)    # ...which also STOPS the guest, so every
        s = sample(m, S)            # read below is of a machine that is not
        out.append(s)               # moving under it
        if s[1]:
            seen, quiet = True, 0
        elif seen:
            # THE DEADBAND ONLY COUNTS AFTER THE WIDGET HAS BEEN UP. Counting
            # it from the start ends the run before the operation has warmed
            # past FPG_WARM = 3 sectors, which is a stop this test read as
            # "the widget never armed" - a setup failure reported against a
            # kernel that was working.
            quiet += 1
            if quiet >= DEADBAND:
                break
        # keep the hand moving - this is the input the claim is about
        if i % SWING == SWING - 1:
            up = not up
        m.mouse(dy=-STEP if up else STEP)
    return out


def leg(defines, label):
    S = (lambda n: os88sym.linear(n, defines))
    say("\n=== %s ===\n" % label)
    with os88marty.launch(IMAGE, apps=APPS, machine=MACHINE) as m:
        mo = os88mouse.Mouse(marty=m)
        os88marty.no_saver(m)

        # Setup: a Disk window on B:, and a folder row to open inside it.  The
        # row is used rather than the desktop's drive zone because a row is
        # far below the menu bar, and SPEC.md 7.4.2's widget test refuses a
        # move near it - measuring there would report the guard as the defect.
        dispcp.open_drive(m, mo, S, os88marty.settle, "B")
        disk = dispcp.win_list(m, S)[-1]
        dx, dy, _, _ = dispcp.win_rect(m, S, disk)
        entry = dispcp.row_of(m, S, "SYSTEM")
        row = dispcp.scroll_to(m, mo, S, os88marty.settle, dx, dy, entry)
        rx, ry = dispcp.row_xy(dx, dy, row)

        s = watch(m, S, mo, rx, ry)

    busy = [x for x in s if x[1]]
    held = [x for x in s if x[0]]
    lit = [x for x in busy if x[2] < 128]        # cur_level >= 0
    moves = sum(1 for a, b in zip(s, s[1:])
                if a[0] and b[0] and (a[3], a[4]) != (b[3], b[4]))
    say("  %d samples: %d with the widget up, %d with the lock held"
        % (len(s), len(busy), len(held)))
    say("  arrow ON THE GLASS for %d of %d widget samples (%s)"
        % (len(lit), len(busy),
           "%.0f%%" % (100.0 * len(lit) / len(busy)) if busy else "n/a"))
    say("  arrow MOVED under the lock %d times" % moves)
    if "--trace" in sys.argv:
        say("    #   lock fpg lvl    x    y")
        for i, x in enumerate(s):
            say("    %-3d %4d %3d %3d %4d %4d"
                % (i, x[0], x[1], x[2] - 256 if x[2] > 127 else x[2],
                   x[3], x[4]))
    return {"n": len(s), "busy": len(busy), "held": len(held),
            "lit": len(lit), "moves": moves}


def main(argv):
    os.chdir(ROOT)
    solo = "--solo" in argv
    fail = []

    new = leg((), "default: the arrow tracks the hand (SPEC.md 7.4)")

    if not new["busy"]:
        fail.append("SETUP: the progress widget never armed, so no sample was "
                    "taken during a freeze at all. The operation was too "
                    "short (FPG_WARM is 3 sectors in ONE lock hold) or the "
                    "double-click missed the row - nothing below means "
                    "anything, and this is not a verdict on SPEC.md 7.4.")
    if not new["held"]:
        fail.append("SETUP: no sample saw the gfx lock held, so the freeze "
                    "itself was never observed.")
    if not fail:
        if new["moves"] < MOVES_MIN:
            fail.append("the arrow NEVER MOVED under the lock. That is the "
                        "whole of SPEC.md 7.4: [cur_inrom] should let the "
                        "mouse ISR run cur_move inside each int 13h. Check "
                        "the three gates in 7.4.2 - a clip region left armed "
                        "by a painter, or a lock held by another task, both "
                        "defer for good reasons and would read like this.")
        share = 100.0 * new["lit"] / new["busy"] if new["busy"] else 0.0
        if share < LIT_MIN:
            fail.append("the arrow was on the glass for only %.0f%% of the "
                        "freeze (want >= %.0f%%). SPEC.md 7.4.3 is what "
                        "changed this: [cur_barok] makes cur_unlazy keep "
                        "gfx_lock's promise for a painter confined to the "
                        "menu bar, and the unclipped menu_draw_bar inside "
                        "fpg_arm is the one that used to hide the pointer for "
                        "the whole operation before fpg_paint was reached."
                        % (share, LIT_MIN))

    if solo:
        say("\ncurdisk: --solo, the NOCURDISK=1 leg is skipped")
        old = None
    else:
        say("\n--- building the other arm ---")
        subprocess.check_call(["make", "NOCURDISK=1"], cwd=ROOT,
                              stdout=subprocess.DEVNULL)
        atexit.register(subprocess.check_call, ["make"], cwd=ROOT,
                        stdout=subprocess.DEVNULL)
        old = leg(("NOCURDISK",), "NOCURDISK=1: the freeze it replaces")

        if old["moves"]:
            fail.append("NOCURDISK=1 moved the arrow under the lock %d times, "
                        "and it cannot: mou_apply's first compare is "
                        "`cmp byte [gfx_lock_flag], 0 / jne .dirty`. Either "
                        "the knob is not reaching the build (check VIDSTAMP "
                        "and KNOBS in the Makefile) or these samples are not "
                        "reading what they claim to."
                        % old["moves"])
        oshare = 100.0 * old["lit"] / old["busy"] if old["busy"] else 0.0
        if oshare >= LIT_MIN:
            fail.append("NOCURDISK=1 kept the arrow on the glass for %.0f%% "
                        "of the freeze, which is the behaviour it exists to "
                        "NOT have: its cur_unlazy is unconditional, so the "
                        "bar composition inside fpg_arm should take the "
                        "pointer off within a few instructions of arming. "
                        "The two arms are not separated, so the default "
                        "arm's %.0f%% says nothing." % (oshare, share))
        # A SAMPLE OR TWO HERE IS NOT A FAILURE, and the bound above is a
        # share rather than a zero for that reason: fpg_arm sets [fpg_on]
        # BEFORE the cursor block that follows it (SPEC.md 12.8.4), so a
        # sample landing in those few instructions sees the widget up and the
        # arrow not yet down. Measured at 1 of 24. `moves` has no such window
        # and IS asserted at zero, because mou_apply's first compare makes a
        # move under the lock unreachable rather than merely unlikely.
        if not old["busy"]:
            fail.append("SETUP: the NOCURDISK=1 leg never armed the widget "
                        "either, so the two arms are not comparable.")

    say("")
    if fail:
        say("curdisk: %d FAILED" % len(fail))
        for f in fail:
            say("  FAIL: %s" % f)
        return 1
    if old is not None:
        say("curdisk: pass - %d moves under the lock against NOCURDISK's %d, "
            "arrow lit for %d of %d widget samples against %d"
            % (new["moves"], old["moves"], new["lit"], new["busy"],
               old["lit"]))
    else:
        say("curdisk: pass (one arm)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
