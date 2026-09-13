#!/usr/bin/env python3
"""Can a DOS program be given ARGUMENTS? (SPEC.md 96.19)

Half the DOS software worth running is configured by its command line, and
until this wave the box wrote an EMPTY tail and every program got its
defaults.  Creative's own card test prints "run this program again and select
the other options manually" and there was no way to say `/M`.

The row drives the whole loop the feature is for, because each step is a
separate thing that can be missing:

  1  it runs with NO arguments, and the program says so - COUNT 0 and no
     terminator offset.  That is the state the user is in when they discover
     they needed some.
  2  the window SURVIVES the exit with the program still named (SPEC.md 96.1),
     which is what makes step 3 possible without File->Open.
  3  clicking the field takes the caret and TYPING fills it.
  4  ENTER RUNS IT AGAIN (96.19.4) - without this the field is a box the user
     types into and nothing reads.
  5  the program now sees the text, IN BOTH FRAMINGS.  PSP:0080 is a length
     byte and the text after it ends in 0Dh; a program that treats the tail as
     a counted string reads one and a program that parses its own arguments
     scans for the other.  A shim that wrote only one is wrong for half the
     world, so the gate program reports COUNT and TERM independently and this
     asserts both.
  6  MYPATH is a real path (96.19.3).  It was a bare 8.3 name until
     OSAPI_FILE_PATH existed, which is why the gate disk puts the program in a
     subdirectory: in the root both spellings agree and the row proves nothing.
"""
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import dosmap                                                  # noqa: E402
import os88marty                                               # noqa: E402
import os88mouse                                               # noqa: E402
import os88geom                                                # noqa: E402
import os88ui                                                  # noqa: E402

SYS = "build/os8088-360.img"
ARGS = "build/dosargs360.img"
TYPED = "/M P:220"                   # ...what a user would actually type
WANTPATH = "B:\\BIN\\DOSARGS.COM"
ENVVAR = "SOUND=SB"              # ...typed in the Setup page's env row
# **NOT ONE LAYOUT CONSTANT HERE ANY MORE.** Five stood here - DOS_FLDW,
# DOS_BTNW, DOS_BTNY, DOS_EROWY, DOS_FLDY - copied from apps/dos/dos.asm under
# a comment saying that mirroring them was "the nearest a package-local
# constant gets" to doing this properly. It is not near enough: SPEC.md 96.32
# moved every one of those controls and this row went on clicking where they
# used to be, with nothing to say about it. dosmap.centre reads each control's
# real rect out of the guest's own bss instead.
#
# **AND THE COUNTERS ARE READ BY NAME** (dosmap), never at an offset counted by
# hand. `R_NCELL, R_NKEY = 6, 8` stood here - "past DOS_B_CTOP/LNV/LNL" - and
# SPEC.md 96.32 put four words of console geometry in that gap, so this row
# started reading dos_conrows and dos_concols and reporting them as "25
# keystrokes redrew 80 glyph cells". A plausible number from the wrong word is
# worse than a crash, which is the same failure docs/WRITING-TESTS.md keeps
# naming: a layout known in two places decodes nonsense the day it moves.


def u16(m, at):
    return struct.unpack("<H", m.read(at, 2))[0]


def pkg_base(m):
    """dos.o88's bss: the window's segment, plus the image size at +8."""
    S = m.sym
    for slot in range(8):
        wp = os88geom.winptr(m, slot, S)
        seg = u16(m, wp + os88geom.W_SEG)
        if not seg:
            continue
        ttl = u16(m, wp + os88geom.W_TITLE)
        if ttl and m.read(seg * 16 + ttl, 4).startswith(b"DOS\0"):
            return seg * 16 + u16(m, seg * 16 + 8)
    fail("the DOS window is not in the table")


def fail(msg):
    print("dosargs: FAIL: %s" % msg)
    sys.exit(1)


def field(text, name):
    m = re.search(r"^%s (.*?)\s*$" % name, text, re.M)
    return m.group(1) if m else None


def run_and_read(m, limit=120.0):
    """Wait for the program's READY line and hand back its whole screen."""
    end = time.time() + limit
    while time.time() < end:
        rows = m.screen() or []
        if any("READY" in r for r in rows):
            return "\n".join(r.rstrip() for r in rows)
        time.sleep(0.3)
    fail("the program never reached its READY line; the last screen was %r"
         % ([r.rstrip() for r in (m.screen() or []) if r.strip()][:10],))


