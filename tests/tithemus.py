#!/usr/bin/env python3
"""TITHE's MUSIC: does the machine play what the score says, tick for tick?

SPEC.md 97.10. The sequencer (apps/tithe/timus.inc) and the tool's model of it
(tools/os88tithemus.py's `Seq`) read the SAME packed part, so the machine's
state after N ticks - which order row, which row, which note on every channel -
must be the model's after N steps EXACTLY. That is what this holds it to, on
both arms, for every title theme `M` steps through:

  1. THE ARM IS THE CAPS' ANSWER. A Sound Blaster 5150 (SOUND.DRV mounts
     itself at boot, SPEC.md 51.3.1) plays FM; a plain one plays the speaker.

  2. EVERY SONG, TICK FOR TICK. The first song's whole COMMAND STREAM - every
     OSAPI_SND_TONE or OSAPI_SND_FM call, caught at a breakpoint with its
     registers and the tick it was made on (and a patch's eleven bytes) - is
     the model's, call for call. Then each song is sampled with the machine PAUSED - the
     tick count, the order row, the row and all four channels' notes - and
     compared with the model stepped as many times. A stall pauses the music
     and does not count a tick, so the comparison is exact under any load.
     A pause can land INSIDE a tick - the row counted and the tick not yet -
     and the first run of this row caught exactly that, so `[tm_busy]` is set
     across tm_run and a sample waits it out.

  3. THE SPEAKER IS GATED ONLY WHEN THE LEAD SOUNDS, on the speaker arm:
     port 61h's two low bits against the model's lead, at every sample - and
     the lead's last FREQUENCY is the model's, which is where the instrument's
     macro and vibrato show and nowhere else.

  4. `M` past the last song is SILENCE, and `S` moves a playing song to the
     one-voice arm on a machine that has FM.

  5. THE FRAME HOLDS WITH THE MUSIC ON (TITHE-PLAN 16.1.1's gate for wave
     1b): wheel passes a second with a song playing against the same span
     silent.

Broken on purpose before it was registered: a gate that starts counting on
the note-on tick (every note one tick short) fails every song's samples; the
speaker's macro step off by one fails the command stream - and PASSED the
samples, a one-tick scoop being what a sample a second apart sees one time in
eight, which is why the stream is here. The groove's index never advancing
fails NOTHING, and says so: no song yet has a groove of more than one step,
so that branch is exercised by the tool's --selfcheck on the host and not
here.

    make && make tithedisk && python3 tests/tithemus.py
    python3 tests/tithemus.py --record build/tithemus-guest

`--record DIR` also saves the GUEST's own audio - one WAV per song per arm,
cut out of MartyPC's continuous capture (MARTYPC_WAV) by the guest's cycle
count at the key press - which is the truth the host render approximates.
"""
import argparse
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402
import os88tithemus as tm                                 # noqa: E402

SYMS = ("tm_song", "tm_arm", "tm_ticks", "tm_ord", "tm_row", "tm_ch",
        "tm_sel", "ti_nframe", "tm_busy", "tm_tone")
