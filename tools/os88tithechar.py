#!/usr/bin/env python3
"""TITHE's CHARACTERS as LAYERS - a body, and an item in the near hand.

    python3 tools/os88tithechar.py sheet        # build/tithe-chars.png
    python3 tools/os88tithechar.py emit         # apps/tithe/tiart.inc + build/tiart.bin
    python3 tools/os88tithechar.py --selfcheck

A CHARACTER IS COMPOSED, NOT DRAWN (TITHE-PLAN 4.2.1, SPEC.md 97.4.9). A card
names a BODY - the person, less the near arm - and two ITEMS: the one it
carries in the FRONT column and the one it carries at the REAR. "The same man
with a different tool" is one body and two items, and an ATTACK is the item's
own four frames over the body's first pose. So a pose is never drawn per
character: sixty characters are ~60 bodies and a few dozen items, and every
attack in the game is the items'.

PIXEL ART, in three states a pixel - '#' ink, 'o' black and opaque, '.'
nothing - and so a figure is INK AND MASK, composed at layout as
`(band AND NOT mask) OR ink`: the body's figure, with its halo, then the
item's frame, with a one-pixel black RING that parts it from the torso it is
held in front of. A frame still commits one opaque band a feature, and the
detail costs it nothing.

THE ANCHOR IS THE NEAR SHOULDER, and a body answers it per pose: it may move
UP AND DOWN with the body (the Ember rises and falls) and never sideways,
because the body is placed so its anchor lands on a BYTE and the machine puts
every item frame down in whole bytes from there. The selfcheck refuses an
anchor that leaves the grid.

THE CUT, per surface: bodies and items are reduced per LAYER to Hercules and
the card minis, the outlines re-drawn at the target size; CGA's bodies are
DRAWN again at 17 rows and its items are cut.

WHAT IS EMITTED IS A PART (SPEC.md 20.12), build/tiart.bin, and the offsets the
package reads it by in apps/tithe/tiart.inc. The art is not in the image any
more: a package's image and bss cap at 60KB together, and layered art for even
seven cards does not fit beside the program (TITHE-PLAN 4.3).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from os88tithebase import Sheet, WHITE, GREY          # noqa: E402

T, I, K = 0, 1, 2                                   # nothing, ink, black

# The FIGURE band, out of ti_geo_*'s BW and BH, and the MINI UNIT that rides a
# card (TI_UNITW by ti_unith). (name, w, h, pixel aspect)
# THREE BOARD SURFACES, the VGA fullscreen one DELETED: fullscreen VGA takes the
# windowed board (SPEC.md 97.4.12), so its 64 x 48 figures were reached by
# nothing. The unit surfaces follow the board's in the same order, because the
# package reads a unit record at TI_CHAR_BG + its surface.
SURFACES = [
    ("vga",      64, 44, 1.00),
    ("herc",     64, 32, 1.55),
    ("cga",      64, 18, 2.40),
    ("unit-vga",      24, 26, 1.00),
    ("unit-herc",     24, 18, 1.55),
    ("unit-cga",      24,  7, 2.40),
]
BOARD_G = 3                     # the first three are the BOARD's
POSES = 4                       # a ping-pong idle: A B C B (SPEC.md 97.5)
MW, MH = 28, 42                 # the MASTER canvas every figure is drawn on
MARGIN = 3                      # columns each side a board figure may not
                                # light: the stat column begins two past it


def ppose(p):
    """The ping-pong for a 4-pose idle: 0, 1, 2, 1 -> 0, -1, 0, +1."""
    return (0, -1, 0, 1)[p]


def parse(s):
    rows = [r.rstrip() for r in s.strip("\n").split("\n")]
    w = max(len(r) for r in rows)
    return [[{".": T, "#": I, "o": K}[c] for c in r.ljust(w, ".")]
            for r in rows]


def reduce_art(g, sx, sy):
    """A layer cut to (sx, sy) of its size: each target pixel is the box of
    master pixels it covers, and the vote keeps a DARK DETAIL LINE where one
    crosses the box - a nearest-neighbour cut drops a one-pixel line about as
    often as it keeps it, and those lines are the whole of 1bpp detail."""
    if sx == 1 and sy == 1:
        return g
    h, w = len(g), len(g[0])
    th, tw = max(1, int(round(h * sy))), max(1, int(round(w * sx)))
    out = []
    for ty in range(th):
        y0 = int(ty * h / th)
        y1 = max(y0 + 1, int((ty + 1) * h / th))
        row = []
        for tx in range(tw):
            x0 = int(tx * w / tw)
            x1 = max(x0 + 1, int((tx + 1) * w / tw))
            cells = [g[y][x] for y in range(y0, y1) for x in range(x0, x1)]
            nt, ni, nk = cells.count(T), cells.count(I), cells.count(K)
            if nt * 2 > len(cells):
                row.append(T)
            elif nk and ni and nk * 4 >= len(cells):
                row.append(K)
            elif ni >= nk:
                row.append(I)
            else:
                row.append(K)
        out.append(row)
    return out


class Fig:
    """A figure being put together at one scale. Every coordinate and every
    offset is in MASTER pixels and is scaled here, so a character is written
    once and drawn at every surface."""

    def __init__(self, sx, sy, mw=MW, mh=MH):
        self.sx, self.sy = sx, sy
        self.w = max(1, int(round(mw * sx)))
        self.h = max(1, int(round(mh * sy)))
        self.px = [[T] * self.w for _ in range(self.h)]
        self._cache = {}

    def X(self, v):
        return int(round(v * self.sx))

    def Y(self, v):
        return int(round(v * self.sy))

    def dy(self, v):
        """A MOTION in y: scaled, but never to nothing - an idle that loses its
        motion at a small size is a still picture that costs a pose."""
        if v == 0:
            return 0
        s = int(round(v * self.sy))
        return s if s else (1 if v > 0 else -1)

    def dx(self, v):
        if v == 0:
            return 0
        s = int(round(v * self.sx))
        return s if s else (1 if v > 0 else -1)

    def art(self, g):
        k = id(g)
        if k not in self._cache:
            self._cache[k] = reduce_art(g, self.sx, self.sy)
        return self._cache[k]

    def put(self, g, x, y, outline=False, ox=0, oy=0):
        """Layer `g` at master (x, y) plus a scaled motion (ox, oy) - OUTLINED
        against what is under it when asked, which is what separates a shield
        from the torso it is held in front of."""
        a = self.art(g)
        x, y = self.X(x) + self.dx(ox), self.Y(y) + self.dy(oy)
        if outline:
            for yy, row in enumerate(a):
                for xx, v in enumerate(row):
                    if v == T:
                        continue
                    for ddy in (-1, 0, 1):
                        for ddx in (-1, 0, 1):
                            ay, ax = yy + ddy, xx + ddx
                            if 0 <= ay < len(a) and 0 <= ax < len(a[0]) \
                                    and a[ay][ax] != T:
                                continue
                            self._set(x + ax, y + ay, K)
        for yy, row in enumerate(a):
            for xx, v in enumerate(row):
                if v != T:
                    self._set(x + xx, y + yy, v)

    def line(self, x0, y0, x1, y1, ox=0):
        x0, y0 = self.X(x0), self.Y(y0)
        x1, y1 = self.X(x1) + self.dx(ox), self.Y(y1)
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(n + 1):
            self._set(int(round(x0 + (x1 - x0) * i / n)),
                      int(round(y0 + (y1 - y0) * i / n)), I)

    def _set(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = v

    def halo(self):
        out = [r[:] for r in self.px]
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] != T:
                    continue
                for ddy in (-1, 0, 1):
                    for ddx in (-1, 0, 1):
                        yy, xx = y + ddy, x + ddx
                        if 0 <= yy < self.h and 0 <= xx < self.w \
                                and self.px[yy][xx] == I:
                            out[y][x] = K
        self.px = out



def ring(g):
    """`g` with a one-pixel BLACK ring round everything it draws - the item's
    own outline, which separates it from the body it is held in front of and
    haloes it over the ground in the same stroke."""
    h, w = len(g), len(g[0])
    out = [[T] * (w + 2) for _ in range(h + 2)]
    for y in range(h):
        for x in range(w):
            if g[y][x] == T:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if out[y + 1 + dy][x + 1 + dx] == T:
                        out[y + 1 + dy][x + 1 + dx] = K
    for y in range(h):
        for x in range(w):
            if g[y][x] != T:
                out[y + 1][x + 1] = g[y][x]
    return out


# =============================================================================
# THE BODIES - the person, less the NEAR arm, which is the item's
#
# A body draws its layers and answers its ANCHOR for the pose: the near
# shoulder, where an item's arm begins. The anchor may move VERTICALLY with
# the pose (the Ember rises and falls) and never sideways, because the machine
# puts an item down in whole bytes from it (SPEC.md 97.4.9).
# =============================================================================

B_HEAD = parse("""
...####...
.########.
##########
##########
oooooooooo
.#oo##oo#.
.########.
.##oooo##.
..######..
""")

B_BODY = parse("""
..############..
.##############.
################
###o########o###
##o#o#o#o#o#o#o#
################
###o#o#o#o#o#o##
################
##o#o#o#o#o#o#o#
################
###o#o#o#o#o#o##
oooooooooooooooo
#######oo#######
oooooooooooooooo
.##############.
.######o#######.
.######o#######.
.######o#######.
.#####ooo######.
..####o..o####..
..#####..#####..
..#####..#####..
..#####..#####..
..#####..#####..
..#####..#####..
..#####..#####..
..#####..#####..
.######..######.
.######..######.
""")

B_OFF = parse("""
..##
.###
.###
.###
####
###.
###.
###.
###.
.##.
.##.
.###
""")


def b_soldier(f, p):
    pp = ppose(p)
    f.put(B_OFF, 1, 11)
    f.put(B_BODY, 5, 10, True)
    f.put(B_HEAD, 8, 1, True, ox=-pp)          # the head rocks a pixel
    return (19, 12, 0)


E_UPPER = parse("""
........#.........
.......###........
......#####.......
.....#######......
....####o####.....
....###ooo###.....
...###ooooo###....
...##oo#o#oo##....
...##ooooooo##....
...###ooooo###....
..#####ooo#####...
..#############...
.###############..
.#######o#######..
.######o#o######..
.######o#o######..
.#####o#o#o#####..
.#####o###o#####..
.######o#o######..
.#######o#######..
.################.
.################.
.################.
.################.
.################.
.################.
.################.
.################.
##################
""")

E_HEM = parse("""
##################
##################
##################
###################
###################
####################
#o###o####o###o####.
.#.#.#.##.#.#.##.#..
""")

E_SHADOW = parse("""
..#.#.#.#.#.#.#.#..
.#.#.#.#.#.#.#.#.#.
""")


def b_hooded(f, p):
    dy = ppose(p) * 2
    f.put(E_UPPER, 3, 2, oy=dy)                # everything above the hem...
    f.put(E_HEM, 2, 27)                        # ...and the hem, which never
    f.put(E_SHADOW, 2, 38)                     # moves, over its own shadow
    return (15, 16, dy)                        # ...and the arm rises with it


C_BODY = parse("""
.....######.....
....#oooooo#....
...#oo####oo#...
...#o######o#...
...#o#o##o#o#...
...#o######o#...
..#oo##oo##oo#..
..#o########o#..
.#o##########o#.
.#o####oo####o#.
.#o###oooo###o#.
.##############.
.##############.
.######oo######.
.#####oooo#####.
.######oo######.
.######oo######.
.##############.
.oooooooooooooo.
.##############.
.####o####o####.
####o######o####
####o######o####
####o######o####
###o########o###
###o########o###
###o########o###
##o##########o##
##o##########o##
##o##########o##
################
################
""")


def b_nun(f, p):
    f.put(C_BODY, 3, 6)
    return (15, 17, 0)


# --- and the CGA bodies, DRAWN for the surface ------------------------------
# A CGA pixel is 2.4 times as tall as it is wide, so a board figure there is
# 17 ROWS, and the per-layer reduction that holds up on a Hercules turns a
# helm, a face and a hood into one dark blob at that height. So CGA's BODIES
# are drawn again at their own size, 1:1, with the same motion in CGA pixels -
# and its ITEMS are not: an item is small already and its cut holds, which is
# TITHE-PLAN 4.2.4's "the items, being small already, cut cleanly".
CW_, CH_ = 26, 17

BC_HEAD = parse("""
.####.
######
oooooo
#o##o#
.####.
""")
BC_BODY = parse("""
.##########.
############
##o#o#o#o###
############
oooooooooooo
.##########.
.####o#####.
.###o.o####.
.###...####.
.###...####.
####...#####
""")
BC_OFF = parse("""
.##
###
##.
##.
##.
.#.
""")


def c_soldier(f, p):
    pp = ppose(p)
    f.put(BC_OFF, 4, 6)
    f.put(BC_BODY, 6, 5, True)
    f.put(BC_HEAD, 9, 0, True, ox=-pp)
    return (16, 6, 0)


EC_UPPER = parse("""
.....#......
....###.....
...##o##....
..##o#o##...
..###o###...
..#######...
.#########..
.####o####..
.###o#o###..
.#########..
.#########..
.#########..
###########.
""")
EC_HEM = parse("""
############
############
#o##o##o##o#
.#.#.#.#.#..
""")


def c_hooded(f, p):
    dy = ppose(p)
    f.put(EC_UPPER, 6, 0, oy=dy)
    f.put(EC_HEM, 6, 12)
    return (14, 6, dy)


CC_BODY = parse("""
...####...
..#oooo#..
.#o####o#.
.#o#oo#o#.
.#oo##oo#.
#o######o#
##########
####oo####
####oo####
oooooooooo
##########
###o##o###
##o####o##
##o####o##
#o######o#
##########
""")


def c_nun(f, p):
    f.put(CC_BODY, 7, 1)
    return (15, 6, 0)


BODIES = [
    ("soldier", b_soldier, c_soldier),
    ("hooded",  b_hooded,  c_hooded),
    ("nun",     b_nun,     c_nun),
]


# =============================================================================
# THE ITEMS - the NEAR arm and what is in it (TITHE-PLAN 4.2.1)
#
# An item is eight frames - four of IDLE, a ping-pong like the body's, and
# four of ATTACK - each an (art, gx, gy) placed with its top-left at the body's
# anchor plus (gx, gy), in master pixels. The arm is the item's and not the
# body's, which is the decision that makes the layer model work: a swing moves
# an arm, so an arm that is part of the weapon can swing against any torso.
# The attack's fourth frame is the idle's first, so an attack comes home.
# =============================================================================

I_SHIELD = parse("""
###########
#ooooooooo#
#o#######o#
#o###o###o#
#o###o###o#
#o#ooooo#o#
#o###o###o#
#o###o###o#
#o#######o#
.#o#####o#.
.#o#####o#.
..#o###o#..
...#o#o#...
....#o#....
.....#.....
""")


def it_shield():
    idle = [(I_SHIELD, -4, 1, 0, ppose(p) * 2) for p in range(POSES)]
    # A SHOVE: the shield driven forward and back - a bash is the shield's
    # own attack, and it is the Bulwark's
    atk = [(I_SHIELD, -4, 1, 1, -1), (I_SHIELD, -4, 1, 3, -1),
           (I_SHIELD, -4, 1, 2, 0), (I_SHIELD, -4, 1, 0, 0)]
    return idle, atk


I_SWORD = parse("""
......#..
......##.
......##.
......##.
......##.
......##.
......##.
......##.
......##.
###...##.
###...##.
###...##.
###.#####
###...#..
.###.###.
..#######
...####..
""")
I_SWORD_UP = parse("""
#........
##.......
.##......
..##.....
...##....
....##...
.....###.
....####.
...###...
###......
###......
###......
###......
.##......
""")
I_SWORD_CUT = parse("""
.........#...........
#########o###########
#########o###########
#########o...........
.........#...........
""")
I_SWORD_LOW = parse("""
###.......
####......
.#####....
..######..
.....###..
....#.##..
......##..
.......##.
........##
.........#
""")


def it_sword():
    idle = [(I_SWORD, 0, -9, 0, ppose(p)) for p in range(POSES)]
    atk = [(I_SWORD_UP, 0, -9, 0, 0), (I_SWORD_CUT, 0, -1, 0, 0),
           (I_SWORD_LOW, 0, 0, 0, 0), (I_SWORD, 0, -9, 0, 0)]
    return idle, atk


def _bow(string, arrow):
    """A bow held out at arm's length: belly forward at column 12, the string
    at `string` - drawn back for the attack - and an arrow on it or not."""
    rows = []
    for y in range(17):
        r = ["."] * 16
        d = abs(y - 8)
        belly = 12 - (d * d) // 16                # the limbs curve back
        r[belly] = "#"
        if d == 8:
            r[belly - 1] = "#"
        sx = string + (8 - d) * 0 if d == 8 else string + ((12 - string) * d) // 8
        if 0 <= sx < 16 and sx != belly:
            r[sx] = "#"
        if y in (7, 8):                           # the arm, to the grip
            for x in range(0, belly):
                if r[x] == ".":
                    r[x] = "#"
        if arrow and y == 6:
            for x in range(string, min(16, belly + 4)):
                r[x] = "#"
        rows.append("".join(r))
    return parse("\n".join(rows))


I_BOW = _bow(9, False)
I_BOW_DRAW = _bow(6, True)
I_BOW_FULL = _bow(3, True)
I_BOW_LOOSE = _bow(10, False)


def it_bow():
    idle = [(I_BOW, 0, -7, 0, ppose(p)) for p in range(POSES)]
    atk = [(I_BOW_DRAW, 0, -7, 0, 0), (I_BOW_FULL, 0, -7, 0, 0),
           (I_BOW_LOOSE, 0, -7, 1, 0), (I_BOW, 0, -7, 0, 0)]
    return idle, atk


I_FORK = parse("""
....#.#.#.
....#.#.#.
....#.#.#.
....#####.
......#...
......#...
......#...
......#...
......#...
......#...
##....#...
###...#...
###...#...
.###..#...
..######..
...####...
......#...
......#...
......#...
......#...
......#...
......#...
......#...
......#...
......#...
......#...
......#...
""")
I_FORK_JAB = parse("""
.......#.#.#
.......#.#.#
.......#.#.#
.......#####
.........#..
.........#..
.........#..
.........#..
.........#..
##.......#..
####.....#..
.#####...#..
...#######..
.....###.#..
.........#..
.........#..
.........#..
.........#..
.........#..
.........#..
.........#..
.........#..
""")


def it_fork():
    idle = [(I_FORK, 0, -10, 0, ppose(p)) for p in range(POSES)]
    atk = [(I_FORK, 0, -10, -1, -1), (I_FORK_JAB, 0, -12, 0, 0),
           (I_FORK_JAB, 0, -12, 0, 1), (I_FORK, 0, -10, 0, 0)]
    return idle, atk


I_STAFF = parse("""
.....###.
....#o#o#
....##o##
....#o#o#
.....###.
......#..
......#..
......#..
......#..
......#..
......#..
##....#..
###...#..
###...#..
.###..#..
..######.
...####..
......#..
......#..
......#..
......#..
......#..
......#..
......#..
......#..
......#..
......#..
......#..
""")
I_STAFF_UP = parse("""
#...#...#
.#..#..#.
..#####..
.#.#o#.#.
####o####
.#.#o#.#.
..#####..
.#..#..#.
#...#...#
......#..
......#..
##....#..
###...#..
###...#..
.###..#..
..######.
...####..
......#..
......#..
......#..
......#..
......#..
......#..
""")


def it_staff():
    idle = [(I_STAFF, 0, -11, 0, ppose(p)) for p in range(POSES)]
    atk = [(I_STAFF, 0, -11, 0, -2), (I_STAFF_UP, 0, -15, 0, 0),
           (I_STAFF_UP, 0, -15, 0, 1), (I_STAFF, 0, -11, 0, 0)]
    return idle, atk


I_WISP_ARM = parse("""
........#.#
........###
.......####
....######.
..#######..
#####o##...
####o......
###o.......
##o........
""")


def _wisp(n, reach=0):
    """The raised hand and its flame: `n` is the flame's size, `reach` how far
    forward the hand has thrust it."""
    g = [r[:] for r in I_WISP_ARM]
    w = len(g[0]) + reach + 8
    g = [[T] * w for _ in range(8)] + [r + [T] * (w - len(r)) for r in g]
    if reach:
        for y in range(8, 8 + 5):
            for x in range(4, 4 + reach + 6):
                if g[y][x - reach] == I and x < w:
                    g[y][x] = I
    cx = 9 + reach
    for i in range(n):
        for x in range(cx - (n - i) // 2, cx + (n - i) // 2 + 1):
            if 0 <= x < w:
                g[7 - i][x] = I
    return g


def it_wisp():
    size = (2, 1, 3, 1)
    idle = [(_wisp(size[p]), 0, -13, 0, 0) for p in range(POSES)]
    atk = [(_wisp(4), 0, -13, 0, 0), (_wisp(6, 3), 0, -13, 0, 0),
           (_wisp(3, 3), 0, -13, 0, 0), (_wisp(2), 0, -13, 0, 0)]
    return idle, atk


I_CENSER_ARM = parse("""
##.....
####...
######.
.######
...####
.....##
""")
I_CENSER = parse("""
..#..
.###.
#####
#o#o#
#####
.###.
""")


def _censer(sw, lift=0):
    """The arm, the chain and the censer, swung `sw` pixels off the hand's
    vertical and raised `lift`: a sway is two, and the swing the field read
    as a mace being wielded - too active for an IDLE - is the ATTACK now."""
    w = 7 + 12
    h = 6 + 14
    g = [[T] * w for _ in range(h)]
    for y, r in enumerate(I_CENSER_ARM):
        for x, v in enumerate(r):
            if v:
                g[y][x] = v
    hx, hy = 6, 5
    tx, ty = 7 + sw, 13 - lift
    n = max(abs(tx - hx), abs(ty - hy), 1)
    for i in range(n + 1):
        g[int(round(hy + (ty - hy) * i / n))][int(round(hx + (tx - hx) * i / n))] = I
    for y, r in enumerate(I_CENSER):
        for x, v in enumerate(r):
            if v and 0 <= tx - 2 + x < w:
                g[ty + 1 + y][tx - 2 + x] = v
    return g


def it_censer():
    idle = [(_censer(ppose(p) * 2), 0, 0, 0, 0) for p in range(POSES)]
    atk = [(_censer(-3, 1), 0, 0, 0, 0), (_censer(8, 5), 0, 0, 0, 0),
           (_censer(5, 2), 0, 0, 0, 0), (_censer(0), 0, 0, 0, 0)]
    return idle, atk


I_BOOK = parse("""
##.........
###........
###........
.###.......
..###..####
...###o####
....#######
...o#######
...########
""")
I_BOOK_UP = parse("""
.....#.#.#.
......###..
.....#####.
##..#######
###.o######
.###.######
..#####....
...###.....
""")


def it_book():
    idle = [(I_BOOK, 0, 1, 0, ppose(p)) for p in range(POSES)]
    atk = [(I_BOOK, 0, 1, 0, -1), (I_BOOK_UP, 0, -3, 0, 0),
           (I_BOOK_UP, 0, -3, 0, 1), (I_BOOK, 0, 1, 0, 0)]
    return idle, atk


ITEMS = [
    ("shield", it_shield),
    ("sword",  it_sword),
    ("bow",    it_bow),
    ("fork",   it_fork),
    ("staff",  it_staff),
    ("wisp",   it_wisp),
    ("censer", it_censer),
    ("book",   it_book),
]
IX = {n: i for i, (n, _) in enumerate(ITEMS)}
BX = {n: i for i, (n, _, _) in enumerate(BODIES)}

# THE HAND, as cards: a body, the item it carries in the FRONT column and the
# one it carries at the REAR (TITHE-PLAN 5.2 - "the same man with a different
# tool"). Seven cards, three bodies, eight items, and every item but two on
# more than one card - the SWORD on a soldier and a hooded caster, the SHIELD on
# two soldiers and a nun, the BOOK in two factions' hands - because whether a
# shared item looks right on different builds is the question wave 1a asks.
CARDS = [
    ("PIKEMAN", "soldier", "sword",  "fork"),
    ("ARCHER",  "hooded",  "sword",  "bow"),
    ("WARDEN",  "soldier", "shield", "fork"),
    ("ACOLYTE", "hooded",  "wisp",   "book"),
    ("RAM",     "soldier", "sword",  "shield"),
    ("HERALD",  "nun",     "censer", "staff"),
    ("BULWARK", "nun",     "shield", "book"),
]
FRONT, REAR = 0, 1
LUNGE = 8          # pixels an attack's STRIKE and FOLLOW-THROUGH step toward
                   # the enemy - inside the band, so it stays self-erasing
                   # (the machine's TI_CLSTEP, and tests/titheterr.py holds
                   # the two to the same bytes)


# =============================================================================
# THE CUT, per surface
# =============================================================================

def scales(w, h, aspect):
    """(sx, sy) for a surface: as large as the band allows, never above the
    master, and y cut by the pixel aspect so the figure is the same SHAPE on
    the glass."""
    room_w = (w - 2 * MARGIN) if w > 32 else (w - 4)
    room_h = h - 1
    s = min(1.0, room_w / float(MW), room_h * aspect / float(MH))
    return s, s / aspect


CGA_ITEM = (0.72, 0.30)          # an item's cut on CGA, to the drawn bodies


def _surf(name):
    return [s for s in SURFACES if s[0] == name][0]


def body_fig(body, surf, pose):
    """(Fig, anchor) of a body at a surface: the anchor in the Fig's pixels."""
    name, w, h, aspect = surf
    b = BODIES[BX[body]]
    if name == "cga":
        f = Fig(1, 1, CW_, CH_)
        ax, ay, oy = b[2](f, pose)
    else:
        sx, sy = scales(w, h, aspect)
        f = Fig(sx, sy)
        ax, ay, oy = b[1](f, pose)
    f.halo()
    return f, (f.X(ax), f.Y(ay) + f.dy(oy))   # the layers' own scaling rule


