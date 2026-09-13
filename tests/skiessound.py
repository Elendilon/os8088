#!/usr/bin/env python3
"""AN ENGINE EACH (SPEC.md 88.8.2), on MartyPC.

    python3 tests/skiessound.py [--machine os8088_5150_herc_gla]

Every aeroplane used to make the same noise - `[cs_thr] + 50`, so a Fouga
Magister and an Icon A5 were the same note at the same lever. Each one reads
its own engine record now, and this asks the guest what it is actually
playing rather than what the table says it should:

  1. every powered aeroplane's tone is its OWN record's law at three lever
     positions - idle, half and full - read off `[cs_tone]` on the machine
     and computed on the host from the record the guest holds;
  2. the four of them are FOUR DIFFERENT NOTES at full power, which is the
     whole of the ask and the one check a shared record cannot pass;
  3. a SHUT THROTTLE IS AN IDLE and not silence, which is the change that
     does most of the work: an engine that is running is never silent;
  4. the WASSMER BIJAVE plays nothing at any lever position - it has no
     engine record, and 88.7.6.1 gave it that silence long before this;
  5. the BEAT drops the note on the ticks its mask selects and leaves it
     alone on the others, so a piston's roughness is there and a turbine's
     note is flat. Sampled over sixteen consecutive ticks, a beating engine
     reads exactly two values and a smooth one reads exactly one;
  6. the FOUGA'S NOTE LAGS THE HAND. Its record sets CSSF_SPOOL, so it
     follows the thrust the engine HAS (88.7.5) and not the lever: the
     throttle goes to full in one tick and the note is still CLIMBING many
     ticks later, where a piston arrives inside one.

Two red runs (docs/WRITING-TESTS.md 1). --clobber-shared points every plane
at the Cessna's record: check 2 goes red because five aeroplanes are then one
note, check 6 because a jet reading the lever arrives at once, and the
record-versus-thrust rule because the sailplane is holding an engine. Check 1
stays GREEN in that arm and is meant to - it asks whether each aeroplane plays
the record it HOLDS, and under the clobber they all honestly do, which is
exactly why check 2 has to exist separately. --clobber-spool clears the
Magister's CSSF_SPOOL so it reads the lever like everything else, and 6 goes
red on its own while every other check stays green: the jet still has its own
NUMBERS, it has just stopped lagging, which is the mechanic it is here for.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88ui                                               # noqa: E402
import dispapps                                             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILED = []


def _equates():
    """The record offsets, READ OUT of skies.asm - skiesfleet.py's rule."""
    out = {}
    for line in open(os.path.join(ROOT, "apps", "skies", "skies.asm")):
        m = re.match(r"^(CS[A-Z]*_[A-Z0-9_]+)\s+equ\s+"
                     r"(-?(?:0[xX][0-9A-Fa-f]+|\d+))\s*(?:;|$)", line)
        if m:
            out[m.group(1)] = int(m.group(2), 0)
    return out


E = _equates()
_WANT = "CSP_SND CSP_THRUST CSS_IDLE CSS_SPAN CSS_BEAT CSS_MASK CSS_FLAGS " \
        "CSSF_SPOOL".split()
_missing = [k for k in _WANT if k not in E]
if _missing:
    sys.exit("skiessound: skies.asm no longer declares %s" % ", ".join(_missing))


