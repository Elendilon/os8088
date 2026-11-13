#!/usr/bin/env python3
"""BONANZA: the frame's cost on MartyPC's 4.77 MHz XT, CGA and Hercules (SPEC.md 128.4, 128.10.11.3, 128.11.15, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_perf.py [--adapter cga|herc|both] [--ab [COMMIT]] [--no-trial]
                                                      [--leg bench|heavy|trial|mill|ride ...]
    python3 tests/bonanza_perf.py --red halfcal | --check
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

WAVE 3 (SPEC.md 128.12.13.2).  The marks gain bz_tw: rows end there, and
bz_tw .. bz_tv is the WHEEL's part - the commits in the retrace wait and
the spins between them, idle like the wait - so BUSY is the period less the
wait and the wheel, comparable with wave 2's, and the wheel's part is
printed beside it.  The legs: BENCH with [bz_hvoff] 1 (wave 2's camera: the
A/B leg, 0 misses ASSERTED), BENCH and TRIAL with the heavy rule (reported:
busy, rows, columns, full writes, the rows and columns withheld, the busy
of every miss), MILL (bz_wover 0 and bz_wlate 0 ASSERTED; the wheel's
commits, LEADs, skips, waits, the contact and platform boxes and the busy
of every must-draw frame and every miss reported) and the RIDE (the ball
poked onto the lift at its low dock, up and down, no key: the busy of its
line-change frames and of the others, reported - O30).  --red halfcal
(bz_wlw halved after the calibration) must fail the MILL leg at bz_wover.

--ab builds an EARLIER wave's package - wave 2's, commit 848ade16, by default
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
MARKS = ["bz_t0", "bz_ts", "bz_tr", "bz_tw", "bz_tv", "bz_tf", "bz_tb", "bz_tc", "bz_presented"]
WRITERS = ["bz_row", "bz_col", "bz_fullw", "bz_boxw", "bz_step"]     # (bz_step: the frame's physics steps)
# wave 3's props (SPEC.md 128.12.13.2), counted a frame like the writers: the
# wheel's commits (and the LEAD among them: one after bz_tb), the contact
# group's lane (bz_csync: a must-draw rotor or a contact lane), a MUST-DRAW
# lane - a rotor at its gate change or a post lighting (bz_props.mlane + 4: the
# DEC AX only that branch runs) - and the platform's box (bz_cslab)
PROPS = ["bz_wcommit", "bz_csync", "bz_cslab", ("bz_props.mlane", 4)]
PARTS = ["sim+camera", "box compose", "rows", "retrace wait", "flip+columns", "box write", "wheel"]
# each mark CLOSES a part (bz_mark's accounting); wave 3 adds bz_tw: rows end
# there, and bz_tw .. bz_tv is the WHEEL's (the 7th accumulator, SPEC.md 128.12.5.6)
CLOSES3 = {"bz_ts": 0, "bz_tr": 1, "bz_tw": 2, "bz_tv": 6, "bz_tf": 3, "bz_tb": 4, "bz_tc": 5}
CLOSES2 = {"bz_ts": 0, "bz_tr": 1, "bz_tv": 2, "bz_tf": 3, "bz_tb": 4, "bz_tc": 5}
AGREE = 0.10
AGREE_ABS = 200
AB_COMMIT = "848ade16"         # wave 2 (SPEC.md 128.11), the engine the A/B leg measures against
SKIP_RC = 77


def pname(n):
    return n if isinstance(n, str) else "%s+%d" % n


def frames_of(hits, a):
    """Logged hits (sorted by cycle) -> one record per presented frame.  Every
    mark closes a part (CLOSES; bz_presented closes the box write, or the
    flip+columns part after a bz_tc), as the package's bz_mark accounts."""
    by = {v: k for k, v in a.items()}
    closes = CLOSES3 if "bz_tw" in a else CLOSES2
    out, last = [], None
    cnt = {n: 0 for n in WRITERS + [pname(x) for x in PROPS]}
    parts = [0] * 7
    marks, tc = {}, False
    prev = None                                 # the last mark's cycle
    for h in hits:
        n = by.get(h["addr"] & 0xFFFFF)
        c = h["cycles"]
        if n in cnt:
            cnt[n] += 1
            if n == "bz_wcommit" and "bz_tb" in marks:
                cnt["lead"] = cnt.get("lead", 0) + 1
            continue
        if n is None or n == "bz_t0":
            if n:
                marks[n] = c
            continue
        if n != "bz_presented":
            marks[n] = c
            if prev is not None:
                parts[closes[n]] += c - prev
            prev = c
            tc = tc or n == "bz_tc"
            continue
        rec = {"end": c, "period": None if last is None else c - last, "rows": cnt["bz_row"], "steps": cnt["bz_step"],
               "colcalls": cnt["bz_col"], "full": cnt["bz_fullw"] > 0, "boxes": cnt["bz_boxw"],
               "marks": dict(marks), "commits": cnt["bz_wcommit"], "lead": cnt.get("lead", 0),
               "contact": cnt["bz_csync"], "must": cnt["bz_props.mlane+4"], "pbox": cnt["bz_cslab"]}
        if last is not None and prev is not None and all(k in marks for k in ("bz_ts", "bz_tr", "bz_tv", "bz_tf",
                                                                                 "bz_tb")):
            parts[4 if tc else 5] += c - prev
            rec["parts"] = dict(zip(PARTS, parts))
        rec["column"] = (cnt["bz_col"] > 0) and not rec["full"]
        if "parts" in rec:                      # BUSY: all but the retrace wait and the wheel (both idle:
            rec["busy"] = rec["period"] - parts[3] - parts[6]     # the wheel spends the wait, 128.12.5.6)
        out.append(rec)
        last, prev, marks, tc = c, c, {}, False
        parts = [0] * 7
        cnt = {n: 0 for n in WRITERS + [pname(x) for x in PROPS]}
    return out


