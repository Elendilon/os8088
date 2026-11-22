#!/usr/bin/env python3
"""bbedit - THE BOUNCE BONANZA COURSE BUILDER (SPEC.md 130.58).

    python3 tools/bbedit.py [COURSE.bbc]

A window over tools/bbedproj.py's Document: the course is its .bbc text, and
every edit rewrites only the lines it is about (comments and order are kept).
Two views of one selection - PLAN, top-down with a height map, and ISO, the
game's own picture out of tools/bbcourse.py - and the compiler as the only
judge: its refusals are ERRORS, its visual checks WARNINGS (SPEC.md 130.58.4).
Slow work (the picture, the full check) runs as a process (tools/bbedjob.py)
that the next edit cancels.

Needs Tk and Pillow (macOS: python.org's Python, `pip install pillow`;
Windows: `pip install pillow`; Linux: python3-tk and python3-pil).
"""

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbedproj as E  # noqa: E402
import bbcourse as B  # noqa: E402
import bbedshape  # noqa: E402
import bbedmap  # noqa: E402

TITLE = "Bounce Bonanza course builder"
CONFIG = os.path.join(os.path.expanduser("~"), ".config", "os8088", "bbedit.json")
CELL = 24                       # a plan cell at zoom 1, screen px

# ----------------------------------------------------------------------------
# the palette: every part, its group, plain name, what it does, its template
# ({x} {y}: the clicked cell; {x0} {y0} {x1} {y1}: a dragged rectangle; {h}: the toolbar's height)
# ----------------------------------------------------------------------------

PALETTE = [
    ("Ground", [
        ("Floor", "rect", "floor rect {x0} {y0} {x1} {y1} flat {h}", "Solid flat ground, at the height of the "
         "floor already there or beside it (the toolbar's height in empty space). Make it a ramp on the right"),
        ("Ramp", "rect", "floor rect {x0} {y0} {x1} {y1} ramp x {x0} {x1} {h} {h1}", "A floor that rises one unit "
         "across the area's longer side, half a unit a tile; change its direction and heights on the right"),
        ("Wall", "rect", "wall rect {x0} {y0} {x1} {y1} flat {h}", "A block the ball cannot cross: one unit "
         "above the floor it stands on, or in an empty gap above the lowest floor beside it (a wall need only "
         "stand above what it walls off; a higher floor beside it ends at its edge)"),
        ("Hole", "rect", "hole rect {x0} {y0} {x1} {y1}", "Open void: the ball falls"),
        ("Goal", "rect", "goal rect {x0} {y0} {x1} {y1} flat {h}", "Finish floor"),

        ("Guard rail", "rect", "guard rect {x0} {y0} {x1} {y1}", "A rail on the open edge beside a floor"),
        ("Water", "cell", "water tile {x} {y} top {h} bed 0", "A pool: a surface and a bed"),
        ("Waterfall face", "cell", "arch {x} {y} +x", "The face a water column spills from"),
        ("Hump", "cell", "hump {x} {y} {h}", "A rounded bump (the Shapes tab edits it)"),
        ("Archway", "rect", "archway tile {x} {y} along x", "A ceiling over a path: select the path (1 or 2 "
         "cells wide, with empty space on both sides for its legs)"),
        ("Chute", "cell", "chute 1 round depth 5 way {x} {y} {h} way {x4} {y}", "A curved channel"),
        ("Pit", "cell", "pit {x} {y} {h} radius 3 depth 16", "A bowl to ride round at speed"),
    ]),
    ("Surface", [
        ("Ice", "rect", "surface ice rect {x0} {y0} {x1} {y1}", "Slippery: keeps speed, steers badly"),
        ("Sand", "rect", "surface sand rect {x0} {y0} {x1} {y1}", "Drags the ball to a stop"),
        ("Bounce mat", "rect", "surface bounce rect {x0} {y0} {x1} {y1}", "Springy: landings bounce high"),
        ("Normal", "rect", "surface normal rect {x0} {y0} {x1} {y1}", "Ordinary grip"),
    ]),
    ("Movers", [
        ("Windmill", "cell", "prop windmill {x} {y}", "Turning blades (over a KEEP tube's mouth)"),
        ("Bumper", "cell", "prop bumper {x} {y}", "A post that kicks the ball away"),
        ("Lift", "cell", "prop platform {x} {y} 4", "A platform that rises and falls (in a void shaft)"),
        ("Turntable", "cell", "prop turntable {x} {y} size 2 fill oo/..", "A spinning disc"),
        ("Seesaw", "rect", "seesaw {x0} {y0} {x1} {y1} along x pivot 3", "A plank the ball's weight tips"),
        ("Bridge", "rect", "prop bridge {x0} {y0} {x1} {y1} period 256 on 128", "A floor on a timer"),
    ]),
    ("Launch", [
        ("Spring", "cell", "spring {x} {y} 768", "Fires the ball straight up"),
        ("Tube (keep)", "cell", "tube keep {x} {y} {x3} {y}", "In one mouth, out the other (body in a wall)"),
        ("Tube (launch)", "cell", "tube launch {x} {y} {x3} {y} speed -192 192 480", "Fires the ball out"),
        ("Tube (drop)", "cell", "tube drop {x} {y} {x3} {y} out +x height 3", "Drops the ball out"),
        ("Boost pad", "cell", "prop boost {x} {y} face +x", "A shove the way its arrows point"),
        ("Blower", "cell", "prop blower {x} {y} face +y region {x} {y1b} {x4} {y3} strength 8", "A fan over a region"),
        ("Magnet", "cell", "prop magnet {x} {y} face -x range 4 strength 48", "Pulls the ball in"),
    ]),
    ("Hazards", [
        ("Spikes", "rect", "prop spikes {x0} {y0} {x1} {y1}", "Pop rubber and glass; steel rolls over"),
        ("Pop-up spikes", "cell", "prop popspikes {x} {y} period 128 on 64", "Spikes on a timer"),
        ("Membrane", "rect", "prop membrane {x0} {y0} {x1} {y1}", "Only glass crosses it"),
        ("Cracked floor", "cell", "prop crack {x} {y}", "Breaks under the ball"),
        ("Glass path", "cell", "prop glass {x} {y}", "Solid, unseen until touched"),
    ]),
    ("Pickups", [
        ("Hourglass", "cell", "prop hourglass {x} {y}", "+10 seconds, once a try"),
        ("Speed", "cell", "prop speed {x} {y} for 3", "Faster for a few seconds"),
        ("Jump", "cell", "prop jump {x} {y} for 3", "A higher hop for a few seconds"),
        ("Life", "cell", "prop life {x} {y}", "A heart: one more life for the game. `Once` keeps it taken for good "
         "(one a course)"),
    ]),
    ("Game", [
        ("Start", "cell", "start {x} {y}", "Where the ball appears (one a course)"),
        ("Route point", "cell", "way {x} {y}", "The route the checks and autopilot follow"),
        ("Flag", "cell", "checkpoint {x} {y}", "A checkpoint; a fall returns here"),
        ("Ball pad: rubber", "cell", "pad rubber {x} {y}", "Swaps the ball"),
        ("Ball pad: steel", "cell", "pad steel {x} {y}", "Swaps the ball"),
        ("Ball pad: glass", "cell", "pad glass {x} {y}", "Swaps the ball"),
        ("Goal tile", "cell", "goal tile {x} {y} flat {h}", "One finish cell"),
        ("Cup", "cell", "cup {x} {y}", "A hole to drop into to finish"),
        ("Clock", "cell", "clock {x} {y}", "The time, on the course"),
        ("Gate", "cell", "prop gate {x} {y} channel ring along x", "Opened by its channel's plate or key"),
        ("Pressure plate", "cell", "prop plate {x} {y} channel ring", "Opens its channel while pressed"),
        ("Key", "cell", "prop key {x} {y} channel ring", "Opens its channel for good"),
    ]),
]

GLYPH = {"Windmill": "W", "Bumper": "B", "Lift": "L", "Turntable": "T", "Start": "S", "Route point": "·",
         "Flag": "F", "Ball pad": "P", "Cup": "U", "Clock": "C", "Tube": "", "Spring": "Sp", "Boost": "»",
         "Blower": "~", "Magnet": "M", "Spikes": "^", "Pop-up spikes": "^", "Membrane": "=", "Cracked floor": "x",
         "Glass path": "g", "Hourglass": "H", "Speed": ">", "Jump": "J", "Life": "♥", "Gate": "G", "Pressure plate": "_",
         "Key": "K", "Bridge": "#", "Seesaw": "/", "Probe": "?"}

# a height (units) to a colour: dark blue low, through green and yellow, to pale high
RAMP = [(-8, (38, 52, 110)), (0, (42, 110, 150)), (4, (64, 160, 120)), (10, (150, 200, 80)),
        (18, (235, 205, 80)), (30, (250, 236, 200)), (60, (255, 250, 240))]


def hcolour(h):
    for i in range(1, len(RAMP)):
        if h <= RAMP[i][0]:
            (a, ca), (b, cb) = RAMP[i - 1], RAMP[i]
            f = max(0.0, (h - a) / float(b - a))
            return "#%02x%02x%02x" % tuple(int(ca[k] + (cb[k] - ca[k]) * f) for k in range(3))
    return "#%02x%02x%02x" % RAMP[-1][1]


def load_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        with open(CONFIG, "w") as f:
            json.dump(cfg, f, indent=1)
    except OSError:
        pass


# ----------------------------------------------------------------------------
# jobs: a tools/bbedjob.py process, its JSON lines, a kill that takes the group
# ----------------------------------------------------------------------------

class Job(object):
    def __init__(self, argv, on_event):
        self.argv = [sys.executable, "-u", os.path.join(HERE, "bbedjob.py")] + list(argv)
        self.on_event = on_event
        self.p = None
        self.killed = False
        self.q = queue.Queue()

    def start(self):
        kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                  encoding="utf-8", errors="replace", bufsize=1)
        if sys.platform == "win32":
            kw["creationflags"] = 0x00000200 | 0x08000000      # a new group, no console window
        else:
            kw["start_new_session"] = True
        self.p = subprocess.Popen(self.argv, **kw)
        threading.Thread(target=self._read, daemon=True).start()
        return self

    def _read(self):
        for line in self.p.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                ev = {"stage": "log", "what": line.rstrip()}
            self.q.put(ev)
        self.p.wait()
        self.q.put({"stage": "exit", "code": self.p.returncode})

    def poll(self):
        while True:
            try:
                ev = self.q.get_nowait()
            except queue.Empty:
                return
            if not self.killed:
                self.on_event(self, ev)

    def kill(self):
        self.killed = True
        if self.p and self.p.poll() is None:
            try:
                if sys.platform == "win32":
                    self.p.kill()
                else:
                    os.killpg(self.p.pid, 9)
            except OSError:
                pass

    @property
    def running(self):
        return self.p is not None and self.p.poll() is None


# ----------------------------------------------------------------------------
# the window
# ----------------------------------------------------------------------------

