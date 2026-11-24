#!/usr/bin/env python3
"""BOUNCE BONANZA's WALL CLOCK study (docs/plans/BOUNCE-BONANZA-WALLCLOCK.md): RESEARCH, host only, nothing in
`make` runs it and nothing it writes ships.

    python3 docs/plans/bonanza-courses/wallclock/wallclock.py

compiles the scratch course wall.bbc (three 2 x 2 blocks, 3, 2 and 1 units proud) and FIRST ROLL with the tool
as it is (tools/bbcourse.py, unchanged), then paints clock digits onto block FACES the way a lane's poses would
ink them, and for each variant:
  - checks the placement (every ink pixel, at every pose, on the host face's own visible pixels and clear of its
    edge lines and seams - so its occluder key is the face's whatever the pose, SPEC.md 130.12.4.5);
  - finds each digit place's LANE (the 8 x 8 blocks any pose inks: words x block rows) and whether two places
    share a block (a shared block's poses would be the PRODUCT of two digits', SPEC.md 130.18.5.5);
  - counts the NEW blocks the poses add to the picture's pool (CGA 16 bytes each; the Hercules and the VGA
    translate the same blocks at load, SPEC.md 130.11.3 / 130.46.5, so they store none), the static art's
    blocks (a plaque), and the lane records and pose maps (130.12.3.1: 32 bytes a record, poses x h x w words);
  - draws the crop on the CGA (palette 1), the Hercules (herc_pair, card pixels) and the VGA (mode 0Dh with the
    CGA's four colours, 130.46.1 D6: the same pixels as the CGA) with "47" and "08" on it.
Writes wallclock/*.png and wallclock/numbers.txt.  About 10 s."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B                                                   # noqa: E402
from bonanza_assets import BLK, CYN, MAG, WHT, CGA1, cga_bytes, herc_pair   # noqa: E402
from PIL import Image, ImageDraw                                       # noqa: E402

FONT57 = B.CLOCK_FONT                                       # the shipped 5 x 7 (bit 4 the leftmost column)
# a 4 x 7 condensed cut of it (bit 3 the leftmost), for the one-digit-a-cell layout
FONT47 = ((6, 9, 11, 13, 9, 9, 6), (2, 6, 2, 2, 2, 2, 7), (6, 9, 1, 2, 4, 8, 15), (15, 1, 2, 1, 1, 9, 6),
          (2, 6, 10, 10, 15, 2, 2), (15, 8, 14, 1, 1, 9, 6), (6, 8, 8, 14, 9, 9, 6), (15, 1, 1, 2, 4, 4, 4),
          (6, 9, 9, 6, 9, 9, 6), (6, 9, 9, 7, 1, 1, 6))
# a 3 x 5 (bit 2 the leftmost), for a 1-unit (8 px) face
FONT35 = ((7, 5, 5, 5, 7), (2, 6, 2, 2, 7), (7, 1, 7, 4, 7), (7, 1, 3, 1, 7), (5, 5, 7, 1, 1), (7, 4, 7, 1, 7),
          (7, 4, 7, 5, 7), (7, 1, 1, 2, 2), (7, 5, 7, 5, 7), (7, 5, 7, 1, 7))
FONTS = {"5x7": (FONT57, 5), "4x7": (FONT47, 4), "3x5": (FONT35, 3)}
POSES = 11                                                  # 0 blank, 1 + d the digit d (CLOCK_POSES)
Z = 6                                                       # preview zoom (game px)
OUT = []


def say(s=""):
    print(s)
    OUT.append(s)


def hosts(c, which, cells):
    return sorted((Face(c, which, k) for k in cells), key=lambda f: f.x0)


def compile_(path):
    return B.compile_course(path)


class Face:
    """one visible face of one cell: its pixels as the compile drew them"""
    def __init__(self, c, which, cell):
        op = [o for o in c.ops if o[1] == which and o[6] == cell]
        if not op:
            raise SystemExit("no %s face at %s" % (which, cell))
        sp0, _w, s = op[0][0], op[0][1], op[0][2]
        self.which, self.cell, self.s = which, cell, s
        self.pix = set()
        for y, runs in sp0.items():
            for a, b in runs:
                for x in range(a, b):
                    if c.sbuf[y + c.y0][x] == s:
                        self.pix.add((x, y + c.y0))
        self.top = {}
        for (x, y) in self.pix:
            self.top[x] = min(self.top.get(x, 1 << 30), y)
        xs = sorted(self.top)
        self.x0, self.x1 = xs[0], xs[-1] + 1
        # interior: a face-ink pixel (not an edge line's black) with its four neighbours on the face
        self.inner = {(x, y) for (x, y) in self.pix if c.pic[y][x] != BLK or which == "se"}
        self.inner = {(x, y) for (x, y) in self.inner
                      if all(q in self.pix for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
                      and x != self.x0}
        # the black edge line under the face's top edge: the first face-ink line at each column
        # the first line under the face's top edge line, each column: the face's own 1:2 staircase (read off the
        # geometry, not the ink - the se face's checker would make an ink test jitter a line by parity)
        self.ink_top = {x: y + 1 for x, y in self.top.items() if x != self.x0}


def glyph_ink(font, w, d, X0, ytop, shear):
    """digit D's pixels with its left column at X0: row r of column k at ytop(X0 + k) + r (SHEARED: the face's
    own staircase) or ytop(X0) + r (UPRIGHT)"""
    g = font[d]
    out = set()
    for r, bits in enumerate(g):
        for k in range(w):
            if bits & (1 << (w - 1 - k)):
                x = X0 + k
                out.add((x, (ytop(x) if shear else ytop(X0)) + r))
    return out


def place_digits(faces, font, n, pitch, shear, v0, first_word, nudge):
    """the n places' ink at every pose -> [{pose: set}] (place 0 the units, the rightmost)"""
    fnt, w = FONTS[font]
    top = {}
    for f in faces:
        top.update({x: y + 1 for x, y in f.top.items()})
        top.update(f.ink_top)
    places = []
    for p in range(n):
        k = n - 1 - p                                      # left to right
        X0 = 8 * first_word + k * pitch + 1 + nudge
        poses = {0: set()}
        XL = 8 * first_word + 1 + nudge                    # LEVEL: every place on the leftmost one's line
        for d in range(10):
            if shear == "level":
                poses[1 + d] = glyph_ink(fnt, w, d, X0, lambda x: top.get(XL, -1000) + v0, False)
            else:
                poses[1 + d] = glyph_ink(fnt, w, d, X0, lambda x: top.get(x, -1000) + v0, shear)
        places.append(poses)
    return places


