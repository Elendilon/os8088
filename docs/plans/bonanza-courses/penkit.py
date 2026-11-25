#!/usr/bin/env python3
"""The PEN for courses 5 - 7's paper sketches (wave 11's pipeline, the pen-in step: README.md section 3).
Host-only; nothing in `make` runs it and it ships nothing.  It is mill/sketch.py's drawing made a module, so
kite/sketch.py, lode/sketch.py and keep/sketch.py hold only their DESIGN: each lays its sections with a Pen
and the pen draws plan.png and iso.png and writes the engine course (`--bbc`).

A section is laid ONCE and feeds three things: the plan, the picture in the game's projection, and the
`.bbc` text - so the sheet's pictures and the pen-in course cannot disagree about where a floor is.

The cells are the ENGINE's cells (no offset): +wx runs down-right on the screen, +wy down-left, a height unit
is 8 px (SPEC.md 130.10.2).  A prop the engine has is laid by its own method (the `.bbc` line and its glyph
together); `raw()` is a `.bbc` line the pen draws nothing for; `note()` is a label on the pictures alone.
"""
import math
import os
import sys
from PIL import Image, ImageDraw

GLYPH = {"ring": "o", "plus": "+", "box": "#", "cross": "x"}
BALLCOL = {"rubber": (255, 90, 200), "steel": (170, 180, 200), "glass": (120, 240, 255)}
DIRV = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}


def P(wx, wy, z):
    """the game's projection (SPEC.md 130.10.2), before the origin"""
    return 16 * (wx - wy), 8 * (wx + wy) - 8 * z


