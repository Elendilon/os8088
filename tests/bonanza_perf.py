#!/usr/bin/env python3
"""BONANZA: the frame's cost on MartyPC's 4.77 MHz XT, CGA and Hercules (SPEC.md 128.4, 128.10.11.3, 128.11.15, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_perf.py [--adapter cga|herc|both] [--ab [COMMIT]] [--no-trial]
    python3 tests/bonanza_perf.py --apps IMG --src DIR --art DIR   (another build, by hand)

THE BENCHMARK (B: BENCH, the autopilot's fixed route, 1,200 frames,
deterministic) is run under LOGGED breakpoints on the frame marks - bz_t0
bz_ts bz_tr bz_tv bz_tf bz_tb bz_tc bz_presented (wave 2's bz_tcmid, the
column's rows between two boxes, has no mark: they are the box write's) - and
on the writers bz_row,
bz_col, bz_fullw and bz_boxw.  A logged breakpoint notes (address, cycle) and
lets the guest run on, so it costs the guest NO cycle: these are MartyPC's own
cycle counts, an XT's 8088 exactly, with no real CGA or Hercules wait states
(docs/FIELD-MACHINES.md is where those are measured).

Each mark CLOSES a part, exactly as the package's own bz_mark does:

    sim+camera     .. bz_ts      (the input, the fixed steps, the camera)
    box compose    .. bz_tr      (the boxes in RAM, the occluder pass)
    rows           .. bz_tv      (entering rows into the slack, rule 1)
    retrace wait   .. bz_tf      (IDLE)
    flip+columns   .. bz_tb, and the column's rows after the last box (.. bz_presented after a bz_tc)
    box write      bz_tb .. bz_tc or bz_presented: every box, and the column's rows
                   between two boxes (bz_tcmid, unmarked)

Reported per adapter: the frame period (mean, min, max, p99) in clocks and Hz
against the card's own refresh (MartyPC's frame counter over the same run),
frames held one refresh, two, or more, each miss's parts; each part's mean
and share; columns, rows, full writes and BOXES a frame (one, two, three,
four - bz_boxw's hits); the package's instruments (bz_r*: the same marks read
off PIT channel 0) after the run, compared.

ASSERTED, and nothing else: the FLOOR - the display holds at least half the
refresh (mean period <= two refreshes) - and that the package's instruments
agree with the breakpoints: every part's mean and the period within 10% (or
200 clocks, for a part that small), and the frame, column, row and full-write
counts exactly.

THE TRIAL LEG (SPEC.md 128.11.17.2): the same benchmark on TRIAL ([bz_crs]
poked at bz_launch's entry), the rubber ball off H's lip and over the gap -
its period, misses (128.11.15's target 0, reported), shadow frames
(bz_rnshd), the frames of one, two, three and four boxes, the bounces
(bz_nbnc), the records laid (bz_rnlay) - and the CAMERA: a log of the same
flight (the chord off H's lip from the start) REPLAYED once in GLIDE and once
in TRICKLE (the benchmark always rolls GLIDE), the rows each mode pans
(bz_row's hits outside full writes) over the bounces (128.11.11.1, O9).

--ab builds an EARLIER wave's package - wave 1's, commit 2df3f469, by default
- in a private temporary tree with ITS OWN art: that commit's apps/bonanza/,
apps/os88*.inc, tools/bonanza_assets.py and tools/bbcourse.py out of git
(`git archive`), its generators run into the tree, assembled and packed with
that wave's part order and put on a 360KB floppy there (never build/).  The
same breakpoints then run on its benchmark too, printed beside wave 2 part
by part.  The commit is FETCHED first when this clone has not got it
(unshallowing a shallow clone, docs/UPSTREAM.md Rule 0; else fetching it from
origin).  If it still cannot be had - upstream squash-merges, so after the
merge no clone of main has it - the A/B leg reports SKIP with the reason and
the row EXITS 77 (tests/m83.py's convention): the suite has no runtime skip,
so os88test scores it as not passing - never a pass, and never 128.10.9's
recorded figures standing in for a measurement.
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
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402

CLK = M.GUEST_HZ
BENCH = 1200                   # bzgame.inc BZ_BENCH
MARKS = ["bz_t0", "bz_ts", "bz_tr", "bz_tv", "bz_tf", "bz_tb", "bz_tc", "bz_presented"]
WRITERS = ["bz_row", "bz_col", "bz_fullw", "bz_boxw"]
PARTS = ["sim+camera", "box compose", "rows", "retrace wait", "flip+columns", "box write"]
CLOSES = {"bz_ts": 0, "bz_tr": 1, "bz_tv": 2, "bz_tf": 3, "bz_tb": 4, "bz_tc": 5}
AGREE = 0.10
AGREE_ABS = 200
AB_COMMIT = "2df3f469"         # wave 1 (SPEC.md 128.10)
SKIP_RC = 77


def frames_of(hits, a):
    """Logged hits (sorted by cycle) -> one record per presented frame.  Every
    mark closes a part (CLOSES; bz_presented closes the box write, or the
    flip+columns part after a bz_tc), as the package's bz_mark accounts."""
    by = {v: k for k, v in a.items()}
    out, last = [], None
    cnt = {n: 0 for n in WRITERS}
    parts = [0] * 6
    marks, tc = {}, False
    prev = None                                 # the last mark's cycle
    for h in hits:
        n = by.get(h["addr"] & 0xFFFFF)
        c = h["cycles"]
        if n in WRITERS:
            cnt[n] += 1
            continue
        if n is None or n == "bz_t0":
            if n:
                marks[n] = c
            continue
        if n != "bz_presented":
            marks[n] = c
            if prev is not None:
                parts[CLOSES[n]] += c - prev
            prev = c
            tc = tc or n == "bz_tc"
            continue
        rec = {"end": c, "period": None if last is None else c - last, "rows": cnt["bz_row"],
               "colcalls": cnt["bz_col"], "full": cnt["bz_fullw"] > 0, "boxes": cnt["bz_boxw"],
               "marks": dict(marks)}
        if last is not None and prev is not None and all(k in marks for k in ("bz_ts", "bz_tr", "bz_tv", "bz_tf",
                                                                                 "bz_tb")):
            parts[4 if tc else 5] += c - prev
            rec["parts"] = dict(zip(PARTS, parts))
        rec["column"] = (cnt["bz_col"] > 0) and not rec["full"]
        out.append(rec)
        last, prev, marks, tc = c, c, {}, False
        parts = [0] * 6
        cnt = {n: 0 for n in WRITERS}
    return out


