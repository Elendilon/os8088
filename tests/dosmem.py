#!/usr/bin/env python3
"""The Memory page's three arms (SPEC.md 96.36, 96.25, 47).

The choice of how much of the machine a DOS program gets used to be a CHECK
BOX, which holds two answers.  There are three, and the third - take os8088
itself as well (docs/plans/KERN-DOS-PLAN.md) - is greyed because nothing
behind it is built yet.

WHAT IT WOULD CATCH, and every one was seen FAILING on the way to writing it
(docs/WRITING-TESTS.md 1):

  - the record filled in the wrong ORDER      -> dos_mem_whole answers in SI
    (dos_mrad_place's own bug, twice)            and so does the record
                                                 pointer: the group drew at
                                                 screen 0,0 over the menu bar
                                                 and the rect stayed 0,0,0,0
  - [dos_keepc] not being OS88UI_RD_SEL        -> the page shows one arm and
    (a second copy of the pick)                  dos_run sizes for another
  - the DEFAULT arm flipping polarity          -> the check box's ON byte was
    (DOS_MEM_KEEP is 0, the ticked box was 1)    1 for "keep" and the radio's
                                                 arm 0 is 0, so a copied test
                                                 keeps the cache exactly when
                                                 it should take it
  - the third arm not greyed at all            -> a control that is offered
                                                 and then does nothing
  - the third arm greyed and still PICKABLE    -> os88ui_radhit reading the
                                                 DIS bits wrongly
  - dos_mem_fix not demoting                   -> a .LNK written on a machine
                                                 that has the feature sizes
                                                 the arena against a level
                                                 nothing implements

IT RUNS ON A 1bpp ADAPTER ON PURPOSE (SPEC.md 47.2): grey rounds to black in
text there, so a greyed label is a CHECKERBOARD and a live one is solid - the
one adapter class where "is this row disabled" is a pixel fact rather than a
colour.  On VGA both are legible and the assertion would be about CDGRAY.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosmap                                                  # noqa: E402
import os88marty                                               # noqa: E402
import os88mouse                                               # noqa: E402
import os88ui                                                  # noqa: E402

SYS = "build/os8088-360.img"
APPS = "build/apps360.img"
MACH = "os8088_5150_cga_gla"

# os88ui.inc's record, mirrored here for the same reason the test carries no
# layout: these are the SDK's offsets and the box does not own them.
RD_RECT, RD_ITEMS, RD_N, RD_SEL, RD_PITCH, RD_DIS = 0, 8, 10, 12, 14, 16
KEEP, DUMP, WHOLE, NARM = 0, 1, 2, 3


def fail(msg):
    print("dosmem: FAIL: %s" % msg)
    sys.exit(1)


def u16(m, at):
    return int.from_bytes(m.read(at, 2), "little")


def rec(m, pseg, dm, off):
    return u16(m, (pseg << 4) + dm["dos_mrad"] + off)


def arm_centre(m, pseg, dm, i):
    """The middle of row i, out of the GUEST's own rect and pitch."""
    x1, y1, x2, _ = dosmap.rect(m, pseg, dm, "dos_mrad")
    pitch = rec(m, pseg, dm, RD_PITCH)
    return (x1 + x2) // 2, y1 + i * pitch + pitch // 2


def band(m, x1, y1, x2, y2):
    """The pixels of a rect, as a flat tuple - for 'did anything change'."""
    return tuple(os88marty.crop_rgb(m, x1, y1, x2 - x1 + 1, y2 - y1 + 1))


def dithered(m, x, y, w, h):
    """Is this run of text a CHECKERBOARD? (SPEC.md 47 rule 3)

    A solid glyph has runs of set pixels side by side; font_ink's disabled
    mask leaves no two horizontally adjacent ones at all, because the stipple
    is laid on in 1-pixel columns.  So the question is answered by counting
    ADJACENT PAIRS rather than by counting ink, which would only say how much
    text there is.
    """
    px = os88marty.crop_rgb(m, x, y, w, h)
    pairs = ink = 0
    for row in range(h):
        prev = False
        for col in range(w):
            i = (row * w + col) * 3
            dark = px[i] < 128
            ink += dark
            pairs += dark and prev
            prev = dark
    return ink, pairs


