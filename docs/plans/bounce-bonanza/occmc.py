#!/usr/bin/env python3
"""BOUNCE BONANZA - where the ball REALLY goes, against where the reach says it
can (the occlusion deep-dive, 2026-11-17).  NOT a build input; nothing in
`make` runs it.

A Monte Carlo over the binding model (tools/bbcourse.py's Physics, the guest's
step exactly): from random floor cells, at random ground velocities, with every
ball, random held arrows, Hops and Grip, until the ball falls or N steps pass.
Every step's position is kept as the guest's occluder pass sees it (px, py,
s_b, z_b, air).  Then, against the SHIPPED merged records:
  - the records some sampled position lays a pixel of (a LOWER bound on what a
    perfect reach would need; the conservative reach of SPEC.md 130.11.4.4 is
    the upper bound, and the truth lies between);
  - the same over the non-VOID positions only;
  - for every sampled position in a VOID cell, the share of the ball's lit
    pixels the rule hides today - so option V's visual cost is weighed by
    where balls actually fall rather than by the reach's whole box.

    python3 docs/plans/bounce-bonanza/occmc.py [--trials N] [--steps N] [course.bbc ...]
"""
import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import occproto as P  # noqa: E402
B = P.B


def sample(c, trials, steps, seed=1):
    rng = random.Random(seed)
    floors = sorted(k for k, v in c.cells.items()
                    if v[2] & 15 in (B.KIND_FLOOR, B.KIND_GOAL) and k not in c.pcell)
    pos = {}
    arrows = [0, B.K_L, B.K_R, B.K_U, B.K_D, B.K_L | B.K_U, B.K_L | B.K_D, B.K_R | B.K_U, B.K_R | B.K_D]
    nsteps = nfall = 0
    for t in range(trials):
        mat = rng.randrange(3)
        p = B.Physics(c, play=False, mat=mat)
        wx, wy = rng.choice(floors)
        v = B.VMAXG
        p.poke(wx, wy, rng.randint(-v, v), rng.randint(-v, v))
        held, left = 0, 0
        f0 = p.nfall + p.nret
        for i in range(steps):
            if left <= 0:
                held = rng.choice(arrows)
                left = rng.randint(4, 40)
            left -= 1
            k = held
            r = rng.random()
            if r < 0.06:
                k |= B.K_HOP
            elif r < 0.09:
                k |= B.K_GRIP
            try:
                p.step(k)
            except Exception:
                break
            nsteps += 1
            if p.nfall + p.nret != f0:
                nfall += 1
                break
            if p.tube:
                continue
            cell = (p.gx >> 12, p.gy >> 12)
            cl = c.cells.get(cell)
            kind = cl[2] & 15 if cl else B.KIND_VOID
            key = (p.px, p.py, p.sb, p.zb, int(bool(p.air)))
            pos[key] = (kind, cell)
    return pos, nsteps, nfall


def rec_boxes(c):
    out = []
    for r in c.records:
        xs = [x for x, _ in r["pix"]]
        ys = [y for _, y in r["pix"]]
        out.append((r, min(xs), max(xs), min(ys), max(ys)))
    return out


def errors(c, pos, ghs):
    """the visual error of each treatment over the sampled VOID positions (not the lift's shaft), as the
    mean share of the ball's lit pixels a frame gets WRONG against today's rule: OVER - drawn over what
    hides them today; DIM - ghosted though nothing hides them today.  ghs: {name: ghost heights}; '(c)'
    is no record and no ghost"""
    rows = {k: [0.0, 0.0, 0, 0, 0] for k in ["(c)", "A(void)"] + list(ghs)}
    An = P.Analytic(c, 2)
    aall = [0.0, 0.0, 0, 0, 0]               # option A everywhere: the NON-void positions it can read
    for (px, py, sb, zb, air), (kind, cell) in pos.items():
        if kind == B.KIND_VOID or cell in c.slabcells:
            continue
        m = 0 if air else B.CLIMB
        bp = B.ball_pixels(px, py)
        hs = P.hidden_set(c, sb, zb + m, px, py, bp)         # (the rule with the margin: z_b + m < top)
        a = An.hidden(cell[0], cell[1], zb, m, bp)
        aall[3] += 1
        if a is None:
            continue
        ov, dm = len(hs - a) / float(len(bp)), len(a - hs) / float(len(bp))
        aall[0] += ov
        aall[1] += dm
        aall[2] += 1
        aall[4] += ov + dm > 0.25
    errors.aall = aall
    n = 0
    doomed = {k: 0 for k in ghs}
    for (px, py, sb, zb, air), (kind, cell) in pos.items():
        if kind != B.KIND_VOID or cell in c.slabcells:
            continue
        n += 1
        bp = B.ball_pixels(px, py)
        hs = P.hidden_set(c, sb, zb, px, py, bp)
        f = len(hs) / float(len(bp))
        a = An.hidden(cell[0], cell[1], zb, 0, bp)
        if a is not None:                   # (unreadable: the cell keeps its records, exact)
            ov, dm = len(hs - a) / float(len(bp)), len(a - hs) / float(len(bp))
            rows["A(void)"][0] += ov
            rows["A(void)"][1] += dm
            rows["A(void)"][2] += 1
            rows["A(void)"][4] += ov + dm > 0.25
        rows["(c)"][0] += f
        rows["(c)"][4] += f > 0.25
        for k, gh in ghs.items():
            g = gh.get(cell)
            if g and zb < g[0]:
                rows[k][1] += 1 - f
                rows[k][2] += 1
                rows[k][4] += 1 - f > 0.25
                if zb < P.thr_of(c, B.Reach(cell[0], cell[1], 0, 0, 0, None)):
                    doomed[k] += 1
            else:
                rows[k][0] += f
                rows[k][4] += f > 0.25
    return n, {k: (v[0] / n, v[1] / n, v[2], doomed.get(k, 0), v[4] / float(n)) for k, v in rows.items()} if n else {}


