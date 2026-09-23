#!/usr/bin/env python3
"""TITHE's FACTION IDLES - one animated character a faction, as art.

    python3 tools/os88tithechar.py sheet        # build/tithe-chars.png
    python3 tools/os88tithechar.py emit         # apps/tithe/tichars.inc
    python3 tools/os88tithechar.py --selfcheck

WHY IT IS ART AND NOT A FORMULA. The placeholder figure is a trapezoid with a
lean, drawn by `ti_pose_build` out of the band's own dimensions: it scales to
every surface for free and it says nothing about WHO is standing there. Three
factions with three silhouettes and three motions is what wave 1a owes the
look, and it is what the music session about to happen needs to write against -
a rhythm has to be a rhythm of something.

THE MOTION IS THE POINT AND IT IS SMALL. The reference (docs/plans/TITHE-PLAN.md
§0) idles at a few pixels: a body that shifts weight, and a HELD ITEM that
moves further than the body does. That is TITHE-PLAN §4.2.1's body/item split arriving as
a drawing rule rather than as a data structure - the item layer is what swings,
and the body barely moves.

  BULWARK    a shield-bearer. The body rocks one pixel; the SHIELD lifts and
             settles two, which is what a man holding a heavy thing looks like.
  EMBER      a hooded caster. The robe's hem never moves - it is the shadow it
             hovers over - and everything above it rises and falls, with a
             WISP that flickers between two sizes above the open hand.
  COVENANT   a nun with a censer. The body is still, hands together; the
             CENSER swings on its chain through an arc, which is the cathedral
             base's pendulum one scale down and deliberately so.

WHAT IS EMITTED, and it is tibases.inc's shape: per character and surface a
STATIC ground - the body, which every pose shares - and per pose a packed
sub-band of what moved, with its own bbox. The band is 64 x BH, four poses, and
emitting each pose whole would be 13,632 bytes of a package that has 60KB for
everything; packed it is a fraction of that, and the package ORs the sub-band
over a copy of the ground exactly as it does for a base.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from os88tithebase import (Band, Sheet, circ, bbox, pack, _db,   # noqa: E402
                           WHITE, GREY, RED)

# The FIGURE band, out of ti_geo_*'s BW and BH. BW is 64 on every surface -
# what changes is the height, and that is the whole of the cut (TITHE-PLAN §4.2).
SURFACES = [
    ("vga-full", 64, 48, 1.00),
    ("vga",      64, 44, 1.00),
    ("herc",     64, 32, 1.55),
    ("cga",      64, 18, 2.40),
    # ...AND THE MINI UNIT THAT RIDES A CARD, which is the same three
    # characters at TI_UNITW by `ti_unith` - `cardh - 4 - 2*cpad`, capped at
    # TI_UNITHMAX. It is a SURFACE and not a scale of the board's band: the
    # width changes as well as the height (24 against 64), so the same drawing
    # code has to be asked for it rather than the same pixels resampled.
    ("unit-vga-full", 24, 30, 1.00),
    ("unit-vga",      24, 26, 1.00),
    ("unit-herc",     24, 18, 1.55),
    ("unit-cga",      24,  7, 2.40),
]
BOARD_G = 4                     # the first four are the BOARD's

POSES = 4                       # a ping-pong idle: A B C B (SPEC.md 97.5)


def ph(b, f):
    """A fraction of the band's height, rounded - every shape is in these."""
    return int(round(f * b.h))


def pw(b, f):
    return int(round(f * b.w))


def ppose(p):
    """The ping-pong for a 4-pose idle: 0, 1, 2, 1 -> -1, 0, +1, 0."""
    return (0, -1, 0, 1)[p]


# =============================================================================
# THE BULWARK - a shield-bearer, and the shield is the item
# =============================================================================

def g_bulwark(b):
    cx = b.w // 2
    head = ph(b, 0.16)
    # helmet: a dome with a nasal bar
    for y in range(ph(b, 0.04), head):
        t = (y - ph(b, 0.04)) / max(1, head - ph(b, 0.04))
        b.span(cx - 1, pw(b, 0.055) * circ(1 - t) + 1, y)
    b.set(cx - 1, head - 1)
    # torso: broad at the shoulders, tapering
    top, bot = head, ph(b, 0.78)
    for y in range(top, bot):
        t = (y - top) / max(1, bot - top)
        b.span(cx - 1, pw(b, 0.105) - pw(b, 0.03) * t, y)
    # legs, planted apart
    for y in range(bot, b.h - 1):
        b.span(cx - pw(b, 0.055), pw(b, 0.025), y)
        b.span(cx + pw(b, 0.04), pw(b, 0.025), y)


