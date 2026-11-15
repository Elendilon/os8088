#!/usr/bin/env python3
"""BONANZA: the frame's cost on MartyPC's 4.77 MHz XT, CGA and Hercules (SPEC.md 128.4, 128.10.11.3, 128.11.15, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_perf.py [--adapter cga|herc|both] [--ab [COMMIT]] [--no-trial]
                                                      [--fmt-ab]
                                                      [--leg bench|trial|mill|ride|corner ...] [--sound off|on]
    python3 tests/bonanza_perf.py --red rideoff|level1 | --check
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
line-change frames and of the others, reported - O30).  (--red halfcal,
bz_wlw halved after the calibration, failed the MILL leg at bz_wover until
wave 6b; retired here, kept in bonanza_wheel.)  --red rideoff (the ride merge's limit back to BZ_BOXH: two boxes a riding
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
CARDS (PREDICTED +0.15 - 0.3k on the CGA, 128.14.12).  THE DEMO LEGS (`demo`): every
shipped demo (V with bz_vk poked, BZD1 - BZD6) through D on both cards, sound
OFF and ON: ASSERTED the replay's end the model's (bonanza_demo.model_end),
bz_wover and bz_wlate 0; REPORTED busy mean and p95, the misses with their
parts, pads, springs and lip-outs.  D's OVERHEAD (`dover`): MILL's route demo
through D and through R under the same outside trace, busy compared, REPORTED.
(Wave 4's HUD legs - the HUD's fit, REST and FOLLOW, and B's no-HUD-box check
with its red arm `hudon` - went in wave 5a with the HUD, which was not built:
SPEC.md 128.14.26, 128.15.3.)

WAVE 5B (SPEC.md 128.15.13): two A/Bs, each a by-hand run at one commit, not
the registered row's (which runs this build's legs alone):

    python3 tests/bonanza_perf.py --ab --fmt-ab

(The third, --rec-ab, THE D/C ACCEPTANCE of SPEC.md 128.15.5.4, ran twice
and left with the losing arm, as that subsection says.  5b's final pass
shipped C under the first rule (D +23.5 summed misses on the CGA, past +2,
almost all MILL's camera tipping between two modes).  The owner re-opened it
under the SMOOTHNESS rule (2026-11-14: missed refreshes a second off the
flip, MILL compared within one camera mode, no new stutter), and the second
run measured D within +0.16 a second of C on both cards with no new stutter
(its red arm, occslow, went red at +2.10 and +11.50), so D ships and C's arm
and this leg were deleted.  The figures are 128.15.5.4's.)

  --ab      BENCH against the ANCHOR, ef59209a - the last BZC1 tree, whose
            package wave 5a's is byte for byte - built out of git with its own
            art, sound, demos and part order: this build's mean busy at most
            +0.5k over it ASSERTED on both cards, the standing guard on the
            frame's cost (re-anchored at 5b's commit only for later waves).
  --fmt-ab  THE PARTS' FORMAT (128.15.9), REPORTED: the shipped parts' format
            (the table's, R.part_fmt) against the other in a private tree -
            bonanza360.img's clusters with each, and PEAK's and MOON's launch
            timed from bz_launch's entry to the kernel's fsx_run (every part
            fetched and expanded) on both cards.

Every private tree here packs its parts in the shipped build's format (its
part table's byte, R.part_fmt), not os88pkg's default (128.15.9).

WAVE 6 (SPEC.md 128.16.10, 128.16.14).  The physics moves every demo's path
and BENCH's course, so NOTHING end to end is asserted against an earlier
build: the final pass REPORTS, both cards, speaker ON (the `demo` leg, all
six shipped demos BZD1 - BZD6 through D):
  - per demo: misses, MISSED REFRESHES A SECOND off each frame's flip (a
    frame held k refreshes misses k - 1; a second is the frames' own clocks),
    runs of two or more misses (the stutter half of the owner's smoothness
    rule) and the longest run, MILL's columns panned against the host's
    prediction (5b's 49- and 84 - 88-column modes, 128.15.5.4, no longer
    classify it: wave 6's physics predicts 106 on the CGA - the review's C1),
    GLIDE's columns and rows panned a second of play against the HOST'S
    PREDICTION (the demo's log replayed through bbcourse.Glide at the card's
    step rate: `bbcourse.py --pans`'s figure, bbcourse.pans, 128.16.13), and
    the occluder pass's span a frame (bz_occ's gate to
    bz_pover) - each beside 5b's when --ab ran 5b's own demos;
  - TRIAL's bounce leg (the camera's replays): the rows panned a bounce in
    GLIDE and TRICKLE under the GROUND LINE, against wave 2's 251 and 137
    (CGA) - REPORTED;
  - --ab's default is now 5b's commit, 503031d4 (its own art, sound and
    demos): BENCH's busy REPORTED against it (wave 6 moves BENCH's course:
    not like for like, so the +0.5k guard is not asserted until the freeze
    re-anchors it, 128.16.10), and its demos through D beside this build's.
--baseline (THE RE-BASELINE, at the FREEZE commit only, 128.16.10 - not this
wave's final pass): every shipped demo through D and B, both cards, speaker
OFF and ON, six runs a configuration for MILL and PEAK and three for the rest
(2 x 2 x (2 x 6 + 5 x 3) = 108 runs with six demos), each figure with its
spread (min - max, mean) and MILL's runs classified by mode, each row keyed to
its demo's log (its identity, steps and the CRC of its runs); the table is
written to docs/reports/BONANZA-BASELINE-<date>.md (a NEW report).

WAVE 6B (SPEC.md 128.17.10, story 6b.7).  The camera is LATTICE; every figure
is REPORTED, both cards, against wave 6's final pass (128.16.10) and the
host's 128.17.6.6:
  - per demo through D (sound OFF and ON) and B: misses, missed refreshes a
    second, runs of two or more misses and the longest run (the half-rate
    stretches), GLIDE's columns and rows a second against `--pans` (LATTICE's
    prediction, wave 6's policy's beside it), two-row frames against the
    host's, and THE FRAMES IN A TUBE (bz_lexit hit: LATTICE's pre-aim runs
    once a frame while a tube carries the ball) - their misses against the
    run's other frames; a run with at least two missed tube frames whose
    tube frames miss more often than its others by more than one tube
    frame's worth is printed as 128.17.6.8's IN-TUBE RULE'S TRIGGER;
  - THE FALL LEG (`fall`): FIRST's autopilot - a loop of falls and
    respawns - run as the benchmark (B with bz_crs poked, speaker ON; a
    replay through R would end at the goal FIRST's autopilot crosses before
    its first fall): each fall's misses, missed refreshes and runs
    (128.17.6.6 risk 8).
--lattice-ab [COMMIT] (the final pass's by-hand run, like every A/B here: a
row that could only fail once the commit has left the clone is no row; exits
77 when it is not in this clone) is THE LIKE-FOR-LIKE A/B the decision rides
on: MILL's route demo, whose keys hold neither Space nor Grip, runs the same
path in wave 6's build (4d69985c, GLIDE) and this one (LATTICE) - the leg
ASSERTS the two demos' key bytes carry no Space or Grip bit and are the same
- through D, three runs a side, speaker ON, both cards; B beside it REPORTED
only (its route pans a third of wave 6's work, 128.17.6.7: B's series breaks
at 6b).  THE DECISION is computed and printed: LATTICE ships on round 2's
disk if, on both cards, this build's missed refreshes a second and longest
run of misses (each its three runs' mean) are no worse than 4d69985c's
beyond the spread of its three runs (at most their maximum); otherwise the
figures go to the owner with the disk held.  No red arm is new: `rideoff`
and `level1` re-run (level1's anchor is bz_hv1's text, which 6b left as it
was: the near-edge bits went into bz_pnear); `halfcal` is retired here (its
bz_wover never fires under LATTICE's MILL frames) and kept in bonanza_wheel.
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zlib

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
WRITERS = ["bz_row", "bz_col", "bz_fullw", "bz_boxw", "bz_step",     # (bz_step: the frame's physics steps)
           "bz_lexit"]                  # (wave 6b: LATTICE's pre-aim, called once a frame while a tube carries
                                        # the ball - the frame IN A TUBE, SPEC.md 128.17.10; a build without it
                                        # counts none)
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
AB_COMMIT = "503031d470aa776b8cea39548aa8bbe2e74f755b"   # wave 6 (SPEC.md 128.16.10): 5b's commit, REPORTED
                               # against (the FULL id: git fetches an object only by it).  Wave 5b's anchor was
                               # ef59209a, the last BZC1 tree (128.15.13); wave 4's 3b's head, 573eec83
AB_OVER = 500                  # 128.14.17 item 7, kept by 128.15.13: BENCH's mean busy at most this much OVER
                               # the anchor's, BOTH cards - the standing guard on the frame's cost
AB_ASSERT = False              # wave 6 (128.16.10): BENCH's course moved, so the guard is REPORTED until the
                               # freeze commit re-anchors it on its own package (three runs for its spread)
W2_TRIAL_ROWS = {"GLIDE": 251, "TRICKLE": 137}   # wave 2's rows over TRIAL's five bounces, CGA (128.16.7)
STEP_HZ = BB.PIT_HZ / float(BB.STEP_PIT)          # steps a second of play (54.6)
# (wave 6's review C1: 5b's MILL_MODE_COLS split - under 67 columns its "49-column mode" - is gone: under wave
# 6's physics MILL's demo pans 106 columns on the CGA, which that split would have reported as one of 5b's two
# known modes.  MILL's columns are reported against the host's prediction, bbcourse.pans, instead)
DEMO_CAP = 4000                # frames a shipped demo's D presents at most (MOON's: ~2,300 on the CGA)
LIFT_MISS = 3                  # 128.13.4.5: the Hercules' lift stretch, missed refreshes at most (sound ON)
SND_OFF, SND_AUTO = 3, 0       # bzs_mode: OFF, and AUTO (the speaker on a 5150 without an AdLib)
SKIP_RC = 77
# WAVE 5B (SPEC.md 128.15.5.4, 128.15.9): the occluder pass's span a frame - its gate open (bz_occ.gate) to
# the call after it (bz_pover, called every frame) - logged like the writers
OCC = ("bz_occ.gate", "bz_pover")
# ...and inside that span, with measure(framed=True) (5b's D/C A/B used it; kept as the instrument): every bz_olay (a group laid into a
# box: its count moves with the box layout, which follows the LAST PRESENTED frame and so differs between
# two builds at one step n) and every entry to the kernel's int 08h handler (sch_isr, 54.6 Hz under
# FSXF_FASTTICK: an IRQ inside the span adds its whole cost) - so D - C is compared only on frames where
# both builds laid as many groups and took no tick inside the pass (the review's S3)
OLAY, IRQ0 = "bz_olay", "sch_isr"
FMT_COURSES = ("peak", "moon")  # 128.15.9: the launches the format A/B times


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
    occ, o0, nsum, nolay, oirq = 0, None, 0, 0, 0
    for h in hits:
        n = by.get(h["addr"] & 0xFFFFF)
        c = h["cycles"]
        if n in (OLAY, IRQ0):                   # (logged only by the D/C A/B: inside the span or not at all)
            if o0 is not None:
                if n == OLAY:
                    nolay += 1
                else:
                    oirq += 1
            continue
        if n == OCC[0]:                         # the occluder pass, its gate open ...
            o0 = c
            continue
        if n == OCC[1]:                         # ... to the call after it
            if o0 is not None:
                occ += c - o0
            o0 = None
            continue
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
               "pwt": cnt["bz_props.pwt"], "promo": cnt["bz_props.promo"], "snd": snd, "hit": h.get("hit"),
               "occ": occ, "n": nsum + cnt["bz_step"], "olay": nolay, "oirq": oirq, "tube": cnt["bz_lexit"] > 0}
        nsum += cnt["bz_step"]                  # (n: the steps run by this frame's end, the same in two
        occ = nolay = oirq = 0                  # builds that replay one log: the occluder A/B's key)
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
    out.update({n: g.a(n) for n in OCC if n in g.sym})
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


def measure(g, crs=None, pokes=None, key="KeyB", frames_cap=BENCH, framed=False):
    """one benchmark under logged breakpoints: -> (frames, the package's
    instruments, the refresh in clocks, presented hits).  CRS: the course
    poked into [bz_crs] at bz_launch's entry; POKES {bss byte: value} poked
    there too (a name the build lacks is skipped: wave 2's).  Wave 4: KEY
    `KeyD` measures the held log's DEMO benchmark (128.14.7.3) and `KeyR` its
    plain replay (the package's instruments then not filled: pkg None).
    FRAMED (wave 5b, SPEC.md 128.15.5.4): the guest paused, stepped to the
    card's next COMPLETED frame and the key pressed there, so its phase
    against the refresh is the same in every run"""
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
    if framed:                                  # the D/C A/B's span instruments (OLAY, IRQ0 above)
        if OLAY in g.sym:
            a[OLAY] = g.a(OLAY)
        a[IRQ0] = m.sym(IRQ0)
    logged = list(a.values())
    if framed:
        m.pause()
        m.advance(frames=1)                     # (it ends stopped, on the frame's completion)
        m.key(key, up=False)
        m.run()
    with M.bp_trace(m, *(list(a.values()) + [launch]), log=logged, on_hit=on_launch,
                    cap=frames_cap * (128 if framed else 64) + 20000) as tr:
        if framed:
            M.pace(m, .04)
            m.key(key, down=False)
        else:
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


LEGS = ("bench", "trial", "mill", "ride", "corner", "demo", "dover", "fall")
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
        if old:                                 # (the A/B's BENCH and MILL are OFF; its demos as asked)
            sounds = tuple(sounds) if "demo" in legs else ("off",)
        for snd in sounds:
            on = snd == "on"
            set_snd(g, on)
            lab = " (sound %s)" % snd.upper()
            if "bench" in legs and not (old and on):
                # OFF: THE A/B LEG, LIKE FOR LIKE - wave 3 has no sound, and both builds run [bz_hvoff] 1 (no
                # heavy rule), engine against engine.  ON: the shipped camera, as played (REPORTED)
                hv = 1 if not on else 0
                fr, pkg, refresh, npres = measure(g, pokes={"bz_hvoff": hv})
                bad, summ = report("%s BENCH (bz_hvoff %d)%s" % (tag, hv, lab), fr, pkg, refresh, npres)
                summ["busy_p95"] = busy_of(fr)["p95"]
                idle_line(fr, refresh, summ)
                if on:                          # (its busy and misses REPORTED; the floor and the
                    heavy_line(tag, pkg, summ)  # instruments' agreement asserted as on every leg)
                elif not old and summ["miss"]:
                    bad += phase_misses(tag, summ, ab_steps)
                out.append(("BENCH " + snd, bad, summ))
            if old:
                if "mill" in legs and not on:
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
        if set(legs) & {"demo", "dover"}:
            out += demo_legs(g, tag, legs, sounds, old, art)
        if "fall" in legs and not old:          # wave 6b (SPEC.md 128.17.10): FIRST's fall-and-respawn replay
            bad, summ = fall_leg(g, tag)
            out.append(("fall", bad, summ))
        set_snd(g, True)                        # (S back at AUTO for whatever runs next)
    return out


# ---- WAVE 4 (SPEC.md 128.14.7.3, 128.14.14): the DEMO legs ------------


def load_demo(g, kd, art=None):
    """V with bz_vk poked to KD - 1: the shipped demo BZD<KD>.BIN in the log
    (ART: another build's art directory, --ab's)"""
    m = g.m
    demo = open(os.path.join(R.ROOT, art or R.at("build/bonanza-art"), "BZD%d.BIN" % kd), "rb").read()
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


def demo_leg(g, tag, kd, snd, old=False, art=None):
    """one shipped demo through D: -> (failures, summary).  ASSERTED its end the
    model's (not for OLD: an earlier physics' demo is not this model's),
    bz_wover and bz_wlate 0; REPORTED the rest, and wave 6's figures (w6_line)"""
    import bonanza_demo as DM
    demo = load_demo(g, kd, art)
    set_snd(g, snd == "on")
    lab = "%s D of BZD%d (sound %s)%s" % (tag, kd, snd.upper(), " [%s]" % AB_COMMIT[:8] if old else "")
    fr, pkg, refresh, npres = measure(g, key="KeyD", frames_cap=DEMO_CAP)
    bad, summ = report(lab, fr, pkg, refresh, npres)
    got = DM.end_state(g)
    want = None if old else DM.model_end(demo, len(got) > 8)
    if want is not None and got != want:
        bad.append("%s: D ended at %s, the model's replay of the demo at %s" % (lab, got, want))
    summ["w6"] = w6_line(lab, tag, fr, refresh, demo, kd, pred=not old)
    for n in ("wover", "wlate"):
        if pkg.get(n, 0):
            bad.append("%s: bz_r%s %d, 0 asserted (SPEC.md 128.14.14)" % (lab, n, pkg[n]))
    summ["busy_p95"] = busy_of(fr)["p95"]
    print("  %s: busy mean %.0f p95 %d, misses %d (%s), pads %s, springs %s, lip-outs %s" % (
        lab, summ["busy"], summ["busy_p95"], summ["miss"],
        "; ".join("frame %d busy %d%s" % x for x in summ["misses"][:8]) or "none",
        g.w("bz_npad") if "bz_npad" in g.sym else "-", g.w("bz_nspr") if "bz_nspr" in g.sym else "-",
        g.w("bz_nlip") if "bz_nlip" in g.sym else "-"), flush=True)
    return bad, summ


def demo_legs(g, tag, legs, sounds, old=False, art=None):
    """every shipped demo through D, sound OFF and ON, and D's overhead
    against R.  OLD: --ab's build, its own demos (its art's BZD*.BIN), no
    overhead leg.  -> [(label, failures, summary)]"""
    out = []
    mill = R.CRS_K["mill"]
    nd = len(R.CRS_K) - 1
    if old:
        nd = len([f for f in os.listdir(art) if re.match(r"BZD\d+\.BIN$", f)])
    if "demo" in legs:
        for snd in sounds:
            for kd in range(1, nd + 1):
                bad, summ = demo_leg(g, tag, kd, snd, old, art)
                out.append(("D BZD%d %s" % (kd, snd), bad, summ))
    if old:
        return out
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


# ---- WAVE 5B (SPEC.md 128.15.9): the parts' format A/B (the D/C A/B left once D shipped, 128.15.5.4) ---
def course_paths():
    """the shipped courses' files in BZ_COURSES's order (bzcourse.inc's own list, R.COURSES)"""
    R.CRS_K["bench"]
    R.COURSES["bench"]
    order = sorted(dict.keys(R.CRS_K), key=lambda n: dict.__getitem__(R.CRS_K, n))
    return [os.path.join(R.ROOT, dict.__getitem__(R.COURSES, n)) for n in order]


def clusters(o88):
    """bonanza360.img's clusters with O88: the package, the README as bonanzadisk ships it and
    SYSTEM\\APPDATA, by os88disk.py's own count -> (used, of)"""
    readme = R.at("build/zdata-lz4/bonanza/README.md")
    if not os.path.exists(os.path.join(R.ROOT, readme)):
        readme = os.path.join(R.ROOT, "apps", "bonanza", "README.md")
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, "tools/os88disk.py", "-o", os.path.join(td, "b.img"), "--size", "360",
                            o88, readme, "--folder", "SYSTEM/APPDATA"], cwd=R.ROOT, capture_output=True, text=True,
                           check=True)
    m_ = re.search(r"(\d+)/(\d+) clusters", r.stdout)
    return (int(m_.group(1)), int(m_.group(2))) if m_ else (None, None)


