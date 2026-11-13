#!/usr/bin/env python3
"""BONANZA: the guest's physics equals bbcourse.Physics, step for step (SPEC.md 128.10.7, 128.11.8, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_phys.py [--adapter cga|herc|both] [--leg bench|scen|replay|all]
                                                      [--only NAME ...]
    python3 tests/bonanza_phys.py --red NAME        (a red arm, below)
    python3 tests/bonanza_phys.py --check           (the host half: every scenario built and proved on the
                                                     model, every red arm's broken copy assembled)

THE REFERENCE is tools/bbcourse.py's Physics class - the model SPEC.md
128.11.8 binds the guest to ("the guest and bbcourse.Physics do exactly
this") - run on the HOST on the same course part the build compiled.  The
guest is read at chosen marks through its own bss (bzphys.inc's head lists
the words): 128.10.11.3's eight values (nstep, gx, gy, gz, gvx, gvy, gvz,
air) and 128.11.8.1's (the arrows' levels, the Hop's window, the last key
byte, the ball's state and its steps, the squash, the last landing's lvz).
Physics is a function of the step count and the key bytes alone, so the
model is stepped to the guest's nstep and every value compared EXACTLY - no
tolerance: a rounding that differs is a defect, and the first one is where
the guest and the model part.

  1  THE BENCHMARK (B: BENCH, the autopilot through the ramp, 1,200 frames),
     on both cards: at every frame's bz_presented the guest's state equals
     the model's after that many steps of its own autopilot (step_auto) - so
     the CGA's and the Hercules' trajectories are one, though their frames
     hold different numbers of steps.  A benchmark that falls is a route
     that is wrong (128.11.17.1 item 8).
  2  WAVE 1'S FOUR on FIRST, POKED in play mode with no key held (the ball's
     position and velocities written at bz_t0 with bz_pokd = 1; the model
     poked the same way at the guest's nstep and its SAFE cell), every
     frame compared:
       pit    from (5, 5) at gvx 364: off B's lip, over C, into the void:
              killed at the model's step and put back on the model's SAFE
              cell (6, 5), with a CUT (the frame's full write) exactly when
              128.10.8 item 3 says
       lip    from (9, 4) at gvx 100: off B's lip with the floor's gvz; on
              C it is a RUBBER BOUNCE now (wave 2), its lfall and lvz the
              model's at the contact
       rail   from (5, 4) at (-150, -250): into the rail at wy = 3, where gvy
              REBOUNDS now (128.11.8.4) and gvx is kept
       goal   from (12, 6) at gvx 250: the play ENDS the frame after the
              model's goal step (a finish line, grounded or in the air), and
              the face reads `Finished in <s.hh> s` for the final nstep
  3  REPLAYS (SPEC.md 128.11.17.2): each scenario is a LOG the row builds on
     the host (bbcourse.encode_log), writes into bz_rlog and plays with R; at
     the replay's first frame's bz_t0 the ball is poked (or left at the
     course's start), and from there every frame's bz_presented is compared
     to the model stepped through the same key bytes, to the replay's end:
       ramp      the arrows' ramp and coast, each material (rubber, steel, glass)
       hop       a Hop from the ground (Space's key-down edge)
       hopagain  Space again at the Hop's own landing: a Hop at the contact
       stepup    a Hop up FIRST's B ramp, where the airborne margin decides
                 (128.11.8.2 step 5: no shipped course has a half-unit step;
                 the scenario is the one the model says the margin changes)
       grip      Grip held from 300: the brake, never past 0
       catch     a rubber ball dropped 6 units with Grip held: caught at the
                 first contact
       eastwall  P1: held Right + Down into G's east rail on TRIAL
       bumper    steel into the ice strip's bumper rail: 230/256 back
       ice       a coast over TRIAL's ice: no drag
       sand      a coast onto TRIAL's sand
       mat       steel dropped onto TRIAL's mat: bounces, unhurt
       bounce    rubber off H's lip at the cap, over the gap onto G
       stun      steel off H's lip: stunned on F, still for 55 steps
       shatter   glass off H's lip: shattered on F, respawned on H 24 steps
                 later, with the CUT 128.10.8 item 3 says
       ramphop   steel and glass Hop down TRIAL's steep ramp: unhurt
     Each scenario is PROVED on the model before it is run (its events
     there - the hop, the contact, the stun, ...), and each red arm's
     scenario is proved to PART from the broken model (or to raise the
     event the red arm changes), so a green scenario cannot be one that
     does not exercise what it names.

  4  WAVE 3 (SPEC.md 128.12.6, 128.12.13.2): at every frame also 128.12.6.6's
     state - bz_ps, bz_wol, the tube in transit, its segment and steps, the
     entry speed, bz_onp, every prop's last kick and the kick, knock and
     capture counts (Physics.state3), not the display state - from the first
     step after a poke; and on MILL fifteen more replays, built and PROVED on
     the model (the idle steps that put a windmill's gate where a scenario
     needs it SEARCHED, so a re-seeded course re-finds them): knock (the gate
     closed, then swallowed), pass (open: the tunnel), side (along the house
     front into the open doorway), keep (the other windmill's tunnel, out
     along its mouth), kick (at the cap into a post), cluster (a ricochet
     between two posts), post (dropped onto a post's top: it rests there - a
     Hop's apex, 4 px for rubber, is under a post's 8, so it is a drop),
     ride (on the LIFT at its low dock, carried PMAX up with no spin, off
     onto its high rim), hop (a Hop on the rising slab lands back on it),
     land (rubber dropped onto the slab at its lowest settles), fall (the
     owner's preview: rolled off the high rim into the shaft while the slab
     is low, it lands on it), board (rolled onto it at its high dock), under
     (in the shaft under the slab: never lifted, falls),
     launch (the cannon), drop (the chute) with each ball.

--red NAME builds a broken package in a temporary directory (never build/)
and PASSES only if the row FAILS - at its own check:
  slope      the slope term's sign flipped: the benchmark's descent parts
  respawn    the respawn put on the course's START instead of bz_safe: pit
  takeoff    gvz zeroed at a grounded take-off (over no floor, or a floor
             falling away; not a Hop's), as the model's switch: lip
  bounce     the floor's rebound taken from EW, the wall's: bounce parts
  edge       the east test put back to wave 1's (pu > 2,815): eastwall
  stun       no stun: the steel ball bounces on: stun parts
  shatter    the respawn at once, no 24 steps: shatter parts
  absimpact  the impact on -gvz, not relative to the floor: ramphop parts
  airwall    no airborne margin: stepup parts
  gate       the gate judged one step late: knock parts
  kick       the kick's floor at K alone: kick parts
  carry      no carry: hop parts (a Hop on the rising lift comes down early)
  carrys     the carry along +s, wave 3's first design: ride parts (the
             rider moves and spins - the owner's preview)
  stick      bz_onp cleared at a take-off: hop parts
  exit       a windmill's KEEP exit along its entry (the doorway's direction),
             not its mouth's: keep parts
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
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402

BENCH = 1200                   # bzgame.inc BZ_BENCH
FIELDS = ("nstep", "gx", "gy", "gz", "gvx", "gvy", "gvz", "air")
FIELDS2 = ("lvl", "hopw", "kprev", "mst", "mct", "sqf", "lvz")
SCEN = {
    # name: (tile, gvx, gvy, frames at most) - poked in play, no key held
    "pit": ((5, 5), 364, 0, 260),
    "lip": ((9, 4), 100, 0, 120),
    "rail": ((5, 4), -150, -250, 90),
    "goal": ((12, 6), 250, 0, 60),
}
K = BB
CHORD_X = K.K_R | K.K_D        # +wx: Right (+F, -F) and Down (+F, +F)
CHORD_MX = K.K_L | K.K_U       # -wx


def ftime(n):
    """bzphys.inc bz_ftime: hundredths, truncated; a play past 65,535 steps reads as that"""
    return min(n, 0xFFFF) * 2184500 // 1193182


def show(st):
    return "nstep %d gx %06X gy %06X gz %d gvx %d gvy %d gvz %d air %d" % st


def show2(s2):
    return "lvl %s hopw %d kprev %02X mst %d mct %d sqf %d lvz %d" % s2


class Reader:
    """The physics words in ONE read a stop: bz_phs .. bz_phe are one run of
    VARs (bzphys.inc BZ_PHYS_VARS)."""

    def __init__(self, g):
        self.g = g
        s = g.sym
        self.lo = s["bz_phs"]
        self.n = s["bz_phe"] - self.lo
        self.off = {n: s[n] - self.lo for n in (
            "bz_gx", "bz_gy", "bz_gz", "bz_gvx", "bz_gvy", "bz_gvz", "bz_nstep", "bz_air", "bz_lfall", "bz_lvz",
            "bz_nland", "bz_nfall", "bz_resp", "bz_goal", "bz_lvl", "bz_hopw", "bz_kprev", "bz_mst", "bz_mct",
            "bz_sqf", "bz_nbnc", "bz_nstun", "bz_nshat", "bz_nhop")}

    def read(self):
        """-> (state, state2, extras): Physics.state()'s and state2()'s shapes"""
        raw = self.g.m.read(self.g.base + self.lo, self.n)
        o = self.off
        st = (struct.unpack_from("<I", raw, o["bz_nstep"])[0], struct.unpack_from("<I", raw, o["bz_gx"])[0],
              struct.unpack_from("<I", raw, o["bz_gy"])[0], struct.unpack_from("<i", raw, o["bz_gz"])[0],
              struct.unpack_from("<h", raw, o["bz_gvx"])[0], struct.unpack_from("<h", raw, o["bz_gvy"])[0],
              struct.unpack_from("<h", raw, o["bz_gvz"])[0], raw[o["bz_air"]])
        s2 = (tuple(raw[o["bz_lvl"]:o["bz_lvl"] + 4]), raw[o["bz_hopw"]], raw[o["bz_kprev"]], raw[o["bz_mst"]],
              raw[o["bz_mct"]], raw[o["bz_sqf"]], struct.unpack_from("<H", raw, o["bz_lvz"])[0])
        ext = {k: struct.unpack_from("<H", raw, o["bz_" + k])[0]
               for k in ("lfall", "lvz", "nland", "nfall", "nbnc", "nstun", "nshat", "nhop")}
        ext["resp"], ext["goal"] = raw[o["bz_resp"]], raw[o["bz_goal"]]
        ext["s3"] = self.state3(raw) if "bz_ps" in self.g.sym else None
        return st, s2, ext

    def state3(self, raw):
        """wave 3's state (SPEC.md 128.12.6.6) in Physics.state3()'s shape: bz_ps,
        bz_wol's pairs, the tube in transit, its segment and steps left, the entry
        speed, bz_onp, every prop's last kick, the kicks, knock-backs and captures
        - all of it but the display state (bz_ldrw, bz_lage, bz_pline)"""
        s, lo = self.g.sym, self.lo

        def b(n, k=0):
            return raw[s[n] - lo + k]

        def w(n, k=0):
            return struct.unpack_from("<H", raw, s[n] - lo + 2 * k)[0]
        nw = b("bz_wol")
        wol = tuple((b("bz_wol", 1 + 2 * k), b("bz_wol", 2 + 2 * k)) for k in range(min(nw, 9)))
        return (b("bz_ps"), wol, b("bz_tube"), b("bz_tseg"), w("bz_tcnt"), w("bz_tsin"), b("bz_onp"),
                tuple(w("bz_pkick", k) for k in range(BB.PROP_MAX)), w("bz_nkick"), w("bz_nknock"), w("bz_ntube"))


def counts(p):
    return {"nland": p.nland, "nfall": p.nfall, "nbnc": p.nbnc, "nstun": p.nstun, "nshat": p.nshat, "nhop": p.nhop}


def advance(p, n, keys=None):
    """the model to step N (Physics.step_auto for the benchmark; KEYS a list of
    key bytes indexed by the step, or one byte for every step); -> the events"""
    e0 = len(p.events)
    while p.nstep < n:
        if keys is None:
            p.step_auto()
        elif isinstance(keys, int):
            p.step(keys)
        else:
            p.step(keys[p.nstep] if p.nstep < len(keys) else 0)
    return p.events[e0:]


def compare(name, frames, st, s2, ext, p):
    """-> a failure line, or None: the guest's state against the model's - and
    wave 3's (128.12.6.6, Physics.state3) once a step has run since a poke (a
    poke's window refill is the guest's next step's, the model's at once)"""
    if st != p.state() or s2 != p.state2():
        return ("%s frame %d: the guest differs from the model after %d steps:\n      guest %s\n            %s\n"
                "      model %s\n            %s" % (name, frames, st[0], show(st), show2(s2), show(p.state()),
                                                   show2(p.state2())))
    if ext.get("s3") is not None and p.nstep > getattr(p, "_poked_at", -1) and ext["s3"] != p.state3():
        g3, m3 = ext["s3"], p.state3()
        names = ("ps", "wol", "tube", "tseg", "tcnt", "tsin", "onp", "pkick", "nkick", "nknock", "ntube")
        return "%s frame %d: wave 3's state differs from the model's after %d steps: %s" % (
            name, frames, st[0], "; ".join("%s guest %s model %s" % (n, a, b)
                                           for n, a, b in zip(names, g3, m3) if a != b))
    want = counts(p)
    got = {k: ext[k] for k in want}
    if got != want:
        return "%s frame %d: the counters %s against the model's %s" % (name, frames, got, want)
    return None


def bench(g, crs):
    """Part 1: the benchmark, the guest against the model at every bz_presented."""
    m, tag = g.m, g.tag
    rd = Reader(g)
    p = BB.Physics(crs)
    fails = []
    m.bp_exec(g.a("bz_presented"))
    g.key("KeyB")
    frames, ev = 0, []
    first = True
    while frames < BENCH:
        m.run()
        assert m.wait_stop(60) == "breakpoint", "the benchmark stopped presenting (frame %d)" % frames
        if first:
            g.check_base()
            assert g.b("bz_mode") == 1 and g.b("bz_crs") == R.CRS_K["bench"], "B did not run BENCH's benchmark"
            assert g.b("bz_mat") == crs.ball, "B rolls material %d, BENCH's ball is %d" % (g.b("bz_mat"), crs.ball)
            first = False
        frames += 1
        st, s2, ext = rd.read()
        if st[0] < p.nstep:
            fails.append("frame %d: the guest's nstep went BACK to %d (the model is at %d)" % (frames, st[0], p.nstep))
            break
        ev += advance(p, st[0])
        bad = compare("the benchmark", frames, st, s2, ext, p)
        if bad:
            fails.append(bad)
            break
    m.bp_exec()
    m.run()
    if not fails:
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark ends", guest=120)
        dropped(g, "the benchmark")
    kinds = {}
    for e in ev:
        kinds[e[0]] = kinds.get(e[0], 0) + 1
    print("%s benchmark: %d frames, %d steps, the guest equal to bbcourse.Physics at every bz_presented: %s; "
          "the run's events %s" % (tag, frames, p.nstep, "yes" if not fails else "NO",
                                   ", ".join("%s %d" % kv for kv in sorted(kinds.items())) or "none"),
          flush=True)
    if not fails and p.nfall:
        fails.append("the benchmark FELL %d times under the model: its route is wrong (SPEC.md 128.11.17.1 8)"
                     % p.nfall)
    return fails, p.nstep


def outwin(px, py, R0, c0, Wc, rl):
    """bz_outwin: the footprint (128.4's 20 x 16 from px & ~3) not wholly inside the window"""
    first = px >> 3
    last = ((px >> 2) + 4) >> 1
    top = R0 * rl
    return first < c0 or last >= c0 + Wc or py < top or py > top + 200 - 16


def cut_check(g, name, frames, ev, win, Wc, rl, cuts, fails):
    """a respawn in this frame's steps takes a CUT (the frame's full write) exactly
    when 128.10.8 item 3 says: the respawned footprint not wholly inside the
    window the frame began with"""
    resp = [e for e in ev if e[0] == "respawn"]
    if not resp:
        return
    px, py = g.w("bz_px"), g.w("bz_py")
    want = outwin(px, py, win[0], win[1], Wc, rl)
    got = bool(g.b("bz_full"))
    cuts.append((frames, resp[0][1], resp[0][2], want, got))
    if want != got:
        fails.append("%s frame %d: a respawn on %s %s a CUT ([bz_full] %d), but 128.10.8 item 3 says %s "
                     "(footprint %d,%d against the window R0 %d c0 %d)" % (
                         name, frames, resp[0][2], "took" if got else "took no", got,
                         "cut" if want else "no cut", px, py, win[0], win[1]))


def scenario(g, crs, name):
    """Part 2: one of wave 1's poked scenarios on FIRST in play mode."""
    m, tag = g.m, g.tag
    (wx, wy), gvx, gvy, nmax = SCEN[name]
    rd = Reader(g)
    fails = []
    g.key("Enter")
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 5, "play mode on FIRST runs", guest=60)
    m.pause()
    g.check_base()
    assert g.b("bz_mode") == 0 and g.b("bz_crs") == R.CRS_K["first"], "Enter did not play FIRST"
    wk = R.Walker(g, t0=True)
    m.bp_exec(wk.t0, wk.pr)
    while wk.next() != "t0":
        pass
    st0, s20, ext0 = rd.read()
    safe = tuple(m.read(g.a("bz_safe"), 2))
    p = MarkPhysics(crs, play=True, mat=g.b("bz_mat")).poke(wx, wy, gvx, gvy)
    p.nstep, p.safe = st0[0], safe             # the model picks the play up where the guest is
    p._poked_at = st0[0]
    p.lvl, p.hopw, p.kprev = list(s20[0]), s20[1], s20[2]
    for k in ("nland", "nfall", "nbnc", "nstun", "nshat", "nhop"):
        setattr(p, k, ext0[k])
    R.poke_ball(g, p.gx, p.gy, p.gz, p.gvx, p.gvy, p.gvz, air=0)
    Wc = g.w("bz_W")
    rl = R.RL[tag]
    win = (g.w("bz_R0"), g.w("bz_c0"))          # the window this frame begins with
    frames, last, ended, cuts = 0, None, False, []
    contact = None
    while frames < nmax:
        k = wk.next()
        if k == "t0":
            win = (g.w("bz_R0"), g.w("bz_c0"))
            if g.b("bz_goal"):                  # bz_t0 ends the play on this frame: it presents nothing
                ended = True
                break
            continue
        if k != "pr":
            continue
        frames += 1
        st, s2, ext = rd.read()
        ev = advance(p, st[0], 0)
        bad = compare(name, frames, st, s2, ext, p)
        if bad:
            fails.append(bad)
            break
        cut_check(g, name, frames, ev, win, Wc, rl, cuts, fails)
        for e in ev:
            if e[0] in ("land", "bounce") and contact is None:
                contact = (frames, e[1], (p.lfall, p.lvz))
                if (ext["lfall"], ext["lvz"]) != (p.lfall, p.lvz):
                    fails.append("%s: the contact at step %d recorded lfall %d lvz %d; the model %d %d"
                                 % (name, e[1], ext["lfall"], ext["lvz"], p.lfall, p.lvz))
        if (ext["nfall"], ext["goal"]) != (p.nfall, p.goal):
            fails.append("%s frame %d: nfall %d goal %d against the model's %d %d" % (
                name, frames, ext["nfall"], ext["goal"], p.nfall, p.goal))
            break
        last = st
        if name != "goal" and frames >= 8 and _done(name, p):
            break
    out = {"frames": frames, "events": list(p.events), "cuts": cuts, "landed": contact, "model": p}
    face = None
    if name == "goal" and not fails:
        if not ended:
            fails.append("goal: the play did not end within %d frames (the model's goal at %s)" % (
                nmax, [e[1] for e in p.events if e[0] == "goal"]))
        else:
            gs = [e[1] for e in p.events if e[0] == "goal"]
            if last is None or not gs or not (gs[0] <= last[0]):
                fails.append("goal: the play ended after step %s but the model's goal step is %s" % (
                    last[0] if last else None, gs))
            n = last[0] if last else 0
            face = goal_face(g, n)
            want = "Finished in %d.%02d s" % divmod(ftime(n), 100)
            if face is None or not face.startswith(want):
                fails.append("goal: the face reads %r, the model's time is %r" % (face, want))
            if not g.b("bz_fin"):
                fails.append("goal: [bz_fin] is not set after the play reached the goal")
    else:
        m.bp_exec()
        m.run()
        if not ended:
            g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0, "the %s scenario's play ends" % name, guest=60)
        dropped(g, name)
    out["face"] = face
    _say(tag, name, out, fails)
    if name == "pit" and not fails:
        r = [e for e in p.events if e[0] == "respawn"]
        if not r or r[0][2] != (6, 5):
            fails.append("pit: the model's respawn was %s, not on the SAFE cell (6, 5)" % r)
    if name == "lip" and not fails and (contact is None or not [e for e in p.events if e[0] == "takeoff"]):
        fails.append("lip: no take-off and contact in %d frames (%s)" % (frames, p.events[:4]))
    if name == "rail" and not fails and not p._reb:
        fails.append("rail: the model never REBOUNDED gvy off the rail with gvx kept")
    return fails, out