def m_bulwark(b, p):
    """The SHIELD, on the near arm, lifting and settling."""
    cx = b.w // 2
    dy = ppose(p) * max(1, ph(b, 0.045))
    x0 = cx + pw(b, 0.095)          # ...clear of the torso, so it reads as a
                                    # thing HELD and not as a wider shoulder
    top = ph(b, 0.26) + dy
    bot = ph(b, 0.66) + dy
    wide = pw(b, 0.085)
    for y in range(top, bot):
        t = (y - top) / max(1, bot - top)
        half = wide * (1.0 if t < 0.62 else circ((t - 0.62) / 0.38))
        b.span(x0, half, y)
    # ...and the head rocks the other way, one pixel, so the two read as one body
    if ppose(p):
        for y in range(ph(b, 0.04), ph(b, 0.16)):
            b.set(cx - 1 - ppose(p), y)


# =============================================================================
# THE EMBER CHOIR - a hooded caster that HOVERS, with a wisp at its hand
# =============================================================================

def g_ember(b):
    """The hem alone: the shadow it never leaves."""
    cx = b.w // 2
    for y in range(ph(b, 0.86), b.h - 1):
        t = (y - ph(b, 0.86)) / max(1, b.h - 1 - ph(b, 0.86))
        b.dither(cx - 1, pw(b, 0.115) * (0.55 + 0.45 * t), y, phase=y)


def m_ember(b, p):
    """Everything above the hem, risen or fallen - and the wisp."""
    cx = b.w // 2
    dy = ppose(p) * max(1, ph(b, 0.05))
    hood_t = ph(b, 0.06) + dy
    hood_b = ph(b, 0.24) + dy
    for y in range(hood_t, hood_b):                     # the hood: a peak
        t = (y - hood_t) / max(1, hood_b - hood_t)
        b.span(cx - 1, pw(b, 0.085) * t + 0.5, y)
    for y in range(hood_t + 2, hood_b - 1):             # ...and its dark mouth
        b.span(cx - 1, pw(b, 0.03) * (y - hood_t - 1) / 3.0, y, 0)
    top, bot = hood_b, ph(b, 0.88)                      # the robe
    for y in range(top, bot):
        t = (y - top) / max(1, bot - top)
        b.span(cx - 1, pw(b, 0.055) + pw(b, 0.06) * t, y)
    # THE WISP: a small flame at the outstretched hand, two sizes and a gap,
    # so it FLICKERS rather than merely moving
    wx = cx + pw(b, 0.125)
    wy = ph(b, 0.40) + dy
    size = (2, 1, 3, 1)[p]
    for i in range(size):
        b.span(wx, (size - i) * 0.6, wy - i)
    b.set(wx, wy + 1)


# =============================================================================
# THE COVENANT - a nun, still, with a censer swinging on its chain
# =============================================================================

def g_covenant(b):
    cx = b.w // 2
    # the coif: a wide wimple over a narrow face
    top, bot = ph(b, 0.05), ph(b, 0.22)
    for y in range(top, bot):
        t = (y - top) / max(1, bot - top)
        b.span(cx - 2, pw(b, 0.045) + pw(b, 0.045) * t, y)
    # the habit: straight, widening to the floor
    top, bot = bot, b.h - 1
    for y in range(top, bot):
        t = (y - top) / max(1, bot - top)
        b.span(cx - 2, pw(b, 0.065) + pw(b, 0.075) * t, y)
    # hands together at the waist
    b.span(cx - 2, pw(b, 0.03), ph(b, 0.52), 0)


def m_covenant(b, p):
    """The CENSER, on its chain, through an arc - the body does not move."""
    cx = b.w // 2
    ax = cx + pw(b, 0.06)
    ay = ph(b, 0.34)
    swing = (0, -1, 0, 1)[p]
    reach = pw(b, 0.16)
    drop = ph(b, 0.30)
    tipx = ax + reach * swing * 0.9         # SYMMETRIC about the hand: an arc
    tipy = ay + drop * (1.0 - 0.16 * abs(swing))   # that reaches further one
                                                    # way than the other reads
                                                    # as a throw, not a swing
    n = max(3, int(drop))
    for i in range(n + 1):                              # the chain
        b.set(int(ax + (tipx - ax) * i / n), int(ay + (tipy - ay) * i / n))
    r = max(1, pw(b, 0.035))
    for y in range(int(tipy) - r, int(tipy) + r + 1):   # ...and the censer
        t = (y - tipy) / max(1, r)
        b.span(tipx, r * circ(t), y)


CHARACTERS = [
    ("bulwark",  "PIKEMAN", "THE BULWARK",
     "a shield-bearer; the shield lifts and settles", g_bulwark, m_bulwark),
    ("ember",    "ACOLYTE", "THE EMBER CHOIR",
     "a hooded caster that hovers, wisp at the hand", g_ember, m_ember),
    ("covenant", "HERALD",  "THE COVENANT",
     "a nun, still, with a censer on its chain", g_covenant, m_covenant),
]


