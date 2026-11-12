#!/usr/bin/env python3
"""BONANZA (Bounce Bonanza) asset generator, wave 0 (SPEC.md 128.3).

    python3 tools/bonanza_assets.py -o build/bonanza-art     # what `make` runs
    python3 tools/bonanza_assets.py --selfcheck              # invariants + determinism
    python3 tools/bonanza_assets.py --png DIR                # previews (needs Pillow)

Generates the wave-0 TEST COURSE and the phase-torus BALL from code alone:
no ROM, no reference game, no input file, no environment variable.  Python
standard library only (Pillow is used by --png and nothing else, behind a
try/except) and deterministic: the same tool gives byte-identical outputs,
no timestamps, sorted iteration, integer geometry.

Outputs, in the -o directory (the four PARTS of BONANZA.O88, then NASM):
    BZCRSC.BIN    the course, CGA: header, block MAP, deduplicated 8x8 BLOCKS
    BZCRSH.BIN    the course, Hercules: the same map, blocks in pair pixels
    BZBALC.BIN    the ball, CGA: masks, then 4 shifts x 64 frames
    BZBALH.BIN    the ball, Hercules: the same layout in pair pixels
    bzconst.inc   dimensions, part sizes and offsets, the start point and the
                  autopilot's waypoints (all derived from the course)
    .bz-art       stamp: sha256 of this tool (make's rebuild key), written FIRST

Course part (SPEC.md 128.3):
    +0 'BZC0'  +4 word BZ_COLS (64)  +6 word BZ_BROWS (200)  +8 word N (<= 1024)
    +10 word offset of the blocks  +12 four reserved bytes (0)
    +16 the map: BZ_COLS x BZ_BROWS words, row-major, block number x 16
    then N blocks of 16 bytes: 8 lines of one word, left byte first.
    Block 0 is all black.  CGA: 8 pixels at 2 bits, MSB first.  Hercules: 8
    game pixels as 16 card bits: 0 -> 00, 3 -> 11, 1 and 2 -> the mid level,
    10 where (line + column) is even and 01 where it is odd (SPEC.md 102.7.1).

Ball part:
    +0 'BZB0'  +4 word frames (64)  +6 word shifts (4)  +8 word rows (16)
    +10 word bytes a row (5)  +12 four reserved bytes (0)
    +16 masks: 4 x 16 x 5 bytes, shift-major; a SET bit keeps the background
    then frames: 4 x 64 x 16 x 5 bytes (shift, frame, row), ANDed with ~mask.
    Shift s = the ball moved s game pixels right in its 20-pixel row.
    Frame f = (py & 7) * 8 + (px & 7).  Hercules ball pixels: 0 -> 00,
    3 -> 11, 1 and 2 -> 10 (a ball lands on any line, so no checkerboard).

Host reference for the test rows (import this module):
    course_indices()        the 512 x 1600 picture, a tuple of 1600 bytes rows
    ball_frame_indices(f)   16 rows of 16 entries, an index or None (clear)
    cga_bytes(pixels)       pack indices 4 a byte, MSB first
    herc_bytes(pixels, line=None, col0=0)
                            pack as Hercules pairs; line=None is the ball's
                            rule, a line number is the course's checkerboard
    waypoints()             the autopilot's route, ball top-left world pixels
"""
import argparse
import functools
import hashlib
import math
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.abspath(__file__)

# --- the picture -------------------------------------------------------------
WPX, WPY = 512, 1600          # world pixels (SPEC.md 128.3)
COLS = WPX // 8               # 64 word columns: a CGA word is 8 pixels
BROWS = WPY // 8              # 200 block rows
MAXBLK = 1024
CRS_MAX = 42000               # SPEC.md 128.7: the course part's ceiling
BLK, CYN, MAG, WHT = 0, 1, 2, 3   # CGA palette 1
CGA1 = [(0, 0, 0), (85, 255, 255), (255, 85, 255), (255, 255, 255)]

# --- the ball ----------------------------------------------------------------
P = 8                         # texture period: P*P = 64 frames
D = 16                        # diameter, game pixels
RB = 5                        # bytes a row: 16 px + up to 3 px of shift
SHIFTS = 4
NFRAMES = P * P
MARGIN = 16                   # SPEC.md 128.5: the ball stays this far inside

HDR = 16
MAPOFF = HDR
MAPSIZE = COLS * BROWS * 2
BLKOFF = MAPOFF + MAPSIZE
BAL_MASKOFF = HDR
BAL_MASKSIZE = SHIFTS * D * RB
BAL_FRMOFF = BAL_MASKOFF + BAL_MASKSIZE
BAL_FRMSIZE = SHIFTS * NFRAMES * D * RB
BAL_SIZE = BAL_FRMOFF + BAL_FRMSIZE


class AssetError(Exception):
    pass


