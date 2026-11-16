#!/usr/bin/env python3
"""bbtitle.py - Bounce Bonanza's TITLE ART, drawn from code (SPEC.md 128.23.2).

Writes apps/bonanza/courses/title.bba, the text pixmap `art title.bba 0 0`
paints over the title course's CGA window: the lettering - BOUNCE BONANZA in
fat rounded strokes, each letter bobbing on its own baseline as if it had
just bounced - and the KEY HINTS on a plaque in the sky's left pocket, in the
tree's own 8 x 8 face (fonts/tallx.f8), the slot's digit left out for the
course's label lane (`label 0 ...`) to draw.

ART IS SOURCE (CLAUDE.md, the waves' step 5): this program is the source,
the .bba is its output, both committed; `make` reads only the .bba, and
`--check` says whether the .bba is still this program's. No image service,
no font file outside the tree, nothing random: the output is a function of
this text.

    python3 tools/bbtitle.py            # write the .bba
    python3 tools/bbtitle.py --check    # exit 1 if it would change
    python3 tools/bbtitle.py --png F    # a preview (needs Pillow), 3x, CGA colours
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "apps", "bonanza", "courses", "title.bba")
sys.path.insert(0, HERE)
import os88font                 # noqa: E402

W, H = 320, 112                 # the art's box: the CGA window's top 112 lines
BLK, CYN, MAG, WHT = 0, 1, 2, 3

# THE LETTERS, as strokes in a 10 x 14 cell (x right, y down): polylines, and
# arcs ("arc", cx, cy, rx, ry, a0, a1) in degrees, 0 = +x, clockwise on screen
LETTERS = {
    "B": [[(1, 14), (1, 0)], [(1, 0), (5, 0)], ("arc", 5, 3.5, 3.5, 3.5, -90, 90), [(5, 7), (1, 7)],
          [(1, 7), (5.5, 7)], ("arc", 5.5, 10.5, 3.5, 3.5, -90, 90), [(5.5, 14), (1, 14)]],
    "O": [("arc", 5, 7, 4, 7, 0, 360)],
    "U": [[(1, 0), (1, 9)], ("arc", 5, 9, 4, 5, 180, 0, -1), [(9, 9), (9, 0)]],
    "N": [[(1, 14), (1, 0), (9, 14), (9, 0)]],
    "C": [("arc", 5.5, 7, 4.5, 7, 40, 320)],
    "E": [[(9, 0), (1, 0), (1, 14), (9, 14)], [(1, 7), (7, 7)]],
    "A": [[(0.5, 14), (5, 0), (9.5, 14)], [(2.5, 9), (7.5, 9)]],
    "Z": [[(1, 0), (9, 0), (1, 14), (9, 14)]],
}
WORD = "BOUNCE BONANZA"
UNIT = 1.45                     # px a cell unit (a letter 14.5 x 20 px of skeleton)
RAD = 2.6                       # the stroke's radius, px: fat, rounded
OUTL = 1.6                      # the black keyline round the white, px
RIM = 1.6                       # the magenta rim round that, px
ADV = 21                        # px a letter (its skeleton 14.5 wide plus the strokes)
SPACE = 10                      # the gap between the words, px
TOP = 16                        # px: the letters' cell top, before the bob (the owner, 2026-11-16: lower, clear of the top)
SHADOW = 2                      # the cyan shadow's offset, px
BOB = (0, -3, -5, -3, 1, -2, 0, -4, -6, -4, -1, -3, 0)   # each letter's bounce, px (a bit of a wave)

# THE KEY HINTS: a plaque in the sky's left pocket (cells of the window), its
# text in the tree's 8 x 8 face; the SLOT's digit is the course's label 0,
# drawn by its lane (title.bbc's `label 0 LABEL_COL LABEL_ROW`)
PLAQUE = (1, 6, 12, 10)         # cols 1 - 11, rows 6 - 9 (x 8 - 95, y 48 - 79)
HINTS = ((7, "P  PLAY"), (8, "S  SLOT"))
LABEL_COL, LABEL_ROW = 10, 8    # the slot's digit: "S  SLOT " then the label


def _pts(stroke):
    """a stroke's skeleton as points about half a unit apart"""
    if stroke[0] == "arc":
        cx, cy, rx, ry, a0, a1 = stroke[1:7]
        d = stroke[7] if len(stroke) > 7 else 1
        span = (a1 - a0) % 360 or 360
        if d < 0:
            span = (a0 - a1) % 360 or 360
        n = max(8, int(span / 4))
        out = []
        for i in range(n + 1):
            a = math.radians(a0 + d * span * i / n)
            out.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        return out
    out = []
    for (x0, y0), (x1, y1) in zip(stroke, stroke[1:]):
        n = max(2, int(2 * math.hypot(x1 - x0, y1 - y0)))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n + 1)]
    return out


