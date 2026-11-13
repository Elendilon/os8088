#!/usr/bin/env python3
"""BONANZA: nothing is left behind, and a held key is one press (SPEC.md 128.10.6.2, 128.11.11.2, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_exit.py [--adapter cga|herc|both] [--no-keys]
    python3 tests/bonanza_exit.py --red leak|crepeat|overswallow     (a red arm, below)
    python3 tests/bonanza_exit.py --check                            (the host half: the red arms assemble)

A launch fetches TWO lazy, compressed parts on the desktop - course K's row
(3 + K) and the row of the ball MATERIAL in use (0 - 2, SPEC.md 128.11.3.1),
the same rows on both cards (the Hercules translates them in place) - and
holds them for the bracket's whole life, so both stay PINNED and every way
out must drop both.  This row takes every way out, on both cards, WITH EACH
BALL (M on the desktop: rubber, steel, glass):

    Esc, F, Alt+Enter    a play of FIRST (Enter), left by that key
    the goal             a play of FIRST whose ball is POKED onto the goal
                         column at bz_t0: the play ends the frame after
    a replay's end       R, a log of FIRST with that ball (the row writes it
                         into bz_rlog: 120 steps), run to its end
    Esc in a replay      R, a log of 600 steps, left by Esc
    the benchmark's end  B, BENCH with BENCH's ball, its 1,200th frame (once)

    and, wave 3 (SPEC.md 128.12.13.2), on MILL (part row 6) every way out
    above - its goal, a log of MILL, its benchmark - and Esc while the ball
    is HIDDEN in a tube (poked into the chute's drain)

and asserts, against what was read on the desktop BEFORE that launch:

  1  every part row of BONANZA.O88's table (os88parts.inc's op_table, all
     3 + BZ_NCRS of them): OP_FETCHED clear - so op_seg answers 0 - and
     OP_R_ZKB equal to its value before the launch (the PACKED LENGTH
     op_drop writes back, SPEC.md 20.12.7.4.1);
  2  the instance's heap claims, read by tools/heapmap.py, exactly those
     before the launch: the same count, sizes and pinning (compared by what
     each is, not where: the region is movable);
  3  as a POSITIVE CONTROL, inside every bracket: the two rows the launch
     fetched - the material's ball row and the course's - FETCHED with a
     segment, [bz_mat] the ball M chose (a replay's the log's, B's BENCH's),
     and the claims two more than on the desktop.

THE DESKTOP KEYS (128.11.11.2), last: for each of C, M and N - counted by a
logged breakpoint on its handler (bz_camkey, bz_ballkey, bz_crskey), since C's
two modes would hide an odd count - HELD for 1.5 s (MartyPC's keyboard
repeats after 0.5 s, ten times a second) it advances EXACTLY ONCE; pressed,
released for 0.2 s and pressed again it advances TWICE.

It reports, for each launch, the floppy controller's reads from the key to the
bracket (MartyPC's own counter, m.disk(): no guest instrument).  A refused
fetch is not driven (it needs a heap too short at one moment and not the
next, SPEC.md 128.10.11.3); the review reads that path.

--red NAME builds a broken package in a temporary directory (never build/)
and PASSES only if the row FAILS - at its own check:
  leak         the goal path does not drop the course's row: fails at the
               goal, and only there
  crepeat      the held-key guard taken out: a held key advances more than once
  overswallow  bz_dkk never cleared: the second press is swallowed
"""
import argparse
import os
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import heapmap                 # noqa: E402
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402
import bonanza_phys as P       # noqa: E402

OP_ROW, OP_T_ROWS, OP_R_FLAG, OP_R_ZKB = 8, 10, 1, 6        # apps/os88parts.inc
OP_LAZY, OP_FETCHED = 8, 32
WAYS = ("esc", "f", "altenter", "goal", "replayend", "replayesc")
HANDLERS = (("KeyC", "bz_camkey"), ("KeyM", "bz_ballkey"), ("KeyN", "bz_crskey"))


