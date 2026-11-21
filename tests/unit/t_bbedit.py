#!/usr/bin/env python3
"""t_bbedit - the course builder's model and the compiler's warning tier
(SPEC.md 130.55.3 - 130.55.5), on the host, no emulator:

 1. ROUND TRIP: every course under apps/bonanza/courses/ read and written by
    tools/bbedproj.py is byte-identical, and moving every statement that has
    a position and then undoing every move is byte-identical too;
 2. MOVE: every course moved one cell (+1, +1) lays the same cells at the
    same heights, one cell over - so coord_slots names every position each
    statement has (a `half` prefix, a ramp's span, water's ripple cell, ...);
 3. WARNINGS: a flag wholly behind a wall is a WARNING without --strict, a
    REFUSAL with it, no warning when it is `hidden`, an accepted one with
    `accept hidden X Y`, and a refusal in the plain build once the course
    says `strict`;
 4. USES: placing a family's element (a magnet) adds its `uses` line;
 5. ONE LAYER: a ramp cut into a floor moves no other cell and undoes in one step; a floor past the
    picture gets an `origin`, one far past it `width 128` (auto_band).

Red arms, by hand: drop the `half`/`quarter` skip from bbedproj.coord_slots
(item 2 goes red on DOWN), or make bbcourse._visual raise again (item 3).
"""

import glob
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B  # noqa: E402
import bbedproj as E  # noqa: E402

FLAG = """course HFLAG "Hidden flag"
width 64
ball rubber
floor rect 3 3 13 8 flat 4
wall rect 7 6 10 8 flat 20
start 4 4
checkpoint 6 5%s
goal rect 12 3 13 5 flat 4
clock 11 3
target 30
way 4 4
way 12 4
%s"""


def main():
    bad = []
    courses = sorted(glob.glob(os.path.join(ROOT, "apps", "bonanza", "courses", "*.bbc")))
    if not courses:
        bad.append("no courses found")
    for f in courses:
        nm = os.path.basename(f)
        with open(f, "r", encoding="ascii", newline="") as fh:
            text = fh.read()
        d = E.Document(text, f)
        if d.text() != text:
            bad.append("%s: read and written is not byte-identical" % nm)
            continue
        a = d.analysis()
        moved = 0
        for st in d.statements():
            if E.coord_slots(st.toks):
                d.move(st.line, 1, 1)
                moved += 1
        b = d.analysis()
        if a["cells"]:
            exp = {(x + 1, y + 1): v["h"] for (x, y), v in a["cells"].items()}
            got = {k: v["h"] for k, v in b["cells"].items()}
            if exp != got:
                bad.append("%s: moved (+1, +1), %d cells differ (%s)" % (
                    nm, len(set(exp.items()) ^ set(got.items())), (b["error"] or "")[:100]))
        while d.undo():
            pass
        if d.text() != text:
            bad.append("%s: %d moves undone are not byte-identical" % (nm, moved))
    cases = (("", "", False, "warn"), ("", "", True, "refuse"), (" hidden", "", True, "none"),
             ("", "accept hidden 6 5", True, "accepted"), ("", "strict", False, "refuse"))
    for suf, extra, strict, want in cases:
        try:
            c = B.compile_course(FLAG % (suf, extra), "hflag.bbc", strict=strict)
            ws = [w for w in c.warnings if w["kind"] == "hidden"]
            got = "none" if not ws else "accepted" if all(w["accepted"] for w in ws) else "warn"
        except B.CourseError as e:
            got = "refuse" if "HIDDEN" in str(e) else "error: %s" % e
        if got != want:
            bad.append("hidden flag%s%s%s: %s, wanted %s" % (suf, " + " + extra if extra else "",
                                                             " --strict" if strict else "", got, want))
    d = E.Document(FLAG % ("", ""))
    d.insert("prop magnet 4 7 face +x range 4 strength 48")
    if d.auto_uses() != ["magnet"] or not any(s.kind == "uses" and "magnet" in s.toks for s in d.statements()):
        bad.append("placing a magnet did not add `uses magnet`")
    # 5. THE GROUND AS ONE LAYER (SPEC.md 130.55.13): a ramp cut into the middle of a floor leaves every
    # other cell where it was, the ramp's cells on its plane, and one undo; and the picture's band fixed
    base = ('course NEW "New course"\nwidth 64\nball rubber\n\nfloor rect 4 4 14 12 flat 4\nstart 5 5\n'
            'goal rect 12 10 14 12 flat 4\ntarget 30\nway 5 5\nway 13 11\n')
    d = E.Document(base)
    a0 = d.analysis()["cells"]
    d.replace_area((7, 6, 9, 8), ["floor rect 7 6 10 9 ramp x 7 10 4 5.5"])
    a1 = d.analysis()
    moved = [c for c in a0 if not (7 <= c[0] <= 9 and 6 <= c[1] <= 8) and a1["cells"].get(c, {}).get("h") != a0[c]["h"]]
    ramp = [a1["cells"][(x, 7)]["h"] for x in (7, 8, 9)]
    if a1["error"] or moved or ramp != [4.25, 4.75, 5.25] or len(d.undo_stack) != 1:
        bad.append("replace_area: error %r, %d cells moved, ramp %r, %d undo steps" % (
            a1["error"], len(moved), ramp, len(d.undo_stack)))
    d.undo()
    if d.text() != base:
        bad.append("replace_area: undone is not the text it was")
    d = E.Document(base)
    d.insert("floor rect 15 4 24 12 flat 4")
    did = d.auto_band()
    if not did or d.analysis()["error"] or not any(l.startswith("origin ") for l in d.lines):
        bad.append("auto_band: %r, %r" % (did, d.analysis()["error"]))
    d = E.Document(base)
    d.insert("floor rect 15 4 40 12 flat 4")
    did = d.auto_band()
    if not did or "width 128" not in d.lines or d.analysis()["error"]:
        bad.append("auto_band wide: %r, %r" % (did, d.analysis()["error"]))
    for b_ in bad:
        print("FAIL " + b_)
    print("t_bbedit: %d courses, %s" % (len(courses), "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
