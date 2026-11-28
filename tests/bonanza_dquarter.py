#!/usr/bin/env python3
"""BONANZA's QUARTER-UNIT HEIGHTS in the guest (SPEC.md 137.48): the package's own routines under unicorn
against tools/bbcourse.py's model on a course of quarter steps - tests/bonanza_dsplit.py's method, and its
harness (Guest, start, poke, run): after EVERY step the guest's state is read out of its own bss and compared
EXACTLY with the model's.

    python3 tests/bonanza_dquarter.py [--runs N] [--seed S] [--reds]

  1  CELLS: bz_cexp on QDEV's, BENCH's and SUMMIT's STORED forms equals their RAM forms - the CELLS rule's
     quarter-unit corner and bias (SPEC.md 137.48.3) on a quarter course and on the two REBASED ones.
  2  SCRIPTED: a half-unit step rolled up; a 3/4-unit step that stops a rolling ball (a WALL); rubber's Hop
     onto it (it lands); steel's against it; a quarter ramp climbed; a fall into a pit whose kill height is a
     quarter course's (12 quarter units under its lowest corner).
  3  FUZZ: N runs from random states beside QDEV's quarter steps, every step.
  4  THE DEMOS: MOON's and PEAK's shipped demos replayed through the guest, every step against the
     model - every family those courses use (PEAK's springs found the one 16 z0 the first pass missed), on a
     course written in half units and on PEAK, rebased 24.

--reds: each red arm (a broken package) must go red: `h16` (bz_h4's flat floor back to 16 z0), `kill4` (the
VOID kill test back to 4 z0 px), `cells79` (the CELLS rule's bias back to 79h).  A family's code cannot have a
red arm here - DS.fam_load loads the BUILT family parts (build/bzf-<name>.bin), not a patched tree - so the
SPRING's 16 z0 (leg 4's find) has its red in the record instead: bonanzamega, on 454746ed0, failed on it.
"""
import argparse
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402
import bonanza_dsplit as DS    # noqa: E402

# THE QUARTER DEV COURSE: 0 -> 1/2 (rolled up) -> 1 1/4 (a 3/4 step: Hopped, never rolled) -> a quarter ramp to
# 2 1/4 -> a pit (its kill a quarter course's) and the goal
QDEV = ('course QDEV "Quarter Dev"\nwidth 64\nfloor rect 3 4 6 8 flat 0\nfloor rect 6 4 8 8 flat 0.5\n'
        'floor rect 8 4 10 8 flat 1.25\nfloor rect 10 4 12 8 ramp x 10 12 1.25 2.25\nfloor rect 12 4 15 8 flat 2.25\n'
        'hole tile 12 7\ngoal rect 14 4 15 8 flat 2.25\nstart 4 5\n')

REDS = {
    "h16": [("bzphys.inc", ".flat:\n    mov al, [si]\n    cbw\n    shl ax, 1\n    shl ax, 1\n    shl ax, 1\n    ret",
             ".flat:\n    mov al, [si]\n    cbw\n    shl ax, 1\n    shl ax, 1\n    shl ax, 1\n    shl ax, 1\n    ret")],
    "kill4": [("bzphys.inc", "    cmp ax, -256                ; 4 z0: the fall it always was)\n    jne .kq",
               "    cmp ax, -256                ; 4 z0: the fall it always was)\n    jmp short .kq0\n.kq0:")],
    "cells79": [("bonanza.asm", "    mov al, 73h                 ; z0 + 2 min(0, sx)",
                 "    mov al, 79h                 ; z0 + 2 min(0, sx)")],
}


def scripted():
    rub, stl = BB.MAT_RUBBER, BB.MAT_STEEL
    Rt, D, H = BB.K_R, BB.K_D, BB.K_HOP
    hold = DS.hold
    return [
        ("a half-unit step rolled up", rub, (5, 5, 8 << 8, 8 << 8, 200, 0), hold(Rt, 40), ()),
        ("a 3/4-unit step stops a rolling ball", rub, (7, 5, 8 << 8, 8 << 8, 300, 0), hold(Rt, 40), ("wall",)),
        ("rubber's Hop onto the 3/4-unit step", rub, (7, 5, 4 << 8, 8 << 8, 200, 0),
         hold(Rt, 3) + [Rt | H] + hold(Rt, 40), ("hop", "land")),
        ("steel's Hop against it", stl, (7, 5, 4 << 8, 8 << 8, 200, 0), hold(Rt, 3) + [Rt | H] + hold(Rt, 40),
         ("hop", "wall")),
        ("the quarter ramp climbed", rub, (9, 5, 8 << 8, 8 << 8, 300, 0), hold(Rt, 30), ()),
        ("a fall into the pit, its quarter kill", rub, (12, 6, 8 << 8, 8 << 8, 0, 120), hold(D, 90), ("takeoff",)),
    ]


