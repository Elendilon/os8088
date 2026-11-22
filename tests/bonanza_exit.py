#!/usr/bin/env python3
"""BONANZA: nothing is left behind, and a held key is one press (SPEC.md 130.10.6.2, 130.11.11.2, 130.11.17.2).

    make bonanzadisk && python3 tests/bonanza_exit.py [--adapter cga|herc|both] [--no-keys]
    python3 tests/bonanza_exit.py --red NAME                    (a red arm, below)
    python3 tests/bonanza_exit.py --check            (the host half: the red arms assemble, the test courses
                                                      carry what each leg and each red arm is aimed at)

ON THE TEST COURSES (SPEC.md 130.54, docs/plans/BOUNCE-BONANZA-SOAK.md phase 3): ONE BOOT A CARD, and
every leg on a course built for it, found by NAME - TQUIK (the goal 165 autopilot steps from the start, a
KEEP tube off the route, `palette 0`), TCUP (the cup, steel, the default palette) and BENCH (B's own) -
never on a prototype course.  The balls are HELD in the resident bundle (130.25.5.2), so one ball's pass
is the test: there is no loop over the materials any more.

A launch fetches course K's lazy, compressed part (row K) - and a two-part course its world part too
(130.30.5) - and holds them for the bracket's whole life, so they stay PINNED and every way out must drop
them.  This row takes every way out, on every card:

    Esc, F, Alt+Enter    a play of TQUIK (F, [bz_crs] poked at bz_launch), left by that key
    the goal             a play of TQUIK whose ball is POKED onto its first GOAL cell at bz_t0: the play
                         ends the frame after
    a replay's end       R, a log of TQUIK (the row writes it into bz_rlog: 120 steps), run to its end
    Esc in a replay      R, a log of 600 steps, left by Esc
    Esc while HIDDEN     TQUIK, the ball poked into its KEEP tube's IN cell (a drain) and Esc taken while
                         [bz_tube] says it is inside
    the cup              TCUP, the ball poked at rest in its cup's mouth: holes out ([bz_hid]) and ends
    the benchmark's end  B, BENCH (B's own course), its end path reached a few frames in: [bz_frames]
                         poked to BZ_BENCH less BENCH_TAIL once the bracket is up (the end is the same
                         compare at frame 1,200; nothing here needs the 1,200 frames before it)
    the world part       every TWO-PART course of the build (the tool's compile), F then Esc: its ONE
                         part fetched, its world part a segment of it, and dropped (130.30.5).  NO TEST COURSE IS TWO PARTS yet
                         (a two-part picture is over 65,024 bytes), so this is the PLAYGROUND today - by
                         the build's list, never by name: when it leaves, the leg says it ran on none

and asserts, against what was read on the desktop BEFORE that launch:

  1  every part row of BONANZA.O88's table (os88parts.inc's op_table) but
     the ones held on the desktop (the bundle, the kit, the shell): OP_FETCHED
     clear - so op_seg answers 0 - and
     OP_R_ZKB equal to its value before the launch (the PACKED LENGTH
     op_drop writes back, SPEC.md 20.12.7.4.1);
  2  the instance's heap claims, read by tools/heapmap.py, exactly those
     before the launch: the same count, sizes and pinning (compared by what
     each is, not where: the region is movable);
  3  as a POSITIVE CONTROL, inside every bracket: the course's row(s) and
     the bundle's FETCHED with a segment, the three held balls' segments
     (bz_bsegs) set and the sprite's (bz_bseg) the material's, [bz_mat] the
     course's own ball (a replay's the log's), and the claims the desktop's less the shell plus the
     course's part(s) and the arena.

THE DESKTOP KEYS (130.11.11.2): T (HANDLERS: C, the camera mode, went
with TRICKLE, 130.46.12, and M and N on 2026-11-19, 130.11.5.4) - counted by
a logged breakpoint on its handler (bz_tkey), since a two-way toggle would
hide an odd count - HELD for 1.5 s (MartyPC's keyboard
repeats after 0.5 s, ten times a second) it advances EXACTLY ONCE; pressed,
released for 0.2 s and pressed again it advances TWICE.

It reports, for each launch, the floppy controller's reads from the key to the
bracket (MartyPC's own counter, m.disk(): no guest instrument).  A refused
fetch is not driven (it needs a heap too short at one moment and not the
next, SPEC.md 130.10.11.3); the review reads that path.

WAVE 4 (SPEC.md 130.14.14): a launch fetches only the course (the balls are held, 130.25.5.2); the part
rows are BZ_NCRS + the world parts + BZ_NDEMO + the shell and the rows after it (no ball rows, no sound
rows, 130.50).  Then, last (it closes the window): V's fetch and drop (ROLL's SHIPPED demo, [bz_vk] poked
to its row - the shipped demos are the shipped courses' alone), D's end (a TQUIK log made from the model's
autopilot play, bbcourse.encode_log), W through the Save dialog, L through the Open dialog and the
DOUBLE-CLICK of the saved .BZR (a new instance): every row as before and the claims as before after each.

WAVE 5B (SPEC.md 130.15.4.5, 130.15.13): THE CLAIM LEG.  A course part is
fetched in its STORED form and expanded in place by bz_cexp; between that
(and bz_hxlat on the Hercules) and OSAPI_FSX_RUN nothing writes it, and inside
the bracket the lanes' writer does.  So EVERY launch the row makes - and one cheap launch (F, then Esc)
of every course of BZ_COURSES no other leg launched (by the build's own table, never a list of names) -
stops at the kernel's fsx_run (a kernel address: the package's region may
move while the launch claims), and there the course claim ([bz_cseg], found
in the heap map, at least the part's length) must equal byte for byte the
tool's RAM form (bbcourse's cga; the art's
BZ<K>.BIN checked to be the same compile's stored form) on the CGA, or its
htab() translation on the Hercules; a difference names the first offset and
its BZC2 section.  The full run must have compared EVERY course K of
BZ_COURSES (on the CGA and the Hercules: the VGA converts its art in place).
V opens no bracket and is checked as before.

WAVE 6 (SPEC.md 130.16.6, 130.16.8, 130.16.14): THE PALETTE, once a card: a launch of TQUIK (`palette 0`,
10h) and one of TCUP (the default 30h), each stopped at the kernel's fsx_run and then at the first of
bz_vinit.vpal (bz_vinit's labelled `out` to 3D9h, resolved through the package's own symbols) and
bz_presented:
  - on the CGA bz_vinit.vpal is reached first with AL the course's BZ_CRS_PALS byte
    (read out of the guest's own table, bz_cpals); a few frames later, the
    ball at rest, MartyPC's RENDERED frame (m.fbuf), aligned on the card's own
    picture, shows the ball's body index - the most common non-black index in
    its 16 x 16 footprint - in the colour that byte selects (TQUIK's 10h: palette 0's light red; TCUP's
    30h: palette 1's light magenta), and every index the frame holds in its byte's colour: nearest of the
    CGA's sixteen, so MartyPC's exact RGB is not this row's business;
  - on the Hercules bz_presented is reached first: bz_vinit.vpal is NEVER hit;
  - after each bracket the desktop renders only the COLOURS its capture before
    the launch held, both of them (the menu bar's band left out): 3D9h's low
    nibble is the 1bpp desktop's foreground, so a colour select left behind
    shows there.  Not the bitmap: BONANZA's own window is in the frame and
    its face is rewritten after every play, Esc included (the review's F1).

--red NAME builds a broken package in a temporary directory (never build/)
and PASSES only if the row FAILS - at its own check (each aimed at a leg on a test course; --check
proves the course carries what the arm needs):
  leak         the goal path does not drop the course's row: fails at TQUIK's goal, and only there
  crepeat      the held-key guard taken out: a held key advances more than once
  overswallow  bz_dkk never cleared: the second press is swallowed
  padleak      the COURSE PART not dropped at a cup: TCUP's goal leaves its row fetched
  expoff1      WDIFF's count one record short: the claim leg's first launch (TQUIK)
  rowtab1      ROWTAB writes NROWS - 1 words: the claim leg's first launch (TQUIK)
  cellsafe     the guest's SAFE rule without its OBS test (bz_cxsafe): a prop's cell made SAFE - TQUIK's
               KEEP tube's cells (the host's rule without the OBS clause parts there: --check)
  nopal        the `out` left out: TQUIK's rendered colour (palette 1's, the BIOS's 30h)
  hercpal      the bz_herc branch round the write removed, so it runs on the
               Hercules: the bz_vinit.vpal breakpoint is hit there
  kitlate      the kit not fetched at the open: the desktop's kit check
  kitdrop      the kit dropped with each course: the held row not fetched after the first launch
  vgakeep      bz_vdrop a RET: the VGA's part kept after a launch (the VGA card)
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

OP_ROW, OP_T_ROWS, OP_R_FLAG, OP_R_ZKB = 8, 10, 1, 6        # apps/os88parts.inc
OP_LAZY, OP_FETCHED = 8, 32
WAYS = ("esc", "f", "altenter", "goal", "replayend", "replayesc")
BENCH_TAIL = 8                  # B's frames run before its end compare: [bz_frames] poked to BZ_BENCH less these
HANDLERS = (("KeyT", "bz_tkey"),)


class Q(object):
    """heapmap.Map wants .read(linear, n); Marty has exactly that"""

    def __init__(self, m):
        self.m = m

    def read(self, linear, n):
        return self.m.read(linear, n)


def ndemo():
    """the shipped demos, one part each after the courses' (bzcourse.inc's BZ_NDEMO, SPEC.md 130.14.7.4)"""
    import re
    inc = open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzcourse.inc")).read()
    if "%macro BZ_CRS_COUNTS" in inc:   # SPEC.md 130.58.34: BZ_CRS_MAX demo rows, the list's first
        return R.crs_rows()
    m_ = re.search(r"^BZ_NDEMO\s+equ\s+(\d+)", inc, re.M)
    return int(m_.group(1)) if m_ else 0


def title_rows():
    """the rows held while the window is open: the desktop's song's held none
    since SPEC.md 130.26.5 (the window is silent); story 9.8 (SPEC.md
    130.25.6.9): the RESIDENT BUNDLE, one row (BZ_P_FBUN), fetched once at
    the start and never dropped - the three balls at its head since 130.25.5.2,
    so a row in every build - and (SPEC.md 130.37.5) THE KIT, BZ_P_KIT,
    fetched quietly at the open before the bundle and held for the instance
    (kern_small gives it back at the open; none of these rows boots it)"""
    k = kit_row()
    return {fbun_row()} | ({k} if k is not None else set())


def kit_row():
    """BZ_P_KIT, the standard kit's row (SPEC.md 130.37.5) as the package
    assembled it - None for a tree older than 130.37"""
    return link_row("BZ_P_KIT")


def kit_held(g, rws):
    """-> failures: THE KIT held - its row FETCHED and bz_kseg its segment
    (SPEC.md 130.37.5) - for a tree that has one"""
    k = kit_row()
    if k is None:
        return []
    out = []
    if not rws[k][0] & OP_FETCHED:
        out.append("the kit (row %d) is not held (SPEC.md 130.37.5: fetched at the open, held)" % k)
    elif "bz_kseg" in g.sym and g.w("bz_kseg") == 0:
        out.append("the kit's row %d is fetched but [bz_kseg] is 0 (bz_kget did not keep its segment)" % k)
    return out


def fbun_row():
    """BZ_P_FBUN, the resident bundle's row (the balls and the resident families, SPEC.md 130.25.5.2)"""
    import re
    link = open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzlink.inc")).read()
    return int(re.search(r"^BZ_P_FBUN\s+equ\s+(0x[0-9A-Fa-f]+|\d+)", link, re.M).group(1), 0)


