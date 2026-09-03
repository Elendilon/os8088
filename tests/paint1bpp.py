#!/usr/bin/env python3
"""IS THE CANVAS ONE BIT A PIXEL WHERE IT SHOULD BE, AND FOUR WHERE IT SHOULD
NOT? (SPEC.md 42.23)

    make && python3 tests/paint1bpp.py [--machine os8088_5150_herc_gla]

SPEC.md 42.23's whole claim is a MEMORY claim: the same 448x258 canvas is
56.6KB stored packed and 14.2KB stored one bit deep, and on the 128KB floor
machine that is the difference between the full default picture and the
letterbox 42.6.5 cuts.  So the assertion here is the CLAIM and not the
pixels - every other paint row already compares pixels, and not one of them
would notice a canvas that came out four times bigger than it had to be.

**Three things, and the third is the point of the row:**

  1. On a 1bpp adapter the canvas is one bit - stride ceil(w/8) rounded to 4,
     a 62-byte DIB rather than 118, and [pt_ncol] = 2 because a canvas that
     cannot store 39.4's dither class must not offer it.
  2. The DIB in front of row 0 is a VALID 1bpp BMP - the canvas IS the file
     (SPEC.md 42), so a save is one write of it and a header that lies is a
     file no host can open.  biBitCount 1, biClrUsed 2, bfOffBits 62, the
     palette {black, white}, and every field agreeing with the live geometry.
     **A blank canvas must read all 0xFF**, which is 42.23.1's polarity: 1 is
     WHITE, both because that is what a standard 1bpp BMP means and because
     gfx_blit1 blits a band that way up with `rep movsw` at 12.5 clocks a
     byte instead of the complementing loop's 17.
  3. **On a COLOUR adapter it is NOT one bit** - the canvas is four planes,
     sixteen colours, and the arithmetic is byte-for-byte what it was before
     42.23 existed.  A new canvas on a VGA opens in colour and only a mono
     screen opens one bit; that is a product decision and this is what stops
     it drifting.  Nothing else in tests/ asserts a NEGATIVE about the
     format, so a change that made every canvas one bit deep would pass the
     whole suite and quietly cost the VGA fifteen of its colours.

The GLaBIOS twin, for tests/paintwipe.py's reason: `ibm5150_82_v4` is IBM's
ROM and is not in this tree, and this row takes no timing of any kind.
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)
import os88marty                                            # noqa: E402
import os88mouse                                            # noqa: E402
import os88sym                                              # noqa: E402
import dispcp                                               # noqa: E402
import dispapps                                             # noqa: E402

ROOT = os.path.dirname(HERE)
S = os88sym.linear
PT_BMPHDR = 118                 # 14 + 40 + 16*4, mirrored in apps/paint
PT_BMPHDR1 = 62                 # ...and 14 + 40 + 2*4 at one bit


def _boff(seg, name):
    return ((seg << 4) + dispapps.img_size("paint")
            + dispapps.bss_off("paint", name))


def _w(m, seg, name, n=2):
    return int.from_bytes(m.read(_boff(seg, name), n), "little")


def _open_paint(m, mo):
    dispcp.open_drive(m, mo, S, os88marty.settle, "B")
    disk = dispcp.win_list(m, S)[-1]
    wx, wy = dispcp.win_rect(m, S, disk)[:2]
    dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "APPS")
    wx, wy = dispcp.win_rect(m, S, disk)[:2]
    rows = [r[0] for r in dispcp.listing(m, S)]
    row = dispcp.scroll_to(m, mo, S, os88marty.settle, wx, wy,
                           rows.index("PAINT.O88"))
    x, y = dispcp.row_xy(wx, wy, row)
    mo.dblclick(x, y)
    m.advance(frames=250)
    m.run()
    got = dispapps.pkg_seg(m, 0)
    if got is None:
        sys.exit("paint1bpp: PAINT.O88 did not open")
    return got[1]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    ap.add_argument("--colour", action="store_true",
                    help="assert the COLOUR arm instead - four planes, "
                         "sixteen colours, no 1bpp anywhere")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    fails = []

    with os88marty.launch(a.image, apps=a.apps, machine=a.machine) as m:
        os88marty.settle(m)
        mo = os88mouse.Mouse(marty=m)
        seg = _open_paint(m, mo)

        cw, ch = _w(m, seg, "pt_cw"), _w(m, seg, "pt_ch")
        stride, hdr = _w(m, seg, "pt_stride"), _w(m, seg, "pt_hdrsz")
        one, planar = _w(m, seg, "pt_1bpp", 1), _w(m, seg, "pt_planar", 1)
        ncol = _w(m, seg, "pt_ncol", 1)
        base = _w(m, seg, "pt_base")
        claim = hdr + stride * ch
        packed = (((cw + 1) // 2 + 3) & ~3) * ch + PT_BMPHDR
        print("   canvas   %dx%d  stride %d  header %d" % (cw, ch, stride, hdr))
        print("   format   1bpp=%d planar=%d ncol=%d" % (one, planar, ncol))
        print("   claim    %d bytes (%.1f KB), packed would be %.1f KB"
              % (claim, claim / 1024.0, packed / 1024.0))

        if a.colour:
            # --- 3. THE NEGATIVE. A colour adapter is untouched by 42.23 ----
            if one:
                fails.append("a COLOUR adapter gave Paint a one-bit canvas - "
                             "a new canvas opens in colour there and only a "
                             "mono screen opens one bit (SPEC.md 42.23)")
            if not planar:
                fails.append("[pt_planar] is 0 on a colour adapter, so "
                             "SPEC.md 42.13's four-plane canvas is gone")
            if ncol != 16:
                fails.append("[pt_ncol] is %d on a colour adapter, wanted 16"
                             % ncol)
            if hdr != PT_BMPHDR:
                fails.append("the DIB is %d bytes on a colour adapter, "
                             "wanted %d" % (hdr, PT_BMPHDR))
            if claim != packed:
                fails.append("the claim is %d bytes and the 4bpp arithmetic "
                             "says %d" % (claim, packed))
        else:
            # --- 1. the format ---------------------------------------------
            if not one:
                fails.append("a 1bpp adapter did NOT give Paint a one-bit "
                             "canvas (SPEC.md 42.23)")
            if planar:
                fails.append("[pt_planar] and [pt_1bpp] are BOTH set, which "
                             "42.23 says can never happen")
            if ncol != 2:
                fails.append("[pt_ncol] is %d, wanted 2 - the dither class is "
                             "not storable at one bit (SPEC.md 42.23.1)"
                             % ncol)
            want = ((cw + 7) // 8 + 3) & ~3
            if stride != want:
                fails.append("stride %d, wanted ceil(%d/8) rounded to 4 = %d"
                             % (stride, cw, want))
            if hdr != PT_BMPHDR1:
                fails.append("the DIB is %d bytes, wanted %d"
                             % (hdr, PT_BMPHDR1))
            if claim * 3 > packed:
                fails.append("the claim is %d bytes against %d packed - the "
                             "whole point of 42.23 is the factor of four"
                             % (claim, packed))

            # --- 2. ...and the file it is ----------------------------------
            h = m.read(base << 4, PT_BMPHDR1)
            f = dict(magic=h[0:2],
                     bfSize=struct.unpack("<I", h[2:6])[0],
                     bfOffBits=struct.unpack("<I", h[10:14])[0],
                     biSize=struct.unpack("<I", h[14:18])[0],
                     biWidth=struct.unpack("<i", h[18:22])[0],
                     biHeight=struct.unpack("<i", h[22:26])[0],
                     biPlanes=struct.unpack("<H", h[26:28])[0],
                     biBitCount=struct.unpack("<H", h[28:30])[0],
                     biCompr=struct.unpack("<I", h[30:34])[0],
                     biSizeImage=struct.unpack("<I", h[34:38])[0],
                     biClrUsed=struct.unpack("<I", h[46:50])[0])
            print("   header   %s bpp=%d clr=%d off=%d %dx%d size=%d"
                  % (f["magic"], f["biBitCount"], f["biClrUsed"],
                     f["bfOffBits"], f["biWidth"], f["biHeight"],
                     f["bfSize"]))
            print("   palette  %s"
                  % " ".join("%02X" % c for c in h[54:PT_BMPHDR1]))
            for k, v in (("magic", b"BM"), ("biSize", 40), ("biPlanes", 1),
                         ("biBitCount", 1), ("biCompr", 0), ("biClrUsed", 2),
                         ("bfOffBits", PT_BMPHDR1), ("biWidth", cw),
                         ("biHeight", ch), ("bfSize", claim),
                         ("biSizeImage", stride * ch)):
                if f[k] != v:
                    fails.append("the DIB's %s is %r, wanted %r - the canvas "
                                 "IS the file (SPEC.md 42), so a save is one "
                                 "write of this" % (k, f[k], v))
            if bytes(h[54:PT_BMPHDR1]) != bytes([0, 0, 0, 0, 255, 255, 255, 0]):
                fails.append("the palette is not {black, white} as BGRA - "
                             "42.23.1's polarity is that index 1 is WHITE")

            # --- ...and a blank canvas is all 0xFF, which IS that polarity
            r0 = m.read((base << 4) + hdr, stride)
            if set(r0) != {0xFF}:
                fails.append("file row 0 of a blank canvas is %s, not all "
                             "0xFF - 42.23.1 stores 1 as WHITE"
                             % r0[:8].hex())

    for f in fails:
        print("paint1bpp: " + f)
    if fails:
        print("paint1bpp: FAIL")
        return 1
    print("paint1bpp: PASS - %s"
          % ("a colour adapter is untouched: four planes, sixteen colours"
             if a.colour else
             "the canvas is one bit, a quarter of the claim, and a valid "
             "1bpp BMP"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
