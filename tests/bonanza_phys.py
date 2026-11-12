#!/usr/bin/env python3
"""BONANZA: physics v1 on the guest equals bbcourse.Physics, step for step (SPEC.md 128.10.7, 128.10.11.3).

    make bonanzadisk && python3 tests/bonanza_phys.py [--adapter cga|herc|both] [--leg bench|scen|both]
    python3 tests/bonanza_phys.py --red slope|respawn|takeoff     (a red arm, below)

THE REFERENCE is tools/bbcourse.py's Physics class - the model SPEC.md
128.10.7.3 binds the guest to ("the guest and bbcourse.Physics do exactly
this") - run on the HOST on the same course part the build compiled.  The
guest is read at chosen marks through its own bss (bzphys.inc's head lists
the words): nstep, gx, gy (24.8 DWORDs), gz (signed 24.8), gvx, gvy, gvz and
the air flag.  Physics is a function of the step count and the input alone
(128.10.7.3, *Determinism*), so the model is stepped to the guest's nstep and
the eight values compared EXACTLY - no tolerance: a rounding that differs is
a defect, and the first one is where the guest and the model part.

  1  THE BENCHMARK (B: BENCH, the autopilot, 1,200 frames), on both cards:
     at every frame's bz_presented the guest's state equals the model's
     after that many steps of its own autopilot (Physics.step_auto) - and
     the CGA's and the Hercules' trajectories are therefore the same one,
     though their frames hold different numbers of steps (0.911 and 1.075 a
     frame).  It reports the steps, take-offs, landings and falls the run
     met (a benchmark that falls is a route that is wrong, 128.10.4.6 8).
  2  POKED SCENARIOS on FIRST (Enter: play mode, no key held).  At bz_t0 of
     a frame the row writes the ball's position and velocities, the screen
     state derived from them and bz_pokd = 1 (128.10.7.1: the next step then
     re-centres the window itself; bonanza_ring.poke_ball), the model
     is poked the same way at the guest's nstep and its SAFE cell, and from
     there every frame's bz_presented is compared as in 1:
       pit    from (5, 5) at gvx 256: over the SAFE (6, 5), down B, off its
              lip and into the pit (12, 5): killed at the model's step and
              put back on the model's SAFE cell (6, 5) - not the start -
              with a CUT (the frame's full write, [bz_full]) exactly when
              128.10.8 item 3 says: the respawned footprint not wholly inside
              the window the frame began with
       lip    from (9, 4) at gvx 100: off B's lip, airborne at the model's
              step with the floor's gvz, landing on C at the model's step
              with the model's lfall and lvz ([bz_lfall], [bz_lvz], wave 2's
              input) and [bz_nland] counted
       rail   from (5, 4) at (-150, -250): into the rail at wy = 3, gvy
              zeroed and gvx kept, sliding west as the model does
       goal   from (12, 6) at gvx 250: onto the goal column; the play ENDS
              the frame after the model's goal step (bz_fs drops, [bz_fin]
              set, the last frame presented is the one that held it) and the
              face's line reads `Finished in <s.hh> s` for the guest's final
              nstep by 128.10.6.2's truncated formula (read off bz_lbuf as
              bz_line draws it, breakpointed)

--red NAME builds a broken package in a temporary directory (never build/)
and PASSES only if the row FAILS - at its own check:
  slope     the slope term's sign flipped (gvx += BZ_GSL sx): the benchmark's
            descent parts from the model
  respawn   the respawn put on the course's START instead of bz_safe: the
            pit scenario reappears on (4, 5) where the model says (6, 5)
  takeoff   gvz zeroed at take-off: the lip's flight lands late
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
SCEN = {
    # name: (tile, gvx, gvy, frames at most)
    "pit": ((5, 5), 256, 0, 260),
    "lip": ((9, 4), 100, 0, 120),
    "rail": ((5, 4), -150, -250, 90),
    "goal": ((12, 6), 250, 0, 60),
}


def ftime(n):
    """bzphys.inc bz_ftime: hundredths, truncated; a play past 65,535 steps reads as that"""
    return min(n, 0xFFFF) * 2184500 // 1193182


def show(st):
    return "nstep %d gx %06X gy %06X gz %d gvx %d gvy %d gvz %d air %d" % st


class Reader:
    """The physics words in ONE read a stop: bz_gx .. bz_resp are one run of
    VARs (bzphys.inc BZ_PHYS_VARS)."""

    def __init__(self, g):
        self.g = g
        s = g.sym
        self.lo = s["bz_phs"]
        self.n = s["bz_phe"] - self.lo
        self.off = {n: s[n] - self.lo for n in ("bz_gx", "bz_gy", "bz_gz", "bz_gvx", "bz_gvy", "bz_gvz",
                                                "bz_nstep", "bz_air", "bz_lfall", "bz_lvz", "bz_nland",
                                                "bz_nfall", "bz_resp", "bz_goal")}

    def read(self):
        raw = self.g.m.read(self.g.base + self.lo, self.n)
        o = self.off
        st = (struct.unpack_from("<I", raw, o["bz_nstep"])[0], struct.unpack_from("<I", raw, o["bz_gx"])[0],
              struct.unpack_from("<I", raw, o["bz_gy"])[0], struct.unpack_from("<i", raw, o["bz_gz"])[0],
              struct.unpack_from("<h", raw, o["bz_gvx"])[0], struct.unpack_from("<h", raw, o["bz_gvy"])[0],
              struct.unpack_from("<h", raw, o["bz_gvz"])[0], raw[o["bz_air"]])
        ext = {k: struct.unpack_from("<H", raw, o["bz_" + k])[0] for k in ("lfall", "lvz", "nland", "nfall")}
        ext["resp"], ext["goal"] = raw[o["bz_resp"]], raw[o["bz_goal"]]
        return st, ext


def advance(p, n, keys=None):
    """the model to step N (Physics.step_auto for the benchmark, KEYS for a scenario);
    -> the events the steps raised"""
    e0 = len(p.events)
    while p.nstep < n:
        if keys is None:
            p.step_auto()
        else:
            p.step(keys)
    return p.events[e0:]


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
            first = False
        frames += 1
        st, ext = rd.read()
        if st[0] < p.nstep:
            fails.append("frame %d: the guest's nstep went BACK to %d (the model is at %d)" % (frames, st[0], p.nstep))
            break
        ev += advance(p, st[0])
        if st != p.state():
            fails.append("frame %d: the guest differs from the model after %d steps:\n      guest %s\n      model %s"
                         % (frames, st[0], show(st), show(p.state())))
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
        fails.append("the benchmark FELL %d times under the model: its route is wrong (SPEC.md 128.10.4.6 8)" % p.nfall)
    return fails, p.nstep


def outwin(px, py, R0, c0, Wc, rl):
    """bz_outwin: the footprint (128.4's 20 x 16 from px & ~3) not wholly inside the window"""
    first = px >> 3
    last = ((px >> 2) + 4) >> 1
    top = R0 * rl
    return first < c0 or last >= c0 + Wc or py < top or py > top + 200 - 16


def scenario(g, crs, name):
    """Part 2: one poked scenario on FIRST in play mode."""
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
    st0, _ = rd.read()
    safe = tuple(m.read(g.a("bz_safe"), 2))
    p = SlidePhysics(crs, play=True).poke(wx, wy, gvx, gvy)
    p.nstep, p.safe = st0[0], safe
    R.poke_ball(g, p.gx, p.gy, p.gz, p.gvx, p.gvy, p.gvz)
    Wc = g.w("bz_W")
    rl = R.RL[tag]
    win = (g.w("bz_R0"), g.w("bz_c0"))          # the window this frame begins with
    frames, last, ended, cuts = 0, None, False, []
    landed = None
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
        st, ext = rd.read()
        ev = advance(p, st[0], 0)
        if st != p.state():
            fails.append("%s frame %d: the guest differs from the model after %d steps:\n      guest %s\n"
                         "      model %s" % (name, frames, st[0], show(st), show(p.state())))
            break
        resp = [e for e in ev if e[0] == "respawn"]
        if resp:
            px, py = g.w("bz_px"), g.w("bz_py")
            want = outwin(px, py, win[0], win[1], Wc, rl)
            got = bool(g.b("bz_full"))
            cuts.append((frames, resp[0][1], resp[0][2], want, got))
            if want != got:
                fails.append("%s frame %d: a respawn on %s %s a CUT ([bz_full] %d), but 128.10.8 item 3 says %s "
                             "(footprint %d,%d against the window R0 %d c0 %d)" % (
                                 name, frames, resp[0][2], "took" if got else "took no", got,
                                 "cut" if want else "no cut", px, py, win[0], win[1]))
        for e in ev:
            if e[0] == "land" and landed is None:
                landed = (frames, e[1], e[2])
                if (ext["lfall"], ext["lvz"]) != (p.lfall, p.lvz) or ext["nland"] != p.nland:
                    fails.append("%s: the landing at step %d recorded lfall %d lvz %d nland %d; the model %d %d %d"
                                 % (name, e[1], ext["lfall"], ext["lvz"], ext["nland"], p.lfall, p.lvz, p.nland))
        if (ext["nfall"], ext["goal"]) != (p.nfall, p.goal):
            fails.append("%s frame %d: nfall %d goal %d against the model's %d %d" % (
                name, frames, ext["nfall"], ext["goal"], p.nfall, p.goal))
            break
        last = st
        if name != "goal" and frames >= 8 and _done(name, p):
            break
    out = {"frames": frames, "events": list(p.events), "cuts": cuts, "landed": landed, "model": p}
    face = None
    if name == "goal" and not fails:
        if not ended:
            fails.append("goal: the play did not end within %d frames (the model's goal at %s)" % (
                nmax, [e[1] for e in p.events if e[0] == "goal"]))
        else:
            gs = [e[1] for e in p.events if e[0] == "goal"]
            if last is None or not gs or not (gs[0] <= last[0]):
                fails.append("goal: the play ended after step %d but the model's goal step is %s" % (last[0], gs))
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
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0, "the %s scenario's play ends on Esc" % name, guest=60)
        dropped(g, name)
    out["face"] = face
    _say(tag, name, out, fails)
    if name == "pit" and not fails:
        r = [e for e in p.events if e[0] == "respawn"]
        if not r or r[0][2] != (6, 5):
            fails.append("pit: the model's respawn was %s, not on the SAFE cell (6, 5)" % r)
    if name == "lip" and not fails and (landed is None or not [e for e in p.events if e[0] == "takeoff"]):
        fails.append("lip: no take-off and landing in %d frames (%s)" % (frames, p.events[:4]))
    if name == "rail" and not fails and not _slid(p):
        fails.append("rail: the model never zeroed gvy against the rail with gvx kept")
    return fails, out


