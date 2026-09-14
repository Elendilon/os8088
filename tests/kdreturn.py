#!/usr/bin/env python3
"""The DOS handoff comes BACK (SPEC.md 96.41, docs/plans/KERN-DOS-PLAN.md 8).

    python3 tests/kdreturn.py

W5 gave a DOS program the whole machine and restarted when it exited, because
there was nothing to return to.  On a machine with a fixed disk there is: the
kernel writes a hibernation image before the handoff, `kern_dos` restarts as it
always did, and the fresh boot finds the pointer and resumes it **without
asking** - because this was not the user leaving the machine.

WHAT IT ASSERTS, in the order the machine does it:

  1 the program ran with the whole machine, which is the KB figure W5 gates
  2 the desktop came back BY ITSELF - no Resume window, no question. A
    hibernation the user did not ask for and then has to answer for is worse
    than no return at all
  3 the DOS window is up with the program's own exit code in it, which is the
    whole point: the session is the one that left
  4 the mailbox at 0040:00F0 is CLEARED, so the next resume cannot pick up a
    code from this one

IT NEEDS A HARD DISK and boots off one: `hb_pick` is the predicate on both
sides, so a floppy-only machine takes W5's arm and this row would be asserting
nothing.  tests/hibernate.py's fixture, with the parted DOS.O88 and a DOS
program in the volume's root.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosmap                                                  # noqa: E402
import os88marty as M                                          # noqa: E402
import os88mouse                                               # noqa: E402
import os88ui                                                  # noqa: E402

# THE TEMPLATE IS THE BUILT TREE'S, not tools/martypc/ - that directory holds
# the SOURCE patches and the ROMs, and `make marty` stages the run tree under
# build/. tests/hibernate.py names the same file.
TEMPLATE = "build/martypc/run/media/hdds/default_xtide.vhd"
MACHINE = "os8088_xt_hdd"
KERNEL = "build/kernel.sys"
# **ABSOLUTE, BECAUSE MARTYPC RESOLVES A PATH AGAINST ITS OWN RUN TREE**
# (tools/os88marty.py's _private_run_dir): a relative one names a file that is
# not there and the machine boots to a loading screen and stays on it.
VHD = os.path.abspath("build/kdreturn-%d.vhd" % os.getpid())
FLOPPY = os.path.abspath("build/kdreturn-%d.img" % os.getpid())

KDB = 0x4F0                     # 0040:00F0, the exit code's mailbox


def fail(msg):
    print("kdreturn: FAIL: %s" % msg)
    sys.exit(1)


def rows(m):
    return [r.rstrip() for r in (m.screen() or [])]


def fixture():
    for p in (TEMPLATE, KERNEL, "build/kdos/DOS.O88", "build/DOSHELLO.COM"):
        if not os.path.exists(p):
            fail("%s is missing - `make kdostest` builds the DOS pieces and "
                 "`make marty` the template" % p)
    subprocess.check_call(
        ["python3", "tools/os88hdd.py", "--template", TEMPLATE, "--out", VHD,
         "--kernel", KERNEL, "--vbr", "build/boothd.bin",
         "--mbr", "build/mbr.bin",
         "--file", "HIBER.DRV=build/hiber.drv",
         "--file", "CTRL.DRV=build/ctrl.drv",
         "--file", "HDD.DRV=build/hdd.drv",
         "--file", "DOS.O88=build/kdos/DOS.O88"])
    # ...AND THE PROGRAM ON A FLOPPY, which is still not an accident of the
    # fixture though the reason has changed. It USED to be that `kern_dos`
    # had no volume table and a fixed disk was a geometry it had not got -
    # SPEC.md 96.46 carries the kernel's table over now and `tests/kdhdd.py`
    # is that row. What W6 is about is the RETURN, and keeping the program on
    # a floppy keeps this row about the return rather than about the mount.
    subprocess.check_call(
        ["python3", "tools/os88disk.py", "-o", FLOPPY, "--size", "360",
         "build/DOSHELLO.COM"])


def wait_text(m, want, secs, what):
    end = time.time() + secs
    while time.time() < end:
        rs = rows(m)
        if any(want in r for r in rs):
            return rs
        time.sleep(0.25)
    fail("%s: %r never reached the text screen; the last one held %r"
         % (what, want, [r for r in rows(m) if r.strip()][:10]))


def topmem(rs):
    for r in rs:
        if "Memory to top of block:" in r:
            return int(r.split(":")[1].strip().split()[0])
    fail("the program printed no top-of-memory figure: %r"
         % [r for r in rs if r.strip()][:8])


def wait_desktop(m, ui, secs=300):
    """Wait for the RESTARTED machine to reach a graphics desktop.

    **`ui.up()` IS NOT THE WAIT HERE**, and neither is poking its two words
    first. A warm boot clears no bss (kernel/hiber.inc's `hb_probe` says so
    about its own three), so `desk_rows` and `menu_nbar` hold whatever is at
    those offsets - which between the handoff and the boot is `kern_dos`'s
    own image, so `up()` returns on the BIOS banner and everything after it
    reads a machine that has not booted. Zeroing them first is worse: at that
    moment those addresses ARE kern_dos's running code.

    The mode is the honest question. os8088's desktop is GRAPHICS on every
    adapter it has (SPEC.md 39) and everything between - the ROM's banner,
    `kern_dos`, the loading screen's own text - is not.
    """
    end = time.time() + secs
    while time.time() < end:
        try:
            if "Graphics" in (m.video() or {}).get("mode", ""):
                return ui.ready(limit=secs)
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError("no graphics desktop in %ds; the text screen holds %r"
                       % (secs, [r for r in rows(m) if r.strip()][-4:]))


def main():
    fixture()
    m = M.launch(None, apps=FLOPPY, machine=MACHINE,
                 extra=["--mount", "hd:0:" + VHD])
    try:
        ui = os88ui.UI(m)
        ui.ready(limit=240)
        print("kdreturn: booted off the fixed disk")

        win = ui.path("B:/DOSHELLO.COM")
        if not win:
            fail("double-clicking DOSHELLO.COM on the floppy opened no window")
        rs = wait_text(m, "READY", 150, "the windowed run")
        win_kb = topmem(rs)
        m.type_text("x")
        M.settle(m)
        print("kdreturn: windowed, %d KB above the PSP" % win_kb)

        dm = dosmap.package(*dosmap.KDBOX)
        pseg = dosmap.instance(m)
        mo = os88mouse.Mouse(marty=m)
        m.write((pseg << 4) + dm["dos_keepc"], bytes([2, 0]))
        mo.click(*dosmap.centre(m, pseg, dm, "dos_rrect"))

        rs = wait_text(m, "READY", 300, "the run under kern_dos")
        kd_kb = topmem(rs)
        if kd_kb <= win_kb:
            fail("%d KB under kern_dos against %d in the window - the handoff "
                 "gave the program no more memory" % (kd_kb, win_kb))
        print("kdreturn: under kern_dos, %d KB - the handoff is worth %d"
              % (kd_kb, kd_kb - win_kb))

        m.type_text("x")                        # exit with code 42
        wait_text(m, "exited", 120, "the exit")
        m.type_text("x")                        # ...and restart

        # --- 2. IT COMES BACK BY ITSELF ---------------------------------
        try:
            wait_desktop(m, ui)
        except Exception as e:
            fail("the machine never came back after the return: %s" % e)
        titles = ui.titles()
        print("kdreturn: back on a desktop, titles %r" % (titles,))
        if "Hibernate" in titles:
            fail("the machine asked. An image written for a DOS handoff is "
                 "not the user leaving the machine, so HBP_DOS should have "
                 "turned UI_RBQ_ASK into UI_RBQ_RESUME "
                 "(docs/plans/KERN-DOS-PLAN.md 8)")
        if "DOS" not in titles:
            fail("the DOS window is not up: the session that came back is not "
                 "the one that left - titles %r" % (titles,))

        # --- 3. ...with the program's own exit code ---------------------
        pseg = dosmap.instance(m)
        st = m.read((pseg << 4) + dm["dos_state"], 1)[0]
        code = m.read((pseg << 4) + dm["dos_exit"], 1)[0]
        if st != 2:                             # DST_RAN
            fail("[dos_state] is %d and not DST_RAN: the box was woken and "
                 "did not read KDH_CODE (SPEC.md 96.41)" % st)
        if code != 42:
            fail("[dos_exit] is %d and DOSHELLO exits with 42 - the code came "
                 "back wrong, which is worse than not coming back" % code)
        print("kdreturn: the box shows DST_RAN, exit code %d" % code)

        # --- 4. and the mailbox is spent --------------------------------
        box = m.read(KDB, 6)
        if box[:4] == b"KDX1":
            fail("0040:00F0 still holds a live record %r - the next resume "
                 "would attach this program's code to another run" % box)
        print("kdreturn: the mailbox is cleared (%s)" % box[:4].hex())
    finally:
        m.close()
        for p in (VHD, FLOPPY):
            try:
                os.unlink(p)
            except OSError:
                pass

    print("kdreturn: ok - the machine went away, ran DOS, and came back")


if __name__ == "__main__":
    main()
