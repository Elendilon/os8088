#!/usr/bin/env python3
"""BONANZA's pathway icons and glowing pads, generated (SPEC.md 128.22.8).

    python3 tools/bbicons.py              # write apps/bonanza/courses/icons/*.bba and courses/pads/*.bba
    python3 tools/bbicons.py --check      # the committed files equal what the generator writes
                                          # (tools/bonanza_assets.py --selfcheck runs it too)
    python3 tools/bbicons.py --png DIR    # previews: CGA palette 1 and the Hercules mono, 4x, frames side by side

One `.bba` text pixmap (128.23.2's format: one line a pixel row, `.` transparent,
`0 1 2 3` the CGA's four colours, `#` comments) a course, FRAMES stacked top to
bottom with a `# frames K` line (128.22.2): frame 0 the rest pose, the others
a loop.  PLACEHOLDERS for the owner's art: procedural, deterministic (no
randomness, no clock, sorted iteration), standard library only (Pillow is for
--png and nothing else).

SIZE: an icon is W x H = 48 x 32 world pixels (6 words x 4 block rows).  The
engine's units are a WORD = 8 world px (2 bytes of 2bpp) and a BLOCK = 8 x 8
px; a LANE is at most `LANE_WMAX` x `LANE_HMAX` = 4 words x 3 block rows = 32
x 24 px (bbcourse.py), and the course tool cuts an icon into as many lanes as
it needs (128.22.2).  What bounds an icon is that every one of those lanes is
counted FAST while its pad is the marble's, against 128.19.10's per-window
bounds (`WIN_LANES` = 6 FAST lanes, `WIN_CHG` = 6 pose changes a step) - not a
fixed rectangle.  48 x 32 is 4 lanes (e.g. 4 + 2 words across, 3 + 1 block
rows down), which leaves two of each bound for the rest of the page; 384
bytes a frame as lane data.

Luminance: every icon is drawn so that colour 3 (white / brown) carries the
shape against black, and colours 1 and 2 (which the Hercules shows as the same
checker grey) shade it, so it reads on the mono card as well.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bonanza_assets as BA                                   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_DIR = os.path.join(ROOT, "apps", "bonanza", "courses", "icons")
PAD_DIR = os.path.join(ROOT, "apps", "bonanza", "courses", "pads")
W, H = 48, 32


class Canvas:
    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.p = [[None] * w for _ in range(h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[y][x] = c

    def disc(self, cx, cy, r, c, fn=None):
        for y in range(int(cy - r - 1), int(cy + r + 2)):
            for x in range(int(cx - r - 1), int(cx + r + 2)):
                if (x + .5 - cx) ** 2 + (y + .5 - cy) ** 2 <= r * r:
                    self.put(x, y, c if fn is None else fn(x, y))

    def ring(self, cx, cy, r0, r1, c):
        for y in range(int(cy - r1 - 1), int(cy + r1 + 2)):
            for x in range(int(cx - r1 - 1), int(cx + r1 + 2)):
                d2 = (x + .5 - cx) ** 2 + (y + .5 - cy) ** 2
                if r0 * r0 <= d2 <= r1 * r1:
                    self.put(x, y, c)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.put(x, y, c)

    def line(self, x0, y0, x1, y1, c, w=1.0):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy or 1.0
        for y in range(int(min(y0, y1) - w - 1), int(max(y0, y1) + w + 2)):
            for x in range(int(min(x0, x1) - w - 1), int(max(x0, x1) + w + 2)):
                t = max(0.0, min(1.0, ((x + .5 - x0) * dx + (y + .5 - y0) * dy) / L2))
                if math.hypot(x0 + t * dx - x - .5, y0 + t * dy - y - .5) <= w / 2.0:
                    self.put(x, y, c)

    def poly(self, pts, c, fn=None):
        ys = [q[1] for q in pts]
        for y in range(int(min(ys)) - 1, int(max(ys)) + 2):
            yy = y + .5
            xs = []
            for i in range(len(pts)):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
                if (ay <= yy < by) or (by <= yy < ay):
                    xs.append(ax + (yy - ay) * (bx - ax) / float(by - ay))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                for x in range(int(math.floor(xs[i] + .5)), int(math.floor(xs[i + 1] + .5))):
                    self.put(x, y, c if fn is None else fn(x, y))

    def rows(self):
        return self.p


def _ball(cv, cx, cy, r, rot):
    """the game's ball, small: a white sphere, mid shade lower right, three
    magenta spots rolling round a horizontal axis by rot radians"""
    def ink(x, y):
        u, v = (x + .5 - cx) / r, (y + .5 - cy) / r
        return 1 if (u * .55 + v * .75) > .62 else 3
    cv.disc(cx, cy, r, 3, ink)
    for k in range(3):
        a = rot + k * 2 * math.pi / 3
        sx = math.sin(a)
        if math.cos(a) <= 0.1:
            continue
        px, py = cx + r * .78 * sx, cy + r * .25 * math.sin(a * 0.5 + k)
        sr = max(1.0, r * .26 * math.cos(a))
        cv.disc(px, py, sr, 2)
    cv.ring(cx, cy, r - 1.0, r, 1)


def _first(t, n):
    cv = Canvas()
    for x in range(0, W):                                     # the ground, a dash train that loops every frame period
        ph = (x + 8 * t) % 8
        cv.put(x, 28, 1)
        if ph < 5:
            cv.put(x, 29, 2)
    _ball(cv, 24, 15, 12, t * 2 * math.pi / n)
    return cv


def _trial(t, n):
    cv = Canvas()
    cx, cy = 24, 18
    cv.rect(21, 1, 27, 4, 3)                                  # the crown
    cv.rect(23, 4, 25, 6, 3)
    cv.line(36, 8, 40, 4, 3, 2.6)                             # the side button
    cv.disc(cx, cy, 13.5, 3)
    cv.disc(cx, cy, 11.0, 0)
    a0 = -math.pi / 2
    sweep = 60.0 * t * math.pi / 180.0                        # the swept wedge trails the hand
    for y in range(H):
        for x in range(W):
            ux, uy = x + .5 - cx, y + .5 - cy
            r = math.hypot(ux, uy)
            if 2 < r < 10.5 and t:
                ang = (math.atan2(uy, ux) - a0) % (2 * math.pi)
                if ang <= sweep:
                    cv.put(x, y, 1)
    for k in range(12):                                       # the ticks
        a = a0 + k * math.pi / 6
        r0 = 8.0 if k % 3 == 0 else 9.4
        cv.line(cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + 10.6 * math.cos(a), cy + 10.6 * math.sin(a),
                3, 1.2 if k % 3 == 0 else 1.0)
    a = a0 + sweep
    cv.line(cx, cy, cx + 9 * math.cos(a), cy + 9 * math.sin(a), 3, 1.6)
    cv.disc(cx, cy, 2.2, 3)
    cv.disc(cx, cy, 0.9, 0)
    return cv


def _mill(t, n):
    cv = Canvas()
    cv.poly([(20, 14), (28, 14), (32, 31), (16, 31)], 2)      # the tower
    cv.line(20, 14, 16, 31, 3, 1.4)
    cv.line(28, 14, 32, 31, 3, 1.4)
    cv.rect(16, 30, 33, 32, 3)
    cv.rect(22, 24, 26, 31, 0)                                # the door
    cv.poly([(18, 14), (30, 14), (24, 8)], 3)                 # the cap
    hx, hy = 24, 11
    a0 = t * (math.pi / 2) / n                                # four blades: a quarter turn over the loop
    for k in range(4):
        a = a0 + k * math.pi / 2 - math.pi / 4
        c, s = math.cos(a), math.sin(a)

        def q(r, o):
            return (hx + r * c - o * s, hy + r * s + o * c)
        cv.poly([q(4, 0.0), q(15, 0.0), q(15, 3.6), q(4, 3.6)], 1)     # the sail
        cv.line(*q(2, 0), *q(15.5, 0), 3, 1.6)                          # the stock, white against the sail
        cv.line(*q(15, 0), *q(15, 3.8), 3, 1.0)
    cv.disc(hx, hy, 2.4, 3)
    cv.disc(hx, hy, 0.9, 0)
    return cv


def _moon(t, n):
    cv = Canvas()
    cx, cy, R = 20, 17, 13.0
    for y in range(H):
        for x in range(W):
            if (x + .5 - cx) ** 2 + (y + .5 - cy) ** 2 <= R * R and \
                    (x + .5 - (cx + 7.5)) ** 2 + (y + .5 - (cy - 4)) ** 2 > 10.6 ** 2:
                u, v = (x + .5 - cx) / R, (y + .5 - cy) / R
                cv.put(x, y, 3 if u * .5 + v * .55 < .42 else 1)
    stars = ((34, 5, 3), (41, 14, 2), (36, 24, 3), (29, 13, 1), (44, 28, 1), (9, 4, 1))
    for i, (sx, sy, sz) in enumerate(stars):
        ph = (t + i * 2) % n                                  # twinkle: phase 0 is the lit rest pose in frame 0
        lit = 0 if i == 0 else ph
        size = sz if (lit % n) < n - 2 else sz - 1
        if t == 0:
            size = sz
        if size >= 3:
            cv.line(sx - 3, sy, sx + 3, sy, 3, 1.0)
            cv.line(sx, sy - 3, sx, sy + 3, 3, 1.0)
            cv.disc(sx, sy, 1.2, 3)
        elif size == 2:
            cv.put(sx, sy, 3), cv.put(sx - 1, sy, 1), cv.put(sx + 1, sy, 1), cv.put(sx, sy - 1, 1), cv.put(sx, sy + 1, 1)
        elif size == 1:
            cv.put(sx, sy, 3)
        else:
            cv.put(sx, sy, 1)
    return cv


def _peak(t, n):
    cv = Canvas()
    cv.poly([(0, 31), (11, 15), (24, 31)], 1)                 # the far hill
    apex = (28, 10)
    cv.poly([apex, (47, 31), (9, 31)], 2)                     # the mountain, shaded on the right
    cv.poly([apex, (28, 31), (9, 31)], 1)
    cv.poly([apex, (36, 20), (32, 18), (28, 22), (24, 18), (20, 21)], 3)   # the snow
    cv.line(apex[0], apex[1], 9, 31, 3, 1.2)
    cv.line(apex[0], apex[1], 47, 31, 3, 1.2)
    cv.rect(0, 30, 48, 32, 3)                                 # the ground
    cv.line(28, 10, 28, 0, 3, 1.4)                            # the pole
    for x in range(29, 40):                                   # the flag, a rippling banner
        k = x - 29
        wob = math.sin(t * 2 * math.pi / n - k * .55) * (0.5 + .22 * k)
        top = 1 + wob
        bot = top + 6 - k * 0.35
        for y in range(int(top), int(bot) + 1):
            cv.put(x, y, 3 if (y == int(top) or y == int(bot)) else 2)
    return cv


def _play(t, n):
    cv = Canvas()
    base = 30
    L = (12, 9, 6, 12, 15, 13)[t % 6]
    cx = 24
    cv.rect(14, base, 34, 32, 3)
    top = base - L
    coils = 5
    pts = [(cx, base)]
    for i in range(coils * 2):
        y = base - (i + 0.5) * L / (coils * 2)
        pts.append((cx + (7 if i & 1 else -7), y))
    pts.append((cx, top))
    for a, b in zip(pts, pts[1:]):
        cv.line(a[0], a[1], b[0], b[1], 3, 1.8)
    cv.rect(cx - 8, int(top) - 1, cx + 8, int(top) + 1, 3)     # the cap plate
    _ball(cv, cx, top - 8, 7, t * 0.9)
    return cv


# one icon a course: the file stem is the course's source name (apps/bonanza/courses/<stem>.bbc)
ICONS = (
    ("first", "FIRST", "a first rolling ball", _first, 6),
    ("trial", "TRIAL", "a stopwatch", _trial, 6),
    ("mill", "MILL", "a windmill turning", _mill, 6),
    ("moon", "MOON", "a crescent and stars", _moon, 5),
    ("summit", "PEAK", "a mountain with a flag", _peak, 6),
    ("playground", "PLAY", "a spring and a ball", _play, 6),
)


def icon_frames(i):
    stem, title, what, fn, k = ICONS[i]
    return [fn(t, k).rows() for t in range(k)]


def icon_text(i):
    stem, title, what, fn, k = ICONS[i]
    rows = [r for fr in icon_frames(i) for r in fr]
    return BA.bba_text(rows, k, "%s: %s - %d frames of %d x %d, frame 0 the rest pose, the rest a loop.\n"
                       "generated by tools/bbicons.py (SPEC.md 128.22.8); a PLACEHOLDER for the owner's art."
                       % (title, what, k, W, H))


def pad_text(pose):
    return BA.bba_text(BA.pad_rows(pose), None, "pad pose %d (%s): the glowing ring over a 32 x 16 cell top.\n"
                       "generated by tools/bonanza_assets.py's pad_overlay (SPEC.md 128.22.8)."
                       % (pose, BA.PAD_POSE_NAMES[pose]))


def outputs():
    d = {}
    for i, ic in enumerate(ICONS):
        d[os.path.join(ICON_DIR, ic[0] + ".bba")] = icon_text(i)
    for p in range(BA.PAD_POSES):
        d[os.path.join(PAD_DIR, "pad%d.bba" % p)] = pad_text(p)
    return d


def lane_bytes(i):
    """w words x h lines x frames, and the bytes as lane data"""
    k = ICONS[i][4]
    return W // 8, H, k, (W // 4) * H * k


def check():
    bad = 0
    for path, txt in sorted(outputs().items()):
        try:
            have = open(path).read()
        except OSError:
            have = None
        if have != txt:
            print("bbicons: %s is not what the generator writes" % os.path.relpath(path, ROOT), file=sys.stderr)
            bad += 1
    if bad:
        return 1
    return 0


# --- the previews -----------------------------------------------------------

def _png(out):
    from PIL import Image
    os.makedirs(out, exist_ok=True)
    z = 4
    pal = {1: BA.CGA1, 0: [(0, 0, 0), (0, 170, 0), (170, 0, 0), (170, 85, 0)]}

    def sheet(frames_list, herc, palette, gap=3):
        """frames_list: [[frame rows]...] side by side; transparent shows a dark blue-black ground"""
        fw = len(frames_list[0][0])
        fh = len(frames_list[0])
        wpx = fw * (2 if herc else 1)
        img = Image.new("RGB", (sum(wpx + gap for _ in frames_list) + gap, fh + 2 * gap), (24, 24, 40))
        ip = img.load()
        for fi, fr in enumerate(frames_list):
            ox = gap + fi * (wpx + gap)
            for y, row in enumerate(fr):
                for x, c in enumerate(row):
                    if c is None:
                        continue
                    if herc:
                        pr = BA.herc_pair(c, y, x)
                        for b in range(2):
                            ip[ox + 2 * x + b, gap + y] = (230, 230, 230) if (pr >> (1 - b)) & 1 else (0, 0, 0)
                    else:
                        ip[ox + x, gap + y] = palette[c]
        return img.resize((img.width * z, img.height * z * (1 if herc else 1)), Image.NEAREST)

    def stack(imgs):
        w = max(i.width for i in imgs)
        h = sum(i.height + 8 for i in imgs)
        o = Image.new("RGB", (w, h), (60, 60, 60))
        y = 0
        for i in imgs:
            o.paste(i, (0, y))
            y += i.height + 8
        return o
    rows = []
    for i, ic in enumerate(ICONS):
        fr = icon_frames(i)
        rows.append(sheet(fr, False, pal[1]))
        rows.append(sheet(fr, True, pal[1]))
    stack(rows).save(os.path.join(out, "art-icons.png"))
    rows = []
    for i, ic in enumerate(ICONS):
        fr = icon_frames(i)
        rows.append(sheet(fr, False, pal[0]))
    stack(rows).save(os.path.join(out, "art-icons-pal0.png"))
    # the crystal rail and the pads: a small route of tiles over a dark void
    def tiles_img(herc, palette):
        cw, ch = 192, 96
        pic = [[None] * cw for _ in range(ch)]
        route = [(0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (4, 2), (4, 1), (5, 1), (6, 1)]
        for wx, wy in sorted(route, key=lambda c: (c[0] + c[1], c[0])):
            cx, cy = 16 * (wx - wy) + 96, 8 * (wx + wy) + 12
            for j in range(10):                                    # the side walls: columns 0..15 sw, 16..31 se
                for k in range(16):
                    for face, xx in (("sw", cx - 16 + k), ("se", cx + k)):
                        yy = cy + (k >> 1 if face == "sw" else 7 - (k >> 1)) + j
                        if 0 <= xx < cw and 0 <= yy < ch:
                            pic[yy][xx] = BA.crystal_side_ink(face, k, j)
            for v in range(-8, 8):
                for u in range(-16, 16):
                    c = BA.crystal_top_ink(u, v)
                    if c is not None and 0 <= cx + u < cw and 0 <= cy + v < ch:
                        pic[cy + v][cx + u] = c
        for pose, (wx, wy) in zip((0, 1, 2, 3), ((0, 3), (3, 3), (4, 1), (6, 1))):
            cx, cy = 16 * (wx - wy) + 96, 8 * (wx + wy) + 12
            for (u, v), c in BA.pad_overlay(pose).items():
                if 0 <= cx + u < cw and 0 <= cy + v < ch:
                    pic[cy + v][cx + u] = c
        return sheet([pic], herc, palette)
    stack([tiles_img(False, pal[1]), tiles_img(False, pal[0]), tiles_img(True, pal[1])]).save(
        os.path.join(out, "art-crystal.png"))
    # the four pad poses alone, over a crystal tile
    frames = []
    for pose in range(BA.PAD_POSES):
        fr = [[BA.crystal_top_ink(u, v) for u in range(-16, 16)] for v in range(-8, 8)]
        for (u, v), c in BA.pad_overlay(pose).items():
            fr[v + 8][u + 16] = c
        frames.append(fr)
    stack([sheet(frames, False, pal[1]), sheet(frames, False, pal[0]), sheet(frames, True, pal[1])]).save(
        os.path.join(out, "art-pads.png"))
    print("bbicons: previews in %s" % out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--png", metavar="DIR")
    a = ap.parse_args()
    if a.check:
        rc = check()
        print("bbicons --check: %s" % ("ok" if not rc else "FAILED"))
        return rc
    if a.png:
        _png(a.png)
        return 0
    os.makedirs(ICON_DIR, exist_ok=True)
    os.makedirs(PAD_DIR, exist_ok=True)
    for path, txt in sorted(outputs().items()):
        with open(path, "w", newline="\n") as f:
            f.write(txt)
    for i, ic in enumerate(ICONS):
        w, h, k, b = lane_bytes(i)
        print("  %-11s %-5s %d words x %d lines x %d frames = %d bytes" % (ic[0] + ".bba", ic[1], w, h, k, b))
    return 0


if __name__ == "__main__":
    sys.exit(main())
