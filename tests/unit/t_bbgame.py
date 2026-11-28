#!/usr/bin/env python3
"""t_bbgame - ADD TO THE GAME (SPEC.md 137.58.17, 137.58.36): tools/bbgame.py composes BONANZA.O88 from the
shipped build's own pieces (`make bbgamebin`: the pieces and their map, no variants) with no assembler:

 1. THE SHIPPED LIST: composed with no added course, the package is build/bonanza.o88 byte for byte
    (the course compile through the cache, the pieces the build's, os88pkg as the Makefile runs it), and its
    --disk --size 360 is build/bonanza360.img byte for byte when `make bonanzadisk` has made that;
 2. TWO ADDED COURSES: XTRA and XTRB (FIRST's and HOP's text under other NAMEs and titles) composed after the
    shipped ones - os88pkg validated it, its course table names them in rows 12 and 13, its counts byte says 14,
    and it is byte for byte the package `make BUILD=... BZ_COURSES="<shipped> XTRA XTRB"` assembles with nasm
    (the tables and counts written at the map's places are all that nasm would have changed);
 3. --pad0 XTRA: XTRA takes pad 0's course's K (ROLL's, 6), ROLL goes last, the pathway's pad 0 names
    XTRA - again byte for byte the nasm build of that list and that pathway; and a floppy holds it;
 4. REFUSALS: an inc that needs a larger BZ_PROPMAX is refused naming the lanes, a pathway past BZ_PAD_MAX pads
    is refused naming it, a course part row of a form the shipped rows lack is refused, a course NAME that is
    the game's own symbol (TITLE) is refused, a TEST course is refused, more than BZ_CRS_MAX courses are refused;
 5. A BIGGER MAP: the shipped pathway with XTRA on a THIRTEENTH pad (`# builder-course:`, the pad, route and icon
    bbedmap.place_course writes) composed with --path - 13 pads where the shipped map has 12 -
    os88pkg validated it, its course table names XTRA, and it is byte for byte the package
    `make BZ_COURSES=... BZ_PATH=...` assembles with nasm; RED: the same game with BZ_CRS_COUNTS left as the
    shipped one's (the save's pad guard at 12 where the map has 13) is not nasm's build;
 6. A BIGGER MAP, NO ADDED COURSE: FIRST on a thirteenth pad as well (no `# builder-course:`) composes, byte for byte
    nasm's build of the shipped list and that pathway.

The nasm builds (2, 3, 5, 6) seed their art from the composition's compile (make -o .bz-crs), so they assemble
the same course parts: what they check is the assembly, which is the claim. Red, by hand: take a table
out of bbgame.PATCH (item 2 refuses), or skip a table's write (compose's _skip: items 2, 3 and 5 differ).
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


MAP = G.json.load(open(os.path.join(G.BIN, "map.json"))) if os.path.isfile(os.path.join(G.BIN, "map.json")) else None


def at(o88, table):
    img = os88pkg.image_unwrap(rb(o88))
    return img, [o for p, o in MAP["map"][table] if p == "bonanza.bin"][0]


def names_row(o88, k):
    img, off = at(o88, "BZ_CRS_NAMES")
    return img[off + 6 * k:off + 6 * k + 6]


def counts(o88):
    img, off = at(o88, "BZ_CRS_COUNTS")
    return tuple(img[off:off + 3])


def copy_course(src, dst, name, title):
    with open(dst, "w") as f:
        txt = open(os.path.join(B.COURSE_DIR, src)).read()
        old = [ln for ln in txt.splitlines() if ln.startswith("course ")][0]
        f.write(txt.replace(old, 'course %s "%s"' % (name, title), 1))


if not os.path.isfile(os.path.join(ROOT, "build", "bonanza.o88")) or MAP is None:
    sys.exit("t_bbgame: needs build/bonanza.o88 and %s/map.json (make bonanza bbgamebin)" % G.BIN)
ship = G.shipped_paths()
with tempfile.TemporaryDirectory() as t:
    log = lambda s: None  # noqa: E731
    # 1. the shipped list
    o0, d0 = os.path.join(t, "ship.o88"), os.path.join(t, "ship.img")
    G.compose(o0, [], disk=d0, size=360, log=log)
    ok(rb(o0) == rb(os.path.join(ROOT, "build", "bonanza.o88")),
       "the shipped list composed is build/bonanza.o88 byte for byte (%d bytes)" % os.path.getsize(o0))
    ok(counts(o0) == (len(ship), len(ship), 12), "its counts are %d courses, %d demos, 12 pads" % (len(ship), len(ship)))
    ref360 = os.path.join(ROOT, "build", "bonanza360.img")
    if os.path.isfile(ref360):   # bonanzadisk is on demand, not in `all`
        ok(rb(d0) == rb(ref360), "its --disk --size 360 is build/bonanza360.img byte for byte")
    else:
        print("skip its --disk is build/bonanza360.img (no image: make bonanzadisk)")

    # 2. two added courses
    xt, xb = os.path.join(t, "xtra.bbc"), os.path.join(t, "xtrb.bbc")
    copy_course("first.bbc", xt, "XTRA", "Extra Roll")
    copy_course("hop.bbc", xb, "XTRB", "Extra Hop")
    o1, w1 = os.path.join(t, "xtra.o88"), os.path.join(t, "w1")
    G.compose(o1, [xt, xb], work=w1, log=log)
    n = len(ship)
    ok(names_row(o1, n) == b"XTRA\0\0" and names_row(o1, n + 1) == b"XTRB\0\0" and counts(o1)[:2] == (n + 2, n + 2)
       and os88pkg.part_table(os88pkg.image_unwrap(rb(o1)))[0] is not None,
       "two added courses: os88pkg validated it, its course table names XTRA and XTRB in rows %d, %d, its counts "
       "say %d courses and %d demos" % (n, n + 1, n + 2, n + 2))
    tree = os.path.join(ROOT, "build", "t_bbgame")
    try:
        n1 = nasm_build(tree, [os.path.relpath(p, ROOT) for p in ship] + [xt, xb], os.path.join(w1, "art"))
        ok(n1 is not None and rb(n1) == rb(o1), "shipped + XTRA + XTRB composed is the nasm build of that list byte "
           "for byte (%d bytes, %+d against the shipped)" % (os.path.getsize(o1), os.path.getsize(o1)
                                                             - os.path.getsize(o0)))
        o1r = os.path.join(t, "xtra-red.o88")
        G.compose(o1r, [xt, xb], work=os.path.join(t, "w1r"), log=log, _skip=("BZ_CRS_NAMES",))
        ok(n1 is not None and rb(o1r) != rb(n1), "RED: the same game with its NAMES table not written is not nasm's")

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

        # 5. a bigger map: XTRA on a thirteenth pad of the author's pathway (pad 12, off pad 7: the shipped map has 12)
        pd = os.path.join(t, "map")
        os.makedirs(pd)
        shutil.copyfile(xt, os.path.join(pd, "xtra.bbc"))
        pth = os.path.join(pd, "path.bbc")
        with open(pth, "w", encoding="ascii") as f:
            f.write(open(os.path.join(B.COURSE_DIR, "path.bbc"), encoding="ascii").read()
                    + "# builder-course: xtra.bbc\npad 12 XTRA 7 6\nroute 7 12 exit 0  path 3,10 7,6\n"
                    "icon 12 icons/first32x24.bba 0 64\n")
        o5, w5 = os.path.join(t, "map.o88"), os.path.join(t, "w5")
        G.compose(o5, [], pathway=pth, work=w5, log=log)
        inc5 = open(os.path.join(w5, "art", "bzcourse.inc")).read()
        ok("BZ_PATH_NPAD    equ 13" in inc5 and counts(o5) == (n + 1, n + 1, 13)
           and names_row(o5, len(ship)) == b"XTRA\0\0",
           "a thirteenth pad: composed with --path, its counts say 13 pads, its course table names XTRA")
        n5 = nasm_build(tree, [os.path.relpath(p, ROOT) for p in ship] + [os.path.join(pd, "xtra.bbc")],
                        os.path.join(w5, "art"), path=pth)
        ok(n5 is not None and rb(n5) == rb(o5), "the bigger map composed is the nasm build of that list and pathway "
           "byte for byte (%d bytes)" % os.path.getsize(o5))
        o6 = os.path.join(t, "red.o88")
        G.compose(o6, [], pathway=pth, work=os.path.join(t, "w6"), log=log, _skip=("BZ_CRS_COUNTS",))
        ok(n5 is not None and rb(o6) != rb(n5) and counts(o6) == (n, n, 12),
           "RED: the shipped counts left in (the save's pad guard at 12) are not nasm's build")

        # 6. a bigger map and no added course: FIRST on a thirteenth pad as well
        p0 = os.path.join(pd, "path0.bbc")
        with open(p0, "w", encoding="ascii") as f:
            f.write(open(os.path.join(B.COURSE_DIR, "path.bbc"), encoding="ascii").read()
                    + "pad 12 FIRST 7 6\nroute 7 12 exit 0  path 3,10 7,6\nicon 12 icons/first32x24.bba 0 64\n")
        o7, w7 = os.path.join(t, "map0.o88"), os.path.join(t, "w7")
        G.compose(o7, [], pathway=p0, work=w7, log=log)
        n7 = nasm_build(tree, [os.path.relpath(p, ROOT) for p in ship], os.path.join(w7, "art"), path=p0)
        ok(n7 is not None and rb(n7) == rb(o7) and counts(o7) == (n, n, 13),
           "no added course, FIRST on a thirteenth pad too: the nasm build of the shipped list and that pathway byte "
           "for byte (%d bytes)" % os.path.getsize(o7))
    finally:
        shutil.rmtree(tree, ignore_errors=True)

    # 4. refusals
    inc = open(os.path.join(G.BIN, "bzcourse.inc")).read()
    big = inc.replace("BZ_PROPMAX      equ 50", "BZ_PROPMAX      equ 52", 1)
    many = G.re.sub(r"^(BZ_PATH_NPAD\s+equ\s+)\d+", lambda m: m.group(1) + "24", inc, count=1, flags=G.re.M)
    arena = G.re.sub(r"(OS88_PART OP_ASSET, OP_LAZY \| OP_COMP)(   ; RESERVED)", r"\1 | OP_ARENA\2", inc, count=1)
    for what, txt, want in (("a pathway of 24 pads", many, "BZ_PAD_MAX"), ("a larger BZ_PROPMAX", big, "LANES"),
                            ("a course row of a form no shipped row has", arena, "a form no shipped course")):
        try:
            G.compare(inc, txt, MAP["info"], MAP["forms"])
            ok(False, "%s is refused" % what)
        except G.Refused as e:
            ok(want in str(e), "%s is refused naming %s" % (what, want))
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
    try:
        G.compose(os.path.join(t, "r.o88"), [xt] * (B.CRS_MAX - len(ship) + 1), log=log)
        ok(False, "more than BZ_CRS_MAX courses are refused")
    except G.Refused as e:
        ok("BZ_CRS_MAX" in str(e), "more than BZ_CRS_MAX courses are refused (%s)" % str(e)[:80])
print("t_bbgame: %s" % ("%d failed" % len(fails) if fails else "ok"))
sys.exit(1 if fails else 0)
