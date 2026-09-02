#!/usr/bin/env python3
"""TANK ATTACK's aim assists (SPEC.md 85.6.5) do what they claim.

    python3 tests/tankaim.py [--machine os8088_5150_cga_gla]

The defect these answer is arithmetic, so this asserts arithmetic. A heading
is a byte, `TK_TURN` spends two units of it a TICK, and `tk_input` latches once
a FRAME while `tk_pmove` spends up to `TK_MAXSTEP` - so the finest turn a
player can COMMAND on a 1bpp adapter is six units, and `tk_espoil`'s own
window is 4.1 units wide at 3,000 and 3.1 at the shell's longest reach. The
sweep steps over a distant tank and the phase of the press decides whether it
was ever hittable.

FOUR CLAIMS, and the first is the one that matters most.

**AIM OFF is unchanged.** It is the control arm of a comparison somebody is
about to make on real hardware, so it has to be the thing it was: two units a
tick, the same assertion tests/tank.py makes about SPEC.md 85.6.4, taken here
against a heading that is now 8.8 rather than 8.

**G cycles `tk_aimset`** and lands back on OFF.

**FINE's floor is ONE unit.** The ramp is in 1/256ths and `tk_khold` is its own
index, so the heading a press has moved must be the ramp's prefix sum for the
ticks it has been held - which is what makes a one-frame tap one unit on the
machine this game is for, rather than the three a whole-unit ramp would give.

**SNAP aims at the tank and not at the hull.** A tank is placed at a KNOWN
bearing and the shell's heading is read out of the slot it spawned into: with
OFF it must leave at `tk_pa`, and with SNAP at the tank's own bearing. That is
`tk_aimerr`'s scale and sign tested end to end, and LOCK rests on the same
routine - so LOCK is then only asked the one thing that is its own: a tank
between one step and two is LANDED on, which shows up as a heading that has
gone ODD off an even lattice.
"""
import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88marty                                            # noqa: E402
import dispapps                                             # noqa: E402
import tank as tanktest                                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASM = os.path.join(ROOT, "apps", "tank", "tank.asm")

OT_FREE, OT_TANK, OT_SHELL = 0, 4, 5
TK_NSTAT, TK_NOBJ = 12, 18
TK_TURN = 2
AS_SNAP, AS_LOCK, AS_FINE = 1, 2, 4
CYCLE = [0, AS_SNAP, AS_LOCK, AS_FINE, AS_SNAP | AS_FINE]

SNAPE = 4                               # the bearing SNAP is tested at, in
                                        # units - inside TK_RETQ's five
LOCKE = 2.5                             # ...and LOCK's, which is between one
                                        # step of TK_TURN and two, so the
                                        # annulus of SPEC.md 85.6.5.3 contains
                                        # it. IT IS DELIBERATELY NOT A WHOLE
                                        # NUMBER: every ordinary step adds
                                        # exactly TK_TURN units and leaves
                                        # tk_paf alone, so a FRACTION in the
                                        # 8.8 heading is a thing only a magnet
                                        # can have put there. Parity of tk_pa
                                        # is not that witness and looked like
                                        # one - a magnet onto 2.75 units moves
                                        # tk_pa by two and banks the rest
RANGE = 3000                            # where the six-unit quantum stops
                                        # fitting inside the window at all
MAXSTEP = 3                             # apps/tank's TK_MAXSTEP
HOLD = 12                               # emulator frames a LOCK arm holds D:
                                        # about one 6 fps game frame, because
                                        # the parity witness only reads if the
                                        # sweep crosses the tank ONCE


def ramp():
    """tk_ramp, read out of the source so this cannot drift from it."""
    for line in open(ASM, encoding="utf-8"):
        m = re.match(r"\s*tk_ramp:\s*dw\s+(.*)", line)
        if m:
            return [int(x) for x in m.group(1).split(",")]
    sys.exit("tankaim: tank.asm has no tk_ramp")


def sintab():
    """tksin.inc, for placing a tank at a bearing the guest will agree with."""
    out = []
    for line in open(os.path.join(ROOT, "apps", "tank", "tksin.inc"),
                     encoding="utf-8"):
        line = line.strip()
        if line.startswith("dw"):
            out += [int(x) for x in line[2:].split(",")]
    if len(out) != 256:
        sys.exit("tankaim: tksin.inc is %d entries, not 256" % len(out))
    return out