def fuzz(binp, sym, c, n, seed):
    rnd = random.Random(seed)
    bad, steps = [], 0
    for i in range(n):
        mat = rnd.choice((BB.MAT_RUBBER, BB.MAT_STEEL, BB.MAT_GLASS))
        g, p = DS.start(binp, sym, c, mat)
        wx, wy = rnd.randrange(3, 15), rnd.randrange(4, 8)
        rec = p.prec(wx, wy)
        if rec is None or rec[3] not in (BB.KIND_FLOOR, BB.KIND_GOAL):
            continue
        pu, pv = rnd.randrange(1, 15) << 8, rnd.randrange(1, 15) << 8
        air = rnd.random() < 0.3
        gz = ((BB.Physics.h4(rec, pu >> 8, pv >> 8) << 6) + (rnd.randrange(1, 40) << 8)) if air else None
        v = BB.VMAXG
        DS.poke(g, p, wx, wy, pu, pv, rnd.randrange(-v, v + 1), rnd.randrange(-v, v + 1), int(air), gz)
        keys = []
        while len(keys) < 160:
            keys += [rnd.choice((0, BB.K_U, BB.K_D, BB.K_L, BB.K_R, BB.K_U | BB.K_R, BB.K_D | BB.K_R, BB.K_HOP,
                                 BB.K_R | BB.K_HOP, BB.K_GRIP))] * rnd.randrange(1, 30)
        err, ns, _ev = DS.run(g, p, keys[:160], "fuzz %d (%s, (%d, %d) %d %d)" % (i, BB.MAT_NAMES[mat], wx, wy, pu, pv))
        steps += ns
        if err:
            bad.append(err)
    return bad, steps


def check(n=200, seed=1119, verbose=True, patches=()):
    out = []
    with tempfile.TemporaryDirectory() as td:
        binp, sym = DS.build(td, patches)
        c = BB.compile_course(QDEV, "<QDEV>", _hack={"no_finish": True})
        cs = {"qdev": c}
        for k in ("bench", "summit"):               # (the two REBASED courses, SPEC.md 137.48.1)
            cs[k] = BB.compile_course(os.path.join(BB.COURSE_DIR, k + ".bbc"))
        b = DS.cells_check(binp, sym, cs)
        print("bonanza_dquarter CELLS: bz_cexp on %s's stored forms (BENCH rebased %d units, SUMMIT %d) -> %s" % (
            ", ".join(sorted(cs)), cs["bench"].src.zbase, cs["summit"].src.zbase,
            "; ".join(b) or "each its RAM form, byte for byte"))
        out += b
        for label, mat, pk, keys, want in scripted():
            g, p = DS.start(binp, sym, c, mat)
            DS.poke(g, p, *pk)
            err, ns, ev = DS.run(g, p, keys, label)
            got = sorted({e[0] for e in ev})
            miss = [w for w in want if w not in got]
            if err:
                out.append(err)
            elif miss:
                out.append("%s: the model raised %s, not %s: the run does not exercise what it names" % (label, got,
                                                                                                         miss))
            if verbose:
                print("bonanza_dquarter %-40s %3d steps, events %s: %s" % (label, ns, ",".join(got) or "-",
                                                                         "FAIL" if err or miss else "every step equal"))
        b, steps = fuzz(binp, sym, c, n, seed)
        print("bonanza_dquarter fuzz: %d runs, %d steps beside QDEV's quarter steps (seed %d): %s" % (
            n, steps, seed, "%d differ" % len(b) if b else "every step equal"))
        out += b[:10]
        for name in ("moon", "summit"):         # (PLAYGROUND's leaves this harness's stack unbalanced at step 0
            # at the base too, faec308: its families need what DS.start does not set up - bonanzareplay plays it)
            cd = BB.compile_course(os.path.join(BB.COURSE_DIR, name + ".bbc"))
            dm = BB.parse_bzd(open(os.path.join(ROOT, "apps", "bonanza", "demos", name + ".bzd")).read())
            K = [os.path.basename(q) for q in BB.default_paths()].index(name + ".bbc")
            _K, mat, kt, _fl = BB.decode_log_t(BB.bzd_log(dm, K))
            g, p = DS.start(binp, sym, cd, mat)
            err, ns, _ev = DS.run(g, p, [k for k, _t in kt], "%s's demo" % name.upper(), stop_goal=False)
            print("bonanza_dquarter the %s demo (rebased %d): %d steps: %s" % (name.upper(), cd.src.zbase, ns,
                                                                           err or "every step equal"))
            if err:
                out.append(err)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1119)
    ap.add_argument("--reds", action="store_true", help="every red arm: each must go red")
    a = ap.parse_args()
    R.dev()                             # the BZDEV=1 build (SPEC.md 137.26.6.1)
    if a.reds:
        for name in sorted(REDS):
            bad = check(min(a.runs, 40), a.seed, verbose=False, patches=REDS[name])
            assert bad, "RED ARM %s: the check stayed GREEN against a broken package" % name
            print("bonanza_dquarter red %s: went red (%d): %s" % (name, len(bad), bad[0][:160]))
        return
    bad = check(a.runs, a.seed)
    for b in bad:
        print("FAIL %s" % b)
    assert not bad, "%d difference(s) between the guest and the model" % len(bad)
    print("bonanza_dquarter: PASS")


if __name__ == "__main__":
    main()
