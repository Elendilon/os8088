#!/usr/bin/env python3
"""COURSE 5, KITE HILL (KITE): the sketch (wave 11's pipeline; ../KITE.md is the design sheet).  Host-only;
nothing in `make` runs it and it ships nothing.  ../penkit.py is the pen.

    python3 sketch.py [outdir]                  plan.png and iso.png
    python3 sketch.py --bbc [OUT] [--force]     the engine course (apps/bonanza/courses/kite.bbc)

A CLIMB, the first course whose finish is ABOVE its start: a hill of terraces up the screen, the WIND its one
new idea - a gust that shoves, a gust across a crumbling bridge, a THERMAL that lifts the ball up a cliff, gusts
to wait out behind windbreaks, and the GLIDE: a pit crossed on rising air, straight up the screen.  Rubber from
start to finish.  REFINED (the step after the pen-in): the layout the engine's constraints left, KITE.md
section 10.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from penkit import Pen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art as ART                         # the signs and decals (kite/art.py, ART.md): the course's `art` lines

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))

HEAD = """
# Course 5 (KITE; docs/plans/bonanza-courses/KITE.md): KITE HILL, a CLIMB - a hill of terraces up the screen
# and the WIND on it.  A gust that shoves (railed: the lesson), a gust across a CRUMBLING BRIDGE, a THERMAL
# that lifts the ball 8.5 units up a cliff, gusts waited out behind WINDBREAKS, and the GLIDE: a pit crossed
# straight up the screen on rising air, the summit across it.  Rubber from start to finish.  REFINED
# (2026-11-25, the step after the pen-in): written by docs/plans/bonanza-courses/kite/sketch.py --bbc --force
# while the layout moves.  NOT in the build yet (no BZ_COURSES entry, no pathway pad).
course KITE "Kite Hill"
guide                     # a REAL course: held to the course guide's checkable rules (G1, G3, G9 - G12)
width 96                  # 768 px: the floors run from px 112 (the summit's wing) to 656 (the breezeway's east end)
origin 528                # NOT free: the camera's lattice is 64 px of the PICTURE, and every flight is framed in
                          # the middle of its window at this origin (KITE.md section 2: 512 and 544 pass G3 too,
                          # 496 and 560 do not).  Move it by 64 or re-run --guide
