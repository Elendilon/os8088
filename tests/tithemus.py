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
     across tm_run and a sample waits it out. It can also land BEFORE one:
     IRQ0 has counted the tick and expired a tone whose duration ran out,
     and the worker has not yet been scheduled to key the note off - a
     window of well under a millisecond that Litany's long notes hit once in
     48 samples. So a sample also waits for `[tm_last]` to be the kernel's
     tick, which is the sequencer having served the tick the timer began.

  3. THE SPEAKER IS GATED ONLY WHEN THE LEAD SOUNDS, on the speaker arm:
     port 61h's two low bits against the model's lead, at every sample - and
     the lead's last FREQUENCY is the model's, which is where the instrument's
     macro and vibrato show and nowhere else.

  4. `M` past the last song is SILENCE, `S` moves a playing song to the
     one-voice arm on a machine that has FM and back again - and the Control
     Panel's "PC speaker" does too. That setting is the TONE route (SPEC.md
     34.8) and leaves FM published, so a package reading the caps word alone
     plays FM to a user who asked for the speaker; it was reported off the
     owner's machine exactly that way.

  5. THE FRAME HOLDS WITH THE MUSIC ON (TITHE-PLAN 16.1.1's gate for wave
     1b): wheel passes a second with a song playing against the same span
     silent.

  6. ...AND THE MUSIC HOLDS WHEN THE FRAME DOES NOT. `G` rebuilds the board
     on the UI task with the gfx lock held for seconds, and the worker is
     blocked on that lock throughout; the song must advance one tick per tick
     of the clock across it, and no step may come more than TM_LATE ticks
     late (`[tm_gapmax]`). It did not: a pass three ticks late counted as a
     STALL and stepped once, so the music slowed with the frame and STOPPED
     for a relayout - reported off the owner's machine, and measured at 0
     ticks of song in 75 of clock before the fix, with a worst gap of 876
     ms after it until the relayout's own loops stepped the music too.

  7. THE RESOLUTION CUTS IN AND HANDS BACK (SPEC.md 97.10.6). Each option
     is cut into a faction theme at a different point by `R`, is the model
     tick for tick, and `R` again plays its tail and hands back - and the
     theme must RESUME at the order row and row it was cut at, the model
     sought there, tick for tick. Resuming from the theme's top instead
     fails every option. Recorded, each option cuts into all three themes.

Broken on purpose before it was registered: a gate that starts counting on
the note-on tick (every note one tick short) fails every song's samples; the
speaker's macro step off by one fails the command stream - and PASSED the
samples, a one-tick scoop being what a sample a second apart sees one time in
eight, which is why the stream is here. The groove's index never advancing
failed NOTHING while every song had a one-step groove, and said so; the
Bulwark's Tollkeeper swings (3 then 2 ticks), and now it fails that song's
samples and its speaker gating both.

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
        "tm_sel", "ti_nframe", "tm_busy", "tm_tone", "tm_last",
        "tm_gapmax", "tm_rsel", "tm_resing", "tm_theme", "tm_bord", "tm_brow",
        "tm_state", "tm_tbuf")
