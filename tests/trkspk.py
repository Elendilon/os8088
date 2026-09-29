#!/usr/bin/env python3
"""TRACKER ON THE PC SPEAKER, with no card - SPEC.md 45.25.

    make && python3 tests/trkspk.py [--leg play|refuse|turbo|end|card]

On MartyPC's card-less Hercules 5150 with a fixed disk, BEVERLY.MOD opened
from C:. With no card Tracker plays through the speaker on its own (the
owner's question 1), from inside its own FSXF_RATE bracket - the imposter
window - after timing this machine once (question 5). What must hold:

  play    the 5150 is CALIBRATED and takes the 4,800 Hz rung - the one it
          can HOLD (45.25.1: the owner's 5150 measured the ISR at ~395 cycles a
          sample, and 5,512's "95%" was ~103%): the pulses run at that rate
          (under LOSS lost to IF = 0), the ring NEVER runs dry while the song
          plays, the visualiser is forced off (tw_vizxhi, the 11 kHz rule) and
          the elapsed clock counts. Then Space pauses - the door shut, channel
          2 and the sample ISR given back - Space plays on from there, F
          takes the play into the full screen with the door open again and
          no dry ring, F brings it back to the window, and S stops it clean.
  refuse  a build whose ceiling is 50% (-DTSP_PCTMAX=50): the load's play is
          REFUSED with the predicted figure on the status line and the door
          never opens; Play again plays anyway, at the last rung (question 2)
  turbo   MartyPC's 7.16 MHz XT (the only faster machine it has): the same
          bench takes the 8,000 Hz rung, and the pulses keep it
  end     tools/mkmod.py's short song plays to its end: the door closes by
          itself and the kernel is left clean
  card    a Sound Blaster machine: the card's stream, the speaker untouched

Broken on purpose - tw_vizxhi's speaker test removed: play FAILS on the
visualiser. TSP_CS doubled: play FAILS on the rung (the 5150 is then
refused). TSP_CS back at 89: play FAILS on the rung (it takes 5,512). NOT seen, and said so: tsp_wmain's audio-first gate removed (a
frame every period whatever the lead) still passes play - with the
visualiser off a 5150's frame is cheap enough that BEVERLY.MOD at 4,800 Hz
never needs it. The gate is a net for a heavier face, not something this
machine exercises.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88marty, os88ui, os88build                   # noqa: E402
import os88geom as geom                               # noqa: E402
from cycweb import pkg_syms                           # noqa: E402

MACHINE = "os8088_5150_herc_hdd_gla"
MACHINE_SB = "os8088_5150_herc_hdd_sb_gla"
TURBO = "os8088_xt_vga_hdd"
TEMPLATE = "build/martypc/run/media/hdds/default_xtide.vhd"
PULSES = 3000
LOSS = 0.04
CPU = 4772727.0
TWV_OFF = 3
SRC = ("apps/tracker/tracker.asm", ("apps/", "apps/tracker/"))


def u16(b, o=0):
    return b[o] | b[o + 1] << 8


def vhd_for(tmp, files):
    vhd = os.path.join(tmp, "trk.vhd")
    cmd = [sys.executable, "tools/os88hdd.py", "--template", TEMPLATE,
           "--out", vhd, "--kernel", os88build.at("build/kernel.sys"),
           "--vbr", os88build.at("build/boothd.bin"),
           "--mbr", os88build.at("build/mbr.bin")]
    for name, path in files:
        cmd += ["--file", "%s=%s" % (name, path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return vhd


class Trk:
    """a booted machine with Tracker open on a module from C:"""

    def __init__(self, machine, files, mod, defines=(), extra=()):
        self.syms, _ = pkg_syms(*SRC, defines=defines) if defines else \
            pkg_syms(*SRC)
        self.tmp = tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "build"))
        vhd = vhd_for(self.tmp.name, files)
        self.m = os88marty.launch(
            None, machine=machine,
            extra=list(extra) + ["--mount", "hd:0:" + os.path.abspath(vhd)])
        self.ui = os88ui.UI(self.m)
        self.ui.ready(limit=240)
        w = self.ui.path("C:/" + mod)
        rec = self.m.read(self.ui._S("wm_wins") + w.i * geom.WIN_SIZE,
                          geom.WIN_SIZE)
        self.base = (rec[geom.W_SEG] | rec[geom.W_SEG + 1] << 8) << 4

    def a(self, n):
        return self.base + self.syms[n]

    def rb(self, n):
        return self.m.read(self.a(n), 1)[0]

    def rw(self, n):
        return u16(self.m.read(self.a(n), 2))

    def ring(self):
        """(TOTAL, CONS) of the speaker's ring"""
        d = self.m.read((self.rw("tsp_rseg") << 4) + 16384, 4)
        return u16(d), u16(d, 2)

    def until(self, f, what, limit=300.0):
        os88marty.until(self.m, lambda mm: f(), what, poll=0.2,
                        limit=limit, guest=limit)

    def kernel_clean(self):
        return (self.m.read(self.m.sym("snd_ch2mode"), 1)[0],
                u16(self.m.read(self.m.sym("spk_seg"), 2)))

    def pulses(self, n=PULSES):
        """n writes to port 42h, and the ring's dry grants over them"""
        cyc, dry = [], [0]
        k_dry = self.base + self.syms["os88spk_grant.dry"]

        def hit(mm, rec):
            if rec.get("addr") == k_dry:
                dry[0] += 1
            else:
                cyc.append(rec["cycles"])
        with os88marty.bp_trace(self.m, {"type": "io", "addr": 0x42},
                                k_dry, on_hit=hit):
            t0 = time.time()
            while len(cyc) < n and time.time() - t0 < 600:
                time.sleep(0.2)
        if len(cyc) < 2:
            return 0.0, dry[0]
        return (len(cyc) - 1) / ((cyc[-1] - cyc[0]) / CPU), dry[0]

    def close(self):
        try:
            self.m.close()
        finally:
            self.tmp.cleanup()


