#!/usr/bin/env python3
"""CASTLE CLIMB's art: six small pieces, each a file of its own and a line of its own at the END of
apps/bonanza/courses/castle.bbc, so any of them is struck by deleting one line (the course is the owner's own
layout; ART.md is the write-up).  Host only; nothing in `make` runs it.  ../artkit.py is the kit; this file is
the artwork's SOURCE and the `.bba` files it writes are committed:

    python3 docs/plans/bonanza-courses/castle/art.py            write apps/bonanza/courses/castle_*.bba, print the
                                                                `art` lines
    python3 docs/plans/bonanza-courses/castle/art.py --check    ...and compile the course: the picture's origin
                                                                must be the one the pieces were placed for
    python3 docs/plans/bonanza-courses/castle/art.py --png OUT  ...and OUT/picture-cga.png, picture-herc.png and
                                                                OUT/art-pieces.png (each piece in place, both cards)

Palette 2's inks by index: 1 cyan, 2 RED, 3 white.  The castle's faces are red (solid on the left, a red and
black dither on the right) and on the Hercules both are grey, so every piece is BLACK ON WHITE with a black
edge: the look the engine gives its own plate and key glyphs (SPEC.md 130.41.5)."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import artkit as A                                     # noqa: E402
from artkit import K, C, M, W                          # noqa: E402

A.PALS[2] = ((0, 0, 0), (85, 255, 255), (255, 85, 85), (255, 255, 255))     # the CGA's palette 2 (mode 5's)
X0, Y0 = 384, 84                          # the course's `origin` and the compile's Y0 (`--check` holds them)
ZBASE = 15                                # the tool's zero height in this course, units: a floor at height h
#                                           is drawn 8 (h - ZBASE) px over it (the start clock's z4 is -84 at 4.5)
GLYPH = {"plus": ("..###..", "..###..", "#######", "#######", "#######", "..###..", "..###.."),
         "ring": (".#####.", "#######", "##...##", "##...##", "##...##", "#######", ".#####.")}
_PENNANT = ("KKK.................", "KWWKKKK.............", "KWMMMWWKKKK.........", "KWMMMMMMMWWKKKK.....",
            "KWMMMMMMMMMMMWWKKK..", "KWMMWMMMMMMMMMMMMDKK", "KWMMMMMMMMMMMDDKKK..", "KWMMMMMMMDDKKKK.....",
            "KWMMMDDKKKK.........", "KDDKKKK.............", "KKK.................")
_UP = ("......K......", ".....KWK.....", "....KWWWK....", "...KWWWWWK...", "..KWWWWWWWK..", ".KWWWWWWWWWK.",
       "KWWWWWWWWWWWK", "KKKKWWWWWKKKK", "...KWWWWWK...", "...KWWWWWK...", "...KWWWWWK...", "...KWWWWWK...",
       "...KWWWWWK...", "...KWWWWWK...", "...KWWWWWK...", "...KKKKKKK...")


def sheet():
    return A.Sheet(X0, Y0 + 8 * ZBASE)


def plaque(s, cx, cy, glyph):
    """a channel's glyph LARGE and UPRIGHT: 7 x 7, black on a white 11 x 11 plaque with a black edge and cut
    corners, its centre at (cx, cy) - CLOCKWORK KEEP's gates wear the same (keep/art.py)"""
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            if abs(dx) == 5 and abs(dy) == 5:
                continue
            s.put(cx + dx, cy + dy, K if max(abs(dx), abs(dy)) == 5 else W)
    for j, row in enumerate(GLYPH[glyph]):
        for i, ch in enumerate(row):
            if ch == "#":
                s.put(cx + i - 3, cy + j - 3, K)


def ring(u, v):
    """floor paint: the ring key's RING, large - black, a white line inside and outside it"""
    r = math.hypot(u - 0.5, v - 0.5)
    if 0.2 <= r <= 0.32:
        return K
    if 0.13 <= r <= 0.39:
        return W
    return None


