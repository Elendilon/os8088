"""SPEC.md 137.29.12 research: a per-position COST PROXY of bz_amodel's ENTERING frame (the frame that reads V's
front and computes the footprint's words: today's worst), today against (A) the far list and (B) the cheap float.
The proxy, from the guest's own instructions priced (price.py on bz_arange's half and bz_ahalf's column, and the
sketch sk_far.asm): 14 x 670 for the front reads (137.29.5's measured), each COUNTING half not shadowed (the
guest's flat parent shadow) whose columns meet the footprint's words 780 + 111 a column, each far entry 1,360,
each float read +150 (B's slab bottom).  The ball centred in the cell.  usage: avproxy.py course [farpickle]"""
import sys, os, pickle, collections
sys.path.insert(0, "tools")
import bbcourse as B

course = sys.argv[1]
far = pickle.load(open(sys.argv[2], "rb"))["far"] if len(sys.argv) > 2 else {}
c = B.compile_course(open("apps/bonanza/courses/%s.bbc" % course).read(), "apps/bonanza/courses/%s.bbc" % course)
g = B.AGrid(B.world_of(c))
floats = getattr(c, "floats", {}) or {}
NEG = -(1 << 30)
READ, HALF, COL, FENT, FREAD = 670, 780, 111, 1360, 150


def table(wx, wy):
    """the front table as the guest reads it: {(d, i): (H, X, Y, sx, sy, float_kfbase or None)}"""
    t = {}
    for d in range(1, 5):
        for i in range(d + 1):
            cx, cy = wx + i, wy + d - i
            b = g.raw(cx, cy)
            if b is None:
                continue
            z0, sl, kd, fl = b
            kind = kd & 15
            if kind not in (B.KIND_FLOOR, B.KIND_WALL, B.KIND_GOAL) or fl & B.FL_OBS:
                continue
            isf = kind != B.KIND_GOAL and fl & B.FL_FLOAT
            H, X, Y, kr, kl = g.geom(b, wx + wy + d, cx - cy)
            sx, sy = B._nib(sl & 15), B._nib(sl >> 4)
            bmin = None
            if isf:
                fd = floats.get((cx, cy), B.FACE8)
                bc = Y + 16 - 4 * (sx + sy) + fd
                bmin = min(min(bc - B.amodel_f(kl, x - X, True) for x in range(X, X + 16)),
                           min(bc - B.amodel_f(kr, X - 1 - x, False) for x in range(X - 16, X)))
            t[(d, i)] = (H, X, Y, sx, sy, isf, bmin)
    return t


def shadows(t):
    """the guest's flat parent shadow: {(d, i): bits} 1 right half, 2 left half (137.29.5)"""
    sh = {}
    for (d, i), (H, X, Y, sx, sy, isf, _b) in t.items():
        v = 0
        if d >= 2:
            p1, p2 = t.get((d - 1, i)), t.get((d - 1, i - 1))
            if sx == 0 and p1 and p1[4] == 0 and p1[0] >= H and p1[2] <= Y - 8 and not p1[5]:
                v |= 1
            if sy == 0 and p2 and p2[3] == 0 and p2[0] >= H and p2[2] <= Y - 8 and not p2[5]:
                v |= 2
        sh[(d, i)] = v
    return sh


def overlap(X, right, w0, w1):
    lo, hi = (X, X + 15) if right else (X - 16, X - 1)
    return max(0, min(hi, 8 * w1 + 7) - max(lo, 8 * w0) + 1)


res = {"today": [], "far": [], "float": []}
pos = [q for q in B.av_positions(c.reach, g, c.slabcells, c.x0) if q.pts is None]
nfl = 0
for q in pos:
    t = table(q.wx, q.wy)
    sh = shadows(t)
    fl = far.get((q.wx, q.wy), [])
    fcells = []
    for i, j in fl:
        b = g.raw(q.wx + i, q.wy + j)
        H, X, Y, kr, kl = g.geom(b, q.wx + q.wy + i + j, q.wx + i - q.wy - j)
        fcells.append((H, X))
    nf_reads = sum(1 for v in t.values() if v[5])
    px = 16 * (q.wx - q.wy) + c.x0 - 8
    x4 = px & ~3
    w0, w1 = x4 >> 3, (x4 + 19) >> 3
    for z in range(q.zlo, q.zhi + 1, 2):
        base = 14 * READ
        tod = flo = base
        for k, (H, X, Y, sx, sy, isf, bmin) in t.items():
            for right, bit in ((True, 1), (False, 2)):
                ov = overlap(X, right, w0, w1)
                if not ov or sh[k] & bit:
                    continue
                cost = HALF + COL * ov
                if not isf and H > z:
                    tod += cost
                    flo += cost
                elif isf and H > z and z >= 8 * q.s + 17 + c.y0 - bmin + 1:
                    flo += cost
        flo += FREAD * nf_reads
        fa = tod + (FENT * len(fl) + 100 if True else 0)
        for H, X in fcells:
            for right in (True, False):
                ov = overlap(X, right, w0, w1)
                if ov and H > z:
                    fa += HALF + COL * ov
        res["today"].append((tod, q.wx, q.wy, z))
        res["far"].append((fa, q.wx, q.wy, z))
        res["float"].append((flo, q.wx, q.wy, z))
for k, v in res.items():
    v.sort()
    n = len(v)
    print("%s %-6s entering-frame proxy over %d (cell, height): median %.1fk, 95%% %.1fk, worst %.1fk at %s" % (
        course, k, n, v[n // 2][0] / 1000.0, v[int(n * 0.95)][0] / 1000.0, v[-1][0] / 1000.0, v[-1][1:]))
d = sorted(b[0] - a[0] for a, b in zip(sorted(res["today"], key=lambda r: r[1:]), sorted(res["far"], key=lambda r: r[1:])))
print("  far - today per position: median %+.1fk, worst %+.1fk; positions changed %d" % (
    d[len(d) // 2] / 1000.0, d[-1] / 1000.0, sum(1 for x in d if x)))
d = sorted(b[0] - a[0] for a, b in zip(sorted(res["today"], key=lambda r: r[1:]), sorted(res["float"], key=lambda r: r[1:])))
print("  float - today per position: median %+.1fk, worst %+.1fk; positions changed %d" % (
    d[len(d) // 2] / 1000.0, d[-1] / 1000.0, sum(1 for x in d if x)))
