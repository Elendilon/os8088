#!/usr/bin/env python3
"""BONANZA's sound, held to tools/bbmusic.py's model on the guest (SPEC.md 128.20).

    make bonanzadisk && python3 tests/bonanza_sound.py [--leg spk|fm|both]
    python3 tests/bonanza_sound.py --red groove|mat      (a red arm, below)
    python3 tests/bonanza_sound.py --check               (the host half)

The package plays a song with ITS sequencer (apps/bonanza/bzsound.inc) and the
tool renders the same packed bytes with ITS copy of it (bbmusic.Seq).  This row
stops the guest where a step has just been sounded (bzs_tp, the end of
bzs_run) and holds its whole state to the model stepped as many sub-ticks
(bzs_nsub): every voice's key, note, gate, instrument, volume, macro place,
age and PITCH WORD, and the song's order row, row, groove step and sub-ticks
left - and on the speaker the Hz it last sent against the model's fold.

LEG spk, os8088_5150_cga_gla (no card, the owner's 5150 #1):
  1  THE WINDOW IS SILENT (SPEC.md 128.26.5): no arm, no song held;
  2  S (the harness's key, bz_dev) toggles OFF and AUTO, the window silent
     either way;
  3  F plays FIRST: course 1's song (song 0 since 128.26.5, the part row after
     the sound part's) in the bracket, three stops held to the model;
  4  THE EVENTS, poked into the counters the physics keeps (SPEC.md 128.20.5)
     at a stop, each ball in turn (bz_mat): a bounce, a wall, a bumper's face -
     the next frame's slot holds that ball's effect (its instrument, priority
     and transpose), and the three balls' effects are not the same;
  5  the cost: every frame's sound (bzs_frame to .fend) in guest cycles over
     120 frames of play;
  6  Esc: the song given back, the window silent again.
LEG fm, os8088_5150_sb (the same 5150 with an AdLib, SOUND.DRV loaded at
boot): 1 and 3 on the ADLIB arm (two effect slots), 5 priced there, the OPL's
own capture loud in play, and Esc and the window's close giving the chip back
(SOUND.DRV's opl_xown).

--red NAME builds a broken package in a temporary directory and PASSES only if
the row FAILS at its own check:
  groove   every row the groove's FIRST count: FIRST's 8 6 swing played
           straight - the bracket's model comparison fails
  mat      every event played as the rubber ball's: the events check fails
  noboost  wave 6: bz_nboost left out of bzs_ctab (its slot names bz_ntube
           again): the boost check's rubber poke keys no effect
  nofree   wave 8R round 2: an effect's 0 terminator read, its slot not
           freed (F_PTR kept): the wait for an idle slot fails, naming it

WAVE 6 (SPEC.md 128.16.4.4, 128.16.14): step 4 gains THE BOOST: bz_nboost
poked with each ball - rubber's next frame's slot holds rubber's BOOST effect,
whose record differs from its HOP's (another effect, by content); steel's and
glass's key NOTHING (bzs_fxseq unchanged: their columns name no effect); and
a boost contact keys no LAND (bz_nland, bz_lvz past BZS_LMIN and bz_nboost
poked in one frame: one effect keyed, the BOOST).  The effect numbers are read
out of the built BZSND.BIN, never written here.

WAVE 8R ROUND 2 (SPEC.md 128.20.5, 128.18.6): THE COURSE'S CLOCK HELD.  FIRST has
a 15 s limit and its countdown ran under step 4: its LOW at 10 s and a TICK
every second after are the game's own, and one keyed in a poked frame was a
second effect ('rubber's boost keyed 2'), while w7's pokes left bz_t55 stale,
so the poked 10 s could run out a step later under its own LOW (priority 4)
and the game's TICK at 9 (priority 1) found the slot taken - the test's 9 then
moved nothing.  The longer effects of 128.22.9's `strip_comment` fix widened
both windows (LOW 4 sub-ticks -> 13).  So step 4 runs with the limit off
(bz_tsec 0), w7 pokes each second AT ITS START (bz_t55 = BZ_SECSTEPS, the
countdown's own state there) and fails if the clock still moved, and every
wait for an idle slot FAILS when an effect never frees it.

WAVE 5B (SPEC.md 128.15.9, 128.15.13): unchanged in logic.  The parts table's
format byte is the whole table's, so with LZB parts (shipped) the sound part and the
songs are LZB parts like the courses: the title's fetch on the desktop and
course 1's song in the bracket are decoded by OSAPI_DECOMP's LZB arm, and the
model comparison holds the decoded bytes to bbmusic's.  The format is printed
at the start; a red tree packs its parts in it (bonanza_ring.build_tree).
"""
import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import bbmusic as BM           # noqa: E402
import bonanza_ring as R       # noqa: E402

