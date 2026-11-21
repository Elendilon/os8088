#!/usr/bin/env python3
"""WINDMILL LANE's clock OPTIONS, compiled and drawn (host only, nothing in `make` runs it).  DOWNHILL DECISION's
sheet (../../down/clocks/sheet.py) is the precedent; this one reads the course, apps/bonanza/courses/mill.bbc
(the scratch draft ../mill-draft.bbc until it shipped, 2026-11-21: SPEC.md 130.54.10).

    python3 docs/plans/bonanza-courses/mill/clocks/sheet.py [CONCEPT ...]
        for each concept (frames.py's CONCEPTS; `crystal` is the draft's default frame, the baseline): writes a
        SCRATCH copy of the course with its three `frame`s (clocks/mill-<concept>.bbc), compiles it with
        frames.py's styles installed IN THIS PROCESS (the tool on disk is not changed), and writes
        clocks/<concept>.png - each clock's crop of the course's real picture, CGA beside Hercules - and
        clocks/<concept>.txt, the part's sizes (RAM, stored, LZ4 and LZB packed, the block pool, the occluder
        masks).  One process a concept (a compile is about 2.5 minutes)
    python3 docs/plans/bonanza-courses/mill/clocks/sheet.py --render [CONCEPT ...]
        the pictures again from the compiles' cache (clocks/cache/, not committed), in seconds
    python3 docs/plans/bonanza-courses/mill/clocks/sheet.py --overview [CONCEPT ...]
        clocks/overview-cga.png and overview-herc.png: a row a position, a column a concept"""
import json
import os
import re
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
COURSE = os.path.join(ROOT, "apps", "bonanza", "courses", "mill.bbc")
CACHE = os.path.join(HERE, "cache")              # (the compiles' pictures: not committed)
CW, CH, Z = 200, 130, 3                         # a crop round each clock, game px, and its zoom
POSITIONS = ("start", "turntable", "finish")


def scratch(concept):
    import frames as F
    src = open(COURSE).read()
    names = [n for n, _a in F.CONCEPTS[concept]] if concept != "crystal" else ["crystal"] * 3
    it = iter(names)

    def sub(m):
        nm = next(it)
        return "clock %s %s%s%s" % (m.group(1), m.group(2), "" if nm == "crystal" else " frame " + nm, m.group(3))
    out = re.sub(r"^clock (\d+) (\d+)(\s*(?:#.*)?)$", sub, src, flags=re.M)
    path = os.path.join(HERE, "mill-%s.bbc" % concept)
    open(path, "w").write(out)
    return path, names


def run(concept):
    import bbcourse as B
    import frames as F
    F.install(B)
    path, names = scratch(concept)
    try:
        c = B.compile_course(path)
    except B.CourseError as e:
        open(os.path.join(HERE, "%s.txt" % concept), "w").write("REFUSED: %s\n" % e)
        return "%s REFUSED: %s" % (concept, e)
    lines = ["%s: %s" % (concept, ", ".join(names))]
    lines.append("blocks %d of 1,024 (the picture's pool); occluder masks %d (of 256), records %d" % (
        len(c.blocks), len(c.masks), len(c.records)))
    sh = c.sstored or [c.stored]
    plan = c.plan or {}
    if c.sstored:
        lines.append("sheets %d of %s block rows from rows %s; each sheet %d bytes in RAM" % (
            len(sh), plan.get("n"), [x["m0"] for x in plan.get("sheets", [])], len(c.cga)))
    else:
        lines.append("one part, %d bytes in RAM (%d under 65,024)" % (len(c.cga), 65024 - len(c.cga)))
    for i, s in enumerate(sh):
        lines.append("part %d stored %d, LZ4 %d, LZB %d" % (i, len(s), B.packed_len(s, "lz4"),
                                                             B.packed_len(s, "lzb")))
    if getattr(c, "wstored", None):
        lines.append("world part %d in RAM, stored %d, LZ4 %d, LZB %d" % (
            len(c.wcga), len(c.wstored), B.packed_len(c.wstored, "lz4"), B.packed_len(c.wstored, "lzb")))
    allp = list(sh) + ([c.wstored] if getattr(c, "wstored", None) else [])
    lines.append("on disk, every part: LZ4 %d, LZB %d" % (sum(B.packed_len(s, "lz4") for s in allp),
                                                         sum(B.packed_len(s, "lzb") for s in allp)))
    clocks = [{"at": list(p["at"]), "z4": p["z4"], "ndig": p["ndig"], "place": p["place"]}
              for p in c.props if p.get("ndig")]
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"names": names, "lines": lines, "x0": c.x0, "y0": c.y0, "width": c.width, "height": c.lines,
               "pic": [bytes(r).hex() for r in c.pic], "clocks": clocks},
              open(os.path.join(CACHE, "%s.json" % concept), "w"))
    return render(concept)


