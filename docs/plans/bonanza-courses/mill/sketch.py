#!/usr/bin/env python3
"""COURSE 4, WINDMILL LANE (MILL), attempt 1: the PAPER sketch (wave 11's
pipeline, the pen-in step; ../MILL.md is the design sheet).  Host-only;
nothing in `make` runs it and it ships nothing.  DOWNHILL DECISION's sketch
(../down/sketch.py) adapted: the cells are the ENGINE's cells (no offset),
every open edge of a section is guarded unless the design says it is open
(`fence`), and the bumper box is the prototype's (apps/bonanza/courses/mill.bbc)
moved up 12 units.

    python3 sketch.py [outdir]               plan.png and iso.png
    python3 sketch.py --bbc OUT [--force]     the engine course (the rubber route's ways, and the glass
                                              route's as `branch GLASS` ways: the tool's alone)
    python3 sketch.py --bbc OUT --glass ...   the same with the GLASS route's ways (timing only)
"""
import os
import sys
from PIL import Image, ImageDraw

CELLS = {}           # (wx, wy) -> (corner heights nw, ne, se, sw)
SECTION = {}
WALLS = {}           # (wx, wy) -> z: a solid block (a house, a tube's body, the bumper box's walls)
BOUNCE = set()       # wall cells whose surface is `bounce` (the bumper rails)
NOGUARD = set()      # void cells `fence` must leave open (an archway's legs go there)
FENCED = []          # the sections `fence` guards
ROOMS_TXT = []
MARKS = []           # (wx, wy, kind, text): props the sketch does not model, drawn as markers


def floor(sec, x0, y0, x1, y1, z):
    ROOMS_TXT.append("floor rect %3d %3d %3d %3d  flat %g   # %s" % (x0, y0, x1, y1, z, sec))
    for x in range(x0, x1):
        for y in range(y0, y1):
            CELLS[(x, y)] = (z, z, z, z)
            SECTION[(x, y)] = sec


def ramp(sec, axis, x0, y0, x1, y1, z0, z1):
    """z0 at the low-coordinate edge of `axis`, z1 at the high one"""
    p0, p1 = (x0, x1) if axis == "x" else (y0, y1)
    ROOMS_TXT.append("floor rect %3d %3d %3d %3d  ramp %s %d %d %g %g   # %s"
                     % (x0, y0, x1, y1, axis, p0, p1, z0, z1, sec))
    n = (x1 - x0) if axis == "x" else (y1 - y0)
    for x in range(x0, x1):
        for y in range(y0, y1):
            i = (x - x0) if axis == "x" else (y - y0)
            a, b = z0 + (z1 - z0) * i / n, z0 + (z1 - z0) * (i + 1) / n
            CELLS[(x, y)] = (a, b, b, a) if axis == "x" else (a, a, b, b)
            SECTION[(x, y)] = sec


def wall(x0, y0, x1, y1, z, bounce=False):
    ROOMS_TXT.append("wall  rect %3d %3d %3d %3d  flat %g" % (x0, y0, x1, y1, z))
    if bounce:
        ROOMS_TXT.append("surface bounce rect %d %d %d %d" % (x0, y0, x1, y1))
    for x in range(x0, x1):
        for y in range(y0, y1):
            WALLS[(x, y)] = z
            if bounce:
                BOUNCE.add((x, y))


def mark(x, y, kind, text=""):
    MARKS.append((x, y, kind, text))


# =============================================================================
# WINDMILL LANE, attempt 1 (the owner's brief, 2026-11-21): a windmill MINIGOLF course, windmills and tubes,
# about 60 s, DENSE screens.  Rubber from the start.  The prototype's bumper box and tube kept; a FORK into two
# tubes - an open one to the easier RUBBER way (a turntable and a second windmill), and one behind an ARCHWAY
# over a GLASS pad to the riskier GLASS way (a respawning JUMP pickup and a jump it must make, or break); both
# rejoin before the finish, a cup in a sandpit.
# =============================================================================
# 1. THE TEE AND THE FIRST WINDMILL (the prototype's, its left windmill gone) ---------------------------------
floor("A", 7, 9, 13, 14, 28)                     # the TEE: 6 x 5, guarded, the start 3 tiles from the door (its
                                                 #   east column under B: a guard there, between two heights, shaded the door)
NOGUARD.update({(13, y) for y in range(9, 14)})  #   its east edge OPEN to a 1-tile slot before the ramp: a block rail
                                                 #   there (a guard may not touch a ramp) shaded the door too
