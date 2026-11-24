#!/usr/bin/env python3
"""bbedmap - THE COURSE BUILDER'S MAP TAB (SPEC.md 130.58.20): the pathway (`path.bbc`, SPEC.md 130.22)
edited on its own picture - pads, routes and their points, gates, icons, lives counters, pages and the
view - and a course put on the map (its pad, its route, its icon).

The helpers at the top are the tab's model and import no Tk: the window, the jobs (tools/bbedjob.py)
and the row (tests/unit/t_bbedit.py) call them. The tab (`MapTab`) is built by tools/bbedit.py.

A pathway may name courses that are not in the game yet: a comment line

    # builder-course: FILE.bbc

(FILE relative to the pathway's own folder) adds that course to the courses the map's pads may play,
after BZ_COURSES - the compiler ignores the comment, the builder and tools/bbgame.py read it.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbcourse as B  # noqa: E402

EXTRA_RE = re.compile(r"^\s*#\s*builder-course:\s*(\S+)\s*$", re.M)


def is_map(text):
    return bool(re.search(r"^\s*pathway\b", text, re.M))


def extra_courses(text, path):
    """the course files a pathway's `# builder-course:` lines name, as paths"""
    base = os.path.dirname(os.path.abspath(path)) if path else os.getcwd()
    return [os.path.normpath(os.path.join(base, f)) for f in EXTRA_RE.findall(text)]


def course_info(text, path):
    """the pathway's crsinfo: BZ_COURSES's (NAME, title, test) and then the extra courses' -> (crsinfo, the
    paths in that order)"""
    paths = list(B.default_paths()) + [p for p in extra_courses(text, path) if os.path.isfile(p)]
    return B._course_info_t(tuple(paths)), paths


def compile_map(text, path, occluders=False):
    """the pathway compiled as the window and its jobs see it: its picture's block limit lifted, its pads'
    courses BZ_COURSES's and the extra ones"""
    held = B.BLK_MAX
    B.BLK_MAX = 1 << 30
    try:
        crsinfo, _ = course_info(text, path)
        return B.compile_course(text, path or "path.bbc", occluders=occluders, crsinfo=crsinfo)
    finally:
        B.BLK_MAX = held


def proofs(text, path, log=None):
    """the map's PROOFS (SPEC.md 130.22.2: every pad reachable, every route's exit one its course has, a
    secret route a shortcut or a side): every pad's course compiled (play-only, through the cache) ->
    path_proofs' answer"""
    crsinfo, paths = course_info(text, path)
    pc = compile_map(text, path)
    names = {q["crs"] for q in pc.src.ppads}
    courses = []
    held = B.BLK_MAX
    B.BLK_MAX = 1 << 30
    try:
        for p, (nm, _t, _tst) in zip(paths, crsinfo):
            if nm in names:
                if log:
                    log(nm)
                courses.append(B.compile_course(p, occluders=False))
    finally:
        B.BLK_MAX = held
    return B.path_proofs(pc, courses)


# ----------------------------------------------------------------------------
# the statements (no Tk)
# ----------------------------------------------------------------------------

def _pt(tok):
    v = tok.split(",")
    return [int(v[0]), int(v[1]), float(v[2]) if len(v) > 2 else 0.0]


def _g(v):
    return "%g" % v


def parse_map(statements):
    """the pathway's own statements -> {"pads": {N: {...}}, "routes": [...], "icons": {N: {...}}, "lives": [...],
    "view": {...}|None, "pages": {...}|None}; each item carries its "line" """
    m = {"pads": {}, "routes": [], "icons": {}, "lives": [], "view": None, "pages": None}
    for st in statements:
        t, ln = list(st.toks), st.line
        try:
            if st.kind == "pad" and len(t) == 5 and t[1].isdigit():
                m["pads"][int(t[1])] = {"line": ln, "n": int(t[1]), "crs": t[2], "at": (int(t[3]), int(t[4]))}
            elif st.kind == "route":
                r = {"line": ln, "a": int(t[1]), "b": int(t[2]), "exit": int(t[4]), "secret": False, "gate": None,
                     "pts": []}
                i = 5
                while i < len(t) and t[i] != "path":
                    if t[i] == "secret":
                        r["secret"] = True
                        i += 1
                    elif t[i] == "gate":
                        r["gate"] = (int(t[i + 1]), int(t[i + 2]))
                        i += 3
                    else:
                        i += 1
                r["pts"] = [_pt(x) for x in t[i + 1:]]
                m["routes"].append(r)
            elif st.kind == "icon":
                ic = {"line": ln, "n": int(t[1]), "file": t[2], "sx": int(t[3]), "sy": int(t[4]), "fps": None,
                      "title": None, "tdx": None}
                i = 5
                while i + 1 < len(t):
                    if t[i] == "fps":
                        ic["fps"] = int(t[i + 1])
                    elif t[i] == "title":
                        ic["title"] = t[i + 1].strip('"')
                    elif t[i] == "tdx":
                        ic["tdx"] = int(t[i + 1])
                    i += 2
                m["icons"][ic["n"]] = ic
            elif st.kind == "lives":
                m["lives"].append({"line": ln, "at": (int(t[1]), int(t[2]))})
            elif st.kind == "view":
                m["view"] = {"line": ln, "sx": int(t[1]), "sy": int(t[2]), "drop": int(t[4]) if len(t) > 4 else None}
            elif st.kind == "pages":
                m["pages"] = {"line": ln, "n": int(t[1])}
        except (ValueError, IndexError):
            continue
    return m


def pad_code(p):
    return "pad %d %s %d %d" % (p["n"], p["crs"], p["at"][0], p["at"][1])


def route_code(r):
    out = "route %d %d exit %d" % (r["a"], r["b"], r["exit"])
    if r["secret"]:
        out += " secret"
    if r["gate"] and not r["secret"]:
        out += " gate %d %d" % tuple(r["gate"])
    pts = ["%d,%d%s" % (x, y, ("," + _g(h)) if h else "") for x, y, h in r["pts"]]
    return out + "  path " + " ".join(pts)


def icon_code(ic):
    out = "icon %d %s %d %d" % (ic["n"], ic["file"], ic["sx"], ic["sy"])
    if ic.get("fps"):
        out += " fps %d" % ic["fps"]
    if ic.get("title"):
        out += ' title "%s"' % ic["title"]
    if ic.get("tdx"):
        out += " tdx %d" % ic["tdx"]
    return out


