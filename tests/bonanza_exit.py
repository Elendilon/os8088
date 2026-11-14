#!/usr/bin/env python3
"""BONANZA: nothing is left behind, and a held key is one press (SPEC.md 128.10.6.2, 128.11.11.2, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_exit.py [--adapter cga|herc|both] [--no-keys]
    python3 tests/bonanza_exit.py --red leak|crepeat|overswallow|padleak|expoff1|rowtab1|cellsafe   (a red arm)
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

WAVE 4 (SPEC.md 128.14.14): a launch fetches the course and EVERY ball its pad
mask names with the starting one (128.14.4.4), so the positive control is the
course's row and each of those balls' rows FETCHED and 1 + that many claims
more; the part rows are 3 + BZ_NCRS + 1 + BZS_NSONG + BZ_NDEMO; MOON and PEAK
(SUMMIT) take every way out above (their GOAL is the CUP: the ball poked at
rest in its mouth holes out, bz_hid); then, with the autopilot driving
(bz_apilot), every way out of a TOUR course - Esc, F, Alt+Enter (each stops
the tour: bz_tour BZ_NTOUR + 2, 8) and the cup (a tour poked to stand at MOON) - and a tour
stopped on the face, V's fetch and drop, D's end, W through the Save dialog, L
through the Open dialog and the DOUBLE-CLICK of the saved .BZR (a new
instance): every row as before and the claims as before after each.
  padleak      the glass ball's row not dropped at a cup: MOON's goal leaves
               row 2 fetched

WAVE 5B (SPEC.md 128.15.4.5, 128.15.13): THE CLAIM LEG.  A course part is
fetched in its STORED form and expanded in place by bz_cexp; between that
(and bz_hxlat on the Hercules) and OSAPI_FSX_RUN nothing writes it, and inside
the bracket the lanes' writer does.  So EVERY launch the row makes - FIRST,
MILL, MOON, PEAK, BENCH (B), the tour's (FIRST, and MOON at the cup), D's
(FIRST's demo) and one launch of TRIAL added for this leg (Enter, then Esc) -
stops at the kernel's fsx_run (a kernel address: the package's region may
move while the launch claims), and there the course claim ([bz_cseg], found
in the heap map, at least the part's length) must equal byte for byte the
tool's RAM form under the build's RECB (bbcourse's cga4 / cga8; the art's
BZ<K>.BIN checked to be the same compile's stored form) on the CGA, or its
htab() translation on the Hercules; a difference names the first offset and
its BZC2 section.  The full run must have compared all six shipped courses.
V opens no bracket and is checked as before.  Red arms, each red at the claim
leg's first differing offset:
  expoff1      WDIFF's count one record short (the last record left as its
               differences): the first launch (FIRST)
  rowtab1      ROWTAB writes NROWS - 1 words: the first launch (FIRST)
  cellsafe     the guest's SAFE rule without its OBS test (bz_cxsafe): a prop's
               cell made SAFE - MILL (the first course with props)

WAVE 6 (SPEC.md 128.16.6, 128.16.8, 128.16.14): the PLAYGROUND (course 6,
`PLAY`) takes every way out as MOON and PEAK do - its three pads, so its three
ball rows fetched and dropped; the tour is SIX courses, so a stopped tour's
bz_tour is BZ_NTOUR + 2 (derived from BZ_COURSES, not written here); the claim
leg covers seven courses.  And THE PALETTE, once a card: a launch of the
PLAYGROUND and one of FIRST, each stopped at the kernel's fsx_run and then at
the first of bz_vinit.vpal (bz_vinit's labelled `out` to 3D9h, resolved through the
package's own symbols) and bz_presented:
  - on the CGA bz_vinit.vpal is reached first with AL the course's BZ_CRS_PALS byte
    (read out of the guest's own table, bz_cpals); a few frames later, the
    ball at rest, MartyPC's RENDERED frame (m.fbuf), aligned on the card's own
    picture, shows the ball's body index - the most common non-black index in
    its 16 x 16 footprint - in the colour that byte selects (the PLAYGROUND's
    10h: palette 0's light red; FIRST's 30h: palette 1's light magenta), and
    every index the frame holds in its byte's colour: nearest of the CGA's
    sixteen, so MartyPC's exact RGB is not this row's business;
  - on the Hercules bz_presented is reached first: bz_vinit.vpal is NEVER hit;
  - after each bracket the desktop renders only the COLOURS its capture before
    the launch held, both of them (the menu bar's band left out): 3D9h's low
    nibble is the 1bpp desktop's foreground, so a colour select left behind
    shows there.  Not the bitmap: BONANZA's own window is in the frame and
    its face is rewritten after every play, Esc included (the review's F1).
  Red arms:
  nopal        the `out` left out: the PLAYGROUND's rendered colour (palette 1's,
               the BIOS's 30h)
  hercpal      the bz_herc branch round the write removed, so it runs on the
               Hercules: the bz_vinit.vpal breakpoint is hit there
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
import importlib.util          # noqa: E402


def _tools_heapmap():
    """tools/heapmap.py BY PATH: tests/ is first on sys.path, and
    tests/heapmap.py (QEMU's census, a different module of the same name)
    shadows it whenever nothing imported the tools one first - as when
    bonanzademo imports this row (the final pass of wave 4)"""
    mod = sys.modules.get("heapmap")
    if mod is not None and hasattr(mod, "Map"):
        return mod
    spec = importlib.util.spec_from_file_location("os88_tools_heapmap", os.path.join(ROOT, "tools", "heapmap.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


heapmap = _tools_heapmap()
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


def nsong():
    """the songs, one part each after the sound part (bbmusic's bzsnd.inc)"""
    import re
    inc = open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzsnd.inc")).read()
    return int(re.search(r"^BZS_NSONG\s+equ\s+(\d+)", inc, re.M).group(1))


def ndemo():
    """the shipped demos, one part each after the songs (bzcourse.inc's BZ_NDEMO, SPEC.md 128.14.7.4)"""
    import re
    inc = open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzcourse.inc")).read()
    m_ = re.search(r"^BZ_NDEMO\s+equ\s+(\d+)", inc, re.M)
    return int(m_.group(1)) if m_ else 0


def balls(crs, mat):
    """the ball rows a launch of CRS fetches (SPEC.md 128.14.4.4): the starting
    material's and every one its PAD MASK names"""
    return sorted({mat} | {r["mat"] for r in R.course(crs).part["props"] if r["kind"] == BB.PK_PAD})


def title_rows():
    """the two rows the desktop's title holds while the window is open: the
    sound part and song 0 (SPEC.md 128.20.6) - after the courses' rows"""
    R.CRS_K["bench"]
    snd = CRS_ROW0 + dict.__len__(R.CRS_K)
    return {snd, snd + 1}


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


# ---- WAVE 5B (SPEC.md 128.15.13): THE CLAIM LEG --------------------------------------
CLAIMED = {}                    # tag -> the courses whose claim was compared, by name


def build_rec(art=None):
    """the build's RECB (bonanza_ring.build_rec: one reader of bzcourse.inc)"""
    return R.build_rec(art)


_RAM = {}


def ram_form(k, tag, art=None):
    """course K's part as the card holds it between bz_cexp (and bz_hxlat on
    the Hercules) and OSAPI_FSX_RUN (SPEC.md 128.15.4.5): THE TOOL'S RAM FORM
    under the build's RECB (bbcourse's cga4 / cga8), or its htab() translation
    (herc_translate_course).  The art's BZ<K>.BIN must be the same compile's
    STORED form, or the comparison would be with another tree's courses."""
    art = art or R.at("build/bonanza-art")
    key = (k, tag, art)
    if key not in _RAM:
        c = R.course_k(k)
        rec = build_rec(art)
        ram, stored = (c.cga4, c.stored4) if rec == 4 else (c.cga8, c.stored8)
        with open(os.path.join(ROOT, art, "BZ%d.BIN" % k), "rb") as f:
            if f.read() != stored:
                raise SystemExit("%s/BZ%d.BIN is not this tree's course %s as stored under RECB %d: the art is "
                                 "stale (`make bonanzadisk`)" % (art, k, c.name, rec))
        _RAM[key] = BB.herc_translate_course(ram) if tag == "herc" else bytes(ram)
    return _RAM[key]


def section_at(ram, off):
    """the BZC2 section holding OFF (its directory's tag), or the header / the directory"""
    if off < 48:
        return "the header"
    diroff, nsec = struct.unpack_from("<HH", ram, 38)
    for i in range(nsec):
        tg, _fm, so, sl, _dl = struct.unpack_from("<BBHHH", ram, diroff + 8 * i)
        if so <= off < so + sl:
            return "section %s (+%d)" % (chr(tg), off - so)
    return "the directory" if off >= diroff else "no section"


def claim_check(g, what):
    """THE CLAIM LEG (SPEC.md 128.15.13), at the kernel's fsx_run - the
    launch's OSAPI_FSX_RUN call, after bz_cexp and bz_hxlat, before the lanes'
    writer: the course claim ([bz_cseg], found in the heap map, its claim at
    least the part's length) equal byte for byte to the tool's RAM form (CGA)
    or its htab() translation (Hercules).  -> failures"""
    m = g.m
    k = g.b("bz_crs")
    R.CRS_K["bench"]                            # (fills the course table)
    name = [n for n in R.CRS_K if R.CRS_K[n] == k][0]
    want = ram_form(k, g.tag)
    seg = g.w("bz_cseg")
    mp = heapmap.Map(Q(m), {n: m.sym(n) for n in ("mem_base", "mem_top", "spl_live", "mem_tab")})
    cl = [c for c in mp.claims if c.seg == seg]
    if not cl:
        return ["%s: claim leg, %s: [bz_cseg] %04X is no claim of the heap map" % (what, name.upper(), seg)]
    if cl[0].para * 16 < len(want):
        return ["%s: claim leg, %s: the course claim at %04X is %d bytes, the RAM form %d" % (
            what, name.upper(), seg, cl[0].para * 16, len(want))]
    got = bytes(m.read(seg * 16, len(want)))
    CLAIMED.setdefault(g.tag, set()).add(name)
    if got == want:
        return []
    bad = [i for i in range(len(want)) if got[i] != want[i]]
    return ["%s: claim leg, %s: the course claim differs from the tool's RAM form%s at %d byte(s), the first at "
            "offset %d in %s (%02Xh, the tool's %02Xh) - SPEC.md 128.15.13" % (
                what, name.upper(), " through htab()" if g.tag == "herc" else "", len(bad), bad[0],
                section_at(want if g.tag == "cga" else ram_form(k, "cga"), bad[0]), got[bad[0]], want[bad[0]])]


def at_fsx(g, what, fails):
    """the launch armed with a STOP at the kernel's fsx_run (a kernel address:
    the package's region may move while the launch claims), already under way:
    wait for it, run the claim leg into FAILS, and let the bracket run"""
    m = g.m
    st = m.wait_stop(60)
    assert st == "breakpoint", "%s: the launch never reached OSAPI_FSX_RUN (state %r)" % (what, st)
    fails += claim_check(g, what)
    m.bp_exec()
    m.run()


def launch(g, way, crs=None, fails=None):
    """Start the launch that WAY leaves by - on course CRS ([bz_crs] poked at
    bz_launch's entry; a replay's course is its log's) - with THE CLAIM LEG at
    its OSAPI_FSX_RUN call (failures into FAILS); -> the floppy reads it took,
    once the bracket is up (both parts fetched)."""
    m = g.m
    fails = [] if fails is None else fails
    m.disk(reset=True)
    key = "KeyB" if way == "bench" else "KeyR" if way.startswith("replay") else "Enter"
    if crs and not way.startswith("replay"):
        m.bp_exec(g.a("bz_launch"))
        g.key(key)
        assert m.wait_stop(60) == "breakpoint", "%s did not reach bz_launch" % key
        g.putb("bz_crs", R.CRS_K[crs])
        m.bp_exec(m.sym("fsx_run"))
        m.run()
    else:
        m.bp_exec(m.sym("fsx_run"))
        g.key(key)
    at_fsx(g, way, fails)
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "the bracket is up (%s)" % way, guest=60)
    m.pause()
    return m.disk()["reads"]


def keyed_launch(g, key, what, fails):
    """KEY (G, Enter, D: a launch of the package's own choosing) with the claim leg at its fsx_run"""
    g.m.bp_exec(g.m.sym("fsx_run"))
    g.key(key)
    at_fsx(g, what, fails)


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
    cup = [r for r in R.course(crs).part["props"] if r["kind"] == BB.PK_CUP]
    if crs == "first":
        (wx, wy), gvx, gvy, _ = P.SCEN["goal"]
    elif cup:                                   # wave 4: the CUP, the ball at rest in its mouth
        (wx, wy), gvx, gvy = cup[0]["at"], 0, 0
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
    reads = launch(g, way, None if crs == "first" else crs, fails)
    pc, pb = g.b("bz_pc"), g.b("bz_pb")
    r_in, c_in = rows(g), claims(g)
    crs_b = "bench" if (way == "bench" and crs == "first") else crs
    nb = balls(crs_b, want_mat)
    for i in [pc] + [BALL_ROW0 + b_ for b_ in nb]:
        f, z = r_in[i]
        if not f & OP_FETCHED or not z:
            fails.append("%s: inside the bracket row %d is not fetched (flags %02X zkb %04X): the control cannot "
                         "see a part that is there" % (way, i, f, z))
    if g.b("bz_mat") != want_mat or pb != BALL_ROW0 + want_mat or pc != CRS_ROW0 + g.b("bz_crs"):
        fails.append("%s: the launch rolls material %d from row %d with course row %d; want material %d, rows %d "
                     "and %d (SPEC.md 128.11.3.1)" % (way, g.b("bz_mat"), pb, pc, want_mat, BALL_ROW0 + want_mat,
                                                     CRS_ROW0 + g.b("bz_crs")))
    if len(c_in) != len(base_claims) + 1 + len(nb):
        fails.append("%s: inside the bracket the instance holds %d claims, not the desktop's %d + 1 + %d balls: %s" % (
            way, len(c_in), len(base_claims), len(nb), c_in))
    if way == "bench":
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark's 1,200 frames", guest=120)
    elif way == "goal":
        goal(g, crs)
        M.until(m, lambda _: g.b("bz_fs") == 0, "the play to end at the goal", guest=60)
        if not g.b("bz_fin"):
            fails.append("goal: the play ended but [bz_fin] is clear - it did not end at the goal")
        if [r for r in R.course(crs).part["props"] if r["kind"] == BB.PK_CUP] and not g.b("bz_hid"):
            fails.append("goal: %s's play ended without holing out ([bz_hid] 0)" % crs.upper())
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
    if "bzs_desk" in g.sym:                     # ...and the title's parts READ BACK: bz_launch's last
        M.until(m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3,   # act (SPEC.md 128.20.6)
                "the title to be back (%s)" % way, guest=30)
    m.pause()
    r_out, c_out = rows(g), claims(g)
    title = title_rows()
    for i, (before, after) in enumerate(zip(base_rows, r_out)):
        if i in title:                      # the title's music, held on the desktop
            if (after[0] & OP_FETCHED) != (before[0] & OP_FETCHED):
                fails.append("%s: the title's part row %d is %s after the launch, %s before (SPEC.md 128.20.6)"
                             % (way, i, "fetched" if after[0] & OP_FETCHED else "not fetched",
                                "fetched" if before[0] & OP_FETCHED else "not fetched"))
            continue
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


def after(g, what, base_rows, base_claims):
    """every part row back as it was on the desktop and the claims as before:
    -> failures (one()'s post-launch checks, for a leg that is not one launch)"""
    m = g.m
    fails = []
    M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "%s: the parts dropped" % what, guest=30)
    if "bzs_desk" in g.sym:
        M.until(m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3, "%s: the title back" % what, guest=30)
    m.pause()
    r_out, c_out = rows(g), claims(g)
    m.run()
    title = title_rows()
    for i, (before, aft) in enumerate(zip(base_rows, r_out)):
        if i in title:
            continue
        if aft[0] & OP_FETCHED:
            fails.append("%s: part row %d is still FETCHED" % (what, i))
        if aft[1] != before[1]:
            fails.append("%s: part row %d's zkb is %04X, %04X before" % (what, i, aft[1], before[1]))
    if c_out != base_claims:
        fails.append("%s: the instance's claims %s, before %s" % (what, c_out, base_claims))
    print("%s %s: every part row and the claims as before: %s" % (g.tag, what, "yes" if not fails else "NO"),
          flush=True)
    return fails


