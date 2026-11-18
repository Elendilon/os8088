#!/usr/bin/env python3
"""FIRST ROLL, attempt 1: the PAPER sketch (wave 11's pipeline, the pen-in
step).  Host-only, nothing in `make` runs it and it ships nothing.  It is
NOT a .bbc: tiles are tiles, heights are units (8 px), and the pictures are
the game's projection (px = 16 (wx - wy), line = 8 (wx + wy) - 8 z) drawn as
plain blocks, to argue the layout with the owner before anything goes into
the engine.  python3 sketch.py [outdir] -> plan.png, iso.png"""
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
NOTES = []           # (wx, wy, z, text)


OFF = 4             # the engine course's shift (bbc(), below)
ROOMS_TXT, CHUTE_TXT = [], []


def floor(sec, x0, y0, x1, y1, z):
    ROOMS_TXT.append("floor rect %3d %3d %3d %3d  flat %g   # %s" % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, z, sec))
    for x in range(x0, x1):
        for y in range(y0, y1):
            CELLS[(x, y)] = (z, z, z, z)
            SECTION[(x, y)] = sec


def ramp(sec, axis, x0, y0, x1, y1, z0, z1):
    p0, p1 = (x0, x1) if axis == "x" else (y0, y1)
    ROOMS_TXT.append("floor rect %3d %3d %3d %3d  ramp %s %d %d %g %g   # %s"
                     % (x0 + OFF, y0 + OFF, x1 + OFF, y1 + OFF, axis, p0 + OFF, p1 + OFF, z0, z1, sec))
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


Z = 26                                   # the start's height, units
# REVISION 4 (the owner's first play, 2026-11-18): every leg is balanced
# against the next so the route stays inside ONE horizontal camera framing
# (a +x leg moves right on the screen, a +y leg left; the CGA's dead zone is
# 160 px, 10 tiles of wx - wy); the lip, the hole and the chute's mouth lie
# on ONE straight line, so going forward means going over the hole.
# A  the start and the hill of ramps, UNRAILED (revision 5: the owner, "the guard here is that its so
#    wide"): ramps alternate +y and +x; no rail and no back wall
floor("A", 4, 4, 8, 8, Z)                                    # P0 the start
ramp("A", "y", 4, 8, 8, 10, Z, Z - 2)                        # R1
floor("A", 4, 10, 8, 14, Z - 2)                              # L1
ramp("A", "x", 8, 10, 10, 14, Z - 2, Z - 4)                  # R2
floor("A", 10, 10, 14, 14, Z - 4)                            # L2
ramp("A", "y", 10, 14, 14, 16, Z - 4, Z - 6)                 # R3
floor("A", 10, 16, 14, 20, Z - 6)                            # L3
# B  the ledge: two tiles wide, its FRONT edge open to the void
floor("B", 14, 17, 20, 19, Z - 6)
rail(15, 17, 20, 17, "guard")                                # its back: a see-through GUARD rail, its first tile open beside the hill's ramp (revision 6)
# C  flag 0 on M, then the lip: a ramp, a 3-unit step down onto T, a hole
#    where the straight full-speed landing falls, the chute straight beyond it
floor("C", 20, 16, 23, 20, Z - 6)                            # M, flag 0
WALLS += [(20, 15, 23, 16, Z - 4)]
rail(23, 16, 23, 20); rail(20, 19, 20, 20)
ramp("C", "y", 20, 20, 23, 24, Z - 6, Z - 8)                 # the lip ramp: 4 tiles, as the prototype's
rail(20, 20, 20, 24); rail(23, 20, 23, 24)
floor("T", 19, 24, 24, 28, Z - 10)                           # T, 2 units under the lip
rail(19, 24, 19, 28); rail(24, 24, 24, 28); rail(19, 24, 20, 24); rail(23, 24, 24, 24)
rail(19, 28, 21, 28); rail(23, 28, 24, 28)                   # T's far edge: open only at the chute's mouth
HOLES |= {(21, 25)}                                          # ONE BLOCK OUT from the ramp's foot, in the path (the prototype's)
# D  the CHUTE: a shaped two-wide channel, UNFENCED, straight on from the
#    lip (+y), round one corner along +x into D3.  D3's rails come back up
#    as it exits; K3's far end stays OPEN for the full-speed overshoot
chute("D", [(22, 28, Z - 10), (22, 31, Z - 11), (29, 31, Z - 13.5)], 1.0)
floor("D", 29, 30, 31, 32, Z - 13.5)                        # D3, flat: the rails come back up one tile on
rail(29, 30, 31, 30); rail(30, 32, 31, 32)                # one tile on from the chute's exit
floor("D", 31, 30, 34, 33, Z - 13.5)                         # K3, level with D3, its far end open
rail(31, 30, 34, 30); rail(31, 32, 31, 33)
# E  the steps: one unit each, down onto floor; flag 1 on the last
floor("E", 31, 33, 34, 35, Z - 14.5)
floor("E", 31, 35, 34, 37, Z - 15.5)
floor("E", 31, 37, 34, 40, Z - 16.5)
for y0, y1 in ((33, 35), (35, 37), (37, 40)):
    rail(31, y0, 31, y1)
