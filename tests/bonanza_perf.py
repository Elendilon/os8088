#!/usr/bin/env python3
"""BONANZA: the frame's cost on MartyPC's 4.77 MHz XT, CGA and Hercules (SPEC.md 128.4, 128.10.11.3, 128.11.15, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_perf.py [--adapter cga|herc|both] [--ab [COMMIT]] [--no-trial]
                                                      [--leg bench|trial|mill|ride|corner ...] [--sound off|on]
    python3 tests/bonanza_perf.py --red halfcal|rideoff|level1 | --check
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
(bz_wlw halved after the calibration) must fail the MILL leg at bz_wover;
--red rideoff (the ride merge's limit back to BZ_BOXH: two boxes a riding
line change) the CGA's ride leg at its line-change misses; --red level1 (the
occluder-pass and two-box clauses restored in bz_hv1) TRIAL's bz_nhvy.

WAVE 3B (SPEC.md 128.13.12, 128.13.15: the sound arrived first, so there is
no pad - every leg runs with the sound OFF and with it ON, the speaker at S's
AUTO, which is what a 5150 without an AdLib plays).  OFF is like for like:
the A/B against wave 3.  ON is what the owner hears, and the asserted lift
targets are taken there; a miss is printed with the sound's share of its
frame (bzs_frame to its .fend, logged) for the owner to weigh.  The legs:

  BENCH   OFF with [bz_hvoff] 1 on both builds (the A/B): 0 misses ASSERTED
          but a frame running more steps than wave 3's same frame (the step
          phase's, REPORTED), and the mean busy at least 2.0k clk under wave
          3's on the CGA ASSERTED (128.13.14 item 11; the Hercules' REPORTED).
          ON with the shipped camera: REPORTED.
  TRIAL   bz_nhvy 0 ASSERTED, OFF and ON (no slab: the no-rule camera, 128.13.6);
          misses REPORTED against wave 2's 8 / 2.  Then the camera replays.
  MILL    OFF three ways - this build, this build with [bz_hvoff] 1, and wave
          3 - REPORTED side by side (busy mean and p95, misses, bz_npbx,
          bz_ncon, bz_npwt, the promotions); bz_wover 0 and bz_wlate 0
          ASSERTED on this build's legs.  ON (this build): THE LIFT STRETCH -
          every frame that draws the platform's box (bz_cslabr) or waits one
          (bz_props.pwt), and the frame after each - at most 3 missed
          refreshes on the Hercules ASSERTED, the CGA's REPORTED with each
          missed frame's parts, boxes, steps and sound; the share of the lift's
          line changes that waited and the longest wait / draw alternation
          REPORTED.
  RIDE    the ball poked onto the slab's middle (THE RIDE BOX): OFF (the
          engine's figure), no miss on a line-change frame ASSERTED on both
          cards and bz_late 0 ASSERTED (bz_tpoke 1: its boxes timed); ON the
          same REPORTED, each miss with its sound share (a downbeat on a p95
          line-change frame is a miss the song's phase decides); GLIDE's
          withheld rows and their longest deferral REPORTED.
  CORNER  the ride with the ball held over the slab's LEFT corner (two boxes,
          128.13.4.1's residue): its line-change frames REPORTED, OFF and ON.

and on every BENCH and MILL leg THE WHEEL'S SPARE RETRACE IDLE - the wait's
part after the wheel - REPORTED per card (128.13.15 item 3).  THE ADLIB ARM
(--no-adlib leaves it out): MILL and the ride with the sound at AUTO on
os8088_5150_sb, the 5150 with an AdLib - REPORTED, nothing asserted.

--ab builds an EARLIER wave's package - wave 3's, commit e781df53, by default
- in a private temporary tree with ITS OWN art: that commit's apps/bonanza/,
apps/os88*.inc, tools/bonanza_assets.py and tools/bbcourse.py out of git
(`git archive`), its generators run into the tree, assembled and packed with
that wave's part order and put on a 360KB floppy there (never build/).  The
same breakpoints then run on its BENCH and MILL benchmarks too, printed
beside this build part by part.  The row never fetches: when this clone has
not got the commit (a shallow clone, docs/UPSTREAM.md Rule 0, or after
upstream's squash merge, when no clone of main has it) the A/B leg reports
SKIP naming the command that would bring it, and the run EXITS 77
(tests/m83.py's convention) - never a pass, and never 128.10.9's recorded
figures standing in for a measurement.  So the REGISTERED row runs without
--ab (a row that could only fail after the merge is no row): the A/B, with
128.13.14 item 11's asserted 2.0k, is the final pass's by-hand run,
`python3 tests/bonanza_perf.py --ab`.

WAVE 4 (SPEC.md 128.14.14, 128.14.16, 128.14.17 item 7).  --ab's default is now
3b's head, 573eec83, built with ITS OWN art and sound (its bbmusic.py and part
order: the balls, the courses, the sound, the songs): BENCH OFF with bz_hvoff 1
on both, and THIS build's mean busy at most +0.5k over 3b's ASSERTED ON BOTH
CARDS (PREDICTED +0.15 - 0.3k on the CGA, 128.14.12).  B runs with H at FOLLOW
on every BENCH leg and draws NO HUD box (bz_nhud 0) ASSERTED.  THE DEMO LEGS
(`demo`): every shipped demo (V with bz_vk poked, BZD1 - BZD5) through D on both
cards, sound OFF and ON, the HUD OFF and - when the build carries it - REST, and
MILL's route demo also FOLLOW: ASSERTED the replay's end the model's
(bonanza_demo.model_end), bz_wover and bz_wlate 0, and in REST no HUD box on a
frame with an entering row or column but a release (bz_presented a STOP reading
bz_hwk and bz_nhrel); REPORTED busy mean and p95, the misses with their parts,
the HUD's boxes by kind and the releases, pads, springs and lip-outs, each HUD
leg against its HUD-OFF twin.  THE HUD'S FIT (`hudfit`, 128.14.16 item 3): MILL's
route demo with the speaker on, the HUD OFF against REST on the CGA and FOLLOW
on the Hercules - the misses may rise by at most 2 a card, ASSERTED (a failure
there is the measurement that REMOVES the HUD).  D's OVERHEAD (`dover`): MILL's
route demo through D and through R under the same outside trace, busy compared,
REPORTED.  Red arm `--red hudon` (bz_hinit's B test taken out: bz_nhud non-zero
on the B leg) - built only while the HUD is.
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
PROPS = ["bz_wcommit", "bz_csync", "bz_cslabr", ("bz_props.mlane", 4),
         # wave 3b (SPEC.md 128.13.4.3): the platform's box WAITED (bz_props.pwt, its one entry) and a
         # wheel lane PROMOTED to the contact slot (bz_props.promo); bz_cslabr is every platform box,
         # the ride box's and the second rect beside a lighting post included
         "bz_props.pwt", "bz_props.promo"]
SOUND = ("bzs_frame", "bzs_frame.fend")     # the sound's span a frame (SPEC.md 128.20.7), logged
PARTS = ["sim+camera", "box compose", "rows", "retrace wait", "flip+columns", "box write", "wheel"]
# each mark CLOSES a part (bz_mark's accounting); wave 3 adds bz_tw: rows end
# there, and bz_tw .. bz_tv is the WHEEL's (the 7th accumulator, SPEC.md 128.12.5.6)
CLOSES3 = {"bz_ts": 0, "bz_tr": 1, "bz_tw": 2, "bz_tv": 6, "bz_tf": 3, "bz_tb": 4, "bz_tc": 5}
CLOSES2 = {"bz_ts": 0, "bz_tr": 1, "bz_tv": 2, "bz_tf": 3, "bz_tb": 4, "bz_tc": 5}
AGREE = 0.10
AGREE_ABS = 200
AB_COMMIT = "573eec831342c34c1c1489894845fe8b0f005bc8"   # wave 3b (SPEC.md 128.13), the engine wave 4's A/B
                               # measures against (128.14.14) - the FULL id: git fetches an object only by it
AB_OVER = 500                  # 128.14.17 item 7: BENCH's mean busy at most this much OVER 3b's, BOTH cards
HUD_MISS = 2                   # 128.14.16 item 3: MILL's misses (speaker on) the HUD may add, a card
DEMO_CAP = 4000                # frames a shipped demo's D presents at most (MOON's: ~2,300 on the CGA)
LIFT_MISS = 3                  # 128.13.4.5: the Hercules' lift stretch, missed refreshes at most (sound ON)
SND_OFF, SND_AUTO = 3, 0       # bzs_mode: OFF, and AUTO (the speaker on a 5150 without an AdLib)
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
    snd, s0 = 0, None
    for h in hits:
        n = by.get(h["addr"] & 0xFFFFF)
        c = h["cycles"]
        if n == SOUND[0]:
            s0 = c
            continue
        if n == SOUND[1]:
            if s0 is not None:
                snd += c - s0
            s0 = None
            continue
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
               "contact": cnt["bz_csync"], "must": cnt["bz_props.mlane+4"], "pbox": cnt["bz_cslabr"],
               "pwt": cnt["bz_props.pwt"], "promo": cnt["bz_props.promo"], "snd": snd, "hit": h.get("hit")}
        if last is not None and prev is not None and all(k in marks for k in ("bz_ts", "bz_tr", "bz_tv", "bz_tf",
                                                                                 "bz_tb")):
            parts[4 if tc else 5] += c - prev
            rec["parts"] = dict(zip(PARTS, parts))
        rec["column"] = (cnt["bz_col"] > 0) and not rec["full"]
        if "parts" in rec:                      # BUSY: all but the retrace wait and the wheel (both idle:
            rec["busy"] = rec["period"] - parts[3] - parts[6]     # the wheel spends the wait, 128.12.5.6)
        out.append(rec)
        last, prev, marks, tc = c, c, {}, False
        snd = 0
        parts = [0] * 7
        cnt = {n: 0 for n in WRITERS + [pname(x) for x in PROPS]}
    return out


def stats(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return {"n": 0, "mean": 0.0, "min": 0, "max": 0, "p99": 0, "p95": 0, "p10": 0}
    return {"n": n, "mean": sum(xs) / n, "min": xs[0], "max": xs[-1], "p99": xs[min(n - 1, int(n * .99))],
            "p95": xs[min(n - 1, int(n * .95))], "p10": xs[int(n * .10)]}


def addrs(g):
    out = {n: g.a(n) for n in MARKS + WRITERS if n in g.sym}
    out.update({n: g.a(n) for n in SOUND if n in g.sym})
    for x in PROPS:
        if isinstance(x, str):
            if x in g.sym:
                out[x] = g.a(x)
            elif x == "bz_cslabr" and "bz_cslab" in g.sym:      # (an earlier wave's: its one entry)
                out[x] = g.a("bz_cslab")
        elif x[0] in g.sym:
            assert g.m.read(g.a(x[0]) + x[1], 1)[0] == 0x48, \
                "%s + %d is not bz_props's must-draw DEC AX: the row's offset moved" % x
            out[pname(x)] = g.a(x[0]) + x[1]
    return out


NPART = {True: 7, False: 6}


def measure(g, crs=None, pokes=None, key="KeyB", hud=False, frames_cap=BENCH):
    """one benchmark under logged breakpoints: -> (frames, the package's
    instruments, the refresh in clocks, presented hits).  CRS: the course
    poked into [bz_crs] at bz_launch's entry; POKES {bss byte: value} poked
    there too (a name the build lacks is skipped: wave 2's).  Wave 4: KEY
    `KeyD` measures the held log's DEMO benchmark (128.14.7.3) and `KeyR` its
    plain replay (the package's instruments then not filled: pkg None); HUD
    makes bz_presented a STOP that reads the frame's HUD box (bz_hwk), its
    releases (bz_nhrel) and bz_hon into each frame (fr[i]["hud"])"""
    m = g.m
    a = addrs(g)
    pres = a["bz_presented"]
    launch = g.a("bz_launch")
    poked = []
    hudrec = []

    def on_launch(mm, rec):                     # (a STOP, the guest paused: poke the course)
        if rec["addr"] == launch & 0xFFFFF:
            if crs is not None:
                g.putb("bz_crs", crs)
            for n, v in (pokes or {}).items():
                if n in g.sym:
                    g.putb(n, v)
            poked.append(rec["cycles"])
        elif rec["addr"] == pres & 0xFFFFF:
            hudrec.append((g.b("bz_hwk"), g.w("bz_nhrel"), g.b("bz_hon")))
    logged = [x for x in a.values() if not (hud and x == pres)]
    with M.bp_trace(m, *(list(a.values()) + [launch]), log=logged, on_hit=on_launch,
                    cap=frames_cap * 64 + 20000) as tr:
        g.key(key)
        M.until(m, lambda _: g.b("bz_fs") == 1, "the benchmark starts", guest=60)
        m.pause()
        g.check_base()
        if crs is not None and (not poked or g.b("bz_crs") != crs):
            raise AssertionError("the benchmark runs course %d, not the poked %d" % (g.b("bz_crs"), crs))
        c0, f0 = m.status()["cycles"], m.cards()[0]["frames"]
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark's frames (%s)" % key, guest=120 * frames_cap // BENCH)
        m.pause()
        c1, f1 = m.status()["cycles"], m.cards()[0]["frames"]
        hits = tr.hits
        assert not tr.overflowed, "the trace overflowed its cap: frames are missing"
        m.run()
    R.dropped(g, "the benchmark")
    fr = frames_of(hits, a)
    if hud:
        for r, h in zip(fr, hudrec):
            r["hud"] = h
    if key == "KeyR":                           # a replay: no instruments of the package's
        return fr, None, (c1 - c0) / float(f1 - f0), sum(1 for h in hits if h["addr"] == pres)
    assert g.b("bz_res") == 1 and g.b("bz_err") == 0, "the benchmark did not finish (res %d, err %d)" % (
        g.b("bz_res"), g.b("bz_err"))
    np = NPART["bz_tw" in g.sym]
    pkg = {"frames": g.w("bz_rframes"), "mfr": g.w("bz_rmfr"), "ncol": g.w("bz_rncol"),
           "nrow": g.w("bz_rnrow"), "nfull": g.w("bz_rnfull"), "miss": g.w("bz_rmiss"),
           "fmax": g.d("bz_rfmax") * 4, "tos": g.w("bz_tos"),
           "acc": [struct.unpack("<I", g.m.read(g.a("bz_racc") + 4 * i, 4))[0] * 4 for i in range(np)]}
    for n in ("bz_rnocf", "bz_rnlay", "bz_rn2bx", "bz_rn3bx", "bz_rnshd", "bz_rlate", "bz_nbnc", "bz_rwcom",
              "bz_rwover", "bz_rwlate", "bz_rwlead", "bz_rwskip", "bz_rncon", "bz_rnpbx", "bz_rndef", "bz_rnhvy",
              "bz_rnwr", "bz_rnwc", "bz_rnhedge", "bz_rwtmin", "bz_rnpwt"):
        if n in g.sym:
            pkg[n[4:] if n.startswith("bz_r") else n[3:]] = g.w(n)
    for n in ("bz_nhud", "bz_nhhold", "bz_nhrel"):
        if n in g.sym:
            pkg[n[3:]] = g.w(n)
    refresh = (c1 - c0) / float(f1 - f0)
    return fr, pkg, refresh, sum(1 for h in hits if h["addr"] == pres)


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


LEGS = ("bench", "trial", "mill", "ride", "corner", "demo", "hudfit", "dover")
SOUNDS = ("off", "on")


def set_snd(g, on):
    """the sound OFF or at S's AUTO (bzs_mode, the player's own choice, which
    persists across plays): a build without the sound (wave 3's) has neither"""
    if "bzs_mode" not in g.sym:
        return
    g.m.pause()
    g.putb("bzs_mode", SND_AUTO if on else SND_OFF)
    g.m.run()


ADLIB = "os8088_5150_sb"       # the 5150 with an AdLib (SOUND.DRV at boot): S's AUTO plays the chip there


def run(tag, apps=None, src=None, art=None, trial=True, legs=LEGS, ab_steps=None, sounds=SOUNDS, old=False,
        machine=None):
    """-> [(label, failures, summary)].  Wave 3b's legs (SPEC.md 128.13.12,
    128.13.15; the module's docstring).  OLD: the A/B's other side, wave 3's
    build - BENCH ([bz_hvoff] 1) and MILL alone, no sound.  MACHINE: another
    MartyPC machine of the card TAG (the AdLib arm's)."""
    sym = R.symbols(src, art)
    out = []
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=machine or R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym)
        ui.settle()
        if old:
            sounds = ("off",)
        for snd in sounds:
            on = snd == "on"
            set_snd(g, on)
            lab = " (sound %s)" % snd.upper()
            if "bench" in legs:
                # OFF: THE A/B LEG, LIKE FOR LIKE - wave 3 has no sound, and both builds run [bz_hvoff] 1 (no
                # heavy rule), engine against engine.  ON: the shipped camera, as played (REPORTED)
                hv = 1 if not on else 0
                if "bz_hmode" in g.sym:         # wave 4: H at FOLLOW - B must still draw no HUD box
                    g.m.pause()
                    g.putb("bz_hmode", 2)
                    g.m.run()
                fr, pkg, refresh, npres = measure(g, pokes={"bz_hvoff": hv})
                bad, summ = report("%s BENCH (bz_hvoff %d)%s" % (tag, hv, lab), fr, pkg, refresh, npres)
                summ["busy_p95"] = busy_of(fr)["p95"]
                if "bz_hmode" in g.sym:
                    g.m.pause()
                    g.putb("bz_hmode", 0)
                    g.m.run()
                    if pkg.get("nhud", 0):
                        bad.append("%s BENCH%s: bz_nhud %d with H at FOLLOW - B runs with the HUD OFF, so it draws "
                                   "no HUD box (SPEC.md 128.14.14)" % (tag, lab, pkg["nhud"]))
                idle_line(fr, refresh, summ)
                if on:                          # (its busy and misses REPORTED; the floor and the
                    heavy_line(tag, pkg, summ)  # instruments' agreement asserted as on every leg)
                elif not old and summ["miss"]:
                    bad += phase_misses(tag, summ, ab_steps)
                out.append(("BENCH " + snd, bad, summ))
            if old:
                if "mill" in legs:
                    fr, pkg, refresh, npres = measure(g, crs=R.CRS_K["mill"], pokes={"bz_hvoff": 0})
                    bad, summ = report("%s MILL (%s)" % (tag, AB_COMMIT[:8]), fr, pkg, refresh, npres)
                    mill_line(tag, fr, pkg, summ, refresh, assert_lift=False, assert_wheel=False)
                    out.append(("MILL off", bad, summ))
                continue
            if trial and "trial" in legs:
                fr, pkg, refresh, npres = measure(g, crs=R.CRS_K["trial"], pokes={"bz_hvoff": 0})
                bad, summ = report("%s TRIAL (the shipped camera)%s" % (tag, lab), fr, pkg, refresh, npres)
                heavy_line(tag, pkg, summ)
                # TRIAL has no slab and no prop: its camera is bz_hvoff 1's exactly (SPEC.md 128.13.6)
                if pkg.get("nhvy", 0):
                    bad.append("%s TRIAL%s: bz_nhvy %d, 0 asserted - TRIAL has no slab, so no frame of it is "
                               "heavy (SPEC.md 128.13.6)" % (tag, lab, pkg["nhvy"]))
                print("  TRIAL's misses %d%s, against wave 2's 8 (CGA) / 2 (Hercules): REPORTED (128.13.6)" % (
                    summ["miss"], lab), flush=True)
                out.append(("TRIAL " + snd, bad, summ))
                if not on:
                    summ["camera"] = camera(g, tag)
            if "mill" in legs:
                ways = ((0, "this build"), (1, "this build, bz_hvoff 1")) if not on else ((0, "this build"),)
                for hv, what in ways:
                    fr, pkg, refresh, npres = measure(g, crs=R.CRS_K["mill"], pokes={"bz_hvoff": hv})
                    bad, summ = report("%s MILL (%s)%s" % (tag, what, lab), fr, pkg, refresh, npres)
                    heavy_line(tag, pkg, summ)
                    bad += mill_line(tag, fr, pkg, summ, refresh, assert_lift=on and hv == 0)
                    idle_line(fr, refresh, summ)
                    out.append(("MILL %s%s" % (snd, "" if not hv else " hvoff"), bad, summ))
            if "ride" in legs:
                bad, summ = ride(g, tag, corner=False, on=on)
                out.append(("ride " + snd, bad, summ))
            if "corner" in legs:
                bad, summ = ride(g, tag, corner=True, on=on)
                out.append(("corner ride " + snd, bad, summ))
        if not old and set(legs) & {"demo", "hudfit", "dover"}:
            out += demo_legs(g, tag, legs, sounds)
        set_snd(g, True)                        # (S back at AUTO for whatever runs next)
    return out


# ---- WAVE 4 (SPEC.md 128.14.7.3, 128.14.14, 128.14.16): the DEMO legs ------------
HMODES = {0: "OFF", 1: "REST", 2: "FOLLOW"}
FIT_MODE = {"cga": 1, "herc": 2}        # 128.14.16 item 3: H at REST on the CGA, FOLLOW on the Hercules


def load_demo(g, kd):
    """V with bz_vk poked to KD - 1: the shipped demo BZD<KD>.BIN in the log"""
    m = g.m
    demo = open(os.path.join(R.ROOT, R.at("build/bonanza-art"), "BZD%d.BIN" % kd), "rb").read()
    m.pause()
    g.putb("bz_vk", kd - 1)
    m.run()
    M.until(m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)
    g.key("KeyV")
    M.until(m, lambda _: bytes(m.read(g.a("bz_rlog"), len(demo))) == demo, "V to load BZD%d.BIN" % kd, guest=20)
    return demo


def busy_of(fr):
    meas = [r for r in fr if not r["full"] and "busy" in r and r["period"] is not None]
    return stats([r["busy"] for r in meas])


def demo_leg(g, tag, kd, hmode, snd):
    """one shipped demo through D: -> (failures, summary).  ASSERTED its end the
    model's, bz_wover and bz_wlate 0, and in REST no HUD box on a frame with an
    entering row or column but a release; REPORTED the rest"""
    import bonanza_demo as DM
    m = g.m
    demo = load_demo(g, kd)
    set_snd(g, snd == "on")
    if "bz_hmode" in g.sym:
        m.pause()
        g.putb("bz_hmode", hmode)
        m.run()
    lab = "%s D of BZD%d (HUD %s, sound %s)" % (tag, kd, HMODES[hmode], snd.upper())
    fr, pkg, refresh, npres = measure(g, key="KeyD", hud=hmode != 0 and "bz_hmode" in g.sym, frames_cap=DEMO_CAP)
    bad, summ = report(lab, fr, pkg, refresh, npres)
    got, want = DM.end_state(g), DM.model_end(demo)
    if got != want:
        bad.append("%s: D ended at %s, the model's replay of the demo at %s" % (lab, got, want))
    for n in ("wover", "wlate"):
        if pkg.get(n, 0):
            bad.append("%s: bz_r%s %d, 0 asserted (SPEC.md 128.14.14)" % (lab, n, pkg[n]))
    summ["busy_p95"] = busy_of(fr)["p95"]
    if hmode == 1:
        rel0, kinds, nrel = None, {}, 0
        for i, r in enumerate(fr):
            hw = r.get("hud")
            if hw is None:
                continue
            hwk, rel, _hon = hw
            if hwk:
                kinds[hwk] = kinds.get(hwk, 0) + 1
            if hwk and (r["rows"] or r["column"]) and not r["full"] and not (hwk == 3 and rel0 is not None
                                                                               and rel != rel0):
                bad.append("%s frame %d: a HUD box (kind %d) on a frame with an entering row or column, not a "
                           "release (SPEC.md 128.14.5.6)" % (lab, i + 1, hwk))
                break
            nrel += rel0 is not None and rel != rel0
            rel0 = rel
        summ["hudboxes"] = kinds
        print("  HUD REST: boxes by kind %s, releases %d" % (kinds, nrel), flush=True)
    print("  %s: busy mean %.0f p95 %d, misses %d (%s), HUD boxes %s, pads %s, springs %s, lip-outs %s" % (
        lab, summ["busy"], summ["busy_p95"], summ["miss"],
        "; ".join("frame %d busy %d%s" % x for x in summ["misses"][:8]) or "none", pkg.get("nhud", "-"),
        g.w("bz_npad") if "bz_npad" in g.sym else "-", g.w("bz_nspr") if "bz_nspr" in g.sym else "-",
        g.w("bz_nlip") if "bz_nlip" in g.sym else "-"), flush=True)
    if "bz_hmode" in g.sym:
        m.pause()
        g.putb("bz_hmode", 0)
        m.run()
    return bad, summ


def demo_legs(g, tag, legs, sounds):
    """every shipped demo through D, sound OFF and ON, the HUD OFF and REST
    (the HUD's legs only when it is built), MILL's also FOLLOW; the HUD-fit
    comparison (128.14.16 item 3) and D's overhead against R.  -> [(label,
    failures, summary)]"""
    out = []
    hud = "bz_hmode" in g.sym
    mill = R.CRS_K["mill"]
    res = {}
    if "demo" in legs:
        for snd in sounds:
            for kd in range(1, len(R.CRS_K)):
                for hm in ((0, 1) if hud else (0,)) + ((2,) if hud and kd == mill else ()):
                    bad, summ = demo_leg(g, tag, kd, hm, snd)
                    res[(kd, hm, snd)] = summ
                    out.append(("D BZD%d %s %s" % (kd, HMODES[hm], snd), bad, summ))
                    if (kd, 0, snd) in res and hm:
                        o = res[(kd, 0, snd)]
                        print("  BZD%d sound %s: HUD %s against OFF - busy %+.0f, misses %+d" % (
                            kd, snd.upper(), HMODES[hm], summ["busy"] - o["busy"], summ["miss"] - o["miss"]))
    if "hudfit" in legs and hud:
        fm = FIT_MODE[tag]
        for hm in (0, fm):
            if (mill, hm, "on") not in res:
                bad, summ = demo_leg(g, tag, mill, hm, "on")
                res[(mill, hm, "on")] = summ
                out.append(("D BZD%d %s on" % (mill, HMODES[hm]), bad, summ))
        o, h = res[(mill, 0, "on")], res[(mill, fm, "on")]
        bad = []
        d = h["miss"] - o["miss"]
        print("\n%s THE HUD'S FIT (SPEC.md 128.14.16 item 3): MILL's route demo, the speaker on - misses %d with the "
              "HUD OFF, %d at %s (%+d; at most %d asserted)" % (tag.upper(), o["miss"], h["miss"], HMODES[fm], d,
                                                                 HUD_MISS), flush=True)
        if d > HUD_MISS:
            bad.append("%s HUD fit: MILL's misses with the speaker on rise by %d at %s over the HUD OFF (at most %d: "
                       "SPEC.md 128.14.16 item 3 - the HUD does not fit and is to be REMOVED)" % (
                           tag, d, HMODES[fm], HUD_MISS))
        out.append(("HUD fit", bad, h))
    if "dover" in legs:
        load_demo(g, mill)
        set_snd(g, False)
        frd, _pkg, _r, _n = measure(g, key="KeyD", frames_cap=DEMO_CAP)
        frr, _pkg, _r, _n = measure(g, key="KeyR", frames_cap=DEMO_CAP)
        bd, br = busy_of(frd), busy_of(frr)
        print("\n%s D's OVERHEAD (SPEC.md 128.14.7.3, REPORTED): MILL's route demo through D busy %.0f clk (p95 %d) "
              "and through R %.0f (p95 %d), under the same outside trace: %+.0f a frame" % (
                  tag.upper(), bd["mean"], bd["p95"], br["mean"], br["p95"], bd["mean"] - br["mean"]), flush=True)
        set_snd(g, True)
    return out


def phase_misses(tag, summ, ab_steps):
    """the A/B leg's misses: one on a frame that ran MORE physics steps than
    wave 3's same frame is the step clock's phase against the refresh (each
    build catches up on its own frames), not the engine's - REPORTED; every
    other miss fails it (SPEC.md 128.13.12).  With no A/B run (the registered
    row: the A/B is the final pass's by-hand run, 128.13.14 item 11) there is
    no same frame to compare, so a miss on a frame running MORE THAN ONE step
    is that phase's by the same rule, REPORTED, and a one-step miss still
    fails (the final pass of wave 3b: CGA frame 400 and the Hercules' frame
    953, two steps each, missed in one run and not in the next).
    -> failures"""
    own, phase = [], []
    for m_ in summ["misses"]:
        i = m_[0] - 1
        s3 = summ["steps"][i]
        s2 = ab_steps[i] if ab_steps and i < len(ab_steps) else None
        (phase if (s3 > s2 if s2 is not None else not ab_steps and s3 > 1) else own).append((m_, s3, s2))
    for m_, s3, s2 in phase:
        print("  the A/B leg's miss at frame %d (busy %d): %d physics steps against %s on %s's same "
              "frame - the step clock's phase, REPORTED" % (
                  m_[0], m_[1], s3, s2 if s2 is not None else "(no A/B run: more than one)", AB_COMMIT[:8]),
              flush=True)
    if not own:
        return []
    return ["%s BENCH, the A/B leg: %d missed refreshes on frames running no more steps than %s's, 0 "
            "asserted (SPEC.md 128.13.12): %s" % (tag, len(own), AB_COMMIT[:8], ", ".join(
                "frame %d busy %d%s" % m_ + " (%s steps, %s %s)" % (s3, AB_COMMIT[:8], s2) for m_, s3, s2 in own[:6]))]


def idle_line(fr, refresh, summ):
    """THE WHEEL'S SPARE RETRACE IDLE (SPEC.md 128.13.15 item 3): the retrace
    wait's part - bz_tv .. bz_tf, the idle the wheel left - a frame, REPORTED"""
    xs = [r["parts"]["retrace wait"] for r in fr if not r["full"] and "parts" in r]
    wh = [r["parts"]["wheel"] for r in fr if not r["full"] and "parts" in r]
    s, w = stats(xs), stats(wh)
    summ["idle"] = s
    print("  the wheel's SPARE retrace idle (the wait after the wheel), a frame: mean %.0f clk (%.1f%% of a refresh), "
          "p10 %d, min %d; the wheel's own part mean %.0f clk" % (s["mean"], 100.0 * s["mean"] / refresh, s["p10"],
                                                                 s["min"], w["mean"]), flush=True)


def heavy_line(tag, pkg, summ):
    print("  the heavy rule (SPEC.md 128.12.7): heavy frames %d, rows withheld %d, columns withheld %d, edge "
          "releases %d; contact groups %d (the platform's box %d), contact lanes that waited %d" % (
              pkg.get("nhvy", 0), pkg.get("nwr", 0), pkg.get("nwc", 0), pkg.get("nhedge", 0), pkg.get("ncon", 0),
              pkg.get("npbx", 0), pkg.get("ndef", 0)), flush=True)


def mill_line(tag, fr, pkg, summ, refresh, assert_lift=False, assert_wheel=True):
    """a MILL leg: bz_wover and bz_wlate 0 ASSERTED (a build with the wheel's
    3b counters, not the A/B's other side); the wheel's, the contact groups'
    and the must-draw frames' figures, and THE LIFT STRETCH, REPORTED - and
    with ASSERT_LIFT (the sound ON, this build's shipped camera) the
    Hercules' stretch at most LIFT_MISS missed refreshes (SPEC.md 128.13.4.5,
    128.13.14 items 2 and 3, 128.13.15 item 2).  -> failures"""
    bad = []
    meas = [r for r in fr if not r["full"] and "busy" in r]
    print("  the wheel: commits %d (the breakpoints %d), LEADs %d, skipped waits %d, overruns %d, lanes late %d, the "
          "trim's lowest %d" % (pkg.get("wcom", 0), sum(r["commits"] for r in fr), pkg.get("wlead", 0),
                                pkg.get("wskip", 0), pkg.get("wover", 0), pkg.get("wlate", 0), pkg.get("wtmin", 0)),
          flush=True)
    sb = stats([r["busy"] for r in meas])
    summ["busy_p95"] = sb["p95"]
    print("  MILL busy mean %.0f (%.0f%%), p95 %d (%.0f%%); contact groups %d, platform boxes %d (bz_npbx), waited "
          "%d (bz_npwt), promotions %d (bz_props.promo), contact lanes that waited %d" % (
              sb["mean"], 100.0 * sb["mean"] / refresh, sb["p95"], 100.0 * sb["p95"] / refresh, pkg.get("ncon", 0),
              pkg.get("npbx", 0), pkg.get("npwt", 0), sum(r["promo"] for r in fr), pkg.get("ndef", 0)), flush=True)
    summ["mill"] = {"npbx": pkg.get("npbx", 0), "ncon": pkg.get("ncon", 0), "npwt": pkg.get("npwt", 0),
                    "promo": sum(r["promo"] for r in fr)}
    must = [r["busy"] for r in meas if r["must"]]
    con = [r["busy"] for r in meas if r["contact"] and not r["must"]]
    pbx = [r["busy"] for r in meas if r["pbox"]]
    for what, xs in (("must-draw rotor", must), ("contact lane", con), ("platform box", pbx)):
        s = stats(xs)
        print("  %s frames %d: busy mean %.0f clk (%.0f%%), p95 %d, max %d (%.0f%%)%s" % (
            what, s["n"], s["mean"], 100.0 * s["mean"] / refresh, s["p95"], s["max"], 100.0 * s["max"] / refresh,
            "" if what != "must-draw rotor" else ": " + ", ".join("%d" % x for x in must[:12])), flush=True)
    print("  MILL's misses, each with its busy (REPORTED: SPEC.md 128.12.11's target is a miss only on the cannon's "
          "flight and the chute's fall): %s" % (", ".join("frame %d busy %d%s" % m_ for m_ in summ["misses"])
                                                 or "none"), flush=True)
    bad += lift_line(tag, fr, refresh, summ, assert_lift)
    for n in ("wover", "wlate"):
        if assert_wheel and pkg.get(n, 0):
            bad.append("%s MILL: bz_%s %d, 0 asserted (SPEC.md 128.13.12)" % (tag, n, pkg[n]))
    return bad


def lift_line(tag, fr, refresh, summ, assert_lift):
    """THE LIFT STRETCH (SPEC.md 128.13.4.5): every frame that draws the
    platform's box or waits one, and the frame after each; its MISSED frames
    (period over 1.5 refreshes, bz_miss's rule), each with its parts, boxes,
    steps and the sound's share; the share of the lift's line changes that
    waited and the longest wait / draw alternation.  -> failures"""
    lift = [i for i, r in enumerate(fr) if r.get("pbox") or r.get("pwt")]
    span = sorted(set(lift) | {i + 1 for i in lift if i + 1 < len(fr)})
    miss = [i for i in span if not fr[i]["full"] and fr[i]["period"] and fr[i]["period"] > 1.5 * refresh]
    nw = sum(1 for r in fr if r.get("pwt"))
    nd = sum(1 for r in fr if r.get("pbox"))
    best = run_ = 0
    last = None
    for i, r in enumerate(fr):
        k = "w" if r.get("pwt") else "d" if r.get("pbox") else None
        if k and last and last[0] == i - 1 and last[1] != k:
            run_ += 1
        else:
            run_ = 1 if k else 0
        best = max(best, run_)
        last = (i, k) if k else None
    summ["lift"] = {"frames": len(span), "miss": len(miss), "waits": nw, "draws": nd, "alt": best}
    print("  THE LIFT STRETCH: %d frames (the platform's box drawn on %d, WAITED on %d: %.0f%% of the lift's line "
          "changes waited; the longest wait / draw alternation %d frames); missed refreshes %d%s" % (
              len(span), nd, nw, 100.0 * nw / float(nw + nd or 1), best, len(miss),
              " (ASSERTED at most %d on the Hercules, REPORTED on the CGA)" % LIFT_MISS if assert_lift else
              " (REPORTED)"), flush=True)
    for i in miss:
        r = fr[i]
        print("    lift miss: frame %d, period %d (%.2f refreshes), BUSY %d (%.0f%%): %s; %d steps, %d boxes, %s%s; "
              "the sound %d clk of it" % (
                  i + 1, r["period"], r["period"] / refresh, r["busy"], 100.0 * r["busy"] / refresh,
                  ", ".join("%s %d" % (p, r["parts"][p]) for p in PARTS if p in r["parts"]), r["steps"], r["boxes"],
                  "WAITED" if r.get("pwt") else "the box" if r.get("pbox") else "the frame after", feats(r),
                  r.get("snd", 0)), flush=True)
    if assert_lift and tag == "herc" and len(miss) > LIFT_MISS:
        return ["%s MILL (sound ON): the lift stretch missed %d refreshes, at most %d asserted on the Hercules "
                "(SPEC.md 128.13.4.5): frames %s" % (tag, len(miss), LIFT_MISS, [i + 1 for i in miss][:12])]
    return []


RIDE_STEPS = 32 + 2 * 128 + 8           # the low dock, a rise and a descent (P 256), and its last dock
RIDE_CORNER = 5                         # gu: the corner ride's ball this far toward the diamond's LEFT
                                        # corner (gx - d, gy + d: 2d px left on the screen) - its footprint's
                                        # words leave the slab's four, so wave 3's two boxes (128.13.4.1)


def ride(g, tag, corner=False, on=True):
    """THE RIDE (SPEC.md 128.13.4.1, 128.13.12): play on MILL, the ball poked
    onto the LIFT's slab at its low dock at the first bz_t0 and carried, no key
    held, up and down - its middle (the RIDE BOX), or with CORNER toward the
    diamond's left corner (two boxes, the residue).  bz_tpoke 1 times its boxes
    (bz_late); a stop at bz_presented reads GLIDE's withheld rows (bz_nwr).
    The middle with the sound OFF (the engine's figure): no miss on a
    line-change frame (the platform's box, bz_cslabr) and bz_late 0,
    ASSERTED; with it ON, and the rest, REPORTED.
    -> (failures, summary)"""
    m = g.m
    crs = R.course("mill")
    P_ = R.plat_rec(crs)
    a = addrs(g)
    pres = a.pop("bz_presented")
    wk = R.Walker(g, t0=True)
    m.bp_exec(g.a("bz_launch"))
    g.key("Enter")
    assert m.wait_stop(60) == "breakpoint", "Enter did not reach bz_launch"
    g.putb("bz_crs", R.CRS_K["mill"])
    g.putb("bz_hvoff", 0)
    g.putb("bz_tpoke", 1)                       # its boxes timed: bz_latechk counts bz_late (128.13.4.1)
    m.bp_exec(wk.t0)
    m.run()
    assert m.wait_stop(60) == "breakpoint", "the MILL play did not reach bz_t0"
    n = g.d("bz_nstep")
    R.slab_ball(g, P_, n, 0, 0, True)
    if corner:                                  # toward the diamond's left corner: gx - d, gy + d
        d = RIDE_CORNER << 8
        gx, gy, gz = g.d("bz_gx") - d, g.d("bz_gy") + d, g.sd("bz_gz")
        R.poke_ball(g, gx, gy, gz, 0, 0, 0, air=0, ztop=gz >> 8)
    m.bp_exec()

    def on_hit(mm, rec):
        return (g.w("bz_nwr"), g.w("bz_late"), g.b("bz_onp"))
    with M.bp_trace(m, *(list(a.values()) + [pres]), log=list(a.values()), on_hit=on_hit,
                    cap=RIDE_STEPS * 90 + 20000) as tr:
        m.run()
        M.until(m, lambda _: g.d("bz_nstep") >= RIDE_STEPS, "the ride's %d steps" % RIDE_STEPS, guest=120)
        m.pause()
        hits = tr.hits
        onp = g.b("bz_onp")
        late = g.w("bz_late")
        g.putb("bz_tpoke", 0)
        m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the ride ends on Esc", guest=60)
    R.dropped(g, "the ride")
    a["bz_presented"] = pres
    fr = frames_of(hits, a)
    meas = [r for r in fr if not r["full"] and "busy" in r]
    refresh = R_REFRESH[tag]
    chg = [r for r in meas if r["pbox"]]
    same = [r for r in meas if not r["pbox"]]
    miss = [(fr.index(r) + 1, r["busy"], bool(r["pbox"]), r["boxes"], r.get("snd", 0)) for r in meas
            if r["period"] > 1.5 * refresh]
    s1, s2 = stats([r["busy"] for r in same]), stats([r["busy"] for r in chg])
    one = sum(1 for r in chg if r["boxes"] == 1)
    # GLIDE's withheld rows: bz_nwr's growth a frame, and the longest run of frames that withheld one
    nwr = [r["hit"][0] for r in fr if r.get("hit")]
    grow = [max(0, b - a_) for a_, b in zip(nwr, nwr[1:])]
    longest = cur = 0
    for x in grow:
        cur = cur + 1 if x else 0
        longest = max(longest, cur)
    what = "CORNER RIDE (the ball %d gu toward the slab's left corner)" % RIDE_CORNER if corner else \
        "RIDE (the ball on the slab's middle: the ride box)"
    lab = "sound %s" % ("ON" if on else "OFF")
    print("\n%s %s, %s (MILL, %d steps, still carried at the end: %s): %d frames; the slab's line unchanged on %d, "
          "busy mean %.0f (%.0f%%) max %d; its line changed on %d (%d of them ONE box), busy mean %.0f (%.0f%%) p95 %d "
          "max %d (%.0f%%); misses %d%s; bz_late %d; GLIDE's rows withheld %d, the longest deferral %d frames" % (
              tag.upper(), what, lab, RIDE_STEPS, "yes" if onp else "NO", len(meas), s1["n"], s1["mean"],
              100.0 * s1["mean"] / refresh, s1["max"], s2["n"], one, s2["mean"], 100.0 * s2["mean"] / refresh,
              s2["p95"], s2["max"], 100.0 * s2["max"] / refresh, len(miss),
              ": " + ", ".join("frame %d busy %d%s, %d boxes, the sound %d" % (
                  f, b, " (a LINE CHANGE)" if c else "", nb, sn) for f, b, c, nb, sn in miss) if miss else "", late,
              sum(grow), longest), flush=True)
    bad = []
    if not chg:
        bad.append("%s %s (%s): no frame drew the platform's box: the ride never rode" % (tag, what, lab))
    if not onp:
        bad.append("%s %s (%s): the ball is no longer carried at the ride's end" % (tag, what, lab))
    # THE ENGINE'S figure is asserted - the ride with the sound OFF (the review of wave 3b, C6): the lift
    # stage MEASURED its line-change p95 at 66.2k and max 67.4k on the CGA, and the speaker's worst frame
    # (a downbeat, 13.4k, SPEC.md 128.20.7) on one of those is a miss decided by where the song's bar falls
    # against the lift's phase, not by the engine - so ON is REPORTED, each miss with its sound share
    # (128.13.15 item 2)
    if not corner:
        lc = [x for x in miss if x[2]]
        if lc and not on:
            bad.append("%s RIDE (sound OFF): %d missed refreshes on line-change frames, none asserted (SPEC.md "
                       "128.13.4.5): %s" % (tag, len(lc), ", ".join("frame %d busy %d, %d boxes, the sound %d" % (
                           x[0], x[1], x[3], x[4]) for x in lc[:6])))
        elif lc:
            print("  %s RIDE (sound ON): %d missed refreshes on line-change frames, REPORTED: %s" % (
                tag.upper(), len(lc), ", ".join("frame %d busy %d (the sound %d of it), %d boxes" % (
                    x[0], x[1], x[4], x[3]) for x in lc[:6])), flush=True)
        if late and not on:
            bad.append("%s RIDE (sound OFF): bz_late %d, 0 asserted (a ride box the beam overtook, SPEC.md "
                       "128.13.4.1)" % (tag, late))
        elif late:
            print("  %s RIDE (sound ON): bz_late %d, REPORTED" % (tag.upper(), late), flush=True)
    return bad, {"same": s1, "change": s2, "miss": miss, "late": late, "one": one, "withheld": sum(grow),
                 "defer": longest}


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
    """-> None when the commit is in this clone, else why not and the command
    that would bring it.  A ROW never fetches (the review of wave 3b, R1):
    unshallowing or fetching is a network fetch and a change to the user's
    repository as a side effect of a test, and its result changes what later
    git ancestry answers say (docs/UPSTREAM.md Rule 0) - so the reason names
    the command and the person runs it"""
    if reachable(commit):
        return None
    shallow = git("rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    return "%s is not in this clone (%s; `git fetch origin %s` asks for it by its full id) - after upstream's " \
           "squash merge no clone of main has it" % (
               commit, "SHALLOW: `git fetch --unshallow` first, docs/UPSTREAM.md Rule 0" if shallow else "not shallow",
               commit)


def ab_tree(td, commit=AB_COMMIT):
    """An earlier wave's package with ITS OWN art, built in TD out of git:
    -> (floppy, source dir, art dir).  Wave 1's recipe (its Makefile's
    bonanza block): bonanza_assets.py and bbcourse.py over its BZ_COURSES,
    the parts the ball's two then each course's two."""
    w = os.path.join(td, "w")
    os.makedirs(w)
    names = git("ls-tree", "--name-only", commit, "apps/").stdout.split()
    incs = [n for n in names if n.startswith("apps/os88") and n.endswith(".inc")]
    tools = [t for t in ("tools/bonanza_assets.py", "tools/bbcourse.py", "tools/bbmusic.py")
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
    for line in mk.replace("\\\n", " ").splitlines():      # (its continuation lines joined: wave 3's
        if line.startswith("BZ_COURSES :="):                # list runs over two)
            order = line.split(":=", 1)[1].split()
    if order and "tools/bbcourse.py" in tools:
        subprocess.run([sys.executable, os.path.join(w, "tools", "bbcourse.py"), "-o", art] +
                       [os.path.join(w, c) for c in order], cwd=w, check=True, stdout=subprocess.DEVNULL)
    if "BZ_SNDPARTS" in mk and "tools/bbmusic.py" in tools:     # 3b's sound (SPEC.md 128.20): its own songs
        subprocess.run([sys.executable, os.path.join(w, "tools", "bbmusic.py"), "-o", art], cwd=w, check=True,
                       stdout=subprocess.DEVNULL)
    src = os.path.join(w, "apps", "bonanza")
    binp, o88, img = (os.path.join(td, n) for n in ("bonanza.bin", "BONANZA.O88", "bonanza360.img"))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(w, "apps") + "/", "-I", src + "/",
                    "-I", art + "/", "-o", binp, os.path.join(src, "bonanza.asm")], cwd=R.ROOT, check=True)
    nc = len(order) if order else len(crs)
    if "BZBALR.BIN" in mk:                      # wave 2's part order (its Makefile's BZ_PARTS): the three
        plist = ["BZBALR.BIN", "BZBALS.BIN", "BZBALG.BIN"] + ["BZ%d.BIN" % k for k in range(nc)]   # balls, a
    else:                                       # course a part; wave 1's: the ball's two, each course's two
        plist = ["BZBALC.BIN", "BZBALH.BIN"] + ["BZ%d%s.BIN" % (k, c) for k in range(nc) for c in "CH"]
    if "BZ_SNDPARTS" in mk:                     # 3b's: the sound part and a part a song, after the courses
        import re
        ns = int(re.search(r"^BZS_NSONG\s+equ\s+(\d+)", open(os.path.join(art, "bzsnd.inc")).read(),
                           re.M).group(1))
        plist += ["BZSND.BIN"] + ["BZM%d.BIN" % i for i in range(ns)]
    parts = []
    for p in plist:
        parts += ["--part", os.path.join(art, p)]
    subprocess.run([sys.executable, "tools/os88pkg.py", "--compress-if=lz4", binp, "-o", o88] + parts,
                   cwd=R.ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "tools/os88disk.py", "-o", img, "--size", "360", o88], cwd=R.ROOT,
                   check=True, stdout=subprocess.DEVNULL)
    return img, src, art


