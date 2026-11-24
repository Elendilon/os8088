#!/usr/bin/env python3
"""SPEC.md 130.58.55: the Course tab keeps what was typed until it is applied. Drives the real window, so it needs
a Python with Tk and a display:  xvfb-run -a python3 tools/bbedcvtab.py  (exit 1 on a failure)"""
import os
import shutil
import sys
import tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = tempfile.mkdtemp(prefix="bbedcv")
for f in ("hop.bbc", "first.bbc"):
    shutil.copy(os.path.join(ROOT, "apps", "bonanza", "courses", f), OUT)
sys.path[:0] = [os.path.join(ROOT, "tools")]
os.environ["HOME"] = os.path.join(OUT, "home"); os.makedirs(os.environ["HOME"], exist_ok=True)
import bbedit as W
app = W.App(os.path.join(OUT, "hop.bbc")); r = app.root; r.update()
fails = []
def chk(what, cond):
    print(("ok   " if cond else "FAIL ") + what); cond or fails.append(what)
orig = app.cv_title.get()
app.cv_title.set("Typed Title"); app.cv_limit.set("77"); r.update()
chk("typing marks the tab not applied", app.cv_dirty and "not applied" in app.cv_note.cget("text"))
# an unrelated edit elsewhere in the course (a comment line appended, as any edit refills every tab)
app._edit(lambda: app.doc.insert("# an unrelated edit", after=len(app.doc.lines), label="test")); r.update()
chk("an unrelated edit keeps the typed title", app.cv_title.get() == "Typed Title" and app.cv_limit.get() == "77")
app.undo() if hasattr(app, "undo") else None; r.update()
chk("an undo keeps the typed title", app.cv_title.get() == "Typed Title")
app.save(); r.update()
txt = open(os.path.join(OUT, "hop.bbc")).read()
chk("Save applies the typed fields first", '"Typed Title"' in txt and "\nlimit 77" in txt)
chk("after Save the tab is clean", not app.cv_dirty and app.cv_note.cget("text") == "")
app.cv_title.set("Second"); r.update()
app.apply_course(); r.update()
chk("Apply writes the field and the tab is clean", '"Second"' in app.doc.text() and not app.cv_dirty)
app.cv_width.set("not-a-number"); r.update()
app.apply_course(); r.update()
chk("a refused Apply keeps what was typed, still not applied", app.cv_width.get() == "not-a-number" and app.cv_dirty)
app.cv_width.set("64"); app.apply_course(); r.update()
app.save(); r.update()
app.open(os.path.join(OUT, "first.bbc")); r.update()
chk("opening another course shows ITS settings", app.cv_title.get() != "Second" and not app.cv_dirty)
r.destroy()
print("FAILS", len(fails))
shutil.rmtree(OUT, ignore_errors=True)
sys.exit(1 if fails else 0)
