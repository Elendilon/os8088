#!/usr/bin/env python3
"""BONANZA: the frame's cost on MartyPC's 4.77 MHz XT, CGA and Hercules (SPEC.md 128.4, 128.6, 128.8).

    make bonanzadisk && python3 tests/bonanza_perf.py [--adapter cga|herc|both]
    python3 tests/bonanza_perf.py --apps IMG --src DIR --art DIR   (an A/B leg)

--apps/--src/--art point the run at ANOTHER build of the package - a floppy
with its BONANZA.O88, the source it was assembled from and the art directory
it assembled against (the symbols are read by re-assembling that source) -
so an earlier wave's package, built in a private tree, is measured by the
same breakpoints on the same route as the current one (SPEC.md 128.9's A/B
leg against wave 0).

The BENCHMARK (B: the autopilot's fixed route, 1,200 frames, deterministic) is
run under LOGGED breakpoints on the frame marks - bz_t0 bz_ts bz_tr bz_tv bz_tf
bz_tb bz_tc bz_presented - and on the writers bz_row, bz_col and bz_fullw.  A
logged breakpoint notes (address, cycle) and lets the guest run on, so it costs
the guest NO cycle: these are MartyPC's own cycle counts, an XT's 8088 exactly,
with no real CGA or Hercules wait states (docs/FIELD-MACHINES.md is where those
are measured).

Reported per adapter: the frame period (mean, min, max, p99) in clocks and Hz
against the card's own refresh (MartyPC's frame counter over the same run),
how many frames held one refresh, two, or more; each part's mean and share:

    sim+camera     bz_presented .. bz_ts   (the input, the fixed steps, the camera)
    box compose    bz_ts .. bz_tr          (the box in RAM)
    rows           bz_tr .. bz_tv          (entering rows into the slack, rule 1)
    retrace wait   bz_tv .. bz_tf          (IDLE)
    flip+columns   bz_tf .. bz_tb, + bz_tc .. bz_presented
    box write      bz_tb .. bz_tc or .. bz_presented

and the columns, rows and full writes a frame.  The in-package instruments
(bz_r*: the same marks read off PIT channel 0, SPEC.md 128.6) are read after
the run and compared.

ASSERTED, and nothing else: the FLOOR - the display holds at least half the
refresh (mean period <= two refreshes) - and that the package's instruments
agree with the breakpoints: every part's mean and the period within 10% (or
200 clocks, for a part that small), and the frame, column, row and full-write
counts exactly.
"""
import argparse
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import bonanza_ring as R       # noqa: E402

CLK = M.GUEST_HZ
BENCH = 1200                   # bzgame.inc BZ_BENCH
MARKS = ["bz_t0", "bz_ts", "bz_tr", "bz_tv", "bz_tf", "bz_tb", "bz_tc", "bz_presented"]
WRITERS = ["bz_row", "bz_col", "bz_fullw"]
PARTS = ["sim+camera", "box compose", "rows", "retrace wait", "flip+columns", "box write"]
AGREE = 0.10
AGREE_ABS = 200


def frames_of(hits, a):
    """Logged hits (sorted by cycle) -> one record per presented frame."""
    by = {v: k for k, v in a.items()}
    out, cur, last = [], {}, None
    cnt = {n: 0 for n in WRITERS}
    for h in hits:
        n = by.get(h["addr"] & 0xFFFFF)
        c = h["cycles"]
        if n in WRITERS:
            cnt[n] += 1
            continue
        if n != "bz_presented":
            cur[n] = c
            continue
        rec = {"end": c, "period": None if last is None else c - last, "rows": cnt["bz_row"],
               "colcalls": cnt["bz_col"], "full": cnt["bz_fullw"] > 0, "marks": dict(cur)}
        if last is not None and all(k in cur for k in ("bz_ts", "bz_tr", "bz_tv", "bz_tf", "bz_tb")):
            p = {"sim+camera": cur["bz_ts"] - last, "box compose": cur["bz_tr"] - cur["bz_ts"],
                 "rows": cur["bz_tv"] - cur["bz_tr"], "retrace wait": cur["bz_tf"] - cur["bz_tv"]}
            if "bz_tc" in cur:
                p["flip+columns"] = (cur["bz_tb"] - cur["bz_tf"]) + (c - cur["bz_tc"])
                p["box write"] = cur["bz_tc"] - cur["bz_tb"]
            else:
                p["flip+columns"] = cur["bz_tb"] - cur["bz_tf"]
                p["box write"] = c - cur["bz_tb"]
            rec["parts"] = p
        rec["column"] = (cnt["bz_col"] > 0) and not rec["full"]
        out.append(rec)
        last, cur = c, {}
        cnt = {n: 0 for n in WRITERS}
    return out


