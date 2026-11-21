"""Mockups for Bounce Bonanza's column/floor junction cues.

Hooks tools/bbcourse.py's render(): every face pixel remembers its cell and
whether that face hangs over the VOID (a gap) or over a neighbour record
(joined). After the picture is drawn, each face's visible FOOT (its lowest
visible pixel in a column, with a floor top directly under it) is restyled.

usage (from the repository root):
    python3 docs/plans/bonanza-courses/edges/edges.py OUTDIR STYLE COURSE.bbc...
STYLE: none, or "+"-joined words: seamless plinth sill heavy (joined feet),
    dissolve void teeth stripe measured (gap feet). Never writes the compile cache.
"""
import sys, os
sys.path.insert(0, "tools")
import bbcourse as B
from bonanza_assets import BLK, CYN, MAG, WHT, CGA1

STYLE = "none"
VOID = set()
NEIGH = {}
FACEK = ("sw", "se", "front")

_orig_fill = B.Canvas.fill


def fill(self, sp, colour, s, top, owner=-1):
    _orig_fill(self, sp, colour, s, top, owner)
    if not hasattr(self, "kb"):
        self.kb = [bytearray(self.w) for _ in range(self.h)]
        self.ob2 = [[-1] * self.w for _ in range(self.h)]
        self.wb = [bytearray(self.w) for _ in range(self.h)]
    w = self.lwhich
    wc = {"sw": 1, "se": 2}.get(w, 0)
    if w in FACEK:
        k = 2 if (owner, w) in VOID else 1
    elif w == "post":
        k = 0
    else:
        k = 3
    for y, runs in sp.items():
        kr, orow, wr = self.kb[y], self.ob2[y], self.wb[y]
        for a, b in runs:
            for x in range(a, b):
                wr[x] = wc
                kr[x] = k
                orow[x] = owner


B.Canvas.fill = fill
_orig_render = B.render

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def feet(cv):
    """-> [(x, yfoot, kind 1 joined / 2 gap, face owner)] where a face's pixel has a
    floor TOP of another cell directly under it"""
    out = []
    kb, ob = cv.kb, cv.ob2
    for y in range(cv.h - 1):
        for x in range(cv.w):
            k = kb[y][x]
            if k in (1, 2) and kb[y + 1][x] == 3 and ob[y + 1][x] != ob[y][x]:
                if k == 1 and ob[y + 1][x] not in NEIGH.get(ob[y][x], ()):
                    k = 2                            # cut by something nearer that it does not touch: a gap
                out.append((x, y, k, ob[y][x]))
    return out


def up(cv, x, y, n, own):
    """the face pixels at and above (x, y) of the same face, at most n"""
    r = []
    while n and y >= 0 and cv.ob2[y][x] == own and cv.kb[y][x] in (1, 2):
        r.append(y)
        y -= 1
        n -= 1
    return r


XY0 = (0, 0)


