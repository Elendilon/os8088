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

 19. A MOUTH HEIGHT THE BUILDER CHOSE (130.58.41): the compiler's MouthFit names the height that fits (2.5 on a
    4-unit wall); the palette's drop's `height 3` and the kind switch's 2 are fitted on the picture's refusal, in
    the placement's undo step; a height typed in the Mouth height field is never changed, its row's fix button
    "Use height 2.5" builds; a drop traced onto a wall comes out on the floor past it, as one traced past it
    does, and no traced end writes a floor over a cell the course has (an empty one still gets one).

 20. A FLAG'S BLANK BALL IS THE BALL YOU HAD (SPEC.md 130.14.4.5, the owner 2026-11-23): the flag's "Ball here"
    row names its blank "as when touched" and its hint says a fall returns as the ball that touched the flag;
    cleared it writes the bare `checkpoint`, which compiles AS TOUCHED (+17 = CK_TOUCH), while `ball glass`
    compiles glass; and a blank flag a steel pad can bring steel to, past a gap steel cannot hop, is refused
    with words naming the flag, its missing Ball here and the steel ball.

 21. THE OCCLUDERS AS SHIPPED (SPEC.md 130.58.44): on item 16's floor occ_data's `shipped` is the part's records
    (c.records, after AV and the merge) pixel for pixel, fewer than the rule's, each naming the cells that need it
    and the rule's records sharing its pixels; bbedocc.OccView shows them by default, the rule's under "as cut" and
    under Shade alone, its status "N records shipped (M before AV)"; a noocclude over a shipped record's cells
    leaves no shipped record over its pixels needed by them alone. Red by hand: occ_data's `shipped` made the
    rule's rows ("304 records for the part's 215"), or OccView.shipped() False ("does not show the shipped records
    by default").
 22. OVER 256 MASKS (SPEC.md 130.58.45): the 256 masks' refusal explained and its fix button writing `masks banded`
    once; a band over its 256 explained with no button; the Course tab's box reading and writing the line. Red by
    hand: the WHOLE_FIXES row's pattern changed, or _apply_course without its `masks` row.
 23. THE CUT SHOWN ON A REFUSAL (SPEC.md 130.58.46): REC_ROW_MAX lowered to 1, the refused course's occ.json still
    written (both lists, needs, flags, the refusal) and the overlay saying REFUSED. Red by hand: partial_course
    returning None.
 24. SEVERAL AT ONCE (SPEC.md 130.58.47): a rectangle selects every shipped record, Ctrl-click in and out, the
    union of their cells made noocclude in ONE edit that one Undo takes back, several noocclude cells taken out in
    one. Red by hand: toggle only adding, or noocclude split into two edits.
 25. THE ROUTE'S WARNINGS (SPEC.md 130.58.49): on constructed courses, a way next to / on a see-saw's plate, a leg
    across an L's inside corner the arrows fall off, a tube mouth the route passes two cells off and a windmill
    doorway's cell left by its -x face are each named on the right way's line - and none is named for the way two
    cells clear, a way in the L's corner, a gap across the whole leg, a way on the mouth, the doorway left -y or by
    its corner; the plate's way on a leg the arrows really take is not named (the proof). The check job (strict)
    carries them as warnings; each has its explanation; the mouth's and doorway's buttons add the way after the
    named one in its branch, the plate's removes it, the gap's offers none. The toolbar's Autopilot names the
    picker's branch (130.58.50). Red by hand (2026-11-23): _lint_exit's corner (None) counted as a miss ("left by
    the corner ... got [('door' ..."), the detour test removed ("a gap across the whole leg"), _lint_proven made
    empty ("its leg taken by the arrows (the proof)").

 26. COURSE STATS (SPEC.md 130.58.51): the check job's stats for FIRST - its records, masks, blocks, part and
    picture the compile's own, each with its bound, the floppy's bytes os88pkg.compress_part's LZB of the part with
    its song, nothing past a bound - and DOWN, past 1,024 px and in SHEETS (and nothing else), its width at its
    bound. Red by hand (2026-11-23): course_stats's wide test made `c.cols > 160` ("DOWN goes past ['sheets'],
    not ['wide', 'sheets']").

Red arms, by hand: drop the `half`/`quarter` skip from bbedproj.coord_slots
(item 2 goes red on DOWN), make bbcourse._visual raise again (item 3), or
make toggle_gap's `codes` keep the pieces no face is in (item 8: "gap bands
nothing"), make occ_data add no cell to a record's `needs` (item 16: "no record
of the wall hides a cell behind it"), or cut with `rcut = reach` in
compile_course (item 16: "noocclude ... left record(s)"); delete crack's `hole` row from bbedopts.OPTIONS
(item 17: "no row for prop crack's hole"), or give the see-saw's `rest` row `at=None` (item 17: "rest ...
not legal again"); for item 18, drop the `text != tried` test from bbedshape.picture_refused ("undid the float's
delete") or make bbedit.App._edit compare `after != before` again ("an edit above the float was refused");
for item 19, keep `fit = None` in bbcourse's mouth refusal ("MouthFit line 12 fit None"), drop the palette's
`auto_mouth.add` ("the palette's drop was not fitted"), set_kind's `mouth_auto` ("the kind switch's drop was
not fitted"), _fit_mouth's is_auto_mouth test ("a typed height was changed"), the FIXES row's "Use height {0}"
words, _add_traced's wall extension ("a drop traced onto the wall laid []") or its `d is None` ("wrote a floor
over it").
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
    ("seesaw", None): ("seesaw 4 4 6 5 along x pivot 3 rest + period 64 flat 6 seed 3 base 1.5",
                       "seesaw 4 4 6 5 along x pivot 3 base ground"),
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


# item 19 (SPEC.md 130.58.41): the owner's case on _W3W - a wall 4 units over the floor OUT is on, so the palette's
# `height 3` mouth (its sill 24 px up, 9 px tall) does not fit its face; the compiler names the most that does
MOUTH = B._W3W + "wall tile 7 13 flat 20\nfloor rect 6 14 9 17 flat 16\n"


class _Var(object):
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


class _PaletteApp(_StubApp):
    """add_part's own helpers, no Tk"""
    add_part, _fit_mouth, _add_traced = W.App.add_part, W.App._fit_mouth, W.App._add_traced
    _target, _heights, _flat_heights, _lowest_beside = (W.App._target, W.App._heights, W.App._flat_heights,
                                                        W.App._lowest_beside)
    _is_path_part = staticmethod(W.App._is_path_part)
    GROUND, PAINT, ON_GROUND = W.App.GROUND, W.App.PAINT, W.App.ON_GROUND

    def __init__(self, text):
        _StubApp.__init__(self, text)
        self.part, self.path_pick, self.area, self.height, self.shapes = None, [], None, _Var("4"), None

    def _show_shape(self, ln):
        self.sel = ln


class _SetVar(_Var):
    def set(self, v):
        self.v = v


class _RouteApp(_StubApp):
    """the route's branch picker and Ctrl-click (SPEC.md 130.58.43), no Tk"""
    _ways, _br_shown, _br_target, _branches, route_add, _route_ctrl, route_fork = (
        W.App._ways, W.App._br_shown, W.App._br_target, W.App._branches, W.App.route_add, W.App._route_ctrl,
        W.App.route_fork)
    root = None

    def __init__(self, text, br):
        _StubApp.__init__(self, text)
        self.route_branch, self.show_route, self.view = _SetVar(br), _Var(True), _Var("plan")


def route_check():
    """item 20 (SPEC.md 130.58.43): a branch chosen shows and takes only its points; Ctrl-click lays a point in
    it, after the selected one of its own; with All branches and nothing selected Ctrl-click still selects"""
    bad = []
    base = ("course RT \"Route\"\nwidth 64\nfloor rect 0 0 12 4 flat 2\nstart 1 1\nclock 0 0\nclock 11 3\n"
            "way 2 1\nway 9 1\nway 3 2 branch B\nway 8 2 branch B\n")
    a = _RouteApp(base, "B")
    if [w[3] for w in a._ways() if a._br_shown(w[3])] != ["B", "B"]:
        bad.append("route: branch B chosen does not show only B's points")
    if a._br_shown(None):
        bad.append("route: branch B chosen still shows the main route")
    if not a._route_ctrl():
        bad.append("route: with a branch chosen Ctrl-click does not lay a route point")
    a.route_add((5, 2))
    ws = a._ways()
    if ws[-1][1:] != (5, 2, "B"):
        bad.append("route: Ctrl-click in branch B laid %r, not 'way 5 2 branch B' after B's last" % (ws[-1],))
    a.sel = ws[2][0]                    # B's first point selected: the next goes right after it
    a.route_add((4, 3))
    bw = [w[1:3] for w in a._ways() if w[3] == "B"]
    if bw != [(3, 2), (4, 3), (8, 2), (5, 2)]:
        bad.append("route: a point Ctrl-clicked with B's first selected is not after it: %r" % bw)
    m = _RouteApp(base, W.MAIN_ROUTE)
    m.route_add((6, 1))
    if [w[1:] for w in m._ways() if w[3] is None] != [(2, 1, None), (9, 1, None), (6, 1, None)]:
        bad.append("route: Main route chosen, Ctrl-click did not join the main route")
    al = _RouteApp(base, W.ALL_BRANCHES)
    if al._route_ctrl():
        bad.append("route: All branches with nothing selected took Ctrl-click from the selection")
    al.sel = al._ways()[3][0]
    if not al._route_ctrl() or al._br_target() != "B":
        bad.append("route: All branches with B's point selected does not lay into B")
    if True:
        f = _RouteApp(base, W.ALL_BRANCHES)
        f.route_fork(f._ways()[1][0], "gl")    # main point (9, 1): a branch GL forking exactly there
        g = [w[1:] for w in f._ways() if w[3] == "GL"]
        if g != [(9, 1, "GL")] or f.route_branch.v != "GL":
            bad.append("route: Branch from here on main (9, 1) gave %r, picker %r" % (g, f.route_branch.v))
        f.route_add((10, 2))
        if [w[1:3] for w in f._ways() if w[3] == "GL"] != [(9, 1), (10, 2)]:
            bad.append("route: the forked branch's next Ctrl-click does not follow its fork point")
    return bad


def course_tab_check():
    """item 26: the Course tab's Apply writes every field typed, though each edit refills the tab from the course
    (the medals vanished once `limit` was written first) -> [problems]"""
    bad = []

    class _C(_StubApp):
        _apply_course, _fill_course = W.App._apply_course, W.App._fill_course

        def __init__(self, text):
            _StubApp.__init__(self, text)
            for k in ("cv_title", "cv_name", "cv_width", "cv_ball", "cv_music", "cv_pal", "cv_gstyle", "cv_target",
                      "cv_limit", "cv_gold", "cv_silver", "cv_cstrict", "cv_mbanded", "cv_lock"):
                setattr(self, k, _SetVar(""))
            self.cv_stops = {e: _SetVar("") for e in B.STOP_EDGES}
            self._fill_course()
            self.doc.listeners.append(lambda *a: self._fill_course())   # (the window's _changed refills the tab)
    base = "course CT \"Course tab\"\nwidth 64\nfloor rect 0 0 4 4 flat 2\nstart 1 1\n"
    a = _C(base)
    a.cv_limit.set("120")
    a.cv_gold.set("70")
    a.cv_silver.set("90")
    a._apply_course()
    got = [l for l in a.doc.text().split("\n") if l.startswith(("limit", "medals"))]
    if sorted(got) != ["limit 120", "medals 70 90"]:
        bad.append("item 26: the Course tab's limit 120, medals 70 90 applied as %r" % got)
    # SPEC.md 130.45.5: the camera's flags - the four stop ticks one `stop` statement, read back; none, taken out
    a.cv_stops["down"].set(True)
    a.cv_stops["left"].set(True)
    a.cv_lock.set(True)
    a._apply_course()
    got = [l for l in a.doc.text().split("\n") if l.startswith(("stop", "lock"))]
    if sorted(got) != ["lock across", "stop down left"]:
        bad.append("item 26: the Course tab's lock and stops down, left applied as %r" % got)
    b = _C(base + "stop up right\n")
    if [e for e in B.STOP_EDGES if b.cv_stops[e].get()] != ["up", "right"] or b.cv_lock.get():
        bad.append("item 26: the Course tab does not read `stop up right`")
    for e in B.STOP_EDGES:
        a.cv_stops[e].set(False)
    a.cv_lock.set(False)
    a._apply_course()
    if any(l.startswith(("stop", "lock")) for l in a.doc.text().split("\n")):
        bad.append("item 26: the Course tab's stops cleared leave %r" % a.doc.text()[-80:])
    return bad


def stats_check():
    """26. COURSE STATS (SPEC.md 130.58.51): the check job's stats for FIRST (one part, nothing past a bound) and
    DOWN (1,280 px and SHEETS) - each figure the compile's own, the floppy's bytes os88pkg's LZB of the part"""
    import io
    import contextlib
    import json
    import os88pkg
    bad = []
    got = {}
    for nm in ("first", "down"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = J.check(os.path.join(ROOT, "apps", "bonanza", "courses", nm + ".bbc"), False)
        res = json.loads(out.getvalue().strip().splitlines()[-1])
        st = res.get("stats")
        if rc or not st:
            bad.append("item 27: %s's check gave rc %d and no stats: %s" % (nm, rc, str(res)[:150]))
            continue
        got[nm] = st
    if len(got) < 2:
        return bad
    rows = {r["key"]: r for r in got["first"]["rows"]}
    c = B.compile_course(os.path.join(ROOT, "apps", "bonanza", "courses", "first.bbc"))
    B.attach_song(c, B._music()[1][B.course_song(c)])
    with contextlib.redirect_stdout(io.StringIO()):
        lzb = os88pkg.compress_part(0, bytes(c.stored), "lzb")[1]
    want = {"records": (len(c.model["recs"]), None), "masks": (len(c.masks), 256), "blocks": (len(c.blocks), 1024),
            "picture": (len(c.cga), B.PARTMAX), "disk": (lzb, None), "width": (512, 1280)}
    for k, (n, mx) in want.items():
        if k not in rows or (rows[k]["n"], rows[k]["max"]) != (n, mx):
            bad.append("item 27: FIRST's %s row is %r, not %r" % (k, rows.get(k) and (rows[k]["n"], rows[k]["max"]),
                                                                   (n, mx)))
    if "world" in rows or "sheet0" in rows or "time" not in rows or "limit 15 s" not in rows["time"]["text"]:
        bad.append("item 27: FIRST's parts or time rows: %r" % sorted(rows))
    for nm, keys in (("first", []), ("down", ["wide", "sheets"])):
        ab = [a["key"] for a in got[nm]["above"]]
        if ab != keys or any("130." not in a["spec"] for a in got[nm]["above"]):
            bad.append("item 27: %s goes past %r, not %r" % (nm.upper(), ab, keys))
    dr = {r["key"]: r for r in got["down"]["rows"]}
    if not {"sheet0", "sheet1", "world"} <= set(dr) or "picture" in dr or dr["width"]["state"] != "near" \
            or "Sheets" not in got["down"]["summary"]:
        bad.append("item 27: DOWN's rows %r, width %r, summary %r" % (sorted(dr), dr.get("width"),
                                                                      got["down"]["summary"]))
    return bad


def _lint(text, noproof=False):
    """item 25: bbcourse.route_lint on TEXT's play-only compile -> [(what, line, cell)], or the refusal"""
    held, B.BLK_MAX = B.BLK_MAX, 1 << 30
    B._LINT_NOPROOF = noproof
    try:
        c = B.compile_course(text, "rl.bbc", occluders=False)
        return [(w["what"], w["line"], tuple(w["cell"])) for w in B.route_lint(c)]
    except B.CourseError as e:
        return "REFUSED " + str(e)[:150]
    finally:
        B.BLK_MAX = held
        B._LINT_NOPROOF = False


class _AutoApp(_StubApp):
    """the toolbar's Autopilot (SPEC.md 130.58.50): its command line, no Tk"""
    autopilot_argv, _ways, _branches, _name = W.App.autopilot_argv, W.App._ways, W.App._branches, W.App._name

    def __init__(self, text, br):
        _StubApp.__init__(self, text)
        self.route_branch = _SetVar(br)


def route_lint_check():
    """item 25 (SPEC.md 130.58.49): the route's warnings - each named on a constructed course, with its negative
    control; the leg a real run takes is not named (the proof); the check job carries them; their explanations
    and fix buttons. And the toolbar's Autopilot names the picker's branch (130.58.50)"""
    bad = []

    def want(what, got, exp):
        if got != exp:
            bad.append("item 25: %s: got %r, wanted %r" % (what, got, exp))

    # 1. A WAY ON OR NEXT TO A SEE-SAW'S PLATE (the geometry alone; MILL's (23, 21) was next to its plate)
    S_ = ('course S "s"\nwidth 64\nuses seesaw\nfloor rect 4 6 8 10 flat 4\nseesaw 8 7 10 9 along x pivot 4\n'
          'floor rect 10 6 16 10 flat 4\nstart 5 7\nway 5 7\n')
    want("a way next to the plate", _lint(S_ + "way 7 7\nway 14 7\n", True), [("seesaw", 9, (7, 7))])
    want("a way on the plate", _lint(S_ + "way 9 7\nway 14 7\n", True), [("seesaw", 9, (9, 7))])
    want("a way two cells clear (negative)", _lint(S_ + "way 6 7\nway 14 7\n", True), [])
    want("next to the plate, its leg taken by the arrows (the proof)", _lint(S_ + "way 7 7\nway 14 7\n"), [])
    # 2. A STRAIGHT LEG OVER NO FLOOR: an L of floor, the leg across its inside corner - the arrows fall there
    L_ = 'course V "v"\nwidth 64\nfloor rect 4 4 12 7 flat 4\nfloor rect 9 7 12 16 flat 4\nstart 5 5\nway 5 5\n'
    want("a leg across the L's corner", _lint(L_ + "way 10 14\n"), [("void", 6, (5, 5))])
    want("a way in the L's corner (negative)", _lint(L_ + "way 10 5\nway 10 14\n"), [])
    G_ = 'course V "v"\nwidth 64\nfloor rect 4 4 12 7 flat 4\nfloor rect 4 9 12 12 flat 4\nstart 5 5\nway 5 5\n'
    want("a gap across the whole leg (the design's: no way goes round)", _lint(G_ + "way 5 10\n"), [])
    # 3. A TUBE'S MOUTH THE ROUTE PASSES AND NEVER ENTERS, and 4. A WINDMILL'S DOORWAY THE LEG LEAVES SIDEWAYS
    W_ = B._W3W                                     # (a KEEP tube in at (9, 9), its windmill's doorway the +y face)
    want("the mouth passed two cells off", _lint(W_ + "way 9 12\nway 7 10\nway 6 12\n", True), [("mouth", 10, (9, 12))])
    want("a way on the mouth (negative)", _lint(W_ + "way 9 12\nway 9 9\nway 12 5\n", True), [])
    want("the doorway's cell left by its -x face", _lint(W_ + "way 9 12\nway 9 9\nway 6 10\n", True),
         [("door", 11, (9, 9))])
    want("...left through the doorway, -y (negative)", _lint(W_ + "way 9 12\nway 9 9\nway 12 5\n", True), [])
    want("...left by the corner (MILL's first windmill: pressed in too)",
         _lint(W_ + "way 9 12\nway 9 9\nway 12 6\n", True), [])
    # the check job carries them, never as a refusal
    import io
    import contextlib
    import json
    with tempfile.TemporaryDirectory() as td:
        p_ = os.path.join(td, "rl.bbc")
        with open(p_, "w", encoding="ascii") as f:     # (a test course, and a finish: the full check owes one)
            f.write(L_.replace("width 64\n", "test\nwidth 64\n").replace(
                "9 7 12 16 flat 4\n", "9 7 12 14 flat 4\ngoal rect 9 14 12 16 flat 4\n") + "way 10 14\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = J.check(p_, True)
        res = json.loads(out.getvalue().strip().splitlines()[-1])
        rw = [w for w in res.get("warnings", []) if w["kind"] == "route"]
        if rc or not res.get("ok") or [(w["line"], tuple(w["cell"])) for w in rw] != [(8, (5, 5))]:
            bad.append("item 25: the check job (strict) gave rc %d, ok %r, route warnings %r" % (rc, res.get("ok"), rw))
    # the window's words and buttons
    msgs = {
        "seesaw": "rl.bbc:9: route: way (7, 7) is next to the see-saw of line 5: the autopilot counts ...",
        "void": "rl.bbc:6: route: the straight line from way (5, 5) to way (10, 14) (the main route) passes over "
                "(7, 8), which has no floor, and ...",
        "mouth": "rl.bbc:10: route: the keep tube of line 7 goes in at (9, 9), and no way sits on that cell and no "
                 "leg crosses it: the autopilot passes 2 cells from it and never goes in - put a way on (9, 9)",
        "door": "rl.bbc:11: route: the windmill of line 8 is entered through its +y face at (9, 9), and the leg from "
                "way (9, 9) to way (6, 10) leaves that cell by its -x face: the ball is never pushed into the "
                "doorway - add a way past the doorway at (9, 4), -y of it, after way (9, 9)"}
    for what, m in msgs.items():
        if W.explain(m) == m:
            bad.append("item 25: the %s warning has no plain explanation" % what)
    d = E.Document(W_ + "way 9 12\nway 7 10 branch B\nway 6 12 branch B\n")
    fx = W.fix_for(msgs["mouth"], 11, d)                 # (line 11: B's first point)
    if not fx or fx[0] != "Add a route point on (9, 9)":
        bad.append("item 25: the mouth warning offers %r" % (fx,))
    else:
        fx[1](d)
        if "way 7 10 branch B\nway 9 9 branch B\nway 6 12 branch B\n" not in d.text():
            bad.append("item 25: the mouth's fix did not lay 'way 9 9 branch B' after line 10: %r" % d.text()[-60:])
    d = E.Document(S_ + "way 7 7\nway 14 7\n")
    fx = W.fix_for(msgs["seesaw"], 9, d)
    if not fx or fx[0] != "Remove this route point":
        bad.append("item 25: the see-saw warning offers %r" % (fx,))
    else:
        fx[1](d)
        if "way 7 7" in d.text():
            bad.append("item 25: the see-saw's fix left the way")
    fx = W.fix_for(msgs["door"], 11, E.Document(W_ + "way 9 12\nway 9 9\nway 6 10\n"))
    if not fx or fx[0] != "Add a route point on (9, 4)":
        bad.append("item 25: the doorway warning offers %r" % (fx,))
    if W.fix_for(msgs["void"], 6, E.Document(L_ + "way 10 14\n")):
        bad.append("item 25: the void warning offers a fix (where the way goes is the author's)")
    # the toolbar's Autopilot: the picker's branch, else the main route
    base = ("course RT \"Route\"\nwidth 64\nfloor rect 0 0 12 4 flat 2\nstart 1 1\nway 2 1\nway 9 1\n"
            "way 3 2 branch B\nway 8 2 branch B\n")
    for br, tail in (("B", ["--autopilot", "--branch", "B"]), (W.ALL_BRANCHES, ["--autopilot"]),
                     (W.MAIN_ROUTE, ["--autopilot"]), ("GONE", ["--autopilot"])):
        av = _AutoApp(base, br).autopilot_argv("x.bbc")
        if av[-len(tail):] != tail or (br != "B" and "--branch" in av):
            bad.append("item 25: Autopilot with %r chosen runs %r" % (br, av[2:]))
    return bad


def _refusal(text):
    """the picture job's `done` event for TEXT: {ok, error, mouth}"""
    held, B.BLK_MAX = B.BLK_MAX, 1 << 30
    try:
        B.compile_course(text, "d.bbc", occluders=False)
        return {"stage": "done", "ok": True}
    except B.CourseError as e:
        return dict({"stage": "done", "ok": False, "error": str(e)}, **J.refusal(e))
    finally:
        B.BLK_MAX = held


def mouth_check():
    """item 19 (SPEC.md 130.58.41) -> [problems]"""
    bad = []
    # (1) the compiler: the refusal names the height that fits, as a MouthFit carrying the line and h2
    try:
        B.compile_course(MOUTH + "tube drop 7 12 7 14 height 3\n", "d.bbc")
        bad.append("mouth: a 3-unit mouth on a 4-unit face compiled")
    except B.MouthFit as e:
        if e.line != MOUTH.count("\n") + 1 or e.fit != 5 or "height 2.5 fits; a taller wall" not in str(e):
            bad.append("mouth: MouthFit line %r fit %r: %s" % (e.line, e.fit, e))
    except B.CourseError as e:
        bad.append("mouth: refused, but not a MouthFit: %s" % e)
    # (2) the palette's Tube (drop) on the strip (7, 12) - (7, 14): its `height 3` the builder's, fitted
    app = _PaletteApp(MOUTH)
    app.area = (7, 12, 7, 14)
    app.add_part("Tube (drop)")
    ln = next((st.line for st in app.doc.statements() if st.kind == "tube" and st.toks[1] == "drop"), None)
    n1 = len(app.doc.undo_stack)
    e = _refusal(app.doc.text())
    if not ln or "height 3" not in app.doc.lines[ln - 1] or e.get("mouth") != [ln, 5]:
        bad.append("mouth: the palette's drop at line %r: %r, its picture %r" % (
            ln, ln and app.doc.lines[ln - 1], {k: e.get(k) for k in ("error", "mouth")}))
    elif not app._fit_mouth(e, app.doc.text()):
        bad.append("mouth: the palette's drop was not fitted (%s)" % app.msgs[-1:])
    else:
        if "height 2.5" not in app.doc.lines[ln - 1] or (_refusal(app.doc.text()).get("mouth")):
            bad.append("mouth: the palette's drop fitted to %r" % app.doc.lines[ln - 1])
        if len(app.doc.undo_stack) != n1 or not any("Mouth height set to 2.5" in m for m in app.msgs):
            bad.append("mouth: the fit is not folded into the placement (%d undo steps), or not said: %r" % (
                len(app.doc.undo_stack) - n1 + 1, app.msgs[-1:]))
        app.doc.move(ln, 1, 0)                  # (still the builder's after a move, which keeps the height)
        if not app.doc.is_auto_mouth(ln):
            bad.append("mouth: the fitted height moved is no longer the builder's")
        app.doc.set_clause(ln, "height", ["2"])  # (and not once it is changed)
        if app.doc.is_auto_mouth(ln):
            bad.append("mouth: a height written over the builder's is still the builder's")
    # (3) the shape editor's kind switch: a KEEP tube made a DROP, Try it, the builder's 2 units refused on a
    # 2.5-unit face (a wall 2.5 over the floor) - fitted to 1.5
    low = B._W3W + "wall tile 7 13 flat 18.5\nfloor rect 6 14 9 17 flat 16\ntube keep 7 12 7 14\n"
    app = _StubApp(low)
    tl = low.count("\n")
    se = S.ShapeEditor(app, None, None, None, None)
    app.shapes = se
    app._fit_mouth = lambda e, t: W.App._fit_mouth(app, e, t)
    se.load(tl)
    se.draft = S.set_kind(se.sh, "drop")
    se.try_draft()
    e = _refusal(app.doc.text())
    if app.doc.statement(tl).code != "tube drop 7 12 7 14 height 2" or not e.get("mouth") or e["mouth"][0] != tl:
        bad.append("mouth: the kind switch wrote %r, its picture %r" % (app.doc.statement(tl).code, e))
    elif not app._fit_mouth(e, app.doc.text()):
        bad.append("mouth: the kind switch's drop was not fitted")
    elif _refusal(app.doc.text()).get("mouth") or se.pending[1] != app.doc.statement(tl).code:
        bad.append("mouth: the kind switch's drop fitted to %r, still refused or not pending" %
                   app.doc.statement(tl).code)
    # (4) a height the author TYPED is never changed: the Mouth height field's draft, refused, fit refused too;
    # the error row offers "Use height N", which makes it build
    app = _StubApp(MOUTH + "tube drop 7 12 7 14 height 2\n")
    se = S.ShapeEditor(app, None, None, None, None)
    app.shapes = se
    tl = MOUTH.count("\n") + 1
    se.load(tl)
    se.draft = dict(se.sh, height=3.0, mouth_auto=False)   # (what the field's setter writes)
    se.try_draft()
    text = app.doc.text()
    e = _refusal(text)
    if W.App._fit_mouth(app, e, text) or app.doc.text() != text:
        bad.append("mouth: a typed height was changed: %r" % app.doc.statement(tl).code)
    fx = W.fix_for(e.get("error") or "", E._line_of(e.get("error") or ""), app.doc)
    if not fx or fx[0] != "Use height 2.5" or "2.5 is the most" not in W.explain(e.get("error") or ""):
        bad.append("mouth: the typed height's error row offers %r, explained %r" % (
            fx and fx[0], W.explain(e.get("error") or "")[:120]))
    else:
        app._edit(fx[1], app.doc)
        if app.doc.statement(tl).code != "tube drop 7 12 7 14 height 2.5" or _refusal(app.doc.text()).get("mouth"):
            bad.append("mouth: Use height 2.5 left %r" % app.doc.statement(tl).code)
    # (5) a DROP TRACED (Ctrl-click) onto the wall (7, 13), the floor (7, 14) past it: OUT goes on that floor, the
    # wall its last body cell - and no floor tile is written over the wall; traced on to the floor, the same tube
    for trace, what in (([(7, 12), (7, 13)], "onto the wall"), ([(7, 12), (7, 13), (7, 14)], "past the wall")):
        app = _PaletteApp(MOUTH)
        app.path_pick = list(trace)
        app.add_part("Tube (drop)")
        tubes = [st.code for st in app.doc.statements() if st.kind == "tube" and st.toks[1] == "drop"]
        if tubes != ["tube drop 7 12 7 14 height 3"] or "wall tile 7 13 flat 20" not in app.doc.lines or \
                any(l_.startswith("floor tile") for l_ in app.doc.lines):
            bad.append("mouth: a drop traced %s laid %r, the lines %r" % (what, tubes, app.doc.lines[-3:]))
            continue
        e = _refusal(app.doc.text())
        if not app._fit_mouth(e, app.doc.text()) or "tube drop 7 12 7 14 height 2.5" not in app.doc.lines:
            bad.append("mouth: a drop traced %s was not fitted: %r" % (what, e.get("error")))
    # (6) a traced end on a wall with no floor past it (_W3W's wall at (7, 8), wall again at (7, 7)): the wall
    # stays a wall - never a floor tile over a cell the course has; an EMPTY end still gets one
    app = _PaletteApp(B._W3W)
    app.path_pick = [(7, 10), (7, 8)]
    app.add_part("Tube (keep)")
    if any(l_.startswith("floor tile 7 8") for l_ in app.doc.lines) or "OUT cell (7, 8) is not a FLOOR" not in (
            app.banner or ""):                  # (refused, saying why, rather than the wall quietly made floor)
        bad.append("mouth: a tube traced onto a wall wrote a floor over it: %r" % app.doc.lines)
    app = _PaletteApp(B._W3W)
    app.path_pick = [(7, 12), (7, 18)]
    app.add_part("Tube (launch)")
    if "floor tile 7 18 flat 16" not in app.doc.lines:
        bad.append("mouth: a tube traced to an empty cell got no floor under it: %r (%s)" % (app.doc.lines,
                                                                                           app.banner))
    return bad


_CKT = ('course H "h"\nwidth 64\norigin 224\n'
        'floor rect 4 5 9 8 flat 4\nwall rect 4 4 9 5 flat 5\nfloor rect 11 5 15 8 flat 4\nwall rect 11 4 15 5 flat 5\n'
        'start 5 6\ncup 13 6\ncheckpoint 5 7%s\n%s')


def flag_ball_check():
    """item 20 (SPEC.md 130.14.4.5): a flag's blank ball is the ball you had -> [problems]"""
    bad = []
    row = [o for o in OPT.OPTIONS[("checkpoint", None)] if o["w"] == "ball"]
    if len(row) != 1 or row[0]["blank"] != "as when touched" or "touched this flag" not in row[0]["hint"]:
        bad.append("item 20: the flag's Ball here row does not say blank is the ball you had: %s" % (
            [(o["blank"], o["hint"]) for o in row],))

    def balls(text):
        try:
            c = B.compile_course(text, "ckt.bbc")
        except B.CourseError as e:
            return str(e)
        return [r["ball"] for r in c.part["props"] if r["kind"] == B.PK_CHECKPOINT]
    got = (balls(_CKT % ("", "")), balls(_CKT % (" ball glass", "")))
    if got != ([B.CK_TOUCH], [B.MAT_GLASS]):
        bad.append("item 20: a blank flag and a glass one compile to %s, wanted [%d] and [%d]" % (
            got, B.CK_TOUCH, B.MAT_GLASS))
    err = balls(_CKT % ("", "pad steel 13 7\n"))
    words = W.explain(err) if isinstance(err, str) else ""
    if not isinstance(err, str) or not words.startswith("Flag 0 has no Ball here") or "a steel ball" not in words:
        bad.append("item 20: a blank flag steel can reach but not leave: %s" % ((words or err)[:200],))
    return bad


class _OccApp(object):
    """what bbedocc.OccView reads of the window, no Tk"""
    def __init__(self, text, secs=1.5):
        self.doc = E.Document(text)
        self.pic = {"meta": {"occ": {"secs": secs}}}


def occ_ship_check(c, od, text):
    """item 21 (SPEC.md 130.58.44): the occluder view shows what SHIPS - occ_data's `shipped` is the part's records
    (c.records, after AV and the merge), each named back to the rule's records it was cut as and to the cells
    that need it; OccView shows them by default and the rule's with *as cut*, its status gives both counts, and
    noocclude over a shipped record's cells leaves no shipped record over its pixels -> [problems]"""
    import bbedocc as O
    bad = []
    sh, rl = od.get("shipped"), od["records"]
    if sh is None or len(sh) != len(c.records) or od.get("av") != bool(c.av):
        return ["item 21: occ_data's shipped list is %s records for the part's %d (av %r)" % (
            None if sh is None else len(sh), len(c.records), od.get("av"))]
    if len(sh) >= len(rl):
        bad.append("item 21: %d shipped against %d as cut - AV and the merge took nothing on FLAG" % (len(sh),
                                                                                                    len(rl)))
    rpix = {}
    for r in rl:
        for y, x0, x1 in r["runs"]:
            for x in range(x0, x1 + 1):
                rpix.setdefault((x, y), set()).add(r["id"])
    for r in sh:
        px = {(x, y) for y, x0, x1 in r["runs"] for x in range(x0, x1 + 1)}
        if px != {(x, y) for (x, y) in c.records[r["id"]]["pix"]}:
            bad.append("item 21: shipped record %d's pixels are not the part's record's" % r["id"])
            break
        if not r["needs"] or not r["rule"] or set(r["rule"]) != {k for p in px for k in rpix.get(p, ())}:
            bad.append("item 21: shipped record %d names needs %r, cut as %r" % (r["id"], r["needs"], r["rule"]))
            break
    v = O.OccView.__new__(O.OccView)
    v.app, v.data, v.flags = _OccApp(text), od, {(x, y): f for x, y, f in od["cells"]}
    v.show, v.shade, v.which = _Var(True), _Var(False), _Var("shipped")
    said = []
    v._say = said.append
    v.wanted = lambda: True
    if v.recs() is not sh:
        bad.append("item 21: the Occluders overlay does not show the shipped records by default")
    v._counts()
    want = "%s records shipped (%s before AV)" % (format(len(sh), ","), format(len(rl), ","))
    if not said or not said[-1].startswith(want):
        bad.append("item 21: the status reads %r, not %r" % (said[-1:] or None, want))
    k = max(range(len(sh)), key=lambda i: len(sh[i]["needs"]))
    if not v.describe(k).startswith("shipped occluder %d (cut as the rule's" % k):
        bad.append("item 21: a shipped record is described %r" % v.describe(k)[:120])
    v.which = _Var("cut")
    if v.recs() is not rl or "showing the rule's" not in (v._counts() or said[-1]):
        bad.append("item 21: *as cut* does not show the rule's records")
    v.show, v.shade = _Var(False), _Var(True)
    if v.recs() is not rl:
        bad.append("item 21: Shade alone does not take the rule's records (its doorway's ids are the rule's)")
    do = E.Document(text)
    play = do.in_play()                 # (the start's and the route points' cells: noocclude refuses them)
    free = [i for i in range(len(sh)) if not {tuple(n) for n in sh[i]["needs"]} & play]
    if not free:
        return bad + ["item 21: every shipped record is needed by the start or a route point"]
    k = max(free, key=lambda i: len(sh[i]["needs"]))
    r0 = sh[k]
    pix0 = {(x, y_) for y_, x0_, x1_ in r0["runs"] for x in range(x0_, x1_ + 1)}
    do.set_noocclude(add=r0["needs"])
    c2 = B.compile_course(do.text(), "occ.bbc", occluders=True)
    still = [r for r in J.occ_data(c2)["shipped"]
             if pix0 & {(x, y_) for y_, x0_, x1_ in r["runs"] for x in range(x0_, x1_ + 1)}
             and set(map(tuple, r["needs"])) <= set(map(tuple, r0["needs"]))]
    if still:
        bad.append("item 21: noocclude over shipped record %d's cells %r left shipped record(s) %r over its pixels" % (
            k, r0["needs"], [r["id"] for r in still]))
    return bad


class _SVar(_Var):
    def set(self, v):
        self.v = v


class _CourseApp(object):
    """the Course tab's variables and its two methods, no Tk"""
    _fill_course, _apply_course = W.App._fill_course, W.App._apply_course

    def __init__(self, text):
        self.doc = E.Document(text)
        for n in ("title", "name", "width", "ball", "music", "pal", "target", "limit", "gold", "silver", "gstyle",
                  "cstrict", "mbanded", "lock"):
            setattr(self, "cv_" + n, _SVar(""))
        self.cv_stops = {e: _SVar("") for e in B.STOP_EDGES}
        self.msgs = []

    def _msg(self, m):
        self.msgs.append(m)


def masks_check(text):
    """item 22 (SPEC.md 130.58.45): over 256 masks - the refusal explained, its fix button writing `masks banded`
    (once), the Course tab's box reading and writing it, and a band over its 256 explained as past what banding
    does -> [problems]"""
    bad = []
    e256 = "occ.bbc: 301 occluder masks, over the 256 a 4-byte record's mask byte names (SPEC.md 130.15.5)"
    eband = ("occ.bbc: band 1 (block rows 16 - 31) names 270 occluder masks, over the 256 a record's mask byte "
             "names in its band (SPEC.md 130.52)")
    if "masks banded" not in W.explain(e256) or "301" not in W.explain(e256):
        bad.append("item 22: the 256 masks' refusal is not explained: %r" % W.explain(e256)[:160])
    if "as far as the game goes" not in W.explain(eband) or "band 1" not in W.explain(eband):
        bad.append("item 22: a band over its 256 is not explained as past masks banded: %r" % W.explain(eband)[:160])
    fx = W.fix_for(e256, None, E.Document(text))
    if not fx or fx[0] != "Give each band its own mask table (masks banded)":
        return bad + ["item 22: the 256 masks' refusal offers no fix: %r" % (fx,)]
    d = E.Document(text)
    fx[1](d)
    fx[1](d)
    if d.text().count("masks banded\n") != 1:
        bad.append("item 22: the fix wrote %d `masks banded` lines" % d.text().count("masks banded"))
    try:
        B.compile_course(d.text(), "mb.bbc", occluders=False)
    except B.CourseError as e:
        bad.append("item 22: the fixed course is refused: %s" % str(e)[:150])
    if W.fix_for(eband, None, E.Document(text)):
        bad.append("item 22: a band over its 256 offers a fix that cannot help")
    ca = _CourseApp(d.text())
    ca._fill_course()
    if ca.cv_mbanded.get() is not True:
        bad.append("item 22: the Course tab's box does not read `masks banded`")
    ca.cv_mbanded.set(False)
    ca._apply_course()
    if "masks" in ca.doc.text() or ca.doc.text() != text:
        bad.append("item 22: the Course tab's box cleared leaves %r" % ca.doc.text()[-80:])
    ca.cv_mbanded.set(True)
    ca._apply_course()
    if ca.doc.text().count("masks banded\n") != 1:
        bad.append("item 22: the Course tab's box set writes no `masks banded`")
    return bad


def partial_check(text):
    """item 23 (SPEC.md 130.58.46): a course the full rules refuse for a bound AFTER the cut (a block row's records,
    REC_ROW_MAX lowered) still writes occ.json - the rule's records and the shipped ones, needs, flags, the
    refusal - and the overlay loads it and says it was refused -> [problems]"""
    import bbedocc as O
    import json
    bad = []
    text = text + "# (item 23)\n"               # (its own compile: never a cached one)
    held = B.REC_ROW_MAX
    out = tempfile.mkdtemp()
    try:
        B.REC_ROW_MAX = 1
        p = os.path.join(out, "part.bbc")
        with open(p, "w") as f:
            f.write(text)
        _ws, err = J.occluders(p, out, "part.bbc")
    finally:
        B.REC_ROW_MAX = held
    if not err or "occluder records, over 1" not in err:
        return ["item 23: the lowered bound did not refuse: %r" % err]
    if not os.path.exists(os.path.join(out, "occ.json")):
        return ["item 23: a refusal after the cut wrote no occ.json (%s)" % err[:100]]
    with open(os.path.join(out, "occ.json")) as f:
        d = json.load(f)
    if d.get("refused") != err or not d["records"] or not d.get("shipped") or not d["cells"] or \
            not all(r["needs"] for r in d["shipped"]):
        bad.append("item 23: the partial occ.json holds %d rule, %d shipped records, %d cells, refused %r" % (
            len(d["records"]), len(d.get("shipped") or ()), len(d["cells"]), d.get("refused")))
    v = O.OccView.__new__(O.OccView)
    meta = {"width": 1, "lines": 1, "occ": {"error": err, "partial": True, "secs": 1.0}}
    v.app = _OccApp(text)
    v.app.pic = {"meta": meta}
    v.show, v.shade, v.which, v.sel = _Var(True), _Var(False), _Var("shipped"), None
    said = []
    v._say = said.append
    v.wanted = lambda: True
    v.loaded(out, meta)
    if v.data is None or not said or not said[-1].startswith("REFUSED, shown as cut") or "over 1" not in said[-1]:
        bad.append("item 23: the overlay on a refused cut says %r" % (said[-1:] or None))
    return bad


class _SelApp(_OccApp):
    """what the overlay's selection touches of the window, no Tk"""
    def __init__(self, text, c):
        _OccApp.__init__(self, text)
        ob = B.owners_canvas(c)
        self.pic["meta"].update(width=c.width, lines=c.lines)
        self.pic["owners"] = [o for row in ob for o in row]
        self.sel, self.sels, self.area, self.edits, self.msgs = None, [], None, 0, []

    def _edit(self, fn, *a, **kw):
        self.edits += 1
        return fn(*a, **kw)

    def _fill_inspector(self):
        pass

    def _redraw(self):
        pass

    def _msg(self, m):
        self.msgs.append(m)


def multi_check(c, od, text):
    """item 24 (SPEC.md 130.58.47): several occluder records selected - a rectangle, Ctrl-click in and out - and
    the union of the cells they hide made `noocclude` as ONE edit (one undo step); several noocclude cells selected
    and taken out as one -> [problems]"""
    import bbedocc as O
    bad = []
    v = O.OccView.__new__(O.OccView)
    v.app = _SelApp(text, c)
    v.data, v.flags = od, {(x, y): f for x, y, f in od["cells"]}
    v.noocc = set()
    v.show, v.shade, v.which, v.sel, v.drag = _Var(True), _Var(False), _Var("shipped"), None, None
    sh = od["shipped"]
    v.pick_rect(0, 0, c.width - 1, c.lines - 1)
    if not v.sel or v.sel[0] != "recs" or len(v.sel[1]) != len(sh):
        return ["item 24: a rectangle over the picture selected %r, not the %d shipped records" % (
            v.sel and (v.sel[0], len(v.sel[1]) if v.sel[0] == "recs" else v.sel[1]), len(sh))]
    if v.app.msgs[-1:] != ["%d occluder records selected" % len(sh)]:
        bad.append("item 24: the selection's count is not shown: %r" % v.app.msgs[-1:])
    ks = sorted(v.sel[1])[:3]
    v._set_sel("recs", {ks[0]})
    v.toggle("recs", ks[1])
    v.toggle("recs", ks[2])
    v.toggle("recs", ks[2])
    if v.sel != ("recs", frozenset(ks[:2])):
        bad.append("item 24: Ctrl-click in and out leaves %r, not records %r" % (v.sel, ks[:2]))
    v.pick_rect(0, 0, c.width - 1, c.lines - 1)
    cells, ok, back = v.sel_cells()
    want = {tuple(n) for r in sh for n in r["needs"]} - v.app.doc.in_play()
    if ok != want or back:
        bad.append("item 24: the selection offers %d cells to noocclude, not the union's %d" % (len(ok), len(want)))
    before = v.app.doc.text()
    v.noocclude(add=ok)
    have = set()
    for cs, _ln in v.app.doc.analysis()["src"].noocc:
        have |= set(cs)
    if v.app.edits != 1 or have != ok:
        bad.append("item 24: noocclude over the selection took %d edits, wrote %d of %d cells" % (
            v.app.edits, len(have), len(ok)))
    v.app.doc.undo()
    if v.app.doc.text() != before:
        bad.append("item 24: one Undo does not take the selection's noocclude back out")
    v.app.doc.redo()
    v.noocc = set(have)
    some = sorted(have)[:3]
    for cl in some:
        v.toggle("noocs", cl)
    if v.sel != ("noocs", frozenset(some)) or "%d noocclude cells selected" % len(some) not in v.app.msgs[-1]:
        bad.append("item 24: three noocclude cells Ctrl-clicked leave %r" % (v.sel,))
    v.noocclude(remove=set(some))
    left = set()
    for cs, _ln in v.app.doc.analysis()["src"].noocc:
        left |= set(cs)
    if v.app.edits != 2 or left != have - set(some):
        bad.append("item 24: the noocclude cells selected were not taken out in one edit")
    return bad


def main():
    bad = []
    bad += options_check()
    bad += flag_ball_check()
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
            bad += occ_ship_check(c, od, occ_course)     # 21. what ships (SPEC.md 130.58.44)
            bad += masks_check(occ_course)               # 22. over 256 masks (130.58.45)
            bad += partial_check(occ_course)             # 23. the cut shown on a refusal (130.58.46)
            bad += multi_check(c, od, occ_course)        # 24. several at once (130.58.47)
        finally:
            B.BLK_MAX = held
    except B.CourseError as e:
        bad.append("occ view: refused: %s" % str(e)[:150])
    bad += stranded_check()
    bad += mouth_check()
    bad += route_check()
    bad += course_tab_check()
    bad += route_lint_check()
    bad += stats_check()
    for b_ in bad:
        print("FAIL " + b_)
    print("t_bbedit: %d courses, %s" % (len(courses), "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
