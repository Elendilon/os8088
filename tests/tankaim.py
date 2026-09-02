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
LOCKE = 3.0                             # LOCK's bearing: inside the FRAME's own
                                        # sweep (TK_TURN * tk_lstep, six units
                                        # on a 1bpp adapter) and well outside
                                        # TK_LOCKIN. An ordinary frame turns
                                        # six units and lands three PAST it, so
                                        # the two arms cannot be confused
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


def reachable(boxq, turn, maxstep, grid=4096):
    """Is there a bearing no sequence of presses can put inside the box?

    THE QUESTION THIS ANSWERS IS THE ONE THAT WAS ASKED - "are there turns that
    could skip it?" - and it is answered by enumeration rather than by the
    algebra in SPEC.md 85.6.5.8, so that a slip in the algebra shows up here.

    The player's heading moves TK_TURN * tk_lstep units a frame and tk_lstep is
    capped at TK_MAXSTEP, so the reachable headings from wherever they start
    are a lattice of Q = TK_MAXSTEP * TK_TURN. A tank's bearing is anywhere;
    what matters is the WORST distance from a bearing to the nearest lattice
    point, and whether the box admits it."""
    q = turn * maxstep                          # the coarsest lattice, units
    worst, at = 0.0, 0.0
    for i in range(grid):                       # a bearing anywhere in one
        f = q * i / float(grid)                 # lattice cell, finely walked
        d = min(f, q - f)                       # ...to the nearer end of it
        if d > worst:
            worst, at = d, f
    return worst, at, q


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
    IN, BOXPX = const("TK_LOCKIN"), const("TK_BOXPX")
    BOXQ = MAXSTEP * TK_TURN * 2 + 1        # tank.asm's TK_BOXQ, derived the
                                            # same way it is there

    def fix(mode, err, cap, boxq):
        """tk_aimfix, in Python: the correction the gun applies."""
        if not mode & (AS_TRIM | AS_SNAP):
            return 0
        if not mode & AS_SNAP and abs(err) > boxq:
            return 0                            # outside the box: aim it
        return max(-cap, min(cap, err))         # yourself

    # --- 0. the arithmetic SPEC.md 85.6.5.8 rests on, before any of it runs ---
    worst, at, q = reachable(BOXQ, TK_TURN, MAXSTEP)
    print("  reachability: lattice %d units, worst bearing is %.3f units off "
          "the nearest reachable heading (at %+.3f); box is %.2f units "
          "(%d quarters, drawn at %d px)"
          % (q, worst, at, BOXQ / 4.0, BOXQ, BOXPX))
    if worst > BOXQ / 4.0:
        bad.append("a bearing %.3f units off the nearest commandable heading "
                   "cannot be put inside a box of %.2f units: there ARE turns "
                   "that skip it, and %.1f%% of bearings are unreachable "
                   "(SPEC.md 85.6.5.8)"
                   % (worst, BOXQ / 4.0, 100.0 * (worst - BOXQ / 4.0) / worst))
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

        # --- 3. the gun helps INSIDE THE BOX and nowhere else -----------------
        # SPEC.md 85.6.5.8. TRIM's window is the closed sight's own box; SNAP
        # keeps the open bracket, which is what the assist was before the box
        # and is on the wheel as the A/B for it. So the two bearings below are
        # the whole test: one inside the box and one outside it.
        lstep = g.b("tk_lstep")
        print("  tk_lstep %d -> lattice %d units, cap %d quarters; box %d "
              "quarters drawn at %d px" % (lstep, TK_TURN * lstep,
                                           g.cap() if False else
                                           min(TK_TURN * 2 * lstep, RETQ),
                                           BOXQ, BOXPX))
        for e in (3.0, 4.5):
            for mode, tag in ((0, "OFF"), (AS_TRIM, "TRIM"), (AS_SNAP, "SNAP")):
                g.wr("tk_aim", [mode])
                g.quiet()
                g.place(TK_NSTAT, e, RANGE, SIN)
                m.advance(frames=20)            # ...so tk_lockon measures it
                pa, err, cap = g.b("tk_pa"), g.sw("tk_aimq"), g.cap()
                m.type_text(" ")
                m.advance(frames=40)
                islot, sa = g.shell()
                corr = fix(mode, err, cap, BOXQ)
                want = (pa + int(math.floor((corr + 2) / 4.0))) & 0xFF
                print("  %-4s: tank %+.1f units (%d quarters, %s the %d-quarter"
                      " box); shell left at %s (want %d, a %d-quarter fix)"
                      % (tag, e, err, "IN" if abs(err) <= BOXQ else "outside",
                         BOXQ, sa, want, corr))
                if sa is None:
                    bad.append("%s at %+.1f: no shell spawned - tk_fire "
                               "refused and the assist was never reached"
                               % (tag, e))
                elif sa != want:
                    bad.append("%s at %+.1f units: the shell left at %d "
                               "against %d. An error of %d quarters %s the "
                               "%d-quarter box, with a cap of %d, must be "
                               "corrected by %d (SPEC.md 85.6.5.8)"
                               % (tag, e, sa, want, err,
                                  "inside" if abs(err) <= BOXQ else "outside",
                                  BOXQ, cap, corr))
                g.clear_movers()                # ...and the gun is free again

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
                err, rng = g.sw("tk_aimq"), g.w("tk_aimz")
                err = abs(err - fix(mode, err, g.cap(), BOXQ))   # what is LEFT
                win = HITQ // max(1, rng)
                lock = g.b("tk_locked")
                ok = lock == (1 if err <= win else 0)
                got.append(lock)
                print("  %-4s: tank %+.2f units, %d out -> %d quarters STILL "
                      "wrong after the gun, window %d, sight %s%s"
                      % (tag, e, rng, err, win, "CLOSED" if lock else "open",
                         "" if ok else "   <-- disagrees"))
                if not ok and abs(err - win) > HYS:
                    bad.append("%s at %+.2f units: the sight is %s with a "
                               "residual of %d quarters against a window of "
                               "%d - it is promising a shot the gun does not "
                               "keep, or hiding one it does (SPEC.md 85.6.5.7)"
                               % (tag, e, "closed" if lock else "open",
                                  err, win))
        if not (any(got) and not all(got)):
            bad.append("the reticle ladder came back all %s: it agreed with "
                       "itself and tested nothing"
                       % ("closed" if all(got) else "open"))

        # --- 5. a LOCK sweep ENDS on the tank --------------------------------
        # The witness is the error LEFT OVER, which is the user-facing claim
        # itself: sweep once at a tank three units ahead and see where the
        # sights finish. An ordinary frame turns TK_TURN * tk_lstep - six units
        # on a 1bpp adapter - and finishes three PAST it; a frame that lands
        # finishes ON it, and the steps behind the magnet must not carry the
        # sights off again (SPEC.md 85.6.5.3).
        #
        # This is what the FRACTION witness could not see. tk_paf caught the
        # magnet firing, and the magnet was firing all along - per STEP, with
        # the frame's remaining steps erasing the landing.
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
            left = abs(g.sw("tk_aimq"))         # ...how far off it FINISHED
            print("  %-4s: tank %+.2f units; %d frames; heading %.2f -> %.2f, "
                  "+%.2f; %d quarters off the tank at the end  [%d magnet "
                  "event(s)]"
                  % (tag, LOCKE, df, h0 / 256.0, h1 / 256.0, d / 256.0, left, n))
            if d < 256:
                bad.append("%s: the heading moved %.2f units, so no sweep "
                           "happened and nothing was measured" % (tag, d / 256.0))
            elif mode and left > IN + 2:
                bad.append("LOCK: a sweep at a tank %+.2f units ahead finished "
                           "%d quarters off it, outside TK_LOCKIN (%d): the "
                           "frame stepped OVER the tank instead of ending on "
                           "it (SPEC.md 85.6.5.3)" % (LOCKE, left, IN))
            elif not mode and left <= IN + 2:
                bad.append("OFF: a sweep finished %d quarters off the tank "
                           "with no assist live - the arms are not "
                           "distinguishable and the LOCK check above is "
                           "vacuous" % left)
            if mode and not n:
                bad.append("LOCK: tk_lockn counted no magnet events over a "
                           "sweep that crossed a tank")
            if not mode and n:
                bad.append("OFF: tk_lockn counted %d magnet events with no "
                           "assist live" % n)
            if not mode and (h1 & 0xFF):
                bad.append("OFF: the heading picked up a fraction of %d/256 "
                           "with no assist live at all" % (h1 & 0xFF))

    if bad:
        print("\ntankaim: FAIL")
        for s in bad:
            print("  - " + s)
        return 1
    print("\ntankaim: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
