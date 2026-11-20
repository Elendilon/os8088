#!/usr/bin/env python3
"""COURSE 2 (tutorial 2, working name HOP), attempt 1: the PAPER sketch
(wave 11's pipeline, the pen-in step).  Host-only; nothing in `make` runs it
and it ships nothing.  First Roll's sketch (../first/sketch.py) adapted:
FLOATING cells (faces 3 units deep, the owner's "for another course"), and
SPRINGS.  Tiles are tiles, heights are units (8 px), the pictures are the
game's projection drawn as plain blocks.  python3 sketch.py [outdir]"""
import os
import sys
from PIL import Image, ImageDraw

# --- the course, section by section ---------------------------------------
# floor(x0, y0, x1, y1, z) ; ramp(axis, x0, y0, x1, y1, z0, z1): z0 at the
# low-coordinate edge of `axis`, z1 at the high one.  Half-open tile rects.
CELLS = {}           # (wx, wy) -> (corner heights nw, ne, se, sw), section
SECTION = {}
RAILS = []           # (x0, y0, x1, y1) a guard rail along a tile edge
WALLS = []           # (x0, y0, x1, y1, z) a solid block
HOLES = set()
FLOATS = set()     # the FLOATING cells: their faces hang 3 units, not to the ground (`float`)
SPRINGS = []       # (wx, wy, gvz): SPEC.md 130.14's springs, drawn as a coil
ARCHES = []                                                  # (x0, y0, x1, y1, along, under): SPEC.md 130.39
# revision 8 (the owner's edit of the diagonal variant): half cells made VOID - (wx, wy, side): the start
# plateau's corners and its front corner on a diagonal, and the hill landings' outer corners
HALVES = []
NOTES = []           # (wx, wy, z, text)


OFF = 4             # the engine course's shift (bbc(), below)
ROOMS_TXT, CHUTE_TXT = [], []
FLOATING = False     # revision 3 (the owner): grounded columns; floating is a later, HARD course style


def floor(sec, x0, y0, x1, y1, z, float_=None):
    float_ = FLOATING if float_ is None else float_
    ROOMS_TXT.append("floor rect %3d %3d %3d %3d  flat %g   # %s" % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, z, sec))
    if float_:
        ROOMS_TXT.append(("@float", x0, y0, x1, y1))     # resolved in bbc(): only if a face hangs
        FLOATS.update((x, y) for x in range(x0, x1) for y in range(y0, y1))
    for x in range(x0, x1):
        for y in range(y0, y1):
            CELLS[(x, y)] = (z, z, z, z)
            SECTION[(x, y)] = sec


def ramp(sec, axis, x0, y0, x1, y1, z0, z1, float_=None):
    float_ = FLOATING if float_ is None else float_
    p0, p1 = (x0, x1) if axis == "x" else (y0, y1)
    ROOMS_TXT.append("floor rect %3d %3d %3d %3d  ramp %s %d %d %g %g   # %s"
                     % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, axis, p0 + OFF, p1 + OFF, z0, z1, sec))
    if float_:
        ROOMS_TXT.append(("@float", x0, y0, x1, y1))     # resolved in bbc(): only if a face hangs
        FLOATS.update((x, y) for x in range(x0, x1) for y in range(y0, y1))
    n = (x1 - x0) if axis == "x" else (y1 - y0)
    for x in range(x0, x1):
        for y in range(y0, y1):
            i = (x - x0) if axis == "x" else (y - y0)
            a, b = z0 + (z1 - z0) * i / n, z0 + (z1 - z0) * (i + 1) / n
            # corners: (x, y) (x+1, y) (x+1, y+1) (x, y+1)
            CELLS[(x, y)] = (a, b, b, a) if axis == "x" else (a, a, b, b)
            SECTION[(x, y)] = sec


CHUTE = {}          # (wx, wy) -> the height function of the chute it is part of


def chute(sec, ways, depth, wide=2):
    """a shaped channel, WIDE cells across (SPEC.md 130.28.4): 2-wide, its crease
    through the cell CORNERS `ways` [(x, y, lip z)]; 3-wide, through the CELLS
    `ways` (their centres), each inner way the middle of a 3 x 3 corner block.
    Its bottom `depth` units under the lip on the crease, rising as a parabola
    to the lip at its sides (one tile either side of a 2-wide crease, a tile
    and a half of a 3-wide's)"""
    CHUTE_TXT.append("chute %d round depth %d " % (wide, round(depth * 8))
                     + " ".join("way %d %d %g" % (x + OFF, y + OFF, z) for x, y, z in ways))
    if wide == 3:
        return _chute3(sec, ways, depth)
    segs, L = [], 0.0
    for (ax, ay, az), (bx, by, bz) in zip(ways, ways[1:]):
        n = abs(bx - ax) + abs(by - ay)
        segs.append((ax, ay, az, bx, by, bz, L, n))
        L += n

    def near(px, py):
        best = None
        for ax, ay, az, bx, by, bz, l0, n in segs:
            t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / (n * n)))
            qx, qy = ax + (bx - ax) * t, ay + (by - ay) * t
            dd = ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5
            if best is None or dd < best[0]:
                best = (dd, az + (bz - az) * t)
        return best

    def h(px, py):
        dd, lip = near(px, py)
        return lip - depth * (1 - min(dd, 1.0) ** 2)
    xs = [w[0] for w in ways]; ys = [w[1] for w in ways]
    for x in range(min(xs) - 1, max(xs) + 1):
        for y in range(min(ys) - 1, max(ys) + 1):
            if near(x + 0.5, y + 0.5)[0] <= 0.75:
                CELLS[(x, y)] = (h(x, y), h(x + 1, y), h(x + 1, y + 1), h(x, y + 1))
                SECTION[(x, y)] = sec
                CHUTE[(x, y)] = h


