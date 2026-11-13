#!/usr/bin/env python3
"""BONANZA's course compiler, waves 1 and 2 (SPEC.md 128.10.3 - 128.10.7, 128.11).

    python3 tools/bbcourse.py -o DIR COURSE.bbc ...        # what `make` runs: every
                                                          # course, in BZ_COURSES's order
    python3 tools/bbcourse.py --selfcheck [COURSE.bbc ...] # SPEC.md 128.11.17.1
    python3 tools/bbcourse.py COURSE.bbc --png DIR         # previews (Pillow, behind a try)

A course is TEXT (`apps/bonanza/courses/*.bbc`, SPEC.md 128.10.3, with
wave 2's `surface` and `ball`, 128.11.6.1).  ONE run compiles the whole list:
course K (its place on the command line) becomes ONE part, `BZ<K>.BIN`, a
`BZC1` part carrying the picture (a flat map of absolute block offsets and
the deduplicated 8 x 8 CGA blocks - the guest translates them in place on the
Hercules through htab(), SPEC.md 128.11.3), the occluder records (MERGED
exactly where no reachable position tells two apart, 128.11.4.1) and masks,
and the `BZG1` physics grid (SPEC.md 128.10.5; surfaces and OCCG,
128.11.2); and the same run writes `bzcourse.inc` WHOLE - `BZ_NCRS`, each
course's name, title and ball, the materials and surfaces tables, and the
`OS88_PART` rows of every course part (SPEC.md 128.11.3.1).  A stamp,
`.bz-crs`, holding a hash of this tool, of tools/bonanza_assets.py (whose
palette and Hercules encoders it imports) and of every course file, is
written FIRST.

Deterministic (the same inputs give the same bytes), standard library only,
integer geometry throughout (Fraction where a ramp's height at a pixel is a
ratio).  The renderer MOVED here from tools/bonanza_assets.py (SPEC.md
128.10.4); the palette, `cga_bytes`, `herc_pair`, `herc_bytes` and `htab`
are IMPORTED from there, so a course and the ball cannot disagree about a
mid-level pixel.

The run checks what it wrote, at BUILD time (packages are trusted, so the
guest does not): `read_part` re-reads every part as the guest would and
refuses a bad magic, offset, count, map word, OCCIDX, ROWTAB row, mask
offset, route, kind, surface or flag, naming the course and the field.

`Physics` is SPEC.md 128.11.8's step (wave 1's, 128.10.7.3, as wave 2
changes it), integer-exact: the guest's bzphys.inc is written to do exactly
what it does, and the bonanzaphys row compares the two at every frame.
`MATERIALS` is the one place the balls' constants are written.

Host reference for the rows (import this module):
    compile_course(path_or_text)    -> Course: .pic (the CGA picture, a list of
                                       bytearray rows), .cga (THE part), .herc
                                       (the part as the guest translates it on
                                       the Hercules), .sbuf/.tbuf (the per-pixel
                                       cell row and top), .records (merged),
                                       .raw (unmerged), .by_block, .cells,
                                       .reach, .x0, .y0, .route, .ball ...
    read_part(bytes)                -> the parsed part (and its build checks)
    Grid(part).cell(wx, wy)         -> (z0, sx, sy, kind, flags, surface), OPEN
                                       outside
    Physics(course, play=False, mat=None)
                                    -> the model: .step(key byte), .step_auto(),
                                       .poke(wx, wy, gvx, gvy), .run_log(log),
                                       the guest's state as .gx .gy .gz .gvx
                                       .gvy .gvz .air .nstep ... and wave 2's
                                       .lvl .hopw .kprev .mst .mct .sqf .lvz
                                       .gh .ghv (state2()), the screen state
                                       .bx .by .vx .vy, and .events
    Glide(physics, herc, brows, cols), glide_run(course, herc, rate, phase)
                                    -> GLIDE, bz_camglide's model (128.11.11.1)
    encode_log(keys, course, mat), decode_log(log)   BZR1 (128.11.12.1)
    ledge_gaps(), gap_table_text()  -> 128.11.5.3's table, from Physics
    htab(), herc_translate_course(part)              128.11.3
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
# SPEC.md 128.11.4.2's bounds, on the records the part ships (after the
# exact merge, 128.11.4.1): at most 4 records in one 8 x 8 BLOCK (a footprint's
# 3 x 3 blocks test at most 36 and lay at most 9, grouped) and at most 128 in
# one block ROW (the binary search on OCCIDX: at most 7 probes).  The laid
# count at a position is REPORTED, not refused.
REC_BLOCK_MAX = 4
REC_ROW_MAX = 128
BAND = 2                      # a record's tops span at most 2 px

KIND_VOID, KIND_FLOOR, KIND_WALL, KIND_GOAL = 0, 1, 2, 3
FL_SAFE, FL_OCC, FL_OCCG = 1, 2, 4
SURF_NORMAL, SURF_ICE, SURF_SAND, SURF_BOUNCE = 0, 1, 2, 3     # grid byte +2's high nibble
SURFACES = ("normal", "ice", "sand", "bounce")
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
K_HOP, K_GRIP = 0x10, 0x20         # Space, Left Shift (SPEC.md 128.11.7.2)

# --- wave 2: the materials (SPEC.md 128.11.5.1), PROVISIONAL --------------------
# THE one place they are written: bzcourse.inc's BZ_MATTAB and BZ_SURFTAB are
# generated from these, and Physics reads the same.  The owner tunes them by
# feel inside 128.10.7.2's caps (a tune is a table edit and a rebuild).
MAT_RUBBER, MAT_STEEL, MAT_GLASS = 0, 1, 2
MAT_NAMES = ("rubber", "steel", "glass")
HARD_NONE, HARD_STUN, HARD_SHATTER = 0, 1, 2
MATERIALS = (
    # ACC  K  EF   EW  BMIN HOP GRIP  hard          threshold steps
    dict(ACC=4, K=6, EF=205, EW=96, BMIN=128, HOP=224, GRIP=6, HARD=HARD_NONE, HTHR=0, HSTEPS=0),
    dict(ACC=2, K=8, EF=38, EW=32, BMIN=128, HOP=160, GRIP=5, HARD=HARD_STUN, HTHR=432, HSTEPS=55),
    dict(ACC=6, K=5, EF=102, EW=64, BMIN=96, HOP=176, GRIP=10, HARD=HARD_SHATTER, HTHR=552, HSTEPS=24),
)
MATREC = 16                   # BZ_MATTAB: bytes a material
SQTHR = 384                   # a landing at lvz >= this squashes (but a shatter)
SQSTEPS = 6                   # ...for this many steps
HOPWIN = 6                    # the Hop's window, steps (Space's key-down edge)
WMIN = 16                     # a wall rebound under this is 0 (no chatter)
E_BUMPER = 230                # a WALL with a bounce surface, every ball
E_MAT = 224                   # a bounce FLOOR (a mat), every ball
BMIN_MAT = 128                # ...and its rebound floor
SAND_K = 5                    # sand's drag shift, every ball
LVL_MAX = 8                   # the arrows' ramp: levels 0 .. 8


def surf_entry(mat, surf):
    """(force, drag shift (0 none), brake, floor restitution) of a material on a
    surface - BZ_SURFTAB's 4 bytes (SPEC.md 128.11.6.2)"""
    m = MATERIALS[mat]
    if surf == SURF_ICE:
        return (max(1, m["ACC"] >> 2), 0, max(1, m["GRIP"] >> 2), m["EF"])
    if surf == SURF_SAND:
        return (max(2, m["ACC"] >> 1), SAND_K, m["GRIP"], m["EF"] >> 1)
    if surf == SURF_BOUNCE:
        return (m["ACC"], m["K"], m["GRIP"], E_MAT)
    return (m["ACC"], m["K"], m["GRIP"], m["EF"])


def surftab():
    """BZ_SURFTAB: 3 materials x 4 surfaces x 4 bytes, material-major"""
    return bytes(b for mat in range(len(MATERIALS)) for surf in range(4) for b in surf_entry(mat, surf))


def mattab():
    """BZ_MATTAB: 16 bytes a material (SPEC.md 128.11.5.1's layout):
    +0 ACC, +1 drag shift, +2 EF, +3 EW, +4 BMIN, +5 GRIP, +6 HOP (word),
    +8 the hard landing (0 none, 1 stun, 2 shatter), +9 its steps,
    +10 its threshold (word, 1/256 px a step), +12 four zero bytes"""
    out = bytearray()
    for m in MATERIALS:
        out += struct.pack("<BBBBBBHBBH4x", m["ACC"], m["K"], m["EF"], m["EW"], m["BMIN"], m["GRIP"],
                           m["HOP"], m["HARD"], m["HSTEPS"], m["HTHR"])
    assert len(out) == MATREC * len(MATERIALS)
    return bytes(out)


HOPMAX = max(m["HOP"] for m in MATERIALS)
# a SHATTER's sprite: frame (SHA_STEPS - mct) // SHA_FSTEPS of the ball part's
# BA.NSH (SPEC.md 128.11.9.2) - so every shattering material's steps are
# exactly the frames' (bzgame.inc's bz_sprite reads these, and guards them
# against bzconst.inc's BZ_BAL_NSHA)
SHA_FSTEPS = 6
SHA_STEPS = BA.NSH * SHA_FSTEPS
assert all(m["HSTEPS"] == SHA_STEPS for m in MATERIALS if m["HARD"] == HARD_SHATTER), \
    "a shattering material's HSTEPS must be NSH x SHA_FSTEPS (the sprite's frames)"

RESERVED = ("edge", "prop", "tube", "checkpoint", "pad", "shape")


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
        self.surfaces = []          # [(surface, frozenset of tiles, line)], after every room
        self.ball = None            # (material, line); rubber when there is none


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
        elif st == "surface":
            if len(toks) < 2 or toks[1][0] != 'w' or toks[1][1] not in SURFACES:
                raise CourseError("%s: unknown surface %r (normal, ice, sand or bounce)"
                                  % (where, toks[1][1] if len(toks) > 1 else ""))
            tiles, i = _shape(toks, 2, where)
            if i != len(toks):
                raise CourseError("%s: surface takes a surface, a shape and nothing else" % where)
            src.surfaces.append((SURFACES.index(toks[1][1]), tiles, ln))
        elif st == "ball":
            if len(toks) != 2 or toks[1][0] != 'w' or toks[1][1] not in MAT_NAMES:
                raise CourseError("%s: unknown ball %r (rubber, steel or glass)"
                                  % (where, toks[1][1] if len(toks) > 1 else ""))
            if src.ball is not None:
                raise CourseError("%s: a second 'ball' statement" % where)
            src.ball = (MAT_NAMES.index(toks[1][1]), ln)
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
    __slots__ = ("kind", "z0", "sx", "sy", "line", "surf")

    def __init__(self, kind, z0, sx, sy, line):
        self.kind, self.z0, self.sx, self.sy, self.line = kind, z0, sx, sy, line
        self.surf = SURF_NORMAL

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
    f = src.fname
    # surfaces after every room, before every hole (SPEC.md 128.11.6.1): a
    # WALL takes only normal or bounce (a bumper rail)
    for surf, shape, ln in src.surfaces:
        for t in sorted(shape):
            tl = tiles.get(t)
            if tl is None:
                continue
            if tl.kind == KIND_WALL and surf not in (SURF_NORMAL, SURF_BOUNCE):
                raise CourseError("%s:%d: %s on the wall (%d, %d): a wall takes normal or bounce"
                                  % (f, ln, SURFACES[surf], t[0], t[1]))
            tl.surf = surf
    for hole, _ in src.holes:
        for t in hole:
            tiles.pop(t, None)
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
        cells[(wx, wy)] = [t.z0, (t.sx & 15) | ((t.sy & 15) << 4), t.kind | (t.surf << 4), flags]
    for (wx, wy) in near:
        low = min(min(t.corners()) for t in _cheb(tiles, wx, wy, 2))
        cells[(wx, wy)] = [low - 6, 0, KIND_VOID, 0]
    return cells


def _nib(v):
    return v - 16 if v & 8 else v


# =============================================================================
# the reachable set (SPEC.md 128.10.4.1)
# =============================================================================

# The step's own flights (SPEC.md 128.11.4.4), DISCRETE: a take-off step adds
# U to z, each later one first loses BZ_G from gvz (capped at BZ_VZMAX) and
# then adds it.

def flight(U):
    """a flight that leaves at U (1/256 px a step): (its apex in 1/256 px, n0,
    the steps until it is back at its launch height)"""
    z = g = U
    top, n = z, 1
    while z > 0:
        g = max(g - G, -VZMAX)
        z += g
        n += 1
        top = max(top, z)
    return top, n


