#!/usr/bin/env python3
"""The ART kit courses 5 - 7 share (KITE, LODE, KEEP; 2026-11-25): what a course's `art.py` draws its signs, its
decals and its gates with.  Host only; nothing in `make` runs it.  A course's art.py is the artwork's SOURCE
(the `.bba` files under apps/bonanza/courses/ are its committed output, as roll_*.bba are first/decals.py's and
down_*.bba down/art.py's), and its sketch.py imports it for the `art` lines, so a re-emitted course keeps them.

  Sheet(x0, y0)      a canvas in the course's PICTURE pixels (SPEC.md 137.23.2's `art FILE X Y`: x0 the course's
                     `origin`, y0 the compile's Y0 - `check()` compiles the course and refuses a stale one)
    .tile(wx, wy, z)       a tile's top centre (z in units; 8 px a unit)
    .floor(wx, wy, z, fn)  PAINT on a tile's top: fn(u, v) -> ink or None, u and v 0 - 1 across the tile along
                           +x and +y; the tile's black outline is left alone
    .pat(rows, x, y)       a hand-drawn pattern (K black, W white, M magenta, C cyan, D the right faces'
                           dither, . nothing), its top-left at (x, y)
    .text(s, cx, y, ink)   the tool's 5 x 7 small caps, centred on cx
    .line(x0, y0, x1, y1, ink)
    .write(name, comment)  the opaque pixels' box as apps/bonanza/courses/<name>.bba -> its `art` line
  arrow, chevrons, up_arrow   floor paint for .floor(): fn(u, v) -> ink
  crop_png(c, boxes, out, pal, zoom)   crops of a compiled course, CGA over Hercules; picture_png: the whole of it
  gate_bba(name, frames, cells, comment)   a gate's ART (SPEC.md 137.41.12): four ELEVATIONS, {(u, v): ink} with
                     u across the opening and v up from the floor, sheared onto the wall's plane through the
                     cell's middle as the picture's own faces are, written with the header the tool reads; a
                     frame may be (elevation, flat): FLAT {((u, v), dx, dy): ink} is drawn UPRIGHT, dx and dy
                     screen px off the plane's point (u, v) - a plaque, which a shear would make unreadable

Inks are the CGA's by index: 0 black, 1 cyan, 2 magenta, 3 white (palette 1), or 1 green, 2 red, 3 yellow on
KITE's palette 0.  On the Hercules 1 and 2 are one grey checker: draw every form in 3 and 0 as well."""
import os
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(KIT, "..", "..", ".."))
COURSES = os.path.join(ROOT, "apps", "bonanza", "courses")
K, C, M, W = 0, 1, 2, 3
INK = {"K": K, "C": C, "M": M, "W": W}
PALS = {1: ((0, 0, 0), (85, 255, 255), (255, 85, 255), (255, 255, 255)),
        0: ((0, 0, 0), (85, 255, 85), (255, 85, 85), (255, 255, 85))}


def _caps():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from os88cdart import CAPS
    return CAPS


def arrow(u, v):
    """floor paint: an arrow on a tile's top pointing to u = 0 - black, a white line round it (so it stands on a
    white tile and a coloured one, and on the Hercules).  For the other three ways swap or flip u and v"""
    d = abs(v - 0.5)
    if 0.14 <= u <= 0.5:
        w = (u - 0.14) * 0.95
    elif 0.5 < u <= 0.86:
        w = 0.12
    else:
        return None
    if d <= w:
        return K
    if d <= w + 0.07 or (u <= 0.56 and d <= w + 0.1):
        return W
    return None


def chevrons(u, v):
    """floor paint: two chevrons pointing to u = 0 ("keep going"): black, a white line under each"""
    d = abs(v - 0.5)
    if d > 0.36:
        return None
    for c in (0.2, 0.52):
        t = u - c - 0.55 * d
        if 0.0 <= t < 0.12:
            return K
        if 0.12 <= t < 0.19:
            return W
    return None