def launch_times(tag, apps, src, art, label):
    """FMT_COURSES' launches on one boot: Enter with [bz_crs] and [bz_matsel]
    (the course's own ball) poked at bz_launch's entry, the launch timed by
    MartyPC's cycle counter from that entry to the kernel's fsx_run (the
    OSAPI_FSX_RUN call: every part fetched and expanded), then Esc.
    -> {course: (seconds, floppy reads)}"""
    sym = R.symbols(src, art)
    out = {}
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym, live=True)      # (a launch claims and drops: the region may move)
        ui.settle()
        m = g.m
        for name in FMT_COURSES:
            launch, fsx = g.a("bz_launch"), m.sym("fsx_run")
            stops = []
            ball = R.course(name).ball          # (compiled HERE: on_hit runs with the guest stopped, and a
            #                                      course's compile there outlasts every pause's backstop)

            def on_hit(mm, rec, name=name, launch=launch, stops=stops, ball=ball):
                if rec["addr"] == launch & 0xFFFFF:
                    g.putb("bz_crs", R.CRS_K[name])
                    g.putb("bz_matsel", ball)
                    stops.append(rec["cycles"])
            M.until(m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)
            m.disk(reset=True)
            with M.bp_trace(m, launch, fsx, log=[fsx], on_hit=on_hit) as tr:
                g.key("Enter")
                M.until(m, lambda _: g.b("bz_fs") == 1, "%s's bracket (%s)" % (name, label), guest=60)
                hits = list(tr.hits)
            reads = m.disk()["reads"]
            c0 = stops or [h["cycles"] for h in hits if h["addr"] == launch & 0xFFFFF]
            c1 = [h["cycles"] for h in hits if h["addr"] == fsx & 0xFFFFF]
            assert c0 and c1, "%s %s: the launch's marks were not both hit (%d, %d)" % (label, name, len(c0), len(c1))
            out[name] = ((c1[0] - c0[0]) / float(CLK), reads)
            g.key("Escape")
            M.until(m, lambda _: g.b("bz_fs") == 0, "%s's play to end on Esc" % name, guest=60)
            M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "%s's parts dropped" % name, guest=30)
            if "bzs_desk" in g.sym:
                M.until(m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3, "the title back", guest=30)
            print("  %s %s: %s's launch, bz_launch to fsx_run, %.2f s; %d floppy reads" % (
                tag, label, name.upper(), out[name][0], reads), flush=True)
    return out


