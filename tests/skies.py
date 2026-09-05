#!/usr/bin/env python3
"""CLEAR SKIES (SPEC.md 88) flies, lands where it should, crashes where it
should, and its frames do not flash.

    python3 tests/skies.py [--machine os8088_5150_herc_gla]

FIVE ASSERTIONS, read out of the package's own bss rather than off the glass
wherever the question is about the world (docs/WRITING-TESTS.md 8):

**It draws, and it advances.** `cs_frames` climbs, and the glass differs
between two samples - the same pair SPEC.md 85.1's gate asks, because a page
flip that never latches leaves a counter climbing over a still picture.

**It takes off.** Full throttle on the runway, the stick back once the speed
passes VROT, and the state goes to FLYING with the altitude climbing - the
whole of SPEC.md 88.7's ground model in one flight.

**It crashes, and comes back.** The nose pushed over into the ground is a
crash: `cs_crashes` increments, the picture freezes for CS_CRASHT ticks, and
the aeroplane is back at the airport's reset point on the runway heading with
the engine closed.

**It does not flash** (SPEC.md 85.1's instrument, 88.3): the ink per DISPLAYED
frame priced against its neighbours, with the same 70% floor, on a raster
whose whole view is redrawn and blitted every frame.

**The raster is the one the design names**: the view's width on Hercules is
400 and on CGA 320, read out of cs_ww, because a wrong table row draws a
plausible picture that is simply the wrong size.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88marty                                            # noqa: E402
import os88mouse                                            # noqa: E402
import os88sym                                              # noqa: E402
import dispapps                                             # noqa: E402
import dispcp                                               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES = 40                             # displayed frames sampled for the floor
FLOOR = 70                              # SPEC.md 85.1's margin: a blit caught
                                        # part-way down is tearing, not a gap
CS_ST_GROUND, CS_ST_AIR, CS_ST_CRASH = 0, 1, 2
CS_CRASHT = 36
VROT = 28 * 256                         # apps/skies/csworld.inc's Cessna
POP = bytes(bin(i).count("1") for i in range(256))


def lit(fb):
    n = 0
    for b in fb:
        n += POP[b]
    return n


def open_game(m):
    """Boot to the desktop and get SKIES.O88 open. Returns (slot, seg, bss)."""
    S = os88sym.linear
    os88marty.settle(m)
    mo = os88mouse.Mouse(marty=m)
    dispcp.open_drive(m, mo, S, os88marty.settle, "B")
    disk = dispcp.win_list(m, S)[-1]
    wx, wy = dispcp.win_rect(m, S, disk)[:2]
    dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "GAMES")
    wx, wy = dispcp.win_rect(m, S, disk)[:2]
    rows = [r[0] for r in dispcp.listing(m, S)]
    if "SKIES.O88" not in rows:
        sys.exit("skies: SKIES.O88 is not on the apps disk")
    row = dispcp.scroll_to(m, mo, S, os88marty.settle, wx, wy,
                           rows.index("SKIES.O88"))
    x, y = dispcp.row_xy(wx, wy, row)
    mo.dblclick(x, y)
    m.advance(frames=200)
    m.run()
    got = dispapps.pkg_seg(m, 0)
    if got is None:
        sys.exit("skies: SKIES.O88 did not open")
    slot, seg = got
    base = int.from_bytes(m.readseg(seg, 8, 2), "little")
    return slot, seg, base


class Bss:
    def __init__(self, m, seg, base):
        self.m, self.seg, self.base = m, seg, base

    def word(self, name):
        return int.from_bytes(self.m.readseg(
            self.seg, self.base + dispapps.bss_off("skies", name), 2), "little")

    def sword(self, name):
        v = self.word(name)
        return v - 65536 if v >= 32768 else v

    def byte(self, name):
        return self.m.readseg(self.seg,
                              self.base + dispapps.bss_off("skies", name), 1)[0]

    def metres(self, name):
        """A 16.8 dword position's whole metres, signed."""
        v = int.from_bytes(self.m.readseg(
            self.seg, self.base + dispapps.bss_off("skies", name), 4), "little")
        if v >= 1 << 31:
            v -= 1 << 32
        return v // 256


