#!/usr/bin/env python3
"""COURSE 7, CLOCKWORK KEEP (KEEP): the sketch (wave 11's pipeline; ../KEEP.md is the design sheet).  Host-only;
nothing in `make` runs it and it ships nothing.  ../penkit.py is the pen.

    python3 sketch.py [outdir]                  plan.png and iso.png
    python3 sketch.py --bbc [OUT] [--force]     the engine course (apps/bonanza/courses/keep.bbc)

A floating castle that is one LOCK: the first course that is not a line.  A drawbridge on a timer, a portcullis
its plate raises, a courtyard with a locked door in sight, a rocking stair up to the battlements, pop-up spikes
along them to the KEY, one roll back down to the door, and a hall whose floor is two turning cogs.  A second key,
across a bridge that is down a third of the time, opens the treasury: the second exit.  Rubber from start to
finish.  REFINED (KEEP.md sections 10 - 13): every number here is the course as it passes the course guide.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from penkit import Pen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import art as ART                         # the gates' art and the decals (keep/art.py, ART.md): their names and `art` lines

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))

ORIGIN = 496                              # KEEP.md section 2: the camera's lattice, and the reach's room on the left
HEAD = """
# Course 7 (KEEP; docs/plans/bonanza-courses/KEEP.md): CLOCKWORK KEEP, a floating castle that is one LOCK -
# the first course that is not a line.  A DRAWBRIDGE on a timer (up as the play starts: watch it lay down), a
# PORTCULLIS its plate raises, a courtyard with the keep's locked DOOR in sight, the ROCKING STAIR (a timed
# see-saw) up to the battlements, POP-UP SPIKES along them to the ring KEY, one roll back down to the door, and
# the COG HALL: two quarter-turn tables over a pit, the throne across them.  The cross key, over the TRAITOR'S
# BRIDGE (down a third of the time), opens the TREASURY: exit 1.  Rubber throughout.  REFINED to the course
# guide (KEEP.md sections 10 - 13).  Written by docs/plans/bonanza-courses/keep/sketch.py --bbc --force; NOT in
# the build yet (no BZ_COURSES entry, no pathway pad).
course KEEP "Clockwork Keep"
guide                     # a REAL course: held to the course guide's checkable rules
width 128
origin %d
ball rubber
uses gate spike seesaw turntable
music clockwork           # its own song (the second, 2026-11-25): a gavotte in D major whose motif KNOCKS, at the machines' own rate (KEEP.md, "The song")
limit 99
target 90
""" % ORIGIN

p = Pen("KEEP", "Clockwork Keep", HEAD, ground=7)
for sec, rgb in (("S", (150, 200, 150)), ("D", (200, 150, 90)), ("G", (190, 190, 200)), ("C", (140, 190, 140)),
                 ("W", (255, 235, 90)), ("B", (205, 205, 215)), ("H", (205, 120, 120)), ("T", (230, 200, 110)),
                 ("K", (180, 180, 195)), ("X", (215, 215, 225)), ("Z", (170, 170, 185))):
    p.col(sec, rgb)
STONE, TOWER, HAY = (150, 150, 165), (110, 110, 135), (225, 205, 120)
p.scale = 1.5
p.plan_s = 24
p.plan_pad = (5, 11)

ZC, ZW = 10, 12                           # the courtyard (and the barbican, the hall), the battlements
CX0, CX1, CY0, CY1 = 20, 30, 21, 30       # the COURTYARD, 10 x 9: one window holds its door, its key and its stair
GX = 24                                   # the gate's two lanes, GX and GX + 1; the plate's is GX
GY = CY1                                  # the gatehouse's first row (3), then the drawbridge (4), the barbican (5)
KY = 24                                   # the KEY's row, and the DOOR's: one straight roll
BY = KY + 4                               # the TRAITOR'S BRIDGE's row: 4 from the key (KEEP.md section 12, K17)
SX = CX1 - 5                              # the rocking stair's first cell (4 long, its east end the low one at rest)
DX = CX1                                  # the door's sill
HX = DX + 2                               # the cog hall's near floor (3 x 5), past the keep's 1-tile passage
TX = HX + 8                               # the throne's dais (3 x 6)

# 1. THE BARBICAN: the start, on its own island, railed all round but the bridge's mouth -------------------------
p.floor("S", GX - 2, GY + 7, GX + 4, GY + 12, ZC, "S: the BARBICAN, 6 x 5")
p.guard(GX - 2, GY + 7, GX + 4, GY + 12, sides=["-x", "+x", "+y"])
p.guard(GX - 2, GY + 7, GX, GY + 8, sides=["-y"])
p.guard(GX + 2, GY + 7, GX + 4, GY + 8, sides=["-y"])
p.start = (GX, GY + 10)                   # (three tiles from the bridge, in the plate's lane: the straight line presses it)
# 2. THE DRAWBRIDGE: 2 wide, 4 long, on a timer - UP as the play starts, laid down at 0.7 s for 2.9 s of every 4.7
p.floor("D", GX, GY + 3, GX + 2, GY + 7, ZC, "D: the DRAWBRIDGE's cells")
p.bridge(GX, GY + 3, GX + 2, GY + 7, period=256, on=160, seed=216, style="picket")
# 3. THE GATEHOUSE: a plate, and the portcullis it raises ------------------------------------------------------
p.floor("G", GX, GY, GX + 2, GY + 3, ZC, "G: the GATEHOUSE, 2 x 3")
p.wall(GX - 1, GY, GX, GY + 3, ZC + 1.5, col=STONE, note="the gatehouse's cheeks: low, so the courtyard is seen over them")
p.wall(GX + 2, GY, GX + 3, GY + 3, ZC + 1.5, col=STONE)
p.plate(GX, GY + 1, "plus")
p.gate(GX, GY, "plus", "y", art=ART.GATES["portcullis"])
# 4. THE COURTYARD: the keep's DOOR in its east curtain, in sight from the gate --------------------------------
p.floor("C", CX0, CY0, CX1, CY1, ZC, "C: the COURTYARD, 10 x 9")
p.guard(CX0, CY1 - 1, GX, CY1, sides=["+y"])               # the south curtain, either side of the gatehouse
p.guard(GX + 2, CY1 - 1, CX1, CY1, sides=["+y"])
p.guard(CX1 - 1, KY + 1, CX1, CY1, sides=["+x"])           # the east curtain, either side of the door
p.guard(CX1 - 1, CY0, CX1, KY - 1, sides=["+x"])
p.surface("sand", CX0, KY - 1, CX0 + 2, KY + 2, HAY)        # the HAY under the key: a ball that drops lands dead
# 5. THE ROCKING STAIR: a TIMED see-saw between the courtyard and the north battlement - ride its low end up ----
p.seesaw(SX, CY0 - 1, SX + 4, CY0, "x", ZC + 1, rest="+", period=128, flat=16)
p.wall(SX + 4, CY0 - 1, SX + 5, CY0, ZW + 0.5, col=STONE, note="the stair's end wall: the ball waits against it")
p.wall(CX0, CY0 - 1, SX, CY0, ZW + 0.5, col=STONE, note="the north battlement's inner parapet (and the stair's other end wall)")
# 6. THE BATTLEMENTS: north and west, 2 units over the courtyard, their outer edges crenellated -----------------
p.floor("B", CX0 - 2, CY0 - 3, CX1 + 2, CY0 - 1, ZW, "B: the north battlement, 2 wide")
p.floor("B", CX0 - 2, CY0 - 1, CX0, CY1, ZW, "B: the west battlement, 2 wide")
p.guard(CX0 - 2, CY0 - 3, CX0 - 1, CY0 - 1, sides=["-x"])
p.guard(CX0 - 2, CY0, CX0 - 1, BY, sides=["-x"])
p.guard(CX0 - 2, BY + 1, CX0 - 1, CY1, sides=["-x"])
p.guard(CX0 - 2, CY0 - 3, CX1 + 2, CY0 - 2, sides=["-y"])
p.guard(CX1 + 1, CY0 - 3, CX1 + 2, CY0 - 1, sides=["+x"])
p.guard(CX1, CY0 - 2, CX1 + 2, CY0 - 1, sides=["+y"])
p.wall(CX0 - 4, CY0 - 5, CX0 - 2, CY0 - 3, ZW + 3, col=TOWER, note="the north-west tower (3 units: a floating face is at most 3)", thick=3)
p.wall(CX1 + 2, CY0 - 5, CX1 + 4, CY0 - 3, ZW + 3, col=TOWER, note="the north-east tower", thick=3)
p.wall(CX0 - 2, CY1, CX0, CY1 + 2, ZW + 2, col=TOWER, note="the south-west tower (low: it stands in front of the battlement)", thick=2)
# the flags' PINCHES: a merlon on the inner lane, so every ball passes over the flag beside it (a flag is one cell)
p.wall(SX - 1, CY0 - 2, SX, CY0 - 1, ZW + 0.5, col=STONE, note="a merlon: the walk is one lane here, the flag's")
p.flag(SX - 1, CY0 - 3, name="flag 0")
p.popspikes([(SX - 3, CY0 - 3), (SX - 3, CY0 - 2)], 128, 64, seed=0)
p.wall(CX0 - 2, CY0 - 1, CX0 - 1, CY0, ZW + 0.5, col=STONE, note="a merlon: the flag's lane is the inner one, beside the parapet")
p.flag(CX0 - 1, CY0 - 1, name="flag 1")
p.popspikes([(CX0 - 2, CY0 + 1), (CX0 - 1, CY0 + 1)], 128, 64, seed=64)
p.wall(CX0, CY0, CX0 + 1, CY0 + 2, ZW + 0.5, col=STONE, note="a buttress: a spiked cell may not stand beside a LOWER floor (SPEC.md 137.38.4)")
p.key(CX0 - 1, KY, "ring")
# 7. THE DOOR, the keep's passage and the COG HALL: two quarter-turn tables over a pit, an island, the throne ----
p.floor("K", DX, KY, DX + 2, KY + 1, ZC, "the door's sill and the keep's passage")
p.guard(DX + 1, KY, DX + 2, KY + 1, sides=["-y", "+y"])
p.gate(DX, KY, "ring", "x", art=ART.GATES["door"])
p.wall(DX, KY - 1, DX + 1, KY, ZC + 2, col=STONE, note="the door's jamb")
p.floor("H", HX, KY - 2, HX + 3, KY + 3, ZC, "H: the COG HALL's near floor, 3 x 5")
p.floor("H", HX + 3, KY, HX + 5, KY + 2, ZC, "the first cog (a 2 x 2 table)")
p.floor("H", HX + 5, KY, HX + 6, KY + 2, ZC, "the island between the cogs")
p.floor("H", HX + 6, KY, HX + 8, KY + 2, ZC, "the second cog")
for _c in [(x, y) for x in (HX + 3, HX + 4, HX + 6, HX + 7) for y in (KY, KY + 1)]:
    p.tint[_c] = (60, 60, 80)                        # (a table is half floor, half port: drawn dark under its cog)
p.turntable(HX + 3, KY, 2, "oo/..")
p.turntable(HX + 6, KY, 2, "oo/..", seed=96)
p.floor("T", TX, KY - 2, TX + 3, KY + 4, ZC, "T: the THRONE's dais, 3 x 6")
p.guard(HX, KY - 2, HX + 3, KY - 1, sides=["-y"])
p.guard(HX, KY + 2, HX + 3, KY + 3, sides=["+y"])
p.guard(HX, KY - 2, HX + 1, KY, sides=["-x"])               # the keep's west wall, either side of the passage
p.guard(HX, KY + 1, HX + 1, KY + 3, sides=["-x"])
p.guard(HX + 2, KY - 2, HX + 3, KY, sides=["+x"])           # the pit's near edge, either side of the first cog
p.guard(HX + 2, KY + 2, HX + 3, KY + 3, sides=["+x"])
p.guard(TX, KY - 2, TX + 1, KY, sides=["-x"])               # ...and its far edge, either side of the second
p.guard(TX, KY + 2, TX + 1, KY + 4, sides=["-x"])
p.guard(TX, KY + 3, TX + 3, KY + 4, sides=["+y"])
p.guard(TX + 2, KY - 2, TX + 3, KY + 4, sides=["+x"])
p.guard(TX, KY - 2, TX + 1, KY - 1, sides=["-y"])
p.guard(TX + 2, KY - 2, TX + 3, KY - 1, sides=["-y"])
p.flag(DX + 1, KY, name="flag 2")
p.goal(TX + 1, KY + 2, TX + 3, KY + 4, ZC)          # the THRONE: to the RIGHT off the second cog, never straight on
# 8. THE SECRET: the TRAITOR'S BRIDGE off the west battlement to a turret, the cross key, the TREASURY -----------
p.floor("X", CX0 - 5, BY, CX0 - 2, BY + 1, ZW, "the TRAITOR'S BRIDGE's cells")
p.bridge(CX0 - 5, BY, CX0 - 2, BY + 1, period=256, on=96, seed=96, style="portcullis")   # iron plates, a boss a
# tile: a different machine from the planked drawbridge, and plainly not floor (the default deck is a bare seam)
p.floor("Z", CX0 - 8, BY - 1, CX0 - 5, BY + 2, ZW, "the turret, 3 x 3")
p.guard(CX0 - 8, BY - 1, CX0 - 5, BY + 2, sides=["-x", "-y", "+y"])
p.guard(CX0 - 6, BY - 1, CX0 - 5, BY, sides=["+x"])
p.guard(CX0 - 6, BY + 1, CX0 - 5, BY + 2, sides=["+x"])
p.flag(CX0 - 2, BY, name="flag 3")
p.flag(CX0 - 6, BY, name="flag 4")
p.key(CX0 - 7, BY, "cross")
p.floor("Z", TX + 1, KY - 3, TX + 2, KY - 2, ZC, "the treasury's gate cell")
p.guard(TX + 1, KY - 3, TX + 2, KY - 2, sides=["-x", "+x"])
p.gate(TX + 1, KY - 3, "cross", "y", art=ART.GATES["vault"])
p.floor("Z", TX, KY - 6, TX + 3, KY - 3, ZC, "the TREASURY, 3 x 3")
p.guard(TX, KY - 6, TX + 3, KY - 3, sides=["-x", "-y", "+x"])
p.guard(TX, KY - 4, TX + 1, KY - 3, sides=["+y"])
p.guard(TX + 2, KY - 4, TX + 3, KY - 3, sides=["+y"])
p.goal(TX + 1, KY - 6, TX + 2, KY - 4, ZC, exit=1, hidden=True)   # a SECRET finish (SPEC.md 137.19.4): the pathway's `secret` route needs the word
p.float_all(CX0 - 10, CY0 - 7, TX + 5, GY + 14)

# the clocks are HOURGLASSES (keep/CLOCKS.md; SPEC.md 137.18.5.2): the sand runs out along the course, and the
# finial is a padlock, a key, a crown.  White digits where the sand is below them (SPEC.md 137.18.5.6)
p.clock(GX - 2, GY + 9, ZC, "start: full, a padlock", frame="hourp")
p.clock(CX0 - 2, CY0 - 3, ZW, "tower: half run, a key", frame="hourk ink white")
p.clock(TX, KY - 2, ZC, "throne: run out, a crown", frame="hourc ink white")                  # the dais's back-left corner: only the void is behind its head

p.comment("ART (docs/plans/bonanza-courses/keep/art.py draws the files and places them: ART.md)")
for _ln in ART.lines():
    p.raw(_ln)

p.route = [(GX + .5, GY + 10.5), (GX + .5, GY + 2.5), (GX + .5, GY - .5), (SX + 3.5, CY0 + 1.5), (SX + 3.5, CY0 + .5),
           (SX + 3.5, CY0 - 1.5), (SX - .5, CY0 - 2.5), (SX - 1.5, CY0 - 2.5), (SX - 3.5, CY0 - 2.5), (CX0 + .5, CY0 - 1.5),
           (CX0 - .5, CY0 - 1.5), (CX0 - .5, CY0 - .5), (CX0 - .5, CY0 + .5), (CX0 - .5, CY0 + 2.5),
           (CX0 - .5, KY + .5), (CX0 + 1.5, KY + .5), (DX - .5, KY + .5), (DX + 1.5, KY + .5), (HX + 2.5, KY + .5),
           (HX + 5.5, KY + .5), (TX + .5, KY + .5), (TX + .5, KY + 2.5), (TX + 1.5, KY + 2.5)]
p.branches["VAULT"] = [(CX0 - .5, KY + .5), (CX0 - 1.5, BY + .5), (CX0 - 5.5, BY + .5), (CX0 - 7.5, BY + .5),   # (a way is TAKEN
                       # a little short of its tile: the one past the cross key takes the ball over it)
                       (CX0 - 5.5, BY + .5), (CX0 - 1.5, BY + .5), (CX0 - .5, KY + 1.5), (CX0 + 1.5, KY + 1.5),
                       (DX - .5, KY + .5), (DX + 1.5, KY + .5), (HX + 2.5, KY + .5), (HX + 5.5, KY + .5),
                       (TX + .5, KY + .5), (TX + 1.5, KY - .5), (TX + 1.5, KY - 1.5), (TX + 1.5, KY - 2.5),
                       (TX + 1.5, KY - 4.5)]              # (up the dais's middle, straight at the gate)

for x, y, t in ((GX + 4.6, GY + 11.4, "the BARBICAN"), (GX + 2.8, GY + 6.6, "the DRAWBRIDGE: up at the start, down 2.9 s of 4.7"),
                (GX + 3.4, GY + 2.9, "a plate, and the PORTCULLIS it raises"), (CX0 + .6, CY1 - 1.1, "the COURTYARD"),
                (SX + .2, CY0 + 1.5, "the ROCKING STAIR"), (SX - 4.5, CY0 - 4.8, "pop-up spikes"),
                (CX0 - 5.8, CY0 + .4, "pop-up spikes"), (SX + 1.5, CY0 - 4.2, "the BATTLEMENTS"),
                (CX0 - 4.6, KY - .3, "the ring KEY"), (CX0 + 2.4, KY + 1.6, "hay"), (DX - .6, KY + 3.3, "the DOOR (ring)"),
                (HX + .6, KY + 4.7, "the COG HALL: two quarter-turn tables over a pit"), (TX + 3.6, KY + 4, "the THRONE"),
                (CX0 - 11, BY + 2.4, "the TRAITOR'S BRIDGE to the cross KEY"), (TX + 3.8, KY - 3.6, "the TREASURY (cross): exit 1")):
    p.note(x, y, t)
p.windows = [(((CX0 + CX1) / 2.0, KY + .5), "the courtyard")]
p.legend = ["o + # x = a channel's glyph on its plate (white square), key (yellow disc), gate (orange) and bridge"]

if __name__ == "__main__":
    p.main(HERE, os.path.join(ROOT, "apps", "bonanza", "courses", "keep.bbc"))
