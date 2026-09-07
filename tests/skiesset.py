#!/usr/bin/env python3
"""CLEAR SKIES' SETTINGS (SPEC.md 88.13): the page, and the four knobs on it
reaching the picture, on MartyPC.

    python3 tests/skiesset.py [--machine os8088_5150_herc_gla]

Every setting trades picture for frame rate, so every check here is about
one of the two: either the renderer does less work, or the glass shows
something different.

  1. Flight -> Settings opens the page and the painter writes all eight
     controls' rects (four drop-downs, three fill boxes, Done);
  2. picking Buildings = Few leaves fewer objects in the frame - cs_nvisn,
     which is what the cull filed - and the frame gets measurably shorter;
  3. a fill box toggles its bit in cs_setfill, and clearing all three leaves
     the wireframe: the ground's dither is gone from the glass;
  4. inside the bracket the hotkeys do the same things without the page -
     1/2/3 buildings, 4/5/6 fills, 7/8/9 detail, -/+ size;
  4b. the page's controls behave: a drop-down's list actually COMES DOWN
     (banked and on the glass, not merely marked open), and Done is drawn
     down on the press, cancels on a release off it and turns the page only
     on a release over it (88.13.6);
  5. and shrinking the view CLEARS THE PIXELS BESIDE IT. cs_clearall zeroes
     the shadow and the blit copies only the view's byte columns out of it,
     so without cs_scrclear the larger view's ground stands in a band either
     side of the smaller picture (88.13.4). That band is read out of VRAM
     and not out of the rendered frame - see the note at the check.

Three red runs (docs/WRITING-TESTS.md 1). --clobber-clear NOPs the call to
cs_scrclear, which is that band exactly, and check 5 must go red.
--clobber-drwin takes the page's drop-downs' OS88UI_DR_WIN away, which is
the defect exactly, and the bank and glass checks must go red - note that
the PICK still works without it, which is why those two checks exist.
--clobber-arm puts a ret on os88ui_arm so Done never arms, and the release
must then fail to turn the page.
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
CPS = 4772727
CSBL_FEW, CSBL_ALL = 0, 2
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
    ap.add_argument("--clobber-clear", action="store_true",
                    help="NOP the screen clear a size change owes: must go red")
    ap.add_argument("--clobber-drwin", action="store_true",
                    help="take the page's drop-downs' window handle away")
    ap.add_argument("--clobber-arm", action="store_true",
                    help="put a ret on os88ui_arm, so Done never arms")
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

        def rec(name, o):
            return int.from_bytes(m.readseg(seg, mp[name] + o, 2), "little")

        def rect(name):
            return [rec(name, 2 * i) for i in range(4)]

        m.advance(frames=30)
        m.run()
        if a.clobber_clear:
            lo, hi = mp["cs_hotkey"], mp["cs_hotkey"] + 0x120
            code = m.read(lin + lo, hi - lo)
            site = None
            for i in range(len(code) - 3):
                if code[i] == 0xE8:
                    r = int.from_bytes(code[i + 1:i + 3], "little")
                    r = r - 0x10000 if r >= 0x8000 else r
                    if lo + i + 3 + r == mp["cs_scrclear"]:
                        site = lo + i
                        break
            if site is None:
                sys.exit("skiesset: cs_hotkey does not call cs_scrclear")
            m.pause()
            m.write(lin + site, b"\x90\x90\x90")
            m.run()
            print("  (the size change's screen clear NOPed: this run must fail)")
        if a.clobber_drwin:
            m.pause()
            for i in range(4):
                at = int.from_bytes(m.readseg(seg, mp["cs_setdrops"] + 2 * i, 2),
                                    "little")
                m.write(lin + at + 14, b"\x00\x00")     # OS88UI_DR_WIN
            m.run()
            print("  (the page's drop-downs given no window: this run must fail)")
        if a.clobber_arm:
            m.pause()
            m.write(lin + mp["os88ui_arm"], b"\xC3")
            m.run()
            print("  (os88ui_arm is a ret: this run must fail)")

        # --- 1. the page and its controls ------------------------------------
        ui.menu_pick("Flight", "Settings")
        m.advance(frames=40)
        m.run()
        check(byte("cs_page") == 2, "Flight -> Settings turns to the page (%d)"
              % byte("cs_page"))
        names = ("cs_drbld", "cs_drlod", "cs_drsize", "cs_drmode",
                 "cs_ckgnd", "cs_ckwat", "cs_ckbld", "cs_donerect")
        rects = {n: rect(n) for n in names}
        wrote = [n for n in names if rects[n][2] > rects[n][0]]
        check(len(wrote) == 8, "the painter wrote all eight controls' rects (%d)"
              % len(wrote))

        def click(x, y, f=25):
            ui.mo.click(x, y)
            m.advance(frames=f)
            m.run()

        # --- 3. a fill box toggles its bit -----------------------------------
        for nm, bit, lbl in (("cs_ckgnd", 1, "Ground"), ("cs_ckwat", 2, "Water"),
                             ("cs_ckbld", 4, "Buildings")):
            r = rects[nm]
            was = byte("cs_setfill")
            click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)
            now = byte("cs_setfill")
            check(now == was & ~bit, "the %s box clears its fill bit (%d -> %d)"
                  % (lbl, was, now))
        check(byte("cs_setfill") == 0, "all three off is the wireframe (%d)"
              % byte("cs_setfill"))
        for nm in ("cs_ckgnd", "cs_ckwat", "cs_ckbld"):
            r = rects[nm]
            click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)
        check(byte("cs_setfill") == 7, "...and back on again (%d)"
              % byte("cs_setfill"))

        # --- 2. Buildings = Few, on the page ---------------------------------
        #
        # AND THE LIST HAS TO COME DOWN ON THE GLASS. The pick alone is not
        # the check: os88ui_drpress marks the record OPEN before it arms the
        # clip, so a record with no OS88UI_DR_WIN takes the press, draws
        # NOTHING, and the second click still lands on an item rect and picks
        # it - which is how this row passed while the page's four drop-downs
        # could not be dropped down at all (88.13.6). The proofs are the bank
        # (OS88UI_DR_SEG is non-zero only on the path that drew the list) and
        # the pixels under the box.
        r = rects["cs_drbld"]
        m.pause()
        _, _, was = m.vram()
        m.run()
        click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)
        drseg = int.from_bytes(m.readseg(seg, mp["cs_drbld"] + 18, 2), "little")
        check(m.readseg(seg, mp["cs_drbld"] + 16, 1)[0] == 1,
              "the press opens the Buildings list")
        check(drseg != 0,
              "...and it BANKED what it covered, which only the path that "
              "drew it does (%04x)" % drseg)
        m.pause()
        _, _, now = m.vram()
        m.run()
        # ...and WHERE it is drawn is OS88UI_DR_TOP (SPEC.md 13.14.2), not the
        # row under the box: a list too tall for the room below its control
        # slides UP into the window. The page's three-item lists all still fit
        # below theirs, so the two agree here - but reading the record is what
        # keeps this row true if a fourth item is ever added to one of them.
        top = int.from_bytes(m.readseg(seg, mp["cs_drbld"] + 22, 2), "little")
        drew = sum(sum(1 for x in range(r[0], r[2] + 1)
                       if was[y][x] != now[y][x])
                   for y in range(top, min(top + 38, len(was))))
        check(drew > 200, "...and the list is ON THE GLASS where os88ui_drfit "
                          "put it (%d pixels changed)" % drew)
        click(r[0] + 20, top + 1 + 6)               # the first item: Few
        check(byte("cs_setbld") == CSBL_FEW,
              "picking Few sets the buildings level (%d)" % byte("cs_setbld"))

        # --- 2b. Done is a BUTTON: down on the press, fired at the release --
        d = rects["cs_donerect"]
        cx, cy = (d[0] + d[2]) // 2, (d[1] + d[3]) // 2

        def press(x, y):
            ui.mo.to(x, y)
            ui.mo._edge(True)
            m.advance(frames=20)
            m.run()

        def release(x, y):
            ui.mo.to(x, y)
            ui.mo._edge(False)
            m.advance(frames=40)
            m.run()

        press(cx, cy)
        check(byte("cs_donedn") == 1, "Done is drawn DOWN while it is held")
        check(byte("cs_page") == 2, "...and the press alone does not turn the "
                                    "page (%d)" % byte("cs_page"))
        release(d[0] - 60, d[1] - 40)
        check(byte("cs_page") == 2 and byte("cs_donedn") == 0,
              "a release off the button is a cancel (page %d, down %d)"
              % (byte("cs_page"), byte("cs_donedn")))
        press(cx, cy)
        release(cx, cy)
        check(byte("cs_page") == 0,
              "...and pressed and released on it, Done turns the page (%d)"
              % byte("cs_page"))
        ui.menu_pick("Flight", "Settings")
        m.advance(frames=40)
        m.run()

        # --- into the bracket, where the work is measurable ------------------
        rd = mp["cs_render"]

        seen = {}

        def frames(n=6):
            """Milliseconds a frame, and what the cull filed - READ AT THE
            STOP, because cs_nvisn is zeroed at the top of every cs_scene and
            a read taken while the guest runs catches it part way up."""
            m.bp_exec(lin + rd)
            m.run()
            if m.wait_stop(30) is None:
                sys.exit("skiesset: cs_render never ran")
            c0 = m.status()["cycles"]
            out = []
            for _ in range(n):
                m.run()
                if m.wait_stop(30) is None:
                    sys.exit("skiesset: the frame never came")
                c1 = m.status()["cycles"]
                out.append((c1 - c0) / CPS * 1000.0)
                c0 = c1
            seen["n"] = w("cs_nvisn")
            m.bp_exec()
            m.run()
            return sum(out) / len(out)

        def pin():
            """Over the city, the world paused, every skip cleared."""
            m.pause()
            for nm, v in (("cs_px", 150), ("cs_py", 300), ("cs_pz", -900)):
                m.write(lin + base + off(nm), ((v * 256) & 0xFFFFFFFF).to_bytes(4, "little"))
            m.write(lin + base + off("cs_hdg"), (30 * 65536 // 360).to_bytes(2, "little"))
            m.write(lin + base + off("cs_pitch"),   # NOSE DOWN, so the view is
                    ((-20 * 65536 // 360) & 0xFFFF).to_bytes(2, "little"))
            m.write(lin + base + off("cs_state"), b"\x01")
            m.write(lin + base + off("cs_pause"), b"\x01")
            # THE WORLD IS THE PICKED LOCATION'S since SPEC.md 88.6.4, so the
            # skips to clear are the ones in the table its record names and
            # not a global cs_objtab, which no longer exists.
            ap = int.from_bytes(m.read(lin + base + off("cs_airport"), 2), "little")
            objs = int.from_bytes(m.read(lin + ap + 18, 2), "little")
            nobj = int.from_bytes(m.read(lin + ap + 20, 2), "little")
            for o in range(objs, objs + nobj * 20, 20):
                m.write(lin + o + 18, b"\x00\x00")
            m.run()

        m.type_text("f")                            # off the page first: any
        m.advance(frames=40)                        # key returns to the title
        m.run()
        check(byte("cs_page") == 0, "a key comes back from the page (%d)"
              % byte("cs_page"))
        m.type_text("f")
        m.advance(frames=80)
        m.run()
        check(byte("cs_back") != 0, "the bracket took a mode")
        pin()
        frames(3)
        few_ms = frames()
        few_n = seen["n"]
        m.type_text("3")                            # ...and 1/2/3 is Buildings
        m.advance(frames=40)
        m.run()
        pin()
        frames(3)
        all_ms = frames()
        all_n = seen["n"]
        check(byte("cs_setbld") == CSBL_ALL,
              "the 3 key puts every building back (%d)" % byte("cs_setbld"))
        check(few_n < all_n, "Few files fewer objects than Full (%d against %d)"
              % (few_n, all_n))
        check(few_ms < all_ms * 0.9,
              "...and its frame is shorter (%.1f ms against %.1f)" % (few_ms, all_ms))

        # --- 4. the other hotkeys --------------------------------------------
        for key, name, want in (("7", "cs_setlod", 0), ("9", "cs_setlod", 2),
                                ("8", "cs_setlod", 1), ("1", "cs_setbld", 0),
                                ("2", "cs_setbld", 1), ("3", "cs_setbld", 2)):
            m.type_text(key)
            m.advance(frames=25)
            m.run()
            check(byte(name) == want, "the %s key sets %s to %d (%d)"
                  % (key, name, want, byte(name)))
        m.type_text("4")
        m.advance(frames=25)
        m.run()
        check(byte("cs_setfill") == 6, "the 4 key takes the ground's fill off (%d)"
              % byte("cs_setfill"))
        m.type_text("4")
        m.advance(frames=25)
        m.run()

        # --- 5. a smaller view leaves nothing beside it ----------------------
        #
        # READ VRAM, NOT THE RENDERED FRAME. MartyPC's Hercules raster does
        # not land on the framebuffer's origin - measured at (-16, +2) on the
        # mode this kernel sets - so a band named in BOX coordinates and read
        # out of m.fbuf() is sixteen pixels adrift, which puts the view's own
        # left edge inside it and reads as a bleed beside the picture that is
        # not there at all (docs/MARTYPC-DEBUG.md, "the rendered frame is not
        # the framebuffer"). m.vram() is byte-for-byte the card's memory.
        pin()
        frames(3)
        big = (w("cs_ww"), w("cs_wh"))
        vx, vy = w("cs_vx"), w("cs_vy")
        back = byte("cs_back")
        bpp = 2 if back == 2 else 1             # CGA packs two bits a pixel
        m.pause()
        _, _, was = m.vram()
        m.run()

        def band(rows, wx0, wh):
            """Every pixel of the box LEFT of the view, lit ones counted."""
            return sum(sum(rows[y][vx * bpp:(vx + wx0) * bpp])
                       for y in range(vy, vy + wh))

        m.type_text("-")
        m.advance(frames=80)
        m.run()
        pin()
        frames(4)
        small = (w("cs_ww"), w("cs_wh"))
        check(small[0] * 2 == big[0] and small[1] * 2 == big[1],
              "the - key halves the view (%dx%d -> %dx%d)" % (big + small))
        m.pause()
        _, _, fb = m.vram()
        m.run()
        wx0 = w("cs_wx0")
        before, after = band(was, wx0, small[1]), band(fb, wx0, small[1])
        check(before > 100,
              "the larger view really did put something there (%d lit)" % before)
        check(after == 0, "the larger view is gone from beside the smaller "
              "one (%d lit)" % after)
        m.type_text("+")
        m.advance(frames=60)
        m.run()
        m.type_text("f")
        m.advance(frames=40)
        m.run()

    if bad:
        for b in bad:
            print("FAIL: " + b)
        return 1
    print("  ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