def _done(name, p):
    """the scenario has shown what it is for, and a few frames past it"""
    def at(*kinds):
        return [e[1] for e in p.events if e[0] in kinds]
    if name == "pit":
        return at("respawn") and p.nstep > at("respawn")[0] + 8
    if name == "lip":
        return at("land", "bounce") and p.nstep > at("land", "bounce")[0] + 8
    if name == "rail":
        return p._reb and p.nstep > 40
    return False


def goal_face(g, n):
    """The face's lines as bz_line draws them after the play: -> the
    `Finished in` one, or None."""
    m = g.m
    m.bp_exec(g.a("bz_line"))
    found = None
    for _ in range(40):
        m.run()
        if m.wait_stop(20) != "breakpoint":
            break
        # at bz_line's entry DI is the line's end (the bytes past it are the
        # last longer line's, not yet padded over), and bz_lstr opened the
        # line with a cell of margin (the padding is the erase)
        n = (m.regs()["di"] - g.sym["bz_lbuf"]) & 0xFFFF
        line = m.read(g.a("bz_lbuf"), min(n, 88)).decode("latin-1").strip()
        if line.startswith("Finished in"):
            found = line
            break
    m.bp_exec()
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 0, "the goal's play to have ended", guest=60)
    dropped(g, "the goal")
    return found


