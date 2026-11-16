"""bonanzatitle - THE TITLE SCREEN on the glass (SPEC.md 128.23).

BONANZA on MartyPC, CGA and Hercules. Enter on the face opens the TITLE in
the bracket, and in that one bracket:

  1. the title is up: its course (BZ_CRS_TITLE) fetched, a title demo (mode 2,
     bz_tmode 1) playing, the window the header's FIXED one (bz_fixed, R0 and
     c0 for this card);
  2. the window NEVER MOVES: bz_R0 and bz_c0 read at 40 frames of the demo,
     each the fixed pair;
  3. the SLOT's label: 3 then 2 then S - bz_slot 2, 1, 2 and the label's lane
     drawn at pose 1 + slot within a few frames each time (bz_ldrw);
  4. the title demo runs its BZ_TSTEPS steps to its end (4b: with ONE full
     write, its first - a respawn on the fixed window is no cut, so no blank
     flash; discriminating for demos 2 - 4, which fall), and there - stopped
     at bz_tlog, before the course demo's fetch - the guest's ball (gx, gy, gz)
     and its falls, tube rides and spring launches EQUAL the model's replay of
     the same demo (bbcourse.title_start and its runs, the .bzt the build
     packed);
  5. a COURSE DEMO follows (bz_tmode 2, bz_crs a tour course, the window its
     own camera's); a key ends it and the title is back (bz_tmode 1);
  6. P plays THE GAME: the pathway, the slot shown (2); its Esc is the title
     again;
  7. Esc on the title leaves the bracket; the instance's claims are as before
     Enter.

Red arm `view`: bz_camera's first frame centred on the ball as a course's is
(the fixed window's placement taken out) - red at check 2.

    python3 tests/bonanza_title.py [--tag cga|herc] [--red view] [--check]
"""
import argparse
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import bbcourse as BB           # noqa: E402
import os88marty as M           # noqa: E402
import os88ui                   # noqa: E402
import bonanza_ring as R        # noqa: E402
import bonanza_exit as X        # noqa: E402

REDS = {
    # SPEC.md 128.23.2: the fixed window's FIRST frame taken out - the window is centred on the ball (the
    # every-frame hold then keeps it there), never the header's
    "view": [("bzgame.inc", "    cmp byte [bz_fixed], 0      ; SPEC.md 128.23.2: a FIXED window is the\n",
              "    cmp byte [bz_fixed], 1      ; RED view: the first frame centred as a course's\n")],
}
RED_WANT = {"view": "2. "}


def title_k():
    R.CRS_K["bench"]
    return dict.__len__(R.CRS_K) + 1            # BZ_CRS_TITLE = BZ_CRS_PATH + 1 = BZ_NCRS + 1


def on_title(g):
    return g.b("bz_fs") == 1 and g.b("bz_tmode") == 1 and g.b("bz_crs") == title_k() and g.w("bz_cseg") != 0


def label_lane(g):
    """the title's label's lane index: its one SIGN lane (SPEC.md 128.22.4.1: a PK_SIGN since wave 8R)"""
    n = g.b("bz_nlane")
    knd = g.m.read(g.a("bz_lknd"), n)
    ks = [i for i in range(n) if knd[i] == BB.PK_SIGN]
    assert len(ks) == 1, "the title has %d SIGN lanes, not its one label" % len(ks)
    return ks[0]


def frames_until(g, pred, n=12):
    """step the frame loop (bz_t0 stops) until PRED(g), at most N frames -> True"""
    m = g.m
    wk = R.Walker(g, t0=True)
    m.bp_exec(wk.t0)
    try:
        for _ in range(n):
            while wk.next() != "t0":
                pass
            if pred(g):
                return True
        return False
    finally:
        m.bp_exec()
        m.run()


def model_end(c, n):
    """the model's replay of title demo N (1 - 4), as the build packed it: its
    end state"""
    with open(BB.title_demo_path(n)) as f:
        d = BB.parse_bzt(f.read())
    _log, p = BB.title_check(c, d, "title demo %d" % n)
    return p


