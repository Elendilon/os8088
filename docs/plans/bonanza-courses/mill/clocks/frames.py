# WINDMILL LANE's clock OPTIONS (course 4, the owner to pick; the brief is the course guide's G23, and
# ../../down/clocks/frames.py is the precedent this follows).
#
# Four concepts in the minigolf-windmill theme, each with a per-POSITION variant - the course's three clocks:
# the START (the tee's front-left corner), the TURNTABLE (a low pillar east of S) and the FINISH (the sandpit's
# front-left corner, by the cup) - so that "something on the clock represents where this is in the course" (the
# owner, DOWN's pick): the TEE, a QUARTER TURN, the CUP.  Drawn with the tool's own clock-frame machinery
# (bbcourse._ClockArt, round clock_face_geom's digits' blocks) in the course's inks: palette 1, CYN, MAG and WHT
# on black (MILL names no palette); on the Hercules CYN and MAG are one grey checker, so every form is carried by
# white and black as well.  The digits sit on WHITE in all four.
#
# This file is SOURCE for the tool, not a second copy of it: `install(B)` adds the twelve frames to bbcourse's
# CLOCK_STYLES and _CLOCK_DRAW in THIS process only (sheet.py and preview.py call it), so nothing in `make` and no
# shipped course moves.  The frame the owner picks is lifted into tools/bbcourse.py beside _clock_orb, its three
# names into CLOCK_STYLES, and the sketch's clocks name them per position.
import math

BLK = CYN = MAG = WHT = None


def _bind(B):
    global BLK, CYN, MAG, WHT
    BLK, CYN, MAG, WHT = B.BLK, B.CYN, B.MAG, B.WHT


def _in_win(a, x, y, m=1):
    wx0, wx1, wy0, wy1 = a.win
    return wx0 - m <= x <= wx1 + m and wy0 - m <= y <= wy1 + m


