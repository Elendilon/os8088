#!/usr/bin/env python3
"""BONANZA: the guest's physics equals bbcourse.Physics, step for step (SPEC.md 128.10.7, 128.11.8, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_phys.py [--adapter cga|herc|both] [--leg bench|scen|replay|all]
                                                      [--only NAME ...]
    python3 tests/bonanza_phys.py --red NAME        (a red arm, below)
    python3 tests/bonanza_phys.py --check           (the host half: every scenario built and proved on the
                                                     model, every red arm's broken copy assembled; and the
                                                     SPLIT leg, tests/bonanza_dsplit.py, under unicorn)

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
       goal   from (12, 6) at gvx 250: the play's comparison ENDS the frame
              after the model's goal step (a finish line, grounded or in the
              air; the finish sequence, 128.22.6, runs on to the play's end),
              and the face's held-log line (6) reads `<NAME> <time> s goal`
              for the model's goal step
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

  5  WAVE 4 (SPEC.md 128.14.4, 128.14.14): every frame also compares 128.14.4.7's
     state - the material, bz_ckpt, bz_ckmat, bz_cksn, bz_inmo, bz_hid and the
     counters bz_nckpt, bz_npad, bz_nlip, bz_nspr, bz_nret (Physics.state4) - and
     on MOON and PEAK (SUMMIT) these replays, FOUND by a search on the model and
     proved there:
       flag           rolled off MOON's flag 0 into a pit: respawned ON the flag
       flagmat-peak   glass dropped onto PEAK's flag 3 (touched in the air),
                      shattered, respawned there AS GLASS (the flag's ball)
       flagmat-moon   glass dropped onto MOON's flag 2: respawned AS RUBBER
       padswap-*      every pad of MOON and PEAK, another ball rolled on it with
                      an arrow held: bz_mat, bz_mrec, bz_fta and bz_ftg the
                      model's material's at EVERY frame
       cup-128        rolled into PEAK's cup at 128: holed out, the play over
       cup-lip        across the mouth faster than the capture: lipped out
                      (gvz BZ_LIPZ), bz_nlip 1, rolled on
       cup-stun       a stunned steel ball in the mouth holes out as it ends
       cup-shatter    a shattering glass ball in the mouth does not
       spring-tier    rubber up PEAK's spring 1 onto the upper tier
       spring-max     a rubber bounce on spring 2 (its launch POKED to 360 in
                      the part and the model, where max and sum differ: the
                      shipped springs are BZ_VZMAX, 128.14.19 item 6) leaves at
                      the max, not the sum
       spring-shatter glass shattering on a spring is not launched
       return         RETURN mid-roll from MOON's flag 1: back on it, bz_nret 1
       tilt           a TILT log on FIRST: caps 0 - 8 on both axes, then Right
                      held at cap 8 and dropped to 2 - levels 8, 6, 4, 2
     and their red arms:
  ckpt       the respawn at bz_safe on a CKPT course: flag parts
  ckmat      bz_ckmat from the touching ball, not the flag's: flagmat-moon parts
  padftg     ftg not rebuilt at a swap: padswap's tables (and its steps)
  cupv       the capture without the speed test: cup-lip holes out
  springsum  the spring ADDS to the rebound: spring-max's apex
  tiltcap    the min before the decay: tilt's 8, 6, 4, 2 become 8, 2

  6  WAVE 6 (SPEC.md 128.16.3.1, 128.16.4, 128.16.14): every frame also compares
     128.16.4.3's five - bz_btok, bz_stf, bz_nboost, bz_drx, bz_dry
     (Physics.state6) - and these replays, FOUND and PROVED on the model (the
     take-off steps and the contacts searched, so a re-laid course or a retuned
     constant re-finds them; every expected value the model's or MATERIALS',
     never a literal, SPEC.md 128.16.11):
       boost         rubber on the PLAYGROUND's apron: a Hop, Space 2 steps before
                     its first contact: nboost 1, gvz = BOOST, stf = BZ_STRS
       boostclimb    onto the 1.5-unit ledge from the apron at the cap, a Hop and
                     its boost
       boostdrop     a Hop off the 1-unit top onto the apron, Space at the contact:
                     a boost with sqf 0 although its impact passes 384
       boostfall     (round 3b: a BOOST, the bounce plus BADD; was:)
                     a Hop off the 2-unit top, Space at the contact: a contact
                     Hop at the rebound, nboost 0
       pumpchk       Space at every contact of the chain: one boost, then contact Hops
       bouncefirst   a Hop, no Space at its first contact (a bounce), Space at its
                     second: a contact Hop, nboost 0
       gripchain     (re-keyed by wave 6b with mid-flight taps: part 7)
       rampnot       a Hop whose first contact is on a ramp (TRIAL's, searched),
                     Space before it: no boost
       sandnot, matnot  the same on the PLAYGROUND's sand lane and its mat
       liftnot       a Hop on MILL's lift slab, Space before its contact: no boost
       springarm     (round 3b: the launch TAKES the token, a boost; wave 6's
                     springnot:) a Hop on PEAK's spring (searched): the spring's launch spends
                     the token, Space at its flight's first contact a contact Hop
       steelglass-*  steel and glass: contact Hops, never a boost
       drag-rest     one arrow from rest on the PLAYGROUND's longest level run
                     (searched): |gvx| reaches axis_feel's top (the remainders
                     compared every frame); and THE DRAG'S COST, ASSERTED: a
                     second replay of it breaks at bz_gax's entry and at its
                     return (off the stack), every DRAGGED call's span in
                     MartyPC's cycles, the worst at most DRAG_PRICE (the as-built
                     routine's 428, SPEC.md 128.16.3.1) plus 25%
       drag-cap      one arrow from the cap: |gvx| falls back to the top
       gripglass     glass at the cap, Grip held: stopped in axis_feel's steps
     and their red arms:
  pump       the token set again by a contact Hop: pumpchk's second boost
  rampboost  rule 4's slope test left out: rampnot boosts
  tokbst     the token cleared only by a boost: bouncefirst boosts
  slabcell   rule 4 on the slab's substituted cell (bz_fslab): liftnot boosts
  springoff  round 3b: round 3's spring, the launch spends the token:
             springarm does not boost (wave 6's springtok, inverted)
  noadd      round 3b: round 3's boost (BOOST, rule 5): boostfall a contact Hop
  nospent    round 3b: a boost never spent: spentspring boosts twice
  ceildrag   the guest keeps wave 2's round-up drag: drag-rest (|gvx| settles
             at 189, the remainders 0)
  slowdrag   the remainder's split done twice more, by DIV: the drag's span
  (`hopagain` is glass's since wave 6: rubber's Space at the Hop's own landing
  is the `boost` replay's)

  7  WAVE 6B (SPEC.md 128.17.4, 128.17.10): the boost ARMED by a second Space
     edge anywhere in the Hop's flight (bz_btok 2), and the LATE GRACE: an
     unarmed bouncing first contact that passes rules 3 - 5 opens BGRACE steps
     in which a Space edge converts the rebound into the boost exactly.  Every
     frame also compares bz_bgr and bz_bgd (Physics.state6's two new values),
     and each replay below ends with the model's nboost on the guest, checked
     by name.  Wave 6's boost replays are kept (re-proved on 6b's model: the
     second press 2 steps before the contact arms the flight), `gripchain`
     re-keyed; each on both cards, FOUND and PROVED on the model:
       armearly   the second press 14 steps before the first contact: a boost
                  (wave 6's window, closing on the contact, refused it)
       armroll    rubber at the cap with a chord, a Hop, the second press
                  mid-flight: a boost
       armlate    the press 2 steps AFTER the first contact (a bounce): the
                  grace converts at k = 2 (the `boostg` event), a boost
       armlate5   the press BGRACE + 1 steps after: nothing, nboost 0
                  (armlate4 until round 3's BGRACE 4)
       hoponly    one tap and nothing else: no boost
       armheld    Space held from the Hop through the contact: round 3
                  (SPEC.md 128.17.16) BOOSTS (round 2: no boost)
       ledgehold  a Hop at the half-unit lip, its first contact on the ledge
                  1 - 4 steps later, Space held through it: no boost there
                  (round 3's take-off gate)
       fallarm    round 3: rubber rolled off a rung's top, no Hop, a tap 2
                  steps after the take-off: the FALL's token, a boost
       fallnone   the same roll with no Space: no boost
       spentspring round 3b: a boost whose bounce carries the ball onto
                  PEAK's spring: the launch out of the air takes no token
                  while the boost is spent, one boost
       mashchain  rubber at the cap, Space tapped every 2 steps through three
                  contacts of the chain: one boost
       gripchain  a Hop and a mid-flight tap, the boost; Grip through its
                  landing; a Hop and a mid-flight tap, the second boost (the
                  cycle about 52 steps)
       gripsteel  steel at the cap, Grip held (Grip 3): stopped in the axis
                  model's steps (gripglass, wave 6's, at Grip 1)
     and their red arms:
  heldarm    Space HELD arms the token: ledgehold boosts on the ledge
  hopedge    the Hop's own edge arms its flight: hoponly boosts
  armwin     wave 6's test kept (the token AND the window at the contact):
             armearly does not boost
  nograce    no late grace: armlate does not boost
  grace5     a grace one step longer in the rule: armlate5 boosts
  noheld     round 3: Space held at the contact arms nothing: armheld
  nogate     round 3: held arms without the take-off gate: ledgehold
             boosts on the ledge
  nofall     round 3: a fall takes no token: fallarm does not boost
  graceoff   the conversion without its k - 1 lift: armlate's state (gz)
  The CARRIED arms (pump, tokbst, rampboost, slabcell, springtok: anchored in
  bz_land's boost block, which 6b rewrote) are re-anchored and re-proved on
  6b's model by --check.

  9  WAVE 9's FAMILIES (SPEC.md 128.25.6, 128.25.7, 128.25.15): at every frame
     also bz_fst and every family slot (Physics.statef: the per-play state
     bits and the slots' bytes), on a course that names families; and the
     replay `probe`, PLAYGROUND's demo through its PROBE element (ENTER,
     CONTACT, the lane's POSE, the CELL overlay) and a RETURN 30 steps after
     it, which the RESPAWN class clears and RESET counts.  Its red arms:
       famrsp    the RESPAWN class ignored (bz_frst not called): TOUCHED
                 stays set after the RETURN, bz_fst parts at the probe frame
     and on the unicorn only (--check): famcell, the CELL hook never called
     (its entry 0): the window holds no overlay - the glass's reader does not
     read bz_nbr, so the host half is where it goes red
     The HOST half (--check) also runs the guest's bz_step under unicorn
     against the model, every step, on PLAYGROUND's demo and the RETURN
     scenario (the ball, bz_fst, the slots, bz_fref, the window's 36 bytes
     and each element's POSE through bz_ltrue), on MOON's and PEAK's demos
     (no family: bz_fhk 0, the ball equal), and both red arms there too.
"""
import argparse
import os
import re
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
    "lip": ((9, 6), 100, 0, 120),       # 8R: row 6 - row 4 meets the clock at (11, 4) (SPEC.md 128.22.6)
    "rail": ((5, 4), -150, -250, 90),
    "goal": ((12, 6), 250, 0, 60),
}
K = BB
CHORD_X = K.K_R | K.K_D        # +wx: Right (+F, -F) and Down (+F, +F)
CHORD_MX = K.K_L | K.K_U       # -wx


def ftime(n):
    """bonanza.asm bz_t100: hundredths, truncated (a play past 65,535 steps is
    clamped to that word by bz_post)"""
    return min(n, 0xFFFF) * 2184500 // 1193182


def ftext(n):
    """the face's time (SPEC.md 128.14.17 item 2, bonanza.asm bz_ltimew):
    `s.hh` under 100 s, `s.h` from there, `20:00+` at the 65,535 clamp"""
    if n >= 0xFFFF:
        return "20:00+"
    s, c = divmod(ftime(n), 100)
    return "%d.%02d" % (s, c) if s < 100 else "%d.%d" % (s, c // 10)


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
        for n in ("bz_tout", "bz_tsec", "bz_t55", "bz_exit"):  # wave 7 (SPEC.md 128.18.4), 8b (128.19.4)
            if n in s:
                self.off[n] = s[n] - self.lo

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
        ext["s4"] = self.state4(raw) if "bz_ckpt" in self.g.sym else None
        ext["s6"] = self.state6(raw) if "bz_btok" in self.g.sym else None
        # wave 7 (SPEC.md 128.18.4): the timeout, the seconds left and the steps to the next
        ext["s7"] = ((raw[o["bz_tout"]], struct.unpack_from("<H", raw, o["bz_tsec"])[0], raw[o["bz_t55"]])
                     if "bz_tout" in o else None)
        ext["s8"] = raw[o["bz_exit"]] if "bz_exit" in o else None   # wave 8b (128.19.4): the finish's exit
        ext["sf"] = self.statef(raw) if "bz_fst" in self.g.sym else None
        return st, s2, ext

    def statef(self, raw):
        """wave 9's state (SPEC.md 128.25.6.6, 128.25.7.2): bz_fst's BZ_FSTB
        bytes and the three slots' bytes (bz_fsl), as the guest holds them"""
        s, lo = self.g.sym, self.lo
        fst = raw[s["bz_fst"] - lo:s["bz_fsl"] - lo]
        fsl = raw[s["bz_fsl"] - lo:s["bz_fsl"] - lo + guest_fsl_bytes()]
        return (bytes(fst), bytes(fsl))

    def state6(self, raw):
        """wave 6's state (SPEC.md 128.16.4.3) in Physics.state6()'s shape: the
        boost's token, the stretch's steps, the boosts, the drag's remainders;
        and wave 6b's (128.17.4.3): the late grace's steps left and its lift"""
        s, lo = self.g.sym, self.lo
        out = (raw[s["bz_btok"] - lo], raw[s["bz_stf"] - lo], struct.unpack_from("<H", raw, s["bz_nboost"] - lo)[0],
               raw[s["bz_drx"] - lo], raw[s["bz_dry"] - lo])
        if "bz_bgr" in s:
            out += (raw[s["bz_bgr"] - lo], struct.unpack_from("<h", raw, s["bz_bgd"] - lo)[0])
        if "bz_bsp" in s:                       # round 3b (SPEC.md 128.17.17): the boost spent
            out += (raw[s["bz_bsp"] - lo],)
        return out

    def state4(self, raw):
        """wave 4's state (SPEC.md 128.14.4.7) in Physics.state4()'s shape: the
        material, bz_ckpt, bz_ckmat, bz_cksn, bz_inmo, bz_hid and the five new
        counters"""
        s, lo = self.g.sym, self.lo

        def b(n):
            return raw[s[n] - lo]

        def w(n):
            return struct.unpack_from("<H", raw, s[n] - lo)[0]
        return (self.g.b("bz_mat"), b("bz_ckpt"), b("bz_ckmat"), b("bz_cksn"), b("bz_inmo"), b("bz_hid"),
                w("bz_nckpt"), w("bz_npad"), w("bz_nlip"), w("bz_nspr"), w("bz_nret"))

    def tables(self):
        """(bz_mrec, bz_fta, bz_ftg, bz_surf): the material's record and the
        arrows' force tables as the guest holds them (a pad's swap rebuilds
        them, 128.14.4.4)"""
        g = self.g
        return (bytes(g.m.read(g.a("bz_mrec"), BB.MATREC)), tuple(g.m.read(g.a("bz_fta"), BB.LVL_MAX + 1)),
                tuple(g.m.read(g.a("bz_ftg"), BB.LVL_MAX + 1)), g.b("bz_surf"))

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
                tuple([w("bz_pkick", k) for k in range(R.guest_propmax())]      # (128.19.10: the guest's
                      + [0xFFFA] * (BB.PROP_MAX - R.guest_propmax())),         # tables, the model's pad)
                w("bz_nkick"), w("bz_nknock"), w("bz_ntube"))


def counts(p):
    return {"nland": p.nland, "nfall": p.nfall, "nbnc": p.nbnc, "nstun": p.nstun, "nshat": p.nshat, "nhop": p.nhop}


def advance(p, n, keys=None, tilts=None):
    """the model to step N (Physics.step_auto for the benchmark; KEYS a list of
    key bytes indexed by the step, or one byte for every step; TILTS a tilt
    byte a step, a TILT log's, 128.14.8.3); -> the events"""
    e0 = len(p.events)
    while p.nstep < n:
        if keys is None:
            p.step_auto()
        elif isinstance(keys, int):
            p.step(keys)
        elif tilts:
            i = p.nstep
            p.step(keys[i] if i < len(keys) else 0, tilts[i] if i < len(tilts) else BB.TILT_KEYS)
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
    if ext.get("s4") is not None and ext["s4"] != p.state4():
        names = ("mat", "ckpt", "ckmat", "cksn", "inmo", "hid", "nckpt", "npad", "nlip", "nspr", "nret")
        return "%s frame %d: wave 4's state differs from the model's after %d steps: %s" % (
            name, frames, st[0], "; ".join("%s guest %s model %s" % (n, a, b)
                                           for n, a, b in zip(names, ext["s4"], p.state4()) if a != b))
    if ext.get("s7") is not None and ext["s7"] != p.state7():
        return "%s frame %d: wave 7's time differs from the model's after %d steps: %s" % (
            name, frames, st[0], "; ".join("%s guest %s model %s" % (n, a, b) for n, a, b in
                                           zip(("tout", "tsec", "t55"), ext["s7"], p.state7()) if a != b))
    if ext.get("s8") is not None and ext["s8"] != p.exit:
        return "%s frame %d: the finish's EXIT differs from the model's after %d steps: guest %d model %d " \
            "(SPEC.md 128.19.4)" % (name, frames, st[0], ext["s8"], p.exit)
    if ext.get("s6") is not None and ext["s6"] != p.state6():
        names = ("btok", "stf", "nboost", "drx", "dry", "bgr", "bgd")
        return "%s frame %d: wave 6's state differs from the model's after %d steps: %s" % (
            name, frames, st[0], "; ".join("%s guest %s model %s" % (n, a, b)
                                           for n, a, b in zip(names, ext["s6"], p.state6()) if a != b))
    if ext.get("sf") is not None and p.nstep > getattr(p, "_poked_at", -1):
        bad = statef_diff(ext["sf"], p)
        if bad:
            return "%s frame %d: wave 9's family state differs from the model's after %d steps: %s" % (
                name, frames, st[0], bad)
    want = counts(p)
    got = {k: ext[k] for k in want}
    if got != want:
        return "%s frame %d: the counters %s against the model's %s" % (name, frames, got, want)
    return None


def guest_fsl_bytes(art=None):
    """bz_fsl's bytes as the guest has them: BZ_FAMMAX slots (SPEC.md 128.25.6.9, the build's longest family
    list, never under 3 - PLAYGROUND names four since its wind yard, 128.34.12), not bbcourse.FAM_MAX's three
    (the FETCHED families' cap)"""
    t = open(os.path.join(art or R.at("build/bonanza-art"), "bzcourse.inc")).read()
    return int(re.search(r"^BZ_FAMMAX\s+equ\s+(\d+)", t, re.M).group(1)) * BB.FSLOT


def statef_diff(gf, p):
    """the guest's (bz_fst, bz_fsl) against Physics.statef(): its NFST bytes and
    its families' slots, every byte past them 0 -> a description, or None"""
    fst, fsl = p.statef()
    want = (fst + bytes(len(gf[0]) - len(fst)), b"".join(fsl) + bytes(len(gf[1]) - BB.FSLOT * len(fsl)))
    if gf == want:
        return None
    return "bz_fst %s model %s; slots %s model %s" % (gf[0].hex(), want[0].hex(), gf[1].hex(), want[1].hex())


def compare_tables(name, frames, tb, p):
    """a pad's swap (128.14.4.4): the guest's record and force tables the
    model's material's - BZ_MATTAB's record, fta from its ACC, ftg from its
    surface entry on the surface the guest holds (bz_surf)"""
    mrec, fta, ftg, surf = tb
    want_rec = BB.mattab()[BB.MATREC * p.mat:BB.MATREC * (p.mat + 1)]
    if mrec != want_rec:
        return "%s frame %d: bz_mrec is not material %d's BZ_MATTAB record" % (name, frames, p.mat)
    if fta != tuple(BB.fta_table(p.m["ACC"])):
        return "%s frame %d: bz_fta %s, material %d's %s" % (name, frames, fta, p.mat,
                                                             BB.fta_table(p.m["ACC"]))
    if surf != 0xFF and ftg != tuple(BB.ftg_table(BB.surf_entry(p.mat, surf)[0])):
        return "%s frame %d: bz_ftg %s, material %d's on surface %d %s (not rebuilt at the swap?)" % (
            name, frames, ftg, p.mat, surf, BB.ftg_table(BB.surf_entry(p.mat, surf)[0]))
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
    g.key("KeyF")
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
    if ext0.get("s7") is not None:              # (wave 7: its clock too)
        p.tout, p.tsec, p.t55 = ext0["s7"]
    if ext0.get("s8") is not None:              # (wave 8b: and the exit, 128.19.4)
        p.exit = ext0["s8"]
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
        if name == "goal" and ext["goal"] and last is not None and last[0] < st[0] and \
                [e for e in p.events if e[0] == "goal"]:
            # (a frame presented on a FINISH-SEQUENCE step, past the goal's: bz_fstep holds the clock
            # (bz_t55 BZ_SECSTEPS, 128.22.6), which the model does not run - the play has ended as far as
            # this scenario is concerned, as bz_t0 seeing bz_goal says.  A loaded machine can present one
            # such frame before bz_t0 runs; the soak of 2026-11-17 did, at step 62 of a goal at 61)
            ended = True
            break
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
            n = gs[0] if gs else 0              # the FINISHING step's time: a play's finish
            face = goal_face(g, n)              # sequence (128.22.6) runs steps on in that frame
                                                # and bz_fend takes them back off bz_nstep
            want = " %s s goal " % ftext(n)    # line 6, the held log (SPEC.md 128.14.3.2)
            if face is None or want not in face:
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
    """The face's lines as bz_line draws them after the play: -> the held
    log's (line 6: `<NAME> <time> s goal falls <n>`), or None."""
    m = g.m
    fl = R.FaceLines(g)                         # (bz_line is in the shell part, SPEC.md 128.19.2)
    fl.arm()
    found = None
    for _ in range(40):
        m.run()
        st = fl.next()
        if st is None:
            break
        # at bz_line's entry DI is the line's end (the bytes past it are the
        # last longer line's, not yet padded over), and bz_lstr opened the
        # line with a cell of margin (the padding is the erase)
        line = st[1]
        if " s goal " in line or " s cup " in line:
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


def model(crs, mat, poke, src=None, **kw):
    """the model of a replay: the course's start, poked as the guest will be -
    the window refilled round the poked cell (the guest's bz_pokd refill) and,
    on a slab, carried (bz_onp); wave 4: the ball's state (EXTRA: mst, mct) and
    a prop record's field (RECPOKE: (record, field, value) - the spring's
    launch lowered to where max and sum differ, 128.14.19 item 6) as poked"""
    p = BB.Physics(R.course(crs, src=src), play=True, mat=mat, **kw)
    if poke and poke.get("recpoke"):
        import copy
        i, fld, v = poke["recpoke"]
        p.props = copy.deepcopy(p.props)
        p.props[i][fld] = v
    if poke and poke.get("extra"):
        for k_, v in poke["extra"].items():
            setattr(p, k_, v)
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


def run_keys(crs, mat, poke, keys, tilts=None, **kw):
    p = model(crs, mat, poke, **kw)
    for i, k in enumerate(keys):
        p.step(k, tilts[i] if tilts else BB.TILT_KEYS)
        if p.goal:
            break
    return p


def parts(crs, mat, poke, keys, tilts=None, **red):
    """does the broken model PART from the model somewhere over KEYS? -> the step, or None"""
    a, b = model(crs, mat, poke), model(crs, mat, poke, **red)
    for i, k in enumerate(keys):
        t_ = tilts[i] if tilts else BB.TILT_KEYS
        a.step(k, t_)
        b.step(k, t_)
        if a.state() + a.state2() + a.state3() + a.state4() + a.state6() + a.state7() != \
                b.state() + b.state2() + b.state3() + b.state4() + b.state6() + b.state7():
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
    base = [0] * 5 + [K.K_HOP] * 2 + [0] * 60       # (glass: rubber's is a BOOST since wave 6, the
    p, ev = ev_of("trial", BB.MAT_GLASS, None, base)  # `boost` replay's; SPEC.md 128.11.7.2 as amended)
    c1 = [e[1] for e in p.events if e[0] in ("bounce", "land")]
    t = c1[0] if c1 else 30
    keys = [0] * 5 + [K.K_HOP] * 2 + [0] * (t - 9) + [K.K_HOP] * 2 + [0] * 40
    p, ev = ev_of("trial", BB.MAT_GLASS, None, keys)
    add("hopagain", "trial", BB.MAT_GLASS, None, keys, "glass: Space at the Hop's own landing (step %d) hops at "
        "the contact" % t, ev.count("hop") == 1 and "hopc" in ev and not p.nboost)
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
    return S + mill_replays() + w4_replays() + w6_replays() + w9_replays()


# ---- wave 9 (SPEC.md 128.25.6, 128.25.7, 128.25.15): the families -----------------
def play_demo_keys():
    """PLAYGROUND's shipped demo's key bytes (a keyboard log)"""
    d = BB.parse_bzd(open(os.path.join(ROOT, "apps", "bonanza", "demos", "playground.bzd")).read())
    return d["ball"], [k for k, n, _t in d["runs"] for _ in range(n)]


def probe_bit(p):
    """the PROBE element's TOUCHED bit (its FSB: GLASS's crack bytes are laid first, SPEC.md 128.25.18)"""
    b = next(pr["fsb"] for pr in p.props if pr["kind"] == BB.FAM_K0)
    return p.fst[b >> 3] >> (b & 7) & 1


def mill_demo_keys():
    """story 9.8: MILL's shipped demo (its ROUTE DEMO, the build's BZD3: the
    model's autopilot from the start) -> (material, keys)"""
    c = R.course("mill")
    _K, mat, kt, _fl = BB.decode_log_t(BB.route_demo(c, R.CRS_K["mill"]))
    assert all(tt == BB.TILT_KEYS for _k, tt in kt)
    return mat, [k for k, _tt in kt]


def probe_keys():
    """the `probe` scenario: PLAYGROUND's demo to 30 steps after the step its
    PROBE element is first ENTERED (its TOUCHED bit set), one RETURN (back to
    the start, the RESPAWN class cleared), then -wx held from the start until
    the probe is entered again, and 30 steps with no key -> (material, keys,
    the first ENTER's step)"""
    mat, keys = play_demo_keys()
    p = BB.Physics(R.course("play"), play=True, mat=mat)
    touched = lambda p: probe_bit(p)
    for i, k in enumerate(keys):
        p.step(k)
        if p.fam and touched(p):
            break
    else:
        raise AssertionError("PLAYGROUND's demo never enters its probe")
    out = keys[:i + 31] + [BB.K_RET]
    for k in out[i + 1:]:
        p.step(k)
    assert p.nret == 1 and not touched(p), "the RETURN did not clear the probe"
    for _ in range(400):
        out.append(K.K_L | K.K_U)
        p.step(K.K_L | K.K_U)
        if touched(p):
            break
    else:
        raise AssertionError("-wx from the start never enters the probe")
    return mat, out + [0] * 30, i


# GLASS (SPEC.md 128.25.8, 128.25.18): a DRIVER that writes a key log by steering the model, so the
# scenario is the model's own and the guest is held to it.  Cells are PLAYGROUND's glass section's.
KX = {(1, 0): K.K_R | K.K_D, (0, 1): K.K_L | K.K_D, (1, 1): K.K_D, (-1, -1): K.K_U, (1, -1): K.K_R,
      (-1, 1): K.K_L, (-1, 0): K.K_L | K.K_U, (0, -1): K.K_R | K.K_U, (0, 0): 0}


