"""ROLL before/after (SPEC.md 130.48, the diary's 2026-11-19): the record maps (the whole-cell cut against the
real-pose cut), and twelve real ball poses each drawn before (whole-cell cut, no low-flight margin, no split AV:
the compile's _hack realcut False, noavsplit) and after.  Nothing in make runs it.

    python3 docs/plans/bounce-bonanza/occ-real/occreal.py      # writes the two PNGs beside it
"""
import os, sys, collections
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B
from PIL import Image, ImageDraw, ImageFont
SP = os.path.dirname(os.path.abspath(__file__)) + os.sep
F = ImageFont.load_default()
roll = os.path.join(ROOT, 'apps', 'bonanza', 'courses', 'roll.bbc')
old = B.compile_course(roll, _hack={"realcut": False, "noavsplit": True})
new = B.compile_course(roll)
W, H = new.width, new.lines
COL = {1: (40, 100, 230), 2: (40, 170, 60), 3: (230, 150, 20), 4: (230, 30, 30)}
def base(c, dim=0.55):
    im = Image.new("RGB", (W, H)); im.putdata([B.CGA1[v] for row in c.pic for v in row])
    return Image.eval(im, lambda v: int(v * dim))
def countmap(c, title):
    im = base(c); ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
    n = collections.Counter((r["brow"], r["col"]) for r in c.records)
    for (br, bc), k in n.items():
        d.rectangle([bc * 8, br * 8, bc * 8 + 7, br * 8 + 7], fill=COL[min(k, 4)] + (200,))
        if k >= 4: d.rectangle([bc * 8, br * 8, bc * 8 + 7, br * 8 + 7], outline=(255, 0, 0, 255))
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    ImageDraw.Draw(im).text((4, 2), title, fill=(255, 255, 255), font=F)
    return im
maps = [countmap(old, "BEFORE (f6b7c84): %d records a block" % len(old.records)),
        countmap(new, "AFTER (bb-occfix): %d records a block" % len(new.records))]
out = Image.new("RGB", (2 * W + 8, H), (255, 255, 255))
for i, m in enumerate(maps): out.paste(m, (i * (W + 8), 0))
out.save(SP + "roll-maps-before-after.png")
# the same poses as the first gallery
POSES = [((9, 12), 201, 1, 159, 207, "RAMP (9,12), 0.5 px up, airborne"),
         ((9, 13), 193, 1, 159, 223, "RAMP (9,13), 0.5 px up, airborne"),
         ((14, 18), 171, 1, 239, 299, "RAMP (14,18), 0.5 px up, airborne"),
         ((15, 18), 171, 1, 255, 299, "RAMP (15,18), 0.5 px up, airborne"),
         ((8, 8), 194, 1, 129, 137, "CORNER (8,8) void half, z 194"),
         ((11, 8), 187, 1, 177, 129, "CORNER (11,8) void half, z 187"),
         ((8, 11), 187, 1, 129, 181, "CORNER (8,11) void half, z 187"),
         ((8, 14), 178, 1, 129, 233, "CORNER (8,14) void half, z 178"),
         ((6, 7), 185, 1, 109, 119, "VOID (6,7) by a corner, z 185"),
         ((7, 7), 186, 1, 113, 121, "VOID (7,7) by a corner, z 186"),
         ((7, 8), 190, 1, 113, 129, "VOID (7,8) by a corner, z 190"),
         ((7, 6), 185, 1, 117, 111, "VOID (7,6) by a corner, z 185")]
def pose_img(c, cell, z, air, gx, gy, label, newrule, Z=5):
    gx8, gy8 = gx << 8, gy << 8
    f = B.pose_floor(c.tiles, cell[0], cell[1], gx8, gy8)
    oair = B.oair_at(air, z, f) if newrule else air
    m = 0 if oair else B.CLIMB
    px = gx - gy + c.x0 - 8; py = (gx + gy) // 2 - z + c.y0 - 13
    bp = B.ball_pixels(px, py)
    hidden = set()
    for br in range(py >> 3, ((py + 15) >> 3) + 1):
        for bc in range((px & ~3) >> 3, (((px & ~3) + 19) >> 3) + 1):
            for r in c.by_block.get((br, bc), ()):
                if (cell[0] + cell[1]) < r["s"] and z + m < r["top"]:
                    hidden |= r["pix"] & set(bp)
    model = B.amodel_pix(c, B.mcell(gx8, gy8) if newrule else cell, z, air, px, py) & set(bp)
    cx0, cy0 = px - 24, py - 20; w, h = 64, 52
    im = Image.new("RGB", (w, h)); p = im.load()
    for y in range(h):
        for x in range(w):
            X, Y = cx0 + x, cy0 + y
            if 0 <= X < W and 0 <= Y < H: p[x, y] = B.CGA1[c.pic[Y][X]]
    for (X, Y), ci in bp.items():
        x, y = X - cx0, Y - cy0
        if 0 <= x < w and 0 <= y < h:
            p[x, y] = (255, 0, 0) if (X, Y) in hidden else (255, 120, 220) if (X, Y) in model else B.CGA1[ci]
    im = im.resize((w * Z, h * Z), Image.NEAREST)
    lab = Image.new("RGB", (w * Z, 30), (20, 20, 20)); d = ImageDraw.Draw(lab)
    d.text((4, 2), label, fill=(255, 255, 255), font=F)
    d.text((4, 15), "records %d px (red), AV model %d px (pink), of %d" % (len(hidden), len(model - hidden), len(bp)),
           fill=(255, 255, 255), font=F)
    full = Image.new("RGB", (w * Z, h * Z + 30)); full.paste(im, (0, 0)); full.paste(lab, (0, h * Z))
    return full
rows = []
for cell, z, air, gx, gy, lab in POSES:
    rows.append((pose_img(old, cell, z, air, gx, gy, "BEFORE: " + lab, False),
                 pose_img(new, cell, z, air, gx, gy, "AFTER: " + lab, True)))
tw, th = rows[0][0].size
g = Image.new("RGB", (4 * (tw + 6), (len(rows) // 2) * (th + 6)), (255, 255, 255))
for i, (a, b) in enumerate(rows):
    r, col = i // 2, (i % 2) * 2
    g.paste(a, (col * (tw + 6), r * (th + 6))); g.paste(b, ((col + 1) * (tw + 6), r * (th + 6)))
g.save(SP + "roll-balls-before-after.png")
print("records", len(old.records), "->", len(new.records))
