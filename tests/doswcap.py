#!/usr/bin/env python3
"""doswcap - a program that writes the screen ITSELF, live in a DOS window
(SPEC.md 96.54.5, 96.54.6; docs/plans/DOS-WINDOWED-PLAN.md waves 4 and 6).

Two machines, because the two halves are about two kinds of machine.

On `os8088_5150_both_gla_mono` - a Hercules desktop with a CGA beside it, the
owner's 5150 - the CGA's B800 is RAM nobody shows, so a windowed run CAPTURES
it (DVWC_SEG):
  1  tests/dostrap/dwdirect.asm (Works' shape: AH=0Fh, then direct writes)
     runs in the window: [dvw_cmode] = DVWC_SEG on B800, its lines reach the
     band WHILE IT RUNS, and not one of them is in the desktop's own
     framebuffer at B000
  2  `q` ends it with exit code 113

On `os8088_5150_herc_gla` - a lone Hercules, which MartyPC decodes at B800
as well as B000 - the capture is REFUSED (a capture there would read and let
the program write the desktop's own pixels), and a TopView-aware program is
the one that still works:
  3  tests/dostrap/dwtv.asm asks int 10h AH=FEh and is given the window's own
     buffer (our segment); [dvw_cseg] is 0 - no capture was taken
  4  its lines reach the band while it runs - the even ones with no AH=FFh,
     found by the row sums, the odd ones marked by AH=FFh

**Break it on purpose** (docs/WRITING-TESTS.md 1): with dvw_cdetect forced to
answer CF=1, leg 1 reads [dvw_cmode] 0 and no DWDIRECT line in the band; with
the alias test removed, leg 3 reads a capture on the lone Hercules.
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
DVWC_TV, DVWC_SEG = 1, 2


def fail(msg):
    print("doswcap: FAIL: %s" % msg)
    sys.exit(1)


class Dos(object):
    def __init__(self, m):
        self.m = m
        self.dm = dosmap.package()

    def seg(self):
        return int(dosmap.instance(self.m))

    def base(self):
        return dosmap.lin(self.m, dosmap.instance(self.m))

    def b(self, name):
        return self.m.read(self.base() + self.dm[name], 1)[0]

    def w(self, name):
        return int.from_bytes(self.m.read(self.base() + self.dm[name], 2),
                              "little")

    def rows(self):
        scr = self.m.read(self.base() + self.dm["con_scr"], 4000)
        return ["".join(chr(scr[r * 160 + i]) if 32 <= scr[r * 160 + i] < 127
                        else " " for i in range(0, 160, 2)).rstrip()
                for r in range(25)]

    def pword(self, off):
        psp = self.w("dos_ldpsp")
        return int.from_bytes(self.m.read(psp * 16 + off, 2), "little")


def until(m, cond, what, limit):
    try:
        os88marty.until(m, lambda _m: cond(), what, poll=0.2, limit=limit)
        return True
    except os88marty.MartyError:
        return False


def build(tmp, names):
    coms = []
    for n in names:
        com = os.path.join(tmp, n.upper() + ".COM")
        subprocess.run(["nasm", "-f", "bin", "-w+error", "-o", com,
                        os.path.join(ROOT, "tests", "dostrap", n + ".asm")],
                       check=True)
        coms.append(com)
    disk = os.path.join(tmp, "dwcap360.img")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "os88disk.py"),
                    "-o", disk, "--size", "360"] + coms, check=True,
                   stdout=subprocess.DEVNULL)
    return disk


def live_lines(m, dos, tag, want):
    """`want` of the probe's lines in the band, with the program still on."""
    got = lambda: [r for r in dos.rows() if r.startswith(tag)]
    if not until(m, lambda: len(got()) >= want, "%d %s lines" % (want, tag),
                 30):
        fail("the band holds %d %s lines (want %d) with the program "
             "running: %r" % (len(got()), tag, want, dos.rows()[:6]))
    if not dos.b("dvw_run"):
        fail("the program ended before its lines were read - this says "
             "nothing about LIVE")
    return got()


def main():
    if not os.path.exists(SYS):
        fail("%s is missing - a plain `make` builds it" % SYS)
    tmp = tempfile.mkdtemp(prefix="doswcap")
    try:
        disk = build(tmp, ["dwdirect", "dwtv"])
        capture(disk)
        topview(disk)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("doswcap: ok")