def item_scale(surf):
    name, w, h, aspect = surf
    if name == "cga":
        return CGA_ITEM
    return scales(w, h, aspect)


_ICACHE = {}


def item_frame(item, surf, frame):
    """(grid with its ring, gx, gy): the frame at the surface, and where its
    top-left sits relative to the anchor, in surface pixels."""
    k = (item, surf[0], frame)
    if k in _ICACHE:
        return _ICACHE[k]
    idle, atk = ITEMS[IX[item]][1]()
    art, gx, gy, mx, my = (idle + atk)[frame]
    sx, sy = item_scale(surf)
    f = Fig(sx, sy)                     # for its scaling rules only: a MOTION
    g = ring(reduce_art(art, sx, sy))   # never rounds away to nothing
    ox = f.X(gx) + f.dx(mx)
    oy = f.Y(gy) + f.dy(my)
    _ICACHE[k] = (g, ox - 1, oy - 1)    # the ring grew it a pixel each way
    return _ICACHE[k]


_PLACE = {}


def body_place(body, surf):
    """(bx, by): where a body's Fig lands in its band - the SAME for every
    pose and every item, so a character stands still whatever it carries.

    ON THE BOARD, against its numbers: the leftmost pixel any pose touches is
    MARGIN in, and then the body steps RIGHT until its anchor is on a BYTE
    boundary, so every item goes down in whole bytes (SPEC.md 97.4.9). ON A
    CARD it is centred, and steps the same way."""
    k = (body, surf[0])
    if k in _PLACE:
        return _PLACE[k]
    name, w, h, aspect = surf
    xs = []
    fh = 0
    ax = 0
    for p in range(POSES):
        f, (ax, ay) = body_fig(body, surf, p)
        xs += [x for r in f.px for x, v in enumerate(r) if v != T]
        fh = f.h
        fw = f.w
    left = min(xs)
    bx = (MARGIN - left) if w == 64 else (w - fw) // 2
    while (bx + ax) % 8:
        bx += 1
    _PLACE[k] = (bx, h - fh)
    return _PLACE[k]