def stats(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return {"n": 0, "mean": 0.0, "min": 0, "max": 0, "p99": 0}
    return {"n": n, "mean": sum(xs) / n, "min": xs[0], "max": xs[-1], "p99": xs[min(n - 1, int(n * .99))]}


def addrs(g):
    return {n: g.a(n) for n in MARKS + WRITERS if n in g.sym}


def measure(g, crs=None):
    """one benchmark under logged breakpoints: -> (frames, the package's
    instruments, the refresh in clocks, presented hits)"""
    m = g.m
    a = addrs(g)
    pres = a["bz_presented"]
    launch = g.a("bz_launch")
    poked = []

    def on_launch(mm, rec):                     # (a STOP, the guest paused: poke the course)
        if rec["addr"] == launch & 0xFFFFF and crs is not None:
            g.putb("bz_crs", crs)
            poked.append(rec["cycles"])
    with M.bp_trace(m, *(list(a.values()) + [launch]), log=list(a.values()), on_hit=on_launch,
                    cap=BENCH * 48 + 20000) as tr:
        g.key("KeyB")
        M.until(m, lambda _: g.b("bz_fs") == 1, "the benchmark starts", guest=60)
        m.pause()
        g.check_base()
        if crs is not None and (not poked or g.b("bz_crs") != crs):
            raise AssertionError("the benchmark runs course %d, not the poked %d" % (g.b("bz_crs"), crs))
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
    R.dropped(g, "the benchmark")
    pkg = {"frames": g.w("bz_rframes"), "mfr": g.w("bz_rmfr"), "ncol": g.w("bz_rncol"),
           "nrow": g.w("bz_rnrow"), "nfull": g.w("bz_rnfull"), "miss": g.w("bz_rmiss"),
           "fmax": g.d("bz_rfmax") * 4, "tos": g.w("bz_tos"),
           "acc": [struct.unpack("<I", g.m.read(g.a("bz_racc") + 4 * i, 4))[0] * 4 for i in range(6)]}
    for n in ("bz_rnocf", "bz_rnlay", "bz_rn2bx", "bz_rn3bx", "bz_rnshd", "bz_rlate", "bz_nbnc"):
        if n in g.sym:
            pkg[n[4:] if n.startswith("bz_r") else n[3:]] = g.w(n)
    refresh = (c1 - c0) / float(f1 - f0)
    return frames_of(hits, a), pkg, refresh, sum(1 for h in hits if h["addr"] == pres)


def run(tag, apps=None, src=None, art=None, trial=True):
    """-> [(label, failures, summary)] for BENCH, and TRIAL and the camera when TRIAL"""
    sym = R.symbols(src, art)
    out = []
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym)
        ui.settle()
        fr, pkg, refresh, npres = measure(g)
        out.append(("BENCH",) + report(tag, fr, pkg, refresh, npres))
        if trial and "bz_rlog" in sym:
            fr, pkg, refresh, npres = measure(g, crs=R.CRS_K["trial"])
            bad, summ = report(tag + " TRIAL", fr, pkg, refresh, npres)
            out.append(("TRIAL", bad, summ))
            summ["camera"] = camera(g, tag)
    return out


