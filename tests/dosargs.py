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
import os88marty                                               # noqa: E402
import os88mouse                                               # noqa: E402
import os88geom                                                # noqa: E402
import os88ui                                                  # noqa: E402

SYS = "build/os8088-360.img"
ARGS = "build/dosargs360.img"
TYPED = "/M P:220"                   # ...what a user would actually type
WANTPATH = "\\BIN\\DOSARGS.COM"
ENVVAR = "SOUND=SB"              # ...typed on the Environment page
DOS_FLDW = 256                   # apps/dos/dos.asm's field and button metrics
DOS_BTNW = 104
DOS_BTNY = 90
DOS_EROWY = 24
DOS_FLDY = 64                    # apps/dos/dos.asm's arguments box, from the
                                 # content top - mirrored here because a test
                                 # that clicks a remembered pixel is the thing
                                 # docs/WRITING-TESTS.md warns about, and this
                                 # is the nearest a package-local constant gets
R_NCELL, R_NKEY = 6, 8           # dos.asm's counters, past DOS_B_CTOP/LNV/LNL


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
        # The band is LEFT OF THE DISK WINDOW TOO (x 20..90), because that one
        # is white and would answer for the desktop.
        wd, ht, data = m.fbuf()

        def lit(x, y):
            return data[(y * wd + x) * 3] < 128

        rows = [y for y in range(w.y + 24, min(w.y + w.h - 8, ht - 1))]
        ink = sum(1 for y in rows for x in range(20, 90) if lit(x, y))
        frac = ink / float(len(rows) * 70)
        if not 0.35 <= frac <= 0.65:
            fail("the desktop to the LEFT of the window is %.0f%% ink over the "
                 "window's own rows, and SPEC.md 63's dither is 50. A white "
                 "band there is a fill whose x1 was clobbered before it ran "
                 "(SPEC.md 96.19.5)" % (frac * 100))
        print("dosargs: the desktop left of the window is %.0f%% ink over its "
              "rows - the fill stayed inside (SPEC.md 96.19.5)" % (frac * 100))

        dw = ui.disk_window()
        if dw:
            ui.close(dw)
        ui.move_window(w, 300, 40)
        os88marty.settle(m)
        w = ui.window("DOS")

        # --- 3: click the field and type -------------------------------------
        # The field is at content+8, content_top+80, 256x13 (DOS_FLD*). The
        # click lands in its middle rather than at an edge, because an edge
        # click is os88line_hit's boundary and this row is not about that.
        cx, cy = w.x + 8 + 100, w.y + 16 + DOS_FLDY + 6
        os88mouse.Mouse(marty=m).click(cx, cy)
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
        base = pkg_base(m)
        cells = u16(m, base + R_NCELL)
        keys = u16(m, base + R_NKEY)
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

        # --- 3b: THE ENVIRONMENT PAGE (SPEC.md 96.20) ------------------------
        # The Environment button, then row 0, then Done. Every coordinate is
        # apps/dos/dos.asm's own constant measured from the CONTENT origin,
        # not a pixel somebody remembered - which is docs/WRITING-TESTS.md's
        # rule and the reason these are named at the top of this file.
        ctop = w.y + os88geom.TITLE_H   # ...IMPORTED, and t_mirror is why:
                                       # typing 16 here passed only because
                                       # the field is 13px tall and 2px of
                                       # error still lands inside it
        mo = os88mouse.Mouse(marty=m)
        mo.click(w.x + 8 + DOS_FLDW - DOS_BTNW // 2, ctop + DOS_BTNY + 7)
        os88marty.settle(m)
        mo.click(w.x + 8 + 60, ctop + DOS_EROWY + 6)
        os88marty.settle(m)
        for ch in ENVVAR:
            m.type_text(ch)
        os88marty.settle(m)
        mo.click(w.x + 8 + DOS_FLDW - DOS_BTNW // 2, ctop + DOS_BTNY + 7)
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
