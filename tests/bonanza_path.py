#!/usr/bin/env python3
"""bonanzapath - THE PATHWAY's loop on the glass (SPEC.md 130.22.4, wave 8R;
rewritten from wave 8b's rolled prototype, 130.19.5; brought to the SHIPPED
map, option A, 2026-11-19: pad 0 FIRST ROLL, pad 1 LITTLE HOP; onto the TEST
MAP, 2026-11-20, BOUNCE-BONANZA-SOAK phase 3).

BONANZA on MartyPC, CGA and Hercules.  Enter on the face opens the TITLE and
P there plays THE GAME (SPEC.md 130.23.4, `enter_game`): the pathway comes up
in the bracket, the FOLLOWER's play (bz_mode 4).  Every item is asserted on
the guest's own state (bz_* reads, breakpoints on its labels), its timing on
the guest's clock.  The pads, routes and arrows are the GUEST's tables (the
pathway part's, `guest_tables`), never numbers written here: pad 0 and the
route its finish opens, the pad that route reaches (pad 1), the arrows each
pad's key map gives a route, the nearest DIAGONAL (a route two arrows take),
the nearest route between pages, the road on from its far pad, and the
SECRET route.  No prototype course is named, played or rolled across.

THE MAP IT BOOTS (SPEC.md 130.54.6; BOUNCE-BONANZA-SOAK phase 3): the BZDEV=1
build's pathway is the TEST MAP (apps/bonanza/courses/pathdev.bbc), not the
shipped path.bbc: pads 0 and 1 the shipped map's cell for cell (ROLL, HOP;
Right, Left back), the rest TEST courses - the diagonal at pad 2 (TQUIK, Up
and Left to pad 3 TCUP), the page route TCUP -> pad 4 TPLY (page 1, its icon),
the climb TPLY -> pad 5 TMIL (1 unit up), and the SECRET route 2 -> 6 by
TQUIK's hidden exit 1 to the hidden pad 6 (BENCH).  ONE BOOT A CARD walks
every item below, the secret leg's included: the build's own map, no patch,
no private compile.  The courses PLAYED are ROLL (2.), HOP (5. - 7.) and
TQUIK (s1.); the rest are only rolled across.

  0. a new game: five lives, the marble RESTING on pad 0's cell, every gate
     closed;
  1. no arrow moves it (pad 0's routes are closed); Space shows the INFO card
     of pad 0's course (bz_kinfow, AL its K), a key takes it down;
  2. Enter plays pad 0's course (ROLL), its ball POKED next to its goal (the
     shortest play there is) and, once the camera has come to rest there, into
     it: the FINISH SEQUENCE - the clock's digit lanes alternate (bz_ffl's
     blank bit, bz_tdig's units) and are drawn together (2s), the camera still
     (bz_R0, bz_c0), and a ball poked over a VOID cell below its kill height in
     the sequence falls on, neither counted nor respawned (bz_nfall, its cell) -
     then Enter SKIPS it (bz_fend with steps left: 2e);
  3. back on the pathway pad 0 is DONE (its sign a medal pose), the route its
     exit keys OPENED, its gate's sign posed 1 - 5 in order and its LANE drawn
     at 5; the marble AUTO-ROLLS to that route's far pad (pad 1), its position
     bbcourse.Follow's at every STEP of the roll (bz_follow's entries), RESTING
     there;
  4. every arrow pad 1's key map gives that route takes it BACK to pad 0
     (Follow, reversed), and every arrow pad 0's gives it brings it back (on
     the test map, as on the shipped one, Left and Right: a straight road);
  5. the HELD pathway: Enter at pad 1 plays its course (HOP) beside the
     pathway's row, kept fetched (bz_phold 1) and re-entered with no fetch
     (bz_phre); Esc in the course costs a LIFE (4) on the counters (their digit
     lanes drawn 1 + 4: 5l);
  6. the FORCED fallback (bz_phforce, poked before the game is entered again
     from the title): HOP again, the pathway dropped for the course and fetched
     after;
  7. the lives poked to 1, HOP left by Esc: the GAME OVER - the pathway's OVER
     state (its sound), then the card (bz_kover), then the title;
  8. P again: a NEW game (five lives, resting on pad 0, no route open); every
     route but the secret one opened by a poke; the secret route CLOSED (s0.:
     its hidden pad's sign 0, its reveal groups 0); the marble rolled to the
     nearest pad with a DIAGONAL route (two arrows: on the test map pad 2's
     up-left road to pad 3, Up and Left) and each of that pad's arrows on it
     takes the route (Follow), the far pad's arrow bringing it back (8d);
  9. the PAGED camera: the nearest route between pages taken (on the test
     map pad 3 up to pad 4, page 1): bz_R0 at every bz_presented on the start
     page's rows (bz_fixr less a page's card rows a page) until it moves BZ_MAXR
     rows a frame to the far page's and stops there; bz_c0 never moves;
 10. RESTING on that route's far pad its icon's lanes are walked (their drawn
     pose changes) and no other icon's lane is MARKED (bz_latt) at any walk's
     entry (bz_props); rolled on (pad 4 up the ramp to pad 5 on the test map),
     the left pad's icon is back at its rest pose and its lanes unmarked at
     every walk's entry, and the marble UP the ramp (gz > 0: 10b);
 s1. THE SECRET route, in the same boot: the marble rolled over the open map
     to the secret route's pad (pad 2), Enter plays its course (TQUIK), its
     ball poked into the goal of the route's HIDDEN exit (exit 1): no gate, the
     route rolled at once, its REVEAL groups posed 1 one at a time, each once
     the marble's distance passes its own (the tables'), the hidden pad shown
     at the arrival and the visible end (pad 2) with the route drawn (+ 4).

Red arms: `nopage` (bz_crshdr never sets PAGED: the camera follows like GLIDE,
R0 off the page rows - 9.), `nogate` (bz_nset marks no lane: the gate's poses
never drawn - 3.), `nodiag` (Left is not the pathway's arrow: pad 1's way back
- 4.), `finfall` (a fall in a goal's finish sequence respawns the ball - 2.).

--check (the host half): every red arm's anchors found and its copy
assembles; the test map's walk as the row takes it (pads 0 and 1 ROLL and HOP,
pad 1's way back Left alone - nodiag's aim -, a diagonal, a page route to an
icon pad, a CLIMB on from it, the secret route keyed by a hidden exit and
reachable from 10b.'s pad); and bz_follow run under unicorn against
bbcourse.Follow on every route of the test map (the secret one and the ramp
included), both ways - the arithmetic items 3, 4, 8d and s1 then check on
the glass.

    python3 tests/bonanza_path.py [--tag cga|herc] [--red ARM] [--check]
"""
import argparse
import os
import struct
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
    # bz_pwkey: Left is not the pathway's (pad 1's arrow back to pad 0 on the shipped map ignored)
    "nodiag": [("bonanza.asm", "    inc bx\n    cmp ah, KSC_LEFT\n    je .k\n",
                "    inc bx\n    cmp ah, 0ffh                ; RED nodiag\n    je .k\n")],
    # bz_step .respawn: a fall in a FINISH SEQUENCE respawns as in play
    "finfall": [("bzphys.inc", "    je .rsp                     ; plane or an open cell neither kills nor\n",
                 "    jmp .rsp                    ; RED finfall\n")],
}
RED_WANT = {"nopage": "9.", "nogate": "3.", "nodiag": "4.", "finfall": "2."}

