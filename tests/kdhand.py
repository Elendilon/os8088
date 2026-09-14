#!/usr/bin/env python3
"""The DOS handoff, end to end (SPEC.md 96.40, docs/plans/KERN-DOS-PLAN.md 7).

Run a .COM in the window, then run THE SAME .COM again with the Memory page's
third arm picked - and assert that the second run happened on a machine with
no os8088 in it at all: more memory, a text screen the kernel is not drawing,
and a restart at the end that brings the desktop back.

WHAT IT WOULD CATCH, and every one of these was seen FAILING on the way to
writing it (docs/WRITING-TESTS.md 1):

  - the post refused, or spent by nobody        -> the program runs WINDOWED and
                                                   the KB figure does not move
  - `hbm_dosrun` reading the record through the -> `mov ds` before `mov si` puts
    poster's DS                                    543 bytes of the package's own
                                                   bss in the record, and the
                                                   magic check refuses it
  - the module asking `dsk_find_name` for a     -> "DOS.O88 is not on that disk
    name in its OWN image                          any more" about a file in the
                                                   folder it just stood in
  - the stub reading the part as a CLASSIC LZ4  -> the T word is read as a token
    block (SPEC.md 20.13.7)                        and the image lands NINE bytes
                                                   along: a jump into rubble
  - `int 1Eh` left naming KERNEL_SEG:dsk_dpt    -> kern_dos's own table is at
                                                   another offset, so the BIOS
                                                   reads code as an EOT: "the
                                                   disk could not be mounted"
  - `.bss` arriving as the outgoing kernel's    -> a volume table that looks
    bytes (nobits is not zeroed by anything)       plausible and is another OS's
  - `OSAPI_MOUSE` surviving into the image      -> `dos_getkey` polls it, so the
                                                   machine spins in the ROM with
                                                   a key already in the ring

It runs on MartyPC and must: the whole point is a real 8088 running a DOS
program with the operating system gone, and both halves are read with
`screen()` off a text mode nothing of ours is driving.
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

SYS = "build/kdos360.img"
COM = "build/doscom360.img"
MACH = "os8088_5150_cga_gla"

RD_N, RD_SEL, RD_PITCH, RD_DIS = 10, 12, 14, 16
KEEP, DUMP, WHOLE, NARM = 0, 1, 2, 3


def fail(msg):
    print("kdhand: FAIL: %s" % msg)
    sys.exit(1)


def rows(m):
    return [r.rstrip() for r in (m.screen() or [])]


def wait_text(m, want, secs=90, what=""):
    """Wait for `want` on the guest's text screen, or say what was there."""
    end = time.time() + secs
    while time.time() < end:
        rs = rows(m)
        if any(want in r for r in rs):
            return rs
        time.sleep(0.25)
    fail("%s: %r never appeared on the text screen. The last one was %r"
         % (what or want, want, [r for r in rows(m) if r.strip()][:10]))


def topmem(rs, what):
    for r in rs:
        if "Memory to top of block:" in r:
            try:
                return int(r.split(":")[1].strip().split()[0])
            except (IndexError, ValueError):
                fail("could not read a KB figure out of %r" % r)
    fail("%s: the program never printed its top-of-memory figure" % what)


def rec(m, pseg, dm, off):
    return int.from_bytes(m.read((pseg << 4) + dm["dos_mrad"] + off, 2),
                          "little")