class Pen:
    def __init__(self, tag, title, head, ground=None):
        self.tag, self.title, self.head = tag, title, head
        self.cells = {}          # (wx, wy) -> corner heights (nw, ne, se, sw)
        self.sec = {}            # (wx, wy) -> section letter
        self.walls = {}          # (wx, wy) -> z
        self.wallcol = {}        # (wx, wy) -> colour (a tower, a house, a pier)
        self.thick = {}          # (wx, wy) -> a FLOATING cell's thickness (units)
        self.tint = {}           # (wx, wy) -> colour over the section's (sand, water, a crack, a deck ...)
        self.cutc = {}           # (wx, wy) -> the half CUT AWAY (up, down, left, right): a diagonal corner
        self.rooms = []          # the .bbc's room lines, in order
        self.floats = []
        self.rails = []          # (x0, y0, x1, y1, sides or None)
        self.lines = []          # the .bbc's prop lines, in order
        self.glyphs = []         # (kind, dict)
        self.notes = []          # (wx, wy, text, colour)
        self.route, self.branches = [], {}
        self.flags, self.clocks, self.goals = [], [], []
        self.start = None
        self.windows = []        # ((wx, wy), name): a CGA window drawn round a screen the design is made for
        self.seccol = {}
        self.ground = ground     # the height every grounded face is drawn down to (None: the lowest floor - 3)
        self.legend = []
        self.allfloat = None     # every floor without a thickness of its own floats this thick
        self.scale = 1           # the iso picture's scale (a small course drawn larger)
        self.plan_s = 20         # the plan's px a tile
        self.plan_pad = (0, 9)   # tiles of margin left and right of the plan, for its labels

    # ---- the ground -----------------------------------------------------------------------------------
    def col(self, sec, rgb):
        self.seccol[sec] = rgb

    def floor(self, sec, x0, y0, x1, y1, z, note=""):
        self.rooms.append("floor rect %3d %3d %3d %3d  flat %g%s" % (x0, y0, x1, y1, z, "   # " + (note or sec)))
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.cells[(x, y)] = (z, z, z, z)
                self.sec[(x, y)] = sec
                self.walls.pop((x, y), None)

    def ramp(self, sec, axis, x0, y0, x1, y1, z0, z1, note=""):
        """z0 at the low-coordinate edge of `axis`, z1 at the high one"""
        p0, p1 = (x0, x1) if axis == "x" else (y0, y1)
        self.rooms.append("floor rect %3d %3d %3d %3d  ramp %s %d %d %g %g%s"
                          % (x0, y0, x1, y1, axis, p0, p1, z0, z1, "   # " + (note or sec)))
        n = (x1 - x0) if axis == "x" else (y1 - y0)
        for x in range(x0, x1):
            for y in range(y0, y1):
                i = (x - x0) if axis == "x" else (y - y0)
                a, b = z0 + (z1 - z0) * i / n, z0 + (z1 - z0) * (i + 1) / n
                self.cells[(x, y)] = (a, b, b, a) if axis == "x" else (a, a, b, b)
                self.sec[(x, y)] = sec

    def wall(self, x0, y0, x1, y1, z, col=None, bounce=False, note="", thick=None):
        """thick: on a floating course, how far down the block's faces go (a tower's)"""
        self.rooms.append("wall  rect %3d %3d %3d %3d  flat %g%s" % (x0, y0, x1, y1, z, "   # " + note if note else ""))
        if thick:
            self.floats.append("float rect %3d %3d %3d %3d thick %g" % (x0, y0, x1, y1, thick))
            for x in range(x0, x1):
                for y in range(y0, y1):
                    self.thick[(x, y)] = thick
        if bounce:
            self.rooms.append("surface bounce rect %d %d %d %d" % (x0, y0, x1, y1))
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.walls[(x, y)] = z
                self.cells.pop((x, y), None)
                if col or bounce:
                    self.wallcol[(x, y)] = col or (210, 70, 170)

    def float(self, x0, y0, x1, y1, thick=None):
        """the cells FLOAT (SPEC.md 130.27.2): short icicle faces, not faces down to the ground"""
        self.floats.append("float rect %3d %3d %3d %3d%s" % (x0, y0, x1, y1, " thick %g" % thick if thick else ""))
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.thick[(x, y)] = thick or 3

    def float_all(self, x0, y0, x1, y1):
        """the whole course floats (the pathway's look, SPEC.md 130.27.2): laid FIRST, so a bridge's or a
        plate's own `thick` after it still holds"""
        self.floats.insert(0, "float rect %3d %3d %3d %3d" % (x0, y0, x1, y1))
        self.allfloat = 3

    def cut(self, x, y, side):
        """a DIAGONAL corner (SPEC.md 130.24.4): the cell's half on that side of the SCREEN is cut away"""
        self.rooms.append("hole  half %s tile %d %d          # a diagonal corner" % (side, x, y))
        self.cutc[(x, y)] = side

    def octa(self, x0, y0, x1, y1):
        """the rect's four corners cut on the diagonal: the platform reads as an octagon"""
        self.cut(x0, y0, "up")
        self.cut(x1 - 1, y0, "right")
        self.cut(x0, y1 - 1, "left")
        self.cut(x1 - 1, y1 - 1, "down")

    def surface(self, name, x0, y0, x1, y1, rgb):
        self.lines.append("surface %s rect %d %d %d %d" % (name, x0, y0, x1, y1))
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.tint[(x, y)] = rgb

    def guard(self, x0, y0, x1, y1, sides=None, height=None):
        """a see-through GUARD RAIL on the floor's edges (SPEC.md 130.35.1): `sides` None rails every OPEN
        edge of the rect's outline"""
        self.rails.append((x0, y0, x1, y1, sides))
        self.rooms.append(("guard rect %3d %3d %3d %3d" % (x0, y0, x1, y1)) +
                          (" side " + " ".join(sides) if sides else "") + (" height %g" % height if height else ""))

    # ---- props: the .bbc line and its glyph together -----------------------------------------------------
    def raw(self, line):
        self.lines.append(line)

    def comment(self, text):
        self.lines.append("# " + text)

    def g(self, kind, **kw):
        self.glyphs.append((kind, kw))

    def note(self, wx, wy, text, colour=(255, 255, 255), z=None):
        self.notes.append((wx, wy, text, colour, z))

    def znear(self, wx, wy):
        """the floor's height at a point, or the nearest floor's"""
        z = self.zat(wx, wy)
        if z is not None:
            return z
        best = None
        for (x, y), c in list(self.cells.items()) + [(k, (v,) * 4) for k, v in self.walls.items()]:
            dd = (x + 0.5 - wx) ** 2 + (y + 0.5 - wy) ** 2
            if best is None or dd < best[0]:
                best = (dd, max(c))
        return best[1] if best else 0

    def blower(self, x, y, face, region, strength, gust=None, seed=None, top=None, lift=False, flag=False):
        s = "prop blower %d %d face %s region %d %d %d %d strength %d" % ((x, y, face) + tuple(region) + (strength,))
        if gust:
            s += " gust %d %d" % gust + (" seed %d" % seed if seed else "")
        if top:
            s += " top %g" % top
        s += (" lift" if lift else "") + (" flag" if flag else "")
        self.lines.append(s)
        self.g("blower", at=(x, y), face=face, region=region, gust=gust, top=top, flag=flag)

    def magnet(self, x, y, face, rng=1, strength=None, down=None):
        """a SIDE magnet (its field `rng` cells out along `face`, pulling toward the post) or, with `down`
        the arm's way, a HANGING one over the next cell that way (SPEC.md 130.33)"""
        if down:
            s = "prop magnet %d %d face down %s" % (x, y, down)
        else:
            s = "prop magnet %d %d face %s" % (x, y, face) + (" range %d" % rng if rng != 1 else "")
        self.lines.append(s + (" strength %d" % strength if strength else ""))
        self.g("magnet", at=(x, y), face=down or face, rng=rng, down=bool(down))

    def crack(self, x, y):
        self.lines.append("prop crack %d %d" % (x, y))
        self.tint[(x, y)] = (235, 235, 215)
        self.g("crack", at=(x, y))

    def pad(self, ball, x, y):
        self.lines.append("pad %s %d %d" % (ball, x, y))
        self.g("pad", at=(x, y), ball=ball)

    def spring(self, x, y, v):
        self.lines.append("spring %d %d %d" % (x, y, v))
        self.g("spring", at=(x, y))

    def boost(self, x, y, face, strength=None, flat=False):
        self.lines.append("prop boost %d %d face %s" % (x, y, face) + (" strength %d" % strength if strength else "")
                          + (" flat" if flat else ""))
        self.g("boost", at=(x, y), face=face)

    def plate(self, x, y, ch):
        self.lines.append("prop plate %d %d channel %s" % (x, y, ch))
        self.g("plate", at=(x, y), ch=ch)

    def key(self, x, y, ch):
        self.lines.append("prop key %d %d channel %s" % (x, y, ch))
        self.g("key", at=(x, y), ch=ch)

    def gate(self, x, y, ch, along, art=None, style=None):
        self.lines.append("prop gate %d %d channel %s along %s" % (x, y, ch, along) +
                          (" art %s" % art if art else "") + (" style %s" % style if style else ""))
        self.g("gate", at=(x, y), ch=ch, along=along, art=art)

    def bridge(self, x0, y0, x1, y1, ch=None, period=None, on=None, seed=None, style=None, thick=0.5):
        """a DRAWBRIDGE (SPEC.md 130.41): switched by a channel, or timed"""
        self.floats.append("float rect %3d %3d %3d %3d thick %g" % (x0, y0, x1, y1, thick))
        s = "prop bridge %d %d %d %d " % (x0, y0, x1, y1)
        s += "channel %s" % ch if ch else "period %d on %d" % (period, on) + (" seed %d" % seed if seed else "")
        self.lines.append(s + (" style %s" % style if style else ""))
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.thick[(x, y)] = thick
                self.tint[(x, y)] = (200, 150, 90)
                self.g("bridge", at=(x, y), ch=ch)

    def popspikes(self, cells, period, on, seed=0, step=1):
        """a row of POP-UP SPIKES (SPEC.md 130.38), each cell `step` after the last"""
        for i, (x, y) in enumerate(cells):
            self.lines.append("prop popspikes %d %d period %d on %d seed %d" % (x, y, period, on, (seed + i * step) % period))
            self.g("spikes", at=(x, y), pop=True)

    def spikes(self, x0, y0, x1, y1):
        self.lines.append("prop spikes %d %d %d %d" % (x0, y0, x1, y1))
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.g("spikes", at=(x, y), pop=False)

    def seesaw(self, x0, y0, x1, y1, along, pivot, rest=None, period=None, flat=None, seed=None, sec="W"):
        """a SEE-SAW (SPEC.md 130.42), a weight plate or (with `period`) a TIMED one; drawn at rest"""
        s = "seesaw %d %d %d %d along %s pivot %g" % (x0, y0, x1, y1, along, pivot)
        s += (" rest %s" % rest if rest else "") + (" period %d" % period if period else "")
        s += (" flat %d" % flat if flat else "") + (" seed %d" % seed if seed else "")
        self.lines.append(s)
        n = (x1 - x0) if along == "x" else (y1 - y0)
        tilt = 1.0 * (-1 if rest == "+" else 1)          # at rest its minus end is DOWN (a unit under the pivot)
        for x in range(x0, x1):
            for y in range(y0, y1):
                i = (x - x0) if along == "x" else (y - y0)
                a = pivot + tilt * (2.0 * i / n - 1)
                b = pivot + tilt * (2.0 * (i + 1) / n - 1)
                self.cells[(x, y)] = (a, b, b, a) if along == "x" else (a, a, b, b)
                self.sec[(x, y)] = sec
                self.thick[(x, y)] = 0.5
        self.g("seesaw", box=(x0, y0, x1, y1), along=along, pivot=pivot, timed=bool(period))

    def turntable(self, x, y, size, fill, seed=None, quarter=None):
        self.lines.append("prop turntable %d %d size %d fill %s" % (x, y, size, fill) +
                          (" quarter %d" % quarter if quarter else "") + (" seed %d" % seed if seed else ""))
        self.g("turn", at=(x, y), size=size)

    def lift(self, x, y, rise, period=None, zlow=0):
        self.lines.append("prop platform %d %d %d" % (x, y, rise) + (" period %d" % period if period else ""))
        self.g("lift", at=(x, y), rise=rise, z=zlow)

    def hump(self, x, y, z, along=None, n=None, height=None, open_=False):
        s = "hump %d %d %g" % (x, y, z)
        if along:
            s += " along %s %d" % (along, n) + (" open" if open_ else "")
        self.lines.append(s + (" height %d" % height if height else ""))
        self.g("hump", at=(x, y), z=z, along=along, n=n or 0, h=height or 6)

    def pit(self, x, y, z, radius, depth, hole=None):
        self.lines.append("pit %d %d %g radius %d depth %d" % (x, y, z, radius, depth) +
                          (" hole %d" % hole if hole is not None else ""))
        self.g("pit", at=(x, y), z=z, r=radius, hole=1 if hole is None else hole)

    def chute(self, width, prof, depth, ways, sec="U"):
        """ways: (x, y, z) points on the crease (SPEC.md 130.28.3); the pen lays its cells flat at the lip,
        a leg's slope along it, so the pictures show where the channel runs"""
        self.lines.append("chute %d %s depth %d " % (width, prof, depth) +
                          " ".join("way %d %d %g" % w for w in ways))
        self.seccol.setdefault(sec, (205, 120, 205))
        span = {1: (0, 1), 2: (-1, 1), 3: (-1, 2)}[width]
        for (x0, y0, z0), (x1, y1, z1) in zip(ways, ways[1:]):
            n = max(abs(x1 - x0), abs(y1 - y0))
            for i in range(n + 1):
                cx, cy = x0 + (x1 - x0) * i // n, y0 + (y1 - y0) * i // n
                za, zb = z0 + (z1 - z0) * max(i - 0.5, 0) / n, z0 + (z1 - z0) * min(i + 0.5, n) / n
                for a in range(*span):
                    for b in range(*span):
                        if (cx + a, cy + b) in self.sec and self.sec[(cx + a, cy + b)] == sec:
                            continue
                        along_x = x1 != x0
                        if (along_x and b != 0 and i not in (0, n)) or (not along_x and a != 0 and i not in (0, n)):
                            pass
                        lo, hi_ = (za, zb) if (x1 > x0 or y1 > y0) else (zb, za)
                        self.cells[(cx + a, cy + b)] = ((lo, hi_, hi_, lo) if along_x else (lo, lo, hi_, hi_))
                        self.sec[(cx + a, cy + b)] = sec
        self.g("chute", ways=ways, width=width)

    def tube(self, kind, a, b, vias=(), extra=""):
        self.lines.append("tube %s %d %d %d %d " % ((kind,) + tuple(a) + tuple(b)) +
                          " ".join("via %d %d" % v for v in vias) + (" " + extra if extra else ""))
        self.g("tube", pts=[a] + list(vias) + [b])

    def pickup(self, kind, x, y, extra=""):
        self.lines.append("prop %s %d %d%s" % (kind, x, y, " " + extra if extra else ""))
        self.g("pickup", at=(x, y), kind=kind)

    def archway(self, x, y, along, under=None):
        self.lines.append("archway tile %d %d along %s" % (x, y, along) + (" under %g" % under if under else ""))
        self.g("arch", at=(x, y), along=along)

    def water(self, x0, y0, x1, y1, top, bed, extra=""):
        self.lines.append("water rect %d %d %d %d top %g bed %g%s" % (x0, y0, x1, y1, top, bed, " " + extra if extra else ""))
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.cells[(x, y)] = (top, top, top, top)
                self.sec.setdefault((x, y), "~")
                self.tint[(x, y)] = (70, 130, 235)

    def goal(self, x0, y0, x1, y1, z, exit=0, hidden=False):
        self.goals.append((x0, y0, x1, y1, z, exit, hidden))
        for x in range(x0, x1):
            for y in range(y0, y1):
                self.cells[(x, y)] = (z, z, z, z)
                self.sec[(x, y)] = "!"

    def cup(self, x, y):
        self.lines.append("cup %d %d" % (x, y))
        self.g("cup", at=(x, y))

    def flag(self, x, y, ball="rubber", name=None):
        self.flags.append((x, y, ball, name or "flag %d" % len(self.flags)))

    def clock(self, x, y, z, name, own_tile=False, frame=None):
        """a clock on (x, y); own_tile: a tile of its own laid at z (one out from the path)"""
        self.clocks.append((x, y, z, name, own_tile, frame))

    # ---- geometry helpers -----------------------------------------------------------------------------
    def zat(self, wx, wy):
        c = self.cells.get((int(math.floor(wx)), int(math.floor(wy))))
        if not c:
            return self.walls.get((int(math.floor(wx)), int(math.floor(wy))), None)
        fx, fy = wx - math.floor(wx), wy - math.floor(wy)
        nw, ne, se, sw = c
        return nw * (1 - fx) * (1 - fy) + ne * fx * (1 - fy) + se * fx * fy + sw * (1 - fx) * fy

    def top(self, x, y):
        if (x, y) in self.cells:
            return max(self.cells[(x, y)])
        return self.walls.get((x, y))

    def rail_edges(self):
        """every railed edge as ((wx, wy) of the floor cell, side)"""
        out = set()
        for x0, y0, x1, y1, sides in self.rails:
            for x in range(x0, x1):
                for y in range(y0, y1):
                    if (x, y) not in self.cells:
                        continue
                    for side, (a, b) in DIRV.items():
                        n = (x + a, y + b)
                        inside = x0 <= n[0] < x1 and y0 <= n[1] < y1 and n in self.cells
                        if inside:
                            continue
                        if sides:
                            if side in sides or "all" in sides:
                                out.add(((x, y), side))
                        else:
                            zt = self.top(*n)
                            if zt is None or zt < min(self.cells[(x, y)]) - 0.01:
                                out.add(((x, y), side))
        return out

    def route_len(self, r):
        return sum(((c - a) ** 2 + (e - b) ** 2) ** 0.5 for (a, b), (c, e) in zip(r, r[1:]))

    # ---- the plan -----------------------------------------------------------------------------------
    def plan(self, out, S=None):
        S = S or self.plan_s
        xs = [k[0] for k in self.cells] + [k[0] for k in self.walls]
        ys = [k[1] for k in self.cells] + [k[1] for k in self.walls]
        mx, my = min(xs) - 2 - self.plan_pad[0], min(ys) - 2
        W, H = (max(xs) - mx + 3 + self.plan_pad[1]) * S, (max(ys) - my + 3) * S + 76
        im = Image.new("RGB", (W, H), (20, 20, 30))
        d = ImageDraw.Draw(im, "RGBA")
        zs = [max(c) for c in self.cells.values()]
        zlo, zhi = min(zs), max(zs) + 1

        def X(x):
            return (x - mx) * S

        def Y(y):
            return (y - my) * S
        for (x, y), c in self.cells.items():
            base = self.tint.get((x, y)) or self.seccol.get(self.sec[(x, y)], (150, 200, 150))
            k = 0.55 + 0.45 * (sum(c) / 4 - zlo) / (zhi - zlo)
            if (x, y) in self.cutc:
                T, R, B_, L = (X(x), Y(y)), (X(x) + S - 1, Y(y)), (X(x) + S - 1, Y(y) + S - 1), (X(x), Y(y) + S - 1)
                tri = {"up": (R, B_, L), "down": (T, R, L), "left": (T, R, B_), "right": (T, B_, L)}[self.cutc[(x, y)]]
                d.polygon(tri, fill=tuple(int(v * k) for v in base), outline=(60, 60, 70))
                continue
            d.rectangle([X(x), Y(y), X(x) + S - 1, Y(y) + S - 1], fill=tuple(int(v * k) for v in base),
                        outline=(60, 60, 70))
            if len(set(c)) > 1:
                dx, dy = (c[1] - c[0]), (c[3] - c[0])
                t = (">" if dx < 0 else "<") if dx else ("v" if dy < 0 else "^")
                d.text((X(x) + 7, Y(y) + 4), t, fill=(0, 0, 0))
        for (x, y), z in self.walls.items():
            d.rectangle([X(x), Y(y), X(x) + S - 1, Y(y) + S - 1], fill=self.wallcol.get((x, y), (110, 80, 70)),
                        outline=(60, 50, 50))
        for (x, y), side in self.rail_edges():
            a, b = DIRV[side]
            if a:
                ex = X(x) + (S - 1 if a > 0 else 0)
                d.line([ex, Y(y), ex, Y(y) + S - 1], fill=(255, 220, 0), width=3)
            else:
                ey = Y(y) + (S - 1 if b > 0 else 0)
                d.line([X(x), ey, X(x) + S - 1, ey], fill=(255, 220, 0), width=3)
        for kind, k in self.glyphs:
            self._plan_glyph(d, kind, k, X, Y, S)
        for x0, y0, x1, y1, z, ex, hid in self.goals:
            for x in range(x0, x1):
                for y in range(y0, y1):
                    d.rectangle([X(x), Y(y), X(x) + S - 1, Y(y) + S - 1],
                                fill=(255, 255, 255) if (x + y) & 1 else (40, 40, 40))
            d.text((X(x0) + 2, Y(y0) - 12), "FINISH exit %d%s" % (ex, " (secret)" if hid else ""), fill=(255, 255, 120))
        for name, r in self.branches.items():
            d.line([(X(x), Y(y)) for x, y in r], fill=(120, 240, 255), width=2)
        if self.route:
            d.line([(X(x), Y(y)) for x, y in self.route], fill=(255, 60, 60), width=2)
        for x, y, z, name, own, fr in self.clocks:
            d.ellipse([X(x) + 2, Y(y) + 2, X(x) + S - 3, Y(y) + S - 3], outline=(0, 255, 255), width=3)
        for x, y, ball, name in self.flags:
            d.polygon([(X(x) + 6, Y(y) + 1), (X(x) + 17, Y(y) + 5), (X(x) + 6, Y(y) + 10)], fill=(255, 80, 200))
            d.line([X(x) + 6, Y(y) + 1, X(x) + 6, Y(y) + 17], fill=(255, 255, 255))
        if self.start:
            d.ellipse([X(self.start[0]) + 3, Y(self.start[1]) + 3, X(self.start[0]) + S - 4, Y(self.start[1]) + S - 4],
                      fill=(255, 140, 0), outline=(255, 255, 255))
        for x, y, t, colr, _z in self.notes:
            d.text((X(x) + 4, Y(y) - 11), t, fill=(0, 0, 0))
            d.text((X(x) + 3, Y(y) - 12), t, fill=colr)
        for i in range(mx + 2, max(xs) + 1, 2):
            d.text((X(i) + 3, 2), str(i), fill=(120, 120, 140))
        for j in range(my + 2, max(ys) + 1, 2):
            d.text((2, Y(j) + 3), str(j), fill=(120, 120, 140))
        legend = ["%s, the plan: +wx right, +wy down (the screen's up is the top-left corner)" % self.title,
                  "red = the route, cyan = a branch; yellow edges = guard rails; brown or grey blocks = walls",
                  "cyan rings = clocks, pink pennants = flags, orange = the start, checker = a finish"] + self.legend
        for i, t in enumerate(legend):
            d.text((6, H - 70 + 16 * i), t, fill=(220, 220, 220))
        im.save(out)

    def _plan_glyph(self, d, kind, k, X, Y, S):
        if "at" in k:
            x, y = k["at"]
            cx, cy = X(x) + S // 2, Y(y) + S // 2
        if kind == "blower":
            x0, y0, x1, y1 = k["region"]
            colr = (255, 255, 255, 70) if k["face"] != "up" else (255, 240, 120, 80)
            d.rectangle([X(x0), Y(y0), X(x1) + S - 1, Y(y1) + S - 1], fill=colr, outline=(255, 255, 255, 200))
            d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(255, 255, 255), outline=(0, 0, 0))
            d.line([cx - 5, cy - 5, cx + 5, cy + 5], fill=(0, 0, 0), width=2)
            d.line([cx - 5, cy + 5, cx + 5, cy - 5], fill=(0, 0, 0), width=2)
            if k["face"] in DIRV:
                a, b = DIRV[k["face"]]
                for xx in range(x0, x1 + 1, 2):
                    for yy in range(y0, y1 + 1, 2):
                        px, py = X(xx) + S // 2, Y(yy) + S // 2
                        d.line([px - 6 * a, py - 6 * b, px + 6 * a, py + 6 * b], fill=(255, 255, 255), width=2)
                        d.polygon([(px + 9 * a, py + 9 * b), (px + 4 * a - 4 * b, py + 4 * b - 4 * a),
                                   (px + 4 * a + 4 * b, py + 4 * b + 4 * a)], fill=(255, 255, 255))
            else:
                d.text((X(x0) + 2, Y(y0) + 2), "UP", fill=(255, 240, 120))
        elif kind == "magnet":
            a, b = DIRV[k["face"]]
            for i in range(1, k["rng"] + 1):
                d.rectangle([X(x + a * i) + 2, Y(y + b * i) + 2, X(x + a * i) + S - 3, Y(y + b * i) + S - 3],
                            outline=(255, 80, 220), width=2)
            d.arc([cx - 6, cy - 6, cx + 6, cy + 6], 0, 360, fill=(255, 60, 200), width=4)
            d.text((cx - 3, cy - 5), "v" if k["down"] else "M", fill=(255, 255, 255))
        elif kind == "crack":
            d.line([cx - 7, cy - 6, cx, cy, cx - 3, cy + 7], fill=(60, 50, 40), width=1)
            d.line([cx, cy, cx + 7, cy - 2], fill=(60, 50, 40), width=1)
        elif kind == "pad":
            d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=BALLCOL[k["ball"]], outline=(0, 0, 0))
        elif kind == "spring":
            d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(60, 230, 120), outline=(0, 0, 0))
        elif kind == "boost":
            a, b = DIRV[k["face"]]
            for o in (-3, 3):
                d.line([cx - 5 * b - a * 2 + o * a, cy - 5 * a - b * 2 + o * b, cx + 4 * a + o * a, cy + 4 * b + o * b,
                        cx + 5 * b - a * 2 + o * a, cy + 5 * a - b * 2 + o * b], fill=(255, 0, 255), width=2)
        elif kind in ("plate", "key", "gate", "bridge"):
            colr = {"plate": (255, 255, 255), "key": (255, 230, 60), "gate": (255, 120, 60), "bridge": (200, 150, 90)}[kind]
            if kind == "gate":
                d.rectangle([cx - 9, cy - 9, cx + 9, cy + 9], fill=colr, outline=(0, 0, 0))
            elif kind == "key":
                d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=colr, outline=(0, 0, 0))
            elif kind == "plate":
                d.rectangle([cx - 7, cy - 7, cx + 7, cy + 7], fill=colr, outline=(0, 0, 0))
            if k.get("ch"):
                d.text((cx - 3, cy - 6), GLYPH[k["ch"]], fill=(0, 0, 0))
        elif kind == "spikes":
            for o in (-5, 0, 5):
                d.polygon([(cx + o - 3, cy + 5), (cx + o, cy - 6), (cx + o + 3, cy + 5)],
                          fill=(255, 255, 255) if k["pop"] else (255, 120, 120), outline=(0, 0, 0))
        elif kind == "seesaw":
            x0, y0, x1, y1 = k["box"]
            d.rectangle([X(x0) + 1, Y(y0) + 1, X(x1) - 2, Y(y1) - 2], outline=(255, 240, 80), width=3)
            d.text((X(x0) + 3, Y(y0) + 3), "T" if k["timed"] else "W", fill=(0, 0, 0))
        elif kind == "turn":
            n = k["size"]
            d.ellipse([X(x) + 2, Y(y) + 2, X(x + n) - 3, Y(y + n) - 3], outline=(0, 255, 255), width=3)
        elif kind == "lift":
            d.rectangle([X(x) + 2, Y(y) + 2, X(x) + S - 3, Y(y) + S - 3], fill=(255, 0, 255), outline=(255, 255, 255))
            d.text((cx - 3, cy - 6), "^", fill=(255, 255, 255))
        elif kind == "hump":
            n = max(k["n"], 2)
            if k["along"] == "x":
                box = [X(x) - S + 2, Y(y) - S + 2, X(x) + (n - 1) * S - 2, Y(y) + S - 2]
            elif k["along"] == "y":
                box = [X(x) - S + 2, Y(y) - S + 2, X(x) + S - 2, Y(y) + (n - 1) * S - 2]
            else:
                box = [X(x) - S + 2, Y(y) - S + 2, X(x) + S - 2, Y(y) + S - 2]
            d.ellipse(box, outline=(255, 0, 255), width=2)
        elif kind == "pit":
            r = k["r"]
            d.ellipse([X(x - r), Y(y - r), X(x + r), Y(y + r)], outline=(255, 0, 255), width=2)
            d.ellipse([X(x - r) + S, Y(y - r) + S, X(x + r) - S, Y(y + r) - S], outline=(200, 0, 200), width=1)
            if k["hole"]:
                d.rectangle([X(x - 1), Y(y - 1), X(x + 1), Y(y + 1)], fill=(0, 0, 0))
        elif kind == "chute":
            w = k["width"]
            o = 0 if w == 2 else S // 2
            d.line([(X(a) + o, Y(b) + o) for a, b, _z in k["ways"]], fill=(120, 0, 120, 200), width=w * S // 3)
        elif kind == "tube":
            d.line([(X(a) + S // 2, Y(b) + S // 2) for a, b in k["pts"]], fill=(0, 220, 220), width=5)
        elif kind == "pickup":
            d.polygon([(cx, cy - 8), (cx + 7, cy + 6), (cx - 7, cy + 6)], fill=(255, 255, 0), outline=(0, 0, 0))
        elif kind == "arch":
            d.rectangle([cx - 9, cy - 9, cx + 9, cy + 9], outline=(255, 220, 0), width=3)
        elif kind == "cup":
            d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(0, 0, 0), outline=(255, 255, 255))

    # ---- the picture in the game's projection ---------------------------------------------------------
    def iso(self, out, margin=(200, 110, 200, 150)):
        K = self.scale

        def P(wx, wy, z):                       # (the module's P, K times as big: a small course drawn larger)
            return 16 * K * (wx - wy), 8 * K * (wx + wy) - 8 * K * z
        pts = [P(x + a, y + b, cz) for (x, y), c in self.cells.items() for a, b, cz in
               ((0, 0, c[0]), (1, 0, c[1]), (1, 1, c[2]), (0, 1, c[3]))]
        pts += [P(x + a, y + b, z) for (x, y), z in self.walls.items() for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))]
        zs = [min(c) for c in self.cells.values()]
        ground = self.ground if self.ground is not None else min(zs) - 3
        ml, mt, mr, mb = margin
        minx, maxx = int(min(p[0] for p in pts)) - ml, int(max(p[0] for p in pts)) + mr
        miny, maxy = int(min(p[1] for p in pts)) - mt, int(max(p[1] for p in pts)) + mb
        W, H = maxx - minx, maxy - miny
        im = Image.new("RGB", (W, H), (10, 10, 25))
        d = ImageDraw.Draw(im, "RGBA")

        def Q(wx, wy, z):
            x, y = P(wx, wy, z)
            return x - minx, y - miny
        self._Q = Q
        rails = self.rail_edges()
        items = [((x, y), c, None) for (x, y), c in self.cells.items()]
        items += [((x, y), (z, z, z, z), "wall") for (x, y), z in self.walls.items()]
        items.sort(key=lambda it: (it[0][0] + it[0][1], it[0][0]))
        byrow = {}
        for kind, k in self.glyphs:
            if "at" in k:
                byrow.setdefault(k["at"], []).append((kind, k))
        for (x, y), c, kind in items:
            nw, ne, se, sw = c
            top = [Q(x, y, nw), Q(x + 1, y, ne), Q(x + 1, y + 1, se), Q(x, y + 1, sw)]
            if kind == "wall":
                base = self.wallcol.get((x, y), (150, 110, 90))
            else:
                base = self.tint.get((x, y)) or self.seccol.get(self.sec[(x, y)], (150, 200, 150))
            lo = ground
            if (x, y) in self.thick:
                lo = min(c) - self.thick[(x, y)]
            elif self.allfloat and kind is None:
                lo = min(c) - self.allfloat
            # the back rails (on the -x and -y edges): behind the cell's top
            for side in ("-x", "-y"):
                if ((x, y), side) in rails:
                    self._rail(d, Q, x, y, c, side)
            cutside = self.cutc.get((x, y)) if kind is None else None
            dk, md = tuple(v // 2 for v in base), tuple(v * 2 // 3 for v in base)
            if cutside:
                T_, R_, B_, L_ = (x, y, nw), (x + 1, y, ne), (x + 1, y + 1, se), (x, y + 1, sw)

                def face(a_, b_, colr):
                    d.polygon([Q(*a_), Q(*b_), Q(b_[0], b_[1], lo), Q(a_[0], a_[1], lo)], fill=colr)
                if cutside == "up":                     # kept: the down half (R, B, L)
                    face(L_, B_, dk)
                    face(R_, B_, md)
                    top = [Q(*R_), Q(*B_), Q(*L_)]
                elif cutside == "down":                 # kept: the up half, its diagonal L - R faces the camera
                    face(L_, R_, tuple(v * 7 // 12 for v in base))
                    top = [Q(*T_), Q(*R_), Q(*L_)]
                elif cutside == "left":                 # kept: the right half (T, R, B), its diagonal faces left
                    face(T_, B_, dk)
                    face(R_, B_, md)
                    top = [Q(*T_), Q(*R_), Q(*B_)]
                else:                                   # kept: the left half (T, B, L), its diagonal faces right
                    face(T_, B_, md)
                    face(L_, B_, dk)
                    top = [Q(*T_), Q(*B_), Q(*L_)]
            else:
                d.polygon([Q(x, y + 1, sw), Q(x + 1, y + 1, se), Q(x + 1, y + 1, lo), Q(x, y + 1, lo)], fill=dk)
                d.polygon([Q(x + 1, y, ne), Q(x + 1, y + 1, se), Q(x + 1, y + 1, lo), Q(x + 1, y, lo)], fill=md)
            if (self.thick.get((x, y), 0) >= 2 or (self.allfloat and kind is None and (x, y) not in self.thick)) \
                    and (x, y + 1) not in self.cells and (x + 1, y) not in self.cells:     # a floating island's icicles
                for fx in (0.25, 0.75):
                    a = Q(x + fx, y + 1, lo)
                    d.polygon([a, (a[0] + 5, a[1]), (a[0] + 2, a[1] + 9)], fill=tuple(v // 2 for v in base))
                    a = Q(x + 1, y + fx, lo)
                    d.polygon([a, (a[0] + 5, a[1]), (a[0] + 2, a[1] + 9)], fill=tuple(v * 2 // 3 for v in base))
            d.polygon(top, fill=base, outline=tuple(v * 3 // 4 for v in base))
            if kind is None and self.sec.get((x, y)) == "!":
                d.polygon(top, fill=(255, 255, 255) if (x + y) & 1 else (40, 40, 40))
            if cutside:
                continue                                # (no rail or prop on a cut cell)
            for gk, k in byrow.get((x, y), ()):
                self._iso_glyph(d, Q, gk, k)
            for side in ("+x", "+y"):
                if ((x, y), side) in rails:
                    self._rail(d, Q, x, y, c, side)
        for kind, k in self.glyphs:
            if "at" not in k:
                self._iso_glyph(d, Q, kind, k)
        for kind, k in self.glyphs:             # the air over the floors: wind and the magnets' arms
            if kind in ("blower", "magnet"):
                self._iso_air(d, Q, kind, k)
        # the routes
        for r, colr in [(b, (120, 240, 255)) for b in self.branches.values()] + [(self.route, (255, 60, 60))]:
            rz, pp = None, []
            for x, y in r:
                z = self.zat(x, y)
                if z is not None and (int(x), int(y)) in self.cells:
                    rz = z
                if rz is None:
                    rz = 0
                pp.append(Q(x, y, rz + 0.6))
            if len(pp) > 1:
                d.line(pp, fill=colr, width=2)
        for x0, y0, x1, y1, z, ex, hid in self.goals:
            cx, cy = Q((x0 + x1) / 2, (y0 + y1) / 2, z)
            self._label(d, cx - 30, cy + 12, "FINISH (exit %d%s)" % (ex, ", secret" if hid else ""), (255, 255, 120))
        heads = {}
        for x, y, z, name, own, fr in self.clocks:
            cx, cy = Q(x + 0.5, y + 0.5, z)
            heads[name] = (16 * ((x + 0.5) - (y + 0.5)), 8 * (x + y + 1) - 8 * (z + 3))
            d.rectangle([cx - 2, cy - 22, cx + 2, cy], fill=(120, 100, 80))
            d.ellipse([cx - 10, cy - 40, cx + 10, cy - 20], fill=(0, 200, 220), outline=(255, 255, 255))
            self._label(d, cx + 13, cy - 38, name + " clock", (0, 255, 255))
        for x, y, ball, name in self.flags:
            bx, by = Q(x + 0.5, y + 0.5, self.zat(x + 0.5, y + 0.5) or 0)
            d.line([bx, by, bx, by - 20], fill=(255, 255, 255))
            d.polygon([(bx, by - 20), (bx + 10, by - 16), (bx, by - 12)], fill=(255, 80, 200))
            self._label(d, bx + 12, by - 26, "%s%s" % (name, "" if ball == "rubber" else " (%s)" % ball), (255, 140, 220))
        if self.start:
            sx, sy = Q(self.start[0] + 0.5, self.start[1] + 0.5, self.zat(self.start[0] + 0.5, self.start[1] + 0.5))
            d.ellipse([sx - 8, sy - 15, sx + 8, sy + 1], fill=(255, 140, 0), outline=(255, 255, 255))
            self._label(d, sx - 16, sy + 5, "START", (255, 180, 60))
        for x, y, t, colr, z in self.notes:
            lx, ly = Q(x, y, self.znear(x, y) if z is None else z)
            self._label(d, lx, ly - 6, t, colr)
        for (x, y), name in self.windows:
            cx, cy = Q(x, y, self.zat(x, y) or 0)
            d.rectangle([cx - 160 * K, cy - 100 * K, cx + 160 * K, cy + 100 * K], outline=(0, 255, 255, 110))
            self._label(d, cx - 160 * K + 4, cy - 100 * K + 3, "one CGA window: " + name, (0, 200, 200))
        rx = [16 * (x - y) for x, y in self.route] or [0]
        allx = [p[0] for p in pts]
        d.text((8, 8), "%s (%s), in the game's projection%s: the floors %d px wide, the route's swing %d px, %d "
               "lines tall; red = the route, cyan = a branch; a cyan box = one CGA window"
               % (self.title, self.tag, " (drawn x%g)" % K if K != 1 else "", (max(allx) - min(allx)) / K,
                  (max(rx) - min(rx)), (H - mt - mb) / K), fill=(220, 220, 220))
        im.save(out)
        return heads

    @staticmethod
    def _label(d, x, y, t, colr):
        """a label on a dark plate, so it reads over anything"""
        x0, y0, x1, y1 = d.textbbox((x, y), t)
        d.rectangle([x0 - 3, y0 - 2, x1 + 3, y1 + 2], fill=(10, 10, 25, 185))
        d.text((x, y), t, fill=colr)

    def _rail(self, d, Q, x, y, c, side):
        nw, ne, se, sw = c
        seg = {"+x": ((x + 1, y, ne), (x + 1, y + 1, se)), "-x": ((x, y, nw), (x, y + 1, sw)),
               "+y": ((x, y + 1, sw), (x + 1, y + 1, se)), "-y": ((x, y, nw), (x + 1, y, ne))}[side]
        (ax, ay, az), (bx, by, bz) = seg
        d.line([Q(ax, ay, az + 1.6), Q(bx, by, bz + 1.6)], fill=(255, 225, 40), width=2)
        d.line([Q(ax, ay, az + 0.8), Q(bx, by, bz + 0.8)], fill=(200, 170, 30), width=1)
        for px, py, pz in ((ax, ay, az), (bx, by, bz)):
            d.line([Q(px, py, pz), Q(px, py, pz + 1.6)], fill=(255, 225, 40), width=1)

    def _iso_glyph(self, d, Q, kind, k):
        if "at" in k:
            x, y = k["at"]
            z = self.zat(x + 0.5, y + 0.5) or 0
            cx, cy = Q(x + 0.5, y + 0.5, z)
        if kind == "blower":
            d.ellipse([cx - 11, cy - 6, cx + 11, cy + 6], fill=(255, 255, 255), outline=(0, 0, 0))
            for a in range(4):
                t = math.pi / 4 + a * math.pi / 2
                d.line([cx, cy, cx + 9 * math.cos(t), cy + 4.5 * math.sin(t)], fill=(0, 0, 0), width=2)
            if k["flag"]:
                d.line([cx, cy, cx, cy - 26], fill=(255, 255, 255), width=1)
                d.polygon([(cx, cy - 26), (cx + 14, cy - 22), (cx, cy - 17)], fill=(255, 220, 0), outline=(0, 0, 0))
        elif kind == "magnet":
            if k["down"]:
                return                                  # (its post, arm and head are drawn in the air pass)
            d.rectangle([cx - 1, cy - 12, cx + 1, cy], fill=(255, 255, 255))
            a, b = DIRV[k["face"]]
            ox, oy = 8 * (a - b), 4 * (a + b)
            d.arc([cx - 6 + ox * 0.2, cy - 22, cx + 6 + ox * 0.2, cy - 10], 0, 360, fill=(255, 60, 200), width=3)
            d.line([cx + ox * 0.5, cy - 16 + oy * 0.5, cx + ox, cy - 16 + oy], fill=(255, 255, 255), width=2)
        elif kind == "crack":
            d.line([cx - 9, cy - 2, cx - 1, cy, cx - 4, cy + 4], fill=(70, 60, 40), width=1)
            d.line([cx - 1, cy, cx + 9, cy - 1], fill=(70, 60, 40), width=1)
        elif kind == "pad":
            d.ellipse([cx - 10, cy - 5, cx + 10, cy + 5], fill=BALLCOL[k["ball"]], outline=(0, 0, 0))
            d.text((cx - 3, cy - 6), k["ball"][0].upper(), fill=(0, 0, 0))
        elif kind == "spring":
            d.ellipse([cx - 9, cy - 5, cx + 9, cy + 4], fill=(60, 230, 120), outline=(0, 0, 0))
            d.ellipse([cx - 6, cy - 8, cx + 6, cy - 1], fill=(120, 255, 170), outline=(0, 0, 0))
        elif kind == "boost":
            a, b = DIRV[k["face"]]
            ux, uy = 8 * (a - b), 4 * (a + b)
            vx, vy = 8 * (-b - a), 4 * (-b + a)
            for o in (-0.25, 0.25):
                d.line([cx - vx * 0.5 + ux * (o - 0.2), cy - vy * 0.5 + uy * (o - 0.2), cx + ux * (o + 0.2),
                        cy + uy * (o + 0.2), cx + vx * 0.5 + ux * (o - 0.2), cy + vy * 0.5 + uy * (o - 0.2)],
                       fill=(255, 0, 255), width=2)
        elif kind == "plate":
            d.polygon([(cx, cy - 6), (cx + 12, cy), (cx, cy + 6), (cx - 12, cy)], fill=(255, 255, 255), outline=(0, 0, 0))
            d.text((cx - 3, cy - 6), GLYPH[k["ch"]], fill=(0, 0, 0))
        elif kind == "key":
            d.ellipse([cx - 6, cy - 24, cx + 6, cy - 12], fill=(255, 230, 60), outline=(0, 0, 0))
            d.line([cx, cy - 12, cx, cy - 3], fill=(255, 230, 60), width=3)
            d.line([cx, cy - 6, cx + 4, cy - 6], fill=(255, 230, 60), width=2)
            d.text((cx - 3, cy - 24), GLYPH[k["ch"]], fill=(0, 0, 0))
            d.text((cx + 9, cy - 26), "KEY", fill=(255, 230, 60))
        elif kind == "gate":
            a, b = (0, 1) if k["along"] == "x" else (1, 0)         # the bars stand ACROSS the path
            p0, p1 = Q(x + 0.5 - a * 0.5, y + 0.5 - b * 0.5, z), Q(x + 0.5 + a * 0.5, y + 0.5 + b * 0.5, z)
            hh = 22 if k.get("art") else 14
            d.polygon([p0, p1, (p1[0], p1[1] - hh), (p0[0], p0[1] - hh)], fill=(255, 120, 60, 170), outline=(0, 0, 0))
            for t in (0.2, 0.4, 0.6, 0.8):
                gx, gy = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
                d.line([gx, gy, gx, gy - hh], fill=(0, 0, 0), width=1)
            mx_, my_ = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - hh / 2
            d.rectangle([mx_ - 5, my_ - 6, mx_ + 5, my_ + 6], fill=(255, 255, 255), outline=(0, 0, 0))
            d.text((mx_ - 3, my_ - 6), GLYPH[k["ch"]], fill=(0, 0, 0))
        elif kind == "bridge":
            if k.get("ch"):
                d.text((cx - 3, cy - 6), GLYPH[k["ch"]], fill=(0, 0, 0))
            else:
                d.line([cx - 8, cy, cx + 8, cy], fill=(90, 60, 30), width=1)
        elif kind == "spikes":
            for o in (-8, 0, 8):
                d.polygon([(cx + o - 3, cy + 2), (cx + o, cy - 9), (cx + o + 3, cy + 2)],
                          fill=(255, 255, 255) if k["pop"] else (255, 130, 130), outline=(0, 0, 0))
        elif kind == "seesaw":
            x0, y0, x1, y1 = k["box"]
            px, py = Q((x0 + x1) / 2, (y0 + y1) / 2, k["pivot"] - 0.5)
            d.polygon([(px - 7, py + 12), (px + 7, py + 12), (px, py)], fill=(255, 255, 255), outline=(0, 0, 0))
            if k["timed"]:
                d.line([px - 4, py + 6, px + 4, py + 6], fill=(0, 0, 0), width=2)
                d.line([px - 6, py + 10, px + 6, py + 10], fill=(0, 0, 0), width=2)
        elif kind == "turn":
            n = k["size"]
            c0 = Q(x + n / 2, y + n / 2, self.zat(x + 0.5, y + 0.5) or 0)
            rr = 16 * n * 0.62 * self.scale
            d.ellipse([c0[0] - rr, c0[1] - rr / 2, c0[0] + rr, c0[1] + rr / 2], fill=(150, 235, 245), outline=(0, 90, 110), width=2)
            for a in range(8):                      # a cog's teeth
                t = a * math.pi / 4
                d.line([c0[0] + rr * 0.55 * math.cos(t), c0[1] + rr * 0.275 * math.sin(t),
                        c0[0] + rr * math.cos(t), c0[1] + rr * 0.5 * math.sin(t)], fill=(0, 90, 110), width=2)
            d.ellipse([c0[0] - 4, c0[1] - 2, c0[0] + 4, c0[1] + 2], fill=(0, 90, 110))
        elif kind == "lift":
            lo, hi = Q(x + 0.5, y + 0.5, k["z"]), Q(x + 0.5, y + 0.5, k["z"] + k["rise"])
            d.line([lo, hi], fill=(255, 0, 255), width=2)
            for q in (lo, hi):
                d.polygon([(q[0], q[1] - 7), (q[0] + 14, q[1]), (q[0], q[1] + 7), (q[0] - 14, q[1])],
                          outline=(255, 0, 255), fill=(255, 0, 255, 90))
            d.polygon([(hi[0], hi[1] - 14), (hi[0] + 5, hi[1] - 7), (hi[0] - 5, hi[1] - 7)], fill=(255, 0, 255))
        elif kind == "hump":
            n = max(k["n"], 2)
            hz = k["h"] / 8.0
            if k["along"] == "x":
                a, b = (x - 1, y - 1), (x + n - 1, y + 1)
            elif k["along"] == "y":
                a, b = (x - 1, y - 1), (x + 1, y + n - 1)
            else:
                a, b = (x - 1, y - 1), (x + 1, y + 1)
            cc = Q((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, k["z"])
            rw = 8 * ((b[0] - a[0]) + (b[1] - a[1]))
            for i, f in enumerate((1.0, 0.66, 0.33)):
                d.ellipse([cc[0] - rw * f, cc[1] - rw * f / 2 - hz * 8 * (1 - f) * 1.2, cc[0] + rw * f,
                           cc[1] + rw * f / 2 - hz * 8 * (1 - f) * 1.2],
                          fill=((230, 120, 230), (240, 160, 240), (250, 205, 250))[i], outline=(140, 40, 140))
        elif kind == "pit":
            r = k["r"]
            cc = Q(x, y, k["z"])
            for i, f in enumerate((1.0, 0.72, 0.45)):
                d.ellipse([cc[0] - 16 * r * f, cc[1] - 8 * r * f + i * 4, cc[0] + 16 * r * f, cc[1] + 8 * r * f + i * 4],
                          fill=((205, 110, 205), (160, 70, 160), (110, 40, 110))[i], outline=(80, 20, 80))
            if k["hole"]:
                d.ellipse([cc[0] - 12, cc[1] - 6 + 9, cc[0] + 12, cc[1] + 6 + 9], fill=(0, 0, 0))
        elif kind == "chute":
            w = k["width"]
            o = 0 if w == 2 else 0.5
            pp = [Q(a + o, b + o, zz) for a, b, zz in k["ways"]]
            d.line(pp, fill=(120, 30, 120), width=int(6 * w), joint="curve")
            d.line(pp, fill=(245, 190, 245), width=int(2 * w), joint="curve")
        elif kind == "tube":
            pp = [Q(a + 0.5, b + 0.5, (self.top(a, b) or 0)) for a, b in k["pts"]]
            d.line(pp, fill=(0, 0, 0), width=7)
            d.line(pp, fill=(0, 220, 220), width=4)
            for q in (pp[0], pp[-1]):
                d.ellipse([q[0] - 8, q[1] - 4, q[0] + 8, q[1] + 4], fill=(0, 0, 0), outline=(255, 255, 255))
        elif kind == "pickup":
            d.polygon([(cx, cy - 20), (cx + 6, cy - 9), (cx - 6, cy - 9)], fill=(255, 255, 0), outline=(0, 0, 0))
            d.text((cx + 8, cy - 22), k["kind"], fill=(255, 255, 0))
        elif kind == "arch":
            a, b = (0, 1) if k["along"] == "x" else (1, 0)
            p0, p1 = Q(x + 0.5 - a * 0.6, y + 0.5 - b * 0.6, z), Q(x + 0.5 + a * 0.6, y + 0.5 + b * 0.6, z)
            d.line([p0, (p0[0], p0[1] - 20)], fill=(255, 220, 0), width=3)
            d.line([p1, (p1[0], p1[1] - 20)], fill=(255, 220, 0), width=3)
            d.line([(p0[0], p0[1] - 20), (p1[0], p1[1] - 20)], fill=(255, 220, 0), width=4)
        elif kind == "cup":
            d.ellipse([cx - 6, cy - 3, cx + 6, cy + 3], fill=(0, 0, 0))
            d.line([cx, cy, cx, cy - 24], fill=(255, 255, 255))
            d.polygon([(cx, cy - 24), (cx + 10, cy - 20), (cx, cy - 16)], fill=(255, 60, 60))

    def _iso_air(self, d, Q, kind, k):
        x, y = k["at"]
        if kind == "blower":
            x0, y0, x1, y1 = k["region"]
            fz = self.zat(x + 0.5, y + 0.5) or 0
            for xx in range(x0, x1 + 1):
                for yy in range(y0, y1 + 1):
                    z = self.zat(xx + 0.5, yy + 0.5)
                    if k["face"] == "up":
                        base = fz if z is None or (xx, yy) not in self.cells else z
                        if (xx + yy) & 1:
                            continue
                        topz = fz + (k["top"] or 4)
                        for t in range(3):
                            za = base + 1 + (topz - base - 1) * t / 3.0
                            p0 = Q(xx + 0.5, yy + 0.5, za)
                            p1 = Q(xx + 0.5, yy + 0.5, za + (topz - base) / 4.5)
                            d.line([p0, p1], fill=(255, 245, 150, 220), width=1)
                            d.polygon([(p1[0], p1[1] - 4), (p1[0] - 3, p1[1] + 1), (p1[0] + 3, p1[1] + 1)],
                                      fill=(255, 245, 150, 220))
                    else:
                        if (xx + yy) & 1:
                            continue
                        if z is None:
                            z = fz
                        a, b = DIRV[k["face"]]
                        p0 = Q(xx + 0.5 - a * 0.35, yy + 0.5 - b * 0.35, z + 1.4)
                        p1 = Q(xx + 0.5 + a * 0.35, yy + 0.5 + b * 0.35, z + 1.4)
                        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - 3)
                        d.line([p0, mid, p1], fill=(255, 255, 255, 230), width=1)
                        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
                        d.polygon([p1, (p1[0] - 5 * math.cos(ang - 0.5), p1[1] - 5 * math.sin(ang - 0.5)),
                                   (p1[0] - 5 * math.cos(ang + 0.5), p1[1] - 5 * math.sin(ang + 0.5))],
                                  fill=(255, 255, 255, 230))
        elif kind == "magnet" and k["down"]:
            z = self.zat(x + 0.5, y + 0.5) or 0
            a, b = DIRV[k["face"]]
            foot, head = Q(x + 0.5, y + 0.5, z), Q(x + 0.5, y + 0.5, z + 4)
            tip = Q(x + 0.5 + a, y + 0.5 + b, z + 4)
            d.line([foot, head], fill=(255, 255, 255), width=2)
            d.line([head, tip], fill=(255, 255, 255), width=2)
            d.arc([tip[0] - 6, tip[1], tip[0] + 6, tip[1] + 12], 180, 360, fill=(255, 60, 200), width=3)
            d.line([tip[0] - 5, tip[1] + 6, tip[0] - 5, tip[1] + 11], fill=(255, 255, 255), width=2)
            d.line([tip[0] + 5, tip[1] + 6, tip[0] + 5, tip[1] + 11], fill=(255, 255, 255), width=2)

    # ---- the engine course --------------------------------------------------------------------------------
    def bbc(self, out, force=False):
        if os.path.exists(out) and not force:
            sys.exit("sketch.py: %s exists; --force to re-emit it" % out)
        L = self.head.strip("\n").split("\n") + [""]
        L.append("# rooms (the sketch's sections), walls and guard rails")
        L += self.rooms
        L += self.floats
        L.append("")
        L += self.lines
        L.append("")
        for x0, y0, x1, y1, z, ex, hid in self.goals:
            L.append("goal  rect %d %d %d %d  flat %g%s%s" % (x0, y0, x1, y1, z, " exit %d" % ex if ex else "",
                                                             " hidden" if hid else ""))
        L.append("start %d %d" % self.start)
        for x, y, ball, name in self.flags:
            L.append("checkpoint %d %d ball %s   # %s" % (x, y, ball, name))
        L.append("")
        L.append("# clocks: on a corner of a floor off the way, or on a tile one out from it")
        for x, y, z, name, own, fr in self.clocks:
            if own:
                L.append("floor tile %d %d  flat %g   # the %s clock's tile" % (x, y, z, name))
            L.append("clock %d %d%s   # %s" % (x, y, " frame %s" % fr if fr else "", name))
        L.append("")
        L.append("# the autopilot's route")
        seen = None
        for x, y in self.route:
            c = (int(x), int(y))
            if c in self.cells and c != seen and self.sec.get(c) != "W":
                L.append("way %d %d" % c)
                seen = c
        for name, r in self.branches.items():
            L.append("# the %s way: a branch (the tool's alone)" % name)
            seen = None
            for x, y in r:
                c = (int(x), int(y))
                if c in self.cells and c != seen and self.sec.get(c) != "W":
                    L.append("way %d %d branch %s" % (c + (name,)))
                    seen = c
        open(out, "w").write("\n".join(L) + "\n")

    def report(self, heads):
        print("%s: the route %.1f tiles%s" % (self.tag, self.route_len(self.route), "".join(
            "; branch %s %.1f tiles" % (n, self.route_len(r)) for n, r in self.branches.items())))
        names = list(heads)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                (ax, ay), (bx, by) = heads[a], heads[b]
                print("clocks %-10s - %-10s dx %5d dy %5d%s" % (a, b, bx - ax, by - ay,
                      "   ONE WINDOW?" if abs(bx - ax) < 300 and abs(by - ay) < 185 else ""))

    def main(self, here, bbcname):
        if sys.argv[1:2] == ["--bbc"]:
            self.bbc(sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else bbcname,
                     force="--force" in sys.argv)
            return
        o = sys.argv[1] if len(sys.argv) > 1 else here
        heads = self.iso(os.path.join(o, "iso.png"))
        self.plan(os.path.join(o, "plan.png"))
        self.report(heads)