ST_REST, ST_ROLL, ST_GATE, ST_OVER = 0, 1, 2, 3     # bz_pwst (bonanza.asm BZ_PW_*)
PROPREC = 32                                        # a record's bytes (bz_lrecsi: five shifts)
BZP_SNUM = 28
MAXR = 2                                            # bzgame.inc BZ_MAXR
LINES = 200                                         # bzvideo.inc BZ_LINES
ARROWS = ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight")    # a pad's key map's order (130.22.4.5)
SETTLE = 8                                          # frames R0 and c0 unchanged: the camera at rest

BB_PATH = None
TAG = ["?"]


def path_k():
    global BB_PATH
    if BB_PATH is None:
        R.crs_fill()                    # (fills the table: the pathway's K is BZ_CRS_PATH -
        BB_PATH = R.inc_equ("BZ_CRS_PATH")          # BZ_CRS_MAX since SPEC.md 130.58.36)
        if BB_PATH is None:
            BB_PATH = dict.__len__(R.CRS_K)
    return BB_PATH


def crs_name(k):
    """bzcourse.inc's name of course K (R.CRS_K's)"""
    path_k()
    return next(n for n, v in R.CRS_K.items() if v == k)


# ---- the part's tables (SPEC.md 130.22.3) -----------------------------------------------------------

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


# ---- the map's walk, off the tables ------------------------------------------------------------------

def arrows(T, pad, ri, rev):
    """the arrows pad PAD's key map gives route RI (REV: travelled B to A) -> their key names"""
    want = ri | (0x80 if rev else 0)
    return [ARROWS[k] for k, v in enumerate(T["keys"][pad]) if v == want]


def ways(T, pad):
    """the routes leaving PAD (secret ones left out): [(route index, rev, the far pad)]"""
    out = []
    for i, r in enumerate(T["routes"]):
        if r["secret"]:
            continue
        if r["a"] == pad:
            out.append((i, False, r["b"]))
        elif r["b"] == pad:
            out.append((i, True, r["a"]))
    return out


def walk(T, frm, to):
    """the shortest roll from pad FRM to pad TO over the open map: [(route, rev, from, to)] (None: no way)"""
    prev, todo = {frm: None}, [frm]
    while todo:
        p = todo.pop(0)
        if p == to:
            break
        for ri, rev, q in ways(T, p):
            if q not in prev:
                prev[q] = (ri, rev, p)
                todo.append(q)
    if to not in prev:
        return None
    legs, p = [], to
    while prev[p] is not None:
        ri, rev, q = prev[p]
        legs.append((ri, rev, q, p))
        p = q
    return legs[::-1]


def by_distance(T, frm):
    """every pad reachable from FRM, nearest first (ties: page 0 first, then the pad number)"""
    d = {frm: 0}
    todo = [frm]
    while todo:
        p = todo.pop(0)
        for _ri, _rev, q in ways(T, p):
            if q not in d:
                d[q] = d[p] + 1
                todo.append(q)
    return sorted(d, key=lambda p: (d[p], T["pads"][p]["page"], p))


def find_diagonal(T, frm):
    """the nearest pad (page 0 first) with a route two of its arrows take -> (pad, route, rev, far pad) or None"""
    for p in by_distance(T, frm):
        for ri, rev, q in ways(T, p):
            if len(arrows(T, p, ri, rev)) >= 2:
                return p, ri, rev, q
    return None


def find_page_route(T, frm):
    """the nearest route between two pages, taken from its end nearest FRM -> (start pad, route, rev, far pad)"""
    for p in by_distance(T, frm):
        for ri, rev, q in ways(T, p):
            if T["pads"][p]["page"] != T["pads"][q]["page"]:
                return p, ri, rev, q
    return None


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
    """SPEC.md 130.23.4: the TITLE up - its course fetched and its demo's frame
    loop reached (a key typed before bz_play starts is drained)"""
    M.until(g.m, lambda _: g.b("bz_tmode") == 1 and g.b("bz_crs") == path_k() + 1 and g.w("bz_cseg") != 0,
            "the title", guest=60)
    X.at_t0(g, lambda g_: None)


