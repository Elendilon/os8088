#!/usr/bin/env python3
"""bonanzapath - THE PATHWAY's loop on the glass (SPEC.md 128.22.4, wave 8R;
rewritten from wave 8b's rolled prototype, 128.19.5).

BONANZA on MartyPC, CGA and Hercules.  Enter on the face opens the TITLE and
P there plays THE GAME (SPEC.md 128.23.4, `enter_game`): the pathway comes up
in the bracket, the FOLLOWER's play (bz_mode 4).  Every item is asserted on
the guest's own state (bz_* reads, breakpoints on its labels), its timing on
the guest's clock:

  0. a new game: five lives, the marble RESTING on pad 0's cell, every gate
     closed;
  1. no arrow moves it (pad 0's routes are closed); Space shows the INFO card
     of pad 0's course (bz_kinfow, AL its K), a key takes it down;
  2. Enter plays FIRST, the autopilot finishes it: the FINISH SEQUENCE - the
     clock's digit lanes alternate (bz_ffl's blank bit, bz_tdig's units), the
     camera still (bz_R0, bz_c0), and a ball poked over a VOID cell below its
     kill height in the sequence falls on, neither counted nor respawned
     (bz_nfall, its cell) - then Enter SKIPS it (bz_fend with steps left);
  3. back on the pathway pad 0 is DONE (its sign a medal pose), route (0, exit
     0) OPENED, its gate's sign posed 1 - 5 in order and its LANE drawn at 5;
     the marble AUTO-ROLLS to pad 1, its position bbcourse.Follow's at every
     STEP of the roll (bz_follow's entries), RESTING on pad 1;
  4. Down at pad 1 (a down-left route: both of its arrows) takes route 0 back
     to pad 0 (Follow, reversed), Up brings it back; LEFT, the diagonal's
     second arrow, takes it too, and Right brings it back;
  5. routes 1 and 3 opened by a poke: Up to MILL (pad 2), Up to MOON (pad 4,
     page 1): bz_R0 at every bz_presented on page 0's rows (bz_fixr) until it
     moves BZ_MAXR rows a frame to page 1's and stops there; bz_c0 never moves;
  6. RESTING on MOON its icon's lanes are walked (their drawn pose changes)
     and no other icon's lane is MARKED (bz_latt) at any bz_presented; on PEAK
     (up a ramp, pad 5) MOON's icon is back at its rest pose and unmarked;
  7. the HELD pathway: Enter at PEAK plays it beside the pathway's row, kept
     fetched (bz_phold 1) and re-entered with no fetch (bz_phre); Esc in the
     course costs a LIFE (4) on the counters (their digit lanes drawn 1 + 4);
  8. the FORCED fallback (bz_phforce, poked before the game is entered again
     from the title): the pathway dropped for the course and fetched after;
  9. the lives poked to 1, a course left by Esc: the GAME OVER - the pathway's
     OVER state (its sound), then the card (bz_kover), then the title.

The SECRET leg (after the main leg on the first card; `--leg secret` alone)
plays a PRIVATE tree: path.bbc's route 1 -> 3 (TRIAL's exit 1 to PLAY) made
`secret` and TRIAL's exit-1 goal `hidden` (tools/bbcourse.py builds its art
into a temporary directory).  FIRST finished, TRIAL finished by its hidden
exit 1: no gate, the route rolled at once, its REVEAL groups posed 1 one at a
time, each once the marble's distance passes its own (the tables'), PLAY's
hidden pad shown at the arrival and TRIAL's pad (the visible end) with the
route drawn (+ 4).

Red arms: `nopage` (bz_crshdr never sets PAGED: the camera follows like GLIDE,
R0 off the page rows - 5.), `nogate` (bz_nset marks no lane: the gate's poses
never drawn - 3.), `nodiag` (Left, the down-left diagonal's second arrow, is
not the pathway's - 4.), `finfall` (a fall in a goal's finish sequence
respawns the ball - 2.).

--check (the host half): every red arm's anchors found and its copy
assembles; the private map compiles with its secret route; and bz_follow run
under unicorn against bbcourse.Follow on every route of the shipped part and
of the private one, both ways - the arithmetic item 3 then checks on the glass.

    python3 tests/bonanza_path.py [--tag cga|herc] [--leg main|secret] [--red ARM] [--check]
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import bbcourse as BB           # noqa: E402
import os88marty as M           # noqa: E402
import os88ui                   # noqa: E402
import bonanza_ring as R        # noqa: E402
import bonanza_exit as X        # noqa: E402

REDS = {
    # bz_crshdr: the PAGED bit read, never set - the pathway's camera is GLIDE's
    "nopage": [("bonanza.asm", "    inc byte [bz_paged]\n    mov al, [es:BZC_NPAGES]\n",
                "    nop                         ; RED nopage\n    mov al, [es:BZC_NPAGES]\n")],
    # bz_nset: the pose written, no lane MARKED
    "nogate": [("bzwheel.inc", "    cmp [es:si + BZP_SNUM], cl\n    jne .n\n    mov byte [bz_latt + bx], 1\n",
                "    cmp [es:si + BZP_SNUM], cl\n    jne .n\n    nop                         ; RED nogate\n")],
    # bz_pwkey: Left is not the pathway's (the down-left diagonal's second arrow ignored)
    "nodiag": [("bonanza.asm", "    inc bx\n    cmp ah, KSC_LEFT\n    je .k\n",
                "    inc bx\n    cmp ah, 0ffh                ; RED nodiag\n    je .k\n")],
    # bz_step .respawn: a fall in a FINISH SEQUENCE respawns as in play
    "finfall": [("bzphys.inc", "    je .rsp                     ; plane or an open cell neither kills nor\n",
                 "    jmp .rsp                    ; RED finfall\n")],
}
RED_WANT = {"nopage": "5.", "nogate": "3.", "nodiag": "4.", "finfall": "2."}

ST_REST, ST_ROLL, ST_GATE, ST_OVER = 0, 1, 2, 3     # bz_pwst (bonanza.asm BZ_PW_*)
PROPREC = 32                                        # a record's bytes (bz_lrecsi: five shifts)
BZP_SNUM = 28
MAXR = 2                                            # bzgame.inc BZ_MAXR
LINES = 200                                         # bzvideo.inc BZ_LINES

# the private map (the SECRET leg): TRIAL's exit-1 route a secret one, its goal hidden
SECRET_PATCH = [("path.bbc", "route 1 3 exit 1  path 22,21 25,18", "route 1 3 exit 1 secret path 22,21 25,18"),
                ("trial.bbc", "goal  rect   8 18  9 19  flat 2 exit 1",
                 "goal  rect   8 18  9 19  flat 2 exit 1 hidden")]
COURSES = ["bench", "first", "trial", "mill", "moon", "summit", "playground"]

BB_PATH = None
TAG = ["?"]


def path_k():
    global BB_PATH
    if BB_PATH is None:
        R.CRS_K["bench"]                # (fills the table: the pathway's K is BZ_NCRS)
        BB_PATH = dict.__len__(R.CRS_K)
    return BB_PATH


# ---- the part's tables (SPEC.md 128.22.3) -----------------------------------------------------------

def tables_of(t):
    """{pads, routes, keys} out of the tables' bytes T (from PTHOFF)"""
    npad, nroute = t[0], t[1]
    pads, routes, keys = [], [], []
    o = 4
    for i in range(npad):
        r = t[o:o + 10]
        pads.append(dict(k=r[0], sign=r[1], isign=None if r[2] == 0xFF else r[2], page=r[3] & 63,
                         hidden=bool(r[3] & 128), vend=bool(r[3] & 64),
                         gx=struct.unpack_from("<H", r, 4)[0], gy=struct.unpack_from("<H", r, 6)[0],
                         frames=r[8], every=r[9]))
        o += 10
    for i in range(nroute):
        r = t[o:o + 8]
        off = struct.unpack_from("<H", r, 6)[0]
        n, ng = t[off], t[off + 1]
        pts = [struct.unpack_from("<hhh", t, off + 2 + 6 * k) for k in range(n)]
        dist = [struct.unpack_from("<H", t, off + 2 + 6 * n + 2 * k)[0] for k in range(ng)]
        routes.append(dict(a=r[0], b=r[1], e=r[2], secret=bool(r[3] & 1), gate=None if r[4] == 0xFF else r[4],
                           rsign=None if r[5] == 0xFF else r[5], pts=pts, dist=dist))
        o += 8
    for i in range(npad):
        keys.append(list(t[o:o + 4]))
        o += 4
    return dict(pads=pads, routes=routes, keys=keys)


