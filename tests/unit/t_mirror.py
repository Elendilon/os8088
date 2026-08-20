#!/usr/bin/env python3
"""A constant written down twice must say the same thing in both places.

    python3 tests/unit/t_mirror.py

There is no linker in this tree (SPEC.md: everything is `nasm -f bin`), so
nothing resolves a symbol across two files.  When the kernel, the boot sector,
the SDK and the host tools all need the same number, the number is TYPED OUT
in each of them - and CLAUDE.md names the consequence in two separate places:

    "APP_MAX_SIZE is mirrored in kernel/kernel.asm, apps/os88api.inc and
     tools/os88pkg.py - change them together and rebuild every .o88."

    "Two files carry KERNEL_SEG - kernel/kernel.asm and boot/boot.asm - plus
     apps/os88api.inc, because it is baked into every package's far-call
     targets."

Both are instructions to a human to remember something, which is the same
class of gate as *"sort the %defines by address and look for a duplicate"* and
fails the same way.  A half-applied change assembles perfectly: the boot
sector loads the kernel to one segment and the kernel believes it is at
another, and what you get is a machine that dies before the first pixel with
nothing to read.

THE LIST MAINTAINS ITSELF, which is the point.  Nothing here enumerates which
constants are mirrored - it takes every `NAME equ VALUE` from each file and
checks that any name defined in MORE THAN ONE of them agrees everywhere.  So
a constant that becomes mirrored tomorrow is covered tomorrow, with nobody
remembering to add it.  Today that is 20 names across the kernel and the SDK,
including `KERNEL_SEG`, `APP_MAX_SIZE`, `TITLE_H`, `MBAR_H`, the colour
indices and the SPEC.md 57 debug-registry tags.

The host tools are checked too, for the two constants they carry.  Those are
Python, so they cannot `%include` anything and are the most likely of all of
them to be left behind.

ONE LIMITATION, stated so nobody trusts it further: a definition inside a
`%if` is read at its first spelling, so a constant that legitimately differs
per build would be compared at one arm.  None does today; if one ever should,
put it in DIVERGENT below with the reason rather than deleting the check.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from harness import check, done                           # noqa: E402

ASM = ["kernel/kernel.asm", "kernel/splash.inc", "boot/boot.asm",
       "boot/boothd.asm", "apps/os88api.inc", "apps/os88ui.inc",
       "drivers/os88drv.inc"]

# Constants a host tool spells out for itself, and where the truth lives.
PY_MIRROR = {
    "KERNEL_SEG":   ["tools/os88sym.py", "tools/os88marty.py"],
    "APP_MAX_SIZE": ["tools/os88pkg.py"],
}

# Names that are DELIBERATELY different between two files. Empty today. A row
# here is a decision, so give the reason - an unexplained exemption is how a
# real divergence gets filed as an intended one.
DIVERGENT = {}

EQU = re.compile(r"^([A-Z][A-Z0-9_]*)\s+equ\s+([^\s;]+)", re.M)
PYCONST = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*([^\s#]+)", re.M)


def num(v):
    """The value as an int where that is possible, else the text."""
    t = v.strip().rstrip("hH")
    try:
        if v.lower().startswith("0x"):
            return int(v, 16)
        if v.lower().endswith("h"):
            return int(t, 16)
        return int(v, 0)
    except ValueError:
        return v.strip()


def defs(rel, pattern):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return {}
    with open(path, errors="replace") as f:
        src = f.read()
    out = {}
    for name, val in pattern.findall(src):
        out.setdefault(name, num(val))          # first spelling wins - see above
    return out


def main():
    tables = {rel: defs(rel, EQU) for rel in ASM}

    where = {}
    for rel, d in tables.items():
        for name, val in d.items():
            where.setdefault(name, []).append((rel, val))

    mirrored = {n: v for n, v in where.items() if len(v) > 1}
    for name, places in sorted(mirrored.items()):
        if name in DIVERGENT:
            continue
        vals = {v for _, v in places}
        check(len(vals) == 1,
              "%s agrees across %s" % (name, ", ".join(p for p, _ in places)),
              "there is no linker here - a constant mirrored in two files is "
              "two constants, and a half-applied change assembles cleanly in "
              "both. If this divergence is deliberate, put it in DIVERGENT",
              got="; ".join("%s=%s" % (p, v) for p, v in places),
              want="one value")

    # ...and the Python side, which cannot include anything at all.
    truth = tables["kernel/kernel.asm"]
    pychecked = 0
    for name, tools in PY_MIRROR.items():
        if name not in truth:
            check(False, "%s is defined in kernel/kernel.asm" % name,
                  "PY_MIRROR names it as the authority; if it moved, point this at "
                  "the new home rather than dropping the check")
            continue
        for rel in tools:
            got = defs(rel, PYCONST).get(name, "<not defined>")
            check(got == truth[name], "%s in %s matches the kernel" % (name, rel),
                  "a host tool with a stale copy validates or builds against a "
                  "kernel that is not this one (CLAUDE.md names both of these)",
                  got=got, want=truth[name])
            pychecked += 1

    print("t_mirror: %d names mirrored across %d asm files, %d host-tool copies"
          % (len(mirrored), len(ASM), pychecked))
    done("t_mirror")


if __name__ == "__main__":
    main()