class _Drv:
    def __init__(self, c, mat):
        self.p = BB.Physics(c, play=True, mat=mat)
        self.keys, self.rev = [], {}

    def k(self, key, n=1):
        for _ in range(n):
            self.keys.append(key)
            self.p.step(key)
            p = self.p
            if p.fam:                           # each glass tile's first REVEALED step
                for pr in p.props:
                    if pr["kind"] == BB.FK_GLASS and pr["at"] not in self.rev and p.fpose(pr):
                        self.rev[pr["at"]] = len(self.keys)

    def pos(self):
        return self.p.gx / 4096.0, self.p.gy / 4096.0

    def go(self, tx, ty, vcap=384, n=900, until=None):
        """steer the centre to (tx, ty), cell units, at most vcap a step: each axis wants the speed it can
        still stop from (a square root of the distance), Shift held when it is far over"""
        nf0 = self.p.nfall
        for _ in range(n):
            x, y = self.pos()
            if until is not None and until():
                return
            if abs(x - tx) < 0.12 and abs(y - ty) < 0.12 and abs(self.p.gvx) < 16 and abs(self.p.gvy) < 16:
                return
            a, grip = [], False
            for d, v in ((tx - x, self.p.gvx), (ty - y, self.p.gvy)):
                want = min(vcap, 130 * abs(d) ** 0.5, 400 * abs(d))
                want = want if d > 0 else -want
                a.append(1 if v < want - 12 else (-1 if v > want + 12 else 0))
                grip = grip or abs(v) > abs(want) + 60
            self.k(KX[tuple(a)] | (K.K_GRIP if grip else 0))
            if self.p.nfall > nf0:
                return

    def line(self, dx, vcap, stopx, n=900):
        """along the row the centre is on, toward dx, until the centre passes stopx or the ball falls"""
        y, nf = int(self.pos()[1]) + 0.5, self.p.nfall
        self.go(-20 if dx < 0 else 40, y, vcap, n,
                until=lambda: self.p.nfall > nf or (self.pos()[0] <= stopx if dx < 0 else self.pos()[0] >= stopx))

    def st(self):
        p = self.p
        return {"cell": (p.gx >> 12, p.gy >> 12), "fst": bytes(p.fst), "nfall": p.nfall, "mat": p.mat,
                "n": len(self.keys)}


SEC_LIMIT_PLAY = 40 * 546 // 10                 # PLAYGROUND's `limit 40` in steps: a scenario ends inside it
GLASS_PATH = ((9, 27), (8, 27), (7, 27), (6, 27))


GLASS_LEGS = ("crack-rubber", "glass-path", "crack-steel", "crack-glass", "crack-lab", "crack-bridge")


def glass_keys(leg):
    """a `glass-*` scenario (PLAYGROUND's glass section, from the start, inside the course's limit - a play
    that times out runs the finish sequence, where a fall does not respawn) -> (material, keys,
    {what: state}, {glass cell: its first revealed step}).  crack-rubber: slowly onto the cracks (counts,
    breaks, falls; the respawn restores), then a Hop's landing on a whole one (broken at once);
    glass-path: across the cracks at speed (each broken behind it), back by the glass path (revealed tile
    by tile), into a broken crack (a fall: restored); crack-steel: the pad, slowly (falls), at speed
    (across), a Hop's landing; crack-glass: the pad, across and back (twice across, never broken), a
    landing (cracked), a second (broken: a fall)"""
    d = _Drv(R.course("play"), BB.MAT_RUBBER)
    ms = {}

    def mark(what):
        ms[what] = d.st()

    def hop(vcap, at, what):                    # (WHAT + "-land": the step of its first contact on the crack
        d.go(at + 1.6, 24.5)                    # (9, 24) - a bounce off FF first does not count)
        d.line(-1, vcap, at)
        d.k(K.K_HOP)
        for _ in range(90):
            n0 = d.p.nland
            d.k(0)
            if d.p.nland != n0 and (d.p.gx >> 12, d.p.gy >> 12) == (9, 24) and what + "-land" not in ms:
                mark(what + "-land")
        d.k(0, 20)

    def across(vcap):
        d.line(-1, vcap, 5.6)
        d.go(4.5, 24.5)

    def back():                                 # (round the far pad, by the glass path)
        d.go(5.5, 24.5)
        d.go(5.5, 27.5)
        d.line(1, 110, 10.6)
        d.go(11.5, 27.5)

    def pad(at):                                # (down FF's right side, clear of the notches)
        d.go(21.5, 24.5)
        d.go(21.5, at[1])
        d.go(*at)
        d.k(0, 2)
    if leg == "crack-rubber":
        d.go(21.5, 24.5)
        d.go(11.5, 24.5)
        d.line(-1, 70, -99)
        mark("slow")
        hop(150, 10.9, "hop")
        mark("hop")
    elif leg == "glass-path":
        d.go(20.5, 24.5)
        across(384)
        mark("fast")
        back()
        mark("path")
        d.go(11.5, 24.5)
        d.line(-1, 90, -99)
        mark("through")
    elif leg == "crack-steel":
        pad((22.5, 25.5))
        d.go(11.5, 24.5)
        d.line(-1, 80, -99)
        mark("slow")
        hop(150, 10.3, "hop")
        mark("hop")
        d.go(22.5, 24.5)
        across(384)
        mark("fast")
    elif leg == "crack-lab":                    # SPEC.md 128.25.18.1: the CRACK LAB
        d.go(31.5, 18.5)                        # (steel from the lab's pad; the floating bridge wy 16, its
        d.k(0, 2)                               # cracks 35, 37, 39 VANISH; the band holes at 43, 44 wy 19)
        d.go(33.5, 18.5)
        d.go(33.5, 16.5)
        d.line(1, 80, 99)
        mark("vslow")
        d.go(33.5, 19.5)
        d.go(42.5, 19.5)                        # (along wy 19 to the end platform, then slowly onto 43's
        nf = d.p.nfall                          # band hole: line() aims at x 40, behind it)
        d.go(90, 19.5, 80, until=lambda: d.p.nfall > nf)
        mark("wslow")
        d.go(33.5, 19.5)
        d.go(33.5, 17.5)
        d.go(26.5, 16.5)
        nf = d.p.nfall                          # (line() aims at x 40, so it would brake for the platform)
        d.go(90, 16.5, 384, until=lambda: d.p.nfall > nf or d.pos()[0] >= 40.8)
        mark("vfast")
    elif leg == "crack-bridge":                 # EXPLORATORY (SPEC.md 128.27.2.1): the THIN BRIDGE, wy 14,
        d.go(33.5, 14.5)                        # its five cracks 35 - 39 edge to edge (rubber): slowly onto
        d.line(1, 70, 99)                       # the first (a fall, restored), then at speed across all five
        mark("bslow")
        d.go(26.5, 14.5)
        nf = d.p.nfall
        brk = set()                             # (each crack's first BROKEN step: the ball runs off the
        crs = [pr for pr in d.p.props if pr["kind"] == BB.FK_CRACK and pr["at"][1] == 14]    # bridge's end

        def seen():                             # and falls, the respawn restoring all five)
            for pr in crs:
                if d.p.fst[pr["fsb"] >> 3] == BB.CR_BROKEN and pr["at"] not in brk:
                    brk.add(pr["at"])
                    ms["b%d" % pr["at"][0]] = d.st()
            return d.p.nfall > nf
        d.go(90, 14.5, 384, until=seen)
        mark("bfast")
    else:
        pad((22.5, 27.5))
        d.go(11.5, 24.5)
        mark("at")
        across(120)
        d.line(1, 120, 10.7)
        d.go(11.5, 24.5)
        mark("rolled")
        hop(110, 10.45, "hop1")
        mark("hop1")
        d.go(11.5, 24.5)
        hop(110, 10.45, "hop2")
        mark("hop2")
    d.k(0, 30)
    return BB.MAT_RUBBER, d.keys, ms, d.rev


def glass_verdict(leg, ms, rev, p):
    """-> (ok, a line): the leg's milestones as SPEC.md 128.25.8's table says"""
    k = sorted(pr["fsb"] >> 3 for pr in p.props if pr["kind"] == BB.FK_CRACK and pr["at"][1] == 24)
    lab = sorted({pr["fsb"] >> 3 for pr in p.props if pr["kind"] == BB.FK_CRACK and pr["at"][1] == 16})
    lab = lambda w, lab=lab: bytes(ms[w]["fst"][j] for j in lab)
    brg = sorted({pr["fsb"] >> 3 for pr in p.props if pr["kind"] == BB.FK_CRACK and pr["at"][1] == 14})
    brg = lambda w, brg=brg: bytes(ms[w]["fst"][j] for j in brg)
    cr = lambda w: bytes(ms[w]["fst"][j] for j in k)
    nine = next(pr["fsb"] >> 3 for pr in p.props if pr["kind"] == BB.FK_CRACK and pr["at"] == (9, 24))
    at9 = lambda w: ms[w]["fst"][nine] if w in ms else None
    lim = p.grid.limit if hasattr(p.grid, "limit") else None
    if leg == "crack-rubber":
        checks = [("slow: counted, broke, fell, restored", ms["slow"]["nfall"] == 1 and cr("slow") == bytes(4)),
                  ("a Hop's landing: broken at once, a fall", at9("hop-land") == 0xFF and ms["hop-land"]["nfall"] == 1
                   and ms["hop"]["nfall"] == 2 and cr("hop") == bytes(4))]
    elif leg == "glass-path":
        order = [rev.get(c) for c in GLASS_PATH]
        checks = [("fast: across, all four broken behind it", ms["fast"]["nfall"] == 0
                   and ms["fast"]["cell"] == (4, 24) and cr("fast") == b"\xff" * 4),
                  ("the glass path revealed tile by tile (steps %s)" % order,
                   None not in order and order == sorted(order, reverse=True) and len(set(order)) == 4
                   and ms["path"]["nfall"] == 0),
                  ("into a broken crack: a fall, every crack restored", ms["through"]["nfall"] == 1
                   and cr("through") == bytes(4))]
    elif leg == "crack-steel":
        checks = [("steel slow: fell, restored", ms["slow"]["mat"] == BB.MAT_STEEL and ms["slow"]["nfall"] == 1
                   and cr("slow") == bytes(4)),
                  ("a Hop's landing: broken at once, a fall", at9("hop-land") == 0xFF and ms["hop"]["nfall"] == 2
                   and cr("hop") == bytes(4)),
                  ("steel fast: across, all four broken", ms["fast"]["nfall"] == 2 and ms["fast"]["cell"] == (4, 24)
                   and cr("fast") == b"\xff" * 4)]
    elif leg == "crack-lab":
        checks = [("steel slow onto a vanishing crack: a fall, restored", ms["vfast"]["mat"] == BB.MAT_STEEL
                   and ms["vslow"]["nfall"] == 1 and lab("vslow") == bytes(3)),
                  ("steel slow onto a band hole: a fall, all restored", ms["wslow"]["nfall"] == 2
                   and lab("wslow") == bytes(3)),
                  ("steel fast across the floating bridge: all three vanished behind it", ms["vfast"]["nfall"] == 2
                   and ms["vfast"]["cell"][0] >= 40 and lab("vfast") == b"\xff" * 3)]
    elif leg == "crack-bridge":
        checks = [("rubber slow onto the bridge's first crack: a fall, restored", ms["bslow"]["nfall"] == 1
                   and brg("bslow") == bytes(5)),
                  ("rubber fast across the bridge: all five vanished behind it, one by one (steps %s), then off its "
                   "end: a fall, all restored" % [ms["b%d" % x]["n"] if "b%d" % x in ms else None for x in range(35, 40)],
                   all("b%d" % x in ms and ms["b%d" % x]["nfall"] == 1 for x in range(35, 40))
                   and [ms["b%d" % x]["n"] for x in range(35, 40)] == sorted(ms["b%d" % x]["n"] for x in range(35, 40))
                   and ms["bfast"]["nfall"] == 2 and brg("bfast") == bytes(5))]
    else:
        checks = [("glass across and back: never broken", ms["rolled"]["mat"] == BB.MAT_GLASS
                   and ms["rolled"]["nfall"] == ms["at"]["nfall"] and cr("rolled") == bytes(4)),
                  ("its first landing cracks it", at9("hop1") == 1 and ms["hop1"]["nfall"] == ms["at"]["nfall"]),
                  ("its second breaks it: a fall, restored", ms["hop2"]["nfall"] == ms["at"]["nfall"] + 1
                   and cr("hop2") == bytes(4))]
    bad = [w for w, ok in checks if not ok]
    return not bad, ("; ".join(w for w, _ok in checks) if not bad else "NOT: " + "; ".join(bad))


GROUP_CRACKS = ((3, 23), (4, 23), (5, 23))      # SPEC.md 128.32.8: PLAYGROUND's GROUP LAB
GROUP_GLASS = ((4, 27), (5, 27), (4, 26))


def group_keys():
    """the GROUP LAB scenario (SPEC.md 128.32.8, PLAYGROUND's far platform): across the crack path at
    speed, then the glass TURN tile by tile ((4, 27), (5, 27), (4, 26): one more revealed each time,
    the group's lanes through every combination on the way), then slowly onto the lab's last crack and
    along its row at speed (each crack counted and broken on its own, behind the ball), off it before the
    last breaks - and on until a fall restores them -> (material, keys)"""
    d = _Drv(R.course("play"), BB.MAT_RUBBER)
    d.go(20.5, 24.5)
    d.line(-1, 384, 5.6)
    d.go(3.5, 24.5)
    d.go(3.5, 27.5)
    d.go(4.5, 27.5)
    d.go(5.5, 27.5)
    d.go(4.5, 26.5)
    d.go(5.5, 24.6)
    d.go(5.5, 23.5, vcap=60)
    d.line(-1, 300, 3.5)
    d.go(3.5, 24.5)
    d.k(0, 60)
    d.go(4.5, 23.5)
    d.k(0, 80)
    return BB.MAT_RUBBER, d.keys


def group_verdict(urun_p, seen):
    """-> (ok, a line): the lab's cracks broken INDEPENDENTLY (a step with some broken and some whole),
    the glass turn revealed one at a time, and the group lanes through at least six combinations"""
    p = urun_p
    pr = dict((q["at"], q) for q in p.props if q["kind"] in (BB.FK_CRACK, BB.FK_GLASS))
    ok1 = any(0 < sum(1 for c in GROUP_CRACKS if st[0][c] == 0xFF) < 3 for st in seen)
    ok2 = any(st[1] == (1, 0, 0) for st in seen) and any(st[1] == (1, 1, 0) for st in seen) \
        and any(st[1] == (1, 1, 1) for st in seen)
    combos = len({st[2] for st in seen})
    checks = [("a lab crack broken while another stays whole", ok1),
              ("the glass turn revealed tile by tile", ok2),
              ("the group lanes' poses through %d distinct states" % combos, combos >= 6)]
    bad = [w for w, ok in checks if not ok]
    return not bad, ("; ".join(w for w, _ok in checks) if not bad else "NOT: " + "; ".join(bad))


def group_seen(p, mat, keys):
    """the model stepped through KEYS: each step's (lab cracks' bytes, glass turn's bits, group lane poses)"""
    m = BB.Physics(R.course("play"), play=True, mat=mat)
    pr = dict((q["at"], q) for q in m.props if q["kind"] in (BB.FK_CRACK, BB.FK_GLASS))
    gl = [q for q in m.props if q["kind"] == BB.PK_GROUP]
    out = []
    for k in keys:
        m.step(k)
        out.append(({c: m.fst[pr[c]["fsb"] >> 3] for c in GROUP_CRACKS},
                    tuple(m.fpose(pr[c]) for c in GROUP_GLASS), tuple(m.fpose(q) for q in gl)))
    return m, out


def w9_replays():
    S = []
    for leg in GLASS_LEGS:                      # GLASS (SPEC.md 128.25.8): its section, each rule
        mat, keys, ms, rev = glass_keys(leg)
        p = run_keys("play", mat, None, keys)
        ok, what = glass_verdict(leg, ms, rev, p)
        S.append({"name": "glass-" + leg.split("-")[1] if leg != "glass-path" else leg, "crs": "play",
                  "mat": mat, "poke": None, "keys": keys, "red": None,
                  "what": "PLAYGROUND's GLASS section, %s: %s" % (leg, what),
                  "ok": ok and len(keys) < SEC_LIMIT_PLAY})
    mat, keys, ent = probe_keys()
    p = run_keys("play", mat, None, keys)
    sl = p.fsl[0] if p.fam else bytes(8)
    S.append({"name": "probe", "crs": "play", "mat": mat, "poke": None, "keys": keys, "red": None,
              "what": "PLAYGROUND's PROBE: entered at step %d, a RETURN 30 steps later clears its RESPAWN bit, "
                      "-wx from the start enters it again (RESETs %d, ENTERs %d, CONTACTs %d, STEPs %d)" % (
                          ent + 1, sl[0], sl[1], sl[2] | sl[3] << 8, sl[4] | sl[5] << 8),
              "ok": bool(p.fam) and p.nret == 1 and sl[0] == 2 and sl[1] == 2 and probe_bit(p) and not p.nfall})
    keys, marks = pickup_keys()
    p = run_keys("play", BB.MAT_RUBBER, None, keys)
    S.append({"name": "pickups", "crs": "play", "mat": BB.MAT_RUBBER, "poke": None, "keys": keys, "red": None,
              "what": "PLAYGROUND's PICKUPS (SPEC.md 128.25.19): %s" % ", ".join("%s at %d" % (n, i) for n, i in marks),
              "ok": pickup_ok(p, marks)})
    return S


# ---- wave 9: PICKUPS (SPEC.md 128.25.9, 128.25.19) - the scripted scenario ---------------
def _pu_dirs():
    out = []
    for k in (K.K_R, K.K_L, K.K_D, K.K_U, K.K_R | K.K_D, K.K_R | K.K_U, K.K_L | K.K_D, K.K_L | K.K_U):
        fx = (1 if k & K.K_R else 0) - (1 if k & K.K_L else 0) + (1 if k & K.K_D else 0) - (1 if k & K.K_U else 0)
        fy = -(1 if k & K.K_R else 0) + (1 if k & K.K_L else 0) + (1 if k & K.K_D else 0) - (1 if k & K.K_U else 0)
        out.append((k, fx, fy))
    return out


