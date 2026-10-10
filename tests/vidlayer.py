#!/usr/bin/env python3
"""THE LAYER (SPEC.md 98.1.9), host-side: a file made for a slow disk with a
second stream on top of it for a faster one.

    python3 tests/vidlayer.py

ffmpeg makes six seconds of a Mandelbrot zoom - every pixel moving every
frame, so a 60 KB/s disk cuts most of them - and each arm encodes it twice for the 286-fast profile
at that disk: once plain, once with `--layer-disk` for 240 KB/s. What it
asserts, per arm:

  - THE BASE IS UNTOUCHED: the layered file's frame records and keyframe
    records are the plain one's byte for byte (only the options block,
    which records the layer's options, and the header's layer words may
    differ). Every player made before plays exactly what it played;
  - verify_v88 passes it, which walks the layer by the writer's rules
    (verify_layer: a record a frame, each super-packet naming its first
    frame, the key table naming each key's next frame);
  - THE DECODE IS THE MODEL: base then layer, frame by frame, ends on the
    exact screen the encoder's layer model ended on - and with ONE layer
    record left out - the last, which nothing after it writes over - it
    does not (the negative control: the check bites);
  - the layer buys something: records in most frames (or fewer, where it
    takes the error under a fifth of the base's), and the enhanced play's
    error as seen below the base's.

Arms: vga8 (LIN320, one plane) and modex (four planes, sub-records), both
for the 286 at 60 KB/s; and xt286, a CGA file for a 5150 at 20 KB/s whose
layer is for the 286 (--layer-profile 286-fast): the layer's machine is
ANOTHER CPU, pricing the base's records at its own speed; and bank486,
BANKED AND LAYERED - a base for the 286 with a 512 KB bank prefilled, its
layer for the 486 - where the yardstick (key 0's decode modelled on each,
SPEC.md 98.1.9) must say the 486 is the faster.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import os88venc as venc                                       # noqa: E402
import os88vid as vid                                         # noqa: E402

SKIP = 77
BASE_DISK, LAYER_DISK = 61440, 245760


def main():
    if venc.np is None or not shutil.which("ffmpeg"):
        print("   SKIP: needs ffmpeg and numpy")
        return SKIP
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mkv")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             "mandelbrot=size=320x180:rate=24,trim=duration=6", "-c:v", "ffv1",
             src], check=True)

        def run(name, *args):
            a = venc.parser().parse_args(
                [src, os.path.join(tmp, name + ".V88"), "--quiet",
                 "--audio", "none"] + list(args))
            return a.out, venc.encode(a)

        # (arm, the base's options, the layer's)
        arms = (("vga8", ["--preset", "vga8", "--profile", "286-fast",
                          "--disk", str(BASE_DISK)],
                 ["--layer-disk", str(LAYER_DISK)]),
                ("modex", ["--preset", "modex", "--profile", "286-fast",
                           "--disk", str(BASE_DISK)],
                 ["--layer-disk", str(LAYER_DISK)]),
                # A FILE FOR A 5150, ITS LAYER FOR A 286 (--layer-profile):
                # the base's records repriced on the 286's CPU
                ("xt286", ["--preset", "cga", "--profile", "5150-st225",
                           "--disk", "20480"],
                 ["--layer-profile", "286-fast", "--layer-disk",
                  str(LAYER_DISK)]),
                # BANKED AND LAYERED: the base for a 286 with an XMS bank,
                # its layer for a 486 - which the player tells apart by the
                # yardstick (key 0's decode on each), read off the header
                ("bank486", ["--preset", "modex", "--profile", "286-fast",
                             "--disk", str(BASE_DISK), "--bank", "512",
                             "--prefill", "all"],
                 ["--layer-profile", "486-dx2-66", "--layer-disk",
                  str(LAYER_DISK)]))
        for arm, bopt, lopt in arms:
            print("\n== arm %s" % arm)
            plain, rp = run(arm + "p", *bopt)
            lay, rl = run(arm + "l", *(bopt + lopt))
            ra, rb = vid.Reader(plain), vid.Reader(lay)
            same = [x[0] for x in ra.records()] == \
                [x[0] for x in rb.records()] and \
                [ra.key(i)[:2] for i in range(ra.nkeys)] == \
                [rb.key(i)[:2] for i in range(rb.nkeys)]
            print("   the base: %d bytes, the layered file %d; its records "
                  "and keys untouched: %s"
                  % (len(ra.d), len(rb.d), same))
            if not same:
                bad.append("%s: the layered file's base differs from the "
                           "plain encode" % arm)
            vid.verify_v88(lay)
            r = vid.Reader(lay)
            print("   the yardstick: key 0 in %.2f ms on the layer's machine, "
                  "%.2f on the base's" % (r.ltl / 100.0, r.ltb / 100.0))
            if not r.ltl or not r.ltb or \
                    (arm in ("xt286", "bank486")) != (r.ltl < r.ltb * 0.8):
                bad.append("%s: the yardstick %d / %d does not tell the two "
                           "machines apart as it should" % (arm, r.ltl, r.ltb))
            if arm == "bank486" and (r.xbank, r.xpre) != (512, 0xFFFF):
                bad.append("bank486: the base's bank %d KB, prefill %x"
                           % (r.xbank, r.xpre))
            L = rl["layer"]
            print("   layer: %.1f KB/s, %d of %d frames; error as seen "
                  "%.2f%% -> %.2f%%"
                  % (L["kbs"], L["recs"], r.frames, 100 * rl["q_vis"],
                     100 * L["q_vis"]))
            if L["recs"] < r.frames // 2 and \
                    L["q_vis"] > rl["q_vis"] / 5:
                bad.append("%s: the layer has records in %d of %d frames"
                           % (arm, L["recs"], r.frames))
            if not L["q_vis"] < rl["q_vis"]:
                bad.append("%s: the layered play %.4f is no better than the "
                           "base's %.4f" % (arm, L["q_vis"], rl["q_vis"]))
            last = None
            for f, surf in vid.v88_layered(r):
                last = r.g.canvas(surf)
            print("   the decode ends on the model's screen: %s"
                  % (last == L["final"]))
            if last != L["final"]:
                bad.append("%s: base then layer does not end on the "
                           "encoder's screen" % arm)
            drop = max(f for f, rec, *_ in r.layer_records()
                       if rec is not None)  # (the last: nothing after it
                                            # writes over what it wrote)
            for f, surf in vid.v88_layered(r, drop=lambda f: f == drop):
                last = r.g.canvas(surf)
            print("   ...with frame %d's layer record left out: %s"
                  % (drop, last == L["final"]))
            if last == L["final"]:
                bad.append("%s: leaving a layer record out changed nothing "
                           "- the decode check cannot see a layer" % arm)
    if bad:
        print("\nvidlayer: FAIL")
        for x in bad:
            print("  - " + x)
        return 1
    print("\nvidlayer: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
