# CASTLE CLIMB's clock CONCEPTS (the owner's own course; the brief is the course guide's G23,
# ../../mill/clocks/frames.py the precedent, ../../clockkit.py the kit that compiles and draws them).  One object
# a concept, a variant a clock: the course's four clocks are the OUTER WALL (start, cell (28, 41)), the FIRST
# GATE (39, 30), the TERRACES (23, 22) and the KEEP (8, 8), and what changes between them says how far up the
# castle the player has climbed.  Palette 2's inks (cyan, RED, white on black: the tool's MAG is this course's
# red); on the Hercules cyan and red are one grey checker, so every form is carried by white and black.
#
#   beacon  A BEACON: an iron fire-basket on a stem, the digits on its white-hot coals; the FIRE grows up the
#           castle (embers and smoke, a small flame, a tall one, a roaring one with sparks) - the alarm running
#           up the walls ahead of the ball.  INSTALLED: tools/bbcourse.py's `bcn0` .. `bcn3` (`_clock_beacon`,
#           SPEC.md 137.18.5.2) - named here, drawn there.
#   banner  A war BANNER hung from a crossbar on a spear, the digits on its white chief; its red field carries one
#           CHEVRON a stage climbed (1, 2, 3) and a CROWN at the keep.  Scratch: DRAW below.
#   turret  A round brick TURRET, the digits on its white string course; it is a storey TALLER at each clock
#           and at the keep it has its roof and pennant.  Scratch: DRAW below.
import math

CONCEPTS = {
    "beacon": [("bcn0", ""), ("bcn1", ""), ("bcn2", ""), ("bcn3", "")],
    "banner": [("bnr1", ""), ("bnr2", ""), ("bnr3", ""), ("bnr4", "")],
    "turret": [("tur1", ""), ("tur2", ""), ("tur3", ""), ("tur4", "")],
}
BASE = "beacon"

_CROWN = (".K...K...K.", "KWK.KWK.KWK", "KWKKWWWKKWK", "KWWWWWWWWWK", "KWMWWMWWMWK", "KWWWWWWWWWK", "KKKKKKKKKKK")


def _clock_banner(B, p, x0, y0, tops, pos):
    BLK, CYN, MAG, WHT = B.BLK, B.CYN, B.MAG, B.WHT
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1, wy0, wy1 = a.win
    hs = 4 * n + 4.0                                # the cloth's half width
    kx = fx - 0.5
    bar = wy0 - 8
    B._clock_top_shadow(a, 3, 10.0, 3.4)
    for (x, y) in B._ellipse(cx - 0.5, cy - 1.5, 6.0, 2.4, cx - 7, cx + 7, cy - 5, cy + 2):   # the spear's foot
        a.put(x, y, BLK if y >= cy or x in (cx - 6, cx + 5) else (WHT if x < cx - 2 else MAG))
    a.column(cx - 2, bar - 3, cy - 3, WHT, CYN)
    a.pattern(("..KK..", ".KWCK.", ".KWCK.", "KWWCCK", "KWWCCK", ".KWCK.", ".KKKK."), cx - 3, bar - 10)   # its head
    for x in range(int(kx - hs) - 2, int(kx + hs) + 3):                    # the crossbar
        for k, ink in enumerate((BLK, WHT, CYN, BLK)):
            a.put(x, bar + k, ink)
    top, chief, tip = bar + 4, wy1 + 2, wy1 + 19

    def low(x):                                     # the cloth's dagged lower edge: three tails
        u = (x + 0.5 - kx + hs) % (2 * hs / 3.0)
        return tip - int(abs(u - hs / 3.0) * 0.9)
    cl = {(x, y) for x in range(int(kx - hs), int(kx + hs) + 1) for y in range(top, low(x) + 1)}

    def ink(x, y):
        if y < chief:
            if wx0 - 1 <= x <= wx1 + 1:
                return WHT                          # the chief: the digits' field
            return MAG
        if y == chief:
            return BLK
        if x + 0.5 > kx + 0.55 * hs and (x + y) & 1:
            return BLK                              # the field's shade
        return MAG
    a.blob(cl, ink)
    y = chief + 3
    if pos == 4:
        a.pattern(_CROWN, fx - 6, y + 1)
    else:
        for k in range(pos):                        # a chevron a stage, pointing up
            for i in range(-6, 7):
                yy = y + 3 * k + abs(i) // 2
                a.put(int(kx) + i, yy, WHT)
                a.put(int(kx) + i, yy + 1, WHT)
    return a.done(tops)