def analyse(c, pos, gh):
    byb = {}
    for i, r in enumerate(c.records):
        byb.setdefault((r["brow"], r["col"]), []).append(i)
    need_all, need_nv = set(), set()
    vtot = vn = vnone = vfew = 0
    vgh = vgh_none = 0
    gtot = 0.0
    for (px, py, sb, zb, air), (kind, cell) in pos.items():
        m = 0 if air else B.CLIMB
        x4 = px & ~3
        x1, y1 = x4 + B.FOOT_W - 1, py + B.FOOT_H - 1
        hit = []
        for br in range(py >> 3, (y1 >> 3) + 1):
            for bc in range(x4 >> 3, (x1 >> 3) + 1):
                for i in byb.get((br, bc), ()):
                    r = c.records[i]
                    if sb < r["s"] and zb + m < r["top"]:
                        hit.append(i)
        if not hit and kind != B.KIND_VOID:
            continue
        laid = set()
        bp = None
        for i in hit:
            pix = [q for q in c.records[i]["pix"] if x4 <= q[0] <= x1 and py <= q[1] <= y1]
            if pix:
                need_all.add(i)
                if kind != B.KIND_VOID:
                    need_nv.add(i)
                laid.update(pix)
        if kind == B.KIND_VOID and cell not in c.slabcells:
            bp = B.ball_pixels(px, py)
            f = len(laid & bp.keys()) / float(len(bp))
            vn += 1
            vtot += f
            vnone += f == 0
            vfew += f < 0.25
            g = gh.get(cell)
            if g and zb < g[0]:
                vgh += 1
                gtot += f
                vgh_none += f == 0
    return {"need": len(need_all), "need_nv": len(need_nv), "void_pos": vn,
            "void_hidden": vtot / vn if vn else 0, "void_none": vnone / float(vn) if vn else 0,
            "ghosted": vgh, "ghost_hidden": gtot / vgh if vgh else 0,
            "ghost_none": vgh_none / float(vgh) if vgh else 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("courses", nargs="*")
    ap.add_argument("--trials", type=int, default=4000)
    ap.add_argument("--steps", type=int, default=300)
    a = ap.parse_args()
    for path in a.courses or P.course_paths():
        c = B.compile_course(path)
        pos, n, nf = sample(c, a.trials, a.steps)
        gh = P.ghost_heights(c)
        r = analyse(c, pos, gh)
        nv = sum(1 for v in pos.values() if v[0] == B.KIND_VOID)
        print("%s: %d trials, %d steps (%d ended in a fall); %d distinct positions (%d in VOID cells)"
              % (c.name, a.trials, n, nf, len(pos), nv))
        print("  shipped rule records %d; laid somewhere by a sampled position %d (%.0f%%); by a non-VOID one %d "
              "(%.0f%%)" % (len(c.records), r["need"], 100.0 * r["need"] / len(c.records), r["need_nv"],
                            100.0 * r["need_nv"] / len(c.records)))
        print("  sampled VOID positions: today the rule hides %.0f%% of the ball on average, none of it at %.0f%%; "
              "of them option V ghosts %d, where today hides %.0f%% on average and none at %.0f%%"
              % (100 * r["void_hidden"], 100 * r["void_none"], r["ghosted"], 100 * r["ghost_hidden"],
                 100 * r["ghost_none"]))
        ghs = {"V(any)": gh, "V(25%)": P.ghost_heights_q(c, 0.25), "V(50%)": P.ghost_heights_q(c, 0.5)}
        n_, er = errors(c, pos, ghs)
        print("  visual error over %d sampled VOID positions, the mean share of the ball wrong a frame "
              "(OVER: drawn over its occluder; DIM: ghosted though nothing hides it):" % n_)
        for k, (ov, dm, ng, nd, gross) in er.items():
            print("    %-7s OVER %5.1f%%  DIM %5.1f%%  frames over a quarter of the ball wrong %5.1f%%;  ghosted %d "
                  "positions (%d below every floor within two tiles)" % (k, 100 * ov, 100 * dm, 100 * gross, ng, nd))
        aa = errors.aall
        if aa[2]:
            print("    option A everywhere, over the %d sampled NON-void positions (%d readable): OVER %.1f%%  WRONG-HIDE "
                  "%.1f%%  frames over a quarter wrong %.1f%%" % (aa[3], aa[2], 100 * aa[0] / aa[2], 100 * aa[1] / aa[2],
                                                                  100 * aa[4] / aa[2]))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