def ntour():
    """bonanza.asm BZ_NTOUR: every course but BENCH (BZ_COURSES's, six with the PLAYGROUND)"""
    R.CRS_K["bench"]
    return dict.__len__(R.CRS_K) - 1


def guard(g):
    M.until(g.m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)


def wave4_exits(g, ui, base_rows, base_claims):
    """SPEC.md 128.14.14: every way out of a TOUR course (Esc, F, Alt+Enter, the
    cup) and a tour stopped on the face; V's fetch and drop, D's end, W, L and
    the double-click - each with the rows and the claims as before"""
    m = g.m
    fails = []
    m.pause()
    g.putb("bz_apilot", 1)
    m.run()
    for way in ("esc", "f", "altenter"):
        guard(g)
        keyed_launch(g, "KeyG", "tour %s" % way, fails)
        M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "tour course 1 (%s)" % way, guest=60)
        leave(g, way)
        M.until(m, lambda _: g.b("bz_fs") == 0, "tour course 1 to end on %s" % way, guest=60)
        fails += after(g, "tour %s" % way, base_rows, base_claims)
        if g.b("bz_tour") != ntour() + 2:
            fails.append("tour %s: [bz_tour] %d after the way out, not %d (stopped)" % (
                way, g.b("bz_tour"), ntour() + 2))
    m.pause()
    g.putb("bz_tour", R.CRS_K["moon"])          # a tour standing at MOON: Enter plays it
    m.run()
    keyed_launch(g, "Enter", "tour MOON", fails)
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "tour MOON", guest=60)
    goal(g, "moon")
    M.until(m, lambda _: g.b("bz_fs") == 0, "tour MOON to end at its cup", guest=60)
    fails += after(g, "tour cup", base_rows, base_claims)
    if not g.b("bz_hid"):
        fails.append("tour cup: MOON's play did not hole out")
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_tour") == ntour() + 2, "Esc on the face to stop the tour", guest=10)
    fails += after(g, "tour stopped on the face", base_rows, base_claims)
    m.pause()
    g.putb("bz_vk", 0)
    m.run()
    guard(g)
    g.key("KeyV")
    M.until(m, lambda _: g.b("bz_vk") == 1, "V to load FIRST's shipped demo", guest=20)
    fails += after(g, "V", base_rows, base_claims)
    guard(g)
    keyed_launch(g, "KeyD", "D of FIRST's demo", fails)
    M.until(m, lambda _: g.b("bz_fs") == 1, "D's bracket", guest=60)
    M.until(m, lambda _: g.b("bz_fs") == 0, "D to its end", guest=120)
    fails += after(g, "D's end", base_rows, base_claims)
    guard(g)
    g.key("KeyW")
    ui.chooser_save("EXIT.BZR")
    ui.wait_toast(says="Demo saved")
    fails += after(g, "W", base_rows, base_claims)
    guard(g)
    g.key("KeyL")
    ui.chooser_open("EXIT.BZR")
    M.guest_sleep(m, 1.0)
    fails += after(g, "L", base_rows, base_claims)
    ui.close(g.win)
    dw = R.disk_b(ui)
    ui.open("SYSTEM", expect="nav", win=dw)      # (in and out: the listing re-read with EXIT.BZR)
    ui.open("..", expect="nav", win=dw)
    ui.open("EXIT.BZR")                          # the double-click: a new instance with the log
    g2 = R.Bz(ui, g.tag, g.sym, live=True)
    ui.settle()
    if bytes(m.read(g2.a("bz_rlog"), 4)) != b"BZR1":
        fails.append("double-click: BONANZA opened without EXIT.BZR's log")
    fails += after(g2, "the double-click", base_rows, base_claims)
    return fails


