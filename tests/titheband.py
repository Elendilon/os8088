#!/usr/bin/env python3
"""WAVE 0 of docs/plans/TITHE-PLAN.md: run the band bench on all three adapters.

    make && make titheband && python3 tests/titheband.py

TITHE's whole frame budget rests on one derived constant - 6.15 us a band byte
- and that constant comes from PERFORMANCE.md Set 77's measurement of a
**128x128** band, which is sixteen bytes a row. A 56x56 sprite is seven. If
`gfx_blit1` charges anything per ROW, a per-byte figure taken at the widest
shape in the system is the reading most favourable to the plan, and every
budget downstream of it moves.

`tests/titheband/titheband.asm` is what asks. This drives it, on each adapter
in turn, and brings the three reports back HERE - `bl_save` writes them to the
bench floppy and MartyPC keeps the guest's writes in RAM, so `os88flush` is
what spends them.

**THE COMPARISON ACROSS ADAPTERS IS THE POINT, NOT THE VGA RUN.** Two of the
rows are only meaningful as a cross-adapter pair:

  * the four PEN rows must LAND ON EACH OTHER on Hercules and CGA. SPEC.md
    5.4.2.2 says the pen is not read on a 1bpp adapter - a band there already
    means lit and unlit - so a gap there is a defect, and it is a defect
    nothing else in the tree would notice.
  * the three BLITP rows must REFUSE on Hercules and CGA. A refusal costs
    almost nothing, so from the microsecond column alone a refusal and a very
    fast blit are the same thing. The bench prints the CF answer in words and
    this checks the words.

So the summary at the end is three columns, and the checks are about the
SHAPE of the three rather than about any one number.

Not a suite row and deliberately not: it is minutes on three machines and its
output is a measurement, which belongs in a dated docs/reports/ file and is
true of the tree it was taken on and of no other.
"""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)
import os88marty, os88flush, os88ui                            # noqa: E402

# benchlib's column layout (tests/benchlib.inc, BL_C_*), read here rather than
# guessed: a label runs to column 24, the iteration count to 29, the counts to
# 38, the microseconds to 51, and column 55 is the flag.
C_N, C_CNT, C_US, C_FLAG = 24, 30, 39, 55
FRAME_US = 54925.0

ADAPTERS = [
    # name     machine                  the file the guest writes
    ("vga",   "os8088_xt_vga",          "TITHVGA.TXT"),
    ("herc",  "os8088_5150_herc_gla",   "TITHHERC.TXT"),
    ("cga",   "os8088_5150_cga_gla",    "TITHCGA.TXT"),
]

SET77_BAR_US = 12588.15     # PERFORMANCE.md Set 77, GFX_BLIT1 128x128
FAIL = []


def check(ok, what):
    print("   %-62s %s" % (what, "ok" if ok else "FAIL"))
    if not ok:
        FAIL.append(what)


def parse(text):
    """The report's rows, as {label: (n, counts, us, flag)}."""
    rows = {}
    for ln in text.splitlines():
        if len(ln) < C_US:
            continue
        label = ln[:C_N].strip()
        if not label or label.startswith("-") or label.startswith("="):
            continue
        us = ln[C_US:C_US + 13].strip()
        try:
            v = float(us)
        except ValueError:
            continue
        n = ln[C_N:C_CNT].strip()
        cnt = ln[C_CNT:C_US].strip()
        flag = ln[C_FLAG:C_FLAG + 1] if len(ln) > C_FLAG else " "
        rows[label] = (n, cnt, v, flag.strip())
    return rows


def words(text, label):
    """A bl_kvs line: the word in the value column rather than a number."""
    for ln in text.splitlines():
        if ln[:C_N].strip() == label:
            return ln[C_N:].strip()
    return None


