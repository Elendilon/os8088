#!/usr/bin/env python3
"""Bounce Bonanza's PATHWAY - OPTIONS for its initial look (the owner, 2026-11-19).

    python3 docs/plans/bonanza-courses/pathway/gen.py [--out DIR] [--only A,B]

writes, for each option in OPTIONS below:

  docs/plans/bonanza-courses/pathway/opt<X>.bbc   the option's pathway SOURCE (SPEC.md 130.22.2's grammar),
                                                  generated from the layout here; it compiles with
                                                  tools/bbcourse.py's own checks and proofs
  docs/plans/bonanza-courses/pathway/icons/*.bba  the icons it names (bbicons.py's placeholders redrawn at
                                                  the option's sizes, plus two new placeholders below)
  DIR/opt<X>-sheet.png                            the comparison sheet: every page, CGA palette 1 and the
                                                  Hercules, windows marked, pads tagged 1 - 8 as on the sketch

and DIR/overview.png, every option side by side.  DIR defaults to build/bonanza-pathway/.

Everything here is TOOL-side.  The pathway is compiled by tools/bbcourse.py itself (compile_course, the
same call `make` makes with --path, its checks included) and its proofs (path_proofs) run against the
BZROLL=1 course list, so ROLL and HOP are pads.  Two things are done to the tool from OUTSIDE it, for a
sheet only and never for a build:

  * the course titles: TRIAL plays course 3 and is titled "Downhill Decision" (the course is not built
    yet), FIRST plays course 8 titled "Bounce Trial" (FIRST and ROLL are both "First Roll" today);
  * an option with font "5x7" swaps bbcourse.text_pixels (the TITLES only: the lives counter keeps the
    8 x 8 label face) for the 5 x 7 small caps of tools/os88cdart.py, centred where the 8 x 8 title would
    be.  The titles are picture pixels, so the guest is unchanged by a face: a face costs only the picture
    blocks its pixels make.
"""
import argparse
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
import bbcourse as B                                          # noqa: E402
import bbicons as BI                                          # noqa: E402
import bonanza_assets as BA                                   # noqa: E402
from os88cdart import CAPS                                    # noqa: E402

ICON_OUT = os.path.join(HERE, "icons")
ICON_REL = os.path.relpath(ICON_OUT, B.COURSE_DIR)            # an icon FILE is under apps/bonanza/courses/

COURSES = B.default_paths() + [os.path.join("apps", "bonanza", "courses", n) for n in ("roll.bbc", "hop.bbc")]
TITLES = {"TRIAL": "@-25@Downhill|Decision", "FIRST": "Bounce Trial",     # the sheet's stand-ins
          "MOON": "@-26@Moonlit Green", "MILL": "@-21@Windmill Lane"}    # (@DX@: option A's titles set off their icons, the owner's mark-up)

# sketch number -> (course, icon stem)
SKETCH = {1: ("ROLL", "first"), 2: ("HOP", "frog"), 3: ("TRIAL", "fork"), 4: ("MILL", "mill"),
          5: ("PEAK", "summit"), 6: ("MOON", "moon"), 7: ("PLAY", "playground"), 8: ("FIRST", "trial")}


# =============================================================================
# the icons: bbicons.py's drawings at any size, and two new placeholders
# =============================================================================
class _Raw:
    """a target canvas the base Canvas methods draw into without scaling"""
    def __init__(self, cv):
        self.cv, self.w, self.h = cv, cv.w, cv.h

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.cv.p[y][x] = c


BaseCanvas = BI.Canvas