def enter_game(g, what="the pathway", title=False):
    """Enter on the face opens the TITLE (130.23.4) - or, TITLE, it is up - and
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


def roll_to(g, T, legs, what):
    """the marble rolled along LEGS (walk()'s), each leg's first arrow, resting at each far pad"""
    for ri, rev, frm, to in legs:
        M.guest_sleep(g.m, 0.2)                 # (the arrows up: the held guard let go)
        g.key(arrows(T, frm, ri, rev)[0])
        resting(g, to, "%s: resting on pad %d" % (what, to))


class Stops:
    """exec breakpoints on package labels: next() -> the name the guest stopped
    at (None: no stop within GUEST seconds)"""

    def __init__(self, g, names):
        self.g, self.m = g, g.m
        self.at = {g.a(n): n for n in names}
        # NO pause on a guest already STOPPED (a breakpoint's): the server's pause turns BreakpointHit into
        # Paused with the CPU's breakpoint flag still set, so the next run steps nothing and stops AGAIN at
        # the same CS:IP - a stop at an address no longer armed, which next() reads as None (debug_server.rs
        # "run"'s comment is that flag's account)
        if self.m.status().get("state") == "running":
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


def skip(n, why):
    print("%s %s SKIP: %s" % (TAG[0], n, why), flush=True)


def void_cell(crs):
    """a VOID cell of the course (a ball under its kill height there respawns, in play)"""
    grid = BB.Grid(crs.cga, crs.wcga)
    for y in range(1, 64):
        for x in range(1, 64):
            try:
                if grid.cell(x, y)[3] == BB.KIND_VOID:
                    return x, y
            except (IndexError, KeyError, ValueError):
                continue
    raise AssertionError("no VOID cell on the course")


def goal_cells(crs, exit_=None):
    """the course's GOAL cells (of exit EXIT_, any when None) -> [(cell, its APRON: a flat plain FLOOR neighbour
    at the goal's height, or None)], the cells with an apron first, then the middle of the run first"""
    tiles = BB.rec_map(crs.tiles)
    goals = sorted(c for c, t in tiles.items() if len(c) == 2 and t.kind == BB.KIND_GOAL   # (whole cells:
                   and (exit_ is None or t.exit == exit_))                                 # a ball poked centred)
    out = []
    for c in goals:
        t = tiles[c]
        ap = None
        for d in ((0, -1), (-1, 0), (0, 1), (1, 0)):
            n = (c[0] + d[0], c[1] + d[1])
            u = tiles.get(n)
            if u is not None and u.kind == BB.KIND_FLOOR and not u.sx and not u.sy and u.z0 == t.z0 \
                    and n not in crs.pcell:
                ap = n
                break
        out.append((c, ap))
    mid = len(out) // 2
    return sorted(out, key=lambda e: (e[1] is None, abs(out.index(e) - mid)))


def clock_lit(g):
    """the clock digit lanes meeting the SHOWN window (bz_lshown's test) whose DRAWN pose (bz_ldrw) is lit, not
    blank (pose 0) -> their count"""
    n = g.b("bz_nlane")
    rd = lambda name, k: g.m.read(g.a(name), k)
    knd, drw, tcl, tw = rd("bz_lknd", n), rd("bz_ldrw", n), rd("bz_ltcl", n), rd("bz_ltw", n)
    q0 = struct.unpack("<%dH" % n, rd("bz_ltq0", 2 * n))
    q1 = struct.unpack("<%dH" % n, rd("bz_ltq1", 2 * n))
    r0, h, c0, w = g.w("bz_R0"), g.w("bz_H"), g.w("bz_c0"), g.w("bz_W")
    lit = 0
    for i in range(n):
        if knd[i] != BB.PK_CLOCK:
            continue
        if not (r0 < q1[i] and r0 + h > q0[i] and tcl[i] < c0 + w and tcl[i] + tw[i] > c0):
            continue
        lit += drw[i] != 0
    return lit


def finish_pad0(g, fails, k):
    """item 2: course K from pad 0, its ball poked beside its goal and, the camera at rest, into it; the finish
    sequence, a fall in it, Enter skipping it.  -> the exit finished by (None: no finish), the guest paused at
    bz_fend, breakpoints clear"""
    m = g.m
    name = crs_name(k)
    crs = R.course(name)                        # (the host's work BEFORE the play: the sequence is ~3 guest s)
    void = void_cell(crs)
    cells = goal_cells(crs)
    gc, ap = cells[0]
    if ap is None:
        raise AssertionError("%s: no goal cell with a plain floor beside it to rest the ball on" % name)
    mat = crs.ball
    pa = BB.Physics(crs, play=True, mat=mat).poke(*ap)
    pg = BB.Physics(crs, play=True, mat=mat).poke(*gc)
    g.key("Enter")
    course_up(g, k, "%s from pad 0" % name.upper())
    X.at_t0(g, lambda g_: R.poke_ball(g_, pa.gx, pa.gy, pa.gz, 0, 0, 0, air=0))
    # the camera comes to rest over the ball (a scroll at BZ_MAXR rows a frame): then the goal, so the finish
    # sequence's window is the goal's, its clock in it (130.22.6), as a play's would be
    sp = Stops(g, ("bz_t0",))
    last, same = None, 0
    for _ in range(1200):
        if sp.next() != "bz_t0":
            break
        cam = (g.w("bz_R0"), g.w("bz_c0"))
        same = same + 1 if cam == last else 0
        last = cam
        if same >= SETTLE:
            break
    settled = same >= SETTLE
    if settled:
        R.poke_ball(g, pg.gx, pg.gy, pg.gz, 0, 0, 0, air=0)
    sp.done(run=False)
    if not settled:
        check(fails, False, "2.", "%s's finish: the camera at rest beside the goal" % name.upper(),
              "the camera never came to rest over the ball beside the goal (R0, c0 %s)" % (last,))
        m.run()
        return None
    # the guest STOPPED at the goal step's bz_fstart (a poll of bz_fcnt lets the guest run on while the host
    # reads: a whole sequence can pass before the next breakpoint is set)
    sp = Stops(g, ("bz_fstart",))
    hit = sp.next(guest=30)
    sp.done(run=False)
    if hit != "bz_fstart":
        check(fails, False, "2.", "%s's finish sequence: the goal step (%s)" % (name.upper(), hit),
              "the ball poked into the goal %s finished nothing (%s)" % (gc, hit))
        return None
    ex = g.b("bz_exit")
    sp = Stops(g, ("bz_t0", "bz_fend"))
    hit = sp.next()
    if hit != "bz_t0":
        sp.done()
        check(fails, False, "2.", "%s's finish sequence" % name.upper(),
              "the sequence ended before its frames were read")
        return None
    r0, c0, nfall = g.w("bz_R0"), g.w("bz_c0"), g.w("bz_nfall")
    R.poke_ball(g, (void[0] << 12) + 0x800, (void[1] << 12) + 0x800, -2048 * 256, air=1)
    blanks, units, still, cell = set(), set(), True, True
    # SPEC.md 130.22.6.1: the lit phase shows the RUN's time (the limit less the seconds left), not the seconds left
    kc = g.b("bz_crs")
    lim = struct.unpack("<H", g.m.read(g.a("bz_clims") + 2 * kc, 2))[0]
    run = lim - g.w("bz_tsec")
    lit, runok, nlit = set(), True, []
    for _ in range(24):
        if sp.next() != "bz_t0":
            break
        bl = g.b("bz_ffl") >> 7
        blanks.add(bl)
        units.add(g.b("bz_tdig"))
        if not bl:
            lit.add(g.b("bz_tdig"))
            runok = runok and g.b("bz_tdig") == run % 10 + 1
        nlit.append((bl, clock_lit(g)))
        still = still and (g.w("bz_R0"), g.w("bz_c0")) == (r0, c0)
        cell = cell and (g.d("bz_gx") >> 12, g.d("bz_gy") >> 12) == void
    fall = g.w("bz_nfall") == nfall and cell
    left = g.b("bz_fcnt")
    # ...and the shown clock digits change TOGETHER (130.22.6.1, bz_wclk): at every frame's start either none of
    # them is drawn lit or all that the run's time lights are, never some
    # ...and DRAWN as the phase says by the frame after it changed (one frame's lag, never a stall: on the VGA
    # the group once waited for the wheel's room, the clock frozen on the countdown for 26 frames)
    whole = max([n for _, n in nlit] or [0])
    split = [n for _, n in nlit if n not in (0, whole)]
    stale = [i for i in range(1, len(nlit)) if nlit[i][0] == nlit[i - 1][0]
             and nlit[i][1] != (0 if nlit[i][0] else whole)]
    up = name.upper()
    check(fails, whole > 0 and not split and not stale, "2s.",
          "%s's finish: the shown clock digits drawn lit a frame %s - all %d or none, never split, and as the "
          "phase says from the frame after it changes" % (up, sorted(set(n for _, n in nlit)), whole),
          "the flash's digits split (%s) or lagged their phase (frames %s): (blank, lit) a frame %s" % (
              split, stale, nlit))
    check(fails, len(blanks) == 2 and len(units) >= 2 and lit and runok and still and fall, "2.",
          "%s's finish sequence (exit %d, the goal %s): the clock blank %s, its units' poses %s (lit %s: the run's "
          "%d s of %d), the camera still %s; a fall poked in it neither counted (falls %d -> %d) nor respawned "
          "(on its void cell %s)" % (up, ex, gc, sorted(blanks), sorted(units), sorted(lit), run, lim, still,
                                     nfall, g.w("bz_nfall"), cell),
          "the finish sequence (blank %s, units %s, lit %s against the run's %d s, still %s) or its fall "
          "(respawned or counted: %s)" % (sorted(blanks), sorted(units), sorted(lit), run, still, not fall))
    sp.done(run=False)
    sp = Stops(g, ("bz_fend",))
    hit = sp.press("Enter", guest=5)
    fc = g.b("bz_fcnt")
    sp.done(run=False)
    check(fails, hit == "bz_fend" and fc > 1, "2e.", "Enter in the sequence (%d steps left) ends the play at once: "
          "bz_fend with %d left" % (left, fc), "Enter did not skip the finish sequence (%s, %d left)" % (hit, fc))
    return ex


def aborts(leg):
    """LEG(tag, fails, ...) run with a wait that RAISES (a guest that never reaches a later item's state, a
    red arm's usual way past the item it breaks) recorded as one more failure - after the items already
    checked, so a red arm is judged by the item it went red at -> fails"""
    def run_(tag, *a, **k):
        TAG[0] = tag
        fails = []
        try:
            leg(tag, fails, *a, **k)
        except (M.MartyError, KeyError, IndexError) as e:
            why = str(e).split(" THE BUDGET")[0]
            print("%s aborted: %s: %s" % (tag, type(e).__name__, why), flush=True)
            fails.append("abort (after %d failed item(s)): %s: %s" % (len(fails), type(e).__name__, why))
        return fails
    return run_


def host_tables():
    """the pathway part's tables as the build wrote them (BZPATH.BIN, the part the guest fetches)"""
    return tables(open(R.at("build/bonanza-art/BZPATH.BIN"), "rb").read())


@aborts
def run(tag, fails, apps=None, src=None):
    sec = secret_plan(host_tables())            # (the host's work BEFORE the boot: the secret leg's poke)
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
        if not check(fails, ok, "0.", "a new game: lives %d, resting on pad 0 (%s) at %s (its cell %s), the gates %s"
                     % (lives, crs_name(p0["k"]).upper(), at, (p0["gx"], p0["gy"]), gates),
                     "a new game is not resting on pad 0, every gate closed"):
            return fails
        # --- 1. no arrow moves it; Space the INFO card ---------------------------------------------------
        at0 = pos(g)
        for key in ARROWS:
            g.key(key)
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
        # --- 2. pad 0's course finished, its finish sequence, Enter skipping it ----------------------------
        ex = finish_pad0(g, fails, p0["k"])
        if ex is None:
            return fails
        # --- 3. pad 0 DONE, the gate, the auto-roll (from the course's bz_fend, still paused) ---------------
        ri0 = next(i for i, r in enumerate(T["routes"]) if r["a"] == 0 and r["e"] == ex)
        rt0 = T["routes"][ri0]
        b0 = rt0["b"]
        if rt0["gate"] is None:
            check(fails, False, "3.", "the route pad 0's exit %d opens has a gate" % ex, "route %d has no gate" % ri0)
            return fails
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
        done = bool(g.d("bz_ndone") & 1 and g.d("bz_nrop") & (1 << ri0))
        medal = nst(g, p0["sign"])
        check(fails, seen == [1, 2, 3, 4, 5] and 5 in drawn and done and medal >= 1, "3.",
              "back on the pathway: pad 0 DONE (its sign %d), route %d (0 -> %d, exit %d) OPENED, its gate posed %s, "
              "its lane drawn %s" % (medal, ri0, b0, ex, seen, sorted(drawn)),
              "the gate of (0, exit %d): poses %s, drawn %s, done and opened %s, pad 0's sign %d" % (
                  ex, seen, sorted(drawn), done, medal))
        if hit == "bz_pwdep":
            why, n = follow_roll(g, rt0, False, "the auto-roll to pad %d" % b0)
        else:
            sp.done()
            why, n = "no departure after the gate (%s)" % hit, 0
        check(fails, why is None and g.b("bz_ppad") == b0, "3r.", "the auto-roll to pad %d: bbcourse.Follow's "
              "position at every one of its %d steps, RESTING on pad %d" % (b0, n, b0),
              why or "not resting on pad %d" % b0)
        # --- 4. every arrow on that route takes it back, and brings it back ------------------------------
        back, fwd = arrows(T, b0, ri0, True), arrows(T, 0, ri0, False)
        if not back or not fwd:
            check(fails, False, "4.", "route %d's arrows" % ri0, "route %d has no arrow (back %s, on %s)" % (
                ri0, back, fwd))
        for i in range(max(len(back), len(fwd)) if back and fwd else 0):
            why = None
            for key, rev, frm, dest in ((back[i % len(back)], True, b0, 0), (fwd[i % len(fwd)], False, 0, b0)):
                resting(g, frm, "resting on pad %d before %s" % (frm, key))
                M.guest_sleep(m, 0.2)               # (the arrows up: the held guard let go)
                why, n = follow_roll(g, rt0, rev, "%s at pad %d" % (key, frm), key=key)
                check(fails, why is None and g.b("bz_ppad") == dest, "4.", "%s at pad %d: route %d %s, Follow's every "
                      "one of %d steps, resting on pad %d" % (key, frm, ri0, "B to A" if rev else "A to B", n, dest),
                      why or "%s did not take route %d to pad %d" % (key, ri0, dest))
                if why:
                    break
            if why:
                break
        # --- 5. the HELD pathway; Esc in a course costs a life ---------------------------------------------
        resting(g, b0, "resting on pad %d" % b0)
        kb = T["pads"][b0]["k"]
        nb = crs_name(kb).upper()
        held = []
        M.guest_sleep(m, 0.2)
        g.key("Enter")
        course_up(g, kb, "%s from pad %d" % (nb, b0))
        X.at_t0(g, lambda g_: held.append((g_.b("bz_phold"), X.rows(g_)[prow][0] & X.OP_FETCHED)))
        g.key("Escape")
        M.until(m, lambda _: on_path(g), "the pathway after Esc", guest=60)
        X.at_t0(g, lambda g_: None)
        M.guest_sleep(m, 0.3)
        m.pause()
        dig = sorted({ldrw(g, i) for i in lanes_of(g, BB.PK_CLOCK)})
        lives, re_ = g.b("bz_lives"), g.b("bz_phre")
        m.run()
        check(fails, held == [(1, X.OP_FETCHED)] and re_ == 1, "5.", "%s played beside the HELD pathway (phold, its "
              "row fetched: %s), the pathway re-entered from the hold (phre %d)" % (nb, held, re_),
              "the pathway was not held across the course (%s, phre %d)" % (held, re_))
        check(fails, lives == 4 and 1 + 4 in dig, "5l.", "Esc in %s cost a life: lives %d, the counters' digit "
              "lanes drawn %s" % (nb, lives, dig), "Esc cost no life on the counters (lives %d, drawn %s)" % (lives, dig))
        # --- 6. the FORCED fallback: the game entered again from the title with bz_phforce ------------------
        g.key("Escape")
        to_title(g)
        m.pause()
        g.putb("bz_phforce", 1)
        m.run()
        enter_game(g, "the pathway, forced", title=True)
        held = []
        g.key("Enter")
        course_up(g, kb, "%s again" % nb)
        X.at_t0(g, lambda g_: held.append((g_.b("bz_phold"), X.rows(g_)[prow][0] & X.OP_FETCHED)))
        g.key("Escape")
        M.until(m, lambda _: on_path(g), "the pathway fetched again", guest=60)
        back_ = X.rows(g)[prow][0] & X.OP_FETCHED
        check(fails, held == [(0, 0)] and back_, "6.", "forced (bz_phforce): the pathway dropped for %s (%s) and "
              "fetched again after (%s)" % (nb, held, bool(back_)), "the forced fallback held the pathway (%s)" % held)
        # --- 7. the last life: the GAME OVER --------------------------------------------------------------
        m.pause()
        g.putb("bz_phforce", 0)
        g.putb("bz_lives", 1)
        m.run()
        g.key("Enter")
        course_up(g, kb, "%s with the last life" % nb)
        X.at_t0(g, lambda g_: None)
        sp = Stops(g, ("bz_kover",))
        hit = sp.press("Escape", guest=60)
        st = g.b("bz_pwst")
        sp.done()
        M.guest_sleep(m, 1.0)
        g.key("Space")
        to_title(g)
        check(fails, hit == "bz_kover" and st == ST_OVER and g.b("bz_lives") == 0, "7.", "the last life lost: the "
              "pathway's GAME OVER (its state %d), then the card, then the title" % st,
              "the game over: %s, the pathway's state %d, lives %d" % (hit, st, g.b("bz_lives")))
        # --- 8. a NEW game; the nearest DIAGONAL's two arrows -------------------------------------------
        enter_game(g, "a new game after the game over", title=True)
        m.pause()
        lives, pad, st, nrop = g.b("bz_lives"), g.b("bz_ppad"), g.b("bz_pwst"), g.d("bz_nrop")
        allr = sum(1 << i for i, r in enumerate(T["routes"]) if not r["secret"])
        g.putd("bz_nrop", allr)                     # (every route opened by a poke: the walk below crosses pads
        m.run()                                     # whose courses this row never plays)
        check(fails, lives == 5 and pad == 0 and st == ST_REST and nrop == 0, "8.", "P after the game over: a NEW "
              "game - lives %d, resting on pad %d, no route open (%08Xh)" % (lives, pad, nrop),
              "not a new game after the game over (lives %d, pad %d, state %d, routes %08Xh)" % (lives, pad, st, nrop))
        # s0. the SECRET route (SPEC.md 130.54.6) closed at the new game: its hidden pad's sign 0, its reveal
        # groups 0 - its pad's and route's tables the guest's own, as the host planned them
        if sec is None:
            skip("s0.", "the map has no secret route: the secret leg is not tested")
        else:
            srt = T["routes"][sec["ri"]]
            hid = T["pads"][srt["b"]]
            m.pause()
            rv0, hs0 = reveal(g, srt), nst(g, hid["sign"])
            m.run()
            check(fails, srt == sec["rt"] and hs0 == 0 and not any(rv0) and hid["hidden"], "s0.", "the new game: "
                  "the secret route %d (pad %d -> hidden pad %d, %s's exit %d) closed - the hidden pad's sign %d, "
                  "its %d reveal groups %s" % (sec["ri"], srt["a"], srt["b"], sec["name"], srt["e"], hs0,
                                               len(srt["dist"]), rv0),
                  "the secret route shown at a new game (the hidden pad's sign %d, reveal %s) or not the build's "
                  "table" % (hs0, rv0))
        dg = find_diagonal(T, 0)
        at_pad = 0
        if dg is None:
            skip("8d.", "no route of the map is taken by two arrows (a diagonal): its two arrows are not tested")
        else:
            dp, dri, drev, dq = dg
            roll_to(g, T, walk(T, 0, dp), "to the diagonal")
            at_pad = dp
            for key in arrows(T, dp, dri, drev):
                ret = arrows(T, dq, dri, not drev)[0]
                why = None
                for k_, rev, frm, dest in ((key, drev, dp, dq), (ret, not drev, dq, dp)):
                    resting(g, frm, "resting on pad %d before %s" % (frm, k_))
                    M.guest_sleep(m, 0.2)
                    why, n = follow_roll(g, T["routes"][dri], rev, "%s at pad %d" % (k_, frm), key=k_)
                    check(fails, why is None and g.b("bz_ppad") == dest, "8d.", "%s at pad %d (route %d, %s of its "
                          "two arrows %s): Follow's every one of %d steps, resting on pad %d" % (
                              k_, frm, dri, "one" if frm == dp else "back", arrows(T, dp, dri, drev), n, dest),
                          why or "%s did not take route %d to pad %d" % (k_, dri, dest))
                    if why:
                        break
                if why:
                    break
        # --- 9. the PAGED camera: the nearest route between pages ------------------------------------------
        pr = find_page_route(T, at_pad)
        if pr is None:
            skip("9.", "no route of the map crosses between pages: the paged camera is not tested")
            skip("10.", "the icon walk follows item 9's route: not tested")
        else:
            sp_, pri, prev_, zp = pr
            resting(g, at_pad, "resting on pad %d" % at_pad)
            roll_to(g, T, walk(T, at_pad, sp_), "to the page route")
            M.guest_sleep(m, 0.3)
            fixr = g.w("bz_fixr")
            r_from, r_to = fixr - rows * T["pads"][sp_]["page"], fixr - rows * T["pads"][zp]["page"]
            c0 = g.w("bz_c0")
            key = arrows(T, sp_, pri, prev_)[0]
            sp = Stops(g, ("bz_presented",))
            m.key(key, up=False)
            seq = []
            for i in range(400):
                if sp.next() != "bz_presented":
                    break
                if i == 2:
                    m.key(key, down=False)
                seq.append((g.w("bz_R0"), g.w("bz_c0"), g.b("bz_pwst"), g.b("bz_ppad")))
                if seq[-1][2] == ST_REST and seq[-1][3] == zp and seq[-1][0] == r_to:
                    break
            sp.done()
            sgn = -1 if r_to < r_from else 1
            rs = [s[0] for s in seq]
            steps = [b - a for a, b in zip(rs, rs[1:]) if b != a]
            okp = bool(rs) and rs[0] == r_from and rs[-1] == r_to and bool(steps) \
                and all(d == sgn * MAXR for d in steps[:-1]) and 0 < sgn * steps[-1] <= MAXR \
                and all(s[1] == c0 for s in seq)
            check(fails, okp, "9.", "%s from pad %d (page %d) to pad %d (page %d), route %d: R0 %d (the page's %d) -> "
                  "%d (the page's %d) in %d moves of %s rows a frame, c0 %d throughout" % (
                      key, sp_, T["pads"][sp_]["page"], zp, T["pads"][zp]["page"], pri, rs[0] if rs else -1, r_from,
                      rs[-1] if rs else -1, r_to, len(steps), sorted(set(steps)), c0),
                  "the PAGED camera: R0 %s, c0 %s" % (rs[:6] + ["..."] + rs[-4:], sorted({s[1] for s in seq})))
            # --- 10. an icon's lanes walked only while its pad is the marble's ------------------------------
            resting(g, zp, "resting on pad %d" % zp)
            M.until(m, lambda _: g.w("bz_R0") == r_to, "the page's scroll ended", guest=10)
            sl = lanes_of(g, BB.PK_SIGN)
            icons = {i: q["isign"] for i, q in enumerate(T["pads"]) if q["isign"] is not None}
            if zp not in icons:
                skip("10.", "pad %d has no icon: the icon walk is not tested" % zp)
            else:
                mine = [i for i, n in sl.items() if n == icons[zp]]
                other = [i for i, n in sl.items() if n in icons.values() and n != icons[zp]]
                # (the MARKS are read at the walk's ENTRY, bz_props: after it a lane it walked is unmarked again,
                # so a mark set on a lane that should have none would be gone by bz_presented)
                sp = Stops(g, ("bz_props", "bz_presented"))
                drawn, marked = set(), set()
                for _ in range(180):
                    hit = sp.next()
                    if hit == "bz_props":
                        marked |= {i for i in other if g.m.read(g.a("bz_latt") + i, 1)[0]}
                    elif hit == "bz_presented":
                        drawn |= {ldrw(g, i) for i in mine}
                    else:
                        break
                sp.done()
                check(fails, len(drawn) >= 2 and not marked, "10.", "resting on pad %d: its icon's lanes drawn at "
                      "poses %s, no other icon's lane marked" % (zp, sorted(drawn)),
                      "the icons' marks: pad %d's lanes drawn %s, others marked %s" % (zp, sorted(drawn), sorted(marked)))
                # rolled on: a route on from the icon's pad other than the one it came by, else that one back
                on = [w for w in ways(T, zp) if w[0] != pri] or [w for w in ways(T, zp)]
                lri, lrev, lq = on[0]
                lrt = T["routes"][lri]
                climb = (lrt["pts"][0] if lrev else lrt["pts"][-1])[2] > (lrt["pts"][-1] if lrev else lrt["pts"][0])[2]
                M.guest_sleep(m, 0.2)
                g.key(arrows(T, zp, lri, lrev)[0])
                resting(g, lq, "resting on pad %d" % lq)
                sp = Stops(g, ("bz_props",))           # (the marks at the walk's entry, as above)
                mk = set()
                for _ in range(60):
                    if sp.next() != "bz_props":
                        break
                    mk |= {i for i in mine if g.m.read(g.a("bz_latt") + i, 1)[0]}
                pose, gz = nst(g, icons[zp]), g.sd("bz_gz")
                sp.done()
                if not climb:
                    skip("10b.", "route %d (pad %d to %d) does not climb: the ramp's gz > 0 is not checked (the "
                         "test map's climb is gone: --check refuses that)" % (lri, zp, lq))
                check(fails, pose == 0 and not mk and (gz > 0 or not climb), "10b.", "on pad %d (route %d%s): pad "
                      "%d's icon at its rest pose, its lanes unmarked" % (
                          lq, lri, ", up its ramp: gz %d" % (gz >> 8) if climb else "", zp),
                      "leaving pad %d: its icon's pose %d, marked %s, gz %d" % (zp, pose, sorted(mk), gz >> 8))
        # --- s1. the SECRET route, in the same boot: its key's course finished by its hidden exit ----------
        if sec is not None:
            secret_leg(g, fails, T, sec)
        M.guest_sleep(m, 0.3)
        g.key("Escape")
        to_title(g)
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, "the desktop", guest=30)
    return fails


