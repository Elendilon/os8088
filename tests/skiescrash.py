#!/usr/bin/env python3
"""THE WINDSHIELD IS DRAWN WHOLE (SPEC.md 88.7.11.1).

    python3 tests/skiescrash.py [--machine os8088_5150_herc_gla]

A crash freezes the picture and draws eight cracks over it for CS_CRASHT
ticks. Reported from the air, on Hercules: the UPPER part of the view is wrong
after a crash.

It is 88.13.3.1's rule, applied one caller short. cs_seg reads three words to
decide what a segment owes the glass, and cs_crackle runs AFTER cs_scene, so
all three hold the LAST OBJECT DRAWN's values: cs_pinview would skip the clip,
cs_pwhole would skip the marking outright, and cs_markacc would accumulate
into an object box cs_drawobj flushed a moment ago and resets for its first
object next frame. Either way the marks are lost, and an unmarked run never
reaches the glass (88.3.1). The horizon and the panel (cs_pclip) both take all
three stores; cs_crackle took only cs_pinview.

WHAT THAT LOOKS LIKE is a windshield with a hole in it: a crack appears
wherever SOMETHING ELSE marked the row - the ground, a building, the horizon
segment - and nowhere else. Over open sky, which on Hercules is the top of the
view and is black, nothing marks a row and the cracks up there were never
drawn at all. The star and the ring stop dead at the horizon.

The row pins 300 m over Paris with the nose down, so the view has real sky
above a real city below, crashes the aeroplane where it stands, and counts
what the crash ADDS to each half:

  1. the crash reaches the glass at all - so a row that poked a state byte
     and photographed two identical frames would not pass;
  2. and it reaches THE SKY, above the horizon the guest itself reports in
     cs_hzy0. That is the check the defect fails;
--clobber-crash is the red run (docs/WRITING-TESTS.md 1): it NOPs the two
stores the fix added and the one that puts the borrow back, which is
cs_crackle exactly as it shipped, and CHECK 2 must go red. It reads 129 lit
sky pixels against 0.

WHAT THIS ROW DELIBERATELY DOES NOT ASK is whether a crack OUTLIVES the crash.
It was tried - photograph the pose, crash, wait, re-pin, photograph again -
and it reads the same 1,622 differing pixels on BOTH arms, so it is measuring
the harness and not the code. cs_hzrows is incremental (a row whose kind has
not changed and whose last span was empty is left alone), so a teleport leaves
the view partly stale by itself; and the poke that makes a capture
deterministic - cs_rowkind to 0x83 and both span sets empty, which is
cs_clearall by hand - forces a full refill and would erase exactly the leftover
such a check is looking for. The two cannot both be had, and a check that
fails identically with the fix and without it is a check about the test.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88ui                                               # noqa: E402
import dispapps                                             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS_ST_CRASH = 2
bad = []


def check(cond, what):
    print("  [%s] %s" % ("PASS" if cond else "FAIL", what))
    if not cond:
        bad.append(what)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    ap.add_argument("--clobber-crash", action="store_true",
                    help="cs_crackle marks nothing again: check 2 goes red")
    ap.add_argument("--shot", help="write the three pictures here, as a stem")
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

        def poke(n, d):
            m.write(lin + base + off(n), d)

        def word(n):
            v = int.from_bytes(m.read(lin + base + off(n), 2), "little")
            return v - 65536 if v >= 32768 else v

        def byte(n):
            return m.readseg(seg, base + off(n), 1)[0]

        m.advance(frames=40)
        m.run()
        m.type_text("f")
        m.advance(frames=100)
        m.run()

        def guest_frames(n, cap=40):
            """Advance until the GUEST has drawn n more frames. m.advance
            counts the emulator's, and a Clear Skies frame on a 4.77 MHz 8088
            is 150-280 ms of them, so a fixed count is a guess that reads
            differently on every scene."""
            want = word("cs_frames") + n
            for _ in range(cap):
                m.advance(frames=30)
                m.run()
                if word("cs_frames") >= want:
                    return True
            return False

        if a.clobber_crash:
            # cs_crackle's `mov byte [cs_pwhole],0` and `mov byte
            # [cs_ownmk],-1`, and the `mov byte [cs_ownmk],0` that puts the
            # borrow back: fifteen bytes of NOP is the routine as it shipped.
            lo, hi = mp["cs_crackle"], mp["cs_crx"]
            code = m.read(lin + lo, hi - lo)
            pats = [b"\xC6\x06" + (base + off(n)).to_bytes(2, "little") + v
                    for n, v in (("cs_pwhole", b"\x00"), ("cs_ownmk", b"\xFF"),
                                 ("cs_ownmk", b"\x00"))]
            m.pause()
            for p in pats:
                i = code.find(p)
                if i < 0:
                    sys.exit("skiescrash: cs_crackle does not take the three "
                             "stores the way this patch expects - re-read it "
                             "before trusting the red run")
                m.write(lin + lo + i, b"\x90" * 5)
            m.run()
            print("  (cs_crackle marking nothing again: check 2 must fail)")

        def shot():
            m.pause()
            w, h, data = m.fbuf(0)
            m.run()
            return w, h, data

        def rows(w, h, data):
            """(the view's first screen row, its height) - found off the
            PANEL's own full-width rule, because where the view sits on the
            glass is the backend's business and not a number to mirror."""
            lit = [sum(1 for x in range(w) if data[(y * w + x) * 3] > 128)
                   for y in range(h)]
            top = min(y for y in range(h) if lit[y] > w * 0.5)
            return top - word("cs_wh"), word("cs_wh")

        def count(w, h, data, y0, y1):
            return sum(1 for y in range(y0, y1) for x in range(w)
                       if data[(y * w + x) * 3] > 128)

        # --- 300 m over Paris, nose down: real sky over a real city --------
        m.pause()
        for n, v in (("cs_px", 150), ("cs_py", 300), ("cs_pz", -900)):
            poke(n, ((v * 256) & 0xFFFFFFFF).to_bytes(4, "little"))
        for n, v in (("cs_hdg", 30), ("cs_pitch", -5), ("cs_roll", 0)):
            poke(n, ((v * 65536 // 360) & 0xFFFF).to_bytes(2, "little"))
        poke("cs_state", b"\x01")
        poke("cs_pause", b"\x01")
        port = word("cs_airport") & 0xFFFF   # a poke is a TELEPORT (88.5.2)
        objs = int.from_bytes(m.read(lin + port + 18, 2), "little")
        nobj = int.from_bytes(m.read(lin + port + 20, 2), "little")
        for o in range(objs, objs + nobj * 20, 20):
            m.write(lin + o + 18, b"\x00\x00")
        m.run()
        guest_frames(6)
        w, h, before = shot()
        v0, vh = rows(w, h, before)
        sky = word("cs_hzy0")               # the horizon's own top row
        if not 4 <= sky <= vh - 4:
            sys.exit("skiescrash: the pinned pose has no sky over a horizon "
                     "(cs_hzy0 = %d of %d rows)" % (sky, vh))
        b_all = count(w, h, before, v0, v0 + vh)
        b_sky = count(w, h, before, v0, v0 + sky)

        # --- crash it where it stands. The crash state freezes the world -
        # cs_step does nothing but count the picture down - so nothing moves
        # while it runs, and cs_pause has to come off for it to run at all.
        m.pause()
        poke("cs_state", bytes([CS_ST_CRASH]))
        poke("cs_crasht", (36).to_bytes(2, "little"))
        poke("cs_pause", b"\x00")
        m.run()
        guest_frames(2)
        w2, h2, during = shot()
        d_all = count(w2, h2, during, v0, v0 + vh)
        d_sky = count(w2, h2, during, v0, v0 + sky)

        check(d_all - b_all >= 200,
              "the crash REACHES THE GLASS: %d lit pixels in the view against "
              "%d before it (want 200 more at least)" % (d_all, b_all))
        check(d_sky - b_sky >= 40,
              "...and it reaches THE SKY, above the horizon the guest puts at "
              "row %d: %d lit pixels there against %d before the crash (want "
              "40 more at least - the cracks up there were the half that was "
              "never drawn)" % (sky, d_sky, b_sky))

        # --- and let it end, so the row leaves a machine that is flying
        # rather than one frozen in a crash
        for _ in range(40):
            m.advance(frames=30)
            m.run()
            if byte("cs_state") != CS_ST_CRASH:
                break
        if byte("cs_state") == CS_ST_CRASH:
            sys.exit("skiescrash: the crash never ended (%d ticks left)"
                     % word("cs_crasht"))
        guest_frames(4)
        if a.shot:
            import os88marty
            w3, h3, after = shot()
            for nm, (ww, hh, d) in (("before", (w, h, before)),
                                    ("during", (w2, h2, during)),
                                    ("after", (w3, h3, after))):
                os88marty.write_png_rgb("%s-%s.png" % (a.shot, nm), ww, hh, d)

    print("skiescrash: %s" % ("ok" if not bad else "FAILED %d" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
