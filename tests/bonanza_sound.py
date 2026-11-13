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
  1  THE TITLE on the desktop: the speaker arm, song 0's part fetched, three
     stops a second apart held to the model;
  2  S cycles SPEAKER, EFFECTS ONLY (no song live), OFF (no arm, both parts
     given back) and AUTO (the title from its top);
  3  ENTER plays FIRST: course 1's song (song 1, the part row after the
     title's) in the bracket, three stops held to the model;
  4  THE EVENTS, poked into the counters the physics keeps (SPEC.md 128.20.5)
     at a stop, each ball in turn (bz_mat): a bounce, a wall, a bumper's face -
     the next frame's slot holds that ball's effect (its instrument, priority
     and transpose), and the three balls' effects are not the same;
  5  the cost: every frame's sound (bzs_frame to .fend) in guest cycles over
     120 frames of play;
  6  Esc: the song given back, the title again.
LEG fm, os8088_5150_sb (the same 5150 with an AdLib, SOUND.DRV loaded at
boot): 1 and 3 on the ADLIB arm (two effect slots), 5 priced there, the OPL's
own capture loud in play, and Esc and the window's close giving the chip back
(SOUND.DRV's opl_xown).

--red NAME builds a broken package in a temporary directory and PASSES only if
the row FAILS at its own check:
  groove   every row the groove's FIRST count: FIRST's 8 6 swing played
           straight - the bracket's model comparison fails
  mat      every event played as the rubber ball's: the events check fails
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
        open(p, "w").write(open(os.path.join(d, "bonanza.asm")).read() + "\n" +
                           "\n".join("dw " + n for n in names))
        subprocess.run(["nasm", "-f", "bin", "-I", os.path.join(ROOT, "apps") + "/", "-I", d + "/",
                        "-I", art + "/", "-o", b, p], cwd=ROOT, check=True)
        raw = open(b, "rb").read()
    return dict(zip(names, struct.unpack("<%dH" % len(names), raw[-2 * len(names):])))


def parts(art=None):
    art = art or R.at("build/bonanza-art")
    snd = open(os.path.join(art, "BZSND.BIN"), "rb").read()
    songs = [open(os.path.join(art, "BZM%d.BIN" % i), "rb").read() for i in range(len(BM.SONGS))]
    ncrs = int(re.search(r"^BZ_NCRS\s+equ\s+(\d+)", open(os.path.join(art, "bzcourse.inc")).read(),
                         re.M).group(1))
    return snd, songs, 3 + ncrs                 # ... and BZ_P_SND's row


def stop(g, label="bzs_tp", guest=10):
    """run to the next LABEL and stay there"""
    m = g.m
    m.breakpoints([{"type": "exec", "addr": g.a(label)}])
    m.run()
    if not m.wait_stop(guest):
        raise AssertionError("the guest never reached %s" % label)
    m.breakpoints([])


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
            for _ in range(400):                # the slot idle first (play makes its own)
                stop(g)
                if g.w("bzs_fx") == 0 and g.w("bzs_fx") == 0:
                    break
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
            M.until(m, lambda _: g.w("bzs_nsub") > 60, "the title is playing", guest=30)
            m.pause()
            # 1. THE TITLE
            if g.b("bzs_arm") != want_arm or g.b("bzs_song") != p_snd + 1:
                fails.append("title: arm %d, song row %d - not arm %d, row %d"
                             % (g.b("bzs_arm"), g.b("bzs_song"), want_arm, p_snd + 1))
            if only != "mat":
                for k in range(3):
                    m.run()
                    M.guest_sleep(m, 1.0)
                    stop(g)
                    f, n = held(g, snd, songs[0], want_arm, "title")
                    fails += f
            # 2. S (the speaker leg only)
            if arm_name == "spk" and only is None:
                for mode, arm, live in ((1, A_SPK, 1), (2, A_SPK, 0), (3, A_NONE, 0), (0, A_SPK, 1)):
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
            # 3. FIRST
            m.run()
            g.key("Enter")
            M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 30, "the bracket is up", guest=60)
            m.pause()
            if g.b("bzs_arm") != want_arm or g.b("bzs_song") != p_snd + 2:
                fails.append("play: arm %d, song row %d - not arm %d, row %d (song 1)"
                             % (g.b("bzs_arm"), g.b("bzs_song"), want_arm, p_snd + 2))
            if only != "mat":
                for k in range(3):
                    for _ in range(25 + 40 * k):
                        stop(g)
                    f, n = held(g, snd, songs[1], want_arm, "FIRST")
                    fails += f
            # 4. THE EVENTS (the speaker leg; the slots are the same code on both)
            if arm_name == "spk" and only != "groove":
                fails += events(g, snd)
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
            M.until(m, lambda _: g.b("bz_fs") == 0 and g.b("bzs_desk") == 1, "the desktop and the title",
                    guest=30)
            m.pause()
            if g.b("bzs_song") != p_snd + 1 or g.b("bzs_arm") != want_arm:
                fails.append("Esc: song row %d, arm %d - not the title's %d on arm %d"
                             % (g.b("bzs_song"), g.b("bzs_arm"), p_snd + 1, want_arm))
            if arm_name == "fm" and only is None:
                import os88drvsym
                sy = os88drvsym.symbols("sound.bin")
                fseg = struct.unpack("<H", bytes(m.read(m.sym("drv_fseg"), 2)))[0]
                if m.read(fseg * 16 + sy["opl_xown"], 1)[0] == 0xFF:
                    fails.append("the title on the AdLib holds no claim")
                m.run()
                ui.menu_pick("BONANZA", "Close")
                M.guest_sleep(m, 1.0)
                m.pause()
                if m.read(fseg * 16 + sy["opl_xown"], 1)[0] != 0xFF:
                    fails.append("closing the window left the chip claimed")
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
}
RED_WANT = {"groove": "FIRST", "mat": "events"}


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