def build(ch, w, h, pose):
    """(the pose's band, the ground it was drawn over) - tibases' contract."""
    g = Band(w, h)
    ch[4](g)
    b = g.copy()
    ch[5](b, pose)
    return b, g


# =============================================================================


def sheet_out(out):
    zx, zy = 3, 3
    rows = []
    for ci, ch in enumerate(CHARACTERS):
        for si, (gname, w, h, aspect) in enumerate(SURFACES):
            rows.append((ch, gname, w, h, aspect))
    cw = max(r[2] for r in rows) * zx + 18
    sh = Sheet(cw * POSES + 210, sum(int(r[3] * r[4]) * zy + 26 for r in rows) + 30)
    y = 12
    for ch, gname, w, h, aspect in rows:
        sh.text(6, y, "%s %s" % (ch[0][:9].upper(), gname), GREY, 1)
        yy = y + 12
        for p in range(POSES):
            b, _ = build(ch, w, h, p)
            sh.band(b, 200 + p * cw, yy, zx, int(round(zy * aspect)))
        y = yy + int(h * aspect) * zy + 14
    sh.save(out)
    print("%s: %dx%d" % (out, sh.w, sh.h))


def emit(path):
    lines = ["; GENERATED by tools/os88tithechar.py - do not edit.",
             "; TITHE's faction idles (SPEC.md 97.4.9): a shared GROUND - the body -",
             "; and a small moving sub-band per pose, one set per surface.",
             "",
             "TI_CHAR_N   equ %d" % len(CHARACTERS),
             "TI_CHAR_G   equ %d" % len(SURFACES),
             "TI_CHAR_BG  equ %d" % BOARD_G,
             ""]
    total = 0
    tab, body = [], []
    for ch in CHARACTERS:
        for gname, w, h, _ in SURFACES:
            tag = "tic_%s_%s" % (ch[0], gname.replace("-", ""))
            tab.append(tag)
            _, ground = build(ch, w, h, 0)
            gb = pack(ground, 0, 0, w, ground.h)
            body.append("%s:" % tag)
            body.append("    dw .g")
            for p in range(POSES):
                body.append("    dw .p%d" % p)
            body.append(".g:")
            body += _db(gb)
            total += len(gb)
            for p in range(POSES):
                bp, g2 = build(ch, w, h, p)
                bx = bbox(bp, g2)
                body.append(".p%d:" % p)
                if bx is None:
                    body.append("    db 0, 0, 0, 0")
                    continue
                x0, y0, ww, hh = bx
                body.append("    db %d, %d, %d, %d" % (x0, y0, ww, hh))
                pb = pack(bp, x0, y0, ww, hh)
                body += _db(pb)
                total += len(pb)
    lines.append("ti_char_tab:")
    for i in range(0, len(tab), 4):
        lines.append("    dw " + ", ".join(tab[i:i + 4]))
    lines.append("")
    lines += body
    open(path, "w").write("\n".join(lines) + "\n")
    print("%s: %d characters x %d surfaces, %d bytes of art"
          % (path, len(CHARACTERS), len(SURFACES), total))
    return total


def selfcheck():
    bad = []
    for ch in CHARACTERS:
        for gname, w, h, _ in SURFACES:
            bands = [build(ch, w, h, p)[0] for p in range(POSES)]
            # 1. EVERY POSE IS A PICTURE. A pose count is paid for in build
            #    time and in the claim, and art that does not vary with it is
            #    SILENT - the wheel still commits and nothing moves. It caught
            #    the base candidates at 3 distinct poses of 8.
            keys = {"\n".join("".join(map(str, r)) for r in b.px) for b in bands}
            if len(keys) < 3:
                bad.append("%s/%s: %d distinct poses of %d"
                           % (ch[0], gname, len(keys), POSES))
            # 2. AND IT IS A FIGURE, not an empty band or a filled one
            for p, b in enumerate(bands):
                frac = b.lit() / float(w * h)
                if not 0.03 < frac < 0.60:
                    bad.append("%s/%s pose %d covers %.0f%% of its band"
                               % (ch[0], gname, p, frac * 100))
            # 3. THE MOTION IS SMALL, AND THE RULE IS IN BYTES. An idle that
            #    redraws most of its band emits that whole band per pose, and
            #    four poses times three characters times eight surfaces is
            #    what this file exists to keep down. A FRACTION is the wrong
            #    bar and read as a defect on the mini units: the Ember's upper
            #    body IS most of a 24x18 band, and most of a 24x18 band is 54
            #    bytes. The budget is the board's worst case - a 64x48 band is
            #    384 bytes and half of it is 192.
            for p in range(POSES):
                bp, g = build(ch, w, h, p)
                bx = bbox(bp, g)
                if bx is None:
                    continue
                cost = (bx[2] // 8) * bx[3]
                if cost > 192:
                    bad.append("%s/%s pose %d moves %dx%d = %d bytes"
                               % (ch[0], gname, p, bx[2], bx[3], cost))
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
