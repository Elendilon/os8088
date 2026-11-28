#!/usr/bin/env python3
"""bbedlayout - the course builder's CLIPPING AUDIT (SPEC.md 137.58.54).

    xvfb-run -s "-screen 0 1920x1080x24" python3 tools/bbedlayout.py [--geometry WxH] [--shots DIR]
                                                                       [--only PAGE] [--quick]

Opens tools/bbedit.py's window at a size (its own default when --geometry is not given), visits every page of
it - the Build tab with nothing selected, an area, the Add panel's choices, every statement kind's inspector
(one of each, found in apps/bonanza/courses/), several selected, the Iso view's rows with the occluder, gap and
kit overlays on, an occluder record, the fix bar and the banner - then the Course, Source, Map and Kit tabs, the
Map tab's two dialogs and Test Roll's window, and walks the widget tree on each, reporting:

  cut     a control whose requested width (its whole text or row) does not fit the room it has, on its own or
          inside every frame above it - the "Nor" of a Paint row's Normal
  hidden  a control packed or gridded into a frame that had no room left to map it at all
  text    a fixed-width button whose text is longer than its width

and, with --shots, a screenshot of each page. Exit status 1 when anything is clipped, so it can stand as a check.
Needs Tk and Pillow (Linux: python3-tk, python3-pil) and an X display: Xvfb is enough.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# controls whose content scrolls by design, so a request wider than the room is not a clip
SCROLLS = {"Canvas", "Treeview", "Text", "Scrollbar", "TScrollbar", "Listbox", "TProgressbar", "Menu",
           "TSeparator", "Separator"}
LEAVES = {"TLabel", "Label", "TButton", "Button", "TCheckbutton", "Checkbutton", "TRadiobutton", "Radiobutton",
          "TEntry", "Entry", "TSpinbox", "Spinbox", "TCombobox", "TScale", "Scale", "TMenubutton", "Menubutton"}
SLACK = 1


NAMES = {}                      # str(widget) -> the attribute that holds it ("app.ins_body"): where a clip is


def name_widgets(prefix, obj):
    for k, v in vars(obj).items():
        if hasattr(v, "winfo_id") and str(v) not in NAMES:
            NAMES[str(v)] = "%s.%s" % (prefix, k)


def _name(w):
    try:
        t = w.get() if w.winfo_class() in ("TCombobox", "TEntry", "TSpinbox", "Entry") else w.cget("text")
    except Exception:
        t = ""
    t = " ".join(str(t).split())
    return "%s %s%s" % (w.winfo_class(), w.winfo_name() if not t else "", repr(t[:48]) if t else "")


def _path(w):
    """a short trail of the frames above W that carry a text (a LabelFrame) or are named - where on the page"""
    out = []
    p = w.master
    while p is not None and p.master is not None:
        if str(p) in NAMES:
            out.append(NAMES[str(p)])
            if len(out) >= 2:
                break
            p = p.master
            continue
        try:
            t = p.cget("text")
            if t:
                out.append(str(t))
        except Exception:
            pass
        p = p.master
    return " > ".join(reversed(out))


def _clip(w):
    """the room W's ancestors leave it, in root coordinates: (right, bottom) - Tk clips a child to its parent;
    a frame inside a Canvas (the inspector) SCROLLS up and down, so the canvas bounds only its right"""
    r, b = 1 << 30, 1 << 30
    p = w.master
    scrolled = False
    while p is not None:
        try:
            r = min(r, p.winfo_rootx() + p.winfo_width())
            if p.winfo_class() == "Canvas":
                scrolled = True
            if not scrolled:
                b = min(b, p.winfo_rooty() + p.winfo_height())
        except Exception:
            break
        if p.winfo_class() == "Toplevel" or p.master is None:
            break
        p = p.master
    return r, b


def _font(w):
    import tkinter.font as tkfont
    try:
        f = w.cget("font")
    except Exception:
        f = ""
    if not f:
        try:
            from tkinter import ttk
            f = ttk.Style().lookup(w.winfo_class(), "font") or "TkDefaultFont"
        except Exception:
            f = "TkDefaultFont"
    try:
        return tkfont.nametofont(str(f))
    except Exception:
        return tkfont.Font(font=f)


def audit(top):
    """every clipped control under TOP (a Tk or Toplevel) as [(kind, where, what, by px)]"""
    found = []

    def walk(w):
        for c in w.winfo_children():
            cls = c.winfo_class()
            if cls == "Toplevel" or cls == "Menu":
                continue
            try:
                mgr = c.winfo_manager()
            except Exception:
                mgr = ""
            if not c.winfo_ismapped():
                if mgr in ("pack", "grid") and w.winfo_viewable() and cls not in SCROLLS:
                    found.append(("hidden", _path(c), _name(c), c.winfo_reqwidth()))
                continue
            if cls in ("Canvas", "Treeview", "Text", "Listbox") and mgr in ("pack", "grid") and \
                    c.winfo_width() < min(c.winfo_reqwidth(), 150) - SLACK:
                found.append(("squeezed", _path(c), _name(c), c.winfo_reqwidth() - c.winfo_width()))
            if cls in LEAVES:
                x, wd, rw = c.winfo_rootx(), c.winfo_width(), c.winfo_reqwidth()
                y, ht, rh = c.winfo_rooty(), c.winfo_height(), c.winfo_reqheight()
                cr, cb = _clip(c)
                vis_w = max(0, min(x + wd, cr) - x)
                vis_h = max(0, min(y + ht, cb) - y)
                if rw - vis_w > SLACK:
                    found.append(("cut", _path(c), _name(c), rw - vis_w))
                elif rh - vis_h > SLACK and vis_h < rh:
                    found.append(("cut-below", _path(c), _name(c), rh - vis_h))
                try:
                    width = int(str(c.cget("width")) or 0)
                    text = str(c.cget("text"))
                except Exception:
                    width, text = 0, ""
                if width > 0 and text and cls in ("TButton", "TLabel", "TCheckbutton", "TRadiobutton"):
                    f = _font(c)
                    if f.measure(text) > width * f.measure("0") + SLACK:
                        found.append(("text", _path(c), _name(c), f.measure(text) - width * f.measure("0")))
            if cls not in SCROLLS or cls == "Canvas":       # (a canvas holds the inspector: walked into)
                walk(c)

    walk(top)
    return found


class Runner(object):
    def __init__(self, geometry, shots, only):
        self.geometry, self.shots, self.only = geometry, shots, only
        self.results = []               # (page, [found])

    def settle(self, root, secs=0.3):
        t = time.time() + secs
        while time.time() < t:
            root.update()
            time.sleep(0.02)

    def page(self, name, top, root=None):
        if self.only and self.only not in name:
            return
        root = root or top
        self.settle(root)
        found = audit(top)
        self.results.append((name, found))
        if self.shots:
            os.makedirs(self.shots, exist_ok=True)
            fn = os.path.join(self.shots, "%s.png" % name)
            try:
                top.lift()
                self.settle(root, 0.2)
                subprocess.call(["import", "-window", str(top.winfo_id()) if top is not root else "root",
                                 "-crop", "%dx%d+%d+%d" % (top.winfo_width(), top.winfo_height(),
                                                           top.winfo_rootx(), top.winfo_rooty()), fn]
                                if top is root else ["import", "-window", str(top.winfo_id()), fn])
            except OSError:
                pass

    def report(self):
        n = 0
        for name, found in self.results:
            if not found:
                print("%-34s ok" % name)
                continue
            n += len(found)
            print("%-34s %d clipped" % (name, len(found)))
            for kind, where, what, by in found:
                print("    %-9s %-40s %4d px  %s" % (kind, what, by, where))
        print("%d pages, %d clipped controls at %s" % (len(self.results), n, self.geometry or "the default size"))
        return n


def kinds_index():
    """one statement of each (kind, subkind) out of the shipped courses: {(kind, sub): (path, line)}"""
    import bbedproj as E
    out = {}
    d = os.path.join(ROOT, "apps", "bonanza", "courses")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".bbc"):
            continue
        p = os.path.join(d, fn)
        try:
            doc = E.Document.load(p)
        except Exception:
            continue
        for st in doc.statements():
            if not st.kind:
                continue
            k = (st.kind, st.toks[1] if st.kind in ("prop", "surface", "tube") and len(st.toks) > 1 else None)
            extra = []
            if st.kind in ("floor", "wall", "hole", "goal"):
                for w in ("half", "quarter", "chamfer", "ramp"):
                    if w in st.toks:
                        extra.append(w)
            if st.kind == "prop" and st.subkind == "bridge" and "timer" in st.toks:
                extra.append("timer")
            k = k + tuple(extra)
            out.setdefault(k, (p, st.line))
    return out


def _keys(x):
    return sorted(x) if isinstance(x, dict) else range(len(x or ()))


def run_builder(rn, args):
    import bbedit as W
    import bbedproj as E
    app = W.App(None)
    r = app.root
    if args.geometry:
        r.geometry(args.geometry + "+0+0")
    else:
        r.geometry("+0+0")
    rn.settle(r, 1.0)
    for pre, o in (("app", app), ("occ", app.occ), ("kitv", app.kitv), ("map", app.map), ("kittab", app.kittab),
                   ("shapes", app.shapes)):
        name_widgets(pre, o)
    rn.page("build-empty", r)
    idx = kinds_index()
    mill = os.path.join(ROOT, "apps", "bonanza", "courses", "mill.bbc")
    app.open(mill)
    rn.settle(r, 0.5)
    rn.page("build-nothing-selected", r)

    def area(a, part=None):
        app.select(None)
        if part:
            for iid, it in app.pal_items.items():
                if it[0] == part:
                    app.pal.selection_set(iid)
                    app.pal.see(iid)
            r.update()
            app._pick_part()
        app.area = a
        app._fill_inspector()
        app._fill_add()
        app._redraw()

    area((3, 3, 5, 5))
    rn.page("build-area", r)
    for part in ("Half tile", "Quarter tile", "Cut a corner", "Diagonal strip", "Tube"):
        if any(it[0] == part for it in app.pal_items.values()):
            area((3, 3, 5, 5), part)
            rn.page("build-area-add-%s" % part.lower().replace(" ", "-"), r)
    area((3, 3, 5, 5), None)
    app.part = None
    app.pal.selection_set(())
    app._fill_add()

    cur = [None]
    for k in sorted(idx, key=lambda k: tuple(str(x) for x in k)):
        p, line = idx[k]
        name = "ins-" + "-".join(str(x) for x in k if x)
        if rn.only and rn.only not in name:
            continue
        if cur[0] != p:
            app.doc = E.Document.load(p)        # (no prompts, no picture: the inspector is what is audited)
            app.doc.listeners.append(app._changed)
            app.sel, app.sels, app.area = None, [], None
            cur[0] = p
        app.area = None
        try:
            app.select(line)
        except Exception as e:      # (a kind the window cannot show on this course is the window's problem)
            rn.results.append((name, [("error", "", repr(e)[:80], 0)]))
            continue
        rn.page(name, r)

    # several selected
    doc = app.doc
    lines = [st.line for st in doc.statements() if st.kind in ("floor", "wall")][:3]
    if len(lines) >= 2:
        app.select(lines[0])
        for ln in lines[1:]:
            app.select(ln, add=True)
        rn.page("ins-multi", r)
    app.select(None)

    # the fix bar: a problem picked
    app.doc = E.Document.load(mill)
    app.doc.listeners.append(app._changed)
    app.sel = None
    app._banner("The edit was refused: this is the banner's text, long enough to show how it wraps when a "
                "refusal names the statement, the line and what to do about it instead.", keep=True)
    rn.page("build-banner", r)
    app._banner(None)

    # Iso: its rows, and the overlays
    app.view.set("iso")
    app._view_changed()
    t = time.time() + 120
    while time.time() < t and (app.pic is None or (app.pic_job and app.pic_job.running)):
        rn.settle(r, 0.5)
    rn.page("iso", r)
    app.show_gaps.set(True)
    app._gaps_toggled()
    rn.settle(r, 2)
    rn.page("iso-gaps", r)
    app.occ.show.set(True)
    app.occ.toggled()
    t = time.time() + 240
    while time.time() < t and (app.pic_job and app.pic_job.running or app.occ.data is None):
        rn.settle(r, 0.5)
    rn.page("iso-occluders", r)
    if app.occ.data is not None and app.occ.recs():
        app.occ.sel = ("rec", 0)
        app.select(None)
        app.area = None
        app._fill_inspector()
        rn.page("ins-occluder-record", r)
        app.occ.sel = ("recs", frozenset(range(min(3, len(app.occ.recs())))))
        app._fill_inspector()
        rn.page("ins-occluder-records", r)
        app.occ.sel = ("noocc", (3, 3))
        app._fill_inspector()
        rn.page("ins-noocclude", r)
        app.occ.sel = None
    app.occ.show.set(False)
    app.occ.toggled()
    app.kitv.show.set(True)
    app.kitv.toggled()
    t = time.time() + 180
    while time.time() < t and (app.pic_job and app.pic_job.running or app.kitv.data is None):
        rn.settle(r, 0.5)
    rn.page("iso-kit", r)
    app.kitv.show.set(False)
    app.kitv.toggled()
    app.show_gaps.set(False)
    app._gaps_toggled()
    app.view.set("plan")
    app._view_changed()

    # the problems list and its fix bar
    rn.settle(r, 1)
    kids = app.probs.get_children()
    if kids:
        app.probs.selection_set(kids[0])
        app._pick_problem()
        rn.page("build-problem-picked", r)

    # the other tabs
    for tab in app.nb.tabs():
        text = app.nb.tab(tab, "text")
        if text == "Build":
            continue
        app.nb.select(tab)
        rn.settle(r, 1.0)
        if text == "Kit":
            t = time.time() + 120
            while time.time() < t and app.kittab.job is not None and app.kittab.job.running:
                rn.settle(r, 0.5)
        rn.page("tab-%s" % text.lower(), r)
        if text == "Kit" and app.kittab.hits:
            app.kittab.select(app.kittab.hits[0][4])
            rn.page("tab-kit-piece", r)
    # the Map tab on the pathway itself, and its two dialogs
    path = os.path.join(ROOT, "apps", "bonanza", "courses", "path.bbc")
    app.open(path)
    rn.settle(r, 1.0)
    for tab in app.nb.tabs():
        if app.nb.tab(tab, "text") == "Map":
            app.nb.select(tab)
    t = time.time() + 120
    while time.time() < t and not app.map.m:
        rn.settle(r, 0.5)
    rn.settle(r, 2.0)
    rn.page("tab-map-pathway", r)
    if app.map.m:
        for fn, nm in ((app.map.new_route_dialog, "dialog-new-route"), (app.map.put_course, "dialog-put-course")):
            before = set(r.winfo_children())
            fn()
            rn.settle(r, 0.5)
            for d in set(r.winfo_children()) - before:
                if d.winfo_class() == "Toplevel":
                    rn.page(nm, d, r)
                    d.destroy()
        m = app.map.m
        sels = [("pad", n) for n in sorted(m.get("pads", {}))[:1]] + [("route", 0)] * bool(m.get("routes")) + \
            [(k, i) for k, mk in (("icon", "icons"), ("lives", "lives")) for i in list(_keys(m.get(mk)))[:1]] + \
            [("map",)]
        for sel in sels:
            app.map.sel = sel
            try:
                app.map.refresh()
            except Exception as e:
                rn.results.append(("tab-map-" + sel[0], [("error", "", repr(e)[:80], 0)]))
                continue
            rn.page("tab-map-" + sel[0], r)
    app.nb.select(0)
    app.pbar.stop()
    app.cancel_jobs()
    rn.settle(r, 0.3)
    r.destroy()


def run_play(rn, args):
    import bbplay as P
    pl = P.Player(os.path.join(ROOT, "apps", "bonanza", "courses", "first.bbc"), None, None, None, False, False,
                  None)
    r = pl.r
    if args.geometry:
        r.geometry("+0+0")
    t = time.time() + 60
    while time.time() < t and pl.roll is None:
        rn.settle(r, 0.5)
    rn.page("test-roll", r)
    for j in (pl.jplay, pl.jfull):
        try:
            j.p.kill()
        except Exception:
            pass
    r.destroy()


def main(argv):
    ap = argparse.ArgumentParser(prog="bbedlayout.py", description=__doc__.split("\n")[0])
    ap.add_argument("--geometry", help="the window's size, WxH (default: the builder's own default)")
    ap.add_argument("--shots", help="a screenshot of each page into this directory")
    ap.add_argument("--only", help="only the pages whose name holds this")
    a = ap.parse_args(argv)
    home = tempfile.mkdtemp(prefix="bbedlayout")
    os.environ["HOME"] = home               # (the builder's own config, so the default size is the default)
    rn = Runner(a.geometry, a.shots, a.only)
    try:
        run_builder(rn, a)
        if not a.only or a.only in "test-roll":
            run_play(rn, a)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    return 1 if rn.report() else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
