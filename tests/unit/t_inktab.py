#!/usr/bin/env python3
"""Paint's three ink classes ARE the kernel's `gfx_inktab` (SPEC.md 39.4, 42.23.1).

    python3 tests/unit/t_inktab.py

A canvas of one bit stores what a 1bpp SCREEN shows, which means Paint has to
agree with the kernel about what each of the sixteen colours looks like there:
solid black, solid white, or the 50% dither.  The kernel says it once, in
`kernel/viddet.inc`'s `gfx_inktab` - 00 / 01 / FF a colour - and Paint says it
again as two bit-masks, `PT_WHT16` and `PT_DTH16`, because a package cannot
read a kernel table at assembly time and reading it at run time would cost a
far call per pixel.

**THE FIRST VERSION OF THOSE MASKS WAS A GUESS AND IT WAS WRONG**, which is
why this file exists.  It was one word, `PT_LIT16` = colours 7..15 white, on
the reasoning that the bright half lights up.  `gfx_inktab` says six of them -
light grey, dark grey, light blue, light green, light cyan and light magenta -
are the DITHER class and only light red, yellow and white are solid.  So a
one-bit canvas stored six colours as flat white that every 1bpp screen in the
system draws as a checkerboard, and nothing in the tree compared the two.

It is a `db` table rather than an `equ`, so `tests/unit/t_mirror.py` - which
maintains its own list by taking every `NAME equ VALUE` - cannot see it.  That
is the whole reason this is a file of its own rather than a row there.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KERN = os.path.join(ROOT, "kernel", "viddet.inc")
PAINT = os.path.join(ROOT, "apps", "paint", "paint.asm")


def inktab():
    """The kernel's 00/01/FF per colour, from the db rows after the label."""
    src = open(KERN).read()
    m = re.search(r"^gfx_inktab:\s*$", src, re.M)
    if not m:
        sys.exit("t_inktab: kernel/viddet.inc has no gfx_inktab label")
    out = []
    for line in src[m.end():].split("\n"):
        line = line.split(";")[0].strip()
        if not line:
            if out:
                break
            continue
        if not line.startswith("db "):
            break
        for tok in line[3:].split(","):
            out.append(int(tok.strip(), 16))
    if len(out) != 16:
        sys.exit("t_inktab: gfx_inktab read as %d entries, wanted 16 - the "
                 "table's shape moved and this reader did not" % len(out))
    return out


def mask(name):
    src = open(PAINT).read()
    m = re.search(r"^%s\s+equ\s+([01]{16})b\b" % name, src, re.M)
    if not m:
        sys.exit("t_inktab: apps/paint/paint.asm has no `%s equ <16 bits>b`"
                 % name)
    return int(m.group(1), 2)


def main():
    tab = inktab()
    for v in tab:
        if v not in (0x00, 0x01, 0xFF):
            sys.exit("t_inktab: gfx_inktab holds %02X, which is not one of "
                     "SPEC.md 39.4's three classes" % v)
    want_wht = sum(1 << i for i, v in enumerate(tab) if v == 0xFF)
    want_dth = sum(1 << i for i, v in enumerate(tab) if v == 0x01)
    got_wht, got_dth = mask("PT_WHT16"), mask("PT_DTH16")

    fails = []
    for nm, want, got in (("PT_WHT16", want_wht, got_wht),
                          ("PT_DTH16", want_dth, got_dth)):
        if want != got:
            bad = [i for i in range(16) if ((want >> i) & 1) != ((got >> i) & 1)]
            fails.append("%s is %016db and gfx_inktab says %016db - colour(s) "
                         "%s disagree" % (nm, int(bin(got)[2:]),
                                          int(bin(want)[2:]), bad))
    if got_wht & got_dth:
        fails.append("PT_WHT16 and PT_DTH16 overlap on colour(s) %s - a colour "
                     "is one class or another"
                     % [i for i in range(16) if (got_wht >> i) & (got_dth >> i) & 1])
    print("t_inktab: gfx_inktab -> black %s"
          % [i for i, v in enumerate(tab) if v == 0x00])
    print("t_inktab:               dither %s"
          % [i for i, v in enumerate(tab) if v == 0x01])
    print("t_inktab:               white %s"
          % [i for i, v in enumerate(tab) if v == 0xFF])
    for f in fails:
        print("  FAIL: " + f)
    if fails:
        print("t_inktab: %d FAILED - Paint's masks are a MIRROR of the kernel's "
              "table (SPEC.md 42.23.1); change them together" % len(fails))
        return 1
    print("t_inktab: PASS - Paint's two masks are gfx_inktab, colour for colour")
    return 0


if __name__ == "__main__":
    sys.exit(main())
