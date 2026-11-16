#!/usr/bin/env python3
"""BONANZA (Bounce Bonanza) ball generator and the shared encoders
(SPEC.md 128.3, 128.10.5.3, 128.11.9).

    python3 tools/bonanza_assets.py -o build/bonanza-art     # what `make` runs
    python3 tools/bonanza_assets.py --selfcheck              # invariants + determinism
    python3 tools/bonanza_assets.py --png DIR                # previews (needs Pillow)

Generates the phase-torus BALL from code alone: no ROM, no reference game, no
input file, no environment variable.  Python standard library only (Pillow is
used by --png and nothing else, behind a try/except) and deterministic: the
same tool gives byte-identical outputs, no timestamps, sorted iteration.

Since wave 1 the COURSES are text, compiled by tools/bbcourse.py, which
imports this module's palette and encoders (`cga_bytes`, `herc_pair`,
`herc_bytes`: 128.3's Hercules checker, which the ball must match, 128.9
item 7) - so a course and the ball cannot disagree about a mid-level pixel.
The renderer and wave 0's generated test course MOVED there (SPEC.md
128.10.4); this tool keeps the ball and the encoders.

Outputs, in the -o directory (the three ball PARTS of BONANZA.O88, then NASM):
    BZBALR.BIN    the rubber ball, BZB2, the CGA's (SPEC.md 128.11.9.1)
    BZBALS.BIN    the steel ball
    BZBALG.BIN    the glass ball (with its four shatter frames)
    bzconst.inc   the ball parts' layout
    .bz-art       stamp: sha256 of this tool (make's rebuild key), written FIRST
The Hercules parts are NOT shipped: the guest builds htab() (512 bytes) and
translates a fetched part in place (SPEC.md 128.11.3); herc_translate_ball()
is that translation on the host.  Wave 1's BZB1 builder (build_ball_part) is
kept as the reference the rubber part is held to.

Ball part, BZB2 (SPEC.md 128.11.9.1): +0 'BZB2', +4 frames (64), +6 rows (16),
+8 bytes a row (5), +10 the material, +11 squash frames (2), +12 shatter
frames (0 or 4), +13 shadow rows (6), +14 stretch frames (1 rubber, else 0,
wave 6), +15 a zero byte; +16 the masks (4
shifts x 16 rows x 5, the material's silhouette, a SET bit keeps); +336 the
64 roll frames, frame f at shift f & 3; +5,456 the squash entries (2 x 4
shifts x 2 line parities x (mask 80 + frame 80)); +8,016 the shadow masks (2
parities x 4 shifts x 6 rows x 5, AND only); +8,256 glass's shatter entries
(4 x 4 x 2 x 160), or rubber's STRETCH entry (1 x 4 x 2 x 160, wave 6, SPEC.md
128.16.4.4).  Steel 8,256 bytes, rubber 9,536, glass 13,376.

Wave 1's ball part, BZB1 (SPEC.md 128.10.5.3), the reference:
    +0 'BZB1'  +4 word frames (64)  +6 word rows (16)  +8 word bytes a row (5)
    +10 six zero bytes
    +16 masks: 4 shifts x 16 rows x 5 bytes, shift-major
    +336 frames: 64 x 16 rows x 5 bytes, frame f at shift f & 3.
    Hercules ball pixels: 0 -> 00, 3 -> 11, 1 and 2 -> the COURSE's checker
    (SPEC.md 128.9 item 7): 10 where (line + column) is even, 01 where odd.

Host reference for the rows (import this module):
    ball_frame_indices(f)   16 rows of 16 entries, an index or None (clear)
    cga_bytes(pixels)       pack indices 4 a byte, MSB first
    herc_bytes(pixels, line, col0=0)
                            pack as Hercules pairs by the course's checker,
                            pixels[0] at world (line, col0)
    ball_herc_pairs(f)      frame f as Hercules pairs (0..3) or None, by the
                            checker at the ball's world position
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

# --- the palette ----------------------------------------------------------------
BLK, CYN, MAG, WHT = 0, 1, 2, 3   # CGA palette 1
CGA1 = [(0, 0, 0), (85, 255, 255), (255, 85, 255), (255, 255, 255)]

# --- the ball ----------------------------------------------------------------
P = 8                         # texture period: P*P = 64 frames
D = 16                        # diameter, game pixels
RB = 5                        # bytes a row: 16 px + up to 3 px of shift
SHIFTS = 4
NFRAMES = P * P

HDR = 16
BAL_MASKOFF = HDR
BAL_MASKSIZE = SHIFTS * D * RB            # 320
BAL_FRMOFF = BAL_MASKOFF + BAL_MASKSIZE   # 336
BAL_FRMSIZE = NFRAMES * D * RB            # 5,120: each frame at its own shift
BAL_SIZE = BAL_FRMOFF + BAL_FRMSIZE       # 5,456


class AssetError(Exception):
    pass


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


def herc_pair(c, line, col):
    """one game pixel at world (line, col) -> its two card bits as a number
    0..3 (left bit high).  The course and the ball share it (SPEC.md 128.3,
    128.9 item 7): the mid level is 10 / 01 by (line + column)"""
    if c == BLK:
        return 0
    if c == WHT:
        return 3
    return 2 if (line + col) % 2 == 0 else 1


def herc_bytes(pixels, line, col0=0):
    """indices -> Hercules bytes, four game pixels (eight card pixels) a byte,
    pixels[0] at world (line, col0).  Only the parities matter, so the
    ball's frame-relative line and column (ball_herc_line) serve as well"""
    out = bytearray()
    for i in range(0, len(pixels), 4):
        v = 0
        for k in range(4):
            v = (v << 2) | herc_pair(pixels[i + k], line, col0 + i + k)
        out.append(v)
    return bytes(out)


def htab():
    """BZ_HTAB (SPEC.md 128.11.3): 512 bytes, [256 p + b] = the byte whose pixel
    j (0 the leftmost, bits 7 - 6) is herc_pair(c_j, p, j), c_j = (b >> (6 -
    2j)) & 3.  A block, a ball row and a squash row all start on a 4-pixel
    world column, so a byte's pixel j sits at an even column + j and only the
    PARITY of its line, p, chooses the table.  The guest's bz_hgen builds
    exactly this (two loops, four 2-bit fields a byte); nothing ships it."""
    out = bytearray(512)
    for p in range(2):
        for b in range(256):
            v = 0
            for j in range(4):
                c = (b >> (6 - 2 * j)) & 3
                v = (v << 2) | (0 if c == 0 else 3 if c == 3 else (2 if (p + j) & 1 == 0 else 1))
            out[256 * p + b] = v
    return bytes(out)


# =============================================================================
# the ball part (BZB1, SPEC.md 128.10.5.3)
# =============================================================================

def _ball_row(frame_row, shift):
    """one ball row at a shift -> (20 indices or None) slots"""
    slots = [None] * (RB * 4)
    for x, c in enumerate(frame_row):
        slots[shift + x] = c
    return slots


def ball_herc_line(f, s, r):
    """(line, col0) for herc_bytes of shift s, frame f, ball row r: congruent
    mod 2 to the world line and the world column of slot 0 of every ball
    position that uses them.  Slot j holds ball pixel x = j - s, which lands
    on world column px + x; px = fx (mod 8), py = fy (mod 8)."""
    return (f >> 3) + r, (f & 7) - s


def ball_herc_pairs(f):
    """frame f as Hercules pairs: 16 rows of 16 entries, 0..3 or None where the
    background shows; pixel (x, r) by the checker at world (py + r, px + x)"""
    return tuple(tuple(None if c is None else herc_pair(c, (f >> 3) + r, (f & 7) + x)
                       for x, c in enumerate(row))
                 for r, row in enumerate(ball_frame_indices(f)))


def build_ball_part(herc, _fixed_mid=False):
    """_fixed_mid: wave 0's Hercules ball (1 and 2 always 10), kept only as
    --selfcheck's negative control"""
    hdr = b"BZB1" + struct.pack("<HHH", NFRAMES, D, RB) + bytes(6)
    masks = bytearray()
    frames = bytearray()
    sil = ball_frame_indices(0)
    for s in range(SHIFTS):
        for row in sil:
            masks += cga_bytes([3 if c is None else 0 for c in _ball_row(row, s)])
    for f in range(NFRAMES):
        s = f & 3                             # the one shift frame f is drawn at
        for r, row in enumerate(ball_frame_indices(f)):
            slots = [0 if c is None else c for c in _ball_row(row, s)]
            if not herc:
                frames += cga_bytes(slots)
            elif _fixed_mid:
                frames += cga_bytes([2 if c in (CYN, MAG) else c for c in slots])
            else:
                line, col0 = ball_herc_line(f, s, r)
                frames += herc_bytes(slots, line, col0)
    out = bytes(hdr + masks + frames)
    if len(out) != BAL_SIZE:
        raise AssetError("ball part is %d bytes, not %d" % (len(out), BAL_SIZE))
    return out


# =============================================================================
# wave 2: three balls (BZB2, SPEC.md 128.11.9)
# =============================================================================

MAT_RUBBER, MAT_STEEL, MAT_GLASS = 0, 1, 2
MAT_NAMES = ("rubber", "steel", "glass")
BALL_FILES = ("BZBALR.BIN", "BZBALS.BIN", "BZBALG.BIN")
SEE = -1                      # a glass pixel the course shows through (its mask keeps it)

