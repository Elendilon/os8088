import sys
sys.path.insert(0, "/home/user/os8088/tools")
import bbcourse as B
import patch_tt
B.TRAP_CHECK = False
c = B.compile_course(open("../m4.bbc").read(), "../m4.bbc")
route = [t for t, _ in c.src.ways]
p = B.Physics(c, play=True); p.tsec = 0
p.route = [B._way_point(c, t) for t in route]
keys = []
for i in range(580): k = p.auto(); p.step(k); keys.append(k)
for back in ((23, 14), (22, 14), (23, 15)):
    q = B._clone(p); pre = []
    q.route = list(p.route[:9]) + [B._way_point(c, back)]; q.wp = 9
    for i in range(400):
        k = q.auto(); q.step(k); pre.append(k)
        if (q.gx >> 12, q.gy >> 12) == back and abs(q.gvx) < 16 and abs(q.gvy) < 16 and not q.air: break
    good = []
    for t in range(0, 140):
        r = B._clone(q)
        for i in range(320):
            x = r.gx >> 8
            sx = 1 if x < 16 * back[0] + 6 else -1 if x > 16 * back[0] + 10 else 0
            r.step(B.PLAN_W2K[(sx, 1)] | (B.K_HOP if i == t else 0))
            if r.nfall: break
            if not r.air and (r.gy >> 12) >= 23: good.append((t, i)); break
    print("run-up from", back, "(reached at rest after %d steps of arrows)" % len(pre), "-> hold +y, one Hop at t: made for", [g[0] for g in good], "landing step", good[0][1] if good else None)