MACHINE = {"spk": "os8088_5150_cga_gla", "fm": "os8088_5150_sb"}
MHZ = 4.77273
V_SIZE, F_SIZE = 26, 22                 # bzsound.inc's records
A_NONE, A_SPK, A_FM = 0, 1, 2
FILES = ("bonanza.asm", "bzvideo.inc", "bzgame.inc", "bzwheel.inc", "bzphys.inc", "bzsound.inc")
EXTRA = ("bzs_frame.fend",)
EV = {e: i for i, e in enumerate(BM.EVENTS)}


def symbols(src=None, art=None):
    """bz_/bzs_ labels and VARs, by assembling a `dw` table onto the package"""
    d = src or os.path.join(ROOT, "apps", "bonanza")
    art = art or R.at("build/bonanza-art")
    names = []
    for f in FILES:
        t = open(os.path.join(d, f)).read()
        names += re.findall(r"^VAR (bzs?_\w+),", t, re.M)
        names += re.findall(r"^(bzs?_\w+):", t, re.M)
    names = sorted(set(names)) + list(EXTRA)
    with tempfile.TemporaryDirectory() as td:
        p, b = os.path.join(td, "probe.asm"), os.path.join(td, "probe.bin")
        for _try in range(2):                   # (a VAR only an experiment's knob defines - the speed pass's
            open(p, "w").write(open(os.path.join(d, "bonanza.asm")).read() + "\n" +    # BZS_SKIPTEST, off -
                               "\n".join("dw " + n for n in names))                    # is left out, named)
            r = subprocess.run(["nasm", "-f", "bin", "-I", os.path.join(ROOT, "apps") + "/", "-I", d + "/",
                                "-I", art + "/", "-o", b, p], cwd=ROOT, capture_output=True, text=True)
            if r.returncode == 0:
                break
            undef = set(re.findall(r"symbol `(\w+)' not defined", r.stderr))
            if not undef or _try:
                raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)
            names = [n for n in names if n not in undef]
        raw = open(b, "rb").read()
    return dict(zip(names, struct.unpack("<%dH" % len(names), raw[-2 * len(names):])))


def parts(art=None):
    art = art or R.at("build/bonanza-art")
    snd = open(os.path.join(art, "BZSND.BIN"), "rb").read()
    songs = [open(os.path.join(art, "BZM%d.BIN" % i), "rb").read() for i in range(len(BM.SONGS))]
    inc = open(os.path.join(art, "bzcourse.inc")).read()
    ncrs = int(re.search(r"^BZ_NCRS\s+equ\s+(\d+)", inc, re.M).group(1))
    pcrs = int(re.search(r"^BZ_P_CRS\s+equ\s+(\d+)", inc, re.M).group(1))   # (0 since SPEC.md 128.25.5.2: the
                                                                                # balls ride the bundle; 3 before)
    n2 = re.search(r"^BZ_NCRS2\s+equ\s+(\d+)", inc, re.M)  # SPEC.md 128.30.4.4: the two-part courses' WORLD
    ncrs2 = int(n2.group(1)) if n2 else 0                    # rows come between the courses' and the sound's
    return snd, songs, pcrs + ncrs + ncrs2      # ... and BZ_P_SND's row


def stop(g, label="bzs_tp", guest=10):
    """run to the next LABEL and stay there"""
    m = g.m
    m.breakpoints([{"type": "exec", "addr": g.a(label)}])
    m.run()
    if not m.wait_stop(guest):
        raise AssertionError("the guest never reached %s" % label)
    m.breakpoints([])


IDLE_FRAMES = 400


def idle(g, what):
    """stop frame by frame until the effect slot is idle (F_PTR 0: the effect
    read its 0 terminator) -> [] or a failure naming an effect that never ends"""
    for _ in range(IDLE_FRAMES):
        stop(g)
        if g.w("bzs_fx") == 0:
            return []
    return ["%s: the effect slot never went idle in %d frames (F_PTR %04X, instrument %d): an effect that "
            "never frees its slot" % (what, IDLE_FRAMES, g.w("bzs_fx"), g.m.read(g.a("bzs_fx") + 13, 1)[0])]


