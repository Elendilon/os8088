#!/usr/bin/env python3
"""t_bbgame - ADD TO THE GAME (SPEC.md 130.58.17): tools/bbgame.py composes BONANZA.O88 from the prebuilt
pieces (`make bbgamebin`) with no assembler, on the host:

 1. THE SHIPPED LIST: composed with no added course, the package is build/bonanza.o88 byte for byte
    (the course compile through the cache, the pieces v0's, os88pkg as the Makefile runs it), and its
    --disk --size 360 is build/bonanza360.img byte for byte when `make bonanzadisk` has made that;
 2. ONE ADDED COURSE: XTRA (FIRST's text under another NAME and title) composed after the shipped ones -
    os88pkg validated it, its course table names XTRA in row 8, and it is byte for byte the package
    `make BUILD=... BZHEADROOM=1 BZ_COURSES="<shipped> XTRA"` assembles with nasm (the tables written at the map's
    places are all that nasm would have changed);
 3. --pad0 XTRA: XTRA takes pad 0's course's K (ROLL's, 6), ROLL goes last, the pathway's pad 0 names
    XTRA - again byte for byte the nasm build of that list and that pathway; and a floppy holds it;
 4. REFUSALS: an inc that needs a larger BZ_PROPMAX is refused naming the lanes, a course NAME that is
    the game's own symbol (TITLE) is refused, a TEST course is refused, a pathway past BZ_PAD_MAX pads is
    refused;
 5. A BIGGER MAP (SPEC.md 130.58.17.1): the shipped pathway with XTRA on a NINTH pad (`# builder-course:`, the
    pad, route and icon bbedmap.place_course writes) composed with --path - 9 pads and 26 signs where the
    shipped map has 8 and 23 - os88pkg validated it, its course table names XTRA, and it is byte for byte
    the package `make BZHEADROOM=1 BZ_COURSES=... BZ_PATH=...` assembles with nasm; the make recipe passes
    bbcourse.py --headroom; RED: the same game with the shipped map's pad count's bytes written in place of
    its own (the save file's guard at 8 where the map has 9) differs from nasm's;
 6. A BIGGER MAP, NO ADDED COURSE: FIRST on a ninth pad as well (no `# builder-course:`) composes from v0r, the
    shipped list's headroom variant (v0 refuses it), byte for byte nasm's `BZHEADROOM=1` build.

The nasm builds (2, 3, 5, 6) seed their art from the composition's compile (make -o .bz-crs), so they assemble
the same course parts: what they check is the assembly, which is the claim. Red, by hand: take a table
out of bbgame.PATCH (item 2 refuses), or skip the patch loop in compose (items 2, 3 and 5 differ from nasm).
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


def nasm_build(tree, courses, art, path=None, headroom=True):
    """the Makefile's package for COURSES in the private tree TREE (under build/), its art seeded from ART;
    HEADROOM: with BZHEADROOM=1 (SPEC.md 130.58.17.1), as an added course's prebuilt variant is made"""
    rel = os.path.relpath(tree, ROOT)
    shutil.rmtree(tree, ignore_errors=True)
    shutil.copytree(art, os.path.join(tree, "bonanza-art"))
    cmd = ["make", "--no-print-directory", "BUILD=" + rel, "BZ_COURSES=" + " ".join(courses),
           "-o", rel + "/bonanza-art/.bz-crs", rel + "/bonanza.o88"]
    if headroom:
        cmd.insert(3, "BZHEADROOM=1")
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
    o0, d0 = os.path.join(t, "ship.o88"), os.path.join(t, "ship.img")
    G.compose(o0, [], disk=d0, size=360, log=log)
    ok(rb(o0) == rb(os.path.join(ROOT, "build", "bonanza.o88")),
       "the shipped list composed is build/bonanza.o88 byte for byte (%d bytes)" % os.path.getsize(o0))
    ref360 = os.path.join(ROOT, "build", "bonanza360.img")
    if os.path.isfile(ref360):   # bonanzadisk is on demand, not in `all`
        ok(rb(d0) == rb(ref360), "its --disk --size 360 is build/bonanza360.img byte for byte")
    else:
        print("skip its --disk is build/bonanza360.img (no image: make bonanzadisk)")

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

        # 5. a bigger map: XTRA on a ninth pad of the author's pathway
        pd = os.path.join(t, "map")
        os.makedirs(pd)
        shutil.copyfile(xt, os.path.join(pd, "xtra.bbc"))
        pth = os.path.join(pd, "path.bbc")
        with open(pth, "w", encoding="ascii") as f:
            f.write(open(os.path.join(B.COURSE_DIR, "path.bbc"), encoding="ascii").read()
                    + "# builder-course: xtra.bbc\npad 8 XTRA 8 7\nroute 7 8 exit 0  path 4,11 8,7\n"
                    "icon 8 icons/first32x24.bba 0 80\n")
        o5, w5 = os.path.join(t, "map.o88"), os.path.join(t, "w5")
        G.compose(o5, [], pathway=pth, work=w5, log=log)
        inc5 = open(os.path.join(w5, "art", "bzcourse.inc")).read()
        img5 = os88pkg.image_unwrap(rb(o5))
        ok("BZ_PATH_NPAD    equ 9" in inc5 and os88pkg.part_table(img5)[0] is not None
           and names_row(o5, len(ship)) == b"XTRA\0\0",
           "a ninth pad: composed with --path (9 pads), os88pkg validated it, its course table names XTRA")
        n5 = nasm_build(tree, [os.path.relpath(p, ROOT) for p in ship] + [os.path.join(pd, "xtra.bbc")],
                        os.path.join(w5, "art"), path=pth)
        ok(n5 is not None and rb(n5) == rb(o5), "the bigger map composed is the nasm build of that list and pathway "
           "with BZHEADROOM=1 byte for byte (%d bytes)" % os.path.getsize(o5))
        r = subprocess.run(["make", "-n", "-B", "--no-print-directory", "BUILD=" + os.path.relpath(tree, ROOT),
                            "BZHEADROOM=1", os.path.relpath(tree, ROOT) + "/bonanza-art/.bz-crs"],
                           cwd=ROOT, capture_output=True, text=True)
        ok(" --headroom " in r.stdout, "BZHEADROOM=1's recipe runs bbcourse.py --headroom")
        o6 = os.path.join(t, "red.o88")
        G.compose(o6, [], pathway=pth, work=os.path.join(t, "w6"), log=log, _npad=8)
        ok(n5 is not None and rb(o6) != rb(n5), "RED: the shipped map's pad count's bytes (the save's guard at 8) "
           "written instead are not nasm's build")

        # 6. a bigger map and no added course: FIRST on a ninth pad as well - v0r, the shipped list's headroom build
        p0 = os.path.join(pd, "path0.bbc")
        with open(p0, "w", encoding="ascii") as f:
            f.write(open(os.path.join(B.COURSE_DIR, "path.bbc"), encoding="ascii").read()
                    + "pad 8 FIRST 8 7\nroute 7 8 exit 0  path 4,11 8,7\nicon 8 icons/first32x24.bba 0 80\n")
        o7, w7 = os.path.join(t, "map0.o88"), os.path.join(t, "w7")
        said = []
        G.compose(o7, [], pathway=p0, work=w7, log=said.append)
        n7 = nasm_build(tree, [os.path.relpath(p, ROOT) for p in ship], os.path.join(w7, "art"), path=p0)
        ok(any("v0r," in s_ for s_ in said) and n7 is not None and rb(n7) == rb(o7),
           "no added course, FIRST on a ninth pad too: composed from v0r, the nasm build of the shipped list and "
           "that pathway with BZHEADROOM=1 byte for byte (%d bytes)" % os.path.getsize(o7))
    finally:
        shutil.rmtree(tree, ignore_errors=True)

    # 4. refusals
    inc = open(os.path.join(G.BIN, "v1", "bzcourse.inc")).read()
    big = inc.replace("BZ_PROPMAX      equ 50", "BZ_PROPMAX      equ 52", 1)
    many = G.NPAD_RE.sub(lambda m: m.group(1) + "24", inc, 1)
    try:
        G.compare(inc, many, npads=range(1, 24))
        ok(False, "a pathway of 24 pads is refused")
    except G.Refused as e:
        ok("BZ_PAD_MAX" in str(e), "a pathway of 24 pads is refused naming BZ_PAD_MAX")
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
