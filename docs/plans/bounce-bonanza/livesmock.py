import sys, os, math
sys.path.insert(0, "tools")
import bbcourse as B
import bonanza_assets as BA
from PIL import Image, ImageDraw
BLK, CYN, MAG, WHT = B.BLK, B.CYN, B.MAG, B.WHT
OUT = sys.argv[1]
ORIG_FACE = B.clock_face_pix
B.clock_face_pix = lambda *a, **k: {}
c = B.compile_course("apps/bonanza/courses/path.bbc")
x0, y0 = c.x0, c.y0
AT = (29, 22)
N = 3

def base_p():
    return {"at": AT, "z4": 0, "ndig": 1, "place": 0}

def tile_c():
    wx, wy = AT
    return 16 * (wx - wy) + x0, 8 * (wx + wy) + 8 + y0

BB = B

def caption(text, cx, ytop, ink=WHT):
    w = 8 * len(text)
    return B.text_pixels(text, cx - w // 2, ytop, ink)

def outline_text(text, cx, ytop):
    """white text with a 1px black keyline (the title lettering's trick, small)"""
    t = caption(text, cx, ytop)
    out = {}
    for (x, y) in t:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                out[(x + dx, y + dy)] = BLK
    out.update(t)
    return out

def marble(cx, cy, r=4.6, body=MAG):
    """a small marble: black rim, body, a white rim of light upper left and a glint"""
    out = {}
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            ux, uy = (x + 0.5 - cx) / r, (y + 0.5 - cy) / r
            d = ux * ux + uy * uy
            if d > 1.0:
                continue
            if d > 0.62:
                ink = BLK
            elif ux + uy < -0.55 and d > 0.18:
                ink = WHT
            elif ux + uy > 0.5:
                ink = MAG if (x + y) & 1 else (body if body != WHT else CYN)
            else:
                ink = body
            out[(x, y)] = ink
    gx, gy = int(cx - 0.35 * r), int(cy - 0.4 * r)
    out[(gx, gy)] = WHT
    return out

def opt_current():
    p = dict(base_p())
    out = ORIG_FACE(p, x0, y0)
    bx, by = BB.clock_digit_block(p, x0, y0)
    out.update(BB.clock_glyph(N, bx, by))
    return out

def opt_caption():
    """the crystal ball kept, LIVES beside it at the ball's height, and the digit WHITE in a BLACK window
    (black on cyan is a checker under a black digit on the Hercules)"""
    p = dict(base_p())
    out = ORIG_FACE(p, x0, y0)
    cx, cy, fx, fy, rx, ry = BB.clock_face_geom(p, x0, y0)
    bx, by = BB.clock_digit_block(p, x0, y0)
    for y in range(8 * by - 1, 8 * by + 8):
        for x in range(8 * bx - 1, 8 * bx + 7):
            if out.get((x, y)) is not None:
                out[(x, y)] = BLK
    for (x, y), v in BB.clock_glyph(N, bx, by).items():
        out[(x, y)] = WHT
    out.update(B.text_pixels("LIVES", fx - rx - 4 - 40, fy - 4, WHT))
    return out

def plinth(cx, cy, pw=9, ph=4, pt=4):
    out = {}
    top_y = cy - ph
    for x in range(cx - pw, cx + pw + 1):
        half = pt * (pw - abs(x - cx)) / float(pw)
        y_lo, y_hi = top_y - half, top_y + half
        for y in range(int(math.floor(y_lo)), int(math.ceil(y_hi)) + 1):
            if y_lo - 0.5 <= y <= y_hi + 0.5:
                edge = y <= y_lo + 0.5 or y >= y_hi - 0.5
                out[(x, y)] = BLK if edge else WHT
        for y in range(int(math.ceil(y_hi)) + 1, int(math.ceil(y_hi)) + ph + 1):
            if x == cx - pw or x == cx + pw or y == int(math.ceil(y_hi)) + ph or x == cx:
                out[(x, y)] = BLK
            elif x < cx:
                out[(x, y)] = MAG
            else:
                out[(x, y)] = MAG if (x + y) & 1 else BLK
    return out, top_y

def shadow(cx, cy, w=10):
    out = {}
    for y in range(cy - 2, cy + 5):
        for x in range(cx - 6, cx + w + 4):
            e = ((x - cx - 4) / float(w)) ** 2 + ((y - cy - 1) / 3.6) ** 2
            if e <= 1.0 and (x + y) & 1:
                out[(x, y)] = BLK
    return out

def opt_plaque():
    """a signboard on two posts: the title's plaque (black, magenta keyline, white letters)"""
    cx, cy = tile_c()
    out = shadow(cx, cy, 14)
    bw, bh = 48, 28
    bx0 = cx - bw // 2
    by0 = cy - 16 - bh
    for px in (cx - 9, cx + 8):                  # the posts, standing on the tile
        for y in range(by0 + bh, cy + 1):
            out[(px - 1, y)] = BLK; out[(px, y)] = WHT; out[(px + 1, y)] = MAG; out[(px + 2, y)] = BLK
    for y in range(by0, by0 + bh):
        for x in range(bx0, bx0 + bw):
            e = x in (bx0, bx0 + bw - 1) or y in (by0, by0 + bh - 1)
            k = x in (bx0 + 2, bx0 + bw - 3) or y in (by0 + 2, by0 + bh - 3)
            inner = bx0 + 2 <= x <= bx0 + bw - 3 and by0 + 2 <= y <= by0 + bh - 3
            out[(x, y)] = WHT if e else (MAG if k and inner else BLK)
    out.update(caption("LIVES", bx0 + bw // 2, by0 + 5))
    out.update(caption(str(N), bx0 + bw // 2, by0 + 16))
    return out

def opt_marblex():
    """the arcade convention: your marble, x N, a caption above"""
    cx, cy = tile_c()
    out = shadow(cx - 4, cy, 12)
    pl, top_y = plinth(cx - 8, cy)
    out.update(pl)
    out.update(marble(cx - 8 + 0.5, top_y - 5.5, 6.2))
    out.update(caption("x" + str(N), cx + 10, top_y - 12))
    out.update(caption("LIVES", cx, top_y - 30))
    return out

def opt_rack():
    """the lives AS marbles: N of 5 resting on the crystal tile, a 3 + 2 pile, a caption above"""
    cx, cy = tile_c()
    out = {}
    spots = [(cx - 9, cy - 1), (cx, cy - 1), (cx + 9, cy - 1), (cx - 4.5, cy + 3), (cx + 4.5, cy + 3)]
    for k, (mx, my) in enumerate(spots[:N]):
        out.update(marble(mx + 0.5, my - 4.0, 4.7, body=WHT))
    out.update(caption("LIVES", cx, cy - 26))
    return out

def opt_ball_caption():
    """A with the digit WHITE on black inside a darkened window, so it reads like the caption"""
    return opt_caption()

OPTS = [("current (no caption)", opt_current), ("A  caption", opt_caption), ("B  plaque", opt_plaque),
        ("C  marble x N", opt_marblex), ("D  marbles on the tile", opt_rack)]

def picture(extra):
    rows = [list(r) for r in c.pic]
    for (x, y), v in extra.items():
        if 0 <= y < len(rows) and 0 <= x < len(rows[0]):
            rows[y][x] = v
    return rows

def cga(rows):
    im = Image.new("RGB", (len(rows[0]), len(rows)))
    im.putdata([B.CGA1[v] for r in rows for v in r])
    return im

def herc(rows):
    im = Image.new("L", (2 * len(rows[0]), len(rows)))
    data = []
    for y, r in enumerate(rows):
        for x, v in enumerate(r):
            pr = B.herc_pair(v, y, x)
            data += [255 * (pr >> 1), 255 * (pr & 1)]
    im.putdata(data)
    return im.convert("RGB")

cx, cy = tile_c()
X0, X1, Y0, Y1 = cx - 70, cx + 50, cy - 100, cy + 14
Z = 4
tiles = []
for name, f in OPTS:
    rows = picture(f())
    a = cga(rows).crop((X0, Y0, X1, Y1)).resize(((X1 - X0) * Z, (Y1 - Y0) * Z), Image.NEAREST)
    h = herc(rows).crop((2 * X0, Y0, 2 * X1, Y1)).resize(((X1 - X0) * Z, (Y1 - Y0) * Z), Image.NEAREST)
    tiles.append((name, a, h))
    full = cga(rows)
    full.save("%s/full_%s.png" % (OUT, name.split()[0]))
W, H = tiles[0][1].size
sheet = Image.new("RGB", (2 * W + 30, len(tiles) * (H + 26)), (70, 70, 70))
d = ImageDraw.Draw(sheet)
for i, (name, a, h) in enumerate(tiles):
    y = i * (H + 26)
    d.text((8, y + 6), name + "   (left CGA, right Hercules)", fill=(255, 255, 0))
    sheet.paste(a, (10, y + 22)); sheet.paste(h, (W + 20, y + 22))
sheet.save(OUT + "/lives-options.png")
print(sheet.size)
