#!/usr/bin/env python3
"""Generate apps/catdemo/cats.inc - the four cat line drawings for CATDEMO.

Not run by the build: cats.inc is committed. Re-run by hand after editing:
    python3 apps/catdemo/mkcats.py > apps/catdemo/cats.inc

Drawing space is 200 x 125 pixels. Record format, one byte stream per cat:
    0FFh, colour      set the ink (SPEC.md colour index)
    n, x0,y0 .. xn-1,yn-1   a polyline of n points (n = 1..254)
    0                 end
"""
import math

W, H = 200, 125
BLACK, BROWN, GREEN, MAGENTA, CYAN, YELLOW, LRED = 0, 6, 2, 13, 3, 14, 12


class Pic:
    def __init__(self, name):
        self.name, self.recs = name, []
        self.off = (0, 0)

    def ink(self, c):
        self.recs.append(("c", c))

    def line(self, pts):
        ox, oy = self.off
        pts = [(min(W - 1, max(0, round(x + ox))), min(H - 1, max(0, round(y + oy))))
               for x, y in pts]
        while len(pts) > 254:
            self.recs.append(("p", pts[:254]))
            pts = pts[253:]
        self.recs.append(("p", pts))

    def clipline(self, pts, ymax):
        """Draw only the runs of a polyline whose points are above ymax."""
        run = []
        for x, y in pts + [(0, ymax + 1)]:
            if y <= ymax:
                run.append((x, y))
            else:
                if len(run) > 1:
                    self.line(run)
                run = []

    def ellipse(self, cx, cy, rx, ry, a0=0, a1=360, n=None):
        if n is None:
            n = max(8, int((rx + ry) * abs(a1 - a0) / 360 * 1.2))
        self.line([(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                    cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
                   for i in range(n + 1)])

    def bez(self, *p, n=16):
        out = []
        for i in range(n + 1):
            t = i / n
            pts = list(p)
            while len(pts) > 1:
                pts = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1])
                       for a, b in zip(pts, pts[1:])]
            out.append(pts[0])
        self.line(out)

    def patch(self, cx, cy, rx, ry, step):
        """A fur patch: an outlined ellipse filled with horizontal strokes."""
        y = cy - ry + 1
        while y < cy + ry:
            dx = rx * math.sqrt(max(0.0, 1 - ((y - cy) / ry) ** 2))
            if dx >= 1:
                self.line([(cx - dx, y), (cx + dx, y)])
            y += step
        self.ellipse(cx, cy, rx, ry)

    def emit(self):
        out = [f"{self.name}:"]
        for kind, v in self.recs:
            if kind == "c":
                out.append(f"    db 0FFh, {v}")
            else:
                flat = ", ".join(f"{x},{y}" for x, y in v)
                out.append(f"    db {len(v)}, {flat}")
        out.append("    db 0")
        return "\n".join(out)


def face(p, cx, cy, eye=BLACK, nose=MAGENTA):
    """Front-facing cat head features around (cx, cy)."""
    p.ink(eye)
    for ex in (cx - 10, cx + 10):
        p.ellipse(ex, cy - 2, 4, 5)
        p.line([(ex, cy - 5), (ex, cy + 1)])          # slit pupil
    p.ink(nose)
    p.line([(cx - 3, cy + 7), (cx + 3, cy + 7), (cx, cy + 10), (cx - 3, cy + 7)])
    p.ink(BLACK)
    p.line([(cx, cy + 10), (cx, cy + 13)])
    p.bez((cx, cy + 13), (cx - 2, cy + 16), (cx - 6, cy + 15), n=4)
    p.bez((cx, cy + 13), (cx + 2, cy + 16), (cx + 6, cy + 15), n=4)
    for s in (-1, 1):                                   # whiskers
        for dy, ey in ((-1, -6), (1, 0), (3, 6)):
            p.line([(cx + s * 12, cy + 9 + dy), (cx + s * 38, cy + 9 + ey)])


