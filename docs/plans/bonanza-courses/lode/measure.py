#!/usr/bin/env python3
"""COURSE 6, LODESTONE GORGE: the MEASURED numbers of ../LODE.md section 3, on the tool's model
(tools/bbcourse.py's Physics and Glide; never an emulator).  Host-only; nothing in `make` runs it.

    python3 measure.py [COURSE.bbc] [--only SECTION,...]
        sections: start flume mouth hoist sirens wall gantry island reach held soft walks frame

Every place it names is read off the compiled course (the flags, the magnets, the goal), so it follows the
sketch.  A STEEL ball throughout; "the pair" is two arrows held together, which move the ball along a tile
axis.  The whole of it takes about ten minutes; `flume`, `held`, `soft` and `walks` are the long ones.

`held` (every arrow from rest on every tile) and `soft` (the goal from every tile at rest) read ANY course,
with its own ball:  python3 measure.py ../../../../apps/bonanza/courses/keep.bbc --only held,soft
"""
import collections
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B                                    # noqa: E402

K_L, K_R, K_U, K_D, K_HOP = B.K_L, B.K_R, B.K_U, B.K_D, B.K_HOP
PX, MX, PY, MY = K_R | K_D, K_L | K_U, K_L | K_D, K_R | K_U        # the pairs: +x, -x, +y, -y
NAMES = {0: "none", K_L: "L", K_R: "R", K_U: "U", K_D: "D", PX: "+x", MX: "-x", PY: "+y", MY: "-y"}
ALL8 = [K_L, K_R, K_U, K_D, PX, MX, PY, MY]
SEC = float(B.SEC_STEPS)


def ball(c, wx, wy, vx=0, vy=0, mat=None, gx=None, gy=None):
    p = B.Physics(c, play=True, mat=mat)
    p.poke(wx, wy, vx, vy)
    if gx is not None:
        p.gx = int(gx * 4096)
    if gy is not None:
        p.gy = int(gy * 4096)
    return p


def cell(p):
    return (p.gx >> 12, p.gy >> 12)


def at(p):
    return p.gx / 4096.0, p.gy / 4096.0


def run(p, keys, n, stop=None):
    """n steps of `keys` (a key byte, or f(p, i)) -> ('FELL' | 'GOAL' | 'stop' | 'end', the step)"""
    nf = p.nfall
    for i in range(n):
        p.step(keys(p, i) if callable(keys) else keys)
        if p.nfall != nf:
            return "FELL", i
        if p.goal:
            return "GOAL", i
        if stop and stop(p):
            return "stop", i
    return "end", n


class Course:
    """the places the measurements name, read off the compiled course"""

    def __init__(self, path):
        self.c = c = B.compile_course(open(path).read(), fname=path, occluders=False)
        self.rm = rm = B.rec_map(c.tiles)
        self.start = tuple(c.src.start[0])
        self.flags = [tuple(q["at"]) for q in c.props if q["kind"] == B.PK_CHECKPOINT]
        self.pcells = {tuple(q["at"]) for q in c.props}
        self.stand = sorted(k for k, t in rm.items() if t.kind in (B.KIND_FLOOR, B.KIND_FIELD, B.KIND_GOAL)
                            and k not in self.pcells)
        mags = [(tuple(q["at"]), q["mg"]) for q in c.props if q["kind"] == B.K_MAGNET]
        if not mags:                                    # (another course: `held` and `soft` read any)
            return
        self.sirens = sorted(m[0] for m in mags if m[1][2] == 4 and m[1][3] < 64)
        self.hang = sorted(m[0] for m in mags if m[1][1] & 1)
        goal = sorted(k for k, t in rm.items() if t.kind == B.KIND_GOAL)
        self.G = goal[1][0]                             # the island's, the gantry's and the runway's column
        self.goal_y = goal[0][1]
        self.AY = self.goal_y + 4                       # the apron's back row
        self.lane = sorted(y for (_x, y) in self.hang)  # the lane's rows
        self.RY = self.lane[-1] + 1                     # the runway's far tile
        self.field = sorted(k for k, t in rm.items() if t.kind == B.KIND_FIELD)
        self.taper = max(k[1] for k in self.field)      # the flume's last row
        self.mouth = sorted(k[0] for k in self.field if k[1] == self.taper)[1]
        fence = sorted(m[0] for m in mags if m[1][2] == 1 and not m[1][1] & 1)
        self.WX = max(x for x, _y in fence) + 1         # the wall's column
        self.leg1 = [(self.WX, y) for (x, y) in fence if x == self.WX - 1]
        self.leg2 = [(x, y + 1) for (x, y) in fence if x != self.WX - 1]

    def inpen(self, p):
        x, y = cell(p)
        return not p.air and self.mouth - 2 <= x <= self.mouth + 7 and self.taper + 1 <= y <= self.taper + 6


