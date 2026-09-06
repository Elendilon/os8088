#!/usr/bin/env python3
"""CLEAR SKIES' title-screen art (SPEC.md 88.10): two 1bpp bands, generated.

    python3 tools/csart.py -o apps/skies/csart.inc [--preview DIR]

The launcher is a white page with the title lettered across the top and a
Cessna 172 in front of a cumulus on the right, and both are DRAWN HERE, as
vectors - the lettering as brush strokes (a black stroke and a narrower white
one over it, which is what makes a letter an outline with a white centre),
the aeroplane as filled polygons that hide the cloud behind them and the
lines that make it an aeroplane - and rasterised ONCE into the framebuffer's
own 1bpp bit order, so the window puts each up with a single OSAPI_GFX_BLIT1
(apps/os88api.inc) instead of the four hundred line calls the drawing would
be on an 8088, at SPEC.md 5.6's price each. A set bit is a LIT pixel there,
so the bands carry paper as 1 and ink as 0: right on a 1bpp adapter as they
are, and right on VGA under the blit's default pen.

The output is checked in and `tests/unit/t_csart.py` regenerates it and
compares, so the include cannot drift from this file. --preview writes the
two bands as PNGs, eight times up, for looking at.
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import shot                                     # noqa: E402  (the PNG writer)


class Canvas:
    """One byte a pixel while drawing: 1 = ink, 0 = paper."""

    def __init__(self, w, h):
        assert w % 8 == 0, "a band's width is a multiple of 8 (OSAPI_GFX_BLIT1)"
        self.w, self.h = w, h
        self.px = [bytearray(w) for _ in range(h)]

    def plot(self, x, y, ink=1):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = ink

    def disc(self, cx, cy, r, ink=1):
        r2 = r * r
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                    self.plot(x, y, ink)

    def line(self, x0, y0, x1, y1, ink=1):
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.plot(x0, y0, ink)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def polyline(self, pts, ink=1):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            self.line(x0, y0, x1, y1, ink)

    def stroke(self, pts, r, ink=1):
        """A round brush of radius r along the polyline, a step a pixel."""
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) * 2))
            for i in range(n + 1):
                t = i / n
                self.disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r, ink)

    def fill(self, pts, ink=1):
        """Scanline fill of a simple polygon (even-odd)."""
        ys = [p[1] for p in pts]
        for y in range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for a, b in zip(xs[0::2], xs[1::2]):
                for x in range(int(round(a)), int(round(b)) + 1):
                    self.plot(x, y, ink)

    def outline_of_mask(self, mask):
        """The boundary of a filled mask (another Canvas): a set pixel with an
        unset 4-neighbour, or on the edge."""
        for y in range(self.h):
            for x in range(self.w):
                if not mask.px[y][x]:
                    continue
                edge = False
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= self.w or ny >= self.h or not mask.px[ny][nx]:
                        edge = True
                        break
                if edge:
                    self.plot(x, y, 1)

    def band(self):
        """The 1bpp rows, bit 7 leftmost, in OSAPI_GFX_BLIT1's order: a SET
        bit is a LIT pixel. Ink is therefore CLEAR here and paper SET - on a
        1bpp adapter lit is white and the band goes up untranslated, and on
        VGA the blit's DEFAULT pen is white for set and black for clear, so no
        package sets a pen either way (apps/os88api.inc, OSAPI_GFX_BLIT1_PEN)."""
        out = []
        for row in self.px:
            b = bytearray(self.w // 8)
            for x, v in enumerate(row):
                if not v:
                    b[x >> 3] |= 0x80 >> (x & 7)
            out.append(bytes(b))
        return out

    def png(self, path, zoom=4):
        w, h = self.w * zoom, self.h * zoom
        pix = bytearray(w * h * 3)
        for y in range(h):
            row = self.px[y // zoom]
            for x in range(w):
                v = 0 if row[x // zoom] else 255
                i = (y * w + x) * 3
                pix[i] = pix[i + 1] = pix[i + 2] = v
        shot.png(path, w, h, bytes(pix))


def arc(cx, cy, rx, ry, a0, a1, n=None):
    """Points on an ellipse from angle a0 to a1 (degrees, y down: 0 = right,
    90 = down, 180 = left, 270 = up), either way round."""
    if n is None:
        n = max(6, int(abs(a1 - a0) / 6))
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def bezier(p0, p1, p2, p3, n=24):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0]
        y = u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]
        pts.append((x, y))
    return pts


# =============================================================================
# The aeroplane in front of its cloud: 152 x 96
# =============================================================================
ART_PLANE_W, ART_PLANE_H = 152, 96


def plane_art():
    c = Canvas(ART_PLANE_W, ART_PLANE_H)
    # --- the cumulus: a union of discs over a flat base, outlined ------------
    mask = Canvas(ART_PLANE_W, ART_PLANE_H)
    for cx, cy, r in ((34, 66, 19), (58, 50, 24), (90, 44, 29), (122, 56, 24), (138, 70, 15)):
        mask.disc(cx, cy, r)
    for y in range(83, ART_PLANE_H):                      # the flat bottom
        mask.px[y] = bytearray(ART_PLANE_W)
    c.outline_of_mask(mask)
    # --- the Cessna 172, side on, nose to the left ---------------------------
    body = [(12, 53), (18, 47), (30, 44), (46, 43), (54, 34), (82, 34), (92, 38),
            (118, 42), (140, 17), (147, 17), (150, 46), (150, 51), (130, 55),
            (100, 60), (64, 64), (42, 64), (24, 61), (13, 57)]
    wing = [(30, 29), (108, 29), (108, 33), (30, 33)]
    stab = [(124, 52), (150, 49), (150, 52), (128, 56)]
    spinner = [(7, 53), (13, 49), (13, 57)]
    prop = arc(11, 53, 2, 19, 0, 360)
    nosewheel = arc(31, 71, 4, 5, 0, 360)
    mainwheel = arc(76, 72, 5, 6, 0, 360)
    for poly in (body, wing, stab, spinner, prop, nosewheel, mainwheel):
        c.fill(poly, 0)                               # white: in front of the cloud
    for poly in (body, wing, stab, spinner, prop, nosewheel, mainwheel):
        c.polyline(poly + [poly[0]], 1)
    # the strut, the windows, the door, the gear legs, the rudder hinge
    c.line(58, 63, 48, 33)                            # the wing strut
    c.line(60, 63, 50, 33)
    c.polyline([(46, 43), (54, 35), (62, 35), (62, 43), (46, 43)])     # windscreen
    c.polyline([(64, 35), (78, 35), (78, 43), (64, 43), (64, 35)])     # the door's window
    c.polyline([(80, 35), (88, 36), (94, 41), (80, 43), (80, 35)])     # the rear window
    c.line(64, 44, 64, 62)                            # the door
    c.line(64, 62, 78, 62)
    c.line(30, 63, 31, 66)                            # the nose gear leg
    c.line(74, 64, 76, 66)                            # the main gear leg
    c.line(142, 20, 147, 44)                          # the rudder hinge
    c.line(118, 42, 148, 45)                          # the fuselage top under the fin
    return c


# =============================================================================
# The title: "Clear Skies" in an outlined italic script, 272 x 40
# =============================================================================
ART_TITLE_W, ART_TITLE_H = 272, 40
SHEAR = 0.28                                          # x per row above the baseline
BASE = 33                                             # the baseline row
CAP, XH = 30, 19                                      # cap height and x-height


def glyphs():
    """Each glyph: (advance, [strokes]), a stroke a list of points in a box
    whose baseline is y = 0 and whose top is y = -CAP (up is negative)."""
    g = {}
    g["C"] = (24, [arc(13, -15, 12, 15, 40, 320)])
    g["l"] = (11, [[(3, -CAP), (3, -6), (5, -1), (10, -2)]])
    g["e"] = (19, [[(2, -10), (16, -10)] + arc(9, -10, 7.5, 9.5, 0, -250)])
    g["a"] = (20, [arc(9, -9.5, 7.5, 9.5, 0, 360), [(17, -XH), (17, -3), (20, -1)]])
    g["r"] = (14, [[(3, -XH), (3, 0)], [(3, -12)] + arc(9, -12, 6, 7, 180, 300)])
    g["S"] = (22, [arc(12, -22, 9, 8, 340, 90) + arc(12, -8, 10, 8, 270, 510)])
    g["k"] = (18, [[(3, -CAP), (3, 0)], [(3, -8), (7, -10), (14, -XH)], [(7, -11), (16, 0)]])
    g["i"] = (9, [[(3, -XH), (3, -3), (5, -1), (8, -2)], arc(3, -25, 1.6, 1.6, 0, 360)])
    g["s"] = (17, [arc(9, -14, 6.5, 5, 340, 90) + arc(9, -5, 7, 5, 270, 510)])
    g[" "] = (12, [])
    return g


def title_art():
    c = Canvas(ART_TITLE_W, ART_TITLE_H)
    g = glyphs()
    text = "Clear Skies"
    x = 6
    strokes = []
    for ch in text:
        adv, sts = g[ch]
        for st in sts:
            strokes.append([(x + px + SHEAR * (-py), BASE + py) for px, py in st])
        x += adv
    for st in strokes:                                # the black body...
        c.stroke(st, 2.6, 1)
    for st in strokes:                                # ...and the white centre
        c.stroke(st, 1.3, 0)
    return c


def emit(path, bands):
    lines = ["; CLEAR SKIES' title-screen art (SPEC.md 88.10): GENERATED by",
             "; tools/csart.py - do not edit by hand; tests/unit/t_csart.py holds",
             "; this file to the generator. Each band is OSAPI_GFX_BLIT1's own",
             "; order: row-major, bit 7 leftmost, a set bit LIT - so ink is a",
             "; clear bit and paper a set one, on every adapter, with no pen.", ""]
    for name, canvas in bands:
        lines.append("%s_w equ %d" % (name, canvas.w))
        lines.append("%s_h equ %d" % (name, canvas.h))
        lines.append("%s:" % name)
        for row in canvas.band():
            lines.append("    db " + ", ".join("0x%02X" % b for b in row))
        lines.append("")
    open(path, "w").write("\n".join(lines))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "apps", "skies", "csart.inc"))
    ap.add_argument("--preview", help="write PNG previews into this directory")
    ap.add_argument("--zoom", type=int, default=4)
    a = ap.parse_args(argv)
    bands = [("cs_art_title", title_art()), ("cs_art_plane", plane_art())]
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        for name, canvas in bands:
            canvas.png(os.path.join(a.preview, name + ".png"), a.zoom)
    emit(a.out, bands)
    print("csart: %s (%s)" % (a.out, ", ".join("%s %dx%d" % (n, c.w, c.h) for n, c in bands)))


if __name__ == "__main__":
    main(sys.argv[1:])
