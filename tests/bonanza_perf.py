#!/usr/bin/env python3
"""BONANZA: the frame's cost on MartyPC's 4.77 MHz XT, CGA and Hercules (SPEC.md 128.4, 128.6, 128.8, 128.10.11.3).

    make bonanzadisk && python3 tests/bonanza_perf.py [--adapter cga|herc|both] [--ab [COMMIT]]
    python3 tests/bonanza_perf.py --apps IMG --src DIR --art DIR   (another build, by hand)

--ab builds an EARLIER wave's package - wave 0b's, commit 5c398695, by
default - in a private temporary tree with ITS OWN art: that commit's
apps/bonanza/, apps/os88*.inc and tools/bonanza_assets.py out of git (`git
archive`), its generator run into the tree, assembled and packed with that
wave's part order and put on a 360KB floppy there (never build/).  The same
breakpoints then run on its benchmark too, and the two are printed side by
side: SPEC.md 128.10.11.3's A/B leg, wave 1 against wave 0b.  The legs run
different COURSES (wave 0b's generated one, wave 1's BENCH under physics),
so the comparison is of a frame's cost on each wave's own benchmark.  When
COMMIT is not in the clone (upstream squash-merges; a shallow clone) the A/B
leg is skipped with a line saying so, and wave 1 runs alone.

--apps/--src/--art point the run at ANOTHER build by hand - a floppy with its
BONANZA.O88, the source it was assembled from and the art directory it
assembled against (the symbols are read by re-assembling that source).

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
the run and compared.  Wave 1's three more are reported, not asserted
(SPEC.md 128.10.8 item 1, 128.10.9): the boxes composed with the occluder
pass gated on (bz_rnocf - the frames with OCC set, a two-box frame twice),
the records it laid (bz_rnlay) and the two-box frames (bz_rn2bx).

ASSERTED, and nothing else: the FLOOR - the display holds at least half the
refresh (mean period <= two refreshes) - and that the package's instruments
agree with the breakpoints: every part's mean and the period within 10% (or
200 clocks, for a part that small), and the frame, column, row and full-write
counts exactly.
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile

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
AB_COMMIT = "5c398695"         # wave 0b (SPEC.md 128.9)
AB_PARTS = ("BZCRSC.BIN", "BZCRSH.BIN", "BZBALC.BIN", "BZBALH.BIN")   # its Makefile's BZ_PARTS order


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
            g.check_base()
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
        for n in ("bz_rnocf", "bz_rnlay", "bz_rn2bx", "bz_rlate"):      # wave 1's (wave 0b: some absent)
            if n in sym:
                pkg[n[4:]] = g.w(n)
    refresh = (c1 - c0) / float(f1 - f0)
    return report(tag, frames_of(hits, a), pkg, refresh, sum(1 for h in hits if h["addr"] == pres))


def report(tag, fr, pkg, refresh, npres):
    """-> (failures, the summary bonanza_perf's A/B prints)"""
    meas = [r for r in fr if not r["full"] and r["period"] is not None and "parts" in r]
    per = stats([r["period"] for r in meas])
    bad = []
    summ = {"refresh": refresh, "period": per["mean"], "parts": {}, "pkg": pkg}
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
        summ["parts"][p] = s["mean"]
        print("  %-14s %8.0f %6.1f%% %7d %7d %7d   %8.0f %s" % (
            p, s["mean"], 100.0 * s["mean"] / per["mean"], s["min"], s["max"], s["p99"], pk,
            "" if ok else "<- DISAGREES"))
        if not ok:
            bad.append("%s: package %.0f against breakpoints %.0f" % (p, pk, s["mean"]))
    work = per["mean"] - stats([r["parts"]["retrace wait"] for r in meas])["mean"]
    summ["busy"] = work
    summ["miss"] = sum(1 for r in meas if r["period"] > 1.5 * refresh)
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
    if "nocf" in pkg:
        print("  occluders and boxes (SPEC.md 128.10.8, reported): boxes with the pass gated on %d, records "
              "laid %d (%.2f a gated box), two-box frames %d, late row-0 boxes %s" % (
                  pkg["nocf"], pkg["nlay"], pkg["nlay"] / float(pkg["nocf"] or 1), pkg["n2bx"],
                  pkg.get("late", "-")))
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
    return bad, summ


def reachable(commit):
    """True when COMMIT is in this clone - upstream squash-merges (CLAUDE.md, fork
    rule 7), so after BONANZA lands as one squash no clone of main has wave 0b's
    commit, and a shallow clone may not either (tests/waverackdisk.py's guard)"""
    return subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=R.ROOT,
                          capture_output=True).returncode == 0


