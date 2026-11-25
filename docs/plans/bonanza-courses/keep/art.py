#!/usr/bin/env python3
"""CLOCKWORK KEEP's art: its three GATES and its signs and decals (course 7; ../KEEP.md's "The art", ART.md
is the write-up).  Host only; nothing in `make` runs it.  ../artkit.py is the kit; this file is the artwork's
SOURCE and the `.bba` files it writes are committed:

    python3 docs/plans/bonanza-courses/keep/art.py            write apps/bonanza/courses/gates/keep_*.bba and
                                                              apps/bonanza/courses/keep_*.bba, print the `art` lines
    python3 docs/plans/bonanza-courses/keep/art.py --check    ...and compile the course: the picture's origin must
                                                              be the one the decals were placed for
    python3 docs/plans/bonanza-courses/keep/art.py --png OUT  ...and crops of each piece in place, both cards

sketch.py imports `lines()` (the course's `art` statements) and `GATES` (each gate's art name), so a re-emitted
course keeps its art.  The castle's stone is the scene's own MAGENTA face with black joints and a white line of
light along its tops; what moves in it (a grille, a door's leaves, bars) is black and white, so every frame reads
on the Hercules, where the scene's cyan and magenta are one grey.  The course's whole language is three GLYPHS, drawn
LARGE - black on a white plaque, as the engine draws them on its plates and keys (SPEC.md 130.41.5):
the PLUS on the portcullis's keystone, the RING the door's knocker, the CROSS the strongroom's lock."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import artkit as A                                     # noqa: E402
from artkit import K, C, M, W                          # noqa: E402

X0, Y0 = 496, -76                         # the course's `origin` and the compile's Y0 (`--check` holds them)
ZC, ZW = 10, 12                           # the courtyard's floor, the battlements'
GATES = {"portcullis": "keep_port", "door": "keep_door", "vault": "keep_vault"}
GLYPH = {"plus": ("..###..", "..###..", "#######", "#######", "#######", "..###..", "..###.."),
         "ring": (".#####.", "#######", "##...##", "##...##", "##...##", "#######", ".#####."),
         "cross": ("##...##", "###.###", ".#####.", "..###..", ".#####.", "###.###", "##...##")}


# ---- the gates (SPEC.md 130.41.12): four elevations each, shut to open ---------------------------------------
def _stone(cells):
    """dressed stone over CELLS (a set of (u, v)): MAGENTA courses as the castle's own faces are (white stone is
    lost on the white and cyan floor behind it), a black joint every 5 lines, a black line round the whole"""
    out = {}
    for (u, v) in cells:
        edge = any((u + du, v + dv) not in cells for du, dv in ((1, 0), (-1, 0), (0, -1), (0, 1)))
        out[(u, v)] = K if edge or v % 5 == 4 else M
    return out


def _plaque(uc, vc, glyph):
    """a channel's glyph LARGE and UPRIGHT: 7 x 7, black on a white plaque with a black edge, hung at the
    plane's point (uc, vc) -> gate_bba's flat piece"""
    d = {}
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            if abs(dx) == 5 and abs(dy) == 5:
                continue                             # (its corners cut)
            d[((uc, vc), dx, dy)] = K if max(abs(dx), abs(dy)) == 5 else W
    for j, row in enumerate(GLYPH[glyph]):
        for i, ch in enumerate(row):
            if ch == "#":
                d[((uc, vc), i - 3, j - 3)] = K
    return d


def portcullis():
    """2 cells: a stone gate arch with battlements, the PLUS on a plaque on its keystone, and an iron grille
    that RISES into the arch (frame 3: its spikes just showing, the way clear)"""
    U0, U1, TOP = -6, 38, 28                         # the piers' outer edges; the wall walk's line

    def under(u):                                    # the arch's underside over the opening (u 0 - 31)
        return 14 + int(round(5.0 * math.sin(math.pi * (u + 0.5) / 32.0)))
    stone = set()
    for u in range(U0, U1):
        for v in range(0, TOP + 4):
            pier = u < 0 or u > 31
            if v < TOP and (pier or v >= under(u)):
                stone.add((u, v))
            elif v >= TOP and ((u - U0) % 8) < 4:
                stone.add((u, v))                    # the merlons
    frames = []
    for lift in (0, 6, 11, 16):
        d = {}
        for u in range(0, 32):                       # the grille: bars 2 px in 4, a cross bar every 6 lines
            for v in range(0, under(u)):
                g = v - lift
                if g < -2:
                    continue
                bar = (u - 1) % 4
                if g < 0:
                    if bar == 0:
                        d[(u, v)] = K                # the spikes at its foot
                    continue
                if g % 6 in (4, 5):
                    d[(u, v)] = K if g % 6 == 4 or bar in (2, 3) else W
                elif bar == 0:
                    d[(u, v)] = K
                elif bar == 1:
                    d[(u, v)] = W
        d.update(_stone(stone))
        frames.append((d, _plaque(16, 24, "plus")))
    return A.gate_bba(GATES["portcullis"], frames, 2,
                      "CLOCKWORK KEEP's PORTCULLIS (docs/plans/bonanza-courses/keep/art.py writes this file):\n"
                      "a stone gate arch with battlements over two cells, the PLUS on a plaque on its keystone,\n"
                      "and an iron grille that rises into the arch (SPEC.md 130.41.12) - drawn for `along x`;\n"
                      "frame 0 shut, 3 open.")


def _doorway(top):
    """a one-cell stone doorway: two jambs and a round-headed lintel -> (the stone's cells, the opening's
    height at u)"""
    def under(u):
        return top - 9 + int(round(3.0 * math.sin(math.pi * (u + 0.5) / 16.0)))
    stone = set()
    for u in range(-4, 20):
        for v in range(0, top):
            if u < 0 or u > 15 or v >= under(u):
                stone.add((u, v))
    return stone, under


def door():
    """1 cell: the keep's DOOR, two iron-bound plank leaves under a round stone head with the RING on its
    keystone (and a ring for their knocker); the leaves SLIDE apart into the jambs (clockwork), so frame 3 is
    an empty doorway"""
    stone, under = _doorway(28)
    leaf = {}
    for u in range(0, 16):
        for v in range(0, under(u)):
            if v in (3, 13):
                ink = K
            elif v in (4, 5, 14, 15):
                ink = M                              # the iron bands
            elif u % 4 == 0 or u in (7, 8):
                ink = K                              # the planks' joints, and the leaves' meeting
            else:
                ink = W
            leaf[(u, v)] = ink
    for j, row in enumerate(GLYPH["ring"]):          # the knocker, on the leaves' meeting
        for i, ch in enumerate(row):
            if ch == "#" and row[3] != "#" or (ch == "#" and i != 3):
                leaf[(11 - i, 12 - j)] = K
    frames = []
    for s in (0, 3, 6, 8):
        d = {}
        for (u, v), ink in leaf.items():
            nu = u - s if u < 8 else u + s           # each leaf into its own jamb
            if (u < 8 and nu >= 0) or (u >= 8 and nu <= 15):
                if v < under(nu):
                    d[(nu, v)] = ink
        d.update(_stone(stone))
        frames.append((d, _plaque(8, 25, "ring")))
    return A.gate_bba(GATES["door"], frames, 1,
                      "CLOCKWORK KEEP's DOOR (docs/plans/bonanza-courses/keep/art.py writes this file): two\n"
                      "iron-bound plank leaves under a round stone head, the RING on its keystone; they slide\n"
                      "apart into the jambs, so frame 3 is an empty doorway (SPEC.md 130.41.12) - drawn for\n"
                      "`along x`; frame 0 shut, 3 open.")


def vault():
    """1 cell: the TREASURY's strongroom grille - heavy bars under a stone head, the CROSS on its keystone -
    sliding ASIDE into one jamb"""
    stone, under = _doorway(26)
    bars = {}
    for u in range(0, 16):
        for v in range(0, under(u)):
            b = u % 5
            if v in (3, 4, 12, 13):
                bars[(u, v)] = K if v in (3, 12) or b in (3, 4) else W
            elif b in (0, 2):
                bars[(u, v)] = K
            elif b == 1:
                bars[(u, v)] = W
    frames = []
    for s in (0, 5, 10, 16):
        d = {}
        for (u, v), ink in bars.items():
            nu = u + s
            if nu <= 15 and v < under(nu):
                d[(nu, v)] = ink
        d.update(_stone(stone))
        frames.append((d, _plaque(8, 23, "cross")))
    return A.gate_bba(GATES["vault"], frames, 1,
                      "CLOCKWORK KEEP's TREASURY GRILLE (docs/plans/bonanza-courses/keep/art.py writes this\n"
                      "file): heavy bars under a round stone head, the CROSS on its keystone, sliding aside into\n"
                      "one jamb (SPEC.md 130.41.12) - drawn for `along x`; frame 0 shut, 3 open.")


# ---- the signs and decals (SPEC.md 130.23.2's `art`) ------------------------------------------------------------
_HOURGLASS = (".KKKKKKK.", ".KWWWWWK.", "..KWWWK..", "...KWK...", "..KCWCK..", ".KCCWCCK.", ".KWWWWWK.", ".KKKKKKK.")
_THRONE = ("....K.....K.....K....", "...KWK...KWK...KWK...", "...KWWK.KWWWK.KWWK...", "...KWWWKWWWWWKWWWK...",
           "...KWWWWWWWWWWWWWK...", "...KWMMMMMMMMMMMWK...", "...KWMMMMMMMMMMMWK...", "...KWMMMMMWMMMMMWK...",
           "...KWMMMMWWWMMMMWK...", "...KWMMMMMWMMMMMWK...", "...KWMMMMMMMMMMMWK...", "...KWMMMMMMMMMMMWK...",
           ".KKKWMMMMMMMMMMMWKKK.", "KWWKWWWWWWWWWWWWWKWWK", "KWWKKKKKKKKKKKKKKKWWK", "KWWWWWWWWWWWWWWWWWWDK",
           "KWWMMMMMMMMMMMMMMWWDK", "KWWKKKKKKKKKKKKKKWWDK", "KWWK.............KWDK", "KWWK.............KWDK",
           "KKKK.............KKKK")
_SLIT = ("KKKK", "K..K", "K..K", "K..K", "K..K", "K..K", "KWWK", "KKKK")
_PENNANT = ("KK.........", "KWKKK......", "KWMMWKKK...", "KWMMMMMWKK.", "KWMMMMMMMDK", "KWMMMMMDKK.", "KWMMDKKK...",
            "KDKKK......", "KK.........")


def decals():
    """each piece its own file -> the course's `art` lines"""
    out = []
    # 1. WAIT, before the drawbridge: a signboard on the barbican's edge left of the bridge's mouth (tile (23, 37);
    #    only the void is behind it), an hourglass on top - the clocks' own, and what the bridge is: a timer
    s = A.Sheet(X0, Y0)
    cx, cy = s.tile(23, 37, ZC)
    for y in range(cy - 14, cy):
        s.put(cx - 1, y, K)
        s.put(cx, y, W)
        s.put(cx + 1, y, K)
    board = {(x, y) for y in range(cy - 25, cy - 13) for x in range(cx - 14, cx + 15)} - \
        {(cx + dx, cy + dy) for dx in (-14, 14) for dy in (-25, -14)}
    for xy in board:
        s.pix[xy] = W
    s.outline(board)
    s.text("WAIT", cx, cy - 23, K)
    s.pat(_HOURGLASS, cx - 4, cy - 35)
    out.append(s.write("keep_wait", "CLOCKWORK KEEP: the WAIT sign before the drawbridge (keep/art.py)"))
    # 2. the arrow to the PLATE: on the gatehouse's right lane, before the bars
    s = A.Sheet(X0, Y0)
    s.floor(25, 31, ZC, A.arrow)
    out.append(s.write("keep_plate", "CLOCKWORK KEEP: the floor arrow to the plate (keep/art.py)"))
    # 3. UP, at the rocking stair's two ends: an arrow on the courtyard floor south of each
    for name, wx in (("keep_up0", 28), ("keep_up1", 25)):
        s = A.Sheet(X0, Y0)
        s.floor(wx, 21, ZC, lambda u, v: A.arrow(v, u))
        out.append(s.write(name, "CLOCKWORK KEEP: an up arrow at the rocking stair's end (keep/art.py)"))
    # 4. the HAY: straw over the six sand tiles under the key (the drop's landing)
    s = A.Sheet(X0, Y0)
    for wx in (20, 21):
        for wy in (23, 24, 25):
            cx, cy = s.tile(wx, wy, ZC)

            def straw(u, v, wx=wx, wy=wy):
                x, y = int(64 * (wx + u)), int(64 * (wy + v))
                h = (x * 7 + y * 13 + (x // 5) * (y // 3)) % 9
                if (x // 3 + y // 2) % 4 == 0 and h < 5:
                    return W
                if (x // 2 - y // 3) % 7 == 0 and h > 5:
                    return K
                return None
            s.floor(wx, wy, ZC, straw, margin=0.04)
    out.append(s.write("keep_hay", "CLOCKWORK KEEP: straw over the six sand tiles (keep/art.py)"))
    # 5. the CARPET: from the keep's passage across the hall, the island between the cogs and the dais, turning
    #    right to the throne.  Not on the door's sill, the flag's tile or a cog (their lanes' blocks)
    s = A.Sheet(X0, Y0)

    def band(d):
        return M if d < 0.2 else (W if d < 0.27 else (K if d < 0.31 else None))
    for wx in (32, 33, 34, 37, 40):
        s.floor(wx, 24, ZC, lambda u, v: band(abs(v - 0.5)), margin=0.0)
    s.floor(41, 24, ZC, lambda u, v: band(max(abs(v - 0.5) if u < 0.5 else 0, abs(u - 0.5) if v > 0.5 else 0,
                                             max(u - 0.5, 0.5 - v) if (u >= 0.5 and v <= 0.5) else 0)), margin=0.0)
    s.floor(41, 25, ZC, lambda u, v: band(abs(u - 0.5)), margin=0.0)
    out.append(s.write("keep_carpet", "CLOCKWORK KEEP: the carpet from the keep's passage to the throne (keep/art.py)"))
    # 6. the THRONE: on the dais's west side beside the goal, the carpet's end in front of it (tile (40, 27): the
    #    void is behind it)
    s = A.Sheet(X0, Y0)
    cx, cy = s.tile(40, 27, ZC)
    s.pat(_THRONE, cx - 10, cy - 18)
    out.append(s.write("keep_throne", "CLOCKWORK KEEP: the throne (keep/art.py)"))
    # 7. the towers: arrow slits on the north-east and south-west towers' faces, a pennant on the north-east one
    for name, faces_y, faces_x, pen in (("keep_tower0", ((32, 17, 15), (33, 17, 15)), ((33, 16, 15), (33, 17, 15)), (32, 16, 15)),
                                        ("keep_tower1", ((18, 31, 14), (19, 31, 14)), ((19, 30, 14), (19, 31, 14)), None)):
        s = A.Sheet(X0, Y0)
        for (wx, wy, z) in faces_y:                  # their +y faces
            cx, cy = s.tile(wx, wy, z)
            s.pat(_SLIT, cx - 10, cy + 8)
        for (wx, wy, z) in faces_x:                  # their +x faces
            cx, cy = s.tile(wx, wy, z)
            s.pat(_SLIT, cx + 6, cy + 8)
        if pen:
            cx, cy = s.tile(*pen)
            for y in range(cy - 22, cy - 3):
                s.put(cx, y, W)
                s.put(cx + 1, y, K)
            s.pat(_PENNANT, cx + 1, cy - 23)
        out.append(s.write(name, "CLOCKWORK KEEP: arrow slits%s on a tower (keep/art.py)" % (" and a pennant" if pen else "")))
    return out


def lines():
    """the course's `art` statements (sketch.py emits them), the files written"""
    portcullis()
    door()
    vault()
    return decals()


if __name__ == "__main__":
    for ln in lines():
        print(ln)
    if "--check" in sys.argv or "--png" in sys.argv:
        c = A.check("keep", X0, Y0)
        if "--png" in sys.argv:
            out = sys.argv[sys.argv.index("--png") + 1]
            boxes = []
            for (wx, wy) in ((24, 30), (30, 24), (41, 21)):
                cx, cy = 16 * (wx - wy) + X0, 8 * (wx + wy) + 8 - 8 * ZC + Y0
                boxes.append((cx - 44, cy - 50, 88, 72))
            print(A.crop_png(c, boxes, os.path.join(out, "art-gates.png")))
            boxes = []
            for (wx, wy, w, h) in ((24, 38, 150, 100), (25, 31, 110, 90), (26, 22, 130, 90), (21, 24, 100, 90),
                                   (37, 25, 240, 130), (33, 17, 100, 110)):
                cx, cy = 16 * (wx - wy) + X0, 8 * (wx + wy) + 8 - 8 * ZC + Y0
                boxes.append((cx - w // 2, cy - h // 2 - 10, w, h))
            print(A.crop_png(c, boxes[:4], os.path.join(out, "art-signs.png")))
            print(A.crop_png(c, boxes[4:], os.path.join(out, "art-decals.png"), zoom=2))
            print(A.picture_png(c, out))
