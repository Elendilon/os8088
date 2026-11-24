#!/usr/bin/env python3
"""bbplay - TEST ROLL, the course builder's player (SPEC.md 130.58.7, 130.58.16).

    python3 tools/bbplay.py COURSE.bbc [--start X Y] [--ball rubber|steel|glass] [--herc] [--name PATH]
                                       [--autopilot [--branch NAME]]

Plays a course on the host, on the game's own model: bbcourse's Physics (the
step the guest runs), Glide and Heavy (its camera and its props' drawn poses)
and sprite() / shadow() (the ball's frame and its shadow). No disk, no
emulator, no boot. The props are drawn in the pose the PHYSICS has (what the
ball meets); a checkbox draws them in Heavy's drawn poses instead, the XT's
(SPEC.md 130.58.48).

Two compiles run as processes as soon as the window opens:

  PLAY-ONLY  occluders off and the part's block limit lifted - under a second
             on MILL, about ten on PLAY. The ball rolls on it at once.
  FULL       the shipped compile (the occluders, the checks) - 3 s on MILL,
             two minutes or more on PLAY. When it lands the run so far is
             REPLAYED on it, the two end states are compared (the window says
             if they differ), and the window carries on on the full compile:
             the walls in front of the ball hide it as the card does, and the
             run's demo can be saved, because a .BZR names the shipped part's
             identity.

Keys: arrows roll, Space hops, Left Shift grips, Backspace goes back to the
last flag (the game's RETURN), P pauses, N steps one frame (one that holds a step) while paused,
1 / 2 / 4 set the speed (1, 1/2, 1/4), Z rewinds 5 s, R restarts, A runs the autopilot, Esc closes.

AUTOPILOT (--autopilot [--branch NAME], the A key or its button; SPEC.md 130.58.50)
replays what the planner plays: route_plan's keys (branch_plan's for a branch),
or - when it finds no route - its furthest partial route and 130.6's arrows on
from there, ending where the ball gets stuck, with a note naming the way it
was heading for, the step and why (it fell, stalled or timed out). The planning
runs as a job of its own (--job plan), its progress on the note line; the
route and the way it heads for are drawn over the frame.

Needs Tk and Pillow (no PIL.ImageTk: pictures reach Tk as PNG bytes).
The model half (Roll, Art) needs no Tk and is what tests/unit/t_bbplay.py drives.
"""

import base64
import copy
import io
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbcourse as B  # noqa: E402
import bonanza_assets as BA  # noqa: E402

SNAP_STEPS = 27                 # a rewind point every 27 steps (0.49 s); a snapshot is ~0.5 ms (130.58.16)
REWIND_S = 5.0
SPEEDS = (1.0, 0.5, 0.25)


def palette(src):
    """the course's CGA colours (SPEC.md 130.16.6): its `palette` byte, else palette 1 bright - the same
    reading as bbedjob's picture job"""
    b = src.palette[0] if src.palette else B.PAL_DEFAULT
    bright = bool(b & 0x10)
    if b & 0x40:                                # palette 2: mode 5's (the B/W bit), cyan, red, white
        cols = [(85, 255, 255), (255, 85, 85), (255, 255, 255)] if bright else \
               [(0, 170, 170), (170, 0, 0), (170, 170, 170)]
    elif b & 0x20:
        cols = [(85, 255, 255), (255, 85, 255), (255, 255, 255)] if bright else \
               [(0, 170, 170), (170, 0, 170), (170, 170, 170)]
    else:
        cols = [(85, 255, 85), (255, 85, 85), (255, 255, 85)] if bright else \
               [(0, 170, 0), (170, 0, 0), (170, 85, 0)]
    return [(0, 0, 0)] + cols


# ----------------------------------------------------------------------------
# the compiles (SPEC.md 130.58.16.1)
# ----------------------------------------------------------------------------

def compile_play(text, name):
    """the PLAY-ONLY compile: no occluders, the block limit lifted for this call alone. What Physics reads
    is the full compile's (130.58.16.1: every cell's kind, heights, slopes, surface and the SAFE, OBS and
    exit flags, the start, the route, the props' world fields); what it is not is a part that ships - its
    picture's Y0, the occluder flags and records, the prop records' order and its identity differ"""
    held = B.BLK_MAX
    B.BLK_MAX = 1 << 30
    try:
        return B.compile_course(text, name, occluders=False)
    finally:
        B.BLK_MAX = held


def compile_full(text, name):
    return B.compile_course(text, name)


def save_course(c, out):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(out)), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        B._dump(c, f, B._globals_ids())
    os.replace(tmp, out)


def load_course(path):
    import pickle
    with open(path, "rb") as f:
        up = pickle.Unpickler(f)
        up.persistent_load = B._resolve
        return up.load()


def job(mode, path, out, name):
    """the child process: compile, pickle the Course to OUT, report a JSON line"""
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    try:
        c = (compile_play if mode == "play" else compile_full)(text, name or path)
    except B.CourseError as e:
        print(json.dumps({"stage": "done", "ok": False, "error": str(e), "secs": round(time.time() - t0, 2)}))
        return 1
    save_course(c, out)
    print(json.dumps({"stage": "done", "ok": True, "out": out, "secs": round(time.time() - t0, 2)}))
    return 0