class Q(object):
    """heapmap.Map wants .read(linear, n); Marty has exactly that"""

    def __init__(self, m):
        self.m = m

    def read(self, linear, n):
        return self.m.read(linear, n)


def rows(g):
    """[(flags, zkb)] for every part row, read out of the image's own table"""
    n = g.m.read(g.a("op_table") + 8, 1)[0]
    raw = g.m.read(g.a("op_table") + OP_T_ROWS, n * OP_ROW)
    return [(raw[i * OP_ROW + OP_R_FLAG], struct.unpack_from("<H", raw, i * OP_ROW + OP_R_ZKB)[0])
            for i in range(n)]


def claims(g):
    """The instance's claims through tools/heapmap.py: [(role, paragraphs, pinned,
    owner)], sorted - the region (the claim holding the window's W_SEG; MC_OWN
    its instance slot) and the data claims (MC_OWN = the package's segment)."""
    m = g.m
    mp = heapmap.Map(Q(m), {n: m.sym(n) for n in ("mem_base", "mem_top", "spl_live", "mem_tab")})
    seg = g.wseg()
    reg = [c for c in mp.claims if c.seg <= seg < c.end]
    assert len(reg) == 1, "no claim of the heap holds BONANZA's segment %04X" % seg
    out = [("region", reg[0].para, reg[0].pinned, owner_kind(reg[0].own))]
    out += [("data", c.para, c.pinned, "seg") for c in mp.claims if c.own == seg]
    return sorted(out)


def owner_kind(own):
    return "slot" if own < 12 else "%04X" % own


def leave(g, way):
    """One way out of a running play or replay (Esc, F, Alt+Enter)."""
    m = g.m
    if way in ("esc", "replayesc"):
        g.key("Escape")
    elif way == "f":
        g.key("KeyF")
    else:
        m.key("AltLeft", up=False)
        M.pace(m, .04)
        m.key("Enter", up=False)
        M.pace(m, .04)
        m.key("Enter", down=False)
        m.key("AltLeft", down=False)


def launch(g, way, crs=None):
    """Start the launch that WAY leaves by - on course CRS ([bz_crs] poked at
    bz_launch's entry; a replay's course is its log's) - ; -> the floppy reads
    it took, once the bracket is up (both parts fetched)."""
    m = g.m
    m.disk(reset=True)
    key = "KeyB" if way == "bench" else "KeyR" if way.startswith("replay") else "Enter"
    if crs and not way.startswith("replay"):
        m.bp_exec(g.a("bz_launch"))
        g.key(key)
        assert m.wait_stop(60) == "breakpoint", "%s did not reach bz_launch" % key
        g.putb("bz_crs", R.CRS_K[crs])
        m.bp_exec()
        m.run()
    else:
        g.key(key)
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "the bracket is up (%s)" % way, guest=60)
    m.pause()
    return m.disk()["reads"]


def at_t0(g, poke):
    """POKE(g) at the next bz_t0 (the guest stopped there), then run on"""
    m = g.m
    wk = R.Walker(g, t0=True)
    m.bp_exec(wk.t0)
    while wk.next() != "t0":
        pass
    poke(g)
    m.bp_exec()
    m.run()


def goal(g, crs="first"):
    """Play to the goal: FIRST's ball poked onto its goal column at bz_t0; on
    another course, onto the centre of its first GOAL cell, at rest."""
    if crs == "first":
        (wx, wy), gvx, gvy, _ = P.SCEN["goal"]
    else:
        grid = BB.Grid(R.course(crs).cga)
        wx, wy = next((x, y) for y in range(256) for x in range(256) if grid.cell(x, y)[3] == BB.KIND_GOAL)
        gvx = gvy = 0
    p = BB.Physics(R.course(crs), play=True, mat=g.b("bz_mat")).poke(wx, wy, gvx, gvy)
    at_t0(g, lambda g_: R.poke_ball(g_, p.gx, p.gy, p.gz, p.gvx, p.gvy, p.gvz, air=0))


