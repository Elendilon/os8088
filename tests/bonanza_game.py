#!/usr/bin/env python3
"""BONANZA: the GAME - the tour, BONANZA.DAT, the scorecard (SPEC.md 128.14.3, 128.14.14 bonanzagame).

    make bonanzadisk && python3 tests/bonanza_game.py [--adapter cga|herc|both] [--leg NAME ...]
    python3 tests/bonanza_game.py --red NAME        (a red arm, below)
    python3 tests/bonanza_game.py --check           (the host half: the model's tour, the hostile
                                                     files built and decided, every red arm assembled)

The game is driven by the AUTOPILOT: `bz_apilot` (a harness byte, never set
by the package) makes a PLAY take its key bytes from `bz_auto`, recorded as a
play's (bzphys.inc bz_step) - so a tour course is played by exactly the keys
bbcourse.Physics.auto() chooses, and its time is the MODEL's: the route demo's
steps (bbcourse.route_demo), the same on both cards.  The legs, on MartyPC's
CGA (os8088_5150_cga_gla) and Hercules (os8088_5150_herc_gla), each on a disk
the row builds (the shipped build/bonanza.o88, with SYSTEM\\APPDATA as
bonanzadisk builds it, and nothing else):

  posts   V loads FIRST's shipped route demo, R replays it to its goal, D
          benchmarks it, V three times more loads MOON's and D runs it to the
          CUP; then a free play of FIRST with ANOTHER ball (M; the model says
          which one finishes) to its goal - and after each BONANZA.DAT is still
          ABSENT from the floppy (read off it on the host, os88flush): only a
          PLAY with the course's own ball posts a best (128.14.3.3)
  pause   a free play of FIRST with its own ball, P pressed in mid-play: no
          step for a guest second, the log unchanged; P again: the play ends at
          the model's goal step (the pause added none) with the model's log,
          and BONANZA.DAT holds FIRST's best alone
  tour    G: the five courses, each played by the autopilot with its own ball
          (bz_cballs): after each its time in bz_ttime (the model's steps), its
          falls in bz_tfall, bz_tour the next course; bz_tour 6 after the fifth
          and the total their sum; BONANZA.DAT read back = the expected 64
          bytes (`BZT1`, the count, each course's identity, best and falls,
          the tour's XOR and total); every course's launch time to its
          bracket and floppy reads REPORTED - wave 5b (SPEC.md 128.15.13): on
          the BZC2 parts, stored compact and expanded at the fetch, in the
          shipped parts' format (printed)
  stop    a second tour: course 1 as before, course 2 (TRIAL) played SLOWER
          (the autopilot withheld for a guest second: its steps the idle ones
          plus the model's from rest), Esc in course 3 - bz_tour 7 (stopped),
          the finished courses entered, no total, and BONANZA.DAT UNCHANGED
          (neither course's time is under its best; no tour total)
  face    a third tour: course 1, then on the face G, N, M, B, R, D, L and V
          each DO NOTHING (bz_tour, bz_crsel, bz_matsel, bz_vk and bz_rlog as
          they were, no launch reached bz_launch, no chooser), then Esc on the
          face stops it (bz_tour 7)
  hostile one boot a file: a BONANZA.DAT the host wrote onto SYSTEM\\APPDATA
          (a 32-byte file whose bytes are a valid head with a best - the
          length; a bad magic; an entry of another identity; a best of 0; a
          tour of another XOR; a count of 9) - bz_dat after the entry proc is
          the image 128.14.3.3 and 128.14.17 item 6 say (the file refused
          whole, or the bad entry alone), and the next best (FIRST by the
          autopilot) REWRITES THE FILE WHOLE as this build's 64 bytes
  noapp   a disk built WITHOUT SYSTEM\\APPDATA: a best toasts `Best times not
          saved` once (bz_toast reached once over two bests, bz_datw 1)

--red NAME builds a broken package (or image) in a temporary directory (never
build/) and PASSES only if the row FAILS - at its own check:
  besttime    the writer keeps the LAST time, not the least: the stop leg's file
  datlen      BONANZA.DAT's length check removed: the 32-byte file's best is shown
  replaybest  a replay posts a best: the posts leg's R
  noappdata   the leg's image built without SYSTEM\\APPDATA: the tour's read-back
"""
import argparse
import os
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import os88flush               # noqa: E402
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402

