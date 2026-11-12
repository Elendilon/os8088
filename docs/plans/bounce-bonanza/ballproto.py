#!/usr/bin/env python3
"""BOUNCE BONANZA - host prototype of the rolling ball and the 4-colour look.

NOT a build input and not shipped: a picture to judge the plan by
(docs/plans/BOUNCE-BONANZA-PLAN.md, section 4). Run it with no arguments; it
writes PNG/GIF files next to itself.

The ball is the PHASE-TORUS trick: the visible face samples a texture that
is periodic in both axes (period P) through a fixed spherical lookup,
u = R*asin(x/R), v = R*asin(y/R). Rolling by (dx, dy) screen pixels adds
(dx, dy) to the phase, mod P - so P*P precomputed frames cover rolling in
EVERY direction, a change of direction is never a jump, and the guest does
no 3D maths at all: frame = phase_y * P + phase_x.
"""
import math, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
P = 8                 # texture period -> P*P = 64 frames
D = 16                # ball diameter in pixels
R = D / 2.0
# CGA palette 1, high intensity: black, light cyan, light magenta, white
CGA1 = [(0, 0, 0), (85, 255, 255), (255, 85, 255), (255, 255, 255)]
BLK, CYN, MAG, WHT = 0, 1, 2, 3
BAYER2 = [[0, 2], [3, 1]]
LIGHT = (-0.45, -0.55, 0.70)  # from upper left, toward the viewer
ln = math.sqrt(sum(c * c for c in LIGHT)); LIGHT = tuple(c / ln for c in LIGHT)


def tex(pattern, u, v):
    u %= P; v %= P
    if pattern == "checker":
        return (u < P / 2) ^ (v < P / 2)
    if pattern == "spots":       # one round spot a cell
        du, dv = u - P / 2 + 0.5, v - P / 2 + 0.5
        return du * du + dv * dv < 5.0
    if pattern == "band":        # two crossing stripes: a "seam" ball
        return (abs(u - P / 2) < 1.2) or (abs(v - P / 2) < 1.2)
    raise ValueError(pattern)


def ball_frame(pattern, fx, fy, base=MAG, ink=WHT):
    """One 16x16 frame: list of rows of colour indices, None = transparent."""
    rows = []
    for py in range(D):
        row = []
        for px in range(D):
            x = (px + 0.5 - R) / R
            y = (py + 0.5 - R) / R
            rr = x * x + y * y
            if rr > 1.0:
                row.append(None); continue
            if rr > 0.80:            # 1px dark rim: separates it from any floor
                row.append(BLK); continue
            z = math.sqrt(1.0 - rr)
            lam = x * LIGHT[0] + y * LIGHT[1] + z * LIGHT[2]
            # specular: reflect light about the normal, viewer is +z
            rz = 2 * lam * z - LIGHT[2]
            u = R * math.asin(max(-1, min(1, x))) + fx
            v = R * math.asin(max(-1, min(1, y))) + fy
            c = ink if tex(pattern, u, v) else base
            if rz > 0.93:
                c = WHT
            thr = (BAYER2[py & 1][px & 1] + 0.5) / 4.0
            if lam < 0.04 or (lam < 0.24 and (lam - 0.04) / 0.20 < thr):
                c = BLK              # the terminator, ordered-dithered
            row.append(c)
        rows.append(row)
    return rows


def paste(img, frame, ox, oy, pal=None):
    px = img.load()
    for y, row in enumerate(frame):
        for x, c in enumerate(row):
            if c is not None and 0 <= ox + x < img.width and 0 <= oy + y < img.height:
                px[ox + x, oy + y] = pal[c] if pal else c


def phase_sheet(pattern):
    """All P*P frames: the whole ball art for one texture."""
    gap = 4
    img = Image.new("RGB", (P * (D + gap) + gap, P * (D + gap) + gap), (40, 40, 40))
    for fy in range(P):
        for fx in range(P):
            paste(img, ball_frame(pattern, fx, fy), gap + fx * (D + gap), gap + fy * (D + gap), CGA1)
    return img.resize((img.width * 4, img.height * 4), Image.NEAREST)


# --- an isometric floor in four colours -------------------------------------
TW = 32               # a tile is a 32x16 diamond (2:1 isometric)


def iso(wx, wy, wz):
    """world (x right-down, y left-down, z up), in tile units -> screen px."""
    return (160 + (wx - wy) * TW / 2, 20 + (wx + wy) * TW / 4 - wz * 12)