rail(34, 33, 34, 35); rail(34, 35, 34, 37); rail(31, 40, 34, 40)   # (34, 37) open: its lone block read as a tile (revision 6)
# W  the walk: two tiles wide, BOTH edges open: +x, a railed elbow, +y
floor("W", 34, 38, 38, 40, Z - 16.5)                         # W1, level
floor("W", 38, 38, 40, 41, Z - 16.5)
rail(40, 38, 40, 41); rail(38, 38, 40, 38)   # the elbow's lone left block gone: it read as a tile (revision 7)
ramp("W", "y", 38, 41, 40, 43, Z - 16.5, Z - 17.5)          # 2 tiles (revision 5: the lip took 2)
# F  the leap: a railed elbow, a run-up along +x (no rail across its entry:
#    rails protect, never block), a ONE-tile gap, a landing 2 units under the lip
floor("F", 38, 43, 41, 46, Z - 17.5)
rail(38, 43, 38, 46); rail(38, 46, 41, 46); rail(40, 43, 41, 43)
ramp("F", "x", 41, 43, 45, 46, Z - 17.5, Z - 19.5)
rail(41, 43, 45, 43); rail(41, 46, 45, 46)
floor("G", 46, 42, 50, 47, Z - 21.5)                           # the landing
rail(46, 42, 50, 42); rail(50, 42, 50, 47)
# H  the finish: a short ramp down and a wide goal plateau, all in view
ramp("G", "y", 46, 47, 50, 49, Z - 21.5, Z - 22.5)
rail(46, 47, 46, 49); rail(50, 47, 50, 49)
floor("H", 45, 49, 51, 54, Z - 22.5)
rail(45, 49, 45, 54); rail(45, 54, 51, 54); rail(51, 49, 51, 54); rail(45, 49, 46, 49); rail(50, 49, 51, 49)
GOAL = {(x, y) for x in range(45, 51) for y in range(52, 54)}

START = (5.5, 5.5)
# a flag stands just BEFORE what can kill, so a fall never replays a long stretch
FLAGS = [(20.5, 18.5, "flag 0"), (32.5, 38.5, "flag 1")]
# clocks (revision 5, the owner's mark-ups): (wx, wy, the tile's floor z, name, KIND):
#   "tile"  - a floor tile LEVEL with the path, one block out from it (the start's);
#   "block" - on top of an EXISTING block: the rail's wall tile becomes a floor tile at its height;
#   "float" - a lone floating pillar (revision 4's)
CLOCKS = [(8.5, 5.5, Z, "start", "tile"), (18.5, 26.5, Z - 8.5, "middle", "block"),
          (45.5, 48.5, Z - 20.5, "finish", "block")]
