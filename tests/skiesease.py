#!/usr/bin/env python3
"""THE HORIZON CAPTURES THE LAST THREE TICKS (SPEC.md 88.7.3), on MartyPC.

    python3 tests/skiesease.py [--machine os8088_5150_herc_gla]

A key is a stick that is hard over or centred, so an axis moves in whole
CSP_ROLLR quanta and can only STOP where the quanta fall - 10 degrees on the
Pitts, three ticks to a frame, so the pilot's quantum is 30 degrees and level
flight is not in it. `cs_ease` shortens the last three ticks of an approach
so the angle lands ON the horizon instead of stepping over it.

Every reading here is taken at a `cs_step` BREAKPOINT and not after a frame:
the model steps per tick and a frame spends one, two or three of them, so a
per-frame sample cannot see whether the angle passed through zero or landed
on it - which is the whole question.

  1. held toward level from an angle that is NOT a multiple of the rate, both
     aeroplanes and both axes land EXACTLY on the horizon, within three ticks
     of coming inside three rates of it;
  2. the eased ticks are not a crawl - each is at least 60% of the full rate,
     which is what keeps a continuous roll from hitching at level;
  3. held AWAY from the horizon nothing is eased: every tick is the full rate;
  4. and the Pitts' horizon is a HALF TURN - held toward inverted from 173
     degrees it lands exactly on 180, which is where an aerobatic aeroplane
     flies upside down.

--clobber-ease is the red run (docs/WRITING-TESTS.md 1): it puts a `ret` on
cs_ease's first byte, which returns the step unchanged - the model exactly as
it was - and checks 1 and 4 must go red.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88ui                                               # noqa: E402
import dispapps                                             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEG = 65536.0 / 360.0
CSP_ROLLR, CSP_PITCHR = 16, 20
HALF = 32768
bad = []


def check(cond, what):
    print("  [%s] %s" % ("PASS" if cond else "FAIL", what))
    if not cond:
        bad.append(what)


def sg(v):
    return v - 0x10000 if v >= 0x8000 else v


def tohorizon(a):
    """The signed distance from a 16-bit angle to the nearest half turn."""
    d = a & 0x7FFF
    return (HALF - d) if d >= 0x4000 else -d


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    ap.add_argument("--clobber-ease", action="store_true",
                    help="return the step unchanged: the row must go red")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    mp = dispapps._map("skies")

    def off(n):
        return dispapps.bss_off("skies", n)

    with os88ui.boot(a.image, apps=a.apps, machine=a.machine) as ui:
        m = ui.m
        ui.path("B:/GAMES/SKIES.O88")
        slot, seg = dispapps.pkg_seg(m, 0)
        lin = seg << 4
        base = int.from_bytes(m.readseg(seg, 8, 2), "little")

        def w(n):
            return int.from_bytes(m.readseg(seg, base + off(n), 2), "little")

        def byte(n):
            return m.readseg(seg, base + off(n), 1)[0]

        def poke(n, d):
            m.write(lin + base + off(n), d)

        def rec(at, o):
            return int.from_bytes(m.readseg(seg, at + o, 2), "little")

        m.advance(frames=30)
        m.run()
        if a.clobber_ease:
            m.pause()
            m.write(lin + mp["cs_ease"], b"\xC3")
            m.run()
            print("  (cs_ease returns its step unchanged: this run must fail)")

        def pick(row):
            po = [rec(mp["cs_drplane"], 2 * i) for i in range(4)]
            ui.mo.click((po[0] + po[2]) // 2, (po[1] + po[3]) // 2)
            m.advance(frames=20)
            m.run()
            ui.mo.click(po[0] + 20, po[3] + 2 + 12 * row + 6)
            m.advance(frames=20)
            m.run()

        def airborne(roll, pitch):
            """Level at 600 m and 70 m/s, the attitude pinned, engine in.

            Called with the guest ALREADY HALTED at a cs_step breakpoint, so
            it neither pauses nor resumes."""
            for nm, v in (("cs_px", -2400), ("cs_py", 600), ("cs_pz", -2000)):
                poke(nm, ((v * 256) & 0xFFFFFFFF).to_bytes(4, "little"))
            poke("cs_hdg", (7282).to_bytes(2, "little"))
            poke("cs_pitch", (pitch & 0xFFFF).to_bytes(2, "little"))
            poke("cs_roll", (roll & 0xFFFF).to_bytes(2, "little"))
            poke("cs_spd", (70 * 256).to_bytes(2, "little"))
            poke("cs_thr", (100).to_bytes(2, "little"))
            poke("cs_state", b"\x01")

        def ticks(key, name, pin, n=10):
            """The angle at the top of each of n consecutive cs_step calls.

            THE KEY GOES DOWN FIRST and the attitude is pinned at the FIRST
            stop, not before it: a poke followed by a free run loses the
            approach to the ticks that pass while the breakpoint is being
            armed, and the trainer's own return-to-level eats it besides."""
            m.key(key, down=True, up=False)
            m.advance(frames=6)                 # ...so cs_input has read it
            m.run()
            m.bp_exec(lin + mp["cs_step"])
            m.run()
            if m.wait_stop(30) is None:
                sys.exit("skiesease: cs_step never ran")
            pin()                               # halted at the top of a tick
            out = []
            for _ in range(n):
                out.append(sg(w(name)))
                m.run()
                if m.wait_stop(30) is None:
                    sys.exit("skiesease: cs_step never ran")
            m.bp_exec()
            m.run()
            m.key(key, down=False, up=True)
            return out

        def run(plane, axis, start_deg, key, rate, label, want_half=False):
            angle = int(start_deg * DEG)
            seq = ticks(key, axis,
                        lambda: airborne(angle if axis == "cs_roll" else 0,
                                         0 if axis == "cs_roll" else angle))
            deg = [round(x / DEG, 2) for x in seq]
            print("      %-22s %s" % (label, deg))
            # the first reading is the pinned start; the model has not run yet
            target = HALF if want_half else 0
            landed = [i for i, x in enumerate(seq)
                      if (abs(x) if not want_half else abs(abs(x) - HALF)) == 0]
            check(bool(landed),
                  "%s lands EXACTLY on the horizon (%s)"
                  % (label, "tick %d" % landed[0] if landed else "never: %s" % deg))
            if not landed:
                return
            k = landed[0]
            inside = [i for i in range(k) if abs(tohorizon(seq[i])) <= 3 * rate]
            if inside:
                check(k - inside[0] <= 3,
                      "%s takes at most three ticks from inside three rates "
                      "(%d)" % (label, k - inside[0]))
                steps = [abs(seq[i + 1] - seq[i]) for i in range(inside[0], k)]
                steps = [s if s < HALF else 65536 - s for s in steps]
                check(min(steps) * 10 >= rate * 6,
                      "%s: no eased tick is a crawl - the smallest is %d%% of "
                      "the rate (%s)"
                      % (label, round(100 * min(steps) / rate), steps))

        for row, name in ((0, "CESSNA"), (1, "PITTS")):
            if byte("cs_back") != 0:
                m.type_text("f")
                m.advance(frames=60)
                m.run()
            pick(row)
            plane = w("cs_plane")
            check(plane == rec(mp["cs_planes"], 2 * row),
                  "%s: the list's row %d is in hand (%04x)" % (name, row, plane))
            m.type_text("f")
            m.advance(frames=80)
            m.run()
            check(byte("cs_back") != 0, "%s: the bracket took a mode" % name)
            rr = rec(plane, CSP_ROLLR)
            pr = rec(plane, CSP_PITCHR)
            print("    --- %s: ROLLR %d (%.1f deg), PITCHR %d (%.1f deg)"
                  % (name, rr, rr / DEG, pr, pr / DEG))
            # 1/2 - toward level on both axes, from angles the rate cannot hit
            run(plane, "cs_roll", 2.6 * rr / DEG, "ArrowLeft", rr,
                "%s roll -> level" % name)
            # ArrowDown is the stick BACK - the nose comes UP - so a nose
            # below the horizon is brought to it with Down, not Up
            run(plane, "cs_pitch", -2.4 * pr / DEG, "ArrowDown", pr,
                "%s pitch -> horizon" % name)
            # 3 - away from it, nothing eased
            angle = int(0.4 * rr)
            seq = ticks("ArrowRight", "cs_roll", lambda: airborne(angle, 0), 6)
            steps = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
            check(all(s == rr for s in steps),
                  "%s: held AWAY from level every tick is the full rate (%s)"
                  % (name, steps))

        # 4 - the Pitts' other horizon: INVERTED level
        run(w("cs_plane"), "cs_roll", 173.0, "ArrowRight",
            rec(w("cs_plane"), CSP_ROLLR), "PITTS roll -> inverted",
            want_half=True)
        m.type_text("f")
        m.advance(frames=40)
        m.run()

    if bad:
        for b in bad:
            print("FAIL: " + b)
        return 1
    print("  ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
