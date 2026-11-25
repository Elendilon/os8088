#!/usr/bin/env python3
"""COURSE 6, LODESTONE GORGE (LODE): the PAPER sketch (wave 11's pipeline, the pen-in step; ../LODE.md is the
design sheet).  Host-only; nothing in `make` runs it and it ships nothing.  ../penkit.py is the pen.

    python3 sketch.py [outdir]                  plan.png and iso.png
    python3 sketch.py --bbc [OUT] [--force]     the engine course (apps/bonanza/courses/lode.bbc)

STEEL's course, on DOWNHILL DECISION's steel exit: a SPIRAL into a quarry, the GREAT LODESTONE on an island in
its middle, in sight from the sirens' bridge on and reached last.  MAGNETS are its one new idea, and each
meeting turns them over: a HOIST that hauls steel up a ramp (they help), SIRENS that pull it off a bridge (they
hurt), a WALL of lodestones that holds it on a tilted ledge (they hold), the GANTRY it hovers under across
the moat (they fly), and the great lodestone, which hauls it up the last ramp into the goal (they bring it home).
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from penkit import Pen

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))

HEAD = """
# Course 6 (LODE; docs/plans/bonanza-courses/LODE.md): LODESTONE GORGE, STEEL's course - a SPIRAL into a
# quarry round the GREAT LODESTONE, on an island in its middle.  The FLUME (an S of round channel, 7 units
# down), a HOIST (a magnet at a ramp's top hauls steel up it), the SIRENS (magnets across a gap that pull steel
# off a bridge), a ramp into the LODESTONE WALL (a tilted ledge a fence of magnets holds steel on), a SLAG
# ridge that wants the speed, the GANTRY (a row of hanging magnets steel HOVERS under, over the moat), and the
# great lodestone's own hoist, into the goal.  PEN-IN, attempt 1: written by
# docs/plans/bonanza-courses/lode/sketch.py --bbc --force while the layout moves.  NOT in the build, NOT
# `guide` yet (LODE.md's "Risks for refinement").
course LODE "Lodestone Gorge"
width 128
origin 480
ball steel
uses magnet
music fairway             # PLACEHOLDER: the song is the music agent's (LODE.md: heavy, driving, a work song)
masks banded              # over the 256 occluder masks of one table at the pen-in (SPEC.md 130.52; LODE.md risk L3)
limit 99
target 60
"""

p = Pen("LODE", "Lodestone Gorge", HEAD)
for sec, rgb in (("A", (200, 170, 120)), ("B", (170, 150, 130)), ("C", (190, 160, 110)), ("P", (180, 160, 140)),
                 ("R", (200, 180, 130)), ("L", (160, 170, 190)), ("M", (120, 110, 130)), ("S", (150, 140, 150)),
                 ("Y", (200, 200, 120)), ("V", (240, 215, 120)), ("O", (120, 110, 130)), ("H", (215, 190, 130))):
    p.col(sec, rgb)

# (the gantry's posts stand at 14.5: a hanging magnet's ceiling is a signed byte of px, LODE.md risk L2)
ZA, ZB, ZC, ZL, ZS, ZV = 23, 16, 18, 14, 13, 12.5

# 1. THE HEADLAND and the FLUME: an S of round channel, 3 wide, 7 units down ---------------------------------
p.floor("A", 20, 4, 25, 8, ZA, "A: the HEADLAND, 5 x 4")
p.cut(20, 4, "up")
p.cut(24, 4, "right")
p.guard(21, 4, 24, 5, sides=["-y"])
p.guard(20, 5, 21, 8, sides=["-x"])
p.guard(24, 5, 25, 8, sides=["+x"])
p.start = (22, 5)
# (3 wide, `round`, 8 px: DOWN's standard - a 2-wide corner threw steel over its lip at every speed tried)
p.chute(3, "round", 8, [(22, 8, ZA), (22, 15, ZA - 5), (16, 15, ZA - 6.5), (16, 18, ZB)])
# the corners' CATWALKS: a strip of floor at the lip on the OUTSIDE of each corner, a guard rail on its inner
# edge - steel at the cap climbs a corner's bank and leaves over the lip without it (MEASURED on the model)
p.floor("O", 21, 17, 24, 18, ZA - 5, "the first corner's catwalk")
p.guard(21, 17, 24, 18, sides=["-y"])
p.floor("O", 14, 14, 15, 17, ZA - 6.5, "the second corner's catwalk")
p.guard(14, 14, 15, 17, sides=["+x"])
# 2. THE CATCH PEN: a railed room to stop in ------------------------------------------------------------------
p.floor("B", 14, 18, 24, 25, ZB, "B: the CATCH PEN, 10 x 7")
p.cut(14, 24, "left")
p.guard(14, 19, 15, 24, sides=["-x"])
p.guard(15, 24, 24, 25, sides=["+y"])
p.guard(23, 18, 24, 21, sides=["+x"])
p.guard(23, 23, 24, 25, sides=["+x"])
p.guard(18, 18, 21, 19, sides=["-y"])
# 3. THE HOIST: a magnet at the top of a ramp no steel ball climbs - it hauls the ball up (magnets HELP) -------
p.floor("H", 24, 21, 26, 23, ZB, "the hoist's foot, off the pen's east side")
p.ramp("H", "y", 25, 19, 26, 21, ZC, ZB, "H: the HOIST's ramp, 2 units in 2 tiles: steel stalls on it")
p.floor("H", 25, 18, 26, 19, ZC, "its top")
p.floor("M", 25, 17, 26, 18, ZC + 2, "the hoist's post")
p.magnet(25, 17, "+y", rng=3, strength=64)
p.guard(24, 22, 26, 23, sides=["+y"])
p.guard(25, 21, 26, 23, sides=["+x"])
# 4. THE SIRENS: a 2-wide bridge, three magnets on pillars across a gap, pulling steel at the edge (they HURT) -
p.floor("C", 26, 18, 39, 20, ZC, "C: the SIRENS' bridge, 13 x 2")
p.flag(26, 18, "steel", "flag 0")
for (x, y, face, s) in ((29, 15, "+y", 16), (33, 22, "-y", 24), (37, 15, "+y", 32)):     # a tug, a pull, a hard pull (MEASURED)
    p.floor("O", x, y, x + 1, y + 1, ZC + 2, "a siren's pillar")
    p.magnet(x, y, face, rng=4, strength=s)
# 5. THE TURN and the ramp into the LODESTONE WALL (they HOLD) ------------------------------------------------
p.floor("P", 39, 18, 42, 23, ZC, "P: the TURN, 3 x 5")
p.guard(39, 18, 42, 19, sides=["-y"])
p.guard(41, 18, 42, 23, sides=["+x"])                # the backstop: steel does not stop short
p.guard(39, 20, 40, 23, sides=["-x"])
p.guard(39, 22, 41, 23, sides=["+y"])
p.flag(40, 21, "steel", "flag 1")
p.ramp("R", "y", 41, 23, 42, 27, ZC, ZL, "R: the ramp, 4 units in 4 tiles, 1 wide: the speed for the wall")
p.floor("L", 41, 27, 42, 33, ZL, "L: the ledge, 1 wide, level and railed")
p.guard(41, 27, 42, 33, sides=["+x", "-x"])
p.ramp("L", "x", 41, 33, 42, 39, ZL, ZL - 0.5, "L: the LODESTONE WALL's first leg: tilted to its open side")
p.floor("L", 41, 39, 42, 41, ZL - 0.5, "the wall's corner")
p.guard(41, 39, 42, 41, sides=["+x", "+y"])          # the corner's backstop
p.ramp("L", "y", 35, 40, 41, 41, ZL - 0.5, ZL - 1, "L: its second leg, walked up-left (-x)")
for y in range(33, 39):
    p.floor("M", 40, y, 41, y + 1, ZL + 2, "a lodestone's post")
    p.magnet(40, y, "+x", strength=8)
for x in range(35, 41):
    p.floor("M", x, 39, x + 1, 40, ZL + 1.5, "a lodestone's post")
    p.magnet(x, 39, "+y", strength=8)
# 6. THE SLAG: a HIGH ridge across the gallery - steel wants three tiles of run at it --------------------------
p.floor("S", 25, 39, 35, 42, ZS, "S: the SLAG gallery, 10 x 3")
p.guard(25, 39, 26, 42, sides=["-x"])
p.guard(25, 41, 35, 42, sides=["+y"])
p.guard(25, 39, 28, 40, sides=["-y"])
p.guard(29, 39, 35, 40, sides=["-y"])
p.hump(31, 39, ZS, along="y", n=3, height=10, open_=True)
p.flag(26, 40, "steel", "flag 2")
# 7. THE GANTRY: a railed runway, then five tiles of moat under hanging magnets (they FLY) ---------------------
p.floor("Y", 28, 36, 29, 39, ZS, "Y: the RUNWAY, 1 wide, railed both sides: the ball leaves it straight")
p.guard(28, 36, 29, 39, sides=["-x", "+x"])
for y in range(31, 36):
    p.floor("M", 27, y, 28, y + 1, ZS + 1.5, "the gantry's post")
    p.magnet(27, y, None, down="+x")
# 8. THE GREAT LODESTONE: an island in the middle of the spiral; its magnet hauls the ball up into the goal ----
p.floor("V", 26, 28, 31, 31, ZV, "V: the island's apron, 5 x 3")
p.cut(26, 28, "up")
p.cut(30, 28, "right")
p.guard(26, 29, 27, 31, sides=["-x"])
p.guard(30, 29, 31, 31, sides=["+x"])
p.guard(26, 30, 28, 31, sides=["+y"])
p.guard(29, 30, 31, 31, sides=["+y"])
p.ramp("V", "y", 28, 25, 29, 28, ZV + 3, ZV, "the last ramp, 3 units in 3 tiles")
p.floor("M", 28, 23, 29, 24, ZV + 5, "the GREAT LODESTONE's post")
p.magnet(28, 23, "+y", rng=4, strength=104)
p.goal(27, 24, 30, 25, ZV + 3)

p.clock(24, 6, ZA, "start")
p.clock(41, 18, ZC, "turn")
p.clock(30, 29, ZV, "vault")

p.route = [(22.5, 5.5), (22.5, 8.5), (22.5, 15.5), (16.5, 15.5), (16.5, 18.5), (17.5, 21.5), (22.5, 21.5),
           (25.5, 21.5), (25.5, 18.5), (26.5, 18.5), (38, 19), (40.5, 20.5), (41.5, 23), (41.5, 27), (41.5, 40.5),
           (40.5, 40.5), (35, 40.5), (32, 40.5), (29, 40.5), (28.5, 39), (28.5, 36), (28.5, 31), (28.5, 29.5),
           (28.5, 28), (28.5, 24.5)]

for x, y, t in ((25.3, 6, "the HEADLAND"), (24.2, 11.5, "the FLUME: an S of channel, 7 units down"),
                (11.5, 25.8, "the CATCH PEN"), (19.5, 26.6, "the HOIST: a magnet hauls steel up the ramp"),
                (30.3, 17.2, "the SIRENS: three magnets pull steel at the edge"),
                (42.6, 20, "the TURN"), (42.5, 25, "the ramp"), (42.5, 35.5, "the LODESTONE WALL: magnets hold steel on the tilt"),
                (35.5, 42.2, "its second leg"), (22, 43.6, "the SLAG: a high ridge wants speed"),
                (29.8, 38.6, "the RUNWAY"), (30.2, 35.2, "the GANTRY: 5 tiles of hover"),
                (31.6, 25.4, "the GREAT LODESTONE hauls the ball into the goal")):
    p.note(x, y, t)
p.windows = [((22.5, 6), "the start"), ((33, 19), "the sirens")]
p.legend = ["magenta M = a magnet (its field outlined), v = a hanging one; the magenta band = the flume"]

if __name__ == "__main__":
    p.main(HERE, os.path.join(ROOT, "apps", "bonanza", "courses", "lode.bbc"))
