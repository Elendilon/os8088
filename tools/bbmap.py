#!/usr/bin/env python3
"""bbmap.py - a Bounce Bonanza course's MAP: the shipped picture (the course compiler's own CGA art) with the
course's route, its branches, its marks and its CGA windows drawn over it - the design sketches' style
(docs/plans/bonanza-courses/*/sketch.py) for the course as it ships rather than as it was planned.
Host-only; nothing in `make` runs it and it writes no shipped byte.

    python3 tools/bbmap.py apps/bonanza/courses/mill.bbc -o mill-map.png [--log DEMO.BZR] [--scale 2]

THE ROUTE (red) is a real run of the model (bbcourse.Physics) over the picture: the course's own shipped demo
(build/bonanza-art/BZD<NAME>.BIN, as `make bonanza` built it) unless --log names another, its ball's centre
every step. A BRANCH (cyan) is its `branch` ways joined. THE MARKS are the source's own: the start, every
flag (checkpoint, numbered in source order), the cup, the clocks, the pads, springs, tubes, see-saws and the
props. THE CGA WINDOWS (cyan boxes, 320 x 200 picture pixels) sit centred on the start, each clock and the cup:
one screen of the game each. Every position is the model's ball resting on that cell (Physics.poke), so a mark
lands where a ball would be drawn there."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bbcourse as B          # noqa: E402
import bbplay as BP           # noqa: E402

RED, CYAN, YEL, PINK, WHITE, ORANGE, GREEN = (255, 64, 64), (0, 220, 230), (255, 220, 0), (255, 110, 200), \
    (255, 255, 255), (255, 150, 0), (90, 230, 120)
WIN_W, WIN_H = 320, 200


def kind_names():
    """{prop kind: a short name} out of the families' table and bbcourse's PK_ / FK_ constants"""
    out = {}
    for f in getattr(B, "FAMILIES", ()):
        for kd in f.get("kinds", ()):
            out.setdefault(kd["kind"], kd["name"])
    for n in dir(B):
        if (n.startswith("PK_") or n.startswith("FK_")) and isinstance(getattr(B, n), int):
            out.setdefault(getattr(B, n), n[3:].lower())
    return out


def at_px(c, mat, cell):
    """the picture point of a ball resting on CELL (its centre), or None where no ball can rest"""
    try:
        p = B.Physics(c, play=True, mat=mat).poke(cell[0], cell[1], 0, 0)
    except Exception:
        return None
    return p.px + 8, p.py + 8


def route_points(c, log):
    _k, mat, kt, _fl = B.decode_log_t(log)
    p = B.Physics(c, play=True, mat=mat)
    pts = []
    for k, t in kt:
        p.step(k, t)
        if not p.tube:
            pts.append((p.px + 8, p.py + 8))
        if p.tout:
            break
    return pts, mat


def main(argv=None):
    from PIL import Image, ImageDraw, ImageFont
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("course")
    a.add_argument("-o", "--out", required=True)
    a.add_argument("--log", help="a BZR or BZD log to draw as the route (default: the course's shipped demo)")
    a.add_argument("--scale", type=int, default=2)
    o = a.parse_args(argv)
    src_text = open(o.course).read()
    c = BP.compile_full(src_text, os.path.basename(o.course))
    s = c.src
    name = c.name
    logp = o.log or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "bonanza-art",
                                 "BZD%s.BIN" % name.upper())
    pts, mat = [], c.ball if isinstance(getattr(c, "ball", None), int) else 0
    if os.path.exists(logp):
        pts, mat = route_points(c, open(logp, "rb").read())
    pal = BP.palette(s)
    base = BP.to_rgb(Image.frombytes("P", (c.width, c.lines), b"".join(bytes(r) for r in c.pic)), pal)
    S = o.scale
    im = base.resize((c.width * S, c.lines * S), Image.NEAREST).convert("RGB")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    def P(xy):
        return xy[0] * S, xy[1] * S

    try:
        font = ImageFont.load_default(size=8 * S)
    except TypeError:
        font = ImageFont.load_default()

    def label(xy, text, col, dy=-10):
        x, y = P(xy)
        x, y = x + 4 * S, y + dy * S
        bb = d.textbbox((x, y), text, font=font)
        d.rectangle((bb[0] - 2, bb[1] - 1, bb[2] + 2, bb[3] + 1), fill=(0, 0, 0, 170))
        d.text((x, y), text, fill=col + (255,), font=font)

    def dot(xy, col, r=4 * 2):
        x, y = P(xy)
        d.ellipse((x - r, y - r, x + r, y + r), fill=col + (255,), outline=(0, 0, 0, 255))

    if len(pts) > 1:                                    # the route (red)
        d.line([P(q) for q in pts], fill=RED + (235,), width=3 * S)
    for bname, ways in (s.branches or {}).items():      # each branch (cyan), its ways joined
        q = [at_px(c, mat, w) for w, _ln in ways]
        q = [x for x in q if x]
        if len(q) > 1:
            d.line([P(x) for x in q], fill=CYAN + (235,), width=3 * S)
            label(q[0], bname.lower(), CYAN)
    marks, wins = [], []
    st = at_px(c, mat, s.start[0])
    if st:
        marks.append((st, ORANGE, "start"))
        wins.append(st)
    for i, ck in enumerate(s.ckpts):
        q = at_px(c, mat, ck["at"])
        if q:
            marks.append((q, PINK, "flag %d%s" % (i + 1, " (%s)" % B.MAT_NAMES[ck["ball"]] if ck.get("ball")
                                                  is not None and hasattr(B, "MAT_NAMES") else "")))
    for cp in s.cups:
        q = at_px(c, mat, cp["at"])
        if q:
            marks.append((q, WHITE, "CUP"))
            wins.append(q)
    for ck in s.clocks:
        q = at_px(c, mat, ck["at"])
        if q:
            marks.append((q, CYAN, "clock"))
            wins.append(q)
    for pd in s.pads:
        q = at_px(c, mat, pd["at"])
        if q:
            marks.append((q, GREEN, "%s pad" % (B.MAT_NAMES[pd["mat"]] if hasattr(B, "MAT_NAMES") else "ball")))
    for sp in s.springs:
        q = at_px(c, mat, sp["at"])
        if q:
            marks.append((q, GREEN, "spring"))
    for tb in s.tubes:
        for end, what in ((tb["inn"], "tube in"), (tb["out"], "tube out")):
            q = at_px(c, mat, end)
            if q:
                marks.append((q, YEL, what))
    for sw in s.seesaws:
        cells = sorted(sw["cells"])
        q = at_px(c, mat, cells[len(cells) // 2])
        if q:
            marks.append((q, YEL, "SEE-SAW"))
    kn, seen = kind_names(), set()
    SKIP = {getattr(B, n_) for n_ in ("FK_TILT", "FK_TILTLANE", "PK_CLOCK") if hasattr(B, n_)} | {80, 81, 9}
    for pr in s.props:
        k, at = pr["kind"], pr.get("at")
        nm = kn.get(k, "prop %d" % k)
        if not isinstance(at, tuple) or (nm, at) in seen or k in SKIP:
            continue
        if any(nm == n_ for (n_, a_) in seen if abs(a_[0] - at[0]) + abs(a_[1] - at[1]) <= 2):
            seen.add((nm, at))
            continue                                     # (one label for a group of the same thing)
        seen.add((nm, at))
        q = at_px(c, mat, at)
        if q:
            marks.append((q, WHITE, nm))
    for q, col, text in marks:
        dot(q, col)
        label(q, text, col)
    for i, q in enumerate(wins):                        # one CGA window each (the game's 320 x 200)
        x, y = q
        d.rectangle((P((x - WIN_W // 2, y - WIN_H // 2)), P((x + WIN_W // 2, y + WIN_H // 2))),
                    outline=CYAN + (255,), width=S)
    span = (max(q[0] for q in pts) - min(q[0] for q in pts)) if pts else 0
    head = ("%s \"%s\": route px span %d; course %d lines tall; red = the route (its shipped demo, %d steps), "
            "cyan = a branch; cyan boxes = one CGA window at the start, each clock and the cup"
            % (name.upper(), s.title or "", span, c.lines, len(pts)))
    im = Image.alpha_composite(im.convert("RGBA"), ov)
    canvas = Image.new("RGBA", (im.size[0], im.size[1] + 12 * S), (10, 10, 24, 255))
    canvas.paste(im, (0, 12 * S))
    ImageDraw.Draw(canvas).text((8, 4), head, fill=(230, 230, 230, 255), font=font)
    canvas.convert("RGB").save(o.out)
    print("bbmap: %s -> %s (%d x %d, %d marks, %d route points)" % (o.course, o.out, canvas.size[0],
                                                                    canvas.size[1], len(marks), len(pts)))


if __name__ == "__main__":
    main()
