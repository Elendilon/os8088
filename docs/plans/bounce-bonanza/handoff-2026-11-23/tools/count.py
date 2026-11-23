import sys, json, collections
sys.path.insert(0, sys.argv[1] + "/tools")
import bbcourse as B, bbedjob as J
B.TRAP_CHECK = False
B.BLK_MAX = 1 << 30
D = "/tmp/claude-0/-home-user-os8088/50152400-584f-5f02-99a3-d60ce56fde4a/scratchpad/"
c = B.compile_course(open(D + "mo.bbc").read(), "mo.bbc", occluders=True)
d = J.occ_data(c)
unc = {tuple(k) for k in json.load(open(D + "occwhy/railreach-mono.json"))["unc"]}
reach = {(r.wx, r.wy): r for r in c.reach}


def grp(name, f):
    rs = [r for r in d["shipped"] if r["own"] and f(r["own"][0][0], r["own"][0][1])]
    only = [r for r in rs if {tuple(x) for x in r["needs"]} <= unc]
    fl = [r for r in rs if any(reach[tuple(x)].kind != B.KIND_VOID for x in r["needs"])]
    cells = collections.Counter(tuple(x) for r in rs for x in r["needs"])
    print(name, "shipped", len(rs), "doubtful-only", len(only), "needed by a floor", len(fl))
    print("   needing cells:", [(k, n, "VOID" if reach[k].kind == 0 else "floor", "DOUBT" if k in unc else "",
                                 reach[k].src) for k, n in cells.most_common(14)])


grp("back wall 8..11 x 5..8", lambda x, y: 8 <= x <= 11 and 5 <= y <= 8)
grp("floor B 12..15 x 5..8", lambda x, y: 12 <= x <= 15 and 5 <= y <= 8)
grp("cup sandpit 23..25 x 51..53", lambda x, y: 23 <= x <= 25 and 51 <= y <= 53)
only = [r for r in d["shipped"] if {tuple(x) for x in r["needs"]} <= unc]
print("doubtful-only shipped records by owner:",
      collections.Counter((r["own"][0][0], r["own"][0][1]) for r in only if r["own"]).most_common(12))