def sitting(p, cx=100, calico=False):
    if calico:                      # patches first, so the outline is on top
        p.ink(BROWN)
        p.patch(cx - 13, cy_head - 9, 11, 9, 2)
        p.patch(cx - 12, 84, 15, 13, 2)
        p.patch(cx + 20, 110, 9, 7, 2)
        p.ink(BLACK)
        p.patch(cx + 14, cy_head - 10, 9, 7, 1)
        p.patch(cx + 16, 86, 10, 9, 1)
        p.patch(cx - 22, 108, 6, 6, 1)
    p.ink(BLACK)
    p.ellipse(cx, cy_head, 27, 22)                                   # head
    p.line([(cx - 22, cy_head - 12), (cx - 20, 6), (cx - 6, cy_head - 21)])
    p.line([(cx + 6, cy_head - 21), (cx + 20, 6), (cx + 22, cy_head - 12)])
    p.ink(MAGENTA)
    p.line([(cx - 18, cy_head - 14), (cx - 17, 12), (cx - 10, cy_head - 19)])
    p.line([(cx + 10, cy_head - 19), (cx + 17, 12), (cx + 18, cy_head - 14)])
    face(p, cx, cy_head, eye=GREEN if calico else BLACK)
    p.ellipse(cx, 92, 34, 32, -58, 238)                              # body
    for lx in (cx - 12, cx + 12):                                    # legs
        p.line([(lx - 5, 92), (lx - 5, 120)])
        p.line([(lx + 5, 92), (lx + 5, 120)])
        p.ellipse(lx, 120, 6, 3, 180, 360, n=8)
    if calico:
        p.ink(BROWN)
    p.bez((cx + 32, 110), (cx + 62, 120), (cx + 70, 80), (cx + 55, 62), n=20)
    p.bez((cx + 30, 104), (cx + 56, 112), (cx + 62, 82), (cx + 50, 66), n=20)
    p.line([(cx + 55, 62), (cx + 50, 66)])
    p.ink(BLACK)


cy_head = 40


def sleeping(p):
    p.ink(BLACK)
    p.ellipse(110, 82, 60, 32, 200, 520)                     # curled body
    p.ellipse(70, 86, 23, 18)                                 # head
    p.line([(52, 76), (50, 58), (62, 69)])                    # ears
    p.line([(74, 68), (86, 56), (88, 76)])
    p.ink(MAGENTA)
    p.line([(54, 73), (53, 63), (60, 70)])
    p.line([(77, 69), (84, 62), (85, 73)])
    p.ink(BLACK)
    p.ellipse(61, 86, 5, 3, 0, 180, n=6)                      # closed eyes
    p.ellipse(79, 86, 5, 3, 0, 180, n=6)
    p.ink(MAGENTA)
    p.line([(68, 93), (72, 93), (70, 95), (68, 93)])
    p.ink(BLACK)
    p.ellipse(52, 103, 9, 5)                                  # paw
    p.bez((165, 92), (175, 125), (110, 122), (60, 116), n=24)  # tail
    p.bez((167, 84), (186, 122), (110, 129), (62, 122), n=24)
    p.line([(60, 116), (55, 119), (62, 122)])
    p.ink(CYAN)                                               # Zzz
    for x, y, s in ((120, 30, 10), (138, 16, 8), (152, 6, 6)):
        p.line([(x, y), (x + s, y), (x, y + s), (x + s, y + s)])


def walking(p):
    p.ink(BLACK)
    p.ellipse(92, 66, 46, 20)                                       # body
    p.off = (-7, 7)                                                 # the head
    p.ellipse(148, 44, 19, 16)                                      # head
    p.line([(136, 33), (137, 16), (148, 29)])                       # ears
    p.line([(153, 29), (163, 15), (164, 35)])
    p.ink(MAGENTA)
    p.line([(139, 31), (140, 21), (146, 29)])
    p.line([(155, 29), (161, 20), (161, 33)])
    p.ink(GREEN)
    p.ellipse(156, 41, 4, 4)
    p.ink(BLACK)
    p.line([(156, 38), (156, 44)])
    p.ink(MAGENTA)
    p.line([(164, 49), (168, 49), (166, 52), (164, 49)])
    p.ink(BLACK)
    p.bez((166, 52), (164, 56), (160, 55), n=4)
    for ey in (-4, 0, 4):
        p.line([(160, 52), (190, 50 + ey * 2)])
    p.off = (0, 0)
    for x0, x1 in ((124, 132), (110, 112), (70, 66), (54, 48)):     # legs
        p.line([(x0 - 4, 80), (x1 - 4, 117), (x1 + 4, 117), (x0 + 4, 80)])
    p.bez((47, 60), (25, 52), (15, 25), (35, 12), n=20)             # tail
    p.bez((48, 66), (18, 58), (8, 22), (35, 12), n=20)
    p.ink(BROWN)
    p.line([(4, 119), (195, 119)])                                  # ground