def sec_steps(art=None):
    """BZ_SECSTEPS, the clock's second in steps, out of the built include"""
    t = open(os.path.join(art or R.at("build/bonanza-art"), "bzcourse.inc")).read()
    return int(re.search(r"^BZ_SECSTEPS\s+equ\s+(\d+)", t, re.M).group(1))


def set_clock(g, secs):
    """THE CLOCK POKED AT A SECOND'S START (bzphys.inc .counted): bz_tsec and
    bz_t55 = BZ_SECSTEPS, as the countdown leaves them the step a second
    changes - so the course's own clock cannot move bz_tsec again for a second
    (a stale bz_t55 let it end the poked second a step later: the 10 s LOW
    poke's own second ran out under the LOW, priority 4, whose slot the
    game's TICK at 9, priority 1, could not take - and the test's 9 then
    moved nothing)"""
    g.put("bz_tsec", secs)
    g.putb("bz_t55", g.secsteps)


def clock_off(g):
    """the course's LIMIT stopped for the contact checks (bz_tsec 0: no limit):
    FIRST's 15 s run under them - its LOW at 10 s and a TICK every second
    after are the game's, and one keyed in a poke's frame is a second effect
    beside the poked one (rubber's boost 'keyed 2 effect(s)').  One frame
    takes the copy (bz_tsec 0 and no bz_tout: nothing keyed)"""
    g.put("bz_tsec", 0)
    stop(g)


def voices(g):
    """the guest's voices, its stamps turned into the model's gate and age
    (bzsound.inc's record: a note is when it was keyed and when it goes up)"""
    raw = g.m.read(g.a("bzs_v"), 8 * V_SIZE)
    now = g.w("bzs_nsub")
    out = []
    for i in range(8):
        r = raw[i * V_SIZE:(i + 1) * V_SIZE]
        w = lambda o: r[o] | (r[o + 1] << 8)
        t0, end = w(6), w(8)
        on = r[0]
        out.append({"on": on, "note": r[2], "inst": r[3], "vol": r[4], "mpos": r[5],
                    "gate": (end - now) & 0xFFFF, "pitch": w(10),
                    "age": min(255, ((now - t0 + 1) if on else (now - end)) & 0xFFFF),
                    "h_tl": r[14], "h_a0": r[15], "h_b0": r[16], "h_inst": r[17]})
    return out


def held(g, snd, song, arm, what):
    """the guest's song state against the model's at bzs_nsub sub-ticks"""
    fails = []
    n = g.w("bzs_nsub")
    q = BM.Seq(snd, song, "spk" if arm == A_SPK else "fm")
    for _ in range(n):
        q.step()
    gv = voices(g)
    for i in range(6):
        mv = q.v[i]
        want = {"on": mv.on, "age": mv.age}
        if mv.on:
            want.update(note=mv.note, gate=mv.gate, inst=mv.inst, vol=mv.vol)
            if arm == A_FM or i not in (2, 3, 4):     # (the speaker works out no chord pitch)
                want.update(mpos=mv.mpos, pitch=mv.pitch)
        got = {k: gv[i][k] for k in want}
        if got != want:
            fails.append("%s, %d sub-ticks: voice %d is %s, the model's %s" % (what, n, i, got, want))
    for name, mval in (("bzs_ord", q.ord), ("bzs_row", q.row), ("bzs_gi", q.gi), ("bzs_rtick", q.rtick)):
        if g.b(name) != mval:
            fails.append("%s, %d sub-ticks: %s %d, the model's %d" % (what, n, name, g.b(name), mval))
    if arm == A_FM and g.b("bzs_dirty") == 0 and g.w("bzs_fx") == 0:
        # the chip caught up: its shadows ARE the model's wanted registers
        for i in range(6):
            on, a0, b0, tl, pid, _ = q.fm_want(i)
            h = gv[q.fm_chan(i)]                  # (the shadows are a CHANNEL's)
            if on:
                got, want = (h["h_a0"], h["h_b0"], h["h_tl"], h["h_inst"]), (a0, b0, tl, pid)
            else:
                got, want = h["h_b0"] & 0x20, 0
            if got != want:
                fails.append("%s, %d sub-ticks: the chip's voice %d holds %s, the model wants %s"
                             % (what, n, i, got, want))
    if arm == A_SPK and g.w("bzs_fx") == 0:      # the fold, with no effect running
        p, _, _ = q.spk_choice()
        hz = BM.pitch_hz(p) if p else 0
        if g.w("bzs_shz") != hz:
            fails.append("%s, %d sub-ticks: the speaker sent %d Hz, the model's fold %d"
                         % (what, n, g.w("bzs_shz"), hz))
    return fails, n