def tables(part):
    return tables_of(part[struct.unpack_from("<H", part, 42)[0]:])


def guest_tables(g):
    """the pathway part's tables as the guest holds them (bz_cseg, BZC2 +42)"""
    base = g.w("bz_cseg") << 4
    pth = struct.unpack("<H", g.m.read(base + 42, 2))[0]
    return tables_of(bytes(g.m.read(base + pth, 2048)))


def lanes_of(g, kind):
    """{lane: record +28} of the play's lanes of KIND (the records with a lane are the first ones)"""
    seg, poff, n = g.w("bz_cseg"), g.w("bz_poff"), g.b("bz_nlane")
    out = {}
    for i in range(n):
        rec = g.m.read((seg << 4) + poff + PROPREC * i, PROPREC)
        if rec[0] == kind:
            out[i] = rec[BZP_SNUM]
    return out


def nst(g, sign):
    return g.m.read(g.a("bz_nst") + sign, 1)[0]


def ldrw(g, lane):
    return g.m.read(g.a("bz_ldrw") + lane, 1)[0]


# ---- driving ---------------------------------------------------------------------------------------

def on_path(g):
    return g.b("bz_fs") == 1 and g.b("bz_mode") == 4 and g.b("bz_crs") == path_k() and g.w("bz_cseg") != 0