def _chute3(sec, ways, depth):
    """chute()'s 3-wide arm: the crease through the ways' cell centres"""
    cs = [(x + 0.5, y + 0.5, z) for x, y, z in ways]

    def near(px, py):
        best = None
        for (ax, ay, az), (bx, by, bz) in zip(cs, cs[1:]):
            n = abs(bx - ax) + abs(by - ay)
            t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / (n * n)))
            qx, qy = ax + (bx - ax) * t, ay + (by - ay) * t
            dd = ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5
            if best is None or dd < best[0]:
                best = (dd, az + (bz - az) * t)
        return best

    def h(px, py):
        dd, lip = near(px, py)
        return lip - depth * (1 - min(dd / 1.5, 1.0) ** 2)
    cells = set()
    for (ax, ay, _a), (bx, by, _b) in zip(ways, ways[1:]):      # each leg, way to way, 3 across
        for x in range(min(ax, bx) - (ax == bx), max(ax, bx) + 1 + (ax == bx)):
            for y in range(min(ay, by) - (ay == by), max(ay, by) + 1 + (ay == by)):
                cells.add((x, y))
    for x, y, _z in ways[1:-1]:                                 # each corner: the 3 x 3 block round its way
        cells.update((x + a, y + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
    for (x, y) in cells:
        CELLS[(x, y)] = (h(x, y), h(x + 1, y), h(x + 1, y + 1), h(x, y + 1))
        SECTION[(x, y)] = sec
        CHUTE[(x, y)] = h


def rail(x0, y0, x1, y1, style="block"):
    """a rail along a tile edge: a BLOCK rail (a wall tile) or a see-through GUARD rail (SPEC.md 130.35), the
    style a choice per rail (the course guide's G24); either takes the tile on the void side of the edge"""
    RAILS.append((x0, y0, x1, y1, style))


Z = 40                                   # the start's height, units (the course is DOWNHILL: the tool rebases)
THICK = 3
THICKS = ""
MARKS = []           # (wx, wy, kind, text): props the sketch does not model - drawn as markers
def mark(x, y, kind, text=""):
    MARKS.append((x, y, kind, text))

# =============================================================================
# DOWNHILL DECISION, attempt 1 (the owner, 2026-11-19): the tutorial's REWARD - SPEED, then a SPLIT two thirds
# of the way along (by tiles), where two archways force a CONVERSION: STEEL one way, GLASS the other, each to
# its own exit.  Grounded (no floating), the climbs up the screen and the drops down it (the guide's 1.10).
# =============================================================================
# 1. SPEED -------------------------------------------------------------------
import os as _os
SHAPE_N = int(_os.environ.get("DOWN_SHAPE_N", "1"))   # rev 7 (the owner, ON TRIAL): the shape N rows longer NORTH, the start moved with it
N = SHAPE_N
floor("A", 4, 4 - N, 5, 5 - N, Z)                                    # the start: ONE tile, guard rails round it
rail(4, 4 - N, 5, 4 - N, "guard"); rail(4, 4 - N, 4, 5 - N); rail(5, 4 - N, 5, 5 - N)   # (rev 4: the start tile keeps all three - a start must be SAFE)
# rev 6 (the owner, ON TRIAL): the line from the ramp through the corner chute into the hump run 3 wide all the
# way (docs/plans/bonanza-courses/CHUTE3.md).  CHUTE_W = 2 is rev 5's 2-wide line, with rev 7's SHAPE_N rows north
CHUTE_W = 3                                  # (rev 8: 3 wide, SHAPE_N 1 - the owner's pick of the two rev 7 variants)
if CHUTE_W == 2:
    ramp("R", "y", 4, 5 - N, 5, 10 - N, Z, Z - 10)           # a STEEP ramp, 2 units a tile (the most), railed
    floor("R", 4, 10 - N, 5, 11 - N, Z - 10)                 # its foot, flat, into the corner chute
    rail(4, 5 - N, 4, 11 - N)                                # (rev 5: the LEFT rail kept, the right one gone - it hid the ball at the spawn and down the ramp)
    chute("C", [(4, 11 - N, Z - 10), (4, 13, Z - 10), (8, 13, Z - 11)], 1.0)   # the CORNER: a banked shape turns it +x
else:
    ramp("R", "y", 3, 5 - N, 6, 10 - N, Z, Z - 10)           # the STEEP ramp, 3 wide (no flat foot: the chute's
    rail(3, 5 - N, 3, 10 - N)                                #   end taper is the foot); its LEFT rail, the right open (rev 5)
    chute("C", [(4, 10 - N, Z - 10), (4, 12, Z - 10), (7, 12, Z - 11)], 1.0, wide=3)   # the CORNER, 3 x 3, turns it +x
floor("H", 8, 11, 18, 14, Z - 11)                            # the HUMP RUN, now 3 wide (rev 2), unguarded, along +x
for hx in (10, 16):                                          # two humps, 2 long x 3 wide (rev 7: the first 2 west - the shape, 2 flats, the hump)
    for x in range(hx, hx + 2):
        for y in (11, 12, 13):
            CELLS[(x, y)] = (Z - 10, Z - 10, Z - 10, Z - 10)
    mark(hx + 1, 12.5, "hump", "hump")
ramp("D", "x", 18, 11, 20, 14, Z - 11, Z - 13)               # the DESCENT, 3 wide: gentle - mild - steep
ramp("D", "x", 20, 11, 23, 14, Z - 13, Z - 14.5)
ramp("D", "x", 23, 11, 25, 14, Z - 14.5, Z - 18.5)
floor("F", 25, 11, 27, 14, Z - 18.5)                         # the FUNNEL (rev 2): 3 x 3 flat, flag 0 in its middle;
floor("F", 27, 12, 28, 13, Z - 18.5)
mark(27.5, 11.5, "guide", ""); mark(27.5, 13.5, "guide", "")  # its last column's outer cells: DIAGONAL guides (EXTRA)
floor("B", 28, 12, 32, 13, Z - 18.5)                         # the BOOSTER CHUTE: 1 wide, block-railed, pads +x
rail(28, 12, 32, 12); rail(28, 13, 29, 13); rail(29, 13, 32, 13, "guard")   # (its FRONT see-through: a block hid the pads)
for x in range(29, 32):
    mark(x + 0.5, 12.5, "boost", "")
floor("L", 34, 10, 39, 15, Z - 23)                           # a WIDE GAP (x 32 - 33) and a DROP onto L: easy,
                                                             # unguarded, NO FLAG (a respawn there could never
                                                             # cross on); rubber BOUNCES on over a second gap
floor("X", 42, 8, 48, 17, Z - 26)                            # the HUB, large and safe (x 39 - 41 the gap; 6 wide: the width)
rail(42, 8, 48, 8); rail(48, 8, 48, 14); rail(48, 15, 48, 17)    # (rev 4: the front rails gone, to see it)
# 2. THE SPLIT: two exits out of the hub - EAST a STEEL pad, SOUTH a GLASS pad (rev 2: swapped, so the glass
#    leg's lift climbs up the screen in view; rev 3: no archways - a rubber ball that hops a pad dies on the
#    spikes or the membrane, which introduces both)
mark(47.5, 14.5, "steel", "steel pad")
mark(45.5, 15.5, "glass", "glass pad")
# 3a. STEEL (east, +x): SPIKES on the only path, a WATER SINK, MOMENTUM, the finish
floor("S", 48, 13, 52, 16, Z - 26)
for y in range(13, 16):
    for x in range(49, 51):
        mark(x + 0.5, y + 0.5, "spike", "")
rail(48, 13, 52, 13); rail(52, 13, 53, 13, "guard"); rail(48, 16, 52, 16, "guard")   # (rev 7: the FRONT a guard, the spikes seen through it) (over the water a GUARD: it seals and shows it) (rev 8: its last tile a guard too - beside S and the lower T, a two-height guard, SPEC.md 130.35.9)
floor("W", 52, 13, 53, 16, Z - 26)                           # the WATER column (3 units deep) across the path
for y in range(13, 16):
    mark(52.5, y + 0.5, "water", "")
# rev 11 (the owner): steel goes NORTH then WEST, with the course's LIFT (glass no longer needs it) - out of the
# water's EAST arch, north over a SPIKE CARPET (steel rolls over what kills the others), UP the lift 4, then west
# along the top, a momentum hump and a ramp down to the finish in the north-west.  Width 160 (1,280 px)
rail(53, 13, 53, 16, "guard")                                # the water's east face a guard (its front, +y, the arch)
floor("T", 52, 16, 56, 17, Z - 29)                           # the ARCH's exit (+y, as before) at the bed, a pier east
floor("T", 56, 7, 60, 17, Z - 29)                            # the run NORTH, 4 wide
for y in range(8, 13):
    for x in range(56, 60):
        mark(x + 0.5, y + 0.5, "spike", "")
mark(57.5, 6.5, "lift", "LIFT up 4")                         # the LIFT, at the run's north end
floor("M", 30, 3, 59, 6, Z - 25)                             # the TOP, west, a momentum hump (EXTRA) on it
floor("G", 24, 2, 30, 7, Z - 25)                             # FINISH 1, steel (exit 0), in the north-west
# 3b. GLASS (south, +y): a WEB BRIDGE, then (rev 10, the owner) WEST at the bridge's height - no lift (it goes to
# steel, which climbs): a WEB MAZE of solid islands joined by ONE-cell membrane links (glass-only, easy to
# steer), the old plateau its first island; a FLOAT pool (water, no arch) as one crossing; a BOOST off the far
# bank; then STAIRS with two valid-looking ways (glass shatters from 3): a couple of steps down, then the
# straight way 3, 1, 1 and the way round 2, 1, 2
floor("K", 45, 17, 46, 22, Z - 26)                           # the WEB BRIDGE: 1 wide, a glass-only MEMBRANE over the void
for y in range(17, 22):
    mark(45.5, y + 0.5, "crack", "")
floor("P", 43, 22, 47, 25, Z - 26)                           # the bridge's landing (a flag)
LINKS = [(42, 23), (40, 21), (38, 19), (36, 21), (34, 23), (30, 23), (40, 25), (32, 21)]
for lx, ly in LINKS:                                         # the maze's LINKS: one membrane cell each
    floor("K", lx, ly, lx + 1, ly + 1, Z - 26)
    mark(lx + 0.5, ly + 0.5, "crack", "")
# rev 12 (the owner): every island 3 x 3, and the way through WINDS - north off island 1, west, south, west to
# the junction - with two islands that lead nowhere
floor("Q", 39, 22, 42, 25, Z - 26)                           # island 1 (a flag): north to N1, south to D1
floor("Q", 39, 18, 42, 21, Z - 26)                           # N1: west to W1
floor("Q", 35, 18, 38, 21, Z - 26)                           # W1: south to W2
floor("Q", 35, 22, 38, 25, Z - 26)                           # W2: west to the junction
floor("Q", 31, 22, 34, 25, Z - 26)                           # the JUNCTION (a flag): west to the pool, north to D2
floor("Q", 39, 26, 42, 29, Z - 26)                           # D1, a DEAD END
floor("Q", 31, 18, 34, 21, Z - 26)                           # D2, a DEAD END
floor("W", 20, 22, 25, 25, Z - 26)                           # the FLOAT pool, 3 deep, no arch: glass rides across
rail(20, 22, 25, 22, "guard")                                # a guard rail seals it north; SOUTH (rev 12: the bank
floor("Y", 20, 25, 25, 26, Z - 28)                           #   gone) a LEDGE 2 under the water: it seals the column
                                                             #   (steel's bed rule), the water's side is seen over it,
                                                             #   and a glass ball off the water's edge drops onto it
                                                             #   and can't climb back - no way round
floor("Y", 25, 22, 30, 26, Z - 26)                           # the east bank, where the junction's link lands
for x in range(20, 25):
    for y in range(22, 25):
        mark(x + 0.5, y + 0.5, "water", "")
floor("Y", 17, 22, 20, 25, Z - 26)                           # the far bank (a flag), and its BOOST south
mark(18.5, 24.5, "boost", "")
floor("Z", 17, 28, 21, 31, Z - 27)                           # the STAIR platform past a 3-tile gap, 1 down,
floor("Z", 21, 28, 23, 31, Z - 28)                           #   and a second step: the FORK
floor("Z", 23, 28, 25, 30, Z - 31)                           # the STRAIGHT way: 3 (glass shatters),
floor("Z", 25, 28, 27, 30, Z - 32)                           #   1, then 1 onto the finish
floor("Z", 21, 31, 23, 33, Z - 30)                           # the way ROUND: 2,
floor("Z", 23, 31, 25, 34, Z - 31)                           #   1, then 2 onto the finish
floor("V", 27, 28, 33, 30, Z - 33)                           # FINISH 2, glass (exit 1): an L round the two ways
floor("V", 25, 30, 33, 34, Z - 33)
GOAL = {(x, y) for x in range(24, 26) for y in range(2, 7)} | {(x, y) for x in range(31, 33) for y in range(28, 34)}

# the PROPS the sketch does not model, as the engine's statements (world cells: sketch + OFF)
def _w(x):
    return x + OFF
EXTRA = [
    "# the funnel's diagonal guides: split cells, the floor's half inside, a wall's half outside (SPEC.md 130.24.4)",
    "floor half left tile %d %d  flat %g" % (_w(27), _w(11), Z - 18.5),
    "wall  half right tile %d %d  flat %g" % (_w(27), _w(11), Z - 16.5),
    "floor half up tile %d %d  flat %g" % (_w(27), _w(13), Z - 18.5),
    "wall  half down tile %d %d  flat %g" % (_w(27), _w(13), Z - 16.5),
    "# the hump run's two humps: ridges across its 3 rows (the hump course's back hump's kind, SPEC.md 130.44)",
    "hump %d %d %g along y 3 open height 8" % (_w(11), _w(11), Z - 11),
    "hump %d %d %g along y 3 open height 8" % (_w(17), _w(11), Z - 11),
    "# the BOOSTER chute's pads (SPEC.md 130.40)",
] + ["prop boost %d %d face +x strength 40" % (_w(x), _w(12)) for x in range(29, 32)] + [   # (three: the first tile's block hid a fourth)
    "# the split: a pad at each exit (no archways: a rubber ball that hops one dies on what follows)",
    "pad steel %d %d" % (_w(47), _w(14)),        # (off the arrival line; rev 4: one pad again, the owner)
    "pad glass %d %d" % (_w(45), _w(15)),        # (rev 4: one north)
    "# steel: SPIKES across the only path (SPEC.md 130.38), a WATER column 3 deep, out of its front ARCH",
    "prop spikes %d %d %d %d" % (_w(49), _w(13), _w(51), _w(16)),      # (two rows: a spiked cell never touches water)
    "water rect %d %d %d %d top %g bed %g" % (_w(52), _w(13), _w(53), _w(16), Z - 26, Z - 29),
    "arch %d %d +y guard" % (_w(52), _w(15)),     # (rev 8: the FRONT edge guarded - rubber and glass stay on the water; steel sinks under the rail and out, SPEC.md 130.35.10)
    "# glass: the MEMBRANE bridge, thin (glass-only, SPEC.md 130.38), and the LIFT (SPEC.md 130.12.6.4)",
    "prop membrane %d %d %d %d" % (_w(45), _w(17), _w(46), _w(22)),
    "# glass's maze (rev 10): one-cell membrane LINKS, the FLOAT pool (water, no arch), the far bank's BOOST",
] + ["prop membrane %d %d %d %d" % (_w(lx), _w(ly), _w(lx + 1), _w(ly + 1)) for lx, ly in LINKS] + [
    "water rect %d %d %d %d top %g bed %g" % (_w(20), _w(22), _w(25), _w(25), Z - 26, Z - 29),
    "prop boost %d %d face +y strength 40" % (_w(18), _w(24)),
    "# steel (rev 11): the SPIKE CARPET north, the LIFT up 4, a ridge hump across the top, 8 px",
    "prop spikes %d %d %d %d" % (_w(56), _w(8), _w(60), _w(13)),
    "prop platform %d %d 4" % (_w(57), _w(6)),
    "hump %d %d %g along y 3 open height 8" % (_w(48), _w(3), Z - 25),
]
GOAL_RECTS = [(24, 2, 26, 7, Z - 25, 0, "steel"), (31, 28, 33, 34, Z - 33, 1, "glass")]

START = (4.5, 4.5 - N)
FLAGS = [(26.5, 12.5, "flag 0", "rubber"), (45.5, 12.5, "flag 1", "rubber"), (44.5, 23.5, "flag 2", "glass"),
         (40.5, 23.5, "flag 3", "glass"), (32.5, 23.5, "flag 4", "glass"), (18.5, 23.5, "flag 5", "glass"),
         (55.5, 4.5, "flag 6", "steel")]       # (rev 4: no flag at steel's entrance; one on the lift's top too)
CLOCKS = [(6.5, 4.5 - N, Z, "start", "block"), (46.5, 7.5, Z - 24.5, "hub", "block"), (23.5, 4.5, Z - 23.5, "steel finish", "block"),
          (33.5, 31.5, Z - 31.5, "glass finish", "block")]
FRAMES = {}
PLACED = {}
SIGNS = []
ROUTE = [(4.5, 4.5 - N), (4.5, 8.5 - N), (8.5, 12.5), (18, 12.5), (25, 12.5), (28, 12.5), (32, 12.5), (37, 12.5),
         (45, 12.5), (46, 14.5), (48, 14.5), (52.5, 14.5), (52.5, 16.5), (57.5, 16.5), (57.5, 9), (57.5, 7.5), (57.5, 4.5),
         (47, 4.5), (38, 4.5), (26, 4.5)]
ROUTE2 = [(45.5, 12.5), (45.5, 17), (45.5, 22), (44.5, 23.5), (40.5, 23.5), (40.5, 19.5), (36.5, 19.5), (36.5, 23.5),
          (32.5, 23.5), (27, 23.5),
          (22, 23.5), (18.5, 23.5), (18.5, 29.5), (22, 29.5), (22, 32), (24, 32.5), (27, 32), (32, 31)]
LABELS = [(4.5, 4.5, "start (1 tile)"), (4.5, 7, "STEEP ramp"), (5, 12, "shape corner"), (12, 12.5, "hump run"),
          (21, 12.5, "3 inclines"), (26, 12, "funnel+flag"), (29, 12.5, "BOOSTER chute"), (33, 12.5, "wide gap+drop"),
          (36, 12.5, "landing (no flag)"), (40, 12.5, "bounce gap"), (45, 11, "HUB"), (47.5, 14, "steel pad"),
          (50, 14.5, "spikes"), (52.5, 14, "water sink"), (58, 10, "spike carpet"), (57.5, 6, "lift"), (48, 2.5, "hump"), 
          (25, 1.5, "FINISH steel"), (45.5, 16, "glass pad"), (45.5, 19, "web bridge"), (40, 22, "island 1"), (40, 18, "N1"), (36, 18, "W1"), (36, 22, "W2"), (32, 22, "junction"), (40, 26, "D1"), (32, 18, "D2"),
          (22, 22.5, "FLOAT pool"), (18, 22, "bank+boost"), (17, 28, "stairs"), (23, 27, "3"), (21, 32, "2"), (29, 31, "FINISH glass")]

# --- drawing ----------------------------------------------------------------
SECCOL = {k: v for k, v in zip("ARCHDBLXSWTMGNKPQYZVF", [(120, 200, 120), (200, 200, 120), (150, 210, 200),
          (240, 200, 150), (200, 180, 140), (240, 160, 160), (240, 240, 140), (210, 210, 210), (170, 170, 190),
          (120, 160, 240), (180, 180, 200), (200, 170, 140), (250, 250, 250), (150, 230, 240), (200, 230, 250),
          (170, 220, 230), (160, 220, 210), (150, 200, 240), (240, 150, 150), (250, 250, 250), (220, 200, 150)])}


def zat(wx, wy):
    c = CELLS.get((int(wx), int(wy)))
    if not c:
        return 0
    fx, fy = wx - int(wx), wy - int(wy)
    nw, ne, se, sw = c
    return (nw * (1 - fx) * (1 - fy) + ne * fx * (1 - fy) + se * fx * fy + sw * (1 - fx) * fy)


def plan(out):
    S = 18
    xs = [k[0] for k in CELLS] + [w[2] for w in WALLS]
    ys = [k[1] for k in CELLS] + [w[3] for w in WALLS]
    W, H = (max(xs) + 3) * S, (max(ys) + 3) * S
    im = Image.new("RGB", (W, H), (20, 20, 30))
    d = ImageDraw.Draw(im)
    for (x, y), c in CELLS.items():
        base = SECCOL[SECTION[(x, y)]]
        k = 0.55 + 0.45 * (sum(c) / 4) / Z
        col = tuple(int(v * k) for v in base)
        if (x, y) in HOLES:
            col = (0, 0, 0)
        if (x, y) in GOAL:
            col = (255, 255, 255) if (x + y) % 2 else (40, 40, 40)
        d.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1], fill=col, outline=(60, 60, 70))
        if (x, y) in CHUTE:
            dep = min(c)
            d.text((x * S + 5, y * S + 3), "~", fill=(0, 0, 0))
        elif c[0] != c[2] or c[1] != c[3]:
            d.text((x * S + 4, y * S + 3), "v" if c[3] < c[0] else ">", fill=(0, 0, 0))
    for x0, y0, x1, y1, z in WALLS:
        d.rectangle([x0 * S, y0 * S, x1 * S - 1, y1 * S - 1], fill=(90, 70, 70))
    for x0, y0, x1, y1, style in RAILS:
        d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=(255, 220, 0), width=3)
    d.line([(x * S, y * S) for x, y in ROUTE], fill=(255, 60, 60), width=2)
    d.line([(x * S, y * S) for x, y in ROUTE2], fill=(120, 240, 255), width=2)
    for x, y, kind, t in MARKS:
        d.ellipse([x * S - 3, y * S - 3, x * S + 3, y * S + 3], fill={"steel": (150, 150, 170),
                  "glass": (120, 240, 255), "spike": (255, 60, 60), "water": (60, 120, 255), "boost": (255, 160, 0),
                  "crack": (255, 255, 255), "lift": (255, 0, 255), "arch": (255, 220, 0), "hump": (255, 255, 255), "guide": (255, 220, 0)}[kind])
    for x, y, z, f in PLACED.values():
        d.ellipse([x * S - 7, y * S - 7, x * S + 7, y * S + 7], outline=(0, 255, 255), width=2)
    for x, y, t, _b in FLAGS:
        d.polygon([(x * S, y * S - 8), (x * S + 10, y * S - 4), (x * S, y * S)], fill=(255, 80, 200))
    d.text((START[0] * S - 3, START[1] * S - 5), "S", fill=(255, 255, 255))
    for x, y, t in LABELS:
        d.text((x * S + 8, y * S - 14), t, fill=(255, 255, 255))
    d.text((6, H - 16), "plan: +wx right, +wy down; yellow = guard rails, open edges drop to the void; "
           "red = route; cyan = clocks; pink = flags", fill=(220, 220, 220))
    im.save(out)