PLACED = {}

# the route, as the player rolls it (the sketch's centre line, not a demo)
ROUTE = [(5.5, 5.5), (6, 9), (6, 12.5), (9, 12), (12, 12.5), (12, 15), (12, 18), (14, 18), (20, 18),
         (21.5, 18), (20.4, 21), (20.4, 24.5), (20.4, 26.5), (21.5, 27.5), (21.5, 30.5), (25, 30.5), (29, 30.5),
         (32.5, 31.5), (32.5, 35), (32.5, 38.5), (35, 39), (38.5, 39), (39, 40), (39, 42), (39, 44),
         (40, 44.5), (43, 44.5), (48, 44.5), (48, 47), (48, 53)]
LABELS = [(6, 6, "A start"), (12, 12, "A hill"), (17, 18, "B ledge"), (21.5, 17, "C lip"),
          (21.5, 26, "T"), (24, 30.5, "D chute"), (32.5, 31.5, "K3 open"),
          (32.5, 35, "E steps"), (36, 39, "W walk"), (43, 44.5, "F leap"),
          (48, 52, "H goal")]

# --- drawing ----------------------------------------------------------------
SECCOL = {"A": (120, 200, 120), "B": (210, 190, 120), "C": (220, 150, 110), "T": (200, 200, 200),
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
        # the two faces the camera sees: the +y face (left) and the +x face (right)
        d.polygon([Q(x, y + 1, sw), Q(x + 1, y + 1, se), Q(x + 1, y + 1, ground), Q(x, y + 1, ground)],
                  fill=tuple(v // 2 for v in base))
        d.polygon([Q(x + 1, y, ne), Q(x + 1, y + 1, se), Q(x + 1, y + 1, ground), Q(x + 1, y, ground)],
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
    d.line([Q(x, y, zat(x, y) + 1) for x, y in ROUTE], fill=(255, 60, 60), width=2)
    for i, (x, y, z, name) in PLACED.items():
        cx, cy = Q(x, y, z + 2)
        d.rectangle([cx - 3, cy, cx + 3, cy + 40], fill=(120, 100, 80), outline=(70, 60, 50))
        d.ellipse([cx - 9, cy - 18, cx + 9, cy], fill=(0, 200, 220), outline=(255, 255, 255))
        d.text((cx - 12 - 6 * len(name), cy - 14), name, fill=(0, 255, 255))
        d.text((cx + 12, cy - 14), "void behind" if BACK[i] else "art behind", fill=(120, 120, 160))
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
# First Roll - the shipped course 1 in the making (docs/plans/bonanza-courses/FIRST-ROLL.md): tutorial 1,
# rubber, no families.  Roll, brake, ramps and a shaped chute; drops kill you, and you learn the timing.
# Built only by the BZROLL=1 knob for now (the pathway's pad 0), until it ships.  Written by
# docs/plans/bonanza-courses/first/sketch.py --bbc from the paper design while the LAYOUT moves (revision 4:
# the owner's first play); once it settles this file is the source and is edited by hand.
course ROLL "First Roll"
guide                     # a REAL course: held to the course guide's checkable rules (G1, G3, G9 - G12)
width 64
lock across               # SPEC.md 130.45: the camera held across - the whole course is one window wide
stop down                 # SPEC.md 130.45.4: the camera scrolls no further once the finish is in view
ball rubber
target 30                 # the design class (30, 60 or 90); the sheet aims at about 35 s
# the PLAYTEST's limit, given by hand: the autopilot cannot steer a chute yet (no `way` may sit on a FIELD
# cell), so its route stops at the chute's mouth and the tool's limit rule has no route to price.  The
# batched step replaces this with an AUTHOR script's run and the tool's own rule (the guide, section 3)
limit 60
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
    L.append("")
    for (x, y) in sorted(HOLES):
        L.append("hole  tile %d %d" % (x + OFF, y + OFF))
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
