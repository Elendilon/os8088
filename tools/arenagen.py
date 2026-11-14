#!/usr/bin/env python3
"""arenagen - WireArena's host-built tables (docs/plans/MULTIPLAYER-FPS-PLAN.md).

Writes one NASM include, deterministic byte for byte. Its constants are
always defined; each DATA block is assembled only where the includer asks for
it (docs/plans/WIREARENA-PARTS-PLAN.md: the primary and the renderer part
each take what they read):

  WA_TAB_SIN     wa_sin
  WA_TAB_ARENAS  every arena's tables and wa_arenas
  WA_TAB_PATHS   wa_pathtab and the patrols
  WA_TAB_POSE    wa_pose

The constants come first, under a guard of their own, so a second include
of the file adds only the data blocks the includer has asked for by then.

  wa_sin        257 words, a quarter wave of sin in Q14 (16384 = 1.0), sin(0..256);
                wa_sincos (apps/wirearena/wasin.inc) mirrors it to all 1024 angles
  wa_boxes      the arena's solid blocks, axis-aligned, in world units
  wa_room       the room's inner bounds
  wa_paths      each dummy's patrol: waypoints with the leg's heading and
                step count precomputed, so the guest needs no atan2
  wa_pose       the stick figure's keyframes, PRE-PROJECTED for 16 view
                facings: per frame, per facing, 11 joints of (lateral, height)
                as signed bytes in world units

World units are 1/64 m. Angles are 1024 to a turn, counter-clockwise from
+x, the map's y axis pointing "north". Heights are units above the floor
(docs/plans/WIREARENA-HEIGHTS-PLAN.md): a box is a 4-tuple, a 3 m solid
block, or a Box with a height and a kind (solid, a RAMP - kind FLIGHT, a
slope from the floor at its low face to its height at the face it rises
toward, HEIGHTS-PLAN 7.4.2 - or a lift),
and an arena part carries each box's height, kind and drawn faces after its
descriptor (WIREARENA-PARTS-PLAN 7.5, HEIGHTS-PLAN 7.2.1).

    python3 tools/arenagen.py build/watab.inc
    python3 tools/arenagen.py --arena N build/waaN.asm   (arena N as a part)
"""
import math
import re
import sys

UNIT = 64.0                     # world units a metre
NFACE = 16                      # view facings a pose is projected for
SPEED = 8                       # a dummy's run, units a 30 Hz tick (~4.8 m/s)

# --- the arena: a 32 m room with blocks in it (x0, y0, x1, y1), units ------
ROOM = (0, 0, 2048, 2048)
WALL_H = 192                    # today's walls and blocks: 3 m
STEPUP = 24                     # the most a step may rise and still walk
                                # (0.375 m, HEIGHTS-PLAN 3.1)
FRAD = 8                        # a dummy's feet: the square its floor is
                                # read under (wa_figtick; WA_FRAD)
SOLID, FLIGHT, LIFT = 0, 1, 2
FACES = "SENW"                  # face order, as everywhere: S E N W


class Box(tuple):
    """A box: the 4-tuple every geometry routine reads, plus its height
    (units above the floor; a lift's REST height), its kind, its colour (0 a
    boundary, 1 an item - wa_bcol), and for a flight the face it rises
    TOWARD and its tread count, for a lift its raised height."""
    def __new__(cls, x0, y0, x1, y1, h=WALL_H, kind=SOLID, col=1, toward=None,
                treads=0, top=None, name=""):
        b = tuple.__new__(cls, (x0, y0, x1, y1))
        b.h, b.kind, b.col, b.toward, b.treads = h, kind, col, toward, treads
        b.top, b.name = top, name
        return b


def bx(b):
    """Any box as a Box: a bare 4-tuple is a 3 m solid item."""
    return b if isinstance(b, Box) else Box(*b)


def jump_apex():
    """The jump's highest point, units: the game's own integration
    (wa_tick: jz += jv, jv -= GRAV, 8.8 a tick) off its own constants."""
    src = open(__file__.replace("tools/arenagen.py", "apps/wirearena/waconst.inc")
               if __file__.endswith("tools/arenagen.py") else
               "apps/wirearena/waconst.inc").read()
    v = int(re.search(r"WA_JUMPV\s+equ\s+(\d+)", src).group(1))
    g = int(re.search(r"WA_GRAV\s+equ\s+(\d+)", src).group(1))
    z = top = 0
    while v > 0 or z > 0:
        z += v
        v -= g
        top = max(top, z)
        if z <= 0:
            break
    return top >> 8
BOXES = [
    (448, 448, 576, 576),       # four pillars round the middle
    (1472, 448, 1600, 576),
    (448, 1472, 576, 1600),
    (1472, 1472, 1600, 1600),
    (896, 960, 1152, 1088),     # a long block across the centre
    (192, 960, 256, 1088),      # stubs off the west and east walls
    (1792, 960, 1856, 1088),
    (960, 192, 1088, 320),      # and off the south and north ones
    (960, 1728, 1088, 1856),
]
# The open arena: the same room, only the four pillars - the sparser level
# that asks how much of a frame the scene's own complexity costs.
OPEN_BOXES = BOXES[:4]
# x, y, angle. NOT (1024, 256), where Wave 0 started: that is inside the
# south stub, so every step collided and WASD looked dead. arenas() checks.
PLAYER_START = (1024, 480, 256)  # facing north, the patrols crossing ahead

# The HEIGHTS demo (docs/plans/WIREARENA-HEIGHTS-PLAN.md 4.1, revised for wave
# 3 in 7.4 from the owner's sketch): in the west an ANNEX, one plain block
# narrower than the room, with two straight hallways into it joined by a
# corridor along the room's west wall and, between the hallways, the back
# room - an alcove off that corridor - holding the jump platform; in the
# centre the platform with a RAMP up its south and north sides; in the east
# the tower with ONE lift, narrower than it, on its north side; two pillars
# in the open area. 13 boxes.
HB = 384                        # the annex and the pillars: 6 m, taller
                                # than any eye (HEIGHTS-PLAN 7.1)
HEIGHTS_BOXES = [
    Box(0, 0, 640, 384, HB, col=0, name="annex fill, south"),
    Box(0, 1664, 640, 2048, HB, col=0, name="annex fill, north"),
    Box(576, 576, 640, 1472, HB, col=0, name="annex front"),
    Box(128, 576, 576, 832, HB, col=0, name="annex block, south"),
    Box(128, 1216, 576, 1472, HB, col=0, name="annex block, north"),
    Box(384, 960, 576, 1088, 48, name="jump platform"),
    Box(1088, 896, 1408, 1152, 80, name="platform"),
    Box(1184, 704, 1312, 896, 80, FLIGHT, toward="N", treads=4,
        name="south ramp"),
    Box(1184, 1152, 1312, 1344, 80, FLIGHT, toward="S", treads=4,
        name="north ramp"),
    Box(1856, 896, 2048, 1152, 160, name="tower"),
    Box(1920, 1152, 2048, 1280, 16, LIFT, top=160, name="lift"),
    Box(1472, 384, 1600, 512, HB, name="pillar"),
    Box(1472, 1536, 1600, 1664, HB, name="pillar"),
]
NOPATROL = set()
# Arena 2's own patrols (HEIGHTS-PLAN 7.4.5), carried in its part: one up
# the south ramp, across the platform and down the north one; one through
# the annex's hallways and corridor; one round the tower. Checked for every
# rise a walker meets (patrol_checks)
HEIGHTS_PATHS = [
    [(1248, 600), (1248, 1450), (1700, 1450), (1700, 600)],
    [(800, 480), (64, 480), (64, 1568), (800, 1568)],
    [(1000, 300), (1750, 300), (1750, 1750), (1000, 1750)],
]