def fmt_ab(tags, td):
    """THE PARTS' FORMAT A/B (SPEC.md 128.15.9), REPORTED: the shipped build
    (its parts in the table's format, LZB unless a single-format kernel
    forced LZ4) against the same package with every part LZ4 (BZPARTZ=lz4: a
    private tree, R.build_tree's fmt) - bonanza360.img's clusters with each,
    and PEAK's and MOON's launch to the bracket on both cards.  -> failures
    (none: it reports)"""
    ship = R.part_fmt()
    other = "lz4" if ship == "lzb" else "lzb"
    src, img = R.build_tree(td, [], name="bonanzafmt", fmt=other)
    o88s = {ship: os.path.join(R.ROOT, R.at("build/bonanza.o88")), other: os.path.join(td, "BONANZA.O88")}
    cl = dict((f, clusters(p)) for f, p in o88s.items())
    res = {}
    for tag in tags:
        res[(tag, ship)] = launch_times(tag, None, None, None, ship.upper() + " (shipped)")
        res[(tag, other)] = launch_times(tag, img, src, None, other.upper())
    print("\nTHE PARTS' FORMAT A/B (SPEC.md 128.15.9), REPORTED:")
    for f in (ship, other):
        print("  %s parts: BONANZA.O88 %d bytes, bonanza360.img %s of %s clusters" % (
            f.upper(), os.path.getsize(o88s[f]), cl[f][0], cl[f][1]))
    for tag in tags:
        for name in FMT_COURSES:
            a_, b_ = res[(tag, ship)][name], res[(tag, other)][name]
            print("  %s %s's launch to its bracket: %s %.2f s (%d reads), %s %.2f s (%d reads): %s %+.2f s" % (
                tag.upper(), name.upper(), ship.upper(), a_[0], a_[1], other.upper(), b_[0], b_[1], ship.upper(),
                a_[0] - b_[0]), flush=True)
    return []