def _load(concept):
    """the cached compile, with "47" put into every clock's digits' blocks (the lanes' poses, which the static
    picture leaves plain)"""
    import bbcourse as B
    d = json.load(open(os.path.join(CACHE, "%s.json" % concept)))
    pic = [bytearray(bytes.fromhex(r)) for r in d["pic"]]
    for p in d["clocks"]:                           # "47": the tens 4, the units 7
        bx, by = B.clock_digit_block(dict(p, at=tuple(p["at"])), d["x0"], d["y0"])
        for j, row in enumerate(B.CLOCK_FONT[4 if p["place"] else 7]):
            for i in range(5):
                if (row >> (4 - i)) & 1:
                    pic[8 * by + 1 + j][8 * bx + 1 + i] = B.BLK
    return d, pic


def _crop(pic, d, x0, y0, w, h, card):
    import bbcourse as B
    from PIL import Image
    W_, H_ = d["width"], d["height"]

    def px(x, y):
        return pic[y][x] if 0 <= x < W_ and 0 <= y < H_ else B.BLK
    if card == "cga":
        im = Image.new("RGB", (w, h))
        im.putdata([B.CGA1[px(x, y)] for y in range(y0, y0 + h) for x in range(x0, x0 + w)])
        return im
    im = Image.new("L", (2 * w, h))
    im.putdata([255 * b for y in range(y0, y0 + h) for x in range(x0, x0 + w)
                for pr in (B.herc_pair(px(x, y), y, x),) for b in (pr >> 1, pr & 1)])
    return im.convert("RGB")


def _centre(p, d):
    wx, wy = p["at"]
    return 16 * (wx - wy) + d["x0"], 8 * (wx + wy) + 8 - p["z4"] + d["y0"]


def render(concept):
    """the picture sheet from the compile's cache: each clock's crop, CGA beside Hercules"""
    import bbcourse as B
    from PIL import Image
    d, pic = _load(concept)
    lines = list(d["lines"])
    tiles = []
    for p, nm in zip([q for q in d["clocks"] if q["place"] == 0], d["names"]):
        cx, cy = _centre(p, d)
        lines.append("clock at (%d, %d), frame %s: its tile's centre at canvas (%d, %d), its digits in block row "
                     "%d" % (p["at"][0], p["at"][1], nm, cx, cy,
                             B.clock_digit_block(dict(p, at=tuple(p["at"])), d["x0"], d["y0"])[1]))
        x0, y0 = cx - CW // 2, cy - 20 - CH // 2
        tiles.append((_crop(pic, d, x0, y0, CW, CH, "cga").resize((CW * Z, CH * Z), Image.NEAREST),
                      _crop(pic, d, x0, y0, CW, CH, "herc").resize((CW * Z, CH * Z), Image.NEAREST)))
    W, H = CW * Z, CH * Z
    img = Image.new("RGB", (2 * W + 12, len(tiles) * (H + 12)), (70, 70, 70))
    for i, (a, b) in enumerate(tiles):
        img.paste(a, (0, i * (H + 12)))
        img.paste(b, (W + 12, i * (H + 12)))
    img.save(os.path.join(HERE, "%s.png" % concept))
    open(os.path.join(HERE, "%s.txt" % concept), "w").write("\n".join(lines) + "\n")
    return "\n".join(lines)


def overview(concepts, card):
    """clocks/overview-<card>.png: a row a position, a column a concept, a tight crop of each (from the cache)"""
    from PIL import Image
    cw, ch, z = 96, 88, 3
    cols = []
    for concept in concepts:
        d, pic = _load(concept)
        col = []
        for p in [q for q in d["clocks"] if q["place"] == 0]:
            cx, cy = _centre(p, d)
            col.append(_crop(pic, d, cx - cw // 2, cy - 24 - ch // 2, cw, ch, card).resize((cw * z, ch * z),
                                                                                          Image.NEAREST))
        cols.append(col)
    from PIL import ImageDraw
    W, H, T = cw * z, ch * z, 22                    # T: a caption strip, each column's concept
    img = Image.new("RGB", (len(cols) * (W + 8), T + len(POSITIONS) * (H + 8)), (70, 70, 70))
    dr = ImageDraw.Draw(img)
    for i, col in enumerate(cols):
        dr.text((i * (W + 8) + 6, 5), concepts[i], fill=(255, 255, 255))
        for j, im in enumerate(col):
            img.paste(im, (i * (W + 8), T + j * (H + 8)))
    img.save(os.path.join(HERE, "overview-%s.png" % card))


ORDER = ("crystal", "mill", "body", "side", "wheel", "hub", "post", "vase", "flag")     # round 2's beside its parent


def _all():
    import frames as F
    return [c for c in ORDER if c == "crystal" or c in F.CONCEPTS] + [c for c in F.CONCEPTS if c not in ORDER]


if __name__ == "__main__":
    if sys.argv[1:2] == ["--overview"]:             # every concept at every position, one sheet a card
        cs = sys.argv[2:] or _all()
        overview(cs, "cga")
        overview(cs, "herc")
        sys.exit(0)
    args = sys.argv[1:]
    fn = run
    if args[:1] == ["--render"]:                    # the pictures again from the compiles' cache, in seconds
        fn, args = render, args[1:]
    cs = args or _all()
    with Pool(min(len(cs), int(os.environ.get("JOBS", "4")))) as pool:
        for r in pool.imap_unordered(fn, cs):
            print(r, flush=True)