def events(g, snd):
    """SPEC.md 128.20.5: each ball's bounce, wall and bumper face, poked"""
    fails, seen = [], {}
    emap, fxt = BM.u16(snd, 12), BM.u16(snd, 10)
    pokes = (("BOUNCE", "bz_nbnc", {"bz_lvz": 300}), ("WALL", "bz_nwall", {"bz_lwv": 100, "bz_lwb": 0}),
             ("BUMPER", "bz_nwall", {"bz_lwv": 100, "bz_lwb": 1}))
    for mat in range(3):
        for ev, ctr, extra in pokes:
            fails += idle(g, "events")          # the slot idle first (play makes its own)
            g.putb("bz_mat", mat)
            for k, v in extra.items():
                (g.putb if k == "bz_lwb" else g.put)(k, v)
            g.put(ctr, g.w(ctr) + 1)
            seq0 = g.w("bzs_fxseq")
            stop(g)
            n = snd[emap + mat * len(BM.EVENTS) + EV[ev]]
            rec = BM.u16(snd, fxt + 2 * n)
            strength = extra.get("bz_lvz", extra.get("bz_lwv", 0))
            sens = snd[rec + 2]
            tr = 0 if sens >= 16 else min(7, strength >> sens)
            base = g.a("bzs_fx")
            slots = [g.m.read(base, F_SIZE)]          # one effect slot (128.20.5)
            hit = [s for s in slots if s[13] == snd[rec] and s[12] == snd[rec + 1] and s[10] == tr
                   and struct.unpack("<H", s[17:19])[0] == (seq0 + 1) & 0xFFFF]
            if g.w("bzs_fxseq") != (seq0 + 1) & 0xFFFF or not hit:
                fails.append("events: %s's %s left no slot holding effect %d (instrument %d, priority %d, "
                             "transpose %d)" % (BM.MATS[mat], ev, n, snd[rec], snd[rec + 1], tr))
            seen[(mat, ev)] = n
    for ev in ("BOUNCE", "WALL", "BUMPER"):
        if len({seen.get((m, ev)) for m in range(3)}) != 3:
            fails.append("events: the three balls' %s are not three effects" % ev)
    g.putb("bz_mat", 0)
    return fails


