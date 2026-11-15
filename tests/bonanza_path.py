#!/usr/bin/env python3
"""bonanzapath - THE GAME's loop on the glass (SPEC.md 128.19.5, wave 8b).

BONANZA on MartyPC, CGA and Hercules: Enter on the face starts a NEW game -
five lives, node 0 open, nothing done - and the pathway comes up in the
bracket, its node 0 sign OPEN and the rest LOCKED, its clock showing the
lives.  Then, in that one bracket:

  1. the ball poked onto LOCKED node 1's cell rolls on: no course is fetched,
     the pathway's play goes on (the goal's gate, 128.19.5);
  2. poked onto node 0: FIRST is fetched and played; the autopilot finishes
     it, and back on the pathway node 0 is DONE and node 1 OPEN (the edge
     0 -> 1), their signs' poses 2 and 1;
  3. node 1 (TRIAL), left by Esc: a life (4), back on the pathway;
  4. the lives poked to 1, node 0 replayed and left by Esc: the GAME IS OVER -
     the bracket ends, the lives 0, the instance's claims as before the game;
  5. Enter again: a NEW game (lives 5, node 0 open, nothing done); Esc leaves.

Red arm `nogate`: the goal's gate on the pathway taken out, so a locked node
plays its course - red at check 1.

    python3 tests/bonanza_path.py [--tag cga|herc] [--red nogate] [--check]
"""
import argparse
import os
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
    # the pathway's goal gate (bzphys.inc step 8): every node's cell a finish, locked or not
    "nogate": [("bzphys.inc", "    test ax, [bz_nopen]\n    jz .end\n",
                "    test ax, [bz_nopen]                ; RED nogate: no gate\n")],
}
RED_WANT = {"nogate": "1. "}


def path_course(src=None):
    d = src or os.path.join(ROOT, "apps", "bonanza")
    return BB.compile_course(os.path.join(d, "courses", "path.bbc"))


def poke_node(g, pc, n):
    """the ball at rest on node N's cell, at the next bz_t0"""
    nd = next(x for x in pc.src.nodes if x["num"] == n)
    p = BB.Physics(pc, play=True).poke(*nd["at"])
    X.at_t0(g, lambda g_: R.poke_ball(g_, p.gx, p.gy, p.gz, 0, 0, 0, air=0))


def on_path(g):
    return g.b("bz_fs") == 1 and g.b("bz_crs") == BB_PATH and g.w("bz_cseg") != 0


BB_PATH = None


