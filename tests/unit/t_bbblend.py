#!/usr/bin/env python3
"""t_bbblend - THE BLEND CHECK (SPEC.md 130.56.6, 130.56.18), on the host, no emulator:

 1. BLEND: a lower floor behind a higher one, four units down, so that its
    cell checker runs on above the higher floor's back edge, WARNS (kind
    `blend`, both floors' cells and lines, the seam's pixels, over BLEND_PX);
 2. NOT A BLEND: the same two floors ADJOINED (one height: one floor), and the
    same two with the drop two units (130.47.2's height phase turns the
    checker over, so two cells of one colour meet along the seam) - no blend;
 3. STRICT: the blending course is REFUSED under --strict, and a course that
    says `strict`;
 4. ACCEPT: `accept blend` and `accept blend X Y` (a cell of EITHER floor)
    let it build under --strict, the warning reported as accepted; a cell of
    neither does not;
 5. SHIPPED: every course in BZ_COURSES, the pathway and the title raises the
    blend warnings 130.56.18 records (SHIPPED below: PLAYGROUND's and the
    title's) - each compile the compile cache's when it has one, else a
    core each.

Red arms, by hand (`--quick` skips item 5 for them): make bbcourse.blend_check
return at once (items 1, 3 and 4 go red); make blend_pairs compare only where
the outline is, not the cells' colours (item 2 goes red on the 2-unit drop).
"""

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B  # noqa: E402

COURSE = """course BLEND "Blend"
width 64
floor rect 4 10 13 14 flat 4
floor rect 4 5 13 10 flat %s
goal  rect 12 10 13 14 flat 4
start 5 12
%s"""

# SPEC.md 130.56.18: what the shipped courses raise (the record; a change here is a finding to report)
SHIPPED = {"playground.bbc": [((26, 31), 101)],        # floor -8 (line 77) seen on past floor 0 (line 313)
           "title.bbc": [((10, 13), 59)]}               # floor 3 (line 60) behind the half-unit step to 3.5


def blends(c):
    return [w for w in c.warnings if w["kind"] == "blend"]


def shipped_paths():
    with open(os.path.join(ROOT, "Makefile")) as f:
        mk = f.read()
    m = re.search(r"^BZ_COURSES\s*:?=\s*((?:.*\\\n)*.*)$", mk, re.M)
    names = re.findall(r"[\w/.$()-]+\.bbc", m.group(1)) if m else []
    out = []
    for n in names:
        n = n.replace("$(BZDIR)", "apps/bonanza").replace("$(BZCRS)", "apps/bonanza/courses")
        if "$(" in n:
            continue
        out.append(n)
    return out + ["apps/bonanza/courses/path.bbc", "apps/bonanza/courses/title.bbc"]


def main():
    bad = []
    # 1. the blending pair
    c = B.compile_course(COURSE % ("0", ""), "blend.bbc", strict=False)
    w = blends(c)
    if len(w) != 1:
        bad.append("1: the floor 4 units behind and below: %d blend warnings, want 1" % len(w))
    else:
        w = w[0]
        if w["px"] <= B.BLEND_PX or len(w["seam"]) != w["px"] or sorted(w["lines"]) != [3, 4]:
            bad.append("1: the warning's seam %d px (over %d), lines %s (want 3 and 4)" % (
                w["px"], B.BLEND_PX, w["lines"]))
        if (9, 10) not in w["cells"] or (7, 7) not in w["cells"] or w["accepted"]:
            bad.append("1: the warning's cells miss a floor, or it is accepted: %s" % w["msg"])
        print("  1. %s" % w["msg"])
    # 2. adjoined (one height), and the 2-unit drop's turned checker
    for h, why in (("4", "adjoined"), ("2", "a 2-unit drop (the checker turned)")):
        c = B.compile_course(COURSE % (h, ""), "blend.bbc", strict=False)
        if blends(c):
            bad.append("2: %s raised %s" % (why, blends(c)[0]["msg"]))
        else:
            print("  2. %s: no blend (pairs under the threshold: %s)" % (
                why, [len(p["seam"]) for p in B.blend_pairs(c)][:4]))
    # 3. strict
    for extra, strict, why in (("", True, "--strict"), ("strict", False, "the course's `strict`")):
        try:
            B.compile_course(COURSE % ("0", extra), "blend.bbc", strict=strict)
            bad.append("3: not refused under %s" % why)
        except B.CourseError as e:
            if "blend warning" not in str(e):
                bad.append("3: refused under %s, but not for the blend: %s" % (why, e))
            else:
                print("  3. refused under %s" % why)
    # 4. accept
    for extra, ok in (("accept blend", True), ("accept blend 9 10", True), ("accept blend 7 7", True),
                      ("accept blend 20 20", False)):
        try:
            c = B.compile_course(COURSE % ("0", extra), "blend.bbc", strict=True)
            if not ok:
                bad.append("4: `%s` (a cell of neither floor) let it build" % extra)
            elif not (blends(c) and all(x["accepted"] for x in blends(c))):
                bad.append("4: `%s` built without an accepted blend warning" % extra)
            else:
                print("  4. `%s`: builds under --strict, accepted" % extra)
        except B.CourseError as e:
            if ok:
                bad.append("4: `%s` still refused: %s" % (extra, e))
            else:
                print("  4. `%s`: still refused" % extra)
    # 5. the shipped courses (--quick: not, for a red arm by hand)
    paths = [] if "--quick" in sys.argv else shipped_paths()
    if len(paths) < 3 and "--quick" not in sys.argv:
        bad.append("5: BZ_COURSES not read out of the Makefile (%s)" % paths)
    got_all = B.par_map(B.compile_course, [os.path.join(ROOT, p) for p in paths])   # (forked, a core each)
    for p, (c, e) in zip(paths, got_all):
        if e is not None:
            bad.append("5: %s refused: %s" % (p, e))
            continue
        got = sorted((x["cell"], x["px"]) for x in blends(c))
        want = SHIPPED.get(os.path.basename(p), [])
        print("  5. %s: %s" % (os.path.basename(p), got or "no blend"))
        if [g[0] for g in got] != [tuple(x[0]) for x in want]:
            bad.append("5: %s raises %s, SPEC.md 130.56.18 records %s" % (p, got, want))
    for b in bad:
        print("FAIL", b)
    print("t_bbblend: %s" % ("FAIL" if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