def to_title(g):
    """SPEC.md 128.23.4: the TITLE up - its course fetched and its demo's frame
    loop reached (a key typed before bz_play starts is drained)"""
    M.until(g.m, lambda _: g.b("bz_tmode") == 1 and g.b("bz_crs") == path_k() + 1 and g.w("bz_cseg") != 0,
            "the title", guest=60)
    X.at_t0(g, lambda g_: None)


def enter_game(g, what="the pathway", title=False):
    """Enter on the face opens the TITLE (128.23.4) - or, TITLE, it is up - and
    P there plays the game: the pathway's play REACHED (bz_t0)"""
    if not title:
        g.key("Enter")
        to_title(g)
    g.key("KeyP")
    M.until(g.m, lambda _: on_path(g), what, guest=60)
    X.at_t0(g, lambda g_: None)


def resting(g, pad, what):
    M.until(g.m, lambda _: on_path(g) and g.b("bz_pwst") == ST_REST and g.b("bz_ppad") == pad, what, guest=60)


def course_up(g, k, what):
    """course K's play REACHED (bz_t0), from a pad's Enter"""
    M.until(g.m, lambda _: g.b("bz_mode") == 0 and g.b("bz_crs") == k and g.w("bz_cseg") != 0, what, guest=60)


class Stops:
    """exec breakpoints on package labels: next() -> the name the guest stopped
    at (None: no stop within GUEST seconds)"""

    def __init__(self, g, names):
        self.g, self.m = g, g.m
        self.at = {g.a(n): n for n in names}
        self.m.pause()
        self.m.bp_exec(*self.at)

    def next(self, guest=20.0):
        m = self.m
        m.run()
        if m.wait_stop(180, guest=guest) != "breakpoint":
            return None
        r = m.regs()
        return self.at.get(((r["cs"] << 4) + r["ip"]) & 0xFFFFF)

    def press(self, key, guest=20.0):
        """KEY down, the next stop, KEY up"""
        self.m.key(key, up=False)
        hit = self.next(guest)
        self.m.key(key, down=False)
        return hit

    def done(self, run=True):
        self.m.bp_exec()
        if run:
            self.m.run()


def pos(g):
    return (g.sd("bz_gx"), g.sd("bz_gy"), g.sd("bz_gz"))


def follow_roll(g, rt, rev, what, key=None):
    """the ROLL of route RT (REV: B to A) followed STEP by step at bz_follow's
    entries against bbcourse.Follow: started by KEY, or (KEY None) the guest
    already stopped at its bz_pwdep.  -> (complaint or None, steps)"""
    F = BB.Follow(rt["pts"], reverse=rev)
    exp = [tuple(256 * c for c in F.pts[0])] + [tuple(p) for p in F.run()]
    if key:
        sp = Stops(g, ("bz_pwdep",))
        hit = sp.press(key)
        if hit != "bz_pwdep":
            sp.done()
            return "%s: no departure (%s)" % (what, hit), 0
    sp = Stops(g, ("bz_follow",))
    k = 0
    while True:
        if sp.next() != "bz_follow":
            sp.done()
            return "%s: the follower's steps stopped" % what, k
        st, p = g.b("bz_pwst"), pos(g)
        if k >= len(exp):
            sp.done()
            return "%s: still rolling past the model's %d steps" % (what, len(exp) - 1), k
        if p != exp[k]:
            sp.done()
            return "%s: step %d at %s, the model's %s" % (what, k, p, exp[k]), k
        if st != ST_ROLL:
            break
        k += 1
    sp.done()
    if k != len(exp) - 1:
        return "%s: resting after %d steps, the model's %d" % (what, k, len(exp) - 1), k
    return None, k


def check(fails, ok, n, line, why):
    print("%s %s %s: %s" % (TAG[0], n, line, "yes" if ok else "NO"), flush=True)
    if not ok:
        fails.append("%s %s" % (n, why))
    return ok


def void_cell(crs):
    """a VOID cell of the course (a ball under its kill height there respawns, in play)"""
    grid = BB.Grid(crs.cga)
    for y in range(1, 64):
        for x in range(1, 64):
            try:
                if grid.cell(x, y)[3] == BB.KIND_VOID:
                    return x, y
            except (IndexError, KeyError, ValueError):
                continue
    raise AssertionError("no VOID cell on the course")


