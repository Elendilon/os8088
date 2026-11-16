#!/usr/bin/env python3
"""bonanzapath - THE GAME's loop on the glass (SPEC.md 128.19.5, wave 8b).

BONANZA on MartyPC, CGA and Hercules: Enter on the face opens the TITLE and P
there (SPEC.md 128.23.4) starts a NEW game -
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
import bonanza_game as GM       # noqa: E402
import struct                   # noqa: E402

REDS = {
    # the pathway's goal gate (bzphys.inc step 8): every node's cell a finish, locked or not
    "nogate": [("bzphys.inc", "    test ax, [bz_gmask]         ; (8c: EXPLORE's every node)\n    jz .end\n",
                "    test ax, [bz_gmask]                ; RED nogate: no gate\n")],
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


def to_title(g):
    """SPEC.md 128.23.4: the TITLE up - its course fetched and its demo's frame
    loop reached (a key typed before bz_play starts is drained)"""
    m = g.m
    M.until(m, lambda _: g.b("bz_tmode") == 1 and g.b("bz_crs") == BB_PATH + 1 and g.w("bz_cseg") != 0,
            "the title", guest=60)
    X.at_t0(g, lambda g_: None)


def enter_game(g, what="the pathway"):
    """Enter on the face opens the TITLE (128.23.4); P there plays the game"""
    g.key("Enter")
    to_title(g)
    g.key("KeyP")
    M.until(g.m, lambda _: on_path(g), what, guest=60)


def leave_game(g, what="the desktop"):
    """Esc on the pathway returns to the TITLE (128.23.4); Esc there leaves"""
    playing(g, "the pathway")
    g.key("Escape")
    to_title(g)
    g.key("Escape")
    M.until(g.m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, what, guest=30)


def playing(g, what):
    """the play's frame loop REACHED (a stop at bz_t0, past bz_play's drain): a
    key typed before bz_play starts is drained, and the fetch before it takes
    its time"""
    X.at_t0(g, lambda g_: None)


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
        # --- a new game: Enter opens the title, P plays (SPEC.md 128.23.4) ---------------
        enter_game(g)
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
        best = struct.unpack_from("<H", m.read(g.a("bz_dat") + 64 + 24 + 2 * R.CRS_K["first"], 2))[0]
        gold = R.medals("first")[0]
        ok = g.w("bz_ndone") == 1 and g.w("bz_nopen") == 3 and nst[:2] == [4, 1] and g.b("bz_lives") == 5 \
            and 0 < best <= gold
        print("%s 2. node 0 (FIRST) finished: done %04X, open %04X, the signs %s (node 0 GOLD: the slot's best %d "
              "steps, G %d), lives %d: %s" % (tag, g.w("bz_ndone"), g.w("bz_nopen"), nst, best, gold,
                                              g.b("bz_lives"), "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("2. FIRST's finish did not mark node 0 done (GOLD) and open node 1 (%s, best %d)" % (nst, best))
        # --- 3. node 1: TRIAL, left by Esc ---------------------------------------------
        poke_node(g, pc, 1)
        M.until(m, lambda _: g.b("bz_crs") == R.CRS_K["trial"] and g.w("bz_cseg") != 0, "TRIAL from node 1",
                guest=30)
        M.until(m, lambda _: g.d("bz_nstep") < 20, "TRIAL's play started (its steps from 0)", guest=30)
        M.until(m, lambda _: g.d("bz_nstep") > 30, "TRIAL's play under way", guest=30)
        # wave 8c (128.19.8): P - the pause card; R on it RETRIES the course for a life
        g.key("KeyP")
        M.until(m, lambda _: g.b("bz_inpause") == 1, "the pause card", guest=10)
        n0 = g.d("bz_nstep")
        g.key("KeyR")
        M.until(m, lambda _: g.b("bz_inpause") == 0 and g.b("bz_fs") == 1 and g.d("bz_nstep") < n0
                and g.b("bz_crs") == R.CRS_K["trial"], "TRIAL retried", guest=30)
        ok = g.b("bz_lives") == 4 and g.b("bz_crs") == R.CRS_K["trial"]
        print("%s 3r. P then R on TRIAL: a RETRY, the course again (steps %d -> %d), lives %d: %s" % (
            tag, n0, g.d("bz_nstep"), g.b("bz_lives"), "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("3r. R on the pause card did not retry the course for a life (lives %d)" % g.b("bz_lives"))
        M.until(m, lambda _: g.d("bz_nstep") > 30, "TRIAL's retry under way", guest=30)
        g.key("Escape")
        M.until(m, lambda _: on_path(g), "back on the pathway after Esc", guest=30)
        ok = g.b("bz_lives") == 3
        print("%s 3. node 1 (TRIAL) left by Esc: lives %d: %s" % (tag, g.b("bz_lives"), "yes" if ok else "NO"),
              flush=True)
        if not ok:
            fails.append("3. an Esc on a course cost no life (lives %d)" % g.b("bz_lives"))
        # --- 3b. SAVE V2 (128.19.6): left for the desktop, the slot on the floppy; Enter continues it --
        leave_game(g, "the desktop (the game left, through the title)")
        GM.motor_off(g)
        dat = GM.read_dat(g)
        sl = struct.unpack_from("<BBHHH", dat, 64) if dat and len(dat) == GM.DAT_FILE else None
        ok = dat is not None and dat[:4] == b"BZS2" and sl == (3, 0, 3, 1, R.path_ident()) \
            and struct.unpack_from("<H", dat, 64 + 8 + 2 * R.CRS_K["first"])[0] == 1
        print("%s 3b. left for the desktop: BONANZA.DAT %s, slot 0 %s (lives, 0, open, done, the pathway), "
              "FIRST's exits found %s: %s" % (tag, dat[:4] if dat else None, sl,
                                              struct.unpack_from("<H", dat, 64 + 8 + 2 * R.CRS_K["first"])[0]
                                              if sl else None, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("3b. the game's slot on the floppy is %s, not (3, 0, 3, 1, the pathway's identity)" % (sl,))
        enter_game(g, "the pathway again (the game continued)")
        ok = g.b("bz_lives") == 3 and g.w("bz_nopen") == 3 and g.w("bz_ndone") == 1
        print("%s 3c. Enter continues the slot's game: lives %d, open %04X, done %04X: %s" % (
            tag, g.b("bz_lives"), g.w("bz_nopen"), g.w("bz_ndone"), "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("3c. Enter did not continue the slot's game")
        # --- 4. the last life: the game is over -----------------------------------------
        m.pause()
        g.putb("bz_lives", 1)
        m.run()
        poke_node(g, pc, 0)
        M.until(m, lambda _: g.b("bz_crs") == R.CRS_K["first"] and g.w("bz_cseg") != 0, "FIRST again", guest=30)
        playing(g, "FIRST again")
        GM.motor_off(g)                     # the LIFE taken on the disk at the course's entry (128.19.6)
        dat = GM.read_dat(g)
        ok = dat is not None and len(dat) == GM.DAT_FILE and dat[64] == 0
        print("%s 4a. FIRST entered with the last life: the slot's lives on the floppy %s: %s" % (
            tag, dat[64] if dat and len(dat) > 64 else None, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("4a. the life was not taken on the disk at the course's entry")
        g.key("Escape")
        to_title(g)                             # (128.23.4: the game's end is the TITLE again)
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
        enter_game(g, "the pathway again")
        ok = g.b("bz_lives") == 5 and g.w("bz_nopen") == 1 and g.w("bz_ndone") == 0
        print("%s 5. Enter after the game's end: a NEW game (lives %d, open %04X, done %04X): %s" % (
            tag, g.b("bz_lives"), g.w("bz_nopen"), g.w("bz_ndone"), "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("5. Enter after game over did not start a new game")
        leave_game(g)
        M.until(m, lambda _: X.rows(g)[X.shell_row()][0] & X.OP_FETCHED and g.b("bz_shpend") == 0,
                "the face back", guest=30)
        # --- 6. EXPLORE (8c.2): E, then every node open, no life lost ---------------------------
        g.key("KeyE")
        GM.motor_off(g)
        dat = GM.read_dat(g)
        enter_game(g, "the pathway in EXPLORE")
        playing(g, "the pathway in EXPLORE")
        nst = list(m.read(g.a("bz_nst"), len(pc.src.nodes)))
        ok = dat is not None and dat[65] & 1 == 1 and g.w("bz_gmask") == 0xFFFF and min(nst) >= 1
        print("%s 6. E: the slot's mode EXPLORE on the floppy (+1 %s), every node open (the gate %04X, the signs "
              "%s): %s" % (tag, dat[65] if dat else None, g.w("bz_gmask"), nst, "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("6. EXPLORE did not open every node (%s, gate %04X)" % (nst, g.w("bz_gmask")))
        poke_node(g, pc, 4)                     # MOON: locked in TIMED
        M.until(m, lambda _: g.b("bz_crs") == R.CRS_K["moon"] and g.w("bz_cseg") != 0, "MOON (EXPLORE)", guest=30)
        playing(g, "MOON")
        tsec = g.w("bz_tsec")
        g.key("Escape")
        M.until(m, lambda _: on_path(g), "back on the pathway (EXPLORE)", guest=30)
        ok = tsec == 0 and g.b("bz_lives") == 5
        print("%s 6b. node 4 (MOON, locked when timed) played in EXPLORE: no clock (tsec %d), Esc cost no life "
              "(lives %d): %s" % (tag, tsec, g.b("bz_lives"), "yes" if ok else "NO"), flush=True)
        if not ok:
            fails.append("6b. EXPLORE ran a clock or took a life (tsec %d, lives %d)" % (tsec, g.b("bz_lives")))
        leave_game(g)
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