def check(cond, what):
    print("%s  %s" % ("ok  " if cond else "FAIL", what))
    if not cond:
        FAILED.append(what)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    ap.add_argument("--clobber-shared", action="store_true",
                    help="give every aeroplane the Cessna's engine: red")
    ap.add_argument("--clobber-spool", action="store_true",
                    help="make the Magister read the lever: red")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    mp = dispapps._map("skies")

    def off(n):
        return dispapps.bss_off("skies", n)

    with os88ui.boot(a.image, apps=a.apps, machine=a.machine) as ui:
        m = ui.m
        ui.path("B:/GAMES/SKIES.O88")
        slot, seg = dispapps.pkg_seg(m, 0)
        lin = seg << 4
        base = int.from_bytes(m.readseg(seg, 8, 2), "little")

        def w(n):
            return int.from_bytes(m.readseg(seg, base + off(n), 2), "little")

        def byte(n):
            return m.readseg(seg, base + off(n), 1)[0]

        def poke(n, d):
            m.write(lin + base + off(n), d)

        def rec(at, o):
            return int.from_bytes(m.readseg(seg, at + o, 2), "little")

        def recb(at, o):
            return m.readseg(seg, at + o, 1)[0]

        def name(at):
            return m.readseg(seg, rec(at, 0), 24).split(b"\0")[0].decode()

        def dropbox():
            """The Plane drop-down's box, WAITED FOR rather than read once.

            `cs_drplane`'s clip is filled in when the title page arms the
            control, and reading it the instant the package is launched
            answers (0, 168, 335, 183) - a box whose centre is 167, which is
            41 pixels left of the real one at 208. Every click then misses
            and the row that is picked is the row that was already picked,
            which reads exactly like a drop-down that does not work.
            """
            for _ in range(20):
                p = [rec(mp["cs_drplane"], 2 * i) for i in range(4)]
                if p[0]:
                    return p
                m.advance(frames=20)
                m.run()
            sys.exit("skiessound: the Plane list never armed its clip")

        def inbracket():
            """SPEC.md 88.10.5's own predicate, and it is a PAIR.

            `[cs_back]` is the mode the bracket took and is never cleared on
            the way out, so it answers "has this program ever flown", not
            "is it flying". `[cs_quit]` is what the F key sets and what the
            loop leaves on.
            """
            return byte("cs_back") != 0 and byte("cs_quit") == 0

        if a.clobber_shared:
            # every aeroplane gets the Cessna's engine, the sailplane too
            src = rec(mp["cs_planes"], 0)
            snd = rec(src, E["CSP_SND"])
            for i in range(5):
                p = rec(mp["cs_planes"], 2 * i)
                m.write(lin + p + E["CSP_SND"], snd.to_bytes(2, "little"))
        if a.clobber_spool:
            jet = rec(mp["cs_planes"], 4)
            s = rec(jet, E["CSP_SND"])
            m.write(lin + s + E["CSS_FLAGS"], b"\x00")

        def leave():
            """Out of the bracket and back to the title page, CONFIRMED.

            `F TOGGLES` (88.10.5), so this asks ONCE and then WAITS: a
            second `f` typed while the first is still being acted on walks
            straight back into the bracket. What it waits ON is `inbracket()`
            and NOT `[cs_back]` alone - 88.10.5 is explicit that cs_back is
            the mode the bracket took and is NEVER CLEARED on the way out, so
            a loop polling it for zero waits for ever. A frame count would
            not do either: a mode restore is not a fixed number of frames,
            and a crash (88.7) holds the picture for CS_CRASHT ticks with the
            key going nowhere.
            """
            if not inbracket():
                return
            m.type_text("f")                    # ONCE: F TOGGLES
            for _ in range(20):
                m.advance(frames=40)
                m.run()
                if not inbracket():
                    m.advance(frames=60)        # ...and let the mode restore
                    m.run()                     # finish before the next click
                    return
            sys.exit("skiessound: the bracket would not close")

        def fly(row):
            """Pick row `row`, enter the bracket; out: its plane record."""
            leave()
            want = rec(mp["cs_planes"], 2 * row)
            for _ in range(3):
                po = dropbox()
                ui.mo.click((po[0] + po[2]) // 2, (po[1] + po[3]) // 2)
                m.advance(frames=25)
                m.run()
                # THE OPEN LIST'S OWN TOP, read back out of the control
                # (tests/skiesadi.py's spelling), not derived from the closed
                # box's bottom edge: a computed one picks the wrong row.
                top = rec(mp["cs_drplane"], 22)
                ui.mo.click(po[0] + 20, top + 1 + 12 * row + 6)
                m.advance(frames=25)
                m.run()
                if w("cs_plane") == want:
                    break
            got = w("cs_plane")
            if got != want:
                sys.exit("skiessound: row %d picked %04x, wanted %04x"
                         % (row, got, want))
            # ...and ENTERING is polled for leave()'s reason, one direction
            # along: `f` is typed ONCE because it toggles, and what follows
            # is a wait rather than a frame count. cs_cmd_fly reads the
            # picked location's world off the floppy (88.10.5), so the first
            # flight into a world is a disk transfer and not a repaint.
            m.type_text("f")
            for _ in range(20):
                m.advance(frames=40)
                m.run()
                if inbracket():
                    return got
            sys.exit("skiessound: row %d took no mode" % row)

        def tones(plane, thr, nn=16, spool=True):
            """(note, thrust) over nn consecutive ticks at throttle `thr`.

            The aeroplane is held in the AIR and the lever re-pinned on every
            tick, so nothing the ground model does to the throttle (the brake
            closes it, 88.7.10) can reach the reading. SPOOL is pinned with
            it unless the caller is measuring the lag itself.

            IT RETURNS THE THRUST AS WELL AS THE NOTE, and it has to: a
            spooled engine's note is computed from `[cs_thracc]`, which
            `cs_step` moves every tick and which does NOT settle on the
            lever's own percentage - the target is `thr x CSP_THRUST / 100`
            in WHOLE units before it is shifted into 8.8, so 50% of a
            19-unit engine is 9 and not 9.5. Both are read at the same stop,
            which is the one moment they are the pair that made the note:
            cs_sound_step ran at the end of the previous tick and nothing
            between there and here touches either.
            """
            full = rec(plane, E["CSP_THRUST"]) << 8
            out = []
            m.bp_exec(lin + mp["cs_step"])
            m.run()
            if m.wait_stop(30) is None:
                sys.exit("skiessound: cs_step never ran")
            for i in range(nn + 1):
                if i:
                    out.append((w("cs_tone"), w("cs_thracc")))
                poke("cs_py", (600 * 256).to_bytes(4, "little"))
                poke("cs_thr", thr.to_bytes(2, "little"))
                if spool:
                    poke("cs_thracc",
                         (full * thr // 100).to_bytes(2, "little"))
                m.run()
                if m.wait_stop(30) is None:
                    sys.exit("skiessound: cs_step never ran")
            m.bp_exec()
            m.run()
            return out

        def law(snd, plane, thr, thracc):
            """What 88.8.2 says the note is, off the GUEST's own record.

            Hz = CSS_IDLE + source x CSS_SPAN / 100, and the SOURCE is the
            lever unless CSSF_SPOOL says it is the thrust the engine has.
            """
            src = thr
            if recb(snd, E["CSS_FLAGS"]) & E["CSSF_SPOOL"]:
                full = rec(plane, E["CSP_THRUST"]) << 8
                src = thracc * 100 // full
            return (rec(snd, E["CSS_IDLE"])
                    + src * rec(snd, E["CSS_SPAN"]) // 100)

        # --- 1, 3, 5: each aeroplane's own law, its idle, and its beat ------
        full_notes = {}
        for row in range(5):
            plane = fly(row)
            nm = name(plane)
            snd = rec(plane, E["CSP_SND"])

            # AN AEROPLANE HAS AN ENGINE RECORD IF AND ONLY IF IT HAS THRUST,
            # which is the whole rule and the one the fleet has to keep as it
            # grows. It is checked per row rather than as a count so a future
            # sixth aeroplane is covered by arriving.
            check((snd != 0) == (rec(plane, E["CSP_THRUST"]) != 0),
                  "%s: CSP_SND is %s and CSP_THRUST is %d - an aeroplane has "
                  "an engine record exactly when it has an engine"
                  % (nm, "set" if snd else "0",
                     rec(plane, E["CSP_THRUST"])))

            if snd == 0:                        # --- 4: the sailplane -------
                quiet = all(t == 0 for thr in (0, 50, 100)
                            for t, _ in tones(plane, thr, nn=4))
                check(quiet, "%s has no engine record and plays NOTHING at "
                             "any lever position (88.7.6.1)" % nm)
                continue

            beat = recb(snd, E["CSS_BEAT"])
            for thr in (0, 50, 100):
                seq = tones(plane, thr)
                # EVERY SAMPLE against the law for the thrust THAT sample was
                # made at, because a spooled engine's source moves under the
                # reading. A beat may only ever take the note DOWN, and by
                # exactly CSS_BEAT.
                bad = [(t, law(snd, plane, thr, ta)) for t, ta in seq
                       if t not in (law(snd, plane, thr, ta),
                                    law(snd, plane, thr, ta) - beat)]
                want = law(snd, plane, thr, seq[-1][1])
                check(not bad,
                      "%s at throttle %3d: %s Hz, and its record's law says "
                      "%d%s" % (nm, thr, sorted({t for t, _ in seq}), want,
                                " with a %d Hz beat" % beat if beat
                                else " flat"))
                if thr == 100:
                    full_notes[nm] = want
                if thr == 0:
                    check(want > 0, "%s IDLES at %d Hz rather than falling "
                                    "silent (88.8.2)" % (nm, want))
            # 5: a beating engine reads exactly two values over sixteen ticks
            # and a smooth one exactly one. This is the beat's own check, and
            # it is why the note is sampled over a run of ticks at all.
            got = {t for t, _ in tones(plane, 100)}
            check(len(got) == (2 if beat else 1),
                  "%s reads %d distinct note(s) over 16 ticks, which is what "
                  "a %s engine should" % (nm, len(got),
                                          "beating" if beat else "smooth"))

        # --- 2: four engines, four notes ------------------------------------
        check(len(set(full_notes.values())) == len(full_notes),
              "the four powered aeroplanes are four DIFFERENT notes at full "
              "power: %s" % ", ".join("%s %d Hz" % (k, v)
                                      for k, v in sorted(full_notes.items(),
                                                         key=lambda x: x[1])))

        # --- 6: the jet's note LAGS THE HAND --------------------------------
        # CSP_SPOOL is 5 - a 32nd of the gap a tick, 95% in 5.3 seconds - so
        # the lever goes to full in one tick and the note does not. A piston
        # arrives inside one tick, which is the control this check needs: the
        # assertion is not "it rises", it is "it is STILL rising later".
        for row, want_lag in ((2, True), (0, False)):
            plane = fly(row)
            nm = name(plane)
            snd = rec(plane, E["CSP_SND"])
            poke("cs_thracc", b"\x00\x00")
            seq = [t for t, _ in tones(plane, 100, nn=24, spool=False)]
            top = law(snd, plane, 100, rec(plane, E["CSP_THRUST"]) << 8)
            # ...and the floor a beating engine can sit at is the law LESS
            # its beat, which is what the Cessna reads on three ticks in four
            arrived = seq[2] >= top - recb(snd, E["CSS_BEAT"])
            climbing = seq[-1] > seq[8] > seq[2]
            if want_lag:
                check(climbing and not arrived,
                      "%s is STILL climbing 24 ticks after the lever moved "
                      "(%d -> %d -> %d Hz): it follows the thrust it HAS "
                      "(88.7.5)" % (nm, seq[2], seq[8], seq[-1]))
            else:
                check(arrived, "%s arrives inside three ticks (%d Hz of %d): "
                               "a piston's throttle IS its power"
                      % (nm, seq[2], top))

        leave()

    print("skiessound: %d check(s) failed" % len(FAILED) if FAILED
          else "skiessound: all checks passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