def dropped(g, what):
    """Wait for the LAUNCH to return, not only the play: bz_fs drops inside
    the bracket, and a key pressed while the bracket is still being left can
    be lost (the soak's first pass lost the Hercules' Enter after the
    benchmark).  bz_launch's .drop writes bz_cseg and bz_bseg 0 last, after
    both op_drop calls (bonanza_exit.py waits on the same words)."""
    M.until(g.m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0,
            "the launch to drop its parts after %s" % what, guest=30)


def _say(tag, name, out, fails):
    p = out["model"]
    print("%s %s: %d frames to step %d, the guest equal to the model at every bz_presented: %s; events %s%s%s%s" % (
        tag, name, out["frames"], p.nstep, "yes" if not fails else "NO",
        ", ".join("%s@%d" % (e[0], e[1]) for e in out["events"] if e[0] != "corner") or "none",
        "; cuts %s" % ["frame %d step %d on %s: want %s got %s" % c for c in out["cuts"]] if out["cuts"] else "",
        "; first contact frame %d step %d (lfall, lvz) %s" % out["landed"] if out.get("landed") else "",
        "; face %r" % out.get("face") if out.get("face") else ""), flush=True)


class MarkPhysics(BB.Physics):
    """the model, noting the rail's REBOUND: a step that turns gvy from
    negative to positive while gvx stays non-zero, on the ground"""
    _reb = False

    def step(self, keys=0):
        g0 = (self.gvx, self.gvy)
        r = BB.Physics.step(self, keys)
        if g0[1] < 0 < self.gvy and self.gvx and not self.air:
            self._reb = True
        return r


