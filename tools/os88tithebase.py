#!/usr/bin/env python3
"""os8088 - tools/os88tithebase.py

TITHE's BASE CANDIDATES (SPEC.md 97.2.1, docs/plans/TITHE-PLAN.md 16.1), drawn
at the exact band size every adapter asks for.

WHY A HOST TOOL AND NOT MORE ASSEMBLY. The shipping path for this art is DATA -
TITHE-PLAN 3 has `art/base/<faction>_<frame>.png -> BASES.DAT` - so a candidate
written as a procedural builder in 8086 is code that gets deleted the moment
one is picked. This is the generator that path starts from: it draws a
candidate into a 1bpp band of any size, which is what `OSAPI_GFX_BLIT1` takes,
and the same function that makes the contact sheet will make the file.

WHAT THE BOX IS. `baseh` is THREE LANES (3 x CH) and `basew` is a layout-table
field, so every surface reserves a TALL NARROW SLAB - and once each adapter's
pixel aspect is applied they are all about 1:2.5 apparent:

    surface        band      apparent (aspect-corrected)
    VGA full     56 x 156         56 x 156     1 : 2.79
    VGA window   56 x 144         56 x 144     1 : 2.57
    Hercules     72 x 108         72 x 167     1 : 2.32
    CGA          48 x  60         48 x 144     1 : 3.00

That is a tower's proportion and not a fortress's, which is the single
strongest constraint on the design: a broad low keep cannot be drawn in this
box on any surface. Every candidate below is cut to it.

THREE COLOURS, AND ONE OF THEM IS A LIE. 1bpp has two, so the mid-tone is
SPEC.md 39.4's 50% dither - which is what carries "stone" while solid white
carries "the thing you are meant to look at". A candidate that needs three real
tones is a candidate that will not survive Hercules.

ONE MOVING ELEMENT. SPEC.md 97.5.1 builds the base's GROUND once and replicates
it, drawing only the moving part per pose - so a candidate is a STATIC half and
an ANIMATED half, and the animated half is the only thing that costs per frame.
Eight poses is what the base lane plays.

    python3 tools/os88tithebase.py sheet          # build/tithe-bases-*.png
    python3 tools/os88tithebase.py --selfcheck
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88marty                                             # noqa: E402

# The band every surface asks for, and the pixel aspect it is seen through.
# ASPECT is how many times TALLER than wide one pixel is: a shape judged on the
# stored band alone is judged on the wrong picture, and CGA is 2.4x out.
SURFACES = [
    ("vga-full", 56, 156, 1.00),
    ("vga",      56, 144, 1.00),
    ("herc",     72, 108, 1.55),
    ("cga",      48,  60, 2.40),
]

POSES = 8


class Band:
    """A 1bpp band: [y][x], 1 = lit. What gfx_blit1 takes, one bit a pixel."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[0] * w for _ in range(h)]

    def set(self, x, y, v=1):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = v

    def span(self, cx, half, y, v=1):
        """A run centred on cx, `half` either side - the shape primitive."""
        for x in range(int(cx - half), int(cx + half) + 1):
            self.set(x, y, v)

    def dither(self, cx, half, y, phase=0):
        """The same run as a 50% checker - SPEC.md 39.4's mid-tone."""
        for x in range(int(cx - half), int(cx + half) + 1):
            if (x + y + phase) & 1:
                self.set(x, y, 1)

    def box(self, x0, y0, x1, y1, v=1):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.set(x, y, v)

    def frame(self, x0, y0, x1, y1):
        for x in range(int(x0), int(x1) + 1):
            self.set(x, int(y0)); self.set(x, int(y1))
        for y in range(int(y0), int(y1) + 1):
            self.set(int(x0), y); self.set(int(x1), y)

    def copy(self):
        b = Band(self.w, self.h)
        b.px = [row[:] for row in self.px]
        return b

    def lit(self):
        return sum(sum(r) for r in self.px)


def circ(t):
    """sqrt(1 - t*t), clamped.

    Python's `**0.5` on a negative is a COMPLEX NUMBER rather than an error, so
    an ellipse whose parameter strays outside [-1,1] does not raise where it
    goes wrong - it raises in the span primitive three frames later. Every arch
    and bowl below goes through here.
    """
    return max(0.0, 1.0 - t * t) ** 0.5


