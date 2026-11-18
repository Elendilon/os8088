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


def floor(sec, x0, y0, x1, y1, z, float_=True):
    ROOMS_TXT.append("floor rect %3d %3d %3d %3d  flat %g   # %s" % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, z, sec))
    if float_:
        ROOMS_TXT.append("float rect %3d %3d %3d %3d" % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF))
        FLOATS.update((x, y) for x in range(x0, x1) for y in range(y0, y1))
    for x in range(x0, x1):
        for y in range(y0, y1):
            CELLS[(x, y)] = (z, z, z, z)
            SECTION[(x, y)] = sec


def ramp(sec, axis, x0, y0, x1, y1, z0, z1, float_=True):
    p0, p1 = (x0, x1) if axis == "x" else (y0, y1)
    ROOMS_TXT.append("floor rect %3d %3d %3d %3d  ramp %s %d %d %g %g   # %s"
                     % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, axis, p0 + OFF, p1 + OFF, z0, z1, sec))
    if float_:
        ROOMS_TXT.append("float rect %3d %3d %3d %3d" % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF))
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


def chute(sec, ways, depth):
    """a 2-wide shaped channel: its crease through the cell corners `ways`
    [(x, y, lip z)], its bottom `depth` units under the lip on the crease,
    rising as a parabola to the lip one tile either side"""
    CHUTE_TXT.append("chute 2 round depth %d " % round(depth * 8)
                     + " ".join("way %d %d %g" % (x + OFF, y + OFF, z) for x, y, z in ways))
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


def rail(x0, y0, x1, y1, style="block"):
    """a rail along a tile edge: a BLOCK rail (a wall tile) or a see-through GUARD rail (SPEC.md 130.35), the
    style a choice per rail (the course guide's G24); either takes the tile on the void side of the edge"""
    RAILS.append((x0, y0, x1, y1, style))


Z = 24                                   # the start's height, units
# Every island FLOATS (faces 3 units deep): void between the levels, a gap you can see.  Teach, then test:
#   A  the start island        T1 a 1-tile gap, LEVEL: the first Hop (a wide window, 549 ms)
#   T2 a 1-tile gap, half a unit DOWN, then a ramp to L
#   U  a 1-UNIT STEP UP from L: "and again" is the easy answer (531 ms against a Hop's 128); a miss bounces back
#   V  flag 0 on U, then a 2-TILE gap, LEVEL: Hop and "and again" (348 ms; a Hop alone 73) - TAUGHT, railed
#   W  a ramp and a run to the basin B, whose SPRING throws the ball BACK up the screen (away from the camera,
#      CD1) onto H, 6 units up, on the course's right where nothing earlier stands
#   R  a long ramp down from H to D; then the TEST: a 1-unit step up (S) and a 2-tile gap (E), unrailed
#   G  the goal
floor("A", 4, 4, 8, 8, Z)                                    # the start island
rail(4, 4, 8, 4); rail(4, 4, 4, 8)
floor("T", 4, 9, 8, 13, Z)                                   # T1: a 1-tile gap (y 8), level
rail(4, 13, 8, 13)                                           # (its far edge: an over-Hop is caught)
floor("T", 9, 9, 13, 13, Z - 0.5)                            # T2: a 1-tile gap (x 8), half a unit down
rail(13, 9, 13, 13)
ramp("L", "y", 9, 13, 13, 15, Z - 0.5, Z - 2.5)              # down to L
floor("L", 9, 15, 13, 19, Z - 2.5)                           # L
rail(9, 19, 13, 19)
floor("U", 13, 15, 17, 19, Z - 1.5)                          # U: ONE UNIT UP from L (its face is L's far edge)
rail(17, 15, 17, 19); rail(13, 15, 17, 15)
floor("V", 13, 21, 17, 25, Z - 1.5)                          # V: a 2-tile gap (y 19 - 20), level
rail(13, 25, 17, 25); rail(13, 21, 13, 25)
ramp("W", "x", 17, 21, 19, 25, Z - 1.5, Z - 3.5)             # W: down, and a run
floor("W", 19, 21, 25, 25, Z - 3.5)
rail(19, 25, 25, 25)
floor("B", 25, 21, 29, 25, Z - 3.5)                          # B: the basin, the SPRING
rail(25, 25, 29, 25); rail(29, 21, 29, 25)
SPRINGS.append((27, 22, 768))                                # thrown -y, over the void row (y 20), onto H
floor("H", 25, 15, 29, 20, Z + 2.5)                          # H: 6 units over the basin, BEHIND it
rail(25, 15, 29, 15); rail(25, 15, 25, 20)                   # (its back edges: an over-throw is caught)
ramp("R", "x", 29, 15, 33, 19, Z + 2.5, Z - 1.5)             # R: the long ramp down
floor("D", 33, 15, 37, 19, Z - 1.5)                          # D: flag 2
rail(37, 15, 37, 19); rail(33, 15, 37, 15)
floor("S", 33, 19, 37, 23, Z - 0.5)                          # S: the TEST step, one unit up from D
floor("E", 33, 25, 37, 29, Z - 0.5)                          # E: the TEST gap, 2 tiles (y 23 - 24), level
ramp("G", "y", 33, 29, 37, 32, Z - 0.5, Z - 3.5)
floor("G", 32, 32, 38, 37, Z - 3.5)                          # the goal plateau
rail(32, 37, 38, 37); rail(38, 32, 38, 37); rail(32, 32, 32, 37)
GOAL = {(x, y) for x in range(32, 38) for y in range(35, 37)}

