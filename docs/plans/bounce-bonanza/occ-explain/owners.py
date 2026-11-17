import sys, pickle, colorsys, hashlib, collections
from PIL import Image, ImageDraw
W = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "../../../.."))
sys.path.insert(0, W + "/tools")
import bbcourse as B
c = B.compile_course(W + "/apps/bonanza/courses/summit.bbc")
ob = B.owners_canvas(c)
sel = pickle.load(open("peakfall.pkl", "rb"))["sel"]
X0, Y0, CW, CH, Z = 264, 352, 136, 112, 6
K = {getattr(B, n): n[5:] for n in dir(B) if n.startswith("KIND_")}
def col(o):
    h = int(hashlib.md5(str(o).encode()).hexdigest()[:6], 16)
    r, g, b = colorsys.hsv_to_rgb((h % 1000) / 1000.0, 0.65, 0.95)
    return (int(r*255), int(g*255), int(b*255))
img = Image.new("RGB", (CW, CH)); P = img.load(); pts = collections.defaultdict(list)
for y in range(CH):
    for x in range(CW):
        X, Y = X0 + x, Y0 + y
        o = ob[Y][X]; base = B.CGA1[c.pic[Y][X]]
        if o < 0: P[x, y] = tuple(v // 5 for v in base); continue
        cc = col(o); P[x, y] = tuple(int(0.55*a + 0.45*b) for a, b in zip(cc, base)); pts[o].append((x, y))
img = img.resize((CW*Z, CH*Z), Image.NEAREST); D = ImageDraw.Draw(img)
for o, ps in pts.items():
    if len(ps) < 25: continue
    wx, wy = o >> 8, o & 255
    v = c.cells.get((wx, wy), [0, 0, 0])
    mx = sum(p[0] for p in ps) / len(ps); my = sum(p[1] for p in ps) / len(ps)
    t = "%d,%d %s h%d" % (wx, wy, K.get(v[2] & 15, "?").lower(), v[0])
    D.rectangle([mx*Z - 34, my*Z - 7, mx*Z + 34, my*Z + 7], fill=(0, 0, 0)); D.text((mx*Z - 32, my*Z - 6), t, fill=(255, 255, 255))
for i, st in enumerate([sel[0], sel[2], sel[4], sel[7]]):
    px, py = st[0] - X0, st[1] - Y0
    D.ellipse([px*Z, py*Z, (px + 16)*Z, (py + 13)*Z], outline=(255, 255, 255), width=3)
    D.text((px*Z + 40, py*Z + 30), str(i + 1), fill=(255, 255, 255))
out = Image.new("RGB", (CW*Z, CH*Z + 40), (30, 30, 30)); out.paste(img, (0, 40)); D2 = ImageDraw.Draw(out)
D2.text((8, 6), "PEAK around the fall: every surface tinted and labelled by the CELL that drew it (x,y kind h = height in units; floor 38 = 152 px, wall 54 = 216 px).", fill=(255, 255, 255))
D2.text((8, 20), "White circles 1-4: the ball rolling off floor (24,18) toward -x into the void (23,18), behind wall (23,19). The exit arch is cut in wall (23,19)'s face.", fill=(255, 255, 255))
out.save("peak-owners.png"); print("ok")