# the CGA's sixteen as an RGB monitor shows them (IRGB, brown's half green): a rendered colour is
# judged by the NEAREST of these, so the check reads which colour, not MartyPC's exact RGB
CGA16 = [(0, 0, 0), (0, 0, 170), (0, 170, 0), (0, 170, 170), (170, 0, 0), (170, 0, 170), (170, 85, 0),
         (170, 170, 170), (85, 85, 85), (85, 85, 255), (85, 255, 85), (85, 255, 255), (255, 85, 85),
         (255, 85, 255), (255, 255, 85), (255, 255, 255)]
CGA16_NAMES = ("black", "blue", "green", "cyan", "red", "magenta", "brown", "light grey", "dark grey",
               "light blue", "light green", "light cyan", "light red", "light magenta", "yellow", "white")
MENU_EIGHTH = 8                             # the rendered frame's top 1/8 (the menu bar and its clock, with the
                                            # border above it) left out of the desktop compare


def pal_colour(byte, idx):
    """the CGA colour (0 - 15) that colour-select BYTE (3D9h, SPEC.md 128.16.6)
    gives mode 4's index IDX: 0 the ground (bits 0 - 3); 1 - 3 palette 1's
    cyan, magenta, white or palette 0's green, red, brown (bit 5), +8 bright
    (bit 4)"""
    if idx == 0:
        return byte & 15
    base = (3, 5, 7) if byte & 0x20 else (2, 4, 6)
    return base[idx - 1] + (8 if byte & 0x10 else 0)