def _pu_steer(p, tx, ty, vmax):
    """the arrows that push the ball's velocity toward one heading for (tx, ty) (24.8 gu), at most VMAX"""
    vdx = max(-vmax, min(vmax, (tx - p.gx) // 24))
    vdy = max(-vmax, min(vmax, (ty - p.gy) // 24))
    ex, ey = vdx - p.gvx, vdy - p.gvy
    if abs(ex) + abs(ey) < 40:
        return 0
    best, bk = 0, 0
    for k, fx, fy in _pu_dirs():
        sc = (ex * fx + ey * fy) / (abs(fx) + abs(fy)) ** 0.5
        if sc > best:
            best, bk = sc, k
    return bk


def _pu_goto(p, keys, wx, wy, vmax=300, until=None, n=600):
    tx, ty = (16 * wx + 8) << 8, (16 * wy + 8) << 8
    for _ in range(n):
        if (until(p) if until is not None else
                abs(p.gx - tx) < 512 and abs(p.gy - ty) < 512 and abs(p.gvx) < 60 and abs(p.gvy) < 60):
            return
        k = _pu_steer(p, tx, ty, vmax)
        keys.append(k)
        p.step(k)
    raise AssertionError("the pickups scenario never reached (%d, %d)%s" % (wx, wy, "" if until is None else
                                                                         " with its condition"))


def _pu_slot(p):
    """PICKUPS' slot index in the course's family list (PLAYGROUND: probe, glass, pickups)"""
    return next(i for i, (fm, _v) in enumerate(p.fam) if fm.row["name"] == "pickups")


def _pu_t(p):
    sl = p.fsl[_pu_slot(p)]
    return sl[0] | sl[1] << 8, sl[2] | sl[3] << 8


def pickup_keys():
    """THE PICKUPS SCENARIO on PLAYGROUND's yard (SPEC.md 128.25.19), steered on the model from the start:
    the SPEED taken, a sprint past BZ_VMAXG under it (the raised cap), the JUMP, a Hop with rubber's boost
    STACKED on its contact onto the 2-unit RIDGE, off it and both worn off, the HOURGLASS (+10 s), a RETURN
    (the ATTEMPT hourglass stays taken, the RESPAWN two come back), back into the hourglass's cell (not taken
    again: once an attempt), the speed again and the jump while it
    runs (both at once), a RETURN while both run, the jump a third time, worn off.  -> (keys, [(mark, step)])"""
    c = R.course("play")
    p = BB.Physics(c, play=True, mat=BB.MAT_RUBBER)
    keys, marks = [], []
    # (the yard left of the mat, SPEC.md 128.25.19: in by the row above the mat, wy 14; the sprint east
    # along it over the apron; back by the yard's column 6, clear of the mat)
    for wp in ((21, 14), (8, 14)):
        _pu_goto(p, keys, *wp)
    _pu_goto(p, keys, 5, 14, until=lambda q: _pu_t(q)[0])
    marks.append(("speed", len(keys)))
    vmax0 = abs(p.gvx)
    _pu_goto(p, keys, 19, 14, vmax=BB.VMAXG + BB.PU_SVUP, until=lambda q: abs(q.gvx) > BB.VMAXG)
    marks.append(("past the cap (%d)" % abs(p.gvx), len(keys)))
    _pu_goto(p, keys, 6, 14, vmax=BB.VMAXG)
    _pu_goto(p, keys, 6, 17, vmax=BB.VMAXG, until=lambda q: _pu_t(q)[1])
    marks.append(("jump", len(keys)))
    _pu_goto(p, keys, 4, 17, vmax=200)
    hopped = armed = None
    for i in range(300):
        k = _pu_steer(p, (16 * 4 + 8) << 8, (16 * 9) << 8, BB.VMAXG)
        if hopped is None and (p.gy >> 8) <= 16 * 17 and not p.air:
            k |= K.K_HOP
            hopped = i
        elif hopped is not None and armed is None and i >= hopped + 4 and p.air:
            k |= K.K_HOP
            armed = i
        keys.append(k)
        p.step(k)
        if not p.air and (p.gy >> 12) <= 12 and (p.gz >> 8) >= 48:
            break
    else:
        raise AssertionError("the jump and the boost never landed on the ridge")
    marks.append(("on the ridge (boost %d)" % p.nboost, len(keys)))
    _pu_goto(p, keys, 4, 10, vmax=120)
    _pu_goto(p, keys, 4, 15, vmax=200, until=lambda q: q.gy >> 12 >= 14 and not q.air)
    _pu_goto(p, keys, 4, 15, vmax=200, until=lambda q: _pu_t(q) == (0, 0))
    marks.append(("both worn off", len(keys)))
    hg = next(pr for pr in p.props if pr["kind"] == BB.K_HOURGLASS)
    _pu_goto(p, keys, *hg["at"], until=lambda q: q.fst[hg["fsb"] >> 3] >> (hg["fsb"] & 7) & 1)
    marks.append(("hourglass", len(keys)))
    keys.append(BB.K_RET)
    p.step(BB.K_RET)
    marks.append(("RETURN", len(keys)))
    tsec = p.tsec                                   # (pickups-v: the hourglass ONCE AN ATTEMPT, on the guest -
    _pu_goto(p, keys, *hg["at"])                    # back into its cell after the RETURN, held there: no take)
    if p.tsec > tsec or p.nfev != 3:
        raise AssertionError("the hourglass was taken again after the RETURN (tsec %d -> %d, nfev %d)" % (tsec, p.tsec, p.nfev))
    marks.append(("hourglass again, kept", len(keys)))
    _pu_goto(p, keys, 5, 14, until=lambda q: _pu_t(q)[0])
    marks.append(("speed again", len(keys)))
    _pu_goto(p, keys, 6, 17, until=lambda q: _pu_t(q)[1])
    if not _pu_t(p)[0]:
        raise AssertionError("the speed ran out before the jump was taken: not both at once")
    marks.append(("jump with the speed (%d steps of it left)" % _pu_t(p)[0], len(keys)))
    for _ in range(20):
        keys.append(0)
        p.step(0)
    keys.append(BB.K_RET)
    p.step(BB.K_RET)
    marks.append(("RETURN while both run", len(keys)))
    _pu_goto(p, keys, 6, 17, until=lambda q: _pu_t(q)[1])
    marks.append(("jump again", len(keys)))
    for _ in range(4 * 41 + 20):
        keys.append(0)
        p.step(0)
    marks.append(("worn off", len(keys)))
    assert vmax0 >= 0
    return keys, marks


RIDGE = (4, 16, 48)                             # PLAYGROUND's yard cell, the RIDGE's floor (px: z 6)


def ridge_apex(hop=None):
    """the RIDGE reachable ONLY with the jump (SPEC.md 128.25.19): on the model, every ball held on the yard
    pumping Hop and boost (the key held, or tapped every 1 - 9 steps in the air) -> the highest apex in
    px over (material, pattern); HOP: the Hop forced (the jump's PU_JHOP: the control, which must clear it)"""
    c = R.course("play")
    best = (0, None)
    for mat in (BB.MAT_RUBBER, BB.MAT_STEEL, BB.MAT_GLASS):
        for tap in (0, 1, 3, 5, 9):
            p = BB.Physics(c, play=True, mat=mat).poke(RIDGE[0], RIDGE[1], 0, 0)
            for i in range(600):
                if hop is not None:
                    p.hop = hop
                p.step(BB.K_HOP if not p.air or not tap or i % tap == 0 else 0)
                if p.nfall:
                    break
                best = max(best, (p.gz >> 8, (BB.MAT_NAMES[mat], tap)))
    return best


def pickup_ok(p, marks):
    """what the scenario is for, at its end: every pickup taken (the hourglass kept through two RETURNs,
    the timed two cleared by the last and the jump taken again), no effect left, two RETURNs, no fall"""
    hg = next(pr for pr in p.props if pr["kind"] == BB.K_HOURGLASS)
    jp = next(pr for pr in p.props if pr["kind"] == BB.K_JUMP)
    sp = next(pr for pr in p.props if pr["kind"] == BB.K_SPEED)

    def bit(pr):
        return p.fst[pr["fsb"] >> 3] >> (pr["fsb"] & 7) & 1
    return (len(marks) == 13 and p.nret == 2 and not p.nfall and bit(hg) and bit(jp) and not bit(sp)
            and _pu_t(p) == (0, 0) and p.hop == BB.MATERIALS[BB.MAT_RUBBER]["HOP"] and not p.wacc and not p.vup
            and p.nfev == 6 and p.nboost >= 1)


# WIND (SPEC.md 128.34): the knob build's test course, compiled here from its source WITHOUT its cracks (the
# default build ships no course that names the family, so the scenes ride the WIND course under the default
# build's image and parts, whose bz_fst is the shipped courses' largest: five cracks and four blower bytes
# would not fit it; the cracks are GLASS's, which its own scenes prove)
WIND_SRC = os.path.join(ROOT, "apps", "bonanza", "courses", "wind.bbc")
_WIND_SCENE = []


def wind_scene_src():
    """the WIND course less its cracks and GLASS, in a file of its own (made once a process)"""
    if not _WIND_SCENE:
        txt = open(WIND_SRC).read()
        txt = "\n".join(ln for ln in txt.split("\n") if not ln.startswith("prop crack"))
        assert "uses glass wind" in txt
        txt = txt.replace("uses glass wind", "uses wind")
        fd, path = tempfile.mkstemp(suffix=".bbc", prefix="bzwind-")
        with os.fdopen(fd, "w") as f:
            f.write(txt)
        _WIND_SCENE.append(path)
    return _WIND_SCENE[0]


def _wd_el(p, at):
    return next(q for q in p.props if q["kind"] == BB.WD_K and q["at"] == at)


def _wd_blowing(p, at):
    return BB.wind_blowing(_wd_el(p, at), p.nstep & 0xFFFF)


def _wd_at(wx, wy):
    """a goto's end: the ball's centre in cell (WX, WY), grounded, at under 100 on each axis (steel's slow
    brake never settles _pu_goto's own 60)"""
    return lambda q: (q.gx >> 12, q.gy >> 12) == (wx, wy) and not q.air and abs(q.gvx) < 100 and abs(q.gvy) < 100


def _wd_cross(p, keys, wy, stop, lean=False, n=260):
    """from (9, WY), R + D held (straight down +x) - LEAN: R alone (+x and -y, into the wind) from wx 11 -
    until the ball is past wx STOP or has fallen -> 'crossed' or 'blown off'"""
    f0 = p.nfall
    for _ in range(n):
        k = K.K_R if lean and p.gx >> 12 >= 11 else K.K_R | K.K_D
        keys.append(k)
        p.step(k)
        if p.nfall > f0:
            return "blown off"
        if p.gx >> 12 >= stop and not p.air:
            return "crossed"
    raise AssertionError("the wind scene at wy %d neither crossed nor fell" % wy)


def wind_keys(leg, mat):
    """THE WIND SCENES (SPEC.md 128.34.8, 128.34.11), steered on the model from WIND's start with ball MAT:
      path     onto the THIN PATH from (9, 12) and across under its steady +y wind (strength 10), leaning
               into it (R alone, from the wind's first cell): steel crosses, rubber and glass are blown off
               (a fall, the respawn) - rubber's best counter-push on one axis (8) is under its 10; the path's
               FAN spins while the ball is in its wind and WD_SPIN steps after (its counter, its frames)
      gust     (rubber and glass) to the BRIDGE's end (9, 9); waited for a GUST to begin and across in it
               (strength 8, gust 64 of 256): blown off; back, waited for the gust to END and across between
               gusts: crossed - the WISP's squiggles turning with the gust, the bridge's fan spinning
      updraft  onto the hop UPDRAFT's fan (5, 7), a Hop, and up-left (R + U, -y) for the LEDGE: glass rises
               onto it; rubber and steel never rise past their own Hop
      lift     PIT WIND: onto the GRATING's wind (22, 11), a `lift` updraft (strength 16) over the pit, and held
               there: glass is LAUNCHED with no Hop and, once high, R then R + U onto the PLATFORM; rubber
               (16 under gravity's 24) and steel stay on the ground, then roll on into the pit: they fall
    -> (keys, [(mark, step)])"""
    c = R.course("windscene", wind_scene_src())
    p = BB.Physics(c, play=True, mat=mat)
    keys, marks = [], []
    if leg == "path":
        _pu_goto(p, keys, 9, 12, vmax=200, n=1500)
        fan = _wd_el(p, (12, 12))
        res = _wd_cross(p, keys, 12, 17, lean=True)
        marks.append((res, len(keys)))
        if res == "crossed":                    # (on, off the ramp that would roll it back into the wind)
            _pu_goto(p, keys, 19, 12, vmax=200, n=1500, until=lambda q: (q.gx >> 12, q.gy >> 12) == (19, 12))
        if p.fst[fan["fsb"] >> 3]:
            marks.append(("the fan spinning", len(keys)))
        for _ in range(BB.WD_SPIN + 8):         # (on, until it stops)
            keys.append(0)
            p.step(0)
        marks.append(("the fan %s" % ("stopped" if not p.fst[fan["fsb"] >> 3] else "still spinning"), len(keys)))
    elif leg == "gust":
        _pu_goto(p, keys, 9, 10, vmax=200, n=1500, until=_wd_at(9, 10))
        _pu_goto(p, keys, 9, 9, vmax=120, n=1500, until=_wd_at(9, 9))
        while _wd_blowing(p, (9, 8)) or not BB.wind_blowing(_wd_el(p, (9, 8)), (p.nstep + 1) & 0xFFFF):
            keys.append(0)                      # (to the gust's first step)
            p.step(0)
        marks.append(("gust on, " + _wd_cross(p, keys, 9, 17), len(keys)))
        if marks[-1][0].endswith("blown off"):
            _pu_goto(p, keys, 9, 10, vmax=200, n=1500, until=_wd_at(9, 10))
            _pu_goto(p, keys, 9, 9, vmax=120, n=1500, until=_wd_at(9, 9))
            while not _wd_blowing(p, (9, 8)):
                keys.append(0)
                p.step(0)
            while _wd_blowing(p, (9, 8)):                           # (to the gust's END)
                keys.append(0)
                p.step(0)
            marks.append(("gust off, " + _wd_cross(p, keys, 9, 17), len(keys)))
    elif leg == "updraft":
        _pu_goto(p, keys, 5, 8, vmax=200, n=1500, until=_wd_at(5, 8))
        _pu_goto(p, keys, 5, 7, vmax=100, n=1500, until=_wd_at(5, 7))
        top, res = 0, "no ledge"
        for i in range(300):
            k = K.K_HOP if i < 2 else (K.K_L | K.K_D) if p.gy < 0x4C00 and (p.air or abs(p.gvy) > 40) \
                else (K.K_R | K.K_U) if (p.gz >> 8) >= 40 or i > 150 else 0     # (over the ledge: braked)
            keys.append(k)
            p.step(k)
            top = max(top, p.gz >> 8)
            if not p.air and (p.gy >> 12) <= 4 and (p.gz >> 8) >= 36:
                res = "the ledge"
                break
            if p.nfall:
                break
        marks.append(("%s, apex %d px" % (res, top), len(keys)))
    else:
        for wp in ((8, 7), (9, 6), (16, 6), (17, 7), (18, 12)):    # (by the walkway: the thin path's wind would blow it off)
            _pu_goto(p, keys, *wp, vmax=250, n=1500, until=lambda q, wp=wp: (q.gx >> 12, q.gy >> 12) == wp)
        _pu_goto(p, keys, 18, 12, vmax=150, n=1500, until=_wd_at(18, 12))     # (clear of both finishes)
        _pu_goto(p, keys, 21, 11, vmax=200, n=1500, until=_wd_at(21, 11))
        _pu_goto(p, keys, 22, 11, vmax=100, n=1500, until=lambda q: (q.gx >> 12, q.gy >> 12) == (22, 11))
        top, res, f0 = 0, "?", p.nfall
        for i in range(400):
            fly = (K.K_R if p.gx < 0x17800 else K.K_R | K.K_U) if p.gy >= 0x8800 else K.K_L | K.K_D   # (R, R + U;
            if i < 120:                                             # over the platform braked)
                k = fly if (p.gz >> 8) >= 44 else 0
            else:
                k = fly if p.air else K.K_R | K.K_D
            keys.append(k)
            p.step(k)
            top = max(top, p.gz >> 8)
            if not p.air and (p.gy >> 12) <= 8 and (p.gx >> 12) >= 23 and (p.gz >> 8) >= 36:
                res = "the platform"
                break
            if p.nfall > f0:
                res = "not lifted, fell in the pit"
                break
        marks.append(("%s, apex %d px" % (res, top), len(keys)))
    for _ in range(12):                         # (a few steps on: a respawn's)
        keys.append(0)
        p.step(0)
    return keys, marks


WIND_WANT = {("path", BB.MAT_STEEL): ("crossed", "the fan spinning", "the fan stopped"),
             ("path", BB.MAT_RUBBER): ("blown off", "the fan spinning", "the fan stopped"),
             ("path", BB.MAT_GLASS): ("blown off", "the fan spinning", "the fan stopped"),
             ("gust", BB.MAT_RUBBER): ("gust on, blown off", "gust off, crossed"),
             ("gust", BB.MAT_GLASS): ("gust on, blown off", "gust off, crossed"),
             ("updraft", BB.MAT_GLASS): ("the ledge",),
             ("updraft", BB.MAT_RUBBER): ("no ledge",), ("updraft", BB.MAT_STEEL): ("no ledge",),
             ("lift", BB.MAT_GLASS): ("the platform",),
             ("lift", BB.MAT_RUBBER): ("not lifted, fell in the pit",),
             ("lift", BB.MAT_STEEL): ("not lifted, fell in the pit",)}


def wind_ok(leg, mat, marks):
    """what the scene is for: each mark's verdict the one the weighting says"""
    return tuple(m.split(", apex")[0] for m, _n in marks) == WIND_WANT[(leg, mat)]


# the unicorn half (--check): bz_step itself, on the host, against the model -------
UCS, UPS, UFS, USS, USTUB = 0x1000, 0x3000, 0x6000, 0x8000, 0xFFF0
UMS = 0x9000                    # a TWO-PART course's PICTURE part (SPEC.md 128.30.5: [bz_mseg]; UPS its world part)


_LST_SYMS = {}


def lst_syms(lst, names):
    """labels out of a listing (the parts standard's op_*, which R.symbols does not read); read once a
    process for each listing's CONTENT and NAMES (fam_host builds a guest per scenario, 59 of them)"""
    import hashlib
    import io
    with open(lst, "rb") as f:
        data = f.read()
    key = (hashlib.sha256(data).digest(), tuple(names))
    if key not in _LST_SYMS:
        _LST_SYMS[key] = _lst_syms(io.TextIOWrapper(io.BytesIO(data)), names)
    return dict(_LST_SYMS[key])


def _lst_syms(lines, names):
    import re
    out, pend = {}, []
    for ln in lines:
        m = re.match(r"\s*\d+\s+([0-9A-F]{8})\s+[0-9A-F\[\]\(\)]+", ln)
        lm = re.search(r"(?:^|\s)(%s):(?:\s|$)" % "|".join(names), ln.split(";", 1)[0])
        if lm:
            pend.append(lm.group(1))
        if m:
            for q in pend:
                out.setdefault(q, int(m.group(1), 16))
            pend = []
    return out


USEGT = 0xFA00                  # (op_seg's table in the image's segment: past the bss, under USTUB)


def fam_parts(over=None, nocell=()):
    """story 9.8: every family part ROW of the build, {its part row: its bytes}
    (BZ_P_FAM + bbcourse.fam_row: a `fetch` family's own part, and the RESIDENT
    BUNDLE, SPEC.md 128.25.6.9, made by bbcourse.fam_bundle as the build makes
    it), OVER replacing a family's part by name; NOCELL: the families whose
    CELL entry is zeroed (GLASS's and the probe's red arms)"""
    link = open(R.at("build/bonanza-art/bzlink.inc")).read()
    import re
    pf = int(re.search(r"^BZ_P_FAM\s+equ\s+(0x[0-9A-Fa-f]+|\d+)", link, re.M).group(1), 0)
    parts = {}
    for f in BB.FAMILIES:
        b = (over or {}).get(f["name"])
        b = bytearray(b if b is not None else open(R.at("build/bzf-%s.bin" % f["name"]), "rb").read())
        if f["name"] in nocell:
            b[12 + 2 * 5:14 + 2 * 5] = b"\0\0"
        parts[f["name"]] = bytes(b)
    out = dict((pf + BB.fam_row(f), parts[f["name"]]) for f in BB.FAM_FETCH)
    out[pf + len(BB.FAM_FETCH)] = BB.fam_bundle(parts, BB.fam_balls(R.at("build/bonanza-art")))  # (the balls
    return out                                  # at its head since SPEC.md 128.25.5.2)


class UGuest:
    """BONANZA's image under unicorn: the course part at UPS, each family part
    at UFS + 100h k, op_fetch a CF = 0 and op_seg / op_cseg answering each
    family row's segment out of a table at USEGT (story 9.8: a course names
    several), bz_toast a HLT (never reached)"""

    def __init__(self, binp, lst, sym, part, fam=None, patch=()):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_16
        self.sym = sym
        mu = self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        mu.mem_map(0, 0x100000)
        mu.mem_write(UCS * 16, open(binp, "rb").read())
        mu.mem_write(UPS * 16, bytes(part))
        mu.mem_write(UCS * 16 + USTUB, b"\xf4")
        # FAM: {row: part} (story 9.8: a course names several; op_seg / op_cseg answer AL's row out of the
        # table), [(row, part), ...] the same, or one part's bytes (every row answered with it)
        if isinstance(fam, (bytes, bytearray)):
            fam = {None: fam}
        fam = dict(fam or ())
        segt = bytearray(512)
        at_ = UFS                               # (each part at the next 100h paragraphs or more: the bundle
        for row, b in sorted(fam.items(), key=lambda rb: -1 if rb[0] is None else rb[0]):  # holds the balls,
            n_ = max(0x100, (len(b) + 15) >> 4)                                          # 128.25.5.2)
            assert at_ + n_ <= USS
            mu.mem_write(at_ * 16, bytes(b))
            if row is None:
                segt[:] = struct.pack("<H", at_) * 256
            else:
                struct.pack_into("<H", segt, 2 * row, at_)
            at_ += n_
        mu.mem_write(UCS * 16 + USEGT, bytes(segt))
        op = lst_syms(lst, ("op_fetch", "op_seg", "op_cseg", "bz_toast"))
        for n in ("op_seg", "op_cseg"):        # push bx; mov bl, al; xor bh, bh; shl bx, 1;
            if n in op:                         # mov ax, [cs:bx + USEGT]; pop bx; ret
                mu.mem_write(UCS * 16 + op[n], b"\x53\x88\xc3\x30\xff\xd1\xe3\x2e\x8b\x87"
                             + struct.pack("<H", USEGT) + b"\x5b\xc3")
        if "op_fetch" in op:
            mu.mem_write(UCS * 16 + op["op_fetch"], b"\xf8\xc3")
        # OSAPI_SEG (bz_fbfind's SEG_SUBC into the RESIDENT BUNDLE, SPEC.md 128.25.6.9): a real-mode
        # kernel's answer, DX + AX - add dx, ax; clc; retf - at the slot's own far address
        api = open(os.path.join(ROOT, "apps", "os88api.inc")).read()
        import re
        ks = int(re.search(r"^KERNEL_SEG\s+equ\s+(0x[0-9A-Fa-f]+)", api, re.M).group(1), 16)
        so = int(re.search(r"^%define OSAPI_SEG\s+KERNEL_SEG:(0x[0-9A-Fa-f]+)", api, re.M).group(1), 16)
        mu.mem_write(ks * 16 + so, b"\x01\xc2\xf8\xcb")
        mu.mem_write(UCS * 16 + op["bz_toast"], b"\xf4")
        for n, b in patch:
            mu.mem_write(UCS * 16 + (n if isinstance(n, int) else sym[n]), b)

    def w(self, n, v, sz, k=0):
        self.mu.mem_write(UCS * 16 + self.sym[n] + k, (v & ((1 << (8 * sz)) - 1)).to_bytes(sz, "little"))

    def r(self, n, sz, signed=True, k=0):
        return int.from_bytes(self.mu.mem_read(UCS * 16 + self.sym[n] + k, sz), "little", signed=signed)

    def rb(self, n, sz):
        return bytes(self.mu.mem_read(UCS * 16 + self.sym[n], sz))

    def call(self, n, ax=0, bx=0):
        from unicorn.x86_const import UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, \
            UC_X86_REG_SP, UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_IP, UC_X86_REG_FLAGS
        mu = self.mu
        for reg, v in ((UC_X86_REG_CS, UCS), (UC_X86_REG_DS, UCS), (UC_X86_REG_ES, UCS), (UC_X86_REG_SS, USS)):
            mu.reg_write(reg, v)
        mu.mem_write(USS * 16 + 0xFFEE, struct.pack("<H", USTUB))
        mu.reg_write(UC_X86_REG_SP, 0xFFEE)
        mu.reg_write(UC_X86_REG_AX, ax)
        mu.reg_write(UC_X86_REG_BX, bx)
        mu.emu_start(UCS * 16 + self.sym[n], UCS * 16 + USTUB, count=5000000)
        assert mu.reg_read(UC_X86_REG_IP) + 16 * mu.reg_read(UC_X86_REG_CS) == UCS * 16 + USTUB, \
            "%s did not return" % n
        return mu.reg_read(UC_X86_REG_AX), mu.reg_read(UC_X86_REG_FLAGS) & 1


def _cellb(c):
    z0, sx, sy, kd, fl, sf = c
    return bytes((z0 & 255, (sx & 15) | (sy & 15) << 4, kd | sf << 4, fl & 255))


def urun(binp, lst, sym, crs, mat, keys, fam=None, patch=(), poke=None, src=None, k=None):
    """KEYS played on course CRS through bz_crshdr, bz_ffetch, bz_pinit and
    bz_step under unicorn, the model stepped beside it and compared after
    every step: the ball (Physics.state), and on a course with families
    bz_fst, the slots, bz_fref, the window bz_nbr against the model's
    snapshot and each element's POSE through bz_ltrue.  SRC: a course file
    the build does not ship (a knob build's: MAGNETS', SPEC.md 128.33.10;
    WIND's, 128.34.8), compiled here and played as course K (default
    PLAYGROUND's K), its time limit the model's.  -> (model, failures)"""
    c = R.course(crs, src=src)
    g = UGuest(binp, lst, sym, c.wcga if c.split else c.cga, fam, patch)
    g.w("bz_cseg", UPS, 2)
    if c.split:                                 # (a TWO-PART course, SPEC.md 128.30.5: the world part in
        g.mu.mem_write(UMS * 16, bytes(c.cga))  # [bz_cseg], the picture part in [bz_mseg]; one part is in
    if "bz_mseg" in sym:                        # both words, as bz_cload leaves them)
        g.w("bz_mseg", UMS if c.split else UPS, 2)
    g.w("bz_crs", k if k is not None else R.CRS_K["play" if src else crs], 1)
    g.w("bz_mat", mat, 1)
    g.w("bz_mode", 0, 1)
    g.call("bz_crshdr")
    _ax, cf = g.call("bz_ffetch")
    assert not cf, "bz_ffetch refused the family part"
    g.call("bz_pinit")
    p = BB.Physics(c, play=True, mat=mat) if poke is None else model(crs, mat, poke, src=src)
    if src:                                     # (the borrowed K's limit replaced by the course's own)
        g.w("bz_tsec", p.tsec, 2)
        g.w("bz_t55", p.t55, 1)
    if poke:                                    # story 9.8: a scenario's POKE, as replay() makes it
        for n in ("gx", "gy", "gz"):
            g.w("bz_" + n, poke[n], 4)
        for n in ("gvx", "gvy", "gvz", "ztop"):
            g.w("bz_" + n, poke[n], 2)
        g.w("bz_air", poke["air"], 1)
        for i_, v in enumerate(poke["lvl"]):
            g.w("bz_lvl", v, 1, i_)
        g.w("bz_onp", poke.get("onp", 0), 1)
        g.w("bz_ps", (g.r("bz_ps", 1, False) & ~4) | (4 if poke.get("onp") else 0), 1)
        for k_, v in (poke.get("extra") or {}).items():
            g.w("bz_" + k_, v, 1)
        if poke.get("recpoke"):
            i_, fld, v = poke["recpoke"]
            g.mu.mem_write(UPS * 16 + g.r("bz_poff", 2, False) + BB.PROPREC * i_ + {"gvz": 16}[fld],
                           struct.pack("<H", v))
        g.w("bz_pokd", 1, 1)
    bad = []
    if (g.r("bz_fhk", 1, False), g.r("bz_fnf", 1, False)) != (p.fhk, len(p.fam)):
        bad.append("bz_fhk %02Xh bz_fnf %d, the model's %02Xh, %d" % (g.r("bz_fhk", 1, False), g.r("bz_fnf", 1, False),
                                                                     p.fhk, len(p.fam)))
    elem = [pr for pr in p.props if BB.is_fam(pr["kind"])]
    lanes = [pr for pr in elem if pr.get("lane")]
    lanes += [pr for pr in p.props if pr["kind"] == BB.PK_GROUP]     # SPEC.md 128.32: the GROUP lanes too
    if lanes:                                   # (bz_pread's count, which a RESET's marks walk: the lane
        g.w("bz_nlane", sum(1 for pr in p.props if pr.get("lane")), 1)  # records are the first)
    alll = [pr["i"] for pr in p.props if pr.get("lane")]    # SPEC.md 128.19.10 item 10: EVERY lane's KICK and
    for i, k in enumerate(keys):                            # HOLD too (bz_pkick, bz_lhold: a post's)
        g.w("bz_keys", k, 1)
        g.w("bz_tilt", BB.TILT_KEYS, 1)
        if lanes:                               # (the display's: every element lane unmarked, the walk
            pose0 = [p.fpose(pr) for pr in lanes]   # QUIET, as after a walk that skipped every lane)
        if alll:
            for j in alll:
                g.w("bz_latt", 0, 1, j)
            g.w("bz_lqt", 1, 1)
            kh0 = [(g.r("bz_pkick", 2, False, 2 * j), g.r("bz_lhold", 1, False, j)) for j in alll]
        g.call("bz_step")
        p.step(k)
        if lanes:                               # SPEC.md 128.25.6.3: a step that moves an element's
            for pr, q0 in zip(lanes, pose0):    # pose MARKS its lane and makes the next walk (bz_lqt 0,
                q1 = p.fpose(pr)                # bz_nset's rule: the quiet walk reads no mark)
                if q1 != q0 and (not g.r("bz_latt", 1, False, pr["i"]) or g.r("bz_lqt", 1, False)):
                    bad.append("step %d: element %d's pose %d -> %d, but bz_latt %d, bz_lqt %d (never drawn)" % (
                        i, pr["i"], q0, q1, g.r("bz_latt", 1, False, pr["i"]), g.r("bz_lqt", 1, False)))
        if alll:                                # 128.19.10 item 10: the quiet walk compares no lane's
            for j, (kk0, hh0) in zip(alll, kh0):    # state, so a step that writes a lane's KICK or HOLD
                kk1, hh1 = g.r("bz_pkick", 2, False, 2 * j), g.r("bz_lhold", 1, False, j)   # marks it AND makes
                if (kk1, hh1) != (kk0, hh0) and (not g.r("bz_latt", 1, False, j) or g.r("bz_lqt", 1, False)):
                    bad.append("step %d: lane %d's kick %d -> %d, hold %d -> %d, but bz_latt %d, bz_lqt %d (never "
                               "drawn)" % (i, j, kk0, kk1, hh0, hh1, g.r("bz_latt", 1, False, j),
                                           g.r("bz_lqt", 1, False)))
        gs = (g.r("bz_nstep", 4), g.r("bz_gx", 4), g.r("bz_gy", 4), g.r("bz_gz", 4), g.r("bz_gvx", 2),
              g.r("bz_gvy", 2), g.r("bz_gvz", 2), g.r("bz_air", 1))
        if gs != p.state():
            bad.append("step %d: the ball %s, the model's %s" % (i, gs, p.state()))
        if p.fam:
            d = statef_diff((g.rb("bz_fst", g.sym["bz_fsl"] - g.sym["bz_fst"]), g.rb("bz_fsl", guest_fsl_bytes())), p)
            if d:
                bad.append("step %d: %s" % (i, d))
            if g.r("bz_fref", 1, False) != p.fref:
                bad.append("step %d: bz_fref %d, the model's %d" % (i, g.r("bz_fref", 1, False), p.fref))
            nw = g.rb("bz_nwin", 2)
            if (nw[0], nw[1]) == p.wcell:
                gw = bytearray(g.rb("bz_nbr", 36))
                mw = bytearray(b"".join(_cellb(p.cell(nw[0] + dx, nw[1] + dy)) for dy in (-1, 0, 1)
                                        for dx in (-1, 0, 1)))
                for q in range(9):              # (a SPLIT cell, 128.24: the window holds the grid's
                    if mw[4 * q + 2] & 15 >= BB.KIND_TB:    # pair bytes, the model's cell() reads
                        gw[4 * q:4 * q + 2] = mw[4 * q:4 * q + 2]   # (0, 0) - its records are bz_nbh's)
                if gw != mw:
                    bad.append("step %d: the window %s, the model's %s" % (i, gw.hex(), mw.hex()))
            if any(fm.row["name"] == "water" for fm, _v in p.fam):       # SPEC.md 128.36: WATER's working values
                gv = (g.r("bz_mrec", 2, False, 10), g.r("bz_surf", 1, False),
                      g.r("bz_se", 1, False, 3) if p.surf != 0xFF else None)
                mv = (p.hthr, p.surf, (p.wef if p.wef is not None else BB.surf_entry(p.mat, p.surf)[3])
                      if p.surf != 0xFF else None)
                if gv != mv:
                    bad.append("step %d: water's working values (HTHR, bz_surf, the floor's e) %s, the model's %s"
                               % (i, gv, mv))
            if any(fm.row["name"] == "spike" for fm, _v in p.fam):       # SPIKES (SPEC.md 128.38): bz_mrec's
                gv = (g.r("bz_mrec", 1, False, 8), g.r("bz_mrec", 1, False, 9), g.r("bz_mrec", 2, False, 10),
                      g.r("bz_mst", 1, False), g.r("bz_mct", 1, False))      # HARD, HSTEPS, HTHR; the state
                mv = (p.hard, p.hsteps, p.hthr, p.mst, p.mct)
                if gv != mv:
                    bad.append("step %d: spikes' working values (HARD, HSTEPS, HTHR, bz_mst, bz_mct) %s, the model's %s"
                               % (i, gv, mv))
            if any(fm.row["name"] == "pickups" for fm, _v in p.fam):     # wave 9: the WORKING values
                gv = (g.r("bz_wacc", 1, False), g.r("bz_vup", 2), g.r("bz_mrec", 2, False, 6), g.r("bz_cue", 1, False), g.r("bz_nfev", 2, False), g.rb("bz_fta", 9),
                      g.r("bz_tsec", 2, False))
                mv = (p.wacc, p.vup, p.hop, p.cue, p.nfev, bytes(p.fta), p.tsec)
                if gv != mv:
                    bad.append("step %d: the working values (wacc, vup, Hop, cue, nfev, fta, tsec) %s, the "
                               "model's %s" % (i, gv, mv))
            for pr in elem + [pr for pr in lanes if pr["kind"] == BB.PK_GROUP]:
                if not pr.get("lane"):          # (a group MEMBER has no lane: its group lanes are checked)
                    continue
                g.w("bz_lknd", pr["kind"], 1, pr["i"])
                ax, _cf = g.call("bz_ltrue", bx=pr["i"])
                if ax & 255 != p.fpose(pr):
                    bad.append("step %d: %s %d's POSE %d, the model's %d" % (
                        i, "group lane" if pr["kind"] == BB.PK_GROUP else "element", pr["i"], ax & 255, p.fpose(pr)))
        if len(bad) > 3:
            break
    return p, bad


def fam_host():
    """--check's unicorn half (SPEC.md 128.25.13 bonanzaphys) -> failure lines"""
    sym = R.symbols()
    binp, lst = R.at("build/bonanza.bin"), R.at("build/bonanza.lst")
    fam = fam_parts()
    out, fails = [], []
    mat, keys = play_demo_keys()
    p, bad = urun(binp, lst, sym, "play", mat, keys, fam)
    out.append("PLAYGROUND's demo, %d steps with its probe: %s (slot %s, bz_fst %s)" % (
        len(keys), "; ".join(bad) or "the guest is the model at every step", bytes(p.fsl[0]).hex(), bytes(p.fst).hex()))
    fails += bad
    pm, k2, ent = probe_keys()                  # (pm: the probe scenario's material, the red arms' too)
    p, bad = urun(binp, lst, sym, "play", pm, k2, fam)
    out.append("the probe scenario (entered at %d, a RETURN at %d): %s (slot %s)" % (
        ent + 1, ent + 31, "; ".join(bad) or "equal at every step", bytes(p.fsl[0]).hex()))
    fails += bad
    for crs, f in (("mill", None), ("moon", "moon.bzd"), ("peak", "summit.bzd")):
        if f:
            d = BB.parse_bzd(open(os.path.join(ROOT, "apps", "bonanza", "demos", f)).read())
            mat, kk = d["ball"], [k for k, n, _t in d["runs"] for _ in range(n)]
        else:                                   # (MILL's: its route demo, the build's BZD3)
            mat, kk = mill_demo_keys()
        p, bad = urun(binp, lst, sym, crs, mat, kk, fam)
        names = [BB.FAM_BY_ID[fid]["name"] for fid, _v in p.grid.fams]
        out.append("%s's demo, %d steps, families %s (%d tube rides, %d knocks, %d springs): %s" % (
            crs.upper(), len(kk), "+".join(names) or "none", p.ntube, p.nknock, p.nspr, "; ".join(bad) or "equal"))
        fails += bad
    # GLASS (SPEC.md 128.25.8, 128.25.18): its scenarios, every step
    gl = {}
    for leg in GLASS_LEGS:
        gm, gk, gms, grev = gl[leg] = glass_keys(leg)
        p, bad = urun(binp, lst, sym, "play", gm, gk, fam)
        gok, gwhat = glass_verdict(leg, gms, grev, p)
        out.append("the %s scenario, %d steps (%d respawns): %s; %s" % (
            leg, len(gk), p.nfall, "; ".join(bad) or "the guest is the model at every step", gwhat))
        fails += bad + ([] if gok else ["the %s scenario: %s" % (leg, gwhat)])
    gm, gk = gl["crack-rubber"][0], gl["crack-rubber"][1]
    # GROUP LANES (SPEC.md 128.32): the lab's cracks and glass turn, every step, every group lane's pose; and
    # red grpcomb, bz_ltrue's GROUP case summing the classes without their MULT
    grm, grk = group_keys()
    _m, seen = group_seen(None, grm, grk)
    p, bad = urun(binp, lst, sym, "play", grm, grk, fam)
    gok, gwhat = group_verdict(_m, seen)
    out.append("the GROUP LAB scenario, %d steps (%d respawns, %d group lanes): %s; %s" % (
        len(grk), p.nfall, sum(1 for q in p.props if q["kind"] == BB.PK_GROUP),
        "; ".join(bad) or "the guest is the model at every step", gwhat))
    fails += bad + ([] if gok else ["the GROUP LAB scenario: %s" % gwhat])
    mulat = open(binp, "rb").read().find(b"\x26\xf6\x64\x13", sym["bz_ltrue"])
    assert 0 < mulat - sym["bz_ltrue"] < 400, "red grpcomb: bz_ltrue's MULT not found"
    _p, bad = urun(binp, lst, sym, "play", grm, grk, fam, ((mulat, b"\x90" * 4),))
    ok = any("group lane" in b and "POSE" in b for b in bad)
    out.append("red grpcomb: %s" % ("red at %s" % bad[0] if ok else "STAYED GREEN"))
    if not ok:
        fails.append("red grpcomb stayed green on the unicorn: %s" % bad[:1])
    # story 9.8 (SPEC.md 128.25.20): every MILL, MOON and PEAK scenario of the replays (the windmills'
    # knocks and doorways, the tubes' KEEP, DROP and LAUNCH - the cannon - the bumpers, the springs), the
    # guest's bz_step under unicorn with the three families' parts against the model at every step
    nsc, nst = 0, 0
    for s in replays():
        if s["crs"] not in ("mill", "moon", "peak") or s.get("tilts"):
            continue
        p, bad = urun(binp, lst, sym, s["crs"], s["mat"], s["keys"], fam, poke=s["poke"])
        nsc, nst = nsc + 1, nst + len(s["keys"])
        if bad:
            fails += ["scenario %s: %s" % (s["name"], b) for b in bad]
            out.append("scenario %s (%s): %s" % (s["name"], s["crs"], "; ".join(bad)[:300]))
    out.append("%d MILL / MOON / PEAK scenarios, %d steps, with the ROTOR, SPRING and TUBE parts: %s" % (
        nsc, nst, "equal at every step" if not [f for f in fails if f.startswith("scenario")] else "FAILED"))
    # red kickquiet (SPEC.md 128.19.10 item 10): the KICK's write of bz_pkick without its bz_lqt clear - the
    # post marked but the walk left quiet, so a lit post is never drawn (MILL's `kick` scenario must go red
    # with "never drawn"; the 39 above are its control)
    lq = sym["bz_lqt"]
    img = open(binp, "rb").read()
    kq = img.find(bytes((0xC6, 0x06, lq & 255, lq >> 8, 0)), sym["bz_circle"])
    assert 0 < kq - sym["bz_circle"] < 400 and img.find(bytes((0xC6, 0x06, lq & 255, lq >> 8, 0)), kq + 1,
                                                         sym["bz_circle"] + 400) < 0, "red kickquiet: the clear not found"
    s = [s_ for s_ in replays() if s_["name"] == "kick"][0]
    _p, bad = urun(binp, lst, sym, s["crs"], s["mat"], s["keys"], fam, ((kq, b"\x90" * 5),), poke=s["poke"])
    ok = any("never drawn" in b and "kick" in b for b in bad)
    out.append("red kickquiet: %s" % ("red at %s" % bad[0] if ok else "STAYED GREEN"))
    if not ok:
        fails.append("red kickquiet stayed green on the unicorn: %s" % bad[:1])
    # ...and story 9.8's red arms ON THE PARTS (each a REDS arm whose code moved into a family part):
    # the arm's part assembled from a patched copy against this build's bzlink.inc, its scenario on the
    # unicorn, which must part from the model
    import shutil
    import subprocess
    import tempfile
    sc = dict((s["name"], s) for s in replays())
    for arm in ("gate", "exit", "springsum"):
        (f, a_, b_), = REDS[arm]
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "bonanza")
            shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
            R.patch_tree(src, REDS[arm])
            name = os.path.splitext(os.path.basename(f))[0]
            name = {"bztube": "tube"}.get(name, name)
            o = os.path.join(td, "part.bin")
            subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", src + "/",
                            "-I", R.at("build/bonanza-art") + "/", "-o", o, os.path.join(src, "fam", name + ".asm")],
                           cwd=ROOT, check=True)
            ff = fam_parts({name: open(o, "rb").read()})
            hit = None
            for sn in [n for n in sc if any(n == o or n.startswith(o + "-") for o in RED_ONLY[arm])]:
                s = sc[sn]
                _p, bad = urun(binp, lst, sym, s["crs"], s["mat"], s["keys"], ff, poke=s["poke"])
                hit = hit or (bad and "%s: %s" % (sn, bad[0]))
            out.append("red %s (the %s part): %s" % (arm, name, "red at %s" % hit[:160] if hit else "STAYED GREEN"))
            if not hit:
                fails.append("red %s stayed green on the unicorn (the %s part)" % (arm, name))
    # the red arms, on the unicorn: each must part from the model
    for name, ff, patch, want, kk, gmat in (
            ("famcell", fam_parts(nocell=("probe",)), (), "the window", k2, pm),
            ("famrsp", fam, (("bz_frst", b"\xc3"),), "bz_fst", k2, pm),
            # GLASS's: the CELL hook skipped (a broken crack is never VOID in the window: the ball rolls on
            # over it), the RESPAWN class ignored (the cracks stay broken after a respawn)
            ("glscell", fam_parts(nocell=("glass",)), (), "the ball", gk, gm),
            ("glsrsp", fam, (("bz_frst", b"\xc3"),), "bz_fst", gk, gm)):
        p, bad = urun(binp, lst, sym, "play", gmat, kk, ff, patch)
        ok = any(want in b for b in bad)
        out.append("red %s: %s" % (name, "red at %s" % bad[0] if ok else "STAYED GREEN"))
        if not ok:
            fails.append("red %s stayed green on the unicorn: %s" % (name, bad[:1]))
    # GLASS's DRAW arms (the owner, 2026-11-16: steel fell through a crack and the hole was never drawn -
    # the hooks marked the lane but left a QUIET walk quiet, so with the camera still nothing walked it;
    # SPEC.md 128.25.6.3: a hook marks through bz_fmark, which wakes the walk too).  crack-steel (the
    # count's break, a landing's, the respawn) must go red with: glsquiet, the part's marks as they were
    # (bz_latt written, the walk left quiet); glsmark, the count's break leaving its lane unmarked;
    # fmkquiet, the engine's bz_fmark marking without waking the walk
    import re
    sk, sm = gl["crack-steel"][1], gl["crack-steel"][0]
    gsrc = open(os.path.join(ROOT, "apps", "bonanza", "fam", "glass.asm")).read()
    old = re.sub(r"(?m)^    call far \[bz_fmkp\][^\n]*\n", "    mov byte [bz_latt + bx], 1\n", gsrc)
    one = gsrc.replace("    call gl_mark                ; its lane marked, the next walk made\n", "")
    la = sym["bz_latt"]
    for arm, txt, patch in (("glsquiet", old, ()), ("glsmark", one, ()),
                            ("fmkquiet", None, (("bz_fmark", bytes((0xC6, 0x87, la & 255, la >> 8, 1, 0xCB))),))):
        assert txt != gsrc, "red %s: its patch did not apply" % arm
        ff = fam
        if txt is not None:
            with tempfile.TemporaryDirectory() as td:
                src = os.path.join(td, "bonanza")
                shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
                open(os.path.join(src, "fam", "glass.asm"), "w").write(txt)
                o = os.path.join(td, "part.bin")
                subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I",
                                src + "/", "-I", R.at("build/bonanza-art") + "/", "-o", o,
                                os.path.join(src, "fam", "glass.asm")], cwd=ROOT, check=True)
                ff = fam_parts({"glass": open(o, "rb").read()})
        _p, bad = urun(binp, lst, sym, "play", sm, sk, ff, patch)
        ok = any("never drawn" in b for b in bad)
        out.append("red %s: %s" % (arm, "red at %s" % bad[0] if ok else "STAYED GREEN"))
        if not ok:
            fails.append("red %s stayed green on the unicorn: %s" % (arm, bad[:1]))
    # EXPLORATORY (SPEC.md 128.25.18.1): red glspart - gl_mark marks the crack's lane and not its
    # COMPANION's, so a vanishing crack's lower lane is never drawn (crack-lab must go red: "never drawn")
    txt = gsrc.replace("    xor bh, bh\n    call far [bz_fmkp]\n.o:", "    xor bh, bh\n.o:")
    assert txt != gsrc, "red glspart: its patch did not apply"
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "bonanza")
        shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
        open(os.path.join(src, "fam", "glass.asm"), "w").write(txt)
        o = os.path.join(td, "part.bin")
        subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I",
                        src + "/", "-I", R.at("build/bonanza-art") + "/", "-o", o,
                        os.path.join(src, "fam", "glass.asm")], cwd=ROOT, check=True)
        ff = fam_parts({"glass": open(o, "rb").read()})
    _p, bad = urun(binp, lst, sym, "play", gl["crack-lab"][0], gl["crack-lab"][1], ff, ())
    ok = any("never drawn" in b for b in bad)
    out.append("red glspart: %s" % ("red at %s" % bad[0] if ok else "STAYED GREEN"))
    if not ok:
        fails.append("red glspart stayed green on the unicorn: %s" % bad[:1])
    # the RESIDENT BUNDLE (SPEC.md 128.25.6.9): the demos above found rotor, spring and tube by walking its
    # headers (bz_fbfind); red `bunwalk` - the first header's +11 one paragraph long - and PEAK, which names
    # all three, is refused by bz_ffetch (the next header is not where the step lands)
    if BB.FAM_RES:
        ff = dict(fam)
        row = max(ff)
        b = bytearray(ff[row])
        b[sum(BB.BA.B2_SIZE) + BB.FAM_HDR_PARAS] += 1   # (the first FAMILY header: past the balls, 128.25.5.2)
        ff[row] = bytes(b)
        cf = []
        for parts in (fam, ff):                 # (the control first: the same leg, the build's bundle)
            g = UGuest(binp, lst, sym, R.course("peak").cga, parts)
            g.w("bz_cseg", UPS, 2)
            if "bz_mseg" in sym:                # (one part: in both words, SPEC.md 128.30.5)
                g.w("bz_mseg", UPS, 2)
            g.w("bz_crs", R.CRS_K["peak"], 1)
            g.w("bz_fs", 1, 1)                  # (OP_SAYGATE: the refusal quiet, as inside a bracket)
            g.call("bz_crshdr")
            cf.append(g.call("bz_ffetch")[1])
        red = cf == [0, 1]
        out.append("red bunwalk: %s" % ("red: bz_ffetch refused PEAK (its control fetched all three)" if red
                                        else "STAYED GREEN (CF %s)" % cf))
        if not red:
            fails.append("red bunwalk stayed green: a bundle header's step one paragraph off went unnoticed")
    # wave 9 (SPEC.md 128.25.19): THE PICKUPS SCENARIO, and its red arms - the STEP entry 0 (no timer
    # runs down: the slot parts at the first step after the speed's take), the RESET entry 0 (the RETURN
    # while the speed runs leaves it running: the slot), and the cap without bz_vup (bz_gax.clamp's
    # `add dx, [bz_vup]` made NOPs: the ball parts in the sprint past BZ_VMAXG)
    ap, apw = ridge_apex()
    aj, ajw = ridge_apex(BB.PU_JHOP)
    rok = ap < RIDGE[2] - BB.CLIMB <= aj
    out.append("the RIDGE (z 6, %d px less CLIMB %d): every ball's best apex on the yard with no jump %d px %s; "
               "with the jump's Hop %d px %s" % (RIDGE[2], BB.CLIMB, ap, apw, aj, ajw))
    if not rok:
        fails.append("the ridge is not the jump's alone (apex %d with no jump, %d with it)" % (ap, aj))
    pk, marks = pickup_keys()
    p, bad = urun(binp, lst, sym, "play", BB.MAT_RUBBER, pk, fam)
    out.append("the pickups scenario, %d steps (%s): %s (slot %s, bz_fst %s)" % (
        len(pk), ", ".join("%s %d" % m_ for m_ in marks), "; ".join(bad) or "equal at every step",
        bytes(p.fsl[_pu_slot(p)]).hex(), bytes(p.fst).hex()))
    fails += bad
    if not pickup_ok(p, marks):
        fails.append("the pickups scenario does not show what it is for (marks %s)" % marks)
    img = open(binp, "rb").read()
    vup = img.find(b"\xba" + struct.pack("<H", BB.VMAXG) + b"\x03\x16" + struct.pack("<H", sym["bz_vup"]),
                   sym["bz_gax"])
    # (pickups-v: `puretake` - CONTACT's COLLECTED test gone, `jnz .out` after the first `test [si], al`
    # made NOPs: an element is taken again while its cell is held, the hourglass on its revisit after the
    # RETURN among them - the working values part)
    pick = open(R.at("build/bzf-pickups.bin"), "rb").read()
    retake = bytearray(pick)
    rt = retake.find(b"\x84\x04\x75")
    retake[rt + 2:rt + 4] = b"\x90\x90"
    for name, ff, patch, want in (("pustep", fam_parts({"pickups": _noentry(pick, BB.H_STEP)}), (), "slots"),
                                  ("puretake", fam_parts({"pickups": bytes(retake)}), (), "the working values"),
                                  ("purst", fam_parts({"pickups": _noentry(pick, BB.H_RESET)}), (), "slots"),
                                  ("puvup", fam, ((vup + 3, b"\x90" * 4),), "the ball")):
        p, bad = urun(binp, lst, sym, "play", BB.MAT_RUBBER, pk, ff, patch)
        ok = any(want in b for b in bad)
        out.append("red %s: %s" % (name, "red at %s" % bad[0][:160] if ok else "STAYED GREEN"))
        if not ok:
            fails.append("red %s stayed green on the unicorn: %s" % (name, bad[:1]))
    # MAGNETS (SPEC.md 128.33.10): the test course's scenes and their red arms
    o_, f_ = mg_host(binp, lst, sym)
    o2, f2 = wind_host(binp, lst, sym, fam)
    wo, wf = water_host(binp, lst, sym, fam)       # WATER (SPEC.md 128.36)
    ao, af = arch_host(binp, lst, sym, fam)         # THE ARCHWAY (SPEC.md 128.39)
    so, sf = spike_host(binp, lst, sym)            # SPIKES (SPEC.md 128.38)
    bo, bf = bp_host(binp, lst, sym)               # BOOST PADS (SPEC.md 128.40)
    return out + o_ + o2 + wo + ao + so + bo, fails + f_ + f2 + wf + af + sf + bf


