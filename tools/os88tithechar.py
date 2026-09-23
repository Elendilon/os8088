#!/usr/bin/env python3
"""TITHE's FACTION IDLES - one animated character a faction, as PIXEL ART.

    python3 tools/os88tithechar.py sheet        # build/tithe-chars.png
    python3 tools/os88tithechar.py emit         # apps/tithe/tichars.inc
    python3 tools/os88tithechar.py --selfcheck

PIXEL ART AND NOT A SILHOUETTE (SPEC.md 97.4.9). The first cut drew each
faction as a solid white shape out of spans and ellipses, which scaled to every
surface for free and could not be told apart once there are sixty of them. A
figure is AUTHORED now, one character of ASCII a pixel, in THREE states:

    '#'  INK - lit
    'o'  BLACK - drawn dark, and OPAQUE: the ground does not show through it
    '.'  nothing - the ground shows here

A black pixel is what 1bpp detail IS - the visor slit, the mail, the fold of a
habit - and it is why a figure is INK AND MASK rather than ink alone: the old
figures were ORed over the ground, which works only for a figure that is solid
white, since a dark detail line ORed over a lit ground pixel stays lit. The
mask is composed away at LOAD, never in a frame, and the frame still commits
one opaque 1bpp band a feature - so a detailed figure costs exactly what a
solid one of the same box does (TITHE-PLAN 1.1: the band is priced by rows and
bytes, never by what is in them).

A FIGURE IS LAYERS, and every layer is OUTLINED where it is put down, so a
shield over a torso or a head over a collar is separated by one black pixel
without anybody drawing that pixel. The whole figure then gets a black HALO,
which is what keeps it reading over a textured ground on a one-bit screen.

THE SMALLER SURFACES ARE REDUCED PER LAYER, NOT PER PICTURE. Each layer's art
is cut down on its own and the outlines are re-drawn at the target size, so a
Hercules or CGA figure keeps the separation between its parts - where scaling
the finished picture merges a shield into the torso behind it. The cut is per
AXIS (TITHE-PLAN 4.2): x stays near 1:1 and y takes the pixel aspect, so a
CGA figure is short in rows and correctly proportioned on the glass.

THE MOTION IS THE SAME AS THE SILHOUETTES' - which the field liked - bar one:

  BULWARK    the head rocks a pixel; the SHIELD lifts and settles two
  EMBER      the hem never moves - it is the shadow it hovers over - and the
             rest rises and falls, with a WISP flickering at the open hand
  COVENANT   the body is still; the CENSER sways on its chain. It swung ten
             pixels each way and read as a mace being wielded - too active for
             an idle - so it is TWO now, a sway and not a swing.

WHAT IS EMITTED: per character and surface, FOUR POSE FIGURES (deduplicated -
a ping-pong has three distinct pictures) as byte-aligned boxes of interleaved
(ink, mask) bytes, and per pose the rows that the transition INTO it moves, in
band coordinates. The rows are the TOOL's, computed from the figures alone and
not from a composed band, so they hold whatever ground a cell composes under
them (SPEC.md 97.4.3).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from os88tithebase import Sheet, WHITE, GREY          # noqa: E402

T, I, K = 0, 1, 2                                   # nothing, ink, black

# The FIGURE band, out of ti_geo_*'s BW and BH, and the MINI UNIT that rides a
# card (TI_UNITW by ti_unith). (name, w, h, pixel aspect)
SURFACES = [
    ("vga-full", 64, 48, 1.00),
    ("vga",      64, 44, 1.00),
    ("herc",     64, 32, 1.55),
    ("cga",      64, 18, 2.40),
    ("unit-vga-full", 24, 30, 1.00),
    ("unit-vga",      24, 26, 1.00),
    ("unit-herc",     24, 18, 1.55),
    ("unit-cga",      24,  7, 2.40),
]
BOARD_G = 4                     # the first four are the BOARD's
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


# =============================================================================
# THE BULWARK - a shield-bearer in mail, sword down, heater shield on the arm
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

B_ARM = parse("""
..##..
.####.
.####.
.###..
.###..
.###..
.###..
..##..
..##..
..##..
######
..##..
..##..
..##..
..##..
..##..
..##..
..#...
""")

B_SHIELD = parse("""
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


def d_bulwark(f, p):
    pp = ppose(p)
    f.put(B_ARM, 1, 11)
    f.put(B_BODY, 5, 10, True)
    f.put(B_HEAD, 8, 1, True, ox=-pp)          # the head rocks a pixel...
    f.put(B_SHIELD, 15, 13, True, oy=pp * 2)   # ...the shield lifts two