def nearest16(rgb):
    return min(range(16), key=lambda i: sum((a - b) * (a - b) for a, b in zip(rgb, CGA16[i])))


def rendered_indices(fw, fh, fd, exp):
    """the rendered frame aligned on the card's own 320 x 200 picture EXP (by
    black / not black on a sample, as bonanza_ring.glass_cga): -> {index:
    {nearest CGA colour: pixels}}, and the field's origin"""
    sx, sy = max(1, fw // 320), max(1, fh // 200)
    best = None
    for y0 in range(0, fh - 200 * sy + 1):
        for x0 in range(0, fw - 320 * sx + 1):
            bad = 0
            for y in range(0, 200, 9):
                for x in range(0, 320, 5):
                    o = ((y0 + sy * y) * fw + x0 + sx * x) * 3
                    bad += (fd[o:o + 3] == b"\0\0\0") != (exp[y][x] == 0)
            if best is None or bad < best[0]:
                best = (bad, x0, y0)
    _, x0, y0 = best
    out = {}
    for y in range(200):
        for x in range(320):
            o = ((y0 + sy * y) * fw + x0 + sx * x) * 3
            c = nearest16(tuple(fd[o:o + 3]))
            d = out.setdefault(exp[y][x], {})
            d[c] = d.get(c, 0) + 1
    return out, (x0, y0, sx, sy)


def desktop_colours(a):
    """a rendered desktop: -> the set of RGB triples below the menu band"""
    w, h, x = a
    out = set()
    for r in range(h // MENU_EIGHTH, h):
        row = x[r * w * 3:(r + 1) * w * 3]
        for c in range(0, 3 * w, 3):
            out.add(bytes(row[c:c + 3]))
    return out


def palette_leg(g, crss=("play", "first")):
    """SPEC.md 128.16.6 (bonanzaexit's wave 6 leg): the colour select on the
    CGA, none on the Hercules, the desktop restored after each bracket"""
    m, tag = g.m, g.tag
    fails, say = [], []
    for crs in crss:
        k = R.CRS_K[crs]
        ui_settle(g)
        m.pause()
        before = m.fbuf(0)
        byte = m.read(g.a("bz_cpals") + k, 1)[0]
        m.bp_exec(g.a("bz_launch"))
        m.run()
        g.key("Enter")
        assert m.wait_stop(60) == "breakpoint", "palette %s: Enter did not reach bz_launch" % crs
        g.putb("bz_crs", k)
        m.bp_exec(m.sym("fsx_run"))
        m.run()
        assert m.wait_stop(60) == "breakpoint", "palette %s: the launch never reached OSAPI_FSX_RUN" % crs
        vpal, pres = g.a("bz_vinit.vpal"), g.a("bz_presented")    # (inside the bracket the region stays put)
        m.bp_exec(vpal, pres)
        m.run()
        assert m.wait_stop(60) == "breakpoint", "palette %s: neither bz_vinit.vpal nor bz_presented reached" % crs
        r = m.regs()
        at = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
        if tag == "herc":
            if at == vpal:
                fails.append("palette %s: the bz_vinit.vpal breakpoint was HIT on the Hercules (AL %02Xh): the "
                             "colour select written to 3D9h where the picture has no palette (SPEC.md 128.16.6)"
                             % (crs.upper(), r["ax"] & 0xFF))
            say.append("%s: bz_presented first, bz_vinit.vpal never hit" % crs.upper())
        else:
            if at != vpal:
                fails.append("palette %s: the first frame presented with no write at bz_vinit.vpal" % crs.upper())
            elif (r["ax"] & 0xFF) != byte or (r["dx"] & 0xFFFF) != 0x3D9:
                fails.append("palette %s: bz_vinit.vpal writes %02Xh to port %04Xh, the course's BZ_CRS_PALS byte is "
                             "%02Xh to 3D9h" % (crs.upper(), r["ax"] & 0xFF, r["dx"], byte))
        m.bp_exec()
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 20, "palette %s: the play runs" % crs,
                guest=60)
        if tag == "cga":
            m.bp_exec(g.a("bz_presented"))
            seen = None
            for _ in range(4):                  # the ball at rest: every refresh scanned one picture
                m.run()
                assert m.wait_stop(60) == "breakpoint", "palette %s: play stopped presenting" % crs
                seen = g.state()
            m.bp_exec()
            S, R0, c0, px, py = seen
            exp = g.decode(S)
            fw, fh, fd = m.fbuf(0)
            got, org = rendered_indices(fw, fh, fd, exp)
            bx, by = px - 8 * c0, py - R0 * R.RL[tag]
            cnt = {}
            for y in range(max(0, by), min(200, by + 16)):
                for x in range(max(0, bx), min(320, bx + 16)):
                    v = exp[y][x]
                    if v:
                        cnt[v] = cnt.get(v, 0) + 1
            body = max(cnt, key=cnt.get) if cnt else None
            want = {i: pal_colour(byte, i) for i in got}
            seen_c = {i: max(d, key=d.get) for i, d in got.items()}
            if body is None:
                fails.append("palette %s: no ball pixel in the footprint at %d,%d" % (crs.upper(), bx, by))
            elif seen_c.get(body) != want[body]:
                fails.append("palette %s: the ball's body (index %d) is rendered %s; its BZ_CRS_PALS byte %02Xh "
                             "selects %s" % (crs.upper(), body, CGA16_NAMES[seen_c.get(body, 0)], byte,
                                             CGA16_NAMES[want[body]]))
            mix = {i: sorted(d) for i, d in got.items() if len(d) > 1 or seen_c[i] != want[i]}
            if mix and not [f for f in fails if f.startswith("palette %s: the ball" % crs.upper())]:
                fails.append("palette %s: indices rendered off the byte's colours: %s (want %s)" % (
                    crs.upper(), {i: [CGA16_NAMES[c] for c in v] for i, v in mix.items()},
                    {i: CGA16_NAMES[want[i]] for i in mix}))
            say.append("%s: byte %02Xh, the ball's body index %s rendered %s" % (
                crs.upper(), byte, body, CGA16_NAMES[seen_c.get(body, 0)] if body is not None else "-"))
        m.run()
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0, "palette %s: the play to end on Esc" % crs, guest=60)
        M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "palette %s: its parts dropped" % crs,
                guest=30)
        ui_settle(g)
        m.pause()
        after = m.fbuf(0)
        m.run()
        # (the review's F1: BONANZA's own window is IN the frame and bz_post rewrites its face after every play,
        # Esc included, so a bitmap compare fails a correct build.  What the leg is about is the desktop's
        # PALETTE: the exit mode set must leave the 1bpp desktop's two colours, which a colour select left
        # behind would change - 3D9h's low nibble is mode 6's foreground - so the COLOURS are compared)
        cb, ca = desktop_colours(before), desktop_colours(after)
        if not ca <= cb or len(ca) < min(2, len(cb)):
            fails.append("palette %s: after the bracket the desktop renders the colours %s, before it %s: the "
                         "palette not restored" % (crs.upper(), sorted(c.hex() for c in ca),
                                                   sorted(c.hex() for c in cb)))
    print("%s palette (SPEC.md 128.16.6): %s; the desktop restored after each: %s" % (
        tag, "; ".join(say), "yes" if not fails else "NO"), flush=True)
    return fails