wall(8, 5, 12, 9, 34)                            # the windmill's HOUSE, 6 units over the tee
floor("B", 12, 5, 16, 9, 32)                     # B, east of the house, where its tube comes out
ramp("R", "y", 14, 9, 16, 17, 32, 20)            # B's descent along +y into the bumper box
NOGUARD.update({(x, y) for x in (13, 16) for y in range(9, 17)})   # its sides open, as the prototype's (the
                                                 #   block rails a ramp needs took the course past 1,024 blocks)
# 2. THE BUMPER BOX (the prototype's green, the owner's KEEP: its entrance and spacing), up 12 units ----------
floor("G", 12, 17, 18, 22, 20)
wall(12, 16, 14, 17, 22, True)                   # its back wall either side of the ramp's mouth
wall(16, 16, 18, 17, 22, True)
wall(11, 17, 12, 22, 21, True)                   # its bumper RAILS (the `bounce` surface)
wall(18, 17, 19, 22, 21, True)
wall(12, 22, 19, 23, 21, True)
wall(19, 20, 20, 21, 21)                         # the DROP tube's last wall (its mouth on the +x face)
for bx, by in ((14, 19), (16, 18), (16, 20)):
    mark(bx + 0.5, by + 0.5, "bumper", "")
# 3. THE BUNKER and the walk to the fork -------------------------------------------------------------------
floor("F", 20, 15, 26, 22, 14)                 # F: the drop's 3 units onto plain fairway (a SAND bunker
BUNKER = os.environ.get("MILL_BUNKER", "0") == "1"   #   there took the course past 1,024 blocks: MILL_BUNKER=1)
# the SEE-SAW (SPEC.md 130.42), the owner's pick (2026-11-21): a minigolf TEETER from F toward the plaza, 2 x 2,
# tilting along y about its middle edge, pivot 14.5: at rest its near end is F's height (14) and its far end a unit
# up; the ball rolls up it, past the pivot its weight tips it (rubber: 0.29 s, the ball carried) and it rolls off
# the far end, now F's height, onto a landing 2 units over the plaza (whole units: half ones cost blocks).  Railed:
# block rails west, the east open (below).  (4 long changed the picture over 10 lanes, over the 6 a plate may have: SPEC.md 130.42.5)
SEESAW = (22, 22, 24, 24, 14.5)
ROOMS_TXT.append("@seesaw")                      # (the plate lays its own cells: the statement is in EXTRA)
for _x in range(22, 24):
    for _y in range(22, 24):
        _a, _b = 14 + 0.5 * (_y - 22), 14 + 0.5 * (_y - 21)
        CELLS[(_x, _y)] = (_a, _a, _b, _b)
        SECTION[(_x, _y)] = "W"
floor("F", 22, 24, 24, 26, 14)                   #   its LANDING, 2 x 2, then a 2-unit step down to the plaza
# (its WEST side BLOCK rails, which `blockrails` lays beside a slope - open, a ball drifting off the plate fell to a
# respawn at the start, as the autopilot did; its EAST side open: a block rail there, in FRONT, hid the ball on the
# plate for 1.4 s.  A flag on F before it, and the way along its west half)
NOGUARD.update({(24, 22), (24, 23), (24, 24)})
floor("P", 16, 26, 29, 30, 12)                   # the FORK PLAZA, 13 x 4
# 4a. THE RUBBER WAY: an open tube, a TURNTABLE, the second WINDMILL ----------------------------------------
floor("P", 26, 30, 27, 31, 12)                   #   the open tube's mouth (a drain) off the plaza's front
wall(26, 31, 27, 33, 13); wall(27, 32, 33, 33, 13)   # its body, a pipe a unit up (it hides half the mouth:
                                                 #   half a unit cost blocks): +y, +x along wy 32, +y out