DAT = "SYSTEM/APPDATA/BONANZA.DAT"
NTOUR = 5                       # bonanza.asm BZ_NTOUR (BZ_NCRS - 1)
NENT = 8                        # BZD_NENT
TOURMAX = NTOUR * 65534
LEGS = ("posts", "pause", "tour", "stop", "face", "hostile", "noapp")


# ---- the model's side -----------------------------------------------------------
_AUTO = {}


def ncrs():
    R.CRS_K["bench"]
    return dict.__len__(R.CRS_K)


def name_k(k):
    R.CRS_K["bench"]
    return [n for n in R.CRS_K if R.CRS_K[n] == k][0]


def auto_steps(k, mat=None, idle=0):
    """the model's autopilot PLAY on course K with material MAT (its own ball
    by default), after IDLE steps with no key: -> (steps at its goal, falls),
    (None, falls) when it does not finish within bbcourse.DEMO_STEPS"""
    key = (k, mat, idle)
    if key not in _AUTO:
        c = R.course_k(k)
        p = BB.Physics(c, play=True, mat=c.ball if mat is None else mat)
        for _ in range(idle):
            p.step(0)
        keys = [0] * idle
        while p.nstep < BB.DEMO_STEPS + idle and not p.goal:
            kb = p.auto()
            p.step(kb)
            keys.append(kb)
        _AUTO[key] = ((p.nstep if p.goal else None), p.nfall, keys)
    return _AUTO[key][:2]


def auto_keys(k, mat=None, idle=0):
    auto_steps(k, mat, idle)
    return _AUTO[(k, mat, idle)][2]


def ids():
    """K -> the identity BONANZA.DAT files entry K under: course K's (1 - 5),
    0 for BENCH's and past the courses (bz_dnorm)"""
    return {k: (R.course_k(k).ident if 1 <= k < ncrs() else 0) for k in range(NENT)}


def tourx():
    x = 0
    for k in range(1, NTOUR + 1):
        x ^= R.course_k(k).ident
    return x


def dat_image(best=None, tour=0, count=None):
    """the 64 bytes bz_dat holds and a save writes (SPEC.md 128.14.3.3): BEST
    {K: (steps, falls)}, TOUR the total (0 none)"""
    best = best or {}
    b = bytearray(b"BZT1" + bytes([ncrs() if count is None else count, 0, 0, 0]))
    idt = ids()
    for k in range(NENT):
        t, f = best.get(k, (0, 0))
        b += struct.pack("<HHH", idt[k], t, f)
    b += struct.pack("<HIH", tourx(), tour, 0)
    assert len(b) == 64
    return bytes(b)


def hostile_set():
    """[(name, the file's bytes, the bz_dat image the entry proc must make,
    the best the next FIRST play files)] - SPEC.md 128.14.3.3's hostile set and
    128.14.17 item 6's whole-file refusals.  FIRST's play (the autopilot, its
    own ball) is the next best in every case, so each file is REWRITTEN WHOLE"""
    t1, _ = auto_steps(1)
    first = dat_image()
    out = []
    good = bytearray(dat_image({1: (t1 + 99, 2), 2: (499, 0)}))
    # the LENGTH: 32 bytes that are a valid head with FIRST's best (the datlen red shows it)
    short = bytes(dat_image({1: (99, 0)})[:32])
    out.append(("short", short, first, {1: (t1, 0)}))
    bad = bytearray(good)
    bad[3] = ord("2")                                     # `BZT2`
    out.append(("magic", bytes(bad), first, {1: (t1, 0)}))
    bad = bytearray(good)
    struct.pack_into("<H", bad, 8 + 6 * 1, R.course_k(1).ident ^ 0x0101)   # FIRST's entry of another identity
    out.append(("ident", bytes(bad), dat_image({2: (499, 0)}), {1: (t1, 0), 2: (499, 0)}))
    bad = bytearray(good)
    struct.pack_into("<HH", bad, 8 + 6 * 1 + 2, 0, 3)                       # FIRST's best 0 (its falls 3)
    out.append(("zero", bytes(bad), dat_image({2: (499, 0)}), {1: (t1, 0), 2: (499, 0)}))
    bad = bytearray(good)
    struct.pack_into("<HI", bad, 56, tourx() ^ 0x8001, 5000)                # a tour of another XOR
    out.append(("tourx", bytes(bad), dat_image({1: (t1 + 99, 2), 2: (499, 0)}), {1: (t1, 0), 2: (499, 0)}))
    bad = bytearray(good)
    bad[4] = 9                                                              # a count past BZD_NENT
    out.append(("count", bytes(bad), first, {1: (t1, 0)}))
    return out


