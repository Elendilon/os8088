"""part 2: which reach cells need the shipped occluder records on MILL (mo.bbc), and how the reach puts a ball there"""
import sys, json, time, collections
ROOT = sys.argv[1]
sys.path.insert(0, ROOT + "/tools")
import bbcourse as B, bbedjob as J, bbedproj as E
B.TRAP_CHECK = False
B.BLK_MAX = 1 << 30
D = "/tmp/claude-0/-home-user-os8088/50152400-584f-5f02-99a3-d60ce56fde4a/scratchpad/"
OUT = D + "occwhy/"
text = open(D + "mo.bbc").read()
t0 = time.time()
c = B.compile_course(text, "mo.bbc", occluders=True)
print("compile", round(time.time() - t0, 1), "s; shipped", len(c.records), "rule", len(c.rule_records),
      "part bytes stored", len(c.part_bytes) if not isinstance(c.part_bytes, (list, tuple)) else "?", "split", c.split)
d = J.occ_data(c)
reach = {(r.wx, r.wy): r for r in c.reach}
kind = {k: v[2] & 15 for k, v in c.cells.items()}
print("reach cells", len(reach), "by kind", collections.Counter(r.kind for r in c.reach))
# --- the flood: orthogonal steps between non-WALL grid cells, never across a railed edge (FL_EDX/FL_EDY, a wall
# at every height, 137.35.1); tubes carry IN -> OUT; seeded at the start, every flag and every route point
def blocked(a, b):
    (x, y), (x2, y2) = a, b
    if (x2, y2) == (x + 1, y):
        return bool(c.cells.get(a, [0, 0, 0, 0])[3] & B.FL_EDX)
    if (x2, y2) == (x - 1, y):
        return bool(c.cells.get(b, [0, 0, 0, 0])[3] & B.FL_EDX)
    if (x2, y2) == (x, y + 1):
        return bool(c.cells.get(a, [0, 0, 0, 0])[3] & B.FL_EDY)
    return bool(c.cells.get(b, [0, 0, 0, 0])[3] & B.FL_EDY)
nedx = sum(1 for v in c.cells.values() if v[3] & (B.FL_EDX | B.FL_EDY))
print("cells with a rail bit", nedx, "redges", len(c.redges))
# --- the TIGHTER reach: a VOID cell is a position only when a ball leaving some FLOOR cell L can get there through
# open edges (no rail, no WALL: both walls at every height) still ABOVE every cell's kill on the way.  The ball's
# height t steps after it leaves L is at most ENV(t): zhi(L) while it may still be rising (fall(zhi(L) - lo(L))
# steps), then zhi(L) less what a ball falls from rest in the steps since; crossing k cell edges takes at least
# (k - 2) x 4096 / (2 x VMAXG) steps (each axis at most VMAXG a step, so |dx| + |dy| at most 2 VMAXG t / 4096 cells)
kill = min(r.zlo for r in c.reach if r.kind == B.KIND_VOID)
vmax = max([B.VMAXG] + [max(abs(p["speed"][0]), abs(p["speed"][1])) for p in c.props
                         if p["kind"] == B.PK_TUBE and p.get("speed")])