def camera(g, tag):
    """the rows each camera mode pans over TRIAL's bounces: a log of the chord off
    H's lip from the start, replayed in GLIDE and in TRICKLE (the benchmark
    always rolls GLIDE).  Reported, not asserted (O9)."""
    m = g.m
    keys = [0] * 4 + [BB.K_R | BB.K_D] * 260
    log = BB.encode_log(keys, course=R.CRS_K["trial"], mat=R.course("trial").ball)
    res = {}
    for mode, name in ((0, "GLIDE"), (1, "TRICKLE")):
        m.pause()
        g.write_log(log)
        g.putb("bz_cmode", mode)
        with M.bp_trace(m, g.a("bz_row"), g.a("bz_fullw"), log=True, cap=20000) as tr:
            g.key("KeyR")
            M.until(m, lambda _: g.b("bz_fs") == 1, "the camera's replay starts", guest=60)
            M.until(m, lambda _: g.b("bz_fs") == 0, "the camera's replay ends", guest=120)
            hits = tr.hits
        R.dropped(g, "the camera's replay")
        m.pause()
        rows = sum(1 for h in hits if h["addr"] & 0xFFFFF == g.a("bz_row"))
        nb = g.w("bz_nbnc")
        res[name] = (rows, nb)
        m.run()
    m.pause()
    g.putb("bz_cmode", 0)
    m.run()
    print("  camera over TRIAL's flight (%d steps, replayed): %s" % (len(keys), "; ".join(
        "%s %d rows panned over %d bounces (%.1f a bounce)" % (k, v[0], v[1], v[0] / float(v[1] or 1))
        for k, v in res.items())), flush=True)
    return res