def iso(out):
    def P(wx, wy, z):
        return 16 * (wx - wy), 8 * (wx + wy) - 8 * z
    pts = [P(x + a, y + b, cz) for (x, y), c in CELLS.items() for a, b, cz in
           ((0, 0, c[0]), (1, 0, c[1]), (1, 1, c[2]), (0, 1, c[3]))]
    minx = min(p[0] for p in pts) - 200
    maxx = max(p[0] for p in pts) + 200
    miny = min(p[1] for p in pts) - 60
    maxy = max(p[1] for p in pts) + 160
    minx, maxx, miny, maxy = int(minx), int(maxx), int(miny), int(maxy)
    W, H = maxx - minx, maxy - miny
    im = Image.new("RGB", (W, H), (10, 10, 25))
    d = ImageDraw.Draw(im)

    def Q(wx, wy, z):
        x, y = P(wx, wy, z)
        return x - minx, y - miny
    ground = Z - 32 - 3
    items = [((x, y), c, False) for (x, y), c in CELLS.items()]
    for x0, y0, x1, y1, z in WALLS:
        for x in range(x0, x1):
            for y in range(y0, y1):
                items.append(((x, y), (z, z, z, z), True))
    items.sort(key=lambda it: (it[0][0] + it[0][1], it[0][0]))
    for (x, y), c, wall in items:
        nw, ne, se, sw = c
        top = [Q(x, y, nw), Q(x + 1, y, ne), Q(x + 1, y + 1, se), Q(x, y + 1, sw)]
        base = (110, 90, 90) if wall else SECCOL[SECTION[(x, y)]]
        if (x, y) in HOLES:
            base = (0, 0, 0)
        if (x, y) in GOAL:
            base = (250, 250, 250) if (x + y) % 2 else (50, 50, 50)
        # the two faces the camera sees: the +y face (left) and the +x face (right); a FLOATING cell's
        # hang 3 units, every other one's to the ground
        gnd = min(c) - 3 if (x, y) in FLOATS else ground
        d.polygon([Q(x, y + 1, sw), Q(x + 1, y + 1, se), Q(x + 1, y + 1, gnd), Q(x, y + 1, gnd)],
                  fill=tuple(v // 2 for v in base))
        d.polygon([Q(x + 1, y, ne), Q(x + 1, y + 1, se), Q(x + 1, y + 1, gnd), Q(x + 1, y, gnd)],
                  fill=tuple(v * 2 // 3 for v in base))
        if (x, y) in CHUTE and not wall:
            hf, k = CHUTE[(x, y)], 4
            for i in range(k):
                for j in range(k):
                    a0, b0, a1, b1 = x + i / k, y + j / k, x + (i + 1) / k, y + (j + 1) / k
                    zz = [hf(a0, b0), hf(a1, b0), hf(a1, b1), hf(a0, b1)]
                    sh = 0.75 + 0.25 * (zz[1] + zz[2] - zz[0] - zz[3] + 2) / 4
                    col = tuple(min(255, int(v * sh)) for v in base)
                    d.polygon([Q(a0, b0, zz[0]), Q(a1, b0, zz[1]), Q(a1, b1, zz[2]), Q(a0, b1, zz[3])], fill=col)
        else:
            d.polygon(top, fill=base, outline=tuple(v * 3 // 4 for v in base))
    for x0, y0, x1, y1, style in RAILS:
        n = max(abs(x1 - x0), abs(y1 - y0)) * 2
        seg = []
        for i in range(n + 1):
            wx, wy = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
            e = 1e-3
            zz = max(zat(wx + a, wy + b) for a in (-e, e) for b in (-e, e))
            seg.append(Q(wx, wy, zz + 2))
            d.line([Q(wx, wy, zz), Q(wx, wy, zz + 2)], fill=(200, 170, 0), width=1)
        d.line(seg, fill=(255, 220, 0), width=2)
    WALLCELLS = {(x, y) for x0, y0, x1, y1, _ in WALLS for x in range(x0, x1) for y in range(y0, y1)}
    bare = im.copy()                       # the course alone: the clocks' backdrop test
    rx = [Q(x, y, zat(x, y))[0] for x, y in ROUTE]
    mid = int((min(rx) + max(rx)) // 2)
    BACK = {}
    for i, (x, y, z, name, kind) in enumerate(CLOCKS):
        PLACED[i] = (x, y, z + 4, name)               # the head stands about 4 units over its pillar's floor
        cx, cy = Q(x, y, z + 6)
        cx, cy = int(cx), int(cy)
        BACK[i] = all(bare.getpixel((px, py)) == (10, 10, 25)
                      for px in range(cx - 11, cx + 12, 2) for py in range(cy - 20, cy + 3, 2))
    MC = {"steel": (150, 150, 170), "glass": (120, 240, 255), "spike": (255, 60, 60), "water": (60, 120, 255),
          "boost": (255, 160, 0), "crack": (255, 255, 255), "lift": (255, 0, 255), "arch": (255, 220, 0),
          "hump": (255, 255, 255), "guide": (255, 220, 0)}
    for x, y, kind, t in MARKS:
        bx, by = Q(x, y, zat(x, y))
        c = MC[kind]
        if kind == "spike":
            d.polygon([(bx - 4, by + 2), (bx + 4, by + 2), (bx, by - 6)], fill=c)
        elif kind == "boost":
            d.line([(bx - 6, by - 3), (bx, by), (bx - 6, by + 3)], fill=c, width=2)
        elif kind == "crack":
            d.line([(bx - 6, by - 2), (bx + 6, by + 2)], fill=c); d.line([(bx - 3, by + 2), (bx + 3, by - 2)], fill=c)
        elif kind == "guide":
            d.polygon([(bx - 12, by - 2), (bx + 12, by - 2), (bx + 12, by - 14)], fill=c)
        elif kind == "arch":
            d.arc([bx - 14, by - 30, bx + 14, by + 2], 180, 360, fill=c, width=3)
        elif kind == "lift":
            d.rectangle([bx - 16, by - 4, bx + 16, by + 4], outline=c, width=2)
            d.line([(bx, by - 4), (bx, by - 32)], fill=c, width=2)
        else:
            d.ellipse([bx - 6, by - 4, bx + 6, by + 4], fill=c, outline=(0, 0, 0))
        if t:
            d.text((bx + 8, by - 18), t, fill=c)
    rz, pts = Z, []
    for x, y in ROUTE2:
        if (int(x), int(y)) in CELLS:
            rz = zat(x, y)
        pts.append(Q(x, y, rz + 1))
    d.line(pts, fill=(120, 240, 255), width=2)
    rz, pts = Z, []
    for x, y in ROUTE:
        if (int(x), int(y)) in CELLS:
            rz = zat(x, y)
        pts.append(Q(x, y, rz + 1))
    d.line(pts, fill=(255, 60, 60), width=2)
    for i, (x, y, z, name) in PLACED.items():
        cx, cy = Q(x, y, z + 2)
        d.rectangle([cx - 3, cy, cx + 3, cy + 40], fill=(120, 100, 80), outline=(70, 60, 50))
        d.ellipse([cx - 9, cy - 18, cx + 9, cy], fill=(0, 200, 220), outline=(255, 255, 255))
        d.text((cx - 12 - 6 * len(name), cy - 14), name, fill=(0, 255, 255))
        d.text((cx + 12, cy - 14), "void behind" if BACK[i] else "art behind", fill=(120, 120, 160))
    for x, y, gvz in SPRINGS:                   # a SPRING: a coil on its cell
        bx, by = Q(x + 0.5, y + 0.5, zat(x + 0.5, y + 0.5))
        for k in range(4):
            d.ellipse([bx - 7, by - 3 - 4 * k, bx + 7, by + 3 - 4 * k], outline=(255, 120, 0), width=2)
    for x, y, t, _b in FLAGS:
        bx, by = Q(x, y, zat(x, y))
        d.line([bx, by, bx, by - 20], fill=(255, 255, 255))
        d.polygon([(bx, by - 20), (bx + 10, by - 16), (bx, by - 12)], fill=(255, 80, 200))
    sx, sy = Q(*START, Z)
    d.ellipse([sx - 8, sy - 16, sx + 8, sy], fill=(255, 140, 0))
    for x, y, t in LABELS:
        lx, ly = Q(x, y, zat(x, y))
        d.text((lx + 12, ly - 6), t, fill=(255, 255, 255))
    # the CGA window (320 x 200) at three places, and the no-pan band: the
    # route's px span against the camera's dead zone (160 px on the CGA)
    for i, (x, y) in enumerate((ROUTE[0], ROUTE[9], ROUTE[-1])):
        _, cy = Q(x, y, zat(x, y))
        d.rectangle([mid - 160, cy - 100, mid + 160, cy + 100], outline=(0, 255, 255))
    d.line([mid - 80, 0, mid - 80, H], fill=(70, 70, 120))
    d.line([mid + 80, 0, mid + 80, H], fill=(70, 70, 120))
    d.text((8, 8), "route px span %d (CGA dead zone 160); course %d lines tall; cyan boxes = one CGA "
           "window at the start, the hub and the steel finish" % (max(rx) - min(rx), H - 220), fill=(220, 220, 220))
    im.save(out)
    return max(rx) - min(rx), H


def route_len():
    L = 0
    for (a, b), (c, e) in zip(ROUTE, ROUTE[1:]):
        L += ((c - a) ** 2 + (e - b) ** 2) ** 0.5
    return L


# --- the first draft of the engine's course ---------------------------------
# python3 sketch.py --bbc OUT.bbc writes the course as BONANZA's text course
# (SPEC.md 130.10.3) ONCE, to start the engine work from the paper design;
# after that the .bbc is the source and is edited by hand.  Every tile moves
# by OFF so walls and clock pillars stay inside 3 .. 252.  A rail becomes a
# WALL tile on the void side of its edge, 2 units over the floor it guards.

HEAD_TXT = """
# Course 3 (DOWN; docs/plans/bonanza-courses/DOWN.md): DOWNHILL DECISION, the tutorial's reward - SPEED, then a
# SPLIT where a pad converts the ball: STEEL east (spikes, a water sink) to exit 0, GLASS south (a membrane bridge,
# a lift, a choice of stairs) to exit 1.  Written by docs/plans/bonanza-courses/down/sketch.py --bbc --force
# while the layout moves.
course DOWN "Downhill Decision"
guide                     # a REAL course: held to the course guide's checkable rules
width 160
origin 304                # 1,280 px (SPEC.md 130.10.4.2): steel's north-west leg
uses boost spike water
ball rubber
music trial               # the owner: Bounce Trial, kept for course 3 (its speaker ring fix: spkring)
target 60
"""


def bbc(out):
    if os.path.exists(out) and "--force" not in sys.argv:
        sys.exit("sketch.py: %s exists - the course is edited by hand from here on; --force to re-emit a "
                 "re-laid revision (every hand-made line is in HEAD_TXT below or is lost)" % out)
    L = HEAD_TXT.strip("\n").split("\n") + [""]
    L.append("# rooms (the sketch's sections)")
    rooms_at = len(L)
    L.append("")
    L.append("# the chute (SPEC.md 130.28): unfenced, its shape guides")
    L += CHUTE_TXT
    L.append("")
    L.append("# rails: block rails (wall tiles) on the void side of each railed edge")
    walls, guards = {}, set()
    for x0, y0, x1, y1, style in RAILS:
        if y0 == y1:
            for x in range(min(x0, x1), max(x0, x1)):
                a, b = (x, y0 - 1), (x, y0)
                inner, outer = (a, b) if a in CELLS else (b, a)
                if inner in CELLS and outer not in CELLS:
                    walls[outer] = max(walls.get(outer, -99), max(CELLS[inner]) + 2)
                    if style == "guard":
                        guards.add(outer)
        else:
            for y in range(min(y0, y1), max(y0, y1)):
                a, b = (x0 - 1, y), (x0, y)
                inner, outer = (a, b) if a in CELLS else (b, a)
                if inner in CELLS and outer not in CELLS:
                    walls[outer] = max(walls.get(outer, -99), max(CELLS[inner]) + 2)
                    if style == "guard":
                        guards.add(outer)
    for x0, y0, x1, y1, z in WALLS:
        for x in range(x0, x1):
            for y in range(y0, y1):
                walls[(x, y)] = max(walls.get((x, y), -99), z)
    solid = set(CELLS) | set(walls)
    rooms = []
    for r in ROOMS_TXT:                     # a float only where a visible (+x or +y) face hangs over the void
        if isinstance(r, tuple):
            _t, x0, y0, x1, y1 = r
            if any((x + 1, y) not in solid or (x, y + 1) not in solid
                   for x in range(x0, x1) for y in range(y0, y1)):
                rooms.append("float rect %3d %3d %3d %3d%s" % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, THICKS))
        else:
            rooms.append(r)
    L[rooms_at:rooms_at] = rooms
    taken = {(int(x), int(y)) for x, y, _z, _n, kind in CLOCKS if kind == "block"}
    for (x, y), z in sorted(walls.items()):
        if (x, y) in taken:                     # a clock stands on this block: its tile is the clock's
            continue
        if (x, y) in guards:
            L.append("guard tile %3d %3d                # see-through" % (x + OFF, y + OFF))
        else:
            L.append("wall  tile %3d %3d  flat %g" % (x + OFF, y + OFF, round(z * 2) / 2))
            if (any((x + a, y + b) in FLOATS for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                    and ((x + 1, y) not in solid or (x, y + 1) not in solid)):
                L.append("float tile %3d %3d%s                # (a floating island's rail)" % (x + OFF, y + OFF, THICKS))
    L.append("")
    for (x, y) in sorted(HOLES):
        L.append("hole  tile %d %d" % (x + OFF, y + OFF))
    for x, y, side in HALVES:
        L.append("hole  half %s tile %d %d          # a diagonal corner" % (side, x + OFF, y + OFF))
    for x, y, gvz in SPRINGS:
        L.append("spring %d %d %d                      # SPEC.md 130.14: thrown up, away from the camera" % (x + OFF, y + OFF, gvz))
    for x0, y0, x1, y1, along, under in ARCHES:
        L.append("archway rect %d %d %d %d along %s under %g   # SPEC.md 130.39: a Hop passes under it"
                 % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, along, under))
    L.append("")
    L += EXTRA
    L.append("")
    for x0, y0, x1, y1, gz, ex, what in GOAL_RECTS:
        L.append("goal  rect %d %d %d %d  flat %g%s   # the %s finish" % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, gz,
                                                                   " exit %d" % ex if ex else "", what))
    L.append("start %d %d" % (int(START[0]) + OFF, int(START[1]) + OFF))
    for x, y, t, ball in FLAGS:
        L.append("checkpoint %d %d ball %s   # %s" % (int(x) + OFF, int(y) + OFF, ball, t))
    L.append("")
    L.append("# clocks (the owner's mark-ups): a tile level with the path one block out, or on top of a block")
    for x, y, z, name, kind in CLOCKS:
        px, py = int(x) + OFF, int(y) + OFF
        L.append("floor tile %d %d  flat %g   # the %s clock's tile (%s)" % (px, py, z, name, {
            "tile": "level with the path, one block out", "block": "on top of the rail block it replaces",
            "float": "a lone floating pillar"}[kind]))
        if kind == "float":                     # (a block's clock stands on its column, grounded: revision 6)
            L.append("float tile %d %d%s" % (px, py, THICKS))
        L.append("clock %d %d%s" % (px, py, " frame %s" % FRAMES[name] if name in FRAMES else ""))
    L.append("")
    L.append("# the autopilot's route")
    for x, y in ROUTE:
        if (int(x), int(y)) not in CHUTE and (int(x), int(y)) in CELLS:   # (none on a chute or over a gap)
            L.append("way %d %d" % (int(x) + OFF, int(y) + OFF))
    open(out, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--bbc"]:
        import tempfile, os
        fd, tmp = tempfile.mkstemp(suffix=".png"); os.close(fd); iso(tmp); os.remove(tmp)
        bbc(sys.argv[2])
        sys.exit(0)
    o = sys.argv[1] if len(sys.argv) > 1 else "."
    span, h = iso(o + "/iso.png")
    plan(o + "/plan.png")
    print("route %.1f tiles; px span %d; picture %d lines" % (route_len(), span, h))
    for i, (x, y, z, name) in PLACED.items():
        print("%s clock at wx %.1f, wy %.1f, head about z %g" % (name, x, y, z))