def w7_events(g, snd):
    """wave 7 (SPEC.md 128.18.6): wave 4's counters mapped - a flag, a pad, a
    lip-out, a spring, a RETURN - and the sound plan's I9 (a kick, a knock, a
    tube), each poked with the rubber ball: the next frame's slot holds the
    event's effect; and the clock's seconds poked (bz_tsec): 30 s left plays
    LOW, 9 s a TICK, and 0 with bz_tout a TIMEOUT (poked at bzs_frame's
    entry, after the frame's goal test, as a real timeout's step is)"""
    fails = []
    emap, fxt = BM.u16(snd, 12), BM.u16(snd, 10)
    ne = len(BM.EVENTS)

    def idle_w7():
        """True when the slot is idle; a slot that never frees ends the clock's
        checks (400 frames outrun a pinned second: the course would time out)"""
        f = idle(g, "w7")
        fails.extend(f)
        return not f

    def held_at(secs):
        """the poked second still the guest's (the course's clock did not move it)"""
        if g.w("bz_tsec") != secs:
            fails.append("w7: the clock poked to %d s reads %d s a frame on: the course's countdown moved it "
                         "under the check" % (secs, g.w("bz_tsec")))

    def check(ev, what, seq0):
        n = snd[emap + 0 * ne + EV[ev]]
        if n == 0xFF:
            return ["w7: rubber's %s names no effect in BZSND.BIN" % ev]
        rec = BM.u16(snd, fxt + 2 * n)
        slot = g.m.read(g.a("bzs_fx"), F_SIZE)
        dseq = (g.w("bzs_fxseq") - seq0) & 0xFFFF
        if dseq != 1 or slot[13] != snd[rec] or slot[12] != snd[rec + 1]:
            return ["w7: %s keyed %d effect(s), the slot instrument %d priority %d - not %s's effect %d "
                    "(instrument %d, priority %d)" % (what, dseq, slot[13], slot[12], ev, n, snd[rec], snd[rec + 1])]
        return []
    clock_off(g)                                # (no limit from here: the checks' frames hear no tick)
    g.putb("bz_mat", 0)
    for ev, ctr in (("FLAG", "bz_nckpt"), ("PAD", "bz_npad"), ("LIP", "bz_nlip"), ("SPRING", "bz_nspr"),
                    ("RETURN", "bz_nret"), ("KNOCK", "bz_nknock"), ("TUBE", "bz_ntube"), ("BUMPER", "bz_nkick")):
        idle_w7()
        seq0 = g.w("bzs_fxseq")
        g.put(ctr, g.w(ctr) + 1)
        stop(g)
        fails += check(ev, "%s poked" % ctr, seq0)
    for secs, ev in ((30, "LOW"), (9, "TICK")):    # (each second poked at its start: set_clock)
        if not idle_w7():
            return fails
        set_clock(g, secs + 1)
        stop(g)
        if not idle_w7():                       # (31 keys nothing; 10 is a LOW, 13 sub-ticks)
            return fails
        held_at(secs + 1)
        seq0 = g.w("bzs_fxseq")
        set_clock(g, secs)
        stop(g)
        fails += check(ev, "%d seconds left" % secs, seq0)
    if not idle_w7():
        return fails
    set_clock(g, 1)                             # (and 1 s held: the course's own step to 0 would
    stop(g)                                     # time the play out - bz_fstart - under the check)
    if not idle_w7():
        return fails
    held_at(1)
    seq0 = g.w("bzs_fxseq")
    stop(g, "bzs_frame")
    g.put("bz_tsec", 0)
    g.putb("bz_tout", 1)
    stop(g)
    fails += check("TIMEOUT", "the timeout", seq0)
    g.putb("bz_tout", 0)                        # (the play goes on: the row's next steps run in it)
    return fails


def boost_events(g, snd):
    """SPEC.md 128.16.4.4: a boost poked into bz_nboost with each ball, and
    with a landing in the same frame"""
    fails = []
    emap, fxt = BM.u16(snd, 12), BM.u16(snd, 10)
    ne = len(BM.EVENTS)

    def eff(mat, ev):
        n = snd[emap + mat * ne + EV[ev]]
        return n, (None if n == 0xFF else BM.u16(snd, fxt + 2 * n))

    nb, rb = eff(0, "BOOST")
    nh, rh = eff(0, "HOP")
    if rb is None:
        return ["boost: rubber's BOOST names no effect in BZSND.BIN"]
    nxt = sorted(BM.u16(snd, fxt + 2 * k) for k in range(256) if fxt + 2 * k + 2 <= emap)

    def body(rec):
        later = [a for a in nxt if a > rec]
        return bytes(snd[rec:later[0] if later else rec + 32])
    if rh is not None and (nb == nh or body(rb) == body(rh)):
        fails.append("boost: rubber's BOOST effect %d is its HOP's (%d) by name or by content" % (nb, nh))
    for mat in range(3):
        for with_land in ((False, True) if mat == 0 else (False,)):
            fails += idle(g, "boost")
            g.putb("bz_mat", mat)
            seq0 = g.w("bzs_fxseq")
            if with_land:
                g.put("bz_lvz", 300)
                g.put("bz_nland", g.w("bz_nland") + 1)
            g.put("bz_nboost", g.w("bz_nboost") + 1)
            stop(g)
            dseq = (g.w("bzs_fxseq") - seq0) & 0xFFFF
            what = "%s's boost%s" % (BM.MATS[mat], " with a landing in the same frame" if with_land else "")
            n, rec = eff(mat, "BOOST")
            if rec is None:
                if dseq:
                    fails.append("boost: %s keyed %d effect(s); its column names none (SPEC.md 128.16.4.4)" % (
                        what, dseq))
                continue
            slot = g.m.read(g.a("bzs_fx"), F_SIZE)
            ok = slot[13] == snd[rec] and slot[12] == snd[rec + 1] and \
                struct.unpack("<H", slot[17:19])[0] == g.w("bzs_fxseq")
            if dseq != 1 or not ok:
                fails.append("boost: %s keyed %d effect(s), the slot %s effect %d (instrument %d, priority %d)%s" % (
                    what, dseq, "holding" if ok else "NOT holding", n, snd[rec], snd[rec + 1],
                    ": a boost contact keys no LAND" if with_land and dseq > 1 else ""))
    g.putb("bz_mat", 0)
    print("bonanza_sound boost: rubber's BOOST effect %d (HOP's %d), steel's and glass's none: %s" % (
        nb, nh, "yes" if not fails else "NO"), flush=True)
    return fails


