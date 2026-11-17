import sys, pickle, colorsys
from PIL import Image, ImageDraw
W = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "../../../.."))
sys.path.insert(0, W + "/tools")
import bbcourse as B
c = B.compile_course(W + "/apps/bonanza/courses/summit.bbc")
d = pickle.load(open("peakfall.pkl", "rb")); sel = d["sel"]
X0, Y0, CW, CH, Z = 296, 396, 72, 64, 6
VOID = -32768
def scene(st, mode):
    px, py, sb, zb, air, cell = st
    laid = B.laid_at(c, px, py, sb, zb, air)
    bp = B.ball_pixels(px, py)
    hid = {p for r in laid for p in r["pix"]}
    m = 0 if air else B.CLIMB
    img = Image.new("RGB", (CW, CH)); P = img.load()
    for y in range(CH):
        for x in range(CW):
            X, Yy = X0 + x, Y0 + y
            s, t = c.sbuf[Yy][X], c.tbuf[Yy][X]
            if mode == "pic":
                v = bp.get((X, Yy)) if (X, Yy) in bp and (X, Yy) not in hid else c.pic[Yy][X]
                if (X, Yy) in bp and (X, Yy) in hid and B.ghost(X, Yy): v = bp[(X, Yy)]
                P[x, y] = B.CGA1[v]
            else:
                if s == VOID: col = (20, 20, 20)
                elif s > sb and t > zb + m: col = (230, 40, 40)      # in front AND taller: hides the ball
                elif s > sb: col = (240, 170, 60)                    # in front but lower than the ball
                else: col = (60, 90, 200)                            # behind or beside the ball
                base = B.CGA1[c.pic[Yy][X]]
                col = tuple(int(0.75*a + 0.25*b) for a, b in zip(col, base))
                if (X, Yy) in bp: col = (255, 255, 255) if (X, Yy) not in hid else (255, 120, 255)
                P[x, y] = col
    return img.resize((CW*Z, CH*Z), Image.NEAREST)
frames = [sel[0], sel[2], sel[4], sel[7]]
out = Image.new("RGB", (2*(CW*Z+8)+8, len(frames)*(CH*Z+30)+30), (40,40,40)); D = ImageDraw.Draw(out)
D.text((8, 8), "as drawn today", fill=(255,255,255)); D.text((CW*Z+16, 8), "depth vs the ball: RED = in front and taller (hides), ORANGE = in front but lower, BLUE = behind/beside; ball white, hidden ball px pink", fill=(255,255,255))
for i, st in enumerate(frames):
    y = 30 + i*(CH*Z+30)
    out.paste(scene(st, "pic"), (8, y)); out.paste(scene(st, "depth"), (CW*Z+16, y))
    px, py, sb, zb, air, cell = st
    D.text((8, y+CH*Z+4), "ball in cell %s (cell row %d), height %d, %s" % (cell, sb, zb, "falling" if air else "rolling"), fill=(255,255,0))
out.save("why-peak-fall.png"); print("ok")
