#!/usr/bin/env python3
"""VIDEO.O88's DESKTOP POSTERS (SPEC.md 98.1.3.11, 98.4.5), on MartyPC's VGA
XT: a sixteen-colour file of its own colours, 640 wide, which the Preview
shows at half - a picture of 50% checkerboards, which the poster's old
decimation turned to one colour of each - three ways, each one held to the
host's reference BYTE FOR BYTE in the poster's claim:

1. POSTERS STORED AT HALF, and a CUSTOM one: at open the box is the custom
   poster as stored; Right to key 1, and it is key 1's as stored.
2. POSTERS STORED AT ITS OWN SIZE (a file the encoder thought would fit):
   the box at half is the stored poster halved, `packed_half`.
3. NONE STORED: the key decoded and packed as `vga4_pack` packs it - one
   pixel of each cell, which one turning with the output's place, so the
   checkerboards stay checkerboards.

Broken on purpose: the posters ignored ([vp_thn] 0 after the header) and 1
FAILS; vp_dphalf's turning taken out and 2 FAILS; vp_v4pack's turning
taken out (the corner every time) and 3 FAILS.
"""
import os
import random
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88marty, os88ui, os88build, os88vid as vid, os88geom as geom  # noqa: E402
from cycweb import pkg_syms                                   # noqa: E402

W, H, NF, FPS = 640, 120, 30, 15.0
# sixteen greys: none is the desktop's but black and white
PAL = bytes(v for i in range(16) for v in (i * 4 + 3,) * 3)
PAL = bytes(3) + PAL[3:45] + bytes((63, 63, 63))


def u16(b, i=0):
    return struct.unpack_from("<H", b, i)[0]


def clip(tmp, name, thumbs):
    """checkerboards of two greys over a moving bar, keys every second"""
    rnd = random.Random(98)
    cvs = []
    for f in range(NF):
        a, b = rnd.randrange(16), rnd.randrange(16)
        cv = bytearray(W * H)
        for y in range(H):
            for x in range(W):
                cv[y * W + x] = a if (x + y) & 1 else b
        x0 = (f * 17) % (W - 64)
        for y in range(20, 60):
            cv[y * W + x0:y * W + x0 + 64] = bytes([15]) * 64
        cvs.append(bytes(cv))
    g = vid.Geom(vid.LAY_LIN80, W // 8, H, bitplanes=True)
    out = os.path.join(tmp, name)
    th = None
    if thumbs:
        ts, custom = thumbs
        cpk = None
        if custom:
            crgb = [[(min(63, (x * 63) // W), min(63, (y * 63) // H), 32)
                     for x in range(W)] for y in range(H)]
            cpk = vid.desktop_poster_rgb(crgb, W, H, ts)
        th = (ts, lambda c, _s=ts: vid.desktop_poster(c, W, H, PAL, _s), cpk)
    vid.encode_canvases(cvs, g, out, FPS, vid.PF_VGA4, PAL + bytes(
        vid.PAL_BYTES - 48), "vidposter clip", keysecs=1.0, poster=0,
        thumbs=th)
    vid.verify_v88(out)
    return out


def main():
    os.chdir(ROOT)
    syms, _ = pkg_syms("apps/video/video.asm", ("apps/",))
    pkg = os88build.at("build/video.o88")
    bad = []
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "build")) as tmp:
        files = [clip(tmp, "STORED.V88", (2, True)),
                 clip(tmp, "OWNSIZE.V88", (1, False)),
                 clip(tmp, "NONE.V88", None)]
        disk = os.path.join(tmp, "vidpost.img")
        subprocess.run([sys.executable, "tools/os88disk.py", "-o", disk,
                        "--size", "360", pkg] + files, check=True,
                       capture_output=True)
        with os88ui.boot(os88build.at("build/os8088-360.img"), apps=disk,
                         machine="os8088_xt_vga") as ui:
            m = ui.m
            for arm, v88 in enumerate(files, 1):
                r = vid.Reader(v88)
                g = r.g
                w = ui.path("B:/" + os.path.basename(v88))
                rec = m.read(ui._S("wm_wins") + w.i * geom.WIN_SIZE,
                             geom.WIN_SIZE)
                base = u16(rec, geom.W_SEG) << 4

                def rw(n):
                    return u16(m.read(base + syms[n], 2))

                def until(cond, what, guest=90.0):
                    os88marty.until(m, cond, what, poll=0.3, limit=600.0,
                                    guest=guest)

                until(lambda mm: rw("vp_ploads") >= 1, "the poster", 60.0)
                ps = rw("vp_ps")

                def poster(n):
                    return bytes(m.read(rw("vp_pseg") << 4, n))

                if arm == 1:
                    tn = r.thumb[1]
                    want = r.thumb_pic(tn - 1)
                    got = poster(len(want))
                    d1 = sum(1 for a, b in zip(got, want) if a != b)
                    loads = rw("vp_ploads")
                    m.key("ArrowRight")
                    until(lambda mm: rw("vp_ploads") > loads, "key 1's", 60.0)
                    want2 = r.thumb_pic(1)
                    d2 = sum(1 for a, b in zip(poster(len(want2)), want2)
                             if a != b)
                    print("   1. stored at half: scale %d, the custom poster "
                          "%d of %d bytes differ, key 1's %d" % (
                              ps, d1, len(want), d2))
                    if ps != 2 or d1 or d2:
                        bad.append("stored posters: scale %d, %d and %d "
                                   "bytes differ" % (ps, d1, d2))
                elif arm == 2:
                    tat, tn, tw, th_, ts, tf = r.thumb
                    want = vid.packed_half(r.thumb_pic(r.poster), tw, th_)[0]
                    d = sum(1 for a, b in zip(poster(len(want)), want)
                            if a != b)
                    print("   2. stored at its own size, shown at %d: %d of "
                          "%d bytes differ from packed_half" % (
                              ps, d, len(want)))
                    if ps != 2 or d:
                        bad.append("own-size posters halved: scale %d, %d "
                                   "bytes differ" % (ps, d))
                else:
                    cv = vid.decode_at(r, r.key(r.poster)[0])
                    want = vid.vga4_pack(cv, W, H, ps,
                                         vid.vga4_xlat(r.palette))[0]
                    d = sum(1 for a, b in zip(poster(len(want)), want)
                            if a != b)
                    print("   3. none stored, shown at %d: %d of %d bytes "
                          "differ from vga4_pack" % (ps, d, len(want)))
                    if ps != 2 or d:
                        bad.append("no posters stored: scale %d, %d bytes "
                                   "differ" % (ps, d))
                ui.menu_pick("Video Player", "Close")
    for b in bad:
        print("   FAIL: %s" % b)
    if not bad:
        print("   ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
