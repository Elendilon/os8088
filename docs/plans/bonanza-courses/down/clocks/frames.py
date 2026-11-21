# DOWNHILL DECISION's clock OPTIONS (course 3, the owner to pick; the brief is the course guide's G23).
#
# Four concepts, each with a per-POSITION variant (start, hub, steel finish, glass finish), drawn with the tool's
# own clock-frame machinery (bbcourse._ClockArt, round clock_face_geom's digits' blocks) in the course's inks
# (palette 1: CYN, MAG, WHT on black; on the Hercules CYN and MAG are one grey checker, so every form is
# carried by white and black as well).  Every one stands on its BLOCK's top, as LITTLE HOP's frogs do: a
# dithered shadow on the top's diamond, nothing hanging off the tile.
#
# This file is SOURCE for the tool, not a second copy of it: `install(B)` adds the sixteen frames to
# bbcourse's CLOCK_STYLES and _CLOCK_DRAW in THIS process only (sheet.py calls it), so nothing in `make` and
# no shipped course moves.  The frame the owner picks is lifted into tools/bbcourse.py beside _clock_frog,
# its four names into CLOCK_STYLES, and sketch.py's FRAMES names them per position.
import math

BLK = CYN = MAG = WHT = None


def _bind(B):
    global BLK, CYN, MAG, WHT
    BLK, CYN, MAG, WHT = B.BLK, B.CYN, B.MAG, B.WHT


def _dither(a, b):
    return lambda x, y: a if (x + y) & 1 else b


def _ontop(a, x, y, m=0.92):
    return abs(x + 0.5 - a.cx) / 16.0 + abs(y + 0.5 - a.cy) / 8.0 <= m


def _top_shadow(B, a, dx=3, rx=11.0, ry=4.0, dy=2.0):
    """the dithered shadow on the BLOCK's top (the frogs'): every other pixel black, on the diamond only"""
    for (x, y) in B._ellipse(a.cx + dx, a.cy + dy, rx, ry, a.cx - 16, a.cx + 17, a.cy - 6, a.cy + 8):
        if _ontop(a, x, y) and (x + y) & 1:
            a.put(x, y, BLK, "shadow")