# ---- the replays (SPEC.md 128.11.17.2) -----------------------------------------
POKE = ("gx", "gy", "gz", "gvx", "gvy", "gvz", "air", "ztop")


def poke_of(p):
    """the fields a scenario's poke writes, off a Physics poked on the host"""
    d = {k: getattr(p, k) for k in POKE}
    d["lvl"] = list(p.lvl)
    return d


def model(crs, mat, poke, **kw):
    """the model of a replay: the course's start, poked as the guest will be -
    the window refilled round the poked cell (the guest's bz_pokd refill) and,
    on a slab, carried (bz_onp)"""
    p = BB.Physics(R.course(crs), play=True, mat=mat, **kw)
    if poke:
        for k in POKE:
            setattr(p, k, poke[k])
        p.lvl = list(poke["lvl"])
        p.onp = poke.get("onp", 0)
        p._fill(p.gx >> 12, p.gy >> 12)
        p._ps()
        p._derive(True)
        p._poked_at = p.nstep
    return p


def run_keys(crs, mat, poke, keys, **kw):
    p = model(crs, mat, poke, **kw)
    for k in keys:
        p.step(k)
        if p.goal:
            break
    return p


def parts(crs, mat, poke, keys, **red):
    """does the broken model PART from the model somewhere over KEYS? -> the step, or None"""
    a, b = model(crs, mat, poke), model(crs, mat, poke, **red)
    for i, k in enumerate(keys):
        a.step(k)
        b.step(k)
        if a.state() + a.state2() + a.state3() != b.state() + b.state2() + b.state3():
            return i + 1
        if a.goal:
            break
    return None


def tile(crs, mat, wx, wy, gvx=0, gvy=0, lvl=(0, 0, 0, 0), lift=0):
    """a poke on tile (wx, wy)'s centre at a ground velocity, LIFT px in the air"""
    p = BB.Physics(R.course(crs), play=True, mat=mat).poke(wx, wy, gvx, gvy)
    p.lvl = list(lvl)
    if lift:
        p.gz += lift << 8
        p.air, p.ztop = 1, p.gz >> 8
    p._derive(True)
    return poke_of(p)


def shot(mat, v=BB.VMAXG, off=0):
    """bbcourse._trial_shot's poke: on H 20 gu before its lip at gvx V, the chord's levels full"""
    p = BB.Physics(R.course("trial"), play=True, mat=mat).poke(BB.TRIAL_H[0][1] - 1, 11)
    lip = BB.TRIAL_H[0][1] * BB.TILE
    p.gx = (lip << 8) - (20 << 8)
    p.gy = ((11 * BB.TILE + 8) << 8) + (off << 8)
    p.gvx = v
    p.lvl = [0, BB.LVL_MAX, 0, BB.LVL_MAX]
    p._derive(True)
    return poke_of(p)


def ev_of(crs, mat, poke, keys):
    p = run_keys(crs, mat, poke, keys)
    return p, [e[0] for e in p.events]


def replays():
    """-> [scenario dicts]: name, course, material, poke (None: the start), the
    key bytes, the proof on the model (a description and a bool), and the red
    arm the scenario is the check of (the model's switch, when it has one)"""
    S = []

    def add(name, crs, mat, poke, keys, what, ok, red=None):
        S.append({"name": name, "crs": crs, "mat": mat, "poke": poke, "keys": keys, "what": what,
                  "ok": bool(ok), "red": red})
    for mat in range(3):                          # the ramp and the coast, from TRIAL's start
        keys = [K.K_R] * 12 + [0] * 2 + [K.K_R] * 10 + [CHORD_X] * 24 + [0] * 30
        p, ev = ev_of("trial", mat, None, keys)
        moved = model("trial", mat, None)
        mv = []
        for k in keys:
            moved.step(k)
            mv.append(moved.gvx)
        add("ramp-%s" % BB.MAT_NAMES[mat], "trial", mat, None, keys, "it moves and coasts (gvx peak %d)" % max(mv),
            max(mv) > 0 and not p.nfall)
    keys = [0] * 5 + [K.K_HOP] * 3 + [0] * 40
    p, ev = ev_of("trial", 0, None, keys)
    add("hop", "trial", 0, None, keys, "a Hop from the ground", "hop" in ev)
    base = [0] * 5 + [K.K_HOP] * 2 + [0] * 60
    p, ev = ev_of("trial", 0, None, base)
    c1 = [e[1] for e in p.events if e[0] in ("bounce", "land")]
    t = c1[0] if c1 else 30
    keys = [0] * 5 + [K.K_HOP] * 2 + [0] * (t - 9) + [K.K_HOP] * 2 + [0] * 40
    p, ev = ev_of("trial", 0, None, keys)
    add("hopagain", "trial", 0, None, keys, "Space at the Hop's own landing (step %d) hops at the contact" % t,
        ev.count("hop") == 1 and "hopc" in ev)
    pk = tile("first", 0, 8, 4, -200, 0, (BB.LVL_MAX, 0, BB.LVL_MAX, 0))
    keys = [CHORD_MX] * 2 + [CHORD_MX | K.K_HOP] + [CHORD_MX] * 47
    p, ev = ev_of("first", 0, pk, keys)
    add("stepup", "first", 0, pk, keys, "a Hop up B's ramp the airborne margin decides", "hop" in ev,
        red={"_no_airclimb": True})
    pk = tile("trial", 0, 5, 11, 300, 0)
    keys = [K.K_GRIP] * 45 + [0] * 10
    p, ev = ev_of("trial", 0, pk, keys)
    add("grip", "trial", 0, pk, keys, "Grip from 300 stops it on H", p.gvx == 0 and "takeoff" not in ev)
    pk = tile("trial", 0, 10, 11, lift=48)
    keys = [K.K_GRIP] * 80
    p, ev = ev_of("trial", 0, pk, keys)
    add("catch", "trial", 0, pk, keys, "a 6-unit drop caught at the first contact", "land" in ev
        and "bounce" not in ev and ev_of("trial", 0, pk, [0] * 80)[1].count("bounce") > 0)
    pk = tile("trial", 0, 17, 11, 300, 0, (0, BB.LVL_MAX, 0, BB.LVL_MAX))
    keys = [CHORD_X] * 120
    add("eastwall", "trial", 0, pk, keys, "held into G's east rail", True, red={"_east_w1": True})
    pk = tile("trial", 1, 13, 17, 0, -200)
    keys = [0] * 40
    p, ev = ev_of("trial", 1, pk, keys)
    q = model("trial", 1, pk)
    back = None
    for k in keys:
        g0 = q.gvy
        q.step(k)
        if g0 < 0 < q.gvy:
            back = (g0, q.gvy)
            break
    add("bumper", "trial", 1, pk, keys, "steel off the bumper rail: %s" % (back,),
        back is not None and back[1] == (BB.E_BUMPER * -back[0]) >> 8)
    pk = tile("trial", 0, 15, 17, -300, 0)
    keys = [0] * 20
    p, ev = ev_of("trial", 0, pk, keys)
    add("ice", "trial", 0, pk, keys, "a coast over ice keeps -300", p.gvx == -300)
    pk = tile("trial", 0, 12, 18, -300, 0)
    keys = [0] * 60
    p, ev = ev_of("trial", 0, pk, keys)
    q = model("trial", 0, pk)
    on = 0
    for k in keys:
        q.step(k)
        on += q.cell(q.gx >> 12, q.gy >> 12)[5] == BB.SURF_SAND
        if q.goal:
            break
    add("sand", "trial", 0, pk, keys, "a coast onto the sand (%d steps on it)" % on, on > 0)
    pk = tile("trial", 1, BB.TRIAL_MAT[0], BB.TRIAL_MAT[1], lift=48)
    keys = [0] * 150
    p, ev = ev_of("trial", 1, pk, keys)
    add("mat", "trial", 1, pk, keys, "steel dropped onto the mat bounces, unhurt",
        "bounce" in ev and "stun" not in ev)
    pk = shot(0)
    keys = [CHORD_X] * 150
    p, ev = ev_of("trial", 0, pk, keys)
    add("bounce", "trial", 0, pk, keys, "rubber off H's lip bounces on F, over the gap",
        "bounce" in ev and not p.nfall and p.m["EF"] != p.m["EW"])
    pk = shot(1)
    keys = [CHORD_X] * 120
    p, ev = ev_of("trial", 1, pk, keys)
    add("stun", "trial", 1, pk, keys, "steel stunned on F", "stun" in ev, red={"_no_stun": True})
    pk = shot(2)
    keys = [CHORD_X] * 120
    p, ev = ev_of("trial", 2, pk, keys)
    add("shatter", "trial", 2, pk, keys, "glass shattered on F and respawned 24 steps later",
        "shatter" in ev and "respawn" in ev)
    for mat in (1, 2):
        pk = tile("trial", mat, 17, 11, 0, BB.VMAXG, (BB.LVL_MAX, 0, 0, BB.LVL_MAX))
        keys = [K.K_L | K.K_D] * 20 + [K.K_L | K.K_D | K.K_HOP] + [K.K_L | K.K_D] * 49
        p, ev = ev_of("trial", mat, pk, keys)
        add("ramphop-%s" % BB.MAT_NAMES[mat], "trial", mat, pk, keys, "a Hop down the steep ramp, unhurt",
            "hop" in ev and "stun" not in ev and "shatter" not in ev, red={"_abs_impact": True})
    return S + mill_replays()