START = (5.5, 5.5)
# a flag stands just BEFORE what can kill, so a fall never replays a long stretch
FLAGS = [(14.5, 17.5, "flag 0"), (26.5, 23.5, "flag 1"), (34.5, 16.5, "flag 2")]
# clocks (the owner places them; these are first guesses): (wx, wy, the tile's floor z, name, kind)
CLOCKS = [(8.5, 5.5, Z, "start", "tile"), (24.5, 17.5, Z - 2, "middle", "float"),
          (31.5, 34.5, Z - 1.5, "finish", "block")]
PLACED = {}

# the route, as the player rolls it (the sketch's centre line, not a demo)
ROUTE = [(5.5, 5.5), (6, 8.5), (6, 11), (8.5, 11), (11, 11), (11, 14), (11, 17), (15, 17), (15, 20),
         (15, 23), (18, 23), (22, 23), (27.5, 23), (27.5, 22.5), (27.5, 19), (27, 17), (31, 17),
         (35, 17), (35, 21), (35, 24), (35, 27), (35, 30), (35, 36)]
LABELS = [(6, 6, "A start"), (6, 11, "T1 hop"), (11, 11, "T2 hop down"), (11, 17, "L"),
          (15, 17, "U step+again"), (15, 23, "V 2-gap"), (21, 23, "W run"), (27, 23, "B spring"),
          (27, 17, "H high"), (31, 17, "R ramp"), (35, 17, "D"), (35, 21, "S test step"),
          (35, 27, "E test gap"), (35, 35, "G goal")]

# --- drawing ----------------------------------------------------------------
SECCOL = {"S": (150, 200, 240), "U": (150, 200, 240), "V": (240, 200, 150), "R": (200, 200, 120), "L": (160, 220, 160),
          "A": (120, 200, 120), "B": (210, 190, 120), "C": (220, 150, 110), "T": (200, 200, 200),
          "D": (130, 170, 220), "E": (180, 140, 210), "F": (220, 150, 110), "G": (200, 200, 200), "W": (150, 210, 200),
          "H": (240, 240, 140)}


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
    for x, y, z, f in PLACED.values():
        d.ellipse([x * S - 7, y * S - 7, x * S + 7, y * S + 7], outline=(0, 255, 255), width=2)
    for x, y, t in FLAGS:
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
    ground = Z - 26 - 3
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
    for x, y, t in FLAGS:
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
    for i, (x, y) in enumerate((ROUTE[0], ROUTE[15], ROUTE[-1])):
        _, cy = Q(x, y, zat(x, y))
        d.rectangle([mid - 160, cy - 100, mid + 160, cy + 100], outline=(0, 255, 255))
    d.line([mid - 80, 0, mid - 80, H], fill=(70, 70, 120))
    d.line([mid + 80, 0, mid + 80, H], fill=(70, 70, 120))
    d.text((8, 8), "route px span %d (CGA dead zone 160); course %d lines tall; cyan boxes = one CGA "
           "window at the start, the chute's clock and the goal" % (max(rx) - min(rx), H - 220), fill=(220, 220, 220))
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
# Course 2, tutorial 2 (working name HOP; docs/plans/bonanza-courses/HOP.md): rubber, the Hop, rubber's "and
# again", a spring.  Floating islands.  Written by docs/plans/bonanza-courses/hop/sketch.py --bbc while the
# layout moves; edited by hand once it settles.
course HOP "Island Hop"
guide                     # a REAL course: held to the course guide's checkable rules
width 64
uses spring
ball rubber
target 30                 # the design class; the sheet aims at about 35 s
"""


def bbc(out):
    if os.path.exists(out) and "--force" not in sys.argv:
        sys.exit("sketch.py: %s exists - the course is edited by hand from here on; --force to re-emit a "
                 "re-laid revision (every hand-made line is in HEAD_TXT below or is lost)" % out)
    L = HEAD_TXT.strip("\n").split("\n") + [""]
    L.append("# rooms (the sketch's sections)")
    L += ROOMS_TXT
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
    taken = {(int(x), int(y)) for x, y, _z, _n, kind in CLOCKS if kind == "block"}
    for (x, y), z in sorted(walls.items()):
        if (x, y) in taken:                     # a clock stands on this block: its tile is the clock's
            continue
        if (x, y) in guards:
            L.append("guard tile %3d %3d                # see-through" % (x + OFF, y + OFF))
        else:
            L.append("wall  tile %3d %3d  flat %g" % (x + OFF, y + OFF, round(z * 2) / 2))
            if any((x + a, y + b) in FLOATS for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                L.append("float tile %3d %3d                # (a floating island's rail)" % (x + OFF, y + OFF))
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
    L.append("goal  rect %d %d %d %d  flat %g" % (min(g[0] for g in GOAL) + OFF, min(g[1] for g in GOAL) + OFF,
                                               max(g[0] for g in GOAL) + 1 + OFF, max(g[1] for g in GOAL) + 1 + OFF,
                                               CELLS[min(GOAL)][0]))
    L.append("start %d %d" % (int(START[0]) + OFF, int(START[1]) + OFF))
    for x, y, t in FLAGS:
        L.append("checkpoint %d %d ball rubber   # %s" % (int(x) + OFF, int(y) + OFF, t))
    L.append("")
    L.append("# clocks (the owner's mark-ups): a tile level with the path one block out, or on top of a block")
    for x, y, z, name, kind in CLOCKS:
        px, py = int(x) + OFF, int(y) + OFF
        L.append("floor tile %d %d  flat %g   # the %s clock's tile (%s)" % (px, py, z, name, {
            "tile": "level with the path, one block out", "block": "on top of the rail block it replaces",
            "float": "a lone floating pillar"}[kind]))
        if kind == "float":
            L.append("float tile %d %d" % (px, py))
        L.append("clock %d %d" % (px, py))
    L.append("")
    L.append("# the autopilot's route")
    for x, y in ROUTE:
        if (int(x), int(y)) not in CHUTE:
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
