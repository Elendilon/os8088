#!/usr/bin/env python3
"""bbedshape - THE COURSE BUILDER'S SHAPE EDITOR (SPEC.md 130.58.19, 130.58.29): chutes, pits, humps and
tubes (130.28, 130.44, 130.12.3.3) edited in place on the Build tab's plan - a path drawn with handles, a bowl,
a ridge - as a DRAFT until Try it, with the height graph and how each ball rides the shape (bbedjob.py `ride`,
the game's own Physics).

The helpers at the top are the editor's model and import no Tk: the window and the row
(tests/unit/t_bbedit.py) both call them. The editor (`ShapeEditor`) is made by tools/bbedit.py, which hands
it the window (its document, `_edit`, the plan's coordinates, the job runner and the height colours).
"""

import sys

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
PATHS = ("chute", "tube")      # the shapes drawn and dragged as a path of points (a chute's ways, a tube's IN/vias/OUT)


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
        if k == "tube":                         # SPEC.md 130.12.3.3: its IN, vias and OUT as the path's points
            sh = {"kind": k, "sub": t[1], "width": 1, "ways": [[int(t[2]), int(t[3]), None]], "out": None,
                  "speed": None, "height": None, "body": None}
            last = [int(t[4]), int(t[5]), None]
            i = 6
            while i < len(t):
                if t[i] == "via":
                    sh["ways"].append([int(t[i + 1]), int(t[i + 2]), None])
                    i += 3
                elif t[i] == "out":
                    sh["out"] = t[i + 1]
                    i += 2
                elif t[i] == "speed":
                    sh["speed"] = [int(t[i + 1]), int(t[i + 2]), int(t[i + 3])]
                    i += 4
                elif t[i] == "height":
                    sh["height"] = float(t[i + 1])
                    i += 2
                elif t[i] == "body":            # (one height, or one a leg: SPEC.md 130.12.3.5)
                    hs = [float(t[i + 1])]
                    i += 2
                    while i < len(t) and _num(t[i]):
                        hs.append(float(t[i]))
                        i += 1
                    sh["body"] = hs[0]
                    if len(hs) > 1:
                        sh["legs"] = hs
                elif t[i] == "column":
                    sh["column"] = float(t[i + 1])
                    i += 2
                else:
                    return None
            sh["ways"].append(last)
            hs = sh.pop("legs", None)
            if hs is not None:                  # each leg's height on the way it STARTS at, where it changes
                if len(hs) != len(sh["ways"]) - 1:
                    return None
                for k in range(1, len(hs)):
                    sh["ways"][k][2] = hs[k] if hs[k] != hs[k - 1] else None
            return sh
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
    if sh["kind"] == "tube":
        w = sh["ways"]
        out = "tube %s %d %d %d %d" % (sh["sub"], w[0][0], w[0][1], w[-1][0], w[-1][1])
        out += "".join(" via %d %d" % (x, y) for x, y, _z in w[1:-1])
        if sh.get("out"):
            out += " out %s" % sh["out"]
        if sh["sub"] == "launch":
            out += " speed %d %d %d" % tuple(sh.get("speed") or (0, 0, 0))
        if sh["sub"] == "drop":
            out += " height %s" % _g(sh.get("height") or 2)
        hs = leg_heights(sh)
        if hs is not None:
            out += " body " + (_g(hs[0]) if len(set(hs)) == 1 else " ".join(_g(h) for h in hs))
        if sh.get("column") is not None:
            out += " column %s" % _g(sh["column"])
        return out
    if sh["kind"] == "pit":
        out = "pit %d %d %s radius %d depth %d" % (sh["x"], sh["y"], _g(sh["z"]), sh["radius"], sh["depth"])
        return out + (" hole %d" % sh["hole"] if sh["hole"] != 1 else "")
    out = "hump %d %d %s" % (sh["x"], sh["y"], _g(sh["z"]))
    if sh["along"]:
        out += " along %s %d%s" % (sh["along"], sh["n"], " open" if sh["open"] else "")
    return out + (" height %d" % sh["height"] if sh["height"] else "")