def into_tube(g, crs="mill"):
    """the ball poked onto the centre of the course's first plain tube's IN
    cell (a DRAIN: SPEC.md 128.12.6.1) at bz_t0: the next step captures it;
    -> once the guest says it is hidden ([bz_tube])"""
    tb = next(r for r in R.course(crs).part["props"] if r["kind"] == BB.PK_TUBE)
    p = BB.Physics(R.course(crs), play=True, mat=g.b("bz_mat")).poke(*tb["at"])
    at_t0(g, lambda g_: R.poke_ball(g_, p.gx, p.gy, p.gz, 0, 0, 0, air=0))
    M.until(g.m, lambda _: g.b("bz_tube") != 0, "the ball to be swallowed by the tube at %s" % (tb["at"],), guest=10)


def one(g, way, base_rows, base_claims, mat, crs="first"):
    """One launch on CRS left by WAY with the ball MAT chose: -> (failures, the
    report line).  B on FIRST is BENCH's benchmark (B's own course)."""
    m = g.m
    fails = []
    if way.startswith("replay"):                # a log of CRS with this ball: 2 s to its end, or
        m.pause()                               # 11 s to be left by Esc early
        g.write_log(R.make_log([0] * (120 if way == "replayend" else 600), R.CRS_K[crs], mat))
        m.run()
    if way == "bench":
        want_mat = R.course("bench" if crs == "first" else crs).ball    # B rolls its course's own ball
    elif way.startswith("replay"):
        want_mat = m.read(g.a("bz_rlog") + 5, 1)[0]   # R the log's (SPEC.md 128.11.12.2)
    else:
        want_mat = mat                              # a play M's
    reads = launch(g, way, None if crs == "first" else crs)
    pc, pb = g.b("bz_pc"), g.b("bz_pb")
    r_in, c_in = rows(g), claims(g)
    for i in (pc, pb):
        f, z = r_in[i]
        if not f & OP_FETCHED or not z:
            fails.append("%s: inside the bracket row %d is not fetched (flags %02X zkb %04X): the control cannot "
                         "see a part that is there" % (way, i, f, z))
    if g.b("bz_mat") != want_mat or pb != BALL_ROW0 + want_mat or pc != CRS_ROW0 + g.b("bz_crs"):
        fails.append("%s: the launch rolls material %d from row %d with course row %d; want material %d, rows %d "
                     "and %d (SPEC.md 128.11.3.1)" % (way, g.b("bz_mat"), pb, pc, want_mat, BALL_ROW0 + want_mat,
                                                     CRS_ROW0 + g.b("bz_crs")))
    if len(c_in) != len(base_claims) + 2:
        fails.append("%s: inside the bracket the instance holds %d claims, not the desktop's %d + 2: %s" % (
            way, len(c_in), len(base_claims), c_in))
    if way == "bench":
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark's 1,200 frames", guest=120)
    elif way == "goal":
        goal(g, crs)
        M.until(m, lambda _: g.b("bz_fs") == 0, "the play to end at the goal", guest=60)
        if not g.b("bz_fin"):
            fails.append("goal: the play ended but [bz_fin] is clear - it did not end at the goal")
    elif way == "replayend":
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 0, "the replay to reach its end", guest=60)
    elif way == "tubeesc":                      # Esc while the ball is HIDDEN in a tube
        m.run()
        for _ in range(3):                      # (swallowed and still inside, the guest paused)
            into_tube(g, crs)
            m.pause()
            if g.b("bz_tube"):
                break
            m.run()
        # the Esc is judged where bz_exitchk TAKES it: the ball must still be hidden there,
        # or this case is an ordinary Esc that says nothing about a tube
        m.bp_exec(g.a("bz_exitchk.leave"))
        m.run()
        leave(g, "esc")
        if m.wait_stop(60) != "breakpoint":
            fails.append("tubeesc: bz_exitchk never took the Esc")
            hid = None
        else:
            hid = g.b("bz_tube")
        m.bp_exec()
        m.run()
        if hid == 0:
            fails.append("tubeesc: the Esc was taken after the ball left the tube ([bz_tube] 0 at "
                         "bz_exitchk's leave) - an ordinary Esc, not one with the ball HIDDEN")
        M.until(m, lambda _: g.b("bz_fs") == 0, "the launch to end on Esc in a tube", guest=60)
    else:
        m.run()
        leave(g, way)
        M.until(m, lambda _: g.b("bz_fs") == 0, "the launch to end on %s" % way, guest=60)
    # bz_launch's .drop writes bz_cseg and bz_bseg 0 LAST, after both op_drop calls
    M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "the launch to drop its parts (%s)" % way,
            guest=30)
    m.pause()
    r_out, c_out = rows(g), claims(g)
    for i, (before, after) in enumerate(zip(base_rows, r_out)):
        if after[0] & OP_FETCHED:
            fails.append("%s: part row %d is still FETCHED after the launch (op_seg answers %04X)" % (
                way, i, after[1]))
        if after[1] != before[1]:
            fails.append("%s: part row %d's zkb is %04X after the launch, %04X before (op_drop did not write "
                         "the packed length back)" % (way, i, after[1], before[1]))
    if c_out != base_claims:
        fails.append("%s: the instance's claims after the launch %s, before it %s" % (way, c_out, base_claims))
    m.run()
    line = "%s %s (%s): rows %d,%d fetched inside; %d floppy reads to the bracket; after it every row as before " \
           "and the claims as before: %s" % (crs.upper(), way, BB.MAT_NAMES[want_mat], pc, pb, reads,
                                             "yes" if not fails else "NO")
    return fails, line