# ---- MILL (SPEC.md 128.12.6, 128.12.13.2): every obstacle, as replays ------------
def mill_rec(kind, at=None):
    return next(r for r in R.course("mill").part["props"] if r["kind"] == kind and (at is None or r["at"] == at))


def mill_poke(wx, wy, gvx=0, gvy=0, mat=0, dgx=0, gy=None, lift=0):
    """a MILL poke: tile (wx, wy)'s centre (DGX gu along x, or GY in 24.8), at
    a ground velocity, LIFT px up"""
    p = BB.Physics(R.course("mill"), play=True, mat=mat).poke(wx, wy, gvx, gvy)
    p.gx += dgx << 8
    if gy is not None:
        p.gy = gy
    if lift:
        p.gz += lift << 8
        p.air, p.ztop = 1, p.gz >> 8
    p._derive(True)
    return poke_of(p)


def slab_poke(n0, off=(8, 8), lift=0, zoff=0, onp=True, mat=0):
    """the ball on (or over, or under) the LIFT's slab, in its shaft, as it
    stands at step N0"""
    P = mill_rec(BB.PK_PLATFORM)
    p = BB.Physics(R.course("mill"), play=True, mat=mat)
    A, I = P["at"], BB.plat_pos(P, n0 & 0xFFFF)
    p.gx, p.gy = (16 * A[0] + off[0]) << 8, (16 * A[1] + off[1]) << 8
    p.gz = (P["hP"] << 8) + I + ((zoff + lift) << 8)
    p.air = 1 if (lift or zoff < 0) else 0
    p.ztop = p.gz >> 8
    p.gvx = p.gvy = p.gvz = 0
    p._derive(True)
    d = poke_of(p)
    d["onp"] = P["i"] + 1 if onp else 0
    return d