# ---- the guest's side -----------------------------------------------------------
def boot(tag, img):
    return os88ui.boot(R.at("build/os8088-360.img"), apps=img, machine=R.MACHINE[tag])


def open_game(ui, tag, sym):
    ui.open_drive("B")
    ui.open("BONANZA.O88")
    g = R.Bz(ui, tag, sym, live=True)       # launches claim and drop: the region may move
    ui.settle()
    g.m.pause()
    g.putb("bz_apilot", 1)                  # every play from here is the autopilot's
    g.m.run()
    return g


def guard(g):
    """the held-key guard: the next press of a guarded key needs the last one up"""
    M.until(g.m, lambda _: g.b("bz_dkk") == 0, "the held-key guard to see the last key come up", guest=5)


def motor_off(g):
    """a save is written and finished once the floppy motors have stopped (SPEC.md 18.9.1)"""
    M.guest_sleep(g.m, 0.5)
    M.until(g.m, lambda mm: mm.read(0x43F, 1)[0] & 0x0F == 0, "the floppy motors to stop", guest=15.0)


def bracket(g, what, guest=120):
    """a launch's whole life: the bracket up, down, its parts dropped, the
    title back; -> (floppy reads to the bracket, guest seconds to it)"""
    m = g.m
    c0 = R.cycles(m)
    M.until(m, lambda _: g.b("bz_fs") == 1, "%s: the bracket to come up" % what, guest=60)
    up = (R.cycles(m) - c0) / 4772727.0
    reads = m.disk()["reads"]
    M.until(m, lambda _: g.b("bz_fs") == 0, "%s: the bracket to end" % what, guest=guest)
    M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "%s: its parts dropped" % what, guest=30)
    if "bzs_desk" in g.sym:
        M.until(m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3, "%s: the title back" % what, guest=30)
    motor_off(g)
    return reads, up


def read_dat(g):
    """BONANZA.DAT as the FLOPPY holds it (os88flush, the host's reader), None when absent"""
    try:
        return os88flush.Flush(marty=g.m).volume(1).read(DAT)
    except os88flush.FlushError:
        return None


def choose(g, var, want, key):
    """press KEY (guarded) until [VAR] is WANT"""
    for _ in range(8):
        if g.b(var) == want:
            return
        guard(g)
        k0 = g.b(var)
        g.key(key)
        M.until(g.m, lambda _: g.b(var) != k0, "%s to change %s" % (key, var), guest=5)
    assert g.b(var) == want, "%s never reached %d" % (var, want)


def free_play(g, k, mat, what):
    """a free play of course K with ball MAT (N, M, Enter), the autopilot's -> bracket()"""
    choose(g, "bz_crsel", k, "KeyN")
    choose(g, "bz_matsel", mat, "KeyM")
    g.m.disk(reset=True)
    g.key("Enter")
    return bracket(g, what)


def logs_equal(g, keys, k, mat):
    want = R.make_log(keys, k, mat)
    got = g.m.read(g.a("bz_rlog"), len(want))
    return bytes(got) == want, want, bytes(got)