def choose_ball(g, mat):
    """M until [bz_matsel] is MAT (one press each: the guard needs the key UP
    between presses, so the next waits for [bz_dkk] to clear)"""
    m = g.m
    for _ in range(4):
        if g.b("bz_matsel") == mat:
            return
        M.until(m, lambda _: g.b("bz_dkk") == 0, "the held-key guard to see M come up", guest=5)
        k0 = g.b("bz_matsel")
        g.key("KeyM")
        M.until(m, lambda _: g.b("bz_matsel") != k0, "M to change the ball", guest=5)
    assert g.b("bz_matsel") == mat, "M never reached material %d" % mat


def held_keys(g):
    """SPEC.md 128.11.11.2 on the desktop: -> failures.  Each key's handler is
    counted by a logged breakpoint (C's two modes would hide an odd count)."""
    m = g.m
    fails = []
    for key, h in HANDLERS:
        with M.bp_trace(m, g.a(h), log=True) as tr:
            n0 = tr.count()                     # (a guard left set by an earlier key holds
            m.key(key, up=False)                # ITS make code: it swallows nothing of this one)
            M.pace(m, 1.5)
            m.key(key, down=False)
            # the guard's timer polls a tick at a time (128.11.11.2): a fixed guest
            # interval, then a LOOK, so a guard that never clears is a failure here
            # and the second press below is still judged (the overswallow red's check)
            M.pace(m, .4)
            if g.b("bz_dkk") != 0:
                fails.append("%s released: the guard did not see it come up in 0.4 s (bz_dkk %02Xh)" % (
                    key, g.b("bz_dkk")))
            held = tr.count() - n0
            n1 = tr.count()
            g.key(key)
            M.pace(m, .2)
            g.key(key)
            M.pace(m, .3)
            twice = tr.count() - n1
        print("%s held 1.5 s: %d advance(s); pressed, 0.2 s up, pressed: %d" % (key, held, twice), flush=True)
        if held != 1:
            fails.append("%s held 1.5 s advanced %d times, not once (the typematic repeats were not swallowed)" % (
                key, held))
        if twice != 2:
            fails.append("%s pressed twice 0.2 s apart advanced %d times, not twice (a real second press was "
                         "swallowed)" % (key, twice))
    return fails


