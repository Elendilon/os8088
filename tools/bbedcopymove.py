#!/usr/bin/env python3
"""SPEC.md 130.58.57: several parts dragged together on the plan, Ctrl+C / Ctrl+X / Ctrl+V, and the whole course
moved over when an addition reaches the grid's edge - driven through the REAL window (the canvas's own press,
motion and release; the keys sent to it; the pointer warped over the plan), so it needs a Python with Tk and a
display:

    xvfb-run -a python3 tools/bbedcopymove.py [--shots DIR]      (exit 1 on a failure)

--shots writes a screenshot of the multi-drag's preview and of a paste (ImageMagick's `import`)."""
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = tempfile.mkdtemp(prefix="bbedcm")
shutil.copy(os.path.join(ROOT, "apps", "bonanza", "courses", "first.bbc"), OUT)
sys.path[:0] = [os.path.join(ROOT, "tools")]
os.environ["HOME"] = os.path.join(OUT, "home")
os.makedirs(os.environ["HOME"], exist_ok=True)
import bbedit as W  # noqa: E402

SHOTS = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
app = W.App(os.path.join(OUT, "first.bbc"))
r = app.root
r.geometry("1366x768")
fails = []


def chk(what, cond):
    print(("ok   " if cond else "FAIL ") + what)
    cond or fails.append(what)


def settle(secs=0.3):
    t = time.time() + secs
    while time.time() < t:
        r.update()
        time.sleep(0.02)


def shot(name):
    if not SHOTS:
        return
    os.makedirs(SHOTS, exist_ok=True)
    settle(0.3)
    subprocess.call(["import", "-window", "root", "-crop", "%dx%d+%d+%d" % (
        r.winfo_width(), r.winfo_height(), r.winfo_rootx(), r.winfo_rooty()), os.path.join(SHOTS, name)])


def line_of(code):
    return next((s.line for s in app.doc.statements() if " ".join(s.toks) == code), None)


def norm():
    """the course's statements, one space between words"""
    return "\n".join(" ".join(s.toks) for s in app.doc.statements()) + "\n"


def at(cell):
    """the canvas pixel at the middle of a plan cell"""
    x, y = app._cpx(cell[0] + .5, cell[1] + .5)
    c = app.cv
    return int(x - c.canvasx(0)), int(y - c.canvasy(0))


def drag(a, b, mid=None):
    c = app.cv
    c.focus_force()
    x, y = at(a)
    c.event_generate("<Button-1>", x=x, y=y)
    settle(0.05)
    x, y = at(b)
    c.event_generate("<B1-Motion>", x=x, y=y, state=0x100)
    settle(0.2)
    if mid:
        mid()
    c.event_generate("<ButtonRelease-1>", x=x, y=y)
    settle(0.2)


def key(seq, over=None):
    c = app.cv
    c.focus_force()
    if over is not None:
        x, y = at(over)
        c.event_generate("<Motion>", warp=True, x=x, y=y)
    else:                                       # (the pointer off the plan: over the toolbar)
        r.event_generate("<Motion>", warp=True, x=10, y=10)
    settle(0.1)
    c.event_generate(seq)
    settle(0.2)


settle(0.8)
app.view.set("plan")
app._fit()
settle(0.3)
t0 = app.doc.text()

# 1. several selected (Ctrl-click's selection) dragged together, with a live preview, as ONE undo step
la, lb, lh = line_of("clock 3 6"), line_of("clock 11 4"), line_of("hole tile 12 5")
app.select(la)
app.select(lb, add=True)
app.select(lh, add=True)
settle()
chk("three parts selected", sorted(app.sels) == sorted([la, lb, lh]))
n0 = len(app.doc.undo_stack)
seen = {}


def preview():
    items = [i for i in app.cv.find_all() if app.cv.type(i) == "rectangle"
             and app.cv.itemcget(i, "outline") == "#ffd54f" and app.cv.itemcget(i, "width") in ("2", "2.0")]
    seen["n"] = len(items)
    shot("multi-drag.png")


drag((3, 6), (4, 6), preview)
chk("the drag draws every selected part where it will land (%d preview cells)" % seen.get("n", 0),
    seen.get("n", 0) >= 2)
txt = norm()
chk("all three moved one cell along x", "clock 4 6" in txt and "clock 12 4" in txt and "hole tile 13 5" in txt
    and "clock 3 6" not in txt)
