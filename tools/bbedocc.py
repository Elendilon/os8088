#!/usr/bin/env python3
"""bbedocc - THE COURSE BUILDER'S OCCLUDER VIEW (SPEC.md 130.58.32): the Iso view's *Occluders* and *Shade*
overlays over the picture job's occ.json (tools/bbedjob.py `picture ... --occ`).

- **Occluders**: the records the PART ships (130.58.44: after AV, 130.29, and the merge) or, with *as cut*,
  every record the occluder RULE cuts (the records the cells' OCC and OCCG flags are counted on, 130.11.4.3), drawn
  over the picture, tinted by the cell that drew it; the cells a ball CAN be hidden in (OCC /
  OCCG) dithered faintly, `noocclude` cells hatched blue. Hovering names a record's owner cell (and its guard rail),
  the cells whose ball it hides and the cells it flags; a click selects it and the inspector offers *Don't hide the
  ball here (noocclude)* for the cells it hides, written through the window's checked edit; a click on a
  noocclude cell offers to take it out again.
- **Shade**: for a windmill whose doorway is "in the shade" (130.12.4.6), its IN 3 x 3 outlined, the flagged
  cells marked, the box a ball anywhere in them covers, and the records responsible, with one plain sentence.

Made by tools/bbedit.py with the window (`OccView(app, row)`); the window hands it its picture, its canvas and
its `_edit`. Nothing here runs a compile: the picture job does, and only while an overlay is on.
"""

import json
import os
import sys


def _tint(o):
    """a bright colour for owner cell O (256 wx + wy): its hue from the cell, so neighbours differ"""
    h = ((o >> 8) * 7 + (o & 255) * 13) % 12
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h / 12.0, 0.85, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