def m_start(L):
    print("THE START %s: each arrow and pair held 16 s" % (L.start,))
    for k in ALL8:
        p = ball(L.c, *L.start)
        r, _i = run(p, k, 900, stop=L.inpen)
        print("   %-2s: %s" % (NAMES[k], "FELL" if r == "FELL" else "in the pen" if r == "stop" else
                               "at rest on %s" % (cell(p),)))


def m_flume(L):
    print("THE FLUME, ridden from the start: the first key to step t1, the second for d more, then the third")
    T1, D = range(90, 270, 12), range(30, 200, 15)
    for k1, k2, k3 in ((PY, MX, PY), (PY, PY, PY), (PY, MX, K_L), (PY, MX, K_D), (PY, K_L, PY)):
        ok, ts = 0, []
        for t1 in T1:
            for d in D:
                p = ball(L.c, *L.start)
                r, i = run(p, lambda p, i: k1 if i < t1 else k2 if i < t1 + d else k3, 1100, stop=L.inpen)
                ok += r == "stop"
                if r == "stop":
                    ts.append(i / SEC)
        print("   %s / %s / %s: in the pen on %d of %d%s" % (NAMES[k1], NAMES[k2], NAMES[k3], ok, len(T1) * len(D),
                                                           ", in %.1f - %.1f s" % (min(ts), max(ts)) if ts else ""))
    n, fell = 0, collections.Counter()
    for k1 in (PY, K_L, K_D):
        for k2 in (MX, K_L, K_U):
            for k3 in (PY, K_L, K_D, 0):
                for t1 in T1:
                    for d in D:
                        p = ball(L.c, *L.start)
                        last = [None]

                        def keys(p, i):
                            if not p.air:
                                last[0] = cell(p)
                            return k1 if i < t1 else k2 if i < t1 + d else k3
                        r, _i = run(p, keys, 900, stop=L.inpen)
                        n += 1
                        if r == "FELL":
                            fell[last[0]] += 1
    print("   every one of 3 x 3 x 4 keys on those timings: %d runs, %d left the flume %s" % (
        n, sum(fell.values()), dict(fell) or ""))


def m_mouth(L):
    x, c = L.mouth, L.c
    print("THE FLUME'S MOUTH (the taper on row %d): into the last corner at v" % L.taper)
    for key in (PY, 0):
        out = []
        for v in (0, 40, 80, 120, 160, 200, 260, 320, 384):
            p = ball(c, x, L.taper - 4, 0, v)
            r, i = run(p, key, 700, stop=L.inpen)
            out.append("%d: %s" % (v, "%.1f s" % (i / SEC) if r == "stop" else "no"))
        print("   %s: %s" % ("the pair held" if key else "coasting", "; ".join(out)))
    n = fwd = back = neither = 0
    for k in L.field:
        if k[1] < L.taper - 4 or k[0] > x + 1:
            continue
        p = ball(c, *k)
        run(p, 0, 300)
        r1, _i = run(p, PY, 600, stop=L.inpen)
        q = ball(c, *k)
        run(q, 0, 300)
        run(q, MY, 110)
        r2, _i = run(q, PY, 600, stop=L.inpen)
        n += 1
        fwd += r1 == "stop"
        back += r2 == "stop"
        neither += r1 != "stop" and r2 != "stop"
    print("   at REST in the last corner and leg, %d places: the pair held takes out %d; backing up 2 s and coming "
          "again %d; neither %d" % (n, fwd, back, neither))
    for v in (-60, -150, -300):
        res = []
        for back2 in (False, True):
            p = ball(c, x, L.taper + 3, 0, v)
            run(p, 0, 500)
            if back2:
                run(p, MY, 110)
            r, _i = run(p, PY, 600, stop=L.inpen)
            res.append(r == "stop")
        print("   rolled back into the mouth from the pen at %d: the pair %s, back up then the pair %s" % (
            v, "out" if res[0] else "NO", "out" if res[1] else "NO"))