class Game:
    """The package's own state, by name."""

    def __init__(self, m, seg, base):
        self.m, self.seg, self.base = m, seg, base

    def off(self, name):
        return self.base + dispapps.bss_off("tank", name)

    def rd(self, name, n=2, i=0):
        return self.m.readseg(self.seg, self.off(name) + i, n)

    def b(self, name, i=0):
        return self.rd(name, 1, i)[0]

    def w(self, name, i=0):
        return int.from_bytes(self.rd(name, 2, i), "little")

    def sw(self, name, i=0):
        v = self.w(name, i)
        return v - 0x10000 if v & 0x8000 else v

    def wr(self, name, data, i=0):
        self.m.write((self.seg << 4) + self.off(name) + i, bytes(data))

    def head88(self):
        """The 8.8 heading SPEC.md 85.6.5.4 made of tk_pa and tk_paf."""
        return (self.b("tk_pa") << 8) | self.b("tk_paf")

    def movers(self):
        t = self.rd("tk_otype", TK_NOBJ)
        return {i: t[i] for i in range(TK_NSTAT, TK_NOBJ)}

    def clear_movers(self):
        for i in range(TK_NSTAT, TK_NOBJ):
            self.wr("tk_otype", [OT_FREE], i)

    def place(self, slot, err, rng, sin):
        """A tank `err` units off the sights at `rng`.

        `err` may be fractional, which the guest's own 256-entry table cannot
        express - so a whole number is placed through that table, to the byte,
        and anything else through the same angle in floating point. The guest
        derives the bearing from the POSITION either way; the table is only
        used where it can be exact."""
        if err == int(err):
            a = (self.b("tk_pa") + int(err)) & 0xFF
            dx, dz = sin[a] / 16384.0, sin[(a + 64) & 0xFF] / 16384.0
        else:
            r = (self.b("tk_pa") + err) * math.pi / 128.0
            dx, dz = math.sin(r), math.cos(r)
        x = (self.w("tk_px") + int(rng * dx)) & 0x1FFF
        z = (self.w("tk_pz") + int(rng * dz)) & 0x1FFF
        self.wr("tk_ox", x.to_bytes(2, "little"), slot * 2)
        self.wr("tk_oz", z.to_bytes(2, "little"), slot * 2)
        self.wr("tk_oa", [0], slot)
        self.wr("tk_ocool", [255], slot)        # ...and it may not shoot back
        self.wr("tk_otim", [0], slot)
        self.wr("tk_otype", [OT_TANK], slot)

    def quiet(self):
        """An empty, frozen world: tk_spawn = 0 shuts tk_update's spawner off
        at its own gate, so the only tank in play is the one placed here and
        the magnet has exactly one thing it can land on."""
        self.wr("tk_spawn", [0])
        self.wr("tk_dead", [0])
        self.clear_movers()

    def shell(self):
        """The heading of the player's live shell, if there is one."""
        t = self.rd("tk_otype", TK_NOBJ)
        for i in range(TK_NSTAT, TK_NOBJ):
            if t[i] == OT_SHELL:
                return i, self.b("tk_oa", i)
        return None, None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_cga_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    RAMP, SIN = ramp(), sintab()
    bad = []

    with os88marty.launch(a.image, apps=a.apps, machine=a.machine) as m:
        slot, seg, base = tanktest.open_game(m)
        g = Game(m, seg, base)
        print("  TANK.O88: window %d, segment %04x, bss at %04x"
              % (slot, seg, base))
        m.type_text("f")                        # into the bracket
        m.advance(frames=150)
        if g.w("tk_back") & 0xFF == 0:
            sys.exit("tankaim: the bracket refused its mode - nothing to test")
        print("  backend %d, viewport %dx%d, aim %d"
              % (g.b("tk_back"), g.w("tk_vw"), g.w("tk_vh"), g.b("tk_aim")))
        if g.b("tk_aim") != 0:
            bad.append("tk_aim came up at %d: OFF is not the default, so the "
                       "game changed for somebody who never asked it to"
                       % g.b("tk_aim"))

        # --- 1. AIM OFF is the control arm, and is unchanged -----------------
        f0, t0, h0 = g.w("tk_frames"), g.w("tk_last"), g.head88()
        m.key("KeyD", down=True, up=False)
        m.advance(frames=300)
        f1, t1, h1 = g.w("tk_frames"), g.w("tk_last"), g.head88()
        m.key("KeyD", down=False, up=True)
        m.advance(frames=30)
        df, dt = f1 - f0, (t1 - t0) & 0xFFFF
        da = ((h1 - h0) & 0xFFFF) / 256.0
        print("  OFF: held D over %d frames / %d ticks: heading +%.2f units, "
              "%.2f a tick, %.2f a frame"
              % (df, dt, da, da / max(1, dt), da / max(1, df)))
        if dt < 20 or da == 0:
            bad.append("the OFF turn sample is degenerate (%d ticks, %.2f "
                       "units): nothing was measured" % (dt, da))
        elif not (TK_TURN * 0.6 <= da / dt <= TK_TURN * 1.15):
            bad.append("AIM OFF turned %.2f units a tick against TK_TURN = %d: "
                       "the CONTROL arm has moved, so nothing measured against "
                       "it means anything (SPEC.md 85.6.4)" % (da / dt, TK_TURN))
        if h1 & 0xFF:
            bad.append("AIM OFF left a fraction of %d in tk_paf: with no ramp "
                       "the step is a whole number of units and the 8.8 "
                       "heading must carry nothing" % (h1 & 0xFF))

        # --- 2. G cycles tk_aimset and comes back to OFF ---------------------
        seen = []
        for _ in range(len(CYCLE) + 1):
            m.type_text("g")
            m.advance(frames=20)
            seen.append(g.b("tk_aim"))
        want = CYCLE[1:] + CYCLE[:2]
        print("  G cycles: %s (want %s)" % (seen, want))
        if seen != want:
            bad.append("G walked %s and not %s: the cycle does not visit every "
                       "combination, or does not come home to OFF"
                       % (seen, want))

        # --- a fresh, quiet round before the three fixtures ------------------
        # Section 1 spends the better part of a minute of GUEST time with a
        # tank hunting, so by here the player is usually dead and sometimes out
        # of lives - and BOTH of those refuse: tk_fire tests tk_dead and
        # tk_over, and tk_input zeroes the latch under either. A fixture built
        # on a finished game measures nothing and reports it as "no shell".
        print("  state before the fixtures: over=%d dead=%d lives=%d"
              % (g.b("tk_over"), g.b("tk_dead"), g.b("tk_lives")))
        m.type_text("n")
        m.advance(frames=90)
        g.quiet()
        print("  after N and a quiet world: over=%d dead=%d lives=%d"
              % (g.b("tk_over"), g.b("tk_dead"), g.b("tk_lives")))
        if g.b("tk_over") or g.b("tk_dead"):
            bad.append("N did not give a live round back (over=%d dead=%d): "
                       "everything below it is a refusal and not a result"
                       % (g.b("tk_over"), g.b("tk_dead")))

        # --- 3. FINE's floor is ONE unit, and tk_khold is the witness --------
        # tk_khold IS the ramp's index and advances exactly once a step, so the
        # heading a fresh press has moved must be the ramp's prefix sum for it.
        # Read while the key is still DOWN: a release zeroes the counter.
        g.wr("tk_aim", [AS_FINE])
        g.quiet()
        m.advance(frames=40)
        h0 = g.head88()
        if g.b("tk_dead") or g.b("tk_over"):
            bad.append("the player was dead or the game over before the FINE "
                       "tap: tk_input zeroes the latch under either and the "
                       "sample below is of nothing")
        m.key("KeyD", down=True, up=False)
        k, h1 = 0, h0                   # ...until a whole GAME frame has gone
        for _ in range(6):              # by: one is 10 of these on a 6 fps
            m.advance(frames=4)         # adapter and 14 on a 4.32 fps one, so
            k, h1 = g.b("tk_khold"), g.head88()   # a fixed wait either misses
            if k:                       # the press or saturates the ramp
                break
        m.key("KeyD", down=False, up=True)
        m.advance(frames=30)
        got = (h1 - h0) & 0xFFFF
        wantq = sum(RAMP[min(i, len(RAMP) - 1)] for i in range(k))
        print("  FINE: %d ticks held -> heading +%d/256 = %.2f units "
              "(ramp says %d = %.2f)"
              % (k, got, got / 256.0, wantq, wantq / 256.0))
        if not 1 <= k < len(RAMP):
            bad.append("the FINE sample held %d ticks, outside the ramp's own "
                       "1..%d: it measured the hold and not the tap"
                       % (k, len(RAMP) - 1))
        elif got != wantq:
            bad.append("a %d-tick tap moved the heading %d/256 where tk_ramp "
                       "sums to %d: the ramp is not what is being spent"
                       % (k, got, wantq))
        elif k >= 3 and sum(RAMP[:3]) != 256:
            bad.append("tk_ramp's first three sum to %d and not 256: a "
                       "one-frame tap on a 1bpp adapter is %.2f units and not "
                       "the byte heading's own floor of one"
                       % (sum(RAMP[:3]), sum(RAMP[:3]) / 256.0))

        # --- 4. SNAP leaves at the TANK's bearing, not the hull's ------------
        # Paused, so the world is a fixture: tk_update does not run and nothing
        # spawns, wanders or shoots back. tk_fire is deliberately reachable
        # there - it tests tk_dead and tk_over and not tk_pause.
        if not g.b("tk_pause"):
            m.type_text("p")
            m.advance(frames=40)
        if not g.b("tk_pause"):
            bad.append("the world would not pause, so the fixtures below are "
                       "being built under a running simulation")
        for mode, tag in ((0, "OFF"), (AS_SNAP, "SNAP")):
            g.wr("tk_aim", [mode])
            g.clear_movers()
            g.place(TK_NSTAT, SNAPE, RANGE, SIN)
            pa = g.b("tk_pa")
            m.type_text(" ")
            m.advance(frames=40)
            islot, sa = g.shell()
            want = (pa + (SNAPE if mode else 0)) & 0xFF
            print("  %-4s: tank at %+d units, %d out; heading %d, shell left "
                  "at %s (want %d)" % (tag, SNAPE, RANGE, pa, sa, want))
            if sa is None:
                bad.append("%s: no shell spawned - tk_fire refused and the "
                           "assist was never reached" % tag)
            elif sa != want:
                bad.append("%s: the shell left at %d against %d - a tank %+d "
                           "units off the sights at %d out %s"
                           % (tag, sa, want, SNAPE, RANGE,
                              "moved a shot that must not move" if not mode
                              else "did not move the shot onto it, so "
                                   "tk_aimerr's scale or sign is wrong"))
            g.clear_movers()                    # ...and the gun is free again

        # --- 5. LOCK lands ON a tank between one step and two ----------------
        # The witness is PARITY. Every step off AIM OFF is TK_TURN, so the
        # heading walks an even lattice off wherever the press began; a magnet
        # onto a tank at an ODD offset takes it off that lattice and no later
        # even step puts it back. It survives however many steps the frame
        # owed, which is what makes it race-free on a machine whose frame is
        # three ticks (SPEC.md 85.6.5.3).
        for mode, tag in ((0, "OFF"), (AS_LOCK, "LOCK")):
            g.wr("tk_pause", [1])               # place it on a frozen world -
            m.advance(frames=20)                # POKED, because a toggle that
            g.wr("tk_aim", [mode])              # misses leaves the arm running
            g.quiet()                           # the wrong way round in silence
            g.place(TK_NSTAT, LOCKE, RANGE, SIN)
            g.wr("tk_lockr", b"\0\0")
            g.wr("tk_locks", b"\0\0")
            g.wr("tk_paf", [0])                 # the witness starts clean
            h0, f0 = g.head88(), g.w("tk_frames")
            g.wr("tk_pause", [0])               # ...and then let it step
            m.advance(frames=6)
            m.key("KeyD", down=True, up=False)
            m.advance(frames=HOLD)
            m.key("KeyD", down=False, up=True)
            g.wr("tk_pause", [1])
            m.advance(frames=20)
            got, df = g.head88(), g.w("tk_frames") - f0
            d = (got - h0) & 0xFFFF
            print("  %-4s: tank at %+.2f units; %d frames; heading %.2f -> "
                  "%.2f, +%.2f  [fraction %d/256, step %d, inner %d, "
                  "pick %d, live %s]"
                  % (tag, LOCKE, df, h0 / 256.0, got / 256.0, d / 256.0,
                     got & 0xFF, g.sw("tk_locks"), g.sw("tk_lockr"),
                     g.sw("tk_aimq"),
                     [i for i, t in g.movers().items() if t == OT_TANK]))
            if not 256 <= d <= TK_TURN * MAXSTEP * 256 * 2:
                bad.append("%s: the heading moved %.2f units over %d frames, "
                           "outside the one sweep this is asked about: the "
                           "sample says nothing about the crossing"
                           % (tag, d / 256.0, df))
            elif mode and not got & 0xFF:
                bad.append("LOCK: a tank %+.2f units off the sights left the "
                           "8.8 heading a whole number of units on (+%.2f, "
                           "fraction 0): every ordinary step is TK_TURN exactly"
                           ", so the sweep stepped OVER the tank rather than "
                           "landing on it" % (LOCKE, d / 256.0))
            elif not mode and got & 0xFF:
                bad.append("OFF: the heading picked up a fraction of %d/256 "
                           "with no assist live at all: something other than "
                           "TK_TURN moved it" % (got & 0xFF))

    if bad:
        print("\ntankaim: FAIL")
        for s in bad:
            print("  - " + s)
        return 1
    print("\ntankaim: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