# ---- MAGNETS (SPEC.md 128.33): the test course's scenes, poked - each POKE a tile, a ground velocity, the steps,
# a RETURN at a step (None none), and what it is for, judged on the model's own trace -----------------------
MG_SRC = os.path.join(ROOT, "apps", "bonanza", "courses", "magnets.bbc")
MG_SCENES = (
    # name          material         poke (wx, wy, gvx, gvy)  steps  RETURN  what
    ("hover-steel", BB.MAT_STEEL,  (15, 22, 300, 0),   120, None, "steel rolls off the gap's edge and HOVERS under the "
                                                                  "hanging magnets to the goal's plate"),
    ("hover-rubber", BB.MAT_RUBBER, (15, 22, 300, 0),  120, None, "rubber falls into the same gap"),
    ("pull-steel", BB.MAT_STEEL,   (11, 12, 0, 160),   140, None, "slow steel is pulled off the walkway by the "
                                                                  "magnet across the gap"),
    ("pull-fast", BB.MAT_STEEL,    (11, 12, 0, 384),   60, None, "fast steel rolls past it"),
    ("pull-rubber", BB.MAT_RUBBER, (11, 12, 0, 160),   140, None, "rubber rolls on past it"),
    ("rail-steel", BB.MAT_STEEL,   (20, 10, 0, 200),   170, 150, "steel rides the tilted rail held by its fence of "
                                                                 "magnets (a RETURN while one wiggles)"),
    ("rail-rubber", BB.MAT_RUBBER, (20, 10, 0, 200),   170, None, "rubber slides off the tilted rail"),
)


def mg_poke(mat, at):
    wx, wy, gvx, gvy = at
    return poke_of(BB.Physics(R.course("mags", src=MG_SRC), play=True, mat=mat).poke(wx, wy, gvx, gvy))


def mg_keys(n, ret):
    return [BB.K_RET if i == ret else 0 for i in range(n)]


def mg_verdict(name, mat, poke, keys):
    """what a magnet scene is for, on the model's trace -> (ok, what it saw)"""
    p = model("mags", mat, poke, src=MG_SRC)
    xs, zs, fell, pulled, wig = [], [], None, 0, 0
    for i, k in enumerate(keys):
        g0 = (p.gvx, p.gvy)
        p.step(k)
        if p.respawned and fell is None and not k:
            fell = i
        if fell is None:
            xs.append((p.gx >> 12, p.gy >> 12, p.air))
            zs.append((p.gz >> 8, p.gx >> 12) if p.air else None)
        wig += p.fsl[0][7] != 0
    if name == "hover-steel":
        over = [z for z, x in filter(None, zs) if 18 <= x <= 20]
        ok = fell is None and xs[-1][0] >= 21 and len(over) > 20 and min(over) >= 15
        return ok, "%d steps over the gap, z %s - %s px, ended on (%d, %d)%s" % (
            len(over), min(over or [0]), max(over or [0]), xs[-1][0], xs[-1][1], "" if fell is None else
            ", FELL at %d" % fell)
    if name in ("hover-rubber", "pull-steel", "rail-rubber"):
        return fell is not None, "fell at step %s (%d steps a magnet wiggled)" % (fell, wig)
    if name in ("pull-rubber", "pull-fast"):            # (the field's row is 14: rubber stops IN it, unpulled)
        return fell is None and xs[-1][1] >= 14 + (name == "pull-fast"), "ended on (%d, %d), no fall" % xs[-1][:2]
    if name == "rail-steel":
        ok = fell is None and max(y for _x, y, _a in xs) >= 15 and wig > 100
        return ok, "no fall, reached row %d; a magnet wiggled %d steps" % (max(y for _x, y, _a in xs), wig)
    raise AssertionError(name)


def mg_parts(over=None, src=None):
    """the build's family rows with the MAGNET part replaced by OVER (bytes), or assembled from SRC (text)"""
    if src is not None:
        import shutil
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, "bonanza")
            shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), d)
            open(os.path.join(d, "fam", "magnet.asm"), "w").write(src)
            o = os.path.join(td, "part.bin")
            subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", d + "/",
                            "-I", R.at("build/bonanza-art") + "/", "-o", o, os.path.join(d, "fam", "magnet.asm")],
                           cwd=ROOT, check=True)
            over = open(o, "rb").read()
    return fam_parts({"magnet": over}) if over is not None else fam_parts()


def mg_host(binp, lst, sym):
    """MAGNETS' unicorn half (SPEC.md 128.33.10): every scene equal at every step, what each is for, and the red
    arms -> (lines, failures)"""
    out, fails = [], []
    fam = fam_parts()
    sc = []
    for name, mat, at, n, ret, what in MG_SCENES:
        poke, keys = mg_poke(mat, at), mg_keys(n, ret)
        sc.append((name, mat, poke, keys))
        p, bad = urun(binp, lst, sym, "mags", mat, keys, fam, poke=poke, src=MG_SRC, k=0)
        ok, saw = mg_verdict(name, mat, poke, keys)
        out.append("magnet %s (%s): %s; %s" % (name, what, "; ".join(bad)[:200] or "equal at every step", saw))
        fails += ["magnet %s: %s" % (name, b) for b in bad] + ([] if ok else ["magnet %s is not what it is "
                                                                             "for: %s" % (name, saw)])
    msrc = open(os.path.join(ROOT, "apps", "bonanza", "fam", "magnet.asm")).read()
    # the red arms, each assembled from a broken copy of the part's source: the STEP entry 0 (no magnet acts),
    # the material's test inverted (rubber pulled, steel not), the hover's damping gone, the scan's ACROSS test
    # gone (a field a whole band of rows), the wiggle's pose change left unmarked (never drawn)
    arms = (("mgstep", "    dw 0, 0, 0, mg_step, mg_pose, 0\n", "    dw 0, 0, 0, 0, mg_pose, 0\n", None,
             ("hover-steel",)),
            ("mgsteel", "    jne .stop\n", "    je .stop\n", None, ("pull-rubber", "rail-rubber")),
            ("mgdamp", "    sar dx, 1\n    sar dx, 1\n    sar dx, 1\n", "    xor dx, dx\n", "the ball",
             ("hover-steel",)),
            ("mgscan", "    or ah, ah\n    jnz .n\n", "    or ah, ah\n", None, ("pull-fast", "hover-steel")),
            ("mgmark", "    call far [bz_fmkp]          ; (bz_fmark: the walk made; BX the element)\n", "",
             "never drawn", ("rail-steel",)),
            # (the hover's BOBBLE gone; a cell change's step counting the wiggle on - two pose changes a step)
            ("mgbob", "    add ax, BZ_MG_BOB\n", "    nop\n", "the ball", ("hover-steel",)),
            ("mgfresh", "    call mg_one                 ; (a cell change's step: the force, no count -\n"
             "    jmp short .out              ; it may have STOPPED a wiggle: one change a step)\n", "", None,
             ("hover-steel", "rail-steel")))
    for arm, a_, b_, want, scs in arms:
        assert msrc.count(a_) == 1, "red %s: its patch does not apply" % arm
        ff = mg_parts(src=msrc.replace(a_, b_))
        hit = None
        for name, mat, poke, keys in sc:
            if name in scs and hit is None:
                _p, bad = urun(binp, lst, sym, "mags", mat, keys, ff, poke=poke, src=MG_SRC, k=0)
                hit = next((b for b in bad if want is None or want in b), None)
        out.append("red %s: %s" % (arm, "red at %s" % hit[:160] if hit else "STAYED GREEN"))
        if not hit:
            fails.append("red %s stayed green on the unicorn" % arm)
    return out, fails


# ---- BOOST PADS (SPEC.md 128.40.8): the BZBOOST=1 knob's test course BOOS, compiled from its source and played on
# the default build's image and parts (the family's part is in every build's resident bundle) -------------------
BP_SRC = os.path.join(ROOT, "apps", "bonanza", "courses", "boost.bbc")


def _bp_ramp(p):
    return BB.K_L | BB.K_U if p.gx >> 12 > 10 else BB.K_GRIP     # (-x: up the ramp; on the ledge, the brake)


def _bp_gap(p):
    if p.gx >> 12 >= 14:
        return BB.K_GRIP                                    # (over the low plate: the brake)
    return BB.K_R | BB.K_D if (p.gy >> 12) >= 17 or p.gx >> 12 > 10 else BB.K_D | BB.K_L


def _bp_chain(p):
    return BB.K_GRIP if p.gy >> 12 >= 12 else 0             # (nothing held until the goal plate: the brake)


BP_SCENES = (
    # name    poke (wx, wy, gvx, gvy)  keys      steps  what (judged on the model: the pad's scene against the
    #                                                   same course LESS the scene's pads, bp_verdict)
    ("ramp", (14, 6, 0, 0), _bp_ramp, 120, "from the pocket's one tile of run-up, the -x pad (strength 40) drives the "
     "ball up the ramp to the ledge; rubber and steel cannot climb it without the pad, glass can"),
    ("gap", (10, 16, 0, 200), _bp_gap, 120, "into the pocket and +x: its two pads throw the ball over the 2-cell gap "
     "onto the low plate (they are `flat`: every ball pushed the same); without them every ball falls short"),
    ("chain", (12, 10, 120, 0), _bp_chain, 200, "no key held: five +x pads and two +y pads carry the ball down the "
     "runway and round onto the goal plate; without them it stops on the runway"),
    ("hop", (12, 10, 300, 0), lambda p: BB.K_HOP if p.nstep < 2 else 0, 60, "a Hop over the pads: no push while "
     "airborne (bpair's scene)"),
)
BP_PADS = {"ramp": {(14, 6)}, "gap": {(10, 17), (11, 17)}, "chain": {(13, 10), (14, 10), (15, 10), (16, 10), (17, 10), (19, 10),
                                                           (19, 11)}}


def bp_course(drop=()):
    """BOOS (DROP: less the pads at those cells, a scene's control) - a Course, compiled from the tree"""
    if not drop:
        return R.course("boos", src=BP_SRC)
    txt = open(BP_SRC).read().split("\n")
    txt = [ln for ln in txt if not (ln.split()[:2] == ["prop", "boost"] and (int(ln.split()[2]), int(ln.split()[3]))
                                    in drop)]
    return BB.compile_course("\n".join(txt), fname=BP_SRC + " (less its pads)")


def bp_play(c, mat, at, keyf, n):
    """the scene's model run -> (its keys, the Physics, the step it respawned or None, steps lit, poses seen)"""
    p = BB.Physics(c, play=True, mat=mat).poke(*at)
    keys, fell, lit, poses = [], None, 0, set()
    p.landed = None                         # (the first step it meets the gap's low plate, x 14 on)
    pads = [pr for pr in p.props if pr["kind"] == BB.BP_K]
    for i in range(n):
        k = keyf(p)
        keys.append(k)
        p.step(k)
        poses |= {p.fpose(pr) for pr in pads}
        lit += p.fsl[0][0] != 0
        if p.respawned and fell is None:
            fell = i
        if fell is None and p.landed is None and p.gx >> 12 >= 14 and (not p.air or p.events[-1][1] == p.nstep
                                                                        and p.events[-1][0] in ("land", "bounce")):
            p.landed = i                    # (its first contact there: a landing, or rubber's bounce)
    return keys, p, fell, lit, poses


def bp_verdict(name, mat):
    """what a boost scene is for, on the model: with its pads and without -> (ok, what it saw)"""
    at, keyf, n = next((a, k, n_) for nm, a, k, n_, _w in BP_SCENES if nm == name)
    _k, p1, f1, lit, poses = bp_play(bp_course(), mat, at, keyf, n)
    if name == "hop":
        return poses == {0, 1} and f1 is None, "lit %d steps, poses %s" % (lit, sorted(poses))
    _k, p0, f0, _l, _q = bp_play(bp_course(BP_PADS[name]), mat, at, keyf, n)
    cell = lambda q: (q.gx >> 12, q.gy >> 12, q.gz >> 8)
    if name == "ramp":                      # (the ledge: x 11 or less, 4 units up)
        up1, up0 = p1.gx >> 12 <= 11 and p1.gz >> 8 == 32, p0.gx >> 12 <= 11 and p0.gz >> 8 == 32
        ok = up1 and f1 is None and up0 == (mat == BB.MAT_GLASS)
    elif name == "gap":                     # (the low plate: x 14 on, 1.5 units up - met whole)
        ok = p1.landed is not None and (f1 is None or f1 > p1.landed) and p0.landed is None
    else:
        ok = f1 is None and p1.gy >> 12 >= 12 and f0 is None and p0.gy >> 12 < 12
    return ok and poses == {0, 1}, "with its pads ended on %s%s%s, lit %d steps; without, %s%s" % (
        cell(p1), "" if f1 is None else " (FELL at %d)" % f1, "" if name != "gap" or p1.landed is None
        else ", met the low plate at step %d" % p1.landed, lit, cell(p0), "" if f0 is None else " (fell at %d)" % f0)


def bp_parts(src):
    """the build's family rows with the BOOST part assembled from SRC (text)"""
    import shutil
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "bonanza")
        shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), d)
        open(os.path.join(d, "fam", "boost.asm"), "w").write(src)
        o = os.path.join(td, "part.bin")
        subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", d + "/",
                        "-I", R.at("build/bonanza-art") + "/", "-o", o, os.path.join(d, "fam", "boost.asm")],
                       cwd=ROOT, check=True)
        return fam_parts({"boost": open(o, "rb").read()})


