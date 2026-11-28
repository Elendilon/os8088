"""SPEC.md 137.29.12 research: the AV model with (A) a per-VOID-cell FAR LIST (whole front cells past d = 4 the
tool picks, greedily by the residual pixels each hides) and (B) the cheap float (a float front cell counted as a
whole cell at the keys at which the ball's lowest line is above its slab's lowest bottom: per cell, or per
column).  Patches bbcourse.av_residual and measures records / masks / LZB.
usage: avfar.py course base | far DMAX CAP [budget] [nowrong] | float cell|col
  budget: the far list trimmed (last pick first) at each V until the entering-frame proxy (avproxy.py's) at no height
  of V passes the course's own worst under today's model; nowrong: a candidate refused where it hides a
  pixel of V's footprint superset that the rule shows at a height of V's range (WRONG-HIDE kept today's).
  Run from the repository root; each run compiles the course once (BB_CACHE off) and writes its far lists
  as a pickle beside this file, which avdata.py, avproxy.py, avrun.py and avwrong.py read"""
import sys, os, time, struct, collections, pickle
sys.path.insert(0, "tools")
os.environ["BB_CACHE"] = "0"
import bbcourse as B

HERE = os.path.dirname(os.path.abspath(__file__))
NEG = -(1 << 30)
course, mode = sys.argv[1], sys.argv[2]
DMAX = int(sys.argv[3]) if mode == "far" else 4
CAP = int(sys.argv[4]) if mode == "far" else 0
BUD = mode == "far" and "budget" in sys.argv[5:]
NOWRONG = mode == "far" and "nowrong" in sys.argv[5:]
FMODE = sys.argv[3] if mode == "float" else None
STATS = {"far": {}, "fl": 0, "today": 0, "trim": 0}
FLOATS = {}
READ, HALF, COL, FENT = 670, 780, 111, 1360


def whole(grid, wx, wy, fl_ok=False):
    b = grid.raw(wx, wy)
    if b is None:
        return None
    z0, sl, kd, fl = b
    kind = kd & 15
    if kind not in (B.KIND_FLOOR, B.KIND_WALL, B.KIND_GOAL) or fl & B.FL_OBS:
        return None
    isf = kind != B.KIND_GOAL and fl & B.FL_FLOAT
    if isf and not fl_ok:
        return None
    return b, bool(isf)


def far_cands(grid, wx, wy, dmin, dmax):
    out = []
    for d in range(dmin, dmax + 1):
        for i in range(d + 1):
            w = whole(grid, wx + i, wy + d - i)
            if w is None or w[1]:
                continue
            H, X, Y, kr, kl = grid.geom(w[0], wx + wy + d, (wx + i) - (wy + d - i))
            out.append(((i, d - i), [(H, X, Y, kr, True, False, NEG), (H, X, Y, kl, False, False, NEG)]))
    return out


def float_hedges(grid, wx, wy, yb, y0, per_col):
    out = []
    for d in range(1, 5):
        for i in range(d + 1):
            cx, cy = wx + i, wy + d - i
            w = whole(grid, cx, cy, True)
            if w is None or not w[1]:
                continue
            b = w[0]
            fd = FLOATS.get((cx, cy), B.FACE8)
            H, X, Y, kr, kl = grid.geom(b, wx + wy + d, cx - cy)
            sx, sy = B._nib(b[1] & 15), B._nib(b[1] >> 4)
            bc = Y + 16 - 4 * (sx + sy) + fd
            bot_r = lambda x, X=X, bc=bc, kl=kl: bc - B.amodel_f(kl, x - X, True)
            bot_l = lambda x, X=X, bc=bc, kr=kr: bc - B.amodel_f(kr, X - 1 - x, False)
            bmin = min(min(bot_r(x) for x in range(X, X + 16)), min(bot_l(x) for x in range(X - 16, X)))
            if per_col:
                out.append((H, X, Y, kr, True, False, ("col", bot_r, yb + y0 + 1)))
                out.append((H, X, Y, kl, False, False, ("col", bot_l, yb + y0 + 1)))
            else:
                kf = yb + y0 - bmin + 1
                out.append((H, X, Y, kr, True, False, kf))
                out.append((H, X, Y, kl, False, False, kf))
            STATS["fl"] += 1
    return out