def m_hoist(L):
    c = L.c
    mg = [tuple(q["at"]) for q in c.props if q["kind"] == B.K_MAGNET and q["mg"][2] == 3][0]
    hx, top = mg[0], mg[1] + 1
    print("THE HOIST (its post %s, the top tile row %d)" % (mg, top))
    for mat, nm in ((None, "steel"), (B.MAT_RUBBER, "rubber")):
        p = ball(c, hx, top + 2, mat=mat)
        run(p, 0, 400)
        print("   %s at rest on the ramp's low tile, no key: ends on %s" % (nm, cell(p)))
    p = ball(c, hx, top + 4)
    _r, i = run(p, MY, 600, stop=lambda p: cell(p) == (hx, top))
    _r, i2 = run(p, PX, 600, stop=lambda p: cell(p)[0] > hx)
    print("   from rest on the foot, the pair up it: the top tile in %.1f s; then the pair at the bridge: on it "
          "%.1f s later" % (i / SEC, i2 / SEC))
    out = []
    for key in ALL8:
        p = ball(c, hx, top)
        r, _i = run(p, key, 200, stop=lambda p: cell(p) != (hx, top))
        out.append("%s %s" % (NAMES[key], "leaves" if r == "stop" else "held"))
    print("   on the top tile: " + ", ".join(out))


def m_sirens(L):
    c, sx = L.c, [s[0] for s in L.sirens]
    f0 = L.flags[0]
    print("THE SIRENS %s, from flag 0 %s" % (L.sirens, f0))

    def done(p):
        return not p.air and p.gx / 4096.0 > sx[2] + 1.6

    def drive(p, lane, vcap):
        def keys(p, i):
            gx, gy = at(p)
            vt = max(-120, min(120, int((lane(gx) - gy) * 300)))
            fy = 1 if p.gvy < vt - 6 else -1 if p.gvy > vt + 6 else 0
            return B.PLAN_W2K[(0 if vcap and p.gvx > vcap else 1, fy)]
        return run(p, keys, 900, stop=done)
    far, near = f0[1] + 0.5, f0[1] + 1.5
    nears = {s[0] for s in L.sirens if s[1] > f0[1]}        # the sirens on the near side
    lanes = (("the far lane", lambda x: far), ("the near lane", lambda x: near), ("the middle", lambda x: far + 0.5),
             ("the weave", lambda x: far if any(abs(x - (s + 0.5)) < 2 for s in nears) else near))
    for nm, fn in lanes:
        out = []
        for vcap in (None, 200, 120, 90):
            p = ball(c, f0[0], f0[1], gy=fn(f0[0] + 0.5))
            r, i = drive(p, fn, vcap)
            out.append("%s %s" % ("uncapped" if vcap is None else "capped %d" % vcap,
                                  "across %.1f s" % (i / SEC) if r == "stop" else "LOST"))
        print("   from rest, %-13s: %s" % (nm, "; ".join(out)))
    for key, nm in ((PX, "the pair along the bridge and nothing else"), (0, "coasting (no key)")):
        for row in (f0[1], f0[1] + 1):
            out = []
            for v0 in (0, 100, 150, 200, 250, 300, 384):
                if not key and v0 < 150:
                    continue
                p = ball(c, f0[0], row, v0, 0)
                r, _i = run(p, key, 900, stop=done)
                out.append("%d %s" % (v0, "across" if r == "stop" else "lost" if r == "FELL" else "stops"))
            print("   %s, row %d: %s" % (nm, row, ", ".join(out)))


