# KITE HILL's clock CONCEPTS (course 5; the brief is the course guide's G23, ../../mill/clocks/frames.py the
# precedent, ../../clockkit.py the kit that compiles and draws them).  One object a concept, a variant a clock:
# the course's four clocks are the MEADOW (start), the FAN PLAZA, the LAUNCH PLAZA and the SUMMIT, and what
# changes between them says how far up the hill the player is.  Drawn in the course's inks BY INDEX - KITE is
# `palette 0`, so ink 1 (CYN) is GREEN, ink 2 (MAG) RED and ink 3 (WHT) YELLOW; on the Hercules green and red are
# one grey checker and yellow is white, so every form is carried by yellow and black as well.
#
#   kite   A KITE on its string, the digits on its sail; its TAIL grows a bow a clock (1, 2, 3, then a full
#          streaming tail of 5) and it leans the way the course goes next.  INSTALLED: tools/bbcourse.py's
#          `kite1` .. `kite4` (`_clock_kite`, SPEC.md 130.18.5.2) - named here, drawn there.
#   sock   A WINDSOCK on a pole, the digits on its first band; the wind fills it up the hill: limp at the meadow,
#          half out at the fan plaza, straight out at the launch plaza, taut and fluttering on the summit.
#          Scratch: DRAW below, in this process only.
import math

CONCEPTS = {
    "kite": [("kite1", "digits 0 -16"), ("kite2", "digits 0 -16"), ("kite3", "digits 0 -16"),
             ("kite4", "digits 0 -16")],
    "sock": [("sock1", ""), ("sock2", ""), ("sock3", ""), ("sock4", "")],
}
BASE = "kite"


def _clock_sock(B, p, x0, y0, tops, pos):
    BLK, MAG, WHT = B.BLK, B.MAG, B.WHT
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy = a.cx, a.cy, a.fx, a.fy
    wx0, wx1, wy0, wy1 = a.win
    px = wx0 - 7                                    # the pole's left edge
    B._clock_top_shadow(a, 2, 10.0, 3.4)
    for (x, y) in B._ellipse(px + 2.0, cy - 1.0, 5.0, 2.2, px - 4, px + 8, cy - 4, cy + 2):   # its foot, on the tile
        a.put(x, y, BLK if y >= cy or x in (px - 3, px + 6) else (WHT if x < px + 1 else MAG))
    a.column(px, wy0 - 9, cy - 2)
    a.pattern((".KK.", "KWMK", "KWMK", ".KK."), px, wy0 - 13)      # the finial
    for y in (wy0 - 3, wy1 + 2):                    # the two arms that hold the hoop
        for x in range(px + 4, wx0 - 1):
            a.put(x, y, BLK)
            a.put(x, y + 1, WHT)
    xb = wx1 + 2                                    # the digits' band ends here; the cone hangs from it
    L = 26 if pos == 4 else 22
    droop = {1: 0.85, 2: 0.42, 3: 0.0, 4: 0.0}[pos]

    def off(u):
        if pos == 3:
            return 0.12 * u
        if pos == 4:
            return 1.2 * math.sin(u * 0.55) * (u / float(L))
        return droop * u * u / 22.0
    cells = {}
    for x in range(wx0 - 1, xb + L + 1):
        u = max(0, x - xb)
        h = 7.0 - 4.2 * u / float(L)
        yc = fy - 0.5 + off(u)
        for y in range(int(math.floor(yc - h + 0.5)), int(math.floor(yc + h + 0.5))):
            cells[(x, y)] = (u, y + 0.5 - yc, h)
    cs = set(cells)

    def ink(x, y):
        u, v, h = cells[(x, y)]
        if u == 0:
            if wx0 - 1 <= x <= wx1 + 1 and wy0 - 1 <= y <= wy1 + 1:
                return WHT                          # the digits' band
            return MAG if (v > h - 2.2 and (x + y) & 1) else WHT
        band = MAG if (int(u - 1) // 6) % 2 == 0 else WHT
        if v > h - 2.0 and (x + y) & 1:
            return BLK if band == MAG else MAG      # the shade under it
        return band
    a.blob(cs, ink)
    for y in range(wy0 - 3, wy1 + 4):               # the hoop: a bright ring at the mouth
        a.put(wx0 - 2, y, BLK)
        a.put(wx0 - 1, y, WHT if (wy0 - 2 <= y <= wy1 + 2) else BLK)
    if pos == 4:                                    # taut: flutter marks past the tip
        tx, ty = xb + L + 2, int(fy + off(L))
        for k, (dx, dy) in enumerate(((0, -3), (2, 0), (0, 3))):
            for i in range(4 - (k == 1)):
                a.put(tx + dx + i, ty + dy, WHT)
    return a.done(tops)


DRAW = {"sock%d" % k: (lambda q: lambda B, p, x0, y0, tops: _clock_sock(B, p, x0, y0, tops, q))(k)
        for k in (1, 2, 3, 4)}