def _chequer(a, x0, y0, w, h, cell=2, edge=True):
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if edge and (y in (y0, y0 + h - 1) or x in (x0, x0 + w - 1)):
                a.put(x, y, BLK)
            else:
                a.put(x, y, WHT if ((x - x0) // cell + (y - y0) // cell) & 1 else BLK)


def _icon_ball(B, a, x, y, kind):
    """a 7 px ball, the course's two mechanic balls: STEEL (chrome, black under a white sky) or GLASS (cyan,
    a white glint and a bright caustic low on its right)"""
    cells = B._ellipse(x, y, 3.6, 3.6, x - 4, x + 4, y - 4, y + 4)

    def ink(px, py):
        ux, uy = px + 0.5 - x, py + 0.5 - y
        if kind == "steel":
            if ux < -0.5 and uy < -0.5:
                return WHT
            return WHT if uy < 0 else (MAG if (px + py) & 1 else BLK)
        if ux < -0.5 and uy < -0.5:
            return WHT
        return WHT if (ux > 0.5 and uy > 0.5) else CYN
    a.blob(cells, ink)


# ---- A. SIGN: a FINGERPOST at a fork in the road ------------------------------------------------------------
# A lit post on a collar on the block's top, a ball finial, and the digits on a white ARROW BOARD clamped to it -
# a pointed end, a swallow-tailed one, nails, a lit top bevel and a dithered under-edge; the board is a sign on a
# pole, which is what the owner said made First Roll's `pin` fit.  Per position:
#   signs (start)   one arrow, pointing LEFT (back up the line the ball came down) under a CHEQUERED start
#                   flag flying from the post's head
#   signh (hub)     the FORK: the digits' arrow points LEFT (south, STEEL: a steel ball on its tail) and a
#                   second, smaller arrow over it points RIGHT (east, GLASS: a glass ball on it)
#   signf (steel)   the digits' arrow points RIGHT with the steel ball on its tail; a chequered FINISH banner
#                   across the post's head
#   signg (glass)   the same, the glass ball, pointing LEFT (the glass goal is up-left of its clock)
def _arrow(a, X0, X1, Y0, Y1, left, tip=6, tail=3):
    """an arrow board X0 .. X1 by Y0 .. Y1 with its TIP pointing left (or right) and a swallow tail"""
    cells = set()
    mid = (Y0 + Y1) / 2.0
    half = (Y1 - Y0 + 1) / 2.0
    for y in range(Y0, Y1 + 1):
        d = abs(y + 0.5 - mid - 0.5)
        for x in range(X0 - tip, X1 + tip + 1):
            if X0 <= x <= X1:
                # the tail's notch: a V cut tail px deep into the square end
                if (not left and x < X0 + tail and (x - X0) < tail - d * tail / half) or \
                        (left and x > X1 - tail and (X1 - x) < tail - d * tail / half):
                    continue
                cells.add((x, y))
            elif left and x < X0 and (X0 - x) <= tip * (1 - d / half):
                cells.add((x, y))
            elif not left and x > X1 and (x - X1) <= tip * (1 - d / half):
                cells.add((x, y))

    def ink(x, y):
        if y <= Y0 + 1:
            return WHT
        if y >= Y1 - 1:
            return MAG if (x + y) & 1 else BLK
        return WHT
    a.blob(cells, ink)
    for nx in ((X1 - 4,) if left else (X0 + 4,)):
        a.put(nx, int(mid) - 3, BLK)
        a.put(nx, int(mid) + 3, BLK)


def _clock_sign(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy = a.cx, a.cy, a.fx, a.fy
    wx0, wx1, wy0, wy1 = a.win
    _top_shadow(B, a, 4, 9.0, 3.2)
    for (x, y) in B._ellipse(cx - 0.5, cy - 1.0, 5.0, 2.2, cx - 6, cx + 6, cy - 4, cy + 2):   # the collar
        a.put(x, y, BLK if y >= cy or x in (cx - 5, cx + 4) else (WHT if x < cx - 1 else MAG))
    head = wy0 - (17 if pos in ("s", "f", "g") else 15)
    a.column(cx - 2, head + 2, cy - 2)
    for (x, y, ink) in ((-2, 0, BLK), (-1, -1, BLK), (0, -1, BLK), (1, 0, BLK), (-1, 0, WHT), (0, 0, MAG),
                        (-2, 1, BLK), (-1, 1, WHT), (0, 1, MAG), (1, 1, BLK)):
        a.put(cx + x, head + y, ink)                # the finial
    left = pos in ("s", "h", "g")
    X0, X1, Y0, Y1 = wx0 - 2, wx1 + 2, wy0 - 3, wy1 + 3
    if pos != "s":                                  # room on the tail for the ball's icon
        if left:
            X1 += 8
        else:
            X0 -= 8
    _arrow(a, X0, X1, Y0, Y1, left)
    if pos != "s":
        _icon_ball(B, a, X1 - 4 if left else X0 + 4, (Y0 + Y1) // 2, "glass" if pos == "g" else "steel")
    if pos == "h":                                  # the GLASS arm over it, pointing the other way
        _arrow(a, cx - 1, cx + 13, head + 3, head + 11, False, tip=5, tail=2)
        _icon_ball(B, a, cx + 9, head + 7, "glass")
    if pos == "s":                                  # the START flag from the post's head
        _chequer(a, cx + 2, head + 2, 11, 8)
        for k in range(4):
            a.put(cx + 13, head + 3 + k, BLK)       # (a little wave at its fly)
    if pos in ("f", "g"):                           # the FINISH banner across the post's head
        _chequer(a, cx - 11, head + 2, 22, 6)
    return a.done(tops)


# ---- B. ORB: the course's three balls, one object in three materials --------------------------------------
# A big sphere on a short lit stem and a cup, the digits on a white band round its middle (bowed to the
# sphere, as LITTLE HOP's `ball`).  It is the course's subject - you start rubber and finish steel or glass:
#   orbr (start)    RUBBER: magenta, lit white, a black dither in its shade
#   orbh (hub)      the SPLIT: its left half steel, its right half glass, a zigzag seam down its face
#                   (steel south = screen left, glass east = screen right)
#   orbs (steel)    STEEL: chrome - a white sky over a hard horizon, black ground under it, a bright rim
#   orbg (glass)    GLASS: cyan, a window glint, a caustic low on its right, and its own STEM SEEN THROUGH IT
def _clock_orb(B, p, x0, y0, tops, mat):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1 = a.win[0], a.win[1]
    slim = mat in ("steel", "glass")                # the finishes' are slimmer (130.18.5.4's one ball length)
    r = 4 * n + (6.5 if slim else 10.0)
    bh, bow = (5.5, 2.0) if slim else (6.5, 3.0)    # the band's half height (the digits' rows), its bow
    bcx, bcy = fx, fy
    _top_shadow(B, a, 4, 10.0, 3.6)
    bot = int(bcy + r)
    for (x, y) in B._ellipse(cx - 0.5, cy - 1.5, 6.0, 2.5, cx - 7, cx + 7, cy - 5, cy + 2):   # the foot
        a.put(x, y, BLK if y >= cy or x in (cx - 6, cx + 5) else (WHT if x < cx - 2 else MAG))
    a.column(cx - 2, bot - 2, cy - 3)
    for (x, y) in B._ellipse(bcx - 0.5, bot - 1.0, 8.0, 2.6, bcx - 9, bcx + 9, bot - 4, bot + 2):  # the cup
        a.put(x, y, BLK if y >= bot or abs(x + 0.5 - bcx) > 6.5 else (WHT if x < bcx - 2 else MAG))
    ball = B._ellipse(bcx, bcy, r, r, int(bcx - r) - 1, int(bcx + r) + 1, int(bcy - r) - 1, int(bcy + r) + 1)

    def seam(y):                                    # the split's zigzag, x of it on row y
        return bcx - 1 + (1 if (y // 3) & 1 else -1)

    def ink(x, y):
        ux, uy = (x + 0.5 - bcx) / r, (y + 0.5 - bcy) / r
        uz = math.sqrt(max(0.0, 1.0 - ux * ux - uy * uy))
        lit = -0.5 * ux - 0.6 * uy + 0.62 * uz
        mid = bcy - 0.5 + bow * (1.0 - math.sqrt(max(0.0, 1.0 - ux * ux)))
        off = y + 0.5 - mid
        if abs(off) <= bh:                          # the band: white, shaded only off the digits
            if wx0 <= x <= wx1:
                return WHT
            return (MAG if (x + y) & 1 else WHT) if lit < 0.05 else WHT
        if abs(off) < bh + 1:
            return BLK
        m = mat
        if mat == "split":
            if x == seam(y):
                return BLK
            m = "steel" if x < seam(y) else "glass"
        if m == "rubber":
            if lit > 0.9:
                return WHT
            if lit < -0.1 or (lit < 0.2 and (x + y) & 1):
                return BLK if (x + y) & 1 else MAG
            return MAG
        if m == "steel":
            if off < 0:                             # the sky: white, greying to the horizon
                if lit > 0.95 or uy < -0.8:
                    return WHT
                return (WHT if (x + y) & 1 else MAG) if lit > 0.45 else (MAG if (x + y) & 1 else BLK)
            if uy > 0.78 and ux < 0.35:
                return WHT                          # the bright rim the ground throws back
            return BLK if (lit < 0.1 or (x + y) & 1) else MAG
        # glass
        if lit > 0.98:
            return WHT
        if uy > 0.55 and ux > 0.05 and (ux * ux + uy * uy) > 0.55:
            return WHT if (x + y) & 1 or uy > 0.7 else CYN     # the caustic
        if lit < -0.15 and (x + y) & 1:
            return MAG
        return CYN
    a.blob(ball, ink)
    if mat in ("glass", "split"):                   # the STEM seen through the glass, dimmed
        for y in range(int(bcy + 8.5), bot - 1):
            for k, c_ in ((-1, MAG), (0, CYN)):
                if (cx + k, y) in ball and (mat == "glass" or cx + k > seam(y)) and a.out.get((cx + k, y)) == CYN:
                    a.put(cx + k, y, c_ if (y & 1) else CYN)
    gx, gy = int(bcx - 0.5 * r), int(bcy - 0.62 * r)    # the glint (a little window on glass)
    if mat == "glass" or mat == "split":
        gx = int(bcx + 0.2 * r) if mat == "split" else gx
        a.pattern(("WW.W", "WW.W", "....", "WW.W"), gx - 1, gy - 1)
    else:
        a.pattern(("WW", "WW"), gx, gy)
    return a.done(tops)


# ---- C. PENGUIN: a downhill racer and a swimmer -------------------------------------------------------------
# A penguin standing on the block's top, the digits on its white BELLY; its back and head a dark blue (black
# and cyan dithered, so a black edge is never lost on the void), a white rim of light down its upper left, a
# magenta beak and feet, white eyes.  Per position (LITTLE HOP's frog's rule: the same creature, its pose per
# use):
#   pengs (start)   racing GOGGLES on its forehead, flippers swept back: about to belly-slide down the ramp
#   pengh (hub)     head turned LEFT, its left flipper pointing (steel's way), the other on its hip: "which way?"
#   pengf (steel)   both flippers up, cheering, a little STEEL helmet (a chrome dome, a rivet)
#   pengg (glass)   both flippers up, cheering, eyes back over its shoulder to the glass goal, a bead
#                   of glass balanced on its crown
def _clock_peng(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1, wy0, wy1 = a.win
    _top_shadow(B, a, 4, 11.0, 3.8)
    top, bot = wy0 - 17, cy - 2
    by_, bry, brx = (top + bot + 1) / 2.0, (bot + 1 - top) / 2.0, 4 * n + 5.5

    def dark(x, y, ux, uy):
        if ux + uy < -0.95 and ux < -0.45:
            return WHT                              # the rim of light
        return CYN if (x + y) & 1 else BLK

    def egg(x, y):
        uy = (y + 0.5 - by_) / bry
        return ((x + 0.5 - fx) / (brx * (0.80 + 0.2 * uy))) ** 2 + uy * uy <= 1.0
    for sx in (-1, 1):                              # the FEET, on the top
        a.pattern(("KMMMMK", "MMMMMM", "KKKKKK"), fx + sx * 5 - 3, bot - 1)
    for sx in (-1, 1):                              # the FLIPPERS (under the body, so drawn first)
        if pos == "s":                              # swept back and down
            pts = [(fx + sx * (brx - 2) + sx * k * 0.3, by_ + 2 + k) for k in range(10)]
        elif pos == "h" and sx < 0:                 # pointing out to the left
            pts = [(fx - brx + 3 - k, by_ - 2 - k * 0.5) for k in range(7)]
        elif pos == "h":                            # on its hip
            pts = [(fx + brx - 1 + min(k, 4) * 0.5 - max(0, k - 4) * 0.7, by_ - 2 + k) for k in range(9)]
        else:                                       # up, cheering
            pts = [(fx + sx * (brx - 2 + k * 0.3), by_ - 3 - k) for k in range(10)]
        cells = set()
        for i, (px, py) in enumerate(pts):
            w = 3.0 if i < len(pts) - 3 else 2.0
            cells |= B._ellipse(px, py, w, 1.6, int(px) - 3, int(px) + 3, int(py) - 2, int(py) + 2)
        a.blob(cells, lambda x, y: CYN if (x + y) & 1 else BLK)
    body = {(x, y) for y in range(top - 1, bot + 2) for x in range(int(fx - brx) - 2, int(fx + brx) + 2)
            if egg(x, y)}
    a.blob(body, lambda x, y: dark(x, y, (x + 0.5 - fx) / brx, (y + 0.5 - by_) / bry))
    bex, bey, berx, bery = fx - 0.5, (wy0 + bot) / 2.0 + 0.5, 4 * n + 2.5, (bot - wy0) / 2.0 + 2.5
    for (x, y) in B._ellipse(bex, bey, berx, bery, int(bex - berx) - 1, int(bex + berx) + 1,
                             int(bey - bery) - 1, int(bey + bery) + 1):
        if all(q in body for q in ((x, y), (x + 1, y), (x - 1, y), (x, y + 1))):
            ux = (x + 0.5 - bex) / berx
            a.put(x, y, (WHT if (x + y) & 1 else CYN) if (ux > 0.75 and not wx0 <= x <= wx1) else WHT)
    look = -2 if pos in ("h", "g") else 0           # the head turned (left) or ahead
    gy = -1 if pos == "g" else 0
    ey = wy0 - 8
    for sx in (-1, 1):                              # the EYES
        ex = fx + sx * 5 + look - (sx > 0)
        a.pattern(("KWWWK", "WWWWW", "WWWWW", "KWWWK"), ex - 2, ey - 2)
        a.pattern(("KK", "KK"), ex - 1 + (-1 if look else 0) + (sx > 0), ey - 1 + gy)
    bx = fx + look                                  # the BEAK
    a.pattern(("KMMMMK", ".KMMK.", "..KK.."), bx - 3, ey + 3)
    if pos == "s":                                  # GOGGLES pushed up on the forehead
        for x in range(int(fx - brx * 0.75), int(fx + brx * 0.75) + 1):
            if (x, ey - 4) in body:
                a.put(x, ey - 4, WHT)
        for sx in (-1, 1):
            a.pattern(("KKKK", "KCWK", "KCCK", "KKKK"), fx + sx * 4 - 2, ey - 6)
    if pos == "f":                                  # the STEEL helmet: a chrome dome on its crown, a rivet
        dome = {(x, y) for (x, y) in B._ellipse(fx - 0.5, top + 3.0, 8.5, 6.0, fx - 10, fx + 9, top - 4, top + 3)
                if y <= top + 2}
        a.blob(dome, lambda x, y: WHT if y < top - 1 or x < fx - 4 else (MAG if (x + y) & 1 else BLK))
        a.pattern(("KW", "KK"), fx - 1, top - 3)
    if pos == "g":                                  # a GLASS bead balanced on its crown
        _icon_ball(B, a, fx + 1, top - 3, "glass")
    return a.done(tops)


# ---- D. WATCH: the race's STOPWATCH --------------------------------------------------------------------------
# A stopwatch standing in a cradle on a stepped plinth: a magenta bezel lit white at its upper left and dithered
# at its lower right, a white dial with twelve black ticks round the digits (the dial is a window, and here it is
# the object's own face), a crown and its bow on top, a side pusher.  Per position:
#   watchs (start)  the crown PRESSED, three click marks round it: the race starts
#   watchh (hub)    a FORK painted on the plinth's face (a Y, white), the watch upright
#   watchf (steel)  a STEEL case (chrome: white and black), a chequered ribbon from the bow
#   watchg (glass)  a GLASS case (cyan, a white glint), the chequered ribbon
def _clock_watch(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    _top_shadow(B, a, 4, 10.0, 3.6)
    R, Rd = (4 * n + 5.5, 4 * n + 2.5) if pos == "f" else (4 * n + 6.5, 4 * n + 3.5)               # the case, the dial
    wcx, wcy = fx - 0.0, fy + 0.0
    bot = int(wcy + R)
    # the STAND: a round foot on the block's top, a lit stem and a cradle cupping the case from below
    for (x, y) in B._ellipse(cx - 0.5, cy - 1.5, 7.0, 3.0, cx - 8, cx + 8, cy - 5, cy + 2):
        a.put(x, y, BLK if y >= cy or abs(x + 0.5 - cx) > 6 else (WHT if x < cx - 2 else MAG))
    a.column(cx - 2, bot - 1, cy - 4)
    for (x, y) in B._ellipse(wcx - 0.5, bot - 2.0, 9.0, 4.0, int(wcx) - 10, int(wcx) + 10, bot - 6, bot + 2):
        a.put(x, y, BLK if y >= bot + 1 or abs(x + 0.5 - wcx) > 7.5 else (WHT if x < wcx - 3 else
                                                                         (MAG if x < wcx + 4 else (MAG if (x + y) & 1 else BLK))))
    if pos == "h":                                  # the FORK: a white Y on the foot
        for (dx, dy) in ((0, 0), (0, -1), (-1, -2), (1, -2), (-2, -3), (2, -3)):
            a.put(cx - 1 + dx, cy - 1 + dy, WHT)

    def bezel(x, y, ux, uy):
        if pos == "f":
            return WHT if uy < 0.05 else (BLK if (x + y) & 1 else MAG)
        if pos == "g":
            return WHT if ux + uy < -1.0 else CYN
        if ux + uy < -0.7:
            return WHT
        if ux + uy > 0.7:
            return MAG if (x + y) & 1 else BLK
        return MAG
    cy_top = int(wcy - R)
    press = 1 if pos == "s" else 0
    for (x, y, ink) in ((-1, -1, BLK), (0, -1, BLK), (-1, 0, WHT), (0, 0, MAG)):   # the stem
        a.put(fx + x, cy_top + y, ink)
    knob = {(x, y) for x in range(fx - 3, fx + 3) for y in range(cy_top - 4 + press, cy_top - 1)}
    a.blob(knob, lambda x, y: WHT if x < fx - 1 else MAG)
    bow = B._ellipse(fx - 0.5, cy_top - 7.5 + press, 4.5, 3.5, fx - 6, fx + 5, cy_top - 12, cy_top - 3)
    inner = B._ellipse(fx - 0.5, cy_top - 7.5 + press, 2.5, 1.6, fx - 4, fx + 3, cy_top - 10, cy_top - 5)
    for (x, y) in bow - inner:
        if (x, y) not in knob:
            edge = any((x + dx, y + dy) not in bow or (x + dx, y + dy) in inner
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            a.put(x, y, BLK if edge else (WHT if x < fx else MAG))
    ang = math.radians(-50)                         # the side PUSHER, up and right
    px, py = wcx + (R + 1.5) * math.cos(ang), wcy + (R + 1.5) * math.sin(ang)
    a.blob(B._ellipse(px, py, 2.6, 2.6, int(px) - 3, int(px) + 3, int(py) - 3, int(py) + 3),
           lambda x, y: WHT if x < px else MAG)
    case = B._ellipse(wcx, wcy, R, R, int(wcx - R) - 1, int(wcx + R) + 1, int(wcy - R) - 1, int(wcy + R) + 1)

    def ink(x, y):
        ux, uy = (x + 0.5 - wcx) / R, (y + 0.5 - wcy) / R
        d = math.hypot(x + 0.5 - wcx, y + 0.5 - wcy)
        if d <= Rd:
            if d >= Rd - 1.6 and not (a.win[0] <= x <= a.win[1] and a.win[2] <= y <= a.win[3]):   # the ticks
                t = (math.degrees(math.atan2(y + 0.5 - wcy, x + 0.5 - wcx)) + 360) % 30
                if t < 6 or t > 24:
                    return BLK
            return WHT
        if d <= Rd + 1.0:
            return BLK
        return bezel(x, y, ux, uy)
    a.blob(case, ink)
    if pos == "g":
        a.pattern(("WW", "W."), int(wcx - R * 0.62), int(wcy - R * 0.62))
    if pos == "s":                                  # the CLICK marks
        for (dx, dy) in ((-7, -3), (-8, -5), (6, -3), (7, -5), (0, -14), (0, -15)):
            a.put(fx + dx, cy_top + dy + 2, WHT)
    if pos in ("f", "g"):                           # the chequered RIBBON from the bow, down its left
        for k in range(12):
            for j in range(3):
                x, y = fx - 6 - k // 2 - j, cy_top - 6 + k
                if (x, y) not in case:
                    a.put(x, y, BLK if j == 2 or k == 11 else (WHT if (k // 2 + j) & 1 else BLK))
    return a.done(tops)


CONCEPTS = {
    "sign": [("signs", "s"), ("signh", "h"), ("signf", "f"), ("signg", "g")],
    "orb": [("orbr", "rubber"), ("orbh", "split"), ("orbs", "steel"), ("orbg", "glass")],
    "peng": [("pengs", "s"), ("pengh", "h"), ("pengf", "f"), ("pengg", "g")],
    "watch": [("watchs", "s"), ("watchh", "h"), ("watchf", "f"), ("watchg", "g")],
}
POSITIONS = ("start", "hub", "steel finish", "glass finish")
_DRAW = {"sign": _clock_sign, "orb": _clock_orb, "peng": _clock_peng, "watch": _clock_watch}


def install(B):
    """add the sixteen frames to bbcourse's styles, in this process only"""
    _bind(B)
    names = []
    for concept, vs in CONCEPTS.items():
        for name, arg in vs:
            B._CLOCK_DRAW[name] = (lambda f, a_: lambda p, x0, y0, tops: f(B, p, x0, y0, tops, a_))(
                _DRAW[concept], arg)
            names.append(name)
    B.CLOCK_STYLES = tuple(B.CLOCK_STYLES) + tuple(n for n in names if n not in B.CLOCK_STYLES)
    return names