def mill_replays():
    """SPEC.md 128.12.13.2's thirteen MILL scenarios (fifteen replays: drop
    with each ball), each found and PROVED on the model - the idle steps that
    put the windmill's gate where the scenario needs it are SEARCHED, so a
    re-seeded course re-finds them - and each red arm's broken model shown to
    part from it.  -> [scenario dicts], replays()'s shape"""
    S = []
    c = R.course("mill")

    def add(name, mat, poke, keys, what, ok, red=None):
        S.append({"name": name, "crs": "mill", "mat": mat, "poke": poke, "keys": keys, "what": what,
                  "ok": bool(ok), "red": red})

    def evs(p, *kinds):
        return [e for e in p.events if e[0] in kinds]
    W1 = mill_rec(BB.PK_WINDMILL, (9, 9))           # the route's windmill (seed 16)
    W0 = mill_rec(BB.PK_WINDMILL, (7, 9))           # the other (seed 36)
    UPR = K.K_U | K.K_R

    def gate(W, want):
        pk = mill_poke(W["at"][0], W["at"][1] + 2)
        for d in range(W["mask"] + 1):
            keys = [0] * d + [UPR] * 200
            p, _ = ev_of("mill", 0, pk, keys)
            g = evs(p, "knock", "capture")
            if g and g[0][0] == want and g[0][2] == W["i"] and evs(p, "exit"):
                return pk, keys[:evs(p, "exit")[0][1] + 20], p
        return pk, [0], None
    pk, keys, p = gate(W1, "knock")
    add("knock", 0, pk, keys, "held at the doorway of %s with the gate CLOSED: knocked back (%s), then swallowed"
        % (W1["at"], [(e[0], e[1]) for e in evs(p, "knock", "capture")] if p else None),
        p and evs(p, "capture") and evs(p, "knock")[0][1] < evs(p, "capture")[0][1], red={"_gate_late": True})
    pk, keys, p = gate(W1, "capture")
    add("pass", 0, pk, keys, "the gate OPEN: swallowed at once, through the tunnel to its exit (%s)"
        % ([(e[0], e[1]) for e in evs(p, "capture", "exit")] if p else None), p and not evs(p, "knock"))
    pk = mill_poke(W1["at"][0] - 1, W1["at"][1], gy=(16 * W1["at"][1] + BB.RAD) << 8)
    for d in range(W1["mask"] + 1):
        keys = [0] * d + [K.K_R] * 80
        p, _ = ev_of("mill", 0, pk, keys)
        g = evs(p, "knock", "capture")
        if g and g[0][0] == "capture":
            break
    add("side", 0, pk, keys[:g[0][1] + 40] if g else keys,
        "rolled along the house front into the open doorway of %s from the side (%s)" % (
            W1["at"], [(e[0], e[1]) for e in g] if g else None), g and g[0][0] == "capture" and not p.nfall)
    pk, keys, p = gate(W0, "capture")
    add("keep", 0, pk, keys, "the KEEP tunnel of %s: out along its mouth at max(s_in, 64) (%s)" % (
        W0["at"], [e for e in evs(p, "exit")] if p else None), p and evs(p, "exit"), red={"_exit_vel": True})
    B2 = mill_rec(BB.PK_BUMPER, (14, 19))
    pk = mill_poke(B2["at"][0] - 2, B2["at"][1] - 2, BB.VMAXG, BB.VMAXG)     # diagonal: past K, the rail's
    keys = [0] * 60                                                          # floor shows (K 384, O23)
    p, _ = ev_of("mill", 0, pk, keys)
    add("kick", 0, pk, keys, "diagonally at the cap into the post at %s: kicked (%s)" % (
        B2["at"], [(e[1], e[2], e[4]) for e in evs(p, "kick")]), evs(p, "kick") and not p.nfall,
        red={"_kick_k": True})
    pk = mill_poke(16, 19, 0, 64)
    keys = [0] * 60
    p, _ = ev_of("mill", 0, pk, keys)
    who = [e[2] for e in evs(p, "kick")]
    add("cluster", 0, pk, keys, "between the posts at (16, 18) and (16, 20): a ricochet (%s)" % who,
        len(set(who)) >= 2 and not p.nfall)
    B3 = mill_rec(BB.PK_BUMPER, (16, 18))
    pk = mill_poke(B3["at"][0], B3["at"][1], lift=B3["ph"] + 16)
    keys = [0] * 120
    p, _ = ev_of("mill", 0, pk, keys)
    top = (BB.Physics.h4(c and p.cell(*B3["at"]), 8, 8) >> 2) + B3["ph"]
    add("post", 0, pk, keys, "dropped onto the post at %s: it rests on the top (z %d, the top %d), unkicked "
        "(a Hop's apex, 4 px for rubber, is under a post's 8)" % (B3["at"], p.gz >> 8, top),
        not p.air and p.gz >> 8 == top and not evs(p, "kick"))
    P = mill_rec(BB.PK_PLATFORM)
    per = P["mask"] + 1
    n_dep = next(n for n in range(per) if BB.plat_pos(P, n) == 0 and BB.plat_pos(P, n + 1) > 0)
    n_arr = next(n for n in range(n_dep, n_dep + per) if BB.plat_pos(P, n) == P["pmax"])
    hi_rim, hi_in = BB._plat_rim(c, P, P["hT"])
    hi_out = {K.K_R | K.K_D: K.K_L | K.K_U, K.K_L | K.K_U: K.K_R | K.K_D,
              K.K_L | K.K_D: K.K_R | K.K_U, K.K_R | K.K_U: K.K_L | K.K_D}[hi_in]
    pk = slab_poke(0)
    keys = [0] * (n_arr + 8) + [hi_out] * 60
    p = run_keys("mill", 0, pk, keys)
    q = model("mill", 0, pk)
    turn = lambda r: (BB.sprite(r, 0), BB.sprite(r, 1)[0], BB.sprite(r, 1)[1] & ~8)
    f0, spin = turn(q), 0
    for k in keys[:n_arr + 8]:
        q.step(k)
        spin += turn(q) != f0
    carried = (q.gx - pk["gx"], q.gy - pk["gy"], q.gz - pk["gz"])
    add("ride", 0, pk, keys, "on the LIFT at its low dock, carried %s (x, y, z; PMAX %d) to its high dock with no "
        "spin on the way (%d steps whose roll frame turned), off onto its high rim" % (carried, P["pmax"], spin),
        carried == (0, 0, P["pmax"]) and not spin and not p.nfall and not p.air, red={"_carry_s": True})
    pk = slab_poke(0)
    keys = [0] * (n_dep + 20) + [K.K_HOP] + [0] * 70
    p = run_keys("mill", 0, pk, keys)
    add("hop", 0, pk, keys, "a Hop on the RISING slab at step %d lands back on it (%s)" % (
        n_dep + 21, [(e[0], e[1]) for e in evs(p, "hop", "bounce", "land")][:4]),
        evs(p, "hop") and not p.nfall and p.onp == P["i"] + 1 and not p.air, red={"_stick": True})
    for lift in range(40, 4, -4):
        pk = slab_poke(0, off=(10, 6), lift=lift, onp=False)
        keys = [0] * 200
        p = run_keys("mill", 0, pk, keys)
        b = evs(p, "bounce", "land")
        if b and b[0][1] < n_dep and not p.nfall and p.onp == P["i"] + 1 and not p.air:
            break
    add("land", 0, pk, keys, "rubber dropped %d px onto the slab at its LOWEST (its first contact at step %s, the "
        "slab docked low until %d): it settles on it and rides" % (lift, b[0][1] if b else None, n_dep),
        b and b[0][1] < n_dep and not p.nfall and p.onp == P["i"] + 1 and not p.air)
    ux, uy = P["at"][0] - hi_rim[0], P["at"][1] - hi_rim[1]
    pk = mill_poke(hi_rim[0], hi_rim[1], 32 * ux, 32 * uy, dgx=9 * ux)       # its centre just over the shaft
    if uy:
        pk["gy"] += (9 * uy) << 8
    keys = [0] * 160
    p = run_keys("mill", 0, pk, keys)
    q = model("mill", 0, pk)
    first = None
    for k in keys:
        q.step(k)
        if first is None and evs(q, "bounce", "land"):
            first = (evs(q, "bounce", "land")[0], q.onp == P["i"] + 1,
                     (q.gx >> 12, q.gy >> 12) == tuple(P["at"]), BB.plat_pos(P, q.nstep & 0xFFFF) >> 8)
    add("fall", 0, pk, keys, "the owner's preview: rolled off the high rim %s into the shaft while the slab is LOW "
        "(6 units down): its first contact %s is ON the slab (risen %s px) and carries it, and it is never "
        "respawned" % (hi_rim, first[0][:2] if first else None, first[3] if first else None),
        first and first[1] and first[2] and not p.nfall)
    pk = mill_poke(*hi_rim)
    keys = [0] * (n_arr + 4) + [hi_in] * 60
    p = run_keys("mill", 0, pk, keys)
    q = model("mill", 0, pk)
    boarded = False
    for k in keys:
        q.step(k)
        boarded = boarded or bool(q.onp)
    add("board", 0, pk, keys, "waiting on the high rim %s, rolled onto the slab at its HIGHEST dock: boarded" % (
        hi_rim,), boarded and not p.nfall)
    pk = slab_poke(n_dep + 4, zoff=-10, onp=False)
    keys = [0] * 80
    p = model("mill", 0, pk)
    lifted = False
    for k in keys:
        p.step(k)
        lifted = lifted or bool(p.onp)
    add("under", 0, pk, keys, "in the shaft under the slab: never lifted onto it, it falls (%s)" % (
        [e[0] for e in p.events][:3]), p.nfall and not lifted)
    TL = next(r for r in c.part["props"] if r["kind"] == BB.PK_TUBE and r["sub"] == BB.TK_LAUNCH)
    TD = next(r for r in c.part["props"] if r["kind"] == BB.PK_TUBE and r["sub"] == BB.TK_DROP)
    pk = mill_poke(*TL["at"])
    keys = [0] * 160
    p, _ = ev_of("mill", 0, pk, keys)
    add("launch", 0, pk, keys, "the cannon at %s: swallowed, fired, landed (%s)" % (
        TL["at"], [(e[0], e[1]) for e in evs(p, "capture", "exit", "bounce", "land")][:4]),
        evs(p, "capture") and evs(p, "exit") and evs(p, "bounce", "land") and not p.nfall)
    for mat, out in ((0, "bounce"), (1, "stun"), (2, "shatter")):
        pk = mill_poke(*TD["at"], mat=mat)
        keys = [0] * 100
        p, _ = ev_of("mill", mat, pk, keys)
        add("drop-%s" % BB.MAT_NAMES[mat], mat, pk, keys, "the chute at %s, %s: %s (%s)" % (
            TD["at"], BB.MAT_NAMES[mat], out, [(e[0], e[1]) for e in evs(p, "capture", "exit", out)][:3]),
            evs(p, "capture") and evs(p, "exit") and evs(p, out))
    return S


def prove(S):
    """the host's proof of each scenario: -> failure lines (empty: all proved)"""
    bad = []
    for s in S:
        if not s["ok"]:
            bad.append("replay %s: the model does not show what the scenario is for (%s)" % (s["name"], s["what"]))
        if s["red"]:
            at = parts(s["crs"], s["mat"], s["poke"], s["keys"], **s["red"])
            if at is None:
                bad.append("replay %s: the broken model %s never parts from the model over its %d steps: the "
                           "scenario cannot catch its red arm" % (s["name"], s["red"], len(s["keys"])))
            else:
                s["parts_at"] = at
    return bad


