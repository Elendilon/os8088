#!/usr/bin/env python3
"""kfzread: decode the KFZ heartbeat strip out of a screenshot.

    make KFZ=1                       # ...and boot THAT kernel
    python3 tools/kfzread.py shot.png [shot2.png ...]

A `KFZ=1` kernel paints fifteen bytes of kernel state into the top-left of
the menu bar from IRQ0, twice per tick (SPEC.md 9.6.5, kernel/sched.inc).
**That strip is the only instrument that survives a hard freeze**: the field's
last one took the timer interrupt with it, so the 30-second watchdog never
fired and the LAST PICTURE ON THE GLASS was the whole of the evidence.

This turns that picture back into numbers, so a photograph is read
mechanically instead of by eye - which is how `beat` one ahead of `chain` got
noticed at all.

--- THE ENCODING, and every part of it is for the camera -------------------
Two bits per framebuffer byte, four pixels per bit, high bit first; a set bit
is BLACK on the white bar; four banks tall, so the strip is four screen rows
of identical pixels. Four bytes make one 8-bit value, then one blank byte,
then the next: 15 values, 75 bytes, 600 pixels.

At one pixel per bit a photographed cell was unreadable, which is why the
kernel spends four.

--- WHAT IT TAKES ----------------------------------------------------------
Any PNG of the guest: 86Box's own screenshot (clean, origin 0,0) or a capture
of the whole emulator window with its chrome. The strip is FOUND rather than
assumed - the run-length structure is strong enough to lock onto, and a wrong
lock cannot produce it - so no offsets have to be passed. `--at X,Y,SCALE`
overrides if the search ever fails.
"""
import argparse
import struct
import sys
import zlib

NVAL = 15
NAMES = ["beat", "chain", "kfz", "sch_cur", "sch_lock", "gfx_lock_flag",
         "gfx_lock_own", "SP hi", "SP lo", "stk0 bad", "CS hi", "IP hi",
         "IP lo", "PIC mask", "PIC in-service"]


def load_png(path):
    """Minimal PNG reader - greyscale/RGB/palette, 8-bit, no interlace."""
    d = open(path, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit("%s: not a PNG" % path)
    pos, idat, pal, w, h, depth, ctype = 8, b"", None, 0, 0, 0, 0
    while pos < len(d):
        ln, = struct.unpack(">I", d[pos:pos + 4])
        typ = d[pos + 4:pos + 8]
        body = d[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
        elif typ == b"PLTE":
            pal = body
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    if depth != 8:
        sys.exit("%s: %d-bit PNG, only 8-bit is handled" % (path, depth))
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(idat)
    stride = w * nch
    out, prev = [], bytearray(stride)
    p = 0
    for _ in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        for i in range(stride):
            a = line[i - nch] if i >= nch else 0
            b = prev[i]
            c = prev[i - nch] if i >= nch else 0
            if f == 1: line[i] = (line[i] + a) & 0xFF
            elif f == 2: line[i] = (line[i] + b) & 0xFF
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif f == 4:
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        out.append(bytes(line)); prev = line
    # ...to one luminance byte per pixel
    rows = []
    for line in out:
        if ctype == 3:
            rows.append([pal[3 * v] for v in line])
        elif ctype in (0, 4):
            rows.append([line[i * nch] for i in range(w)])
        else:
            rows.append([line[i * nch] for i in range(w)])
    return w, h, rows


def bits_from(row, x0, scale):
    """600 pixels -> 15 bytes, or None if the run structure does not hold."""
    vals, x = [], x0
    for v in range(NVAL):
        byte = 0
        for b in range(8):
            run = row[x:x + 4 * scale]
            if len(run) < 4 * scale:
                return None
            dark = sum(1 for p in run if p < 128)
            if dark not in (0, len(run)):      # a bit is four SOLID pixels;
                return None                    # anything else is not the strip
            byte = (byte << 1) | (1 if dark else 0)
            x += 4 * scale
        vals.append(byte)
        gap = row[x:x + 8 * scale]             # ...then one blank byte
        if len(gap) < 8 * scale or any(p < 128 for p in gap):
            return None
        x += 8 * scale
    return vals


def find(rows, w, h):
    """Search the whole image, not just the corner.

    A clean 86Box screenshot puts the strip at (0, 0); a capture of the whole
    emulator WINDOW puts it a hundred-odd pixels down and some pixels in, and
    the field sends both. `bits_from` bails on the first run that is not four
    solid pixels, so almost every candidate costs a handful of compares and
    the wide search is affordable.
    """
    for scale in (4, 3, 2, 1):          # LARGEST FIRST: a genuine 2x strip must
        need = 600 * scale              # win before a 1x coincidence somewhere
        if w < need:                    # else in the image
            continue
        tall = 4 * scale                # four banks, so four guest rows
        for y in range(0, h - tall + 1):
            for x0 in range(0, w - need + 1):
                v = bits_from(rows[y], x0, scale)
                if v is None:
                    continue
                if len(set(v)) == 1:    # fifteen identical values is a flat
                    continue            # region, not a strip
                # **AND IT MUST BE FOUR GUEST ROWS TALL, ALL THE SAME.** The
                # first version took the first thing whose run structure held
                # and locked onto the emulator's own window chrome, reporting
                # beat FF chain 00 off a picture of a border. The kernel
                # paints the strip into four banks precisely so a photograph
                # is legible, and that repetition is the signature.
                if all(bits_from(rows[y + d], x0, scale) == v
                       for d in range(1, tall)):
                    return v, x0, y, scale
    return None, 0, 0, 0


def report(path):
    w, h, rows = load_png(path)
    vals, x0, y, scale = find(rows, w, h)
    print("== %s ==" % path)
    if vals is None:
        print("   NO STRIP FOUND. Is this a KFZ=1 kernel (`make KFZ=1`), on a")
        print("   MONO adapter? The strip is Hercules/CGA banked and is not")
        print("   painted on VGA at all.")
        return 1
    print("   strip at x=%d y=%d, %dx scale" % (x0, y, scale))
    for n, v in zip(NAMES, vals):
        print("   %-16s %02X  (%d)" % (n, v, v))
    beat, chain = vals[0], vals[1]
    csh, iph, ipl = vals[10], vals[11], vals[12]
    print("   ---")
    print("   stopped at  %02X:%02X%02X   (CS high: 00 kernel, 0D cold, "
          "else a package)" % (csh, iph, ipl))
    d = (beat - chain) & 0xFF
    if d == 0:
        print("   beat == chain: the timer interrupt RAN TO THE END, so "
              "whatever stopped")
        print("   the machine is out in task code.")
    elif d == 1:
        print("   beat is ONE AHEAD of chain: the machine died INSIDE the "
              "timer interrupt")
        print("   and never came back from the BIOS int 08h chain.")
    else:
        print("   beat - chain = %d, which is neither 0 nor 1 - the strip was "
              "caught mid-paint" % d)
    print("   PIC mask %02X in-service %02X   (IRQ0 is bit 0 of each)"
          % (vals[13], vals[14]))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("png", nargs="+")
    a = ap.parse_args()
    rc = 0
    for p in a.png:
        rc |= report(p)
        print()
    sys.exit(rc)