def ui_settle(g):
    """the desktop quiet: the title's face drawn, nothing moving"""
    M.until(g.m, lambda _: g.b("bz_fs") == 0, "the desktop", guest=30)
    if "bzs_desk" in g.sym:
        M.until(g.m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3, "the title back", guest=30)
    g.ui.settle()


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


def run(tag, ways=WAYS, apps=None, src=None, mats=(0, 1, 2), bench=True, keys=True, mill=True, w4=True,
        trial=True, cover=True, pal=True):
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
        title = title_rows()
        if any(f & OP_FETCHED for i, (f, _) in enumerate(base_rows) if i not in title):
            fails.append("a part row is fetched on the desktop before any launch")
        if any(not base_rows[i][0] & OP_FETCHED for i in title):
            fails.append("the title's parts (rows %s) are not held on the desktop (SPEC.md 128.20.6)"
                         % sorted(title))
        R.CRS_K["bench"]                    # (fills the course table: BZ_NCRS of them)
        if len(base_rows) != CRS_ROW0 + dict.__len__(R.CRS_K) + 1 + nsong() + ndemo():
            fails.append("the package has %d part rows, not 3 balls, %d courses, the sound, %d songs and %d "
                         "shipped demos (SPEC.md 128.11.3.1, 128.20.3, 128.14.7.4)" % (
                             len(base_rows), dict.__len__(R.CRS_K), nsong(), ndemo()))
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
        if w4 and not fails:                    # wave 4: MOON and PEAK (SUMMIT), their three balls; wave 6:
            for crs in ("moon", "peak", "play"):    # the PLAYGROUND's three pads (SPEC.md 128.16.14)
                choose_ball(g, R.course(crs).ball)
                for way in [w for w in ways if w in WAYS]:
                    f, line = one(g, way, base_rows, base_claims, R.course(crs).ball, crs=crs)
                    print("%s %s" % (tag, line), flush=True)
                    fails += f
                    if f:
                        break
                if fails:
                    break
        if trial and not fails:                 # wave 5b: TRIAL's one launch, for the claim leg (Enter, Esc)
            choose_ball(g, R.course("trial").ball)
            f, line = one(g, "esc", base_rows, base_claims, R.course("trial").ball, crs="trial")
            print("%s %s" % (tag, line), flush=True)
            fails += f
        if pal and not fails:                   # wave 6 (SPEC.md 128.16.6): the colour select
            fails += palette_leg(g)
        if keys and not fails:
            fails += held_keys(g)
        if w4 and not fails:                    # (last: it closes the window)
            fails += wave4_exits(g, ui, base_rows, base_claims)
        R.CRS_K["bench"]
        seen = CLAIMED.get(tag, set())
        print("%s THE CLAIM LEG (SPEC.md 128.15.13): the course claim = the tool's RAM form at fsx_run on %s" % (
            tag, ", ".join(sorted(n.upper() for n in seen)) or "no launch"), flush=True)
        if cover and not fails and seen != set(dict.keys(R.CRS_K)):
            fails.append("the claim leg compared %s, not all %d shipped courses (SPEC.md 128.15.13)" % (
                sorted(seen), dict.__len__(R.CRS_K)))
    return fails