def finish_first(g, fails):
    """item 2: FIRST from pad 0, the autopilot to its goal, the finish sequence,
    a fall in it, Enter skipping it.  -> paused at bz_fend, breakpoints clear"""
    m = g.m
    g.key("Enter")
    course_up(g, R.CRS_K["first"], "FIRST from pad 0")
    X.at_t0(g, lambda g_: g_.putb("bz_apilot", 1))
    M.until(m, lambda _: g.b("bz_fcnt") > 1, "FIRST's finish (the autopilot)", guest=120)
    void = void_cell(R.course("first"))
    sp = Stops(g, ("bz_t0", "bz_fend"))
    hit = sp.next()
    if hit != "bz_t0":
        sp.done()
        check(fails, False, "2.", "FIRST's finish sequence", "the sequence ended before its frames were read")
        return
    r0, c0, nfall = g.w("bz_R0"), g.w("bz_c0"), g.w("bz_nfall")
    g.putb("bz_apilot", 0)
    R.poke_ball(g, (void[0] << 12) + 0x800, (void[1] << 12) + 0x800, -2048 * 256, air=1)
    blanks, units, still, cell = set(), set(), True, True
    for _ in range(24):
        if sp.next() != "bz_t0":
            break
        blanks.add(g.b("bz_ffl") >> 7)
        units.add(g.b("bz_tdig"))
        still = still and (g.w("bz_R0"), g.w("bz_c0")) == (r0, c0)
        cell = cell and (g.d("bz_gx") >> 12, g.d("bz_gy") >> 12) == void
    fall = g.w("bz_nfall") == nfall and cell
    left = g.b("bz_fcnt")
    check(fails, len(blanks) == 2 and len(units) >= 2 and still and fall, "2.",
          "FIRST's finish sequence: the clock blank %s, its units' poses %s, the camera still %s; a fall poked in "
          "it neither counted (falls %d -> %d) nor respawned (on its void cell %s)" % (
              sorted(blanks), sorted(units), still, nfall, g.w("bz_nfall"), cell),
          "the finish sequence (blank %s, units %s, still %s) or its fall (respawned or counted: %s)" % (
              sorted(blanks), sorted(units), still, not fall))
    sp.done(run=False)
    sp = Stops(g, ("bz_fend",))
    hit = sp.press("Enter", guest=5)
    fc = g.b("bz_fcnt")
    sp.done(run=False)
    check(fails, hit == "bz_fend" and fc > 1, "2e.", "Enter in the sequence (%d steps left) ends the play at once: "
          "bz_fend with %d left" % (left, fc), "Enter did not skip the finish sequence (%s, %d left)" % (hit, fc))


