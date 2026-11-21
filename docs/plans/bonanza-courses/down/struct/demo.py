#!/usr/bin/env python3
# run from the repository root (it imports tools/bbcourse.py from there)
"""demo.py plan BASE.bbc KEYS.json      : the route demo's keys on BASE (route_demo's own choice: arrows, else
                                          route_plan's hopping search), saved
   demo.py replay KEYS.json COURSE.bbc...: those keys replayed on each course - goal?, steps, flags, trajectory
                                          hash (the same hash as BASE = the same play, step for step)"""
import sys, os, json, hashlib, time
sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
import bbcourse as B


def run(c, keys):
    p = B.Physics(c, play=True)
    h = hashlib.sha1()
    n = 0
    for k in keys:
        if p.goal or p.tout:
            break
        p.step(k)
        n += 1
        h.update(repr((p.gx, p.gy, p.gz, p.gvx, p.gvy, p.air, p.mat)).encode())
    return p, n, h.hexdigest()[:16]


if sys.argv[1] == "plan":
    t = time.time()
    c = B.compile_course(sys.argv[2])
    p = B.Physics(c, play=True)
    keys = []
    while len(keys) < B.DEMO_STEPS and not p.goal and not p.tout:
        k = p.auto(); p.step(k); keys.append(k)
    how = "arrows"
    nfl = sum(1 for q in c.props if q["kind"] == B.PK_CHECKPOINT)
    if not p.goal or p.nckpt < nfl:
        plan = B.route_plan(c)
        if plan is not None:
            keys, how = list(plan), "route_plan"
    json.dump({"how": how, "keys": keys}, open(sys.argv[3], "w"))
    p, n, hh = run(c, keys)
    print("plan by %s in %.0fs: goal %s after %d steps (%.1f s), flags %d/%d, ball %s, trajectory %s"
          % (how, time.time() - t, p.goal, n, n / float(B.SEC_STEPS), p.nckpt, nfl, p.mat, hh))
else:
    keys = json.load(open(sys.argv[2]))["keys"]
    for path in sys.argv[3:]:
        c = B.compile_course(path)
        nfl = sum(1 for q in c.props if q["kind"] == B.PK_CHECKPOINT)
        p, n, hh = run(c, keys)
        print("%s: goal %s after %d steps (%.1f s), flags %d/%d, ball %s, trajectory %s"
              % (os.path.basename(path), p.goal, n, n / float(B.SEC_STEPS), p.nckpt, nfl, p.mat, hh))
