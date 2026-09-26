#!/usr/bin/env python3
"""The encoder's window, without a window - VIDEO-PLAN 14.2 (E1-E4),
tools/os88vencgui.py.

    python3 tests/vencguitest.py

Host-side. Everything the window does short of drawing is ordinary data,
so it is checked here with no Tk at all:

1. EVERY OPTION IS ON A TAB, WITH A TOOLTIP: the window's table against
   os88venc.parser(), each option once, none without its help - and every
   tab the table names is one of the window's.
2. THE DEFAULTS ARE THE ENCODER'S: the form left alone makes a command line
   that parses to the parser's own defaults, option for option.
3. EVERY TARGET ENCODES: each "made for" choice, on a second of ffmpeg's
   testsrc2, is a file os88vid verifies, of the format and layout it says -
   and a Live one a live file naming its screen.
4. THE PREVIEW IS THE SCREEN'S SHAPE: every frame of every target rendered,
   each at its file's pixel aspect - a 4:3 screen's canvas comes out 4:3 -
   and a CGA4 frame in its own four colours.
5. MAKE A DISK makes one: the image holds the video (and VIDEO.O88 when it
   is built).

Broken on purpose - an option dropped from the table, or a help string
emptied - 1 FAILS naming it. Needs ffmpeg for 3 to 5 and SKIPS without it.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88venc as V                                         # noqa: E402
import os88vencgui as G                                      # noqa: E402
import os88vid as vid                                        # noqa: E402

SKIP = 77


def main():
    bad = []
    # --- 1
    fl = G.fields()
    dests = [f["dest"] for f in fl]
    opts = [a.dest for a in V.parser()._actions
            if a.option_strings and a.dest not in G.HIDDEN]
    missing = sorted(set(opts) - set(dests))
    twice = sorted(d for d in set(dests) if dests.count(d) > 1)
    notip = [f["flag"] for f in fl if not f["tip"]]
    tabs = sorted({f["tab"] for f in fl} - set(G.TABS))
    stale = sorted(set(G.TAB_OF) - set(opts))
    print("   %d options on %d tabs; %d missing, %d twice, %d without a "
          "tooltip, %d tab names unknown, %d placings for no option"
          % (len(fl), len({f["tab"] for f in fl}), len(missing), len(twice),
             len(notip), len(tabs), len(stale)))
    for what, lst in (("missing from the window", missing),
                      ("on the window twice", twice),
                      ("with no tooltip", notip), ("on no tab", tabs),
                      ("placed but not an option", stale)):
        if lst:
            bad.append("options %s: %s" % (what, " ".join(lst)))
    # --- 2
    vals = {f["dest"]: f["default"] for f in fl}
    a = V.parser().parse_args(G.argv_from("in.mp4", "out.V88", vals))
    d = V.parser().parse_args(["in.mp4", "out.V88"])
    diff = [k for k in vars(d) if getattr(a, k) != getattr(d, k)]
    print("   the untouched form: %d options differ from the parser's "
          "defaults" % len(diff))
    if diff:
        bad.append("the untouched form changes %s" % " ".join(diff))
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        for b in bad:
            print("   FAIL: %s" % b)
        print("   SKIP: no ffmpeg for 3 to 5")
        return 1 if bad else SKIP
    # --- 3, 4, 5
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "build")) as tmp:
        src = os.path.join(tmp, "src.mp4")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", "testsrc2=duration=1:size=320x240:rate=15",
                        src], check=True)
        text, sv = G.suggest(src)
        print("   the source: %s; suggested %s" % (text, sv))
        if sv.get("audio") != "none":
            bad.append("a silent source did not suggest no sound")
        for i, (label, preset, pixfmt, profile, extra) in \
                enumerate(G.TARGETS):
            v = dict(vals)
            v.update(sv)
            v.update(G.target_values(i))
            if pixfmt == "cgacomp":
                v["comp_quick"] = "1"       # (the gate's time, not its point)
            out = os.path.join(tmp, "T%d.V88" % i)
            argv = G.argv_from(src, out, v) + ["--quiet"]
            try:
                V.encode(V.parser().parse_args(argv))
                vid.verify_v88(out)
            except Exception as e:
                bad.append("%s: %s" % (label, e))
                continue
            r, frames = G.preview_frames(out)
            w, h = frames[0][1].size
            an, ad = r.aspect
            ratio = w / float(h)
            # the canvas's own display shape: its pixels times their aspect
            px = r.g.wb * (4 if r.pixfmt == vid.PF_CGA4 else
                           vid.PIX_PER_BYTE[r.g.layout])
            shape = px * an / float(ad) / (r.g.h * r.rowscale)
            print("   %-58s %s on %s, %d frames, preview %d x %d"
                  % (label, vid.PF_NAMES[r.pixfmt], r.g.name, len(frames),
                     w, h))
            if len(frames) != r.frames or abs(ratio - shape) > 0.02:
                bad.append("%s: the preview is %d x %d for a %.3f:1 canvas"
                           % (label, w, h, shape))
            if extra.get("live") and not (r.live and r.target ==
                                          vid.TARGETS[extra["live"]]):
                bad.append("%s: not a live file for its screen" % label)
            if pixfmt and vid.PF_NAMES[r.pixfmt].lower() != \
                    {"mono": "mono1"}.get(pixfmt, pixfmt):
                bad.append("%s: made %s" % (label, vid.PF_NAMES[r.pixfmt]))
            if r.pixfmt == vid.PF_CGA4:
                import numpy as np
                cols = {tuple(c) for c in np.asarray(
                    frames[-1][1]).reshape(-1, 3).tolist()}
                own = {tuple(G._rgb16()[c]) for c in
                       vid.cga4_colours(r.cgapal)}
                if not cols <= own:
                    bad.append("the CGA4 preview has colours its palette "
                               "has not: %s" % sorted(cols - own)[:4])
        cmd, img = G.disk_argv(os.path.join(tmp, "T0.V88"), 360)
        p = subprocess.run(cmd, capture_output=True, text=True)
        ls = subprocess.run([sys.executable,
                             os.path.join(ROOT, "tools", "os88disk.py"),
                             "--verify", img], capture_output=True,
                            text=True)
        print("   make a disk: %s" % (ls.stdout.strip() or p.stderr.strip()))
        if p.returncode or ls.returncode:
            bad.append("make a disk failed: %s" % (p.stderr or ls.stderr))
    for b in bad:
        print("   FAIL: %s" % b)
    if not bad:
        print("   ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