# ---- the legs -----------------------------------------------------------------
def leg_posts(g):
    """V, R, D (FIRST's demo), V to MOON's and D to its cup, M's other ball: no post"""
    fails = []
    m = g.m
    art = R.at("build/bonanza-art")

    def absent(what):
        d = read_dat(g)
        if d is not None:
            fails.append("posts: after %s BONANZA.DAT is ON the floppy (%d bytes): only a play with the course's "
                         "own ball posts a best (SPEC.md 128.14.3.3)" % (what, len(d)))
        if g.b("bz_newb"):
            fails.append("posts: after %s [bz_newb] is 1" % what)
    if read_dat(g) is not None:
        fails.append("posts: the leg's disk holds a BONANZA.DAT before any play")
    m.pause()
    g.putb("bz_vk", 0)
    m.run()
    guard(g)
    g.key("KeyV")
    demo1 = open(os.path.join(ROOT, art, "BZD1.BIN"), "rb").read()
    M.until(m, lambda _: bytes(m.read(g.a("bz_rlog"), len(demo1))) == demo1,
            "V to put FIRST's shipped demo (BZD1.BIN) in the log", guest=20)
    g.key("KeyR")
    bracket(g, "R of FIRST's demo")
    if not g.b("bz_goal"):
        fails.append("posts: R of FIRST's shipped demo did not reach its goal")
    absent("R of FIRST's demo to its goal")
    guard(g)
    g.key("KeyD")
    bracket(g, "D of FIRST's demo")
    absent("D of FIRST's demo to its goal")
    for _ in range(3):                          # V: BZD2, BZD3, BZD4 (MOON's: to the cup)
        guard(g)
        v0 = g.b("bz_vk")
        g.key("KeyV")
        M.until(m, lambda _: g.b("bz_vk") != v0, "V to load the next shipped demo", guest=20)
    demo4 = open(os.path.join(ROOT, art, "BZD4.BIN"), "rb").read()
    if bytes(m.read(g.a("bz_rlog"), len(demo4))) != demo4:
        fails.append("posts: V four times did not leave MOON's shipped demo (BZD4.BIN) in the log")
    guard(g)
    g.key("KeyD")
    bracket(g, "D of MOON's demo", guest=200)
    if not (g.b("bz_goal") and g.b("bz_hid")):
        fails.append("posts: D of MOON's shipped demo did not hole out (bz_goal %d bz_hid %d)" % (
            g.b("bz_goal"), g.b("bz_hid")))
    absent("D of MOON's demo to its cup")
    other = [mt for mt in range(3) if mt != R.course_k(1).ball and auto_steps(1, mt)[0]]
    if other:
        free_play(g, 1, other[0], "FIRST with %s" % BB.MAT_NAMES[other[0]])
        if not g.b("bz_goal"):
            fails.append("posts: the autopilot's play of FIRST with %s did not finish (the model's does)" %
                         BB.MAT_NAMES[other[0]])
        absent("a free play of FIRST with %s (not its own ball) to its goal" % BB.MAT_NAMES[other[0]])
    print("%s posts: R, D, V and %s left BONANZA.DAT absent: %s" % (
        g.tag, "M's %s" % BB.MAT_NAMES[other[0]] if other else "no other ball (none finishes FIRST in the model)",
        "yes" if not fails else "NO"), flush=True)
    return fails