def up_arrow(u, v):
    """floor paint: an arrow pointing UP THE SCREEN (to the tile's far corner, where u and v are both 0)"""
    a, b = (u + v) / 2.0, abs(u - v)
    if 0.16 <= a <= 0.5:
        w = (a - 0.16) * 1.5
    elif 0.5 < a <= 0.84:
        w = 0.14
    else:
        return None
    if b <= w:
        return K
    if b <= w + 0.1:
        return W
    return None


class Sheet(object):
    def __init__(self, x0, y0):
        self.x0, self.y0 = x0, y0
        self.pix = {}

    def tile(self, wx, wy, z):
        return 16 * (wx - wy) + self.x0, 8 * (wx + wy) + 8 - int(round(8 * z)) + self.y0

    def put(self, x, y, ink):
        self.pix[(int(x), int(y))] = ink

    def floor(self, wx, wy, z, fn, margin=0.07):
        cx, cy = self.tile(wx, wy, z)
        for y in range(cy - 8, cy + 8):
            for x in range(cx - 16, cx + 16):
                dx, dy = (x + 0.5 - cx) / 16.0, (y + 0.5 - cy) / 8.0
                u, v = (dx + dy) / 2.0 + 0.5, (dy - dx) / 2.0 + 0.5
                if margin <= u < 1.0 - margin and margin <= v < 1.0 - margin:
                    ink = fn(u, v)
                    if ink is not None:
                        self.pix[(x, y)] = ink

    def pat(self, rows, x, y, flip=False):
        w = max(len(r) for r in rows)
        for j, r in enumerate(rows):
            for i, ch in enumerate(r):
                if ch in ". ":
                    continue
                px = x + (w - 1 - i if flip else i)
                self.pix[(px, y + j)] = (M if (px + y + j) & 1 else K) if ch == "D" else INK[ch]

    def text(self, s, cx, y, ink=K):
        caps = _caps()
        x = cx - (6 * len(s) - 1) // 2
        for i, ch in enumerate(s):
            for r, row in enumerate(caps.get(ch, caps[" "])):
                for k, cc in enumerate(row):
                    if cc == "#":
                        self.pix[(x + 6 * i + k, y + r)] = ink

    def line(self, xa, ya, xb, yb, ink):
        n = max(abs(xb - xa), abs(yb - ya), 1)
        for k in range(n + 1):
            self.pix[(int(round(xa + (xb - xa) * k / float(n))), int(round(ya + (yb - ya) * k / float(n))))] = ink

    def outline(self, cells, ink=K):
        """a one-pixel line round CELLS (a set), on the pixels just outside it"""
        for (x, y) in cells:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) not in cells:
                    self.pix[(x + dx, y + dy)] = ink

    def write(self, name, comment):
        xs, ys = [x for x, _y in self.pix], [y for _x, y in self.pix]
        bx, by, w, h = min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        rows = ["".join("." if (bx + i, by + j) not in self.pix else str(self.pix[(bx + i, by + j)])
                        for i in range(w)) for j in range(h)]
        with open(os.path.join(COURSES, name + ".bba"), "w") as f:
            f.write("".join("# %s\n" % c for c in comment.split("\n")) + "\n".join(rows) + "\n")
        return "art %s.bba %d %d" % (name, bx, by)


