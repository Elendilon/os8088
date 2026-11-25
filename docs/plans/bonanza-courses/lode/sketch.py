#!/usr/bin/env python3
"""COURSE 6, LODESTONE GORGE (LODE): the sketch (wave 11's pipeline; ../LODE.md is the design sheet).  Host-only;
nothing in `make` runs it and it ships nothing.  ../penkit.py is the pen.

    python3 sketch.py [outdir]                  plan.png and iso.png
    python3 sketch.py --bbc [OUT] [--force]     the engine course (apps/bonanza/courses/lode.bbc)

STEEL's course, on DOWNHILL DECISION's steel exit: a SPIRAL into a quarry, the GREAT LODESTONE on an island in
its middle, in sight from the sirens' bridge on and reached last.  MAGNETS are its one new idea, and each
meeting turns them over: a HOIST that hauls steel up a ramp (they help), SIRENS that pull it off a bridge (they
hurt), a WALL of lodestones that holds it on a tilted ledge (they hold), the GANTRY it hovers under across
the moat (they fly), and the great lodestone, which hauls it up the last ramp into the goal (they bring it home).
REFINED (the step after the pen-in): the layout the engine's constraints left, LODE.md sections 10 - 12.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from penkit import Pen, DIRV

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))

HEAD = """
# Course 6 (LODE; docs/plans/bonanza-courses/LODE.md): LODESTONE GORGE, STEEL's course - a SPIRAL into a
# quarry round the GREAT LODESTONE, on an island in its middle.  The FLUME (an S of round channel between stone
# curbs, 6.5 units down), a HOIST (a magnet at a ramp's top hauls steel up it), the SIRENS (magnets across a gap
# that pull steel off a bridge), a ramp into the LODESTONE WALL (a tilted ledge a fence of magnets holds steel
# on), the SLAG gallery (a room to stop in), the GANTRY (a row of hanging magnets steel HOVERS under, over the
# moat), and the great lodestone's own hoist, into the goal.  REFINED (2026-11-25, the step after the pen-in):
# written by docs/plans/bonanza-courses/lode/sketch.py --bbc --force while the layout moves.  NOT in the build
# yet (no BZ_COURSES entry, no pathway pad).
course LODE "Lodestone Gorge"
guide                     # a REAL course: held to the course guide's checkable rules (G1, G3, G9 - G12)
width 104                 # 832 px: the reach runs from px 8 (the void off the gallery's west corner) to 791 (off the turn)
origin 272                # NOT free: the least the reach allows, so the picture's LEFT EDGE is 112 px from the gallery's
                          # pocket - the window cannot pan further left, which is what frames the gantry's flight with
                          # no pan (LODE.md section 2).  A wider picture takes `width`; the origin stays