def bsegs(g):
    """the three HELD balls' segments, bz_bsegs (SPEC.md 130.25.5.2)"""
    return list(struct.unpack("<3H", bytes(g.m.read(g.a("bz_bsegs"), 6))))


def link_row(name):
    """a BZ_P_* row constant as the package assembled it (bzlink.inc, the shell
    part's link, which lists the package's BZ constants), or None"""
    import re
    link = open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzlink.inc")).read()
    m_ = re.search(r"^%s\s+equ\s+(0x[0-9A-Fa-f]+|\d+)" % name, link, re.M)
    return int(m_.group(1), 0) if m_ else None


def snd_row():
    """the row after the courses': the DEMOS' first since SPEC.md 130.50 (the sound part went into the
    RESIDENT BUNDLE, each song into its course part - no sound rows), and no WORLD rows since SPEC.md
    130.30.5 (a two-part course's world part is in its ONE part, as a sheeted course's)"""
    R.crs_fill()                        # (fills the course table: BZ_NCRS of them)
    return CRS_ROW0 + R.crs_rows()      # (BZ_CRS_MAX rows since SPEC.md 130.58.34, the list's first)


def crs_row(name):
    """course NAME's own part's row (by name, never a literal K): padleak's red keeps TCUP's at the cup"""
    return CRS_ROW0 + R.CRS_K[name]