def main():
    for p in (SYS, APPS):
        if not os.path.exists(p):
            fail("%s is missing - `make` builds it" % p)

    with os88ui.boot(SYS, apps=APPS, machine=MACH) as ui:
        m = ui.m
        if not ui.path("A:/APPS/DOS.O88"):
            fail("could not open the DOS box")
        os88marty.settle(m)
        dm = dosmap.package()
        pseg = dosmap.instance(m)
        mo = os88mouse.Mouse(marty=m)

        # --- 1: on to the Setup page -----------------------------------------
        mo.click(*dosmap.centre(m, pseg, dm, "dos_erect"))
        os88marty.settle(m)
        rect = dosmap.rect(m, pseg, dm, "dos_mrad")
        if rect == [0, 0, 0, 0]:
            fail("the radio's rect is still zero after the page painted - "
                 "dos_mrad_place never ran, or it wrote somewhere else "
                 "(SPEC.md 96.36)")
        print("dosmem: the group is at %r, pitch %d"
              % (rect, rec(m, pseg, dm, RD_PITCH)))

        # --- 2: the record says what the page is ------------------------------
        if rec(m, pseg, dm, RD_N) != NARM:
            fail("OS88UI_RD_N is %d and the page has %d arms"
                 % (rec(m, pseg, dm, RD_N), NARM))
        if rec(m, pseg, dm, RD_SEL) != KEEP:
            fail("the default arm is %d and DOS_MEM_KEEP is %d - a fresh box "
                 "keeps the disk cache (SPEC.md 96.25)"
                 % (rec(m, pseg, dm, RD_SEL), KEEP))
        dis = rec(m, pseg, dm, RD_DIS)
        if not dis & (1 << WHOLE):
            fail("OS88UI_RD_DIS is 0x%04X - the third arm is NOT greyed, and "
                 "nothing behind it is built (SPEC.md 96.36.1)" % dis)
        if dis & 0x8000:
            fail("OS88UI_RD_DIS bit 15 is set - the WHOLE group is greyed, so "
                 "the page offers no choice at all")
        print("dosmem: N=%d SEL=%d DIS=0x%04X - arm %d greyed, the group live"
              % (NARM, KEEP, dis, WHOLE))

        # --- 3: the greyed row is DITHERED and its live neighbour is not ------
        # SPEC.md 47 rules 2 and 3, asserted in pixels because that is the only
        # thing that says the two halves of the control agree.
        x1, y1, _, _ = rect
        pitch = rec(m, pseg, dm, RD_PITCH)
        lx = x1 + 12 + 6                     # OS88UI_RDBOX + OS88UI_RDGAP
        for arm, want in ((DUMP, False), (WHOLE, True)):
            ink, pairs = dithered(m, lx, y1 + arm * pitch + 4, 23 * 8, 8)
            if ink < 40:
                fail("arm %d's label has %d dark pixels - it did not draw at "
                     "all" % (arm, ink))
            got = pairs * 8 < ink         # a stipple leaves almost no pairs
            if got != want:
                fail("arm %d: %d dark pixels in %d adjacent pairs, which reads "
                     "as %s. SPEC.md 47 rule 2 - the label greys with the "
                     "ring, or the two halves of the control disagree"
                     % (arm, ink, pairs, "dithered" if got else "solid"))
            print("dosmem: arm %d label %d px / %d pairs -> %s"
                  % (arm, ink, pairs, "dithered" if got else "solid"))

        # --- 4: the reason is on the glass, in the same pen -------------------
        ink, pairs = dithered(m, lx, y1 + 48 + 2, 21 * 8, 8)
        if ink < 40:
            fail("nothing is drawn under the greyed arm - SPEC.md 47 rule 3 "
                 "wants the words that say WHY NOT")
        if pairs * 8 >= ink:
            fail("the reason under the greyed arm is SOLID: %d dark pixels in "
                 "%d pairs. It sits at the labels' own indent, so drawn live "
                 "it reads as a fourth arm that works (SPEC.md 96.36.1)"
                 % (ink, pairs))
        print("dosmem: the reason is on the glass and greyed with its row")

        # --- 5: a press on a LIVE arm moves the pick and only two dots --------
        # **PARK THE POINTER FIRST.** crop_rgb reads the card's RENDERED
        # framebuffer, so the arrow is in it: a capture taken before the move
        # and one taken after differ by the arrow wherever the control is, and
        # step 6's whole assertion is that nothing differs.
        mo.to(*arm_centre(m, pseg, dm, DUMP))
        os88marty.settle(m)
        before = band(m, *rect)
        mo.click(*arm_centre(m, pseg, dm, DUMP))
        os88marty.settle(m)
        if rec(m, pseg, dm, RD_SEL) != DUMP:
            fail("a press on arm %d left the pick at %d"
                 % (DUMP, rec(m, pseg, dm, RD_SEL)))
        after = band(m, *rect)
        if before == after:
            fail("the pick moved and NOTHING was redrawn - os88ui_radhit owes "
                 "the two dots that changed (SPEC.md 13.17.4)")
        print("dosmem: arm %d picked, and the group redrew" % DUMP)

        # --- 6: a press on the GREYED arm does nothing at all ----------------
        mo.to(*arm_centre(m, pseg, dm, WHOLE))
        os88marty.settle(m)
        before = band(m, *rect)
        mo.click(*arm_centre(m, pseg, dm, WHOLE))
        os88marty.settle(m)
        if rec(m, pseg, dm, RD_SEL) != DUMP:
            fail("a press on the GREYED arm moved the pick to %d. It is "
                 "greyed because the machine cannot do it (SPEC.md 96.36.1)"
                 % rec(m, pseg, dm, RD_SEL))
        if band(m, *rect) != before:
            fail("a press on the greyed arm redrew something. SPEC.md 47 rule "
                 "6: greyed, so say nothing more")
        print("dosmem: the greyed arm swallowed its press and drew nothing")

        # --- 7: ...and back --------------------------------------------------
        mo.click(*arm_centre(m, pseg, dm, KEEP))
        os88marty.settle(m)
        if rec(m, pseg, dm, RD_SEL) != KEEP:
            fail("a press on arm %d left the pick at %d"
                 % (KEEP, rec(m, pseg, dm, RD_SEL)))
        print("dosmem: ...and back to arm %d" % KEEP)

        # --- 8: CONSUMER THREE - a pick the machine cannot honour ------------
        # A .LNK another machine wrote can carry DOS_MEM_WHOLE, and a greyed
        # control refuses a CLICK and not a FILE (SPEC.md 96.36.1).  Poking the
        # word is that link with the file system left out of it; LEAVING THE
        # PAGE is what commits the block, and dos_mem_take is where the pick
        # meets the machine.  It asserts the demotion and not the arithmetic
        # that follows it, which is dosarena's subject.
        at = (pseg << 4) + dm["dos_keepc"]
        m.write(at, bytes((WHOLE, 0)))
        if u16(m, at) != WHOLE:
            fail("could not poke the pick")
        mo.click(*dosmap.centre(m, pseg, dm, "dos_trect"))       # Return
        os88marty.settle(m)
        got = u16(m, at)
        if got != DUMP:
            fail("leaving the page with the pick at DOS_MEM_WHOLE left it at "
                 "%d. dos_mem_fix demotes to the arm below, so the page comes "
                 "back showing what the machine will really do rather than an "
                 "arm it is quietly ignoring (SPEC.md 96.36.1)" % got)
        print("dosmem: leaving the page demoted an arm this build cannot do")

        # ...and the CONTROL agrees with it, which is the point of the pick
        # living in the record rather than beside it (SPEC.md 96.36).
        mo.click(*dosmap.centre(m, pseg, dm, "dos_erect"))
        os88marty.settle(m)
        if rec(m, pseg, dm, RD_SEL) != DUMP:
            fail("the record says arm %d after the demotion wrote %d - "
                 "[dos_keepc] is OS88UI_RD_SEL's low byte and there is not "
                 "supposed to be a second copy" % (rec(m, pseg, dm, RD_SEL),
                                                   DUMP))
        print("dosmem: ...and the control came back showing it")

        wd, ht, data = m.fbuf()
        os88marty.write_png_rgb("build/dosmem.png", wd, ht, data)
        print("dosmem: build/dosmem.png written")

    print("dosmem: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
