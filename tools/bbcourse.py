#!/usr/bin/env python3
"""BONANZA's course compiler, wave 1 (SPEC.md 128.10.3 - 128.10.7).

    python3 tools/bbcourse.py -o DIR COURSE.bbc ...        # what `make` runs: every
                                                          # course, in BZ_COURSES's order
    python3 tools/bbcourse.py --selfcheck [COURSE.bbc ...] # SPEC.md 128.10.4.6
    python3 tools/bbcourse.py COURSE.bbc --png DIR         # previews (Pillow, behind a try)

A course is TEXT (`apps/bonanza/courses/*.bbc`, SPEC.md 128.10.3).  ONE run
compiles the whole list: course K (its place on the command line) becomes
the two PARTS `BZ<K>C.BIN` (CGA) and `BZ<K>H.BIN` (Hercules), each a `BZC1`
part carrying the picture (a flat map of absolute block offsets and the
deduplicated 8 x 8 blocks), the occluder records and masks, and the `BZG1`
physics grid (SPEC.md 128.10.5); and the same run writes `bzcourse.inc`
WHOLE - `BZ_NCRS`, each course's name and title, and the `OS88_PART` rows of
every course part (SPEC.md 128.10.6.1).  A stamp, `.bz-crs`, holding a hash
of this tool, of tools/bonanza_assets.py (whose palette and Hercules encoders
it imports) and of every course file, is written FIRST.

Deterministic (the same inputs give the same bytes), standard library only,
integer geometry throughout (Fraction where a ramp's height at a pixel is a
ratio).  The renderer MOVED here from tools/bonanza_assets.py (SPEC.md
128.10.4); the palette, `cga_bytes`, `herc_pair` and `herc_bytes` are
IMPORTED from there, so a course and the ball cannot disagree about a
mid-level pixel.

The run checks what it wrote, at BUILD time (packages are trusted, so the
guest does not): `read_part` re-reads every part as the guest would and
refuses a bad magic, offset, count, map word, OCCIDX, ROWTAB row, mask
offset or route, naming the course and the field.

`Physics` is SPEC.md 128.10.7.3's step, integer-exact: the guest's
bzphys.inc is written to do exactly what it does, and the bonanzaphys row
compares the two at every frame of the benchmark.

Host reference for the rows (import this module):
    compile_course(path_or_text)    -> Course: .pic (the CGA picture, a list of
                                       bytearray rows), .cga/.herc (the parts),
                                       .sbuf/.tbuf (the per-pixel cell row and
                                       top), .records, .by_block, .cells,
                                       .reach, .x0, .y0, .route ...
    read_part(bytes)                -> the parsed part (and its build checks)
    Grid(part).cell(wx, wy)         -> (z0, sx, sy, kind, flags), OPEN outside
    Physics(course, play=False)     -> the model: .step(keys), .step_auto(),
                                       .poke(wx, wy, gvx, gvy), the guest's
                                       state as .gx .gy .gz .gvx .gvy .gvz .air
                                       .nstep ..., the screen state .bx .by .vx
                                       .vy, and .events
    laid_at(course, px, py, sb, zb, air)   the records the guest's pass lays
    composite(course, px, py, sb, zb, air) the ball over the picture with the
                                       occluders laid back through the RECORDS
                                       (the ring's oracle, SPEC.md 128.10.11.3)
"""
import argparse
import hashlib
import math
import os
import re
import struct
import sys
from array import array
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bonanza_assets as BA                      # noqa: E402
from bonanza_assets import BLK, CYN, MAG, WHT, CGA1, cga_bytes, herc_pair, herc_bytes   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.abspath(__file__)
COURSE_DIR = os.path.join(ROOT, "apps", "bonanza", "courses")

# --- formats (SPEC.md 128.10.5) -----------------------------------------------
HDR = 32                      # BZC1's header
GHDR = 32                     # BZG1's header
PARTMAX = 0xFE00              # 65,024: one part (SPEC.md 20.12.11's OP_PARTMAX)
MINLINES = 200                # a picture is at least the CGA field
# SPEC.md 128.10.4.4's bounds are 24 records a block row and 8 laid at any
# reachable position.  PROVISIONAL: the contract's own two courses need more
# under its own reachable set - FIRST (its worked example) 32 a row and 23
# laid, BENCH 79 and 29: the NEAR void round every back edge and pit, from the
# kill height to the apex, sees one record for each (block, cell row, band)
# in front of it, up to three cell rows a block.  Until the owner rules (a
# second OCCIDX level, a narrower reachable set, a pass that lays a block once
# with its records' masks ANDed, or these numbers), the refusals stand at:
REC_ROW_MAX = 96
REC_LAID_MAX = 32
REC_ROW_CONTRACT, REC_LAID_CONTRACT = 24, 8
BAND = 2                      # a record's tops span at most 2 px

KIND_VOID, KIND_FLOOR, KIND_WALL, KIND_GOAL = 0, 1, 2, 3
FL_SAFE, FL_OCC = 1, 2
Z_OPEN = -128                 # an OPEN cell's z0

# --- the world (SPEC.md 128.10.2) ---------------------------------------------
TILE = 16                     # ground units a tile
FACE8 = 24                    # a face over the void hangs 3 units (24 px)
BALL_D = BA.D                 # 16
FOOT_W, FOOT_H = 20, 16       # the footprint the boxes cover (SPEC.md 128.4)

# --- physics v1 (SPEC.md 128.10.7.2), PROVISIONAL -----------------------------
ACCG = 4                      # 1/256 gu a step a step, each arrow on each axis
GSL = 4                       # ... a half unit a tile of slope
G = 24                        # 1/256 px a step a step
VMAXG = 384                   # |gvx|, |gvy| (per axis)
VZMAX = 768                   # |gvz|
RAD = 6                       # the ball's radius on the ground, gu
CLIMB = 4                     # px: the highest step rolled UP
STICK = 1                     # px
STEP_PIT = 21845              # PIT counts a step (FASTTICK sub-tick)
PIT_HZ = 1193182

# the autopilot, SPEC.md 128.6 (bzgame.inc's bz_auto, unchanged)
AUTO_ACC = 8                  # BZ_ACC: its threshold is BZ_ACC / 2
AUTO_VMAX = 512               # BZ_VMAX
AUTO_REACH = 12               # BZ_REACH
K_L, K_R, K_U, K_D = 1, 2, 4, 8   # bz_keys

RESERVED = ("surface", "edge", "prop", "tube", "checkpoint", "pad", "shape", "ball")


class CourseError(Exception):
    pass


# =============================================================================
# the text course (SPEC.md 128.10.3)
# =============================================================================

_NAME = re.compile(r"^[A-Z0-9]{1,5}$")
_HEIGHT = re.compile(r"^-?\d+(\.[05])?$")
_INT = re.compile(r"^-?\d+$")


def _tokens(line, where):
    """split a line on spaces, honouring one "quoted" string; '#' starts a
    comment outside quotes"""
    out = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c in " \t\r":
            i += 1
            continue
        if c == "#":
            break
        if c == '"':
            j = line.find('"', i + 1)
            if j < 0:
                raise CourseError("%s: an unterminated quoted string" % where)
            out.append(('"', line[i + 1:j]))
            i = j + 1
            continue
        j = i
        while j < n and line[j] not in " \t\r#\"":
            j += 1
        out.append(('w', line[i:j]))
        i = j
    return out


class Room:
    def __init__(self, style, tiles, height, line):
        self.style = style          # 'floor' | 'wall' | 'goal' | None (a hole)
        self.tiles = tiles          # a frozenset of (wx, wy)
        self.height = height        # ('flat', h2) | ('ramp', axis, p0, p1, h0_2, r)
        self.line = line


class Source:
    """a parsed course: statements in order, nothing derived"""

    def __init__(self, fname):
        self.fname = fname
        self.name = self.title = None
        self.width = None
        self.origin = None
        self.rooms = []
        self.holes = []
        self.start = None           # ((wx, wy), line)
        self.ways = []              # [((wx, wy), line)]


def _int(tok, where, what):
    if tok[0] != 'w' or not _INT.match(tok[1]):
        raise CourseError("%s: %s must be an integer, not %r" % (where, what, tok[1]))
    v = int(tok[1])
    if not -4096 <= v <= 4096:
        raise CourseError("%s: %s %d is out of any course's reach" % (where, what, v))
    return v


def _height2(tok, where):
    """a height in units, a multiple of 0.5 from -60 to 63.5 -> half units"""
    if tok[0] != 'w' or not _HEIGHT.match(tok[1]):
        raise CourseError("%s: height %r is not a whole number of half units" % (where, tok[1]))
    s = tok[1]
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    whole, _, frac = s.partition(".")
    h2 = 2 * int(whole) + (1 if frac == "5" else 0)
    if neg:
        h2 = -h2
    if not -120 <= h2 <= 127:
        raise CourseError("%s: height %s is out of range (-60 to 63.5 units)" % (where, tok[1]))
    return h2