def ab_print(tag, res, ores, commit):
    """the A/B (SPEC.md 128.13.12): BENCH, sound OFF and bz_hvoff 1 on both,
    part by part - its mean busy at least AB_BUSY under wave 3's on the CGA,
    ASSERTED (128.13.14 item 11), the Hercules' REPORTED - and MILL three
    ways, side by side.  -> failures"""
    new = dict((lab, s) for lab, _, s in res)
    old = dict((lab, s) for lab, _, s in ores)
    bad = []
    if "BENCH off" in new and "BENCH off" in old:
        n, o = new["BENCH off"], old["BENCH off"]
        print("\n%s A/B: BENCH, this build against %s, sound OFF and bz_hvoff 1 on both (busy: all but the retrace "
              "wait and the wheel)" % (tag.upper(), commit))
        print("  %-14s %9s %9s %9s" % ("", "wave 4", commit[:8], "delta"))
        for p in PARTS + ["busy", "period"]:
            a = n["parts"].get(p, 0) if p in PARTS else n[p]
            b = o["parts"].get(p, 0) if p in PARTS else o[p]
            print("  %-14s %9.0f %9.0f %+9.0f" % (p, a, b, a - b))
        print("  %-14s %8.1f%% %8.1f%%" % ("busy share", 100.0 * n["busy"] / n["refresh"],
                                            100.0 * o["busy"] / o["refresh"]))
        print("  %-14s %9d %9d" % ("misses", n["miss"], o["miss"]))
        d = n["busy"] - o["busy"]
        print("  BENCH's mean busy %+.0f clk against %s's (at most +%d ASSERTED on both cards, SPEC.md 128.14.17 "
              "item 7; PREDICTED +150 - 300 on the CGA, 128.14.12)" % (d, commit, AB_OVER))
        if d > AB_OVER:
            bad.append("%s A/B: BENCH's mean busy %.0f clk against %s's %.0f, %+.0f - at most +%d asserted "
                       "(SPEC.md 128.14.17 item 7)" % (tag, n["busy"], commit, o["busy"], d, AB_OVER))
    ways = [("this build", new.get("MILL off")), ("bz_hvoff 1", new.get("MILL off hvoff")),
            (commit, old.get("MILL off"))]
    if all(w[1] for w in ways):
        print("\n%s MILL three ways, sound OFF (REPORTED, SPEC.md 128.13.12):" % tag.upper())
        print("  %-12s %8s %8s %6s %6s %6s %6s %6s %9s" % ("", "busy", "p95", "misses", "npbx", "ncon", "npwt",
                                                          "promo", "lift miss"))
        for what, s in ways:
            mi = s.get("mill", {})
            print("  %-12s %8.0f %8d %6d %6d %6d %6s %6s %9s" % (
                what, s["busy"], s.get("busy_p95", 0), s["miss"], mi.get("npbx", 0), mi.get("ncon", 0),
                mi.get("npwt", "-") if what != commit else "-", mi.get("promo", "-") if what != commit else "-",
                s.get("lift", {}).get("miss", "-")))
    return bad