# =============================================================================
# THE COURSE: an isometric heightfield of 32x16 diamond tiles
# =============================================================================
#
# World tile (wx, wy): +wx runs down-RIGHT on screen, +wy down-LEFT, z up.  A
# tile's corners are (wx, wy) top, (wx+1, wy) right, (wx+1, wy+1) bottom,
# (wx, wy+1) left.  A corner (cx, cy, z) is on screen at
#     x = (cx - cy) * 16 + X0,   y = (cx + cy) * 8 - 8 z + Y0
# so a tile is a 32 x 16 diamond and a height unit is 8 pixels (one block
# row).  Heights are quantised to HALF units (4 px): every corner lands on x a
# multiple of 16 and y a multiple of 4, which is what keeps the deduplicated
# block count small.  Each tile owns its four corner heights, so a step is a
# discontinuity between two tiles and a ramp is a run of tiles whose corners
# follow one function.
#
# Geometry is integer throughout: vertices are kept in quarter pixels (x4, y4)
# and a pixel is filled when its CENTRE is inside, half-open on both axes, so
# two polygons sharing an edge share no pixel and leave no gap.

X0 = 256
FACE_DEPTH8 = 24             # a face over the void hangs 3 units (24 px)
WALL8 = 16                   # walls and rails stand 2 units (16 px) proud


def _z8(z2):
    """half units -> pixels"""
    return z2 * 4


def _q2(num, den):
    """round num/den (a height in units) to half units, half up, integer only"""
    # floor(2 * num / den + 1/2) = floor((4 num + den) / (2 den))
    if den < 0:
        num, den = -num, -den
    return (4 * num + den) // (2 * den)


def flat(z):
    return lambda cx, cy: _q2(z, 1)


def rampx(x0, x1, z0, z1):
    """z runs from z0 at corner column x0 to z1 at x1 (linear, then quantised)"""
    return lambda cx, cy: _q2(z0 * (x1 - x0) + (z1 - z0) * (cx - x0), x1 - x0)


def rampy(y0, y1, z0, z1):
    return lambda cx, cy: _q2(z0 * (y1 - y0) + (z1 - z0) * (cy - y0), y1 - y0)


def ramps(s0, s1, z0, z1):
    """z runs along s = cx + cy: a slope that faces the viewer"""
    return lambda cx, cy: _q2(z0 * (s1 - s0) + (z1 - z0) * (cx + cy - s0), s1 - s0)


def offset(fn, dx=0, dy=0, add2=0):
    """fn evaluated at a neighbouring corner, plus add2 half units: a rail
    standing on the edge of a floor follows the floor's slope"""
    return lambda cx, cy: fn(cx + dx, cy + dy) + add2


def rect(x0, y0, x1, y1):
    return lambda wx, wy: x0 <= wx < x1 and y0 <= wy < y1


def band(a0, a1, s0, s1):
    """a screen-VERTICAL band: a = wx - wy in [a0, a1], s = wx + wy in [s0, s1)"""
    return lambda wx, wy: a0 <= wx - wy <= a1 and s0 <= wx + wy < s1