FM_CELL = os88marty.KERNEL_SEG * 16 + 0x00F8    # OSAPI_SND_FM's cell
STREAM = {"spk": 80, "fm": 240}                 # calls of song 0 compared
MACHINES = (("os8088_5150_herc_sb_gla", "fm"), ("os8088_5150_herc_gla", "spk"))
SAMPLES = 6                         # a song, a guest second apart
fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    """Assembled from the SOURCE, as tests/titheterr.py's are."""
    src = open(os.path.join(ROOT, "apps/tithe/tithe.asm"), encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "tithemus-off.asm")
    out = os.path.join(ROOT, "build", "tithemus-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp], cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def run(mach, want_arm, off, part, nsong, record, marks):
    print("  --- %s (%s)" % (mach, want_arm))
    with os88ui.boot("build/os8088-360.img", apps="build/tithe360.img",
                     machine=mach) as ui:
        m = ui.m
        ui.path("B:/TITHE.O88")
        win = [w for w in os88geom.windows(m) if w.title == "Tithe"][0]
        seg = struct.unpack(
            "<H", bytes(m.read(os88geom.winptr(m, win) + os88geom.W_SEG, 2)))[0]
        ui.raise_window(win)
        os88marty.guest_sleep(m, 6.0)

        def rb(name, n=1):
            return bytes(m.readseg(seg, off[name], n))

        def rw(name):
            return struct.unpack("<H", rb(name, 2))[0]

        def gsecs():
            return int(m.status().get("cycles", 0)) / os88marty.GUEST_HZ

        def fps(span):
            f = rw("ti_nframe")
            spent = os88marty.guest_sleep(m, span)
            return ((rw("ti_nframe") - f) & 0xFFFF) / spent

        quiet = fps(4.0)

        # --- item 2's first half: SONG 0's WHOLE COMMAND STREAM, every call
        # the sequencer makes, against the model's - exact, where a sample a
        # second apart would see a one-tick macro step one time in eight
        want = []
        sq = tm.Seq(part, 0, want_arm)
        k = 0
        while len(want) < STREAM[want_arm]:
            for a in sq.step():
                if a[0] == "spk":
                    want.append((k, a[1], a[2]))
                else:
                    want.append((k, a[1], a[2], a[3] if a[2] in (0, 2) else None))
            k += 1
        want = want[:STREAM[want_arm]]

        def on_hit(mm, rec):
            r = mm.regs()
            t = struct.unpack("<H", bytes(mm.readseg(seg, off["tm_ticks"], 2)))[0]
            if want_arm == "spk":
                return (t, r["ax"], r["cx"])
            verb, voice = r["ax"] & 0xFF, r["cx"] & 0xFF
            arg = (r["bx"] if verb == 0 else
                   bytes(mm.readseg(r["ds"], r["si"], 11)) if verb == 2 else None)
            return (t, voice, verb, arg)

        at = seg * 16 + off["tm_tone"] if want_arm == "spk" else FM_CELL
        with os88marty.bp_trace(m, at, on_hit=on_hit) as tr:
            m.key("KeyM")
            t0 = gsecs()
            tr.wait(len(want), limit=120.0)
        got = [h["hit"] for h in tr.hits][:len(want)]
        first = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), None)
        check(len(got) == len(want) and first is None,
              "%s: song 0's first %d %s calls are the model's, call for call"
              % (mach, len(want), "OSAPI_SND_TONE" if want_arm == "spk"
                 else "OSAPI_SND_FM"),
              "call %s: guest %s, model %s" % (first, got[first], want[first])
              if first is not None else "%d calls" % len(got))

        for si in range(nsong):
            if si:                      # song 0 was started by the trace, and
                m.key("KeyM")           # its recording starts at ITS key press
                t0 = gsecs()
            os88marty.guest_sleep(m, 0.5)
            song, arm = rb("tm_song")[0], rb("tm_arm")[0]
            name = tm.parse_song(os.path.join(tm.MUSDIR, tm.SONGS[si]),
                                 *tm.parse_bank()[0::2]).id
            check(song == si, "%s: M starts song %d (%s)" % (mach, si, name), song)
            check(arm == (1 if want_arm == "fm" else 0),
                  "...on the %s arm" % want_arm, arm)
            if song != si:
                continue
            bad, spk_bad, n = [], [], 0
            for _ in range(SAMPLES):
                os88marty.guest_sleep(m, 1.0)
                m.pause()
                for _ in range(50):     # never read a tick half-stepped
                    if not rb("tm_busy")[0]:
                        break
                    m.run()
                    os88marty.guest_sleep(m, 0.003)
                    m.pause()
                T = rw("tm_ticks")
                chs = rb("tm_ch", 4 * 12)
                ordr, row = rb("tm_ord")[0], rb("tm_row")[0]
                gate61 = m.inb(0x61) & 3 if want_arm == "spk" else None
                m.run()
                sq = tm.Seq(part, si, want_arm)
                for _ in range(T):
                    sq.step()
                model = [c.note for c in sq.ch]
                guest = [chs[12 * c + 3] for c in range(4)]
                if want_arm == "spk":   # ...and the lead's FREQUENCY, which is
                    model.append(sq.ch[0].last_f)       # where the macro and
                    guest.append(chs[10] | chs[11] << 8)  # the vibrato live
                n += 1
                if (model, sq.ord, sq.row) != (guest, ordr, row):
                    bad.append("T=%d guest ord %d row %d %s, model ord %d row %d %s"
                               % (T, ordr, row, guest, sq.ord, sq.row, model))
                if gate61 is not None and (gate61 == 3) != bool(model[0]):
                    spk_bad.append("T=%d 61h&3=%d lead %d" % (T, gate61, model[0]))
            check(not bad, "...%d samples, the machine is the model tick for tick"
                  % n, bad[:2])
            if want_arm == "spk":
                check(not spk_bad, "...and the speaker sounds exactly when the "
                      "lead does", spk_bad[:2])
            if si == 0:
                on = fps(4.0)
                check(on >= quiet * 0.95,
                      "...the frame holds with the music on: %.1f passes/s "
                      "against %.1f silent" % (on, quiet), (on, quiet))
            if record:
                one = tm.Seq(part, si, want_arm).song_ticks() / tm.TICK_HZ
                os88marty.guest_sleep(m, max(0.0, one + 2.0 - SAMPLES - 0.5))
            marks.append((mach, want_arm, name, t0, gsecs()))
        m.key("KeyM")
        os88marty.guest_sleep(m, 0.5)
        check(rb("tm_song")[0] == 0xFF, "%s: M past the last song is silence" % mach,
              rb("tm_song")[0])
        if want_arm == "spk":
            os88marty.guest_sleep(m, 0.3)
            check(m.inb(0x61) & 3 != 3, "...and the speaker is off", m.inb(0x61))
        else:
            m.key("KeyM")               # song 0 again, then S: the one voice
            os88marty.guest_sleep(m, 0.5)
            m.key("KeyS")
            os88marty.guest_sleep(m, 0.5)
            check(rb("tm_song")[0] == 0 and rb("tm_arm")[0] == 0,
                  "...and S moves the song to the one-voice arm",
                  (rb("tm_song")[0], rb("tm_arm")[0]))