def rect(p, x0, y0, x1, y1):
    p.line([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def glyph(p, ch, x, y):
    """A stroke letter in an 8 x 14 cell at (x, y)."""
    if ch == "o":
        p.ellipse(x + 4, y + 10, 4, 4, n=12)
    elif ch == "s":
        p.line([(x + 8, y + 6), (x + 1, y + 6), (x, y + 7), (x, y + 9),
                (x + 1, y + 10), (x + 7, y + 10), (x + 8, y + 11),
                (x + 8, y + 13), (x + 7, y + 14), (x, y + 14)])
    elif ch == "8":
        p.ellipse(x + 4, y + 3.5, 3.5, 3.5, n=12)
        p.ellipse(x + 4, y + 10.5, 4, 3.5, n=12)
    elif ch == "0":
        p.ellipse(x + 4, y + 7, 4, 7, n=16)
        p.line([(x + 1, y + 11), (x + 7, y + 3)])


def mascot(p):
    """The os8088 mascot: a cat peering over an IBM PC with the name lit."""
    p.ink(BLACK)
    rect(p, 30, 96, 170, 122)                                # system unit
    for y in (101, 111):                                     # two floppies
        rect(p, 112, y, 162, y + 7)
        p.line([(118, y + 3), (156, y + 3)])
        p.line([(136, y + 1), (140, y + 1)])
    p.line([(30, 105), (38, 105)])
    p.ink(LRED)
    p.ellipse(42, 116, 2, 2, n=6)                            # power lamp
    p.ink(BLACK)
    p.line([(80, 96), (76, 92), (124, 92), (120, 96)])      # monitor stand
    rect(p, 55, 46, 145, 92)                                 # monitor
    rect(p, 62, 53, 138, 86)                                 # the glass
    p.ink(GREEN)
    for i, ch in enumerate("os8088"):                        # the name, lit
        glyph(p, ch, 67 + i * 11, 61)
    p.line([(67, 79), (75, 79)])                             # a cursor
    p.ink(BLACK)
    head = [(100 + 23 * math.cos(math.radians(a)),
             29 + 19 * math.sin(math.radians(a))) for a in range(0, 361, 8)]
    p.clipline(head, 46)                                     # head, behind
    p.line([(80, 20), (80, 2), (93, 12)])                    # ears
    p.line([(107, 12), (120, 2), (120, 20)])
    p.ink(MAGENTA)
    p.line([(83, 17), (83, 8), (90, 13)])
    p.line([(110, 13), (117, 8), (117, 17)])
    p.ink(GREEN)
    for ex in (91, 109):
        p.ellipse(ex, 27, 4, 5)
    p.ink(BLACK)
    for ex in (91, 109):
        p.line([(ex, 24), (ex, 30)])
    p.ink(MAGENTA)
    p.line([(97, 35), (103, 35), (100, 38), (97, 35)])
    p.ink(BLACK)
    p.line([(100, 38), (100, 40)])
    p.bez((100, 40), (98, 43), (94, 42), n=4)
    p.bez((100, 40), (102, 43), (106, 42), n=4)
    for s in (-1, 1):                                        # whiskers
        for dy, ey in ((-1, -5), (1, 0), (3, 5)):
            p.line([(100 + s * 12, 37 + dy), (100 + s * 36, 37 + ey)])
    for px in (80, 120):                                     # paws over
        p.ellipse(px, 47, 7, 4, 180, 360, n=8)               # the bezel
        p.line([(px - 7, 47), (px - 7, 50), (px + 7, 50), (px + 7, 47)])
        p.line([(px - 2, 48), (px - 2, 50)])
        p.line([(px + 2, 48), (px + 2, 50)])
    p.bez((145, 50), (162, 52), (150, 72), (164, 94), n=18)  # tail, down
    p.bez((145, 55), (156, 58), (144, 74), (158, 96), n=18)  # the side
    p.line([(164, 94), (158, 96)])


cats = []
for name, fn in (("ct_pic0", lambda p: sitting(p)),
                 ("ct_pic1", sleeping),
                 ("ct_pic2", lambda p: sitting(p, calico=True)),
                 ("ct_pic3", walking),
                 ("ct_pic4", mascot)):
    p = Pic(name)
    fn(p)
    cats.append(p.emit())

print("; GENERATED by apps/catdemo/mkcats.py - edit that, not this.")
print("\n\n".join(cats))