def report(tag, fr, pkg, refresh, npres):
    """-> (failures, the summary bonanza_perf's A/B prints)"""
    meas = [r for r in fr if not r["full"] and r["period"] is not None and "parts" in r]
    per = stats([r["period"] for r in meas])
    bad = []
    summ = {"refresh": refresh, "period": per["mean"], "parts": {}, "pkg": pkg}
    print("\n%s: %d frames presented (%d breakpoint hits at bz_presented), %d measured (not a full write); "
          "the card's refresh %.0f clk = %.2f Hz" % (tag.upper(), len(fr), npres, len(meas), refresh, CLK / refresh))
    print("  period  mean %7.0f clk = %5.2f Hz   min %6d   max %6d   p99 %6d" % (
        per["mean"], CLK / max(per["mean"], 1), per["min"], per["max"], per["p99"]))
    hold = {}
    for r in meas:
        k = min(3, max(1, int(r["period"] / refresh + 0.5)))
        hold[k] = hold.get(k, 0) + 1
    miss = sum(1 for r in meas if r["period"] > 1.5 * refresh)
    print("  frames held 1 refresh %d, 2 refreshes %d, 3 or more %d;  over 1.5 refreshes (a miss) %d" % (
        hold.get(1, 0), hold.get(2, 0), hold.get(3, 0), miss))
    for i, r in enumerate(fr):
        if r in meas and r["period"] > 1.5 * refresh:
            print("    miss: frame %d, period %d clk (%.2f refreshes): %s; %d rows, %d boxes, %s" % (
                i + 1, r["period"], r["period"] / refresh,
                ", ".join("%s %d" % (p, r["parts"][p]) for p in PARTS), r["rows"], r["boxes"],
                "a column" if r["column"] else "no column"))
    print("  %-14s %8s %7s %7s %7s %7s   %s" % ("part", "mean clk", "share", "min", "max", "p99", "package"))
    for i, p in enumerate(PARTS):
        s = stats([r["parts"][p] for r in meas])
        pk = pkg["acc"][i] / float(pkg["mfr"] or 1)
        tol = max(AGREE * s["mean"], AGREE_ABS)
        ok = abs(pk - s["mean"]) <= tol
        summ["parts"][p] = s["mean"]
        print("  %-14s %8.0f %6.1f%% %7d %7d %7d   %8.0f %s" % (
            p, s["mean"], 100.0 * s["mean"] / max(per["mean"], 1), s["min"], s["max"], s["p99"], pk,
            "" if ok else "<- DISAGREES"))
        if not ok:
            bad.append("%s %s: package %.0f against breakpoints %.0f" % (tag, p, pk, s["mean"]))
    work = per["mean"] - stats([r["parts"]["retrace wait"] for r in meas])["mean"]
    summ["busy"] = work
    summ["miss"] = miss
    print("  busy (all but the retrace wait) %.0f clk = %.0f%% of a refresh" % (work, 100.0 * work / refresh))
    ncol = sum(1 for r in fr if r["column"])
    nsplit = sum(1 for r in fr if "bz_tc" in r["marks"])
    nrow = sum(r["rows"] for r in fr)
    nfull = sum(1 for r in fr if r["full"])
    nrow_inc = sum(r["rows"] for r in fr if not r["full"])
    nbx = {}
    for r in fr:
        if not r["full"]:
            nbx[r["boxes"]] = nbx.get(r["boxes"], 0) + 1
    summ["boxes"] = nbx
    print("  columns %d (%.3f a frame; %d with rows after the boxes, bz_tc), rows %d (%.3f a frame outside full "
          "writes), full writes %d" % (ncol, ncol / float(len(fr)), nsplit, nrow, nrow_inc / float(len(fr)), nfull))
    print("  boxes a frame (outside full writes): %s" % ", ".join(
        "%d: %d" % kv for kv in sorted(nbx.items())))
    pkper = sum(pkg["acc"]) / float(pkg["mfr"] or 1)
    print("  package: frames %d, measured %d, period %.0f clk = %.2f Hz, misses %d, worst %d clk, columns %d, "
          "rows %d, full %d, retrace timeouts %d" % (
              pkg["frames"], pkg["mfr"], pkper, CLK / max(pkper, 1), pkg["miss"], pkg["fmax"], pkg["ncol"],
              pkg["nrow"], pkg["nfull"], pkg["tos"]))
    if "nocf" in pkg:
        print("  occluders, boxes, the shadow (SPEC.md 128.10.8, 128.11.10, reported): frames the pass ran %d, "
              "records laid %d (%.2f a pass), frames of two boxes or more %d, three or more %s, shadow frames %s, "
              "late boxes %s, bounces %s" % (
                  pkg["nocf"], pkg["nlay"], pkg["nlay"] / float(pkg["nocf"] or 1), pkg["n2bx"], pkg.get("n3bx", "-"),
                  pkg.get("nshd", "-"), pkg.get("late", "-"), pkg.get("nbnc", "-")))
    if abs(pkper - per["mean"]) > max(AGREE * per["mean"], AGREE_ABS):
        bad.append("%s period: package %.0f against breakpoints %.0f" % (tag, pkper, per["mean"]))
    for what, got, want in (("frames", pkg["frames"], len(fr)), ("measured frames", pkg["mfr"], len(meas)),
                            ("columns", pkg["ncol"], ncol), ("rows", pkg["nrow"], nrow),
                            ("full writes", pkg["nfull"], nfull)):
        if got != want:
            bad.append("%s %s: package %d against breakpoints %d" % (tag, what, got, want))
    floor = 2 * refresh
    print("  FLOOR: mean period %.0f <= two refreshes %.0f (%.2f Hz, half the refresh): %s" % (
        per["mean"], floor, CLK / floor, "held" if per["mean"] <= floor else "MISSED"))
    if per["mean"] > floor:
        bad.append("%s: the display holds %.2f Hz, under half the refresh (%.2f)" % (
            tag, CLK / per["mean"], CLK / floor))
    return bad, summ


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=R.ROOT, capture_output=True, text=True)