def bench_frames():
    """BZ_BENCH, the benchmark's frames (bzgame.inc), read out of the source"""
    import re
    t_ = open(os.path.join(ROOT, "apps", "bonanza", "bzgame.inc")).read()
    return int(re.search(r"^BZ_BENCH\s+equ\s+(\d+)", t_, re.M).group(1))


def two_part():
    """the build's TWO-PART courses, by name, in K order (the tool's compile: a world part and no sheets): the
    world part's leg.  Since SPEC.md 130.30.5 a two-part course is ONE part on the disk, its world part a
    segment of its one claim, so there is no list of world rows to read; a SHEETED course (SPEC.md 130.30.12)
    is not among them"""
    R.crs_fill()
    names = sorted(dict.keys(R.CRS_K), key=R.CRS_K.__getitem__)
    return [n for n in names if R.course_k(R.CRS_K[n]).split and not R.course_k(R.CRS_K[n]).sstored]


def one_plan(k):
    """course K's ONE part's layout when it has a world part (SPEC.md 130.30.5, 130.30.12.5: a two-part
    course's picture part, or a sheeted course's sheets, and its world part, each from a paragraph of the one
    claim - plan["k"] the picture pieces, plan["paras"] their paragraphs and the world part's last), else
    None"""
    return getattr(R.course_k(k), "oplan", None)


def shell_row():
    """the SHELL PART's row (SPEC.md 130.19.2): after the demos - held on the
    desktop, never inside a bracket.  Counted from the build's own lists (the
    courses, the sound, the songs, the demos) and
    held to the package's BZ_P_SHELL, so a row the table gains that this count
    does not know of is a refusal here rather than a wrong row read quietly"""
    k = snd_row() + ndemo()             # (no sound rows since SPEC.md 130.50)
    pk = link_row("BZ_P_SHELL")
    assert pk is None or pk == k, ("the shell part's row: the build's lists count %d, the package's "
                                   "BZ_P_SHELL is %d - a part row this row does not know of" % (k, pk))
    return k


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


# ---- WAVE 5B (SPEC.md 130.15.13): THE CLAIM LEG --------------------------------------
CLAIMED = {}                    # tag -> the courses whose claim was compared, by name


_RAM = {}
_SHEETS = {}


def ram_forms(k, tag, art=None):
    """course K's part(s) as the card holds them between bz_cexp (and bz_hxlat on
    the Hercules) and OSAPI_FSX_RUN (SPEC.md 130.15.4.5): THE TOOL'S RAM FORM
    (bbcourse's cga), or its htab() translation
    (herc_translate_course) -> (the part, None) - or for a TWO-PART course
    (SPEC.md 130.30) (the picture part, the world part), herc_translate_parts'
    on the Hercules.  The art's BZ<K>.BIN (a two-part course's ONE part, SPEC.md 130.30.5) must be the same
    compile's STORED forms, or the comparison would be with another tree's
    courses.  A SHEETED course (SPEC.md 130.30.12): the picture part is its
    sheet 0 (its ONE part's first piece, what bz_crshdr shows), its other
    sheets' forms sheet_forms(); its BZ<K>.BIN is the one part (130.30.12.5).
    """
    art = art or R.at("build/bonanza-art")
    key = (k, tag, art)
    if key not in _RAM:
        c = R.course_k(k)
        ram, stored = c.cga, (c.bstored or c.stored)
        wram = c.wcga if c.split else None  # (SPEC.md 130.30.5, 130.30.12.5: the world part is in the one part)
        for f_, want in [("BZ%d.BIN" % k, stored)]:
            with open(os.path.join(ROOT, art, f_), "rb") as f:
                if f.read() != want:
                    raise SystemExit("%s/%s is not this tree's course %s as stored: the art is "
                                     "stale (`make bonanzadisk`)" % (art, f_, c.name))
        if wram is not None:
            pw = BB.herc_translate_parts(ram, wram) if tag == "herc" else (ram, bytes(wram))
            _SHEETS[key] = [bytes(q) for q in (BB.sheets_of(pw[0]) or ())[1:]]
            _RAM[key] = (bytes(pw[0]), pw[1])
        else:
            _RAM[key] = (BB.herc_translate_course(ram) if tag == "herc" else bytes(ram), None)
    return _RAM[key]


def sheet_forms(k, tag, art=None):
    """a SHEETED course K's other sheets (1, 2, ...) as the card holds them at the claim leg (SPEC.md
    130.30.12.5: on the Hercules each translated, bz_hxshs) - [] for any other course"""
    ram_forms(k, tag, art)
    return _SHEETS.get((k, tag, art or R.at("build/bonanza-art")), [])