def m_wall(L):
    c, WX, f1 = L.c, L.WX, L.flags[-1]
    cy = L.leg2[0][1]

    def ingal(p):
        x, y = cell(p)
        return not p.air and x <= f1[0] and abs(y - cy) <= 1
    print("THE WALL (column %d, then row %d), from rest on the turn" % (WX, cy))
    for nm, k1, k2 in (("the pairs along it", PY, MX), ("pushing OUT on leg 1 (D alone)", K_D, MX),
                       ("the pair OUT on leg 1 (+x) every other step", None, MX), ("pushing OUT on leg 2 (L alone)", PY, K_L)):
        p = ball(c, WX, 22)

        def keys(p, i):
            gx, gy = at(p)
            if gy < 24:
                return PY
            if gy < cy - 0.7 and gx > WX - 0.2:
                return (PX if i & 1 else PY) if k1 is None else k1
            return k2
        r, i = run(p, keys, 1500, stop=ingal)
        print("   %s: %s" % (nm, "in the gallery %.1f s" % (i / SEC) if r == "stop" else r))
    res = collections.Counter()
    for k in L.leg1 + L.leg2:
        for key in ALL8 + [0]:
            p = ball(c, *k)
            r, _i = run(p, key, 500)
            res[r] += 1
    print("   at rest on each of the %d tilted tiles, each of 9 keys held 9 s: %s" % (len(L.leg1 + L.leg2), dict(res)))
    p = ball(c, WX, L.leg1[0][1] - 3, 0, 250, mat=B.MAT_RUBBER)
    r, _i = run(p, 0, 600, stop=ingal)
    print("   RUBBER along leg 1 at 250, no key: %s" % r)


def m_gantry(L):
    c, G, RY = L.c, L.G, L.RY
    land = L.lane[0] - 0.1
    print("THE GANTRY (the lane column %d, rows %d - %d; the runway's far tile row %d)" % (G, L.lane[0], L.lane[-1], RY))
    p = ball(c, *L.flags[-1])
    r, i = run(p, lambda p, i: MX if at(p)[1] > RY + 1.9 and at(p)[0] > G + 0.7 else MY, 1500)
    print("   from rest on flag 1: the pair west to the pocket, then the pair up the runway held: %s in %.1f s" % (r, i / SEC))
    for v in (-30, -60, -150, -384):
        p = ball(c, G, RY, 0, v, gy=RY + 0.05)
        zs, n = [], 0
        for i in range(3000):
            p.step(0)
            if p.air:
                zs.append(p.gz / 2048.0)
                n += 1
            elif at(p)[1] < land or p.nfall:
                break
        print("   off the runway's end at %d, no key: %s" % (v, "on the apron after %.1f s, %d steps in the air at "
              "%.2f - %.2f units" % (i / SEC, n, min(zs), max(zs)) if zs and not p.nfall else "does not cross"))
    n = ok = 0
    for xo in (0.2, 0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8):
        for vy in (-60, -150, -300, -384):
            for vx in (0, 20, -20, 40, -40):
                p = ball(c, G, RY + 1, vx, vy, gx=G + xo)
                r, _i = run(p, MY, 900, stop=lambda p: not p.air and at(p)[1] < land)
                n += 1
                ok += r == "stop"
    print("   from 9 places across the runway, 4 speeds, a drift of 0, 20 or 40 either way, the pair held: across "
          "on %d of %d" % (ok, n))
    p = ball(c, G, RY + 1, 0, -250, mat=B.MAT_RUBBER)
    print("   RUBBER off the runway at 250: %s" % run(p, 0, 300)[0])
    p = ball(c, G, RY, 0, -40, gy=RY + 0.05)
    run(p, 0, 80)
    p.gvx = p.gvy = 0
    post = 2 * p.grid.cell(G - 1, L.lane[0])[0]            # the posts' tops, px
    rise = None
    for i in range(2000):
        p.step(0)
        if rise is None and (p.gz >> 8) >= post:
            rise = i
    print("   a ball STOPPED in the lane, no key: still hanging after 36 s at %.2f units; over the posts' tops "
          "(%.2f) after %s s" % (p.gz / 2048.0, post / 8.0, "%.1f" % (rise / SEC) if rise is not None else "-"))
    r, _i = run(p, MX, 400, stop=lambda p: not p.air)
    print("   ...then the pair at the posts: %s, on %s" % (r, cell(p)))


