#!/usr/bin/env python3
"""kern_dos's refusal table has to cover the SDK's whole API table.

    python3 tests/unit/t_kdapi.py

`KERNEL_SEG` is kern_dos's OWN segment (`kerndos/kdlayout.inc`), so every
`call OSAPI_X` that survives into that image is a far call to `KD_SEG:0xNNNN`.
`apps/dos/dos.asm` is included whole and has ~96 of them; wave 2 measured the
LOAD path at 21 procs reaching none, and the RUN path then reached one -
`dos_getkey` polls `dos_mou_read`, which is every DOS program that waits for a
keystroke.  It presented as a machine spinning in the ROM with a key already
in the BIOS ring, and it took a day to find.

So `kerndos/kdos.asm` lays a cell at every published offset and each one
REFUSES (`stc`/`retf`, SPEC.md 20.8's published meaning).  That turns a wild
jump into the middle of the disk layer into a wrong ANSWER, which is
diagnosable - and it only works if the table's two ends still describe
`apps/os88api.inc`.  They are two constants in a different file, so this is
`t_mirror.py`'s subject with a derivation on one side instead of a literal.

WHAT IT CHECKS

  1 `KD_API_LO` is the LOWEST `KERNEL_SEG:0x....` offset the SDK publishes.
  2 `KD_API_HI` is the HIGHEST.
  3 every published offset lands inside the span AND on an 8-byte boundary
    from `KD_API_LO` - a cell at an odd offset would be entered mid-row.
  4 the span does not reach down into kern_dos's fixed header (0x0000..0x0007),
    which is what leaves room for it.

It is HOST-SIDE and needs no build: both files are source.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SDK = os.path.join(ROOT, "apps", "os88api.inc")
KDOS = os.path.join(ROOT, "kerndos", "kdos.asm")
HDR_END = 8                     # KD_H_JMP/KD_H_LBP/KD_H_LBSZ, kdlayout.inc


def fail(msg):
    print("t_kdapi: FAIL: %s" % msg)
    sys.exit(1)


def main():
    cells = {}
    for ln in open(SDK):
        m = re.match(r"\s*%define\s+(OSAPI_\w+)\s+KERNEL_SEG:(0x[0-9A-Fa-f]+)",
                     ln)
        if m:
            cells[m.group(1)] = int(m.group(2), 16)
    if len(cells) < 100:
        fail("only %d OSAPI_* cells found in apps/os88api.inc - the regex no "
             "longer matches how they are spelled" % len(cells))

    src = open(KDOS).read()
    got = {}
    for name in ("KD_API_LO", "KD_API_HI"):
        m = re.search(r"^%s\s+equ\s+(0x[0-9A-Fa-f]+)" % name, src, re.M)
        if not m:
            fail("kerndos/kdos.asm defines no %s - the refusal table is gone, "
                 "and with it the only thing between a stray kernel call and "
                 "the middle of the disk layer" % name)
        got[name] = int(m.group(1), 16)

    lo, hi = min(cells.values()), max(cells.values())
    if got["KD_API_LO"] != lo:
        fail("KD_API_LO is 0x%04X and the SDK's lowest cell is 0x%04X (%s). "
             "A table that starts too high leaves the cells under it as "
             "whatever kern_dos has there"
             % (got["KD_API_LO"], lo,
                next(n for n, v in cells.items() if v == lo)))
    if got["KD_API_HI"] != hi:
        fail("KD_API_HI is 0x%04X and the SDK's highest cell is 0x%04X (%s). "
             "A cell published above the table is a far call into kern_dos's "
             "own code with the caller's registers"
             % (got["KD_API_HI"], hi,
                next(n for n, v in cells.items() if v == hi)))
    if lo < HDR_END:
        fail("the SDK publishes a cell at 0x%04X, which is inside kern_dos's "
             "fixed header (0x0000..0x%04X) - the two cannot both be there, "
             "and kdlayout.inc's KD_H_* is what the stub jumps to"
             % (lo, HDR_END - 1))

    for name, off in sorted(cells.items(), key=lambda kv: kv[1]):
        if (off - lo) % 8:
            fail("%s is at 0x%04X, which is %d bytes past 0x%04X - not a "
                 "multiple of the 8-byte cell, so the refusal table's row "
                 "would be entered in the middle"
                 % (name, off, off - lo, lo))

    print("t_kdapi: ok - %d cells, 0x%04X..0x%04X, %d refusal rows"
          % (len(cells), lo, hi, (hi - lo) // 8 + 1))


if __name__ == "__main__":
    main()
