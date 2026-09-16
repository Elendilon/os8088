#!/usr/bin/env python3
"""THE MEMORY PAGE'S FIGURE IS THE FIGURE THE PROGRAM GETS (SPEC.md 96.36.3).

    python3 tests/dosram.py [--machine os8088_5150_cga_gla]

`For the program: ~NNNNN K` is one number now, live, that every control under
it moves.  Two of its terms can be checked against the machine and the third
cannot be checked against anything else at all:

  1  **ARM 0 IS EXACT** - the base is `OSAPI_MEM_COMPACT`'s what-if at the
     floor `dos_run` will really set, so a launch on that arm must hand out
     what the row promised.  That half is `tests/dirwshed.py`'s and is not
     re-driven here;
  2  **THE DRIVER BOXES MOVE IT BY WHAT THEY SAY** (96.36.7).  The figure in
     a box's label and the figure the total moves by are ONE word read once,
     so clearing a live box must move the row by exactly what its own label
     printed.  A box that is greyed says 0 and must move it by nothing;
  3  **ARM 1 CANNOT BE ASKED ANYTHING** (96.36.3).  The machine it describes
     has no kernel in it, so every term is a constant this build knows -
     `DOS_KDKB` most of all, which is deliberately NOT gated against
     `kern_dos`'s own arithmetic because that moves with its image.  **THIS
     ROW IS THAT GATE**: put a program through arm 3 and compare what the
     page promised against what the PROGRAM says it was given.

What it would catch, and every one is a silent failure:

  - `DOS_KDKB` drifting as `kern_dos` grows      -> the page promises memory
                                                    the program does not get,
                                                    and nothing says so
  - the dial's ladder disagreeing with kern_dos  -> `DOS_CA_AUTORUN` is gated
    (96.36.6)                                       at assembly, but 32K/18K/
                                                    9K are only checked here
  - a box's label and the total disagreeing      -> two reads of
                                                    OSAPI_DRV_CLASSK where
                                                    96.36.7 says one

It needs a machine with a fixed disk for arm 3 (the session has to have
somewhere to go), and the figure it compares against is **DOSHELLO's own
`Memory to top of block`** - `int 21h AH=4Ah`'s answer for its PSP, which is
the arena `dos_build_psp` handed it.  The BDA mailbox (96.41.1) carries the
same number and was the first shape of this row: it is written by `kd_bda` at
`kd_leave`, so reading it means exiting the program AND letting the live
resume run, which is `tests/kdreturn.py`'s subject and a great deal of
machinery for a figure the program is already printing.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosmap                                                  # noqa: E402
import os88marty as M                                          # noqa: E402
import os88mouse                                               # noqa: E402
import os88ui                                                  # noqa: E402

TEMPLATE = os.path.join(ROOT, "build/martypc/run/media/hdds/default_xtide.vhd")
KERNEL = os.path.join(ROOT, "build", "kernel.sys")
VHD = os.path.join(ROOT, "build", "dosram.vhd")
FLOPPY = os.path.join(ROOT, "build", "dosram360.img")
PROG = "DOSHELLO.COM"
MACHINE = "os8088_5150_cga_hdd"

CK_ON = 10                              # OS88UI_CK_ON
HDD_CFGBIT = 1                          # kernel/driver.inc's drv_cfgbit, row 1
SLACK = 24                              # KB.  Arm 1's terms are ESTIMATES and
                                        # the row is about DRIFT, not about
                                        # arithmetic: a kern_dos that grew a
                                        # kilobyte is fine and one that grew
                                        # twenty-four is a figure nobody
                                        # re-measured


def fail(msg):
    print("dosram: FAIL: %s" % msg)
    sys.exit(1)


def fixture():
    for p in (TEMPLATE, KERNEL, os.path.join(ROOT, "build/kdos/DOS.O88")):
        if not os.path.exists(p):
            fail("%s is missing - `make kdostest` builds the DOS pieces and "
                 "`make marty` the template" % p)
    prog = os.path.join(ROOT, "build", PROG)
    subprocess.check_call(
        ["python3", "tools/os88hdd.py", "--template", TEMPLATE, "--out", VHD,
         "--kernel", KERNEL, "--vbr", "build/boothd.bin",
         "--mbr", "build/mbr.bin",
         "--file", "HIBER.DRV=build/hiber.drv",
         "--file", "CTRL.DRV=build/ctrl.drv",
         "--file", "HDD.DRV=build/hdd.drv",
         "--file", "DOS.O88=build/kdos/DOS.O88",
         "--file", "%s=%s" % (PROG, prog),
         "--file", "SYSTEM.CFG=" + syscfg()], cwd=ROOT)
    subprocess.check_call(
        ["python3", "tools/os88disk.py", "-o", FLOPPY, "--size", "360", prog],
        cwd=ROOT)


def syscfg():
    """...and the file that ASKS for HDD.DRV (SPEC.md 51.3).

    **NOTHING LOADS UNLESS SYSTEM.CFG ASKS**, and this row would pass its own
    first assertion without noticing: the machine boots off the fixed disk
    either way, because the boot partition is a DVK_BIOS row served by
    `int 13h` and not by the driver (SPEC.md 18.7.1).  So C: is there, the
    page opens, and `OSAPI_DRV_CLASSK` answers 0 for a class that really is
    holding nothing - a true answer about a machine this row did not mean to
    build.  kdreturn's own eighteen bytes: the signature, the generation, one
    DW record and the terminator, every other key ABSENT so the reader answers
    each with its default (51.5 rule 3).
    """
    p = os.path.join(ROOT, "build", "dosram-cfg-%d.bin" % os.getpid())
    with open(p, "wb") as f:
        f.write(b"O88CFG\0\0" + (3).to_bytes(2, "little")
                + b"DW" + bytes([1, 2])
                + (1 << HDD_CFGBIT).to_bytes(2, "little") + b"\0\0")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default=MACHINE)
    a = ap.parse_args()
    fixture()

    m = M.launch(None, apps=FLOPPY, machine=a.machine,
                 extra=["--mount", "hd:0:" + VHD])
    try:
        ui = os88ui.UI(m)
        ui.ready(limit=240)
        mo = os88mouse.Mouse(marty=m)
        # **OPEN THE PROGRAM, NOT THE BOX** (SPEC.md 54): a double click on a
        # .COM opens a DOS window already pointed at it, which is what every
        # kd* row does - typing a path into the arguments field opens nothing
        # and the Run below then has no program.
        if not ui.path("C:/" + PROG):
            fail("double-clicking %s on the fixed disk opened no window"
                 % PROG)
        M.settle(m)
        dm = dosmap.package()
        ps = dosmap.instance(m)

        def pb():
            return dosmap.instance(m) << 4

        def byte(n):
            return m.read(pb() + dm[n], 1)[0]

        def word(n):
            return int.from_bytes(m.read(pb() + dm[n], 2), "little")

        def rect(n):
            b = pb() + dm[n]
            return [int.from_bytes(m.read(b + 2 * i, 2), "little")
                    for i in range(4)]

        def arena():
            raw = m.read(pb() + dm["dos_marn"], 8).split(b"\0")[0]
            try:
                return int(raw.decode("latin-1").rstrip("KB").strip())
            except ValueError:
                fail("the arena row reads %r and should be digits and a KB - "
                     "the page has never been painted (SPEC.md 96.36.3)" % raw)

        # **AN ASSOCIATION OPEN OF A `.COM` RUNS IT** (SPEC.md 54), so the box
        # arrives inside its own fsx bracket with the program's output on the
        # screen - no window, no page, and every read below would be of a box
        # that has not painted one.  DOSHELLO waits on AH=08h so its screen
        # can be read; a key dismisses it and leaves the box with the program
        # still NAMED, which is exactly the state arm 3 wants.
        def inbr(_=None):
            return m.read(pb() + dm["dos_inbr"], 1)[0]

        M.until(m, inbr, "%s to be running" % PROG, limit=120.0, guest=240.0)
        m.type_text(" ")
        M.until(m, lambda _=None: not inbr(), "%s to exit" % PROG, limit=120.0)
        M.settle(m)

        mo.click(*dosmap.centre(m, ps, dm, "dos_erect"))
        M.settle(m)
        if byte("dos_page") != dm["DOS_PAGE_SET"]:
            fail("the bar's button left [dos_page] = %d and Setup is %d"
                 % (byte("dos_page"), dm["DOS_PAGE_SET"]))

        # --- 1: a LIVE box moves the row by what its own label says ----------
        # The hard disk is mounted here, so DRVC_DISK has a figure and the box
        # is live.  Clearing it is the whole of 96.36.7: what the label prints
        # and what the total moves by are one word read once.
        hdkb = word("dos_mhkb")
        print("dosram: DRVC_DISK holds %d KB, DRVC_NET %d KB"
              % (hdkb, word("dos_mnkb")))
        if not hdkb:
            fail("OSAPI_DRV_CLASSK says DRVC_DISK is holding nothing on a "
                 "machine that BOOTED off the fixed disk. This fixture's "
                 "SYSTEM.CFG asks for HDD.DRV, so either the driver is not "
                 "mounted or the slot at 0x0580 is answering wrongly "
                 "(SPEC.md 51.12)")
        before = arena()
        r = rect("dos_mhdd")
        mo.click(r[0] + 4, r[1] + 5)
        M.settle(m)
        if m.read(pb() + dm["dos_mhdd"] + CK_ON, 1)[0]:
            fail("a press inside the Hard drives box did not clear it - the "
                 "box is live on this machine (SPEC.md 96.36.7)")
        after = arena()
        if after - before != hdkb:
            fail("clearing `Hard drives (%d K)` moved the arena %d -> %d, a "
                 "step of %d. The label's figure and the total's are supposed "
                 "to be ONE word read once (SPEC.md 96.36.7, 47 rule 5)"
                 % (hdkb, before, after, after - before))
        print("dosram: clearing the box moved the row %d -> %d, exactly its "
              "own %d K" % (before, after, hdkb))
        mo.click(r[0] + 4, r[1] + 5)            # ...and back
        M.settle(m)
        if arena() != before:
            fail("re-ticking the box left the arena at %d and it was %d"
                 % (arena(), before))

        # --- 2: ARM 1's estimate, against what the machine really hands over --
        rr = rect("dos_mrad")
        pitch = int.from_bytes(m.read(pb() + dm["dos_mrad"] + 14, 2), "little")
        mo.click((rr[0] + rr[2]) // 2, rr[1] + pitch + pitch // 2)
        M.settle(m)
        if byte("dos_keepc") != 1:
            fail("clicking the Shut down the OS arm left the pick at %d"
                 % byte("dos_keepc"))
        promised = arena()
        print("dosram: the page promises ~%d K on arm 1" % promised)

        mo.click(*dosmap.centre(m, ps, dm, "dos_trect"))         # Return
        M.settle(m)
        mo.click(*dosmap.centre(m, ps, dm, "dos_rrect"))         # ...and Run

        # The handoff tears the whole machine down and `kern_dos` boots in its
        # place, so what is on the screen afterwards is the PROGRAM's own
        # output on real text VRAM - no window, no instance, and `dos_inbr`
        # is in a segment that no longer exists.  DOSHELLO prints what
        # `int 21h AH=4Ah` says its block reaches, which IS the arena.
        want = "Memory to top of block:"

        def said(_=None):
            try:
                return any(want in r for r in (m.screen() or []))
            except Exception:                                  # noqa: BLE001
                return False                                   # mid-teardown

        M.until(m, said, "the program to run under kern_dos",
                limit=300.0, guest=900.0)
        got = None
        for r in (m.screen() or []):
            if want in r:
                got = int(r.split(want, 1)[1].strip().split()[0])
                break
        print("dosram: the machine handed the program %d K" % got)
        if not got:
            fail("the program reports an arena of 0 - kern_dos never got as "
                 "far as dos_build_psp, so there is nothing here about memory")
        if abs(got - promised) > SLACK:
            fail("the page promised ~%d K on arm 1 and the machine handed out "
                 "%d K, a drift of %d against a slack of %d. **DOS_KDKB IS "
                 "NOT GATED AT ASSEMBLY ON PURPOSE** (SPEC.md 96.36.3): "
                 "kern_dos's floor moves with its own image, so a mirror "
                 "would fail this build every time that image changed a byte "
                 "and would be raised rather than read. THIS ROW IS THE GATE, "
                 "and the fix is to re-measure DOS_KDKB in apps/dos/dos.asm "
                 "against the figure above"
                 % (promised, got, got - promised, SLACK))
        print("dosram: ok - promised ~%d K, got %d K (slack %d)"
              % (promised, got, SLACK))
        m.type_text(" ")                # ...and let kd_leave put the session
                                        # back, so the machine is not left
                                        # holding the screen
    finally:
        m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