class Scaled(BaseCanvas):
    """bbicons.Canvas whose drawing calls are in the 48 x 32 design space and land on a W x H canvas"""
    SIZE = (48, 32)

    def __init__(self, w=None, h=None):
        tw, th = self.SIZE
        super().__init__(tw, th)
        self.sx, self.sy = tw / 48.0, th / 32.0
        self.raw = _Raw(self)

    def _fn(self, fn):
        return None if fn is None else (lambda x, y: fn((x + .5) / self.sx - .5, (y + .5) / self.sy - .5))

    def put(self, x, y, c):
        self.raw.put(int(x * self.sx), int(y * self.sy), c)

    def disc(self, cx, cy, r, c, fn=None):
        BaseCanvas.disc(self.raw, cx * self.sx, cy * self.sy, max(.7, r * min(self.sx, self.sy)), c, self._fn(fn))

    def ring(self, cx, cy, r0, r1, c):
        s = min(self.sx, self.sy)
        BaseCanvas.ring(self.raw, cx * self.sx, cy * self.sy, r0 * s, max(r1 * s, r0 * s + .8), c)

    def rect(self, x0, y0, x1, y1, c):
        BaseCanvas.rect(self.raw, int(round(x0 * self.sx)), int(round(y0 * self.sy)),
                       max(int(round(x1 * self.sx)), int(round(x0 * self.sx)) + 1),
                       max(int(round(y1 * self.sy)), int(round(y0 * self.sy)) + 1), c)

    def line(self, x0, y0, x1, y1, c, w=1.0):
        BaseCanvas.line(self.raw, x0 * self.sx, y0 * self.sy, x1 * self.sx, y1 * self.sy, c,
                       max(1.0, w * min(self.sx, self.sy)))

    def poly(self, pts, c, fn=None):
        BaseCanvas.poly(self.raw, [(x * self.sx, y * self.sy) for x, y in pts], c, self._fn(fn))


def _frog(t, n):
    """LITTLE HOP's placeholder: a frog that crouches and hops (the course's clocks are frogs)"""
    cv = BI.Canvas()
    lift = (0, 3, 7, 9, 7, 3)[t % 6]
    cv.rect(4, 30, 44, 32, 1)                                 # the lily pad's rim
    cv.poly([(6, 30), (42, 30), (38, 27), (10, 27)], 2)
    y = 22 - lift
    if lift:                                                  # the hind legs stretched under a hop
        cv.line(16, y + 4, 11, y + 9, 1, 2.2)
        cv.line(32, y + 4, 37, y + 9, 1, 2.2)
    else:                                                     # crouched: the haunches out to the sides
        cv.disc(13, y + 3, 4.2, 1)
        cv.disc(35, y + 3, 4.2, 1)
    cv.disc(24, y, 10.5, 1)                                   # the body
    cv.disc(24, y + 3, 6.0, 3)                                # the belly
    for ex in (17, 31):                                       # the eyes, white with black pupils
        cv.disc(ex, y - 8, 4.2, 3)
        cv.disc(ex, y - 8, 1.6, 0)
    cv.line(19, y - 1, 29, y - 1, 0, 1.0)                     # the mouth
    return cv


def _fork(t, n):
    """DOWNHILL DECISION's placeholder: a signpost at a fork on a slope, its two arrows lit in turn"""
    cv = BI.Canvas()
    cv.poly([(0, 31), (0, 25), (48, 18), (48, 31)], 2)        # the slope, down to the left
    cv.line(0, 25, 48, 18, 3, 1.2)
    cv.rect(23, 6, 26, 28, 3)                                 # the post
    left_lit = t in (1, 2)
    right_lit = t in (4, 5)
    for (pts, lit) in (([(4, 9), (10, 4), (22, 4), (22, 14), (10, 14)], left_lit),
                       ([(44, 13), (38, 8), (27, 8), (27, 18), (38, 18)], right_lit)):
        cv.poly(pts, 3 if lit or t == 0 else 1)
        for a, b in zip(pts, pts[1:] + pts[:1]):
            cv.line(a[0], a[1], b[0], b[1], 0, 1.0)
    cv.disc(24.5, 5, 2.2, 3)                                  # the post's cap
    return cv