def ram_form(k, tag, art=None):
    """course K's ONE part, or a two-part course's picture part (ram_forms)"""
    return ram_forms(k, tag, art)[0]


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
    """THE CLAIM LEG (SPEC.md 130.15.13), at the kernel's fsx_run - the
    launch's OSAPI_FSX_RUN call, after bz_cexp and bz_hxlat, before the lanes'
    writer: the course claim ([bz_cseg], found in the heap map, its claim at
    least the part's length) equal byte for byte to the tool's RAM form (CGA)
    or its htab() translation (Hercules).  On the VGA the course's art is
    converted IN PLACE to planar pairs (BZV_CONV, SPEC.md 130.46.5) at
    bz_cload, so the claim is no byte-for-byte copy of either: the leg is not
    run there (bonanzaring's VGA card checks every converted pixel instead,
    on the card).  -> failures"""
    m = g.m
    if g.tag == "vga":
        print("vga THE CLAIM LEG: not run on the VGA (its art converted in place, SPEC.md 130.46.5; "
              "bonanzaring's VGA card checks it on the card)", flush=True)
        return []
    k = g.b("bz_crs")
    R.crs_fill()                                # (fills the course table)
    name = [n for n in R.CRS_K if R.CRS_K[n] == k][0]
    pic, world = ram_forms(k, g.tag)
    cpic, cworld = ram_forms(k, "cga")
    mp = heapmap.Map(Q(m), {n: m.sym(n) for n in ("mem_base", "mem_top", "spl_live", "mem_tab")})
    # a TWO-PART course (SPEC.md 130.30.5): the picture part in [bz_mseg], the world part in [bz_cseg] - ONE
    # claim, the picture part at its base and the world part a SEGMENT inside it at the plan's paragraphs
    legs = [("bz_cseg", pic, cpic, "")] if world is None else [("bz_mseg", pic, cpic, "picture "),
                                                               ("bz_cseg", world, cworld, "world ")]
    # a SHEETED course (SPEC.md 130.30.12.5): ONE claim - sheet 0 at its base ([bz_shseg], the picture part's
    # above), every other sheet ([bz_shseg + 2 i]) and the world part ([bz_cseg]) SEGMENTS inside it at the
    # plan's paragraphs, each its RAM form (on the Hercules its blocks translated, bz_hxshs) - and at fsx_run
    # the SHOWN sheet, [bz_mseg], is sheet 0 (bz_crshdr's)
    shs = sheet_forms(k, g.tag)
    spl = one_plan(k)
    inner = {}                                  # (a word's segment -> its paragraphs past the claim's base)
    if spl:
        inner = {"bz_cseg": spl["paras"][-1]}
        inner.update({("bz_shseg", i): spl["paras"][i] for i in range(1, spl["k"])})
    legs += [(("bz_shseg", i), q, cq, "sheet %d " % i)
             for i, (q, cq) in enumerate(zip(shs, sheet_forms(k, "cga")), 1)]
    out = []
    if shs and g.w("bz_mseg") != g.w("bz_shseg"):
        out.append("%s: claim leg, %s: [bz_mseg] %04X at fsx_run is not sheet 0's segment [bz_shseg] %04X "
                   "(bz_crshdr shows sheet 0, SPEC.md 130.30.12.3)" % (what, name.upper(), g.w("bz_mseg"),
                                                                       g.w("bz_shseg")))
    for word, want, cwant, which in legs:
        if isinstance(word, tuple):             # (a sheet's word: the i-th of bz_shseg)
            seg = struct.unpack("<H", bytes(m.read(g.a(word[0]) + 2 * word[1], 2)))[0]
            word = "%s + %d" % (word[0], 2 * word[1])
        else:
            seg = g.w(word)
        key = word
        if isinstance(word, str) and word.startswith("bz_shseg + "):
            key = ("bz_shseg", int(word.split()[-1]) // 2)
        if key in inner:                        # (a segment of the course's one claim, 130.30.5, 130.30.12.5:
            base = g.w("bz_mseg")               # its base the picture part's, or sheet 0's, checked above)
            cl = [c for c in mp.claims if c.seg == base]
            if not cl or seg - base != inner[key] or (cl[0].para - inner[key]) * 16 < len(want):
                out.append("%s: claim leg, %s: [%s] %04X is not the one claim's (at %04X) paragraph %d with "
                           "room for its %d bytes (SPEC.md 130.30.12.5)" % (what, name.upper(), word, seg, base,
                                                                            inner[key], len(want)))
                continue
            cl = []
        else:
            cl = [c for c in mp.claims if c.seg == seg]
        if key not in inner and not cl:
            out.append("%s: claim leg, %s: [%s] %04X is no claim of the heap map" % (what, name.upper(), word, seg))
            continue
        if cl and cl[0].para * 16 < len(want):
            out.append("%s: claim leg, %s: the course's %sclaim at %04X is %d bytes, the RAM form %d" % (
                what, name.upper(), which, seg, cl[0].para * 16, len(want)))
            continue
        got = bytes(m.read(seg * 16, len(want)))
        if got == want:
            continue
        bad = [i for i in range(len(want)) if got[i] != want[i]]
        out.append("%s: claim leg, %s: the course's %sclaim differs from the tool's RAM form%s at %d byte(s), the "
                   "first at offset %d in %s (%02Xh, the tool's %02Xh) - SPEC.md 130.15.13" % (
                       what, name.upper(), which, " through htab()" if g.tag == "herc" else "", len(bad), bad[0],
                       section_at(cwant, bad[0]), got[bad[0]], want[bad[0]]))
    if world is not None and not out and g.w("bz_mseg") == g.w("bz_cseg"):
        out.append("%s: claim leg, %s: a two-part course with [bz_mseg] = [bz_cseg]" % (what, name.upper()))
    if not out:
        CLAIMED.setdefault(g.tag, set()).add(name)
    return out


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
    key = "KeyB" if way == "bench" else "KeyR" if way.startswith("replay") else "KeyF"
    # (F plays BZ_CRS_DEFAULT, pathway pad 0's course, SPEC.md 130.14.7.4, and B BENCH: every leg here
    # names its course, so a play is POKED onto it at bz_launch - CRS None leaves the key's own)
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
    """KEY (Enter, D: a launch of the package's own choosing) with the claim leg at its fsx_run"""
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


def goal(g, crs):
    """Play to the goal: the ball poked at bz_t0 onto the centre of the course's first GOAL cell, at rest -
    or, on a course with a CUP, at rest in its mouth (it holes out)."""
    cup = [r for r in R.course(crs).part["props"] if r["kind"] == BB.PK_CUP]
    if cup:                                     # wave 4: the CUP, the ball at rest in its mouth
        (wx, wy), gvx, gvy = cup[0]["at"], 0, 0
    else:
        grid = BB.Grid(R.course(crs).cga, R.course(crs).wcga)
        wx, wy = next((x, y) for y in range(256) for x in range(256) if grid.cell(x, y)[3] & 15 == BB.KIND_GOAL)
        gvx = gvy = 0
    p = BB.Physics(R.course(crs), play=True, mat=g.b("bz_mat")).poke(wx, wy, gvx, gvy)
    at_t0(g, lambda g_: R.poke_ball(g_, p.gx, p.gy, p.gz, p.gvx, p.gvy, p.gvz, air=0))


def into_tube(g, crs):
    """the ball poked onto the centre of the course's first plain tube's IN
    cell (a DRAIN: SPEC.md 130.12.6.1) at bz_t0: the next step captures it;
    -> once the guest says it is hidden ([bz_tube])"""
    tb = next(r for r in R.course(crs).part["props"] if r["kind"] == BB.PK_TUBE)
    p = BB.Physics(R.course(crs), play=True, mat=g.b("bz_mat")).poke(*tb["at"])
    at_t0(g, lambda g_: R.poke_ball(g_, p.gx, p.gy, p.gz, 0, 0, 0, air=0))
    M.until(g.m, lambda _: g.b("bz_tube") != 0, "the ball to be swallowed by the tube at %s" % (tb["at"],), guest=10)


def one(g, way, base_rows, base_claims, mat=None, crs="tquik"):
    """One launch on CRS left by WAY: -> (failures, the report line).  A play rolls its course's own ball,
    a replay the log's (made with MAT, the course's by default).  WAY "bench" is B on its own course
    (BENCH: CRS is ignored), ended early (BENCH_TAIL)."""
    m = g.m
    fails = []
    if way == "bench":
        crs = "bench"                           # (B's own course, BZ_CRS_BENCH: never poked)
    if mat is None:
        mat = R.course(crs).ball
    if way.startswith("replay"):                # a log of CRS with this ball: 2 s to its end, or
        m.pause()                               # 11 s to be left by Esc early
        g.write_log(R.make_log([0] * (120 if way == "replayend" else 600), R.CRS_K[crs], mat))
        m.run()
    if way.startswith("replay"):
        want_mat = m.read(g.a("bz_rlog") + 5, 1)[0]   # R the log's (SPEC.md 130.11.12.2)
    else:
        want_mat = R.course(crs).ball               # a play its course's own (SPEC.md 130.11.5.4), B's too
    reads = launch(g, way, None if way == "bench" else crs, fails)
    pc = g.b("bz_pc")
    r_in, c_in = rows(g), claims(g)
    # SPEC.md 130.25.5.2: the balls have no rows - all three are HELD in the resident bundle (its row is
    # fetched since the open), so the control is the course's row and the bundle's FETCHED, the three
    # ball segments (bz_bsegs) set, and the sprite's (bz_bseg) the material's
    shd = one_plan(g.b("bz_crs")) is not None   # SPEC.md 130.30.5, 130.30.12.5: a course's WORLD part is a
    for i in [pc, fbun_row()]:                  # segment of its ONE part, no row of its own
        f, z = r_in[i]
        if not f & OP_FETCHED or not z:
            fails.append("%s: inside the bracket row %d is not fetched (flags %02X zkb %04X): the control cannot "
                         "see a part that is there" % (way, i, f, z))
    bs = bsegs(g)
    if g.b("bz_mat") != want_mat or not all(bs) or g.w("bz_bseg") != bs[want_mat] or pc != CRS_ROW0 + g.b("bz_crs"):
        fails.append("%s: the launch rolls material %d (bz_bseg %04X, the held balls %s) with course row %d; want "
                     "material %d and course row %d (SPEC.md 130.25.5.2)" % (
                         way, g.b("bz_mat"), g.w("bz_bseg"), ["%04X" % b_ for b_ in bs], pc, want_mat,
                         CRS_ROW0 + g.b("bz_crs")))
    if r_in[shell_row()][0] & OP_FETCHED:
        fails.append("%s: inside the bracket the SHELL part (row %d) is still fetched: it may never share memory "
                     "with a course (SPEC.md 130.19.2)" % (way, shell_row()))
    # wave 9 (SPEC.md 130.25.4): the balls, the sound part, the song and the fanfare are ONE claim, the ARENA,
    # so a play holds the course and the arena - the shell gone, the desktop title's arena (if it had one)
    # become the play's: two claims however many balls, and no fanfare term
    ar_in = 1 if g.w("op_arena") else 0
    np = 1                                      # (130.30.5: a two-part course's picture and world parts ONE
                                                # claim; 130.30.12.5: a SHEETED course's sheets and world part)
    if g.tag == "vga":                          # (130.46.6: the VGA's code part and the balls' converted
        np += 2                                 # copies, both held through the bracket)
    if len(c_in) != len(base_claims) - 1 + np - g.ar0 + ar_in or not ar_in:
        fails.append("%s: inside the bracket the instance holds %d claims, not the desktop's %d - the shell + the "
                     "course's %d part(s) + the arena (%d on the desktop, %d here): %s" % (
                         way, len(c_in), len(base_claims), np, g.ar0, ar_in, c_in))
    if "bz_mseg" in g.sym:                      # the two words: one part's both the course's, two parts' apart
        cs, ms = g.w("bz_cseg"), g.w("bz_mseg")
        if not cs or (ms != cs) != shd:
            fails.append("%s: inside the bracket [bz_cseg] %04X and [bz_mseg] %04X - a %d-part course's (SPEC.md "
                         "130.30.5)" % (way, cs, ms, np))
    if way == "bench":                          # (the guest paused with the bracket up: BENCH_TAIL frames
        g.put("bz_frames", max(g.w("bz_frames"), bench_frames() - BENCH_TAIL))     # to B's own end)
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark to its end (BZ_BENCH)", guest=60)
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
        M.until(m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3,   # act (SPEC.md 130.20.6)
                "the title to be back (%s)" % way, guest=30)
    M.until(m, lambda _: rows(g)[shell_row()][0] & OP_FETCHED and g.b("bz_shpend") == 0,
            "the shell part to be fetched back and the face repainted (%s, SPEC.md 130.19.2)" % way, guest=30)
    m.pause()
    r_out, c_out = rows(g), claims(g)
    title = title_rows() | {shell_row()}
    for i, (before, after) in enumerate(zip(base_rows, r_out)):
        if i in title:                      # the title's music, held on the desktop
            if (after[0] & OP_FETCHED) != (before[0] & OP_FETCHED):
                fails.append("%s: the held part row %d is %s after the launch, %s before (SPEC.md 130.20.6, "
                             "130.37.5)"
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
    if "bz_mseg" in g.sym and g.w("bz_mseg"):
        fails.append("%s: [bz_mseg] %04X after the launch: bz_cdrop zeroes it (SPEC.md 130.30.5)"
                     % (way, g.w("bz_mseg")))
    line = "%s %s (%s): rows %s fetched inside; %d floppy reads to the bracket; after it every row as before " \
           "and the claims as before: %s" % (crs.upper(), way, BB.MAT_NAMES[want_mat],
                                             ",".join(str(i) for i in [pc, fbun_row()]), reads, "yes" if not fails else "NO")
    return fails, line


def after(g, what, base_rows, base_claims):
    """every part row back as it was on the desktop and the claims as before:
    -> failures (one()'s post-launch checks, for a leg that is not one launch)"""
    m = g.m
    fails = []
    M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "%s: the parts dropped" % what, guest=30)
    if "bzs_desk" in g.sym:
        M.until(m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3, "%s: the title back" % what, guest=30)
    M.until(m, lambda _: rows(g)[shell_row()][0] & OP_FETCHED and g.b("bz_shpend") == 0,
            "%s: the shell part fetched back (SPEC.md 130.19.2)" % what, guest=30)
    m.pause()
    r_out, c_out = rows(g), claims(g)
    m.run()
    title = title_rows() | {shell_row()}
    for i, (before, aft) in enumerate(zip(base_rows, r_out)):
        if i in title:
            if (aft[0] & OP_FETCHED) != (before[0] & OP_FETCHED):
                fails.append("%s: the held part row %d is %s, %s before" % (
                    what, i, "fetched" if aft[0] & OP_FETCHED else "not fetched",
                    "fetched" if before[0] & OP_FETCHED else "not fetched"))
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


def guard(g):
    M.until(g.m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)


def quik_log():
    """TQUIK's log MADE FROM THE MODEL: the autopilot's play to the goal (bbcourse.Physics.auto, 165 steps),
    encoded with TQUIK's identity (bonanza_ring.make_log) - never a shipped demo"""
    import bonanza_game as GM
    k = R.CRS_K["tquik"]
    return R.make_log(GM.auto_keys(k), k, R.course("tquik").ball)


def wave4_exits(g, ui, base_rows, base_claims):
    """SPEC.md 130.14.14: V's fetch and drop (ROLL's shipped demo), D's end (a TQUIK log made from the
    model), W, L and the double-click - each with the rows and the claims as before"""
    m = g.m
    fails = []
    vk = R.demo_ks().index(R.CRS_K["roll"])     # (the demo rows' order: [bz_vk] the row V loads next)
    m.pause()
    g.putb("bz_vk", vk)
    m.run()
    guard(g)
    g.key("KeyV")
    M.until(m, lambda _: g.b("bz_vk") != vk, "V to load ROLL's shipped demo", guest=20)
    fails += after(g, "V", base_rows, base_claims)
    m.pause()
    g.write_log(quik_log())
    m.run()
    guard(g)
    keyed_launch(g, "KeyD", "D of TQUIK's log", fails)
    M.until(m, lambda _: g.b("bz_fs") == 1, "D's bracket", guest=60)
    M.until(m, lambda _: g.b("bz_fs") == 0, "D to its end", guest=60)
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
    if bytes(g2.read_log(4)) != b"BZR1":
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
    """the CGA colour (0 - 15) that colour-select BYTE (3D9h, SPEC.md 130.16.6)
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


def palette_leg(g, crss=("tquik", "tcup")):
    """SPEC.md 130.16.6 (bonanzaexit's wave 6 leg): the colour select on the
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
        g.key("KeyF")
        assert m.wait_stop(60) == "breakpoint", "palette %s: F did not reach bz_launch" % crs
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
                             "colour select written to 3D9h where the picture has no palette (SPEC.md 130.16.6)"
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
    print("%s palette (SPEC.md 130.16.6): %s; the desktop restored after each: %s" % (
        tag, "; ".join(say), "yes" if not fails else "NO"), flush=True)
    return fails


def ui_settle(g):
    """the desktop quiet: the title's face drawn, nothing moving"""
    M.until(g.m, lambda _: g.b("bz_fs") == 0, "the desktop", guest=30)
    if "bzs_desk" in g.sym:
        M.until(g.m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3, "the title back", guest=30)
    g.ui.settle()


def held_keys(g):
    """SPEC.md 130.11.11.2 on the desktop: -> failures.  Each key's handler is
    counted by a logged breakpoint (T's two controls would hide an odd count);
    the control is put back to KEYS after."""
    m = g.m
    fails = []
    for key, h in HANDLERS:
        with M.bp_trace(m, g.a(h), log=True) as tr:
            n0 = tr.count()                     # (a guard left set by an earlier key holds
            m.key(key, up=False)                # ITS make code: it swallows nothing of this one)
            M.pace(m, 1.5)
            m.key(key, down=False)
            # the guard's timer polls a tick at a time (130.11.11.2): a fixed guest
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
    m.pause()
    g.putb("bz_ctl", 0)                         # (T toggled an odd number of times: KEYS again)
    m.run()
    return fails


def run(tag, ways=WAYS, apps=None, src=None, tube=True, cup=True, bench=True, world=True, keys=True, w4=True,
        rest=True, cover=True, pal=True):
    """ONE BOOT of card TAG, every leg the card owes on its test course (the module's docstring) -> failures"""
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
        g.ar0 = 1 if g.w("op_arena") else 0     # the title's arena (130.25.4): one claim on the desktop
        m.run()
        nlazy = sum(1 for f, _ in base_rows if f & OP_LAZY)
        title = title_rows() | {shell_row()}
        print("%s: %d part rows (%d lazy), fetched on the desktop: %s (the held ones: the bundle's and the "
              "shell's, %s); the instance's claims %s" % (
                  tag, len(base_rows), nlazy, [i for i, (f, _) in enumerate(base_rows) if f & OP_FETCHED],
                  sorted(title), base_claims), flush=True)
        if any(f & OP_FETCHED for i, (f, _) in enumerate(base_rows) if i not in title):
            fails.append("a part row is fetched on the desktop before any launch")
        m.pause()
        fails += kit_held(g, base_rows)
        m.run()
        if any(not base_rows[i][0] & OP_FETCHED for i in title):
            fails.append("the title's parts (rows %s) are not held on the desktop (SPEC.md 130.20.6)"
                         % sorted(title))
        R.crs_fill()                        # (fills the course table: BZ_NCRS of them)
        if len(base_rows) != shell_row() + 1 + R.after_shell():
            fails.append("the package has %d part rows, not %d courses, %d shipped demos, the shell, the "
                         "pathway, the title's two, the families' and the VGA's - no sound rows, no world rows "
                         "(SPEC.md 130.11.3.1, 130.30.5, 130.50, 130.14.7.4, 130.19.2, 130.19.5, 130.23, 130.46.6)" % (
                             len(base_rows), dict.__len__(R.CRS_K), ndemo()))
        plan = [(w, "tquik") for w in ways]     # the six ways out, ONCE, on TQUIK (130.25.5.2: the balls held)
        if tube:
            plan.append(("tubeesc", "tquik"))   # Esc with the ball HIDDEN in TQUIK's KEEP tube
        if cup:
            plan.append(("goal", "tcup"))       # the CUP's way out (and padleak's leg)
        if bench:
            plan.append(("bench", None))        # B, BENCH, to its end
        if world:                               # a TWO-PART course's world part (130.30.5): no test course is
            two = two_part()                    # two parts, so the build's own list (the PLAYGROUND today)
            print("%s the world part's leg (SPEC.md 130.30.5): %s" % (
                tag, ", ".join(n.upper() for n in two) if two else
                "NO two-part course in this build - the leg ran on none"), flush=True)
            plan += [("esc", n) for n in two]
        for way, crs in plan:
            f, line = one(g, way, base_rows, base_claims, crs=crs or "tquik")
            print("%s %s" % (tag, line), flush=True)
            fails += f
            if f:
                break
        if rest and not fails and tag != "vga":     # wave 5b: one launch (F, Esc) of every course no leg above
            R.crs_fill()                            # launched, for the claim leg - the build's own table, in K
            names = sorted(dict.keys(R.CRS_K), key=R.CRS_K.__getitem__)    # order (the VGA runs no claim leg)
            for crs in [n for n in names if n not in CLAIMED.get(tag, set())]:
                f, line = one(g, "esc", base_rows, base_claims, crs=crs)
                print("%s %s" % (tag, line), flush=True)
                fails += f
                if f:
                    break
        if pal and not fails and tag != "vga":  # wave 6 (SPEC.md 130.16.6): the colour select - the CGA's
            fails += palette_leg(g)             # 3D9h (the VGA's four colours are its attribute controller's,
                                                # BZV_INIT, and bonanzaring's VGA glass compares them)
        if keys and not fails:
            fails += held_keys(g)
        if w4 and not fails:                    # (last: it closes the window)
            fails += wave4_exits(g, ui, base_rows, base_claims)
        R.crs_fill()
        seen = CLAIMED.get(tag, set())
        print("%s THE CLAIM LEG (SPEC.md 130.15.13): the course claim = the tool's RAM form at fsx_run on %s" % (
            tag, ", ".join(sorted(n.upper() for n in seen)) or "no launch"), flush=True)
        if cover and not fails and tag != "vga" and seen != set(dict.keys(R.CRS_K)):
            fails.append("the claim leg compared %s, not all %d courses of BZ_COURSES (SPEC.md 130.15.13)" % (
                sorted(seen), dict.__len__(R.CRS_K)))
    return fails


CRS_ROW0 = 0                                # BZ_P_CRS: no ball rows since SPEC.md 130.25.5.2 (it was 3)
REDS = {
    # the goal path does not drop the course's row: bz_fin is set only by a play that reached the goal
    "leak": [("bonanza.asm", "    call op_areserve            ; into given back (a refused first fetch)\n"
              "    mov al, [bz_pc]\n",
              "    call op_areserve\n    cmp byte [bz_fin], 0         ; RED leak: the goal keeps the course\n"
              "    jne .redleak\n    mov al, [bz_pc]\n"),
             ("bonanza.asm", "    call op_drop\n%if BZ_PATH_NPAD\n.held:\n%endif\n",
              "    call op_drop\n.redleak:\n%if BZ_PATH_NPAD\n.held:\n%endif\n")],
    # the held-key guard taken out: every typed T acts
    "crepeat": [("bonanza.asm", "    call bz_dkey                ; AH = the make code: CF = 1 a repeat, swallowed\n"
                 "    jc .done\n", "    ; RED crepeat: no guard\n")],
    # bz_dkk never cleared: the key never reads as come up
    "overswallow": [("bonanza.asm", ".up:\n    mov byte [bz_dkk], 0\n", ".up:                            ; RED overswallow\n")],
}
# (SPEC.md 130.25.5.2, 130.50.2: no ball row and no sound part's row is dropped any more - both are held in
# the bundle - so the cup's leak is the COURSE PART's, TCUP's row, kept at the cup)
REDS["padleak"] = [("bonanza.asm", "    call op_drop\n%if BZ_PATH_NPAD\n.held:\n%endif\n",
                    "    cmp byte [bz_hid], 0        ; RED padleak: the course part kept at the cup\n"
                    "    jne .rpl\n    call op_drop\n.rpl:\n%if BZ_PATH_NPAD\n.held:\n%endif\n")]
# wave 5b (SPEC.md 130.15.13): the expansion broken, each red at the CLAIM LEG's first differing offset -
# WDIFF's count one record short (the last record left as differences), ROWTAB's last word never written,
# and the guest's SAFE rule without its OBS test (a prop's cell made SAFE: TQUIK's tube's)
REDS["expoff1"] = [("bonanza.asm", "    sub cx, bx\n    shr cx, 1                   ; the words after the first record\n",
                    "    sub cx, bx\n    sub cx, bx                  ; RED expoff1: one record short\n"
                    "    shr cx, 1                   ; the words after the first record\n")]
REDS["rowtab1"] = [("bonanza.asm", "bz_cxrtb:\n    mov bx, [es:BZC_GRID]\n    mov cx, [es:bx + BZG_NROWS]\n",
                    "bz_cxrtb:\n    mov bx, [es:BZC_GRID]\n    mov cx, [es:bx + BZG_NROWS]\n"
                    "    dec cx                      ; RED rowtab1: NROWS - 1 words\n")]
REDS["cellsafe"] = [("bonanza.asm", "    test ah, BZ_FL_OBS          ; a prop's cell: never SAFE\n    jnz .no\n",
                     "    ; RED cellsafe: no OBS test\n")]
# wave 6 (SPEC.md 130.16.14): the colour select's write left out (TQUIK renders palette 1), and its
# Hercules branch removed (the labelled write runs there)
REDS["nopal"] = [("bzvideo.inc", ".vpal:\n    out dx, al\n",
                  ".vpal:\n    nop                         ; RED nopal: no write\n")]
REDS["hercpal"] = [("bzvideo.inc", ".nvga:\n    cmp byte [bz_herc], 0\n    jne .herc\n"
                    "    mov bl, [bz_crs]            ; the CGA: the course's colour select\n"
                    "    xor bh, bh\n    mov al, [bz_cpals + bx]\n    mov dx, 3d9h\n.vpal:\n    out dx, al\n",
                    ".nvga:\n    mov bl, [bz_crs]            ; RED hercpal: the write on the Hercules too\n"
                    "    xor bh, bh\n    mov al, [bz_cpals + bx]\n    mov dx, 3d9h\n.vpal:\n    out dx, al\n"
                    "    cmp byte [bz_herc], 0\n    jne .herc\n")]
# SPEC.md 130.37.5: the kit not fetched at the open (the first launch's bz_kget fetches it, so only the
# desktop's check sees it), and the kit dropped with each course (held no longer: re-read every launch)
REDS["kitlate"] = [("bonanza.asm", "    push es                     ; THE KIT (SPEC.md 130.37.5), HELD for the instance:\n"
                    "    call bz_kget0 ",
                    "    push es                     ; RED kitlate: no fetch at the open\n"
                    "    nop\n   ")]
REDS["kitdrop"] = [("bonanza.asm", "                                ; (NO BALL: held for the instance, 130.25.5.2)\n",
                    "    mov al, BZ_P_KIT            ; RED kitdrop: the kit dropped with the course\n"
                    "    call op_drop\n")]
# the VGA's part and the balls' converted copies never dropped after a launch (bz_vdrop a RET): the rows and the
# claims after the bracket are not the desktop's (SPEC.md 130.46.6)
REDS["vgakeep"] = [("bonanza.asm", "bz_vdrop:\n", "bz_vdrop:\n    ret                         ; RED vgakeep\n")]


# Each red arm runs only the legs it needs (the rest OFF), aimed at a leg on a test course; --check proves the
# course carries what the arm is aimed at (aims()).
RUN_LEGS = ("tube", "cup", "bench", "world", "keys", "w4", "rest", "cover", "pal")


def _only(ways=(), **on):
    """a red arm's run(): WAYS on TQUIK and the legs named ON, every other leg off"""
    d = {k: False for k in RUN_LEGS}
    d.update(on)
    d["ways"] = ways
    return d


RED_RUN = {
    "leak": _only(WAYS),                        # TQUIK's six ways: red at the goal, and only there
    "crepeat": _only(keys=True), "overswallow": _only(keys=True),
    "padleak": _only(cup=True),                 # TCUP's cup
    "expoff1": _only(("esc",)), "rowtab1": _only(("esc",)),     # the claim leg's first launch: TQUIK
    "cellsafe": _only(("esc",)),                # TQUIK's KEEP tube's cells (a prop's)
    "nopal": _only(pal=True), "hercpal": _only(pal=True),
    "kitlate": _only(), "kitdrop": _only(("esc",)),
    "vgakeep": _only(("esc",)),
}
RED_WANT = {"padleak": lambda: "part row %d is still FETCHED" % crs_row("tcup"),  # TCUP's course part
            "leak": "goal:", "crepeat": "held 1.5 s advanced", "overswallow": "pressed twice",
            "expoff1": "claim leg, TQUIK", "rowtab1": "claim leg, TQUIK", "cellsafe": "claim leg, TQUIK",
            "nopal": "palette TQUIK: the ball's body", "hercpal": "bz_vinit.vpal breakpoint was HIT",
            "kitlate": "the kit (row", "kitdrop": lambda: "held part row %d is not fetched" % kit_row(),
            "vgakeep": "is still FETCHED after the launch"}
RED_TAGS = {"nopal": ("cga",), "hercpal": ("herc",), "vgakeep": ("vga",)}   # each goes red on its own card
assert set(RED_RUN) == set(RED_WANT) == set(REDS), "every red arm has its run and its check"


def pals():
    """{K: the course's colour select byte} out of the build's BZ_CRS_PALS (bzcourse.inc)"""
    import re
    inc = open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzcourse.inc")).read()
    m_ = re.search(r"^%macro BZ_CRS_PALS 0\n\s+db ([^\n]+)", inc, re.M)
    return dict(enumerate(int(x.strip().rstrip("h"), 16) for x in m_.group(1).split(",")))


def aims():
    """THE HOST HALF OF THE AIM: every leg's test course carries what the leg and its red arm need, read off
    the build and the tool's compile -> (lines, failures).  The arms are re-aimed at test courses (phase 3);
    an arm aimed at a feature its course lost would go green against a broken package"""
    import bonanza_game as GM
    lines, bad = [], []
    R.crs_fill()
    q, c = R.course("tquik"), R.course("tcup")
    pk = pals()
    props_q = [r["kind"] for r in q.part["props"]]
    grid = BB.Grid(q.cga, q.wcga)
    goals = [(x, y) for y in range(64) for x in range(64) if grid.cell(x, y)[3] & 15 == BB.KIND_GOAL]
    steps, falls = GM.auto_steps(R.CRS_K["tquik"])
    lines.append("TQUIK: %d goal cell(s) (the goal's way, leak), a KEEP tube %s (tubeesc), its ball %s, its "
                 "colour select %02Xh (nopal: not the BIOS's 30h), the autopilot's goal at step %s (D's log)"
                 % (len(goals), "yes" if BB.PK_TUBE in props_q else "NO", BB.MAT_NAMES[q.ball],
                    pk[R.CRS_K["tquik"]], steps))
    if not goals:
        bad.append("TQUIK has no GOAL cell: the goal's way and the leak red have nothing to end on")
    if BB.PK_TUBE not in props_q:
        bad.append("TQUIK has no tube: tubeesc's Esc while hidden is not driven")
    if pk[R.CRS_K["tquik"]] == 0x30:
        bad.append("TQUIK's colour select is the BIOS's 30h: the nopal red renders the same colour")
    if steps is None:
        bad.append("TQUIK: the model's autopilot does not reach the goal (wave 4's D log)")
    cups = [r for r in c.part["props"] if r["kind"] == BB.PK_CUP]
    lines.append("TCUP: %d cup(s) (the cup's way out, padleak), its ball %s, its colour select %02Xh" % (
        len(cups), BB.MAT_NAMES[c.ball], pk[R.CRS_K["tcup"]]))
    if not cups:
        bad.append("TCUP has no cup: the cup's way out and the padleak red have nothing to hole in")
    # expoff1: WDIFF one record short must change the RAM form (the tool's own control of the same fault)
    wd = len(q.model["recs"]) > 1 and BB.expand(q.stored, q.name, _hack={"wdiff_short": True}) != q.cga
    lines.append("TQUIK: WDIFF one record short changes the RAM form: %s (expoff1)" % ("yes" if wd else "NO"))
    if not wd:
        bad.append("TQUIK: WDIFF one record short leaves the RAM form as it is - the expoff1 red cannot fire")
    # cellsafe: the SAFE rule without its OBS clause parts from the course's own cells off a lift's shaft
    shaft = set(q.slabcells)
    exc = [(x, y) for x, y, _w in BB.cells_exceptions(q.cga, _no_obs=True) if (x, y) not in shaft]
    lines.append("TQUIK: the SAFE rule without its OBS clause parts at %d cell(s) %s (cellsafe)" % (
        len(exc), exc[:6]))
    if not exc:
        bad.append("TQUIK: no prop's cell would be SAFE but for its OBS - the cellsafe red cannot fire there")
    dk = R.demo_ks()
    if R.CRS_K["roll"] not in dk:
        bad.append("ROLL has no shipped demo: wave 4's V has none to load")
    two = two_part()
    lines.append("the world part's leg: %s" % (", ".join(n.upper() for n in two) if two else
                                                "no two-part course in this build (the leg runs on none)"))
    return lines, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "vga", "both", "all"), default="all")
    ap.add_argument("--no-keys", action="store_true", help="the ways out only")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only: every red arm assembles")
    a = ap.parse_args()
    R.dev()                             # the BZDEV=1 build (SPEC.md 130.26.6.1)
    if a.check:
        lines, bad = aims()
        for line in lines:
            print("bonanza_exit aim: %s" % line)
        for line in R.check_reds(REDS, "bonanza_exit"):
            print(line)
        for b in bad:
            print("FAIL %s" % b)
        assert not bad, "%d aim failure(s)" % len(bad)
        return
    tags = {"both": ("cga", "herc"), "all": ("cga", "herc", "vga")}.get(a.adapter, (a.adapter,))
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
                want = RED_WANT[a.red]() if callable(RED_WANT[a.red]) else RED_WANT[a.red]
                assert any(want in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (a.red, tag, want, bad)
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
