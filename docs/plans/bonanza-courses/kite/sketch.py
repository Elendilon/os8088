#!/usr/bin/env python3
"""COURSE 5, KITE HILL (KITE): the PAPER sketch (wave 11's pipeline, the pen-in step; ../KITE.md is the
design sheet).  Host-only; nothing in `make` runs it and it ships nothing.  ../penkit.py is the pen.

    python3 sketch.py [outdir]                  plan.png and iso.png
    python3 sketch.py --bbc [OUT] [--force]     the engine course (apps/bonanza/courses/kite.bbc)

A CLIMB, the first course whose finish is ABOVE its start: a hill of terraces up the screen, the WIND its one
new idea - a gust that shoves, a gust across a crumbling bridge, a THERMAL that lifts the ball up a cliff, gusts
to wait out behind windbreaks, and the GLIDE: a chasm crossed on rising air.  Rubber from start to finish.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from penkit import Pen

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))

HEAD = """
# Course 5 (KITE; docs/plans/bonanza-courses/KITE.md): KITE HILL, a CLIMB - a hill of terraces up the screen
# and the WIND on it.  A gust that shoves (railed: the lesson), a gust across a CRUMBLING BRIDGE, a THERMAL
# that lifts the ball 8 units up a cliff, gusts waited out behind WINDBREAKS, and the GLIDE: a chasm crossed
# on rising air, the summit across it.  Rubber from start to finish.  PEN-IN, attempt 1: written by
# docs/plans/bonanza-courses/kite/sketch.py --bbc --force while the layout moves.  NOT in the build, NOT
# `guide` yet (KITE.md's "Risks for refinement").
course KITE "Kite Hill"
width 128
origin 480                # 1,024 px: the floors run from about px -250 (the launch plaza) to +310 (terrace 3)
ball rubber
uses wind glass           # (the crumbling bridge's cracked tiles are GLASS's kind `crack`, SPEC.md 130.25.8)
music fairway             # PLACEHOLDER: the song is the music agent's (KITE.md: light, airy, rising)
palette 0                 # green, red, yellow on black: a grassy hill (LITTLE HOP's palette)
limit 90
target 60
"""

p = Pen("KITE", "Kite Hill", HEAD)
for sec, rgb in (("A", (110, 200, 110)), ("R", (150, 215, 130)), ("B", (135, 205, 120)), ("C", (235, 235, 215)),
                 ("D", (120, 190, 160)), ("S", (190, 170, 120)), ("T", (200, 190, 140)), ("E", (190, 150, 100)),
                 ("F", (170, 180, 170)), ("P", (120, 130, 150)), ("K", (200, 160, 110)), ("G", (235, 240, 250)),
                 ("N", (120, 170, 120)), ("H", (250, 250, 255))):
    p.col(sec, rgb)

ZA, Z1, Z3, ZG = 4, 7, 15, 17.5          # the meadow, terraces 1 - 2, terraces 3 - 4, the summit

# 1. THE MEADOW: the start, with roll room, and the first rise ---------------------------------------------
p.floor("A", 38, 44, 45, 49, ZA, "A: the MEADOW, 7 x 5")
p.octa(38, 44, 45, 49)
p.guard(39, 44, 44, 49)                              # a safe start: its open edges railed (the cut corners open)
p.guard(38, 45, 45, 48)
p.start = (41, 47)
p.ramp("R", "y", 40, 38, 43, 44, Z1, ZA, "R: the first rise, 3 units in 6 tiles, 3 wide")
# 2. THE BREEZEWAY (terrace 1): the wind's LESSON - a gust across a wide walk, the downwind edge RAILED --------
p.floor("B", 29, 35, 43, 38, Z1, "B: the BREEZEWAY, 14 x 3, walked up-left (-x)")
p.floor("N", 36, 34, 37, 35, Z1, "the lesson's fan, in a notch on the upwind side")
p.blower(36, 34, "+y", (34, 35, 38, 37), 10, gust=(64, 64), flag=True)
p.guard(32, 37, 41, 38, sides=["+y"])                # the lesson's rail: the gust only leans the ball on it
p.guard(32, 35, 36, 36, sides=["-y"])                # ... and one upwind, either side of the fan's notch: a ball
p.guard(37, 35, 41, 36, sides=["-y"])                # leaning into the gust rolls that way when the calm comes
p.guard(36, 34, 37, 35, sides=["-x", "-y", "+x"])
p.guard(29, 35, 30, 38, sides=["-x"])                # the walk's end (the turn onto the bridge)
# 3. THE GUST BRIDGE: five CRUMBLING tiles, 1 wide, a gust across them ------------------------------------------
for y in range(30, 35):
    p.floor("C", 30, y, 31, y + 1, Z1, "C: the crumbling bridge")
    p.crack(30, y)
p.float(30, 30, 31, 35, 0.5)
p.floor("N", 28, 32, 29, 33, Z1, "the bridge's fan, on a lone pillar upwind (one void cell off the bridge)")
p.blower(28, 32, "+x", (29, 30, 31, 34), 8, gust=(64, 192))
p.flag(30, 36, name="flag 0")                        # G20: just before what kills
# 4. THE FAN PLAZA (terrace 2) and THE THERMAL: 8 units up the cliff on rising air -----------------------------
p.floor("D", 28, 24, 36, 30, Z1, "D: the FAN PLAZA, 8 x 6, under the cliff")
p.cut(28, 29, "left")
p.cut(35, 29, "down")
p.guard(28, 24, 36, 29)
p.guard(29, 29, 35, 30)
p.blower(32, 25, "up", (31, 24, 33, 25), 40, top=9, lift=True)
p.floor("S", 27, 19, 37, 24, Z3, "S: terrace 3, the cliff's top (its +y face is the cliff, 8 units)")
p.cut(27, 19, "up")
p.cut(36, 19, "right")
p.guard(28, 19, 36, 20, sides=["-y"])
p.guard(36, 20, 37, 24, sides=["+x"])
p.guard(27, 23, 31, 24, sides=["+y"])                # the cliff's edge railed beside the thermal's landing ...
p.guard(34, 23, 36, 24, sides=["+y"])                # ... (open over the thermal, x 31 - 33)
# TOOL AID (KITE.md risk K1): the tool's finish rule closes the start's reach by rolls and Hops ALONE - no
# thermal, lift or spring is in it - so a finish above the start is refused.  This 1-wide stair of a ramp (2
# units a tile: no ball climbs it) is a rollable way in that closure, and it is RAILED OFF at both ends (the
# closure knows no rail), so in play it is scenery.  It goes when the tool's closure learns a `lift` updraft.
p.ramp("K", "y", 36, 24, 37, 28, Z3, Z1, "K: a TOOL AID, railed off - not a design element (risk K1)")
p.guard(36, 23, 37, 24, sides=["+y"])
p.guard(35, 24, 36, 28, sides=["+x"])
# 5. THE WINDBREAKS: a 2-wide bridge in a hard gust, a railed SHELTER every fourth tile ------------------------
p.floor("E", 16, 21, 27, 23, Z3, "E: the WINDBREAK bridge, 11 x 2, walked up-left (-x)")
p.float(16, 21, 27, 23, 1)
for sx in (24, 20):
    p.guard(sx, 22, sx + 1, 23, sides=["+y"])        # a SHELTER: its downwind edge railed
p.floor("N", 22, 19, 23, 20, Z3, "the windbreaks' fan, on a lone pillar upwind")
p.blower(22, 19, "+y", (17, 20, 26, 22), 12, gust=(24, 104))
p.flag(28, 21, name="flag 1")
# 6. THE LAUNCH PLAZA (terrace 4) and THE GLIDE: 7 tiles of chasm on rising air, the summit 2.5 units up ------
p.floor("F", 9, 19, 16, 24, Z3, "F: the LAUNCH PLAZA, 7 x 5")
p.cut(9, 23, "left")
p.cut(15, 23, "down")
p.guard(9, 19, 10, 23, sides=["-x"])
p.guard(10, 23, 15, 24, sides=["+y"])
p.guard(9, 19, 10, 20, sides=["-y"])
p.guard(14, 19, 15, 20, sides=["-y"])
p.guard(15, 19, 16, 21, sides=["+x"])
p.floor("P", 11, 15, 12, 16, Z3 - 3, "P: the glide's fan, on a pillar in the middle of the chasm, 3 units down")
p.blower(11, 15, "up", (10, 12, 13, 18), 40, top=7, lift=True)
p.flag(12, 21, name="flag 2")
# THE ROPE BRIDGE: the glide's other answer (G22) - 1 wide, no rail, out of the wind, slow
p.ramp("K", "y", 15, 14, 16, 19, ZG, Z3, "the ROPE BRIDGE: 1 wide, 2.5 units up in 5 tiles")
p.floor("K", 15, 12, 16, 14, ZG, "the rope bridge's last two planks")
p.float(15, 12, 16, 19, 0.5)
p.guard(15, 12, 16, 19, sides=["+x", "-x"])          # railed both sides: the slow answer is the SAFE one
# 7. THE SUMMIT ------------------------------------------------------------------------------------------
p.floor("G", 8, 5, 17, 12, ZG, "G: the SUMMIT, 9 x 7")
p.cut(8, 5, "up")
p.cut(16, 5, "right")
p.guard(9, 5, 16, 6, sides=["-y"])
p.guard(8, 6, 9, 12, sides=["-x"])
p.guard(16, 6, 17, 12, sides=["+x"])
p.guard(8, 11, 10, 12, sides=["+y"])
p.guard(14, 11, 15, 12, sides=["+y"])
p.guard(16, 11, 17, 12, sides=["+y"])
p.floor("H", 10, 6, 15, 9, ZG + 0.5, "the CROWN: half a unit up (every ball rolls up it), the goal on it")
p.goal(11, 6, 14, 8, ZG + 0.5)

p.clock(44, 45, ZA, "start")
p.clock(35, 28, Z1, "plaza")
p.clock(9, 22, Z3, "launch")
p.clock(16, 7, ZG, "summit")

p.route = [(41.5, 47.5), (41.5, 44), (41.5, 38), (41.5, 36.5), (36, 36.5), (30.5, 36.5), (30.5, 35), (30.5, 30),
           (30.5, 28), (32.5, 26.5), (32.5, 25.5), (32.5, 24.5), (32.5, 23.5), (32.5, 21.5), (28.5, 21.5),
           (27, 21.5), (16, 21.5), (12.5, 21.5), (12.5, 19.5), (12.5, 12), (12.5, 11.5), (12.5, 9.5), (12.5, 7.5)]
p.branches["ROPE"] = [(12.5, 21.5), (15.5, 20.5), (15.5, 19), (15.5, 12.5), (15.5, 11.5), (12.5, 9.5), (12.5, 7.5)]

for x, y, t in ((38.3, 49.6, "the MEADOW"), (43.4, 41.5, "the first rise"),
                (33, 38.9, "the BREEZEWAY: the lesson - a gust onto a rail"),
                (31.6, 33, "the GUST BRIDGE: 5 crumbling tiles"), (29.5, 30.8, "the FAN PLAZA"),
                (34.3, 26, "the THERMAL: 8 units up"), (29, 18.2, "terrace 3: the cliff top"),
                (17, 24.3, "the WINDBREAKS: wait in a shelter, run in the calm"), (8.2, 25, "the LAUNCH PLAZA"),
                (6.4, 15.2, "the GLIDE: 7 tiles of chasm"), (16.6, 15.5, "the rope bridge (the slow answer)"),
                (17.3, 9, "the SUMMIT"), (37.4, 26.5, "(a tool aid, railed off)")):
    p.note(x, y, t)
p.note(22.6, 23.6, "shelter", (255, 225, 40))
p.note(18.6, 23.6, "shelter", (255, 225, 40))
p.note(12.2, 4, "ART: the great kite flies here", (255, 220, 0), z=ZG + 7)
p.note(45.5, 46, "ART: a windsock", (255, 220, 0))
p.windows = [((41.5, 46), "the start"), ((31.5, 26.5), "the thermal"), ((12.5, 14.5), "the glide")]
p.legend = ["white arrows = wind (a gust unless noted), yellow arrows = an updraft; cracked tiles crumble"]

if __name__ == "__main__":
    p.main(HERE, os.path.join(ROOT, "apps", "bonanza", "courses", "kite.bbc"))