def run_one(name, machine, fname, image, apps, out_dir, limit, pkg):
    print("\n== %s (%s) ==" % (name.upper(), machine))
    with os88ui.boot(image, apps=apps, machine=machine) as ui:
        m = ui.m
        f = os88flush.Flush(marty=m)
        ui.path("B:/" + pkg)
        w = ui.wait_window("Tithe Band Bench")
        print("   window up; running (this is ~30 guest seconds)")
        m.key("KeyR")

        # Poll the FLOPPY rather than the screen. The run ends by writing the
        # report, so the file appearing IS the completion signal - and it is
        # the same fact the result is read from, so there is no window in
        # which the script believes a run finished that did not.
        t0 = time.time()
        text = None
        while time.time() - t0 < limit:
            time.sleep(4.0)
            try:
                v = f.volume(1)
                if fname in v.names():
                    text = v.read(fname).decode("latin-1")
                    break
            except Exception as e:                        # a mid-write grab
                print("   (flush: %s)" % e)
        if text is None:
            raise RuntimeError("%s: %s never appeared in %.0fs"
                               % (name, fname, limit))
        print("   report: %d bytes, %d lines after %.0fs"
              % (len(text), len(text.splitlines()), time.time() - t0))

    path = os.path.join(out_dir, fname)
    open(path, "w").write(text)
    print("   wrote %s" % path)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default=None)
    ap.add_argument("--quick", action="store_true",
                    help="the -DTBQUICK disk: the same rows at a handful of "
                         "iterations, a couple of guest seconds, numbers too "
                         "coarse to quote. For sizing and for a smoke test")
    ap.add_argument("--out", default=None,
                    help="where the three reports land (default: a temp dir)")
    ap.add_argument("--adapter", action="append",
                    choices=[a[0] for a in ADAPTERS],
                    help="just this one; repeatable")
    ap.add_argument("--limit", type=float, default=300.0,
                    help="host seconds to wait for the report file")
    a = ap.parse_args()

    if a.apps is None:
        a.apps = ("build/tithequick360.img" if a.quick
                  else "build/titheband360.img")
    pkg = "TITHEBNQ.O88" if a.quick else "TITHEBND.O88"
    out_dir = a.out or os.path.join(os.environ.get("TMPDIR", "/tmp"), "titheband")
    os.makedirs(out_dir, exist_ok=True)
    want = a.adapter or [x[0] for x in ADAPTERS]

    reports = {}
    for name, machine, fname in ADAPTERS:
        if name not in want:
            continue
        reports[name] = run_one(name, machine, fname, a.image, a.apps,
                                out_dir, a.limit, pkg)

    # =========================================================================
    # the summary: three columns, because the shape is the finding
    # =========================================================================
    cols = [n for n, _, _ in ADAPTERS if n in reports]
    parsed = {n: parse(reports[n]) for n in cols}
    labels = []
    for n in cols:
        for k in parsed[n]:
            if k not in labels:
                labels.append(k)

    print("\n%s" % ("=" * 72))
    print("us per operation, by adapter")
    print("=" * 72)
    print("%-24s %s" % ("row", "".join("%14s" % c for c in cols)))
    for k in labels:
        cells = ""
        for n in cols:
            r = parsed[n].get(k)
            cells += "%14s" % ("%.2f%s" % (r[2], r[3]) if r else "-")
        print("%-24s %s" % (k, cells))

    print("\n%s" % ("=" * 72))
    print("what the shape says")
    print("=" * 72)

    for n in cols:
        p, t = parsed[n], reports[n]

        # 1. THE BAR. Two harnesses that disagree about the same primitive on
        # the same machine is the finding, and nothing below it is to be
        # believed until this agrees. bandbench's own discipline.
        bar = p.get("BLIT1 128x128 bar")
        if bar and n == "vga":
            d = abs(bar[2] - SET77_BAR_US) / SET77_BAR_US
            check(d < 0.15, "%s: the 128x128 bar is within 15%% of Set 77's "
                            "%.0f us (got %.0f, %+.1f%%)"
                            % (n, SET77_BAR_US, bar[2], 100 * (bar[2] / SET77_BAR_US - 1)))

        # 2. THE PEN, on a 1bpp adapter, is NOT READ - so the four rows must
        # land on each other. This is the check nothing else in the tree makes.
        if n != "vga":
            pen = [p.get(k) for k in ("BLIT1 pen default", "BLIT1 pen ink/black",
                                      "BLIT1 pen black/white",
                                      "BLIT1 pen split 8on7")]
            if all(pen):
                v = [x[2] for x in pen]
                spread = (max(v) - min(v)) / max(min(v), 1e-9)
                check(spread < 0.05,
                      "%s: the four pen paths agree to 5%% (spread %.1f%%) - "
                      "the pen is not read on 1bpp" % (n, 100 * spread))

        # 3. ...and BLITP refuses there. In WORDS, because a refusal and a
        # fast blit are the same number.
        cf = words(t, "GFX_BLITP 56x56")
        if n == "vga":
            check(cf is not None and cf.startswith("DRAWN"),
                  "%s: GFX_BLITP drew (%s)" % (n, cf))
        else:
            check(cf is not None and cf.startswith("REFUSED"),
                  "%s: GFX_BLITP refused (%s)" % (n, cf))

        # 4. THE FULLSCREEN ARM must have run AND drawn the right pixels. A
        # hand-rolled row loop that is fast and wrong is the easy mistake, and
        # its time would look like the win it is there to measure.
        rb = words(t, "FSX read-back says")
        check(rb is not None and rb.startswith("MATCH"),
              "%s: the fullscreen own-loop drew the right pixels (%s)" % (n, rb))

        # 5. and the row that answers the brief at all: did the wheel run?
        for lbl, what in (("WHEEL 23x adapter", "23 bands, one each"),
                          ("WHEEL 13x paired", "as 13 lane-pairs"),
                          ("FSX own loop 23x", "fullscreen, our own loop"),
                          ("FSX own 23x dirty", "...and dirty rects too")):
            wh = p.get(lbl)
            if wh and wh[2] > 0:
                print("   %-4s %-26s %8.2f ms = %6.1f%% of a frame"
                      % (n, what, wh[2] / 1000.0, 100.0 * wh[2] / FRAME_US))

    print("\n%s" % ("=" * 72))
    if FAIL:
        print("FAILED %d:" % len(FAIL))
        for x in FAIL:
            print("  - " + x)
        return 1
    print("all checks ok - the reports are in %s" % out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