def until(m, pred, frames, step=15, what="the condition"):
    """Advance the guest in steps until pred() holds, or `frames` are spent.
    The guest's own clock, never the host's (docs/WRITING-TESTS.md 7)."""
    spent = 0
    while spent < frames:
        m.advance(frames=step)
        m.run()
        spent += step
        if pred():
            return True
    return False


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    bad = []

    with os88marty.launch(a.image, apps=a.apps, machine=a.machine) as m:
        slot, seg, base = open_game(m)
        r = Bss(m, seg, base)
        print("  SKIES.O88: window %d, segment %04x, bss at %04x"
              % (slot, seg, base))
        if r.byte("cs_want") == 0:
            bad.append("cs_adapter found no mode on this display")

        m.type_text("f")                        # into the bracket
        m.advance(frames=60)
        m.run()
        back, ww, wh = r.byte("cs_back"), r.word("cs_ww"), r.word("cs_wh")
        print("  backend %d, view %dx%d in a %dx%d box"
              % (back, ww, wh, r.word("cs_vw"), r.word("cs_vh")))
        if back == 0:
            bad.append("no raster was adopted: the bracket refused its mode")
        want = {3: (400, 112), 2: (320, 112), 1: (320, 144)}.get(back)
        if want and (ww, wh) != want:
            bad.append("backend %d drew a %dx%d view, not %dx%d (SPEC.md 88.3)"
                       % (back, ww, wh) + want)

        # --- on the runway, engine off, the take-off prompt up ----------------
        st, spd, thr = r.byte("cs_state"), r.word("cs_spd"), r.word("cs_thr")
        print("  at entry: state %d, speed %d, throttle %d, msg %d"
              % (st, spd, thr, r.byte("cs_msg")))
        if st != CS_ST_GROUND or spd or thr:
            bad.append("the first frame is not a parked aeroplane (state %d, "
                       "speed %d, throttle %d)" % (st, spd, thr))
        x0, z0, hdg0 = r.metres("cs_px"), r.metres("cs_pz"), r.word("cs_hdg")

        # --- it draws, and it advances -----------------------------------------
        f0 = r.word("cs_frames")
        m.pause()
        w, h, before = m.fbuf(0)
        m.run()
        m.advance(frames=90)
        m.run()
        f1 = r.word("cs_frames")
        m.pause()
        w, h, after = m.fbuf(0)
        m.run()
        moved = sum(1 for i in range(0, len(before), 3)
                    if before[i:i + 3] != after[i:i + 3])
        print("  frames %d -> %d on a parked aeroplane; %d of %d pixels moved"
              % (f0, f1, moved, w * h))
        if f1 <= f0:
            bad.append("cs_frames did not move (%d -> %d): the loop stopped"
                       % (f0, f1))

        # --- it takes off --------------------------------------------------------
        m.key("KeyW", down=True, up=False)      # full throttle...
        ok = until(m, lambda: r.word("cs_thr") >= 100, 180)
        m.key("KeyW", down=False, up=True)
        print("  throttle %d after holding W" % r.word("cs_thr"))
        if not ok:
            bad.append("W held for ten seconds did not open the throttle "
                       "(cs_thr = %d)" % r.word("cs_thr"))
        ok = until(m, lambda: r.word("cs_spd") >= VROT, 1200, 30)
        print("  speed %d (VROT %d), state %d" % (r.word("cs_spd"), VROT,
                                                 r.byte("cs_state")))
        if not ok:
            bad.append("the aeroplane never reached VROT (%d of %d)"
                       % (r.word("cs_spd"), VROT))
        m.key("ArrowDown", down=True, up=False) # ...the stick back...
        ok = until(m, lambda: r.byte("cs_state") == CS_ST_AIR, 300)
        m.key("ArrowDown", down=False, up=True)
        print("  state %d, pitch %d, altitude %d m"
              % (r.byte("cs_state"), r.sword("cs_pitch"), r.metres("cs_py")))
        if not ok:
            bad.append("the stick back at VROT did not lift off (state %d)"
                       % r.byte("cs_state"))
        alt0 = r.metres("cs_py")
        ok = until(m, lambda: r.metres("cs_py") >= alt0 + 30, 900, 30)
        print("  climbed to %d m at %d units of pitch, %d m/s"
              % (r.metres("cs_py"), r.sword("cs_pitch"), r.word("cs_spd") // 256))
        if not ok:
            bad.append("no climb: %d -> %d m" % (alt0, r.metres("cs_py")))
        f2 = r.word("cs_frames")
        m.advance(frames=90)
        m.run()
        f3 = r.word("cs_frames")
        print("  frames %d -> %d in flight" % (f2, f3))
        if f3 <= f2:
            bad.append("cs_frames stopped in flight (%d -> %d)" % (f2, f3))

        # --- it does not flash (SPEC.md 85.1's instrument) --------------------
        # Straight out of VRAM, once per DISPLAYED frame, in flight, where the
        # whole view is rewritten every frame.
        if back in (2, 3):
            fbseg, banks = (0xB800, 2) if back == 2 else (0xB000, 4)
            samples = []
            for _ in range(FRAMES):
                m.advance(frames=1)
                m.pause()
                samples.append(lit(m.read(fbseg << 4, banks * 0x2000)))
                m.run()
            s = sorted(samples)
            med = s[len(s) // 2]
            worst, at = 100, 0
            for i in range(1, len(samples) - 1):
                near = min(samples[i - 1], samples[i + 1])
                if near <= 0:
                    continue
                rr = 100 * samples[i] // near
                if rr < worst:
                    worst, at = rr, i
            print("  ink per displayed frame: min %d median %d max %d over %d; "
                  "thinnest against its neighbours %d%% (frame %d)"
                  % (s[0], med, s[-1], len(s), worst, at))
            if med == 0:
                bad.append("nothing is lit on any frame")
            elif worst < FLOOR:
                bad.append("a displayed frame carried %d%% of the ink of the "
                           "two around it: the frame is being taken apart ON "
                           "THE GLASS (SPEC.md 85.1, 88.3)" % worst)

        # --- it crashes, and comes back ------------------------------------------
        c0 = r.word("cs_crashes")
        m.key("ArrowUp", down=True, up=False)   # the nose over, into the ground
        ok = until(m, lambda: r.byte("cs_state") == CS_ST_CRASH, 1500, 30)
        m.key("ArrowUp", down=False, up=True)
        print("  crash: state %d, crashes %d -> %d, why at %04x"
              % (r.byte("cs_state"), c0, r.word("cs_crashes"),
                 r.word("cs_crashwhy")))
        if not ok:
            bad.append("the nose held down never met the ground (state %d, "
                       "altitude %d m)" % (r.byte("cs_state"), r.metres("cs_py")))
        elif r.word("cs_crashes") != c0 + 1:
            bad.append("cs_crashes read %d after one crash" % r.word("cs_crashes"))
        ok = until(m, lambda: r.byte("cs_state") == CS_ST_GROUND,
                   CS_CRASHT * 4 + 60, 15)
        x1, z1, hdg1 = r.metres("cs_px"), r.metres("cs_pz"), r.word("cs_hdg")
        print("  after the crash: state %d at (%d, %d) heading %d; spawned at "
              "(%d, %d) heading %d; throttle %d"
              % (r.byte("cs_state"), x1, z1, hdg1, x0, z0, hdg0, r.word("cs_thr")))
        if not ok:
            bad.append("the crash never reset (state %d after %d ticks)"
                       % (r.byte("cs_state"), CS_CRASHT * 4))
        elif (x1, z1) != (x0, z0) or hdg1 != hdg0 or r.word("cs_thr"):
            bad.append("the reset did not put the aeroplane back where it "
                       "started: (%d, %d)/%d against (%d, %d)/%d, throttle %d"
                       % (x1, z1, hdg1, x0, z0, hdg0, r.word("cs_thr")))

        m.type_text("f")                        # ...and F leaves (SPEC.md 11.2.1)
        m.advance(frames=90)
        m.run()
        q = r.byte("cs_quit")
        print("  after F: cs_quit %d" % q)
        if not q:
            bad.append("F did not leave the bracket")

    if bad:
        for b in bad:
            print("FAIL: " + b)
        return 1
    print("  ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