DRAW = {"first": (BI._first, 6), "trial": (BI._trial, 6), "mill": (BI._mill, 6), "moon": (BI._moon, 5),
        "summit": (BI._peak, 6), "playground": (BI._play, 6), "frog": (_frog, 6), "fork": (_fork, 6)}


def icon_file(stem, w, h):
    """write ICON_OUT/<stem><w>x<h>.bba (frames stacked) -> its name relative to apps/bonanza/courses/"""
    fn, k = DRAW[stem]
    Scaled.SIZE = (w, h)
    old = BI.Canvas
    BI.Canvas = Scaled
    try:
        frames = [fn(t, k).rows() for t in range(k)]
    finally:
        BI.Canvas = old
    rows = [r for fr in frames for r in fr]
    name = "%s%dx%d.bba" % (stem, w, h)
    os.makedirs(ICON_OUT, exist_ok=True)
    txt = BA.bba_text(rows, k, "%s at %d x %d, %d frames: a PLACEHOLDER (bbicons.py's drawing, or gen.py's), "
                               "generated by docs/plans/bonanza-courses/pathway/gen.py - edit that" % (stem, w, h, k))
    with open(os.path.join(ICON_OUT, name), "w", newline="\n") as f:
        f.write(txt)
    return os.path.join(ICON_REL, name)


# =============================================================================
# the title faces
# =============================================================================
def caps57_pixels(text, x, y, ink=3):
    """the 5 x 7 small caps (os88cdart.CAPS), 6 px a letter, centred where text_pixels' 8 x 8 run would be,
    its baseline that run's.  A "|" breaks the title into LINES (the owner's 2026-11-19 mark-up of A:
    DOWNHILL over DECISION), each centred on the same column, the last on the run's baseline and each
    one before it 9 lines higher"""
    cx = x + 4 * len(text)
    m = re.match(r"@(-?\d+)@", text)
    if m:
        cx += int(m.group(1))
        text = text[m.end():]
    lines = text.split("|")
    out = {}
    for n, t in enumerate(lines):
        w = 6 * len(t) - 1
        x0 = cx - w // 2
        ly = y - 9 * (len(lines) - 1 - n)
        for i, ch in enumerate(t):
            g = CAPS.get(ch, CAPS[" "])
            for r, row in enumerate(g):
                for k, cc in enumerate(row):
                    if cc == "#":
                        out[(x0 + 6 * i + k, ly + 1 + r)] = ink
    return out


FACES = {"8x8": B.text_pixels, "5x7": caps57_pixels}