def check(bad, ok, what):
    print("   %s %s" % ("ok  " if ok else "FAIL", what))
    if not ok:
        bad.append(what)


def leg_play(bad):
    t = Trk(MACHINE, [("TRACKER.O88", os88build.at("build/tracker.o88")),
                      ("BEVERLY.MOD", "apps/tracker/beverly.mod")],
            "BEVERLY.MOD")
    try:
        t.until(lambda: t.rb("tsp_open") == 1 or t.rb("tsp_force") == 1,
                "the play or its refusal")
        rate, rung, pct = t.rw("tsp_rate"), t.rb("tsp_rung"), t.rw("tsp_pct")
        print("   the bench: shaper %d in 4 ticks, mixer %d in 8; %d Hz "
              "(rung %d) predicted at %d%%" % (t.rw("tsp_ne"), t.rw("tsp_nm"),
                                              rate, rung, pct))
        check(bad, t.rb("tsp_open") == 1 and rate == 4800,
              "play: the 5150 plays at 4,800 Hz by itself")
        if t.rb("tsp_open") != 1:
            return
        want = "Spk %d Hz, %d%% cpu (CARRIER WHINES!)" % (rate, pct)
        os88marty.pace(t.m, 3.0)        # ...and STILL says it once the door
        p = t.rw("tui_msgp")            # is open: the play's first frames
        msg = t.m.read(t.base + p, 64).split(b"\0")[0].decode()   # put the
        check(bad, msg == want,         # transport legend over it once
              "play: the status line reads %r, the door open" % msg)
        os88marty.pace(t.m, 1.0)
        r, dry = t.pulses()
        print("   %d pulses at %.0f Hz, the ring dry %d times" % (
            PULSES, r, dry))
        check(bad, r >= rate * (1 - LOSS), "play: the pulses keep the rate")
        check(bad, dry == 0, "play: the ring never runs dry")
        check(bad, t.rb("tw_vizm") == TWV_OFF,
              "play: the visualiser is off (tw_vizxhi)")
        el = t.rw("tw_el")
        check(bad, el > 0, "play: the clock counts (%d bytes heard)" % el)
        # --- Space: paused, the machine given back ---
        pos = t.rb("tui_apos") * 64 + t.rb("tui_arow")
        t.m.type_text(" ")
        t.until(lambda: t.rb("tsp_run") == 0 and t.kernel_clean()[1] == 0,
                "Space to pause")
        ch2, seg = t.kernel_clean()
        check(bad, t.rb("trk_pause") == 1 and ch2 == 0 and seg == 0,
              "pause: the door shut, channel 2 %d, sample ISR %04x" % (ch2,
                                                                      seg))
        os88marty.pace(t.m, 1.0)
        t.m.type_text(" ")
        t.until(lambda: t.rb("tsp_open") == 1, "Space to play on")
        os88marty.pace(t.m, 1.0)
        pos2 = t.rb("tui_apos") * 64 + t.rb("tui_arow")
        check(bad, pos2 >= pos, "resume: on from row %d, now %d" % (pos,
                                                                   pos2))
        # --- F: the full screen, playing on ---
        t.m.type_text("f")
        t.until(lambda: t.rb("trk_fs") == 1 and t.rb("tsp_open") == 1,
                "F to the full screen")
        os88marty.pace(t.m, 1.0)
        r, dry = t.pulses(1500)
        print("   full screen: %.0f Hz, dry %d" % (r, dry))
        check(bad, r >= rate * (1 - LOSS) and dry == 0,
              "full screen: the speaker plays on, never dry")
        t.m.type_text("f")
        t.until(lambda: t.rb("trk_fs") == 0 and t.rb("tsp_open") == 1,
                "F back to the window")
        check(bad, True, "full screen: back to the window, still playing")
        os88marty.pace(t.m, 1.0)
        t.m.type_text("s")
        t.until(lambda: t.rb("tsp_run") == 0 and t.kernel_clean()[1] == 0,
                "S to stop")
        ch2, seg = t.kernel_clean()
        check(bad, ch2 == 0 and seg == 0, "stop: the kernel clean")
    finally:
        t.close()