def secret_plan(T):
    """the SECRET leg's host work, done BEFORE the boot (a course's compile is host seconds, many guest ones at
    MartyPC's pace: done after the course came up it once ran out the course's limit): the map T's secret
    route, its key's course and the goal cell of that exit, and the model's poke into it -> dict, or None (the
    map has no secret route)"""
    ri = next((i for i, r in enumerate(T["routes"]) if r["secret"]), None)
    if ri is None:
        return None
    rt = T["routes"][ri]
    k = T["pads"][rt["a"]]["k"]
    c = R.course(crs_name(k))
    gc = goal_cells(c, rt["e"])[0][0]
    p = BB.Physics(c, play=True, mat=c.ball).poke(*gc)
    return dict(ri=ri, rt=rt, k=k, name=crs_name(k).upper(), gc=gc, poke=(p.gx, p.gy, p.gz))


def reveal(g, rt):
    """the secret route RT's reveal groups' poses (bz_nst from its rsign)"""
    return list(g.m.read(g.a("bz_nst") + rt["rsign"], len(rt["dist"])))


def secret_leg(g, fails, T, sec):
    """s1. (SPEC.md 130.54.6): from wherever the main leg left the marble, rolled over the open map to the pad
    the secret route leaves (on the test map pad 2, TQUIK), Enter plays its course, the ball poked into the goal
    of the route's HIDDEN exit (TQUIK's exit 1): no gate, the route rolled at once, its REVEAL groups posed 1 one
    at a time, each once the marble's distance passes its own (the tables'), the hidden pad shown at the arrival
    and the visible end (the pad it left) with the route drawn (+ 4)"""
    m = g.m
    rt = sec["rt"]
    hid, vend = T["pads"][rt["b"]], T["pads"][rt["a"]]
    at = g.b("bz_ppad")
    resting(g, at, "resting on pad %d before the secret leg" % at)
    legs = walk(T, at, rt["a"])
    if legs is None:
        check(fails, False, "s1.", "a way from pad %d to pad %d (the secret route's start)" % (at, rt["a"]),
              "no open way from pad %d to pad %d" % (at, rt["a"]))
        return
    roll_to(g, T, legs, "to the secret route's pad")
    M.guest_sleep(m, 0.2)
    g.key("Enter")                              # the course, finished by its HIDDEN exit
    course_up(g, sec["k"], "%s from pad %d" % (sec["name"], rt["a"]))
    X.at_t0(g, lambda g_: R.poke_ball(g_, *sec["poke"], 0, 0, 0, air=0))
    M.until(m, lambda _: g.b("bz_fcnt") > 1, "%s's hidden finish" % sec["name"], guest=30)
    ex = g.b("bz_exit")
    sp = Stops(g, ("bz_pwdep",))
    hit = sp.press("Enter", guest=120)          # (the finish skipped)
    order, bad, k = [], [], 0
    if hit == "bz_pwdep":
        sp = Stops(g, ("bz_follow",))
        while sp.next() == "bz_follow":
            s = g.d("bz_pws") >> 8
            rv = reveal(g, rt)
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
    check(fails, ok, "s1.", "%s (pad %d) finished by its hidden exit %d (the goal %s): the secret route %d rolled at "
          "once (no gate), its reveal groups shown %s along it, the hidden pad %d shown (%d) and pad %d's with the "
          "route (%d)" % (sec["name"], rt["a"], ex, sec["gc"], sec["ri"], order, rt["b"], nst(g, hid["sign"]),
                          rt["a"], nst(g, vend["sign"])),
          "the secret route's reveal: %s, exit %d, order %s, %s" % (hit, ex, order, bad[:3]))


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