def m_island(L):
    c, G, AY = L.c, L.G, L.AY
    print("THE ISLAND (the apron rows %d - %d, the goal row %d)" % (AY, AY + 2, L.goal_y))
    res = collections.Counter()
    for xo in (0.2, 0.35, 0.5, 0.65, 0.8):
        for vx in (-80, -40, 0, 40, 80):
            for vy in (-40, -150, -300):
                for key in (MY, K_R, K_U, 0, MX, PX):
                    p = ball(c, G, AY + 1, vx, vy, gx=G + xo)
                    res[run(p, key, 500)[0]] += 1
    print("   landing: 5 places across, 5 drifts, 3 speeds, 6 keys: %s" % dict(res))
    res, n = collections.Counter(), 0
    for x in range(G - 2, G + 3):
        for y in range(AY, AY + 3):
            if (x, y) in L.pcells:
                continue
            n += 1
            for key in ALL8:
                res[run(ball(c, x, y), key, 700)[0]] += 1
    print("   from rest on each of the apron's %d free tiles, each of 8 keys held 12 s: %s" % (n, dict(res)))
    r, i = run(ball(c, G, AY + 2), MY, 600)
    print("   from rest on the landing, the pair at the ramp: %s in %.1f s" % (r, i / SEC))
    for vy in (-40, -150):
        r, i = run(ball(c, G, AY, 0, vy), 0, 600)
        print("   coasting onto the ramp's foot at %d, no key: %s" % (vy, "GOAL in %.1f s" % (i / SEC) if r == "GOAL"
                                                                     else "stops short"))
    print("   RUBBER at 150, no key: %s" % run(ball(c, G, AY, 0, -150, mat=B.MAT_RUBBER), 0, 300)[0])


def m_reach(L):
    c, G, f0 = L.c, L.G, L.flags[0]
    edge = f0[1] + 1                                       # the bridge's near row
    top = L.goal_y - 1                                     # the lodestone's row

    def isl(p):
        x, y = cell(p)
        return not p.air and G - 2 <= x <= G + 2 and top <= y <= L.AY + 2
    n = hit = 0
    best = 99.0
    for x10 in range(10 * (G - 4) + 5, 10 * (G + 6) + 5, 5):
        for vy in (200, 300, 384, 448):
            for vx in (-200, -100, 0, 100, 200):
                for hop in (None, 0, 3, 6, 9, 12, 15, 18):
                    for again in (None, 8, 14, 20):
                        if hop is None and again is not None:
                            continue
                        p = ball(c, int(x10 / 10.0), edge, vx, vy, gx=x10 / 10.0, gy=edge + 0.3)
                        ymax = 0
                        for i in range(140):
                            k = PY | (K_HOP if i == hop or (again is not None and hop is not None and i == hop + again)
                                      else 0)
                            nf = p.nfall
                            p.step(k)
                            if p.nfall != nf:
                                break
                            ymax = max(ymax, at(p)[1])
                            if isl(p):
                                hit += 1
                                break
                        n += 1
                        best = min(best, top - ymax)
    print("THE ISLAND FROM THE BRIDGE: %d tries off its near edge (20 places, 4 speeds, 5 slants, no Hop, one, two): "
          "%d land on the island; the nearest dies %.2f tiles short of row %d" % (n, hit, best, top))


