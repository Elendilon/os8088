#!/usr/bin/env python3
"""t_bbgame - ADD TO THE GAME (SPEC.md 130.56.17): tools/bbgame.py composes BONANZA.O88 from the prebuilt
pieces (`make bbgamebin`) with no assembler, on the host:

 1. THE SHIPPED LIST: composed with no added course, the package is build/bonanza.o88 byte for byte
    (the course compile through the cache, the pieces v0's, os88pkg as the Makefile runs it);
 2. ONE ADDED COURSE: XTRA (FIRST's text under another NAME and title) composed after the shipped ones -
    os88pkg validated it, its course table names XTRA in row 8, and it is byte for byte the package
    `make BUILD=... BZ_COURSES="<shipped> XTRA"` assembles with nasm (the tables written at the map's
    places are all that nasm would have changed);
 3. --pad0 XTRA: XTRA takes pad 0's course's K (ROLL's, 6), ROLL goes last, the pathway's pad 0 names
    XTRA - again byte for byte the nasm build of that list and that pathway; and a floppy holds it;
 4. REFUSALS: an inc that needs a larger BZ_PROPMAX is refused naming the lanes, a course NAME that is
    the game's own symbol (TITLE) is refused, a TEST course is refused.

The nasm builds (2, 3) seed their art from the composition's compile (make -o .bz-crs), so they assemble
the same course parts: what they check is the assembly, which is the claim. Red, by hand: take a table
out of bbgame.PATCH (item 2 refuses), or skip the patch loop in compose (items 2 and 3 differ from nasm).
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B  # noqa: E402
import bbgame as G  # noqa: E402
import os88pkg  # noqa: E402

fails = []


def ok(cond, what):
    print("%s %s" % ("ok  " if cond else "FAIL", what), flush=True)
    if not cond:
        fails.append(what)


def rb(p):
    with open(p, "rb") as f:
        return f.read()


def nasm_build(tree, courses, art, path=None):
    """the Makefile's package for COURSES in the private tree TREE (under build/), its art seeded from ART"""
    rel = os.path.relpath(tree, ROOT)
    shutil.rmtree(tree, ignore_errors=True)
    shutil.copytree(art, os.path.join(tree, "bonanza-art"))
    cmd = ["make", "--no-print-directory", "BUILD=" + rel, "BZ_COURSES=" + " ".join(courses),
           "-o", rel + "/bonanza-art/.bz-crs", rel + "/bonanza.o88"]
    if path:
        cmd.insert(3, "BZ_PATH=" + path)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:])
    return os.path.join(tree, "bonanza.o88") if r.returncode == 0 else None


def names_row(o88, k):
    img = os88pkg.image_unwrap(rb(o88))
    mp = G.json.load(open(os.path.join(G.BIN, "v1", "map.json")))
    off = [o for p, o in mp["map"]["BZ_CRS_NAMES"] if p == "bonanza.bin"][0]
    return img[off + 6 * k:off + 6 * k + 6]


if not os.path.isfile(os.path.join(ROOT, "build", "bonanza.o88")) or \
        not os.path.isfile(os.path.join(G.BIN, "v1", "map.json")):
    sys.exit("t_bbgame: needs build/bonanza.o88 and %s (make bonanza bbgamebin)" % G.BIN)
ship = G.shipped_paths()
with tempfile.TemporaryDirectory() as t:
    log = lambda s: None  # noqa: E731
    # 1. the shipped list
    o0 = os.path.join(t, "ship.o88")
    G.compose(o0, [], log=log)
    ok(rb(o0) == rb(os.path.join(ROOT, "build", "bonanza.o88")),
       "the shipped list composed is build/bonanza.o88 byte for byte (%d bytes)" % os.path.getsize(o0))

    # 2. one added course
    xt = os.path.join(t, "xtra.bbc")
    with open(xt, "w") as f:
        f.write(open(os.path.join(B.COURSE_DIR, "first.bbc")).read().replace(
            'course FIRST "First Roll"', 'course XTRA "Extra Roll"', 1))
    o1, w1 = os.path.join(t, "xtra.o88"), os.path.join(t, "w1")
    G.compose(o1, [xt], work=w1, log=log)
    ok(names_row(o1, len(ship)) == b"XTRA\0\0", "the package's course table names XTRA in row %d" % len(ship))
    tree = os.path.join(ROOT, "build", "t_bbgame")
    try:
        n1 = nasm_build(tree, [os.path.relpath(p, ROOT) for p in ship] + [xt], os.path.join(w1, "art"))
        ok(n1 is not None and rb(n1) == rb(o1), "shipped + XTRA composed is the nasm build of that list byte "
           "for byte (%d bytes)" % os.path.getsize(o1))

        # 3. --pad0
        o2, w2 = os.path.join(t, "pad0.o88"), os.path.join(t, "w2")
        img = os.path.join(t, "pad0.img")
        G.compose(o2, [xt], pad0="XTRA", disk=img, size=360, work=w2, log=log)
        k0 = [G._course_name(p) for p in ship].index("ROLL")
        ok(names_row(o2, k0) == b"XTRA\0\0" and names_row(o2, len(ship)) == b"ROLL\0\0",
           "--pad0 XTRA: XTRA is row %d, ROLL row %d" % (k0, len(ship)))
        lst = [os.path.relpath(p, ROOT) for p in ship]
        lst = lst[:k0] + [xt] + lst[k0 + 1:] + [lst[k0]]
        n2 = nasm_build(tree, lst, os.path.join(w2, "art"), path=os.path.join(w2, "path.bbc"))
        ok(n2 is not None and rb(n2) == rb(o2), "--pad0 composed is the nasm build of that list and pathway")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "os88disk.py"), "--verify", img],
                           capture_output=True, text=True)
        ok(r.returncode == 0 and os.path.getsize(img) == 368640, "the 360 KB floppy verifies")
    finally:
        shutil.rmtree(tree, ignore_errors=True)

    # 4. refusals
    inc = open(os.path.join(G.BIN, "v1", "bzcourse.inc")).read()
    big = inc.replace("BZ_PROPMAX      equ 50", "BZ_PROPMAX      equ 52", 1)
    try:
        G.compare(inc, big)
        ok(False, "a larger BZ_PROPMAX is refused")
    except G.Refused as e:
        ok("LANES" in str(e), "a larger BZ_PROPMAX is refused naming the lanes")
    for name, txt, want in (("TITLE", 'course TITLE "Extra Roll"', "symbol"),
                            ("TSTX", 'course TSTX "Extra Roll"\ntest', "TEST")):
        p = os.path.join(t, name.lower() + ".bbc")
        with open(p, "w") as f:
            f.write(open(os.path.join(B.COURSE_DIR, "first.bbc")).read().replace('course FIRST "First Roll"', txt, 1))
        try:
            G.compose(os.path.join(t, "r.o88"), [p], log=log)
            ok(False, "a course named %s is refused" % name)
        except G.Refused as e:
            ok(want in str(e), "a course %s is refused (%s)" % (name, str(e)[:90]))
print("t_bbgame: %s" % ("%d failed" % len(fails) if fails else "ok"))
sys.exit(1 if fails else 0)
