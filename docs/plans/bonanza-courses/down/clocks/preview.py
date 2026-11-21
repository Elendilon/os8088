#!/usr/bin/env python3
"""a FAST look at the sixteen frames (no compile): each drawn on a plain block top, CGA over Hercules, zoomed.
    python3 docs/plans/bonanza-courses/down/clocks/preview.py docs/plans/bonanza-courses/down/clocks/frames.png"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import bbcourse as B                                   # noqa: E402
import frames as F                                     # noqa: E402
from PIL import Image                                  # noqa: E402

F.install(B)
W, H, Z = 64, 72, 4


def cell(name):
    p = {"at": (0, 0), "z4": 0, "ndig": 2, "frame": name}
    x0, y0 = 32, 56
    pic = [[B.BLK] * W for _ in range(H)]
    cx, cy = x0, 8 + y0
    for y in range(H):                              # the block: a top diamond and its two faces
        for x in range(W):
            d = abs(x + 0.5 - cx) / 16.0 + abs(y + 0.5 - cy) / 8.0
            if d <= 1.0 and y <= cy + 8:
                pic[y][x] = B.WHT if d < 0.93 else B.BLK
            elif cy - 8 < y and abs(x + 0.5 - cx) <= 16 and y <= cy + 8 + (16 - abs(x + 0.5 - cx)) / 2.0 \
                    and y > cy + (16 - abs(x + 0.5 - cx)) / 2.0 - 0.5:
                pic[y][x] = B.MAG if x < cx else (B.MAG if (x + y) & 1 else B.BLK)
    out = B.clock_face_pix(p, x0, y0)
    for (x, y), v in out.items():
        if 0 <= x < W and 0 <= y < H:
            pic[y][x] = v
    bx, by = B.clock_digit_block(dict(p, place=1), x0, y0)
    for place, d in ((1, 4), (0, 7)):                # "47" in the clock's font
        gx = 8 * (bx + 1 - place)
        g = B.CLOCK_FONT[d] if hasattr(B, "CLOCK_FONT") else None
        if g:
            for j, row in enumerate(g):
                for i in range(5):
                    if (row >> (4 - i)) & 1:
                        pic[8 * by + 1 + j][gx + 1 + i] = B.BLK
    cga = Image.new("RGB", (W, H))
    cga.putdata([B.CGA1[v] for r in pic for v in r])
    herc = Image.new("L", (2 * W, H))
    herc.putdata([255 * b for y, r in enumerate(pic) for x, v in enumerate(r)
                  for pr in (B.herc_pair(v, y, x),) for b in (pr >> 1, pr & 1)])
    herc = herc.resize((W, H)).convert("RGB") if False else herc.convert("RGB")
    return cga.resize((W * Z, H * Z), Image.NEAREST), herc.resize((W * Z, H * Z), Image.NEAREST)


def main(out):
    names = [n for vs in F.CONCEPTS.values() for n, _a in vs]
    sheet = Image.new("RGB", (4 * W * Z + 3 * 8, 8 * H * Z + 7 * 4), (60, 60, 60))
    for i, n in enumerate(names):
        c, h = cell(n)
        r, k = divmod(i, 4)
        sheet.paste(c, (k * (W * Z + 8), (2 * r) * (H * Z + 4)))
        sheet.paste(h, (k * (W * Z + 8), (2 * r + 1) * (H * Z + 4)))
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
