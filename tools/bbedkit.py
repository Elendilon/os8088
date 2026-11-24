#!/usr/bin/env python3
"""bbedkit - THE COURSE BUILDER'S KIT VIEWS (SPEC.md 130.58.52): what of a course comes from THE STANDARD KIT
(SPEC.md 130.37), and what is in the kit.

- **The Kit overlay** (the Iso view, `KitView`): over the picture, every 8 x 8 picture BLOCK whose bytes are a kit
  piece washed green, the course's own blocks amber (the black block, every course's block 0, left plain); every
  FIELD cell whose shape table is a kit F piece striped cyan, an own table's violet, each labelled; and with
  *Masks (K)* every occluder record the part ships checkered blue when its mask is a kit K piece, red when it is
  the course's own. A summary line counts each class against the course's and says the bytes the kit saves it.
  The data is the picture job's (tools/bbedjob.py `picture ... --kit`, kit.json; the masks ride the occluder
  compile, `--occ`, occ.json's `kmask`), cut only while the overlay is on.
- **The Kit tab** (`KitTab`): every piece of the kit, drawn - blocks as zoomed tiles in the open course's palette,
  masks as zoomed 1-bit tiles, FIELD tables as height thumbnails - each with its index and how many of the pool
  courses (bbcourse.KIT_POOL) use it, ringed when the open course does and red when no pool course does any more;
  the pieces the kit LACKS that a re-cut would take; the totals; when the source was last committed. The data is
  the kit job's (`bbedjob.py kit`, kitlib.json: the pool courses compiled through the compile cache). Clicking a
  piece names who uses it, and *Show where this course uses it* rings every place on the Iso view.

Made by tools/bbedit.py with the window: `KitView(app, row)` and `KitTab(app, nb, Job, photo)`. Nothing here runs a
compile: the jobs do.
"""

import json
import os
import time

KIT_TINT = (80, 255, 120)       # a block from the kit: the grey picture tinted green
OWN_TINT = (255, 175, 60)       # the course's own block: amber
KMASK_INK = (80, 150, 255)      # a record whose mask is the kit's: blue
OMASK_INK = (255, 60, 90)       # ... the course's own mask: red
KTAB_INK = (170, 255, 255)      # a FIELD cell whose table is the kit's: pale cyan stripes
OTAB_INK = (200, 90, 255)       # ... its own table: violet stripes
PICK = "#ff3cdc"                # the places the Kit tab's chosen piece is used
CLASS_WORD = {"B": ("block", "blocks"), "K": ("mask", "masks"), "F": ("table", "tables")}


def _n(v):
    return format(v, ",")