def check(faces, places):
    inner = set().union(*[f.inner for f in faces])
    bad = [(x, y) for pl in places for q in pl.values() for (x, y) in q if (x, y) not in inner]
    return bad


def blocks_of(pts):
    return {(x >> 3, y >> 3) for (x, y) in pts}


def block_bytes(pic, bx, by):
    return bytes(pic[8 * by + j][8 * bx + i] for j in range(8) for i in range(8))


def pool(pic, W, H):
    return {block_bytes(pic, bx, by) for by in range(H // 8) for bx in range(W // 8)}


def lane_cost(c, base, places, ink):
    """-> (rects, shared, new blocks, record + map bytes)"""
    W, H = c.width, c.lines
    have = pool(base, W, H)
    rects, cells = [], []
    for pl in places:
        bs = set().union(*[blocks_of(q) for q in pl.values()])
        cells.append(bs)
        xs = [b[0] for b in bs]
        ys = [b[1] for b in bs]
        rects.append((min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1))
    shared = any(cells[i] & cells[j] for i in range(len(cells)) for j in range(i + 1, len(cells)))
    new = set()
    for pl, (bx0, by0, w, h) in zip(places, rects):
        for q in pl.values():
            for by in range(by0, by0 + h):
                for bx in range(bx0, bx0 + w):
                    blk = bytearray(block_bytes(base, bx, by))
                    for (x, y) in q:
                        if x >> 3 == bx and y >> 3 == by:
                            blk[8 * (y & 7) + (x & 7)] = ink
                    blk = bytes(blk)
                    if blk not in have:
                        new.add(blk)
    rec = sum(32 + 2 * POSES * w * h for (_x, _y, w, h) in rects)
    return rects, shared, len(new), rec


def draw(pic, pts, ink):
    for (x, y) in pts:
        pic[y][x] = ink


def panels(pic, box, title):
    """CGA | Hercules | VGA of the crop BOX (x, y, w, h), zoomed, captioned"""
    x, y, w, h = box
    cga = Image.new("RGB", (w, h))
    cga.putdata([CGA1[pic[y + j][x + i]] for j in range(h) for i in range(w)])
    cga = cga.resize((w * Z, h * Z), Image.NEAREST)
    herc = Image.new("RGB", (2 * w, h))
    data = []
    for j in range(h):
        for i in range(w):
            pr = herc_pair(pic[y + j][x + i], y + j, x + i)
            for b in (pr >> 1, pr & 1):
                data.append((255, 255, 255) if b else (0, 0, 0))
    herc.putdata(data)
    herc = herc.resize((w * Z, h * Z), Image.NEAREST)
    vga = cga.copy()                       # 130.46.1 D6: the CGA's four colours, the same blocks (130.46.5)
    cap = 14
    sheet = Image.new("RGB", (3 * w * Z + 16, h * Z + cap), (60, 60, 60))
    d = ImageDraw.Draw(sheet)
    for k, (im, nm) in enumerate(((cga, "CGA"), (herc, "Hercules"), (vga, "VGA (0Dh, the CGA's colours)"))):
        sheet.paste(im, (k * (w * Z + 8), cap))
        d.text((k * (w * Z + 8) + 2, 1), "%s - %s" % (title, nm), fill=(255, 255, 255))
    return sheet


def stack(sheets, path):
    W = max(s.width for s in sheets)
    H = sum(s.height for s in sheets) + 6 * (len(sheets) - 1)
    out = Image.new("RGB", (W, H), (40, 40, 40))
    y = 0
    for s in sheets:
        out.paste(s, (0, y))
        y += s.height + 6
    out.save(os.path.join(HERE, path))
    say("  wrote %s" % path)


def best(faces, font, n, pitch, shear, first_words):
    """the placement (v0, first word, nudge) that is legal and costs the fewest lane blocks"""
    out = None
    for fw in first_words:
        for nudge in (-1, 0, 1, 2):
            for v0 in range(0, 20):
                pl = place_digits(faces, font, n, pitch, shear, v0, fw, nudge)
                if check(faces, pl):
                    continue
                nb = sum(len(set().union(*[blocks_of(q) for q in p.values()])) for p in pl)
                ys = [y for p in pl for q in p.values() for (_x, y) in q]
                xs = [x for p in pl for q in p.values() for (x, _y) in q]
                inner = set().union(*[f.inner for f in faces])
                col = [y for (x, y) in inner if x == (min(xs) + max(xs)) // 2]
                mid = (min(col) + max(col)) / 2.0 if col else 0
                key = (nb, abs((min(ys) + max(ys)) / 2.0 - mid) // 2)
                if out is None or key < out[0]:
                    out = (key, v0, fw, nudge, pl)
    return out


def variant(c, name, faces, font, n, pitch, shear, ink, first_words, plaque=None, show=((4, 7), (0, 8))):
    """one study: place, check, cost, picture"""
    b = best(faces, font, n, pitch, shear, first_words)
    if b is None:
        say("%-34s NO LEGAL PLACEMENT (the face is too small for the glyph)" % name)
        return None
    _k, v0, fw, nudge, places = b
    base = [bytearray(r) for r in c.pic]
    stat_new = 0
    if plaque is not None:
        pts = plaque(places) & set().union(*[f.inner for f in faces])
        have0 = pool(base, c.width, c.lines)
        draw(base, pts, WHT)
        stat_new = len(pool(base, c.width, c.lines) - have0)
    rects, shared, new, rec = lane_cost(c, base, places, ink)
    say("%-34s lanes %s%s; new pose blocks %d (CGA %d B), static art blocks %d (%d B), records+maps %d B"
        % (name, " ".join("%dx%d@(%d,%d)" % (w, h, x, y) for (x, y, w, h) in rects),
           "  SHARED BLOCK (product poses)" if shared else "", new, 16 * new, stat_new, 16 * stat_new, rec))
    imgs = []
    for digits in show:
        pic = [bytearray(r) for r in base]
        for p, d in enumerate(reversed(digits)):
            if p < n:
                draw(pic, places[p][1 + d], ink)
        imgs.append(pic)
    return {"name": name, "places": places, "pics": imgs, "rects": rects, "new": new, "stat": stat_new,
            "rec": rec, "shared": shared}


def plaque_band(faces):
    """a factory: a WHITE plaque under the digits, a parallelogram on the face - every column from a line over
    the digits' highest ink to a line under their lowest, measured from the face's own top edge, so the band
    follows the face's slope (static paint on the face: its key is the face's)"""
    top = {}
    for f in faces:
        top.update({x: y + 1 for x, y in f.top.items()})
        top.update(f.ink_top)

    def band(places, pad=1):
        allp = [(x, y) for pl in places for q in pl.values() for (x, y) in q]
        lo = min(y - top[x] for x, y in allp) - pad
        hi = max(y - top[x] for x, y in allp) + pad
        xs = [x for x, _y in allp]
        return {(x, top[x] + r) for x in range(min(xs) - pad - 1, max(xs) + pad + 2) if x in top
                for r in range(lo, hi + 1)}
    return band


def plaque_boxes(places, pad=1):
    """a WHITE box under each digit place (UPRIGHT digits: each place's poses' bounding box, PAD px round)"""
    pts = set()
    for pl in places:
        allp = [xy for q in pl.values() for xy in q]
        xs = [x for x, _y in allp]
        ys = [y for _x, y in allp]
        pts |= {(x, y) for x in range(min(xs) - pad, max(xs) + pad + 1)
                for y in range(min(ys) - pad, max(ys) + pad + 1)}
    return pts


def existing_clock(c):
    """FIRST's shipped clock lanes, counted the same way (the comparator, MEASURED from the compile)"""
    uniq, base = set(), set()
    for L in c.lanes:
        for pose, ws in L["words"].items():
            (base if pose == 0 else uniq).update(ws)
    return len(c.lanes), len(uniq - base)


def main():
    say("WALL CLOCK study, %s" % os.path.relpath(__file__, ROOT))
    say("")
    first = compile_(os.path.join(ROOT, "apps", "bonanza", "courses", "first.bbc"))
    nl, nb = existing_clock(first)
    say("comparator, FIRST's shipped clocks: %d digit lanes, each 1 x 1 block, %d distinct pose blocks over pose 0's "
        "(CGA %d B) - MEASURED from the compile" % (nl, nb, 16 * nb))
    say("")
    c = compile_(os.path.join(HERE, "wall.bbc"))
    tall_sw = hosts(c, "sw", ((5, 7), (6, 7)))       # 3 units, two cells
    tall_se = hosts(c, "se", ((6, 6), (6, 7)))
    mid_sw = hosts(c, "sw", ((10, 7), (11, 7)))      # 2 units
    mid_se = hosts(c, "se", ((11, 6), (11, 7)))
    low_sw = hosts(c, "sw", ((15, 7), (16, 7)))      # 1 unit
    low_se = hosts(c, "se", ((16, 6), (16, 7)))
    for nm, fs in (("tall sw", tall_sw), ("tall se", tall_se), ("2u sw", mid_sw), ("1u sw", low_sw)):
        say("host %-8s cells %s, x %d .. %d, %d visible px, %d inside the edges"
            % (nm, [f.cell for f in fs], fs[0].x0, fs[-1].x1, sum(len(f.pix) for f in fs),
               sum(len(f.inner) for f in fs)))
    say("")

    def words(fs):
        return range(fs[0].x0 >> 3, (fs[-1].x1 >> 3))

    def crop(fs, pad=6):
        xs = [x for f in fs for (x, _y) in f.pix]
        ys = [y for f in fs for (_x, y) in f.pix]
        return (min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)

    say("== 1. SHEARED 5 x 7 (the shipped font), two digits a word apart, on a 3-unit face ==")
    rows = []
    for fs, ink, nm in ((tall_sw, BLK, "sw (left), black, bare"), (tall_se, WHT, "se (right), white, bare"),
                        (tall_sw, BLK, "sw, black on a white plaque"), (tall_se, BLK, "se, black on a white plaque")):
        pl = plaque_band(fs) if "plaque" in nm else None
        v = variant(c, "shear 5x7 " + nm, fs, "5x7", 2, 8, True, ink, words(fs), plaque=pl)
        if v:
            rows.append(panels(v["pics"][0], crop(fs), "%s  '47'" % v["name"]))
            rows.append(panels(v["pics"][1], crop(fs), "%s  '08'" % v["name"]))
    stack(rows, "shear57.png")
    say("")

    say("== 2. ONE DIGIT A CELL: a 4 x 7 sheared, a digit on each column's face (16 px apart) ==")
    rows = []
    for fs, ink, nm in ((tall_sw, BLK, "sw, black, bare"), (tall_se, WHT, "se, white, bare"),
                        (mid_sw, BLK, "sw 2-unit, black, bare"), (mid_se, WHT, "se 2-unit, white, bare")):
        v = variant(c, "shear 4x7 a cell " + nm, fs, "4x7", 2, 16, True, ink, words(fs))
        if v:
            rows.append(panels(v["pics"][0], crop(fs), "%s  '47'" % v["name"]))
    stack(rows, "percell47.png")
    say("")

    say("== 3. 2-unit and 1-unit faces ==")
    rows = []
    for fs, font, ink, nm in ((mid_sw, "5x7", BLK, "shear 5x7 2-unit sw"), (mid_se, "5x7", WHT, "shear 5x7 2-unit se"),
                              (low_sw, "5x7", BLK, "shear 5x7 1-unit sw"),
                              (low_sw, "3x5", BLK, "shear 3x5 1-unit sw"), (low_se, "3x5", WHT, "shear 3x5 1-unit se")):
        v = variant(c, nm, fs, font, 2, 8 if font != "3x5" else 4 + 4, True, ink, words(fs))
        if v:
            rows.append(panels(v["pics"][0], crop(fs), "%s  '47'" % v["name"]))
    stack(rows, "small.png")
    say("")

    say("== 4. UPRIGHT (unsheared) on the same faces, for comparison ==")
    rows = []
    for fs, ink, pitch, nm in ((tall_sw, BLK, 8, "sw, black"), (tall_se, WHT, 8, "se, white"),
                               (tall_sw, BLK, 8, "sw, black, boxed"), (tall_se, BLK, 8, "se, black, boxed"),
                               (mid_sw, BLK, 8, "sw 2-unit, black, boxed"), (mid_se, BLK, 8, "se 2-unit, black, boxed"),
                               (tall_sw, BLK, "level", "sw, LEVEL, black, boxed"),
                               (tall_se, BLK, "level", "se, LEVEL, black, boxed"),
                               (mid_sw, BLK, "level", "sw 2-unit, LEVEL, black, boxed"),
                               (tall_sw, BLK, 16, "sw, a digit a cell, black, boxed"),
                               (tall_se, BLK, 16, "se, a digit a cell, black, boxed")):
        pl = plaque_boxes if "boxed" in nm else None
        shear = "level" if pitch == "level" else False
        pitch = 8 if pitch == "level" else pitch
        v = variant(c, "upright 5x7 " + nm, fs, "5x7", 2, pitch, shear, ink, words(fs), plaque=pl)
        if v:
            rows.append(panels(v["pics"][0], crop(fs), "%s  '47'" % v["name"]))
            if "boxed" in nm and pitch == 8 and "2-unit" not in nm:
                rows.append(panels(v["pics"][1], crop(fs), "%s  '08'" % v["name"]))
    stack(rows, "upright.png")
    say("")

    say("== 5. THREE digits (a limit of 100 s or more) across two cells ==")
    rows = []
    for fs, ink, nm in ((tall_sw, BLK, "sw, black"), (tall_se, WHT, "se, white")):
        v = variant(c, "shear 5x7 3 digits " + nm, fs, "5x7", 3, 8, True, ink, words(fs),
                    show=((1, 2, 7), (0, 0, 9)))
        if v:
            rows.append(panels(v["pics"][0], crop(fs), "%s  '127'" % v["name"]))
    stack(rows, "three.png")
    say("")

    say("== 6. a FLOOR clock: digits painted flat on a top (projected, 2 gu a glyph pixel) and as an upright decal ==")
    floor(c)
    say("")

    say("== 7. on a real course: FIRST ROLL's plateau front (sw faces of (3..6, 6)) ==")
    ff = hosts(first, "sw", ((4, 6), (5, 6)))
    rows = []
    for ink, shear, nm in ((BLK, True, "sheared, black, bare"), (BLK, True, "sheared, black on a white plaque"),
                           (BLK, False, "upright, black, boxed"), (BLK, "level", "LEVEL, black, boxed")):
        pl = plaque_band(ff) if "plaque" in nm else (plaque_boxes if "boxed" in nm else None)
        v = variant(first, "FIRST plateau sw 5x7 " + nm, ff, "5x7", 2, 8, shear, ink, words(ff), plaque=pl)
        if v:
            x, y, w, h = crop(ff, 12)
            rows.append(panels(v["pics"][0], (x, y, w, min(h, 96)), "%s  '47'" % v["name"]))
    stack(rows, "first.png")
    with open(os.path.join(HERE, "numbers.txt"), "w") as f:
        f.write("\n".join(OUT) + "\n")


def floor(c):
    """digits on the apron's floor in front of the tall block: (a) projected onto the top plane, a glyph pixel
    2 x 2 gu (screen: u along +x is (2, 1) px a gu... so a digit is about 24 x 12 px), (b) an upright decal"""
    rows = []
    fnt, w = FONTS["5x7"]
    ox, oy = 2 * 16 * 0 + 384 + 16 * (9 - 9), 0
    # the floor cell (8, 9)'s top: its north corner at cx = 16 (wx - wy) + x0, cy = 8 (wx + wy) + y0
    wx, wy = 7.2, 8.6
    pics = []
    for mode in ("projected", "decal"):
        pic = [bytearray(r) for r in c.pic]
        pts = set()
        for p, d in enumerate((4, 7)):
            if mode == "projected":
                for r, bits in enumerate(fnt[d]):
                    for k in range(w):
                        if bits & (1 << (w - 1 - k)):
                            for a in range(4):
                                for b_ in range(4):
                                    u = wx * 16 + 2 * (k + 6 * p) + a / 2.0     # gu (16 a cell)
                                    v = wy * 16 + 2 * r + b_ / 2.0
                                    x = int(round(u - v)) + c.x0
                                    y = int(round((u + v) / 2.0)) + c.y0 + 8
                                    pts.add((x, y))
            else:
                X0 = 16 * (8 - 9) + c.x0 + 8 * p + 1
                Y0 = 8 * (8 + 9) + c.y0 + 2
                for r, bits in enumerate(fnt[d]):
                    for k in range(w):
                        if bits & (1 << (w - 1 - k)):
                            pts.add((X0 + k, Y0 + r))
        draw(pic, pts, BLK)
        bs = blocks_of(pts)
        say("floor %-9s '47': %d ink px over %d blocks (x %d .. %d, lines %d .. %d)"
            % (mode, len(pts), len(bs), min(x for x, _ in pts), max(x for x, _ in pts),
               min(y for _, y in pts), max(y for _, y in pts)))
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        rows.append(panels(pic, (min(xs) - 24, min(ys) - 16, max(xs) - min(xs) + 48, max(ys) - min(ys) + 32),
                           "floor, %s  '47'" % mode))
    # the projected digits' lanes: a digit's blocks against its neighbour's
    pl = []
    for p, d0 in enumerate((0, 0)):
        poses = {0: set()}
        for d in range(10):
            q = set()
            for r, bits in enumerate(fnt[d]):
                for k in range(w):
                    if bits & (1 << (w - 1 - k)):
                        for a in range(4):
                            for b_ in range(4):
                                u = wx * 16 + 2 * (k + 6 * (1 - p)) + a / 2.0
                                v = wy * 16 + 2 * r + b_ / 2.0
                                q.add((int(round(u - v)) + c.x0, int(round((u + v) / 2.0)) + c.y0 + 8))
            poses[1 + d] = q
        pl.append(poses)
    rects, shared, new, rec = lane_cost(c, [bytearray(r) for r in c.pic], pl, BLK)
    say("floor projected lanes %s%s; new pose blocks %d (CGA %d B), records+maps %d B"
        % (" ".join("%dx%d" % (w_, h) for (_x, _y, w_, h) in rects), "  SHARED BLOCK" if shared else "",
           new, 16 * new, rec))
    stack(rows, "floor.png")


if __name__ == "__main__":
    main()