def run(tag, apps=None, src=None):
    TAG[0] = tag
    fails = []
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, R.symbols(src), live=True)
        ui.settle()
        m = g.m
        path_k()
        prow = X.shell_row() + 1                     # BZ_P_PATH: the row after the shell's
        rows = LINES >> (2 if tag == "herc" else 1)  # a page's card rows
        # --- 0. a new game -------------------------------------------------------------------------------
        enter_game(g)
        m.pause()
        T = guest_tables(g)
        p0 = T["pads"][0]
        gates = [nst(g, r["gate"]) for r in T["routes"] if r["gate"] is not None]
        at = (g.d("bz_gx") >> 8, g.d("bz_gy") >> 8)
        ok = g.b("bz_lives") == 5 and g.b("bz_ppad") == 0 and g.b("bz_pwst") == ST_REST \
            and at == (p0["gx"], p0["gy"]) and not any(gates)
        lives = g.b("bz_lives")
        m.run()
        if not check(fails, ok, "0.", "a new game: lives %d, resting on pad 0 at %s (its cell %s), the gates %s" % (
                lives, at, (p0["gx"], p0["gy"]), gates), "a new game is not resting on pad 0, every gate closed"):
            return fails
        # --- 1. no arrow moves it; Space the INFO card ---------------------------------------------------
        at0 = pos(g)
        for k in ("ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft"):
            g.key(k)
            M.guest_sleep(m, 0.3)
        check(fails, pos(g) == at0 and g.b("bz_pwst") == ST_REST and g.b("bz_ppad") == 0, "1.",
              "the four arrows at pad 0 (its routes closed): still resting there",
              "an arrow moved the marble on a closed route")
        sp = Stops(g, ("bz_kinfow",))
        hit = sp.press("Space", guest=5)
        k = m.regs()["ax"] & 0xFF if hit else None
        sp.done()
        M.guest_sleep(m, 0.3)
        g.key("KeyX")                               # (any key takes the card down; X is nothing on the pathway)
        M.guest_sleep(m, 0.5)
        check(fails, hit == "bz_kinfow" and k == p0["k"] and on_path(g), "1i.",
              "Space: the INFO card of pad 0's course (K %s, the pad's %d), a key takes it down" % (k, p0["k"]),
              "Space did not show pad 0's course's info card (%s, K %s)" % (hit, k))
        # --- 2. FIRST, its finish sequence, Enter skipping it ---------------------------------------------
        finish_first(g, fails)
        # --- 3. pad 0 DONE, the gate, the auto-roll to pad 1 (from the course's bz_fend, still paused) ------
        rt0 = T["routes"][0]
        sp = Stops(g, ("bz_follow", "bz_presented", "bz_pwdep"))
        seen, drawn, gl, hit = [], set(), None, None
        for _ in range(600):
            hit = sp.next()
            if hit in (None, "bz_pwdep"):
                break
            if gl is None and hit == "bz_follow":
                gl = [i for i, n in lanes_of(g, BB.PK_SIGN).items() if n == rt0["gate"]]
            if hit == "bz_follow":
                p = nst(g, rt0["gate"])
                if not seen or seen[-1] != p:
                    seen.append(p)
            elif hit == "bz_presented" and gl:
                drawn |= {ldrw(g, i) for i in gl}
        done = bool(g.d("bz_ndone") & 1 and g.d("bz_nrop") & 1)
        medal = nst(g, p0["sign"])
        check(fails, seen == [1, 2, 3, 4, 5] and 5 in drawn and done and medal >= 1, "3.",
              "back on the pathway: pad 0 DONE (its sign %d), route 0 OPENED, its gate posed %s, its lane drawn %s"
              % (medal, seen, sorted(drawn)),
              "the gate of (0, exit 0): poses %s, drawn %s, done and opened %s, pad 0's sign %d" % (
                  seen, sorted(drawn), done, medal))
        if hit == "bz_pwdep":
            why, n = follow_roll(g, rt0, False, "the auto-roll to pad 1")
        else:
            sp.done()
            why, n = "no departure after the gate (%s)" % hit, 0
        check(fails, why is None and g.b("bz_ppad") == 1, "3r.", "the auto-roll to pad 1: bbcourse.Follow's position "
              "at every one of its %d steps, RESTING on pad 1" % n, why or "not resting on pad 1")
        # --- 4. Down and Left (the down-left diagonal) take it back, Up and Right bring it back ------------
        for key, rev, dest in (("ArrowDown", True, 0), ("ArrowUp", False, 1),
                               ("ArrowLeft", True, 0), ("ArrowRight", False, 1)):
            resting(g, 1 - dest, "resting before %s" % key)
            M.guest_sleep(m, 0.2)                   # (the arrows up: the held guard let go)
            why, n = follow_roll(g, rt0, rev, "%s at pad %d" % (key, 1 - dest), key=key)
            check(fails, why is None and g.b("bz_ppad") == dest, "4.", "%s at pad %d: route 0 %s, Follow's every one "
                  "of %d steps, resting on pad %d" % (key, 1 - dest, "B to A" if rev else "A to B", n, dest),
                  why or "%s did not take route 0 to pad %d" % (key, dest))
            if why:
                break
        # --- 5. the PAGED camera: Up to MILL, Up to MOON (page 1) ------------------------------------------
        resting(g, 1, "resting on pad 1")
        m.pause()
        g.putd("bz_nrop", g.d("bz_nrop") | (1 << 1) | (1 << 3))
        fixr = g.w("bz_fixr")
        m.run()
        M.guest_sleep(m, 0.2)
        g.key("ArrowUp")
        resting(g, 2, "resting on MILL (pad 2)")
        M.guest_sleep(m, 0.3)
        c0 = g.w("bz_c0")
        sp = Stops(g, ("bz_presented",))
        m.key("ArrowUp", up=False)
        seq = []
        for i in range(400):
            if sp.next() != "bz_presented":
                break
            if i == 2:
                m.key("ArrowUp", down=False)
            seq.append((g.w("bz_R0"), g.w("bz_c0"), g.b("bz_pwst"), g.b("bz_ppad")))
            if seq[-1][2] == ST_REST and seq[-1][3] == 4 and seq[-1][0] == fixr - rows:
                break
        sp.done()
        rs = [s[0] for s in seq]
        steps = [b - a for a, b in zip(rs, rs[1:]) if b != a]
        okp = bool(rs) and rs[0] == fixr and rs[-1] == fixr - rows and bool(steps) \
            and all(d == -MAXR for d in steps[:-1]) and -MAXR <= steps[-1] < 0 and all(s[1] == c0 for s in seq)
        check(fails, okp, "5.", "Up from MILL to MOON (page 1): R0 %d (page 0's %d) -> %d (page 1's %d) in %d moves "
              "of %s rows a frame, c0 %d throughout" % (rs[0] if rs else -1, fixr, rs[-1] if rs else -1, fixr - rows,
                                                         len(steps), sorted(set(steps)), c0),
              "the PAGED camera: R0 %s, c0 %s" % (rs[:6] + ["..."] + rs[-4:], sorted({s[1] for s in seq})))
        # --- 6. an icon's lanes walked only while its pad is the marble's ---------------------------------
        resting(g, 4, "resting on MOON (pad 4)")
        M.until(m, lambda _: g.w("bz_R0") == fixr - rows, "the page's scroll ended", guest=10)
        sl = lanes_of(g, BB.PK_SIGN)
        icons = {i: q["isign"] for i, q in enumerate(T["pads"]) if q["isign"] is not None}
        moon = [i for i, n in sl.items() if n == icons[4]]
        other = [i for i, n in sl.items() if n in icons.values() and n != icons[4]]
        sp = Stops(g, ("bz_presented",))
        drawn, marked = set(), set()
        for _ in range(90):
            if sp.next() != "bz_presented":
                break
            drawn |= {ldrw(g, i) for i in moon}
            marked |= {i for i in other if g.m.read(g.a("bz_latt") + i, 1)[0]}
        sp.done()
        check(fails, len(drawn) >= 2 and not marked, "6.", "resting on MOON: its icon's lanes drawn at poses %s, no "
              "other icon's lane marked" % sorted(drawn),
              "the icons' marks: MOON's lanes drawn %s, others marked %s" % (sorted(drawn), sorted(marked)))
        g.key("ArrowLeft")                          # up-left and up a ramp: PEAK
        resting(g, 5, "resting on PEAK (pad 5)")
        sp = Stops(g, ("bz_presented",))
        mk = set()
        for _ in range(60):
            if sp.next() != "bz_presented":
                break
            mk |= {i for i in moon if g.m.read(g.a("bz_latt") + i, 1)[0]}
        pose, gz = nst(g, icons[4]), g.sd("bz_gz")
        sp.done()
        check(fails, pose == 0 and not mk and gz > 0, "6b.", "on PEAK (up the ramp, gz %d): MOON's icon at its rest "
              "pose, its lanes unmarked" % (gz >> 8), "leaving MOON: its icon's pose %d, marked %s" % (pose, sorted(mk)))
        # --- 7. the HELD pathway; Esc in a course costs a life ---------------------------------------------
        k5 = T["pads"][5]["k"]
        held = []
        g.key("Enter")
        course_up(g, k5, "PEAK from pad 5")
        X.at_t0(g, lambda g_: held.append((g_.b("bz_phold"), X.rows(g_)[prow][0] & X.OP_FETCHED)))
        g.key("Escape")
        M.until(m, lambda _: on_path(g), "the pathway after Esc", guest=60)
        X.at_t0(g, lambda g_: None)
        M.guest_sleep(m, 0.3)
        m.pause()
        dig = sorted({ldrw(g, i) for i in lanes_of(g, BB.PK_CLOCK)})
        lives, re = g.b("bz_lives"), g.b("bz_phre")
        m.run()
        check(fails, held == [(1, X.OP_FETCHED)] and re == 1, "7.", "PEAK played beside the HELD pathway (phold, its "
              "row fetched: %s), the pathway re-entered from the hold (phre %d)" % (held, re),
              "the pathway was not held across the course (%s, phre %d)" % (held, re))
        check(fails, lives == 4 and 1 + 4 in dig, "7l.", "Esc in PEAK cost a life: lives %d, the counters' digit "
              "lanes drawn %s" % (lives, dig), "Esc cost no life on the counters (lives %d, drawn %s)" % (lives, dig))
        # --- 8. the FORCED fallback: the game entered again from the title with bz_phforce ------------------
        g.key("Escape")
        to_title(g)
        m.pause()
        g.putb("bz_phforce", 1)
        m.run()
        enter_game(g, "the pathway, forced", title=True)
        held = []
        g.key("Enter")
        course_up(g, k5, "PEAK again")
        X.at_t0(g, lambda g_: held.append((g_.b("bz_phold"), X.rows(g_)[prow][0] & X.OP_FETCHED)))
        g.key("Escape")
        M.until(m, lambda _: on_path(g), "the pathway fetched again", guest=60)
        back = X.rows(g)[prow][0] & X.OP_FETCHED
        check(fails, held == [(0, 0)] and back, "8.", "forced (bz_phforce): the pathway dropped for the course (%s) "
              "and fetched again after (%s)" % (held, bool(back)), "the forced fallback held the pathway (%s)" % held)
        # --- 9. the last life: the GAME OVER --------------------------------------------------------------
        m.pause()
        g.putb("bz_phforce", 0)
        g.putb("bz_lives", 1)
        m.run()
        g.key("Enter")
        course_up(g, k5, "a course with the last life")
        X.at_t0(g, lambda g_: None)
        sp = Stops(g, ("bz_kover",))
        hit = sp.press("Escape", guest=60)
        st = g.b("bz_pwst")
        sp.done()
        M.guest_sleep(m, 1.0)
        g.key("Space")
        to_title(g)
        check(fails, hit == "bz_kover" and st == ST_OVER and g.b("bz_lives") == 0, "9.", "the last life lost: the "
              "pathway's GAME OVER (its state %d), then the card, then the title" % st,
              "the game over: %s, the pathway's state %d, lives %d" % (hit, st, g.b("bz_lives")))
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, "the desktop", guest=30)
    return fails


