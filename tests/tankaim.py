#!/usr/bin/env python3
"""TANK ATTACK's aim assists and its reticle (SPEC.md 85.6.5) do what they claim.

    python3 tests/tankaim.py [--machine os8088_5150_cga_gla]

The defect these answer is arithmetic, so this asserts arithmetic. A heading is
a byte, `TK_TURN` spends two units of it a TICK, and `tk_input` latches once a
FRAME while `tk_pmove` spends up to `TK_MAXSTEP` - so the finest turn a player
can COMMAND on a 1bpp adapter is six units, and `tk_espoil`'s own window is 4.1
units wide at 3,000 and 3.1 at the shell's longest reach. The sweep steps over
a distant tank and the phase of the press decides whether it was ever hittable.

FIVE CLAIMS.

**AIM OFF is unchanged**, because it is the control arm of a comparison
somebody makes on real hardware: two units a tick, and no fraction in the 8.8
heading.

**G cycles `tk_aimset`** and lands back on OFF.

**The gun corrects by `tk_aimcap` and no further.** A tank is placed at a KNOWN
bearing and the shell's heading is read out of the slot it spawned into. OFF
must leave it at `tk_pa`; SNAP must put it on the tank; TRIM must stop at half
the lattice `tk_lstep` says the player is on - which is the whole of SPEC.md
85.6.5.6, and is why TRIM changes no outcome at close range.

**The reticle does not lie** (85.6.5.7). Rather than assume a geometry, this
reads the code's OWN inputs back - `tk_aimq`, the measured error, and
`tk_aimz`, the range it was measured at - and asserts `tk_locked` against the
window those two imply. A ladder of bearings then has to produce both answers,
or the check is vacuous.

**LOCK lands ON a tank between one step and two**, witnessed by the 8.8
fraction, because every ordinary step is `TK_TURN` exactly and leaves `tk_paf`
alone - and by `tk_lockn`, which counts the events. That counter exists because
the field reported LOCK as "no difference from aim off" while it was firing:
what the eye had to see was a two-unit correction lasting one step.
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
MAXSTEP = 3                             # apps/tank's TK_MAXSTEP
AS_TRIM, AS_SNAP, AS_LOCK = 1, 2, 4
CYCLE = [0, AS_TRIM, AS_SNAP, AS_LOCK, AS_TRIM | AS_LOCK]

RANGE = 3000                            # where the six-unit quantum stops
                                        # fitting inside the window at all
LOCKE = 2.5                             # LOCK's bearing: between one step of
                                        # TK_TURN and two, so 85.6.5.3's
                                        # annulus contains it. DELIBERATELY NOT
                                        # A WHOLE NUMBER - every ordinary step
                                        # adds TK_TURN units and leaves tk_paf
                                        # alone, so a FRACTION in the 8.8
                                        # heading is a thing only a magnet can
                                        # have put there. Parity of tk_pa is
                                        # not that witness and looks like one
HOLD = 4                                # emulator frames a LOCK arm holds D
                                        # between looks. The sweep may cross
                                        # the tank only ONCE for the witness to
                                        # read, and it cannot cross twice: once
                                        # passed, the error changes sign and
                                        # 85.6.5.3's direction test refuses
RETICLE = (1.0, 2.75, 4.25)             # the bearings the reticle ladder walks


def const(name):
    """A tank.asm equate, read out of the source so this cannot drift."""
    for line in open(ASM, encoding="utf-8"):
        m = re.match(r"\s*%s\s+equ\s+(\w+)" % re.escape(name), line)
        if m:
            return int(m.group(1), 0)
    sys.exit("tankaim: tank.asm has no %s" % name)


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

    def quiet(self):
        """An empty, frozen world: tk_spawn = 0 shuts tk_update's spawner off
        at its own gate, so the only tank in play is the one placed here."""
        self.wr("tk_spawn", [0])
        self.wr("tk_dead", [0])
        self.clear_movers()

    def cap(self):
        """tk_aimcap, in quarter units, for the mode and frame rate in play."""
        aim = self.b("tk_aim")
        if aim & AS_SNAP:
            return const("TK_RETQ")
        if aim & AS_TRIM:
            return min(TK_TURN * 2 * self.b("tk_lstep"), const("TK_RETQ"))
        return 0

    def place(self, slot, err, rng, sin):
        """A tank `err` units off the sights at `rng`.

        `err` may be fractional, which the guest's own 256-entry table cannot
        express - so a whole number is placed through that table, to the byte,
        and anything else through the same angle in floating point. The guest
        derives the bearing from the POSITION either way."""
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
    RETQ, HITQ, HYS = const("TK_RETQ"), const("TK_HITQ"), const("TK_LOCKHYS")
    SIN = sintab()
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
        print("  backend %d, viewport %dx%d, aim %d, steps a frame %d"
              % (g.b("tk_back"), g.w("tk_vw"), g.w("tk_vh"), g.b("tk_aim"),
                 g.b("tk_lstep")))
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
            bad.append("AIM OFF left a fraction of %d in tk_paf: only a magnet "
                       "may put one there (SPEC.md 85.6.5.4)" % (h1 & 0xFF))
        if g.w("tk_lockn"):
            bad.append("tk_lockn is %d with no assist live: LOCK fired under "
                       "AIM OFF" % g.w("tk_lockn"))

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

        # --- a fresh, quiet, FROZEN world for the three fixtures -------------
        # Section 1 spends the better part of a minute of guest time with a
        # tank hunting, so by here the player is usually dead and sometimes out
        # of lives - and both refuse: tk_fire tests tk_dead and tk_over, and
        # tk_input zeroes the latch under either. A fixture built on a finished
        # game measures nothing and reports it as "no shell".
        print("  state before the fixtures: over=%d dead=%d lives=%d"
              % (g.b("tk_over"), g.b("tk_dead"), g.b("tk_lives")))
        m.type_text("n")
        m.advance(frames=90)
        g.quiet()
        g.wr("tk_pause", [1])           # POKED, never toggled: a keystroke that
        m.advance(frames=40)            # misses leaves an arm running the wrong
        if g.b("tk_over") or g.b("tk_dead") or not g.b("tk_pause"):
            bad.append("no live frozen round to build the fixtures on "
                       "(over=%d dead=%d pause=%d)"
                       % (g.b("tk_over"), g.b("tk_dead"), g.b("tk_pause")))

        # --- 3. the gun corrects by tk_aimcap and no further ------------------
        lstep = g.b("tk_lstep")
        for mode, tag in ((0, "OFF"), (AS_SNAP, "SNAP"), (AS_TRIM, "TRIM")):
            g.wr("tk_aim", [mode])
            g.quiet()
            g.place(TK_NSTAT, 4, RANGE, SIN)
            m.advance(frames=20)                # ...so tk_lockon measures it
            pa, err, cap = g.b("tk_pa"), g.sw("tk_aimq"), g.cap()
            m.type_text(" ")
            m.advance(frames=40)
            islot, sa = g.shell()
            corr = max(-cap, min(cap, err))
            want = (pa + int(math.floor((corr + 2) / 4.0))) & 0xFF
            print("  %-4s: tank +4 units at %d out, error %d quarters, cap %d;"
                  " shell left at %s (want %d)"
                  % (tag, RANGE, err, cap, sa, want))
            if sa is None:
                bad.append("%s: no shell spawned - tk_fire refused and the "
                           "assist was never reached" % tag)
            elif sa != want:
                bad.append("%s: the shell left at %d against the %d its own "
                           "cap of %d quarters allows for an error of %d: "
                           "tk_fire is not clamping to tk_aimcap"
                           % (tag, sa, want, cap, err))
            g.clear_movers()                    # ...and the gun is free again
        if lstep < 1 or (AS_TRIM and min(TK_TURN * 2 * lstep, RETQ) >= RETQ):
            print("  note: tk_lstep is %d, so TRIM's cap (%d quarters) is at "
                  "the bracket and is not distinguishable from SNAP here"
                  % (lstep, min(TK_TURN * 2 * lstep, RETQ)))

        # --- 4. the reticle does not lie -------------------------------------
        # Read the code's OWN inputs back rather than assuming a geometry:
        # tk_aimq is the error it measured and tk_aimz the range it measured
        # it at, so the window those imply is what tk_locked has to agree with.
        got = []
        for mode, tag in ((0, "OFF"), (AS_TRIM, "TRIM"), (AS_SNAP, "SNAP")):
            for e in RETICLE:
                g.wr("tk_aim", [mode])
                g.quiet()                       # nothing in view: the sight
                m.advance(frames=25)            # opens and tk_lockwas clears,
                g.place(TK_NSTAT, e, RANGE, SIN)   # so HYSTERESIS is not in play
                m.advance(frames=25)
                err, rng = abs(g.sw("tk_aimq")), g.w("tk_aimz")
                win = max(HITQ // max(1, rng), g.cap())
                lock = g.b("tk_locked")
                ok = lock == (1 if err <= win else 0)
                got.append(lock)
                print("  %-4s: tank %+.2f units, %d out -> error %d quarters, "
                      "window %d, sight %s%s"
                      % (tag, e, rng, err, win, "CLOSED" if lock else "open",
                         "" if ok else "   <-- disagrees"))
                if not ok and abs(err - win) > HYS:
                    bad.append("%s at %+.2f units: the sight is %s with an "
                               "error of %d quarters against a window of %d - "
                               "it is promising a shot the gun does not keep, "
                               "or hiding one it does (SPEC.md 85.6.5.7)"
                               % (tag, e, "closed" if lock else "open",
                                  err, win))
        if not (any(got) and not all(got)):
            bad.append("the reticle ladder came back all %s: it agreed with "
                       "itself and tested nothing"
                       % ("closed" if all(got) else "open"))

        # --- 5. LOCK lands ON a tank between one step and two ----------------
        # The witness is the FRACTION. Every step off AIM OFF is TK_TURN, so
        # the 8.8 heading walks a whole number of units off wherever the press
        # began; a magnet onto a tank at 2.5 units cannot leave one there.
        for mode, tag in ((0, "OFF"), (AS_LOCK, "LOCK")):
            g.wr("tk_pause", [1])
            m.advance(frames=20)
            g.wr("tk_aim", [mode])
            g.quiet()
            g.place(TK_NSTAT, LOCKE, RANGE, SIN)
            g.wr("tk_paf", [0])                 # the witness starts clean
            g.wr("tk_lockn", b"\0\0")
            h0, f0 = g.head88(), g.w("tk_frames")
            g.wr("tk_pause", [0])               # ...and then let it step
            m.advance(frames=6)
            m.key("KeyD", down=True, up=False)
            for _ in range(8):                  # ...until the sweep has
                m.advance(frames=HOLD)          # actually MOVED. A fixed hold
                if (g.head88() - h0) & 0xFFFF >= 256:   # is 1.2 game frames at
                    break                       # 6 fps and can fall entirely
            m.key("KeyD", down=False, up=True)  # between two tk_input polls
            g.wr("tk_pause", [1])
            m.advance(frames=20)
            h1, df, n = g.head88(), g.w("tk_frames") - f0, g.w("tk_lockn")
            d = (h1 - h0) & 0xFFFF
            if not 256 <= d <= TK_TURN * MAXSTEP * 256 * 2:
                print("     [pause=%d kturn=%d dead=%d over=%d live=%s]"
                      % (g.b("tk_pause"), g.b("tk_kturn"), g.b("tk_dead"),
                         g.b("tk_over"),
                         [i for i, t in g.movers().items() if t == OT_TANK]))
            print("  %-4s: tank %+.2f units; %d frames; heading %.2f -> %.2f, "
                  "+%.2f  [fraction %d/256, %d magnet event(s)]"
                  % (tag, LOCKE, df, h0 / 256.0, h1 / 256.0, d / 256.0,
                     h1 & 0xFF, n))
            if not 256 <= d <= TK_TURN * MAXSTEP * 256 * 2:
                bad.append("%s: the heading moved %.2f units over %d frames, "
                           "outside the one sweep this asks about"
                           % (tag, d / 256.0, df))
            elif mode and not (h1 & 0xFF):
                bad.append("LOCK: a tank %+.2f units off the sights left the "
                           "8.8 heading a whole number of units on (+%.2f): "
                           "every ordinary step is TK_TURN exactly, so the "
                           "sweep stepped OVER the tank rather than landing "
                           "on it" % (LOCKE, d / 256.0))
            elif not mode and (h1 & 0xFF):
                bad.append("OFF: the heading picked up a fraction of %d/256 "
                           "with no assist live at all" % (h1 & 0xFF))
            if mode and not n:
                bad.append("LOCK: tk_lockn counted no magnet events over a "
                           "sweep that crossed a tank")
            if not mode and n:
                bad.append("OFF: tk_lockn counted %d magnet events with no "
                           "assist live" % n)

    if bad:
        print("\ntankaim: FAIL")
        for s in bad:
            print("  - " + s)
        return 1
    print("\ntankaim: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
