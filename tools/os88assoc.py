#!/usr/bin/env python3
"""Where the association tables are on a running machine (SPEC.md 54.2.3).

They used to be `assoc_stem`, `assoc_glyph` and `assoc_ext` in the kernel's
.text, so a test read them by symbol. Since 54.2.3 they live in the icon
store's purgeable claim, at fixed offsets (AT_STEM, AT_GLYPH, AT_EXT,
AT_CLUS, AT_DRV in kernel/disk.inc) from the claim's base, and a machine
whose store has been shed has no tables at all.

    base = os88assoc.table(m, "AT_STEM")   # linear address, or None

`m` is an os88marty instance; under kern_mega the claim is a selector, so the
base goes through `m.lin` when the instance has one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88sym                                             # noqa: E402

NAMES = ("AT_STEM", "AT_GLYPH", "AT_EXT", "AT_CLUS", "AT_DRV")


def counts():
    """(ASSOC_NAPP, ASSOC_NEXT) of the kernel the symbols describe."""
    eq = os88sym.equates()
    return eq["ASSOC_NAPP"], eq["ASSOC_NEXT"]


def table(m, name):
    """Linear address of table `name` in the claim, or None with no claim."""
    if name not in NAMES:
        raise ValueError("%s is not an association table" % name)
    seg = int.from_bytes(m.read(os88sym.linear("ico_seg"), 2), "little")
    if not seg:
        return None
    off = os88sym.equates()[name]
    lin = getattr(m, "lin", None)
    return lin(seg, off) if lin else (seg << 4) + off