# =============================================================================
# the options
# =============================================================================
# pad: sketch number -> (wx, wy, icon size (w, h) or None, where the icon sits: L R U, dx, dy nudges in px)
# route: (a, b, exit, "path ...") in sketch numbers;  lives: [(wx, wy)]
OPTIONS = {
    "A": dict(
        name="Faithful", pages=2, view=(0, 332), font="5x7", float=True, rail="crystal",
        blurb="the sketch's layout over two pages: 1-2-3 along a broad bottom road, the split at 3 - a straight "
              "climb to 4-5 on the right, a long diagonal to 6, then 7 and out to 8 at the far left; "
              "32 x 24 icons, 5 x 7 titles",
        pads={1: (21, 28, (32, 24), "U", 0, 0), 2: (24, 25, (32, 24), "U", 0, 0),
              3: (24, 17, (32, 24), "L", -2, 24), 4: (20, 13, (32, 24), "L", 1, 0),
              5: (12, 5, (32, 24), "L", -34, 0), 6: (15, 17, (32, 24), "L", 4, 16),
              7: (9, 11, (32, 24), "R", 0, 8), 8: (4, 11, (32, 24), "R", 0, -8)},
        routes=[(1, 2, 0, "21,28 24,25"), (2, 3, 0, "24,25 28,21 24,17"),
                (3, 4, 0, "24,17 20,13"), (3, 6, 1, "24,17 15,17"),
                (4, 5, 0, "20,13 12,5"), (6, 7, 0, "15,17 9,11", (14, 16)), (7, 8, 0, "9,11 4,11")],
        lives=[(16, 23), (6, 4)]),
    "B": dict(
        name="Roomy", pages=4, view=(0, 740), font="8x8", float=True, rail="crystal",
        blurb="sparser: two or three pads a page over four pages, today's 48 x 32 icons (Downhill Decision's "
              "64 x 40) and today's 8 x 8 titles; the split at 3 is a T, two climbing columns, 4-5 right and 6-7 "
              "left, page 3 left for what comes after 8",
        pads={1: (46, 52, (48, 32), "U", -16, 0), 2: (47, 42, (48, 32), "R", -8, 0),
              3: (37, 37, (64, 40), "U", 0, 0), 4: (33, 27, (48, 32), "L", -40, 0),
              5: (25, 19, (48, 32), "L", -40, 0), 6: (30, 36, (48, 32), "R", 40, 0),
              7: (21, 27, (48, 32), "R", 40, 8), 8: (10, 10, (48, 32), "U", 0, 0)},
        routes=[(1, 2, 0, "46,52 46,43 47,42"), (2, 3, 0, "47,42 42,42 37,37"),
                (3, 4, 0, "37,37 40,34 33,27"), (3, 6, 1, "37,37 34,40 30,36"),
                (4, 5, 0, "33,27 25,19"), (6, 7, 0, "30,36 21,27"), (7, 8, 0, "21,27 17,23 17,17 10,10")],
        lives=[(38, 45), (30, 39), (13, 22), (12, 4)]),
    "C": dict(
        name="Causeway", pages=3, view=(0, 540), font="5x7", float=False, rail="normal",
        blurb="causeways, not crystal: the routes in the courses' own floor look, standing on walls to the ground "
              "and RAMPING up as the map climbs (no floating); icons of mixed sizes (32 x 24 to 48 x 32), "
              "5 x 7 titles, three pages",
        pads={1: (33, 40, (32, 24), "U", 0, 0), 2: (33, 34, (32, 24), "L", 0, 0),
              3: (35, 28, (32, 24), "L", -74, 14), 4: (29, 22, (32, 24), "L", -34, 0),
              5: (14, 7, (40, 28), "L", -26, 0), 6: (26, 28, (32, 24), "L", -36, 0),
              7: (13, 15, (40, 28), "R", 16, 16), 8: (8, 15, (32, 24), "U", 0, 0)},
        routes=[(1, 2, 0, "33,40 33,37 33,34,1"), (2, 3, 0, "33,34,1 37,30,1 35,28,1"),
                (3, 4, 0, "35,28,1 29,22,1"), (3, 6, 1, "35,28,1 32,28,1 28,28,4 26,28,4"),
                (4, 5, 0, "29,22,1 14,7,1"), (6, 7, 0, "26,28,4 13,15,4"),
                (7, 8, 0, "13,15,4 10,15,5 8,15,5")],
        lives=[(42, 34), (19, 17), (8, 4)]),
}


def pad_xy(wx, wy, x0, y0, h2=0):
    return 16 * (wx - wy) + x0, 8 * (wx + wy) + 8 - 4 * h2 + y0


def pad_h2(o, n):
    """pad N's height in half units, from the route ends at its cell"""
    wx, wy = o["pads"][n][:2]
    for _a, _b, _e, pts in (r[:4] for r in o["routes"]):
        for t in pts.split():
            v = t.split(",")
            if (int(v[0]), int(v[1])) == (wx, wy):
                return int(round(2 * float(v[2]))) if len(v) > 2 else 0
    return 0


