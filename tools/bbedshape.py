#!/usr/bin/env python3
"""bbedshape - THE COURSE BUILDER'S SHAPES TAB (SPEC.md 130.56.19): chutes, pits and humps
(130.28, 130.44) edited as what they are - a crease drawn with handles, a bowl, a ridge - with the
height graph and how each ball rides the shape (bbedjob.py `ride`, the game's own Physics).

The helpers at the top are the tab's model and import no Tk: the window and the row
(tests/unit/t_bbedit.py) both call them. The tab itself (`ShapesTab`) is built by tools/bbedit.py,
which hands it the window (its document, `_edit`, the job runner and the height colours).
"""

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def _num(t):
    try:
        float(t)
        return True
    except ValueError:
        return False


def _g(v):
    """a height as the course writes it: 4, 4.5, 4.25"""
    return ("%g" % v) if v is not None else None


def _sg(v):
    return (v > 0) - (v < 0)


# ----------------------------------------------------------------------------
# the statements (no Tk)
# ----------------------------------------------------------------------------

def parse(toks):
    """a shape statement's fields, or None: chute {"kind", "width", "prof", "depth", "ways": [[x, y, z|None]]},
    pit {"kind", "x", "y", "z", "radius", "depth", "hole"}, hump {"kind", "x", "y", "z", "along", "n", "open",
    "height"}"""
    t = list(toks)
    k = t[0] if t else None
    try:
        if k == "chute":
            sh = {"kind": k, "width": int(t[1]), "prof": t[2], "depth": 5, "ways": []}
            i = 3
            while i < len(t):
                if t[i] == "depth":
                    sh["depth"] = int(t[i + 1])
                    i += 2
                elif t[i] == "way":
                    z = float(t[i + 3]) if i + 3 < len(t) and _num(t[i + 3]) else None
                    sh["ways"].append([int(t[i + 1]), int(t[i + 2]), z])
                    i += 4 if z is not None else 3
                else:
                    return None
            return sh if len(sh["ways"]) >= 2 else None
        if k == "pit":
            sh = {"kind": k, "x": int(t[1]), "y": int(t[2]), "z": float(t[3]), "radius": 3, "depth": 16, "hole": 1}
            i = 4
            while i + 1 < len(t):
                sh[t[i]] = int(t[i + 1])
                i += 2
            return sh
        if k == "hump":
            sh = {"kind": k, "x": int(t[1]), "y": int(t[2]), "z": float(t[3]), "along": None, "n": 0,
                  "open": False, "height": None}
            i = 4
            while i < len(t):
                if t[i] == "along":
                    sh["along"], sh["n"] = t[i + 1], int(t[i + 2])
                    i += 3
                elif t[i] == "open":
                    sh["open"] = True
                    i += 1
                elif t[i] == "height":
                    sh["height"] = int(t[i + 1])
                    i += 2
                else:
                    return None
            return sh
    except (ValueError, IndexError):
        return None
    return None


def code(sh):
    """the statement for parse()'s fields"""
    if sh["kind"] == "chute":
        out = ["chute", str(sh["width"]), sh["prof"], "depth", str(sh["depth"])]
        for i, (x, y, z) in enumerate(sh["ways"]):
            out += ["way", str(x), str(y)] + ([_g(z if z is not None or i else 0)] if z is not None or not i else [])
        return " ".join(out)
    if sh["kind"] == "pit":
        out = "pit %d %d %s radius %d depth %d" % (sh["x"], sh["y"], _g(sh["z"]), sh["radius"], sh["depth"])
        return out + (" hole %d" % sh["hole"] if sh["hole"] != 1 else "")
    out = "hump %d %d %s" % (sh["x"], sh["y"], _g(sh["z"]))
    if sh["along"]:
        out += " along %s %d%s" % (sh["along"], sh["n"], " open" if sh["open"] else "")
    return out + (" height %d" % sh["height"] if sh["height"] else "")


def lip_heights(ways):
    """each way's lip height: its own, else the way before's (130.28.3)"""
    out, z = [], 0.0
    for w in ways:
        z = w[2] if w[2] is not None else z
        out.append(z)
    return out