def phase_misses(tag, summ, ab_steps):
    """the A/B leg's misses: one on a frame that ran MORE physics steps than
    wave 3's same frame is the step clock's phase against the refresh (each
    build catches up on its own frames), not the engine's - REPORTED; every
    other miss fails it (SPEC.md 128.13.12).  With no A/B run (the registered
    row: the A/B is the final pass's by-hand run, 128.13.14 item 11) there is
    no same frame to compare, so a miss on a frame running MORE THAN ONE step
    is that phase's by the same rule, REPORTED, and a one-step miss still
    fails (the final pass of wave 3b: CGA frame 400 and the Hercules' frame
    953, two steps each, missed in one run and not in the next).  WAVE 6B
    (SPEC.md 128.17.6.7, 128.17.10): B's camera is LATTICE, so B's pans are
    no longer any earlier build's - "engine against engine" holds only on
    the frames that pan NOTHING.  A one-step miss on a frame that pans (a row
    or a column: the camera's choice of frame, B's series broken at 6b) is
    REPORTED as the camera's; a one-step miss on a frame with no strip still
    fails (the final pass of 6b: the CGA's B OFF, frames 1133 - 1149, a slow
    row pan over the end's occluded box, 9 misses at one row each).
    -> failures"""
    own, phase, cam = [], [], []
    pans = summ.get("pans") or []
    for m_ in summ["misses"]:
        i = m_[0] - 1
        s3 = summ["steps"][i]
        s2 = ab_steps[i] if ab_steps and i < len(ab_steps) else None
        if s3 > s2 if s2 is not None else not ab_steps and s3 > 1:
            phase.append((m_, s3, s2))
        elif i < len(pans) and pans[i]:
            cam.append((m_, s3, s2))
        else:
            own.append((m_, s3, s2))
    if cam:
        print("  the A/B leg's misses on frames that PAN (a row or a column), one step each - LATTICE's frames, "
              "REPORTED (SPEC.md 128.17.6.7: B's series breaks at 6b): %d (%s)" % (
                  len(cam), ", ".join("frame %d busy %d" % (m_[0], m_[1]) for m_, _s3, _s2 in cam[:12])),
              flush=True)
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
    print("  camera over TRIAL's flight (%d steps, replayed), the GROUND LINE's (SPEC.md 128.16.7): %s; wave 2's "
          "%s (CGA) - REPORTED" % (len(keys), "; ".join(
              "%s %d rows panned over %d bounces (%.1f a bounce)" % (k, v[0], v[1], v[0] / float(v[1] or 1))
              for k, v in res.items()), ", ".join("%s %d" % kv for kv in W2_TRIAL_ROWS.items())), flush=True)
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
    summ["pans"] = [bool(r["rows"] or r["column"]) for r in fr]
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
    tools = [t for t in ("tools/bonanza_assets.py", "tools/bbcourse.py", "tools/bbmusic.py",
                         "tools/os88lz.py")     # (5b's bbcourse imports os88lz for its course budget)
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
    if "BZ_DEMOPARTS" in mk:                    # wave 4's: a shipped demo a tour course, after the songs
        plist += ["BZD%d.BIN" % k for k in range(1, nc)]
    parts = []
    for p in plist:
        parts += ["--part", os.path.join(art, p)]
    # packed in the SHIPPED build's parts format (SPEC.md 128.15.9), never os88pkg's default
    subprocess.run([sys.executable, "tools/os88pkg.py", "--compress-if=lz4", binp, "-o", o88] + parts
                   + ["--part-compress", R.part_fmt()], cwd=R.ROOT, check=True, stdout=subprocess.DEVNULL)
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
        print("  %-14s %9s %9s %9s" % ("", "this", commit[:8], "delta"))
        for p in PARTS + ["busy", "period"]:
            a = n["parts"].get(p, 0) if p in PARTS else n[p]
            b = o["parts"].get(p, 0) if p in PARTS else o[p]
            print("  %-14s %9.0f %9.0f %+9.0f" % (p, a, b, a - b))
        print("  %-14s %8.1f%% %8.1f%%" % ("busy share", 100.0 * n["busy"] / n["refresh"],
                                            100.0 * o["busy"] / o["refresh"]))
        print("  %-14s %9d %9d" % ("misses", n["miss"], o["miss"]))
        d = n["busy"] - o["busy"]
        print("  BENCH's mean busy %+.0f clk against %s's (at most +%d ASSERTED on both cards, SPEC.md 128.14.17 "
              "item 7 and 128.15.13: the standing guard on the frame's cost; D ships, its 4-byte walk about "
              "+0.4k clk a pass frame over wave 4's, SPEC.md 128.15.5.4)" % (d, commit, AB_OVER))
        if d > AB_OVER and AB_ASSERT:
            bad.append("%s A/B: BENCH's mean busy %.0f clk against %s's %.0f, %+.0f - at most +%d asserted "
                       "(SPEC.md 128.14.17 item 7, 128.15.13)" % (tag, n["busy"], commit, o["busy"], d, AB_OVER))
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


# ---- WAVE 6 (SPEC.md 128.16.10, 128.16.14): the smoothness figures, the pans' prediction, the re-baseline ----
_PRED = {}


def pans_pred(demo, herc, w6=False):
    """the HOST'S PREDICTION of GLIDE's pans over DEMO on a card: `bbcourse.py
    --pans`'s figure (bbcourse.pans, SPEC.md 128.16.13; LATTICE since wave 6b,
    W6 wave 6's policy, `_w6`, beside it) -> (columns, rows, two-row frames,
    seconds of play)"""
    key = (bytes(demo), herc, w6)
    if key not in _PRED:
        _PRED[key] = BB.pans(R.course_k(BB.decode_log_t(demo)[0]), demo, herc, **({"_w6": True} if w6 else {}))
    return _PRED[key]


def smooth(fr, refresh):
    """the owner's smoothness rule's figures off each frame's flip (SPEC.md
    128.15.5.4): -> dict(missed refreshes, a second, misses, runs of two or more
    missed frames, the longest run, the seconds)"""
    meas = [r for r in fr if r["period"] is not None]
    held = [max(1, int(r["period"] / refresh + 0.5)) for r in meas]
    secs = sum(r["period"] for r in meas) / CLK
    missed = sum(h - 1 for h in held)
    runs, cur, longest = 0, 0, 0
    for h in held + [1]:
        if h > 1:
            cur += 1
            longest = max(longest, cur)
        else:
            runs += cur >= 2
            cur = 0
    return {"missed": missed, "per_s": missed / secs if secs else 0.0, "misses": sum(1 for h in held if h > 1),
            "runs2": runs, "longest": longest, "secs": secs}


def tube_split(fr, refresh):
    """wave 6b (SPEC.md 128.17.10): the frames IN A TUBE (bz_lexit's) against the
    run's other frames - (tube frames, of them missed, other frames, of them
    missed); a miss a frame held past 1.5 refreshes"""
    meas = [r for r in fr if r["period"] is not None and not r["full"]]
    tb = [r for r in meas if r.get("tube")]
    ot = [r for r in meas if not r.get("tube")]
    miss = lambda rs: sum(1 for r in rs if r["period"] > 1.5 * refresh)
    return len(tb), miss(tb), len(ot), miss(ot)


def intube_triggered(ts):
    """128.17.10's trigger for 128.17.6.8's in-tube rule on one run: at least
    two tube frames missed, and the share of tube frames that miss above the
    share of the run's other frames by MORE than one tube frame's worth - so
    that a single missed tube frame, phase noise on a run with a dozen tube
    frames, never ships a behaviour change on its own (the review's R5)"""
    nt, mt, no, mo = ts
    return mt >= 2 and ((mt - 1) / float(nt)) > (mo / float(no or 1))


def w6_line(lab, tag, fr, refresh, demo, kd, pred=True):
    """wave 6's REPORT for one demo's D (SPEC.md 128.16.10), with wave 6b's
    (128.17.10): two-row frames against --pans' (LATTICE's, and wave 6's
    policy's beside it), and the misses of frames in a tube against the
    run's other frames: -> its figures"""
    sm = smooth(fr, refresh)
    steps = sum(r["steps"] for r in fr)
    secs = steps / STEP_HZ if steps else 1.0
    cols = sum(1 for r in fr if r["column"])
    rows = sum(r["rows"] for r in fr if not r["full"])
    occ = [r["occ"] for r in fr if r.get("occ")]
    out = dict(sm, cols=cols, rows=rows, cols_s=cols / secs, rows_s=rows / secs,
               occ=(sum(occ) / len(occ)) if occ else 0.0, occ_frames=len(occ),
               ident=BB.log_ident(demo), steps=steps, crc=zlib.crc32(bytes(demo[16:])) & 0xFFFFFFFF)
    mode = ""
    if kd == R.CRS_K["mill"]:
        out["mode"] = "%d columns" % cols
        mode = ", MILL's camera panned %d columns (the host's prediction %d, bbcourse.py --pans)" % (
            cols, pans_pred(demo, tag == "herc")[0])
    pr = ""
    if pred:
        pc, prw, ptwo, psec = pans_pred(demo, tag == "herc")
        out["pred"] = (pc / psec, prw / psec, ptwo)
        pr = " (the host's prediction %.1f and %.1f, %d two-row frames)" % (pc / psec, prw / psec, ptwo)
    print("  %s, wave 6 (SPEC.md 128.16.10, REPORTED): missed refreshes %d = %.2f a second over %.1f s, misses %d, "
          "runs of two or more %d, the longest %d; GLIDE's columns %.1f and rows %.1f a second of play%s%s; the "
          "occluder pass %.0f clk a frame over %d frames; the log %04Xh, %d steps, CRC %08Xh" % (
              lab, sm["missed"], sm["per_s"], sm["secs"], sm["misses"], sm["runs2"], sm["longest"], out["cols_s"],
              out["rows_s"], pr, mode, out["occ"], len(occ), out["ident"], steps, out["crc"]), flush=True)
    # wave 6b (SPEC.md 128.17.10): two-row frames against --pans (LATTICE's, wave 6's policy's beside it), and
    # the misses of frames in a tube against the run's other frames (128.17.6.8's in-tube rule's trigger)
    out["two"] = sum(1 for r in fr if not r["full"] and r["rows"] >= 2)
    out["tube"] = tube_split(fr, refresh)
    nt, mt, no, mo = out["tube"]
    w6p = ""
    if pred:
        c6, r6, t6, s6 = pans_pred(demo, tag == "herc", w6=True)
        w6p = "; wave 6's policy on the host %.1f and %.1f a second, %d two-row frames" % (c6 / s6, r6 / s6, t6)
    print("  %s, wave 6b (SPEC.md 128.17.10, REPORTED): two-row frames %d%s%s; frames in a tube %d, %d missed "
          "(%.1f%%), the other frames %d, %d missed (%.1f%%)%s" % (
              lab, out["two"], " (the host's %d)" % out["pred"][2] if pred else "", w6p, nt, mt,
              100.0 * mt / (nt or 1), no, mo, 100.0 * mo / (no or 1),
              " - THE IN-TUBE RULE'S TRIGGER (128.17.6.8)" if intube_triggered(out["tube"]) else ""), flush=True)
    return out


def w6_ab_print(tag, res, ores):
    """this build's demos beside --ab's (5b's own demos, its own physics):
    REPORTED, never asserted - not like for like (SPEC.md 128.16.10)"""
    new = dict((lab, s) for lab, _, s in res if "w6" in s)
    old = dict((lab, s) for lab, _, s in ores if "w6" in s)
    if not old:
        return
    print("\n%s wave 6 against %s, every demo through D, speaker ON (REPORTED, not like for like: SPEC.md "
          "128.16.10):" % (tag.upper(), AB_COMMIT[:8]))
    print("  %-14s %18s %18s %14s %14s %14s" % ("", "missed/s", "runs >= 2", "longest", "cols/s", "occ clk"))
    for lab in sorted(set(new) | set(old)):
        a, b = (new.get(lab) or {}).get("w6"), (old.get(lab) or {}).get("w6")

        def f(x, k, fmt):
            return fmt % x[k] if x else "-"
        print("  %-14s %8s / %-8s %8s / %-8s %6s / %-6s %6s / %-6s %6s / %-6s" % (
            lab, f(a, "per_s", "%.2f"), f(b, "per_s", "%.2f"), f(a, "runs2", "%d"), f(b, "runs2", "%d"),
            f(a, "longest", "%d"), f(b, "longest", "%d"), f(a, "cols_s", "%.1f"), f(b, "cols_s", "%.1f"),
            f(a, "occ", "%.0f"), f(b, "occ", "%.0f")))


# ---- WAVE 6B (SPEC.md 128.17.10, story 6b.7): FIRST's falls, and the like-for-like A/B the decision rides on ----
FALL_STEPS = 1100              # FIRST's autopilot steps the host lists falls over (B's 1,200 frames run ~1,090)
LAT_AB = "4d69985c49ead0f387858d7e8411aec102a964c9"   # wave 6's commit (the shipped GLIDE), the A/B's other side
LAT_AB_RUNS = 3                # runs a side (6b.7: "no worse than 4d69985c's beyond the spread of its three")


def fall_log(steps=None):
    """FIRST's autopilot (a loop of falls and respawns, 128.17.6.6) as the
    BENCHMARK runs it (B with bz_crs poked: the guest's autopilot, the
    model's play=False, where the GOAL ends nothing - a replay through R
    ends at the goal, and FIRST's autopilot crosses its goal on the way to
    its first fall at step 154): the model's (take-off step, respawn step)
    for every fall over STEPS steps.  -> ([(take-off, respawn)], steps)"""
    c = R.course("first")
    p = BB.Physics(c, play=False, mat=c.ball)
    n = steps or FALL_STEPS
    for _ in range(n):
        p.step_auto()
    tk = [e[1] for e in p.events if e[0] == "takeoff"]
    falls = [(max([s for s in tk if s < r] or [0]), r) for r in [e[1] for e in p.events if e[0] == "respawn"]]
    return falls, n


def fall_leg(g, tag):
    """THE FALL REPLAY (SPEC.md 128.17.6.6 risk 8, 128.17.10): FIRST's
    autopilot - a loop of falls and respawns - run as the benchmark (B with
    bz_crs poked to FIRST, BENCH frames, speaker ON; the guest's B is the
    model's play=False, so the goal it crosses ends nothing): each fall that
    the run reaches - from its take-off to the next fall's take-off (the
    last: the run's end) - its misses, missed refreshes and runs of two or
    more, REPORTED.  The frames' step counts are the guest's own, so the
    windows are the model's steps.  -> (failures, summary)"""
    falls, _n = fall_log()
    set_snd(g, True)
    fr, _pkg, refresh, _np = measure(g, crs=R.CRS_K["first"], pokes={"bz_hvoff": 0})
    lab = "%s FIRST's falls through B (FIRST's autopilot, sound ON)" % tag
    n = fr[-1]["n"] if fr else 0
    falls = [(a, r_) for a, r_ in falls if r_ < n]
    out = {"falls": []}
    ends = [a for a, _r in falls[1:]] + [n + 1]
    for (a, r_), b in zip(falls, ends):
        win = [f for f in fr if a <= f["n"] < b]
        sm = smooth(win, refresh) if win else None
        out["falls"].append((a, r_, len(win), sm, sum(1 for f in win if not f["full"] and f["rows"] >= 2)))
    print("\n%s (SPEC.md 128.17.10, REPORTED): %d falls over %d steps; per fall (take-off step, respawn step): %s" % (
        lab, len(falls), n, "; ".join(
            "%d - %d: %d frames, misses %d, missed refreshes %d, runs of two or more %d, the longest %d, two-row "
            "frames %d" % (a, r_, nw, sm["misses"], sm["missed"], sm["runs2"], sm["longest"], two)
            if sm else "%d - %d: no frame" % (a, r_) for a, r_, nw, sm, two in out["falls"])), flush=True)
    allw = [f for f in fr if falls and f["n"] >= falls[0][0]]
    if allw:
        sm = smooth(allw, refresh)
        print("  %s over every fall: %d frames, misses %d, missed refreshes %d (%.2f a second), runs of two or more "
              "%d, the longest %d" % (tag.upper(), len(allw), sm["misses"], sm["missed"], sm["per_s"], sm["runs2"],
                                      sm["longest"]), flush=True)
    return [], out


def mill_runs(tag, apps, src, art, label, runs=LAT_AB_RUNS):
    """MILL's route demo through D and B, LAT_AB_RUNS times each, speaker ON, on
    one build: -> {"D": [smooth figures], "B": [...], "keys": the demo's key bytes}"""
    sym = R.symbols(src, art)
    out = {"D": [], "B": [], "two": []}
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps, machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym)
        ui.settle()
        kd = R.CRS_K["mill"]
        for i in range(runs):
            demo = load_demo(g, kd, art)
            set_snd(g, True)
            fr, _pkg, refresh, _n = measure(g, key="KeyD", frames_cap=DEMO_CAP)
            out["D"].append(smooth(fr, refresh))
            out["two"].append(sum(1 for r in fr if not r["full"] and r["rows"] >= 2))
            out["keys"] = [k for k, _t in BB.decode_log_t(demo)[2]]
        for i in range(runs):
            set_snd(g, True)
            fr, _pkg, refresh, _n = measure(g, pokes={"bz_hvoff": 0})
            out["B"].append(smooth(fr, refresh))
    for what in ("D", "B"):
        print("  %s %s, %s (sound ON): %s" % (tag.upper(), label, "MILL's route demo through D" if what == "D" else
                                                "B, BENCH's benchmark", "; ".join(
            "missed/s %.2f, misses %d, runs >= 2 %d, the longest %d" % (s["per_s"], s["misses"], s["runs2"],
                                                                        s["longest"]) for s in out[what])),
              flush=True)
    return out