def write_source(key, o, x0=None, y0=None):
    """the option's .bbc; with X0/Y0 (a first compile's) the icons placed and snapped to blocks"""
    lines = ["# Bounce Bonanza's PATHWAY, option %s (%s) - GENERATED by docs/plans/bonanza-courses/pathway/gen.py:"
             % (key, o["name"]),
             "# edit OPTIONS there, not this.  A SHEET'S source (docs/plans/bonanza-courses/pathway/README.md),",
             "# never the shipped map: pads 4 - 8 play the old test courses as STAND-INS, TRIAL stands in for",
             "# course 3 (Downhill Decision, not built yet).  Pads are numbered from 0: pad N is the sketch's N+1.",
             "#   " + o["blurb"],
             'course PATH "The Pathway"', "width  64", "ball   rubber", "pathway", "music  fairway",
             "rail   %s" % o["rail"], "view   %d %d" % o["view"], "pages  %d" % o["pages"]]
    if o["float"]:
        lines.append("float  rect 0 0 64 64")
    lines.append("")
    for n in sorted(o["pads"]):
        wx, wy = o["pads"][n][:2]
        lines.append("pad %d %-5s %2d %2d                 # sketch %d" % (n - 1, SKETCH[n][0], wx, wy, n))
    lines.append("")
    for r in o["routes"]:
        a, b, e, pts = r[:4]
        gate = "gate %d %d  " % r[4] if len(r) > 4 else ""
        lines.append("route %d %d exit %d  %spath %s" % (a - 1, b - 1, e, gate, pts))
    lines.append("")
    if x0 is not None:
        for n in sorted(o["pads"]):
            wx, wy, size, side, dx, dy = o["pads"][n]
            if size is None:
                continue
            w, h = size
            f = icon_file(SKETCH[n][1], w, h)
            cx, cy = pad_xy(wx, wy, x0, y0, pad_h2(o, n))
            if side == "U":
                px, py = cx - w // 2, cy - 10 - h
            elif side == "L":
                px, py = cx - 22 - w, cy - h + 4
            else:
                px, py = cx + 22, cy - h + 4
            px, py = px + dx, py + dy
            px, py = 8 * int(round(px / 8.0)), 8 * int(round(py / 8.0))
            lines.append("icon %d %s %d %d" % (n - 1, f, px - x0, py - y0))
        lines.append("")
    for wx, wy in o["lives"]:
        lines.append("lives %d %d" % (wx, wy))
    return "\n".join(lines) + "\n"


_COURSES = []


class _Seen:
    """a compiled course as the pathway's checks read it: its name, its title and its exits"""
    def __init__(self, name, title, exits):
        self.name, self.title, self.exits = name, title, exits


def courses():
    """the BZROLL=1 courses, compiled by the tool (minutes); what the pathway reads of them is remembered in
    build/bonanza-pathway/courses.json, keyed by a hash of the tool and the sources"""
    if _COURSES:
        return _COURSES
    import hashlib
    import json
    h = hashlib.sha256()
    for p in [os.path.join("tools", "bbcourse.py")] + COURSES:
        h.update(open(p, "rb").read())
    memo = os.path.join(ROOT, "build", "bonanza-pathway", "courses.json")
    try:
        d = json.load(open(memo))
        if d["key"] != h.hexdigest():
            d = None
    except (OSError, ValueError, KeyError):
        d = None
    if d is None:
        got = B.par_map(B.compile_course, COURSES)
        for c, e in got:
            if e is not None:
                raise e
        d = {"key": h.hexdigest(), "courses": [[c.name, c.title, sorted(B.course_exits(c).items())]
                                               for c, _e in got]}
        os.makedirs(os.path.dirname(memo), exist_ok=True)
        json.dump(d, open(memo, "w"))
    _COURSES.extend(_Seen(n, t, dict(ex)) for n, t, ex in d["courses"])
    return _COURSES


def proofs(pc, cs):
    """the tool's path_proofs over the remembered exits"""
    old = B.course_exits
    B.course_exits = lambda c: c.exits
    try:
        return B.path_proofs(pc, cs)
    finally:
        B.course_exits = old


