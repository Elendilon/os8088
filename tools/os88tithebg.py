#!/usr/bin/env python3
"""TITHE's BOARD - the PLACE the lanes are fought in, as art.

    python3 tools/os88tithebg.py mock       # build/tithe-board-<surface>.png
    python3 tools/os88tithebg.py emit       # apps/tithe/tiground.inc
    python3 tools/os88tithebg.py --selfcheck

THE BOARD IS A LOCATION AND NOT A CHART (SPEC.md 97.4.10). The first cut was a
50% dithered diamond per cell and a stack of lit bars under the columns, which
read as a grid with a shadow. What the owner asked for is the reference game's
kind of board: ground you could stand on, something built BETWEEN the lanes,
and an edge that says where the world stops. So a board is five things:

  TEXTURE    one per COLUMN, and SPARSE - pebbles, tufts, cracks, joints, a
             tenth of the pixels or less - so a figure stands ON it rather
             than being hidden in it. Four columns, four grounds: a player's
             yard behind their line, the contested middle in front of it.
  FENCES     between the LANES, which is where a lane stops. A lane runs
             up-and-to-the-right (SPEC.md 97.3's shear), so a fence is a
             SLOPED line: RISE over CW, the same slope in every column, and so
             continuous across all four without anybody joining it.
  THE WALL   along the back of lane 0 - the fence's heavier sibling, and the
             far edge of the world. Above it is nothing.
  THE CLIFF  under lane 4: a lit lip on the same slope and a face of rock
             under it, which is the board's front edge and its depth.
  THE SIDES  a lit edge down the outside of columns 0 and 3.

WHY IT IS COMPOSED INTO COLUMN STRIPS. Every one of those is a function of
(column, x, y) and of nothing else, so the machine composes each COLUMN once at
layout, top to bottom, into a strip in a heap claim - and the board is then
four blits rather than twenty (SPEC.md 97.4.10). Everything else that needs the
ground reads it from there: a figure's band is cut from its cell's rows of the
strip before the figure is masked over it, which is what lets a column's
texture differ from its neighbour's at all. The old ground was one tile shared
by every cell, and a figure composed once over it could stand anywhere; a
figure composed over a column's own ground stands in that column, so figures
are composed PER CELL now.

THE ALGORITHM HERE IS THE MACHINE'S, step for step, and tests/titheterr.py
holds the machine to it TO THE BYTE - every strip and every composed pose, on
all three adapters and both terrains:

  1. every row of the strip is the column's texture row, (ly mod TH), repeated
     across in whole bytes - the tile is 32 wide, four bytes;
  2. then, PER PIXEL COLUMN lx, with y0 = yoff[lx] = RISE*(CW-lx) div CW:
       rows [0, y0)                     black - above the wall
       rows [y0, y0+WH)                 the WALL pattern
       rows [k*CH+y0, +FH), k = 1..4    the FENCE pattern
       row  L = 5*CH + y0 + FH          the LIP, lit
       rows (L, L+D]                    the CLIFF pattern
       rows beyond                      black
     and in columns 0 and 3 the outside pixel column is lit from y0 to L+D.

A pattern is 16 pixels wide and one entry a row, as an (ink, mask) pair of
words: mask 0 leaves the texture showing, mask 1 draws the ink bit. So a rail
can have a shadow under it and a post an outline beside it, and the ground
between two posts is still the ground.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ti_geo_*: CW, CH, RISE, BW, BH, HUD, PAN, BASEW, CARDH, INSX (tithe.asm)
GEO = [
    ("vga-full", 96, 52, 22, 64, 48, 1.00),
    ("vga",      96, 48, 20, 64, 44, 1.00),
    ("herc",    104, 36, 12, 64, 32, 1.55),
    ("cga",      96, 20,  4, 64, 18, 2.40),
]
INSX = 24
COLS, ROWS = 4, 5

# FH fence rows, WH wall rows, D cliff rows, per surface. E, what the board
# grows by under column 0, is RISE + FH + 1 + D - and on a CGA that is the
# whole of the eight rows its window has spare.
SIZES = {"vga-full": (7, 7, 10), "vga": (6, 6, 8),
         "herc": (4, 4, 5), "cga": (2, 2, 1)}

TW, TH = 32, 32                   # a texture master: square pixels


def extra(name, rise):
    fh, wh, d = SIZES[name]
    return rise + fh + 1 + d


def parse(s):
    return [r for r in s.strip("\n").split("\n")]


# =============================================================================
# THE TEXTURES - authored at square pixels, 32 x 32, and SPARSE on purpose
# =============================================================================

TEX = {}

TEX["cobble"] = parse("""
................................
..####..............###.........
.#....#............#...#........
.#....#............#...#........
..####..............###.........
................................
.........###....................
........#...#...........####....
........#...#..........#....#...
.........###...........#....#...
........................####....
...##...........................
..#..#..........................
..#..#.............###..........
...##.............#...#.........
..................#...#.........
...................###.....##...
..........................#..#..
..........####............#..#..
.........#....#............##...
.........#....#.................
..........####..................
................................
....###.........................
...#...#.............####.......
...#...#............#....#......
....###.............#....#......
.....................####.......
..............##................
.............#..#...............
.............#..#...............
..............##................
""")

TEX["dirt"] = parse("""
................................
................................
.....#..........................
......#.........................
......##..............#.........
........#..............#........
.........#.............#........
......................#.#.......
.....................#...#......
................................
..##............................
................................
...................#............
..............................#.
.......#.......................#
......#.#.......................
................................
................................
.........................##.....
......................###.......
.....................#..........
...#................#...........
................................
................................
............#...................
.............#..................
.............##.................
...............#................
................................
.#..............................
................................
...............................#
""")

# the same earth worn the other way, so the two middle columns are one
# stretch of ground and not one tile twice
TEX["dirt2"] = [r[16:] + r[:16] for r in TEX["dirt"][16:] + TEX["dirt"][:16]]

TEX["grass"] = parse("""
................................
......#.#.......................
.......#..................#.#...
...........................#....
................................
..................#.#...........
...................#............
.#.#............................
..#.............................
..........................#.#...
...........#.#.............#....
............#...................
................................
....................#.#.........
.....................#..........
................................
.......#.#......................
........#...................#.#.
.............................#..
................#.#.............
.................#..............
................................
...#.#..........................
....#......................#.#..
............................#...
................................
..........#.#...................
...........#....................
......................#.#.......
.......................#........
................................
................................
""")


def _flag(moss):
    """PAVING: square slabs, a half-slab bond, and only their JOINTS marked -
    a dotted line and a small cross where four slabs meet. A solid joint grid
    reads as brickwork on a wall, which is the wrong way up for a floor."""
    g = [["."] * TW for _ in range(TH)]
    for y in range(TH):
        for x in range(TW):
            xo = (x + (8 if (y // 16) % 2 else 0)) % 16
            if y % 16 == 0 and x % 4 == 0:
                g[y][x] = "#"
            if xo == 0 and y % 4 == 0:
                g[y][x] = "#"
    for y in (0, 16):
        for x in range(TW):
            xo = (x + (8 if (y // 16) % 2 else 0)) % 16
            if xo == 0:
                for dx, dy in ((-1, 0), (1, 0), (0, 1), (0, -1)):
                    g[(y + dy) % TH][(x + dx) % TW] = "#"
    if moss:
        for x, y in ((6, 5), (7, 6), (22, 9), (11, 21), (12, 22), (27, 26),
                     (4, 28), (19, 3)):
            g[y][x] = "#"
    return ["".join(r) for r in g]


TEX["flag"] = _flag(False)
TEX["flagmoss"] = _flag(True)

TEXNAMES = ["cobble", "dirt", "dirt2", "grass", "flag", "flagmoss"]


def tex_rows(name, aspect):
    """The texture at a surface's pixel aspect: the SAME 32 columns and fewer
    rows, each target row the master row at its CENTRE. OR-ing the rows a
    target covers keeps every mark and piles them up - on a CGA, 2.4 master
    rows to one, a sparse ground came out a noise field a figure vanished in."""
    m = TEX[name]
    n = max(1, int(round(TH / aspect)))
    out = []
    for ty in range(n):
        y = min(TH - 1, int((ty + 0.5) * TH / n))
        row = 0
        for x in range(TW):
            if m[y][x] == "#":
                row |= 1 << (TW - 1 - x)
        out.append(row)
    return out


# =============================================================================
# THE PATTERNS - 16 pixels a period, (ink, mask) a row
# =============================================================================

def pat_fence(fh):
    """A WOODEN FENCE: a post every 16 pixels, outlined, and rails with a
    shadow under them. The ground shows between the posts and the rails."""
    rows = []
    rails = [1, fh - 3] if fh >= 5 else [0]
    for r in range(fh):
        ink = mask = 0
        for x in range(16):
            post = x in (0, 1)
            edge = x in (2, 15)
            b = 1 << (15 - x)
            if post:
                ink |= b; mask |= b
            elif r in rails:
                ink |= b; mask |= b
            elif (r - 1) in rails:
                mask |= b                       # the rail's shadow
            elif edge:
                mask |= b                       # the post's outline
        rows.append((ink, mask))
    return rows


def pat_wall(wh):
    """A LOW STONE WALL: a lit cap, courses of block with the joints
    staggered, and a shadow at its foot."""
    rows = []
    for r in range(wh):
        ink = mask = 0xFFFF
        if r == wh - 1 and wh >= 3:
            ink = 0                             # the shadow at its foot
        elif r == 0:
            pass                                # the cap
        elif r == 1 and wh >= 4:
            ink = 0                             # under the cap
        else:
            j = (0, 8) if r % 2 else (4, 12)
            for x in j:
                ink &= ~(1 << (15 - x))
        rows.append((ink, mask))
    return rows


def pat_bollard(fh):
    """THE CLOISTER's lane divide: a row of stone posts with a chain between,
    the ground showing through."""
    rows = []
    for r in range(fh):
        ink = mask = 0
        for x in range(16):
            b = 1 << (15 - x)
            if x in (6, 7, 8, 9):
                ink |= b; mask |= b
            elif x in (5, 10):
                mask |= b
            elif r == fh // 2 and x % 2 == 0:
                ink |= b; mask |= b             # the chain
        rows.append((ink, mask))
    return rows


CLIFF = parse("""
################
#####o##########
####o#####oo####
oooo#####o##o###
####o###o####ooo
#####ooo#####o##
###o#####o###o##
##o#######o##o##
oo#########oo#oo
#o#o#o#o#o#o#o#o
""")


def pat_cliff(d):
    """The ROCK FACE under the lip: mostly lit, with black joints. Its last
    row is ragged when there is room for one, and outside the board is black,
    so the pattern's mask is solid - there is no ground under a cliff."""
    rows = []
    src = CLIFF if d >= len(CLIFF) else CLIFF[:d - 1] + [CLIFF[-1]] \
        if d > 1 else [CLIFF[0]]
    for r in range(d):
        s = src[min(r, len(src) - 1)]
        ink = 0
        for x in range(16):
            if s[x] == "#":
                ink |= 1 << (15 - x)
        rows.append((ink, 0xFFFF))
    return rows


