#!/usr/bin/env python3
"""Run a play/idle-mode tests/rbcore image in QEMU and render its last frame.

    python3 tests/rbcore/rbshot.py IMG -o OUT.pgm [--timeout S]

MODES 3 and 4 of tests/rbcore/rbhost.asm end by sending VRAM, OAM and the
LCD registers on COM1 after "RBVRAM". This draws them as a DMG would -
background, window and sprites, a whole frame at the registers' final values
- into a 160x144 PGM, the format tools/gbprof.py --shots writes, so the core's
picture can be put beside Peanut-GB's before the core has a renderer of its
own. A raster effect shows as one frame of its last values.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

SHADE = (255, 170, 85, 0)


def capture(img, timeout):
    fd, log = tempfile.mkstemp(prefix="rbs-")
    os.close(fd)
    p = subprocess.Popen(["qemu-system-i386", "-drive", "file=%s,format=raw,if=floppy" % img,
                          "-boot", "a", "-display", "none", "-serial", "file:%s" % log,
                          "-no-reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    need = 0x2000 + 0xA0 + 0x0C
    t0 = time.time()
    try:
        while time.time() - t0 < timeout:
            data = open(log, "rb").read()
            k = data.find(b"RBVRAM")
            if k >= 0 and len(data) >= k + 6 + need:
                return data[:k], data[k + 6:k + 6 + need]
            time.sleep(0.3)
    finally:
        p.kill()
        p.wait()
        os.unlink(log)
    sys.exit("rbshot: no RBVRAM block within %ds" % timeout)


def render(blk):
    vram, oam, reg = blk[:0x2000], blk[0x2000:0x20A0], blk[0x20A0:]
    lcdc, scy, scx, bgp, obp0, obp1, wy, wx = (reg[0], reg[2], reg[3], reg[7],
                                              reg[8], reg[9], reg[10], reg[11])
    pix = bytearray(160 * 144)
    raw = bytearray(160 * 144)                  # BG colour index, for priority

    def tile(map_base, mx, my, x, y):
        t = vram[map_base - 0x8000 + my * 32 + mx]
        a = t * 16 if lcdc & 0x10 else 0x1000 + ((t ^ 0x80) - 0x80) * 16
        lo, hi = vram[a + y * 2], vram[a + y * 2 + 1]
        return ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)

    if lcdc & 0x80 and lcdc & 0x01:
        bgmap = 0x9C00 if lcdc & 0x08 else 0x9800
        wmap = 0x9C00 if lcdc & 0x40 else 0x9800
        for y in range(144):
            for x in range(160):
                if lcdc & 0x20 and y >= wy and x >= wx - 7:
                    px, py = x - (wx - 7), y - wy
                    c = tile(wmap, px >> 3, py >> 3, px & 7, py & 7)
                else:
                    px, py = (x + scx) & 255, (y + scy) & 255
                    c = tile(bgmap, px >> 3, py >> 3, px & 7, py & 7)
                raw[y * 160 + x] = c
                pix[y * 160 + x] = (bgp >> (c * 2)) & 3
    if lcdc & 0x80 and lcdc & 0x02:
        h = 16 if lcdc & 0x04 else 8
        for i in reversed(range(40)):
            sy, sx, t, fl = oam[i * 4] - 16, oam[i * 4 + 1] - 8, oam[i * 4 + 2], oam[i * 4 + 3]
            if h == 16:
                t &= 0xFE
            pal = obp1 if fl & 0x10 else obp0
            for yy in range(h):
                for xx in range(8):
                    x, y = sx + xx, sy + yy
                    if not (0 <= x < 160 and 0 <= y < 144):
                        continue
                    ty = h - 1 - yy if fl & 0x40 else yy
                    tx = 7 - xx if fl & 0x20 else xx
                    a = t * 16 + ty * 2
                    c = ((vram[a] >> (7 - tx)) & 1) | (((vram[a + 1] >> (7 - tx)) & 1) << 1)
                    if c == 0 or (fl & 0x80 and raw[y * 160 + x]):
                        continue
                    pix[y * 160 + x] = (pal >> (c * 2)) & 3
    return bytes(SHADE[p] for p in pix)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("img")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--timeout", type=float, default=300)
    a = ap.parse_args()
    text, blk = capture(a.img, a.timeout)
    sys.stdout.write(text.decode("latin-1"))
    with open(a.out, "wb") as f:
        f.write(b"P5 160 144 255\n" + render(blk))
    print("rbshot: %s" % a.out)


if __name__ == "__main__":
    main()