def leg_pause(g):
    """P in mid-play: no step while paused, the log unchanged; the time the model's"""
    fails = []
    m = g.m
    k, mat = 1, R.course_k(1).ball
    t1, _ = auto_steps(k)
    choose(g, "bz_crsel", k, "KeyN")
    choose(g, "bz_matsel", mat, "KeyM")
    g.key("Enter")
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.d("bz_nstep") >= 40, "FIRST's play 40 steps in", guest=30)
    g.key("KeyP")
    M.guest_sleep(m, 0.3)
    m.pause()
    n1, log1 = g.d("bz_nstep"), bytes(g.read_log())
    m.run()
    M.guest_sleep(m, 1.0)
    m.pause()
    n2, log2 = g.d("bz_nstep"), bytes(g.read_log())
    m.run()
    if n1 != n2 or n1 >= t1:
        fails.append("pause: P pressed at step >= 40: the steps %d then %d a guest second later (the goal at %d): "
                     "a pause runs no step (SPEC.md 128.14.4.7)" % (n1, n2, t1))
    if log1 != log2:
        fails.append("pause: the log changed while paused")
    g.key("KeyP")
    bracket(g, "FIRST's paused play")
    n = g.d("bz_nstep")
    eq, want, got = logs_equal(g, auto_keys(k), k, mat)
    if not g.b("bz_goal") or n != t1:
        fails.append("pause: the play ended at step %d (goal %d), the model's goal step is %d: the pause added "
                     "steps" % (n, g.b("bz_goal"), t1))
    if not eq:
        fails.append("pause: the play's log is not the model's (%d bytes against %d): the pause recorded "
                     "something" % (len(got), len(want)))
    d = read_dat(g)
    exp = dat_image({k: (t1, 0)})
    if d != exp:
        fails.append("pause: BONANZA.DAT after FIRST's best is %s, not the expected %s" % (
            d.hex() if d else None, exp.hex()))
    print("%s pause: paused at step %d for a guest second, the play to its goal at %d (the model's %d), the log "
          "the model's, BONANZA.DAT FIRST's best: %s" % (g.tag, n1, n, t1, "yes" if not fails else "NO"), flush=True)
    return fails, {k: (t1, 0)}


def tour_state(g):
    raw = g.m.read(g.a("bz_ttime"), 4 * NTOUR)
    return g.b("bz_tour"), struct.unpack("<5H", raw[:10]), struct.unpack("<5H", raw[10:])


def leg_tour(g, best):
    """G: the five courses by the autopilot; bz_ttime, bz_tour, the total, the file"""
    fails = []
    m = g.m
    want = [auto_steps(k)[0] for k in range(1, NTOUR + 1)]
    guard(g)
    m.disk(reset=True)
    g.key("KeyG")
    rep = []
    for k in range(1, NTOUR + 1):
        if k > 1:
            m.disk(reset=True)
            g.key("Enter")
        reads, up = bracket(g, "tour course %d" % k, guest=200)
        tour, tt, tf = tour_state(g)
        rep.append("%s %d steps (%d reads, %.2f s to the bracket)" % (name_k(k).upper(), tt[k - 1], reads, up))
        if tt[k - 1] != want[k - 1] or tf[k - 1] != 0:
            fails.append("tour: course %d (%s) entered %d steps and %d falls, the model's autopilot %d and 0" % (
                k, name_k(k).upper(), tt[k - 1], tf[k - 1], want[k - 1]))
        if tour != k + 1:
            fails.append("tour: after course %d bz_tour is %d, not %d" % (k, tour, k + 1))
        if fails:
            return fails, best, 0
    total = sum(want)
    for k in range(1, NTOUR + 1):
        if k not in best or want[k - 1] < best[k][0]:
            best[k] = (want[k - 1], 0)
    exp = dat_image(best, total)
    d = read_dat(g)
    if d != exp:
        fails.append("tour: BONANZA.DAT read back off the floppy %s, the expected 64 bytes %s" % (
            d.hex() if d else "ABSENT", exp.hex()))
    if bytes(g.m.read(g.a("bz_dat"), 64)) != exp:
        fails.append("tour: [bz_dat] is not the expected image")
    print("%s tour (the parts %s, the courses BZC2's, expanded at each fetch: SPEC.md 128.15.13, the launch times "
          "REPORTED): %s; total %d steps; BONANZA.DAT the expected 64 bytes: %s" % (
              g.tag, R.part_fmt().upper(), "; ".join(rep), total, "yes" if not fails else "NO"), flush=True)
    return fails, best, total


