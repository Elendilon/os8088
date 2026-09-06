#!/usr/bin/env python3
"""THE THREE NEW AEROPLANES (SPEC.md 88.7.5-88.7.7), on MartyPC.

    python3 tests/skiesfleet.py [--machine os8088_5150_herc_gla]

Each one exists for a MECHANIC and not for a number on the airspeed
indicator, so each check is about the mechanic:

  1. the Plane list has five rows and every row is the record it names;
  2. FOUGA MAGISTER - cs_att_lag. Held hard over, the roll rate RAMPS: the
     first tick moves a fraction of what the eighth does, where the two
     direct-drive aeroplanes move the same amount every tick. Released, the
     rate DECAYS instead of stopping dead - and the tail is SHORT, so a tap
     held for two ticks is a 2.2-degree nudge that has stopped moving well
     inside 26 (88.7.5.1: it was 19.6 degrees and still going). And the
     engine SPOOLS: thrust climbs toward the throttle over seconds, which no
     piston does;
  3. WASSMER BIJAVE - no engine. It starts in the AIR at CSP_LAUNCH with the
     tow-released message, its thrust is zero however hard the throttle key
     is held, and left alone it comes down;
  4. ICON A5 - CSPF_AMPHIB. It starts ON THE WATER, gets off it under its own
     power, and a touchdown inside the water strip is a LANDING with the
     water's name on the strip. The same touchdown in the Cessna is a crash,
     which is what ditching is.

Three red runs (docs/WRITING-TESTS.md 1). --clobber-lag gives the Magister
the trainer's CSP_ATT, and the ramp and decay checks go red. --clobber-tail
makes the rate decay as slowly as it builds, which is the model as it was,
and the tap becomes 6.45 degrees and never settles. --clobber-amphib
clears the A5's CSP_FLAGS, and the water start and the splash go red - note
that everything ELSE about the A5 still passes, which is why those two
checks are the ones that are there.
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
CSP_VSTALL, CSP_VMAX, CSP_THRUST = 2, 6, 8
CSP_ROLLR, CSP_COCKPIT, CSP_ATT = 16, 32, 34
CSP_SPOOL, CSP_LAUNCH, CSP_FLAGS = 36, 38, 40
CSA_WX, CSA_WZ, CSA_WHDG, CSA_WLEN = 22, 24, 26, 28
CSG_TAKEOFF, CSG_RELEASE, CSG_SPLASH = 1, 7, 8
CS_ST_GROUND, CS_ST_AIR, CS_ST_CRASH = 0, 1, 2
bad = []


def check(cond, what):
    print("  [%s] %s" % ("PASS" if cond else "FAIL", what))
    if not cond:
        bad.append(what)


def sg(v):
    return v - 0x10000 if v >= 0x8000 else v


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    ap.add_argument("--clobber-lag", action="store_true",
                    help="give the Magister the trainer's model: must go red")
    ap.add_argument("--clobber-amphib", action="store_true",
                    help="take the A5's amphibious flag away: must go red")
    ap.add_argument("--clobber-tail", action="store_true",
                    help="make the rate decay as slowly as it builds: red")
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

        def dw(n):
            return int.from_bytes(m.readseg(seg, base + off(n), 4), "little")

        def poke(n, d):
            m.write(lin + base + off(n), d)

        def rec(at, o):
            return int.from_bytes(m.readseg(seg, at + o, 2), "little")

        def name(at):
            p = rec(at, 0)
            return m.readseg(seg, p, 24).split(b"\0")[0].decode()

        m.advance(frames=30)
        m.run()
        if a.clobber_lag:
            m.pause()
            m.write(lin + mp["cs_p_fouga"] + CSP_ATT,
                    mp["cs_att_trim"].to_bytes(2, "little"))
            m.run()
            print("  (the Magister given the trainer's model: this must fail)")
        if a.clobber_tail:
            # cs_lagax turns a quarter of the gap into three quarters on the
            # decay arm with `neg ax / add ax, cx`; without those the rate
            # dies as slowly as it builds, which is the model as it was
            lo, hi = mp["cs_lagax"], mp["cs_move"]
            code = m.read(lin + lo, hi - lo)
            i = code.find(b"\xF7\xD8\x01\xC8")      # neg ax ; add ax, cx
            if i < 0:
                sys.exit("skiesfleet: cs_lagax does not shape its decay the "
                         "way this patch expects")
            m.pause()
            m.write(lin + lo + i, b"\x90\x90\x90\x90")
            m.run()
            print("  (the rate made to decay as slowly as it builds: must fail)")
        if a.clobber_amphib:
            m.pause()
            m.write(lin + mp["cs_p_a5"] + CSP_FLAGS, b"\x00\x00")
            m.run()
            print("  (the A5's amphibious flag cleared: this must fail)")

        # --- 1. the list ------------------------------------------------------
        n = (mp["cs_plnames"] - mp["cs_planes"]) // 2
        check(n == 5, "the Plane list has five rows (%d)" % n)
        po = [rec(mp["cs_drplane"], 2 * i) for i in range(4)]

        def fly(row):
            """Pick row `row` and enter the bracket; out: the plane record."""
            if byte("cs_back") != 0:
                m.type_text("f")
                m.advance(frames=60)
                m.run()
            ui.mo.click((po[0] + po[2]) // 2, (po[1] + po[3]) // 2)
            m.advance(frames=25)
            m.run()
            ui.mo.click(po[0] + 20, po[3] + 2 + 12 * row + 6)
            m.advance(frames=25)
            m.run()
            got, want = w("cs_plane"), rec(mp["cs_planes"], 2 * row)
            check(got == want, "row %d picks the record it names (%04x)" % (row, got))
            m.type_text("f")
            m.advance(frames=100)
            m.run()
            check(byte("cs_back") != 0, "row %d: the bracket took a mode" % row)
            return got

        def ticks(nn, pin=None):
            """Stop at the top of each of nn consecutive cs_step calls."""
            m.bp_exec(lin + mp["cs_step"])
            m.run()
            if m.wait_stop(30) is None:
                sys.exit("skiesfleet: cs_step never ran")
            if pin:
                pin()
            out = []
            for _ in range(nn):
                out.append(None)
                m.run()
                if m.wait_stop(30) is None:
                    sys.exit("skiesfleet: cs_step never ran")
                out[-1] = True
            m.bp_exec()
            m.run()

        def sample(nn, what, pin=None):
            m.bp_exec(lin + mp["cs_step"])
            m.run()
            assert m.wait_stop(30) is not None
            if pin:
                pin()
            out = []
            for _ in range(nn):
                out.append(what())
                m.run()
                assert m.wait_stop(30) is not None
            m.bp_exec()
            m.run()
            return out

        def airborne(spd, alt=600, pitch=0):
            m.pause()
            for nm, v in (("cs_px", -2400), ("cs_py", alt), ("cs_pz", -2000)):
                poke(nm, ((v * 256) & 0xFFFFFFFF).to_bytes(4, "little"))
            poke("cs_hdg", (7282).to_bytes(2, "little"))
            poke("cs_pitch", (int(pitch * DEG) & 0xFFFF).to_bytes(2, "little"))
            poke("cs_roll", b"\x00\x00")
            poke("cs_rrate", b"\x00\x00")
            poke("cs_prate", b"\x00\x00")
            poke("cs_spd", (spd * 128).to_bytes(2, "little"))
            poke("cs_state", b"\x01")

        # --- 2. the Magister --------------------------------------------------
        jet = fly(2)
        print("    --- %s: SPOOL %d, ROLLR %d"
              % (name(jet), rec(jet, CSP_SPOOL), rec(jet, CSP_ROLLR)))
        m.key("ArrowRight", down=True, up=False)
        m.advance(frames=8)
        m.run()
        rolls = sample(9, lambda: sg(w("cs_roll")), lambda: airborne(120))
        m.key("ArrowRight", down=False, up=True)
        steps = [rolls[i + 1] - rolls[i] for i in range(len(rolls) - 1)]
        print("      roll steps held: %s" % steps)
        # THE FIRST STEP IS DROPPED and that is not a fudge: the attitude is
        # pinned at a cs_step breakpoint, which is inside a frame whose
        # cs_input has already run, so the first tick after it moves nothing
        # whatever model is fitted - a leading zero that made this check pass
        # against the trainer's model too, which is the false green
        # --clobber-lag exists to catch.
        steps = steps[1:]
        check(steps[0] * 2 < steps[-1],
              "the roll rate RAMPS - the second tick is under half the "
              "eighth (%d against %d)" % (steps[0], steps[-1]))
        m.advance(frames=10)
        m.run()
        after = sample(5, lambda: sg(w("cs_roll")))
        dec = [after[i + 1] - after[i] for i in range(len(after) - 1)]
        print("      roll steps released: %s" % dec)
        check(dec[0] > 0 and dec[0] > dec[-1],
              "...and DECAYS when the stick is centred instead of stopping "
              "dead (%s)" % dec)

        # --- 2b. the tail is SHORT, and a TAP is a nudge (SPEC.md 88.7.5.1)
        # Both of the owner's complaints about this aeroplane are one number.
        # A rate decaying by a quarter a tick has THREE TIMES its current
        # value still to travel, so centring the stick at the horizon coasted
        # a fifth of a turn past it and a one-tick tap rolled 19.6 degrees.
        # The decay is three quarters a tick now and the tail is a third of
        # the rate.
        def stickticks(key, held, n=26):
            # Hold `key` through `held` + 1 TICKS, which only cs_stick's own
            # breakpoint makes expressible: the stick is read per tick now
            # (88.7.5.1) and a frame is three of them. EVERY HIT OF THIS
            # BREAKPOINT IS A SIM TICK since 88.7.5.2 - cs_input used to call
            # cs_stick as well, and while it did, one stop in three or four
            # was that call and moved nothing.
            m.pause()
            airborne(120)
            poke("cs_roll", b"\x00\x00")
            m.run()
            m.bp_exec(lin + mp["cs_stick"])
            m.run()
            assert m.wait_stop(30) is not None
            m.key(key, down=True, up=False)
            out = []
            for i in range(n):
                out.append(sg(w("cs_roll")))
                if i == held:
                    m.key(key, down=False, up=True)
                m.run()
                assert m.wait_stop(30) is not None
            m.bp_exec()
            m.run()
            m.key(key, down=False, up=True)
            return out

        tap = stickticks("ArrowRight", 1)       # TWO ticks - a release sent
                                                # at the same halt as the press
                                                # never reaches the guest
        moved = abs(tap[-1]) / DEG
        print("      a short tap: %.2f degrees, settled %s"
              % (moved, "yes" if tap[-1] == tap[-4] else "no"))
        check(0.5 < moved < 6.0,
              "a TAP is a nudge and not a manoeuvre (%.2f degrees)" % moved)
        check(tap[-1] == tap[-4],
              "...and it has stopped moving well inside %d ticks (%d then %d)"
              % (len(tap), tap[-4], tap[-1]))
        # the spool
        m.pause()
        airborne(120)
        poke("cs_thr", (100).to_bytes(2, "little"))
        poke("cs_thrust", b"\x00\x00")
        poke("cs_thracc", b"\x00\x00")
        m.run()
        thr = sample(40, lambda: w("cs_thrust"))
        full = rec(jet, CSP_THRUST)
        print("      thrust over 40 ticks: %d -> %d (full %d)"
              % (thr[0], thr[-1], full))
        check(thr[0] < full and thr[-1] > thr[0],
              "the engine SPOOLS toward the throttle rather than arriving "
              "(%d -> %d of %d)" % (thr[0], thr[-1], full))
        check(thr[-1] < full,
              "...and forty ticks is not enough to get there (%d of %d)"
              % (thr[-1], full))

        # --- 3. the Bijave ----------------------------------------------------
        gl = fly(3)
        launch = rec(gl, CSP_LAUNCH)
        alt = int.from_bytes(m.readseg(seg, base + off("cs_py") + 1, 2), "little")
        print("    --- %s: LAUNCH %d, THRUST %d, started at %d m, msg %d"
              % (name(gl), launch, rec(gl, CSP_THRUST), alt, byte("cs_msg")))
        check(byte("cs_state") == CS_ST_AIR and abs(alt - launch) <= 2,
              "the sailplane starts in the AIR at CSP_LAUNCH (state %d, %d m)"
              % (byte("cs_state"), alt))
        check(byte("cs_msg") == CSG_RELEASE,
              "...and says the tow is released (%d)" % byte("cs_msg"))
        m.key("KeyW", down=True, up=False)         # the throttle, held wide open
        m.advance(frames=30)
        m.run()
        m.key("KeyW", down=False, up=True)
        check(w("cs_thrust") == 0,
              "no throttle key can give it thrust (%d)" % w("cs_thrust"))
        m.pause()
        airborne(25, alt=900, pitch=-2)
        m.run()
        a0 = int.from_bytes(m.readseg(seg, base + off("cs_py") + 1, 2), "little")
        x0, z0 = sg(dw("cs_px") >> 8) & 0xFFFF, 0
        x0 = sg(int.from_bytes(m.readseg(seg, base + off("cs_px") + 1, 2), "little"))
        z0 = sg(int.from_bytes(m.readseg(seg, base + off("cs_pz") + 1, 2), "little"))
        ticks(120)
        a1 = int.from_bytes(m.readseg(seg, base + off("cs_py") + 1, 2), "little")
        x1 = sg(int.from_bytes(m.readseg(seg, base + off("cs_px") + 1, 2), "little"))
        z1 = sg(int.from_bytes(m.readseg(seg, base + off("cs_pz") + 1, 2), "little"))
        drop = a0 - a1
        run = int(((x1 - x0) ** 2 + (z1 - z0) ** 2) ** 0.5)
        print("      two degrees down: %d m of height for %d m of ground"
              % (drop, run))
        check(drop > 0, "it comes DOWN with no engine (%d m)" % drop)
        check(run > drop * 12,
              "...and it GLIDES rather than falling - better than 12:1 "
              "(%d:%d)" % (run, drop))

        # --- 4. the A5 --------------------------------------------------------
        a5 = fly(4)
        port = w("cs_airport")
        wlen = rec(port, CSA_WLEN)
        print("    --- %s: FLAGS %04x, the location's water strip is %d m long"
              % (name(a5), rec(a5, CSP_FLAGS), 2 * wlen))
        check(byte("cs_onwater") == 1,
              "the amphibian starts ON THE WATER (%d)" % byte("cs_onwater"))
        m.key("KeyW", down=True, up=False)         # THE THROTTLE HELD TO 100
        for _ in range(12):                        # and not merely nudged: the
            m.advance(frames=25)                   # key moves it 2 a tick, and
            m.run()                                # a third of the way open is
            if w("cs_thr") >= 100:                 # less thrust than a hull's
                break                              # drag, so it would sit there
        m.key("KeyW", down=False, up=True)
        check(w("cs_thr") >= 100, "the throttle opens (%d%%)" % w("cs_thr"))
        m.key("ArrowDown", down=True, up=False)
        ok = False
        for _ in range(60):
            m.advance(frames=40)
            m.run()
            if byte("cs_state") == CS_ST_AIR:
                ok = True
                break
            if byte("cs_state") == CS_ST_CRASH:
                break
        m.key("ArrowDown", down=False, up=True)
        check(ok, "...and gets off it under its own power (state %d, %d kt)"
              % (byte("cs_state"), w("cs_spd") * 1944 // 128000))

        def splashdown():
            """Put the aeroplane a metre over the water strip, sinking gently
            along it, and let the touchdown happen."""
            m.pause()
            sn = rec(port, CSA_WX), rec(port, CSA_WZ)
            poke("cs_px", ((sg(sn[0]) * 256) & 0xFFFFFFFF).to_bytes(4, "little"))
            poke("cs_pz", ((sg(sn[1]) * 256) & 0xFFFFFFFF).to_bytes(4, "little"))
            poke("cs_py", ((3 * 256) & 0xFFFFFFFF).to_bytes(4, "little"))
            poke("cs_hdg", rec(port, CSA_WHDG).to_bytes(2, "little"))
            # TWO DEGREES DOWN and not a poked vertical speed: cs_step
            # recomputes cs_vs from the attitude every tick, so a poked one
            # is gone before the next touchdown test and the aeroplane hangs
            # there at three metres for ever
            poke("cs_pitch", (int(-2 * DEG) & 0xFFFF).to_bytes(2, "little"))
            poke("cs_roll", b"\x00\x00")
            poke("cs_spd", (25 * 128).to_bytes(2, "little"))
            poke("cs_state", b"\x01")
            m.run()

        land0 = w("cs_landings")
        splashdown()
        for _ in range(20):
            m.advance(frames=20)
            m.run()
            if byte("cs_state") != CS_ST_AIR:
                break
        print("      after the touchdown: state %d, water %d, msg %d, "
              "landings %d -> %d" % (byte("cs_state"), byte("cs_onwater"),
                                     byte("cs_msg"), land0, w("cs_landings")))
        check(byte("cs_state") == CS_ST_GROUND and byte("cs_onwater") == 1,
              "a touchdown on the water strip is a LANDING (state %d, water %d)"
              % (byte("cs_state"), byte("cs_onwater")))
        check(byte("cs_msg") == CSG_SPLASH,
              "...and the strip names the water (msg %d)" % byte("cs_msg"))
        check(w("cs_landings") == land0 + 1,
              "...and it counts (%d -> %d)" % (land0, w("cs_landings")))

        # ...and the same touchdown in the trainer is a ditching
        fly(0)
        splashdown()
        for _ in range(20):
            m.advance(frames=20)
            m.run()
            if byte("cs_state") != CS_ST_AIR:
                break
        check(byte("cs_state") == CS_ST_CRASH,
              "the SAME touchdown in the Cessna is a crash (state %d)"
              % byte("cs_state"))
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