def reachable(commit):
    return git("cat-file", "-e", commit + "^{commit}").returncode == 0


def fetch(commit):
    """the commit into this clone if it can be had: -> None, or why not
    (docs/UPSTREAM.md Rule 0: a shallow clone answers ancestry wrongly, so
    unshallow it first; then ask origin for the commit itself)"""
    if reachable(commit):
        return None
    tried = []
    if git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        r = git("fetch", "--unshallow")
        tried.append("git fetch --unshallow: %s" % ("ok" if r.returncode == 0 else r.stderr.strip()[-120:]))
        if reachable(commit):
            return None
    r = git("fetch", "origin", commit)
    tried.append("git fetch origin %s: %s" % (commit, "ok" if r.returncode == 0 else r.stderr.strip()[-120:]))
    if reachable(commit):
        return None
    return "%s is not in this clone and could not be fetched (%s) - after upstream's squash merge no clone " \
           "of main has it" % (commit, "; ".join(tried))


def ab_tree(td, commit=AB_COMMIT):
    """An earlier wave's package with ITS OWN art, built in TD out of git:
    -> (floppy, source dir, art dir).  Wave 1's recipe (its Makefile's
    bonanza block): bonanza_assets.py and bbcourse.py over its BZ_COURSES,
    the parts the ball's two then each course's two."""
    w = os.path.join(td, "w")
    os.makedirs(w)
    names = git("ls-tree", "--name-only", commit, "apps/").stdout.split()
    incs = [n for n in names if n.startswith("apps/os88") and n.endswith(".inc")]
    tools = [t for t in ("tools/bonanza_assets.py", "tools/bbcourse.py")
             if git("cat-file", "-e", "%s:%s" % (commit, t)).returncode == 0]
    tar = os.path.join(td, "w.tar")
    r = subprocess.run(["git", "archive", "-o", tar, commit, "apps/bonanza"] + tools + incs, cwd=R.ROOT)
    assert r.returncode == 0, "git archive of %s failed" % commit
    with tarfile.open(tar) as tf:
        tf.extractall(w)
    art = os.path.join(td, "art")
    subprocess.run([sys.executable, os.path.join(w, "tools", "bonanza_assets.py"), "-o", art], cwd=w, check=True,
                   stdout=subprocess.DEVNULL)
    crs = sorted(os.listdir(os.path.join(w, "apps", "bonanza", "courses"))) \
        if os.path.isdir(os.path.join(w, "apps", "bonanza", "courses")) else []
    mk = git("show", "%s:Makefile" % commit).stdout
    order = []
    for line in mk.splitlines():
        if line.startswith("BZ_COURSES :="):
            order = line.split(":=", 1)[1].split()
    if order and "tools/bbcourse.py" in tools:
        subprocess.run([sys.executable, os.path.join(w, "tools", "bbcourse.py"), "-o", art] +
                       [os.path.join(w, c) for c in order], cwd=w, check=True, stdout=subprocess.DEVNULL)
    src = os.path.join(w, "apps", "bonanza")
    binp, o88, img = (os.path.join(td, n) for n in ("bonanza.bin", "BONANZA.O88", "bonanza360.img"))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(w, "apps") + "/", "-I", src + "/",
                    "-I", art + "/", "-o", binp, os.path.join(src, "bonanza.asm")], cwd=R.ROOT, check=True)
    nc = len(order) if order else len(crs)
    plist = ["BZBALC.BIN", "BZBALH.BIN"] + ["BZ%d%s.BIN" % (k, c) for k in range(nc) for c in "CH"]
    parts = []
    for p in plist:
        parts += ["--part", os.path.join(art, p)]
    subprocess.run([sys.executable, "tools/os88pkg.py", "--compress-if=lz4", binp, "-o", o88] + parts,
                   cwd=R.ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "tools/os88disk.py", "-o", img, "--size", "360", o88], cwd=R.ROOT,
                   check=True, stdout=subprocess.DEVNULL)
    return img, src, art