def secret_art(td):
    """the PRIVATE tree's art: build/bonanza-art copied, the courses copied with
    SECRET_PATCH, and tools/bbcourse.py's run over them into it -> (art, courses)"""
    art, crs = os.path.join(td, "art"), os.path.join(td, "courses")
    shutil.copytree(R.at("build/bonanza-art"), art)
    shutil.copytree(os.path.join(ROOT, "apps", "bonanza", "courses"), crs)
    R.patch_tree(crs, SECRET_PATCH)
    files = [os.path.join(crs, n + ".bbc") for n in COURSES]
    subprocess.run(["python3", "tools/bbcourse.py", "-o", art, "--path", os.path.join(crs, "path.bbc"),
                    "--title", os.path.join(crs, "title.bbc")] + files, cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    return art, crs


def run_secret(tag):
    """the SECRET leg: a private tree's map and TRIAL"""
    TAG[0] = tag
    fails = []
    with tempfile.TemporaryDirectory() as td:
        art, crs = secret_art(td)
        src, img = R.build_tree(td, [], art=art)
        T = tables(open(os.path.join(art, "BZPATH.BIN"), "rb").read())
        rt = next(r for r in T["routes"] if r["secret"])
        hid, vend = T["pads"][rt["b"]], T["pads"][rt["a"]]
        with os88ui.boot(R.at("build/os8088-360.img"), apps=img, machine=R.MACHINE[tag]) as ui:
            ui.open_drive("B")
            ui.open("BONANZA.O88")
            g = R.Bz(ui, tag, R.symbols(src, art), live=True)
            ui.settle()
            m = g.m
            path_k()
            enter_game(g)
            rv0 = list(m.read(g.a("bz_nst") + rt["rsign"], len(rt["dist"])))
            check(fails, nst(g, hid["sign"]) == 0 and not any(rv0), "s0.", "the private map: the hidden pad's sign 0 "
                  "and the secret route's %d reveal groups 0" % len(rt["dist"]), "the secret route shown at the start")
            g.key("Enter")                          # FIRST, then the auto-roll to TRIAL
            course_up(g, R.CRS_K["first"], "FIRST")
            X.at_t0(g, lambda g_: g_.putb("bz_apilot", 1))
            M.until(m, lambda _: on_path(g), "the pathway after FIRST", guest=180)
            m.pause()
            g.putb("bz_apilot", 0)
            m.run()
            resting(g, rt["a"], "resting on TRIAL")
            M.guest_sleep(m, 0.3)
            g.key("Enter")                          # TRIAL, finished by its HIDDEN exit 1
            course_up(g, R.CRS_K["trial"], "TRIAL")
            p = BB.Physics(R.course("trial", src=os.path.join(crs, "trial.bbc"), art=art), play=True,
                           mat=g.b("bz_mat")).poke(8, 18)
            X.at_t0(g, lambda g_: R.poke_ball(g_, p.gx, p.gy, p.gz, 0, 0, 0, air=0))
            M.until(m, lambda _: g.b("bz_fcnt") > 1, "TRIAL's hidden finish", guest=30)
            ex = g.b("bz_exit")
            sp = Stops(g, ("bz_pwdep",))
            hit = sp.press("Enter", guest=120)      # (the finish skipped)
            order, bad, k = [], [], 0
            if hit == "bz_pwdep":
                sp = Stops(g, ("bz_follow",))
                while sp.next() == "bz_follow":
                    s = g.d("bz_pws") >> 8
                    rv = list(m.read(g.a("bz_nst") + rt["rsign"], len(rt["dist"])))
                    n = sum(rv)
                    if rv != [1] * n + [0] * (len(rv) - n):
                        bad.append("not in order at step %d: %s" % (k, rv))
                    if any(rt["dist"][i] > s for i in range(n)):
                        bad.append("a group shown before its distance at step %d (s %d)" % (k, s))
                    if not order or order[-1] != n:
                        order.append(n)
                    if g.b("bz_pwst") != ST_ROLL:
                        break
                    k += 1
            sp.done()
            ok = hit == "bz_pwdep" and ex == rt["e"] and order and order[-1] == len(rt["dist"]) and not bad \
                and g.b("bz_ppad") == rt["b"] and nst(g, hid["sign"]) >= 1 and nst(g, vend["sign"]) >= 4
            check(fails, ok, "s1.", "TRIAL finished by its hidden exit %d: the secret route rolled at once (no gate), "
                  "its reveal groups shown %s along it, PLAY's hidden pad shown (%d) and TRIAL's with the route (%d)"
                  % (ex, order, nst(g, hid["sign"]), nst(g, vend["sign"])),
                  "the secret route's reveal: %s, exit %d, order %s, %s" % (hit, ex, order, bad[:3]))
            g.key("Escape")
            to_title(g)
            g.key("Escape")
            M.until(m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, "the desktop", guest=30)
    return fails


# ---- the host half -----------------------------------------------------------------------------------

def follower_check(binp, part, sym):
    """bz_pwdep then bz_follow under unicorn (the package image at one segment,
    the pathway part at another, the routes opened) on every route of PART,
    both ways, against bbcourse.Follow: -> [complaints]"""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_16
    from unicorn.x86_const import UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP, \
        UC_X86_REG_AX
    cs, ps, ss, stub = 0x1000, 0x3000, 0x6000, 0xFFF0
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x100000)
    mu.mem_write(cs * 16, open(binp, "rb").read())
    mu.mem_write(ps * 16, part)
    mu.mem_write(cs * 16 + stub, b"\xf4")

    def w(n, v, sz):
        mu.mem_write(cs * 16 + sym[n], v.to_bytes(sz, "little"))

    def r(n, sz):
        return int.from_bytes(mu.mem_read(cs * 16 + sym[n], sz), "little", signed=True)

    def call(n, ax=0, es=cs):
        for reg, v in ((UC_X86_REG_CS, cs), (UC_X86_REG_DS, cs), (UC_X86_REG_ES, es), (UC_X86_REG_SS, ss)):
            mu.reg_write(reg, v)
        mu.mem_write(ss * 16 + 0xFFEE, struct.pack("<H", stub))
        mu.reg_write(UC_X86_REG_SP, 0xFFEE)
        mu.reg_write(UC_X86_REG_AX, ax)
        mu.emu_start(cs * 16 + sym[n], cs * 16 + stub, count=1000000)

    w("bz_cseg", ps, 2)
    w("bz_nrop", 0xFFFFFFFF, 4)
    call("bz_ppose")
    bad = []
    for i, rt in enumerate(tables(part)["routes"]):
        for rev in (0, 1):
            w("bz_pwis", 0xFF, 1)
            call("bz_pwdep", ax=i | (rev << 8), es=ps)
            F = BB.Follow(rt["pts"], reverse=bool(rev))
            for k, exp in enumerate(F.run()):
                call("bz_follow")
                got = (r("bz_gx", 4), r("bz_gy", 4), r("bz_gz", 4))
                if got != tuple(exp):
                    bad.append("route %d %s step %d: %s, the model's %s" % (i, "B-A" if rev else "A-B", k, got, exp))
                    break
            else:
                if r("bz_pwst", 1) != ST_REST:
                    bad.append("route %d %s: not resting at the arrival" % (i, "B-A" if rev else "A-B"))
    return bad