def _ink(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def summary(kd, kk=None):
    """the overlay's line (SPEC.md 130.58.52.2): each class from the kit against the course's, and the bytes the kit
    saves this course (its stored form, before packing) against its own pieces'; KK the K account (occ.json's
    `kit`), or None while the masks are not cut"""
    if not kd.get("play"):
        return "No kit: %s" % kd.get("why", "not a play course")
    cl = dict(kd["classes"])
    if kk:
        cl["K"] = kk
    parts = []
    for t in "BKF":
        a = cl.get(t)
        if a is None:
            parts.append("masks: turn on Masks (K) - the full rules' compile")
            continue
        one, many = CLASS_WORD[t]
        if not a["all"]:
            parts.append("no %s" % many)
            continue
        s = "%s %s of %s from the kit" % (many, _n(a["kit"]), _n(a["all"]))
        if t == "B" and kd["pose"]["n"]:
            s += " (%d of the %d only lanes' poses use)" % (kd["pose"]["kit"], kd["pose"]["n"])
        if a["kit"] and not a["ref"]:
            s += " - carried, the bitmap would cost more"
        parts.append(s)
    saved = sum(cl[t]["saved"] for t in cl)
    named = sum(cl[t]["named"] for t in cl)
    bm = sum(cl[t]["bitmap"] for t in cl)
    own = sum(cl[t]["own"] for t in cl)
    return "%s: %s.  The kit saves it %s bytes of its stored form (%s named, for %s of bitmap); its own pieces are " \
           "%s bytes%s.  Green: the kit's blocks, amber its own (the picture greyed); blue / red checker: masks; " \
           "cyan / violet stripes: FIELD tables" % (
               kd.get("name", "the course"), "; ".join(parts), _n(saved), _n(named), _n(bm), _n(own),
               "" if kk else " (the masks not counted)")


class KitView(object):
    """the Kit overlay and its row of the Iso view's options"""

    def __init__(self, app, row):
        self.app = app
        tk, ttk = app.tk, app.ttk
        self.show = tk.BooleanVar(value=False)
        self.own = tk.BooleanVar(value=True)
        self.masks = tk.BooleanVar(value=False)
        self.data = None                # kit.json of the picture shown
        self.kmask = None               # occ.json's shipped rows with `kmask`, and its `kit` account (K)
        self.pick = None                # (tag, kit index) chosen in the Kit tab: its places ringed
        self.cache = None
        self.row = row
        ttk.Checkbutton(row, text="Kit", variable=self.show, command=self.toggled).pack(side="left")
        ttk.Checkbutton(row, text="own blocks too", variable=self.own, command=self.toggled).pack(side="left")
        ttk.Checkbutton(row, text="Masks (K)", variable=self.masks, command=self.toggled).pack(side="left")
        self.label = ttk.Label(row, text="", foreground="#1d5e33", wraplength=900, justify="left")

    # -- the job --------------------------------------------------------------
    def wanted(self):
        return bool(self.show.get())

    def wants_occ(self):
        """the masks are the occluder compile's (the full rules), so they are cut only while asked for"""
        return bool(self.show.get() and self.masks.get())

    def toggled(self):
        a = self.app
        meta = a.pic["meta"] if a.pic else None
        if self.wanted() and (a.pic_job and a.pic_job.running or meta is not None and (
                meta.get("kit") is None or self.wants_occ() and meta.get("occ") is None)):
            a.run_picture()
            self._say("Finding what comes from the kit%s..." % (
                " and cutting the occluders (tens of seconds on a big course)" if self.wants_occ() else ""))
        if not self.wanted():
            self._say("")
        elif self.data is not None:
            self._say(summary(self.data, self.kmask and self.kmask["kit"]))
        if self.wanted() and a.view.get() != "iso":
            a.view.set("iso")
        self.cache = None
        a._redraw()

    def loaded(self, out, meta):
        """the picture job's OUTDIR read: kit.json when it wrote one, and occ.json's mask rows for K"""
        self.data, self.kmask, self.cache = None, None, None
        if meta.get("kit"):
            try:
                with open(os.path.join(out, "kit.json")) as f:
                    self.data = json.load(f)
            except (OSError, ValueError) as e:
                self._say("kit.json could not be read: %s" % e)
        om = meta.get("occ")
        if self.wants_occ() and om and (not om.get("error") or om.get("partial")):
            try:
                with open(os.path.join(out, "occ.json")) as f:
                    od = json.load(f)
                if od.get("kit"):
                    self.kmask = {"kit": od["kit"], "recs": [r for r in od.get("shipped", ())
                                                             if r.get("kmask") is not None]}
            except (OSError, ValueError):
                pass
        if self.wanted() and not self.app.pic_after and (
                meta.get("kit") is None or self.wants_occ() and om is None):
            self.app.root.after(10, self.app.run_picture)     # (drawn before the overlay was turned on: again)
        if self.wanted() and self.data is not None:
            self._say(summary(self.data, self.kmask and self.kmask["kit"]))

    def _say(self, text):
        self.label.config(text=text)
        if text and not self.label.winfo_manager():
            self.label.pack(side="bottom", anchor="w", padx=8, before=self.row.winfo_children()[0])
        elif not text:
            self.label.pack_forget()

    def _ready(self):
        a = self.app
        return self.wanted() and self.data is not None and self.data.get("play") and a.pic

    # -- the picture ----------------------------------------------------------
    def block_at(self, x, y):
        """picture pixel (x, y) -> (block column, block row, block index) at the kit's alignment, or None"""
        d = self.data
        by, bx = (y + d["dy"]) >> 3, x >> 3
        if 0 <= bx < d["cols"] and 0 <= by < d["brows"]:
            return bx, by, d["map"][by * d["cols"] + bx]
        return None

    def composite(self, img, herc):
        """the picture made grey and each block tinted - the kit's green, the course's own amber (or left grey), the
        black block plain - so the classes read whatever the course's palette; the FIELD cells striped by their
        table's class, and with Masks (K) each shipped record checkered by its mask's - one image, kept until the
        picture or a toggle changes"""
        if not self._ready():
            return img
        from PIL import Image
        key = (id(self.app.pic), herc, self.own.get(), bool(self.kmask), id(self.data))
        if self.cache and self.cache[0] == key:
            return self.cache[1]
        d = self.data
        meta = self.app.pic["meta"]
        W, H = meta["width"], meta["lines"]
        from PIL import ImageChops
        cols, brows, nb = d["cols"], d["brows"], len(d["use"]["B"])
        small = Image.new("RGB", (cols, brows), (255, 255, 255))
        sp = small.load()
        own = self.own.get()
        for i, j in enumerate(d["map"]):
            if j == 0:                  # (the black block: every course's block 0 and the kit's piece 0, 130.10.4)
                continue
            if j < nb:
                sp[i % cols, i // cols] = KIT_TINT
            elif own:
                sp[i % cols, i // cols] = OWN_TINT
        tint = Image.new("RGB", (W, H), (255, 255, 255))
        tint.paste(small.resize((cols * 8, brows * 8), Image.NEAREST), (0, -d["dy"]))
        if herc:
            tint = tint.resize((W * 2, H), Image.NEAREST)
        grey = img.convert("L").point(lambda v: 70 + v * 185 // 255).convert("RGB")
        base = ImageChops.multiply(grey, tint)
        over = Image.new("RGB", (W, H))
        mask = Image.new("L", (W, H))
        px, mp = over.load(), mask.load()
        if d["fcells"]:
            fk = {(x, y): k for x, y, _s, k in d["fcells"]}
            ow = self.app.pic["owners"]
            for i in range(W * H):
                o = ow[i]
                if o < 0:
                    continue
                k = fk.get((o >> 8, o & 255))
                if k is None:
                    continue
                x, y = i % W, i // W
                if (x - y) % 4 == 0:
                    px[x, y] = KTAB_INK if k >= 0 else OTAB_INK
                    mp[x, y] = 235
        if self.kmask:
            for r in self.kmask["recs"]:
                ink = KMASK_INK if r["kmask"] >= 0 else OMASK_INK
                for y, x0, x1 in r["runs"]:
                    for x in range(x0, x1 + 1):
                        if not (x + y) & 1 and 0 <= y < H:
                            px[x, y] = ink
                            mp[x, y] = 255
        if herc:
            over = over.resize((W * 2, H), Image.NEAREST)
            mask = mask.resize((W * 2, H), Image.NEAREST)
        out = Image.composite(over, base, mask)
        self.cache = (key, out)
        return out

    def places(self, tag, k):
        """the open picture's places that use kit piece K of class TAG: boxes in picture pixels [(x0, y0, x1, y1)]"""
        d = self.data
        out = []
        if not d or not d.get("play"):
            return out
        if tag == "B":
            use, cols = d["use"]["B"], d["cols"]
            js = {j for j, kk in enumerate(use) if kk == k}
            for i, j in enumerate(d["map"]):
                if j in js:
                    x, y = 8 * (i % cols), 8 * (i // cols) - d["dy"]
                    out.append((x, y, x + 7, y + 7))
        elif tag == "F":
            for x, y, _s, kk in d["fcells"]:
                if kk == k:
                    bb = self.app.occ._cell_box((x, y))
                    if bb:
                        out.append(bb)
        elif tag == "K" and self.kmask:
            for r in self.kmask["recs"]:
                if r["kmask"] == k and r["runs"]:
                    xs = [x for _y, a, b in r["runs"] for x in (a, b)]
                    ys = [y for y, _a, _b in r["runs"]]
                    out.append((min(xs), min(ys), max(xs), max(ys)))
        return out

    def draw(self, c):
        """over the canvas: each FIELD cell's table named (F and its kit index, or `own`), and the Kit tab's chosen
        piece's places ringed"""
        if not self._ready():
            return
        kx, ky = self.app.iso_scale
        if self.data["fcells"] and kx >= 2:
            for x, y, s, k in self.data["fcells"]:
                bb = self.app.occ._cell_box((x, y))
                if bb:
                    c.create_text((bb[0] + bb[2] + 1) * kx / 2, (bb[1] + bb[3] + 1) * ky / 2, fill="#ffffff",
                                  text="F%d" % k if k >= 0 else "own %d" % s, font=("TkDefaultFont", 8))
        if self.pick:
            for x0, y0, x1, y1 in self.places(*self.pick):
                c.create_rectangle(x0 * kx - 1, y0 * ky - 1, (x1 + 1) * kx + 1, (y1 + 1) * ky + 1, outline=PICK,
                                   width=2)

    def show_pick(self, tag, k):
        """the Kit tab's piece: the overlay on (with the masks for a K piece), Iso, its places ringed and the first
        scrolled to"""
        a = self.app
        self.pick = (tag, k)
        self.show.set(True)
        if tag == "K":
            self.masks.set(True)
        self.toggled()
        a.nb.select(0)
        pl = self.places(tag, k)
        if pl and getattr(a, "iso_scale", None) and a.pic:
            kx, ky = a.iso_scale
            W, H = a.pic["meta"]["width"] * kx, a.pic["meta"]["lines"] * ky
            x0, y0 = pl[0][0] * kx, pl[0][1] * ky
            a.cv.xview_moveto(max(0.0, (x0 - 200) / max(W, 1)))
            a.cv.yview_moveto(max(0.0, (y0 - 150) / max(H, 1)))
        one, many = CLASS_WORD[tag]
        a._msg("Kit %s %d: %s on the picture%s" % (one, k, "%d place%s" % (len(pl), "" if len(pl) == 1 else "s") if pl
                                                   else "not used",
                                                   "" if self.data or tag != "K" else " (cutting...)"))

    def describe_at(self, x, y):
        """the readout's words for picture pixel (x, y) while the overlay shows, or None"""
        if not self._ready():
            return None
        b = self.block_at(x, y)
        if b is None:
            return None
        bx, by, j = b
        use = self.data["use"]["B"]
        if j == 0:
            what = "the black block (kit block 0)"
        elif j < len(use):
            what = "kit block %d" % use[j]
        else:
            what = "the course's own block %d" % j
        out = ["block %d, %d: %s" % (bx, by, what)]
        if self.kmask:
            for r in self.kmask["recs"]:
                if any(yy == y and a <= x <= b_ for yy, a, b_ in r["runs"]):
                    out.append("occluder %d's mask: %s" % (r["id"], "kit mask %d" % r["kmask"] if r["kmask"] >= 0
                                                            else "the course's own"))
                    break
        return "; ".join(out)


# ----------------------------------------------------------------------------
# the Kit tab
# ----------------------------------------------------------------------------

def tile_block(hexs, pal, z):
    """a kit block (16 CGA bytes: 8 rows of 2, four pixels a byte, the leftmost in bits 7-6) as a Z-times image"""
    from PIL import Image
    b = bytes.fromhex(hexs)
    im = Image.new("RGB", (8, 8))
    p = im.load()
    for y in range(8):
        for x in range(8):
            v = (b[2 * y + (x >> 2)] >> (6 - 2 * (x & 3))) & 3
            p[x, y] = tuple(pal[v])
    return im.resize((8 * z, 8 * z), Image.NEAREST)


def tile_mask(hexs, z):
    """a kit mask (16 bytes, 2 bits a pixel: 11 keeps the buffer - the ball shows - and 00 lays the record's pixel)
    as a 1-bit Z-times image: laid dark, kept light"""
    from PIL import Image
    b = bytes.fromhex(hexs)
    im = Image.new("RGB", (8, 8))
    p = im.load()
    for y in range(8):
        for x in range(8):
            v = (b[2 * y + (x >> 2)] >> (6 - 2 * (x & 3))) & 3
            p[x, y] = (225, 228, 235) if v == 3 else (30, 34, 48)
    return im.resize((8 * z, 8 * z), Image.NEAREST)


def tile_table(hexs, z):
    """a kit FIELD table (17 x 17 relative heights, SPEC.md 130.28.2) as a Z-times height thumbnail, low dark"""
    from PIL import Image
    b = bytes.fromhex(hexs)
    lo, hi = min(b), max(b)
    im = Image.new("RGB", (17, 17))
    p = im.load()
    for v in range(17):
        for u in range(17):
            g = 50 + (205 * (b[17 * v + u] - lo) // (hi - lo) if hi > lo else 100)
            p[u, v] = (g, g, min(255, g + 30))
    return im.resize((17 * z, 17 * z), Image.NEAREST)


class KitTab(object):
    """the Kit tab: the kit's pieces, who uses each, the totals and the staleness"""

    ZOOM = {"B": 5, "K": 5, "F": 3}
    PAD = 6
    LAB = 16

    def __init__(self, app, nb, Job, photo):
        self.app, self.Job, self.photo_of = app, Job, photo
        tk, ttk = app.tk, app.ttk
        self.data = None                # kitlib.json
        self.job = None
        self.text = None                # the course text the data counted (None: none open)
        self.masks = tk.BooleanVar(value=False)
        self.sel = None                 # (tag, index) or ("missing", tag, index)
        self.hits = []                  # [(x0, y0, x1, y1, sel)] on the canvas
        self.photos = []
        f = ttk.Frame(nb)
        nb.add(f, text="Kit")
        self.frame = f
        left = ttk.Frame(f, padding=8, width=380)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        ttk.Label(left, text="The standard kit", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(left, wraplength=360, justify="left", foreground="#444", text=(
            "Picture blocks (B), occluder masks (K) and FIELD shape tables (F) held ONCE, in BZKIT.BIN, instead of "
            "once a course: a course NAMES the kit's pieces and they are copied in at its load (SPEC.md 130.37). "
            "Each piece shows its index and how many pool courses use it; ringed green when this course does, red "
            "when no pool course does any more.")).pack(anchor="w", pady=(2, 6))
        bf = ttk.Frame(left)
        bf.pack(fill="x")
        ttk.Button(bf, text="Count again", command=self.run).pack(side="left")
        ttk.Checkbutton(bf, text="this course's masks too (slower)", variable=self.masks,
                        command=self.run).pack(side="left", padx=6)
        self.status_l = ttk.Label(left, wraplength=360, justify="left", foreground="#0b6b80", text="")
        self.status_l.pack(anchor="w", pady=(6, 0))
        self.totals_l = ttk.Label(left, wraplength=360, justify="left", text="")
        self.totals_l.pack(anchor="w", pady=(6, 0))
        self.stale_l = ttk.Label(left, wraplength=360, justify="left", foreground="#8a1d12", text="")
        self.stale_l.pack(anchor="w", pady=(6, 0))
        ttk.Separator(left).pack(fill="x", pady=8)
        self.info_l = ttk.Label(left, wraplength=360, justify="left", text="Click a piece to see who uses it.")
        self.info_l.pack(anchor="w")
        self.show_b = ttk.Button(left, text="Show where this course uses it", command=self.show_pick)
        cf = ttk.Frame(f)
        cf.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(cf, background="#20242b", highlightthickness=0)
        ys = ttk.Scrollbar(cf, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=ys.set)
        self.cv.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Configure>", lambda e: self.draw() if self.data else None)
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.cv.bind("<Button-4>", lambda e: self.cv.yview_scroll(-3, "units"))
        self.cv.bind("<Button-5>", lambda e: self.cv.yview_scroll(3, "units"))

    def shown(self):
        try:
            return self.app.nb.select() == str(self.frame)
        except Exception:
            return False

    def refresh(self):
        """the tab shown: counted again when the course changed since (or never counted)"""
        t = self._course_text()
        if self.data is None or t != self.text:
            if not (self.job and self.job.running):
                self.run()

    def _course_text(self):
        a = self.app
        return a.doc.text() if a.doc.analysis().get("src") is not None else None

    def run(self):
        a = self.app
        if self.job:
            self.job.kill()
        text = self._course_text()
        out = os.path.join(a.tmp, "kit-%d" % int(time.time() * 1000))
        argv = ["kit", out]
        if text is not None:
            argv += [a._write_tmp("kit"), "--name", a._name()] + (["--masks"] if self.masks.get() else [])
        t0 = time.time()

        def ev(job, e):
            if e["stage"] == "done":
                if e.get("ok"):
                    try:
                        with open(os.path.join(out, "kitlib.json")) as f:
                            self.data = json.load(f)
                        self.text = text
                    except (OSError, ValueError) as x:
                        self.status_l.config(text="kitlib.json could not be read: %s" % x)
                        return
                    self.status_l.config(text="Counted in %.1f s (the pool courses through the compile cache: "
                                              "about 40 s the first time, a second or two after)." % (
                                                  time.time() - t0))
                    self.draw()
                else:
                    self.status_l.config(text="The kit could not be counted: %s" % e.get("error"))
            elif e["stage"] not in ("exit", "log"):
                self.status_l.config(text="Counting: %s..." % e.get("what", e["stage"]))
        self.job = self.Job(argv, ev).start()
        self.status_l.config(text="Counting the pool courses' use of the kit...")

    def poll(self):
        if self.job:
            self.job.poll()
            if not self.job.running:
                self.job.poll()
                self.job = None
        return bool(self.job)

    # -- drawing ----------------------------------------------------------------
    def _texts(self):
        d = self.data
        tt = d["totals"]
        np = len(d["pool"])
        kit = d["pieces"]
        tot = ("THE KIT (%s): %s blocks (%s bytes), %s masks (%s), %s tables (%s): BZKIT.BIN %s bytes (and its "
               "replay log's %s-byte tail: %s held), %s LZB on the disk.\nCut from the pool: %s.\nLast committed: "
               "%s." % (
                   d["source"], _n(len(kit["B"])), _n(tt["bytes"]["B"]), _n(len(kit["K"])), _n(tt["bytes"]["K"]),
                   _n(len(kit["F"])), _n(tt["bytes"]["F"]), _n(tt["part"]), _n(tt["file"] - tt["part"]),
                   _n(tt["file"]), _n(tt["lzb"]), ", ".join(d["pool"]) or "-",
                   d["cut"] or "not recorded (no git here; the source names no date)"))
        c = d.get("course")
        if c and c.get("error"):
            tot += "\nThis course: does not compile (%s)." % c["error"][:200]
        elif c:
            tot += "\nThis course (%s) names %s." % (c["name"], ", ".join(
                "%d %s" % (len(c["use"][t]), CLASS_WORD[t][1]) for t in "BKF" if c["use"][t] is not None) + (
                    "" if c["use"]["K"] is not None else " (masks not counted)"))
        else:
            tot += "\nNo play course open: the open course's use is not shown."
        if d["pool_err"]:
            tot += "\nNot counted: %s." % "; ".join("%s: %s" % (n, e[:80]) for n, e in d["pool_err"])
        un, mi = d["unused"], d["missing"]
        st = []
        if any(un[t] for t in "BKF"):
            st.append("STALE - in the kit, used by none of the %d pool courses (red): %s." % (np, ", ".join(
                "%d %s" % (len(un[t]), CLASS_WORD[t][1 if len(un[t]) != 1 else 0]) for t in "BKF" if un[t])))
        if any(mi[t] for t in "BKF"):
            st.append("MISSING - shared by %d or more pool courses (any FIELD table one holds) but not in the kit "
                      "(below the kit): %s." % (d["min"], ", ".join(
                          "%d %s" % (len(mi[t]), CLASS_WORD[t][1 if len(mi[t]) != 1 else 0]) for t in "BKF"
                          if mi[t])))
        if st:
            st.append("A stale kit costs bytes, never correctness: a re-cut (python3 tools/bbcourse.py kit) is the "
                      "owner's call (SPEC.md 130.37.2, 130.37.12).")
        else:
            st.append("Not stale: every piece is used and nothing shared is missing.")
        return tot, "\n".join(st)

    def draw(self):
        from PIL import Image
        d = self.data
        if not d:
            return
        tot, st = self._texts()
        self.totals_l.config(text=tot)
        self.stale_l.config(text=st)
        c = self.cv
        c.delete("all")
        self.photos, self.hits = [], []
        width = max(300, c.winfo_width() - 16)
        pal = d["palette"]
        mine = d.get("course") or {}
        muse = {t: set(mine["use"][t]) if mine.get("use") and mine["use"][t] is not None else None for t in "BKF"}
        y = 8
        np = len(d["pool"])
        for t in "BKF":
            one, many = CLASS_WORD[t]
            secs = [("%s: %s %s, %s bytes each - index, then pool courses using it (of %d)" % (
                t, _n(len(d["pieces"][t])), many, d["size"][t], np), [(i, q, len(d["uses"][t][i]))
                                                                       for i, q in enumerate(d["pieces"][t])], False)]
            if d["missing"][t]:
                secs.append(("%s not in the kit, shared by pool courses (a re-cut would take them) - how many hold "
                             "it" % many, [(i, q, len(ks)) for i, (q, ks) in enumerate(d["missing"][t])], True))
            for title, items, missing in secs:
                c.create_text(8, y, anchor="nw", fill="#e6e6e6", text=title, font=("TkDefaultFont", 10, "bold"))
                y += 22
                z = self.ZOOM[t]
                side = (17 if t == "F" else 8) * z
                pitch = side + 2 * self.PAD
                per = max(1, width // pitch)
                rows = (len(items) + per - 1) // per
                sheet = Image.new("RGB", (per * pitch, max(1, rows) * (pitch + self.LAB)), (32, 36, 43))
                for n, (i, q, uses) in enumerate(items):
                    tx, ty = (n % per) * pitch + self.PAD, (n // per) * (pitch + self.LAB) + self.PAD
                    im = tile_block(q, pal, z) if t == "B" else tile_mask(q, z) if t == "K" else tile_table(q, z)
                    sheet.paste(im, (tx, ty))
                ph = self.photo_of(self.app.tk, sheet)
                self.photos.append(ph)
                c.create_image(8, y, image=ph, anchor="nw")
                for n, (i, q, uses) in enumerate(items):
                    tx, ty = 8 + (n % per) * pitch + self.PAD, y + (n // per) * (pitch + self.LAB) + self.PAD
                    sel = ("missing", t, i) if missing else (t, i)
                    if missing:
                        ring, lab = "#e0b000", "x%d" % uses
                    else:
                        here = muse[t] is not None and i in muse[t]
                        ring = "#ff4040" if not uses else "#40e080" if here else "#5a606b"
                        lab = "%d  %d" % (i, uses)
                    w = 3 if self.sel == sel else 2 if ring != "#5a606b" else 1
                    c.create_rectangle(tx - 2, ty - 2, tx + side + 1, ty + side + 1, outline="#ffffff"
                                       if self.sel == sel else ring, width=w)
                    c.create_text(tx + side // 2, ty + side + 3, anchor="n", fill="#cfd3da", text=lab,
                                  font=("TkDefaultFont", 7))
                    self.hits.append((tx - 2, ty - 2, tx + side + 2, ty + side + self.LAB, sel))
                y += rows * (pitch + self.LAB) + 10
        c.configure(scrollregion=(0, 0, width, y + 20))

    def _click(self, e):
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        for x0, y0, x1, y1, sel in self.hits:
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.select(sel)
                return

    def select(self, sel):
        """a piece chosen: who uses it, and the button that shows its places on the Iso view"""
        d = self.data
        self.sel = sel
        self.show_b.pack_forget()
        if sel[0] == "missing":
            _m, t, i = sel
            q, ks = d["missing"][t][i]
            self.info_l.config(text="Not in the kit: a %s %s held as their own by %s (%d of %d pool courses). The kit's "
                                    "rule (%s) would take it at a re-cut." % (
                                        CLASS_WORD[t][0], "of %d bytes" % d["size"][t],
                                        ", ".join(d["pool"][k] for k in ks), len(ks), len(d["pool"]),
                                        "every FIELD table any pool course holds" if t == "F" else
                                        "a piece %d or more pool courses hold" % d["min"]))
        else:
            t, i = sel
            us = [d["pool"][k] for k in d["uses"][t][i]]
            mine = d.get("course") or {}
            pl = (mine.get("places") or {}).get(t)
            if not mine.get("use"):
                here = "No play course open."
            elif pl is None:
                here = "This course's masks are not counted (tick \"this course's masks too\")."
            else:
                n = pl.get(str(i), 0)
                here = "This course (%s): %s." % (mine["name"], "uses it at %d place%s" % (n, "" if n == 1 else "s")
                                                  if n or i in (mine["use"][t] or ()) else "does not use it")
            self.info_l.config(text="Kit %s %d: %d bytes%s.\nUsed by %s (%d of %d pool courses).\n%s" % (
                CLASS_WORD[t][0], i, d["size"][t], " - the black block, every course's block 0" if t == "B" and i == 0
                else "", ", ".join(us) or "NO pool course - stale", len(us), len(d["pool"]), here))
            if mine.get("use") and (mine["use"][t] is None or i in mine["use"][t]):
                self.show_b.pack(anchor="w", pady=6)
        self.draw()

    def show_pick(self):
        if self.sel and self.sel[0] in "BKF":
            self.app.kitv.show_pick(*self.sel)
