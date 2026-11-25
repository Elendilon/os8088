#!/usr/bin/env python3
"""KITE HILL: what the CAMERA shows of the sky art (the owner, 2026-11-25: "Is anyone going to see the further
out kites, with our camera moving as it does?").  Host only; nothing in `make` runs it.

    python3 docs/plans/bonanza-courses/kite/camera.py [OUT.png]

The autopilot's route through the tool's own camera model - `bbcourse.guide_runs`, the run `--guide` reads: the
model stepped at each card's rate, the camera once a frame - and, for every `art` piece of the course, the
frames on which its pixels are in the window: WHOLLY (every opaque pixel) and PARTLY (any), in seconds, on the
CGA (320 x 200) and the Hercules (360 x 200 of the same picture), with the stretch of the run it is seen in.
OUT.png (default camera.png beside this file): the picture, brighter where the window spends longer, the
route's window drawn every half second (cyan: CGA), every art piece boxed (green: seen whole at some time;
yellow: only ever partly; red: never)."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(HERE, ".."))
import bbcourse as B                                   # noqa: E402
import artkit as A                                     # noqa: E402

COURSE = os.path.join(ROOT, "apps", "bonanza", "courses", "kite.bbc")

def where(c, f):
    """the stretch of the course a frame's ball is in, from its picture y (the course climbs the screen)"""
    y = f["py"]
    for lim, name in ((690, "the meadow and the first rise"), (640, "the breezeway"), (590, "the gust bridge"),
                      (470, "the fan plaza and the thermal"), (400, "terrace 3 and the windbreaks"),
                      (300, "the launch plaza"), (200, "the glide"), (-999, "the summit")):
        if y >= lim:
            return name


def main(out):
    c = B.compile_course(COURSE)
    arts = []
    for f, x, y in re.findall(r"^art (\S+) (\d+) (\d+)", open(COURSE).read(), flags=re.M):
        pix = [(int(x) + px, int(y) + py) for (px, py) in B.read_bba(os.path.join(B.COURSE_DIR, f))]
        arts.append((f[:-4], pix))
    runs = B.guide_runs(c)
    seen = {}
    print("%-13s %-9s %7s %7s %7s  %s" % ("piece", "card", "run s", "whole s", "part s", "seen whole / partly while the ball is on"))
    for herc in (0, 1):
        W, _H, rl, _l = B.CARDS[herc]
        name, r = runs[herc][0]
        hz = B.CARD_HZ[herc]
        for an, pix in arts:
            whole = part = 0
            wsec, psec = {}, {}
            for f in r.rows:
                xa, ya = 8 * f["c0"], f["R0"] * rl
                n = sum(1 for (x, y) in pix if xa <= x < xa + 8 * W and ya <= y < ya + B.WIN_LINES)
                if n == len(pix):
                    whole += 1
                    wsec[where(c, f)] = wsec.get(where(c, f), 0) + 1
                elif n * 4 >= len(pix):             # (PARTLY: a quarter of it or more - a tail's tip is not a kite)
                    part += 1
                    psec[where(c, f)] = psec.get(where(c, f), 0) + 1
            seen[(an, herc)] = (whole, part)
            print("%-13s %-9s %7.1f %7.1f %7.1f  %s" % (
                an, "Hercules" if herc else "CGA", len(r.rows) / hz, whole / hz, part / hz,
                "; ".join(["whole: " + ", ".join("%s %.1f s" % (k, v / hz) for k, v in wsec.items())] * bool(wsec) +
                          ["partly: " + ", ".join("%s %.1f s" % (k, v / hz) for k, v in psec.items())] * bool(psec))
                or "never"))
    from PIL import Image, ImageDraw
    W, _H, rl, _l = B.CARDS[0]
    r = runs[0][0][1]
    heat = [[0] * (c.width // 8) for _ in range(c.lines // 8)]
    for f in r.rows:
        for by in range(max(0, f["R0"] * rl // 8), min(c.lines // 8, (f["R0"] * rl + B.WIN_LINES) // 8)):
            for bx in range(max(0, f["c0"]), min(c.width // 8, f["c0"] + W)):
                heat[by][bx] += 1
    img = Image.new("RGB", (c.width, c.lines))
    pal = A.PALS[0]
    img.putdata([tuple((v * (90 if heat[y // 8][x // 8] == 0 else 255)) // 255 for v in pal[c.pic[y][x]]) if c.pic[y][x]
                 else ((0, 0, 0) if heat[y // 8][x // 8] == 0 else (0, 0, min(120, 30 + heat[y // 8][x // 8] // 4)))
                 for y in range(c.lines) for x in range(c.width)])
    img = img.resize((2 * c.width, 2 * c.lines), Image.NEAREST)
    d = ImageDraw.Draw(img)
    step = int(B.CARD_HZ[0] / 2)
    for f in r.rows[::step]:
        xa, ya = 8 * f["c0"], f["R0"] * rl
        d.rectangle([2 * xa, 2 * ya, 2 * (xa + 8 * W) - 1, 2 * (ya + B.WIN_LINES) - 1], outline=(0, 200, 255))
    for i in range(1, len(r.rows)):
        a_, b_ = r.rows[i - 1], r.rows[i]
        d.line([2 * a_["px"], 2 * a_["py"], 2 * b_["px"], 2 * b_["py"]], fill=(255, 255, 255), width=2)
    for an, pix in arts:
        xs, ys = [x for x, _y in pix], [y for _x, y in pix]
        w0, p0 = seen[(an, 0)]
        col = (0, 255, 0) if w0 else ((255, 255, 0) if p0 else (255, 40, 40))
        d.rectangle([2 * min(xs) - 3, 2 * min(ys) - 3, 2 * max(xs) + 3, 2 * max(ys) + 3], outline=col, width=2)
        d.text((2 * min(xs), 2 * max(ys) + 6), "%s %.1f s" % (an.replace("kite_", ""), w0 / B.CARD_HZ[0]), fill=col)
    d.text((8, 2 * c.lines - 44), "KITE HILL, the autopilot's route (white) and its CGA window every 0.5 s (cyan boxes).", fill=(255, 255, 255))
    d.text((8, 2 * c.lines - 30), "Dim: never in the window.  Art boxed: green seen whole (seconds), yellow only partly, red never.", fill=(255, 255, 255))
    img.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "camera.png"))