NOGUARD.add((27, 30))                            #   (nor a rail beside the mouth)
floor("S", 31, 33, 34, 37, 11)                   #   S: where it comes out, 3 wide (flag 0 on its line)
floor("T", 31, 37, 34, 40, 11)                   #   the TURNTABLE, 3 x 3 (SPEC.md 130.43)
mark(32.5, 38.5, "turn", "turntable")
NOGUARD.update({(x, y) for x in (30, 34) for y in range(37, 40)})   # (no rails beside it: the tool's 4 records a block)
# U's east edge open by the table (a rail there laid a fifth occluder record in a block by the table's front
# corner); U is 5 deep and its door one row up, so its south rail is two rows in front of the door's 3 x 3
# (a rail one row in front laid records over it: the doorway "in the shade")
NOGUARD.update({(34, 40), (34, 41)})
floor("U", 30, 40, 34, 45, 11)                   #   U: the second windmill's apron, its door on the house's +x face
wall(26, 40, 30, 45, 17)                         #   the second HOUSE (6 units)
floor("J", 26, 45, 30, 47, 10)                   #   the house's front step, where its tube comes out (+y)
# 4b. THE GLASS WAY: behind an ARCHWAY over a glass pad, a tube up to a ledge, the jump ---------------------
floor("P", 21, 30, 22, 31, 12)                   #   the ARCH's cell (the glass pad under it)
floor("Q", 21, 31, 22, 32, 12)                   #   the glass tube's mouth, only reached under the arch
NOGUARD.update({(20, 30), (22, 30), (22, 31)})   #   (the arch's legs stand there; no rail beside the mouth: it hid the pad)
wall(19, 31, 21, 32, 15); wall(19, 32, 20, 34, 15)   #   its body, -x then +y (a +y body in front of the arch hid
                                                 #   its pad: SPEC.md 130.39.1 A10), a pipe a unit over H
floor("H", 18, 34, 25, 39, 14)                   #   H: the LEDGE, 2 units over the plaza; the jump pickup on it
floor("L", 16, 30, 18, 36, 12)                   #   the BACK DOOR: H's west edge drops 2 units onto a lane
                                                 #   back to the plaza - glass may step down it, nothing climbs it
PIT = os.environ.get("MILL_PIT", "0") == "1"     # OFF: the pit put 5 occluder records in a block (over 4)
if PIT:
    floor("K", 18, 39, 25, 41, 9)                #   the PIT under the gap, 5 units down: glass breaks there
NOGUARD.update((x, y) for x in range(18, 25) for y in range(39, 41))   # the GAP: open, no rails
floor("V", 18, 41, 25, 43, 14)                   #   V: the far side, past a 2-tile gap
floor("V", 21, 43, 23, 45, 14)                   #   the neck: two RUBBER pads end the glass stretch
ramp("V", "y", 21, 45, 23, 47, 14, 10)           #   and a ramp down to the rejoin, its sides open (a block
NOGUARD.update({(x, y) for x in (20, 23) for y in range(44, 47)})   #   rail beside it hid a pad)
# 5. THE REJOIN and the FINISH: a cup in a sandpit ---------------------------------------------------------
floor("J", 19, 47, 32, 50, 10)                   # J: the rejoin green
floor("J", 23, 50, 26, 51, 10)                   #   the walk in
floor("Z", 22, 51, 27, 56, 10)                   # the FINISH green: SAND round the cup
FINRAILS = os.environ.get("MILL_FINRAILS", "0") == "1"   # its back BUMPER rails (magenta bounce walls) took the
if FINRAILS:                                     #   course past 1,024 blocks with the see-saw: guard rails instead
    wall(21, 50, 22, 56, 11, True); wall(22, 50, 23, 51, 11, True); wall(26, 50, 27, 51, 11, True)
CUP = (24, 53)
FENCED = "ABRFPSTUJQHLVZW"                        # every section's open edges guarded but the pit's

START = (9.5, 12.5)
FLAGS = [(21.5, 20.5, "flag 0", "rubber"), (32.5, 35.5, "flag 1", "rubber"), (19.5, 35.5, "flag 2", "glass")]
# (no FORK clock: in the see-saw's window its two numerals, the plate's 4 lanes and the event lane passed the
# 6 pose changes a window may land on one step, SPEC.md 130.19.10)
CLOCKS = [(7, 13, 28, "start", "on"), (34, 36, 6, "turntable", "out"),
          (22, 55, 10, "finish", "on")]
ROUTE = [(9.5, 12.5), (9.5, 9.5), (9.5, 6.5), (12.5, 6.5), (14.5, 7.5), (14.5, 13), (14.5, 18), (17.5, 20.5),
         (20.5, 20.5), (21.5, 20.5), (22.5, 21.5), (22.5, 23), (22.5, 25.5), (23, 26.5), (24.5, 27.5), (26.5, 29.5), (26.5, 30.5), (26.5, 32.5), (32.5, 32.5),
         (32.5, 33.5), (32.5, 35.5), (32.5, 38.5), (32.5, 40.5), (31.5, 41.5), (30.5, 41.5), (27.5, 41.5),
         (27.5, 45.5), (27.5, 47.5), (25.5, 49), (24.5, 50.5), (24.5, 53.5)]
