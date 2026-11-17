#!/usr/bin/env python3
"""BOUNCE BONANZA - option A's model ALONE on the falling ball (the occlusion deep-dive, 2026-11-17).  NOT a
build input.  Over occmc's sampled VOID positions, the analytic model (front cells to depth 2, 3, 4; a cell
it cannot read passed over) with NO record, against today's rule: how much of the ball it gets wrong.  This
is the error of option A3R+V's void positions when they keep no residual record.

    python3 docs/plans/bounce-bonanza/occaskip.py [course.bbc ...]
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import occmc as M  # noqa: E402
import occproto as P  # noqa: E402
B = P.B
for path in (sys.argv[1:] or P.course_paths()):
    c = B.compile_course(path)
    pos, n, nf = M.sample(c, 3000, 300)
    for d in (2, 3, 4):
        An = P.Analytic(c, d)
        ov = dm = g = k = 0
        for (px, py, sb, zb, air), (kind, cell) in pos.items():
            if kind != B.KIND_VOID or cell in c.slabcells:
                continue
            bp = B.ball_pixels(px, py)
            hs = P.hidden_set(c, sb, zb, px, py, bp)
            a = An.hidden(cell[0], cell[1], zb, 0, bp, skip=True)
            k += 1
            o = len(hs - a) / len(bp)
            m = len(a - hs) / len(bp)
            ov += o
            dm += m
            g += (o + m) > 0.25
        print('%s depth %d: %d sampled VOID positions, the analytic model alone (no record): OVER %.2f%% '
              'WRONG-HIDE %.2f%% frames over a quarter wrong %.2f%%' % (c.name, d, k, 100 * ov / k, 100 * dm / k,
                                                                      100 * g / k))
    sys.stdout.flush()