NSQ = 2                       # squash frames
SQ_ROWS = (13, 11)            # each one's height, bottom-anchored in the 16 rows
NSH = 4                       # glass's shatter frames: crack, burst, spread, glints
SHD_ROWS = 6                  # the shadow: a 16 x 6 ellipse, AND only
NST = 1                       # rubber's STRETCH frames (wave 6, the boost's cue)
ST_W = 12                     # the stretch: an ellipse 12 wide, 16 tall, centred
ENT = 2 * D * RB              # a squash or shatter entry: mask 80 + frame 80
B2_MASKOFF = HDR                                   # 16
B2_FRMOFF = B2_MASKOFF + SHIFTS * D * RB           # 336
B2_SQOFF = B2_FRMOFF + NFRAMES * D * RB            # 5,456
B2_SHDOFF = B2_SQOFF + NSQ * SHIFTS * 2 * ENT      # 8,016
B2_SHAOFF = B2_SHDOFF + 2 * SHIFTS * SHD_ROWS * RB  # 8,256
B2_STROFF = B2_SHAOFF                              # 8,256: rubber's stretch, where glass's shatter is
B2_SIZE = (B2_STROFF + NST * SHIFTS * 2 * ENT, B2_SHAOFF,
           B2_SHAOFF + NSH * SHIFTS * 2 * ENT)     # 9,536, 8,256, 13,376


def nstretch(mat):
    """BZB2 +14: the material's stretch frames (SPEC.md 128.16.4.4)"""
    return NST if mat == MAT_RUBBER else 0