def lattice_ab(tags, commit=LAT_AB):
    """THE LIKE-FOR-LIKE A/B and the decision it carries (SPEC.md 128.17.10,
    story 6b.7): MILL's route demo - its keys hold neither Space nor Grip, so
    its path is the same in COMMIT (wave 6's GLIDE) and here (LATTICE); the
    leg ASSERTS the two logs' key bytes carry no Space or Grip bit and are the
    same - through D, LAT_AB_RUNS runs a side, speaker ON, both cards; B
    beside it REPORTED only (its route pans a third of wave 6's work, 128.17.6.7:
    B's series breaks at 6b).  THE DECISION, computed and printed: LATTICE
    ships on round 2's disk if on BOTH cards this build's missed refreshes a
    second and longest run of misses (each its runs' mean) are no worse than
    COMMIT's beyond the spread of its runs (at most their maximum); otherwise
    the figures go to the owner with the disk held.  -> failures"""
    bad = []
    skip = fetch(commit)
    if skip:
        print("bonanza_perf: SKIP the LATTICE A/B: %s" % skip, flush=True)
        return None
    td = tempfile.mkdtemp(prefix="bz6b")
    verdict = {}
    try:
        old = ab_tree(td, commit)
        for tag in tags:
            print("\n%s THE LATTICE A/B (SPEC.md 128.17.10, story 6b.7): MILL's route demo, %s against this build, "
                  "%d runs a side, speaker ON" % (tag.upper(), commit[:8], LAT_AB_RUNS), flush=True)
            o = mill_runs(tag, *old, label=commit[:8])
            n = mill_runs(tag, R.at("build/bonanza360.img"), None, None, label="this build (LATTICE)")
            for side, s in ((commit[:8], o), ("this build", n)):
                held = [k for k in s["keys"] if k & (BB.K_HOP | BB.K_GRIP)]
                if held:
                    bad.append("%s LATTICE A/B: %s's MILL demo holds Space or Grip on %d steps - not like for like "
                               "(SPEC.md 128.17.10)" % (tag, side, len(held)))
            if o["keys"] != n["keys"]:
                bad.append("%s LATTICE A/B: the two builds' MILL demos are not the same key bytes (%d and %d steps)"
                           % (tag, len(o["keys"]), len(n["keys"])))
            ok = True
            for k, what in (("per_s", "missed refreshes a second"), ("longest", "the longest run of misses")):
                om, nm = [s[k] for s in o["D"]], [s[k] for s in n["D"]]
                mean = sum(nm) / float(len(nm))
                good = mean <= max(om)
                ok = ok and good
                print("  %s %s: this build %s (mean %.2f) against %s %s (spread %.2f - %.2f): %s" % (
                    tag.upper(), what, ["%.2f" % x for x in nm], mean, commit[:8], ["%.2f" % x for x in om],
                    min(om), max(om), "no worse" if good else "WORSE beyond the spread"), flush=True)
            print("  %s two-row frames a run: this build %s, %s %s; B (REPORTED, its series breaks at 6b): missed/s "
                  "this build %s, %s %s" % (tag.upper(), n["two"], commit[:8], o["two"],
                                            ["%.2f" % s["per_s"] for s in n["B"]], commit[:8],
                                            ["%.2f" % s["per_s"] for s in o["B"]]), flush=True)
            verdict[tag] = ok
    finally:
        shutil.rmtree(td, ignore_errors=True)
    ships = all(verdict.get(t, False) for t in tags) and not bad
    print("\nTHE DECISION (story 6b.7, SPEC.md 128.17.10): %s" % (
        "LATTICE SHIPS on round 2's disk - MILL's misses a second and longest run no worse than %s's beyond its "
        "spread on %s" % (commit[:8], " and ".join(t.upper() for t in tags)) if ships else
        "HOLD THE DISK - the figures above go to the owner (%s)" % ", ".join(
            "%s %s" % (t.upper(), "no worse" if verdict.get(t) else "WORSE") for t in tags)), flush=True)
    return bad