BALL_ROW0, CRS_ROW0 = 0, 3                  # SPEC.md 128.11.3.1: BZ_P_BALR, BZ_P_CRS
REDS = {
    # the goal path does not drop the course's row: bz_fin is set only by a play that reached the goal
    "leak": [("bonanza.asm", "    jb .dball\n    mov al, [bz_pc]\n    call op_drop\n",
              "    jb .dball\n    cmp byte [bz_fin], 0         ; RED leak: the goal keeps the course\n"
              "    jne .redleak\n    mov al, [bz_pc]\n    call op_drop\n.redleak:\n")],
    # the held-key guard taken out: every typed C, M or N acts
    "crepeat": [("bonanza.asm", "    call bz_dkey                ; AH = the make code: CF = 1 a repeat, swallowed\n"
                 "    jc .done\n", "    ; RED crepeat: no guard\n")],
    # bz_dkk never cleared: the key never reads as come up
    "overswallow": [("bonanza.asm", ".up:\n    mov byte [bz_dkk], 0\n", ".up:                            ; RED overswallow\n")],
}
REDS["padleak"] = [("bonanza.asm", ".dball:                         ; of a part that is not here is a no-op, so\n"
                    "    call op_drop                ; all go whichever failed; it preserves AX)\n",
                    ".dball:                         ; RED padleak: the glass ball kept at the cup\n"
                    "    cmp al, BZ_P_BALG\n    jne .rpl\n    cmp byte [bz_hid], 0\n    jne .rpl2\n.rpl:\n"
                    "    call op_drop\n.rpl2:\n")]
