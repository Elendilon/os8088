#!/usr/bin/env python3
"""stkdiagread: the STKDIAG panel's numbers, off a running guest.

    make stkdiag && make test STKDIAG=1
    python3 tools/stkdiagread.py                    # ...then this, after ~95s

The panel (kernel/stkdiag.inc, docs/STACK-SLOTS-PLAN.md 10) is drawn to be
PHOTOGRAPHED, because that is the only channel a 5150 has. On an emulator a
photograph is a screenshot somebody then has to read with their eyes, and a
number transcribed by eye is a number that can be transcribed wrong - so the
same values are published in SPEC.md 57's debug registry as 'SD' and this
follows the registry to them.

It reads the block by SYMBOL, the way tools/stkwater.py reads sch_stacks: the
registry's own tag word is checked first, so a pointer that landed somewhere
else is reported rather than believed.

WHAT THE NUMBERS MEAN, and the pairing is the point:

  ROM int08   what the ROM's int 08h chain costs a stack, measured on a private
              one so no task slice is touched. THE UNKNOWN - every BIOS differs
              and docs/STACK-SLOTS-PLAN.md 9 is open on it.
  floor       the interrupt floor on a task slice, latched at the end of each
              phase, cumulative. The kernel alternates ticks so this is the
              SHIPPING floor and not the floor of the fix.
  MAX         the running maximum. The one to quote; it only rises.

A phase nobody performed reads equal to the phase before it, which is a
reading and not a hole.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88sym                                              # noqa: E402

# The arm's defines, because os88sym asserts byte-identity with
# build/kernel.bin and there are three arms: a reader pinned to STK_DIAG alone
# refuses arms 2 and 3 with "the map describes a DIFFERENT kernel", which reads
# as the disk being wrong rather than the tool.
#   python3 tools/stkdiagread.py                     # arm 1, as it ships
#   OS88_ARM="NO_MOUPRIV" python3 tools/...          # arm 2, before SPEC.md 9.10
#   OS88_ARM="STK_FIX"    python3 tools/...          # arm 3
DEF = tuple(["STK_DIAG"] + os.environ.get("OS88_ARM", "").split())
TAG = 0x4453                    # 'SD' - kernel.asm's DBG_TAG_STKD
# The block holds POINTERS, not values - bootprof's convention (SPEC.md 57.2):
# the registry names where the live state is, so a reader never gets a stale
# snapshot. The last two are literals, because a constant cannot go stale.
PTRS = ("rom08", "q", "m", "k", "phase")
LITS = ("slice", "ntask")
PHASES = ("1/3 quiet", "2/3 mouse", "3/3 keys", "done")


def read(sock="build/qmp.sock"):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(here, "tests"))
    import ethernet as eth
    m = eth.Qemu(sock)
    nw = 1 + len(PTRS) + len(LITS)
    blk = m.read(os88sym.linear("sd_dbg_blk", DEF), 2 * nw)
    w = [blk[i] | (blk[i + 1] << 8) for i in range(0, len(blk), 2)]
    if w[0] != TAG:
        sys.exit("stkdiagread: the block at sd_dbg_blk starts 0x%04X, not 'SD' "
                 "(0x%04X) - is this a STKDIAG=1 kernel?" % (w[0], TAG))
    base = os88sym.linear("sd_dbg_blk", DEF) - os88sym.syms(DEF)["sd_dbg_blk"]
    v = {}
    for i, name in enumerate(PTRS, start=1):
        v[name] = int.from_bytes(m.read(base + w[i], 2), "little")
    for i, name in enumerate(LITS, start=1 + len(PTRS)):
        v[name] = w[i]
    # ...and the per-slice fill, which is the same question one level down
    eq = os88sym.equates(DEF)
    n, nt = int(eq["SCH_STACK"]), int(eq["MAX_TASKS"])
    import stkwater as W
    mem = m.read(os88sym.linear("sch_stacks", DEF), (nt - 1) * n)
    return v, W.water(mem, nt - 1, n), n


def main():
    sock = sys.argv[1] if len(sys.argv) > 1 else "build/qmp.sock"
    v, slices, n = read(sock)
    ph = v["phase"] & 0xFF
    arm = {(): "ARM 1 as it ships", ("NO_MOUPRIV",): "ARM 2 NOMOUPRIV (before)",
           ("STK_FIX",): "ARM 3 + STKFIX"}.get(DEF[1:], " ".join(DEF[1:]))
    print("== STKDIAG ==   %s   slice %d, MAX_TASKS %d, phase %s"
          % (arm, v["slice"], v["ntask"], PHASES[ph] if ph < 4 else "?"))
    if ph < 3:
        print("   NOT FINISHED - the run takes ~95 seconds from the desktop")
    print("   ROM int08 chain      %4d" % v["rom08"])
    print("   floor  quiet         %4d" % v["q"])
    print("   floor  +mouse        %4d   (+%d)" % (v["m"], v["m"] - v["q"]))
    print("   floor  +keys         %4d   (+%d)" % (v["k"], v["k"] - v["m"]))
    print("   --- every slice ---")
    for slot, used, _free in slices:
        print("   slot %-2d %s" % (slot, "never spawned" if used is None
                                   else "%3d of %d" % (used, n)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
