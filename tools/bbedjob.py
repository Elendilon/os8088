#!/usr/bin/env python3
"""bbedjob - THE COURSE BUILDER'S JOBS (SPEC.md 130.58.8), each run as a process
by tools/bbedit.py, reporting JSON lines on stdout and killed by Cancel or by
the next edit:

    python3 tools/bbedjob.py picture COURSE.bbc OUTDIR [--name PATH] [--gaps]   # the Iso view's picture
    python3 tools/bbedjob.py check   COURSE.bbc [--strict] [--name PATH] # the full check
    python3 tools/bbedjob.py ride    COURSE.bbc LINE [--name PATH]     # how each ball rides a shape

Each line is a JSON object: {"stage": ..., "what": ...} while it works, then
{"stage": "done", "ok": true|false, ...}.

PICTURE compiles WITHOUT the occluder pass (fast) and with the part's block
limit lifted, because the picture is all it keeps: a course over the limit
still gets a picture to look at, and the CHECK says what is over. It writes
OUTDIR/cga.png, OUTDIR/herc.png, OUTDIR/owners.bin (the cell that drew each
pixel, 256 wx + wy or -1, int32 rows) and OUTDIR/meta.json (the size, the
origin, every mark the visibility audit weighs with its seen and hidden
pixels; with --gaps, the gap band's candidate faces, SPEC.md 130.57.4).

CHECK is bbcourse's compile_course: the errors that refuse the course and
the warnings that do not (SPEC.md 130.58.4); a blend warning carries its two
regions' cells and the seam's pixels (130.58.18).

RIDE (SPEC.md 130.58.19) rolls each ball over the shape on line LINE - a
chute, a pit or a hump - on the play-only compile, and answers in words.
"""

import json
import os
import sys
import time
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbcourse as B  # noqa: E402


def emit(**kw):
    sys.stdout.write(json.dumps(kw) + "\n")
    sys.stdout.flush()


def palette(src):
    """the course's CGA colours (SPEC.md 130.16.6): its `palette` byte, else palette 1 bright"""
    b = src.palette[0] if src.palette else 0x30
    bright = bool(b & 0x10)
    if b & 0x20:
        cols = [(85, 255, 255), (255, 85, 255), (255, 255, 255)] if bright else \
               [(0, 170, 170), (170, 0, 170), (170, 170, 170)]
    else:
        cols = [(85, 255, 85), (255, 85, 85), (255, 255, 85)] if bright else \
               [(0, 170, 0), (170, 0, 0), (170, 85, 0)]
    return [(0, 0, 0)] + cols


BLEND_KEYS = ("regions", "lines", "seam", "px", "cards", "x0", "y0")


def warning(w):
    """a warning as JSON: its kind, message, line, cell and whether accepted - and a blend's two regions' cells,
    lines and seam pixels with the picture's origin they were measured at (SPEC.md 130.58.18), for the window"""
    out = {k: w[k] for k in ("kind", "msg", "line", "cell", "accepted")}
    out.update({k: w[k] for k in BLEND_KEYS if k in w})
    return out


def picture(path, out, name=None, gaps=False):
    from PIL import Image
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    path = name or path
    B.BLK_MAX = 1 << 30                         # the picture's alone: never a part that ships (130.58.8)
    B.GAP_DETECT = gaps                         # the gap band's candidates, only while the overlay shows (130.58.21)
    emit(stage="compile", what="laying the course")
    try:
        c = B.compile_course(text, path, occluders=False)
    except B.CourseError as e:
        emit(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 2))
        return 1
    emit(stage="render", what="drawing the picture")
    os.makedirs(out, exist_ok=True)
    pal = palette(c.src)
    img = Image.new("RGB", (c.width, c.lines))
    img.putdata([pal[v] for r in c.pic for v in r])
    img.save(os.path.join(out, "cga.png"))
    h = Image.new("L", (c.width * 2, c.lines))
    data = []
    for y, row in enumerate(c.pic):
        for x, v in enumerate(row):
            pr = B.herc_pair(v, y, x)
            data += [255 * (pr >> 1), 255 * (pr & 1)]
    h.putdata(data)
    h.save(os.path.join(out, "herc.png"))
    emit(stage="owners", what="who drew each pixel")
    ob = B.owners_canvas(c)
    a = array("i")
    for row in ob:
        a.extend(row)
    with open(os.path.join(out, "owners.bin"), "wb") as f:
        a.tofile(f)
    marks = []
    try:
        for m in B.vis_marks(c):
            pix = c.prop_pix[m["prop"]]
            key = m["what"].split()[-1] if m["what"].startswith("tube") else m["what"]
            pts = pix.get(key) or []
            own = 256 * m["cell"][0] + m["cell"][1]
            marks.append({"what": m["what"], "cell": list(m["cell"]), "pct": round(m["pct"], 1), "need": m["need"],
                          "below": m["below"], "line": c.props[m["prop"]].get("line"),
                          "cover": [[o >> 8, o & 255, n] for o, n in m["cover"] if o >= 0],
                          "seen": [[x, y] for (x, y) in pts if ob[y][x] == own],
                          "hidden": [[x, y] for (x, y) in pts if ob[y][x] != own]})
    except Exception as e:                      # (the audit wants more than a picture compile holds)
        emit(stage="log", what="no visibility marks: %s" % e)
    meta = {"width": c.width, "lines": c.lines, "x0": c.x0, "y0": c.y0, "name": c.name, "marks": marks,
            "warnings": [warning(w) for w in c.warnings],
            "gaps": c.gap_faces if gaps else None, "secs": round(time.time() - t0, 2)}
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f)
    emit(stage="done", ok=True, out=out, secs=meta["secs"])
    return 0


