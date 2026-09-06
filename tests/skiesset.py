#!/usr/bin/env python3
"""CLEAR SKIES' SETTINGS (SPEC.md 88.13): the page, and the four knobs on it
reaching the picture, on MartyPC.

    python3 tests/skiesset.py [--machine os8088_5150_herc_gla]

Every setting trades picture for frame rate, so every check here is about
one of the two: either the renderer does less work, or the glass shows
something different.

  0. the Detail Level a player who never opens the page flies on is
     MODERATE (88.13.1.1) - in the byte and in the drop-down's own record -
     because Moderate carries every location's whole table and High is the
     286/386 rung above it;
  1. Flight -> Settings opens the page and the painter writes all seven
     controls' rects (four drop-downs, two fill boxes, Done);
  2. picking Detail Level = Low leaves fewer objects in the frame - cs_nvisn,
     which is what the cull filed - and the frame gets measurably shorter;
  3. a fill box toggles its bit in cs_setfill, and clearing both leaves the
     wireframe: the ground's dither is gone from the glass;
  3a. Moderate is High minus CSO_DENSE, COUNTED and not compared as pixels:
     a paused Clear Skies is not a still picture - the water moves - so two
     arms drawing the same objects differ by thousands of pixels and a
     SAME-RUNG control reads the same thousands. The dense objects are
     counted out of the world's own table, so the check does not go stale
     the day a location grows a High tier;
  3b. Detail Level = None files nothing built and still leaves the
     runway, the water and the terrain standing (88.13.1), and Only
     Roads brings the roads and bridges back and no more;
  4. inside the bracket the hotkeys do the same things without the page -
     F1..F5 the detail level, F6/F7 the fills, F8..F10 the draw
     distance, -/+ size;
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
must then fail to turn the page. --clobber-default puts the old top-rung
default back and check 0 must go red; --clobber-dense points cs_consider's
`test ax, CSO_DENSE` at CSO_COLLIDE, which objects actually wear, so the top
rung's filter fires at Moderate too and check 3a must go red.
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
CSBL_NONE, CSBL_ROADS, CSBL_LOW, CSBL_MOD, CSBL_HIGH = 0, 1, 2, 3, 4
CSFL_TERRAIN, CSFL_BLDG, CSFL_ALL = 1, 2, 3
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
    ap.add_argument("--clobber-default", action="store_true",
                    help="the old CSBL_HIGH default back: check 0 goes red")
    ap.add_argument("--clobber-dense", action="store_true",
                    help="the top rung's filter fires at Moderate too: check"
                         " 3a goes red")
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

        if a.clobber_default:
            m.pause()
            m.write(lin + base + off("cs_setbld"), bytes([CSBL_HIGH]))
            m.write(lin + mp["cs_drbld"] + 12, CSBL_HIGH.to_bytes(2, "little"))
            m.run()
            print("  (the old top-rung default back: this run must fail)")
        if a.clobber_dense:
            # `test ax, CSO_DENSE` is A9 00 02. Point it at CSO_COLLIDE, which
            # objects actually wear, and the top rung's filter starts firing at
            # Moderate - the defect check 3a exists for.
            lo, hi = mp["cs_consider"], mp["cs_range"]
            code = m.read(lin + lo, hi - lo)
            i = code.find(b"\xA9\x00\x02")
            if i < 0:
                sys.exit("skiesset: cs_consider does not test CSO_DENSE the "
                         "way this patch expects - re-read it before trusting "
                         "the red run")
            m.pause()
            m.write(lin + lo + i + 1, b"\x01\x00")
            m.run()
            print("  (the dense filter pointed at CSO_COLLIDE: must fail)")

        # --- 0. THE DEFAULT IS MODERATE (SPEC.md 88.13.1) --------------------
        #
        # Moderate carries every location's whole table today, so this is the
        # picture the simulator has always drawn; High is the rung that adds
        # CSO_DENSE on top of it and is a 286/386 one. Read BEFORE the page is
        # opened, because opening it is what would set the byte if the record
        # and the init disagreed.
        check(byte("cs_setbld") == CSBL_MOD,
              "the Detail Level a player who never opens the page flies on is "
              "Moderate (%d)" % byte("cs_setbld"))
        drdef = int.from_bytes(m.readseg(seg, mp["cs_drbld"] + 12, 2), "little")
        check(drdef == CSBL_MOD,
              "...and the page's own drop-down agrees (%d)" % drdef)

        # --- 1. the page and its controls ------------------------------------
        ui.menu_pick("Flight", "Settings")
        m.advance(frames=40)
        m.run()
        check(byte("cs_page") == 2, "Flight -> Settings turns to the page (%d)"
              % byte("cs_page"))
        names = ("cs_drbld", "cs_drlod", "cs_drsize", "cs_drmode",
                 "cs_ckterr", "cs_ckbld", "cs_donerect")
        rects = {n: rect(n) for n in names}
        wrote = [n for n in names if rects[n][2] > rects[n][0]]
        check(len(wrote) == len(names),
              "the painter wrote all seven controls' rects (%d)" % len(wrote))

        def click(x, y, f=25):
            ui.mo.click(x, y)
            m.advance(frames=f)
            m.run()

        # --- 3. a fill box toggles its bit -----------------------------------
        for nm, bit, lbl in (("cs_ckterr", CSFL_TERRAIN, "Terrain"),
                             ("cs_ckbld", CSFL_BLDG, "Buildings")):
            r = rects[nm]
            was = byte("cs_setfill")
            click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)
            now = byte("cs_setfill")
            check(now == was & ~bit, "the %s box clears its fill bit (%d -> %d)"
                  % (lbl, was, now))
        check(byte("cs_setfill") == 0, "both off is the wireframe (%d)"
              % byte("cs_setfill"))
        for nm in ("cs_ckterr", "cs_ckbld"):
            r = rects[nm]
            click((r[0] + r[2]) // 2, (r[1] + r[3]) // 2)
        check(byte("cs_setfill") == CSFL_ALL, "...and back on again (%d)"
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
        # slides UP into the window. Buildings HAS a fourth item now (None,
        # 88.13.1) and the others have three, so reading the record is what
        # keeps this row true - which is exactly what it was written for.
        top = int.from_bytes(m.readseg(seg, mp["cs_drbld"] + 22, 2), "little")
        drew = sum(sum(1 for x in range(r[0], r[2] + 1)
                       if was[y][x] != now[y][x])
                   for y in range(top, min(top + 5 * 12 + 2, len(was))))
        check(drew > 200, "...and the list is ON THE GLASS where os88ui_drfit "
                          "put it (%d pixels changed)" % drew)
        click(r[0] + 20, top + 1 + 2 * 12 + 6)      # the THIRD item: None and
        check(byte("cs_setbld") == CSBL_LOW,        # Only Roads are above it
              "picking Low sets the detail level (%d)" % byte("cs_setbld"))

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
        m.key("F5")                                 # ...F1..F5 the detail level
        m.advance(frames=40)
        m.run()
        pin()
        frames(3)
        all_ms = frames()
        all_n = seen["n"]
        check(byte("cs_setbld") == CSBL_HIGH,
              "F5 is Detail Level = High (%d)" % byte("cs_setbld"))
        check(few_n < all_n, "Low files fewer objects than High (%d against %d)"
              % (few_n, all_n))

        # --- 3a. MODERATE IS HIGH MINUS CSO_DENSE (SPEC.md 88.13.1.1) -------
        #
        # Counted rather than compared as pixels: a paused Clear Skies is not
        # a still picture - the water moves - so two arms drawing the same
        # objects differ on the glass by thousands of pixels, and a same-rung
        # CONTROL reads the same thousands. The cull's own count is exact.
        # The dense objects are counted out of the world's table, so this
        # check does not go stale the day a location grows a High tier: with
        # none, the two rungs file the same set.
        ap = int.from_bytes(m.read(lin + base + off("cs_airport"), 2), "little")
        objs = int.from_bytes(m.read(lin + ap + 18, 2), "little")
        nobj = int.from_bytes(m.read(lin + ap + 20, 2), "little")
        ndense = sum(1 for o in range(objs, objs + nobj * 20, 20)
                     if int.from_bytes(m.read(lin + o + 16, 2), "little") & 0x0200)
        m.key("F4")
        m.advance(frames=40)
        m.run()
        pin()
        frames(3)
        frames()
        mod_n = seen["n"]
        check(byte("cs_setbld") == CSBL_MOD,
              "F4 is Detail Level = Moderate (%d)" % byte("cs_setbld"))
        if ndense:
            check(mod_n < all_n,
                  "this world has %d CSO_DENSE objects, so Moderate files "
                  "fewer than High (%d against %d)" % (ndense, mod_n, all_n))
        else:
            check(mod_n == all_n,
                  "nothing here wears CSO_DENSE, so Moderate and High file "
                  "the same set (%d and %d)" % (mod_n, all_n))
        check(few_n < mod_n, "and Low files fewer than Moderate (%d against %d)"
              % (few_n, mod_n))
        m.key("F5")
        m.advance(frames=40)
        m.run()
        check(few_ms < all_ms * 0.9,
              "...and its frame is shorter (%.1f ms against %.1f)" % (few_ms, all_ms))

        # --- 3b. Buildings = None files FEWER STILL, and keeps the world -----
        #
        # None is a density and not a fill: it refuses in cs_consider before
        # any transform (88.13.1), which is the cheapest form there is. What
        # it must NOT refuse is TERRAIN - the hills, the water and the runway
        # carry CSO_TERRAIN and are the world's surface, not scenery to thin
        # out. Then Only Roads brings back the roads and bridges and nothing
        # else, which is the rung between. IN THE BRACKET, because on the
        # Settings page any key turns the page back and the F-key is spent
        # doing that.
        m.key("F1")
        m.advance(frames=40)
        m.run()
        check(byte("cs_setbld") == CSBL_NONE,
              "F1 is Detail Level = None (%d)" % byte("cs_setbld"))
        pin()
        frames(3)
        none_ms = frames()
        none_n = seen["n"]
        check(none_n < few_n, "None files fewer than Low (%d against %d)"
              % (none_n, few_n))
        check(none_n > 0, "...and not an empty world: the runway, the water "
                          "and the terrain are still filed (%d)" % none_n)
        # AGAINST FULL and not against Low: by Low the frame is already the
        # ground band and a few distant objects, so None against Low is a few
        # per cent either way - under this harness's own spread - and a check
        # that asserts it is a check that fails on nothing.
        check(none_ms < all_ms * 0.6, "...and its frame is far shorter than "
              "Full's (%.1f ms against %.1f)" % (none_ms, all_ms))

        m.key("F2")                                 # ...and ONLY ROADS brings
        m.advance(frames=40)                        # the roads back, no more
        m.run()
        check(byte("cs_setbld") == CSBL_ROADS,
              "F2 is Only Roads (%d)" % byte("cs_setbld"))
        pin()
        frames(3)
        frames()
        roads_n = seen["n"]
        check(none_n < roads_n < few_n,
              "Only Roads files more than None and fewer than Low "
              "(%d, %d, %d)" % (none_n, roads_n, few_n))
        m.key("F5")                                 # ...and everything back
        m.advance(frames=40)
        m.run()

        # --- 4. the other hotkeys --------------------------------------------
        for key, name, want in (("F8", "cs_setlod", 0), ("F10", "cs_setlod", 2),
                                ("F9", "cs_setlod", 1), ("F1", "cs_setbld", 0),
                                ("F2", "cs_setbld", 1), ("F3", "cs_setbld", 2),
                                ("F4", "cs_setbld", 3), ("F5", "cs_setbld", 4)):
            m.key(key)
            m.advance(frames=25)
            m.run()
            check(byte(name) == want, "the %s key sets %s to %d (%d)"
                  % (key, name, want, byte(name)))
        m.key("F6")
        m.advance(frames=25)
        m.run()
        check(byte("cs_setfill") == CSFL_BLDG,
              "F6 takes the terrain's fill off (%d)" % byte("cs_setfill"))
        m.key("F6")
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
