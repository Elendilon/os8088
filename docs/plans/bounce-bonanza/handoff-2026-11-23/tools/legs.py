import sys, time, pickle, os
sys.path.insert(0, "/home/user/os8088/tools")
import bbcourse as B
import patch_tt
B.TRAP_CHECK = False
src = sys.argv[1]
only = sys.argv[2] if len(sys.argv) > 2 else None
t0 = time.time()
c = B.compile_course(open(src).read(), src)
print("compiled %.0fs" % (time.time() - t0), flush=True)
main = [t for t, _ in c.src.ways]
glass = B.branch_route(c, "GLASS")
tt = B._plan_tt(c)

def start(route, i, mat):
    p = B.Physics(c, play=True); p.tsec = 0
    p.route = [B._way_point(c, t) for t in route]
    if p.mat != mat: p._setmat(mat)
    p._place(*route[i]); p._derive(True); p._ps()
    p.wp = i + 1
    return p

def leg(route, i, mat):
    p = start(route, i, mat)
    q = B._clone(p)
    ok, keys, fail = B._plan_leg(q, (), B.PLAN_SEG)
    cell = (q.gx >> 12, q.gy >> 12)
    if ok:
        return "arrows", len(keys), cell, q
    plain = (fail, cell, q.nfall, q.air)
    spent = [0]
    note = ""
    try:
        for keys, q2 in B._plan_tries(p, spent, False, True, None, tt):
            nh = sum(1 for k in keys if k & B.K_HOP)
            return "search(hops=%d)" % nh, len(keys), (q2.gx >> 12, q2.gy >> 12), q2
    except KeyError as e:
        note = " STAND-KeyError%s" % (e,)
        for keys, q2 in B._plan_tries(p, spent, False, True, None, None):
            nh = sum(1 for k in keys if k & B.K_HOP)
            return "search-noTT(hops=%d)%s" % (nh, note), len(keys), (q2.gx >> 12, q2.gy >> 12), q2
    return "FAIL plain-stuck@%s fall=%d spent=%d%s" % (cell, q.nfall, spent[0], note), fail, cell, q

for name, route, sw in (("MAIN", main, None), ("GLASS", glass, glass.index((17, 27)))):
    if only and name != only: continue
    print("==", name, route)
    for i in range(int(os.environ.get("I0", 0)), len(route) - 1):
        mat = B.MAT_GLASS if sw is not None and i >= sw else c.ball
        t = time.time()
        r, n, cell, q = leg(route, i, mat)
        print("%2d %s -> %s  %-40s steps %4d end %s mat %s (%.0fs)" % (i, route[i], route[i+1], r, n, cell,
              B.MAT_NAMES[q.mat], time.time() - t), flush=True)

if os.environ.get("CHAIN"):
    for name, route, sw in (("MAIN", main, None), ("GLASS", glass, glass.index((17, 27)))):
        if only and name != only: continue
        print("== CHAINED", name)
        p = B.Physics(c, play=True); p.tsec = 0
        p.route = [B._way_point(c, t) for t in route]
        total = 0
        while not p.goal and p.wp < len(route):
            i = p.wp
            q = B._clone(p)
            ok, keys, fail = B._plan_leg(q, (), B.PLAN_SEG)
            how = "arrows"
            if not ok:
                spent = [0]; got = None
                try:
                    got = next(B._plan_tries(p, spent, False, True, None, tt), None)
                except KeyError as e:
                    how = "noTT(KeyError %s) " % (e,)
                    got = next(B._plan_tries(p, spent, False, True, None, None), None)
                if got is None:
                    print("  leg ->%d %s FAILS: plain stuck at %s air %d falls %d" % (i, route[i] if i < len(route) else "-",
                          (q.gx >> 12, q.gy >> 12), q.air, q.nfall - p.nfall))
                    break
                keys, q = got
                how += "search(hops=%d)" % sum(1 for k in keys if k & B.K_HOP)
            total += len(keys)
            print("  ->wp%d %s via %s %d steps, now wp %d cell %s step %d mat %s" % (i, route[i], how, len(keys), q.wp,
                  (q.gx >> 12, q.gy >> 12), total, B.MAT_NAMES[q.mat]), flush=True)
            p = q
        print("  goal", p.goal, "total", total)