def check(path, strict, name=None):
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    path = name or path
    emit(stage="compile", what="the full check (occluders, reach, traps)")
    try:
        c = B.compile_course(text, path, strict=strict)
    except B.CourseError as e:
        emit(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 1))
        return 1
    warns = [warning(w) for w in c.warnings]
    emit(stage="done", ok=True, warnings=warns, secs=round(time.time() - t0, 1))
    return 0


SIDES = {(1, 0): "+x", (-1, 0): "-x", (0, 1): "+y", (0, -1): "-y"}


def _sg(v):
    return (v > 0) - (v < 0)


def shape_of(toks):
    """a shape statement's numbers: chute -> {"kind", "width", "ways": [(x, y, z or None)]}, pit -> {"kind",
    "at", "z", "radius", "depth", "hole"}, hump -> {"kind", "at", "z", "along", "n"}; None for anything else"""
    t, k = toks, toks[0] if toks else None
    try:
        if k == "chute":
            ways, i = [], 1
            while i < len(t):
                if t[i] == "way":
                    z = float(t[i + 3]) if i + 3 < len(t) and _num(t[i + 3]) else None
                    ways.append((int(t[i + 1]), int(t[i + 2]), z))
                    i += 4 if z is not None else 3
                else:
                    i += 1
            return {"kind": k, "width": int(t[1]), "ways": ways}
        if k == "pit":
            kw = {t[i]: t[i + 1] for i in range(4, len(t) - 1)}
            return {"kind": k, "at": (int(t[1]), int(t[2])), "z": float(t[3]), "radius": int(kw.get("radius", 2)),
                    "depth": int(kw.get("depth", 8)), "hole": int(kw.get("hole", 1))}
        if k == "hump":
            along, n = "x", 1
            if "along" in t:
                i = t.index("along")
                along, n = t[i + 1], int(t[i + 2])
            return {"kind": k, "at": (int(t[1]), int(t[2])), "z": float(t[3]) if len(t) > 3 and _num(t[3]) else 0,
                    "along": along, "n": n}
    except (ValueError, IndexError):
        return None
    return None


def _num(t):
    try:
        float(t)
        return True
    except ValueError:
        return False


def chute_route(ways):
    """the cells the autopilot steers through, a quarter and three quarters along each leg and the last way
    (never ON a corner: the tool lays it radial, and the autopilot cuts it as a player does)"""
    pts = []
    for (ax, ay, _), (bx, by, _) in zip(ways, ways[1:]):
        for f in (0.25, 0.75):
            q = (int(round(ax + (bx - ax) * f)), int(round(ay + (by - ay) * f)))
            if not pts or pts[-1] != q:
                pts.append(q)
    pts.append(tuple(ways[-1][:2]))
    return pts


def _roll(c, mat, at, v, route=None, secs=20.0, done=None):
    """one run: poke at AT with ground velocity V, steered by the autopilot along ROUTE (or no keys); ->
    (what happened, seconds, the cell it ended on, the top speed in tiles a second)"""
    p = B.Physics(c, play=True, mat=mat).poke(at[0], at[1], v[0], v[1])
    if route:
        p.route = [B._way_point(c, t) for t in route]
        p.wp = 0
    top, still = 0, 0
    for k in range(int(secs * B.STEP_HZ)):
        p.step(p.auto() if route else 0)
        cell = (p.gx >> 12, p.gy >> 12)
        sp = max(abs(p.gvx), abs(p.gvy))
        top = max(top, sp)
        if p.nfall:
            return "fell", k / B.STEP_HZ, cell, top
        if done and done(cell):
            return "through", k / B.STEP_HZ, cell, top
        still = still + 1 if sp < 8 and not p.air else 0
        if still > B.STEP_HZ:
            return "stopped", k / B.STEP_HZ, cell, top
    return "still rolling", secs, cell, top