ROUTE2 = [(24.5, 27.5), (21.5, 28.5), (21.5, 30.5), (21.5, 31.5), (19.5, 31.5), (19.5, 34.5), (19.5, 35.5),
          (19.5, 36.5), (19.5, 38.5), (19.5, 41.5), (21.5, 42.5), (21.5, 43.5), (21.5, 46), (22.5, 48),
          (24.5, 50.5), (24.5, 53.5)]
JUMP = (19, 36)
GAP = {(x, y) for x in range(18, 25) for y in range(39, 41)}      # (no way over the gap)
LABELS = [(9, 12.5, "TEE"), (9, 7, "WINDMILL 1"), (13, 6, "B"), (14.5, 12, "ramp"), (14.5, 19, "BUMPER BOX"),
          (18.5, 21, "drop"), (21, 19, "F"), (22, 25, "landing"), (21, 27, "FORK plaza"), (21, 30, "arch+glass pad"),
          (26, 30.5, "open tube"), (32, 34, "S"), (33, 38, "TURNTABLE"), (31, 41, "U"), (27, 41, "WINDMILL 2"),
          (16, 33, "back door"), (20, 36.5, "jump pickup"), (22, 39.5, "GAP (2 tiles)"), (23, 22.5, "SEE-SAW"), (22, 42.5, "rubber pads"),
          (20, 48, "REJOIN"), (23, 54, "CUP in the sandpit")]

EXTRA = [
    "# the first windmill (the prototype's right one): a KEEP tube through its house, entered -y from the tee",
    "tube keep   9 9  12 6  via 9 6",
    "prop windmill 9 9  seed 16",
    "# the bumper box (the prototype's): three posts, the DROP tube out of its east rail onto the bunker",
    "prop bumper 14 19", "prop bumper 16 18", "prop bumper 16 20",
    "tube drop  17 20  20 20  out +x  height 3",
] + (["surface sand rect 20 18 23 22               # the bunker the drop lands in (G16: it kills the bounce)"]
       if BUNKER else []) + [
    "# the SEE-SAW: F's teeter down to the plaza (SPEC.md 130.42), resting with its near (minus) end down",
    "seesaw %d %d %d %d along y pivot %g" % SEESAW,
    "# the FORK: the open tube (the rubber way) and the ARCHWAY over a glass pad (SPEC.md 130.39) before the",
    "# glass way's tube",
    "tube keep  26 30  32 33  via 26 32  via 32 32",
    "archway tile 21 30 along y",
    "pad glass 21 30",
    "tube keep  21 31  19 34  via 19 31",
    "# the rubber way's TURNTABLE (SPEC.md 130.43): the middle column open on every other quarter turn",
    "prop turntable 31 37 size 3 fill ooo/.o./.o. seed 228",
    "# the second windmill: entered -x off U, out of its house's +y face onto the rejoin",
    "tube keep  30 41  27 45  via 27 41",
    "prop windmill 30 41",
    "# the glass way: a respawning JUMP (SPEC.md 130.25.9, 130.55) on the ledge, the rubber pads past the gap",
    "prop jump %d %d for 10 respawn" % JUMP,
    "pad rubber 21 43", "pad rubber 22 43",
    "# the finish: the CUP in a sandpit (SPEC.md 130.14.4.3; MOON's ring)",
    "surface sand rect 22 51 27 56",
    "surface normal tile %d %d" % CUP,
    "cup %d %d" % CUP,
]

# --- drawing ----------------------------------------------------------------
SECCOL = {"A": (120, 210, 120), "B": (140, 200, 120), "R": (170, 210, 130), "G": (90, 200, 110),
          "F": (110, 190, 110), "W": (230, 230, 120), "P": (130, 220, 150), "S": (150, 210, 200), "T": (200, 230, 250),
          "U": (150, 210, 200), "Q": (200, 240, 250), "H": (170, 230, 240), "L": (150, 190, 170),
          "K": (90, 90, 110), "V": (170, 230, 240), "J": (110, 210, 130), "Z": (230, 210, 140)}
SAND = ({(x, y) for x in range(20, 23) for y in range(18, 22) if BUNKER} |
        {(x, y) for x in range(22, 27) for y in range(51, 56)}) - {CUP}
MC = {"bumper": (255, 60, 200), "turn": (0, 255, 255), "glass": (120, 240, 255), "rubber": (255, 80, 200),
      "jump": (255, 255, 0), "arch": (255, 220, 0), "cup": (0, 0, 0)}