def _done(name, p):
    """the scenario has shown what it is for, and a few frames past it"""
    kinds = [e[0] for e in p.events]
    if name == "pit":
        return "respawn" in kinds and p.nstep > [e[1] for e in p.events if e[0] == "respawn"][0] + 8
    if name == "lip":
        return "land" in kinds and p.nstep > [e[1] for e in p.events if e[0] == "land"][0] + 8
    if name == "rail":
        return _slid(p) and p.nstep > 40
    return False


def _slid(p):
    return getattr(p, "_slid", False)


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
        "; landed frame %d step %d (lfall, lvz) %s" % out["landed"] if out["landed"] else "",
        "; face %r" % out.get("face") if out.get("face") else ""), flush=True)


class SlidePhysics(BB.Physics):
    """the model, noting the rail's slide: a step that zeroes gvy from a
    non-zero value while gvx stays non-zero"""

    def step(self, keys=0):
        g0 = (self.gvx, self.gvy)
        r = BB.Physics.step(self, keys)
        if g0[1] and not self.gvy and self.gvx and not self.air:
            self._slid = True
        return r


def run(tag, legs, apps=None, src=None):
    sym = R.symbols(src)
    fails, outs = [], {}
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
                f, out = scenario(g, first, name)
                fails += f
                outs[name] = out
    return fails, outs