# wave 5b (SPEC.md 128.15.13): the expansion broken, each red at the CLAIM LEG's first differing offset -
# WDIFF's count one record short (the last record left as differences), ROWTAB's last word never written,
# and the guest's SAFE rule without its OBS test (a prop's cell made SAFE: MILL's first)
REDS["expoff1"] = [("bonanza.asm", "    sub cx, bx\n    shr cx, 1                   ; the words after the first record\n",
                    "    sub cx, bx\n    sub cx, bx                  ; RED expoff1: one record short\n"
                    "    shr cx, 1                   ; the words after the first record\n")]
REDS["rowtab1"] = [("bonanza.asm", "bz_cxrtb:\n    mov bx, [es:BZC_GRID]\n    mov cx, [es:bx + BZG_NROWS]\n",
                    "bz_cxrtb:\n    mov bx, [es:BZC_GRID]\n    mov cx, [es:bx + BZG_NROWS]\n"
                    "    dec cx                      ; RED rowtab1: NROWS - 1 words\n")]
REDS["cellsafe"] = [("bonanza.asm", "    test ah, BZ_FL_OBS          ; a prop's cell: never SAFE\n    jnz .no\n",
                     "    ; RED cellsafe: no OBS test\n")]
RED_RUN = {"leak": {"keys": False}, "crepeat": {"ways": (), "bench": False, "mill": False},
           "overswallow": {"ways": (), "bench": False, "mill": False}}