def run(tag, apps=None, src=None):
    global BB_PATH
    fails = []
    pc = path_course(src)
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, R.symbols(src), live=True)
        ui.settle()
        m = g.m
        R.CRS_K["bench"]                    # (fills the course table: the pathway's index is BZ_NCRS)
        BB_PATH = dict.__len__(R.CRS_K)
        m.pause()
        base = X.claims(g)
        m.run()
        # --- a new game ------------------------------------------------------------
        g.key("Enter")
        M.until(m, lambda _: on_path(g), "the pathway", guest=60)
        nst = list(m.read(g.a("bz_nst"), len(pc.src.nodes)))
        ok = g.b("bz_lives") == 5 and g.w("bz_nopen") == 1 and g.w("bz_ndone") == 0 and nst == [1] + [0] * (len(nst) - 1)
        print("%s 0. a new game: lives %d, open %04X, done %04X, the signs %s: %s" % (
            tag, g.b("bz_lives"), g.w("bz_nopen"), g.w("bz_ndone"), nst, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("0. a new game is not 5 lives, node 0 open and nothing done (%s)" % nst)
        # --- 1. a LOCKED node rolls like floor ------------------------------------------
        poke_node(g, pc, 1)
        M.guest_sleep(m, 1.5)
        ok = on_path(g) and g.b("bz_goal") == 0
        print("%s 1. the ball on LOCKED node 1: the pathway goes on (course %d, goal %d): %s" % (
            tag, g.b("bz_crs"), g.b("bz_goal"), "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("1. a LOCKED node played its course (course %d, goal %d)" % (g.b("bz_crs"), g.b("bz_goal")))
            return fails
        # --- 2. node 0: FIRST, finished ---------------------------------------------------
        poke_node(g, pc, 0)
        M.until(m, lambda _: g.b("bz_crs") == R.CRS_K["first"] and g.w("bz_cseg") != 0, "FIRST from node 0",
                guest=30)
        m.pause()
        g.putb("bz_apilot", 1)
        m.run()
        M.until(m, lambda _: on_path(g), "back on the pathway after FIRST", guest=120)
        m.pause()
        g.putb("bz_apilot", 0)
        m.run()
        M.guest_sleep(m, 0.5)
        nst = list(m.read(g.a("bz_nst"), len(pc.src.nodes)))
        ok = g.w("bz_ndone") == 1 and g.w("bz_nopen") == 3 and nst[:2] == [2, 1] and g.b("bz_lives") == 5
        print("%s 2. node 0 (FIRST) finished: done %04X, open %04X, the signs %s, lives %d: %s" % (
            tag, g.w("bz_ndone"), g.w("bz_nopen"), nst, g.b("bz_lives"), "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("2. FIRST's finish did not mark node 0 done and open node 1 (%s)" % nst)
        # --- 3. node 1: TRIAL, left by Esc ---------------------------------------------
        poke_node(g, pc, 1)
        M.until(m, lambda _: g.b("bz_crs") == R.CRS_K["trial"] and g.w("bz_cseg") != 0, "TRIAL from node 1",
                guest=30)
        M.guest_sleep(m, 0.5)
        g.key("Escape")
        M.until(m, lambda _: on_path(g), "back on the pathway after Esc", guest=30)
        ok = g.b("bz_lives") == 4
        print("%s 3. node 1 (TRIAL) left by Esc: lives %d: %s" % (tag, g.b("bz_lives"), "yes" if ok else "NO"),
              flush=True)
        if not ok:
            fails.append("3. an Esc on a course cost no life (lives %d)" % g.b("bz_lives"))
        # --- 4. the last life: the game is over -----------------------------------------
        m.pause()
        g.putb("bz_lives", 1)
        m.run()
        poke_node(g, pc, 0)
        M.until(m, lambda _: g.b("bz_crs") == R.CRS_K["first"] and g.w("bz_cseg") != 0, "FIRST again", guest=30)
        M.guest_sleep(m, 0.5)
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, "the bracket to end (game over)", guest=30)
        M.until(m, lambda _: X.rows(g)[X.shell_row()][0] & X.OP_FETCHED and g.b("bz_shpend") == 0,
                "the face back", guest=30)
        m.pause()
        after = X.claims(g)
        lives = g.b("bz_lives")
        m.run()
        ok = lives == 0 and after == base
        print("%s 4. the last life lost: the bracket ended, lives %d, the claims %s as before: %s" % (
            tag, lives, after, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("4. game over: lives %d, the claims %s, before %s" % (lives, after, base))
        # --- 5. Enter again: a new game ----------------------------------------------------
        g.key("Enter")
        M.until(m, lambda _: on_path(g), "the pathway again", guest=60)
        ok = g.b("bz_lives") == 5 and g.w("bz_nopen") == 1 and g.w("bz_ndone") == 0
        print("%s 5. Enter after the game's end: a NEW game (lives %d, open %04X, done %04X): %s" % (
            tag, g.b("bz_lives"), g.w("bz_nopen"), g.w("bz_ndone"), "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("5. Enter after game over did not start a new game")
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, "the desktop", guest=30)
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", choices=("cga", "herc"), action="append")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only: every red arm assembles")
    a = ap.parse_args()
    if a.check:
        for line in R.check_reds(REDS, "bonanza_path"):
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
        print("bonanza_path --red %s: PASS (the row fails against the broken package)" % a.red)
        return 0
    allbad = []
    for tag in tags:
        allbad += ["%s: %s" % (tag, b) for b in run(tag)]
    for b in allbad:
        print("FAIL %s" % b)
    assert not allbad, "%d failure(s)" % len(allbad)
    print("bonanza_path (%s): PASS" % ", ".join(tags))
    return 0


if __name__ == "__main__":
    sys.exit(main())