def cols_of(front, xlo, xhi):
    out = {}
    for he in front:
        X = he[1]
        lo, hi = (X, X + 15) if he[4] else (X - 16, X - 1)
        kf = he[6] if len(he) > 6 else NEG
        for x in range(max(xlo, lo), min(xhi, hi) + 1):
            k = kf[2] - kf[1](x) if isinstance(kf, tuple) else kf
            out.setdefault(x, []).append((B.amodel_hedge(he[:6], x), he[0], k))
    for v in out.values():
        v.sort()
    return out


def free(cl, y, lo, hi):
    """some key in [lo, hi] at which the column list CL does not hide line y"""
    if cl is None:
        return lo <= hi
    ivs = sorted((k, h - 1) for e, h, k in cl if e <= y and k <= h - 1)
    for a, b in ivs:
        if a > lo:
            break
        if b >= lo:
            lo = b + 1
    return lo <= hi


def pos_pairs(cv, q, y0):
    xl, xh = max(q.xl, 0), min(q.xh, cv.w - 1)
    out = []
    for y, zlo_y, zhi_y in B._av_lines(q, y0, cv.h):
        sr, tr = cv.sbuf[y], cv.tbuf[y]
        for x in range(xl, xh + 1):
            if sr[x] > q.s:
                out.append((x, y, zlo_y, min(zhi_y, tr[x] - 1), sr[x], tr[x]))
    return out


def _table(grid, wx, wy):
    t = {}
    for d in range(1, 5):
        for i in range(d + 1):
            cx, cy = wx + i, wy + d - i
            w = whole(grid, cx, cy)
            if w is None:
                continue
            H, X, Y, kr, kl = grid.geom(w[0], wx + wy + d, cx - cy)
            t[(d, i)] = (H, X, Y, B._nib(w[0][1] & 15), B._nib(w[0][1] >> 4))
    sh = {}
    for (d, i), (H, X, Y, sx, sy) in t.items():
        v = 0
        if d >= 2:
            p1, p2 = t.get((d - 1, i)), t.get((d - 1, i - 1))
            if sx == 0 and p1 and p1[4] == 0 and p1[0] >= H and p1[2] <= Y - 8:
                v |= 1
            if sy == 0 and p2 and p2[3] == 0 and p2[0] >= H and p2[2] <= Y - 8:
                v |= 2
        sh[(d, i)] = v
    return t, sh


def _ov(X, right, w0, w1):
    lo, hi = (X, X + 15) if right else (X - 16, X - 1)
    return max(0, min(hi, 8 * w1 + 7) - max(lo, 8 * w0) + 1)


def proxy_max(grid, q, x0, fl):
    t, sh = _table(grid, q.wx, q.wy)
    fc = [(hes[0][0], hes[0][1]) for hes in fl]
    x4 = (16 * (q.wx - q.wy) + x0 - 8) & ~3
    w0, w1 = x4 >> 3, (x4 + 19) >> 3
    worst = 0
    for z in range(q.zlo, q.zhi + 1, 2):
        cost = 14 * READ + (FENT * len(fc) + 100 if fc else 0)
        for k, (H, X, Y, sx, sy) in t.items():
            if H > z:
                for right, bit in ((True, 1), (False, 2)):
                    ov = _ov(X, right, w0, w1)
                    if ov and not sh[k] & bit:
                        cost += HALF + COL * ov
        for H, X in fc:
            if H > z:
                for right in (True, False):
                    ov = _ov(X, right, w0, w1)
                    if ov:
                        cost += HALF + COL * ov
        worst = max(worst, cost)
    return worst


