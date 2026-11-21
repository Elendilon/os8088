#!/usr/bin/env python3
"""The Bounce Bonanza course builder's zip, used where there is no os8088 tree
(`make bbeditbundle`, tools/bbeditbundle.py, SPEC.md 130.56.11).

    make bbeditbundle && python3 tests/bbeditbundle.py

Unpacked in a temporary folder and run from THERE with `python -I`, with an
audit hook that fails on any file opened under the tree: the compiler's ROOT
must be the bundle's data/; bbedproj must read and write a shipped course
byte for byte and `check` it; bbedjob must draw MILL's picture and run its
full check; the pathway (which reads the course list out of data/Makefile)
must lay out; the window's module must import; and two zips from the same
tree must be the same bytes. Red: take the data/ ROOT out of bbcourse.py and
the hook catches the tree's files being read.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ZIP = os.path.join(TREE, "build", "os8088-course-builder.zip")
fails = []

PROBE = r'''
import os, sys
TREE = sys.argv[1]
B = os.path.dirname(os.path.abspath(__file__))
seen = set()
def hook(ev, a):
    if ev == "open" and a and isinstance(a[0], str):
        p = os.path.abspath(a[0])
        if p.startswith(TREE + os.sep):
            seen.add(p)
sys.addaudithook(hook)
sys.path.insert(0, B)
import bbcourse, bbedproj, bbedjob, bbedit
print("ROOT", bbcourse.ROOT)
p = os.path.join(B, "data", "apps", "bonanza", "courses", "mill.bbc")
d = bbedproj.Document.load(p)
print("ROUNDTRIP", d.text() == open(p, newline="").read())
print("CELLS", len(d.analysis()["cells"]))
print("PICTURE", bbedjob.picture(p, os.path.join(B, "pic")))
print("CHECK", bbedjob.check(p, False))
pa = os.path.join(B, "data", "apps", "bonanza", "courses", "path.bbc")
print("PATHWAY", bbedjob.picture(pa, os.path.join(B, "pic-path")))
print("TREE_OPENED", sorted(seen))
'''


def ok(cond, what):
    print("%s %s" % ("ok  " if cond else "FAIL", what), flush=True)
    if not cond:
        fails.append(what)


if not os.path.exists(ZIP):
    sys.exit("no %s: make bbeditbundle" % ZIP)
with tempfile.TemporaryDirectory() as t:
    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        z.extractall(t)
    b = os.path.join(t, "os8088-course-builder")
    for f in ("bbedit.py", "bbedproj.py", "bbedjob.py", "bbcourse.py", "README.TXT", "data/Makefile",
              "data/fonts/tallx.f8", "data/apps/bonanza/courses/kit.bzk", "data/apps/bonanza/courses/mill.bbc"):
        ok(os.path.isfile(os.path.join(b, f)), "the zip holds %s" % f)
    with open(os.path.join(b, "probe.py"), "w") as f:
        f.write(PROBE)
    r = subprocess.run([sys.executable, "-I", os.path.join(b, "probe.py"), TREE], cwd=t, capture_output=True,
                       text=True, timeout=600)
    out = r.stdout
    vals = {}
    for ln in out.splitlines():
        k, _, v = ln.partition(" ")
        if k.isupper():
            vals[k] = v
    ok(r.returncode == 0, "the probe ran (%s)" % (r.stderr.strip().splitlines()[-1:] or ["exit 0"])[0])
    ok(vals.get("ROOT") == os.path.join(b, "data"), "the compiler's ROOT is the bundle's data/ (%s)" % vals.get("ROOT"))
    ok(vals.get("ROUNDTRIP") == "True", "MILL read and written byte for byte")
    ok(vals.get("CELLS", "0").isdigit() and int(vals.get("CELLS", "0")) > 100, "MILL lays out (%s cells)"
       % vals.get("CELLS"))
    ok(vals.get("PICTURE") == "0" and os.path.isfile(os.path.join(b, "pic", "owners.bin")), "MILL's picture drawn")
    ok(vals.get("CHECK") == "0", "MILL's full check passes")
    ok(vals.get("PATHWAY") == "0", "the pathway lays out from data/Makefile's course list")
    ok(vals.get("TREE_OPENED") == "[]", "nothing read from the tree (%s)" % vals.get("TREE_OPENED", "")[:200])
with tempfile.TemporaryDirectory() as t:
    z2 = os.path.join(t, "again.zip")
    subprocess.run([sys.executable, os.path.join(TREE, "tools", "bbeditbundle.py"), z2], check=True,
                   capture_output=True)
    ok(open(z2, "rb").read() == open(ZIP, "rb").read(), "two zips from the same tree are the same bytes")
print("bbeditbundle: %s" % ("%d failed" % len(fails) if fails else "ok"))
sys.exit(1 if fails else 0)