def main():
    for p in (SYS, ARGS):
        if not os.path.exists(p):
            fail("%s is missing - `make doscom` builds the gate disks" % p)

    with os88ui.boot(SYS, apps=ARGS, machine="os8088_5150_herc_gla") as ui:
        m = ui.m

        # --- 1: no arguments -------------------------------------------------
        if not ui.path("B:/BIN/DOSARGS.COM"):
            fail("could not launch the gate program")
        first = run_and_read(m)
        print("dosargs: the first run, with nothing typed:")
        for r in first.splitlines()[:8]:
            if r.strip():
                print("   | %s" % r)

        if field(first, "COUNT") != "0":
            fail("a program launched with no arguments reports COUNT %s - the "
                 "tail should be empty and its count zero"
                 % field(first, "COUNT"))
        if field(first, "TERM") != "0":
            fail("the 0Dh is at offset %s in an EMPTY tail - it belongs at 0, "
                 "and a program that parses its own arguments scans until it "
                 "finds one" % field(first, "TERM"))

        # --- 6: the environment's own path -----------------------------------
        got = field(first, "MYPATH")
        if got != WANTPATH:
            fail("the environment says this program's path is %r and it is "
                 "%r. DOS 3+ puts it after the set's NUL and a count word, "
                 "and it was a bare 8.3 name until OSAPI_FILE_PATH existed "
                 "(SPEC.md 96.19.3)" % (got, WANTPATH))
        print("dosargs: ...and its own path in the environment is %r" % got)

        # --- 2: the window survives with the program named -------------------
        m.type_text("x")
        os88marty.settle(m)
        w = ui.window("DOS")
        if not w:
            fail("the DOS window did not survive the exit, so there is "
                 "nowhere to type the arguments the user just discovered they "
                 "needed (SPEC.md 96.1)")
        ui.raise_window(w)

        # --- 2b: THE POST-EXIT FILL STAYED INSIDE THE WINDOW -----------------
        # SPEC.md 96.19.5: dos_repaint set its ink with `mov al, CWHITE` AFTER
        # OSAPI_WM_CONTENT had answered x1 in AX - and AL is that x1's low
        # byte, so a content left of 121 (0x0079) became 15 and the fill ran
        # from near the screen's edge across to the window's right, taking the
        # border and the desktop beside it.
        #
        # MEASURED BEFORE ANYTHING MOVES, and that is the whole difficulty:
        # a move or a close repaints the damaged area and ERASES THE EVIDENCE.
        # An earlier version of this check moved the window first and stayed
        # green with the bug deliberately put back.
        #
        # **IT LOOKS BELOW THE WINDOW NOW, AND IT HAS TO** (SPEC.md 96.32).
        # This used to sample the desktop to the LEFT of the window, which was
        # where a clobbered x1 showed: the fill ran from near the screen's
        # edge across to the window's right, eating the border and the dither
        # beside it. The window SPANS THE SCREEN WIDTH now - 80 columns is 640
        # pixels and VGA and CGA are 640 wide - so there is no desktop to its
        # left to eat, and the old sample was reading the window's own white
        # content and calling it a band.
        #
        # What is still there to guard is the fill escaping VERTICALLY, which
        # is the same defect measured on the axis that still has desktop on
        # it. The rows below the window are the dither and must stay it.
        wd, ht, data = m.fbuf()

        def lit(x, y):
            return data[(y * wd + x) * 3] < 128

        y0 = w.y + w.h + 2
        rows = [y for y in range(y0, min(y0 + 40, ht - 1))]
        if len(rows) < 8:
            fail("this adapter leaves no desktop below the window, so the "
                 "escape check has nothing to measure - run it on one that "
                 "does (Hercules is 348 rows and the window is 239)")
        ink = sum(1 for y in rows for x in range(20, 90) if lit(x, y))
        frac = ink / float(len(rows) * 70)
        if not 0.35 <= frac <= 0.65:
            fail("the desktop BELOW the window is %.0f%% ink and SPEC.md 63's "
                 "dither is 50. A white band there is a fill that ran past the "
                 "window's own content box (SPEC.md 96.19.5)" % (frac * 100))
        print("dosargs: the desktop below the window is %.0f%% ink - the fill "
              "stayed inside (SPEC.md 96.19.5)" % (frac * 100))

        dw = ui.disk_window()
        if dw:
            ui.close(dw)
        # **THE MOVE IS GONE** (SPEC.md 96.32). It was here to get the window
        # clear of the Disk window, which the close above already does now
        # that the DOS window spans the screen - and it cannot do what it
        # used to anyway: `wm_land_fit` refuses every horizontal destination
        # for a screen-width frame, so a drag to 300 lands back at 0.
        #
        # What it would ALSO have needed is a repaint, and that is worth
        # writing down because the console wave inherits it: **a MOVE does
        # not call the paint callback** - the window manager carries the
        # pixels - so every screen-coordinate rect this package caches stays
        # at the old position until something paints or clicks. dos_click and
        # dos_key both call dos_place first, so the box itself is never wrong;
        # a reader that takes the rects out of bss and then clicks them is.
        w = ui.window("DOS")

        # --- 3: click the field and type -------------------------------------
        # **THE ARGUMENTS BOX IS ON THE SETUP PAGE NOW** (SPEC.md 96.32.2), so
        # getting to it is a click on the bar's Environment button first. Every
        # coordinate below is READ OUT OF THE GUEST by name (dosmap.centre) -
        # this row used to compute them from host-side copies of the layout
        # constants, and when the layout moved it went on clicking an empty
        # part of the window with nothing to say about it.
        mo = os88mouse.Mouse(marty=m)
        pseg = dosmap.instance(m)
        dm = dosmap.package()
        mo.click(*dosmap.centre(m, pseg, dm, "dos_erect"))
        os88marty.settle(m)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_ln"))
        os88marty.settle(m)
        for ch in TYPED:
            m.type_text(ch)
        os88marty.settle(m)
        wd, ht, data = m.fbuf()
        os88marty.write_png_rgb("build/dosargs.png", wd, ht, data)

        # --- 5: WHAT DID THE TYPING COST? ------------------------------------
        # The point of a narrow redraw, and the only way to see it: redrawing
        # the same glyph changes no pixel, so a field that repaints all twenty
        # characters on every keystroke is INVISIBLE to the flick instrument
        # and costs ~18ms a key on the target machine (PERFORMANCE.md prices a
        # glyph cell at ~900us). dos.asm counts the cells os88line_edit says it
        # drew; a whole-field repaint of this text would be 1+2+...+8 = 36.
        cells = u16(m, (pseg << 4) + dm["dos_ncell"])
        keys = u16(m, (pseg << 4) + dm["dos_nkey"])
        print("dosargs: %d keystrokes redrew %d glyph cells" % (keys, cells))
        if keys != len(TYPED):
            fail("%d keystrokes were counted for %d typed - the field did not "
                 "take them all" % (keys, len(TYPED)))
        if cells > keys * 2:
            fail("%d keystrokes redrew %d cells. An APPEND touches ONE cell; "
                 "os88line_draw would have repainted the whole field every "
                 "time, which for this text is %d - invisible in pixels and "
                 "~%.0fms a keystroke on a 4.77MHz machine (SPEC.md 96.19.1)"
                 % (keys, cells, sum(range(1, len(TYPED) + 1)),
                    len(TYPED) * 0.9))

        # --- 3b: THE ENVIRONMENT ROW (SPEC.md 96.20, 96.32.2) ----------------
        # It is on the SAME page as the arguments box now - one env row beside
        # them, which IS Environment's first row rather than a copy of it - so
        # this no longer changes page at all. Then Return, which is what leaves
        # the setup area and also commits the memory limit.
        mo.click(*dosmap.centre(m, pseg, dm, "dos_eln"))
        os88marty.settle(m)
        for ch in ENVVAR:
            m.type_text(ch)
        os88marty.settle(m)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_trect"))
        os88marty.settle(m)

        # --- 4: Enter runs it again ------------------------------------------
        m.key("Enter")
        second = run_and_read(m)
        print("dosargs: ...and again, after typing %r:" % TYPED)
        for r in second.splitlines()[:8]:
            if r.strip():
                print("   | %s" % r)

        # --- 5: both framings ------------------------------------------------
        args = field(second, "ARGS")
        if args != TYPED:
            fail("the program read its tail as %r and %r was typed. If it is "
                 "empty the field never reached PSP:0080; if it is short the "
                 "count is wrong; if it has rubbish on the end the 0Dh is"
                 % (args, TYPED))
        if field(second, "COUNT") != str(len(TYPED)):
            fail("PSP:0080's LENGTH BYTE says %s for a %d-character tail. A "
                 "program that treats the tail as a counted string reads that "
                 "byte and nothing else (SPEC.md 96.19)"
                 % (field(second, "COUNT"), len(TYPED)))
        gotset = field(second, "SET") or ""
        print("dosargs: the program's environment is %r" % gotset)
        if ENVVAR not in gotset.split("|"):
            fail("the environment does not carry %r - it is %r. The row was "
                 "typed on the Environment page and should reach the block "
                 "verbatim (SPEC.md 96.20); an empty set means the page never "
                 "took the keys, and a set WITHOUT it but with BLASTER= means "
                 "the emit loop skipped it" % (ENVVAR, gotset))
        if not gotset.endswith("|"):
            fail("the environment's last variable has no terminator: %r"
                 % gotset)
        print("dosargs: ...and the row typed on the Environment page is in it")

        if field(second, "TERM") != str(len(TYPED)):
            fail("the 0Dh is at offset %s for a %d-character tail. A program "
                 "that PARSES its arguments scans for that byte, and one in "
                 "the wrong place sends it into the FCB area"
                 % (field(second, "TERM"), len(TYPED)))
        print("dosargs: both framings agree - count %s, terminator at %s"
              % (field(second, "COUNT"), field(second, "TERM")))

        m.type_text("x")

    print("dosargs: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
