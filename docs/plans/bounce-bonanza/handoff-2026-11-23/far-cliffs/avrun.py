"""SPEC.md 130.29.12 research: the model's per-FRAME work along a real run (the course's route demo, the host
autopilot), today against (A) the far list and (B) the cheap float - the cache's semantics (130.29.5): a new V
reads its table and computes the footprint's words; a changed count set recomputes them; new footprint words are
computed; otherwise nothing.  Priced with avproxy.py's proxy.  usage: avrun.py course farpickle [demo.bzd]"""
import sys, os, pickle, collections
sys.path.insert(0, "tools")
import bbcourse as B
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

course = sys.argv[1]
far = pickle.load(open(sys.argv[2], "rb"))["far"]
c = B.compile_course(open("apps/bonanza/courses/%s.bbc" % course).read(), "apps/bonanza/courses/%s.bbc" % course)
if len(sys.argv) > 3:
    log = B.parse_bzd(open(sys.argv[3]).read(), sys.argv[3])
else:
    log = B.route_demo(c, 0)
g = B.AGrid(B.world_of(c))
floats = getattr(c, "floats", {}) or {}
READ, HALF, COL, FENT, FREAD, FRAME = 670, 780, 111, 1360, 150, 700
sys.argv = [sys.argv[0], course]
_m4 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "avproxy.py")).read()
exec(_m4[_m4.index("def table"):_m4.index("res = {")])


def halves(V, K, variant, t, sh, fc):
    """the counting halves: [(id, X, right)]"""
    out = []
    for k, (H, X, Y, sx, sy, isf, bmin) in t.items():
        for right, bit in ((True, 1), (False, 2)):
            if sh[k] & bit:
                continue
            if not isf and H > K:
                out.append(((k, right), X, right))
            elif isf and variant == "float" and H > K and K >= 8 * (V[0] + V[1]) + 17 + c.y0 - bmin + 1:
                out.append(((k, right), X, right))
    if variant == "far":
        for n, (H, X) in enumerate(fc):
            if H > K:
                out += [(("f", n, True), X, True), (("f", n, False), X, False)]
    return out


def edges(hs, words):
    t = 0
    for _id, X, right in hs:
        for w in words:
            ov = overlap(X, right, w, w)
            if ov:
                t += COL * ov
        if any(overlap(X, right, w, w) for w in words):
            t += HALF
    return t


_K, mat, kt, _fl = B.decode_log_t(log)
p = B.Physics(c, play=True, mat=mat)
frames = []
for k, tt in kt:
    p.step(k, tt)
    wx, wy = p.gx >> 12, p.gy >> 12
    cl = c.cells.get((wx, wy))
    if p.air and not p.tube and cl and cl[3] & B.FL_OCC and g.runs(*B.mcell(p.gx, p.gy)):
        frames.append((p.nstep, wx, wy, p.gx, p.gy, p.gz >> 8))
    if p.goal or p.tout:
        break
print("%s: %d steps, %d model frames" % (course, p.nstep, len(frames)))
TAB = {}
for variant in ("today", "far", "float"):
    st = {"V": None, "cs": None, "words": set()}
    costs = []
    for (n, wx, wy, gx, gy, zb) in frames:
        V = (wx, wy)
        if V not in TAB:
            t = table(wx, wy)
            fc = []
            for i, j in far.get(V, []):
                b = g.raw(wx + i, wy + j)
                H, X, Y, kr, kl = g.geom(b, wx + wy + i + j, wx + i - wy - j)
                fc.append((H, X))
            TAB[V] = (t, shadows(t), fc)
        t, sh, fc = TAB[V]
        K = zb
        px = ((gx - gy) >> 8) + c.x0 - 8
        x4 = px & ~3
        words = set(range(x4 >> 3, ((x4 + 19) >> 3) + 1))
        hs = halves(V, K, variant, t, sh, fc)
        cs = frozenset(h[0] for h in hs)
        cost = FRAME
        isfl = any(v[5] for v in t.values())
        if V != st["V"]:
            cost += 14 * READ + (FENT * len(fc) + 100 if variant == "far" else 0) + \
                (FREAD * sum(1 for v in t.values() if v[5]) if variant == "float" else 0)
            cost += edges(hs, words) if hs else 0
            st["words"] = set(words)
        elif cs != st["cs"]:
            cost += 60 * (len(t) + (len(fc) * 2 if variant == "far" else 0))
            cost += edges(hs, words) if hs else 0
            st["words"] = set(words)
        else:
            new = words - st["words"]
            if new and hs:
                cost += edges(hs, new)
            st["words"] |= words
        st["V"], st["cs"] = V, cs
        costs.append((cost, n, V, K, bool(fc), isfl, len(hs)))
    TAB_ = costs
    cs_ = sorted(x[0] for x in costs)
    m = len(cs_)
    if not m:
        continue
    fl = sorted(x[0] for x in costs if x[5])
    fa = sorted(x[0] for x in costs if x[4])
    w = max(costs)
    print("  %-6s mean %.1fk median %.1fk worst %.1fk (step %d, cell %s, K %d, %d halves)%s%s" % (
        variant, sum(cs_) / m / 1000.0, cs_[m // 2] / 1000.0, w[0] / 1000.0, w[1], w[2], w[3], w[6],
        "; the %d frames beside a float: mean %.1fk worst %.1fk" % (len(fl), sum(fl) / len(fl) / 1000.0, fl[-1] / 1000.0)
        if fl else "",
        "; the %d frames with a far list: mean %.1fk worst %.1fk" % (len(fa), sum(fa) / len(fa) / 1000.0, fa[-1] / 1000.0)
        if fa else ""))