def arenas():
    return [("a0", "Arena", BOXES, PLAYER_START),
            ("a1", "Open", OPEN_BOXES, PLAYER_START),
            ("a2", "Heights", HEIGHTS_BOXES, PLAYER_START)]


# an arena's own patrols, carried in its part (the rest walk PATHS, which the
# primary carries): every arena's are WA_NFIG loops
ARENA_PATHS = {"a2": HEIGHTS_PATHS}


def height_at(b, x, y, r):
    """Box b's height under the square (x +- r, y +- r), which overlaps it -
    for a RAMP (a FLIGHT) the height at the square's highest point on it,
    the slope linear from 0 at its low face to b.h at the face it rises
    TOWARD: the game's wa_hat, exactly (integer, rounded down)"""
    b = bx(b)
    if b.kind != FLIGHT:
        return b.h
    x0, y0, x1, y1 = b
    if b.toward == "N":
        num, ln = min(y + r, y1) - y0, y1 - y0
    elif b.toward == "S":
        num, ln = y1 - max(y - r, y0), y1 - y0
    elif b.toward == "E":
        num, ln = min(x + r, x1) - x0, x1 - x0
    else:
        num, ln = x1 - max(x - r, x0), x1 - x0
    return int(b.h * num) // ln


def floor_at(x, y, boxes, r):
    """The floor under the square (x +- r, y +- r): the tallest height of
    any box it overlaps, or 0 (wa_floor)"""
    f = 0
    for b in boxes:
        if b[0] - r < x < b[2] + r and b[1] - r < y < b[3] + r:
            f = max(f, height_at(b, x, y, r))
    return f


def room_h(boxes):
    return WALL_H


def hmax(boxes):
    """The arena's tallest height, the room's and the lifts' raised included:
    a face at it, seen from below it, shuts its columns (HEIGHTS-PLAN 1.2)"""
    return max([room_h(boxes)] + [max(b.h, b.top or 0) for b in map(bx, boxes)])

# --- the potentially-visible sets (docs/plans/WIREARENA-HEIGHTS-PLAN.md 9.8) --
# Per cell of a square grid over the room, the boxes that can draw anything
# from SOMEWHERE in the cell: the renderer's walk (wa_order) skips the rest
# before their cone test, transforms or setup. Only TALL boxes occlude - a box
# at the arena's tallest, which every eye the game allows is below
# (pvs_eyemax), so occlusion is a question in 2D: a box is visible from a
# point when some ray from it reaches the box before any tall box in front of
# it. A box draws only in columns whose centre ray meets it, and a column a
# nearer tall face covers is shut, so a box no ray reaches draws nothing.
# Conservative against the renderer's own rounding: each box's angular
# interval widened, each occluder's narrowed, by PVS_EPS radians (a column's
# projection truncates to under 1/16 of a column: 0.0025 rad at 90 degrees and
# 40 columns, the widest) plus PVS_EPSD / distance (a camera-space coordinate
# truncates by under a unit in x and in z, under 2 / z rad on the screen; and
# a point tested is within 2 units of any on its outline). From a cell, the
# points tested are its outline and any tall box's outline (a unit out)
# inside it at PVS_STEP units, and a PVS_GRIDP grid inside: a ray from an
# inner point reaches the box from where, run backwards, it leaves the cell
# or meets an occluder's face, as well.
PVS_EPS = 0.003
PVS_EPSD = 5.0
PVS_STEP = 4
PVS_GRIDP = 16
PVS_MIN = 0.10                  # an arena carries one when it culls at
                                # least this share of its box-cells
PVS_SHIFT = 7                   # the grid: 128 units (2 m) a cell


def pvs_eyemax(boxes):
    """The highest eye the game allows: the highest floor anything stands
    on (a low box's top, a lift raised), the eye above it, and a jump"""
    top = hmax(boxes)
    floor = max([0] + [max(b.h, b.top or 0) for b in boxes if b.h < top
                       or b.kind == LIFT])
    src = open(__file__.replace("tools/arenagen.py", "apps/wirearena/waconst.inc")
               if __file__.endswith("tools/arenagen.py") else
               "apps/wirearena/waconst.inc").read()
    eye = int(re.search(r"WA_EYE\s+equ\s+(\d+)", src).group(1))
    return floor + eye + jump_apex()


def pvs_interval(p, r, ref):
    """Box r's angular interval seen from p, relative to the direction ref,
    and its distance - None when p is in it"""
    a, b, c, d = r
    px, py = p
    if a <= px <= c and b <= py <= d:
        return None
    cd = math.atan2((b + d) / 2 - py, (a + c) / 2 - px)
    ts = [(math.atan2(y - py, x - px) - cd + math.pi) % (2 * math.pi) - math.pi
          for (x, y) in ((a, b), (c, b), (c, d), (a, d))]
    s = (cd - ref + math.pi) % (2 * math.pi) - math.pi
    return (min(ts) + s, max(ts) + s,
            math.hypot(max(a - px, 0, px - c), max(b - py, 0, py - d)))


def pvs_front(p, o, b):
    """Box o can stand in front of box b on a ray from p: p is on o's side
    of every axis line that separates them (on b's side of any, b is met
    first on any ray meeting both)"""
    px, py = p
    if b[2] <= o[0] and not px > o[0]:
        return False
    if o[2] <= b[0] and not px < o[2]:
        return False
    if b[3] <= o[1] and not py > o[1]:
        return False
    if o[3] <= b[1] and not py < o[3]:
        return False
    return True


def pvs_seen(p, boxes, tall, have):
    """-> the boxes (bits) not in have that p sees some part of"""
    got = 0
    for i, B in enumerate(boxes):
        if have >> i & 1:
            continue
        ref = math.atan2((B[1] + B[3]) / 2 - p[1], (B[0] + B[2]) / 2 - p[0])
        bi = pvs_interval(p, B, ref)
        if bi is None:
            got |= 1 << i
            continue
        e = PVS_EPS + PVS_EPSD / max(bi[2], 1.0)
        lo, hi = bi[0] - e, bi[1] + e
        cov = []
        for j in tall:
            if j != i and pvs_front(p, boxes[j], B):
                oi = pvs_interval(p, boxes[j], ref)
                if oi is None:
                    continue            # (never: no point is in a tall box)
                f = PVS_EPS + PVS_EPSD / max(oi[2], 1.0)
                a, b = oi[0] + f, oi[1] - f
                for k in (-2 * math.pi, 0, 2 * math.pi):
                    if a < b and a + k < hi and b + k > lo:
                        cov.append((a + k, b + k))
        at = lo
        for a, b in sorted(cov):
            if a > at:
                break
            at = max(at, b)
        if at < hi:
            got |= 1 << i
    return got