def compile_option(key, o):
    cs = courses()
    info = [(c.name, TITLES.get(c.name, c.title)) for c in cs]
    old_mode, B._CACHE["mode"] = B._CACHE["mode"], "off"
    old_tp = B.text_pixels
    B.text_pixels = FACES[o["font"]]
    try:
        bare = write_source(key, o)
        pc0 = B.compile_course(bare, fname="<opt%s, no icons>" % key, crsinfo=info)
        text = write_source(key, o, pc0.x0, pc0.y0)
        path = os.path.join(HERE, "opt%s.bbc" % key)
        with open(path, "w", newline="\n") as f:
            f.write(text)
        pc = B.compile_course(path, crsinfo=info)
        prf = proofs(pc, cs)
    finally:
        B.text_pixels = old_tp
        B._CACHE["mode"] = old_mode
    return pc, prf


def today():
    """today's BZROLL=1 pathway (path.bbc through pathroll.sed), for the costs' baseline"""
    src = open(os.path.join(B.COURSE_DIR, "path.bbc")).read()
    for ln in open(os.path.join(B.COURSE_DIR, "pathroll.sed")).read().splitlines():
        m = re.match(r"^s/\^(.*)\$/(.*)/$", ln)
        if m:
            src = re.sub("^" + re.escape(m.group(1)) + "$", m.group(2), src, flags=re.M)
        m = re.match(r"^s/\^(.*?) /(.*?) /$", ln)
        if m:
            src = re.sub("^" + re.escape(m.group(1)) + " ", m.group(2) + " ", src, flags=re.M)
        m = re.match(r"^/\^(.*)/d$", ln)
        if m:
            src = "\n".join(x for x in src.split("\n") if not x.startswith(m.group(1)))
    cs = courses()
    pc = B.compile_course(src, fname="<path.bbc + pathroll.sed>", crsinfo=[(c.name, c.title) for c in cs])
    proofs(pc, cs)
    return pc


def costs(pc):
    pic, kinds = B.path_costs(pc)
    return {"ram": len(pc.cga), "stored": len(pc.stored), "lz4": B.packed_len(pc.stored, "lz4"),
            "lzb": B.packed_len(pc.stored, "lzb"), "pic": pic, "kinds": kinds, "blocks": pc.nblk_pic}


# =============================================================================
# the sheets
# =============================================================================
TAG = (255, 40, 40)