def stats(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return {"n": 0, "mean": 0.0, "min": 0, "max": 0, "p99": 0}
    return {"n": n, "mean": sum(xs) / n, "min": xs[0], "max": xs[-1], "p99": xs[min(n - 1, int(n * .99))]}


def addrs(g):
    out = {n: g.a(n) for n in MARKS + WRITERS if n in g.sym}
    for x in PROPS:
        if isinstance(x, str):
            if x in g.sym:
                out[x] = g.a(x)
        elif x[0] in g.sym:
            assert g.m.read(g.a(x[0]) + x[1], 1)[0] == 0x48, \
                "%s + %d is not bz_props's must-draw DEC AX: the row's offset moved" % x
            out[pname(x)] = g.a(x[0]) + x[1]
    return out


NPART = {True: 7, False: 6}


def measure(g, crs=None, pokes=None):
    """one benchmark under logged breakpoints: -> (frames, the package's
    instruments, the refresh in clocks, presented hits).  CRS: the course
    poked into [bz_crs] at bz_launch's entry; POKES {bss byte: value} poked
    there too (a name the build lacks is skipped: wave 2's)"""
    m = g.m
    a = addrs(g)
    pres = a["bz_presented"]
    launch = g.a("bz_launch")
    poked = []

    def on_launch(mm, rec):                     # (a STOP, the guest paused: poke the course)
        if rec["addr"] == launch & 0xFFFFF:
            if crs is not None:
                g.putb("bz_crs", crs)
            for n, v in (pokes or {}).items():
                if n in g.sym:
                    g.putb(n, v)
            poked.append(rec["cycles"])
    with M.bp_trace(m, *(list(a.values()) + [launch]), log=list(a.values()), on_hit=on_launch,
                    cap=BENCH * 64 + 20000) as tr:
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
    np = NPART["bz_tw" in g.sym]
    pkg = {"frames": g.w("bz_rframes"), "mfr": g.w("bz_rmfr"), "ncol": g.w("bz_rncol"),
           "nrow": g.w("bz_rnrow"), "nfull": g.w("bz_rnfull"), "miss": g.w("bz_rmiss"),
           "fmax": g.d("bz_rfmax") * 4, "tos": g.w("bz_tos"),
           "acc": [struct.unpack("<I", g.m.read(g.a("bz_racc") + 4 * i, 4))[0] * 4 for i in range(np)]}
    for n in ("bz_rnocf", "bz_rnlay", "bz_rn2bx", "bz_rn3bx", "bz_rnshd", "bz_rlate", "bz_nbnc", "bz_rwcom",
              "bz_rwover", "bz_rwlate", "bz_rwlead", "bz_rwskip", "bz_rncon", "bz_rnpbx", "bz_rndef", "bz_rnhvy",
              "bz_rnwr", "bz_rnwc", "bz_rnhedge", "bz_rwtmin"):
        if n in g.sym:
            pkg[n[4:] if n.startswith("bz_r") else n[3:]] = g.w(n)
    refresh = (c1 - c0) / float(f1 - f0)
    return frames_of(hits, a), pkg, refresh, sum(1 for h in hits if h["addr"] == pres)


def feats(r):
    """a frame's props, as its logged hits name them"""
    out = []
    if r.get("must"):
        out.append("a MUST-DRAW rotor")
    elif r.get("contact"):
        out.append("a contact lane")
    if r.get("pbox"):
        out.append("the platform's box")
    if r.get("commits"):
        out.append("%d wheel commit%s%s" % (r["commits"] - r.get("lead", 0), "s" if r["commits"] > 1 else "",
                                            " and a LEAD" if r.get("lead") else ""))
    return "; " + ", ".join(out) if out else ""


LEGS = ("bench", "heavy", "trial", "mill", "ride")


def run(tag, apps=None, src=None, art=None, trial=True, legs=LEGS, ab_steps=None):
    """-> [(label, failures, summary)].  Wave 3's legs (SPEC.md 128.12.13.2):
    BENCH with [bz_hvoff] 1 (the A/B leg: wave 2's camera, so it measures the
    engine; 0 misses ASSERTED), BENCH with the heavy rule (reported), TRIAL with
    it (the busy of every miss, reported) and its camera, MILL (bz_wover and
    bz_wlate 0 ASSERTED, the rest reported) and the poked RIDE.  A build without
    the heavy rule (wave 2's, the A/B's other side) runs BENCH alone."""
    sym = R.symbols(src, art)
    w3 = "bz_hvoff" in sym
    out = []
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym)
        ui.settle()
        if "bench" in legs:
            fr, pkg, refresh, npres = measure(g, pokes={"bz_hvoff": 1})
            bad, summ = report(tag + (" BENCH (A/B: bz_hvoff 1)" if w3 else " BENCH"), fr, pkg, refresh, npres)
            if w3 and summ["miss"]:
                # a miss on a frame that ran MORE physics steps than wave 2's same frame is the step clock's
                # phase against the refresh (each build catches up on its own frames), not the engine's:
                # reported beside the A/B; every other miss fails it (the final pass)
                own, phase = [], []
                for m_ in summ["misses"]:
                    i = m_[0] - 1
                    s3 = summ["steps"][i]
                    s2 = ab_steps[i] if ab_steps and i < len(ab_steps) else None
                    (phase if s2 is not None and s3 > s2 else own).append((m_, s3, s2))
                for m_, s3, s2 in phase:
                    print("  the A/B leg's miss at frame %d (busy %d): %d physics steps against %d on %s's same "
                          "frame - the step clock's phase, REPORTED" % (m_[0], m_[1], s3, s2, AB_COMMIT), flush=True)
                if own:
                    bad.append("%s BENCH, the A/B leg: %d missed refreshes on frames running no more steps than "
                               "wave 2's, 0 asserted (SPEC.md 128.12.13.2): %s" % (
                                   tag, len(own), ", ".join("frame %d busy %d%s" % m_ + " (%s steps, wave 2 %s)" % (
                                       s3, s2) for m_, s3, s2 in own[:6])))
            out.append(("BENCH", bad, summ))
        if not w3:
            return out
        if "heavy" in legs:
            fr, pkg, refresh, npres = measure(g, pokes={"bz_hvoff": 0})
            bad, summ = report(tag + " BENCH (the heavy rule)", fr, pkg, refresh, npres)
            heavy_line(tag, pkg, summ)
            out.append(("BENCH heavy", bad, summ))
        if trial and "trial" in legs:
            fr, pkg, refresh, npres = measure(g, crs=R.CRS_K["trial"], pokes={"bz_hvoff": 0})
            bad, summ = report(tag + " TRIAL (the heavy rule)", fr, pkg, refresh, npres)
            heavy_line(tag, pkg, summ)
            out.append(("TRIAL", bad, summ))
            summ["camera"] = camera(g, tag)
        if "mill" in legs:
            fr, pkg, refresh, npres = measure(g, crs=R.CRS_K["mill"], pokes={"bz_hvoff": 0})
            bad, summ = report(tag + " MILL", fr, pkg, refresh, npres)
            heavy_line(tag, pkg, summ)
            bad += mill_line(tag, fr, pkg, summ, refresh)
            out.append(("MILL", bad, summ))
        if "ride" in legs:
            out.append(("ride",) + ride(g, tag))
    return out