BASE_RUNS = {"mill": 6, "peak": 6}         # the re-baseline's runs a configuration (128.16.10); 3 for the rest
BASE_DEFAULT = 3


def baseline(tags):
    """THE RE-BASELINE (SPEC.md 128.16.10), at the FREEZE commit only: every
    shipped demo through D and B, both cards, speaker OFF and ON, each figure
    with its spread, keyed to its log; written to a new dated report.  -> its path"""
    import datetime
    rows = []
    R.CRS_K["bench"]
    names = {v: n for n, v in dict.items(R.CRS_K)}
    for tag in tags:
        sym = R.symbols()
        for snd in SOUNDS:
            with os88ui.boot(R.at("build/os8088-360.img"), apps=R.at("build/bonanza360.img"),
                             machine=R.MACHINE[tag]) as ui:
                ui.open_drive("B")
                ui.open("BONANZA.O88")
                g = R.Bz(ui, tag, sym)
                ui.settle()
                set_snd(g, snd == "on")
                for kd in [None] + list(range(1, len(R.CRS_K))):
                    name = "bench" if kd is None else names[kd]
                    n = BASE_RUNS.get(name, BASE_DEFAULT)
                    runs, key = [], None
                    for _ in range(n):
                        if kd is None:
                            fr, pkg, refresh, _np = measure(g, pokes={"bz_hvoff": 0})
                            key = "B (BENCH's benchmark)"
                        else:
                            demo = load_demo(g, kd)
                            fr, pkg, refresh, _np = measure(g, key="KeyD", frames_cap=DEMO_CAP)
                            key = "BZD%d %04Xh %d steps CRC %08Xh" % (
                                kd, BB.log_ident(demo), BB.decode_log_t(demo)[2].__len__(),
                                zlib.crc32(bytes(demo[16:])) & 0xFFFFFFFF)
                        meas = [r for r in fr if not r["full"] and "busy" in r and r["period"] is not None]
                        sm = smooth(fr, refresh)
                        cols = sum(1 for r in fr if r["column"])
                        runs.append({"busy": stats([r["busy"] for r in meas])["mean"], "misses": sm["misses"],
                                     "per_s": sm["per_s"], "runs2": sm["runs2"], "longest": sm["longest"],
                                     "mode": "%d" % cols if name == "mill" else ""})
                    rows.append((tag, snd, name, key, runs))
                    print("  baseline %s %s %s: %d runs, missed/s %s" % (tag, snd, name, n, ", ".join(
                        "%.2f" % r["per_s"] for r in runs)), flush=True)
                set_snd(g, True)
    day = datetime.date.today().isoformat()
    path = os.path.join(R.ROOT, "docs", "reports", "BONANZA-BASELINE-%s.md" % day)
    head = git("rev-parse", "--short", "HEAD").stdout.strip()
    with open(path, "w") as f:
        f.write("# BONANZA's re-baseline, %s (SPEC.md 128.16.10)\n\nA MEASUREMENT of one tree: commit %s, by "
                "`python3 tests/bonanza_perf.py --baseline` on MartyPC's 5150s.  Every figure is each "
                "configuration's runs' min - max (mean).  Each row is keyed to its demo's log; a later figure "
                "is compared only with the row of the same log.\n\n" % (day, head))
        f.write("| card | speaker | demo | the log | runs | mean busy clk | misses | missed refreshes a second "
                "| runs of 2+ | longest run | MILL's columns |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
        for tag, snd, name, key, runs in rows:
            def sp(k, fmt):
                v = [r[k] for r in runs]
                return (fmt + " - " + fmt + " (" + fmt + ")") % (min(v), max(v), sum(v) / len(v))
            f.write("| %s | %s | %s | %s | %d | %s | %s | %s | %s | %s | %s |\n" % (
                tag.upper(), snd.upper(), name.upper(), key, len(runs), sp("busy", "%.0f"), sp("misses", "%.1f"),
                sp("per_s", "%.2f"), sp("runs2", "%.1f"), sp("longest", "%.1f"),
                ", ".join(r["mode"] for r in runs) if name == "mill" else "-"))
    print("bonanza_perf --baseline: %d configurations, %d runs, written to %s" % (
        len(rows), sum(len(r[4]) for r in rows), os.path.relpath(path, R.ROOT)), flush=True)
    return path


REDS = {
    # (`halfcal`, the calibration's word-line halved, RETIRED here in wave 6b's final pass: under LATTICE
    # MILL's benchmark frames leave every halved commit inside its deadline on the CGA - bz_wover 0, 40
    # commits - so this row's bz_wover check no longer sees it; the same broken copy goes red at
    # bonanza_wheel's (5), its cost check, SPEC.md 128.17.14)
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
}
# each arm's legs and sound: the ones its check is asserted in
RED_LEGS = {"rideoff": (("ride",), ("off",)), "level1": (("trial",), ("off",))}
RED_TAGS = {"rideoff": ("cga",)}
RED_WANT = {"rideoff": "line-change frames", "level1": "bz_nhvy"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--apps", help="the B: floppy to run instead of build/bonanza360.img")
    ap.add_argument("--src", help="the package source that floppy was built from (default apps/bonanza)")
    ap.add_argument("--art", help="the art directory that source assembled against (default build/bonanza-art)")
    ap.add_argument("--ab", nargs="?", const=AB_COMMIT, metavar="COMMIT",
                    help="also measure COMMIT's package (default %s, wave 5b's anchor: 5a's package) built with "
                         "its own art" % AB_COMMIT)
    ap.add_argument("--fmt-ab", action="store_true",
                    help="wave 5b's parts' format A/B (SPEC.md 128.15.9): the other format in a private tree, the "
                         "clusters and PEAK's and MOON's launch to the bracket REPORTED")
    ap.add_argument("--no-trial", action="store_true", help="no TRIAL leg, no camera")
    ap.add_argument("--leg", choices=LEGS, action="append", help="only these legs (default all)")
    ap.add_argument("--sound", choices=SOUNDS, action="append", help="only these sounds (default off and on)")
    ap.add_argument("--no-adlib", action="store_true", help="no AdLib arm (the CGA's MILL and ride on %s)" % ADLIB)
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only: every red arm assembles")
    ap.add_argument("--lattice-ab", nargs="?", const=LAT_AB, metavar="COMMIT",
                    help="wave 6b's like-for-like A/B (SPEC.md 128.17.10, story 6b.7): MILL's route demo through D, "
                         "%d runs a side against COMMIT (default wave 6's, %s), B beside it, and THE DECISION "
                         "printed; exits %d when COMMIT is not in this clone" % (LAT_AB_RUNS, LAT_AB[:8], SKIP_RC))
    ap.add_argument("--baseline", action="store_true",
                    help="THE RE-BASELINE (SPEC.md 128.16.10), at the FREEZE commit only: every demo through D and "
                         "B, both cards, speaker OFF and ON, its runs' spreads written to a new dated report")
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.check:
        for line in R.check_reds(REDS, "bonanza_perf"):
            print(line)
        R.CRS_K["bench"]                        # wave 6: the pans' prediction for every shipped demo, both cards
        for kd in range(1, len(R.CRS_K)):
            demo = open(os.path.join(R.ROOT, R.at("build/bonanza-art"), "BZD%d.BIN" % kd), "rb").read()
            held = [k for k, _t in BB.decode_log_t(demo)[2] if k & (BB.K_HOP | BB.K_GRIP)]
            for herc in (0, 1):
                c, rw, two, sec = pans_pred(demo, herc)
                c6, r6, t6, s6 = pans_pred(demo, herc, w6=True)
                print("bonanza_perf the host's prediction, BZD%d on the %s: LATTICE %.1f columns and %.1f rows a "
                      "second of play (%d and %d over %.1f s), %d two-row frames; wave 6's policy %.1f and %.1f, %d "
                      "two-row frames%s" % (
                          kd, ("CGA", "Hercules")[herc], c / sec, rw / sec, c, rw, sec, two, c6 / s6, r6 / s6, t6,
                          "; its keys hold Space or Grip on %d steps" % len(held) if held else
                          "; its keys hold neither Space nor Grip (like for like across a physics change)"))
        falls, n = fall_log()                  # wave 6b: the fall leg's falls, and the A/B's commit
        print("bonanza_perf the fall leg: FIRST's autopilot as B runs it, %d falls (take-off, respawn) in %d steps: %s"
              % (len(falls), n, falls))
        assert len(falls) >= 4, "FIRST's autopilot falls %d times in %d steps: the fall leg needs a loop" % (
            len(falls), n)
        print("bonanza_perf --lattice-ab's commit %s: %s" % (LAT_AB[:8], fetch(LAT_AB) or "in this clone"))
        return
    if a.baseline:
        baseline(tags)
        return
    if a.lattice_ab:
        bad = lattice_ab(tags, a.lattice_ab)
        if bad is None:
            sys.exit(SKIP_RC)
        for b in bad:
            print("FAIL %s" % b)
        assert not bad, "%d failure(s)" % len(bad)
        print("\nbonanza_perf --lattice-ab (%s): the A/B measured, the decision printed" % ", ".join(tags))
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
    if a.fmt_ab and not a.leg:                  # (5b's A/B alone: this build's legs only as --ab needs them)
        legs = ("bench", "mill") if a.ab else ()
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
        for tag in tags if legs else ():
            ores = None
            if ab:                                  # wave 3 first: its frames' step counts judge the A/B's misses
                ores = run(tag, *ab, trial=False, legs=tuple(x for x in legs if x in ("bench", "mill", "demo")),
                           old=True)
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
                w6_ab_print(tag, res, ores)
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
    for flag, fn in ((a.fmt_ab, fmt_ab),):
        if flag:
            with tempfile.TemporaryDirectory(prefix="bz5b") as td5:
                bad = fn(tags, td5)
            for b in bad:
                print("FAIL %s" % b)
            allbad += bad
    assert not allbad, "%d failure(s)" % len(allbad)
    if skip:
        print("\nbonanza_perf (%s): this build measured; the A/B leg SKIPPED: %s" % (", ".join(tags), skip))
        sys.exit(SKIP_RC)
    print("\nbonanza_perf (%s%s%s): PASS" % (", ".join(tags), ", A/B against %s" % a.ab if a.ab else "",
                                           ", the format A/B reported" if a.fmt_ab else ""))


if __name__ == "__main__":
    main()
