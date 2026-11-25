#!/usr/bin/env python3
"""COURSE 7, CLOCKWORK KEEP (KEEP): the PAPER sketch (wave 11's pipeline, the pen-in step; ../KEEP.md is the
design sheet).  Host-only; nothing in `make` runs it and it ships nothing.  ../penkit.py is the pen.

    python3 sketch.py [outdir]                  plan.png and iso.png
    python3 sketch.py --bbc [OUT] [--force]     the engine course (apps/bonanza/courses/keep.bbc)

A floating castle that is one LOCK: the first course that is not a line.  A drawbridge on a timer, a portcullis
its plate raises, a courtyard with a locked door in sight, a rocking stair up to the battlements, pop-up spikes
along them to the KEY, back down to the door, and a hall whose floor is two turning cogs.  A second key, across
a bridge that is hardly ever down, opens the treasury: the second exit.  Rubber from start to finish.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from penkit import Pen

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))

HEAD = """
# Course 7 (KEEP; docs/plans/bonanza-courses/KEEP.md): CLOCKWORK KEEP, a floating castle that is one LOCK -
# the first course that is not a line.  A DRAWBRIDGE on a timer, a PORTCULLIS its plate raises, a courtyard
# with the keep's locked DOOR in sight, the ROCKING STAIR (a timed see-saw) up to the battlements, POP-UP
# SPIKES along them to the ring KEY, a drop back to the door, and the COG HALL: two quarter-turn tables over
# a pit, the throne across them.  The cross key, over the TRAITOR'S BRIDGE (down a third of the time), opens
# the TREASURY: exit 1.  Rubber throughout.  PEN-IN, attempt 1: written by
# docs/plans/bonanza-courses/keep/sketch.py --bbc --force while the layout moves.  NOT in the build, NOT
# `guide` yet (KEEP.md's "Risks for refinement").
course KEEP "Clockwork Keep"
width 128
origin 496
ball rubber
uses gate spike seesaw turntable
music fairway             # PLACEHOLDER: the song is the music agent's (KEEP.md: a clockwork march, ticking)
limit 99
target 90
"""

p = Pen("KEEP", "Clockwork Keep", HEAD, ground=7)
for sec, rgb in (("S", (150, 200, 150)), ("D", (200, 150, 90)), ("G", (190, 190, 200)), ("C", (140, 190, 140)),
                 ("W", (255, 235, 90)), ("B", (205, 205, 215)), ("H", (205, 120, 120)), ("T", (230, 200, 110)),
                 ("K", (180, 180, 195)), ("X", (215, 215, 225)), ("Z", (170, 170, 185))):
    p.col(sec, rgb)
STONE, TOWER = (150, 150, 165), (110, 110, 135)
p.scale = 1.5
p.plan_s = 24
p.plan_pad = (5, 11)

ZC, ZW = 10, 12                           # the courtyard (and the barbican, the hall), the battlements

# 1. THE BARBICAN: the start, on its own island ----------------------------------------------------------------
p.floor("S", 22, 36, 28, 40, ZC, "S: the BARBICAN, 6 x 4")
p.octa(22, 36, 28, 40)
p.guard(22, 37, 23, 39, sides=["-x"])
p.guard(27, 37, 28, 39, sides=["+x"])
p.guard(23, 39, 27, 40, sides=["+y"])
p.guard(23, 36, 24, 37, sides=["-y"])
p.guard(26, 36, 27, 37, sides=["-y"])
p.start = (25, 38)
# 2. THE DRAWBRIDGE: 2 wide, 4 long, on a timer - down 2.3 s in every 4.7, folding a cell at a time -------------
p.floor("D", 24, 32, 26, 36, ZC, "D: the DRAWBRIDGE's cells")
p.bridge(24, 32, 26, 36, period=256, on=128, style="picket")
# 3. THE GATEHOUSE: a plate, and the portcullis it raises ------------------------------------------------------
p.floor("G", 24, 29, 26, 32, ZC, "G: the GATEHOUSE, 2 x 3")
p.wall(23, 29, 24, 32, ZC + 1.5, col=STONE, note="the gatehouse's cheeks: low, so the courtyard is seen over them")
p.wall(26, 29, 27, 32, ZC + 1.5, col=STONE)
p.plate(24, 30, "plus")
p.gate(24, 29, "plus", "y", art="portcullis")
# 4. THE COURTYARD: the keep's DOOR in its east curtain, in sight from the gate --------------------------------
p.floor("C", 20, 21, 30, 29, ZC, "C: the COURTYARD, 10 x 8")
p.guard(20, 28, 24, 29, sides=["+y"])                # the south curtain, either side of the gatehouse
p.guard(26, 28, 30, 29, sides=["+y"])
p.guard(29, 25, 30, 29, sides=["+x"])                # the east curtain, either side of the door
p.guard(29, 21, 30, 23, sides=["+x"])
p.flag(25, 27, name="flag 0")
# 5. THE ROCKING STAIR: a TIMED see-saw between the courtyard and the north battlement - ride its low end up ----
p.seesaw(25, 20, 29, 21, "x", ZC + 1, rest="+", period=128, flat=16)
p.wall(29, 20, 30, 21, ZW + 0.5, col=STONE, note="the stair's end wall: the ball waits against it")
p.wall(20, 20, 25, 21, ZW + 0.5, col=STONE, note="the north battlement's inner parapet (and the stair's other end wall)")
# 6. THE BATTLEMENTS: north and west, 2 units over the courtyard, their outer edges crenellated -----------------
p.floor("B", 18, 18, 32, 20, ZW, "B: the north battlement, 14 x 2")
p.floor("B", 18, 20, 20, 29, ZW, "B: the west battlement, 2 x 9")
p.guard(18, 18, 19, 26, sides=["-x"])
p.guard(18, 27, 19, 29, sides=["-x"])
p.guard(18, 18, 32, 19, sides=["-y"])
p.guard(31, 18, 32, 20, sides=["+x"])
p.guard(29, 19, 32, 20, sides=["+y"])
p.wall(16, 16, 18, 18, ZW + 3, col=TOWER, note="the north-west tower (3 units: a floating face is at most 3, KEEP.md risk C6)", thick=3)
p.wall(32, 16, 34, 18, ZW + 3, col=TOWER, note="the north-east tower", thick=3)
p.wall(18, 29, 20, 31, ZW + 2, col=TOWER, note="the south-west tower (low: it stands in front of the battlement)", thick=2)
p.flag(24, 18, name="flag 1")
p.popspikes([(22, 18), (22, 19)], 128, 64, seed=0)
p.popspikes([(18, 22), (19, 22)], 128, 64, seed=64)
p.wall(20, 21, 21, 23, ZW + 0.5, col=STONE, note="a buttress: a spiked cell may not stand beside a LOWER floor (KEEP.md risk C4)")
p.key(19, 24, "ring")
# 7. THE DOOR and the COG HALL: two quarter-turn tables over a pit, an island between them, the throne ----------
p.floor("K", 30, 24, 31, 25, ZC, "the door's sill")
p.gate(30, 24, "ring", "x", art="door")
p.wall(30, 23, 31, 24, ZC + 2, col=STONE, note="the door's jamb")
p.floor("H", 31, 22, 34, 27, ZC, "H: the COG HALL's near floor, 3 x 5")
p.floor("H", 34, 24, 36, 26, ZC, "the first cog (a 2 x 2 table)")
p.floor("H", 36, 24, 37, 26, ZC, "the island between the cogs")
p.floor("H", 37, 24, 39, 26, ZC, "the second cog")
for _c in [(x, y) for x in (34, 35, 37, 38) for y in (24, 25)]:
    p.tint[_c] = (60, 60, 80)                        # (a table is half floor, half port: drawn dark under its cog)
p.turntable(34, 24, 2, "oo/..")
p.turntable(37, 24, 2, "oo/..", seed=96)
p.floor("T", 39, 22, 42, 28, ZC, "T: the THRONE's dais, 3 x 6")
p.guard(31, 22, 34, 23, sides=["-y"])
p.guard(31, 26, 34, 27, sides=["+y"])
p.guard(39, 27, 42, 28, sides=["+y"])
p.guard(41, 22, 42, 28, sides=["+x"])
p.guard(39, 22, 40, 23, sides=["-y"])
p.guard(41, 22, 42, 23, sides=["-y"])
p.flag(32, 24, name="flag 2")
p.goal(40, 24, 42, 26, ZC)
# 8. THE SECRET: the TRAITOR'S BRIDGE off the west battlement to a turret, the cross key, the TREASURY -----------
p.floor("X", 15, 26, 18, 27, ZW, "the TRAITOR'S BRIDGE's cells")
p.bridge(15, 26, 18, 27, period=256, on=96)       # down 1.8 s in every 4.7 (KEEP.md risk C2: NO TRAP reads one phase and cannot wait)
p.floor("Z", 12, 25, 15, 28, ZW, "the turret, 3 x 3")
p.guard(12, 25, 15, 28, sides=["-x", "-y", "+y"])
p.flag(19, 26, name="flag 3")
p.flag(14, 26, name="flag 4")
p.key(13, 26, "cross")
p.floor("Z", 40, 21, 41, 22, ZC, "the treasury's gate cell")
p.gate(40, 21, "cross", "y")
p.floor("Z", 39, 18, 42, 21, ZC, "the TREASURY, 3 x 3")
p.guard(39, 18, 42, 21, sides=["-x", "-y", "+x"])
p.goal(40, 18, 41, 20, ZC, exit=1)
p.float_all(10, 14, 44, 42)

p.clock(22, 38, ZC, "start")
p.clock(18, 18, ZW, "tower")
p.clock(41, 27, ZC, "throne")

p.route = [(25.5, 38.5), (24.5, 36), (24.5, 30.5), (24.5, 29.5), (25.5, 27.5), (28.5, 22), (28.5, 20.5),
           (28.5, 19.5), (22.5, 18.5), (19, 19), (19.5, 22.5), (19.5, 24.5), (21, 24.5), (29.5, 24.5),
           (30.5, 24.5), (32.5, 24.5), (34.5, 24.5), (36.5, 24.5), (38.5, 24.5), (40.5, 24.5)]
p.branches["VAULT"] = [(19.5, 24.5), (19.5, 26.5), (18.5, 26.5), (15, 26.5), (13.5, 26.5), (15, 26.5), (18.5, 26.5),
                       (20.5, 25.5), (29.5, 24.5), (32.5, 24.5), (38.5, 24.5), (40.5, 23), (40.5, 21.5), (40.5, 19.5)]

for x, y, t in ((28.6, 39.4, "the BARBICAN"), (26.8, 35.6, "the DRAWBRIDGE: down half the time"),
                (27.4, 31.9, "a plate, and the PORTCULLIS it raises"), (20.6, 27.9, "the COURTYARD"),
                (25.2, 22.5, "the ROCKING STAIR"), (21.5, 16.2, "pop-up spikes"), (14.2, 21.4, "pop-up spikes"),
                (26.5, 16.8, "the BATTLEMENTS"), (15.4, 23.7, "the ring KEY"), (29.4, 27.3, "the DOOR (ring)"),
                (32.6, 28.7, "the COG HALL: two quarter-turn tables over a pit"), (42.6, 27, "the THRONE"),
                (9, 28.4, "the TRAITOR'S BRIDGE to the cross KEY"), (42.8, 20.4, "the TREASURY (cross): exit 1")):
    p.note(x, y, t)
p.windows = [((25, 24.5), "the courtyard")]
p.legend = ["o + # x = a channel's glyph on its plate (white square), key (yellow disc), gate (orange) and bridge"]

if __name__ == "__main__":
    p.main(HERE, os.path.join(ROOT, "apps", "bonanza", "courses", "keep.bbc"))