def lives_code(lv):
    return "lives %d %d" % lv["at"]


def _sgn(v):
    return (v > 0) - (v < 0)


def legal(p, q):
    """a route's step (SPEC.md 130.22.2): along one axis, or along both by equal amounts"""
    dx, dy = q[0] - p[0], q[1] - p[1]
    return dx == 0 or dy == 0 or abs(dx) == abs(dy)


def bridge(p, q):
    """the corner a step P -> Q that is not legal goes through: along the longer axis first (a ramp there if the
    heights differ), then the diagonal at Q's height. -> [corner] or [] when P -> Q is legal already"""
    if legal(p, q):
        return []
    dx, dy = q[0] - p[0], q[1] - p[1]
    k = min(abs(dx), abs(dy))
    if abs(dx) > abs(dy):
        return [[q[0] - _sgn(dx) * k, p[1], q[2]]]
    return [[p[0], q[1] - _sgn(dy) * k, q[2]]]


def tidy_points(pts):
    """a route's points with every illegal step bridged and every point dropped that sits in the middle of a
    straight run at one height (the same step direction either side)"""
    out = [list(pts[0])]
    for q in pts[1:]:
        out += bridge(out[-1], q)
        out.append(list(q))
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        d1 = (_sgn(b[0] - a[0]), _sgn(b[1] - a[1]))
        d2 = (_sgn(c[0] - b[0]), _sgn(c[1] - b[1]))
        if (d1 == d2 and a[2] == b[2] == c[2]) or b[:2] == a[:2]:
            del out[i]
        else:
            i += 1
    return out


def moved_point(r, i, cell):
    """route R with point I moved to CELL, its steps bridged where they would not be legal"""
    pts = [list(p) for p in r["pts"]]
    pts[i][0], pts[i][1] = cell
    return dict(r, pts=tidy_points(pts))


def new_route(m, a, b, exit_):
    """a route from pad A to pad B, an L of legal steps at height 0"""
    pa, pb = m["pads"][a]["at"], m["pads"][b]["at"]
    return {"a": a, "b": b, "exit": exit_, "secret": False, "gate": None,
            "pts": tidy_points([[pa[0], pa[1], 0.0], [pb[0], pb[1], 0.0]])}


_EXITS = {}


def course_exits(path):
    """the exits a course HAS (its goals' and cups' `exit`, 0 by default; SPEC.md 130.19.4), off a parse alone"""
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return {0}
    if key not in _EXITS:
        try:
            src = B.parse(open(path, encoding="ascii").read(), path)
            ex = {getattr(r, "exit", 0) or 0 for r in src.rooms if r.style == "goal"}
            ex |= {(c.get("exit", 0) if isinstance(c, dict) else getattr(c, "exit", 0)) or 0 for c in src.cups}
        except (B.CourseError, OSError):
            ex = {0}
        _EXITS[key] = ex or {0}
    return _EXITS[key]


def pad_exits(m, n, text, path):
    """pad N's course's exits"""
    crsinfo, paths = course_info(text, path)
    names = [e[0] for e in crsinfo]
    crs = m["pads"][n]["crs"]
    return course_exits(paths[names.index(crs)]) if crs in names else set(range(B.EXIT_MAX + 1))


def free_exit(m, a, exits=None):
    """pad A's first exit no route uses yet - one its course HAS when EXITS is given - or None"""
    used = {r["exit"] for r in m["routes"] if r["a"] == a}
    pool = sorted(exits) if exits is not None else range(B.EXIT_MAX + 1)
    return next((e for e in pool if e not in used), None)


