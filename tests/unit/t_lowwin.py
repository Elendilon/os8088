#!/usr/bin/env python3
"""The mount-owned window is the bottom of `.lowbss` (SPEC.md 2.1.2).

    python3 tests/unit/t_lowwin.py

`disk_dir`, `disk_icons` and `dsk_secbuf` come alive at `drv_boot`'s first
mount and are untouched before it - the same moment, and the same silence, as
the FAT window under them.  Adjacent, the two are one contiguous 8,192-byte
region that is dead for the whole of `kmain`, which is what the boot overlay
is meant to land in and spill through (docs/BOOT-LADDER-PLAN.md stage B).

THIS ROW EXISTS BECAUSE NOTHING ELSE WOULD NOTICE.  The placement is bought by
one line - `kernel/dskwin.inc` being the FIRST file `kernel.asm` includes,
because `-f bin` lays a section out in the order its contributions appear and
`.lowbss` has twelve contributors.  Put a new include above it, or move a
`.lowbss` block into a file that sorts earlier, and the window slides into the
middle of the rung.  The kernel still assembles.  It still boots.  Every test
in this tree still passes, because no byte of RAM has moved and no address any
code names has changed - `.lowbss` is `nobits` and reached through SS either
way.  The only thing that breaks is stage C, later, in a build nobody has run
yet, and the symptom there is the overlay writing over `vid_rowtab`.

So the invariant is checked where it can still be read: the offsets, off the
same NASM listing the layout comes from.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from harness import check, done                           # noqa: E402

WANT = [("disk_dir", 1024), ("disk_icons", 2048), ("dsk_secbuf", 512)]
FAT_BYTES = 4608          # DSK_FAT_SECS * 512, the rung under this one


def lowbss(defines=()):
    """[(offset, size, label)] for `.lowbss`, in address order."""
    out = os.path.join(ROOT, "build", "t_lowwin.lst")
    binout = os.path.join(ROOT, "build", "t_lowwin.bin")
    cmd = [os.environ.get("NASM", "nasm"), "-f", "bin", "-w+error",
           "-I", "kernel/", "-I", "apps/", "-I", "build/"] + list(defines) + \
          ["-l", out, "-o", binout, "kernel/kernel.asm"]
    subprocess.run(cmd, check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    sec, rows = None, []
    for ln in open(out, errors="replace"):
        m = re.match(r'^\s*(\d+) ([0-9A-F]{8})? *(<res ([0-9A-Fa-f]+)h>)?'
                     r' *(?:<\d+>)? ?(.*)$', ln)
        if not m:
            continue
        addr, res, src = m.group(2), m.group(4), (m.group(5) or "")
        s = src.strip()
        sm = re.match(r'^section\s+(\.[A-Za-z0-9_]+)', s)
        if sm:
            sec = sm.group(1)
            continue
        if sec != ".lowbss" or not addr:
            continue
        lab = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)', s)
        rows.append((int(addr, 16), int(res, 16) if res else 0,
                     lab.group(1) if lab else ""))
    for p in (out, binout):
        if os.path.exists(p):
            os.remove(p)
    rows.sort()
    return rows


for label, defines in (("kern_big", ("-DKERN_BIG",)),
                       ("kern_small", ("-DKERN_SMALL",))):
    rows = lowbss(defines)
    at = {l: (a, sz) for a, sz, l in rows if l}

    want_off = 0
    for name, size in WANT:
        if name not in at:
            check(False, "%s: %s is in .lowbss" % (label, name),
                  "the window is what stage B put at the bottom of the rung",
                  got="absent", want="present")
            continue
        off, sz = at[name]
        check(off == want_off, "%s: %s at .lowbss+%d" % (label, name, want_off),
              "the three have to be the rung's FIRST bytes, so that they and "
              "the FAT window under them are one dead region - see this "
              "file's header for why nothing else would catch a slide",
              got=off, want=want_off)
        check(sz == size, "%s: %s is %d bytes" % (label, name, size),
              "the window's size is what SPEC.md 2.1.2's 8,192 is computed "
              "from; a resize moves the total and stage C's headroom with it",
              got=sz, want=size)
        want_off += size

    total = sum(s for _, s in WANT)
    check(want_off == total, "%s: the window is contiguous, %d bytes"
          % (label, total),
          "a gap between them is a gap in the region the overlay spills "
          "through", got=want_off, want=total)
    check((FAT_BYTES + total) % 512 == 0,
          "%s: FAT window + window is 512-aligned" % label,
          "every disk-visible base is 512-aligned (SPEC.md 2.1.1) and the "
          "overlay arrives on the kernel's own int 13h read",
          got=(FAT_BYTES + total) % 512, want=0)

done("lowwin")