chk("one undo step for the move", len(app.doc.undo_stack) == n0 + 1)
chk("the moved parts stay selected", len(app.sels) == 3 and all(
 " ".join(app.doc.statement(ln).toks) in ("clock 4 6", "clock 12 4", "hole tile 13 5") for ln in app.sels))
app.undo()
settle()
chk("one Undo takes the move back", app.doc.text() == t0)

# 2. a drag the course refuses is undone, the banner says why
app.select(line_of("clock 3 6"))
app.select(line_of("clock 11 4"), add=True)
settle()
drag((3, 6), (3, 3))                            # a clock onto the back wall, the other into the void
chk("a refused multi-drag leaves the course as it was", app.doc.text() == t0)
chk("...and the banner says why", bool(app.banner.winfo_ismapped()) and "undone" in app.banner_l.cget("text"))
app._banner(None)

# 3. Ctrl+C, then Ctrl+V with the pointer OFF the plan: one cell over (diagonally), the pasted set selected
app.select(line_of("floor rect 3 4 7 7 flat 4"))
app.select(line_of("clock 3 6"), add=True)
settle()
key("<Control-c>")
clip = ""
try:
    clip = r.clipboard_get()
except Exception:
    pass
chk("Ctrl+C puts course text on the system clipboard", "floor rect 3 4 7 7 flat 4" in clip and "clock 3 6" in clip)
n0 = len(app.doc.undo_stack)
key("<Control-v>")
txt = norm()
chk("Ctrl+V pastes them one cell over", "floor rect 4 5 8 8 flat 4" in txt and "clock 4 7" in txt)
chk("one undo step for the paste", len(app.doc.undo_stack) == n0 + 1)
chk("the pasted set is selected", sorted(" ".join(app.doc.statement(ln).toks) for ln in app.sels) ==
    ["clock 4 7", "floor rect 4 5 8 8 flat 4"])
shot("paste.png")
# ... and the pasted set dragged at once
drag((4, 7), (5, 7))
txt = norm()
chk("the pasted set drags together", "clock 5 7" in txt and "floor rect 5 5 9 8 flat 4" in txt)
while app.doc.undo_stack:
    app.doc.undo()
settle()

# 4. Ctrl+V with the pointer over the plan, reaching past the grid's edge: the WHOLE course moves over
app.select(line_of("floor rect 11 4 14 7 flat 0"))
key("<Control-c>")
n0 = len(app.doc.undo_stack)
# the plan's left edge is the course's least x less 6: cell (1, 4) is over the plan, past the grid's 3
key("<Control-v>", over=(1, 4))
txt = norm()
moved = getattr(app.doc, "last_shift", None)
chk("a paste past the edge moved the whole course over (by %r)" % (moved,), moved is not None and moved[0] >= 2)
chk("...as one undo step with the paste", len(app.doc.undo_stack) == n0 + 1)
if moved:
    dx, dy = moved
    chk("...every part with it (the start, the route, the clocks)", "start %d %d" % (4 + dx, 5 + dy) in txt
        and "way %d %d" % (13 + dx, 4 + dy) in txt and "clock %d %d" % (3 + dx, 6 + dy) in txt)
    chk("...the picture's origin moved back so the picture is the same", "origin %d" % (256 - 16 * (dx - dy)) in txt)
chk("...and the status line says so", "moved the whole course" in app._status_full)
chk("...and the course is not refused", not app.doc.analysis()["error"])
shot("paste-shifted.png")
app.undo()
settle()
chk("one Undo takes the paste and the shift back", app.doc.text() == t0)

# 5. Ctrl+X cuts; the start is not copied
app.select(line_of("clock 11 4"))
key("<Control-x>")
chk("Ctrl+X takes the clock out and onto the clipboard", "clock 11 4" not in norm() and
    "clock 11 4" in (app.clip or ""))
app.undo()
app.select(line_of("start 4 5"))
app.select(line_of("clock 3 6"), add=True)
key("<Control-c>")
chk("copying the start leaves it out and says so", app.clip == "clock 3 6\n" and "start" in app._status_full)

# 6. a field's own Ctrl+C is the field's: the course's clipboard is left alone
app.nb.select(2)                                # the Source tab
settle()
before = app.clip
app.src_t.focus_force()
app.src_t.event_generate("<Control-c>")
settle(0.1)
chk("Ctrl+C in the Source tab's text is the text's own", app.clip == before)
app.nb.select(0)

r.destroy()
print("FAILS", len(fails))
shutil.rmtree(OUT, ignore_errors=True)
sys.exit(1 if fails else 0)
