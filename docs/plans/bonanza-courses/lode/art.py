#!/usr/bin/env python3
"""LODESTONE GORGE's art: its signs and decals (course 6; ../LODE.md's "The art", ART.md is the write-up).  Host
only; nothing in `make` runs it.  ../artkit.py is the kit; this file is the artwork's SOURCE and the `.bba`
files it writes (apps/bonanza/courses/lode_*.bba) are committed:

    python3 docs/plans/bonanza-courses/lode/art.py            write the files, print the course's `art` lines
    python3 docs/plans/bonanza-courses/lode/art.py --check    ...and compile the course: the picture's origin must
                                                              be the one the decals were placed for
    python3 docs/plans/bonanza-courses/lode/art.py --png OUT  ...and crops of each piece in place, both cards

sketch.py imports `lines()`, so a re-emitted course keeps its art.  Palette 1's inks; MAGENTA is the lodestones'
own, and every piece carries its shape in black and white for the Hercules.  The course is 2,000 LZ4 bytes
under its budget's 1.5x line and its clocks take a third of that: the pieces are few and small on purpose."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import artkit as A                                     # noqa: E402
from artkit import K, C, M, W                          # noqa: E402

X0, Y0 = 272, 76                          # the course's `origin` and the compile's Y0 (`--check` holds them)


def _shoe(u, v):
    """floor paint: a HORSESHOE seen from above, its poles toward v = 0 (magenta, white pole tips, a black line
    round it) - the magnets' glyph, the first time the player meets it"""
    du, dv = u - 0.5, v - 0.56
    r = (du * du + dv * dv) ** 0.5
    if dv >= 0:
        body, edge = 0.17 <= r <= 0.33, 0.12 <= r <= 0.38
    else:
        body = 0.17 <= abs(du) <= 0.33 and v >= 0.16
        edge = 0.12 <= abs(du) <= 0.38 and v >= 0.11
    if body:
        return W if v < 0.3 else M
    return K if edge else None


_ROCK_L = ("................", "KK..............", "KWKK............", "KWWMKK..........", "KWMMMMKK........",
           "KWWMMMMMKK......", "KKWMMMKMMMKK....", "KMKWMMKMMMMMKK..", "KMMKWMMKMMMMMMKK", "KWMMKMMMKMMMMMMK",
           "KWWMMKMMMKMMMMMK", "KKWMMMKMMMKKMMMK", ".KKWMMMKMMMMKMMK", "...KKMMMKMMMMKMK", ".....KKMMKMMMMKK",
           ".......KKMKMMMMK", ".........KKKMMMK", "...........KKMMK", ".............KKK")
_SPARK = ("..W..", "..W..", "WWWWW", "..W..", "..W..")


def decals():
    out = []
    # 1. the HOIST: at its foot, a horseshoe painted on the floor and an arrow up the ramp - the glyph beside
    #    what it does
    s = A.Sheet(X0, Y0)
    s.floor(25, 22, 16, _shoe)
    s.floor(25, 21, 16, lambda u, v: A.arrow(v, u))
    out.append(s.write("lode_hoist", "LODESTONE GORGE: the hoist's foot - a horseshoe and an arrow up the ramp (lode/art.py)"))
    # 2. KEEP MOVING: chevrons on the sirens' bridge, both lanes, before the first siren
    s = A.Sheet(X0, Y0)
    for wy in (18, 19):
        s.floor(28, wy, 18, lambda u, v: A.chevrons(1.0 - u, v))
    out.append(s.write("lode_sirens", "LODESTONE GORGE: keep moving - chevrons before the first siren (lode/art.py)"))
    # 3. STRAIGHT ON: chevrons up the runway, to the gantry's hover
    s = A.Sheet(X0, Y0)
    for wy in (37, 38):
        s.floor(30, wy, 13, lambda u, v: A.chevrons(v, u))
    out.append(s.write("lode_runway", "LODESTONE GORGE: straight on - chevrons up the runway (lode/art.py)"))
    # 4. the GREAT LODESTONE: the last magnet's post dressed as a boulder of lodestone - its two faces rough
    #    crystal, a spur of it either side, glints off it.  Nothing on the post's top: that is the magnet's lane
    s = A.Sheet(X0, Y0)
    cx, cy = s.tile(30, 24, 17.5)
    s.pat(_ROCK_L, cx - 16, cy - 1)
    s.pat(_ROCK_L, cx, cy - 1, flip=True)
    for (dx, dy) in ((-25, 4), (22, 2), (-20, 20), (25, 18)):
        s.pat(_SPARK, cx + dx - 2, cy + dy - 2)
    out.append(s.write("lode_great", "LODESTONE GORGE: the great lodestone - the last magnet's post as a boulder (lode/art.py)"))
    return out


def lines():
    """the course's `art` statements (sketch.py emits them), the files written"""
    return decals()


if __name__ == "__main__":
    for ln in lines():
        print(ln)
    if "--check" in sys.argv or "--png" in sys.argv:
        c = A.check("lode", X0, Y0)
        if "--png" in sys.argv:
            out = sys.argv[sys.argv.index("--png") + 1]
            boxes = []
            for (wx, wy, z, w, h) in ((25, 21, 16, 120, 90), (29, 18, 18, 120, 80), (30, 36, 13, 120, 110),
                                      (30, 25, 16, 120, 90)):
                cx, cy = 16 * (wx - wy) + X0, 8 * (wx + wy) + 8 - 8 * z + Y0
                boxes.append((cx - w // 2, cy - h // 2 - 8, w, h))
            print(A.crop_png(c, boxes, os.path.join(out, "art-signs.png")))
            print(A.picture_png(c, out))
