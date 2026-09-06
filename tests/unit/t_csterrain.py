#!/usr/bin/env python3
"""Every object built on a HILL model carries CSO_TERRAIN (SPEC.md 88.13.1).

The Buildings density refuses objects before they are transformed, and
CSO_TERRAIN is what exempts the world's own surface from it - a mountain
range is not scenery you thin out to buy frames. The bit is on the OBJECT
rather than the model, because cs_consider tests it in the word it has
already loaded; the cost of that choice is that a new hill can be added and
the flag forgotten, and nothing would say so - the mountain would simply
disappear at Buildings = None.

So this is the gate for that: the hill MODELS are exactly what the CS_HILL
macro makes (plus Paris' Montmartre, which predates it), and every CS_OBJ
row naming one has to carry the flag.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    worlds = sorted(glob.glob(os.path.join(ROOT, "apps", "skies", "csw_*.inc")))
    hills = {"cs_m_hill"}                       # Montmartre, written by hand
    for f in worlds:
        for line in open(f):
            m = re.match(r"\s*CS_HILL\s+(\w+)", line)
            if m:
                hills.add(m.group(1))
    if len(hills) < 2:
        sys.exit("t_csterrain: no CS_HILL models found - has the macro moved?")
    bad, seen = [], 0
    for f in worlds:
        for n, line in enumerate(open(f), 1):
            m = re.match(r"\s*CS_OBJ\s+(\w+)\s*,\s*(\w+)\s*,(.*)$", line)
            if not m:
                continue
            if m.group(1) not in hills and m.group(2) not in hills:
                continue
            seen += 1
            if "CSO_TERRAIN" not in m.group(3):
                bad.append("%s:%d %s" % (os.path.basename(f), n, m.group(1)))
    if bad:
        sys.exit("t_csterrain: hill object(s) without CSO_TERRAIN - they would\n"
                 "  vanish at Buildings = None (SPEC.md 88.13.1):\n    "
                 + "\n    ".join(bad))
    print("  csterrain: %d hill model(s), %d object(s), every one CSO_TERRAIN"
          % (len(hills), seen))


if __name__ == "__main__":
    main()