def plan_job(path, out, name, branch=None, every=0.5):
    """the AUTOPILOT's job (SPEC.md 130.58.50): the play-only compile and bbcourse.autopilot_run on it - the
    search watched (PLAN_WATCH) from the compile on, since the compile's own limit may run the main route's
    search, so it is searched once - a progress line every EVERY seconds, the run's JSON to OUT"""
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    w = {}
    main = sum(1 for ln in text.splitlines() if ln.split("#")[0].split()[:1] == ["way"] and "branch" not in ln.split())
    state = {"stage": "compile", "nways": None if branch else main, "done": False}
    lock = threading.Lock()

    def say(**kw):
        with lock:
            print(json.dumps(kw), flush=True)

    def tick():
        while not state["done"]:
            time.sleep(every)
            if state["done"]:
                break
            sp, best = w.get("spent"), w.get("best")
            if sp is None or state["nways"] is None:    # (a branch's: the compile's own main-route search first)
                say(stage="compile", what="compiling the course (play-only)", secs=round(time.time() - t0, 1))
            else:
                say(stage="plan", what="searching", passes=w.get("pass", 0), spent=sp[0], budget=B.PLAN_BUDGET,
                    best=best[1] if best else None, nways=state["nways"], secs=round(time.time() - t0, 1))
    threading.Thread(target=tick, daemon=True).start()
    held = B.PLAN_WATCH
    B.PLAN_WATCH = w
    try:
        try:
            c = compile_play(text, name or path)
        finally:
            B.PLAN_WATCH = held
        if not c.src.ways:
            raise B.CourseError("the course has no route (no `way` lines): the autopilot has nothing to steer by")
        if branch is not None and branch not in c.branches:
            raise B.CourseError("the course has no branch %s" % branch)
        state["nways"] = len(c.src.ways) if branch is None else len(B.branch_route(c, branch))
        r = B.autopilot_run(c, branch, w)
    except B.CourseError as e:
        state["done"] = True
        say(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 2))
        return 1
    state["done"] = True
    r["branch"] = branch
    with open(out, "w") as f:
        json.dump(r, f)
    say(stage="done", ok=True, out=out, how=r["how"], goal=r["goal"], secs=round(time.time() - t0, 2))
    return 0


def stuck_note(r, step_hz=None):
    """SPEC.md 130.58.50: the autopilot run's end in words - where it finished, or which way it was heading for
    (its number, cell and line), the step and why it stopped"""
    step_hz = step_hz or B.STEP_HZ
    route = r["route"]
    n = len(route)
    where = "branch %s" % r["branch"] if r.get("branch") else "the main route"
    how = {"plan": "the planner's route (route_plan)" if not r.get("branch") else "the planner's route (branch_plan)",
           "partial": "the planner found NO route: its furthest progress, then the arrows alone",
           "arrows": "the planner found NO route and no progress: the arrows alone from the start"}[r["how"]]
    if r["goal"]:
        return "AUTOPILOT, %s: %s - it finishes, %d steps (%.1f s)" % (where, how, r["step"], r["step"] / step_hz)
    wx, wy, ln = route[r["wp"]]
    why = {"fell": "it falls off on the next step", "stalled": "it stalls - no progress for %d steps"
           % B.PLAN_STALL, "timed out": "it times out - %d steps on this leg without reaching the way" % B.PLAN_SEG,
           "shattered": "the glass ball shatters", None: "the keys run out"}.get(r["reason"], r["reason"])
    return ("AUTOPILOT STUCK, %s: %s.  Step %d (%.1f s): heading for way %d of %d at (%d, %d), line %d; the ball "
            "at cell (%d, %d); %s" % (where, how, r["step"], r["step"] / step_hz, r["wp"], n - 1, wx, wy, ln,
                                     r["cell"][0], r["cell"][1], why))