class App(object):
    def __init__(self, path=None):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.root = tk.Tk()
        self.root.title(TITLE)
        self.cfg = load_config()
        self.root.geometry(self.cfg.get("geometry", "1400x860"))
        self.doc = E.Document("")
        self.sel = None                 # the selected statement's line
        self.zoom = 1.0
        self.tool = tk.StringVar(value="select")
        self.view = tk.StringVar(value="plan")
        self.height = tk.StringVar(value="4")
        self.show_heights = tk.BooleanVar(value=True)
        self.show_route = tk.BooleanVar(value=True)
        self.show_hard = tk.BooleanVar(value=True)
        self.xray = tk.BooleanVar(value=True)
        self.show_gaps = tk.BooleanVar(value=False)   # the gap band's candidates on the Iso view (130.58.21)
        self.gap_min = tk.IntVar(value=4)             # ... with at least this many feet (or marked)
        self.adapter = tk.StringVar(value="cga")
        self.strict = tk.BooleanVar(value=False)
        self.part = None                # the palette entry chosen: (name, mode, template, hint)
        self.area = None                # the selected AREA, cells (x0, y0, x1, y1) inclusive
        self.sels = []                  # Ctrl-click's MULTI-selection: lines (self.sel the last one)
        self.drag = None
        self.good = None                # the last analysis that laid out (shown while one does not)
        self.keep = None                # the edit "Keep it anyway" re-does
        self.tmp = tempfile.mkdtemp(prefix="bbedit-")
        self.pic = None                 # the Iso picture: {meta, img_cga, img_herc, owners}
        self.pic_job = self.check_job = None
        self.pic_after = self.check_after = None
        self.check = None               # the last full check's result
        self.photo = None
        self._build_ui()
        self.doc.listeners.append(self._changed)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.bind("<FocusIn>", self._focus)
        self.root.after(100, self._tick)
        if path:
            self.open(path)
        else:
            self._redraw()

    # -- layout -----------------------------------------------------------
    def _build_ui(self):
        tk, ttk = self.tk, self.ttk
        r = self.root
        style = ttk.Style()
        if "clam" in style.theme_names() and sys.platform.startswith("linux"):
            style.theme_use("clam")
        mb = tk.Menu(r)
        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="New course", command=self.new, accelerator="Ctrl+N")
        fm.add_command(label="Open...", command=self.open_dialog, accelerator="Ctrl+O")
        self.recent_menu = tk.Menu(fm, tearoff=0)
        fm.add_cascade(label="Open recent", menu=self.recent_menu)
        fm.add_command(label="Save", command=self.save, accelerator="Ctrl+S")
        fm.add_command(label="Save as...", command=self.save_as)
        fm.add_command(label="Reload from disk", command=self.reload)
        fm.add_separator()
        fm.add_command(label="Quit", command=self.quit)
        mb.add_cascade(label="File", menu=fm)
        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        em.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        em.add_separator()
        em.add_command(label="Duplicate", command=self.duplicate, accelerator="Ctrl+D")
        em.add_command(label="Delete", command=self.delete, accelerator="Del")
        mb.add_cascade(label="Edit", menu=em)
        vm = tk.Menu(mb, tearoff=0)
        vm.add_radiobutton(label="Plan", variable=self.view, value="plan", command=self._redraw)
        vm.add_radiobutton(label="Iso", variable=self.view, value="iso", command=self._redraw)
        vm.add_separator()
        vm.add_checkbutton(label="Height map", variable=self.show_heights, command=self._redraw)
        vm.add_checkbutton(label="Route", variable=self.show_route, command=self._redraw)
        vm.add_checkbutton(label="Hard to see", variable=self.show_hard, command=self._redraw)
        vm.add_separator()
        vm.add_command(label="Zoom in", command=lambda: self.set_zoom(self.zoom * 1.25), accelerator="+")
        vm.add_command(label="Zoom out", command=lambda: self.set_zoom(self.zoom / 1.25), accelerator="-")
        mb.add_cascade(label="View", menu=vm)
        cm = tk.Menu(mb, tearoff=0)
        cm.add_command(label="Check now", command=self.run_check)
        cm.add_checkbutton(label="Treat warnings as errors (--strict)", variable=self.strict,
                           command=self.run_check)
        mb.add_cascade(label="Course", menu=cm)
        r.config(menu=mb)
        for k, fn in (("<Control-n>", self.new), ("<Control-o>", self.open_dialog), ("<Control-s>", self.save),
                      ("<Control-z>", self.undo), ("<Control-y>", self.redo), ("<Control-d>", self.duplicate),
                      ("<Command-z>", self.undo), ("<Command-s>", self.save)):
            try:
                r.bind_all(k, lambda e, fn=fn: (fn(), "break")[1])
            except tk.TclError:
                pass

        # toolbar
        tb = ttk.Frame(r, padding=(6, 4))
        tb.pack(side="top", fill="x")
        ttk.Button(tb, text="Open...", command=self.open_dialog).pack(side="left")
        ttk.Button(tb, text="Save", command=self.save).pack(side="left", padx=(2, 8))
        ttk.Button(tb, text="Undo", command=self.undo).pack(side="left")
        ttk.Button(tb, text="Redo", command=self.redo).pack(side="left", padx=(2, 8))
        ttk.Button(tb, text="Test Roll", command=self.test_roll).pack(side="left", padx=(0, 8))
        self.badge_err = ttk.Label(tb, text="", foreground="#b3261e")
        self.badge_err.pack(side="right", padx=4)
        self.badge_warn = ttk.Label(tb, text="", foreground="#8a6d00")
        self.badge_warn.pack(side="right", padx=4)

        # status bar
        sb = ttk.Frame(r, padding=(6, 2))
        sb.pack(side="bottom", fill="x")
        self.status = ttk.Label(sb, text="Open a course (File > Open) or start a new one.")
        self.status.pack(side="left")
        self.cancel_b = ttk.Button(sb, text="Cancel", command=self.cancel_jobs)
        self.cancel_b.pack(side="right")
        self.job_l = ttk.Label(sb, text="")
        self.job_l.pack(side="right", padx=8)
        self.pbar = ttk.Progressbar(sb, mode="indeterminate", length=140)
        self.pbar.pack(side="right")

        self.nb = ttk.Notebook(r)
        self.nb.pack(side="top", fill="both", expand=True)
        self._build_build_tab()
        self._build_course_tab()
        self._build_source_tab()
        self.shapes = bbedshape.ShapesTab(self, self.nb, self.tk, self.ttk, Job, hcolour)   # SPEC.md 130.58.19
        self.map = bbedmap.MapTab(self, self.nb, self.tk, self.ttk, _photo)                  # SPEC.md 130.58.20
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._tab_changed())

    def _build_build_tab(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="Build")
        pw = ttk.PanedWindow(f, orient="horizontal")
        pw.pack(fill="both", expand=True)

        # palette
        left = ttk.Frame(pw, padding=6, width=240)
        self.find = tk.StringVar()
        e = ttk.Entry(left, textvariable=self.find)
        e.pack(fill="x")
        e.insert(0, "")
        self.find.trace_add("write", lambda *a: self._fill_palette())
        ttk.Label(left, text="Find a part", foreground="#666").pack(anchor="w")
        self.pal = ttk.Treeview(left, show="tree", selectmode="browse", height=10)
        self.pal.pack(fill="both", expand=True, pady=4)
        self.pal.bind("<<TreeviewSelect>>", lambda e: self._pick_part())
        self.pal.bind("<Double-Button-1>", lambda e: self.add_part())
        addf = ttk.LabelFrame(left, text="Add", padding=6)
        addf.pack(fill="x")
        self.add_name = ttk.Label(addf, text="Choose a part above", font=("TkDefaultFont", 11, "bold"))
        self.add_name.pack(anchor="w")
        self.add_desc = ttk.Label(addf, text="", wraplength=220, foreground="#444")
        self.add_desc.pack(anchor="w")
        self.add_btn = ttk.Button(addf, text="Add to the selection", command=self.add_part)
        self.add_btn.pack(fill="x", pady=(6, 2))
        self.add_where = ttk.Label(addf, text="", wraplength=220, foreground="#666")
        self.add_where.pack(anchor="w")
        pw.add(left, weight=0)

        # view
        mid = ttk.Frame(pw)
        vb = ttk.Frame(mid, padding=(4, 4))
        vb.pack(side="top", fill="x")
        for txt, v in (("Plan", "plan"), ("Iso", "iso")):
            ttk.Radiobutton(vb, text=txt, variable=self.view, value=v, command=self._view_changed).pack(side="left")
        ttk.Label(vb, text="  (Tab)").pack(side="left")
        ttk.Separator(vb, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Radiobutton(vb, text="Select", variable=self.tool, value="select",
                        command=self._tool_changed).pack(side="left")
        ttk.Radiobutton(vb, text="Erase", variable=self.tool, value="erase",
                        command=self._tool_changed).pack(side="left")
        ttk.Label(vb, text="   New floor height").pack(side="left")
        ttk.Spinbox(vb, from_=-20, to=60, increment=0.5, width=5, textvariable=self.height).pack(side="left")
        self.plan_opts = ttk.Frame(vb)
        self.plan_opts.pack(side="right")
        for txt, v in (("Height map", self.show_heights), ("Route", self.show_route), ("Hard to see", self.show_hard)):
            ttk.Checkbutton(self.plan_opts, text=txt, variable=v, command=self._redraw).pack(side="left")
        self.iso_opts = ttk.Frame(vb)
        for txt, v in (("CGA", "cga"), ("Hercules", "herc")):
            ttk.Radiobutton(self.iso_opts, text=txt, variable=self.adapter, value=v,
                            command=self._redraw).pack(side="left")
        ttk.Checkbutton(self.iso_opts, text="X-ray the selection", variable=self.xray,
                        command=self._redraw).pack(side="left", padx=6)
        # the gap band's row (SPEC.md 130.58.21): the Iso view's alone, under the toolbar
        self.gap_row = ttk.Frame(mid, padding=(4, 0, 4, 4))
        ttk.Checkbutton(self.gap_row, text="Gap bands", variable=self.show_gaps,
                        command=self._gaps_toggled).pack(side="left")
        ttk.Label(self.gap_row, text="  show places at least").pack(side="left")
        ttk.Spinbox(self.gap_row, from_=1, to=60, width=3, textvariable=self.gap_min,
                    command=self._redraw).pack(side="left")
        ttk.Label(self.gap_row, text="px wide").pack(side="left")
        self.gap_l = ttk.Label(self.gap_row, text="", foreground="#0b6b80")
        self.gap_l.pack(side="left", padx=10)
        self.gap_row_after = vb
        self.banner = tk.Frame(mid, background="#fde2df", padx=8, pady=6)
        self.banner_l = tk.Label(self.banner, text="", background="#fde2df", foreground="#5c1510",
                                 justify="left", anchor="w", wraplength=700)
        self.banner_l.pack(side="left", fill="x", expand=True)
        tk.Button(self.banner, text="Dismiss", command=lambda: self._banner(None)).pack(side="right")
        self.banner_keep = tk.Button(self.banner, text="Keep it anyway", command=self._keep_anyway)
        self.banner_keep.pack(side="right", padx=6)
        self.banner_shown = False
        self.banner_after = mid
        cf = ttk.Frame(mid)
        cf.pack(fill="both", expand=True)
        self.cf = cf
        self.cv = tk.Canvas(cf, background="#2b2f36", highlightthickness=0)
        xs = ttk.Scrollbar(cf, orient="horizontal", command=self.cv.xview)
        ys = ttk.Scrollbar(cf, orient="vertical", command=self.cv.yview)
        self.cv.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        self.cv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        cf.rowconfigure(0, weight=1)
        cf.columnconfigure(0, weight=1)
        self.readout = ttk.Label(mid, text="", padding=(6, 2))
        self.readout.pack(side="bottom", fill="x")
        # problems
        pf = ttk.Frame(mid)
        pf.pack(side="bottom", fill="x")
        self.probs = ttk.Treeview(pf, show="tree", height=4, selectmode="browse")
        self.probs.column("#0", width=600, stretch=True)
        self.probs.pack(fill="x")
        self.probs.bind("<<TreeviewSelect>>", lambda e: self._pick_problem())
        self.probs.tag_configure("err", foreground="#b3261e")
        self.probs.tag_configure("warn", foreground="#8a6d00")
        self.probs.tag_configure("ok", foreground="#2e7d32")
        pw.add(mid, weight=1)
        c = self.cv
        c.bind("<Button-1>", self._press)
        c.bind("<B1-Motion>", self._motion)
        c.bind("<ButtonRelease-1>", self._release)
        c.bind("<Motion>", self._hover)
        c.bind("<MouseWheel>", self._wheel)
        c.bind("<Button-4>", lambda e: self.set_zoom(self.zoom * 1.25))
        c.bind("<Button-5>", lambda e: self.set_zoom(self.zoom / 1.25))
        c.bind("<ButtonPress-2>", lambda e: c.scan_mark(e.x, e.y))
        c.bind("<B2-Motion>", lambda e: c.scan_dragto(e.x, e.y, gain=1))
        c.bind("<ButtonPress-3>", lambda e: c.scan_mark(e.x, e.y))
        c.bind("<B3-Motion>", lambda e: c.scan_dragto(e.x, e.y, gain=1))
        r = self.root
        r.bind("<Tab>", self._toggle_view)
        r.bind("<Escape>", lambda e: self._escape())
        r.bind("<Delete>", lambda e: self._key_delete(e))
        r.bind("<BackSpace>", lambda e: self._key_delete(e))
        for k, d in (("<Left>", (-1, 0)), ("<Right>", (1, 0)), ("<Up>", (0, -1)), ("<Down>", (0, 1))):
            r.bind(k, lambda e, d=d: self._nudge(e, *d))
        r.bind("<plus>", lambda e: self.set_zoom(self.zoom * 1.25))
        r.bind("<equal>", lambda e: self.set_zoom(self.zoom * 1.25))
        r.bind("<minus>", lambda e: self.set_zoom(self.zoom / 1.25))

        # inspector
        right = ttk.Frame(pw, padding=8, width=330)
        self.ins_title = ttk.Label(right, text="Nothing selected", font=("TkDefaultFont", 13, "bold"))
        self.ins_title.pack(anchor="w")
        self.ins_line = ttk.Label(right, text="", foreground="#555", wraplength=310)
        self.ins_line.pack(anchor="w", pady=(0, 6))
        self.ins_body = ttk.Frame(right)
        self.ins_body.pack(fill="x")
        ttk.Label(right, text="The statement").pack(anchor="w", pady=(10, 0))
        self.raw = tk.StringVar()
        re_ = ttk.Entry(right, textvariable=self.raw, font=("TkFixedFont", 10))
        re_.pack(fill="x")
        re_.bind("<Return>", lambda e: self.apply_raw())
        bf = ttk.Frame(right)
        bf.pack(fill="x", pady=4)
        ttk.Button(bf, text="Apply", command=self.apply_raw).pack(side="left")
        ttk.Button(bf, text="Duplicate", command=self.duplicate).pack(side="left", padx=4)
        ttk.Button(bf, text="Delete", command=self.delete).pack(side="left")
        self.ins_help = ttk.Label(right, text="", wraplength=310, foreground="#444")
        self.ins_help.pack(anchor="w", pady=(8, 0))
        self.ins_err = ttk.Label(right, text="", wraplength=310, foreground="#b3261e")
        self.ins_err.pack(anchor="w", pady=(8, 0))
        pw.add(right, weight=0)
        self._fill_palette()
        self._fill_add()

    def _build_course_tab(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text="Course")
        g = ttk.LabelFrame(f, text="About this course", padding=10)
        g.grid(row=0, column=0, sticky="nwe", padx=(0, 12))
        self.cv_title = tk.StringVar()
        self.cv_name = tk.StringVar()
        self.cv_width = tk.StringVar()
        self.cv_ball = tk.StringVar()
        self.cv_music = tk.StringVar()
        self.cv_pal = tk.StringVar()
        self.cv_target = tk.StringVar()
        self.cv_limit = tk.StringVar()
        self.cv_gold = tk.StringVar()
        self.cv_silver = tk.StringVar()
        self.cv_gstyle = tk.StringVar()
        self.cv_cstrict = tk.BooleanVar()
        rows = [
            ("Title", ttk.Entry(g, textvariable=self.cv_title, width=26), "1 - 24 characters, no quote marks"),
            ("Short name", ttk.Entry(g, textvariable=self.cv_name, width=8), "1 - 5 of A-Z 0-9"),
            ("Picture width", ttk.Combobox(g, textvariable=self.cv_width, values=[str(w) for w in range(64, 161, 8)],
                                           width=6, state="readonly"),
             "columns of 8 px (64 - 160); wider leaves less room for the course's length"),
            ("Course's ball", ttk.Combobox(g, textvariable=self.cv_ball, values=E.MATERIALS, width=8,
                                           state="readonly"), "best times count only with this ball"),
            ("Music", ttk.Combobox(g, textvariable=self.cv_music, values=["(default)"] + list(_songs()),
                                   width=14, state="readonly"), ""),
            ("CGA palette", ttk.Combobox(g, textvariable=self.cv_pal, values=("(default)", "0", "1", "0 dim",
                                                                             "1 dim"), width=8,
                                         state="readonly"), "0: green, red, brown; 1: cyan, magenta, white"),
            ("Gate style", ttk.Combobox(g, textvariable=self.cv_gstyle, values=("(default)",) + tuple(B.GT_STYLES),
                                        width=10, state="readonly"), ""),
            ("Designed to take", ttk.Combobox(g, textvariable=self.cv_target, values=("(none)", "30", "60", "90"),
                                              width=6, state="readonly"), "seconds: sets the size budget"),
            ("Time limit", ttk.Entry(g, textvariable=self.cv_limit, width=6), "whole seconds; empty: automatic"),
            ("Gold medal", ttk.Entry(g, textvariable=self.cv_gold, width=6), "seconds"),
            ("Silver medal", ttk.Entry(g, textvariable=self.cv_silver, width=6), "seconds"),
        ]
        for i, (lab, w, hint) in enumerate(rows):
            ttk.Label(g, text=lab).grid(row=i, column=0, sticky="w", pady=3)
            w.grid(row=i, column=1, sticky="w", padx=8)
            ttk.Label(g, text=hint, foreground="#666").grid(row=i, column=2, sticky="w")
        ttk.Checkbutton(g, text="This course is finished: hold it to --strict in every build (`strict`)",
                        variable=self.cv_cstrict).grid(row=len(rows), column=0, columnspan=3, sticky="w", pady=6)
        ttk.Button(g, text="Apply", command=self.apply_course).grid(row=len(rows) + 1, column=0, sticky="w")
        ttk.Label(g, text="Extras the course loads (`uses`) are added for you as you place parts.",
                  foreground="#666").grid(row=len(rows) + 2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        c = ttk.LabelFrame(f, text="Ready to play?", padding=10)
        c.grid(row=0, column=1, sticky="nsew")
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)
        top = ttk.Frame(c)
        top.pack(fill="x")
        ttk.Button(top, text="Check now", command=self.run_check).pack(side="left")
        ttk.Button(top, text="Put this course in the game...", command=self.put_in_game).pack(side="right")
        ttk.Checkbutton(top, text="Treat warnings as errors (--strict, what agents' runs use)",
                        variable=self.strict, command=self.run_check).pack(side="left", padx=8)
        self.check_l = ttk.Label(c, text="", wraplength=520)
        self.check_l.pack(anchor="w", pady=6)
        self.checks = ttk.Treeview(c, show="tree", height=12)
        self.checks.column("#0", width=600, stretch=True)
        self.checks.pack(fill="both", expand=True)
        self.checks.tag_configure("err", foreground="#b3261e")
        self.checks.tag_configure("warn", foreground="#8a6d00")
        self.checks.tag_configure("ok", foreground="#2e7d32")
        self.checks.tag_configure("acc", foreground="#666")
        self.checks.bind("<<TreeviewSelect>>", lambda e: self._pick_check())
        ttk.Label(c, text="Errors stop a build. Warnings never do; mark an element `hidden` (its inspector) or "
                  "`accept` a warning to keep it under --strict (SPEC.md 130.58.5).", wraplength=520,
                  foreground="#444").pack(anchor="w", pady=(6, 0))

    def put_in_game(self):
        """ADD TO THE GAME (SPEC.md 130.58.17): tools/bbgame.py as a process - BONANZA.O88 with the shipped
        courses and this one on the pathway's pad 0, or a floppy holding it (an .img name)"""
        import shutil
        from tkinter import filedialog, messagebox
        if not self.doc.path or self.doc.dirty:
            messagebox.showinfo(TITLE, "Save the course first: the game is made from the file on disk.")
            return
        out = filedialog.asksaveasfilename(
            title="Put this course in the game: save the game as", initialfile="BONANZA.O88",
            defaultextension=".o88", initialdir=self.cfg.get("dir"),
            filetypes=[("The game (BONANZA.O88)", "*.o88"), ("A floppy with the game (1.44 MB)", "*.img")])
        if not out:
            return
        work = tempfile.mkdtemp(prefix="bbgame-")
        img = out.lower().endswith(".img")
        pk = os.path.join(work, "BONANZA.O88") if img else out
        is_map = bbedmap.is_map(self.doc.text())
        if is_map:                              # the pathway: the game with this map and the courses it names
            argv = [sys.executable, "-u", os.path.join(HERE, "bbgame.py"), pk, "--path", self.doc.path]
        else:
            name = B.parse(self.doc.text(), self.doc.path).name
            argv = [sys.executable, "-u", os.path.join(HERE, "bbgame.py"), pk, self.doc.path, "--pad0", name]
        argv += ["--disk", out, "--size", "1440"] if img else []
        self._msg("Putting the course in the game: compiling every course (minutes the first time)...")
        res = {}

        def go():
            r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            res["r"] = r

        def wait():
            if "r" not in res:
                self.root.after(500, wait)
                return
            r = res["r"]
            shutil.rmtree(work, ignore_errors=True)
            if r.returncode == 0:
                self._msg("Wrote %s" % out)
                messagebox.showinfo(TITLE, ("Wrote %s.\n\nThe game has this map, and the courses it names." % out)
                                    if is_map else ("Wrote %s.\n\nYour course is on the pathway's first pad: "
                                                    "Play Game, then Enter plays it." % out))
            else:
                self._msg("The game was not made")
                messagebox.showerror(TITLE, (r.stderr or r.stdout).strip()[-1500:] or "bbgame.py failed")

        threading.Thread(target=go, daemon=True).start()
        self.root.after(500, wait)

    def _build_source_tab(self):
        tk, ttk = self.tk, self.ttk
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="Source")
        self.src_t = tk.Text(f, wrap="none", font=("TkFixedFont", 10), undo=False)
        ys = ttk.Scrollbar(f, orient="vertical", command=self.src_t.yview)
        self.src_t.configure(yscrollcommand=ys.set)
        self.src_t.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self.src_t.tag_configure("sel_line", background="#fff3c4")
        self.src_t.tag_configure("err_line", background="#fde2df")
        self.src_t.tag_configure("cmt", foreground="#777")
        self.src_t.bind("<Double-Button-1>", self._src_pick)
        self.src_t.configure(state="disabled")

    # -- files ------------------------------------------------------------
    def new(self):
        if not self._discard_ok():
            return
        text = ('course NEW "New course"\nwidth 64\nball rubber\n\n'
                "floor rect 4 4 14 12 flat 4\nstart 5 5\ngoal rect 12 10 14 12 flat 4\n"
                "target 30\nway 5 5\nway 13 11\n")
        self._set_doc(E.Document(text))

    def open_dialog(self):
        from tkinter import filedialog
        p = filedialog.askopenfilename(title="Open a course", filetypes=[("Courses", "*.bbc"), ("All", "*")],
                                       initialdir=self.cfg.get("dir") or os.path.join(B.ROOT, "apps", "bonanza",
                                                                                     "courses"))
        if p:
            self.open(p)

    def open(self, path):
        if not self._discard_ok():
            return
        try:
            d = E.Document.load(path)
        except (OSError, UnicodeDecodeError) as e:
            self._msg("Cannot open %s: %s" % (path, e))
            return
        self.cfg["dir"] = os.path.dirname(os.path.abspath(path))
        rec = [p for p in self.cfg.get("recent", []) if p != os.path.abspath(path)]
        self.cfg["recent"] = [os.path.abspath(path)] + rec[:9]
        save_config(self.cfg)
        self._set_doc(d)

    def _set_doc(self, d):
        self.doc.listeners = []
        self.doc = d
        d.listeners.append(self._changed)
        self.sel = None
        self.area = None
        self.good = None
        self.pic = None
        self.check = None
        self._banner(None)
        self._fill_recent()
        self._changed("open")
        self.root.after(50, self._fit)
        if bbedmap.is_map(d.text()):            # a pathway opens on its Map tab (SPEC.md 130.58.20)
            self.nb.select(self.map.frame)

    def save(self):
        if self.doc.path is None:
            return self.save_as()
        try:
            self.doc.save()
        except E.EditError as e:
            from tkinter import messagebox
            if messagebox.askyesno(TITLE, "%s\n\nOverwrite the file on disk?" % e):
                self.doc.save(force=True)
            else:
                return
        self._msg("Saved %s" % self.doc.path)
        self._title()

    def save_as(self):
        from tkinter import filedialog
        p = filedialog.asksaveasfilename(title="Save the course", defaultextension=".bbc",
                                         filetypes=[("Courses", "*.bbc")], initialdir=self.cfg.get("dir"))
        if p:
            self.doc.save(p, force=True)
            self._msg("Saved %s" % p)
            self._title()

    def reload(self):
        if self.doc.path and self._discard_ok():
            self.open(self.doc.path)

    def _discard_ok(self):
        if not self.doc.dirty:
            return True
        from tkinter import messagebox
        return messagebox.askyesno(TITLE, "The course has unsaved changes. Discard them?")

    def _focus(self, e):
        if e.widget is not self.root or not self.doc.path:
            return
        if self.doc.changed_on_disk() and not getattr(self, "_asked_disk", False):
            self._asked_disk = True
            from tkinter import messagebox
            if messagebox.askyesno(TITLE, "%s changed on disk. Reload it?%s" % (
                    os.path.basename(self.doc.path), "\n\nYour unsaved edits would be lost." if self.doc.dirty
                    else "")):
                self.doc.saved_text = self.doc.text()
                self.open(self.doc.path)
            else:
                self.doc.stamp = E.file_stamp(self.doc.path)
            self._asked_disk = False

    def quit(self):
        if not self._discard_ok():
            return
        self.cancel_jobs()
        self.cfg["geometry"] = self.root.geometry()
        save_config(self.cfg)
        self.root.destroy()

    def _fill_recent(self):
        self.recent_menu.delete(0, "end")
        for p in self.cfg.get("recent", []):
            self.recent_menu.add_command(label=p, command=lambda p=p: self.open(p))

    def _title(self):
        nm = os.path.basename(self.doc.path) if self.doc.path else "untitled"
        self.root.title("%s%s - %s" % (nm, " *" if self.doc.dirty else "", TITLE))

    # -- edits ------------------------------------------------------------
    def _changed(self, what):
        self._title()
        a = self.doc.analysis()
        if a["cells"] and not a["error"]:
            self.good = a
        if self.sel is not None and (self.sel > len(self.doc.lines) or not self.doc.lines[self.sel - 1].strip()
                                     or self.doc.lines[self.sel - 1].lstrip().startswith("#")):
            self.sel = None
        self._redraw()
        self._fill_inspector()
        self._fill_course()
        self._fill_source()
        self._fill_problems()
        if getattr(self, "shapes", None) and self.shapes.shown():
            self.shapes.refresh()
        if getattr(self, "map", None) and self.map.shown():
            self.map.refresh()
        self._schedule_jobs()
        if a["error"]:
            self._msg(a["error"])

    def undo(self):
        lab = self.doc.undo()
        self._msg("Undid: %s" % lab if lab else "Nothing to undo")

    def redo(self):
        lab = self.doc.redo()
        self._msg("Redid: %s" % lab if lab else "Nothing to redo")

    def _edit(self, fn, *a, **kw):
        """every edit the window makes: done, `uses` added for it, and UNDONE AGAIN when it leaves the course
        refused where it was not before - the course never ends up broken by a click; the banner says why
        in plain words and offers to keep it anyway"""
        before = self.doc.analysis()["error"]
        n0 = len(self.doc.undo_stack)
        try:
            r = fn(*a, **kw)
        except E.EditError as e:
            self._msg(str(e))
            return None
        added = self.doc.auto_uses()
        band = self.doc.auto_band()
        self._note = ("The course grew past the game's picture, so the builder %s. " % band) if band else ""
        after = self.doc.analysis()["error"]
        if after and after != before and E.Document.WAY_ERR.search(after) and len(self.doc.undo_stack) > n0:
            moved = self.doc.relocate_ways()        # SPEC.md 130.58.22: a route point the edit stranded moves
            if moved:                               # to the nearest floor, in the same undo step
                self.doc.merge_since(n0)
                self._note += "Route point%s moved to stay on the floor: %s. " % (
                    "s" if len(moved) > 1 else "", "; ".join("line %d to %d, %d" % (ln, n[0], n[1])
                                                             for ln, _o, n in moved))
                after = self.doc.analysis()["error"]
        if after and after != before and len(self.doc.undo_stack) > n0:
            while len(self.doc.undo_stack) > n0:
                self.doc.undo()
                if self.doc.redo_stack:
                    self.doc.redo_stack.pop()
            self.keep = (fn, a, kw)
            self._banner("That change was undone: %s" % explain(after), keep=True)
            return None
        self._banner(None)
        if added:
            self._msg("Added `uses %s`: the course needs it for the part you added" % " ".join(added))
        return r

    def _banner(self, text, keep=False):
        if not text:
            if self.banner_shown:
                self.banner.pack_forget()
                self.banner_shown = False
            return
        self.banner_l.config(text=text)
        if keep:
            self.banner_keep.pack(side="right", padx=6)
        else:
            self.banner_keep.pack_forget()
        if not self.banner_shown:
            self.banner.pack(side="top", fill="x", before=self.cf)
            self.banner_shown = True

    def _keep_anyway(self):
        k, self.keep = self.keep, None
        self._banner(None)
        if k:
            fn, a, kw = k
            try:
                fn(*a, **kw)
            except E.EditError as e:
                self._msg(str(e))
            self.doc.auto_uses()

    def delete(self):
        lines = sorted(set(self.sels) | ({self.sel} if self.sel else set()), reverse=True)
        if not lines:
            return
        self.sel, self.sels = None, []

        def rm():
            with self.doc.group("delete"):
                for ln in lines:
                    self.doc.remove(ln)
            return True
        self._edit(rm)

    def duplicate(self):
        if not self.sel:
            return
        st = self.doc.statement(self.sel)
        n = self._edit(self.doc.insert, st.code, after=self.sel, label="duplicate %s" % st.subkind)
        if n:
            self.sel = n
            if E.coord_slots(st.toks):
                self._edit(self.doc.move, n, 1, 1, label="duplicate %s" % st.subkind)

    def apply_raw(self):
        if not self.sel:
            code = self.raw.get().strip()
            if code:
                n = self._edit(self.doc.insert, code)
                if n:
                    self.select(n)
            return
        self._edit(self.doc.set_statement, self.sel, self.raw.get())

    def _key_delete(self, e):
        if isinstance(e.widget, (self.tk.Entry, self.ttk.Entry, self.tk.Text, self.ttk.Spinbox)):
            return
        if self.sel:
            self.delete()
        elif self.area:
            self.clear_area()

    def clear_area(self):
        """remove every part whose whole footprint is inside the selected area (one undo step)"""
        x0, y0, x1, y1 = self.area
        a = self.doc.analysis()
        foot = {}
        for c, d in a["cells"].items():
            foot.setdefault(d["line"], set()).add(c)
        for it in a["items"]:
            foot.setdefault(it["line"], set()).update(it["cells"])
        gone = sorted((ln for ln, cs in foot.items() if ln and cs and all(x0 <= x <= x1 and y0 <= y <= y1
                                                                          for x, y in cs)), reverse=True)
        if not gone:
            self._msg("Nothing lies wholly inside the area; click a part to delete it")
            return

        def rm():
            new = [l_ for i, l_ in enumerate(self.doc.lines, 1) if i not in set(gone)]
            self.doc._commit("clear the area", new)
        self._edit(rm)

    def _nudge(self, e, dx, dy):
        if isinstance(e.widget, (self.tk.Entry, self.ttk.Entry, self.tk.Text, self.ttk.Spinbox,
                                 self.ttk.Treeview)) or not self.sel:
            return
        if E.coord_slots(self.doc.statement(self.sel).toks):
            self.move_sel(dx, dy)
        return "break"

    def apply_course(self):
        self._edit(self._apply_course)

    def _apply_course(self):
        d = self.doc
        sts = {s.kind: s for s in d.statements()}

        def put(kind, code):
            if code is None:
                if kind in sts:
                    d.remove(sts[kind].line, label="course settings")
                return
            if kind in sts:
                if sts[kind].code != code:
                    d.set_statement(sts[kind].line, code, label="course settings")
            else:
                anchor = [s.line for s in d.statements() if s.kind in ("course", "width", "ball", "uses")]
                d.insert(code, after=anchor[-1] if anchor else 0, label="course settings")
            sts.update({s.kind: s for s in d.statements()})
        try:
            title = self.cv_title.get().strip().replace('"', "")
            put("course", '%s "%s"' % ("course " + (self.cv_name.get().strip().upper() or "NEW"), title or "Course"))
            put("width", "width %s" % (self.cv_width.get() or "64"))
            put("ball", "ball %s" % self.cv_ball.get() if self.cv_ball.get() else None)
            m = self.cv_music.get()
            put("music", None if m in ("", "(default)") else "music %s" % m)
            p = self.cv_pal.get()
            put("palette", None if p in ("", "(default)") else "palette %s" % p)
            g = self.cv_gstyle.get()
            put("gatestyle", None if g in ("", "(default)") else "gatestyle %s" % g)
            t = self.cv_target.get()
            put("target", None if t in ("", "(none)") else "target %s" % t)
            lim = self.cv_limit.get().strip()
            put("limit", "limit %s" % lim if lim else None)
            gd, sv = self.cv_gold.get().strip(), self.cv_silver.get().strip()
            put("medals", "medals %s %s" % (gd, sv) if gd and sv else None)
            put("strict", "strict" if self.cv_cstrict.get() else None)
        except E.EditError as e:
            self._msg(str(e))
        return True

    # -- the palette --------------------------------------------------------
    def _fill_palette(self):
        q = self.find.get().strip().lower()
        self.pal.delete(*self.pal.get_children())
        self.pal_items = {}
        for grp, items in PALETTE:
            shown = [it for it in items if not q or q in it[0].lower() or q in it[3].lower() or q in it[2].lower()]
            if not shown:
                continue
            gid = self.pal.insert("", "end", text=grp, open=bool(q) or grp in ("Ground", "Game"))
            for it in shown:
                iid = self.pal.insert(gid, "end", text=it[0])
                self.pal_items[iid] = it

    def _pick_part(self):
        sel = self.pal.selection()
        it = self.pal_items.get(sel[0]) if sel else None
        self.part = it
        self._fill_add()

    def _tool_changed(self):
        self._msg("Erase: click something to remove it" if self.tool.get() == "erase" else
                  "Select: click a part to edit it, or drag across the course to choose an area")

    def _escape(self):
        self.tool.set("select")
        self.area = None
        self.select(None)
        self._fill_add()
        self._msg("Nothing selected")

    def _target(self):
        """the cells an Add goes to: the selected area, else the selected part's footprint"""
        if self.area:
            return self.area
        cells = self._sel_cells() if self.sel else set()
        if cells:
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            return min(xs), min(ys), max(xs), max(ys)
        return None

    def _fill_add(self):
        it = self.part
        t = self._target()
        if not it:
            self.add_name.config(text="Choose a part above")
            self.add_desc.config(text="Then press Add to put it on the selected area. Drag across the course "
                                 "to select an area; click a part to select it.")
            self.add_btn.state(["disabled"])
            self.add_where.config(text="")
            return
        self.add_name.config(text=it[0])
        self.add_desc.config(text=it[3])
        self.add_btn.config(text="Add %s" % it[0].lower())
        if t:
            self.add_btn.state(["!disabled"])
            w, h = t[2] - t[0] + 1, t[3] - t[1] + 1
            self.add_where.config(text=("on the %d x %d area at (%d, %d)" % (w, h, t[0], t[1])) if it[1] == "rect"
                                  else "at (%d, %d)%s" % (t[0], t[1], "" if w == h == 1 else ", the area's corner"))
        else:
            self.add_btn.state(["disabled"])
            self.add_where.config(text="First drag across the course to choose where (or click a cell).")

    def _covers(self, st, cell):
        sh = self._shape(st)
        if not sh:
            return False
        x0, y0, x1, y1 = sh[2]
        return x0 <= cell[0] < x1 and y0 <= cell[1] < y1

    def _ramp_fit(self, area):
        """a ramp that JOINS the floors on two opposite sides of the area: (axis, p0, p1, h0, h1), its low end
        at the lower floor's edge, rising toward the higher one as nearly as half units a tile allow; the axis
        whose two floors differ most. None when no two opposite sides have floor"""
        a = self.doc.analysis()["cells"]
        x0, y0, x1, y1 = area
        best = None
        for ax in ("x", "y"):
            if ax == "x":
                lo_cells = [(x0 - 1, y) for y in range(y0, y1 + 1)]
                hi_cells = [(x1 + 1, y) for y in range(y0, y1 + 1)]
                e_lo, e_hi, n, p0, p1 = "+x", "-x", x1 - x0 + 1, x0, x1 + 1
            else:
                lo_cells = [(x, y0 - 1) for x in range(x0, x1 + 1)]
                hi_cells = [(x, y1 + 1) for x in range(x0, x1 + 1)]
                e_lo, e_hi, n, p0, p1 = "+y", "-y", y1 - y0 + 1, y0, y1 + 1
            A = [a[c]["edges"][e_lo] for c in lo_cells if c in a and a[c]["kind"] in ("floor", "goal")]
            Bv = [a[c]["edges"][e_hi] for c in hi_cells if c in a and a[c]["kind"] in ("floor", "goal")]
            if not A or not Bv:
                continue
            ha, hb = max(A), max(Bv)
            if ha == hb:
                continue
            rate = (hb - ha) / float(n)
            k = round(abs(rate) * 2) / 2.0 or 0.5
            k = k if hb > ha else -k
            if ha <= hb:                         # anchored at the lower floor
                h0, h1 = ha, ha + k * n
            else:
                h1, h0 = hb, hb - k * n
            cand = (abs(hb - ha), ax, p0, p1, h0, h1)
            if best is None or cand[0] > best[0]:
                best = cand
        return best[1:] if best else None

    def cut_corner(self, corner):
        """SPEC.md 130.58.15: cut the area's CORNER off along a diagonal - the cells before the line dropped,
        the cells ON it halved (the half away from the corner kept), every piece keeping its own statement's
        kind, height and ramp. The cut is as deep as the area's shorter side"""
        if not self.area:
            return
        x0, y0, x1, y1 = self.area
        n = min(x1 - x0, y1 - y0) + 1
        keep, depth = {"nw": ("down", lambda x, y: (x - x0) + (y - y0)), "ne": ("left", lambda x, y: (x1 - x) + (y - y0)),
                       "sw": ("right", lambda x, y: (x - x0) + (y1 - y)),
                       "se": ("up", lambda x, y: (x1 - x) + (y1 - y))}[corner]
        a = self.doc.analysis()
        drop, halves, skipped = [], [], 0
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                k = depth(x, y)
                d = a["cells"].get((x, y))
                if not d or k > n - 1:
                    continue
                if d.get("pieces") or d["kind"] == "field":
                    skipped += 1
                    continue
                st = self.doc.statement(d["line"])
                sh = self.doc._ground_shape(st)
                if not sh:
                    skipped += 1
                    continue
                if k < n - 1:
                    drop.append((x, y, x, y))
                else:
                    i, _r, w = sh
                    halves.append(E.join_tokens(st.toks[:i] + ["half", keep, "tile", str(x), str(y)] +
                                                st.toks[i + w:]))
        if not drop and not halves:
            self._msg("Nothing to cut there: the corner's cells are empty%s" % (
                " or already diagonal" if skipped else ""))
            return

        def go():
            with self.doc.group("cut a corner"):
                if drop:
                    self.doc.replace_area(drop, surfaces=True)
                hc = []
                for h in halves:
                    t_ = h.split()
                    j = t_.index("tile")
                    hc.append((int(t_[j + 1]), int(t_[j + 2]), int(t_[j + 1]), int(t_[j + 2])))
                if halves:
                    self.doc.replace_area(hc, ground=halves)
                self.doc.tidy(self.area)
            return True
        if self._edit(go):
            self._msg("Cut the corner: %d cells dropped, %d halved%s" % (len(drop), len(halves), (
                "; %d already diagonal or shaped, left alone" % skipped) if skipped else ""))

    def diagonal_strip(self, how):
        """SPEC.md 130.58.15: a STRAIGHT strip of the screen (`floor box`), one diamond (32 px) wide, from the
        area's first cell to its last - down the screen along the plan's x = y diagonal, or across it along
        x + y - at the height of the floor there. Laid over what is there (a box is never cut)"""
        if not self.area:
            return
        x0, y0, x1, y1 = self.area
        inside, around = self._heights(self.area)
        try:
            typed = float(self.height.get())
        except ValueError:
            typed = 4.0
        h = inside if inside is not None else around if around is not None else typed
        h = round(h * 4) / 4.0
        hs = ("%d" % h) if h == int(h) else ("%g" % h)
        if how == "down":                       # cells x - y = a, from (x0, y0) toward (x1, y1)
            a = x0 - y0
            n = max(x1 - x0, y1 - y0)
            a0, a1, s0, s1 = a - 1, a + 1, x0 + y0, x0 + y0 + 2 * n + 2
        else:                                   # cells x + y = k, from (x0, y1) toward (x1, y0)
            k = x0 + y1
            n = max(x1 - x0, y1 - y0)
            a0, a1, s0, s1 = x0 - y1 - 1, x0 - y1 + 2 * n + 1, k, k + 2
        code = "floor box %d %d %d %d flat %s" % (a0, a1, s0, s1, hs)

        def go():
            self.doc.replace_area(None, ground=[code], label="a diagonal strip")
            return True
        if self._edit(go):
            ln = next((s_.line for s_ in self.doc.statements() if s_.code == code), None)
            self.select(ln)
            self._msg("Added a diagonal strip %s the screen at height %s: %s" % (
                "down" if how == "down" else "across", hs, code))

    def _flat_heights(self, t):
        """(the highest FLAT floor in the area, the highest flat floor touching it from outside), or None"""
        a = self.doc.analysis()
        x0, y0, x1, y1 = t
        fin, fout = [], []
        for (x, y), d in a["cells"].items():
            if d["kind"] not in ("floor", "goal") or d["slope"] != (0, 0) or d["hmin"] != d["hmax"]:
                continue
            if x0 <= x <= x1 and y0 <= y <= y1:
                fin.append(d["h"])
            elif x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1:
                fout.append(d["h"])
        return (max(fin) if fin else None), (max(fout) if fout else None)

    def _heights(self, t):
        """(the highest floor IN the area, the highest floor in it or touching it), units, or None"""
        a = self.doc.analysis()
        x0, y0, x1, y1 = t
        inside = [d["hmax"] for (x, y), d in a["cells"].items() if x0 <= x <= x1 and y0 <= y <= y1
                  and d["kind"] in ("floor", "goal", "field")]
        around = [d["hmax"] for (x, y), d in a["cells"].items() if x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1
                  and d["kind"] in ("floor", "goal", "field")]
        return (max(inside) if inside else None), (max(around) if around else None)

    def _lowest_beside(self, t):
        """the height a wall laid over the empty area T needs to wall off what is below it (SPEC.md 130.10.3: each
        wall cell above at least one floor it shares an edge with): for every cell of T the lowest floor point on
        its four sides, the highest of those - in units, or None when no cell of T touches a floor"""
        a = self.doc.analysis()
        x0, y0, x1, y1 = t
        need = []
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                low = [a["cells"][q]["hmin"] for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                       if q in a["cells"] and a["cells"][q]["kind"] in ("floor", "goal", "field")]
                if low:
                    need.append(min(low))
        return max(need) if need else None

    GROUND = {"Floor": "floor", "Ramp": "floor", "Wall": "wall", "Hole": "hole", "Goal": "goal"}
    PAINT = {"Ice": "ice", "Sand": "sand", "Bounce mat": "bounce", "Normal": "normal"}
    # the parts that stand ON the ground: added on an empty cell, they bring a floor tile with them
    ON_GROUND = {"Windmill", "Bumper", "Turntable", "Spring", "Boost pad", "Blower", "Magnet",
                 "Pop-up spikes", "Cracked floor", "Glass path", "Hourglass", "Speed", "Jump", "Start",
                 "Route point", "Flag", "Ball pad: rubber", "Ball pad: steel", "Ball pad: glass", "Cup", "Clock",
                 "Gate", "Pressure plate", "Key", "Pit", "Chute", "Hump", "Life"}

    def add_part(self, name=None):
        """the chosen part on the selected area (SPEC.md 130.58.12, 130.58.13): the GROUND is one layer of
        cells, so Floor, Ramp, Wall, Hole and Goal REPLACE the area's cells (the statements round it are cut,
        keeping their own heights and ramps), the surfaces repaint it, a part that stands on the ground brings
        a floor tile to an empty cell, and an archway goes OVER the area with its legs made for it"""
        it = self.part if name is None else next((i for _g, its in PALETTE for i in its if i[0] == name), None)
        t = self._target()
        if not it or not t:
            self._fill_add()
            return
        name, mode, tpl, _hint = it
        x0, y0, x1, y1 = t
        inside, around = self._heights(t)
        try:
            typed = float(self.height.get())
        except ValueError:
            typed = 4.0
        base = inside if inside is not None else around if around is not None else typed
        if name in ("Floor", "Goal"):           # level with the FLAT floor here, or round it (not a ramp's top)
            flat_in, flat_out = self._flat_heights(t)
            base = flat_in if flat_in is not None else flat_out if flat_out is not None else base
        if name == "Wall":                      # (SPEC.md 130.10.3: a wall need only stand above what it walls off)
            h = (inside if inside is not None else self._lowest_beside(t) if self._lowest_beside(t) is not None
                 else typed) + 1
        else:
            h = base
        h = round(h * 4) / 4.0

        def f(v):
            return ("%d" % v) if v == int(v) else ("%g" % v)
        a = self.doc.analysis()
        area = (x0, y0, x1, y1)
        if name in self.GROUND or name in self.PAINT:
            if name == "Ramp":                  # between two floors it joins them; else half a unit a tile
                fit = self._ramp_fit(area)
                if fit:
                    ax, p0, p1, ha, hb = fit
                else:
                    ax = "y" if (y1 - y0) > (x1 - x0) else "x"
                    n = (y1 - y0 + 1) if ax == "y" else (x1 - x0 + 1)
                    p0, p1 = (y0, y1 + 1) if ax == "y" else (x0, x1 + 1)
                    ha, hb = h, h + 0.5 * n
                code = "floor rect %d %d %d %d ramp %s %d %d %s %s" % (x0, y0, x1 + 1, y1 + 1, ax, p0, p1, f(ha),
                                                                     f(hb))
            elif name in self.PAINT:
                code = None if name == "Normal" else "surface %s rect %d %d %d %d" % (self.PAINT[name], x0, y0,
                                                                                      x1 + 1, y1 + 1)
            else:
                kind = self.GROUND[name]
                shape = "tile %d %d" % (x0, y0) if (x0, y0) == (x1, y1) else "rect %d %d %d %d" % (
                    x0, y0, x1 + 1, y1 + 1)
                code = "%s %s%s" % (kind, shape, "" if kind == "hole" else " flat %s" % f(h))
            paint = name in self.PAINT

            def go():
                with self.doc.group("make the area %s" % name.lower()):
                    n0 = self.doc.replace_area(area, ground=[code] if code else [],
                                               kinds=() if paint else ("floor", "wall", "goal", "hole"),
                                               surfaces=paint or name in ("Wall", "Hole"))
                    self.doc.tidy(area)
                return n0 or True
            n_ = self._edit(go)
            if n_ and code:
                n_ = next((s_.line for s_ in self.doc.statements() if s_.code == code),
                          next((s_.line for s_ in self.doc.statements() if s_.kind == code.split()[0] and
                                self._covers(s_, (x0, y0))), None))
            if n_:
                self.area = area
                self.select(n_ if code else None)
                self._msg("The area is now %s. Its settings are on the right; Ctrl+Z takes it back." % name.lower())
            return
        if name == "Archway":                   # OVER the area, its legs the cells beside it, made walls
            w, hh = x1 - x0 + 1, y1 - y0 + 1
            if min(w, hh) <= 2 and max(w, hh) >= 3:
                # leg, passage, leg: the area IS the arch, its legs its two ends, the ball passing across it
                if hh > w:
                    along = "x"
                    y0, y1 = y0 + 1, min(y1 - 1, y0 + 2)
                else:
                    along = "y"
                    x0, x1 = x0 + 1, min(x1 - 1, x0 + 2)
            elif w <= 2 and hh <= 2:
                along = "y" if w > hh else "x"
            else:
                along = "x" if w >= hh else "y"
                if along == "x":
                    mx = (x0 + x1) // 2
                    x0, x1, y1 = mx, mx, min(y1, y0 + 1)
                else:
                    my = (y0 + y1) // 2
                    y0, y1, x1 = my, my, min(x1, x0 + 1)
            legs = ([(x, y0 - 1) for x in range(x0, x1 + 1)] + [(x, y1 + 1) for x in range(x0, x1 + 1)]
                    if along == "x" else
                    [(x0 - 1, y) for y in range(y0, y1 + 1)] + [(x1 + 1, y) for y in range(y0, y1 + 1)])
            walls = []
            cuts = []
            for c in legs:
                d = a["cells"].get(c)
                if d and d["kind"] in ("floor", "goal"):
                    cuts.append((c[0], c[1], c[0], c[1]))
                    walls.append("wall tile %d %d flat %s" % (c[0], c[1], f(d["hmax"])))
            code = ("archway tile %d %d along %s" % (x0, y0, along) if (x0, y0) == (x1, y1) else
                    "archway rect %d %d %d %d along %s" % (x0, y0, x1 + 1, y1 + 1, along))
            n_ = self._edit(self.doc.replace_area, cuts, ground=walls, then=[code], kinds=("floor", "goal"),
                            label="add an archway")
            if n_:
                ln = next((s_.line for s_ in self.doc.statements() if s_.code == code), None)
                self.select(ln)
                self._msg("Added an archway over (%d, %d)%s. Change its clearance on the right." % (
                    x0, y0, "; its legs stand on %d cells made walls" % len(walls) if walls else ""))
            return
        code = tpl.format(x=x0, y=y0, x0=x0, y0=y0, x1=x1 + 1, y1=y1 + 1, h=f(h), x3=x0 + 3, x4=x0 + 4,
                          y1b=y0 + 1, y3=y0 + 3)
        tall = (y1 - y0) > (x1 - x0)            # a part with a direction takes it from the area's shape
        if tall:
            code = (code.replace(" along x", " along y").replace(" face +x", " face +y")
                    .replace(" face -x", " face -y"))
            if code.startswith("tube "):        # a tube from the area's top to its bottom
                t_ = code.split()
                t_[4], t_[5] = str(x0), str(y1 if y1 > y0 else y0 + 3)
                code = " ".join(t_).replace(" out +x", " out +y")
        elif code.startswith("tube ") and x1 > x0:
            t_ = code.split()
            t_[4] = str(x1)
            code = " ".join(t_)
        kind = code.split()[0]
        ground = []
        if name in self.ON_GROUND and (x0, y0) not in a["cells"]:
            ground = ["floor tile %d %d flat %s" % (x0, y0, f(base))]
        if kind == "start":                 # one start: move it
            st = [s_ for s_ in self.doc.statements() if s_.kind == "start"]
            if st:
                def mv():
                    self.doc.set_statement(st[0].line, code, label="move the start")
                    if ground:
                        self.doc.replace_area(None, ground=ground, label="move the start")
                    return True
                if self._edit(mv):
                    self.select(next(s_.line for s_ in self.doc.statements() if s_.kind == "start"))
                return
        n_ = self._edit(self.doc.replace_area, None, ground=ground, then=[code], kinds=(),
                        label="add %s" % name.lower())
        if n_:
            ln = next((s_.line for s_ in reversed(self.doc.statements()) if s_.code == code), n_)
            self.select(ln)
            self._msg("Added %s%s (line %d). Edit it on the right; Ctrl+Z takes it back." % (
                name.lower(), " with floor under it" if ground else "", ln))

    # -- selection and the inspector ---------------------------------------------
    def select(self, line, scroll=False, add=False):
        if add and line:                        # Ctrl-click: toggle it in the multi-selection
            if line in self.sels:
                self.sels.remove(line)
                line = self.sels[-1] if self.sels else None
            else:
                self.sels.append(line)
        else:
            self.sels = [line] if line else []
        self.sel = line
        self._redraw()
        self._fill_inspector()
        self._fill_source()
        self._fill_add()
        if scroll:
            self.root.after(10, self._scroll_to_sel)

    def _sel_cells(self, lines=None):
        a = self.doc.analysis()
        want = set(lines) if lines is not None else ({self.sel} | set(self.sels))
        cells = {c for c, d in a["cells"].items() if d["line"] in want}
        for it in a["items"]:
            if it["line"] in want:
                cells.update(it["cells"])
        return cells

    def _scroll_to_sel(self):
        """bring the selection into view, in either view"""
        cells = self._sel_cells() or ({self.hilite} if getattr(self, "hilite", None) else set())
        c = self.cv
        if not cells:                            # nothing selected: the middle of the course
            if self.view.get() == "iso" and self.pic and getattr(self, "iso_scale", None):
                kx, ky = self.iso_scale
                cx, cy = self.pic["meta"]["centre"]
                cx, cy = cx * kx, cy * ky
                sr = [float(v) for v in str(c.cget("scrollregion")).split()] or [0, 0, 1, 1]
                c.xview_moveto(max(0.0, (cx - c.winfo_width() / 2.0) / max(1.0, sr[2])))
                c.yview_moveto(max(0.0, (cy - c.winfo_height() / 2.0) / max(1.0, sr[3])))
            return
        if self.view.get() == "plan":
            xs, ys = zip(*[self._cpx(x + .5, y + .5) for (x, y) in cells])
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        else:
            if not self.pic:
                return
            meta = self.pic["meta"]
            W = meta["width"]
            ow = self.pic["owners"]
            keys = {256 * x + y for (x, y) in cells}
            pts = [i for i in range(len(ow)) if ow[i] in keys]
            if not pts:
                return
            kx, ky = self.iso_scale
            cx = sum(i % W for i in pts) / float(len(pts)) * kx
            cy = sum(i // W for i in pts) / float(len(pts)) * ky
        sr = [float(v) for v in str(c.cget("scrollregion")).split()] or [0, 0, 1, 1]
        tw, th = max(1.0, sr[2] - sr[0]), max(1.0, sr[3] - sr[1])
        c.xview_moveto(max(0.0, (cx - c.winfo_width() / 2.0) / tw))
        c.yview_moveto(max(0.0, (cy - c.winfo_height() / 2.0) / th))

    def _fill_inspector(self):
        for w in self.ins_body.winfo_children():
            w.destroy()
        a = self.doc.analysis()
        if not self.sel:
            self.raw.set("")
            self.ins_err.config(text="")
            if self.area:
                x0, y0, x1, y1 = self.area
                inside, around = self._heights(self.area)
                ttk, tk = self.ttk, self.tk
                ttk.Label(self.ins_body, text="Make it:").grid(row=0, column=0, sticky="w")
                bf = ttk.Frame(self.ins_body)
                bf.grid(row=0, column=1, sticky="w")
                for k, nm in enumerate(("Floor", "Ramp", "Wall", "Hole", "Goal")):
                    ttk.Button(bf, text=nm, width=6, command=lambda nm=nm: self.add_part(nm)).grid(
                        row=k // 3, column=k % 3, padx=1, pady=1)
                ttk.Label(self.ins_body, text="Cut a corner:").grid(row=2, column=0, sticky="w")
                cf_ = ttk.Frame(self.ins_body)
                cf_.grid(row=2, column=1, sticky="w")
                for k, (lab, corner) in enumerate((("\u2196", "nw"), ("\u2197", "ne"), ("\u2199", "sw"),
                                                   ("\u2198", "se"))):
                    ttk.Button(cf_, text=lab, width=3, command=lambda c_=corner: self.cut_corner(c_)).grid(
                        row=0, column=k, padx=1)
                ttk.Label(self.ins_body, text="Diagonal strip:").grid(row=3, column=0, sticky="w")
                df_ = ttk.Frame(self.ins_body)
                df_.grid(row=3, column=1, sticky="w")
                ttk.Button(df_, text="\u2198 down the screen", command=lambda: self.diagonal_strip("down")).grid(
                    row=0, column=0, padx=1)
                ttk.Button(df_, text="\u2197 across", command=lambda: self.diagonal_strip("across")).grid(
                    row=0, column=1, padx=1)
                ttk.Label(self.ins_body, text="Paint:").grid(row=1, column=0, sticky="w")
                pf_ = ttk.Frame(self.ins_body)
                pf_.grid(row=1, column=1, sticky="w")
                for k, nm in enumerate(("Ice", "Sand", "Bounce mat", "Normal")):
                    ttk.Button(pf_, text=nm.split()[0], width=6, command=lambda nm=nm: self.add_part(nm)).grid(
                        row=0, column=k, padx=1)
                self.ins_title.config(text="An area, %d x %d" % (x1 - x0 + 1, y1 - y0 + 1))
                self.ins_line.config(text="from (%d, %d) to (%d, %d)" % (x0, y0, x1, y1))
                self.ins_help.config(text="%s\n\nMake it replaces just these cells (the floor around keeps "
                                     "its height). Or choose any part on the left and press Add. Delete removes "
                                     "every part lying wholly inside the area." % ("Floor here: up to %g units high." % inside if inside is not None
                                                   else "Empty space%s." % (
                                                       ", next to floor %g units high" % around
                                                       if around is not None else "")))
            else:
                self.ins_title.config(text="Nothing selected")
                self.ins_line.config(text="")
                self.ins_help.config(text="Click a part on the course to edit it, or drag across the course to "
                                     "choose an area to add to. You can also type a whole statement below and "
                                     "press Apply.")
            return
        if len(self.sels) > 1:
            return self._fill_multi()
        try:
            st = self.doc.statement(self.sel)
        except E.EditError:
            self.sel = None
            return self._fill_inspector()
        self.ins_title.config(text=_plain_kind(st))
        self.ins_line.config(text="line %d%s" % (st.line, ("   " + st.comment.strip()) if st.comment.strip() else ""))
        self.raw.set(st.code)
        ttk, tk = self.ttk, self.tk
        body = self.ins_body
        slots = E.coord_slots(st.toks)
        row = 0
        if st.kind in E.SHAPED:                 # the ramp's span is the Slope's to keep in step, not a point
            cut = min([st.toks.index(w) for w in ("ramp", "flat") if w in st.toks] or [len(st.toks)])
            slots = [q for q in slots if q[0] < cut]
        if slots:
            pairs = [slots[k:k + 2] for k in range(0, len(slots), 2)]
            names = {1: ["At"], 2: ["From", "To"]}.get(len(pairs), ["Point %d" % (k + 1) for k in range(len(pairs))])
            if st.kind == "tube":
                names = ["In", "Out"] + ["Via"] * 4
            for k, pr in enumerate(pairs[:6]):
                ttk.Label(body, text=names[k] if k < len(names) else "Point").grid(row=row, column=0, sticky="w")
                fr = ttk.Frame(body)
                fr.grid(row=row, column=1, sticky="w")
                for i, ax in pr:
                    v = tk.StringVar(value=st.toks[i])
                    ttk.Label(fr, text=ax).pack(side="left")
                    sp = ttk.Spinbox(fr, from_=-999, to=999, width=4, textvariable=v,
                                     command=lambda i=i, v=v: self._set_word(i, v.get()))
                    sp.pack(side="left", padx=(1, 6))
                    sp.bind("<Return>", lambda e, i=i, v=v: self._set_word(i, v.get()))
                row += 1
            ttk.Label(body, text="Drag it on the plan, or use the arrow keys.", foreground="#666").grid(
                row=row, column=0, columnspan=2, sticky="w")
            row += 1
        row = self._slope_rows(st, body, row)
        if st.kind == "way":
            row = self._route_rows(st, body, row)
        for word, n, label in (("flat", 1, "Height"), ("top", 1, "Water top"), ("bed", 1, "Water bed"),
                               ("period", 1, "Period (steps)"), ("on", 1, "On for (steps)"),
                               ("seed", 1, "Starts at"), ("strength", 1, "Strength"), ("range", 1, "Range"),
                               ("for", 1, "Seconds"), ("depth", 1, "Depth (px)"), ("radius", 1, "Radius"),
                               ("pivot", 1, "Pivot height"), ("height", 1, "Height"), ("kick", 1, "Kick"),
                               ("dwell", 1, "Wait at each end"), ("under", 1, "Clearance (units)")):
            if word in st.toks[1:]:
                i = st.toks.index(word, 1) + n
                if i < len(st.toks):
                    v = tk.StringVar(value=st.toks[i])
                    ttk.Label(body, text=label).grid(row=row, column=0, sticky="w")
                    sp = ttk.Spinbox(body, from_=-999, to=9999, increment=0.5 if word == "flat" else 1, width=7,
                                     textvariable=v, command=lambda i=i, v=v: self._set_word(i, v.get()))
                    sp.grid(row=row, column=1, sticky="w")
                    sp.bind("<Return>", lambda e, i=i, v=v: self._set_word(i, v.get()))
                    row += 1
        for word, choices, label in (("face", ("+x", "-x", "+y", "-y"), "Faces"),
                                     ("along", ("x", "y"), "Runs along"),
                                     ("channel", B.GT_CHANNELS, "Channel"),
                                     ("style", B.GT_STYLES, "Style")):
            if word in st.toks[1:]:
                i = st.toks.index(word, 1) + 1
                if i < len(st.toks):
                    v = tk.StringVar(value=st.toks[i])
                    ttk.Label(body, text=label).grid(row=row, column=0, sticky="w")
                    cb = ttk.Combobox(body, values=choices, textvariable=v, width=8, state="readonly")
                    cb.grid(row=row, column=1, sticky="w")
                    cb.bind("<<ComboboxSelected>>", lambda e, i=i, v=v: self._set_word(i, v.get()))
                    row += 1
        if st.kind == "surface" and len(st.toks) > 1:
            v = tk.StringVar(value=st.toks[1])
            ttk.Label(body, text="Surface").grid(row=row, column=0, sticky="w")
            cb = ttk.Combobox(body, values=B.SURFACES, textvariable=v, width=8, state="readonly")
            cb.grid(row=row, column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda e, v=v: self._set_word(1, v.get()))
            row += 1
        if st.kind == "pad" and len(st.toks) > 1 and st.toks[1] in E.MATERIALS:
            v = tk.StringVar(value=st.toks[1])
            ttk.Label(body, text="Ball").grid(row=row, column=0, sticky="w")
            cb = ttk.Combobox(body, values=E.MATERIALS, textvariable=v, width=8, state="readonly")
            cb.grid(row=row, column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda e, v=v: self._set_word(1, v.get()))
            row += 1
        if st.kind in ("floor", "wall", "goal") and self._shape(st):
            fl = self._float_of(st)
            hv = tk.StringVar(value="to the ground" if not fl else "3 units" if fl[0] == 3 else "%g units" % fl[0])
            ttk.Label(body, text="Hangs down").grid(row=row, column=0, sticky="w")
            hc = ttk.Combobox(body, values=HANGS, textvariable=hv, width=13, state="readonly")
            hc.grid(row=row, column=1, sticky="w")
            hc.bind("<<ComboboxSelected>>", lambda e, v=hv: self.set_hang(v.get()))
            row += 1
            if "ramp" in st.toks:
                rf = ttk.Frame(body)
                rf.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))
                ttk.Button(rf, text="Add stepped rails", command=lambda: self.add_rails("steps")).pack(side="left")
                ttk.Button(rf, text="Smooth rails", command=lambda: self.add_rails("smooth")).pack(side="left",
                                                                                                  padx=4)
                row += 1
            cur = self._surface_of(st)
            v = tk.StringVar(value=cur[0] if cur else "normal")
            ttk.Label(body, text="Surface").grid(row=row, column=0, sticky="w")
            cb = ttk.Combobox(body, values=B.SURFACES, textvariable=v, width=8, state="readonly")
            cb.grid(row=row, column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda e, v=v: self.set_surface(v.get()))
            row += 1
        if st.kind == "prop" and len(st.toks) > 1 and st.toks[1] in ("life", "speed", "jump"):
            for word, label in (("once", "Once: taken for good (one a course)"), ("respawn", "Comes back when its "
                                                                                  "effect ends"),
                                ("overwrite", "Ends the other timed effect")):
                if (word == "once") != (st.toks[1] == "life"):
                    continue
                v = tk.BooleanVar(value=word in st.toks)
                ttk.Checkbutton(body, text=label, variable=v, command=lambda w=word, v=v: self._edit(
                    self.doc.set_flag, self.sel, w, v.get())).grid(row=row, column=0, columnspan=2, sticky="w")
                row += 1
        if st.kind in B.VIS_HIDEABLE:
            v = tk.BooleanVar(value=st.toks[-1] == "hidden")
            ttk.Checkbutton(body, text="Hidden on purpose (a secret: no warning)", variable=v,
                            command=lambda v=v: self._edit(self.doc.set_flag, self.sel, "hidden", v.get())).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))
            row += 1
        hint = next((it[3] for _g, its in PALETTE for it in its if it[2].split()[0:2] == st.toks[0:2]
                     or (it[2].split()[0] == st.kind and st.kind not in ("prop", "surface", "tube", "pad"))), "")
        self.ins_help.config(text=hint)
        err = a["error"] if a["error_line"] == st.line else ""
        self.ins_err.config(text=err)

    def _fill_multi(self):
        """several parts (Ctrl-click): what they can share - a height, a surface, a hang - and Delete"""
        ttk, tk = self.ttk, self.tk
        body = self.ins_body
        sts = [self.doc.statement(l_) for l_ in self.sels]
        ground = [st for st in sts if st.kind in ("floor", "wall", "goal") and self._shape(st)]
        self.ins_title.config(text="%d parts selected" % len(sts))
        self.ins_line.config(text=", ".join(sorted({_plain_kind(st) for st in sts})))
        self.raw.set("")
        self.ins_err.config(text="")
        self.ins_help.config(text="Ctrl-click (Command-click on a Mac) adds or removes a part. Changes here "
                             "apply to every selected floor, wall or goal; Delete removes them all.")
        row = 0
        if ground:
            flats = [float(st.toks[st.toks.index("flat") + 1]) for st in ground if "flat" in st.toks]
            hv = tk.StringVar(value="%g" % flats[0] if flats else "")
            ttk.Label(body, text="Height").grid(row=row, column=0, sticky="w")
            fr = ttk.Frame(body)
            fr.grid(row=row, column=1, sticky="w")
            sp = ttk.Spinbox(fr, from_=-60, to=60, increment=0.5, width=6, textvariable=hv)
            sp.pack(side="left")
            ttk.Button(fr, text="Set", width=4, command=lambda: self.multi_height(set_to=hv.get())).pack(side="left")
            row += 1
            ttk.Label(body, text="Raise").grid(row=row, column=0, sticky="w")
            fr2 = ttk.Frame(body)
            fr2.grid(row=row, column=1, sticky="w")
            for d_ in (-1, -0.5, 0.5, 1):
                ttk.Button(fr2, text="%+g" % d_, width=4, command=lambda d_=d_: self.multi_height(by=d_)).pack(
                    side="left")
            row += 1
            sv = tk.StringVar(value="")
            ttk.Label(body, text="Surface").grid(row=row, column=0, sticky="w")
            cb = ttk.Combobox(body, values=B.SURFACES, textvariable=sv, width=8, state="readonly")
            cb.grid(row=row, column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda e: self.multi_surface(sv.get()))
            row += 1
            hv2 = tk.StringVar(value="")
            ttk.Label(body, text="Hangs down").grid(row=row, column=0, sticky="w")
            hc = ttk.Combobox(body, values=HANGS, textvariable=hv2, width=13, state="readonly")
            hc.grid(row=row, column=1, sticky="w")
            hc.bind("<<ComboboxSelected>>", lambda e: self.set_hang(hv2.get()))
            row += 1

    def multi_height(self, set_to=None, by=None):
        """every selected floor, wall and goal: a flat one to SET_TO, or every height (a ramp's two ends) BY"""
        lines = list(self.sels)

        def f(v):
            return ("%d" % v) if v == int(v) else ("%g" % v)

        def go():
            with self.doc.group("heights"):
                for ln in lines:
                    st = self.doc.statement(ln)
                    t = list(st.toks)
                    if "flat" in t:
                        i = t.index("flat") + 1
                        t[i] = f(float(set_to)) if set_to not in (None, "") else f(float(t[i]) + (by or 0))
                    elif "ramp" in t and by:
                        j = t.index("ramp")
                        t[j + 4], t[j + 5] = f(float(t[j + 4]) + by), f(float(t[j + 5]) + by)
                    else:
                        continue
                    self.doc.set_tokens(ln, t)
            return True
        self._edit(go)
        self._fill_inspector()

    def multi_surface(self, surf):
        lines = list(self.sels)

        def go():
            with self.doc.group("surfaces"):
                for ln in lines:
                    st = self.doc.statement(ln)
                    sh = self._shape(st)
                    if not sh:
                        continue
                    x0, y0, x1, y1 = sh[2]
                    self.doc.replace_area((x0, y0, x1 - 1, y1 - 1), kinds=(), surfaces=True,
                                          ground=[] if surf == "normal" else ["surface %s %s" % (surf, " ".join(
                                              sh[1]))])
            return True
        self._edit(go)
        self._fill_inspector()

    def add_rails(self, style):
        """RAILS beside the selected ramp, on both its long sides: walls 1.5 units over the ramp beside them,
        STEPPED (a wall a tile, each at the ramp's height there, joined where equal) or SMOOTH (one ramped wall,
        the ramp's plane raised). The cells they take are cut out of whatever was there"""
        st = self.doc.statement(self.sel)
        sh = self._shape(st)
        if not sh or "ramp" not in st.toks:
            return
        x0, y0, x1, y1 = sh[2]
        j = st.toks.index("ramp")
        ax, p0, p1, h0, h1 = st.toks[j + 1], int(st.toks[j + 2]), int(st.toks[j + 3]), float(st.toks[j + 4]), \
            float(st.toks[j + 5])
        if ax not in ("x", "y"):
            return
        RAIL = 1.5

        def hat(p):                             # the ramp's height at position p along its axis
            return h0 + (h1 - h0) * (p - p0) / float(p1 - p0)

        def f(v):
            return ("%d" % v) if v == int(v) else ("%g" % v)
        sides = [(x0, y0 - 1, x1, y0), (x0, y1, x1, y1 + 1)] if ax == "x" else [(x0 - 1, y0, x0, y1), (x1, y0, x1 + 1, y1)]
        walls, cuts = [], []
        for (a0, b0, a1, b1) in sides:
            cuts.append((a0, b0, a1 - 1, b1 - 1))
            if style == "smooth":
                walls.append("wall rect %d %d %d %d ramp %s %d %d %s %s" % (a0, b0, a1, b1, ax, p0, p1, f(h0 + RAIL),
                                                                          f(h1 + RAIL)))
                continue
            lo, hi = (a0, a1) if ax == "x" else (b0, b1)
            run = []
            for p in range(lo, hi):
                h = max(hat(p), hat(p + 1)) + RAIL
                h = -(-h * 2 // 1) / 2.0                 # up to the half unit
                if run and run[-1][2] == h:
                    run[-1][1] = p + 1
                else:
                    run.append([p, p + 1, h])
            for q0, q1, h in run:
                walls.append(("wall rect %d %d %d %d flat %s" % (q0, b0, q1, b1, f(h))) if ax == "x" else
                             ("wall rect %d %d %d %d flat %s" % (a0, q0, a1, q1, f(h))))

        def go():
            with self.doc.group("rails"):
                self.doc.replace_area(cuts, ground=walls, surfaces=True)
            return True
        if self._edit(go):
            self._msg("Added %d rail walls beside the ramp, %g units over it" % (len(walls), RAIL))

    def _shape(self, st):
        """(index of the shape word, the shape's tokens, (x0, y0, x1, y1) end-exclusive) of a floor, wall or
        goal laid by `tile` or `rect`, or None"""
        t = st.toks
        i = 1
        if i + 1 < len(t) and t[i] in ("half", "quarter"):
            i += 2
        if i < len(t) and t[i] == "tile" and i + 2 < len(t):
            x, y = int(t[i + 1]), int(t[i + 2])
            return i, t[i:i + 3], (x, y, x + 1, y + 1)
        if i < len(t) and t[i] == "rect" and i + 4 < len(t):
            x0, y0, x1, y1 = (int(t[i + k]) for k in range(1, 5))
            return i, t[i:i + 5], (x0, y0, x1, y1)
        return None

    def _slope_rows(self, st, body, row):
        """Flat or Ramp, for a floor, wall or goal: a ramp rises toward one side, from Low to High"""
        tk, ttk = self.tk, self.ttk
        sh = self._shape(st) if st.kind in ("floor", "wall", "goal") else None
        t = st.toks
        if not sh or not ("flat" in t or "ramp" in t):
            return row
        ttk.Label(body, text="Slope").grid(row=row, column=0, sticky="w")
        mode = tk.StringVar(value="Ramp" if "ramp" in t else "Flat")
        cb = ttk.Combobox(body, values=("Flat", "Ramp"), textvariable=mode, width=8, state="readonly")
        cb.grid(row=row, column=1, sticky="w")
        row += 1
        if "ramp" in t:
            i = t.index("ramp")
            ax, p0, p1, h0, h1 = t[i + 1:i + 6]
            lo, hi = sorted((float(h0), float(h1)))
            rises = {("x", True): "the right (+x)", ("x", False): "the left (-x)", ("y", True): "the bottom (+y)",
                     ("y", False): "the top (-y)"}.get((ax, float(h1) >= float(h0)), "")
        else:
            i = t.index("flat")
            lo = float(t[i + 1])
            hi = lo + 1
            rises = "the right (+x)"
        if "ramp" in t:
            dv = tk.StringVar(value=rises)
            lv, hv = tk.StringVar(value="%g" % lo), tk.StringVar(value="%g" % hi)
            ttk.Label(body, text="Rises toward").grid(row=row, column=0, sticky="w")
            dcb = ttk.Combobox(body, values=("the right (+x)", "the left (-x)", "the bottom (+y)", "the top (-y)"),
                               textvariable=dv, width=14, state="readonly")
            dcb.grid(row=row, column=1, sticky="w")
            row += 1
            for lab, var in (("Low end", lv), ("High end", hv)):
                ttk.Label(body, text=lab).grid(row=row, column=0, sticky="w")
                sp = ttk.Spinbox(body, from_=-60, to=60, increment=0.5, width=6, textvariable=var,
                                 command=lambda: self.set_slope("Ramp", dv.get(), lv.get(), hv.get()))
                sp.grid(row=row, column=1, sticky="w")
                sp.bind("<Return>", lambda e: self.set_slope("Ramp", dv.get(), lv.get(), hv.get()))
                row += 1
            dcb.bind("<<ComboboxSelected>>", lambda e: self.set_slope("Ramp", dv.get(), lv.get(), hv.get()))
        cb.bind("<<ComboboxSelected>>", lambda e: self.set_slope(mode.get(), rises, "%g" % lo, "%g" % hi))
        return row

    def set_slope(self, mode, rises, low, high):
        """rewrite the selected floor's height clause: `flat LOW`, or `ramp AXIS P0 P1 H0 H1` across its shape"""
        st = self.doc.statement(self.sel)
        sh = self._shape(st)
        if not sh:
            return
        x0, y0, x1, y1 = sh[2]
        t = list(st.toks)
        for w, n in (("flat", 2), ("ramp", 6)):
            if w in t:
                i = t.index(w)
                del t[i:i + n]
                break
        else:
            i = len(t)
        try:
            lo, hi = float(low), float(high)
        except ValueError:
            return
        if mode != "Flat":                      # a ramp rises a whole number of half units a tile
            ax_ = "y" if "bottom" in rises or "top" in rises else "x"
            n = (y1 - y0) if ax_ == "y" else (x1 - x0)
            rate = max(0.5, round((hi - lo) / float(n) * 2) / 2.0) if n else 0.5
            if lo + rate * n != hi:
                self._msg("High end set to %g: a ramp rises a whole number of half units on each of its %d "
                          "tiles" % (lo + rate * n, n))
            hi = lo + rate * n

        def f(v):
            return ("%d" % v) if v == int(v) else ("%g" % v)
        if mode == "Flat":
            t[i:i] = ["flat", f(lo)]
        else:
            ax = "y" if "bottom" in rises or "top" in rises else "x"
            p0, p1 = (y0, y1) if ax == "y" else (x0, x1)
            up = "right" in rises or "bottom" in rises
            t[i:i] = ["ramp", ax, str(p0), str(p1), f(lo if up else hi), f(hi if up else lo)]
        self._edit(self.doc.set_tokens, self.sel, t, label="the slope")

    def _surface_of(self, st):
        """the `surface` statement painted over exactly this floor's shape: (surface, its line), or None"""
        sh = self._shape(st)
        if not sh:
            return None
        for s_ in self.doc.statements():
            if s_.kind == "surface" and len(s_.toks) > 2 and s_.toks[2:] == list(sh[1]):
                return s_.toks[1], s_.line
        return None

    def set_surface(self, surf):
        st = self.doc.statement(self.sel)
        sh = self._shape(st)
        cur = self._surface_of(st)
        line = self.sel
        if cur and surf == "normal":
            self._edit(self.doc.remove, cur[1], label="the surface")
        elif cur:
            self._edit(self.doc.set_word, cur[1], 1, surf, label="the surface")
        elif surf != "normal":
            self._edit(self.doc.insert, "surface %s %s" % (surf, " ".join(sh[1])), label="the surface")
        self.select(line if line <= len(self.doc.lines) else None)

    def _companions(self, line):
        """the lines that travel with LINE: a floor's, wall's or goal's own `surface` (the same shape)"""
        try:
            st = self.doc.statement(line)
        except E.EditError:
            return []
        cur = self._surface_of(st) if st.kind in ("floor", "wall", "goal") else None
        fl = self._float_of(st) if st.kind in ("floor", "wall", "goal") else None
        return ([cur[1]] if cur else []) + ([fl[1]] if fl else [])

    # -- the route (SPEC.md 130.58.22) ---------------------------------------------
    def _ways(self):
        """every `way` statement in file order: [(line, x, y, branch or None)]"""
        out = []
        for st in self.doc.statements():
            if st.kind == "way" and len(st.toks) >= 3:
                try:
                    br = st.toks[st.toks.index("branch") + 1] if "branch" in st.toks else None
                    out.append((st.line, int(st.toks[1]), int(st.toks[2]), br))
                except (ValueError, IndexError):
                    pass
        return out

    def _route_rows(self, st, body, row):
        """a route point's panel: the whole route listed (a click selects a point), and its edits"""
        tk, ttk = self.tk, self.ttk
        ways = self._ways()
        mine = next((w for w in ways if w[0] == st.line), None)
        same = [w for w in ways if mine and w[3] == mine[3]]
        k = same.index(mine) if mine in same else 0
        ttk.Label(body, text="Route point %d of %d%s" % (k + 1, len(same), (" (branch %s)" % mine[3]) if mine and
                                                          mine[3] else ""), font=("TkDefaultFont", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        row += 1
        lb = tk.Listbox(body, height=min(10, max(3, len(ways))), width=34, exportselection=False)
        start = next((s_ for s_ in self.doc.statements() if s_.kind == "start"), None)
        lb.insert("end", "start  %s" % " ".join(start.toks[1:3]) if start else "start  (none)")
        n = {}
        for i, (ln, x, y, br) in enumerate(ways):
            n[br] = n.get(br, 0) + 1
            lb.insert("end", "%2d.  %d, %d%s   (line %d)" % (n[br], x, y, ("   branch %s" % br) if br else "", ln))
            if ln == st.line:
                lb.selection_set(i + 1)
                lb.see(i + 1)
        lb.grid(row=row, column=0, columnspan=2, sticky="we")
        lb.bind("<<ListboxSelect>>", lambda e: lb.curselection() and lb.curselection()[0] > 0 and self.select(
            ways[lb.curselection()[0] - 1][0], scroll=True))
        row += 1
        fr = ttk.Frame(body)
        fr.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Button(fr, text="Insert one after", command=lambda: self.route_insert(st.line)).pack(side="left")
        ttk.Button(fr, text="Earlier", width=7, command=lambda: self.route_shift(st.line, -1)).pack(side="left")
        ttk.Button(fr, text="Later", width=6, command=lambda: self.route_shift(st.line, 1)).pack(side="left")
        ttk.Button(fr, text="Delete", width=7, command=self.delete).pack(side="left")
        row += 1
        ttk.Label(body, text="With Route on, drag a point on the plan. An edit that leaves a point off the floor "
                            "moves it to the nearest floor by itself.", foreground="#666", wraplength=300).grid(
            row=row, column=0, columnspan=2, sticky="w")
        return row + 1

    def route_insert(self, line):
        """a route point after LINE's: halfway to the next point of its route (or one cell on past it), on floor"""
        ways = self._ways()
        me = next(w for w in ways if w[0] == line)
        same = [w for w in ways if w[3] == me[3]]
        i = same.index(me)
        if i + 1 < len(same):
            nx, ny = (me[1] + same[i + 1][1]) // 2, (me[2] + same[i + 1][2]) // 2
        elif i > 0:
            nx, ny = 2 * me[1] - same[i - 1][1], 2 * me[2] - same[i - 1][2]
        else:
            nx, ny = me[1] + 1, me[2]
        code = "way %d %d%s" % (nx, ny, (" branch %s" % me[3]) if me[3] else "")
        ln = self._edit(self.doc.insert, code, after=line, label="insert a route point")
        if ln:
            self.select(ln)

    def route_shift(self, line, d):
        """a route point one place earlier (D -1) or later (+1) in its route: two lines swap their text"""
        ways = self._ways()
        me = next(w for w in ways if w[0] == line)
        same = [w for w in ways if w[3] == me[3]]
        j = same.index(me) + d
        if not 0 <= j < len(same):
            return
        other = same[j][0]
        a_, b_ = self.doc.statement(line).code, self.doc.statement(other).code
        if self._edit(self.doc.set_many, {line: b_, other: a_}, label="reorder the route"):
            self.select(other)

    # -- drag resizing (SPEC.md 130.58.22) -----------------------------------------
    def _resizable(self):
        """the one selected floor, wall, goal or hole laid by `tile` or `rect`: (statement, shape, rect), or None"""
        if not self.sel or len(self.sels) > 1 or self.view.get() != "plan":
            return None
        try:
            st = self.doc.statement(self.sel)
        except E.EditError:
            return None
        sh = self._shape(st) if st.kind in ("floor", "wall", "goal", "hole") else None
        return (st, sh, sh[2]) if sh else None

    def _handles(self, rect):
        """the eight resize handles of RECT (end-exclusive cells): [(name, canvas x, canvas y)]"""
        x0, y0, x1, y1 = rect
        ax, ay = self._cpx(x0, y0)
        bx, by = self._cpx(x1, y1)
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        return [("nw", ax, ay), ("n", mx, ay), ("ne", bx, ay), ("e", bx, my), ("se", bx, by), ("s", mx, by),
                ("sw", ax, by), ("w", ax, my)]

    def _handle_at(self, e):
        rz = self._resizable()
        if not rz:
            return None
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        for h, hx, hy in self._handles(rz[2]):
            if abs(hx - x) <= 7 and abs(hy - y) <= 7:
                return h
        return None

    def _resize_motion(self, e):
        d = self.drag
        s = CELL * self.zoom
        gx = int(round(self.cv.canvasx(e.x) / s)) + self.origin[0]      # (the nearest grid LINE)
        gy = int(round(self.cv.canvasy(e.y) / s)) + self.origin[1]
        x0, y0, x1, y1 = d["orig"]
        h = d["resize"]
        if "w" in h:
            x0 = min(gx, x1 - 1)
        if "e" in h:
            x1 = max(gx, x0 + 1)
        if "n" in h:
            y0 = min(gy, y1 - 1)
        if "s" in h:
            y1 = max(gy, y0 + 1)
        if (x0, y0, x1, y1) != d["rect"]:
            d["rect"] = (x0, y0, x1, y1)
            self._draw_plan()

    def resize_sel(self, rect):
        """the selected floor, wall, goal or hole laid over RECT (end-exclusive) instead: it cuts its way into
        what is there (as a move does), a ramp keeps its slope along its run (its span and end heights follow the
        new extent), its own surface and hang go with it, and the floor round it is rejoined"""
        st, sh, old = self._resizable()
        x0, y0, x1, y1 = rect
        shape = ["tile", str(x0), str(y0)] if (x1 - x0, y1 - y0) == (1, 1) else ["rect"] + [str(v) for v in rect]

        def reshaped(t, si, n):
            return E.reshape(t, si, n, rect)
        code = reshaped(st.toks, sh[0], len(sh[1]))
        comp = []
        for ln in self._companions(self.sel):
            cs = self.doc.statement(ln)
            csh = None if cs.kind == "surface" else self._shape(cs)
            if cs.kind == "surface":
                comp.append(E.join_tokens(cs.toks[:2] + shape))
            elif csh:
                comp.append(reshaped(cs.toks, csh[0], len(csh[1])))
        dest = (x0, y0, x1 - 1, y1 - 1)

        def go():
            with self.doc.group("resize %s" % st.kind):
                for ln in sorted([self.sel] + self._companions(self.sel), reverse=True):
                    self.doc.remove(ln)
                self.doc.replace_area(dest, ground=[code], surfaces=st.kind in ("wall", "hole"))
                for cc in comp:
                    self.doc.replace_area(dest, ground=[cc], kinds=(), surfaces=cc.startswith("surface"))
                self.doc.tidy((min(old[0], x0), min(old[1], y0), max(old[2], x1) - 1, max(old[3], y1) - 1))
            return True
        if self._edit(go):
            ln = next((s_.line for s_ in self.doc.statements() if s_.code == code), None)
            self.area = dest
            self.select(ln)
            self._msg("Resized to %d x %d" % (x1 - x0, y1 - y0))

    def _way_at(self, e):
        """the route point under the pointer on the plan (Route on), or None"""
        if self.view.get() != "plan" or not self.show_route.get():
            return None
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        s = CELL * self.zoom
        for ln, wx, wy, _br in self._ways():
            px, py = self._cpx(wx + .5, wy + .5)
            if (px - x) ** 2 + (py - y) ** 2 <= max(6.0, s * .3) ** 2:
                return ln
        return None

    def _float_of(self, st):
        """the `float` statement over exactly this shape: (its thickness in units, its line), or None"""
        sh = self._shape(st)
        if not sh:
            return None
        for s_ in self.doc.statements():
            if s_.kind == "float" and s_.toks[1:1 + len(sh[1])] == list(sh[1]):
                rest = s_.toks[1 + len(sh[1]):]
                return (float(rest[1]) if rest[:1] == ["thick"] else 3.0), s_.line
        return None

    def set_hang(self, how):
        """`Hangs down`: to the ground (no float), or so many units (`float <shape> [thick N]`)"""
        lines = [l_ for l_ in (self.sels or [self.sel]) if l_]

        def go():
            with self.doc.group("hangs down"):
                for ln in sorted(lines, reverse=True):
                    st = self.doc.statement(ln)
                    sh = self._shape(st)
                    if not sh or st.kind not in ("floor", "wall", "goal"):
                        continue
                    cur = self._float_of(st)
                    code = None if how == "to the ground" else "float %s%s" % (
                        " ".join(sh[1]), "" if how == "3 units" else " thick %s" % how.split()[0])
                    if cur and code:
                        self.doc.set_statement(cur[1], code)
                    elif cur:
                        self.doc.remove(cur[1])
                    elif code:
                        self.doc.replace_area(None, ground=[code])
            return True
        self._edit(go)

    def move_sel(self, dx, dy):
        """move the selection. GROUND (a floor, wall, goal or hole laid by tile or rect) moves as one layer:
        its old cells are left empty, it cuts its way into the cells it lands on, a flat floor or goal takes
        the height of the floor it lands on, its own surface and hang go with it, and the floor round it is
        rejoined (SPEC.md 130.58.14)"""
        st = self.doc.statement(self.sel)
        sh = self._shape(st) if st.kind in ("floor", "wall", "goal", "hole") else None
        if not sh:
            lines = [self.sel] + self._companions(self.sel)
            self._edit(self.doc.move_many, lines, dx, dy, label="move")
            return
        x0, y0, x1, y1 = sh[2]
        dest = (x0 + dx, y0 + dy, x1 - 1 + dx, y1 - 1 + dy)
        a = self.doc.analysis()
        under = [d["hmax"] for (x, y), d in a["cells"].items() if dest[0] <= x <= dest[2] and dest[1] <= y <= dest[3]
                 and d["line"] != self.sel and d["kind"] in ("floor", "goal", "field")]
        toks = self.doc.moved_code(self.sel, dx, dy).split()
        if under and st.kind in ("floor", "goal") and "flat" in toks:
            h = max(under)
            toks[toks.index("flat") + 1] = ("%d" % h) if h == int(h) else ("%g" % h)
        code = E.join_tokens(toks)
        comp = [(ln, self.doc.moved_code(ln, dx, dy)) for ln in self._companions(self.sel)]
        ways = self.doc.ways_in(sh[2], ("way", "start", "checkpoint")) if st.kind in ("floor", "goal") else []
        # (what stands on it rides along: its route points, the start, a flag - SPEC.md 130.58.22)

        def mv():
            with self.doc.group("move %s" % st.kind):
                for ln in sorted([self.sel] + [c for c, _ in comp], reverse=True):
                    self.doc.remove(ln)
                self.doc.replace_area(dest, ground=[code], surfaces=st.kind in ("wall", "hole"))
                for _ln, cc in comp:
                    self.doc.replace_area(dest, ground=[cc], kinds=(), surfaces=cc.startswith("surface"))
                self.doc.tidy((min(x0, dest[0]), min(y0, dest[1]), max(x1 - 1, dest[2]), max(y1 - 1, dest[3])))
                done = set()
                for _ln, wc in ways:                # (found again by their text: the lines above moved)
                    w = next((s_ for s_ in self.doc.statements() if s_.code == wc and s_.line not in done), None)
                    if w:
                        done.add(w.line)
                        self.doc.set_statement(w.line, self.doc.moved_code(w.line, dx, dy))
            return True
        if self._edit(mv):
            ln = next((s_.line for s_ in self.doc.statements() if s_.code == code), None)
            self.area = dest
            self.select(ln)
            rode = sorted({wc.split()[0] for _l, wc in ways})
            names = {"way": "its route points", "start": "the start", "checkpoint": "its flag"}
            self._msg("Moved%s%s" % ((", with " + " and ".join(names[k] for k in rode)) if rode else "",
                                    ("; it took the height of the floor it landed on (%g)" % max(under))
                                    if under and st.kind in ("floor", "goal") else ""))

    def _set_word(self, i, value):
        if not self.sel:
            return
        st = self.doc.statement(self.sel)
        comp = self._companions(self.sel)
        if comp and self._shape(st) and i < self._shape(st)[0] + len(self._shape(st)[1]):
            # a corner of a floor with its own surface: the surface's shape follows, in the same edit
            t = list(st.toks)
            t[i] = value.strip()
            sh0 = self._shape(st)
            new_shape = t[sh0[0]:sh0[0] + len(sh0[1])]
            sf = self.doc.statement(comp[0])
            codes = {comp[0]: E.join_tokens(sf.toks[:2] + new_shape)}
            if "ramp" in t:
                j = t.index("ramp")
                ax = t[j + 1]
                sh = self._shape(E.Statement(0, " ".join(t)))
                if sh and ax in ("x", "y"):
                    x0, y0, x1, y1 = sh[2]
                    on = int(t[j + 3]) - int(t[j + 2])
                    nn = (y1 - y0) if ax == "y" else (x1 - x0)
                    rate = (float(t[j + 5]) - float(t[j + 4])) / on if on else 0
                    t[j + 2:j + 4] = [str(y0), str(y1)] if ax == "y" else [str(x0), str(x1)]
                    e = float(t[j + 4]) + rate * nn
                    t[j + 5] = ("%d" % e) if e == int(e) else ("%g" % e)
            codes[self.sel] = E.join_tokens(t)
            self._edit(self.doc.set_many, codes, label="the corners")
            return
        if "ramp" in st.toks and self._shape(st) and i < st.toks.index("ramp"):
            # a corner of a ramped floor: the ramp's span follows it, in the same edit
            t = list(st.toks)
            t[i] = value.strip()
            j = t.index("ramp")
            ax, h0, h1 = t[j + 1], t[j + 4], t[j + 5]
            sh = self._shape(E.Statement(0, " ".join(t)))
            if sh and ax in ("x", "y"):
                x0, y0, x1, y1 = sh[2]
                on = int(t[j + 3]) - int(t[j + 2])
                nn = (y1 - y0) if ax == "y" else (x1 - x0)
                t[j + 2:j + 4] = [str(y0), str(y1)] if ax == "y" else [str(x0), str(x1)]
                if on and nn:                   # the same steepness over the new length
                    rate = (float(h1) - float(h0)) / on
                    e = float(h0) + rate * nn
                    t[j + 5] = ("%d" % e) if e == int(e) else ("%g" % e)
            self._edit(self.doc.set_tokens, self.sel, t, label="the corners")
            return
        self._edit(self.doc.set_word, self.sel, i, value.strip())

    # -- the course tab and the source --------------------------------------------
    def _fill_course(self):
        sts = {s.kind: s for s in self.doc.statements()}

        def tok(kind, i, d=""):
            s = sts.get(kind)
            return s.toks[i] if s and len(s.toks) > i else d
        self.cv_name.set(tok("course", 1))
        self.cv_title.set(tok("course", 2).strip('"'))
        self.cv_width.set(tok("width", 1, "64"))
        self.cv_ball.set(tok("ball", 1, "rubber"))
        self.cv_music.set(tok("music", 1, "(default)"))
        p = sts.get("palette")
        self.cv_pal.set(" ".join(p.toks[1:]) if p else "(default)")
        self.cv_gstyle.set(tok("gatestyle", 1, "(default)"))
        self.cv_target.set(tok("target", 1, "(none)"))
        self.cv_limit.set(tok("limit", 1))
        self.cv_gold.set(tok("medals", 1))
        self.cv_silver.set(tok("medals", 2))
        self.cv_cstrict.set("strict" in sts)

    def _fill_source(self):
        t = self.src_t
        t.configure(state="normal")
        t.delete("1.0", "end")
        for i, ln in enumerate(self.doc.lines, 1):
            t.insert("end", "%5d  %s\n" % (i, ln))
            if ln.lstrip().startswith("#"):
                t.tag_add("cmt", "%d.0" % i, "%d.end" % i)
        a = self.doc.analysis()
        if a["error_line"]:
            t.tag_add("err_line", "%d.0" % a["error_line"], "%d.end" % a["error_line"])
        if self.sel:
            t.tag_add("sel_line", "%d.0" % self.sel, "%d.end" % self.sel)
            t.see("%d.0" % self.sel)
        t.configure(state="disabled")

    def _src_pick(self, e):
        line = int(self.src_t.index("@%d,%d" % (e.x, e.y)).split(".")[0])
        if 1 <= line <= len(self.doc.lines) and self.doc.lines[line - 1].strip() \
                and not self.doc.lines[line - 1].lstrip().startswith("#"):
            self.select(line)
            self.nb.select(0)

    def _tab_changed(self):
        if getattr(self, "shapes", None) and self.shapes.shown():
            try:
                if self.sel and self.doc.statement(self.sel).kind in ("chute", "pit", "hump"):
                    self.shapes.line = self.sel         # (the shape selected on the Build tab, shown)
            except E.EditError:
                pass
            self.shapes.refresh()
        if getattr(self, "map", None) and self.map.shown():
            self.map.refresh()

    # -- problems -----------------------------------------------------------------
    def _problems(self):
        """[(tag, text, line, cell)]: the analysis's error, the last check's errors and warnings, and the
        picture's visibility marks below their share"""
        out = []
        a = self.doc.analysis()
        if a["error"]:
            out.append(("err", a["error"], a["error_line"], None))
        if self.check and self.check.get("text") == self.doc.text():
            r = self.check["result"]
            if not r.get("ok") and r.get("error") and r.get("error") != a["error"]:
                out.append(("err", r["error"], E._line_of(r["error"]), None))
            for w in r.get("warnings", []):
                out.append(("acc" if w["accepted"] else "warn", ("accepted: " if w["accepted"] else "") + w["msg"],
                            w["line"], tuple(w["cell"]) if w.get("cell") else None))
        if self.pic and self.pic.get("text") == self.doc.text():
            for m in self.pic["meta"]["marks"]:
                if m["below"] or m["pct"] < 100:
                    cov = ", ".join("(%d, %d)" % (c[0], c[1]) for c in m["cover"][:3])
                    tag = "warn" if m["below"] else "acc"
                    out.append((tag, "%s at (%d, %d) is %d%% visible (needs %d%%)%s" % (
                        m["what"], m["cell"][0], m["cell"][1], m["pct"], m["need"],
                        "; in front: " + cov if cov else ""), m["line"], tuple(m["cell"])))
        return out

    def _fill_problems(self):
        self.probs.delete(*self.probs.get_children())
        self.prob_rows = {}
        probs = self._problems()
        nerr = sum(1 for p in probs if p[0] == "err")
        nwarn = sum(1 for p in probs if p[0] == "warn")
        for tag, text, line, cell in probs:
            if tag == "err":
                ex = explain(text)
                text = ex.split("\n")[0] if ex != text else text
            iid = self.probs.insert("", "end", text=("ERROR   " if tag == "err" else "warning  " if tag == "warn"
                                                     else "note     ") + text, tags=(tag,))
            self.prob_rows[iid] = (line, cell)
        if not probs:
            self.probs.insert("", "end", text="No problems found" + ("" if self.check else
                                                                     " yet (the full check runs after you stop "
                                                                     "editing)"), tags=("ok",))
        self.badge_err.config(text="%d error%s" % (nerr, "" if nerr == 1 else "s") if nerr else "")
        self.badge_warn.config(text="%d warning%s" % (nwarn, "" if nwarn == 1 else "s") if nwarn else "")
        self._fill_checks(probs)

    def _fill_checks(self, probs):
        t = self.checks
        t.delete(*t.get_children())
        self.check_rows = {}
        if self.check_job and self.check_job.running:
            self.check_l.config(text="Checking...")
        elif self.check and self.check.get("text") == self.doc.text():
            r = self.check["result"]
            self.check_l.config(text="%s - full check took %s s%s" % (
                "Builds" if r.get("ok") else "REFUSED", r.get("secs", "?"),
                " (strict)" if self.check.get("strict") else ""))
        else:
            self.check_l.config(text="Not checked since the last edit.")
        for tag, text, line, cell in probs:
            iid = t.insert("", "end", text=text, tags=(tag,))
            self.check_rows[iid] = (line, cell)
        if not probs and self.check and self.check.get("text") == self.doc.text():
            t.insert("", "end", text="Everything passes.", tags=("ok",))

    def _pick_problem(self):
        s = self.probs.selection()
        if s and s[0] in self.prob_rows:
            line, cell = self.prob_rows[s[0]]
            if line:
                self.hilite = cell
                self.select(line, scroll=True)

    def _pick_check(self):
        s = self.checks.selection()
        if s and s[0] in self.check_rows:
            line, cell = self.check_rows[s[0]]
            if line:
                self.nb.select(0)
                self.hilite = cell
                self.select(line, scroll=True)

    def _show_cell(self, cell):
        self.hilite = cell
        self._redraw()

    # -- jobs -----------------------------------------------------------------
    def _schedule_jobs(self):
        for attr in ("pic_after", "check_after"):
            if getattr(self, attr):
                self.root.after_cancel(getattr(self, attr))
                setattr(self, attr, None)
        if self.check_job:                  # an edit makes a running check stale: cancelled (130.58.8)
            self.check_job.kill()
            self.check_job = None
        a = self.doc.analysis()
        if a["src"] is None or not (a["cells"] or bbedmap.is_map(self.doc.text())):
            return
        self.pic_after = self.root.after(400, self.run_picture)
        self.check_after = self.root.after(2000, self.run_check)

    def _write_tmp(self, tag):
        p = os.path.join(self.tmp, "%s.bbc" % tag)
        with open(p, "w", encoding="ascii", newline="") as f:
            f.write(self.doc.text())
        return p

    def _name(self):
        return self.doc.path or "untitled.bbc"

    def run_picture(self):
        self.pic_after = None
        if self.pic_job:
            self.pic_job.kill()
        text = self.doc.text()
        out = os.path.join(self.tmp, "pic-%d" % int(time.time() * 1000))
        p = self._write_tmp("pic")

        def ev(job, e):
            if e["stage"] == "done":
                if e.get("ok"):
                    self._load_picture(out, text)
                elif self.view.get() == "iso":
                    self._msg("No picture: %s" % e.get("error"))
            elif e["stage"] not in ("exit", "log"):
                self.job_l.config(text="Picture: %s" % e.get("what", e["stage"]))
        self.pic_job = Job(["picture", p, out, "--name", self._name()] + (["--gaps"] if self.show_gaps.get() else []),
                           ev).start()

    def run_check(self):
        self.check_after = None
        if self.check_job:
            self.check_job.kill()
        if self.doc.analysis()["src"] is None:
            return
        text = self.doc.text()
        strict = self.strict.get()
        p = self._write_tmp("check")
        t0 = time.time()

        def ev(job, e):
            if e["stage"] == "done":
                self.check = {"text": text, "strict": strict, "result": e}
                self._fill_problems()
                self._msg("Full check: %s in %.1f s" % ("builds" if e.get("ok") else "refused", time.time() - t0))
            elif e["stage"] not in ("exit", "log"):
                self.job_l.config(text="Check: %s" % e.get("what", e["stage"]))
        self.check_job = Job(["check", p, "--name", self._name()] + (["--strict"] if strict else []), ev).start()
        self._fill_checks(self._problems())

    def test_roll(self):
        """TEST ROLL (SPEC.md 130.58.16): tools/bbplay.py on the text as it stands, as a process of its own;
        from the selected area's centre cell, or a selected one-cell part's, when there is one"""
        p = os.path.join(self.tmp, "roll-%d.bbc" % int(time.time() * 1000))
        with open(p, "w", encoding="ascii", newline="") as f:
            f.write(self.doc.text())
        argv = [sys.executable, os.path.join(HERE, "bbplay.py"), p, "--name", self._name()]
        cells = None
        if self.area:
            x0, y0, x1, y1 = self.area
            cells = {((x0 + x1) // 2, (y0 + y1) // 2)}
        elif self.sel:
            cells = self._sel_cells()
        if cells and len(cells) == 1:
            argv += ["--start"] + [str(v) for v in next(iter(cells))]
        subprocess.Popen(argv, stdin=subprocess.DEVNULL)
        self._msg("Test Roll: %s" % ("from cell %s, %s" % tuple(argv[-2:]) if "--start" in argv else "from the start"))

    def cancel_jobs(self):
        for j in (self.pic_job, self.check_job):
            if j:
                j.kill()
        self.pic_job = self.check_job = None

    def _tick(self):
        busy = False
        for j in (self.pic_job, self.check_job):
            if j:
                j.poll()
                busy = busy or j.running
        self.shapes.poll()
        if busy:
            self.pbar.start(12) if not getattr(self, "_spin", False) else None
            self._spin = True
        else:
            if getattr(self, "_spin", False):
                self.pbar.stop()
                self.job_l.config(text="")
            self._spin = False
        self.cancel_b.state(["!disabled"] if busy else ["disabled"])
        self.root.after(100, self._tick)

    def _load_picture(self, out, text):
        from PIL import Image
        from array import array
        try:
            with open(os.path.join(out, "meta.json")) as f:
                meta = json.load(f)
            cga = Image.open(os.path.join(out, "cga.png")).convert("RGB")
            herc = Image.open(os.path.join(out, "herc.png")).convert("RGB")
            ow = array("i")
            with open(os.path.join(out, "owners.bin"), "rb") as f:
                ow.frombytes(f.read())
        except (OSError, ValueError) as e:
            self._msg("The picture could not be read: %s" % e)
            return
        W = meta["width"]
        drawn = [i for i in range(0, len(ow), 7) if ow[i] >= 0]
        meta["centre"] = ((sum(i % W for i in drawn) / float(len(drawn)), sum(i // W for i in drawn) / float(len(drawn)))
                          if drawn else (W / 2.0, meta["lines"] / 2.0))
        if meta.get("dropped_gaps") and self.doc.text() == text:   # SPEC.md 130.58.21: marks that no longer fit
            self.root.after(10, lambda: self._drop_gaps(meta["dropped_gaps"], text))
        if self.show_gaps.get() and meta.get("gaps") is None and not self.pic_after:
            self.root.after(10, self.run_picture)   # (drawn before the overlay was turned on: again, with them)
        first = self.pic is None
        self.pic = {"meta": meta, "cga": cga, "herc": herc, "owners": ow, "text": text}
        if getattr(self, "map", None) and self.map.shown():
            self.map.draw()
        if first and self.view.get() == "iso":
            self.root.after(20, self._scroll_to_sel)
        self._fill_problems()
        if self.view.get() == "iso":
            self._redraw()

    # -- drawing --------------------------------------------------------------
    def set_zoom(self, z):
        self.zoom = max(0.25, min(6.0, z))
        self._redraw()

    def _wheel(self, e):
        self.set_zoom(self.zoom * (1.25 if e.delta > 0 else 0.8))

    def _toggle_view(self, e=None):
        if e is not None and isinstance(e.widget, (self.tk.Entry, self.ttk.Entry, self.tk.Text, self.ttk.Spinbox)):
            return
        self.view.set("iso" if self.view.get() == "plan" else "plan")
        self._view_changed()
        return "break"

    def _view_changed(self):
        self._redraw()
        self.root.after(10, self._scroll_to_sel)

    def _bounds(self):
        a = self.doc.analysis()
        if not a["cells"] and self.good:
            a = self.good
        cells = list(a["cells"]) + [c for it in a["items"] for c in it["cells"]]
        if not cells:
            return 0, 0, 20, 16
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        return min(xs) - 6, min(ys) - 6, max(xs) + 7, max(ys) + 7

    def _fit(self):
        if self.view.get() == "plan":
            x0, y0, x1, y1 = self._bounds()
            w = max(200, self.cv.winfo_width())
            h = max(200, self.cv.winfo_height())
            self.zoom = max(0.25, min(3.0, min(w / float((x1 - x0) * CELL), h / float((y1 - y0) * CELL))))
        self._redraw()

    def _redraw(self):
        if self.view.get() == "plan":
            self.iso_opts.pack_forget()
            self.gap_row.pack_forget()
            self.plan_opts.pack(side="right")
            self._draw_plan()
        else:
            self.plan_opts.pack_forget()
            self.iso_opts.pack(side="right")
            if not self.gap_row.winfo_ismapped():
                self.gap_row.pack(side="top", fill="x", after=self.gap_row_after)
            self._draw_iso()

    def _cpx(self, x, y):
        s = CELL * self.zoom
        x0, y0 = self.origin
        return (x - x0) * s, (y - y0) * s

    def _draw_plan(self):
        c = self.cv
        c.delete("all")
        a = self.doc.analysis()
        stale = False
        if a["error"] and not a["cells"] and self.good:     # refused: draw the last that laid out
            a, stale = self.good, True
        bx0, by0, bx1, by1 = self._bounds()
        self.origin = (bx0, by0)
        s = CELL * self.zoom
        c.configure(scrollregion=(0, 0, (bx1 - bx0) * s, (by1 - by0) * s))
        band = a.get("band")
        if band:                    # where no floor may go: past the picture's edge, less a ball's flight
            box = [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)]
            for k, side in ((band["amin"] + E.FLY - 0.5, -1), (band["amax"] - E.FLY + 1.5, 1)):
                poly = _clip(box, k, side)          # cells x - y beyond k (continuous: centre at +0.5)
                if len(poly) >= 3:
                    pts = [v for p in poly for v in self._cpx(*p)]
                    c.create_polygon(*pts, fill="#3d2a2e", outline="")
                    ends = sorted(poly, key=lambda p: p[1])
                    q = [p for p in poly if abs((p[0] - p[1]) - k) < 1e-6]
                    if len(q) >= 2:
                        c.create_line(*self._cpx(*q[0]), *self._cpx(*q[-1]), fill="#ff6b5e", width=2, dash=(8, 4))
                        lx, ly = self._cpx(*max(q, key=lambda p: p[1]))
                        c.create_text(lx + (6 if side > 0 else -6), ly - 6, anchor="se" if side < 0 else "sw",
                                      fill="#ff8a80", font=("TkDefaultFont", 9),
                                      text="edge of the picture (%d columns)" % band["width"])
        for gx in range(bx0, bx1 + 1):          # the grid, every 4 cells marked
            x, _ = self._cpx(gx, 0)
            c.create_line(x, 0, x, (by1 - by0) * s, fill="#3a3f48" if gx % 4 else "#4a505b")
        for gy in range(by0, by1 + 1):
            _, y = self._cpx(0, gy)
            c.create_line(0, y, (bx1 - bx0) * s, y, fill="#3a3f48" if gy % 4 else "#4a505b")
        if s >= 14:
            for gx in range(bx0, bx1, 4 if s < 30 else 2):
                x, _ = self._cpx(gx, by0)
                c.create_text(x + 2, 2, text=str(gx), anchor="nw", fill="#8a92a0", font=("TkDefaultFont", 8))
            for gy in range(by0, by1, 4 if s < 30 else 2):
                _, y = self._cpx(bx0, gy)
                c.create_text(2, y + 2, text=str(gy), anchor="nw", fill="#8a92a0", font=("TkDefaultFont", 8))
        selcells = set()
        lines_cells = {}
        for (x, y), d in a["cells"].items():
            lines_cells.setdefault(d["line"], []).append((x, y))
            px, py = self._cpx(x, y)
            if self.show_heights.get():
                fill = hcolour(d["h"])
            else:
                fill = "#9aa0a6" if d["kind"] != "wall" else "#6f747a"
            if d["kind"] == "goal":
                fill = "#ffffff"
            if d.get("pieces"):                    # a split cell: its pieces, each its own colour
                for pc in d["pieces"]:
                    pf = hcolour(pc["h"]) if self.show_heights.get() else ("#9aa0a6" if pc["kind"] != "wall"
                                                                            else "#6f747a")
                    if pc["kind"] == "goal":
                        pf = "#ffffff"
                    pts = [v for (u, w) in pc["poly"] for v in (px + u * s, py + w * s)]
                    c.create_polygon(*pts, fill=pf, outline="#1b1d22",
                                     width=2 if pc["kind"] == "wall" else 1)
                    if pc["line"] == self.sel or pc["line"] in self.sels:
                        selcells.add((x, y))
                continue
            c.create_rectangle(px, py, px + s, py + s, fill=fill, outline="#1b1d22")
            if d["kind"] == "goal":
                q = s / 2
                c.create_rectangle(px, py, px + q, py + q, fill="#111", width=0)
                c.create_rectangle(px + q, py + q, px + s, py + s, fill="#111", width=0)
            if d["kind"] == "wall":
                c.create_line(px + 2, py + s - 2, px + s - 2, py + 2, fill="#1b1d22", width=max(1, s / 12))
                c.create_rectangle(px + 1, py + 1, px + s - 1, py + s - 1, outline="#1b1d22", width=max(1, s / 10))
            if d["surf"] == "ice":
                c.create_rectangle(px + s * .2, py + s * .2, px + s * .8, py + s * .8, outline="#e8f8ff",
                                   width=max(1, s / 12))
            elif d["surf"] == "sand":
                for fx, fy in ((.3, .3), (.7, .45), (.4, .72)):
                    r_ = max(1, s / 14)
                    c.create_oval(px + s * fx - r_, py + s * fy - r_, px + s * fx + r_, py + s * fy + r_,
                                  fill="#7a4a12", width=0)
            elif d["surf"] == "bounce":
                for fy in (.33, .66):
                    c.create_line(px + 2, py + s * fy, px + s - 2, py + s * fy, fill="#c0249f",
                                  width=max(1, s / 10))
            if d["kind"] == "field" and s >= 10:          # a shaped floor (a chute, a pit): its groove
                c.create_arc(px + s * .15, py - s * .35, px + s * .85, py + s * .75, start=200, extent=140,
                             style="arc", outline="#1b1d22", width=max(1, s / 14))
            if d["water"]:
                c.create_text(px + s / 2, py + s / 2, text="≈", fill="#0b3d91", font=("TkDefaultFont",
                                                                                     max(6, int(s / 2))))
            if d["slope"] != (0, 0) and s >= 12:
                ax, ay = d["slope"]
                cx_, cy_ = px + s / 2, py + s / 2
                L = s * .3
                n = (ax * ax + ay * ay) ** 0.5 or 1
                c.create_line(cx_ - ax / n * L, cy_ - ay / n * L, cx_ + ax / n * L, cy_ + ay / n * L,
                              arrow="last", fill="#1b1d22", width=max(1, s / 14))     # (uphill)
            if d["line"] == self.sel or d["line"] in self.sels:
                selcells.add((x, y))
        # a label for each statement's region: its height
        if s >= 10 and self.show_heights.get():
            for ln, cl in lines_cells.items():
                if len(cl) < 2 and s < 30:
                    continue
                xs = [p[0] for p in cl]
                ys = [p[1] for p in cl]
                ds = [a["cells"][q] for q in cl]
                lo, hi = min(q["hmin"] for q in ds), max(q["hmax"] for q in ds)
                cx_, cy_ = self._cpx((min(xs) + max(xs) + 1) / 2.0, (min(ys) + max(ys) + 1) / 2.0)
                txt = ("%g" % lo) if lo == hi else "%g-%g" % (lo, hi)
                c.create_text(cx_, cy_, text=txt, fill="#111", font=("TkDefaultFont", max(7, min(11, int(s / 2.4))),
                                                                   "bold"))
        # tubes and the route
        for it in a["items"]:
            if it["kind"] == "tube" and it.get("path"):
                pts = []
                for (x, y) in it["path"]:
                    pts += list(self._cpx(x + .5, y + .5))
                if len(pts) >= 4:
                    c.create_line(*pts, fill="#111", width=max(3, s / 3), capstyle="round", joinstyle="round")
                    c.create_line(*pts, fill="#9fd3ff", width=max(2, s / 5), capstyle="round", joinstyle="round")
        if self.show_route.get() and a["src"]:
            src = a["src"]
            pts = []
            for (x, y), _l in ([src.start] if src.start else []) + list(src.ways):
                pts += list(self._cpx(x + .5, y + .5))
            if len(pts) >= 4:
                c.create_line(*pts, fill="#ffffff", width=2, dash=(6, 5))
        # items
        wnum, wc = {}, {}
        for ln_, _x, _y, br_ in self._ways():
            wc[br_] = wc.get(br_, 0) + 1
            wnum[ln_] = wc[br_]
        for it in a["items"]:
            if it["kind"] == "tube" or not it["cells"]:
                continue
            if it["kind"] == "way" and not self.show_route.get():
                continue
            sel = it["line"] == self.sel or it["line"] in self.sels
            if len(it["cells"]) > 1 and it["kind"] == "prop":
                for (x, y) in it["cells"]:
                    px, py = self._cpx(x, y)
                    c.create_rectangle(px + 3, py + 3, px + s - 3, py + s - 3, outline="#ffd54f" if sel else "#ffb3ff",
                                       width=2)
            x, y = it["at"] or it["cells"][0]
            px, py = self._cpx(x, y)
            g = GLYPH.get(it["what"], it["what"][:1])
            fill = {"start": "#9be29b", "way": "#ffffff", "checkpoint": "#ffcc80"}.get(it["kind"], "#ffffff")
            if sel:
                fill = "#ffd54f"
            r_ = s * (.2 if it["kind"] == "way" else .38)
            c.create_oval(px + s / 2 - r_, py + s / 2 - r_, px + s / 2 + r_, py + s / 2 + r_, fill=fill,
                          outline="#111", width=2)
            if it["kind"] != "way" and s >= 14:
                c.create_text(px + s / 2, py + s / 2, text=g, font=("TkDefaultFont", max(7, int(s / 2.6)), "bold"))
            elif it["kind"] == "way" and s >= 12:
                c.create_text(px + s / 2 + r_ + 2, py + s / 2 - r_ - 2, anchor="sw", fill="#ffffff",
                              text=str(wnum.get(it["line"], "")), font=("TkDefaultFont", max(7, int(s / 3.2)), "bold"))
            if sel:
                selcells.update(it["cells"])
        # the hard-to-see marks: the mark, and the cells in front of it
        if self.show_hard.get() and self.pic and self.pic.get("text") == self.doc.text():
            for m in self.pic["meta"]["marks"]:
                if not m["below"] and m["pct"] >= 100:
                    continue
                px, py = self._cpx(*m["cell"])
                c.create_rectangle(px, py, px + s, py + s, outline="#ff5a4e", width=3)
                for cx_, cy_, _n in m["cover"]:
                    qx, qy = self._cpx(cx_, cy_)
                    c.create_rectangle(qx + 2, qy + 2, qx + s - 2, qy + s - 2, outline="#ffb020", width=3)
        for (x, y) in selcells:
            px, py = self._cpx(x, y)
            c.create_rectangle(px, py, px + s, py + s, outline="#ffffff", width=2, dash=(4, 3))
        hl = getattr(self, "hilite", None)
        if hl:
            px, py = self._cpx(*hl)
            c.create_oval(px - s * .4, py - s * .4, px + s * 1.4, py + s * 1.4, outline="#ff5a4e", width=3)
        if self.area:                            # the selected AREA: it stays until another is chosen
            x0, y0, x1, y1 = self.area
            ax, ay = self._cpx(x0, y0)
            bx, by = self._cpx(x1 + 1, y1 + 1)
            c.create_rectangle(ax - 1, ay - 1, bx + 1, by + 1, outline="#111", width=4)
            c.create_rectangle(ax, ay, bx, by, outline="#ffd54f", width=2, dash=(6, 3))
        rz = self._resizable()
        if rz and not (self.drag and self.drag.get("resize")):
            for _h, hx, hy in self._handles(rz[2]):
                c.create_rectangle(hx - 5, hy - 5, hx + 5, hy + 5, fill="#ffd54f", outline="#111", width=1)
        if self.drag and self.drag.get("resize"):
            x0_, y0_, x1_, y1_ = self.drag["rect"]
            ax, ay = self._cpx(x0_, y0_)
            bx, by = self._cpx(x1_, y1_)
            c.create_rectangle(ax, ay, bx, by, outline="#ffd54f", width=3)
            c.create_text(bx + 4, by + 4, anchor="nw", fill="#ffd54f", font=("TkDefaultFont", 10, "bold"),
                          text="%d x %d" % (x1_ - x0_, y1_ - y0_))
        if self.drag and self.drag["move"] and self.drag["to"] != self.drag["from"]:
            dx = self.drag["to"][0] - self.drag["from"][0]
            dy = self.drag["to"][1] - self.drag["from"][1]
            for (x, y) in self._sel_cells():
                px, py = self._cpx(x + dx, y + dy)
                c.create_rectangle(px, py, px + s, py + s, outline="#ffd54f", width=2)
        if stale:
            c.create_text(10, 10, anchor="nw", fill="#ffd54f", width=700, font=("TkDefaultFont", 11, "bold"),
                          text="Showing the last version that laid out: the course as it stands is refused "
                               "(see the problems below). Undo, or fix that line.")
        if not a["cells"] and not a["items"]:
            c.create_text(20, 20, anchor="nw", fill="#e6e6e6", text=self.doc.analysis()["error"] or
                          "An empty course: drag across the grid to choose an area, then choose Floor on the "
                          "left and press Add.", width=600)
        self._draw_blends(c, "plan")

    def _draw_iso(self):
        c = self.cv
        c.delete("all")
        if not self.pic:
            busy = bool(self.pic_after) or bool(self.pic_job and self.pic_job.running)
            c.create_text(20, 20, anchor="nw", fill="#e6e6e6", text="Drawing the game's picture (a few seconds "
                          "on a big course)..." if busy else "No picture yet: the course has to lay out first "
                          "(see the problems below).", width=600)
            if busy:
                self.root.after(500, lambda: self.view.get() == "iso" and not self.pic and self._redraw())
            return
        from PIL import Image
        meta = self.pic["meta"]
        herc = self.adapter.get() == "herc"
        img = self.pic["herc"] if herc else self.pic["cga"]
        W, H = meta["width"], meta["lines"]
        if self.xray.get() and self.sel:
            img = self._xray(img, herc)
        z = max(1, int(round(self.zoom * 2)))
        disp = img.resize((W * z, H * z), Image.NEAREST)     # (the Hercules image is 2 px a pixel across)
        self.iso_scale = (disp.width / float(W), disp.height / float(H))
        self.photo = _photo(self.tk, disp)
        c.configure(scrollregion=(0, 0, disp.width, disp.height))
        c.create_image(0, 0, image=self.photo, anchor="nw")
        if self.pic.get("text") != self.doc.text():
            c.create_text(8, 8, anchor="nw", fill="#ffd54f", text="(updating...)")
        if self.show_hard.get():
            kx, ky = self.iso_scale
            for m in meta["marks"]:
                if not m["below"] and m["pct"] >= 100:
                    continue
                for (x, y) in m["hidden"]:
                    c.create_rectangle(x * kx, y * ky, (x + 1) * kx, (y + 1) * ky, fill="#ff2828", width=0)
        if self.show_gaps.get():
            self._draw_gaps()
        else:
            self.gap_l.config(text="")
        self._draw_blends(c, "iso")

    # -- the gap band (SPEC.md 130.58.21, 130.57) --------------------------------
    def _gaps_toggled(self):
        """the detector costs every picture compile time, so it runs only while the overlay shows: turned on
        with a picture that has no candidates, the picture is drawn again with them"""
        if self.show_gaps.get() and (self.pic_job and self.pic_job.running or self.pic
                                     and self.pic["meta"].get("gaps") is None):
            self.run_picture()                  # (one already drawing has no candidates either: started again)
            self._msg("Finding where a gap band could go...")
        self._redraw()

    def _drop_gaps(self, lines, text):
        """the `gap` lines the picture found banding nothing after an edit, removed - one undo step"""
        if self.doc.text() != text:
            return
        lines = [ln for ln in lines if ln <= len(self.doc.lines) and self.doc.lines[ln - 1].split()[:1] == ["gap"]]
        if not lines:
            return

        def go():
            with self.doc.group("gap bands that no longer fit removed"):
                for ln in sorted(lines, reverse=True):
                    self.doc.remove(ln)
            return True
        if self._edit(go):
            self._msg("Removed %d gap band mark%s the edit left with nothing to band (line%s %s)" % (
                len(lines), "" if len(lines) == 1 else "s", "" if len(lines) == 1 else "s",
                ", ".join(map(str, sorted(lines)))))

    def _gaps_shown(self):
        """the candidates the overlay draws: every marked face, and the unmarked ones at least gap_min wide"""
        if not (self.show_gaps.get() and self.pic and self.pic["meta"].get("gaps") is not None):
            return []
        try:
            n = int(self.gap_min.get())
        except (tk.TclError, ValueError):
            n = 1
        return [g for g in self.pic["meta"]["gaps"] if g["marked"] or g["feet"] >= n]

    def _draw_gaps(self):
        c = self.cv
        kx, ky = self.iso_scale
        shown = self._gaps_shown()
        for g in shown:
            x0, y0, x1, y1 = g["box"]
            r = (x0 * kx - 1, y0 * ky - 1, (x1 + 1) * kx + 1, (y1 + 1) * ky + 1)
            if g["marked"]:
                c.create_rectangle(*r, outline="#ff3df5", width=2)      # (the band itself shows inside)
            else:
                c.create_rectangle(*r, outline="#29e6ff", width=1, dash=(3, 2))
        allg = self.pic["meta"].get("gaps") or []
        m = sum(1 for g in allg if g["marked"])
        self.gap_l.config(text=("%d of %d shown, %d marked (pink): click a box to mark or unmark it"
                                % (len(shown), len(allg), m))
                          if self.pic["meta"].get("gaps") is not None else "finding them...")

    def _gap_at(self, e):
        """the shown candidate under the pointer (the smallest box, within a few screen px of a sliver)"""
        if self.view.get() != "iso" or not getattr(self, "iso_scale", None):
            return None
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        kx, ky = self.iso_scale
        hit = []
        for g in self._gaps_shown():
            x0, y0, x1, y1 = g["box"]
            if x0 * kx - 4 <= x <= (x1 + 1) * kx + 4 and y0 * ky - 4 <= y <= (y1 + 1) * ky + 4:
                hit.append(((x1 - x0 + 1) * (y1 - y0 + 1), g))
        return min(hit, key=lambda h: h[0])[1] if hit else None

    def toggle_gap(self, g):
        faces = [(f["cell"], f["side"]) for f in self.pic["meta"]["gaps"]]
        r = self._edit(self.doc.toggle_gap, g["cell"], g["side"], faces)
        if r:
            g["marked"] = r == "marked"          # (shown at once; the picture drawn again confirms it)
            self._redraw()
            self._msg("%s the gap band on the %s face of x %d, y %d (%d px wide)" % (
                "Marked" if g["marked"] else "Unmarked", g["side"].upper(), g["cell"][0], g["cell"][1], g["feet"]))

    def _draw_blends(self, c, view):
        """SPEC.md 130.58.18: the last full check's BLEND warnings, while "Hard to see" is on - in Plan both
        floors hatched (one green, one magenta), in Iso the seam's pixels where the checker runs on.  A check
        refused (under strict) carries none, so the picture job's warnings stand in for it"""
        if not self.show_hard.get():
            return
        ws = []
        for got in (self.check, self.pic):
            if got and got.get("text") == self.doc.text():
                ws = (got.get("result") or got.get("meta") or {}).get("warnings") or []
                if ws:
                    break
        blends = [w for w in ws if w.get("kind") == "blend" and w.get("regions")]
        for w in blends:
            if view == "plan":
                s = CELL * self.zoom
                for reg, ink in zip(w["regions"], ("#39ff7a", "#ff4fd8")):
                    for (x, y) in reg:
                        px, py = self._cpx(x, y)
                        for f in (.5, 1.0, 1.5):
                            c.create_line(px + max(0, f - 1) * s, py + min(f, 1) * s, px + min(f, 1) * s,
                                          py + max(0, f - 1) * s, fill=ink, width=max(1, s / 12))
            elif self.pic:
                meta = self.pic["meta"]
                dx, dy = meta["x0"] - w.get("x0", meta["x0"]), meta["y0"] - w.get("y0", meta["y0"])
                kx, ky = self.iso_scale
                ink = "#39ff7a" if not w.get("accepted") else "#7fa88c"
                for (x, y) in w.get("seam", ()):    # (each pixel a pixel wider all round: a seam is thin)
                    x, y = x + dx, y + dy
                    c.create_rectangle((x - .5) * kx, (y - .5) * ky, (x + 1.5) * kx, (y + 1.5) * ky, fill=ink,
                                       width=0)

    def _xray(self, img, herc):
        """the picture dimmed but for the pixels the selection's cells drew, and what drew over them"""
        from PIL import Image
        a = self.doc.analysis()
        mine = {256 * x + y for (x, y), d in a["cells"].items() if d["line"] == self.sel or d["line"] in self.sels}
        for it in a["items"]:
            if it["line"] == self.sel or it["line"] in self.sels:
                mine |= {256 * x + y for (x, y) in it["cells"]}
        if not mine:
            return img
        meta = self.pic["meta"]
        W, H = meta["width"], meta["lines"]
        ow = self.pic["owners"]
        mask = bytearray(W * H)
        for i in range(W * H):
            if ow[i] in mine:
                mask[i] = 255
        m = Image.frombytes("L", (W, H), bytes(mask))
        if herc:
            m = m.resize((W * 2, H), Image.NEAREST)
        dim = Image.blend(img, Image.new("RGB", img.size, (20, 22, 28)), 0.7)
        out = Image.composite(img, dim, m)
        # what hides the selection's marks (the visibility audit's cover cells): orange, dithered
        cover = set()
        for mk in meta.get("marks", []):
            if mk.get("line") == self.sel:
                cover |= {256 * c[0] + c[1] for c in mk["cover"]}
        if cover:
            cm = bytearray(W * H)
            for i in range(W * H):
                if ow[i] in cover and ((i % W) + (i // W)) & 1:
                    cm[i] = 255
            cmi = Image.frombytes("L", (W, H), bytes(cm))
            if herc:
                cmi = cmi.resize((W * 2, H), Image.NEAREST)
            out = Image.composite(Image.new("RGB", img.size, (255, 170, 0)), out, cmi)
        return out

    # -- the mouse --------------------------------------------------------------
    def _cell_at(self, e):
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        if self.view.get() == "plan":
            s = CELL * self.zoom
            self.frac = ((x % s) / s, (y % s) / s)
            return int(x // s) + self.origin[0], int(y // s) + self.origin[1]
        if not self.pic:
            return None
        kx, ky = self.iso_scale
        px, py = int(x / kx), int(y / ky)
        W, H = self.pic["meta"]["width"], self.pic["meta"]["lines"]
        if 0 <= px < W and 0 <= py < H:
            o = self.pic["owners"][py * W + px]
            if o >= 0:
                return o >> 8, o & 255
        return None

    def _press(self, e):
        self.cv.focus_set()
        g = self._gap_at(e) if self.show_gaps.get() else None
        if g:                                            # the gap overlay: a click marks or unmarks that face
            self.toggle_gap(g)
            return
        cell = self._cell_at(e)
        self.hilite = None
        if cell is None:
            return
        a = self.doc.analysis()
        if self.tool.get() == "erase":
            lines = E.at_cell(a, cell)
            if lines:
                self._edit(self.doc.remove, lines[0], label="erase")
            return
        if self.view.get() != "plan":                    # Iso: a click selects what drew that pixel
            lines = E.at_cell(a, cell)
            self.area = (cell[0], cell[1], cell[0], cell[1])
            self.select(lines[0] if lines else None)
            self._fill_add()
            return
        h = self._handle_at(e)                           # a resize handle of the selected floor, wall, goal or hole
        if h:
            rz = self._resizable()
            self.drag = {"from": cell, "to": cell, "move": False, "shift": False, "ctrl": False, "resize": h,
                         "orig": rz[2], "rect": rz[2]}
            return
        w = self._way_at(e)                              # a route point, picked and dragged straight off the plan
        if w:
            self.select(w)
            self.drag = {"from": cell, "to": cell, "move": True, "shift": False, "ctrl": False}
            return
        movable = self.sel and cell in self._sel_cells() and E.coord_slots(self.doc.statement(self.sel).toks)
        ctrl = bool(e.state & 0x0004) or (sys.platform == "darwin" and bool(e.state & 0x0008))
        self.drag = {"from": cell, "to": cell, "move": bool(movable) and not ctrl, "shift": bool(e.state & 0x0001),
                     "ctrl": ctrl}

    def _motion(self, e):
        d = self.drag
        if not d:
            return
        if d.get("resize"):
            return self._resize_motion(e)
        cell = self._cell_at(e)
        if cell is None or cell == d["to"]:
            return
        d["to"] = cell
        if not d["move"]:                        # dragging out an AREA
            fx, fy = d["from"]
            self.area = (min(fx, cell[0]), min(fy, cell[1]), max(fx, cell[0]), max(fy, cell[1]))
            if self.sel:
                self.sel = None
                self._fill_inspector()
        self._draw_plan()

    def _release(self, e):
        d, self.drag = self.drag, None
        if not d:
            return
        if d.get("resize"):
            if d["rect"] != d["orig"]:
                self.resize_sel(d["rect"])
            else:
                self._redraw()
            return
        if d["move"] and d["to"] != d["from"]:
            self.move_sel(d["to"][0] - d["from"][0], d["to"][1] - d["from"][1])
        elif not d["move"] and d["to"] != d["from"]:
            self._fill_inspector()                # an area: it stays selected
            x0, y0, x1, y1 = self.area
            self._msg("Selected %d x %d cells. Choose a part on the left and press Add, or press Delete to "
                      "clear what is in it." % (x1 - x0 + 1, y1 - y0 + 1))
        else:                                     # a click: select what is there
            cell = d["from"]
            lines = E.at_cell(self.doc.analysis(), cell, getattr(self, "frac", None))
            self.area = (cell[0], cell[1], cell[0], cell[1])
            if lines and d.get("ctrl"):
                self.select(lines[0], add=True)
            elif lines and self.sel in lines and d["shift"]:
                self.select(lines[(lines.index(self.sel) + 1) % len(lines)])
            elif lines and self.sel in lines:
                self.select(self.sel)
            else:
                self.select(lines[0] if lines else None)
        self._fill_add()
        self._redraw()

    def _hover(self, e):
        g = self._gap_at(e) if self.show_gaps.get() else None
        if g:
            self.readout.config(text="gap band: the %s face of x %d, y %d, %d px wide - %s" % (
                g["side"].upper(), g["cell"][0], g["cell"][1], g["feet"],
                "marked (click to unmark)" if g["marked"] else "click to mark it"))
            return
        cell = self._cell_at(e)
        if cell is None:
            self.readout.config(text="")
            return
        a = self.doc.analysis()
        d = a["cells"].get(cell)
        parts = ["x %d, y %d" % cell]
        if d and d["slope"] != (0, 0):
            sx_, sy_ = d["slope"]
            parts.append("rises toward %s" % ("+x" if sx_ > 0 else "-x" if sx_ < 0 else "+y" if sy_ > 0 else "-y"))
        if d:
            parts.append("%s, height %s%s" % ({"field": "shaped floor"}.get(d["kind"], d["kind"]),
                                              ("%g" % d["h"]) if d["slope"] == (0, 0) and d["kind"] != "field" else
                                              "%g to %g" % (d["hmin"], d["hmax"]),
                                              "" if d["surf"] == "normal" else ", " + d["surf"]))
        names = []
        for ln in E.at_cell(a, cell):
            try:
                names.append("%s (line %d)" % (_plain_kind(self.doc.statement(ln)), ln))
            except E.EditError:
                pass
        if names:
            parts.append(("drawn by " if self.view.get() == "iso" else "") + "; ".join(names))
        self.readout.config(text="    ".join(parts))

    def _msg(self, text):
        note, self._note = getattr(self, "_note", ""), ""
        self.status.config(text=note + text)

    def run(self):
        self.root.mainloop()


HANGS = ("to the ground", "3 units", "2 units", "1.5 units", "1 units", "0.5 units", "0.25 units")

EXPLAIN = [
    (r"solid outside 3 \.\. 252|outside 3 \.\.", "it reaches the edge of the course's grid. Keep it at least "
     "3 cells from the edge."),
    (r"past the \d+ px width|footprint", "the course would be wider than its picture. Keep it nearer the rest "
     "of the course, or choose Size 128 on the Course tab."),
    (r"archway's leg", "an archway stands ACROSS a path, and its legs need empty space on both sides of it. "
     "Select a path one or two cells wide with nothing beside it."),
    (r"guard .* stands on a solid cell", "a guard rail goes on the EMPTY cells along a floor's edge, not on the "
     "floor. Select the empty strip beside the floor."),
    (r"tube's body cell .* not a WALL", "a tube runs through a wall: its two ends sit on floor and every cell "
     "between them must be wall. Add the wall first."),
    (r"without a KEEP tube", "a windmill sits on the mouth of a Tube (keep): add the tube first, then the "
     "windmill on its in-end."),
    (r"lift's shaft .* not VOID", "a lift rises out of an empty shaft: put it on an empty cell (or a Hole)."),
    (r"laid already: a plate lays its own cells", "a seesaw makes its own floor: select empty space for it."),
    (r"hump's .* meets the floor .* off its base", "a hump's rim must be level with the floor around it. Put it "
     "on one flat floor."),
    (r"HALF filled", "a turntable needs exactly half of its cells filled; change its fill on the right."),
    (r"is empty", "the area is empty (zero cells across)."),
    (r"has \d+ occluder records, over \d+", "too many things stand in front of each other at one spot of the "
     "game's picture - usually a steep ramp or a tall cliff beside other tall parts. Make the ramp gentler "
     "(longer, or a smaller rise) or the drop beside it lower."),
    (r"NO TRAP: from (.*) cannot reach the goal", "a ball could get stuck: from {0} it cannot get to the goal. "
     "Connect that part to the rest of the course, or remove it."),
    (r"way \(\d+, \d+\) is on a", "a route point must be on floor."),
    (r"start .* is not a flat FLOOR", "the start must be on flat floor with no other part on it."),
    (r"guard \(\d+, \d+\) touches \(\d+, \d+\), which is not a whole FLAT floor", "a guard rail's cell is a wall at "
     "every height, drawn only as a rail on its flat floor's edge, so it may not touch a ramp, a split or a shaped "
     "cell anywhere round it (it would be an invisible wall on that side). Where one empty cell separates a floor "
     "from a ramp, no rail fits there: widen the gap to two cells, put the rail on the ramp's far side, or use a "
     "low wall."),
    (r"guard \(\d+, \d+\) stands on a solid cell", "a guard rail goes in the EMPTY cell beside a floor, not on "
     "the floor: select the empty cells along the edge."),
    (r"gap bands nothing", "that `gap` line names no face that stands over a gap, so it would change no pixel. "
     "Turn on Gap bands in the Iso view and click the places you want instead; a line left with no mark is "
     "deleted."),
    (r"gap takes whole cells", "a gap band goes on whole cells' faces, never a half or a quarter: name the "
     "whole cell (`gap tile X Y sw`)."),
    (r"too near the edge of the course's picture", "the course would reach past the edge of the game's picture "
     "(the dashed red lines), even at its widest (160 columns). Build toward the bottom-right or top-left of the "
     "plan instead: that is down or up the screen, which has no limit."),
    (r"ramp rate", "a ramp must rise by a whole number of half units on each tile it crosses. Set the high end "
     "to the low end plus 0.5, 1, 1.5 ... times its length."),
    (r"already belongs to the prop", "only one part can stand on a cell. Choose another cell."),
    (r"an archway .* at most 2 cells", "an archway is at most 2 cells each way: select the path's width, "
     "not its length."),
    # the LANE bounds that remain (SPEC.md 130.19.10 item 14, 130.32): what the game's drawing can really not do
    (r"lanes on their own clocks meet", "too many things that keep changing by themselves (windmills, fans, "
     "and the clock's digits) are on one screen together with a clock. At the finish the clock's digits are "
     "drawn all at once, which needs room for all of them in one frame. Move the clock, or a windmill or fan, "
     "further away (about a screen)."),
    (r"two lanes share blocks", "two animated parts are drawn into the same 8 x 8 pixel squares of the picture, "
     "and at least one of them (a windmill, a bumper, a flag, a clock, a sign, a pickup) cannot share its "
     "squares. Move them at least a cell apart."),
    (r"FAST lanes \(rotors\) meet the|FAST lanes in the walk's range", "too many constantly moving parts "
     "(windmills, fans) are near each other: at most 6 on one screen and 8 a little beyond it. Spread them out."),
    (r"rotor pose changes on one step", "windmills in one screen turn too often on the same moment. Give one of "
     "them a different `seed` or `period` on the right."),
    (r"a group lane of \d+ members|an element in \d+ group lanes|a group member of \d+ poses", "too many parts "
     "that share their picture squares overlap in one spot (at most 4 in any 32 x 24 pixel patch). Split the "
     "row or the area into smaller pieces with a cell between them."),
    (r"does not name|`uses ", "it needs an extra the course does not load."),
    (r"no '(course|width|start)' statement", "a course needs a name, a width and a start."),
    (r"HIDDEN", "the player could not see it (it is behind something taller)."),
    (r"unknown statement", "that is not a statement the course language has."),
]


def explain(err):
    """the compiler's refusal, with what to do about it in plain words where we know it"""
    import re
    for pat, words in EXPLAIN:
        m = re.search(pat, err)
        if m:
            words = words.format(*m.groups())
            return "%s\n(The compiler said: %s)" % (words[:1].upper() + words[1:], err)
    return err


def _clip(poly, k, side):
    """the part of polygon POLY where side * (x - y - k) > 0 (one half-plane, Sutherland-Hodgman)"""
    def inside(p):
        return side * (p[0] - p[1] - k) > 0

    def cut(p, q):
        fp, fq = p[0] - p[1] - k, q[0] - q[1] - k
        t = fp / (fp - fq)
        return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        if inside(p):
            out.append(p)
            if not inside(q):
                out.append(cut(p, q))
        elif inside(q):
            out.append(cut(p, q))
    return out


def _photo(tk, img):
    """a Tk image of a PIL one through PNG bytes: Tk 8.6 reads PNG itself, so no ImageTk is needed (Debian
    ships it apart from Pillow)"""
    import base64
    import io
    b = io.BytesIO()
    img.save(b, "PNG")
    return tk.PhotoImage(data=base64.b64encode(b.getvalue()).decode("ascii"))


def _songs():
    try:
        return B.song_names()
    except Exception:
        return []


def _plain_kind(st):
    k, t = st.kind, st.toks
    if k == "prop" and len(t) > 1:
        return E._plain(t[1])
    if k == "surface" and len(t) > 1:
        return "Surface: %s" % t[1]
    if k == "tube" and len(t) > 1:
        return "Tube (%s)" % t[1]
    if k == "pad" and len(t) > 1 and t[1] in E.MATERIALS:
        return "Ball pad: %s" % t[1]
    names = {"floor": "Floor", "wall": "Wall", "hole": "Hole", "goal": "Goal", "float": "Overhang",
             "guard": "Guard rail", "water": "Water", "arch": "Waterfall face", "hump": "Hump", "archway": "Archway",
             "chute": "Chute", "pit": "Pit", "seesaw": "Seesaw", "spring": "Spring", "start": "Start",
             "way": "Route point", "checkpoint": "Flag", "cup": "Cup", "clock": "Clock", "course": "Course name",
             "uses": "Extras loaded", "accept": "Accepted warning", "gap": "Gap band"}
    return names.get(k, k.capitalize())


def main(argv):
    path = argv[0] if argv else None
    App(path).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