def compose(card, stance, surf, pose, attack=False):
    """The character as the machine composes it: the body's figure, then the
    item's frame over it at the anchor. Rows of T/I/K in BAND coordinates."""
    name, w, h, aspect = surf
    c = CARDS[card]
    f, (ax, ay) = body_fig(c[1], surf, 0 if attack else pose)
    bx, by = body_place(c[1], surf)
    if attack and pose in (1, 2) and w == 64:
        bx += LUNGE                     # the strike steps in
    band = [[T] * w for _ in range(h)]
    for y in range(f.h):
        for x in range(f.w):
            v = f.px[y][x]
            if v != T and 0 <= y + by < h and 0 <= x + bx < w:
                band[y + by][x + bx] = v
    g, gx, gy = item_frame(c[2 + stance], surf, POSES + pose if attack else pose)
    for y, r in enumerate(g):
        for x, v in enumerate(r):
            X, Y = bx + ax + gx + x, by + ay + gy + y
            if v != T and 0 <= Y < h and 0 <= X < w:
                band[Y][X] = v
    return band


# =============================================================================
# WHAT THE MACHINE IS HANDED - one PART (SPEC.md 20.12), and the offsets into it
# =============================================================================

def boxed(g, x0, y0, w, h):
    """The byte-aligned box of what grid g (placed at x0, y0 in a band w x h)
    touches, as (bx, by, wb, rows, bytes) with (ink, mask) interleaved."""
    pts = [(x0 + x, y0 + y) for y, r in enumerate(g) for x, v in enumerate(r)
           if v != T and 0 <= x0 + x < w and 0 <= y0 + y < h]
    if not pts:
        return (0, 0, 0, 0, b"")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    b0, b1 = min(xs) // 8, max(xs) // 8
    Y0, Y1 = min(ys), max(ys)
    band = {}
    for y, r in enumerate(g):
        for x, v in enumerate(r):
            if v != T:
                band[(x0 + x, y0 + y)] = v
    out = bytearray()
    for y in range(Y0, Y1 + 1):
        for b in range(b0, b1 + 1):
            ink = mask = 0
            for i in range(8):
                v = band.get((b * 8 + i, y), T)
                if v != T:
                    mask |= 0x80 >> i
                if v == I:
                    ink |= 0x80 >> i
            out += bytes((ink, mask))
    return (b0, Y0, b1 - b0 + 1, Y1 - Y0 + 1, bytes(out))