ball rubber
uses wind glass           # (the crumbling bridge's cracked tiles are GLASS's kind `crack`, SPEC.md 137.25.8)
music kitehill            # its own song (2026-11-25): a 6/8 in D that climbs, each phrase a step higher (KITE.md, "The song")
palette 0                 # green, red, yellow on black: a grassy hill (LITTLE HOP's palette)
limit 90
target 60
"""

p = Pen("KITE", "Kite Hill", HEAD)
for sec, rgb in (("A", (110, 200, 110)), ("R", (150, 215, 130)), ("B", (135, 205, 120)), ("C", (235, 235, 215)),
                 ("D", (120, 190, 160)), ("S", (190, 170, 120)), ("E", (190, 150, 100)), ("F", (170, 180, 170)),
                 ("P", (120, 130, 150)), ("K", (200, 160, 110)), ("G", (235, 240, 250)), ("N", (120, 170, 120)),
                 ("H", (250, 250, 255))):
    p.col(sec, rgb)

ZA, Z1, Z3, ZG = 5, 7, 15.5, 18          # the meadow, terraces 1 - 2, terraces 3 - 4, the summit
BROW = 1                                 # the first rise tops out this far OVER the breezeway (below)

# 1. THE MEADOW: the start, with roll room, and the first rise ---------------------------------------------
p.floor("A", 48, 54, 55, 59, ZA, "A: the MEADOW, 7 x 5")
p.cut(48, 58, "left")                                # its two NEAR corners cut on the diagonal (a diagonal edge takes no
p.cut(54, 58, "down")                                # rail); the two beside the rise's foot are square and railed: one
p.guard(48, 54, 55, 58)                              # arrow held from the start slid the ball along a rail and out of a
p.guard(49, 58, 54, 59)                              # cut corner there (MEASURED on the pen-in's octagon)
p.start = (51, 57)
# THE BROW: the rise climbs 3 units to one unit OVER the breezeway, and the ball drops onto the walk.  No ball
# rolls back up a 1-unit step (SPEC.md 137.48), so a ball braked at the top and nudged back stays up there instead
# of rolling down the whole rise with the camera after it: the camera's "a dither does not pan back" (SPEC.md
# 137.17.6.5 item 4, asserted over every shipped demo) holds on a CLIMB only with it - KITE.md section 12, K13.
# (A whole unit, not the 3/4 that would do: a quarter-unit meadow costs 81 blocks and 23 masks more)
p.ramp("R", "y", 50, 48, 53, 54, Z1 + BROW, ZA, "R: the first rise, 3 units in 6 tiles, 3 wide, to a BROW a unit over the walk")
# 2. THE BREEZEWAY (terrace 1): the wind's LESSON - a gust across a wide walk, the downwind edge RAILED --------
p.floor("B", 39, 45, 53, 48, Z1, "B: the BREEZEWAY, 14 x 3, walked up-left (-x)")
p.floor("N", 46, 44, 47, 45, Z1, "the lesson's fan, in a notch on the upwind side")
p.blower(46, 44, "+y", (44, 45, 48, 47), 10, gust=(64, 64), flag=True)
p.guard(42, 47, 50, 48, sides=["+y"])                # the lesson's rail: the gust only leans the ball on it (it stops a
                                                     # tile short of the rise: the pen-in's ran across the rise's west lane)
p.guard(42, 45, 46, 46, sides=["-y"])                # ... and one upwind, either side of the fan's notch: a ball
p.guard(47, 45, 51, 46, sides=["-y"])                # leaning into the gust rolls that way when the calm comes
p.guard(46, 44, 47, 45, sides=["-x", "-y", "+x"])
p.guard(39, 45, 40, 48, sides=["-x"])                # the walk's end (the turn onto the bridge)
p.guard(51, 45, 53, 46, sides=["-y"])                # ... and its EAST end, a railed pocket at the top of the rise: a ball
p.guard(52, 45, 53, 48, sides=["+x"])                # that comes over the brow with the arrows still held bumps it and turns
# 3. THE GUST BRIDGE: five CRUMBLING tiles, 1 wide, a gust across them ------------------------------------------
for y in range(40, 45):
    p.floor("C", 40, y, 41, y + 1, Z1, "C: the crumbling bridge")
    p.crack(40, y)
p.float(40, 40, 41, 45, 0.5)
p.floor("N", 38, 42, 39, 43, Z1, "the bridge's fan, on a lone pillar upwind (one void cell off the bridge)")
# seed 80: the demo's ball reaches the bridge 0.4 s after a gust ends (the route demo crosses in the calm)
p.blower(38, 42, "+x", (39, 40, 41, 44), 8, gust=(64, 192), seed=80)
p.flag(40, 46, name="flag 0")                        # G20: just before what kills
# 4. THE FAN PLAZA (terrace 2) and THE THERMAL: 8.5 units up the cliff on rising air ---------------------------
# The cliff is terrace 3's +x face, on the plaza's west side: the ball crosses the plaza up-LEFT to it, rises,
# and lands going up-left - the way the next leg goes.  Coming up the bridge the ball moves right on the screen,
# so the flight's drift left stays in the middle of the camera's band (G3).  The rising air is the plaza's whole
# west strip, 2 x 5, between the plaza's two railed ends: a ball that slides along the cliff stays in it.
p.floor("D", 37, 35, 42, 40, Z1, "D: the FAN PLAZA, 5 x 5, under the cliff")
p.cut(41, 35, "right")
p.cut(41, 39, "down")
p.guard(37, 35, 41, 36, sides=["-y"])
p.guard(41, 36, 42, 39, sides=["+x"])
p.guard(37, 39, 40, 40, sides=["+y"])                # (open at x 40: the bridge comes in there)
p.blower(38, 37, "up", (37, 35, 38, 39), 40, top=9, lift=True)
p.floor("S", 32, 35, 37, 40, Z3, "S: terrace 3, the cliff's top (its +x face is the cliff, 8.5 units)")
p.guard(32, 35, 37, 36, sides=["-y"])                # the cliff's own edge is OPEN: the ball lands anywhere along it
p.guard(32, 39, 37, 40, sides=["+y"])
p.guard(32, 35, 33, 37, sides=["-x"])
p.guard(32, 39, 33, 40, sides=["-x"])
# 5. THE WINDBREAKS: a 2-wide bridge in a hard gust, two railed SHELTERS, each 2 tiles ------------------------
p.floor("E", 21, 37, 32, 39, Z3, "E: the WINDBREAK bridge, 11 x 2, walked up-left (-x)")
p.float(21, 37, 32, 39, 1)
for sx in (28, 24):
    p.guard(sx, 38, sx + 2, 39, sides=["+y"])        # a SHELTER: its downwind edge railed, 2 tiles
p.floor("N", 27, 35, 28, 36, Z3, "the windbreaks' fan, on a lone pillar upwind")
# seed 48: the demo's ball, on the upwind lane, takes one shove and stays on the bridge
p.blower(27, 35, "+y", (22, 36, 31, 38), 12, gust=(24, 104), seed=48)
p.flag(34, 37, name="flag 1")
# 6. THE LAUNCH PLAZA (terrace 4) and THE GLIDE: a pit crossed on rising air, STRAIGHT UP THE SCREEN ----------
# The plaza is a diamond on the screen: the windbreaks come in at its bottom, flag 2 is its middle, and its top
# corner is open.  One arrow (Up) from the flag rolls the ball off that corner: it sinks, the air catches it,
# and it lands 2.5 units higher on the summit's corner, straight above - no pan across at all (G3).  The pit has
# ground on its three far sides (the summit's WING, the rope walk's top, the rope walk's ramp): only a ball
# steered BACK falls.
p.floor("F", 16, 34, 21, 39, Z3, "F: the LAUNCH PLAZA, 5 x 5, a diamond on the screen")
p.guard(16, 35, 17, 39, sides=["-x"])                # (open: the corner tile's two outer edges, and (17, 34): the walk)
p.guard(16, 38, 21, 39, sides=["+y"])
p.guard(18, 34, 21, 35, sides=["-y"])
p.guard(20, 34, 21, 37, sides=["+x"])
p.floor("P", 14, 32, 15, 33, Z3 - 3, "P: the glide's fan, on a pillar in the middle of the pit, 3 units down")
p.blower(14, 32, "up", (11, 29, 16, 34), 40, top=7)  # (no `lift`: the corner tile is in it, and is not a launch pad)
p.flag(18, 36, name="flag 2")
# THE ROPE WALK: the glide's other answer (G22) - 1 wide round the pit's east and north sides, railed on its
# OUTER edge alone: a ball that slips off the inner one falls into the rising air and is carried up
p.ramp("K", "y", 17, 29, 18, 34, ZG, Z3, "the ROPE WALK: 1 wide round the pit, 2.5 units up in 5 tiles")
p.floor("K", 11, 28, 18, 29, ZG, "the rope walk's top: along the pit's far side to the summit")
p.float(17, 28, 18, 34, 0.5)
p.float(11, 28, 17, 29, 0.5)
p.guard(17, 28, 18, 34, sides=["+x"])
p.guard(11, 28, 18, 29, sides=["-y"])
# 7. THE SUMMIT ------------------------------------------------------------------------------------------
p.floor("G", 4, 22, 11, 29, ZG, "G: the SUMMIT, 7 x 7")
p.cut(4, 22, "up")
p.guard(5, 22, 11, 23, sides=["-y"])
p.guard(4, 23, 5, 29, sides=["-x"])
p.guard(10, 22, 11, 28, sides=["+x"])                # (open at y 28: the rope walk's top comes in there)
p.guard(4, 28, 9, 29, sides=["+y"])
p.floor("G", 9, 29, 11, 35, ZG, "the summit's WING: the pit's west side, a landing for a ball that drifts left")
p.guard(9, 29, 10, 35, sides=["-x"])
p.guard(9, 34, 11, 35, sides=["+y"])
p.floor("H", 6, 24, 9, 27, ZG + 0.5, "the CROWN: half a unit up (every ball rolls up it), the goal on it")
p.goal(6, 24, 9, 27, ZG + 0.5)

# the clocks are WINDSOCKS (the owner's pick, 2026-11-25: kite/CLOCKS.md; SPEC.md 137.18.5.2): the wind fills the
# sock up the hill - limp, half out, straight, taut
p.clock(54, 55, ZA, "start: limp", frame="sock1")
p.clock(41, 37, Z1, "plaza: half out", frame="sock2")
p.clock(16, 38, Z3, "launch: straight out", frame="sock3")
p.clock(7, 22, ZG, "summit: taut", frame="sock4")

p.comment("ART (docs/plans/bonanza-courses/kite/art.py draws the files and places them: ART.md)")
for _ln in ART.lines():
    p.raw(_ln)

p.route = [(51.5, 57.5), (51.5, 54), (51.5, 48), (50.5, 46.5), (46, 46.5), (40.5, 46.5), (40.5, 38.5), (38.5, 37.5),
           (36.5, 37.5), (34.5, 37.5), (32, 37.5), (21, 37.5), (18.5, 36.5), (16.5, 34.5), (10.5, 28.5),
           (7.5, 25.5)]
p.branches["ROPE"] = [(18.5, 36.5), (17.5, 34.5), (17.5, 33), (17.5, 28.5), (11, 28.5), (10.5, 28.5), (7.5, 25.5)]

for x, y, t in ((48.3, 59.6, "the MEADOW"), (53.4, 51.5, "the first rise"),
                (43, 48.9, "the BREEZEWAY: the lesson - a gust onto a rail"),
                (41.6, 43, "the GUST BRIDGE: 5 crumbling tiles"), (42.3, 38, "the FAN PLAZA"),
                (38.4, 34.3, "the THERMAL: 8.5 units up the cliff"), (30.5, 34.3, "terrace 3: the cliff top"),
                (21.2, 40.7, "the WINDBREAKS: wait in a shelter, or lean into the gust"),
                (16.2, 39.7, "the LAUNCH PLAZA"), (4.2, 36.3, "the GLIDE: a pit crossed on rising air"),
                (18.6, 31, "the rope walk (the slow answer)"), (11.5, 23.5, "the SUMMIT"), (5.4, 31.5, "the wing")):
    p.note(x, y, t)
p.note(28.1, 39.6, "shelter", (255, 225, 40))
p.note(24.1, 39.6, "shelter", (255, 225, 40))
p.note(11.5, 25, "ART: the great kite flies over it", (255, 220, 0))
p.note(55.5, 56, "ART: a windsock", (255, 220, 0))
p.windows = [((51.5, 56), "the start"), ((37.5, 37.5), "the thermal"), ((13.5, 31.5), "the glide")]
p.legend = ["white arrows = wind (a gust unless noted), yellow arrows = an updraft; cracked tiles crumble"]

if __name__ == "__main__":
    p.main(HERE, os.path.join(ROOT, "apps", "bonanza", "courses", "kite.bbc"))
