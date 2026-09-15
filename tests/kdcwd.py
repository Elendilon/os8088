#!/usr/bin/env python3
"""WHERE A LAUNCHED PROGRAM STANDS, under BOTH arms of one machine (96.44.9).

    make kdostest && python3 tests/kdcwd.py

A program launched out of a subdirectory stands IN it, and everything it opens
by a bare name resolves there, and the path the environment hands it says where
it came from.  Four facts; the windowed box has always got all four right, and
`kern_dos` got the fourth wrong from the day it existed.

**THE POINT IS THE PAIR.**  The DOS core is ONE object joined to two back ends
(96.44), so a row that runs either one alone cannot see a disagreement between
them - and the disagreement is the whole class of defect the split introduces.
This boots one machine, runs CWDHERE.COM windowed, then runs the SAME program
on the SAME disk with the whole machine under it, and requires the two answers
to be identical.

WHAT IT CAUGHT.  `OSAPI_FILE_PATH` is an X cell, so `api_x` puts the caller's
DS in ES and the core's callers pass a bare DS offset; `kern_dos` bound the
door with a far call straight at `dsk_path_x`, which writes to ES:DI and never
reloads ES.  The environment's program path came out as `B:` - the drive and
nothing after it - so a program that builds its data path off its own path
looked in the volume root.  Prince of Persia is the field report: under the
whole-machine arm it answered *"Unable to find necessary files. Please start
program from the default drive and directory."*

VERIFIED TO FAIL: taking the `push es`/`pop es` back out of `dos_k_path` in
kerndos/kdback.inc takes step 2 red with MYPATH `B:` against the window's
`B:\\SUB\\CWDHERE.COM`.  The other three rows stay green, which is why they are
printed too - a row that only checked the CWD would have called this fixed.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosmap                                                  # noqa: E402
import os88marty                                               # noqa: E402
import os88mouse                                               # noqa: E402
import os88ui                                                  # noqa: E402
from kdhand import rec, RD_SEL, RD_PITCH, wait_text            # noqa: E402

MACH = "os8088_5150_herc_sb_720_gla"
SYS = "build/kdos720.img"
APPS = "build/cwdsub.img"
PROG = "B:/SUB/CWDHERE.COM"
WHOLE = 2                            # the Memory page's third arm
# os88ui.inc's alert geometry, mirrored for tests/kdhand.py's reason.
A_BW, A_BG, A_BH, A_BTNY, TITLE_H = 72, 12, 13, 46, 18

WANT = {
    "DRIVE": "B:",
    "DIR": "\\SUB",
    "BARE": "opened HERE.TXT beside me",
    "MYPATH": "B:\\SUB\\CWDHERE.COM",
}


def fail(msg):
    print("kdcwd: FAIL: %s" % msg)
    sys.exit(1)


def answers(rows, arm):
    """The probe's four lines, as {key: value}."""
    got = {}
    for r in rows:
        for k in WANT:
            if r.strip().startswith(k + " "):
                got[k] = r.strip()[len(k):].strip()
    miss = [k for k in WANT if k not in got]
    if miss:
        fail("%s: the probe printed no %s line. What was on the screen:\n%s"
             % (arm, "/".join(miss), "\n".join("   | " + r.rstrip()
                                               for r in rows if r.strip())))
    return got


def main():
    with os88ui.boot(SYS, apps=APPS, machine=MACH) as ui:
        m = ui.m
        ui.path(PROG)                # the association RUNS it, windowed
        dm = dosmap.package(*dosmap.KDBOX)
        mo = os88mouse.Mouse(marty=m)

        # --- 1: the WINDOW's own DOS ----------------------------------------
        win = answers(wait_text(m, "READY", secs=180,
                                what="the windowed run"), "windowed")
        for k in ("DRIVE", "DIR", "BARE", "MYPATH"):
            print("kdcwd: windowed %-7s %s" % (k, win[k]))
        for k, v in WANT.items():
            if win[k] != v:
                fail("windowed: %s is %r and should be %r - the WINDOW's own "
                     "answer is wrong, so this is not a seam defect at all "
                     "(SPEC.md 96.6.1)" % (k, win[k], v))
        m.type_text("x")
        os88marty.settle(m)

        # **RE-READ THE INSTANCE**: the windowed run claimed the DOS arena, so
        # the segment read before it is stale and every rect below would come
        # back in the tens of thousands.
        pseg = dosmap.instance(m)

        # --- 2: ...and the same program with the whole machine under it -----
        mo.click(*dosmap.centre(m, pseg, dm, "dos_erect"))
        os88marty.settle(m)
        x1, y1, x2, _ = dosmap.rect(m, pseg, dm, "dos_mrad")
        pitch = rec(m, pseg, dm, RD_PITCH)
        mo.click((x1 + x2) // 2, y1 + WHOLE * pitch + pitch // 2)
        os88marty.settle(m)
        sel = rec(m, pseg, dm, RD_SEL)
        if sel != WHOLE:
            fail("clicking the third arm left OS88UI_RD_SEL at %d, so the run "
                 "below would be the WINDOWED one again and the comparison "
                 "would be of a thing with itself" % sel)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_trect"))
        os88marty.settle(m)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_rrect"))
        os88marty.settle(m)

        # the handover's confirmation, found through the WM rather than through
        # the package: the launch moves the instance under us.
        t0 = time.time()
        while time.time() - t0 < 90:
            f = ui.front()
            if f is not None and f.visible and f.w <= 400 and f.h <= 200:
                row = 2 * (A_BW + A_BG) - A_BG
                left = f.x + (f.w - row) // 2 + (A_BW + A_BG)
                mo.click(left + A_BW // 2,
                         f.y + TITLE_H + A_BTNY + A_BH // 2)
                break
            time.sleep(1.0)
        else:
            fail("the handover was never asked for - `Open windows are lost. "
                 "Proceed?` is once per LAUNCH (SPEC.md 96.42) and without it "
                 "the run below is not under kern_dos")

        kd = answers(wait_text(m, "READY", secs=240,
                               what="the run under kern_dos"), "kern_dos")
        for k in ("DRIVE", "DIR", "BARE", "MYPATH"):
            print("kdcwd: kern_dos %-7s %s" % (k, kd[k]))

        # --- 3: the two arms are the same program on the same disk ----------
        bad = [k for k in WANT if kd[k] != win[k]]
        if bad:
            fail("the two arms disagree about %s: the window says %s and "
                 "kern_dos says %s. The DOS core is ONE object joined to two "
                 "back ends (SPEC.md 96.44), so every one of these is a fact "
                 "about the program and not about which arm ran it"
                 % (", ".join(bad),
                    " / ".join("%s=%r" % (k, win[k]) for k in bad),
                    " / ".join("%s=%r" % (k, kd[k]) for k in bad)))
        print("kdcwd: both arms agree on all four - drive, directory, a "
              "bare-name open and the environment's own path")


if __name__ == "__main__":
    main()
