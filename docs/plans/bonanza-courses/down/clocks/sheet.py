#!/usr/bin/env python3
"""DOWNHILL DECISION's clock OPTIONS, compiled and drawn (host only, nothing in `make` runs it).

    python3 docs/plans/bonanza-courses/down/clocks/sheet.py [CONCEPT ...]
        for each concept (sign, orb, peng, watch; `crystal` is today's baseline): writes a SCRATCH copy of
        apps/bonanza/courses/down.bbc with its four `frame`s (clocks/down-<concept>.bbc), compiles it with
        frames.py's styles installed IN THIS PROCESS (the tool on disk is not changed), and writes
        clocks/<concept>.png - each clock's crop of the course's real picture, CGA beside Hercules - and
        clocks/<concept>.txt, the part sizes (every sheet's RAM and stored bytes, LZB-packed, the world
        part, the block pool, the occluder masks).  Each concept runs in its own process (a compile is minutes)
    python3 docs/plans/bonanza-courses/down/clocks/sheet.py --render [CONCEPT ...]
        the pictures again from the compiles' cache (clocks/cache/), in seconds
    python3 docs/plans/bonanza-courses/down/clocks/sheet.py --overview [CONCEPT ...]
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
COURSE = os.path.join(ROOT, "apps", "bonanza", "courses", "down.bbc")
CACHE = os.path.join(HERE, "cache")              # (the compiles' pictures: not committed)
CW, CH, Z = 200, 130, 3                         # a crop round each clock, game px, and its zoom


def scratch(concept):
    import frames as F
    src = open(COURSE).read()
    names = [n for n, _a in F.CONCEPTS[concept]] if concept != "crystal" else ["crystal"] * 4
    it = iter(names)
    out = re.sub(r"^clock (\d+) (\d+)\s*$", lambda m: "clock %s %s frame %s" % (m.group(1), m.group(2), next(it)),
                 src, flags=re.M)
    path = os.path.join(HERE, "down-%s.bbc" % concept)
    open(path, "w").write(out)
    return path, names


def run(concept):
    import bbcourse as B
    import frames as F
    from PIL import Image
    F.install(B)
    path, names = scratch(concept)
    try:
        c = B.compile_course(path)
    except B.CourseError as e:
        open(os.path.join(HERE, "%s.txt" % concept), "w").write("REFUSED: %s\n" % e)
        return "%s REFUSED: %s" % (concept, e)
    lines = ["%s: %s" % (concept, ", ".join(names))]
    lines.append("blocks %d (the picture's pool); occluder masks %d (of 256), records %d" % (
        len(c.blocks), len(c.masks), len(c.records)))
    sh = c.sstored or [c.stored]
    plan = c.plan or {}
    lines.append("sheets %d of %s block rows from rows %s; each sheet %d bytes in RAM" % (
        len(sh), plan.get("n"), [x["m0"] for x in plan.get("sheets", [])], len(c.cga)))
    for i, s in enumerate(sh):
        lines.append("sheet %d stored %d, LZB %d" % (i, len(s), B.packed_len(s, "lzb")))
    if getattr(c, "wstored", None):
        lines.append("world part %d in RAM, stored %d, LZB %d" % (len(c.wcga), len(c.wstored),
                                                                    B.packed_len(c.wstored, "lzb")))
    clocks = [{"at": list(p["at"]), "z4": p["z4"], "ndig": p["ndig"], "place": p["place"]}
              for p in c.props if p.get("ndig")]
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"names": names, "lines": lines, "x0": c.x0, "y0": c.y0, "width": c.width, "height": c.lines,
               "pic": [bytes(r).hex() for r in c.pic], "clocks": clocks},
              open(os.path.join(CACHE, "%s.json" % concept), "w"))
    return render(concept)


def render(concept):
    """the picture sheet from the compile's cache: each clock's crop with "47" in its digits' blocks (the
    lanes' poses, which the static picture leaves plain), CGA beside Hercules"""
    import bbcourse as B
    from PIL import Image
    d = json.load(open(os.path.join(CACHE, "%s.json" % concept)))
    pic = [bytearray(bytes.fromhex(r)) for r in d["pic"]]
    W_, H_ = d["width"], d["height"]
    lines = list(d["lines"])
    for p in d["clocks"]:                           # "47": the tens 4, the units 7
        bx, by = B.clock_digit_block(dict(p, at=tuple(p["at"])), d["x0"], d["y0"])
        for j, row in enumerate(B.CLOCK_FONT[4 if p["place"] else 7]):
            for i in range(5):
                if (row >> (4 - i)) & 1:
                    pic[8 * by + 1 + j][8 * bx + 1 + i] = B.BLK
    tiles = []
    for p, nm in zip([q for q in d["clocks"] if q["place"] == 0], d["names"]):
        wx, wy = p["at"]
        cx = 16 * (wx - wy) + d["x0"]
        cy = 8 * (wx + wy) + 8 - p["z4"] + d["y0"]
        lines.append("clock at (%d, %d), frame %s: its tile's centre at canvas (%d, %d), its digits in block row "
                     "%d" % (wx, wy, nm, cx, cy, B.clock_digit_block(dict(p, at=(wx, wy)), d["x0"], d["y0"])[1]))
        x0, y0 = max(0, min(W_ - CW, cx - CW // 2)), max(0, min(H_ - CH, cy - 20 - CH // 2))
        cga = Image.new("RGB", (CW, CH))
        cga.putdata([B.CGA1[pic[y][x]] for y in range(y0, y0 + CH) for x in range(x0, x0 + CW)])
        herc = Image.new("L", (2 * CW, CH))
        herc.putdata([255 * b for y in range(y0, y0 + CH) for x in range(x0, x0 + CW)
                      for pr in (B.herc_pair(pic[y][x], y, x),) for b in (pr >> 1, pr & 1)])
        tiles.append((cga.resize((CW * Z, CH * Z), Image.NEAREST),
                      herc.convert("RGB").resize((CW * Z, CH * Z), Image.NEAREST)))
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
    import bbcourse as B
    from PIL import Image
    cw, ch, z = 96, 84, 3
    cols = []
    for concept in concepts:
        d = json.load(open(os.path.join(CACHE, "%s.json" % concept)))
        pic = [bytearray(bytes.fromhex(r)) for r in d["pic"]]
        for p in d["clocks"]:
            bx, by = B.clock_digit_block(dict(p, at=tuple(p["at"])), d["x0"], d["y0"])
            for j, row in enumerate(B.CLOCK_FONT[4 if p["place"] else 7]):
                for i in range(5):
                    if (row >> (4 - i)) & 1:
                        pic[8 * by + 1 + j][8 * bx + 1 + i] = B.BLK
        col = []
        for p in [q for q in d["clocks"] if q["place"] == 0]:
            wx, wy = p["at"]
            cx = 16 * (wx - wy) + d["x0"]
            cy = 8 * (wx + wy) + 8 - p["z4"] + d["y0"]
            x0, y0 = cx - cw // 2, cy - 22 - ch // 2
            if card == "cga":
                im = Image.new("RGB", (cw, ch))
                im.putdata([B.CGA1[pic[y][x]] for y in range(y0, y0 + ch) for x in range(x0, x0 + cw)])
            else:
                im = Image.new("L", (2 * cw, ch))
                im.putdata([255 * b for y in range(y0, y0 + ch) for x in range(x0, x0 + cw)
                            for pr in (B.herc_pair(pic[y][x], y, x),) for b in (pr >> 1, pr & 1)])
                im = im.convert("RGB")
            col.append(im.resize((cw * z, ch * z), Image.NEAREST))
        cols.append(col)
    W, H = cw * z, ch * z
    img = Image.new("RGB", (len(cols) * (W + 8), 4 * (H + 8)), (70, 70, 70))
    for i, col in enumerate(cols):
        for j, im in enumerate(col):
            img.paste(im, (i * (W + 8), j * (H + 8)))
    img.save(os.path.join(HERE, "overview-%s.png" % card))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--overview"]:             # every concept at every position, one sheet a card
        cs = sys.argv[2:] or ["crystal", "sign", "orb", "peng", "watch"]
        overview(cs, "cga")
        overview(cs, "herc")
        sys.exit(0)
    args = sys.argv[1:]
    fn = run
    if args[:1] == ["--render"]:                    # the pictures again from the compiles' cache, in seconds
        fn, args = render, args[1:]
    cs = args or ["crystal", "sign", "orb", "peng", "watch"]
    with Pool(len(cs)) as pool:
        for r in pool.imap_unordered(fn, cs):
            print(r, flush=True)
