# WINDMILL LANE's clock options, ROUND 2 (2026-11-21).  The owner: "Tulips currently works the best, we may
# pick it, but first: I also like wheel and mill, though neither quite fully work. Can we get a few more
# variations around those two?"  CLOCKS.md's "What fails in mill and wheel" is the critique these answer.
#
# Four more concepts, round frames.py's `mill` and `wheel`, in the same machinery (bbcourse._ClockArt round
# clock_face_geom's digits' blocks, palette 1's inks) and the same three position marks: the TEE (a tee'd ball),
# a QUARTER TURN (the turntable disc and motion arcs) and the CUP (a flag).  frames.install(B) installs these as
# well; nothing in `make` and no shipped course moves.
#
# Shared: a broader, simpler SAIL (_vane) - a 3 px stock with a white heart and a blade on its trailing side,
# edged all round in black - so the silhouette survives a magenta wall and the Hercules' grey checker.
import math

import frames as F


def _vane(a, hx, hy, ang, L, w, kind, r0=3.0, sx=1.0, sy=1.0, behind=None):
    """one broad SAIL from the hub (HX, HY) at ANG degrees (screen: y down), L px long, its blade W px wide on
    the trailing side from R0 out.  KIND "cloth" (magenta cloth, white bars every 4 px), "white" (a white
    blade, black bars), "furled" (the cloth rolled along the stock: a white-and-black twist) or "stock" (the
    whip alone).  SX / SY < 1 foreshorten it (the cross seen turned).  BEHIND: cells it is not drawn over"""
    BLK, MAG, WHT = F.BLK, F.MAG, F.WHT
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    R = int(L + w + 3)
    cells = {}
    for y in range(int(hy) - R, int(hy) + R + 1):
        for x in range(int(hx) - R, int(hx) + R + 1):
            dx, dy = (x + 0.5 - hx) / sx, (y + 0.5 - hy) / sy
            u, v = dx * c + dy * s, -dx * s + dy * c
            if 0 <= u <= L + 0.5 and abs(v) <= 1.2:
                cells[(x, y)] = ("s", u, v)
            elif kind == "furled" and r0 + 1 <= u <= L - 1 and 1.2 < v <= 3.0:
                cells[(x, y)] = ("b", u, v)
            elif kind in ("cloth", "white") and r0 <= u <= L and 1.2 < v <= w:
                cells[(x, y)] = ("b", u, v)
    for (x, y), (part, u, v) in cells.items():
        if behind is not None and (x, y) in behind:
            continue
        edge = any((x + dx, y + dy) not in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if edge:
            ink = BLK
        elif part == "s":
            ink = WHT
        elif kind == "furled":
            ink = WHT if int(u) % 3 else BLK
        elif kind == "white":
            ink = BLK if int(u + 0.5) % 4 == 0 else WHT
        else:
            ink = WHT if int(u + 0.5) % 4 == 0 else MAG
        a.put(x, y, ink)
    return set(cells)


def _arcs(a, hx, hy, r, angs, sx=1.0, sy=1.0, n=9):
    """motion marks: a short white arc at radius R TRAILING each sail at ANGS (the cross turns clockwise)"""
    for a0 in angs:
        for k in range(n):
            t = math.radians(a0 - 14 - k * 3.0)
            a.put(int(round(hx + sx * r * math.cos(t))), int(round(hy + sy * r * math.sin(t))), F.WHT)


def _flagpin(a, x, top, bot):
    """a FLAG PIN: a 2 px pole (black, white) from TOP to BOT and frames.py's pennant at its head"""
    for y in range(top, bot + 1):
        a.put(x, y, F.BLK)
        a.put(x + 1, y, F.WHT)
    a.pattern(F._PENNANT, x + 2, top)


def _boatcap(B, a, cx_, base, hw, h):
    """the mill's boat CAP: a half ellipse HW wide, H tall, its foot on row BASE, lit at its left"""
    BLK, MAG, WHT = F.BLK, F.MAG, F.WHT
    cap = {(x, y) for (x, y) in B._ellipse(cx_ - 0.5, base + 0.5, hw, h, int(cx_ - hw) - 1, int(cx_ + hw) + 1,
                                             base - int(h) - 1, base) if y <= base}
    a.blob(cap, lambda x, y: WHT if x < cx_ - hw / 3.0 else (MAG if x < cx_ + hw / 3.0 else
                                                               (MAG if (x + y) & 1 else BLK)))
    return cap


def _smock(a, fx, top, bot, hw_top, hw_bot, plinth=3):
    """a WHITEWASHED tapering tower, rows TOP .. BOT, half widths HW_TOP .. HW_BOT: white (the digits' window
    on it, no plate), two black facet lines that stop short of the window, the right faces dithered cyan, a
    magenta brick PLINTH and an arched black DOOR.  -> its cells"""
    BLK, CYN, MAG, WHT = F.BLK, F.CYN, F.MAG, F.WHT
    wx0, wx1, wy0, wy1 = a.win

    def hw(y):
        return hw_top + (hw_bot - hw_top) * (y - top) / float(max(1, bot - top))
    body = {(x, y) for y in range(top, bot + 1) for x in range(int(fx - hw(y) - 0.5), int(fx + hw(y) + 0.5))}

    def ink(x, y):
        u = (x + 0.5 - fx) / hw(y)
        if y > bot - plinth:
            return WHT if u < -0.6 else (MAG if u < 0.5 or (x + y) & 1 else BLK)     # the plinth
        if F._in_win(a, x, y, 1):
            return WHT
        if abs(abs(u) - 0.7) < 0.08:
            return BLK                              # the facet lines
        if u > 0.7:
            return CYN if (x + y) & 1 else WHT      # the shade
        return WHT
    a.blob(body, ink)
    dt = max(wy1 + 4, bot - 9)                      # the DOOR: an arch, at the foot
    for y in range(dt, bot + 1):
        for x in range(fx - 3, fx + 3):
            if y > dt + 1 or (y == dt + 1 and fx - 2 <= x <= fx + 1) or (y == dt and fx - 1 <= x <= fx):
                a.put(x, y, BLK)
    return body


def _foot(B, a, pos, rx=13.5, ry=5.5):
    """the position's ground: the turntable disc (pos "t"), else the shadow on the block's top"""
    if pos == "t":
        F._disc(B, a, a.cx - 0.5, a.cy - 0.5, rx, ry)
    else:
        B._clock_top_shadow(a, 4, 11.0, 3.8)


def _collar(B, a):
    """the post's collar on the tile (`wheel`'s)"""
    cx, cy = a.cx, a.cy
    for (x, y) in B._ellipse(cx - 0.5, cy - 1.0, 5.0, 2.2, cx - 6, cx + 6, cy - 4, cy + 2):
        a.put(x, y, F.BLK if y >= cy or x in (cx - 5, cx + 4) else (F.WHT if x < cx - 1 else F.MAG))


def _plate(B, a, hx, hy, hrx, hry, ring=(0.62, 0.70)):
    """the round HUB PLATE that carries the digits: white, a magenta RIM RING between black lines, lit white at
    its upper left"""
    BLK, MAG, WHT = F.BLK, F.MAG, F.WHT
    cells = B._ellipse(hx, hy, hrx, hry, int(hx - hrx) - 1, int(hx + hrx) + 1, int(hy - hry) - 1,
                       int(hy + hry) + 1)

    def ink(x, y):
        ux, uy = (x + 0.5 - hx) / hrx, (y + 0.5 - hy) / hry
        d = ux * ux + uy * uy
        if F._in_win(a, x, y, 0):
            return WHT
        if d > ring[0]:
            return BLK if d > 0.92 or d < ring[1] else (WHT if ux + uy < -0.7 else MAG)
        return WHT
    a.blob(cells, ink)
    return cells


# ---- E. BODY: a squat whitewashed mill, its BODY the digits' window -----------------------------------------
# What `mill` lacked: its gallery read as a sign plate on a pole, and its sails as two rabbit ears (the lower
# two clipped at the digits).  Here the tower itself is white and the digits sit ON it; the cap sits just over
# them, and the cross on the cap's hub is a big one, seen a little from below (flatter than square), so its
# lower sails pass the digits' corners and run down IN FRONT of the tower; a sail that would cross the digits
# (the turntable's, turned) passes BEHIND the tower instead.  Lower than `mill` (the cap at the digits' top).
#   bodys  an X, four sails spread, a tee'd ball by the door
#   bodyt  turned 25 degrees on, white arcs behind the tips, the tower on the turntable disc
#   bodyf  an X, the sails furled, a flag pin on the cap
def _clock_body(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy = a.cx, a.cy, a.fx, a.fy
    wx0, wx1, wy0, wy1 = a.win
    _foot(B, a, pos)
    bot = cy - (2 if pos == "t" else 1)
    top = wy0 - 3
    hx, hy = fx - 0.5, top - 5.5
    ang0 = {"s": 45, "t": 75, "f": 45}[pos]
    kind = "furled" if pos == "f" else "cloth"
    L, w, sy = 27.0, 7.0, 0.55                      # the cross seen turned: a flat X
    win = {(x, y) for x in range(wx0 - 2, wx1 + 3) for y in range(wy0 - 2, wy1 + 3)}
    front, back = [], []
    for k in range(4):                              # a sail whose stock would cross the digits goes BEHIND
        ang = ang0 + 90 * k
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        hits = any((int(hx + u * c), int(hy + sy * u * s_)) in win for u in range(int(L) + 1))
        (back if hits else front).append(ang)
    for ang in back:
        _vane(a, hx, hy, ang, L, w, kind, sy=sy)
    _smock(a, fx, top, bot, 11.5, 13.5)
    _boatcap(B, a, hx + 0.5, top, 13.0, 7.0)
    for ang in front:
        _vane(a, hx, hy, ang, L, w, kind, sy=sy, behind=win if ang % 360 < 180 else None)
    a.pattern((".KK.", "KWWK", "KWWK", ".KK."), int(hx) - 1, int(hy) - 1)     # the hub
    if pos == "t":
        _arcs(a, hx, hy, L + 2.5, [ang0 + 90 * k for k in range(4)], sy=sy)
    if pos == "s":
        F._tee_peg(a, fx - 9, bot + 1)
    if pos == "f":
        _flagpin(a, int(hx) + 4, top - 20, top - 7)
    return a.done(tops)


# ---- F. SIDE: the mill seen from the SIDE, its sails a tall narrow X off its left ---------------------------
# The other cure for the digits-against-sails fight: turn the mill a quarter, so its sails face screen-left.
# The cross is foreshortened to a tall slim X standing off the cap's nose, clear of the digits at every angle;
# the tower is `body`'s, the cap a boat seen long, its windshaft poking out left.
#   sides  an X, the cloth spread, a tee'd ball at the door
#   sidet  a + (a quarter on: one sail up, one down, two seen end-on), arcs, on the turntable disc
#   sidef  an X, furled, a flag pin at the cap's tail
def _clock_side(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy = a.cx, a.cy, a.fx, a.fy
    wx0, wx1, wy0, wy1 = a.win
    BLK, MAG, WHT = F.BLK, F.MAG, F.WHT
    _foot(B, a, pos)
    bot = cy - (2 if pos == "t" else 1)
    top = wy0 - 3
    body = _smock(a, fx, top, bot, 11.5, 13.5)
    cap = {(x, y) for (x, y) in B._ellipse(fx + 0.5, top + 0.5, 15.0, 6.5, fx - 16, fx + 16, top - 8, top)
           if y <= top}
    a.blob(cap, lambda x, y: WHT if y < top - 3 else (MAG if (x + y) & 1 or x < fx + 6 else BLK))
    hx, hy = fx - 19.5, top - 2.5                   # the windshaft's nose, off the cap's left
    for x in range(int(hx) + 1, fx - 13):
        a.put(x, int(hy) - 1, BLK)
        a.put(x, int(hy), WHT)
        a.put(x, int(hy) + 1, BLK)
    sx = 0.6
    L, w = 23.0, 8.0
    if pos == "t":
        sails = [(ang, "cloth") for ang in (0, 90, 180, 270)]
    else:
        sails = [(ang, "furled" if pos == "f" else "cloth") for ang in (45, 135, 225, 315)]
    for ang, kind in sails:
        _vane(a, hx, hy, ang, L, w, kind, sx=sx, behind=body | cap)
    a.pattern((".KK.", "KWWK", "KWWK", ".KK."), int(hx) - 1, int(hy) - 1)
    if pos == "t":
        _arcs(a, hx, hy, L + 2.0, [90, 270], sx=sx * 1.6, n=7)
    if pos == "s":
        F._tee_peg(a, fx + 10, bot + 1)
    if pos == "f":
        _flagpin(a, fx + 11, top - 20, top - 6)
    return a.done(tops)


# ---- G. HUB: `wheel` with four BROAD white sails and a big round hub plate ----------------------------------
# What `wheel` lacked: thin lattice sails that dissolved into the magenta wall at the turntable and into the
# guard rail at the start, and a hub that read as an egg (the crystal's sign again).  Here the hub is a ROUND
# plate (a magenta rim ring between black lines round the white field), the sails broad WHITE blades with black
# bars (they read on black, on magenta and on the Hercules alike), and the cross UPRIGHT at the start so the
# lower sail runs down the post instead of across the rail.  No cap.
#   hubs   a + (the cross at rest), a tee'd ball at the post's foot
#   hubt   turned 30 degrees on, arcs, the post on the turntable disc
#   hubf   an X (stopped), the sails furled, a flag pin from the top of the plate
def _clock_hub(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    _foot(B, a, pos, 11.5, 5.0)
    hx, hy = fx - 0.5, fy - 0.5
    hrx, hry = 4 * n + 5.0, 10.5
    _collar(B, a)
    a.column(cx - 2, int(hy + hry) - 1, cy - 2)
    ang0 = {"s": 0, "t": 30, "f": 45}[pos]
    kind = "furled" if pos == "f" else "white"
    L, w = 26.0, 7.0
    for k in range(4):
        _vane(a, hx, hy, ang0 + 90 * k, L, w, kind, r0=8.0)
    if pos == "t":
        _arcs(a, hx, hy, L + 2.0, [ang0 + 90 * k for k in range(4)])
    _plate(B, a, hx, hy, hrx, hry)
    if pos == "s":
        F._tee_peg(a, cx + 9, cy + 1)
    if pos == "f":
        _flagpin(a, int(hx), int(hy - hry) - 13, int(hy - hry))
    return a.done(tops)


# ---- H. POST: the CHEAP one - a pinwheel + on a post, its blades on alternate quadrants, block-aligned -------
# Built for the block pool: the + is upright, its blades rectangles on ALTERNATE quadrants (a pinwheel), the
# vertical arms on the digits' own block columns and the bars every 4 px, so an arm's inside repeats block for
# block and the pool dedupes it.  The digits on `hub`'s round plate, which the arms come out of; no cap, no
# tower.
#   posts  the pinwheel's cloth spread, a tee'd ball at the post's foot
#   postt  spread the OTHER way round (the blades on the other quadrants: the wheel seen turning), white arcs
#          between the arms, the post on the turntable disc
#   postf  the cloth taken in (the stocks bare), a flag pin from the top arm's tip
def _clock_post(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    MAG, WHT = F.MAG, F.WHT
    _foot(B, a, pos, 11.5, 5.0)
    hx, hy = fx - 0.5, fy - 0.5
    hrx, hry = 4 * n + 4.0, 9.5
    _collar(B, a)
    a.column(cx - 2, int(hy + hry) - 1, cy - 2)
    hy_i = int(hy)
    pt, pb = int(hy - hry) + 1, int(hy + hry) - 1       # the plate's top and bottom rows
    pl, pr = int(hx - hrx) + 1, int(hx + hrx) - 1       # ... its left and right columns
    up, dn = pt - 15, pb + 8                        # the arms' ends
    lf, rt = pl - 13, pr + 13
    cw = pos != "t"                                 # the blades' quadrants: one way round, or the other
    bar = (lambda x, y: WHT if x % 4 == 0 or y % 4 == 0 else MAG)
    if pos != "f":                                  # the BLADES, 6 px wide (drawn first: the stocks over them)
        a.blob({(x, y) for y in range(up, pt + 1) for x in (range(fx, fx + 7) if cw else range(fx - 7, fx))},
               bar)
        a.blob({(x, y) for y in range(pb, dn + 1) for x in (range(fx - 7, fx) if cw else range(fx, fx + 7))},
               bar)
        a.blob({(x, y) for x in range(pr, rt + 1) for y in (range(hy_i + 1, hy_i + 8) if cw else
                                                             range(hy_i - 6, hy_i + 1))}, bar)
        a.blob({(x, y) for x in range(lf, pl + 1) for y in (range(hy_i - 6, hy_i + 1) if cw else
                                                             range(hy_i + 1, hy_i + 8))}, bar)
    st = (lambda x, y: WHT)                         # the STOCKS: 4 px, a black edge and a white heart
    a.blob({(x, y) for y in range(up, pt + 1) for x in range(fx - 2, fx + 2)}, st)
    a.blob({(x, y) for y in range(pb, dn + 1) for x in range(fx - 2, fx + 2)}, st)
    a.blob({(x, y) for x in range(lf, pl + 1) for y in range(hy_i - 1, hy_i + 3)}, st)
    a.blob({(x, y) for x in range(pr, rt + 1) for y in range(hy_i - 1, hy_i + 3)}, st)
    if pos == "t":                                  # arcs between the arms, trailing the turn
        for ang in (-60, 30, 120, 210):
            for k in range(7):
                t = math.radians(ang - k * 3.5)
                a.put(int(round(hx + (hrx + 10) * math.cos(t))), int(round(hy + (hry + 10) * math.sin(t))), WHT)
    _plate(B, a, hx, hy, hrx, hry, ring=(0.66, 0.74))
    if pos == "s":
        F._tee_peg(a, cx + 9, cy + 1)
    if pos == "f":
        _flagpin(a, fx - 1, up - 11, up - 1)
    return a.done(tops)


CONCEPTS = {
    "body": [("bodys", "s"), ("bodyt", "t"), ("bodyf", "f")],
    "side": [("sides", "s"), ("sidet", "t"), ("sidef", "f")],
    "hub": [("hubs", "s"), ("hubt", "t"), ("hubf", "f")],
    "post": [("posts", "s"), ("postt", "t"), ("postf", "f")],
}
DRAW = {"body": _clock_body, "side": _clock_side, "hub": _clock_hub, "post": _clock_post}