def bp_host(binp, lst, sym):
    """BOOST PADS' unicorn half (SPEC.md 128.40.8): every scene for every ball equal at every step (the ball, the
    slot, every pad's POSE and its marks), what each is for asserted on the model, and the red arms, each
    assembled from a broken copy of the part's source and each of which must part from the model:
    `bpstep` (STEP's entry 0: a flash never goes out), `bpsign` (the minus sign's `neg` gone: a -x pad pushes
    +x), `bplit` (the lighting's mark gone: a lit pad never drawn), `bpout` (the putting-out's mark gone: the
    chain's put-out pad never drawn), `bpair` (the air test gone: a Hop over the pads pushed), and round 2's
    `bpweight` (glass's x1.25 gone: glass pushed as rubber) and `bpflat` (`flat` ignored: the gap's flat pads
    weight steel)
    -> (lines, failures)"""
    out, fails = [], []
    fam = fam_parts()
    sc = {}
    for name, at, keyf, n, what in BP_SCENES:
        for mat in (BB.MAT_RUBBER, BB.MAT_STEEL, BB.MAT_GLASS):
            keys = bp_play(bp_course(), mat, at, keyf, n)[0]
            poke = poke_of(BB.Physics(bp_course(), play=True, mat=mat).poke(*at))
            sc[(name, mat)] = (poke, keys)
            _p, bad = urun(binp, lst, sym, "boos", mat, keys, fam, poke=poke, src=BP_SRC, k=0)
            ok, saw = bp_verdict(name, mat)
            out.append("boost %s, %s (%s): %s; %s" % (name, BB.MAT_NAMES[mat], what if mat == BB.MAT_RUBBER else
                                                      "as rubber's", "; ".join(bad)[:200] or "equal at every step",
                                                      saw))
            fails += ["boost %s, %s: %s" % (name, BB.MAT_NAMES[mat], b) for b in bad] + (
                [] if ok else ["boost %s, %s is not what it is for: %s" % (name, BB.MAT_NAMES[mat], saw)])
    bsrc = open(os.path.join(ROOT, "apps", "bonanza", "fam", "boost.asm")).read()
    mk = "    call far [bz_fmkp]          ; (bz_fmark: the walk made; BX the element)\n    pop bx\n"
    arms = (("bpstep", "    dw 0, 0, bp_contact, bp_step, bp_pose, 0\n", "    dw 0, 0, bp_contact, 0, bp_pose, 0\n",
             None, ("chain", BB.MAT_RUBBER)),
            ("bpsign", "    jnc .pos\n    neg ax\n", "    jnc .pos\n", "the ball", ("ramp", BB.MAT_STEEL)),
            ("bplit", "    call far [bz_fmkp]          ; this pad LIT: its lane MARKED\n", "", "never drawn",
             ("gap", BB.MAT_GLASS)),
            ("bpout", mk, "    pop bx\n", "never drawn", ("chain", BB.MAT_STEEL)),
            ("bpair", "    cmp byte [bz_air], 0\n    jne .out\n", "", "the ball", ("hop", BB.MAT_RUBBER)),
            # round 2 (SPEC.md 128.40.4): glass's x1.25 gone (glass pushed as rubber); `flat` ignored (the gap's
            # flat pads weight steel)
            ("bpweight", "    add al, ah\n", "", "the ball", ("ramp", BB.MAT_GLASS)),
            ("bpflat", "    test bl, BZ_BP_FFLAT\n    jnz .w\n", "", "the ball", ("gap", BB.MAT_STEEL)))
    for arm, a_, b_, want, (name, mat) in arms:
        assert bsrc.count(a_) == 1, "red %s: its patch does not apply" % arm
        poke, keys = sc[(name, mat)]
        _p, bad = urun(binp, lst, sym, "boos", mat, keys, bp_parts(bsrc.replace(a_, b_)), poke=poke, src=BP_SRC, k=0)
        hit = next((b for b in bad if want is None or want in b), None)
        out.append("red %s: %s" % (arm, "red at %s" % hit[:160] if hit else "STAYED GREEN"))
        if not hit:
            fails.append("red %s stayed green on the unicorn" % arm)
    return out, fails


def wind_host(binp, lst, sym, fam):
    """WIND (SPEC.md 128.34.8, 128.34.11): the scenes on the knob build's WIND course (less its cracks),
    compiled from its source, with the build's image and parts - each ball's push by its weight on the thin
    path and its fan spinning and stopping, the gust on and off on the bridge with its wisp, the hop
    updraft only glass rises on, the PIT WIND's grating launching glass alone - the guest's bz_step equal to
    the model at every step (the ball, the spin bytes, the slots, every wind lane's POSE and its marks), what
    each scene is for asserted on the model; and the red arms, each of which must part from the model:
    `wdstep` (STEP's entry 0), `wdglass` (glass's shift NOPed: glass pushed as rubber), `wdfan` (the fan's
    mark NOPed: a fan that turns never drawn), `wdgust` (the gust's marks NOPed: the wisp never drawn),
    `wdspin` (the spin byte never set: bz_fst), `wdlift` (the updraft's gvz test NOPed), `wdpit` (the
    launch NOPed: glass stays on the grating)"""
    out, fails = [], []
    src = wind_scene_src()
    c = R.course("windscene", src)
    nfst = (sum(pr["bits"] for pr in c.props if BB.is_fam(pr["kind"])) + 7) // 8
    if nfst > sym["bz_fsl"] - sym["bz_fst"]:
        return out, ["the WIND scenes' %d state bytes are over the build's bz_fst (%d): they cannot run on this "
                     "image" % (nfst, sym["bz_fsl"] - sym["bz_fst"])]
    sc = {}
    for leg, mat in sorted(WIND_WANT):
        keys, marks = sc[(leg, mat)] = wind_keys(leg, mat)
        p, bad = urun(binp, lst, sym, "windscene", mat, keys, fam, src=src)
        ok = wind_ok(leg, mat, marks)
        out.append("the wind %s scene, %s, %d steps (%s): %s%s" % (
            leg, BB.MAT_NAMES[mat], len(keys), "; ".join("%s at %d" % m_ for m_ in marks),
            "; ".join(bad) or "the guest is the model at every step", "" if ok else " - NOT WHAT IT IS FOR"))
        fails += ["the wind %s scene, %s: %s" % (leg, BB.MAT_NAMES[mat], b) for b in bad]
        if not ok:
            fails.append("the wind %s scene, %s: %s, not %s" % (leg, BB.MAT_NAMES[mat], marks, WIND_WANT[(leg, mat)]))
    part = open(R.at("build/bzf-wind.bin"), "rb").read()

    def nop(b, pat, k=0, n=None):
        """PART with the K-th occurrence of PAT made NOPs (N bytes of it: all)"""
        i = -1
        for _ in range(k + 1):
            i = b.find(pat, i + 1)
        assert i >= 0, "a red arm's pattern is not in the wind part: %s" % pat.hex()
        b = bytearray(b)
        b[i:i + (n or len(pat))] = b"\x90" * (n or len(pat))
        return bytes(b)
    lift = b"\x81\x3e" + struct.pack("<HH", sym["bz_gvz"], BB.WD_LIFT) + b"\x7d"   # cmp word [bz_gvz], LIFT; jge
    mk = b"\xff\x1e" + struct.pack("<H", sym["bz_fmkp"])                          # call far [bz_fmkp]
    launch = b"\xc6\x06" + struct.pack("<HB", sym["bz_air"], 1)                    # mov byte [bz_air], 1
    for name, ff, leg, mat, want in (
            ("wdstep", fam_parts({"wind": _noentry(part, BB.H_STEP)}), "path", BB.MAT_STEEL, "the ball"),
            ("wdglass", fam_parts({"wind": nop(part, b"\xd1\xe0")}), "path", BB.MAT_GLASS, "the ball"),
            ("wdfan", fam_parts({"wind": nop(part, mk, 0)}), "path", BB.MAT_STEEL, "never drawn"),
            ("wdgust", fam_parts({"wind": nop(part, mk, 1)}), "gust", BB.MAT_RUBBER, "never drawn"),
            ("wdspin", fam_parts({"wind": nop(part, b"\xb5" + bytes((BB.WD_SPIN,)))}), "path", BB.MAT_STEEL,
             "bz_fst"),
            ("wdlift", fam_parts({"wind": nop(part, lift, 0, len(lift) + 1)}), "updraft", BB.MAT_GLASS,
             "the ball"),
            ("wdpit", fam_parts({"wind": nop(part, launch)}), "lift", BB.MAT_GLASS, "the ball")):
        _p, bad = urun(binp, lst, sym, "windscene", mat, sc[(leg, mat)][0], ff, src=src)
        ok = any(want in b for b in bad)
        out.append("red %s: %s" % (name, "red at %s" % bad[0][:160] if ok else "STAYED GREEN"))
        if not ok:
            fails.append("red %s stayed green on the unicorn: %s" % (name, bad[:1]))
    return out, fails


# WATER (SPEC.md 128.36): its scenarios on the WATER test course (apps/bonanza/courses/water.bbc, the BZWATER=1
# knob's course), compiled here from the tree whatever the build: the family's part is in every build's
# resident bundle, and the course part is handed to the guest as any course's is (bz_crs borrowed from
# PLAYGROUND's: bz_crshdr reads the part alone)
WATER_STEPS = 160


def _water_course():
    R.COURSES["bench"]                          # (fills both tables)
    R.CRS_K["bench"]
    if "water" not in dict.keys(R.COURSES):
        dict.__setitem__(R.COURSES, "water", "apps/bonanza/courses/water.bbc")
        dict.__setitem__(R.CRS_K, "water", R.CRS_K["play"])


def water_poke(wx, wy, mat, gvx=0, gvy=0, dz=0):
    """a poke on WATER: the centre of (wx, wy) on its floor at (gvx, gvy), DZ px above it falling from rest"""
    _water_course()
    p = BB.Physics(R.course("water"), play=True, mat=mat).poke(wx, wy, gvx, gvy)
    if dz:
        p.gz += dz << 8
        p.air, p.ztop = 1, p.gz >> 8
    return poke_of(p)


def water_scenarios():
    """[(name, material, poke, keys, what it shows)]: steel off the walkway into the sketch's column - it sinks
    (no stun) and rolls out of the arch; rubber dropped 3 units onto the water - its rebound water's, lower
    than sand's; glass dropped 5 units onto the water - whole (the same drop onto the walkway shatters it);
    rubber onto the steel pad beside the column - the swap refills the window, and it sinks"""
    D, R_ = BB.K_D, BB.K_R
    return [("water-steel", BB.MAT_STEEL, water_poke(8, 7, BB.MAT_STEEL, 0, 200), [0] * 60 + [D] * 80 + [0] * 20),
            ("water-deep", BB.MAT_STEEL, water_poke(4, 7, BB.MAT_STEEL, 0, 200), [0] * 110 + [D] * 80 + [0] * 10),
            ("water-roll", BB.MAT_RUBBER, water_poke(7, 8, BB.MAT_RUBBER, 160, 0), [0] * 150),
            ("water-rubber", BB.MAT_RUBBER, water_poke(8, 8, BB.MAT_RUBBER, dz=24), [0] * 80),
            ("water-float", BB.MAT_RUBBER, water_poke(8, 8, BB.MAT_RUBBER), [0] * 110),
            ("water-glass", BB.MAT_GLASS, water_poke(8, 8, BB.MAT_GLASS, dz=40), [0] * 60),
            ("water-pad", BB.MAT_RUBBER, water_poke(7, 6, BB.MAT_RUBBER, 0, 160), [0] * 20 + [R_ | D] * 100)]


def water_verdict(name, p, ctl=None, zt=()):
    """what a water scenario is for, on the model at its end (ZT: its heights, whole px, step by step) -> (ok,
    what)"""
    ev = p.events
    kinds = [e[0] for e in ev]
    if name in ("water-steel", "water-deep"):
        t0 = next((e[1] for e in ev if e[0] == "takeoff"), None)
        land = next((e for e in ev if e[0] == "land"), None)
        x_ = 8 if name == "water-steel" else 4
        ok = t0 is not None and land is not None and "stun" not in kinds and p.nfall == 0 \
            and (p.gx >> 12, p.gy >> 12) == (x_, 9) and not p.air and p.gz == 0 \
            and (name == "water-steel" or land[1] - t0 > 60)
        return ok, "steel sank from step %s to its landing at step %s (lfall, lvz %s), no stun, out of the arch " \
            "to (%d, %d) z %d" % (t0, land and land[1], land and land[2], p.gx >> 12, p.gy >> 12, p.gz >> 8)
    lands = [e for e in ev if e[0] in ("land", "bounce")]
    loud = [e for e in lands if (e[2][1] if e[0] == "land" else e[2]) >= 48]     # (bzsound's BZS_LMIN)
    if name == "water-float":                   # SPEC.md 128.36.10: the SURFACE BOB of a ball at rest on the water -
        zs = sorted(set(zt))                    # no landing, no takeoff (no sound, no squash), its heights
        ok = not lands and "takeoff" not in kinds and zs == [20, 24]
        return ok, "rubber at rest on the water, %d steps: heights %s px, %d landing(s), %d takeoff(s)" % (
            len(zt), zs, len(lands), kinds.count("takeoff"))
    if name == "water-roll":                    # rubber across the walkway's water: never chatter
        ok = len(lands) <= 2 and p.nfall == 0 and "stun" not in kinds
        return ok, "rubber rolled across the sketch's column: %d landing(s) (%s), %d of them audible" % (
            len(lands), [e[1] for e in lands], len(loud))
    if name == "water-rubber":
        b = next((e for e in ev if e[0] == "bounce"), None)
        we, se = BB.water_entry(BB.MAT_RUBBER)[3], BB.surf_entry(BB.MAT_RUBBER, BB.SURF_SAND)[3]
        ok = b is not None and b[3] == (we * b[2]) >> 8 < (se * b[2]) >> 8 and not p.air and p.gz >> 8 in (20, 24)
        return ok, "rubber's first bounce on the water: lvz %s, rebound %s (sand's would be %s); at rest on the " \
            "float line, z %d px (the top 24)" % (b and b[2], b and b[3], b and (se * b[2]) >> 8, p.gz >> 8)
    if name == "water-glass":
        lv = max([e[2][1] for e in ev if e[0] == "land"] + [e[2] for e in ev if e[0] == "bounce"] + [0])
        ok = "shatter" not in kinds and p.nfall == 0 and (lv or 0) >= BB.MATERIALS[BB.MAT_GLASS]["HTHR"] \
            and ctl is not None and "shatter" in [e[0] for e in ctl.events]
        return ok, "glass dropped 5 units onto the water: whole (lvz %s, the threshold %d); the same drop onto " \
            "the walkway: %s" % (lv, BB.MATERIALS[BB.MAT_GLASS]["HTHR"], "shattered" if ctl and "shatter" in [
                e[0] for e in ctl.events] else "NOT shattered")
    pad = next((e[1] for e in ev if e[0] == "pad"), None)
    land = next((e for e in ev if e[0] == "land" and pad is not None and e[1] > pad), None)
    ok = pad is not None and p.mat == BB.MAT_STEEL and land is not None and "stun" not in kinds
    return ok, "the steel pad at step %s, then sank into the column (landing at step %s)" % (pad, land and land[1])


def water_reds():
    """WATER's red arms on the unicorn, each the part assembled from a patched water.asm: (name, the patch, the
    scenario, what must part).  wacell: the CELL entry 0 (steel's window keeps the water at its top); wahthr:
    HTHR never put back on the way out (the working values, once steel leaves by the arch); warefill: no
    refill on a changed material (the pad's swap leaves rubber's window: the window); wafloat: rubber's
    window at the top, not the float line; waact: the ACTIVE ripple's flip unmarked; waalw: an ALWAYS
    ripple's flip unmarked (each a pose that changed with its lane never drawn)"""
    return (("wacell", ("    dw wa_reset, 0, 0, wa_step, wa_pose, wa_cell\n", "    dw wa_reset, 0, 0, wa_step, wa_pose, 0\n"), "water-steel",
             "the window"),
            ("wahthr", ("    mov [bz_mrec + BZM_HTHR], ax\n    mov byte [bz_surf], 0FFh\n",
                        "    mov byte [bz_surf], 0FFh\n"), "water-steel", "working values"),
            ("warefill", ("    mov [di], al\n    mov byte [bz_fref], 1\n", "    mov [di], al\n"), "water-pad",
             "the window"),
            ("wafloat", ("    mov al, [es:si + WA_HTOP]   ; rubber's and glass's floor, H less BP\n    sub ax, bp ",
                         "    mov al, [es:si + WA_HTOP]   ; rubber's and glass's floor, H less BP\n    nop\n    nop "),
             "water-rubber", "the window"),
            ("wabsnap", ("    sub word [bz_gz], 4 << 8\n    sbb word [bz_gz + 2], 0\n", ""), "water-float", "the ball"),
            ("wabflip", ("    mov byte [bz_fref], 1\n    test al, 1 << BZ_WA_FBSH\n", "    test al, 1 << BZ_WA_FBSH\n"),
             "water-float", "the window"),
            ("waact", ("    test byte [es:si + WA_RIP], WR_ALWAYS\n    jnz .x\n    call far [bz_fmkp]\n.x:\n    retf\n\n"
                       "; POSE", "    test byte [es:si + WA_RIP], WR_ALWAYS\n    jnz .x\n.x:\n    retf\n\n; POSE"),
             "water-rubber", "never drawn"),
            ("waalw", ("    jz .wn\n    call far [bz_fmkp]\n", "    jz .wn\n"), "water-deep", "never drawn"))


def water_host(binp, lst, sym, fam):
    """the WATER scenarios under unicorn, every step against the model, and their red arms -> (lines, fails)"""
    import shutil
    import subprocess
    out, fails = [], []
    sc = dict((n, (m, pk, k)) for n, m, pk, k in water_scenarios())
    for name, (mat, pk, keys) in sc.items():
        p, bad = urun(binp, lst, sym, "water", mat, keys, fam, poke=pk)
        ctl = None
        if name == "water-glass":               # (the control, on the model: the same drop onto the walkway)
            ctl = run_keys("water", BB.MAT_GLASS, water_poke(7, 7, BB.MAT_GLASS, dz=40), keys)
        zt = []
        if name == "water-float":               # (its heights, step by step, on the model)
            q = model("water", mat, pk)
            for k_ in keys:
                q.step(k_)
                zt.append(q.gz >> 8)
        ok, what = water_verdict(name, p, ctl, zt)
        out.append("%s, %d steps: %s; %s" % (name, len(keys), "; ".join(bad) or "the guest is the model at every "
                                             "step", what))
        fails += bad + ([] if ok else ["%s: %s" % (name, what)])
    src0 = open(os.path.join(ROOT, "apps", "bonanza", "fam", "water.asm")).read()
    for arm, (a_, b_), scn, want in water_reds():
        assert src0.count(a_) == 1, "red %s: its patch does not apply" % arm
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "bonanza")
            shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
            open(os.path.join(src, "fam", "water.asm"), "w").write(src0.replace(a_, b_))
            o = os.path.join(td, "part.bin")
            subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", src + "/",
                            "-I", R.at("build/bonanza-art") + "/", "-o", o, os.path.join(src, "fam", "water.asm")],
                           cwd=ROOT, check=True)
            ff = fam_parts({"water": open(o, "rb").read()})
        mat, pk, keys = sc[scn]
        _p, bad = urun(binp, lst, sym, "water", mat, keys, ff, poke=pk)
        ok = any(want in b for b in bad)
        out.append("red %s (%s): %s" % (arm, scn, "red at %s" % bad[0][:160] if ok else "STAYED GREEN"))
        if not ok:
            fails.append("red %s stayed green on the unicorn: %s" % (arm, bad[:1]))
    return out, fails


# THE ARCHWAY (SPEC.md 128.39.7): its scenarios on the ARCH test course (apps/bonanza/courses/arches.bbc, the
# BZARCH=1 knob's course), compiled here from the tree whatever the build, as WATER's are: the family's part is
# in every build's resident bundle
def _arch_course():
    R.COURSES["bench"]                          # (fills both tables)
    R.CRS_K["bench"]
    if "arch" not in dict.keys(R.COURSES):
        dict.__setitem__(R.COURSES, "arch", "apps/bonanza/courses/arches.bbc")
        dict.__setitem__(R.CRS_K, "arch", R.CRS_K["play"])


def arch_poke(wx, wy, mat, gvx=0, gvy=0):
    _arch_course()
    return poke_of(BB.Physics(R.course("arch"), play=True, mat=mat).poke(wx, wy, gvx, gvy))


def arch_scenarios():
    """[(name, material, poke, keys)]: rubber rolled through A's 2-unit arch over the steel pad (it leaves steel);
    rubber Hopping and boosting into A (the face stops it, the underside caps it, it still takes the pad); rubber
    Hopping and boosting into B's bare arch; rubber Hopping under C's 3-unit two-wide arch"""
    H, X, Y = BB.K_HOP, BB.K_R | BB.K_D, BB.K_L | BB.K_D
    return [("arch-roll", BB.MAT_RUBBER, arch_poke(10, 6, BB.MAT_RUBBER), [X] * 80),
            ("arch-boost", BB.MAT_RUBBER, arch_poke(10, 6, BB.MAT_RUBBER),
             [X] * 6 + [X | H] + [X] * 15 + [X | H] + [X] * 137),
            ("arch-hop", BB.MAT_RUBBER, arch_poke(20, 12, BB.MAT_RUBBER),
             [Y] * 4 + [Y | H] + [Y] * 13 + [Y | H] + [Y] * 101),
            ("arch-tall", BB.MAT_RUBBER, arch_poke(23, 6, BB.MAT_RUBBER), [X] * 14 + [X | H] + [X] * 45),
            ("arch-under", BB.MAT_STEEL, arch_poke(12, 6, BB.MAT_STEEL, 120, 0), [X | H] + [X] * 3 + [X | H] + [X] * 35)]


def arch_verdict(name, p, trace):
    """what an arch scenario is for, on the model's trace [(cell, z, air)] -> (ok, what)"""
    clr = dict((pr["at"], pr["clr"]) for pr in p.props if pr["kind"] == BB.FK_ARCH)
    above = [k for k, (cell, z, _a) in enumerate(trace) if cell in clr and z > clr[cell]]
    if name == "arch-under":
        hops = p.nhop
        ok = not above and hops and max(z for _c, z, _a in trace) == 16 and (p.gx >> 12) >= 13
        return ok, "Hops UNDER A's arch: %d Hop(s), the contact never past the floor's 16 px (the clearance)" % hops
    if name in ("arch-roll", "arch-boost"):
        ok = not above and p.mat == BB.MAT_STEEL and (p.gx >> 12) >= (13 if name == "arch-roll" else 12) \
            and (name == "arch-roll" or p.nboost)
        return ok, "through A's arch: steel %s at (%d, %d), %d boost(s), above a clearance at %s" % (
            p.mat == BB.MAT_STEEL, p.gx >> 12, p.gy >> 12, p.nboost, above[:3])
    if name == "arch-hop":
        hi = max(z for _c, z, _a in trace[:30])
        ok = not above and hi > 16 + 2 and p.nfall == 0
        return ok, "Hops into B's arch: up to %d px before it, above a clearance at %s" % (hi, above[:3])
    under = [z for cell, z, air in trace if cell in clr and air and z > 16]
    ok = not above and under and max(under) <= 24
    return ok, "a Hop under C's 3-unit arch, its contact up to %s px inside it (clearance 24)" % (
        max(under) if under else None)


def arch_reds():
    """the ARCHWAY's red arms on the unicorn, each the part assembled from a patched archway.asm: arwall (the CELL
    hook's WALL write gone: the window), arcap (STEP's ceiling gone: the ball), arref (no refill when z leaves the
    band: bz_fref), arcell (the CELL entry 0: the slot never written, so STEP caps the ball at a clearance of 0)"""
    return (("arwall", ("    or byte [bz_nbr + bx + 2], BZ_AR_WALL\n", ""), "arch-boost", "the window"),
            ("arcap", ("    cmp ax, [di + 4]\n    jle .b\n", "    cmp ax, [di + 4]\n    jmp .b\n"), "arch-under",
             "the ball"),
            ("arref", ("    mov byte [bz_fref], 1\n", ""), "arch-boost", "bz_fref"),
            ("arcell", ("    dw 0, 0, 0, ar_step, 0, ar_cell\n", "    dw 0, 0, 0, ar_step, 0, 0\n"), "arch-boost",
             "the ball"))


def arch_host(binp, lst, sym, fam):
    """the ARCHWAY scenarios under unicorn, every step against the model, and their red arms -> (lines, fails)"""
    import shutil
    import subprocess
    out, fails = [], []
    sc = dict((n, (m, pk, k)) for n, m, pk, k in arch_scenarios())
    for name, (mat, pk, keys) in sc.items():
        p, bad = urun(binp, lst, sym, "arch", mat, keys, fam, poke=pk)
        q = model("arch", mat, pk)
        trace = []
        for k in keys:
            q.step(k)
            trace.append(((q.gx >> 12, q.gy >> 12), q.gz >> 8, q.air))
        ok, what = arch_verdict(name, q, trace)
        out.append("%s, %d steps: %s; %s" % (name, len(keys), "; ".join(bad) or "the guest is the model at every "
                                             "step", what))
        fails += bad + ([] if ok else ["%s: %s" % (name, what)])
    src0 = open(os.path.join(ROOT, "apps", "bonanza", "fam", "archway.asm")).read()
    for arm, (a_, b_), scn, want in arch_reds():
        assert src0.count(a_) == 1, "red %s: its patch does not apply" % arm
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "bonanza")
            shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
            open(os.path.join(src, "fam", "archway.asm"), "w").write(src0.replace(a_, b_))
            o = os.path.join(td, "part.bin")
            subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", src + "/",
                            "-I", R.at("build/bonanza-art") + "/", "-o", o, os.path.join(src, "fam", "archway.asm")],
                           cwd=ROOT, check=True)
            ff = fam_parts({"archway": open(o, "rb").read()})
        mat, pk, keys = sc[scn]
        _p, bad = urun(binp, lst, sym, "arch", mat, keys, ff, poke=pk)
        ok = any(want in b for b in bad)
        out.append("red %s (%s): %s" % (arm, scn, "red at %s" % bad[0][:160] if ok else "STAYED GREEN"))
        if not ok:
            fails.append("red %s stayed green on the unicorn: %s" % (arm, bad[:1]))
    return out, fails


# ---- SPIKES (SPEC.md 128.38): the BZSPIKE=1 test course's scenes, poked - each a tile, a ground velocity, the
# keys, and what it is for, judged on the model's own trace; the part assembled from a patched spike.asm for
# each red arm -----------------------------------------------------------------------------------------------
SP_SRC = os.path.join(ROOT, "apps", "bonanza", "courses", "spike.bbc")


def sp_scenes():
    """[(name, material, (wx, wy, gvx, gvy), keys, what)] on SPIKE"""
    D = BB.K_D
    return [("spike-steel", BB.MAT_STEEL, (10, 6, 300, 0), [0] * 100, "steel pushed up onto the corridor's tips "
             "rolls on, whole"),
            ("spike-rubber", BB.MAT_RUBBER, (10, 6, 200, 0), [0] * 60, "rubber drops onto the spikes and POPS: the "
             "shatter, then the respawn"),
            ("spike-glass", BB.MAT_GLASS, (10, 6, 200, 0), [0] * 60, "glass SHATTERS on the spikes, then respawns"),
            ("pop-down", BB.MAT_RUBBER, (6, 14, 0, 250), [D] * 60, "rubber crosses the far row while it is DOWN"),
            ("pop-up", BB.MAT_RUBBER, (6, 11, 0, 200), [0] * 50, "rubber rolls into the near row while it is UP: "
             "it pops"),
            ("pop-steel", BB.MAT_STEEL, (6, 11, 0, 200), [D] * 50, "steel rides the near row UP"),
            ("pop-rise", BB.MAT_RUBBER, (6, 15, 0, 0), [0] * 100, "rubber at rest on the far row DOWN: it rises "
             "under the ball, which pops"),
            ("pop-rise-steel", BB.MAT_STEEL, (6, 15, 0, 0), [0] * 140, "steel at rest on the far row: lifted as "
             "it rises, dropped as it falls"),
            ("mem-glass", BB.MAT_GLASS, (9, 9, 250, 0), [0] * 60, "glass rolls onto the membrane bridge"),
            ("mem-rubber", BB.MAT_RUBBER, (9, 9, 250, 0), [0] * 60, "rubber falls through the membrane"),
            ("water-spike", BB.MAT_STEEL, (22, 5, 0, 200), [0] * 60 + [D] * 190 + [0] * 30, "steel sinks down the "
             "water column, rolls out of the arch and rides the spikes onto the yard")]


def sp_verdict(name, p, zs):
    """what a SPIKE scene is for, on the model at its end (ZS: the ball's (cell, z px, air) every step)"""
    kinds = [e[0] for e in p.events]
    on = [z for c_, z, a in zs if c_ in SP_CELLS and not a]
    if name in ("spike-steel", "pop-steel", "water-spike"):
        tip = [z for z in on]
        ok = "shatter" not in kinds and "stun" not in kinds and p.nfall == 0 and tip and min(tip) == max(tip)
        return ok, "%s on the spikes at z %s px for %d steps, no shatter, no fall, out at %s" % (
            MAT_N[p.mat], sorted(set(tip)), len(tip), (p.gx >> 12, p.gy >> 12))
    if name in ("spike-rubber", "spike-glass", "pop-up", "pop-rise"):
        sh = next((e for e in p.events if e[0] == "shatter"), None)
        ok = sh is not None and p.nfall >= 1 and p.mat == (BB.MAT_GLASS if name == "spike-glass" else BB.MAT_RUBBER)
        return ok, "%s at step %s (lvz %s), %d respawn(s)" % ("popped" if p.mat == BB.MAT_RUBBER else "shattered",
                                                            sh and sh[1], sh and sh[2], p.nfall)
    if name == "pop-rise-steel":
        zz = sorted(set(z for z in on))
        ok = "shatter" not in kinds and p.nfall == 0 and len(zz) >= 2
        return ok, "steel at rest on the row: its z %s px as the spikes rose and fell" % zz
    if name == "pop-down":
        ok = "shatter" not in kinds and p.nfall == 0 and (p.gy >> 12) >= 18
        return ok, "rubber crossed the far row down, to %s" % ((p.gx >> 12, p.gy >> 12),)
    if name == "mem-glass":
        ok = p.nfall == 0 and any(c_ in MEM_CELLS for c_, _z, a in zs)
        return ok, "glass on the membrane, no fall, at %s" % ((p.gx >> 12, p.gy >> 12),)
    ok = p.nfall >= 1 and "shatter" not in kinds
    return ok, "rubber fell through the membrane (%d respawn)" % p.nfall