def run(tag, ways=WAYS, apps=None, src=None, mats=(0, 1, 2), bench=True, keys=True, mill=True):
    sym = R.symbols(src)
    fails = []
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym, live=True)     # the region is movable and launches claim and drop
        ui.settle()
        m = g.m
        m.pause()
        base_rows, base_claims = rows(g), claims(g)
        m.run()
        nlazy = sum(1 for f, _ in base_rows if f & OP_LAZY)
        print("%s: %d part rows (%d lazy), none fetched on the desktop: %s; the instance's claims %s" % (
            tag, len(base_rows), nlazy, all(not f & OP_FETCHED for f, _ in base_rows), base_claims), flush=True)
        if any(f & OP_FETCHED for f, _ in base_rows):
            fails.append("a part row is fetched on the desktop before any launch")
        R.CRS_K["bench"]                    # (fills the course table: BZ_NCRS of them)
        if len(base_rows) != CRS_ROW0 + dict.__len__(R.CRS_K):
            fails.append("the package has %d part rows, not 3 balls and %d courses (SPEC.md 128.11.3.1)" % (
                len(base_rows), dict.__len__(R.CRS_K)))
        for mat in mats if ways else ():
            choose_ball(g, mat)
            for way in ways:
                f, line = one(g, way, base_rows, base_claims, mat)
                print("%s %s" % (tag, line), flush=True)
                fails += f
                if f:
                    break
            if fails:
                break
        if bench and not fails:
            f, line = one(g, "bench", base_rows, base_claims, 0)
            print("%s %s" % (tag, line), flush=True)
            fails += f
        if mill and not fails:                  # wave 3: MILL (row 6) every way out, and Esc in a tube
            choose_ball(g, R.course("mill").ball)
            for way in [w for w in ways if w in WAYS] + ["tubeesc", "bench"]:
                f, line = one(g, way, base_rows, base_claims, R.course("mill").ball, crs="mill")
                print("%s %s" % (tag, line), flush=True)
                fails += f
                if f:
                    break
        if keys and not fails:
            fails += held_keys(g)
    return fails


BALL_ROW0, CRS_ROW0 = 0, 3                  # SPEC.md 128.11.3.1: BZ_P_BALR, BZ_P_CRS
REDS = {
    # the goal path does not drop the course's row: bz_fin is set only by a play that reached the goal
    "leak": [("bonanza.asm", "    mov al, [bz_pc]\n    call op_drop\n",
              "    cmp byte [bz_fin], 0         ; RED leak: the goal keeps the course\n    jne .redleak\n"
              "    mov al, [bz_pc]\n    call op_drop\n.redleak:\n")],
    # the held-key guard taken out: every typed C, M or N acts
    "crepeat": [("bonanza.asm", "    call bz_dkey                ; AH = the make code: CF = 1 a repeat, swallowed\n"
                 "    jc .done\n", "    ; RED crepeat: no guard\n")],
    # bz_dkk never cleared: the key never reads as come up
    "overswallow": [("bonanza.asm", ".up:\n    mov byte [bz_dkk], 0\n", ".up:                            ; RED overswallow\n")],
}
RED_RUN = {"leak": {"keys": False}, "crepeat": {"ways": (), "bench": False, "mill": False},
           "overswallow": {"ways": (), "bench": False, "mill": False}}
RED_WANT = {"leak": "goal:", "crepeat": "held 1.5 s advanced", "overswallow": "pressed twice"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--no-keys", action="store_true", help="the ways out only")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only: every red arm assembles")
    a = ap.parse_args()
    if a.check:
        for line in R.check_reds(REDS, "bonanza_exit"):
            print(line)
        return
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags:
                try:
                    bad = run(tag, apps=img, src=src, **RED_RUN[a.red])
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(RED_WANT[a.red] in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (a.red, tag, RED_WANT[a.red],
                                                                                    bad)
                if a.red == "leak":
                    assert all(b.startswith("goal:") for b in bad), \
                        "RED ARM leak on %s went red somewhere other than the goal: %s" % (tag, bad)
                print("bonanza_exit --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_exit --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    allbad = []
    for tag in tags:
        bad = run(tag, keys=not a.no_keys)
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d exit failure(s)" % len(allbad)
    print("bonanza_exit (%s): PASS" % ", ".join(tags))


if __name__ == "__main__":
    main()