def ab_print(tag, new, old, commit):
    print("\n%s A/B: wave 2 (this tree) against %s, each on its own BENCH benchmark" % (tag.upper(), commit))
    print("  %-14s %9s %9s %9s" % ("", "wave 2", commit, "delta"))
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
                    help="also measure COMMIT's package (default %s, wave 1) built with its own art" % AB_COMMIT)
    ap.add_argument("--no-trial", action="store_true", help="BENCH only (no TRIAL leg, no camera)")
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    allbad = []
    skip = None
    if a.ab:
        skip = fetch(a.ab)
        if skip:
            print("bonanza_perf: SKIP the A/B leg: %s.  Wave 2 runs alone; the row exits %d, which is not a pass"
                  % (skip, SKIP_RC), flush=True)
            a.ab = None
    td = tempfile.mkdtemp(prefix="bzab") if a.ab else None
    try:
        ab = ab_tree(td, a.ab) if a.ab else None
        for tag in tags:
            res = run(tag, a.apps, a.src, a.art, trial=not a.no_trial)
            for label, bad, _ in res:
                for b in bad:
                    print("FAIL %s %s: %s" % (tag, label, b))
                allbad += bad
            if ab:
                ores = run(tag, *ab, trial=False)
                for label, obad, _ in ores:
                    for b in obad:
                        print("FAIL %s (%s): %s" % (tag, a.ab, b))
                    allbad += ["%s: %s" % (a.ab, b) for b in obad]
                ab_print(tag, res[0][2], ores[0][2], a.ab)
    finally:
        if td:
            shutil.rmtree(td, ignore_errors=True)
    assert not allbad, "%d failure(s)" % len(allbad)
    if skip:
        print("\nbonanza_perf (%s): wave 2 measured; the A/B leg SKIPPED: %s" % (", ".join(tags), skip))
        sys.exit(SKIP_RC)
    print("\nbonanza_perf (%s%s): PASS" % (", ".join(tags), ", A/B against %s" % a.ab if a.ab else ""))


if __name__ == "__main__":
    main()