def leg_stop(g, best, total):
    """a second tour: course 2 slower, Esc in course 3: stopped, the file unchanged"""
    fails = []
    m = g.m
    k2 = 2
    guard(g)
    g.key("KeyG")
    bracket(g, "stop tour course 1", guest=200)
    m.pause()
    g.putb("bz_apilot", 0)                      # course 2 held back a guest second: slower
    m.run()
    g.key("Enter")
    M.until(m, lambda _: g.b("bz_fs") == 1, "stop tour course 2's bracket", guest=60)
    M.guest_sleep(m, 1.0)
    wk = R.Walker(g, t0=True)
    m.bp_exec(wk.t0)
    while wk.next() != "t0":
        pass
    idle = g.d("bz_nstep")
    g.putb("bz_apilot", 1)
    m.bp_exec()
    m.run()
    bracket(g, "stop tour course 2", guest=200)
    t2, _ = auto_steps(k2, idle=idle)
    tour, tt, _tf = tour_state(g)
    if tt[1] != t2:
        fails.append("stop: course 2 held %d idle steps entered %d steps, the model's %d" % (idle, tt[1], t2))
    g.key("Enter")
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 20, "stop tour course 3 under way", guest=60)
    g.key("Escape")
    # (the bracket is already up: the Esc ends it - so wait for its END, not
    # bracket()'s rise, which never comes again; the final pass of wave 4)
    M.until(m, lambda _: g.b("bz_fs") == 0, "stop tour course 3 to end on Esc", guest=60)
    M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "stop tour course 3: its parts dropped",
            guest=30)
    motor_off(g)
    tour, tt, _tf = tour_state(g)
    if tour != NTOUR + 2 or tt[2] != 0 or tt[0] != auto_steps(1)[0]:
        fails.append("stop: Esc in course 3 left bz_tour %d and the times %s; want 7 (stopped), course 3 not "
                     "entered" % (tour, tt))
    exp = dat_image(best, total)
    d = read_dat(g)
    if d != exp:
        fails.append("stop: BONANZA.DAT after the stopped tour %s, the first tour's %s: a slower course 2 or the "
                     "stopped tour changed it" % (d.hex() if d else "ABSENT", exp.hex()))
    print("%s stop: course 2 slower by %d idle steps (%d), Esc in course 3: bz_tour %d, the file unchanged: %s" % (
        g.tag, idle, t2, tour, "yes" if not fails else "NO"), flush=True)
    return fails


def leg_face(g):
    """a third tour: the withheld keys on the face, then Esc on the face"""
    fails = []
    m = g.m
    guard(g)
    g.key("KeyG")
    bracket(g, "face tour course 1", guest=200)
    m.pause()
    before = (g.b("bz_tour"), g.b("bz_crsel"), g.b("bz_matsel"), g.b("bz_vk"), bytes(g.read_log()))
    m.run()
    with M.bp_trace(m, g.a("bz_launch"), log=True) as tr:
        for key in ("KeyG", "KeyN", "KeyM", "KeyB", "KeyR", "KeyD", "KeyL", "KeyV"):
            g.key(key)
            M.guest_sleep(m, 0.3)
            guard(g)
        M.guest_sleep(m, 0.5)
        n = tr.count()
    m.pause()
    after = (g.b("bz_tour"), g.b("bz_crsel"), g.b("bz_matsel"), g.b("bz_vk"), bytes(g.read_log()))
    dlg = g.ui._word("fdlg_win")
    m.run()
    if after != before or n or dlg not in (0, 0xFFFF):
        fails.append("face: during a tour G, N, M, B, R, D, L and V changed (tour, course, ball, demo) %s -> %s%s, "
                     "%d launch(es), chooser %04X (SPEC.md 128.14.3.4: they do nothing)" % (
                         before[:4], after[:4], ", the log changed" if before[4] != after[4] else "", n, dlg))
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_tour") == NTOUR + 2, "Esc on the face to stop the tour", guest=10)
    print("%s face: the eight keys withheld in a tour, Esc on the face stopped it: %s" % (
        g.tag, "yes" if not fails else "NO"), flush=True)
    return fails


