#!/usr/bin/env python3
"""BONANZA's course compiler, waves 1 - 3 (SPEC.md 128.10.3 - 128.10.7, 128.11, 128.12).

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

Wave 3 (SPEC.md 128.12): `tube` and `prop` statements; the prop table after
the grid (BZC1 +28 / +30: records, pose maps, tube segments, the platform's
sprite), the grid's OBS bit, each lane's poses rendered into the one block
pool, the course's IDENTITY at BZG1 +18, and every refusal and bound of
128.12.3.3 and 128.12.4.6 - the exits checked by the model, the lanes'
occluder verdicts checked over every pose.

`Physics` is SPEC.md 128.11.8's step (wave 1's, 128.10.7.3, as wave 2
changes it, with wave 3's obstacles, 128.12.6.5), integer-exact: the
guest's bzphys.inc is written to do exactly what it does, and the
bonanzaphys row compares the two at every frame (state3() is wave 3's
part of the state).
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

RESERVED = ("edge", "checkpoint", "pad", "shape")   # prop and tube are wave 3's (SPEC.md 128.12.3.3)

# --- wave 3: props (SPEC.md 128.12.3, 128.12.6), PROVISIONAL constants -----------
PK_TUBE, PK_WINDMILL, PK_BUMPER, PK_PLATFORM = 1, 2, 3, 4      # record +0
PK_NAMES = {PK_TUBE: "tube", PK_WINDMILL: "windmill", PK_BUMPER: "bumper", PK_PLATFORM: "platform"}
PF_UNDER, PF_LANE = 1, 2      # record +1: UNDERSIDE (reserved, refused), LANE
FL_OBS = 8                    # grid +3 bit 3: the cell belongs to a prop
FL_EDGES = 16 | 32            # bits 4 - 5: RESERVED for `edge`
PROPREC = 32                  # bytes a record
PROP_MAX = 16                 # wave 3's per-prop arrays (bz_ldrw, bz_lage, bz_pkick)
SEGREC = 16                   # bytes a tube segment
SEG_MAX = 8
TK_KEEP, TK_LAUNCH, TK_DROP = 0, 1, 2
TK_NAMES = ("keep", "launch", "drop")
DIR_NAMES = ("+x", "-x", "+y", "-y")             # record +17's codes
DIR_VEC = ((1, 0), (-1, 0), (0, 1), (0, -1))
TMIN = 64                     # BZ_TMIN: KEEP's and DROP's least exit speed
E_GATE = 160                  # a windmill blade's restitution, every ball (0.625)
WM_PERIODS = (32, 64, 128, 256)
WM_POSES = 8                  # a rotor's poses (shift = log2(P) - 3)
KICK_K = 384                  # a bumper's least normal speed out (1.5 gu a step; the owner's preview, O23)
KICK_A = 64                   # ...and what it adds to the rail's rebound
PRAD = 6                      # BZ_PRAD: a post's radius, gu
POST_H = 8                    # a post's height, px (1 unit)
PLITF = 8                     # a kicked post stays LIT this many frames ON THE GLASS (display, 128.12.6.3)
OCT_N = 11                    # the octant table's reach: max(|du|, |dv|) <= 11
PL_PERIODS = (64, 128, 256)
PL_LMAX = 8                   # a LIFT's rise, units (SPEC.md 128.12.6.4)
PL_VMAX = 192                 # a lift's v, 1/256 px a step (0.75 lines a step), a multiple of 64
PL_W, PL_H = 32, 18           # its sprite: 4 words x 18 lines (16 of top, 2 of lip)
PL_SPR = 2 * 2 * PL_W // 4 * PL_H              # two parity copies x (mask + frame): 576
LANE_WMAX, LANE_HMAX = 4, 3   # a lane: BZ_BOXW words x BZ_BOXH / 8 block rows
LANE_PMAX = 16
WIN_LANES = 6                 # lanes meeting any window (SPEC.md 128.12.4.6)
RANGE_LANES = 8               # lanes in the walk's range
ROTOR_CHG = 2                 # rotor pose changes on a step, and in two consecutive
HEDGE = 16                    # BZ_HEDGE: the heavy rule's edge zone, lines (and 24 px)
WLAG = 8                      # BZ_WLAG: frames due and shown before a lane is late
WPRO = 3                      # BZ_WPRO: frames a WHEEL candidate is due before it is PROMOTED
                              # to the contact slot on a frame that allows a contact lane, and
WPRF = 5                      # BZ_WPRF on any frame - and a waiting contact candidate takes
                              # the slot anyway (SPEC.md 128.12.18, 128.13.9)


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
        self.tubes = []             # wave 3: [dict], in file order (SPEC.md 128.12.3.3)
        self.props = []             # [dict]: windmill, bumper, platform


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


def _word(toks, i, where):
    if i >= len(toks) or toks[i][0] != 'w':
        raise CourseError("%s: a word is missing" % where)
    return toks[i][1]


def _parse_tube(toks, where, ln):
    """tube keep|launch|drop <iwx> <iwy> <owx> <owy> [via <wx> <wy>]... [out D]
    [speed <gvx> <gvy> <gvz>] [height <h>]  (SPEC.md 128.12.3.3)"""
    if len(toks) < 6 or toks[1][1] not in TK_NAMES:
        raise CourseError("%s: tube takes keep|launch|drop <iwx> <iwy> <owx> <owy> ..." % where)
    t = {"line": ln, "sub": TK_NAMES.index(toks[1][1]),
         "inn": (_int(toks[2], where, "iwx"), _int(toks[3], where, "iwy")),
         "out": (_int(toks[4], where, "owx"), _int(toks[5], where, "owy")),
         "via": [], "dir": None, "speed": None, "height": None}
    i = 6
    while i < len(toks):
        w = _word(toks, i, where)
        if w == "via" and i + 3 <= len(toks):
            t["via"].append((_int(toks[i + 1], where, "via wx"), _int(toks[i + 2], where, "via wy")))
            i += 3
        elif w == "out" and i + 2 <= len(toks) and t["dir"] is None:
            d = _word(toks, i + 1, where)
            if d not in DIR_NAMES:
                raise CourseError("%s: out is +x, -x, +y or -y, not %r" % (where, d))
            t["dir"] = DIR_NAMES.index(d)
            i += 2
        elif w == "speed" and i + 4 <= len(toks) and t["speed"] is None:
            if t["sub"] != TK_LAUNCH:
                raise CourseError("%s: speed is a LAUNCH tube's alone" % where)
            t["speed"] = tuple(_int(toks[i + k], where, "speed") for k in (1, 2, 3))
            i += 4
        elif w == "height" and i + 2 <= len(toks) and t["height"] is None:
            if t["sub"] != TK_DROP:
                raise CourseError("%s: height is a DROP tube's alone" % where)
            t["height"] = _height2(toks[i + 1], where)
            i += 2
        else:
            raise CourseError("%s: unknown or repeated tube clause %r" % (where, w))
    if t["sub"] == TK_LAUNCH and t["speed"] is None:
        raise CourseError("%s: a LAUNCH tube needs its speed <gvx> <gvy> <gvz>" % where)
    if t["sub"] == TK_DROP and t["height"] is None:
        raise CourseError("%s: a DROP tube needs its height <h>" % where)
    if t["speed"] is not None:
        gvx, gvy, gvz = t["speed"]
        if abs(gvx) > VMAXG or abs(gvy) > VMAXG or not 0 <= gvz <= VZMAX:
            raise CourseError("%s: a LAUNCH speed %s is over the caps (|gvx|, |gvy| <= %d, 0 <= gvz <= %d)"
                              % (where, t["speed"], VMAXG, VZMAX))
    if t["height"] is not None and t["height"] < 2:
        raise CourseError("%s: a DROP height under 1 unit" % where)
    if t["dir"] is not None and t["sub"] == TK_DROP and t["dir"] not in (0, 2):
        raise CourseError("%s: a DROP's mouth faces %s: it must face +x or +y (a wall shows only those)"
                          % (where, DIR_NAMES[t["dir"]]))
    return t


def _pow2(v):
    return v > 0 and v & (v - 1) == 0


def _parse_prop(toks, where, ln):
    """prop windmill|bumper|platform ... (SPEC.md 128.12.3.3)"""
    if len(toks) < 4 or toks[1][1] not in ("windmill", "bumper", "platform"):
        raise CourseError("%s: prop takes windmill, bumper or platform" % where)
    kind = toks[1][1]
    p = {"line": ln, "kind": {"windmill": PK_WINDMILL, "bumper": PK_BUMPER, "platform": PK_PLATFORM}[kind],
         "at": (_int(toks[2], where, "wx"), _int(toks[3], where, "wy")), "seed": None}
    i = 4
    if kind == "platform":
        if len(toks) < 5:
            raise CourseError("%s: prop platform takes <wx> <wy> <L>" % where)
        p["L"] = _int(toks[4], where, "L")
        if not 1 <= p["L"] <= PL_LMAX:
            raise CourseError("%s: a lift's rise L is 1 - %d units, not %d" % (where, PL_LMAX, p["L"]))
        i = 5
    allowed = {"windmill": ("period", "closed", "seed"), "bumper": ("kick", "seed"),
               "platform": ("period", "dwell", "seed")}[kind]
    seen = set()
    while i < len(toks):
        w = _word(toks, i, where)
        if w not in allowed or w in seen:
            raise CourseError("%s: unknown or repeated %s clause %r" % (where, kind, w))
        seen.add(w)
        if w == "closed":
            if i + 3 > len(toks):
                raise CourseError("%s: closed takes <c0> <c1>" % where)
            p["closed"] = (_int(toks[i + 1], where, "c0"), _int(toks[i + 2], where, "c1"))
            i += 3
            continue
        if i + 2 > len(toks):
            raise CourseError("%s: %s takes a number" % (where, w))
        p[w] = _int(toks[i + 1], where, w)
        i += 2
    if kind == "bumper" and "seed" in seen:
        raise CourseError("%s: a bumper takes no seed (it lights by kicks)" % where)
    if kind == "bumper":
        p.setdefault("kick", KICK_K)
        if not 1 <= p["kick"] <= VMAXG:
            raise CourseError("%s: a kick of %d is outside 1 - %d" % (where, p["kick"], VMAXG))
    if kind == "windmill":
        P = p.setdefault("period", 64)
        if P not in WM_PERIODS:
            raise CourseError("%s: a windmill's period %d is not a power of two of 32 - 256" % (where, P))
        pl = P // WM_POSES
        c0, c1 = p.setdefault("closed", (3 * P // 8, 5 * P // 8))
        if not (0 <= c0 < c1 <= P and c1 <= 255) or c0 % pl or c1 % pl:
            raise CourseError("%s: a closed window %d %d is not on pose boundaries (%d steps) inside the period %d"
                              % (where, c0, c1, pl, P))
    if kind == "platform":
        P = p.setdefault("period", 256)
        if P not in PL_PERIODS:
            raise CourseError("%s: a platform's period %d is not a power of two of 64 - 256" % (where, P))
        W = p.setdefault("dwell", P // 8)
        if not 0 <= W < P // 4:
            raise CourseError("%s: a dwell of %d leaves the platform no time to move" % (where, W))
    if p["seed"] is not None and not 0 <= p["seed"] < p["period"]:
        raise CourseError("%s: a seed of %d is not under the period %d" % (where, p["seed"], p["period"]))
    return p


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
        elif st == "tube":
            src.tubes.append(_parse_tube(toks, where, ln))
        elif st == "prop":
            src.props.append(_parse_prop(toks, where, ln))
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
# wave 3: the props (SPEC.md 128.12.3, 128.12.6), checked against the tiles
# =============================================================================

def _dir_of(dx, dy):
    return 0 if dx > 0 else 1 if dx < 0 else 2 if dy > 0 else 3


def _h4t(t, u, v):
    """a tile's floor at its point (u, v), quarter px (Physics.h4's)"""
    return 16 * t.z0 + t.sx * u + t.sy * v


def _rnd(n, d):
    """n / d rounded half up (integers, d > 0)"""
    return (2 * n + d) // (2 * d)


def _ghost_bxy(gx, gy, gz):
    """the screen state the ghost derives (Physics._derive, without X0 / Y0)"""
    return gx - gy, ((gx + gy) >> 1) - gz


def _segments(points, zs):
    """the tube's segments (SPEC.md 128.12.6.1): each leg's m the least that
    keeps the ghost inside 3 px and 3 lines a step - checked on the 24.8 steps
    the guest takes, the snap at the segment's end included - and its
    increments round(256 D / m).  points: gu (integers), zs: px at each point.
    -> [dict m incx incy incz ex ey ez]"""
    segs = []
    x, y, z = points[0][0] << 8, points[0][1] << 8, zs[0] << 8
    for (ax, ay), (bx, by), za, zb in zip(points, points[1:], zs, zs[1:]):
        dgx, dgy, dz = bx - ax, by - ay, zb - za
        m = max(1, -(-abs(dgx - dgy) // 3), -(-abs(dgx + dgy - 2 * dz) // 6))
        while True:
            inc = (_rnd(256 * dgx, m) if dgx >= 0 else -_rnd(-256 * dgx, m),
                   _rnd(256 * dgy, m) if dgy >= 0 else -_rnd(-256 * dgy, m),
                   _rnd(256 * dz, m) if dz >= 0 else -_rnd(-256 * dz, m))
            cx, cy, cz = x, y, z
            ok = True
            b0 = _ghost_bxy(cx, cy, cz)
            for k in range(m):
                if k == m - 1:
                    cx, cy, cz = bx << 8, by << 8, zb << 8
                else:
                    cx, cy, cz = cx + inc[0], cy + inc[1], cz + inc[2]
                b1 = _ghost_bxy(cx, cy, cz)
                if abs(b1[0] - b0[0]) > 768 or abs(b1[1] - b0[1]) > 768:
                    ok = False
                    break
                b0 = b1
            if ok:
                break
            m += 1
        segs.append({"m": m, "incx": inc[0], "incy": inc[1], "incz": inc[2], "ex": bx, "ey": by, "ez": zb})
        x, y, z = bx << 8, by << 8, zb << 8
    return segs


def _fall_steps(px):
    """the steps a ball takes to fall px from rest"""
    z, g, n = px * 256, 0, 0
    while z > 0:
        g = max(g - G, -VZMAX)
        z += g
        n += 1
    return n


def _units(z2):
    """a height in half units as the course file writes it"""
    return ("%d" % (z2 // 2)) if z2 % 2 == 0 else ("%.1f" % (z2 / 2.0))


def plat_v(L, P, W):
    """SPEC.md 128.12.6.4: v = 64 ceil(32 L / (P / 2 - 2 W)), the least multiple
    of 64 (a quarter pixel) that rises 8 L px in the half period's moving steps"""
    return 64 * -(-(32 * L) // (P // 2 - 2 * W))


def plat_pos(pr, n):
    """the LIFT's rise above its low top at step n, 1/256 px (128.12.6.4): a
    multiple of 64, so the top is a whole quarter pixel"""
    P = pr["mask"] + 1
    H = P // 2
    m = (n + pr["seed"]) & pr["mask"]
    q = m if m < H else P - 1 - m
    return min(pr["pmax"], max(0, q - pr["W"]) * pr["v"])


def build_props(src, tiles, fname):
    """-> [prop dict], in the course file's order: the tubes (a windmill's is
    its tube's record) and the props.  Every check of 128.12.3.3 that the
    tiles alone decide; the model's exits, the art's and the bounds' come
    later, once the part exists."""
    f = fname
    props = []
    owner = {}

    def claim(cell, ln, what):
        if cell in owner:
            raise CourseError("%s:%d: cell (%d, %d) already belongs to the prop on line %d (one prop a cell)"
                              % (f, ln, cell[0], cell[1], owner[cell]))
        owner[cell] = ln

    def kind(cell):
        t = tiles.get(cell)
        return t.kind if t else KIND_VOID
    for tb in src.tubes:
        ln = tb["line"]
        pts = [tb["inn"]] + tb["via"] + [tb["out"]]
        for what, c in (("IN", tb["inn"]), ("OUT", tb["out"])):
            if kind(c) != KIND_FLOOR:
                raise CourseError("%s:%d: the tube's %s cell (%d, %d) is not a FLOOR" % (f, ln, what, c[0], c[1]))
        legs = []
        body = []
        for a, b in zip(pts, pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            if (dx != 0) == (dy != 0):
                raise CourseError("%s:%d: the tube's leg (%d, %d) -> (%d, %d) is not along a tile axis"
                                  % (f, ln, a[0], a[1], b[0], b[1]))
            d = _dir_of(dx, dy)
            legs.append(d)
            ux, uy = DIR_VEC[d]
            c = a
            while True:
                c = (c[0] + ux, c[1] + uy)
                if c == b:
                    break
                body.append(c)
            if b != tb["out"]:
                body.append(b)
        if len(legs) > SEG_MAX:
            raise CourseError("%s:%d: %d legs, over %d segments" % (f, ln, len(legs), SEG_MAX))
        for c in body:
            if kind(c) != KIND_WALL:
                raise CourseError("%s:%d: the tube's body cell (%d, %d) is not a WALL" % (f, ln, c[0], c[1]))
        if len(set(body)) != len(body) or tb["inn"] in body or tb["out"] in body or tb["inn"] == tb["out"]:
            raise CourseError("%s:%d: the tube's path crosses itself" % (f, ln))
        dr = tb["dir"] if tb["dir"] is not None else legs[-1]
        if tb["sub"] == TK_DROP and dr not in (0, 2):
            raise CourseError("%s:%d: a DROP's mouth faces %s: it must face +x or +y (a wall shows only those)"
                              % (f, ln, DIR_NAMES[dr]))
        if tb["sub"] == TK_DROP and (not body or body[-1] != (tb["out"][0] - DIR_VEC[dr][0],
                                                             tb["out"][1] - DIR_VEC[dr][1])):
            raise CourseError("%s:%d: a DROP's mouth must be on the face of the body's last wall, behind OUT "
                              "along %s" % (f, ln, DIR_NAMES[dr]))
        if tb["sub"] == TK_KEEP:
            o = tb["out"]
            nx = (o[0] + DIR_VEC[dr][0], o[1] + DIR_VEC[dr][1])
            tn, to = tiles.get(nx), tiles[o]
            if tn is None or tn.kind not in (KIND_FLOOR, KIND_GOAL):
                raise CourseError("%s:%d: a KEEP exit's next cell (%d, %d) along %s is not a FLOOR"
                                  % (f, ln, nx[0], nx[1], DIR_NAMES[dr]))
            ea, eb = {0: ((1, 0), (1, 1)), 1: ((0, 0), (0, 1)), 2: ((0, 1), (1, 1)), 3: ((0, 0), (1, 0))}[dr]
            na, nb = {0: ((0, 0), (0, 1)), 1: ((1, 0), (1, 1)), 2: ((0, 0), (1, 0)), 3: ((0, 1), (1, 1))}[dr]
            if tn.corner(*na) > to.corner(*ea) + 1 or tn.corner(*nb) > to.corner(*eb) + 1:
                raise CourseError("%s:%d: a KEEP exit's next cell (%d, %d) is too high to roll onto"
                                  % (f, ln, nx[0], nx[1]))
        claim(tb["inn"], ln, "IN")
        props.append({"kind": PK_TUBE, "line": ln, "at": tb["inn"], "sub": tb["sub"], "inn": tb["inn"],
                      "out": tb["out"], "pts": pts, "legs": legs, "body": body, "dir": dr,
                      "speed": tb["speed"] or (0, 0, 0), "h2": tb["height"], "mask": 0, "shift": 0, "seed": 0,
                      "eG": 0, "door": None, "closed": (0, 0)})
    tubes_at = {p["inn"]: p for p in props}
    nwm = sum(1 for p in src.props if p["kind"] == PK_WINDMILL)
    npl = sum(1 for p in src.props if p["kind"] == PK_PLATFORM)
    iw = ip = 0
    for sp in src.props:
        ln, at = sp["line"], sp["at"]
        if sp["kind"] == PK_WINDMILL:
            tb = tubes_at.get(at)
            if tb is None or tb["sub"] != TK_KEEP or tb["kind"] != PK_TUBE:
                raise CourseError("%s:%d: a windmill at (%d, %d) without a KEEP tube whose IN is there"
                                  % (f, ln, at[0], at[1]))
            if tb["legs"][0] not in (1, 3):
                raise CourseError("%s:%d: a windmill entered along %s: its tube's first leg must run -x or -y "
                                  "(a face the viewer sees)" % (f, ln, DIR_NAMES[tb["legs"][0]]))
            d = DIR_VEC[tb["legs"][0]]
            wall = (at[0] + d[0], at[1] + d[1])
            if kind(wall) != KIND_WALL:
                raise CourseError("%s:%d: a windmill without a wall behind its doorway at (%d, %d)"
                                  % (f, ln, wall[0], wall[1]))
            P = sp["period"]
            shift = (P // WM_POSES).bit_length() - 1
            if sp["seed"] is None:
                pl = 1 << shift
                seed = (iw * P // nwm) // pl * pl + iw * pl // nwm
            else:
                seed = sp["seed"]
            iw += 1
            tb.update(kind=PK_WINDMILL, mask=P - 1, shift=shift, seed=seed, eG=E_GATE,
                      door=tb["legs"][0], closed=sp["closed"], wline=ln, seed_given=sp["seed"] is not None)
        elif sp["kind"] == PK_BUMPER:
            t = tiles.get(at)
            if t is None or t.kind != KIND_FLOOR:
                raise CourseError("%s:%d: a bumper on (%d, %d), not a FLOOR" % (f, ln, at[0], at[1]))
            if t.sx or t.sy:
                raise CourseError("%s:%d: a bumper on (%d, %d), a ramp: a post stands on a flat floor"
                                  % (f, ln, at[0], at[1]))
            claim(at, ln, "post")
            props.append({"kind": PK_BUMPER, "line": ln, "at": at, "mask": 0, "shift": 0, "seed": 0,
                          "K": sp["kick"], "KA": KICK_A, "cx": 16 * at[0] + 8, "cy": 16 * at[1] + 8,
                          "top": 4 * t.z0 + POST_H})
        else:
            L, P, W = sp["L"], sp["period"], sp["dwell"]
            A = at                                      # THE SHAFT: one VOID cell
            if A in tiles:
                raise CourseError("%s:%d: the lift's shaft (%d, %d) is not VOID" % (f, ln, A[0], A[1]))
            rims = [tiles[c] for c in ((A[0] - 1, A[1]), (A[0] + 1, A[1]), (A[0], A[1] - 1), (A[0], A[1] + 1))
                    if kind(c) == KIND_FLOOR]
            if not rims or any(r.sx or r.sy for r in rims):
                raise CourseError("%s:%d: the lift's rims are not flat FLOORs (or it has none)" % (f, ln))
            lo = min(r.z0 for r in rims)
            if {r.z0 for r in rims} != {lo, lo + 2 * L}:
                raise CourseError("%s:%d: the lift's rims must stand at its two docks, %s and %s units (its "
                                  "low rim's and L %d over it), and at nothing else"
                                  % (f, ln, _units(lo), _units(lo + 2 * L), L))
            v = plat_v(L, P, W)
            if v > PL_VMAX:
                raise CourseError("%s:%d: the lift's v %d is over %d (a longer period or a shorter dwell)"
                                  % (f, ln, v, PL_VMAX))
            if ip:                              # the guest tracks ONE lift (bzwheel.inc's
                raise CourseError("%s:%d: a second lift: a course holds one (SPEC.md 128.12.4.6)"
                                  % (f, ln))    # bz_pidx, bz_pline, its sprite)
            seed = sp["seed"] if sp["seed"] is not None else ip * P // npl
            ip += 1
            claim(A, ln, "shaft")
            props.append({"kind": PK_PLATFORM, "line": ln, "at": A, "L": L, "W": W, "v": v,
                          "mask": P - 1, "shift": 0, "seed": seed, "h2": lo, "hP": 4 * lo, "hT": 4 * lo + 8 * L,
                          "pmax": 2048 * L, "track": [A]})
    if len(props) > PROP_MAX:
        raise CourseError("%s:%d: a %d%s prop, over the %d a course holds"
                          % (f, props[PROP_MAX]["line"], PROP_MAX + 1, "th", PROP_MAX))
    # the tubes' paths (the windmills' known now): gu points and px heights
    for p in props:
        if p["kind"] not in (PK_TUBE, PK_WINDMILL):
            continue
        tin, tout = tiles[p["inn"]], tiles[p["out"]]
        ix, iy = p["inn"]
        if p["kind"] == PK_WINDMILL:
            u0, v0 = (0, 8) if p["door"] == 1 else (8, 0)
        else:
            u0, v0 = 8, 8
        p["start"] = (16 * ix + u0, 16 * iy + v0)
        p["zin4"] = _h4t(tin, u0, v0)                   # IN's floor there, quarter px
        zin = _h4t(tin, u0, v0) // 4 if _h4t(tin, u0, v0) % 4 == 0 else None
        zout = _h4t(tout, 8, 8) // 4
        p["zfloor_out"] = zout
        if p["sub"] == TK_DROP:
            zout += 4 * p["h2"]
        p["zexit"] = zout
        gpts = [p["start"]] + [(16 * x + 8, 16 * y + 8) for (x, y) in p["pts"][1:]]
        dist = [0]
        for a, b in zip(gpts, gpts[1:]):
            dist.append(dist[-1] + abs(b[0] - a[0]) + abs(b[1] - a[1]))
        z0 = _h4t(tin, u0, v0) / 4.0
        zs = [None] + [int(math.floor(z0 + (zout - z0) * dist[k] / dist[-1] + 0.5)) for k in range(1, len(gpts))]
        zs[-1] = zout
        # segment 0 starts at IN's floor exactly (24.8): its increments run
        # from there; a fractional IN floor (a ramp's half pixel) is refused
        if zin is None:
            raise CourseError("%s:%d: the tube's IN floor at its start is not a whole pixel" % (f, p["line"]))
        zs[0] = zin
        p["gpts"], p["zs"] = gpts, zs
        p["segs"] = _segments(gpts, zs)
        p["T"] = sum(s["m"] for s in p["segs"])
    return props


def prop_cells(props):
    """{cell: prop index} of every OBS cell (SPEC.md 128.12.3.2)"""
    out = {}
    for i, p in enumerate(props):
        if p["kind"] == PK_PLATFORM:
            for c in p["track"]:
                out[c] = i
        else:
            out[p["at"]] = i
    return out


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


def build_reach(tiles, cells, fname="<course>", props=()):
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
    # wave 3 (SPEC.md 128.12.6.7): a LAUNCH exit, a DROP's fall, a post's top
    # and the platform's top over its track are launches too; the slab is a
    # floor the bounces see
    bfl = {}
    for p in props:
        if p["kind"] == PK_TUBE and p["sub"] == TK_LAUNCH:
            gvz = p["speed"][2]
            srcs.append((p["out"], p["zfloor_out"] + UP(gvz), RADIUS(gvz), "launch tube"))
        elif p["kind"] == PK_TUBE and p["sub"] == TK_DROP:
            srcs.append((p["out"], p["zexit"], max(3, -(-(_fall_steps(p["zexit"] - p["zfloor_out"]) * VMAXG)
                                                        // (256 * TILE))), "drop tube"))
        elif p["kind"] == PK_BUMPER:
            srcs.append((p["at"], p["top"] + UP(HOPMAX), RADIUS(HOPMAX), "post"))
        elif p["kind"] == PK_PLATFORM:            # a LIFT: a floor from hP to hT over its shaft
            for c in p["track"]:
                srcs.append((c, p["hT"] + UP(HOPMAX), RADIUS(HOPMAX), "lift"))
                bfl[c] = (p["hP"], p["hT"])
    for c, (h0, h1) in bfl.items():
        lo[c], hi[c] = h0, h1

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
        for k in sorted(set(sol) | set(bfl)):
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

    def __init__(self, w, h, owners=False):
        self.w, self.h = w, h
        self.rows = [bytearray(w) for _ in range(h)]
        self.sbuf = [array("h", [-32768]) * w for _ in range(h)]
        self.tbuf = [array("h", [0]) * w for _ in range(h)]
        # wave 3: the tile that drew each pixel last, 256 wx + wy (-1 none),
        # kept only for a course with a windmill (the house check, 128.12.3.3)
        self.obuf = [array("i", [-1]) * w for _ in range(h)] if owners else None

    def fill(self, sp, colour, s, top, owner=-1):
        """colour: an index or (x, y) -> index; top: (x, y) -> whole px"""
        ob = self.obuf
        for y, runs in sp.items():
            if not 0 <= y < self.h:
                raise CourseError("course pixel line %d outside the %d-line picture" % (y, self.h))
            row, sr, tr = self.rows[y], self.sbuf[y], self.tbuf[y]
            orow = ob[y] if ob is not None else None
            for a, b in runs:
                if a < 0 or b > self.w:
                    raise CourseError("course pixels %d .. %d outside the %d px picture" % (a, b, self.w))
                for x in range(a, b):
                    row[x] = colour(x, y) if callable(colour) else colour
                    sr[x] = s
                    tr[x] = top(x, y)
                    if orow is not None:
                        orow[x] = owner

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


def draw_ops(tiles, x0, deep=()):
    """-> [(spans at Y0 = 0, colour, s, top-maker, outline-left, tile)], back
    to front: each tile's two front faces, then its top (128.3's order).
    deep: cells (a tube's body, SPEC.md 128.12.6.1) whose face over the void
    hangs as deep as its other front face reaches at their shared corner, so
    a pipe's wall standing on a lower tier reads as one column, not a column
    with a bite out of one side"""
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
        bots = []
        for p, zp, q, zq, nb, which in faces:
            if nb is None:
                bots.append([zp - FACE8, zq - FACE8])
            else:
                bots.append([min(zp, nb[0]), min(zq, nb[1])])
        if (wx, wy) in deep:                        # B is the sw face's q and the se face's p
            if faces[0][4] is None and faces[1][4] is not None and bots[1][0] < bots[0][1]:
                d = bots[0][1] - bots[1][0]
                bots[0] = [bots[0][0] - d, bots[0][1] - d]
            if faces[1][4] is None and faces[0][4] is not None and bots[0][1] < bots[1][0]:
                d = bots[1][0] - bots[0][1]
                bots[1] = [bots[1][0] - d, bots[1][1] - d]
        for (p, zp, q, zq, nb, which), (lp, lq) in zip(faces, bots):
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


def render(tiles, ops, x0, y0, w, h, owners=False):
    cv = Canvas(w, h, owners)
    for sp0, which, s, mk, left, t, (wx, wy) in ops:
        sp = _shift(sp0, y0)
        own = 256 * wx + wy
        if which == "paint":                        # wave 3: a mark on what is drawn
            ink = mk(y0)
            for y, runs in sp.items():
                row = cv.rows[y]
                for a, b in runs:
                    for x in range(a, b):
                        c = ink(x, y)
                        if c is not None:
                            row[x] = c
            continue
        if which == "post":                         # wave 3: a post, geometry
            ink, top = mk(y0)
            cv.fill(sp, ink, s, top, own)
            continue
        top = mk(y0)
        if which == "sw":
            cv.fill(sp, MAG, s, top, own)
            cv.outline(sp, left=True)
        elif which == "se":
            cv.fill(sp, lambda x, y: MAG if (x + y) & 1 == 0 else BLK, s, top, own)
            cv.outline(sp, left=True)
        else:
            if t.kind == KIND_WALL:
                cv.fill(sp, MAG if t.surf == SURF_BOUNCE else WHT, s, top, own)   # a bumper rail: magenta
            elif t.kind != KIND_GOAL and t.surf != SURF_NORMAL:
                cv.fill(sp, _surface_ink(t.surf, x0, y0), s, top, own)
            elif t.kind == KIND_GOAL or t.sx or t.sy:
                cv.fill(sp, BLK, s, top, own)            # the ground and the keys...
                for sub, ink in _top_subquads(t, wx, wy, x0):
                    sub = _shift(sub, y0)
                    for y, runs in sub.items():     # ...then the checker's inks
                        row = cv.rows[y]
                        for a, b in runs:
                            for x in range(a, b):
                                row[x] = ink
            else:
                cv.fill(sp, WHT if (wx + wy) & 1 else CYN, s, top, own)
            cv.outline(sp)
    return cv


# =============================================================================
# wave 3: the props' art (SPEC.md 128.12.4, 128.12.6): marks painted on what is
# drawn, posts as geometry, rotors stood on a house, the slab's sprite
# =============================================================================

def _spans_of(pix):
    """{(x, y)} -> {y: [(x, x + 1), ...]} runs"""
    out = {}
    for (x, y) in sorted(pix, key=lambda p: (p[1], p[0])):
        r = out.setdefault(y, [])
        if r and r[-1][1] == x:
            r[-1] = (r[-1][0], x + 1)
        else:
            r.append((x, x + 1))
    return out


def _paint_op(pix, s, tile, owner):
    """a 'paint' op from {(x, y at Y0 = 0): ink}"""
    mk = (lambda d: lambda y0: lambda x, y: d.get((x, y - y0)))(dict(pix))
    return (_spans_of(pix), "paint", s, mk, False, tile, owner)


def _op_spans(ops, owner, which):
    for sp0, w, s, mk, left, t, own in ops:
        if own == owner and w == which:
            return sp0
    return None


def _top_world(t, wx, wy, x0):
    """a tile top's pixel (Y0 = 0) -> its world point (gx, gy) in gu, floats"""
    zf = _top_fn(t, wx, wy, x0, 0)

    def w(x, y):
        z = zf(x, y)
        a = x + 0.5 - x0
        b = 2 * (y + 0.5 + z)
        return (a + b) / 2.0, (b - a) / 2.0
    return w


def _seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if not L2 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / float(L2)))
    qx, qy = ax + t * dx - px, ay + t * dy - py
    return math.hypot(qx, qy)


def _post_pix(wx, wy, t, x0, lit):
    """a post (SPEC.md 128.12.6.3): a cylinder 1 unit tall, radius 8 px across
    and 4 lines deep on screen, on its cell's centre -> {(x, y at Y0 = 0): ink}"""
    cx = 16 * (wx - wy) + x0
    cy = 8 * (wx + wy) + 8 - 4 * t.z0
    ty = cy - POST_H
    out = {}

    def ell(X, Y, yc, a, b):
        return ((X - cx) / a) ** 2 + ((Y - yc) / b) ** 2 <= 1.0
    side = set()
    top = set()
    for y in range(ty - 5, cy + 6):
        for x in range(cx - 8, cx + 8):
            X, Y = x + 0.5, y + 0.5
            if ell(X, Y, ty, 8.0, 4.0):
                top.add((x, y))
            elif abs(X - cx) < 8 and Y >= ty and (Y <= cy or ell(X, Y, cy, 8.0, 4.0)):
                side.add((x, y))
    for (x, y) in top:
        rim = not ell(x + 0.5, y + 0.5, ty, 6.6, 2.9)
        out[(x, y)] = BLK if rim else (WHT if lit else CYN)
    for (x, y) in side:
        edge = (x, y + 1) not in side and (x, y + 1) not in top or x in (cx - 8, cx + 7)
        out[(x, y)] = BLK if edge else (CYN if lit else MAG)
    return out


def _arch(sp0, xc, rows, half, sill=0):
    """an arch on a face: columns xc - half .. xc + half - 1, the `rows` lines
    above each column's SILL - its last face line, raised `sill` px (a mouth
    above the floor in front of the face: a DROP's exit height) - its top
    corners rounded.  -> (pixels, each column's last face line, whole): whole
    when every pixel of the arch is on the face"""
    last = {}
    for y, runs in sp0.items():
        for a, b in runs:
            for x in range(a, b):
                if x not in last or y > last[x]:
                    last[x] = y
    pix = {}
    whole = True
    for x in range(xc - half, xc + half):
        if x not in last:
            whole = False
            continue
        for k in range(rows):
            y = last[x] - sill - k
            if k >= rows - 2 and abs(x + 0.5 - xc) > half - 1.5:
                continue
            if _inside(sp0.get(y), x):
                pix[(x, y)] = BLK
            else:
                whole = False
    return pix, last, whole


MOUTH_ROWS, MOUTH_HALF = 11, 4      # an exit mouth on a wall face: the doorway's arch


def mouth_of(p, x0):
    """a tube's EXIT MOUTH (SPEC.md 128.12.6.1): (the wall, its face, the
    arch's centre column, its rows, half width, sill) when the ball leaves
    through a face the viewer sees - a DROP's (always: its OUT is in front of
    its last wall, at its exit height) and a windmill's whose OUT is in front
    of its house along +x or +y (at OUT's floor) - else None"""
    if p["kind"] not in (PK_TUBE, PK_WINDMILL) or p["dir"] not in (0, 2):
        return None
    o = p["out"]
    w = (o[0] - DIR_VEC[p["dir"]][0], o[1] - DIR_VEC[p["dir"]][1])
    face = "se" if p["dir"] == 0 else "sw"
    xm = 16 * (w[0] - w[1]) + x0 + (8 if p["dir"] == 0 else -8)
    if p["kind"] == PK_TUBE and p["sub"] == TK_DROP:
        return w, face, xm, 9, 5, 4 * p["h2"]
    if p["kind"] == PK_WINDMILL and p["body"] and p["body"][-1] == w:
        return w, face, xm, MOUTH_ROWS, MOUTH_HALF, 0
    return None


def prop_ops(tiles, ops, props, x0):
    """the props' static art as ops, each inserted after the op it is drawn
    on (so whatever is in front still covers it): a plain tube's IN hole and
    OUT rim with its chevron, the pipe on its body's tops, a DROP's mouth, a
    windmill's doorway, the posts (geometry: their own s and top)"""
    after = {}

    def add(owner, which, op):
        after.setdefault((owner, which), []).append(op)
    for p in props:
        if p["kind"] in (PK_TUBE, PK_WINDMILL):
            if p["kind"] == PK_TUBE:
                for cell, hole in ((p["inn"], True), (p["out"], False)):
                    t = tiles[cell]
                    sp0 = _op_spans(ops, cell, "top")
                    wf = _top_world(t, cell[0], cell[1], x0)
                    pix = {}
                    for y, runs in sp0.items():
                        for a, b in runs:
                            for x in range(a, b):
                                gx, gy = wf(x, y)
                                du, dv = gx - (16 * cell[0] + 8), gy - (16 * cell[1] + 8)
                                m = max(abs(du), abs(dv))
                                if hole and m <= 5:
                                    pix[(x, y)] = BLK
                                elif not hole and 4.5 < m <= 6:
                                    pix[(x, y)] = BLK
                    if not hole:                    # the chevron along `out`
                        ux, uy = DIR_VEC[p["dir"]]
                        vx, vy = -uy, ux
                        cxg, cyg = 16 * cell[0] + 8, 16 * cell[1] + 8
                        zc = _h4t(t, 8, 8) / 4.0
                        tip = (cxg + 3 * ux, cyg + 3 * uy)
                        for side in (1, -1):
                            arm = (cxg - 1 * ux + 3 * side * vx, cyg - 1 * uy + 3 * side * vy)
                            for k in range(17):
                                f = k / 16.0
                                gx = tip[0] + (arm[0] - tip[0]) * f
                                gy = tip[1] + (arm[1] - tip[1]) * f
                                x = int(math.floor(gx - gy + x0))
                                y = int(math.floor((gx + gy) / 2.0 - zc))
                                if _inside(sp0.get(y), x):
                                    pix[(x, y)] = BLK
                    add(cell, "top", _paint_op(pix, cell[0] + cell[1], t, cell))
                for cell in p["body"]:              # the pipe on the body's tops
                    t = tiles[cell]
                    sp0 = _op_spans(ops, cell, "top")
                    wf = _top_world(t, cell[0], cell[1], x0)
                    pix = {}
                    for y, runs in sp0.items():
                        for a, b in runs:
                            for x in range(a, b):
                                gx, gy = wf(x, y)
                                d = min(_seg_dist(gx, gy, a_, b_) for a_, b_ in zip(p["gpts"], p["gpts"][1:]))
                                if d <= 3.0:
                                    pix[(x, y)] = CYN
                                elif d <= 4.5:
                                    pix[(x, y)] = BLK
                    add(cell, "top", _paint_op(pix, cell[0] + cell[1], t, cell))
            mo = mouth_of(p, x0)
            if mo is not None:                      # the EXIT MOUTH: an arch on the face the ball leaves by,
                w, face, xm, rows, half, sill = mo  # its sill at the exit's height (the owner's preview)
                sp0 = _op_spans(ops, w, face)
                if sp0 is None:
                    raise CourseError("the tube on line %d: its last wall (%d, %d) shows no %s face"
                                      % (p["line"], w[0], w[1], DIR_NAMES[p["dir"]]))
                pix, _l, whole = _arch(sp0, xm, rows, half, sill)
                if not whole:
                    raise CourseError("the tube on line %d: its exit mouth (%d x %d px, its sill %d px over OUT's "
                                      "floor) is not wholly on the face of its last wall (%d, %d): a taller wall, "
                                      "or a lower exit" % (p["line"], 2 * half, rows, sill, w[0], w[1]))
                add(w, face, _paint_op(pix, w[0] + w[1], tiles[w], w))
                p["mouth"] = (w, face, xm, rows, half, sill)
                p["mouth_pix"] = pix
            if p["kind"] == PK_WINDMILL:            # the windmill's doorway on the house face
                ix, iy = p["inn"]
                if p["door"] == 1:
                    D, face, xh = (ix - 1, iy), "se", 16 * (ix - iy) - 8 + x0 - 4
                else:
                    D, face, xh = (ix, iy - 1), "sw", 16 * (ix - iy) + 8 + x0 + 4
                sp0 = _op_spans(ops, D, face)
                if sp0 is None:
                    raise CourseError("the windmill on line %d: its doorway wall (%d, %d) shows no face"
                                      % (p["wline"], D[0], D[1]))
                pix, last, _w = _arch(sp0, xh, MOUTH_ROWS, MOUTH_HALF)
                p["D"], p["face"], p["xh"], p["flast"] = D, face, xh, last.get(xh)
                if p["flast"] is None:
                    raise CourseError("the windmill on line %d: its house face has no line at its doorway"
                                      % p["wline"])
                add(D, face, _paint_op(pix, D[0] + D[1], tiles[D], D))
        elif p["kind"] == PK_BUMPER:
            wx, wy = p["at"]
            t = tiles[p["at"]]
            dark = _post_pix(wx, wy, t, x0, False)
            p["pix0"], p["pix1"] = dark, _post_pix(wx, wy, t, x0, True)
            mk = (lambda d, top: lambda y0: (lambda x, y: d[(x, y - y0)], lambda x, y: top))(dark, p["top"])
            add(p["at"], "top", (_spans_of(dark), "post", wx + wy, mk, False, t, p["at"]))
    out = []
    for op in ops:
        out.append(op)
        out += after.get((op[6], op[1]), [])
    return out


def rotor_poses(p):
    """a windmill's rotor (SPEC.md 128.12.6.2): {pose: {(x, y): ink}} about its
    hub (p['hub']): four blades, `poses` of them over a quarter turn, the
    blade pointing down on exactly the closed window's poses"""
    npose = (p["mask"] + 1) >> p["shift"]
    pc0, pc1 = p["closed"][0] >> p["shift"], p["closed"][1] >> p["shift"]
    mid = (pc0 + pc1) / 2.0
    hx, hy = p["hub"]
    out = {}
    for q in range(npose):
        th0 = math.radians((q + 0.5 - mid) * 90.0 / npose)
        pix = {}
        for y in range(hy - 12, hy + 12):
            for x in range(hx - 12, hx + 12):
                dx, dy = x + 0.5 - hx, y + 0.5 - hy
                r = math.hypot(dx, dy)
                if r < 2.6:
                    pix[(x, y)] = BLK
                    continue
                if r > 11.0:
                    continue
                best = None
                for k in range(4):
                    th = th0 + k * math.pi / 2
                    ax, ay = math.sin(th), math.cos(th)
                    along = dx * ax + dy * ay
                    perp = abs(dx * ay - dy * ax)
                    if along > 0 and perp <= 2.0:
                        c = CYN if perp <= 1.2 else BLK
                        if best is None or c == CYN:
                            best = c
                if best is not None:
                    pix[(x, y)] = best
        out[q] = pix
    return out


def slab_pixels():
    """the platform's sprite (SPEC.md 128.12.6.4): {(x, y): ink}, 32 x 18 -
    the tile's top diamond (the very spans a tile's top is drawn with), an
    outline and a stipple, and a 2-line LIP under its two front edges"""
    quad = [(64, 0), (128, 32), (64, 64), (0, 32)]
    sp = spans(quad)
    inside = {(x, y) for y, runs in sp.items() for a, b in runs for x in range(a, b)}
    out = {}
    for (x, y) in inside:
        edge = (x, y - 1) not in inside or (x, y + 1) not in inside or (x - 1, y) not in inside \
            or (x + 1, y) not in inside
        out[(x, y)] = BLK if edge else (WHT if (x + 2 * y) % 6 == 0 else CYN)
    for x in range(PL_W):
        ys = [y for (xx, y) in inside if xx == x]
        if not ys:
            continue
        yb = max(ys)
        for k in (1, 2):
            out[(x, yb + k)] = BLK if k == 2 else (MAG if x < 16 else (MAG if (x + yb + k) & 1 == 0 else BLK))
    assert max(y for _, y in out) < PL_H and max(x for x, _ in out) < PL_W
    return out


def slab_bytes(pix):
    """two parity copies, each the mask (144) and the frame (144): mask 3
    where the course shows, frame the slab's ink (128.12.6.4)"""
    out = bytearray()
    for _p in range(2):
        m = bytearray()
        fr = bytearray()
        for y in range(PL_H):
            m += cga_bytes([0 if (x, y) in pix else 3 for x in range(PL_W)])
            fr += cga_bytes([pix.get((x, y), 0) for x in range(PL_W)])
        out += m + fr
    assert len(out) == PL_SPR
    return bytes(out)


def slab_xy(p, I, x0, y0):
    """the sprite's top-left with the LIFT risen I whole px over its low top:
    its columns never change, its line is 8 (Awx + Awy) - (hP + I) + Y0"""
    A = p["at"]
    return 16 * (A[0] - A[1] - 1) + x0, 8 * (A[0] + A[1]) - (p["hP"] + I) + y0


def slab_s(p, I=0):
    """sP: the cell row of the slab's centre - its shaft's, whatever its height"""
    A = p["at"]
    return A[0] + A[1]


def slab_rise(p, line, x0, y0):
    """the rise I (whole px) a drawn LINE stands for: slab_xy's inverse"""
    return slab_xy(p, 0, x0, y0)[1] - line


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
    _blocks.index = index
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


def _occg(reach, by_block, x0, y0, tiles, slab=None):
    """SPEC.md 128.11.4.3: a FLOOR or GOAL cell some GROUNDED ball in which - at
    its floor, margin BZ_CLIMB, anywhere in its area - meets a record the rule
    lays.  -> {cell: most laid by a grounded ball}.  slab: {shaft cell: (hP,
    hT)}, a lift's, where a ball grounded on the slab is anywhere from its low
    top to its high one (wave 3)"""
    slab = slab or {}
    fl = [rc for rc in reach if rc.kind in (KIND_FLOOR, KIND_GOAL) or (rc.wx, rc.wy) in slab]

    def zr(rc):
        if (rc.wx, rc.wy) in slab:
            return slab[(rc.wx, rc.wy)]
        t = tiles[(rc.wx, rc.wy)]
        return 4 * min(t.corners()), 4 * max(t.corners())

    def frac(rc, z):                    # a plane's height carries a fraction
        if (rc.wx, rc.wy) in slab:
            return False
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
    block), and every platform sprite's FRAME halves (row r of parity copy p
    through table (p + r) & 1, SPEC.md 128.12.3.1); the rest unchanged"""
    t = htab()
    p = bytearray(part)
    nblk, _, blkoff = struct.unpack_from("<HHH", p, 8)
    for i in range(16 * nblk):
        o = blkoff + i
        p[o] = t[256 * ((i >> 1) & 1) + p[o]]
    propoff, nprop = struct.unpack_from("<HH", p, 28)
    rb = PL_W // 4
    for k in range(nprop):
        r0 = propoff + PROPREC * k
        if p[r0] == PK_PLATFORM:
            so = struct.unpack_from("<H", p, r0 + 22)[0]
            for cp in range(2):
                fo = so + cp * 2 * rb * PL_H + rb * PL_H
                for r in range(PL_H):
                    for j in range(rb):
                        o = fo + rb * r + j
                        p[o] = t[256 * ((cp + r) & 1) + p[o]]
    return bytes(p)


def compile_course(source, fname=None, occluders=True, _hack=None):
    """source: a path, or the text itself (with fname for messages).
    occluders=False cuts no records (a host model that wants only the grid).
    _hack: --selfcheck's negative controls' switches, and nothing else's"""
    hack = _hack or {}
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
    props = build_props(src, tiles, fname)
    cells = build_cells(tiles)
    pcell = prop_cells(props)
    for c_ in pcell:                                  # no prop's cell is SAFE (a respawn lands in no drain)
        if c_ in cells:
            cells[c_][3] &= ~FL_SAFE
    slabcells = {}
    for p in props:
        if p["kind"] == PK_PLATFORM:                 # the shaft: a NEAR void, its kill 3 units under the LOW top
            for t in p["track"]:
                cells[t] = [p["h2"] - 6, 0, KIND_VOID, 0]
                slabcells[t] = (p["hP"], p["hT"])
    reach, rounds, emax = build_reach(tiles, cells, fname, props)
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
    ops = draw_ops(tiles, x0, {c for p in props if p["kind"] == PK_TUBE for c in p["body"]})
    if props:
        ops = prop_ops(tiles, ops, props, x0)
    gtop = min(min(sp) for sp, *_ in ops if sp)
    gbot = max(max(sp) for sp, *_ in ops if sp)
    for p in props:                                   # the slab over its whole rise
        if p["kind"] == PK_PLATFORM:
            gtop = min(gtop, slab_xy(p, 8 * p["L"], x0, 0)[1])
            gbot = max(gbot, slab_xy(p, 0, x0, 0)[1] + PL_H - 1)
    ftop = min(foot_top(rc, rc.zhi) for rc in reach)
    y0 = max(-gtop, -ftop)
    fbot = max(foot_top(rc, rc.zlo) + 30 for rc in reach)
    lines = max(gbot, fbot) + y0 + 1
    lines = max(MINLINES, (lines + 7) // 8 * 8)
    cols, brows = src.width, lines // 8
    owners = any(p["kind"] == PK_WINDMILL for p in props)
    cv = render(tiles, ops, x0, y0, width, lines, owners)
    # ---- the lanes (SPEC.md 128.12.4): a rotor stood on its house, a post ----
    lanes = []
    for i, p in enumerate(props):
        if p["kind"] == PK_WINDMILL:
            ln = p["wline"]
            fl = p["flast"] + y0                     # the face's last line at the hub's column
            hy = fl - 11
            hy -= (hy - 4) % 8
            p["hub"] = (p["xh"], hy + hack.get("rotor_dy", 0))
            poses = rotor_poses(p)
            ix, iy = p["inn"]
            # the house: the WALL tiles 4-connected to the doorway's wall
            house, todo = set(), [p["D"]]
            while todo:
                t = todo.pop()
                if t in house or t not in tiles or tiles[t].kind != KIND_WALL:
                    continue
                house.add(t)
                todo += [(t[0] + 1, t[1]), (t[0] - 1, t[1]), (t[0], t[1] + 1), (t[0], t[1] - 1)]
            hown = {256 * a + b for (a, b) in house}
            p["house"] = house
            sD = p["D"][0] + p["D"][1]
            for q in list(poses):
                # a blade below the doorway's floor line is behind what stands in
                # front of the house (IN's floor): clipped; anything else must be
                # the house's own
                pix = {}
                for (x, y), ink in poses[q].items():
                    o = cv.obuf[y][x] if 0 <= x < width and 0 <= y < lines else -1
                    if o >= 0 and o not in hown and (o >> 8) + (o & 255) > sD:
                        continue
                    pix[(x, y)] = ink
                poses[q] = pix
            for q, pix in poses.items():
                for (x, y) in pix:
                    if not (0 <= x < width and 0 <= y < lines) or cv.obuf[y][x] not in hown:
                        o = cv.obuf[y][x] if 0 <= x < width and 0 <= y < lines else -1
                        raise CourseError("%s:%d: the windmill's house cannot hold its rotor: pose %d's pixel "
                                          "(%d, %d) is not the house's but %s (its +x and +y faces and roof; "
                                          "in practice a house 2 cells along the face and 3 units tall)"
                                          % (fname, ln, q, x, y, "cell (%d, %d)'s" % (o >> 8, o & 255)
                                             if o >= 0 else "nothing's"))
            hx, hy = p["hub"]
            rect = ((hx - 12) >> 3, (hy - 12) >> 3, 3, 3)
            sts = {}
            if hack.get("rotor_front"):              # the negative control: blades IN FRONT of the doorway
                stop = max(cv.tbuf[y][x] for q in poses for (x, y) in poses[q])
                for q, pix in poses.items():
                    sts[q] = {xy: (ix + iy + 1, stop) for xy in pix}
            lanes.append({"prop": i, "rect": rect, "poses": poses, "st": sts, "kind": PK_WINDMILL, "line": ln})
        elif p["kind"] == PK_BUMPER:
            pix = {(x, y + y0): c for (x, y), c in p["pix1"].items()}
            xs = [x for x, _ in pix]
            ys = [y for _, y in pix]
            c0, r0 = min(xs) >> 3, min(ys) >> 3
            rect = (c0, r0, (max(xs) >> 3) - c0 + 1, (max(ys) >> 3) - r0 + 1)
            lanes.append({"prop": i, "rect": rect, "poses": {0: {}, 1: pix}, "st": {},
                          "kind": PK_BUMPER, "line": p["line"]})
    for L in lanes:
        bx, by, w, h = L["rect"]
        if not (1 <= w <= LANE_WMAX and 1 <= h <= LANE_HMAX and 2 <= len(L["poses"]) <= LANE_PMAX):
            raise CourseError("%s:%d: a lane of %d x %d blocks and %d poses, over %d x %d and 2 - %d"
                              % (fname, L["line"], w, h, len(L["poses"]), LANE_WMAX, LANE_HMAX, LANE_PMAX))
        if bx < 0 or by < 0 or bx + w > cols or by + h > brows:
            raise CourseError("%s:%d: a lane outside the picture" % (fname, L["line"]))
        L["bare"] = [bytes(cv.rows[y][8 * bx:8 * (bx + w)]) for y in range(8 * by, 8 * (by + h))]
        for M in lanes:
            if M is not L and M["prop"] > L["prop"]:
                mx, my, mw, mh = M["rect"]
                if bx < mx + mw and mx < bx + w and by < my + mh and my < by + h:
                    raise CourseError("%s:%d: two lanes share blocks (lines %d and %d)"
                                      % (fname, M["line"], L["line"], M["line"]))
    for L in lanes:                                   # pose 0 into the picture
        for (x, y), ink in L["poses"][0].items():
            cv.rows[y][x] = ink
        for (x, y), st in L["st"].get(0, {}).items():
            cv.sbuf[y][x], cv.tbuf[y][x] = st
    pic = cv.rows
    # the blocks and the map; each lane's poses join the one pool
    blocks, mp = _blocks(pic, cols, brows)
    bindex = _blocks.index
    nblk_pic = len(blocks)
    for L in lanes:
        bx, by, w, h = L["rect"]
        L["pics"], L["words"] = {}, {}
        for q in range(len(L["poses"])):
            reg = [bytearray(r) for r in L["bare"]]
            for (x, y), ink in L["poses"][q].items():
                reg[y - 8 * by][x - 8 * bx] = ink
            L["pics"][q] = reg
            idxs = []
            for r in range(h):
                for k in range(w):
                    blk = b"".join(bytes(reg[8 * r + yy][8 * k:8 * k + 8]) for yy in range(8))
                    n = bindex.get(blk)
                    if n is None:
                        n = bindex[blk] = len(blocks)
                        blocks.append(blk)
                    idxs.append(n)
            L["words"][q] = idxs
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
    # the occluders: cut (128.10.4.4) from pose 0's picture, merged (128.11.4.1), bounded (128.11.4.2)
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
    occg = _occg(reach, by_block, x0, y0, tiles, slabcells) if records else {}
    for (wx, wy), n in occg.items():
        if n:
            cells[(wx, wy)][3] |= FL_OCC | FL_OCCG
    # wave 3's occlusion refusals (SPEC.md 128.12.4.5, 128.12.15 item 2)
    if occluders:
        for L in lanes:
            bad = lane_pose_verdicts(L, reach, x0, y0, cv)
            if bad:
                qq, (x, y), rc, z, air = bad
                raise CourseError("%s:%d: the lane's occluder verdicts depend on its pose: pose %d's pixel (%d, %d) "
                                  "hides a ball in cell (%d, %d) at %d px (%s) differently from pose 0's (a "
                                  "moving part in front of the ball needs per-pose records, O25)"
                                  % (fname, L["line"], qq, x, y, rc.wx, rc.wy, z, "airborne" if air else "grounded"))
    for p in props:
        if p["kind"] == PK_WINDMILL:
            ix, iy = p["inn"]
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    cl = cells.get((ix + dx, iy + dy))
                    if cl and cl[3] & (FL_OCC | FL_OCCG):
                        raise CourseError("%s:%d: the windmill's doorway is in the shade: cell (%d, %d) of IN's "
                                          "3 x 3 has OCC%s set" % (fname, p["wline"], ix + dx, iy + dy,
                                                                   "G" if cl[3] & FL_OCCG else ""))
    slab = slab_pixels() if any(p["kind"] == PK_PLATFORM for p in props) else {}
    for p in props:
        if p["kind"] != PK_PLATFORM:
            continue
        for I in range(8 * p["L"] + 1):
            sx_, sy_ = slab_xy(p, I, x0, y0)
            sP = slab_s(p, I)
            for (dx, dy) in slab:
                x, y = sx_ + dx, sy_ + dy
                if cv.sbuf[y][x] > sP and cv.tbuf[y][x] > p["hP"] + I:
                    raise CourseError("%s:%d: the lift risen %d px overlaps pixel (%d, %d), drawn by a cell "
                                      "in front of it (row %d) that rises above its top (%d px)"
                                      % (fname, p["line"], I, x, y, cv.sbuf[y][x], p["hP"] + I))
        x_l, ya = slab_xy(p, 8 * p["L"], x0, y0)
        yb = slab_xy(p, 0, x0, y0)[1] + PL_H
        for L in lanes:
            bx, by, w, h = L["rect"]
            if 8 * bx < x_l + PL_W and x_l < 8 * (bx + w) and 8 * by < yb and ya < 8 * (by + h):
                raise CourseError("%s:%d: a lane (line %d) meets the platform's sprite on its track"
                                  % (fname, p["line"], L["line"]))
    for c_ in pcell:
        cells[c_][3] |= FL_OBS
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
    # the props after the grid (SPEC.md 128.12.3.1): the records, lanes first
    # by first block row, then the rest, each in the file's order
    lane_of = {L["prop"]: L for L in lanes}
    order = sorted((i for i in range(len(props)) if i in lane_of),
                   key=lambda i: (lane_of[i]["rect"][1], props[i]["line"]))
    order += sorted((i for i in range(len(props)) if i not in lane_of), key=lambda i: props[i]["line"])
    propoff = end if props else 0
    pmoff = end + PROPREC * len(props)
    segoff = pmoff + sum(2 * len(L["poses"]) * L["rect"][2] * L["rect"][3] for L in lanes)
    spoff = segoff + SEGREC * sum(len(props[i]["segs"]) for i in order if "segs" in props[i])
    pend = spoff + PL_SPR * sum(1 for p in props if p["kind"] == PK_PLATFORM)
    if props:
        end = pend
    if end > PARTMAX:
        raise CourseError("%s: the course part is %d bytes, over the %d one part may be, by %d"
                          % (fname, end, PARTMAX, end - PARTMAX))
    hdr = b"BZC1" + struct.pack("<13H", cols, brows, len(blocks), 4 if cols == 64 else 5, blkoff,
                                occidx, occrec, len(records), maskoff, len(masks), 2 * cols,
                                gridoff, propoff) + struct.pack("<H", len(props))
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
    recp, pmb, segb, sprb = bytearray(), bytearray(), bytearray(), bytearray()
    so = segoff
    spo = spoff
    pmo = pmoff
    slab_b = slab_bytes(slab) if slab else b""
    for i in order:
        p = props[i]
        L = lane_of.get(i)
        flags = PF_LANE if L else 0
        rec = struct.pack("<BBBBBBH", p["kind"], flags, p["at"][0], p["at"][1], p["mask"], p["shift"], p["seed"])
        if L:
            bx, by, w, h = L["rect"]
            rec += struct.pack("<HBBBBH", by, bx, w, h, len(L["poses"]), pmo)
            p["lane"] = {"brow": by, "col": bx, "w": w, "h": h, "poses": len(L["poses"]), "off": pmo}
            for qq in range(len(L["poses"])):
                for n in L["words"][qq]:
                    pmb += struct.pack("<H", blkoff + 16 * n)
            pmo += 2 * len(L["poses"]) * w * h
        else:
            rec += bytes(8)
            p["lane"] = None
        if p["kind"] in (PK_TUBE, PK_WINDMILL):
            if p["kind"] == PK_WINDMILL:
                g = (0 if p["door"] == 1 else 1, 0, 0)
            elif p["sub"] == TK_LAUNCH:
                g = p["speed"]
            elif p["sub"] == TK_DROP:
                g = (0, 0, p["zexit"])
            else:
                g = (0, 0, 0)
            rec += struct.pack("<BBBBHHhhhBB", p["sub"], p["dir"], len(p["segs"]), p["eG"], so, p["T"],
                               g[0], g[1], g[2], p["closed"][0], p["closed"][1])
            p["segoff"] = so
            for sg in p["segs"]:
                segb += struct.pack("<Hhhhhhhh", sg["m"], sg["incx"], sg["incy"], sg["incz"], sg["ex"], sg["ey"],
                                    sg["ez"], 0)
            so += SEGREC * len(p["segs"])
        elif p["kind"] == PK_BUMPER:
            rec += struct.pack("<HBBHHH6x", p["K"], PLITF, POST_H, p["cx"], p["cy"], p["KA"])
        else:
            rec += struct.pack("<HBBhHH6x", p["v"], p["W"], p["L"], p["hP"], spo, p["pmax"])
            p["spoff"] = spo
            sprb += slab_b
            spo += PL_SPR
        assert len(rec) == PROPREC
        recp += rec
    cga = bytearray(hdr + mapb)
    for blk in blocks:
        for y in range(8):
            cga += cga_bytes(blk[y * 8:y * 8 + 8])
    cga += bytes(idx) + recb + b"".join(masks) + bytes(grid)
    if props:
        cga += recp + pmb + segb + sprb
    assert len(cga) == end, (len(cga), end)
    # the course's IDENTITY at BZG1 +18 (SPEC.md 128.12.8)
    ident = part_identity(cga, gridoff)
    struct.pack_into("<H", cga, gridoff + 18, ident)
    c = Course()
    c.fname, c.name, c.title = fname, src.name, src.title
    c.src, c.tiles, c.cells, c.reach = src, tiles, cells, reach
    c.x0, c.y0, c.width, c.lines, c.cols, c.brows = x0, y0, width, lines, cols, brows
    c.pic, c.sbuf, c.tbuf = pic, cv.sbuf, cv.tbuf
    c.blocks, c.map = blocks, mp
    c.nblk_pic = nblk_pic
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
    c.props, c.order, c.lanes, c.pcell, c.slab, c.slabcells = props, order, lanes, pcell, slab, slabcells
    c.ident = ident
    c.cga = bytes(cga)
    c.part_bytes = c.cga                # the ONE part (BZ<K>.BIN, SPEC.md 128.11.3)
    c.herc = herc_translate_course(c.cga)   # what the guest makes of it on the Hercules
    c.gtop, c.ftop = gtop, ftop
    c.part = read_part(c.cga, fname)
    c.exits = {}
    if props and not hack.get("no_exits"):
        check_exits(c)
    if props and occluders and not hack.get("no_bounds"):
        c.bounds = check_bounds(c)
    return c


def exit_run(c, rec, mat, vin=TMIN, n=400, steps=None):
    """a tube's exit, by the model (SPEC.md 128.12.6.1): the ball left at OUT
    as the exit leaves it, then no keys.  -> (outcome, cell, Physics):
    'land', 'bounce', 'stun', 'shatter' at the first contact, 'wall' when a
    wall or a corner turns it first, 'fell', or 'rolls' (KEEP: still rolling
    on a floor after `steps` steps)"""
    p = Physics(c, mat=mat)
    o = (rec["segs"][-1]["ex"] >> 4, rec["segs"][-1]["ey"] >> 4)
    p.poke(*o)
    ux, uy = DIR_VEC[rec["dir"]]
    v = max(vin, TMIN)
    if rec["sub"] == TK_LAUNCH:
        p.gvx, p.gvy, p.gvz = rec["g"]
        p.air = 1
        p.ztop = p.gz >> 8
        p.gz += p.gvz
    elif rec["sub"] == TK_DROP:
        p.gz = rec["segs"][-1]["ez"] << 8
        p.gvx, p.gvy, p.gvz = ux * v, uy * v, 0
        p.air = 1
        p.ztop = p.gz >> 8
    else:
        p.gvx, p.gvy = ux * v, uy * v
    p._derive(True)
    for _ in range(steps or n):
        n0 = len(p.events)
        p.step(0)
        for e in p.events[n0:]:
            if e[0] in ("wall", "corner", "undo", "knock"):
                return "wall", (p.gx >> 12, p.gy >> 12), p
            if e[0] in ("land", "bounce", "stun", "shatter", "hopc"):
                return e[0], (p.gx >> 12, p.gy >> 12), p
            if e[0] == "respawn":
                return "fell", (p.gx >> 12, p.gy >> 12), p
            if e[0] == "capture":
                return "captured", (p.gx >> 12, p.gy >> 12), p
    return "rolls", (p.gx >> 12, p.gy >> 12), p


def check_exits(c):
    """SPEC.md 128.12.3.3: a LAUNCH's flight comes down on a FLOOR for each
    ball; a DROP's does over s_in 64 - BZ_VMAXG for each ball; a KEEP's rolls
    on.  -> c.exits {record: {ball: (outcome, ...)}} for the report"""
    floors = lambda cell: (cell in c.tiles and c.tiles[cell].kind in (KIND_FLOOR, KIND_GOAL)) \
        or cell in c.slabcells
    for rec in c.part["props"]:
        if rec["kind"] not in (PK_TUBE, PK_WINDMILL):
            continue
        line = c.props[c.order[rec["i"]]]["line"]
        out = {}
        for mat in range(len(MATERIALS)):
            if rec["sub"] == TK_KEEP:
                res = [exit_run(c, rec, mat, vin, steps=8) for vin in (TMIN, VMAXG)]
                bad = [r for r in res if r[0] not in ("rolls", "land") or not floors(r[1])]
                out[mat] = ("rolls", None)
            elif rec["sub"] == TK_LAUNCH:
                r = exit_run(c, rec, mat)
                bad = [] if r[0] in ("land", "bounce", "stun", "shatter") and floors(r[1]) else [r]
                out[mat] = (r[0], r[1])
            else:
                seen = {}
                bad = []
                for vin in range(TMIN, VMAXG + 1):
                    r = exit_run(c, rec, mat, vin)
                    if r[0] not in ("land", "bounce", "stun", "shatter") or not floors(r[1]):
                        bad.append(r + (vin,))
                        break
                    seen[r[0]] = seen.get(r[0], 0) + 1
                out[mat] = (" ".join("%s %d" % kv for kv in sorted(seen.items())), None)
            if bad:
                r = bad[0]
                raise CourseError("%s:%d: the %s tube's exit, %s ball%s: %s at (%d, %d), not a landing on a FLOOR"
                                  % (c.fname, line, TK_NAMES[rec["sub"]], MAT_NAMES[mat],
                                     " at s_in %d" % r[3] if len(r) > 3 else "", r[0], r[1][0], r[1][1]))
        c.exits[rec["i"]] = out


def _rects(c):
    """the lanes' and the slab's pixel rectangles: ([(x0, y0, x1, y1, rec)], [platform rects])"""
    lanes, slabs = [], []
    for rec in c.part["props"]:
        L = rec["lane"]
        if L:
            lanes.append((8 * L["col"], 8 * L["brow"], 8 * (L["col"] + L["w"]), 8 * (L["brow"] + L["h"]), rec))
        if rec["kind"] == PK_PLATFORM:
            p = c.props[c.order[rec["i"]]]
            x_l, ya = slab_xy(p, 8 * p["L"], c.x0, c.y0)
            yb = slab_xy(p, 0, c.x0, c.y0)[1] + PL_H
            slabs.append((x_l, ya, x_l + PL_W, yb, rec))
    return lanes, slabs


def _meet(r, x0, y0, x1, y1):
    return r[0] < x1 and x0 < r[2] and r[1] < y1 and y0 < r[3]


def rotor_changes(recs, P=256):
    """-> (most rotor pose changes on one step, most in two consecutive steps)
    among the windmills `recs`, over every step mod 256"""
    ch = [0] * P
    for r in recs:
        pl = 1 << r["shift"]
        for n in range(P):
            if (n + r["seed"]) % pl == 0:
                ch[n] += 1
    return max(ch), max(ch[n] + ch[(n + 1) % P] for n in range(P))


def ring_cross(r0, r1, x0, x1, herc):
    """SPEC.md 128.13.5.1-2: does a column of the card rectangle (rows [r0, r1),
    words [x0, x1)) cross the ring's 8KB end - bz_wprect's test, a column's last
    row's offset ((rb r + 2 x) mod 8K, absolute) at 2000h or past, made as
    bz_lwrp makes it for the LAST column"""
    rb = 90 if herc else 80
    if r1 - r0 < 2 or x1 <= x0:
        return False
    return ((rb * r0 + 2 * x0) & 0x1FFF) + (r1 - r0 - 1) * rb + 2 * (x1 - x0) >= 0x2000 + 2


def check_bounds(c):
    """SPEC.md 128.12.4.6's bounds over every window position on both cards,
    and the start window's calibration corner.  -> a dict for the report"""
    lanes, slabs = _rects(c)
    info = {}
    for herc in (0, 1):
        W, H, rl, lsh = CARDS[herc]
        rmax = c.brows * 8 // rl - H
        cmax = c.cols - W
        most = most_r = 0
        worst = (0, 0)
        for R in range(rmax + 1):
            ya, yb = R * rl, R * rl + WIN_LINES
            ra, rb = 8 * ((ya >> 3) - 2), 8 * (((yb - 1) >> 3) + 3)
            inrange = [L for L in lanes if L[1] < rb and ra < L[3]]
            most_r = max(most_r, len(inrange))
            if len(inrange) > RANGE_LANES:
                raise CourseError("%s: %d lanes in the walk's range of the %s window at row %d, over %d"
                                  % (c.fname, len(inrange), "Hercules" if herc else "CGA", R, RANGE_LANES))
            for C in range(cmax + 1):
                xa, xb = 8 * C, 8 * (C + W)
                meet = [L for L in inrange if _meet(L, xa, ya, xb, yb)]
                if len(meet) > WIN_LANES:
                    raise CourseError("%s: %d lanes meet the %s window at (row %d, column %d), over %d"
                                      % (c.fname, len(meet), "Hercules" if herc else "CGA", R, C, WIN_LANES))
                most = max(most, len(meet))
                rot = [L[4] for L in meet if L[4]["kind"] == PK_WINDMILL]
                if len(rot) > 1:
                    w1 = rotor_changes(rot)
                    worst = max(worst, w1)
                    if w1[0] > ROTOR_CHG or w1[1] > ROTOR_CHG:
                        raise CourseError("%s: the %s window at (row %d, column %d): %d rotor pose changes on one "
                                          "step, %d in two consecutive (at most %d)" % (
                                              c.fname, "Hercules" if herc else "CGA", R, C, w1[0], w1[1], ROTOR_CHG))
                sl = [S for S in slabs if _meet(S, xa, ya, xb, yb)]
                if len(sl) > 1:
                    raise CourseError("%s: two platforms in one %s window (row %d, column %d)"
                                      % (c.fname, "Hercules" if herc else "CGA", R, C))
                if sl and rot:
                    raise CourseError("%s: a platform's track and a windmill's rotor in one %s window (row %d, "
                                      "column %d)" % (c.fname, "Hercules" if herc else "CGA", R, C))
        # the start window's calibration corner (128.12.5.4)
        p = Physics(c)
        R0 = max(0, min(max(0, p.py + 8 - WIN_LINES // 2) >> lsh, rmax))
        C0 = max(0, min(max(0, p.px + 8 - 4 * W) >> 3, cmax))
        ya, yb = R0 * rl, R0 * rl + WIN_LINES
        top, bot = (ya + 7) >> 3, (yb >> 3) - 3
        foot = ((p.px & ~3), p.py, (p.px & ~3) + FOOT_W, p.py + FOOT_H)
        corner = None
        for name, bc, br in (("top-left", C0, top), ("top-right", C0 + W - 4, top),
                             ("bottom-left", C0, bot), ("bottom-right", C0 + W - 4, bot)):
            rx = (8 * bc, 8 * br, 8 * (bc + 4), 8 * (br + 3))
            if any(_meet(L, *rx) for L in lanes) or any(_meet(S, *rx) for S in slabs) or _meet(foot, *rx):
                continue
            if ring_cross((8 * br) >> lsh, (8 * (br + 3)) >> lsh, bc, bc + 4, herc):
                continue                    # its columns cross the ring's end (bz_lwrp, 128.13.5.2)
            corner = (name, bc, br)
            break
        if corner is None:
            raise CourseError("%s: the %s start window (row %d, column %d) has no calibration corner of 4 words x "
                              "3 block rows free of lanes, the track and the ball" % (
                                  c.fname, "Hercules" if herc else "CGA", R0, C0))
        info[herc] = {"lanes": most, "range": most_r, "worst": worst, "corner": corner}
    return info


def part_identity(part, gridoff):
    """SPEC.md 128.12.8: a POSITION-SENSITIVE checksum of the part's words,
    the identity word itself (BZG1 +18) taken as 0, an odd last byte a word's
    low byte - Fletcher's pair, s1 += w and s2 += s1 for each word (mod
    2^16), and the identity s2 XOR s1 with its bytes swapped.  A plain sum
    missed two words exchanged (two windmills' seeds swapped: the review's
    case, which replays a different run); a pair sees an exchange of words
    i < j unless (j - i)(w_j - w_i) is 0 mod 2^16"""
    b = bytearray(part)
    b[gridoff + 18:gridoff + 20] = b"\0\0"
    if len(b) & 1:
        b.append(0)
    s1 = s2 = 0
    for w in struct.unpack_from("<%dH" % (len(b) // 2), b, 0):
        s1 = (s1 + w) & 0xFFFF
        s2 = (s2 + s1) & 0xFFFF
    return s2 ^ (((s1 << 8) | (s1 >> 8)) & 0xFFFF)


def lane_pose_verdicts(L, reach, x0, y0, cv):
    """SPEC.md 128.12.4.5: the records are cut from pose 0's picture and lay
    through the map, which is exact when no pose changes a pixel's (s, top)
    in a way some reachable position can see.  -> None, or the first (pose,
    pixel, cell, z, air) whose verdict at that pose differs from pose 0's"""
    st0 = L["st"].get(0, {})
    for qq in sorted(L["poses"]):
        if not qq:
            continue
        stq = L["st"].get(qq, {})
        diff = {}
        for xy in set(st0) | set(stq):
            a = st0.get(xy, (cv.sbuf[xy[1]][xy[0]], cv.tbuf[xy[1]][xy[0]]))
            b = stq.get(xy, (cv.sbuf[xy[1]][xy[0]], cv.tbuf[xy[1]][xy[0]]))
            if a[0] in (-32768,) and b[0] in (-32768,):
                continue
            if a != b:
                diff[xy] = (a, b)
        if not diff:
            continue
        for rc in reach:
            xl, xh = foot_x(rc, x0)
            for (x, y), (a, b) in sorted(diff.items()):
                if not xl <= x <= xh:
                    continue
                for z in range(rc.zlo, rc.zhi + 1):
                    t0 = foot_top(rc, z) + y0
                    if not t0 - 1 <= y <= t0 + 15:
                        continue
                    for air in ((1,) if rc.kind == KIND_VOID else (0, 1)):
                        m = 0 if air else CLIMB
                        va = rc.s < a[0] and z + m < a[1]
                        vb = rc.s < b[0] and z + m < b[1]
                        if va != vb:
                            return qq, (x, y), rc, z, air
    return None


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
    if bool(propoff) != bool(nprop) or nprop > PROP_MAX:
        bad("PROPOFF", "offset %d with %d props" % (propoff, nprop))
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
    nrows, smin, amin, kw, rowtab, x0, y0, ident = struct.unpack_from("<HhhHHHhH", p, g + 4)
    swx, swy, nway, routeoff = struct.unpack_from("<HHHH", p, g + 20)
    if p[g + 28:g + 32] != bytes(4):
        bad("BZG1", "reserved bytes")
    if ident != part_identity(p, g):
        bad("BZG1 +18", "identity %04Xh is not the part's sum %04Xh" % (ident, part_identity(p, g)))
    if amin & 1:
        bad("AMIN", "odd")
    celloff = g + GHDR
    if rowtab != celloff + 4 * nrows * kw:
        bad("ROWTAB", "offset %d" % rowtab)
    rt = struct.unpack_from("<%dH" % nrows, p, rowtab)
    for r, o in enumerate(rt):
        if o < celloff or o + 4 * kw > rowtab:
            bad("ROWTAB[%d]" % r, "row outside the cells")
    if routeoff != rowtab + 2 * nrows or routeoff + 4 * nway != (propoff if nprop else n):
        bad("route", "offset %d, %d ways" % (routeoff, nway))
    route = [struct.unpack_from("<HH", p, routeoff + 4 * i) for i in range(nway)]
    for (bx, by) in route:
        if bx + FOOT_W > 8 * cols or by + FOOT_H > 8 * brows:
            bad("route", "point (%d, %d) outside the picture" % (bx, by))
    for i in range(nrows * kw):
        z0, sl, kd, fl = struct.unpack_from("<bBBB", p, celloff + 4 * i)
        if kd & 15 > KIND_GOAL or kd >> 4 > SURF_BOUNCE or fl & ~(FL_SAFE | FL_OCC | FL_OCCG | FL_OBS) \
                or (fl & FL_OCCG and not fl & FL_OCC):
            bad("cell %d" % i, "kind %d flags %d" % (kd, fl))
    props = read_props(p, propoff, nprop, blkoff, occidx, bad) if nprop else []
    return {"cols": cols, "brows": brows, "nblk": nblk, "mapsh": mapsh, "blkoff": blkoff,
            "occidx": occidx, "occrec": occrec, "nocc": nocc, "maskoff": maskoff, "nmask": nmask,
            "rowb": rowb, "gridoff": gridoff, "map": mp, "idx": idx, "recs": recs,
            "propoff": propoff, "nprop": nprop, "props": props, "ident": ident,
            "grid": {"nrows": nrows, "smin": smin, "amin": amin, "kw": kw, "rowtab": rt,
                     "x0": x0, "y0": y0, "start": (swx, swy), "route": route, "ident": ident,
                     "cells_raw": bytes(p[celloff:rowtab]), "celloff": celloff}}


def read_props(p, propoff, nprop, blkoff, occidx, bad):
    """the prop table (SPEC.md 128.12.3.1) as the guest reads it, checked: every
    offset inside the part, every pose map word a block offset, the kinds,
    the flags (UNDERSIDE refused), the segments' and sprites' places, and the
    records, pose maps, segments and sprites filling the part's tail exactly"""
    n = len(p)
    out = []
    if propoff + PROPREC * nprop > n:
        bad("PROPOFF", "the records run past the part")
    tail = propoff + PROPREC * nprop
    lanebr = []
    for i in range(nprop):
        r = propoff + PROPREC * i
        kind, flags, wx, wy, mask, shift, seed = struct.unpack_from("<BBBBBBH", p, r)
        if kind not in PK_NAMES:
            bad("prop %d" % i, "kind %d" % kind)
        if flags & ~PF_LANE:
            bad("prop %d" % i, "flags %02Xh (UNDERSIDE is reserved)" % flags)
        if mask and (not _pow2(mask + 1) or seed > mask):
            bad("prop %d" % i, "clock mask %d, seed %d" % (mask, seed))
        d = {"i": i, "kind": kind, "flags": flags, "at": (wx, wy), "mask": mask, "shift": shift, "seed": seed}
        if flags & PF_LANE:
            brow, col, w, h, poses, pmo = struct.unpack_from("<HBBBBH", p, r + 8)
            if not (1 <= w <= LANE_WMAX and 1 <= h <= LANE_HMAX and 2 <= poses <= LANE_PMAX):
                bad("prop %d" % i, "lane %d x %d, %d poses" % (w, h, poses))
            if pmo != tail or pmo + 2 * poses * w * h > n:
                bad("prop %d" % i, "pose maps at %d" % pmo)
            for k in range(poses * w * h):
                wd = struct.unpack_from("<H", p, pmo + 2 * k)[0]
                if wd < blkoff or wd >= occidx or (wd - blkoff) % 16:
                    bad("prop %d pose map[%d]" % (i, k), "word %d is not a block offset" % wd)
            tail += 2 * poses * w * h
            d["lane"] = {"brow": brow, "col": col, "w": w, "h": h, "poses": poses, "off": pmo}
            lanebr.append(brow)
            if len(lanebr) != i + 1:
                bad("prop %d" % i, "a lane after a record without one")
        else:
            d["lane"] = None
            if p[r + 8:r + 16] != bytes(8):
                bad("prop %d" % i, "lane bytes without the LANE flag")
        out.append(d)
    if lanebr != sorted(lanebr):
        bad("props", "lanes not sorted by first block row")
    for d in out:
        r = propoff + PROPREC * d["i"]
        if d["kind"] in (PK_TUBE, PK_WINDMILL):
            sub, dr, nseg, eg, so, T, g0, g1, g2, c0, c1 = struct.unpack_from("<BBBBHHhhhBB", p, r + 16)
            if sub > TK_DROP or dr > 3 or not 1 <= nseg <= SEG_MAX or so != tail:
                bad("prop %d" % d["i"], "tube %d %d %d at %d" % (sub, dr, nseg, so))
            segs = []
            for k in range(nseg):
                m, ix, iy, iz, ex, ey, ez, zz = struct.unpack_from("<Hhhhhhhh", p, so + SEGREC * k)
                if not m or zz:
                    bad("prop %d segment %d" % (d["i"], k), "steps %d" % m)
                segs.append({"m": m, "incx": ix, "incy": iy, "incz": iz, "ex": ex, "ey": ey, "ez": ez})
            if sum(sg["m"] for sg in segs) != T:
                bad("prop %d" % d["i"], "T %d is not its segments' steps" % T)
            tail += SEGREC * nseg
            d.update(sub=sub, dir=dr, segs=segs, eG=eg, T=T, g=(g0, g1, g2), closed=(c0, c1))
            if d["kind"] == PK_WINDMILL and (sub != TK_KEEP or not d["lane"] or g0 > 1 or not eg):
                bad("prop %d" % d["i"], "a windmill's record")
        elif d["kind"] == PK_BUMPER:
            K, lit, ph, cx, cy, KA = struct.unpack_from("<HBBHHH", p, r + 16)
            if not d["lane"] or cx != 16 * d["at"][0] + 8 or cy != 16 * d["at"][1] + 8:
                bad("prop %d" % d["i"], "a bumper's record")
            d.update(K=K, lit=lit, ph=ph, cx=cx, cy=cy, KA=KA)
    for d in out:                                  # the sprites after every segment
        r = propoff + PROPREC * d["i"]
        if d["kind"] == PK_PLATFORM:
            v, W, L, hP, so, pmax = struct.unpack_from("<HBBhHH", p, r + 16)
            if d["lane"] or so != tail or pmax != 2048 * L or not 1 <= L <= PL_LMAX or v & 63:
                bad("prop %d" % d["i"], "a lift's record")
            tail += PL_SPR
            d.update(v=v, W=W, L=L, hP=hP, hT=hP + 8 * L, spoff=so, pmax=pmax)
    if tail != n:
        bad("props", "the tail ends at %d, the part at %d" % (tail, n))
    return out


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
        self.ident = g["ident"]
        self.props = info["props"]

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


def bumper_table():
    """SPEC.md 128.12.6.3's OCTANT table: 78 entries (a, b), 0 <= b <= a <= 11,
    at a (a + 1) / 2 + b, three bytes each: |n| along the larger, |n| along
    the smaller (64 times the unit vector, half up; (0, 0) takes 45, 45) and
    the depth 192 - round(16 sqrt(a^2 + b^2)) in 1/16 gu; zeros where
    a^2 + b^2 >= 144 (no contact)"""
    out = []
    for a in range(OCT_N + 1):
        for b in range(a + 1):
            d2 = a * a + b * b
            if d2 >= (2 * PRAD) ** 2:
                out.append((0, 0, 0))
                continue
            if d2 == 0:
                nl = ns = 45
            else:
                d = math.sqrt(d2)
                nl = int(math.floor(64 * a / d + 0.5))
                ns = int(math.floor(64 * b / d + 0.5))
            out.append((nl, ns, 32 * PRAD - _isqrt_round(256 * d2)))
    assert len(out) == 78
    return out


OCTANT = bumper_table()


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
                 _east_w1=False, _no_stun=False, _abs_impact=False, _no_airclimb=False, _hop_add=False,
                 _gate_late=False, _kick_k=False, _no_carry=False, _stick=False, _exit_vel=False,
                 _carry_s=False):
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
        # wave 3's state (SPEC.md 128.12.6.6) and the prop table it reads
        self._gate_late, self._kick_k, self._no_carry = _gate_late, _kick_k, _no_carry
        self._carry_s = _carry_s
        self._stick, self._exit_vel = _stick, _exit_vel
        self.props = self.grid.props
        self.ps = 0
        self.wol = []
        self.wcell = None
        self.tube = self.tseg = self.tcnt = self.tsin = 0
        self.onp = 0
        self.pkick = [0xFFFA] * PROP_MAX            # -6: every post starts dark
        self.respawned = False
        self.nkick = self.nknock = self.ntube = 0
        self._tin = (0, 0)
        self._place(*self.grid.start)
        self.bx = self.by = 0
        self._derive(True)

    # -- the grid ------------------------------------------------------------
    def cell(self, wx, wy):
        return self.grid.cell(wx, wy)

    @staticmethod
    def h4(c, u, v):
        return 16 * c[0] + c[1] * u + c[2] * v

    def blocks(self, c, u, v, at=None):
        """does neighbour c block the ball at its point (u, v)?  A WALL always;
        a floor whose height there is above the step's START z + BZ_CLIMB,
        grounded or airborne (SPEC.md 128.11.8.2 step 5); a bumper's post
        cell never (128.12.6.5 step 5: its post is the circle's)"""
        if at is not None and c[4] & FL_OBS:
            pr = self.owner(at)
            if pr is not None and pr["kind"] == PK_BUMPER:
                return False
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
        self.tube = self.tseg = self.tcnt = 0
        self.onp = 0
        self._fill(wx, wy)

    # -- wave 3: the props (SPEC.md 128.12.3.2, 128.12.6) ----------------------
    def owner(self, cell):
        """the records' scan bz_win9f makes for an OBS cell: the first record
        whose anchor is the cell (a tube's, a windmill's, a bumper's, a lift's
        shaft).  -> the record, or None"""
        for pr in self.props:
            if pr["at"] == cell:
                return pr
        return None

    # the window's nine cells in bz_wrt's order (rows s - 2 .. s + 2, a rising)
    WORDER = ((-1, -1), (-1, 0), (0, -1), (-1, 1), (0, 0), (1, -1), (0, 1), (1, 0), (1, 1))

    def _fill(self, wx, wy):
        """the window refill round (wx, wy): bz_wol and bz_ps bit 0"""
        self.wcell = (wx, wy)
        self.wol = []
        if self.props:
            for dx, dy in self.WORDER:
                if self.cell(wx + dx, wy + dy)[4] & FL_OBS:
                    pr = self.owner((wx + dx, wy + dy))
                    if pr is not None:
                        self.wol.append((3 * (dy + 1) + dx + 1, pr["i"]))
        self._ps()

    def _ps(self):
        self.ps = (1 if self.wol else 0) | (2 if self.tube else 0) | (4 if self.onp else 0)

    def phase(self, pr, n):
        return (n + pr["seed"]) & pr["mask"]

    def gate_open(self, pr, n):
        if self._gate_late:
            n -= 1
        ph = self.phase(pr, n & 0xFFFF)
        return ph < pr["closed"][0] or ph >= pr["closed"][1]

    def state3(self):
        """wave 3's state as bonanzaphys compares it (SPEC.md 128.12.6.6)"""
        return (self.ps, tuple(self.wol), self.tube, self.tseg, self.tcnt, self.tsin, self.onp,
                tuple(self.pkick), self.nkick, self.nknock, self.ntube)

    def _capture(self, pr, n):
        """SPEC.md 128.12.6.1's capture"""
        self.tsin = max(abs(self.gvx), abs(self.gvy))
        self._tin = (self.gvx, self.gvy)
        sx_, sy_ = (16 * pr["at"][0] + 8, 16 * pr["at"][1] + 8)
        if pr["kind"] == PK_WINDMILL:
            sx_, sy_ = (16 * pr["at"][0], sy_) if pr["g"][0] == 0 else (sx_, 16 * pr["at"][1])
        c = self.cell(*pr["at"])
        self.gx, self.gy = sx_ << 8, sy_ << 8
        self.gz = self.h4(c, sx_ - 16 * pr["at"][0], sy_ - 16 * pr["at"][1]) << 6
        self.gvx = self.gvy = self.gvz = 0
        self.air = 0
        self.sqf = 0
        self.ghv = 0
        self.onp = 0
        self.tube, self.tseg, self.tcnt = pr["i"] + 1, 0, pr["segs"][0]["m"]
        self.ntube += 1
        self._ps()
        self.events.append(("capture", self.nstep + 1, pr["i"], self.tsin))

    def _transit(self):
        """SPEC.md 128.12.6.1: the ghost along its segments, then the exit"""
        pr = self.props[self.tube - 1]
        sg = pr["segs"][self.tseg]
        self.gx += sg["incx"]
        self.gy += sg["incy"]
        self.gz += sg["incz"]
        self.tcnt -= 1
        if self.tcnt:
            return
        self.gx, self.gy, self.gz = sg["ex"] << 8, sg["ey"] << 8, sg["ez"] << 8
        self.tseg += 1
        if self.tseg < len(pr["segs"]):
            self.tcnt = pr["segs"][self.tseg]["m"]
            return
        # the exit
        self.tube = self.tseg = 0
        v = max(self.tsin, TMIN)
        ux, uy = DIR_VEC[pr["dir"]]
        if self._exit_vel and pr["sub"] == TK_KEEP:     # the negative control: along the entry velocity
            ex, ey = self._tin
            if abs(ex) >= abs(ey):
                ux, uy = (1 if ex >= 0 else -1), 0
            else:
                ux, uy = 0, (1 if ey >= 0 else -1)
        if pr["sub"] == TK_LAUNCH:
            self.gvx, self.gvy, self.gvz = pr["g"]
            self.air = 1
            self.ztop = self.gz >> 8
            self.gz += self.gvz
        else:
            self.gvx, self.gvy, self.gvz = ux * v, uy * v, 0
            self.air = 1 if pr["sub"] == TK_DROP else 0
            self.ztop = self.gz >> 8
        self._fill(self.gx >> 12, self.gy >> 12)
        self.events.append(("exit", self.nstep + 1, pr["i"], TK_NAMES[pr["sub"]], (self.gvx, self.gvy, self.gvz)))

    def _circle(self, pr, n):
        """SPEC.md 128.12.6.3: a post's circle, and the kick"""
        c = self.cell(*pr["at"])
        top = (self.h4(c, 8, 8) >> 2) + pr["ph"]
        if not self.zs < top << 8:              # the step's START z, as the edge test's (so a ball
            return                              # coming down onto the top lands on it)
        du = (self.gx >> 8) - pr["cx"]
        dv = (self.gy >> 8) - pr["cy"]
        a, b = abs(du), abs(dv)
        if max(a, b) > OCT_N:
            return
        if a >= b:
            nx, ny, depth = OCTANT[a * (a + 1) // 2 + b]
        else:
            ny, nx, depth = OCTANT[b * (b + 1) // 2 + a]
        if not depth:
            return
        sx = 1 if du >= 0 else -1
        sy = 1 if dv >= 0 else -1
        nx, ny = sx * nx, sy * ny
        self.gx += sx * ((depth * abs(nx)) >> 2)
        self.gy += sy * ((depth * abs(ny)) >> 2)
        d = (self.gvx * nx + self.gvy * ny) >> 6
        if d < 0 and not self._kick_k:
            t = max(pr["K"], ((E_BUMPER * -d) >> 8) + pr["KA"])
        else:
            t = max(pr["K"], d)
        self.gvx = _clamp(self.gvx + (((t - d) * nx) >> 6), VMAXG)
        self.gvy = _clamp(self.gvy + (((t - d) * ny) >> 6), VMAXG)
        self.pkick[pr["i"]] = n
        self.nkick += 1
        self.events.append(("kick", self.nstep + 1, pr["i"], d, t, nx, ny))

    def _floor(self, C, at, n):
        """step 6's floor at the centre's point (SPEC.md 128.12.6.3, 128.12.6.4):
        -> (the cell to judge, its h4 there, the platform carrying or None)"""
        u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
        if C[4] & FL_OBS:
            pr = self.owner(at)
            if pr is not None and pr["kind"] == PK_PLATFORM:
                # the LIFT's shaft: its top at n + 1 is the floor for a ball
                # that began the step at or over it less BZ_CLIMB
                top4 = 4 * pr["hP"] + (plat_pos(pr, (n + 1) & 0xFFFF) >> 6)
                if self.zs >= (top4 << 6) - (CLIMB << 8):
                    return (top4 >> 4, 0, 0, KIND_FLOOR, 0, C[5]), top4, pr
                return C, 0, None
            if pr is not None and pr["kind"] == PK_BUMPER:
                a, b = abs((self.gx >> 8) - pr["cx"]), abs((self.gy >> 8) - pr["cy"])
                h4 = self.h4(C, u, v)
                if max(a, b) <= OCT_N:
                    depth = OCTANT[max(a, b) * (max(a, b) + 1) // 2 + min(a, b)][2]
                    if depth > 16 * PRAD:
                        h4 += 4 * pr["ph"]
                return C, h4, None
        return C, (self.h4(C, u, v) if C[3] in (KIND_FLOOR, KIND_GOAL) else 0), None

    def _door(self, C, cwx, cwy):
        """the centre's cell a windmill's IN: (0 for a -x doorway, 1 for -y, the record)"""
        if not (self.wol and C[4] & FL_OBS):
            return None
        pr = self.owner((cwx, cwy))
        if pr is None or pr["kind"] != PK_WINDMILL:
            return None
        return (pr["g"][0], pr)

    def _door_touch(self, C, u, v):
        """...and the ball low enough to touch its doorway: z <= IN's floor + BZ_CLIMB"""
        return self.gz <= (self.h4(C, u, v) << 6) + (CLIMB << 8)

    def over_slab(self, pr, n=None):
        """the centre over the lift's slab: in its shaft (any n)"""
        return (self.gx >> 12, self.gy >> 12) == tuple(pr["at"])

    def poke(self, wx, wy, gvx=0, gvy=0):
        """a scenario's start: the centre of tile (wx, wy) on its floor,
        grounded, at a ground velocity (the rows' POKED scenarios do the same
        through the guest's variables)"""
        self._place(wx, wy)
        self.gvx, self.gvy = gvx, gvy
        self._ps()
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
        self._ps()
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
        n = self.nstep & 0xFFFF
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
        # wave 3: one byte test of bz_ps bits 1 - 2; in a tube, the transit
        if self.tube:
            self._transit()
            self._ps()
            return self._end()
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
        sgx, sgy, sgz = self.gx, self.gy, self.gz   # the undo's start: before the carry too
        scell = (cwx, cwy)
        if self.onp and not self._no_carry:         # the carry: the lift's rise first (z only)
            pr = self.props[self.onp - 1]
            dd = plat_pos(pr, (n + 1) & 0xFFFF) - plat_pos(pr, n)
            if self._carry_s:                       # (a red arm: wave 3's first design, carried along +s)
                self.gx += dd
                self.gy += dd
            else:
                self.gz += dd
        self.zs = self.gz                           # the START z the climb and the slab judge: after the carry
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
        if (cwx, cwy) != self.wcell:
            self._fill(cwx, cwy)
        if self.wol and C[4] & FL_OBS:               # the prop path: a plain tube's drain
            pr = self.owner((cwx, cwy))
            if pr is not None and pr["kind"] == PK_TUBE:
                u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
                if not self.air or self.gz <= (self.h4(C, u, v) << 6) + (CLIMB << 8):
                    self._capture(pr, n)
                    return self._end()
        # 5. walls: the circle, the edge test SYMMETRIC (128.11.8.3), every
        # zeroing a reflection (128.11.8.4)
        pu, pv = self.gx & 0xFFF, self.gy & 0xFFF
        u, v = pu >> 8, pv >> 8
        lo = RAD << 8
        hi = (16 - RAD) << 8 if not self._east_w1 else ((16 - RAD) << 8) + 255
        door = self._door(C, cwx, cwy)
        if pu < lo:
            c = self.cell(cwx - 1, cwy)
            if self.blocks(c, 16, v, (cwx - 1, cwy)):
                if door and door[0] == 0 and self._door_touch(C, u, v):
                    if self.gate_open(door[1], n):
                        self._capture(door[1], n)
                        return self._end()
                    self.gx = (16 * cwx + RAD) << 8
                    if self.gvx < 0:
                        self.gvx = _refl(self.gvx, door[1]["eG"])
                        self.nknock += 1
                        self.events.append(("knock", self.nstep + 1, door[1]["i"], self.gvx))
                else:
                    self.gx = (16 * cwx + RAD) << 8
                    if self.gvx < 0:
                        self.gvx = _refl(self.gvx, self.e_wall(c))
                        self.events.append(("wall", self.nstep + 1, (-1, 0)))
        elif pu > hi:
            c = self.cell(cwx + 1, cwy)
            if self.blocks(c, 0, v, (cwx + 1, cwy)):
                self.gx = (16 * cwx + 16 - RAD) << 8
                if self.gvx > 0:
                    self.gvx = _refl(self.gvx, self.e_wall(c))
                    self.events.append(("wall", self.nstep + 1, (1, 0)))
        if pv < lo:
            c = self.cell(cwx, cwy - 1)
            if self.blocks(c, u, 16, (cwx, cwy - 1)):
                if door and door[0] == 1 and self._door_touch(C, u, v):
                    if self.gate_open(door[1], n):
                        self._capture(door[1], n)
                        return self._end()
                    self.gy = (16 * cwy + RAD) << 8
                    if self.gvy < 0:
                        self.gvy = _refl(self.gvy, door[1]["eG"])
                        self.nknock += 1
                        self.events.append(("knock", self.nstep + 1, door[1]["i"], self.gvy))
                else:
                    self.gy = (16 * cwy + RAD) << 8
                    if self.gvy < 0:
                        self.gvy = _refl(self.gvy, self.e_wall(c))
                        self.events.append(("wall", self.nstep + 1, (0, -1)))
        elif pv > hi:
            c = self.cell(cwx, cwy + 1)
            if self.blocks(c, u, 0, (cwx, cwy + 1)):
                self.gy = (16 * cwy + 16 - RAD) << 8
                if self.gvy > 0:
                    self.gvy = _refl(self.gvy, self.e_wall(c))
                    self.events.append(("wall", self.nstep + 1, (0, 1)))
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
            if depth and self.blocks(c, 16 if dx < 0 else 0, 16 if dy < 0 else 0, (cwx + dx, cwy + dy)):
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
        # wave 3: each post on bz_wol, the circle (SPEC.md 128.12.6.3)
        for _ci, pi in list(self.wol):
            pr = self.props[pi]
            if pr["kind"] == PK_BUMPER:
                self._circle(pr, n)
        if self.wol and (self.gx >> 12, self.gy >> 12) != self.wcell:
            self._fill(self.gx >> 12, self.gy >> 12)
        # the fallback
        cwx, cwy = self.gx >> 12, self.gy >> 12
        if (cwx, cwy) != scell:
            C = self.cell(cwx, cwy)
            u, v = (self.gx >> 8) & 15, (self.gy >> 8) & 15
            if self.blocks(C, u, v, (cwx, cwy)):
                e = self.e_wall(C)
                if cwx != scell[0]:
                    self.gvx = _refl(self.gvx, e)
                if cwy != scell[1]:
                    self.gvy = _refl(self.gvy, e)
                self.gx, self.gy, self.gz = sgx, sgy, sgz
                cwx, cwy = scell
                if self.wcell != scell:
                    self._fill(*scell)
                self.events.append(("undo", self.nstep + 1, None))
        # 6. the floor (a track cell's and a post cell's are 128.12.6.4's and 128.12.6.3's)
        C = self.cell(cwx, cwy)
        Cv = C
        C, h4, slab = self._floor(C, (cwx, cwy), n)
        solid = C[3] in (KIND_FLOOR, KIND_GOAL)
        h = h4 << 6
        onslab = False
        lifted = False
        if not self.air:
            if self.hopw and not stun and solid:
                # 128.11.8.6: the Hop from the ground
                self.air = 1
                self.gvz = min(VZMAX, self.gvz + m["HOP"])
                self.ztop = self.gz >> 8
                self.gz += self.gvz
                self.hopw = 0
                self.nhop += 1
                lifted = True
                self.events.append(("hop", self.nstep + 1, self.gvz))
            elif not solid or h < self.gz + self.gvz - G - (STICK << 8):
                self.air = 1
                if self._takeoff_zero:
                    self.gvz = 0
                self.ztop = self.gz >> 8
                self.gz += self.gvz
                lifted = True
                self.events.append(("takeoff", self.nstep + 1, self.gvz))
            else:
                self.gz = h
                onslab = slab is not None
        else:
            if solid and self.gz <= h:
                self._land(C, h, K, stun)
                onslab = slab is not None
            elif Cv[3] == KIND_VOID and not solid and self.gz < (4 * Cv[0]) << 8:
                self._respawn()
                return self._end()
        # bz_onp (SPEC.md 128.12.6.4): SET grounded on, or landed on, the slab;
        # KEPT airborne over its square at n + 1; CLEARED otherwise
        if onslab:
            self.onp = slab["i"] + 1
        elif self.onp and self.air and self.over_slab(self.props[self.onp - 1], n + 1) \
                and not (self._stick and lifted):
            pass
        else:
            self.onp = 0
        self._ps()
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


def encode_log(keys, course=0, mat=MAT_RUBBER, complete=True, ident=0):
    """a step's key bytes -> the log's bytes, run-length coded as the guest's
    recorder does (a run is at most 255 steps; a flush into a full buffer
    truncates).  ident: the course's identity at +14 (SPEC.md 128.12.8; a
    Course's .ident).  -> bytes (the 16-byte header and the runs, not padded)"""
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
    head = b"BZR1" + struct.pack("<BBBBIHH", course, mat, flags, 0, steps, len(runs), ident)
    return head + b"".join(struct.pack("<BB", k, n) for k, n in runs)


def log_ident(log):
    """a log's course identity, +14 (SPEC.md 128.12.8)"""
    return struct.unpack_from("<H", log, 14)[0]


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

    def __init__(self, phys, herc, brows, cols, _w1=False, heavy=None):
        self.p, self.herc, self._w1 = phys, herc, _w1
        self.heavy = heavy                     # a Heavy (wave 3's rule, 128.12.7), or None: wave 2's camera
        self.nhvy = self.nwr = self.nwc = self.nhedge = 0
        self.want = (False, False)             # this frame: a row, a column outstanding (GLIDE's pans)
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
        if getattr(p, "tube", 0):              # wave 3: a ghost is fast on both axes (128.12.6.1)
            fastx = fasty = True
        R0, c0 = self.R0, self.c0
        hv = self.heavy.frame(self) if self.heavy is not None else (0, True, True)
        keep = (self.gpx, self.gpar, self.gpy)
        # ---- across ----
        if p.vx:
            self.gdx = 0 if p.vx > 0 else 1
        bc = px + 8
        off = bc - 8 * c0
        out = off < 2 * W or off > 6 * W
        if out and not self.gpx:
            self.gpx, self.gpar = 1, 0
        C = c0
        self.want_c = self.want_r = False
        if self.gpx:
            if self.gdx == 0:
                t = bc - 2 * W
                ct = t >> 3 if t >= 0 else 0
            else:
                t = bc - 6 * W
                ct = (t + 7) >> 3 if t > 0 else 0
            ct = min(ct, self.cmax)
            self.want_c = ct != c0
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
            self.want_r = rt != R0
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
        self.want = (R != R0, C != c0)
        level, relr, relc = hv
        if level:                              # 128.12.7: the heavy frame withholds
            self.nhvy += 1
            if relr or relc:
                self.nhedge += 1
            if not relc and C != c0:
                C = c0
                self.nwc += 1
                self.gpx, self.gpar = 1, keep[1]
            if not relr:
                lim = 0 if level == 2 else 1
                if abs(R - R0) > lim:
                    self.nwr += abs(R - R0) - lim
                    R = R0 + max(-lim, min(lim, R - R0))
                    self.gpy = 1
        full = abs(R - R0) > MAXR or abs(C - c0) > MAXC
        self.R0, self.c0 = R, C
        return R - R0, C - c0, full


class Heavy:
    """bz_props's bz_heavy and its contact choice, the host model's (SPEC.md
    128.12.7, 128.13.6, 128.13.9): from what is known before the camera - the
    ball after the frame's steps, its old and new footprints, the lanes'
    true and drawn poses and the window as it stands - level 2 (the frame
    draws a contact group), level 1 (no group, and the slab shown near the
    window's edge on the ball's side: the clause alone, 128.13.6) or 0; and
    the edge clause, per axis.

    The choice is bz_props's: a must-draw rotor (of two, the IN cell nearer
    the window's centre); else the platform's box when its drawn line changes
    while shown - which WAITS one frame (its drawn line holds; never two
    running, never while the lift carries the ball, never LEAVING: its drawn
    footprint shown and its true one not, 128.13.4.3) on a CROWDED frame (the
    ball's and the shadow's footprints, old and new, not one BZ_BOXW x
    BZ_BOXH box: bz_bsone), and for a PROMOTED wheel lane on another frame
    with no post lighting; with a post lighting the post is the group and the
    box a second rect (the model takes the frame to have room for it); else a
    post lighting; else the contact candidate due longest - on a frame that
    allows a contact lane (bz_conok: no occluder pass, the ball outside the
    edge zone, not crowded) or once it has been due WPRF frames; else the
    WHEEL candidate due longest once it has been due WPRO frames on such a
    frame, or WPRF on any (bz_wpro: PROMOTED).  A lane the group draws is
    drawn and its age 0 (bz_csync).  The wheel: every other wheel candidate
    is drawn by the frame's end - or, with WCAP, the first WCAP of them in
    raster order and the rest stay due and age (a wheel that runs out of
    room, which is when the promotion fires) - and a deferred contact lane
    waits."""

    def __init__(self, phys, wcap=None):
        self.p = phys
        self.wcap = wcap                        # None: the wheel takes every candidate
        self.drawn = {}
        self.pline = {}
        self.old = None                         # the last frame's footprint (x4, py)
        self.oshadow = None
        self.ncon = self.ndef = self.nmust = self.npbx = 0
        self.npwt = 0                           # the platform's box waited (bz_npwt)
        self.npro = 0                           # a wheel lane PROMOTED to the contact group
        self.pylp = False                       # ...last frame (never two running)
        self.levels = [0, 0, 0]
        self.hold = {}                          # a post's lit frames left ON THE GLASS (bz_lhold)
        self.seen = {}                          # the kick it last saw (bz_lkick)
        self.age = {}                           # frames due and shown (bz_lage)

    def _true(self, r, n_last):
        if r["kind"] == PK_WINDMILL:
            return ((n_last + r["seed"]) & r["mask"]) >> r["shift"]
        i = r["i"]
        k = self.p.pkick[i]
        if self.seen.setdefault(i, k) != k:     # a new kick: lit for PLITF frames on the glass
            self.seen[i] = k
            self.hold[i] = PLITF
        return 1 if self.hold.get(i, 0) else 0

    def _draw(self, r, n_last):
        """the contact group draws lane R: drawn = true, its age 0 (bz_csync)"""
        self.drawn[r["i"]] = self._true(r, n_last)
        self.age[r["i"]] = 0

    def frame(self, g):
        p = self.p
        W, rl = g.W, g.rl
        ya, yb = g.R0 * rl, g.R0 * rl + WIN_LINES
        xa, xb = 8 * g.c0, 8 * (g.c0 + W)
        n_last = (p.nstep - 1) & 0xFFFF
        new = None if p.tube else ((p.px & ~3), p.py)
        sh = shadow(p) if not p.tube else None
        news = ((sh[1] & ~3), sh[0]) if sh else None
        rect = lambda f, h: (f[0], f[1], f[0] + FOOT_W, f[1] + h)
        frects = [rect(f, FOOT_H) for f in (self.old, new) if f] + [rect(f, 6) for f in (self.oshadow, news) if f]
        cl = p.cell(p.gx >> 12, p.gy >> 12)
        passon = bool(new) and bool(cl[4] & (FL_OCC if p.air else FL_OCCG))
        crowded = False                         # bz_bsone: the ball's and the shadow's groups two boxes
        if frects and not p.tube:
            crowded = (max(r[2] for r in frects) - 1 >> 3) - (min(r[0] for r in frects) >> 3) > 3 or \
                max(r[3] for r in frects) - min(r[1] for r in frects) > 24
        edge_r = bool(new) and (new[1] < ya + HEDGE or new[1] + FOOT_H > yb - HEDGE)
        edge_c = bool(new) and (new[0] < xa + 24 or new[0] + FOOT_W > xb - 24)
        conok = bool(p.tube) or not (passon or edge_r or edge_c or crowded)     # bz_conok
        shown = lambda r4: r4[0] < xb and xa < r4[2] and r4[1] < yb and ya < r4[3]
        contact = None
        must = []
        mustp = []
        cands = []
        wheel = []
        slabbox = False
        slabnear = False
        slableave = False
        plat = None
        # the ball's side of the window (bz_pnear: GLIDE pans toward it)
        up = bool(new) and 2 * new[1] + FOOT_H < 2 * ya + WIN_LINES
        left = bool(new) and 2 * new[0] + FOOT_W < xa + xb
        for r in p.props:
            L = r["lane"]
            if r["kind"] == PK_PLATFORM:
                x_l, y_t = slab_xy(r, plat_pos(r, p.nstep & 0xFFFF) >> 8, p.x0, p.y0)
                r4 = (x_l, y_t, x_l + PL_W, y_t + PL_H)
                yd = self.pline.get(r["i"], y_t)
                if shown(r4) or shown((x_l, yd, x_l + PL_W, yd + PL_H)):
                    if yd != y_t:               # its drawn or its true footprint shown
                        slabbox = True
                        slableave = not shown(r4)
                    if ((up and y_t < ya + 2 * rl) or (not up and y_t + PL_H > yb - 2 * rl)
                            or (left and x_l < xa + 8) or (not left and x_l + PL_W > xb - 8)):
                        slabnear = True
                plat = (r["i"], y_t)            # (its drawn line: after the choice, which may wait)
                continue
            if not L:
                continue
            r4 = (8 * L["col"], 8 * L["brow"], 8 * (L["col"] + L["w"]), 8 * (L["brow"] + L["h"]))
            if self.hold.get(r["i"]):           # a lit post's frames on the glass (bz_props)
                if not shown(r4):
                    self.hold[r["i"]] = 0
                elif self.drawn.get(r["i"]) == 1:
                    self.hold[r["i"]] -= 1
            tq = self._true(r, n_last)
            dq = self.drawn.setdefault(r["i"], tq)
            if tq == dq:
                self.age[r["i"]] = 0
                continue
            if not shown(r4):                   # wholly outside: its map now, in RAM
                self.drawn[r["i"]] = tq
                self.age[r["i"]] = 0
                continue
            self.age[r["i"]] = min(255, self.age.get(r["i"], 0) + 1)
            if r["kind"] == PK_WINDMILL:
                cell = [c for c, pi in p.wol if pi == r["i"]]
                c0, c1 = r["closed"][0] >> r["shift"], r["closed"][1] >> r["shift"]
                if cell and (c0 <= tq < c1) != (c0 <= dq < c1):
                    must.append((0 if cell[0] == 4 else 1 if cell[0] & 1 else 2, len(must), r))
                    continue
            if r["kind"] == PK_BUMPER and tq == 1 and dq == 0:
                mustp.append(r)                 # a post LIGHTING is must-draw (the owner's preview)
                continue
            if any(_meet(r4, *f) for f in frects):
                cands.append(r)
            elif len(wheel) < WIN_LANES:
                wheel.append(r)                 # (raster order: the props' order)
        wbest = None                            # the wheel candidate due longest (the first of a tie)
        for r in wheel:
            if self.age[r["i"]] > (self.age[wbest["i"]] if wbest else 0):
                wbest = r
        wpro = wbest is not None and (self.age[wbest["i"]] >= WPRF or
                                      (self.age[wbest["i"]] >= WPRO and conok))
        waits = len(must) + len(mustp)          # must-draw lanes not chosen wait a frame
        pwait = promo = False
        if must:
            contact = min(must, key=lambda t: t[:2])[2]
            waits -= 1
            slabbox = False                     # (its line holds: no window has both, 128.12.4.6)
        elif slabbox:
            if not self.pylp and not p.onp and not slableave:
                if crowded:                     # (a) and (b): the box waits, a post lighting is the group
                    pwait = True
                elif not mustp and wpro:        # (c): the box waits for a promoted wheel lane
                    pwait = promo = True
            if pwait:
                slabbox = False
                self.npwt += 1
                waits += 1
        if contact is None and not promo:
            if slabbox:
                self.npbx += 1                  # the slab's box: the group, or beside a post lighting
                if not mustp:
                    contact = "slab"
            if mustp:
                contact = mustp[0]
                waits -= 1
        if contact is None and not promo and cands:
            cands.sort(key=lambda r: (-self.age.get(r["i"], 0), r["i"]))
            best = cands[0]
            if conok or self.age.get(best["i"], 0) >= WPRF:
                contact = best
                cands = cands[1:]
            elif wpro:
                promo = True
        elif contact is None and not promo and wpro:
            promo = True
        if promo:
            contact = wbest
            wheel.remove(wbest)
            self.npro += 1
        if contact is not None and contact != "slab":
            if contact in mustp or any(contact is t[2] for t in must):
                self.nmust += 1
            self._draw(contact, n_last)
        self.pylp = pwait
        if plat is not None and not pwait and not must:
            self.pline[plat[0]] = plat[1]
        for k, r in enumerate(wheel):           # the wheel: the rest by the frame's end (or WCAP of them)
            if self.wcap is None or k < self.wcap:
                self.drawn[r["i"]] = self._true(r, n_last)
                self.age[r["i"]] = 0
        self.ndef += len(cands) + waits
        level = 0
        if contact is not None:
            level = 2
            self.ncon += 1
        elif slabnear:
            level = 1
        self.old, self.oshadow = new, news
        self.levels[level] += 1
        if p.tube:
            return 0, True, True
        return level, edge_r, edge_c


def glide_run(course, herc, rate=1.0, phase=0.0, frames=1200, mat=None, _w1=False, heavy=False, frame_cb=None):
    """the benchmark under GLIDE: frames at the card's refresh, `rate` times
    the real step rate, the first frame a full write with its sub-ticks
    discarded.  heavy: wave 3's rule on (Heavy).  frame_cb(p, g, dr, dc)
    after each frame's camera.  -> ({direction: frames that scrolled that
    way}, Physics); the Glide is p.glide"""
    p = Physics(course, mat=mat)
    g = Glide(p, herc, course.brows, course.cols, _w1=_w1, heavy=Heavy(p) if heavy else None)
    p.glide = g
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
        if frame_cb:
            frame_cb(p, g, dr, dc)
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
              "; wave 3 (SPEC.md 128.12.3, 128.12.6): the props, the prop table, the tubes",
              "BZ_FL_OBS       equ %d        ; grid +3 bit 3: the cell belongs to a prop" % FL_OBS,
              "BZ_PROPMAX      equ %d       ; props a course (bz_ldrw, bz_lage, bz_pkick)" % PROP_MAX,
              "BZ_PROPREC      equ %d       ; bytes a prop record" % PROPREC,
              "BZ_PK_TUBE      equ %d        ; record +0, the kind" % PK_TUBE,
              "BZ_PK_WINDMILL  equ %d" % PK_WINDMILL,
              "BZ_PK_BUMPER    equ %d" % PK_BUMPER,
              "BZ_PK_PLATFORM  equ %d" % PK_PLATFORM,
              "BZ_PF_LANE      equ %d        ; record +1: the record has a lane" % PF_LANE,
              "BZP_KIND        equ 0        ; record fields",
              "BZP_FLAGS       equ 1",
              "BZP_WX          equ 2        ; the anchor cell",
              "BZP_WY          equ 3",
              "BZP_MASK        equ 4        ; the clock's P - 1 (0: no clock)",
              "BZP_SHIFT       equ 5        ; a rotor's pose = phase >> shift",
              "BZP_SEED        equ 6        ; word",
              "BZP_LROW        equ 8        ; LANE: its first block row (word)",
              "BZP_LCOL        equ 10       ; ...its first word column",
              "BZP_LW          equ 11       ; ...its width in words (1 - 4)",
              "BZP_LH          equ 12       ; ...its height in block rows (1 - 3)",
              "BZP_LPOSES      equ 13       ; ...its poses (2 - 16)",
              "BZP_LMAPS       equ 14       ; ...the offset of its pose maps (word)",
              "BZP_TSUB        equ 16       ; TUBE / WINDMILL: 0 KEEP, 1 LAUNCH, 2 DROP",
              "BZP_TDIR        equ 17       ; ...the exit: 0 +x, 1 -x, 2 +y, 3 -y",
              "BZP_TNSEG       equ 18       ; ...segments (1 - 8)",
              "BZP_TEG         equ 19       ; ...a windmill's gate restitution (0 a tube)",
              "BZP_TSEGS       equ 20       ; ...the segments' offset (word)",
              "BZP_TT          equ 22       ; ...T, the transit's steps (word)",
              "BZP_TGVX        equ 24       ; ...LAUNCH's gvx; a windmill's doorway (0 -x, 1 -y)",
              "BZP_TGVY        equ 26",
              "BZP_TGVZ        equ 28       ; ...LAUNCH's gvz; DROP's exit z (whole px)",
              "BZP_TC0         equ 30       ; ...a windmill's closed window c0 .. c1 (phases)",
              "BZP_TC1         equ 31",
              "BZP_BK          equ 16       ; BUMPER: K (word)",
              "BZP_BLIT        equ 18       ; ...its lit FRAMES on the glass",
              "BZP_BH          equ 19       ; ...the post's height, px",
              "BZP_BCX         equ 20       ; ...the post's centre, integer gu (words)",
              "BZP_BCY         equ 22",
              "BZP_BKA         equ 24       ; ...KA (word)",
              "BZP_PV          equ 16       ; PLATFORM (a LIFT): v (word, 1/256 px a step)",
              "BZP_PW          equ 18       ; ...the dwell W",
              "BZP_PL          equ 19       ; ...L, its rise in units",
              "BZP_PHP         equ 20       ; ...its LOW top hP (signed word, whole px)",
              "BZP_PSPR        equ 22       ; ...its sprite's offset (word)",
              "BZP_PMAX        equ 24       ; ...PMAX = 2048 L, its rise in 1/256 px (word)",
              "BZ_SEGREC       equ %d       ; a tube segment: +0 m, +2/4/6 the increments, +8/10/12 the END" % SEGREC,
              "BZ_TK_KEEP      equ %d" % TK_KEEP,
              "BZ_TK_LAUNCH    equ %d" % TK_LAUNCH,
              "BZ_TK_DROP      equ %d" % TK_DROP,
              "BZ_TMIN         equ %d       ; KEEP's and DROP's least exit speed" % TMIN,
              "BZ_EGATE        equ %d      ; a blade's restitution (the record's +19 carries it)" % E_GATE,
              "BZ_PRAD         equ %d        ; a post's radius, gu" % PRAD,
              "BZ_PLITF        equ %d        ; a kicked post's lit frames on the glass" % PLITF,
              "BZ_OCTN         equ %d       ; the octant table: max(|du|, |dv|) <= 11" % OCT_N,
              "BZ_PLW          equ %d       ; the slab's sprite: px wide" % PL_W,
              "BZ_PLH          equ %d       ; ...lines (16 of top, 2 of lip)" % PL_H,
              "BZ_PLSPR        equ %d      ; ...two parity copies of mask and frame" % PL_SPR,
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
              "; the bumpers' OCTANT table (SPEC.md 128.12.6.3): 78 entries (a, b),",
              "; 0 <= b <= a <= 11, at a (a + 1) / 2 + b: |n| along the larger, |n| along the",
              "; smaller (x 64) and the depth in 1/16 gu; zeros where a^2 + b^2 >= 144",
              "%macro BZ_OCTANT_TABLE 0"]
    for a in range(OCT_N + 1):
        k0 = a * (a + 1) // 2
        lines.append("    db " + ", ".join("%d,%d,%d" % OCTANT[k0 + b] for b in range(a + 1)) + "   ; a = %d" % a)
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
        ("a prop of no kind (prop is wave 3's statement)", F + "prop tile 4 4\n", "prop takes windmill, bumper or platform"),
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


# wave 3's malformed props (SPEC.md 128.12.13.1 item 2), every one a string here
_W3W = ('course P "p"\nwidth 64\nfloor rect 6 9 11 14 flat 16\nwall rect 6 5 12 9 flat 22\n'
        'floor rect 12 5 16 9 flat 20\ntube keep 9 9 12 6 via 9 6\nprop windmill 9 9\nstart 9 12\n')
_W3P = ('course Q "q"\nwidth 64\nfloor rect 6 6 10 10 flat 4\nfloor rect 11 7 13 10 flat 1\nstart 7 7\n'
        'prop platform 10 8 3\n')
_W3H = ('course H "h"\nwidth 64\nfloor rect 6 9 16 14 flat 16\nwall rect 6 5 16 9 flat 22\n'
        'floor rect 6 3 14 5 flat 20\nstart 9 12\ntube keep 7 9 7 4\ntube keep 10 9 10 4\n'
        'tube keep 13 9 13 4\nprop windmill 7 9 seed %d\nprop windmill 10 9 seed %d\nprop windmill 13 9 seed %d\n')
_W3F = 'course F "f"\nwidth 64\nfloor band -10 10 26 %d flat 0\nstart %d %d\n'


def _posts(cells):
    return "".join("prop bumper %d %d\n" % c for c in cells)


def _sa(s_, a):
    return ((s_ + a) // 2, (s_ - a) // 2)


def _corner_case():
    """a start window with no free calibration corner on the CGA: posts
    placed (by the window's own arithmetic) in all four corners"""
    base = _W3F % (60, 20, 20)
    c = compile_course(base, "<corners>")
    p = Physics(c)
    W, H, rl, lsh = CARDS[0]
    rmax, cmax = c.brows * 8 // rl - H, c.cols - W
    R0 = max(0, min(max(0, p.py + 8 - WIN_LINES // 2) >> lsh, rmax))
    C0 = max(0, min(max(0, p.px + 8 - 4 * W) >> 3, cmax))
    ya, yb = R0 * rl, R0 * rl + WIN_LINES
    top, bot = (ya + 7) >> 3, (yb >> 3) - 3
    cells = []
    for bc, br in ((C0, top), (C0 + W - 4, top), (C0, bot), (C0 + W - 4, bot)):
        rx = (8 * bc, 8 * br, 8 * (bc + 4), 8 * (br + 3))
        for (wx, wy), t in sorted(c.tiles.items()):
            if (wx, wy) in cells or (wx, wy) == c.start:
                continue
            cx = 16 * (wx - wy) + c.x0
            cy = 8 * (wx + wy) + 8 - 4 * t.z0 + c.y0
            if _meet((cx - 8, cy - 13, cx + 8, cy + 5), *rx) and all(abs((wx - a) - (wy - b)) > 1 or
                                                                    abs((wx + a) - (wy + b)) > 3
                                                                    for a, b in cells):
                cells.append((wx, wy))
                break
    return base + _posts(cells)


def _wave3_cases():
    W, P = _W3W, _W3P
    big = _W3F % (60, 20, 20)
    seven = big + _posts([_sa(36, a) for a in (-8, -4, 0, 4, 8)] + [_sa(42, a) for a in (-6, 6)])
    nine = _W3F % (70, 20, 20) + _posts([_sa(s_, a) for s_ in (32, 46, 61) for a in (-6, 0, 6)])
    return [
        ("a tube body cell not a WALL", W + "floor tile 10 6 flat 21\n", "is not a WALL"),
        ("a tube leg off the axes", _swap(W, "tube keep 9 9 12 6 via 9 6", "tube keep 9 9 12 6"),
         "not along a tile axis"),
        ("a KEEP exit's next cell not a FLOOR", _swap(W, "via 9 6", "via 9 6 out -x"), "is not a FLOOR"),
        ("a LAUNCH over the caps", W + "tube launch 7 12 7 14 speed 500 0 0\n", "over the caps"),
        ("a DROP under 1 unit", W + "tube drop 7 12 7 14 height 0.5\n", "under 1 unit"),
        ("a DROP whose mouth faces -x", W + "tube drop 7 12 7 14 out -x height 2\n", "must face +x or +y"),
        ("a LAUNCH whose flight lands off a FLOOR", W + "wall tile 7 13 flat 17\nfloor tile 7 14 flat 16\n"
         "tube launch 7 12 7 14 speed 0 384 300\n", "not a landing on a FLOOR"),
        ("a DROP whose landing range does", W + "wall tile 7 13 flat 20\nfloor tile 7 14 flat 16\n"
         "tube drop 7 12 7 14 height 2\n", "not a landing on a FLOOR"),
        ("a DROP whose mouth does not fit its wall", W + "wall tile 7 13 flat 17\nfloor rect 6 14 9 17 flat 16\n"
         "tube drop 7 12 7 14 height 2\n", "not wholly on the face"),
        ("a windmill without its KEEP tube", _swap(W, "prop windmill 9 9", "prop windmill 8 10"),
         "without a KEEP tube"),
        ("a windmill entered along +y", W + "wall tile 7 13 flat 17\nfloor tile 7 14 flat 16\n"
         "floor tile 7 15 flat 16\ntube keep 7 12 7 14\nprop windmill 7 12\n", "entered along +y"),
        ("a windmill without a wall behind its doorway", W + "tube keep 10 12 10 11\nprop windmill 10 12\n",
         "without a wall behind its doorway"),
        ("a house that cannot hold the rotor", 'course P "p"\nwidth 64\nfloor rect 6 9 11 14 flat 16\n'
         'wall rect 7 8 12 9 flat 17\nfloor rect 7 5 12 8 flat 16.5\ntube keep 9 9 9 7\nprop windmill 9 9\n'
         'start 9 12\n', "cannot hold its rotor"),
        ("a doorway in the shade", W + "wall tile 11 10 flat 30\n", "is in the shade"),
        ("a bumper off a FLOOR", W + "prop bumper 3 3\n", "not a FLOOR"),
        ("a bumper with a seed", W + "prop bumper 7 11 seed 3\n", "takes no seed"),
        ("a period not a power of two", _swap(W, "prop windmill 9 9", "prop windmill 9 9 period 48"),
         "not a power of two"),
        ("a closed window off the pose boundaries", _swap(W, "prop windmill 9 9", "prop windmill 9 9 closed 20 40"),
         "not on pose boundaries"),
        ("a 17th prop", big + _posts([_sa(s_, a) for s_ in (30, 36, 42, 48) for a in (-6, -2, 2, 6)] +
                                     [_sa(54, 0)]), "17th prop"),
        ("a lift's rim at a third height", P + "floor tile 10 7 flat 2.5\n", "at its two docks"),
        ("a lift's rims not L apart", _swap(P, "prop platform 10 8 3", "prop platform 10 8 2"), "at its two docks"),
        ("a lift's shaft not VOID", P + "floor tile 10 8 flat 4\n", "is not VOID"),
        ("a lift's v over 192", _swap(P, "prop platform 10 8 3", "prop platform 10 8 3 period 64"),
         "over %d" % PL_VMAX),
        ("a lift hidden by a higher rim in front", _swap(P, "floor rect 6 6 10 10 flat 4\nfloor rect 11 7 13 10 "
         "flat 1", "floor rect 6 6 10 10 flat 1\nfloor rect 11 7 13 10 flat 4"), "overlaps pixel"),
        ("a reserved statement (edge)", W + "edge tile 4 4\n", "reserved for a later wave"),
        ("a reserved statement (checkpoint)", W + "checkpoint 4 4\n", "reserved for a later wave"),
        ("a reserved statement (pad)", W + "pad 4 4\n", "reserved for a later wave"),
        ("a reserved statement (shape)", W + "shape 4 4\n", "reserved for a later wave"),
        ("two lanes sharing blocks", big + _posts([(20, 18), (21, 19)]), "two lanes share blocks"),
        ("bound: a 7th lane in a window", seven, "lanes meet the"),
        ("bound: a 9th lane in the walk's range", nine, "lanes in the walk's range"),
        ("bound: three rotor changes on one step", _W3H % (0, 0, 0), "rotor pose changes"),
        ("bound: three rotor changes in two consecutive steps", _W3H % (0, 0, 1), "rotor pose changes"),
        ("bound: a windmill and a track in one window", W + "floor tile 12 12 flat 13\nprop platform 11 12 3\n",
         "a platform's track and a windmill's rotor"),
        ("bound: two lifts in a course", P + "floor tile 6 11 flat 1\nprop platform 6 10 3\n",
         "a second lift"),
        ("bound: a lane meeting the slab", P + "prop bumper 9 8\n", "meets the platform's sprite"),
        ("bound: a start window with no free calibration corner", _corner_case(), "no calibration corner"),
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
# =============================================================================
# wave 3's --selfcheck (SPEC.md 128.12.13.1): the props' items on any course
# that has them, and MILL's physics and route
# =============================================================================

def _lane_of(c, rec):
    pi = c.order[rec["i"]]
    return next(L for L in c.lanes if L["prop"] == pi)


def _pose_pic(c, L, q):
    """the picture with lane L at pose q (rows copied only where it differs)"""
    bx, by, w, h = L["rect"]
    pic = list(c.pic)
    for y, row in enumerate(L["pics"][q]):
        r = bytearray(pic[8 * by + y])
        r[8 * bx:8 * bx + len(row)] = row
        pic[8 * by + y] = r
    return pic


def _lanes_decode(c, part, herc):
    """every pose of every lane, from its pose map words in the part: -> the
    first (record, pose) that does not decode to the renderer's pose, or None"""
    for rec in c.part["props"]:
        L = rec["lane"]
        if not L:
            continue
        lane = _lane_of(c, rec)
        bx, by, w, h = lane["rect"]
        for q in range(L["poses"]):
            words = struct.unpack_from("<%dH" % (w * h), part, L["off"] + 2 * q * w * h)
            reg = lane["pics"][q]
            for k, off in enumerate(words):
                r, cc = divmod(k, w)
                for yy in range(8):
                    pix = reg[8 * r + yy][8 * cc:8 * cc + 8]
                    got = part[off + 2 * yy:off + 2 * yy + 2]
                    want = herc_bytes(pix, line=8 * (by + r) + yy, col0=8 * (bx + cc)) if herc else cga_bytes(pix)
                    if bytes(got) != bytes(want):
                        return rec["i"], q
    return None


def _slab_decode(c, part, herc):
    """the platform's sprite, both parity copies, mask and frame -> ok?"""
    for rec in c.part["props"]:
        if rec["kind"] != PK_PLATFORM:
            continue
        rb = PL_W // 4
        for cp in range(2):
            base = rec["spoff"] + cp * 2 * rb * PL_H
            for y in range(PL_H):
                row = [c.slab.get((x, y)) for x in range(PL_W)]
                m = part[base + rb * y:base + rb * y + rb]
                f = part[base + rb * PL_H + rb * y:base + rb * PL_H + rb * y + rb]
                if bytes(m) != cga_bytes([3 if v is None else 0 for v in row]):
                    return False
                px = [0 if v is None else v for v in row]
                want = herc_bytes(px, line=cp + y, col0=0) if herc else cga_bytes(px)
                if bytes(f) != bytes(want):
                    return False
    return True


def _composite_pose(c, L, q, px, py, sb, zb, air, via):
    """composite() with lane L at pose q: 'records' lays the records cut from
    pose 0 through the map (now pose q's); 'pixels' rules each pixel by pose
    q's own (s, top) - its overrides, else the picture's"""
    pic = _pose_pic(c, L, q)
    st = L["st"].get(q, {})
    m = 0 if air else CLIMB
    x4 = px & ~3
    out = {}
    for y in range(py, py + FOOT_H):
        for x in range(x4, x4 + FOOT_W):
            out[(x, y)] = pic[y][x]
    for pp, col in ball_pixels(px, py).items():
        out[pp] = col
    if via == "records":
        for br in range(py >> 3, ((py + FOOT_H - 1) >> 3) + 1):
            for bc in range(x4 >> 3, ((x4 + FOOT_W - 1) >> 3) + 1):
                for r in c.by_block.get((br, bc), ()):
                    if sb < r["s"] and zb + m < r["top"]:
                        for (x, y) in r["pix"]:
                            if (x, y) in out:
                                out[(x, y)] = pic[y][x]
    else:
        for (x, y) in list(out):
            s_, t_ = st.get((x, y), (c.sbuf[y][x], c.tbuf[y][x]))
            if s_ == -32768:
                continue
            if (x, y) not in st:
                t_ = c._raised.get((x, y), t_)
            if sb < s_ and zb + m < t_:
                out[(x, y)] = pic[y][x]
    return out


def _props_course_checks(c, res, tag):
    """items 3 - 6 for a course with props"""
    t0 = __import__("time").time()
    info = c.part
    # 3. every pose, both cards; every pose map word a block (read_part); the slab; the marks
    bad_c, bad_h = _lanes_decode(c, c.cga, False), _lanes_decode(c, c.herc, True)
    slab_ok = _slab_decode(c, c.cga, False) and _slab_decode(c, c.herc, True)
    marks = True
    for pr in c.props:
        if pr["kind"] == PK_TUBE:
            for cell, hole in ((pr["inn"], True), (pr["out"], False)):
                t = c.tiles[cell]
                x = 16 * (cell[0] - cell[1]) + c.x0
                y = 8 * (cell[0] + cell[1]) + 8 - (_h4t(t, 8, 8) >> 2) + c.y0
                ink = c.pic[y][x]
                marks = marks and ((ink == BLK) == hole)
    npose = sum(len(L["poses"]) for L in c.lanes)
    res.append(("3 %s: every pose of its %d lanes (%d poses) decodes from its pose map to the picture rendered in "
                "that pose, on the CGA and through the Hercules translation; the platform's sprite, both parity "
                "copies, decodes to the slab on both cards; each plain tube's IN is a hole and its OUT is not"
                % (tag, len(c.lanes), npose), bad_c is None and bad_h is None and slab_ok and marks))
    if c.lanes:
        rec = next(r for r in info["props"] if r["lane"])
        L = rec["lane"]
        b = bytearray(c.cga)
        o = L["off"] + 2 * L["w"] * L["h"]               # pose 1's first word
        w0 = struct.unpack_from("<H", b, o)[0]
        struct.pack_into("<H", b, o, w0 + 16 if w0 + 16 < info["occidx"] else w0 - 16)
        res.append(("3 %s negative control: one pose map word moved fails the decode" % tag,
                    _lanes_decode(c, bytes(b), False) is not None))
    # 4. OBS exactly on the props' cells; the window's scan names the right prop; the track's kill; the seeds
    g = Grid(c.cga)
    obs_ok = True
    for r in range(g.nrows):
        sR = g.smin + r
        for kk in range(g.kw):
            aC = g.amin + 2 * kk + (sR & 1)
            cell = ((sR + aC) >> 1, (sR - aC) >> 1)
            if bool(g.cell(*cell)[4] & FL_OBS) != (cell in c.pcell):
                obs_ok = False
    p = Physics(c)
    scan_ok = all(p.owner(cell) is not None and c.order[p.owner(cell)["i"]] == pi for cell, pi in c.pcell.items())
    kill_ok = all(g.cell(*t)[3] == KIND_VOID and g.cell(*t)[0] == pr["h2"] - 6 and not g.cell(*t)[4] & FL_SAFE
                  for pr in c.props if pr["kind"] == PK_PLATFORM for t in pr["track"])
    nwm = [pr for pr in c.props if pr["kind"] == PK_WINDMILL]
    seeds_ok = True
    for i, pr in enumerate(sorted(nwm, key=lambda q: q["wline"])):
        pl = 1 << pr["shift"]
        want = (i * (pr["mask"] + 1) // len(nwm)) // pl * pl + i * pl // len(nwm)
        if not pr.get("seed_given") and pr["seed"] != want:
            seeds_ok = False
    wins = 0
    for cell in sorted(c.pcell):                        # every window holding the cell lists it, rightly
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = Physics(c)
                q._fill(cell[0] - dx, cell[1] - dy)
                wins += 1
                k = 3 * (dy + 1) + dx + 1
                if (k, next(i for i, pi in enumerate(c.order) if pi == c.pcell[cell])) not in q.wol:
                    scan_ok = False
    res.append(("4 %s: OBS exactly on the props' %d cells, bits 4 - 7 zero (read_part); bz_wol's scan names the "
                "owning record in all %d windows that hold one; every track cell NEAR with its kill 3 units under "
                "the slab and never SAFE; the windmills' seeds as 128.12.3.4 derives them (%s)" % (
                    tag, len(c.pcell), wins, ", ".join("%d%s" % (pr["seed"], " given" if pr.get("seed_given")
                                                                         else "") for pr in nwm)),
                obs_ok and scan_ok and kill_ok and seeds_ok))
    # 5. every pose's composite through the records equals its own per-pixel composite
    c._raised = getattr(c, "_raised", None) or _raised_tops(c)
    tried = mism = 0
    for L in c.lanes:
        bx, by, w, h = L["rect"]
        rx = (8 * bx, 8 * by, 8 * (bx + w), 8 * (by + h))
        for rc in c.reach:
            xl, xh = foot_x(rc, c.x0)
            if not (xl <= rx[2] and rx[0] <= xh):
                continue
            gx, gy = (16 * rc.wx + 8) << 8, (16 * rc.wy + 8) << 8
            for z in sorted({rc.zlo, rc.zhi}):
                px = ((gx - gy) >> 8) + c.x0 - 8
                py = (((gx + gy) >> 1) >> 8) - z + c.y0 - 13
                if not _meet((px & ~3, py, (px & ~3) + FOOT_W, py + FOOT_H), *rx):
                    continue
                for air in ((1,) if rc.kind == KIND_VOID else (0, 1)):
                    for q in L["poses"]:
                        tried += 1
                        if _composite_pose(c, L, q, px, py, rc.s, z, air, "records") != \
                                _composite_pose(c, L, q, px, py, rc.s, z, air, "pixels"):
                            mism += 1
    nsl = sum(8 * pr["L"] + 1 for pr in c.props if pr["kind"] == PK_PLATFORM)
    res.append(("5 %s: over EVERY POSE, the ball through the records cut from pose 0 equals that pose's per-pixel "
                "composite at every reachable cell centre whose footprint meets a lane, lowest and highest, both air "
                "states (%d composites, %d differ); the slab clear of every pixel in front of it that rises above "
                "it at all %d heights of its rise" % (tag, tried, mism, nsl), mism == 0))
    _mouth_checks(c, res, tag)
    # 6. the bounds, printed
    b = c.bounds
    for herc in (0, 1):
        print("    %s, %s: the most lanes meeting a window %d (bound %d), in the walk's range %d (bound %d); the worst "
              "rotor coincidence %d on a step, %d in two (bound %d); the calibration corner %s" % (
                  tag, "Hercules" if herc else "CGA", b[herc]["lanes"], WIN_LANES, b[herc]["range"], RANGE_LANES,
                  b[herc]["worst"][0], b[herc]["worst"][1], ROTOR_CHG, b[herc]["corner"]))
    for rec in info["props"]:
        pr = c.props[c.order[rec["i"]]]
        what = "%-8s at (%d, %d), line %d" % (PK_NAMES[rec["kind"]], rec["at"][0], rec["at"][1], pr["line"])
        if rec["kind"] in (PK_TUBE, PK_WINDMILL):
            ex = c.exits.get(rec["i"], {})
            what += ": %s, %d segment%s, T %d steps; exits %s" % (
                TK_NAMES[rec["sub"]].upper(), len(rec["segs"]), "s" if len(rec["segs"]) > 1 else "", rec["T"],
                "; ".join("%s %s" % (MAT_NAMES[m], ex[m][0] + (" at %s" % (ex[m][1],) if ex[m][1] else ""))
                          for m in sorted(ex)))
            if rec["kind"] == PK_WINDMILL:
                what += "; P %d, seed %d, closed %d - %d" % (rec["mask"] + 1, rec["seed"], rec["closed"][0],
                                                            rec["closed"][1])
        elif rec["kind"] == PK_BUMPER:
            what += ": K %d, KA %d" % (rec["K"], rec["KA"])
        else:
            what += ": a LIFT, L %d, P %d, dwell %d, v %d, its top %d - %d px, seed %d" % (
                rec["L"], rec["mask"] + 1, rec["W"], rec["v"], rec["hP"], rec["hT"], rec["seed"])
        if rec["lane"]:
            Ln = rec["lane"]
            what += "; lane %d x %d at (row %d, column %d), %d poses" % (Ln["w"], Ln["h"], Ln["brow"], Ln["col"],
                                                                         Ln["poses"])
        print("    %s prop %d: %s" % (tag, rec["i"], what))
    print("    %s: identity %04Xh; %d prop records, %d pose-map bytes, %d segment bytes, %d sprite bytes; the "
          "picture's blocks %d and the lanes' %d more (%.1f s)" % (
              tag, c.ident, len(info["props"]), sum(2 * L["poses"] * L["w"] * L["h"] for L in
                                                    (r["lane"] for r in info["props"]) if L),
              SEGREC * sum(len(r.get("segs", ())) for r in info["props"]),
              PL_SPR * sum(1 for r in info["props"] if r["kind"] == PK_PLATFORM), c.nblk_pic - 0,
              len(c.blocks) - c.nblk_pic, __import__("time").time() - t0))


def _mouth_checks(c, res, tag):
    """the owner's preview, items 1, 3 and 4, as picture facts: (a) every
    tube that leaves through a wall face the viewer sees has its EXIT MOUTH
    drawn there - a DROP's, and a windmill's through its house - every pixel
    of it on the glass in the course picture; (b) the ball at the exit, as the
    model leaves it, stands IN that mouth: its contact line within 2 lines of
    the sill's line plus the half cell in front of the face (4 lines) and its
    columns meeting the arch's; (c) a tube's body wall standing on a lower
    tier is ONE column: its face over the void reaches as deep as its other
    front face at their shared corner.  Each with its negative control: the
    DROP's mouth drawn on the floor (the preview's), and the body drawn
    without the deep faces (the preview's), fail (b) and (c)"""
    pic = c.pic
    nm, bad, worst = 0, [], 0
    for p in c.props:
        if p["kind"] not in (PK_TUBE, PK_WINDMILL):
            continue
        mo = mouth_of(p, c.x0)
        visible = p["dir"] in (0, 2) and p["body"] and p["body"][-1] == (p["out"][0] - DIR_VEC[p["dir"]][0],
                                                                         p["out"][1] - DIR_VEC[p["dir"]][1])
        if p["kind"] == PK_WINDMILL and visible and mo is None:
            bad.append("the windmill on line %d leaves by a face with no mouth" % p["wline"])
        if mo is None:
            continue
        nm += 1
        pix = p.get("mouth_pix") or {}
        if not pix or any(pic[y + c.y0][x] != BLK for (x, y) in pix):
            bad.append("the tube on line %d: its mouth is not on the glass" % p["line"])
            continue
        rec = next(r for r in c.part["props"] if r["at"] == p["at"])
        q = Physics(c).poke(*p["out"])                  # the exit's own state, before any step
        if rec["sub"] == TK_DROP:
            q.gz = rec["segs"][-1]["ez"] << 8
        q._derive(True)

        def stands(pix_, q=q):
            sill = max(y for (_x, y) in pix_) + c.y0
            contact = q.py + 13
            cols = {x for (x, _y) in pix_}
            return abs(contact - (sill + 4)) <= 2 and any(q.px <= x < q.px + 16 for x in cols), contact - sill - 4
        ok, off = stands(pix)
        worst = max(worst, abs(off))
        if not ok:
            bad.append("the tube on line %d: the ball leaves %+d lines off its mouth" % (p["line"], off))
        if rec["sub"] == TK_DROP:                       # the preview's: the mouth on the floor line
            w, face, xm, rows, half, sill = mo
            ops = draw_ops(c.tiles, c.x0, {cl for pp in c.props if pp["kind"] == PK_TUBE for cl in pp["body"]})
            low, _l, _w = _arch(_op_spans(ops, w, face), xm, rows, half, 0)
            if stands(low)[0]:
                bad.append("negative control: the DROP's mouth on the floor line still passes (b)")
    # (c) the body walls' columns
    deep = {cl for pp in c.props if pp["kind"] == PK_TUBE for cl in pp["body"]}
    ncol, cbad = 0, []

    def column(ops, cell, void_sw):
        sw, se = _op_spans(ops, cell, "sw"), _op_spans(ops, cell, "se")
        if sw is None or se is None:
            return True
        bx = 16 * (cell[0] - cell[1]) + c.x0             # the shared corner B's column
        low = lambda sp, x: max((y for y, runs in sp.items() if _inside(runs, x)), default=None)
        a, b = low(sw, bx - 1), low(se, bx)
        if a is None or b is None:
            return True
        return (a >= b - 1) if void_sw else (b >= a - 1)     # the void face no shallower: no bite
    ops_deep = draw_ops(c.tiles, c.x0, deep)
    ops_flat = draw_ops(c.tiles, c.x0)
    nctl = 0
    for cell in sorted(deep):
        sw_n, se_n = c.tiles.get((cell[0], cell[1] + 1)), c.tiles.get((cell[0] + 1, cell[1]))
        if (sw_n is None) == (se_n is None):
            continue                                    # both faces over the void, or neither
        ncol += 1
        if not column(ops_deep, cell, sw_n is None):
            cbad.append(cell)
        if not column(ops_flat, cell, sw_n is None):
            nctl += 1
    res.append(("3 %s: the exit MOUTHS (the owner's preview) - %d tube%s leaving by a face the viewer sees, each "
                "mouth wholly on the glass and the ball at the exit standing in it (worst %d lines off), the "
                "windmill's through its house included; %d body wall%s on a lower tier drawn as one column%s; "
                "the preview's mouth-on-the-floor and bitten column fail it (%d bitten without the rule)" % (
                    tag, nm, "s" if nm != 1 else "", worst, ncol, "s" if ncol != 1 else "",
                    (": " + "; ".join(bad + ["%s bitten" % (cb,) for cb in cbad])) if bad or cbad else "", nctl),
                not bad and not cbad and (ncol == 0 or nctl > 0)))


def _mill_rec(c, kind, at=None):
    return next(r for r in c.part["props"] if r["kind"] == kind and (at is None or r["at"] == at))


def _gate_run(c, W, n0, keys, start, v, **kw):
    """a ball driven at a windmill's doorway from step n0: -> (what, closed at
    that step, the event, gvy after)"""
    p = Physics(c, **kw).poke(*start, gvx=v[0], gvy=v[1])
    p.lvl = [LVL_MAX if keys & b else 0 for b in (K_L, K_R, K_U, K_D)]
    p.nstep = n0
    for _ in range(80):
        n = p.nstep
        m0 = len(p.events)
        p.step(keys)
        ev = [e for e in p.events[m0:] if e[0] in ("knock", "capture")]
        if ev:
            ph = (n + W["seed"]) & W["mask"]
            return ev[0][0], W["closed"][0] <= ph < W["closed"][1], ev[0], p.gvy
    return None, None, None, None


def _gate_sweep(c, W, **kw):
    out = []
    for n0 in range(W["mask"] + 1):
        out.append(_gate_run(c, W, n0, K_U | K_R, (W["at"][0], W["at"][1] + 2), (0, -VMAXG), **kw))
    ok = all(r[0] and (r[0] == "knock") == r[1] and (r[0] != "knock" or r[3] == (E_GATE * VMAXG) >> 8)
             for r in out)
    return ok, sum(1 for r in out if r[0] == "knock")


_POST1 = 'course K "k"\nwidth 64\nfloor rect 6 6 16 16 flat 0\nstart 7 7\nprop bumper 11 11\n'
_POST2 = 'course K "k"\nwidth 64\nfloor rect 6 6 16 16 flat 0\nstart 7 7\nprop bumper 10 10\nprop bumper 11 10\n'
_DIR8 = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


def _kick_sweep(**kw):
    """every approach (8 directions, offsets at 1/2 gu, speeds 16 - 384) at a
    lone post: -> (kicks, the worst shortfall of the normal speed under t
    where no axis is clamped, below the rail's rebound, double contacts,
    the least distance from the post at a kick step's end)"""
    c = compile_course(_POST1, "<a post>", occluders=False)
    rec = c.part["props"][0]
    cx, cy = rec["cx"], rec["cy"]
    nk = short = below = double = over = 0
    mind = 99.0
    for dx, dy in _DIR8:
        Ln = math.hypot(dx, dy)
        ux, uy = dx / Ln, dy / Ln
        for b2 in range(-22, 23):
            bb = b2 / 2.0
            for sp in (16, 64, 128, 192, 256, 320, VMAXG):
                p = Physics(c, **kw).poke(11, 11)
                p.gx = int((cx - 20 * ux - bb * uy) * 256)
                p.gy = int((cy - 20 * uy + bb * ux) * 256)
                p.gvx, p.gvy = sp * dx, sp * dy
                p._fill(p.gx >> 12, p.gy >> 12)
                p._derive(True)
                for _ in range(80):
                    m0 = len(p.events)
                    p.step(0)
                    ks = [e for e in p.events[m0:] if e[0] == "kick"]
                    if not ks:
                        continue
                    nk += 1
                    _, _, _, d, t, nx, ny = ks[0]
                    dn = (p.gvx * nx + p.gvy * ny) >> 6
                    if abs(p.gvx) < VMAXG and abs(p.gvy) < VMAXG:
                        short = max(short, t - dn)
                        # |n| is the table's rounding of 64: the change t - d
                        # lands short by at most that share, and two floors
                        allow = -(-(t - d) * max(0, 4096 - nx * nx - ny * ny) // 4096) + 2
                        over += t - dn > allow
                        if d < 0 and dn < (E_BUMPER * -d) >> 8:
                            below += 1
                    mind = min(mind, math.hypot(p.gx / 256.0 - cx, p.gy / 256.0 - cy))
                    m1 = len(p.events)
                    p.step(0)
                    double += sum(1 for e in p.events[m1:] if e[0] == "kick")
                    break
    return nk, short, below, double, mind, over


def _plat_at(c, P, n0, off=(8, 8), **kw):
    """a ball resting on the LIFT's slab at step n0, at `off` gu into its shaft"""
    p = Physics(c, **kw)
    A = P["at"]
    p.gx, p.gy = (16 * A[0] + off[0]) << 8, (16 * A[1] + off[1]) << 8
    p.gz, p.air = (P["hP"] << 8) + plat_pos(P, n0 & 0xFFFF), 0
    p.gvx = p.gvy = p.gvz = 0
    p.onp = P["i"] + 1
    p.nstep = n0
    p._fill(p.gx >> 12, p.gy >> 12)
    p._ps()
    p._derive(True)
    return p


def _plat_rim(c, P, z):
    """the lift's rim at height z px: its cell and the keys that roll the ball
    from it into the shaft (the opposite keys roll the ball out to it)"""
    A = P["at"]
    keys = {(-1, 0): K_R | K_D, (1, 0): K_L | K_U, (0, -1): K_L | K_D, (0, 1): K_R | K_U}
    for (dx, dy), k in keys.items():
        t = c.tiles.get((A[0] + dx, A[1] + dy))
        if t is not None and t.kind == KIND_FLOOR and 4 * t.z0 == z:
            return (A[0] + dx, A[1] + dy), k
    raise CourseError("the lift has no rim at %d px" % z)


def _plat_runs(c, **kw):
    """SPEC.md 128.12.6.4's checks, on MILL's lift"""
    P = _mill_rec(c, PK_PLATFORM)
    per = P["mask"] + 1
    n_dep = next(n for n in range(per) if plat_pos(P, n) == 0 and plat_pos(P, n + 1) > 0)
    n_arr = next(n for n in range(n_dep, n_dep + per) if plat_pos(P, n) == P["pmax"])
    n_low = next(n for n in range(n_arr, n_arr + per) if plat_pos(P, n) == 0)    # it docks LOW again
    hi_rim, hi_in = _plat_rim(c, P, P["hT"])
    lo_rim, lo_in = _plat_rim(c, P, P["hP"])
    out_keys = {K_R | K_D: K_L | K_U, K_L | K_U: K_R | K_D, K_L | K_D: K_R | K_U, K_R | K_U: K_L | K_D}
    out = {}
    # the RIDE, low dock to high: carried PMAX in z, never along x or y, and no
    # SPIN on the way (the roll frame is the ground line's, which the carry
    # never moves: the owner's preview), then off onto the high rim
    p = _plat_at(c, P, n_dep - 4, **kw)
    g0 = (p.gx, p.gy, p.gz)
    turn = lambda q: (sprite(q, 0), sprite(q, 1)[0], sprite(q, 1)[1] & ~8)   # the Hercules's PHY bit 0
    f0 = turn(p)                                                            # is py's parity (128.11.9.2)
    spin = 0
    for _ in range(n_arr - n_dep + 8):
        p.step(0)
        spin += turn(p) != f0
    carried = (p.gx - g0[0], p.gy - g0[1], p.gz - g0[2])
    for _ in range(60):
        p.step(out_keys[hi_in])
    tl = c.tiles.get((p.gx >> 12, p.gy >> 12))
    out["ride"] = carried == (0, 0, P["pmax"]) and not p.air and not p.nfall \
        and tl is not None and tl.kind == KIND_FLOOR and 4 * tl.z0 == P["hT"]
    out["spin"] = spin == 0
    hops, flights = [], []
    for at in (n_arr + 20, n_dep + 20, n_arr - 8):      # docked, mid-rise, and spanning the dock's stop
        q = _plat_at(c, P, at, **kw)
        t = None
        for k in range(60):
            q.step(K_HOP if k == 0 else 0)
            if t is None and _ev(q, "hop") and (_ev(q, "bounce") or _ev(q, "land")):
                t = k
        flights.append(t)
        hops.append(bool(_ev(q, "hop")) and not q.nfall and q.onp == P["i"] + 1 and not q.air)
    out["hop"] = all(hops)
    # the carry makes a flight RELATIVE to the slab: a Hop on the rising slab
    # comes down on it after as many steps as one on the docked slab
    out["hoprel"] = flights[0] is not None and flights[1] == flights[0]
    # DROPPED ONTO THE SLAB at its LOWEST and at its HIGHEST (the owner's
    # preview: a ball rolled off the high rim into the shaft lands on the slab
    # wherever it is - a lift, not a moat), and mid-rise
    lands = []
    q = Physics(c, **kw).poke(*hi_rim)                  # off the high rim's edge at 1/4 gu a step
    ux, uy = (P["at"][0] - hi_rim[0], P["at"][1] - hi_rim[1])
    q.gx, q.gy = q.gx + ((9 * ux) << 8), q.gy + ((9 * uy) << 8)
    q.gvx, q.gvy = 64 * ux, 64 * uy
    q.nstep = n_low + 2
    q._fill(q.gx >> 12, q.gy >> 12)
    q._derive(True)
    for n0 in (n_arr + 4, n_dep + 30):                  # dropped 16 px onto it at its highest, and mid-rise
        r = _plat_at(c, P, n0, **kw)
        r.gz += 16 << 8
        r.air, r.ztop, r.onp = 1, r.gz >> 8, 0
        lands.append(r)
    lands.insert(0, q)
    ok = []
    for q in lands:
        on = False
        for _ in range(40):
            q.step(0)
            on = on or (q.onp == P["i"] + 1 and bool(_ev(q, "bounce") or _ev(q, "land")))
        ok.append(on and not q.nfall)
    out["land"] = all(ok)
    # rolling off its open side falls, and is killed
    side = next(k for k in (K_L | K_D, K_R | K_U, K_R | K_D, K_L | K_U)
                if (P["at"][0] + (1 if k == K_R | K_D else -1 if k == K_L | K_U else 0),
                    P["at"][1] + (1 if k == K_L | K_D else -1 if k == K_R | K_U else 0)) not in c.tiles)
    q = _plat_at(c, P, n_dep + 30, **kw)
    for _ in range(120):
        q.step(side)
    out["off"] = q.nfall == 1
    # the low rim into the shaft while the slab is up: under it, never lifted, falls
    q = Physics(c, **kw).poke(*lo_rim)
    q.nstep = n_arr + 2
    lifted = False
    for _ in range(80):
        q.step(lo_in)
        lifted = lifted or bool(q.onp)
    out["under"] = q.nfall == 1 and not lifted
    # waiting on the low rim, the ball boards as the slab docks
    q = Physics(c, **kw).poke(*lo_rim)
    q.nstep = n_low
    boarded = False
    for _ in range(60):
        q.step(lo_in)
        boarded = boarded or bool(q.onp)
    out["board"] = boarded and not q.nfall
    return out


def _props_physics(c, res):
    """item 7's wave-3 runs on MILL, and their negative controls"""
    W = _mill_rec(c, PK_WINDMILL, (9, 9))
    ok, nk = _gate_sweep(c, W)
    res.append(("7 MILL gate: from every phase of the windmill at (9, 9) a ball held at the doorway at the cap is "
                "knocked back exactly when its gate is closed at the step its circle first touches it, at "
                "(160 x 384) >> 8 = %d, and captured otherwise (%d knocks of %d)" % (
                    (E_GATE * VMAXG) >> 8, nk, W["mask"] + 1), ok))
    side = [_gate_run(c, W, n0, K_R, (W["at"][0] - 1, W["at"][1]), (200, -32)) for n0 in range(W["mask"] + 1)]
    res.append(("7 MILL side: rolled along the house front into the doorway, from every phase, captured exactly when "
                "the gate is open at its first touch (O31)", all(r[0] and (r[0] == "capture") != r[1] for r in side)))
    res.append(("7 negative control: the gate judged one step late fails the gate run",
                not _gate_sweep(c, W, _gate_late=True)[0]))
    # transit and exits, every tube of MILL, the ghost checked step by step
    tr_ok = True
    tinfo = []
    for rec in c.part["props"]:
        if rec["kind"] not in (PK_TUBE, PK_WINDMILL):
            continue
        p = Physics(c)
        p.poke(*rec["at"])
        if rec["kind"] == PK_WINDMILL:
            p.nstep = next(n for n in range(256) if not (rec["closed"][0] <= (n + rec["seed"]) & rec["mask"]
                                                       < rec["closed"][1]))
        p._capture(rec, p.nstep & 0xFFFF)
        p._end()
        hidden = 0
        ends = []
        bx, by = p.bx, p.by
        seg, left = 0, rec["segs"][0]["m"]
        while p.tube:
            p.step(0)
            hidden += 1
            if abs(p.bx - bx) > 768 or abs(p.by - by) > 768:
                tr_ok = False
            bx, by = p.bx, p.by
            left -= 1
            if not left:
                sg = rec["segs"][seg]
                ends.append((p.gx, p.gy, p.gz) == (sg["ex"] << 8, sg["ey"] << 8, sg["ez"] << 8)
                            or rec["sub"] == TK_LAUNCH and seg == len(rec["segs"]) - 1)
                seg += 1
                left = rec["segs"][seg]["m"] if seg < len(rec["segs"]) else 0
        tr_ok = tr_ok and hidden == rec["T"] and all(ends)
        tinfo.append("%s T %d" % (TK_NAMES[rec["sub"]], rec["T"]))
    res.append(("7 MILL transit: every tube's ghost is hidden exactly T steps (%s), on each segment's end exactly, "
                "within 3 px and 3 lines a step" % ", ".join(tinfo), tr_ok))

    def keep_exit(vin, **kw):
        p = Physics(c, **kw).poke(W["at"][0], W["at"][1] + 1, gvx=0, gvy=-vin)
        p.nstep = next(n for n in range(64) if not (W["closed"][0] <= (n + W["seed"]) & W["mask"] < W["closed"][1])
                       and not (W["closed"][0] <= (n + 1 + W["seed"]) & W["mask"] < W["closed"][1]))
        p.gy = ((16 * W["at"][1] + RAD) << 8) + 16
        for _ in range(200):
            p.step(0)
            e = _ev(p, "exit")
            if e:
                return e[0][4], p.tsin
        return None, None
    kx = [keep_exit(v) for v in (8, 40, 200)]
    want = [((max(t, TMIN) * DIR_VEC[W["dir"]][0], max(t, TMIN) * DIR_VEC[W["dir"]][1], 0)) for _, t in kx]
    res.append(("7 MILL exits: KEEP leaves along its mouth (%s) at max(s_in, 64) (s_in %s -> %s); LAUNCH and DROP "
                "land every ball on a FLOOR (item 6's lines, the compile's check)" % (
                    DIR_NAMES[W["dir"]], [t for _, t in kx], [v for v, _ in kx]),
                all(v == w for (v, _), w in zip(kx, want)) and all(t is not None for _, t in kx)))
    res.append(("7 negative control: KEEP's exit along the entry velocity fails the exit run",
                keep_exit(200, _exit_vel=True)[0] != want[2]))
    # the kick
    t0 = __import__("time").time()
    nk, short, below, double, mind, over = _kick_sweep()
    print("    the kick sweep (%.1f s): %d kicks; the normal speed out at least t less %d (the table's |n| rounds 64 by "
          "up to 1.4%%); %d past that rounding; %d below the rail's rebound; %d second contacts; the centre at a "
          "kick step's end at least %.2f gu from the post" % (__import__("time").time() - t0, nk, short, over, below,
                                                              double, mind))
    res.append(("7 kick: a sweep of approaches (8 directions, offsets at 1/2 gu, speeds 16 - 384) leaves along the "
                "normal at least t = max(K, rail + KA) but for the unit normal's rounding (%d short at worst, none "
                "past it), never below the rail's rebound, and never touches the post again on the next step (the "
                "push leaves the centre %.2f gu out at least)" % (short, mind), nk > 0 and not over and not below
                and not double))
    nkr = _kick_sweep(_kick_k=True)
    res.append(("7 negative control: the kick's floor at K alone (t = max(K, d)) fails the kick run (%d short of "
                "the rail's floor)" % nkr[2], nkr[2] > 0 or nkr[5] > 0))
    c2 = compile_course(_POST2, "<two posts>", occluders=False)
    p = Physics(c2).poke(10, 10)
    p.gx, p.gy = (176 << 8), (172 << 8)
    p._fill(11, 10)
    p.step(0)
    kicked = {e[2] for e in _ev(p, "kick")}
    res.append(("7 cluster: a ball between two posts touching both is kicked by each in one step (%s)"
                % sorted(kicked), kicked == {0, 1}))
    c1 = compile_course(_POST1, "<a post>", occluders=False)
    rec = c1.part["props"][0]
    p = Physics(c1).poke(11, 11)
    p.gz = (rec["ph"] + 16) << 8
    p.air, p.ztop = 1, p.gz >> 8
    for _ in range(200):
        p.step(0)
    top_ok = not p.air and p.gz == rec["ph"] << 8 and not _ev(p, "kick")
    p = Physics(c1).poke(11, 11)
    p.gx += 9 << 8
    p.gz = (rec["ph"] + 16) << 8
    p.air, p.ztop = 1, p.gz >> 8
    p._fill(p.gx >> 12, p.gy >> 12)
    for _ in range(80):
        p.step(0)
    res.append(("7 post: a ball dropped on a post's top rests there, one dropped beside it is kicked",
                top_ok and bool(_ev(p, "kick"))))
    pr = _plat_runs(c)
    res.append(("7 lift: carried PMAX up a traverse, never along x or y, and off onto its high rim (%s) with no spin "
                "on the way (%s); a Hop on the moving slab lands back on it and one spanning the dock's stop too "
                "(%s); a ball rolled off the high rim into the shaft lands on the slab at its LOWEST, and one dropped "
                "on it at its highest and mid-rise lands too (%s); rolling off its open side falls (%s); a ball "
                "entering under it is not lifted (%s); boarding at the low dock (%s)" % (
                    pr["ride"], pr["spin"], pr["hop"], pr["land"], pr["off"], pr["under"], pr["board"]),
                all(pr.values())))
    res.append(("7 lift: a Hop on the RISING slab comes down on it after as many steps as one on the docked slab "
                "(the carry: a flight relative to the slab)", pr["hoprel"]))
    res.append(("7 negative control: the carry left out fails the lift's Hop", not _plat_runs(c, _no_carry=True)["hoprel"]))
    res.append(("7 negative control: the carry along +s (wave 3's first design) SPINS the ball riding it (the owner's "
                "preview)", not _plat_runs(c, _carry_s=True)["spin"]))
    res.append(("7 negative control: the carry cleared at a take-off fails the Hop run",
                not _plat_runs(c, _stick=True)["hoprel"]))
    # 128.11.5.3's proof with LAUNCH exits as crossing sources: a LAUNCH is a
    # crossing open to every ball, so a rubber-only gap must not have one
    launch = [r for r in c.part["props"] if r["kind"] == PK_TUBE and r["sub"] == TK_LAUNCH]
    res.append(("7 every LAUNCH exit a crossing source (128.11.5.3): MILL's %d land every ball on a FLOOR, so none "
                "bypasses a rubber-only gap (MILL has none; TRIAL has no LAUNCH)" % len(launch),
                all(c.exits[r["i"]][m][0] in ("land", "bounce", "stun", "shatter") for r in launch for m in range(3))))


def _mill_route(c, res):
    """item 8: MILL's route by the autopilot, and GLIDE on it"""
    out = []
    for steps in (CGA_STEPS, HERC_STEPS):
        p = Physics(c, play=True)
        fl = []                         # airborne OCC steps from each exit to its first contact
        after = 0
        flying = None
        for _ in range(steps):
            m0 = len(p.events)
            p.step_auto()
            for e in p.events[m0:]:
                if e[0] == "exit" and e[3] in ("launch", "drop"):
                    flying = e[3]
                elif e[0] in ("land", "bounce", "stun", "shatter", "hopc", "respawn"):
                    flying = None
            cl = p.cell(p.gx >> 12, p.gy >> 12)
            if p.air and not p.tube and cl[4] & FL_OCC:
                if flying:
                    fl.append((flying, p.nstep))
                else:
                    after += 1
        out.append((p, fl, after))
    p, fl, after = out[0]
    caps = [e[2] for e in _ev(p, "capture")]
    kinds = {}
    for rec in c.part["props"]:
        kinds[rec["i"]] = (rec["kind"], rec.get("sub"))
    seen_w = any(kinds[i][0] == PK_WINDMILL for i in caps)
    seen_d = any(kinds[i] == (PK_TUBE, TK_DROP) for i in caps)
    seen_l = any(kinds[i] == (PK_TUBE, TK_LAUNCH) for i in caps)
    goal = _ev(p, "goal")
    res.append(("8 MILL: the autopilot rolls the rubber ball into the windmill (step %s), over the green (%d kicks), "
                "down the chute and through the cannon to the goal (step %s) with no fall in the CGA's %d steps or "
                "the Hercules's %d; the LAUNCH's flight and the DROP's fall cross no OCC cell (%d airborne OCC "
                "steps from an exit to its first contact; %d later, bouncing on)" % (
                    _ev(p, "capture")[0][1] if caps else "-", len(_ev(p, "kick")), goal[0][1] if goal else "-",
                    CGA_STEPS, HERC_STEPS, len(fl), after),
                seen_w and seen_d and seen_l and bool(goal) and p.nfall == 0 and out[1][0].nfall == 0
                and not fl and bool(_ev(p, "kick"))))
    # GLIDE on MILL: the transit pans, and the lanes shown and their commits
    for herc in (0, 1):
        stats = {"tf": 0, "tbad": 0, "shown": 0, "frames": 0, "chg": 0}
        last = {}
        posts = {}                                  # bumper -> ([drawn a frame], [kick frames])

        def cb(p, g, dr, dc, st=stats, last=last, herc=herc, posts=posts):
            st["frames"] += 1
            for r in p.props:
                if r["kind"] == PK_BUMPER:
                    dl, kl = posts.setdefault(r["i"], ([], [], [p.pkick[r["i"]]]))[:2]
                    seen = posts[r["i"]][2]
                    if p.pkick[r["i"]] != seen[0]:
                        seen[0] = p.pkick[r["i"]]
                        kl.append(st["frames"] - 1)
                    dl.append(g.heavy.drawn.get(r["i"], 0))
            if p.tube:
                st["tf"] += 1
                if (g.want_r and not dr) or (g.want_c and not dc):
                    st["tbad"] += 1
            W, rl = g.W, g.rl
            ya, xa = g.R0 * rl, 8 * g.c0
            for r in p.props:
                L = r["lane"]
                if not L or not _meet((8 * L["col"], 8 * L["brow"], 8 * (L["col"] + L["w"]), 8 * (L["brow"] + L["h"])),
                                      xa, ya, xa + 8 * W, ya + WIN_LINES):
                    continue
                st["shown"] += 1
                q = ((((p.nstep - 1) & 0xFFFF) + r["seed"]) & r["mask"]) >> r["shift"] \
                    if r["kind"] == PK_WINDMILL else g.heavy.drawn.get(r["i"], 0)
                if last.get(r["i"], q) != q:
                    st["chg"] += 1
                last[r["i"]] = q
        dirs, gp = glide_run(c, herc, heavy=True, frame_cb=cb)
        g = gp.glide
        print("    MILL under GLIDE with the heavy rule, %s: %d frames, %.2f lanes shown a frame, %d pose changes "
              "while shown (the commits the route needs); %d transit frames; heavy frames %d (level 1 %d, level 2 "
              "%d), rows withheld %d, columns %d, edge releases %d; contact groups %d (must-draw rotors %d, "
              "platform boxes %d, platform waits %d, promoted wheel lanes %d), deferred lanes %d" % (
                  "Hercules" if herc else "CGA", stats["frames"], stats["shown"] / float(stats["frames"]),
                  stats["chg"], stats["tf"], g.nhvy, g.heavy.levels[1], g.heavy.levels[2], g.nwr, g.nwc, g.nhedge,
                  g.heavy.ncon, g.heavy.nmust, g.heavy.npbx, g.heavy.npwt, g.heavy.npro, g.heavy.ndef))
        res.append(("8 MILL, %s: GLIDE (heavy rule on) pans on every transit frame that has a row or a column "
                    "outstanding (%d transit frames)" % ("Hercules" if herc else "CGA", stats["tf"]),
                    stats["tf"] > 0 and stats["tbad"] == 0))
        # the owner's preview: a kicked post shows LIT, at once and for PLITF frames on the glass
        nk, worst_lag, worst_run = 0, 0, None
        for i, (dl, kl, _s) in posts.items():
            for fk in kl:
                nk += 1
                f1 = next((f for f in range(fk, len(dl)) if dl[f] == 1), None)
                if f1 is None:
                    worst_lag = 99
                    continue
                f2 = next((f for f in range(f1, len(dl)) if dl[f] != 1), len(dl))
                worst_lag = max(worst_lag, f1 - fk)
                worst_run = f2 - f1 if worst_run is None else min(worst_run, f2 - f1)
        res.append(("8 MILL, %s: every kick (%d on the route) shows its post LIT on the kick's frame (worst %d "
                    "late) and for at least %d frames on the glass (shortest %s) - a lighting post is MUST-DRAW "
                    "and its lit time counts frames shown, not steps (the owner's preview)" % (
                        "Hercules" if herc else "CGA", nk, worst_lag, PLITF, worst_run),
                    nk > 0 and worst_lag == 0 and worst_run is not None and worst_run >= PLITF))


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
            out.append((p, occ, lays, air_occ, occg, pl))
        p, occ, lays, air_occ, occg, pl = out[0]
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
                "least 5 times on both cards at step rates 0.96 - 1.04 (ten phases each; fewest %d), the heavy rule "
                "OFF (128.12.7: BENCH's route is frozen)" % min(mins.values()), min(mins.values()) >= 5))
    for herc in (0, 1):                     # ...and reported with it on
        d, gp = glide_run(bench, herc, 1.0, 0.0, heavy=True)
        g = gp.glide
        print("    GLIDE on BENCH with the heavy rule, %s, rate 1.00: %s; heavy frames %d (level 1 %d, level 2 %d), "
              "rows withheld %d, columns withheld %d, frames releasing an axis %d" % (
                  "Hercules" if herc else "CGA", " ".join("%s %d" % (n, d.get(k, 0)) for n, k in zip(
                      ("UL", "U", "UR", "L", "R", "DL", "D", "DR"), DIRS)), g.nhvy, g.heavy.levels[1],
                  g.heavy.levels[2], g.nwr, g.nwc, g.nhedge))


W2_COMMIT = "848ade16"          # wave 2's tree (SPEC.md 128.12.9)


def wave2_parts(names):
    """the wave-2 parts of the named courses, compiled by 848ade16's own
    tool out of git in a temporary tree: -> ({NAME: bytes}, None) or (None,
    why it cannot be had)"""
    import subprocess
    import tempfile
    import tarfile
    try:
        r = subprocess.run(["git", "cat-file", "-e", W2_COMMIT + "^{commit}"], cwd=ROOT, capture_output=True)
        if r.returncode:
            return None, "commit %s is not in this clone (a shallow one? `git fetch --unshallow`)" % W2_COMMIT
        with tempfile.TemporaryDirectory() as td:
            tar = os.path.join(td, "w.tar")
            r = subprocess.run(["git", "archive", "-o", tar, W2_COMMIT, "tools/bbcourse.py", "tools/bonanza_assets.py",
                                "apps/bonanza/courses"], cwd=ROOT, capture_output=True)
            if r.returncode:
                return None, "git archive of %s failed" % W2_COMMIT
            w = os.path.join(td, "w")
            with tarfile.open(tar) as tf:
                if hasattr(tarfile, "data_filter"):
                    tf.extractall(w, filter="data")
                else:
                    tf.extractall(w)
            paths = [os.path.join(w, "apps", "bonanza", "courses", n.lower() + ".bbc") for n in names]
            r = subprocess.run([sys.executable, os.path.join(w, "tools", "bbcourse.py"), "-o",
                                os.path.join(td, "art")] + paths, cwd=w, capture_output=True)
            if r.returncode:
                return None, "848ade16's tool failed: %s" % r.stderr.decode(errors="replace")[-200:]
            return {n: open(os.path.join(td, "art", "BZ%d.BIN" % k), "rb").read() for k, n in enumerate(names)}, None
    except OSError as e:
        return None, "git is not to be had (%s)" % e


def selfcheck(paths=None):
    paths = paths or default_paths()
    res = []
    skipped = []
    # 1. determinism
    a = compile_all(paths)
    b = compile_all(paths)
    same = all(a[1][k] == b[1][k] for k in a[1]) and a[2] == b[2] and sorted(a[1]) == sorted(b[1])
    res.append(("1 two compiles byte-identical, file for file (%s, bzcourse.inc)" % ", ".join(sorted(a[1])), same))
    courses = a[0]
    byname = {c.name: c for c in courses}
    for k, c in enumerate(courses):
        report(c, k)
    idok = all(struct.unpack_from("<H", c.cga, c.part["gridoff"] + 18)[0] == part_identity(c.cga, c.part["gridoff"])
               for c in courses)
    res.append(("1 every course's identity at BZG1 +18 is 128.12.8's checksum of its part's words, that word taken as 0 "
                "(%s)" % ", ".join("%s %04Xh" % (c.name, c.ident) for c in courses), idok))
    if "MILL" in byname:                    # the negative control: two windmills' seeds exchanged
        src = open(byname["MILL"].fname if os.path.isabs(byname["MILL"].fname)
                   else os.path.join(ROOT, byname["MILL"].fname)).read()
        swp = src.replace("prop windmill 9 9  seed 16", "prop windmill 9 9  seed 36").replace(
            "prop windmill 7 9\n", "prop windmill 7 9  seed 16\n")
        try:
            cs = [compile_course(t, "<MILL, %s>" % n, occluders=False) for t, n in ((src, "as is"), (swp, "seeds swapped"))]
            def _plain(c):
                b = bytearray(c.cga)
                b[c.part["gridoff"] + 18:c.part["gridoff"] + 20] = b"\0\0"
                return sum(struct.unpack_from("<%dH" % (len(b) // 2), b, 0)) & 0xFFFF
            sums = [_plain(c) for c in cs]
            res.append(("1 negative control: MILL with its two windmills' seeds exchanged has another identity "
                        "(%04Xh against %04Xh; a plain sum of the words would %s)" % (
                            cs[1].ident, cs[0].ident, "not" if sums[0] == sums[1] else "too"),
                        swp != src and cs[0].ident != cs[1].ident))
        except CourseError as e:
            res.append(("1 negative control: MILL with its seeds exchanged compiles (%s)" % e, False))
    w2names = [n for n in ("BENCH", "FIRST", "TRIAL") if n in byname]
    if w2names:
        old, why = wave2_parts(w2names)
        if old is None:
            skipped.append("1 SKIPPED: %s, %s and %s against wave 2's parts: %s" % (tuple(w2names) + (why,)))
        else:
            diff = []
            for n in w2names:
                x, y = bytearray(byname[n].cga), bytearray(old[n])
                g = byname[n].part["gridoff"]
                for z in (x, y):
                    z[g + 18:g + 20] = b"\0\0"
                if x != y:
                    diff.append(n)
            res.append(("1 %s compile to wave 2's parts (%s's tool, run from git in a temporary tree) byte for byte "
                        "but the identity word%s" % (", ".join(w2names), W2_COMMIT,
                                                   "" if not diff else " -- DIFFER: %s" % diff), not diff))
    # 2. the grammar and the bounds
    for what, text, want in _grammar_cases():
        try:
            compile_course(text, fname="<%s>" % what)
            fired, msg = False, "compiled"
        except CourseError as e:
            fired, msg = want in str(e), str(e)
        res.append(("2 refused: %s%s" % (what, "" if fired else " -- got: " + msg), fired))
    for what, text, want in _wave3_cases():
        try:
            compile_course(text, fname="<%s>" % what)
            fired, msg = False, "compiled"
        except CourseError as e:
            fired, msg = want in str(e), str(e)
        res.append(("2 refused (wave 3): %s%s" % (what, "" if fired else " -- got: " + msg), fired))
    for c in courses:
        if c.part["nprop"]:
            bb = bytearray(c.cga)
            bb[c.part["propoff"] + 1] |= PF_UNDER
            struct.pack_into("<H", bb, c.part["gridoff"] + 18, part_identity(bb, c.part["gridoff"]))
            try:
                read_part(bytes(bb))
                fired = False
            except CourseError as e:
                fired = "UNDERSIDE" in str(e)
            res.append(("2 refused: %s's first record with the UNDERSIDE flag (the reader's own check)" % c.name, fired))
            break
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
            safe = (tl.kind == KIND_FLOOR and tl.sx == 0 and tl.sy == 0 and (wx, wy) not in c.pcell
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
                if (wx, wy) in c.slabcells:
                    want = (c.slabcells[(wx, wy)][0] >> 2) - 6
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
        if c.props:
            _props_course_checks(c, res, tag)
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
    if "MILL" in byname:
        _props_physics(byname["MILL"], res)
    if "BENCH" in byname:
        _route_checks(byname["BENCH"], res, byname.get("TRIAL"), byname.get("FIRST"))
    if "MILL" in byname:
        _mill_route(byname["MILL"], res)
    try:                                      # item 5's negative control: a blade in front of the doorway
        compile_course(open(byname["MILL"].fname if os.path.isabs(byname["MILL"].fname)
                            else os.path.join(ROOT, byname["MILL"].fname)).read(), "<MILL, rotor in front>",
                       _hack={"rotor_front": True})
        caught = False
    except CourseError as e:
        caught = "depend on its pose" in str(e)
    except KeyError:
        caught = None
    if caught is not None:
        res.append(("5 MILL negative control: a rotor whose blades are drawn IN FRONT of the doorway (a moving part "
                    "before the ball in one pose and not another) is REFUSED by the pose check", caught))
    ok = True
    for what, good in res:
        print("  %-4s %s" % ("ok" if good else "FAIL", what))
        ok = ok and good
    for what in skipped:
        print("  SKIP %s" % what)
    print("bbcourse selfcheck: %s" % ("ok" if ok and not skipped else "FAILED" if not ok else
                                      "ok, but %d item%s SKIPPED (exit 77)" % (len(skipped), "s" if len(skipped) > 1
                                                                               else "")))
    return 1 if not ok else 77 if skipped else 0


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
        m = re.search(r"^BZ_COURSES\s*:=\s*((?:.*\\\n)*.+)$", f.read(), re.M)
    if not m:
        raise SystemExit("bbcourse: the Makefile has no BZ_COURSES line")
    return [os.path.join(ROOT, p) for p in m.group(1).replace("\\", " ").split()]


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