def run(tag, apps=None, src=None):
    fails = []
    tc = BB.compile_course(os.path.join(src or os.path.join(ROOT, "apps", "bonanza"), "courses", "title.bbc"))
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, R.symbols(src), live=True)
        ui.settle()
        m = g.m
        m.pause()
        base = X.claims(g)
        m.run()
        # --- 1. the title up ----------------------------------------------------------------
        g.key("Enter")
        M.until(m, lambda _: on_title(g), "the title", guest=60)
        X.at_t0(g, lambda g_: None)
        m.pause()
        fr, fc = g.w("bz_fixr"), g.w("bz_fixc")
        v = tc.model["grid"]["view"]
        want = (2 * (v & 255), v >> 8) if tag == "cga" else (v & 255, (v >> 8) - BB.HERC_LEFT)
        ok = g.b("bz_fixed") == 1 and (fr, fc) == want and g.b("bz_mode") == 2
        print("%s 1. the title: course %d, mode %d, the FIXED window (R0 %d, c0 %d; the header's %s): %s" % (
            tag, g.b("bz_crs"), g.b("bz_mode"), fr, fc, want, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("1. the title's window is not the header's fixed one (%s, %d %d)" % (want, fr, fc))
        m.run()
        # --- 2. the window never moves -----------------------------------------------------
        seen = set()
        wk = R.Walker(g, t0=True)
        m.bp_exec(wk.t0)
        for _ in range(40):
            while wk.next() != "t0":
                pass
            if g.b("bz_tmode") == 1:
                seen.add((g.w("bz_R0"), g.w("bz_c0")))
        m.bp_exec()
        m.run()
        ok = seen == {want}
        print("%s 2. the window over 40 frames of the demo: %s: %s" % (tag, sorted(seen), "yes" if ok else "NO"),
              flush=True)
        if not ok:
            fails.append("2. the title's window moved: %s, not %s" % (sorted(seen), want))
            return fails
        # --- 3. the slot's label ------------------------------------------------------------
        m.pause()
        lane = label_lane(g)
        m.run()
        for key, slot in (("Digit3", 2), ("Digit2", 1), ("KeyS", 2)):
            g.key(key)
            got = frames_until(g, lambda g_: g_.b("bz_slot") == slot
                               and g_.m.read(g_.a("bz_ldrw") + lane, 1)[0] == slot + 1, 30)
            print("%s 3. %s: slot %d, the label drawn at pose %d: %s" % (
                tag, key, g.b("bz_slot"), m.read(g.a("bz_ldrw") + lane, 1)[0], "yes" if got else "NO"),
                flush=True)
            if not got:
                fails.append("3. %s: the slot %d's label was not drawn (slot %d, pose %d)" % (
                    key, slot, g.b("bz_slot"), m.read(g.a("bz_ldrw") + lane, 1)[0]))
        # --- 4. the demo's end, against the model --------------------------------------------
        m.bp_exec(g.a("bz_tlog"))
        st = m.wait_stop(120)
        assert st == "breakpoint", "the title demo never ended (state %r)" % st
        n = g.b("bz_tsel") + 1
        gst = (g.d("bz_gx"), g.d("bz_gy"), g.d("bz_gz"), g.w("bz_nfall"), g.w("bz_ntube"), g.w("bz_nspr"),
               g.d("bz_nstep"))
        nfull = g.w("bz_nfull")                 # (the owner, 2026-11-16: no black flash - a respawn on the
                                                # FIXED window is no cut, so the play's one full write is its first)
        m.bp_exec()
        m.run()
        p = model_end(tc, n)
        mst = (p.gx, p.gy, p.gz, p.nfall, p.ntube, p.nspr, p.nstep)
        ok = gst == mst and gst[-1] == BB.TITLE_STEPS
        print("%s 4. title demo %d's end: the guest (gx gy gz falls tubes springs steps) %s, the model %s: %s" % (
            tag, n, gst, mst, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("4. title demo %d ended at %s on the guest, %s on the model" % (n, gst, mst))
        ok = nfull == 1
        print("%s 4b. title demo %d: %d full write(s), its %d fall(s) none (no blank flash): %s" % (
            tag, n, nfull, gst[3], "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("4b. title demo %d made %d full writes - a respawn blanked the glass" % (n, nfull))
        # --- 5. a course demo, ended by a key ---------------------------------------------------
        M.until(m, lambda _: g.b("bz_tmode") == 2 and g.b("bz_crs") < title_k() - 1 and g.w("bz_cseg") != 0,
                "a course demo", guest=60)
        X.at_t0(g, lambda g_: None)
        crs = g.b("bz_crs")
        g.key("KeyQ")
        M.until(m, lambda _: on_title(g), "the title again (a key in the course demo)", guest=60)
        print("%s 5. a course demo (course %d) followed; a key brought the title back: yes" % (tag, crs), flush=True)
        # --- 6. P: the game, in the slot shown; its Esc is the title --------------------------
        X.at_t0(g, lambda g_: None)
        g.key("KeyP")
        M.until(m, lambda _: g.b("bz_crs") == title_k() - 1 and g.w("bz_cseg") != 0 and g.b("bz_tmode") == 0,
                "the pathway (P)", guest=60)
        X.at_t0(g, lambda g_: None)
        slot = g.b("bz_slot")
        g.key("Escape")
        M.until(m, lambda _: on_title(g), "the title again (the pathway's Esc)", guest=60)
        ok = slot == 2
        print("%s 6. P played the game in slot %d; its Esc was the title again: %s" % (
            tag, slot + 1, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("6. P's game was slot %d, not the one shown (3)" % (slot + 1))
        # --- 7. Esc on the title: the desktop, the claims as before -----------------------------
        X.at_t0(g, lambda g_: None)
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, "the desktop", guest=30)
        M.until(m, lambda _: X.rows(g)[X.shell_row()][0] & X.OP_FETCHED and g.b("bz_shpend") == 0
                and g.b("bzs_desk") == 1, "the face back and the desktop's song again (bz_title8's tail: the "
                "bracket's restore can paint the face first)", guest=30)
        m.pause()
        after = X.claims(g)
        m.run()
        ok = after == base
        print("%s 7. Esc on the title: the desktop, the claims %s as before: %s" % (
            tag, after, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("7. after the title the claims are %s, before %s" % (after, base))
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", choices=("cga", "herc"), action="append")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only: every red arm assembles")
    a = ap.parse_args()
    if a.check:
        for line in R.check_reds(REDS, "bonanza_title"):
            print(line)
        return 0
    tags = tuple(a.tag or ("cga", "herc"))
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags[:1]:
                bad = run(tag, apps=img, src=src)
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(b.startswith(RED_WANT[a.red]) for b in bad), \
                    "RED ARM %s went red, but not at its own check: %s" % (a.red, bad)
        print("bonanza_title --red %s: PASS (the row fails against the broken package)" % a.red)
        return 0
    allbad = []
    for tag in tags:
        allbad += ["%s: %s" % (tag, b) for b in run(tag)]
    for b in allbad:
        print("FAIL %s" % b)
    assert not allbad, "%d failure(s)" % len(allbad)
    print("bonanza_title (%s): PASS" % ", ".join(tags))
    return 0


if __name__ == "__main__":
    sys.exit(main())