def m_held(L):
    c = L.c
    falls, stuck = collections.defaultdict(list), []
    for k in L.stand:
        moved = 0
        for key in ALL8:
            p = ball(c, *k)
            r, _i = run(p, key, 660)
            if r == "FELL":
                falls[k].append(NAMES[key])
            moved += r != "end" or cell(p) != k
        if not moved:
            stuck.append(k)
    print("EVERY ARROW FROM REST ON EVERY TILE (%d tiles, 12 s each): tiles no arrow leaves: %s" % (len(L.stand), stuck))
    by = collections.defaultdict(list)
    for k, v in sorted(falls.items()):
        by[len(v)].append(k)
    for n in sorted(by, reverse=True):
        print("   %d of the 8 end in a fall from: %s" % (n, " ".join("(%d,%d)" % k for k in by[n])))


def m_soft(L):
    c = L.c
    cells = L.stand + [f for f in L.flags if f not in L.stand]
    succ = {}

    def settle(p):
        last, still = None, 0
        for _ in range(500):
            nf = p.nfall
            p.step(0)
            if p.goal:
                return "GOAL"
            if p.nfall != nf:
                return "FALL"
            st = (p.gx >> 8, p.gy >> 8, p.air)
            still = still + 1 if st == last else 0
            last = st
            if still > 12 and not p.air:
                break
        return cell(p)
    for k in cells:
        out = set()
        for key in ALL8:
            for T in (30, 70, 140, 300, 520):
                p = ball(c, *k)
                r, _i = run(p, key, T)
                out.add("GOAL" if r == "GOAL" else "FALL" if r == "FELL" else settle(p))
        succ[k] = out

    def closure(ok0):
        ok, more = set(), True
        while more:
            more = False
            for k, out in succ.items():
                if k not in ok and any(o in ok0 or o in ok for o in out):
                    ok.add(k)
                    more = True
        return ok
    nofall, anyhow = closure({"GOAL"}), closure({"GOAL", "FALL"})
    print("NO SOFTLOCK AT REST: %d tiles, moves of one arrow or pair held 0.5 - 9.5 s and let go: the goal with NO "
          "fall from %d, a goal or a fall from %d" % (len(succ), len(nofall), len(anyhow)))
    print("   not without a fall: %s; not at all: %s" % (sorted(set(succ) - nofall), sorted(set(succ) - anyhow)))


def m_walks(L):
    c = L.c
    keys = ALL8 + [0]
    for nm, st, T, N in (("the start", L.start, 400, 1200), ("flag 0", L.flags[0], 300, 2000),
                         ("the ledge", (L.WX, L.leg1[0][1] - 4), 300, 2000), ("flag 1", L.flags[-1], 300, 2000)):
        rng = random.Random(7)
        falls = collections.Counter()
        for _t in range(T):
            p = ball(c, *st)
            last, k, left = None, 0, 0
            for _i in range(N):
                if left == 0:
                    k, left = rng.choice(keys), rng.randint(15, 70)
                    if rng.random() < 0.15:
                        k |= K_HOP
                left -= 1
                nf = p.nfall
                p.step(k)
                k &= ~K_HOP
                if p.nfall != nf:
                    falls[last] += 1
                    break
                if p.goal:
                    break
                if not p.air:
                    last = cell(p)
        rows = collections.Counter()
        for (x, y), n in falls.items():
            rows["the bridge" if y in (L.flags[0][1], L.flags[0][1] + 1) and x >= L.flags[0][0] else
                 "the runway's end" if (x, y) == (L.G, L.RY) else "(%d,%d)" % (x, y)] += n
        print("RANDOM WALKS from %s (%d of %.0f s, a new key every 0.3 - 1.3 s): %d fell %s" % (
            nm, T, N / SEC, sum(falls.values()), dict(rows) or ""))