FALL = [0]
z_, g_ = 0, 0
for _ in range(400):
    g_ = max(g_ - B.G, -B.VZMAX)
    z_ += g_
    FALL.append(-z_ // 256)
def tmin(k):
    return max(0, -(-(k - 2) * 4096 // (2 * vmax)))
reachv, how = {}, {}
for L, rl in reach.items():
    if rl.kind == B.KIND_VOID:
        continue
    tr = B._fall_steps(max(0, rl.zhi - rl.zlo))
    def env(t):
        return rl.zhi if t <= tr else rl.zhi - FALL[min(t - tr, 400)]
    dist = {L: 0}
    q = collections.deque([L])
    while q:
        a = q.popleft()
        k = dist[a] + 1
        e = env(tmin(k))
        for b in [(a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)]:
            if b in reach and b not in dist and not blocked(a, b) and e >= reach[b].zlo:
                dist[b] = k
                q.append(b)
                if reach[b].kind == B.KIND_VOID and (b not in how or how[b][1] > k):
                    how[b] = (L, k, rl.zhi)
    for b in dist:
        reachv[b] = True
seen = set(reachv)
doubt = {k for k, r in reach.items() if r.kind == B.KIND_VOID and k not in seen}
print("vmax", vmax, "lowest kill", kill)
print("void cells reached by a flight off a floor through open edges", sum(1 for k in seen if reach[k].kind == B.KIND_VOID),
      "of", sum(1 for r in c.reach if r.kind == B.KIND_VOID), "; doubtful", len(doubt))
# --- the records each class needs
def cls(recs):
    only, some = 0, 0
    for r in recs:
        n = {tuple(x) for x in r["needs"]}
        if n and n <= doubt:
            only += 1
        elif n & doubt:
            some += 1
    return only, some
print("shipped: needed ONLY by doubtful cells %d, by some %d, of %d" % (cls(d["shipped"]) + (len(d["shipped"]),)))
print("rule:    needed ONLY by doubtful cells %d, by some %d, of %d" % (cls(d["records"]) + (len(d["records"]),)))
# --- why the reach has each doubtful cell, and at what heights
src_c = collections.Counter()
for k in doubt:
    r = reach[k]
    src_c[(B.KIND_VOID == r.kind and "VOID" or "kind %d" % r.kind, "zhi==zlo (no flight)" if r.zhi == r.zlo
           else (r.src[1] if r.src else "own floor"))] += 1
print("doubtful cells by (kind, what set zhi):", src_c.most_common())
# --- the regions the owner names
def owned_by(rect):
    x0, y0, x1, y1 = rect
    return [r for r in d["shipped"] if r["own"] and x0 <= r["own"][0][0] <= x1 and y0 <= r["own"][0][1] <= y1]
regions = {"back wall 8..12 x 5..9": (8, 5, 12, 9)}
for nm, rc in regions.items():
    rs = owned_by(rc)
    ns = collections.Counter(tuple(x) for r in rs for x in r["needs"])
    nd = [r for r in rs if {tuple(x) for x in r["needs"]} <= doubt]
    print(nm, ": shipped records drawn by it", len(rs), "needed only by doubtful cells", len(nd))
    for cl, n in ns.most_common(40):
        r = reach[cl]
        print("   needed by", cl, "x%d" % n, "kind", r.kind, "zlo", r.zlo, "zhi", r.zhi, "src", r.src,
              "DOUBT" if cl in doubt else "flood via %s" % (how.get(cl),))
byown = collections.Counter()
for r in d["shipped"]:
    if r["own"] and {tuple(x) for x in r["needs"]} <= doubt:
        byown[(r["own"][0][0], r["own"][0][1])] += 1
print("doubtful-only shipped records by the cell that drew them (top 30):", byown.most_common(30))
byneed = collections.Counter(tuple(x) for r in d["shipped"] for x in r["needs"] if tuple(x) in doubt)
print("doubtful cells needing the most shipped records:", byneed.most_common(20))
for cl, _n in byneed.most_common(8):
    r = reach[cl]
    print("   ", cl, "zlo", r.zlo, "zhi", r.zhi, "src", r.src)
vneed = collections.Counter(tuple(x) for r in d["shipped"] for x in r["needs"]
                            if reach[tuple(x)].kind == B.KIND_VOID and tuple(x) not in doubt)
print("reachable VOID cells needing the most shipped records, and the flight that reaches them:")
for cl, n in vneed.most_common(12):
    print("   ", cl, "x%d" % n, "off floor %s, %d edges, leaving at zhi %d px" % how[cl], "reach src", reach[cl].src)
json.dump({"doubt": sorted(doubt), "seen": sorted(seen),
           "reach": {"%d,%d" % k: [r.kind, r.zlo, r.zhi, list(r.src[0]) if r.src else None, r.src[1] if r.src else None]
                     for k, r in reach.items()},
           "how": {"%d,%d" % k: (list(v) if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], int) else str(v))
                   for k, v in how.items()}}, open(OUT + "why.json", "w"))
json.dump(d, open(OUT + "occ.json", "w"))
# --- the picture: the shipped records tinted, the doubtful-only ones red, the doubtful cells marked
from PIL import Image, ImageDraw
pal = J.palette(c.src)
W, H = c.width, c.lines
img = Image.new("RGB", (W, H))
img.putdata([pal[v] for row in c.pic for v in row])
img = img.convert("RGB")
px = img.load()
for r in d["shipped"]:
    n = {tuple(x) for x in r["needs"]}
    ink = (255, 40, 40) if n <= doubt else (60, 220, 255) if not (n & doubt) else (255, 200, 40)
    for y, a, b in r["runs"]:
        for x in range(a, b + 1):
            if (x + y) & 1 == 0:
                px[x, y] = ink
dr = ImageDraw.Draw(img)
# calibrate a cell's top corner: the start cell's top pixels
ob = B.owners_canvas(c)
st = c.start
own = 256 * st[0] + st[1]
ys = [y for y in range(H) for x in range(W) if ob[y][x] == own]
xs = [x for y in range(H) for x in range(W) if ob[y][x] == own]
rs = reach[st]
K = min(ys) - (8 * (st[0] + st[1]) + c.y0 - rs.zlo)
xc0 = (min(xs) + max(xs)) / 2.0 - (16 * (st[0] - st[1]) + c.x0)
print("calibration K", K, "xc offset", xc0)
for k in sorted(doubt):
    r = reach[k]
    s, a = k[0] + k[1], k[0] - k[1]
    z = r.zlo + 24                  # (the near floor the void hangs off: its kill is 3 units under it)
    xc = 16 * a + c.x0 + xc0
    yt = 8 * s + c.y0 + K - z
    dr.polygon([(xc, yt), (xc + 16, yt + 8), (xc, yt + 16), (xc - 16, yt + 8)], outline=(255, 0, 255))
big = img.resize((W * 2, H * 2), Image.NEAREST)
big.save(OUT + "occwhy-mill.png")
print("saved", OUT + "occwhy-mill.png", W, H)
# --- what the tightening would save: the doubtful cells noocclude'd, compiled again
doc = E.Document(text)
added, _r, refused = doc.set_noocclude(add=sorted(doubt))
print("noocclude added", len(added), "refused", len(refused))
open(OUT + "mo-tight.bbc", "w").write(doc.text())
t0 = time.time()
c2 = B.compile_course(doc.text(), "mo-tight.bbc", occluders=True)
def plen(cc):
    return (len(cc.stored) if not cc.split else len(cc.stored) + len(cc.wstored), len(cc.cga) if not cc.split else None)
print("tight compile", round(time.time() - t0, 1), "s; shipped", len(c2.records), "rule", len(c2.rule_records),
      "flagged OCC cells", sum(1 for v in c2.cells.values() if v[3] & B.FL_OCC), "vs", sum(1 for v in c.cells.values() if v[3] & B.FL_OCC))
print("part bytes stored (before, after)", plen(c), plen(c2), "split", c.split, c2.split)
print("masks", len(c.masks), len(c2.masks))