# THE TERRAINS: (name, four textures, the lane divide, the wall)
TERRAINS = [
    ("THE MARCH",    ("cobble", "dirt", "dirt2", "grass"), "fence", "wall"),
    ("THE CLOISTER", ("flag", "flagmoss", "flagmoss", "flag"), "bollard", "wall"),
]
DIVIDES = {"fence": pat_fence, "bollard": pat_bollard}


# =============================================================================
# THE MODEL - the machine's algorithm, on the host
# =============================================================================

def yoff(cw, rise):
    return [rise * (cw - lx) // cw for lx in range(cw)]


def strip(geo, terr, c):
    """Column c's strip as rows of 0/1, exactly as the machine composes it."""
    name, cw, ch, rise, bw, bh, aspect = geo
    fh, wh, d = SIZES[name]
    sh = ROWS * ch + extra(name, rise)
    tx = tex_rows(TERRAINS[terr][1][c], aspect)
    px = [[(tx[ly % len(tx)] >> (TW - 1 - (lx % TW))) & 1 for lx in range(cw)]
          for ly in range(sh)]
    fence = DIVIDES[TERRAINS[terr][2]](fh)
    wall = pat_wall(wh)
    cliff = pat_cliff(d)
    yo = yoff(cw, rise)

    def apply(lx, ly, p):
        ink, mask = p
        b = 1 << (15 - (lx & 15))
        if mask & b and 0 <= ly < sh:
            px[ly][lx] = 1 if ink & b else 0

    for lx in range(cw):
        y0 = yo[lx]
        for ly in range(0, y0):
            px[ly][lx] = 0
        for r in range(wh):
            apply(lx, y0 + r, wall[r])
        for k in range(1, ROWS):
            for r in range(fh):
                apply(lx, k * ch + y0 + r, fence[r])
        lip = ROWS * ch + y0 + fh
        px[lip][lx] = 1
        for r in range(d):
            apply(lx, lip + 1 + r, cliff[r])
        for ly in range(lip + 1 + d, sh):
            px[ly][lx] = 0
        if (c == 0 and lx == 0) or (c == COLS - 1 and lx == cw - 1):
            for ly in range(y0, lip + 1 + d):
                px[ly][lx] = 1
    return px


def mock(geo, terr, out, figures=True):
    """The whole board as the machine will draw it - four strips at the
    shear's heights, and a figure in every cell, masked over its own ground."""
    import os88tithechar as tc
    import os88marty
    name, cw, ch, rise, bw, bh, aspect = geo
    lift = (COLS - 1) * rise
    W = COLS * cw
    H = ROWS * ch + lift + extra(name, rise)
    scr = [[0] * W for _ in range(H)]
    for c in range(COLS):
        s = strip(geo, terr, c)
        top = lift - c * rise
        for ly, row in enumerate(s):
            for lx, v in enumerate(row):
                scr[top + ly][c * cw + lx] = v
    if figures:
        surf = [s for s in tc.SURFACES if s[0] == name][0]
        for c in range(COLS):
            for r in range(ROWS):
                chr_ = tc.CHARACTERS[(c * ROWS + r) % 7 % 3]
                band = tc.figure(chr_, surf, (c + 2 * r) % 4)
                x0 = c * cw + INSX
                if c >= COLS // 2:              # P2's cells are MIRRORED
                    band = [row[::-1] for row in band]
                    x0 = c * cw + cw - INSX - bw
                y0 = lift - c * rise + r * ch + (ch - bh)
                for by in range(bh):
                    for bx in range(bw):
                        v = band[by][bx]
                        if v:
                            scr[y0 + by][x0 + bx] = 1 if v == 1 else 0
    zx, zy = 2, int(round(2 * aspect))
    buf = bytearray()
    for y in range(H):
        line = bytearray()
        for x in range(W):
            line += (b"\xff\xff\xff" if scr[y][x] else b"\x00\x00\x00") * zx
        buf += bytes(line) * zy
    os88marty.write_png_rgb(out, W * zx, H * zy, bytes(buf))
    return out


# =============================================================================


def _dw(words):
    out = []
    for i in range(0, len(words), 8):
        out.append("    dw " + ", ".join("0%04Xh" % w for w in words[i:i + 8]))
    return out


def emit(path):
    L = ["; GENERATED by tools/os88tithebg.py - do not edit.",
         "; TITHE's board as a PLACE (SPEC.md 97.4.10): per-column textures, and the",
         "; wall, fence and cliff patterns the strips are composed from.",
         "",
         "TI_TERRAINS equ %d" % len(TERRAINS),
         "TI_TEXW     equ %d               ; a texture row is this many BYTES"
         % (TW // 8),
         ""]
    total = 0
    # --- per surface: the three heights, and a pointer to each pattern
    L.append("; per surface: FH, WH, D, E (the rows the board grows by under")
    L.append("; column 0), then the fence patterns, wall, cliff - as pointers")
    L.append("ti_gsz:")
    for g in GEO:
        fh, wh, d = SIZES[g[0]]
        L.append("    dw %d, %d, %d, %d" % (fh, wh, d, extra(g[0], g[3])))
    L.append("")
    L.append("; per surface, per terrain: four texture pointers, the divide")
    L.append("ti_gtex:")
    for gi, g in enumerate(GEO):
        for ti, t in enumerate(TERRAINS):
            L.append("    dw " + ", ".join(
                "tig_%s_%s" % (x, _cls(g)) for x in t[1])
                + ", tip_%s_%d" % (t[2], gi))
    L.append("ti_gwall:")
    L.append("    dw " + ", ".join("tip_wall_%d" % gi for gi in range(len(GEO))))
    L.append("ti_gcliff:")
    L.append("    dw " + ", ".join("tip_cliff_%d" % gi for gi in range(len(GEO))))
    L.append("ti_terr_nm:")
    L.append("    dw " + ", ".join(".t%d" % i for i in range(len(TERRAINS))))
    wide = max(len(t[0]) for t in TERRAINS)
    for i, t in enumerate(TERRAINS):
        L.append(".t%d: db '%-*s', 0" % (i, wide, t[0]))
    L.append("")
    # --- the textures, one per aspect class: db rows, then 4 bytes a row
    done = set()
    for g in GEO:
        cls = _cls(g)
        for x in TEXNAMES:
            if (x, cls) in done:
                continue
            done.add((x, cls))
            rows = tex_rows(x, g[6])
            L.append("tig_%s_%s: db %d" % (x, cls, len(rows)))
            for r in rows:
                L.append("    db 0%02Xh, 0%02Xh, 0%02Xh, 0%02Xh"
                         % ((r >> 24) & 255, (r >> 16) & 255, (r >> 8) & 255,
                            r & 255))
            total += 1 + 4 * len(rows)
    # --- the patterns: (ink, mask) words a row, stored as BYTES in screen
    #     order so the machine reads the byte its pixel is in
    for gi, g in enumerate(GEO):
        fh, wh, d = SIZES[g[0]]
        for nm, rows in ([(k, DIVIDES[k](fh)) for k in sorted(DIVIDES)]
                         + [("wall", pat_wall(wh)), ("cliff", pat_cliff(d))]):
            L.append("tip_%s_%d:" % (nm, gi))
            for ink, mask in rows:
                L.append("    db 0%02Xh, 0%02Xh, 0%02Xh, 0%02Xh"
                         % (ink >> 8, ink & 255, mask >> 8, mask & 255))
            total += 4 * len(rows)
    open(path, "w").write("\n".join(L) + "\n")
    print("%s: %d terrains, %d bytes of ground" % (path, len(TERRAINS), total))


def _cls(g):
    return {1.00: "v", 1.55: "h", 2.40: "c"}[g[6]]


def selfcheck():
    bad = []
    for g in GEO:
        name, cw, ch, rise, bw, bh, aspect = g
        fh, wh, d = SIZES[name]
        # 1. THE FENCE IS BELOW THE CELL'S TOP and THE FIGURE STANDS IN ITS
        #    LANE: a lane's own fence is in its own cells' top rows, so a
        #    figure is drawn in front of it and never behind the next one
        if rise + fh > ch - 2:
            bad.append("%s: a fence (RISE %d + FH %d) reaches the cell's floor"
                       % (name, rise, fh))
        for t in range(len(TERRAINS)):
            for c in range(COLS):
                s = strip(g, t, c)
                # 2. SPARSE: the ground in a lane's middle lights under a
                #    fifth of its pixels, so a figure stands ON it
                ly0 = 2 * ch + rise + fh + 2
                lit = sum(sum(s[y]) for y in range(ly0, ly0 + ch - rise - fh - 4))
                n = cw * (ch - rise - fh - 4)
                if n > 0 and lit > n // 5:
                    bad.append("%s/%s col %d: ground lights %d of %d"
                               % (name, TERRAINS[t][0], c, lit, n))
                # 3. THE LIP IS ONE UNBROKEN SLOPE: lit in every pixel column
                for lx in range(cw):
                    lip = ROWS * ch + yoff(cw, rise)[lx] + fh
                    if not s[lip][lx]:
                        bad.append("%s col %d: the lip is broken at %d"
                                   % (name, c, lx))
                        break
    for x in TEXNAMES:
        m = TEX[x]
        if len(m) != TH or any(len(r) != TW for r in m):
            bad.append("texture %s is not %dx%d" % (x, TW, TH))
    for line in bad:
        print("  FAIL %s" % line)
    print("os88tithebg: %d terrains x %d surfaces, %s"
          % (len(TERRAINS), len(GEO), "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", default="mock", choices=["mock", "emit"])
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if a.cmd == "emit":
        emit("apps/tithe/tiground.inc")
        return 0
    for g in GEO:
        for t in range(len(TERRAINS)):
            out = "build/tithe-board-%s-%d.png" % (g[0], t)
            mock(g, t, out)
            print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
