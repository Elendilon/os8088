#!/usr/bin/env python3
"""bzwinart.py - Bounce Bonanza's WINDOW ART, drawn from code (SPEC.md 137.26.2).

The desktop window's two pictures, 1bpp, in the desktop's own bit order
(row-major, bit 7 leftmost, 1 = LIT - the window's white ground):

  * the TITLE: the in-game lettering (tools/bbtitle.py's strokes, bob and
    proportions - its LETTERS and WORD are imported, not copied) at about
    two thirds of its in-game size, re-rasterised at the desktop's
    resolution: a white core, a black keyline, a grey (checkered) rim where
    the game has magenta, and a solid shadow down and right where it has
    cyan;
  * the LEDGE: an isometric slab like a course's floor, running off to the
    right, with the rubber marble resting on it (tools/bonanza_assets.py's
    ball, its spots, rim, terminator and highlight, at 1.75x, the game's
    magenta a checker).

Each in two ASPECTS: SHORT for a 640 x 200 desktop (the CGA's, whose pixels
are the game's 320 x 200 pixels halved across) and TALL for a desktop whose
pixels are near square (VGA, EGA, and the Hercules, which takes it 30% tall
rather than 60% short).  The geometry is authored in GAME pixels and every
desktop pixel samples it at its centre, so the strokes are smooth at both.

ART IS SOURCE (CLAUDE.md, the waves' step 5): this program is the source and
`make` runs it into build/bonanza-art/bzwin.inc; nothing it writes is
committed and nothing random is in it.

    python3 tools/bzwinart.py -o build/bonanza-art     # bzwin.inc
    python3 tools/bzwinart.py --png F                  # a preview of all four
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbtitle                  # noqa: E402  (the lettering's strokes)

# ---------------------------------------------------------------------------
# the aspects: desktop pixels a GAME pixel, across and down
# ---------------------------------------------------------------------------
ASPECTS = (("S", 2.0, 1.0),     # SHORT: a 640 x 200 desktop
           ("T", 2.0, 2.0))     # TALL: VGA / EGA / Hercules

# THE TITLE, in game pixels
TSCALE = 0.62                   # of the in-game lettering
T_UNIT = bbtitle.UNIT * TSCALE
T_RAD = bbtitle.RAD * TSCALE
T_OUTL = max(0.9, bbtitle.OUTL * TSCALE)
T_RIM = max(0.9, bbtitle.RIM * TSCALE)
T_ADV = bbtitle.ADV * TSCALE
T_SPACE = bbtitle.SPACE * TSCALE
T_SHADOW = 1.5
T_BOB = [b * TSCALE for b in bbtitle.BOB]
T_PAD = 1.0

# THE LEDGE, in game pixels: a slab whose top is a parallelogram of iso
# tiles running to the right, its front face below it
L_W = 120                       # the art's width (game px)
L_TILE = 16                     # a tile's half-width (the game's 32 x 16 diamond)
L_TOPH = 20                     # the top face's depth
L_FACE = 10                     # the front face's height
L_X0 = 24                       # where the slab's front-left corner is
BALL_D = 24                     # the marble's diameter (the game's is 16)
BALL_X = 84                     # its centre, across
WHT, CHK, BLK, NONE = 0, 1, 2, None


def bayer4(x, y):
    m = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
    return (m[y & 3][x & 3] + 0.5) / 16.0


# ---------------------------------------------------------------------------
# the title
# ---------------------------------------------------------------------------
def _title_points():
    pts = []
    x = 0.0
    i = 0
    for ch in bbtitle.WORD:
        if ch == " ":
            x += T_SPACE
            continue
        ox, oy = x + 3.5 * TSCALE, T_BOB[i % len(T_BOB)]
        for st in bbtitle.LETTERS[ch]:
            for (u, v) in bbtitle._pts(st):
                pts.append((ox + u * T_UNIT, oy + v * T_UNIT))
        x += T_ADV
        i += 1
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    m = T_RAD + T_OUTL + T_RIM + T_PAD
    x0, y0 = min(xs) - m, min(ys) - m
    pts = [(px - x0, py - y0) for (px, py) in pts]
    gw = max(xs) - min(xs) + 2 * m + T_SHADOW
    gh = max(ys) - min(ys) + 2 * m + T_SHADOW
    return pts, gw, gh


def _near(pts, gx, gy, r):
    r2 = r * r
    for (px, py) in pts:
        dx, dy = gx - px, gy - py
        if dx * dx + dy * dy <= r2:
            return True
    return False


def title(sx, sy):
    pts, gw, gh = _title_points()
    w, h = int(math.ceil(gw * sx)), int(math.ceil(gh * sy))
    # bucket the points by game cell for speed
    cell = 4.0
    grid = {}
    for p in pts:
        grid.setdefault((int(p[0] // cell), int(p[1] // cell)), []).append(p)

    def near(gx, gy, r):
        cx, cy = int(gx // cell), int(gy // cell)
        k = int(r // cell) + 1
        for j in range(cy - k, cy + k + 1):
            for i in range(cx - k, cx + k + 1):
                if _near(grid.get((i, j), ()), gx, gy, r):
                    return True
        return False

    rows = []
    rcore, rline, rrim = T_RAD, T_RAD + T_OUTL, T_RAD + T_OUTL + T_RIM
    for y in range(h):
        row = []
        for x in range(w):
            gx, gy = (x + 0.5) / sx, (y + 0.5) / sy
            if near(gx, gy, rcore):
                c = WHT
            elif near(gx, gy, rline):
                c = BLK
            elif near(gx, gy, rrim):
                c = CHK
            elif near(gx - T_SHADOW, gy - T_SHADOW, rrim):
                c = BLK
            else:
                c = WHT
            row.append(c)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# the ledge and the marble
# ---------------------------------------------------------------------------
def _ball(gx, gy, cx, cy):
    """the rubber marble at (cx, cy), radius BALL_D / 2: WHT, CHK, BLK or NONE"""
    R = BALL_D / 2.0
    x, y = (gx - cx) / R, (gy - cy) / R
    rr = x * x + y * y
    if rr > 1.0:
        return NONE
    if rr > 0.86:
        return BLK
    L = (-0.45, -0.55, 0.70)
    n = math.sqrt(sum(c * c for c in L))
    L = tuple(c / n for c in L)
    z = math.sqrt(1.0 - rr)
    lam = x * L[0] + y * L[1] + z * L[2]
    rz = 2 * lam * z - L[2]
    # the spots: the ball's 8-periodic texture, scaled with it, phase fixed
    k = BALL_D / 16.0 * 8.0 / 8.0
    u = (R * math.asin(max(-1.0, min(1.0, x)))) / k
    v = (R * math.asin(max(-1.0, min(1.0, y)))) / k
    du, dv = (u % 8) - 3.5, (v % 8) - 3.5
    c = WHT if du * du + dv * dv < 5.0 else CHK
    if rz > 0.93:
        c = WHT
    if lam < 0.06:
        c = BLK
    elif lam < 0.30 and (lam - 0.06) / 0.24 < bayer4(int(gx * 2), int(gy * 2)):
        c = BLK
    return c


def ledge(sx, sy):
    """the slab: top face from (L_X0, top) rising to the right in the iso
    slope (1 down for 2 across, the game's), a front face under it"""
    top = 1 + BALL_D - 2 - 0.45 * L_TOPH   # room above the top face for the marble
    gh = top + L_TOPH + L_FACE + 1
    gw = L_W
    w, h = int(math.ceil(gw * sx)), int(math.ceil(gh * sy))
    # the slab's top face: the parallelogram with corners
    #   front-left  A = (L_X0, top + L_TOPH)          (its left end)
    #   back-left   B = (L_X0 - L_TOPH, top)          (up and LEFT: its left end
    #                                                  face shows under that edge)
    # and running to the right edge of the art, the front edge from A along
    # the +x direction, which in this view is flat (the ledge seen face on)
    ax, ay = L_X0, top + L_TOPH
    bcx = BALL_X
    bcy = top + L_TOPH * 0.45 - BALL_D / 2.0 + 2   # resting on the top face
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            gx, gy = (x + 0.5) / sx, (y + 0.5) / sy
            c = _ball(gx, gy, bcx, bcy)
            if c is not NONE:
                row.append(c)
                continue
            # the top face: between the back edge y = top and the front edge
            # y = ay, its left end the slanted edge x = ax + (ay - gy)
            left = ax - (ay - gy)
            if top <= gy < ay and gx >= left:
                edge = gy < top + 1.0 / sy or gx < left + 1.2 / sx
                if edge:
                    row.append(BLK)
                    continue
                # the marble's shadow, an ellipse under it
                ex, ey = (gx - bcx - 3) / (BALL_D * 0.55), (gy - (bcy + BALL_D / 2.0)) / (BALL_D * 0.16)
                if ex * ex + ey * ey <= 1.0:
                    row.append(BLK if bayer4(x, y) < 0.75 else WHT)
                    continue
                # the tiles: iso seams every L_TILE along +x, and the courses'
                # light floor a sparse dither
                tu = (gx - left)
                seam = (tu % (2 * L_TILE)) < 1.0 / sx * 1.2
                if seam:
                    row.append(BLK)
                    continue
                row.append(BLK if bayer4(x, y) < 0.125 else WHT)
                continue
            # the front face, under the front edge
            if ay <= gy < ay + L_FACE and gx >= ax:
                if gy < ay + 1.0 / sy or gy >= ay + L_FACE - 1.0 / sy or gx < ax + 1.2 / sx:
                    row.append(BLK)
                    continue
                row.append(BLK if bayer4(x, y) < 0.5 else WHT)
                continue
            # the slab's left END face, a parallelogram left of the front face
            # (the -x side seen at the iso angle): from the slanted edge down
            if gx < ax and gy >= ay - (ax - gx) and gy < ay + L_FACE - (ax - gx) and gx >= ax - L_TOPH:
                le = gx > ax - L_TOPH + 1.2 / sx
                if not le or gy < ay - (ax - gx) + 1.0 / sy or gy >= ay + L_FACE - (ax - gx) - 1.0 / sy:
                    row.append(BLK)
                    continue
                row.append(BLK if bayer4(x, y) < 0.8 else WHT)
                continue
            row.append(WHT)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# 1bpp, the include, the preview
# ---------------------------------------------------------------------------
def mono(rows):
    """CHK becomes a checker in DESKTOP pixels; 1 = LIT (white: OSAPI_GFX_BLIT1's
    polarity on a 1bpp desktop, and its paper pen on a colour one)"""
    out = []
    for y, row in enumerate(rows):
        out.append([0 if (c == BLK or (c == CHK and (x + y) & 1)) else 1 for x, c in enumerate(row)])
    return out


def band(bits):
    h, w = len(bits), len(bits[0])
    stride = (w + 7) // 8
    data = bytearray()
    for row in bits:
        for b in range(stride):
            v = 0
            for k in range(8):
                x = 8 * b + k
                if x < w and row[x]:
                    v |= 128 >> k
            data.append(v)
    return w, h, stride, bytes(data)


def pictures():
    out = []
    for tag, sx, sy in ASPECTS:
        out.append(("BZW_TITLE_" + tag, mono(title(sx, sy))))
        out.append(("BZW_LEDGE_" + tag, mono(ledge(sx, sy))))
    return out


def emit(path):
    lines = ["; GENERATED by tools/bzwinart.py (SPEC.md 137.26.2) - edit that, not this.",
             "; Each picture: <NAME>_W, _H (pixels), _B (bytes a row), and its rows at <name>."]
    body = []
    for name, bits in pictures():
        w, h, stride, data = band(bits)
        lines += ["%s_W equ %d" % (name, w), "%s_H equ %d" % (name, h), "%s_B equ %d" % (name, stride)]
        body.append("%%macro %s_DATA 0" % name)
        for i in range(0, len(data), 16):
            body.append("    db " + ",".join("%d" % v for v in data[i:i + 16]))
        body.append("%endmacro")
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines + body) + "\n")


def preview(path):
    from PIL import Image
    pics = pictures()
    W = max(len(b[0]) for _, b in pics) + 8
    H = sum(len(b) + 8 for _, b in pics)
    im = Image.new("L", (W, H), 160)
    y = 0
    for _, bits in pics:
        for r, row in enumerate(bits):
            for x, v in enumerate(row):
                im.putpixel((x, y + r), 255 if v else 0)
        y += len(bits) + 8
    im.resize((2 * W, 2 * H), Image.NEAREST).save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", help="the directory bzwin.inc goes into")
    ap.add_argument("--png")
    a = ap.parse_args()
    if a.png:
        preview(a.png)
    if a.o:
        os.makedirs(a.o, exist_ok=True)
        emit(os.path.join(a.o, "bzwin.inc"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
