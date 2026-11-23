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
 10. THE MAP (130.58.20): every pad, route, icon and lives statement of the shipped pathway reads and writes
    back to the same meaning (bbedmap.parse_map / *_code); a route step bridged is legal; pad 1 dragged a cell
    takes its routes with it and the map compiles; a pad dropped on another's cell is refused; a course of
    the author's (`# builder-course:`) put on the map from pad 7, one of the two pads whose course has an exit free,
    at (8, 7) - pad, route, icon - compiles.
 11. EDITS KEEP THE ROUTE (130.58.22): a floor cut back from under two route points leaves them moved to the
    nearest floor (relocate_ways), folded into the edit's one undo step (merge_since), and the course lays out;
    a ramp reshaped longer keeps its slope (reshape: 4 to 9 over 10 cells at half a unit a cell); ways_in
    finds the start, the flag and the route points on a floor.
 12. THE GAME'S RULES IN THE FULL CHECK (130.58.23): a course with no `music` compiles and is refused by the
    check job naming the song; the builder's New course template passes it; with TRAP_CHECK off (the builder's
    default, 130.58.24) a 3-cell gap a jump pickup carries glass over compiles.
 13. TUBES (130.58.26, 130.12.3.3): a KEEP tube made from nothing on a plain floor, an end dragged, a right
    turn added and made a DROP compiles, the tube laying its own body along both legs.
    13d (130.12.3.5, 130.58.39): a pipe's height a leg - set_leg_height writes `body 6 4`, read back the same,
    kept through a point added and a corner axis_path inserts, each leg's walls laid at its height - and a
    `column 1` over a gap floating the body one unit deep, one over floor refused (`column hangs nothing`).
    13e (130.12.3.6, 130.58.40): `body 5 column 1` over the floor a pipe the ball passes under - its cells the
    floor with the slab over it, each an archway element, `uses archway` added by the builder - and `body 4.5`
    (1.5 units of room) refused.
    13f (130.12.3.7): a tube's `top` (the Walkable top) read and written by the shape editor, `uses archway` added
    by the builder, its passable cells archway elements with a TOP and its walls walkable ones; none without it.
 14. DRAFTS AND TRACES (130.58.27): a drafted path made axis-legged (a corner where two points differ along both
    axes, a point mid-run dropped), a Ctrl-click past the end a new end, and a tube traced through three cells
    compiles with its body laid.
 8. GAP BANDS (130.58.21): (and a mark an edit left with nothing to band is dropped by the picture job,
    which draws the picture rather than refusing it) a ledge's faces over the lower floor are the detector's candidates; marking two
    neighbours folds them into one `gap rect`, unmarking one of a statement's faces rewrites it to the rest
    (and drops a piece that would band nothing), unmarking the last deletes the line - and the compiler's
    `marked` agrees after every step.

 16. THE OCCLUDER VIEW (130.58.32): on FLAG's floor a record the wall cuts hides a floor cell behind it, named by
    bbedjob.occ_data (owner, the cells it hides, its cells flagged); set_noocclude over every cell it hides
    and the compiler cuts it no more; taken out, the course is the text it was; the start is refused.

 18. WHAT ONLY MADE SENSE ON THE GROUND, AND ERRORS BY IDENTITY (130.58.38): MILL's deadlock - a float left on
    deleted ground and a launch tube landing off a floor, both already there - the float deletes even with the
    shape editor's Try it on the tube pending (its picture killed), the picture then refusing on the tube's
    landing; the tube deletes with the float still refused; an edit renumbering the float is kept, one adding
    a NEW error is not; a floor deleted takes its exact float and paint in one undo step; paint_in finds a
    floor's inner paint; FIXES offers "Remove this overhang" and it clears the refusal; the Source tab's Apply
    is one undo step and is kept with an error.

 17. EVERY OPTION HAS A CONTROL (130.58.37): every clause of tools/bbedopts.py's GRAMMAR list (the audit,
    docs/plans/BONANZA-BUILDER-OPTIONS.md) has its row in OPTIONS and every row is in GRAMMAR; on a statement
    with every clause written (FULL) each row reads its value, and cleared then set back to it the statement
    is legal again with the same value - so a clause the grammar wants in one place goes back there (the
    see-saw's `rest` after its pivot, a clock's `frame` before `digits`, water's `open` before `ripple`); on
    the bare statement each row's default writes a legal clause and clearing it gives the bare statement back.

Red arms, by hand: drop the `half`/`quarter` skip from bbedproj.coord_slots
(item 2 goes red on DOWN), make bbcourse._visual raise again (item 3), or
make toggle_gap's `codes` keep the pieces no face is in (item 8: "gap bands
nothing"), make occ_data add no cell to a record's `needs` (item 16: "no record
of the wall hides a cell behind it"), or cut with `rcut = reach` in
compile_course (item 16: "noocclude ... left record(s)"); delete crack's `hole` row from bbedopts.OPTIONS
(item 17: "no row for prop crack's hole"), or give the see-saw's `rest` row `at=None` (item 17: "rest ...
not legal again"); for item 18, drop the `text != tried` test from bbedshape.picture_refused ("undid the float's
delete") or make bbedit.App._edit compare `after != before` again ("an edit above the float was refused").
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
import bbedmap as M  # noqa: E402
import bbedopts as OPT  # noqa: E402
import bbedit as W  # noqa: E402
import tempfile  # noqa: E402

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

# item 17: each statement kind bbedopts answers for, bare and with every clause it may take written (one form)
OPT_BARE = {
    ("goal", None): "goal rect 4 4 6 6 flat 2", ("water", None): "water rect 4 4 6 6 top 4 bed 0",
    ("arch", None): "arch 4 4 +x", ("float", None): "float rect 4 4 6 6", ("gap", None): "gap rect 4 4 6 6",
    ("guard", None): "guard rect 4 4 8 8", ("seesaw", None): "seesaw 4 4 6 5 along x pivot 3",
    ("archway", None): "archway rect 4 4 6 5 along x", ("cup", None): "cup 4 4",
    ("checkpoint", None): "checkpoint 4 4", ("clock", None): "clock 4 4", ("spring", None): "spring 4 4 768",
    ("pad", None): "pad rubber 4 4", ("label", None): 'label 1 2 3 glyphs "HI"', ("way", None): "way 4 4",
    ("prop", "windmill"): "prop windmill 4 4", ("prop", "bumper"): "prop bumper 4 4",
    ("prop", "platform"): "prop platform 4 4 4", ("prop", "turntable"): "prop turntable 4 4 size 2 fill oo/..",
    ("prop", "bridge"): "prop bridge 4 4 6 6 channel ring", ("prop", "boost"): "prop boost 4 4 face +x",
    ("prop", "magnet"): "prop magnet 4 4 face -x", ("prop", "blower"): "prop blower 4 4 face +y region 4 5 6 7",
    ("prop", "popspikes"): "prop popspikes 4 4 period 128 on 64", ("prop", "crack"): "prop crack 4 4",
    ("prop", "gate"): "prop gate 4 4 channel ring", ("prop", "plate"): "prop plate 4 4 channel ring",
    ("prop", "key"): "prop key 4 4 channel ring", ("prop", "speed"): "prop speed 4 4",
    ("prop", "jump"): "prop jump 4 4", ("prop", "life"): "prop life 4 4"}
OPT_FULL = {
    ("goal", None): "goal rect 4 4 6 6 flat 2 exit 1 hidden",
    ("water", None): "water rect 4 4 6 6 top 4 bed 0 open ripple 4 4",
    ("arch", None): "arch 4 4 +y guard height 2.5", ("float", None): "float rect 4 4 6 6 thick 1",
    ("gap", None): "gap rect 4 4 6 6 sw", ("guard", None): "guard rect 4 4 8 8 side +x -y height 2.5",
    ("seesaw", None): "seesaw 4 4 6 5 along x pivot 3 rest + period 64 flat 6 seed 3",
    ("archway", None): "archway rect 4 4 6 5 along y under 3 top",
    ("cup", None): "cup 4 4 capture 200 exit 1 hidden", ("checkpoint", None): "checkpoint 4 4 ball steel",
    ("clock", None): "clock 4 4 frame pin digits 1 2", ("spring", None): "spring 4 4 500",
    ("pad", None): "pad steel 4 4", ("label", None): 'label 1 2 3 glyphs "HI" ink 2',
    ("way", None): "way 4 4 branch AB",
    ("prop", "windmill"): "prop windmill 4 4 period 32 closed 12 20 seed 5",
    ("prop", "bumper"): "prop bumper 4 4 kick 200",
    ("prop", "platform"): "prop platform 4 4 3 period 64 dwell 4 seed 3",
    ("prop", "turntable"): "prop turntable 4 4 size 3 fill oo./.o./.oo quarter 32 turn ccw seed 9 warn 8",
    ("prop", "bridge"): ("prop bridge 4 4 6 6 period 64 on 20 seed 3 style picket",
                         "prop bridge 4 4 6 6 channel cross style grille"),
    ("prop", "boost"): "prop boost 4 4 face +y strength 30 flat",
    ("prop", "magnet"): ("prop magnet 4 4 face -x range 4 strength 48", "prop magnet 4 4 face down -x strength 9"),
    ("prop", "blower"): "prop blower 4 4 face up region 4 4 6 6 strength 9 top 4 lift gust 16 16 seed 3 flag",
    ("prop", "popspikes"): "prop popspikes 4 4 period 64 on 20 seed 3", ("prop", "crack"): "prop crack 4 4 hole wide",
    ("prop", "gate"): ("prop gate 4 4 channel plus along y style picket", "prop gate 4 4 channel plus art door"),
    ("prop", "plate"): "prop plate 4 4 channel box",
    ("prop", "key"): "prop key 4 4 channel box", ("prop", "speed"): "prop speed 4 4 for 4 overwrite respawn",
    ("prop", "jump"): "prop jump 4 4 for 4 overwrite respawn", ("prop", "life"): "prop life 4 4 once"}


def options_check():
    """item 17 (SPEC.md 130.58.37): every option the grammar has, a row; each row round-trips -> [problems]"""
    bad = []
    for key, ids in OPT.GRAMMAR.items():
        have = [OPT.option_id(o) for o in OPT.OPTIONS.get(key, [])]
        bad += ["options: no row for %s's %s" % (" ".join(k for k in key if k), w) for w in ids if w not in have]
    for key, rows in OPT.OPTIONS.items():
        bad += ["options: %s's row %s is not in GRAMMAR" % (key, OPT.option_id(o)) for o in rows
                if OPT.option_id(o) not in OPT.GRAMMAR.get(key, ())]
        if key not in OPT_FULL or key not in OPT_BARE:
            bad.append("options: no sample statement for %r" % (key,))
            continue
        fulls = OPT_FULL[key] if isinstance(OPT_FULL[key], tuple) else (OPT_FULL[key],)
        bare = E.tokens(OPT_BARE[key])
        for t in [E.tokens(f_) for f_ in fulls] + [bare]:
            if OPT.statement_error(E.join_tokens(t)):
                bad.append("options: the sample %r is refused: %s" % (E.join_tokens(t),
                                                                     OPT.statement_error(E.join_tokens(t))))
        read = set()
        for full in [E.tokens(f_) for f_ in fulls]:
            for o in OPT.options_for(full):
                oid, v = OPT.option_id(o), OPT.value(full, o)
                if v in (None, False, set()) and o["t"] != "mode":
                    continue
                read.add(oid)
                if o["req"] or o["t"] == "mode" or o["w"] is None and o["t"] != "bare":
                    continue
                blank = {"flag": False, "sides": set()}.get(o["t"], "")
                back = OPT.apply(OPT.apply(full, o, blank), o, v)
                err = OPT.statement_error(E.join_tokens(back))
                if err or OPT.value(back, o) != v:
                    bad.append("options: %s's %s cleared and set back to %r: %r, not legal again (%s)" % (
                        key, oid, v, E.join_tokens(back), err))
        bad += ["options: %s's %s reads no value from any of %r" % (key, OPT.option_id(o), fulls) for o in rows
                if OPT.option_id(o) not in read and not (o["t"] == "choice" and not o["vals"])]
        for o in OPT.options_for(bare):
            oid = OPT.option_id(o)
            if o["t"] == "mode":
                vals = [m[0] for m in o["modes"]]
            elif o["req"]:
                continue
            else:
                vals = [True if o["t"] == "flag" else {"+x", "-y"} if o["t"] == "sides" else o["vals"][0]
                        if o["t"] == "bare" else o["vals"][-1] if o["t"] == "choice" else o["d"]]
            for v in vals:
                t2 = OPT.apply(bare, o, v)
                err = OPT.statement_error(E.join_tokens(t2))
                if err:
                    bad.append("options: %s's %s set to %r: %r refused (%s)" % (key, oid, v, E.join_tokens(t2),
                                                                               err[:120]))
                elif o["t"] != "mode" and OPT.apply(t2, o, {"flag": False, "sides": set()}.get(o["t"], "")) != bare:
                    bad.append("options: %s's %s set and cleared is not the bare %r" % (key, oid, OPT_BARE[key]))
    return bad


class _StubApp(object):
    """the window's checked edit (bbedit.App._edit, delete, do_fix's FIXES) and what the shape editor calls, with
    no Tk - for item 18"""
    _edit = W.App._edit
    delete = W.App.delete

    def __init__(self, text):
        self.doc = E.Document(text, "d.bbc")
        self.sel, self.sels, self.keep, self._note, self.pic_err = None, [], None, "", None
        self.banner, self.msgs = None, []

    def _msg(self, t):
        self.msgs.append(t)

    def _banner(self, t, keep=False):
        self.banner = t

    def select(self, ln, **kw):
        self.sel = ln

    def _fill_inspector(self):
        pass

    def _redraw(self):
        pass


def _full_error(text):
    held, B.BLK_MAX = B.BLK_MAX, 1 << 30
    try:
        B.compile_course(text, "d.bbc", occluders=False)
        return None
    except B.CourseError as e:
        return str(e)
    finally:
        B.BLK_MAX = held


def stranded_check():
    """item 18 (SPEC.md 130.58.38)"""
    bad = []
    base = B._W3W
    land = "wall tile 7 13 flat 17\nfloor tile 7 14 flat 16\ntube launch 7 12 7 14 speed 0 384 300\n"
    flt = "float rect 30 30 32 31 thick 0.5\n"
    two = base + land + flt                         # MILL's deadlock: a float on deleted ground, and a launch
    nl = base.count("\n")                           # tube landing off a floor, both already there
    tube_ln, float_ln = nl + 3, nl + 4
    if "floats nothing" not in (E.analyse(two, "d.bbc")["error"] or ""):
        bad.append("stranded: the cheap check does not see the float that floats nothing")
    # (1) the shape editor's Try it on the tube, its picture killed by the next edit; then the float deleted;
    # the picture of THAT text refuses on the tube's landing - which must not undo the delete
    app = _StubApp(two)
    app.pic_err = (two, _full_error(two))
    se = S.ShapeEditor(app, None, None, None, None)
    se.line = tube_ln
    se.draft = S.parse("tube launch 7 12 7 14 speed 0 380 300".split())
    se.try_draft()
    app.sel = float_ln
    app.delete()
    if flt.strip() in app.doc.lines:
        bad.append("stranded: deleting the stranded float was refused: %s" % app.banner)
    err = _full_error(app.doc.text())
    se.picture_refused(err, app.doc.text())
    if flt.strip() in app.doc.lines:
        bad.append("stranded: the tube's landing (%s) undid the float's delete" % (err or "")[:80])
    # (2) the tube deleted while the float floats nothing: kept
    app = _StubApp(two)
    app.sel = tube_ln
    app.delete()
    if any(l_.startswith("tube launch") for l_ in app.doc.lines):
        bad.append("stranded: deleting the tube was refused by the float: %s" % app.banner)
    # (3) an unrelated edit that renumbers the float's line: kept (the error is the same error)
    app = _StubApp(two)
    fc = min(c for c, d_ in app.doc.analysis()["cells"].items() if d_["kind"] == "floor")
    paint = "surface sand tile %d %d" % fc
    app._edit(app.doc.insert, paint, after=nl)
    if paint not in app.doc.lines:
        bad.append("stranded: an edit above the float was refused: %s" % app.banner)
    # (4) a NEW error is still refused: a statement the parser refuses
    app = _StubApp(two)
    app._edit(app.doc.insert, "floor rect 1 1", after=nl)
    if "floor rect 1 1" in app.doc.lines:
        bad.append("stranded: an edit adding a new error was kept")
    # (5) a floor deleted takes its float and its paint (one undo step); undone, all three are back
    own = "floor rect 30 30 32 32 flat 4\nfloat rect 30 30 32 32 thick 0.5\nsurface sand rect 30 30 32 32\n"
    app = _StubApp(base + own)
    if app.doc.analysis()["error"]:
        bad.append("stranded: the floor with its float refused: %s" % app.doc.analysis()["error"])
    n0 = len(app.doc.undo_stack)
    app.sel = nl + 1
    app.delete()
    left = [l_ for l_ in app.doc.lines if "30 30 32" in l_]
    if left or app.doc.analysis()["error"] or len(app.doc.undo_stack) != n0 + 1:
        bad.append("stranded: a floor deleted left %r (%s), %d undo steps" % (
            left, app.doc.analysis()["error"], len(app.doc.undo_stack) - n0))
    app.doc.undo()
    if app.doc.text() != base + own:
        bad.append("stranded: the floor's delete undone is not the text it was")
    # (6) a moved floor's paint inside it rides: paint_in finds the sub-rect paint, not the paint outside
    d = E.Document(base + own + "surface ice tile 31 31\nsurface ice tile 40 40\n")
    if [d.statement(l_).code for l_ in d.paint_in((30, 30, 32, 32))] != [
            "float rect 30 30 32 32 thick 0.5", "surface sand rect 30 30 32 32", "surface ice tile 31 31"]:
        bad.append("stranded: paint_in %r" % [d.statement(l_).code for l_ in d.paint_in((30, 30, 32, 32))])
    # (7) the error row's fix: FIXES offers "Remove this overhang" and it clears the refusal
    app = _StubApp(base + flt)
    e0 = app.doc.analysis()["error"]
    fx = W.fix_for(e0, app.doc.analysis()["error_line"], app.doc)
    if not fx or "Remove" not in fx[0]:
        bad.append("stranded: no fix offered for %r" % e0)
    else:
        app._edit(fx[1], app.doc)
        if app.doc.analysis()["error"] or flt.strip() in app.doc.lines:
            bad.append("stranded: the fix left %s" % app.doc.analysis()["error"])
    if W.explain(e0) == e0 or "deleted" not in W.explain(e0):
        bad.append("stranded: the float's refusal is not explained")
    # (8) the Source tab's Apply: one undo step, never undone even when it adds an error
    app = _StubApp(base)
    t2 = base.replace("start ", "#start ", 1) if "start " in base else base + "way 60 60\n"
    app._edit(app.doc.set_text, t2, label="edit the source", _allow=True)
    if app.doc.text() != t2 or len(app.doc.undo_stack) != 1:
        bad.append("source apply: %d undo steps, text %s" % (len(app.doc.undo_stack),
                                                             "as typed" if app.doc.text() == t2 else "changed"))
    return bad


def main():
    bad = []
    bad += options_check()
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
    # ... and a mark an edit left banding nothing is dropped by the picture job, not a refused picture
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "g.bbc")
        with open(src, "w", encoding="ascii") as f:
            f.write(gt.replace("floor rect 3 3 9 9 flat 4", "floor rect 3 3 8 9 flat 4") + "gap tile 8 3 se\n")
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            rc = J.picture(src, os.path.join(td, "pic"))
        import json as _json
        meta = _json.load(open(os.path.join(td, "pic", "meta.json"))) if rc == 0 else {}
        if rc != 0 or meta.get("dropped_gaps") != [len(gt.split("\n"))]:
            bad.append("gap: a stale mark: picture rc %r, dropped %r" % (rc, meta.get("dropped_gaps")))
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
    # 10. THE MAP (SPEC.md 130.58.20)
    pp = os.path.join(ROOT, "apps", "bonanza", "courses", "path.bbc")
    d = E.Document.load(pp)
    m = M.parse_map(d.statements())
    for st in d.statements():
        code = {"pad": lambda: M.pad_code(m["pads"][int(st.toks[1])]),
                "route": lambda: M.route_code([r for r in m["routes"] if r["line"] == st.line][0]),
                "icon": lambda: M.icon_code(m["icons"][int(st.toks[1])]),
                "lives": lambda: M.lives_code([v for v in m["lives"] if v["line"] == st.line][0])}.get(st.kind)
        if code and M.parse_map([E.Statement(st.line, code())]) != M.parse_map([st]):
            bad.append("map: line %d reads back as %r" % (st.line, code()))
    if not all(M.legal(p, q) for p, q in zip(*(lambda t: (t, t[1:]))(M.tidy_points([[0, 0, 0], [5, 2, 0], [5, 9, 1]])))):
        bad.append("map: tidy_points left an illegal step: %r" % M.tidy_points([[0, 0, 0], [5, 2, 0], [5, 9, 1]]))

    def mapc(text, where):
        try:
            M.compile_map(text, where)
            return None
        except B.CourseError as e:
            return str(e)
    p1 = m["pads"][1]
    codes = {p1["line"]: M.pad_code(dict(p1, at=(25, 24)))}
    for r in m["routes"]:
        if 1 in (r["a"], r["b"]):
            pts = [list(q) for q in r["pts"]]
            pts[0 if r["a"] == 1 else -1][:2] = (25, 24)
            codes[r["line"]] = M.route_code(dict(r, pts=M.tidy_points(pts)))
    d.set_many(codes)
    if mapc(d.text(), pp):
        bad.append("map: pad 1 moved with its routes is refused: %s" % mapc(d.text(), pp))
    d.set_statement(p1["line"], M.pad_code(dict(p1, at=m["pads"][0]["at"])))
    if "share a cell" not in (mapc(d.text(), pp) or ""):
        bad.append("map: a pad on another's cell is not refused (%r)" % mapc(d.text(), pp))
    with tempfile.TemporaryDirectory() as td:
        xt = open(os.path.join(ROOT, "apps", "bonanza", "courses", "first.bbc"), encoding="ascii").read()
        with open(os.path.join(td, "xtra.bbc"), "w", encoding="ascii") as f:
            f.write(xt.replace('course FIRST "First Roll"', 'course XTRA "Extra Roll"'))
        tp = os.path.join(td, "path.bbc")
        d = E.Document(open(pp, encoding="ascii").read() + "# builder-course: xtra.bbc\n", tp)
        m = M.parse_map(d.statements())
        ends = [n for n in m["pads"] if M.free_exit(m, n, M.pad_exits(m, n, d.text(), tp)) is not None]
        if ends != [4, 7]:                      # (the map's two ends: every other pad's exits open a route)
            bad.append("map: the pads with an exit free are %r, not the two ends [4, 7]" % ends)
        for code in M.place_course(m, "XTRA", (8, 7), 7, ("icons/first32x24.bba", os.path.join(
                B.COURSE_DIR, "icons", "first32x24.bba")), exits=M.pad_exits(m, 7, d.text(), tp)):
            d.insert(code)
        if mapc(d.text(), tp) or 8 not in M.parse_map(d.statements())["pads"]:
            bad.append("map: XTRA put on the map at (8, 7) from pad 7 is refused: %s" % mapc(d.text(), tp))
    # 11. EDITS KEEP THE ROUTE (SPEC.md 130.58.22)
    wt = ('course WAYT "Way test"\nwidth 96\nball rubber\nfloor rect 4 4 12 10 flat 4\n'
          'floor rect 12 4 20 7 ramp x 12 20 4 8\nstart 5 5\ncheckpoint 6 8\ngoal rect 18 4 20 7 flat 8\ntarget 30\n'
          'way 5 5\nway 10 8\nway 11 5\nway 16 5\nway 19 5\n')
    d = E.Document(wt)
    n0 = len(d.undo_stack)
    fl = [st.line for st in d.statements() if st.code.startswith("floor rect 4 4")][0]
    d.set_statement(fl, "floor rect 4 4 10 10 flat 4")
    moved = d.relocate_ways()
    d.merge_since(n0)
    ways = [l_ for l_ in d.lines if l_.startswith("way")]
    if d.analysis()["error"] or len(moved) != 2 or len(d.undo_stack) != n0 + 1 or "way 10 8" in ways:
        bad.append("route kept: error %r, moved %r, %d undo steps, %r" % (d.analysis()["error"], moved,
                                                                         len(d.undo_stack) - n0, ways))
    rp = [st for st in E.Document(wt).statements() if "ramp" in st.toks][0]
    got = E.reshape(rp.toks, 1, 5, (12, 4, 22, 7))
    if got != "floor rect 12 4 22 7 ramp x 12 22 4 9":
        bad.append("reshape: a ramp made longer is %r" % got)
    kinds = sorted(c.split()[0] for _l, c in E.Document(wt).ways_in((4, 4, 12, 10), ("way", "start", "checkpoint")))
    if kinds != ["checkpoint", "start", "way", "way", "way"]:
        bad.append("ways_in: %r on the first floor" % kinds)
    # 12. THE GAME'S RULES IN THE FULL CHECK (SPEC.md 130.58.23)
    import io
    import contextlib
    nm = ('course NEW "New course"\nwidth 64\nball rubber\nmusic fairway\n\nfloor rect 4 4 14 12 flat 4\n'
          'start 5 5\ngoal rect 12 10 14 12 flat 4\nclock 13 9\ntarget 30\nway 5 5\nway 13 11\n')
    with tempfile.TemporaryDirectory() as td:
        for what, text, want in (("the template", nm, True), ("no music", nm.replace("music fairway\n", ""), False)):
            p_ = os.path.join(td, "n.bbc")
            with open(p_, "w", encoding="ascii") as f:
                f.write(text)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = J.check(p_, False)
            if (rc == 0) != want or (not want and "music" not in out.getvalue()):
                bad.append("full check, %s: rc %d, %s" % (what, rc, out.getvalue().strip().splitlines()[-1][:150]))
    # ... and NO TRAP only when asked (SPEC.md 130.58.24): a 3-cell gap a jump pickup carries glass over
    gap3 = ('course T12 "gap"\nmusic fairway\nwidth 128\nball rubber\nuses pickups\nfloor rect 4 8 10 14 flat 4\n'
            'floor rect 10 8 30 14 flat 4\nstart 5 10\ngoal rect 30 8 32 14 flat 4\nclock 4 8\ntarget 60\n'
            'way 5 10\nway 31 10\npad glass 6 12\nprop jump 12 10 for 3\nhole rect 18 8 21 14\n')
    got = []
    for on in (False, True):
        B.TRAP_CHECK = on
        try:
            B.compile_course(gap3, "gap3.bbc")
            got.append("compiles")
        except B.CourseError as e:
            got.append("NO TRAP" if "NO TRAP" in str(e) else str(e)[:80])
    B.TRAP_CHECK = True
    if got[0] != "compiles" or got[1] not in ("NO TRAP", "compiles"):
        bad.append("NO TRAP off / on: %r" % got)
    # 13. TUBES (SPEC.md 130.58.26): drawn over a plain floor, the tube lays its own body
    tt = ('course TUB "Tubes"\nwidth 96\nball rubber\nmusic fairway\nuses tube\nfloor rect 4 4 24 20 flat 2\n'
          'start 5 5\ngoal rect 22 18 24 20 flat 2\nclock 21 17\ntarget 60\nway 5 5\nway 23 19\n')
    tb = S.new_shape("tube", 8, 8, 2.0)
    tb = dict(tb, ways=S.drag_way(tb["ways"], 1, 14, 8))
    tb = dict(tb, ways=S.add_leg(tb["ways"], "right", 3))
    tb = dict(tb, sub="drop", height=2.0, out="+y")
    if S.code(tb) != "tube drop 8 8 14 11 via 14 8 out +y height 2" or S.parse(S.code(tb).split()) != tb:
        bad.append("tube: %r" % S.code(tb))
    B.BLK_MAX, held = 1 << 30, B.BLK_MAX
    try:
        dt = E.Document(tt + S.code(tb) + "\n")
        dt.auto_band()                          # (the window's own fix: the picture's width and origin)
        c = B.compile_course(dt.text(), "tub.bbc", occluders=False)
        body = sorted(k for k, v in c.tiles.items() if v.kind == B.KIND_WALL)
        if body != [(9, 8), (10, 8), (11, 8), (12, 8), (13, 8), (14, 8), (14, 9), (14, 10)]:
            bad.append("tube: its body is %r" % body)
    except B.CourseError as e:
        bad.append("tube: refused: %s" % str(e)[:150])
    finally:
        B.BLK_MAX = held
    tl = dict(S.new_shape("tube", 8, 8, 2.0), sub="launch", speed=[192, 0, 300], height=2.5)    # a RAISED
    if S.code(tl) != "tube launch 8 8 12 8 speed 192 0 300 height 2.5" or S.parse(S.code(tl).split()) != tl \
            or S.code(dict(tl, height=None)) != "tube launch 8 8 12 8 speed 192 0 300":       # launch (130.12.3.3)
        bad.append("launch tube: %r" % S.code(tl))
    # 13b. a tube's pipe height (`body`, SPEC.md 130.58.33): the author's, and a drop's automatic one the lowest
    B.BLK_MAX, held = 1 << 30, B.BLK_MAX
    try:
        for tl_, want in (("tube keep 8 8 14 8 body 6", 12), ("tube drop 8 8 14 8 out +x height 2", 4 + 4 + 3),
                          ("tube launch 8 8 14 8 speed 64 0 100 height 2", 4 + 4 + 3)):   # (a RAISED launch's, as a
                                                                                       # drop's: 130.12.3.3)
            dt = E.Document(tt + tl_ + "\n")
            dt.auto_band()
            c = B.compile_course(dt.text(), "tb.bbc", occluders=False)
            zs = sorted({v.z0 for k, v in c.tiles.items() if v.kind == B.KIND_WALL})
            if zs != [want]:
                bad.append("tube body: %s laid at %r half units, wanted %d" % (tl_, zs, want))
    except B.CourseError as e:
        bad.append("tube body: refused: %s" % str(e)[:150])
    finally:
        B.BLK_MAX = held
    # 13d. a pipe's height a LEG and its column's depth (SPEC.md 130.12.3.5, 130.58.39)
    tl = dict(S.new_shape("tube", 8, 8, 2.0), ways=[[8, 8, None], [14, 8, None], [14, 11, None]])
    tl = S.set_leg_height(dict(tl, body=6.0), 1, 4.0)
    want = "tube keep 8 8 14 11 via 14 8 body 6 4"
    if S.code(tl) != want or S.parse(want.split()) != tl or S.leg_heights(tl) != [6.0, 4.0]:
        bad.append("leg heights: %r %r" % (S.code(tl), S.leg_heights(tl)))
    tl2 = dict(tl, ways=S.insert_point(tl["ways"], (11, 8)))        # (a point on leg 1: both its halves keep 6)
    if S.leg_heights(tl2) != [6.0, 6.0, 4.0] or S.code(dict(tl2, ways=S.axis_path(tl2["ways"]))) != want:
        bad.append("leg heights through a point added: %r" % S.code(tl2))
    ta = dict(tl, ways=S.axis_path([[8, 8, None], [14, 11, 4.0]]))   # (a corner axis_path inserts: leg 2 inherits)
    if S.leg_heights(dict(ta, body=6.0)) != [6.0, 6.0]:
        bad.append("leg heights through axis_path: %r" % S.leg_heights(ta))
    if S.code(dict(tl, body=5.0, ways=[[x, y, None] for x, y, _z in tl["ways"]])) != \
            "tube keep 8 8 14 11 via 14 8 body 5":
        bad.append("pipe height for every leg")
    B.BLK_MAX, held = 1 << 30, B.BLK_MAX
    try:
        dt = E.Document(tt + S.code(tl) + "\n")
        dt.auto_band()
        c = B.compile_course(dt.text(), "tl.bbc", occluders=False)
        zs = sorted((k, v.z0) for k, v in c.tiles.items() if v.kind == B.KIND_WALL)
        if zs != [((x, 8), 12) for x in range(9, 15)] + [((14, 9), 8), ((14, 10), 8)]:
            bad.append("leg heights laid: %r" % zs)
        gap = tt.replace("floor rect 4 4 24 20 flat 2\n", "floor rect 4 4 10 20 flat 2\nfloor rect 14 4 24 20 flat 2\n"
                         "floor rect 10 14 14 20 flat 2\n")
        for tl_, ok in (("tube keep 8 8 15 8 column 1", True), ("tube keep 8 8 14 11 via 14 8 column 1", False)):
            sh = S.parse(tl_.split())
            if S.code(sh) != tl_ or sh.get("column") != 1.0:
                bad.append("column: %r" % S.code(sh))
            dt = E.Document((gap if ok else tt) + tl_ + "\n")
            dt.auto_band()
            try:
                c = B.compile_course(dt.text(), "tc.bbc", occluders=False)
                got = c.floats.get((11, 8)) == 8
            except B.CourseError as e:
                got = "column hangs nothing" in str(e) and None
            if (got is True) != ok or (not ok and got is not None):
                bad.append("column %s: %r" % (tl_, got))
        # 13e (SPEC.md 130.12.3.6, 130.58.40): a column that stops two units or more over the floor is a pipe the
        # ball passes UNDER - the builder adds `uses archway` for it; one that stops under two units is refused
        dt = E.Document(tt + "tube keep 8 8 15 8 body 5 column 1\n")
        dt.auto_band()
        added = dt.auto_uses()
        c = B.compile_course(dt.text(), "tp.bbc", occluders=False)
        sl = c.tiles[(11, 8)]
        arc = sorted(p["at"] for p in c.props if p["kind"] == B.FK_ARCH)
        if "archway" not in added or sl.kind != B.KIND_FLOOR or sl.slab is None or sl.slab[0].z0 != 10 \
                or sl.slab[1] != 32 or arc != [(x, 8) for x in range(9, 15)]:
            bad.append("pipe under: %r %r %r" % (added, (sl.kind, sl.slab), arc))
        try:
            B.compile_course(tt.replace("uses tube", "uses tube archway") + "tube keep 8 8 15 8 body 4.5 column 1\n",
                             "tl.bbc", occluders=False)
            bad.append("pipe 1.5 units over the floor: compiled")
        except B.CourseError as e:
            if "a ball needs 2 units" not in str(e):
                bad.append("pipe 1.5 units over the floor: %s" % str(e)[:150])
        # 13f (SPEC.md 130.12.3.7): the tube's Walkable top - `top` read and written back by the shape editor, the
        # builder adding `uses archway` for it, every body cell an archway element with a TOP (the passable ones
        # two-level, +20 the pipe's top; the walls walkable, clearance -32768); without it no TOP anywhere
        tl_ = "tube keep 8 8 15 8 via 10 8 via 13 8 body 3 5 3 column 1 top"
        sh = S.parse(E.tokens(tl_))
        if sh is None or not sh.get("top") or S.code(sh) != tl_ or "top" in S.code(dict(sh, top=None)):
            bad.append("walkable top: %r" % (sh and S.code(sh)))
        dt = E.Document(tt + tl_ + "\n")
        dt.auto_band()
        added = dt.auto_uses()
        c = B.compile_course(dt.text(), "tw.bbc", occluders=False)
        tops = sorted((p["at"], p["clr"], p["top"]) for p in c.props if p["kind"] == B.FK_ARCH and "top" in p)
        want = sorted([((x, 8), 16, 20) for x in (11, 12, 13)] + [((x, 8), -32768, 12) for x in (9, 10, 14)])
        if "archway" not in added or tops != want:
            bad.append("walkable top: %r %r" % (added, tops))
        c = B.compile_course(dt.text().replace(" top\n", "\n"), "tn.bbc", occluders=False)
        if any("top" in p for p in c.props):
            bad.append("no walkable top: a TOP laid")
    except B.CourseError as e:
        bad.append("leg heights: refused: %s" % str(e)[:150])
    finally:
        B.BLK_MAX = held
    # 13c. what stands on ground rides with it (SPEC.md 130.58.34): wholly-on statements, and a rail split
    dr = E.Document('course T "t"\nwidth 64\nfloor rect 3 3 9 9 flat 4\nfloor rect 9 3 14 9 flat 4\n'
                    'guard rect 3 3 14 4 side -y\nprop bumper 5 5\nstart 4 4\ntube keep 4 6 11 6\n')
    whole, split = dr.riders((3, 3, 9, 9))
    if [c for _l, c in whole] != ["prop bumper 5 5", "start 4 4"] or \
            [(i, o) for _l, i, o in split] != [("guard rect 3 3 9 4 side -y", ["guard rect 9 3 14 4 side -y"])]:
        bad.append("riders: %r %r" % (whole, split))
    # 14. DRAFTS AND TRACES (SPEC.md 130.58.27)
    ap = S.axis_path([[6, 6, None], [9, 6, None], [12, 6, None], [12, 12, None], [15, 14, None]])
    if ap != [[6, 6, None], [12, 6, None], [12, 12, None], [15, 12, None], [15, 14, None]]:
        bad.append("axis_path: %r" % ap)
    ip = S.insert_point([[8, 8, None], [15, 8, None]], (15, 12))
    if ip != [[8, 8, None], [15, 8, None], [15, 12, None]]:
        bad.append("insert_point past the end: %r" % ip)
    tr = dict(S.new_shape("tube", 6, 6, 2.0), ways=S.axis_path([[6, 6, None], [12, 12, None]]))
    try:
        dt = E.Document(tt + S.code(tr) + "\n")
        dt.auto_band()
        B.BLK_MAX, held = 1 << 30, B.BLK_MAX
        try:
            B.compile_course(dt.text(), "tr.bbc", occluders=False)
        finally:
            B.BLK_MAX = held
    except B.CourseError as e:
        bad.append("a traced tube: %s" % str(e)[:150])
    # 15. A GUARD RAIL is one of the parts on the cells along its edge (SPEC.md 130.58.28, 130.35): MILL's start floor
    an = E.Document.load(os.path.join(ROOT, "apps", "bonanza", "courses", "mill.bbc")).analysis()
    gl = [st.line for st in E.Document.load(os.path.join(ROOT, "apps", "bonanza", "courses", "mill.bbc")).statements()
          if st.kind == "guard" and st.toks[1:6] == ["rect", "7", "9", "13", "14"]]
    md = E.Document.load(os.path.join(ROOT, "apps", "bonanza", "courses", "mill.bbc"))
    if not any(md.statement(l_).kind == "surface" for l_ in E.at_cell(an, (13, 16))):
        bad.append("at_cell: MILL's bounce paint at (13, 16) is not offered: %r" % E.at_cell(an, (13, 16)))
    if not gl or gl[0] not in E.at_cell(an, (12, 12)):
        bad.append("at_cell: MILL's start-floor rail (line %r) is not offered at (12, 12): %r" % (
            gl, E.at_cell(an, (12, 12))))
    # 16. THE OCCLUDER VIEW (SPEC.md 130.58.32): a wall in front of a floor cuts a record over the floor behind it,
    # which the job names (its owner the wall, the cells whose ball it hides, the flags it sets); a noocclude over
    # every cell it hides (set_noocclude) and it is not cut; taken out again, it is
    occ_course = (FLAG % ("", "")).replace("checkpoint 6 5\n", "")
    try:
        B.BLK_MAX, held = 1 << 30, B.BLK_MAX
        try:
            c = B.compile_course(occ_course, "occ.bbc", occluders=True)
            od = J.occ_data(c)
            wall = [r for r in od["records"] if r["own"] and 7 <= r["own"][0][0] <= 9 and 6 <= r["own"][0][1] <= 7
                    and r["needs"]]
            behind = [r for r in wall if any(3 <= x <= 12 and 3 <= y <= 7 and x + y < 7 + 6 for x, y in r["needs"])
                      and not {tuple(n) for n in r["needs"]} & {(4, 4), (12, 4)}]   # (a FLOOR cell behind it)
            if not behind:
                bad.append("occ view: no record of the wall hides a cell behind it (%d records)" % len(od["records"]))
            else:
                r0 = behind[0]
                if not set(map(tuple, r0["needs"])) <= {(x, y) for x, y, _f in od["cells"]}:
                    bad.append("occ view: a cell record %d hides is not flagged: %r" % (r0["id"], r0["needs"]))
                pix0 = {(x, y_) for y_, x0_, x1_ in r0["runs"] for x in range(x0_, x1_ + 1)}
                do = E.Document(occ_course)
                added, _rm, refused = do.set_noocclude(add=r0["needs"])
                if not added or refused or "noocclude" not in do.text():
                    bad.append("occ view: set_noocclude wrote nothing: %r" % do.text()[-120:])
                c2 = B.compile_course(do.text(), "occ.bbc", occluders=True)
                still = [r for r in J.occ_data(c2)["records"]
                         if pix0 & {(x, y_) for y_, x0_, x1_ in r["runs"] for x in range(x0_, x1_ + 1)}
                         and set(map(tuple, r["needs"])) & set(map(tuple, r0["needs"]))]
                if still:
                    bad.append("occ view: noocclude over %r left record(s) %r over its pixels" % (
                        r0["needs"], [r["id"] for r in still]))
                do.set_noocclude(remove=r0["needs"])
                if "noocclude" in do.text() or do.text() != occ_course:
                    bad.append("occ view: noocclude taken out leaves %r" % do.text()[-120:])
                if (4, 4) not in do.set_noocclude(add=[(4, 4)])[2]:
                    bad.append("occ view: noocclude on the start was not refused")
        finally:
            B.BLK_MAX = held
    except B.CourseError as e:
        bad.append("occ view: refused: %s" % str(e)[:150])
    bad += stranded_check()
    for b_ in bad:
        print("FAIL " + b_)
    print("t_bbedit: %d courses, %s" % (len(courses), "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