def cost(g, frames=120):
    """cycles from bzs_frame to its .fend, every frame -> (mean, max)"""
    m = g.m
    a0, a1 = g.a("bzs_frame"), g.a("bzs_frame.fend")
    m.breakpoints([{"type": "exec", "addr": a0}, {"type": "exec", "addr": a1}])
    spans, t0 = [], None
    while len(spans) < frames:
        m.run()
        if not m.wait_stop(10):
            raise AssertionError("no frame reached bzs_frame")
        r = m.regs()
        lin = (r["cs"] << 4) + r["ip"]
        c = m.status()["cycles"]
        if lin == a0:
            t0 = c
        elif lin == a1 and t0 is not None:
            spans.append(c - t0)
            if os.environ.get("BZS_COSTLOG"):
                print("  frame %3d: %6d cycles, %d registers, %d sub-ticks stepped" % (
                    len(spans), c - t0, g.w("bzs_fmn"), g.w("bzs_nsub")))
            t0 = None
    m.breakpoints([])
    return sum(spans) / len(spans), max(spans)


def leg(arm_name, apps=None, src=None, art=None, only=None):
    snd, songs, p_snd = parts(art)
    sym = symbols(src, art)
    fails, notes = [], []
    want_arm = A_FM if arm_name == "fm" else A_SPK
    cap = None
    if arm_name == "fm":
        cap = os.path.join(tempfile.mkdtemp(prefix="bzsound-"), "audio")
        os.environ["MARTYPC_WAV"] = cap
    try:
        with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                         machine=MACHINE[arm_name]) as ui:
            os.environ.pop("MARTYPC_WAV", None)
            m = ui.m
            ui.open_drive("B")
            ui.open("BONANZA.O88")
            g = R.Bz(ui, "cga", sym, live=True)
            g.secsteps = sec_steps(art)
            M.guest_sleep(m, 2.0)
            m.pause()
            # 1. THE WINDOW IS SILENT (SPEC.md 128.26.5)
            if g.b("bzs_arm") != A_NONE or g.b("bzs_song") or g.b("bzs_live"):
                fails.append("the window: arm %d, song row %d, live %d - not silent"
                             % (g.b("bzs_arm"), g.b("bzs_song"), g.b("bzs_live")))
            # 2. S (the speaker leg only): OFF and AUTO, the window silent either way
            if arm_name == "spk" and only is None:
                for mode, arm, live in ((3, A_NONE, 0), (0, A_NONE, 0)):
                    m.run()
                    g.key("KeyS")
                    M.guest_sleep(m, 0.4)
                    m.pause()
                    got = (g.b("bzs_mode"), g.b("bzs_arm"), g.b("bzs_live"))
                    if got != (mode, arm, live):
                        fails.append("S: mode, arm, live %s - not %s" % (got, (mode, arm, live)))
                    if mode == 3 and (g.w("bzs_pseg") or g.w("bzs_mseg")):
                        fails.append("S: OFF kept a part (sound %04X, song %04X)"
                                     % (g.w("bzs_pseg"), g.w("bzs_mseg")))
                m.run()
                M.guest_sleep(m, 0.4)
            # 3. FIRST - a free play, F (Enter is the TITLE since SPEC.md 128.23.4)
            m.run()
            g.key("KeyF")
            M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 30, "the bracket is up", guest=60)
            m.pause()
            if g.b("bzs_arm") != want_arm or g.b("bzs_song") != p_snd + 1:
                fails.append("play: arm %d, song row %d - not arm %d, row %d (song 0)"
                             % (g.b("bzs_arm"), g.b("bzs_song"), want_arm, p_snd + 1))
            if only not in ("mat", "noboost"):
                for k in range(3):
                    for _ in range(25 + 40 * k):
                        stop(g)
                    f, n = held(g, snd, songs[0], want_arm, "FIRST")
                    fails += f
            # 4. THE EVENTS (the speaker leg; the slots are the same code on both),
            # FIRST's limit stopped first: its clock's LOW and TICKs are w7's to poke
            if arm_name == "spk" and only != "groove" and "bz_tsec" in g.sym:
                clock_off(g)
            if arm_name == "spk" and only not in ("groove", "noboost"):
                fails += events(g, snd)
            if arm_name == "spk" and only not in ("groove", "mat") and "bz_nboost" in g.sym:
                fails += boost_events(g, snd)
            if arm_name == "spk" and only not in ("groove", "mat", "noboost") and "bz_tsec" in g.sym:
                fails += w7_events(g, snd)              # wave 7 (SPEC.md 128.18.6)
            # 5. THE COST
            if only is None:
                mean, top = cost(g)
                notes.append("%s: a frame's sound %.0f cycles on average, %d at most (%.1f%% / %.1f%% of a "
                             "CGA refresh)" % (arm_name, mean, top, 100 * mean / 79600, 100 * top / 79600))
            # 6. ESC
            m.run()
            if arm_name == "fm":
                M.guest_sleep(m, 4.0)               # play, for the capture
            g.key("Escape")
            M.until(m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, "the desktop", guest=30)
            M.guest_sleep(m, 0.5)
            m.pause()
            if g.b("bzs_song") or g.b("bzs_arm") != A_NONE:
                fails.append("Esc: song row %d, arm %d - not the silent window's (none)"
                             % (g.b("bzs_song"), g.b("bzs_arm")))
            if arm_name == "fm" and only is None:
                import os88drvsym
                sy = os88drvsym.symbols("sound.bin")
                fseg = struct.unpack("<H", bytes(m.read(m.sym("drv_fseg"), 2)))[0]
                if m.read(fseg * 16 + sy["opl_xown"], 1)[0] != 0xFF:
                    fails.append("the silent window kept the chip claimed")
    finally:
        os.environ.pop("MARTYPC_WAV", None)
    if cap and only is None:
        import sndcheck
        rate, mono, _ = sndcheck.load(cap + ".adlib_music_synthesizer.wav")
        peak = max((abs(x) for x in mono), default=0.0)
        notes.append("fm: the OPL's capture peaks at %.3f" % peak)
        if peak < 0.05:
            fails.append("the OPL is silent (peak %.3f)" % peak)
    return fails, notes


