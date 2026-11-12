#!/usr/bin/env python3
"""BONANZA (Bounce Bonanza) ball generator and the shared encoders
(SPEC.md 128.3, 128.10.5.3).

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

Outputs, in the -o directory (the two ball PARTS of BONANZA.O88, then NASM):
    BZBALC.BIN    the ball, CGA
    BZBALH.BIN    the ball, Hercules: the same layout in pair pixels
    bzconst.inc   the ball part's layout
    .bz-art       stamp: sha256 of this tool (make's rebuild key), written FIRST

Ball part, BZB1 (SPEC.md 128.10.5.3):
    +0 'BZB1'  +4 word frames (64)  +6 word rows (16)  +8 word bytes a row (5)
    +10 six zero bytes
    +16 masks: 4 shifts x 16 rows x 5 bytes, shift-major; a SET bit keeps the
        background (as BZB0's)
    +336 frames: 64 x 16 rows x 5 bytes, ANDed with ~mask.  Frame f =
        (py & 7) * 8 + (px & 7) is stored at shift f & 3 - which is px & 3, the
        only shift it is ever drawn at - so its byte is 80 (f - s) past the
        mask byte of the same row and slot, + (336 - 16).
    5,456 bytes, against BZB0's 20,816 (4 shifts x 64 frames).
    Hercules ball pixels: 0 -> 00, 3 -> 11, 1 and 2 -> the COURSE's checker
    (SPEC.md 128.9 item 7): 10 where (line + column) is even, 01 where odd,
    at the WORLD game pixel the ball's pixel lands on.  Ball pixel (x, r) of a
    ball at (px, py) is world column px + x and line py + r; f carries px & 7
    and py & 7, so the parity is (fx + x + fy + r) & 1 - fixed per frame, no
    run-time cost.  In shift s's 5-byte row slot j holds ball pixel x = j - s
    (the row starts at world column px & ~3, and s = px & 3), so slot j's
    column is fx - s + j.

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


def _paras(n):
    return (n + 15) // 16


def emit_const():
    lines = [
        "; bzconst.inc - GENERATED by tools/bonanza_assets.py (SPEC.md 128.3, 128.10.5.3).",
        "; Do not edit: change the tool and rebuild.  The ball part's layout; the",
        "; courses' are tools/bbcourse.py's bzcourse.inc and their parts' headers.",
        "",
        "; the ball part (BZBALC.BIN / BZBALH.BIN, BZB1): identical layout and size",
        "BZ_BAL_FRAMES   equ %d" % NFRAMES,
        "BZ_BAL_SHIFTS   equ %d" % SHIFTS,
        "BZ_BAL_ROWS     equ %d" % D,
        "BZ_BAL_RB       equ %d         ; bytes a row" % RB,
        "BZ_BAL_D        equ %d        ; the ball's diameter, game pixels" % D,
        "BZ_BAL_MASKOFF  equ %d        ; masks: shift x row x byte, SET keeps" % BAL_MASKOFF,
        "BZ_BAL_MASKSH   equ %d        ; bytes of mask a shift" % (D * RB),
        "BZ_BAL_FRMOFF   equ %d       ; frames: frame x row x byte, frame f at shift f & 3" % BAL_FRMOFF,
        "BZ_BAL_FRMB     equ %d        ; bytes a frame" % (D * RB),
        "BZ_BAL_SIZE     equ %d" % BAL_SIZE,
        "BZ_BAL_PARAS    equ %d" % _paras(BAL_SIZE),
        "",
    ]
    return "\n".join(lines)


def compile_all():
    balc = build_ball_part(False)
    balh = build_ball_part(True)
    files = {"BZBALC.BIN": balc, "BZBALH.BIN": balh}
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


def selfcheck():
    results = []
    a_files, a_texts = compile_all()
    _ball_frame.cache_clear()
    b_files, b_texts = compile_all()
    same = all(a_files[k] == b_files[k] for k in a_files) and a_texts == b_texts
    results.append(("two runs byte-identical (%s, bzconst.inc)" % ", ".join(sorted(a_files)), same))
    print("  BZBALC.BIN %d  BZBALH.BIN %d  (BZB0 was 20,816)" % (
        len(a_files["BZBALC.BIN"]), len(a_files["BZBALH.BIN"])))
    _check_ball(a_files["BZBALC.BIN"], False, results)
    _check_ball(a_files["BZBALH.BIN"], True, results)
    bad, mids, tens, ones = _check_herc_ball_checker(a_files["BZBALH.BIN"])
    results.append(("BZBALH mid pixels take the course's checker at the ball's world position, "
                    "every frame (%d mid: %d 10, %d 01; %d wrong)" % (mids, tens, ones, bad),
                    bad == 0 and tens > 0 and ones > 0 and tens + ones == mids))
    hp = all(ball_herc_pairs(f)[r][x] == (None if c is None else herc_pair(c, py + r, px + x))
             for f in range(NFRAMES) for px, py in (((f & 7) + 8, (f >> 3) + 16),)
             for r, row in enumerate(ball_frame_indices(f)) for x, c in enumerate(row))
    results.append(("ball_herc_pairs(f) is the checker at world (py + r, px + x)", hp))
    differ = all(ball_frame_indices(fy * 8 + fx) != ball_frame_indices(fy * 8 + (fx + 1) % 8) and
                 ball_frame_indices(fy * 8 + fx) != ball_frame_indices(((fy + 1) % 8) * 8 + fx)
                 for fy in range(8) for fx in range(8))
    results.append(("every frame differs from its x and y phase neighbours", differ))
    sil = all(all((c is None) == (not _silhouette(x, y)) for y, row in enumerate(ball_frame_indices(f))
                  for x, c in enumerate(row)) for f in range(NFRAMES))
    results.append(("the silhouette is the same 16 px disc in every frame", sil))
    # negative controls: a guard nobody has seen fire is a guard nobody knows is alive
    bad = bytearray(a_files["BZBALC.BIN"])
    bad[BAL_FRMOFF] |= bad[BAL_MASKOFF] | 0xC0
    sub = []
    _check_ball(bytes(bad), False, sub)
    results.append(("negative control: a frame bit under a set mask bit is caught",
                    not all(good for _, good in sub)))
    bad = bytearray(a_files["BZBALC.BIN"])
    f1 = BAL_FRMOFF + (1 * D + 8) * RB          # frame 1 (shift 1) row 8 ...
    bad[f1:f1 + RB] = cga_bytes([0 if c is None else c for c in _ball_row(ball_frame_indices(1)[8], 0)])
    sub = []                                    # ...stored at shift 0 instead
    _check_ball(bytes(bad), False, sub)
    results.append(("negative control: a frame stored at the wrong shift is caught",
                    not all(good for _, good in sub)))
    old = build_ball_part(True, _fixed_mid=True)
    obad, omids, _, _ = _check_herc_ball_checker(old)
    results.append(("negative control: wave 0's fixed-10 Hercules ball is caught (%d of %d mid wrong)"
                    % (obad, omids), obad > 0))
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
