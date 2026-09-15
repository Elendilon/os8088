#!/usr/bin/env python3
"""The DOS arena's unmount-and-compact (SPEC.md 96.35, 51.11.1, 66.4.3).

SOUND.DRV is ~14KB at the TOP of the heap, and the DOS box unmounts it so a
DOS program can have the card. That memory used to be unreachable: the
suspend was fenced on the fsx bracket (SPEC.md 51.11.1), which is long AFTER
the arena is claimed, so the driver's bytes went back to a heap nobody would
ask about again (docs/plans/DISK-CPU-PLAN.md 5).

**THE ROW WAS AN A/B BETWEEN TWO MACHINES AND IT IS NOT ANY MORE, because the
quantity it measured has been taken away by a DESIGNED refusal one layer down
(SPEC.md 96.35.4.1).** The same disk and the same program on a 5150 WITH a
Sound Blaster and on one WITHOUT: with the box's region movable, the card cost
the program nothing and the two arenas agreed at 449 KB.

Since SPEC.md 96.40.3 shipped the four-piece DOS.O88, the box is PART 0 of a
re-homed package - and a re-homed package's region is the loader's CARVE,
re-stamped to the instance SLOT, which `mem_find_own` cannot match. So
`OS88_REGION_MOVABLE` is REFUSED, the region is a wall again, and the card
costs the program **426 KB against 440**: exactly `SOUND.DRV`'s 6,144-byte
image plus its 8,192-byte ring, in a hole above a pinned region. The kernel's
`.rehome` arm refuses on purpose and is right to - `I_SPTR` is the PART's
segment where the claim's base is the carve's, measured 512 bytes apart on
this very package - so this is the OWNER's call and not a defect to work
around here.

**WHAT THAT COSTS THIS ROW is its discriminating power, and pretending
otherwise would be worse than saying so.** A suspend that never happened and a
hole that cannot be reached give the SAME 14 KB, so the arena delta can no
longer tell SPEC.md 96.35's failure modes apart. What it can still do is two
things, and both are worth a row:

  - **assert the MECHANISM**, which is `[dos_drvout]`: the driver really was
    unmounted before the arena was sized. That is the fence and the unmount,
    and it is exactly what the A/B used to prove indirectly;
  - **hold the loss to the driver's own bytes.** 14 KB is the pin. Anything
    LARGER is a new fault - a second claim that stopped moving, a post that
    stopped being sent - and anything SMALLER means the kernel learned to
    relocate a re-homed carve and this row should go back to asserting
    equality.

WHAT IT WOULD CATCH:

  - the fence back on, or the unmount    -> [dos_drvout] reads 0
    moved back inside the bracket
  - a SECOND thing stopping moving       -> the loss grows past the driver's
                                            image plus its ring
  - the carve becoming relocatable       -> the loss goes to zero, and the row
    (the open question above)               says so rather than passing
                                            quietly on a stale expectation

It runs on MartyPC and must: no other emulator here models a Sound Blaster
at all, which is what makes the pair of machines the experiment.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88geom                                                # noqa: E402
import os88ui                                                  # noqa: E402
import dosmap                                                  # noqa: E402

SYS = "build/os8088-360.img"
SND = "build/dossnd360.img"
CARD = "os8088_5150_herc_sb_gla"         # ...a card
BARE = "os8088_5150_herc_gla"            # ...and the same machine without one

# What the card costs the program today: SOUND.DRV's image (6,144) plus its
# ring (8,192), stranded above a pinned region (SPEC.md 96.35.4.1). The two
# machines are not bit-identical either - the sniff runs, the row exists - so
# the band is that figure with the same slack the equality assertion used.
DRV_KB = 14
SLACK_KB = 4


def fail(msg):
    print("dosarena: FAIL: %s" % msg)
    sys.exit(1)


def measure(machine):
    """(SOUND.DRV's segment at the desktop, the arena the program got) in KB."""
    with os88ui.boot(SYS, apps=SND, machine=machine) as ui:
        m = ui.m
        snd = struct.unpack("<H", m.read(m.sym("drv_tab")
                                         + os88geom.DRVR_SEG, 2))[0]
        if not ui.path("B:/DOSSND.COM"):
            fail("%s: double-clicking DOSSND.COM opened no window" % machine)

        rows = []
        end = time.time() + 180.0
        while time.time() < end:
            rows = m.screen() or []
            if any("READY" in r for r in rows):
                break
            time.sleep(0.3)
        else:
            fail("%s: the program never finished; the last screen was %r"
                 % (machine, [r.rstrip() for r in rows if r.strip()][:12]))

        # ...AND THE PACKAGE'S SEGMENT IS READ *NOW*, not before the launch.
        # If the feature works the region has MOVED - that is what the posted
        # pass is for - so a base taken earlier names the bytes it used to
        # occupy, which decode as a plausible wrong number rather than an
        # error (SPEC.md 66.4.3).
        dm = dosmap.package()
        base = dosmap.instance(m) << 4
        akb = struct.unpack("<H", m.read(base + dm["dos_akb"], 2))[0]
        out = m.read(base + dm["dos_drvout"], 1)[0]
        return snd, akb, out


def main():
    for p in (SYS, SND):
        if not os.path.exists(p):
            fail("%s is missing - `make doscom` builds the gate disks" % p)

    csnd, ckb, cout = measure(CARD)
    if not csnd:
        fail("SOUND.DRV is not mounted on %s - this row's whole quantity is "
             "what unmounting it gives back, so a machine without it mounted "
             "asserts nothing (SPEC.md 51.3.1)" % CARD)
    print("dosarena: with a card  - SOUND.DRV at %04X, the program got %d KB, "
          "[dos_drvout]=%d" % (csnd, ckb, cout))

    # --- 1: THE MECHANISM, which is what the A/B used to prove indirectly ---
    if not cout:
        fail("[dos_drvout] is 0 on the machine WITH a card: the box did not "
             "unmount SOUND.DRV before it sized the arena. That is SPEC.md "
             "51.11.1's fence back on, or the suspend moved back inside the "
             "fsx bracket - and it is the half of SPEC.md 96.35 that still "
             "works, so it is the half this row can still assert")

    bsnd, bkb, _ = measure(BARE)
    if bsnd:
        fail("SOUND.DRV is mounted on %s, which has no card - the A/B has no "
             "B arm" % BARE)
    print("dosarena: without one - no driver,        the program got %d KB"
          % bkb)

    # --- 2: ...and the loss is the PIN's worth and nothing more ------------
    lost = bkb - ckb
    if lost > DRV_KB + SLACK_KB:
        fail("the card costs the DOS program %d KB, and SOUND.DRV's image plus "
             "its ring are %d. The %d is the re-homed carve nothing can move "
             "(SPEC.md 96.35.4.1); anything past it is a SECOND claim that has "
             "stopped moving, or the posted compaction no longer reaching the "
             "hole at all (SPEC.md 96.35)" % (lost, DRV_KB, DRV_KB))
    if lost < DRV_KB - SLACK_KB:
        fail("the card costs the DOS program only %d KB against the %d "
             "SOUND.DRV is worth. THAT IS GOOD NEWS AND THIS ROW IS STALE: "
             "the kernel has learned to relocate a re-homed carve, so SPEC.md "
             "96.35.4.1's open question is answered and this row goes back to "
             "asserting the two machines AGREE (`ckb + SLACK_KB < bkb`), which "
             "is what it said before the package became four pieces"
             % (lost, DRV_KB))

    print("dosarena: the unmount happened and the card costs the program %d "
          "KB - the pinned re-homed carve, and nothing more (SPEC.md "
          "96.35.4.1)" % lost)


if __name__ == "__main__":
    main()