def heavy_line(tag, pkg, summ):
    print("  the heavy rule (SPEC.md 128.12.7): heavy frames %d, rows withheld %d, columns withheld %d, edge "
          "releases %d; contact groups %d (the platform's box %d), contact lanes that waited %d" % (
              pkg.get("nhvy", 0), pkg.get("nwr", 0), pkg.get("nwc", 0), pkg.get("nhedge", 0), pkg.get("ncon", 0),
              pkg.get("npbx", 0), pkg.get("ndef", 0)), flush=True)


def mill_line(tag, fr, pkg, summ, refresh):
    """MILL's leg: bz_wover and bz_wlate 0 ASSERTED; the wheel's, the contact
    groups' and the must-draw frames' figures REPORTED.  -> failures"""
    bad = []
    meas = [r for r in fr if not r["full"] and "busy" in r]
    print("  the wheel: commits %d (the breakpoints %d), LEADs %d, skipped waits %d, overruns %d, lanes late %d, the "
          "trim's lowest %d" % (pkg.get("wcom", 0), sum(r["commits"] for r in fr), pkg.get("wlead", 0),
                                pkg.get("wskip", 0), pkg.get("wover", 0), pkg.get("wlate", 0), pkg.get("wtmin", 0)),
          flush=True)
    must = [r["busy"] for r in meas if r["must"]]
    con = [r["busy"] for r in meas if r["contact"] and not r["must"]]
    pbx = [r["busy"] for r in meas if r["pbox"]]
    for what, xs in (("must-draw rotor", must), ("contact lane", con), ("platform box", pbx)):
        s = stats(xs)
        print("  %s frames %d: busy mean %.0f clk (%.0f%%), max %d (%.0f%%)%s" % (
            what, s["n"], s["mean"], 100.0 * s["mean"] / refresh, s["max"], 100.0 * s["max"] / refresh,
            "" if what != "must-draw rotor" else ": " + ", ".join("%d" % x for x in must[:12])), flush=True)
    print("  MILL's misses, each with its busy (REPORTED: SPEC.md 128.12.11's target is a miss only on the cannon's "
          "flight and the chute's fall): %s" % (", ".join("frame %d busy %d%s" % m_ for m_ in summ["misses"])
                                                 or "none"), flush=True)
    for n in ("wover", "wlate"):
        if pkg.get(n, 0):
            bad.append("%s MILL: bz_%s %d, 0 asserted (SPEC.md 128.12.13.2)" % (tag, n, pkg[n]))
    return bad