def ab_tree(td, commit=AB_COMMIT):
    """An earlier wave's package with ITS OWN art, built in TD out of git:
    -> (floppy, source dir, art dir)."""
    w = os.path.join(td, "w")
    os.makedirs(w)
    names = subprocess.run(["git", "ls-tree", "--name-only", commit, "apps/"], cwd=R.ROOT, check=True,
                           capture_output=True, text=True).stdout.split()
    incs = [n for n in names if n.startswith("apps/os88") and n.endswith(".inc")]
    tar = os.path.join(td, "w.tar")
    subprocess.run(["git", "archive", "-o", tar, commit, "apps/bonanza", "tools/bonanza_assets.py"] + incs,
                   cwd=R.ROOT, check=True)
    with tarfile.open(tar) as tf:
        tf.extractall(w)
    art = os.path.join(td, "art")
    subprocess.run([sys.executable, os.path.join(w, "tools", "bonanza_assets.py"), "-o", art], cwd=w, check=True,
                   stdout=subprocess.DEVNULL)
    src = os.path.join(w, "apps", "bonanza")
    binp, o88, img = (os.path.join(td, n) for n in ("bonanza.bin", "BONANZA.O88", "bonanza360.img"))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(w, "apps") + "/", "-I", src + "/",
                    "-I", art + "/", "-o", binp, os.path.join(src, "bonanza.asm")], cwd=R.ROOT, check=True)
    parts = []
    for p in AB_PARTS:
        parts += ["--part", os.path.join(art, p)]
    subprocess.run([sys.executable, "tools/os88pkg.py", "--compress-if=lz4", binp, "-o", o88] + parts,
                   cwd=R.ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "tools/os88disk.py", "-o", img, "--size", "360", o88], cwd=R.ROOT,
                   check=True, stdout=subprocess.DEVNULL)
    return img, src, art


def ab_print(tag, new, old, commit):
    print("\n%s A/B: wave 1 (this tree) against %s, each on its own benchmark" % (tag.upper(), commit))
    print("  %-14s %9s %9s %9s" % ("", "wave 1", commit, "delta"))
    for p in PARTS + ["busy", "period"]:
        a = new["parts"][p] if p in PARTS else new[p]
        b = old["parts"][p] if p in PARTS else old[p]
        print("  %-14s %9.0f %9.0f %+9.0f" % (p, a, b, a - b))
    print("  %-14s %8.1f%% %8.1f%%" % ("busy share", 100.0 * new["busy"] / new["refresh"],
                                        100.0 * old["busy"] / old["refresh"]))
    print("  %-14s %9d %9d" % ("misses", new["miss"], old["miss"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--apps", help="the B: floppy to run instead of build/bonanza360.img")
    ap.add_argument("--src", help="the package source that floppy was built from (default apps/bonanza)")
    ap.add_argument("--art", help="the art directory that source assembled against (default build/bonanza-art)")
    ap.add_argument("--ab", nargs="?", const=AB_COMMIT, metavar="COMMIT",
                    help="also measure COMMIT's package (default %s, wave 0b) built with its own art" % AB_COMMIT)
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    allbad = []
    if a.ab and not reachable(a.ab):
        print("bonanza_perf: %s is not in this clone's history (a squash merge or a shallow clone): the A/B "
              "leg is SKIPPED and wave 1 runs alone - SPEC.md 128.9 records wave 0b's figures (busy 34,476 clk "
              "CGA, 34,821 Hercules) as the reference" % a.ab, flush=True)
        a.ab = None
    td = tempfile.mkdtemp(prefix="bzab") if a.ab else None
    try:
        ab = ab_tree(td, a.ab) if a.ab else None
        for tag in tags:
            bad, summ = run(tag, a.apps, a.src, a.art)
            for b in bad:
                print("FAIL %s: %s" % (tag, b))
            allbad += bad
            if ab:
                obad, osumm = run(tag, *ab)
                for b in obad:
                    print("FAIL %s (%s): %s" % (tag, a.ab, b))
                allbad += ["%s: %s" % (a.ab, b) for b in obad]
                ab_print(tag, summ, osumm, a.ab)
    finally:
        if td:
            shutil.rmtree(td, ignore_errors=True)
    assert not allbad, "%d failure(s)" % len(allbad)
    print("\nbonanza_perf (%s%s): PASS" % (", ".join(tags), ", A/B against %s" % a.ab if a.ab else ""))


if __name__ == "__main__":
    main()