def bba_size(path):
    """an icon file's (width, frame height, frames)"""
    try:
        with open(path, encoding="ascii") as f:
            text = f.read()
    except OSError:
        return 32, 24, 1
    k = re.search(r"^#\s*frames\s+(\d+)", text, re.M)
    rows = [r for r in text.split("\n") if r and not r.startswith("#")]
    n = int(k.group(1)) if k else 1
    return (len(rows[0]) if rows else 32), (len(rows) // max(1, n) if rows else 24), n


def cell_xy(at, h, x0, y0):
    """a cell's top centre in the picture, at height H units"""
    wx, wy = at
    return 16 * (wx - wy) + x0, 8 * (wx + wy) + 8 - 8 * h + y0


def xy_cell(px, py, h, x0, y0):
    """the cell whose top at height H is under picture point (PX, PY)"""
    a = (px - x0) / 16.0
    s = (py - y0 - 8 + 8 * h) / 8.0
    return int(round((s + a) / 2.0)), int(round((s - a) / 2.0))


def windows(m, x0, y0):
    """each page's CGA window in the picture: [(left, top, right, bottom)], page 0 first"""
    v = m["view"]
    if not v:
        return []
    n = m["pages"]["n"] if m["pages"] else 1
    return [(v["sx"] - 160 + x0, v["sy"] - 100 + y0 - 200 * k, v["sx"] + 160 + x0, v["sy"] + 100 + y0 - 200 * k)
            for k in range(n)]


def pad_height(m, n):
    """a pad's floor height: the height its routes give it there"""
    at = m["pads"][n]["at"]
    for r in m["routes"]:
        for p in (r["pts"][0], r["pts"][-1]):
            if tuple(p[:2]) == tuple(at):
                return p[2]
    return 0.0


def place_course(m, crs, cell, from_pad, icon_file, title=None, exits=None):
    """SPEC.md 130.58.20 (the plan's 7.2): COURSE put on the map at CELL - a new pad (the next number), a route
    from pad FROM_PAD on its first free exit, an icon above the pad -> [(None, code)]: the statements to add"""
    n = max(m["pads"]) + 1 if m["pads"] else 0
    ex = free_exit(m, from_pad, exits)
    if ex is None:
        raise ValueError("pad %d's course has no exit left for a new route: each of its exits (%s) already opens one. "
                         "Reach the course from another pad, or give that course another exit (a goal with `exit N`)"
                         % (from_pad, ", ".join(map(str, sorted(exits or ())))))
    m2 = dict(m, pads=dict(m["pads"]))
    m2["pads"][n] = {"n": n, "crs": crs, "at": tuple(cell)}
    h = pad_height(m, from_pad)
    r = new_route(m2, from_pad, n, ex)
    for p in r["pts"]:
        p[2] = h
    w, fh, _ = bba_size(icon_file[1])
    px, py = 16 * (cell[0] - cell[1]), 8 * (cell[0] + cell[1]) + 8 - 8 * h
    ic = {"n": n, "file": icon_file[0], "sx": (px - w // 2) // 8 * 8, "sy": (py - fh - 24) // 8 * 8,
          "title": title}
    return [pad_code(m2["pads"][n]), route_code(r), icon_code(ic)]


# ----------------------------------------------------------------------------
# the tab
# ----------------------------------------------------------------------------

class MapTab(object):
    def __init__(self, app, nb, tk, ttk, photo):
        self.app, self.tk, self.ttk, self.photo_of = app, tk, ttk, photo
        self.m = None
        self.sel = None                 # ("pad", n) | ("route", index) | ("icon", n) | ("lives", index) | ("map",)
        self.drag = None
        self.zoom = 2
        self.place = None               # "put a course on the map": waiting for the click on its cell
        self.photo = None
        f = ttk.Frame(nb)
        nb.insert(1, f, text="Map")
        self.frame = f
        left = ttk.Frame(f, padding=6)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="The pathway", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        self.tv = ttk.Treeview(left, show="tree", height=24, selectmode="browse")
        self.tv.column("#0", width=250)
        self.tv.pack(fill="y", expand=True, pady=4)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._tv_pick())
        ttk.Button(left, text="Put a course on the map...", command=self.put_course).pack(fill="x", pady=1)
        ttk.Button(left, text="New route between two pads...", command=self.new_route_dialog).pack(fill="x", pady=1)
        ttk.Button(left, text="Delete the selected item", command=self.delete).pack(fill="x", pady=1)
        right = ttk.Frame(f, padding=6, width=380)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self.title_l = ttk.Label(right, text="", font=("TkDefaultFont", 12, "bold"), wraplength=360)
        self.title_l.pack(anchor="w")
        self.form = ttk.Frame(right)
        self.form.pack(fill="x", pady=4)
        self.help_l = ttk.Label(right, wraplength=360, foreground="#444", justify="left", text=(
            "Drag a pad, a route's point, a lives counter or an icon on the picture. A route keeps its steps legal "
            "by itself: a step that is neither along one axis nor a true diagonal gets a corner. Double-click a "
            "route to add a point there. Every change is checked against the game's own rules; one it refuses "
            "is undone with the reason."))
        self.help_l.pack(anchor="w", pady=(10, 0))
        self.status_l = ttk.Label(right, wraplength=360, foreground="#0b6b80", justify="left", text="")
        self.status_l.pack(anchor="w", pady=(10, 0))
        cf = ttk.Frame(f)
        cf.pack(side="left", fill="both", expand=True)
        zb = ttk.Frame(cf)
        zb.pack(side="top", fill="x")
        ttk.Label(zb, text="Zoom").pack(side="left", padx=(6, 2))
        for z in (1, 2, 3):
            ttk.Button(zb, text="%dx" % z, width=3, command=lambda z=z: self.set_zoom(z)).pack(side="left")
        self.show_win = tk.BooleanVar(value=True)
        ttk.Checkbutton(zb, text="Page windows", variable=self.show_win, command=self.draw).pack(side="left", padx=8)
        self.cv = tk.Canvas(cf, background="#000", highlightthickness=0)
        xs = ttk.Scrollbar(cf, orient="horizontal", command=self.cv.xview)
        ys = ttk.Scrollbar(cf, orient="vertical", command=self.cv.yview)
        self.cv.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._motion)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.cv.bind("<Double-Button-1>", self._dbl)

    # -- the document ---------------------------------------------------------
    def shown(self):
        return self.frame.winfo_ismapped()

    def meta(self):
        p = self.app.pic
        return p["meta"] if p else None

    def refresh(self):
        doc = self.app.doc
        if not is_map(doc.text()):
            self.m = None
            self.tv.delete(*self.tv.get_children())
            self.title_l.config(text="Not a pathway")
            for w in self.form.winfo_children():
                w.destroy()
            self.cv.delete("all")
            self.cv.create_text(20, 20, anchor="nw", fill="#e6e6e6", width=600, text=(
                "This tab edits the PATHWAY, the map the game's courses sit on: open apps/bonanza/courses/path.bbc "
                "(File > Open). The course open now is a course, not the map."))
            return
        self.m = parse_map(doc.statements())
        self._fill_tree()
        self._fill_form()
        self.draw()

    def _fill_tree(self):
        tv, m = self.tv, self.m
        keep = self.sel
        tv.delete(*tv.get_children())
        tv.insert("", "end", iid="map", text="The map: pages, view, courses", open=True)
        tv.insert("", "end", iid="pads", text="Pads (%d)" % len(m["pads"]), open=True)
        for n in sorted(m["pads"]):
            tv.insert("pads", "end", iid="pad:%d" % n, text="pad %d  %s at %d, %d" % (n, m["pads"][n]["crs"],
                                                                                    *m["pads"][n]["at"]))
        tv.insert("", "end", iid="routes", text="Routes (%d)" % len(m["routes"]), open=True)
        for i, r in enumerate(m["routes"]):
            tv.insert("routes", "end", iid="route:%d" % i, text="%d -> %d by exit %d%s" % (
                r["a"], r["b"], r["exit"], " (secret)" if r["secret"] else ""))
        tv.insert("", "end", iid="icons", text="Icons (%d)" % len(m["icons"]), open=False)
        for n in sorted(m["icons"]):
            tv.insert("icons", "end", iid="icon:%d" % n, text="pad %d: %s" % (n, os.path.basename(m["icons"][n]["file"])))
        tv.insert("", "end", iid="lives", text="Lives counters (%d)" % len(m["lives"]), open=False)
        for i, lv in enumerate(m["lives"]):
            tv.insert("lives", "end", iid="lives:%d" % i, text="at %d, %d" % lv["at"])
        iid = self._iid(keep)
        if iid and tv.exists(iid):
            tv.selection_set(iid)
            tv.see(iid)

    def _iid(self, sel):
        if not sel:
            return None
        return "map" if sel[0] == "map" else "%s:%d" % sel

    def _tv_pick(self):
        s = self.tv.selection()
        if not s or s[0] in ("pads", "routes", "icons", "lives"):
            return
        if s[0] == "map":
            new = ("map",)
        else:
            k, v = s[0].split(":")
            new = (k, int(v))
        if new != self.sel:
            self.sel = new
            self._fill_form()
            self.draw()
            self._scroll_to(new)

    def _item(self, sel=None):
        sel = sel or self.sel
        m = self.m
        if not sel or not m:
            return None
        try:
            return {"pad": lambda: m["pads"][sel[1]], "route": lambda: m["routes"][sel[1]],
                    "icon": lambda: m["icons"][sel[1]], "lives": lambda: m["lives"][sel[1]],
                    "map": lambda: None}[sel[0]]()
        except (KeyError, IndexError):
            return None

    # -- edits ------------------------------------------------------------------
    def edit(self, codes, label, inserts=(), removes=()):
        """{line: code} rewritten, INSERTS ([code]) added after the last of their kind, REMOVES ([line]) taken
        out - one undo step through the window's checked edit; the map compiled at once (0.3 s), and the whole
        step undone with the reason when the game's rules refuse it"""
        doc, app = self.app.doc, self.app
        before = self._refusal(doc.text())

        def go():
            with doc.group(label):
                if codes:
                    doc.set_many(codes, label=label)
                for code in inserts:
                    doc.insert(code)
                for ln in sorted(removes, reverse=True):
                    doc.remove(ln)
            return True
        n0 = len(doc.undo_stack)
        if not app._edit(go):
            return False
        why = self._refusal(doc.text())
        if why and why != before and len(doc.undo_stack) > n0:
            doc.undo()
            if doc.redo_stack:
                doc.redo_stack.pop()
            app._banner("That change was undone: %s" % app_explain(why), keep=False)
            return False
        return True

    def _refusal(self, text):
        try:
            compile_map(text, self.app.doc.path)
            return None
        except B.CourseError as e:
            return str(e)

    def delete(self):
        it, m = self._item(), self.m
        if not it or not self.sel:
            return
        k = self.sel[0]
        if k == "pad":
            n = self.sel[1]
            if n != max(m["pads"]):
                self.app._error("Pads are numbered 0 to %d: only the last (pad %d) can be deleted. Change a pad's course "
                              "to replace it." % (max(m["pads"]), max(m["pads"])))
                return
            rm = [it["line"]] + [r["line"] for r in m["routes"] if n in (r["a"], r["b"])] + \
                 ([m["icons"][n]["line"]] if n in m["icons"] else [])
            ok = self.edit({}, "delete pad %d" % n, removes=rm)
        else:
            ok = self.edit({}, "delete a %s" % k, removes=[it["line"]])
        if ok:
            self.sel = None

    def new_route_dialog(self):
        m = self.m
        if not m:
            return
        tk, ttk = self.tk, self.ttk
        d = tk.Toplevel(self.app.root)
        d.title("New route")
        d.transient(self.app.root)
        pads = ["%d %s" % (n, m["pads"][n]["crs"]) for n in sorted(m["pads"])]
        av, bv = tk.StringVar(value=pads[0] if pads else ""), tk.StringVar(value=pads[-1] if pads else "")
        ttk.Label(d, text="From pad").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        ttk.Combobox(d, values=pads, textvariable=av, state="readonly").grid(row=0, column=1, padx=8)
        ttk.Label(d, text="To pad").grid(row=1, column=0, padx=8, pady=4, sticky="w")
        ttk.Combobox(d, values=pads, textvariable=bv, state="readonly").grid(row=1, column=1, padx=8)

        def ok():
            a, b = int(av.get().split()[0]), int(bv.get().split()[0])
            d.destroy()
            ex = free_exit(m, a, pad_exits(m, a, self.app.doc.text(), self.app.doc.path))
            if a == b or ex is None:
                self.app._error("A route joins two different pads, on an exit the first pad's course has free")
                return
            if self.edit({}, "add a route", inserts=[route_code(new_route(m, a, b, ex))]):
                self.sel = ("route", len(self.m["routes"]) - 1)
                self.refresh()
        ttk.Button(d, text="Add", command=ok).grid(row=2, column=1, sticky="e", padx=8, pady=8)

    def put_course(self):
        """the plan's 7.2: choose a course (one of the game's or a file), then click its cell on the map"""
        m = self.m
        if not m:
            return
        tk, ttk = self.tk, self.ttk
        crsinfo, paths = course_info(self.app.doc.text(), self.app.doc.path)
        on = {p["crs"] for p in m["pads"].values()}
        names = ["%s  %s" % (n, t) for (n, t, tst) in crsinfo if n and not tst]
        d = tk.Toplevel(self.app.root)
        d.title("Put a course on the map")
        d.transient(self.app.root)
        cv = tk.StringVar(value=next((x for x in names if x.split()[0] not in on), names[0] if names else ""))
        ttk.Label(d, text="Course").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        cb = ttk.Combobox(d, values=names, textvariable=cv, width=34, state="readonly")
        cb.grid(row=0, column=1, padx=8)

        def add_file():
            from tkinter import filedialog
            p = filedialog.askopenfilename(parent=d, title="A course file", filetypes=[("Courses", "*.bbc")])
            if not p:
                return
            base = os.path.dirname(os.path.abspath(self.app.doc.path or "."))
            rel = os.path.relpath(p, base).replace(os.sep, "/")
            if self.edit({}, "name a course for the map", inserts=["# builder-course: %s" % rel]):
                ci, _ = course_info(self.app.doc.text(), self.app.doc.path)
                nm = [("%s  %s" % (n, t)) for (n, t, tst) in ci if n and not tst]
                cb.configure(values=nm)
                cv.set(nm[-1])
        ttk.Button(d, text="A course file...", command=add_file).grid(row=0, column=2, padx=4)
        icons = sorted(f for f in os.listdir(os.path.join(B.COURSE_DIR, "icons")) if f.endswith(".bba"))
        iv = tk.StringVar(value="first32x24.bba" if "first32x24.bba" in icons else (icons[0] if icons else ""))
        ttk.Label(d, text="Icon").grid(row=1, column=0, padx=8, pady=4, sticky="w")
        ttk.Combobox(d, values=icons, textvariable=iv, state="readonly").grid(row=1, column=1, padx=8, sticky="w")
        text, dpath = self.app.doc.text(), self.app.doc.path
        frm = [n for n in sorted(m["pads"]) if free_exit(m, n, pad_exits(m, n, text, dpath)) is not None]
        if not frm:
            d.destroy()
            self.app._error("No pad's course has an exit free for a new route: give a course another exit first")
            return
        fv = tk.StringVar(value=("%d %s" % (self.sel[1], m["pads"][self.sel[1]]["crs"])) if self.sel and
                          self.sel[0] == "pad" else ("%d %s" % (frm[-1], m["pads"][frm[-1]]["crs"]) if frm else ""))
        ttk.Label(d, text="Reached from pad").grid(row=2, column=0, padx=8, pady=4, sticky="w")
        ttk.Combobox(d, values=["%d %s" % (n, m["pads"][n]["crs"]) for n in frm], textvariable=fv,
                     state="readonly").grid(row=2, column=1, padx=8, sticky="w")
        ttk.Label(d, text="Then click the cell on the map where its pad goes.", foreground="#444").grid(
            row=3, column=0, columnspan=3, padx=8, sticky="w")

        def ok():
            if not cv.get() or not fv.get():
                return
            self.place = {"crs": cv.get().split()[0], "from": int(fv.get().split()[0]), "icon": iv.get()}
            d.destroy()
            self.status_l.config(text="Click the cell where %s's pad goes (Esc: cancel)." % self.place["crs"])
            self.cv.focus_set()
            self.cv.bind("<Escape>", lambda e: self._cancel_place())
        ttk.Button(d, text="Choose its cell", command=ok).grid(row=4, column=1, sticky="e", padx=8, pady=8)

    def _cancel_place(self):
        self.place = None
        self.status_l.config(text="")

    def _do_place(self, cell):
        p, self.place = self.place, None
        self.status_l.config(text="")
        try:
            codes = place_course(self.m, p["crs"], cell, p["from"],
                                 ("icons/" + p["icon"], os.path.join(B.COURSE_DIR, "icons", p["icon"])),
                                 exits=pad_exits(self.m, p["from"], self.app.doc.text(), self.app.doc.path))
        except ValueError as e:
            self.app._error(str(e))
            return
        n = max(self.m["pads"]) + 1
        if self.edit({}, "put %s on the map" % p["crs"], inserts=codes):
            self.sel = ("pad", n)
            self.app._msg("%s is on the map: pad %d, reached from pad %d. Drag its route's points, or its icon, "
                          "where you want them." % (p["crs"], n, p["from"]))

    # -- the form -------------------------------------------------------------
    def _fill_form(self):
        tk, ttk = self.tk, self.ttk
        for w in self.form.winfo_children():
            w.destroy()
        it, m, sel = self._item(), self.m, self.sel
        row = [0]

        def field(label, var, lo, hi, inc, cmd, width=7):
            ttk.Label(self.form, text=label).grid(row=row[0], column=0, sticky="w", pady=1)
            sb = ttk.Spinbox(self.form, from_=lo, to=hi, increment=inc, width=width, textvariable=var, command=cmd)
            sb.grid(row=row[0], column=1, sticky="w")
            sb.bind("<Return>", lambda e: cmd())
            row[0] += 1

        def iv(v):
            try:
                return int(float(v.get()))
            except (ValueError, tk.TclError):
                return None
        if not m:
            return
        if not sel or sel[0] == "map":
            self.title_l.config(text="The map")
            pv = tk.StringVar(value=str(m["pages"]["n"] if m["pages"] else 1))
            v = m["view"] or {"sx": 0, "sy": 0, "line": None}
            sxv, syv = tk.StringVar(value=str(v["sx"])), tk.StringVar(value=str(v["sy"]))

            def setp():
                n = iv(pv)
                if n and m["pages"] and n != m["pages"]["n"]:
                    self.edit({m["pages"]["line"]: "pages %d" % n}, "pages")
                elif n and not m["pages"] and n > 1:
                    self.edit({}, "pages", inserts=["pages %d" % n])

            def setv():
                sx, sy = iv(sxv), iv(syv)
                if sx is not None and sy is not None and v["line"]:
                    self.edit({v["line"]: "view %d %d%s" % (sx, sy, (" drop %d" % v["drop"]) if v.get("drop") else "")},
                              "the view")
            field("Pages (1 - 8)", pv, 1, 8, 1, setp)
            field("Page 0's window, across", sxv, -2000, 2000, 8, setv)
            field("Page 0's window, down", syv, -2000, 4000, 8, setv)
            ex = extra_courses(self.app.doc.text(), self.app.doc.path)
            ttk.Label(self.form, text="Courses not in the game yet (`# builder-course:`):", wraplength=350).grid(
                row=row[0], column=0, columnspan=2, sticky="w", pady=(10, 0))
            row[0] += 1
            ttk.Label(self.form, text="\n".join(os.path.basename(p) for p in ex) or "none", foreground="#444").grid(
                row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            ttk.Button(self.form, text="Check the whole map\n(every pad reachable, every exit real)",
                       command=self.app.run_check).grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(10, 0))
            return
        k = sel[0]
        if k == "pad" and it:
            self.title_l.config(text="Pad %d: %s" % (it["n"], it["crs"]))
            crsinfo, _ = course_info(self.app.doc.text(), self.app.doc.path)
            names = [n for (n, t, tst) in crsinfo if n and not tst]
            cv = tk.StringVar(value=it["crs"])
            ttk.Label(self.form, text="Plays").grid(row=row[0], column=0, sticky="w")
            cb = ttk.Combobox(self.form, values=names, textvariable=cv, state="readonly", width=10)
            cb.grid(row=row[0], column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda e: self.edit({it["line"]: pad_code(dict(it, crs=cv.get()))},
                                                                "pad %d's course" % it["n"]))
            row[0] += 1
            ttk.Label(self.form, text="at x %d, y %d (drag it on the map)%s" % (
                it["at"][0], it["at"][1], "; where a new game rests" if it["n"] == 0 else ""),
                foreground="#444", wraplength=350).grid(row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            outs = ["exit %d -> pad %d%s" % (r["exit"], r["b"], " (secret)" if r["secret"] else "")
                    for r in m["routes"] if r["a"] == it["n"]]
            ttk.Label(self.form, text="Its course's exits open: " + ("; ".join(outs) or "nothing yet"),
                      wraplength=350).grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(6, 0))
        elif k == "route" and it:
            self.title_l.config(text="Route %d -> %d" % (it["a"], it["b"]))
            ev = tk.StringVar(value=str(it["exit"]))
            sv = tk.BooleanVar(value=it["secret"])
            field("Opened by pad %d's exit" % it["a"], ev, 0, B.EXIT_MAX, 1,
                  lambda: iv(ev) is not None and iv(ev) != it["exit"]
                  and self.edit({it["line"]: route_code(dict(it, exit=iv(ev)))}, "route exit"))
            ttk.Checkbutton(self.form, text="Secret (drawn only once taken; no gate)", variable=sv, command=lambda:
                            self.edit({it["line"]: route_code(dict(it, secret=sv.get(),
                                                                   gate=None if sv.get() else it["gate"]))},
                                      "secret")).grid(row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            ttk.Label(self.form, text="Gate: %s" % (("at %d, %d" % tuple(it["gate"])) if it["gate"] else
                                                    "the first cell with room (automatic)"),
                      foreground="#444").grid(row=row[0], column=0, columnspan=2, sticky="w")
            row[0] += 1
            if it["gate"]:
                ttk.Button(self.form, text="Gate back to automatic", command=lambda: self.edit(
                    {it["line"]: route_code(dict(it, gate=None))}, "gate")).grid(row=row[0], column=0, sticky="w")
                row[0] += 1
            ttk.Label(self.form, text="Points (x, y, height): drag them on the map; double-click the route to "
                                      "add one", wraplength=350).grid(row=row[0], column=0, columnspan=2, sticky="w",
                                                                      pady=(6, 0))
            row[0] += 1
            tv = ttk.Treeview(self.form, columns=("x", "y", "h"), show="headings", height=min(8, len(it["pts"])))
            for c_ in ("x", "y", "h"):
                tv.heading(c_, text={"h": "height"}.get(c_, c_))
                tv.column(c_, width=70, anchor="center")
            for i, (x, y, h) in enumerate(it["pts"]):
                tv.insert("", "end", iid=str(i), values=(x, y, _g(h)))
            tv.grid(row=row[0], column=0, columnspan=2, sticky="we")
            row[0] += 1
            hv = tk.StringVar(value="")
            fr = ttk.Frame(self.form)
            fr.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=2)
            ttk.Label(fr, text="Selected point's height").pack(side="left")
            ttk.Spinbox(fr, from_=-4, to=30, increment=0.5, width=5, textvariable=hv).pack(side="left", padx=4)

            def seth():
                s = tv.selection()
                try:
                    h = round(float(hv.get()) * 2) / 2.0
                except ValueError:
                    return
                if not s:
                    return
                pts = [list(p) for p in it["pts"]]
                pts[int(s[0])][2] = h
                self.edit({it["line"]: route_code(dict(it, pts=pts))}, "a point's height")

            def delp():
                s = tv.selection()
                if not s or int(s[0]) in (0, len(it["pts"]) - 1):
                    self.app._msg("Select a point between the two pads (a route's ends are its pads)")
                    return
                pts = [list(p) for j, p in enumerate(it["pts"]) if j != int(s[0])]
                self.edit({it["line"]: route_code(dict(it, pts=tidy_points(pts)))}, "remove a point")
            ttk.Button(fr, text="Set", width=5, command=seth).pack(side="left")
            row[0] += 1
            fr = ttk.Frame(self.form)           # (its own line: beside Set it ran off the form, SPEC.md 130.58.54)
            fr.grid(row=row[0], column=0, columnspan=2, sticky="w", pady=(0, 2))
            ttk.Button(fr, text="Remove point", command=delp).pack(side="left")
            tv.bind("<<TreeviewSelect>>", lambda e: tv.selection() and hv.set(tv.item(tv.selection()[0])["values"][2]))
            row[0] += 1
            ttk.Label(self.form, text="Heights: a step along one axis between two heights is a ramp; a diagonal "
                                      "step must be level.", foreground="#555", wraplength=350).grid(
                row=row[0], column=0, columnspan=2, sticky="w")
        elif k == "icon" and it:
            self.title_l.config(text="Pad %d's icon" % it["n"])
            icons = sorted("icons/" + f for f in os.listdir(os.path.join(B.COURSE_DIR, "icons")) if f.endswith(".bba"))
            fv = tk.StringVar(value=it["file"])
            ttk.Label(self.form, text="Picture").grid(row=row[0], column=0, sticky="w")
            cb = ttk.Combobox(self.form, values=icons, textvariable=fv, state="readonly", width=20)
            cb.grid(row=row[0], column=1, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda e: self.edit({it["line"]: icon_code(dict(it, file=fv.get()))},
                                                                "icon picture"))
            row[0] += 1
            tvv = tk.StringVar(value=it.get("title") or "")
            ttk.Label(self.form, text="Title (blank: the course's; | breaks a line)", wraplength=120).grid(
                row=row[0], column=0, sticky="w")
            e = ttk.Entry(self.form, textvariable=tvv, width=22)
            e.grid(row=row[0], column=1, sticky="w")
            e.bind("<Return>", lambda ev: self.edit({it["line"]: icon_code(dict(it, title=tvv.get().strip() or None))},
                                                    "icon title"))
            row[0] += 1
            dv = tk.StringVar(value=str(it.get("tdx") or 0))
            field("Title moved across (px)", dv, -64, 64, 1, lambda: iv(dv) is not None and self.edit(
                {it["line"]: icon_code(dict(it, tdx=iv(dv) or None))}, "title across"))
            ttk.Label(self.form, text="at %d, %d in the picture's own coordinates (drag it: it snaps to 8 px)"
                      % (it["sx"], it["sy"]), foreground="#444", wraplength=350).grid(
                row=row[0], column=0, columnspan=2, sticky="w")
        elif k == "lives" and it:
            self.title_l.config(text="Lives counter")
            ttk.Label(self.form, text="at %d, %d: drag it. One on every page, its digit inside that page's window."
                      % it["at"], wraplength=350).grid(row=0, column=0, sticky="w")
        else:
            self.title_l.config(text="")

    # -- the picture ----------------------------------------------------------
    def set_zoom(self, z):
        self.zoom = z
        self.draw()

    def _xy(self, px, py):
        z = self.zoom
        return px * z, py * z

    def draw(self):
        c = self.cv
        if not self.m:
            return
        c.delete("all")
        meta = self.meta()
        if not meta or not self.app.pic:
            c.create_text(20, 20, anchor="nw", fill="#e6e6e6", text="Drawing the map's picture...")
            return
        from PIL import Image
        img = self.app.pic["cga"]
        z = self.zoom
        disp = img.resize((img.width * z, img.height * z), Image.NEAREST)
        self.photo = self.photo_of(self.tk, disp)
        c.configure(scrollregion=(0, 0, disp.width, disp.height))
        c.create_image(0, 0, image=self.photo, anchor="nw")
        x0, y0, m = meta["x0"], meta["y0"], self.m
        if self.app.pic.get("text") != self.app.doc.text():
            c.create_text(c.canvasx(8), c.canvasy(8), anchor="nw", fill="#ffd54f", text="(the picture is catching up...)")
        if self.show_win.get():
            for k, (l_, t_, r_, b_) in enumerate(windows(m, x0, y0)):
                c.create_rectangle(*self._xy(l_, t_), *self._xy(r_, b_), outline="#ffd54f", dash=(6, 4))
                c.create_text(*self._xy(l_ + 4, t_ + 3), anchor="nw", fill="#ffd54f", text="page %d" % k)
        for i, r in enumerate(m["routes"]):
            on = self.sel == ("route", i)
            pts = [self._xy(*cell_xy(p[:2], p[2], x0, y0)) for p in r["pts"]]
            if self.drag and self.drag.get("route") == i:
                pts = [self._xy(*cell_xy(p[:2], p[2], x0, y0)) for p in self.drag["r"]["pts"]]
            c.create_line(*[v for p in pts for v in p], fill="#ffd54f" if on else "#ff9f1c", width=3 if on else 2,
                          dash=(5, 3) if r["secret"] else None, tags=("route:%d" % i,))
            for j, (px, py) in enumerate(pts[1:-1], 1):
                c.create_rectangle(px - 5, py - 5, px + 5, py + 5, fill="#ffd54f" if on else "#ff9f1c",
                                   outline="#000")
            if r["gate"]:
                gx, gy = self._xy(*cell_xy(r["gate"], 0, x0, y0))
                c.create_text(gx, gy, text="G", fill="#ff3df5", font=("TkDefaultFont", 10, "bold"))
        for n, p in m["pads"].items():
            at = self.drag["at"] if self.drag and self.drag.get("pad") == n else p["at"]
            px, py = self._xy(*cell_xy(at, pad_height(m, n), x0, y0))
            on = self.sel == ("pad", n)
            c.create_oval(px - 11, py - 11, px + 11, py + 11, outline="#ffd54f" if on else "#7ee081", width=3)
            c.create_text(px, py, text=str(n), fill="#fff", font=("TkDefaultFont", 10, "bold"))
            c.create_text(px, py + 18, text=p["crs"], fill="#7ee081", font=("TkDefaultFont", 8, "bold"))
        for i, lv in enumerate(m["lives"]):
            at = self.drag["at"] if self.drag and self.drag.get("lives") == i else lv["at"]
            px, py = self._xy(*cell_xy(at, 0, x0, y0))
            on = self.sel == ("lives", i)
            c.create_rectangle(px - 10, py - 8, px + 10, py + 8, outline="#ffd54f" if on else "#ff8a65", width=2)
            c.create_text(px, py, text="L", fill="#ff8a65", font=("TkDefaultFont", 9, "bold"))
        for n, ic in m["icons"].items():
            w, h, _ = bba_size(os.path.join(B.COURSE_DIR, ic["file"]))
            sx, sy = (self.drag["sxy"] if self.drag and self.drag.get("icon") == n else (ic["sx"], ic["sy"]))
            on = self.sel == ("icon", n)
            c.create_rectangle(*self._xy(sx + x0, sy + y0), *self._xy(sx + x0 + w, sy + y0 + h),
                               outline="#ffd54f" if on else "#b39ddb", width=2 if on else 1, dash=None if on else (2, 2))

    def _scroll_to(self, sel):
        meta = self.meta()
        it = self._item(sel)
        if not meta or not it:
            return
        x0, y0 = meta["x0"], meta["y0"]
        if sel[0] == "pad":
            px, py = cell_xy(it["at"], 0, x0, y0)
        elif sel[0] == "route":
            px, py = cell_xy(it["pts"][len(it["pts"]) // 2][:2], 0, x0, y0)
        elif sel[0] == "icon":
            px, py = it["sx"] + x0, it["sy"] + y0
        elif sel[0] == "lives":
            px, py = cell_xy(it["at"], 0, x0, y0)
        else:
            return
        sr = [float(v) for v in str(self.cv.cget("scrollregion")).split()] or [0, 0, 1, 1]
        if len(sr) < 4 or sr[2] <= 0:
            return
        W, H = self.cv.winfo_width(), self.cv.winfo_height()
        self.cv.xview_moveto(max(0.0, (px * self.zoom - W / 2.0) / sr[2]))
        self.cv.yview_moveto(max(0.0, (py * self.zoom - H / 2.0) / sr[3]))

    # -- the mouse --------------------------------------------------------------
    def _pic(self, e):
        z = self.zoom
        return self.cv.canvasx(e.x) / z, self.cv.canvasy(e.y) / z

    def _hit(self, e):
        """what is under the pointer: a pad, a route's inner point, a lives counter, an icon, a route's line"""
        meta, m = self.meta(), self.m
        if not meta or not m:
            return None
        x0, y0 = meta["x0"], meta["y0"]
        px, py = self._pic(e)
        r_ = 12.0 / self.zoom
        for n, p in m["pads"].items():
            cx, cy = cell_xy(p["at"], pad_height(m, n), x0, y0)
            if abs(cx - px) <= r_ and abs(cy - py) <= r_:
                return ("pad", n)
        for i, r in enumerate(m["routes"]):
            for j, p in enumerate(r["pts"][1:-1], 1):
                cx, cy = cell_xy(p[:2], p[2], x0, y0)
                if abs(cx - px) <= r_ * .7 and abs(cy - py) <= r_ * .7:
                    return ("point", i, j)
        for i, lv in enumerate(m["lives"]):
            cx, cy = cell_xy(lv["at"], 0, x0, y0)
            if abs(cx - px) <= r_ and abs(cy - py) <= r_:
                return ("lives", i)
        for n, ic in m["icons"].items():
            w, h, _ = bba_size(os.path.join(B.COURSE_DIR, ic["file"]))
            if ic["sx"] + x0 <= px <= ic["sx"] + x0 + w and ic["sy"] + y0 <= py <= ic["sy"] + y0 + h:
                return ("icon", n)
        for i, r in enumerate(m["routes"]):
            for p, q in zip(r["pts"], r["pts"][1:]):
                ax, ay = cell_xy(p[:2], p[2], x0, y0)
                bx, by = cell_xy(q[:2], q[2], x0, y0)
                L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1
                t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / L2))
                if ((ax + t * (bx - ax) - px) ** 2 + (ay + t * (by - ay) - py) ** 2) ** .5 <= r_ * .6:
                    return ("route", i)
        return None

    def _press(self, e):
        self.cv.focus_set()
        meta = self.meta()
        if self.place and meta:
            px, py = self._pic(e)
            self._do_place(xy_cell(px, py, 0, meta["x0"], meta["y0"]))
            return
        h = self._hit(e)
        if not h:
            return
        if h[0] == "point":
            self.sel = ("route", h[1])
            r = self.m["routes"][h[1]]
            self.drag = {"route": h[1], "j": h[2], "r": r, "moved": False}
        else:
            self.sel = h
            if h[0] == "pad":
                self.drag = {"pad": h[1], "at": self.m["pads"][h[1]]["at"], "moved": False}
            elif h[0] == "lives":
                self.drag = {"lives": h[1], "at": self.m["lives"][h[1]]["at"], "moved": False}
            elif h[0] == "icon":
                ic = self.m["icons"][h[1]]
                px, py = self._pic(e)
                self.drag = {"icon": h[1], "sxy": (ic["sx"], ic["sy"]), "off": (px - ic["sx"], py - ic["sy"]),
                             "moved": False}
        self._fill_tree()
        self._fill_form()
        self.draw()

    def _motion(self, e):
        d, meta, m = self.drag, self.meta(), self.m
        if not d or not meta:
            return
        x0, y0 = meta["x0"], meta["y0"]
        px, py = self._pic(e)
        if "route" in d:
            r = m["routes"][d["route"]]
            cell = xy_cell(px, py, r["pts"][d["j"]][2], x0, y0)
            nr = moved_point(r, d["j"], cell)
            if nr["pts"] != d["r"]["pts"]:
                d["r"], d["moved"] = nr, True
        elif "pad" in d:
            cell = xy_cell(px, py, pad_height(m, d["pad"]), x0, y0)
            if cell != tuple(d["at"]):
                d["at"], d["moved"] = cell, True
        elif "lives" in d:
            cell = xy_cell(px, py, 0, x0, y0)
            if cell != tuple(d["at"]):
                d["at"], d["moved"] = cell, True
        elif "icon" in d:
            sx = int(round((px - d["off"][0]) / 8.0)) * 8
            sy = int(round((py - d["off"][1]) / 8.0)) * 8
            if (sx, sy) != d["sxy"]:
                d["sxy"], d["moved"] = (sx, sy), True
        self.draw()

    def _release(self, e):
        d, self.drag = self.drag, None
        m = self.m
        if not d or not d.get("moved"):
            self.draw()
            return
        if "route" in d:
            r = m["routes"][d["route"]]
            self.edit({r["line"]: route_code(d["r"])}, "move a route's point")
        elif "pad" in d:
            n, at = d["pad"], tuple(d["at"])
            p = m["pads"][n]
            codes = {p["line"]: pad_code(dict(p, at=at))}
            for r in m["routes"]:       # (its routes follow it, their steps bridged)
                if n in (r["a"], r["b"]):
                    pts = [list(q) for q in r["pts"]]
                    if r["a"] == n:
                        pts[0][:2] = at
                    if r["b"] == n:
                        pts[-1][:2] = at
                    codes[r["line"]] = route_code(dict(r, pts=tidy_points(pts)))
            self.edit(codes, "move pad %d" % n)
        elif "lives" in d:
            lv = m["lives"][d["lives"]]
            self.edit({lv["line"]: lives_code(dict(lv, at=tuple(d["at"])))}, "move a lives counter")
        elif "icon" in d:
            ic = m["icons"][d["icon"]]
            self.edit({ic["line"]: icon_code(dict(ic, sx=d["sxy"][0], sy=d["sxy"][1]))}, "move an icon")

    def _dbl(self, e):
        """a double-click on a route's line adds a point there (its cell, the height of the step's start)"""
        h, meta = self._hit(e), self.meta()
        if not h or h[0] != "route" or not meta:
            return
        r = self.m["routes"][h[1]]
        px, py = self._pic(e)
        x0, y0 = meta["x0"], meta["y0"]
        best = None
        for j, (p, q) in enumerate(zip(r["pts"], r["pts"][1:])):
            ax, ay = cell_xy(p[:2], p[2], x0, y0)
            bx, by = cell_xy(q[:2], q[2], x0, y0)
            dd = min(((ax + t / 10.0 * (bx - ax) - px) ** 2 + (ay + t / 10.0 * (by - ay) - py) ** 2) for t in range(11))
            if best is None or dd < best[0]:
                best = (dd, j)
        j = best[1]
        cell = xy_cell(px, py, r["pts"][j][2], x0, y0)
        pts = [list(p) for p in r["pts"]]
        pts.insert(j + 1, [cell[0], cell[1], pts[j][2]])
        self.edit({r["line"]: route_code(dict(r, pts=pts))}, "add a point")


def app_explain(why):
    try:
        import bbedit
        return bbedit.explain(why)
    except Exception:
        return why