RIDE_STEPS = 32 + 2 * 128 + 8           # the low dock, a rise and a descent (P 256), and its last dock


def ride(g, tag):
    """the RIDE leg (SPEC.md 128.12.13.2): play on MILL, the ball poked onto
    the LIFT's slab at its low dock at the first bz_t0 and carried, no key held,
    up and down, under the logged marks: the busy of its frames whose slab line
    changed (the platform's box: bz_cslab) and of those it did not, and its
    misses - REPORTED (O30)"""
    m = g.m
    crs = R.course("mill")
    P_ = R.plat_rec(crs)
    a = addrs(g)
    wk = R.Walker(g, t0=True)
    m.bp_exec(g.a("bz_launch"))
    g.key("Enter")
    assert m.wait_stop(60) == "breakpoint", "Enter did not reach bz_launch"
    g.putb("bz_crs", R.CRS_K["mill"])
    g.putb("bz_hvoff", 0)
    m.bp_exec(wk.t0)
    m.run()
    assert m.wait_stop(60) == "breakpoint", "the MILL play did not reach bz_t0"
    R.slab_ball(g, P_, g.d("bz_nstep"), 0, 0, True)
    m.bp_exec()
    with M.bp_trace(m, *a.values(), log=list(a.values()), cap=RIDE_STEPS * 80 + 20000) as tr:
        m.run()
        M.until(m, lambda _: g.d("bz_nstep") >= RIDE_STEPS, "the ride's %d steps" % RIDE_STEPS, guest=120)
        m.pause()
        hits = tr.hits
        onp = g.b("bz_onp")
        m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the ride ends on Esc", guest=60)
    R.dropped(g, "the ride")
    fr = frames_of(hits, a)
    meas = [r for r in fr if not r["full"] and "busy" in r]
    refresh = R_REFRESH[tag]
    chg = [r for r in meas if r["pbox"]]
    same = [r for r in meas if not r["pbox"]]
    miss = [(fr.index(r) + 1, r["busy"], bool(r["pbox"])) for r in meas if r["period"] > 1.5 * refresh]
    s1, s2 = stats([r["busy"] for r in same]), stats([r["busy"] for r in chg])
    print("\n%s RIDE (MILL, poked onto the slab, %d steps, still carried at the end: %s): %d frames; the slab's line "
          "unchanged on %d, busy mean %.0f (%.0f%%) max %d (%.0f%%); its line changed (its box) on %d, busy mean %.0f "
          "(%.0f%%) max %d (%.0f%%); misses %d%s (REPORTED, O30)" % (
              tag.upper(), RIDE_STEPS, "yes" if onp else "NO", len(meas), s1["n"], s1["mean"],
              100.0 * s1["mean"] / refresh, s1["max"], 100.0 * s1["max"] / refresh, s2["n"], s2["mean"],
              100.0 * s2["mean"] / refresh, s2["max"], 100.0 * s2["max"] / refresh, len(miss),
              ": " + ", ".join("frame %d busy %d%s" % (f, b, " (a line change)" if c else "") for f, b, c in miss)
              if miss else ""), flush=True)
    bad = [] if chg else ["%s RIDE: no frame drew the platform's box: the ride never rode" % tag]
    return bad, {"same": s1, "change": s2, "miss": miss}