def leg_heights(sh):
    """SPEC.md 130.58.39: a tube's pipe height a LEG, [h1 .. hn] (None: automatic) - its `body` the first leg's,
    and a way's own height (ways[k][2], k >= 1) the leg that STARTS there and every one after it until the next"""
    if sh.get("body") is None:
        return None
    z, out = sh["body"], []
    for k in range(len(sh["ways"]) - 1):
        if k and sh["ways"][k][2] is not None:
            z = sh["ways"][k][2]
        out.append(z)
    return out


def set_leg_height(sh, k, v):
    """the tube SH with leg K's pipe at V and every other leg as it was (an automatic tube's legs all at V
    first) -> the new fields"""
    hs = leg_heights(sh) or [v] * (len(sh["ways"]) - 1)
    hs[k] = v
    w = [list(p) for p in sh["ways"]]
    for j in range(1, len(w)):
        w[j][2] = hs[j] if j < len(hs) and hs[j] != hs[j - 1] else None
    return dict(sh, body=hs[0], ways=w)


def axis_path(ways):
    """SPEC.md 130.58.27: a drafted path made one an axis-legged shape can take - a corner added where two points
    differ along both axes (along x first), a repeated point dropped, and a point in the middle of a straight run
    dropped unless it carries a height of its own (a chute's lip). -> the new ways"""
    out = [list(ways[0])]
    for q in ways[1:]:
        p = out[-1]
        if p[0] != q[0] and p[1] != q[1]:
            out.append([q[0], p[1], None])
        if q[:2] != out[-1][:2]:
            out.append(list(q))
        elif q[2] is not None:
            out[-1][2] = q[2]
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        if b[2] is None and ((a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1])):
            del out[i]
        else:
            i += 1
    return out


def insert_point(ways, cell):
    """a point added at CELL where it is nearest the path: after the last point when past it, before the first
    when before it, else between the two points of the nearest leg"""
    best = None
    for j, (p, q) in enumerate(zip(ways, ways[1:])):
        dx, dy = q[0] - p[0], q[1] - p[1]
        L2 = float(dx * dx + dy * dy) or 1.0
        t = ((cell[0] - p[0]) * dx + (cell[1] - p[1]) * dy) / L2
        tc = max(0.0, min(1.0, t))
        d = (p[0] + tc * dx - cell[0]) ** 2 + (p[1] + tc * dy - cell[1]) ** 2
        if best is None or d < best[0] - 1e-9:
            best = (d, j, t)
    w = [list(p) for p in ways]
    _d, j, t = best
    if j == len(ways) - 2 and t >= 1:           # (at or past the last point: a new last point)
        w.append([cell[0], cell[1], None])
    elif j == 0 and t <= 0:
        w.insert(0, [cell[0], cell[1], w[0][2]])
        w[1][2] = None if w[1][2] == w[0][2] else w[1][2]
    else:
        w.insert(j + 1, [cell[0], cell[1], None])
    return w


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
    if kind == "tube":                          # (a KEEP tube 4 cells along x: its body the tube lays itself)
        return {"kind": kind, "sub": "keep", "width": 1, "ways": [[x, y, None], [x + 4, y, None]], "out": None,
                "speed": None, "height": None, "body": None}
    if kind == "pit":
        return {"kind": kind, "x": x + 3, "y": y + 3, "z": z, "radius": 3, "depth": 16, "hole": 1}
    return {"kind": kind, "x": x + 1, "y": y + 1, "z": z, "along": None, "n": 0, "open": False, "height": None}


def describe(sh):
    if sh["kind"] == "chute":
        n = len(sh["ways"]) - 1
        return "Chute: %d wide, %s, %d leg%s" % (sh["width"], sh["prof"], n, "" if n == 1 else "s")
    if sh["kind"] == "tube":
        n = len(sh["ways"]) - 1
        return "Tube (%s): %d, %d to %d, %d, %d leg%s" % (sh["sub"], sh["ways"][0][0], sh["ways"][0][1],
                                                          sh["ways"][-1][0], sh["ways"][-1][1], n, "" if n == 1 else "s")
    if sh["kind"] == "pit":
        return "Pit at %d, %d: radius %d" % (sh["x"], sh["y"], sh["radius"])
    return "Hump at %d, %d%s" % (sh["x"], sh["y"], (", a ridge along %s" % sh["along"]) if sh["along"] else "")