def main():
    for p in (SYS, COM):
        if not os.path.exists(p):
            fail("%s is missing - `make kdostest` builds both" % p)

    with os88ui.boot(SYS, apps=COM, machine=MACH) as ui:
        m = ui.m

        # --- 1. the ordinary windowed run, which is the BASELINE -------------
        if not ui.path("B:/DOSHELLO.COM"):
            fail("double-clicking DOSHELLO.COM opened no window")
        rs = wait_text(m, "READY", what="the windowed run")
        win_kb = topmem(rs, "the windowed run")
        print("kdhand: windowed, the program has %d KB above its PSP" % win_kb)
        m.type_text("x")
        os88marty.settle(m)
        if "DOS" not in ui.titles():
            fail("the DOS window is gone after the windowed run: %r"
                 % (ui.titles(),))

        dm = dosmap.package("DOSKPART")
        pseg = dosmap.instance(m)
        mo = os88mouse.Mouse(marty=m)

        # --- 2. the third arm, which this build can offer --------------------
        mo.click(*dosmap.centre(m, pseg, dm, "dos_erect"))
        os88marty.settle(m)
        if rec(m, pseg, dm, RD_N) != NARM:
            fail("the Memory page has %d arms" % rec(m, pseg, dm, RD_N))
        dis = rec(m, pseg, dm, RD_DIS)
        if dis & (1 << WHOLE):
            fail("the third arm is GREYED on a build that carries kern_dos as "
                 "a part (SPEC.md 96.36.1): OS88UI_RD_DIS is 0x%04X. "
                 "`dos_mem_whole` reads the part table's own length word, so "
                 "either the part is not in DOS.O88 or the row is not found"
                 % dis)
        x1, y1, x2, _ = dosmap.rect(m, pseg, dm, "dos_mrad")
        pitch = rec(m, pseg, dm, RD_PITCH)
        mo.click((x1 + x2) // 2, y1 + WHOLE * pitch + pitch // 2)
        os88marty.settle(m)
        if rec(m, pseg, dm, RD_SEL) != WHOLE:
            fail("clicking the third arm left OS88UI_RD_SEL at %d"
                 % rec(m, pseg, dm, RD_SEL))
        print("kdhand: the third arm is live and picked")

        # --- 3. ...and Run, which does not come back -------------------------
        mo.click(*dosmap.centre(m, pseg, dm, "dos_trect"))   # Return, which is
        os88marty.settle(m)                                  # the ONLY way back
                                                             # to the main page:
                                                             # 'Environment' is
                                                             # one-way and Run
                                                             # is only hit there
        mo.click(*dosmap.centre(m, pseg, dm, "dos_rrect"))
        rs = wait_text(m, "READY", secs=150, what="the run under kern_dos")
        kd_kb = topmem(rs, "the run under kern_dos")
        print("kdhand: under kern_dos, the program has %d KB above its PSP"
              % kd_kb)
        for want in ("os8088 DOS gate", "DOS version 3.30",
                     "refused with CF, as it should be"):
            if not any(want in r for r in rs):
                fail("%r is not on the screen under kern_dos: the DOS core is "
                     "not servicing INT 21h over the new back end" % want)

        # **THE WHOLE POINT, IN ONE COMPARISON.** It is the same program, the
        # same disk and the same DOS core; the only difference is that the
        # second run has no operating system under it.
        if kd_kb <= win_kb:
            fail("the program got %d KB under kern_dos against %d KB in the "
                 "window - the handoff gave it NO MORE MEMORY, which is the "
                 "only reason the arm exists (docs/plans/KERN-DOS-PLAN.md 1)"
                 % (kd_kb, win_kb))
        print("kdhand: %d KB against %d - the handoff is worth %d KB"
              % (kd_kb, win_kb, kd_kb - win_kb))

        # --- 4. the exit code, and the restart at the end (§9) ---------------
        m.type_text("x")
        rs = wait_text(m, "exited", secs=90, what="the exit")
        if not any("042" in r or "42" in r for r in rs if "exited" in r):
            fail("the exit line does not carry the program's code 42: %r"
                 % [r for r in rs if "exited" in r])
        print("kdhand: %s" % next(r.strip() for r in rs if "exited" in r))

        # **AND THE MACHINE COMES BACK** (§9). It comes back to a BARE
        # desktop and not to the one we left - `int 19h` is a cold start of
        # os8088, so there are no windows to look for. `ui.up()` is the
        # question that has an answer: `desk_rows` and `menu_nbar` are zero
        # until the boot reaches the desktop, so a machine that never restarts
        # and one that hangs in the loader both read the same as a black
        # screen and this tells them apart from a finished boot.
        m.type_text("x")                    # "Press any key to restart"
        try:
            ui.up(limit=240)
        except Exception as e:
            fail("the machine never came back to a desktop after the "
                 "program's `int 19h` (SPEC.md 96.40, §9): %s. The text "
                 "screen holds %r" % (e, [r for r in rows(m) if r.strip()][-4:]))
        ui.ready(limit=240)
        w = ui.open_drive("A")
        if not w:
            fail("the restarted machine will not open a Disk window - it "
                 "reached a desktop and the disk layer did not come up")
        print("kdhand: the machine restarted into os8088 - titles %r"
              % (ui.titles(),))

    print("kdhand: ok - a DOS program ran with the whole machine and gave it back")


if __name__ == "__main__":
    main()