SLOPE_X = ("    mov ax, bx                  ; gvx += arrows - BZ_GSL sx; the drag; the clamp\n"
           "    shl ax, 1\n    shl ax, 1\n    neg ax\n")
SLOPE_Y = "    mov ax, si                  ; gvy the same with sy\n    shl ax, 1\n    shl ax, 1\n    neg ax\n"
REDS = {
    "slope": [("bzphys.inc", SLOPE_X, SLOPE_X.replace("    neg ax\n", "")),
              ("bzphys.inc", SLOPE_Y, SLOPE_Y.replace("    neg ax\n", ""))],
    "respawn": [("bzphys.inc", ".respawn:\n    call bz_place\n",
                 ".respawn:\n    mov di, [bz_goff]           ; RED respawn: on the start, not bz_safe\n"
                 "    mov al, [es:di + BZG_WX]\n    mov ah, [es:di + BZG_WY]\n    mov [bz_safe], ax\n"
                 "    call bz_place\n")],
    "takeoff": [("bzphys.inc", ".takeoff:\n    mov byte [bz_air], 1        ; TAKE OFF, keeping the floor's gvz\n",
                 ".takeoff:\n    mov byte [bz_air], 1        ; TAKE OFF, keeping the floor's gvz\n"
                 "    mov word [bz_gvz], 0        ; RED takeoff\n")],
}
RED_LEGS = {"slope": ("bench",), "respawn": ("scen",), "takeoff": ("scen",)}
RED_WANT = {"slope": "benchmark", "respawn": "pit", "takeoff": "lip"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--leg", choices=("bench", "scen", "both"), default="both")
    ap.add_argument("--red", choices=sorted(REDS))
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    legs = ("bench", "scen") if a.leg == "both" else (a.leg,)
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags:
                try:
                    bad, _ = run(tag, RED_LEGS[a.red], apps=img, src=src)
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                want = "the guest differs" if a.red == "slope" else RED_WANT[a.red]
                assert any(want in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (a.red, tag, want, bad)
                print("bonanza_phys --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_phys --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    allbad, steps = [], {}
    for tag in tags:
        bad, outs = run(tag, legs)
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
