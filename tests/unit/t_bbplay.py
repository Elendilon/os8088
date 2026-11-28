#!/usr/bin/env python3
"""t_bbplay - TEST ROLL's model and frame (SPEC.md 137.58.16), on the host, no Tk, no emulator:

 1. THE PLAY-ONLY COMPILE: MILL compiled with no occluders and the block limit lifted
    (bbplay.compile_play) leaves bbcourse.BLK_MAX as it found it, and the AUTOPILOT from the start
    steps to the goal on it in the same world state, step for step, as on the full compile;
 2. A SCRIPTED RUN from the start - arrows held, a Hop, a Grip, a RETURN (Backspace) - frame by frame
    at the card's refresh (bbplay.Roll), in the same world state on both compiles after every frame,
    with the RETURN counted and the ball moved;
 3. FROM A POKED CELL (--start): the ball placed on cell (14, 18) grounded, then the same script, the
    two compiles again equal after every frame;
 4. THE FRAME: composited without Tk (bbplay.Art.window) on the full compile, the camera window holds
    the ball's footprint and every pixel of the ball's sprite() frame sits at (px, py) - except the
    pixels the occluder pass lays back (laid_at, card=True), which show the picture; at least one
    frame of the autopilot's run has such pixels, so the occluder path is exercised; the Hercules
    translation (bbplay.to_herc) equals bonanza_assets.herc_pair pixel for pixel;
 5. THE DEMO: the scripted run saved as the game's log (BZR1, course K of BZ_COURSES, the full
    compile's identity) passes the guest's checks 1 - 8 (bbcourse.check_log) and replays through
    Physics.run_log from the start to the run's own end state;
 6. REWIND: a run rewound 5 s goes back 5 s to 5.5 s (a rewind point every 27 steps), and driven
    again with the same keys ends where it ended.

 7. THE PROPS' POSES (SPEC.md 137.58.48): TURN's turntable lanes drawn, each its own picture at its own
    place, in tt_pose at the physics' step, Heavy's drawn poses made stale on purpose (LAGGED: the stale);
 8. EVERY LANE OF MILL (windmills, clocks, posts, flags, seesaw, the jump, turntable cells) drawn in
    Heavy.pose_now at its own place, the ball poked beside each.
 9. THE AUTOPILOT (SPEC.md 137.58.50): a course whose last leg crosses a gap no Hop clears - no plan, so the
    search's furthest progress and the arrows on, ending the step before the fall, heading for way 2; Roll replays
    the keys to the bare replay's world state, way and cell (rewound and again, and on the full compile), the note
    names way 2, its cell, line and the fall, the way is ringed red; bridged, the planner's run finishes; plan_job
    reports a search line and writes the same keys. Red by hand (2026-11-23): Roll.frame not calling auto() (the
    Roll "heading for way 1"), autopilot_run playing the falling step ("timed out ... falls 6").

Red by hand (2026-11-23): Art.lane looking a lane up by the record's index (items 7 and 8); the default
pose Heavy's drawn one (item 7).
Red by hand (2026-11-21): Art.window drawing the ball at px + 1 (item 4: 'the ball's pixel ... is
not the frame's'); Roll.frame not appending the RETURN pulse to the run's keys (item 5: 'replays
to ... the run ended at'); compile_play leaving BLK_MAX lifted (item 1).
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["BB_CACHE"] = "0"                    # (writes nothing shared: no compile cache)
import bbcourse as B  # noqa: E402
import bonanza_assets as BA  # noqa: E402
import bbplay as P  # noqa: E402

MILL = os.path.join("apps", "bonanza", "courses", "mill.bbc")
SCRIPT = [(B.K_U, 40), (B.K_U | B.K_R, 30), (0, 20), (B.K_D | B.K_HOP, 25), (B.K_D, 30), ("ret", 1),
          (B.K_L | B.K_GRIP, 30), (B.K_R | B.K_D, 60), (0, 40)]


def drive(roll, script=SCRIPT, every=None):
    out = []
    for k, n in script:
        if k == "ret":
            roll.back_to_flag()
            k = 0
        for _ in range(n):
            roll.frame(k)
            if every:
                every(roll)
            out.append(P.wstate(roll.p))
    return out


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x[:8], y[:8]
    return None if len(a) == len(b) else (min(len(a), len(b)), "length", "length")


TURN = os.path.join("apps", "bonanza", "courses", "turntable.bbc")


def item7(bad):
    """TURN's tables from the start plate, frame by frame: in the default mode every turntable lane on the
    window is drawn - its own picture, at its own place - in tt_pose at the step the physics is on, even
    with Heavy's drawn poses made stale on purpose; LAGGED draws Heavy's (the stale) pose instead"""
    with open(os.path.join(ROOT, TURN), "r", encoding="ascii", newline="") as f:
        c = P.compile_play(f.read(), TURN)
    art = P.Art(c)
    roll = P.Roll(c, start=(9, 7))
    tts = [r for r in roll.p.props if r["kind"] == B.FAM_BY_NAME["turntable"]["kinds"][0]["kind"]]
    n = {"lanes": 0, "gaps": 0, "lagged": 0, "frames": 0}
    for fr in range(300):
        roll.frame(0)
        p, hv = roll.p, roll.g.heavy
        for r in tts:
            if hv.pose_now(r) != B.tt_pose(r, p.nstep & 255):
                bad.append("7: step %d: Heavy.pose_now(turntable %d) is %d, the physics' tt_pose %d"
                           % (p.nstep, r["i"], hv.pose_now(r), B.tt_pose(r, p.nstep & 255)))
                return
        stale = {r["i"]: hv.drawn.get(r["i"], 0) for r in tts}
        for r in tts:                           # (the guest's wheel a frame or more behind, on purpose)
            hv.drawn[r["i"]] = (B.tt_pose(r, p.nstep & 255) + 1) % 3
        for lagged in (False, True):
            win, (ox, oy) = art.window(roll, lagged=lagged)
            px = win.load()
            W, H = win.size
            near = lambda x, y: abs(x - p.px - 8) < 20 and abs(y - p.py - 8) < 28     # (the ball, its shadow)
            for r in tts:
                L = r["lane"]
                x0, y0 = 8 * L["col"] - ox, 8 * L["brow"] - oy
                if x0 < 0 or y0 < 0 or x0 + 8 * L["w"] > W or y0 + 8 * L["h"] > H:
                    continue
                q = hv.drawn[r["i"]] if lagged else B.tt_pose(r, p.nstep & 255)
                own = [M for M in c.lanes if tuple(M["rect"][:2]) == (L["col"], L["brow"])][0]
                want = art._pose(own, q) if q else None
                for y in range(8 * L["h"]):
                    for x in range(8 * L["w"]):
                        if near(x + x0 + ox, y + y0 + oy):
                            continue
                        w = want.getpixel((x, y)) if want and x < want.size[0] and y < want.size[1] else \
                            c.pic[y + y0 + oy][x + x0 + ox]
                        if px[x0 + x, y0 + y] != w:
                            bad.append("7: step %d (%s): turntable cell %s's lane is not drawn in pose %d at its "
                                       "own place - pixel (%d, %d) is %d, not %d"
                                       % (p.nstep, "lagged" if lagged else "default", tuple(r["at"]), q,
                                          x0 + x + ox, y0 + y + oy, px[x0 + x, y0 + y], w))
                            return
                if lagged:
                    n["lagged"] += 1
                else:
                    n["lanes"] += 1
                    n["gaps"] += q == 2
        for i, q in stale.items():
            hv.drawn[i] = q
        n["frames"] += 1
    if n["lanes"] < 1000 or n["gaps"] < 200:
        bad.append("7: only %d turntable lanes checked, %d of them open ports" % (n["lanes"], n["gaps"]))
    print("7: %d frames on TURN: %d turntable lanes drawn in the physics' pose (%d open ports), %d in the stale "
          "drawn pose when lagged" % (n["frames"], n["lanes"], n["gaps"], n["lagged"]))


def item8(bad, mill):
    """EVERY prop of MILL that has a lane, the ball poked beside it and rolled 60 frames on the autopilot:
    each lane on the window is drawn - its own picture, at its own place - in the pose Heavy.pose_now gives
    at that step (the physics'). The lane of a record is found through c.order (a record is in the part's
    order, a lane in the source's): looked up by the record's own index, 2 of MILL's 3 windmills, its
    seesaw, its life, every flag and clock and half its turntable cells drew ANOTHER prop's lane"""
    art = P.Art(mill)
    p0 = B.Physics(mill, play=True)
    own = {}                                    # (the test's own reading: a record's lane is the one AT its place)
    for r in p0.props:
        if r.get("lane"):
            own[r["i"]] = [L for L in mill.lanes if tuple(L["rect"][:2]) == (r["lane"]["col"], r["lane"]["brow"])
                           and L["kind"] == r["kind"]][0]
    want = {r["i"] for r in p0.props if r.get("lane") and r["kind"] != B.PK_GROUP}
    seen, changed = set(), set()
    for r0 in p0.props:
        if r0["i"] not in want or r0["i"] in seen:
            continue
        roll = None
        for dx, dy in ((0, 0), (-1, 0), (0, -1), (1, 0), (0, 1), (-2, 0), (0, -2)):
            try:
                roll = P.Roll(mill, start=(r0["at"][0] + dx, r0["at"][1] + dy))
                break
            except Exception:
                roll = None
        if roll is None:
            continue
        last = {}
        for _ in range(60):
            roll.frame(roll.p.auto())
            p, hv = roll.p, roll.g.heavy
            win, (ox, oy) = art.window(roll)
            px = win.load()
            W, H = win.size
            for r in p.props:
                if r["i"] not in want:
                    continue
                L = r["lane"]
                q = hv.pose_now(r)
                if last.setdefault(r["i"], q) != q:
                    changed.add(r["i"])
                x0, y0 = 8 * L["col"] - ox, 8 * L["brow"] - oy
                if x0 < 0 or y0 < 0 or x0 + 8 * L["w"] > W or y0 + 8 * L["h"] > H:
                    continue
                im = art._pose(own[r["i"]], q) if q else None
                for y in range(8 * L["h"]):
                    for x in range(8 * L["w"]):
                        gx, gy = x0 + x + ox, y0 + y + oy
                        if abs(gx - p.px - 8) < 20 and abs(gy - p.py - 8) < 28:
                            continue
                        w = im.getpixel((x, y)) if im and x < im.size[0] and y < im.size[1] else mill.pic[gy][gx]
                        if px[x0 + x, y0 + y] != w:
                            bad.append("8: step %d: MILL's %s at %s is not drawn in its physics pose %d at its own "
                                       "place - pixel (%d, %d) is %d, not %d" % (
                                           p.nstep, B.PK_NAMES.get(r["kind"], r["kind"]), tuple(r["at"]), q, gx, gy,
                                           px[x0 + x, y0 + y], w))
                            return
                seen.add(r["i"])
    kinds = sorted({B.PK_NAMES.get(r["kind"], r["kind"]) for r in p0.props if r["i"] in want})
    if want - seen:
        bad.append("8: %d of MILL's %d lanes never on the window: %s" % (
            len(want - seen), len(want), sorted(B.PK_NAMES.get(p0.props[i]["kind"]) for i in want - seen)))
    print("8: MILL: all %d of %d lanes checked in their physics pose at their own place (%s); %d changed pose "
          "while checked" % (len(seen & want), len(want), ", ".join(map(str, kinds)), len(changed)))


GAP = ('course V "v"\nwidth 128\nfloor rect 12 4 20 7 flat 4\nfloor rect 12 12 20 16 flat 4\n'
       'goal rect 17 14 19 16 flat 4\nstart 13 5\nway 13 5\nway 18 5\nway 18 14\n')
BRIDGE = "floor rect 12 7 20 12 flat 4\n"


def item9(bad):
    """THE AUTOPILOT (SPEC.md 137.58.50): on a course whose last leg crosses a gap no Hop clears, autopilot_run
    finds no plan and gives the search's furthest progress and the arrows on, ending the step before the fall,
    heading for way 2; Roll replays its keys frame by frame to that end - the world state a bare Physics replay
    has, the way it heads for, no fall - rewinds and replays again to it, and replays on the full compile; the
    note names the way, its cell and why; the route is drawn with the way it heads for ringed. Bridged, the run is
    the planner's and finishes. plan_job reports progress and writes the same run"""
    import io
    import contextlib
    import json
    import tempfile
    c = P.compile_play(GAP, "gap.bbc")
    w = {}
    r = B.autopilot_run(c, None, w)
    if (r["how"], r["reason"], r["goal"], r["wp"]) != ("partial", "fell", False, 2) or not w.get("pass"):
        bad.append("9: the gap's run is %r (passes %r), not partial / fell / way 2"
                   % ({k: v for k, v in r.items() if k != "keys"}, w.get("pass")))
        return
    pts = [B._way_point(c, (x, y)) for x, y, _ln in r["route"]]
    q = B.Physics(c, play=True)
    q.tsec = 0
    q.route = list(pts)
    for k in r["keys"]:
        q.auto()
        q.step(k)
    ro = P.Roll(c, script=r["keys"], route=pts)
    while not ro.script_over() and ro.nframe < 5000:
        ro.frame(0)
    end = P.wstate(ro.p)
    if len(ro.keys) != len(r["keys"]) or end != P.wstate(q):
        bad.append("9: the Roll's replay ends at %r after %d steps, a bare replay at %r after %d"
                   % (end[:8], len(ro.keys), P.wstate(q)[:8], len(r["keys"])))
    if ro.p.wp != r["wp"] or ro.p.nfall or [ro.p.gx >> 12, ro.p.gy >> 12] != r["cell"]:
        bad.append("9: the Roll ends heading for way %d, %d falls, at %r - the run said way %d at %r"
                   % (ro.p.wp, ro.p.nfall, [ro.p.gx >> 12, ro.p.gy >> 12], r["wp"], r["cell"]))
    ro.rewind()
    while not ro.script_over() and ro.nframe < 5000:
        ro.frame(0)
    if P.wstate(ro.p) != end:
        bad.append("9: rewound and replayed, the autopilot's run ends elsewhere")
    held, B.TRAP_CHECK = B.TRAP_CHECK, False        # (the builder's default: the goal no ball reaches is the point)
    try:
        full = P.compile_full(GAP, "gap.bbc")
    finally:
        B.TRAP_CHECK = held
    if P.wstate(ro.replay_on(full).p) != end:
        bad.append("9: the autopilot's run replayed on the full compile ends elsewhere")
    note = P.stuck_note(dict(r, branch=None))
    if "heading for way 2 of 2 at (18, 14), line 9" not in note or "falls off" not in note:
        bad.append("9: the note is %r" % note)
    art = P.Art(c)
    win, org = art.window(ro)
    im = P.to_rgb(win, P.palette(c.src))
    im = im.resize((3 * im.size[0], 3 * im.size[1]))
    nred = sum(1 for px in P.route_marks(im, ro, org, 3, 3).getdata() if px == (255, 40, 40))
    if not nred:
        bad.append("9: no red mark for the way the autopilot heads for")
    cb = P.compile_play(GAP + BRIDGE, "gap.bbc")
    rb = B.autopilot_run(cb)
    rr = P.Roll(cb, script=rb["keys"], route=[B._way_point(cb, (x, y)) for x, y, _l in rb["route"]])
    while not rr.script_over() and not rr.p.goal and rr.nframe < 5000:
        rr.frame(0)
    if (rb["how"], rb["goal"]) != ("plan", True) or not rr.p.goal or "it finishes" not in P.stuck_note(rb):
        bad.append("9: bridged, the run is %r and its Roll %s" % ((rb["how"], rb["goal"]),
                                                                  "finishes" if rr.p.goal else "does not finish"))
    with tempfile.TemporaryDirectory() as td:
        src, out = os.path.join(td, "gap.bbc"), os.path.join(td, "plan.json")
        with open(src, "w") as f:
            f.write(GAP)
        so = io.StringIO()
        with contextlib.redirect_stdout(so):
            rc = P.plan_job(src, out, "gap.bbc", every=0.02)
        lines = [json.loads(x) for x in so.getvalue().splitlines() if x.startswith("{")]
        got = json.load(open(out)) if rc == 0 and os.path.exists(out) else {}
        if rc or not any(x.get("stage") == "plan" for x in lines) or got.get("keys") != r["keys"]:
            bad.append("9: plan_job rc %d, stages %r, keys %s" % (rc, sorted({x.get("stage") for x in lines}),
                                                                   "the same" if got.get("keys") == r["keys"] else
                                                                   "DIFFERENT"))
    print("9: the gap's autopilot: %s, %d steps, %s heading for way %d; bridged: %s, %d steps, goal %s; red marks %d"
          % (r["how"], len(r["keys"]), r["reason"], r["wp"], rb["how"], len(rb["keys"]), rb["goal"], nred))


def main():
    bad = []
    with open(os.path.join(ROOT, MILL), "r", encoding="ascii", newline="") as f:
        text = f.read()
    held = B.BLK_MAX
    play = P.compile_play(text, MILL)
    if B.BLK_MAX != held:
        bad.append("1: compile_play left BLK_MAX at %d (was %d)" % (B.BLK_MAX, held))
    full = P.compile_full(text, MILL)

    # 1. the autopilot on both compiles
    def auto(c):
        p = B.Physics(c, play=True)
        tr = []
        while not p.goal and p.nstep < 4000:
            p.step_auto()
            tr.append(P.wstate(p))
        return tr
    ta, tb = auto(play), auto(full)
    d = first_diff(ta, tb)
    if d:
        bad.append("1: the autopilot differs at step %s: play-only %r, full %r" % d)
    if not tb or not tb[-1][10]:
        bad.append("1: the autopilot did not reach MILL's goal on the full compile (%d steps)" % len(tb))
    print("1: the autopilot reaches the goal in %d steps, the same on both compiles: %s" % (len(tb), not d))

    # 2. the scripted run from the start
    ra, rb = P.Roll(play), P.Roll(full)
    sa, sb = drive(ra), drive(rb)
    d = first_diff(sa, sb)
    if d:
        bad.append("2: the scripted run differs at frame %s: play-only %r, full %r" % d)
    p = rb.p
    if p.nret != 1:
        bad.append("2: the RETURN was counted %d times, not once" % p.nret)
    if p.nhop < 1:
        bad.append("2: no Hop in the scripted run")
    if (p.gx >> 12, p.gy >> 12) == tuple(rb.p.grid.start):
        bad.append("2: the ball ended on the start cell")
    print("2: %d frames, %d steps; hops %d, returns %d, falls %d; equal on both compiles: %s"
          % (rb.nframe, p.nstep, p.nhop, p.nret, p.nfall, not d))

    # 3. from a poked cell
    pa, pb = P.Roll(play, start=(14, 18)), P.Roll(full, start=(14, 18))
    if (pb.p.gx >> 12, pb.p.gy >> 12) != (14, 18) or pb.p.air:
        bad.append("3: the poke left the ball at cell (%d, %d), air %d" % (pb.p.gx >> 12, pb.p.gy >> 12, pb.p.air))
    d = first_diff(drive(pa), drive(pb))
    if d:
        bad.append("3: the poked run differs at frame %s: play-only %r, full %r" % d)
    print("3: poked at (14, 18); equal on both compiles: %s" % (not d))

    # 4. the frame
    art = P.Art(full)
    seen = {"frames": 0, "hidden": 0, "checked": 0}

    def under(roll, x, y):
        # what an occluder lays back: the picture, or a posed lane's pixel there (its own lane, by place)
        for r in roll.p.props:
            L = r.get("lane")
            if not L or not (8 * L["col"] <= x < 8 * (L["col"] + L["w"]) and 8 * L["brow"] <= y < 8 * (L["brow"] + L["h"])):
                continue
            q = P.pose(roll, r)
            M = [M for M in full.lanes if tuple(M["rect"][:2]) == (L["col"], L["brow"]) and M["kind"] == r["kind"]]
            im = art._pose(M[0], q) if q and M else None
            if im is not None and x - 8 * L["col"] < im.size[0] and y - 8 * L["brow"] < im.size[1]:
                return im.getpixel((x - 8 * L["col"], y - 8 * L["brow"]))
        return full.pic[y][x]

    def look(roll):
        q = roll.p
        if q.tube:
            return
        win, (ox, oy) = art.window(roll)
        W, H = win.size
        if not (ox <= q.px and q.px + 16 <= ox + W and oy <= q.py and q.py + 16 <= oy + H):
            bad.append("4: frame %d: the ball (%d, %d) is outside the window at (%d, %d)" % (roll.nframe, q.px,
                                                                                              q.py, ox, oy))
            return
        pix = win.load()
        hid = set()
        cl = q.cell(q.gx >> 12, q.gy >> 12)
        if cl[4] & (B.FL_OCC if q.air else B.FL_OCCG):
            hid = B.laid_at(full, q.px, q.py, q.sb, q.zb, q.oair, card=True, cell=B.mcell(q.gx, q.gy))
        fr = art.ball(q.mat, B.sprite(q, False))
        for (dx, dy), v in fr.items():
            x, y = q.px + dx, q.py + dy
            got = pix[x - ox, y - oy]
            if (x, y) in hid:
                want = under(roll, x, y)
                seen["hidden"] += 1
            else:
                want = v
            if got != want and not ((x, y) in hid and got == v == want):
                bad.append("4: frame %d: the ball's pixel (%d, %d) is %d, not the %s's %d"
                           % (roll.nframe, x, y, got, "picture" if (x, y) in hid else "frame", want))
                return
            seen["checked"] += 1
        seen["frames"] += 1
    rc = P.Roll(full)
    while not rc.p.goal and rc.p.nstep < 4000:
        k = rc.p.auto()
        rc.frame(k)
        if rc.nframe % 3 == 0:
            look(rc)
    if seen["frames"] < 100:
        bad.append("4: only %d frames composited" % seen["frames"])
    if not seen["hidden"]:
        bad.append("4: no frame of the autopilot's run had a ball pixel behind an occluder (the path is untested)")
    win, org = art.window(rc)
    h = P.to_herc(win, org)
    wp, hp = win.load(), h.load()
    nh = 0
    for y in range(win.size[1]):
        for x in range(win.size[0]):
            pr = BA.herc_pair(wp[x, y], org[1] + y, org[0] + x)
            nh += (hp[2 * x, y] == 255) != bool(pr & 2) or (hp[2 * x + 1, y] == 255) != bool(pr & 1)
    if nh:
        bad.append("4: the Hercules translation differs from herc_pair at %d pixels" % nh)
    print("4: %d frames composited, %d ball pixels checked, %d of them behind an occluder; Hercules pixels "
          "wrong: %d" % (seen["frames"], seen["checked"], seen["hidden"], nh))

    # 5. the demo
    K = P.course_number(os.path.join(ROOT, MILL))
    if K is None:
        bad.append("5: MILL is not in BZ_COURSES")
    else:
        log = rb.log(K, full.ident)
        idents = [0] * (K + 1)
        idents[K] = full.ident
        chk = B.check_log(log, K + 1, idents)
        if chk:
            bad.append("5: the saved log fails the guest's check %d: %s" % chk)
        why = P.check_saved(log, full, P.wstate(rb.p))
        if why:
            bad.append("5: " + why)
        print("5: a %d-byte log, course %d, identity %04Xh: check_log %s, replay %s"
              % (len(log), K, full.ident, chk or "ok", why or "ends where the run ended"))

    # 6. rewind
    r1 = P.Roll(full)
    drive(r1, SCRIPT * 3)
    end = P.wstate(r1.p)
    n0 = len(r1.keys)
    tail = r1.fsteps[:]
    r1.rewind()
    back = len(r1.keys)
    for ks in tail[len(r1.fsteps):]:
        r1.frame(0, steps=ks)
    if P.wstate(r1.p) != end:
        bad.append("6: rewound and driven again it ends at %r, not %r" % (P.wstate(r1.p)[:8], end[:8]))
    lo = int(P.REWIND_S * B.STEP_HZ)
    if not lo <= n0 - back <= lo + P.SNAP_STEPS + 8:
        bad.append("6: the rewind went back %d steps, not %d - %d" % (n0 - back, lo, lo + P.SNAP_STEPS + 8))
    print("6: rewound %d steps (%.2f s) and driven again: %s" % (n0 - back, (n0 - back) / B.STEP_HZ,
                                                                  "the same end" if P.wstate(r1.p) == end else "DIFFERENT"))

    # 7. the props' poses: what the ball meets (SPEC.md 137.58.48)
    item7(bad)
    item8(bad, full)
    item9(bad)                                  # 9. the autopilot (SPEC.md 137.58.50)

    for b in bad:
        print("FAIL " + b)
    print("t_bbplay: %s" % ("ok" if not bad else "%d failure(s)" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
