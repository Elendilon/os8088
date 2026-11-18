#!/usr/bin/env python3
"""FIRST ROLL, attempt 1: the PAPER sketch (wave 11's pipeline, the pen-in
step).  Host-only, nothing in `make` runs it and it ships nothing.  It is
NOT a .bbc: tiles are tiles, heights are units (8 px), and the pictures are
the game's projection (px = 16 (wx - wy), line = 8 (wx + wy) - 8 z) drawn as
plain blocks, to argue the layout with the owner before anything goes into
the engine.  python3 sketch.py [outdir] -> plan.png, iso.png"""
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


def floor(sec, x0, y0, x1, y1, z):
    for x in range(x0, x1):
        for y in range(y0, y1):
            CELLS[(x, y)] = (z, z, z, z)
            SECTION[(x, y)] = sec


def ramp(sec, axis, x0, y0, x1, y1, z0, z1):
    n = (x1 - x0) if axis == "x" else (y1 - y0)
    for x in range(x0, x1):
        for y in range(y0, y1):
            i = (x - x0) if axis == "x" else (y - y0)
            a, b = z0 + (z1 - z0) * i / n, z0 + (z1 - z0) * (i + 1) / n
            # corners: (x, y) (x+1, y) (x+1, y+1) (x, y+1)
            CELLS[(x, y)] = (a, b, b, a) if axis == "x" else (a, a, b, b)
            SECTION[(x, y)] = sec


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
rail(19, 20, 19, 25); rail(19, 25, 24, 25)
HOLES |= {(21, 22)}
# D  three corners, each less forgiving: the first railed, the second half
#    railed, the third open.  Gentle ramps on the legs
ramp("D", "x", 24, 21, 27, 24, Z - 10, Z - 11)               # D1 leg
rail(24, 21, 27, 21); rail(24, 24, 27, 24)
floor("D", 27, 21, 30, 24, Z - 11)                           # K1, railed
rail(27, 21, 30, 21); rail(30, 21, 30, 24)
ramp("D", "y", 27, 24, 30, 27, Z - 11, Z - 12)               # D2 leg
rail(27, 24, 27, 27); rail(30, 24, 30, 27)
floor("D", 27, 27, 30, 30, Z - 12)                           # K2, half railed
rail(27, 27, 27, 30); rail(27, 30, 28, 30)
ramp("D", "x", 30, 27, 33, 30, Z - 12, Z - 13)               # D3 leg
rail(30, 27, 33, 27); rail(30, 30, 33, 30)
floor("D", 33, 27, 36, 30, Z - 13)                           # K3, open
rail(33, 27, 36, 27)
# E  the steps: one unit each, down onto floor (a drop onto floor is fine)
floor("E", 33, 30, 36, 32, Z - 14)
floor("E", 33, 32, 36, 34, Z - 15)
floor("E", 33, 34, 36, 37, Z - 16)
for y0, y1 in ((30, 32), (32, 34), (34, 37)):
    rail(33, y0, 33, y1); rail(36, y0, 36, y1)
rail(33, 37, 34, 37)
# W  the walk: two tiles wide, BOTH edges open, an easy bend - steering
#    practice with the drop on either side, between the corners and the leap
ramp("W", "y", 34, 37, 36, 42, Z - 16, Z - 17)
floor("W", 34, 42, 37, 44, Z - 17)
rail(34, 44, 37, 44)
ramp("W", "x", 37, 42, 41, 44, Z - 17, Z - 18)
# F  the leap: a railed run-up along +x, a ramp, a ONE-tile void gap, a
#    landing two units under the lip (too slow and the ball drops in the gap)
ramp("F", "x", 41, 42, 45, 45, Z - 18, Z - 20)
rail(41, 42, 45, 42); rail(41, 45, 45, 45); rail(41, 44, 41, 45)
floor("G", 46, 41, 50, 46, Z - 22)                           # G1, flag 1
rail(46, 41, 50, 41); rail(50, 41, 50, 46)
# H  the finish: a short ramp down and a wide goal plateau, all in view
ramp("G", "y", 46, 46, 50, 48, Z - 22, Z - 23)
rail(46, 46, 46, 48); rail(50, 46, 50, 48)
floor("H", 45, 48, 51, 53, Z - 23)
rail(45, 48, 45, 53); rail(45, 53, 51, 53); rail(51, 48, 51, 53)
GOAL = {(x, y) for x in range(45, 51) for y in range(51, 53)}