def corner_h(cx, cy):
    """height at a tile CORNER, so a ramp is a real slope, not a stair."""
    if cy <= 3:
        return 2.0
    if cy <= 5:
        return 2.0 - (cy - 3) * 1.0      # two tiles of ramp
    return 0.0


def tile_ok(tx, ty):
    if tx < 0 or ty < 0 or tx > 7 or ty > 9:
        return False
    return (tx, ty) not in ((5, 7), (5, 8), (6, 7), (6, 8))   # a pit


def render_floor():
    from PIL import ImageDraw
    img = Image.new("P", (320, 200), BLK)
    img.putpalette(sum(CGA1, ()) + (0, 0, 0) * 252)
    d = ImageDraw.Draw(img)
    for s in range(0, 18):               # back to front
        for tx in range(0, 8):
            ty = s - tx
            if not tile_ok(tx, ty):
                continue
            h = [corner_h(tx, ty), corner_h(tx + 1, ty), corner_h(tx + 1, ty + 1), corner_h(tx, ty + 1)]
            a, b = iso(tx, ty, h[0]), iso(tx + 1, ty, h[1])
            c, e = iso(tx + 1, ty + 1, h[2]), iso(tx, ty + 1, h[3])
            # side faces down to z=-1 (only the two the camera sees)
            for (p, q, hp, hq, col) in ((e, c, h[3], h[2], MAG), (c, b, h[2], h[1], CYN)):
                q0 = (q[0], q[1] + (hq + 1) * 12); p0 = (p[0], p[1] + (hp + 1) * 12)
                d.polygon([p, q, q0, p0], fill=col, outline=BLK)
            top = WHT if (tx + ty) & 1 else CYN
            d.polygon([a, b, c, e], fill=top, outline=BLK)
    return img


def herc(img_rgb_idx):
    """Hercules pairs: each game pixel -> 2 card pixels, levels 0/1/2."""
    lv = {BLK: (0, 0), CYN: (1, 0), MAG: (1, 0), WHT: (1, 1)}
    w, h = img_rgb_idx.size
    out = Image.new("1", (w * 2, h))
    src, dst = img_rgb_idx.load(), out.load()
    for y in range(h):
        for x in range(w):
            a, b = lv[src[x, y]]
            if (x + y) & 1:
                a, b = b, a
            dst[2 * x, y], dst[2 * x + 1, y] = a * 255, b * 255
    return out


def roll_gif(pattern):
    floor = render_floor()
    frames, fx, fy = [], 0.0, 0.0
    prev = None
    for i in range(96):
        t = i / 96 * 2 * math.pi
        bx = 70 + 40 * math.sin(t)
        by = 118 + 14 * math.sin(2 * t)
        if prev:
            fx += bx - prev[0]; fy += by - prev[1]
        prev = (bx, by)
        f = floor.copy()
        # the shadow: a dithered ellipse, every other pixel black
        sp = f.load()
        for yy in range(-3, 4):
            for xx in range(-8, 9):
                if xx * xx / 64 + yy * yy / 9 <= 1 and (xx + yy) & 1:
                    X, Y = int(bx + 8 + xx), int(by + 15 + yy)
                    if 0 <= X < 320 and 0 <= Y < 200:
                        sp[X, Y] = BLK
        paste(f, ball_frame(pattern, int(fx) % P, int(fy) % P), int(bx), int(by))
        frames.append(f.convert("RGB").resize((640, 480), Image.NEAREST))
    frames[0].save(os.path.join(HERE, f"roll-{pattern}.gif"), save_all=True,
                   append_images=frames[1:], duration=33, loop=0)
    return floor


if __name__ == "__main__":
    for pat in ("checker", "spots", "band"):
        phase_sheet(pat).save(os.path.join(HERE, f"phases-{pat}.png"))
        roll_gif(pat)
    fl = render_floor()
    paste(fl, ball_frame("spots", 3, 5), 112, 112)
    fl.convert("RGB").resize((640, 480), Image.NEAREST).save(os.path.join(HERE, "mock-cga.png"))
    herc(fl).resize((720, 480), Image.NEAREST).save(os.path.join(HERE, "mock-herc.png"))
    print("wrote", sorted(f for f in os.listdir(HERE) if f.endswith((".png", ".gif"))))
