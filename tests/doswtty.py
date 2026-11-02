#!/usr/bin/env python3
"""doswtty - how fast a program PRINTS in a DOS window (SPEC.md 96.54.12).

tests/dostrap/dwtty.asm puts text on the screen three ways, each started by a
key and counted into PSP:0103h when it is done, so guest seconds (MartyPC's
cycle counter, 4.77 MHz) from the key to the count are its time:

    9   100 lines through INT 21h AH=09h - a command-line utility, a scroll
        a line
    e   the same lines through INT 10h AH=0Eh, the teletype a character at
        a time
    b   20 rows of 66 characters as a compiled BASIC PRINT puts them:
        AH=02h, AH=09h with CX = 1, AH=02h - three calls a character

Each leg runs in the bracket (the whole machine, the ROM's own teletype onto
the Hercules's text page) and then in a window, and the row holds the
window's speed as a share of the bracket's at a floor per leg.

MEASURED on a Hercules 5150 (os8088_5150_herc_gla), before and after 96.54.12
(the 'before' is the tree it was written on, 3241006c):

    leg   before   after
    9      46%      ~90%
    e      49%      ~95%
    b      29%      ~93%

**Break it on purpose** (docs/WRITING-TESTS.md 1): every leg reads under its
floor on the tree before 96.54.12 - three marks a character, a mark and two
host crossings per cursor move, and the band scrolled once a line.
"""

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosmap                                                  # noqa: E402
import os88marty                                               # noqa: E402
import os88ui                                                  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SYS = os.path.join(ROOT, "build", "os8088-360.img")
PROBE = os.path.join(ROOT, "tests", "dostrap", "dwtty.asm")
HZ = 4772727.0
MACHINE = os.environ.get("DOSWTTY_MACHINE", "os8088_5150_herc_gla")
LEGS = (("9", "INT 21h AH=09h", 75.0),
        ("e", "INT 10h AH=0Eh", 75.0),
        ("b", "AH=02h/09h/02h", 70.0))
LIMIT = 120.0                       # guest seconds a leg may take at all


def fail(msg):
    print("doswtty: FAIL: %s" % msg)
    sys.exit(1)


def main():
    if not os.path.exists(SYS):
        fail("%s is missing - a plain `make` builds it" % SYS)
    tmp = tempfile.mkdtemp(prefix="doswtty")
    try:
        com = os.path.join(tmp, "DWTTY.COM")
        subprocess.run(["nasm", "-f", "bin", "-w+error", "-o", com, PROBE],
                       check=True)
        disk = os.path.join(tmp, "dwtty360.img")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools",
                                                     "os88disk.py"),
                        "-o", disk, "--size", "360", com], check=True,
                       stdout=subprocess.DEVNULL)
        run(disk)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("doswtty: ok")


def run(disk):
    with os88ui.boot(SYS, apps=disk, machine=MACHINE) as ui:
        m = ui.m
        dm = dosmap.package()

        def cyc():
            return int(m.status()["cycles"])

        def done():
            base = dosmap.lin(m, dosmap.instance(m))
            psp = int.from_bytes(m.read(base + dm["dos_ldpsp"], 2), "little")
            if not psp or m.read(psp * 16 + 0x100, 3) != b"\xeb\x03\x90":
                return None
            return int.from_bytes(m.read(psp * 16 + 0x103, 2), "little")

        def leg(key, n):
            os88marty.pace(m, 1)
            c0 = cyc()
            m.type_text(key)
            while done() != n + 1:
                if (cyc() - c0) / HZ > LIMIT:
                    fail("leg %r never finished (%s guest s)" % (key, LIMIT))
                os88marty.guest_sleep(m, 0.05)
            return (cyc() - c0) / HZ

        def legs(tag):
            n = None
            for _ in range(200):
                n = done()
                if n == 0:
                    break
                os88marty.guest_sleep(m, 0.1)
            if n != 0:
                fail("%s: DWTTY.COM is not waiting for a key" % tag)
            return [leg(k, i) for i, (k, _, _) in enumerate(LEGS)]

        if not ui.path("B:/DWTTY.COM"):
            fail("could not launch DWTTY.COM")
        full = legs("bracket")
        m.type_text("q")
        os88marty.pace(m, 3)
        os88marty.settle(m)
        ui.raise_window(ui.window("DOS"))
        dosmap.run_in_window(ui)
        win = legs("window")
        m.type_text("q")
        bad = []
        for (k, what, floor), f, w in zip(LEGS, full, win):
            pct = 100.0 * f / w
            print("doswtty: %-15s bracket %6.2f s, window %6.2f s: %5.1f%% "
                  "(floor %.0f%%)" % (what, f, w, pct, floor))
            if pct < floor:
                bad.append("%s at %.1f%%" % (what, pct))
        if bad:
            fail("the window prints at under its floor: %s - the per-"
                 "character marks or the band's scroll have got dearer "
                 "(SPEC.md 96.54.12)" % ", ".join(bad))


if __name__ == "__main__":
    main()