START = (5.5, 5.5)
FLAGS = [(22.5, 24.0, "flag 0"), (48.5, 44.5, "flag 1")]
# clocks: (wx, wy, z of the face's foot, frame)
CLOCKS = [(2.5, 8.5, Z, "pillar"), (31.5, 24.5, Z - 9, "pillar"), (52.5, 50.5, Z - 21, "pillar")]
for x, y, z, _ in CLOCKS:
    WALLS.append((int(x), int(y), int(x) + 1, int(y) + 1, z - 2))

# the route, as the player rolls it (the sketch's centre line, not a demo)
ROUTE = [(5.5, 5.5), (6, 9), (6, 12.5), (9, 12), (12, 12.5), (12, 15), (12, 17),
         (13.5, 17), (17, 17), (21.5, 16), (21.5, 19), (21.5, 20.5), (22.6, 23.5),
         (24, 22.5), (27, 22.5), (28.5, 23), (28.5, 26), (28.5, 28.5), (31, 28.5),
         (34.5, 28.5), (34.5, 31), (35, 36), (35, 40), (35.5, 43), (38, 43),
         (41, 43.5), (45.5, 43.5), (47.5, 44), (48, 46), (48, 52)]
LABELS = [(6, 6, "A start"), (12, 12, "A hill"), (17, 17, "B ledge"), (21.5, 16, "C lip"),
          (21.5, 23, "T"), (28.5, 22.5, "K1"), (28.5, 28.5, "K2"), (34.5, 28.5, "K3"),
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
        if c[0] != c[2] or c[1] != c[3]:
            d.text((x * S + 4, y * S + 3), "v" if c[3] < c[0] else ">", fill=(0, 0, 0))
    for x0, y0, x1, y1, z in WALLS:
        d.rectangle([x0 * S, y0 * S, x1 * S - 1, y1 * S - 1], fill=(90, 70, 70))
    for x0, y0, x1, y1 in RAILS:
        d.line([x0 * S, y0 * S, x1 * S, y1 * S], fill=(255, 220, 0), width=3)
    d.line([(x * S, y * S) for x, y in ROUTE], fill=(255, 60, 60), width=2)
    for x, y, z, f in CLOCKS:
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
    d.line([Q(x, y, zat(x, y) + 1) for x, y in ROUTE], fill=(255, 60, 60), width=2)
    for x, y, z, f in CLOCKS:
        cx, cy = Q(x, y, z + 2)
        d.ellipse([cx - 9, cy - 18, cx + 9, cy], fill=(0, 200, 220), outline=(255, 255, 255))
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
    rx = [Q(x, y, zat(x, y))[0] for x, y in ROUTE]
    mid = (min(rx) + max(rx)) // 2
    for i, (x, y) in enumerate((ROUTE[0], ROUTE[16], ROUTE[-1])):
        _, cy = Q(x, y, zat(x, y))
        d.rectangle([mid - 160, cy - 100, mid + 160, cy + 100], outline=(0, 255, 255))
    d.line([mid - 80, 0, mid - 80, H], fill=(70, 70, 120))
    d.line([mid + 80, 0, mid + 80, H], fill=(70, 70, 120))
    d.text((8, 8), "route px span %d (CGA dead zone 160); course %d lines tall; cyan boxes = one CGA "
           "window at the start, K2's clock and the goal" % (max(rx) - min(rx), H - 220), fill=(220, 220, 220))
    im.save(out)
    return max(rx) - min(rx), H


def route_len():
    L = 0
    for (a, b), (c, e) in zip(ROUTE, ROUTE[1:]):
        L += ((c - a) ** 2 + (e - b) ** 2) ** 0.5
    return L


if __name__ == "__main__":
    o = sys.argv[1] if len(sys.argv) > 1 else "."
    plan(o + "/plan.png")
    span, h = iso(o + "/iso.png")
    print("route %.1f tiles; px span %d; picture %d lines" % (route_len(), span, h))