# =============================================================================
# THE EMBER CHOIR - a hooded caster that HOVERS, with a wisp at its hand
# =============================================================================

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

E_ARM = parse("""
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

E_SHADOW = parse("""
..#.#.#.#.#.#.#.#..
.#.#.#.#.#.#.#.#.#.
""")

E_WISP = [parse(s) for s in ("""
.#.
###
.#.
""", """
#
""", """
..#..
.###.
.###.
#####
.###.
""", """
#
""")]


def d_ember(f, p):
    dy = ppose(p) * 2
    f.put(E_UPPER, 3, 2, oy=dy)                # everything above the hem...
    f.put(E_ARM, 15, 14, True, oy=dy)
    f.put(E_HEM, 2, 27)                        # ...and the hem, which never
    f.put(E_SHADOW, 2, 38)                     # moves, over its own shadow
    w = E_WISP[p]
    f.put(w, 24 - len(w[0]) // 2, 13 - len(w), oy=dy)


# =============================================================================
# THE COVENANT - a nun, still, with a censer SWAYING on its chain
# =============================================================================

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

C_ARM = parse("""
##.....
####...
######.
.######
...####
.....##
""")

C_CENSER = parse("""
..#..
.###.
#####
#o#o#
#####
.###.
""")


def d_covenant(f, p):
    sw = ppose(p) * 2                          # TWO, and not ten: a sway
    f.put(C_BODY, 3, 6)
    f.put(C_ARM, 15, 17, True)
    f.line(21, 22, 22, 30, ox=sw)              # the chain, hand to censer
    f.put(C_CENSER, 20, 31, True, ox=sw)


# =============================================================================
# THE CGA FIGURES - DRAWN, NOT REDUCED
#
# A CGA pixel is 2.4 times as tall as it is wide, so a board figure there is
# 17 ROWS - and the per-layer reduction that holds up on a Hercules turns the
# helm, the face and the hood into one dark blob at that height: every detail
# row of a 42-row figure is one of the 60% the cut has to drop. So CGA is its
# own drawing, at its own size, 1:1, with the same layers and the same motion
# in CGA pixels. It is the one surface that costs an artist a second picture
# (TITHE-PLAN 4.2's "CGA fallback, named and costed now").
# =============================================================================
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
BC_ARM = parse("""
.##.
.##.
.##.
.##.
####
.#..
.#..
.#..
""")
BC_SHIELD = parse("""
#######
###o###
#ooooo#
###o###
###o###
.##o##.
..###..
...#...
""")


def c_bulwark(f, p):
    pp = ppose(p)
    f.put(BC_ARM, 3, 6)
    f.put(BC_BODY, 6, 5, True)
    f.put(BC_HEAD, 9 - pp, 0, True)
    f.put(BC_SHIELD, 14, 6 + (pp > 0) - (pp < 0), True)


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
EC_ARM = parse("""
.....#.#
.....###
..#####.
######..
###o....
""")
EC_WISP = [parse(s) for s in ("""
.#.
###
""", """
#
""", """
.#.
###
###
""", """
#
""")]


def c_ember(f, p):
    dy = ppose(p)
    f.put(EC_UPPER, 6, 0, oy=dy)
    f.put(EC_ARM, 13, 6, True, oy=dy)
    f.put(EC_HEM, 6, 12)
    w = EC_WISP[p]
    f.put(w, 21 - len(w[0]) // 2, 6 - len(w), oy=dy)


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
CC_ARM = parse("""
###..
#####
..###
""")
CC_CENSER = parse("""
.#.
###
#o#
###
""")


def c_covenant(f, p):
    sw = ppose(p) * 2
    f.put(CC_BODY, 7, 1)
    f.put(CC_ARM, 14, 6, True)
    f.line(18, 8, 19, 11, ox=sw)
    f.put(CC_CENSER, 18, 12, True, ox=sw)


CHARACTERS = [
    ("bulwark",  "PIKEMAN", "THE BULWARK",
     "a shield-bearer in mail; the shield lifts and settles",
     d_bulwark, c_bulwark),
    ("ember",    "ACOLYTE", "THE EMBER CHOIR",
     "a hooded caster that hovers, wisp at the hand", d_ember, c_ember),
    ("covenant", "HERALD",  "THE COVENANT",
     "a nun, still, with a censer swaying on its chain",
     d_covenant, c_covenant),
]


def scales(w, h, aspect):
    """(sx, sy) for a surface: as large as the band allows, never above the
    master, and y cut by the pixel aspect so the figure is the same SHAPE on
    the glass."""
    room_w = (w - 2 * MARGIN) if w > 32 else (w - 4)
    room_h = h - 1
    s = min(1.0, room_w / float(MW), room_h * aspect / float(MH))
    return s, s / aspect


def figure(ch, surf, pose):
    """(the figure in BAND coordinates as rows of T/I/K) for one pose."""
    name, w, h, aspect = surf
    if name == "cga":                       # DRAWN for the surface, 1:1
        f = Fig(1, 1, CW_, CH_)
        ch[5](f, pose)
    else:
        sx, sy = scales(w, h, aspect)
        f = Fig(sx, sy)
        ch[4](f, pose)
    f.halo()
    band = [[T] * w for _ in range(h)]
    ox = (w - f.w) // 2
    oy = h - f.h                                # the feet on the band's floor
    for y in range(f.h):
        for x in range(f.w):
            v = f.px[y][x]
            if v != T and 0 <= y + oy < h and 0 <= x + ox < w:
                band[y + oy][x + ox] = v
    return band


def boxed(band):
    """The byte-aligned box of what a figure touches, and its (ink, mask)
    bytes interleaved - one `lodsw` a byte on the machine."""
    h, w = len(band), len(band[0])
    ys = [y for y in range(h) if any(band[y])]
    xs = [x for y in range(h) for x in range(w) if band[y][x]]
    if not ys:
        return (0, 0, 0, 0, b"")
    y0, y1 = min(ys), max(ys)
    b0, b1 = min(xs) // 8, max(xs) // 8
    out = bytearray()
    for y in range(y0, y1 + 1):
        for b in range(b0, b1 + 1):
            ink = mask = 0
            for i in range(8):
                v = band[y][b * 8 + i]
                if v != T:
                    mask |= 0x80 >> i
                if v == I:
                    ink |= 0x80 >> i
            out += bytes((ink, mask))
    return (b0, y0, b1 - b0 + 1, y1 - y0 + 1, bytes(out))


def dirty(bands, p):
    """The rows the transition INTO pose p moves, as (y, h) - (0, 0) if none."""
    a, b = bands[(p - 1) % POSES], bands[p]
    rows = [y for y in range(len(a)) if a[y] != b[y]]
    if not rows:
        return (0, 0)
    return (min(rows), max(rows) - min(rows) + 1)


# =============================================================================


def sheet_out(out):
    z = 3
    pad = 16
    rows = []
    for ch in CHARACTERS:
        for surf in SURFACES:
            rows.append((ch, surf))
    colw = 64 * z + pad
    y = 12
    heights = [int(s[2] * s[3] * z) + 26 for _, s in rows]
    sh = Sheet(200 + colw * POSES, sum(heights) + 24)
    for (ch, surf), hh in zip(rows, heights):
        sh.text(6, y, "%s %s" % (ch[0][:9].upper(), surf[0]), GREY, 1)
        zy = int(round(z * surf[3]))
        for p in range(POSES):
            b = figure(ch, surf, p)
            x0 = 200 + p * colw
            for by in range(surf[2]):
                for bx in range(surf[1]):
                    v = b[by][bx]
                    c = (40, 64, 40) if v == T else (WHITE if v == I else (0, 0, 0))
                    for ddy in range(zy):
                        for ddx in range(z):
                            sh.set(x0 + bx * z + ddx, y + 12 + by * zy + ddy, c)
        y += hh
    sh.save(out)
    print("%s: %dx%d" % (out, sh.w, sh.h))


def _db(data):
    out = []
    for i in range(0, len(data), 16):
        out.append("    db " + ", ".join("0%02Xh" % b for b in data[i:i + 16]))
    return out


def emit(path):
    """RECORD (character x surface):
         dw fig[4]          the pose's figure, SHARED - a fullscreen and a
                            windowed VGA figure are the same pixels at a
                            different band row, and a ping-pong repeats one
         db y[4]            ...the band row that figure's box starts at
         db dy[4], dh[4]    ...interleaved: the rows the move INTO pose p
                            touches, (0, 0) for none
         db bh              the band height the art was cut for, so a
                            shorter band keeps the figure's FLOOR
       FIGURE:
         db bx, wb, h       byte column, width in bytes, rows
         db (ink, mask) x wb x h
    """
    lines = ["; GENERATED by tools/os88tithechar.py - do not edit.",
             "; TITHE's faction idles as PIXEL ART (SPEC.md 97.4.9): per character",
             "; and surface, four pose figures of interleaved (ink, mask) bytes and",
             "; the rows each transition moves.",
             "",
             "TI_CHAR_N   equ %d" % len(CHARACTERS),
             "TI_CHAR_G   equ %d" % len(SURFACES),
             "TI_CHAR_BG  equ %d" % BOARD_G,
             "TI_CR_Y     equ 8                 ; the record's band rows",
             "TI_CR_D     equ 12                ; ...and its (dy, dh) pairs",
             "TI_CR_H     equ 20                ; ...and the band it was cut for",
             ""]
    total = 0
    tab, body, figs = [], [], {}
    fbody = []
    for ch in CHARACTERS:
        for surf in SURFACES:
            tag = "tic_%s_%s" % (ch[0], surf[0].replace("-", ""))
            tab.append(tag)
            bands = [figure(ch, surf, p) for p in range(POSES)]
            names, ys = [], []
            for b in bands:
                bx, by, wb, hh, data = boxed(b)
                key = (bx, wb, hh, data)
                if key not in figs:
                    figs[key] = "tif_%d" % len(figs)
                    fbody.append("%s: db %d, %d, %d" % (figs[key], bx, wb, hh))
                    fbody += _db(data)
                    total += len(data) + 3
                names.append(figs[key])
                ys.append(by)
            dd = []
            for p in range(POSES):
                dd += dirty(bands, p)
            body.append("%s:" % tag)
            body.append("    dw " + ", ".join(names))
            body.append("    db " + ", ".join(str(v) for v in ys))
            body.append("    db " + ", ".join(str(v) for v in dd))
            body.append("    db %d" % surf[2])
            total += 2 * POSES + POSES + 2 * POSES + 1
    lines.append("ti_char_tab:")
    for i in range(0, len(tab), 4):
        lines.append("    dw " + ", ".join(tab[i:i + 4]))
    lines.append("")
    lines += body
    lines.append("")
    lines += fbody
    open(path, "w").write("\n".join(lines) + "\n")
    print("%s: %d characters x %d surfaces, %d figures, %d bytes of art"
          % (path, len(CHARACTERS), len(SURFACES), len(figs), total))
    return total


def selfcheck():
    bad = []
    for ch in CHARACTERS:
        for surf in SURFACES:
            name, w, h, _ = surf
            bands = [figure(ch, surf, p) for p in range(POSES)]
            # 1. EVERY POSE IS A PICTURE, and a ping-pong has three of them.
            #    A pose that reduces to its neighbour at a small size is a
            #    commit that moves nothing - silent, the wheel still pays.
            keys = {repr(b) for b in bands}
            if len(keys) < 3:
                bad.append("%s/%s: %d distinct poses of %d"
                           % (ch[0], name, len(keys), POSES))
            for p, b in enumerate(bands):
                lit = sum(1 for r in b for v in r if v == I)
                frac = lit / float(w * h)
                # 2. A FIGURE, and not an empty band or a filled one
                if not 0.03 < frac < 0.60:
                    bad.append("%s/%s pose %d lights %.0f%% of its band"
                               % (ch[0], name, p, frac * 100))
                # 3. CLEAR OF THE STAT COLUMN: a board figure lights nothing
                #    in the band's outer MARGIN columns (SPEC.md 97.2.1's rule
                #    for a base, and the stat column is two pixels past it)
                if w == 64:
                    for r in b:
                        if any(r[:MARGIN]) or any(r[w - MARGIN:]):
                            bad.append("%s/%s pose %d reaches the band's edge"
                                       % (ch[0], name, p))
                            break
            # 4. THE MOTION IS SMALL: the rows a transition moves are what the
            #    wheel commits, and a figure that moves most of its band is a
            #    dirty rect worth nothing (SPEC.md 97.4.3). NOT ON CGA: its
            #    figure is 17 rows of an 18-row band, so ANY motion in two
            #    parts of it - a head and a shield - spans the band
            for p in range(POSES):
                _, dh = dirty(bands, p)
                if w == 64 and h >= 24 and dh * 4 > h * 3:
                    bad.append("%s/%s pose %d moves %d rows of %d"
                               % (ch[0], name, p, dh, h))
    for line in bad:
        print("  FAIL %s" % line)
    print("os88tithechar: %d character(s) x %d surfaces, %s"
          % (len(CHARACTERS), len(SURFACES),
             "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", default="sheet", choices=["sheet", "emit"])
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if a.cmd == "emit":
        emit("apps/tithe/tichars.inc")
        return 0
    sheet_out("build/tithe-chars.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