ball steel
uses magnet
music lodestone           # its own song (2026-11-25): a work song in G dorian, every bar pulled back to one low G (LODE.md, "The song")
limit 99
target 60
"""

p = Pen("LODE", "Lodestone Gorge", HEAD)
for sec, rgb in (("A", (200, 170, 120)), ("B", (170, 150, 130)), ("C", (190, 160, 110)), ("P", (180, 160, 140)),
                 ("R", (200, 180, 130)), ("L", (160, 170, 190)), ("M", (120, 110, 130)), ("S", (150, 140, 150)),
                 ("Y", (200, 200, 120)), ("V", (240, 215, 120)), ("O", (120, 110, 130)), ("H", (215, 190, 130)),
                 ("N", (120, 110, 130))):
    p.col(sec, rgb)

# the headland, the pen, the bridge and turn, the wall's centre line and the gallery, the island's apron.  (The
# gantry's posts stand at 14.5: a hanging magnet's ceiling is a signed byte of px, so no post stands over 15.25 -
# LODE.md section 12, L2 - and the course cannot be raised)
ZA, ZB, ZC, ZL, ZS, ZV = 22.5, 16, 18, 13, 13, 12.5
BX = 43                                              # the bridge's end, the turn's first column
WX = BX + 2                                          # the wall's column
SX = 31                                              # the first siren's column (then every fourth)
GW = 30                                              # the gallery's west end: the runway's and the island's column
GE = GW + 7                                          # ...and its east end, where the wall's second leg begins
FX = GE - 1                                          # flag 1's column: the gallery's east entrance
RW = 2                                               # the runway's tiles
RIDGE = 0                                            # the pen-in's slag ridge, px (10): CUT - LODE.md section 11

# 1. THE HEADLAND and the FLUME: an S of round channel, 3 wide, 6.5 units down ---------------------------------
p.floor("A", 20, 4, 25, 8, ZA, "A: the HEADLAND, 5 x 4")
p.guard(20, 4, 25, 5, sides=["-y"])                  # railed all round but the flume's mouth (the mouth's flanks
p.guard(20, 4, 21, 8, sides=["-x"])                  # are the flume's curbs): one arrow held from the start ends in
p.guard(24, 4, 25, 8, sides=["+x"])                  # a corner or in the flume, never in a fall (the pen-in's two cut
p.start = (22, 5)                                    # corners and open front let all four single arrows roll it off)
# (3 wide and `round`, as DOWN's: a 2-wide corner threw steel over its lip at every speed the pen-in tried.)
# Its LAST leg is LEVEL: a chute ends in a TAPER, the channel rising to its lip in one tile, which steel cannot
# climb from rest.  With a slope behind it (the pen-in's half unit) a ball that came to rest there sat in a V and
# only rocking freed it (MEASURED: no arrow held, and no backing up).  Level, it rolls back along the channel,
# and one of "the pair held" and "back up, then the pair" works from every place (MEASURED, LODE.md section 3)
DEPTH = 6                                            # px (8 is DOWN's; at 6 the taper is climbed from a tile back)
C1, C2 = ZA - 5, ZB                                  # the lips at the two corners
p.chute(3, "round", DEPTH, [(22, 8, ZA), (22, 15, C1), (16, 15, C2), (16, 18, C2)])


def curb(x0, y0, x1, y1, z, z1=None, axis=None, note=""):
    """a CURB: a strip of wall beside the channel, half a unit proud of its lip (z, or z -> z1 along `axis`)"""
    if z1 is None:
        p.wall(x0, y0, x1, y1, z + 0.5, note=note)
        return
    a, b = (x0, x1) if axis == "x" else (y0, y1)
    p.rooms.append("wall  rect %3d %3d %3d %3d  ramp %s %d %d %g %g   # %s" % (x0, y0, x1, y1, axis, a, b, z + 0.5,
                                                                               z1 + 0.5, note))
    for x in range(x0, x1):
        for y in range(y0, y1):
            p.walls[(x, y)] = max(z, z1) + 0.5
            p.cells.pop((x, y), None)


# the CURBS: the whole flume runs between them.  Steel is at the cap by the first corner and climbs a bank: the
# pen-in had a railed catwalk outside each corner, and MEASURED there a player who steers late or early still
# went over the first corner's EAST lip and the middle leg's far bank (404 of 6,480 timings of the S).  A rail
# needs a floor to stand on and is cut into many occluder masks beside a curved channel; a low stone curb is a
# wall with a straight top (SPEC.md 130.35's "block rail")
curb(20, 8, 21, 9, ZA, note="the flume's curbs: the mouth's flanks")
curb(24, 8, 25, 9, ZA)
curb(20, 9, 21, 13, ZA, C1 + 1, "y", "the first leg's west curb, sloping with it")
curb(24, 9, 25, 14, ZA, C1, "y", "...and its east curb")
curb(20, 13, 21, 14, C1 + 1, note="(the far curb's end, at the first leg's lip)")
curb(24, 14, 25, 17, C1, note="the first corner: its east side")
curb(21, 17, 24, 18, C1, note="...and its outside")
curb(18, 17, 21, 18, C2, C1, "x", "the middle leg's near curb")
curb(18, 13, 20, 14, C2, C2 + (C1 - C2) * 2 / 3, "x", "...and its far curb")
curb(15, 13, 18, 14, C2, note="the second corner: its north side")
curb(14, 14, 15, 18, C2, note="...and its outside, down the last leg")
# 2. THE CATCH PEN: a railed room to stop in ------------------------------------------------------------------
p.floor("B", 14, 18, 24, 25, ZB, "B: the CATCH PEN, 10 x 7")
p.guard(14, 18, 15, 25, sides=["-x"])                # square and railed all round but the flume's mouth and the
p.guard(14, 24, 24, 25, sides=["+y"])                # hoist's foot (the pen-in's cut corner was a hole in the one
p.guard(23, 18, 24, 21, sides=["+x"])                # room steel arrives in at speed)
p.guard(23, 23, 24, 25, sides=["+x"])
# 3. THE HOIST: a magnet at the top of a ramp no steel ball climbs - it hauls the ball up (magnets HELP) -------
p.floor("H", 24, 21, 26, 23, ZB, "the hoist's foot, off the pen's east side")
p.ramp("H", "y", 25, 19, 26, 21, ZC, ZB, "H: the HOIST's ramp, 2 units in 2 tiles: steel stalls on it")
p.floor("H", 25, 18, 26, 19, ZC, "its top")
p.floor("M", 25, 17, 26, 18, ZC + 2, "the hoist's post")
p.magnet(25, 17, "+y", rng=3, strength=64)
p.guard(24, 22, 26, 23, sides=["+y"])
p.guard(25, 21, 26, 23, sides=["+x"])
p.guard(25, 19, 26, 21, sides=["-x", "+x"])          # the ramp railed both sides and the top's open side: the pull
p.guard(25, 18, 26, 19, sides=["-x"])                # is 448 a step at the top, and a ball that came in on a slant left
p.guard(24, 21, 25, 22, sides=["-y"])                # over the side (MEASURED: the arrows-only autopilot fell here).
                                                     # And the foot's back edge, a gap between the pen's rail and the ramp's
# 4. THE SIRENS: a 2-wide bridge, three magnets on pillars across a gap, pulling steel at the edge (they HURT) -
p.floor("C", 26, 18, BX, 20, ZC, "C: the SIRENS' bridge, %d x 2" % (BX - 26))
p.flag(26, 18, "steel", "flag 0")
for (x, y, face, s) in ((SX, 15, "+y", 16), (SX + 4, 22, "-y", 24), (SX + 8, 15, "+y", 32)):     # a tug, a pull, a hard pull (MEASURED)
    p.floor("O", x, y, x + 1, y + 1, ZC + 2, "a siren's pillar")
    p.magnet(x, y, face, rng=4, strength=s)
# 5. THE TURN and the ramp into the LODESTONE WALL (they HOLD) ------------------------------------------------
p.floor("P", BX, 18, BX + 3, 23, ZC, "P: the TURN, 3 x 5")
p.guard(BX, 18, BX + 3, 19, sides=["-y"])
p.guard(WX, 18, WX + 1, 23, sides=["+x"])            # the backstop: steel does not stop short
p.guard(BX, 20, BX + 1, 23, sides=["-x"])
p.guard(BX, 22, BX + 2, 23, sides=["+y"])
p.ramp("R", "y", WX, 23, WX + 1, 28, ZC, ZL, "R: the ramp, 5 units in 5 tiles, 1 wide and railed: the speed for the wall")
p.guard(WX, 23, WX + 1, 28, sides=["+x", "-x"])
p.floor("L", WX, 28, WX + 1, 33, ZL, "L: the ledge, 1 wide, level and railed")
p.guard(WX, 28, WX + 1, 33, sides=["+x", "-x"])
# the wall's legs tilt half a unit ABOUT THEIR CENTRE LINE (a quarter up on the lodestones' side, a quarter down on
# the open one), and the ledge, the corner and the gallery are level at that line: the ball crosses every join
# within a pixel of its height and never leaves the ground (the pen-in's legs hung a quarter under each join, and
# each was a 7-frame flight in the middle of a pan: G3)
p.ramp("L", "x", WX, 33, WX + 1, 39, ZL + 0.25, ZL - 0.25, "L: the LODESTONE WALL's first leg: tilted to its open side")
p.floor("L", WX, 39, WX + 1, 41, ZL, "the wall's corner")
p.guard(WX, 39, WX + 1, 41, sides=["+x", "+y"])      # the corner's backstop
p.guard(WX, 39, WX + 1, 40, sides=["-x"])            # (and its back cell's open side)
p.floor("L", GE + 6, 40, WX, 41, ZL, "the second leg's lead-in: level and railed, as the first leg's ledge is")
p.guard(GE + 6, 40, WX, 41, sides=["-y", "+y"])
p.ramp("L", "y", GE, 40, GE + 6, 41, ZL + 0.25, ZL - 0.25, "L: its second leg, walked up-left (-x)")
for y in range(33, 39):
    p.floor("M", WX - 1, y, WX, y + 1, ZL + 2, "a lodestone's post")
    p.magnet(WX - 1, y, "+x", strength=8)
for x in range(GE, GE + 6):
    p.floor("M", x, 39, x + 1, 40, ZL + 2, "a lodestone's post")
    p.magnet(x, 39, "+y", strength=8)
# 6. THE SLAG GALLERY: a railed room to stop in, flag 1 at its door ---------------------------------------------
p.floor("S", GW, 39, GE, 42, ZS, "S: the SLAG gallery, %d x 3" % (GE - GW))
p.guard(GW, 39, GW + 1, 42, sides=["-x"])
p.guard(GW, 41, GE, 42, sides=["+y"])
p.guard(GW + 1, 39, GE, 40, sides=["-y"])
p.guard(GE - 1, 41, GE, 42, sides=["+x"])            # (its east end beside the wall's leg: open in the pen-in)
if RIDGE:                                            # (the pen-in's ridge, 3 tiles from the flag: 46 occluder masks
    p.hump(GW + 3, 39, ZS, along="y", n=3, height=RIDGE, open_=True)    # and 1.1 KB - LODE.md section 11)
p.flag(FX, 40, "steel", "flag 1")
# 7. THE GANTRY: a railed runway, then five tiles of moat under hanging magnets (they FLY) ---------------------
RY = 39 - RW                                         # the runway's far end, the lane's first void row less one
p.floor("Y", GW, RY, GW + 1, 39, ZS, "Y: the RUNWAY, 1 wide, railed both sides: the ball leaves it straight")
p.guard(GW, RY, GW + 1, 39, sides=["-x", "+x"])
for y in range(RY - 5, RY):
    p.floor("N", GW - 1, y, GW, y + 1, ZS + 1.5, "the gantry's post")
    p.magnet(GW - 1, y, None, down="+x")
# 8. THE GREAT LODESTONE: an island in the middle of the spiral; its magnet hauls the ball up into the goal ----
AY = RY - 8                                          # the apron's back row
p.floor("V", GW - 2, AY, GW + 3, AY + 3, ZV, "V: the island's apron, 5 x 3")
# railed all round but the landing (the lane's end) and the ramp's foot, and the ramp railed both sides: the pen-in's
# apron had two cut corners and an open back, and its ramp open sides - MEASURED there, a ball that landed a quarter
# tile off the lane's centre and held straight on was hauled off the ramp's side, and 43 of 104 single arrows held
# from rest on the apron ended in a fall
p.guard(GW - 2, AY, GW - 1, AY + 3, sides=["-x"])
p.guard(GW + 2, AY, GW + 3, AY + 3, sides=["+x"])
p.guard(GW - 2, AY + 2, GW, AY + 3, sides=["+y"])
p.guard(GW + 1, AY + 2, GW + 3, AY + 3, sides=["+y"])
p.guard(GW - 2, AY, GW, AY + 1, sides=["-y"])
p.guard(GW + 1, AY, GW + 3, AY + 1, sides=["-y"])
p.ramp("V", "y", GW, AY - 3, GW + 1, AY, ZV + 3, ZV, "the last ramp, 3 units in 3 tiles, railed both sides")
p.guard(GW, AY - 3, GW + 1, AY, sides=["-x", "+x"])
p.floor("M", GW, AY - 5, GW + 1, AY - 4, ZV + 5, "the GREAT LODESTONE's post")
p.magnet(GW, AY - 5, "+y", rng=4, strength=104)
p.goal(GW - 1, AY - 4, GW + 2, AY - 3, ZV + 3)


def noocclude(p, keep=()):
    """SPEC.md 130.53: `noocclude` on the cells NO BALL IS IN - the void within 3 cells of the course (the band
    the tool cuts occluders for) less the FALL ZONE of every open edge, and the floors no ball can get onto (the
    wall's posts, the hoists' and the sirens' pillars: sections M and O.  NOT the gantry's posts, section N: a
    ball that waits under the gantry rises to the magnets' ceiling and can be steered onto them, LODE.md
    section 3).  An OPEN edge is one of a floor a ball can stand on (not a goal's: the course is over there)
    with no rail and no curb, the void across it; its fall zone is the cone a ball leaving it can cross before
    it is killed: ZONE_OUT cells out, as many to each side as it is out, at most 2 (the kill is 3 units under
    the lowest floor near, so off the bridge toward the island a ball at the cap crosses 3.6 tiles: MEASURED).
    `keep` is the gantry's lane, where the ball is in play.  A rail or a curb is a wall at every height, so a
    ball is in the void behind one only if it fell from an open edge nearby: most of the pen-in's 323 masks
    were cut for a ball behind a rail it cannot cross"""
    floors = set(p.cells)
    goals = {(x, y) for x0, y0, x1, y1, _z, _e, _h in p.goals for x in range(x0, x1) for y in range(y0, y1)}
    stand = {c for c in floors if p.sec.get(c) not in ("M", "O")} - goals
    railed = p.rail_edges()
    zone = set(keep)
    for (x, y) in stand:
        for side, (a, b) in DIRV.items():
            n = (x + a, y + b)
            if n in floors or n in p.walls or ((x, y), side) in railed:
                continue
            for i in range(0, ZONE_OUT):
                w = min(i + 1, 2)
                for j in range(-w, w + 1):
                    zone.add((n[0] + a * i - b * j, n[1] + b * i + a * j))
    band = {(x + i, y + j) for (x, y) in floors | set(p.walls) for i in range(-3, 4) for j in range(-3, 4)}
    band -= floors | set(p.walls)
    cells = (band - zone) | {c for c in floors if p.sec.get(c) in ("M", "O")}
    rows = {}
    for (x, y) in sorted(cells):
        rows.setdefault(y, []).append(x)
    runs = []                                    # (x0, x1, y) row runs, then stacked into rects
    for y in sorted(rows):
        xs = rows[y]
        s0 = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is None or x != prev + 1:
                runs.append((s0, prev + 1, y))
                s0 = x
            prev = x
    rects, open_ = [], {}
    for x0, x1, y in runs:
        k = (x0, x1)
        if k in open_ and open_[k][1] == y:
            open_[k][1] = y + 1
        else:
            if k in open_:
                rects.append((x0, open_[k][0], x1, open_[k][1]))
            open_[k] = [y, y + 1]
    rects += [(k[0], v[0], k[1], v[1]) for k, v in open_.items()]
    p.comment("the cells no ball is in (LODE.md section 11): the void no fall reaches, and the tiles of the posts no ball gets onto")
    for x0, y0, x1, y1 in sorted(rects, key=lambda r: (r[1], r[0])):
        p.raw("noocclude rect %d %d %d %d" % (x0, y0, x1, y1))
    return len(cells), len(rects)


ZONE_OUT = 4
noocclude(p, keep={(GW, y) for y in range(RY - 5, RY)})

p.clock(24, 6, ZA, "start")
p.clock(14, 19, ZB, "pen")
p.clock(WX, 18, ZC, "turn")
p.clock(GW + 2, AY + 1, ZV, "vault")

p.route = [(22.5, 5.5), (22.5, 8.5), (22.5, 15.5), (16.5, 15.5), (16.5, 18.5), (17.5, 21.5), (22.5, 21.5),
           (25.5, 21.5), (25.5, 18.5), (26.5, 18.5), (BX - 1, 19), (BX + 1.5, 20.5), (WX + 0.5, 23), (WX + 0.5, 28), (WX + 0.5, 40.5),
           (WX - 0.5, 40.5), (FX + 0.5, 40.5), (GW + 0.5, 40.5), (GW + 0.5, RY + 0.5), (GW + 0.5, AY + 1.5),
           (GW + 0.5, AY + 0.5), (GW + 0.5, AY - 3.5)]

for x, y, t in ((25.6, 5.5, "the HEADLAND"), (25.6, 11, "the FLUME: an S of channel between curbs, 6.5 units down"),
                (9.6, 26, "the CATCH PEN"), (14, 27.2, "the HOIST: a magnet hauls steel up the ramp"),
                (32.5, 16.6, "the SIRENS: three magnets pull steel at the edge"),
                (46.6, 20, "the TURN"), (46.6, 25, "the ramp"), (46.6, 35.5, "the LODESTONE WALL: magnets hold steel on the tilt"),
                (38, 42.6, "its second leg"), (24, 43.4, "the SLAG gallery: stop, flag 1"),
                (31.8, 37.6, "the RUNWAY"), (32, 34.3, "the GANTRY: 5 tiles of hover"),
                (33.5, 27, "the GREAT LODESTONE hauls the ball into the goal")):
    p.note(x, y, t)
p.windows = [((22.5, 6), "the start"), ((34, 19), "the sirens"), ((GW + 0.5, 35), "the gantry")]
p.legend = ["magenta M = a magnet (its field outlined), v = a hanging one; the magenta band = the flume"]

if __name__ == "__main__":
    p.main(HERE, os.path.join(ROOT, "apps", "bonanza", "courses", "lode.bbc"))
