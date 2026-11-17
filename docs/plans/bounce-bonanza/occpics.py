#!/usr/bin/env python3
"""BOUNCE BONANZA - what a fall behind a back edge looks like under each
occlusion option (the occlusion deep-dive, 2026-11-17).  NOT a build input;
nothing in `make` runs it.

For a course it finds the binding model's falls off BACK edges (a ball poked on
a floor cell rolling into the VOID cell behind it), picks the one the rule hides
most, and draws its frames side by side, on the CGA's palette, zoomed:
  today      the shipped records, laid as the card lays them (the ghost dither,
             SPEC.md 128.15.10: a hidden ball pixel shows on the odd lattice)
  (c)        no void record: the ball drawn whole over what it falls behind
             (SPEC.md 128.11.4.5's rejected option (c) and 'novoid')
  V ghost    option V: below the VOID cell's ghost height H the WHOLE ball is
             drawn through the checker; above it, as (c) (nothing lays there)
  A          option A: in a VOID cell the mask is computed from the cells in front
             (occproto.Analytic, depth 2) and laid as the card lays a record
Writes occ-fall-<course>.png beside itself.

    python3 docs/plans/bounce-bonanza/occpics.py [course.bbc ...]   (default MILL and PEAK)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import occproto as P  # noqa: E402
B = P.B

ZOOM = 4
CROP_W, CROP_H = 56, 44


def falls(c, gh):
    """-> [(hidden score, [(px, py, sb, zb, air, cell)])]: every back-edge fall the model makes from a poke"""
    out = []
    for (wx, wy), v in sorted(c.cells.items()):
        if v[2] & 15 != B.KIND_FLOOR or (wx, wy) in c.pcell:
            continue
        for (dx, dy, gvx, gvy) in ((-1, 0, -B.VMAXG, 0), (0, -1, 0, -B.VMAXG),
                                   (-1, 0, -B.VMAXG // 2, 0), (0, -1, 0, -B.VMAXG // 2)):
            n = (wx + dx, wy + dy)
            if n not in gh:
                continue
            p = B.Physics(c, play=False)
            p.poke(wx, wy, gvx, gvy)
            f0 = p.nfall
            path = []
            for _ in range(120):
                p.step(0)
                if p.nfall != f0:
                    break
                path.append((p.px, p.py, p.sb, p.zb, p.air, (p.gx >> 12, p.gy >> 12)))
            else:
                continue
            score = 0                       # the frames where the rule hides PART of the ball: what tells the
            for (px, py, sb, zb, air, cell) in path:    # options apart
                if c.cells.get(cell, [0, 0, 0])[2] & 15 == B.KIND_VOID:
                    f = P.hidden_frac(c, sb, zb, px, py)
                    score += 0.15 < f < 0.85
            out.append((score, (wx, wy), path))
    out.sort(key=lambda t: -t[0])
    return out


def frame(c, gh, st, how, An=None):
    px, py, sb, zb, air, cell = st
    pic = {}
    isvoid = c.cells.get(cell, [0, 0, 0])[2] & 15 == B.KIND_VOID
    if how == "today" or not isvoid or cell in c.slabcells:   # (every option keeps today's records off the void)
        pic = B.composite(c, px, py, sb, zb, air, via="records", ghost=True)
        return pic
    bp = B.ball_pixels(px, py)
    if how == "A":
        a = An.hidden(cell[0], cell[1], zb, 0, bp)
        if a is None:
            return B.composite(c, px, py, sb, zb, air, via="records", ghost=True)
        for (x, y), v in bp.items():
            if (x, y) not in a or B.ghost(x, y):
                pic[(x, y)] = v
        return pic
    g = gh.get(cell)
    below = g is not None and zb < g[0] and c.cells.get(cell, [0, 0, 0])[2] & 15 == B.KIND_VOID
    for (x, y), v in bp.items():
        if how == "c" or not below:
            pic[(x, y)] = v
        elif how == "ghost" and B.ghost(x, y):
            pic[(x, y)] = v
    return pic


def draw(c, gh, path, fname, An):
    from PIL import Image, ImageDraw
    first = next((i for i, st in enumerate(path) if c.cells.get(st[5], [0, 0, 0])[2] & 15 == B.KIND_VOID), 0)
    first = max(0, first - 1)
    span = path[first:]
    sel = [span[(len(span) - 1) * i // 7] for i in range(8)] if len(span) >= 8 else span
    cx = sum(s[0] for s in sel) // len(sel) + 8
    cy = sum(s[1] for s in sel) // len(sel) + 8
    x0, y0 = max(0, cx - CROP_W // 2), max(0, cy - CROP_H // 2)
    cols = ("today", "c", "ghost", "A")
    names = ("today (records)", "(c): drawn over", "V: ghosted", "A: computed")
    W, H = CROP_W * ZOOM, CROP_H * ZOOM
    img = Image.new("RGB", (len(cols) * (W + 6) + 6, len(sel) * (H + 6) + 26), (40, 40, 40))
    d = ImageDraw.Draw(img)
    for j, nm in enumerate(names):
        d.text((6 + j * (W + 6), 6), nm, fill=(255, 255, 255))
    for i, st in enumerate(sel):
        for j, how in enumerate(cols):
            over = frame(c, gh, st, how, An)
            tile = Image.new("RGB", (CROP_W, CROP_H))
            tp = tile.load()
            for y in range(CROP_H):
                for x in range(CROP_W):
                    X, Y = x0 + x, y0 + y
                    v = over.get((X, Y), c.pic[Y][X] if 0 <= Y < c.lines and 0 <= X < c.width else 0)
                    tp[x, y] = B.CGA1[v]
            img.paste(tile.resize((W, H), Image.NEAREST), (6 + j * (W + 6), 26 + i * (H + 6)))
    img.save(fname)
    return sel


def main():
    paths = sys.argv[1:] or [p for p in P.course_paths() if os.path.basename(p) in ("mill.bbc", "summit.bbc")]
    for path in paths:
        c = B.compile_course(path)
        gh = P.ghost_heights(c)
        fl = falls(c, gh)
        if not fl:
            print("%s: no back-edge fall found" % c.name)
            continue
        score, at, path_ = fl[0]
        out = os.path.join(HERE, "occ-fall-%s.png" % c.name.lower())
        sel = draw(c, gh, path_, out, P.Analytic(c, 2))
        print("%s: %d back-edge falls from pokes; drew the one off (%d, %d) (%d frames of its %d steps partly hidden"
              "), frames %s -> %s" % (c.name, len(fl), at[0], at[1], score, len(path_),
                                           ", ".join("z %d" % s[3] for s in sel), os.path.relpath(out, B.ROOT)))


if __name__ == "__main__":
    main()