def route_marks(im, roll, origin, sx, sy):
    """SPEC.md 130.58.50: the route the autopilot steers drawn over the frame - its legs (taken ones dim), a ring
    at each way and the way it heads for now ringed in red and numbered.  IM: RGB, SX x SY per game pixel"""
    from PIL import ImageDraw
    pts, wp = roll.p.route, roll.p.wp
    ox, oy = origin
    xy = [(((x & ~1) + 8 - ox) * sx, (y + 13 - oy) * sy) for x, y in pts]
    dr = ImageDraw.Draw(im)
    lw = max(2, sx - 1)
    for i in range(1, len(xy)):                 # (a dark under-stroke, so the line reads on any ground)
        dr.line([xy[i - 1], xy[i]], fill=(0, 0, 0), width=lw + 2)
    for i in range(1, len(xy)):
        dr.line([xy[i - 1], xy[i]], fill=(120, 120, 120) if i < wp else (255, 230, 0), width=lw)
    for i, (x, y) in enumerate(xy):
        r = 2 * sx
        dr.ellipse([x - r, y - r // 2, x + r, y + r // 2], outline=(0, 0, 0), width=lw + 2)
        dr.ellipse([x - r, y - r // 2, x + r, y + r // 2], outline=(120, 120, 120) if i < wp else (255, 230, 0),
                   width=lw)
    if 0 <= wp < len(xy):
        x, y = xy[wp]
        W, H = im.size
        if 0 <= x < W and 0 <= y < H:
            r = 5 * sx
            dr.ellipse([x - r, y - r // 2, x + r, y + r // 2], outline=(0, 0, 0), width=lw + 4)
            dr.ellipse([x - r, y - r // 2, x + r, y + r // 2], outline=(255, 40, 40), width=lw + 1)
            tx, ty = x + r + 4, y - 7
        else:                                   # (off the frame: an arrow at its edge, toward it)
            cx, cy = min(max(x, 14), W - 15), min(max(y, 14), H - 15)
            dx, dy = x - cx, y - cy
            n = max(abs(dx), abs(dy), 1)
            ux, uy = 12.0 * dx / n, 12.0 * dy / n
            dr.polygon([(cx + ux, cy + uy), (cx - uy / 2, cy + ux / 2), (cx + uy / 2, cy - ux / 2)],
                       fill=(255, 40, 40), outline=(0, 0, 0))
            tx, ty = min(max(cx - 30, 2), W - 70), min(max(cy - 24 if cy > H / 2 else cy + 14, 2), H - 14)
        label = "way %d" % wp
        for ddx, ddy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            dr.text((tx + ddx, ty + ddy), label, fill=(0, 0, 0))
        dr.text((tx, ty), label, fill=(255, 80, 80))
    return im


# ----------------------------------------------------------------------------
# the run (no Tk)
# ----------------------------------------------------------------------------

def wstate(p):
    """the world state a replay must reproduce: Physics.state(), state2() and the run's counters"""
    return p.state() + p.state2() + (p.nfall, p.nret, p.goal, p.cksn, p.tsec, p.mat)


class Roll:
    """one run of a course at the card's refresh (CARD_HZ, a frame's steps from the accumulator exactly as
    glide_run counts them, the first frame's discarded), the camera after each frame's steps"""

    def __init__(self, course, mat=None, herc=False, start=None, script=None, route=None):
        self.c = course
        self.mat = course.ball if mat is None else mat
        self.herc = herc
        self.start = tuple(start) if start else None
        self.script = script            # SPEC.md 130.58.50: the AUTOPILOT's keys, step by step from the start
        self.route = route              # ...and the way points it steers (a branch's), for its next way
        self.spf = (B.PIT_HZ / B.CARD_HZ[herc]) / B.STEP_PIT
        self.reset()

    def reset(self):
        p = B.Physics(self.c, play=True, mat=self.mat)
        if self.script is not None:     # (the planner's run: no course limit, as route_plan steps it)
            p.tsec = 0
            if self.route is not None:
                p.route = list(self.route)
        if self.start:
            p.poke(*self.start)
        g = B.Glide(p, self.herc, self.c.brows, self.c.cols, heavy=B.Heavy(p))
        p.glide = g
        self.p, self.g = p, g
        self.acc = 0.0
        self.nframe = 0
        self.keys = []                  # every step's key byte: the run's log
        self.fsteps = []                # every frame's steps' key bytes (a replay's frames)
        self.snaps = []
        self.ret = False                # a RETURN pulse for the next step (Backspace)
        self.frame(0)

    def _memo(self):
        return {id(self.c): self.c, id(self.p.grid): self.p.grid}

    def frame(self, K, steps=None):
        """one frame: its steps, each with K (plus a pending RETURN on the first), then the camera.
        steps: a replay's own key bytes for the frame"""
        self.acc += self.spf
        n = int(self.acc)
        self.acc -= n
        n = min(n, 8)
        if self.nframe == 0:
            n = 0
        if steps is not None:
            assert len(steps) == n, "a replayed frame's steps (%d) are not the accumulator's (%d)" % (len(steps), n)
        ks = []
        for i in range(n):
            if self.script is not None and steps is None:
                j = len(self.keys) + i          # (the script's step: rewind and restart follow len(keys))
                if j >= len(self.script):
                    break                       # (the script is over: where the autopilot got stuck)
                k = self.script[j]
                self.p.auto()                   # (only its way moves: the way it heads for, for the marks)
            else:
                k = steps[i] if steps is not None else K
            if steps is None and self.ret:
                k |= B.K_RET
                self.ret = False
            self.p.step(k)
            ks.append(k)
            if self.p.nstep % SNAP_STEPS == 0:
                self.snaps.append((self.p.nstep, None))     # (taken once the frame's camera has run)
        self.keys += ks
        self.fsteps.append(tuple(ks))
        self.g.camera()
        self.nframe += 1
        if self.snaps and self.snaps[-1][1] is None:
            self.snaps[-1] = (self.p.nstep, self._snap())
        return len(ks)

    def script_over(self):
        """SPEC.md 130.58.50: the autopilot's keys all stepped"""
        return self.script is not None and len(self.keys) >= len(self.script)

    def _snap(self):
        return copy.deepcopy((self.p, self.g, self.acc, self.nframe, len(self.keys), len(self.fsteps)),
                             self._memo())

    def rewind(self, secs=REWIND_S):
        """back to the last rewind point at least SECS before now (the start if there is none)"""
        want = self.p.nstep - int(secs * B.STEP_HZ)
        while self.snaps and (self.snaps[-1][0] > want or self.snaps[-1][1] is None):
            self.snaps.pop()
        if not self.snaps:
            self.reset()
            return
        p, g, acc, nf, nk, nfs = copy.deepcopy(self.snaps[-1][1], self._memo())
        self.p, self.g, self.acc, self.nframe = p, g, acc, nf
        p.glide = g
        del self.keys[nk:]
        del self.fsteps[nfs:]
        self.ret = False

    def back_to_flag(self):
        self.ret = True

    def replay_on(self, course):
        """this run's frames replayed on another compile of the course -> the new Roll (its world state is
        compared by the caller)"""
        r = Roll(course, self.mat, self.herc, self.start, self.script, self.route)
        if self.script is not None:             # (the autopilot's: its own keys, frame by frame, as far as this)
            while r.nframe < self.nframe:
                r.frame(0)
            return r
        for ks in self.fsteps[1:]:
            r.frame(0, steps=ks)
        return r

    # the readout
    def flags(self):
        return bin(self.p.cksn).count("1"), len(self.p.flags_at)

    def seconds(self):
        return self.p.nstep / B.STEP_HZ

    # the demo (SPEC.md 130.11.12, 130.14.7)
    def log(self, K, ident):
        """the run as the game's log: BZR1, course K, the run's ball, complete when the goal was reached"""
        return B.encode_log(self.keys, K, self.mat, bool(self.p.goal), ident)


def course_number(name):
    """the course's K in BZ_COURSES (the game's course list, bbcourse.default_paths), or None"""
    try:
        paths = [os.path.normcase(os.path.abspath(p)) for p in B.default_paths()]
    except (SystemExit, Exception):
        return None
    me = os.path.normcase(os.path.abspath(name))
    return paths.index(me) if me in paths else None


def check_saved(log, course, end):
    """a saved log replayed through the host model from the course's start (Physics.run_log) -> None when
    it ends in END (wstate), else why not"""
    _K, mat, _ks, _fl = B.decode_log_t(log)
    q = B.Physics(course, play=True, mat=mat).run_log(log)
    got = wstate(q)
    return None if got == end else "the saved log replays to %r, the run ended at %r" % (got[:8], end[:8])


# ----------------------------------------------------------------------------
# the frame (no Tk): the compositor, SPEC.md 130.58.16.2
# ----------------------------------------------------------------------------

def pose(roll, r, lagged=False):
    """the pose the Test Roll draws prop record R's lane in (SPEC.md 130.58.48): by default the one the
    PHYSICS has after the frame's steps (Heavy.pose_now), so a turntable's port is open on the glass exactly
    when the ball would drop through it; LAGGED, Heavy's DRAWN pose - the guest's lane wheel, which may draw a
    lane a few frames late to spread a frame's drawing (the look on the XT). A group lane is its members' pose
    either way (the guest draws the group with them)"""
    p, hv = roll.p, roll.g.heavy
    if r["kind"] == B.PK_GROUP:
        return p.fpose(r)
    if hv is None:
        return 0
    return hv.drawn.get(r["i"], 0) if lagged else hv.pose_now(r)


def _rows_dict(rows):
    return {(x, y): v for y, r in enumerate(rows) for x, v in enumerate(r) if v is not None and v != BA.SEE}


class Art:
    """a course's frame pieces: the picture as an image, the lanes' poses, the ball's frames"""

    def __init__(self, course):
        from PIL import Image
        self.Image = Image
        c = self.c = course
        self.base = Image.frombytes("P", (c.width, c.lines), b"".join(bytes(r) for r in c.pic))
        self.lanes = {L["prop"]: L for L in c.lanes}
        self.posed = {}
        self.frames = {}
        self.slab = B.slab_pixels()
        self.records = bool(getattr(c, "by_block", None))

    def _pose(self, L, q):
        key = (L["prop"], q)
        im = self.posed.get(key)
        if im is None and q in L["pics"]:
            rows = L["pics"][q]
            w = max(len(r) for r in rows) if rows else 0
            im = self.Image.frombytes("P", (w, len(rows)), b"".join(bytes(r).ljust(w, b"\0") for r in rows))
            self.posed[key] = im
        return im

    def ball(self, mat, spr):
        """{(dx, dy): index} of a sprite() frame, relative to the ball's top-left"""
        key = (mat, spr)
        d = self.frames.get(key)
        if d is None:
            kind, k = spr
            if kind == "roll":
                d = _rows_dict(BA.material_frame(mat, k & 7, k >> 3))
            elif kind == "squash":
                d = _rows_dict(BA.squash_frame(mat, k))
            elif kind == "stretch":
                d = _rows_dict(BA.stretch_frame(mat))
            elif mat == B.MAT_GLASS:
                d = {q: v for q, v in BA.shatter_frame(min(k, BA.NSH - 1)).items() if v != BA.SEE}
            elif mat == B.MAT_RUBBER:
                d = dict(BA.pop_frame(min(BA.NPOP, k + 1)))
            else:
                d = _rows_dict(BA.material_frame(mat, 0, 0))
            self.frames[key] = d
        return d

    def lane(self, r):
        """the lane of Physics' prop record R. A record's index is the PART's (raster) order, a lane's "prop"
        the course's SOURCE order, and c.order maps the one to the other (SPEC.md 130.58.48)"""
        if not r.get("lane"):
            return None
        o = self.c.order
        return self.lanes.get(o[r["i"]] if r["i"] < len(o) else None)

    def window(self, roll, lagged=False):
        """-> (the window as a 'P' image of palette indices, its picture origin (x, y)). Each lane in the pose
        the PHYSICS has after the frame's steps (Heavy.pose_now: what the ball meets); LAGGED, in Heavy's drawn
        pose instead (the guest's lane wheel, which can draw a lane a few frames late: the look on the XT)"""
        p, g = roll.p, roll.g
        W = g.W * 8
        ox, oy = 8 * g.c0, g.R0 * g.rl
        win = self.base.crop((ox, oy, ox + W, oy + B.WIN_LINES))
        hv = g.heavy
        tlp = {}                                # SPEC.md 130.42.15: each see-saw lane's DRAWN pose, for laid_at
        for r in p.props:
            L = self.lane(r)
            if L is None:
                continue
            q = pose(roll, r, lagged)
            if L.get("kind") == B.FK_TILTL:
                tlp[L["prop"]] = q or 0
            if not q:
                continue
            bx, by, _w, _h = L["rect"]
            im = self._pose(L, q)
            if im is not None:
                win.paste(im, (8 * bx - ox, 8 * by - oy))
        px = win.load()
        Wd, Hd = win.size

        def put(x, y, v):
            x -= ox
            y -= oy
            if 0 <= x < Wd and 0 <= y < Hd:
                px[x, y] = v
        for r in p.props:                       # the lift's slab, at its drawn line
            if r["kind"] == B.PK_PLATFORM and hv is not None and r["i"] == hv.trk:
                x_l, y_t = B.slab_xy(r, B.plat_pos(r, p.nstep & 0xFFFF) >> 8, p.x0, p.y0)
                y_t = hv.pline.get(r["i"], y_t)
                for (x, y), v in self.slab.items():
                    put(x_l + x, y_t + y, v)
        if p.tube:                              # inside a tube the ball is not drawn
            return win, (ox, oy)
        x4 = p.px & ~3
        under = {(x, y): (px[x - ox, y - oy] if 0 <= x - ox < Wd and 0 <= y - oy < Hd else 0)
                 for y in range(p.py, p.py + B.FOOT_H) for x in range(x4, x4 + B.FOOT_W)}
        sh = B.shadow(p)
        if sh:
            spy, spx = sh
            for yy in range(BA.SHD_ROWS):
                for xx in range(BA.D):
                    if BA._shadow_in(xx, yy) and (spx + xx + spy + yy) & 1 == 0:
                        put(spx + xx, spy + yy, BA.BLK)
        for (dx, dy), v in self.ball(p.mat, B.sprite(p, roll.herc)).items():
            put(p.px + dx, p.py + dy, v)
        if self.records:                        # the occluders, where the guest's pass runs (the OCC gate)
            cl = p.cell(p.gx >> 12, p.gy >> 12)
            if cl[4] & (B.FL_OCC if p.air else B.FL_OCCG):
                for (x, y) in B.laid_at(self.c, p.px, p.py, p.sb, p.zb, p.oair, card=True,
                                        cell=B.mcell(p.gx, p.gy), poses=tlp if tlp else None):
                    if (x, y) in under:
                        put(x, y, under[(x, y)])
        return win, (ox, oy)


def to_rgb(win, pal):
    im = win.copy()
    im.putpalette([v for c in pal for v in c] + [0] * (768 - 3 * len(pal)))
    return im.convert("RGB")


_HCACHE = {}


def _herc_masks(w, h, par):
    """(the parity image: 4 where (x + y + par) is odd; the odd-column mask, 2w wide), cached"""
    from PIL import Image
    key = (w, h, par)
    m = _HCACHE.get(key)
    if m is None:
        row0 = bytes(4 * ((x + par) & 1) for x in range(w + 1))
        pim = Image.frombytes("L", (w, h), b"".join(row0[y & 1:(y & 1) + w] for y in range(h)))
        odd = Image.frombytes("L", (2 * w, h), bytes(255 * (x & 1) for x in range(2 * w)) * h)
        m = _HCACHE[key] = (pim, odd)
    return m


def to_herc(win, origin):
    """the window's indices through the Hercules translation (bonanza_assets.herc_pair): each game pixel two
    card pixels, the mid level 10 / 01 by (line + column) - 2x as wide, 'L' 0 / 255"""
    from PIL import Image, ImageChops
    w, h = win.size
    ox, oy = origin
    pim, odd = _herc_masks(w, h, (ox + oy) & 1)
    code = ImageChops.add(Image.frombytes("L", (w, h), win.tobytes()), pim)     # index + 4 x parity
    left = code.point([0, 255, 255, 255, 0, 0, 0, 255] + [0] * 248)
    right = code.point([0, 0, 0, 255, 0, 255, 255, 255] + [0] * 248)
    return Image.composite(right.resize((2 * w, h), Image.NEAREST), left.resize((2 * w, h), Image.NEAREST), odd)


# ----------------------------------------------------------------------------
# the window
# ----------------------------------------------------------------------------

class _Proc(object):
    def __init__(self, argv):
        self.q = queue.Queue()
        kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                  encoding="utf-8", errors="replace", bufsize=1)
        if sys.platform == "win32":
            kw["creationflags"] = 0x00000200 | 0x08000000
        else:
            kw["start_new_session"] = True
        self.p = subprocess.Popen(argv, **kw)
        self.progress = None            # the job's latest line short of its result (SPEC.md 130.58.50: the planning)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        last = None
        for line in self.p.stdout:
            try:
                last = json.loads(line)
            except ValueError:
                continue
            if last.get("stage") != "done":
                self.progress = last
        err = self.p.stderr.read()
        self.p.wait()
        self.q.put(last if last and last.get("stage") == "done" else
                   {"stage": "done", "ok": False, "error": (err.strip().splitlines() or ["no result"])[-1]})

    def result(self):
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None

    def kill(self):
        if self.p.poll() is None:
            try:
                if sys.platform == "win32":
                    self.p.kill()
                else:
                    os.killpg(self.p.pid, 9)
            except OSError:
                pass


class Player(object):
    KEYS = {"Left": B.K_L, "Right": B.K_R, "Up": B.K_U, "Down": B.K_D, "space": B.K_HOP, "Shift_L": B.K_GRIP}

    def __init__(self, path, name, start, mat, herc, autopilot=False, branch=None):
        import tkinter as tk
        self.tk = tk
        self.name = name or path
        self.start, self.mat, self.herc = start, mat, herc
        self.branch = branch            # SPEC.md 130.58.50: the AUTOPILOT's route (a branch's, else the main one)
        self.jplan = None               # ...its planning job, the run it gave (autopilot_run's), its end in words
        self.plan = self.plan_err = None
        self.stuck = None
        if autopilot:
            start = self.start = None   # (the planner's run is from the course's start)
        with open(path, "r", encoding="ascii", newline="") as f:
            text = f.read()
        self.tmp = tempfile.mkdtemp(prefix="bbplay")
        self.src = os.path.join(self.tmp, "course.bbc")
        with open(self.src, "w", encoding="ascii", newline="") as f:
            f.write(text)
        self.t0 = time.time()
        self.roll = self.art = None
        self.full = None                # the full compile, once it lands (or its refusal)
        self.full_note = "the full compile is running: walls do not hide the ball yet, and Save waits for it"
        self.mismatch = None
        self.held = {}
        self.pressed = {}
        self.paused = False
        self.ended = False              # the goal or the time-out paused the run once
        self.speed = 1.0
        self.gacc = 0.0
        self.last = None
        self.photo = None

        r = self.r = tk.Tk()
        r.title("Test Roll - %s" % os.path.basename(self.name))
        r.configure(background="#202020")
        box = tk.Frame(r, background="black", width=960 if not herc else 720, height=600 if not herc else 400)
        box.pack(side="top", padx=8, pady=8)
        box.pack_propagate(False)
        self.view = tk.Label(box, background="black", text="compiling %s ..." % os.path.basename(self.name),
                             foreground="white", font=("TkDefaultFont", 16), compound="center", wraplength=900,
                             borderwidth=0, highlightthickness=0)      # (the picture fills the box exactly)
        self.view.pack(fill="both", expand=True)
        self.read = tk.Label(r, text="", anchor="w", justify="left", background="#202020", foreground="#e0e0e0",
                             font=("TkFixedFont", 12))
        self.read.pack(side="top", fill="x", padx=8)
        self.note = tk.Label(r, text="", anchor="w", justify="left", background="#202020", foreground="#f0c040",
                             wraplength=940)
        self.note.pack(side="top", fill="x", padx=8)
        bar = tk.Frame(r, background="#202020")
        bar.pack(side="top", fill="x", padx=8, pady=6)
        for label, fn in (("Pause (P)", self.toggle_pause), ("Step (N)", self.step_once), ("1x", lambda: self.set_speed(1.0)),
                          ("1/2x", lambda: self.set_speed(0.5)), ("1/4x", lambda: self.set_speed(0.25)),
                          ("Rewind 5 s (Z)", self.rewind), ("Back to flag (Backspace)", self.back),
                          ("Restart (R)", self.restart), ("Autopilot (A)", self.start_autopilot),
                          ("Save demo...", self.save_demo), ("Close", self.close)):
            tk.Button(bar, text=label, command=fn).pack(side="left", padx=2)
        # SPEC.md 130.58.50: the autopilot's route and the way it heads for, over the frame
        self.marks = tk.BooleanVar(r, value=bool(autopilot))
        tk.Checkbutton(r, text="Show the route the autopilot steers (and the way it heads for)", variable=self.marks,
                       command=self._redraw, anchor="w", background="#202020", foreground="#e0e0e0",
                       selectcolor="#404040", activebackground="#202020",
                       activeforeground="#ffffff").pack(side="top", fill="x", padx=8)
        # SPEC.md 130.58.48: the props in the physics' pose (what the ball meets) unless this is ticked
        self.lagged = tk.BooleanVar(r, value=False)
        tk.Checkbutton(r, text="Draw the props as the XT would (lagged: the guest's lane wheel may draw a lane "
                       "a few frames late)", variable=self.lagged, command=self._redraw, anchor="w",
                       background="#202020", foreground="#e0e0e0", selectcolor="#404040",
                       activebackground="#202020", activeforeground="#ffffff").pack(side="top", fill="x", padx=8)
        r.bind("<KeyPress>", self.kdown)
        r.bind("<KeyRelease>", self.kup)
        r.protocol("WM_DELETE_WINDOW", self.close)
        me = [sys.executable, "-u", os.path.abspath(__file__), "--job"]
        self.jplay = _Proc(me + ["play", self.src, os.path.join(self.tmp, "play.pkl"), "--name", self.name])
        self.jfull = _Proc(me + ["full", self.src, os.path.join(self.tmp, "full.pkl"), "--name", self.name])
        if autopilot:
            self.start_autopilot()
        self.r.after(20, self.tick)

    # -- the autopilot (SPEC.md 130.58.50)
    def start_autopilot(self):
        """plan the autopilot's run in a job of its own (it can take tens of seconds) - or, planned already,
        replay it again from the start"""
        if self.plan is not None:
            self._autoroll()
            return
        if self.jplan is not None:
            return
        me = [sys.executable, "-u", os.path.abspath(__file__), "--job"]
        self.plan_err = None
        self.jplan = _Proc(me + ["plan", self.src, os.path.join(self.tmp, "plan.json"), "--name", self.name] +
                           (["--branch", self.branch] if self.branch else []))
        if self.roll is not None:               # (the course at its start, paused, while the planner works)
            self.roll = Roll(self.roll.c, self.mat, self.herc)
            self.paused = True

    def _autoroll(self):
        c = self.roll.c if self.roll is not None else (self.full if isinstance(self.full, B.Course) else None)
        if c is None or self.plan is None:
            return
        pts = [B._way_point(c, (x, y)) for x, y, _ln in self.plan["route"]]
        self.roll = Roll(c, None, self.herc, None, script=self.plan["keys"], route=pts)
        self.start = None
        self.ended = self.paused = False
        self.stuck = None
        self.gacc = 0.0
        self.draw()

    def _plan_arrived(self):
        if self.jplan is None or self.plan is not None:
            return
        res = self.jplan.result()
        if res is None:
            return
        self.jplan = None
        if not res.get("ok"):
            self.plan_err = "the autopilot could not run: %s" % res.get("error", "?")
            return
        with open(res["out"]) as f:
            self.plan = json.load(f)
        self._autoroll()

    def _plan_progress(self):
        """the planning job's line, in words"""
        if self.jplan is None:
            return None
        pr = self.jplan.progress or {}
        if pr.get("stage") == "plan":
            best = pr.get("best")
            return ("AUTOPILOT: planning the %s - pass %d, %d of %d steps searched%s (%.0f s)" % (
                "branch %s" % self.branch if self.branch else "main route", pr.get("passes", 0), pr.get("spent", 0),
                pr.get("budget", 0), ", furthest way %d of %d" % (best, pr["nways"] - 1) if best and pr.get("nways")
                else "", pr.get("secs", 0)))
        return "AUTOPILOT: compiling the course to plan on (%.0f s)" % pr.get("secs", 0)

    # -- input
    def kdown(self, e):
        ks = e.keysym
        if ks in self.KEYS:
            self.held[ks] = True
            self.pressed[ks] = time.time()
        elif ks == "BackSpace":
            self.back()
        elif ks in ("p", "P"):
            self.toggle_pause()
        elif ks in ("n", "N"):
            self.step_once()
        elif ks in ("r", "R"):
            self.restart()
        elif ks in ("z", "Z"):
            self.rewind()
        elif ks in ("a", "A"):
            self.start_autopilot()
        elif ks == "1":
            self.set_speed(1.0)
        elif ks == "2":
            self.set_speed(0.5)
        elif ks == "4":
            self.set_speed(0.25)
        elif ks == "Escape":
            self.close()

    def kup(self, e):
        ks = e.keysym
        if ks in self.KEYS:                     # (X11's autorepeat sends release+press pairs: settle first)
            t = time.time()
            self.r.after(30, lambda: self._settle(ks, t))

    def _settle(self, ks, t):
        if self.pressed.get(ks, 0) <= t:        # no press since this release: really up
            self.held[ks] = False

    def keybyte(self):
        k = 0
        for ks, b in self.KEYS.items():
            if self.held.get(ks):
                k |= b
        return k

    # -- controls
    def toggle_pause(self):
        self.paused = not self.paused
        self.gacc = 0.0

    def step_once(self):
        if self.roll and self.paused:           # one frame with a step in it (a frame can hold none)
            while not self.roll.script_over() and not self.roll.frame(self.keybyte()):
                pass
            self.draw()

    def set_speed(self, s):
        self.speed = s
        self.gacc = 0.0

    def rewind(self):
        if self.roll:
            self.roll.rewind()
            self.ended = bool(self.roll.p.goal or self.roll.p.tout or self.roll.script_over())
            self.draw()

    def back(self):
        if self.roll and self.roll.script is None:     # (the autopilot's run is its keys alone)
            self.roll.back_to_flag()

    def restart(self):
        if self.roll:
            self.roll.reset()
            self.ended = False
            self.draw()

    def close(self):
        import shutil
        for j in (self.jplay, self.jfull):
            j.kill()
        self.r.destroy()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def save_demo(self):
        from tkinter import filedialog, messagebox
        if self.roll is None:
            return
        if self.roll.start:
            messagebox.showinfo("Save demo", "A demo replays from the course's start: this run began at cell "
                                "%d, %d (--start). Restart the course from its start to record one." % self.roll.start)
            return
        if not isinstance(self.full, B.Course):
            messagebox.showinfo("Save demo", "A demo names the shipped part's identity, which the full compile "
                                "gives: %s" % ("it is still running" if self.full is None else "it refused - " + self.full))
            return
        K = course_number(self.name)
        out = filedialog.asksaveasfilename(defaultextension=".BZR", initialfile="%s.BZR" % self.roll.c.name,
                                           filetypes=[("Bonanza demo", "*.BZR"), ("all", "*")])
        if not out:
            return
        log = self.roll.log(K or 0, self.full.ident)
        with open(out, "wb") as f:
            f.write(log)
        bzd = os.path.splitext(out)[0] + ".bzd"
        with open(bzd, "w", newline="\n") as f:
            f.write(B.demo_text(log, self.roll.c.name, "%s, a Test Roll run (tools/bbplay.py, SPEC.md 130.58.16)"
                                % self.roll.c.name))
        bad = check_saved(log, self.full, wstate(self.roll.p))
        msg = "Saved %s (%d steps) and %s.\n\n%s" % (
            out, len(self.roll.keys), os.path.basename(bzd),
            "Replayed through the host model from the start: it ends where this run ended." if bad is None else
            "WARNING: " + bad)
        if K is None:
            msg += ("\n\nThis course is not in the game's course list (BZ_COURSES), so the log's course number is "
                    "0 and the game will not take it until the course is added (SPEC.md 130.58.9).")
        messagebox.showinfo("Save demo", msg)

    # -- the loop
    def _arrived(self):
        if self.roll is None:
            res = self.jplay.result()
            if res is not None:
                if not res.get("ok"):
                    self.view.config(text="The course does not compile:\n\n" + res.get("error", "?"))
                else:
                    c = load_course(res["out"])
                    self._begin(c, "play-only compile in %.1f s" % (time.time() - self.t0))
        if self.full is None:
            res = self.jfull.result()
            if res is not None:
                if not res.get("ok"):
                    self.full = res.get("error", "?")
                    self.full_note = ("the full compile REFUSED (%s): still playing on the play-only compile - walls "
                                      "do not hide the ball and no demo can be saved" % self.full)
                else:
                    self.full = load_course(res["out"])
                    secs = time.time() - self.t0
                    if self.roll is None:
                        self._begin(self.full, "full compile in %.1f s" % secs)
                        self.full_note = ""
                    else:
                        r = self.roll.replay_on(self.full)
                        if wstate(r.p) != wstate(self.roll.p):
                            self.mismatch = "MISMATCH: the run replayed on the full compile ends in another state " \
                                "(%r against %r) - a fault in the play-only compile (SPEC.md 130.58.16.1)" % (
                                    wstate(r.p)[:8], wstate(self.roll.p)[:8])
                        self.roll, self.art = r, Art(self.full)
                        self.full_note = "on the full compile since %.1f s (%d steps replayed: %s)" % (
                            secs, r.p.nstep, "the same end state" if not self.mismatch else "DIFFERENT")

    def _begin(self, c, how):
        self.roll = Roll(c, self.mat, self.herc, self.start)
        self.art = Art(c)
        self.first = how
        self.view.config(text="")
        self.last = time.time()
        if self.plan is not None:               # (the autopilot's run planned before the course landed)
            self._autoroll()
        elif self.jplan is not None:            # (planning: the course at its start, paused)
            self.paused = True

    def tick(self):
        try:
            self._arrived()
            if self.jplan is not None:
                self._plan_arrived()
                if self.roll is not None and self.jplan is not None and int(time.time() * 2) % 2 == 0:
                    self.draw()                 # (the planning's progress line, twice a second)
            now = time.time()
            if self.roll is not None:
                dt = now - (self.last or now)
                self.last = now
                adv = 0
                if not self.paused:
                    self.gacc += dt * B.CARD_HZ[self.herc] * self.speed
                    n = int(self.gacc)
                    self.gacc -= n
                    if n > 4:                       # (the host fell behind: slow down, never spiral)
                        n, self.gacc = 4, 0.0
                    for _ in range(n):
                        self.roll.frame(self.keybyte())
                        adv += 1
                        if (self.roll.p.goal or self.roll.p.tout) and not self.ended:
                            self.ended = self.paused = True     # the course is over: R restarts, P rolls on
                            break
                        if self.roll.script_over():             # SPEC.md 130.58.50: where the autopilot stops
                            self.ended = self.paused = True
                            break
                if adv or self.photo is None:
                    self.draw()
        finally:
            self.r.after(8, self.tick)

    def _redraw(self):
        if self.roll is not None:
            self.draw()

    def draw(self):
        roll = self.roll
        lagged = bool(self.lagged.get())
        win, org = self.art.window(roll, lagged=lagged)
        im = self.frame_image(roll, win, org)
        b = io.BytesIO()
        im.save(b, "PNG", compress_level=1)
        self.photo = self.tk.PhotoImage(data=base64.b64encode(b.getvalue()).decode("ascii"))
        self.view.config(image=self.photo)
        p = roll.p
        f, nf = roll.flags()
        st = "PAUSED" if self.paused else ("%gx" % self.speed)
        goal = "  FINISHED" if p.goal else "  TIME UP" if p.tout else ""
        clock = "  clock %d" % p.tsec if getattr(roll.c, "limit", 0) and roll.script is None else ""
        self.read.config(text="time %6.2f s   falls %d   back %d   flags %d/%d%s%s   %s   ball %s at cell %d, %d" % (
            roll.seconds(), p.nfall, p.nret, f, nf, clock, goal, st, B.MAT_NAMES[p.mat], p.gx >> 12, p.gy >> 12))
        notes = [self.mismatch] if self.mismatch else []
        red = bool(self.mismatch)
        auto = self._auto_notes()
        if auto:
            notes += auto
            red = red or (self.plan is not None and not self.plan["goal"] and roll.script_over()) or \
                bool(self.plan_err)
        notes.append(self.first)
        if self.full_note:
            notes.append(self.full_note)
        notes.append("camera: Glide (the game's), props: %s; the compositor's approximations: SPEC.md 130.58.16.2"
                     % ("Heavy's drawn poses (the XT's, lagged)" if lagged else "the physics' poses (what the ball meets)"))
        self.note.config(text="\n".join(notes), foreground="#ff6060" if red else "#f0c040")

    def frame_image(self, roll, win, org):
        """the frame as the window shows it, zoomed (CGA 3 x 3, Hercules 1 x 2 of its doubled width), with the
        autopilot's route over it when that is ticked (SPEC.md 130.58.50)"""
        from PIL import Image
        if self.herc:
            im, z = to_herc(win, org).convert("RGB"), (1, 2)
            sx, sy = 2, 2
        else:
            im, z = to_rgb(win, palette(roll.c.src)), (3, 3)
            sx, sy = 3, 3
        im = im.resize((im.size[0] * z[0], im.size[1] * z[1]), Image.NEAREST)
        if self.marks.get():
            route_marks(im, roll, org, sx, sy)
        return im

    def _auto_notes(self):
        """the autopilot's lines for the note: planning, a refusal, what is playing, where it stopped"""
        if self.plan_err:
            return [self.plan_err]
        if self.jplan is not None:
            return [self._plan_progress()]
        if self.plan is None or self.roll is None or self.roll.script is None:
            return []
        r = self.plan
        if self.roll.script_over() or self.roll.p.goal:
            return [stuck_note(r)]
        return ["AUTOPILOT, %s: replaying %s - %d steps, %s" % (
            "branch %s" % r["branch"] if r.get("branch") else "the main route",
            {"plan": "the planner's route", "partial": "the planner's furthest progress, then the arrows",
             "arrows": "the arrows alone"}[r["how"]], len(r["keys"]),
            "to the finish" if r["goal"] else "to where it gets stuck (way %d)" % r["wp"])]

    def run(self):
        self.r.mainloop()


def main(argv):
    import argparse
    if argv[:1] == ["--job"]:
        mode, path, out = argv[1:4]
        name = argv[argv.index("--name") + 1] if "--name" in argv else None
        if mode == "plan":
            return plan_job(path, out, name, argv[argv.index("--branch") + 1] if "--branch" in argv else None)
        return job(mode, path, out, name)
    ap = argparse.ArgumentParser(prog="bbplay.py", description="Test Roll: play a course on the host model")
    ap.add_argument("course")
    ap.add_argument("--start", nargs=2, type=int, metavar=("X", "Y"), help="start on this cell (Physics.poke)")
    ap.add_argument("--ball", choices=B.MAT_NAMES, help="the ball (default the course's)")
    ap.add_argument("--herc", action="store_true", help="the Hercules picture and camera")
    ap.add_argument("--name", help="the course's own path, when COURSE is a copy (the builder's)")
    ap.add_argument("--autopilot", action="store_true",
                    help="replay the autopilot's planned route, or where it gets stuck (SPEC.md 130.58.50)")
    ap.add_argument("--branch", help="with --autopilot: a branch's whole route instead of the main route")
    a = ap.parse_args(argv)
    mat = B.MAT_NAMES.index(a.ball) if a.ball else None
    Player(a.course, a.name, a.start, mat, a.herc, a.autopilot or bool(a.branch), a.branch).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