# ----------------------------------------------------------------------------
# the tab
# ----------------------------------------------------------------------------

class ShapeEditor(object):
    """SPEC.md 130.58.29: a chute, pit, hump or tube edited IN PLACE on the Build tab - its handles drawn on the
    plan over the real floors and walls, its form, height graph and ride readout in the inspector, its edits a
    DRAFT until Try it (130.58.27), a refusal in the same tab's banner"""

    def __init__(self, app, tk, ttk, Job, hcolour):
        self.app, self.tk, self.ttk, self.Job, self.hcolour = app, tk, ttk, Job, hcolour
        self.line = None                # the shape statement being edited
        self.sh = None
        self.drag = None
        self.ride_job = None
        self.rides = {}                 # {statement text: the job's answer}
        self.wsel = None                # the selected point (a path's)
        self.draft = None               # the shape as edited, not yet tried (SPEC.md 130.58.27)
        self.form = self.graph = self.ride_t = None

    KINDS = ("chute", "pit", "hump", "tube")

    def load(self, line):
        """the shape on LINE (its draft kept while the same line stays selected) -> its fields, or None"""
        try:
            st = self.app.doc.statement(line)
        except Exception:
            return None
        sh = parse(st.toks) if st.kind in self.KINDS else None
        if line != self.line:
            self.draft, self.wsel, self.drag = None, None, None
        self.line, self.sh = (line, sh) if sh else (None, None)
        return sh

    def active(self):
        return self.line is not None and self.app.sel == self.line and self.cur() is not None

    def fill(self, body):
        """the inspector's part: the draft bar and the form, the height graph, how each ball rides it"""
        tk, ttk = self.tk, self.ttk
        self.form = ttk.Frame(body)
        self.form.grid(row=0, column=0, columnspan=2, sticky="we")
        ttk.Label(body, text="Height along it", font=("TkDefaultFont", 9, "bold")).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.graph = tk.Canvas(body, width=300, height=110, background="#1b1d22", highlightthickness=0)
        self.graph.grid(row=2, column=0, columnspan=2, sticky="w")
        rb = ttk.Frame(body)
        rb.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(rb, text="How each ball rides it", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        ttk.Button(rb, text="Roll each ball", command=self.run_ride).pack(anchor="w")
        self.ride_t = tk.Text(body, width=36, height=8, wrap="word", font=("TkDefaultFont", 9),
                              background="#f6f6f2", relief="flat")
        self.ride_t.grid(row=4, column=0, columnspan=2, sticky="we")
        self.ride_t.tag_configure("ball", font=("TkDefaultFont", 9, "bold"))
        self.ride_t.tag_configure("bad", foreground="#a01818")
        key = self.app.doc.lines[self.line - 1] if self.line else None
        if key in self.rides:
            self._show_ride(self.rides[key])
        else:
            self._ride_text([("Roll each ball to see how rubber, steel and glass ride it (the game's physics).",
                              None)])
        self._fill_form()
        self._draw_graph(self.cur())

    def refresh(self):
        """after an edit of the draft: the form and graph again, and the plan"""
        if self.form is not None and self.form.winfo_exists():
            self._fill_form()
            self._draw_graph(self.cur())
        self.app._redraw()

    def apply(self, sh, label="edit a shape"):
        """SPEC.md 130.58.27: every edit of the shape goes into the DRAFT - drawn dashed, nothing written or
        compiled - until Try it"""
        if self.line is None:
            return
        self.draft = sh
        self.refresh()

    def cur(self):
        return self.draft or self.sh

    def try_draft(self):
        """the draft written to the course through the window's checked edit (its path made axis-legged first);
        refused, the draft stays, the banner above the plan saying why"""
        d = self.draft
        if not d or self.line is None:
            return
        if d["kind"] in PATHS:
            d = dict(d, ways=axis_path(d["ways"]))
        want = code(d)
        line = self.line
        self.draft = None                       # (the edit refills the inspector: no draft while it does)
        self.app._edit(self.app.doc.set_statement, line, want, label="edit a %s" % d["kind"])
        try:
            now = self.app.doc.statement(line).code
        except Exception:
            now = None
        if now == want:
            self.sh = parse(want.split())
            self.pending = (line, want, d)       # (the picture's compile may still refuse it: picture_refused)
            self.app._msg("The %s is changed (line %d); the picture is checking it..." % (d["kind"], line))
        else:
            self.draft = d
            self.app._msg("Not changed: the %s was refused - the red bar says why; the draft is kept, fix it and "
                          "Try it again, or Discard" % d["kind"])
        self.app._fill_inspector()
        self.app._redraw()

    def picture_refused(self, error, text):
        """the picture's compile (the full rules, a few seconds after Try it) refused the course: when it names the
        line a draft was just tried on, and the course is still that text, the edit is undone and the draft is
        back, the banner saying why"""
        pend, self.pending = getattr(self, "pending", None), None
        if not pend:
            return False
        line, want, d = pend
        import re
        m = re.search(r":(\d+):", error or "")
        if not m or int(m.group(1)) != line or self.app.doc.text() != text:
            return False
        try:
            if self.app.doc.statement(line).code != want:
                return False
        except Exception:
            return False
        self.app.doc.undo()
        if self.app.doc.redo_stack:
            self.app.doc.redo_stack.pop()
        self.line, self.draft = line, d
        self.app.select(line)
        self.app._banner("That change was undone: %s" % self.app_explain(error), keep=False)
        self.app._msg("The %s's draft is back: fix it and Try it again, or Discard" % d["kind"])
        return True

    def picture_ok(self):
        self.pending = None

    @staticmethod
    def app_explain(why):
        try:
            import bbedit
            return bbedit.explain(why)
        except Exception:
            return why

    def discard(self):
        self.draft = None
        self.app._fill_inspector()
        self.app._redraw()

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
        sh = self.cur()
        if not sh:
            return
        self.app.ins_title.config(text="%s%s" % (describe(sh), " - DRAFT" if self.draft else ""))
        row = [0]
        bar = tk.Frame(self.form, background="#fff1cf" if self.draft else "#eef3f7", padx=6, pady=4)
        bar.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 6))
        row[0] = 1
        if self.draft:
            tk.Label(bar, text="Draft: not in the course yet.", background="#fff1cf").pack(anchor="w")
            bb = tk.Frame(bar, background="#fff1cf")
            bb.pack(anchor="w")
            ttk.Button(bb, text="Try it", command=self.try_draft).pack(side="left", padx=(0, 4))
            ttk.Button(bb, text="Discard", command=self.discard).pack(side="left")
        else:
            tk.Label(bar, text="Edits make a draft; Try it puts it in the course. Drag points; Ctrl-click adds one, "
                               "right-click removes one.", background="#eef3f7", wraplength=290,
                     justify="left").pack(side="left")

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
            if len(values) > 2:                 # (three choices: their own row, the inspector is narrow)
                row[0] += 1
                fr.grid(row=row[0], column=0, columnspan=2, sticky="w", padx=(12, 0))
            for v in values:
                ttk.Radiobutton(fr, text=str(v), value=v, variable=var, command=cmd).pack(side="left")
            row[0] += 1
        if sh["kind"] == "chute":
            wv, pv, dv = tk.IntVar(value=sh["width"]), tk.StringVar(value=sh["prof"]), tk.IntVar(value=sh["depth"])
            setw = lambda: self.apply(dict(sh, width=wv.get()), "chute width")       # noqa: E731
            choice("Width (cells)", wv, (1, 2, 3), setw)
            choice("Cross-section", pv, ("round", "bank"), lambda: self.apply(dict(sh, prof=pv.get()), "chute profile"))
            field("Depth (px)", dv, 2, 24, 1,
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
        elif sh["kind"] == "tube":
            kv = tk.StringVar(value=sh["sub"])

            def setk():
                k = kv.get()
                if k == sh["sub"]:
                    return
                w = sh["ways"]
                dx, dy = _sg(w[-1][0] - w[-2][0]), _sg(w[-1][1] - w[-2][1])
                new = dict(sh, sub=k)
                if k == "launch" and not sh.get("speed"):
                    new["speed"] = [192 * dx, 192 * dy, 300]
                if k == "drop" and not sh.get("height"):
                    new["height"] = 2.0
                self.apply(new, "tube kind")
            choice("Kind", kv, ("keep", "launch", "drop"), setk)
            ov = tk.StringVar(value=sh.get("out") or "along its last leg")
            ttk.Label(self.form, text="Comes out").grid(row=row[0], column=0, sticky="w", pady=1)
            cb = ttk.Combobox(self.form, values=("along its last leg", "+x", "-x", "+y", "-y"), textvariable=ov,
                              state="readonly", width=16)
            cb.grid(row=row[0], column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda e: self.apply(
                dict(sh, out=None if ov.get().startswith("along") else ov.get()), "tube exit"))
            row[0] += 1
            if sh["sub"] == "drop":
                hv = tk.StringVar(value=_g(sh.get("height") or 2))
                field("Mouth height", hv, 1, 12, 0.5,
                      lambda: self._fvar(hv) is not None and self._fvar(hv) != sh.get("height")
                      and self.apply(dict(sh, height=self._fvar(hv)), "drop height"))
            if sh["sub"] == "launch":
                sp = sh.get("speed") or [0, 0, 0]
                svs = [tk.StringVar(value=str(v)) for v in sp]

                def sets():
                    try:
                        v = [int(float(x.get())) for x in svs]
                    except ValueError:
                        return
                    if v != list(sp):
                        self.apply(dict(sh, speed=v), "launch speed")
                for k_, (lab, lo, hi) in enumerate((("Speed along x", -512, 512), ("Speed along y", -512, 512),
                                                    ("Speed up", 0, 600))):
                    field(lab, svs[k_], lo, hi, 16, sets)
            bv = tk.StringVar(value=_g(sh["body"]) if sh.get("body") is not None else "")
            hs = leg_heights(sh)
            ttk.Label(self.form, text="Pipe height" if not hs or len(set(hs)) == 1 else "Every leg at").grid(
                row=row[0], column=0, sticky="w", pady=1)
            pf = ttk.Frame(self.form)
            pf.grid(row=row[0], column=1, sticky="w")
            sbp = ttk.Spinbox(pf, from_=-8, to=60, increment=0.5, width=6, textvariable=bv)
            sbp.pack(side="left")

            def setb():                         # (every leg at it: the legs' own heights cleared)
                v = self._fvar(bv)
                if v is not None and (v != sh.get("body") or len(set(hs or [v])) > 1):
                    self.apply(dict(sh, body=v, ways=[[x, y, None] for x, y, _z in sh["ways"]]), "pipe height")
            sbp.configure(command=setb)
            sbp.bind("<Return>", lambda e: setb())
            ttk.Button(pf, text="Automatic", command=lambda: self.apply(dict(sh, body=None), "pipe height")).pack(
                side="left", padx=2)
            row[0] += 1
            ttk.Label(self.form, text=("the pipe's top, in units (blank: automatic - one over the higher end, a "
                                       "drop's just high enough for its mouth)" if sh.get("body") is None else
                                       "the pipe's top, in units; each leg can have its own"), wraplength=290,
                      foreground="#555").grid(row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            w_ = sh["ways"]                     # SPEC.md 130.58.39: a height a LEG (the riser joins a change)
            for k in range(len(w_) - 1):
                lv = tk.StringVar(value=_g(hs[k]) if hs else "")
                ttk.Label(self.form, text="  Leg %d (%d, %d to %d, %d)" % (k + 1, w_[k][0], w_[k][1], w_[k + 1][0],
                                                                         w_[k + 1][1])).grid(
                    row=row[0], column=0, sticky="w", pady=1)
                sl = ttk.Spinbox(self.form, from_=-8, to=60, increment=0.5, width=6, textvariable=lv)
                sl.grid(row=row[0], column=1, sticky="w")

                def setl(k=k, lv=lv):
                    v = self._fvar(lv)
                    if v is not None and (hs is None or v != hs[k]):
                        self.apply(set_leg_height(sh, k, v), "leg %d's pipe height" % (k + 1))
                sl.configure(command=setl)
                sl.bind("<Return>", lambda e, f_=setl: f_())
                row[0] += 1
            cv = tk.StringVar(value="ground" if sh.get("column") is None else "depth")
            dv = tk.StringVar(value=_g(sh.get("column") or 1.0))
            ttk.Label(self.form, text="Column reaches").grid(row=row[0], column=0, sticky="w", pady=1)
            cf = ttk.Frame(self.form)
            cf.grid(row=row[0], column=1, sticky="w")

            def setc():
                if cv.get() == "ground":
                    if sh.get("column") is not None:
                        self.apply(dict(sh, column=None), "column")
                    return
                v = self._fvar(dv)
                if v is not None:
                    v = max(0.25, min(3.0, v))
                    if v != sh.get("column"):
                        self.apply(dict(sh, column=v), "column")
            ttk.Radiobutton(cf, text="the ground", value="ground", variable=cv, command=setc).pack(side="left")
            ttk.Radiobutton(cf, text="depth", value="depth", variable=cv, command=setc).pack(side="left")
            sc = ttk.Spinbox(cf, from_=0.25, to=3, increment=0.25, width=5, textvariable=dv,
                             command=lambda: (cv.set("depth"), setc()))
            sc.pack(side="left")
            sc.bind("<Return>", lambda e: (cv.set("depth"), setc()))
            row[0] += 1
            ttk.Label(self.form, text="over the void, the column hangs that many units under the pipe (like "
                                      "`float ... thick`); over a floor it always stands on it - the ball does not "
                                      "pass under a pipe", wraplength=290, foreground="#555").grid(
                row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            ttk.Label(self.form, text="Points: 1 is where the ball goes in, %d where it comes out; drag them on "
                                      "the plan (an end slides along its leg)." % len(sh["ways"]),
                      wraplength=290, foreground="#555").grid(row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            fr = ttk.Frame(self.form)
            fr.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(6, 0))
            ttk.Label(fr, text="Add a leg at the end:").pack(side="left")
            row[0] += 1
            fr = ttk.Frame(self.form)
            fr.grid(row=row[0], column=0, columnspan=2, sticky="w")
            for txt, t_ in (("Turn left", "left"), ("Straight on", "straight"), ("Turn right", "right")):
                ttk.Button(fr, text=txt, command=lambda t_=t_: self.apply(dict(sh, ways=add_leg(sh["ways"], t_, 3)),
                                                                           "add a leg")).pack(side="left")
            row[0] += 1
            ttk.Button(self.form, text="Remove the last leg", command=lambda: self.apply(
                dict(sh, ways=remove_leg(sh["ways"])), "remove a leg")).grid(row=row[0], column=0, sticky="w")
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
            field("Lip height", vs["z"], -8, 60, 0.5, setp("z", 0, 0))
            field("Radius (2 - 4)", vs["radius"], 2, 4, 1, setp("radius", 2, 4))
            field("Depth (px)", vs["depth"], 2, 40, 1, setp("depth", 2, 40))
            field("Hole (0 - 2)", vs["hole"], 0, 3, 1, setp("hole", 0, 3))
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
            field("Ridge length", vs["n"], 1, 12, 1, seth)
            ttk.Checkbutton(self.form, text="Open ends (no caps)", variable=ov, command=seth).grid(
                row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            field("Base height", vs["z"], -8, 60, 0.5, seth)
            field("Height (px)", vs["height"], 2, 11, 1, seth)

    def _way_picked(self, tv):
        s = tv.selection()
        self.wsel = int(s[0]) if s else None
        self.app._redraw()

    def _set_lip(self, zv):
        sh, i = self.cur(), self.wsel
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
    # -- the plan ---------------------------------------------------------------
    def _pt(self, x, y, centre):
        k = 0.5 if centre else 0.0
        return self.app._cpx(x + k, y + k)

    def _handles(self, sh):
        """[(index, x, y, centre)]: the draggable points"""
        if sh["kind"] in PATHS:
            c = sh["width"] != 2
            return [(i, w[0], w[1], c) for i, w in enumerate(sh["ways"])]
        return [(0, sh["x"], sh["y"], False)]

    def draw(self, c):
        """the shape's path, bowl or ridge and its numbered handles, over the plan (the draft dashed orange, the
        path Try it will lay)"""
        sh = self.drag["sh"] if self.drag else self.cur()
        if not sh:
            return
        s = self._scale()
        hs = self._handles(sh)
        if sh["kind"] in PATHS:
            pts = [self._pt(x, y, ctr) for _, x, y, ctr in hs]
            if self.draft or self.drag:
                fin = [self._pt(w[0], w[1], sh["width"] != 2) for w in axis_path(sh["ways"])]
                c.create_line(*[v for p in fin for v in p], fill="#ff9f1c", width=3, dash=(6, 4))
            else:
                c.create_line(*[v for p in pts for v in p], fill="#29e6ff", width=3, capstyle="round",
                              joinstyle="round")
        elif sh["kind"] == "pit":
            cx_, cy_ = self._pt(sh["x"], sh["y"], False)
            r = sh["radius"] * s
            c.create_oval(cx_ - r, cy_ - r, cx_ + r, cy_ + r, outline="#ff9f1c" if self.draft else "#29e6ff", width=2)
            if sh["hole"]:
                q = sh["hole"] * s
                c.create_rectangle(cx_ - q, cy_ - q, cx_ + q, cy_ + q, outline="#ff6b6b", width=2, dash=(3, 2))
        else:
            cx_, cy_ = self._pt(sh["x"], sh["y"], False)
            n = sh["n"] or 0
            ex, ey = (n * s, 0) if sh["along"] == "x" else (0, n * s) if sh["along"] == "y" else (0, 0)
            c.create_line(cx_, cy_, cx_ + ex, cy_ + ey, fill="#ff9f1c" if self.draft else "#29e6ff", width=4,
                          capstyle="round")
        for i, x, y, ctr in hs:
            px, py = self._pt(x, y, ctr)
            on = i == self.wsel and sh["kind"] in PATHS
            c.create_oval(px - 9, py - 9, px + 9, py + 9, fill="#ffd54f" if on else "#29e6ff", outline="#111")
            c.create_text(px, py, text=str(i + 1), fill="#111", font=("TkDefaultFont", 8, "bold"))

    def _draw_graph(self, sh):
        g = self.graph
        g.delete("all")
        Wg, Hg = 300, 110
        if sh["kind"] == "tube" and leg_heights(sh):  # SPEC.md 130.58.39: the pipe's top leg by leg, its column
            ws, hs = sh["ways"], leg_heights(sh)
            dist = [0]
            for p, q in zip(ws, ws[1:]):
                dist.append(dist[-1] + abs(q[0] - p[0]) + abs(q[1] - p[1]))
            col = sh.get("column")
            lo, hi = min(hs) - (col if col is not None else 1.0) - 0.5, max(hs) + 0.5
            L = float(dist[-1] or 1)
            X = lambda d: 30 + d / L * (Wg - 45)                    # noqa: E731
            Y = lambda z: Hg - 18 - (z - lo) / (hi - lo) * (Hg - 30)   # noqa: E731
            top = []
            for k, h in enumerate(hs):
                top += [X(dist[k]), Y(h), X(dist[k + 1]), Y(h)]
            g.create_line(*top, fill="#9fd3ff", width=2)
            if col is not None:
                g.create_line(*[v if j % 2 == 0 else v + (Y(0) - Y(col)) for j, v in enumerate(top)],
                              fill="#7aa7ff", width=2, dash=(4, 2))
            for i, d in enumerate(dist):
                g.create_text(X(d), Hg - 8, text=str(i + 1), fill="#ccc", font=("TkDefaultFont", 7))
            g.create_text(4, Y(hi - 0.5), anchor="w", text="%g" % (hi - 0.5), fill="#ccc", font=("TkDefaultFont", 7))
            g.create_text(Wg - 4, 8, anchor="ne", fill="#ccc", font=("TkDefaultFont", 7),
                          text="pipe top (cyan)%s, units; %g cells" % (
                              ", column's foot over the void (blue)" if col is not None else "; its column reaches "
                              "the ground", L))
            return
        if sh["kind"] == "tube":
            g.create_text(8, 8, anchor="nw", fill="#ccc", width=Wg - 16, text=(
                "In at 1, out at %d. The cells between are its body: the tube lays them as walls itself, its "
                "pipe on top. Both ends on floor; a KEEP rolls out onto the floor beyond %d." % (
                    len(sh["ways"]), len(sh["ways"]))))
            return
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

    def hit(self, e):
        """the handle under the pointer on the plan, or None"""
        sh = self.cur()
        if not sh:
            return None
        x, y = self.app.cv.canvasx(e.x), self.app.cv.canvasy(e.y)
        for i, hx, hy, ctr in self._handles(sh):
            px, py = self._pt(hx, hy, ctr)
            if abs(px - x) <= 11 and abs(py - y) <= 11:
                return i
        return None

    def _scale(self):
        return self.app._cpx(1, 0)[0] - self.app._cpx(0, 0)[0]

    def _cell(self, e, centre):
        import math
        s = self._scale()
        fx = self.app.cv.canvasx(e.x) / s + self.app.origin[0]
        fy = self.app.cv.canvasy(e.y) / s + self.app.origin[1]
        return (int(math.floor(fx)), int(math.floor(fy))) if centre else (int(round(fx)), int(round(fy)))

    def press(self, e, i):
        sh = self.cur()
        self.wsel = i if sh["kind"] in PATHS else None
        self.drag = {"i": i, "sh": sh, "moved": False}
        self.app._redraw()

    def motion(self, e):
        """a point dragged FREELY (SPEC.md 130.58.27): the draft takes any cell; Try it makes the legs lie on axes"""
        d = self.drag
        if not d:
            return
        sh = self.cur()
        ctr = sh["kind"] in PATHS and sh["width"] != 2
        nx, ny = self._cell(e, ctr if sh["kind"] in PATHS else False)
        if sh["kind"] in PATHS:
            w = [list(p) for p in sh["ways"]]
            w[d["i"]][0], w[d["i"]][1] = nx, ny
            new = dict(sh, ways=w)
        else:
            new = dict(sh, x=nx, y=ny)
        if code(new) != code(d["sh"]):
            d["sh"], d["moved"] = new, True
            self.app._draw_plan()

    def release(self, e):
        d, self.drag = self.drag, None
        if d and d["moved"] and code(d["sh"]) != code(self.cur()):
            self.apply(d["sh"], "move a point")
        else:
            self.refresh()

    def add_point(self, e):
        """Ctrl-click: a point added to the draft's path where it is nearest (past an end, a new end)"""
        sh = self.cur()
        if not sh or sh["kind"] not in PATHS:
            return
        cell = self._cell(e, sh["width"] != 2)
        if any(w[:2] == list(cell) for w in sh["ways"]):
            return
        self.apply(dict(sh, ways=insert_point(sh["ways"], cell)), "add a point")

    def remove_point(self, i):
        """a right-clicked point removed from the draft's path (a path keeps its two ends)"""
        sh = self.cur()
        if not sh or sh["kind"] not in PATHS or i is None:
            return
        if len(sh["ways"]) <= 2:
            self.app._msg("A path keeps at least its two ends")
            return
        w = [list(p) for j, p in enumerate(sh["ways"]) if j != i]
        if i == 0 and sh["ways"][0][2] is not None and w[0][2] is None:
            w[0][2] = sh["ways"][0][2]          # (the first point always names the lip)
        self.wsel = None
        self.apply(dict(sh, ways=w), "remove a point")

    # -- how each ball rides it ---------------------------------------------------
    def run_ride(self):
        if self.ride_job:
            self.ride_job.kill()
        if not self.sh or self.app.doc.analysis()["error"]:
            self._ride_text([("The course has to lay out first.", None)])
            return
        if self.draft:
            self._ride_text([("Try the draft first: the ride rolls the course as it stands.", None)])
            return
        key = self.app.doc.lines[self.line - 1]
        p = self.app._write_tmp("ride")
        line = self.line

        def ev(job, e):
            if e["stage"] == "done":
                if e.get("ok"):
                    self.rides[key] = e["rides"]
                    if self.line == line and self.app.doc.lines[line - 1] == key:
                        self._show_ride(e["rides"])
                else:
                    self._ride_text([("Could not roll it: %s" % e.get("error"), "bad")])
            elif e["stage"] not in ("exit", "log"):
                self._ride_text([("%s..." % e.get("what", e["stage"]).capitalize(), None)])
        self.ride_job = self.Job(["ride", p, str(line), "--name", self.app._name()], ev).start()

    def poll(self):
        if self.ride_job:
            self.ride_job.poll()
            if not self.ride_job.running:
                self.ride_job.poll()
                self.ride_job = None

    def _ride_text(self, parts):
        t = self.ride_t
        if t is None or not t.winfo_exists():
            return
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
