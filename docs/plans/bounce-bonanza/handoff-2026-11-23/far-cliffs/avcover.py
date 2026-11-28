"""SPEC.md 137.29.12 research: per VOID position and whole height, what the model's work is (counting half-edges
over the footprint, near and far) and whether the ball is FULLY hidden there (the cover threshold Kc).
usage: avcover.py course [farpickle]"""
import sys, os, pickle, collections
sys.path.insert(0, "tools")
import bbcourse as B

course = sys.argv[1]
far = pickle.load(open(sys.argv[2], "rb"))["far"] if len(sys.argv) > 2 else {}
c = B.compile_course(open("apps/bonanza/courses/%s.bbc" % course).read(), "apps/bonanza/courses/%s.bbc" % course)
g = B.AGrid(B.world_of(c))
NEG = -(1 << 30)


def far_hedges(wx, wy, lst):
    out = []
    for i, j in lst:
        b = g.raw(wx + i, wy + j)
        H, X, Y, kr, kl = g.geom(b, wx + wy + i + j, wx + i - wy - j)
        out += [(H, X, Y, kr, True, False), (H, X, Y, kl, False, False)]
    return out


BALL = {}


def swept(q, z):
    """every lit ball pixel at whole height z anywhere in cell q (a superset: px, py independently)"""
    s, a = q.s, q.wx - q.wy
    out = set()
    for px in range(16 * a + c.x0 - 8 - 15, 16 * a + c.x0 - 8 + 16):
        for py in range(8 * s - z - 1 + c.y0 - 13, 8 * s + 15 - z + c.y0 - 13 + 1):
            key = (px & 7, py & 7)
            bp = BALL.get(key)
            if bp is None:
                bp = BALL[key] = [(x - px, y - py) for (x, y) in B.ball_pixels(px, py)]
            for dx, dy in bp:
                out.add((px + dx, py + dy))
    return out


def hidden_all(cols, pix, z):
    for (x, y) in pix:
        if B.amodel_z(cols, x, y) <= z:
            return False
    return True


rows = []
pos = [q for q in B.av_positions(c.reach, g, c.slabcells, c.x0) if q.pts is None
       and (q.wx, q.wy) not in getattr(c, "noocc", ())]
for q in pos:
    xl, xh = max(q.xl, 0), min(q.xh, c.width - 1)
    near = g.front(q.wx, q.wy)
    fh = far_hedges(q.wx, q.wy, far.get((q.wx, q.wy), []))
    cn = B.amodel_cols(near, xl, xh)
    cf = B.amodel_cols(near + fh, xl, xh)
    kc_n = kc_f = None
    for z in range(q.zlo, q.zhi + 1):
        sw = swept(q, z)
        sw = {p for p in sw if 0 <= p[0] < c.width and 0 <= p[1] < c.lines}
        nn = sum(1 for he in near if he[0] > z and (he[1] + 15 >= xl if he[4] else he[1] - 1 >= xl)
                 and (he[1] <= xh if he[4] else he[1] - 16 <= xh))
        nf = sum(1 for he in fh if he[0] > z and (he[1] + 15 >= xl if he[4] else he[1] - 1 >= xl)
                 and (he[1] <= xh if he[4] else he[1] - 16 <= xh))
        hn = hidden_all(cn, sw, z)
        hf = hn or hidden_all(cf, sw, z)
        rows.append((q.wx, q.wy, z, nn, nf, hn, hf))
n = len(rows)
print("%s: %d VOID cells, %d (cell, whole height) positions" % (course, len(pos), n))
for lab, f in (("near only", 5), ("near + far list", 6)):
    h = [r for r in rows if r[f]]
    print("  fully hidden (%s): %d positions (%.1f%%)" % (lab, len(h), 100.0 * len(h) / n))
    for k in (6, 10, 14):
        hv = [r for r in rows if r[3] >= k]
        if hv:
            print("    of the %d with >= %d near half-edges counting over the footprint: %d hidden (%.0f%%)" % (
                len(hv), k, sum(1 for r in hv if r[f]), 100.0 * sum(1 for r in hv if r[f]) / len(hv)))
# the cover threshold per cell: the greatest z below which (and at which) every height is fully hidden
kc = {}
for r in sorted(rows, key=lambda r: (r[0], r[1], r[2])):
    k = (r[0], r[1])
    if k not in kc:
        kc[k] = [None, None, True, True]
    for i, f in ((0, 5), (1, 6)):
        if kc[k][2 + i] and r[f]:
            kc[k][i] = r[2]
        else:
            kc[k][2 + i] = False
withn = sum(1 for v in kc.values() if v[0] is not None)
withf = sum(1 for v in kc.values() if v[1] is not None)
cov = sum(1 for r in rows if kc[(r[0], r[1])][1] is not None and r[2] <= kc[(r[0], r[1])][1])
print("  cover threshold Kc: %d cells have one (near), %d (with far); positions under it %d (%.1f%%)" % (
    withn, withf, cov, 100.0 * cov / n))
mx = max(r[3] for r in rows)
print("  near half-edges counting over the footprint: max %d; far: max %d; positions with a far one counting %d" % (
    mx, max(r[4] for r in rows), sum(1 for r in rows if r[4])))
top = sorted(rows, key=lambda r: -(r[3] + r[4]))[:8]
for r in top:
    print("    heavy: cell (%d, %d) z %d near %d far %d hidden %s/%s Kc %s" % (r + (kc[(r[0], r[1])][1],)))
pickle.dump({"rows": rows, "kc": kc}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cover_%s.pkl" % course), "wb"))