def stats(xs):
    xs = sorted(xs)
    n = len(xs)
    return {"n": n, "mean": sum(xs) / n, "min": xs[0], "max": xs[-1], "p99": xs[min(n - 1, int(n * .99))]}


def run(tag, apps=None, src=None, art=None):
    sym = R.symbols(src, art)
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym)
        ui.settle()
        m = g.m
        a = {n: g.a(n) for n in MARKS + WRITERS}
        pres = a["bz_presented"]
        with M.bp_trace(m, *[a[n] for n in MARKS + WRITERS], log=True, cap=BENCH * 40 + 20000) as tr:
            g.key("KeyB")
            M.until(m, lambda _: g.b("bz_fs") == 1, "the benchmark starts", guest=60)
            m.pause()
            c0, f0 = m.status()["cycles"], m.cards()[0]["frames"]
            m.run()
            M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark's %d frames" % BENCH, guest=120)
            m.pause()
            c1, f1 = m.status()["cycles"], m.cards()[0]["frames"]
            hits = tr.hits
            assert not tr.overflowed, "the trace overflowed its cap: frames are missing"
            m.run()
        assert g.b("bz_res") == 1 and g.b("bz_err") == 0, "the benchmark did not finish (res %d, err %d)" % (
            g.b("bz_res"), g.b("bz_err"))
        pkg = {"frames": g.w("bz_rframes"), "mfr": g.w("bz_rmfr"), "ncol": g.w("bz_rncol"),
               "nrow": g.w("bz_rnrow"), "nfull": g.w("bz_rnfull"), "miss": g.w("bz_rmiss"),
               "fmax": g.d("bz_rfmax") * 4, "tos": g.w("bz_tos"),
               "acc": [struct.unpack("<I", m.read(g.a("bz_racc") + 4 * i, 4))[0] * 4 for i in range(6)]}
    refresh = (c1 - c0) / float(f1 - f0)
    return report(tag, frames_of(hits, a), pkg, refresh, sum(1 for h in hits if h["addr"] == pres))


