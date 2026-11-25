#!/usr/bin/env python3
"""The clock STUDY kit courses 5 - 7 share (KITE, LODE, KEEP; 2026-11-25), as ../penkit.py is the pen their
sketches share.  Host only; nothing in `make` runs it and it ships nothing.  The method is WINDMILL LANE's and
DOWNHILL DECISION's (mill/clocks/sheet.py, down/clocks/sheet.py; the brief is the course guide's G23): a
course's `clocks/frames.py` holds its CONCEPTS - one object, a variant a position - drawn with the tool's own
`_ClockArt` round `clock_face_geom`'s digits' blocks; this kit compiles the course with each concept's frames
named on its clocks, crops each clock out of the course's REAL picture on both cards, and prices it.

A course's clocks/sheet.py is three lines:

    import clockkit; clockkit.main(course="kite", palette=0, positions=("start", "plaza", "launch", "summit"))

    python3 <course>/clocks/sheet.py [CONCEPT ...]   compile the course with each concept's frames (a process
                                                     each), write clocks/<concept>.txt (the sizes) and cache
                                                     the picture; then the overview sheets
    python3 <course>/clocks/sheet.py --overview      clocks/overview-cga.png, overview-herc.png from the cache:
                                                     a row a position, a column a concept, "47" in the digits
    python3 <course>/clocks/sheet.py --preview       clocks/frames.png: every frame on a plain block, no compile
    python3 <course>/clocks/sheet.py --outline       each frame's width, blocks and partly covered blocks

frames.py gives CONCEPTS = {concept: [(frame name, extra clauses for its `clock` line), ...]} in the clocks'
order (the course file's), DRAW = {frame name: draw(B, p, x0, y0, tops)} for the frames the TOOL has not got
(the installed concept's are tools/bbcourse.py's own, named in CONCEPTS alone), and BASE, the concept the course
ships with.  `crystal` is always there as the baseline.  The cache (CLOCKKIT_CACHE, default clocks/cache/) is
scratch: the scratch course files and the compiles' pictures go there and are not committed."""
import json
import os
import re
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(KIT, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
PALS = {1: ((0, 0, 0), (85, 255, 255), (255, 85, 255), (255, 255, 255)),       # the CGA's palette 1, high
        0: ((0, 0, 0), (85, 255, 85), (255, 85, 85), (255, 255, 85))}          # ...and palette 0 (KITE's)
CW, CH, Z = 104, 96, 3                               # a crop round each clock, game px, and its zoom


def install(B, F):
    """add frames.py's scratch frames to bbcourse's styles, in THIS process only"""
    for name, fn in F.DRAW.items():
        B._CLOCK_DRAW[name] = (lambda f: lambda p, x0, y0, tops: f(B, p, x0, y0, tops))(fn)
    B.CLOCK_STYLES = tuple(B.CLOCK_STYLES) + tuple(n for n in F.DRAW if n not in B.CLOCK_STYLES)


def _clauses(F, concept, nclk):
    return [("crystal", "")] * nclk if concept == "crystal" else F.CONCEPTS[concept]


def scratch(cfg, F, concept):
    """the course file with CONCEPT's frames on its clocks -> (path in the cache, the frames' names)"""
    src = open(cfg["course"]).read()
    n = len(re.findall(r"^clock \d+ \d+", src, flags=re.M))
    it = iter(_clauses(F, concept, n))

    def sub(m):
        nm, extra = next(it)
        return "clock %s %s%s%s%s" % (m.group(1), m.group(2), "" if nm == "crystal" else " frame " + nm,
                                      " " + extra if extra else "", m.group(3))
    out = re.sub(r"^clock (\d+) (\d+)[^#\n]*?(\s*(?:#.*)?)$", sub, src, flags=re.M)
    os.makedirs(cfg["cache"], exist_ok=True)
    path = os.path.join(cfg["cache"], "%s-%s.bbc" % (cfg["name"], concept))
    open(path, "w").write(out)
    return path, [nm for nm, _e in _clauses(F, concept, n)]


def sizes(B, c):
    """a compile's sizes -> (lines, {"part", "masks", "records", "blocks", "lz4", "lzb"})"""
    sh = c.sstored or [c.stored]
    allp = list(sh) + ([c.wstored] if getattr(c, "wstored", None) else [])
    d = {"part": len(c.cga), "masks": len(c.masks), "records": len(c.records), "blocks": len(c.blocks),
         "lz4": sum(B.packed_len(s, "lz4") for s in allp), "lzb": sum(B.packed_len(s, "lzb") for s in allp)}
    return ["blocks %d; occluder masks %d (of 256), records %d" % (d["blocks"], d["masks"], d["records"]),
            "one part, %d bytes in RAM (%d under 65,024)" % (d["part"], 65024 - d["part"]),
            "on disk: LZ4 %d, LZB %d" % (d["lz4"], d["lzb"])], d


def run(args):
    cfg, concept = args
    import bbcourse as B
    F = _frames(cfg)
    install(B, F)
    path, names = scratch(cfg, F, concept)
    txt = os.path.join(cfg["here"], "%s.txt" % concept)
    try:
        c = B.compile_course(path)
    except B.CourseError as e:
        open(txt, "w").write("%s: %s\nREFUSED: %s\n" % (concept, ", ".join(names), e))
        return "%s REFUSED: %s" % (concept, e)
    lines, d = sizes(B, c)
    lines.insert(0, "%s: %s" % (concept, ", ".join(names)))
    clocks = [{"at": list(p["at"]), "z4": p["z4"], "ndig": p["ndig"], "place": p["place"],
               "frame": p.get("frame"), "digits": list(p.get("digits") or (0, 0)), "ink": p.get("ink", B.BLK)}
              for p in c.props if p.get("ndig")]
    vis = B.clock_vis(c)
    lines.append("the longest wholly-hidden run behind each clock (bound %d gu): %s" % (
        B.CLOCK_HIDE, ", ".join(str(v[4]) for v in vis)))
    json.dump({"names": names, "lines": lines, "sizes": d, "x0": c.x0, "y0": c.y0, "width": c.width,
               "height": c.lines, "pic": [bytes(r).hex() for r in c.pic], "clocks": clocks},
              open(os.path.join(cfg["cache"], "%s.json" % concept), "w"))
    open(txt, "w").write("\n".join(lines) + "\n")
    return "\n".join(lines)


def load(cfg, concept):
    """the cached compile, "47" put into every clock's digits' blocks (the lanes' poses the picture leaves plain)"""
    import bbcourse as B
    d = json.load(open(os.path.join(cfg["cache"], "%s.json" % concept)))
    pic = [bytearray(bytes.fromhex(r)) for r in d["pic"]]
    for p in d["clocks"]:
        q = dict(p, at=tuple(p["at"]), digits=tuple(p["digits"]))
        bx, by = B.clock_digit_block(q, d["x0"], d["y0"])
        _a, _b, nx, ny = B.clock_anchor(q) or (0, 0, 0, 0)
        for (x, y) in B.clock_glyph(4 if p["place"] else 7, bx, by, nx, ny):
            pic[y][x] = p.get("ink", B.BLK)
    return d, pic


def crop(B, pic, d, x0, y0, w, h, card, pal=1):
    from PIL import Image
    W_, H_ = d["width"], d["height"]

    def px(x, y):
        return pic[y][x] if 0 <= x < W_ and 0 <= y < H_ else B.BLK
    if card == "cga":
        im = Image.new("RGB", (w, h))
        im.putdata([PALS[pal][px(x, y)] for y in range(y0, y0 + h) for x in range(x0, x0 + w)])
        return im
    im = Image.new("L", (2 * w, h))
    im.putdata([255 * b for y in range(y0, y0 + h) for x in range(x0, x0 + w)
                for pr in (B.herc_pair(px(x, y), y, x),) for b in (pr >> 1, pr & 1)])
    return im.convert("RGB")


def centre(p, d):
    wx, wy = p["at"]
    return 16 * (wx - wy) + d["x0"], 8 * (wx + wy) + 8 - p["z4"] + d["y0"]


def overview(cfg, concepts, card):
    """clocks/overview-<card>.png: a row a position, a column a concept, each clock cropped out of its compile"""
    import bbcourse as B
    from PIL import Image, ImageDraw
    cols = []
    for concept in concepts:
        d, pic = load(cfg, concept)
        col = []
        for p in [q for q in d["clocks"] if q["place"] == 0]:
            cx, cy = centre(p, d)
            im = crop(B, pic, d, cx - CW // 2, cy - 30 - CH // 2, CW, CH, card, cfg["palette"])
            col.append(im.resize((CW * Z, CH * Z), Image.NEAREST))
        cols.append(col)
    W, H, T = CW * Z, CH * Z, 22
    img = Image.new("RGB", (len(cols) * (W + 8), T + len(cfg["positions"]) * (H + 8)), (70, 70, 70))
    dr = ImageDraw.Draw(img)
    for i, col in enumerate(cols):
        dr.text((i * (W + 8) + 6, 5), concepts[i], fill=(255, 255, 255))
        for j, im in enumerate(col):
            img.paste(im, (i * (W + 8), T + j * (H + 8)))
            dr.text((i * (W + 8) + 6, T + j * (H + 8) + 4), cfg["positions"][j], fill=(255, 255, 0))
    out = os.path.join(cfg["here"], "overview-%s.png" % card)
    img.save(out)
    return out


def preview_cell(B, name, extra, pal):
    """one frame on a plain block's top, no compile -> (CGA, Hercules) images, zoomed"""
    from PIL import Image
    W, H, Zp = 96, 104, 3
    p = {"at": (0, 0), "z4": 0, "ndig": 2, "frame": name}
    m = re.search(r"digits (-?\d+) (-?\d+)", extra or "")
    if m:
        p["digits"] = (int(m.group(1)), int(m.group(2)))
    x0, y0 = 48, 80
    pic = [[B.BLK] * W for _ in range(H)]
    cx, cy = x0, 8 + y0
    for y in range(H):                              # the block: a top diamond and its two faces
        for x in range(W):
            dd = abs(x + 0.5 - cx) / 16.0 + abs(y + 0.5 - cy) / 8.0
            if dd <= 1.0:
                pic[y][x] = (B.WHT if dd < 0.93 else B.BLK)
            elif abs(x + 0.5 - cx) <= 16 and cy < y <= cy + 14 + (16 - abs(x + 0.5 - cx)) / 2.0:
                pic[y][x] = B.MAG if x < cx else (B.MAG if (x + y) & 1 else B.BLK)
    for (x, y), v in B.clock_face_pix(p, x0, y0).items():
        if 0 <= x < W and 0 <= y < H:
            pic[y][x] = v
    for place, dgt in ((1, 4), (0, 7)):
        q = dict(p, place=place)
        bx, by = B.clock_digit_block(q, x0, y0)
        _a, _b, nx, ny = B.clock_anchor(q) or (0, 0, 0, 0)
        for (x, y) in B.clock_glyph(dgt, bx, by, nx, ny):
            if 0 <= x < W and 0 <= y < H:
                pic[y][x] = B.WHT if "ink white" in (extra or "") else B.BLK
    cga = Image.new("RGB", (W, H))
    cga.putdata([PALS[pal][v] for r in pic for v in r])
    herc = Image.new("L", (2 * W, H))
    herc.putdata([255 * b for y, r in enumerate(pic) for x, v in enumerate(r)
                  for pr in (B.herc_pair(v, y, x),) for b in (pr >> 1, pr & 1)])
    return (cga.resize((W * Zp, H * Zp), Image.NEAREST),
            herc.convert("RGB").resize((W * Zp, H * Zp), Image.NEAREST))


def preview(cfg, concepts, out=None):
    """clocks/frames.png: every frame of CONCEPTS on a plain block, a row a concept (CGA over Hercules)"""
    import bbcourse as B
    from PIL import Image, ImageDraw
    F = _frames(cfg)
    install(B, F)
    rows = []
    for c in concepts:
        cells = [preview_cell(B, nm, ex, cfg["palette"]) for nm, ex in F.CONCEPTS[c]]
        rows.append((c, [a for a, _b in cells]))
        rows.append((c + " (Hercules)", [b for _a, b in cells]))
    w, h = rows[0][1][0].size
    ncol = max(len(r) for _c, r in rows)
    img = Image.new("RGB", (ncol * (w + 6), len(rows) * (h + 6)), (60, 60, 60))
    dr = ImageDraw.Draw(img)
    for j, (cap, ims) in enumerate(rows):
        for i, im in enumerate(ims):
            img.paste(im, (i * (w + 6), j * (h + 6)))
        dr.text((4, j * (h + 6) + 3), cap, fill=(255, 255, 0))
    out = out or os.path.join(cfg["here"], "frames.png")
    img.save(out)
    return out


def outline(cfg):
    """a fast PROXY for what a frame costs the occluder masks (no compile): its geometry's width, the blocks it
    touches and how many it covers only partly"""
    import bbcourse as B
    F = _frames(cfg)
    install(B, F)
    names = [("crystal", "")] + [v for vs in F.CONCEPTS.values() for v in vs]
    for nm, ex in names:
        tops = {}
        p = {"at": (0, 0), "z4": 0, "ndig": 2, "frame": nm}
        m = re.search(r"digits (-?\d+) (-?\d+)", ex or "")
        if m:
            p["digits"] = (int(m.group(1)), int(m.group(2)))
        B.clock_face_pix(p, 64, 96, tops=tops)
        blocks = {}
        for (x, y) in tops:
            blocks.setdefault((x >> 3, y >> 3), set()).add((x & 7, y & 7))
        xs, ys = [x for x, _y in tops], [y for _x, y in tops]
        print("%-8s geometry px %4d, %2d x %2d, blocks %2d, partly covered %2d" % (
            nm, len(tops), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, len(blocks),
            sum(1 for s in blocks.values() if len(s) < 64)))


def _frames(cfg):
    if cfg["here"] not in sys.path:
        sys.path.insert(0, cfg["here"])
    import importlib
    return importlib.import_module("frames")


def main(course, palette, positions, here=None):
    here = here or os.path.join(KIT, course, "clocks")
    cfg = {"name": course, "palette": palette, "positions": positions, "here": here,
           "course": os.path.join(ROOT, "apps", "bonanza", "courses", course + ".bbc"),
           "cache": os.environ.get("CLOCKKIT_CACHE") or os.path.join(here, "cache")}
    F = _frames(cfg)
    order = ["crystal"] + list(F.CONCEPTS)
    args = sys.argv[1:]
    if args[:1] == ["--preview"]:
        print(preview(cfg, args[1:] or list(F.CONCEPTS)))
        return
    if args[:1] == ["--outline"]:
        outline(cfg)
        return
    if args[:1] != ["--overview"]:
        from multiprocessing import Pool
        cs = args or order
        with Pool(min(len(cs), int(os.environ.get("JOBS", "3")))) as pool:
            for r in pool.imap_unordered(run, [(cfg, c) for c in cs]):
                print(r, flush=True)
        args = []
    else:
        args = args[1:]
    cs = [c for c in (args or order) if os.path.exists(os.path.join(cfg["cache"], "%s.json" % c))]
    for card in ("cga", "herc"):
        print(overview(cfg, cs, card))