TM_LATE = 3                                     # ticks: a note's worst lateness
FM_CELL = os88marty.KERNEL_SEG * 16 + 0x00F8    # OSAPI_SND_FM's cell
STREAM = {"spk": 80, "fm": 240}                 # calls of song 0 compared
MACHINES = (("os8088_5150_herc_sb_gla", "fm"), ("os8088_5150_herc_gla", "spk"))
SAMPLES = 6                         # a song, a guest second apart
fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % (got,)))
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

        def stepped(sq, T):
            for _ in range(T):
                sq.step()
            return sq

        def quiesce():
            """PAUSE the machine between two ticks; tm_ticks. Left paused."""
            m.pause()
            ticks = m.sym("ticks")
            for _ in range(50):         # never read a tick half-stepped, nor
                if not rb("tm_busy")[0] and \
                        bytes(m.read(ticks, 2)) == rb("tm_last", 2):
                    break               # one the timer has begun and the
                                        # worker not yet stepped (item 2)
                m.run()
                os88marty.guest_sleep(m, 0.003)
                m.pause()
            return rw("tm_ticks")

        def sample(model_of, bad, spk_bad):
            """The machine PAUSED between ticks, against model_of(tm_ticks)."""
            T = quiesce()
            chs = rb("tm_ch", 4 * 12)
            ordr, row = rb("tm_ord")[0], rb("tm_row")[0]
            gate61 = m.inb(0x61) & 3 if want_arm == "spk" else None
            m.run()
            sq = model_of(T)
            model = [c.note for c in sq.ch]
            guest = [chs[12 * c + 3] for c in range(4)]
            if want_arm == "spk":       # ...and the lead's FREQUENCY, which is
                model.append(sq.ch[0].last_f)           # where the macro and
                guest.append(chs[10] | chs[11] << 8)    # the vibrato live
            if (model, sq.ord, sq.row) != (guest, ordr, row):
                bad.append("T=%d guest ord %d row %d %s, model ord %d row %d %s"
                           % (T, ordr, row, guest, sq.ord, sq.row, model))
            if gate61 is not None and (gate61 == 3) != bool(model[0]):
                spk_bad.append("T=%d 61h&3=%d lead %d" % (T, gate61, model[0]))

        def to_song(si):
            for _ in range(nsong + 2):
                if rb("tm_sel")[0] == si:
                    break
                m.key("KeyM")
                os88marty.guest_sleep(m, 0.3)
            os88marty.guest_sleep(m, 0.3)

        def resolutions():
            """Item 7: THE RESOLUTION CUTS IN AND HANDS BACK (TITHE-PLAN
            13.4.1). Each option cuts into a different faction theme at a
            different point; the piece is the model tick for tick; `R` again
            plays its tail and the theme RESUMES AT THE ROW IT WAS CUT AT -
            the model sought to the banked order row and row, tick for tick."""
            themes = [tm.SONGS.index(f) for f in
                      ("bulsteadfast.tmu", "emberkindle.tmu", "covinter.tmu")]
            plan = [(r, themes[r % len(themes)]) for r in range(len(tm.RESOLUTIONS))]
            if record:                  # ...and recorded, every option into
                plan = [(r, th) for r in range(len(tm.RESOLUTIONS))  # every
                        for th in themes]                            # theme
            tour = None
            for r, th in plan:
                ri = nsong + r
                rid = tm.RESOLUTIONS[r][:-4]
                to_song(th)
                os88marty.guest_sleep(m, (6.0 if record else 2.5) + 0.7 * r)
                for _ in range(len(tm.RESOLUTIONS) + 1):
                    if rb("tm_rsel")[0] == r:
                        break
                    m.key("KeyE")
                    os88marty.guest_sleep(m, 0.2)
                t0 = gsecs() - (5.0 if record else 0.0)
                if tour is None or tour[0] != r:
                    tour = (r, t0)
                m.key("KeyR")
                os88marty.guest_sleep(m, 0.4)
                ok = (rb("tm_resing")[0], rb("tm_song")[0], rb("tm_theme")[0]) \
                    == (1, ri, th)
                check(ok, "%s: R cuts %s into %s" % (mach, rid, tm.SONGS[th][:-4]),
                      (rb("tm_resing")[0], rb("tm_song")[0], rb("tm_theme")[0]))
                if not ok:
                    continue
                bord, brow = rb("tm_bord")[0], rb("tm_brow")[0]
                bad, spk_bad = [], []
                for _ in range(3):
                    os88marty.guest_sleep(m, 0.9)
                    sample(lambda T: stepped(tm.Seq(part, ri, want_arm), T),
                           bad, spk_bad)
                check(not bad and not spk_bad,
                      "...the resolution is the model tick for tick", (bad + spk_bad)[:2])
                if record:
                    os88marty.guest_sleep(m, 3.0)
                st = 1 + r % 2          # the round's evaluation turned the
                m.write(seg * 16 + off["tm_state"], bytes([st]))    # state
                m.key("KeyR")
                back = False
                for _ in range(60):
                    os88marty.guest_sleep(m, 0.25)
                    if not rb("tm_resing")[0] and rb("tm_song")[0] == th:
                        back = True
                        break
                check(back, "...R again: the tail, then %s is back"
                      % tm.SONGS[th][:-4], (rb("tm_resing")[0], rb("tm_song")[0]))
                if not back:
                    continue

                def resumed(T, th=th, bord=bord, brow=brow, st=st):
                    sq = tm.Seq(part, th, want_arm, state=st)
                    sq.seek(bord, brow)
                    return stepped(sq, T - tm.row_ticks(
                        sq.groove[:sq.glen], sq.rows)[brow])
                bad, spk_bad = [], []
                for _ in range(3):
                    os88marty.guest_sleep(m, 0.9)
                    sample(resumed, bad, spk_bad)
                check(not bad and not spk_bad,
                      "...RESUMED at the row it was cut at (order %d, row %d), "
                      "in the state the round turned it to (%d), tick for tick"
                      % (bord, brow, st), (bad + spk_bad)[:2])
                m.write(seg * 16 + off["tm_state"], b"\0")
                if record:
                    os88marty.guest_sleep(m, 5.0)
                    if th == themes[-1]:    # one recording an option: its cut
                        marks.append((mach, want_arm, "cut-%s" % rid,  # into
                                      tour[1], gsecs()))  # all three themes

        def states():
            """Item 8: THE BATTLE STATES (TITHE-PLAN 13.4). `T` steps the
            state and the title names it; a state written mid-pattern turns
            the lead at the NEXT pattern boundary and nothing else, the model
            switched at the same tick, tick for tick across the boundary."""
            themes = [si for si in range(nsong)
                      if tm.Seq(part, si, want_arm).states > 1]
            check(len(themes) == 3, "%s: three themes have battle states"
                  % mach, themes)
            to_song(themes[0])
            os88marty.guest_sleep(m, 0.5)
            for want, word in ((1, "(pressed)"), (2, "(ascendant)"),
                               (0, "(normal)")):
                m.key("KeyT")
                os88marty.guest_sleep(m, 0.4)
                title = rb("tm_tbuf", 80).split(b"\0")[0].decode("latin-1")
                check(rb("tm_state")[0] == want and word in title,
                      "...T: state %d, and the title says %s" % (want, word),
                      (rb("tm_state")[0], title))
            for th in themes:
                to_song(th)
                t0 = gsecs()
                one = tm.Seq(part, th, want_arm).song_ticks() / tm.TICK_HZ
                sw = []
                for st in (1, 2):
                    os88marty.guest_sleep(m, one if record else 1.2)
                    T1 = quiesce()
                    m.write(seg * 16 + off["tm_state"], bytes([st]))
                    m.run()
                    sw.append((T1, st))

                    def model(T, sw=tuple(sw), th=th):
                        sq, t = tm.Seq(part, th, want_arm), 0
                        for at, s2 in sw:
                            stepped(sq, at - t)
                            sq.state, t = s2, at
                        return stepped(sq, T - t)
                    bad, spk_bad = [], []
                    for _ in range(4):
                        os88marty.guest_sleep(m, 1.5)
                        sample(model, bad, spk_bad)
                    check(not bad and not spk_bad,
                          "...%s turned to state %d at tick %d: the model "
                          "switched there, tick for tick across the boundary"
                          % (tm.SONGS[th][:-4], st, T1), (bad + spk_bad)[:2])
                if record:
                    os88marty.guest_sleep(m, max(0.0, one - 6.0))
                    marks.append((mach, want_arm,
                                  "states-%s" % tm.SONGS[th][:-4], t0, gsecs()))
                m.write(seg * 16 + off["tm_state"], b"\0")

        def tempo():
            """Item 6: THE TEMPO IS THE CLOCK'S, not the frame's. `G` rebuilds
            the board on the UI task with the gfx lock held for seconds - the
            worker is blocked on that lock the whole time - and the song must
            still advance one tick a tick, never more than TM_LATE late."""
            war, toll, charge = (tm.RESOLUTIONS.index(f) for f in
                                 ("reswar.tmu", "restoll.tmu", "rescharge.tmu"))
            for _ in range(len(tm.RESOLUTIONS) + 1):    # a resolution NO
                if rb("tm_rsel")[0] == war:             # board has, so the
                    break                               # G below must MOVE it
                m.key("KeyE")
                os88marty.guest_sleep(m, 0.2)
            ticks = m.sym("ticks")
            m.write(seg * 16 + off["tm_gapmax"], b"\0\0")
            k0, t0, f0 = (struct.unpack("<H", bytes(m.read(ticks, 2)))[0],
                          rw("tm_ticks"), rw("ti_nframe"))
            g0 = gsecs()
            m.key("KeyG")
            os88marty.guest_sleep(m, 5.0)
            k1, t1, f1 = (struct.unpack("<H", bytes(m.read(ticks, 2)))[0],
                          rw("tm_ticks"), rw("ti_nframe"))
            dk, dt = (k1 - k0) & 0xFFFF, (t1 - t0) & 0xFFFF
            fr = ((f1 - f0) & 0xFFFF) / max(0.1, gsecs() - g0)
            # the row's premise - a second of the five stalled at least - and
            # RELATIVE to the quiet rate: a fixed 12.0 read 11.8 to 12.04 once
            # wave 3's relayout got cheaper, while no stall at all reads ~18.5
            check(fr < quiet * 0.8, "...a relayout stalls the frame: %.1f "
                  "passes/s over it against %.1f quiet" % (fr, quiet), fr)
            check(abs(dk - dt) <= 2,
                  "...and the song keeps the CLOCK's time through it: %d ticks "
                  "of song in %d of clock" % (dt, dk), (dt, dk))
            gap = rw("tm_gapmax")
            check(gap <= TM_LATE, "...and no step came more than %d ticks "
                  "late (worst %d)" % (TM_LATE, gap), gap)
            check(rb("tm_rsel")[0] == toll, "...and THE CLOISTER's resolution "
                  "is The Toll (SPEC.md 97.10.7)", rb("tm_rsel")[0])
            m.key("KeyG")               # ...and the board it was, back
            os88marty.guest_sleep(m, 5.0)
            check(rb("tm_rsel")[0] == charge, "...and THE MARCH's is The Charge",
                  rb("tm_rsel")[0])

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
                n += 1
                sample(lambda T: stepped(tm.Seq(part, si, want_arm), T),
                       bad, spk_bad)
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
                tempo()
            if record:
                one = tm.Seq(part, si, want_arm).song_ticks() / tm.TICK_HZ
                os88marty.guest_sleep(m, max(0.0, one + 2.0 - SAMPLES - 0.5))
            marks.append((mach, want_arm, name, t0, gsecs()))
        resolutions()
        states()
        to_song(nsong - 1)
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
            m.key("KeyS")               # ...and back to FM
            os88marty.guest_sleep(m, 0.5)
            check(rb("tm_arm")[0] == 1, "...and S again puts it back on FM",
                  rb("tm_arm")[0])
            # THE CONTROL PANEL'S "PC speaker" (SPEC.md 34.8) is the TONE
            # ROUTE and leaves the card's FM published, so the caps word alone
            # still says FM: the byte the Sound page writes, then a restart
            route = m.sym("snd_route")
            was = bytes(m.read(route, 1))
            m.write(route, bytes([1]))  # SND_RT_SPK
            m.key("KeyS")
            os88marty.guest_sleep(m, 0.3)
            m.key("KeyS")               # S twice: the song restarts, S off
            os88marty.guest_sleep(m, 0.5)
            check(rb("tm_song")[0] == 0 and rb("tm_arm")[0] == 0,
                  "...and the Control Panel's PC speaker route takes the "
                  "speaker arm though FM is there", rb("tm_arm")[0])
            m.write(route, was)


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
    nsong = len(tm.SONGS)               # `M`'s; the resolutions follow them
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
