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
frames (0 or 4), +13 shadow rows (6), +14 two zero bytes; +16 the masks (4
shifts x 16 rows x 5, the material's silhouette, a SET bit keeps); +336 the
64 roll frames, frame f at shift f & 3; +5,456 the squash entries (2 x 4
shifts x 2 line parities x (mask 80 + frame 80)); +8,016 the shadow masks (2
parities x 4 shifts x 6 rows x 5, AND only); +8,256 glass's shatter entries
(4 x 4 x 2 x 160).  8,256 bytes, glass 13,376.

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
ENT = 2 * D * RB              # a squash or shatter entry: mask 80 + frame 80
B2_MASKOFF = HDR                                   # 16
B2_FRMOFF = B2_MASKOFF + SHIFTS * D * RB           # 336
B2_SQOFF = B2_FRMOFF + NFRAMES * D * RB            # 5,456
B2_SHDOFF = B2_SQOFF + NSQ * SHIFTS * 2 * ENT      # 8,016
B2_SHAOFF = B2_SHDOFF + 2 * SHIFTS * SHD_ROWS * RB  # 8,256
B2_SIZE = (B2_SHAOFF, B2_SHAOFF, B2_SHAOFF + NSH * SHIFTS * 2 * ENT)   # 8,256, 8,256, 13,376


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
    hdr = b"BZB2" + struct.pack("<HHHBBBBH", NFRAMES, D, RB, mat, NSQ, nsh, SHD_ROWS, 0)
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
    squash or shatter entry of parity copy p, row r, through (p + r) & 1;
    masks and the shadow untouched (a mask is the same bytes on both cards)"""
    t = table if table is not None else htab()
    b = bytearray(part)
    nsh = b[12]
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
        "BZ_BAL_SIZE     equ %d      ; rubber and steel" % B2_SIZE[0],
        "BZ_BAL_SIZEG    equ %d     ; glass" % B2_SIZE[2],
        "",
    ]
    return "\n".join(lines)


def compile_all():
    files = {BALL_FILES[m]: build_ball2(m) for m in range(3)}
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
    files, texts = compile_all()
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
    hdr = struct.unpack_from("<HHHBBBBH", part, 4)
    results.append(("%s header: BZB2, 64 frames, 16 rows, 5 bytes, material %d, %d squash, %d shatter, %d shadow "
                    "rows, %d bytes" % (name, mat, NSQ, nsh, SHD_ROWS, B2_SIZE[mat]),
                    part[:4] == b"BZB2" and hdr == (NFRAMES, D, RB, mat, NSQ, nsh, SHD_ROWS, 0)
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
    ok = True
    for what, good in results:
        print("  %-4s %s" % ("ok" if good else "FAIL", what))
        ok = ok and good
    print("bonanza_assets selfcheck: %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


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
        sprites = ["roll"] + ["squash%d" % k for k in range(NSQ)] + ["shatter%d" % k for k in range(NSH)]
        img = Image.new("RGB", ((cw * len(GROUNDS)) * (2 if herc else 1), ch * 3 * len(sprites)), (40, 40, 40))
        ip = img.load()
        for m in range(3):
            part = files[BALL_FILES[m]]
            if herc:
                part = herc_translate_ball(part)
            for si, spn in enumerate(sprites):
                if spn.startswith("shatter") and m != MAT_GLASS:
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
                        base = B2_SQOFF if spn.startswith("squash") else B2_SHAOFF
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