MAT_N = ("rubber", "steel", "glass")
SP_CELLS, MEM_CELLS = set(), set()


def sp_reds():
    """SPIKES' red arms: (name, (old, new) in spike.asm, scene, what must part)"""
    return (("spcell", ("    dw sp_reset, 0, 0, sp_step, sp_pose, sp_cell\n", "    dw sp_reset, 0, 0, sp_step, sp_pose, 0\n"),
             "spike-steel", "the window"),
            ("spkill", ("    jne .w\n    mov dl, 1\n", "    jne .w\n"), "spike-rubber", "working values"),
            ("spput", ("    mov ax, [di + SP_HARD]\n    mov [bz_mrec + BZM_HARD], ax\n", ""), "spike-rubber",
             "working values"),
            ("spmark", ("    call far [bz_fmkp]          ; its lane MARKED\n", ""), "pop-rise", "never drawn"),
            ("spfref", ("    ja .nx\n    mov byte [bz_fref], 1\n", "    ja .nx\n"), "pop-rise", None),
            ("spmem", ("    cmp byte [bz_mat], BZ_MAT_GLASS\n    je .n\n", "    jmp .n\n"), "mem-rubber", "the window"))


def spike_host(binp, lst, sym):
    """SPIKES' unicorn half (SPEC.md 128.38): every scene on SPIKE equal at every step, what each is for, and the
    red arms -> (lines, failures)"""
    import shutil
    import subprocess
    out, fails = [], []
    c = R.course("spike", src=SP_SRC)
    SP_CELLS.update(pr["at"] for pr in c.part["props"] if pr["kind"] in (BB.SP_K, BB.SP_KP))
    MEM_CELLS.update(pr["at"] for pr in c.part["props"] if pr["kind"] == BB.SP_KM)
    fam = fam_parts()
    sc = []
    for name, mat, at, keys, what in sp_scenes():
        poke = poke_of(BB.Physics(c, play=True, mat=mat).poke(*at))
        sc.append((name, mat, poke, keys))
        p, bad = urun(binp, lst, sym, "spike", mat, keys, fam, poke=poke, src=SP_SRC, k=0)
        q = model("spike", mat, poke, src=SP_SRC)
        zs = []
        for k_ in keys:
            q.step(k_)
            zs.append(((q.gx >> 12, q.gy >> 12), q.gz >> 8, q.air))
        ok, saw = sp_verdict(name, q, zs)
        out.append("spike %s (%s): %s; %s" % (name, what, "; ".join(bad)[:200] or "equal at every step", saw))
        fails += ["spike %s: %s" % (name, b) for b in bad] + ([] if ok else ["spike %s is not what it is for: %s"
                                                                            % (name, saw)])
    src0 = open(os.path.join(ROOT, "apps", "bonanza", "fam", "spike.asm")).read()
    for arm, (a_, b_), scn, want in sp_reds():
        assert src0.count(a_) == 1, "red %s: its patch does not apply" % arm
        with tempfile.TemporaryDirectory() as td:
            d = os.path.join(td, "bonanza")
            shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), d)
            open(os.path.join(d, "fam", "spike.asm"), "w").write(src0.replace(a_, b_))
            o = os.path.join(td, "part.bin")
            subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", d + "/",
                            "-I", R.at("build/bonanza-art") + "/", "-o", o, os.path.join(d, "fam", "spike.asm")],
                           cwd=ROOT, check=True)
            ff = fam_parts({"spike": open(o, "rb").read()})
        name, mat, poke, keys = next(s for s in sc if s[0] == scn)
        _p, bad = urun(binp, lst, sym, "spike", mat, keys, ff, poke=poke, src=SP_SRC, k=0)
        hit = next((b for b in bad if want is None or want in b), None)
        out.append("red %s (%s): %s" % (arm, scn, "red at %s" % hit[:160] if hit else "STAYED GREEN"))
        if not hit:
            fails.append("red %s stayed green on the unicorn: %s" % (arm, bad[:1]))
    return out, fails


def _noentry(part, h):
    """a family part with hook H's entry zeroed (a red arm: the hook never called)"""
    b = bytearray(part)
    k = h.bit_length() - 1
    b[12 + 2 * k:14 + 2 * k] = b"\0\0"
    return bytes(b)


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
    CK = mill_rec(BB.PK_CLOCK)                  # wave 7 (SPEC.md 128.18.5.3): a clock is a post with no kick
    pk = mill_poke(CK["at"][0] - 2, CK["at"][1], BB.VMAXG, 0)
    keys = [0] * 60
    p, _ = ev_of("mill", 0, pk, keys)
    hit = evs(p, "kick")
    add("clock", 0, pk, keys, "rolled at the cap into MILL's clock at %s: stopped by its ball's post, back at "
        "%s of %d (no kick: K 0), never past its centre" % (CK["at"], [e[4] for e in hit[:1]], BB.VMAXG),
        hit and hit[0][2] == CK["i"] and 0 < hit[0][4] < BB.VMAXG and p.gvx < 0 and not p.nfall
        and p.gx >> 8 < CK["cx"])
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

# ---- WAVE 4 (SPEC.md 128.14.4, 128.14.14 bonanzaphys): flags, pads, springs, the cup ----
DIR8 = (K.K_R, K.K_L, K.K_U, K.K_D, K.K_R | K.K_D, K.K_R | K.K_U, K.K_L | K.K_D, K.K_L | K.K_U)


def w4_rec(crs, kind, **kw):
    return [r for r in R.course(crs).part["props"] if r["kind"] == kind
            and all(r.get(k_) == v for k_, v in kw.items())]


def w4_poke(crs, wx, wy, mat, gvx=0, gvy=0, lift=0, extra=None, recpoke=None):
    p = BB.Physics(R.course(crs), play=True, mat=mat).poke(wx, wy, gvx, gvy)
    if lift:
        p.gz += lift << 8
        p.air, p.ztop = 1, p.gz >> 8
    p._derive(True)
    d = poke_of(p)
    if extra:
        d["extra"] = dict(extra)
    if recpoke:
        d["recpoke"] = recpoke
    return d


def w4_replays():
    """wave 4's replays, each FOUND and PROVED on the model on the shipped
    MOON and PEAK (SUMMIT) - the approaches searched, so a re-laid course re-finds
    them - with the red arm's broken model shown to part where it has one"""
    S = []

    def add(name, crs, mat, poke, keys, what, ok, red=None, tilts=None, tables=False):
        S.append({"name": name, "crs": crs, "mat": mat, "poke": poke, "keys": keys, "what": what,
                  "ok": bool(ok), "red": red, "tilts": tilts, "tables": tables})

    def evs(p, *kinds):
        return [e for e in p.events if e[0] in kinds]
    # flag: a pit past flag 0 respawns ON it (MOON)
    F0 = w4_rec("moon", BB.PK_CHECKPOINT, num=0)[0]
    found = None
    for d in DIR8:
        for v in (0, 192, BB.VMAXG):
            ux = (1 if d & K.K_R else -1 if d & K.K_L else 0)
            uy = (1 if d & K.K_D else -1 if d & K.K_U else 0)
            pk = w4_poke("moon", *F0["at"], mat=0, gvx=ux * v, gvy=uy * v)
            keys = [d] * 240
            p = run_keys("moon", 0, pk, keys)
            r = evs(p, "respawn")
            if evs(p, "flag") and r and r[0][2] == tuple(F0["at"]) and p.nfall >= 1:
                found = (pk, keys[:r[0][1] + 30], r[0][1])
                break
        if found:
            break
    pk, keys, at = found if found else (w4_poke("moon", *F0["at"], mat=0), [0], None)
    add("flag", "moon", 0, pk, keys, "rolled off flag 0 %s into a pit: respawned ON it at step %s" % (F0["at"], at),
        found, red={"_ckpt_safe": True})
    # flagmat: a glass ball touching a flag in the air and shattering below it respawns there as the FLAG's ball
    for crs, num in (("peak", 3), ("moon", 2)):
        F = w4_rec(crs, BB.PK_CHECKPOINT, num=num)[0]
        pk = w4_poke(crs, *F["at"], mat=BB.MAT_GLASS, lift=64)
        keys = [0] * 90
        p = run_keys(crs, BB.MAT_GLASS, pk, keys)
        r = evs(p, "respawn")
        add("flagmat-%s" % crs, crs, BB.MAT_GLASS, pk, keys,
            "glass dropped 64 px onto flag %d %s (its ball %s): touched, shattered, respawned there as %s" % (
                num, F["at"], BB.MAT_NAMES[F["ball"]], BB.MAT_NAMES[p.mat]),
            evs(p, "flag") and evs(p, "shatter") and r and r[0][2] == tuple(F["at"]) and p.mat == F["ball"],
            red={"_ckmat_touch": True} if F["ball"] != BB.MAT_GLASS else None)
    # padswap: every pad of MOON and PEAK, a ball of another material rolled on it with an arrow held
    for crs in ("moon", "peak"):
        for pd in w4_rec(crs, BB.PK_PAD):
            mat = (pd["mat"] + 1) % 3
            best = None
            for d in DIR8:
                pk = w4_poke(crs, *pd["at"], mat=mat)
                keys = [0] * 3 + [d] * 24 + [0] * 12
                p = run_keys(crs, mat, pk, keys)
                if p.npad == 1 and not p.nfall and not p.nshat and not p.nstun and p.mat == pd["mat"]:
                    best = (pk, keys)
                    break
            pk, keys = best if best else (w4_poke(crs, *pd["at"], mat=mat), [0] * 10)
            add("padswap-%s-%d" % (crs, pd["i"]), crs, mat, pk, keys,
                "%s rolled on %s's %s pad %s: swapped once, its record and tables" % (
                    BB.MAT_NAMES[mat], crs.upper(), BB.MAT_NAMES[pd["mat"]], pd["at"]), best, tables=True)
    # the cup (PEAK's): 128 holes out from a neighbour; the fastest approach under VMAXG that LIPS OUT;
    # a stunned steel ball in the mouth holes out after its stun; a shattering glass one does not
    CU = w4_rec("peak", BB.PK_CUP)[0]
    cx, cy = CU["at"]
    cap, lip = None, None
    for ux, uy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for dist in (1, 2):
            c0 = R.course("peak")
            if BB.Grid(c0.cga, c0.wcga).cell(cx - ux * dist, cy - uy * dist)[3] != BB.KIND_FLOOR:
                continue
            if cap is None:
                pk = w4_poke("peak", cx - ux * dist, cy - uy * dist, mat=0, gvx=128 * ux, gvy=128 * uy)
                p = run_keys("peak", 0, pk, [0] * 80)
                if evs(p, "cup") and not p.nlip:
                    cap = (pk, [0] * (evs(p, "cup")[0][1] + 4), evs(p, "cup")[0][1])
            if lip is None:
                for v in (256, 240, 224, 208, 192):
                    pk = w4_poke("peak", cx - ux * dist, cy - uy * dist, mat=0, gvx=v * ux, gvy=v * uy)
                    p = run_keys("peak", 0, pk, [0] * 60)
                    lp = evs(p, "lip")
                    if lp and not evs(p, "cup") and p.events[p.events.index(lp[0])][2] > CU["capture"]:
                        lip = (pk, [0] * 60, lp[0][1], v)
                        break
    pk, keys, at = cap if cap else (w4_poke("peak", cx, cy, 0), [0], None)
    add("cup-128", "peak", 0, pk, keys, "rolled into PEAK's cup %s at 128: holed out at step %s, the play over" % (
        CU["at"], at), cap)
    pk, keys, at, v = lip if lip else (w4_poke("peak", cx, cy, 0), [0], None, None)
    add("cup-lip", "peak", 0, pk, keys, "rolled across the mouth at %s: LIPPED OUT at step %s (a pop of %d) and "
        "rolled on" % (v, at, BB.LIPZ), lip, red={"_cup_nov": True})
    pk = w4_poke("peak", cx, cy, mat=BB.MAT_STEEL, extra={"mst": BB.ST_STUN, "mct": 10})
    p = run_keys("peak", BB.MAT_STEEL, pk, [0] * 20)
    add("cup-stun", "peak", BB.MAT_STEEL, pk, [0] * 20, "a STUNNED steel ball in the mouth holes out as its stun "
        "ends (step %s)" % (evs(p, "cup")[0][1] if evs(p, "cup") else None),
        evs(p, "cup") and evs(p, "cup")[0][1] == 10)
    pk = w4_poke("peak", cx, cy, mat=BB.MAT_GLASS, extra={"mst": BB.ST_SHATTER, "mct": BB.SHA_STEPS})
    p = run_keys("peak", BB.MAT_GLASS, pk, [0] * (BB.SHA_STEPS + 6))
    add("cup-shatter", "peak", BB.MAT_GLASS, pk, [0] * (BB.SHA_STEPS + 6), "a SHATTERING glass ball in the mouth "
        "does not hole out: respawned", not evs(p, "cup") and evs(p, "respawn"))
    # springs (PEAK): rubber up spring 1 onto the upper tier; a rubber BOUNCE on spring 2 with its launch
    # lowered to 360 leaves at the max, not the sum; glass shattering on a spring is not launched
    SP = w4_rec("peak", BB.PK_SPRING)
    s1, s2 = SP[0], SP[-1]
    grid = BB.Grid(R.course("peak").cga, R.course("peak").wcga)
    h0 = grid.cell(*s1["at"])[0]
    tier = None
    for d in DIR8:
        ux = (1 if d & K.K_R else -1 if d & K.K_L else 0)
        uy = (1 if d & K.K_D else -1 if d & K.K_U else 0)
        for dist in (1, 2, 3):
            ax, ay = s1["at"][0] - ux * dist, s1["at"][1] - uy * dist
            if grid.cell(ax, ay)[3] != BB.KIND_FLOOR:
                continue
            for v in (128, 192, 256, 320):
                pk = w4_poke("peak", ax, ay, mat=0, gvx=v * ux, gvy=v * uy)
                keys = [d] * 40 + [0] * 80
                p = run_keys("peak", 0, pk, keys)
                if p.nspr and not p.nfall and not p.air and grid.cell(p.gx >> 12, p.gy >> 12)[0] >= h0 + 3:
                    tier = (pk, keys, v, (p.gx >> 12, p.gy >> 12))
                    break
            if tier:
                break
        if tier:
            break
    pk, keys, v, end = tier if tier else (w4_poke("peak", *s1["at"], 0), [0], None, None)
    add("spring-tier", "peak", 0, pk, keys, "rubber at %s up spring 1 %s onto the upper tier (ends on %s)" % (
        v, s1["at"], end), tier)
    pk = w4_poke("peak", *s2["at"], mat=0, lift=30, recpoke=(s2["i"], "gvz", 360))
    pk["gvz"] = -400
    p = run_keys("peak", 0, pk, [0] * 60)
    sp = evs(p, "spring")
    add("spring-max", "peak", 0, pk, [0] * 60, "rubber bouncing on spring 2 %s, its launch poked to 360: leaves at "
        "max(360, the rebound) = %s, not the sum" % (s2["at"], sp[0][2] if sp else None),
        sp and evs(p, "bounce") and sp[0][2] == max(360, evs(p, "bounce")[0][3]),
        red={"_spring_sum": True})
    pk = w4_poke("peak", *s2["at"], mat=BB.MAT_GLASS, lift=64)
    p = run_keys("peak", BB.MAT_GLASS, pk, [0] * 50)
    add("spring-shatter", "peak", BB.MAT_GLASS, pk, [0] * 50, "glass dropped 64 px onto spring 2: shattered, never "
        "launched", evs(p, "shatter") and not p.nspr)
    # RETURN mid-roll: back to the flag, bz_nret 1, bz_nfall unchanged (MOON's flag 1)
    F1 = w4_rec("moon", BB.PK_CHECKPOINT, num=1)[0]
    ret = None
    for d in DIR8:
        pk = w4_poke("moon", *F1["at"], mat=0)
        keys = [d] * 14 + [d | BB.K_RET] + [0] * 24
        p = run_keys("moon", 0, pk, keys)
        rr = evs(p, "return")
        if rr and rr[0][2] == tuple(F1["at"]) and p.nret == 1 and not p.nfall and evs(p, "flag"):
            ret = (pk, keys)
            break
    pk, keys = ret if ret else (w4_poke("moon", *F1["at"], 0), [0])
    add("return", "moon", 0, pk, keys, "RETURN mid-roll from flag 1 %s: back on it, bz_nret 1, no fall" % (
        F1["at"],), ret)
    # tilt: a TILT log on FIRST - every cap 0 - 8 on both axes, then a held Right at cap 8 dropped to 2
    keys, tilts = [], []
    for c_ in range(9):
        keys += [K.K_R | K.K_D] * 4 + [K.K_L | K.K_U] * 4
        tilts += [(c_ << 4) | (8 - c_)] * 8
    keys += [0] * 10 + [K.K_R] * 9 + [K.K_R] * 4 + [0] * 10
    tilts += [0x88] * 19 + [0x28] * 4 + [0x88] * 10
    p = run_keys("first", 0, None, keys, tilts)
    q = model("first", 0, None)
    lv = []
    for i, (k_, t_) in enumerate(zip(keys, tilts)):
        q.step(k_, t_)
        if 72 + 10 + 8 <= i < 72 + 10 + 13:
            lv.append(q.lvl[1])
    add("tilt", "first", 0, None, keys, "a TILT log: caps 0 - 8 on both axes, then Right held at cap 8 and 2: "
        "levels %s" % lv, lv == [8, 6, 4, 2, 2] and not p.nfall, red={"_tilt_min": True}, tilts=tilts)
    return S


# ---- WAVE 6 (SPEC.md 128.16.4, 128.16.14 bonanzaphys): the boost, its token, the drag ----
CONTACT = ("land", "bounce", "hopc", "boost", "stun", "shatter")
DRAG_PRICE = 428            # bz_gax's as-built price at worst, clocks (k 8, d 0, Grip to 0, the clamp's two
                            # tests; the fetch floor, x 1.05: SPEC.md 128.16.3.1) - a COST, not a retunable
DRAG_SLACK = 1.25           # ...and the span assertion's 25% (SPEC.md 128.16.14)


def pl_poke(crs, at, mat, d=(0, 0), v=None, gv=None):
    """a poke on tile AT's centre at V (the cap) along D, every level full when
    it moves (bbcourse._play_run's ball); GV an explicit (gvx, gvy)"""
    v = BB.VMAXG if v is None else v
    gvx, gvy = gv if gv is not None else (v * d[0], v * d[1])
    p = BB.Physics(R.course(crs), play=True, mat=mat).poke(at[0], at[1], gvx, gvy)
    p.lvl = [BB.LVL_MAX] * 4 if (gvx or gvy) else [0] * 4
    p._derive(True)
    return poke_of(p)


def run_ix(crs, mat, poke, keys, **red):
    """the model over KEYS: -> (the Physics, [(key index, contact kind)])"""
    p = model(crs, mat, poke, **red)
    out = []
    for i, k in enumerate(keys):
        n0 = len(p.events)
        p.step(k)
        out += [(i, e[0]) for e in p.events[n0:] if e[0] in CONTACT]
        if p.goal or p.tout:
            break
    return p, out


def with_space(keys, *at):
    """KEYS with Space's bit added on the steps AT (each an edge: the step before it clear)"""
    k = list(keys)
    for i in at:
        if i is not None and 0 <= i < len(k):
            k[i] |= K.K_HOP
    return k


def first_after(cs, i0, kinds=CONTACT):
    return next((i for i, kind in cs if i > i0 and kind in kinds), None)


def play_rect(H):
    r = dict(BB.PLAY_RUNGS)[H]
    return BB._rect(r), r


def hop_off(crs, mat, start, d, want_off, space, n=90):
    """a Hop off a top along d, searched over its take-off step: the first whose
    FIRST contact is on a cell of WANT_OFF, Space SPACE steps before that contact
    (None: none): -> (poke, keys, contact index) or None"""
    pk = pl_poke(crs, start, mat, d)
    dk = BB._PLAY_DIRK[d]
    for a in range(1, 40):
        keys = with_space([dk] * n, a)
        p, cs = run_ix(crs, mat, pk, keys)
        c = first_after(cs, a)
        if c is None or not p.nhop:
            continue
        q = model(crs, mat, pk)
        for i in range(c + 1):
            q.step(keys[i])
        if (q.gx >> 12, q.gy >> 12) not in want_off:
            continue
        keys = with_space(keys, None if space is None else c - space)
        return pk, keys[:c + 12], c
    return None