def guards():
    """`fence`: every void neighbour of a fenced section's cell is a guard rail tile, but the NOGUARD ones,
    the clocks' and the pit's own"""
    out = set()
    clocks = {(x, y) for x, y, _z, _n, _k in CLOCKS}
    for (x, y), sec in SECTION.items():
        if sec not in FENCED:
            continue
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + a, y + b)
            if n not in CELLS and n not in WALLS and n not in NOGUARD and n not in clocks:
                out.add(n)
    return out


def blockrails():
    """the guard cells beside a RAMP (a guard stands only on a whole flat floor's edge, SPEC.md 130.35.1): a
    BLOCK rail there instead, 2 units over the highest corner it guards -> {(wx, wy): z}"""
    out = {}
    for g in guards():
        nb = [CELLS[(g[0] + a, g[1] + b)] for a in (-1, 0, 1) for b in (-1, 0, 1) if (g[0] + a, g[1] + b) in CELLS]
        lone = any((g[0] + a, g[1] + b) in CELLS and (g[0] + a, g[1]) not in CELLS and (g[0], g[1] + b) not in CELLS
                   for a in (-1, 1) for b in (-1, 1))     # a floor at a corner no rail passes through
        if lone or any(len(set(c)) > 1 for c in nb):
            out[g] = round((max(max(c) for c in nb) + 2) * 2) / 2
    return out


def zat(wx, wy):
    c = CELLS.get((int(wx), int(wy)))
    if not c:
        return WALLS.get((int(wx), int(wy)), 0)
    fx, fy = wx - int(wx), wy - int(wy)
    nw, ne, se, sw = c
    return nw * (1 - fx) * (1 - fy) + ne * fx * (1 - fy) + se * fx * fy + sw * (1 - fx) * fy


def pads():
    for line in EXTRA:
        w = line.split()
        if w and w[0] == "pad":
            yield w[1], int(w[2]), int(w[3])


def plan(out):
    S = 20
    xs = [k[0] for k in CELLS] + [k[0] for k in WALLS]
    ys = [k[1] for k in CELLS] + [k[1] for k in WALLS]
    W, H = (max(xs) + 3) * S, (max(ys) + 3) * S
    im = Image.new("RGB", (W, H), (20, 20, 30))
    d = ImageDraw.Draw(im)
    for (x, y), c in CELLS.items():
        base = SECCOL[SECTION[(x, y)]]
        if (x, y) in SAND:
            base = (230, 200, 120)
        k = 0.55 + 0.45 * (sum(c) / 4) / 34
        col = tuple(int(v * k) for v in base)
        d.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1], fill=col, outline=(60, 60, 70))
        if c[0] != c[2] or c[1] != c[3]:
            d.text((x * S + 6, y * S + 4), "v" if c[3] < c[0] else "^", fill=(0, 0, 0))
    for (x, y), z in WALLS.items():
        d.rectangle([x * S, y * S, x * S + S - 1, y * S + S - 1],
                    fill=(200, 60, 160) if (x, y) in BOUNCE else (110, 80, 70), outline=(60, 50, 50))
    for (x, y), z in blockrails().items():
        d.rectangle([x * S + 2, y * S + 2, x * S + S - 3, y * S + S - 3], fill=(170, 150, 40))
    for x, y in guards():
        d.rectangle([x * S + 6, y * S + 6, x * S + S - 7, y * S + S - 7], fill=(255, 220, 0))
    d.line([(x * S, y * S) for x, y in ROUTE], fill=(255, 60, 60), width=2)
    d.line([(x * S, y * S) for x, y in ROUTE2], fill=(120, 240, 255), width=2)
    for x, y, kind, t in MARKS:
        d.ellipse([x * S - 5, y * S - 5, x * S + 5, y * S + 5], fill=MC[kind])
    for mat, x, y in pads():
        d.ellipse([x * S + 3, y * S + 3, x * S + S - 4, y * S + S - 4], fill=MC[mat], outline=(0, 0, 0))
    d.rectangle([JUMP[0] * S + 6, JUMP[1] * S + 6, JUMP[0] * S + 14, JUMP[1] * S + 14], fill=MC["jump"])
    d.line([(20 * S, 30 * S + 3), (23 * S, 30 * S + 3)], fill=MC["arch"], width=4)
    d.ellipse([CUP[0] * S + 5, CUP[1] * S + 5, CUP[0] * S + 15, CUP[1] * S + 15], fill=(0, 0, 0))
    for x, y, z, name, kind in CLOCKS:
        d.ellipse([x * S + 2, y * S + 2, x * S + S - 3, y * S + S - 3], outline=(0, 255, 255), width=2)
    for x, y, t, _b in FLAGS:
        d.polygon([(x * S, y * S - 9), (x * S + 11, y * S - 5), (x * S, y * S)], fill=(255, 80, 200))
    d.text((START[0] * S - 3, START[1] * S - 5), "S", fill=(255, 255, 255))
    for x, y, t in LABELS:
        d.text((x * S + 8, y * S - 14), t, fill=(255, 255, 255))
    d.text((6, H - 30), "plan: +wx right, +wy down; yellow = guard rails, magenta = bumper rails, brown = walls "
           "(houses, tube bodies); red = the rubber way, cyan = the glass way", fill=(220, 220, 220))
    d.text((6, H - 16), "cyan rings = clocks; pink = flags; discs = pads (pink rubber, cyan glass); yellow square = "
           "the jump; yellow bar = the archway", fill=(220, 220, 220))
    im.save(out)