_PVS = {}


def pvs_masks(tag, boxes):
    """-> the grid's masks, [ix][iy] (bit i: box i may draw from the cell),
    or None when the arena takes none (made once a run: tools/wamodel.py
    walks with them too)"""
    if tag not in _PVS:
        _PVS[tag] = pvs_build(tag, boxes)
    return _PVS[tag]


def pvs_build(tag, boxes):
    boxes = [bx(b) for b in boxes]
    top = hmax(boxes)
    if pvs_eyemax(boxes) >= top:
        return None                     # (an eye over the tallest: no occluder)
    tall = [i for i, b in enumerate(boxes) if b.h >= top]
    occ = [boxes[i] for i in tall]
    g = 1 << PVS_SHIFT
    if (ROOM[2] - ROOM[0]) % g or (ROOM[3] - ROOM[1]) % g or ROOM[0] or ROOM[1]:
        raise SystemExit("arenagen: the PVS grid wants the room at 0, 0 in "
                         "whole cells")
    full = (1 << len(boxes)) - 1
    out, cut = [], 0
    for x0 in range(ROOM[0], ROOM[2], g):
        col = []
        for y0 in range(ROOM[1], ROOM[3], g):
            vis = 0
            for p in pvs_points(x0, y0, x0 + g, y0 + g, occ):
                if vis == full:
                    break
                vis |= pvs_seen(p, boxes, tall, vis)
            col.append(vis)
            cut += bin(full & ~vis).count("1")
        out.append(col)
    share = cut / float(len(boxes) * len(out) * len(out[0]))
    sys.stderr.write("arenagen: arena %s: the PVS culls %.1f%% of box-cells%s\n"
                     % (tag, 100 * share, "" if share >= PVS_MIN else
                        " - under %d%%, none carried" % (100 * PVS_MIN)))
    return out if share >= PVS_MIN else None