def UP(U):
    """the apex of a flight leaving at U, whole px (rounded up)"""
    return -(-flight(U)[0] // 256)


def RADIUS(U):
    """the tiles a flight leaving at U can carry a ball at the ground cap:
    max(3, ceil(n0 x BZ_VMAXG / 256 / 16))"""
    return max(3, -(-(flight(U)[1] * VMAXG) // (256 * TILE)))


def IMP(d):
    """the speed a ball falling d px from rest lands at, by the step"""
    z, g = d * 256, 0
    while z > 0:
        g = max(g - G, -VZMAX)
        z += g
    return -g


REACH_ROUNDS = 16             # a course whose reach has not settled by then is refused


class Reach:
    __slots__ = ("wx", "wy", "s", "a", "zlo", "zhi", "kind", "src")

    def __init__(self, wx, wy, zlo, zhi, kind, src):
        self.wx, self.wy = wx, wy
        self.s, self.a = wx + wy, wx - wy
        self.zlo, self.zhi, self.kind, self.src = zlo, zhi, kind, src


def build_reach(tiles, cells, fname="<course>"):
    """-> ([Reach], rounds, EMAX): every cell a contact point can be in, its
    lowest whole px (128.10.4.1's) and its highest (128.11.4.4's zhi: every
    launch with the largest Hop, and every bounce bounded by the energy that
    reached the cell it bounces on, iterated to a fixed point).  .src is
    (the cell, 'launch' or 'bounce') of what set zhi, or None (its own floor)."""
    sol = {k: t for k, t in tiles.items() if t.kind != KIND_WALL}
    hi = {k: 4 * max(t.corners()) for k, t in sol.items()}
    lo = {k: 4 * min(t.corners()) for k, t in sol.items()}
    emax = max(m["EF"] for m in MATERIALS)
    if any(t.surf == SURF_BOUNCE for t in sol.values()):
        emax = max(emax, E_MAT)
    srcs = []
    for k in sorted(sol):
        t = sol[k]
        U = (abs(t.sx) + abs(t.sy)) * VMAXG // 4 + HOPMAX
        srcs.append((k, hi[k] + UP(U), RADIUS(U), "launch"))

    def spread(srclist):
        best = {}
        for (k, h, r, why) in srclist:
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    c = (k[0] + dx, k[1] + dy)
                    if c in cells and (c not in best or h > best[c][0]):
                        best[c] = (h, k, why)
        return best

    best = spread(srcs)
    rounds = 0
    while True:
        rounds += 1
        if rounds > REACH_ROUNDS:
            worst = max((c for c in best), key=lambda c: best[c][0])
            raise CourseError("%s: the reach has not settled in %d rounds (cell (%d, %d) still rising)"
                              % (fname, REACH_ROUNDS, worst[0], worst[1]))
        extra = []
        for k in sorted(sol):
            E = max(best.get(k, (hi[k],))[0], hi[k])
            if E <= hi[k]:
                continue
            rh = min(emax * IMP(E - hi[k]) >> 8, emax * VZMAX >> 8)
            rl = min(emax * IMP(E - lo[k]) >> 8, emax * VZMAX >> 8)
            extra.append((k, hi[k] + UP(rh), RADIUS(rl), "bounce"))
        nb = spread(srcs + extra)
        if nb == best:
            break
        best = nb
    out = []
    for (wx, wy) in sorted(cells):
        z0, _, kind, _ = cells[(wx, wy)]
        kind &= 15
        if kind == KIND_WALL:
            continue
        zlo = 4 * z0 if kind == KIND_VOID else 4 * min(tiles[(wx, wy)].corners())
        zhi, src = zlo, None
        if (wx, wy) in best and best[(wx, wy)][0] > zhi:
            zhi, src = best[(wx, wy)][0], best[(wx, wy)][1:]
        out.append(Reach(wx, wy, zlo, zhi, kind, src))
    return out, rounds, emax


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


def _surface_ink(surf, x0, y0):
    """a surface's top pattern (SPEC.md 128.11.6.1), in WORLD pixels so the
    blocks it makes repeat: ice a sparse white on cyan, sand a black stipple on
    magenta, a bounce mat a white diamond lattice on magenta"""
    if surf == SURF_ICE:
        return lambda x, y: WHT if (x & 3) == 0 and (y & 1) == 0 and ((x >> 2) + (y >> 1)) & 1 else CYN
    if surf == SURF_SAND:
        return lambda x, y: BLK if (x + 2 * y) % 5 == 0 or (x - y) % 7 == 0 else MAG
    return lambda x, y: WHT if abs(((x - x0) & 15) - 8) + 2 * abs(((y - y0) & 7) - 4) == 8 else MAG


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
                cv.fill(sp, MAG if t.surf == SURF_BOUNCE else WHT, s, top)   # a bumper rail: magenta
            elif t.kind != KIND_GOAL and t.surf != SURF_NORMAL:
                cv.fill(sp, _surface_ink(t.surf, x0, y0), s, top)
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


def _laid(reach, recs_by_block, x0, y0, rc_list=None, zr=None, margin=0, frac=None):
    """-> ({cell: most records laid at any of its positions}, worst (n, cell, z)).
    zr(rc) -> (zlo, zhi) the whole heights to try (default the reach's), margin
    the rule's m, frac(rc, z) -> whether a ball at whole height z can carry a
    fraction (its footprint a line higher; default: below the apex)"""
    best = {}
    worst = (0, None, None)
    for rc in (rc_list or reach):
        lo, hi = zr(rc) if zr else (rc.zlo, rc.zhi)
        xl, xh = foot_x(rc, x0)
        cand = []
        for br in range((foot_top(rc, hi) + y0 - 1) >> 3, ((foot_top(rc, lo) + y0 + 30) >> 3) + 1):
            for bc in range(xl >> 3, (xh >> 3) + 1):
                for r in recs_by_block.get((br, bc), ()):
                    if r["s"] > rc.s and r["top"] > lo + margin:
                        cand.append(r)
        n_best = 0
        if cand:
            p4s = range(16 * rc.a + x0 - 24, 16 * rc.a + x0 + 5, 4)
            for z in range(lo, hi + 1):
                live = [r for r in cand if r["top"] > z + margin]
                if not live:
                    break
                t0 = foot_top(rc, z) + y0
                # (t0 - 1: whole height z with a fraction, below the apex)
                f1 = frac(rc, z) if frac else z < hi
                for py in range(t0 - (1 if f1 else 0), t0 + 16):
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


def block_queries(reach, x0, y0, width):
    """-> {(block row, block column): {(s_b, z_b + m)}}: every verdict input a
    reachable position whose footprint meets the block can present (SPEC.md
    128.11.4.1) - every whole height of its cell's range, both margins, the
    footprint over the cell's area and the fractional line.  A superset of the
    real set, so a merge over it is exact over the real one."""
    q = {}
    for rc in reach:
        xl, xh = foot_x(rc, x0)
        cols = range(max(xl, 0) >> 3, (min(xh, width - 1) >> 3) + 1)
        for z in range(rc.zlo, rc.zhi + 1):
            t0 = foot_top(rc, z) + y0 - 1
            t1 = foot_top(rc, z) + y0 + 30
            pair = ((rc.s, z), (rc.s, z + CLIMB))
            for br in range(max(t0, 0) >> 3, (t1 >> 3) + 1):
                for bc in cols:
                    st = q.get((br, bc))
                    if st is None:
                        st = q[(br, bc)] = set()
                    st.update(pair)
    return q


def _verdict(r, Q):
    return tuple(1 if (sb < r["s"] and zm < r["top"]) else 0 for sb, zm in Q)


def merge_records(records, q, _force=None):
    """SPEC.md 128.11.4.1: two records of ONE block are merged when every query
    of the block gives them the same verdict; a record no query lays is
    dropped.  The merged record's mask is the AND of its members' (it keeps
    only what none of them lays), its s and top the first member's, its pixels
    their union; .members names them (the check's).  _force=(block, i, j)
    merges records i and j of that block whatever their verdicts: the
    negative control's."""
    by_block = {}
    for r in records:
        by_block.setdefault((r["brow"], r["col"]), []).append(r)
    out = []
    for key in sorted(by_block):
        recs = by_block[key]
        Q = sorted(q.get(key, ()))
        classes = {}
        order = []
        for i, r in enumerate(recs):
            v = _verdict(r, Q)
            if _force and _force[0] == key and i == _force[2]:
                v = _verdict(recs[_force[1]], Q)
            if not any(v):
                continue
            if v not in classes:
                classes[v] = []
                order.append(v)
            classes[v].append(r)
        for v in order:
            g = classes[v]
            mask = bytearray(g[0]["mask"])
            pix = set()
            for r in g:
                for i in range(16):
                    mask[i] &= r["mask"][i]
                pix |= r["pix"]
            out.append({"brow": key[0], "col": key[1], "s": g[0]["s"], "top": g[0]["top"],
                        "mask": bytes(mask), "pix": frozenset(pix), "members": tuple(g)})
    out.sort(key=lambda r: (r["brow"], r["col"], r["s"], r["top"], r["mask"]))
    return out


def merge_exact(raw, merged, q):
    """the merge's own check (SPEC.md 128.11.17.1 item 5): for every block and
    every query of it, the merged records lay exactly the pixels the unmerged
    ones lay.  -> (queries tried, the first (block, query) that differs or None)"""
    rb, mb = {}, {}
    for r in raw:
        rb.setdefault((r["brow"], r["col"]), []).append(r)
    for r in merged:
        mb.setdefault((r["brow"], r["col"]), []).append(r)
    tried = 0
    for key in sorted(set(rb) | set(mb)):
        for sb, zm in sorted(q.get(key, ())):
            tried += 1
            a = set()
            for r in rb.get(key, ()):
                if sb < r["s"] and zm < r["top"]:
                    a |= r["pix"]
            b = set()
            for r in mb.get(key, ()):
                if sb < r["s"] and zm < r["top"]:
                    b |= r["pix"]
            if a != b:
                return tried, (key, (sb, zm))
    return tried, None


def _occg(reach, by_block, x0, y0, tiles):
    """SPEC.md 128.11.4.3: a FLOOR or GOAL cell some GROUNDED ball in which - at
    its floor, margin BZ_CLIMB, anywhere in its area - meets a record the rule
    lays.  -> {cell: most laid by a grounded ball}"""
    fl = [rc for rc in reach if rc.kind in (KIND_FLOOR, KIND_GOAL)]

    def zr(rc):
        t = tiles[(rc.wx, rc.wy)]
        return 4 * min(t.corners()), 4 * max(t.corners())

    def frac(rc, z):                    # a plane's height carries a fraction
        t = tiles[(rc.wx, rc.wy)]
        return bool(t.sx or t.sy) and z < 4 * max(t.corners())
    return _laid(reach, by_block, x0, y0, rc_list=fl, zr=zr, margin=CLIMB, frac=frac)[0]


def htab():
    """BZ_HTAB (SPEC.md 128.11.3), the table bz_hgen BUILDS: 512 bytes,
    [256 p + b] the CGA byte b on a line of parity p as Hercules pairs"""
    return BA.htab()


def herc_translate_course(part):
    """the Hercules course part bz_hxlat makes at the fetch: every block byte
    through htab()'s table for its line's parity (the word's index in its
    block); the rest of the part unchanged"""
    t = htab()
    p = bytearray(part)
    nblk, _, blkoff = struct.unpack_from("<HHH", p, 8)
    for i in range(16 * nblk):
        o = blkoff + i
        p[o] = t[256 * ((i >> 1) & 1) + p[o]]
    return bytes(p)


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
    reach, rounds, emax = build_reach(tiles, cells, fname)
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
    # the occluders: cut (128.10.4.4), merged (128.11.4.1), bounded (128.11.4.2)
    raw, occpix = _occluders(cv, reach, x0, y0, cols, brows) if occluders else ([], {})
    q = block_queries(reach, x0, y0, width) if occluders else {}
    records = merge_records(raw, q)
    per_row, per_block = {}, {}
    for r in records:
        per_row[r["brow"]] = per_row.get(r["brow"], 0) + 1
        per_block[(r["brow"], r["col"])] = per_block.get((r["brow"], r["col"]), 0) + 1
    for key in sorted(per_block):
        if per_block[key] > REC_BLOCK_MAX:
            raise CourseError("%s: block (row %d, column %d; lines %d - %d, px %d - %d) has %d occluder records, "
                              "over %d" % (fname, key[0], key[1], 8 * key[0], 8 * key[0] + 7, 8 * key[1],
                                           8 * key[1] + 7, per_block[key], REC_BLOCK_MAX))
    for br in sorted(per_row):
        if per_row[br] > REC_ROW_MAX:
            raise CourseError("%s: block row %d (lines %d - %d) has %d occluder records, over %d"
                              % (fname, br, 8 * br, 8 * br + 7, per_row[br], REC_ROW_MAX))
    by_block = {}
    for r in records:
        by_block.setdefault((r["brow"], r["col"]), []).append(r)
    laid, worst = _laid(reach, by_block, x0, y0)
    for (wx, wy), n in laid.items():
        if n:
            cells[(wx, wy)][3] |= FL_OCC
    occg = _occg(reach, by_block, x0, y0, tiles) if records else {}
    for (wx, wy), n in occg.items():
        if n:
            cells[(wx, wy)][3] |= FL_OCCG
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
    cga = bytearray(hdr + mapb)
    for blk in blocks:
        for y in range(8):
            cga += cga_bytes(blk[y * 8:y * 8 + 8])
    cga += bytes(idx) + recb + b"".join(masks) + bytes(grid)
    assert len(cga) == end
    c = Course()
    c.fname, c.name, c.title = fname, src.name, src.title
    c.src, c.tiles, c.cells, c.reach = src, tiles, cells, reach
    c.x0, c.y0, c.width, c.lines, c.cols, c.brows = x0, y0, width, lines, cols, brows
    c.pic, c.sbuf, c.tbuf = pic, cv.sbuf, cv.tbuf
    c.blocks, c.map = blocks, mp
    c.records, c.occpix, c.by_block = records, occpix, by_block
    c.raw, c.queries = raw, q
    c.masks = masks
    c.raw_masks = len({r["mask"] for r in raw})
    c.laid, c.worst, c.occg = laid, worst, occg
    c.per_row, c.per_block = per_row, per_block
    c.raw_row, c.raw_block = {}, {}
    for r in raw:
        c.raw_row[r["brow"]] = c.raw_row.get(r["brow"], 0) + 1
        c.raw_block[(r["brow"], r["col"])] = c.raw_block.get((r["brow"], r["col"]), 0) + 1
    c.rounds, c.emax = rounds, emax
    c.ball = src.ball[0] if src.ball else MAT_RUBBER
    c.route = route
    c.start = (swx, swy)
    c.cga = bytes(cga)
    c.part_bytes = c.cga                # the ONE part (BZ<K>.BIN, SPEC.md 128.11.3)
    c.herc = herc_translate_course(c.cga)   # what the guest makes of it on the Hercules
    c.gtop, c.ftop = gtop, ftop
    c.part = read_part(c.cga, fname)
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
        if kd & 15 > KIND_GOAL or kd >> 4 > SURF_BOUNCE or fl & ~(FL_SAFE | FL_OCC | FL_OCCG) \
                or (fl & FL_OCCG and not fl & FL_OCC):
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
        """-> (z0, sx, sy, kind, flags, surface); OPEN outside the grid"""
        r = wx + wy - self.smin
        k = (wx - wy - self.amin) >> 1
        if r < 0 or r >= self.nrows or k < 0 or k >= self.kw:
            return (Z_OPEN, 0, 0, KIND_VOID, 0, 0)
        z0, sl, kd, fl = struct.unpack_from("<bBBB", self.p, self.rowtab[r] + 4 * k)
        return (z0, _nib(sl & 15), _nib(sl >> 4), kd & 15, fl, kd >> 4)


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


def _drag(v, k=6):
    """ceil(|v| / 2^k) toward 0; k = 0 is NO drag (ice)"""
    if not k:
        return v
    a = (abs(v) + (1 << k) - 1) >> k
    return v + a if v < 0 else v - a


def _clamp(v, m):
    return m if v > m else -m if v < -m else v


def _s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _brake(v, b):
    """toward 0 by b, never past it (Grip, SPEC.md 128.11.7.2)"""
    return v - b if v > b else v + b if v < -b else 0


def _refl(v, e):
    """SPEC.md 128.11.8.4: v_n = -sign(v_n) x ((e x |v_n|) >> 8), 0 under BZ_WMIN"""
    t = (e * abs(v)) >> 8
    if t < WMIN:
        t = 0
    return -t if v > 0 else t


def ftg_table(acc):
    """the arrows' force on the ground at each level, A the surface's force"""
    return [(acc * lv + 4) >> 3 for lv in range(LVL_MAX + 1)]


def fta_table(acc):
    """...in the air: half the material's ramp"""
    return [((acc * lv + 4) >> 3) >> 1 for lv in range(LVL_MAX + 1)]


ST_NONE, ST_STUN, ST_SHATTER = 0, 1, 2


class Physics:
    """The ball, SPEC.md 128.10.7 as wave 2 changes it (128.11.8, binding: the
    guest does exactly this).  Positions are integers in 1/256 (24.8): gx, gy
    in gu, gz in px.  play: the goal counts.  mat: the material (default the
    course's ball, rubber for a bare part).  The red-arm switches exist for
    --selfcheck's negative controls and nothing else."""

    def __init__(self, course, play=False, mat=None, _slope_sign=1, _takeoff_zero=False, _ef_zero=False,
                 _east_w1=False, _no_stun=False, _abs_impact=False, _no_airclimb=False, _hop_add=False):
        part = course.cga if isinstance(course, Course) else course
        if mat is None:
            mat = course.ball if isinstance(course, Course) else MAT_RUBBER
        self.grid = Grid(part)
        self.play = play
        self.mat = mat
        self.m = MATERIALS[mat]
        self._slope_sign = _slope_sign
        self._takeoff_zero = _takeoff_zero
        self._ef_zero, self._east_w1, self._no_stun = _ef_zero, _east_w1, _no_stun
        self._abs_impact, self._no_airclimb, self._hop_add = _abs_impact, _no_airclimb, _hop_add
        self.x0, self.y0 = self.grid.x0, self.grid.y0
        self.route = self.grid.route
        self.nstep = self.nfall = self.nland = 0
        self.goal = 0
        self.lfall = self.lvz = 0
        self.ztop = 0
        self.safe = self.grid.start
        self.wp = 1                            # bz_play: waypoint 0 is the start
        self.events = []
        # wave 2's state (SPEC.md 128.11.5.2, 128.11.8.1)
        self.lvl = [0, 0, 0, 0]                # BZ_K_* order: L, R, U, D
        self.hopw = self.kprev = 0
        self.mst = self.mct = self.sqf = 0
        self.gh = self.ghv = 0
        self.nbnc = self.nstun = self.nshat = self.nhop = 0
        self.fta = fta_table(self.m["ACC"])
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
        """does neighbour c block the ball at its point (u, v)?  A WALL always;
        a floor whose height there is above the step's START z + BZ_CLIMB,
        grounded or airborne (SPEC.md 128.11.8.2 step 5)"""
        if c[3] == KIND_WALL:
            return True
        if c[3] in (KIND_FLOOR, KIND_GOAL):
            h = self.h4(c, u, v) << 6
            marg = 0 if (self.air and self._no_airclimb) else CLIMB << 8
            return h > self.zs + marg
        return False

    def e_wall(self, c):
        """a blocking cell's restitution: a bumper (a WALL with a bounce
        surface) 230 for every ball, anything else the material's stone EW"""
        if c[3] == KIND_WALL and c[5] == SURF_BOUNCE:
            return E_BUMPER
        return self.m["EW"]

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
        self.mst = self.mct = self.sqf = 0
        self.lvl = [0, 0, 0, 0]
        self.hopw = 0
        self.ghv = 0
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

    @property
    def G8(self):
        """the ground's screen line, no z: the integer part of (gx + gy) / 2"""
        return (self.gx + self.gy) >> 9

    def state(self):
        return (self.nstep, self.gx, self.gy, self.gz, self.gvx, self.gvy, self.gvz, self.air)

    def state2(self):
        """wave 2's state as bonanzaphys compares it (SPEC.md 128.11.17.2)"""
        return (tuple(self.lvl), self.hopw, self.kprev, self.mst, self.mct, self.sqf, self.lvz)

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

    def run_log(self, log):
        """step from the course's start through a log's bytes (SPEC.md
        128.11.12.1); the caller made this Physics with the log's course and
        material.  -> self"""
        for k in decode_log(log)[2]:
            self.step(k)
        return self

    # -- the step (SPEC.md 128.11.8.2) ------------------------------------------
    def _forces(self, K, tab):
        """the held arrows' push, (fx, fy), each arrow at its own level"""
        f = [tab[self.lvl[i]] if K & b else 0 for i, b in enumerate((K_L, K_R, K_U, K_D))]
        fl, fr, fu, fd = f
        return fr - fl + fd - fu, -fr + fl + fd - fu

    def step(self, K=0):
        self.respawned = False
        m = self.m
        # 1. the keys, on every step whatever the state
        for i, b in enumerate((K_L, K_R, K_U, K_D)):
            self.lvl[i] = min(LVL_MAX, self.lvl[i] + 1) if K & b else max(0, self.lvl[i] - 2)
        if K & K_HOP and not self.kprev & K_HOP:
            self.hopw = HOPWIN
        elif self.hopw:
            self.hopw -= 1
        self.kprev = K
        # ...then the ball's state
        if self.sqf:
            self.sqf -= 1
        if self.mst == ST_SHATTER:
            self.mct -= 1
            if self.mct == 0:
                self._respawn()
            return self._end()
        if self.mst == ST_STUN:
            self.mct -= 1
            if self.mct == 0:
                self.mst = ST_NONE
        stun = self.mst == ST_STUN
        cwx, cwy = self.gx >> 12, self.gy >> 12
        C = self.cell(cwx, cwy)
        # 2. forces
        if not self.air:
            force, dk, brake, _ = surf_entry(self.mat, C[5])
            if not stun:
                fx, fy = self._forces(K, ftg_table(force))
                self.gvx += fx
                self.gvy += fy
            sx, sy = (C[1], C[2]) if C[3] in (KIND_FLOOR, KIND_GOAL) else (0, 0)
            self.gvx -= self._slope_sign * GSL * sx
            self.gvy -= self._slope_sign * GSL * sy
            self.gvx = _drag(self.gvx, dk)
            self.gvy = _drag(self.gvy, dk)
            if K & K_GRIP and not stun:
                self.gvx = _brake(self.gvx, brake)
                self.gvy = _brake(self.gvy, brake)
            self.gvx = _clamp(self.gvx, VMAXG)
            self.gvy = _clamp(self.gvy, VMAXG)
            self.gvz = (sx * self.gvx + sy * self.gvy) >> 2
        else:
            if not stun:
                fx, fy = self._forces(K, self.fta)
                self.gvx += fx
                self.gvy += fy
            self.gvx = _clamp(self.gvx, VMAXG)
            self.gvy = _clamp(self.gvy, VMAXG)
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
        # 5. walls: the circle, the edge test SYMMETRIC (128.11.8.3), every
        # zeroing a reflection (128.11.8.4)
        pu, pv = self.gx & 0xFFF, self.gy & 0xFFF
        u, v = pu >> 8, pv >> 8
        lo = RAD << 8
        hi = (16 - RAD) << 8 if not self._east_w1 else ((16 - RAD) << 8) + 255
        if pu < lo:
            c = self.cell(cwx - 1, cwy)
            if self.blocks(c, 16, v):
                self.gx = (16 * cwx + RAD) << 8
                if self.gvx < 0:
                    self.gvx = _refl(self.gvx, self.e_wall(c))
        elif pu > hi:
            c = self.cell(cwx + 1, cwy)
            if self.blocks(c, 0, v):
                self.gx = (16 * cwx + 16 - RAD) << 8
                if self.gvx > 0:
                    self.gvx = _refl(self.gvx, self.e_wall(c))
        if pv < lo:
            c = self.cell(cwx, cwy - 1)
            if self.blocks(c, u, 16):
                self.gy = (16 * cwy + RAD) << 8
                if self.gvy < 0:
                    self.gvy = _refl(self.gvy, self.e_wall(c))
        elif pv > hi:
            c = self.cell(cwx, cwy + 1)
            if self.blocks(c, u, 0):
                self.gy = (16 * cwy + 16 - RAD) << 8
                if self.gvy > 0:
                    self.gvy = _refl(self.gvy, self.e_wall(c))
        pu, pv = self.gx & 0xFFF, self.gy & 0xFFF
        wu, eu = pu < lo, pu > hi
        wv, ev = pv < lo, pv > hi
        if (wu or eu) and (wv or ev):
            dx = -1 if wu else 1
            dy = -1 if wv else 1
            if self._east_w1:
                adu = (pu >> 8) if wu else 16 - (pu >> 8)
                adv = (pv >> 8) if wv else 16 - (pv >> 8)
            else:
                adu = (pu >> 8) if wu else (4096 - pu) >> 8
                adv = (pv >> 8) if wv else (4096 - pv) >> 8
            nx, ny, depth = CORNER[adu * 6 + adv]
            c = self.cell(cwx + dx, cwy + dy)
            if depth and self.blocks(c, 16 if dx < 0 else 0, 16 if dy < 0 else 0):
                nx = -nx if dx > 0 else nx
                ny = -ny if dy > 0 else ny
                mx, my = (depth * abs(nx)) >> 2, (depth * abs(ny)) >> 2
                self.gx += mx if nx >= 0 else -mx
                self.gy += my if ny >= 0 else -my
                d = (self.gvx * nx + self.gvy * ny) >> 6
                if d < 0:
                    t = (self.e_wall(c) * -d) >> 8
                    if t < WMIN:
                        t = 0
                    self.gvx -= ((d - t) * nx) >> 6
                    self.gvy -= ((d - t) * ny) >> 6
                self.events.append(("corner", self.nstep + 1, (-dx * adu, -dy * adv)))
        # the fallback
        cwx, cwy = self.gx >> 12, self.gy >> 12
        if (cwx, cwy) != scell:
            C = self.cell(cwx, cwy)
            u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
            if self.blocks(C, u, v):
                e = self.e_wall(C)
                if cwx != scell[0]:
                    self.gvx = _refl(self.gvx, e)
                if cwy != scell[1]:
                    self.gvy = _refl(self.gvy, e)
                self.gx, self.gy, self.gz = sgx, sgy, sgz
                cwx, cwy = scell
                self.events.append(("undo", self.nstep + 1, None))
        # 6. the floor
        C = self.cell(cwx, cwy)
        u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
        solid = C[3] in (KIND_FLOOR, KIND_GOAL)
        h4 = self.h4(C, u, v) if solid else 0
        h = h4 << 6
        if not self.air:
            if self.hopw and not stun and solid:
                # 128.11.8.6: the Hop from the ground
                self.air = 1
                self.gvz = min(VZMAX, self.gvz + m["HOP"])
                self.ztop = self.gz >> 8
                self.gz += self.gvz
                self.hopw = 0
                self.nhop += 1
                self.events.append(("hop", self.nstep + 1, self.gvz))
            elif not solid or h < self.gz + self.gvz - G - (STICK << 8):
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
                self._land(C, h, K, stun)
            elif C[3] == KIND_VOID and self.gz < (4 * C[0]) << 8:
                self._respawn()
                return self._end()
        # bz_gh, bz_ghv: the floor under an airborne ball (the shadow's, the squash's)
        if self.air and solid:
            self.gh, self.ghv = h4, 1
        else:
            self.ghv = 0
        # 8. SAFE and the goal: not shattering
        if self.mst != ST_SHATTER:
            if not self.air and C[4] & FL_SAFE:
                self.safe = (cwx, cwy)
            if C[3] == KIND_GOAL and self.play:
                if not self.goal:
                    self.events.append(("goal", self.nstep + 1, None))
                self.goal = 1
        return self._end()

    def _land(self, C, h, K, stun):
        """SPEC.md 128.11.8.5: a contact with a floor, judged RELATIVE to it"""
        m = self.m
        surf = C[5]
        fr = (C[1] * self.gvx + C[2] * self.gvy) >> 2
        lvz = max(0, fr - self.gvz) if not self._abs_impact else -self.gvz
        e = surf_entry(self.mat, surf)[3] if not self._ef_zero else 0
        bmin = BMIN_MAT if surf == SURF_BOUNCE else m["BMIN"]
        r = (e * max(0, min(lvz, -self.gvz))) >> 8
        self.lvz = lvz
        self.lfall = max(0, self.ztop - (h >> 8))
        self.gz = h
        self.nland += 1
        mat = surf == SURF_BOUNCE
        hard = m["HARD"] if not mat else HARD_NONE
        base = min(fr, 0)
        if hard == HARD_STUN and lvz >= m["HTHR"] and not self._no_stun:
            self.air = 0
            self.gvx = self.gvy = self.gvz = 0
            self.mst, self.mct = ST_STUN, m["HSTEPS"]
            self.nstun += 1
            self.events.append(("stun", self.nstep + 1, lvz))
        elif hard == HARD_SHATTER and lvz >= m["HTHR"]:
            self.air = 0
            self.gvx = self.gvy = self.gvz = 0
            self.mst, self.mct = ST_SHATTER, m["HSTEPS"]
            self.nshat += 1
            self.events.append(("shatter", self.nstep + 1, lvz))
        elif self.hopw and not stun:
            rr = r if r >= bmin else 0
            self.gvz = (m["HOP"] + rr if self._hop_add else max(m["HOP"], rr)) + base
            self.ztop = self.gz >> 8
            self.hopw = 0
            self.nhop += 1
            self.events.append(("hopc", self.nstep + 1, lvz, self.gvz))
        elif r >= bmin and not K & K_GRIP:
            self.gvz = r + base
            self.ztop = self.gz >> 8
            self.nbnc += 1
            self.events.append(("bounce", self.nstep + 1, lvz, r))
        else:
            self.gvz = 0
            self.air = 0
            self.events.append(("land", self.nstep + 1, (self.lfall, lvz)))
        if lvz >= SQTHR and self.mst != ST_SHATTER:
            self.sqf = SQSTEPS

    def _end(self):
        self.nstep += 1
        self._derive(self.respawned)
        return self


def sprite(p, herc):
    """bz_spr, SPEC.md 128.11.9.2: the sprite a frame draws from the state its
    last step left - ('shatter', k), ('squash', k) or ('roll', f) - with the
    vertical phase off the GROUND line (the CGA's G & 7; the Hercules keeps
    py's parity: (G & 6) | (py & 1))"""
    G8 = p.G8
    phy = (G8 & 6) | (p.py & 1) if herc else G8 & 7
    if p.mst == ST_SHATTER:
        return ("shatter", (SHA_STEPS - p.mct) // SHA_FSTEPS)
    at_floor = not p.air or (p.ghv and (p.gz >> 8) <= (p.gh >> 2))
    if p.sqf and at_floor:
        return ("squash", 0 if p.sqf in (6, 5, 2, 1) else 1)
    if p.mst == ST_STUN:
        phy = (phy + 2 * ((p.mct >> 2) & 1)) & 7
    return ("roll", phy * 8 + (p.px & 7))


def shadow(p):
    """the shadow a frame draws (SPEC.md 128.11.9.4), or None: (spy, px) when
    the ball is airborne over a FLOOR or GOAL cell, at least 2 px above it,
    and the cell's OCCG is clear.  (Whether a frame running the occluder pass
    keeps it is the box layout's, 128.11.10.1.)"""
    if not (p.air and p.ghv):
        return None
    h = p.gh >> 2
    if (p.gz >> 8) - h < 2 or p.cell(p.gx >> 12, p.gy >> 12)[4] & FL_OCCG:
        return None
    return (((p.gx + p.gy) >> 9) - h + p.y0 - 3, p.px)


# =============================================================================
# replays (SPEC.md 128.11.12): a log is BZR1, the course, the material, flags,
# the steps and the runs - the same bytes the guest's bz_rlog holds
# =============================================================================

RLOG_SIZE = 4096
RLOG_HDR = 16
RLOG_RUNS = (RLOG_SIZE - RLOG_HDR) // 2       # 2,040
RL_COMPLETE, RL_TRUNC = 1, 2


def encode_log(keys, course=0, mat=MAT_RUBBER, complete=True):
    """a step's key bytes -> the log's bytes, run-length coded as the guest's
    recorder does (a run is at most 255 steps; a flush into a full buffer
    truncates).  -> bytes (the 16-byte header and the runs, not padded)"""
    runs = []
    steps = 0
    trunc = False
    for k in keys:
        if runs and runs[-1][0] == k and runs[-1][1] < 255:
            runs[-1][1] += 1
        elif len(runs) >= RLOG_RUNS:
            trunc = True
            break
        else:
            runs.append([k, 1])
        steps += 1
    flags = (RL_COMPLETE if complete else 0) | (RL_TRUNC if trunc else 0)
    head = b"BZR1" + struct.pack("<BBBBIHH", course, mat, flags, 0, steps, len(runs), 0)
    return head + b"".join(struct.pack("<BB", k, n) for k, n in runs)


def decode_log(log):
    """-> (course, material, [key byte a step], flags)"""
    if log[:4] != b"BZR1":
        raise ValueError("not a BZR1 log")
    course, mat, flags, _, steps, nruns, _ = struct.unpack_from("<BBBBIHH", log, 4)
    keys = []
    for i in range(nruns):
        k, n = struct.unpack_from("<BB", log, RLOG_HDR + 2 * i)
        keys += [k] * n
    if len(keys) != steps:
        raise ValueError("the log's runs hold %d steps, its header %d" % (len(keys), steps))
    return course, mat, keys, flags


# =============================================================================
# GLIDE (SPEC.md 128.9, 128.11.11.1): the host model, KEPT this time
# =============================================================================

CARD_HZ = (59.93, 50.83)      # CGA, Hercules: the refresh the bracket presents at
CARDS = ((40, 100, 2, 1), (45, 50, 4, 2))   # W (columns), H (rows), rl (lines a row), lsh
WIN_LINES = 200               # BZ_LINES
MAXR, MAXC = 2, 1             # BZ_MAXR, BZ_MAXC
GLIDE_FX, GLIDE_FY = 4 * 4 * 256, 4 * 2 * 256   # 4 px / 2 lines a frame, over four frames
DIRS = tuple((a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0))


class Glide:
    """bz_camglide over a Physics, integer-exact (SPEC.md 128.9, 128.11.11.1).
    camera() runs once a frame AFTER the frame's steps and returns (dr, dc,
    full).  "Fast" is the ball's TRAVEL over four frames: the ring (bz_trx,
    bz_try) holds the low words of bz_bx and bz_by at the end of the last four
    frames; the camera reads the slot written four frames ago, compares, and
    then writes the present position into that slot (a full write fills all
    four with it).  _w1: wave 1's |v| against the per-card constants (the
    negative control's)."""

    GFX1 = (1124, 954)
    GFY1 = (562, 477)

    def __init__(self, phys, herc, brows, cols, _w1=False):
        self.p, self.herc, self._w1 = phys, herc, _w1
        self.W, self.H, self.rl, self.lsh = CARDS[herc]
        self.rmax = brows * 8 // self.rl - self.H
        self.cmax = cols - self.W
        self.R0 = self.c0 = 0
        self.first = True
        self.gpx = self.gpy = self.gpar = 0
        self.gdx = self.gdy = 0                # 0: right / down, 1: left / up
        self.trx = [0] * 4
        self.try_ = [0] * 4
        self.ti = 0

    def _clamp(self, R, C):
        return max(0, min(R, self.rmax)), max(0, min(C, self.cmax))

    def camera(self):
        p = self.p
        px, py = p.px, p.py
        bxl, byl = p.bx & 0xFFFF, p.by & 0xFFFF
        W, rl, lsh, L = self.W, self.rl, self.lsh, WIN_LINES
        if self.first:
            self.first = False
            R = max(0, py + 8 - L // 2) >> lsh
            C = max(0, px + 8 - 4 * W) >> 3
            self.R0, self.c0 = self._clamp(R, C)
            self.gpx = self.gpar = self.gpy = 0
            self.gdy = 0
            self.trx = [bxl] * 4
            self.try_ = [byl] * 4
            return 0, 0, True
        # the travel over four frames (128.11.11.1), then the ring
        dx4 = _s16(bxl - self.trx[self.ti])
        dy4 = _s16(byl - self.try_[self.ti])
        self.trx[self.ti], self.try_[self.ti] = bxl, byl
        self.ti = (self.ti + 1) & 3
        if self._w1:
            fastx = abs(p.vx) > self.GFX1[self.herc]
            fasty = abs(p.vy) > self.GFY1[self.herc]
        else:
            fastx = abs(dx4) > GLIDE_FX
            fasty = abs(dy4) > GLIDE_FY
        R0, c0 = self.R0, self.c0
        # ---- across ----
        if p.vx:
            self.gdx = 0 if p.vx > 0 else 1
        bc = px + 8
        off = bc - 8 * c0
        out = off < 2 * W or off > 6 * W
        if out and not self.gpx:
            self.gpx, self.gpar = 1, 0
        C = c0
        if self.gpx:
            if self.gdx == 0:
                t = bc - 2 * W
                ct = t >> 3 if t >= 0 else 0
            else:
                t = bc - 6 * W
                ct = (t + 7) >> 3 if t > 0 else 0
            ct = min(ct, self.cmax)
            if ct == c0:
                self.gpx = 0
            else:
                par = self.gpar
                self.gpar ^= 1
                if out or par == 0 or fastx:
                    C = c0 + (1 if ct > c0 else -1)
                    if C == ct:
                        self.gpx = 0
        # ---- down ----
        if p.vy:
            self.gdy = 0 if p.vy > 0 else 1
        c = py + 8
        off = c - (R0 << lsh)
        if off < L // 3 or off > 2 * L // 3:
            self.gpy = 1
        R = R0
        if self.gpy:
            if self.gdy == 0:
                t = c - L // 3
                rt = t >> lsh if t >= 0 else 0
            else:
                t = c - 2 * L // 3
                rt = (t + rl - 1) >> lsh if t > 0 else 0
            rt = min(rt, self.rmax)
            if rt == R0:
                self.gpy = 0
            else:
                d = 1 if rt > R0 else -1
                R = R0 + d
                if R == rt:
                    self.gpy = 0
                else:
                    o2 = c - (R << lsh)
                    if fasty or o2 < L // 3 or o2 > 2 * L // 3:
                        R += d
                        if R == rt:
                            self.gpy = 0
        R, C = self._clamp(R, C)
        full = abs(R - R0) > MAXR or abs(C - c0) > MAXC
        self.R0, self.c0 = R, C
        return R - R0, C - c0, full


def glide_run(course, herc, rate=1.0, phase=0.0, frames=1200, mat=None, _w1=False):
    """the benchmark under GLIDE: frames at the card's refresh, `rate` times
    the real step rate, the first frame a full write with its sub-ticks
    discarded.  -> ({direction: frames that scrolled that way}, Physics)"""
    p = Physics(course, mat=mat)
    g = Glide(p, herc, course.brows, course.cols, _w1=_w1)
    spf = rate * (PIT_HZ / CARD_HZ[herc]) / STEP_PIT
    acc = phase
    dirs = {}
    for fr in range(frames):
        acc += spf
        n = int(acc)
        acc -= n
        n = min(n, 8)
        if fr == 0:
            n = 0
        for _ in range(n):
            p.step_auto()
        dr, dc, full = g.camera()
        if dr or dc:
            k = ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
            dirs[k] = dirs.get(k, 0) + 1
    return dirs, p


# =============================================================================
# the ledge-gap table (SPEC.md 128.11.5.3), generated from Physics itself
# =============================================================================

GAP_DROPS = (2, 3, 4, 6)      # units fallen onto F
GAP_LEDGES = (0, 1, 2, 3)     # units G stands above F
_GAP_LIP = 14                 # F's last column + 1


def _gap_course(x, k):
    """F (flat 0) along +wx to column _GAP_LIP, k void tiles, then G at x units"""
    t = ('course GAP "gap"\nwidth 128\norigin 352\nfloor rect 3 10 %d 14 flat 0\n'
         'floor rect %d 10 %d 14 flat %g\nstart 5 12\n' % (_GAP_LIP, _GAP_LIP + k, _GAP_LIP + k + 6, x))
    return compile_course(t, "<ledge gap %g, %d>" % (x, k), occluders=False)


def _gap_run(c, D, xb, edge, mat=MAT_RUBBER):
    """a ball falling D units onto F at the cap along +wx (a chord held), its
    first contact at gx = xb (1/256 gu): -> 'G' when the next contact after
    that bounce is on G (the circle and the airborne margin included), else
    a string naming what happened instead"""
    n = 0
    z, g = (8 * D) << 8, 0
    while z > 0:
        g = max(g - G, -VZMAX)
        z += g
        n += 1
    p = Physics(c, mat=mat).poke(5, 12)
    p.gx = xb - n * VMAXG
    p.gz += (8 * D) << 8
    p.air = 1
    p.ztop = p.gz >> 8
    p.gvx = VMAXG
    p.lvl = [0, LVL_MAX, 0, LVL_MAX]
    first = None
    for _ in range(200):
        n0 = len(p.events)
        p.step(K_R | K_D)
        for e in p.events[n0:]:
            if e[0] in ("bounce", "land", "stun", "shatter", "hopc"):
                if first is None:
                    if e[0] != "bounce" or p.gx != xb:
                        return "first contact %s at %d" % (e[0], p.gx)
                    first = e
                else:
                    return "G" if (p.gx >> 12) >= edge else "F"
            if e[0] == "respawn":
                return "fell"
    return "flying"


def ledge_gaps(step=128):
    """-> {(D, X): (lo, hi) in gu, or None}: the distance from the bounce point
    on F to G's edge over which a rubber ball that fell D units onto F at the
    cap lands its first rebound on a ledge G X units above F.  G at F's
    height needs a gap of at least a tile to be a gap at all, so its lower
    bound is reported but is that tile's; the others run from G's face
    (k = 0).  Every bounce point over a tile, at `step`/256 gu, for each gap
    of 0 - 5 tiles: the step's own flights, the radius's circle and the
    4 px airborne margin all included, because it IS the step."""
    out = {}
    for X in GAP_LEDGES:
        good = {D: [] for D in GAP_DROPS}
        bad = {D: [] for D in GAP_DROPS}
        for k in range(0 if X else 1, 6):
            c = _gap_course(X, k)
            edge = _GAP_LIP + k
            for D in GAP_DROPS:
                for f in range(0, 16 << 8, step):
                    xb = ((_GAP_LIP - 1) * 16 << 8) + f
                    d = (edge * 16 << 8) - xb
                    (good if _gap_run(c, D, xb, edge) == "G" else bad)[D].append(d)
        for D in GAP_DROPS:
            g = good[D]
            if not g:
                out[(D, X)] = None
                continue
            lo, hi = min(g), max(g)
            holes = [d for d in bad[D] if lo < d < hi]
            out[(D, X)] = (lo / 256.0, hi / 256.0, len(holes))
    return out


def gap_table_text(t):
    lines = ["| fall onto `F` | rebound | ledge level with `F` (a gap of a tile or more) | 1 unit up | 2 units up "
             "| 3 units up |", "|---|---|---|---|---|---|"]
    for D in GAP_DROPS:
        r = (MATERIALS[MAT_RUBBER]["EF"] * IMP(8 * D)) >> 8
        cells = []
        for X in GAP_LEDGES:
            w = t[(D, X)]
            cells.append("none" if w is None else "%s - %s gu%s" % (
                ("%.2f" % w[0]).rstrip("0").rstrip("."), ("%.2f" % w[1]).rstrip("0").rstrip("."),
                " (%d holes)" % w[2] if w[2] else ""))
        lines.append("| %d units | %d | %s |" % (D, r, " | ".join(cells)))
    return "\n".join(lines)


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
        "; bzcourse.inc - GENERATED by tools/bbcourse.py (SPEC.md 128.10.4, 128.11.3.1).",
        "; Do not edit: change a course under apps/bonanza/courses/ (the Makefile's",
        "; BZ_COURSES, in order) and rebuild.  Course K's part is row 3 + K, after",
        "; the three balls' (bonanza.asm); ONE part a course, the CGA's blocks - the",
        "; Hercules translates them in place at the fetch (SPEC.md 128.11.3).",
        "",
        "BZ_NCRS         equ %d        ; courses, BZ_COURSES's order" % len(courses),
        "BZ_P_CRS        equ 3        ; course 0's row; course K's is BZ_P_CRS + K",
        "BZ_CRS_NAMEB    equ 6        ; BZ_CRS_NAMES: a row, the NAME NUL-padded",
        "BZ_CRS_TITLEB   equ 25       ; BZ_CRS_TITLES: a row, the title NUL-padded",
    ]
    for k, c in enumerate(courses):
        lines.append("BZ_CRS_%-8s equ %d        ; %s, \"%s\", ball %s" % (
            c.name, k, os.path.basename(c.fname), c.title, MAT_NAMES[c.ball]))
    lines += ["", "%macro BZ_CRS_NAMES 0"]
    for c in courses:
        lines.append("    db '%s'%s" % (c.name, ", 0" * (6 - len(c.name))))
    lines += ["%endmacro", "", "%macro BZ_CRS_TITLES 0"]
    for c in courses:
        lines.append("    db '%s'%s" % (c.title, ", 0" * (25 - len(c.title))))
    lines += ["%endmacro", "",
              "; each course's ball (its `ball` statement; rubber without one): a byte a course",
              "%macro BZ_CRS_BALLS 0",
              "    db " + ", ".join(str(c.ball) for c in courses),
              "%endmacro", "",
              "; physics v1's constants (SPEC.md 128.10.7.2), the model's own: bzphys.inc",
              "; and bbcourse.Physics cannot disagree about them",
              "BZ_ACCG         equ %d        ; rubber's ACC (wave 1's force; wave 2 reads BZ_SURFTAB)" % ACCG,
              "BZ_GSL          equ %d        ; ... a half unit a tile of slope" % GSL,
              "BZ_G            equ %d       ; 1/256 px a step a step" % G,
              "BZ_VMAXG        equ %d      ; |gvx|, |gvy|" % VMAXG,
              "BZ_VZMAX        equ %d      ; |gvz|" % VZMAX,
              "BZ_RAD          equ %d        ; gu" % RAD,
              "BZ_CLIMB        equ %d        ; px" % CLIMB,
              "BZ_STICK        equ %d        ; px" % STICK,
              "",
              "; wave 2 (SPEC.md 128.11.5 - 128.11.8): keys, materials, surfaces, flags",
              "BZ_K_HOP        equ %02Xh      ; the key byte: Space held" % K_HOP,
              "BZ_K_GRIP       equ %02Xh      ; ...Left Shift held" % K_GRIP,
              "BZ_NMAT         equ %d        ; rubber, steel, glass" % len(MATERIALS),
              "BZ_MAT_RUBBER   equ %d" % MAT_RUBBER,
              "BZ_MAT_STEEL    equ %d" % MAT_STEEL,
              "BZ_MAT_GLASS    equ %d" % MAT_GLASS,
              "BZ_MATREC       equ %d       ; BZ_MATTAB: bytes a material" % MATREC,
              "BZM_ACC         equ 0        ; the arrows' force at full ramp, normal ground",
              "BZM_K           equ 1        ; the drag shift: ceil(|v| / 2^K) toward 0",
              "BZM_EF          equ 2        ; floor restitution, /256",
              "BZM_EW          equ 3        ; restitution off a STONE wall, /256",
              "BZM_BMIN        equ 4        ; a rebound under this lands",
              "BZM_GRIP        equ 5        ; Grip's brake a step, normal ground",
              "BZM_HOP         equ 6        ; word: the Hop, 1/256 px a step",
              "BZM_HARD        equ 8        ; 0 none, 1 STUN, 2 SHATTER",
              "BZM_HSTEPS      equ 9        ; ...its steps",
              "BZM_HTHR        equ 10       ; word: ...its threshold on lvz",
              "BZ_HARD_STUN    equ %d" % HARD_STUN,
              "BZ_HARD_SHATTER equ %d" % HARD_SHATTER,
              "BZ_SURF_NORMAL  equ %d        ; grid byte +2's high nibble" % SURF_NORMAL,
              "BZ_SURF_ICE     equ %d" % SURF_ICE,
              "BZ_SURF_SAND    equ %d" % SURF_SAND,
              "BZ_SURF_BOUNCE  equ %d" % SURF_BOUNCE,
              "BZ_SURFREC      equ 4        ; BZ_SURFTAB: force, drag shift (0 none), brake, floor e",
              "BZ_FL_SAFE      equ %d" % FL_SAFE,
              "BZ_FL_OCC       equ %d" % FL_OCC,
              "BZ_FL_OCCG      equ %d        ; a grounded ball here can be hidden: no shadow" % FL_OCCG,
              "BZ_LVLMAX       equ %d        ; the arrows' ramp levels 0 .. 8" % LVL_MAX,
              "BZ_HOPWIN       equ %d        ; the Hop's window, steps" % HOPWIN,
              "BZ_SQTHR        equ %d      ; a landing at lvz >= this squashes (but a shatter)" % SQTHR,
              "BZ_SQSTEPS      equ %d        ; ...for this many steps" % SQSTEPS,
              "BZ_SHA_STEPS    equ %d       ; a shatter's steps (every shattering material's)" % SHA_STEPS,
              "BZ_SHA_FSTEPS   equ %d        ; ...a shatter frame's steps" % SHA_FSTEPS,
              "BZ_WMIN         equ %d       ; a wall rebound under this is 0" % WMIN,
              "BZ_EBUMPER      equ %d      ; a WALL with a bounce surface, every ball" % E_BUMPER,
              "BZ_EMAT         equ %d      ; a bounce FLOOR, every ball" % E_MAT,
              "BZ_BMINMAT      equ %d      ; ...its rebound floor" % BMIN_MAT,
              "",
              "; BZ_MATTAB (SPEC.md 128.11.5.1), %d bytes a material, bbcourse.MATERIALS" % MATREC,
              "%macro BZ_MATTAB 0"]
    mt = mattab()
    for i in range(0, len(mt), MATREC):
        lines.append("    db " + ", ".join(str(b) for b in mt[i:i + MATREC]) + "   ; " + MAT_NAMES[i // MATREC])
    lines += ["%endmacro", "",
              "; BZ_SURFTAB (SPEC.md 128.11.6.2): material-major, 4 surfaces x 4 bytes",
              "%macro BZ_SURFTAB 0"]
    st = surftab()
    for i in range(0, len(st), 16):
        lines.append("    db " + ", ".join(str(b) for b in st[i:i + 16]) + "   ; " + MAT_NAMES[i // 16])
    lines += ["%endmacro", "",
              "; the corner table (SPEC.md 128.10.7.3): 36 entries indexed 6 |du| + |dv|,",
              "; each |nx|, |ny| (x 64) and the push depth in 1/16 gu; zeros where",
              "; du^2 + dv^2 >= 36 (no contact)",
              "%macro BZ_CORNER_TABLE 0"]
    for i in range(0, 36, 6):
        lines.append("    db " + ", ".join("%d,%d,%d" % CORNER[i + k] for k in range(6)))
    lines += ["%endmacro", "",
              "; the course part rows: BZ_NCRS, one a course, every one",
              "; OP_ASSET | OP_LAZY | OP_COMP (SPEC.md 128.11.3.1)",
              "%macro BZ_CRS_PARTS 0",
              " %rep BZ_NCRS",
              "    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ<K>.BIN",
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
        files["BZ%d.BIN" % k] = c.cga
    return courses, files, {"bzcourse.inc": emit_inc(courses)}


def report(c, k=None):
    head = "course %s%s (%s, \"%s\", ball %s)" % ("%d " % k if k is not None else "", c.name,
                                                  os.path.basename(c.fname), c.title, MAT_NAMES[c.ball])
    g = c.part["grid"]

    def most(d):
        return max(d.values()) if d else 0
    top = min(c.reach, key=lambda rc: foot_top(rc, rc.zhi))
    print("  %s: %d x %d px (COLS %d, BROWS %d), X0 %d, Y0 %d (set by cell (%d, %d) at %d px: %s), reach "
          "settled in %d rounds, EMAX %d" % (
              head, c.width, c.lines, c.cols, c.brows, c.x0, c.y0, top.wx, top.wy, top.zhi,
              "%s of cell %s" % (top.src[1], top.src[0]) if top.src else "its own floor", c.rounds, c.emax))
    print("    part %d bytes: header 32, map %d, blocks %d x 16 = %d, OCCIDX %d, records %d x 8 = %d, masks "
          "%d x 16 = %d, grid %d (%d rows x %d cells x 4 + %d header, ROWTAB %d, route %d)" % (
              len(c.cga), 2 * c.cols * c.brows, len(c.blocks), 16 * len(c.blocks), 2 * (c.brows + 1),
              len(c.records), 8 * len(c.records), len(c.masks), 16 * len(c.masks),
              len(c.cga) - c.part["gridoff"], g["nrows"], g["kw"], GHDR, 2 * g["nrows"], 4 * len(c.route)))
    print("    records %d -> %d merged (masks %d -> %d); most in a block %d -> %d (bound %d), in a block row "
          "%d -> %d (bound %d); most laid at a position %d%s; %d OCC cells (%d OCCG) of %d reachable" % (
              len(c.raw), len(c.records), c.raw_masks, len(c.masks), most(c.raw_block), most(c.per_block),
              REC_BLOCK_MAX, most(c.raw_row), most(c.per_row), REC_ROW_MAX, c.worst[0],
              " (cell %s at %d px)" % (c.worst[1], c.worst[2]) if c.worst[1] else "",
              sum(1 for v in c.cells.values() if v[3] & FL_OCC), sum(1 for v in c.cells.values() if v[3] & FL_OCCG),
              len(c.reach)))


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
    STEEP = ('course T "t"\nwidth 64\nfloor rect 10 10 14 13 flat 16\nfloor rect 10 13 14 17 ramp y 13 17 16 8\n'
             'floor rect 10 17 14 19 flat 8\nstart 11 11\n')
    RIDGES = ('course T "t"\nwidth 128\nfloor band -24 24 40 64 flat 0\nfloor band -24 24 48 49 flat 3\n'
              'floor band -24 24 50 51 flat 6\nfloor band -24 24 52 53 flat 9\nstart 30 25\n')
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
        ("a reserved statement (prop)", F + "prop tile 4 4\n", "reserved for a later wave"),
        ("a reserved statement (edge)", F + "edge tile 4 4\n", "reserved for a later wave"),
        ("an unknown statement", F + "bogus 1 2\n", "unknown statement 'bogus'"),
        ("ice on a wall", F + "surface ice rect 3 3 7 4\n", "a wall takes normal or bounce"),
        ("sand on a wall", F + "surface sand tile 4 3\n", "a wall takes normal or bounce"),
        ("an unknown surface", F + "surface mud tile 4 5\n", "unknown surface 'mud'"),
        ("an unknown ball", F + "ball wood\n", "unknown ball 'wood'"),
        ("a second ball", F + "ball glass\n", "a second 'ball' statement"),
        ("a part over 65,024 bytes", BIG, "one part may be"),
        ("a block over %d records (a steep ramp's faces over the void)" % REC_BLOCK_MAX, STEEP,
         "occluder records, over %d" % REC_BLOCK_MAX),
        ("a block row over %d records" % REC_ROW_MAX, RIDGES, "occluder records, over %d" % REC_ROW_MAX),
    ]


def _decode(part, herc=False):
    """an independent reader: the map and blocks back to game pixels"""
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


def _ev(p, *kinds):
    return [e for e in p.events if e[0] in kinds]


_FLAT_LONG = 'course T "t"\nwidth 128\norigin 320\nfloor rect 3 10 33 14 flat 0\nstart 5 12\n%s'
_FLAT_WIDE = 'course T "t"\nwidth 128\norigin 512\nfloor band -26 26 40 52 flat 0\nstart 23 23\n%s'
_STEP = ('course T "t"\nwidth 64\nfloor rect 4 10 10 14 flat 4\nfloor rect 10 10 14 14 flat 4.5\nstart 5 12\n')


def _flat(kind, surf=None):
    t = (_FLAT_LONG if kind == "long" else _FLAT_WIDE) % (
        ("surface %s rect 0 0 60 60\n" % SURFACES[surf]) if surf else "")
    return compile_course(t, "<flat %s %s>" % (kind, SURFACES[surf] if surf else "normal"), occluders=False)


def _feel(long_, wide, mat):
    """SPEC.md 128.11.5.1's feel row, measured on the model: (steps to 300 and
    the top with a chord; one arrow's top and the step it first moves on;
    the coast from the cap (steps, tiles); Grip from the cap (steps, tiles))"""
    def run(c, keys, n, at, v=(0, 0), stop=None):
        p = Physics(c, mat=mat).poke(at[0], at[1], *v)
        out = []
        for _ in range(n):
            p.step(keys)
            if p.air or p.nfall:
                break
            out.append((p.gvx, p.gx))
            if stop and stop(p):
                break
        return out
    o = run(long_, K_R | K_D, 400, (4, 12))
    t300 = next((i + 1 for i, x in enumerate(o) if x[0] >= 300), None)
    top = max(x[0] for x in o)
    o1 = run(wide, K_R, 700, (23, 23))
    mv = next((i + 1 for i, x in enumerate(o1) if x[0] > 0), None)
    top1 = max(x[0] for x in o1)
    oc = run(long_, 0, 3000, (4, 12), (VMAXG, 0), stop=lambda p: p.gvx == 0)
    og = run(long_, K_GRIP, 3000, (4, 12), (VMAXG, 0), stop=lambda p: p.gvx == 0)
    tiles = lambda o: round((o[-1][1] - o[0][1] + VMAXG) / 4096.0, 1)
    return (t300, top, top1, mv, len(oc), tiles(oc), len(og), tiles(og))


def _drop(c, at, units, mat, keys=0, n=400, space_at=None, upto=None):
    """a ball held at rest `units` above the floor of tile `at`, let go"""
    p = Physics(c, mat=mat).poke(*at)
    p.gz += (8 * units) << 8
    p.air = 1
    p.ztop = p.gz >> 8
    for i in range(n):
        k = keys | (K_HOP if space_at is not None and i == space_at else 0)
        p.step(k)
        if upto and upto(p):
            break
    return p


def _hop487(c, **kw):
    """a rubber ball dropped 6 units; its second contact would rebound at 487:
    Space pressed 3 steps before that contact.  -> the 'hopc' event"""
    p = Physics(c, **kw).poke(6, 12)
    p.gz += 48 << 8
    p.air, p.ztop = 1, p.gz >> 8
    for _ in range(200):
        p.step(0)
        if p.nbnc == 2:
            break
    t2 = p.nstep
    p = Physics(c, **kw).poke(6, 12)
    p.gz += 48 << 8
    p.air, p.ztop = 1, p.gz >> 8
    for i in range(t2):
        p.step(K_HOP if i == t2 - 4 else 0)
    e = _ev(p, "hopc")
    return e[0] if e else ("none", 0, 0, 0)


def _physics_checks(first, res, trial=None):
    """item 7 (SPEC.md 128.11.17.1): scripted runs against states written here"""
    # --- wave 1's on FIRST, as amended -------------------------------------
    def slope(**kw):
        p = Physics(first, **kw).poke(8, 5)
        for _ in range(20):
            p.step(0)
        return p.gvx > 0 and p.gvy == 0 and (p.gx, p.gvx, p.gvz) == (35446, 60, -15)

    def lip(**kw):
        p = Physics(first, **kw).poke(4, 6)
        for _ in range(130):
            p.step(K_R | K_D)
        return (_ev(p, "takeoff", "land", "bounce") == [("takeoff", 109, -96), ("bounce", 124, 456, 365)]
                and (p.lfall, p.lvz, p.nland, p.nbnc) == (16, 456, 1, 1))
    res.append(("7 FIRST: B's slope pulls a ball at rest downhill (+wx): after 20 steps gvx 60, gvz -15", slope()))
    p = Physics(first)
    contact = None
    for _ in range(120):
        g0 = p.gvy
        p.step(K_U)
        if g0 < 0 <= p.gvy:
            contact = (p.nstep, p.gy, p.gvx, p.gvy, g0)
            break
    res.append(("7 FIRST: Up drives it into the rail at step 64 and it REBOUNDS (gvy -132 -> 49 = 96/256 of it, at "
                "v = 6; gvx -133 kept)", contact == (64, (16 * 4 + RAD) << 8, -133, 49, -132)))
    p = Physics(first).poke(6, 4)
    got = None
    for _ in range(80):
        gy0 = p.gy
        p.step(K_R)
        if _ev(p, "corner"):
            got = (p.nstep, _ev(p, "corner")[0][2], p.gy - gy0, p.gvx, p.gvy)
            break
    res.append(("7 FIRST: Right from (6, 4): the rail's last cell (6, 3) is a corner neighbour and pushes the "
                "ball out along its normal (0, 1) at step 42", got == (42, (0, 5), 253, 97, 0)))
    res.append(("7 FIRST: B's lip: airborne at step 109 with the floor's gvz -96; on C at 124 with lfall 16, lvz 456, "
                "and a rubber ball BOUNCES at 365", lip()))
    p = Physics(first)
    for _ in range(135):
        p.step(K_R | K_D)
    res.append(("7 FIRST: R+D from the start flies the lip, bounces into the pit (12, 5) and reappears on the last "
                "SAFE cell (6, 5) at step 135", _ev(p, "respawn") == [("respawn", 135, (6, 5))] and p.nfall == 1
                and (p.gx >> 12, p.gy >> 12) == (6, 5) and not p.air))
    p = Physics(first).poke(3, 5, gvx=-VMAXG)
    trail = []
    for _ in range(40):
        p.step(0)
        trail.append((p.nstep, p.gz, p.gx >> 12, p.respawned))
        if p.respawned:
            break
    kill = 4 * Physics(first).cell(1, 5)[0] << 8
    res.append(("7 FIRST: poked off A's west side at the cap, it enters the OPEN cell (0, 5) at step 29 still above "
                "the NEAR band's kill height, and respawns at once",
                trail[-1][0] == 29 and trail[-1][3] and trail[-2][2] == 1 and trail[-2][1] > kill
                and p.cell(0, 5)[0] == Z_OPEN))
    p = Physics(first, play=True).poke(4, 6)
    for _ in range(130):
        p.step(K_R | K_D)
    q = Physics(first).poke(4, 6)
    for _ in range(130):
        q.step(K_R | K_D)
    res.append(("7 FIRST: the goal column sets the goal at step 130 in play, IN THE AIR (a finish line); the "
                "benchmark ignores it", _ev(p, "goal") == [("goal", 130, None)] and p.goal == 1 and q.goal == 0))
    # --- the ramp ---------------------------------------------------------------
    want = {MAT_RUBBER: [1, 1, 2, 2, 3, 3, 4, 4], MAT_STEEL: [0, 1, 1, 1, 1, 2, 2, 2],
            MAT_GLASS: [1, 2, 2, 3, 4, 5, 5, 6]}
    wide = _flat("wide")
    long_ = _flat("long")
    ok = True
    seqs = {}
    for m in range(3):
        p = Physics(wide, mat=m).poke(23, 23)
        f, v = [], []
        for _ in range(8):
            p.step(K_R)
            f.append(ftg_table(MATERIALS[m]["ACC"])[p.lvl[1]])
            v.append(p.gvx)
        seqs[m] = v
        ok = ok and f == want[m]
    ok = ok and seqs[MAT_RUBBER] == [0, 0, 1, 2, 4, 6, 9, 12]
    p = Physics(wide).poke(23, 23)
    lv = []
    for k in [K_R] * 8 + [0, 0, K_R]:
        p.step(k)
        lv.append(p.lvl[1])
    res.append(("7 the ramp: each material's first eight steps of a press push rubber 1,1,2,2,3,3,4,4, steel "
                "0,1,1,1,1,2,2,2, glass 1,2,2,3,4,5,5,6 (one arrow from rest: rubber's gvx %s, steel's %s, glass's "
                "%s); released two steps the level is 4 and a re-press resumes at 5"
                % (seqs[0], seqs[1], seqs[2]), ok and lv[7:] == [8, 6, 4, 5]))
    # --- every material on every surface ----------------------------------------
    feel_want = {MAT_RUBBER: (68, 384, 189, 3, 156, 4.7, 42, 1.7),
                 MAT_STEEL: (112, 384, 255, 6, 320, 13.0, 61, 2.7),
                 MAT_GLASS: (62, 341, 155, 2, 98, 2.5, 25, 0.9)}
    for m in range(3):
        f = _feel(long_, wide, m)
        print("    feel %-6s: a chord to 300 in %s steps, top %d; one arrow top %d, moving on step %s; the coast "
              "from 384 %d steps, %.1f tiles; Grip from 384 %d steps, %.1f tiles" % ((MAT_NAMES[m],) + f))
        res.append(("7 feel, %s (128.11.5.1's row): %s" % (MAT_NAMES[m], f), f == feel_want[m]))
    moving = True
    for sf in range(4):
        cw = _flat("wide", sf) if sf else wide
        for m in range(3):
            for keys in (K_R, K_R | K_D):
                p = Physics(cw, mat=m).poke(23, 23)
                for _ in range(60):
                    p.step(keys)
                if p.gvx == 0 or p.air:
                    moving = False
    ice = compile_course(_FLAT_WIDE % "surface ice band -26 26 45 47\n", "<ice strip>", occluders=False)
    p = Physics(ice, mat=MAT_STEEL).poke(23, 23)                 # s = 46, on the strip, dead still
    left = None
    for i in range(400):
        p.step(K_D)
        if p.cell(p.gx >> 12, p.gy >> 12)[5] != SURF_ICE:
            left = i + 1
            break
    sand = _flat("wide", SURF_SAND)
    sd = []
    for m in range(3):
        p = Physics(sand, mat=m).poke(20, 26, VMAXG, -VMAXG)
        p.lvl = [0, LVL_MAX, 0, 0]
        for i in range(200):
            p.step(K_R)
            if p.gvx <= 62 + (31 if m == MAT_GLASS else 0):
                break
        sd.append((i + 1, p.gvx))
    res.append(("7 every material on every surface moves from rest with one arrow and with a chord; a steel ball "
                "stopped dead on ice leaves it (step %s); sand takes a ball arriving at the cap with one arrow to "
                "62 in %d steps (rubber, steel) and glass to 93 in %d" % (left, sd[0][0], sd[2][0]),
                moving and left is not None and sd == [(93, 62), (93, 62), (90, 93)]))
    # --- Hop ---------------------------------------------------------------------
    hops = []
    for m in range(3):
        p = Physics(long_, mat=m).poke(6, 12)
        z0 = p.gz
        top = 0
        land = None
        for i in range(60):
            p.step(K_HOP if i == 0 else 0)
            top = max(top, p.gz - z0)
            if _ev(p, "bounce", "land", "hopc"):
                land = _ev(p, "bounce", "land", "hopc")[0]
                break
        hops.append((round(top / 256.0, 1), land[1], land[0], land[2]))
    p = _drop(long_, (6, 12), 1, MAT_STEEL, space_at=None, upto=lambda p: not p.air)
    n_land = p.nstep
    q = _drop(long_, (6, 12), 1, MAT_STEEL, space_at=n_land - 3, n=n_land)
    p2 = Physics(long_).poke(6, 12)
    for i in range(30):
        p2.step(K_HOP if i in (0, 17) else 0)
    again = _ev(p2, "hopc")
    res.append(("7 Hop from rest: rubber %s, steel %s, glass %s (apex px, the contact's step, what it does there, "
                "its impact); steel dropped 1 unit with Space 3 steps before its landing hops AT the contact (160); "
                "Space at a rubber Hop's own landing hops again (224, not its 185 rebound)" % tuple(hops),
                hops == [(4.5, 20, "bounce", 232), (2.4, 15, "land", (2, 176)), (2.9, 16, "land", (2, 184))]
                and _ev(q, "hopc") and _ev(q, "hopc")[0][3] == 160 and again and again[0][3] == 224))

    def stepup(**kw):
        c = compile_course(_STEP, "<a half-unit step>", occluders=False)
        for at in range(0, 40):
            p = Physics(c, **kw).poke(8, 12, 200, 0)
            p.lvl = [0, LVL_MAX, 0, LVL_MAX]
            for i in range(60):
                p.step(K_R | K_D | (K_HOP if i == at else 0))
            if any(e[0] in ("land", "bounce", "hopc") for e in p.events) and p.gx >> 12 >= 10 \
                    and not any(e[0] == "undo" for e in p.events) and p.gvx > 150:
                pass
            else:
                return False, at
        return True, None
    su = stepup()
    res.append(("7 a Hop toward a half-unit step lands on it (the airborne margin, 128.11.8.2 step 5) from every "
                "take-off point of 40 (no undo, its speed kept)", su[0]))
    # a 1-unit step: a rubber-only height (rubber's Hop, 4.5 px, and the 4 px
    # margin), never steel's (2.4 px) or glass's (2.9 px) - every take-off point
    unit = compile_course(_STEP.replace("flat 4.5", "flat 5"), "<a one-unit step>", occluders=False)
    ups = {}
    for m in range(3):
        n = 0
        for at in range(0, 60):
            p = Physics(unit, mat=m).poke(7, 12, VMAXG, 0)
            p.lvl = [0, LVL_MAX, 0, LVL_MAX]
            for i in range(80):
                p.step(K_R | K_D | (K_HOP if i == at else 0))
                if p.gx >> 12 >= 10 and not p.air:
                    n += 1
                    break
        ups[m] = n
    res.append(("7 a 1-unit step is a rubber-only height: of 60 take-off points at the cap, rubber's Hop gets onto "
                "it from %d, steel's and glass's from %d and %d" % (ups[0], ups[1], ups[2]),
                ups[0] > 0 and ups[1] == 0 and ups[2] == 0))
    p = _drop(long_, (6, 12), 6, MAT_RUBBER, upto=lambda p: p.nbnc == 1)
    t1 = p.nstep
    h487 = _hop487(long_)
    res.append(("7 a Hop at a contact whose rebound is 487 leaves at 487, not more (no pumping)", h487[3] == 487))
    p = _drop(long_, (6, 12), 6, MAT_RUBBER, keys=K_GRIP, upto=lambda p: not p.air)
    res.append(("7 Grip held at a bounce catches it: a 6-unit drop lands at the first contact", p.nbnc == 0
                and _ev(p, "land") and _ev(p, "land")[0][2][1] == 768))
    p = _drop(long_, (6, 12), 6, MAT_RUBBER, n=600, upto=lambda p: not p.air)
    chain = [e[3] for e in _ev(p, "bounce")]
    res.append(("7 a rubber ball dropped 6 units bounces six times (%s) and lands at the seventh contact (impact "
                "148) %d steps after the first" % (chain, p.nstep - t1),
                chain == [615, 487, 378, 293, 226, 164] and _ev(p, "land")[-1][2][1] == 148 and p.nstep - t1 == 177))
    # --- the walls ---------------------------------------------------------------
    rails = []
    for m in range(3):
        p = Physics(first, mat=m).poke(5, 6, 0, -189)
        hits = []
        for i in range(200):
            g0 = p.gvy
            p.step(K_U)
            if g0 < 0 <= p.gvy and (p.gy >> 8) & 15 <= RAD:
                hits.append((i, p.gvy))
                if p.gvy == 0:                    # under BZ_WMIN: at rest against it
                    break
        rails.append(([h[1] for h in hits if h[1] > 0], hits[-1][0] - hits[0][0] if hits else None))
    print("    FIRST's back rail, one arrow held into it: %s" % "; ".join(
        "%s rebounds %s, at rest %s steps after the first contact" % (MAT_NAMES[m], r[0], r[1])
        for m, r in enumerate(rails)))
    bump = compile_course(_FLAT_LONG % ("wall rect 3 9 33 10 flat 1\nsurface bounce rect 3 9 33 10\n"
                                        "surface ice rect 3 10 33 14\n"), "<bumper over ice>", occluders=False)
    p = Physics(bump, mat=MAT_STEEL).poke(8, 11, 0, -200)
    for _ in range(60):
        g0 = p.gvy
        p.step(0)
        if p.gvy > 0:
            break
    bump_in = -g0

    def eastwall(**kw):
        c = compile_course(_FLAT_LONG % "wall rect 20 10 21 14 flat 1\n", "<east wall>", occluders=False)
        p = Physics(c, **kw).poke(17, 12, 300, 0)
        p.lvl = [0, LVL_MAX, 0, LVL_MAX]
        us = []
        for _ in range(200):
            p.step(K_R | K_D)
            us.append(p.gx & 0xFFF)
        cw = compile_course(_FLAT_LONG % "wall rect 3 10 4 14 flat 1\n", "<west wall>", occluders=False)
        q = Physics(cw, **kw).poke(6, 12, -300, 0)
        ws = []
        for _ in range(200):
            q.step(K_L | K_U)
            ws.append(q.gx & 0xFFF)
        return set(us[-40:]) == {(16 - RAD) << 8} and set(ws[-40:]) == {RAD << 8}
    res.append(("7 the walls: FIRST's rail held into with one arrow, rubber rebounds 70 then 19 and rests 39 steps "
                "after the first contact; a bumper returns 230/256 to steel (%d -> %d); P1: a ball held into an "
                "east wall rests at u = 10.00 every step, as its mirror at 6.00" % (bump_in, p.gvy),
                rails[0] == ([70, 19], 39) and p.gvy == (E_BUMPER * bump_in) >> 8 and eastwall()))
    # --- TRIAL ---------------------------------------------------------------------
    if trial is not None:
        _trial_checks(trial, res)
    # --- the log -------------------------------------------------------------------
    keys = [K_R | K_D] * 300 + [K_R | K_D | K_HOP] * 2 + [K_L | K_GRIP] * 40 + [0] * 600 + [K_U] * 700
    log = encode_log(keys, course=1)
    a = Physics(first, play=True).run_log(log)
    b = Physics(first, play=True)
    for k in keys:
        b.step(k)
    dc = decode_log(log)
    big = encode_log([i & 0x3F for i in range(5000)])
    res.append(("7 a log encodes (%d runs, %d bytes), decodes to the same %d key bytes, and run_log equals stepping "
                "them; one past 2,040 runs TRUNCATES" % (struct.unpack_from("<H", log, 12)[0], len(log), len(keys)),
                dc[2] == keys and dc[:2] == (1, MAT_RUBBER) and a.state() + a.state2() == b.state() + b.state2()
                and big[6] & RL_TRUNC and len(big) == RLOG_SIZE))
    # --- negative controls -----------------------------------------------------------
    res.append(("7 negative control: the slope term's sign flipped fails the slope run", not slope(_slope_sign=-1)))
    res.append(("7 negative control: the take-off's gvz zeroed fails the lip run", not lip(_takeoff_zero=True)))
    p = _drop(long_, (6, 12), 6, MAT_RUBBER, n=600, upto=lambda p: not p.air)
    p0 = Physics(long_)
    pz = _drop(long_, (6, 12), 6, MAT_RUBBER, n=100, upto=lambda p: not p.air)
    pz = Physics(long_, _ef_zero=True).poke(6, 12)
    pz.gz += 48 << 8
    pz.air, pz.ztop = 1, pz.gz >> 8
    for _ in range(100):
        pz.step(0)
    res.append(("7 negative control: the floor restitution zeroed fails the bounce run", pz.nbnc == 0))
    try:
        e1 = eastwall(_east_w1=True)
    except Exception:
        e1 = False
    res.append(("7 negative control: the east test put back to wave 1's fails the P1 run", not e1))
    if trial is not None:
        res.append(("7 negative control: the stun skipped fails the steel-on-F run",
                    not _trial_stun(trial, _no_stun=True)))
        res.append(("7 negative control: the hard tests on -gvz fail the steep-ramp Hop run",
                    not _trial_ramphop(trial, _abs_impact=True)))
    res.append(("7 negative control: no airborne margin fails the step-up run", not stepup(_no_airclimb=True)[0]))
    res.append(("7 negative control: a Hop that ADDS to the rebound fails the 487 run",
                _hop487(long_, _hop_add=True)[3] != 487))


# TRIAL's geometry, read off the course itself (apps/bonanza/courses/trial.bbc)
TRIAL_H = ((4, 9), (10, 13))          # wx range, wy range (half-open): the start tier
TRIAL_F = ((9, 13), (10, 13))
TRIAL_G = ((15, 19), (10, 13))
TRIAL_MAT = (19, 14)


def _in(rect, t):
    return rect[0][0] <= t[0] < rect[0][1] and rect[1][0] <= t[1] < rect[1][1]


def _trial_shot(c, mat, v, off, hop, steps=400, **kw):
    """THE SWEEP's run: poked on H 20 gu before its lip at gvx = v (the route's
    axis, +wx), `off` gu across it, the chord held (and Space on step `hop`).
    -> (outcome, take-off step, Physics): 'G' (a contact on G after a bounce
    on F), 'G!' (on G with no bounce on F), 'stun' / 'shatter' (on F), 'fell'"""
    lip = TRIAL_H[0][1] * TILE
    p = Physics(c, mat=mat, **kw).poke(TRIAL_H[0][1] - 1, 11)
    p.gx = (lip << 8) - (20 << 8)
    p.gy = ((11 * TILE + 8) << 8) + (off << 8)
    p.gvx = v
    p.lvl = [0, LVL_MAX, 0, LVL_MAX]
    p._derive(True)
    bounced = False
    tl = None
    for i in range(steps):
        n0 = len(p.events)
        p.step(K_R | K_D | (K_HOP if hop is not None and i == hop else 0))
        cc = (p.gx >> 12, p.gy >> 12)
        for e in p.events[n0:]:
            if e[0] in ("takeoff", "hop") and tl is None:
                tl = i
            if e[0] in ("bounce", "hopc") and _in(TRIAL_F, cc):
                bounced = True
            if e[0] in ("bounce", "land", "hopc", "stun", "shatter") and _in(TRIAL_G, cc):
                return ("G" if bounced else "G!"), tl, p
            if e[0] in ("stun", "shatter") and _in(TRIAL_F, cc):
                return e[0], tl, p
            if e[0] == "respawn":
                return "fell", tl, p
    return "stayed", tl, p


def _trial_stun(c, **kw):
    """steel off H at the cap: STUNNED on F, every velocity 0 for 55 steps with
    the arrows held, then rolling again"""
    out, _, p = _trial_shot(c, MAT_STEEL, VMAXG, 0, None, **kw)
    if out != "stun":
        return False
    pos = (p.gx, p.gy)
    still = True
    for i in range(SQSTEPS and MATERIALS[MAT_STEEL]["HSTEPS"] - 1):
        p.step(K_R | K_D)
        still = still and (p.gx, p.gy, p.gvx, p.gvy) == pos + (0, 0) and p.mst == ST_STUN
    p.step(K_R | K_D)
    return still and p.mst == ST_NONE


def _trial_ramphop(c, **kw):
    """steel and glass at the cap down the steep ramp, Space on its first
    tile: they land on it unhurt"""
    for m in (MAT_STEEL, MAT_GLASS):
        for at in (20, 22, 24):                   # Space on the ramp's first tile
            p = Physics(c, mat=m, **kw).poke(17, 11, 0, VMAXG)
            p.lvl = [LVL_MAX, 0, 0, LVL_MAX]
            for i in range(70):
                p.step(K_L | K_D | (K_HOP if i == at else 0))
            if not _ev(p, "hop") or _ev(p, "stun", "shatter") or not _ev(p, "land", "bounce"):
                return False
    return True


def _trial_checks(c, res):
    from collections import Counter
    t0 = __import__("time").time()
    cnt = {m: Counter() for m in range(3)}
    for m in range(3):
        for v in range(144, VMAXG + 1, 16):
            for off in range(-8, 9, 2):
                out, tl, _ = _trial_shot(c, m, v, off, None)
                cnt[m][out] += 1
                for j in range(12):
                    out2 = _trial_shot(c, m, v, off, max(0, tl - 1 - j))[0] if tl else "stayed"
                    cnt[m][out2] += 1
    tot = sum(cnt[0].values())
    share = cnt[0]["G"] / float(tot)
    print("    TRIAL's sweep (%d runs a ball, %.1f s): rubber %s (on G after a bounce on F: %.1f%%); steel %s; "
          "glass %s" % (tot, __import__("time").time() - t0, dict(cnt[0]), 100 * share, dict(cnt[1]), dict(cnt[2])))
    res.append(("7 TRIAL, THE SWEEP (approach 144 - 384 by 16, nine offsets, no Space and Space at each of the last "
                "12 steps before the lip): rubber lands on G in %d of %d runs, %.1f%% (at least a quarter); steel is "
                "stunned and glass shattered on F in every run; no ball reaches G without a bounce on F"
                % (cnt[0]["G"], tot, 100 * share),
                share >= 0.25 and cnt[1]["stun"] == tot and cnt[2]["shatter"] == tot
                and all(cnt[m]["G!"] == 0 for m in range(3))))
    out, _, p = _trial_shot(c, MAT_GLASS, VMAXG, 0, None)
    t = p.nstep
    for _ in range(30):
        p.step(K_R | K_D)
    sh = _ev(p, "shatter", "respawn")
    res.append(("7 TRIAL: steel stunned on F stops where it lands (55 steps, every velocity 0, the arrows held); "
                "glass shattered there (24 steps) reappears on its SAFE cell on H",
                _trial_stun(c) and out == "shatter" and len(sh) == 2 and sh[1][1] - sh[0][1] == 24
                and _in(TRIAL_H, sh[1][2])))
    ok = True
    for m in (MAT_STEEL, MAT_GLASS):
        p = _drop(c, TRIAL_MAT, 6, m, n=200)
        ok = ok and _ev(p, "bounce") and not _ev(p, "stun", "shatter")
    res.append(("7 TRIAL: steel and glass Hop down the steep ramp at the cap and land unhurt; the mat bounces steel "
                "and glass dropped 6 units onto it, unhurt", _trial_ramphop(c) and ok))
    p = Physics(c).poke(15, 17, -300, 0)
    for _ in range(20):
        p.step(0)
    q = Physics(c, mat=MAT_STEEL).poke(13, 17, 0, -200)
    for _ in range(60):
        g0 = q.gvy
        q.step(0)
        if q.gvy > 0:
            break
    res.append(("7 TRIAL: the ice keeps a coasting ball's speed (-300 after 20 steps); its bumper rail returns "
                "230/256 (%d -> %d, no drag on the way); the sand patch is sand" % (-g0, q.gvy),
                p.gvx == -300 and -g0 == 200 and q.gvy == (E_BUMPER * 200) >> 8
                and Physics(c).cell(10, 18)[5] == SURF_SAND))


BENCH_COVER = 12      # the route's waypoints the CGA's 1,093 steps must reach
CGA_STEPS, HERC_STEPS = 1093, 1289


def _way_point(c, t):
    """the ball's picture top-left on tile t's centre, on its floor (128.10.4.5)"""
    tl = c.tiles[t]
    return (16 * (t[0] - t[1]) + c.x0 - 8, 8 * (t[0] + t[1]) + 8 - (4 * tl.z0 + 2 * (tl.sx + tl.sy)) + c.y0 - 13)


def _route_stats(c, steps):
    """the autopilot over a course's route: -> (Physics, waypoint reached at
    each step, OCC steps, laid on them, airborne OCC steps, OCCG steps); and
    _route_stats.gated, the steps the guest's gate (bz_mkboxes: OCC airborne,
    OCCG grounded) runs the occluder pass on"""
    p = Physics(c)
    reached = {}
    occ = air_occ = occg = gated = 0
    lays = []
    for i in range(steps):
        wp0 = p.wp
        p.step_auto()
        for k in range(wp0, p.wp):
            reached.setdefault(k, p.nstep)
        cl = p.cell(p.gx >> 12, p.gy >> 12)
        if cl[4] & FL_OCC:
            occ += 1
            air_occ += p.air
            lays.append(len(laid_at(c, p.px, p.py, p.sb, p.zb, p.air)))
        occg += bool(cl[4] & FL_OCCG)
        gated += bool(cl[4] & (FL_OCC if p.air else FL_OCCG))
    _route_stats.gated = gated
    return p, reached, occ, lays, air_occ, occg


def _route_checks(bench, res, trial=None, first=None):
    """item 8: the routes under wave 2's physics and the autopilot"""
    p, reached, occ, lays, _, occg = _route_stats(bench, CGA_STEPS)
    bgated = _route_stats.gated
    cga_wp, cga_fall = p.wp, p.nfall
    q = Physics(bench)
    for _ in range(HERC_STEPS):
        q.step_auto()
    route = Grid(bench.cga).route
    res.append(("8 BENCH: the autopilot rolling its rubber ball through the ramp reaches the route's first %d "
                "waypoints in order within the CGA's %d steps (at %s) and falls nowhere in the Hercules's %d" % (
                    BENCH_COVER, CGA_STEPS, ", ".join(str(reached.get(k, "-")) for k in range(1, BENCH_COVER - 1)),
                    HERC_STEPS), cga_fall == 0 and cga_wp >= BENCH_COVER - 1 and q.nfall == 0
                and route[0] == bench.route[0] == _way_point(bench, bench.start)))
    n = len(lays)
    print("    BENCH over the CGA's %d steps: %d with the cell's OCC set (%.0f%%), %d with OCCG; records laid on "
          "those: mean %.2f, most %d; steps laying none %d; the guest's gate runs the pass on %d" % (
              CGA_STEPS, n, 100.0 * n / CGA_STEPS, occg, (sum(lays) / n) if n else 0, max(lays) if lays else 0,
              sum(1 for x in lays if x == 0), bgated))
    if trial is not None:
        out = []
        for steps in (CGA_STEPS, HERC_STEPS):
            p, reached, occ, lays, air_occ, occg = _route_stats(trial, steps)
            if steps == CGA_STEPS:
                tgated = _route_stats.gated
            pl = Physics(trial, play=True)
            for _ in range(steps):
                pl.step_auto()
            first_g = next((e for e in pl.events if e[0] in ("bounce", "land")
                            and _in(TRIAL_G, (e[2] if False else (0, 0)))), None)
            out.append((p, occ, lays, air_occ, occg, pl))
        p, occ, lays, air_occ, occg, pl = out[0]
        airs = sum(1 for _ in range(0))
        bF = [e for e in pl.events if e[0] == "bounce"]
        res.append(("8 TRIAL: the autopilot goes off H's lip (step %s), bounces on F (impact %s) over the gap, reaches "
                    "the goal at step %s and falls nowhere in the CGA's %d steps or the Hercules's %d" % (
                        _ev(pl, "takeoff")[0][1] if _ev(pl, "takeoff") else "-", bF[0][2] if bF else "-",
                        _ev(pl, "goal")[0][1] if _ev(pl, "goal") else "-", CGA_STEPS, HERC_STEPS),
                    pl.goal == 1 and p.nfall == 0 and out[1][0].nfall == 0 and out[1][5].nfall == 0
                    and bF and bF[0][2] == 768))
        n = len(lays)
        print("    TRIAL over the CGA's %d steps: %d with OCC set (%.0f%%), %d of them AIRBORNE (the toward-the-viewer "
              "layout's count, 128.11.13), %d with OCCG; records laid on the OCC steps: mean %.2f, most %d; the guest's "
              "gate runs the pass on %d" % (
                  CGA_STEPS, n, 100.0 * n / CGA_STEPS, air_occ, occg, (sum(lays) / n) if n else 0,
                  max(lays) if lays else 0, tgated))
    if first is not None:
        res_f = []
        for m in range(3):
            for v in (0, 100, 200, 300, 384):
                p = Physics(first, play=True, mat=m).poke(8, 6, v, 0)
                for _ in range(400):
                    p.step(K_R | K_D)
                    if p.goal or p.nfall:
                        break
                res_f.append((m, v, p.goal and not p.nfall, p.nstep))
        res.append(("8 FIRST with each ball: poked at (8, 6), Right + Down held from 0, 100, 200, 300 and 384, the "
                    "goal reached without a fall in every run (%d - %d steps)" % (
                        min(x[3] for x in res_f), max(x[3] for x in res_f)), all(x[2] for x in res_f)))
    # GLIDE on BENCH: every direction at least 5 times on both cards at 0.96 - 1.04, ten phases each
    mins = {}
    for herc in (0, 1):
        for r in (96, 97, 98, 99, 100, 101, 102, 103, 104):
            for ph in range(10):
                d, gp = glide_run(bench, herc, r / 100.0, ph / 10.0)
                for k in DIRS:
                    mins[(herc, k)] = min(mins.get((herc, k), 99), d.get(k, 0))
    for herc in (0, 1):
        print("    GLIDE on BENCH, %s, the fewest of each direction over 0.96 - 1.04 x ten phases: %s" % (
            "Hercules" if herc else "CGA", " ".join("%s %d" % (n, mins[(herc, k)]) for n, k in zip(
                ("UL", "U", "UR", "L", "R", "DL", "D", "DR"), DIRS))))
    res.append(("8 GLIDE (bbcourse.Glide, the four-frame travel test) on BENCH: every one of the eight directions at "
                "least 5 times on both cards at step rates 0.96 - 1.04 (ten phases each; fewest %d)"
                % min(mins.values()), min(mins.values()) >= 5))


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
    # 4. the tables the guest reads, against 128.11.6.2's table written out here
    want_st = bytes([4, 6, 6, 205, 1, 0, 1, 205, 2, 5, 6, 102, 4, 6, 6, 224,
                     2, 8, 5, 38, 1, 0, 1, 38, 2, 5, 5, 19, 2, 8, 5, 224,
                     6, 5, 10, 102, 1, 0, 2, 102, 3, 5, 10, 51, 6, 5, 10, 224])
    want_mt = bytes([4, 6, 205, 96, 128, 6, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     2, 8, 38, 32, 128, 5, 160, 0, 1, 55, 176, 1, 0, 0, 0, 0,
                     6, 5, 102, 64, 96, 10, 176, 0, 2, 24, 40, 2, 0, 0, 0, 0])
    res.append(("4 BZ_SURFTAB (48 bytes: force, drag shift, brake, floor restitution of each material on normal, ice, "
                "sand and a mat) and BZ_MATTAB (3 x 16) are 128.11.6.2's and 128.11.5.1's tables",
                surftab() == want_st and mattab() == want_mt))
    t = htab()
    for k, c in enumerate(courses):
        tag = "%s" % c.name
        # 3. the picture, the CGA's and the Hercules's through htab()
        try:
            dc = _decode(c.cga)
            ok = all(bytes(dc[y]) == bytes(c.pic[y]) for y in range(c.lines))
        except CourseError as e:
            print("    " + str(e))
            ok = False
        pt = c.part

        def herc_ok(hpart):
            blkoff = pt["blkoff"]
            for y in range(c.lines):
                for bx in range(c.cols):
                    off = pt["map"][(y >> 3) * c.cols + bx]
                    w = hpart[off + 2 * (y & 7):off + 2 * (y & 7) + 2]
                    if bytes(w) != herc_bytes(c.pic[y][bx * 8:bx * 8 + 8], line=y, col0=bx * 8):
                        return False
            return True
        res.append(("3 %s: the map and the CGA blocks decode to the picture; the Hercules picture is the CGA blocks "
                    "through htab() (bz_hgen's algorithm), equal to herc_bytes of it; every map word a block offset "
                    "inside the part; block 0 black; ROWB = 2 COLS" % tag,
                    ok and herc_ok(c.herc) and pt["rowb"] == 2 * pt["cols"]
                    and c.cga[pt["blkoff"]:pt["blkoff"] + 16] == bytes(16)))
        bad = bytearray(c.cga)
        w0 = struct.unpack_from("<H", bad, HDR + 2 * 37)[0]
        alt = next(HDR + 2 * i for i, w in enumerate(pt["map"]) if w != w0)
        struct.pack_into("<H", bad, HDR + 2 * 37, struct.unpack_from("<H", bad, alt)[0])
        try:
            dd = _decode(bytes(bad))
            caught = any(bytes(dd[y]) != bytes(c.pic[y]) for y in range(c.lines))
        except CourseError:
            caught = True
        res.append(("3 %s negative control: one map word moved fails the decode" % tag, caught))
        if k == 0:
            tb = bytearray(t)
            blk = c.cga[pt["blkoff"] + 16:pt["blkoff"] + 32]
            tb[256 * 0 + blk[0]] ^= 0x03
            import bonanza_assets as _BA
            old = _BA.htab
            _BA.htab = lambda: bytes(tb)
            try:
                caught = not herc_ok(herc_translate_course(c.cga))
            finally:
                _BA.htab = old
            res.append(("3 %s negative control: one htab() entry flipped fails the Hercules picture" % tag, caught))
        # 4. the grid against the geometry
        g = Grid(c.cga)
        okp = okk = okv = oks = oksf = True
        for (wx, wy), tl in c.tiles.items():
            cl = g.cell(wx, wy)
            zt, zr, zb, zl = (4 * v for v in tl.corners())
            if zb != zr + zl - zt:
                okp = False
            for u in range(16):
                for v in range(16):
                    if 4 * (16 * zt + (zr - zt) * u + (zl - zt) * v) != 16 * Physics.h4(cl, u, v):
                        okp = False
            if cl[3] != tl.kind:
                okk = False
            safe = (tl.kind == KIND_FLOOR and tl.sx == 0 and tl.sy == 0
                    and all((wx + dx, wy + dy) in c.tiles for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
            if bool(cl[4] & FL_SAFE) != safe:
                oks = False
        # the surfaces as the statements set them, read back independently
        want_s = {}
        for surf, shape, _ln in c.src.surfaces:
            for tt in shape:
                if tt in c.tiles:
                    want_s[tt] = surf
        for tt in c.tiles:
            if g.cell(*tt)[5] != want_s.get(tt, SURF_NORMAL):
                oksf = False
        for r in range(g.nrows):
            sR = g.smin + r
            for kk in range(-2, g.kw + 2):
                aC = g.amin + 2 * kk + (sR & 1)
                wx, wy = (sR + aC) >> 1, (sR - aC) >> 1
                if (wx, wy) in c.tiles:
                    continue
                cl = g.cell(wx, wy)
                near = [tt for tt in _cheb(c.tiles, wx, wy, 2)]
                want = (min(min(tt.corners()) for tt in near) - 6) if near else Z_OPEN
                if cl[3] != KIND_VOID or cl[0] != want or cl[4] & FL_SAFE or cl[5]:
                    okv = False
        res.append(("4 %s: at all 256 integer points of every solid cell h4 is the plane the renderer drew" % tag, okp))
        res.append(("4 %s: kinds are the rooms' styles; VOID is NEAR with the kill height or OPEN exactly where no "
                    "solid cell is within two tiles; SAFE exactly where 128.10.4.3 says; every surface nibble as the "
                    "statements set it (%d tiles not normal)" % (tag, sum(1 for v in want_s.values() if v)),
                    okk and okv and oks and oksf))
        # OCCG: never without OCC; and sound - a grounded ball anywhere in a cell that lays a record has it
        occg_ok = all(not (v[3] & FL_OCCG) or v[3] & FL_OCC for v in c.cells.values())
        tried = missed = 0
        for (wx, wy), cl in c.cells.items():
            if not cl[3] & FL_OCC or (cl[2] & 15) not in (KIND_FLOOR, KIND_GOAL):
                continue
            for u in range(0, 16, 2):
                for v in range(0, 16, 2):
                    for fr in (0, 128):
                        gx, gy = ((16 * wx + u) << 8) + fr, ((16 * wy + v) << 8) + fr
                        gz = Physics.h4(g.cell(wx, wy), u, v) << 6
                        px = ((gx - gy) >> 8) + c.x0 - 8
                        py = ((((gx + gy) >> 1) - gz) >> 8) + c.y0 - 13
                        tried += 1
                        if laid_at(c, px, py, wx + wy, gz >> 8, 0) and not cl[3] & FL_OCCG:
                            missed += 1
        res.append(("4 %s: OCCG (%d cells) never without OCC, and set wherever a grounded ball at its floor lays a "
                    "record (%d grounded positions of OCC cells tried, %d missed)" % (
                        tag, sum(1 for v in c.cells.values() if v[3] & FL_OCCG), tried, missed),
                    occg_ok and missed == 0))
        # 5. the occluders, on the MERGED records
        recs = c.records
        srt = all((x["brow"], x["col"], x["s"]) <= (y["brow"], y["col"], y["s"]) for x, y in zip(recs, recs[1:]))
        seen = set()
        dup = False
        for r in recs:
            if seen & r["pix"]:
                dup = True
            seen |= r["pix"]
        span = 0
        for r in c.raw:
            tops = [c.tbuf[y][x] for (x, y) in r["pix"]]
            span = max(span, max(tops) - min(tops))
            if r["top"] != max(tops) or any(c.sbuf[y][x] != r["s"] for (x, y) in r["pix"]):
                dup = True
        masks_unique = len(c.masks) == len(set(c.masks))
        res.append(("5 %s: OCCIDX non-decreasing to the records' end, records sorted, no pixel in two records, no "
                    "unmerged record's tops spanning over %d px (most %d), masks deduplicated (%d for %d records)"
                    % (tag, BAND, span, len(c.masks), len(recs)), srt and not dup and span <= BAND and masks_unique))
        tried, diff = merge_exact(c.raw, c.records, c.queries)
        res.append(("5 %s: the merge is exact - for every block and every (s_b, z_b + m) of its query set the %d "
                    "merged records lay exactly the pixels the %d unmerged ones lay (%d queries%s)" % (
                        tag, len(c.records), len(c.raw), tried, "" if diff is None else ", differs at %s" % (diff,)),
                    diff is None))
        if k == 0:
            key = next(kk for kk, v in sorted(c.raw_block.items()) if v >= 2)
            rr = [r for r in c.raw if (r["brow"], r["col"]) == key]
            Q = sorted(c.queries.get(key, ()))
            pair = next(((i, j) for i in range(len(rr)) for j in range(i + 1, len(rr))
                         if _verdict(rr[i], Q) != _verdict(rr[j], Q) and any(_verdict(rr[i], Q))
                         and any(_verdict(rr[j], Q))), None)
            if pair:
                forced = merge_records(c.raw, c.queries, _force=(key, pair[0], pair[1]))
                res.append(("5 %s negative control: two records of block %s with different verdicts merged by force "
                            "fail the merge's check" % (tag, key), merge_exact(c.raw, forced, c.queries)[1] is not None))
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
                            if any(p in r["pix"] and Bp[p] != v for p, v in ball_pixels(px, py).items() if p in Bp):
                                first_laid = (r, px, py, rc.s, z, air)
                                break
        res.append(("5 %s: the ball composited through the MERGED RECORDS equals the per-pixel buffer's (tops raised to "
                    "the unmerged records'), at the centre of every reachable cell, lowest and highest, both air "
                    "states (%d positions, %d differ)" % (tag, tried, mism), mism == 0))
        fmism = fgate = ftried = 0
        fneg = None
        for rc in c.reach:
            if rc.zhi <= rc.zlo:
                continue
            for z in sorted({rc.zlo, rc.zhi - 1}):
                gx, gy, gz = (16 * rc.wx) << 8, (16 * rc.wy) << 8, (z << 8) + 128
                px = ((gx - gy) >> 8) + c.x0 - 8
                py = (((gx + gy) >> 1) - gz >> 8) + c.y0 - 13
                for air in ((1,) if rc.kind == KIND_VOID else (0, 1)):
                    ftried += 1
                    if composite(c, px, py, rc.s, z, air, "records") != composite(c, px, py, rc.s, z, air, "pixels"):
                        fmism += 1
                    if laid_at(c, px, py, rc.s, z, air):
                        if not c.cells[(rc.wx, rc.wy)][3] & FL_OCC:
                            fgate += 1
                        elif fneg is None:
                            fneg = (rc, px, py, z, air)
        res.append(("5 %s: at the fractional-height line the records composite as the pixels and every position that "
                    "lays one is in an OCC cell (%d positions, %d differ, %d ungated)" % (tag, ftried, fmism, fgate),
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
                     if v[2] & 15 != KIND_WALL)
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
        print("    %s: Y0 %d - the least reachable footprint top is line %d, cell (%d, %d) at %d px, set by %s; %d "
              "rounds to settle; the geometry's top is line %d.  Longest reachable fall onto a floor %d px (cell "
              "(%d, %d)), into a kill %d px (cell (%d, %d)); mean zhi - zlo %.1f px" % (
                  tag, c.y0, c.ftop + c.y0, top_rc.wx, top_rc.wy, top_rc.zhi,
                  ("a %s of cell %s" % (top_rc.src[1], top_rc.src[0])) if top_rc.src else "its own floor", c.rounds,
                  c.gtop + c.y0, fall.zhi - fall.zlo, fall.wx, fall.wy, void.zhi - void.zlo, void.wx, void.wy,
                  sum(rc.zhi - rc.zlo for rc in c.reach) / float(len(c.reach))))
        res.append(("6 %s: every reachable footprint inside the picture; Y0 the least that does it (line %d); the "
                    "reach settled in %d rounds (at most %d)" % (tag, least, c.rounds, REACH_ROUNDS),
                    inside and least == 0 and c.rounds <= REACH_ROUNDS))
    # 7. physics, 8. the routes
    t0 = __import__("time").time()
    gaps = ledge_gaps()
    print("    the ledge-gap table (SPEC.md 128.11.5.3), from Physics (circle and margin included), %.1f s:"
          % (__import__("time").time() - t0))
    for line in gap_table_text(gaps).split("\n"):
        print("      " + line)
    res.append(("7 the ledge-gap table: a 6-unit fall reaches a ledge 2 units up from 15 to 67.5 gu, 3 units up "
                "from 22.5 to 60, and no fall of 2 units reaches 2 up; no window has a hole",
                gaps[(6, 2)][:2] == (15.0, 67.5) and gaps[(6, 3)][:2] == (22.5, 60.0) and gaps[(2, 2)] is None
                and all(w is None or w[2] == 0 for w in gaps.values())))
    if "FIRST" in byname:
        _physics_checks(byname["FIRST"], res, byname.get("TRIAL"))
    if "BENCH" in byname:
        _route_checks(byname["BENCH"], res, byname.get("TRIAL"), byname.get("FIRST"))
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
