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


def _near(syms, off, window=1024):
    """The symbol `off` is inside, as name+delta - or None if nothing is near.

    `window` bounds it: a stack word that happens to be a small number is not a
    call into whatever label sits 30KB below it, and a resolver that says so
    anyway turns a dump into a page of confident noise.
    """
    best, bestd = None, window + 1
    for name, addr in syms.items():
        d = off - addr
        if 0 <= d < bestd:
            best, bestd = name, d
    if best is None:
        return None
    return best if bestd == 0 else "%s+%d" % (best, bestd)


def is_call_site(img, w):
    """Does a `call` end exactly at offset `w` in `img`?

    **This is what turns the dump into a chain.** A near return address points
    at the byte after a call, so the bytes just before it have to BE a call -
    and almost no random word passes. Without it every stack word matched some
    label within a kilobyte and the page read as a confident list of routines
    the machine had never been in.

        E8 lo hi          call rel16       (3 bytes)
        FF /2  mod r/m    call r/m16       (2-4)
        9A lo hi sg sg    call far ptr     (5)
        FF /3  mod r/m    call far r/m     (2-4)
    """
    if w < 3 or w > len(img):
        return None
    if img[w - 3] == 0xE8:
        return "near"
    if img[w - 5:w - 4] == b"\x9A":
        return "far"
    for n in (2, 3, 4):                      # FF with a mod r/m of 2 or 3
        if w - n >= 0 and img[w - n] == 0xFF:
            if ((img[w - n + 1] >> 3) & 7) in (2, 3):
                return "indirect"
    return None


def annotate(blk, used, n=256, kern=None, drv=None, seg=None,
             kimg=None, dimg=None):
    """The touched part of one slice, word by word, with the code it names.

    **This is the point of the fill.** Between the high-water mark and wherever
    SP is now, the bytes are DEAD - left there by the deepest excursion and
    overwritten by nothing shallower - so the return addresses of the chain
    that went deepest are still sitting in them. Reading them back is how the
    bytes get attributed to routines instead of argued about.

    A word is only called a return address if a `call` really ends at it
    (`is_call_site`); everything else is printed as a bare value, because a
    saved register that happens to land near a label is not a frame.
    """
    kern, drv = kern or {}, drv or {}
    top = n
    print("   --- the deepest excursion, top of slice first ---")
    print("   (only words a `call` actually ends at are named: everything "
          "else is a saved register or a local)")
    for off in range(top - 2, max(n - used - 2, 0), -2):
        w = blk[off] | (blk[off + 1] << 8)
        depth = top - off
        if blk[off] == FILL and blk[off + 1] == FILL:
            continue
        tags = []
        if kimg and is_call_site(kimg, w):
            nm = _near(kern, w, 4096)
            tags.append("KERNEL %s <- %s call" % (nm, is_call_site(kimg, w)))
        if dimg and is_call_site(dimg, w):
            nm = _near(drv, w, 4096)
            tags.append("ETHER  %s <- %s call" % (nm, is_call_site(dimg, w)))
        if seg and w == seg:
            tags.append("the driver's SEGMENT")
        if not tags:
            continue
        print("   -%-3d  %04X   %s" % (depth, w, "   |   ".join(tags)))


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