def leg_hostile(tag, sym, td, cases=None, o88=None):
    """one boot a hostile BONANZA.DAT: bz_dat as the checks say, then the file rewritten whole"""
    fails = []
    t1, _ = auto_steps(1)
    for name, raw, want, nxt in hostile_set():
        if cases and name not in cases:
            continue
        p = os.path.join(td, "BONANZA.DAT")
        open(p, "wb").write(raw)
        img = R.disk(td, ["SYSTEM/APPDATA:" + p], name="dat" + name, o88=o88)
        with boot(tag, img) as ui:
            g = open_game(ui, tag, sym)
            got = bytes(g.m.read(g.a("bz_dat"), 64))
            if got != want:
                fails.append("hostile %s: [bz_dat] after the entry proc %s, SPEC.md 128.14.3.3's %s" % (
                    name, got.hex(), want.hex()))
            free_play(g, 1, R.course_k(1).ball, "hostile %s: FIRST" % name)
            d = read_dat(g)
            exp = dat_image(nxt)
            if d != exp:
                fails.append("hostile %s: the next best did not rewrite the file whole: %s, want %s" % (
                    name, d.hex() if d else "ABSENT", exp.hex()))
        print("%s hostile %s (%d bytes): bz_dat as the checks say and the file rewritten whole: %s" % (
            tag, name, len(raw), "yes" if not [f for f in fails if (" %s:" % name) in f] else "NO"), flush=True)
    return fails


def leg_noapp(tag, sym, td, o88=None):
    """a disk without SYSTEM\\APPDATA: one toast over two bests"""
    fails = []
    img = R.disk(td, appdata=False, name="noapp", o88=o88)
    with boot(tag, img) as ui:
        g = open_game(ui, tag, sym)
        m = g.m
        with M.bp_trace(m, "toast_show", log=True) as tr:     # (the kernel's: fixed, where the
                                                                # package's region may move in a launch)
            free_play(g, 1, R.course_k(1).ball, "noapp FIRST")
            n1 = tr.count()
            txt = ui.toast()[0]
            free_play(g, 2, R.course_k(2).ball, "noapp TRIAL")
            n2 = tr.count() - n1
        if n1 != 1 or "Best times not saved" not in txt or g.b("bz_datw") != 1:
            fails.append("noapp: the first best's failed save toasted %d time(s), the toast %r, bz_datw %d: want "
                         "`Best times not saved` once" % (n1, txt, g.b("bz_datw")))
        if n2:
            fails.append("noapp: the second best's failed save toasted again (%d): once a session" % n2)
        if read_dat(g) is not None:
            fails.append("noapp: a BONANZA.DAT appeared on a disk with no SYSTEM\\APPDATA")
    print("%s noapp: `Best times not saved` once over two bests: %s" % (tag, "yes" if not fails else "NO"),
          flush=True)
    return fails


def run(tag, legs=LEGS, src=None, img_main=None, appdata=True, o88=None):
    sym = R.symbols(src)
    fails = []
    with tempfile.TemporaryDirectory() as td:
        img = img_main or R.disk(td, appdata=appdata, name="game", o88=o88)
        if set(legs) & {"posts", "pause", "tour", "stop", "face"}:
            with boot(tag, img) as ui:
                g = open_game(ui, tag, sym)
                best, total = {}, 0
                if "posts" in legs:
                    fails += leg_posts(g)
                if "pause" in legs and not fails:
                    f, best = leg_pause(g)
                    fails += f
                if "tour" in legs and not fails:
                    f, best, total = leg_tour(g, best)
                    fails += f
                if "stop" in legs and not fails:
                    fails += leg_stop(g, best, total)
                if "face" in legs and not fails:
                    fails += leg_face(g)
        if "hostile" in legs and not fails:
            fails += leg_hostile(tag, sym, td, o88=o88)
        if "noapp" in legs and not fails:
            fails += leg_noapp(tag, sym, td, o88=o88)
    return fails