R_REFRESH = {"cga": 79648.0, "herc": 93790.0}     # clocks, MartyPC's cards (wave 2's measured periods)


def camera(g, tag):
    """the rows each camera mode pans over TRIAL's bounces: a log of the chord off
    H's lip from the start, replayed in GLIDE and in TRICKLE (the benchmark
    always rolls GLIDE).  Reported, not asserted (O9)."""
    m = g.m
    keys = [0] * 4 + [BB.K_R | BB.K_D] * 260
    log = R.make_log(keys, R.CRS_K["trial"], R.course("trial").ball)
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
    parts = PARTS[:len(pkg["acc"])]             # (wave 2's build: six, no wheel)
    for i, r in enumerate(fr):
        if r in meas and r["period"] > 1.5 * refresh:
            print("    miss: frame %d, period %d clk (%.2f refreshes), BUSY %d clk (%.0f%%): %s; %d rows, %d boxes, "
                  "%s%s" % (i + 1, r["period"], r["period"] / refresh, r["busy"], 100.0 * r["busy"] / refresh,
                            ", ".join("%s %d" % (p, r["parts"][p]) for p in parts), r["rows"], r["boxes"],
                            "a column" if r["column"] else "no column", feats(r)))
    print("  %-14s %8s %7s %7s %7s %7s   %s" % ("part", "mean clk", "share", "min", "max", "p99", "package"))
    for i, p in enumerate(parts):
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
    work = stats([r["busy"] for r in meas])["mean"]
    summ["busy"] = work
    summ["miss"] = miss
    summ["misses"] = [(i + 1, r["busy"], feats(r)) for i, r in enumerate(fr)
                      if r in meas and r["period"] > 1.5 * refresh]
    summ["steps"] = [r["steps"] for r in fr]
    print("  busy (all but the retrace wait and the wheel, both idle: SPEC.md 128.12.5.6) %.0f clk = %.1f%% of a "
          "refresh; the wheel's part %.0f clk beside it" % (work, 100.0 * work / refresh,
                                                         stats([r["parts"]["wheel"] for r in meas])["mean"]))
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
    if "BZBALR.BIN" in mk:                      # wave 2's part order (its Makefile's BZ_PARTS): the three
        plist = ["BZBALR.BIN", "BZBALS.BIN", "BZBALG.BIN"] + ["BZ%d.BIN" % k for k in range(nc)]   # balls, a
    else:                                       # course a part; wave 1's: the ball's two, each course's two
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
    print("\n%s A/B: wave 3 (this tree, bz_hvoff 1) against %s, each on its own BENCH benchmark (busy: all but "
          "the retrace wait and the wheel)" % (tag.upper(), commit))
    print("  %-14s %9s %9s %9s" % ("", "wave 3", commit, "delta"))
    for p in PARTS + ["busy", "period"]:
        a = new["parts"].get(p, 0) if p in PARTS else new[p]
        b = old["parts"].get(p, 0) if p in PARTS else old[p]
        print("  %-14s %9.0f %9.0f %+9.0f" % (p, a, b, a - b))
    print("  %-14s %8.1f%% %8.1f%%" % ("busy share", 100.0 * new["busy"] / new["refresh"],
                                        100.0 * old["busy"] / old["refresh"]))
    print("  %-14s %9d %9d" % ("misses", new["miss"], old["miss"]))


