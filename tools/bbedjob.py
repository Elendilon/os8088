#!/usr/bin/env python3
"""bbedjob - THE COURSE BUILDER'S JOBS (SPEC.md 130.55.8), each run as a process
by tools/bbedit.py, reporting JSON lines on stdout and killed by Cancel or by
the next edit:

    python3 tools/bbedjob.py picture COURSE.bbc OUTDIR [--name PATH]   # the Iso view's picture
    python3 tools/bbedjob.py check   COURSE.bbc [--strict] [--name PATH] # the full check

Each line is a JSON object: {"stage": ..., "what": ...} while it works, then
{"stage": "done", "ok": true|false, ...}.

PICTURE compiles WITHOUT the occluder pass (fast) and with the part's block
limit lifted, because the picture is all it keeps: a course over the limit
still gets a picture to look at, and the CHECK says what is over. It writes
OUTDIR/cga.png, OUTDIR/herc.png, OUTDIR/owners.bin (the cell that drew each
pixel, 256 wx + wy or -1, int32 rows) and OUTDIR/meta.json (the size, the
origin, every mark the visibility audit weighs with its seen and hidden
pixels).

CHECK is bbcourse's compile_course: the errors that refuse the course and
the warnings that do not (SPEC.md 130.55.4).
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


def picture(path, out, name=None):
    from PIL import Image
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    path = name or path
    B.BLK_MAX = 1 << 30                         # the picture's alone: never a part that ships (130.55.8)
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
            "warnings": [{k: w[k] for k in ("kind", "msg", "line", "cell", "accepted")} for w in c.warnings],
            "secs": round(time.time() - t0, 2)}
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
    warns = [{k: w[k] for k in ("kind", "msg", "line", "cell", "accepted")} for w in c.warnings]
    emit(stage="done", ok=True, warnings=warns, secs=round(time.time() - t0, 1))
    return 0


def main(argv):
    name = None
    if "--name" in argv:                        # the course's own path, for the messages (the text is a copy)
        i = argv.index("--name")
        name = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) >= 3 and argv[0] == "picture":
        return picture(argv[1], argv[2], name)
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
