#!/usr/bin/env python3
"""t_bbedit - the course builder's model and the compiler's warning tier
(SPEC.md 130.58.3 - 130.58.5), on the host, no emulator:

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
    picture gets the narrowest `width` and `origin` that hold it (80 and 224, the compiler's own
    minimum), and one past 160 columns is left refused (auto_band);
 6. REJOIN: the ramp made floor again rejoins into the one rectangle (tidy), as one undo step (group),
    and a route point is the last thing a click at its cell reaches;
 7. DIAGONALS: PLAY's split cells report their pieces and a click picks the piece under it; a boost pad,
    magnet or membrane wholly behind a wall builds, with a warning;
 9. SHAPES (130.58.19): every chute, pit and hump of the shipped courses reads and writes back as it was
    (bbedshape.parse / code); on a constructed plate a chute made from nothing, dragged by an end and a
    corner, given a left turn and run the other way still compiles, a pit and a ridge too - and the ride
    readout (bbedjob.rides, the game's Physics) takes each ball through the steered chute and over the
    ridge at full speed.
 8. GAP BANDS (130.58.21): a ledge's faces over the lower floor are the detector's candidates; marking two
    neighbours folds them into one `gap rect`, unmarking one of a statement's faces rewrites it to the rest
    (and drops a piece that would band nothing), unmarking the last deletes the line - and the compiler's
    `marked` agrees after every step.

Red arms, by hand: drop the `half`/`quarter` skip from bbedproj.coord_slots
(item 2 goes red on DOWN), make bbcourse._visual raise again (item 3), or
make toggle_gap's `codes` keep the pieces no face is in (item 8: "gap bands
nothing").
"""