def leg_refuse(bad):
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "build")) as tmp:
        b = os.path.join(tmp, "trk50.bin")
        o = os.path.join(tmp, "TRACKER.O88")
        subprocess.run(["nasm", "-f", "bin", "-w+error", "-DTSP_PCTMAX=50",
                        "-I", "apps/", "-I", "apps/tracker/", "-o", b,
                        "apps/tracker/tracker.asm"], check=True)
        subprocess.run([sys.executable, "tools/os88pkg.py", b, "-o", o],
                       check=True, capture_output=True)
        t = Trk(MACHINE, [("TRACKER.O88", o),
                          ("BEVERLY.MOD", "apps/tracker/beverly.mod")],
                "BEVERLY.MOD", defines=("TSP_PCTMAX=50",))
        try:
            t.until(lambda: t.rb("tsp_force") == 1, "the refusal")
            os88marty.pace(t.m, 1.0)
            pct = t.rw("tsp_pct")
            msg = t.m.read(t.a("tsp_msg"), 64).split(b"\0")[0].decode()
            print("   refused: %r (predicted %d%%)" % (msg, pct))
            check(bad, msg == "Speaker: needs %d%% of this PC - Play again "
                  "to try" % pct and pct > 50,
                  "refuse: the status line gives the figure")
            check(bad, t.rb("tsp_run") == 0 and t.kernel_clean()[1] == 0,
                  "refuse: the door never opened")
            t.m.type_text(" ")
            t.until(lambda: t.rb("tsp_open") == 1, "Play again")
            check(bad, t.rw("tsp_rate") == 4800,
                  "refuse: Play again plays anyway, at the last rung "
                  "(%d Hz)" % t.rw("tsp_rate"))
        finally:
            t.close()