def decals():
    """each piece its own file -> the course's `art` lines"""
    out = []
    # 1. the PLUS on the first gate: a plaque on the +y face of the gate's right pier, the wall at (39, 31)
    #    (height 7).  The plate at (41, 28) wears the engine's own plus; this is the other end of it
    s = sheet()
    cx, cy = s.tile(39, 31, 7)
    plaque(s, cx - 8, cy + 20, "plus")
    out.append(s.write("castle_plus", "CASTLE CLIMB: the PLUS plaque on the first gate's pier (castle/art.py)"))
    # 2. the way to the PLATE: an arrow on the stair's first step, (40, 31) at height 1, pointing up it (-y)
    s = sheet()
    s.floor(40, 31, 1, lambda u, v: A.arrow(v, u))
    out.append(s.write("castle_toplate", "CASTLE CLIMB: the floor arrow at the stair to the plate (castle/art.py)"))
    # 3. the way to the KEY: the RING on the floor of (27, 14) and an arrow on (28, 14) pointing along the
    #    bridge (+x) to the ring key's platform - the junction where the keep's gate is straight on
    s = sheet()
    s.floor(27, 14, 12, ring)
    s.floor(28, 14, 12, lambda u, v: A.arrow(1.0 - u, v))
    out.append(s.write("castle_tokey", "CASTLE CLIMB: the ring and the arrow to the ring key (castle/art.py)"))
    # 4. the RING on the keep's gate: a plaque on the +x face of its left pier, the wall at (16, 12) (height 18)
    s = sheet()
    cx, cy = s.tile(16, 12, 18)
    plaque(s, cx + 8, cy + 20, "ring")
    out.append(s.write("castle_ring", "CASTLE CLIMB: the RING plaque on the keep's gate (castle/art.py)"))
    # 5. UP, over the tube's mouth: an arrow on the keep's wall above (12, 10) - the tube climbs to the goal
    s = sheet()
    cx, cy = s.tile(12, 10, 12)
    s.pat(_UP, cx - 14, cy - 58)
    out.append(s.write("castle_up", "CASTLE CLIMB: the up arrow on the keep's wall over the tube's mouth (castle/art.py)"))
    # 6. the keep's PENNANT: on its west corner turret (4, 6), the highest thing in the picture; the void is
    #    behind it
    s = sheet()
    cx, cy = s.tile(4, 6, 32)
    for y in range(cy - 24, cy - 1):
        s.put(cx - 1, y, K)
        s.put(cx, y, W)
        s.put(cx + 1, y, K)
    s.pat((".K.", "KWK", ".K."), cx - 1, cy - 27)
    s.pat(_PENNANT, cx + 1, cy - 24)
    out.append(s.write("castle_flag", "CASTLE CLIMB: the pennant on the keep (castle/art.py)"))
    return out


def lines():
    return decals()


BOXES = (("the plus and the arrow to the plate", 40, 31, 3, 132, 108), ("the ring and the arrow to the key", 28, 14, 13, 112, 80),
         ("the ring on the keep's gate", 16, 11, 16, 96, 88), ("up, over the tube", 12, 10, 16, 80, 88),
         ("the pennant", 5, 6, 33, 80, 64))


def check():
    """the compile's origin against the art's (a decal is placed in picture pixels: a stale Y0 moves them all)"""
    sys.path.insert(0, os.path.join(A.ROOT, "tools"))
    import bbcourse as B
    c = B.compile_course(os.path.join(A.COURSES, "castle.bbc"))
    z4 = [p["z4"] for p in c.props if p.get("ndig") and tuple(p["at"]) == (28, 41)][0]
    if (c.x0, c.y0) != (X0, Y0) or z4 != int(8 * (4.5 - ZBASE)):
        sys.exit("art.py: castle compiles at X0 %d, Y0 %d, the start clock's z4 %d; the art was placed for %d, %d, %d"
                 % (c.x0, c.y0, z4, X0, Y0, int(8 * (4.5 - ZBASE))))
    return c


if __name__ == "__main__":
    for ln in lines():
        print(ln)
    if "--check" in sys.argv or "--png" in sys.argv:
        c = check()
        if "--png" in sys.argv:
            out = sys.argv[sys.argv.index("--png") + 1]
            s = sheet()
            boxes = []
            for (_cap, wx, wy, z, w, h) in BOXES:
                cx, cy = s.tile(wx, wy, z)
                boxes.append((cx - w // 2, cy - h // 2, w, h))
            print(A.crop_png(c, boxes, os.path.join(out, "art-pieces.png"), pal=2))
            print(A.picture_png(c, out, pal=2))