def drag_way(ways, i, nx, ny):
    """way I moved to (NX, NY), every leg kept on its axis: an END slides along its own leg (it lengthens or
    shortens the chute), an inner corner moves freely and takes its two neighbours' shared coordinate with
    it. -> the new ways (the caller's are not changed)"""
    w = [list(p) for p in ways]
    n = len(w)

    def along_x(a, b):
        return w[a][1] == w[b][1]
    if i in (0, n - 1):
        j = 1 if i == 0 else n - 2
        if along_x(i, j):
            w[i][0] = nx
        else:
            w[i][1] = ny
        return w
    for j in (i - 1, i + 1):
        if along_x(i, j):
            w[j][1] = ny
        else:
            w[j][0] = nx
    w[i][0], w[i][1] = nx, ny
    return w


def add_leg(ways, turn, length=4):
    """a leg added at the far end: turn 'left', 'right' (a new corner, on the plan as drawn: x right, y
    down) or 'straight' (the last leg made longer)"""
    w = [list(p) for p in ways]
    d = (_sg(w[-1][0] - w[-2][0]), _sg(w[-1][1] - w[-2][1]))
    if turn == "straight":
        w[-1][0] += d[0] * length
        w[-1][1] += d[1] * length
        return w
    r = (d[1], -d[0]) if turn == "left" else (-d[1], d[0])
    w.append([w[-1][0] + r[0] * length, w[-1][1] + r[1] * length, None])
    return w


def remove_leg(ways):
    return [list(p) for p in ways[:-1]] if len(ways) > 2 else [list(p) for p in ways]


def reverse(ways):
    """the same chute run the other way: each way's lip as it was, written only where it changes"""
    z = lip_heights(ways)
    w = [[x, y, h] for (x, y, _), h in zip(ways, z)][::-1]
    for i in range(len(w) - 1, 0, -1):
        if w[i][2] == w[i - 1][2]:
            w[i][2] = None
    return w


def new_shape(kind, x, y, z):
    """a shape made from nothing at cell (X, Y) on ground Z: each is the smallest the compiler lays"""
    if kind == "chute":
        return {"kind": kind, "width": 1, "prof": "round", "depth": 5, "ways": [[x, y, z], [x + 6, y, None]]}
    if kind == "pit":
        return {"kind": kind, "x": x + 3, "y": y + 3, "z": z, "radius": 3, "depth": 16, "hole": 1}
    return {"kind": kind, "x": x + 1, "y": y + 1, "z": z, "along": None, "n": 0, "open": False, "height": None}


def describe(sh):
    if sh["kind"] == "chute":
        n = len(sh["ways"]) - 1
        return "Chute: %d wide, %s, %d leg%s" % (sh["width"], sh["prof"], n, "" if n == 1 else "s")
    if sh["kind"] == "pit":
        return "Pit at %d, %d: radius %d" % (sh["x"], sh["y"], sh["radius"])
    return "Hump at %d, %d%s" % (sh["x"], sh["y"], (", a ridge along %s" % sh["along"]) if sh["along"] else "")


# ----------------------------------------------------------------------------
# the tab
# ----------------------------------------------------------------------------