def _clock_turret(B, p, x0, y0, tops, pos):
    BLK, CYN, MAG, WHT = B.BLK, B.CYN, B.MAG, B.WHT
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1, wy0, wy1 = a.win
    hw = 4 * n + 4.0
    kx = fx - 0.5
    band0, band1 = wy0 - 2, wy1 + 2                 # the white string course the digits stand on
    top = band0 - 2 - 6 * (pos - 1)                 # the wall walk's line: a storey a stage
    B._clock_top_shadow(a, 4, 12.0, 3.8)

    def bow(x):                                     # a round tower: its courses bow down at the middle
        return int(round(2.0 * (1.0 - ((x + 0.5 - kx) / hw) ** 2)))
    body = set()
    for x in range(int(kx - hw), int(kx + hw) + 1):
        for y in range(top - 4, cy - 3 + bow(x) + 1):
            if y >= top + bow(x) or ((x - int(kx - hw)) % 6) < 3 and y >= top - 4 + bow(x):
                body.add((x, y))                    # (the merlons)

    def ink(x, y):
        yb = y - bow(x)
        if band0 <= y <= band1 and wx0 - 1 <= x <= wx1 + 1:
            return WHT
        if band0 <= yb <= band1:
            return WHT if x < kx + 0.5 * hw or (x + y) & 1 else CYN
        if x + 0.5 < kx - hw + 2:
            return WHT                              # the light down its left
        if (yb - top) % 4 == 3 or ((x + 2 * ((yb - top) // 4)) % 6 == 0):
            return BLK                              # the brick joints
        if x + 0.5 > kx + hw - 4 and (x + y) & 1:
            return BLK
        return MAG
    a.blob(body, ink)
    for k in range(pos - 1):                        # an arrow slit a storey
        sx = int(kx) + (-4 if k & 1 else 3)
        for y in range(top + 2 + 6 * k, top + 6 + 6 * k):
            a.put(sx, y + bow(sx), BLK)
            a.put(sx + 1, y + bow(sx), BLK)
    for y in range(cy - 11, cy - 2):                # its door
        for x in range(int(kx) - 3, int(kx) + 3):
            if y > cy - 11 or abs(x + 0.5 - kx) < 2:
                a.put(x, y + bow(x), BLK)
    if pos == 4:                                    # the keep's: a cone roof and a pennant
        roof = set()
        for y in range(top - 16, top - 2):
            h = (hw + 2) * (y - (top - 16)) / 14.0
            roof |= {(x, y) for x in range(int(math.floor(kx - h + 0.5)), int(math.floor(kx + h + 0.5)) + 1)}
        a.blob(roof, lambda x, y: WHT if x + 0.5 < kx - 1 else (CYN if (x + y) & 1 else WHT))
        for y in range(top - 26, top - 16):
            a.put(int(kx), y, BLK)
            a.put(int(kx) + 1, y, WHT)
        a.pattern(("KKK.....", "KMMKKK..", "KMMMMMKK", "KMMKKK..", "KKK....."), int(kx) + 2, top - 26)
    return a.done(tops)


DRAW = {}
for _k in (1, 2, 3, 4):
    DRAW["bnr%d" % _k] = (lambda q: lambda B, p, x0, y0, tops: _clock_banner(B, p, x0, y0, tops, q))(_k)
    DRAW["tur%d" % _k] = (lambda q: lambda B, p, x0, y0, tops: _clock_turret(B, p, x0, y0, tops, q))(_k)