def _disc(mask, cx, cy, r):
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            if 0 <= x < W and 0 <= y < H and (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                mask.add((x, y))


def lettering():
    """{(x, y): ink}: the word's white strokes, a black keyline, a magenta rim
    and, under them, a cyan shadow SHADOW px down and right"""
    core, line, rim = set(), set(), set()
    x = (W - (len(WORD.replace(" ", "")) * ADV + SPACE)) // 2
    i = 0
    for ch in WORD:
        if ch == " ":
            x += SPACE
            continue
        ox, oy = x + 3.5, TOP + BOB[i % len(BOB)]
        for st in LETTERS[ch]:
            for (u, v) in _pts(st):
                px, py = ox + u * UNIT, oy + v * UNIT
                _disc(core, px, py, RAD)
                _disc(line, px, py, RAD + OUTL)
                _disc(rim, px, py, RAD + OUTL + RIM)
        x += ADV
        i += 1
    out = {}
    for (x, y) in rim:
        if x + SHADOW < W and y + SHADOW < H:
            out[(x + SHADOW, y + SHADOW)] = CYN
    for p in rim:
        out[p] = MAG
    for p in line:
        out[p] = BLK
    for p in core:
        out[p] = WHT
    return out


def hints():
    """{(x, y): ink}: the plaque (black, a magenta rule) and its white text"""
    g = os88font.parse(os.path.join(ROOT, "fonts", "tallx.f8"))
    c0, r0, c1, r1 = PLAQUE
    out = {}
    for y in range(8 * r0, 8 * r1):
        for x in range(8 * c0, 8 * c1):
            edge = y in (8 * r0, 8 * r1 - 1) or x in (8 * c0, 8 * c1 - 1)
            out[(x, y)] = MAG if edge else BLK
    for row, text in HINTS:
        for k, ch in enumerate(text):
            col = c0 + 1 + k
            for r, bits in enumerate(g[ord(ch)]):
                for b in range(8):
                    if bits & (128 >> b):
                        out[(8 * col + b, 8 * row + r)] = WHT
    return out


def pixmap():
    px = lettering()
    px.update(hints())
    return px


def bba_text(px):
    rows = ["# Bounce Bonanza's TITLE ART (SPEC.md 128.23.2): GENERATED by tools/bbtitle.py - edit that,",
            "# not this. %d x %d, the CGA window's top-left; '.' transparent, 0 - 3 the CGA's colours." % (W, H)]
    for y in range(H):
        rows.append("".join(str(px[(x, y)]) if (x, y) in px else "." for x in range(W)))
    return "\n".join(rows) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--png")
    a = ap.parse_args()
    text = bba_text(pixmap())
    if a.png:
        from PIL import Image
        pal = {".": (0, 0, 0), "0": (0, 0, 0), "1": (85, 255, 255), "2": (255, 85, 255), "3": (255, 255, 255)}
        rows = [r for r in text.split("\n") if r and not r.startswith("#")]
        im = Image.new("RGB", (W, H))
        im.putdata([pal[ch] for r in rows for ch in r])
        im.resize((3 * W, 3 * H), Image.NEAREST).save(a.png)
    if a.check:
        with open(OUT) as f:
            if f.read() != text:
                print("bbtitle: %s is not this program's output: run python3 tools/bbtitle.py"
                      % os.path.relpath(OUT, ROOT), file=sys.stderr)
                return 1
        return 0
    if not a.png:
        with open(OUT, "w", newline="\n") as f:
            f.write(text)
        print("bbtitle: wrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