def _font(sz):
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def page_images(pc, o, z=2):
    """(cga, herc) of the option's pages, cropped to the Hercules window's columns and the pages' rows, at
    Z x (the Hercules at 2 px a world px across and Z/... down), with the windows and the tags drawn"""
    from PIL import Image, ImageDraw
    vi = pc.vinfo
    xa, xb = 8 * vi["c0h"], 8 * vi["c0h"] + 8 * 45          # the Hercules window's columns
    ya, yb = vi["tops"][-1], vi["tops"][0] + B.VIEW_H
    w, h = xb - xa, yb - ya
    cga = Image.new("RGB", (w, h))
    herc = Image.new("RGB", (2 * w, h))
    cp, hp = cga.load(), herc.load()
    for y in range(ya, yb):
        row = pc.pic[y]
        for x in range(xa, xb):
            v = row[x]
            cp[x - xa, y - ya] = B.CGA1[v]
            pr = B.herc_pair(v, y, x)
            for b in range(2):
                hp[2 * (x - xa) + b, y - ya] = (235, 235, 235) if (pr >> (1 - b)) & 1 else (0, 0, 0)
    cga = cga.resize((w * z, h * z), Image.NEAREST)
    herc = herc.resize((2 * w * z // 2, h * z), Image.NEAREST)
    fnt = _font(9 * z)
    for img, sx in ((cga, z), (herc, z)):
        d = ImageDraw.Draw(img)
        for k, t in enumerate(vi["tops"]):
            y0 = (t - ya) * z
            cx0 = (vi["left"] - xa) * sx
            d.rectangle([cx0, y0, cx0 + B.VIEW_W * sx - 1, y0 + B.VIEW_H * z - 1], outline=(255, 200, 0), width=1)
            d.text((cx0 + B.VIEW_W * sx - 30 * z, y0 + B.VIEW_H * z - 10 * z), "page %d" % k, fill=(255, 200, 0),
                   font=_font(7 * z))
        d.rectangle([0, 0, img.width - 1, img.height - 1], outline=(90, 90, 255), width=1)
        for q in pc.pth["pads"]:
            cx, cy = B._pad_centre(q, pc.x0, pc.y0)
            tx, ty = (cx - xa) * sx, (cy - ya) * z
            r = 7 * z
            bx, by = tx - 22 * sx, ty + 2 * z
            d.ellipse([bx - r, by - r, bx + r, by + r], fill=TAG, outline=(0, 0, 0))
            s = str(q["num"] + 1)
            tw = d.textlength(s, font=fnt)
            d.text((bx - tw / 2, by - 6 * z), s, fill=(255, 255, 255), font=fnt)
    return cga, herc


def sheet(key, o, pc, cost, base, out):
    from PIL import Image, ImageDraw
    cga, herc = page_images(pc, o)
    gap = 24
    head = 120
    W = cga.width + herc.width + 3 * gap
    H = head + max(cga.height, herc.height) + gap + 30
    img = Image.new("RGB", (W, H), (48, 48, 56))
    d = ImageDraw.Draw(img)
    d.text((gap, 10), "Option %s - %s" % (key, o["name"]), fill=(255, 255, 255), font=_font(26))
    d.text((gap, 44), o["blurb"], fill=(220, 220, 220), font=_font(15))
    d.text((gap, 66), "%d page%s, titles %s, %s routes%s.  Part: RAM %d bytes, LZB %d (today's BZROLL map: RAM %d, "
           "LZB %d)" % (o["pages"], "s" if o["pages"] > 1 else "", o["font"], o["rail"],
                        ", floating islands" if o["float"] else ", on the ground", cost["ram"], cost["lzb"],
                        base["ram"], base["lzb"]), fill=(220, 220, 220), font=_font(15))
    d.text((gap, 88), "Red tags: the sketch's course numbers.  Yellow: the CGA window of each page; blue: the "
           "Hercules window.  Pads 4 - 8 are STAND-INS (old test courses), 3 is TRIAL titled as Downhill "
           "Decision.", fill=(180, 180, 180), font=_font(13))
    img.paste(cga, (gap, head))
    img.paste(herc, (2 * gap + cga.width, head))
    d.text((gap, head + cga.height + 6), "CGA, palette 1 (2x)", fill=(200, 200, 200), font=_font(14))
    d.text((2 * gap + cga.width, head + herc.height + 6), "Hercules (2 px a world px across; 2x down)",
           fill=(200, 200, 200), font=_font(14))
    p = os.path.join(out, "opt%s-sheet.png" % key)
    img.save(p)
    return p, cga


def overview(items, out):
    from PIL import Image, ImageDraw
    gap = 24
    smalls = []
    for key, o, cga, cost in items:
        s = cga.resize((cga.width // 2, cga.height // 2), Image.NEAREST)
        smalls.append((key, o, s, cost))
    W = sum(s.width for _k, _o, s, _c in smalls) + gap * (len(smalls) + 1)
    H = max(s.height for _k, _o, s, _c in smalls) + 150
    img = Image.new("RGB", (W, H), (48, 48, 56))
    d = ImageDraw.Draw(img)
    d.text((gap, 8), "Bounce Bonanza - the pathway: initial-look options (CGA palette 1, 1x, every page)",
           fill=(255, 255, 255), font=_font(22))
    x = gap
    for key, o, s, cost in smalls:
        d.text((x, 44), "%s - %s" % (key, o["name"]), fill=(255, 255, 255), font=_font(18))
        d.text((x, 68), "%d page%s, titles %s" % (o["pages"], "s" if o["pages"] > 1 else "", o["font"]),
               fill=(210, 210, 210), font=_font(13))
        d.text((x, 86), "RAM %d, LZB %d" % (cost["ram"], cost["lzb"]), fill=(210, 210, 210), font=_font(13))
        img.paste(s, (x, 110))
        x += s.width + gap
    p = os.path.join(out, "overview.png")
    img.save(p)
    return p


def title_faces(out, z=3):
    """every sheet title in both faces, CGA palette 1 and the Hercules, at Z x: the readability check"""
    from PIL import Image, ImageDraw
    names = [TITLES.get(SKETCH[n][0], None) or {"ROLL": "First Roll", "HOP": "Little Hop", "MILL": "Windmill Lane",
             "PEAK": "Summit Rush", "MOON": "Moonlit Green", "PLAY": "Playground"}[SKETCH[n][0]] for n in range(1, 9)]
    rows = []
    for face in ("8x8", "5x7"):
        for n, t in zip(range(1, 9), names):
            t = t.upper()
            x = 4 if face == "8x8" else 4 - (4 * len(t) - (6 * len(t) - 1) // 2)     # (both left-aligned)
            pix = FACES[face](t, x, 4)
            w = 8 * len(t) + 8
            rows.append((face, n, t, pix, w))
    W = max(r[4] for r in rows)
    lh = 12
    cga = Image.new("RGB", (W, lh * len(rows)))
    herc = Image.new("RGB", (2 * W, lh * len(rows)))
    for i, (face, n, t, pix, w) in enumerate(rows):
        for (x, y), ink in pix.items():
            if 0 <= x < W:
                cga.putpixel((x, i * lh + y), B.CGA1[ink])
                pr = B.herc_pair(ink, i * lh + y, x)
                for b in range(2):
                    if (pr >> (1 - b)) & 1:
                        herc.putpixel((2 * x + b, i * lh + y), (235, 235, 235))
    cga = cga.resize((W * z, cga.height * z), Image.NEAREST)
    herc = herc.resize((W * z, herc.height * z), Image.NEAREST)
    img = Image.new("RGB", (160 + cga.width + herc.width + 48, cga.height + 60), (48, 48, 56))
    d = ImageDraw.Draw(img)
    d.text((16, 10), "The titles: today's 8 x 8 label face (fonts/tallx.f8) and the 5 x 7 small caps (os88cdart.py), "
           "%dx; CGA left, Hercules right" % z, fill=(255, 255, 255), font=_font(16))
    for i, (face, n, t, pix, w) in enumerate(rows):
        d.text((16, 44 + i * lh * z + 6), "%s  %d" % (face, n), fill=(200, 200, 200), font=_font(14))
    img.paste(cga, (160, 44))
    img.paste(herc, (160 + cga.width + 24, 44))
    p = os.path.join(out, "titles.png")
    img.save(p)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "bonanza-pathway"))
    ap.add_argument("--only")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    keys = a.only.split(",") if a.only else sorted(OPTIONS)
    base = costs(today())
    print("today (BZROLL=1): RAM %(ram)d, stored %(stored)d, LZ4 %(lz4)d, LZB %(lzb)d; picture %(pic)d, %(blocks)d "
          "blocks; %(kinds)s" % base)
    items = []
    for key in keys:
        o = OPTIONS[key]
        try:
            pc, prf = compile_option(key, o)
        except B.CourseError as e:
            print("option %s: REFUSED: %s" % (key, e))
            continue
        cost = costs(pc)
        print("option %s (%s): RAM %d, stored %d, LZ4 %d, LZB %d; picture %d, %d blocks; %s"
              % (key, o["name"], cost["ram"], cost["stored"], cost["lz4"], cost["lzb"], cost["pic"],
                 cost["blocks"], cost["kinds"]))
        for ln in prf + pc.path_bounds:
            print("    " + ln)
        p, cga = sheet(key, o, pc, cost, base, a.out)
        print("    " + p)
        items.append((key, o, cga, cost))
    if len(items) > 1:
        print(overview(items, a.out))
    print(title_faces(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
