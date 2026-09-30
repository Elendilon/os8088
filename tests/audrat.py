#!/usr/bin/env python3
"""AUDIO'S RATCHET LISTENING BUILD STILL BUILDS AND ENGAGES - `make audrat`.

    make audrat && python3 tests/audrat.py [--pkg build/AUDRAT.O88]

-DAPS_RATCHET is a listening build (docs/plans/SPEAKER-LEVELLER-NEXT.md, the
Audio item under candidate 1): one level a track on the speaker, Tracker's
ratchet, for the owner's A/B against the shipped AUDIO.O88. It is %ifdef'd
out of everything that ships, so nothing else would notice it rot while it
waits for an ear; this row is what does. It boots the card-less 5150 with
AUDRAT.O88 and a WAV of tests/apspk.py's deterministic song (a bass, a moving
line, a noise burst and a gap of silence - every level and the gate) and
reads the shaper's own bytes through the play. What must hold:

  1. the ratchet is ENGAGED (os88spkfx_rat = 1) all through the play;
  2. the level starts at 8 or under (APS_LSTART) and NEVER RISES - it only
     steps down, and a song's quiet stretch does not bring it back up;
  3. the play runs to the list's end (the session closed).

Broken on purpose - --pkg build/audio.o88, the shipped player, which
levels per span - it FAILS at 1 (the ratchet is 0) and at 2 (the level
moves both ways).
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88marty, os88ui, os88build                  # noqa: E402
import os88geom as geom                              # noqa: E402
from cycweb import pkg_syms                          # noqa: E402
import apspk                                         # noqa: E402

SECS = 20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", default=None)
    a = ap.parse_args()
    os.chdir(ROOT)
    pkg = a.pkg or os88build.at("build/AUDRAT.O88")
    syms, _ = pkg_syms("apps/audio/audio.asm", ("apps/", "apps/audio/"),
                       ["APS_RATCHET"])
    bad, reads = [], []
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "build")) as tmp:
        w = os.path.join(tmp, "SONG.WAV")
        apspk.wav(w, 8000, apspk.song(8000 * SECS, 8000))
        vhd = os.path.join(tmp, "a.vhd")
        subprocess.run(
            [sys.executable, "tools/os88hdd.py", "--template", apspk.TEMPLATE,
             "--out", vhd, "--kernel", os88build.at("build/kernel.sys"),
             "--vbr", os88build.at("build/boothd.bin"),
             "--mbr", os88build.at("build/mbr.bin"),
             "--file", "AUDIO.O88=" + pkg, "--file", "SONG.WAV=" + w],
            check=True, capture_output=True)
        m = os88marty.launch(None, machine=apspk.MACHINE,
                             extra=["--mount", "hd:0:" + os.path.abspath(vhd)])
        try:
            ui = os88ui.UI(m)
            ui.ready(limit=240)
            win = ui.path("C:/SONG.WAV")
            rec = m.read(ui._S("wm_wins") + win.i * geom.WIN_SIZE,
                         geom.WIN_SIZE)
            base = (rec[geom.W_SEG] | rec[geom.W_SEG + 1] << 8) << 4
            rb = lambda n: m.read(base + syms[n], 1)[0]
            os88marty.until(m, lambda mm: rb("aps_on") == 1, "the play",
                            poll=0.2, limit=120.0)
            ended = False
            for _ in range(80):
                os88marty.pace(m, 0.25)     # ~1 s of the guest's
                if rb("aps_on") == 0 and rb("ap_state") == 0:
                    ended = True
                    break
                reads.append((rb("os88spkfx_rat"), rb("os88spkfx_lev")))
        finally:
            m.close()
    levs = [lv for r, lv in reads]
    print("   %d readings through the play: ratchet %s, levels %s"
          % (len(reads), sorted(set(r for r, lv in reads)), levs))
    if not reads or any(r != 1 for r, lv in reads):
        bad.append("1: the ratchet is not engaged all through the play")
    if not levs or levs[0] > 8 or any(b > a_ for a_, b in zip(levs, levs[1:])):
        bad.append("2: the level did not start at 8 or under and only fall")
    if not ended:
        bad.append("3: the play did not run to the list's end")
    for b in bad:
        print("   FAIL " + b)
    print("audrat: %s" % ("FAIL" if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