def P(wx, wy, z):
    return 16 * (wx - wy), 8 * (wx + wy) - 8 * z


def iso(out):
    pts = [P(x + a, y + b, cz) for (x, y), c in CELLS.items() for a, b, cz in
           ((0, 0, c[0]), (1, 0, c[1]), (1, 1, c[2]), (0, 1, c[3]))]
    minx, maxx = int(min(p[0] for p in pts)) - 220, int(max(p[0] for p in pts)) + 220
    miny, maxy = int(min(p[1] for p in pts)) - 120, int(max(p[1] for p in pts)) + 160
    W, H = maxx - minx, maxy - miny
    im = Image.new("RGB", (W, H), (10, 10, 25))
    d = ImageDraw.Draw(im)

    def Q(wx, wy, z):
        x, y = P(wx, wy, z)
        return x - minx, y - miny
    ground = 9 - 3
    BR = blockrails()
    G = guards() - set(BR)
    items = [((x, y), c, None) for (x, y), c in CELLS.items()]
    items += [((x, y), (z, z, z, z), "rail") for (x, y), z in BR.items()]
    items += [((x, y), (z, z, z, z), "wall") for (x, y), z in WALLS.items()]
    items.sort(key=lambda it: (it[0][0] + it[0][1], it[0][0]))
    for (x, y), c, kind in items:
        nw, ne, se, sw = c
        top = [Q(x, y, nw), Q(x + 1, y, ne), Q(x + 1, y + 1, se), Q(x, y + 1, sw)]
        if kind == "wall":
            base = (210, 70, 170) if (x, y) in BOUNCE else (150, 110, 90)
        elif kind == "rail":
            base = (200, 180, 60)
        else:
            base = SECCOL[SECTION[(x, y)]]
            if (x, y) in SAND:
                base = (235, 205, 125)
        d.polygon([Q(x, y + 1, sw), Q(x + 1, y + 1, se), Q(x + 1, y + 1, ground), Q(x, y + 1, ground)],
                  fill=tuple(v // 2 for v in base))
        d.polygon([Q(x + 1, y, ne), Q(x + 1, y + 1, se), Q(x + 1, y + 1, ground), Q(x + 1, y, ground)],
                  fill=tuple(v * 2 // 3 for v in base))
        d.polygon(top, fill=base, outline=tuple(v * 3 // 4 for v in base))
        if (x, y) in SAND:
            for i in range(3):
                d.point(Q(x + 0.3 + 0.2 * i, y + 0.5, nw), fill=(120, 80, 40))
    # the guard rails: a thin rail on each guarded cell's edges with a floor
    for gx, gy in G:
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (gx + a, gy + b)
            if n in CELLS:
                if a:
                    ex = gx + (1 if a > 0 else 0)
                    seg = [(ex, gy), (ex, gy + 1)]
                else:
                    ey = gy + (1 if b > 0 else 0)
                    seg = [(gx, ey), (gx + 1, ey)]
                zz = max(CELLS[n]) + 1.5
                d.line([Q(*seg[0], zz), Q(*seg[1], zz)], fill=(255, 220, 0), width=2)
    for x, y, kind, t in MARKS:
        bx, by = Q(x, y, zat(x, y))
        if kind == "bumper":
            d.ellipse([bx - 6, by - 12, bx + 6, by], fill=MC[kind], outline=(255, 255, 255))
        elif kind == "turn":
            d.ellipse([bx - 40, by - 20, bx + 40, by + 20], outline=MC[kind], width=2)
            d.text((bx - 14, by - 4), "1/4", fill=MC[kind])
    for mat, x, y in pads():
        bx, by = Q(x + 0.5, y + 0.5, zat(x + 0.5, y + 0.5))
        d.ellipse([bx - 8, by - 4, bx + 8, by + 4], fill=MC[mat], outline=(0, 0, 0))
    bx, by = Q(JUMP[0] + 0.5, JUMP[1] + 0.5, 14)   # the jump pickup
    d.polygon([(bx, by - 18), (bx + 6, by - 8), (bx - 6, by - 8)], fill=MC["jump"])
    d.text((bx + 8, by - 22), "JUMP (respawns)", fill=MC["jump"])
    # the archway's lintel over the glass pad
    ax0, ay0 = Q(20, 31, 14); ax1, ay1 = Q(23, 31, 14)
    d.arc([ax0 - 2, ay0 - 26, ax1 + 2, ay1 + 18], 200, 340, fill=MC["arch"], width=4)
    d.text((ax1 + 4, ay1 - 30), "ARCHWAY", fill=MC["arch"])
    # the windmills' rotors on their doorways, the tubes' mouths
    for (wx, wy, face) in ((9.5, 9, "y"), (30, 41.5, "x")):
        cx, cy = Q(wx, wy, zat(wx, wy) + 3)
        for k in range(4):
            import math
            a = math.pi / 4 + k * math.pi / 2
            d.line([(cx, cy), (cx + 22 * math.cos(a), cy + 22 * math.sin(a))], fill=(255, 255, 255), width=3)
        d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 0, 0))
    for (wx, wy) in ((17.5, 20.5), (26.5, 30.5), (21.5, 31.5)):
        cx, cy = Q(wx, wy, zat(wx, wy))
        d.ellipse([cx - 7, cy - 4, cx + 7, cy + 4], fill=(0, 0, 0), outline=(255, 255, 255))
    cx, cy = Q(CUP[0] + 0.5, CUP[1] + 0.5, 10)
    d.ellipse([cx - 5, cy - 3, cx + 5, cy + 3], fill=(0, 0, 0))
    d.line([cx, cy, cx, cy - 24], fill=(255, 255, 255))
    d.polygon([(cx, cy - 24), (cx + 10, cy - 20), (cx, cy - 16)], fill=(255, 60, 60))
    # the two ways
    for route, col in ((ROUTE2, (120, 240, 255)), (ROUTE, (255, 60, 60))):
        rz, pts = 28, []
        for x, y in route:
            if (int(x), int(y)) in CELLS and (int(x), int(y)) not in GAP:
                rz = zat(x, y)
            elif (int(x), int(y)) in GAP:
                rz = 14 + 1.5
            pts.append(Q(x, y, rz + 1))
        d.line(pts, fill=col, width=2)
    heads = {}
    for x, y, z, name, kind in CLOCKS:
        cx, cy = Q(x + 0.5, y + 0.5, z + 2)
        heads[name] = P(x + 0.5, y + 0.5, z + 5)
        d.rectangle([cx - 2, cy - 24, cx + 2, cy], fill=(120, 100, 80))
        d.ellipse([cx - 9, cy - 40, cx + 9, cy - 22], fill=(0, 200, 220), outline=(255, 255, 255))
        d.text((cx + 12, cy - 38), name + " clock", fill=(0, 255, 255))
    for x, y, t, _b in FLAGS:
        bx, by = Q(x, y, zat(x, y))
        d.line([bx, by, bx, by - 20], fill=(255, 255, 255))
        d.polygon([(bx, by - 20), (bx + 10, by - 16), (bx, by - 12)], fill=(255, 80, 200))
        d.text((bx + 12, by - 22), "%s (%s)" % (t, _b), fill=(255, 120, 220))
    sx, sy = Q(*START, 28)
    d.ellipse([sx - 8, sy - 16, sx + 8, sy], fill=(255, 140, 0))
    for x, y, t in LABELS:
        lx, ly = Q(x, y, zat(x, y))
        d.text((lx + 12, ly - 6), t, fill=(255, 255, 255))
    # one CGA window (320 x 200) centred on the ball at each screen the design is drawn for
    for (x, y), name in (((9.5, 9.5), "the tee"), ((15, 19), "the bumper box"), ((23, 28), "the fork"),
                         ((32.5, 38.5), "the turntable"), ((21.5, 39), "the jump"), ((24.5, 52), "the finish")):
        cx, cy = Q(x, y, zat(x, y))
        d.rectangle([cx - 160, cy - 100, cx + 160, cy + 100], outline=(0, 255, 255))
        d.text((cx - 156, cy - 98), "CGA window: " + name, fill=(0, 200, 200))
    rx = [P(x, y, 0)[0] for x, y in ROUTE + ROUTE2]
    d.text((8, 8), "WINDMILL LANE attempt 1: route px span %d; course %d lines tall; red = the rubber way, cyan = "
           "the glass way; cyan boxes = one CGA window each" % (max(rx) - min(rx), H - 280), fill=(220, 220, 220))
    im.save(out)
    return heads


def route_len(r):
    return sum(((c - a) ** 2 + (e - b) ** 2) ** 0.5 for (a, b), (c, e) in zip(r, r[1:]))


HEAD_TXT = """
# Course 4 (MILL; docs/plans/bonanza-courses/MILL.md): WINDMILL LANE, a windmill MINIGOLF course - the
# prototype's first windmill and bumper box, a FORK into two tubes (an open one to the RUBBER way: a turntable
# and a second windmill; one behind an ARCHWAY over a glass pad to the GLASS way: a respawning jump and a gap
# it must make), a rejoin, and a CUP in a sandpit.  ATTEMPT 1, SHIPPED (2026-11-21; the prototype's features
# are TMIL's, the test copy): written by docs/plans/bonanza-courses/mill/sketch.py --bbc --force while the
# layout moves.
course MILL "Windmill Lane"
guide                     # a REAL course: held to the course guide's checkable rules
music windmill
width 128
origin 672                # 1,024 px: the reach runs from about px -620 (the finish) to +250 (over B)
ball rubber
uses rotor tube archway turntable pickups seesaw
target 60
"""


def bbc(out, glass=False):
    if os.path.exists(out) and "--force" not in sys.argv:
        sys.exit("sketch.py: %s exists; --force to re-emit it" % out)
    L = HEAD_TXT.strip("\n").split("\n") + [""]
    L.append("# rooms (the sketch's sections) and walls")
    L += [r for r in ROOMS_TXT if r != "@seesaw"]
    L.append("")
    L.append("# guard rails: every open edge but the design's (the jump's gap, the back door's step, the arch's legs)")
    br = blockrails()
    for x, y in sorted(guards()):
        if (x, y) in br:
            L.append("wall  tile %3d %3d  flat %g   # a block rail beside a ramp" % (x, y, br[(x, y)]))
        else:
            L.append("guard tile %3d %3d" % (x, y))
    L.append("")
    L += EXTRA
    L.append("")
    L.append("start %d %d" % (int(START[0]), int(START[1])))
    for x, y, t, ball in FLAGS:
        L.append("checkpoint %d %d ball %s   # %s" % (int(x), int(y), ball, t))
    L.append("")
    L.append("# clocks: on a corner of a floor off the way, or on a tile one out from it")
    for x, y, z, name, kind in CLOCKS:
        if kind == "out":
            L.append("floor tile %d %d  flat %g   # the %s clock's tile" % (x, y, z, name))
        L.append("clock %d %d   # %s" % (x, y, name))
    L.append("")
    L.append("# the autopilot's route: %s" % ("the GLASS way (a scratch variant, for its time)" if glass
                                              else "the RUBBER way"))
    route = ROUTE[:13] + ROUTE2 if glass else ROUTE
    for x, y in route:
        c = (int(x), int(y))
        if c in CELLS and c not in GAP and SECTION.get(c) != "W":
            L.append("way %d %d" % c)
    if not glass:
        # the GLASS way (ROUTE2) as a `branch` (SPEC.md 130.14.4.1), DOWN's shape: the tool's alone - no byte
        # of the part, nor its identity - so bbcourse's item 8 plans it and holds flag 2 (glass) to it; the
        # main route, rubber, touches only its own way's flags
        L.append("# the glass way: a branch from the plaza, rejoining at the finish (the tool's alone)")
        for x, y in ROUTE2:
            c = (int(x), int(y))
            if c in CELLS and c not in GAP and SECTION.get(c) != "W":
                L.append("way %d %d branch GLASS" % c)
    open(out, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--bbc"]:
        bbc(sys.argv[2], glass="--glass" in sys.argv)
        sys.exit(0)
    o = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    heads = iso(o + "/iso.png")
    plan(o + "/plan.png")
    print("rubber way %.1f tiles, glass way %.1f tiles (from the plaza)" % (route_len(ROUTE), route_len(ROUTE2)))
    names = list(heads)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (ax, ay), (bx, by) = heads[a], heads[b]
            print("clocks %-9s - %-9s  dx %4d  dy %4d%s" % (a, b, bx - ax, by - ay,
                  "   ONE WINDOW?" if abs(bx - ax) < 300 and abs(by - ay) < 185 else ""))