def _sail(B, a, hx, hy, ang, L, w, kind, keep=None, sq=1.0):
    """one windmill SAIL from the hub (HX, HY) at ANG degrees (screen: y down), L px long: a lit STOCK (the whip)
    and, on its trailing side, a lattice BLADE W px wide from 4 px out - KIND "cloth" (the sail spread: magenta
    cloth between white bars), "bare" (the lattice only, white bars, its cells left open) or "furled" (the cloth
    rolled along the stock: a white-and-black twist).  KEEP(x, y) false: not drawn (the digits' window), and the
    sail stops where its stock would first meet it.  SQ < 1 squashes the cross vertically: the sails' plane seen
    turned, so an X lies flatter"""
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    R = int(L + w + 2)
    if keep is not None:                            # the sail STOPS where its stock would meet what is kept clear
        for k in range(int(2 * L) + 1):
            u = k / 2.0
            if not keep(int(hx + u * c), int(hy + sq * u * s)):
                L = u - 1.0
                break
    stock, blade = set(), {}
    for y in range(int(hy) - R, int(hy) + R + 1):
        for x in range(int(hx) - R, int(hx) + R + 1):
            if keep is not None and not keep(x, y):
                continue
            dx, dy = x + 0.5 - hx, (y + 0.5 - hy) / sq
            u, v = dx * c + dy * s, -dx * s + dy * c
            if 0 <= u <= L and abs(v) <= 0.8:
                stock.add((x, y))
            elif kind == "furled" and 4 <= u <= L - 1 and 0.8 < v <= 2.4:
                blade[(x, y)] = (u, v)
            elif kind != "furled" and 4 <= u <= L and 0.8 < v <= w:
                blade[(x, y)] = (u, v)
    cells = set(blade)
    for (x, y), (u, v) in blade.items():
        edge = any((x + dx, y + dy) not in cells and (x + dx, y + dy) not in stock
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if kind == "furled":
            ink = BLK if edge else (WHT if int(u) % 3 else BLK)
        elif edge:
            ink = BLK
        elif int(u + 0.5) % 4 == 0 or v > w - 1.6:
            ink = WHT                               # the lattice's bars
        elif kind == "cloth":
            ink = MAG
        else:
            continue                                # (bare: the cell open)
        a.put(x, y, ink)
    for (x, y) in stock:
        a.put(x, y, WHT if (x + y) & 1 or kind == "cloth" else CYN)
    return stock


def _arc_marks(a, hx, hy, r, angs, sq=1.0, keep=None):
    """motion marks: a short white arc at radius R round (HX, HY) TRAILING each sail at ANGS (the cross turns
    clockwise), 12 - 36 degrees behind its tip"""
    for a0 in angs:
        for k in range(10):
            t = math.radians(a0 - 12 - k * 2.6)
            x, y = int(hx + r * math.cos(t)), int(hy + sq * r * math.sin(t))
            if keep is None or keep(x, y):
                a.put(x, y, WHT)


def _disc(B, a, x, y, rx, ry, arrow=True):
    """a TURNTABLE disc on the tile (paint, no geometry): white rim, magenta top, a quarter-turn arrow"""
    for (px, py) in B._ellipse(x, y, rx, ry, int(x - rx) - 1, int(x + rx) + 1, int(y - ry) - 1, int(y + ry) + 1):
        ux, uy = (px + 0.5 - x) / rx, (py + 0.5 - y) / ry
        d = ux * ux + uy * uy
        a.put(px, py, BLK if d > 0.78 else (WHT if d > 0.5 else MAG), "shadow")
    if arrow:                                       # the quarter turn, round the near rim, its head at the right
        for k in range(8):
            t = math.radians(110 - k * 9)
            a.put(int(x + 0.7 * rx * math.cos(t)), int(y + 0.7 * ry * math.sin(t)), BLK, "shadow")
        a.pattern(("K.", "KK", "K."), int(x + 0.7 * rx * math.cos(math.radians(40))),
                  int(y + 0.7 * ry * math.sin(math.radians(40))) - 1)


def _tee_peg(a, x, y):
    """the TEE's emblem, small: a white ball on a magenta peg, on the tile (geometry, 7 px tall)"""
    a.pattern((".KKK.", "KWWWK", "KWWCK", ".KKK.", "KMMMK", ".KMK.", ".KMK.", "..K.."), x - 2, y - 7)


# ---- A. MILL: a little smock WINDMILL, the digits on its gallery --------------------------------------------
# A tapering eight-sided tower on the tile (lit white at its left, magenta boarded with the dither, the right
# faces' dither, black facet lines), a door at its foot, a WHITE GALLERY round it that carries the digits, a boat
# cap and a hub; four sails in front of the cap, clear of the digits.  The cross is seen a little turned (SQ:
# the X lies flatter than square), which is what keeps its lower sails off the gallery's digits.  Per position
# (the designer's "whole at the start, split at the turntable, a flag pin at the finish"):
#   mills (start)   the sails WHOLE: four spread, magenta cloth in white lattice; a tee'd ball at the door
#   millt (turn)    the sails SPLIT and TURNING: on a little from the start's, two spread and two bare, white
#                   motion arcs behind their tips; the tower on a turntable disc painted with its quarter-turn arrow
#   millf (finish)  the sails STOPPED, their cloth furled along the stocks, and a FLAG PIN flying from the cap
_PENNANT = ("KKK.....", "KWWKK...", "KWMMWKK.", "KWMMMMMK", "KWMMDKK.", "KDDKK...", "KK......")


def _clock_mill(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1, wy0, wy1 = a.win
    if pos == "t":
        _disc(B, a, cx - 0.5, cy - 0.5, 13.5, 5.5)
    else:
        B._clock_top_shadow(a, 4, 11.0, 3.8)
    ttop = wy0 - 5                                  # the tower's top row (the cap's eave)
    tbot = cy - (2 if pos == "t" else 1)
    hw0, hw1 = 12.5, 9.5                            # its half widths at the foot and the top

    def hw(y):
        return hw1 + (hw0 - hw1) * (y - ttop) / float(tbot - ttop)
    tower = {(x, y) for y in range(ttop, tbot + 1) for x in range(int(fx - hw(y) - 0.5), int(fx + hw(y) + 0.5))}

    def tink(x, y):
        u = (x + 0.5 - fx) / hw(y)
        if abs(abs(u) - 0.42) < 0.07:
            return BLK                              # the facet lines
        if u < -0.72:
            return WHT                              # the rim of light
        if u > 0.42:
            return MAG if (x + y) & 1 else BLK
        return MAG
    a.blob(tower, tink)
    for y in range(tbot - 8, tbot + 1):             # the DOOR, an arch at its foot
        for x in range(fx - 3, fx + 3):
            if y > tbot - 7 or (x in (fx - 2, fx - 1, fx, fx + 1) and y == tbot - 7) or \
                    (x in (fx - 1, fx) and y == tbot - 8):
                a.put(x, y, BLK)
    gy0, gy1 = wy0 - 2, wy1 + 2                     # the GALLERY: wider than the tower, white, the digits on it
    gal = {(x, y) for y in range(gy0, gy1 + 1) for x in range(wx0 - 4, wx1 + 5)}
    a.blob(gal, lambda x, y: (MAG if (x + y) & 1 else WHT) if x >= wx1 + 3 or (y == gy1 - 1 and x > wx1) else WHT)
    for x in range(wx0 - 3, wx1 + 4, 3):            # the gallery's rail posts under it
        a.put(x, gy1 + 1, BLK)
        a.put(x, gy1 + 2, BLK)
    capt = ttop - 8                                 # the CAP: a boat roof, lit at its left
    cap = {(x, y) for (x, y) in B._ellipse(fx - 0.5, ttop + 1.0, hw1 + 2.5, 9.0, int(fx - hw1) - 4,
                                             int(fx + hw1) + 4, capt - 2, ttop) if y <= ttop}
    a.blob(cap, lambda x, y: WHT if x < fx - 3 else (MAG if x < fx + 4 else (MAG if (x + y) & 1 else BLK)))
    hx, hy = fx - 0.5, ttop - 5.5                   # the HUB, high on the cap's face
    keep = (lambda x, y: not _in_win(a, x, y, 1))
    L, w, sq = 20.0, 5.0, 0.8
    if pos == "s":
        sails = [(ang, "cloth") for ang in (45, 135, 225, 315)]
    elif pos == "t":
        sails = [(33, "cloth"), (123, "bare"), (213, "cloth"), (303, "bare")]
    else:
        sails = [(ang, "furled") for ang in (45, 135, 225, 315)]
    for ang, kind in sails:
        _sail(B, a, hx, hy, ang, L, w, kind, keep, sq)
    a.pattern(("KKK", "KWK", "KKK"), int(hx) - 1, int(hy) - 1)
    if pos == "t":
        _arc_marks(a, hx, hy, L + 3, [ang for ang, _k in sails], sq, keep)
    if pos == "s":
        _tee_peg(a, fx - 8, tbot + 1)
    if pos == "f":                                  # the FLAG PIN on the cap: a pole and a pennant flying right
        top = capt - 12
        for y in range(top, capt):
            a.put(int(hx) + 3, y, BLK)
            a.put(int(hx) + 4, y, WHT)
        a.pattern(_PENNANT, int(hx) + 5, top)
    return a.done(tops)


# ---- B. VASE: a DELFT TULIP VASE on a pedestal, the digits on its belly ------------------------------------
# A Delftware vase on a short lit pedestal: white glaze, a cyan (Delft blue) pattern of bands and leaves at its
# shoulder and foot, the shade dithered cyan down its right; its belly's white field, framed in a fine cyan line,
# carries the digits.  Out of its neck come TULIPS on cyan stems, magenta heads lit white.  Per position the bulbs
# GROW down the course:
#   vases (start)   ONE closed bud with a leaf, and a little tee'd ball at the pedestal's foot
#   vaset (turn)    TWO: a bud and one OPENING, and the pedestal on a turntable disc with its quarter-turn arrow
#   vasef (finish)  THREE in full BLOOM, the middle one the tallest
_TULIPS = (("...KK...", "..KMWK..", ".KMMWMK.", ".KMMMDK.", ".KMMMDK.", "..KMDK..", "...KK..."),
           (".K....K.", "KWK..KMK", "KWMKKMDK", "KWMWMMDK", ".KMWMDK.", "..KMDK..", "...KK..."),
           ("K.K..K.K", "WKWKKMKD", "KWMWMMDK", "KWMWMMDK", "KMMWMMDK", ".KMMMDK.", "..KKKK.."))


def _clock_vase(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1, wy0, wy1 = a.win
    if pos == "t":
        _disc(B, a, cx - 0.5, cy - 0.5, 13.5, 5.5)
    else:
        B._clock_top_shadow(a, 4, 11.0, 3.8)
    bot = cy - (2 if pos == "t" else 1)
    ped = bot - 9                                   # the PEDESTAL's top row (the vase's foot stands on it)
    neck = wy0 - 5
    lip = neck - 2
    bel = fy                                        # the belly's widest row

    def half(y):                                    # the vase's half width on row Y
        if y <= lip:
            return 7.0                              # the lip
        if y <= neck:
            return 5.0
        if y >= ped - 2:
            return 7.5                              # its foot ring
        if y <= bel:
            return 5.0 + 9.5 * math.sin(0.5 * math.pi * (y - neck) / float(bel - neck))
        return 7.0 + 7.5 * math.cos(0.5 * math.pi * (y - bel) / float(ped - 2 - bel))
    stems = {"s": [(0, 0, 9, 0)], "t": [(-3, -2, 8, 0), (3, 2, 11, 1)],
             "f": [(-5, -3, 7, 2), (0, 0, 11, 2), (5, 3, 8, 2)]}[pos]
    for (sx, lean, ln, stage) in stems:             # the STEMS and HEADS, behind the neck: drawn first
        for k in range(ln + 1):
            x = fx + sx + int(round(lean * k / float(ln)))
            y = lip - k
            a.put(x - 1, y, BLK)
            a.put(x, y, CYN)
            a.put(x + 1, y, BLK)
        a.pattern(_TULIPS[stage], fx + sx + lean - 4, lip - ln - 6)
    if pos == "s":                                  # a LEAF on the bud's stem
        a.pattern(("KK...", "KCCK.", ".KCCK", "..KK."), fx - 5, lip - 6)
    pedc = {(x, y) for y in range(ped, bot + 1) for x in range(fx - (7 if y >= bot - 1 else 5),
                                                               fx + (7 if y >= bot - 1 else 5))}
    a.blob(pedc, B._lit3(fx - 6, fx + 4))
    vase = {(x, y) for y in range(lip, ped) for x in range(int(fx - half(y) - 0.5), int(fx + half(y) + 0.5))}

    def ink(x, y):
        u = (x + 0.5 - fx) / half(y)
        if _in_win(a, x, y, 1):
            return WHT
        if y in (lip + 1, wy0 - 3, wy1 + 3, ped - 2):
            return CYN                              # the bands
        if y == neck + 1 and x & 1:
            return CYN
        if wy1 + 5 <= y <= ped - 4 and (x - fx) % 4 == 0 and u > -0.6:
            return CYN                              # the flutes round its foot
        if u < -0.55:
            return WHT                              # the shine
        if u > 0.6:
            return CYN if (x + y) & 1 else WHT      # the shade
        return WHT
    a.blob(vase, ink)
    for x in range(wx0 - 1, wx1 + 2):               # the field's fine cyan frame round the digits
        for y in (wy0 - 1, wy1 + 1):
            a.put(x, y, CYN)
    if pos == "s":
        _tee_peg(a, fx + 11, bot + 1)
    return a.done(tops)


# ---- C. FLAG: the HOLE FLAG, the digits on its cloth --------------------------------------------------------
# The mini-golf flag, but the digits ON THE CLOTH (First Roll's `pin` hangs a plate on its pole): a banded pole
# with a knob, and a big white flag flying from it, black-edged, its free end rippling, with a magenta FLY that
# carries a little WINDMILL - four white sails - set by where the clock is.  The digits are block-aligned and the
# pole is at the cloth's edge, so the pole stands near the tile's corner.  Per position:
#   flags (start)   the pole beside the tee's two markers (paint on the tile); the emblem's sails an X
#   flagt (turn)    the flag flying the OTHER way (a quarter turn round, to the left), the emblem's sails a +,
#                   and a turntable disc on the tile under it with its quarter-turn arrow
#   flagf (finish)  the pole in the CUP, a ball at its lip, sand dithered round the hole; the sails an X
def _clock_flag(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1, wy0, wy1 = a.win
    left = pos == "t"                               # the flag flies to the left (the pole at its right)
    X0, X1, Y0, Y1 = wx0 - 2, wx1 + 2, wy0 - 3, wy1 + 3
    fly = 11
    if left:
        X0 -= fly
        px = X1 + 2
    else:
        X1 += fly
        px = X0 - 2

    def ontile(x, y, m=0.95):
        return abs(x + 0.5 - cx) / 16.0 + abs(y + 0.5 - cy) / 8.0 <= m
    if pos == "t":
        _disc(B, a, cx - 0.5, cy - 0.5, 11.5, 5.0)
    else:
        for (x, y) in B._ellipse(px + 6, cy + 1.5, 9.0, 2.6, px - 4, px + 16, cy - 3, cy + 5):
            if ontile(x, y) and (x + y) & 1:
                a.put(x, y, BLK, "shadow")          # the shadow, on the tile
    if pos == "f":                                  # the CUP: sand dithered round the hole
        for (x, y) in B._ellipse(px + 0.5, cy + 0.5, 7.5, 3.2, px - 8, px + 9, cy - 4, cy + 5):
            if ontile(x, y) and (x + y) & 1:
                a.put(x, y, WHT, "shadow")
        for (x, y) in B._ellipse(px + 0.5, cy + 0.5, 3.5, 1.6, px - 4, px + 5, cy - 2, cy + 3):
            a.put(x, y, BLK, "shadow")
    top = Y0 - 5
    for y in range(top, cy + 1):                    # the POLE, banded every 3 px
        band = ((cy - y) // 3) & 1
        a.put(px - 1, y, BLK)
        a.put(px, y, WHT if band else MAG)
        a.put(px + 1, y, BLK)
    a.pattern((".KK.", "KWWK", "KWMK", ".KK."), px - 1, top - 3)    # the knob

    def free(x):                                    # px into the free end, past the digits
        return (x - wx1 - 2) if not left else (wx0 - 2 - x)

    def wave(x):
        f = free(x)
        return 0 if f <= 0 else int(round(1.6 * math.sin(f * 0.55)))
    cloth = set()
    for x in range(X0, X1 + 1):
        for y in range(Y0 + wave(x), Y1 + wave(x) + 1):
            cloth.add((x, y))
    hem = fly - 1                                   # the FLY: its magenta field

    def ink(x, y):
        if _in_win(a, x, y, 1):
            return WHT
        f = free(x)
        if f >= 2 and f <= hem:
            return MAG
        if y >= Y1 + wave(x) - 1 and (x + y) & 1:
            return MAG                              # the lower edge's dither
        return WHT
    a.blob(cloth, ink)
    for y in range(Y0, Y1 + 1):                     # the cloth's sleeve round the pole
        a.put(px + (1 if not left else -1), y, BLK)
    ex = (X1 - fly // 2 - 1) if not left else (X0 + fly // 2 + 1)     # the emblem: the windmill on the fly
    ey = (Y0 + Y1) // 2 + wave(ex)
    ang0 = 0 if pos == "t" else 45
    for k in range(4):
        t = math.radians(ang0 + 90 * k)
        for r in range(1, 5 if pos == "t" else 4):
            a.put(int(round(ex + r * math.cos(t))), int(round(ey + r * math.sin(t))), WHT)
    a.put(ex, ey, BLK)
    if pos == "s":                                  # the TEE: two tee MARKERS, flat on the tile (paint: a tee'd
        for mx, my in ((px + 7, cy - 1), (px + 15, cy + 2)):    # ball here was a 5th occluder record in a block)
            for j, r in enumerate((".KK.", "KWMK", ".KK.")):
                for i, ch in enumerate(r):
                    if ch != ".":
                        a.put(mx - 2 + i, my - 1 + j, {"K": BLK, "W": WHT, "M": MAG}[ch], "shadow")
    if pos == "f":                                  # a BALL at the cup's lip
        a.pattern((".KKK.", "KWWWK", "KWWCK", ".KKK."), px + 4, cy - 3)
    return a.done(tops)


# ---- D. WHEEL: the windmill's SAIL CROSS on a post, the digits on its hub ----------------------------------
# The mill's head alone, as a garden windmill: a lit post on a collar, and on it the sail cross - a big round
# white HUB BOARD (black rimmed, its lower right in the dither) carrying the digits, four lattice sails round it
# and the cap peeking over it.  The hub carries the digits, so the sails are free to turn anywhere: per position
# the cross is where the course is:
#   wheels (start)  an X, four sails spread, a tee'd ball at the post's foot
#   wheelt (turn)   TURNING, most of a quarter on: two sails spread and two bare, white motion arcs behind their
#                   tips, the post on a turntable disc with its quarter-turn arrow
#   wheelf (finish) an X, the sails furled, a pennant flying from the cap's top
def _clock_wheel(B, p, x0, y0, tops, pos):
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    if pos == "t":
        _disc(B, a, cx - 0.5, cy - 0.5, 11.5, 5.0)
    else:
        B._clock_top_shadow(a, 4, 9.0, 3.2)
    hx, hy = fx - 0.5, fy - 0.5
    hrx, hry = 4 * n + 5.0, 9.0
    for (x, y) in B._ellipse(cx - 0.5, cy - 1.0, 5.0, 2.2, cx - 6, cx + 6, cy - 4, cy + 2):   # the collar
        a.put(x, y, BLK if y >= cy or x in (cx - 5, cx + 4) else (WHT if x < cx - 1 else MAG))
    a.column(cx - 2, int(hy + hry) - 1, cy - 2)
    capt = int(hy - hry) - 5                        # the CAP behind the hub's top
    cap = {(x, y) for (x, y) in B._ellipse(hx, hy - hry + 3, 8.5, 8.0, int(hx) - 10, int(hx) + 10, capt - 2,
                                             int(hy)) if y <= int(hy - hry) + 2}
    a.blob(cap, lambda x, y: WHT if x < hx - 3 else (MAG if x < hx + 3 else (MAG if (x + y) & 1 else BLK)))
    hub = B._ellipse(hx, hy, hrx, hry, int(hx - hrx) - 1, int(hx + hrx) + 1, int(hy - hry) - 1, int(hy + hry) + 1)
    L, w = 23.0, 5.0
    if pos == "s":
        sails = [(ang, "cloth") for ang in (45, 135, 225, 315)]
    elif pos == "t":
        sails = [(20, "cloth"), (110, "bare"), (200, "cloth"), (290, "bare")]
    else:
        sails = [(ang, "furled") for ang in (45, 135, 225, 315)]
    for ang, kind in sails:                         # (round the hub: drawn first, the hub over their roots)
        _sail(B, a, hx, hy, ang, L, w, kind)
    if pos == "t":
        _arc_marks(a, hx, hy, L + 2, [ang for ang, _k in sails])

    def ink(x, y):
        ux, uy = (x + 0.5 - hx) / hrx, (y + 0.5 - hy) / hry
        if ux * ux + uy * uy > 0.80:
            return BLK if ux + uy > -0.9 else WHT
        if _in_win(a, x, y, 0):
            return WHT
        return (MAG if (x + y) & 1 else WHT) if ux + uy > 0.85 else WHT
    a.blob(hub, ink)
    if pos == "s":
        _tee_peg(a, cx + 9, cy + 1)
    if pos == "f":                                  # the PENNANT from the cap's top
        top = capt - 11
        for y in range(top, capt + 1):
            a.put(int(hx), y, BLK)
            a.put(int(hx) + 1, y, WHT)
        a.pattern(_PENNANT, int(hx) + 2, top)
    return a.done(tops)


CONCEPTS = {
    "mill": [("mills", "s"), ("millt", "t"), ("millf", "f")],
    "vase": [("vases", "s"), ("vaset", "t"), ("vasef", "f")],
    "flag": [("flags", "s"), ("flagt", "t"), ("flagf", "f")],
    "wheel": [("wheels", "s"), ("wheelt", "t"), ("wheelf", "f")],
}
POSITIONS = ("start", "turntable", "finish")
_DRAW = {"mill": _clock_mill, "vase": _clock_vase, "flag": _clock_flag, "wheel": _clock_wheel}


def install(B):
    """add the twelve frames to bbcourse's styles, in this process only"""
    _bind(B)
    names = []
    for concept, vs in CONCEPTS.items():
        for name, arg in vs:
            B._CLOCK_DRAW[name] = (lambda f, a_: lambda p, x0, y0, tops: f(B, p, x0, y0, tops, a_))(
                _DRAW[concept], arg)
            names.append(name)
    B.CLOCK_STYLES = tuple(B.CLOCK_STYLES) + tuple(n for n in names if n not in B.CLOCK_STYLES)
    return names
