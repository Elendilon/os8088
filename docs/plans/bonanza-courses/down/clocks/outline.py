#!/usr/bin/env python3
"""a fast PROXY for what a frame costs the occluder masks (no compile): each frame's geometry pixels on a
block-aligned tile, its width, the blocks it touches and how many of them it covers only PARTLY (a partly
covered block is the one that needs an occluder mask, SPEC.md 137.15.5).  crystal and Little Hop's frogs for
scale.    python3 docs/plans/bonanza-courses/down/clocks/outline.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "..", "tools"))
sys.path.insert(0, HERE)
import bbcourse as B                                   # noqa: E402
import frames as F                                     # noqa: E402

F.install(B)
names = ["crystal", "pin", "frogl", "frogr", "frogb"] + [n for vs in F.CONCEPTS.values() for n, _a in vs]
for nm in names:
    tops = {}
    B.clock_face_pix({"at": (0, 0), "z4": 0, "ndig": 2, "frame": nm}, 32, 56, tops=tops)
    blocks = {}
    for (x, y) in tops:
        blocks.setdefault((x >> 3, y >> 3), set()).add((x & 7, y & 7))
    xs = [x for x, _y in tops]
    print("%-8s geometry px %4d, width %2d, blocks %2d, partly covered %2d" % (
        nm, len(tops), max(xs) - min(xs) + 1, len(blocks), sum(1 for s in blocks.values() if len(s) < 64)))