def sway(pose, amp):
    """A ping-pong over the pose count: 0, up to +amp, back, down to -amp.

    The placeholder's keep moved between `centred` and `one pixel right`, which
    is TWO pictures however many poses are paid for. Every candidate's motion
    goes through here so that eight frames are eight frames.
    """
    t = pose if pose < POSES // 2 else POSES - pose      # 0,1,2,3,4,3,2,1
    return (t - POSES // 4) * amp


# =============================================================================
# the candidates
#
# Each is (key, name, faction, one-line note, ground_fn, move_fn). `ground_fn`
# draws what every pose shares; `move_fn` draws pose `p` on top of a copy.
# =============================================================================

def g_mound(b):
    """1 KEEP ON A MOUND - the placeholder, kept as the control."""
    w, h, cx = b.w, b.h, b.w / 2
    for y in range(h):
        b.dither(cx, w / 8 + (y * (w / 8)) / h, y)


def m_mound(b, p):
    w, h, cx = b.w, b.h, b.w / 2
    top, foot = h // 4, h - h // 4
    for y in range(top, foot):
        half = w / 16 + ((y - top) * (w / 16)) / max(1, h // 2)
        b.span(cx + sway(p, 1), half, y)


def g_rampart(b):
    """2 THE BULWARK - a rampart and gate tower. Holds the line, so it is the
    only candidate that is WIDER at the bottom than it is tall at the top: the
    wall reads first and the tower second."""
    w, h, cx = b.w, b.h, b.w / 2
    wall_top = int(h * 0.58)
    for y in range(wall_top, h):                         # the wall, dithered
        b.dither(cx, w / 2 - 1, y)
    for y in range(wall_top, wall_top + max(2, h // 40)):   # its coping, solid
        b.span(cx, w / 2 - 1, y)
    step = max(4, w // 7)                                # crenellations
    for x in range(0, w, step * 2):
        b.box(x, wall_top - step // 2, x + step - 1, wall_top)
    tw = w / 5
    tower_top = int(h * 0.20)
    for y in range(tower_top, wall_top):                 # the gate tower
        b.dither(cx, tw, y)
    b.box(cx - tw - 1, tower_top, cx + tw + 1, tower_top + max(2, h // 40))
    gate_h = int(h * 0.26)                               # the gate itself
    for y in range(h - gate_h, h):
        r = tw * 0.7
        head = h - gate_h + r                            # ...round-headed, so
        if y < head:                                     # the gate is an arch
            r = r * circ((head - y) / max(1.0, r))       # and not a slot
        b.span(cx, r, y, 0)
    b.box(cx - w / 12, int(h * 0.30), cx + w / 12, int(h * 0.42))   # the boss


def m_rampart(b, p):
    """...and a BANNER on the tower is the only thing that moves."""
    w, h, cx = b.w, b.h, b.w / 2
    top = int(h * 0.20)
    mast = max(6, h // 9)
    for y in range(top - mast, top):
        b.set(int(cx), y)
    fly = sway(p, 1)
    for i in range(max(3, w // 8)):
        y = top - mast + 1 + (i * 3) // max(3, w // 8)
        b.span(cx + 2 + i, 0.5, y + (1 if (i + p) % 3 == 0 else 0) + fly)


def g_pyre(b):
    """3 THE EMBER CHOIR - a pyre tower. The faction pays in souls and burns
    for range, so its base is the one with a FIRE on it - and a flame is the
    most natural eight-frame loop in the game."""
    w, h, cx = b.w, b.h, b.w / 2
    # A SLENDER SHAFT. The first cut ran w/8 at the top to nearly w/2 at the
    # foot, which at 1:2.5 is not a tower, it is a fir tree - the taper has to
    # be slight or the box's own proportion is thrown away.
    base_top, foot = int(h * 0.34), int(h * 0.87)
    for y in range(base_top, foot):
        t = (y - base_top) / max(1.0, foot - base_top)
        half = w / 7 + t * (w / 14)
        b.dither(cx, half, y)
        b.set(int(cx - half), y)                         # an edge on each side
        b.set(int(cx + half), y)
    for y in range(foot, h):                             # a stepped foot, not
        t = (y - foot) / max(1.0, h - foot)              # a slab: a solid
        b.dither(cx, (w / 3.4) + t * (w / 7), y)         # block that wide read
    for y in range(foot, foot + max(2, h // 50)):        # as a crate
        b.span(cx, w / 3.4, y)
    bowl = int(h * 0.34)                                 # the brazier bowl -
    for i in range(max(3, h // 22)):                     # a shallow dish, so
        t = i / max(1.0, max(3, h // 22) - 1)            # it is not confused
        b.span(cx, (w / 4) * (0.55 + 0.45 * t), bowl + i)  # with the flame
    b.span(cx, w / 4, bowl - 1)


def m_pyre(b, p):
    """...and the flame is JAGGED, which is the shape that came first.

    It was smoothed to a teardrop on the argument that per-row jitter at 56
    pixels is noise rather than fire. On the STILL that is true; on the STRIP
    it is not, and the strip is what a flame is judged on - a smooth tip
    leaning two pixels reads as a leaf blowing, where a stepped edge reads as
    burning. The lean is kept so the whole flame still moves as one thing; the
    jitter is put back on top of it.
    """
    w, h, cx = b.w, b.h, b.w / 2
    bowl = int(h * 0.34) - 1
    tall = int(h * 0.22)
    lean = sway(p, 1)
    for i in range(tall):
        t = i / max(1.0, tall - 1)
        half = (w / 7) * circ(t) * (1.0 - 0.3 * t)
        jag = (1 if (i + p) % 3 < 2 else -1) * t * 1.6          # the tongue
        b.span(cx + lean * t * 2.0 + jag, max(0.0, half), bowl - i)
    tip = bowl - tall
    for i in range(2):                                          # ...and embers
        b.set(int(cx + lean * 2 + sway((p + i * 3) % POSES, 1)),
              tip - 2 - ((p + i * 4) % 5))


def skull(b, cx, cy, sw, sh):
    """A skull, solid with its sockets punched out. Returns False if the box is
    too small for one to read - which CGA's 48x60 band is, and a smear there is
    worse than nothing."""
    if sw < 9 or sh < 8:
        return False
    for y in range(sh):
        t = y / (sh - 1.0)
        if t < 0.62:                                            # the cranium
            half = (sw / 2) * circ(t * 0.95)
        else:                                                   # ...and a jaw
            half = (sw / 2) * 0.62 * (1.0 - (t - 0.62) * 0.9)
        b.span(cx, max(0.5, half), cy + y)
    ey = int(sh * 0.28)
    for dy in range(max(2, sh // 4)):                           # two sockets
        b.span(cx - sw * 0.23, max(0.5, sw * 0.13), cy + ey + dy, 0)
        b.span(cx + sw * 0.23, max(0.5, sw * 0.13), cy + ey + dy, 0)
    b.set(int(cx), cy + int(sh * 0.56), 0)                      # the nose
    b.span(cx, sw * 0.22, cy + int(sh * 0.72), 0)               # the teeth
    return True


def g_pyre_skull(b):
    """3b THE EMBER CHOIR again, with a SKULL cut into the shaft. The faction
    is the undead one - souls, necromancy - so the shaft carries the mark
    rather than leaving the flame to say it alone."""
    g_pyre(b)
    w, h, cx = b.w, b.h, b.w / 2
    sw = int(w / 3.2)
    sh = int(sw * 1.15)
    skull(b, cx, int(h * 0.50), sw, sh)


def g_shrine(b):
    """4 THE COVENANT - a shrine arch. Its keywords change what is about to
    happen rather than dealing damage, so its base is the one that is OPEN:
    two pillars carrying an arch, with the lane visible through it."""
    w, h, cx = b.w, b.h, b.w / 2
    pil = w / 9                                          # THIN. At w/6 the two
    top = int(h * 0.30)                                  # legs and the arch
    spring = int(h * 0.52)                               # met and it read as a
                                                         # blob with a hole
    for y in range(spring, h):                           # the two pillars
        b.dither(cx - w / 3, pil, y)
        b.dither(cx + w / 3, pil, y)
        b.set(int(cx - w / 3 - pil), y)                  # ...outlined, so a
        b.set(int(cx - w / 3 + pil), y)                  # 50% dither against
        b.set(int(cx + w / 3 - pil), y)                  # black still has an
        b.set(int(cx + w / 3 + pil), y)                  # edge
    for y in range(int(h * 0.94), h):                    # a shared step
        b.span(cx, w / 2 - 1, y)
    for y in range(top, spring):                         # the arch over them
        t = (spring - y) / max(1, spring - top)
        half = (w / 3 + pil) * circ(t)
        if half >= w / 3 - pil:
            b.dither(cx, half, y)
            if y < top + max(2, h // 40):
                b.span(cx, half, y)
    for y in range(spring - 1, spring + 1):              # the opening, kept
        b.span(cx, w / 3 - pil - 1, y, 0)                # clear of both legs
    for y in range(top - max(3, h // 22), top):          # a keystone finial
        b.span(cx, w / 14, y)


def m_shrine(b, p):
    """...and a LAMP hangs in the opening and swings, which is a pendulum and
    therefore a true ping-pong rather than a shuffle."""
    w, h, cx = b.w, b.h, b.w / 2
    hang = int(h * 0.34)
    drop = int(h * 0.14)
    x = cx + sway(p, max(1, w // 24))
    for y in range(hang, hang + drop):
        b.set(int(cx + (x - cx) * (y - hang) / max(1, drop)), y)
    r = max(1.5, w / 18)
    for y in range(hang + drop, int(hang + drop + r * 2)):
        t = (y - (hang + drop)) / max(1.0, r * 2 - 1)
        b.span(x, r * circ(2 * t - 1), y)


def g_cathedral(b):
    """5 THE COVENANT - a cathedral, and the PENDULUM is a bell.

    The swing was the thing worth keeping out of the shrine arch, and a
    belfry is where a swinging thing belongs: the opening is cut black out of
    the tower, so the bell moves inside a frame rather than over a silhouette.
    The faction is nuns - holy healing, with trickery for damage - so the front
    is devout and the one thing that is not is the SIDE DOOR, low and off
    centre, which is the only asymmetry on the board.
    """
    w, h, cx = b.w, b.h, b.w / 2
    ground = int(h * 0.95)
    for y in range(ground, h):                               # the steps
        b.span(cx, w / 2 - 1, y)
    nave_top = int(h * 0.46)
    for y in range(nave_top, ground):                        # the nave
        b.dither(cx, w / 2.7, y)
        b.set(int(cx - w / 2.7), y)
        b.set(int(cx + w / 2.7), y)
    gab = max(3, int(h * 0.07))
    for i in range(gab):                                     # its gable
        t = i / max(1.0, gab - 1.0)
        b.span(cx, (w / 2.7) * t, nave_top - gab + i)
    rr = max(2.0, w / 8)                                     # the rose window
    ry = nave_top + int(h * 0.10) + rr
    for y in range(int(ry - rr), int(ry + rr) + 1):
        hw = rr * circ((y - ry) / rr)
        b.span(cx, hw, y)
    for y in range(int(ry - rr * 0.6), int(ry + rr * 0.6) + 1):
        hw = rr * 0.6 * circ((y - ry) / (rr * 0.6))
        b.span(cx, hw, y, 0)
    b.span(cx, rr * 0.7, int(ry))                            # ...and its bars
    for y in range(int(ry - rr * 0.7), int(ry + rr * 0.7) + 1):
        b.set(int(cx), y)
    dh = int(h * 0.20)                                       # the great door
    for y in range(ground - dh, ground):
        t = (y - (ground - dh)) / max(1.0, dh)
        hw = (w / 7) if t > 0.35 else (w / 7) * circ(1.0 - t / 0.35)
        b.span(cx, hw, y, 0)
    sd = max(3, int(h * 0.07))                               # ...and the side
    b.box(cx + w / 3.6, ground - sd, cx + w / 3.6 + max(1, w // 16),
          ground - 1, 0)
    bt_bot = nave_top - gab
    bt_top = int(h * 0.14)
    for y in range(bt_top, bt_bot):                          # the belfry
        b.dither(cx, w / 5.5, y)
        b.set(int(cx - w / 5.5), y)
        b.set(int(cx + w / 5.5), y)
    cap = max(3, int(h * 0.09))
    for i in range(cap):                                     # its spire cap
        t = i / max(1.0, cap - 1.0)
        b.span(cx, (w / 5.5) * t, bt_top - cap + i)
    for y in range(bt_top - cap - max(3, int(h * 0.035)), bt_top - cap):
        b.set(int(cx), y)                                    # ...and a cross
    b.span(cx, max(1.0, w / 18), bt_top - cap - max(2, int(h * 0.024)))
    b.op_top = bt_top + max(2, int(h * 0.02))                # the OPENING the
    b.op_bot = bt_bot - max(2, int(h * 0.02))                # bell hangs in
    for y in range(b.op_top, b.op_bot):
        t = (y - b.op_top) / max(1.0, (b.op_bot - b.op_top) * 0.5)
        hw = (w / 9) if t > 1.0 else (w / 9) * circ(1.0 - t)
        b.span(cx, hw, y, 0)


def m_cathedral(b, p):
    """...and the BELL swings in it, which is the pendulum kept from the arch:
    a true ping-pong, and the one motion here that an eye reads as a rhythm
    rather than as a flicker."""
    w, h, cx = b.w, b.h, b.w / 2
    top = getattr(b, "op_top", int(h * 0.16)) + 1
    bot = getattr(b, "op_bot", int(h * 0.38))
    bw2 = max(1.5, w / 11)
    bh2 = max(3, int((bot - top) * 0.52))
    b.span(cx, w / 10, top)                                  # the headstock
    lean = sway(p, 1)
    hang = top + 2
    for y in range(hang, hang + bh2):
        t = (y - hang) / max(1.0, bh2 - 1.0)
        x = cx + lean * t * 1.3
        half = bw2 * (0.42 + 0.58 * t)
        b.span(x, half, y)
    y = hang + bh2                                           # ...and its lip
    b.span(cx + lean * 1.3, bw2 * 1.18, y)
    b.set(int(cx + lean * 1.5), y + 1)                       # the clapper


def g_zigg(b):
    """6 A STEPPED ZIGGURAT - tiers narrowing upward. The one candidate whose
    silhouette is read by its STEPS rather than its outline, which is what
    survives a 60-row CGA band best."""
    w, h, cx = b.w, b.h, b.w / 2
    # THE TIERS TAKE THE BOTTOM 58%, the shrine the next 14%, and the rest is
    # left EMPTY for the smoke. Filling the band to its top left the moving
    # half nowhere to go: it was drawn above row 0 and clipped away entirely,
    # and the selfcheck's "MOVES" column read 0 with the picture looking fine.
    tiers = 4
    tier_top = int(h * 0.42)
    for i in range(tiers):                               # i = 0 is the TOP
        y0 = int(h - (h - tier_top) * (tiers - i) / tiers)
        y1 = int(h - (h - tier_top) * (tiers - i - 1) / tiers) - 1
        half = (w / 5) + (w / 2 - 1 - w / 5) * i / (tiers - 1)
        for y in range(y0, y1 + 1):
            b.dither(cx, half, y)
        for y in range(y0, y0 + max(2, h // 50)):        # each tier's coping
            b.span(cx, half, y)
    sh = int(h * 0.14)                                   # the shrine on top
    b.box(cx - w / 9, tier_top - sh, cx + w / 9, tier_top - 1)
    b.box(cx - w / 9 + 1, tier_top - sh + 2, cx + w / 9 - 1, tier_top - 3, 0)


def m_zigg(b, p):
    """...with SMOKE climbing out of the shrine on top."""
    w, h, cx = b.w, b.h, b.w / 2
    top = int(h * 0.42) - int(h * 0.14)
    for i in range(min(top - 1, int(h * 0.24))):
        y = top - 2 - i
        if (i + p) % 3 == 0:                             # ...a broken column,
            continue                                     # which is what smoke
        x = int(cx + sway((p + i) % POSES, 1) + i // 6)   # is at this size
        b.set(x, y)
        if i > 3 and (i + p) % 4 == 0:
            b.set(x + 1, y)


# THE CATHEDRAL SPIRE WAS HERE AND IS WITHDRAWN. It read as a rocket - a
# tapering solid cone with fins is a rocket whatever is on top of it, and at
# 1:2.5 with no room for tracery there is nothing to say otherwise. The thing
# worth keeping out of it, a church for THE COVENANT, is g_cathedral above,
# where the mass is a nave and the height is a belfry rather than one cone.


CANDIDATES = [
    ("mound",   "KEEP ON A MOUND", "-- control --",
     "the placeholder, kept so the others are judged against something",
     g_mound, m_mound),
    ("rampart", "RAMPART GATE",    "THE BULWARK",
     "a wall that reads first and a tower second; a banner is what moves",
     g_rampart, m_rampart),
    ("pyre",    "PYRE TOWER",      "THE EMBER CHOIR",
     "a brazier on a slender shaft, and the JAGGED flame is the eight frames",
     g_pyre, m_pyre),
    ("skull",   "PYRE TOWER + SKULL", "THE EMBER CHOIR",
     "the same, with the undead faction's mark cut into the shaft",
     g_pyre_skull, m_pyre),
    ("cathed",  "CATHEDRAL BELL",  "THE COVENANT",
     "the arch's pendulum put where one belongs - a belfry, and a side door",
     g_cathedral, m_cathedral),
    ("shrine",  "SHRINE ARCH",     "THE COVENANT",
     "the swing it came from, kept for comparison; open rather than solid",
     g_shrine, m_shrine),
    ("zigg",    "STEPPED ZIGGURAT", "any",
     "read by its steps rather than its outline, which survives CGA's 60 rows",
     g_zigg, m_zigg),
]


def build(cand, w, h, pose):
    """One pose of one candidate at one band size."""
    _, _, _, _, ground, move = cand
    b = Band(w, h)
    ground(b)
    g = b.copy()
    move(b, pose)
    return b, g


# =============================================================================
# the contact sheet
# =============================================================================

WHITE, BLACK, GREY, RED = (255, 255, 255), (0, 0, 0), (70, 70, 70), (190, 60, 60)

FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "11110", "10001", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "11110", "10000", "10000", "10000", "11111"],
    "F": ["11111", "10000", "11110", "10000", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10101", "10011", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ":": ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    "x": ["00000", "00000", "10001", "01010", "00100", "01010", "10001"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    " ": ["00000"] * 7,
}


class Sheet:
    def __init__(self, w, h, bg=BLACK):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * (w * h))

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, c)

    def text(self, x, y, s, c=WHITE, z=1):
        for ch in s.upper() if s.upper() in FONT or True else s:
            pass
        cx = x
        for ch in s:
            g = FONT.get(ch.upper() if ch.upper() in FONT else ch, FONT[" "])
            for gy, row in enumerate(g):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        for dy in range(z):
                            for dx in range(z):
                                self.set(cx + gx * z + dx, y + gy * z + dy, c)
            cx += (len(g[0]) + 1) * z
        return cx

    def band(self, band, x, y, zx, zy, ink=WHITE):
        for by in range(band.h):
            for bx in range(band.w):
                if band.px[by][bx]:
                    for dy in range(zy):
                        for dx in range(zx):
                            self.set(x + bx * zx + dx, y + by * zy + dy, ink)

    def save(self, path):
        os88marty.write_png_rgb(path, self.w, self.h, bytes(self.px))


def sheet_surface(name, w, h, aspect, out):
    """Every candidate at one surface's band size, aspect-corrected.

    POSE 0 LARGE and all eight beside it: a silhouette is chosen on the still
    and an animation is judged on the strip, and neither view answers the
    other's question.
    """
    zx, zy = 3, max(1, round(3 * aspect))                # the big one
    sx, sy = 2, max(1, round(2 * aspect))                # ...and the strip
    cellw, cellh = w * zx, h * zy
    striph = h * sy
    stripw = POSES * (w * sx + 6)
    rowh = max(cellh, striph) + 104
    sheetw = 24 + cellw + 28 + stripw + 24
    s = Sheet(max(sheetw, 560), 84 + len(CANDIDATES) * rowh + 16)
    s.text(24, 22, "TITHE BASE CANDIDATES - %s" % name.upper(), WHITE, 2)
    s.text(24, 48, "BAND %dx%d   PIXEL ASPECT %s   SHOWN AS SEEN"
           % (w, h, "1.00" if aspect == 1 else "1 x %.2f" % aspect), GREY, 1)
    s.text(24, 62, "LEFT: POSE 0 AT 3X.   RIGHT: ALL 8 POSES AT 2X.", GREY, 1)
    for i, cand in enumerate(CANDIDATES):
        key, title, faction, note, _, _ = cand
        y = 84 + i * rowh
        s.rect(24, y, s.w - 24, y, GREY)
        s.text(24, y + 10, "%d  %s" % (i + 1, title), WHITE, 2)
        s.text(24, y + 32, faction, RED if faction != "any" else GREY, 1)
        s.text(24, y + 44, note[:86], GREY, 1)
        b0, ground = build(cand, w, h, 0)
        top = y + 58
        s.band(b0, 24, top, zx, zy)
        s.text(24, top + cellh + 8, "%d LIT   GROUND %d   MOVES %d"
               % (b0.lit(), ground.lit(), abs(b0.lit() - ground.lit())), GREY, 1)
        x = 24 + cellw + 28
        for p in range(POSES):
            bp, _ = build(cand, w, h, p)
            s.band(bp, x, top, sx, sy)
            s.text(x, top + striph + 6, str(p), GREY, 1)
            x += w * sx + 6
    s.save(out)
    return s.w, s.h


# =============================================================================
# in situ - the candidate dropped into a REAL board, at the REAL position
#
# A contact sheet answers "does this silhouette read"; it cannot answer "does
# it read BESIDE TWENTY FIGURES ON A DITHERED GRID", which is the question the
# board actually asks. This boots TITHE, reads the layout out of the guest, and
# paints each candidate where the machine puts its base.
# =============================================================================

def insitu(machine, out, label, herc=False):
    sys.path.insert(0, os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "..", "tests"))
    import os88ui, os88geom                                      # noqa: E402

    syms = ("ti_b1x", "ti_b2x", "ti_basey", "ti_basey2", "ti_basew",
            "ti_baseh", "ti_bas", "ti_cw")
    import struct
    import subprocess
    src = open("apps/tithe/tithe.asm", encoding="utf-8").read()
    open("build/tithebase-off.asm", "w").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % x for x in syms))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/", "-I",
                    "apps/tithe/", "-o", "build/tithebase-off.bin",
                    "build/tithebase-off.asm"], check=True)
    base = os.path.getsize("build/tithe.bin")
    blob = open("build/tithebase-off.bin", "rb").read()
    off = {x: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
           for i, x in enumerate(syms)}

    with os88ui.boot("build/os8088-360.img", apps="build/tithe360.img",
                     machine=machine) as ui:
        m = ui.m
        ui.path("B:/TITHE.O88")
        win = [x for x in os88geom.windows(m) if x.title == "Tithe"][0]
        seg = struct.unpack("<H", bytes(m.read(
            os88geom.winptr(m, win) + os88geom.W_SEG, 2)))[0]
        ui.raise_window(win)
        os88marty.guest_sleep(m, 7.0)
        v = {k: struct.unpack("<H", bytes(m.readseg(seg, off[k], 2)))[0]
             for k in syms}
        # THE LAYOUT IS ALREADY IN SCREEN COORDINATES. OSAPI_WM_GEOM answers
        # the content rect absolutely, so ti_basey IS a screen row - adding the
        # window's content origin on top put every band 48 rows BELOW the board
        # it was pasted into, and the real placeholder showed through above it.
        # Asserted rather than assumed, below.
        ox, oy = 0, 0
        if herc:
            w, h, rows = m.vram()
            px = [[(255 if c else 0) for c in row] for row in rows]
        else:
            w, h, d = m.fbuf()
            px = [[d[(y * w + x) * 3] for x in range(w)] for y in range(h)]
    bw, bh = v["ti_basew"], v["ti_baseh"]
    print("  %s: base %dx%d at (%d,%d) and (%d,%d)"
          % (label, v["ti_basew"], v["ti_baseh"], v["ti_b1x"], v["ti_basey"],
             v["ti_b2x"], v["ti_basey2"]))
    # THE PLACEMENT IS CHECKED AND NOT TRUSTED: the band's own top row must
    # have something in it and the row above it must be empty, which is true of
    # every base here (the HP block sits 10 rows higher) and false of any
    # off-by-a-content-origin.
    def litrow(y, x0, x1):
        return sum(1 for x in range(x0, x1) if 0 <= y < h and px[y][x] > 127)
    for who, bx, by in (("p1", v["ti_b1x"], v["ti_basey"]),
                        ("p2", v["ti_b2x"], v["ti_basey2"])):
        inside = litrow(by + 2, bx, bx + bw)
        above = litrow(by - 2, bx, bx + bw)
        print("     %s band top row %d lit, the row above it %d"
              % (who, inside, above))
        if inside == 0 or above != 0:
            print("     ** the band is NOT where this thinks it is **")

    pads = 6
    cw = min(w - ox, bw + 2 * v["ti_cw"] + 16)
    cy0 = max(0, oy + v["ti_basey"] - 22)
    ch = min(h - cy0, bh + 40)
    aspect = 1.55 if herc else 1.0
    zx = 2
    zy = max(1, round(2 * aspect))
    s = Sheet(24 + cw * zx + 24, 76 + len(CANDIDATES) * (ch * zy + 34))
    s.text(24, 22, "TITHE BASES IN SITU - %s" % label.upper(), WHITE, 2)
    s.text(24, 48, "P1'S BASE WHERE THE MACHINE PUTS IT, WITH ITS HP BLOCK ABOVE IT."
           "  BAND %dx%d." % (bw, bh), GREY, 1)
    for i, cand in enumerate(CANDIDATES):
        b0, _ = build(cand, bw, bh, 0)
        y = 76 + i * (ch * zy + 34)
        s.text(24, y, "%d  %s" % (i + 1, cand[1]), WHITE, 1)
        for cy in range(ch):
            for cx2 in range(cw):
                sx, sy = ox + cx2, cy0 + cy
                lit = px[sy][sx] > 127 if 0 <= sy < h and 0 <= sx < w else 0
                by = sy - (oy + v["ti_basey"])
                bx = sx - (ox + v["ti_b1x"])
                if 0 <= by < bh and 0 <= bx < bw:        # the band replaces
                    lit = b0.px[by][bx]                  # the placeholder
                if lit:
                    for dy in range(zy):
                        for dx in range(zx):
                            s.set(24 + cx2 * zx + dx, y + 14 + cy * zy + dy,
                                  WHITE)
    s.save(out)
    print("%s: %dx%d" % (out, s.w, s.h))


def selfcheck():
    bad = []
    for name, w, h, _ in SURFACES:
        for cand in CANDIDATES:
            seen = set()
            for p in range(POSES):
                b, g = build(cand, w, h, p)
                if b.lit() == 0:
                    bad.append("%s/%s pose %d is EMPTY" % (name, cand[0], p))
                if g.lit() == 0:
                    bad.append("%s/%s has no GROUND" % (name, cand[0]))
                seen.add(tuple(tuple(r) for r in b.px))
            # EIGHT POSES MUST BE EIGHT PICTURES - the defect this whole file
            # exists downstream of. Four is the ping-pong's own floor.
            if len(seen) < (POSES + 1) // 2:
                bad.append("%s/%s is %d distinct poses of %d"
                           % (name, cand[0], len(seen), POSES))
            # ...and it has to fit the box it was handed.
            b, _ = build(cand, w, h, 0)
            if len(b.px) != h or len(b.px[0]) != w:
                bad.append("%s/%s is not %dx%d" % (name, cand[0], w, h))
    for line in bad:
        print("  FAIL %s" % line)
    print("os88tithebase: %d candidate(s) x %d surface(s) x %d poses, %s"
          % (len(CANDIDATES), len(SURFACES), POSES,
             "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("cmd", nargs="?", default="sheet",
                    choices=["sheet", "insitu"])
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("-o", "--outdir", default="build")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    os.makedirs(a.outdir, exist_ok=True)
    if a.cmd == "insitu":
        insitu("os8088_xt_vga", os.path.join(a.outdir, "tithe-bases-situ-vga.png"),
               "vga")
        insitu("os8088_5150_herc_gla",
               os.path.join(a.outdir, "tithe-bases-situ-herc.png"), "herc",
               herc=True)
        return 0
    for name, w, h, aspect in SURFACES:
        out = os.path.join(a.outdir, "tithe-bases-%s.png" % name)
        sw, sh = sheet_surface(name, w, h, aspect, out)
        print("%s: %dx%d  (band %dx%d, aspect %.2f)" % (out, sw, sh, w, h, aspect))
    return 0


if __name__ == "__main__":
    sys.exit(main())