RED_RUN["padleak"] = {"keys": False, "mats": (), "bench": False, "mill": False, "w4": True}
RED_RUN["leak"]["w4"] = False
RED_RUN["crepeat"]["w4"] = RED_RUN["overswallow"]["w4"] = False
for _r in ("expoff1", "rowtab1"):               # the first launch: FIRST, Esc
    RED_RUN[_r] = {"ways": ("esc",), "mats": (0,), "bench": False, "mill": False, "w4": False, "keys": False}
RED_RUN["cellsafe"] = {"ways": ("esc",), "mats": (), "bench": False, "mill": True, "w4": False, "keys": False}
# wave 6 (SPEC.md 128.16.14): the colour select's write left out (the PLAYGROUND renders palette 1), and its
# Hercules branch removed (the labelled write runs there)
REDS["nopal"] = [("bzvideo.inc", ".vpal:\n    out dx, al\n",
                  ".vpal:\n    nop                         ; RED nopal: no write\n")]
REDS["hercpal"] = [("bzvideo.inc", "    mov [bz_vseg], ax\n    cmp byte [bz_herc], 0\n    jne .herc\n"
                    "    mov bl, [bz_crs]            ; the CGA: the course's colour select\n"
                    "    xor bh, bh\n    mov al, [bz_cpals + bx]\n    mov dx, 3d9h\n.vpal:\n    out dx, al\n",
                    "    mov [bz_vseg], ax\n    mov bl, [bz_crs]            ; RED hercpal: the write on the Hercules too\n"
                    "    xor bh, bh\n    mov al, [bz_cpals + bx]\n    mov dx, 3d9h\n.vpal:\n    out dx, al\n"
                    "    cmp byte [bz_herc], 0\n    jne .herc\n")]
for _r in ("nopal", "hercpal"):
    RED_RUN[_r] = {"ways": (), "mats": (), "bench": False, "mill": False, "w4": False, "keys": False}
for _r in RED_RUN:                              # (only the full run covers all seven courses, and only the
    RED_RUN[_r].setdefault("cover", False)      # claim reds' own runs need TRIAL's launch; only the palette
    RED_RUN[_r].setdefault("trial", False)      # reds' the palette leg)
    RED_RUN[_r].setdefault("pal", _r in ("nopal", "hercpal"))
RED_WANT = {"padleak": "part row 2 is still FETCHED", "leak": "goal:", "crepeat": "held 1.5 s advanced", "overswallow": "pressed twice",
            "expoff1": "claim leg, FIRST", "rowtab1": "claim leg, FIRST", "cellsafe": "claim leg, MILL",
            "nopal": "palette PLAY: the ball's body", "hercpal": "bz_vinit.vpal breakpoint was HIT"}
RED_TAGS = {"nopal": ("cga",), "hercpal": ("herc",)}    # each palette red goes red on its own card


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
    if a.red and a.red in RED_TAGS:
        tags = tuple(t for t in tags if t in RED_TAGS[a.red]) or RED_TAGS[a.red]
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
