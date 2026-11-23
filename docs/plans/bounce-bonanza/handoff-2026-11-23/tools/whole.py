import sys, time, os
sys.path.insert(0, "/home/user/os8088/tools")
import bbcourse as B
import patch_tt
B.TRAP_CHECK = False
deep = {"wp": 0, "spent": 0}
_pt = B._plan_tries
def tries(p, spent, *a, **k):
    for r in _pt(p, spent, *a, **k):
        if r[1].wp > deep["wp"]:
            deep["wp"] = r[1].wp; deep["cell"] = (r[1].gx >> 12, r[1].gy >> 12)
        deep["spent"] = spent[0]
        yield r
B._plan_tries = tries
t = time.time()
try:
    c = B.compile_course(open(sys.argv[1]).read(), sys.argv[1])
except B.CourseError as e:
    print("REFUSED:", str(e)[:300]); sys.exit()
print("compiled %.0fs, limit %s" % (time.time() - t, getattr(c, "limit", None)), flush=True)
for w in c.warnings: print("warning:", w["msg"][:120])
main = [t for t, _ in c.src.ways]
deep.update(wp=0)
k = B.route_plan(c)
print("MAIN route_plan:", ("%d steps (%.1f s at %d/s)" % (len(k), len(k) / B.SEC_STEPS, B.SEC_STEPS)) if k else "None", "deepest wp", deep.get("wp"), main[min(deep["wp"], len(main)-1)], deep.get("cell"), "spent", deep["spent"], flush=True)
deep.update(wp=0)
g = B.branch_route(c, "GLASS")
k = B.branch_plan(c, "GLASS")
print("GLASS branch_plan:", ("%d steps (%.1f s)" % (len(k), len(k) / B.SEC_STEPS)) if k else "None", "deepest wp", deep.get("wp"), g[min(deep["wp"], len(g)-1)], deep.get("cell"), "spent", deep["spent"])
