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


def rail(x0, y0, x1, y1):
    RAILS.append((x0, y0, x1, y1))


Z = 26                                   # the start's height, units
# A  the start and the hill of ramps: ramps alternate +y and +x, so the hill
#    runs DOWN the screen, and every throw lands on a flat that a rail closes
floor("A", 4, 4, 8, 8, Z)                                    # P0 the start
WALLS += [(3, 3, 8, 4, Z + 2), (3, 4, 4, 8, Z + 2)]
rail(8, 4, 8, 8)
ramp("A", "y", 4, 8, 8, 10, Z, Z - 2)                        # R1
rail(4, 8, 4, 10); rail(8, 8, 8, 10)
floor("A", 4, 10, 8, 14, Z - 2)                              # L1
rail(4, 10, 4, 14); rail(4, 14, 8, 14)
ramp("A", "x", 8, 10, 10, 14, Z - 2, Z - 4)                  # R2
rail(8, 10, 10, 10); rail(8, 14, 10, 14)
floor("A", 10, 10, 14, 14, Z - 4)                            # L2
rail(10, 10, 14, 10); rail(14, 10, 14, 14)
ramp("A", "y", 10, 14, 14, 16, Z - 4, Z - 6)                 # R3
rail(10, 14, 10, 16); rail(14, 14, 14, 16)
floor("A", 10, 16, 14, 20, Z - 6)                            # L3
rail(10, 16, 10, 20); rail(10, 20, 14, 20); rail(14, 18, 14, 20)
# B  the ledge: two tiles wide, its FRONT edge open to the void
floor("B", 14, 16, 20, 18, Z - 6)
WALLS += [(14, 15, 20, 16, Z - 4)]
# C  the lip: a run-up, a ramp, a 3-unit step down onto T, a hole where the
#    straight full-speed landing falls
floor("C", 20, 14, 23, 18, Z - 6)                            # M
WALLS += [(20, 13, 23, 14, Z - 4)]
rail(23, 14, 23, 18)
ramp("C", "y", 20, 18, 23, 20, Z - 6, Z - 7)                 # the lip ramp
rail(20, 18, 20, 20); rail(23, 18, 23, 20)
floor("T", 19, 20, 24, 25, Z - 10)                           # T, 3 units under the lip
rail(19, 20, 19, 25); rail(19, 25, 24, 25); rail(24, 20, 24, 21); rail(24, 23, 24, 25)
HOLES |= {(21, 22)}
# D  the CHUTE: a shaped, two-wide channel (`chute 2 round`, SPEC.md
#    130.28, like PLAYGROUND's), UNFENCED - its shape is the guide - from
#    T's exit along +x, round a corner down +y, round a corner along +x into
#    D3.  D3's rails come back up as it exits; K3's far end stays OPEN, so a
#    ball out of the chute at full speed can overshoot into the void
chute("D", [(24, 22, Z - 10), (28, 22, Z - 11), (28, 28, Z - 13), (31, 28, Z - 13)], 1.25)
ramp("D", "x", 31, 27, 33, 30, Z - 13, Z - 14)               # D3, railed
rail(31, 27, 33, 27); rail(31, 30, 33, 30); rail(31, 29, 31, 30)
floor("D", 33, 27, 36, 30, Z - 14)                           # K3, open
rail(33, 27, 36, 27)
# E  the steps: one unit each, down onto floor (a drop onto floor is fine)
floor("E", 33, 30, 36, 32, Z - 15)
floor("E", 33, 32, 36, 34, Z - 16)
floor("E", 33, 34, 36, 37, Z - 17)
for y0, y1 in ((30, 32), (32, 34), (34, 37)):
    rail(33, y0, 33, y1); rail(36, y0, 36, y1)
rail(33, 37, 34, 37)
# W  the walk: two tiles wide, BOTH edges open, an easy bend - steering
#    practice with the drop on either side, between the corners and the leap
ramp("W", "y", 34, 37, 36, 42, Z - 17, Z - 19.5)
floor("W", 34, 42, 37, 44, Z - 19.5)
rail(34, 44, 37, 44)
ramp("W", "x", 37, 42, 41, 44, Z - 19.5, Z - 21.5)
# F  the leap: a railed run-up along +x, a ramp, a ONE-tile void gap, a
#    landing two units under the lip (too slow and the ball drops in the gap)
ramp("F", "x", 41, 42, 45, 45, Z - 21.5, Z - 23.5)
rail(41, 42, 45, 42); rail(41, 45, 45, 45)    # no rail across F's entry: rails protect, never block
floor("G", 46, 41, 50, 46, Z - 25.5)                           # G1, flag 1
rail(46, 41, 50, 41); rail(50, 41, 50, 46)
# H  the finish: a short ramp down and a wide goal plateau, all in view
ramp("G", "y", 46, 46, 50, 48, Z - 25.5, Z - 26.5)
rail(46, 46, 46, 48); rail(50, 46, 50, 48)
floor("H", 45, 48, 51, 53, Z - 26.5)
rail(45, 48, 45, 53); rail(45, 53, 51, 53); rail(51, 48, 51, 53)
GOAL = {(x, y) for x in range(45, 51) for y in range(51, 53)}

START = (5.5, 5.5)
# a flag stands just BEFORE what can kill, so a fall never replays a long stretch
FLAGS = [(21.5, 16.0, "flag 0"), (34.5, 35.5, "flag 1")]
# clocks: (wx, wy, z of the face's foot, frame)
# every clock on a lone pillar, placed so that ONLY THE VOID is behind its
# head: a standard-part clock's art bakes in what is behind it (nothing is
# composited at load), so the void is the one backdrop every use shares.
# iso() checks it (BACKDROP) on the picture without the clocks
# Each is given the ROUTE point whose CGA window must show it and the height
# of its head; iso() places it at the nearest spot to that point that is
# inside the window and has only void behind the head, and prints where.
CLOCKS = [(0, Z, "start"), (15, Z - 9, "chute"), (-1, Z - 24.5, "finish")]
PLACED = {}