REDS = {
    # the calibration's word-line HALVED after it runs: the wheel underprices its
    # commits and the late ones end past their deadline (SPEC.md 128.12.13.2)
    "halfcal": [("bzwheel.inc", "    call .min1\n    mov [bz_warr], ax\n.lcf:\n",
                 "    call .min1\n    mov [bz_warr], ax\n    shr word [bz_wlw], 1        ; RED halfcal (before bz_lcf)\n"
                 ".lcf:\n")],
    # wave 3b (SPEC.md 128.13.12): the ride merge's limit back to BZ_BOXH - the riding line change is two
    # boxes again, each laying the slab and the ball: the CGA's ride misses (about 85k against 79.6k,
    # PREDICTED; the Hercules' 87k fits its 93.8k, so the arm is the CGA's)
    "rideoff": [("bzgame.inc", "    cmp ax, BZ_BOXL             ; CF = it fits ...\n",
                 "    cmp ax, BZ_BOXH             ; RED rideoff: no ride box\n")],
    # level 1's occluder-pass and two-box clauses restored (wave 3's bz_hv1, 128.13.6): TRIAL's frames
    # heavy again
    "level1": [("bzwheel.inc", "bz_hv1:\n    test byte [bz_pflag], 2     ; (CF = 0)\n    jz .x\n"
                "    stc\n.x:\n    ret\n",
                "bz_hv1:                         ; RED level1: wave 3's three clauses\n"
                "    cmp byte [bz_tube], 0\n    jne .rn\n    test byte [bz_pflag], 2\n    jnz .ry\n"
                "    push ax\n    push bx\n    push si\n    call bz_passon\n    jnz .rp\n"
                "    cmp byte [bz_oldv], 0\n    je .rq\n    mov si, bz_nfx0\n    mov bx, bz_ofx0\n"
                "    call bz_union\n    jmp short .rx\n.rp:\n    stc\n    jmp short .rx\n.rq:\n    clc\n"
                ".rx:\n    pop si\n    pop bx\n    pop ax\n    ret\n.ry:\n    stc\n    ret\n.rn:\n    clc\n"
                "    ret\n")],
    # wave 4 (SPEC.md 128.14.14): B's HUD not forced OFF - B with H at FOLLOW draws the HUD
    "hudon": [("bzhud.inc", "    cmp byte [bz_mode], 1\n    jne .u\n    mov al, BZ_HOFF\n.u:\n",
               "    nop                         ; RED hudon: B keeps H's mode\n.u:\n")],
}
# each arm's legs and sound: the ones its check is asserted in
RED_LEGS = {"halfcal": (("mill",), ("off",)), "rideoff": (("ride",), ("off",)), "level1": (("trial",), ("off",)),
            "hudon": (("bench",), ("off",))}
