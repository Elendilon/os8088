"""The heights demo arena (WIREARENA-HEIGHTS-PLAN section 4), arenagen units
(64 a metre). Heights: units above the floor."""
from hmodel import Box, Arena
import itertools

def arena2(hb=384, room_h=192, steps=4, lift=160, plat=80, tower=160, jump=48, pillars=True, flight=False):
    B = []
    # --- WEST: the building - a loop corridor (2 m) round a core, two
    # entrances in its front wall, a back room with a jump platform
    for (x0, y0, x1, y1, n) in [
            (640, 512, 704, 640, "front S"), (640, 768, 704, 1280, "front mid"),
            (640, 1408, 704, 1536, "front N"),
            (256, 512, 640, 576, "south wall"), (256, 1472, 640, 1536, "north wall"),
            (384, 704, 512, 1344, "core"),
            (0, 512, 256, 704, "SW block"), (0, 1344, 256, 1536, "NW block"),
            (192, 704, 256, 960, "back wall S"), (192, 1088, 256, 1344, "back wall N")]:
        B.append(Box(x0, y0, x1, y1, hb, n))
    B.append(Box(0, 960, 128, 1088, jump, "jump platform"))
    # --- CENTRE: a 5 m platform, stairs (2 m wide) up its south and north sides
    B.append(Box(1088, 896, 1408, 1152, plat, "platform"))
    d = 128 // steps                    # the flight is 2 m long
    if flight:                          # one STAIR object a flight
        for (y0, y1) in ((768, 896), (1152, 1280)):
            b = Box(1184, y0, 1312, y1, plat // 2, "flight"); b.treads = steps; B.append(b)
        steps = 0
    for k in range(steps):
        h = plat * (k + 1) // (steps + 1)
        B.append(Box(1184, 896 - (steps - k) * d, 1312, 896 - (steps - k - 1) * d, h, "S step %d" % k))
        B.append(Box(1184, 1152 + (steps - k - 1) * d, 1312, 1152 + (steps - k) * d, h, "N step %d" % k))
    # --- EAST: the tower against the east wall, a lift each side of it
    B.append(Box(1856, 896, 2048, 1152, tower, "tower"))
    B.append(Box(1856, 640, 2048, 896, lift, "lift S"))
    B.append(Box(1856, 1152, 2048, 1408, lift, "lift N"))
    if pillars:
        B.append(Box(1472, 448, 1600, 576, hb, "pillar SE"))
        B.append(Box(1472, 1472, 1600, 1600, hb, "pillar NE"))
    return Arena(B, room_h, "heights")

def stats(ar):
    xs = sorted({v for b in ar.boxes for v in (b.x0, b.x1)} | {0, 2048})
    ys = sorted({v for b in ar.boxes for v in (b.y0, b.y1)} | {0, 2048})
    steps = {b - a for vals in (xs, ys) for a, b in zip(vals, vals[1:])}
    pts = set()
    for b in ar.boxes:
        pts |= {(b.x0, b.y0), (b.x1, b.y0), (b.x1, b.y1), (b.x0, b.y1)}
    return dict(boxes=len(ar.boxes), nodes=len(ar.nodes), xs=len(xs), ys=len(ys),
                steps=sorted(steps), verts=len(pts) + 4, heights=sorted({b.h for b in ar.boxes}))
if __name__ == "__main__":
    for st in (4, 2):
        print(st, stats(arena2(steps=st)))