def plan_lines(T):
    """the main leg's walk on map T, as the guest's tables give it (the host's account of items 3 - 10)"""
    out = []
    r0 = [(i, r) for i, r in enumerate(T["routes"]) if r["a"] == 0 and not r["secret"]]
    for i, r in r0:
        out.append("route %d (pad 0 exit %d -> pad %d): on %s, back %s" % (
            i, r["e"], r["b"], arrows(T, 0, i, False), arrows(T, r["b"], i, True)))
    dg = find_diagonal(T, 0)
    out.append("the diagonal: %s" % ("none" if dg is None else "pad %d, route %d to pad %d, arrows %s, back %s" % (
        dg[0], dg[1], dg[3], arrows(T, dg[0], dg[1], dg[2]), arrows(T, dg[3], dg[1], not dg[2]))))
    pr = find_page_route(T, dg[0] if dg else 0)
    out.append("the page route: %s" % ("none" if pr is None else "pad %d (page %d) -> pad %d (page %d), route %d, %s" % (
        pr[0], T["pads"][pr[0]]["page"], pr[3], T["pads"][pr[3]]["page"], pr[1], arrows(T, pr[0], pr[1], pr[2]))))
    return out


def host_check():
    for line in R.check_reds(REDS, "bonanza_path"):
        print(line)
    with tempfile.TemporaryDirectory() as td:
        binp = os.path.join(td, "bonanza.bin")
        R.assemble(os.path.join(ROOT, "apps", "bonanza"), R.at("build/bonanza-art"), binp)
        part = open(R.at("build/bonanza-art/BZPATH.BIN"), "rb").read()
        T = tables(part)
        for line in plan_lines(T):
            print("bonanza_path the test map's walk: %s" % line)
        dg = find_diagonal(T, 0)
        assert T["pads"][0]["k"] == R.CRS_K["roll"] and T["pads"][1]["k"] == R.CRS_K["hop"], \
            "the test map's pads 0 and 1 are not ROLL and HOP: the row's items 2 - 7 play them"
        assert any(r["a"] == 0 and r["b"] == 1 for r in T["routes"]), "no route from pad 0 to pad 1"
        assert arrows(T, 1, next(i for i, r in enumerate(T["routes"]) if r["a"] == 0 and r["b"] == 1), True) \
            == ["ArrowLeft"], "pad 1's way back to pad 0 is no longer Left alone: the nodiag red arm needs re-aiming"
        assert dg is not None and find_page_route(T, dg[0]) is not None, "the map has no diagonal or no page route"
        g0 = goal_cells(R.course(crs_name(T["pads"][0]["k"])))
        assert g0 and g0[0][1] is not None, "pad 0's course has no goal cell with a plain floor beside it"
        print("bonanza_path pad 0's course: the ball rests at %s and is poked into the goal at %s" % (
            g0[0][1], g0[0][0]))
        bad = follower_check(binp, part, R.symbols())
        print("bonanza_path the follower under unicorn, the test map: its %d routes both ways against "
              "bbcourse.Follow: %s" % (len(T["routes"]), "; ".join(bad) or "every step equal"))
        assert not bad, "bz_follow is not bbcourse.Follow"
        # the SECRET leg's route, the build's own (SPEC.md 130.54.6): one secret route, no gate, its reveal
        # groups, a HIDDEN far pad, its start the VISIBLE END - opened by a hidden exit of that pad's course, a
        # goal of that exit to poke the ball into; the main leg's walk reaches its start from where 10b. leaves
        sec = secret_plan(T)
        srt = sec and sec["rt"]
        assert sec is not None and [r["secret"] for r in T["routes"]].count(True) == 1 and srt["gate"] is None \
            and srt["dist"] and T["pads"][srt["b"]]["hidden"] and T["pads"][srt["a"]]["vend"], \
            "the test map's secret route is not as the secret leg needs it"
        c = R.course(sec["name"].lower())
        assert BB.course_exits(c).get(srt["e"]) is True, "%s's exit %d is not HIDDEN" % (sec["name"], srt["e"])
        pr = find_page_route(T, dg[0])
        zp = pr[3]
        on = [w for w in ways(T, zp) if w[0] != pr[1]] or ways(T, zp)
        lrt = T["routes"][on[0][0]]
        lz = (lrt["pts"][0] if on[0][1] else lrt["pts"][-1])[2] - (lrt["pts"][-1] if on[0][1] else lrt["pts"][0])[2]
        assert T["pads"][zp]["isign"] is not None and lz > 0, \
            "the page route's far pad %d has no icon (10.) or its road on (route %d) does not climb (10b.)" % (
                zp, on[0][0])
        assert walk(T, on[0][2], srt["a"]) is not None, "no open way from pad %d to the secret route's pad %d" % (
            on[0][2], srt["a"])
        print("bonanza_path the icon pad %d (10.), rolled on up route %d's ramp (10b., %d ground px up); the secret route "
              "%d -> hidden pad %d by %s's hidden exit %d (its goal %s), %d reveal groups at %s ground px" % (
                  zp, on[0][0], lz, srt["a"], srt["b"], sec["name"], srt["e"], sec["gc"], len(srt["dist"]),
                  srt["dist"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", choices=("cga", "herc"), action="append")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true",
                    help="the host half: the red arms assemble, the test map's walk, the follower = Follow")
    a = ap.parse_args()
    R.dev()                             # the BZDEV=1 build (SPEC.md 130.26.6.1)
    if a.check:
        host_check()
        return 0
    tags = tuple(a.tag or ("cga", "herc"))
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
        fails += ["%s: %s" % (tag, f) for f in run(tag)]
    for f in fails:
        print("FAIL " + f)
    print("bonanzapath: %s" % ("PASS" if not fails else "%d FAIL" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
