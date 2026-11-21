#!/usr/bin/env python3
# run from the repository root (it imports tools/bbcourse.py from there)
"""compile one course, print its part sizes and save its CGA picture.  measure.py COURSE.bbc OUT.png"""
import sys, os, time
sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
import bbcourse as B
from PIL import Image
t = time.time()
c = B.compile_course(sys.argv[1])
print("compile %.0fs" % (time.time() - t))
rams = B.sheet_rams(c)
pl = getattr(c, "plan", None)
print("plan", None if not pl else {"n": pl["n"], "k": pl["k"], "fixed": pl["fixed"],
                                    "m0": [s["m0"] for s in pl["sheets"]]})
print("rams", [len(r) for r in rams])
st = list(c.sstored or [c.stored]) + ([c.wstored] if c.split else [])
print("lzb", [B.packed_len(s, "lzb") for s in st])
print("blocks", len(c.blocks), "records", len(c.records), "lines", c.lines)
img = Image.new("RGB", (c.width, c.lines))
img.putdata([B.CGA1[v] for r in c.pic for v in r])
img.save(sys.argv[2])
print("size", img.size)