def report(tag, fr, pkg, refresh, npres):
    meas = [r for r in fr if not r["full"] and r["period"] is not None and "parts" in r]
    per = stats([r["period"] for r in meas])
    bad = []
    print("\n%s: %d frames presented (%d breakpoint hits at bz_presented), %d measured (not a full write); "
          "the card's refresh %.0f clk = %.2f Hz" % (tag.upper(), len(fr), npres, len(meas), refresh, CLK / refresh))
    print("  period  mean %7.0f clk = %5.2f Hz   min %6d   max %6d   p99 %6d" % (
        per["mean"], CLK / per["mean"], per["min"], per["max"], per["p99"]))
    hold = {}
    for r in meas:
        k = min(3, max(1, int(r["period"] / refresh + 0.5)))
        hold[k] = hold.get(k, 0) + 1
    miss = sum(1 for r in meas if r["period"] > 1.5 * refresh)
    print("  frames held 1 refresh %d, 2 refreshes %d, 3 or more %d;  over 1.5 refreshes (a miss) %d" % (
        hold.get(1, 0), hold.get(2, 0), hold.get(3, 0), miss))
    for i, r in enumerate(fr):
        if r in meas and r["period"] > 1.5 * refresh:
            print("    miss: frame %d, period %d clk (%.2f refreshes): %s; %d rows, %s" % (
                i + 1, r["period"], r["period"] / refresh,
                ", ".join("%s %d" % (p, r["parts"][p]) for p in PARTS), r["rows"],
                "a column" if r["column"] else "no column"))
    print("  %-14s %8s %7s %7s %7s %7s   %s" % ("part", "mean clk", "share", "min", "max", "p99", "package"))
    for i, p in enumerate(PARTS):
        s = stats([r["parts"][p] for r in meas])
        pk = pkg["acc"][i] / float(pkg["mfr"] or 1)
        tol = max(AGREE * s["mean"], AGREE_ABS)
        ok = abs(pk - s["mean"]) <= tol
        print("  %-14s %8.0f %6.1f%% %7d %7d %7d   %8.0f %s" % (
            p, s["mean"], 100.0 * s["mean"] / per["mean"], s["min"], s["max"], s["p99"], pk,
            "" if ok else "<- DISAGREES"))
        if not ok:
            bad.append("%s: package %.0f against breakpoints %.0f" % (p, pk, s["mean"]))
    work = per["mean"] - stats([r["parts"]["retrace wait"] for r in meas])["mean"]
    print("  busy (all but the retrace wait) %.0f clk = %.0f%% of a refresh" % (work, 100.0 * work / refresh))
    ncol = sum(1 for r in fr if r["column"])
    nsplit = sum(1 for r in fr if "bz_tc" in r["marks"])
    nrow = sum(r["rows"] for r in fr)
    nfull = sum(1 for r in fr if r["full"])
    nrow_inc = sum(r["rows"] for r in fr if not r["full"])
    print("  columns %d (%.3f a frame; %d with rows after the boxes, bz_tc), rows %d (%.3f a frame outside full writes), "
          "full writes %d" % (ncol, ncol / float(len(fr)), nsplit, nrow, nrow_inc / float(len(fr)), nfull))
    pkper = sum(pkg["acc"]) / float(pkg["mfr"] or 1)
    print("  package: frames %d, measured %d, period %.0f clk = %.2f Hz, misses %d, worst %d clk, columns %d, "
          "rows %d, full %d, retrace timeouts %d" % (
              pkg["frames"], pkg["mfr"], pkper, CLK / pkper, pkg["miss"], pkg["fmax"], pkg["ncol"],
              pkg["nrow"], pkg["nfull"], pkg["tos"]))
    if abs(pkper - per["mean"]) > max(AGREE * per["mean"], AGREE_ABS):
        bad.append("period: package %.0f against breakpoints %.0f" % (pkper, per["mean"]))
    for what, got, want in (("frames", pkg["frames"], len(fr)), ("measured frames", pkg["mfr"], len(meas)),
                            ("columns", pkg["ncol"], ncol), ("rows", pkg["nrow"], nrow),
                            ("full writes", pkg["nfull"], nfull)):
        if got != want:
            bad.append("%s: package %d against breakpoints %d" % (what, got, want))
    floor = 2 * refresh
    print("  FLOOR: mean period %.0f <= two refreshes %.0f (%.2f Hz, half the refresh): %s" % (
        per["mean"], floor, CLK / floor, "held" if per["mean"] <= floor else "MISSED"))
    if per["mean"] > floor:
        bad.append("the display holds %.2f Hz, under half the refresh (%.2f)" % (CLK / per["mean"], CLK / floor))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--apps", help="the B: floppy to run instead of build/bonanza360.img")
    ap.add_argument("--src", help="the package source that floppy was built from (default apps/bonanza)")
    ap.add_argument("--art", help="the art directory that source assembled against (default build/bonanza-art)")
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    allbad = []
    for tag in tags:
        bad = run(tag, a.apps, a.src, a.art)
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d failure(s)" % len(allbad)
    print("\nbonanza_perf (%s): PASS" % ", ".join(tags))


if __name__ == "__main__":
    main()