def my_residual(cv, rcs, grid, x0, y0, depth=None):
    plan = []
    for q in rcs:
        xl, xh = max(q.xl, 0), min(q.xh, cv.w - 1)
        if xl > xh:
            continue
        near = [he + (NEG,) for he in grid.front(q.wx, q.wy)]
        if FMODE:
            near += float_hedges(grid, q.wx, q.wy, q.yb0, y0, FMODE == "col")
        pairs = pos_pairs(cv, q, y0)
        cols = cols_of(near, xl, xh)
        res = [p for p in pairs if free(cols.get(p[0]), p[1], p[2], p[3])]
        sel = []
        if DMAX > 4 and res:
            cands = far_cands(grid, q.wx, q.wy, 5, DMAX)
            ylast = max(p[1] for p in res)
            cands = [(ij, hes) for ij, hes in cands if hes[0][1] + 15 >= xl and hes[0][1] - 16 <= xh
                     and hes[0][0] > q.zlo and hes[0][2] <= ylast]
            if NOWRONG:
                vis = []
                for y, zlo_y, zhi_y in B._av_lines(q, y0, cv.h):
                    sr, tr = cv.sbuf[y], cv.tbuf[y]
                    for x in range(xl, xh + 1):
                        vis.append((x, y, zlo_y, zhi_y, tr[x] if sr[x] > q.s else NEG))

                def wrong(hes):
                    H = hes[0][0]
                    for x, y, lo, hi, vf in vis:
                        if min(hi, H - 1) < max(lo, vf):
                            continue
                        for he in hes:
                            e = B.amodel_hedge(he[:6], x)
                            if e is not None and e <= y:
                                return True
                    return False
                n0 = len(cands)
                cands = [c_ for c_ in cands if not wrong(c_[1])]
                STATS["wrongcut"] = STATS.get("wrongcut", 0) + n0 - len(cands)
            while cands and (CAP == 0 or len(sel) < CAP):
                best = None
                for ij, hes in cands:
                    c2 = cols_of(near + [h for _ij, hh in sel for h in hh] + hes, xl, xh)
                    n = sum(1 for p in res if not free(c2.get(p[0]), p[1], p[2], p[3]))
                    if n and (best is None or n > best[0]):
                        best = (n, ij, hes)
                if best is None:
                    break
                sel.append((best[1], best[2]))
                cands = [c_ for c_ in cands if c_[0] != best[1]]
                c2 = cols_of(near + [h for _ij, hh in sel for h in hh], xl, xh)
                res = [p for p in res if free(c2.get(p[0]), p[1], p[2], p[3])]
        plan.append((q, near, pairs, xl, xh, sel, proxy_max(grid, q, x0, []) if BUD else 0))
    bud = max([p_[6] for p_ in plan] or [0])
    STATS["today"] = bud
    occ = {}
    for q, near, pairs, xl, xh, sel, _t in plan:
        while BUD and sel and proxy_max(grid, q, x0, [hh for _ij, hh in sel]) > bud:
            sel = sel[:-1]
            STATS["trim"] += 1
        key = (q.wx, q.wy)
        if sel:
            STATS["far"][key] = sorted(set(STATS["far"].get(key, []) + [ij for ij, _h in sel]))
        cols = cols_of(near + [h for _ij, hh in sel for h in hh], xl, xh)
        for p in pairs:
            if free(cols.get(p[0]), p[1], p[2], p[3]):
                occ[(p[0], p[1])] = (p[4], p[5])
    return occ


B.av_residual = my_residual
_dops = B.draw_ops


def _cap(tiles, x0, deep=(), ground=B.GROUND_AUTO, floats=()):
    if isinstance(floats, dict):
        FLOATS.update(floats)
    return _dops(tiles, x0, deep, ground, floats)


B.draw_ops = _cap
src = open("apps/bonanza/courses/%s.bbc" % course).read()
t = time.time()
c = B.compile_course(src, "apps/bonanza/courses/%s.bbc" % course)
st = [c.stored] + ([c.wstored] if getattr(c, "split", False) else [])
far = STATS["far"]
print("%s %s dmax %d cap %d%s float %s: records %d masks %d LZB %d; far lists %d cells, %d entries, max %d; "
      "float reads %d%s (%.0fs)" % (
          course, mode, DMAX, CAP, (" budget" if BUD else "") + (" nowrong" if NOWRONG else ""), FMODE, len(c.records), len(c.masks),
          sum(B.packed_len(s, "lzb") for s in st), len(far), sum(len(v) for v in far.values()),
          max([len(v) for v in far.values()] or [0]), STATS["fl"],
          ("; budget %.1fk, %d trimmed" % (STATS["today"] / 1000.0, STATS["trim"]) if BUD else "") + ("; %d candidates refused for a wrong hide" % STATS.get("wrongcut", 0) if NOWRONG else ""), time.time() - t))
pickle.dump({"far": far}, open(os.path.join(HERE, "%s_%s_%d_%d_%s%s.pkl" % (course, mode, DMAX, CAP, FMODE,
                                                                           ("_b" if BUD else "") + ("w" if NOWRONG else ""))), "wb"))
