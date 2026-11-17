import sys, collections, colorsys, hashlib
from PIL import Image, ImageDraw
W = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "../../../.."))
sys.path.insert(0, W + "/tools")
import bbcourse as B
VOID = -32768
c = B.compile_course(W + "/apps/bonanza/courses/summit.bbc")
X0, Y0, CW, CH, Z = 256, 368, 128, 104, 4
def kcol(key):
    h = int(hashlib.md5(repr(key).encode()).hexdigest()[:6], 16)
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, 0.75, 0.55 + (h >> 9) % 40 / 100.0)
    return (int(r*255), int(g*255), int(b*255))
def panel(fn):
    im = Image.new("RGB", (CW, CH)); P = im.load()
    for y in range(CH):
        for x in range(CW):
            P[x, y] = fn(X0 + x, Y0 + y)
    im = im.resize((CW*Z, CH*Z), Image.NEAREST); D = ImageDraw.Draw(im)
    return im, D
def grid(D, step, col):
    for gx in range((-X0) % step, CW, step): D.line([(gx*Z, 0), (gx*Z, CH*Z)], fill=col)
    for gy in range((-Y0) % step, CH, step): D.line([(0, gy*Z), (CW*Z, gy*Z)], fill=col)
pic = lambda X, Y: B.CGA1[c.pic[Y][X]]
def depth(X, Y):
    s, t = c.sbuf[Y][X], c.tbuf[Y][X]
    if s == VOID: return (15, 15, 15)
    r, g, b = colorsys.hsv_to_rgb((s * 0.137) % 1.0, 0.7, 0.35 + 0.65 * (t - 100) / 160.0)
    return (int(r*255), int(g*255), int(b*255))
rec_at = {}
for r in c.records:
    for p in r["pix"]: rec_at.setdefault(p, r)
def today(X, Y):
    r = rec_at.get((X, Y))
    if r is None:
        g = B.CGA1[c.pic[Y][X]]; return tuple(int(v * 0.18) for v in g)
    return kcol((r["s"], r["top"]))
# the 2-bit 4x4 map: per 8x8 block a palette of up to 3 (row, top) keys + "nothing"; each 4x4 tile its majority
blocks = collections.defaultdict(list)
for r in c.records: blocks[(r["brow"], r["col"])].append(r)
coarse = {}
for (br, bc), rs in blocks.items():
    for ty in range(2):
        for tx in range(2):
            cnt = collections.Counter()
            for y in range(br*8 + ty*4, br*8 + ty*4 + 4):
                for x in range(bc*8 + tx*4, bc*8 + tx*4 + 4):
                    r = rec_at.get((x, y)); cnt[(r["s"], r["top"]) if r else None] += 1
            k = cnt.most_common(1)[0][0]
            for y in range(br*8 + ty*4, br*8 + ty*4 + 4):
                for x in range(bc*8 + tx*4, bc*8 + tx*4 + 4): coarse[(x, y)] = k
def coarse4(X, Y):
    k = coarse.get((X, Y))
    if k is None:
        g = B.CGA1[c.pic[Y][X]]; return tuple(int(v * 0.18) for v in g)
    return kcol(k)
panels = [("1. The picture (PEAK, around the fall)", pic, None),
          ("2. Your model: a depth for EVERY pixel (colour = cell row, brightness = height of its top)", depth, None),
          ("3. Today: only the 8x8 blocks a reachable ball can be behind; each colour is one record (a shared 1-bit shape + one depth)", today, 8),
          ("4. Your 2-bit map at 4x4: each 4x4 tile picks one of its block's 3 depths, or nothing", coarse4, 4)]
ims = []
for title, fn, g in panels:
    im, D = panel(fn)
    if g: grid(D, 8, (90, 90, 90))
    if g == 4: grid(D, 4, (55, 55, 55)); grid(D, 8, (110, 110, 110))
    ims.append((title, im))
import textwrap
out = Image.new("RGB", (2*(CW*Z+10)+10, 2*(CH*Z+46)+10), (30, 30, 30)); D = ImageDraw.Draw(out)
for i, (t, im) in enumerate(ims):
    x, y = 10 + (i % 2)*(CW*Z+10), 10 + (i // 2)*(CH*Z+46)
    D.multiline_text((x, y), "\n".join(textwrap.wrap(t, 88)), fill=(255, 255, 255)); out.paste(im, (x, y + 34))
out.save("storage-methods.png"); print("ok")