def capture(disk):
    with os88ui.boot(SYS, apps=disk,
                     machine="os8088_5150_both_gla_mono") as ui:
        m = ui.m
        if not ui.path("B:/DWDIRECT.COM"):
            fail("could not launch DWDIRECT.COM")
        dos = Dos(m)
        os88marty.pace(m, 2)
        m.type_text("q")
        if not until(m, lambda: not dos.b("dos_inbr"), "the bracket down",
                     40):
            fail("DWDIRECT's bracketed run never came down after `q`")
        os88marty.settle(m)
        ui.raise_window(ui.window("DOS"))
        ui.menu_pick("Program", "Run in Window")
        if not until(m, lambda: dos.b("dvw_run") == 1, "the windowed run", 20):
            fail("Run in Window put nothing on the worker")

        # --- 1: captured, live, and not on the desktop ----------------------
        if dos.b("dvw_cmode") != DVWC_SEG or dos.w("dvw_cseg") != 0xB800:
            fail("a Hercules desktop with a CGA beside it should capture B800 "
                 "([dvw_cmode] %d, [dvw_cseg] %04X)"
                 % (dos.b("dvw_cmode"), dos.w("dvw_cseg")))
        got = live_lines(m, dos, "DWDIRECT ", 4)
        hb = m.read(0xB0000, 0x8000)
        if b"D\x07W\x07D\x07I\x07R" in hb:
            fail("the program's text is in B000 - the desktop's own "
                 "framebuffer")
        print("doswcap: 1 B800 captured: %d DWDIRECT lines in the band while "
              "it runs, none on the desktop" % len(got))

        # --- 2: it ends --------------------------------------------------------
        m.type_text("q")
        if not until(m, lambda: dos.b("dvw_run") == 0, "its end", 20):
            fail("`q` did not end the captured program")
        os88marty.settle(m)
        if not any("exit code 113" in r for r in dos.rows()):
            fail("no `exit code 113` in the band: %r" % dos.rows()[-4:])
        print("doswcap: 2 `q` ended it, exit code 113")


def topview(disk):
    with os88ui.boot(SYS, apps=disk, machine="os8088_5150_herc_gla") as ui:
        m = ui.m
        if not ui.path("B:/DWTV.COM"):
            fail("could not launch DWTV.COM")
        dos = Dos(m)
        os88marty.pace(m, 2)
        m.type_text("q")
        if not until(m, lambda: not dos.b("dos_inbr"), "the bracket down",
                     40):
            fail("DWTV's bracketed run never came down after `q`")
        os88marty.settle(m)
        ui.raise_window(ui.window("DOS"))
        ui.menu_pick("Program", "Run in Window")
        if not until(m, lambda: dos.b("dvw_run") == 1, "the windowed run", 20):
            fail("Run in Window put nothing on the worker")
        os88marty.pace(m, 0.5)

        # --- 3: no capture here; TopView answers our buffer -----------------
        if dos.w("dvw_cseg"):
            fail("a capture was taken on a lone Hercules, whose B800 is the "
                 "desktop's B000 again ([dvw_cseg] %04X)" % dos.w("dvw_cseg"))
        if dos.b("dvw_cmode") != DVWC_TV:
            fail("AH=FEh in a window should set DVWC_TV; [dvw_cmode] is %d"
                 % dos.b("dvw_cmode"))
        if dos.pword(0x105) != dos.seg() or \
                dos.pword(0x107) != dos.dm["con_scr"]:
            fail("AH=FEh answered %04X:%04X; the window's buffer is %04X:%04X"
                 % (dos.pword(0x105), dos.pword(0x107), dos.seg(),
                    dos.dm["con_scr"]))
        print("doswcap: 3 no capture on a lone Hercules; AH=FEh answered the "
              "window's own buffer")

        # --- 4: its lines, both kinds -------------------------------------------
        got = live_lines(m, dos, "DWTV ", 4)
        letters = set(r[5] for r in got if len(r) > 5)
        even = [c for c in letters if (ord(c) - ord("A")) % 2 == 0]
        odd = [c for c in letters if (ord(c) - ord("A")) % 2 == 1]
        if not even or not odd:
            fail("the band holds DWTV lines %r - want both the AH=FFh ones "
                 "(odd) and the summed ones (even)" % sorted(letters))
        m.type_text("q")
        if not until(m, lambda: dos.b("dvw_run") == 0, "its end", 20):
            fail("`q` did not end the TopView program")
        print("doswcap: 4 its lines reached the band, marked (%s) and summed "
              "(%s)" % ("".join(sorted(odd)), "".join(sorted(even))))


if __name__ == "__main__":
    main()