def cut(capture, marks, outdir):
    """The guest's own audio, song by song, out of MARTYPC_WAV's files."""
    import glob
    os.makedirs(outdir, exist_ok=True)
    for mach, arm, name, t0, t1 in marks:
        src = [f for f in glob.glob(capture[mach] + ".*.wav")
               if ("adlib" in f if arm == "fm" else "speaker" in f)]
        if not src:
            print("  (no capture for %s %s)" % (mach, arm))
            continue
        d = open(src[0], "rb").read()
        nch, sr = struct.unpack("<HI", d[22:28])
        fr = 2 * nch
        a, b = int(t0 * sr) * fr + 44, int(t1 * sr) * fr + 44
        pcm = d[a:min(b, len(d))]
        pcm = pcm[:len(pcm) - len(pcm) % fr]
        path = os.path.join(outdir, "%s-%s-guest.wav" % (name, arm))
        with open(path, "wb") as f:
            f.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt ")
            f.write(struct.pack("<IHHIIHH", 16, 1, nch, sr, sr * fr, fr, 16))
            f.write(b"data" + struct.pack("<I", len(pcm)) + pcm)
        print("  %s: %.1f s of the guest" % (path, len(pcm) / fr / sr))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", metavar="DIR")
    ap.add_argument("machines", nargs="*")
    a = ap.parse_args()
    off = offsets()
    part = open(os.path.join(ROOT, "build", "timus.bin"), "rb").read()
    nsong = part[3]
    marks, capture = [], {}
    for mach, arm in MACHINES:
        if a.machines and mach not in a.machines:
            continue
        if a.record:
            capture[mach] = os.path.join(ROOT, "build", "tithemus-cap-" + arm)
            for old in __import__("glob").glob(capture[mach] + ".*.wav"):
                os.remove(old)
            os.environ["MARTYPC_WAV"] = capture[mach]
        run(mach, arm, off, part, nsong, a.record, marks)
        os.environ.pop("MARTYPC_WAV", None)
    if a.record:
        cut(capture, marks, a.record)
    print("tithemus: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