REDS = {
    # the calibration's word-line HALVED after it runs: the wheel underprices its
    # commits and the late ones end past their deadline (SPEC.md 128.12.13.2)
    "halfcal": [("bzwheel.inc", "    call .min1\n    mov [bz_warr], ax\n.out:\n    ret\n",
                 "    call .min1\n    mov [bz_warr], ax\n    shr word [bz_wlw], 1        ; RED halfcal\n.out:\n    ret\n")],
}
RED_LEGS = {"halfcal": ("mill",)}
RED_WANT = {"halfcal": "bz_wover"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--apps", help="the B: floppy to run instead of build/bonanza360.img")
    ap.add_argument("--src", help="the package source that floppy was built from (default apps/bonanza)")
    ap.add_argument("--art", help="the art directory that source assembled against (default build/bonanza-art)")
    ap.add_argument("--ab", nargs="?", const=AB_COMMIT, metavar="COMMIT",
                    help="also measure COMMIT's package (default %s, wave 2) built with its own art" % AB_COMMIT)
    ap.add_argument("--no-trial", action="store_true", help="no TRIAL leg, no camera")
    ap.add_argument("--leg", choices=LEGS, action="append", help="only these legs (default all)")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only: every red arm assembles")
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.check:
        for line in R.check_reds(REDS, "bonanza_perf"):
            print(line)
        return
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags:
                try:
                    bad = [b for _, bb, _ in run(tag, img, src, legs=RED_LEGS[a.red]) for b in bb]
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(RED_WANT[a.red] in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (a.red, tag, RED_WANT[a.red], bad)
                print("bonanza_perf --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_perf --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    legs = tuple(a.leg) if a.leg else LEGS
    allbad = []
    skip = None
    if a.ab:
        skip = fetch(a.ab)
        if skip:
            print("bonanza_perf: SKIP the A/B leg: %s.  Wave 3 runs alone; the row exits %d, which is not a pass"
                  % (skip, SKIP_RC), flush=True)
            a.ab = None
    td = tempfile.mkdtemp(prefix="bzab") if a.ab else None
    try:
        ab = ab_tree(td, a.ab) if a.ab else None
        for tag in tags:
            ores = None
            if ab:                                  # wave 2 first: its frames' step counts judge the A/B's misses
                ores = run(tag, *ab, trial=False, legs=("bench",))
                for label, obad, _ in ores:
                    for b in obad:
                        print("FAIL %s (%s): %s" % (tag, a.ab, b))
                    allbad += ["%s: %s" % (a.ab, b) for b in obad]
            res = run(tag, a.apps, a.src, a.art, trial=not a.no_trial, legs=legs,
                      ab_steps=ores[0][2]["steps"] if ores else None)
            for label, bad, _ in res:
                for b in bad:
                    print("FAIL %s %s: %s" % (tag, label, b))
                allbad += bad
            if ores and res and res[0][0] == "BENCH":
                ab_print(tag, res[0][2], ores[0][2], a.ab)
    finally:
        if td:
            shutil.rmtree(td, ignore_errors=True)
    assert not allbad, "%d failure(s)" % len(allbad)
    if skip:
        print("\nbonanza_perf (%s): wave 3 measured; the A/B leg SKIPPED: %s" % (", ".join(tags), skip))
        sys.exit(SKIP_RC)
    print("\nbonanza_perf (%s%s): PASS" % (", ".join(tags), ", A/B against %s" % a.ab if a.ab else ""))


if __name__ == "__main__":
    main()