def prove_wave1():
    """the host's proof of wave 1's scenarios and red arms on the wave-2 model:
    the pit reaches its SAFE cell's respawn, the lip and the bench part from
    their broken models.  -> (failure lines, report lines)"""
    bad, say = [], []
    first = R.course("first")
    for name in ("pit", "lip", "rail", "goal"):
        (wx, wy), gvx, gvy, n = SCEN[name]
        p = MarkPhysics(first, play=True).poke(wx, wy, gvx, gvy)
        for _ in range(2 * n):
            p.step(0)
            if p.goal or (name == "pit" and p.nfall):
                break
        kinds = [e[0] for e in p.events if e[0] != "corner"]
        ok = {"pit": [e[2] for e in p.events if e[0] == "respawn"][:1] == [(6, 5)] and
              (6, 5) != BB.Grid(first.cga).start, "lip": "takeoff" in kinds and "bounce" in kinds,
              "rail": p._reb, "goal": p.goal}[name]
        say.append("wave 1's %s on the model: %s" % (name, ", ".join(kinds) or "none"))
        if not ok:
            bad.append("scenario %s: the model does not show it (%s)" % (name, kinds))
    (wx, wy), gvx, gvy, n = SCEN["lip"]
    a = BB.Physics(first, play=True).poke(wx, wy, gvx, gvy)
    b = BB.Physics(first, play=True, _takeoff_zero=True).poke(wx, wy, gvx, gvy)
    at = None
    for i in range(2 * n):
        a.step(0)
        b.step(0)
        if a.state() != b.state():
            at = i + 1
            break
    say.append("the takeoff red's model parts from the lip's at step %s" % at)
    if at is None:
        bad.append("scenario lip cannot catch the takeoff red: its broken model never parts")
    bench = R.course("bench")
    a, b = BB.Physics(bench), BB.Physics(bench, _slope_sign=-1)
    at = None
    for i in range(1400):
        a.step_auto()
        b.step_auto()
        if a.state() != b.state():
            at = i + 1
            break
    say.append("the slope red's model parts from the benchmark's at step %s" % at)
    if at is None:
        bad.append("the benchmark cannot catch the slope red: its broken model never parts")
    return bad, say


def replay(g, s):
    """Part 3: one scenario as a REPLAY: its log in bz_rlog, R, the poke at the
    first frame's bz_t0, every frame against the model, to the replay's end."""
    m, tag, name = g.m, g.tag, s["name"]
    rd = Reader(g)
    fails = []
    log = R.make_log(s["keys"], R.CRS_K[s["crs"]], s["mat"])
    m.pause()
    g.write_log(log)
    wk = R.Walker(g, t0=True)
    m.bp_exec(wk.t0)
    m.run()                                     # (paused for the write: R needs a running guest,
    g.key("KeyR")                               # and wait_stop measures from this resume)
    assert m.wait_stop(60) == "breakpoint", "R did not start the replay"
    r = m.regs()
    assert ((r["cs"] << 4) + r["ip"]) & 0xFFFFF == wk.t0, "R's launch stopped somewhere but bz_t0"
    g.check_base()
    if g.b("bz_mode") != 2 or g.b("bz_crs") != R.CRS_K[s["crs"]] or g.b("bz_mat") != s["mat"]:
        fails.append("%s: R launched mode %d on course %d with material %d, not the log's replay of %d with %d" % (
            name, g.b("bz_mode"), g.b("bz_crs"), g.b("bz_mat"), R.CRS_K[s["crs"]], s["mat"]))
    p = model(s["crs"], s["mat"], s["poke"])
    if s["poke"]:
        pk = s["poke"]
        R.poke_ball(g, pk["gx"], pk["gy"], pk["gz"], pk["gvx"], pk["gvy"], pk["gvz"], air=pk["air"],
                    ztop=pk["ztop"], lvl=pk["lvl"])
        if "bz_onp" in g.sym:                   # wave 3: carried by the slab, or not
            g.putb("bz_onp", pk.get("onp", 0))
            g.putb("bz_ps", (g.b("bz_ps") & ~4) | (4 if pk.get("onp") else 0))
    Wc, rl = g.w("bz_W"), R.RL[tag]
    win = (g.w("bz_R0"), g.w("bz_c0"))
    wk.arm()
    frames, cuts = 0, []
    while not fails:
        k = wk.next()
        if k == "t0":
            win = (g.w("bz_R0"), g.w("bz_c0"))
            if g.b("bz_goal") or not (g.b("bz_rn") or g.w("bz_rruns")):
                break                           # the replay's end: this bz_t0 leaves the bracket
            continue
        if k != "pr":
            continue
        frames += 1
        st, s2, ext = rd.read()
        ev = advance(p, st[0], s["keys"])
        bad = compare(name, frames, st, s2, ext, p)
        if bad:
            fails.append(bad)
            break
        cut_check(g, name, frames, ev, win, Wc, rl, cuts, fails)
        if frames > len(s["keys"]) * 5 // 4 + 50:  # (0.911 steps a CGA frame: a runaway's bound)
            fails.append("%s: the replay ran %d frames past its %d steps" % (name, frames, len(s["keys"])))
    m.bp_exec()
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 0, "the %s replay to end" % name, guest=60)
    dropped(g, name)
    if not fails:
        m.pause()
        st, s2, ext = rd.read()
        advance(p, st[0], s["keys"])
        end = len(s["keys"]) if not p.goal else p.nstep
        if st[0] != end:
            fails.append("%s: the replay ended after step %d, its log holds %d%s" % (
                name, st[0], len(s["keys"]), " (the goal at %d)" % p.nstep if p.goal else ""))
        bad = compare(name + " (its end)", frames, st, s2, ext, p)
        if bad:
            fails.append(bad)
        m.run()
    kinds = [e[0] for e in p.events if e[0] != "corner"]
    print("%s replay %s (%s, %s): %d frames to step %d, equal to the model at every bz_presented and at its end: "
          "%s; events %s%s%s" % (tag, name, s["crs"], BB.MAT_NAMES[s["mat"]], frames, p.nstep,
                                 "yes" if not fails else "NO", ", ".join(kinds) or "none",
                                 "; cuts %s" % ["frame %d step %d on %s: want %s got %s" % c for c in cuts]
                                 if cuts else "",
                                 "; its red arm's model parts at step %d" % s["parts_at"] if s.get("parts_at") else ""),
          flush=True)
    return fails


def run(tag, legs, apps=None, src=None, only=None):
    sym = R.symbols(src)
    fails, outs = [], {}
    S = replays() if "replay" in legs else []
    if only:
        S = [s for s in S if s["name"] in only or s["name"].split("-")[0] in only]
    pre = prove(S) + (prove_wave1()[0] if "scen" in legs or "bench" in legs else [])
    if pre:
        return pre, outs
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym)
        ui.settle()
        if "bench" in legs:
            f, n = bench(g, R.course("bench"))
            fails += f
            outs["bench"] = n
        if "scen" in legs and not fails:         # (a benchmark that parted is still running)
            first = R.course("first")
            for name in SCEN:
                if only and name not in only:
                    continue
                f, out = scenario(g, first, name)
                fails += f
                outs[name] = out
        if "replay" in legs and not [f for f in fails if "benchmark" in f]:
            for s in S:
                fails += replay(g, s)
    return fails, outs


SLOPE_X = ("    mov ax, [bz_tsx]            ; gvx += arrows - BZ_GSL sx; drag; brake; clamp\n"
           "    shl ax, 1                   ; (C's slopes: bz_win9f's, 0 off a plane floor)\n"
           "    shl ax, 1\n    neg ax\n")