REDS = {
    # the writer keeps the LAST time: the best compare taken out
    # - in bz_post AND in bz_dsave's merge with the file, which since the review (128.14.25 item 4)
    # keeps the smaller of the two by itself: either alone is masked by the other (the final pass of
    # wave 4: the bz_post arm alone stayed GREEN)
    "besttime": [("bonanza.asm", "    jcxz .set\n    cmp ax, cx\n    jae .out\n.set:\n",
                  "    jcxz .set\n    nop                         ; RED besttime: the last time kept\n.set:\n"),
                 ("bonanza.asm", "    cmp ax, dx\n    jae .mn\n",
                  "    nop                         ; RED besttime: the merge keeps ours\n")],
    # the length check removed: a short file's bytes are checked as a whole one
    "datlen": [("bonanza.asm", "    cmp ax, BZD_SIZE\n    jne bz_dnorm\n    call bz_dchk\n",
                "    nop                         ; RED datlen: no length check\n    call bz_dchk\n")],
    # a replay posts a best
    "replaybest": [("bonanza.asm", "    cmp byte [bz_mode], 0       ; a replay posts nothing\n    jne .out\n",
                    "    nop                         ; RED replaybest: a replay posts\n")],
    "noappdata": [],
}
RED_LEGS = {"besttime": ("pause", "tour", "stop"), "datlen": ("hostile",), "replaybest": ("posts",),
            "noappdata": ("tour",)}
RED_WANT = {"besttime": "stop: BONANZA.DAT", "datlen": "hostile short", "replaybest": "posts: after R",
            "noappdata": "tour: BONANZA.DAT"}


def check():
    """the host half: the model's tour, the hostile set decided, the reds assembled"""
    bad = []
    for k in range(1, NTOUR + 1):
        t, f = auto_steps(k)
        print("bonanza_game tour course %d %s: the autopilot's play %s steps, %d falls" % (
            k, name_k(k).upper(), t, f))
        if t is None or f:
            bad.append("course %d: the model's autopilot does not finish without a fall" % k)
    x = tourx()
    inc = open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzcourse.inc")).read()
    import re
    gx = int(re.search(r"^BZ_CRS_TOURX\s+equ\s+0?([0-9A-Fa-f]+)h", inc, re.M).group(1), 16)
    print("bonanza_game the tour's XOR %04Xh, bzcourse.inc's %04Xh" % (x, gx))
    if x != gx:
        bad.append("the tour's identity XOR %04X is not bzcourse.inc's BZ_CRS_TOURX %04X" % (x, gx))
    print("bonanza_game the stop leg's course 2 held 60 idle steps: %s steps" % (auto_steps(2, idle=60)[0],))
    if auto_steps(2, idle=60)[0] != auto_steps(2)[0] + 60:
        print("bonanza_game  (TRIAL from rest after idle steps is not its route + the idle steps: the row computes "
              "the expected time from the model, so this is reported only)")
    for name, raw, want, nxt in hostile_set():
        print("bonanza_game hostile %-6s %2d bytes -> bz_dat %s; the next best files %s" % (
            name, len(raw), "the first run's" if want == dat_image() else "kept in part", nxt))
    other = [mt for mt in range(3) if mt != R.course_k(1).ball and auto_steps(1, mt)[0]]
    print("bonanza_game posts: FIRST finished by the autopilot with %s" % (
        ", ".join(BB.MAT_NAMES[mt] for mt in other) or "no other ball"))
    for line in R.check_reds({k: v for k, v in REDS.items() if v}, "bonanza_game"):
        print(line)
    for b in bad:
        print("FAIL %s" % b)
    assert not bad, "%d model failure(s)" % len(bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--leg", action="append", choices=LEGS)
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only")
    a = ap.parse_args()
    if a.check:
        check()
        return
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    legs = tuple(a.leg) if a.leg else LEGS
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            o88 = None
            if a.red == "noappdata":
                src, img = None, R.disk(td, appdata=False, name="red")
            else:
                src, img = R.build_tree(td, REDS[a.red])
                o88 = os.path.join(td, "BONANZA.O88")
            for tag in tags:
                try:
                    bad = run(tag, RED_LEGS[a.red], src=src, img_main=img, o88=o88)
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(RED_WANT[a.red] in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (a.red, tag, RED_WANT[a.red], bad)
                print("bonanza_game --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_game --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    allbad = []
    for tag in tags:
        bad = run(tag, legs)
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d game failure(s)" % len(allbad)
    print("bonanza_game (%s): PASS" % ", ".join(tags))


if __name__ == "__main__":
    main()
