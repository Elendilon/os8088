"""occ-out's proto*.txt -> every variant's figures per course and over the seven (the report's tables)"""
import glob
import os
import re
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
rows = {}
course = None
for f in sorted(glob.glob(os.path.join(HERE, "proto*.txt"))):
    for ln in open(f):
        m = re.match(r"^(\S+) \(\S+\): .*RAM (\d+), LZ4 (\d+), LZB (\d+); with NO occluders RAM (\d+), LZ4 (\d+), LZB (\d+)", ln)
        if m:
            course = m.group(1)
            rows.setdefault(course, {})["(none)"] = (0, int(m.group(5)), int(m.group(6)), int(m.group(7)))
            continue
        m = re.match(r"^  (\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", ln)
        if m and course and m.group(1) != "variant":
            rows[course][m.group(1)] = (int(m.group(4)), int(m.group(8)), int(m.group(10)), int(m.group(11)))
order = ["BENCH", "FIRST", "TRIAL", "MILL", "MOON", "PEAK", "PLAY"]
vs = []
for c in order:
    for v in rows.get(c, {}):
        if v not in vs:
            vs.append(v)
base = [sum(rows[c]["base"][i] for c in order) for i in range(4)]
print("%-11s %8s %8s %8s %8s   %8s %8s %8s" % ("variant", "records", "RAM", "LZ4", "LZB", "dRAM", "dLZ4", "dLZB"))
for v in vs:
    if not all(v in rows.get(c, {}) for c in order):
        print("%-11s (not on every course)" % v)
        continue
    t = [sum(rows[c][v][i] for c in order) for i in range(4)]
    print("%-11s %8d %8d %8d %8d   %+8d %+8d %+8d" % (v, t[0], t[1], t[2], t[3], t[1] - base[1], t[2] - base[2], t[3] - base[3]))
print()
for v in sys.argv[1:]:
    print(v + ": " + "; ".join("%s %d rec, RAM %d, LZB %d" % (c, *(rows[c][v][i] for i in (0, 1, 3))) for c in order))