class ShapesTab(object):
    def __init__(self, app, nb, tk, ttk, Job, hcolour):
        self.app, self.tk, self.ttk, self.Job, self.hcolour = app, tk, ttk, Job, hcolour
        self.line = None                # the shape statement shown
        self.sh = None
        self.drag = None
        self.view = None                # (x0, y0, s, ox, oy): the canvas's window onto the grid
        self.ride_job = None
        self.ride_after = None
        self.rides = {}                 # {statement text: the job's answer}
        self.wsel = None                # the selected way (a chute's)
        f = ttk.Frame(nb)
        nb.insert(1, f, text="Shapes")
        self.frame = f
        left = ttk.Frame(f, padding=6, width=230)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Shapes on this course", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.lb = tk.Listbox(left, width=32, height=14, exportselection=False)
        self.lb.pack(fill="y", expand=False, pady=4)
        self.lb.bind("<<ListboxSelect>>", lambda e: self._pick())
        for kind, label in (("chute", "New chute"), ("pit", "New pit"), ("hump", "New hump")):
            ttk.Button(left, text=label, command=lambda k=kind: self.new(k)).pack(fill="x", pady=1)
        ttk.Label(left, wraplength=220, foreground="#444", justify="left",
                  text="A new shape goes on the area selected on the Build tab (or beside the start), at "
                       "the floor's height there.\n\nDrag the numbered handles: an end slides along its "
                       "leg, a corner moves and its legs follow. Every change is checked; one the course "
                       "compiler refuses is undone with the reason.").pack(anchor="w", pady=8)
        right = ttk.Frame(f, padding=6, width=440)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self.title_l = ttk.Label(right, text="", font=("TkDefaultFont", 12, "bold"))
        self.title_l.pack(anchor="w")
        self.form = ttk.Frame(right)
        self.form.pack(fill="x", pady=4)
        ttk.Label(right, text="Height along it", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(8, 0))
        self.graph = tk.Canvas(right, width=420, height=130, background="#1b1d22", highlightthickness=0)
        self.graph.pack(anchor="w")
        rb = ttk.Frame(right)
        rb.pack(fill="x", pady=(8, 0))
        ttk.Label(rb, text="How each ball rides it", font=("TkDefaultFont", 10, "bold")).pack(side="left")
        ttk.Button(rb, text="Roll again", command=self.run_ride).pack(side="right")
        self.ride_t = tk.Text(right, width=44, height=12, wrap="word", font=("TkDefaultFont", 9),
                              background="#f6f6f2", relief="flat")
        self.ride_t.pack(fill="both", expand=True)
        self.ride_t.tag_configure("ball", font=("TkDefaultFont", 9, "bold"))
        self.ride_t.tag_configure("bad", foreground="#a01818")
        self.ride_t.configure(state="disabled")
        self.cv = tk.Canvas(f, background="#2a2d33", highlightthickness=0)
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.draw())
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._motion)
        self.cv.bind("<ButtonRelease-1>", self._release)

    # -- the list -----------------------------------------------------------
    def shapes(self):
        out = []
        for st in self.app.doc.statements():
            if st.kind in ("chute", "pit", "hump"):
                sh = parse(st.toks)
                if sh:
                    out.append((st.line, sh))
        return out

    def refresh(self):
        """the document changed: the list, the shape shown (followed to its line), the drawing"""
        shs = self.shapes()
        self.lb.delete(0, "end")
        for ln, sh in shs:
            self.lb.insert("end", "line %d  %s" % (ln, describe(sh)))
        lines = [ln for ln, _ in shs]
        if self.line not in lines:
            self.line = lines[0] if lines else None
        if self.line:
            self.lb.selection_set(lines.index(self.line))
            self.sh = dict(shs[lines.index(self.line)][1])
        else:
            self.sh = None
        self._fill_form()
        self.draw()
        self._schedule_ride()

    def _pick(self):
        sel = self.lb.curselection()
        if not sel:
            return
        self.line = self.shapes()[sel[0]][0]
        self.wsel = None
        self.refresh()
        self.app.select(self.line)

    def shown(self):
        return self.frame.winfo_ismapped()

    # -- edits --------------------------------------------------------------
    def apply(self, sh, label="edit a shape"):
        """the statement rewritten from SH, through the window's checked edit (undone with the reason when
        the compiler refuses it)"""
        if self.line is None:
            return
        self.app._edit(self.app.doc.set_statement, self.line, code(sh), label=label)

    def new(self, kind):
        app = self.app
        a = app.doc.analysis()
        if app.area:
            x, y = app.area[0], app.area[1]
        else:
            st = [s for s in app.doc.statements() if s.kind == "start"]
            x, y = (int(st[0].toks[1]) + 2, int(st[0].toks[2]) + 2) if st else (4, 4)
        d = a["cells"].get((x, y))
        z = d["h"] if d and d["kind"] in ("floor", "goal") else float(app.height.get() or 0)
        ln = app._edit(app.doc.insert, code(new_shape(kind, x, y, z)), label="add a %s" % kind)
        if ln:
            self.line = ln
            self.refresh()

    def _ivar(self, v, lo, hi):
        try:
            return max(lo, min(hi, int(float(v.get()))))
        except (ValueError, self.tk.TclError):
            return None

    def _fvar(self, v):
        try:
            return round(float(v.get()) * 4) / 4.0
        except (ValueError, self.tk.TclError):
            return None

    def _fill_form(self):
        tk, ttk = self.tk, self.ttk
        for w in self.form.winfo_children():
            w.destroy()
        sh = self.sh
        if not sh:
            self.title_l.config(text="No shape on this course yet")
            ttk.Label(self.form, wraplength=330, foreground="#444",
                      text="Press New chute, New pit or New hump on the left.").pack(anchor="w")
            return
        self.title_l.config(text="%s (line %d)" % (describe(sh), self.line))
        row = [0]

        def field(label, var, lo, hi, inc=1, cmd=None, width=6):
            ttk.Label(self.form, text=label).grid(row=row[0], column=0, sticky="w", pady=1)
            sb = ttk.Spinbox(self.form, from_=lo, to=hi, increment=inc, width=width, textvariable=var,
                             command=cmd)
            sb.grid(row=row[0], column=1, sticky="w")
            sb.bind("<Return>", lambda e: cmd())
            sb.bind("<FocusOut>", lambda e: cmd())
            row[0] += 1

        def choice(label, var, values, cmd):
            ttk.Label(self.form, text=label).grid(row=row[0], column=0, sticky="w", pady=1)
            fr = ttk.Frame(self.form)
            fr.grid(row=row[0], column=1, sticky="w")
            for v in values:
                ttk.Radiobutton(fr, text=str(v), value=v, variable=var, command=cmd).pack(side="left")
            row[0] += 1
        if sh["kind"] == "chute":
            wv, pv, dv = tk.IntVar(value=sh["width"]), tk.StringVar(value=sh["prof"]), tk.IntVar(value=sh["depth"])
            setw = lambda: self.apply(dict(sh, width=wv.get()), "chute width")       # noqa: E731
            choice("Width (cells)", wv, (1, 2, 3), setw)
            choice("Cross-section", pv, ("round", "bank"), lambda: self.apply(dict(sh, prof=pv.get()), "chute profile"))
            field("Depth (px, lip to bottom)", dv, 2, 24, 1,
                  lambda: self._ivar(dv, 2, 24) and self._ivar(dv, 2, 24) != sh["depth"]
                  and self.apply(dict(sh, depth=self._ivar(dv, 2, 24)), "chute depth"))
            ttk.Label(self.form, text="Ways (click one in the list or on the plan)").grid(
                row=row[0], column=0, columnspan=2, sticky="w", pady=(6, 0))
            row[0] += 1
            tv = ttk.Treeview(self.form, columns=("x", "y", "lip"), show="headings", height=min(6, len(sh["ways"])))
            for c_, w_ in (("x", 60), ("y", 60), ("lip", 150)):
                tv.heading(c_, text={"lip": "lip height"}.get(c_, c_))
                tv.column(c_, width=w_, anchor="center")
            zs = lip_heights(sh["ways"])
            for i, (x, y, z) in enumerate(sh["ways"]):
                tv.insert("", "end", iid=str(i), values=(x, y, ("%g" % zs[i]) + ("" if z is not None or not i
                                                                                 else " (level)")))
            tv.grid(row=row[0], column=0, columnspan=2, sticky="we")
            if self.wsel is not None and self.wsel < len(sh["ways"]):
                tv.selection_set(str(self.wsel))
            tv.bind("<<TreeviewSelect>>", lambda e: self._way_picked(tv))
            row[0] += 1
            zv = tk.StringVar(value=("%g" % zs[self.wsel]) if self.wsel is not None and self.wsel < len(zs) else "")
            fr = ttk.Frame(self.form)
            fr.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=2)
            ttk.Label(fr, text="Selected way's lip").pack(side="left")
            e = ttk.Spinbox(fr, from_=-8, to=60, increment=0.5, width=6, textvariable=zv)
            e.pack(side="left", padx=4)
            ttk.Button(fr, text="Set", command=lambda: self._set_lip(zv)).pack(side="left")
            ttk.Button(fr, text="Level", command=lambda: self._set_lip(None)).pack(side="left")
            row[0] += 1
            ttk.Label(self.form, text="A lip on a later way makes the leg before it a slope.", foreground="#555",
                      wraplength=330).grid(row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            fr = ttk.Frame(self.form)
            fr.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(6, 0))
            ttk.Label(fr, text="Add a leg at the end:").pack(side="left")
            row[0] += 1
            fr = ttk.Frame(self.form)
            fr.grid(row=row[0], column=0, columnspan=2, sticky="w")
            for txt, t in (("Turn left", "left"), ("Straight on", "straight"), ("Turn right", "right")):
                ttk.Button(fr, text=txt, command=lambda t=t: self.apply(dict(sh, ways=add_leg(sh["ways"], t)),
                                                                         "add a leg")).pack(side="left")
            row[0] += 1
            fr = ttk.Frame(self.form)
            fr.grid(row=row[0], column=0, columnspan=2, sticky="w")
            ttk.Button(fr, text="Remove the last leg",
                       command=lambda: self.apply(dict(sh, ways=remove_leg(sh["ways"])), "remove a leg")).pack(side="left")
            ttk.Button(fr, text="Run it the other way",
                       command=lambda: self.apply(dict(sh, ways=reverse(sh["ways"])), "reverse the chute")).pack(side="left")
            row[0] += 1
        elif sh["kind"] == "pit":
            vs = {k: tk.StringVar(value=_g(sh[k]) if k == "z" else str(sh[k]))
                  for k in ("z", "radius", "depth", "hole")}

            def setp(k, lo, hi):
                def f_():
                    v = self._fvar(vs[k]) if k == "z" else self._ivar(vs[k], lo, hi)
                    if v is not None and v != sh[k]:
                        self.apply(dict(sh, **{k: v}), "pit %s" % k)
                return f_
            field("Lip height (units)", vs["z"], -8, 60, 0.5, setp("z", 0, 0))
            field("Radius (cells, 2 - 4)", vs["radius"], 2, 4, 1, setp("radius", 2, 4))
            field("Depth (px)", vs["depth"], 2, 40, 1, setp("depth", 2, 40))
            field("Hole (0 none, 1 2x2, 2 4x4)", vs["hole"], 0, 3, 1, setp("hole", 0, 3))
        else:
            vs = {"z": tk.StringVar(value=_g(sh["z"])), "height": tk.StringVar(value=str(sh["height"] or 8)),
                  "n": tk.StringVar(value=str(sh["n"] or 3))}
            av = tk.StringVar(value=sh["along"] or "dome")
            ov = tk.BooleanVar(value=sh["open"])

            def seth():
                n = self._ivar(vs["n"], 1, 12) or 3
                new = dict(sh, z=self._fvar(vs["z"]) if self._fvar(vs["z"]) is not None else sh["z"],
                           height=self._ivar(vs["height"], 2, 11), along=None if av.get() == "dome" else av.get(),
                           n=0 if av.get() == "dome" else n, open=ov.get() and av.get() != "dome")
                if new["height"] == 8 and not sh["height"]:
                    new["height"] = None
                if code(new) != code(sh):
                    self.apply(new, "edit the hump")
            choice("Shape", av, ("dome", "x", "y"), seth)
            field("Ridge length (cells)", vs["n"], 1, 12, 1, seth)
            ttk.Checkbutton(self.form, text="Open ends (no caps)", variable=ov, command=seth).grid(
                row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            field("Base height (units)", vs["z"], -8, 60, 0.5, seth)
            field("Height (px, 2 - 11)", vs["height"], 2, 11, 1, seth)

    def _way_picked(self, tv):
        s = tv.selection()
        self.wsel = int(s[0]) if s else None
        self.draw()

    def _set_lip(self, zv):
        sh, i = self.sh, self.wsel
        if not sh or sh["kind"] != "chute" or i is None:
            self.app._msg("Select a way first (in the list, or click its handle)")
            return
        z = None if zv is None else self._fvar(zv)
        if zv is not None and z is None:
            return
        if i == 0 and z is None:
            self.app._msg("The first way always names the lip's height")
            return
        w = [list(p) for p in sh["ways"]]
        w[i][2] = z
        self.apply(dict(sh, ways=w), "set a lip height")

    # -- the plan -----------------------------------------------------------
    def _bbox(self, sh):
        if sh["kind"] == "chute":
            xs = [w[0] for w in sh["ways"]]
            ys = [w[1] for w in sh["ways"]]
            m = sh["width"]
            return min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m
        r = sh.get("radius", 2) if sh["kind"] == "pit" else 1
        n = sh.get("n", 0)
        ex, ey = (n, 0) if sh.get("along") == "x" else (0, n) if sh.get("along") == "y" else (0, 0)
        return sh["x"] - r, sh["y"] - r, sh["x"] + r + ex, sh["y"] + r + ey

    def _pt(self, x, y, centre):
        x0, y0, s, ox, oy = self.view
        k = 0.5 if centre else 0.0
        return ox + (x - x0 + k) * s, oy + (y - y0 + k) * s

    def _handles(self, sh):
        """[(index, x, y, centre)]: the draggable points"""
        if sh["kind"] == "chute":
            c = sh["width"] != 2
            return [(i, w[0], w[1], c) for i, w in enumerate(sh["ways"])]
        return [(0, sh["x"], sh["y"], False)]

    def draw(self):
        c = self.cv
        c.delete("all")
        sh = self.sh
        W, H = max(50, c.winfo_width()), max(50, c.winfo_height())
        if not sh:
            c.create_text(20, 20, anchor="nw", fill="#e6e6e6", width=W - 40,
                          text="No chute, pit or hump on this course. Select an area on the Build tab, then press "
                               "New chute, New pit or New hump.")
            self.graph.delete("all")
            return
        bx0, by0, bx1, by1 = self._bbox(sh)
        bx0, by0, bx1, by1 = bx0 - 3, by0 - 3, bx1 + 4, by1 + 4
        s = max(8, min(48, min((W - 20) / float(bx1 - bx0), (H - 20) / float(by1 - by0))))
        self.view = (bx0, by0, s, (W - s * (bx1 - bx0)) / 2.0, (H - s * (by1 - by0)) / 2.0)
        a = self.app.doc.analysis()
        mine = set()
        for (x, y), d in a["cells"].items():
            if not (bx0 <= x < bx1 and by0 <= y < by1):
                continue
            px, py = self._pt(x, y, False)
            h = d["hmin"] if d["kind"] == "field" else d["h"]
            c.create_rectangle(px, py, px + s, py + s, fill=self.hcolour(h), outline="#1b1d22")
            if d["kind"] == "field":
                lo, hi = d["hmin"], d["hmax"]
                c.create_rectangle(px + s * .25, py + s * .25, px + s * .75, py + s * .75,
                                   fill=self.hcolour(hi), width=0)
            if d["line"] == self.line:
                mine.add((x, y))
            if s >= 30:
                c.create_text(px + 3, py + 2, anchor="nw", fill="#111", font=("TkDefaultFont", 7),
                              text=("%g" % d["h"]) if d["kind"] != "field" else "%g-%g" % (d["hmin"], d["hmax"]))
        for (x, y) in mine:
            px, py = self._pt(x, y, False)
            c.create_rectangle(px, py, px + s, py + s, outline="#ffd54f", width=2)
        if s >= 14:                             # the grid's numbers along the top and the left
            for x in range(bx0, bx1):
                c.create_text(self._pt(x, by0, True)[0], self.view[4] - 8, text=str(x), fill="#9aa",
                              font=("TkDefaultFont", 7))
            for y in range(by0, by1):
                c.create_text(self.view[3] - 10, self._pt(bx0, y, True)[1], text=str(y), fill="#9aa",
                              font=("TkDefaultFont", 7))
        sh = self.drag["sh"] if self.drag else sh
        hs = self._handles(sh)
        if sh["kind"] == "chute":
            pts = [self._pt(x, y, ctr) for _, x, y, ctr in hs]
            c.create_line(*[v for p in pts for v in p], fill="#29e6ff", width=3, capstyle="round", joinstyle="round")
        elif sh["kind"] == "pit":
            cx_, cy_ = self._pt(sh["x"], sh["y"], False)
            r = sh["radius"] * s
            c.create_oval(cx_ - r, cy_ - r, cx_ + r, cy_ + r, outline="#29e6ff", width=2)
            if sh["hole"]:
                q = sh["hole"] * s
                c.create_rectangle(cx_ - q, cy_ - q, cx_ + q, cy_ + q, outline="#ff6b6b", width=2, dash=(3, 2))
        else:
            cx_, cy_ = self._pt(sh["x"], sh["y"], False)
            n = sh["n"] or 0
            ex, ey = (n * s, 0) if sh["along"] == "x" else (0, n * s) if sh["along"] == "y" else (0, 0)
            c.create_line(cx_, cy_, cx_ + ex, cy_ + ey, fill="#29e6ff", width=4, capstyle="round")
        for i, x, y, ctr in hs:
            px, py = self._pt(x, y, ctr)
            on = i == self.wsel and sh["kind"] == "chute"
            c.create_oval(px - 9, py - 9, px + 9, py + 9, fill="#ffd54f" if on else "#29e6ff", outline="#111")
            c.create_text(px, py, text=str(i + 1), fill="#111", font=("TkDefaultFont", 8, "bold"))
        self._draw_graph(sh)

    def _draw_graph(self, sh):
        g = self.graph
        g.delete("all")
        Wg, Hg = 420, 130
        if sh["kind"] == "chute":
            ws = sh["ways"]
            zs = lip_heights(ws)
            dist = [0]
            for p, q in zip(ws, ws[1:]):
                dist.append(dist[-1] + abs(q[0] - p[0]) + abs(q[1] - p[1]))
            bot = [z - sh["depth"] / 8.0 for z in zs]
            lo, hi = min(bot) - 0.5, max(zs) + 0.5
            L = float(dist[-1] or 1)
            X = lambda d: 30 + d / L * (Wg - 45)                    # noqa: E731
            Y = lambda z: Hg - 18 - (z - lo) / (hi - lo) * (Hg - 30)   # noqa: E731
            g.create_line(*[v for d, z in zip(dist, zs) for v in (X(d), Y(z))], fill="#7ee081", width=2)
            g.create_line(*[v for d, z in zip(dist, bot) for v in (X(d), Y(z))], fill="#7aa7ff", width=2, dash=(4, 2))
            for i, (d, z) in enumerate(zip(dist, zs)):
                g.create_oval(X(d) - 3, Y(z) - 3, X(d) + 3, Y(z) + 3, fill="#ffd54f" if i == self.wsel else "#7ee081")
                g.create_text(X(d), Hg - 8, text=str(i + 1), fill="#ccc", font=("TkDefaultFont", 7))
            g.create_text(4, Y(hi - 0.5), anchor="w", text="%g" % (hi - 0.5), fill="#ccc", font=("TkDefaultFont", 7))
            g.create_text(4, Y(lo + 0.5), anchor="w", text="%g" % (lo + 0.5), fill="#ccc", font=("TkDefaultFont", 7))
            g.create_text(Wg - 4, 8, anchor="ne", text="lip (green), bottom (blue), units; %g cells long" % L,
                          fill="#ccc", font=("TkDefaultFont", 7))
        else:                                   # a cross-section through the centre
            depth = (sh["depth"] if sh["kind"] == "pit" else -(sh["height"] or 8)) / 8.0
            r = sh["radius"] if sh["kind"] == "pit" else 1.5
            hole = sh.get("hole", 0) if sh["kind"] == "pit" else 0
            import math
            pts = []
            for k in range(61):
                u = -r - 1 + (2 * r + 2) * k / 60.0
                f = max(0.0, 1 - (u / r) ** 2) if abs(u) < r else 0.0
                pts.append((u, sh["z"] - depth * math.sqrt(f)))
            zl = [p[1] for p in pts]
            lo, hi = min(zl) - 0.5, max(zl) + 0.5
            X = lambda u: 20 + (u + r + 1) / (2 * r + 2) * (Wg - 40)   # noqa: E731
            Y = lambda z: Hg - 18 - (z - lo) / (hi - lo) * (Hg - 30)   # noqa: E731
            seg = []
            for u, z in pts:
                if hole and abs(u) < hole:
                    if len(seg) > 1:
                        g.create_line(*seg, fill="#7ee081", width=2)
                    seg = []
                    continue
                seg += [X(u), Y(z)]
            if len(seg) > 1:
                g.create_line(*seg, fill="#7ee081", width=2)
            g.create_text(Wg - 4, 8, anchor="ne", fill="#ccc", font=("TkDefaultFont", 7),
                          text="a cross-section through the centre (a sketch; units)%s" % (
                              ", the hole falls through" if hole else ""))

    def _hit(self, e):
        if not self.sh or not self.view:
            return None
        for i, x, y, ctr in self._handles(self.sh):
            px, py = self._pt(x, y, ctr)
            if abs(px - e.x) <= 11 and abs(py - e.y) <= 11:
                return i
        return None

    def _cell(self, e, centre):
        x0, y0, s, ox, oy = self.view
        fx, fy = (e.x - ox) / s + x0, (e.y - oy) / s + y0
        import math
        return (int(math.floor(fx)), int(math.floor(fy))) if centre else (int(round(fx)), int(round(fy)))

    def _press(self, e):
        i = self._hit(e)
        if i is None:
            return
        self.wsel = i if self.sh["kind"] == "chute" else None
        self.drag = {"i": i, "sh": self.sh, "moved": False}
        self.draw()

    def _motion(self, e):
        d = self.drag
        if not d:
            return
        sh = self.sh
        ctr = sh["kind"] == "chute" and sh["width"] != 2
        nx, ny = self._cell(e, ctr if sh["kind"] == "chute" else False)
        if sh["kind"] == "chute":
            new = dict(sh, ways=drag_way(sh["ways"], d["i"], nx, ny))
        else:
            new = dict(sh, x=nx, y=ny)
        if code(new) != code(d["sh"]):
            d["sh"], d["moved"] = new, True
            self.draw()

    def _release(self, e):
        d, self.drag = self.drag, None
        if d and d["moved"] and code(d["sh"]) != code(self.sh):
            self.apply(d["sh"], "move a handle")
        else:
            self._fill_form()
            self.draw()

    # -- how each ball rides it ---------------------------------------------------
    def _schedule_ride(self):
        if self.ride_after:
            self.app.root.after_cancel(self.ride_after)
            self.ride_after = None
        if not self.sh or not self.shown():
            return
        if self.app.doc.lines[self.line - 1] in self.rides:
            self._show_ride(self.rides[self.app.doc.lines[self.line - 1]])
            return
        self._ride_text([("Rolling each ball over it in a moment...", None)])
        self.ride_after = self.app.root.after(900, self.run_ride)

    def run_ride(self):
        self.ride_after = None
        if self.ride_job:
            self.ride_job.kill()
        if not self.sh or self.app.doc.analysis()["error"]:
            self._ride_text([("The course has to lay out first.", None)])
            return
        key = self.app.doc.lines[self.line - 1]
        p = self.app._write_tmp("ride")

        def ev(job, e):
            if e["stage"] == "done":
                if e.get("ok"):
                    self.rides[key] = e["rides"]
                    if self.line and self.app.doc.lines[self.line - 1] == key:
                        self._show_ride(e["rides"])
                else:
                    self._ride_text([("Could not roll it: %s" % e.get("error"), "bad")])
            elif e["stage"] not in ("exit", "log"):
                self._ride_text([("%s..." % e.get("what", e["stage"]).capitalize(), None)])
        self.ride_job = self.Job(["ride", p, str(self.line), "--name", self.app._name()], ev).start()

    def poll(self):
        if self.ride_job:
            self.ride_job.poll()
            if not self.ride_job.running:
                self.ride_job.poll()
                self.ride_job = None

    def _ride_text(self, parts):
        t = self.ride_t
        t.configure(state="normal")
        t.delete("1.0", "end")
        for txt, tag in parts:
            t.insert("end", txt, tag or ())
        t.configure(state="disabled")

    def _show_ride(self, rides):
        parts, last = [], None
        for r in rides:
            if r["ball"] != last:
                parts.append(("%s%s\n" % ("\n" if last else "", r["ball"].capitalize()), "ball"))
                last = r["ball"]
            parts.append(("  %s\n" % r["words"], "bad" if r["result"] == "fell" else None))
        parts.append(("\nThe game's own physics, steered by its autopilot (or no keys), on the course as it "
                      "stands. A sketch of what a player meets, not a promise.", None))
        self._ride_text(parts)
