#!/usr/bin/env python3
"""stkwater: how deep every task stack has actually been (SPEC.md 8).

    make KFZ=1                      # ...only a KFZ kernel fills the slices
    python3 tests/ftpd.py --kfz     # drives a real FTP session and reports
    python3 tools/stkwater.py build/qmp.sock       # ...or read a live guest

`SCH_STACK` = 256 was sized at 1.8x a 142-byte 0xCC-fill mark
(docs/KERNEL-MEMORY.md, "Task stacks") - and that mark was taken before
`ETHER.DRV` and `apps/ftpd` existed. A socket write runs the whole TCP stack on
the CALLING task's slice, and the field has now photographed `sch_stkdie`'s bar
with a background task 196 bytes into its 256 before the tick even arrived
(docs/FIELD-NOTES.md 27.6).

So this is that probe, automated and pointed at the network stack. A `KFZ=1`
`task_spawn` fills each slice with 0xCC before it writes the canary and the
frame; this reads the slices out of `LOW_SEG` and reports, per slot, the
deepest byte anything ever touched.

**Read the DEPTH, not the occupancy.** A slice is written at both ends by
construction - the canary at the bottom, the spawn frame at the top - so the
fill only ever answers "how far down from the top did anything reach", and a
slot that was never scheduled still shows its 24-byte frame. A slot reading the
whole slice has gone through the canary and `sch_switch` has already halted the
machine.

**QEMU understates a real BIOS by ~20 bytes** (docs/KERNEL-MEMORY.md): SeaBIOS
services its interrupt entries on a stack of its own, where an IBM ROM runs
int 08h on whichever task stack is current. Add that before deciding a number,
and take the deciding one on the 5150 with `tests/stackprobe`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88sym                                              # noqa: E402

FILL = 0xCC
MAGIC = b"\x57\x5A"           # SCH_MAGIC = 0x5A57, at the slice BOTTOM
DEF = ("KFZTRACE",)
SLOTS = 11                       # MAX_TASKS - 1; slot 0 runs on task 0's stack


def slice_len(defines=DEF):
    return int(os88sym.syms(defines).get("SCH_STACK", 256)) or 256


def water(mem, slots=SLOTS, n=256):
    """[(slot, used, untouched)] - `mem` is the slices, back to back.

    **THE CANARY IS AT THE BOTTOM OF EVERY SLICE**, and the first version of
    this walked straight into it: `SCH_MAGIC` is not the fill byte, so every
    slot read 256 of 256 and the report said the machine was dead eleven times
    over while the gate it ran inside passed every assertion. The scan starts
    ABOVE the canary word, and a slot whose canary is not there was never
    spawned (or has already gone through the floor, which `sch_switch` halts
    on) and is reported as such rather than measured.
    """
    out = []
    for i in range(slots):
        blk = mem[i * n:(i + 1) * n]
        if len(blk) < n:
            break
        if blk[0:2] != MAGIC:
            out.append((i + 1, None, None))  # never spawned - no fill either
            continue
        j = 2
        while j < n and blk[j] == FILL:      # the slice grows DOWN, so the
            j += 1                           # first non-fill ABOVE the canary
        out.append((i + 1, n - j, j))        # is how far anything ever reached
    return out


def report(mem, slots=SLOTS, n=256, note="", base=None):
    print("== task stack high water %s ==" % note)
    if base is not None:
        print("   slice %d bytes, sch_stacks at linear 0x%05X" % (n, base))
    worst, worst_slot = 0, 0
    for slot, used, free in water(mem, slots, n):
        if used is None:
            print("   slot %-2d  -   never spawned (no canary)" % slot)
            continue
        bar = "#" * (used * 40 // n)
        print("   slot %-2d  %3d used  %3d free  %s" % (slot, used, free, bar))
        if used > worst:
            worst, worst_slot = used, slot
    print("   ---")
    if not worst:
        print("   NO SLICE WAS EVER FILLED. Is this a `make KFZ=1` kernel? "
              "Nothing else fills them.")
        return 0
    print("   deepest %d of %d (%.0f%%) on slot %d"
          % (worst, n, 100.0 * worst / n, worst_slot))
    if worst >= n - 2:
        print("   *** AT OR THROUGH THE CANARY: sch_switch halts the machine")
    return worst


def read_live(sock="build/qmp.sock"):
    """The slices out of a running QEMU, through tests/ethernet.py's Qemu."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(here, "tests"))
    import ethernet as eth
    n = slice_len()
    base = os88sym.linear("sch_stacks", DEF)
    return eth.Qemu(sock).read(base, SLOTS * n), base, n


def main(argv):
    sock = argv[1] if len(argv) > 1 else "build/qmp.sock"
    mem, base, n = read_live(sock)
    return 0 if report(mem, SLOTS, n, "(live, %s)" % sock, base) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