def dirty(bands, p):
    """The rows the transition INTO pose p moves, as (y, h) - (0, 0) if none."""
    a, b = bands[(p - 1) % POSES], bands[p]
    rows = [y for y in range(len(a)) if a[y] != b[y]]
    if not rows:
        return (0, 0)
    return (min(rows), max(rows) - min(rows) + 1)


class Part:
    """A little-endian byte image with forward references resolved at the end."""

    def __init__(self):
        self.b = bytearray()
        self.fix = []
        self.lab = {}

    def here(self):
        return len(self.b)

    def db(self, *v):
        for x in v:
            self.b.append(x & 255)

    def dw(self, v):
        if isinstance(v, str):
            self.fix.append((len(self.b), v))
            self.b += b"\0\0"
        else:
            self.b += bytes((v & 255, (v >> 8) & 255))

    def label(self, n):
        self.lab[n] = len(self.b)

    def done(self):
        for at, n in self.fix:
            v = self.lab[n]
            self.b[at], self.b[at + 1] = v & 255, v >> 8
        return bytes(self.b)


def build_part():
    """THE ART PART, and the offsets the package reads it by.

        header      dw bodytab, itemtab, dirtytab, cardtab, sametab
        bodytab     dw rec[body][surface]
          rec       dw fig[4]; db bx[4], by[4], ax[4] (a BYTE), ay[4], bh
        itemtab     dw rec[item][surface]
          rec       dw fig[8]; db dx[8] (signed BYTES from the anchor),
                    dy[8] (signed rows)
        fig         db wb, rows; (ink, mask) x wb x rows
        dirtytab    db (dy, dh) x 4, per card x stance x board surface
        cardtab     db body, front item, rear item, per card
        sametab     db 8 per card x stance x board surface: the frame each
                    of the eight is a copy of (itself if it is new)
    """
    P = Part()
    for n in ("bodytab", "itemtab", "dirtytab", "cardtab", "sametab"):
        P.dw(n)
    figs = {}
    fbytes = []

    def fig(wb, rows, data):
        key = (wb, rows, data)
        if key not in figs:
            figs[key] = "f%d" % len(figs)
            fbytes.append((figs[key], wb, rows, data))
        return figs[key]

    recs = []
    P.label("bodytab")
    for bname, _, _ in BODIES:
        for surf in SURFACES:
            r = "b_%s_%s" % (bname, surf[0])
            P.dw(r)
            recs.append(("body", bname, surf, r))
    P.label("itemtab")
    for iname, _ in ITEMS:
        for surf in SURFACES:
            r = "i_%s_%s" % (iname, surf[0])
            P.dw(r)
            recs.append(("item", iname, surf, r))
    P.label("cardtab")
    for c in CARDS:
        P.db(BX[c[1]], IX[c[2]], IX[c[3]])
    P.label("dirtytab")
    for ci in range(len(CARDS)):
        for st in (FRONT, REAR):
            for surf in SURFACES[:BOARD_G]:
                bands = [compose(ci, st, surf, p) for p in range(POSES)]
                for p in range(POSES):
                    P.db(*dirty(bands, p))
    # THE SAME-AS TABLE: of a cell's eight frames - four idle, four attack -
    # which is the SAME PICTURE as an earlier one, so the machine copies a slot
    # it has already composed instead of composing it again. A ping-pong's
    # pose 2 is its pose 0 wherever nothing moves on the off-beat, and every
    # attack's recovery is the idle's first pose; about a quarter of all the
    # composition a board costs. It is the tool's to know and the machine's to
    # trust, and tests/titheterr.py holds every copied slot to the model.
    P.label("sametab")
    for ci in range(len(CARDS)):
        for st in (FRONT, REAR):
            for surf in SURFACES[:BOARD_G]:
                fr = [compose(ci, st, surf, k % POSES, k >= POSES)
                      for k in range(2 * POSES)]
                P.db(*[fr.index(b) for b in fr])
    for kind, n, surf, r in recs:
        P.label(r)
        name, w, h, aspect = surf
        if kind == "body":
            bx, by = body_place(n, surf)
            ents = []
            for p in range(POSES):
                f, (ax, ay) = body_fig(n, surf, p)
                b0, y0, wb, rows, data = boxed(f.px, bx, by, w, h)
                ents.append((fig(wb, rows, data), b0, y0, (bx + ax) // 8, by + ay))
            for e in ents:
                P.dw(e[0])
            for j in (1, 2, 3, 4):
                P.db(*[e[j] for e in ents])
            P.db(h)
        else:
            ents = []
            for fr in range(2 * POSES):
                g, gx, gy = item_frame(n, surf, fr)
                # the anchor is on a byte: place the frame at (8 + gx) in a
                # scratch band, box it there, and read the offset back
                span = 8 * 16
                b0, y0, wb, rows, data = boxed(g, 64 + gx, 64 + gy, span, span)
                ents.append((fig(wb, rows, data), b0 - 8, y0 - 64))
            for e in ents:
                P.dw(e[0])
            P.db(*[e[1] for e in ents])
            P.db(*[e[2] for e in ents])
    for lab, wb, rows, data in fbytes:
        P.label(lab)
        P.db(wb, rows)
        P.b += data
    P.lab["_figmax"] = max(2 + len(d) for _, _, _, d in fbytes)
    return P.done(), P.lab


# =============================================================================


def sheet_out(out):
    """Every card, both stances, idle and attack, at every surface."""
    z = 3
    rows = []
    for ci in range(len(CARDS)):
        for st in (FRONT, REAR):
            for surf in SURFACES:
                rows.append((ci, st, surf))
    heights = [int(s[2] * s[3] * z) + 22 for _, _, s in rows]
    colw = 64 * z + 10
    sh = Sheet(230 + colw * 2 * POSES, sum(heights) + 24)
    y = 12
    for (ci, st, surf), hh in zip(rows, heights):
        sh.text(6, y, "%s %s %s" % (CARDS[ci][0], ("FRONT", "REAR")[st],
                                    surf[0]), GREY, 1)
        zy = int(round(z * surf[3]))
        for k in range(2 * POSES):
            b = compose(ci, st, surf, k % POSES, attack=k >= POSES)
            x0 = 230 + k * colw
            for by in range(surf[2]):
                for bx in range(surf[1]):
                    v = b[by][bx]
                    c = ((40, 64, 40) if k < POSES else (64, 40, 40)) \
                        if v == T else (WHITE if v == I else (0, 0, 0))
                    for ddy in range(zy):
                        for ddx in range(z):
                            sh.set(x0 + bx * z + ddx, y + 12 + by * zy + ddy, c)
        y += hh
    sh.save(out)
    print("%s: %dx%d" % (out, sh.w, sh.h))


def emit(inc_path, bin_path):
    data, lab = build_part()
    os.makedirs(os.path.dirname(bin_path), exist_ok=True)
    open(bin_path, "wb").write(data)
    L = ["; GENERATED by tools/os88tithechar.py - do not edit.",
         "; TITHE's characters as LAYERS (SPEC.md 97.4.9): the numbers the package",
         "; reads the ART PART by. The part itself is %s." % bin_path,
         "",
         "TI_BODIES   equ %d" % len(BODIES),
         "TI_ITEMS    equ %d" % len(ITEMS),
         "TI_CARDS    equ %d" % len(CARDS),
         "TI_CHAR_G   equ %d                 ; surfaces a record exists for" % len(SURFACES),
         "TI_CHAR_BG  equ %d                 ; ...of which the first are the board's" % BOARD_G,
         "TI_P_BODYTAB equ %d" % lab["bodytab"],
         "TI_P_ITEMTAB equ %d" % lab["itemtab"],
         "TI_P_DIRTY  equ %d" % lab["dirtytab"],
         "TI_P_CARDS  equ %d" % lab["cardtab"],
         "TI_P_SAME   equ %d" % lab["sametab"],
         "TI_BR_BX    equ 8                 ; a body record's byte columns,",
         "TI_BR_BY    equ 12                ; ...rows, anchor byte, anchor row",
         "TI_BR_AX    equ 16",
         "TI_BR_AY    equ 20",
         "TI_BR_BH    equ 24                ; ...and the band it was cut for",
         "TI_IR_DX    equ 16                ; an item record's byte offsets",
         "TI_IR_DY    equ 24                ; ...and row offsets, from the anchor",
         "TI_P_SIZE   equ %d                ; bytes in the part" % len(data),
         "TI_P_FIGMAX equ %d                  ; the largest figure, header and all"
         % lab["_figmax"],
         ""]
    open(inc_path, "w").write("\n".join(L) + "\n")
    print("%s + %s: %d bodies, %d items, %d cards, %d bytes of art"
          % (inc_path, bin_path, len(BODIES), len(ITEMS), len(CARDS), len(data)))
    return len(data)


def selfcheck():
    bad = []
    for ci, c in enumerate(CARDS):
        for st in (FRONT, REAR):
            for surf in SURFACES:
                name, w, h, _ = surf
                idle = [compose(ci, st, surf, p) for p in range(POSES)]
                atk = [compose(ci, st, surf, p, True) for p in range(POSES)]
                tag = "%s/%s/%s" % (c[0], ("front", "rear")[st], name)
                # 1. EVERY IDLE POSE IS A PICTURE - three of four at least
                if len({repr(b) for b in idle}) < 3:
                    bad.append("%s: %d distinct idle poses" % (
                        tag, len({repr(b) for b in idle})))
                # 2. ...AND THE ATTACK MOVES: its middle frames are not idle
                if atk[1] == idle[0]:
                    bad.append("%s: the attack's strike is the idle" % tag)
                for p, b in enumerate(idle + atk):
                    lit = sum(1 for r in b for v in r if v == I)
                    if not 0.03 < lit / float(w * h) < 0.60:
                        bad.append("%s frame %d lights %.0f%%"
                                   % (tag, p, 100.0 * lit / (w * h)))
                    # 3. CLEAR OF THE STAT COLUMN - and on a card, of the edge
                    if w == 64 and any(any(r[:MARGIN]) for r in b):
                        bad.append("%s frame %d reaches the stat column"
                                   % (tag, p))
    # 4. THE ANCHOR MOVES ONLY UP AND DOWN, or an item lands between bytes
    for bname, _, _ in BODIES:
        for surf in SURFACES:
            bx, _ = body_place(bname, surf)
            xs = {(bx + body_fig(bname, surf, p)[1][0]) % 8 for p in range(POSES)}
            if xs != {0}:
                bad.append("%s/%s: the anchor leaves the byte grid (%s)"
                           % (bname, surf[0], sorted(xs)))
    for line in bad:
        print("  FAIL %s" % line)
    print("os88tithechar: %d cards, %d bodies, %d items x %d surfaces, %s"
          % (len(CARDS), len(BODIES), len(ITEMS), len(SURFACES),
             "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", default="sheet", choices=["sheet", "emit"])
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--bin", default="build/tiart.bin")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if a.cmd == "emit":
        emit("apps/tithe/tiart.inc", a.bin)
        return 0
    sheet_out("build/tithe-chars.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