def course_layout():
    """-> (rooms, holes, waypoint tiles).  A room is (predicate over tiles,
    corner height function in half units, style); later rooms override
    earlier ones.  The route, top to bottom: a start plateau on the left, the
    LONG DIAGONAL DESCENT down-right with a rail behind it, a landing on the
    right, steps, the TRAVERSE LEFT across the whole width (pits, blocks),
    a CLIMB back down-right, a plateau, the SPRINT DOWN (a screen-vertical
    slope), and the finish."""
    rooms = []

    def room(pred, fn, style="floor"):
        rooms.append((pred, fn, style))

    # A. the start plateau
    room(rect(2, 13, 7, 17), flat(30))
    # B. the long diagonal descent, down-right, 30 -> 21 over 18 tiles
    descent = rampx(7, 25, 30, 21)
    room(rect(7, 13, 25, 17), descent)
    room(rect(7, 12, 25, 13), offset(descent, add2=4), "wall")        # back rail
    room(rect(2, 12, 7, 13), offset(flat(30), add2=4), "wall")
    # C. the landing on the right, one step below the descent's foot
    room(rect(25, 13, 29, 21), flat(20))
    room(rect(25, 12, 28, 13), flat(22), "wall")
    # D. steps down, along +wy
    for k in range(3):
        room(rect(25, 21 + 2 * k, 29, 23 + 2 * k), flat(19 - k))
    # E. the traverse left: along +wy right across the picture, gently down
    trav = rampy(27, 38, 17, 15)
    room(rect(25, 27, 29, 38), trav)
    room(rect(24, 21, 25, 38), offset(trav, dx=1, add2=4), "wall")    # back rail
    room(rect(25, 38, 30, 41), flat(15))                             # left end
    room(rect(27, 32, 28, 33), offset(trav, add2=4), "wall")          # blocks
    room(rect(26, 35, 27, 36), offset(trav, add2=4), "wall")
    # F. the climb: back down-right, rising 15 -> 20
    room(rect(30, 37, 40, 41), rampx(30, 40, 15, 20))
    # G. the plateau at the top of the climb
    room(rect(40, 36, 45, 42), flat(20))
    room(rect(40, 35, 45, 36), flat(22), "wall")
    # H. the sprint down: a screen-vertical band falling one unit a tile
    room(band(-1, 6, 86, 142), ramps(86, 142, 20, -8))
    # I. the finish: a wide plateau and a chequered line
    room(band(-8, 12, 142, 162), flat(-8))
    room(band(-8, 12, 152, 154), flat(-8), "goal")
    room(band(-9, -9, 142, 162), flat(-6), "wall")
    room(band(13, 13, 142, 162), flat(-6), "wall")

    holes = set()
    for t in ((12, 15), (13, 15), (12, 14), (18, 14), (21, 16),        # B
              (26, 29), (27, 29), (26, 30), (27, 30), (25, 34), (28, 34), (28, 35),  # E
              (34, 39), (35, 39)):                                       # F
        holes.add(t)
    # H: pits in the sprint, so the line down is not straight
    for (a, s) in ((4, 100), (5, 101), (0, 112), (1, 113), (5, 126), (-1, 135), (0, 136)):
        holes.add(((s + a) // 2, (s - a) // 2))

    # the route (tile, as the autopilot should see it), SPEC.md 128.6.  The
    # benchmark's 1,200 frames cover about its first 1,400 px (the ball tops out
    # near 1.3 px a frame at a 60 Hz display), so the legs that make the camera
    # step in EVERY direction come first: the long diagonal DESCENT (down-right),
    # the TRAVERSE LEFT across the steps to the climb's foot (down-left), the
    # RETURN UP to the landing (up-right) and on up to the start (up-left) - a
    # course drawn downhill only ever scrolls one way otherwise.  Then the climb
    # and the sprint down, for a longer run.  A host model of the autopilot and
    # the camera (written to choose these legs, not kept) put every one of the
    # eight step directions into the benchmark on both cards at 60/50, 40/33 and
    # 30/25 frames a second; the bonanzaring row is what checks it on the glass.
    route = [(4, 15), (10, 15), (16, 15), (22, 15), (30, 39), (28, 19), (4, 15),
             (33, 40), (38, 39), (42, 39),
             ((92 + 3) // 2, (92 - 3) // 2), ((118 + 2) // 2, (118 - 2) // 2),
             ((138 + 2) // 2, (138 - 2) // 2), ((156 + 2) // 2, (156 - 2) // 2)]
    return rooms, holes, route


def build_tiles():
    rooms, holes, route = course_layout()
    tiles = {}
    for wx in range(-40, 120):
        for wy in range(-40, 120):
            got = None
            for pred, fn, style in rooms:
                if pred(wx, wy):
                    got = (fn, style)
            if got is None or (wx, wy) in holes:
                continue
            fn, style = got
            z2 = (fn(wx, wy), fn(wx + 1, wy), fn(wx + 1, wy + 1), fn(wx, wy + 1))
            tiles[(wx, wy)] = (tuple(_z8(v) for v in z2), style)
    return tiles, route


def _scr(cx2, cy2, z8, y0):
    """corner in HALF tile units and pixel height -> quarter-pixel screen"""
    return ((cx2 - cy2) * 32 + 4 * X0, (cx2 + cy2) * 16 - 4 * z8 + 4 * y0)


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
            # first pixel whose centre 4px+2 >= nn/dd
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


class Canvas:
    def __init__(self):
        self.rows = [bytearray(WPX) for _ in range(WPY)]

    def put(self, x, y, c):
        if not (0 <= x < WPX and 0 <= y < WPY):
            raise AssetError("course pixel (%d, %d) outside the %dx%d picture" % (x, y, WPX, WPY))
        self.rows[y][x] = c

    def fill(self, sp, colour):
        """colour: an index, or a function (x, y) -> index"""
        for y, runs in sp.items():
            for a, b in runs:
                for x in range(a, b):
                    self.put(x, y, colour(x, y) if callable(colour) else colour)

    def outline(self, sp, left=False):
        """black on every pixel with no pixel of the same polygon above it
        (and, for a face, none to its left): one line on each top edge"""
        for y, runs in sp.items():
            above = sp.get(y - 1)
            for a, b in runs:
                for x in range(a, b):
                    if not _inside(above, x) or (left and x == a):
                        self.put(x, y, BLK)


def _render_course():
    tiles, route = build_tiles()
    # Y0: the highest pixel lands at y = 8, and Y0 stays a multiple of 8 so the
    # lattice stays block-aligned
    top = min((cx + cy) * 8 - z8
              for (wx, wy), (z8s, st) in tiles.items()
              for (cx, cy), z8 in zip(((wx, wy), (wx + 1, wy), (wx + 1, wy + 1), (wx, wy + 1)), z8s))
    top -= WALL8
    y0 = ((8 - top) + 7) // 8 * 8
    cv = Canvas()
    order = sorted(tiles, key=lambda t: (t[0] + t[1], t[0]))
    for (wx, wy) in order:
        (zt, zr, zb, zl), style = tiles[(wx, wy)]
        T = (2 * wx, 2 * wy)
        R = (2 * wx + 2, 2 * wy)
        B = (2 * wx + 2, 2 * wy + 2)
        L = (2 * wx, 2 * wy + 2)
        # the two faces the camera sees, each down to the lower neighbour or
        # FACE_DEPTH8 into the void
        sw = tiles.get((wx, wy + 1))        # its top/right corners are our left/bottom
        se = tiles.get((wx + 1, wy))        # its left/top corners are our bottom/right
        faces = (
            (L, zl, B, zb, (sw[0][0], sw[0][1]) if sw else None, lambda x, y: MAG),
            (B, zb, R, zr, (se[0][3], se[0][0]) if se else None,
             lambda x, y: MAG if (x + y) & 1 == 0 else BLK),
        )
        for p, zp, q, zq, nb, col in faces:
            if nb is None:
                lp, lq = zp - FACE_DEPTH8, zq - FACE_DEPTH8
            else:
                lp, lq = min(zp, nb[0]), min(zq, nb[1])
            if lp >= zp and lq >= zq:
                continue
            poly = [_scr(p[0], p[1], zp, y0), _scr(q[0], q[1], zq, y0),
                    _scr(q[0], q[1], lq, y0), _scr(p[0], p[1], lp, y0)]
            sp = spans(poly)
            cv.fill(sp, col)
            cv.outline(sp, left=True)
        quad = [_scr(T[0], T[1], zt, y0), _scr(R[0], R[1], zr, y0),
                _scr(B[0], B[1], zb, y0), _scr(L[0], L[1], zl, y0)]
        whole = spans(quad)
        if style == "wall":
            cv.fill(whole, WHT)
        elif style == "goal" or not (zt == zr == zb == zl):
            # a ramp (or the finish line) is a FINER checker, 2x2 a tile, so
            # the slope's foreshortening reads in four colours
            m = lambda a, b: (a + b) // 2
            mtr = ((T[0] + R[0]) // 2, (T[1] + R[1]) // 2, m(zt, zr))
            mrb = ((R[0] + B[0]) // 2, (R[1] + B[1]) // 2, m(zr, zb))
            mbl = ((B[0] + L[0]) // 2, (B[1] + L[1]) // 2, m(zb, zl))
            mlt = ((L[0] + T[0]) // 2, (L[1] + T[1]) // 2, m(zl, zt))
            c = (2 * wx + 1, 2 * wy + 1, (zt + zr + zb + zl) // 4)
            t, r, b, l = T + (zt,), R + (zr,), B + (zb,), L + (zl,)
            if style == "goal":
                inks = (WHT, BLK)
            else:
                inks = (CYN, WHT)
            for corners, k in (((t, mtr, c, mlt), 0), ((mtr, r, mrb, c), 1),
                               ((c, mrb, b, mbl), 0), ((mlt, c, mbl, l), 1)):
                cv.fill(spans([_scr(*v, y0) for v in corners]), inks[k])
        else:
            cv.fill(whole, WHT if (wx + wy) & 1 else CYN)
        cv.outline(whole)
    # the route, as the ball's top-left in world pixels: tile centre, ball
    # sitting on it
    way = []
    for (wx, wy) in route:
        if (wx, wy) not in tiles:
            raise AssetError("waypoint tile (%d, %d) is not on the course" % (wx, wy))
        z8s = tiles[(wx, wy)][0]
        x = (wx - wy) * 16 + X0
        y = (wx + wy + 1) * 8 - sum(z8s) // 4 + y0
        bx, by = x - D // 2, y - D + 3
        if not (MARGIN <= bx <= WPX - MARGIN - D and MARGIN <= by <= WPY - MARGIN - D):
            raise AssetError("waypoint (%d, %d) inside the %d px margin" % (bx, by, MARGIN))
        way.append((bx, by))
    return tuple(bytes(r) for r in cv.rows), tuple(way), y0


@functools.lru_cache(maxsize=1)
def _course_cached():
    return _render_course()


def course_indices():
    """the 512 x 1600 course picture: a tuple of 1600 bytes, one index a pixel"""
    return _course_cached()[0]


def waypoints():
    """the autopilot's route: (bx, by) ball top-left in world pixels"""
    return _course_cached()[1]


# =============================================================================
# THE BALL: the phase torus (docs/plans/BOUNCE-BONANZA-PLAN.md 4)
# =============================================================================
#
# Ported from docs/plans/bounce-bonanza/ballproto.py ('spots', base magenta,
# ink white): a 16 px disc samples an 8-periodic texture through
# u = R asin(x/R) - phase.  The phase is SUBTRACTED from the lookup (the
# prototype adds it): the face the camera sees is above the equator and moves
# WITH the ball, so the spots must travel the way the ball does.

R_ = D / 2.0
BAYER2 = [[0, 2], [3, 1]]
_LX, _LY, _LZ = -0.45, -0.55, 0.70
_LN = math.sqrt(_LX * _LX + _LY * _LY + _LZ * _LZ)
LIGHT = (_LX / _LN, _LY / _LN, _LZ / _LN)


def _spots(u, v):
    u %= P
    v %= P
    du, dv = u - P / 2 + 0.5, v - P / 2 + 0.5
    return du * du + dv * dv < 5.0


def _silhouette(px, py):
    x = (px + 0.5 - R_) / R_
    y = (py + 0.5 - R_) / R_
    return x * x + y * y <= 1.0


@functools.lru_cache(maxsize=None)
def _ball_frame(fx, fy):
    rows = []
    for py in range(D):
        row = []
        for px in range(D):
            x = (px + 0.5 - R_) / R_
            y = (py + 0.5 - R_) / R_
            rr = x * x + y * y
            if rr > 1.0:
                row.append(None)
                continue
            if rr > 0.80:                    # the 1 px dark rim
                row.append(BLK)
                continue
            z = math.sqrt(1.0 - rr)
            lam = x * LIGHT[0] + y * LIGHT[1] + z * LIGHT[2]
            rz = 2 * lam * z - LIGHT[2]
            u = R_ * math.asin(max(-1.0, min(1.0, x))) - fx
            v = R_ * math.asin(max(-1.0, min(1.0, y))) - fy
            c = WHT if _spots(u, v) else MAG
            if rz > 0.93:                     # the highlight
                c = WHT
            thr = (BAYER2[py & 1][px & 1] + 0.5) / 4.0
            if lam < 0.04 or (lam < 0.24 and (lam - 0.04) / 0.20 < thr):
                c = BLK                       # the terminator, ordered-dithered
            row.append(c)
        rows.append(tuple(row))
    return tuple(rows)


def ball_frame_indices(f):
    """frame f = (py & 7) * 8 + (px & 7): 16 rows of 16 entries, an index or
    None where the background shows"""
    return _ball_frame(f & 7, (f >> 3) & 7)


# =============================================================================
# encoders
# =============================================================================

def cga_bytes(pixels):
    """indices -> bytes, four pixels a byte, the leftmost in bits 7-6"""
    out = bytearray()
    for i in range(0, len(pixels), 4):
        v = 0
        for k in range(4):
            v = (v << 2) | (pixels[i + k] & 3)
        out.append(v)
    return bytes(out)


def herc_pair(c, line=None, col=0):
    """one game pixel -> its two card bits as a number 0..3 (left bit high)"""
    if c == BLK:
        return 0
    if c == WHT:
        return 3
    if line is None:
        return 2                               # the ball: always 10
    return 2 if (line + col) % 2 == 0 else 1   # the course: 10 / 01 checker


def herc_bytes(pixels, line=None, col0=0):
    """indices -> Hercules bytes, four game pixels (eight card pixels) a byte.
    line=None is the ball's rule; a line number is the course's, with col0
    the world column of pixels[0]"""
    out = bytearray()
    for i in range(0, len(pixels), 4):
        v = 0
        for k in range(4):
            v = (v << 2) | herc_pair(pixels[i + k], line, col0 + i + k)
        out.append(v)
    return bytes(out)


# =============================================================================
# the parts
# =============================================================================

def build_course_parts(pic):
    blocks = [bytes(64)]                      # block 0: all black, always
    index = {blocks[0]: 0}
    mp = []
    for by in range(BROWS):
        for bx in range(COLS):
            blk = bytes(pic[by * 8 + y][bx * 8 + x] for y in range(8) for x in range(8))
            n = index.get(blk)
            if n is None:
                n = index[blk] = len(blocks)
                blocks.append(blk)
            mp.append(n)
    nblk = len(blocks)
    if nblk > MAXBLK:
        raise AssetError("%d unique blocks: over the %d the map's words can name" % (nblk, MAXBLK))
    hdr = b"BZC0" + struct.pack("<HHHH", COLS, BROWS, nblk, BLKOFF) + bytes(4)
    mapb = b"".join(struct.pack("<H", n * 16) for n in mp)
    cga = bytearray(hdr + mapb)
    herc = bytearray(hdr + mapb)
    for blk in blocks:
        for y in range(8):
            line = blk[y * 8:y * 8 + 8]
            cga += cga_bytes(line)
            herc += herc_bytes(line, line=y, col0=0)
    for part in (cga, herc):
        if len(part) != BLKOFF + 16 * nblk or len(part) > CRS_MAX:
            raise AssetError("course part is %d bytes (ceiling %d)" % (len(part), CRS_MAX))
    return bytes(cga), bytes(herc), nblk


def _ball_row(frame_row, shift):
    """one ball row at a shift -> (20 indices or None) slots"""
    slots = [None] * (RB * 4)
    for x, c in enumerate(frame_row):
        slots[shift + x] = c
    return slots


def build_ball_part(herc):
    hdr = b"BZB0" + struct.pack("<HHHH", NFRAMES, SHIFTS, D, RB) + bytes(4)
    masks = bytearray()
    frames = bytearray()
    sil = ball_frame_indices(0)
    for s in range(SHIFTS):
        for row in sil:
            slots = _ball_row(row, s)
            masks += cga_bytes([3 if c is None else 0 for c in slots])
    enc = (lambda px: herc_bytes(px)) if herc else cga_bytes
    for s in range(SHIFTS):
        for f in range(NFRAMES):
            for row in ball_frame_indices(f):
                slots = _ball_row(row, s)
                frames += enc([0 if c is None else c for c in slots])
    out = bytes(hdr + masks + frames)
    if len(out) != BAL_SIZE:
        raise AssetError("ball part is %d bytes, not %d" % (len(out), BAL_SIZE))
    return out


def _paras(n):
    return (n + 15) // 16


def emit_const(nblk, crs_len, way, y0):
    lines = [
        "; bzconst.inc - GENERATED by tools/bonanza_assets.py (SPEC.md 128.3).",
        "; Do not edit: change the tool and rebuild.  Everything here derives",
        "; from the generated course and ball, so a course change re-sizes the",
        "; package rather than breaking it.",
        "",
        "BZ_WPX          equ %d       ; the course picture, world pixels" % WPX,
        "BZ_WPY          equ %d" % WPY,
        "BZ_COLS         equ %d        ; word columns (8 px a word)" % COLS,
        "BZ_BROWS        equ %d       ; block rows (8 lines a block)" % BROWS,
        "BZ_NBLK         equ %d       ; unique 8x8 blocks (block 0 is black)" % nblk,
        "BZ_MAXBLK       equ %d" % MAXBLK,
        "",
        "; the course part (BZCRSC.BIN / BZCRSH.BIN): identical layout and size",
        "BZ_CRS_MAPOFF   equ %d        ; the map: BZ_COLS x BZ_BROWS words, block x 16" % MAPOFF,
        "BZ_CRS_ROWB     equ %d       ; bytes of map a block row" % (COLS * 2),
        "BZ_CRS_BLKOFF   equ %d    ; the blocks: 16 bytes each, 8 line words" % BLKOFF,
        "BZ_CRS_SIZE     equ %d" % crs_len,
        "BZ_CRS_PARAS    equ %d" % _paras(crs_len),
        "",
        "; the ball part (BZBALC.BIN / BZBALH.BIN): identical layout and size",
        "BZ_BAL_FRAMES   equ %d" % NFRAMES,
        "BZ_BAL_SHIFTS   equ %d" % SHIFTS,
        "BZ_BAL_ROWS     equ %d" % D,
        "BZ_BAL_RB       equ %d         ; bytes a row" % RB,
        "BZ_BAL_D        equ %d        ; the ball's diameter, game pixels" % D,
        "BZ_BAL_MASKOFF  equ %d        ; masks: shift x row x byte, SET keeps" % BAL_MASKOFF,
        "BZ_BAL_MASKSH   equ %d        ; bytes of mask a shift" % (D * RB),
        "BZ_BAL_FRMOFF   equ %d       ; frames: shift x frame x row x byte" % BAL_FRMOFF,
        "BZ_BAL_FRMB     equ %d        ; bytes a frame" % (D * RB),
        "BZ_BAL_FRMSH    equ %d      ; bytes of frames a shift" % (NFRAMES * D * RB),
        "BZ_BAL_SIZE     equ %d" % BAL_SIZE,
        "BZ_BAL_PARAS    equ %d" % _paras(BAL_SIZE),
        "",
        "; the ball's room and route (SPEC.md 128.5, 128.6): world pixels of the",
        "; ball's 16x16 box's top-left corner",
        "BZ_MARGIN       equ %d" % MARGIN,
        "BZ_BXMIN        equ %d" % MARGIN,
        "BZ_BXMAX        equ %d" % (WPX - MARGIN - D),
        "BZ_BYMIN        equ %d" % MARGIN,
        "BZ_BYMAX        equ %d" % (WPY - MARGIN - D),
        "BZ_START_X      equ %d" % way[0][0],
        "BZ_START_Y      equ %d" % way[0][1],
        "BZ_NWAY         equ %d        ; waypoints in BZ_WAYTAB, the start first" % len(way),
        "; BZ_WAYTAB emits BZ_NWAY pairs `dw x, y`: the long diagonal descent",
        "; (down-right), the traverse left (down-left), the return up (up-right,",
        "; then up-left to the start), the climb, the sprint down",
        "%macro BZ_WAYTAB 0",
    ]
    for x, y in way:
        lines.append("    dw %d, %d" % (x, y))
    lines += ["%endmacro", "", "BZ_Y0           equ %d       ; the course's iso origin row (host geometry)" % y0, ""]
    return "\n".join(lines)


def compile_all():
    pic, way, y0 = _render_course()
    crsc, crsh, nblk = build_course_parts(pic)
    balc = build_ball_part(False)
    balh = build_ball_part(True)
    files = {"BZCRSC.BIN": crsc, "BZCRSH.BIN": crsh, "BZBALC.BIN": balc, "BZBALH.BIN": balh}
    texts = {"bzconst.inc": emit_const(nblk, len(crsc), way, y0)}
    return files, texts, nblk


def stamp():
    h = hashlib.sha256()
    h.update(b"tools/bonanza_assets.py\0")
    with open(TOOL, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def write_out(out):
    os.makedirs(out, exist_ok=True)
    files, texts, nblk = compile_all()
    # the stamp goes FIRST: make's outputs depend on it, so a run that dies
    # part-way leaves an up-to-date stamp and missing outputs, which make's
    # fallback recipe turns back into a re-run that shows the error
    with open(os.path.join(out, ".bz-art"), "w") as f:
        f.write(stamp() + "\n")
    for name in sorted(files):
        with open(os.path.join(out, name), "wb") as f:
            f.write(files[name])
    for name in sorted(texts):
        with open(os.path.join(out, name), "w", newline="\n") as f:
            f.write(texts[name])
    return files, nblk


# =============================================================================
# --selfcheck
# =============================================================================

def _decode_course(part, herc):
    """an independent reader: map + blocks -> the picture, or the Hercules
    card bits as 2-bit pairs a game pixel"""
    if part[:4] != b"BZC0":
        raise AssetError("course magic")
    cols, brows, nblk, blkoff = struct.unpack_from("<HHHH", part, 4)
    if (cols, brows, blkoff) != (COLS, BROWS, BLKOFF) or part[12:16] != bytes(4):
        raise AssetError("course header")
    if len(part) != blkoff + 16 * nblk:
        raise AssetError("course length")
    rows = [bytearray(WPX) for _ in range(WPY)]
    for by in range(brows):
        for bx in range(cols):
            off = struct.unpack_from("<H", part, MAPOFF + 2 * (by * cols + bx))[0]
            if off % 16 or off // 16 >= nblk:
                raise AssetError("map word %d at (%d, %d) is not a block offset" % (off, bx, by))
            for y in range(8):
                w = part[blkoff + off + 2 * y:blkoff + off + 2 * y + 2]
                for x in range(8):
                    v = (w[x >> 2] >> (6 - 2 * (x & 3))) & 3
                    rows[by * 8 + y][bx * 8 + x] = v
    return rows, nblk


def _check_ball(part, herc, results):
    name = "BZBALH" if herc else "BZBALC"
    hdr = struct.unpack_from("<HHHH", part, 4)
    results.append(("%s header (magic, 64 frames, 4 shifts, 16 rows, 5 bytes)" % name,
                    part[:4] == b"BZB0" and hdr == (NFRAMES, SHIFTS, D, RB)
                    and part[12:16] == bytes(4) and len(part) == BAL_SIZE))
    masks = part[BAL_MASKOFF:BAL_FRMOFF]
    frames = part[BAL_FRMOFF:]
    ok_pairs = all(((b >> k) & 3) in (0, 3) for b in masks for k in (0, 2, 4, 6))
    results.append(("%s mask pixels are 00 (ball) or 11 (keep)" % name, ok_pairs))
    under = 0
    for s in range(SHIFTS):
        for f in range(NFRAMES):
            for r in range(D):
                for k in range(RB):
                    m = masks[(s * D + r) * RB + k]
                    v = frames[((s * NFRAMES + f) * D + r) * RB + k]
                    under += bin(v & m).count("1")
    results.append(("%s frame bits only where the mask is clear (%d stray)" % (name, under), under == 0))
    # the silhouette is the disc, and shift s is shift 0 moved s pixels right
    shifted = True
    for s in range(SHIFTS):
        for r in range(D):
            want = cga_bytes([3 if c is None else 0 for c in _ball_row(ball_frame_indices(0)[r], s)])
            if masks[(s * D + r) * RB:(s * D + r + 1) * RB] != want:
                shifted = False
            for f in (0, 9, 63):
                row = [0 if c is None else c for c in _ball_row(ball_frame_indices(f)[r], s)]
                enc = herc_bytes(row) if herc else cga_bytes(row)
                got = frames[((s * NFRAMES + f) * D + r) * RB:((s * NFRAMES + f) * D + r + 1) * RB]
                if got != enc:
                    shifted = False
    results.append(("%s shifts are the ball moved 0..3 px right; %s pixel rule" %
                    (name, "Hercules 10" if herc else "CGA 2-bit"), shifted))


def selfcheck():
    results = []
    a_files, a_texts, nblk = compile_all()
    _course_cached.cache_clear()
    _ball_frame.cache_clear()
    b_files, b_texts, _ = compile_all()
    same = all(a_files[k] == b_files[k] for k in a_files) and a_texts == b_texts
    results.append(("two runs byte-identical (%s, bzconst.inc)" % ", ".join(sorted(a_files)), same))

    crsc, crsh = a_files["BZCRSC.BIN"], a_files["BZCRSH.BIN"]
    print("  blocks: %d unique of %d cells (ceiling %d)" % (nblk, COLS * BROWS, MAXBLK))
    print("  BZCRSC.BIN %d  BZCRSH.BIN %d  (ceiling %d)" % (len(crsc), len(crsh), CRS_MAX))
    print("  BZBALC.BIN %d  BZBALH.BIN %d" % (len(a_files["BZBALC.BIN"]), len(a_files["BZBALH.BIN"])))
    results.append(("block count %d <= %d" % (nblk, MAXBLK), nblk <= MAXBLK))
    results.append(("course parts <= %d bytes and the same length" % CRS_MAX,
                    len(crsc) == len(crsh) <= CRS_MAX))
    results.append(("course parts share header and map", crsc[:BLKOFF] == crsh[:BLKOFF]))
    results.append(("block 0 is black on both cards",
                    crsc[BLKOFF:BLKOFF + 16] == bytes(16) and crsh[BLKOFF:BLKOFF + 16] == bytes(16)))
    pic = course_indices()
    try:
        dec, _ = _decode_course(crsc, False)
        ok = all(bytes(dec[y]) == pic[y] for y in range(WPY))
    except AssetError as e:
        print("  " + str(e))
        ok = False
    results.append(("CGA map + blocks decode back to course_indices() (every map word a block offset)", ok))
    # the Hercules rule: each Hercules block is its CGA block converted
    herc_ok = True
    for n in range(nblk):
        for y in range(8):
            o = BLKOFF + 16 * n + 2 * y
            px = [(crsc[o + (x >> 2)] >> (6 - 2 * (x & 3))) & 3 for x in range(8)]
            if crsh[o:o + 2] != herc_bytes(px, line=y, col0=0):
                herc_ok = False
    results.append(("Hercules blocks: 0->00 3->11, 1/2 -> 10/01 by (line + column)", herc_ok))
    # the course is a course: all four colours, mostly not black, both halves used
    used = set()
    lit = 0
    for r in pic:
        used.update(r)
        lit += sum(1 for v in r if v)
    left = sum(1 for r in pic for v in r[:WPX // 4] if v)
    right = sum(1 for r in pic for v in r[3 * WPX // 4:] if v)
    results.append(("the course uses all four colours, %d%% lit, both edges reached" %
                    (100 * lit // (WPX * WPY)), used == {0, 1, 2, 3} and left > 0 and right > 0))
    _check_ball(a_files["BZBALC.BIN"], False, results)
    _check_ball(a_files["BZBALH.BIN"], True, results)
    # rolling is visible: every frame differs from its neighbours in phase
    differ = all(ball_frame_indices(fy * 8 + fx) != ball_frame_indices(fy * 8 + (fx + 1) % 8) and
                 ball_frame_indices(fy * 8 + fx) != ball_frame_indices(((fy + 1) % 8) * 8 + fx)
                 for fy in range(8) for fx in range(8))
    results.append(("every frame differs from its x and y phase neighbours", differ))
    # the route scrolls the camera BOTH ways on both axes (SPEC.md 128.6): some
    # leg goes left and some right, some down and some UP the screen
    way = waypoints()
    dxs = [b[0] - a[0] for a, b in zip(way, way[1:])]
    dys = [b[1] - a[1] for a, b in zip(way, way[1:])]
    results.append(("the route's legs go both ways in x and in y",
                    min(dxs) < 0 < max(dxs) and min(dys) < 0 < max(dys)))
    sil = all(all((c is None) == (not _silhouette(x, y)) for y, row in enumerate(ball_frame_indices(f))
                  for x, c in enumerate(row)) for f in range(NFRAMES))
    results.append(("the silhouette is the same 16 px disc in every frame", sil))
    # negative controls: a guard nobody has seen fire is a guard nobody knows is alive
    bad = bytearray(crsc)
    struct.pack_into("<H", bad, MAPOFF + 2 * 777, nblk * 16)
    try:
        _decode_course(bytes(bad), False)
        fired = False
    except AssetError:
        fired = True
    results.append(("negative control: a map word past the last block is refused", fired))
    bad = bytearray(a_files["BZBALC.BIN"])
    bad[BAL_FRMOFF] |= bad[BAL_MASKOFF] | 0xC0
    sub = []
    _check_ball(bytes(bad), False, sub)
    results.append(("negative control: a frame bit under a set mask bit is caught",
                    not all(good for _, good in sub)))
    ok = True
    for what, good in results:
        print("  %-4s %s" % ("ok" if good else "FAIL", what))
        ok = ok and good
    print("bonanza_assets selfcheck: %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


# =============================================================================
# --png: previews (Pillow, optional)
# =============================================================================

def previews(out):
    try:
        from PIL import Image
    except ImportError:
        print("bonanza_assets: --png needs Pillow; skipped", file=sys.stderr)
        return 1
    os.makedirs(out, exist_ok=True)
    pic = course_indices()
    img = Image.new("RGB", (WPX, WPY))
    img.putdata([CGA1[v] for r in pic for v in r])
    # the route, as small markers
    px = img.load()
    for (bx, by) in waypoints():
        for d in range(-3, 4):
            for (x, y) in ((bx + 8 + d, by + 8), (bx + 8, by + 8 + d)):
                px[x, y] = (255, 0, 0)
    img.save(os.path.join(out, "course.png"))
    img.resize((WPX * 2, WPY * 2), Image.NEAREST).crop((0, 0, WPX * 2, 900)).save(
        os.path.join(out, "course-top-x2.png"))
    # Hercules: each game pixel two card pixels
    h = Image.new("L", (WPX * 2, WPY))
    data = []
    for y, r in enumerate(pic):
        for x, v in enumerate(r):
            pr = herc_pair(v, y, x)
            data += [255 * (pr >> 1), 255 * (pr & 1)]
    h.putdata(data)
    h.save(os.path.join(out, "course-herc.png"))
    gap = 4
    sheet = Image.new("RGB", (P * (D + gap) + gap, P * (D + gap) + gap), (40, 40, 40))
    sp = sheet.load()
    for f in range(NFRAMES):
        ox, oy = gap + (f & 7) * (D + gap), gap + (f >> 3) * (D + gap)
        for y, row in enumerate(ball_frame_indices(f)):
            for x, c in enumerate(row):
                if c is not None:
                    sp[ox + x, oy + y] = CGA1[c]
    sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST).save(os.path.join(out, "ball.png"))
    print("bonanza_assets: previews in %s" % out)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", help="output directory")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--png", metavar="DIR", help="write preview PNGs (needs Pillow)")
    a = ap.parse_args()
    if not (a.out or a.selfcheck or a.png):
        ap.error("need -o OUT, --selfcheck or --png DIR")
    try:
        rc = 0
        if a.selfcheck:
            rc |= selfcheck()
        if a.out:
            files, nblk = write_out(a.out)
            print("bonanza_assets: %d blocks; %s" % (
                nblk, ", ".join("%s %d" % (k, len(files[k])) for k in sorted(files))))
        if a.png:
            rc |= previews(a.png)
        return rc
    except AssetError as e:
        print("bonanza_assets: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