def leg_drop(bad):
    """a build that believes the speaker CHEAP (-DTSP_CS=40) on mkmod's song,
    which needs ~107% at 5,512 Hz: it starts there, falls behind, and comes
    down to 4,800 LIVE - the door reopening on half a ring, the line saying
    the new rate, and the song playing on at it with the ring never dry"""
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "build")) as tmp:
        b = os.path.join(tmp, "trkcs.bin")
        o = os.path.join(tmp, "TRACKER.O88")
        subprocess.run(["nasm", "-f", "bin", "-w+error", "-DTSP_CS=40",
                        "-I", "apps/", "-I", "apps/tracker/", "-o", b,
                        "apps/tracker/tracker.asm"], check=True)
        subprocess.run([sys.executable, "tools/os88pkg.py", b, "-o", o],
                       check=True, capture_output=True)
        mod = os.path.join(tmp, "TEST.MOD")
        subprocess.run([sys.executable, "tools/mkmod.py", mod], check=True,
                       capture_output=True)
        t = Trk(MACHINE, [("TRACKER.O88", o), ("TEST.MOD", mod)], "TEST.MOD",
                defines=("TSP_CS=40",))
        try:
            t.until(lambda: t.rb("tsp_open") == 1, "the play")
            el = lambda: int.from_bytes(t.m.read(t.a("tw_el"), 4),
                                        "little") / float(t.rw("mp_mixrate"))
            c0, e0 = t.m.status()["cycles"], el()
            r0 = t.rw("tsp_rate")
            print("   drop: starts at %d Hz, predicted %d%%" % (
                r0, t.rw("tsp_pct")))
            check(bad, r0 == 5512, "drop: it starts at 5,512 Hz")
            t.until(lambda: t.rw("tsp_rate") == 4800 and
                    t.rb("tsp_open") == 1, "the rung down", limit=300.0)
            msg = t.m.read(t.a("tsp_msg"), 64).split(b"\0")[0].decode()
            check(bad, msg.startswith("Spk 4800 Hz, ") and
                  msg.endswith(" cpu (CARRIER WHINES!)"),
                  "drop: down to 4,800 live, the line reads %r" % msg)
            os88marty.pace(t.m, 1.0)
            r, dry = t.pulses(2000)
            print("   after it: %.0f Hz, dry %d" % (r, dry))
            check(bad, r >= 4800 * (1 - LOSS) and dry == 0,
                  "drop: it holds 4,800 with the ring never dry")
            # THE TEMPO after the drop: samples a tick at the NEW rate (a
            # drop that kept 5,512's played at 87% - its rows are longer),
            # and the clock going on rather than jumping. mkmod's song
            # changes its own tempo (Fxx), so the invariant is read, not
            # rows a second
            spt, bpm = t.rw("mp_spt"), t.rb("mp_bpm")
            want = 4800 * 5 // (2 * max(bpm, 32))
            print("   tempo: %d samples a tick at BPM %d, 4,800 Hz's %d"
                  % (spt, bpm, want))
            check(bad, spt == want,
                  "drop: the ticks are 4,800 Hz's after it")
            os88marty.pace(t.m, 2.0)
            c1, e1 = t.m.status()["cycles"], el()
            secs = (c1 - c0) / CPU
            # the clock counts what was HEARD, so it trails the guest by
            # the drop's silent refill of half a ring (~1.5 s here); left in
            # the old rate's bytes it JUMPS by the time before the drop x
            # (5,512 / 4,800 - 1) and trails by ~0.2 s - measured both ways
            lag = secs - (e1 - e0)
            print("   the clock: %.1f s over %.1f, %.1f s behind (the "
                  "drop's refill)" % (e1 - e0, secs, lag))
            check(bad, 0.5 <= lag <= 2.5,
                  "drop: the elapsed clock keeps time across it")
        finally:
            t.close()