def rides(c, toks):
    """SPEC.md 130.58.19: each ball over one shape, in words -> [{"ball", "test", "result", "words"}]"""
    sh = shape_of(toks)
    if not sh:
        return []
    tps = lambda v: v * B.STEP_HZ / 4096.0     # noqa: E731  (gu a step -> tiles a second)
    out = []
    for mat in (B.MAT_RUBBER, B.MAT_STEEL, B.MAT_GLASS):
        nm = B.MAT_NAMES[mat]
        if sh["kind"] == "chute":
            ws = sh["ways"]
            d = (_sg(ws[1][0] - ws[0][0]), _sg(ws[1][1] - ws[0][1]))
            end = ws[-1][:2]
            near = lambda cl: abs(cl[0] - end[0]) <= 1 and abs(cl[1] - end[1]) <= 1   # noqa: E731
            for test, v, route in (("steered along it", (B.VMAXG * d[0] // 2, B.VMAXG * d[1] // 2),
                                    chute_route(ws)),
                                   ("let go at the top", (B.VMAXG * d[0] // 2, B.VMAXG * d[1] // 2), None)):
                r, t, cl, top = _roll(c, mat, ws[0][:2], v, route, done=near)
                words = {"through": "reaches the far end in %.1f s" % t,
                         "fell": "falls off at %d, %d after %.1f s" % (cl[0], cl[1], t),
                         "stopped": "comes to rest at %d, %d after %.1f s" % (cl[0], cl[1], t),
                         "still rolling": "is still rolling after %.0f s (at %d, %d)" % (t, cl[0], cl[1])}[r]
                out.append({"ball": nm, "test": test, "result": r,
                            "words": "%s: %s, top speed %.1f tiles/s" % (test, words, tps(top))})
        elif sh["kind"] == "pit":
            x, y = sh["at"]
            rr = sh["radius"]
            for test, frac in (("round the lip at half speed", 2), ("round the lip at full speed", 1)):
                r, t, cl, top = _roll(c, mat, (x - rr, y), (0, B.VMAXG // frac), None, secs=10.0)
                words = {"fell": "drops into the hole after %.1f s" % t,
                         "stopped": "settles at %d, %d after %.1f s" % (cl[0], cl[1], t),
                         "still rolling": "is still circling after %.0f s" % t, "through": ""}[r]
                out.append({"ball": nm, "test": test, "result": r, "words": "%s: %s" % (test, words)})
        else:                                   # a hump: rolled across its axis at three speeds
            x, y = sh["at"]
            ax = (0, 1) if sh["along"] == "x" else (1, 0)      # (across the ridge)
            at = (x - 2 * ax[0], y - 2 * ax[1])
            over = lambda cl: (cl[0] - x) * ax[0] + (cl[1] - y) * ax[1] >= 1   # noqa: E731  (past its cells)
            for test, frac in (("rolled at it slowly", 4), ("at half speed", 2), ("at full speed", 1)):
                r, t, cl, top = _roll(c, mat, at, (B.VMAXG * ax[0] // frac, B.VMAXG * ax[1] // frac), None,
                                      secs=6.0, done=over)
                words = {"through": "gets over (%.1f s)" % t, "fell": "falls off at %d, %d" % cl,
                         "stopped": "stops at %d, %d" % cl, "still rolling": "rolls on"}[r]
                out.append({"ball": nm, "test": test, "result": r, "words": "%s: %s" % (test, words)})
    return out


def ride(path, line, name=None):
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    path = name or path
    lines = text.split("\n")
    toks = lines[line - 1].split("#")[0].split() if 0 < line <= len(lines) else []
    emit(stage="compile", what="laying the course to roll on")
    held = B.BLK_MAX
    B.BLK_MAX = 1 << 30
    try:
        c = B.compile_course(text, path, occluders=False)
    except B.CourseError as e:
        emit(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 2))
        return 1
    finally:
        B.BLK_MAX = held
    emit(stage="roll", what="rolling each ball")
    emit(stage="done", ok=True, line=line, rides=rides(c, toks), secs=round(time.time() - t0, 2))
    return 0


def main(argv):
    name = None
    if "--name" in argv:                        # the course's own path, for the messages (the text is a copy)
        i = argv.index("--name")
        name = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) >= 3 and argv[0] == "picture":
        return picture(argv[1], argv[2], name, "--gaps" in argv[3:])
    if len(argv) >= 3 and argv[0] == "ride":
        return ride(argv[1], int(argv[2]), name)
    if len(argv) >= 2 and argv[0] == "check":
        return check(argv[1], "--strict" in argv[2:], name)
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:                      # a crash is a result too: the window shows it
        emit(stage="done", ok=False, error="%s: %s" % (type(e).__name__, e))
        sys.exit(1)