class OccView(object):
    """the two overlays and their row of the Iso view's options"""

    def __init__(self, app, row):
        self.app = app
        tk, ttk = app.tk, app.ttk
        self.show = tk.BooleanVar(value=False)
        self.shade = tk.BooleanVar(value=False)
        self.data = None                # occ.json, as loaded with the picture it was cut for
        self.sel = None                 # ("rec", id) - an id of the list shown (recs()) - or ("noocc", cell); SEVERAL
        #                                 (130.58.47): ("recs", frozenset of ids) or ("noocs", frozenset of cells)
        self.drag = None                # a press on the overlay: {x, y (picture px), ctrl, moved, e} (130.58.47)
        self.passing = False            # (a click that hit nothing, handed back to the window's own press)
        self.hot = None                 # the record under the pointer
        self.which = tk.StringVar(value="shipped")     # 130.58.44: "shipped" (c.records) or "cut" (the rule's)
        self.cache = None               # (key, the composited overlay image)
        ttk.Label(row, text="  |").pack(side="left")
        ttk.Checkbutton(row, text="Occluders", variable=self.show, command=self.toggled).pack(side="left")
        for v, t in (("shipped", "as shipped"), ("cut", "as cut")):
            ttk.Radiobutton(row, text=t, value=v, variable=self.which, command=self.which_changed).pack(side="left")
        self.shade_b = ttk.Checkbutton(row, text="Shade: why", variable=self.shade, command=self.toggled)
        self.shade_b.pack(side="left", padx=4)
        self.row = row
        self.label = ttk.Label(row, text="", foreground="#6b3a0b")    # (its own line under the row while it
        #                                                                says something: _say)

    # -- the job --------------------------------------------------------------
    def wanted(self):
        """the picture job cuts the occluders only while an overlay shows (they cost the full rules' compile)"""
        return bool(self.show.get() or self.shade.get())

    def toggled(self):
        a = self.app
        if self.wanted() and (a.pic_job and a.pic_job.running or a.pic and a.pic["meta"].get("occ") is None):
            a.run_picture()
            self._say("Cutting the occluders (the full rules: tens of seconds on a big course)...")
        self.hot = None                 # (the list shown may be another now: 130.58.44)
        if self.sel and self.sel[0] in ("rec", "recs"):
            self.sel = None
        if not self.wanted():
            self.sel = None
            self._say("")
        if self.shade.get() and self.app.view.get() != "iso":
            self.app.view.set("iso")
        self.cache = None
        a._redraw()
        if self.shade.get():
            self._shade_say()

    def which_changed(self):
        """130.58.44: as shipped / as cut - the other list drawn, hovered and selected"""
        self.sel, self.hot, self.cache = None, None, None
        self.app._fill_inspector()
        self.app._redraw()
        self._counts()

    def shipped(self):
        """-> True when the list shown is the part's (an occ.json from before 130.58.44 has only the rule's)"""
        return bool(self.show.get() and self.which.get() == "shipped" and self.data is not None
                    and "shipped" in self.data)

    def recs(self):
        """the records shown, hovered and selected: the part's or the rule's (Shade alone: the rule's, whose
        records flag the doorway)"""
        return self.data["shipped"] if self.shipped() else self.data["records"]

    def _counts(self):
        """the status: both counts, shipped and as cut (130.58.44)"""
        if self.data is None or not self.wanted() or not self.show.get():
            return
        n, om = len(self.data["records"]), self.app.pic["meta"].get("occ") or {}
        if "shipped" in self.data:
            m = len(self.data["shipped"])
            what = "%s records shipped (%s %s)" % (format(m, ","), format(n, ","), "before AV" if self.data["av"]
                                                   else "as cut: AV is off")
        else:
            what = "%s occluder records as cut" % format(n, ",")
        ref = self.data.get("refused")
        self._say("%s%s%s; cut in %.1f s; %d cells where a ball can be hidden" % (
            ("REFUSED, shown as cut before the refusal - noocclude cells no ball reaches to come under it: %s\n"
             % _bare(ref)) if ref else "",
            what, " - showing the rule's" if self.which.get() == "cut" else "", om.get("secs", 0), len(self.flags)))

    def loaded(self, out, meta):
        """the picture job's OUTDIR read: its occ.json, when it cut one (meta's `occ`); a picture drawn before an
        overlay was turned on is drawn again with it"""
        self.data, self.cache, self.hot = None, None, None
        om = meta.get("occ")
        if om and (not om.get("error") or om.get("partial")):     # (130.58.46: a bound's refusal, the cut shown)
            try:
                with open(os.path.join(out, "occ.json")) as f:
                    self.data = json.load(f)
            except (OSError, ValueError) as e:
                om["error"] = "occ.json could not be read: %s" % e
        if self.data is not None:
            W = meta["width"]
            self.ats = {}               # per list: pixel index -> [record ids], the front-most (highest s) first
            for k in ("records", "shipped"):
                at = self.ats[k] = {}
                for r in sorted(self.data.get(k, ()), key=lambda r: -r["s"]):
                    for y, x0, x1 in r["runs"]:
                        for x in range(x0, x1 + 1):
                            at.setdefault(y * W + x, []).append(r["id"])
            self.flags = {(x, y): f for x, y, f in self.data["cells"]}
            self.noocc = {tuple(c) for c in self.data.get("noocc", ())}
            if self.sel and self.sel[0] == "rec" and self.sel[1] >= len(self.recs()):
                self.sel = None
            if self.sel and self.sel[0] == "recs":
                self._set_sel("recs", {k for k in self.sel[1] if k < len(self.recs())})
            if self.sel and self.sel[0] == "noocs":
                self._set_sel("noocs", set(self.sel[1]) & self.noocc)
        if self.wanted() and om is None and not self.app.pic_after:
            self.app.root.after(10, self.app.run_picture)
        if self.wanted():
            if om and om.get("error") and self.data is None:
                self._say("No occluders: the full rules refuse the course - %s" % om["error"][:200])
            elif self.data is not None:
                self._counts()
                if self.shade.get():
                    self._shade_say()

    def _say(self, text):
        """the overlay's status, on a line of its own under the options row (the counts do not fit beside them)"""
        self.label.config(text=text)
        if text and not self.label.winfo_manager():
            self.label.pack(side="bottom", anchor="w", padx=8, before=self.row.winfo_children()[0])
        elif not text:
            self.label.pack_forget()

    def _shade_say(self):
        if self.data is None:
            return
        sh = self.data.get("shade") or []
        if not sh:
            self._say("No windmill doorway is in the shade.")
            return
        self._say("in the shade: cell%s %s (the sentence is on the picture)" % (
            "s" if sum(len(s["flagged"]) for s in sh) > 1 else "",
            "; ".join("%d, %d" % (f[0], f[1]) for s in sh for f in s["flagged"])))
        self.app._msg(" ".join(s["why"] for s in sh))

    def problem_picked(self, text):
        """a shade warning clicked in the problems list: the Shade view on, in Iso"""
        if text and "doorway is in the shade" in text:
            self.shade.set(True)
            self.toggled()

    # -- drawing --------------------------------------------------------------
    def _ready(self):
        a = self.app
        return self.data is not None and a.pic and a.pic["meta"].get("occ") and self.wanted()

    def composite(self, img, herc):
        """the picture with the records tinted over it (Occluders), the flagged cells faintly dithered and the
        noocclude cells hatched; the doorway's 3 x 3 for Shade - one image, kept until the picture changes"""
        if not self._ready():
            return img
        from PIL import Image
        key = (id(self.app.pic), herc, self.show.get(), self.shade.get(), self.shipped())
        if self.cache and self.cache[0] == key:
            return self.cache[1]
        meta = self.app.pic["meta"]
        W, H = meta["width"], meta["lines"]
        ow = self.app.pic["owners"]
        over = Image.new("RGB", (W, H))
        mask = bytearray(W * H)
        px = over.load()
        if self.show.get():
            for i in range(W * H):      # the cells a ball can be hidden in: a faint dither; noocclude: hatched
                o = ow[i]
                if o < 0:
                    continue
                x, y = i % W, i // W
                cl = (o >> 8, o & 255)
                if cl in self.noocc and (x + y) % 4 == 0:
                    px[x, y] = (60, 140, 255)
                    mask[i] = 200
                elif cl in self.flags and (x + 2 * y) % 6 == 0:
                    px[x, y] = (255, 255, 255) if self.flags[cl] & 4 else (200, 200, 200)
                    mask[i] = 110
            for r in self.recs():
                own = r["own"][0] if r["own"] else None
                ink = _tint(256 * own[0] + own[1]) if own else (255, 255, 255)
                for y, x0, x1 in r["runs"]:
                    for x in range(x0, x1 + 1):
                        if (x + y) & 1:     # (a checker: the picture shows through the other half)
                            px[x, y] = ink
                            mask[y * W + x] = 230
        if self.shade.get():
            for s in self.data.get("shade") or []:
                box = {tuple(c) for c in s["box"]}
                hit = {(c[0], c[1]) for c in s["flagged"]}
                for i in range(W * H):
                    o = ow[i]
                    if o >= 0 and (o >> 8, o & 255) in box:
                        x, y = i % W, i // W
                        if (o >> 8, o & 255) in hit:
                            px[x, y] = (255, 60, 60)
                            mask[i] = 150
                        elif (x + y) & 1:
                            px[x, y] = (255, 230, 60)
                            mask[i] = 120
        m = Image.frombytes("L", (W, H), bytes(mask))
        if herc:
            over = over.resize((W * 2, H), Image.NEAREST)
            m = m.resize((W * 2, H), Image.NEAREST)
        out = Image.composite(over, img.convert("RGB"), m)
        self.cache = (key, out)
        return out

    def draw(self, c):
        """over the canvas: the selected or hovered record in full (its pixels outlined), the Shade records
        and the box a ball in a flagged cell covers"""
        if not self._ready():
            return
        kx, ky = self.app.iso_scale
        recs, rule = self.recs(), self.data["records"]

        def runs(r, ink, w=2):
            for y, x0, x1 in r["runs"]:
                c.create_rectangle(x0 * kx, y * ky, (x1 + 1) * kx, (y + 1) * ky, outline=ink, width=w)
        if self.shade.get():
            for s in self.data.get("shade") or []:
                for k in s["records"]:
                    runs(rule[k], "#ff2020", 2)
                for cl, (xl, yt, xh, yb) in s["feet"].items():
                    c.create_rectangle(xl * kx, yt * ky, (xh + 1) * kx, (yb + 1) * ky, outline="#ffe23c", width=2,
                                       dash=(5, 3))
                    t = c.create_text(xl * kx + 4, yt * ky + 3, anchor="nw", fill="#2a2410",
                                      text="ball box, %s" % cl.replace(",", ", "))
                    r_ = c.create_rectangle(*c.bbox(t), fill="#ffe23c", outline="")
                    c.tag_raise(t, r_)
            sh = self.data.get("shade") or []
            if sh:                              # the one sentence, on the picture where it is read
                x, y, wd = c.canvasx(0) + 8, c.canvasy(0) + 8, max(200, c.winfo_width() - 40)
                t = c.create_text(x + 6, y + 4, anchor="nw", width=wd, fill="#fff3b0",
                                  text="\n".join(s_["why"] for s_ in sh))
                bb = c.bbox(t)
                r_ = c.create_rectangle(bb[0] - 6, bb[1] - 4, bb[2] + 6, bb[3] + 4, fill="#2a2410", outline="#ffe23c")
                c.tag_raise(t, r_)
        def ring(r, ink):                   # (a record is a few pixels: a ring round it finds it)
            xs = [x for _y, x0, x1 in r["runs"] for x in (x0, x1)]
            ys = [y for y, _x0, _x1 in r["runs"]]
            c.create_oval((min(xs) - 6) * kx, (min(ys) - 6) * ky, (max(xs) + 7) * kx, (max(ys) + 7) * ky,
                          outline=ink, width=2)
        if self.hot is not None and (not self.sel or self.sel != ("rec", self.hot)):
            runs(recs[self.hot], "#ffffff", 1)
        if self.sel and self.sel[0] == "rec":
            r = recs[self.sel[1]]
            for y, x0, x1 in r["runs"]:
                c.create_rectangle(x0 * kx, y * ky, (x1 + 1) * kx, (y + 1) * ky, fill="#00ffd0", outline="#000000")
            ring(r, "#00ffd0")
        if self.sel and self.sel[0] == "recs":          # several (130.58.47): each filled, no rings
            for k in self.sel[1]:
                for y, x0, x1 in recs[k]["runs"]:
                    c.create_rectangle(x0 * kx, y * ky, (x1 + 1) * kx, (y + 1) * ky, fill="#00ffd0", outline="")
        if self.sel and self.sel[0] in ("noocc", "noocs"):
            for cl in ([self.sel[1]] if self.sel[0] == "noocc" else self.sel[1]):
                bb = self._cell_box(cl)
                if bb:
                    c.create_rectangle(bb[0] * kx, bb[1] * ky, (bb[2] + 1) * kx, (bb[3] + 1) * ky, outline="#3c8cff",
                                       width=2)
        d = self.drag
        if d and d["moved"]:                            # the rectangle being dragged out
            x0, x1 = sorted((d["x"], d["x1"]))
            y0, y1 = sorted((d["y"], d["y1"]))
            c.create_rectangle(x0 * kx, y0 * ky, (x1 + 1) * kx, (y1 + 1) * ky, outline="#00ffd0", width=1,
                               dash=(4, 2))

    def _cell_box(self, cl):
        """a cell's pixels' box in the picture (its owner pixels), or None"""
        pic = self.app.pic
        W = pic["meta"]["width"]
        o, ow = 256 * cl[0] + cl[1], pic["owners"]
        xs, ys = [], []
        for i in range(len(ow)):
            if ow[i] == o:
                xs.append(i % W)
                ys.append(i // W)
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None

    # -- the mouse ------------------------------------------------------------
    def _rec_at(self, e):
        a = self.app
        if not self._ready() or a.view.get() != "iso" or not getattr(a, "iso_scale", None):
            return None
        x, y = a.cv.canvasx(e.x), a.cv.canvasy(e.y)
        kx, ky = a.iso_scale
        W, H = a.pic["meta"]["width"], a.pic["meta"]["lines"]
        px, py = int(x / kx), int(y / ky)
        for r in (0, 1, 2):             # (within 2 px: a rail is thin)
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if 0 <= px + dx < W and 0 <= py + dy < H:
                        ids = self.ats["shipped" if self.shipped() else "records"].get((py + dy) * W + px + dx)
                        if ids:
                            if self.shade.get() and not self.show.get():
                                shade_ids = {k for s in self.data.get("shade") or [] for k in s["records"]}
                                ids = [k for k in ids if k in shade_ids]
                                if not ids:
                                    continue
                            return ids[0]
        return None

    def describe(self, k):
        r = self.recs()[k]
        own = ", ".join("%d, %d" % (o[0], o[1]) for o in r["own"][:3]) or "nothing"
        rail = (" (the guard rail on line%s %s)" % ("s" if len(r["rails"]) > 1 else "",
                                                    ", ".join(map(str, r["rails"])))) if r["rails"] else ""
        hides = _cells(r["needs"])
        if self.shipped():
            return ("shipped occluder %d (cut as the rule's %s): drawn by %s%s, row %d, top %d px - hides the ball "
                    "in %s" % (k, _ids(r["rule"]), own, rail, r["s"], r["top"], hides or "no cell"))
        return ("occluder %d: drawn by %s%s, row %d, top %d px - hides the ball in %s%s" % (
            k, own, rail, r["s"], r["top"], hides or "no cell (it is the merge's)",
            ("; flags %s" % _cells(r["flags"])) if r["flags"] != r["needs"] else ""))

    def hover(self, e):
        """-> True when the pointer is over a record (the readout names it)"""
        if not (self.wanted() and self._ready()):
            return False
        k = self._rec_at(e)
        if k != self.hot:
            self.hot = k
            self.app._redraw()
        if k is None:
            cell = self.app._cell_at(e)
            if cell and cell in self.noocc and self.show.get():
                self.app.readout.config(text="x %d, y %d: noocclude - no occluder is cut for a ball here "
                                             "(click to change)" % cell)
                return True
            if cell and cell in self.flags and self.show.get():
                f = self.flags[cell]
                self.app.readout.config(text="x %d, y %d: a ball here can be hidden (%s)" % (
                    cell[0], cell[1], "OCC and OCCG: grounded too" if f & 4 else "OCC: airborne"))
                return True
            return False
        self.app.readout.config(text=self.describe(k))
        return True

    def _px(self, e):
        a = self.app
        kx, ky = a.iso_scale
        return int(a.cv.canvasx(e.x) / kx), int(a.cv.canvasy(e.y) / ky)

    def dragging(self):
        return self.drag is not None

    def press(self, e):
        """-> True when the press is the overlay's.  With Occluders shown every press in Iso is: a click selects a
        record or a noocclude cell (Ctrl-click adds or takes one away) and a drag selects every record - or, with
        none, every noocclude cell - with a pixel in the rectangle (130.58.47); a click on neither is handed back
        to the window.  Shade alone: a click selects one of its records"""
        if self.passing or not (self.wanted() and self._ready()):
            return False
        if self.show.get() and self.app.view.get() == "iso" and getattr(self.app, "iso_scale", None):
            x, y = self._px(e)
            ctrl = bool(e.state & 0x0004) or (sys.platform == "darwin" and bool(e.state & 0x0008))
            self.drag = {"x": x, "y": y, "x1": x, "y1": y, "ctrl": ctrl, "moved": False, "e": e}
            return True
        return self._click(e, False)

    def motion(self, e):
        d = self.drag
        x, y = self._px(e)
        if (x, y) != (d["x1"], d["y1"]):
            d["x1"], d["y1"] = x, y
            d["moved"] = d["moved"] or abs(x - d["x"]) + abs(y - d["y"]) > 2
            if d["moved"]:
                self.app._redraw()

    def release(self, e):
        d, self.drag = self.drag, None
        if not d["moved"]:
            if not self._click(d["e"], d["ctrl"]) and not d["ctrl"]:
                self.passing = True             # nothing of the overlay's there: the window's own click
                try:
                    self.app._press(d["e"])
                finally:
                    self.passing = False
            return
        x0, x1 = sorted((d["x"], d["x1"]))
        y0, y1 = sorted((d["y"], d["y1"]))
        self.pick_rect(x0, y0, x1, y1, d["ctrl"])

    def pick_rect(self, x0, y0, x1, y1, add=False):
        """the records of the list shown with a pixel in the picture's rectangle - or, with none, the noocclude
        cells with one - selected (ADD: added to what is selected of their kind)"""
        ids = set()
        for r in self.recs():
            if any(y0 <= y <= y1 and r_x0 <= x1 and r_x1 >= x0 for y, r_x0, r_x1 in r["runs"]):
                ids.add(r["id"])
        if ids:
            self._set_sel("recs", ids | (self._sel_set("recs") if add else set()))
        else:
            pic = self.app.pic
            W, ow = pic["meta"]["width"], pic["owners"]
            cells = set()
            for y in range(max(y0, 0), min(y1, pic["meta"]["lines"] - 1) + 1):
                for x in range(max(x0, 0), min(x1, W - 1) + 1):
                    o = ow[y * W + x]
                    if o >= 0 and (o >> 8, o & 255) in self.noocc:
                        cells.add((o >> 8, o & 255))
            self._set_sel("noocs", cells | (self._sel_set("noocs") if add else set()))
        self._selected()

    def _sel_set(self, kind):
        """what is selected of KIND ("recs": record ids, "noocs": cells), one or several"""
        if not self.sel:
            return set()
        one = {"recs": "rec", "noocs": "noocc"}[kind]
        return {self.sel[1]} if self.sel[0] == one else set(self.sel[1]) if self.sel[0] == kind else set()

    def _set_sel(self, kind, items):
        one = {"recs": "rec", "noocs": "noocc"}[kind]
        items = set(items)
        self.sel = None if not items else (one, next(iter(items))) if len(items) == 1 else (kind, frozenset(items))

    def sel_cells(self):
        """the selected records' cells (130.58.47) -> (every cell they hide, sorted; those noocclude may take - not
        the start's or a route point's; those noocclude already names)"""
        ks = self._sel_set("recs")
        cells = sorted({tuple(c) for k in ks for c in self.recs()[k]["needs"]})
        play = self.app.doc.in_play()
        return cells, {c for c in cells if c not in play}, set(cells) & self.noocc

    def toggle(self, kind, item):
        """Ctrl-click: ITEM (a record id, kind "recs", or a noocclude cell, "noocs") in or out of the selection"""
        cur = self._sel_set(kind)
        self._set_sel(kind, cur ^ {item})
        self._selected()

    def _selected(self):
        a = self.app
        a.sel, a.sels, a.area = None, [], None
        a._fill_inspector()
        a._redraw()
        if self.sel and self.sel[0] in ("recs", "noocs"):
            a._msg("%d %s selected" % (len(self.sel[1]), "occluder records" if self.sel[0] == "recs"
                                       else "noocclude cells"))
        elif self.sel and self.sel[0] == "rec":
            a._msg(self.describe(self.sel[1]))

    def _click(self, e, ctrl):
        """a click: -> True when it hit a record or a noocclude cell"""
        k = self._rec_at(e)
        a = self.app
        if k is None and self.show.get():
            cell = a._cell_at(e)
            if cell and cell in self.noocc:
                if ctrl:
                    self.toggle("noocs", cell)
                else:
                    self._set_sel("noocs", {cell})
                    self._selected()
                return True
        if k is None:
            if self.sel and not ctrl:
                self.sel = None
                a._redraw()
            return False
        if ctrl:
            self.toggle("recs", k)
        else:
            self._set_sel("recs", {k})
            self._selected()
        return True

    # -- the inspector ----------------------------------------------------------
    def fill_inspector(self):
        """the inspector for the selected record or noocclude cell; -> True when it filled it"""
        a = self.app
        if self.sel and a.view.get() != "iso":
            self.sel = None
        if not self.sel or a.sel or a.area or self.data is None:
            return False
        ttk = a.ttk
        body = a.ins_body
        a.raw.set("")
        a.ins_err.config(text="")
        if self.sel[0] == "noocs":                       # several noocclude cells (130.58.47)
            cells = set(self.sel[1])
            a.ins_title.config(text="%d noocclude cells selected" % len(cells))
            a.ins_line.config(text=_cells(sorted(cells)))
            ttk.Button(body, text="Hide the ball here again (remove noocclude from %d cells)" % len(cells),
                       command=lambda: self.noocclude(remove=cells)).grid(row=0, column=0, sticky="w")
            a.ins_help.config(text="No occluder is cut for a ball in these cells. Take them out (one undo step) and "
                              "the occluders are cut for them again. Ctrl-click adds or takes away one cell; drag "
                              "a rectangle to choose again.")
            return True
        if self.sel[0] == "recs":                        # several records (130.58.47)
            ks = sorted(self.sel[1])
            cells, ok, back = self.sel_cells()
            a.ins_title.config(text="%d %soccluder records selected" % (len(ks), "shipped " if self.shipped()
                                                                          else ""))
            a.ins_line.config(text="records %s" % _ids(ks))
            ttk.Label(body, text="Hide the ball in").grid(row=0, column=0, sticky="nw")
            ttk.Label(body, text="%d cells: %s" % (len(cells), _cells(cells) or "-"),
                      wraplength=220).grid(row=0, column=1, sticky="w")
            b = ttk.Button(body, text="Don't hide the ball here (noocclude %d cell%s)" % (
                len(ok), "" if len(ok) == 1 else "s"), command=lambda: self.noocclude(add=ok))
            b.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 2))
            if not ok:
                b.state(["disabled"])
            b2 = ttk.Button(body, text="Hide it again (remove noocclude from %d cell%s)" % (
                len(back), "" if len(back) == 1 else "s"), command=lambda: self.noocclude(remove=back))
            b2.grid(row=2, column=0, columnspan=2, sticky="w")
            if not back:
                b2.state(["disabled"])
            a.ins_help.config(text="Each button is ONE edit (one undo step) over every cell these records hide. "
                              "Ctrl-click adds or takes away one record; drag a rectangle to choose again (with "
                              "Ctrl held, to add).%s" % (" The start and route points cannot take noocclude: %s." %
                                                         _cells(sorted(set(cells) - ok)) if len(ok) < len(cells)
                                                         else ""))
            return True
        if self.sel[0] == "noocc":
            cell = self.sel[1]
            a.ins_title.config(text="No occluding at %d, %d" % cell)
            a.ins_line.config(text="noocclude (SPEC.md 130.53)")
            ttk.Button(body, text="Hide the ball here again (remove noocclude)",
                       command=lambda: self.noocclude(remove={cell})).grid(row=0, column=0, sticky="w")
            ttk.Button(body, text="Remove every noocclude (%d cells)" % len(self.noocc),
                       command=lambda: self.noocclude(remove=set(self.noocc))).grid(row=1, column=0, sticky="w",
                                                                                     pady=4)
            a.ins_help.config(text="No occluder is cut for a ball in this cell, so a ball here is drawn whole, in "
                              "front of whatever stands nearer the viewer. Take it out and the occluders are cut "
                              "for it again.")
            return True
        r = self.recs()[self.sel[1]]
        a.ins_title.config(text="%s %d" % ("Shipped occluder" if self.shipped() else "Occluder", r["id"]))
        a.ins_line.config(text="drawn by %s" % (", ".join("%d, %d (%d px)" % tuple(o) for o in r["own"][:3])
                                                or "nothing"))
        rows = [("Rail", ", ".join("line %d" % l_ for l_ in r["rails"]) if r["rails"] else "-"),
                ("Row / top", "%d / %d px" % (r["s"], r["top"])),
                ("Hides the ball in", _cells(r["needs"]) or "-")]
        rows.append(("Cut as", "the rule's %s" % _ids(r["rule"])) if self.shipped() else
                    ("Flags OCC in", _cells(r["flags"]) or "-"))
        for i, (k, v) in enumerate(rows):
            ttk.Label(body, text=k).grid(row=i, column=0, sticky="nw")
            ttk.Label(body, text=v, wraplength=220).grid(row=i, column=1, sticky="w")
        play = a.doc.in_play()
        cells = [tuple(c) for c in r["needs"]]
        ok = [c for c in cells if c not in play]
        b = ttk.Button(body, text="Don't hide the ball here (noocclude %d cell%s)" % (len(ok), "" if len(ok) == 1
                                                                                         else "s"),
                       command=lambda: self.noocclude(add=set(ok)))
        b.grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=6)
        if not ok:
            b.state(["disabled"])
        a.ins_help.config(text="These pixels are laid back over a ball in the cells it hides, so the ball shows "
                          "behind what drew them. noocclude names cells no ball needs occluding in (a place no "
                          "player realistically reaches): no record is cut for a ball there, and a record no other "
                          "cell needs goes.%s" % (" The start and route points cannot take it: %s." % _cells(
                              [c for c in cells if c in play]) if len(ok) < len(cells) else ""))
        return True

    def noocclude(self, add=(), remove=()):
        a = self.app
        r = a._edit(a.doc.set_noocclude, add=add, remove=remove)
        if r is None:
            return
        added, removed, refused = r
        self.sel = None
        a._fill_inspector()
        a._msg("%s%s%s - the picture is cut again" % (
            ("noocclude added for %s" % _cells(sorted(added))) if added else "",
            ("; " if added and removed else "") + (("noocclude taken out of %s" % _cells(sorted(removed)))
                                                   if removed else ""),
            ("; not on the start or a route point: %s" % _cells(sorted(refused))) if refused else ""))


def _bare(err):
    """a refusal without its file name, cut short for the status line"""
    err = err.split(": ", 1)[1] if ": " in err else err
    return err[:220]


def _ids(ks):
    s = ", ".join(map(str, ks[:6]))
    return (s + (" and %d more" % (len(ks) - 6) if len(ks) > 6 else "")) if ks else "none (AV's residual alone)"


def _cells(cs):
    cs = [tuple(c) for c in cs]
    s = "; ".join("%d, %d" % c for c in cs[:8])
    return s + (" and %d more" % (len(cs) - 8) if len(cs) > 8 else "")