REDS = {
    "groove": [("bzsound.inc", "    mov bl, [bzs_gi]            ; the row's length, the groove's next count\n",
                "    xor bl, bl                  ; RED groove: always the first count\n")],
    "mat": [("bzsound.inc", "    mov ah, [bz_mat]            ; AH = the material, for every trigger\n",
             "    xor ah, ah                  ; RED mat: every event the rubber ball's\n")],
    # wave 6 (SPEC.md 128.16.14): bz_nboost out of the counters' table
    "noboost": [("bzsound.inc", "            dw bzs_ctr7, bzs_ctr8, bzs_ctr9, bzs_ctr10, bzs_ctr11, bzs_ctr12, bzs_ctr13\n",
                 "            dw bzs_ctr7, bzs_ctr8, bzs_ctr9, bzs_ctr9, bzs_ctr11, bzs_ctr12, bzs_ctr13 ; RED noboost\n")],
}
    # wave 7 (SPEC.md 128.18.6): bz_nckpt out of the counters' table; the clock's events skipped
REDS["noflag"] = [("bzsound.inc", "%define bzs_ctr11   bz_nckpt    ; (wave 4's, mapped by wave 7, SPEC.md 128.18.6)\n",
                   "%define bzs_ctr11   bz_nret     ; RED noflag: bz_nckpt not read\n")]
REDS["notick"] = [("bzsound.inc", "    cmp ax, [bzs_ltsec]         ; moved - the TIMEOUT at 0 (a timed-out play's),\n"
                   "    je .nt                      ; LOW at 30 s and 10 s, a TICK under 10 s\n",
                   "    cmp ax, [bzs_ltsec]         ; moved - the TIMEOUT at 0 (a timed-out play's),\n"
                   "    jmp .nt                     ; RED notick: the clock's events skipped\n")]
    # wave 8R round 2: an effect's 0 terminator read but its slot never freed
REDS["nofree"] = [("bzsound.inc", "    jnz .seg\n    mov word [di + F_PTR], 0\n",
                   "    jnz .seg\n    mov byte [di + F_LEFT], 1    ; RED nofree: the slot never freed\n")]
RED_WANT = {"groove": "FIRST", "mat": "events", "noboost": "boost: rubber's boost keyed 0",
            "noflag": "w7: bz_nckpt poked keyed 0", "notick": "w7: 30 seconds left keyed 0",
            "nofree": "the effect slot never went idle"}