def w6_replays():
    """wave 6's replays (SPEC.md 128.16.14 bonanzaphys), each FOUND and PROVED on
    the model - on the PLAYGROUND (its apron, rungs, mat and sand lane), TRIAL's
    and FIRST's ramps and MILL's lift - with each red arm's broken model shown to
    part.  Every expected value is the model's or MATERIALS': a retune turns
    nothing red by itself (SPEC.md 128.16.11)"""
    S = []
    R_, ST, GL = BB.MAT_RUBBER, BB.MAT_STEEL, BB.MAT_GLASS
    BOOST = BB.MATERIALS[R_]["BOOST"]

    def add(name, crs, mat, poke, keys, what, ok, red=None, span=False, nboost=None):
        S.append({"name": name, "crs": crs, "mat": mat, "poke": poke, "keys": keys, "what": what,
                  "ok": bool(ok), "red": red, "span": span, "nboost": nboost})
    pc = R.course("play")
    start = BB.Grid(pc.cga, pc.wcga).start
    rest = pl_poke("play", start, R_)
    # boost: a Hop from rest on the apron, Space 2 steps before its first contact
    base = [0] * 3 + [K.K_HOP] + [0] * 80
    _p, cs = run_ix("play", R_, rest, base)
    c = first_after(cs, 3)
    keys = with_space(base, c - 2 if c else None)
    p, cs2 = run_ix("play", R_, rest, keys)
    q = model("play", R_, rest)
    for i in range((c or 0) + 1):
        q.step(keys[i])
    ev = [e for e in p.events if e[0] == "boost"]
    add("boost", "play", R_, rest, keys, "a Hop on the apron, Space before its contact (step %s): nboost %d, gvz %s "
        "(BOOST %d), stf %d (BZ_STRS %d)" % (c, p.nboost, ev[0][3] if ev else None, BOOST, q.stf, BB.BZ_STRS),
        c and p.nboost == 1 and ev and ev[0][3] == BOOST and q.stf == BB.BZ_STRS and not p.nfall)
    # boostclimb: onto the 1.5-unit ledge, a Hop and its boost at the cap from the apron's front row
    top, r = play_rect(1.5)
    st_ = ((r[0] + r[2] - 1) // 2, BB.PLAY_FRONT)
    found = None
    for a in range(BB.LAD_PTS):
        land = BB._play_contact(pc, R_, st_, (0, -1), a)
        if land is None or land - 2 <= a:
            continue
        ok, _q = BB._play_run(pc, R_, st_, (0, -1), top, a, land - 2)
        if ok:
            found = (a, land)
            break
    if found:
        a, land = found
        pk = pl_poke("play", st_, R_, (0, -1))
        keys = with_space([BB._PLAY_DIRK[(0, -1)]] * (land + 30), a, land - 2) + [K.K_GRIP] * 40
        p = model("play", R_, pk)
        on = None
        for i, k_ in enumerate(keys):
            p.step(k_)
            if on is None and not p.air and (p.gx >> 12, p.gy >> 12) in top:
                on = i
    add("boostclimb", "play", R_, pk if found else rest, keys if found else [0],
        "onto the 1.5-unit ledge %s: Hop at %s, boost at %s, on the ledge at step %s" % (
            r, found and found[0], found and found[1], on if found else None),
        found and on is not None and p.nboost == 1 and not p.nfall)
    # boostdrop: a Hop off the 1-unit top onto the apron, Space at its contact: a boost though its impact passes 384
    t1, r1 = play_rect(1)
    apron = {(x, y) for x in range(r1[0] - 2, r1[2] + 2) for y in range(r1[3], BB.PLAY_FRONT + 1)}
    hd = hop_off("play", R_, ((r1[0] + r1[2] - 1) // 2, r1[1]), (0, 1), apron, 2)
    if hd:
        pk, keys, c = hd
        q = model("play", R_, pk)
        for i in range(c + 1):
            q.step(keys[i])
        bev = [e for e in q.events if e[0] == "boost"]
    add("boostdrop", "play", R_, hd[0] if hd else rest, hd[1] if hd else [0],
        "a Hop off the 1-unit top onto the apron, Space at the contact (step %s): %s at impact %s, sqf %s, stf %s" % (
            hd and hd[2], "boost" if hd and bev else "NO boost", bev[0][2] if hd and bev else None,
            q.sqf if hd else None, q.stf if hd else None),
        hd and bev and bev[0][2] >= BB.SQTHR and q.sqf == 0 and q.stf == BB.BZ_STRS and q.nboost == 1)
    # boostfall: a Hop off the 2-unit top, Space at its contact: round 3b (SPEC.md 128.17.17) a BOOST at the
    # bounce plus BADD (round 3: a contact Hop, rule 5); `noadd` gives the contact Hop
    t2, r2 = play_rect(2)
    apron2 = {(x, y) for x in range(r2[0] - 2, r2[2] + 2) for y in range(r2[3], BB.PLAY_FRONT + 1)}
    hf = hop_off("play", R_, ((r2[0] + r2[2] - 1) // 2, r2[1]), (0, 1), apron2, 2)
    if hf:
        p, cs = run_ix("play", R_, hf[0], hf[1])
    add("boostfall", "play", R_, hf[0] if hf else rest, hf[1] if hf else [0],
        "a Hop off the 2-unit top onto the apron, Space at the contact (step %s): %s" % (
            hf and hf[2], [k_ for _i, k_ in cs][:2] if hf else None),
        hf and [k_ for _i, k_ in cs][:1] == ["boost"] and p.nboost == 1
        and [e for e in p.events if e[0] == "boost"][0][3] > BB.MATERIALS[R_]["BOOST"],
        red={"_noadd": True}, nboost=1)
    # pumpchk: Space at every contact of the chain: one boost, then contact Hops
    keys = [0] * 3 + [K.K_HOP if i % 2 == 0 else 0 for i in range(300)]
    p, cs = run_ix("play", R_, rest, keys)
    kinds = [k_ for _i, k_ in cs if k_ in ("boost", "hopc")]
    add("pumpchk", "play", R_, rest, keys, "Space at every contact: %d boost(s), then %d contact Hops" % (
        p.nboost, kinds.count("hopc")), p.nboost == 1 and kinds[:1] == ["boost"] and kinds.count("hopc") >= 3,
        red={"_pump": True})
    # bouncefirst: a Hop, no Space at its first contact (a bounce), Space at its second: a contact Hop
    base = [0] * 3 + [K.K_HOP] + [0] * 120
    _p, cs = run_ix("play", R_, rest, base)
    c1 = first_after(cs, 3)
    c2 = first_after(cs, c1) if c1 is not None else None
    keys = with_space(base, c2 - 2 if c2 else None)
    p, cs = run_ix("play", R_, rest, keys)
    add("bouncefirst", "play", R_, rest, keys, "a Hop, a bounce at %s, Space before the second contact %s: %s" % (
        c1, c2, [k_ for _i, k_ in cs][:2]), c2 and [k_ for _i, k_ in cs][:2] == ["bounce", "hopc"]
        and p.nboost == 0, red={"_no_clear": True})
    # (gripchain: wave 6b's, re-keyed with mid-flight taps - w6b_replays)
    # rampnot: a Hop whose first contact is on a RAMP (TRIAL's or FIRST's), Space before it: no boost
    found = None
    for crs in ("trial", "first"):
        gr = BB.Grid(R.course(crs).cga, R.course(crs).wcga)
        for y in range(64):
            for x in range(64):
                cl = gr.cell(x, y)
                if cl[3] != BB.KIND_FLOOR or not (cl[1] or cl[2]) or cl[4] & BB.FL_OBS:
                    continue
                pk = pl_poke(crs, (x, y), R_)
                base = [K.K_HOP] + [0] * 60
                _p, cs = run_ix(crs, R_, pk, base)
                c = first_after(cs, 0)
                if c is None or c < 3:
                    continue
                keys = with_space(base, c - 2)[:c + 20]
                q = model(crs, R_, pk)
                for i in range(c + 1):
                    q.step(keys[i])
                ccell = gr.cell(q.gx >> 12, q.gy >> 12)
                p, cs = run_ix(crs, R_, pk, keys)
                pr, _cs = run_ix(crs, R_, pk, keys, _boost_rise=True)
                if (ccell[1] or ccell[2]) and [k_ for _i, k_ in cs][:1] == ["hopc"] and not p.nboost \
                        and pr.nboost:
                    found = (crs, pk, keys, (x, y), c)
                    break
            if found:
                break
        if found:
            break
    crs, pk, keys, at, c = found if found else ("trial", rest, [0], None, None)
    add("rampnot", crs, R_, pk, keys, "a Hop from %s's ramp cell %s, its first contact (step %s) on a ramp, Space "
        "before it: a contact Hop, no boost" % (crs.upper(), at, c), found, red={"_boost_rise": True})
    # sandnot, matnot: a Hop from rest on the PLAYGROUND's sand lane and on its mat, Space before the contact
    gr = BB.Grid(pc.cga, pc.wcga)
    for name, test in (("sandnot", lambda cl: cl[5] == BB.SURF_SAND),
                       ("matnot", lambda cl: cl[5] == BB.SURF_BOUNCE)):
        cells = [(x, y) for y in range(64) for x in range(64) if gr.cell(x, y)[3] == BB.KIND_FLOOR
                 and test(gr.cell(x, y)) and not gr.cell(x, y)[1] and not gr.cell(x, y)[2]]
        res = None
        for at in cells:
            pk = pl_poke("play", at, R_)
            base = [0] * 3 + [K.K_HOP] + [0] * 60
            _p, cs = run_ix("play", R_, pk, base)
            c = first_after(cs, 3)
            if c is None:
                continue
            keys = with_space(base, c - 2)[:c + 20]
            p, cs = run_ix("play", R_, pk, keys)
            if [k_ for _i, k_ in cs][:1] == ["hopc"] and not p.nboost:
                res = (at, pk, keys, c)
                break
        at, pk, keys, c = res if res else (None, rest, [0], None)
        add(name, "play", R_, pk, keys, "a Hop from rest on the PLAYGROUND's %s %s, Space before its contact (step "
            "%s): a contact Hop, no boost" % ("sand" if name == "sandnot" else "mat", at, c), res)
    # liftnot: a Hop on MILL's lift slab, Space before its contact on the slab: no boost
    pk = slab_poke(0)
    base = [K.K_HOP] + [0] * 80
    _p, cs = run_ix("mill", R_, pk, base)
    c = first_after(cs, 0)
    keys = with_space(base, c - 2 if c else None)[:(c or 0) + 20]
    p, cs = run_ix("mill", R_, pk, keys)
    add("liftnot", "mill", R_, pk, keys, "a Hop on MILL's lift slab, Space before its contact (step %s) on it: %s, "
        "onp %d" % (c, [k_ for _i, k_ in cs][:1], p.onp), c and [k_ for _i, k_ in cs][:1] == ["hopc"]
        and not p.nboost and p.onp, red={"_slab_boost": True})
    # springarm (round 3b, SPEC.md 128.17.17; wave 6's springnot): a Hop taken on PEAK's spring rides the
    # spring's launch, which now TAKES the token, so Space before that flight's first contact boosts there
    # (`springoff`, round 3's spring that spent it: a contact Hop)
    found = None
    for spr in [r for r in R.course("peak").part["props"] if r["kind"] == BB.PK_SPRING]:
        for gv in ((160, 0), (-160, 0), (0, 160), (0, -160), (200, 0), (0, 0)):
            pk = pl_poke("peak", spr["at"], R_, gv=gv)
            base = [K.K_HOP] + [0] * 120
            _p, cs = run_ix("peak", R_, pk, base)
            c = first_after(cs, 0)
            if c is None or c < 3 or not _p.nspr:
                continue
            keys = with_space(base, c - 2)[:c + 20]
            p, cs = run_ix("peak", R_, pk, keys)
            pr, cs_ = run_ix("peak", R_, pk, keys, _springoff=True)
            if p.nspr and [k_ for _i, k_ in cs][:1] == ["boost"] and p.nboost == 1 and not pr.nboost \
                    and [k_ for _i, k_ in cs_][:1] == ["hopc"]:
                found = (pk, keys, spr["at"], gv, c)
                break
        if found:
            break
    pk, keys, at, gv, c = found if found else (rest, [0], None, None, None)
    add("springarm", "peak" if found else "play", R_, pk, keys, "a Hop on PEAK's spring %s at %s, the spring's "
        "launch, Space before its flight's first contact (step %s): a boost" % (at, gv, c), found,
        red={"_springoff": True}, nboost=1)
    # spentspring (round 3b): rubber rolled toward PEAK's spring at (27, 33), a Hop, Space every 2 steps after:
    # ONE boost, whose bounce carries the ball onto the spring - a launch out of the air while the boost is
    # spent, so no token and no second boost (`nospent`: the spring's launch arms, a second boost)
    found = None
    for d, at, v in (((1, 0), (24, 33), 160),):
        dk = BB._PLAY_DIRK[d]
        pk = pl_poke("peak", at, R_, d, v)
        for a in range(0, 10):
            keys = [dk | (K.K_HOP if (i == a or (i > a + 4 and (i - a) % 2 == 0)) else 0) for i in range(120)]
            p, cs = run_ix("peak", R_, pk, keys)
            ev = [e[0] for e in p.events]
            if p.nboost != 1 or p.nfall or "boost" not in ev:
                continue
            if "spring" not in ev[ev.index("boost"):]:
                continue
            q, _c = run_ix("peak", R_, pk, keys, _nospent=True)
            if q.nboost >= 2 and not q.nfall:
                found = (pk, keys, at, a)
                break
    pk, keys, at, a = found if found else (rest, [0], None, None)
    add("spentspring", "peak" if found else "play", R_, pk, keys, "rubber from %s toward PEAK's spring, a Hop at %s "
        "and Space every 2 steps: one boost, its bounce onto the spring, no second boost" % (at, a), found,
        red={"_nospent": True}, nboost=1)
    # steelglass: steel and glass Hop on the apron, Space before the contact: contact Hops, never a boost
    for mat in (ST, GL):
        pk = pl_poke("play", start, mat)
        base = [0] * 3 + [K.K_HOP] + [0] * 60
        _p, cs = run_ix("play", mat, pk, base)
        c = first_after(cs, 3)
        keys = with_space(base, c - 2 if c else None)[:(c or 0) + 20]
        p, cs = run_ix("play", mat, pk, keys)
        add("steelglass-%s" % BB.MAT_NAMES[mat], "play", mat, pk, keys, "%s: Space before the Hop's contact (step "
            "%s): %s" % (BB.MAT_NAMES[mat], c, [k_ for _i, k_ in cs][:1]),
            c and [k_ for _i, k_ in cs][:1] == ["hopc"] and not p.nboost)
    # drag: one arrow from rest settles at the model's top; from the cap it falls back to it (the remainders
    # compared every frame); the longest level run on the PLAYGROUND, searched
    feel = BB.axis_feel(R_)
    top = feel[2]
    best = None
    for y in range(8, 40):
        for x in range(4, 40):
            cl = gr.cell(x, y)
            if cl[3] != BB.KIND_FLOOR or cl[1] or cl[2] or cl[5] != BB.SURF_NORMAL or cl[4] & BB.FL_OBS:
                continue
            q = BB.Physics(pc, play=True, mat=R_).poke(x, y, 0, 0)
            n = 0
            for i in range(400):
                n0 = len(q.events)
                q.step(K.K_R)
                cl2 = q.cell(q.gx >> 12, q.gy >> 12)
                if q.nfall or q.air or q.goal or any(e[0] != "corner" for e in q.events[n0:]) or cl2[1] \
                        or cl2[2] or cl2[5] != BB.SURF_NORMAL or cl2[3] != BB.KIND_FLOOR:   # (a FIELD cell,
                    break                       # SPEC.md 128.28: its +1 is a shape, not slopes - not level)
                n = i + 1
            if best is None or n > best[0]:
                best = (n, (x, y))
    n, at = best
    pk = pl_poke("play", at, R_)
    keys = [K.K_R] * n
    p = model("play", R_, pk)
    mx = 0
    for k_ in keys:
        p.step(k_)
        mx = max(mx, abs(p.gvx))
    add("drag-rest", "play", R_, pk, keys, "one arrow (Right) from rest at %s, %d steps on level ground: |gvx| %d, "
        "the axis model's top %d" % (at, n, mx, top), mx >= top - 3 and mx <= top and not p.nfall,
        red={"_ceil_drag": True}, span=True)
    pk = pl_poke("play", at, R_, gv=(BB.VMAXG, -BB.VMAXG))
    p = model("play", R_, pk)
    seq = []
    for i in range(400):
        n0 = len(p.events)
        p.step(K.K_R)
        cl2 = p.cell(p.gx >> 12, p.gy >> 12)
        if p.nfall or p.air or any(e[0] != "corner" for e in p.events[n0:]) or cl2[1] or cl2[2] \
                or cl2[5] != BB.SURF_NORMAL or cl2[3] != BB.KIND_FLOOR:
            break
        seq.append(abs(p.gvx))
    keys = [K.K_R] * len(seq)
    add("drag-cap", "play", R_, pk, keys, "one arrow from the cap at %s, %d steps: |gvx| 384 -> %s, the axis "
        "model's settled top %d" % (at, len(seq), seq[-1] if seq else None, feel[3]),
        seq and top <= seq[-1] <= top + 8, red={"_ceil_drag": True})
    # gripglass: glass at the cap along the apron, Grip held: stopped in the axis model's steps
    gfeel = BB.axis_feel(GL)
    found = None
    for y in range(14, 20):
        for x in range(4, 20):
            pk = pl_poke("play", (x, y), GL, gv=(BB.VMAXG, 0))
            p = model("play", GL, pk)
            for i in range(gfeel[6] + 5):
                p.step(K.K_GRIP)
                if not p.gvx:
                    break
            if not p.gvx and not p.nfall and not [e for e in p.events if e[0] not in ("corner",)] \
                    and i + 1 == gfeel[6]:
                found = (pk, (x, y), i + 1)
                break
        if found:
            break
    pk, at, n = found if found else (rest, None, None)
    add("gripglass", "play", GL, pk, [K.K_GRIP] * (gfeel[6] + 20), "glass at the cap at %s, Grip held: stopped "
        "in %s steps, the axis model's %d" % (at, n, gfeel[6]), found)
    return S + w6b_replays()


def grip_stop(mat, ys=range(8, 40), xs=range(4, 40)):
    """a PLAYGROUND tile from which `mat` at the cap along +wx, Grip held, stops
    in exactly the axis model's Grip steps with no event on the way (a level
    normal run long enough): -> (poke, tile, steps) or None"""
    feel = BB.axis_feel(mat)
    for y in ys:
        for x in xs:
            pk = pl_poke("play", (x, y), mat, gv=(BB.VMAXG, 0))
            p = model("play", mat, pk)
            i = 0
            for i in range(feel[6] + 5):
                p.step(K.K_GRIP)
                if not p.gvx:
                    break
            if not p.gvx and not p.nfall and not [e for e in p.events if e[0] != "corner"] \
                    and i + 1 == feel[6]:
                return pk, (x, y), i + 1
    return None


def w6b_replays():
    """wave 6b's replays (SPEC.md 128.17.4, 128.17.10 bonanzaphys): the boost ARMED
    by a second Space edge anywhere in the Hop's flight, and the LATE GRACE that
    converts an unarmed bouncing first contact; the accidental cases; Grip 6/3/1.
    Each FOUND and PROVED on the model (every contact searched, so a retuned
    constant re-finds it; every expected value the model's, never a literal,
    SPEC.md 128.16.11), each red arm's broken model shown to part.  Each carries
    `nboost`, the boosts the guest must end the replay with"""
    S = []
    R_, ST = BB.MAT_RUBBER, BB.MAT_STEEL

    def add(name, crs, mat, poke, keys, what, ok, red=None, nboost=None):
        S.append({"name": name, "crs": crs, "mat": mat, "poke": poke, "keys": keys, "what": what,
                  "ok": bool(ok), "red": red, "nboost": nboost})
    pc = R.course("play")
    start = BB.Grid(pc.cga, pc.wcga).start
    rest = pl_poke("play", start, R_)
    HOP = 3                                     # the Hop's one-step press, from rest on the apron
    base = [0] * HOP + [K.K_HOP] + [0] * 90
    _p, cs = run_ix("play", R_, rest, base)
    c = first_after(cs, HOP)                    # its first contact's key index (a bounce: no second press)

    def boosts(p):
        return [e for e in p.events if e[0] in ("boost", "boostg")]

    # armearly: the second press 14 steps before the first contact, which wave 6's window (6 steps,
    # closing on the contact) refused: a boost
    keys = with_space(base, c - 14 if c else None)[:(c or 0) + 30]
    p, cs2 = run_ix("play", R_, rest, keys)
    add("armearly", "play", R_, rest, keys, "a Hop on the apron, the second press 14 steps before its first "
        "contact (step %s): %s, nboost %d" % (c, [k_ for _i, k_ in cs2][:1], p.nboost),
        c and c - 14 > HOP + 1 and [k_ for _i, k_ in cs2][:1] == ["boost"] and p.nboost == 1,
        red={"_armwin": True}, nboost=1)
    # armroll: rubber at the cap with a chord, a Hop, a second press MID-FLIGHT: a boost (128.17.4.1: rolling
    # does not change the physics on the apron; the searched take-off's first contact passes rules 3 - 5)
    found = None
    for d in ((1, 0), (-1, 0), (0, -1), (0, 1)):
        dk = BB._PLAY_DIRK[d]
        for at in ((start[0] + i * d[1], start[1] + i * d[0]) for i in (0, -2, 2, -4, 4)):
            pk = pl_poke("play", at, R_, d)
            for a in range(0, 12):
                kb = with_space([dk] * 90, a)
                _q, csr = run_ix("play", R_, pk, kb)
                cr = first_after(csr, a)
                if cr is None or cr - a < 12:
                    continue
                mid = (a + cr) // 2
                keys = with_space(kb, mid)[:cr + 30]
                p, cs2 = run_ix("play", R_, pk, keys)
                if [k_ for _i, k_ in cs2][:1] == ["boost"] and p.nboost == 1 and not p.nfall \
                        and parts("play", R_, pk, keys, _armwin=True):
                    found = (pk, keys, at, d, a, cr, mid)
                    break
            if found:
                break
        if found:
            break
    pk, keys, at, d, a, cr, mid = found if found else (rest, [0], None, None, None, None, None)
    add("armroll", "play", R_, pk, keys, "rubber at the cap from %s along %s with the chord, a Hop at step %s, "
        "the second press mid-flight at %s, the first contact at %s: a boost" % (at, d, a, mid, cr), found,
        red={"_armwin": True}, nboost=1)
    # armlate: the press 2 steps AFTER the unarmed first contact (a bounce that opened the grace): the grace
    # CONVERTS the rebound - the boost at k = 2, the lift bgd x 1 that `graceoff` leaves out
    keys = with_space(base, c + 2 if c else None)[:(c or 0) + 40]
    p, cs2 = run_ix("play", R_, rest, keys)
    bg = [e for e in p.events if e[0] == "boostg"]
    add("armlate", "play", R_, rest, keys, "a Hop, a bounce at its first contact (step %s), Space 2 steps later: "
        "%s" % (c, bg[:1]), c and [k_ for _i, k_ in cs2][:1] == ["bounce"] and len(bg) == 1 and bg[0][2] == 2
        and p.nboost == 1, red=[{"_nograce": True}, {"_graceoff": True}], nboost=1)
    # armlate5: the press BGRACE + 1 steps after it: past the grace, nothing (a grace one longer, `grace5`,
    # converts).  (armlate4 until round 3's BGRACE 4, SPEC.md 128.17.16)
    late = BB.BGRACE + 1
    keys = with_space(base, c + late if c else None)[:(c or 0) + 40]
    p, cs2 = run_ix("play", R_, rest, keys)
    add("armlate5", "play", R_, rest, keys, "the press %d steps after the first contact (step %s): nboost %d" % (
        late, c, p.nboost), c and not boosts(p) and p.nboost == 0, red={"_grace5": True}, nboost=0)
    # hoponly: one tap and nothing else: no boost (the grace opens, unused)
    keys = base[:(c or 0) + 40]
    p, cs2 = run_ix("play", R_, rest, keys)
    add("hoponly", "play", R_, rest, keys, "a single tap, no second press: %s, nboost %d" % (
        [k_ for _i, k_ in cs2][:1], p.nboost), c and p.nboost == 0 and [k_ for _i, k_ in cs2][:1] == ["bounce"],
        red={"_hopedge": True}, nboost=0)
    # armheld: Space HELD from the Hop through the contact and 3 steps past it: round 3 (SPEC.md 128.17.16)
    # BOOSTS at the contact, the floor level with the take-off (`noheld`: none).  Round 2's was nboost 0
    keys = [k_ | (K.K_HOP if HOP <= i <= (c or 0) + 3 else 0) for i, k_ in enumerate(base)][:(c or 0) + 40]
    p, cs2 = run_ix("play", R_, rest, keys)
    add("armheld", "play", R_, rest, keys, "Space held from the Hop (step %d) through the contact (%s) and 3 "
        "steps past: %s, nboost %d" % (HOP, c, [k_ for _i, k_ in cs2][:1], p.nboost),
        c and p.nboost == 1 and [k_ for _i, k_ in cs2][:1] == ["boost"], red={"_noheld": True}, nboost=1)
    # ledgehold: a Hop at the LIP of the PLAYGROUND's half-unit rung at the cap, Space held 4 steps, its first
    # contact on the ledge 1 - 4 steps later: no boost there (`heldarm` boosts on the ledge, 128.17.4.4)
    top, rr = play_rect(0.5)
    st_ = ((rr[0] + rr[2] - 1) // 2, BB.PLAY_FRONT)
    dk = BB._PLAY_DIRK[(0, -1)]
    pk = pl_poke("play", st_, R_, (0, -1))
    found = None
    for a in range(BB.LAD_PTS):
        land = BB._play_contact(pc, R_, st_, (0, -1), a)
        if land is None or not 1 <= land - a <= 4:
            continue
        keys = [dk | (K.K_HOP if a <= i <= max(a + 3, land) else 0) for i in range(land + 40)]
        p, cs2 = run_ix("play", R_, pk, keys)
        q = model("play", R_, pk)
        for i in range(land + 1):
            q.step(keys[i])
        if (q.gx >> 12, q.gy >> 12) not in top or p.nboost or p.nfall:
            continue
        ph, _c = run_ix("play", R_, pk, keys, _heldarm=True)
        if ph.nboost:
            found = (keys, a, land)
            break
    keys, a, land = found if found else ([0], None, None)
    if found and not parts("play", R_, pk, keys, _nogate=True):
        found = None                            # (round 3: `nogate`, held without the take-off gate, must boost)
    add("ledgehold", "play", R_, pk if found else rest, keys, "a Hop at the half-unit lip %s (take-off point %s), "
        "Space held through its first contact on the ledge at %s: no boost (the ledge is above the "
        "take-off, round 3's gate)" % (rr, a, land), found,
        red=[{"_heldarm": True}, {"_nogate": True}], nboost=0)
    # fallarm / fallnone (round 3, SPEC.md 128.17.16): rubber ROLLED off a rung's top onto the apron, no Hop;
    # a tap 2 steps after the take-off arms the FALL's token, and the first contact boosts (`nofall`: none).
    # With no Space the contact opens the grace and nothing else
    found3 = None
    for H in (1, 0.5, 1.5):
        top3, r3 = play_rect(H)
        for x in range(r3[0], r3[2]):
            for y in range(r3[1], r3[3]):
                for v in (BB.VMAXG, 224, 160):
                    pk3 = pl_poke("play", (x, y), R_, (0, 1), v)
                    kb = [BB._PLAY_DIRK[(0, 1)]] * 80
                    q, _cs = run_ix("play", R_, pk3, kb)
                    off = next((e[1] - 1 for e in q.events if e[0] == "takeoff"), None)
                    if off is None or q.nhop or q.nfall or q.nboost:
                        continue
                    keys = with_space(kb, off + 2)
                    p, cs3 = run_ix("play", R_, pk3, keys)
                    if p.nhop or p.nfall or [k_ for _i, k_ in cs3][:1] != ["boost"] or p.nboost != 1:
                        continue
                    if not parts("play", R_, pk3, keys, _nofall=True):
                        continue
                    cf = first_after(cs3, off)
                    found3 = (pk3, keys, kb, (x, y), H, v, off, cf)
                    break
                if found3:
                    break
            if found3:
                break
        if found3:
            break
    pk3, keys, kb, at3, H3, v3, off3, cf3 = found3 if found3 else (rest, [0], [0], None, None, None, None, None)
    add("fallarm", "play", R_, pk3, keys[:(cf3 or 0) + 30], "rubber rolled off the %s-unit top at %s at %s, no "
        "Hop; the take-off at step %s, a tap 2 steps later, the first contact at %s: a boost" % (
            H3, at3, v3, off3, cf3), found3, red={"_nofall": True}, nboost=1)
    q, cs3 = run_ix("play", R_, pk3, kb[:(cf3 or 0) + 30])
    add("fallnone", "play", R_, pk3, kb[:(cf3 or 0) + 30], "the same roll with no Space: %s, nboost %d" % (
        [k_ for _i, k_ in cs3][:1], q.nboost), found3 and q.nboost == 0 and not q.nhop, nboost=0)
    # mashchain: rubber at the cap with a chord (armroll's), Space tapped every 2 steps from its Hop through the
    # chain's first three contacts: ONE boost (the token one a chain; `pump` re-arms it at every contact Hop)
    found2 = None
    for d in ((1, 0), (-1, 0), (0, -1), (0, 1)):
        dk = BB._PLAY_DIRK[d]
        for at in ((start[0] + i * d[1], start[1] + i * d[0]) for i in (0, -2, 2, -4, 4)):
            pk = pl_poke("play", at, R_, d)
            for a in range(0, 12):
                kb = [dk | (K.K_HOP if i >= a and (i - a) % 2 == 0 else 0) for i in range(160)]
                p, cs2 = run_ix("play", R_, pk, kb)
                if len(cs2) < 3 or p.nfall:
                    continue
                n3 = cs2[2][0]
                keys = [k_ & ~K.K_HOP if i > n3 else k_ for i, k_ in enumerate(kb)][:n3 + 40]
                p, cs2 = run_ix("play", R_, pk, keys)
                if p.nboost == 1 and not p.nfall and [k_ for _i, k_ in cs2][:1] == ["boost"] \
                        and parts("play", R_, pk, keys, _pump=True):
                    found2 = (pk, keys, at, d, a, [k_ for _i, k_ in cs2][:4])
                    break
            if found2:
                break
        if found2:
            break
    pk, keys, at, d, a, kinds = found2 if found2 else (rest, [0], None, None, None, None)
    add("mashchain", "play", R_, pk, keys, "rubber at the cap from %s along %s, Space tapped every 2 steps from "
        "the Hop (step %s) through three contacts %s: one boost" % (at, d, a, kinds), found2,
        red={"_pump": True}, nboost=1)
    # gripchain (re-keyed for 6b, SPEC.md 128.17.4.4): a Hop and a MID-FLIGHT tap - the boost; Grip held through
    # the boost's landing; a Hop off it and a mid-flight tap - the second boost, about 52 steps on
    base2 = [0] * HOP + [K.K_HOP] + [0] * 220
    keys = with_space(base2, (HOP + c) // 2 if c else None)
    _p, cs2 = run_ix("play", R_, rest, keys)
    L1 = first_after(cs2, HOP)
    _p, cs2 = run_ix("play", R_, rest, [k_ | (K.K_GRIP if i > L1 else 0) for i, k_ in enumerate(keys)])
    L2 = first_after(cs2, L1)
    keys = [k_ | (K.K_GRIP if L1 < i <= L2 else 0) for i, k_ in enumerate(keys)]
    keys = with_space(keys, L2 + 1)
    _p, cs2 = run_ix("play", R_, rest, keys)
    L3 = first_after(cs2, L2 + 1)
    keys = with_space(keys, (L2 + 1 + L3) // 2 if L3 else None)[:(L3 or 0) + 30]
    p, cs2 = run_ix("play", R_, rest, keys)
    ev = [e[0] for e in p.events if e[0] in ("hop", "boost", "land", "bounce", "hopc")]
    bst = [e[1] for e in p.events if e[0] == "boost"]
    add("gripchain", "play", R_, rest, keys, "Hop, a mid-flight tap, boost (%s), Grip through its landing (%s), Hop "
        "(%s), a mid-flight tap, boost (%s): %s; the cycle %s steps" % (
            L1, L2, L2 + 1, L3, ev[:6], bst[1] - bst[0] if len(bst) == 2 else None),
        p.nboost == 2 and ev[:5] == ["hop", "boost", "land", "hop", "boost"], nboost=2)
    # gripsteel: steel at the cap, Grip held (Grip 3): stopped in the axis model's steps
    gs = grip_stop(ST)
    pk, at, n = gs if gs else (rest, None, None)
    sf = BB.axis_feel(ST)
    add("gripsteel", "play", ST, pk, [K.K_GRIP] * (sf[6] + 20), "steel at the cap at %s, Grip held: stopped in %s "
        "steps (%.1f tiles), the axis model's %d" % (at, n, sf[7], sf[6]), gs)
    # wave 7 (SPEC.md 128.18.4): TIMEOUT - rubber left at rest on FIRST's start past its limit: the clock counts
    # down 55 steps a second, and the limit's last step times the replay out (the guest's run ends there;
    # `toutoff` runs on, and its state differs at that frame)
    fc = R.course("first")
    lim = fc.limit * BB.SEC_STEPS
    keys = [0] * (lim + 40)
    p, _cs = run_ix("first", R_, None, keys)
    q = model("first", R_, None)
    for k_ in keys[:lim - 1]:
        q.step(k_)
    add("timeout", "first", R_, None, keys, "rubber at rest on FIRST, limit %d s (%d steps): the timeout at step %s, "
        "the clock %s then" % (fc.limit, lim, p.nstep if p.tout else None, p.tsec), fc.limit and p.tout
        and p.nstep == lim and p.tsec == 0 and not q.tout and q.tsec == 1, red={"_toutoff": True}, nboost=0)
    # wave 8b (SPEC.md 128.19.4): SEVERAL FINISHES - TRIAL's goal column split, (8, 17) exit 0 and (8, 18)
    # exit 1: rolled into each from the sand, the guest's bz_exit the model's every frame and at the end
    for nm, at, want in (("exit1", (9, 18), 1), ("exit0", (9, 17), 0)):
        pk = pl_poke("trial", at, R_, d=(-1, 0), v=BB.VMAXG // 2)
        keys = [CHORD_MX] * 40
        p, _cs = run_ix("trial", R_, pk, keys)
        add(nm, "trial", R_, pk, keys, "rubber rolled from %s into TRIAL's goal column: finished at step %s through "
            "exit %d (want %d)" % (at, p.nstep if p.goal else None, p.exit, want), p.goal and p.exit == want
            and not p.nfall, nboost=0)
    return S


def drag_span(g, s):
    """SPEC.md 128.16.14: bz_gax's every DRAGGED call (CL, the drag shift, not 0)
    on the replay S, entry to return, in MartyPC's cycles: the worst at most
    DRAG_PRICE x DRAG_SLACK.  -> (failures, (calls, worst, mean))"""
    m = g.m
    log = R.make_log(s["keys"], R.CRS_K[s["crs"]], s["mat"])
    m.pause()
    g.write_log(log)
    wk = R.Walker(g, t0=True)
    m.bp_exec(wk.t0)
    m.run()
    g.key("KeyR")
    assert m.wait_stop(60) == "breakpoint", "R did not start the replay (the drag's span)"
    if s["poke"]:
        pk = s["poke"]
        R.poke_ball(g, pk["gx"], pk["gy"], pk["gz"], pk["gvx"], pk["gvy"], pk["gvz"], air=pk["air"],
                    ztop=pk["ztop"], lvl=pk["lvl"])
    gax = g.a("bz_gax")
    # (the review's C2: the kernel's int 08h handler, 54.6 Hz under FSXF_FASTTICK, adds its whole cost to a
    # span it lands in - bonanzaperf's lesson - so a span with an sch_isr entry inside it is counted apart
    # and only the CLEAN spans are held to the price)
    irq = m.sym("sch_isr")
    rets, spans, t0, cl, dirty, ntick = set(), [], None, 0, False, 0
    m.bp_exec(gax, wk.t0, irq)
    while True:
        m.run()
        assert m.wait_stop(60) == "breakpoint", "the replay stopped reaching bz_gax"
        r = m.regs()
        at = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
        cyc = m.status()["cycles"]
        if at == irq:
            dirty = t0 is not None
            continue
        if at == wk.t0:
            if g.b("bz_goal") or g.b("bz_tout") or not (g.b("bz_rn") or g.w("bz_rruns")):
                break
            continue
        if at == gax:
            ret = ((r["cs"] << 4) + struct.unpack("<H", bytes(m.read(((r["ss"] << 4) + r["sp"]) & 0xFFFFF, 2)))[0]) \
                & 0xFFFFF
            if ret not in rets:
                rets.add(ret)
                m.bp_exec(gax, wk.t0, irq, *sorted(rets))
            t0, cl, dirty = cyc, r["cx"] & 0xFF, False
            continue
        if at in rets and t0 is not None:
            if cl:
                if dirty:
                    ntick += 1
                else:
                    spans.append(cyc - t0)
            t0, dirty = None, False
    m.bp_exec()
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 0, "the drag's span replay to end", guest=60)
    dropped(g, "the drag's span")
    fails = []
    bound = int(DRAG_PRICE * DRAG_SLACK)
    if not spans:
        fails.append("%s: the drag's span: no CLEAN dragged bz_gax call measured (%d with a tick inside)"
                     % (s["name"], ntick))
    elif max(spans) > bound:
        fails.append("%s: the drag's span: the worst dragged bz_gax call took %d cycles, over its price %d + 25%% "
                     "(%d; SPEC.md 128.16.3.1)" % (s["name"], max(spans), DRAG_PRICE, bound))
    out = (len(spans), max(spans) if spans else None, sum(spans) / len(spans) if spans else None)
    print("%s the drag's span on %s: %d clean dragged bz_gax calls (%d more with a tick inside, left out), worst "
          "%s cycles, mean %s (bound %d): %s" % (
        g.tag, s["name"], out[0], ntick, out[1], "%.0f" % out[2] if out[2] else None, bound,
        "yes" if not fails else "NO"), flush=True)
    return fails, out


def prove(S):
    """the host's proof of each scenario: -> failure lines (empty: all proved)"""
    bad = []
    for s in S:
        if not s["ok"]:
            bad.append("replay %s: the model does not show what the scenario is for (%s)" % (s["name"], s["what"]))
        for red in (s["red"] if isinstance(s["red"], list) else [s["red"]] if s["red"] else []):
            at = parts(s["crs"], s["mat"], s["poke"], s["keys"], s.get("tilts"), **red)
            if at is None:
                bad.append("replay %s: the broken model %s never parts from the model over its %d steps: the "
                           "scenario cannot catch its red arm" % (s["name"], red, len(s["keys"])))
            else:
                s["parts_at"] = min(at, s.get("parts_at") or at)
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
              (6, 5) != BB.Grid(first.cga, first.wcga).start, "lip": "takeoff" in kinds and "bounce" in kinds,
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
    if s.get("tilts"):
        log = BB.encode_log(s["keys"], course=R.CRS_K[s["crs"]], mat=s["mat"], ident=R.course(s["crs"]).ident,
                            tilts=s["tilts"])
    else:
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
        for k_, v in (pk.get("extra") or {}).items():   # wave 4: the ball's state (a stun, a shatter)
            g.putb("bz_" + k_, v)
        if pk.get("recpoke"):                   # ...and a prop record's field, in the course part
            i, fld, v = pk["recpoke"]
            off = {"gvz": 16}[fld]              # bzcourse.inc BZP_SGVZ
            at = (g.w("bz_cseg") << 4) + g.w("bz_poff") + BB.PROPREC * i + off
            g.m.write(at, struct.pack("<H", v))
    Wc, rl = g.w("bz_W"), R.RL[tag]
    win = (g.w("bz_R0"), g.w("bz_c0"))
    wk.arm()
    frames, cuts = 0, []
    while not fails:
        k = wk.next()
        if k == "t0":
            win = (g.w("bz_R0"), g.w("bz_c0"))
            if g.b("bz_goal") or g.b("bz_tout") or not (g.b("bz_rn") or g.w("bz_rruns")):
                break                           # the replay's end: this bz_t0 leaves the bracket (wave 7: a timeout too)
            continue
        if k != "pr":
            continue
        frames += 1
        st, s2, ext = rd.read()
        ev = advance(p, st[0], s["keys"], s.get("tilts"))
        bad = compare(name, frames, st, s2, ext, p)
        if not bad and s.get("tables"):
            bad = compare_tables(name, frames, rd.tables(), p)
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
        advance(p, st[0], s["keys"], s.get("tilts"))
        end = len(s["keys"]) if not (p.goal or p.tout) else p.nstep
        if st[0] != end:
            fails.append("%s: the replay ended after step %d, its log holds %d%s" % (
                name, st[0], len(s["keys"]), " (the goal at %d)" % p.nstep if p.goal else ""))
        bad = compare(name + " (its end)", frames, st, s2, ext, p)
        if bad:
            fails.append(bad)
        if s.get("nboost") is not None and ext.get("s6") is not None and ext["s6"][2] != s["nboost"]:
            fails.append("%s: the replay ended with nboost %d, the scenario's %d (SPEC.md 128.17.4)" % (
                name, ext["s6"][2], s["nboost"]))
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
                if s.get("span") and "bz_dmask" in g.sym:     # wave 6: the drag's cost, ASSERTED
                    fails += drag_span(g, s)[0]
    return fails, outs


SLOPE_X = ("    mov ax, [bz_tsx]            ; gvx += arrows - BZ_GSL sx; drag; brake; clamp\n"
           "    shl ax, 1                   ; (C's slopes: bz_win9f's, 0 off a plane floor)\n"
           "    shl ax, 1\n    neg ax\n")
SLOPE_Y = "    mov ax, [bz_tsy]            ; gvy the same with sy\n    shl ax, 1\n    shl ax, 1\n    neg ax\n"
REDS = {
    "slope": [("bzphys.inc", SLOPE_X, SLOPE_X.replace("    neg ax\n", "")),
              ("bzphys.inc", SLOPE_Y, SLOPE_Y.replace("    neg ax\n", ""))],
    # (DI kept: .resp holds bz_nfall's address in it for .rdone's count, and an
    # arm that clobbered it also bumped a word of the package at the grid's
    # offset - harmless at BZC1's, a hung frame loop at BZC2's: 5b's final pass)
    "respawn": [("bzphys.inc", "    jnz .rflag\n    call bz_place\n",
                 "    jnz .rflag\n    push di\n    mov di, [bz_goff]           ; RED respawn: on the start, not bz_safe\n"
                 "    mov al, [es:di + BZG_WX]\n    mov ah, [es:di + BZG_WY]\n    mov [bz_safe], ax\n"
                 "    pop di\n    call bz_place\n")],
    # (steps 4 - 6 are written once and run by wave 2's path and the prop path
    # alike, SPEC.md 128.13.8: the patch breaks both)
    "takeoff": [("bzphys.inc", ".takeoff:                       ; over no floor: no bz_gh (bz_ghv cleared)\n"
                 "    call bz_toff                ; (round 3: a FALL's token too, bz_toff's)\n",
                 ".takeoff:                       ; over no floor: no bz_gh (bz_ghv cleared)\n"
                 "    mov word [bz_gvz], 0        ; RED takeoff\n    call bz_toff\n"),
                ("bzphys.inc", "    jle .launch\n    mov ax, bx                  ; z = h: the ball follows the floor\n",
                 "    jg .redf\n    mov word [bz_gvz], 0        ; RED takeoff: off a falling floor too\n"
                 "    jmp short .launch\n.redf:\n    mov ax, bx\n")],
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
    "gate": [("fam/rotor.asm", "    mov ax, [bz_nstep]\n    add ax, [es:si + BZP_SEED]\n    and al, [es:si + BZP_MASK]\n"
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
    "exit": [("fam/bztube.inc", "    mov cl, [es:si + BZP_TDIR]  ; 0 +x, 1 -x, 2 +y, 3 -y\n",
              "    mov cl, [es:si + BZP_TDIR]  ; 0 +x, 1 -x, 2 +y, 3 -y\n"
              "    cmp byte [es:si + BZP_KIND], BZ_PK_WINDMILL ; RED exit: along the entry\n    jne .redx\n"
              "    mov cl, [es:si + BZP_TGVX]  ; (the doorway: 0 -x, 1 -y -> codes 1, 3)\n    shl cl, 1\n"
              "    inc cl\n.redx:\n")],
    # wave 4 (SPEC.md 128.14.14): the respawn at bz_safe on a CKPT course
    "ckpt": [("bzphys.inc", "    test byte [bz_gfl], BZ_GF_CKPT\n    jnz .rflag\n",
              "    nop                         ; RED ckpt: bz_safe on every course\n")],
    # the flag's ball taken from the ball that touched it
    "ckmat": [("bzphys.inc", "    mov al, [es:si + BZP_CBALL] ; the FLAG's ball, not the one it was\n",
               "    mov al, [bz_mat]            ; RED ckmat: the touching ball\n")],
    # ftg not rebuilt at a swap
    "padftg": [("bzphys.inc", "    mov al, [bz_surf]\n    call bz_surfset\n",
                "    nop                         ; RED padftg: ftg kept\n")],
    # the capture without the speed test: every entering ball holes out
    "cupv": [("bzphys.inc", "    cmp ax, [es:si + BZP_UCAP]\n    ja .lip\n",
              "    cmp ax, [es:si + BZP_UCAP]\n    nop                         ; RED cupv: no speed test\n")],
    # the spring ADDS to the rebound (and nothing caps it)
    "springsum": [("fam/spring.asm", ".s0:\n    cmp ax, [es:si + BZP_SGVZ]\n    jge .s1\n    mov ax, [es:si + BZP_SGVZ]\n.s1:\n"
                   "    cmp ax, BZ_VZMAX\n    jle .s2\n    mov ax, BZ_VZMAX\n.s2:\n",
                   ".s0:\n    add ax, [es:si + BZP_SGVZ]  ; RED springsum: the sum\n.s2:\n")],
    # the min before the decay: a level above the cap drops to it at once
    "tiltcap": [("bzphys.inc", "    sub al, 2                   ; above the cap: max(c, lvl - 2)\n",
                 "    mov al, ah                  ; RED tiltcap: to the cap at once\n    jmp short .tst\n")],
}
# wave 9 (SPEC.md 128.25.7.1): the RESPAWN class ignored - the respawn never calls bz_frst, so a RETURN
# leaves the probe's TOUCHED bit set (the `probe` replay's bz_fst parts from the model's)
REDS["famrsp"] = [("bzphys.inc", "    call bz_frst                ; the place, whose refill runs the CELL hook\n",
                   "    nop                         ; RED famrsp: the RESPAWN class ignored\n    nop\n    nop\n")]
RED_LEGS = {"slope": ("bench",), "respawn": ("scen",), "takeoff": ("scen",)}
RED_ONLY = {"respawn": ("pit",), "takeoff": ("lip",), "bounce": ("bounce",), "edge": ("eastwall",),
            "stun": ("stun",), "shatter": ("shatter",), "absimpact": ("ramphop",), "airwall": ("stepup",),
            "gate": ("knock",), "kick": ("kick",), "carry": ("hop",), "carrys": ("ride",), "stick": ("hop",),
            "exit": ("keep",), "ckpt": ("flag",), "ckmat": ("flagmat",), "padftg": ("padswap",),
            "cupv": ("cup",), "springsum": ("spring",), "tiltcap": ("tilt",), "famrsp": ("probe",)}
RED_WANT = {"slope": "the benchmark frame", "respawn": "pit", "takeoff": "lip", "bounce": "bounce frame",
            "edge": "eastwall frame", "stun": "stun frame", "shatter": "shatter frame",
            "absimpact": "ramphop-", "airwall": "stepup frame", "gate": "knock frame", "kick": "kick frame",
            "carry": "hop frame", "carrys": "ride frame", "stick": "hop frame", "exit": "keep frame",
            "ckpt": "flag frame", "ckmat": "flagmat-moon frame", "padftg": "padswap-",
            "cupv": "cup-lip frame", "springsum": "spring-max frame", "tiltcap": "tilt frame",
            "famrsp": "probe frame"}

# wave 6 (SPEC.md 128.16.14): the token set again by a contact Hop (a boost every other contact)
REDS["pump"] = [("bzphys.inc", ".hp:\n    mov byte [bz_hopw], 0\n    inc word [bz_nhop]\n    jmp short .leave\n",
                 ".hp:\n    mov byte [bz_hopw], 0\n    inc word [bz_nhop]\n    add ax, di                  ; RED pump: "
                 "the token set again by a contact Hop\n    mov [bz_gvz], ax\n    mov ax, [bz_gz + 1]\n"
                 "    mov [bz_ztop], ax\n    mov byte [bz_btok], 1\n    jmp short .sqr\n"),
                ("bzphys.inc", "    mov byte [bz_btok], 0       ; every contact spends the token (a boost's\n"
                 "    cmp word [bz_lvz], BZ_SQTHR ; own, .boost); the squash, but a shatter's\n",
                 "    mov byte [bz_btok], 0       ; every contact spends the token (a boost's\n.sqr:\n"
                 "    cmp word [bz_lvz], BZ_SQTHR ; own, .boost); the squash, but a shatter's\n")]
# rule 4's slope test left out: a ramp's contact boosts
REDS["rampboost"] = [("bzphys.inc", "    cmp byte [si + 1], 1        ; CF = 1 when both slopes are 0\n",
                      "    stc                         ; RED rampboost: no slope test\n")]
# the token cleared only by a boost, not at every contact
REDS["tokbst"] = [("bzphys.inc", "    mov byte [bz_btok], 0       ; every contact spends the token (a boost's\n",
                   "    nop                         ; RED tokbst: kept past a contact\n")]
# rule 4 on the cell after the slab's substitution: the slab (level, FLOOR, flags 0) boosts
REDS["slabcell"] = [("bzphys.inc", "    jz .no                      ; rule 3 (round 3b: rule 5 went, 128.17.17)\n",
                     "    jz .no                      ; rule 3 (round 3b: rule 5 went, 128.17.17)\n"
                     "    cmp byte [bz_fslab], 0      ; RED slabcell: the slab's substituted cell\n"
                     "    je .redslab\n    stc\n    ret\n.redslab:\n")]
# wave 2's round-up drag kept in the guest (no remainder)
GAX_NEW = ("    mov bx, ax\n    cwd                         ; DX = v's sign (DH keeps it below)\n"
           "    xor bx, dx\n    sub bx, dx                  ; BX = |v|: 0, no drag\n    jz .brake\n"
           "    add bl, [si]\n    adc bh, 0                   ; BX = t = |v| + rem\n"
           "    mov dl, [bz_dmask]\n    and dl, bl                  ; DL = t AND (2^k - 1), the new remainder\n"
           "    shr bx, cl                  ; BX = d = t >> k\n    jnz .d\n"
           "    inc bx                      ; d = 0: 1, and the remainder 0 (BH is 0)\n    mov dl, bh\n.d:\n"
           "    mov [si], dl\n    mov dl, dh                  ; DX = the sign again\n    xor bx, dx\n"
           "    sub bx, dx                  ; BX = d with v's sign\n"
           "    sub ax, bx                  ; v moves d toward 0 (never past it: d <= |v|)\n")
REDS["ceildrag"] = [("bzphys.inc", GAX_NEW,
                     "    mov dx, ax                  ; RED ceildrag: wave 2's ceil(|v| / 2^k), no remainder\n"
                     "    or ax, ax\n    js .dn\n    neg dx\n    sar dx, cl\n    add ax, dx\n    jmp short .brake\n"
                     ".dn:\n    sar dx, cl\n    sub ax, dx\n")]
# the remainder's split done twice more, by DIV: the same results, about 300 clocks a dragged axis more
REDS["slowdrag"] = [("bzphys.inc", "    adc bh, 0                   ; BX = t = |v| + rem\n",
                     "    adc bh, 0                   ; BX = t = |v| + rem\n"
                     "    push ax                     ; RED slowdrag: the split twice more, by DIV\n"
                     "    push dx\n    push cx\n    mov ax, 1\n    shl ax, cl\n    mov cx, ax\n"
                     "    mov ax, bx\n    xor dx, dx\n    div cx\n    mov ax, bx\n    xor dx, dx\n    div cx\n"
                     "    pop cx\n    pop dx\n    pop ax\n")]
# springoff (round 3b, SPEC.md 128.17.17; wave 6's springtok inverted): round 3's spring, its launch spends
# the token - from the ground after bz_toff, and out of the air with no bz_atok
REDS["springoff"] = [("fam/spring.asm", "    call bz_toff                ; (round 3b, 128.17.17: the launch TAKES the\n",
                      "    call bz_toff                ; (round 3b, 128.17.17: the launch TAKES the\n"
                      "    mov byte [bz_btok], 0       ; RED springoff: the spring spends the token\n"),
                     ("fam/spring.asm", "    call bz_atok                ; round 3b: a launch out of the air\n",
                      "                                ; RED springoff: no token out of the air\n")]
RED_ONLY.update({"springoff": ("springarm",)})
RED_WANT.update({"springoff": "springarm frame"})
# noadd (round 3b): round 3's boost - BOOST alone, refused by rule 5 when the rebound reaches it
REDS["noadd"] = [("bzphys.inc", "    or ax, ax\n    jz .no                      ; rule 3 (round 3b: rule 5 went, 128.17.17)\n",
                  "    cmp bp, ax                  ; RED noadd: round 3's rules 3 and 5\n    jae .no\n"),
                 ("bzphys.inc", "    mov dx, [bz_mrec + BZM_BADD] ; round 3b: AX = min(VZMAX, max(BOOST, rr\n"
                  "    add dx, bp                  ; + BADD)), the boost ADDED to the bounce\n"
                  "    cmp dx, ax\n    jbe .lv\n    xchg ax, dx\n    cmp ax, BZ_VZMAX\n    jbe .lv\n"
                  "    mov ax, BZ_VZMAX\n.lv:\n", "                                ; RED noadd: BOOST alone\n")]
# nospent (round 3b): a boost never marks itself spent, so a launch out of the air re-arms a bouncing ball
REDS["nospent"] = [("bzphys.inc", "    mov byte [bz_bsp], 1        ; round 3b: spent until the ball is grounded\n    ret\n",
                    "                                ; RED nospent\n    ret\n"),
                   ("bzphys.inc", "    mov byte [bz_bsp], 1        ; round 3b: spent until the ball is grounded\n    jmp .st\n",
                    "                                ; RED nospent\n    jmp .st\n")]
# toutoff (wave 7, SPEC.md 128.18.4): the limit's last step never times out
REDS["toutoff"] = [("bzphys.inc", "    mov byte [bz_tout], 1\n    call bz_fstart              ; (the same sequence, the clock at 0)\n.tdone:\n",
                    "                                ; RED toutoff: no timeout\n.tdone:\n")]
# clkpass (wave 7, SPEC.md 128.18.5.3): a clock's cell is not taken for a post's, so the ball rolls through it
REDS["clkpass"] = [("bzphys.inc", "    mov ah, BZ_PK_BUMPER        ; (no kick, no light), and every post rule reads\n",
                    "                                ; RED clkpass: the clock's kind left as it is\n")]
# noexit (wave 8b, SPEC.md 128.19.4): the goal's test writes no exit - red at exit1 (bz_exit 0, the model's 1)
REDS["noexit"] = [("bzphys.inc", "    mov [bz_exit], al\n    mov byte [bz_goal], 1\n    call bz_fstart              ; (a play's",
                   "                                ; RED noexit\n    mov byte [bz_goal], 1\n    call bz_fstart              ; (a play's")]
RED_ONLY.update({"noexit": ("exit1",)})
RED_ONLY.update({"noadd": ("boostfall",), "nospent": ("spentspring",), "toutoff": ("timeout",),
                 "clkpass": ("clock",)})
RED_WANT.update({"toutoff": "timeout frame"})
RED_WANT.update({"noadd": "boostfall", "nospent": "spentspring"})
# wave 6b (SPEC.md 128.17.10): the trigger and the late grace broken six ways, each red at its own replay.
# heldarm: Space HELD arms the token too (the edge path arms as shipped; the no-edge path as well)
REDS["heldarm"] = [("bzphys.inc", ".hw:\n    mov ax, [bz_bgr]            ; no edge: the window and (6b) the grace count\n",
                    ".hw:\n    test bl, BZ_K_HOP           ; RED heldarm: Space HELD arms the token too\n"
                    "    jz .hwr\n    cmp byte [bz_btok], 1\n    jne .hwr\n    inc byte [bz_btok]\n.hwr:\n"
                    "    mov ax, [bz_bgr]            ; no edge: the window and (6b) the grace count\n")]
# hopedge: the Hop's own edge arms its flight (the ground Hop sets the token to 2)
REDS["hopedge"] = [("bzphys.inc", "    jmp short .launch           ; (wave 6's TOKEN: bz_toff sets it, 128.16.4.1)\n",
                    "    call bz_toff\n    mov byte [bz_btok], 2       ; RED hopedge: the Hop's own edge arms its flight\n"
                    "    jmp .gh\n")]
# armwin: wave 6's test kept, the token AND the window open at the contact
REDS["armwin"] = [("bzphys.inc", "    cmp byte [bz_btok], 2       ; 2a. the BOOST (wave 6b, 128.17.4.2): the\n"
                   "    jne .hopc                   ; flight ARMED, and rules 3 - 5 (bz_bok, AX =\n",
                   "    cmp byte [bz_btok], 0       ; RED armwin: wave 6's token-and-window test\n"
                   "    je .hopc\n    cmp byte [bz_hopw], 0\n    je .hopc\n")]
# nograce: no late grace (an unarmed bounce opens nothing)
REDS["nograce"] = [("bzphys.inc", "    or al, [bz_mst]             ; open the late grace (.grace, out of line)\n"
                    "    jz .grace\n",
                    "    or al, [bz_mst]             ; RED nograce: the grace never opens\n")]
# grace5: a grace of BGRACE + 1 steps in the rule (its opening and the conversion's k - 1), BZ_BGRACE kept
REDS["grace5"] = [("bzphys.inc", "    mov byte [bz_bgr], BZ_BGRACE\n",
                   "    mov byte [bz_bgr], BZ_BGRACE + 1 ; RED grace5: a grace one step longer\n"),
                  ("bzphys.inc", "    mov cx, BZ_BGRACE           ; on the k-th step after its contact (AL =\n",
                   "    mov cx, BZ_BGRACE + 1       ; RED grace5: k - 1 = BGRACE + 1 - bz_bgr\n")]
# round 3 (SPEC.md 128.17.16): the held arming and the fall's token, each broken
# noheld: Space held at the contact arms nothing (round 2's rule)
REDS["noheld"] = [("bzphys.inc", "    cmp byte [bz_btok], 1       ; round 3 (128.17.16): Space HELD at the\n"
                   "    jne .armd                   ; contact ARMS the token 1, onto a floor no\n",
                   "    jmp short .armd             ; RED noheld: no held arming\n")]
# nogate: held arms without the take-off gate (onto a ledge above the take-off too)
REDS["nogate"] = [("bzphys.inc", "    cmp ax, [bz_zoff]\n    jg .armd\n",
                   "                                ; RED nogate: no take-off gate\n")]
# nofall: a fall takes off with no token (the Hop's own path through .launch keeps it)
REDS["nofall"] = [("bzphys.inc", "    call bz_toff                ; (round 3: a FALL's token too, bz_toff's)\n",
                   "    call bz_toff\n    mov byte [bz_btok], 0       ; RED nofall: no fall token (over no floor)\n"),
                  ("bzphys.inc", "    jle .launch\n    mov ax, bx                  ; z = h: the ball follows the floor\n",
                   "    jle .rfall                  ; RED nofall: a fall off a floor takes no token\n"
                   "    mov ax, bx                  ; z = h: the ball follows the floor\n"),
                  ("bzphys.inc", ".takeoff:                       ; over no floor: no bz_gh (bz_ghv cleared)\n",
                   ".rfall:\n    call bz_toff\n    mov byte [bz_btok], 0\n    jmp short .gh\n"
                   ".takeoff:                       ; over no floor: no bz_gh (bz_ghv cleared)\n")]
# graceoff: the conversion without the k - 1 lift (gz kept: the ball one bgd short a step since the contact)
REDS["graceoff"] = [("bzphys.inc", "    imul cx                     ; where the contact's boost would have it now\n"
                     "    add [bz_gz], ax\n    adc [bz_gz + 2], dx\n",
                     "                                ; RED graceoff: no k - 1 lift\n")]
RED_ONLY.update({"heldarm": ("ledgehold",), "hopedge": ("hoponly",), "armwin": ("armearly",),
                 "nograce": ("armlate",), "grace5": ("armlate5",), "graceoff": ("armlate",),
                 "noheld": ("armheld",), "nogate": ("ledgehold",), "nofall": ("fallarm",)})
RED_WANT.update({"heldarm": "ledgehold", "hopedge": "hoponly", "armwin": "armearly", "nograce": "armlate",
                 "grace5": "armlate5", "graceoff": "armlate frame", "noheld": "armheld", "nogate": "ledgehold",
                 "nofall": "fallarm"})
RED_ONLY.update({"pump": ("pumpchk",), "rampboost": ("rampnot",), "tokbst": ("bouncefirst",),
                 "slabcell": ("liftnot",), "ceildrag": ("drag",), "slowdrag": ("drag-rest",)})
RED_WANT.update({"pump": "pumpchk frame", "rampboost": "rampnot frame", "tokbst": "bouncefirst frame",
                 "slabcell": "liftnot frame", "ceildrag": "drag-rest frame", "slowdrag": "the drag's span"})


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
        # (the unicorn halves - fam_host's and the SPLIT leg's - are independent of the replays' proofs and
        # of each other: each a forked child of this process (BB.jobs_default() > 1), started first, its
        # output printed where the sequential run printed it; BB_JOBS=1 runs them here, in order)
        import bonanza_dsplit
        import bonanza_av
        import bonanza_dfield
        pool = BB._Pool(BB.jobs_default()) if BB.jobs_default() > 1 and hasattr(os, "fork") else None

        def kid(fn, *a_):
            if pool is None:
                return None, fn, a_
            return pool.start(fn, *a_), None, None

        def got(k):
            if k[0] is None:
                return k[1](*k[2])
            val, text, exc = pool.wait(k[0])
            sys.stdout.write(text)
            if exc is not None:
                raise exc
            return val
        try:
            k9 = kid(fam_host)
            kd = kid(bonanza_dsplit.check, 200)
            ka = kid(bonanza_av.check, 300)
            kf = kid(bonanza_dfield.check, 150)
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
            say9, b9 = got(k9)
            for line in say9:
                print("bonanza_phys wave 9 (unicorn): %s" % line)
            bad += b9
            for b in bad:
                print("FAIL %s" % b)
            for line in R.check_reds(REDS, "bonanza_phys"):
                print(line)
            # SPEC.md 128.24 (wave D3): the SPLIT leg's host half - the guest's split cells under unicorn
            # against the model, every step (tests/bonanza_dsplit.py; its red arms by hand, `--reds`), until
            # D5's PLAYGROUND gives this row a split course to replay on the glass
            bad += got(kd)
            for line in R.check_reds(bonanza_dsplit.REDS, "bonanza_dsplit"):
                print(line)
            # SPEC.md 128.28 (wave C3): the FIELD leg's host half, the same method (tests/bonanza_dfield.py;
            # its red arms by hand, `--reds`)
            bad += got(kf)
            for line in R.check_reds(bonanza_dfield.REDS, "bonanza_dfield"):
                print(line)
            # SPEC.md 128.29.7: AV's model in the guest - bz_occ under unicorn against bbcourse's model and the
            # part's records, every course (tests/bonanza_av.py; its red arms by hand, `--red amodel|acache|aneigh`)
            bad += got(ka)
            for line in R.check_reds(bonanza_av.REDS, "bonanza_av"):
                print(line)
        finally:
            if pool is not None:
                pool.kill()
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