import glob
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B  # noqa: E402
import bbedproj as E  # noqa: E402
import bbedshape as S  # noqa: E402
import bbedjob as J  # noqa: E402

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
    # 5. THE GROUND AS ONE LAYER (SPEC.md 130.58.13): a ramp cut into the middle of a floor leaves every
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
    # the narrowest picture that holds it: 80 columns, origin 224 - and the compiler agrees, refusing 72
    # (MEASURED: SPEC.md 130.58.13)
    if did is None or d.analysis()["error"] or "width 80" not in d.lines or "origin 224" not in d.lines:
        bad.append("auto_band: %r, %r, %r" % (did, d.analysis()["error"], [l for l in d.lines if l[:5] in
                                                                         ("width", "origi")]))
    d = E.Document(base)
    d.insert("floor rect 15 4 80 12 flat 4")
    did = d.auto_band()
    if did is not None or not d.analysis()["error"]:
        bad.append("auto_band: a course past 160 columns was 'fixed': %r" % did)
    # 6. REJOIN (SPEC.md 130.58.14): a ramp cut into the floor and made floor again rejoins into the one
    # rectangle it was, every cell as it was; a group of edits is one undo; a route point is under the ground
    d = E.Document(base)
    with d.group("ramp and back"):
        d.replace_area((7, 6, 9, 8), ["floor rect 7 6 10 9 ramp x 7 10 4 5.5"])
        d.replace_area((7, 6, 9, 8), ["floor rect 7 6 10 9 flat 4"])
        d.tidy((7, 6, 9, 8))
    floors = [l_ for l_ in d.lines if l_.startswith("floor")]
    if floors != ["floor rect 4 4 14 12 flat 4"] or len(d.undo_stack) != 1:
        bad.append("tidy: %r, %d undo steps" % (floors, len(d.undo_stack)))
    an = d.analysis()
    if E.at_cell(an, (5, 5))[-1] != [st.line for st in d.statements() if st.code == "way 5 5"][0]:
        bad.append("at_cell: the route point is not last at (5, 5): %r" % E.at_cell(an, (5, 5)))
    # 7. DIAGONALS (SPEC.md 130.58.15): a split cell's pieces are reported and picked by the point; a WHOLLY
    # hidden boost pad, magnet and membrane build with a warning (refused only under --strict)
    an = E.Document.load(os.path.join(ROOT, "apps", "bonanza", "courses", "playground.bbc")).analysis()
    sp = [c for c, d in an["cells"].items() if d.get("pieces")]
    if not sp:
        bad.append("diagonals: PLAY's split cells report no pieces")
    else:
        lanes = {E.at_cell(an, c, (0.15, 0.85))[0] != E.at_cell(an, c, (0.85, 0.15))[0] for c in sp}
        if True not in lanes:
            bad.append("diagonals: no split cell of PLAY picks a different piece at its two corners")
    for nm, (use, part) in (("boost pad", ("uses boost", "prop boost 6 5 face +x")),
                            ("magnet", ("uses magnet", "prop magnet 6 5 face -x range 4 strength 48")),
                            ("membrane", ("uses spike", "prop membrane 6 5 7 6"))):
        t = (FLAG % ("", "")).replace("checkpoint 6 5\n", "").replace("ball rubber", "ball rubber\n" + use) + part + "\n"
        try:
            c = B.compile_course(t, "hid.bbc")
            if not any(w["kind"] == "hidden" for w in c.warnings):
                bad.append("%s wholly hidden: built with no warning" % nm)
        except B.CourseError as e:
            bad.append("%s wholly hidden: refused (%s)" % (nm, str(e)[:100]))
    # 8. GAP BANDS (SPEC.md 130.58.21, 130.57): mark, fold, split, unmark, as the compiler sees each step
    gt = ('course GAPT "Gap test"\nwidth 64\nball rubber\nfloor rect 3 3 9 9 flat 4\nfloor rect 3 10 9 14 flat 0\n'
          'floor rect 10 3 14 9 flat 0\nstart 4 4\ngoal rect 12 4 13 5 flat 0\ntarget 30\nway 4 4\nway 12 4\n')
    d = E.Document(gt)

    def marked():
        B.GAP_DETECT = True
        try:
            gf = B.compile_course(d.text(), "gapt.bbc", occluders=False).gap_faces
        except B.CourseError as e:
            return str(e)[:100], []
        finally:
            B.GAP_DETECT = False
        return {(tuple(g["cell"]), g["side"]) for g in gf if g["marked"]}, gf
    _, gf = marked()
    F = [(g["cell"], g["side"]) for g in gf]
    gaps = lambda: [l_ for l_ in d.lines if l_.startswith("gap")]   # noqa: E731
    steps = ((((8, 3), "se"), "marked", ["gap tile 8 3 se"]),
             (((8, 4), "se"), "marked", ["gap rect 8 3 9 5 se"]),
             (((3, 8), "sw"), "marked", ["gap rect 8 3 9 5 se", "gap tile 3 8 sw"]),
             (((8, 3), "se"), "unmarked", ["gap tile 8 4 se", "gap tile 3 8 sw"]),
             (((8, 4), "se"), "unmarked", ["gap tile 3 8 sw"]))
    want = set()
    if len(F) != 10:
        bad.append("gap: the ledge has %d candidate faces, wanted 10" % len(F))
    for face, r_want, lines in steps:
        r = d.toggle_gap(face[0], face[1], F)
        want ^= {face}
        got, _ = marked()
        if r != r_want or gaps() != lines or got != want:
            bad.append("gap %r %s: %s, lines %r, compiler %r" % (face, r_want, r, gaps(), got))
    d = E.Document(gt.replace("start 4 4", "gap rect 3 8 9 9\nstart 4 4"))    # both sides named, sw only real
    d.toggle_gap((3, 8), "sw", F)
    d.toggle_gap((4, 8), "sw", F)                # (4, 8)'s se, a face of nothing, is dropped with it
    got, _ = marked()
    if gaps() != ["gap rect 5 8 9 9"] or got != {((x, 8), "sw") for x in range(5, 8)}:
        bad.append("gap: a both-sides rect unmarked at its ends is %r (compiler %r)" % (gaps(), got))
    for f_ in [(x, 8) for x in range(5, 8)]:
        d.toggle_gap(f_, "sw", F)
    if gaps() or len(d.undo_stack) != 5:
        bad.append("gap: every mark taken off leaves %r, %d undo steps" % (gaps(), len(d.undo_stack)))
    # 9. SHAPES (SPEC.md 130.58.19)
    for f in courses:
        for st in E.Document.load(f).statements():
            if st.kind in ("chute", "pit", "hump"):
                sh = S.parse(st.toks)
                if not sh or S.parse(E.tokens(S.code(sh))) != sh:
                    bad.append("shapes: %s:%d reads back as %r" % (os.path.basename(f), st.line,
                                                                  sh and S.code(sh)))
    plate = ('course SHP "Shapes"\nwidth 96\nball rubber\nfloor rect 4 4 24 20 flat 2\nstart 5 5\n'
             'goal rect 22 18 24 20 flat 2\ntarget 60\nway 5 5\nway 23 19\n')
    d = E.Document(plate)
    d.auto_band()                                   # (the window's own fix: the picture's width and origin)
    plate = d.text()
    ch = S.new_shape("chute", 8, 15, 2.0)
    steps = [("made", ch)]
    ch = dict(ch, ways=S.drag_way(ch["ways"], 1, 16, 15))
    steps.append(("an end dragged", ch))
    ch = dict(ch, ways=S.add_leg(ch["ways"], "left"))
    steps.append(("a left turn added", ch))
    ch = dict(ch, ways=S.drag_way(ch["ways"], 1, 17, 14))
    steps.append(("a corner dragged", ch))
    steps.append(("run the other way", dict(ch, ways=S.reverse(ch["ways"]))))
    if ch["ways"] != [[8, 14, 2.0], [17, 14, None], [17, 11, None]]:
        bad.append("shapes: the dragged chute's ways are %r" % ch["ways"])
    hump = dict(S.new_shape("hump", 16, 6, 2.0), along="x", n=3)
    steps += [("a pit", S.new_shape("pit", 6, 6, 2.0)), ("a ridge", hump)]
    held = B.BLK_MAX
    B.BLK_MAX = 1 << 30
    try:
        for what, sh in steps:
            try:
                c = B.compile_course(plate + S.code(sh) + "\n", "shp.bbc", occluders=False)
            except B.CourseError as e:
                bad.append("shapes: %s (%s) refused: %s" % (what, S.code(sh), str(e)[:120]))
                continue
            if what == "a left turn added":
                r = J.rides(c, S.code(sh).split())
                if not r or not all(x["result"] == "through" for x in r if x["test"] == "steered along it"):
                    bad.append("shapes: the steered chute: %r" % [x["words"] for x in r])
            if what == "a ridge":
                r = J.rides(c, S.code(sh).split())
                if not all(x["result"] == "through" for x in r if x["test"] == "at full speed"):
                    bad.append("shapes: the ridge at full speed: %r" % [x["words"] for x in r])
    finally:
        B.BLK_MAX = held
    for b_ in bad:
        print("FAIL " + b_)
    print("t_bbedit: %d courses, %s" % (len(courses), "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