def _rim(x, y):
    """the silhouette's outermost ring: a disc pixel with a 4-neighbour outside"""
    return _silhouette(x, y) and any(not _silhouette(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def _band(u, v):
    """steel's SEAM: two crossing stripes of the 8-periodic texture (plan
    section 4's 'band'), so the ball's turning shows on both axes"""
    u %= P
    v %= P
    return abs(u - P / 2 + 0.5) < 1.0 or abs(v - P / 2 + 0.5) < 1.0


def _glint(u, v):
    u %= P
    v %= P
    du, dv = u - P / 2 + 0.5, v - P / 2 + 0.5
    return du * du + dv * dv < 1.3


def _see(x, y):
    """glass: the interior pixels the course shows through - a checker FIXED
    in the disc's own pixels (so the course shimmers through it as it rolls)"""
    return _silhouette(x, y) and not _rim(x, y) and (x + y) & 1 == 0


@functools.lru_cache(maxsize=None)
def material_frame(mat, fx, fy):
    """one 16 x 16 roll frame of a material: rows of an index, None (outside
    the disc) or SEE (glass's see-through checker).  Rubber is wave 1's ball
    exactly (bonanzaassets holds it to wave 1's Hercules part)."""
    if mat == MAT_RUBBER:
        return _ball_frame(fx, fy)
    rows = []
    for py in range(D):
        row = []
        for px in range(D):
            if not _silhouette(px, py):
                row.append(None)
                continue
            if _rim(px, py):
                row.append(BLK)
                continue
            if mat == MAT_GLASS and _see(px, py):
                row.append(SEE)
                continue
            x = (px + 0.5 - R_) / R_
            y = (py + 0.5 - R_) / R_
            z = math.sqrt(max(0.0, 1.0 - x * x - y * y))
            lam = x * LIGHT[0] + y * LIGHT[1] + z * LIGHT[2]
            rz = 2 * lam * z - LIGHT[2]
            u = R_ * math.asin(max(-1.0, min(1.0, x))) - fx
            v = R_ * math.asin(max(-1.0, min(1.0, y))) - fy
            if mat == MAT_STEEL:
                c = WHT if _band(u, v) else CYN
                if rz > 0.90:                     # a HARD highlight: metal
                    c = WHT
                thr = (BAYER2[py & 1][px & 1] + 0.5) / 4.0
                if lam < 0.06 or (lam < 0.30 and (lam - 0.06) / 0.24 < thr):
                    c = BLK
            else:                                 # glass: a cyan tint, glints
                c = WHT if _glint(u, v) else CYN
                if rz > 0.93:
                    c = WHT
                if lam < 0.10:
                    c = BLK
            row.append(c)
        rows.append(tuple(row))
    return tuple(rows)


def _squash_shape(k, x, y):
    """squash frame k (13 rows, then 11), bottom-anchored: an ellipse 16 wide"""
    h = SQ_ROWS[k]
    top = D - h
    if y < top:
        return False
    cx, cy = (D - 1) / 2.0, top + (h - 1) / 2.0
    ax, ay = D / 2.0, h / 2.0
    return ((x - cx) / ax) ** 2 + ((y - cy) / ay) ** 2 <= 1.0 + 1e-9


def squash_frame(mat, k):
    """squash frame k of a material: the same look as its roll frame 0 pressed
    into the ellipse, its outermost ring black"""
    base = material_frame(mat, 0, 0)
    h = SQ_ROWS[k]
    rows = []
    for y in range(D):
        row = []
        for x in range(D):
            if not _squash_shape(k, x, y):
                row.append(None)
                continue
            if any(not _squash_shape(k, x + dx, y + dy) or not 0 <= x + dx < D or not 0 <= y + dy < D
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                row.append(BLK)
                continue
            if mat == MAT_GLASS and (x + y) & 1 == 0:
                row.append(SEE)
                continue
            sy = D - 1 - int((D - 1 - y) * D / h)      # sample the round frame, pressed
            c = base[sy][x]
            if c is None or c == SEE:
                c = CYN if mat != MAT_RUBBER else MAG
            row.append(c)
        rows.append(tuple(row))
    return tuple(rows)


def _stretch_shape(x, y):
    """the stretch (SPEC.md 128.16.4.4): an ellipse ST_W wide and 16 tall,
    centred in the 16 x 16 frame"""
    cx = cy = (D - 1) / 2.0
    ax, ay = ST_W / 2.0, D / 2.0
    return ((x - cx) / ax) ** 2 + ((y - cy) / ay) ** 2 <= 1.0 + 1e-9


def stretch_frame(mat):
    """the boost's STRETCH frame: roll frame 0's look pressed in ACROSS into
    the 12 x 16 ellipse (squash_frame's method, across instead of down), its
    outermost ring black"""
    base = material_frame(mat, 0, 0)
    x0 = (D - ST_W) // 2
    rows = []
    for y in range(D):
        row = []
        for x in range(D):
            if not _stretch_shape(x, y):
                row.append(None)
                continue
            if any(not _stretch_shape(x + dx, y + dy) or not 0 <= x + dx < D or not 0 <= y + dy < D
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                row.append(BLK)
                continue
            if mat == MAT_GLASS and (x + y) & 1 == 0:
                row.append(SEE)
                continue
            sx = min(D - 1, int((x - x0 + 0.5) * D / ST_W))   # sample the round frame, pressed in
            c = base[y][sx]
            if c is None or c == SEE:
                c = CYN if mat != MAT_RUBBER else MAG
            row.append(c)
        rows.append(tuple(row))
    return tuple(rows)


def shatter_frame(k):
    """glass's shatter frame k, in footprint slots x = -2 .. 17 (ball pixels;
    clipped to the 20 slots at each shift), 16 rows: crack, burst, spread,
    glints.  The shards spread toward the footprint's edges and fall two
    lines over the four."""
    base = material_frame(MAT_GLASS, 0, 0)
    out = {}
    if k == 0:                                     # the crack: the disc with black fault lines
        for y in range(D):
            for x in range(D):
                c = base[y][x]
                if c is None:
                    continue
                if c != SEE and (abs((x - 7.5) - 0.6 * (y - 7.5)) < 0.7 or abs((y - 6.5) + 0.8 * (x - 9)) < 0.6):
                    c = BLK
                out[(x, y)] = c
        return out
    # the pieces: the disc's four quadrants pushed out, smaller each frame.
    # Every piece is outlined BLACK where the entry is built (_ring_slots,
    # after the clip to the footprint), so a shard is never the course's own
    # colour against it (SPEC.md 128.11.9.1: the ring is on every frame)
    spread = (0, 2, 4, 5)[k]
    fall = (0, 0, 1, 2)[k]
    for y in range(D):
        for x in range(D):
            c = base[y][x]
            if c is None:
                continue
            qx = -1 if x < 8 else 1
            qy = -1 if y < 8 else 1
            if k == 3:                                 # glints: a few white sparks
                if (x * 7 + y * 3) % 11 != 0:          # (each gets its black
                    continue                           # surround at the ring)
                c = WHT
            elif k == 2 and (x + 4 - (y & 7)) & 7 == 0:
                continue                               # spread: each quadrant in two
            nx = x + qx * spread
            ny = y + (qy * spread) // 2 + fall
            if 0 <= ny < D:
                out[(nx, ny)] = c
    if k == 3:                                         # a glint is white ON black:
        for (x, y) in list(out):                       # its 4-neighbours join it
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if 0 <= y + dy < D:
                    out.setdefault((x + dx, y + dy), BLK)
    return out


def _ring_slots(rows):
    """a shatter entry's 16 rows of 20 slots, clipped: every piece pixel with a
    4-neighbour clear (or past the entry's edge) made BLACK - the outer ring
    of SPEC.md 128.11.9.1 on every shatter frame at every shift"""
    out = []
    for r, sl in enumerate(rows):
        row = list(sl)
        for j, c in enumerate(sl):
            if c is None:
                continue
            if any(not (0 <= j + dx < len(sl) and 0 <= r + dy < len(rows))
                   or rows[r + dy][j + dx] is None
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                row[j] = BLK
        out.append(row)
    return out


def _slots(rowpix, shift, x0=0):
    """{x: index} -> 20 slots at a shift: ball pixel x lands in slot x + shift"""
    sl = [None] * (RB * 4)
    for x, c in rowpix.items():
        j = x + shift
        if 0 <= j < RB * 4:
            sl[j] = c
    return sl


def _encode(slots):
    """20 slots (index, SEE or None) -> (mask 5 bytes, frame 5 bytes)"""
    m = cga_bytes([3 if c is None or c == SEE else 0 for c in slots])
    f = cga_bytes([0 if c is None or c == SEE else c for c in slots])
    return m, f


def _rows_of(frame):
    return [{x: c for x, c in enumerate(row) if c is not None} for row in frame]


def build_ball2(mat):
    """BZB2, the CGA's (SPEC.md 128.11.9.1); the Hercules one is made at the fetch"""
    nsh = NSH if mat == MAT_GLASS else 0
    nst = nstretch(mat)
    hdr = b"BZB2" + struct.pack("<HHHBBBBBB", NFRAMES, D, RB, mat, NSQ, nsh, SHD_ROWS, nst, 0)
    assert len(hdr) == HDR
    out = bytearray(hdr)
    sil = _rows_of(material_frame(mat, 0, 0))
    for s in range(SHIFTS):                        # the MASKS: the material's silhouette
        for r in range(D):
            out += _encode(_slots(sil[r], s))[0]
    for f in range(NFRAMES):                       # the ROLL frames, frame f at shift f & 3
        rows = _rows_of(material_frame(mat, f & 7, f >> 3))
        for r in range(D):
            out += _encode(_slots(rows[r], f & 3))[1]
    for k in range(NSQ):                           # SQUASH: 2 x 4 shifts x 2 parities
        rows = _rows_of(squash_frame(mat, k))
        for s in range(SHIFTS):
            for p in range(2):
                enc = [_encode(_slots(rows[r], s)) for r in range(D)]
                out += b"".join(e[0] for e in enc) + b"".join(e[1] for e in enc)
    for p in range(2):                             # the SHADOW: AND only
        for s in range(SHIFTS):
            out += shadow_mask(p, s)
    for k in range(nsh):                           # SHATTER (glass)
        pix = shatter_frame(k)
        rows = [{x: c for (x, y), c in pix.items() if y == r} for r in range(D)]
        for s in range(SHIFTS):
            ringed = _ring_slots([_slots(rows[r], s) for r in range(D)])
            for p in range(2):
                enc = [_encode(sl) for sl in ringed]
                out += b"".join(e[0] for e in enc) + b"".join(e[1] for e in enc)
    for k in range(nst):                           # STRETCH (rubber): the squash's entry
        rows = _rows_of(stretch_frame(mat))        # format, at +8,256
        for s in range(SHIFTS):
            for p in range(2):
                enc = [_encode(_slots(rows[r], s)) for r in range(D)]
                out += b"".join(e[0] for e in enc) + b"".join(e[1] for e in enc)
    if len(out) != B2_SIZE[mat]:
        raise AssetError("%s ball part is %d bytes, not %d" % (MAT_NAMES[mat], len(out), B2_SIZE[mat]))
    return bytes(out)


def _shadow_in(x, y):
    cx, cy = (D - 1) / 2.0, (SHD_ROWS - 1) / 2.0
    return ((x - cx) / (D / 2.0)) ** 2 + ((y - cy) / (SHD_ROWS / 2.0)) ** 2 <= 1.0 + 1e-9


def shadow_mask(p, s):
    """shadow (p = its first line's parity, s = px & 3): 6 rows x 5 bytes, a SET
    bit keeps; inside the ellipse every pixel of the WORLD checker (x + y) even
    is cleared to black.  Slot j of row r is world column (px & ~3) + j, a
    multiple of 4 plus j, on a line of parity p + r."""
    out = bytearray()
    for r in range(SHD_ROWS):
        sl = []
        for j in range(RB * 4):
            x = j - s
            clear = 0 <= x < D and _shadow_in(x, r) and (j + p + r) & 1 == 0
            sl.append(0 if clear else 3)
        out += cga_bytes(sl)
    return bytes(out)


def herc_translate_ball(part, table=None):
    """the Hercules ball part bz_hxlat makes at the fetch (SPEC.md 128.11.3):
    roll frame f's row r through table ((f >> 3) + r) & 1; the FRAME half of a
    squash, shatter or stretch entry of parity copy p, row r, through (p + r) & 1;
    masks and the shadow untouched (a mask is the same bytes on both cards)"""
    t = table if table is not None else htab()
    b = bytearray(part)
    nsh = b[12] + b[14]                    # shatter or stretch: never both, one table
    for f in range(NFRAMES):
        for r in range(D):
            o = B2_FRMOFF + (f * D + r) * RB
            for i in range(RB):
                b[o + i] = t[256 * (((f >> 3) + r) & 1) + b[o + i]]
    for base, n in ((B2_SQOFF, NSQ), (B2_SHAOFF, nsh)):
        for k in range(n):
            for s in range(SHIFTS):
                for p in range(2):
                    e = base + ((k * SHIFTS + s) * 2 + p) * ENT + D * RB
                    for r in range(D):
                        for i in range(RB):
                            o = e + r * RB + i
                            b[o] = t[256 * ((p + r) & 1) + b[o]]
    return bytes(b)



# =============================================================================
# wave 9 (SPEC.md 128.25.5): BZB3, the ball part's STORED form.  BZB2's header,
# zeros, and a BLOCK at the head of the squash slot (BG_BLK) which the guest's
# bz_ballgen (apps/bonanza/bzballgen.inc) expands, in place and forwards, into
# BZB2 byte for byte; glass's shatter entries stay as they are (literal).
# =============================================================================

BG_BLK = B2_SQOFF
BG_NP, BG_CLO, BG_CHI, BG_O = 0, 2, 34, 66
BG_SQ0, BG_SQ1, BG_STR, BG_SHD, BG_SX = 98, 115, 132, 149, 166
BG_PRE = 182                       # the prefix the guest copies to scratch
BG_XR = 182                        # the x side's ranks, 16 x 8 bytes, COLUMN-major: (R' + 1) * BG_PSTR
BG_YE = BG_XR + 128                # the y side's thresholds, 8 x 16 bytes, fy-major: E' * BG_PSTR
BG_LEN = BG_YE + 128
BG_PSTR = 6                        # the guest's mask table: an entry's bytes
BG_PMAX = 25                       # ...and its entries at most (bz_boxbuf's room)
V2_CFG = ((2560, 512), (2, None), (21, 16))     # (T, scale) a material


def _dd(p, f):
    return (R_ * math.asin((p + 0.5 - R_) / R_) - f) % P - 3.5


def _tex_classes(mat):
    """(Clo, Chi, O) planes: the template over all 64 frames - O opaque; the
    low/high planes the CONSTANT colour (white, or the base colour of a tex pixel)"""
    clo, chi, op = [], [], []
    for r in range(D):
        lo = hi = o = 0
        for x in range(D):
            cols = {material_frame(mat, f & 7, f >> 3)[r][x] for f in range(NFRAMES)}
            if cols in ({2, 3}, {1, 3}):
                b = min(cols); l, h, q = b & 1, b >> 1, 1
            elif cols == {3}:
                l, h, q = 1, 1, 1
            elif cols == {0}:
                l, h, q = 0, 0, 1
            else:
                l, h, q = 0, 0, 0
            lo, hi, o = lo << 1 | l, hi << 1 | h, o << 1 | q
        clo.append(lo); chi.append(hi); op.append(o)
    return clo, chi, op


def rank_tables(mat):
    """the phase sum's test RANK-CODED (SPEC.md 128.25.5.1): ink at column x of
    roll phase fx, row j = fy * 16 + r, is G[fx][x] + G[fy][r] < T, which is
    R'[fx][x] < E'[j] for small integers: R the rank of G among its distinct
    values, E the count of distinct values under T - G[j]; cuts that split no
    rank merged; a row whose ink is empty for every fx given E' 0.  Returns
    (NP, XR, YE): XR = (R' + 1) * BG_PSTR, YE = E' * BG_PSTR (the guest's mask
    table offsets), NP = the table's entries (K + 2)"""
    T, G = phase_table(mat)
    clo, chi, op = _tex_classes(mat)
    W = sorted(set(G))
    R = [W.index(g) for g in G]
    E = [sum(1 for w in W if w + g < T) for g in G]
    for j in range(128):                           # a row with no ink in any phase
        tex = clo[j & 15] ^ chi[j & 15]
        if not any(R[fx * 16 + x] < E[j] and tex >> (15 - x) & 1 for fx in range(8) for x in range(D)):
            E[j] = 0
    cuts, prev = [], frozenset()
    for c in sorted(set(E) - {0}):
        st = frozenset(i for i in range(128) if R[i] < c)
        if st and st != prev:
            cuts.append(c)
            prev = st
    def cls(c):                                    # the kept cut equivalent to c
        if c == 0:
            return 0
        st = frozenset(i for i in range(128) if R[i] < c)
        for k, ck in enumerate(cuts):
            if frozenset(i for i in range(128) if R[i] < ck) == st:
                return k + 1
        return 0
    Ep = [cls(e) for e in E]
    Rp = [sum(1 for c in cuts if c <= r) for r in R]
    for fx in range(8):                            # the recoding is exact
        for j in range(128):
            assert all((R[fx * 16 + x] < E[j]) == (Rp[fx * 16 + x] < Ep[j]) for x in range(D)
                       if (clo[j & 15] ^ chi[j & 15]) >> (15 - x) & 1)
    np_ = len(cuts) + 2
    if np_ > BG_PMAX:
        raise AssetError("%s: %d mask entries, the generator holds %d" % (MAT_NAMES[mat], np_, BG_PMAX))
    return np_, bytes((r + 1) * BG_PSTR for r in Rp), bytes(e * BG_PSTR for e in Ep)


def phase_table(mat):
    T, S = V2_CFG[mat]
    out = []
    for f in range(8):
        for x in range(D):
            if mat == MAT_STEEL:
                out.append(0 if abs(_dd(x, f)) < 1.0 else 1)
            else:
                out.append(min(round(_dd(x, f) ** 2 * S), T))
    return T, out


def _nrows(shape, rows):
    out = []
    for y in range(rows):
        xs = [x for x in range(D) if shape(x, y)]
        assert xs == list(range(8 - len(xs) // 2, 8 + len(xs) // 2)), (y, xs)
        out.append(len(xs) // 2)
    return out


def shape_tables():
    sq = []
    for k in range(NSQ):
        ns = [0] * (D - SQ_ROWS[k]) + _nrows(lambda x, y, k=k, t=D - SQ_ROWS[k]: _squash_shape(k, x, y + t), SQ_ROWS[k])
        sq.append(bytes([SQ_ROWS[k]] + ns))
    st = bytes([D] + _nrows(_stretch_shape, D))
    sh = bytes([D] + _nrows(_shadow_in, SHD_ROWS) + [0] * (D - SHD_ROWS))
    x0 = (D - ST_W) // 2
    sx = bytes((min(D - 1, int((x - x0 + 0.5) * D / ST_W)) if x >= x0 else 0) + 1 for x in range(D))
    return sq[0], sq[1], st, sh, sx


def build_ball3(mat):
    """BZB3: BZB2's size, its header, zeros, the block, glass's shatter as is"""
    ref = build_ball2(mat)
    clo, chi, op = _tex_classes(mat)
    np_, xr, ye = rank_tables(mat)
    sq0, sq1, st, sh, sx = shape_tables()
    if mat != MAT_RUBBER:
        st = bytes(17); sx = bytes(16)
    blk = struct.pack("<H", np_)
    for pl in (clo, chi, op):
        blk += struct.pack("<16H", *pl)
    blk += sq0 + sq1 + st + sh + sx
    assert len(blk) == BG_PRE
    blk += bytes(xr[fx * 16 + x] for x in range(D) for fx in range(8)) + ye   # (packs 33 bytes better)
    assert len(blk) == BG_LEN
    out = bytearray(len(ref))
    out[:HDR] = ref[:HDR]
    out[BG_BLK:BG_BLK + BG_LEN] = blk
    if mat == MAT_GLASS:
        out[B2_SHAOFF:] = ref[B2_SHAOFF:]
    return bytes(out)


# the generator's HOST MODEL (the same planes and order as bzballgen.inc; the
# emulated-8086 proof is tools/bzballchk.py)
def _spread(w):
    v = 0
    for i in range(16):
        v = v << 2 | (3 if (w >> (15 - i)) & 1 else 0)
    return v


def _inter(hi, lo):
    v = 0
    for i in range(16):
        v = v << 2 | ((hi >> (15 - i)) & 1) << 1 | (lo >> (15 - i)) & 1
    return v


def _put5(v32, s, fill1):
    v = (v32 << 8) | (0xFF if fill1 else 0)
    top = ((1 << 2 * s) - 1 << 40 - 2 * s) if fill1 else 0
    return (((v >> 2 * s) | top) & (1 << 40) - 1).to_bytes(5, "big")


def model_ball3(stored):
    """BZB3 -> BZB2 by the guest's algorithm"""
    mat = stored[10]
    b = stored[BG_BLK:BG_BLK + BG_LEN]
    w = lambda o: struct.unpack_from("<H", b, o)[0]
    clo = [w(BG_CLO + 2 * i) for i in range(16)]
    chi = [w(BG_CHI + 2 * i) for i in range(16)]
    op = [w(BG_O + 2 * i) for i in range(16)]
    XR, YE = b[BG_XR:BG_XR + 128], b[BG_YE:BG_YE + 128]
    out = bytearray(stored)
    bh = 0xFFFF if mat == MAT_RUBBER else 0
    qlo = [0] * 16; qhi = [0] * 16
    for s in range(SHIFTS):
        for r in range(D):
            o = B2_MASKOFF + (s * D + r) * RB
            out[o:o + RB] = _put5(_spread(~op[r] & 0xFFFF), s, True)
    for f in range(NFRAMES):
        fx, fy = f & 7, f >> 3
        for r in range(D):
            ink = 0
            for x in range(D):
                ink = ink << 1 | (XR[x * 8 + fx] <= YE[fy * 16 + r])
            ink &= clo[r] ^ chi[r]
            lo, hi = clo[r] | ink, chi[r] | ink
            if f == 0:
                qlo[r] = lo | (~bh & ~op[r] & 0xFFFF)
                qhi[r] = hi | (bh & ~op[r] & 0xFFFF)
            o = B2_FRMOFF + (f * D + r) * RB
            out[o:o + RB] = _put5(_inter(hi, lo), f & 3, False)
    tabs = [b[BG_SQ0:BG_SQ0 + 17], b[BG_SQ1:BG_SQ1 + 17], b[BG_STR:BG_STR + 17]]
    sxt = b[BG_SX:BG_SX + 16]
    o = B2_SQOFF

    def S_of(n):
        return ((1 << 2 * n) - 1 << 8 - n) & 0xFFFF if n else 0

    def entry(tab, o):
        h = tab[0]
        S = [0] + [S_of(n) for n in tab[1:]] + [0]
        chk = 0xAAAA if mat == MAT_GLASS else 0
        pl = []
        for y in range(D):
            s_ = S[y + 1]
            i = s_ & (s_ << 1 & 0xFFFF) & (s_ >> 1) & S[y] & S[y + 2]
            k = chk & i
            chk = (chk >> 1 | chk << 15) & 0xFFFF
            sy = 15 - (15 - y) * 16 // h
            pl.append((s_ ^ k, qlo[sy] & (i ^ k), qhi[sy] & (i ^ k)))
        for s in range(SHIFTS):
            e = b"".join(_put5(_spread(~p[0] & 0xFFFF), s, True) for p in pl)
            e += b"".join(_put5(_inter(p[2], p[1]), s, False) for p in pl)
            out[o:o + 2 * len(e)] = e + e
            o += 2 * len(e)
        return o

    o = entry(tabs[0], o)
    o = entry(tabs[1], o)
    S = [S_of(n) for n in b[BG_SHD + 1:BG_SHD + 17]]
    for p in range(2):
        for s in range(SHIFTS):
            for r in range(SHD_ROWS):
                chk = 0xAAAA if (s + p + r) % 2 == 0 else 0x5555
                out[o:o + RB] = _put5(_spread(~(S[r] & chk) & 0xFFFF), s, True)
                o += RB
    if mat == MAT_RUBBER:
        qlo = [sum(((q >> 15 - (sxt[x] - 1)) & 1) << 15 - x for x in range(16)) for q in qlo]
        qhi = [sum(((q >> 15 - (sxt[x] - 1)) & 1) << 15 - x for x in range(16)) for q in qhi]
        entry(tabs[2], B2_STROFF)
    return bytes(out)


def _paras(n):
    return (n + 15) // 16


def emit_const():
    lines = [
        "; bzconst.inc - GENERATED by tools/bonanza_assets.py (SPEC.md 128.3, 128.11.9).",
        "; Do not edit: change the tool and rebuild.  The ball parts' layout; the",
        "; courses' are tools/bbcourse.py's bzcourse.inc and their parts' headers.",
        "",
        "; the ball parts (BZBALR/S/G.BIN, BZB2, the CGA's; the Hercules part is",
        "; made from it at the fetch, SPEC.md 128.11.3)",
        "BZ_BAL_FRAMES   equ %d" % NFRAMES,
        "BZ_BAL_SHIFTS   equ %d" % SHIFTS,
        "BZ_BAL_ROWS     equ %d" % D,
        "BZ_BAL_RB       equ %d         ; bytes a row" % RB,
        "BZ_BAL_D        equ %d        ; the ball's diameter, game pixels" % D,
        "BZ_BAL_MASKOFF  equ %d        ; masks: shift x row x byte, SET keeps" % B2_MASKOFF,
        "BZ_BAL_MASKSH   equ %d        ; bytes of mask a shift" % (D * RB),
        "BZ_BAL_FRMOFF   equ %d       ; roll frames: frame x row x byte, frame f at shift f & 3" % B2_FRMOFF,
        "BZ_BAL_FRMB     equ %d        ; bytes a frame" % (D * RB),
        "BZ_BAL_SQOFF    equ %d      ; squash: frame x shift x parity x (mask, frame)" % B2_SQOFF,
        "BZ_BAL_NSQ      equ %d" % NSQ,
        "BZ_BAL_ENT      equ %d       ; a squash or shatter entry: mask 80 + frame 80" % ENT,
        "BZ_BAL_SQ0ROWS  equ %d        ; squash 0's height, bottom-anchored" % SQ_ROWS[0],
        "BZ_BAL_SQ1ROWS  equ %d" % SQ_ROWS[1],
        "BZ_BAL_SHDOFF   equ %d      ; the shadow: parity x shift x 6 rows x 5 bytes, AND only" % B2_SHDOFF,
        "BZ_BAL_SHDROWS  equ %d" % SHD_ROWS,
        "BZ_BAL_SHDB     equ %d       ; bytes a shadow mask" % (SHD_ROWS * RB),
        "BZ_BAL_SHAOFF   equ %d      ; glass's shatter: frame x shift x parity x (mask, frame)" % B2_SHAOFF,
        "BZ_BAL_NSHA     equ %d" % NSH,
        "BZ_BAL_STROFF   equ %d      ; rubber's stretch (wave 6): shift x parity x (mask, frame)" % B2_STROFF,
        "BZ_BAL_NSTR     equ %d        ; ...its frames, BZB2 +14" % NST,
        "BZ_BAL_SIZER    equ %d      ; rubber" % B2_SIZE[0],
        "BZ_BAL_SIZE     equ %d      ; steel" % B2_SIZE[1],
        "BZ_BAL_SIZEG    equ %d     ; glass" % B2_SIZE[2],
        "; BZB3's block (SPEC.md 128.25.5): at the head of the squash slot",
        "BZ_BG_BLK       equ %d" % BG_BLK,
        "BZ_BG_NP        equ %d      ; byte: the mask table's entries" % BG_NP,
        "BZ_BG_CLO       equ %d" % BG_CLO,
        "BZ_BG_CHI       equ %d" % BG_CHI,
        "BZ_BG_O         equ %d" % BG_O,
        "BZ_BG_SQ0       equ %d" % BG_SQ0,
        "BZ_BG_SQ1       equ %d" % BG_SQ1,
        "BZ_BG_STR       equ %d" % BG_STR,
        "BZ_BG_SHD       equ %d" % BG_SHD,
        "BZ_BG_SX        equ %d" % BG_SX,
        "BZ_BG_PRE       equ %d      ; the prefix copied to scratch" % BG_PRE,
        "BZ_BG_XR        equ %d      ; the x side's ranks (read in place)" % (BG_BLK + BG_XR),
        "BZ_BG_YE        equ %d      ; the y side's thresholds (read in place)" % (BG_BLK + BG_YE),
        "BZ_BG_PSTR      equ %d" % BG_PSTR,
        "BZ_BG_PMAX      equ %d" % BG_PMAX,
        "",
    ]
    return "\n".join(lines)


def compile_all(stored=False):
    """stored: the files `make` ships, BZB3 (wave 9, SPEC.md 128.25.5); else BZB2, the RAM form.
    A material whose BZB3 the generator's model does not expand back to its BZB2 is REFUSED
    (128.25.5: a texture V2 cannot reproduce), never shipped to be drawn wrong"""
    files = {}
    for m in range(3):
        if stored:
            st = build_ball3(m)
            if model_ball3(st) != build_ball2(m):
                raise SystemExit("bonanza_assets: %s: BZB3 does not expand back to BZB2 (SPEC.md 128.25.5: "
                                 "V2 cannot reproduce this texture, and there is no V1)" % MAT_NAMES[m])
            files[BALL_FILES[m]] = st
        else:
            files[BALL_FILES[m]] = build_ball2(m)
    texts = {"bzconst.inc": emit_const()}
    return files, texts


def stamp():
    h = hashlib.sha256()
    h.update(b"tools/bonanza_assets.py\0")
    with open(TOOL, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def write_out(out):
    os.makedirs(out, exist_ok=True)
    # the stamp goes FIRST: make's outputs depend on it, so a run that dies
    # part-way leaves an up-to-date stamp and missing outputs, which make's
    # fallback recipe turns back into a re-run that shows the error
    with open(os.path.join(out, ".bz-art"), "w") as f:
        f.write(stamp() + "\n")
    files, texts = compile_all(True)
    for name in sorted(files):
        with open(os.path.join(out, name), "wb") as f:
            f.write(files[name])
    for name in sorted(texts):
        with open(os.path.join(out, name), "w", newline="\n") as f:
            f.write(texts[name])
    return files


# =============================================================================
# --selfcheck: the ball alone (SPEC.md 128.10.11.3's bonanzaassets)
# =============================================================================

def _check_ball(part, herc, results):
    name = "BZBALH" if herc else "BZBALC"
    hdr = struct.unpack_from("<HHH", part, 4)
    results.append(("%s header (BZB1, 64 frames, 16 rows, 5 bytes, six zero bytes, %d bytes)"
                    % (name, BAL_SIZE),
                    part[:4] == b"BZB1" and hdr == (NFRAMES, D, RB)
                    and part[10:16] == bytes(6) and len(part) == BAL_SIZE))
    masks = part[BAL_MASKOFF:BAL_FRMOFF]
    frames = part[BAL_FRMOFF:]
    ok_pairs = all(((b >> k) & 3) in (0, 3) for b in masks for k in (0, 2, 4, 6))
    results.append(("%s mask pixels are 00 (ball) or 11 (keep)" % name, ok_pairs))
    under = 0
    for f in range(NFRAMES):
        s = f & 3
        for r in range(D):
            for k in range(RB):
                m = masks[(s * D + r) * RB + k]
                v = frames[(f * D + r) * RB + k]
                under += bin(v & m).count("1")
    results.append(("%s frame bits only where the frame's own shift's mask is clear (%d stray)"
                    % (name, under), under == 0))
    # the silhouette is the disc, shift s is shift 0 moved s pixels right, and
    # frame f decodes back to 128.3's frame at shift f & 3
    good = True
    for s in range(SHIFTS):
        for r in range(D):
            want = cga_bytes([3 if c is None else 0 for c in _ball_row(ball_frame_indices(0)[r], s)])
            if masks[(s * D + r) * RB:(s * D + r + 1) * RB] != want:
                good = False
    for f in range(NFRAMES):
        s = f & 3
        for r, row in enumerate(ball_frame_indices(f)):
            o = (f * D + r) * RB
            for x in range(D):
                j = x + s
                v = (frames[o + (j >> 2)] >> (6 - 2 * (j & 3))) & 3
                c = row[x]
                if c is None:
                    good = good and v == 0
                elif herc:
                    good = good and v == herc_pair(c, (f >> 3) + r, (f & 7) + x)
                else:
                    good = good and v == c
            for j in list(range(s)) + list(range(s + D, RB * 4)):
                good = good and ((frames[o + (j >> 2)] >> (6 - 2 * (j & 3))) & 3) == 0
    results.append(("%s frame f decodes back to 128.3's frame f at shift f & 3, every frame; %s"
                    % (name, "the Hercules checker" if herc else "CGA 2-bit"), good))


def _check_herc_ball_checker(part):
    """SPEC.md 128.9 item 7, read off the part independently of the encoder:
    each lit mid pixel (not 00, not 11) of frame f is 10 where the world
    (line + column) it lands on is even and 01 where odd, the world position
    reckoned both from the ball's (px, py) and from the byte it lands in (the
    row starts at world byte px >> 2, so slot j is world column 4 (px >> 2) + j).
    Returns (bad, mids, tens, ones)."""
    frames = part[BAL_FRMOFF:]
    bad = mids = tens = ones = 0
    for f in range(NFRAMES):
        fx, fy = f & 7, f >> 3
        s = f & 3
        for r, row in enumerate(ball_frame_indices(f)):
            o = (f * D + r) * RB
            for j in range(RB * 4):
                pr = (frames[o + (j >> 2)] >> (6 - 2 * (j & 3))) & 3
                x = j - s
                c = row[x] if 0 <= x < D else None
                if c not in (CYN, MAG):
                    continue
                mids += 1
                tens += pr == 2
                ones += pr == 1
                ok = True
                for px, py in ((fx, fy), (fx + 8 * 37, fy + 8 * 151)):
                    ok = ok and pr == (2 if ((py + r) + (px + x)) % 2 == 0 else 1)
                    col = 4 * (px >> 2) + j
                    ok = ok and pr == (2 if ((py + r) + col) % 2 == 0 else 1)
                bad += not ok
    return bad, mids, tens, ones


def _decode_pix(maskrow, frmrow):
    """a 5-byte mask row and frame row -> 20 slots: None (kept) or an index"""
    out = []
    for j in range(RB * 4):
        m = (maskrow[j >> 2] >> (6 - 2 * (j & 3))) & 3
        v = (frmrow[j >> 2] >> (6 - 2 * (j & 3))) & 3
        out.append(None if m == 3 else v if m == 0 else ("bad", m))
    return out


def _check_ball2(mat, part, results, tag=None):
    """BZB2's own checks for one material (SPEC.md 128.11.17.2's bonanzaassets)"""
    name = tag or "%s (%s)" % (BALL_FILES[mat], MAT_NAMES[mat])
    nsh = NSH if mat == MAT_GLASS else 0
    nst = nstretch(mat)
    hdr = struct.unpack_from("<HHHBBBBBB", part, 4)
    results.append(("%s header: BZB2, 64 frames, 16 rows, 5 bytes, material %d, %d squash, %d shatter, %d shadow "
                    "rows, %d stretch, %d bytes" % (name, mat, NSQ, nsh, SHD_ROWS, nst, B2_SIZE[mat]),
                    part[:4] == b"BZB2" and hdr == (NFRAMES, D, RB, mat, NSQ, nsh, SHD_ROWS, nst, 0)
                    and len(part) == B2_SIZE[mat]))
    ok_mask = stray = 0
    good = True
    ring = True
    masks = [[part[B2_MASKOFF + (s * D + r) * RB:B2_MASKOFF + (s * D + r + 1) * RB] for r in range(D)]
             for s in range(SHIFTS)]
    # the mask: the same disc at every shift (glass: its checker interior kept too)
    sil = material_frame(mat, 0, 0)
    for s in range(SHIFTS):
        for r in range(D):
            want = cga_bytes([3 if c is None or c == SEE else 0 for c in _ball_row(sil[r], s)])
            if masks[s][r] != want:
                good = False
    results.append(("%s mask: the disc at every shift, %s" % (
        name, "its interior a checker the course shows through" if mat == MAT_GLASS else "solid inside"), good))
    # the roll frames: the look, at the frame's own shift; a black outer ring
    good = True
    for f in range(NFRAMES):
        s = f & 3
        fr = material_frame(mat, f & 7, f >> 3)
        for r in range(D):
            o = B2_FRMOFF + (f * D + r) * RB
            got = _decode_pix(masks[s][r], part[o:o + RB])
            for j, v in enumerate(got):
                if isinstance(v, tuple):
                    good = False
                x = j - s
                c = fr[r][x] if 0 <= x < D else None
                want = None if c is None or c == SEE else c
                if v != want:
                    good = False
                if v is None:
                    stray += bin((part[o + (j >> 2)] >> (6 - 2 * (j & 3))) & 3).count("1")
                if 0 <= x < D and _rim(x, r) and v != BLK:
                    ring = False
    results.append(("%s roll frames: frame f decodes to the %s look at shift f & 3; no frame bit under a kept "
                    "pixel (%d stray)" % (name, MAT_NAMES[mat], stray), good and stray == 0))
    # squash and shatter: parity copies identical, frame bits only under the
    # entry's own clear mask, a black outer ring
    entries = [(B2_SQOFF, NSQ, "squash"), (B2_SHAOFF, nsh, "shatter")]
    same = True
    for base, n, what in entries:
        for k in range(n):
            for s in range(SHIFTS):
                e0 = base + ((k * SHIFTS + s) * 2 + 0) * ENT
                e1 = e0 + ENT
                if part[e0:e0 + ENT] != part[e1:e1 + ENT]:
                    same = False
                for r in range(D):
                    got = _decode_pix(part[e0 + r * RB:e0 + r * RB + RB], part[e0 + D * RB + r * RB:e0 + D * RB + r * RB + RB])
                    if any(isinstance(v, tuple) for v in got):
                        same = False
    for k in range(NSQ):
        fr = squash_frame(mat, k)
        e0 = B2_SQOFF + ((k * SHIFTS + 0) * 2) * ENT
        for r in range(D):
            got = _decode_pix(part[e0 + r * RB:e0 + r * RB + RB], part[e0 + D * RB + r * RB:e0 + D * RB + r * RB + RB])
            for x in range(D):
                c = fr[r][x]
                if c is not None and c != SEE and any(
                        not (0 <= x + dx < D and 0 <= r + dy < D) or fr[r + dy][x + dx] is None
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) and got[x] != BLK:
                    ring = False
    for k in range(nsh):                            # every shatter entry, every shift: a
        for s in range(SHIFTS):                     # kept pixel beside a clear one is BLACK
            e0 = B2_SHAOFF + ((k * SHIFTS + s) * 2) * ENT
            got = [_decode_pix(part[e0 + r * RB:e0 + r * RB + RB], part[e0 + D * RB + r * RB:e0 + D * RB + r * RB + RB])
                   for r in range(D)]
            pix = shatter_frame(k)                  # the piece's shape (SEE is a piece's
            shp = [_slots({x: c for (x, y), c in pix.items() if y == r}, s) for r in range(D)]
            for r in range(D):                      # see-through interior, not its outside)
                for j, c in enumerate(shp[r]):
                    if c is not None and got[r][j] != BLK and any(
                            not (0 <= j + dx < RB * 4 and 0 <= r + dy < D) or shp[r + dy][j + dx] is None
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        ring = False
    results.append(("%s squash%s: the two line-parity copies of every entry identical, mask and frame consistent"
                    % (name, " and shatter" if nsh else ""), same))
    results.append(("%s: a BLACK outer ring on every roll and squash frame%s" % (
        name, " and every shatter entry (all frames, shifts and parities)" if nsh else ""), ring))
    # the shadow: AND only, the world checker inside the ellipse
    good = True
    for p in range(2):
        for s in range(SHIFTS):
            o = B2_SHDOFF + (p * SHIFTS + s) * SHD_ROWS * RB
            for r in range(SHD_ROWS):
                for j in range(RB * 4):
                    m = (part[o + r * RB + (j >> 2)] >> (6 - 2 * (j & 3))) & 3
                    x = j - s
                    want = 0 if (0 <= x < D and _shadow_in(x, r) and (j + p + r) & 1 == 0) else 3
                    if m != want:
                        good = False
    results.append(("%s shadow masks: a 16 x 6 ellipse clearing the world checker (x + y even) at each parity "
                    "and shift" % name, good))
    if nst:
        _check_stretch(mat, part, results, name)


def _check_stretch(mat, part, results, name):
    """the boost's STRETCH entry (SPEC.md 128.16.4.4, wave 6): at every shift
    and line parity the mask is the stretch's 12 x 16 ellipse, the frame
    decodes to stretch_frame() there, no frame bit lies under a kept pixel,
    the two parity copies are identical and the outer ring is black"""
    fr = stretch_frame(mat)
    good = ring = True
    stray = 0
    for s in range(SHIFTS):
        e0 = B2_STROFF + (s * 2) * ENT
        if part[e0:e0 + ENT] != part[e0 + ENT:e0 + 2 * ENT]:
            good = False
        for p in range(2):
            e = e0 + p * ENT
            for r in range(D):
                mrow = part[e + r * RB:e + r * RB + RB]
                frow = part[e + D * RB + r * RB:e + D * RB + r * RB + RB]
                got = _decode_pix(mrow, frow)
                for j, v in enumerate(got):
                    x = j - s
                    c = fr[r][x] if 0 <= x < D else None
                    want = None if c is None or c == SEE else c
                    if v != want:
                        good = False
                    if v is None and (frow[j >> 2] >> (6 - 2 * (j & 3))) & 3:
                        stray += 1
                    if (c is not None and c != SEE and v != BLK and any(
                            not (0 <= x + dx < D and 0 <= r + dy < D) or fr[r + dy][x + dx] is None
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))):
                        ring = False
    wide = max(sum(1 for c in row if c is not None) for row in fr)
    tall = sum(1 for row in fr if any(c is not None for c in row))
    results.append(("%s stretch: a %d x %d ellipse (12 x 16); mask and frame consistent at every shift and parity, "
                    "the copies identical, a black outer ring; no frame bit under a kept pixel (%d stray)"
                    % (name, wide, tall, stray), good and ring and stray == 0 and (wide, tall) == (ST_W, D)))


def selfcheck():
    results = []
    a_files, a_texts = compile_all()
    _ball_frame.cache_clear()
    material_frame.cache_clear()
    b_files, b_texts = compile_all()
    same = all(a_files[k] == b_files[k] for k in a_files) and a_texts == b_texts
    results.append(("two runs byte-identical (%s, bzconst.inc)" % ", ".join(sorted(a_files)), same))
    print("  %s  (wave 1's BZB1: 5,456 a card)" % "  ".join("%s %d" % (k, len(a_files[k])) for k in BALL_FILES))
    for m in range(3):
        _check_ball2(m, a_files[BALL_FILES[m]], results)
    # the Hercules table, and the translation through it
    t = htab()
    hp = all(t[256 * p + b] == sum(herc_pair((b >> (6 - 2 * j)) & 3, p, j) << (6 - 2 * j) for j in range(4))
             for p in range(2) for b in range(256))
    results.append(("htab(): 512 bytes, equal to herc_pair over all 256 bytes and both line parities", hp and len(t) == 512))
    w1h = build_ball_part(True)
    rub = herc_translate_ball(a_files["BZBALR.BIN"])
    eq = rub[B2_FRMOFF:B2_SQOFF] == w1h[BAL_FRMOFF:]
    results.append(("the RUBBER part translated through htab() equals wave 1's Hercules ball part, byte for byte "
                    "in its 64 roll frames", eq))
    ring_h = True
    for m in range(3):
        hpart = herc_translate_ball(a_files[BALL_FILES[m]])
        for f in range(NFRAMES):
            for r in range(D):
                o = B2_FRMOFF + (f * D + r) * RB
                for x in range(D):
                    if _rim(x, r):
                        j = x + (f & 3)
                        if (hpart[o + (j >> 2)] >> (6 - 2 * (j & 3))) & 3:
                            ring_h = False
    results.append(("the black outer ring survives the Hercules translation (00 on both cards), every material",
                    ring_h))
    # wave 1's reference part (kept for the assert above)
    _check_ball(build_ball_part(False), False, results)
    _check_ball(w1h, True, results)
    bad, mids, tens, ones = _check_herc_ball_checker(w1h)
    results.append(("wave 1's Hercules ball (the reference): mid pixels take the course's checker (%d mid: %d 10, "
                    "%d 01; %d wrong)" % (mids, tens, ones, bad), bad == 0 and tens > 0 and ones > 0))
    differ = all(material_frame(m, fx, fy) != material_frame(m, (fx + 1) % 8, fy) and
                 material_frame(m, fx, fy) != material_frame(m, fx, (fy + 1) % 8)
                 for m in range(3) for fy in range(8) for fx in range(8))
    results.append(("every material's every roll frame differs from its x and y phase neighbours (it turns)", differ))
    # negative controls: a guard nobody has seen fire is a guard nobody knows is alive
    tb = bytearray(t)
    used = a_files["BZBALR.BIN"][B2_FRMOFF + 3 * D * RB + 6 * RB + 2]   # a byte frame 3's row 6 holds
    tb[256 * ((0 + 6) & 1) + used] ^= 0x0C
    hp2 = all(tb[256 * p + b] == sum(herc_pair((b >> (6 - 2 * j)) & 3, p, j) << (6 - 2 * j) for j in range(4))
              for p in range(2) for b in range(256))
    rub2 = herc_translate_ball(a_files["BZBALR.BIN"], bytes(tb))
    results.append(("negative control: one htab() entry flipped fails the table check and the translated rubber part",
                    not hp2 and rub2[B2_FRMOFF:B2_SQOFF] != w1h[BAL_FRMOFF:]))
    gl = bytearray(a_files["BZBALG.BIN"])
    for s in range(SHIFTS):
        for r in range(D):
            o = B2_MASKOFF + (s * D + r) * RB
            gl[o:o + RB] = cga_bytes([3 if c is None else 0 for c in _ball_row(material_frame(MAT_RUBBER, 0, 0)[r], s)])
    sub = []
    _check_ball2(MAT_GLASS, bytes(gl), sub, "glass, interior mask SOLID")
    results.append(("negative control: glass's interior mask made solid is caught", not all(g for _, g in sub)))
    sq = bytearray(a_files["BZBALS.BIN"])
    sq[B2_SQOFF + ENT + D * RB + 40] ^= 0x30
    sub = []
    _check_ball2(MAT_STEEL, bytes(sq), sub, "steel, a squash parity copy altered")
    results.append(("negative control: a squash parity copy altered on the CGA is caught", not all(g for _, g in sub)))
    st = bytearray(a_files["BZBALS.BIN"])
    f, r = 9, 0
    x = next(x for x in range(D) if _rim(x, r))
    j = x + (f & 3)
    o = B2_FRMOFF + (f * D + r) * RB + (j >> 2)
    st[o] |= CYN << (6 - 2 * (j & 3))
    sub = []
    _check_ball2(MAT_STEEL, bytes(st), sub, "steel, one rim pixel cyan")
    results.append(("negative control: one rim pixel of steel made cyan is caught", not all(g for _, g in sub)))
    gs = bytearray(a_files["BZBALG.BIN"])               # a burst shard's ring pixel made cyan
    e0 = B2_SHAOFF + ((1 * SHIFTS + 0) * 2) * ENT
    hit = None
    for r in range(D):
        got = _decode_pix(gs[e0 + r * RB:e0 + r * RB + RB], gs[e0 + D * RB + r * RB:e0 + D * RB + r * RB + RB])
        hit = next((j for j, v in enumerate(got) if v == BLK), None)
        if hit is not None:
            gs[e0 + D * RB + r * RB + (hit >> 2)] |= CYN << (6 - 2 * (hit & 3))
            gs[e0 + ENT + D * RB + r * RB + (hit >> 2)] |= CYN << (6 - 2 * (hit & 3))
            break
    sub = []
    _check_ball2(MAT_GLASS, bytes(gs), sub, "glass, a burst shard's ring pixel cyan")
    results.append(("negative control: one ring pixel of glass's burst frame made cyan is caught (at the ring check)",
                    hit is not None and [w for w, g in sub if not g] == [w for w, _ in sub if "outer ring" in w]))
    nz = all(a_files[BALL_FILES[m]][14] == 0 for m in (MAT_STEEL, MAT_GLASS)) and a_files["BZBALR.BIN"][14] == NST
    results.append(("BZB2 +14: rubber's stretch count %d, steel's and glass's 0" % NST, nz))
    # wave 9 (128.25.5): the stored form BZB3 and the guest's generator
    st3 = {m: build_ball3(m) for m in range(3)}
    results.append(("BZB3: the host model of bz_ballgen expands every stored part to build_ball2's, every byte",
                    all(model_ball3(st3[m]) == a_files[BALL_FILES[m]] for m in range(3))))
    import bzballchk
    emu = bzballchk.check()
    if emu is None:
        print("  SKIP bz_ballgen under an emulated 8086: unicorn is not importable here")
    else:
        results.append(("bz_ballgen, run under an emulated 8086 IN PLACE on the stored part, equals build_ball2 "
                        "for rubber, steel and glass, every byte (scratch pre-filled with junk), AX ES DS SP DF kept, "
                        "no write outside the part, bz_boxbuf and the stack", all(ok for _, ok, _ in emu)))
        bad = bytearray(st3[MAT_STEEL])
        bad[BG_BLK + BG_SQ0 + 5] += 1                   # one row of squash 0's ellipse widened
        code = bzballchk.assemble()
        results.append(("negative control: a stored ellipse row changed makes the generated part differ",
                        bzballchk.run(code, bytes(bad)) != a_files["BZBALS.BIN"]))
        # ...and the ROUTINE broken: the mask table's field no longer steps to its next byte
        broke = bzballchk.assemble(patch=("    adc di, 0                   ; the field wrapped to the next byte\n", ""))
        results.append(("negative control: bz_ballgen with its mask table's byte step removed differs, every material",
                        all(bzballchk.run(broke, st3[m]) != a_files[BALL_FILES[m]] for m in range(3))))
        # ...and the ROUTINE handing back the ball's selector in ES (9f73af482's fix: the
        # ES a later POP takes must not be a part's, 128.14.26 item 2)
        pr = {}
        bzballchk.run(bzballchk.assemble(patch=("    pop es\n    pop ax\n    ret", "    pop ax\n    pop ax\n    ret")),
                      st3[MAT_STEEL], probe=pr)
        results.append(("negative control: bz_ballgen returning without the caller's ES is caught", not pr["kept"]))
        # ...and the stored rank coding broken: one row's threshold one class higher
        bad = bytearray(st3[MAT_RUBBER])
        j = next(j for j in range(128) if 0 < bad[BG_BLK + BG_YE + j] < (bad[BG_BLK + BG_NP] - 2) * BG_PSTR)
        bad[BG_BLK + BG_YE + j] += BG_PSTR
        results.append(("negative control: one rank-coded threshold raised a class makes the generated part differ",
                        bzballchk.run(code, bytes(bad)) != a_files["BZBALR.BIN"]))
    rs = bytearray(a_files["BZBALR.BIN"])              # one stretch frame pixel flipped
    e = B2_STROFF + ((2 * 2) + 1) * ENT                # against its mask: shift 2, parity 1,
    r = 0                                              # row 0's first KEPT slot gains a frame bit
    j = next(j for j in range(RB * 4) if (rs[e + r * RB + (j >> 2)] >> (6 - 2 * (j & 3))) & 3 == 3)
    rs[e + D * RB + r * RB + (j >> 2)] |= WHT << (6 - 2 * (j & 3))
    sub = []
    _check_ball2(MAT_RUBBER, bytes(rs), sub, "rubber, one stretch frame pixel flipped")
    results.append(("negative control: one stretch frame pixel flipped against its mask is caught (at the stretch "
                    "check)", [w for w, g in sub if not g] == [w for w, _ in sub if " stretch:" in w]))
    # wave 8R (128.22.8): the crystal material and the pad overlay
    c1 = crystal_tile_pixmap()
    c2 = crystal_tile_pixmap()
    ins = sum(1 for r in c1 for c in r if c is not None)
    results.append(("crystal: tile top deterministic, ink 0 - 3 only, a 32 x 16 diamond (%d px), the lit colour on "
                    "a quarter of it" % ins,
                    c1 == c2 and all(c is None or 0 <= c <= 3 for r in c1 for c in r)
                    and 200 < ins <= 256 and sum(c == 3 for r in c1 for c in r) * 4 >= ins))
    results.append(("crystal: sides deterministic and dark (colour 3 never)",
                    all(crystal_side_ink(f, k, j) in (0, 2) for f in ("sw", "se") for k in range(16) for j in range(12))))
    pads = [pad_overlay(p) for p in range(PAD_POSES)]
    results.append(("pad overlay: %d poses, deterministic, pairwise different, inside the tile, one ring each"
                    % PAD_POSES,
                    pads == [pad_overlay(p) for p in range(PAD_POSES)]
                    and len({tuple(sorted(p.items())) for p in pads}) == PAD_POSES
                    and all(crystal_inside(u, v) and 0 <= c <= 3 for p in pads for (u, v), c in p.items())
                    and all(any(c == 3 for c in p.values()) for p in pads)))
    f = crystal_ink(2, 1, 40, 12, 1)                # (2, 1) at 1 unit: centre (40 + 16, 12 + 24 + 8 - 8)
    results.append(("crystal_ink: a tile's centre lands at (16 (wx - wy) + x0, 8 (wx + wy) + 8 - 8 z0 + y0)",
                    f(56, 36) == crystal_top_ink(0, 0) and f(56 - 17, 36) is None and f(56 - 15, 36) is not None))
    try:                                            # the committed icons and pads equal tools/bbicons.py's output
        import bbicons
        ic = bbicons.check() == 0
    except ImportError:
        ic = False
    results.append(("icons and pads: apps/bonanza/courses/icons/*.bba and pads/*.bba are what tools/bbicons.py "
                    "writes (its --check)", ic))
    ht = htab()
    mono = all(herc_pair(c, v, u) == 3 for v, r in enumerate(c1) for u, c in enumerate(r) if c == 3)
    lit = sum(1 for r in c1 for c in r if c == 3)
    results.append(("crystal on the Hercules: the lit table and the dark edge both survive htab() (lit %d px, "
                    "black rim ring in the pad)" % lit, mono and lit > 40 and any(c == 0 for p in pads for c in p.values())
                    and ht[255] == 0xFF))
    ok = True
    for what, good in results:
        print("  %-4s %s" % ("ok" if good else "FAIL", what))
        ok = ok and good
    print("bonanza_assets selfcheck: %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


# =============================================================================
# wave 8R (SPEC.md 128.22.8): the pathway's LOOK - the CRYSTAL route material and
# the GLOWING PAD overlay.  PROVISIONAL, the owner's to refine; pure functions of
# tile-local coordinates, so a course tool paints them wherever a tile lands.
#
# TILE-LOCAL: a floor tile's top is the 32 x 16 diamond centred on (cx, cy) =
# (16 (wx - wy) + x0, 8 (wx + wy) + 8 - 8 h); u = x - cx (-16 .. 15) and
# v = y - cy (-8 .. 7) are a picture pixel's offsets from it, so every function
# below takes (u, v) and needs no tile, origin or height.  Ink is a CGA colour
# index: 0 black, 1 / 2 / 3 the palette's (palette 1: cyan, magenta, white;
# palette 0: green, red, brown), or None (transparent, an overlay's).  The
# Hercules gets them through htab() like every other pixel (128.11.3): 3 white,
# 0 black, 1 and 2 the checker, so the LIT facets (3) and the dark edge (0) carry
# the look there and the mid facets (1, 2) read as grey.
# =============================================================================

CRYSTAL = "crystal"
PAD_POSES = 4                 # 0 OPEN (glowing), 1 DONE, 2 SILVER, 3 GOLD (SPEC.md 128.22.2)
PAD_POSE_NAMES = ("open", "done", "silver", "gold")
TILE_W, TILE_H = 32, 16


def _diamond(u, v):
    """0 at the centre .. 1 at the edge, for the pixel (u, v)'s centre"""
    return abs(u + 0.5) / 16.0 + abs(v + 0.5) / 8.0


def _edge_px(u, v):
    """about how many pixels in from the diamond's edge (perpendicular; a
    negative number is outside): the diamond's edge is 7.15 px a unit of d"""
    return (1.0 - _diamond(u, v)) * 7.155


def crystal_inside(u, v):
    return _diamond(u, v) <= 1.0


def crystal_top_ink(u, v):
    """the crystal rail's TOP (None outside the diamond): a lit gem table
    (colour 3) in the middle, four facets round it split on the diamond's axes
    - the NW one lit, the NE and SW mid, the SE dark - and a lighter rim, with a
    bevel step.  The renderer's own outline draws the black edge;
    pixels on the very rim are the mid colour so it survives either way"""
    d = _diamond(u, v)
    if d > 1.0:
        return None
    x, y = u + 0.5, v + 0.5
    e = _edge_px(u, v)
    if e < 1.0:
        return 1                                    # the rim
    if d < 0.36:                                    # the table
        return 3
    nw, ne, sw = (x < 0 and y < 0), (x >= 0 and y < 0), (x < 0 and y >= 0)
    if abs(x) < 0.6 or abs(y) < 0.6:                # the facet seams, on the axes
        return 1
    if d < 0.62:                                    # the bevel: a step lighter than the facet
        return 3 if (nw or ne or sw) else 1
    return 3 if nw else 1 if (ne or sw) else 2


def crystal_side_ink(face, k, j):
    """a raised rail's SIDE (a wall of the route over the void): face 'sw' or
    'se', k the column across the face (0 at its left edge), j the line down
    from the face's top edge at that column (0 the first).  Dark: black with
    the facets' glints (colour 2) every fourth column on 'sw', and a black
    'se' lit only at its seams, so on the Hercules the edge is a dark band"""
    if face == "sw":
        if j == 0:
            return 2
        return 2 if (k >> 2) & 1 == 0 and j & 1 == 0 else 0
    if j == 0:
        return 0
    return 2 if k & 3 == 1 and j < 6 else 0


def crystal_ink(wx, wy, x0, y0, z0=0):
    """crystal_top_ink as a picture-pixel function for the flat tile (wx, wy)
    at height z0 UNITS (8 px a unit, SPEC.md 128.10.2 - a bbcourse Tile's z0 is
    HALF units, so pass t.z0 / 2), in a picture whose origin is x0 across and
    Y0 = y0 down, bbcourse's convention (picture y = the Y0 = 0 line + y0, as
    render() / _top_fn() / clock_face_geom() have it): ink(x, y) -> index or None"""
    cx = 16 * (wx - wy) + x0
    cy = 8 * (wx + wy) + 8 - 8 * z0 + y0
    return lambda x, y: crystal_top_ink(x - cx, y - cy)


def crystal_tile_pixmap():
    """the 32 x 16 top as rows of ink (None outside): the committed sample"""
    return [[crystal_top_ink(u, v) for u in range(-16, 16)] for v in range(-8, 8)]


def pad_overlay(pose):
    """the glowing pad over a pad's cell: {(u, v): ink} in tile-local
    coordinates, everything else transparent (the crystal shows through the
    ring's inside).  A ring of the light colour round the cell:
        0 OPEN    a bright ring (3), a black gap, a mid glow (1) inside it
        1 DONE    a dim ring (2) one pixel wide on a black gap, the two end pips lit
        2 SILVER  the ring a silver sparkle (3 / 1 alternating) on a black gap
        3 GOLD    a thick ring (3), a mid ring (2), a black gap, the two end pips lit
    (the black gap keeps the ring apart from the crystal's lit table on the Hercules)"""
    if not 0 <= pose < PAD_POSES:
        raise AssetError("pad pose %d outside 0 - %d" % (pose, PAD_POSES - 1))
    out = {}
    for v in range(-8, 8):
        for u in range(-16, 16):
            if _diamond(u, v) > 1.0:
                continue
            e = _edge_px(u, v)
            ink = None
            if pose == 0:
                ink = 3 if e < 1.7 else 0 if e < 3.2 else 1 if e < 4.4 else None
            elif pose == 1:
                ink = 2 if e < 1.2 else 0 if e < 2.6 else None
            elif pose == 2:
                ink = (3 if (u + v) & 1 else 1) if e < 1.7 else 0 if e < 3.0 else None
            else:
                ink = 3 if e < 2.4 else 2 if e < 3.4 else 0 if e < 4.6 else None
            if pose in (1, 3) and abs(u + 0.5) < 2.0 and v < 0 and e < 4.2 and v + 0.5 < -4.0:
                ink = 3
            if pose in (1, 3) and abs(u + 0.5) < 2.0 and v >= 0 and e < 4.2 and v + 0.5 > 3.0:
                ink = 3
            if ink is not None:
                out[(u, v)] = ink
    return out


def pad_rows(pose):
    """the overlay as a 16 x 32 grid of ink / None"""
    p = pad_overlay(pose)
    return [[p.get((u, v)) for u in range(-16, 16)] for v in range(-8, 8)]


def bba_text(rows, frames=None, comment=None):
    """rows of ink / None -> 128.23.2's text: '.' transparent, '0'..'3', one
    line a pixel row, `#` comments; a `# frames K` line for an icon"""
    out = []
    if comment:
        out.extend("# " + c for c in comment.split("\n"))
    if frames is not None:
        out.append("# frames %d" % frames)
    for r in rows:
        out.append("".join("." if c is None else str(c) for c in r))
    return "\n".join(out) + "\n"


# =============================================================================
# --png: previews (Pillow, optional)
# =============================================================================

GROUNDS = ("cyan tile", "white tile", "ramp checker", "magenta face")


def _ground(g, x, y):
    if g == 0:
        return CYN
    if g == 1:
        return WHT
    if g == 2:
        return CYN if ((x >> 1) + (y >> 1)) & 1 else WHT
    return MAG if (x + y) & 1 == 0 else BLK


def previews(out):
    """every material's roll frames as a sheet, and the look step's required
    set (SPEC.md 128.11.9.1): each ball - roll, squash, shatter - and its
    shadow composited over a cyan tile, a white tile, a ramp's checker and a
    magenta face, on the CGA and (through the guest's translation) the
    Hercules"""
    try:
        from PIL import Image
    except ImportError:
        print("bonanza_assets: --png needs Pillow; skipped", file=sys.stderr)
        return 1
    os.makedirs(out, exist_ok=True)
    gap = 4
    for m in range(3):
        sheet = Image.new("RGB", (P * (D + gap) + gap, P * (D + gap) + gap), (40, 40, 40))
        sp = sheet.load()
        for f in range(NFRAMES):
            ox, oy = gap + (f & 7) * (D + gap), gap + (f >> 3) * (D + gap)
            for y, row in enumerate(material_frame(m, f & 7, f >> 3)):
                for x, c in enumerate(row):
                    if c is not None:
                        sp[ox + x, oy + y] = CGA1[c] if c != SEE else (90, 90, 90)
        sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST).save(
            os.path.join(out, "ball-%s.png" % MAT_NAMES[m]))
    # the composites: a 28 x 40 cell per (ground, sprite), the CGA and the Hercules
    files, _ = compile_all()
    for herc in (0, 1):
        cw, ch = 28, 40
        sprites = (["roll"] + ["squash%d" % k for k in range(NSQ)] + ["shatter%d" % k for k in range(NSH)]
                   + ["stretch%d" % k for k in range(NST)])
        img = Image.new("RGB", ((cw * len(GROUNDS)) * (2 if herc else 1), ch * 3 * len(sprites)), (40, 40, 40))
        ip = img.load()
        for m in range(3):
            part = files[BALL_FILES[m]]
            if herc:
                part = herc_translate_ball(part)
            for si, spn in enumerate(sprites):
                if (spn.startswith("shatter") and m != MAT_GLASS) or (spn.startswith("stretch") and not nstretch(m)):
                    continue
                for g in range(len(GROUNDS)):
                    ox, oy = g * cw, (m * len(sprites) + si) * ch
                    px, py = ox + 4 + (si & 3), oy + 2
                    s = px & 3
                    # the picture: the ground's game pixels, then the shadow, then the sprite
                    pic = {}
                    for y in range(ch):
                        for x in range(cw):
                            pic[(ox + x, oy + y)] = _ground(g, ox + x, oy + y)
                    spy = py + 16 + 4
                    so = B2_SHDOFF + ((spy & 1) * SHIFTS + s) * SHD_ROWS * RB
                    for r in range(SHD_ROWS):
                        for j in range(RB * 4):
                            if not (part[so + r * RB + (j >> 2)] >> (6 - 2 * (j & 3))) & 3:
                                pic[((px & ~3) + j, spy + r)] = BLK
                    if spn == "roll":
                        f = ((py & 7) << 3) | (px & 7)
                        mo = B2_MASKOFF + s * D * RB
                        fo = B2_FRMOFF + f * D * RB
                    else:
                        base = B2_SQOFF if spn.startswith("squash") else B2_SHAOFF   # (the stretch's too)
                        k = int(spn[-1])
                        e = base + ((k * SHIFTS + s) * 2 + (py & 1)) * ENT
                        mo, fo = e, e + D * RB
                    cell = {}
                    for r in range(D):
                        for j in range(RB * 4):
                            mm = (part[mo + r * RB + (j >> 2)] >> (6 - 2 * (j & 3))) & 3
                            vv = (part[fo + r * RB + (j >> 2)] >> (6 - 2 * (j & 3))) & 3
                            if mm == 0:
                                cell[((px & ~3) + j, py + r)] = ("card", vv) if herc else vv
                    for (x, y), c in pic.items():
                        v = cell.get((x, y), c)
                        if herc:
                            pr = v[1] if isinstance(v, tuple) else herc_pair(v, y, x)
                            for b in range(2):
                                if 0 <= 2 * x + b - 0 < img.width:
                                    on = (pr >> (1 - b)) & 1
                                    ip[2 * x + b, y] = (255, 255, 255) if on else (0, 0, 0)
                        else:
                            ip[x, y] = CGA1[v]
        img = img.resize((img.width * (2 if herc else 4), img.height * 4), Image.NEAREST)
        img.save(os.path.join(out, "balls-%s.png" % ("herc" if herc else "cga")))
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
            files = write_out(a.out)
            print("bonanza_assets: %s" % ", ".join("%s %d" % (k, len(files[k])) for k in sorted(files)))
        if a.png:
            rc |= previews(a.png)
        return rc
    except AssetError as e:
        print("bonanza_assets: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