RED_TAGS = {"rideoff": ("cga",)}
RED_WANT = {"halfcal": "bz_wover", "rideoff": "line-change frames", "level1": "bz_nhvy", "hudon": "bz_nhud"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--apps", help="the B: floppy to run instead of build/bonanza360.img")
    ap.add_argument("--src", help="the package source that floppy was built from (default apps/bonanza)")
    ap.add_argument("--art", help="the art directory that source assembled against (default build/bonanza-art)")
    ap.add_argument("--ab", nargs="?", const=AB_COMMIT, metavar="COMMIT",
                    help="also measure COMMIT's package (default %s, wave 3) built with its own art" % AB_COMMIT)
    ap.add_argument("--no-trial", action="store_true", help="no TRIAL leg, no camera")
    ap.add_argument("--leg", choices=LEGS, action="append", help="only these legs (default all)")
    ap.add_argument("--sound", choices=SOUNDS, action="append", help="only these sounds (default off and on)")
    ap.add_argument("--no-adlib", action="store_true", help="no AdLib arm (the CGA's MILL and ride on %s)" % ADLIB)
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only: every red arm assembles")
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.check:
        for line in R.check_reds({k: v for k, v in REDS.items() if k != "hudon" or "bz_hmode" in R.symbols()},
                                 "bonanza_perf"):
            print(line)
        return
    if a.red:
        tags = tuple(t_ for t_ in tags if t_ in RED_TAGS.get(a.red, tags)) or RED_TAGS.get(a.red, tags)
        legs, sounds = RED_LEGS[a.red]
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags:
                try:
                    bad = [b for _, bb, _ in run(tag, img, src, legs=legs, sounds=sounds) for b in bb]
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
            print("bonanza_perf: SKIP the A/B leg: %s.  This build runs alone; the row exits %d, which is not a pass"
                  % (skip, SKIP_RC), flush=True)
            a.ab = None
    td = tempfile.mkdtemp(prefix="bzab") if a.ab else None
    try:
        ab = ab_tree(td, a.ab) if a.ab else None
        for tag in tags:
            ores = None
            if ab:                                  # wave 3 first: its frames' step counts judge the A/B's misses
                ores = run(tag, *ab, trial=False, legs=tuple(x for x in legs if x in ("bench", "mill")), old=True)
                for label, obad, _ in ores:
                    for b in obad:
                        print("FAIL %s (%s): %s" % (tag, a.ab, b))
                    allbad += ["%s: %s" % (a.ab, b) for b in obad]
            ob = [s for lab, _, s in ores or () if lab == "BENCH off"]
            res = run(tag, a.apps, a.src, a.art, trial=not a.no_trial, legs=legs,
                      ab_steps=ob[0]["steps"] if ob else None, sounds=tuple(a.sound) if a.sound else SOUNDS)
            for label, bad, _ in res:
                for b in bad:
                    print("FAIL %s %s: %s" % (tag, label, b))
                allbad += bad
            if ores:
                bad = ab_print(tag, res, ores, a.ab)
                for b in bad:
                    print("FAIL %s A/B: %s" % (tag, b))
                allbad += bad
            if tag == "cga" and not a.no_adlib and "on" in (a.sound or SOUNDS):
                # THE ADLIB ARM (SPEC.md 128.13.15 item 2): S's AUTO on the 5150 with an AdLib plays the
                # chip - MILL's lift stretch and the ride, REPORTED (nothing asserted)
                print("\nCGA, THE ADLIB ARM (%s, the sound at AUTO): REPORTED" % ADLIB, flush=True)
                for label, bad, _ in run(tag, a.apps, a.src, a.art, trial=False, sounds=("on",), machine=ADLIB,
                                         legs=tuple(x for x in legs if x in ("mill", "ride"))):
                    for b in bad:
                        print("  (AdLib, REPORTED) %s %s: %s" % (tag, label, b))
    finally:
        if td:
            shutil.rmtree(td, ignore_errors=True)
    assert not allbad, "%d failure(s)" % len(allbad)
    if skip:
        print("\nbonanza_perf (%s): this build measured; the A/B leg SKIPPED: %s" % (", ".join(tags), skip))
        sys.exit(SKIP_RC)
    print("\nbonanza_perf (%s%s): PASS" % (", ".join(tags), ", A/B against %s" % a.ab if a.ab else ""))


if __name__ == "__main__":
    main()