def pvs_points(x0, y0, x1, y1, occ):
    """The points a cell's visibility is tested from, sorted (pvs_build's
    comment): its outline and the occluders' inside it every PVS_STEP, and
    a PVS_GRIDP grid - none inside an occluder (no one stands in a wall)"""
    pts = set()

    def edge(ax, ay, bx_, by):
        k = max(1, -(-max(abs(bx_ - ax), abs(by - ay)) // PVS_STEP))
        for t in range(k + 1):
            pts.add((ax + (bx_ - ax) * t / k, ay + (by - ay) * t / k))
    for (a, b, c, d) in [(x0, y0, x1, y1)] + [(a - 1, b - 1, c + 1, d + 1)
                                              for (a, b, c, d) in occ]:
        a, b, c, d = max(a, x0), max(b, y0), min(c, x1), min(d, y1)
        if a <= c and b <= d:
            edge(a, b, c, b), edge(c, b, c, d), edge(c, d, a, d), edge(a, d, a, b)
    for gx in range(x0, x1 + 1, PVS_GRIDP):
        for gy in range(y0, y1 + 1, PVS_GRIDP):
            pts.add((gx, gy))
    return [p for p in sorted(pts)
            if not any(a <= p[0] <= c and b <= p[1] <= d for (a, b, c, d) in occ)]


# --- pickups (docs/plans/WIREARENA-WEAPONS-PLAN.md 2.4) ----------------------
# kind: the renderer's shape and colour (wa_pkdraw's table) and the game's
# effect (wa_pktake's); a weapon's kind is its weapon number less one
PK_SHOTGUN, PK_CHAINGUN, PK_GRENADE, PK_ROCKET, PK_RAIL = 0, 1, 2, 3, 4
PK_HEALTH, PK_SHIELD = 5, 6
PK_HALF = (24, 28, 20, 32, 40, 16, 12)  # half its width (wa_pkshape's)
PK_PVSR = 16                    # the square its PVS bit is for: at least
                                # every half width but the lines' - a line
                                # is drawn only where its middle's column is
                                # open, so its middle is what must be seen
WA_MPK = 8                      # the most an arena carries: a bit each
# Arena 2's (the owner's placement, 2026-11-13): the health pack in the back
# tunnel (the corridor along the west wall, behind the annex, opposite the
# back room's mouth); the shield pack on the jump platform in the back room;
# on the ramp platform a WEAPON SPAWN - the shotgun, the chaingun or the
# grenade launcher, picked at random each time it spawns - and on the
# tower's top (the platform the lift goes up to) the rocket launcher or the
# railgun (the owner, 2026-11-14). A kind, or a tuple of kinds to pick from
HEIGHTS_PICKUPS = [
    (PK_HEALTH, 64, 1024),
    (PK_SHIELD, 480, 1024),
    ((PK_SHOTGUN, PK_CHAINGUN, PK_GRENADE), 1248, 1024),
    ((PK_ROCKET, PK_RAIL), 1952, 1024),
]
ARENA_PICKUPS = {"a2": HEIGHTS_PICKUPS}


def pickups(tag, boxes):
    """An arena's pickups: [(kind, x, y, z, choices)], z the floor under it,
    choices a bit a kind it may spawn as (0: always kind). Refused in a tall
    box, outside the room, past WA_MPK, or choosing among anything but
    weapons"""
    boxes = [bx(b) for b in boxes]
    out = []
    for k, x, y in ARENA_PICKUPS.get(tag, []):
        if not (ROOM[0] < x < ROOM[2] and ROOM[1] < y < ROOM[3]) or \
                any(b[0] < x < b[2] and b[1] < y < b[3] and b.h >= hmax(boxes)
                    for b in boxes):
            raise SystemExit("arenagen: arena %s: a pickup at (%d, %d) is in a "
                             "wall" % (tag, x, y))
        ks = k if isinstance(k, tuple) else (k,)
        if len(ks) > 1 and max(ks) >= PK_HEALTH:
            raise SystemExit("arenagen: arena %s: a spawn at (%d, %d) picks "
                             "among more than weapons" % (tag, x, y))
        out.append((ks[0], x, y, floor_at(x, y, boxes, 0),
                    sum(1 << c for c in ks) if len(ks) > 1 else 0))
    if len(out) > WA_MPK:
        raise SystemExit("arenagen: arena %s has %d pickups - at most %d"
                         % (tag, len(out), WA_MPK))
    return out


def pvs_pickups(tag, boxes, pks):
    """-> per cell [ix][iy] a byte, bit i: pickup i may be seen from the cell
    (the boxes' test: pvs_seen, over the tall boxes, at each pickup's
    PK_PVSR square) - or None, when the arena carries no PVS"""
    boxes = [bx(b) for b in boxes]
    if not pks or pvs_masks(tag, boxes) is None:
        return None
    top = hmax(boxes)
    tall = [i for i, b in enumerate(boxes) if b.h >= top]
    occ = [boxes[i] for i in tall]
    nb = len(boxes)
    targets = boxes + [Box(x - PK_PVSR, y - PK_PVSR, x + PK_PVSR, y + PK_PVSR)
                       for (_, x, y, _, _) in pks]
    have0 = (1 << nb) - 1
    full = (1 << len(pks)) - 1
    g = 1 << PVS_SHIFT
    out, cut = [], 0
    for x0 in range(ROOM[0], ROOM[2], g):
        col = []
        for y0 in range(ROOM[1], ROOM[3], g):
            vis = 0
            for p in pvs_points(x0, y0, x0 + g, y0 + g, occ):
                if vis == full:
                    break
                vis |= pvs_seen(p, targets, tall, have0 | vis << nb) >> nb
            col.append(vis)
            cut += bin(full & ~vis).count("1")
        out.append(col)
    sys.stderr.write("arenagen: arena %s: the pickups' PVS culls %.1f%% of "
                     "pickup-cells\n" % (tag, 100.0 * cut /
                                          (len(pks) * len(out) * len(out[0]))))
    return out


def pvs_bytes():
    """A cell's mask, bytes: one bit a box, for the largest arena"""
    return (max(len(b) for _, _, b, _ in arenas()) + 7) // 8


# --- the dummies' patrols: closed loops of waypoints clear of every block ----
PATHS = [
    [(320, 384), (1728, 384), (1728, 768), (320, 768)],
    [(768, 1280), (1280, 1280), (1280, 1664), (768, 1664)],
    [(1728, 1664), (1728, 1280), (1344, 800), (704, 800), (320, 1280),
     (320, 1664)],
]

# --- the skeleton ------------------------------------------------------------
# joints: 0 head, 1 neck, 2 pelvis, 3 L elbow, 4 L hand, 5 R elbow, 6 R hand,
#         7 L knee, 8 L foot, 9 R knee, 10 R foot
# local frame: x right, y up, z forward (metres)
NJ = 11
assert NJ == 11, "wrender.inc's WA_LIMB calls and WA_MINMAX are written for 11"
THIGH, SHIN, UARM, FARM = 0.46, 0.46, 0.30, 0.28


def rot_x(p, about, ang):
    """Rotate point p round the x axis through `about` by ang (radians);
    positive tips +y toward +z (forward)."""
    x, y, z = p
    ay, az = about[1], about[2]
    dy, dz = y - ay, z - az
    c, s = math.cos(ang), math.sin(ang)
    return (x, ay + dy * c + dz * s, az - dy * s + dz * c)


def limb(base, ang, length):
    """A limb from base hanging DOWN, swung forward by ang (radians)."""
    return (base[0], base[1] - length * math.cos(ang),
            base[2] + length * math.sin(ang))


def pose(hipL, kneeL, hipR, kneeR, shL, elL, shR, elR, lean=0.0, bob=0.0,
         fall=0.0, sink=0.0):
    """Angles in degrees. hip/shoulder: forward swing of the upper limb;
    knee: backward bend of the shin; elbow: forward bend of the forearm.
    lean tips the torso forward about the pelvis; fall tips the WHOLE body
    backward about the feet's line; sink lowers the pelvis (bent knees)."""
    r = math.radians
    pel = (0.0, 0.96 + bob - sink, 0.0)
    neck = (0.0, pel[1] + 0.52, 0.0)
    head = (0.0, neck[1] + 0.22, 0.0)
    shoulderL = (-0.17, neck[1] - 0.04, 0.0)
    shoulderR = (0.17, neck[1] - 0.04, 0.0)
    eL = limb(shoulderL, r(shL), UARM)
    hL = limb(eL, r(shL + elL), FARM)
    eR = limb(shoulderR, r(shR), UARM)
    hR = limb(eR, r(shR + elR), FARM)
    upper = [head, neck, eL, hL, eR, hR]
    if lean:
        upper = [rot_x(p, pel, r(lean)) for p in upper]
    head, neck, eL, hL, eR, hR = upper
    hipLp = (-0.10, pel[1], 0.0)
    hipRp = (0.10, pel[1], 0.0)
    kL = limb(hipLp, r(hipL), THIGH)
    fL = limb(kL, r(hipL - kneeL), SHIN)
    kR = limb(hipRp, r(hipR), THIGH)
    fR = limb(kR, r(hipR - kneeR), SHIN)
    pts = [head, neck, pel, eL, hL, eR, hR, kL, fL, kR, fR]
    if fall:
        pts = [rot_x(p, (0, 0, 0), -r(fall)) for p in pts]
        pts = on_floor(pts)
    return pts


def on_floor(pts):
    """Nothing sinks through the floor: the whole pose lifted onto it"""
    low = min(p[1] for p in pts)
    if low < 0:
        pts = [(p[0], p[1] - low, p[2]) for p in pts]
    return pts


def run_frame(i, n):
    t = 2 * math.pi * i / n
    sw = math.sin(t)
    return pose(hipL=38 * sw, kneeL=15 + 55 * max(0.0, -math.sin(t + 0.6)),
                hipR=-38 * sw, kneeR=15 + 55 * max(0.0, math.sin(t + 0.6)),
                shL=-35 * sw, elL=75, shR=70, elR=10,   # R arm: the pistol
                lean=10, bob=0.05 * abs(math.cos(t)))


def idle_frame(i, n):
    b = 0.012 * math.sin(2 * math.pi * i / n)
    return pose(4, 6, -4, 6, 6, 15, 80, 5, bob=b)


def flinch_frame(i, n):
    k = [0.6, 1.0, 0.5][i]
    return pose(10 * k, 20 * k, -6 * k, 20 * k, -50 * k, 40, 40 - 60 * k, 30,
                lean=-22 * k, sink=0.06 * k)


def death_frame(i, n):
    k = (i + 1) / n
    e = k * k                   # gathers speed as it goes over
    return pose(25 * k, 70 * k, 10 * k, 90 * k, -60 * k - 20, 30 + 40 * k,
                -40 * k, 50 * k, lean=-15 * k, fall=88 * e, sink=0.3 * k)


def collapse_frame(i, n):
    """The shotgun's kill (WIREARENA-WEAPONS-PLAN 2.3): the knees go and the
    body folds FORWARD onto them - where DEATH goes over backward, straight"""
    k = (i + 1) / n
    over = max(0.0, (k - 0.4) / 0.6)
    return on_floor(pose(hipL=70 * k, kneeL=125 * k, hipR=60 * k, kneeR=135 * k,
                shL=-20 + 110 * k, elL=30 + 50 * k, shR=-10 + 100 * k,
                elR=20 + 60 * k, lean=50 * k, fall=-70 * over * over,
                sink=0.5 * k))         # (the crouch's knees: under it)


def gib_frame(i, n):
    """The rocket's kill (WIREARENA-WEAPONS-PLAN 2.3): every joint flies
    apart from where it stood - outward, up and back down to the floor -
    and the renderer draws the joints alone, the bits. Each joint's
    direction and speed are fixed (a golden-angle spread), so the eleven
    scatter evenly; nothing leaves a signed byte (1.98 m) of the feet"""
    t = (i + 1) / n
    out = []
    for j, (x, y, z) in enumerate(pose(0, 0, 0, 0, 0, 0, 0, 0)):
        a = j * 2.39996 + 0.3
        s = 1.25 * (0.55 + 0.45 * ((j * 37) % 10) / 10.0)
        up = 1.1
        b = y + up - 0.04
        out.append((x + s * math.cos(a) * t,
                    min(JTOP - 0.02, max(0.04, y + up * t - b * t * t)),
                    z + s * math.sin(a) * t))
    return out


ANIMS = [                       # name, keyframes, builder, loops
    ("IDLE", 4, idle_frame, True),
    ("RUN", 8, run_frame, True),
    ("FLINCH", 3, flinch_frame, False),
    ("DEATH", 8, death_frame, False),
    ("COLLAPSE", 6, collapse_frame, False),
    ("GIB", 6, gib_frame, False),
]


# The narrow joint path (wrender.inc's WA_FJN) multiplies a joint's height as
# an UNSIGNED byte, and its 16-bit sum holds for heights 0..111 units
# (wa_render's wa_fvn): every keyframe stays inside, or arenagen refuses it.
# (A COLLAPSE that sank two joints 4 below the floor drew them as 252 at
# medium range: two red lines into the sky - WEAPONS-PLAN 3.5)
JMAXY = 111
JTOP = JMAXY / UNIT             # the highest a joint may be, metres

# The joints' order in wa_pose: pose()'s, regrouped so a figure's first
# SEVEN are the ends - head, neck, pelvis, the hands, the feet - and the
# elbows and knees follow (wa_fjl's reduced figure, the J option, reads the
# first seven alone; the renderer's limb pairs follow this order)
JORDER = [0, 1, 2, 4, 6, 8, 10, 3, 5, 7, 9]


def project(pts, k):
    rel = 2 * math.pi * k / NFACE
    c, s = math.cos(rel), math.sin(rel)
    out = []
    for (x, y, z) in pts:
        lat = x * c - z * s
        out.append((int(round(lat * UNIT)), int(round(y * UNIT))))
    return out


def sb(v):
    if not -128 <= v <= 127:
        raise SystemExit("arenagen: %d does not fit a signed byte" % v)
    return v & 0xFF


def angle_of(dx, dy):
    a = math.atan2(dy, dx)
    return int(round(a * 1024 / (2 * math.pi))) & 1023


# --- the BSP (docs/plans/MULTIPLAYER-FPS-PLAN.md section 16, lever 1) --------
# Over BOXES, not segments: a box's faces never hide one another (it is
# convex), so the tree only has to order the boxes, front to back, and the
# room - which encloses everything - is drawn last. Every split is an
# axis-aligned line that separates the boxes WITHOUT cutting one, so the
# guest's node test is one compare and a leaf is one box; an arena with no
# such line is refused here, at build time.
#
# A wall face is one-sided: drawn when the player is on its outer side, and
# p1 -> p2 runs left to right seen from the front. A box's corners are
# c0 (x0,y0), c1 (x1,y0), c2 (x1,y1), c3 (x0,y1); its faces are south c0->c1,
# east c1->c2, north c2->c3, west c3->c0. The room's run the other way.

def box_tree(ids, nodes, BOXES):
    """-> node index. nodes: [kind, box, value, low, high]; kind 0 splits on
    x, 1 on y, 2 is a leaf holding one box."""
    me = len(nodes)
    nodes.append(None)
    if len(ids) == 1:
        nodes[me] = [2, ids[0], 0, -1, -1, ids]
        return me
    best = None
    for axis in (0, 1):
        for v in sorted({BOXES[i][axis] for i in ids} |
                        {BOXES[i][axis + 2] for i in ids}):
            low = [i for i in ids if BOXES[i][axis + 2] <= v]
            high = [i for i in ids if BOXES[i][axis] >= v]
            if low and high and len(low) + len(high) == len(ids):
                score = abs(len(low) - len(high))
                if best is None or score < best[0]:
                    best = (score, axis, v, low, high)
    if best is None:
        raise SystemExit("arenagen: no axis-aligned line separates boxes %r "
                         "without cutting one - move a box" % ids)
    _, axis, v, low, high = best
    lo = box_tree(low, nodes, BOXES)
    hi = box_tree(high, nodes, BOXES)
    nodes[me] = [axis, 0, v, lo, hi, ids]
    return me


def inside(x, y, boxes, r):
    if not (ROOM[0] + r < x < ROOM[2] - r and ROOM[1] + r < y < ROOM[3] - r):
        return True
    return any(a - r < x < c + r and b - r < y < d + r
               for (a, b, c, d) in boxes)


MAXKS = 8          # distinct steps between coordinates (wa_products)


def face_line(b, f):
    """Face f of box b: (axis, value, lo, hi) - the line it lies on (axis 0:
    x = value, 1: y = value) and its extent along it"""
    x0, y0, x1, y1 = b
    return {"S": (1, y0, x0, x1), "N": (1, y1, x0, x1),
            "E": (0, x1, y0, y1), "W": (0, x0, y0, y1)}[f]


def covered(lo, hi, spans):
    """[lo, hi] wholly covered by the union of spans?"""
    at = lo
    for a, b in sorted(spans):
        if a > at:
            return False
        at = max(at, b)
        if at >= hi:
            return True
    return at >= hi


def face_bits(i, boxes):
    """HEIGHTS-PLAN 7.2.1: bits 0-3 face S E N W drawn, 4-7 its top edge.
    A face against the room wall, or wholly covered by neighbours at least
    as tall (a lift counts at its rest height, and its own faces at their
    raised one), is not drawn; a top edge only where neighbours of exactly
    the same height cover it, so the top runs on unbroken."""
    b = boxes[i]
    mine = max(b.h, b.top or 0)
    bits = 0
    for k, f in enumerate(FACES):
        ax, v, lo, hi = face_line(b, f)
        opp = {"S": "N", "N": "S", "E": "W", "W": "E"}[f]
        tall, same = [], []
        for j, n in enumerate(boxes):
            if j == i:
                continue
            nax, nv, nlo, nhi = face_line(n, opp)
            if nax != ax or nv != v or nhi <= lo or nlo >= hi:
                continue
            if n.h >= mine:
                tall.append((nlo, nhi))
            if n.h == b.h and n.kind != LIFT and b.kind not in (LIFT, FLIGHT):
                same.append((nlo, nhi))     # (a ramp's top edge always: its
                                            # high end is what closes the
                                            # slope's columns, HEIGHTS-PLAN
                                            # 7.4.2, as no neighbour's is)
        wall = v in ((ROOM[0], ROOM[2]) if ax == 0 else (ROOM[1], ROOM[3]))
        if not (wall or covered(lo, hi, tall)):
            bits |= 1 << k
        if not covered(lo, hi, same):
            bits |= 16 << k
    return bits


def kind_byte(b, lifts):
    if b.kind == FLIGHT:
        return FLIGHT | FACES.index(b.toward) << 2 | b.treads << 4
    if b.kind == LIFT:
        return LIFT | lifts.index(b) << 4
    return SOLID


def height_checks(tag, boxes):
    """HEIGHTS-PLAN 1.7, 3.1: every rise a walker meets is at most STEPUP,
    a platform no walk reaches is within the jump, a lift's rest is a step
    and its raised height meets a neighbour's top"""
    top = hmax(boxes)
    apex = jump_apex()

    def neighbours(b):
        for f in FACES:
            ax, v, lo, hi = face_line(b, f)
            opp = {"S": "N", "N": "S", "E": "W", "W": "E"}[f]
            for n in boxes:
                nax, nv, nlo, nhi = face_line(n, opp)
                if n is not b and nax == ax and nv == v and nhi > lo and nlo < hi:
                    yield f, n
    reach = set()
    for b in boxes:
        if b.kind == FLIGHT:
            if not 1 <= b.treads <= 15:          # (its nibble, and the
                raise SystemExit("arenagen: arena %s: %s has %d treads - a "
                                 "flight has 1 to 15 (the renderer divides by "
                                 "them)" % (tag, b.name, b.treads))
            rise, odd = divmod(b.h, b.treads)
            if odd or rise > STEPUP:
                raise SystemExit("arenagen: arena %s: %s rises %d/%d a tread "
                                 "- a walk climbs %d" % (tag, b.name, b.h,
                                                         b.treads, STEPUP))
            ends = [n for f, n in neighbours(b) if f == b.toward]
            if not ends or any(not 0 <= n.h - b.h <= STEPUP for n in ends):
                raise SystemExit("arenagen: arena %s: %s does not end a step "
                                 "below what it climbs to" % (tag, b.name))
            reach |= {id(n) for n in ends}
        if b.kind == LIFT:
            if b.h > STEPUP:
                raise SystemExit("arenagen: arena %s: %s rests %d up - not a "
                                 "step" % (tag, b.name, b.h))
            meet = [n for f, n in neighbours(b) if abs(n.h - b.top) <= STEPUP]
            if not meet:
                raise SystemExit("arenagen: arena %s: %s rises to %d, which "
                                 "meets no neighbour's top" % (tag, b.name, b.top))
            reach |= {id(n) for n in meet}
    for b in boxes:
        if b.kind == SOLID and STEPUP < b.h < top and id(b) not in reach \
                and b.h > apex - 8:
            raise SystemExit("arenagen: arena %s: %s, %d up, is above the "
                             "jump (%d) and no flight or lift reaches it"
                             % (tag, b.name, b.h, apex))


def arena_tables(w, tag, boxes, start):
    """One arena's tables, every label prefixed wa_<tag>_; -> its counts."""
    boxes = [bx(b) for b in boxes]
    if inside(start[0], start[1], boxes, 20):
        raise SystemExit("arenagen: arena %s starts the player INSIDE a wall "
                         "at %r - every step would collide" % (tag, start))
    height_checks(tag, boxes)
    flat = all(b.h >= hmax(boxes) and b.kind == SOLID for b in boxes)
    for p in ([] if tag in NOPATROL else ARENA_PATHS.get(tag, PATHS)):
        for j in range(len(p)):
            (x0, y0), (x1, y1) = p[j], p[(j + 1) % len(p)]
            if flat:
                for k in range(33):
                    x, y = x0 + (x1 - x0) * k / 32, y0 + (y1 - y0) * k / 32
                    if inside(x, y, boxes, 12):
                        raise SystemExit("arenagen: arena %s: a patrol runs "
                                         "into a wall near (%d, %d)" % (tag, x, y))
                continue
            # HEIGHTS: a dummy stands on the floor under its point (wa_figtick)
            # and walks SPEED a tick, so each tick's rise is at most a step
            # and no leg crosses a wall or a lift (which moves)
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) // SPEED))
            prev = floor_at(x0, y0, boxes, FRAD)
            for k in range(n + 1):
                x, y = x0 + (x1 - x0) * k // n, y0 + (y1 - y0) * k // n
                if inside(x, y, [b for b in boxes if b.h >= hmax(boxes)
                                 or b.kind == LIFT], 12):
                    raise SystemExit("arenagen: arena %s: a patrol runs into "
                                     "a wall or a lift near (%d, %d)" % (tag, x, y))
                f = floor_at(x, y, boxes, FRAD)
                if abs(f - prev) > STEPUP:
                    raise SystemExit("arenagen: arena %s: a patrol steps %d at "
                                     "(%d, %d) - a walk takes %d" % (tag, f - prev,
                                                                    x, y, STEPUP))
                prev = f
    nodes = []
    box_tree(list(range(len(boxes))), nodes, boxes)
    pts = []
    for (a, b, c, d) in [ROOM] + boxes:
        pts += [(a, b), (c, b), (c, d), (a, d)]
    xs = sorted({p[0] for p in pts})
    ys = sorted({p[1] for p in pts})
    verts, vix = [], {}
    for p in pts:
        if p not in vix:
            vix[p] = len(verts)
            verts.append(p)
    if len(verts) * 2 > 255 or len(boxes) * 8 > 255 or len(xs) * 4 > 255 \
            or len(ys) * 4 > 255:
        raise SystemExit("arenagen: the arena outgrew a byte index")
    # wa_products makes a coordinate's products from the one before it, by
    # adding the products of the STEP between them, made once a frame: so
    # the distinct steps an arena has are few, and each fits x 4 in 16 bits
    steps = {b - a for vals in (xs, ys) for a, b in zip(vals, vals[1:])}
    if len(steps) > MAXKS or max(steps) * 4 > 32767:
        raise SystemExit("arenagen: arena %s: %d distinct coordinate steps, "
                         "largest %d - wa_products takes at most %d, each "
                         "under 8192" % (tag, len(steps), max(steps), MAXKS))
    for (a, b, c, d) in boxes:          # (a box may stand against a wall:
        if not (ROOM[0] <= a < c <= ROOM[2] and ROOM[1] <= b < d <= ROOM[3]):
            raise SystemExit("arenagen: arena %s: a box outside the room - "
                             "WA_ZMAX assumes none is" % tag)
    P = "wa_%s_" % tag
    w(P + "xv:      dw " + ", ".join(str(x) for x in xs))
    w(P + "yv:      dw " + ", ".join(str(y) for y in ys))
    w(P + "vtx:                         ; x index x 4, y index x 4 (byte offsets")
    w("                                ; into the per-frame product tables)")
    for (x, y) in verts:
        w("    db %d, %d" % (xs.index(x) * 4, ys.index(y) * 4))
    w(P + "corn:                        ; per box (the room first): its corners")
    w("                                ; c0..c3 as vertex x 2")
    for (a, b, c, d) in [ROOM] + boxes:
        w("    db " + ", ".join(str(vix[p] * 2) for p in
                                [(a, b), (c, b), (c, d), (a, d)]))
    w(P + "bsp:                         ; kind (0 x, 1 y, 2 leaf), box x 8 (a")
    w("                                ; leaf's, into wa_boxes), value, low,")
    w("                                ; high (0 = none) - ADDRESSES in the image")
    w("                                ; this is assembled into: walked in place")
    w("                                ; there, or rebased by the renderer's")
    w("                                ; ARENA verb out of an arena part - and")
    w("                                ; the bounds of the boxes under it, x0")
    w("                                ; y0 x1 y1 as coordinate indices x 4,")
    w("                                ; for wa_node's view-cone test")
    for (kind, box, v, lo, hi, ids) in nodes:
        bb = (min(boxes[i][0] for i in ids), min(boxes[i][1] for i in ids),
              max(boxes[i][2] for i in ids), max(boxes[i][3] for i in ids))
        w("    db %d, %d" % (kind, box * 8))
        w("    dw %d, %s, %s" % (v, P + "bsp+%d" % (lo * 12) if lo >= 0 else "0",
                              P + "bsp+%d" % (hi * 12) if hi >= 0 else "0"))
        w("    db %d, %d, %d, %d" % (xs.index(bb[0]) * 4, ys.index(bb[1]) * 4,
                                    xs.index(bb[2]) * 4, ys.index(bb[3]) * 4))
    w(P + "bcol:                        ; per box (the room first): its colour")
    w("                                ; - 0 a boundary wall, 1 an item. The")
    w("                                ; owner's call: colour says WHAT a wall")
    w("                                ; is, not how far (two shades never read")
    w("                                ; as depth, and Hercules has none)")
    w("    db 0" + "".join(", %d" % b.col for b in boxes))
    w(P + "boxes:                       ; x0, y0, x1, y1")
    for b in boxes:
        w("    dw %d, %d, %d, %d" % b)
    lifts = [b for b in boxes if b.kind == LIFT]
    if len(lifts) > 1:
        raise SystemExit("arenagen: arena %s has %d lifts - the sim moves one "
                         "(HEIGHTS-PLAN 7.4)" % (tag, len(lifts)))
    w(P + "bxh:                         ; per box: height (a lift's at rest),")
    w("                                ; kind, faces (HEIGHTS-PLAN 7.2.1)")
    for i, b in enumerate(boxes):
        w("    dw %d" % b.h)
        w("    db %d, %d" % (kind_byte(b, lifts), face_bits(i, boxes)))
    w(P + "lifts:                       ; count; box, 0, rest, raised")
    w("    dw %d" % len(lifts))
    for b in lifts:
        w("    db %d, 0" % boxes.index(b))
        w("    dw %d, %d" % (b.h, b.top))
    sys.stderr.write("arenagen: arena %s: %d boxes in a %d-node tree, %d "
                     "vertices, %d x and %d y values\n"
                     % (tag, len(boxes), len(nodes), len(verts), len(xs),
                        len(ys)))
    return len(xs), len(ys), len(verts), len(boxes), len(nodes)


def bsp_tables(w):
    """Every arena, then their descriptors (SPEC: wa_loadarena copies one into
    the working tables; the tree stays where it is) and the maxima the
    working tables are sized to."""
    counts = []
    w("%ifdef WA_TAB_ARENAS")
    for tag, name, boxes, start in arenas():
        counts.append(arena_tables(w, tag, boxes, start))
    w("%endif")
    w("WA_NARENA equ %d" % len(counts))
    w("WA_MXV equ %d" % max(c[0] for c in counts))
    w("WA_MYV equ %d" % max(c[1] for c in counts))
    w("WA_MVTX equ %d" % max(c[2] for c in counts))
    w("WA_MBOX equ %d" % max(c[3] for c in counts))
    w("WA_MNODE equ %d" % max(c[4] for c in counts))
    w("WA_MAXKS equ %d" % MAXKS)
    w("WA_MPK equ %d" % WA_MPK)
    w("WA_PVSB equ %d" % pvs_bytes())   # (a cell's mask, and the most cells)
    w("WA_PVSN equ %d" % (((ROOM[2] - ROOM[0]) >> PVS_SHIFT) *
                          ((ROOM[3] - ROOM[1]) >> PVS_SHIFT)))
    # the deepest a point can be: the player and every wall are in the room,
    # so no z exceeds its diagonal (wa_rcp covers NEAR..WA_ZMAX-1)
    w("WA_ZMAX equ %d" % (int(math.hypot(ROOM[2] - ROOM[0],
                                         ROOM[3] - ROOM[1])) + 2))
    w("%ifdef WA_TAB_ARENAS")
    w("wa_arenas:                      ; xv, nxv, yv, nyv, vtx, nvtx, corn,")
    w("                                ; boxes, nbox, root, start x, y, angle,")
    w("                                ; colours")
    for (tag, name, boxes, start), (nx, ny, nv, nb, nn) in zip(arenas(), counts):
        P = "wa_%s_" % tag
        w("    dw %sxv, %d, %syv, %d, %svtx, %d, %scorn" % (P, nx, P, ny, P, nv, P))
        w("    dw %sboxes, %d, %sbsp, %d, %d, %d, %sbcol" % (
            P, nb, P, start[0], start[1], start[2], P))
    w("%endif")
    w("WA_ARENASZ equ 28")

def main(out):
    L = []
    w = L.append
    w("; GENERATED by tools/arenagen.py - do not edit (docs/plans/"
      "MULTIPLAYER-FPS-PLAN.md)")
    w("WA_NJ equ %d" % NJ)
    w("WA_NFACE equ %d" % NFACE)
    w("WA_SPEED equ %d" % SPEED)
    w("WA_STEPUP equ %d" % STEPUP)
    w("WA_FRAD equ %d" % FRAD)
    w("WA_ROOM_X0 equ %d" % ROOM[0])
    w("WA_ROOM_Y0 equ %d" % ROOM[1])
    w("WA_ROOM_X1 equ %d" % ROOM[2])
    w("WA_ROOM_Y1 equ %d" % ROOM[3])
    w("%ifdef WA_TAB_SIN")
    w("wa_sin:")                          # a QUARTER wave, 0..256 inclusive:
    for i in range(0, 257, 8):            # wa_sincos mirrors it, and every
        w("    dw " + ", ".join(str(int(round(16384 * math.sin(  # angle comes
            2 * math.pi * j / 1024))))     # out as the whole table's did
            for j in range(i, min(i + 8, 257))))
    w("%endif")
    bsp_tables(w)
    # paths: per dummy, a count and per leg (x, y, heading, steps)
    w("WA_NFIG equ %d" % len(PATHS))
    # an arena's own patrols, as its part carries them (path_block): the
    # most bytes any takes, which the frame block's ARENA keeps room for
    w("WA_APATHSZ equ %d" % max([2] + [2 * len(path_block(ARENA_PATHS[t],
                                                         [bx(b) for b in bs]))
                                       for t, _, bs, _ in arenas()
                                       if t in ARENA_PATHS]))
    w("%ifdef WA_TAB_PATHS")
    w("wa_pathtab:")
    for i in range(len(PATHS)):
        w("    dw wa_path%d" % i)
    for i, p in enumerate(PATHS):
        w("wa_path%d:" % i)
        w("    dw %d                      ; legs" % len(p))
        for j, (x, y) in enumerate(p):
            nx, ny = p[(j + 1) % len(p)]
            dx, dy = nx - x, ny - y
            steps = max(1, int(round(math.hypot(dx, dy) / SPEED)))
            w("    dw %d, %d, %d, %d" % (x, y, angle_of(dx, dy), steps))
    w("%endif")
    # poses
    first = 0
    for name, n, _, _ in ANIMS:
        w("WA_A_%s equ %d" % (name, first))
        w("WA_N_%s equ %d" % (name, n))
        first += n
    w("WA_NFRAMES equ %d" % first)
    w("WA_FRAMESZ equ %d                ; one frame: NFACE x NJ x 2 bytes"
      % (NFACE * NJ * 2))
    w("%ifdef WA_TAB_POSE")
    w("wa_pose:")
    for name, n, fn, loops in ANIMS:
        frames = []
        for i in range(n):
            pts = fn(i, n)
            frames.append([[pr[j] for j in JORDER]
                           for pr in (project(pts, k) for k in range(NFACE))])
        # wa_fjl's narrow path blends a joint between two keyframes in
        # BYTES: B - A must be a signed byte for each coordinate between
        # every pair it can blend - the next keyframe, and the first after
        # the last when it loops (one that holds blends its last with itself)
        for i in range(n):
            for k in range(NFACE):
                for (a, b) in frames[i][k]:
                    if not 0 <= b <= JMAXY:
                        raise SystemExit("arenagen: %s %d facing %d: a "
                                         "joint %d units up - the narrow "
                                         "path takes 0..%d (WA_FJN)"
                                         % (name, i, k, b, JMAXY))
        for i in range(n if loops else n - 1):
            for k in range(NFACE):
                for (a, b), (c, d) in zip(frames[i][k],
                                          frames[(i + 1) % n][k]):
                    if not (-128 <= c - a <= 127 and -128 <= d - b <= 127):
                        raise SystemExit("arenagen: %s %d facing %d: a "
                                         "joint moves past a signed byte "
                                         "(wa_fjl's blend)" % (name, i, k))
        for i in range(n):
            for k in range(NFACE):
                w("    db " + ", ".join("%d,%d" % (sb(a), sb(b))
                                         for a, b in frames[i][k]) +
                  "   ; %s %d facing %d" % (name, i, k))
    w("%endif")
    # Every constant first, once: an includer that wants the constants
    # before its own layout and the data blocks later (the renderer part,
    # apps/wirearena/wrpart.asm) includes this file twice, and the second
    # pass defines only the data it asks for
    const = [l for l in L[1:] if re.match(r"^WA_\w+ equ ", l)]
    rest = [l for l in L[1:] if not re.match(r"^WA_\w+ equ ", l)]
    L = L[:1] + ["%ifndef WATAB_CONSTS", "%define WATAB_CONSTS"] + const + \
        ["%endif"] + rest
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")


def path_block(paths, boxes):
    """An arena's own patrols as its part carries them (HEIGHTS-PLAN 7.4.5):
    WA_NFIG words, each path's offset in the block, then per path a leg
    count and per leg (x, y, heading, steps) - the primary's wa_pathN rows,
    which wa_spawn and wa_figtick walk. -> the block's words"""
    if len(paths) != len(PATHS):
        raise SystemExit("arenagen: an arena's own patrols must be %d (WA_NFIG)"
                         % len(PATHS))
    words, offs = [], []
    at = 2 * len(paths)
    for p in paths:
        offs.append(at)
        words.append(len(p))
        for j, (x, y) in enumerate(p):
            nx, ny = p[(j + 1) % len(p)]
            dx, dy = nx - x, ny - y
            steps = max(1, int(round(math.hypot(dx, dy) / SPEED)))
            # bit 15 of the heading: the leg leaves the ground somewhere
            # (wa_figz reads the floor only on such a leg)
            up = any(floor_at(x + dx * k / steps, y + dy * k / steps,
                              boxes, FRAD) for k in range(steps + 1))
            words += [x, y, angle_of(dx, dy) | (0x8000 if up else 0), steps]
        at = 2 * len(paths) + 2 * len(words)
    return offs + words


def arena_part(n, out):
    """Arena N as an OP_ASSET part of WARENA.O88, assembled at org 0
    (docs/plans/WIREARENA-PARTS-PLAN.md 7.5): wa_arenas' descriptor row at
    offset 0 - every table offset relative to the part, the tree's links too
    - plus the tree's node count, then the tables it names."""
    tag, name, boxes, start = arenas()[n]
    T = []
    nx, ny, nv, nb, nn = arena_tables(T.append, tag, boxes, start)
    import wamodel                      # (it reads the arenas from here)
    (kb, kp), (ke, ep) = wamodel.budget(n)
    if kb > wamodel.BUDGET_BOXES or ke > wamodel.BUDGET_EDGES:
        raise SystemExit("arenagen: arena %s is over the visible budget "
                         "(docs/plans/WIREARENA-HEIGHTS-PLAN.md 4.2): %d boxes "
                         "in view at %r, %d outline edges at %r - at most %d "
                         "and %d" % (tag, kb, kp, ke, ep, wamodel.BUDGET_BOXES,
                                     wamodel.BUDGET_EDGES))
    P = "wa_%s_" % tag
    L = ["; GENERATED by tools/arenagen.py - do not edit: arena %d (%s), an "
         "OP_ASSET part" % (n, name),
         "; of WARENA.O88 (docs/plans/WIREARENA-PARTS-PLAN.md 7.5)",
         "    cpu 8086", "    bits 16", "    org 0",
         "    dw %sxv, %d, %syv, %d, %svtx, %d, %scorn" % (P, nx, P, ny, P, nv,
                                                         P),
         "    dw %sboxes, %d, %sbsp, %d, %d, %d, %sbcol, %d" % (
             P, nb, P, start[0], start[1], start[2], P, nn),
         "    dw %sbxh, %d, %d, %slifts" % (P, room_h(boxes), hmax(boxes), P)]
    pb = path_block(ARENA_PATHS[tag], [bx(b) for b in boxes]) \
        if tag in ARENA_PATHS else []
    L += ["    dw %s, %d                ; its own patrols: offset, bytes (0: the "
          "primary's)" % (P + "paths" if pb else "0", 2 * len(pb))]
    pv = wamodel.A.pvs_masks(tag, boxes)    # (the budget's walk made them)
    L += ["    dw %s                    ; its PVS (0: none): grid shift, cells "
          "a column, masks" % (P + "pvs" if pv else "0")]
    pk = pickups(tag, boxes)
    pkv = pvs_pickups(tag, boxes, pk)
    L += ["    dw %s, %s               ; its pickups (0: none), and their PVS "
          "bytes (0: none - every pickup tested)" % (
              P + "pks" if pk else "0", P + "pkv" if pkv else "0")] + T
    if pk:
        L.append(P + "pks:                     ; count; x, y, z, kind, choices")
        L.append("    dw %d" % len(pk))
        for (k, x, y, z, ch) in pk:
            L.append("    dw %d, %d, %d" % (x, y, z))
            L.append("    db %d, %d" % (k, ch))
    if pkv:
        L.append(P + "pkv:                     ; a byte a PVS cell, column-major")
        for col in pkv:
            L.append("    db " + ", ".join(str(m) for m in col))
    if pv:
        nb_ = pvs_bytes()
        L.append(P + "pvs:")
        L.append("    db %d, %d" % (PVS_SHIFT, len(pv[0])))
        L.append("    dw %d" % (len(pv) * len(pv[0]) * nb_))
        for col in pv:
            L.append("    db " + ", ".join(str(m >> (8 * k) & 255) for m in col
                                           for k in range(nb_)))
    if pb:
        L.append(P + "paths:")
        for i in range(0, len(pb), 8):
            L.append("    dw " + ", ".join(str(v) for v in pb[i:i + 8]))
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--arena":
        arena_part(int(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        raise SystemExit(__doc__)
