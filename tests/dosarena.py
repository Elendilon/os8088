#!/usr/bin/env python3
"""The DOS arena's unmount-and-compact (SPEC.md 96.35, 51.11.1, 66.4.3).

SOUND.DRV is ~14KB at the TOP of the heap, and the DOS box unmounts it so a
DOS program can have the card. That memory used to be unreachable: the
suspend was fenced on the fsx bracket (SPEC.md 51.11.1), which is long AFTER
the arena is claimed, so the driver's bytes went back to a heap nobody would
ask about again (docs/plans/DISK-CPU-PLAN.md 5).

**THE ROW IS AN A/B BETWEEN TWO MACHINES, and that is the whole design.** The
same disk and the same program on a 5150 WITH a Sound Blaster and on one
WITHOUT: if the recovery works, the card costs the DOS program nothing, and
the two arenas agree. If it does not, the card machine is short by the
driver's image plus its ring.

Reading a knob or a state byte would have been easier and would have asserted
the MECHANISM rather than the point of it - and the mechanism has three moving
parts in two layers (the fence, the posted compaction, the wake), any of which
can be present and still leave the program with less memory.

WHAT IT WOULD CATCH:

  - the fence back on, or the unmount    -> the card machine is ~14KB short
    moved back inside the bracket
  - the post never sent, or refused      -> ...the same, because the hole the
    and the refusal not handled             unmount opened is above the claim
  - the wake arriving and the claim       -> the card machine is short by
    being made against the OLD number        whatever the pass moved

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

# What the card is allowed to cost the program once its driver has been
# recovered. It is not zero because the two machines are not bit-identical -
# the sniff runs, the row exists - but it is nowhere near the ~14KB the image
# and the ring are worth, which is the whole quantity under test.
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
        at = (dosmap.instance(m) << 4) + dm["dos_akb"]
        akb = struct.unpack("<H", m.read(at, 2))[0]
        return snd, akb


def main():
    for p in (SYS, SND):
        if not os.path.exists(p):
            fail("%s is missing - `make doscom` builds the gate disks" % p)

    csnd, ckb = measure(CARD)
    if not csnd:
        fail("SOUND.DRV is not mounted on %s - this row's whole quantity is "
             "what unmounting it gives back, so a machine without it mounted "
             "asserts nothing (SPEC.md 51.3.1)" % CARD)
    print("dosarena: with a card  - SOUND.DRV at %04X, the program got %d KB"
          % (csnd, ckb))

    bsnd, bkb = measure(BARE)
    if bsnd:
        fail("SOUND.DRV is mounted on %s, which has no card - the A/B has no "
             "B arm" % BARE)
    print("dosarena: without one - no driver,        the program got %d KB"
          % bkb)

    if ckb + SLACK_KB < bkb:
        fail("the card costs the DOS program %d KB. SOUND.DRV's image and its "
             "ring are ~14KB and the box unmounts them before it sizes the "
             "arena, so they should come back - either the suspend is not "
             "happening before the claim, or the posted compaction is not "
             "reaching the hole it leaves (SPEC.md 96.35)" % (bkb - ckb))

    print("dosarena: the card costs the program %d KB, which is the ~14KB of "
          "SOUND.DRV recovered" % max(0, bkb - ckb))


if __name__ == "__main__":
    main()