def gapcells(cv, x, y, own):
    """how many cells of void lie between the face at (x, y) and the top under it"""
    wc = cv.wb[y][x]
    if not wc:
        return None
    x0, y0 = XY0
    z = cv.tbuf[y + 1][x]
    a = x + 0.5 - x0
    b = 2 * (y + 1 - y0 + 0.5 + z)
    gx, gy = (a + b) / 2.0, (b - a) / 2.0
    wx, wy = own >> 8, own & 255
    d = gy - 16 * (wy + 1) if wc == 1 else gx - 16 * (wx + 1)
    return max(0, int(d // 16))


def style(cv):
    rows = cv.rows
    ft = feet(cv)
    S = STYLE.split("+")
    for x, y, k, own in ft:
        if k == 1:                                   # JOINED
            if "seamless" in S:
                if rows[y + 1][x] == BLK and y + 2 < cv.h and rows[y + 2][x] != BLK and cv.ob2[y + 2][x] == cv.ob2[y + 1][x]:
                    rows[y + 1][x] = rows[y + 2][x]
            if "plinth" in S:                        # a cyan skirting, 2 px, on the face
                for i, yy in enumerate(up(cv, x, y, 2, own)):
                    rows[yy][x] = CYN
            if "sill" in S:                          # a 1 px white line on the face's foot
                for yy in up(cv, x, y, 1, own):
                    rows[yy][x] = WHT
            if "heavy" in S:                         # the joint drawn 2 px
                for yy in up(cv, x, y, 1, own):
                    rows[yy][x] = BLK
        else:                                        # a GAP
            if "dissolve" in S:
                for kk, yy in enumerate(up(cv, x, y, 8, own)):
                    if BAYER[yy & 3][x & 3] < 16 - 2 * kk:
                        rows[yy][x] = BLK
            if "void" in S:
                for yy in up(cv, x, y, 3, own):
                    rows[yy][x] = BLK
            if "teeth" in S:
                t = abs((x % 8) - 4) + 1
                for yy in up(cv, x, y, t, own):
                    rows[yy][x] = BLK
            if "measured" in S:                      # a void band as deep as the gap is wide
                n = gapcells(cv, x, y, own)
                if n is not None:
                    for yy in up(cv, x, y, min(7, 1 + 2 * n), own):
                        rows[yy][x] = BLK
            if "stripe" in S:                        # a void band with a dither fringe over it
                for kk, yy in enumerate(up(cv, x, y, 5, own)):
                    if kk < 2 or (kk < 4 and (x + yy) & 1):
                        rows[yy][x] = BLK
    return cv


def render(tiles, ops, x0, y0, w, h, owners=False):
    global VOID, NEIGH
    VOID = set()
    NEIGH = {}
    for _key, (wx, wy), t, hh, s, ent, faces in B._cell_faces(tiles):
        for f in faces:
            if f[4] is None:
                VOID.add((256 * wx + wy, f[5]))
            n = {"sw": (wx, wy + 1), "se": (wx + 1, wy)}.get(f[5])
            if n:
                NEIGH.setdefault(256 * wx + wy, set()).add(256 * n[0] + n[1])
    global XY0
    XY0 = (x0, y0)
    cv = _orig_render(tiles, ops, x0, y0, w, h, owners)
    if hasattr(cv, "kb") and STYLE != "none":
        style(cv)
    return cv


B.render = render
B.cache_get = lambda key: None
B.cache_put = lambda *a, **k: None


def main():
    global STYLE
    out, STYLE = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    from PIL import Image
    for path in sys.argv[3:]:
        c = B.compile_course(path, occluders=False)
        img = Image.new("RGB", (c.width, c.lines))
        img.putdata([CGA1[v] for r in c.pic for v in r])
        img.save(os.path.join(out, "%s-%s.png" % (c.name.lower(), STYLE)))
        h = Image.new("L", (c.width * 2, c.lines))
        data = []
        for y, row in enumerate(c.pic):
            for x, v in enumerate(row):
                pr = B.herc_pair(v, y, x)
                data += [255 * (pr >> 1), 255 * (pr & 1)]
        h.putdata(data)
        h.save(os.path.join(out, "%s-%s-herc.png" % (c.name.lower(), STYLE)))


if __name__ == "__main__":
    main()


def diag(path, out):
    """the feet: joined green, gap red"""
    global STYLE
    STYLE = "none"
    from PIL import Image
    got = {}
    o = B.render

    def r2(*a, **k):
        cv = o(*a, **k)
        got.setdefault("cv", cv)
        return cv
    B.render = r2
    c = B.compile_course(path, occluders=False)
    B.render = o
    img = Image.new("RGB", (c.width, c.lines))
    img.putdata([CGA1[v] for r in c.pic for v in r])
    px = img.load()
    cv = got["cv"]
    dy = c.lines - cv.h
    n = [0, 0, 0]
    for x, y, k, own in feet(cv):
        n[k] += 1
        if 0 <= y + 1 + dy < c.lines:
            px[x, y + 1 + dy] = (0, 200, 0) if k == 1 else (255, 0, 0)
    img.save(out)
    print(path, "joined", n[1], "gap", n[2], "cv.h", cv.h, "lines", c.lines)