SLOPE_Y = "    mov ax, [bz_tsy]            ; gvy the same with sy\n    shl ax, 1\n    shl ax, 1\n    neg ax\n"
REDS = {
    "slope": [("bzphys.inc", SLOPE_X, SLOPE_X.replace("    neg ax\n", "")),
              ("bzphys.inc", SLOPE_Y, SLOPE_Y.replace("    neg ax\n", ""))],
    "respawn": [("bzphys.inc", "    mov [bz_ghv], al\n    call bz_place\n",
                 "    mov [bz_ghv], al\n    mov di, [bz_goff]           ; RED respawn: on the start, not bz_safe\n"
                 "    mov al, [es:di + BZG_WX]\n    mov ah, [es:di + BZG_WY]\n    mov [bz_safe], ax\n"
                 "    call bz_place\n")],
    # (wave 3 writes steps 4 - 6 as macros instanced twice, SPEC.md 128.12.3.2: the
    # patch is in the macro's body, so both instances - wave 2's path and the
    # prop path - are broken alike)
    "takeoff": [("bzphys.inc", "%%takeoff:                       ; over no floor: no bz_gh (bz_ghv cleared)\n"
                 "    call bz_toff\n",
                 "%%takeoff:                       ; over no floor: no bz_gh (bz_ghv cleared)\n"
                 "    mov word [bz_gvz], 0        ; RED takeoff\n    call bz_toff\n"),
                ("bzphys.inc", "    jle %%launch\n    mov ax, bx                  ; z = h: the ball follows the floor\n",
                 "    jg %%redf\n    mov word [bz_gvz], 0        ; RED takeoff: off a falling floor too\n"
                 "    jmp short %%launch\n%%redf:\n    mov ax, bx\n")],
    "bounce": [("bzphys.inc", "    mov cl, [bz_se + 3]\n",
                "    mov cl, [bz_mrec + BZM_EW]  ; RED bounce: the wall's restitution\n")],
    "edge": [("bzphys.inc", "    cmp ax, (16 - BZ_RAD) * 256 ; east when pu > 2,560: a true distance under\n",
              "    cmp ax, (16 - BZ_RAD) * 256 + 255 ; RED edge: wave 1's east test\n")],
    "stun": [("bzphys.inc", ".hard:\n    or al, al\n    jz .soft\n",
              ".hard:\n    or al, al\n    jz .soft\n    cmp al, BZ_ST_STUN          ; RED stun: none\n    je .soft\n")],
    "shatter": [("bzphys.inc", "    mov dl, [bz_mrec + BZM_HSTEPS] ; velocity stopped, the state's steps\n"
                 "    mov [bz_mct], dl\n",
                 "    mov dl, [bz_mrec + BZM_HSTEPS] ; velocity stopped, the state's steps\n"
                 "    mov [bz_mct], dl\n    cmp al, BZ_ST_SHAT          ; RED shatter: the respawn at once\n"
                 "    jne .redsh\n    mov byte [bz_mct], 1\n.redsh:\n")],
    "absimpact": [("bzphys.inc", "    mov di, ax\n    sub ax, [bz_gvz]            ; lvz = max(0, fr - gvz)\n",
                   "    mov di, ax\n    xor ax, ax                  ; RED absimpact: lvz = -gvz\n"
                   "    sub ax, [bz_gvz]\n")],
    "airwall": [("bzphys.inc", "    add ax, BZ_CLIMB * 4        ; (+ 1,024 / 64)\n",
                 "    cmp byte [bz_air], 0        ; RED airwall: no airborne margin\n    jne .redam\n"
                 "    add ax, BZ_CLIMB * 4\n.redam:\n")],
    # wave 3 (SPEC.md 128.12.13.2).  The gate judged one step late (n - 1)
    "gate": [("bzphys.inc", "    mov ax, [bz_nstep]\n    add ax, [es:si + BZP_SEED]\n    and al, [es:si + BZP_MASK]\n"
              "    cmp al, [es:si + BZP_TC0]\n",
              "    mov ax, [bz_nstep]\n    dec ax                      ; RED gate: a step late\n"
              "    add ax, [es:si + BZP_SEED]\n    and al, [es:si + BZP_MASK]\n    cmp al, [es:si + BZP_TC0]\n")],
    # the kick's floor at K alone: t = max(K, d) for an approach too
    "kick": [("bzphys.inc", "    jns .t                      ; d >= 0: t = max(K, d)\n",
              "    jmp short .t                ; RED kick: t = max(K, d) always\n")],
    # no carry: a Hop on the rising lift is not carried, so it comes down early
    "carry": [("bzphys.inc", "bz_carry:\n    mov bl, [bz_onp]\n",
               "bz_carry:\n    ret                         ; RED carry: none\n    mov bl, [bz_onp]\n")],
    # the carry along +s, wave 3's first design: the ball riding the lift moves (and SPINS)
    "carrys": [("bzphys.inc", "    mov [bz_cdd], ax\n    cwd\n    add [bz_gz], ax\n    adc [bz_gz + 2], dx\n    ret\n",
                "    mov [bz_cdd], ax\n    cwd\n    add [bz_gx], ax             ; RED carrys: along +s\n"
                "    adc [bz_gx + 2], dx\n"
                "    add [bz_gy], ax\n    adc [bz_gy + 2], dx\n    ret\n")],
    # bz_onp cleared at a take-off: a Hop on the slab is not carried through its flight
    "stick": [("bzphys.inc", "    cmp byte [bz_air], 0\n    je .pclr\n    cmp byte [bz_wcen + 1], BZ_PK_PLATFORM\n",
               "    jmp short .pclr             ; RED stick: never kept airborne\n"
               "    cmp byte [bz_wcen + 1], BZ_PK_PLATFORM\n")],
    # a windmill's KEEP exit along its entry (its doorway's direction), not its mouth's
    "exit": [("bzphys.inc", "    mov cl, [es:si + BZP_TDIR]  ; 0 +x, 1 -x, 2 +y, 3 -y\n",
              "    mov cl, [es:si + BZP_TDIR]  ; 0 +x, 1 -x, 2 +y, 3 -y\n"
              "    cmp byte [es:si + BZP_KIND], BZ_PK_WINDMILL ; RED exit: along the entry\n    jne .redx\n"
              "    mov cl, [es:si + BZP_TGVX]  ; (the doorway: 0 -x, 1 -y -> codes 1, 3)\n    shl cl, 1\n"
              "    inc cl\n.redx:\n")],
}
RED_LEGS = {"slope": ("bench",), "respawn": ("scen",), "takeoff": ("scen",)}
RED_ONLY = {"respawn": ("pit",), "takeoff": ("lip",), "bounce": ("bounce",), "edge": ("eastwall",),
            "stun": ("stun",), "shatter": ("shatter",), "absimpact": ("ramphop",), "airwall": ("stepup",),
            "gate": ("knock",), "kick": ("kick",), "carry": ("hop",), "carrys": ("ride",), "stick": ("hop",),
            "exit": ("keep",)}
RED_WANT = {"slope": "the benchmark frame", "respawn": "pit", "takeoff": "lip", "bounce": "bounce frame",
            "edge": "eastwall frame", "stun": "stun frame", "shatter": "shatter frame",
            "absimpact": "ramphop-", "airwall": "stepup frame", "gate": "knock frame", "kick": "kick frame",
            "carry": "hop frame", "carrys": "ride frame", "stick": "hop frame", "exit": "keep frame"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--leg", choices=("bench", "scen", "replay", "all"), default="all")
    ap.add_argument("--only", action="append", help="only these scenarios (and replays) by name")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true",
                    help="the host half only: the replays proved on the model, every red arm assembled")
    a = ap.parse_args()
    if a.check:
        S = replays()
        bad = prove(S)
        for s in S:
            print("bonanza_phys replay %-16s %s, %s, %d steps: %s%s" % (
                s["name"], s["crs"], BB.MAT_NAMES[s["mat"]], len(s["keys"]), s["what"],
                "; red %s parts at step %s" % (s["red"], s.get("parts_at")) if s["red"] else ""))
        b1, say = prove_wave1()
        for line in say:
            print("bonanza_phys %s" % line)
        bad += b1
        for b in bad:
            print("FAIL %s" % b)
        for line in R.check_reds(REDS, "bonanza_phys"):
            print(line)
        assert not bad, "%d scenario(s) not proved on the model" % len(bad)
        return
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    legs = ("bench", "scen", "replay") if a.leg == "all" else (a.leg,)
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags:
                try:
                    bad, _ = run(tag, RED_LEGS.get(a.red, ("replay",)), apps=img, src=src,
                                 only=RED_ONLY.get(a.red))
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(RED_WANT[a.red] in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (
                        a.red, tag, RED_WANT[a.red], bad)
                print("bonanza_phys --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_phys --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    allbad, steps = [], {}
    for tag in tags:
        bad, outs = run(tag, legs, only=a.only)
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
        steps[tag] = outs.get("bench")
    if "bench" in legs and len(tags) == 2 and not allbad:
        print("both cards' benchmarks are the model's ONE trajectory: the CGA's %d steps a prefix of the "
              "Hercules' %d (or the other way round), compared step for step at every frame" % (
                  steps["cga"], steps["herc"]))
    assert not allbad, "%d physics failure(s)" % len(allbad)
    print("bonanza_phys (%s; %s): PASS" % (", ".join(tags), ", ".join(legs)))


if __name__ == "__main__":
    main()
