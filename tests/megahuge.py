#!/usr/bin/env python3
"""kern_mega: ONE CLAIM FOR ALL OF IT (docs/plans/KERN-MEGA-MEMORY-PLAN.md MC5,
D6-D8).

    python3 tests/megahuge.py            the row
    python3 tests/megahuge.py --keep     ...and leave the boot's directory

OSAPI_MEM_HUGE with AX = 0 ASKS: the most one claim of the cell's can be given
- the pool alone, the heap alone, or the BRIDGE, the pool's best run cut to
whole 64KB windows and then the heap less its 64KB reserve, under ONE run of
selectors. This boots kern_mega under Bochs at 4MB with tests/megahuge's
MEGAHUGE on C:'s RUN folder, lets MEGARUN start it, and asserts:

  1. `MEGAHUGE: max N` - the query answered, more than the pool alone can
     hold (so the answer is a bridge: the pool's KB from the walk is less);
  2. the claim of exactly N succeeded, step 8, its first window above 1MB and
     its last below - the bridge, pool first;
  3. `MEGAHUGE: ok` - a pattern written through every window read back, the
     seam included, so no two windows alias;
  4. `MEGAHUGE: again N` - the free gave both pieces back;
  5. no kern_mega FAULT or CLOSED.

THE FAILING CASE (docs/WRITING-TESTS.md 1): the tree before MC5 answers AX = 0
with a refusal (a claim of 0KB) - red on (1), `MEGAHUGE: no 01`. Verified when
the row was written.
"""
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88bochs  # noqa: E402
from os88fixture import need  # noqa: E402

PKGS = ["build/megahuge.o88"]


def main():
    keep = "--keep" in sys.argv
    for p in PKGS + ["build/megarun.o88", "build/mega.img",
                     "build/mbr.bin"]:
        need(p)
    out = tempfile.mkdtemp(prefix="megahuge-")
    t0 = time.time()
    os88bochs.MEGS = 4
    box = os88bochs.Box(out, [os.path.join(ROOT, p) for p in PKGS])
    fails, lines, xkb = [], [], None
    try:
        if box.wait_for("kern_mega:", 240):
            box.up()
            xkb = int.from_bytes(box.read("xm_kb", 2), "little")
            box.megarun()
            end = time.time() + 240
            while time.time() < end:
                lines = box.lines()
                if any(l.startswith("kern_mega FAULT") or
                       l.startswith(("MEGAHUGE: ok", "MEGAHUGE: no",
                                     "MEGAHUGE: bad")) for l in lines):
                    break
                time.sleep(0.2)
            time.sleep(1)
            lines = box.lines()
        else:
            fails.append("no kern_mega line in 240s")
    finally:
        box.stop()
    for l in lines:
        if l.startswith("kern_mega FAULT") or l.startswith(
                "kern_mega CLOSED"):
            fails.append(l)
        if l.startswith("MEGAHUGE"):
            print("megahuge: " + l)
    got = {}
    for l in lines:
        for k, rx in (("max", r"MEGAHUGE: max (\w+)"),
                      ("again", r"MEGAHUGE: again (\w+)"),
                      ("claim", r"MEGAHUGE: claim (\w+) step (\w+)"),
                      ("lin", r"MEGAHUGE: first (\w+) last (\w+)")):
            m = re.match(rx, l)
            if m:
                got[k] = [int(g, 16) for g in m.groups()]
    if "max" not in got:
        fails.append("the query never answered: %s" % [
            l for l in lines if l.startswith("MEGAHUGE: no")])
    else:
        n = got["max"][0]
        print("megahuge: the pool is %sK, the answer %dK" % (xkb, n))
        if xkb is not None and n <= xkb:
            fails.append("the answer %dK is no more than the pool's %dK: "
                         "no bridge" % (n, xkb))
        if "claim" not in got or got["claim"][1] != 8:
            fails.append("the claim of the answer: %s" % got.get("claim"))
        if "lin" not in got:
            fails.append("no window bases")
        elif not (got["lin"][0] >= 0x100000 and got["lin"][1] < 0xA0000):
            fails.append("first window at %X, last at %X: not pool first "
                         "then the heap" % tuple(got["lin"]))
        if "MEGAHUGE: ok" not in lines:
            fails.append("the pattern did not read back: %s" % [
                l for l in lines if l.startswith("MEGAHUGE: bad")])
        if got.get("again", [None])[0] != n:
            fails.append("asked again after the free: %s, not %d"
                         % (got.get("again"), n))
    print("megahuge: %.0fs under Bochs" % (time.time() - t0))
    for f in fails:
        print("FAIL: " + f)
    if keep or fails:
        print("megahuge: the boot is in " + out)
    else:
        shutil.rmtree(out, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
