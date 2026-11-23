import sys; sys.path.insert(0, "tools")
import bbcourse as B
B.TRAP_CHECK = False
c = B.compile_course(open(sys.argv[1]).read(), sys.argv[1])
def run(route, label):
    pts = [B._way_point(c, t) for t in route]
    p = B.Physics(c, play=True); p.tsec = 0; p.route = list(pts)
    last, since, n = -1, 0, 0
    hist = []
    while n < B.DEMO_STEPS and not p.goal and not p.nfall:
        p.step(p.auto()); n += 1
        if p.wp != last:
            hist.append((n, p.wp)); last = p.wp
    cell = (p.gx >> 12, p.gy >> 12)
    print(label, "steps", n, "goal", p.goal, "falls", p.nfall)
    print("  reached waypoint %d of %d (%s) at step %d; stuck at cell %s z %d" % (
        p.wp, len(route), route[p.wp] if p.wp < len(route) else "-", hist[-1][0], cell, p.gz >> 8))
run([t for t, _ in c.src.ways], "MAIN")
run(B.branch_route(c, "GLASS"), "GLASS")
