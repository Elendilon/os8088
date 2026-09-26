#!/usr/bin/env python3
"""The encoder front end and its budgets - SPEC.md 98.2.1, VIDEO-PLAN W8.

    python3 tests/videnc.py

Host-side. ffmpeg makes a source - five seconds of testsrc2, a moving
colour pattern, frozen for its last two, 16:9, with a tone - and
tools/os88venc.py encodes it three ways. Four questions:

1. IS THE CANVAS THE SOURCE'S SHAPE? 16:9 in the Hercules preset's
   400 x 200 box, whose pixels are 29:45, is 400 x 145 - worked here from
   the aspect, not read back from the tool.
2. WITH NO LIMITS, IS EVERY FRAME THE TARGET? The lossless profile's file,
   decoded frame by frame, must equal the dithered target of every frame,
   exactly - the stream is the target when nothing stops it.
3. UNDER TIGHT LIMITS, ARE THEY KEPT? A 20 KB/s disk and a 30%/50% CPU
   must CUT frames (or this tests nothing), and then every record, priced
   by the wave 0 model on its actual bytes, is under the per-frame ceiling,
   and a replay of both buckets never goes below empty.
4. DOES IT CONVERGE? Two seconds of a still picture after the motion: the
   last frame on screen must be the target, the errors the budget left all
   fixed.

Broken on purpose - the measured retry in Encoder.frame skipped, so a
frame is chosen by the per-span estimate alone - question 3 FAILS naming
the frame over its ceiling. The whole row needs ffmpeg and numpy, and
SKIPS without them: that is the box declining to answer, not a pass.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88vid as vid                                        # noqa: E402
import os88venc as venc                                      # noqa: E402

SKIP = 77


def main():
    if venc.np is None or not shutil.which("ffmpeg"):
        print("   SKIP: needs ffmpeg and numpy")
        return SKIP
    np = venc.np
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.mkv")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             "testsrc2=size=320x180:rate=30:duration=3,tpad=stop_mode=clone:"
             "stop_duration=2", "-f", "lavfi", "-i",
             "sine=frequency=440:sample_rate=22050", "-t", "5",
             "-c:v", "ffv1", "-c:a", "pcm_s16le", src], check=True)

        def run(name, *args):
            a = venc.parser().parse_args(
                [src, os.path.join(tmp, name + ".V88"), "--quiet"] +
                list(args))
            keep = []
            res = venc.encode(a, keep)
            return a.out, res, keep

        # --- 1: the canvas's shape
        path, res, keep = run("lossless", "--preset", "herc",
                              "--profile", "lossless", "--rate", "11025")
        want_h = round(400 * 29 / 45 / (16 / 9))
        print("   16:9 in Hercules' 400 x 200: %d x %d (want 400 x %d)"
              % (res["w"], res["h"], want_h))
        if (res["w"], res["h"]) != (400, want_h):
            bad.append("the canvas is %d x %d, not 400 x %d"
                       % (res["w"], res["h"], want_h))
        # --- 2: no limits, every frame the target
        vid.verify_v88(path)
        r = vid.Reader(path)
        diff = 0
        for f, surf, rec, at, i in vid.v88_frames(r):
            if r.g.canvas(surf) != keep[f].tobytes():
                diff += 1
        print("   lossless: %d frames, %d differ from their target"
              % (r.frames, diff))
        if diff or r.frames != len(keep):
            bad.append("lossless: %d of %d frames are not their target"
                       % (diff, r.frames))
        # --- 3: tight limits kept
        path, res, keep = run("tight", "--preset", "herc", "--disk", "20000",
                              "--avg", "0.30", "--peak", "0.50", "--rate",
                              "5512")
        vid.verify_v88(path)
        r = vid.Reader(path)
        period, acyc, abps = res["period"], res["audio_cyc"], res["audio_bps"]
        fps = res["fps"]
        peak = 0.50 * period
        cpu_per = 0.30 * period - acyc
        dsk_per = (20000 * 0.99 - abps) / fps
        cpu = venc.Budget(cpu_per, cpu_per * fps)
        dsk = venc.Budget(dsk_per, dsk_per * fps)
        over, cut, low = [], 0, [0.0, 0.0]
        screens = []
        for f, surf, rec, at, i in vid.v88_frames(r):
            cpu.tick()
            dsk.tick()
            c = vid.cycles_of(rec)
            n = len(rec) - r.abytes
            cpu.spend(c)
            dsk.spend(n)
            low = [min(low[0], cpu.level), min(low[1], dsk.level)]
            if c + acyc > peak + 1:
                over.append((f, c + acyc))
            cv = r.g.canvas(surf)
            if cv != keep[f].tobytes():
                cut += 1
            screens.append(cv)
        print("   20 KB/s, 30%%/50%%: %d of %d frames short of their "
              "target; worst frame %.1f%%; lowest buckets: CPU %.0f "
              "cycles, disk %.0f bytes"
              % (cut, r.frames, 100 * max(vid.cycles_of(rec) + acyc
                                         for rec, a_, i_ in r.records())
                 / period, low[0], low[1]))
        if not cut:
            bad.append("the tight profile cut nothing: it tests nothing")
        for f, c in over[:3]:
            bad.append("frame %d costs %.1f%% of its period, over the 50%% "
                       "ceiling" % (f, 100 * c / period))
        if low[0] < -1 or low[1] < -1:
            bad.append("a bucket went below empty (CPU %.0f, disk %.0f)"
                       % tuple(low))
        # --- 4: converged on the still
        last = screens[-1] == keep[-1].tobytes()
        still = sum(1 for f in range(len(keep)) if np.array_equal(
            keep[f], keep[-1]))
        print("   the still's %d frames: the last is its target: %s"
              % (still, "yes" if last else "NO"))
        if not last:
            bad.append("after %d frames of a still picture the screen is "
                       "not its target" % still)
    for b in bad:
        print("   FAIL: %s" % b)
    if not bad:
        print("   ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
