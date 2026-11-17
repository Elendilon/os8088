import os, sys, pickle
W = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "../../../.."))
sys.path.insert(0, W + "/docs/plans/bounce-bonanza"); sys.path.insert(0, W + "/tools")
import occproto as P, occpics as Q
B = P.B
OUT = os.path.dirname(os.path.abspath(__file__))
c = B.compile_course(W + "/apps/bonanza/courses/summit.bbc")
gh = P.ghost_heights(c)
fl = Q.falls(c, gh)
score, at, path = fl[0]
print("fall off", at, "steps", len(path))
first = next((i for i, st in enumerate(path) if c.cells.get(st[5], [0,0,0])[2] & 15 == B.KIND_VOID), 0)
first = max(0, first - 1); span = path[first:]
sel = [span[(len(span)-1)*i//7] for i in range(8)]
for st in sel:
    px, py, sb, zb, air, cell = st
    laid = B.laid_at(c, px, py, sb, zb, air)
    bp = B.ball_pixels(px, py)
    hid = {p for r in laid for p in r["pix"] if p in bp}
    srcs = sorted({(r["s"], r["top"]) for r in laid if r["pix"] & set(bp)})
    kind = c.cells.get(cell, [0,0,0])[2] & 15
    print("ball px,py=%d,%d cellrow sb=%d z=%d air=%s cell=%s kind=%d | hidden %d/%d px | by (s,top) %s" % (px, py, sb, zb, air, cell, kind, len(hid), len(bp), srcs))
pickle.dump(dict(sel=sel, at=at), open(OUT + "/peakfall.pkl", "wb"))
print("width", c.width, "lines", c.lines, "attrs", [a for a in dir(c) if not a.startswith('__')][:80])
