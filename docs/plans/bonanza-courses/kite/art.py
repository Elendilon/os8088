#!/usr/bin/env python3
"""KITE HILL's art: its signs and decals (course 5; ../KITE.md's "The art", ART.md is the write-up).  Host only;
nothing in `make` runs it.  ../artkit.py is the kit; this file is the artwork's SOURCE and the `.bba` files it
writes (apps/bonanza/courses/kite_*.bba) are committed:

    python3 docs/plans/bonanza-courses/kite/art.py            write the files, print the course's `art` lines
    python3 docs/plans/bonanza-courses/kite/art.py --check    ...and compile the course: the picture's origin must
                                                              be the one the decals were placed for
    python3 docs/plans/bonanza-courses/kite/art.py --png OUT  ...and crops of each piece in place, both cards

sketch.py imports `lines()`, so a re-emitted course keeps its art.  KITE is `palette 0`: ink 1 is GREEN, 2 RED
and 3 YELLOW (the kit's C, M and W); on the Hercules green and red are one grey checker and yellow is white, so
every piece carries its shape in yellow and black as well."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import artkit as A                                     # noqa: E402
from artkit import K, C, M, W                          # noqa: E402

X0, Y0 = 528, 28                          # the course's `origin` and the compile's Y0 (`--check` holds them)
_BOW = ("MM...MM", "MMM.MMM", ".MMWMM.", "MMM.MMM", "MM...MM")
_FLY = ("K.........", "KMMMM.....", "KMMMMMMMM.", "KMMMMMMMMM", "KMMMMMMM..", "KMMMM.....", "K.........", "K.........",
        "K.........")
_LIMP = ("K.........", "KMM.......", "KMM.......", "KMMM......", "KMMM......", "KMMM......", "K.MM......", "K..M......",
         "K.........")
_BANNER = ("KKKKKKK", "KWWWWWK", "KWMMMWK", "KWMMMWK", "KWWWWWK", "KWMMMWK", "KWMMMWK", "KWWWWWK", ".KWWWK.", "..KWK..",
           "...K...")


def _kite(s, kx, ky, hw, up, dn, inks, lean=0):
    """a diamond kite, harlequin: INKS its (upper left / lower right, upper right / lower left) panels, black
    spars and a black line round it -> its foot"""
    sail = set()

    def row(y):
        v = y + 0.5 - ky
        t = (-v / up) if v <= 0 else (v / dn)
        return kx + (lean * t if v <= 0 else -0.6 * lean * t), hw * (1.0 - t)
    for y in range(int(ky - up), int(ky + dn) + 1):
        xc, half = row(y)
        for x in range(int(math.floor(xc - half)), int(math.ceil(xc + half)) + 1):
            if abs(x + 0.5 - xc) <= half:
                sail.add((x, y))
    for (x, y) in sail:
        xc, _h = row(y)
        if x == int(xc) or y == int(ky):
            s.pix[(x, y)] = K
        else:
            s.pix[(x, y)] = inks[0] if (x < xc) == (y < ky) else inks[1]
    s.outline(sail)
    ty = max(y for (_x, y) in sail)
    return min(x for (x, y) in sail if y == ty), ty


def _tail(s, tx, ty, side, bows, slope, gap=9):
    pts = []
    for k in range(1, 4 + gap * bows + 1):
        pts.append((tx + side * k, ty + int(slope * k + 1.6 * math.sin(k * 0.7))))
    for (x, y) in pts:
        s.pix[(x, y)] = M
        s.pix[(x, y + 1)] = K
    for b in range(bows):
        x, y = pts[gap - 2 + gap * b]
        s.pat(_BOW, x - 3, y - 2)


def decals():
    out = []
    # 1. the GREAT KITE: flown from the launch plaza, out over the valley to its left - what the plaza is for.
    #    Placed by the CAMERA (kite/camera.py): whole in the window on the launch plaza and all through the glide
    s = A.Sheet(X0, Y0)
    gx, gy = s.tile(16, 36, 15.5)                    # its peg: the launch plaza's west edge
    s.line(100, 289, gx - 2, gy - 2, K)               # the string, drawn first (the sail over its top): yellow,
    s.line(100, 288, gx - 2, gy - 3, W)               # a black line under it where it crosses the floor
    s.pat((".K.", "KWK", "KMK", "KMK", ".K."), gx - 3, gy - 6)      # the peg
    tx, ty = _kite(s, 89.0, 292.0, 22.0, 26.0, 36.0, (W, M), lean=-3)  # (INSIDE the launch plaza's windows: camera.py.  At
    _tail(s, tx, ty, 1, 3, 0.9, gap=7)               # its first place, over the summit, the camera never showed it whole)
    out.append(s.write("kite_great", "KITE HILL: the great kite, flown from the launch plaza (kite/art.py)"))
    # 2. the GUST BRIDGE's sign: on the breezeway's last tile beside the bridge's mouth (only the void is behind
    #    it).  A pennant FLYING: WAIT.  A pennant LIMP: GO.  (The fan's own pennant is the one to watch.)
    s = A.Sheet(X0, Y0)
    cx, cy = s.tile(39, 45, 7)
    px = cx - 5
    for y in range(cy - 16, cy):
        s.put(px - 1, y, K)
        s.put(px, y, W)
        s.put(px + 1, y, K)
    board = {(x, y) for y in range(cy - 40, cy - 15) for x in range(px - 20, px + 20)} - \
        {(px + dx, cy + dy) for dx in (-20, 19) for dy in (-40, -16)}
    for xy in board:
        s.pix[xy] = W
    s.outline(board)
    s.pat(_FLY, px - 17, cy - 38)
    s.text("WAIT", px + 6, cy - 37, K)
    for x in range(px - 18, px + 18):
        s.put(x, cy - 28, K)
    s.pat(_LIMP, px - 17, cy - 26)
    s.text("GO", px + 3, cy - 25, K)
    out.append(s.write("kite_calm", "KITE HILL: the gust bridge's sign - flying: WAIT, limp: GO (kite/art.py)"))
    # 3. the FAN PLAZA: two arrows on its floor into the rising air (the west strip, at the cliff's foot)
    s = A.Sheet(X0, Y0)
    for wy in (36, 38):
        s.floor(39, wy, 7, A.arrow)
    out.append(s.write("kite_lift", "KITE HILL: the fan plaza's arrows into the thermal (kite/art.py)"))
    # 4. the WINDBREAKS' shelters: each sheltered tile framed in red, a banner hung from its rail's foot (over
    #    the bridge's face and the void: the shelters are the hardest thing on the course to see)
    s = A.Sheet(X0, Y0)
    for wx in (24, 25, 28, 29):
        def frame(u, v):
            d = min(u, 1.0 - u, v, 1.0 - v)
            return M if 0.1 <= d < 0.22 else (K if 0.22 <= d < 0.27 else None)
        s.floor(wx, 38, 15.5, frame, margin=0.05)
        cx, cy = s.tile(wx, 38, 15.5)
        s.pat(_BANNER, cx - 11, cy + 6)
    out.append(s.write("kite_shelter", "KITE HILL: the windbreaks' two shelters, framed and bannered (kite/art.py)"))
    # 5. the LAUNCH PLAZA: an arrow up the screen on the tile between the flag and the open corner, and a kite
    #    painted on the corner tile itself - roll off here
    s = A.Sheet(X0, Y0)
    s.floor(17, 35, 15.5, A.up_arrow)

    def mark(u, v):
        a, b = (u + v) / 2.0 - 0.5, (u - v) / 2.0
        d = abs(b) / 0.3 + (abs(a) / 0.2 if a < 0 else abs(a) / 0.3)
        if d > 1.0:
            return None
        if d > 0.8 or abs(b) < 0.03 or abs(a + 0.02) < 0.03:
            return K
        return M if (b < 0) == (a < 0) else W
    s.floor(16, 34, 15.5, mark, margin=0.03)
    out.append(s.write("kite_launch", "KITE HILL: the launch plaza's arrow and the kite on its corner (kite/art.py)"))
    # 6. two small KITES in the void beside the hill (a backdrop: the ball is always drawn over them), each where
    #    the route's window shows it whole on both cards (kite/camera.py: the first places were cut by its edges)
    s = A.Sheet(X0, Y0)
    for (kx, ky, inks, side) in ((678, 430, (W, M), 1), (440, 330, (C, W), -1)):
        tx, ty = _kite(s, kx + 0.0, ky + 0.0, 8.0, 9.0, 14.0, inks, lean=2 * side)
        _tail(s, tx, ty, side, 2, 0.5, gap=7)
        out.append(s.write("kite_small%d" % len([o for o in out if "small" in o]),
                           "KITE HILL: a small kite in the sky (kite/art.py)"))
        s = A.Sheet(X0, Y0)
    return out


def lines():
    """the course's `art` statements (sketch.py emits them), the files written"""
    return decals()


if __name__ == "__main__":
    for ln in lines():
        print(ln)
    if "--check" in sys.argv or "--png" in sys.argv:
        c = A.check("kite", X0, Y0)
        if "--png" in sys.argv:
            out = sys.argv[sys.argv.index("--png") + 1]
            print(A.crop_png(c, [(60, 240, 200, 130), (372, 590, 130, 90)], os.path.join(out, "art-signs.png"), pal=0, zoom=2))
            print(A.crop_png(c, [(540, 560, 120, 80), (300, 400, 170, 90), (190, 280, 110, 80), (400, 300, 80, 70), (640, 400, 80, 70)],
                             os.path.join(out, "art-decals.png"), pal=0, zoom=2))
            print(A.picture_png(c, out, pal=0))
