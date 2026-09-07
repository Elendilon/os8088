#!/usr/bin/env python3
"""CLEAR SKIES' air keeps out of the circuit (SPEC.md 88.7.6.3).

    python3 tests/unit/t_csair.py

`cs_lifts` is eight rects of lift and sink in metres from the LOCATION's own
centre, so the same weather stands round all nine runways. `CS_LIFTCLR` is
the disc it must keep out of - the circuit, and also where every other test
of this simulator flies, which is the half a flight would find the hard way.

It checks the NEAREST CORNER and not the centre: a rect 3,000 m out that
reaches 900 m toward the field is 2,100 m out, and the centre would have
passed it.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "apps", "skies", "csflight.inc")
ASM = os.path.join(ROOT, "apps", "skies", "skies.asm")
bad = []


def check(cond, what):
    print("  [%s] %s" % ("PASS" if cond else "FAIL", what))
    if not cond:
        bad.append(what)


def equ(path, name):
    m = re.search(r"^%s\s+equ\s+(-?\d+)" % name, open(path).read(), re.M)
    if not m:
        raise SystemExit("t_csair: %s is not defined in %s" % (name, path))
    return int(m.group(1))


def main():
    text = open(SRC).read()
    clr, n = equ(SRC, "CS_LIFTCLR"), equ(SRC, "CS_NLIFT")
    m = re.search(r"^cs_lifts:\n((?:\s*dw .*\n)+)", text, re.M)
    check(bool(m), "cs_lifts is a table of dw rows in csflight.inc")
    if not m:
        return 1
    rows = []
    for line in m.group(1).splitlines():
        v = [int(t) for t in line.split(";")[0].split("dw")[1].split(",")]
        rows.append(v)
    check(len(rows) == n, "CS_NLIFT is %d and the table has %d" % (n, len(rows)))
    check(all(len(r) == 5 for r in rows),
          "every row is CSL_SIZE's five words (%s)"
          % [len(r) for r in rows if len(r) != 5])

    for i, (dx, dz, hw, hd, rate) in enumerate(rows):
        # the nearest point of the rect to the field, which is what a glider
        # in the circuit would meet first
        nx = max(0, abs(dx) - hw)
        nz = max(0, abs(dz) - hd)
        d = (nx * nx + nz * nz) ** 0.5
        check(d >= clr,
              "rect %d (%+d,%+d %dx%d) keeps its nearest corner out of the "
              "circuit: %d m against CS_LIFTCLR %d"
              % (i, dx, dz, 2 * hw, 2 * hd, d, clr))
        check(hw > 0 and hd > 0, "rect %d has size (%d x %d)" % (i, hw, hd))
        check(rate != 0, "rect %d does something (rate %d)" % (i, rate))

    check(any(r[4] > 0 for r in rows) and any(r[4] < 0 for r in rows),
          "...and there is both lift and sink to find (%d up, %d down)"
          % (sum(1 for r in rows if r[4] > 0), sum(1 for r in rows if r[4] < 0)))
    # the swoop's two ends are the ones the tone slides between
    lo, hi = equ(ASM, "CS_SWOOPLO"), equ(ASM, "CS_SWOOPHI")
    t, d = equ(ASM, "CS_SWOOPT"), equ(ASM, "CS_SWOOPD")
    check(lo + t * d == hi,
          "the swoop lands exactly on its far end: %d + %d x %d = %d, want %d"
          % (lo, t, d, lo + t * d, hi))
    print("  %s" % ("ok" if not bad else "FAILED: %d" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
