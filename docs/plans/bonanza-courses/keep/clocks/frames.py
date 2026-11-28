# CLOCKWORK KEEP's clock CONCEPTS (course 7; the brief is the course guide's G23, ../../mill/clocks/frames.py the
# precedent, ../../clockkit.py the kit that compiles and draws them).  One object a concept, a variant a clock:
# the course's three clocks are the BARBICAN (start), the north-west TOWER and the throne's DAIS, and what
# changes between them says how far through the lock the player is.  Palette 1's inks (cyan, magenta, white on
# black); on the Hercules cyan and magenta are one grey checker, so every form is carried by white and black.
#
#   hour    An HOURGLASS in a turned stand, the digits in its upper bulb; the SAND runs down the course (full,
#           half, run out) and the stand's finial is a PADLOCK, a KEY, a CROWN.  INSTALLED: tools/bbcourse.py's
#           `hourp`, `hourk`, `hourc` (`_clock_hour`, SPEC.md 137.18.5.2) - named here, drawn there.
#   shield  The designer's: a heater SHIELD hung by two chains from a banner pole, the digits across its white
#           chief, its CREST the same three (padlock, key, crown), white on the magenta field.  Scratch: DRAW
#           below, in this process only.
import math

CONCEPTS = {
    "hour": [("hourp", ""), ("hourk", "ink white"), ("hourc", "ink white")],
    "shield": [("shldp", ""), ("shldk", ""), ("shldc", "")],
}
BASE = "hour"


def _clock_shield(B, p, x0, y0, tops, pos):
    BLK, CYN, MAG, WHT = B.BLK, B.CYN, B.MAG, B.WHT
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1, wy0, wy1 = a.win
    hs = 4 * n + 4.0                                # the shield's half width
    kx = fx - 0.5
    bar = wy0 - 9
    B._clock_top_shadow(a, 3, 10.0, 3.4)
    for (x, y) in B._ellipse(cx - 0.5, cy - 1.5, 6.0, 2.4, cx - 7, cx + 7, cy - 5, cy + 2):   # the pole's foot
        a.put(x, y, BLK if y >= cy or x in (cx - 6, cx + 5) else (WHT if x < cx - 2 else MAG))
    a.column(cx - 2, bar - 4, cy - 3)
    a.pattern((".KK.", "KWMK", "KWMK", ".KK."), cx - 2, bar - 8)            # its knob
    for x in range(int(kx - hs) - 1, int(kx + hs) + 2):                     # the crossbar
        for k, ink in enumerate((BLK, WHT, MAG, BLK)):
            a.put(x, bar + k, ink)
    for sx in (int(kx - hs) + 3, int(kx + hs) - 3):                         # the two chains
        for y in range(bar + 4, wy0 - 3):
            a.put(sx, y, WHT if (y & 1) else BLK)
            a.put(sx + 1, y, BLK if (y & 1) else WHT)
    top, chief, tip = wy0 - 3, wy1 + 2, wy1 + 17

    def half(y):
        if y <= chief + 1:
            return hs
        t = (y - chief - 1) / float(tip - chief - 1)
        return hs * math.cos(0.5 * math.pi * t) ** 0.8
    sh = {(x, y) for y in range(top, tip + 1) for x in range(int(math.floor(kx - half(y) + 0.5)),
                                                             int(math.floor(kx + half(y) + 0.5)))}

    def ink(x, y):
        d = half(y) - abs(x + 0.5 - kx)
        if d < 2.6 or y < top + 2:
            return CYN                              # the bordure
        if y < chief:
            return WHT                              # the chief: the digits' field
        if y == chief:
            return BLK
        if x + 0.5 > kx + 0.45 * half(y) and (x + y) & 1:
            return BLK                              # the field's shade
        return MAG
    a.blob(sh, ink)
    rows = B._HOUR_CREST[pos]
    a.pattern(rows, fx - (len(rows[0]) + 1) // 2, chief + 2 + (10 - len(rows)) // 2)
    return a.done(tops)


DRAW = {"shld" + k: (lambda q: lambda B, p, x0, y0, tops: _clock_shield(B, p, x0, y0, tops, q))(k)
        for k in ("p", "k", "c")}