def host_check():
    for line in R.check_reds(REDS, "bonanza_path"):
        print(line)
    with tempfile.TemporaryDirectory() as td:
        binp = os.path.join(td, "bonanza.bin")
        R.assemble(os.path.join(ROOT, "apps", "bonanza"), R.at("build/bonanza-art"), binp)
        part = open(R.at("build/bonanza-art/BZPATH.BIN"), "rb").read()
        bad = follower_check(binp, part, R.symbols())
        print("bonanza_path the follower under unicorn, the shipped pathway: its %d routes both ways against "
              "bbcourse.Follow: %s" % (len(tables(part)["routes"]), "; ".join(bad) or "every step equal"))
        assert not bad, "bz_follow is not bbcourse.Follow"
        art, crs = secret_art(td)
        src = os.path.join(td, "bonanza")
        shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
        R.assemble(src, art, binp)
        part = open(os.path.join(art, "BZPATH.BIN"), "rb").read()
        T = tables(part)
        sec = [r for r in T["routes"] if r["secret"]]
        assert len(sec) == 1 and sec[0]["gate"] is None and sec[0]["dist"] and T["pads"][sec[0]["b"]]["hidden"] \
            and T["pads"][sec[0]["a"]]["vend"], "the private map's secret route is not as the leg needs it"
        bad = follower_check(binp, part, R.symbols(src, art))
        print("bonanza_path the private map: secret route %d -> %d (exit %d), %d reveal groups at %s ground px; the "
              "follower under unicorn on its %d routes: %s" % (
                  sec[0]["a"], sec[0]["b"], sec[0]["e"], len(sec[0]["dist"]), sec[0]["dist"], len(T["routes"]),
                  "; ".join(bad) or "every step equal"))
        assert not bad, "bz_follow is not bbcourse.Follow on the private map"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", choices=("cga", "herc"), action="append")
    ap.add_argument("--leg", choices=("main", "secret"), action="append")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true",
                    help="the host half: the red arms assemble, the private map compiles, the follower = Follow")
    a = ap.parse_args()
    if a.check:
        host_check()
        return 0
    tags = tuple(a.tag or ("cga", "herc"))
    legs = tuple(a.leg or ("main", "secret"))
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags[:1]:
                bad = run(tag, apps=img, src=src)
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(b.startswith(RED_WANT[a.red]) for b in bad), \
                    "RED ARM %s went red elsewhere: %s" % (a.red, bad)
        print("RED ARM %s: red as it should be" % a.red)
        return 0
    fails = []
    for tag in tags:
        if "main" in legs:
            fails += ["%s: %s" % (tag, f) for f in run(tag)]
        if "secret" in legs and tag == tags[0]:
            fails += ["%s secret: %s" % (tag, f) for f in run_secret(tag)]
    for f in fails:
        print("FAIL " + f)
    print("bonanzapath: %s" % ("PASS" if not fails else "%d FAIL" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