def gate_bba(name, frames, cells, comment):
    """four elevations -> apps/bonanza/courses/gates/NAME.bba.  u = 0 is the plane's end at the first cell's
    upper right edge (`along x`; the tool mirrors it `along y`), u = 16 CELLS its far end; v = 0 the floor line"""
    placed = []
    for fr in frames:
        fr, flat = fr if isinstance(fr, tuple) else (fr, {})
        d = {}
        for (u, v), ink in fr.items():
            ax = 7 - u
            d[(ax, ((-ax) >> 1) - v)] = ink
        for ((u, v), dx, dy), ink in flat.items():   # UPRIGHT pieces (a plaque): hung at (u, v), not sheared
            ax = 7 - u
            d[(ax + dx, ((-ax) >> 1) - v + dy)] = ink
        placed.append(d)
    xs = [x for d in placed for x, _y in d]
    ys = [y for d in placed for _x, y in d]
    bx, by, w, h = min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    out = ["# %s" % c for c in comment.split("\n")]
    out += ["# frames 4", "# for gate", "# foot %d %d" % (-bx, -by), "# cells %d" % cells]
    for d in placed:
        out += ["".join("." if (bx + i, by + j) not in d else str(d[(bx + i, by + j)]) for i in range(w))
                for j in range(h)]
    with open(os.path.join(COURSES, "gates", name + ".bba"), "w") as f:
        f.write("\n".join(out) + "\n")
    return w, h


def check(course, x0, y0):
    """the compile's origin against the art's (a decal is placed in picture pixels: a stale Y0 moves them all)"""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import bbcourse as B
    c = B.compile_course(os.path.join(COURSES, course + ".bbc"))
    if (c.x0, c.y0) != (x0, y0):
        sys.exit("art.py: %s compiles at X0 %d, Y0 %d; the art was placed for %d, %d" % (course, c.x0, c.y0, x0, y0))
    return c


def crop_png(c, boxes, out, pal=1, zoom=3, cols=None):
    """crops of a compiled course's picture, CGA over Hercules, one a box (x, y, w, h) -> OUT.png"""
    import bbcourse as B
    from PIL import Image

    def one(x0, y0, w, h, card):
        def px(x, y):
            return c.pic[y][x] if 0 <= x < c.width and 0 <= y < c.lines else 0
        if card == "cga":
            im = Image.new("RGB", (w, h))
            im.putdata([PALS[pal][px(x, y)] for y in range(y0, y0 + h) for x in range(x0, x0 + w)])
        else:
            im = Image.new("L", (2 * w, h))
            im.putdata([255 * b for y in range(y0, y0 + h) for x in range(x0, x0 + w)
                        for pr in (B.herc_pair(px(x, y), y, x),) for b in (pr >> 1, pr & 1)])
            im = im.convert("RGB")
        return im.resize((w * zoom, h * zoom), Image.NEAREST)
    tiles = [(one(x, y, w, h, "cga"), one(x, y, w, h, "herc")) for (x, y, w, h) in boxes]
    W_ = sum(t[0].size[0] + 6 for t in tiles)
    H_ = max(t[0].size[1] for t in tiles)
    img = Image.new("RGB", (W_, 2 * H_ + 6), (70, 70, 70))
    x = 0
    for a, b in tiles:
        img.paste(a, (x, 0))
        img.paste(b, (x, H_ + 6))
        x += a.size[0] + 6
    img.save(out)
    return out


def picture_png(c, outdir, pal=1):
    """the compiled course's whole picture, one file a card: OUTDIR/picture-cga.png (in the course's palette)
    and picture-herc.png (the Hercules' 2 px a CGA pixel across, as the card shows it)"""
    import bbcourse as B
    from PIL import Image
    cga = Image.new("RGB", (c.width, c.lines))
    cga.putdata([PALS[pal][v] for r in c.pic for v in r])
    cga.save(os.path.join(outdir, "picture-cga.png"))
    herc = Image.new("L", (2 * c.width, c.lines))
    herc.putdata([255 * b for y, r in enumerate(c.pic) for x, v in enumerate(r)
                  for pr in (B.herc_pair(v, y, x),) for b in (pr >> 1, pr & 1)])
    herc.resize((2 * c.width, 2 * c.lines), Image.NEAREST).save(os.path.join(outdir, "picture-herc.png"))
    return [os.path.join(outdir, "picture-%s.png" % k) for k in ("cga", "herc")]