def m_frame(L):
    c, G, RY = L.c, L.G, L.RY
    f1 = L.flags[-1]
    print("THE GANTRY'S FLIGHT AND THE CAMERA (LODE.md section 2)")
    for herc in (0, 1):
        r = B._guide_run(c, herc, None)
        air = [f for f in r.rows if f["air"] and f["x"]]
        m = min(min(f["x"]["hi"] - f["x"]["off"], f["x"]["off"] - f["x"]["lo"]) for f in air)
        eps = B.cam_episodes(r.rows, "dc")
        print("   %s, the route: %d pans across (%d columns), %d of them in the air; the flight %.1f s, px %d - %d, "
              "the band's nearest edge %d px away" % (("CGA", "Hercules")[herc], len(eps), sum(e["amt"] for e in eps),
                                                      sum(1 for f in r.rows if f["air"] and f["dc"]),
                                                      len(air) / B.CARD_HZ[herc], min(f["px"] for f in air),
                                                      max(f["px"] for f in air), m))

    def line(start, row, herc, vcap, xoff):
        p = ball(c, *start)
        r = B.CamRun(c, herc, p)                            # (a fresh camera: the CUT a respawn makes)
        st = {"ph": 0, "n": 0}

        def keys():
            gx, gy = at(p)
            if st["ph"] == 0:
                tx, ty = G + xoff, row + 0.5
                if abs(gx - tx) < 0.25 and abs(p.gvx) < 60:
                    st["ph"] = 1
                vx_t = max(-300, min(300, int((tx - gx) * 200)))
                vy_t = max(-300, min(300, int((ty - gy) * 200)))
                if vcap:
                    vx_t = max(-vcap, min(vcap, vx_t))
                return B.PLAN_W2K[(1 if p.gvx < vx_t - 8 else -1 if p.gvx > vx_t + 8 else 0,
                                   1 if p.gvy < vy_t - 8 else -1 if p.gvy > vy_t + 8 else 0)]
            fx = 0
            if not p.air:
                vx_t = int((G + xoff - gx) * 200)
                fx = 1 if p.gvx < vx_t - 8 else -1 if p.gvx > vx_t + 8 else 0
            return B.PLAN_W2K[(fx, 0 if vcap and p.gvy < -vcap else -1)]

        def stp():
            st["n"] += 1
            if st["n"] > 1500 or p.goal or p.nfall or (st["ph"] and not p.air and at(p)[1] < L.AY):
                return False
            p.step(keys())
        while r.frame(stp):
            pass
        return sum(abs(f["dc"]) for f in r.rows if f["air"]), p.nfall
    for start, nm in ((f1, "flag 1"), ((G + 3, RY + 4), "3 tiles east of the pocket (no flag is there)")):
        for herc in (0, 1):
            n = pans = fell = worst = 0
            for row in (RY + 2, RY + 3, RY + 4):
                for vcap in (None, 200, 120, 60):
                    for xoff in (0.5, 0.35, 0.65):
                        pan, nf = line(start, row, herc, vcap, xoff)
                        n += 1
                        pans += pan > 0
                        worst = max(worst, pan)
                        fell += nf
            print("   a CUT at %s, %s: %d lines to the gantry, %d pan in the air (the most %d columns), %d steer "
                  "out of the lane" % (nm, ("CGA", "Hercules")[herc], n, pans, worst, fell))


SECTIONS = (("start", m_start), ("flume", m_flume), ("mouth", m_mouth), ("hoist", m_hoist), ("sirens", m_sirens),
            ("wall", m_wall), ("gantry", m_gantry), ("island", m_island), ("reach", m_reach), ("held", m_held),
            ("soft", m_soft), ("walks", m_walks), ("frame", m_frame))


def main():
    a = sys.argv[1:]
    only = None
    if "--only" in a:
        i = a.index("--only")
        only = a[i + 1].split(",")
        del a[i:i + 2]
    path = a[0] if a else os.path.join(ROOT, "apps", "bonanza", "courses", "lode.bbc")
    L = Course(path)
    for name, fn in SECTIONS:
        if only is None or name in only:
            fn(L)


if __name__ == "__main__":
    main()