def shell_static():
    """wave 8R (SPEC.md 128.22.9), the host half: the shell's four events and the
    VICTORY tune are wired the way the contract says - the callable routines
    and the BZS_EV_* names exist, each names its own event, and the generated
    include's song index is the manifest's"""
    out = []
    inc = open(os.path.join(ROOT, "apps", "bonanza", "bzsound.inc")).read()
    for lab in ("bzs_ev", "bzs_victory"):
        if not re.search(r"^%s:" % lab, inc, re.M):
            out.append("bzsound.inc has no %s" % lab)
    for nm, ev in (("PAD", "ARRIVE"), ("GATE", "GATE"), ("LIFE", "LIFE"), ("OVER", "OVER")):
        if not re.search(r"^BZS_EV_%s\s+equ\s+BZS_E_%s\b" % (nm, ev), inc, re.M):
            out.append("BZS_EV_%s is not BZS_E_%s" % (nm, ev))
    # 2026-11-17: the finish's call was under an %ifdef of an EQU, so it was never assembled and the
    # fanfare never played; the listing's ASSEMBLED call (an address and bytes) is the proof it is in
    lst = R.at("build/bonanza.lst")
    if os.path.exists(lst):
        ln = open(lst).read().split("\n")
        # `call` is the SDK's macro: the bytes are on its expansion (E8 rel16), a few lines under the source
        # line; a call in a false conditional is listed with no expansion at all
        ok = any(re.search(r"\scall bzs_victory\b", t) and
                 any(re.match(r"^\s*\d+ [0-9A-F]{8} E8[0-9A-F]{4}\s", u) for u in ln[i + 1:i + 12])
                 for i, t in enumerate(ln))
        if not ok:
            out.append("bonanza.lst has no ASSEMBLED call bzs_victory: the finish never plays the fanfare")
    art = R.at("build/bonanza-art")
    g = os.path.join(art, "bzsnd.inc")
    if os.path.exists(g):
        t = open(g).read()
        v = re.search(r"^BZ_SONG_VICTORY\s+equ\s+(\d+)", t, re.M)
        ids = [x[:-4] for x in BM.SONGS]
        if not v or int(v.group(1)) != ids.index("victory"):
            out.append("bzsnd.inc's BZ_SONG_VICTORY is not victory's index")
        for e in ("ARRIVE", "GATE", "LIFE", "OVER"):
            m = re.search(r"^BZS_E_%s\s+equ\s+(\d+)" % e, t, re.M)
            if not m or int(m.group(1)) != EV[e]:
                out.append("bzsnd.inc's BZS_E_%s is not the tool's event %d" % (e, EV[e]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", choices=("spk", "fm", "both"), default="both")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half: the model and the red arms")
    a = ap.parse_args()
    if a.check:
        if subprocess.run(["python3", "tools/bbmusic.py", "--selfcheck"], cwd=ROOT).returncode:
            sys.exit(1)
        for line in R.check_reds(REDS, "bonanza_sound"):
            print(line)
        bad = shell_static()
        for b in bad:
            print("bonanza_sound: FAIL - " + b)
        if bad:
            sys.exit(1)
        return
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            try:
                bad, _ = leg("spk", apps=img, src=src, only=a.red)
            except AssertionError as e:
                bad = ["assertion: %s" % e]
            for b in bad:
                print("  red %s: %s" % (a.red, b))
            assert bad, "RED ARM %s: the row stayed GREEN against a broken package" % a.red
            assert any(RED_WANT[a.red] in b for b in bad), \
                "RED ARM %s went red, but not at its own check: %s" % (a.red, bad)
            print("bonanza_sound --red %s: red, as it must be" % a.red)
        return
    bad, notes = [], []
    print("bonanza_sound: the parts are %s (the parts table's format byte, SPEC.md 128.15.9): the sound part and "
          "the songs decoded in it" % R.part_fmt().upper(), flush=True)
    for lg in (("spk", "fm") if a.leg == "both" else (a.leg,)):
        f, n = leg(lg)
        bad += ["%s: %s" % (lg, x) for x in f]
        notes += n
    for n in notes:
        print("bonanza_sound: " + n)
    for b in bad:
        print("bonanza_sound: FAIL - " + b)
    if bad:
        sys.exit(1)
    print("bonanza_sound: ok")


if __name__ == "__main__":
    main()