# the route, as the player rolls it (the sketch's centre line, not a demo)
ROUTE = [(5.5, 5.5), (6, 9), (6, 12.5), (9, 12), (12, 12.5), (12, 15), (12, 17),
         (13.5, 17), (17, 17), (21.5, 16), (21.5, 19), (21.5, 20.5), (22.6, 23.5),
         (23, 22.2), (25, 22), (27, 22.3), (27.8, 23.5), (28, 26), (28.4, 27.6), (30, 28), (32, 28.3),
         (34.5, 28.5), (34.5, 31), (35, 36), (35, 40), (35.5, 43), (38, 43),
         (41, 43.5), (44.5, 43.5), (47.5, 44), (48, 46), (48, 52)]
LABELS = [(6, 6, "A start"), (12, 12, "A hill"), (17, 17, "B ledge"), (21.5, 16, "C lip"),
          (21.5, 23, "T"), (26, 22, "D chute"), (34.5, 28.5, "K3 open"),
          (34.5, 33, "E steps"), (35, 40, "W walk"), (43, 43.5, "F leap"),
          (48, 51, "H goal")]

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
    for x0, y0, x1, y1 in RAILS:
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
    for x0, y0, x1, y1 in RAILS:
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
    for i, (k, z, name) in enumerate(CLOCKS):
        ax, ay = Q(*ROUTE[k], zat(*ROUTE[k]))
        best = None
        for cy in range(int(ay) - 92, int(ay) + 92, 2):
            for cx in range(mid - 150, mid + 151, 2):
                if any(bare.getpixel((px, py)) != (10, 10, 25)
                       for px in range(cx - 11, cx + 12, 2) for py in range(cy - 20, cy + 3, 2)):
                    continue
                u, v = (cy + miny + 8 * (z + 2)) / 8, (cx + minx) / 16
                wx, wy = (u + v) / 2, (u - v) / 2      # its pillar's cell and the 8 round it: no floor, no wall
                if any((int(wx) + a, int(wy) + b) in CELLS or (int(wx) + a, int(wy) + b) in WALLCELLS
                       for a in (-1, 0, 1) for b in (-1, 0, 1)):
                    continue
                dd = (cx - ax) ** 2 + (cy - ay) ** 2
                if best is None or dd < best[0]:
                    best = (dd, cx, cy)
        _, cx, cy = best
        px, py = cx + minx, cy + miny
        u, v = (py + 8 * (z + 2)) / 8, px / 16
        PLACED[i] = ((u + v) / 2, (u - v) / 2, z, name)
    d.line([Q(x, y, zat(x, y) + 1) for x, y in ROUTE], fill=(255, 60, 60), width=2)
    for i, (x, y, z, name) in PLACED.items():
        cx, cy = Q(x, y, z + 2)
        d.rectangle([cx - 3, cy, cx + 3, cy + 40], fill=(120, 100, 80), outline=(70, 60, 50))
        d.ellipse([cx - 9, cy - 18, cx + 9, cy], fill=(0, 200, 220), outline=(255, 255, 255))
        d.text((cx - 12 - 6 * len(name), cy - 14), name, fill=(0, 255, 255))
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

def bbc(out):
    if os.path.exists(out):                 # the .bbc is the source once written: hand edits are never lost
        sys.exit("sketch.py: %s exists - the course is edited by hand from here on; refusing to overwrite" % out)
    L = ['course ROLL "First Roll"', "width 64", "ball rubber", "target 30", ""]
    L.append("# rooms (the sketch's sections)")
    L += ROOMS_TXT
    L.append("")
    L.append("# the chute (SPEC.md 130.28): unfenced, its shape guides")
    L += CHUTE_TXT
    L.append("")
    L.append("# rails: block rails (wall tiles) on the void side of each railed edge")
    walls = {}
    for x0, y0, x1, y1 in RAILS:
        if y0 == y1:
            for x in range(min(x0, x1), max(x0, x1)):
                a, b = (x, y0 - 1), (x, y0)
                inner, outer = (a, b) if a in CELLS else (b, a)
                if inner in CELLS and outer not in CELLS:
                    walls[outer] = max(walls.get(outer, -99), max(CELLS[inner]) + 2)
        else:
            for y in range(min(y0, y1), max(y0, y1)):
                a, b = (x0 - 1, y), (x0, y)
                inner, outer = (a, b) if a in CELLS else (b, a)
                if inner in CELLS and outer not in CELLS:
                    walls[outer] = max(walls.get(outer, -99), max(CELLS[inner]) + 2)
    for x0, y0, x1, y1, z in WALLS:
        for x in range(x0, x1):
            for y in range(y0, y1):
                walls[(x, y)] = max(walls.get((x, y), -99), z)
    for (x, y), z in sorted(walls.items()):
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
    L.append("# clocks: each on a lone one-tile pillar, only void behind its head (the sketch's placement)")
    for x, y, z, name in PLACED.values():
        px, py = int(x) + OFF, int(y) + OFF
        L.append("floor tile %d %d  flat %g   # the %s clock's pillar" % (px, py, round((z - 4) * 2) / 2, name))
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
        print("%s clock: over the void at wx %.1f, wy %.1f, head at z %d (only void behind it)" % (name, x, y, z))