def leg_turbo(bad):
    t = Trk(TURBO, [("TRACKER.O88", os88build.at("build/tracker.o88")),
                    ("BEVERLY.MOD", "apps/tracker/beverly.mod")],
            "BEVERLY.MOD", extra=["--turbo"])
    try:
        t.until(lambda: t.rb("tsp_open") == 1 or t.rb("tsp_force") == 1,
                "the play")
        rate = t.rw("tsp_rate")
        print("   turbo: %d Hz predicted at %d%% (shaper %d, mixer %d)" % (
            rate, t.rw("tsp_pct"), t.rw("tsp_ne"), t.rw("tsp_nm")))
        check(bad, rate == 8000 and t.rb("tsp_open") == 1,
              "turbo: the 7.16 MHz XT takes 8,000 Hz")
        os88marty.pace(t.m, 1.0)
        # the turbo machine's cycle counter is not 4.77 MHz: the rate is
        # checked on the ring's own clock instead - dry grants, none
        r, dry = t.pulses(2000)
        check(bad, dry == 0, "turbo: the ring never runs dry (%d)" % dry)
    finally:
        t.close()


def leg_end(bad):
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "build")) as tmp:
        mod = os.path.join(tmp, "TEST.MOD")
        subprocess.run([sys.executable, "tools/mkmod.py", mod], check=True,
                       capture_output=True)
        t = Trk(MACHINE, [("TRACKER.O88", os88build.at("build/tracker.o88")),
                          ("TEST.MOD", mod)], "TEST.MOD")
        try:
            t.until(lambda: t.rb("tsp_open") == 1 or t.rb("tsp_force") == 1,
                    "the play or its refusal")
            print("   %d Hz predicted at %d%% (shaper %d, mixer %d)" % (
                t.rw("tsp_rate"), t.rw("tsp_pct"), t.rw("tsp_ne"),
                t.rw("tsp_nm")))
            if t.rb("tsp_open") != 1:       # a song of 400 sample bytes loops
                t.m.type_text(" ")          # all four channels every few
                t.until(lambda: t.rb("tsp_open") == 1, "Play again")
            # Repeat off: a one-song list LOOPS in the replayer (45.21.3),
            # so the song ends only with [mp_endstop] set - what trk_rep 0
            # makes trk_endstop_upd store
            t.m.write(t.a("trk_rep"), b"\0")
            t.m.write(t.a("mp_endstop"), b"\1")
            t.until(lambda: t.rb("tsp_run") == 0, "the song's end",
                    limit=600.0)
            os88marty.pace(t.m, 1.0)
            ch2, seg = t.kernel_clean()
            check(bad, t.rb("trk_ended") == 1 and ch2 == 0 and seg == 0,
                  "end: the door closed by itself, the kernel clean")
        finally:
            t.close()


def leg_card(bad):
    t = Trk(MACHINE_SB, [("TRACKER.O88", os88build.at("build/tracker.o88")),
                         ("SOUND.DRV", os88build.at("build/sound.drv")),
                         ("BEVERLY.MOD", "apps/tracker/beverly.mod")],
            "BEVERLY.MOD")
    try:
        t.until(lambda: t.rb("trk_sopen") == 1, "the card's stream")
        os88marty.pace(t.m, 2.0)
        check(bad, t.rb("tsp_run") == 0 and t.rb("tsp_cal") == 0 and
              t.kernel_clean()[1] == 0, "card: the speaker untouched")
    finally:
        t.close()


LEGS = {"play": leg_play, "refuse": leg_refuse, "drop": leg_drop,
        "turbo": leg_turbo,
        "end": leg_end, "card": leg_card}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", action="append", choices=sorted(LEGS))
    a = ap.parse_args()
    os.chdir(ROOT)
    bad = []
    for name in a.leg or ["play"]:
        print(" %s:" % name)
        LEGS[name](bad)
    print("trkspk: %s" % ("FAIL" if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