def _shape(toks, i, where):
    """-> (frozenset of tiles, the next token index)"""
    if i >= len(toks):
        raise CourseError("%s: a shape is missing (tile, rect or band)" % where)
    kind = toks[i][1]
    if kind == "tile":
        if i + 3 > len(toks):
            raise CourseError("%s: tile needs <wx> <wy>" % where)
        wx, wy = _int(toks[i + 1], where, "wx"), _int(toks[i + 2], where, "wy")
        return frozenset([(wx, wy)]), i + 3
    if kind == "rect":
        if i + 5 > len(toks):
            raise CourseError("%s: rect needs <x0> <y0> <x1> <y1>" % where)
        x0, y0, x1, y1 = (_int(toks[i + k], where, "rect") for k in range(1, 5))
        if x1 <= x0 or y1 <= y0:
            raise CourseError("%s: rect %d %d %d %d is empty" % (where, x0, y0, x1, y1))
        return frozenset((x, y) for x in range(x0, x1) for y in range(y0, y1)), i + 5
    if kind == "band":
        if i + 5 > len(toks):
            raise CourseError("%s: band needs <a0> <a1> <s0> <s1>" % where)
        a0, a1, s0, s1 = (_int(toks[i + k], where, "band") for k in range(1, 5))
        if a1 < a0 or s1 <= s0:
            raise CourseError("%s: band %d %d %d %d is empty" % (where, a0, a1, s0, s1))
        out = set()
        for s in range(s0, s1):
            for a in range(a0, a1 + 1):
                if (s + a) & 1 == 0:
                    out.add(((s + a) // 2, (s - a) // 2))
        return frozenset(out), i + 5
    raise CourseError("%s: unknown shape %r (tile, rect or band)" % (where, kind))


def _heightspec(toks, i, where):
    if i >= len(toks):
        raise CourseError("%s: a height is missing (flat or ramp)" % where)
    kind = toks[i][1]
    if kind == "flat":
        if i + 2 != len(toks):
            raise CourseError("%s: flat takes one height" % where)
        return ("flat", _height2(toks[i + 1], where))
    if kind == "ramp":
        if i + 6 != len(toks):
            raise CourseError("%s: ramp takes x|y|s <p0> <p1> <h0> <h1>" % where)
        axis = toks[i + 1][1]
        if axis not in ("x", "y", "s"):
            raise CourseError("%s: a ramp's axis is x, y or s, not %r" % (where, axis))
        p0, p1 = _int(toks[i + 2], where, "p0"), _int(toks[i + 3], where, "p1")
        h0, h1 = _height2(toks[i + 4], where), _height2(toks[i + 5], where)
        if p0 == p1:
            raise CourseError("%s: a ramp's p0 and p1 must differ" % where)
        num, den = h1 - h0, p1 - p0           # r = 2 (h1 - h0) / (p1 - p0), half units
        if num % den:
            raise CourseError("%s: ramp rate %d/%d is not a whole number of half units a tile"
                              % (where, num, den))
        r = num // den
        lim = 2 if axis == "s" else 4
        if abs(r) > lim:
            raise CourseError("%s: ramp rate %d half units a tile is past the %s ramp's limit of %d"
                              % (where, r, axis, lim))
        return ("ramp", axis, p0, p1, h0, r)
    raise CourseError("%s: unknown height %r (flat or ramp)" % (where, kind))


def parse(text, fname="<course>"):
    src = Source(fname)
    for ln, raw in enumerate(text.split("\n"), 1):
        where = "%s:%d" % (fname, ln)
        if any(ord(c) > 126 or (ord(c) < 32 and c not in "\t\r") for c in raw):
            raise CourseError("%s: not plain ASCII" % where)
        toks = _tokens(raw, where)
        if not toks:
            continue
        if toks[0][0] != 'w':
            raise CourseError("%s: a statement cannot start with a string" % where)
        st = toks[0][1]
        if st in RESERVED:
            raise CourseError("%s: '%s' is reserved for a later wave" % (where, st))
        if st == "course":
            if src.name is not None:
                raise CourseError("%s: a second 'course' statement" % where)
            if len(toks) != 3 or toks[1][0] != 'w' or toks[2][0] != '"':
                raise CourseError('%s: course takes <NAME> "<title>"' % where)
            if not _NAME.match(toks[1][1]):
                raise CourseError("%s: course name %r is not 1-5 of A-Z 0-9" % (where, toks[1][1]))
            title = toks[2][1]
            if not 1 <= len(title) <= 24 or any(q in title for q in "\"'`"):
                raise CourseError("%s: the title must be 1 - 24 characters, no quote marks" % where)
            src.name, src.title = toks[1][1], title
        elif st == "width":
            if src.width is not None:
                raise CourseError("%s: a second 'width' statement" % where)
            if len(toks) != 2 or toks[1][1] not in ("64", "128"):
                raise CourseError("%s: width is 64 or 128" % where)
            src.width = int(toks[1][1])
        elif st == "origin":
            if src.origin is not None or len(toks) != 2:
                raise CourseError("%s: origin takes one <X0>, once" % where)
            x0 = _int(toks[1], where, "origin")
            if x0 % 16:
                raise CourseError("%s: origin %d is not a multiple of 16" % (where, x0))
            src.origin = (x0, ln)
        elif st in ("floor", "wall", "goal"):
            tiles, i = _shape(toks, 1, where)
            src.rooms.append(Room(st, tiles, _heightspec(toks, i, where), ln))
        elif st == "hole":
            tiles, i = _shape(toks, 1, where)
            if i != len(toks):
                raise CourseError("%s: hole takes a shape and nothing else" % where)
            src.holes.append((tiles, ln))
        elif st in ("start", "way"):
            if len(toks) != 3:
                raise CourseError("%s: %s takes <wx> <wy>" % (where, st))
            t = (_int(toks[1], where, "wx"), _int(toks[2], where, "wy"))
            if st == "start":
                if src.start is not None:
                    raise CourseError("%s: a second 'start'" % where)
                src.start = (t, ln)
            else:
                src.ways.append((t, ln))
        else:
            raise CourseError("%s: unknown statement '%s'" % (where, st))
    for what, v in (("course", src.name), ("width", src.width), ("start", src.start)):
        if v is None:
            raise CourseError("%s: no '%s' statement" % (fname, what))
    return src


# =============================================================================
# tiles (SPEC.md 128.10.3's table)
# =============================================================================

class Tile:
    __slots__ = ("kind", "z0", "sx", "sy", "line")

    def __init__(self, kind, z0, sx, sy, line):
        self.kind, self.z0, self.sx, self.sy, self.line = kind, z0, sx, sy, line

    def corner(self, dx, dy):
        """corner (wx + dx, wy + dy), half units"""
        return self.z0 + self.sx * dx + self.sy * dy

    def corners(self):
        """(top, right, bottom, left) in half units"""
        return (self.z0, self.z0 + self.sx, self.z0 + self.sx + self.sy, self.z0 + self.sy)


_KIND = {"floor": KIND_FLOOR, "wall": KIND_WALL, "goal": KIND_GOAL}


def _room_tile(room, wx, wy):
    h = room.height
    if h[0] == "flat":
        z0, sx, sy = h[1], 0, 0
    else:
        _, axis, p0, p1, h0, r = h
        p = wx if axis == "x" else wy if axis == "y" else wx + wy
        z0 = h0 + r * (p - p0)
        sx = r if axis in ("x", "s") else 0
        sy = r if axis in ("y", "s") else 0
    return Tile(_KIND[room.style], z0, sx, sy, room.line)


def build_tiles(src):
    tiles = {}
    for room in src.rooms:
        for (wx, wy) in room.tiles:
            tiles[(wx, wy)] = _room_tile(room, wx, wy)
    for hole, _ in src.holes:
        for t in hole:
            tiles.pop(t, None)
    f = src.fname
    for (wx, wy) in sorted(tiles):
        t = tiles[(wx, wy)]
        if not (3 <= wx <= 252 and 3 <= wy <= 252):
            raise CourseError("%s:%d: tile (%d, %d) is solid outside 3 .. 252" % (f, t.line, wx, wy))
        for c in t.corners():
            if not -120 <= c <= 127:
                raise CourseError("%s:%d: tile (%d, %d) has a corner at %s units, out of range"
                                  % (f, t.line, wx, wy, c / 2))
    # a wall must look like one: above every floor that shares an edge with it
    for (wx, wy) in sorted(tiles):
        t = tiles[(wx, wy)]
        if t.kind != KIND_WALL:
            continue
        for dx, dy, mine, theirs in ((1, 0, ((1, 0), (1, 1)), ((0, 0), (0, 1))),
                                     (-1, 0, ((0, 0), (0, 1)), ((1, 0), (1, 1))),
                                     (0, 1, ((0, 1), (1, 1)), ((0, 0), (1, 0))),
                                     (0, -1, ((0, 0), (1, 0)), ((0, 1), (1, 1)))):
            n = tiles.get((wx + dx, wy + dy))
            if n is None or n.kind == KIND_WALL:
                continue
            if not all(t.corner(*m) > n.corner(*o) for m, o in zip(mine, theirs)):
                raise CourseError("%s:%d: wall (%d, %d) is not above the floor (%d, %d) beside it"
                                  % (f, t.line, wx, wy, wx + dx, wy + dy))
    return tiles


# =============================================================================
# the grid's cells (SPEC.md 128.10.4.3)
# =============================================================================

def _cheb(tiles, wx, wy, r):
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            t = tiles.get((wx + dx, wy + dy))
            if t is not None:
                yield t


def build_cells(tiles):
    """-> {(wx, wy): [z0, slopes byte, kind byte, flags]} for every cell that is
    not OPEN: the solid ones and the NEAR void"""
    cells = {}
    near = set()
    for (wx, wy) in tiles:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if (wx + dx, wy + dy) not in tiles:
                    near.add((wx + dx, wy + dy))
    for (wx, wy), t in tiles.items():
        flags = 0
        if t.kind == KIND_FLOOR and t.sx == 0 and t.sy == 0 and all(
                (wx + dx, wy + dy) in tiles for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            flags |= FL_SAFE
        cells[(wx, wy)] = [t.z0, (t.sx & 15) | ((t.sy & 15) << 4), t.kind, flags]
    for (wx, wy) in near:
        low = min(min(t.corners()) for t in _cheb(tiles, wx, wy, 2))
        cells[(wx, wy)] = [low - 6, 0, KIND_VOID, 0]
    return cells


def _nib(v):
    return v - 16 if v & 8 else v


# =============================================================================
# the reachable set (SPEC.md 128.10.4.1)
# =============================================================================

def _launch(t):
    """the height a ball leaving tile t at BZ_VMAXG can rise, px (ceiling)"""
    u = (abs(t.sx) + abs(t.sy)) * VMAXG // 4         # 1/256 px a step
    return -((-u * u) // (2 * 256 * G))


class Reach:
    __slots__ = ("wx", "wy", "s", "a", "zlo", "zhi", "kind", "src")

    def __init__(self, wx, wy, zlo, zhi, kind, src):
        self.wx, self.wy = wx, wy
        self.s, self.a = wx + wy, wx - wy
        self.zlo, self.zhi, self.kind, self.src = zlo, zhi, kind, src


def build_reach(tiles, cells):
    """-> [Reach]: every cell a contact point can be in, its lowest and highest
    whole px, and which cell's launch set the highest"""
    out = []
    for (wx, wy) in sorted(cells):
        z0, _, kind, _ = cells[(wx, wy)]
        if kind == KIND_WALL:
            continue
        if kind == KIND_VOID:
            zlo = 4 * z0
        else:
            zlo = 4 * min(tiles[(wx, wy)].corners())
        zhi, src = zlo, None
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                t = tiles.get((wx + dx, wy + dy))
                if t is None or t.kind == KIND_WALL:
                    continue
                h = 4 * max(t.corners()) + _launch(t)
                if h > zhi:
                    zhi, src = h, (wx + dx, wy + dy)
        out.append(Reach(wx, wy, zlo, zhi, kind, src))
    return out


def foot_x(rc, x0):
    """the footprint columns over a cell's area: [lo, hi] inclusive"""
    return 16 * rc.a + x0 - 24, 16 * rc.a + x0 + 23


def foot_top(rc, z):
    """the footprint's top line at Y0 = 0 for a ball in rc at whole height z,
    its centre at the top of the cell's ground range"""
    return 8 * rc.s - z - 13


# =============================================================================
# the renderer (moved from tools/bonanza_assets.py, SPEC.md 128.3, 128.10.4.1)
# =============================================================================

def _scr(cx2, cy2, z8, x0):
    """corner in HALF tile units and pixel height -> quarter-pixel screen, Y0 = 0"""
    return ((cx2 - cy2) * 32 + 4 * x0, (cx2 + cy2) * 16 - 4 * z8)


def _ceil_div(n, d):
    return -((-n) // d)


def spans(poly):
    """Pixels whose centre is inside a simple polygon of quarter-pixel integer
    vertices: {row: [(x0, x1), ...]} half-open runs, even-odd rule."""
    ys = [p[1] for p in poly]
    out = {}
    n = len(poly)
    for y in range(min(ys) // 4, _ceil_div(max(ys), 4) + 1):
        yc = 4 * y + 2
        xs = []
        for i in range(n):
            xa, ya = poly[i]
            xb, yb = poly[(i + 1) % n]
            if (ya <= yc) == (yb <= yc):
                continue
            dd = yb - ya
            nn = xa * dd + (xb - xa) * (yc - ya)
            if dd < 0:
                nn, dd = -nn, -dd
            xs.append(_ceil_div(nn - 2 * dd, 4 * dd))
        xs.sort()
        runs = [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2) if xs[i] < xs[i + 1]]
        if runs:
            out[y] = runs
    return out


def _inside(runs, x):
    for a, b in runs or ():
        if a <= x < b:
            return True
    return False


def _shift(sp, dy):
    return {y + dy: r for y, r in sp.items()}


class Canvas:
    """the picture, and for every pixel the cell row s that drew it last
    (-32768: none) and that geometry's height there, whole px (floor)"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rows = [bytearray(w) for _ in range(h)]
        self.sbuf = [array("h", [-32768]) * w for _ in range(h)]
        self.tbuf = [array("h", [0]) * w for _ in range(h)]

    def fill(self, sp, colour, s, top):
        """colour: an index or (x, y) -> index; top: (x, y) -> whole px"""
        for y, runs in sp.items():
            if not 0 <= y < self.h:
                raise CourseError("course pixel line %d outside the %d-line picture" % (y, self.h))
            row, sr, tr = self.rows[y], self.sbuf[y], self.tbuf[y]
            for a, b in runs:
                if a < 0 or b > self.w:
                    raise CourseError("course pixels %d .. %d outside the %d px picture" % (a, b, self.w))
                for x in range(a, b):
                    row[x] = colour(x, y) if callable(colour) else colour
                    sr[x] = s
                    tr[x] = top(x, y)

    def outline(self, sp, left=False):
        for y, runs in sp.items():
            above = sp.get(y - 1)
            row = self.rows[y]
            for a, b in runs:
                for x in range(a, b):
                    if not _inside(above, x) or (left and x == a):
                        row[x] = BLK


def _top_fn(t, wx, wy, x0, y0):
    """a top's floor height at a pixel centre, whole px (floor): the plane of
    tile t inverted through the projection (SPEC.md 128.10.2)"""
    zt = 4 * t.z0
    if t.sx == 0 and t.sy == 0:
        return lambda x, y: zt
    S = t.sx + t.sy
    if S == 4:                                  # edge-on: it draws no pixel
        return lambda x, y: 4 * max(t.corners())
    sx, sy = t.sx, t.sy

    def top(x, y):
        A = Fraction(4 * x + 2 - 4 * x0, 4)
        B = Fraction(4 * y + 2 - 4 * y0, 4)
        K = B + zt - 4 * (sx * wx + sy * wy) + Fraction(sx - sy, 8) * A
        b = 8 * K / (4 - S)
        return math.floor(b / 2 - B)
    return top


def _face_fn(xp4, zp, xq4, zq):
    """a face's top edge at a pixel's column, whole px (floor)"""
    den = xq4 - xp4

    def top(x, y):
        num = zp * den + (zq - zp) * (4 * x + 2 - xp4)
        d = den
        if d < 0:
            num, d = -num, -d
        return num // d
    return top


def draw_ops(tiles, x0):
    """-> [(spans at Y0 = 0, colour, s, top-maker, outline-left, tile)], back
    to front: each tile's two front faces, then its top (128.3's order)"""
    ops = []
    for (wx, wy) in sorted(tiles, key=lambda t: (t[0] + t[1], t[0])):
        t = tiles[(wx, wy)]
        zt, zr, zb, zl = (4 * c for c in t.corners())
        s = wx + wy
        T = (2 * wx, 2 * wy)
        R = (2 * wx + 2, 2 * wy)
        B = (2 * wx + 2, 2 * wy + 2)
        L = (2 * wx, 2 * wy + 2)
        sw = tiles.get((wx, wy + 1))
        se = tiles.get((wx + 1, wy))
        faces = (
            (L, zl, B, zb, (4 * sw.corner(0, 0), 4 * sw.corner(1, 0)) if sw else None, "sw"),
            (B, zb, R, zr, (4 * se.corner(0, 1), 4 * se.corner(0, 0)) if se else None, "se"),
        )
        for p, zp, q, zq, nb, which in faces:
            if nb is None:
                lp, lq = zp - FACE8, zq - FACE8
            else:
                lp, lq = min(zp, nb[0]), min(zq, nb[1])
            if lp >= zp and lq >= zq:
                continue
            poly = [_scr(p[0], p[1], zp, x0), _scr(q[0], q[1], zq, x0),
                    _scr(q[0], q[1], lq, x0), _scr(p[0], p[1], lp, x0)]
            mk = (lambda xp4, zp_, xq4, zq_: lambda y0: _face_fn(xp4, zp_, xq4, zq_))(
                poly[0][0], zp, poly[1][0], zq)
            ops.append((spans(poly), which, s, mk, True, t, (wx, wy)))
        quad = [_scr(T[0], T[1], zt, x0), _scr(R[0], R[1], zr, x0),
                _scr(B[0], B[1], zb, x0), _scr(L[0], L[1], zl, x0)]
        mk = (lambda tt, a, b: lambda y0: _top_fn(tt, a, b, x0, y0))(t, wx, wy)
        ops.append((spans(quad), "top", s, mk, False, t, (wx, wy)))
    return ops


def _top_subquads(t, wx, wy, x0):
    """a ramp's or a goal's finer 2 x 2 checker: four sub-quads (spans at Y0 = 0, ink)"""
    zt, zr, zb, zl = (4 * c for c in t.corners())
    T = (2 * wx, 2 * wy, zt)
    R = (2 * wx + 2, 2 * wy, zr)
    B = (2 * wx + 2, 2 * wy + 2, zb)
    L = (2 * wx, 2 * wy + 2, zl)

    def m(a, b):
        return ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2, (a[2] + b[2]) // 2)
    mtr, mrb, mbl, mlt = m(T, R), m(R, B), m(B, L), m(L, T)
    c = (2 * wx + 1, 2 * wy + 1, (zt + zr + zb + zl) // 4)
    inks = (WHT, BLK) if t.kind == KIND_GOAL else (CYN, WHT)
    out = []
    for corners, k in (((T, mtr, c, mlt), 0), ((mtr, R, mrb, c), 1),
                       ((c, mrb, B, mbl), 0), ((mlt, c, mbl, L), 1)):
        out.append((spans([_scr(v[0], v[1], v[2], x0) for v in corners]), inks[k]))
    return out


def render(tiles, ops, x0, y0, w, h):
    cv = Canvas(w, h)
    for sp0, which, s, mk, left, t, (wx, wy) in ops:
        sp = _shift(sp0, y0)
        top = mk(y0)
        if which == "sw":
            cv.fill(sp, MAG, s, top)
            cv.outline(sp, left=True)
        elif which == "se":
            cv.fill(sp, lambda x, y: MAG if (x + y) & 1 == 0 else BLK, s, top)
            cv.outline(sp, left=True)
        else:
            if t.kind == KIND_WALL:
                cv.fill(sp, WHT, s, top)
            elif t.kind == KIND_GOAL or t.sx or t.sy:
                cv.fill(sp, BLK, s, top)            # the ground and the keys...
                for sub, ink in _top_subquads(t, wx, wy, x0):
                    sub = _shift(sub, y0)
                    for y, runs in sub.items():     # ...then the checker's inks
                        row = cv.rows[y]
                        for a, b in runs:
                            for x in range(a, b):
                                row[x] = ink
            else:
                cv.fill(sp, WHT if (wx + wy) & 1 else CYN, s, top)
            cv.outline(sp)
    return cv


# =============================================================================
# blocks, occluders, the grid, the part (SPEC.md 128.10.4.2 - 128.10.5)
# =============================================================================

class Course:
    """everything one course compiles to; .cga and .herc are the parts"""


def _blocks(pic, cols, brows):
    blocks = [bytes(64)]
    index = {blocks[0]: 0}
    mp = []
    for by in range(brows):
        rows = pic[by * 8:by * 8 + 8]
        for bx in range(cols):
            blk = b"".join(bytes(r[bx * 8:bx * 8 + 8]) for r in rows)
            n = index.get(blk)
            if n is None:
                n = index[blk] = len(blocks)
                blocks.append(blk)
            mp.append(n)
    return blocks, mp


def _occluders(cv, reach, x0, y0, cols, brows):
    """-> (records, occ pixel set): SPEC.md 128.10.4.4.  A pixel is an occluder
    when SOME reachable position's footprint covers it and the rule lays it
    back there: the ball's cell row before the pixel's, and the ball lower
    than the pixel's top (airborne, so the margin is 0: the most it can lay).
    Records: one per (block, cell, band of tops at most BAND px)."""
    occ = {}                                   # (x, y) -> (s, top)
    w, h = cv.w, cv.h
    for rc in reach:
        xl, xh = foot_x(rc, x0)
        xl, xh = max(xl, 0), min(xh, w - 1)
        ytop = foot_top(rc, rc.zhi) + y0
        ybot = foot_top(rc, rc.zlo) + y0 + 15 + 15
        for y in range(max(ytop, 0), min(ybot, h - 1) + 1):
            sr, tr = cv.sbuf[y], cv.tbuf[y]
            for x in range(xl, xh + 1):
                sp = sr[x]
                if sp <= rc.s:
                    continue
                tp = tr[x]
                zmax = min(rc.zhi, tp - 1)       # the highest ball the pixel still hides
                if zmax < rc.zlo:
                    continue
                # above every footprint low enough - a ball at whole height zmax
                # with a FRACTION (any zmax below the apex) has its top a line
                # higher than foot_top(zmax) at the cell row's first line
                if y < foot_top(rc, zmax) + y0 - (1 if zmax < rc.zhi else 0):
                    continue
                occ[(x, y)] = (sp, tp)
    # group: block, cell row (one cell per row per block column is not
    # guaranteed, so the key is the cell's row AND the drawing tile), band
    groups = {}
    for (x, y), (sp, tp) in occ.items():
        key = (y >> 3, x >> 3, sp)
        groups.setdefault(key, []).append((tp, x, y))
    records = []
    for (br, bc, sp) in sorted(groups):
        px = sorted(groups[(br, bc, sp)])
        band = []
        for p in px:
            if band and p[0] - band[0][0] > BAND:
                records.append((br, bc, sp, band))
                band = []
            band.append(p)
        records.append((br, bc, sp, band))
    out = []
    for br, bc, sp, band in records:
        top = max(p[0] for p in band)
        mask = bytearray(b"\xff" * 16)
        for _, x, y in band:
            ly, lx = y & 7, x & 7
            bi = 2 * ly + (lx >> 2)
            mask[bi] &= ~(3 << (6 - 2 * (lx & 3))) & 0xFF
        out.append({"brow": br, "col": bc, "s": sp, "top": top, "mask": bytes(mask),
                    "pix": frozenset((x, y) for _, x, y in band)})
    out.sort(key=lambda r: (r["brow"], r["col"], r["s"], r["top"], r["mask"]))
    return out, occ


def _laid(reach, recs_by_block, x0, y0, rc_list=None):
    """-> ({cell: most records laid at any of its positions}, worst (n, cell, z))"""
    best = {}
    worst = (0, None, None)
    for rc in (rc_list or reach):
        xl, xh = foot_x(rc, x0)
        cand = []
        for br in range((foot_top(rc, rc.zhi) + y0) >> 3, ((foot_top(rc, rc.zlo) + y0 + 30) >> 3) + 1):
            for bc in range(xl >> 3, (xh >> 3) + 1):
                for r in recs_by_block.get((br, bc), ()):
                    if r["s"] > rc.s and r["top"] > rc.zlo:
                        cand.append(r)
        n_best = 0
        if cand:
            p4s = range(16 * rc.a + x0 - 24, 16 * rc.a + x0 + 5, 4)
            for z in range(rc.zlo, rc.zhi + 1):
                live = [r for r in cand if r["top"] > z]
                if not live:
                    break
                t0 = foot_top(rc, z) + y0
                # (t0 - 1: whole height z with a fraction, below the apex)
                for py in range(t0 - (1 if z < rc.zhi else 0), t0 + 16):
                    rows = (py >> 3, (py + 15) >> 3)
                    for p4 in p4s:
                        c0, c1 = p4 >> 3, (p4 + 19) >> 3
                        n = sum(1 for r in live if rows[0] <= r["brow"] <= rows[1] and c0 <= r["col"] <= c1)
                        if n > n_best:
                            n_best = n
                            if n > worst[0]:
                                worst = (n, (rc.wx, rc.wy), z)
        best[(rc.wx, rc.wy)] = n_best
    return best, worst


def compile_course(source, fname=None, occluders=True):
    """source: a path, or the text itself (with fname for messages).
    occluders=False cuts no records (a host model that wants only the grid)"""
    if fname is None:
        ab = os.path.abspath(source)
        fname = os.path.relpath(ab, ROOT) if ab.startswith(ROOT + os.sep) else source
        with open(source, "r", encoding="ascii", newline="") as f:
            text = f.read()
    else:
        text = source
    src = parse(text, fname)
    tiles = build_tiles(src)
    if not tiles:
        raise CourseError("%s: no solid tile" % fname)
    cells = build_cells(tiles)
    reach = build_reach(tiles, cells)
    width = src.width * 8
    x0 = src.origin[0] if src.origin else src.width * 4
    # the start: SAFE
    (swx, swy), sln = src.start
    sc = cells.get((swx, swy))
    if sc is None or not sc[3] & FL_SAFE:
        raise CourseError("%s:%d: start (%d, %d) is not SAFE (a flat floor with four solid edge neighbours)"
                          % (fname, sln, swx, swy))
    for (wx, wy), ln in src.ways:
        t = tiles.get((wx, wy))
        if t is None or t.kind == KIND_WALL:
            raise CourseError("%s:%d: way (%d, %d) is on a %s tile" % (
                fname, ln, wx, wy, "WALL" if t else "VOID"))
    # every footprint inside the width (before any pixel: footprints are wider)
    for rc in reach:
        xl, xh = foot_x(rc, x0)
        if xl < 0 or xh >= width:
            raise CourseError("%s: cell (%d, %d)'s footprint (px %d .. %d) is past the %d px width"
                              % (fname, rc.wx, rc.wy, xl, xh, width))
    ops = draw_ops(tiles, x0)
    gtop = min(min(sp) for sp, *_ in ops if sp)
    gbot = max(max(sp) for sp, *_ in ops if sp)
    ftop = min(foot_top(rc, rc.zhi) for rc in reach)
    y0 = max(-gtop, -ftop)
    fbot = max(foot_top(rc, rc.zlo) + 30 for rc in reach)
    lines = max(gbot, fbot) + y0 + 1
    lines = max(MINLINES, (lines + 7) // 8 * 8)
    cols, brows = src.width, lines // 8
    cv = render(tiles, ops, x0, y0, width, lines)
    pic = cv.rows
    # the blocks and the map
    blocks, mp = _blocks(pic, cols, brows)
    # the grid's shape
    live = sorted(cells)
    ss = [wx + wy for wx, wy in live]
    aa = [wx - wy for wx, wy in live]
    smin, smax = min(ss), max(ss)
    amin = min(aa) & ~1
    kw = ((max(aa) - amin) >> 1) + 1
    nrows = smax - smin + 1
    least = (HDR + 2 * cols * brows + 16 * len(blocks) + 2 * (brows + 1) + GHDR
             + 4 * nrows * kw + 2 * nrows + 4 * len(src.ways))
    if least > PARTMAX:
        raise CourseError("%s: the course part is at least %d bytes before any occluder, over the %d "
                          "one part may be, by %d" % (fname, least, PARTMAX, least - PARTMAX))
    # the occluders
    records, occpix = _occluders(cv, reach, x0, y0, cols, brows) if occluders else ([], {})
    per_row = {}
    for r in records:
        per_row[r["brow"]] = per_row.get(r["brow"], 0) + 1
    for br in sorted(per_row):
        if per_row[br] > REC_ROW_MAX:
            raise CourseError("%s: block row %d (lines %d - %d) has %d occluder records, over %d"
                              % (fname, br, 8 * br, 8 * br + 7, per_row[br], REC_ROW_MAX))
    by_block = {}
    for r in records:
        by_block.setdefault((r["brow"], r["col"]), []).append(r)
    laid, worst = _laid(reach, by_block, x0, y0)
    if worst[0] > REC_LAID_MAX:
        raise CourseError("%s: a ball in cell (%d, %d) at %d px lays %d occluder records, over %d"
                          % (fname, worst[1][0], worst[1][1], worst[2], worst[0], REC_LAID_MAX))
    for (wx, wy), n in laid.items():
        if n:
            cells[(wx, wy)][3] |= FL_OCC
    # the route: the ball's picture top-left on each way tile's centre
    route = []
    for (wx, wy), ln in src.ways:
        t = tiles[(wx, wy)]
        sx_ = 16 * (wx - wy) + x0
        sy_ = 8 * (wx + wy) + 8 - (4 * t.z0 + 2 * (t.sx + t.sy)) + y0
        route.append((sx_ - 8, sy_ - 13))
    # ---- the part -----------------------------------------------------------
    mapoff = HDR
    blkoff = mapoff + 2 * cols * brows
    occidx = blkoff + 16 * len(blocks)
    occrec = occidx + 2 * (brows + 1)
    masks = []
    mindex = {}
    for r in records:
        if r["mask"] not in mindex:
            mindex[r["mask"]] = len(masks)
            masks.append(r["mask"])
    maskoff = occrec + 8 * len(records)
    gridoff = maskoff + 16 * len(masks)
    celloff = gridoff + GHDR
    rowtab = celloff + 4 * nrows * kw
    routeoff = rowtab + 2 * nrows
    end = routeoff + 4 * len(route)
    if end > PARTMAX:
        raise CourseError("%s: the course part is %d bytes, over the %d one part may be, by %d"
                          % (fname, end, PARTMAX, end - PARTMAX))
    hdr = b"BZC1" + struct.pack("<13H", cols, brows, len(blocks), 4 if cols == 64 else 5, blkoff,
                                occidx, occrec, len(records), maskoff, len(masks), 2 * cols,
                                gridoff, 0) + struct.pack("<H", 0)
    assert len(hdr) == HDR
    mapb = b"".join(struct.pack("<H", blkoff + 16 * n) for n in mp)
    idx = bytearray()
    ri = 0
    for br in range(brows + 1):
        while ri < len(records) and records[ri]["brow"] < br:
            ri += 1
        idx += struct.pack("<H", occrec + 8 * ri)
    recb = b"".join(struct.pack("<BBHhH", r["col"], 0, r["s"], r["top"], maskoff + 16 * mindex[r["mask"]])
                    for r in records)
    grid = bytearray(b"BZG1" + struct.pack("<HhhHHHhH", nrows, smin, amin, kw, rowtab, x0, y0, 0)
                     + struct.pack("<HHHH", swx, swy, len(route), routeoff) + bytes(4))
    assert len(grid) == GHDR
    for r in range(nrows):
        s = smin + r
        for k in range(kw):
            a = amin + 2 * k + (s & 1)
            wx, wy = (s + a) >> 1, (s - a) >> 1
            c = cells.get((wx, wy))
            if c is None:
                grid += struct.pack("<bBBB", Z_OPEN, 0, KIND_VOID, 0)
            else:
                grid += struct.pack("<bBBB", c[0], c[1], c[2], c[3])
    for r in range(nrows):
        grid += struct.pack("<H", celloff + 4 * kw * r)
    for (bx, by) in route:
        grid += struct.pack("<HH", bx, by)
    common_head = hdr + mapb
    tail = bytes(idx) + recb + b"".join(masks) + bytes(grid)
    cga = bytearray(common_head)
    herc = bytearray(common_head)
    for blk in blocks:
        for y in range(8):
            line = blk[y * 8:y * 8 + 8]
            cga += cga_bytes(line)
            herc += herc_bytes(line, line=y, col0=0)
    cga += tail
    herc += tail
    assert len(cga) == len(herc) == end
    c = Course()
    c.fname, c.name, c.title = fname, src.name, src.title
    c.src, c.tiles, c.cells, c.reach = src, tiles, cells, reach
    c.x0, c.y0, c.width, c.lines, c.cols, c.brows = x0, y0, width, lines, cols, brows
    c.pic, c.sbuf, c.tbuf = pic, cv.sbuf, cv.tbuf
    c.blocks, c.map = blocks, mp
    c.records, c.occpix, c.by_block = records, occpix, by_block
    c.masks = masks
    c.laid, c.worst = laid, worst
    c.per_row = per_row
    c.route = route
    c.start = (swx, swy)
    c.cga, c.herc = bytes(cga), bytes(herc)
    c.gtop, c.ftop = gtop, ftop
    c.part = read_part(c.cga, fname)
    read_part(c.herc, fname)
    if c.part["grid"]["cells_raw"] != read_part(c.herc, fname)["grid"]["cells_raw"]:
        raise CourseError("%s: the two parts' grids differ" % fname)
    return c


# =============================================================================
# the reader: what the guest reads, checked (SPEC.md 128.10.4, 128.10.5)
# =============================================================================

def read_part(p, fname="<part>"):
    def bad(field, why):
        raise CourseError("%s: part field %s: %s" % (fname, field, why))

    n = len(p)
    if n < HDR or p[:4] != b"BZC1":
        bad("magic", "not BZC1")
    if n > PARTMAX:
        bad("length", "%d over %d" % (n, PARTMAX))
    (cols, brows, nblk, mapsh, blkoff, occidx, occrec, nocc, maskoff, nmask, rowb, gridoff,
     propoff) = struct.unpack_from("<13H", p, 4)
    nprop = struct.unpack_from("<H", p, 30)[0]
    if cols not in (64, 128):
        bad("COLS", str(cols))
    if mapsh != (4 if cols == 64 else 5):
        bad("MAPSH", str(mapsh))
    if rowb != 2 * cols:
        bad("ROWB", "%d, not 2 COLS" % rowb)
    if brows < 25:
        bad("BROWS", str(brows))
    if blkoff != HDR + 2 * cols * brows:
        bad("BLKOFF", str(blkoff))
    if occidx != blkoff + 16 * nblk:
        bad("OCCIDX", "offset %d" % occidx)
    if occrec != occidx + 2 * (brows + 1):
        bad("OCCREC", str(occrec))
    if maskoff != occrec + 8 * nocc:
        bad("MASKOFF", str(maskoff))
    if gridoff != maskoff + 16 * nmask:
        bad("GRIDOFF", str(gridoff))
    if propoff or nprop:
        bad("PROPOFF", "props are wave 3's")
    if gridoff + GHDR > n:
        bad("GRIDOFF", "past the part")
    # the map: every word a block offset inside the part
    mp = struct.unpack_from("<%dH" % (cols * brows), p, HDR)
    for i, w in enumerate(mp):
        if w < blkoff or w >= occidx or (w - blkoff) % 16:
            bad("map[%d]" % i, "word %d is not a block offset" % w)
    if p[blkoff:blkoff + 16] != bytes(16):
        bad("block 0", "not black")
    idx = struct.unpack_from("<%dH" % (brows + 1), p, occidx)
    if idx[-1] != maskoff or idx[0] != occrec:
        bad("OCCIDX", "does not run from the first record to the records' end")
    for i in range(brows):
        if idx[i + 1] < idx[i] or (idx[i] - occrec) % 8:
            bad("OCCIDX[%d]" % i, "decreasing or not a record")
    recs = []
    for i in range(nocc):
        col, z, s, top, moff = struct.unpack_from("<BBHhH", p, occrec + 8 * i)
        if col >= cols or z:
            bad("record %d" % i, "column %d" % col)
        if moff < maskoff or moff + 16 > gridoff or (moff - maskoff) % 16:
            bad("record %d" % i, "mask offset %d" % moff)
        recs.append((col, s, top, moff))
    for br in range(brows):
        row = recs[(idx[br] - occrec) // 8:(idx[br + 1] - occrec) // 8]
        if [r[:2] for r in row] != sorted(r[:2] for r in row):
            bad("records of block row %d" % br, "not sorted by column, then s")
    g = gridoff
    if p[g:g + 4] != b"BZG1":
        bad("BZG1", "magic")
    nrows, smin, amin, kw, rowtab, x0, y0, z1 = struct.unpack_from("<HhhHHHhH", p, g + 4)
    swx, swy, nway, routeoff = struct.unpack_from("<HHHH", p, g + 20)
    if z1 or p[g + 28:g + 32] != bytes(4):
        bad("BZG1", "reserved bytes")
    if amin & 1:
        bad("AMIN", "odd")
    celloff = g + GHDR
    if rowtab != celloff + 4 * nrows * kw:
        bad("ROWTAB", "offset %d" % rowtab)
    rt = struct.unpack_from("<%dH" % nrows, p, rowtab)
    for r, o in enumerate(rt):
        if o < celloff or o + 4 * kw > rowtab:
            bad("ROWTAB[%d]" % r, "row outside the cells")
    if routeoff != rowtab + 2 * nrows or routeoff + 4 * nway != n:
        bad("route", "offset %d, %d ways" % (routeoff, nway))
    route = [struct.unpack_from("<HH", p, routeoff + 4 * i) for i in range(nway)]
    for (bx, by) in route:
        if bx + FOOT_W > 8 * cols or by + FOOT_H > 8 * brows:
            bad("route", "point (%d, %d) outside the picture" % (bx, by))
    for i in range(nrows * kw):
        z0, sl, kd, fl = struct.unpack_from("<bBBB", p, celloff + 4 * i)
        if kd > KIND_GOAL or fl & ~(FL_SAFE | FL_OCC):
            bad("cell %d" % i, "kind %d flags %d" % (kd, fl))
    return {"cols": cols, "brows": brows, "nblk": nblk, "mapsh": mapsh, "blkoff": blkoff,
            "occidx": occidx, "occrec": occrec, "nocc": nocc, "maskoff": maskoff, "nmask": nmask,
            "rowb": rowb, "gridoff": gridoff, "map": mp, "idx": idx, "recs": recs,
            "grid": {"nrows": nrows, "smin": smin, "amin": amin, "kw": kw, "rowtab": rt,
                     "x0": x0, "y0": y0, "start": (swx, swy), "route": route,
                     "cells_raw": bytes(p[celloff:rowtab]), "celloff": celloff}}


class Grid:
    """the BZG1 grid as the guest reads it, from a part's bytes"""

    def __init__(self, part_bytes):
        self.p = part_bytes
        info = read_part(part_bytes)
        g = info["grid"]
        self.nrows, self.smin, self.amin, self.kw = g["nrows"], g["smin"], g["amin"], g["kw"]
        self.rowtab = g["rowtab"]
        self.x0, self.y0 = g["x0"], g["y0"]
        self.start, self.route = g["start"], g["route"]

    def cell(self, wx, wy):
        """-> (z0, sx, sy, kind, flags); OPEN outside the grid"""
        r = wx + wy - self.smin
        k = (wx - wy - self.amin) >> 1
        if r < 0 or r >= self.nrows or k < 0 or k >= self.kw:
            return (Z_OPEN, 0, 0, KIND_VOID, 0)
        z0, sl, kd, fl = struct.unpack_from("<bBBB", self.p, self.rowtab[r] + 4 * k)
        return (z0, _nib(sl & 15), _nib(sl >> 4), kd & 15, fl)


# =============================================================================
# physics v1 (SPEC.md 128.10.7.3): the guest does exactly this
# =============================================================================

def _isqrt_round(n):
    return (math.isqrt(4 * n) + 1) // 2


def corner_table():
    """36 entries (|du| 0..5, |dv| 0..5, row-major by |du|), three signed bytes
    each: nx, ny (the unit normal from the corner to the centre, x 64) and the
    push depth in 1/16 gu (BZ_RAD less the distance), or three zeros where
    du^2 + dv^2 >= 36 (no contact).  (0, 0) takes the diagonal."""
    out = []
    for du in range(6):
        for dv in range(6):
            d2 = du * du + dv * dv
            if d2 >= RAD * RAD:
                out.append((0, 0, 0))
                continue
            if d2 == 0:
                nx = ny = 45
            else:
                d = math.sqrt(d2)
                nx = int(math.floor(64 * du / d + 0.5))
                ny = int(math.floor(64 * dv / d + 0.5))
            depth = 16 * RAD - _isqrt_round(256 * d2)
            out.append((nx, ny, depth))
    return out


CORNER = corner_table()


def _drag(v):
    a = (abs(v) + 63) >> 6
    v = v + a if v < 0 else v - a
    return v


def _clamp(v, m):
    return m if v > m else -m if v < -m else v


def _s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class Physics:
    """The ball, SPEC.md 128.10.7.  Positions are integers in 1/256 (24.8):
    gx, gy in gu, gz in px.  play: the goal counts.  The red-arm switches
    exist for --selfcheck's negative controls and nothing else."""

    def __init__(self, course, play=False, _slope_sign=1, _takeoff_zero=False):
        part = course.cga if isinstance(course, Course) else course
        self.grid = Grid(part)
        self.play = play
        self._slope_sign = _slope_sign
        self._takeoff_zero = _takeoff_zero
        self.x0, self.y0 = self.grid.x0, self.grid.y0
        self.route = self.grid.route
        self.nstep = self.nfall = self.nland = 0
        self.goal = 0
        self.lfall = self.lvz = 0
        self.ztop = 0
        self.safe = self.grid.start
        self.wp = 1                            # bz_play: waypoint 0 is the start
        self.events = []
        self._place(*self.grid.start)
        self.bx = self.by = 0
        self._derive(True)

    # -- the grid ------------------------------------------------------------
    def cell(self, wx, wy):
        return self.grid.cell(wx, wy)

    @staticmethod
    def h4(c, u, v):
        return 16 * c[0] + c[1] * u + c[2] * v

    def blocks(self, c, u, v):
        """does neighbour c block the ball at its point (u, v)?  Against the
        STEP'S START z (grounded, the move leaves z alone; airborne, a floor
        the ball was above when the step began is one it lands on, not a wall:
        128.10.7.3's fallback rule, applied to the circle too)"""
        if c[3] == KIND_WALL:
            return True
        if c[3] in (KIND_FLOOR, KIND_GOAL):
            h = self.h4(c, u, v) << 6
            return h > self.zs + (CLIMB << 8 if not self.air else 0)
        return False

    # -- the state -----------------------------------------------------------
    def _place(self, wx, wy):
        self.gx = (16 * wx + 8) << 8
        self.gy = (16 * wy + 8) << 8
        c = self.cell(wx, wy)
        self.gz = self.h4(c, 8, 8) << 6
        self.gvx = self.gvy = self.gvz = 0
        self.air = 0

    def poke(self, wx, wy, gvx=0, gvy=0):
        """a scenario's start: the centre of tile (wx, wy) on its floor,
        grounded, at a ground velocity (the rows' POKED scenarios do the same
        through the guest's variables)"""
        self._place(wx, wy)
        self.gvx, self.gvy = gvx, gvy
        self._derive(True)
        return self

    def _respawn(self):
        self._place(*self.safe)
        self.nfall += 1
        self.respawned = True
        self.events.append(("respawn", self.nstep + 1, self.safe))

    def _derive(self, zero):
        nbx = self.gx - self.gy + ((self.x0 - 8) << 8)
        nby = ((self.gx + self.gy) >> 1) - self.gz + ((self.y0 - 13) << 8)
        if zero:
            self.vx = self.vy = 0
        else:
            self.vx = _s16(nbx - self.bx)
            self.vy = _s16(nby - self.by)
        self.bx, self.by = nbx, nby

    @property
    def px(self):
        return self.bx >> 8

    @property
    def py(self):
        return self.by >> 8

    @property
    def zb(self):
        return self.gz >> 8

    @property
    def sb(self):
        return (self.gx >> 12) + (self.gy >> 12)

    def state(self):
        return (self.nstep, self.gx, self.gy, self.gz, self.gvx, self.gvy, self.gvz, self.air)

    # -- the autopilot (bz_auto, SPEC.md 128.6) -------------------------------
    def auto(self):
        nway = len(self.route)
        while True:
            wx, wy = self.route[self.wp]
            dx = wx - (self.bx >> 8)
            dy = wy - (self.by >> 8)
            if self.wp >= nway - 1:
                break
            if abs(dx) < AUTO_REACH and abs(dy) < AUTO_REACH:
                self.wp += 1
                continue
            break
        keys = 0
        ax = _clamp(8 * dx, AUTO_VMAX) - self.vx
        if ax > AUTO_ACC // 2:
            keys |= K_R
        elif ax < -(AUTO_ACC // 2):
            keys |= K_L
        ay = _clamp(8 * dy, AUTO_VMAX) - self.vy
        if ay > AUTO_ACC // 2:
            keys |= K_D
        elif ay < -(AUTO_ACC // 2):
            keys |= K_U
        return keys

    def step_auto(self):
        self.step(self.auto())

    # -- the step --------------------------------------------------------------
    def step(self, keys=0):
        self.respawned = False
        cwx, cwy = self.gx >> 12, self.gy >> 12
        C = self.cell(cwx, cwy)
        # 2. forces
        if not self.air:
            A = ACCG
            if keys & K_R:
                self.gvx += A
                self.gvy -= A
            if keys & K_L:
                self.gvx -= A
                self.gvy += A
            if keys & K_D:
                self.gvx += A
                self.gvy += A
            if keys & K_U:
                self.gvx -= A
                self.gvy -= A
            sx, sy = (C[1], C[2]) if C[3] in (KIND_FLOOR, KIND_GOAL) else (0, 0)
            self.gvx -= self._slope_sign * GSL * sx
            self.gvy -= self._slope_sign * GSL * sy
            self.gvx = _clamp(_drag(self.gvx), VMAXG)
            self.gvy = _clamp(_drag(self.gvy), VMAXG)
            self.gvz = (sx * self.gvx + sy * self.gvy) >> 2
        else:
            self.gvz = _clamp(self.gvz - G, VZMAX)
        # 3. move
        sgx, sgy, sgz = self.gx, self.gy, self.gz
        self.zs = sgz
        scell = (cwx, cwy)
        self.gx += self.gvx
        self.gy += self.gvy
        if self.air:
            self.gz += self.gvz
            self.ztop = max(self.ztop, self.gz >> 8)
        # 4. the window
        cwx, cwy = self.gx >> 12, self.gy >> 12
        C = self.cell(cwx, cwy)
        if C[3] == KIND_VOID and C[0] == Z_OPEN:
            self._respawn()
            return self._end()
        # 5. walls: the circle
        u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
        if u < RAD:
            if self.blocks(self.cell(cwx - 1, cwy), 16, v):
                self.gx = (16 * cwx + RAD) << 8
                if self.gvx < 0:
                    self.gvx = 0
        elif u > 16 - RAD:
            if self.blocks(self.cell(cwx + 1, cwy), 0, v):
                self.gx = (16 * cwx + 16 - RAD) << 8
                if self.gvx > 0:
                    self.gvx = 0
        if v < RAD:
            if self.blocks(self.cell(cwx, cwy - 1), u, 16):
                self.gy = (16 * cwy + RAD) << 8
                if self.gvy < 0:
                    self.gvy = 0
        elif v > 16 - RAD:
            if self.blocks(self.cell(cwx, cwy + 1), u, 0):
                self.gy = (16 * cwy + 16 - RAD) << 8
                if self.gvy > 0:
                    self.gvy = 0
        u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
        if (u < RAD or u > 16 - RAD) and (v < RAD or v > 16 - RAD):
            dx = -1 if u < RAD else 1
            dy = -1 if v < RAD else 1
            du = u if dx < 0 else u - 16
            dv = v if dy < 0 else v - 16
            nx, ny, depth = CORNER[abs(du) * 6 + abs(dv)]
            if depth and self.blocks(self.cell(cwx + dx, cwy + dy), 16 if dx < 0 else 0, 16 if dy < 0 else 0):
                nx = -nx if dx > 0 else nx
                ny = -ny if dy > 0 else ny
                mx, my = (depth * abs(nx)) >> 2, (depth * abs(ny)) >> 2
                self.gx += mx if nx >= 0 else -mx
                self.gy += my if ny >= 0 else -my
                dot = (self.gvx * nx + self.gvy * ny) >> 6
                if dot < 0:
                    self.gvx -= (dot * nx) >> 6
                    self.gvy -= (dot * ny) >> 6
                self.events.append(("corner", self.nstep + 1, (du, dv)))
        # the fallback
        cwx, cwy = self.gx >> 12, self.gy >> 12
        if (cwx, cwy) != scell:
            C = self.cell(cwx, cwy)
            u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
            blk = C[3] == KIND_WALL
            if C[3] in (KIND_FLOOR, KIND_GOAL):
                h = self.h4(C, u, v) << 6
                blk = h > sgz + (0 if self.air else CLIMB << 8)
            if blk:
                if cwx != scell[0]:
                    self.gvx = 0
                if cwy != scell[1]:
                    self.gvy = 0
                self.gx, self.gy, self.gz = sgx, sgy, sgz
                cwx, cwy = scell
                self.events.append(("undo", self.nstep + 1, None))
        # 6. the floor
        C = self.cell(cwx, cwy)
        u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
        solid = C[3] in (KIND_FLOOR, KIND_GOAL)
        h = (self.h4(C, u, v) << 6) if solid else None
        if not self.air:
            if not solid or h < self.gz + self.gvz - G - (STICK << 8):
                self.air = 1
                if self._takeoff_zero:
                    self.gvz = 0
                self.ztop = self.gz >> 8
                self.gz += self.gvz
                self.events.append(("takeoff", self.nstep + 1, self.gvz))
            else:
                self.gz = h
        else:
            if solid and self.gz <= h:
                self.lvz = -self.gvz
                self.lfall = max(0, self.ztop - (h >> 8))
                self.gz = h
                self.gvz = 0
                self.air = 0
                self.nland += 1
                self.events.append(("land", self.nstep + 1, (self.lfall, self.lvz)))
            elif C[3] == KIND_VOID and self.gz < (4 * C[0]) << 8:
                self._respawn()
                return self._end()
        # 8. SAFE and the goal
        if not self.air:
            if C[4] & FL_SAFE:
                self.safe = (cwx, cwy)
            if C[3] == KIND_GOAL and self.play:
                if not self.goal:
                    self.events.append(("goal", self.nstep + 1, None))
                self.goal = 1
        return self._end()

    def _end(self):
        self.nstep += 1
        self._derive(self.respawned)
        return self


# =============================================================================
# the composite: the ball over the picture, the occluders laid back
# =============================================================================

def ball_pixels(px, py):
    """the ball at top-left (px, py): {(x, y): index} for its lit pixels"""
    f = (py & 7) * 8 + (px & 7)
    out = {}
    for r, row in enumerate(BA.ball_frame_indices(f)):
        for x, c in enumerate(row):
            if c is not None:
                out[(px + x, py + r)] = c
    return out


def composite(course, px, py, sb, zb, air, via="records"):
    """the footprint (20 x 16 from px & ~3) with the ball drawn and 128.10.4.4's
    rule applied: via 'records' (what the guest does), 'pixels' (the per-pixel
    buffer, each pixel's top raised to its record's) or 'none' (the ball whole:
    what the guest draws when its OCC gate is off, 128.10.8 item 1).
    -> {(x, y): index}"""
    m = 0 if air else CLIMB
    x4 = px & ~3
    out = {}
    for y in range(py, py + FOOT_H):
        for x in range(x4, x4 + FOOT_W):
            out[(x, y)] = course.pic[y][x]
    for p, c in ball_pixels(px, py).items():
        out[p] = c
    if via == "records":
        for br in range(py >> 3, ((py + FOOT_H - 1) >> 3) + 1):
            for bc in range(x4 >> 3, ((x4 + FOOT_W - 1) >> 3) + 1):
                for r in course.by_block.get((br, bc), ()):
                    if sb < r["s"] and zb + m < r["top"]:
                        for (x, y) in r["pix"]:
                            if (x, y) in out:
                                out[(x, y)] = course.pic[y][x]
    elif via == "pixels":
        raised = course._raised
        for (x, y) in list(out):
            s = course.sbuf[y][x]
            if s == -32768:
                continue
            top = raised.get((x, y), course.tbuf[y][x])
            if sb < s and zb + m < top:
                out[(x, y)] = course.pic[y][x]
    return out


def _raised_tops(course):
    d = {}
    for r in course.records:
        for p in r["pix"]:
            d[p] = r["top"]
    return d


# =============================================================================
# the outputs
# =============================================================================

def emit_inc(courses):
    lines = [
        "; bzcourse.inc - GENERATED by tools/bbcourse.py (SPEC.md 128.10.4, 128.10.6.1).",
        "; Do not edit: change a course under apps/bonanza/courses/ (the Makefile's",
        "; BZ_COURSES, in order) and rebuild.  Course K's parts are rows 2 + 2K (CGA)",
        "; and 3 + 2K (Hercules), after the ball's two (bonanza.asm).",
        "",
        "BZ_NCRS         equ %d        ; courses, BZ_COURSES's order" % len(courses),
        "BZ_P_CRS        equ 2        ; course 0's CGA row; course K's is BZ_P_CRS + 2K",
        "BZ_CRS_NAMEB    equ 6        ; BZ_CRS_NAMES: a row, the NAME NUL-padded",
        "BZ_CRS_TITLEB   equ 25       ; BZ_CRS_TITLES: a row, the title NUL-padded",
    ]
    for k, c in enumerate(courses):
        lines.append("BZ_CRS_%-8s equ %d        ; %s, \"%s\"" % (c.name, k, os.path.basename(c.fname), c.title))
    lines += ["", "%macro BZ_CRS_NAMES 0"]
    for c in courses:
        lines.append("    db '%s'%s" % (c.name, ", 0" * (6 - len(c.name))))
    lines += ["%endmacro", "", "%macro BZ_CRS_TITLES 0"]
    for c in courses:
        lines.append("    db '%s'%s" % (c.title, ", 0" * (25 - len(c.title))))
    lines += ["%endmacro", "",
              "; physics v1's constants (SPEC.md 128.10.7.2), the model's own: bzphys.inc",
              "; and bbcourse.Physics cannot disagree about them",
              "BZ_ACCG         equ %d        ; 1/256 gu a step a step, an arrow on an axis" % ACCG,
              "BZ_GSL          equ %d        ; ... a half unit a tile of slope" % GSL,
              "BZ_G            equ %d       ; 1/256 px a step a step" % G,
              "BZ_VMAXG        equ %d      ; |gvx|, |gvy|" % VMAXG,
              "BZ_VZMAX        equ %d      ; |gvz|" % VZMAX,
              "BZ_RAD          equ %d        ; gu" % RAD,
              "BZ_CLIMB        equ %d        ; px" % CLIMB,
              "BZ_STICK        equ %d        ; px" % STICK,
              "",
              "; the corner table (SPEC.md 128.10.7.3): 36 entries indexed 6 |du| + |dv|,",
              "; each |nx|, |ny| (x 64) and the push depth in 1/16 gu; zeros where",
              "; du^2 + dv^2 >= 36 (no contact)",
              "%macro BZ_CORNER_TABLE 0"]
    for i in range(0, 36, 6):
        lines.append("    db " + ", ".join("%d,%d,%d" % CORNER[i + k] for k in range(6)))
    lines += ["%endmacro", "",
              "; the course part rows: BZ_NCRS pairs, CGA then Hercules, every one",
              "; OP_ASSET | OP_LAZY | OP_COMP (SPEC.md 128.10.6.1)",
              "%macro BZ_CRS_PARTS 0",
              " %rep BZ_NCRS",
              "    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ<K>C.BIN",
              "    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ<K>H.BIN",
              " %endrep",
              "%endmacro", ""]
    return "\n".join(lines)


def stamp(paths):
    h = hashlib.sha256()
    for name, path in (("tools/bbcourse.py", TOOL),
                       ("tools/bonanza_assets.py", os.path.abspath(BA.__file__))):
        h.update(name.encode() + b"\0")
        with open(path, "rb") as f:
            h.update(f.read())
    for p in paths:
        h.update(os.path.basename(p).encode() + b"\0")
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def compile_all(paths):
    courses = [compile_course(p) for p in paths]
    names = [c.name for c in courses]
    if len(set(names)) != len(names):
        raise CourseError("two courses share a NAME: %s" % names)
    files = {}
    for k, c in enumerate(courses):
        files["BZ%dC.BIN" % k] = c.cga
        files["BZ%dH.BIN" % k] = c.herc
    return courses, files, {"bzcourse.inc": emit_inc(courses)}


def report(c, k=None):
    head = "course %s%s (%s, \"%s\")" % ("%d " % k if k is not None else "", c.name,
                                        os.path.basename(c.fname), c.title)
    nrec_max = max(c.per_row.values()) if c.per_row else 0
    g = c.part["grid"]
    print("  %s: %d x %d px (COLS %d, BROWS %d), X0 %d, Y0 %d" % (
        head, c.width, c.lines, c.cols, c.brows, c.x0, c.y0))
    print("    part %d bytes each card: header 32, map %d, blocks %d x 16 = %d, OCCIDX %d, "
          "records %d x 8 = %d, masks %d x 16 = %d, grid %d (%d rows x %d cells x 4 + %d header, "
          "ROWTAB %d, route %d)" % (
              len(c.cga), 2 * c.cols * c.brows, len(c.blocks), 16 * len(c.blocks), 2 * (c.brows + 1),
              len(c.records), 8 * len(c.records), len(c.masks), 16 * len(c.masks),
              len(c.cga) - c.part["gridoff"], g["nrows"], g["kw"], GHDR, 2 * g["nrows"], 4 * len(c.route)))
    print("    records: most %d in a block row (bound %d), most %d laid at a position (bound %d%s); "
          "%d OCC cells of %d reachable" % (
              nrec_max, REC_ROW_MAX, c.worst[0], REC_LAID_MAX,
              ", cell %s at %d px" % (c.worst[1], c.worst[2]) if c.worst[1] else "",
              sum(1 for v in c.cells.values() if v[3] & FL_OCC), len(c.reach)))


def write_out(out, paths):
    """compile every course IN MEMORY first: a refused course removes the
    stamp and writes nothing, so make cannot take a stale part for current"""
    os.makedirs(out, exist_ok=True)
    st = os.path.join(out, ".bz-crs")
    try:
        courses, files, texts = compile_all(paths)
    except CourseError:
        if os.path.exists(st):
            os.remove(st)
        raise
    # the stamp before the files: a run that dies writing leaves a stamp and a
    # missing file, which make's fallback turns back into a re-run
    with open(st, "w") as f:
        f.write(stamp(paths) + "\n")
    for name in sorted(files):
        with open(os.path.join(out, name), "wb") as f:
            f.write(files[name])
    for name in sorted(texts):
        with open(os.path.join(out, name), "w", newline="\n") as f:
            f.write(texts[name])
    for k, c in enumerate(courses):
        report(c, k)
    return courses


# =============================================================================
# --selfcheck (SPEC.md 128.10.4.6): every malformed input is a string HERE,
# so nothing under apps/ is a fixture
# =============================================================================

def _first_text():
    with open(os.path.join(COURSE_DIR, "first.bbc"), "r", encoding="ascii") as f:
        return f.read()


def _swap(text, old, new):
    assert old in text, old
    return text.replace(old, new, 1)


# (what it trips, the course text, a substring of the refusal)
def _grammar_cases():
    F = _first_text()
    B_LINE = "floor rect   7 4 11 7  ramp x 7 11 4 2"
    RIDGES = ('course T "t"\nwidth 64\nfloor band -9 9 20 44 flat 0\nfloor band -9 9 28 29 flat 3\n'
              'floor band -9 9 30 31 flat 6\nfloor band -9 9 32 33 flat 9\nstart 12 12\n')
    WEDGE = ('course T "t"\nwidth 64\nfloor rect 10 10 13 13 flat 30\nfloor rect 13 10 15 13 ramp x 13 15 30 32\n'
             'floor rect 10 13 13 15 ramp y 13 15 30 32\nfloor rect 13 13 15 15 ramp s 26 30 30 34\nstart 11 11\n')
    BIG = 'course BIG "Big"\nwidth 128\nfloor band -2 2 8 300 flat 0\nstart 5 5\n'
    return [
        ("a ramp rate that is not a whole half unit", _swap(F, B_LINE, "floor rect 7 4 11 7 ramp x 7 10 4 2"),
         "not a whole number of half units"),
        ("an x ramp at 5 half units a tile", _swap(F, B_LINE, "floor rect 7 4 11 7 ramp x 7 8 4 6.5"),
         "past the x ramp's limit of 4"),
        ("an s ramp at 3 half units a tile", _swap(F, B_LINE, "floor rect 7 4 11 7 ramp s 11 13 4 7"),
         "past the s ramp's limit of 2"),
        ("a height out of range", _swap(F, "flat 0             # C", "flat 64            # C"),
         "out of range"),
        ("a solid tile at wx = 2", F + "floor tile 2 5 flat 4\n", "solid outside 3 .. 252"),
        ("a wall no higher than a neighbouring floor", _swap(F, "wall  rect   3 3  7 4  flat 6", "wall rect 3 3 7 4 flat 4"),
         "is not above the floor"),
        ("a start that is not SAFE", _swap(F, "start 4 5", "start 8 5"), "is not SAFE"),
        ("a way on a VOID tile", F + "way 12 5\n", "is on a VOID tile"),
        ("a footprint past the width", _swap(F, "width  64\n", "width  64\norigin 64\n"), "past the 512 px width"),
        ("a reserved statement", F + "prop tile 4 4\n", "reserved for a later wave"),
        ("an unknown statement", F + "bogus 1 2\n", "unknown statement 'bogus'"),
        ("a part over 65,024 bytes", BIG, "one part may be"),
        ("a block row over %d records" % REC_ROW_MAX, RIDGES, "occluder records, over %d" % REC_ROW_MAX),
        ("a position laying over %d" % REC_LAID_MAX, WEDGE, "occluder records, over %d" % REC_LAID_MAX),
    ]


def _decode(part, herc):
    """an independent reader: the map and blocks back to game pixels (CGA) or
    to card pairs (Hercules)"""
    cols, brows = struct.unpack_from("<HH", part, 4)
    blkoff = struct.unpack_from("<H", part, 12)[0]
    occidx = struct.unpack_from("<H", part, 14)[0]
    rows = [bytearray(8 * cols) for _ in range(8 * brows)]
    for by in range(brows):
        for bx in range(cols):
            off = struct.unpack_from("<H", part, HDR + 2 * (by * cols + bx))[0]
            if off < blkoff or off >= occidx or (off - blkoff) % 16:
                raise CourseError("map word %d at (%d, %d) is not a block offset" % (off, bx, by))
            for y in range(8):
                w = part[off + 2 * y:off + 2 * y + 2]
                for x in range(8):
                    rows[by * 8 + y][bx * 8 + x] = (w[x >> 2] >> (6 - 2 * (x & 3))) & 3
    return rows


def laid_at(course, px, py, sb, zb, air):
    """the records the guest's pass lays for a ball at picture top-left (px, py)
    in cell row sb at whole height zb (SPEC.md 128.10.8 item 1)"""
    m = 0 if air else CLIMB
    x4 = px & ~3
    out = []
    for br in range(py >> 3, ((py + FOOT_H - 1) >> 3) + 1):
        for bc in range(x4 >> 3, ((x4 + FOOT_W - 1) >> 3) + 1):
            for r in course.by_block.get((br, bc), ()):
                if sb < r["s"] and zb + m < r["top"]:
                    out.append(r)
    return out


def _physics_checks(first, res):
    """item 7: scripted runs on FIRST against states written here, from
    SPEC.md 128.10.3's narrative; -> list of (what, ok)"""
    def ev(p, kind):
        return [e for e in p.events if e[0] == kind]

    def slope(**kw):
        p = Physics(first, **kw).poke(8, 5)
        for _ in range(20):
            p.step(0)
        return p.gvx > 0 and p.gvy == 0 and (p.gx, p.gvx, p.gvz) == (35446, 60, -15)

    def lip(**kw):
        p = Physics(first, **kw).poke(4, 6)
        for _ in range(130):
            p.step(K_R | K_D)
        return (ev(p, "takeoff") == [("takeoff", 105, -96)] and ev(p, "land") == [("land", 120, (16, 456))]
                and (p.lfall, p.lvz, p.nland) == (16, 456, 1))
    res.append(("7 FIRST: B's slope pulls a ball at rest downhill (+wx): after 20 steps gvx 60, gvz -15", slope()))
    p = Physics(first)
    contact = None
    for _ in range(80):
        g0 = (p.gvx, p.gvy)
        p.step(K_U)
        if p.gvy == 0 and g0[1] != 0:
            contact = (p.nstep, p.gy, p.gvx, g0)
            break
    res.append(("7 FIRST: Up drives it into the rail at step 60 and it SLIDES (gvy zeroed at v = 6, gvx kept, -133)",
                contact == (60, (16 * 4 + RAD) << 8, -133, (-132, -132))))
    p = Physics(first).poke(6, 4)
    got = None
    for _ in range(60):
        gy0 = p.gy
        p.step(K_R)
        if ev(p, "corner"):
            got = (p.nstep, ev(p, "corner")[0][2], p.gy - gy0, p.gvx, p.gvy)
            break
    res.append(("7 FIRST: Right from (6, 4): the rail's last cell (6, 3) is a corner neighbour and pushes the "
                "ball out along its normal (0, 1), 1 gu, at step 38", got == (38, (0, 5), 256 - 3, 97, 0)))
    res.append(("7 FIRST: B's lip: airborne at step 105 with the floor's gvz -96, lands on C at 120 with lfall 16, "
                "lvz 456", lip()))
    p = Physics(first)
    for _ in range(140):
        p.step(K_R | K_D)
    res.append(("7 FIRST: R+D from the start flies the lip into the pit (12, 5) and reappears on the last SAFE "
                "cell (6, 5) at step 131", ev(p, "respawn") == [("respawn", 131, (6, 5))] and p.nfall == 1
                and (p.gx >> 12, p.gy >> 12) == (6, 5) and not p.air))
    p = Physics(first).poke(3, 5, gvx=-VMAXG)
    trail = []
    for _ in range(40):
        p.step(0)
        trail.append((p.nstep, p.gz, p.gx >> 12, p.respawned))
        if p.respawned:
            break
    kill = 4 * Physics(first).cell(1, 5)[0] << 8
    res.append(("7 FIRST: poked off A's west side at the cap, it enters the OPEN cell (0, 5) at step 28 still above "
                "the NEAR band's kill height, and respawns at once",
                trail[-1][0] == 28 and trail[-1][3] and trail[-2][2] == 1 and trail[-2][1] > kill
                and p.cell(0, 5)[0] == Z_OPEN))
    p = Physics(first, play=True).poke(4, 6)
    for _ in range(130):
        p.step(K_R | K_D)
    q = Physics(first).poke(4, 6)
    for _ in range(130):
        q.step(K_R | K_D)
    res.append(("7 FIRST: the goal column sets the goal at step 125 in play; the benchmark ignores it",
                ev(p, "goal") == [("goal", 125, None)] and p.goal == 1 and q.goal == 0))
    res.append(("7 negative control: the slope term's sign flipped fails the slope run", not slope(_slope_sign=-1)))
    res.append(("7 negative control: the take-off's gvz zeroed fails the lip run", not lip(_takeoff_zero=True)))


BENCH_COVER = 12      # the route's waypoints the CGA's 1,093 steps must reach
CGA_STEPS, HERC_STEPS = 1093, 1289


def _way_point(c, t):
    """the ball's picture top-left on tile t's centre, on its floor (128.10.4.5)"""
    tl = c.tiles[t]
    return (16 * (t[0] - t[1]) + c.x0 - 8, 8 * (t[0] + t[1]) + 8 - (4 * tl.z0 + 2 * (tl.sx + tl.sy)) + c.y0 - 13)


def _route_checks(bench, res):
    """item 8: the benchmark's route under physics and the autopilot"""
    p = Physics(bench)
    reached = {}
    occ_steps = 0
    lays = []
    for i in range(HERC_STEPS):
        wp0 = p.wp
        p.step_auto()
        if p.wp != wp0:
            for k in range(wp0, p.wp):
                reached.setdefault(k, p.nstep)
        if i < CGA_STEPS:
            c = p.cell(p.gx >> 12, p.gy >> 12)
            if c[4] & FL_OCC:
                occ_steps += 1
                lays.append(len(laid_at(bench, p.px, p.py, p.sb, p.zb, p.air)))
        if i == CGA_STEPS - 1:
            cga_wp, cga_fall = p.wp, p.nfall
    # waypoint k is "reached" when the autopilot moves past it; the last
    # covered one is reached when the next is targeted
    ok = cga_fall == 0 and cga_wp >= BENCH_COVER - 1 and p.nfall == 0
    route = Grid(bench.cga).route
    res.append(("8 BENCH: the autopilot reaches the route's first %d waypoints in order within the CGA's %d "
                "steps (at %s) and falls nowhere in the Hercules's %d" % (
                    BENCH_COVER, CGA_STEPS, ", ".join(str(reached.get(k, "-")) for k in range(1, BENCH_COVER - 1)),
                    HERC_STEPS), ok and route[0] == bench.route[0] == _way_point(bench, bench.start)))
    n = len(lays)
    print("    BENCH over the CGA's %d steps: %d with the cell's OCC set (%.0f%%), records laid on those: mean "
          "%.2f, most %d; steps laying none %d" % (CGA_STEPS, n, 100.0 * n / CGA_STEPS,
                                                   (sum(lays) / n) if n else 0, max(lays) if lays else 0,
                                                   sum(1 for x in lays if x == 0)))


def selfcheck(paths=None):
    paths = paths or default_paths()
    res = []
    # 1. determinism
    a = compile_all(paths)
    b = compile_all(paths)
    same = all(a[1][k] == b[1][k] for k in a[1]) and a[2] == b[2] and sorted(a[1]) == sorted(b[1])
    res.append(("1 two compiles byte-identical, file for file (%s, bzcourse.inc)" % ", ".join(sorted(a[1])), same))
    courses = a[0]
    byname = {c.name: c for c in courses}
    for k, c in enumerate(courses):
        report(c, k)
    # 2. the grammar and the bounds
    for what, text, want in _grammar_cases():
        try:
            compile_course(text, fname="<%s>" % what)
            fired, msg = False, "compiled"
        except CourseError as e:
            fired, msg = want in str(e), str(e)
        res.append(("2 refused: %s%s" % (what, "" if fired else " -- got: " + msg), fired))
    for k, c in enumerate(courses):
        tag = "%s" % c.name
        # 3. the picture
        try:
            dc = _decode(c.cga, False)
            ok = all(bytes(dc[y]) == bytes(c.pic[y]) for y in range(c.lines))
            dh = _decode(c.herc, True)
            okh = True
            for y in range(c.lines):
                row, pic = dh[y], c.pic[y]
                for x in range(c.width):
                    if row[x] != herc_pair(pic[x], y & 7, x & 7):
                        okh = False
                        break
                if not okh:
                    break
        except CourseError as e:
            print("    " + str(e))
            ok = okh = False
        pt = c.part
        res.append(("3 %s: CGA map and blocks decode back to the picture; Hercules blocks are its CGA blocks by "
                    "herc_bytes; every map word a block offset inside the part; block 0 black; ROWB = 2 COLS" % tag,
                    ok and okh and pt["rowb"] == 2 * pt["cols"] and c.cga[pt["blkoff"]:pt["blkoff"] + 16] == bytes(16)
                    and c.herc[pt["blkoff"]:pt["blkoff"] + 16] == bytes(16)))
        bad = bytearray(c.cga)
        w0 = struct.unpack_from("<H", bad, HDR + 2 * 37)[0]
        alt = next(HDR + 2 * i for i, w in enumerate(pt["map"]) if w != w0)
        struct.pack_into("<H", bad, HDR + 2 * 37, struct.unpack_from("<H", bad, alt)[0])
        try:
            dd = _decode(bytes(bad), False)
            caught = any(bytes(dd[y]) != bytes(c.pic[y]) for y in range(c.lines))
        except CourseError:
            caught = True
        res.append(("3 %s negative control: one map word moved fails the decode" % tag, caught))
        # 4. the grid against the geometry
        g = Grid(c.cga)
        okp = okk = okv = oks = True
        for (wx, wy), t in c.tiles.items():
            cl = g.cell(wx, wy)
            zt, zr, zb, zl = (4 * v for v in t.corners())
            if zb != zr + zl - zt:
                okp = False
            for u in range(16):
                for v in range(16):
                    if 4 * (16 * zt + (zr - zt) * u + (zl - zt) * v) != 16 * Physics.h4(cl, u, v):
                        okp = False
            if cl[3] != t.kind:
                okk = False
            safe = (t.kind == KIND_FLOOR and t.sx == 0 and t.sy == 0
                    and all((wx + dx, wy + dy) in c.tiles for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
            if bool(cl[4] & FL_SAFE) != safe:
                oks = False
        for r in range(g.nrows):
            sR = g.smin + r
            for kk in range(-2, g.kw + 2):
                aC = g.amin + 2 * kk + (sR & 1)
                wx, wy = (sR + aC) >> 1, (sR - aC) >> 1
                if (wx, wy) in c.tiles:
                    continue
                cl = g.cell(wx, wy)
                near = [t for t in _cheb(c.tiles, wx, wy, 2)]
                want = (min(min(t.corners()) for t in near) - 6) if near else Z_OPEN
                if cl[3] != KIND_VOID or cl[0] != want or cl[4] & FL_SAFE:
                    okv = False
        res.append(("4 %s: at all 256 integer points of every solid cell h4 is the plane the renderer drew" % tag, okp))
        res.append(("4 %s: kinds are the rooms' styles; VOID is NEAR with the kill height or OPEN exactly where no "
                    "solid cell is within two tiles; SAFE exactly where 128.10.4.3 says; both parts' grids identical"
                    % tag, okk and okv and oks
                    and c.part["grid"]["cells_raw"] == read_part(c.herc)["grid"]["cells_raw"]))
        # 5. the occluders
        recs = c.records
        srt = all((x["brow"], x["col"], x["s"]) <= (y["brow"], y["col"], y["s"]) for x, y in zip(recs, recs[1:]))
        seen = set()
        dup = False
        span = 0
        for r in recs:
            if seen & r["pix"]:
                dup = True
            seen |= r["pix"]
            tops = [c.tbuf[y][x] for (x, y) in r["pix"]]
            span = max(span, max(tops) - min(tops))
            if r["top"] != max(tops) or any(c.sbuf[y][x] != r["s"] for (x, y) in r["pix"]):
                dup = True
        masks_unique = len(c.masks) == len(set(c.masks))
        res.append(("5 %s: OCCIDX non-decreasing to the records' end, records sorted, no pixel in two records, no "
                    "record's tops spanning over %d px (most %d), masks deduplicated (%d for %d records)"
                    % (tag, BAND, span, len(c.masks), len(recs)), srt and not dup and span <= BAND and masks_unique))
        c._raised = _raised_tops(c)
        mism = 0
        tried = 0
        first_laid = None
        for rc in c.reach:
            gx, gy = (16 * rc.wx + 8) << 8, (16 * rc.wy + 8) << 8
            for z in sorted({rc.zlo, rc.zhi}):
                for air in ((1,) if rc.kind == KIND_VOID else (0, 1)):
                    px = ((gx - gy) >> 8) + c.x0 - 8
                    py = (((gx + gy) >> 1) >> 8) - z + c.y0 - 13
                    tried += 1
                    A = composite(c, px, py, rc.s, z, air, "records")
                    Bp = composite(c, px, py, rc.s, z, air, "pixels")
                    if A != Bp:
                        mism += 1
                    if first_laid is None:
                        for r in laid_at(c, px, py, rc.s, z, air):
                            base = composite(c, px, py, rc.s, z, air, "pixels")
                            if any(p in r["pix"] and base[p] != v for p, v in ball_pixels(px, py).items()
                                   if p in base):
                                first_laid = (r, px, py, rc.s, z, air)
                                break
        res.append(("5 %s: the ball composited through the RECORDS equals the per-pixel buffer's (tops raised to the "
                    "records'), at the centre of every reachable cell, lowest and highest, both air states "
                    "(%d positions, %d differ)" % (tag, tried, mism), mism == 0))
        # the FRACTIONAL-height line: a ball at whole height z with a fraction
        # (z below the apex) and (gx + gy) / 2 at its cell row's first line
        # has its footprint top a line above foot_top(z) - the records must
        # composite as the pixels do there, and any record laid there must
        # have set the cell's OCC (the guest's gate skips the pass otherwise)
        fmism = fgate = ftried = 0
        fneg = None
        for rc in c.reach:
            if rc.zhi <= rc.zlo:
                continue
            for z in sorted({rc.zlo, rc.zhi - 1}):
                gx, gy, gz = (16 * rc.wx) << 8, (16 * rc.wy) << 8, (z << 8) + 128
                px = ((gx - gy) >> 8) + c.x0 - 8
                py = (((gx + gy) >> 1) - gz >> 8) + c.y0 - 13
                assert py == foot_top(rc, z) + c.y0 - 1
                for air in ((1,) if rc.kind == KIND_VOID else (0, 1)):
                    ftried += 1
                    if composite(c, px, py, rc.s, z, air, "records") != composite(c, px, py, rc.s, z, air, "pixels"):
                        fmism += 1
                    if laid_at(c, px, py, rc.s, z, air):
                        if not c.cells[(rc.wx, rc.wy)][3] & FL_OCC:
                            fgate += 1
                        elif fneg is None:
                            fneg = (rc, px, py, z, air)
        res.append(("5 %s: at the fractional-height line (z_b below the apex with a fraction, footprint top "
                    "foot_top - 1) the records composite as the pixels and every position that lays one is in an "
                    "OCC cell (%d positions, %d differ, %d ungated)" % (tag, ftried, fmism, fgate),
                    fmism == 0 and fgate == 0))
        if fneg is not None:
            rc, px, py, z, air = fneg
            cl = c.cells[(rc.wx, rc.wy)]
            cl[3] &= ~FL_OCC
            try:
                caught = bool(laid_at(c, px, py, rc.s, z, air)) and not cl[3] & FL_OCC
            finally:
                cl[3] |= FL_OCC
            res.append(("5 %s negative control: cell (%d, %d)'s OCC cleared is caught at its fractional-height line"
                        % (tag, rc.wx, rc.wy), caught))
        occ_ok = all(bool(v[3] & FL_OCC) == bool(c.laid.get(k_, 0)) for k_, v in c.cells.items()
                     if v[2] != KIND_WALL)
        res.append(("5 %s: OCC set exactly on the cells some position of which lays a record" % tag, occ_ok))
        if first_laid is not None:
            r, px, py, sb, z, air = first_laid
            old = r["s"]
            r["s"] = sb
            try:
                caught = composite(c, px, py, sb, z, air, "records") != composite(c, px, py, sb, z, air, "pixels")
            finally:
                r["s"] = old
            res.append(("5 %s negative control: one record's s_C lowered to the ball's row fails the composite" % tag,
                        caught))
        # 6. the bounds
        inside = True
        for rc in c.reach:
            xl, xh = foot_x(rc, c.x0)
            if xl < 0 or xh >= c.width or foot_top(rc, rc.zhi) + c.y0 < 0 or foot_top(rc, rc.zlo) + c.y0 + 30 >= c.lines:
                inside = False
        least = min(c.gtop, c.ftop) + c.y0
        top_rc = min(c.reach, key=lambda rc: foot_top(rc, rc.zhi))
        floors = [rc for rc in c.reach if rc.kind != KIND_VOID]
        fall = max(floors, key=lambda rc: rc.zhi - rc.zlo)
        void = max(c.reach, key=lambda rc: rc.zhi - rc.zlo)
        print("    %s: the least reachable footprint top is line %d: cell (%d, %d), a flight at %d px from the launch "
              "of cell %s; the geometry's top is line %d. Longest reachable fall onto a floor %d px (cell (%d, %d)), "
              "into a kill %d px (cell (%d, %d)); Y0 %d" % (
                  tag, c.ftop + c.y0, top_rc.wx, top_rc.wy, top_rc.zhi, top_rc.src, c.gtop + c.y0,
                  fall.zhi - fall.zlo, fall.wx, fall.wy, void.zhi - void.zlo, void.wx, void.wy, c.y0))
        res.append(("6 %s: every reachable footprint inside the picture; Y0 the least that does it (line %d)"
                    % (tag, least), inside and least == 0))
    # 7. physics on FIRST, 8. the route on BENCH
    if "FIRST" in byname:
        _physics_checks(byname["FIRST"], res)
    if "BENCH" in byname:
        _route_checks(byname["BENCH"], res)
    ok = True
    for what, good in res:
        print("  %-4s %s" % ("ok" if good else "FAIL", what))
        ok = ok and good
    print("bbcourse selfcheck: %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


def previews(paths, out):
    try:
        from PIL import Image
    except ImportError:
        print("bbcourse: --png needs Pillow; skipped", file=sys.stderr)
        return 1
    os.makedirs(out, exist_ok=True)
    for path in paths:
        c = compile_course(path)
        img = Image.new("RGB", (c.width, c.lines))
        img.putdata([CGA1[v] for r in c.pic for v in r])
        px = img.load()
        for (bx, by) in c.route:
            for d in range(-3, 4):
                for (x, y) in ((bx + 8 + d, by + 13), (bx + 8, by + 13 + d)):
                    if 0 <= x < c.width and 0 <= y < c.lines:
                        px[x, y] = (255, 0, 0)
        base = os.path.join(out, c.name.lower())
        img.save(base + "-cga.png")
        occ = img.copy()
        op = occ.load()
        for r in c.records:
            for (x, y) in r["pix"]:
                rr, gg, bb = op[x, y]
                op[x, y] = (255, gg // 3, bb // 3) if (x + y) & 1 else (rr, gg, bb)
        occ.save(base + "-occ.png")
        h = Image.new("L", (c.width * 2, c.lines))
        data = []
        for y, row in enumerate(c.pic):
            for x, v in enumerate(row):
                pr = herc_pair(v, y, x)
                data += [255 * (pr >> 1), 255 * (pr & 1)]
        h.putdata(data)
        h.save(base + "-herc.png")
    print("bbcourse: previews in %s" % out)
    return 0


def default_paths():
    """BZ_COURSES, read out of the Makefile - the one authority on the courses
    and their order (K) - so a course added there is compiled and selfchecked
    by a bare `bbcourse.py --selfcheck` (the bonanzacourse row) too, never a
    hand copy of the list that can drift from it"""
    with open(os.path.join(ROOT, "Makefile"), encoding="utf-8", errors="replace") as f:
        m = re.search(r"^BZ_COURSES\s*:=\s*(.+)$", f.read(), re.M)
    if not m:
        raise SystemExit("bbcourse: the Makefile has no BZ_COURSES line")
    return [os.path.join(ROOT, p) for p in m.group(1).split()]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("courses", nargs="*", help="course files, in BZ_COURSES's order")
    ap.add_argument("-o", "--out", help="output directory")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--png", metavar="DIR", help="write preview PNGs (needs Pillow)")
    a = ap.parse_args()
    if not (a.out or a.selfcheck or a.png):
        ap.error("need -o OUT, --selfcheck or --png DIR")
    paths = a.courses or default_paths()
    try:
        rc = 0
        if a.selfcheck:
            rc |= selfcheck(paths)
        if a.out:
            write_out(a.out, paths)
        if a.png:
            rc |= previews(paths, a.png)
        return rc
    except CourseError as e:
        print("bbcourse: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
