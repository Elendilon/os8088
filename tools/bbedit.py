#!/usr/bin/env python3
"""bbedit - THE BOUNCE BONANZA COURSE BUILDER (SPEC.md 130.55).

    python3 tools/bbedit.py [COURSE.bbc]

A window over tools/bbedproj.py's Document: the course is its .bbc text, and
every edit rewrites only the lines it is about (comments and order are kept).
Two views of one selection - PLAN, top-down with a height map, and ISO, the
game's own picture out of tools/bbcourse.py - and the compiler as the only
judge: its refusals are ERRORS, its visual checks WARNINGS (SPEC.md 130.55.4).
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

TITLE = "Bounce Bonanza course builder"
CONFIG = os.path.join(os.path.expanduser("~"), ".config", "os8088", "bbedit.json")
CELL = 24                       # a plan cell at zoom 1, screen px

# ----------------------------------------------------------------------------
# the palette: every part, its group, plain name, what it does, its template
# ({x} {y}: the clicked cell; {x0} {y0} {x1} {y1}: a dragged rectangle; {h}: the toolbar's height)
# ----------------------------------------------------------------------------

PALETTE = [
    ("Ground", [
        ("Floor", "rect", "floor rect {x0} {y0} {x1} {y1} flat {h}", "Solid ground at a height; flat or a ramp"),
        ("Wall", "rect", "wall rect {x0} {y0} {x1} {y1} flat {h}", "A raised block the ball bounces off"),
        ("Hole", "rect", "hole rect {x0} {y0} {x1} {y1}", "Open void: the ball falls"),
        ("Goal", "rect", "goal rect {x0} {y0} {x1} {y1} flat {h}", "Finish floor"),
        ("Overhang", "rect", "float rect {x0} {y0} {x1} {y1}", "Floor that hangs over the void"),
        ("Guard rail", "rect", "guard rect {x0} {y0} {x1} {y1}", "A rail on the open edge beside a floor"),
        ("Water", "cell", "water tile {x} {y} top {h} bed 0", "A pool: a surface and a bed"),
        ("Waterfall face", "cell", "arch {x} {y} +x", "The face a water column spills from"),
        ("Hump", "cell", "hump {x} {y} 2", "A rounded bump (Shapes tab for more)"),
        ("Archway", "cell", "archway tile {x} {y} along x", "A ceiling the ball rolls under"),
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
         "Glass path": "g", "Hourglass": "H", "Speed": ">", "Jump": "J", "Gate": "G", "Pressure plate": "_",
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
        self.adapter = tk.StringVar(value="cga")
        self.strict = tk.BooleanVar(value=False)
        self.part = None                # the palette entry being placed: (name, mode, template)
        self.drag = None
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
        self.pal_hint = ttk.Label(left, text="Click a part, then click (or drag across) the course. Esc goes "
                                  "back to Select.", wraplength=220, foreground="#444")
        self.pal_hint.pack(fill="x")
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
        ttk.Label(vb, text="   Height").pack(side="left")
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
        cf = ttk.Frame(mid)
        cf.pack(fill="both", expand=True)
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
        right = ttk.Frame(pw, padding=8, width=300)
        self.ins_title = ttk.Label(right, text="Nothing selected", font=("TkDefaultFont", 13, "bold"))
        self.ins_title.pack(anchor="w")
        self.ins_line = ttk.Label(right, text="", foreground="#555", wraplength=280)
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
        self.ins_help = ttk.Label(right, text="", wraplength=280, foreground="#444")
        self.ins_help.pack(anchor="w", pady=(8, 0))
        self.ins_err = ttk.Label(right, text="", wraplength=280, foreground="#b3261e")
        self.ins_err.pack(anchor="w", pady=(8, 0))
        pw.add(right, weight=0)
        self._fill_palette()

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
            ("Size", ttk.Combobox(g, textvariable=self.cv_width, values=("64", "128"), width=6, state="readonly"),
             "128 fits longer courses and costs memory"),
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
                  "`accept` a warning to keep it under --strict (SPEC.md 130.55.5).", wraplength=520,
                  foreground="#444").pack(anchor="w", pady=(6, 0))

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
        self.pic = None
        self.check = None
        self._fill_recent()
        self._changed("open")
        self.root.after(50, self._fit)

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
        if self.sel is not None and (self.sel > len(self.doc.lines) or not self.doc.lines[self.sel - 1].strip()
                                     or self.doc.lines[self.sel - 1].lstrip().startswith("#")):
            self.sel = None
        self._redraw()
        self._fill_inspector()
        self._fill_course()
        self._fill_source()
        self._fill_problems()
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
        try:
            r = fn(*a, **kw)
        except E.EditError as e:
            self._msg(str(e))
            return None
        added = self.doc.auto_uses()
        if added:
            self._msg("Added `uses %s` for the part you placed" % " ".join(added))
        return r

    def delete(self):
        if self.sel:
            line = self.sel
            self.sel = None
            self._edit(self.doc.remove, line)

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
        self.delete()

    def _nudge(self, e, dx, dy):
        if isinstance(e.widget, (self.tk.Entry, self.ttk.Entry, self.tk.Text, self.ttk.Spinbox,
                                 self.ttk.Treeview)) or not self.sel:
            return
        if E.coord_slots(self.doc.statement(self.sel).toks):
            self._edit(self.doc.move, self.sel, dx, dy)
        return "break"

    def apply_course(self):
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
                iid = self.pal.insert(gid, "end", text="%s   %s" % (it[0], "(drag)" if it[1] == "rect" else ""))
                self.pal_items[iid] = it

    def _pick_part(self):
        sel = self.pal.selection()
        it = self.pal_items.get(sel[0]) if sel else None
        if it:
            self.part = it
            self.tool.set("place")
            self._msg("%s: %s. %s on the course to place it; Esc to stop." % (
                it[0], it[3], "Drag a rectangle" if it[1] == "rect" else "Click a cell"))

    def _tool_changed(self):
        if self.tool.get() != "place":
            self.part = None
            self.pal.selection_remove(*self.pal.selection())

    def _escape(self):
        self.tool.set("select")
        self._tool_changed()
        self._msg("Select")

    def place(self, x0, y0, x1=None, y1=None):
        name, mode, tpl, _hint = self.part
        if x1 is None:
            x1, y1 = x0, y0
        xa, xb, ya, yb = min(x0, x1), max(x0, x1) + 1, min(y0, y1), max(y0, y1) + 1
        try:
            h = float(self.height.get())
        except ValueError:
            h = 4.0
        hs = ("%d" % h) if h == int(h) else ("%g" % h)
        code = tpl.format(x=x0, y=y0, x0=xa, y0=ya, x1=xb, y1=yb, h=hs, x3=x0 + 3, x4=x0 + 4, y1b=y0 + 1,
                          y3=y0 + 3)
        kind = code.split()[0]
        if kind == "start":                 # one start: move it
            st = [s for s in self.doc.statements() if s.kind == "start"]
            if st:
                self._edit(self.doc.set_statement, st[0].line, code, label="move the start")
                self.select(st[0].line)
                return
        n = self._edit(self.doc.insert, code, label="place %s" % name.lower())
        if n:
            self.select(n)

    # -- selection and the inspector ---------------------------------------------
    def select(self, line, scroll=False):
        self.sel = line
        self._redraw()
        self._fill_inspector()
        self._fill_source()
        if scroll:
            self.root.after(10, self._scroll_to_sel)

    def _sel_cells(self):
        a = self.doc.analysis()
        cells = {c for c, d in a["cells"].items() if d["line"] == self.sel}
        for it in a["items"]:
            if it["line"] == self.sel:
                cells.update(it["cells"])
        return cells

    def _scroll_to_sel(self):
        """bring the selection into view, in either view"""
        cells = self._sel_cells() or ({self.hilite} if getattr(self, "hilite", None) else set())
        if not cells:
            return
        c = self.cv
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
            self.ins_title.config(text="Nothing selected")
            self.ins_line.config(text="Click something on the course, or type a statement below and Apply "
                                 "to add it.")
            self.raw.set("")
            self.ins_help.config(text="")
            self.ins_err.config(text="")
            return
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
        if slots:
            ttk.Label(body, text="Position").grid(row=row, column=0, sticky="w")
            fr = ttk.Frame(body)
            fr.grid(row=row, column=1, sticky="w")
            for i, ax in slots:
                v = tk.StringVar(value=st.toks[i])
                ttk.Label(fr, text=ax).pack(side="left")
                sp = ttk.Spinbox(fr, from_=-999, to=999, width=4, textvariable=v,
                                 command=lambda i=i, v=v: self._set_word(i, v.get()))
                sp.pack(side="left", padx=(1, 4))
                sp.bind("<Return>", lambda e, i=i, v=v: self._set_word(i, v.get()))
            row += 1
            ttk.Label(body, text="Arrow keys move it a cell; drag it on the plan.", foreground="#666").grid(
                row=row, column=0, columnspan=2, sticky="w")
            row += 1
        for word, n, label in (("flat", 1, "Height"), ("top", 1, "Water top"), ("bed", 1, "Water bed"),
                               ("period", 1, "Period (steps)"), ("on", 1, "On for (steps)"),
                               ("seed", 1, "Starts at"), ("strength", 1, "Strength"), ("range", 1, "Range"),
                               ("for", 1, "Seconds"), ("depth", 1, "Depth (px)"), ("radius", 1, "Radius"),
                               ("pivot", 1, "Pivot height"), ("height", 1, "Height"), ("kick", 1, "Kick"),
                               ("dwell", 1, "Wait at each end")):
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

    def _set_word(self, i, value):
        if self.sel:
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
        pass

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
        if self.check_job:                  # an edit makes a running check stale: cancelled (130.55.8)
            self.check_job.kill()
            self.check_job = None
        a = self.doc.analysis()
        if a["src"] is None or not a["cells"]:
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
        self.pic_job = Job(["picture", p, out, "--name", self._name()], ev).start()

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
        self.pic = {"meta": meta, "cga": cga, "herc": herc, "owners": ow, "text": text}
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
        if self.sel:
            self.root.after(10, self._scroll_to_sel)

    def _bounds(self):
        a = self.doc.analysis()
        cells = list(a["cells"]) + [c for it in a["items"] for c in it["cells"]]
        if not cells:
            return 0, 0, 20, 16
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        return min(xs) - 2, min(ys) - 2, max(xs) + 3, max(ys) + 3

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
            self.plan_opts.pack(side="right")
            self._draw_plan()
        else:
            self.plan_opts.pack_forget()
            self.iso_opts.pack(side="right")
            self._draw_iso()

    def _cpx(self, x, y):
        s = CELL * self.zoom
        x0, y0 = self.origin
        return (x - x0) * s, (y - y0) * s

    def _draw_plan(self):
        c = self.cv
        c.delete("all")
        a = self.doc.analysis()
        bx0, by0, bx1, by1 = self._bounds()
        self.origin = (bx0, by0)
        s = CELL * self.zoom
        c.configure(scrollregion=(0, 0, (bx1 - bx0) * s, (by1 - by0) * s))
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
                c.create_line(cx_ + ax / n * L, cy_ + ay / n * L, cx_ - ax / n * L, cy_ - ay / n * L,
                              arrow="last", fill="#1b1d22", width=max(1, s / 14))
            if d["line"] == self.sel:
                selcells.add((x, y))
        # a label for each statement's region: its height
        if s >= 10 and self.show_heights.get():
            for ln, cl in lines_cells.items():
                if len(cl) < 2 and s < 30:
                    continue
                xs = [p[0] for p in cl]
                ys = [p[1] for p in cl]
                d = a["cells"][cl[0]]
                cx_, cy_ = self._cpx((min(xs) + max(xs) + 1) / 2.0, (min(ys) + max(ys) + 1) / 2.0)
                txt = ("%g" % d["h"]) if d["slope"] == (0, 0) and d["kind"] != "field" else \
                    "%g-%g" % (d["hmin"], d["hmax"])
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
        for it in a["items"]:
            if it["kind"] == "tube" or not it["cells"]:
                continue
            if it["kind"] == "way" and not self.show_route.get():
                continue
            sel = it["line"] == self.sel
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
        if self.drag and self.drag.get("rect"):
            x0, y0, x1, y1 = self.drag["rect"]
            ax, ay = self._cpx(min(x0, x1), min(y0, y1))
            bx, by = self._cpx(max(x0, x1) + 1, max(y0, y1) + 1)
            c.create_rectangle(ax, ay, bx, by, outline="#ffd54f", width=2, dash=(5, 3))
        if self.drag and self.drag.get("move"):
            dx, dy = self.drag["move"]
            for (x, y) in self.drag["cells"]:
                px, py = self._cpx(x + dx, y + dy)
                c.create_rectangle(px, py, px + s, py + s, outline="#ffd54f", width=2)
        if not a["cells"] and not a["items"]:
            c.create_text(20, 20, anchor="nw", fill="#e6e6e6", text=a["error"] or "An empty course: choose "
                          "Floor in the palette and drag a rectangle.", width=600)

    def _draw_iso(self):
        c = self.cv
        c.delete("all")
        if not self.pic:
            c.create_text(20, 20, anchor="nw", fill="#e6e6e6", text="Drawing the game's picture..." if
                          self.pic_job and self.pic_job.running else "No picture yet: the course has to lay "
                          "out first (see the problems below).", width=600)
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

    def _xray(self, img, herc):
        """the picture dimmed but for the pixels the selection's cells drew, and what drew over them"""
        from PIL import Image
        a = self.doc.analysis()
        mine = {256 * x + y for (x, y), d in a["cells"].items() if d["line"] == self.sel}
        for it in a["items"]:
            if it["line"] == self.sel:
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
        cell = self._cell_at(e)
        self.hilite = None
        if cell is None:
            return
        tool = self.tool.get()
        a = self.doc.analysis()
        if tool == "place" and self.part:
            if self.part[1] == "rect":
                self.drag = {"rect": (cell[0], cell[1], cell[0], cell[1])}
            else:
                self.place(*cell)
            return
        lines = E.at_cell(a, cell)
        if tool == "erase":
            if lines:
                self._edit(self.doc.remove, lines[0], label="erase")
            return
        if not lines:
            self.select(None)
            return
        if self.sel in lines and (e.state & 0x0001):          # Shift-click: what is under it
            i = (lines.index(self.sel) + 1) % len(lines)
            self.select(lines[i])
        elif self.sel not in lines:
            self.select(lines[0])
        st = self.doc.statement(self.sel)
        if E.coord_slots(st.toks) and self.view.get() == "plan":
            cells = [c_ for c_, d in a["cells"].items() if d["line"] == self.sel]
            cells += [c_ for it in a["items"] if it["line"] == self.sel for c_ in it["cells"]]
            self.drag = {"from": cell, "move": (0, 0), "cells": cells}

    def _motion(self, e):
        if not self.drag:
            return
        cell = self._cell_at(e)
        if cell is None:
            return
        if "rect" in self.drag:
            x0, y0, _x1, _y1 = self.drag["rect"]
            self.drag["rect"] = (x0, y0, cell[0], cell[1])
        elif "from" in self.drag:
            self.drag["move"] = (cell[0] - self.drag["from"][0], cell[1] - self.drag["from"][1])
        self._draw_plan()

    def _release(self, e):
        d, self.drag = self.drag, None
        if not d:
            return
        if "rect" in d:
            x0, y0, x1, y1 = d["rect"]
            self.place(x0, y0, x1, y1)
        elif d.get("move") and d["move"] != (0, 0):
            self._edit(self.doc.move, self.sel, *d["move"])
        else:
            self._redraw()

    def _hover(self, e):
        cell = self._cell_at(e)
        if cell is None:
            self.readout.config(text="")
            return
        a = self.doc.analysis()
        d = a["cells"].get(cell)
        parts = ["x %d, y %d" % cell]
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
        self.status.config(text=text)

    def run(self):
        self.root.mainloop()


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
             "uses": "Extras loaded", "accept": "Accepted warning"}
    return names.get(k, k.capitalize())


def main(argv):
    path = argv[0] if argv else None
    App(path).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
