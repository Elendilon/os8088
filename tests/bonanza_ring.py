#!/usr/bin/env python3
"""BONANZA: the two-way ring on MartyPC's CGA and Hercules (SPEC.md 128.2, 128.8, 128.10.11, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_ring.py [--adapter cga|herc|both] [--part glass|bench|trial|mill|play|probe|w4|hud]
    python3 tests/bonanza_ring.py --red NAME        (a red arm, below)

THE ORACLE is tools/bbcourse.py and tools/bonanza_assets.py (SPEC.md
128.10.4, 128.11.9, 128.11.10.2): the course's picture as the compiler
rendered it, and over it, in the guest's order, the SHADOW (an AND-only mask
of the ball part, 128.11.9.4) when the frame draws one, the BALL - the
MATERIAL's sprite (roll frame f = PHY * 8 + (px & 7) with its vertical phase
off the GROUND line, a squash, a shatter: bbcourse.sprite, 128.11.9.2) as
mask AND, frame OR out of the ball part's own bytes - and the occluder
records laid back by 128.10.4.4's rule at the guest's s_b, z_b and air flag
over the footprint's lines and columns (so a record in front of the ball
hides the shadow under it too).  On the Hercules the course and the ball
are the CGA bytes THROUGH bbcourse.htab() (the table bz_hgen builds, 128.11.3)
and the ball part through bonanza_assets.herc_translate_ball - so the guest's
BUILT table and its in-place translation are checked by their picture.  The
guest's card memory is decoded through the ring exactly as the 6845 scans it
- bank by line, `+ 2*S` bytes, mod 8,192 - at the package's own shown start
address bz_S, and compared PIXEL FOR PIXEL (2-bit inks on the CGA, 2-bit
card-pixel pairs on the Hercules).

What the oracle takes from the guest is the physics state the frame was drawn
from (gx, gy, gz, px, py, the material, mst, mct, sqf, the floor under an
airborne ball) - bonanzaphys holds that state to bbcourse.Physics - and
whether the frame DREW its shadow ([bz_snv]), which is a choice of the box
layout (128.11.9.4: under an occluder pass, only inside the ball's box).  That
choice is checked rather than trusted: no shadow where the model has none, a
shadow wherever the model has one and the pass is off, and its line the
model's (`spy`).

  1  THE GLASS (m.fbuf): play mode on FIRST (Enter), no key held, so the ball
     rests and every frame re-presents one picture; the card's own
     rasterisation is then the same picture - a 320 x 200 field on the CGA, a
     200-line field of 360 pixel pairs on the Hercules with nothing lit
     outside it.  Its control: the picture one word column over must NOT
     match the glass.
  2  THE BENCHMARK on BENCH (B, the autopilot, 1,200 frames) stopped at bz_tf
     (the card at the OLD bz_S must still be the last frame's picture, rules 1
     and 3's ORDER) and bz_presented (the card at the NEW bz_S this frame's
     picture) on chosen frames: the first full write, the first few of each of
     the eight scroll directions, the first few where the oracle hides part of
     the ball behind a record, then one moving frame in 97.  Every direction
     must appear and a checked frame must hide some ball behind a record.
     bz_rlate must be 0 after it.  Negative controls on a diagonal frame: the
     decode at S + 1 and a poked wrong camera must mismatch.
  3  THE TRIAL LEG (SPEC.md 128.11.17.2): the benchmark on TRIAL ([bz_crs]
     poked at bz_launch's entry; the rubber ball off H's lip, over the gap) -
     at every checked frame the card equals the oracle at bz_tf and
     bz_presented, with at least one checked frame whose SHADOW is in a box
     of its own and one with THREE OR MORE boxes; and on EVERY frame, from
     breakpoints on bz_col (BX its first row, CX its rows) and bz_boxw (SI
     the box), the column's rows and the boxes in RASTER ORDER (128.11.10.3):
     the boxes by first line, and before box j exactly the column rows that
     end above its first line (the first box at window row 0: down to its
     last line; a box holding a cell of the column, or no box: the whole
     column first); and the occluder pass's walk (bz_occ.gate) entered at
     most once a frame.
  4  THE ROW-0 PROBE (SPEC.md 128.10.11.2) and its MULTI-BOX case: play mode
     on BENCH at the top clamp in GLIDE; at bz_t0 of every probe frame the
     ball is poked airborne at window row 0, at least 16 px over a floor cell
     whose OCC and OCCG flags are clear - so its SHADOW is drawn, in a box of
     its own below the ball's - drifting right so a column enters.  At least
     five frames take 128.9 item 6's path (row 0, an entering column) and at
     least five are multi-box (a shadow box apart from the ball's); the card
     equals the oracle at bz_tf and bz_presented on every probe frame; on the
     multi-box frames interrupts are back ON (a breakpoint after bz_tb's
     POPF) before the second box is written, and bz_latechk's verdict on
     EVERY box (DL at bz_wbox's end) agrees with MartyPC's cycle counter:
     the beam reaches window line n at the sync's rise (the breakpoint where
     bz_vr saw it) + (16 + 22 + n) x 304 clocks on the CGA (mode 4: 262
     lines, the sync at line 224), against the cycles at which the box write
     started and ended.  Agreement is asserted on the CGA, the card whose
     boxes can be late (the Hercules' 98 lines of sync and blank hold every
     box ahead of the beam, 128.10.11.2); bz_latechk rounds toward LATE by
     contract, so a guest LATE the cycle model calls on time by less than
     that rounding (BZ_VLAT counts and a line) is reported, not failed.  The
     Hercules' verdicts are reported.  [bz_late] over the probe must be 0 on
     frames that are not multi-box.

  5  WAVE 3 (SPEC.md 128.12.13.2).  The oracle's MAP holds each lane's DRAWN
     pose ([bz_ldrw]; at bz_tf the contact lane is still at [bz_cold] on the
     card) and the platform is on the card at its drawn line ([bz_pline]),
     OVER or under the ball by the oracle's own rule (z_b + m < hP and s_b <=
     sP), never read off the guest's [bz_pov].  BENCH's leg pokes [bz_hvoff] 1
     (wave 2's camera: its eight directions).  THE MILL LEG, the benchmark on
     MILL with the heavy rule, checks the card at bz_tf and bz_presented on
     the frames that have (FEAT_EACH of each): a wheel commit AHEAD of the beam
     and one BEHIND it (where bz_wcommit returns to), a LEAD (the CGA's; the
     Hercules' reaches every line from a wait that saw the rise, so there it
     is reported), a contact rotor and a contact post, a deferred contact lane,
     the platform's box and its clipped box, a lane entering by a row and by a
     column, a transit (the ball not drawn) - and EVERY frame whose wheel
     commit meets the ball's old footprint, which also FAILS by the rule
     itself (wnear_check, on the MILL leg and the MILL play: never one in a
     right build) - and at each tube's exit the
     ball's footprint inside the window.  THE MILL PLAY: the ball poked onto
     the slab and ridden (the slab's layer in the riding ball's box), then
     poked under it in its shaft (the slab OVER the ball).
  6  The row-0 probe's frames are HEAVY now (a poke runs the occluder pass:
     level 1, no column), so its ball sits within the edge clause's 24 px of
     the right edge (PROBE_EDGE), and the frame BEFORE each split frame puts
     it 40 px back.
  7  WAVE 3B (SPEC.md 128.13.12).  On the MILL leg and the MILL play every
     frame's boxes are read at the frame's first bz_boxc (bz_ts + 9, after
     bz_mkboxes, before any compose): each at most BZ_BOXW x BZ_BOXL (4 x
     32), each PLATFORM box at most 30 lines (18 + 2 x 6), and the
     platform's own rect (bz_crect when bz_ctype is 2, bz_crect2 beside a
     lighting post) at most 30 before any clip.  ORACLE CHECK 5:
     after every wheel commit (at bz_tf; the LEAD's at bz_presented) the
     committed lane's map words in the course part are its DRAWN pose's.
     THE RING'S END: every frame of any leg whose 3- or 4-word box has a
     whole card row, not the whole-row path's first, crossing 2000h, and no
     band (`wrapbox`) is checked at bz_presented, at least one a card; and
     every frame with a WHEEL COMMIT whose rectangle's columns cross it
     (`wrapcommit`: the pass's row-at-a-time path) at FEAT_EACH, required on
     the Hercules (MILL's post 4), reported on the CGA.  The PWAIT scene
     asserts the one-wait rule itself: no two frames running with bz_pyld.  The MILL
     play adds: THE RIDE BOX (`ridebox`: the platform's box merged into the
     riding ball's group, bz_ctype 2 with no rect of its own) - at least
     FEAT_EACH checked a card; THE DEFER SCENE (128.13.7 item 1: a post
     kicked so it is really drawn lit, its lit frames poked to 0, the ball
     then two boxes every frame for four frames, one of them meeting the
     post's corner - it WAITS with lit cells outside every box, card =
     oracle, at least one such frame); and THE PWAIT SCENE (the ball
     airborne at two points 48 px apart while the lift rises from its dock,
     the window's bottom edge through the slab, TRICKLE: every WAITED frame
     and the frame after it checked - `pwait`, at least FEAT_EACH a card -
     at least 20 lift steps inside it, and a waited frame on which an
     entering row meets the slab's drawn footprint, bz_ctype 3, by the ball
     poked across the band's foot; ended at one point, so the slab's box is
     drawn and sized).
  8  WAVE 4 (SPEC.md 128.14.14).  The oracle's hidden ball is bz_hidn (in a
     tube, or HOLED OUT: its capture frame draws the course where it was).
     THE W4 PART (`w4`), the HUD OFF: MOON's shipped demo replayed (R) - a
     fall, a RETURN, its three pads, its flags, its cup - then
     bonanzaphys's model-proved `cup-128` and `cup-lip` (PEAK's cup: a
     capture, a lip-out's pop), each under the frame loop: the card equal
     to the oracle at bz_presented on every full write (the first and every
     respawn's cut), the capture frame, every lip-out's frame, every frame
     a FLAG's drawn pose changed (raised, committed or promoted), every pad
     swap's, and one frame in W4_EVERY; and THE BLANK (128.14.5.6) from an
     `io` breakpoint on 3D8h / 3B8h: the video-enable bit CLEAR before
     every full write's first row and at its bz_presented, SET again by the
     next frame's.  THE HUD PART (`hud`, only while the build carries it,
     128.14.16 item 4): MILL's route demo replayed with the HUD FOLLOW, REST
     under GLIDE and under TRICKLE, and OFF - the oracle composes the PANEL
     (bz_hpan, itself the host's render of bz_hdisp) over the rect while it
     is on the card, at bz_tf (bz_hwas: the last panel seen) and at
     bz_presented (bz_hon), on every full write, every HUD box kind's first
     HUD_EACH, the first HUD_EACH of each scroll direction with the panel
     shown, every REST release and one frame in HUD_EVERY; on those frames
     THE WRITE-ONCE CHECK: the rect's card bytes at the old and the new
     window under `mem` breakpoints from bz_tr to bz_presented (a full
     write's set to SENTINEL first), no byte receiving two different values
     in a frame; OFF never shows the panel; REPORTED the shown share, the
     boxes by kind, the releases, the five-box frames.  Then THE LANE SCENE:
     play mode on MILL, FOLLOW, TRICKLE, a centred full write putting a
     rotor or post under the rect (bonanza_wheel.hud_plan), the ball held,
     the lane made due every fourth frame: the card equal to the oracle with
     the panel at every bz_presented - the lane never written over the panel
     - its promotions REPORTED.

--red NAME is the row's red arm (docs/WRITING-TESTS.md 1): it copies
apps/bonanza/ to a temporary directory, breaks one thing there, builds that
package and its 360KB floppy into the same temporary directory (never
build/), runs the parts that can see it and PASSES only if they FAIL at
their own check:
  colright   the entering column moving right is the window's column W, not
             W - 1 (a content error: the right edge is left stale)
  colfirst   the entering column written BEFORE the retrace wait and the flip
             (the same bytes in the end: only the bz_tf check sees it)
  late       every frame counts a late box: the bz_rlate assertion's plumbing
  row0       item 6's order undone (the whole column before a row-0 box):
             [bz_late] above 0 on the probe - the CGA only (RED_TAGS)
  occ        the occluder pass skipped: a checked frame behind a record differs
  shadow     the shadow composed into ITS OWN box only (group 1): where the
             ball's box covers it - a Hop, a flight's last lines - the card
             differs (the TRIAL leg)
  boxfirst   every box before any column row: the raster-order check fails
  htab       one bit of bz_hgen's output flipped (BZ_HTAB[55h], a cyan byte
             on an even line): the Hercules picture differs
  late2      bz_latechk on the first box only: on the CGA the cycle counter
             disagrees on a multi-box frame (the probe)
  pass2      the occluder pass run once per box: its walk entered twice on a
             two-box frame (the TRIAL leg)
  contact    the contact choice and the wheel's box test taken out: a due
             lane beside the ball is the wheel's, which writes it over the
             ball still on the glass - at bz_tf, by the rule itself (a wheel
             commit meeting the ball's or the shadow's OLD footprint inside
             the windows, wnear_check) or the card.  OPEN (SPEC.md 128.14.27
             item 3): no scene yet gives the broken wheel ROOM to commit such
             a lane - the DEFER scene's post is its candidate but is promoted
             (BZ_WPRF) before it loads - so the arm goes red at the DEFER
             scene's coverage instead
  defer      a WAITING contact lane's map words synced anyway: its new pose in
             the box, the old outside it - a `defer` frame (the MILL leg)
  padfront   the platform never over the ball: a `pover` frame (the MILL play)
  hidden     the ball boxed and drawn in a transit: a `transit` frame
  ridebox    (3b) the RIDE BOX composed without the slab's layer under the
             ball: a `ridebox` frame of the MILL play
  pwait2     (3b) the wait's "never two running" taken out: the slab waits on
             every crowded frame - two PWAIT frames running with bz_pyld set,
             caught at bz_tf by the rule itself (the box-size check sees it
             only when the lift rose far enough during the scene)
  fastwrap   (3b) bz_bwrows's ring test taken out: a crossing row written down
             the unrolled block - a `wrapbox` frame (the MILL play's
             ring's-end scene)
  mapskip    (3b) the pass's map stores left out: oracle check 5 (MILL)
  wrapmask   (3b review) the pass's row-at-a-time path across the ring's end
             without its mask: a `wrapcommit` frame (MILL's post 4, Hercules)
  (and `defer` is judged on the DEFER scene now: the MILL play)
  hudinset   (wave 4) the HUD's inset taken to 0: an entering row writes the
             panel's cells and the HUD's box writes them again - `two values`
             on a FOLLOW scroll frame (HUD only)
  hudold     (wave 4) FOLLOW's step without the old rect: the panel left
             where it was - the oracle at bz_presented (HUD only)
  hudlane    (wave 4) the wheel's HUD-rect test removed: a commit writes the
             lane over the panel - the LANE SCENE's oracle (HUD only)
  hudfull    (wave 4) the full write's span skip removed while shown: the
             rect gets the course, then the panel - `two values` (HUD only)
  noblank    (wave 4) the blank left out: a full write with the video enabled
             - the W4 replays' blank check

The module is also the LIBRARY the other BONANZA rows share (bonanza_perf,
bonanza_phys, bonanza_exit, bonanza_mega, bonanza_replay, bonanza_wheel):
`symbols`, `Bz`, `Ref`, `Walker`, `poke_ball`, `make_log` (a log stamped with
its course's identity, SPEC.md 128.12.8), `build_tree` and the course cache.
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import os88geom as G           # noqa: E402
import os88build               # noqa: E402
import bonanza_assets as A     # noqa: E402
import bbcourse as BB          # noqa: E402

MACHINE = {"cga": "os8088_5150_cga_gla", "herc": "os8088_5150_herc_gla"}
W = {"cga": 320, "herc": 360}       # game pixels across the window
RL = {"cga": 2, "herc": 4}          # lines a card row
RB = {"cga": 80, "herc": 90}        # bytes a line
FILES = ("bonanza.asm", "bzvideo.inc", "bzgame.inc", "bzwheel.inc", "bzphys.inc", "bzsound.inc")
EXTRA_SYMS = ("op_table",)          # os88parts.inc's: the part rows (bonanza_exit)
# NASM local labels a row breakpoints (proc, local): resolved by the same
# assembly when the source has them (a red tree, or an older wave, may not)
LOCAL_SYMS = (("bz_tb", "first"), ("bz_wbox", "wr"), ("bz_wbox", "out"), ("bz_vr", "rose"),
              ("bz_vr", "high"), ("bz_occ", "gate"),
              # wave 3 (SPEC.md 128.12.5.3): where a bz_wcommit RETURNS to says which way
              # the pose reached the glass - pass 1 (AHEAD) returns before .an, pass 2
              # (BEHIND) between .p2 and .nofit, the LEAD inside bz_lead
              ("bz_wheel", "an"), ("bz_wheel", "p2"), ("bz_wheel", "nofit"), ("bz_wheel", "out"),
              ("bz_lead", "no"), ("bz_props", "choose"), ("bz_props", "mlane"),
              ("bz_exitchk", "leave"),
              # wave 3b (SPEC.md 128.13.4.3, 128.13.12): the platform's box WAITED and a lane
              # PROMOTED (bz_props's two entries), and the sound's span a frame (128.20.7)
              ("bz_props", "pwt"), ("bz_props", "promo"), ("bzs_frame", "fend"),
              # wave 4 (SPEC.md 128.14.14): a demo file's read (bonanzademo: the disk is touched
              # there, and FERR_BIG lands in .rerr), the tour's post and the respawn's blank
              ("bz_lfile", "read"), ("bz_lfile", "rerr"))
DIRS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]
FIRST_EACH = 3                      # frames checked per direction, first ones
LAY_EACH = 6                        # ...and the first frames that laid a record
SHD_EACH = 4                        # ...and (TRIAL) the first with a shadow box of its own
B3_EACH = 3                         # ...and the first with three boxes or more
EVERY = 97                          # ...and then one moving frame in this many
PROBE_MIN = 5                       # row-0 probe frames a card (SPEC.md 128.10.11.2)
PROBE_MAX = 30                      # probe frames run at most
PROBE_SPLIT = 7                     # from this probe frame, every other one SPLIT: the ball poked 40 px
                                    # back, so its old and new footprints are two boxes at row 0 and the
                                    # second is behind the beam on the CGA - the later-box verdict judged
BZ_BOXD = 20                        # bzvideo.inc: a box descriptor
BZ_VLAT = 56                        # bzvideo.inc: PIT counts, the rise to the sample at most
CGA_LINE = 304                      # clocks a CGA line (76 PIT counts, 912 dots / 3)
CGA_TO0 = 16 + 22                   # CGA lines from the sync's rise to window line 0
SPIN_TOL = 60                       # clocks: bz_vr's tight spin turn (the rise to its stop)


class _CourseTable(dict):
    """name -> K or name -> the .bbc path, read on first use out of the GENERATED
    bzcourse.inc (its `BZ_CRS_<NAME> equ K ; file.bbc, "title"` lines), which
    bbcourse.py writes from the Makefile's BZ_COURSES - the one authority on
    the courses and their order - so a course added or reordered there needs
    no edit here.  (Lazy, so the module imports with nothing built.)"""

    def __init__(self, which):
        dict.__init__(self)
        self.which = which

    def __missing__(self, key):
        if dict.__len__(self):
            raise KeyError(key)
        inc = os.path.join(ROOT, at("build/bonanza-art"), "bzcourse.inc")
        with open(inc) as f:
            txt = f.read()
        for m in re.finditer(r"^BZ_CRS_([A-Z0-9_]+)\s+equ\s+(\d+)\s*;\s*(\S+\.bbc)\b", txt, re.M):
            name = m.group(1).lower()
            self[name] = int(m.group(2)) if self.which == "k" else "apps/bonanza/courses/" + m.group(3)
        if not dict.__len__(self):
            raise SystemExit("bonanza rows: %s names no course (`make bonanzadisk`)" % inc)
        return dict.__getitem__(self, key)


COURSES = _CourseTable("path")      # bzcourse.inc's names -> the course file
CRS_K = _CourseTable("k")           # ...and -> K, BZ_COURSES's order
LUT = [bytes(((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3)) for b in range(256)]
_COURSE = {}
_BALL = {}


def at(p):
    return os88build.at(p)


def course(name, src=None):
    """bbcourse's compile of a course, once a process (a few seconds each).
    SRC: a course file other than the shipped one (a red tree's)."""
    path = src or os.path.join(ROOT, COURSES[name])
    if path not in _COURSE:
        _COURSE[path] = BB.compile_course(path)
    return _COURSE[path]


def course_k(k):
    """course K's compile (BZ_COURSES's order)"""
    name = [n for n in CRS_K if CRS_K[n] == k] if dict.__len__(CRS_K) else None
    if not name:
        CRS_K["bench"]                           # (fills the table)
        name = [n for n in CRS_K if CRS_K[n] == k]
    return course(name[0])


def ball_part(mat, tag, art=None):
    """the material's BZB2 part as the card holds it: the CGA's bytes, or on
    the Hercules those bytes through htab() (bonanza_assets.herc_translate_ball,
    the translation bz_hxlat makes at the fetch, SPEC.md 128.11.3)"""
    art = art or at("build/bonanza-art")
    key = (mat, tag, art)
    if key not in _BALL:
        with open(os.path.join(ROOT, art, A.BALL_FILES[mat]), "rb") as f:
            part = f.read()
        _BALL[key] = A.herc_translate_ball(part, BB.htab()) if tag == "herc" else part
    return _BALL[key]


def _has_local(text, proc, local):
    """does PROC (a `bz_x:` line) have the local label `.local:` before the next proc?"""
    m = re.search(r"^%s:" % re.escape(proc), text, re.M)
    if not m:
        return False
    nxt = re.search(r"^bz_\w+:", text[m.end():], re.M)
    body = text[m.end():m.end() + nxt.start()] if nxt else text[m.end():]
    return re.search(r"^\.%s:" % re.escape(local), body, re.M) is not None


def symbols(src=None, art=None):
    """Every bz_ label and VAR of the package (and EXTRA_SYMS, and LOCAL_SYMS as
    'proc.local'), by assembling it with a table of `dw label` on the end (the
    guest's own offsets, no listing parsing).  A file of FILES a source does not
    have is skipped: an earlier wave's package (bonanza_perf's A/B leg)."""
    d = src or os.path.join(ROOT, "apps", "bonanza")
    art = art or at("build/bonanza-art")
    names = []
    for f in FILES:
        p = os.path.join(d, f)
        if not os.path.exists(p):
            continue
        t = open(p).read()
        names += re.findall(r"^VAR (bzs?_\w+),", t, re.M)      # (bzs_: the sound's, 128.20)
        names += re.findall(r"^(bzs?_\w+):", t, re.M)
        names += [n for n in EXTRA_SYMS if re.search(r"^%s:" % n, t, re.M)]
        names += ["%s.%s" % (pr, lo) for pr, lo in LOCAL_SYMS if _has_local(t, pr, lo)]
    inc = os.path.join(ROOT, "apps", "os88parts.inc")
    names += [n for n in EXTRA_SYMS if re.search(r"^%s:" % n, open(inc).read(), re.M)]
    names = sorted(set(names))
    apps = os.path.join(os.path.dirname(d), "") if os.path.exists(
        os.path.join(os.path.dirname(d), "os88api.inc")) else os.path.join(ROOT, "apps") + "/"
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "probe.asm")
        b = os.path.join(td, "probe.bin")
        open(p, "w").write(open(os.path.join(d, "bonanza.asm")).read() + "\n" +
                           "\n".join("dw " + n for n in names))
        subprocess.run(["nasm", "-f", "bin", "-I", apps, "-I", d + "/", "-I", art + "/", "-o", b, p],
                       cwd=ROOT, check=True)
        raw = open(b, "rb").read()
        return dict(zip(names, struct.unpack("<%dH" % len(names), raw[-2 * len(names):])))


def make_log(keys, k, mat, ident=None):
    """bbcourse.encode_log's bytes for course K, stamped with that course's
    IDENTITY at +14 (SPEC.md 128.12.8: a replay REFUSES a log whose identity is
    not its course part's), unless IDENT is given (a row's refusal case)"""
    return BB.encode_log(keys, course=k, mat=mat, ident=course_k(k).ident if ident is None else ident)


def lane_rects(crs):
    """{record: (first word column, first block row, words, block rows, poses)}
    of every lane of a compiled course, the prop table's own (SPEC.md 128.12.3.1)"""
    return {r["i"]: (r["lane"]["col"], r["lane"]["brow"], r["lane"]["w"], r["lane"]["h"], r["lane"]["poses"])
            for r in crs.part["props"] if r["lane"]}


def true_pose(rec, nstep, pkick=None, hold=None):
    """a lane's TRUE pose after the frame's steps (bz_ltrue, SPEC.md 128.12.3.4,
    128.12.15 item 1): a rotor's from the LAST step's n (nstep - 1, the low
    word); a post's LIT while it has lit frames left on the glass ([bz_lhold],
    HOLD - display state, 128.12.6.3 as the owner's preview amended it: a kick
    gives it its record's lit frames, counted off only on frames it began
    drawn lit)"""
    if rec["kind"] == BB.PK_WINDMILL:
        return (((nstep - 1) + rec["seed"]) & rec["mask"] & 0xFFFF) >> rec["shift"]
    return 1 if hold is not None and hold[rec["i"]] else 0


def unpack_ball(tag):
    return A.ball_herc_pairs if tag == "herc" else A.ball_frame_indices


def _row_pix(data, o, n=A.RB):
    """N bytes at O as their 4N 2-bit pixels, leftmost first"""
    out = []
    for b in data[o:o + n]:
        out += LUT[b]
    return out


class Look(object):
    """what a frame was drawn from: the guest's physics state, read at a stop
    (Bz.look), shaped as bbcourse.sprite and bbcourse.shadow read a Physics"""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    @property
    def G8(self):
        return (self.gx + self.gy) >> 9

    def cell(self, wx, wy):
        return self.grid.cell(wx, wy)

    def key(self):
        return (self.px, self.py, self.sb, self.zb, self.air, self.spr, self.spy, self.gate)


class Ref:
    """The host's picture of one course on one card: bbcourse's render, the
    shadow, the material's sprite and the records laid back over it."""

    def __init__(self, tag, crs, art=None):
        self.tag, self.c, self.art = tag, crs, art
        pic = crs.pic
        self._ht = BB.htab() if tag == "herc" else None
        if tag == "cga":
            self.rows = [bytes(r) for r in pic]
        else:                       # the CGA's bytes through htab(), the table bz_hgen builds
            self.rows = [self._hrow(r, L) for L, r in enumerate(pic)]
        # wave 3 (SPEC.md 128.12.4.1): the MAP holds each lane's DRAWN pose, so the
        # course the card shows is the picture with every lane at the pose the
        # guest's bz_ldrw names; and the platform is on the card at its drawn line
        self._lanes = {r["i"]: BB._lane_of(crs, r) for r in crs.part["props"] if r["lane"]} \
            if crs.part.get("props") else {}
        self._plat = next((r for r in crs.part.get("props") or () if r["kind"] == BB.PK_PLATFORM), None)
        self._vcache = {}
        self.view = None            # (lanes {record: pose}, slab (x_l, y_t, over) or None), or None

    def rule(self, view, lk):
        """VIEW with the slab's over-or-under decided by the ORACLE, not read off
        the guest's [bz_pov]: OVER the ball when z_b + m < hP and s_b <= sP
        (SPEC.md 128.12.4.5; m 0 airborne, BZ_CLIMB grounded; sP the cell row of
        the square's centre at the drawn line), and never over a hidden ball"""
        if not view or not view[1] or self._plat is None:
            return view
        P = self._plat
        x_l, y_t = view[1][0], view[1][1]
        top = P["hP"] + BB.slab_rise(P, y_t, self.c.part["grid"]["x0"], self.c.part["grid"]["y0"])
        sP = BB.slab_s(P)
        over = not getattr(lk, "tube", 0) and lk.zb + (0 if lk.air else BB.CLIMB) < top and lk.sb <= sP
        return (view[0], (x_l, y_t, over))

    def _hrow(self, r, L):
        """a row of CGA inks (4-aligned) as the Hercules shows it on line L"""
        out = []
        for x in range(0, len(r), 4):
            b = (r[x] << 6) | (r[x + 1] << 4) | (r[x + 2] << 2) | r[x + 3]
            out += LUT[self._ht[256 * (L & 1) + b]]
        return bytes(out)

    def lane_rows(self, lanes):
        """the course's rows with each lane at the pose LANES names ({record: pose},
        a pose not in the lane - bz_pread's FFh - leaves the picture's)"""
        if not lanes:
            return self.rows
        key = tuple(sorted(lanes.items()))
        if key in self._vcache:
            return self._vcache[key]
        rows = list(self.rows)
        for i, q in lanes.items():
            L = self._lanes.get(i)
            if L is None or q not in L["pics"]:
                continue
            bx, by = L["rect"][0], L["rect"][1]
            for y, row in enumerate(L["pics"][q]):
                Ly = 8 * by + y
                seg = bytes(row) if self.tag == "cga" else self._hrow(row, Ly)
                r = bytearray(rows[Ly])
                r[8 * bx:8 * bx + len(seg)] = seg
                rows[Ly] = bytes(r)
        if len(self._vcache) > 256:
            self._vcache.clear()
        self._vcache[key] = rows
        return rows

    def slab_pix(self, x_l, y_t, under):
        """{(x, y): card value} of the platform's sprite at (x_l, y_t) over the
        values UNDER ({(x, y): value}, or a rows list): mask AND, frame OR byte
        by byte (SPEC.md 128.12.6.4; on the Hercules the frame's row r through
        htab's table (y_t + r) AND 1, 128.11.3)"""
        out = {}
        slab = self.c.slab
        for r in range(BB.PL_H):
            y = y_t + r
            for x in range(BB.PL_W):
                ink = slab.get((x, r))
                if ink is None:
                    continue
                if self.tag == "cga":
                    v = ink
                else:
                    b = ink << (6 - 2 * (x & 3))
                    v = LUT[self._ht[256 * (y & 1) + b]][x & 3]
                out[(x_l + x, y)] = v
        return out

    def base(self, view):
        """(the rows the card shows under the ball - lanes at their drawn poses,
        the slab at its drawn line - , the rows the occluder records lay back
        from: the MAP's, lanes but no slab)"""
        if not view:
            return self.rows, self.rows
        lanes, slab = view
        lrows = self.lane_rows(lanes)
        if not slab:
            return lrows, lrows
        rows = list(lrows)
        for (x, y), v in self.slab_pix(slab[0], slab[1], None).items():
            if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
                r = bytearray(rows[y])
                r[x] = v
                rows[y] = bytes(r)
        return rows, lrows

    def foot(self, lk, view=None):
        """-> ({(x, y): card value} over the shadow's and the ball's footprints,
        ball pixels the records hid).  LK: a Look; VIEW: Bz.view()'s (the
        lanes' drawn poses and the slab), or None for a course without props.
        A HIDDEN ball (in a tube, SPEC.md 128.12.6.1) draws nothing."""
        view = view if view is not None else self.view
        if getattr(lk, "tube", 0):
            return {}, 0
        rows, lay = self.base(view)
        part = ball_part(lk.mat, self.tag, self.art)
        x4 = lk.px & ~3
        s = lk.px & 3
        out = {}
        if lk.spy is not None:                   # the shadow: AND only (128.11.9.4)
            mo = A.B2_SHDOFF + ((lk.spy & 1) * A.SHIFTS + s) * A.SHD_ROWS * A.RB
            for r in range(A.SHD_ROWS):
                y = lk.spy + r
                if not 0 <= y < len(rows):
                    continue
                for j, mp in enumerate(_row_pix(part, mo + r * A.RB)):
                    out[(x4 + j, y)] = rows[y][x4 + j] & mp
        kind, k = lk.spr                         # the sprite: mask AND, frame OR
        if kind == "roll":
            mo, fo = A.B2_MASKOFF + s * A.D * A.RB, A.B2_FRMOFF + k * A.D * A.RB
        else:
            base = A.B2_SQOFF if kind == "squash" else A.B2_SHAOFF
            mo = base + ((k * A.SHIFTS + s) * 2 + (lk.py & 1)) * A.ENT
            fo = mo + A.ENT // 2
        ball = {}
        for r in range(A.D):
            y = lk.py + r
            mrow, frow = _row_pix(part, mo + r * A.RB), _row_pix(part, fo + r * A.RB)
            for j in range(A.RB * 4):
                v = out.get((x4 + j, y), rows[y][x4 + j] if 0 <= y < len(rows) else 0)
                nv = (v & mrow[j]) | frow[j]
                out[(x4 + j, y)] = nv
                if mrow[j] != 3:
                    ball[(x4 + j, y)] = nv
        hidden = 0
        if lk.gate:                              # the records (128.10.4.4's rule) over the
            m = 0 if lk.air else BB.CLIMB       # footprint's lines and the ball's columns
            for br in range(lk.py >> 3, ((lk.py + BB.FOOT_H - 1) >> 3) + 1):
                for bc in range(x4 >> 3, ((x4 + BB.FOOT_W - 1) >> 3) + 1):
                    for rec in self.c.by_block.get((br, bc), ()):
                        if lk.sb < rec["s"] and lk.zb + m < rec["top"]:
                            for (x, y) in rec["pix"]:
                                if lk.py <= y < lk.py + BB.FOOT_H and x4 <= x < x4 + BB.FOOT_W \
                                        and (x, y) in out:
                                    if (x, y) in ball and out[(x, y)] != lay[y][x]:
                                        hidden += 1
                                    out[(x, y)] = lay[y][x]
        if view and view[1] and view[1][2]:     # the slab OVER the ball: last (128.12.4.5)
            for xy, v in self.slab_pix(view[1][0], view[1][1], None).items():
                if xy in out:
                    out[xy] = v
        return out, hidden

    def picture(self, R0, c0, lk, view=None):
        """200 rows (bytes) of the window whose top card row is R0 and left word
        column c0, drawn from LK (a Look) under VIEW (Bz.view's: the lanes'
        drawn poses and the slab; None: self.view, then the bare course)"""
        view = view if view is not None else self.view
        top, left, w = R0 * RL[self.tag], c0 * 8, W[self.tag]
        rows = self.base(view)[0]
        fp, _ = self.foot(lk, view)
        out = []
        for y in range(200):
            L = top + y
            row = rows[L][left:left + w]
            if any((x, L) in fp for x in range(lk.px & ~3, (lk.px & ~3) + BB.FOOT_W)):
                row = bytearray(row)
                for x in range(max(left, lk.px & ~3), min(left + w, (lk.px & ~3) + BB.FOOT_W)):
                    v = fp.get((x, L))
                    if v is not None:
                        row[x - left] = v
                row = bytes(row)
            out.append(row)
        return out


class Bz:
    """One guest with BONANZA's window open; every read is of a paused machine."""

    def __init__(self, ui, tag, sym, live=False):
        """LIVE: every address re-reads the window's W_SEG first (a row whose
        launches claim and drop, and so may see the movable region compacted
        under it, bonanza_exit); otherwise the base is banked once and
        check_base() says if it moved."""
        self.ui, self.m, self.tag, self.sym, self.live = ui, ui.m, tag, sym, live
        self.win = ui.window("Bounce Bonanza")
        self.base = self.wseg() << 4
        assert self.base, "the window has no package segment"

    def wseg(self):
        raw = self.m.read(self.m.sym("wm_wins"), G.MAX_WIN * G.WIN_SIZE)
        return struct.unpack_from("<H", raw, self.win.i * G.WIN_SIZE + G.W_SEG)[0]

    def check_base(self):
        """The region is OS88_REGION_MOVABLE: a compaction during a fetch could
        have moved it under every address banked from the old base."""
        now = self.wseg() << 4
        assert now == self.base, ("BONANZA's region moved from %05X to %05X (a compaction during op_fetch): "
                                  "the banked addresses are stale" % (self.base, now))

    def a(self, n):
        if self.live:
            self.base = self.wseg() << 4
        return self.base + self.sym[n]

    def b(self, n):
        return self.m.read(self.a(n), 1)[0]

    def w(self, n):
        return struct.unpack("<H", self.m.read(self.a(n), 2))[0]

    def s(self, n):
        return struct.unpack("<h", self.m.read(self.a(n), 2))[0]

    def d(self, n):
        return struct.unpack("<I", self.m.read(self.a(n), 4))[0]

    def sd(self, n):
        return struct.unpack("<i", self.m.read(self.a(n), 4))[0]

    def put(self, n, v):
        self.m.write(self.a(n), struct.pack("<H", v & 0xFFFF))

    def putb(self, n, v):
        self.m.write(self.a(n), bytes([v & 0xFF]))

    def putd(self, n, v):
        self.m.write(self.a(n), struct.pack("<I", v & 0xFFFFFFFF))

    def state(self):
        """(S, R0, c0, px, py) as the package holds them now."""
        return (self.w("bz_S"), self.w("bz_R0"), self.w("bz_c0"), self.w("bz_px"), self.w("bz_py"))

    def look(self, crs):
        """The Look the frame the guest holds now was drawn from (at bz_tf or
        bz_presented), CRS the host's course (its cells: the OCC gate and OCCG):
        the physics state, the sprite bbcourse.sprite chooses from it, and the
        shadow - drawn when [bz_snv] says the box layout drew it, which is
        CHECKED against the model's candidate (bbcourse.shadow): -> (Look, a
        complaint or None)."""
        grid = getattr(crs, "_grid", None)
        if grid is None:
            grid = crs._grid = BB.Grid(crs.cga)
        lo = self.sym["bz_phs"]
        raw = self.m.read(self.base + lo, self.sym["bz_phe"] - lo)

        def f(n, fmt):
            return struct.unpack_from(fmt, raw, self.sym[n] - lo)[0]
        lk = Look(grid=grid, gx=f("bz_gx", "<I"), gy=f("bz_gy", "<I"), gz=f("bz_gz", "<i"), air=f("bz_air", "B"),
                  mst=f("bz_mst", "B"), mct=f("bz_mct", "B"), sqf=f("bz_sqf", "B"), ghv=f("bz_ghv", "B"),
                  gh=f("bz_gh", "<h"), sb=f("bz_sb", "<H"), pokd=f("bz_pokd", "B"),
                  mat=self.b("bz_mat"), px=self.w("bz_px"), py=self.w("bz_py"), y0=grid.y0)
        lk.zb = lk.gz >> 8
        # the HIDDEN ball (SPEC.md 128.14.19 item 4): bz_hidn, in a tube or HOLED OUT - its capture frame
        # restores its footprint; an earlier wave's build has bz_tube alone
        lk.tube = self.b("bz_hidn") if "bz_hidn" in self.sym else f("bz_tube", "B") if "bz_tube" in self.sym else 0
        lk.spr = BB.sprite(lk, self.tag == "herc")
        if lk.tube:                              # hidden in a tube: no sprite, no shadow
            lk.gate, lk.spy = False, None
            return lk, ("the guest drew a shadow ([bz_snv] 1) for a hidden ball (a tube, or holed)"
                        if self.b("bz_snv") else None)
        centred = not lk.pokd
        cell = grid.cell(lk.gx >> 12, lk.gy >> 12)
        # bz_occ's gate (bz_mkboxes: the centre's OCC airborne, its OCCG grounded,
        # or a harness's poke): with no poke since the last step the window is
        # centred on the ball's cell, whose flag is read from the HOST's course,
        # so a wrong flag still shows
        lk.gate = not centred or bool(cell[4] & (BB.FL_OCC if lk.air else BB.FL_OCCG))
        cand = BB.shadow(lk)                     # (spy, px) or None
        drawn = self.b("bz_snv")
        why = None
        if drawn and cand is None:
            why = "the guest drew a shadow ([bz_snv] 1) where the model has none"
        elif cand is not None and not drawn and not lk.gate and not self.fifth():
            why = "the guest drew no shadow where the model has one and no occluder pass runs"
        elif drawn and cand is not None and self.s("bz_spy") != cand[0]:
            why = "the guest's shadow line [bz_spy] %d is not the model's %d" % (self.s("bz_spy"), cand[0])
        lk.spy = cand[0] if (drawn and cand is not None) else None
        return lk, why

    def fifth(self):
        """a frame with a CONTACT group may leave the shadow's new footprint out
        (SPEC.md 128.12.4.3: the contact group would be a fifth box) - the one
        other frame that draws no shadow where the model has one"""
        return "bz_ctype" in self.sym and self.b("bz_ctype") != 0

    def lanes(self):
        """{record: DRAWN pose} of the course's lanes ([bz_ldrw], SPEC.md
        128.12.4.1), or {} for a build or course without them"""
        if "bz_ldrw" not in self.sym:
            return {}
        n = self.b("bz_nlane")
        return dict(enumerate(self.m.read(self.a("bz_ldrw"), n))) if n else {}

    def slab(self):
        """(x_l, y_t, over) of the platform as the card holds it ([bz_pox],
        [bz_pline], [bz_pov] 1), or None: no platform, or none on the card"""
        if "bz_pidx" not in self.sym or self.b("bz_pidx") == 0xFF:
            return None
        pl = self.w("bz_pline")
        if pl == 0x8000:
            return None
        return (self.w("bz_pox"), pl, self.b("bz_pov") == 1)

    def view(self, at_tf=False, prev=None):
        """what the course on the card is drawn from: (lanes, slab).  At bz_tf
        (AT_TF) the card still shows the LAST frame's slab (PREV's: bz_props has
        already moved [bz_pline] to its new line, drawn by this frame's box after
        the flip) and the contact lane at its pose BEFORE its sync ([bz_cold]):
        the old window, untouched but for the wheel's commits"""
        lanes = self.lanes()
        if not at_tf:
            return (lanes, self.slab())
        if lanes and self.b("bz_ctype") == 1:
            lanes[self.b("bz_cln")] = self.b("bz_cold")
        return (lanes, prev[1] if prev else None)

    def phys(self):
        """(nstep, gx, gy, gz, gvx, gvy, gvz, air): bbcourse.Physics.state()'s shape"""
        return (self.d("bz_nstep"), self.d("bz_gx"), self.d("bz_gy"), self.sd("bz_gz"),
                self.s("bz_gvx"), self.s("bz_gvy"), self.s("bz_gvz"), self.b("bz_air"))

    def boxes(self):
        """[(x0, y0, w, h, group)] of the frame's boxes, in their write order"""
        n = self.w("bz_nbox")
        raw = self.m.read(self.a("bz_boxes"), 4 * BZ_BOXD)
        return [struct.unpack_from("<HhHH", raw, i * BZ_BOXD) + (raw[i * BZ_BOXD + 18],) for i in range(min(n, 4))]

    def boxes5(self):
        """boxes() with the FIFTH descriptor too, the HUD's group (SPEC.md
        128.14.5.4) when the build carries it, else boxes()"""
        if "bz_hmode" not in self.sym:
            return self.boxes()
        n = self.w("bz_nbox")
        raw = self.m.read(self.a("bz_boxes"), 5 * BZ_BOXD)
        return [struct.unpack_from("<HhHH", raw, i * BZ_BOXD) + (raw[i * BZ_BOXD + 18],) for i in range(min(n, 5))]

    def read_log(self):
        """bz_rlog's 4,096 bytes"""
        return self.m.read(self.a("bz_rlog"), BB.RLOG_SIZE)

    def write_log(self, log):
        """a log (bbcourse.encode_log's bytes) into bz_rlog, the rest zeroed"""
        assert len(log) <= BB.RLOG_SIZE
        self.m.write(self.a("bz_rlog"), bytes(log) + bytes(BB.RLOG_SIZE - len(log)))

    def decode(self, S):
        """The card memory as the 6845 scans it from start address S (words)."""
        tag = self.tag
        raw = self.m.read(0xB8000, 0x4000) if tag == "cga" else self.m.read(0xB0000, 0x8000)
        rb, nb = RB[tag], RL[tag]
        out = []
        for y in range(200):
            bank = (y % nb) * 0x2000
            o = ((y // nb) * rb + 2 * S) % 8192
            line = raw[bank + o:bank + min(o + rb, 8192)]
            if len(line) < rb:
                line += raw[bank:bank + rb - len(line)]
            out.append(b"".join(LUT[c] for c in line))
        return out

    def key(self, name):
        """A press the package sees: down, 40 ms of guest time, up (the launch waits for the release)."""
        self.m.key(name, up=False)
        M.pace(self.m, .04)
        self.m.key(name, down=False)


def diff(got, exp):
    """-> (pixels that differ, their box) for two lists of rows."""
    n, ys, xs = 0, [], []
    for y, (g, e) in enumerate(zip(got, exp)):
        if g != e:
            bad = [x for x in range(len(e)) if g[x] != e[x]]
            n += len(bad)
            ys.append(y)
            xs += [bad[0], bad[-1]]
    return n, (min(ys), max(ys), min(xs), max(xs)) if n else None


class Walker:
    """The frame loop under breakpoints: bz_tf and bz_presented (and bz_t0, and
    EXTRA: more names of the package's to stop on, each returned by its name)."""

    def __init__(self, g, t0=False, extra=()):
        self.g, self.m = g, g.m
        self.tf, self.pr = g.a("bz_tf"), g.a("bz_presented")
        self.t0 = g.a("bz_t0") if t0 else None
        self.extra = {}
        for n in extra:
            if isinstance(n, tuple):             # (name, offset): an address past a label
                self.extra[g.a(n[0]) + n[1]] = "%s+%d" % n
            else:
                self.extra[g.a(n)] = n

    def arm(self):
        self.m.bp_exec(*([a for a in (self.t0, self.tf, self.pr) if a is not None] + list(self.extra)))

    def next(self):
        """Run to the next mark; -> 't0', 'tf', 'pr' or an EXTRA name."""
        m = self.m
        m.run()
        st = m.wait_stop(60)
        assert st == "breakpoint", "the frame loop stopped reaching its marks (state %r)" % st
        r = m.regs()
        self.r = r
        flat = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
        if flat == self.tf:
            return "tf"
        if flat == self.t0:
            return "t0"
        if flat in self.extra:
            return self.extra[flat]
        assert flat == self.pr, "stopped at %05X, none of the marks" % flat
        return "pr"


def pic_now(g, ref, st=None):
    """The host picture of the frame the guest holds now (at bz_presented)."""
    st = st or g.state()
    lk, _ = g.look(ref.c)
    return ref.picture(st[1], st[2], lk)


def glass(g, ref):
    """Part 1: the card's own rasterisation of a resting ball's frame (FIRST)."""
    m, tag = g.m, g.tag
    g.key("Enter")
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 20, "play mode runs", guest=60)
    m.pause()
    g.check_base()
    assert g.b("bz_mode") == 0, "Enter started the benchmark, not play"
    assert g.b("bz_crs") == CRS_K["first"], "Enter played course %d, not FIRST" % g.b("bz_crs")
    m.bp_exec(g.a("bz_presented"))
    seen = None
    for _ in range(4):                  # three presents with nothing moving: every refresh since
        m.run()                         # the first of them scanned the one picture
        assert m.wait_stop(60) == "breakpoint", "play mode stopped presenting"
        st = g.state()
        assert seen in (None, st), ("the ball moved with no key held", seen, st)
        seen = st
    m.bp_exec()
    S, R0, c0, px, py = seen
    lk, why = g.look(ref.c)
    assert why is None, "play mode's resting frame: %s" % why
    exp = ref.picture(R0, c0, lk)
    n, box = diff(g.decode(S), exp)
    assert n == 0, "play mode's resting frame: card memory != the course (%d px, box %s)" % (n, box)
    fw, fh, fd = m.fbuf(0)
    wrong = ref.picture(R0, c0 + 1, lk)
    res = glass_cga(fw, fh, fd, exp, wrong) if tag == "cga" else glass_herc(fw, fh, fd, exp, wrong)
    print("%s glass (FIRST, the %s ball at rest at %d,%d): framebuffer %dx%d; %s" % (
        tag, A.MAT_NAMES[lk.mat], px, py, fw, fh, res), flush=True)
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "play mode ends on Esc", guest=60)
    dropped(g, "the glass's play")


def dropped(g, what):
    """Wait for the LAUNCH to return, not only the play: bz_launch's .drop
    writes bz_cseg and bz_bseg 0 last, after both op_drop calls."""
    M.until(g.m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0,
            "the launch to drop its parts after %s" % what, guest=30)


def _px(fd, fw, x, y):
    o = (y * fw + x) * 3
    return fd[o:o + 3]


def glass_cga(fw, fh, fd, exp, wrong):
    """The CGA's rendering: 320 x 200 inks, each at (x0 + sx*x, y0 + sy*y).  Aligned by
    black/not-black on a sample, then every pixel through a palette that must be a bijection."""
    sx, sy = max(1, fw // 320), max(1, fh // 200)
    blk = b"\0\0\0"
    best = None
    for y0 in range(0, fh - 200 * sy + 1):
        for x0 in range(0, fw - 320 * sx + 1):
            bad = 0
            for y in range(0, 200, 9):
                for x in range(0, 320, 5):
                    bad += (_px(fd, fw, x0 + sx * x, y0 + sy * y) == blk) != (exp[y][x] == 0)
            if best is None or bad < best[0]:
                best = (bad, x0, y0)
    _, x0, y0 = best
    cols = [[_px(fd, fw, x0 + sx * x, y0 + sy * y) for x in range(320)] for y in range(200)]
    pal = {}
    for y in range(200):
        for x in range(320):
            pal.setdefault(cols[y][x], set()).add(exp[y][x])
    assert all(len(v) == 1 for v in pal.values()) and len(pal) == len(set().union(*pal.values())), \
        ("the CGA glass is not the expected 320 x 200 picture under one palette", x0, y0,
         {k.hex(): sorted(v) for k, v in pal.items()})
    inv = {next(iter(v)): k for k, v in pal.items()}
    nwrong = sum(1 for y in range(200) for x in range(320) if inv.get(wrong[y][x]) != cols[y][x])
    assert nwrong > 1000, "the glass check cannot fail: the picture one column over matches it too (%d px)" % nwrong
    border = set()
    for y in range(fh):
        for x in range(fw):
            if not (y0 <= y < y0 + 200 * sy and x0 <= x < x0 + 320 * sx):
                border.add(_px(fd, fw, x, y))
    assert len(border) <= 1, ("more than a border colour outside the 320 x 200 field", len(border))
    return ("the 320 x 200 field at (%d,%d), scale %dx%d, equals the picture under palette %s; "
            "one column over differs in %d px (the control)" % (
                x0, y0, sx, sy, {i: inv[i].hex() for i in sorted(inv)}, nwrong))


def glass_herc(fw, fh, fd, exp, wrong):
    """The Hercules' rendering: 720 card pixels a line as 360 pairs, 200 lines, nothing lit
    elsewhere.  Aligned by search (the framebuffer crops and offsets the field)."""
    lit = [y for y in range(fh) if any(fd[(y * fw + x) * 3] for x in range(fw))]
    assert lit, "the Hercules shows nothing"
    top, bot = lit[0], lit[-1]
    assert bot - top + 1 <= 200, ("the Hercules lights %d lines, more than the 200-line field" % (bot - top + 1),
                                  top, bot)

    def pair(x, y, gx0, gy0):
        X = 2 * x + gx0
        o = ((y + gy0) * fw + X) * 3
        return ((fd[o] != 0) << 1) | (fd[o + 3] != 0)

    best = None
    for gy0 in range(max(0, bot - 199), min(fh - 199, top + 1)):
        for gx0 in range(-32, 33):
            bad = 0
            for y in range(0, 200, 9):
                for x in range(20, 340, 5):
                    X = 2 * x + gx0
                    if 0 <= X and X + 1 < fw:
                        bad += pair(x, y, gx0, gy0) != exp[y][x]
            if best is None or bad < best[0]:
                best = (bad, gx0, gy0)
    _, gx0, gy0 = best
    xs = [x for x in range(360) if 0 <= 2 * x + gx0 and 2 * x + gx0 + 1 < fw]
    n = sum(1 for y in range(200) for x in xs if pair(x, y, gx0, gy0) != exp[y][x])
    assert n == 0, "the Hercules glass differs from the picture in %d of %d pairs" % (n, 200 * len(xs))
    assert len(xs) >= 340, ("the framebuffer shows only %d of the 360 pairs" % len(xs), gx0)
    elit = [y for y in range(200) if any(exp[y])]
    assert (top, bot) == (gy0 + elit[0], gy0 + elit[-1]), \
        ("lines lit outside the picture's own lit lines", (top, bot), (gy0 + elit[0], gy0 + elit[-1]))
    nwrong = sum(1 for y in range(200) for x in xs if pair(x, y, gx0, gy0) != wrong[y][x])
    assert nwrong > 1000, "the glass check cannot fail: the picture one column over matches it too"
    return ("the 200-line field is lines %d-%d; lit lines %d-%d are exactly the picture's own (nothing lit "
            "outside it); %d of 360 pairs on the framebuffer (field offset %d card px), all equal to the "
            "picture; one column over differs in %d (the control)" % (
                gy0, gy0 + 199, top, bot, len(xs), gx0, nwrong))


def bench(g, ref, trial=False, mill=False, hvoff=None):
    """Parts 2 and 3: a benchmark (BENCH, or TRIAL or MILL poked into [bz_crs]
    at bz_launch's entry), stopped at bz_tf and bz_presented on chosen frames;
    on TRIAL and MILL also at bz_col, bz_boxw and bz_occ.gate on every frame
    (the order), and on MILL at every bz_wcommit (which way each pose reached
    the glass, SPEC.md 128.12.4.2).  HVOFF: [bz_hvoff] poked at the launch
    (BENCH's leg: 1, wave 2's camera, so it steps the eight directions as
    wave 2's did, SPEC.md 128.12.13.2)."""
    m, tag = g.m, g.tag
    leg = "MILL" if mill else "TRIAL" if trial else "BENCH"
    order = trial or mill
    extra = ("bz_col", "bz_boxw", "bz_occ.gate") if order else ()
    if mill:
        extra += ("bz_wcommit", box_point(g))
    wk = Walker(g, t0=trial, extra=extra)
    if order or hvoff is not None:
        m.bp_exec(g.a("bz_launch"))
        g.key("KeyB")
        assert m.wait_stop(60) == "breakpoint", "B did not reach bz_launch"
        if order:                               # the benchmark on TRIAL / MILL, with its ball
            g.putb("bz_crs", CRS_K["mill" if mill else "trial"])
        if hvoff is not None and "bz_hvoff" in g.sym:
            g.putb("bz_hvoff", hvoff)
        wk.arm()
    else:
        wk.arm()                                # the desktop never runs these: armed before B
        g.key("KeyB")
    done = {d: 0 for d in DIRS}
    checks, tfchecks, fails, full_checked, controls = 0, 0, [], 0, None
    laid_checked, hid_checked, hid_px, glaid = 0, 0, 0, 0
    shd_checked, b3_checked, nbox_seen = 0, 0, {}
    shdin_checked = 0
    order_frames, order_bad, walk_max = 0, 0, 0
    prev = None                             # the last presented frame's (S, R0, c0, px, py) + Look
    want = False
    moving = 0
    nlay0 = 0
    first = True
    ev, ngate = [], 0
    fr = 0
    tpokes, tpoke_next = [], TPOKE_AT
    feat = {k: 0 for k in MILL_FEATS}       # MILL: the frames checked with each feature
    seen = {k: 0 for k in MILL_FEATS}       # ...and the frames that had it at all
    commits, exits, ndef0, tube0 = [], [], 0, 0
    cwrap = False                           # a wheel commit across the ring's end since the last bz_presented
    npwt0 = 0
    fview = None
    wraps, tallest = 0, [0, 0]
    while True:
        k = wk.next()
        if first:
            g.check_base()
            first = False
        if k == "t0":
            # TRIAL's route makes no frame of three boxes (its shadow jumps a
            # line only over OCC cells, where the gate drops a box of its own),
            # so the leg MAKES one: the ball poked airborne across the window
            if trial and not b3_checked and fr >= tpoke_next and len(tpokes) < TPOKE_MAX \
                    and g.w("bz_subs") != g.w("bz_lsubs"):
                tpoke_next = fr + TPOKE_EVERY
                got = tpoke(g, ref.c)
                if got:
                    tpokes.append((fr + 1,) + got)
            continue
        if k == "bz_col":
            r = wk.r
            ev.append(("col", r["ax"], r["bx"], r["cx"]))
            continue
        if k == "bz_boxw":
            si = wk.r["si"]
            x0, y0, w, h = struct.unpack("<HhHH", m.read(g.base + si, 8))
            ev.append(("box", (si - g.sym["bz_boxes"]) // BZ_BOXD, y0, h, x0, w))
            continue
        if k == "bz_occ.gate":
            ngate += 1
            continue
        if k == "bz_wcommit":
            commits.append(commit_kind(g, wk.r))
            cwrap = cwrap or commit_wraps(g)
            continue
        if k == "bz_ts+9":
            bad, tl, ptl = box_check(g, "%s frame %d" % (leg, g.w("bz_frames") + 1))
            fails += bad
            tallest = [max(tallest[0], tl), max(tallest[1], ptl)]
            continue
        if k == "tf":
            if mill:                            # ORACLE CHECK 5: the wheel's commits' map words
                fails += ["%s frame %d at bz_tf: %s" % (leg, g.w("bz_frames") + 1, x) for x in map_check(
                    g, ref.c, [c[1] for c in commits if c[0] in ("ahead", "behind")])]
                fails += wnear_check(g, ref.c, commits, "%s frame %d" % (leg, g.w("bz_frames") + 1))
            if g.b("bz_mode") != 1:
                raise AssertionError("B did not start the benchmark")
            if order and g.b("bz_crs") != CRS_K[leg.lower()]:
                raise AssertionError("the %s leg runs course %d, not %s" % (leg, g.b("bz_crs"), leg))
            full = g.b("bz_full")
            dr, dc = g.s("bz_dr"), g.s("bz_dc")
            dk = ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
            moving += dk != (0, 0)
            lk, why = g.look(ref.c)
            if why:
                fails.append("%s frame %d at bz_tf: %s" % (leg, g.w("bz_frames") + 1, why))
            # does the ORACLE hide part of this frame's ball behind a record? (decided on the host,
            # not off [bz_nlay]: a build whose pass never runs must still have these frames checked)
            _, hid = ref.foot(lk)
            laid = hid > 0
            nlay = g.w("bz_nlay")
            glaid += nlay != nlay0
            nlay0 = nlay
            bxs = g.boxes()
            nbox_seen[len(bxs)] = nbox_seen.get(len(bxs), 0) + 1
            shd_own = bool(g.b("bz_snv")) and any(b[4] == 1 for b in bxs)
            shd_in = bool(g.b("bz_snv")) and bool(bxs) and not shd_own    # the shadow in the ball's box
            three = len(bxs) >= 3
            fview = None
            if mill:                            # what this frame shows of the props (128.12.13.2)
                fview = mill_feats(g, ref, commits, ndef0, dk, npwt0)
                ndef0 = g.w("bz_ndef")
                npwt0 = g.w("bz_npwt") if "bz_npwt" in g.sym else 0
                for f in fview:
                    seen[f] = seen.get(f, 0) + 1
            want = bool(full and not full_checked) or (dk in done and done[dk] < FIRST_EACH) or \
                (laid and laid_checked < LAY_EACH) or (dk != (0, 0) and moving % EVERY == 0) or \
                (trial and shd_own and shd_checked < SHD_EACH) or (trial and three and b3_checked < B3_EACH) or \
                (trial and shd_in and shdin_checked < SHD_EACH) or \
                bool(fview and (any(feat.get(f, 0) < FEAT_EACH for f in fview) or "wnear" in fview))
            if want and prev is not None and not full:
                assert g.w("bz_S") == prev[0][0], "bz_S moved before bz_tf"
                n, box = diff(g.decode(prev[0][0]), ref.picture(prev[0][1], prev[0][2], prev[1],
                                                                g.view(True, prev[2])))
                tfchecks += 1
                if n:
                    fails.append("%s frame %d (%+d,%+d) at bz_tf: the shown window (S %d) is not the last "
                                 "frame's picture, card != oracle: %d px, lines %d-%d, x %d-%d" % (
                                     leg, g.w("bz_frames") + 1, dr, dc, prev[0][0], n, *box))
            wk.dk, wk.full, wk.laid, wk.shd, wk.three, wk.shdin = dk, full, laid, shd_own, three, shd_in
            wk.frame = (full, g.w("bz_wtop"), g.w("bz_H"), dc, bxs)
            wk.feats = fview or ()
            ev = []                             # (the pass ran before bz_tf: ngate is this frame's)
            continue
        # bz_presented
        st = g.state()
        lk, _ = g.look(ref.c)
        view = ref.rule(g.view(), lk)
        fr = g.w("bz_frames")
        # THE RING'S END (SPEC.md 128.13.4.4): a 3- or 4-word box whose whole rows cross 2000h - every such
        # frame checked (the `fastwrap` red writes its crossing row down the unrolled block)
        if not g.b("bz_full") and wrap_boxes(g, st, g.boxes()):
            wraps += 1
            want = True
            wk.feats = tuple(getattr(wk, "feats", ())) + ("wrapbox",)
        if mill:
            fails += ["%s frame %d at bz_presented: %s" % (leg, fr, x) for x in map_check(
                g, ref.c, [c[1] for c in commits if c[0] == "lead"])]
            if any(c[0] == "lead" for c in commits):        # the LEAD is after bz_tf
                wk.feats = tuple(wk.feats) + ("lead",)
                seen["lead"] += 1
                want = want or feat["lead"] < FEAT_EACH
            if lk.tube:
                wk.feats = tuple(wk.feats) + ("transit",)
                seen["transit"] += 1
                want = want or feat["transit"] < FEAT_EACH
            if cwrap:                           # (a commit's rectangle crossing the ring's end: `wrapmask`)
                wk.feats = tuple(wk.feats) + ("wrapcommit",)
                seen["wrapcommit"] += 1
                want = want or feat["wrapcommit"] < FEAT_EACH
            if tube0 and not lk.tube:           # a tube's exit: the ball's footprint in the window
                x4, top, left = lk.px & ~3, st[1] * RL[tag], st[2] * 8
                inside = left <= x4 and x4 + BB.FOOT_W <= left + W[tag] and top <= lk.py and \
                    lk.py + BB.FOOT_H <= top + 200
                exits.append((fr, x4, lk.py, inside))
                if not inside:
                    fails.append("MILL frame %d: the ball came out of tube %d at %d,%d, its footprint not inside "
                                 "the window (R0 %d c0 %d): GLIDE did not keep the ghost in it (SPEC.md 128.12.6.1)"
                                 % (fr, tube0, x4, lk.py, st[1], st[2]))
            tube0 = lk.tube
            commits = []
            cwrap = False
        if order:
            walk_max = max(walk_max, ngate)
            if ngate > 1:
                fails.append("%s frame %d: the occluder pass's walk entered %d times (once a frame at most, "
                             "SPEC.md 128.11.10.2)" % (leg, fr, ngate))
            full, wtop, H, dc, bxs = wk.frame
            if not full:
                order_frames += 1
                why = order_check(ev, H, RL[tag], wtop, g.w("bz_ccol"), dc)
                if why:
                    order_bad += 1
                    if order_bad <= 3:
                        fails.append("%s frame %d: the column and the boxes not in RASTER ORDER (128.11.10.3): "
                                     "%s; events %s" % (leg, fr, why, ev))
            ngate = 0
        if want:
            n, box = diff(g.decode(st[0]), ref.picture(st[1], st[2], lk, view))
            checks += 1
            for f in getattr(wk, "feats", ()) if mill else ():
                feat[f] = feat.get(f, 0) + 1
            if "wrapbox" in getattr(wk, "feats", ()) and not mill:
                feat["wrapbox"] = feat.get("wrapbox", 0) + 1
            if wk.full:
                full_checked += 1
            elif wk.dk in done:
                done[wk.dk] += 1
            if wk.laid:
                laid_checked += 1
                _, hid = ref.foot(lk)
                if hid:
                    hid_checked += 1
                    hid_px += hid
            if trial and wk.shd:
                shd_checked += 1
            if trial and wk.three:
                b3_checked += 1
            if trial and wk.shdin:
                shdin_checked += 1
            if n:
                fails.append("%s frame %d (%+d,%+d)%s%s%s at bz_presented, card != oracle: S %d R0 %d c0 %d ball "
                             "%d,%d (s_b %d z_b %d air %d, sprite %s, shadow %s): %d px, lines %d-%d, x %d-%d" % (
                                 leg, fr, wk.dk[0], wk.dk[1], " FULL" if wk.full else "",
                                 " LAID" if wk.laid else "",
                                 " [%s]" % "+".join(getattr(wk, "feats", ())) if getattr(wk, "feats", ()) else "",
                                 *st, lk.sb, lk.zb, lk.air, lk.spr, lk.spy, n, *box))
            elif controls is None and wk.dk[0] and wk.dk[1] and not wk.full:
                ref.view = view
                try:
                    controls = negative_controls(g, ref, st, lk)
                finally:
                    ref.view = None
            want = False
        wk.feats = () if not mill else wk.feats
        prev = (st, lk, view)
        if fr >= 1199 or len(fails) >= 4:
            break
    m.bp_exec()
    m.run()
    late = None
    if not fails:
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark ends", guest=120)
        assert g.b("bz_res") == 1, "the benchmark left no results"
        late = g.w("bz_rlate")
        if late and not trial:
            fails.append("bz_rlate = %d: a box at window row 0 was not ahead of the beam" % late)
        dropped(g, "the %s benchmark" % leg)
    print("%s %s benchmark to frame %d: %d frames checked at bz_presented and %d at bz_tf (the old window "
          "intact at the latch); the full write %d" % (tag, leg, fr, checks, tfchecks, full_checked), flush=True)
    print("%s %s occluders: %d checked frames where the oracle hides part of the ball behind a record (%d of "
          "them still at bz_presented, %d ball px); frames whose compose laid one ([bz_nlay] moved) %d; records "
          "laid over the run %s, frames the pass ran %s" % (
              tag, leg, laid_checked, hid_checked, hid_px, glaid, g.w("bz_rnlay") if late is not None else "-",
              g.w("bz_rnocf") if late is not None else "-"), flush=True)
    print("%s %s boxes a frame %s; late boxes (bz_rlate) %s; frames with a 3- or 4-word box across the ring's end "
          "(wrapbox) %d, checked %d%s" % (
              tag, leg, ", ".join("%d: %d" % kv for kv in sorted(nbox_seen.items())), late, wraps,
              feat.get("wrapbox", 0),
              "; the tallest box %d lines, the tallest platform box %d (at most %d, %d)" % (
                  tallest[0], tallest[1], BZ_BOXL, PBOX_MAX) if mill else ""), flush=True)
    if mill:
        print("%s MILL: frames checked (of frames seen) with each feature: %s" % (
            tag, ", ".join("%s %d/%d" % (f, feat[f], seen[f]) for f in MILL_FEATS)), flush=True)
        print("%s MILL: tube exits %s; the column and boxes in raster order on %d of %d frames that are not a full "
              "write; the pass's walk entered at most %d times a frame" % (
                  tag, ", ".join("frame %d at %d,%d %s" % (e[0], e[1], e[2], "inside" if e[3] else "OUTSIDE")
                                 for e in exits) or "none", order_frames - order_bad, order_frames, walk_max),
              flush=True)
    if trial:
        print("%s TRIAL: the ball poked across the window for a frame of three boxes on frames %s" % (
            tag, ", ".join("%d (%+d,%+d px)" % t for t in tpokes) or "none"), flush=True)
        print("%s TRIAL: %d checked frames with the shadow in a box of its own, %d with it inside the ball's box, "
              "%d with three boxes or more; the column and boxes in raster order on %d of %d frames that are not a "
              "full write; the pass's walk entered at most %d times a frame" % (
                  tag, shd_checked, shdin_checked, b3_checked, order_frames - order_bad, order_frames, walk_max),
              flush=True)
    else:
        print("%s directions checked (dr,dc): %s" % (
            tag, "  ".join("%+d%+d x%d" % (d[0], d[1], done[d]) for d in DIRS)), flush=True)
    if controls:
        print("%s negative controls: %s" % (tag, controls), flush=True)
    return {"fails": fails, "done": done, "full": full_checked, "controls": controls, "checks": checks,
            "hid": hid_checked, "shd": shd_checked, "b3": b3_checked, "orders": order_frames,
            "shdin": shdin_checked, "feat": feat, "seen": seen, "exits": exits, "wraps": wraps,
            "wrapck": feat.get("wrapbox", 0)}


def order_check(ev, H, rl, wtop, ccol, dc):
    """SPEC.md 128.11.10.3 on one frame's writes, EV in time order: ('col', AX,
    first row, rows) and ('box', index, y0, h, x0, w).  -> None, or what is wrong."""
    cols = [e for e in ev if e[0] == "col"]
    bxs = [e for e in ev if e[0] == "box"]
    ys = [b[2] for b in bxs]
    if ys != sorted(ys):
        return "the boxes written at first lines %s, not in their order" % ys
    if [b[1] for b in bxs] != list(range(len(bxs))):
        return "the boxes written as %s, not 0, 1, ... in turn" % [b[1] for b in bxs]
    if not dc:
        return "a column written on a frame with none entering" if cols else None
    nxt = 0
    for c in cols:
        if c[1] != ccol:
            return "a column call for word column %d, the entering column is %d" % (c[1], ccol)
        if c[2] != nxt:
            return "the column's rows from %d where %d were done (not top first)" % (c[2], nxt)
        nxt += c[3]
    if nxt != H:
        return "the column's rows written %d of %d" % (nxt, H)
    whole = not bxs or any(0 <= ((ccol - b[4]) & 0xFFFF) < b[5] for b in bxs)
    exp, last = [], 0
    for j, b in enumerate(bxs):
        y0w = b[2] - wtop
        if whole:
            e = H
        elif j == 0 and y0w // rl == 0:
            e = (y0w + b[3] - 1) // rl + 1
        else:
            e = y0w // rl
        e = min(max(e, last), H)
        last = e
        exp.append(e)
    got, n = [], 0
    for e in ev:
        if e[0] == "col":
            n += e[3]
        else:
            got.append(n)
    if got != exp:
        return "the column rows written before each box %s, raster order says %s%s" % (
            got, exp, " (a box holds a column cell: the whole column first)" if whole else "")
    return None


def negative_controls(g, ref, st, lk):
    """The same decode must FAIL at S + 1, and after a poked wrong camera."""
    S, R0, c0, px, py = st
    n1, _ = diff(g.decode((S + 1) % 4096), ref.picture(R0, c0, lk))
    assert n1 > 1000, "decode at S + 1 matches too (%d px differ): the check cannot fail" % n1
    out = ["S+1 differs in %d px" % n1]
    for name, v in (("bz_c0", c0 + 1), ("bz_R0", R0 + 1)):
        g.put(name, v)
        try:
            st2 = g.state()
            n2, _ = diff(g.decode(g.w("bz_S")), ref.picture(st2[1], st2[2], lk))
        finally:
            g.put(name, c0 if name == "bz_c0" else R0)
        assert n2 > 1000, "a poked %s still matches (%d px differ): the check cannot fail" % (name, n2)
        out.append("%s+1 poked differs in %d px" % (name, n2))
    assert g.state() == st, "the poked camera was not put back"
    return ", ".join(out)


# ---- MILL (SPEC.md 128.12.13.2): the props on the glass ----------------------
# the frames the MILL leg must check, at least one of each (FEAT_EACH at most):
# a wheel commit AHEAD of the beam and one BEHIND it, a LEAD, the contact group
# a rotor and a post, a deferred contact lane, the platform's box and its
# clipped box, a lane entering in a row and in a column, a transit - and in the
# poked play (mill_play) the slab's layer in a RIDING ball's box and the slab
# OVER a ball under it
MILL_FEATS = ("ahead", "behind", "lead", "crotor", "cpost", "defer", "pbox", "pclip", "enter_row", "enter_col",
              "transit", "wrapcommit")
PLAY_FEATS = ("ride", "pover", "ridebox", "pwait")     # (wave 3b's: the RIDE BOX, the slab's WAITED box)
LOW_FEATS = ("ahead", "behind", "lead")     # the play's LOW scenario's: they count for the MILL leg's
FEAT_EACH = 3
# the LEAD on the Hercules: a wheel reckoned from a wait that SAW the rise
# reaches every window line there, so a lead follows only a wait that found
# the sync already high (SPEC.md 128.12.5.3) - reported on that card, required
# on the CGA
# and a lane entering in a COLUMN on the Hercules: its 45-word window holds every MILL lane's columns
# whatever c0 (cmax 19, the lanes in columns 21 - 35), so no column ever brings one in there (the final
# pass) - reported on that card
# and a wheel commit whose columns cross the ring's end (`wrapcommit`, the pass's row-at-a-time path,
# SPEC.md 128.13.5.1): card offsets are absolute, so it is a property of the lane - MILL's post 4 crosses
# on the Hercules (card rows 88 - 93 at word 23), no MILL lane on the CGA - required on the Hercules,
# reported on the CGA
FEAT_OPTIONAL = {"herc": ("lead", "enter_col"), "cga": ("wrapcommit",)}

# THE LOW SCENARIO (the final pass): MILL's route keeps its lanes high in the window and its frames
# heavy, so a wheel commit AHEAD of the beam (and on the CGA the LEAD) never happens on the benchmark.
# A POST is put at window lines LOW_F - LOW_F + 23 by a centred full write round a ball HELD above it
# (poked to the one point at every bz_t0), and after LOW_SETTLE frames, every LOW_CYCLE frames its lit
# frames are poked (bz_lhold 1: display state, physics untouched): it LIGHTS as the frame's must-draw
# lane, and goes dark the frame after, a WHEEL candidate low in the window.  That frame starts late (the
# lit box's write): on the CGA the beam keeps the lane from the wait and the wheel marks it for the
# frame's LEAD; on the Hercules the wait reaches it BEHIND the beam (SPEC.md 128.12.5.3).  Every other
# cycle that frame is made late with bz_hold (LOW_HOLD x 256 PIT counts) past the wheel's room: it skips,
# and the next, LIGHT frame commits the lane AHEAD of the beam (the final pass's traces)
LOW_F = 160
LOW_SETTLE = 10                     # the full write and a few held frames before the cycles
LOW_CYCLE = 6
LOW_CYCLES = 6
LOW_HOLD = {"cga": 16, "herc": 24}  # x 256 PIT counts: the held dark frame past the wheel's room (skipped)


def low_plan(g, crs):
    """-> (the post's lane, R0, c0, the ball's contact point) for THE LOW SCENARIO, or None"""
    tag = g.tag
    lsh, rl = (1 if tag == "cga" else 2), RL[tag]
    Wc, rmax, cmax = g.w("bz_W"), g.w("bz_rmax"), g.w("bz_cmax")
    grid = BB.Grid(crs.cga)
    rects = lane_rects(crs)
    # a post whose columns cross the ring's end first (the Hercules' post 4, MILL's only one on either
    # card): every LOW commit of it is then a `wrapcommit` (bz_wprect's row-at-a-time path, the
    # `wrapmask` red's) - the MILL benchmark's own commits of it are one a run or none (the final pass)
    herc = tag == "herc"

    def crosses(i):
        q = lane_cells(rects[i], lsh)
        return BB.ring_cross(q[0], q[1], q[2], q[3], herc)
    for i in sorted(rects, key=lambda j: (not crosses(j), j)):
        if crs.part["props"][i]["kind"] != BB.PK_BUMPER:
            continue
        col, brow, w = rects[i][:3]
        top = 8 * brow - LOW_F
        top -= top % rl
        R0 = top >> lsh
        if not 0 <= R0 <= rmax:
            continue
        for c0 in sorted(range(1, cmax + 1), key=lambda c: abs(c - (col - Wc // 2 + 6))):
            if not (c0 + 1 <= col and col + w <= c0 + Wc - 1):
                continue
            left, pt = 8 * c0, None
            for dy in range(rl):
                for dx in range(8):
                    pt = pt or probe_ground(crs, left + 4 * Wc - 8 + dx, top + 92 + dy, grid, 1, clear=16,
                                            flags=BB.FL_OCC | BB.FL_OCCG)
            if pt:
                return i, R0, c0, pt
    return None


def low_poke(g, plan, k):
    """THE LOW SCENARIO's pokes at its K-th bz_t0 (0 the first): -> 'lit', 'dark', 'held' or None"""
    lane, _, _, pt = plan
    poke_ball(g, pt[0], pt[1], pt[2], 0, 0, 0, air=1, same_cell=k > 0)   # HELD there every frame: MILL's
    if k == 0:                                                           # ground near the green slopes, and a
        g.putb("bz_first", 1)                                            # rolling ball scrolls the window
        return None
    if k < LOW_SETTLE:
        return None
    j, r = divmod(k - LOW_SETTLE, LOW_CYCLE)
    if j >= LOW_CYCLES:
        return None
    if r == 0:
        g.m.write(g.a("bz_lhold") + lane, bytes([1]))
        return "lit"
    if r == 1:
        if j % 2:
            g.putb("bz_hold", LOW_HOLD[g.tag])
            return "held"
        return "dark"
    return None


LOW_FRAMES = LOW_SETTLE + LOW_CYCLE * LOW_CYCLES + 2


def commit_kind(g, r):
    """at bz_wcommit's entry (REGS R): which way this commit reaches the glass,
    from where it RETURNS - pass 1 of bz_wheel (AHEAD of the beam), pass 2
    (BEHIND it) or bz_lead (the LEAD) - and its lane (AL).  -> (kind, lane)"""
    ret = struct.unpack("<H", g.m.read(((r["ss"] << 4) + r["sp"]) & 0xFFFFF, 2))[0]
    s = g.sym
    if s["bz_wheel"] < ret <= s["bz_wheel.p2"]:
        kind = "ahead"
    elif s["bz_wheel.p2"] < ret <= s["bz_wheel.out"]:
        kind = "behind"
    elif s["bz_lead"] < ret <= s["bz_lead.no"]:
        kind = "lead"
    else:
        kind = "other@%04X" % ret
    return kind, r["ax"] & 0xFF


def commit_wraps(g):
    """at bz_wcommit's entry: does a column of the loaded commit's rectangles
    (bz_lra, bz_lrb: card rows r0 r1, words x0 x1) cross the ring's end -
    bz_wprect's `.slow` path (SPEC.md 128.13.5.1), bbcourse.ring_cross's test"""
    herc = g.tag == "herc"
    for name in ("bz_lra", "bz_lrb"):
        r0, r1, x0, x1 = struct.unpack("<4H", g.m.read(g.a(name), 8))
        if r1 > r0 and x1 > x0 and BB.ring_cross(r0, r1, x0, x1, herc):
            return True
    return False


def lane_cells(rect, lsh):
    """a lane's (first card row, end card row, first word column, end column)"""
    col, brow, w, h = rect[:4]
    return (8 * brow) >> lsh, (8 * (brow + h)) >> lsh, col, col + w


def entering(g):
    """this frame's entering strips, at bz_tf (the new window in bz_R0n, bz_c0n):
    -> ((rows r0, r1), (the column, or None)) - rows [R0n + H - dr, R0n + H)
    moving down, [R0n, R0n - dr) up; the column the new window's right or left"""
    dr, dc, R0n, c0n, H, Wc = (g.s("bz_dr"), g.s("bz_dc"), g.w("bz_R0n"), g.w("bz_c0n"), g.w("bz_H"),
                               g.w("bz_W"))
    rows = (R0n + H - dr, R0n + H) if dr > 0 else (R0n, R0n - dr) if dr < 0 else None
    col = (c0n + Wc - 1) if dc > 0 else c0n if dc < 0 else None
    return rows, col, (R0n, c0n, H, Wc)


def wnear_lanes(g, crs, commits):
    """at bz_tf: the lanes a WHEEL commit of this frame (ahead of the beam or
    behind it - not the LEAD's, after the flip) wrote over the ball's or the
    shadow's OLD footprint where it is in the shown window and the new one -
    the ball still on the glass there until its box restores it.  Never one
    in a right build: such a lane is a contact candidate, and the wheel's box
    filter drops every lane meeting a box (SPEC.md 128.12.4.2, 128.12.13.2).
    A full write's frame has no old footprint on the glass to erase."""
    if not commits or not g.b("bz_oldv") or g.b("bz_full"):
        return []
    olds = [struct.unpack("<4H", g.m.read(g.a("bz_ofx0"), 8))]
    if g.b("bz_sov"):
        olds.append(struct.unpack("<4H", g.m.read(g.a("bz_sox0"), 8)))
    lsh = 1 if g.tag == "cga" else 2
    H, Wc = g.w("bz_H"), g.w("bz_W")
    wins = [(g.w(r), g.w(c)) for r, c in (("bz_R0", "bz_c0"), ("bz_R0n", "bz_c0n"))]
    rects = lane_rects(crs)
    out = []
    for kind, lane in commits:
        if kind not in ("ahead", "behind") or lane not in rects or lane in out:
            continue
        col, brow, w, h = rects[lane][:4]
        for x0, x1, y0, y1 in olds:
            a0, a1 = max(col, x0), min(col + w - 1, x1)           # words
            l0, l1 = max(8 * brow, y0), min(8 * (brow + h) - 1, y1)   # lines
            for R0, c0 in wins:                                     # ...inside both windows
                a0, a1 = max(a0, c0), min(a1, c0 + Wc - 1)
                l0, l1 = max(l0, R0 << lsh), min(l1, ((R0 + H) << lsh) - 1)
            if a0 <= a1 and l0 <= l1:
                out.append(lane)
                break
    return out


def wnear_check(g, crs, commits, where):
    """THE RULE ITSELF at bz_tf (wnear_lanes): -> failures"""
    return ["%s at bz_tf: the wheel committed lane %d over the ball's or the shadow's OLD footprint, still on "
            "the glass (a contact candidate is never the wheel's: SPEC.md 128.12.4.2)" % (where, lane)
            for lane in wnear_lanes(g, crs, commits)]


def mill_feats(g, ref, commits, ndef0, dk, npwt0=0):
    """at bz_tf: the features of SPEC.md 128.12.13.2's MILL leg this frame has
    (a DEFERRED contact lane: bz_ndef moved by more than the slab's waits, which
    it counts too since wave 3b, 128.13.4.3)"""
    out = set(c[0] for c in commits if c[0] in ("ahead", "behind"))
    ct = g.b("bz_ctype")
    if ct == 1:
        kind = ref.c.part["props"][g.b("bz_cln")]["kind"]
        out.add("crotor" if kind == BB.PK_WINDMILL else "cpost")
    elif ct == 2:
        out.add("pbox")
    elif ct == 3:
        out.add("pclip")
    if (g.w("bz_ndef") - ndef0) & 0xFFFF > ((g.w("bz_npwt") - npwt0) & 0xFFFF if "bz_npwt" in g.sym else 0):
        out.add("defer")
    # a wheel commit meeting the ball's or the shadow's OLD footprint, still on the
    # glass at bz_tf: never one in a right build (such a lane is a contact candidate,
    # SPEC.md 128.12.4.2), and the frame the `contact` red erases the ball on - so
    # every such frame is checked, not FEAT_EACH of them (and wnear_check FAILS it)
    if wnear_lanes(g, ref.c, commits):
        out.add("wnear")
    if dk != (0, 0) and not g.b("bz_full"):
        rows, col, (R0n, c0n, H, Wc) = entering(g)
        lsh = 1 if g.tag == "cga" else 2
        for rect in lane_rects(ref.c).values():
            q0, q1, a0, a1 = lane_cells(rect, lsh)
            if rows and q0 < rows[1] and rows[0] < q1 and a0 < c0n + Wc and c0n < a1:
                out.add("enter_row")
            if col is not None and a0 <= col < a1 and q0 < R0n + H and R0n < q1:
                out.add("enter_col")
    return tuple(sorted(out))


def plat_rec(crs):
    return next((r for r in crs.part["props"] if r["kind"] == BB.PK_PLATFORM), None)


# ---- wave 3b (SPEC.md 128.13.12): the box sizes, the ring's end, the map's words --------
BZ_BOXW, BZ_BOXL, PBOX_MAX = 4, 32, 30   # bzvideo.inc; the platform's box: 18 + 2 x 6 lines (128.13.4.3)
HDR_MAP, HDR_ROWB = 32, 24               # bonanza.asm BZC_MAP, BZC_ROWB


def box_point(g):
    """bz_ts + 9: the instruction after `call bz_mkboxes` - the frame's boxes
    laid out, none composed (the frame's first bz_boxc is the next call)"""
    a = g.a("bz_ts")
    code = g.m.read(a, 12)
    tgt = (g.sym["bz_ts"] + 9 + struct.unpack_from("<h", code, 7)[0]) & 0xFFFF
    assert code[0] == 0xBB and code[3] == 0xE8 and code[6] == 0xE8 and tgt == g.sym["bz_mkboxes"], \
        "bz_ts is not MOV BX, CALL bz_mark, CALL bz_mkboxes: the box check's point moved (%s)" % code.hex()
    return ("bz_ts", 9)


def box_check(g, where):
    """at box_point: every box at most BZ_BOXW words x BZ_BOXL lines, and every
    PLATFORM box (group 2 at the slab's first word, the frame's contact the
    platform's or the lift's rect beside a post) at most PBOX_MAX lines (SPEC.md
    128.13.12).  A box past BZ_BOXL would overrun its buffer, so a failing frame
    has its boxes TAKEN AWAY ([bz_nbox] 0) before any compose: the harness keeps
    the guest's memory whole so the row can end and report.  -> (failures, the
    tallest box, the tallest platform box)"""
    bxs = g.boxes()
    plat = g.sym.get("bz_pidx") is not None and g.b("bz_pidx") != 0xFF
    pw = (g.w("bz_pox") >> 3) if plat else None
    ct, c2 = g.b("bz_ctype"), g.w("bz_cgr2")
    bad, tall, ptall = [], 0, 0
    for (x0, y0, w, h, grp) in bxs:
        tall = max(tall, h)
        isp = plat and grp == 2 and x0 == pw and (ct == 2 or c2)
        if isp:
            ptall = max(ptall, h)
        if w > BZ_BOXW or h > BZ_BOXL or (isp and h > PBOX_MAX):
            bad.append("%s: the box-size check at the frame's first bz_boxc: a %sbox of %d words x %d lines at line "
                       "%d (at most %d x %d, a platform box %d lines: SPEC.md 128.13.12)" % (
                           where, "PLATFORM " if isp else "", w, h, y0, BZ_BOXW, BZ_BOXL, PBOX_MAX))
    # the platform's rect itself, before bz_addbox clips it: bz_crect when the contact group is the slab's
    # box (bz_ctype 2), bz_crect2 when it is the lift's rect beside a lighting post (bz_pflag bit 2) - a
    # box clipped at the window's left edge, or merged into the post's rect, is not found by its x0 above
    for name, on in (("bz_crect", ct == 2), ("bz_crect2", plat and bool(g.b("bz_pflag") & 4))):
        if not on:
            continue
        _, _, ya, yb = struct.unpack("<4h", g.m.read(g.a(name), 8))
        ph = yb - ya + 1
        ptall = max(ptall, ph)
        if ph > PBOX_MAX:
            bad.append("%s: the box-size check at the frame's first bz_boxc: the PLATFORM's rect %s is %d lines "
                       "(lines %d - %d), past %d (SPEC.md 128.13.4.3: one wait, never two running)" % (
                           where, name, ph, ya, yb, PBOX_MAX))
    if bad:
        g.put("bz_nbox", 0)
    return bad, tall, ptall


def wrap_boxes(g, st, bxs):
    """the frame's boxes the WHOLE-ROW path writes across the ring's end
    (SPEC.md 128.13.4.4): no band (bz_boxw's own gate), 3 or 4 words, a whole card row other than the path's
    first that crosses 2000h (its offset + 2w past it) - the row bz_bwrows's
    tail sends to bz_wseg.  ST: (S, R0, c0, ...) of the window the boxes were
    written to.  -> [(x0, y0, w, h, the crossing row's offset)]"""
    tag = g.tag
    rl, rb = RL[tag], RB[tag]
    S, R0, c0 = st[:3]
    top = R0 * rl
    out = []
    raw = g.m.read(g.a("bz_boxes"), 4 * BZ_BOXD)
    for i, (x0, y0, w, h, grp) in enumerate(bxs):
        if w not in (3, 4) or x0 < c0:
            continue
        if struct.unpack_from("<H", raw, i * BZ_BOXD + 10)[0]:
            continue                # a BANDED box: bz_boxw's per-line loop, never bz_bwrows (fastwrap's)
        first = (y0 - top + rl - 1) // rl              # the first whole card row (its first line in bank 0)
        last = (y0 + h - top) // rl - 1                # the last whole one
        for r in range(first + 1, last + 1):
            dx = (r * rb + 2 * S + 2 * (x0 - c0)) & 0x1FFF
            if dx + 2 * w > 0x2000:
                out.append((x0, y0, w, h, dx))
                break
    return out


def map_check(g, crs, lanes):
    """ORACLE CHECK 5 (SPEC.md 128.13.11): each of LANES' map words in the course
    part (bz_cseg, BZC_MAP, a row BZC_ROWB) are its DRAWN pose's ([bz_ldrw]),
    read after its commit - a store that never reached the map (the pass's,
    `mapskip`) is seen here.  -> [what is wrong]"""
    if "bz_ldrw" not in g.sym or not lanes:
        return []
    cs = g.w("bz_cseg") << 4
    rowb = struct.unpack("<H", g.m.read(cs + HDR_ROWB, 2))[0]
    rects = lane_rects(crs)
    recs = {r["i"]: r for r in crs.part["props"]}
    drawn = g.lanes()
    out = []
    for i in sorted(set(lanes)):
        if i not in rects or i not in drawn:
            continue
        col, brow, w, h, poses = rects[i]
        q = drawn[i]
        if q >= poses:
            continue
        sz = 2 * w * h
        pm = g.m.read(cs + recs[i]["lane"]["off"] + q * sz, sz)
        mp = b"".join(g.m.read(cs + HDR_MAP + (brow + r) * rowb + 2 * col, 2 * w) for r in range(h))
        if pm != mp:
            bad = [k // 2 for k in range(0, sz, 2) if pm[k:k + 2] != mp[k:k + 2]]
            out.append("oracle check 5: lane %d's map words are not its DRAWN pose %d's (%d of %d words differ, "
                       "the first at block row %d word %d): a commit's map store never reached the course part"
                       % (i, q, len(bad), w * h, brow + bad[0] // w, col + bad[0] % w))
    return out


def slab_ball(g, P, n, z_off, air, onp):
    """the ball poked at the LIFT's shaft's centre with the slab as it stands
    at step N: on it (z_off 0, grounded, carried: onp) or under it (z_off < 0,
    airborne in the shaft, not carried) - bz_onp and bz_ps's bit 2 with it"""
    gx = (16 * P["at"][0] + 8) << 8
    gy = (16 * P["at"][1] + 8) << 8
    gz = (P["hP"] << 8) + BB.plat_pos(P, n & 0xFFFF) + (z_off << 8)
    poke_ball(g, gx, gy, gz, 0, 0, 0, air=air, ztop=gz >> 8)
    g.putb("bz_onp", P["i"] + 1 if onp else 0)
    ps = g.b("bz_ps")
    g.putb("bz_ps", (ps | 4) if onp else (ps & ~4))


RIDE_FRAMES = 150                   # a rise and its dock (P 256: 64 steps moving, 64 docked)
OVER_FRAMES = 12

# THE DEFER SCENE (SPEC.md 128.13.7 item 1): a post of the cluster made REALLY drawn lit and then due while
# the ball's every frame is two boxes - so its contact candidacy waits (bz_ndef) and its cells outside the
# boxes stay lit on the glass, as its map and bz_ldrw say.  At its K-th bz_t0 (TRICKLE, the window centred
# on DF_Q1 by a full write): held at Q1 to DF_KICK, the KICK poked there (it lights as the must-draw), then
# from DF_KICK + 1 its lit frames poked to 0 (DUE) and the ball alternately at Q2, Q1 for DF_ALT frames -
# under BZ_WPRF (5) - then held at Q1 to DF_END (one box: it goes dark as the contact group)
DF_KICK, DF_ALT, DF_END = 5, 4, 12
# THE PWAIT SCENE (SPEC.md 128.13.12): the ball held airborne alternately at two points 48 px apart (every
# frame's ball group two boxes: a CROWDED frame, 128.13.4.3 (a)) while the lift RISES from its low dock,
# the window's bottom edge through the slab (TRICKLE), for PW_FRAMES frames; on a frame after one that did
# not wait, the ball poked across the band's FOOT instead (the camera steps down a row, the entering row
# meeting the slab's drawn footprint on a waited frame: bz_ctype 3), PW_TRIES times at most; then held at one
# point PW_END frames (one box: the slab's is drawn - 18 + 2 x 6 lines at most)
PW_FRAMES = {"cga": 24, "herc": 21}
PW_END, PW_TRIES, PW_STEPS = 3, 4, 20
PW_DX = 24                          # px either side of the window's centre


def defer_plan(g, crs):
    """-> (the post, Q1, Q2) for THE DEFER SCENE, or None: Q1 a point whose
    footprint meets the post's lane rectangle at a CORNER (some of its cells
    outside it) with the ball's centre clear of every post by 16 gu and over a
    floor by 16 px (no kick), Q2 the same 48 px across (its footprint clear of
    every lane)"""
    grid = BB.Grid(crs.cga)
    rects = lane_rects(crs)
    recs = {r["i"]: r for r in crs.part["props"]}
    posts = [i for i in sorted(rects) if recs[i]["kind"] == BB.PK_BUMPER]

    def clear(gp):
        return all((gp[0] / 256.0 - recs[j]["cx"]) ** 2 + (gp[1] / 256.0 - recs[j]["cy"]) ** 2 >= 16 ** 2
                   for j in posts)

    def meets(px, py, i):
        col, brow, w, h = rects[i][:4]
        return px >> 3 <= col + w - 1 and col <= (px + BB.FOOT_W - 1) >> 3 and py <= 8 * (brow + h) - 1 and \
            8 * brow <= py + BB.FOOT_H - 1
    for i in posts:
        col, brow, w, h = rects[i][:4]
        for dy in range(-BB.FOOT_H + 4, 2, 2):          # its top-left corner: the footprint's foot over the
            for dx in range(-BB.FOOT_W + 4, 2, 2):      # lane's first lines and first word only
                px, py = 8 * col + dx, 8 * brow + dy
                if (px + BB.FOOT_W - 1) >> 3 != col or not meets(px, py, i):
                    continue
                q1 = probe_ground(crs, px, py, grid, 1, clear=16, flags=BB.FL_OCC | BB.FL_OCCG)
                if not q1 or not clear(q1):
                    continue
                for ox in (-48, 48, -56, 56):
                    if any(meets(px + ox, py, j) for j in rects):
                        continue
                    q2 = probe_ground(crs, px + ox, py, grid, 1, clear=16, flags=BB.FL_OCC | BB.FL_OCCG)
                    if q2 and clear(q2):
                        return i, q1, q2
    return None


def defer_poke(g, plan, k):
    """THE DEFER SCENE's pokes at its K-th bz_t0: -> 'kick', 'due', 'alt' or None"""
    lane, q1, q2 = plan
    if DF_KICK < k <= DF_KICK + DF_ALT:
        q = q2 if (k - DF_KICK) % 2 else q1
        poke_ball(g, q[0], q[1], q[2], 0, 0, 0, air=1)
    else:
        poke_ball(g, q1[0], q1[1], q1[2], 0, 0, 0, air=1, same_cell=k > 0)
    if k == 0:
        g.putb("bz_cmode", 1)                   # TRICKLE: the window holds while the ball moves in the band
        g.putb("bz_first", 1)                   # the next frame: a full write centred on Q1
        return None
    if k == DF_KICK:                            # the KICK (bz_pkick + 1, 128.13.14 item 10): drawn lit
        a = g.a("bz_pkick") + 2 * lane
        g.m.write(a, struct.pack("<H", (struct.unpack("<H", g.m.read(a, 2))[0] + 1) & 0xFFFF))
        return "kick"
    if k == DF_KICK + 1:                        # true dark, drawn lit: DUE, on a two-box frame
        g.m.write(g.a("bz_lhold") + lane, b"\0")
        return "due"
    return "alt" if DF_KICK < k <= DF_KICK + DF_ALT else None


def pwait_plan(g, crs, n_now):
    """-> (n0, R0, c0, the full write's point, P1, P2) for THE PWAIT SCENE, or
    None: n0 the step the lift next leaves its low dock (at least 12 on), R0 the
    window whose bottom edge is 8 lines above the slab's foot at its dock, c0
    the slab's columns centred; P1 and P2 PW_DX px either side of the centre,
    airborne over floors (the shadow's box apart)"""
    tag = g.tag
    P = plat_rec(crs)
    if P is None:
        return None
    lsh, rl = (1 if tag == "cga" else 2), RL[tag]
    Wc, H, rmax, cmax = g.w("bz_W"), g.w("bz_H"), g.w("bz_rmax"), g.w("bz_cmax")
    x0g, y0g = crs.part["grid"]["x0"], crs.part["grid"]["y0"]
    n0 = next(n for n in range(n_now + 12, n_now + 12 + 2 * (P["mask"] + 1))
              if BB.plat_pos(P, n) == BB.plat_pos(P, n - 1) and BB.plat_pos(P, n + 1) > BB.plat_pos(P, n))
    x_l, y_t = BB.slab_xy(P, BB.plat_pos(P, n0) >> 8, x0g, y0g)
    R0 = ((y_t + BB.PL_H - 8) >> lsh) - H
    c0 = max(0, min((x_l >> 3) + 2 - Wc // 2, cmax))
    if not (0 <= R0 <= rmax and c0 <= x_l >> 3 and (x_l >> 3) + 4 <= c0 + Wc):
        return None
    grid = BB.Grid(crs.cga)
    top, left = R0 << lsh, 8 * c0
    cen = p1 = p2 = None
    for dy in range(rl):
        for dx in range(8):
            cen = cen or probe_ground(crs, left + 4 * Wc - 8 + dx, top + 92 + dy, grid, 1, clear=16,
                                      flags=BB.FL_OCC | BB.FL_OCCG)
    for dy in range(0, 8, 2):
        p1 = p1 or probe_ground(crs, left + 4 * Wc - 8 - PW_DX, top + 92 + dy, grid, 1, clear=16,
                                flags=BB.FL_OCC | BB.FL_OCCG)
        p2 = p2 or probe_ground(crs, left + 4 * Wc - 8 + PW_DX, top + 92 + dy, grid, 1, clear=16,
                                flags=BB.FL_OCC | BB.FL_OCCG)
    if not (cen and p1 and p2):
        return None
    return n0, R0, c0, cen, p1, p2


def lift_steps(P, n0, n1):
    """the steps in [n0, n1) on which the lift's rise changes"""
    return sum(1 for n in range(n0, n1) if BB.plat_pos(P, n + 1) != BB.plat_pos(P, n))


def mill_play(g, ref):
    """the MILL leg's POKED play (SPEC.md 128.12.13.2, 128.13.12): Enter on MILL
    ([bz_crs] poked at bz_launch), the ball poked onto the platform's slab at
    the first bz_t0 (the frame's centred full write puts the window round it)
    and left to RIDE with no key held - every riding frame whose ball box meets
    the slab checked (its layer in the ball's box), and every frame the ride
    merges the slab's box with the ball's (THE RIDE BOX: bz_ctype 2, no rect of
    its own) - then poked UNDER the slab, in its shaft, at each frame's bz_t0
    for OVER_FRAMES frames: the slab drawn OVER it ([bz_pov] 1), checked; then
    THE LOW SCENARIO; then THE DEFER SCENE and THE PWAIT SCENE (above).  The
    card equals the oracle at bz_tf and bz_presented on every checked frame,
    and every frame's boxes pass the box-size check at its first bz_boxc.
    -> (failures, {feature: frames checked})"""
    m, tag, crs = g.m, g.tag, ref.c
    P = plat_rec(crs)
    fails, cnt = [], {f: 0 for f in PLAY_FEATS + ("wrapcommit",)}
    if P is None:
        return ["MILL has no platform"], cnt
    m.bp_exec(g.a("bz_launch"))
    g.key("Enter")
    assert m.wait_stop(60) == "breakpoint", "Enter did not reach bz_launch"
    g.putb("bz_crs", CRS_K["mill"])
    g.putb("bz_hvoff", 0)
    wk = Walker(g, t0=True, extra=("bz_wcommit", box_point(g)))
    wk.arm()
    frames, prev, phase = 0, None, "ride"
    plan, commits = None, []
    for f in LOW_FEATS:
        cnt[f] = 0
    # the scenes' state: the phase's own bz_t0 count, its plans and what each saw
    sc = {"k": 0, "df": None, "pw": None, "pwj": 0, "pwend": 0, "pwn0": None, "pwn1": None, "tries": 0,
          "strip": 0, "waits": 0, "dframes": 0, "tall": 0, "ptall": 0, "rideb": 0, "tfwait": False,
          "wfr": set()}
    low_end = RIDE_FRAMES + OVER_FRAMES + LOW_FRAMES
    df_end = low_end + DF_END + 1
    nmax = df_end + 600                         # (the pwait scene waits for the lift's next rise: at most a
    tag_pw = PW_FRAMES[tag]                     # period, 256 steps)
    while frames < nmax and phase != "done":
        k = wk.next()
        if k == "bz_wcommit":
            commits.append(commit_kind(g, wk.r))
            sc["cwrap"] = sc.get("cwrap") or commit_wraps(g)
            continue
        if k == "bz_ts+9":
            bad, tl, ptl = box_check(g, "MILL play frame %d (%s)" % (frames + 1, phase))
            fails += bad
            sc["tall"], sc["ptall"] = max(sc["tall"], tl), max(sc["ptall"], ptl)
            if bad:
                phase = "done"                  # (the boxes taken away: end the play here)
            continue
        if k == "t0":
            n = g.d("bz_nstep")
            if frames == 0:
                slab_ball(g, P, n, 0, 0, True)
            elif phase == "ringend":
                a_, b_ = sc["re"]
                q = a_ if sc["k"] % 2 == 0 else b_
                poke_ball(g, q[0], q[1], q[2], 0, 0, 0, air=1, same_cell=sc["k"] > 0)
                if sc["k"] == 0:
                    g.putb("bz_first", 1)           # the next frame: a full write centred on it
                sc["k"] += 1
                if sc["k"] > RE_HOLD + 1:
                    phase, sc["k"] = "entercol", 0
                    sc["ec"] = entercol_plan(g, crs)
                    if sc["ec"] is None:
                        if tag == "cga":
                            fails.append("MILL play: no window puts a rotor's or a post's columns just outside its "
                                         "left or right edge with its rows inside (the entering-column scene)")
                        phase = "done"
            elif phase == "entercol":
                entercol_poke(g, sc["ec"], sc["k"])
                sc["k"] += 1
                if sc["k"] > EC_END:
                    phase = "done"
            elif frames >= df_end:
                if phase != "pwait":
                    phase, sc["k"] = "pwait", 0
                    sc["pw"] = pwait_plan(g, crs, n & 0xFFFF)
                    sc["crs"] = crs
                    if getattr(crs, "_grid", None) is None:
                        crs._grid = BB.Grid(crs.cga)
                    if sc["pw"] is None:
                        fails.append("MILL play: no window puts the lift's slab across its bottom edge with the ball "
                                     "held in the band (the PWAIT scene)")
                        phase = "done"
                        continue
                pwait_step(g, sc, n, tag_pw)
                if sc["pwend"] > PW_END:
                    phase, sc["k"] = "ringend", 0
                    sc["re"] = ringend_plan(g, crs)
                    if sc["re"] is None:
                        fails.append("MILL play: no point of MILL puts a 3- or 4-word footprint's whole row "
                                     "across the ring's end (the ring's-end scene)")
                        phase = "done"
                    continue
                sc["k"] += 1
            elif frames >= low_end:
                if phase != "defer":
                    phase, sc["k"] = "defer", 0
                    sc["df"] = defer_plan(g, crs)
                    if sc["df"] is None:
                        fails.append("MILL play: no point meets a post's rectangle at a corner clear of it (the "
                                     "DEFER scene)")
                        phase = "done"
                        continue
                defer_poke(g, sc["df"], sc["k"])
                sc["kcur"] = sc["k"]
                sc["k"] += 1
            elif frames >= RIDE_FRAMES + OVER_FRAMES:
                if phase != "low":
                    phase = "low"
                    plan = low_plan(g, crs)
                    if plan is None:
                        fails.append("MILL play: no post the LOW scenario can put low in a centred window")
                        break
                low_poke(g, plan, frames - RIDE_FRAMES - OVER_FRAMES)
            elif frames >= RIDE_FRAMES:
                phase = "over"
                slab_ball(g, P, n + 1, -12, 1, False)
            continue
        if k == "tf":
            sc["tfwait"] = phase == "pwait" and "bz_pyld" in g.sym and bool(g.b("bz_pyld"))
            # THE RULE ITSELF (SPEC.md 128.13.4.3): the slab's box waits a frame, never two running -
            # bz_pyld (cleared at every bz_props) set on this frame and the last; the box-size check
            # sees the same fault only when the lift rose far enough during the scene (`pwait2`)
            if sc["tfwait"] and sc.get("tfw_prev"):
                fails.append("MILL play frame %d (pwait) at bz_tf: the slab's box waited two frames running "
                             "(bz_pyld on this frame and the last; SPEC.md 128.13.4.3)" % (frames + 1))
            sc["tfw_prev"] = sc["tfwait"]
            if phase == "entercol" and not g.b("bz_full"):
                _rows, col, (R0n, _c0n, H_, _Wc) = entering(g)
                q0, q1, a0, a1 = lane_cells(lane_rects(crs)[sc["ec"][0]], 1 if tag == "cga" else 2)
                sc["ecol"] = col is not None and a0 <= col < a1 and q0 < R0n + H_ and R0n < q1
            sc["tfct"] = g.b("bz_ctype")
            sc["tfcgr"] = g.w("bz_cgr")
            sc["tfnd"] = g.w("bz_ndef")
            sc["tfbx"] = g.boxes()
            fails += ["MILL play frame %d (%s) at bz_tf: %s" % (frames + 1, phase, x) for x in map_check(
                g, crs, [c[1] for c in commits if c[0] in ("ahead", "behind")])]
            fails += wnear_check(g, crs, commits, "MILL play frame %d (%s)" % (frames + 1, phase))
            if prev is not None and not g.b("bz_full") and (phase in ("over", "low", "defer", "pwait", "ringend", "entercol") or
                                                            frames % 10 == 0 or sc.get("ridebox_last")):
                n_, box = diff(g.decode(prev[0][0]), ref.picture(prev[0][1], prev[0][2], prev[1],
                                                                 g.view(True, prev[2])))
                if n_:
                    fails.append("MILL play frame %d (%s) at bz_tf: the shown window is not the last frame's "
                                 "picture, card != oracle: %d px, lines %d-%d, x %d-%d" % (frames + 1, phase, n_, *box))
            continue
        frames += 1
        st = g.state()
        lk, why = g.look(crs)
        view = ref.rule(g.view(), lk)
        if why:
            fails.append("MILL play frame %d: %s" % (frames, why))
        if view[1] and view[1][2] != (g.b("bz_pov") == 1):
            fails.append("MILL play frame %d (%s): the guest's [bz_pov] %d is not the rule's %s (z_b %d air %d s_b "
                         "%d, SPEC.md 128.12.4.5)" % (frames, phase, g.b("bz_pov"), "OVER" if view[1][2] else "under",
                                                      lk.zb, lk.air, lk.sb))
        slab = view[1]
        x4 = lk.px & ~3
        meets = slab and x4 < slab[0] + BB.PL_W and slab[0] < x4 + BB.FOOT_W and lk.py < slab[1] + BB.PL_H \
            and slab[1] < lk.py + BB.FOOT_H
        feats = []
        if phase == "ride" and meets and g.b("bz_onp"):
            feats.append("ride")
        # THE RIDE BOX (SPEC.md 128.13.4.1): the platform's box merged into the riding ball's group
        if phase == "ride" and sc["tfct"] == 2 and sc["tfcgr"] == 0 and g.b("bz_onp") and sc["tfbx"]:
            feats.append("ridebox")
        sc["ridebox_last"] = "ridebox" in feats
        if phase == "over" and meets and slab[2]:
            feats.append("pover")
        if phase == "low":
            feats += sorted(set(c[0] for c in commits if c[0] in LOW_FEATS))
        if sc.get("cwrap"):
            feats.append("wrapcommit")
            sc["cwrap"] = False
        if phase == "defer" and DF_KICK < sc.get("kcur", -1) <= DF_KICK + DF_ALT:
            # the post's cells outside EVERY box, and bz_ndef moved: it WAITED with lit cells on the glass
            lane = sc["df"][0]
            col, brow, w, h = lane_rects(crs)[lane][:4]
            out = [(x, y) for x in range(col, col + w) for y in range(8 * brow, 8 * (brow + h))
                   if not any(b[0] <= x < b[0] + b[2] and b[1] <= y < b[1] + b[3] for b in sc["tfbx"])]
            if out and (sc["tfnd"] - sc.get("nd0", sc["tfnd"])) & 0xFFFF and g.lanes().get(lane) == 1:
                feats.append("defer")
                sc["dframes"] += 1
        sc["nd0"] = sc["tfnd"]
        if phase == "ringend" and not g.b("bz_full") and wrap_boxes(g, st, g.boxes()):
            sc["rewraps"] = sc.get("rewraps", 0) + 1
            feats.append("wrapbox")             # (last: `fastwrap` wants "wrapbox) at bz_presented")
        if phase == "pwait" and sc["pwn0"] is not None:
            if sc["tfwait"] or (frames - 1) in sc["wfr"]:   # a WAITED frame, and the frame after it
                feats.append("pwait")
            if sc["tfwait"]:
                sc["wfr"].add(frames)
                sc["waits"] += 1
                if sc["tfct"] == 3:
                    sc["strip"] += 1
        commits = []
        if phase == "entercol" and sc.pop("ecol", False):
            feats.append("enter_col")
            sc["ecn"] = sc.get("ecn", 0) + 1
        if feats or frames % 10 == 0 or phase in ("low", "defer", "pwait", "ringend", "entercol"):
            n_, box = diff(g.decode(st[0]), ref.picture(st[1], st[2], lk, view))
            for f in feats:
                cnt[f] = cnt.get(f, 0) + 1
            if n_:
                fails.append("MILL play frame %d (%s%s) at bz_presented, card != oracle: S %d R0 %d c0 %d ball "
                             "%d,%d (z_b %d air %d, slab %s): %d px, lines %d-%d, x %d-%d" % (
                                 frames, phase, " " + "+".join(feats) if feats else "", *st, lk.zb, lk.air, slab,
                                 n_, *box))
        prev = (st, lk, view)
        if len(fails) >= 4:
            break
    m.bp_exec()
    g.putb("bz_cmode", 0)
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the MILL play ends on Esc", guest=60)
    dropped(g, "the MILL play")
    nlift = lift_steps(P, sc["pwn0"], sc["pwn1"]) if sc["pwn0"] is not None and sc["pwn1"] is not None else 0
    if sc["df"] and not fails and sc["dframes"] < 1:
        fails.append("MILL play: the DEFER scene had no frame on which post %d WAITED drawn lit with a cell outside "
                     "every box (bz_ndef moved): the defer case was never in front of the check (SPEC.md 128.13.7 "
                     "item 1)" % sc["df"][0])
    if sc["pw"] and not fails:
        if nlift < PW_STEPS:
            fails.append("MILL play: the PWAIT scene saw %d lift steps, at least %d asserted (SPEC.md 128.13.12)" % (
                nlift, PW_STEPS))
        if not sc["strip"]:
            fails.append("MILL play: the PWAIT scene had no WAITED frame on which an entering row met the slab's "
                         "drawn footprint (bz_ctype 3) in %d tries (SPEC.md 128.13.12)" % sc["tries"])
    print("%s MILL play: the ball poked onto the slab and ridden %d frames, then under it %d: frames checked with "
          "the slab's layer in the riding ball's box %d, THE RIDE BOX %d, the slab OVER the ball %d; then THE LOW "
          "SCENARIO (post %s at window line %d, %d frames): checked frames with a wheel commit AHEAD %d, BEHIND %d, "
          "a LEAD %d; THE DEFER SCENE (post %s): %d frames waiting drawn lit with cells outside every box; THE PWAIT "
          "SCENE (the lift from step %s): %d lift steps, %d waited frames, %d with an entering row meeting the slab "
          "(%d tries), %d checked; THE RING'S-END SCENE: %d frames with a 3- or 4-word box's whole row across "
          "2000h checked; THE ENTERING-COLUMN SCENE (lane %s): %d frames bringing it in by a column checked; the tallest box %d lines, the tallest platform box %d; card = oracle: %s" % (
              tag, RIDE_FRAMES, OVER_FRAMES, cnt["ride"], cnt.get("ridebox", 0), cnt["pover"],
              plan[0] if plan else None, LOW_F, LOW_FRAMES, cnt["ahead"], cnt["behind"], cnt["lead"],
              sc["df"][0] if sc["df"] else None, sc["dframes"], sc["pwn0"], nlift, sc["waits"], sc["strip"],
              sc["tries"], cnt.get("pwait", 0), cnt.get("wrapbox", 0),
              sc["ec"][0] if sc.get("ec") else None, sc.get("ecn", 0), sc["tall"], sc["ptall"],
              "yes" if not fails else "NO"), flush=True)
    return fails, cnt


def pwait_step(g, sc, n, nfr):
    """THE PWAIT SCENE's pokes at its bz_t0 (sc["k"] the scene's count, N bz_nstep)"""
    n0, R0, c0, cen, p1, p2 = sc["pw"]
    k = sc["k"]
    if k == 0:
        g.putb("bz_cmode", 1)                   # TRICKLE: the window holds; it steps a row on a crossing
        g.putb("bz_first", 1)                   # the next frame: a full write centred on CEN
        poke_ball(g, cen[0], cen[1], cen[2], 0, 0, 0, air=1)
        return
    if (n & 0xFFFF) < n0 and sc["pwn0"] is None:
        poke_ball(g, p1[0], p1[1], p1[2], 0, 0, 0, air=1, same_cell=True)   # held, idle, until the rise
        return
    if sc["pwn0"] is None:
        sc["pwn0"] = n & 0xFFFF
    j = sc["pwj"]
    if j < nfr:
        sc["pwj"] += 1
        S, R0n, c0n = g.state()[:3]
        P = None
        if sc["tries"] < PW_TRIES and j >= 2 and not sc["strip"] and not g.b("bz_pyld"):
            # ACROSS THE BAND'S FOOT on a frame that may wait (the last one did not): the centre 2 lines past
            # 2L/3 of the window as it stands - TRICKLE steps it down a row, the row entering at the foot
            lsh = 1 if g.tag == "cga" else 2
            top, left = R0n << lsh, 8 * c0n
            crs = sc["crs"]
            # the centre px first, then outward a px at a time to 16 either side (the band's foot, 2 lines
            # past it, held: only the across moves - TRICKLE's row step is the line's, its column a word's
            # band away): the CGA's centre over the slab's shaft has no floor clear of OCC (the final pass)
            for dx in [0] + [s_ * d_ for d_ in range(1, 17) for s_ in (-1, 1)]:
                P = probe_ground(crs, left + 4 * g.w("bz_W") - 8 + dx, top + 2 * 200 // 3 - 8 + 2, crs._grid, 1,
                                 clear=16, flags=BB.FL_OCC | BB.FL_OCCG)
                if P:
                    break
        if P:
            sc["tries"] += 1
            poke_ball(g, P[0], P[1], P[2], 0, 0, 0, air=1)
        else:
            q = p1 if j % 2 == 0 else p2
            poke_ball(g, q[0], q[1], q[2], 0, 0, 0, air=1)
        return
    if sc["pwn1"] is None:
        sc["pwn1"] = n & 0xFFFF
    sc["pwend"] += 1                            # ENDED at one point: one box, the slab's drawn
    poke_ball(g, p1[0], p1[1], p1[2], 0, 0, 0, air=1, same_cell=sc["pwend"] > 1)


# ---- the row-0 probe (SPEC.md 128.10.11.2) ----------------------------------
def poke_ball(g, gx, gy, gz, gvx=0, gvy=0, gvz=0, same_cell=False, air=None, ztop=None, lvl=None):
    """The position and the velocities (SPEC.md 128.10.7.1), 24.8 values, and
    what a poke owes besides: bz_pokd = 1, so the next step refills the window
    round the ball's cell itself, and the SCREEN state derived from the poked
    position with a zero velocity - bbcourse.Physics.poke's _derive(True) -
    so that a frame which runs no step (about 9% of the CGA's) draws the ball
    where it was poked, not where the last step left it.  AIR, ZTOP (whole
    px) and LVL (the arrows' four levels, 128.11.7.1) are poked when given.

    SAME_CELL: leave bz_pokd as it is when the poke stays in the cell the
    window is centred on ([bz_wgx], [bz_wgy] are 16 wx, 16 wy) - the window
    then already holds that cell's neighbours, exactly as after a step that
    stayed in it, so the refill (a step's costliest part, ~4k clk) is one
    play would not pay.  The row-0 probe pokes every frame and is a timing
    row, so it pokes this way; a flag a 0-step frame left set stays set."""
    g.putd("bz_gx", gx)
    g.putd("bz_gy", gy)
    g.putd("bz_gz", gz)
    g.put("bz_gvx", gvx)
    g.put("bz_gvy", gvy)
    g.put("bz_gvz", gvz)
    if air is not None:
        g.putb("bz_air", air)
    if ztop is not None:
        g.put("bz_ztop", ztop)
    if lvl is not None:
        g.m.write(g.a("bz_lvl"), bytes(lvl))
    kx, ky = g.sd("bz_kx"), g.sd("bz_ky")       # (X0 - 8) << 8, (Y0 - 13) << 8
    g.putd("bz_bx", gx - gy + kx)
    g.putd("bz_by", ((gx + gy) >> 1) - gz + ky)
    g.put("bz_vx", 0)
    g.put("bz_vy", 0)
    if not same_cell or (gx >> 12) << 4 != g.w("bz_wgx") or (gy >> 12) << 4 != g.w("bz_wgy"):
        g.putb("bz_pokd", 1)


def probe_ground(crs, px, py, grid, sx=1, clear=16, flags=0):
    """A contact point (24.8 gx, gy, gz) whose derived picture top-left is (px, py)
    with the by fraction at 0x80, high over a FLOOR cell (at least CLEAR px above
    its floor, and none of FLAGS set in the cell: the multi-box probe asks for
    OCC and OCCG clear, so the shadow is drawn in a box of its own), placed so
    that its drift (gvx 64 SX, gvy -64 SX: at most 2 gu
    each way over a catch-up's 8 steps; SX +1 drifts right on the screen, -1
    left) keeps it in the cell, and no neighbour its circle can test over that
    drift is a WALL, OPEN, or a floor reaching within 16 px of it: an airborne
    ball that neither lands, nor meets a wall or a floor's edge, nor respawns
    within a frame.  The lowest."""
    kx, ky = (grid.x0 - 8) << 8, (grid.y0 - 13) << 8
    a8 = (px << 8) - kx                         # gx - gy, 24.8 (bx's fraction 0)
    by8 = (py << 8) | 0x80
    best = None
    for d in range(0, 8190):                    # gx + gy, whole gu
        d8 = d << 8
        gx8, gy8 = (d8 + a8) >> 1, (d8 - a8) >> 1
        if gx8 < 0 or gy8 < 0 or gx8 >= 4096 << 8 or gy8 >= 4096 << 8:
            continue
        wx, wy, u, v = gx8 >> 12, gy8 >> 12, (gx8 >> 8) & 15, (gy8 >> 8) & 15
        c = grid.cell(wx, wy)
        if c[3] != BB.KIND_FLOOR or c[4] & flags:   # (not a GOAL: play would end on it)
            continue
        gz8 = (d8 >> 1) + ky - by8
        z4 = (gz8 >> 6) - 4 * clear             # quarter px, CLEAR px under the ball
        if gz8 >= 600 << 8 or BB.Physics.h4(c, u, v) > z4:
            continue
        ulo, uhi = (u, u + 2) if sx > 0 else (u - 2, u)     # u and v over the drift (u +- 2, v -+ 2
        vlo, vhi = (v - 2, v) if sx > 0 else (v, v + 2)     # over 8 steps): it stays in the cell
        if ulo < 0 or uhi > 15 or vlo < 0 or vhi > 15:
            continue
        # the neighbours the circle can test over the drift: across an edge it comes within BZ_RAD of
        xs = [0] + ([-1] if ulo < BB.RAD else []) + ([1] if uhi > 16 - BB.RAD else [])
        ys = [0] + ([-1] if vlo < BB.RAD else []) + ([1] if vhi > 16 - BB.RAD else [])
        ok = True                               # none of them a WALL, OPEN, or a floor within
        for i in xs:                            # 16 px of the ball anywhere
            for j in ys:
                n = grid.cell(wx + i, wy + j)
                if n[3] == BB.KIND_WALL or (n[3] == BB.KIND_VOID and n[0] == BB.Z_OPEN):
                    ok = False
                elif n[3] in (BB.KIND_FLOOR, BB.KIND_GOAL) and \
                        max(BB.Physics.h4(n, p, q) for p in (0, 16) for q in (0, 16)) > z4:
                    ok = False
        if ok and (best is None or gz8 < best[2]):
            best = (gx8, gy8, gz8)
    return best


def tpoke(g, crs):
    """The TRIAL leg's frame of THREE boxes (SPEC.md 128.11.10.1, 128.11.17.2):
    at bz_t0 of a frame that runs a step, the ball poked AIRBORNE 40 - 56 px
    across the screen, inside the window with its shadow, over a floor cell
    with OCC and OCCG clear (probe_ground's search) - so the ball's old and new
    footprints are two boxes (their union wider than BZ_BOXW) and the shadow,
    the gate clear, a third.  -> (dx, dy) poked, or None where no cell fits."""
    tag = g.tag
    S, R0, c0, px, py = g.state()
    top, left = R0 * RL[tag], c0 * 8
    grid = getattr(crs, "_grid", None) or BB.Grid(crs.cga)
    for dx in (40, -40, 48, -48, 56, -56):
        tpx = px + dx
        if tpx < left + 8 or tpx + 24 > left + W[tag] - 8:
            continue
        for dy in (0, -8, 8, -16, 16, -24, 24):
            tpy = py + dy
            if tpy < top + 8 or tpy + 16 + 48 > top + 192:
                continue
            sx = 1 if dx > 0 else -1
            gp = probe_ground(crs, tpx, tpy, grid, sx, clear=16, flags=BB.FL_OCC | BB.FL_OCCG)
            if gp:
                poke_ball(g, gp[0], gp[1], gp[2], 64 * sx, -64 * sx, 36, air=1)
                return dx, dy
    return None


TPOKE_AT, TPOKE_EVERY, TPOKE_MAX = 300, 40, 12


# THE RING'S-END SCENE (the final pass of wave 3b): BENCH's, TRIAL's and MILL's routes met no box whose
# whole rows cross the ring's end on either card (0 frames in two runs) - the ring is WORLD-anchored (a card
# row's offset is (rb R + 2 c) mod 8192 for world card row R and word column c, whatever the window), so
# only a few world spots put a box's whole row past the path's first across 2000h, and no route passes
# one.  The last scene of the MILL play: the ball poked (airborne, still, over a floor with OCC and OCCG
# clear) to such a spot with a full write centred on it, then held there a line up and down for RE_HOLD
# frames - each frame's box the union of the two footprints, 3 or 4 words, every frame checked
RE_HOLD = 8

# THE ENTERING-COLUMN SCENE (the final pass of wave 4): MILL's benchmark brings a lane in by a
# COLUMN on a frame or two a run on the CGA, or on none - wave 4's heavier frames moved which frames
# step a column, and two runs saw 0 - so the `enter_col` feature gets a scene of its own, the MILL
# play's last: a centred full write with the window's left (right) edge just right (left) of a rotor's
# or a post's columns, the ball HELD there; then on the dead zone's edge (TRICKLE, bz_cmode 1: the
# window holds until the ball crosses it), held; then 2 px across it, so the window steps one column
# and the column it brings in is the lane's.  The Hercules' 45-word window holds every MILL lane's
# columns whatever c0, so the scene has no window there (FEAT_OPTIONAL: reported)
EC_STEP = 3                         # the centred full write and two held frames, then the dead zone's edge
EC_END = EC_STEP + 6                # held one frame, then the step and the frames after it


def entercol_plan(g, crs):
    """-> (lane, R0, c0, the centre's contact point, the edge's, side) or None"""
    tag = g.tag
    lsh, rl = (1 if tag == "cga" else 2), RL[tag]
    H, Wc, rmax, cmax = g.w("bz_H"), g.w("bz_W"), g.w("bz_rmax"), g.w("bz_cmax")
    grid = getattr(crs, "_grid", None) or BB.Grid(crs.cga)
    rects = lane_rects(crs)
    for side in (-1, 1):
        for i in sorted(rects):
            if crs.part["props"][i]["kind"] not in (BB.PK_WINDMILL, BB.PK_BUMPER):
                continue
            q0, q1, a0, a1 = lane_cells(rects[i], lsh)
            c0 = a1 if side < 0 else a0 - Wc      # the lane wholly outside, its nearest column the next in
            R0 = max(0, min(rmax, (q0 + q1) // 2 - H // 2))
            if not (1 <= c0 <= cmax - 1 and q0 >= R0 and q1 <= R0 + H):
                continue
            top, left = R0 << lsh, 8 * c0
            cen = None
            for dy in range(rl):
                for dx in range(8):
                    cen = cen or probe_ground(crs, left + 4 * Wc - 8 + dx, top + 92 + dy, grid, 1, clear=16,
                                              flags=BB.FL_OCC | BB.FL_OCCG)
            hx = left + 2 * Wc - 8 if side < 0 else left + 6 * Wc - 8
            hold = None
            for dy in range(0, 24, rl):             # (the band's middle: no row step on the way)
                hold = hold or probe_ground(crs, hx, top + 92 - dy, grid, side, clear=8,
                                            flags=BB.FL_OCC | BB.FL_OCCG)
            if cen and hold:
                return i, R0, c0, cen, hold, side
    return None


def entercol_poke(g, plan, k):
    """THE ENTERING-COLUMN SCENE's pokes at its K-th bz_t0"""
    _lane, _R0, _c0, cen, hold, side = plan
    if k == 0:
        g.putb("bz_cmode", 1)                   # TRICKLE: the window holds until the dead zone's edge
        g.putb("bz_first", 1)                   # the next frame: a full write centred on CEN
        poke_ball(g, cen[0], cen[1], cen[2], 0, 0, 0, air=1)
    elif k < EC_STEP:
        poke_ball(g, cen[0], cen[1], cen[2], 0, 0, 0, air=1, same_cell=True)
    elif k == EC_STEP:
        poke_ball(g, hold[0], hold[1], hold[2], 0, 0, 0, air=1)
    elif k == EC_STEP + 1:
        poke_ball(g, hold[0], hold[1], hold[2], 0, 0, 0, air=1, same_cell=True)
    else:                                       # 2 px across the edge, in the cell: one column step
        poke_ball(g, hold[0] + 256 * side, hold[1] - 256 * side, hold[2], 0, 0, 0, air=1, same_cell=True)


def ringend_plan(g, crs):
    """-> (A, B): two contact points a line apart whose ball footprints
    (BB.FOOT_W x BB.FOOT_H at the picture's top-left) span 3 or 4 words and
    both have a WHOLE card row other than their first whose offset plus 2w
    passes 2000h (wrap_boxes's test, world-anchored); or None.  Of those, the
    spots that let `fastwrap` show first: two words past the end rather than
    one, the crossing row among the ball's quickly changing lines (its upper
    or lower quarter, not its middle or its edge), and the footprint's first
    word holding only its first 4 px (the crossing words then the ball's) -
    the red writes the crossing words of a CGA row's two lines into each
    other's places (its 16KB mirrored), which only lines that differ show
    (the final pass of wave 3b: the first spot found was the ball's last two
    lines, near alike, and the red stayed green)"""
    tag = g.tag
    rl, rb = RL[tag], RB[tag]
    grid = getattr(crs, "_grid", None) or BB.Grid(crs.cga)
    ylim, xlim = crs.brows * 8 - BB.FOOT_H - 8, crs.cols * 8 - BB.FOOT_W - 8

    def crosses(px, y):
        x4 = px & ~3                            # the footprint's left edge (a byte: 4 px, SPEC.md 128.4)
        x0 = x4 >> 3
        w = ((x4 + BB.FOOT_W - 1) >> 3) - x0 + 1
        if w not in (3, 4):
            return None
        first = (y + rl - 1) // rl
        last = (y + BB.FOOT_H) // rl - 1
        for r in range(first + 1, last + 1):
            o = (r * rb + 2 * x0) & 0x1FFF
            if o + 2 * w > 0x2000:
                return r, o, w
        return None
    cands = []
    for y in range(8 + 8 * 4, ylim, 1):
        for px in range(8 * 2, xlim, 2):
            a, b = crosses(px, y), crosses(px, y + 1)
            if not (a and b):
                continue
            r, o, w = a
            ln = r * rl - y                     # the crossing row's first line, in the footprint
            past = w - (0x2000 - o) // 2         # the words written past 2000h
            score = 4 * past + 2 * (2 <= ln <= 5 or 9 <= ln <= 12) + ((px & 7) >= 4)
            cands.append((-score, y, px))
    for _, y, px in sorted(cands)[:400]:
        a = probe_ground(crs, px, y, grid, 1, clear=16, flags=BB.FL_OCC | BB.FL_OCCG)
        b = a and probe_ground(crs, px, y + 1, grid, 1, clear=16, flags=BB.FL_OCC | BB.FL_OCCG)
        if a and b:
            return a, b
    return None


PROBE_CLEAR = 10    # px over the floor: z - h about 10, so the shadow (spy = py + 10 + (z - h),
                    # 128.11.9.4) is a box of its own just below the ball's (their union 26 lines,
                    # over BZ_BOXH's 24) - the CGA's late case of 128.11.10.3


PROBE_EDGE = 40     # px: the probe's ball 40 px left of the window's right edge - its 20 px footprint
                    # ends 20 px from it, inside the edge clause's 24 (SPEC.md 128.12.7), and its centre
                    # is right of GLIDE's dead zone (6W: 240 of 320 px, 270 of 360)


def cycles(m):
    return int(m.status()["cycles"])


def probe(g, ref):
    """Part 4: the POKED row-0 probe, play mode on BENCH in GLIDE, every frame a
    multi-box frame (the ball at window row 0, its shadow in a box below)."""
    m, tag = g.m, g.tag
    crs = ref.c
    grid = BB.Grid(crs.cga)
    for nm, op in (("bz_tb.first", 0x9D), ("bz_wbox.wr", 0xE8)):
        got = m.read(g.a(nm), 1)[0]
        assert got == op, "%s is not the instruction the probe breakpoints after (%02X, not %02X)" % (nm, got, op)
    m.bp_exec(g.a("bz_launch"))
    g.key("Enter")
    assert m.wait_stop(60) == "breakpoint", "Enter did not reach bz_launch"
    g.putb("bz_crs", CRS_K["bench"])            # play mode, on the benchmark's course
    g.putb("bz_cmode", 0)                       # GLIDE (C cycles it; it persists)
    if "bz_hvoff" in g.sym:                     # the shipped camera: a poked frame is HEAVY
        g.putb("bz_hvoff", 0)                   # (level 1, SPEC.md 128.12.7)
    g.putb("bz_tpoke", 1)                       # time play's boxes: only a benchmark's are
                                                # (bz_wbox, SPEC.md 128.11.10.3)
    m.bp_exec()
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 5, "play mode on BENCH runs", guest=60)
    m.pause()
    g.check_base()
    # 1. the window at the course's TOP: play starts on BENCH's start plateau,
    # and GLIDE settles with the window clamped at R0 = 0 - the one place play
    # can put a box at window row 0 (a flight's apex over the top's back edge,
    # 128.10.4.1).  The probe pans RIGHT from there.
    wk = Walker(g, t0=True, extra=("bz_vr.rose", "bz_vr.high", ("bz_wbox.wr", 0), ("bz_wbox.wr", 3),
                                   "bz_wbox.out", ("bz_tb.first", 1)))
    m.bp_exec(wk.pr)
    still, last = 0, None
    for _ in range(2000):
        assert wk.next() == "pr"
        cur = (g.w("bz_R0"), g.w("bz_c0"))
        still = still + 1 if cur == last else 0
        last = cur
        if still >= 8:
            break
    assert still >= 8, "the camera never settled on the course's start (last %r)" % (last,)
    wk.arm()
    R0, c0 = last
    cmax = g.w("bz_cmax")
    print("%s probe: the window settled at R0 %d c0 %d on the start (cmax %d)" % (tag, R0, c0, cmax), flush=True)
    assert R0 == 0 and c0 + PROBE_MIN + 2 <= cmax, \
        "the probe's window is not at the top clamp with room to pan right: R0 %d, c0 %d, cmax %d" % (R0, c0, cmax)
    # 2. the probe frames.  The FIRST is a lead-in whose timing is not judged:
    # its poke moves the ball from the start to the window's first line, a
    # teleport play cannot make.  Its pictures are checked like every frame's.
    frames, hit, multi, fails, prev = 0, 0, 0, [], None
    agree, pess, unjudged, verd = 0, 0, 0, []
    late_agree = 0                              # later boxes LATE by both bz_latechk and the counter
    fe = None
    while frames < PROBE_MAX:
        k = wk.next()
        if k == "t0":
            R0, c0 = g.w("bz_R0"), g.w("bz_c0")
            if R0 != 0 or c0 >= cmax:
                break
            # the ball's top on the window's first line (world line 0: the window stays clamped) and
            # its centre RIGHT of the dead zone ([2W, 6W] px), so GLIDE steps a column at the right edge
            # each frame, clear of the footprint - and, wave 3, its footprint within the edge clause's
            # 24 px of the right edge: a poked frame is HEAVY (level 1, SPEC.md 128.12.7), which
            # withholds the column unless the ball is that near the edge
            tpx = c0 * 8 + W[tag] - PROBE_EDGE
            f1 = frames + 1
            split = f1 >= PROBE_SPLIT and (f1 - PROBE_SPLIT) % 2 == 0
            back = f1 >= PROBE_SPLIT - 1 and not split
            if back:                    # the frame BEFORE a split: the ball 40 px back, so the split
                tpx -= 40               # frame's old and new footprints are two boxes at row 0, the
                                        # second behind the beam on the CGA, the new one at the edge
            gp = probe_ground(crs, tpx, 0, grid, 1, clear=PROBE_CLEAR, flags=BB.FL_OCC | BB.FL_OCCG)
            if gp is None and back:     # no ground there: the next frame is not split
                back, tpx = False, tpx + 40
                gp = probe_ground(crs, tpx, 0, grid, 1, clear=PROBE_CLEAR, flags=BB.FL_OCC | BB.FL_OCCG)
            if gp is None:              # the ball's screen column has left the course: the probe is over
                break
            poke_ball(g, gp[0], gp[1], gp[2], 64, -64, 36, same_cell=True)
            fe = {"rise": None, "vedge": None, "box": [], "if": None, "late0": g.w("bz_late"), "split": split}
            continue
        if fe is None:
            continue
        if k in ("bz_vr.rose", "bz_vr.high"):
            fe["rise"], fe["vedge"] = cycles(m), k == "bz_vr.rose"
            continue
        if k == "bz_wbox.wr+0":
            fe["box"].append({"i": (wk.r["si"] - g.sym["bz_boxes"]) // BZ_BOXD, "c0": cycles(m)})
            continue
        if k == "bz_wbox.wr+3":
            fe["box"][-1]["c1"] = cycles(m)
            continue
        if k == "bz_wbox.out":
            fe["box"][-1]["dl"] = wk.r["dx"] & 0xFF
            continue
        if k == "bz_tb.first+1":
            fe["if"] = (bool(wk.r["flags"] & 0x200), len(fe["box"]))
            continue
        if k == "tf":
            if prev is not None and not g.b("bz_full"):
                n, box = diff(g.decode(prev[0][0]), ref.picture(prev[0][1], prev[0][2], prev[1]))
                if n:
                    fails.append("probe frame %d at bz_tf: the shown window is not the last frame's picture, "
                                 "card != oracle: %d px, lines %d-%d, x %d-%d" % (frames + 1, n, *box))
            fe["boxes"], fe["wtop"], fe["full"] = g.boxes(), g.w("bz_wtop"), g.b("bz_full")
            continue
        # bz_presented
        frames += 1
        st = g.state()
        lk, why = g.look(crs)
        if why:
            fails.append("probe frame %d: %s" % (frames, why))
        n, box = diff(g.decode(st[0]), ref.picture(st[1], st[2], lk))
        r0, dc = g.b("bz_row0"), g.s("bz_dc")
        bxs = fe["boxes"]
        is_multi = len(bxs) >= 2 and g.b("bz_snv") and any(b[4] == 1 for b in bxs)
        if n:
            fails.append("probe frame %d at bz_presented, card != oracle: S %d R0 %d c0 %d ball %d,%d (row0 %d, "
                         "dc %d, %d boxes): %d px, lines %d-%d, x %d-%d" % (frames, *st, r0, dc, len(bxs), n, *box))
        if frames > 1 and not fe["full"]:       # (the first: the lead-in)
            hit += bool(r0 and dc)
            multi += bool(is_multi and r0)
            tm = fe["box"]
            if tm and tm[0].get("dl"):
                fails.append("probe frame %d: the FIRST box, at window row 0, is late by bz_latechk (DL %d): "
                             "128.9 item 6's order did not hold it ahead of the beam" % (frames, tm[0]["dl"]))
            if not is_multi and g.w("bz_late") != fe["late0"]:
                fails.append("probe frame %d: bz_late counted %d on a frame of one box group" % (
                    frames, g.w("bz_late") - fe["late0"]))
            if is_multi:
                ifon, at_box = fe["if"] if fe["if"] else (None, None)
                if not ifon or at_box != 1:
                    fails.append("probe frame %d: interrupts %s after bz_tb's POPF, with %s boxes started "
                                 "(on, after the FIRST box and before the second, 128.11.10.3)" % (
                                     frames, "ON" if ifon else "OFF", at_box))
                for j, b in enumerate(tm):
                    x0, y0, w, h, grp = bxs[b["i"]]
                    y0w = y0 - fe["wtop"]
                    fl = 0 if (j == 0 and r0) else y0w
                    rec = (frames, j, grp, y0w, h, bool(b.get("dl")))
                    if tag != "cga" or not fe["vedge"]:
                        unjudged += 1
                        verd.append(rec + (None,))
                        continue
                    ms = fe["rise"] + (CGA_TO0 + fl) * CGA_LINE - b["c0"]
                    me = fe["rise"] + (CGA_TO0 + y0w + h - 1) * CGA_LINE - b["c1"]
                    margin = min(ms, me)
                    verd.append(rec + (margin,))
                    if bool(b.get("dl")) == (margin < 0):
                        agree += 1
                        late_agree += j > 0 and margin < 0
                    elif b.get("dl") and margin < BZ_VLAT * 4 + CGA_LINE:
                        pess += 1               # the documented rounding toward LATE
                    elif not b.get("dl") and -margin <= SPIN_TOL:
                        agree += 1              # within bz_vr's spin turn of the beam
                    else:
                        fails.append("probe frame %d box %d (group %d, window lines %d-%d): bz_latechk says %s, the "
                                     "cycle counter %s by %d clocks (the sync's rise at cycle %d)" % (
                                         frames, j, grp, y0w, y0w + h - 1, "LATE" if b.get("dl") else "on time",
                                         "on time" if margin >= 0 else "LATE", abs(margin), fe["rise"]))
        prev = (st, lk)
        fe = None
        if len(fails) >= 6:
            break
    m.bp_exec()
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the probe's play ends on Esc", guest=60)
    dropped(g, "the probe")
    g.putb("bz_tpoke", 0)                       # (the package's bss persists: later legs untimed)
    nlate = sum(1 for v in verd if v[5])
    print("%s probe: %d frames (the first a lead-in), %d with the boxes at window row 0 and an entering column "
          "(128.9 item 6's path), %d MULTI-BOX (a shadow box below the ball's); card = picture on every one at "
          "bz_tf and bz_presented: %s" % (tag, frames, hit, multi, "yes" if not fails else "NO"), flush=True)
    print("%s probe boxes timed: %d, late by bz_latechk %d; against the cycle counter %d agree, %d late within the "
          "documented rounding, %d not judged (%s)" % (
              tag, len(verd), nlate, agree, pess, unjudged,
              "the Hercules: its blank holds every box" if tag != "cga" else "the sync already high"), flush=True)
    for v in verd[:12]:
        print("    frame %d box %d group %d lines %d+%d: guest %s, margin %s" % (
            v[0], v[1], v[2], v[3], v[4], "LATE" if v[5] else "on time", v[6]), flush=True)
    if hit < PROBE_MIN:
        fails.append("only %d probe frames took item 6's path (row 0 and an entering column); %d needed" % (
            hit, PROBE_MIN))
    if multi < PROBE_MIN:
        fails.append("only %d probe frames were multi-box (the shadow in a box of its own); %d needed" % (
            multi, PROBE_MIN))
    if tag == "cga" and multi and not agree:
        fails.append("no box of the probe was judged against the cycle counter")
    print("%s probe: later boxes LATE by bz_latechk and by the cycle counter alike: %d (the split frames, %d on)" % (
        tag, late_agree, PROBE_SPLIT), flush=True)
    if tag == "cga" and not late_agree:
        fails.append("no LATER box of the probe was late by the cycle counter and judged so: the split frames "
                     "(the ball's old and new footprints two boxes at row 0) did not reach bz_latechk's later-box "
                     "verdict")
    return fails


PARTS = ("glass", "bench", "trial", "mill", "play", "probe", "w4", "hud")


def run(tag, apps=None, src=None, art=None, parts=PARTS):
    """-> {"parts": the parts run, "fails": [...], and the benchmarks' tallies}"""
    sym = symbols(src, art)
    out = {"parts": parts, "fails": []}
    with os88ui.boot(at("build/os8088-360.img"), apps=apps or at("build/bonanza360.img"),
                     machine=MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = Bz(ui, tag, sym)
        ui.settle()
        if "glass" in parts:
            glass(g, Ref(tag, course("first"), art))
        if "bench" in parts:                    # [bz_hvoff] 1: wave 2's camera, its eight directions
            out["bench"] = bench(g, Ref(tag, course("bench"), art), hvoff=1 if "bz_hvoff" in sym else None)
            out["fails"] += out["bench"]["fails"]
        if "trial" in parts and not out["fails"]:
            out["trial"] = bench(g, Ref(tag, course("trial"), art), trial=True,
                                 hvoff=0 if "bz_hvoff" in sym else None)
            out["fails"] += out["trial"]["fails"]
        if "mill" in parts and not out["fails"]:
            out["mill"] = bench(g, Ref(tag, course("mill"), art), mill=True, hvoff=0)
            out["fails"] += out["mill"]["fails"]
        if "play" in parts and not out["fails"]:
            f, out["play"] = mill_play(g, Ref(tag, course("mill"), art))
            out["fails"] += f
        if "probe" in parts and not out["fails"]:
            out["fails"] += probe(g, Ref(tag, course("bench"), art))
        if "w4" in parts and not out["fails"]:  # wave 4 (SPEC.md 128.14.14): the props, the blank
            f, out["w4"] = w4_part(g, art)
            out["fails"] += f
        if ("hud" in parts or "hudscene" in parts) and not out["fails"]:   # ...and the HUD, while it is built
            f, out["hud"] = hud_part(g, art, legs="hud" in parts)
            out["fails"] += f
    return out


def verdict(tag, r):
    bad = list(r["fails"])
    if "bench" in r:
        b = r["bench"]
        missing = [d for d in DIRS if not b["done"][d]]
        if missing:
            bad.append("directions never checked: %s" % missing)
        if not b["full"]:
            bad.append("the first frame's full write was not checked")
        if not b["controls"] and not b["fails"]:
            bad.append("no diagonal frame for the negative controls")
        if not b["hid"] and not b["fails"]:
            bad.append("no checked frame hid any of the ball behind an occluder record (SPEC.md 128.10.11.3)")
    if "trial" in r and not r["trial"]["fails"]:
        t = r["trial"]
        if not t["shd"]:
            bad.append("TRIAL: no checked frame had the shadow in a box of its own (SPEC.md 128.11.17.2)")
        if not t["b3"]:
            bad.append("TRIAL: no checked frame had three boxes or more (SPEC.md 128.11.17.2)")
        if not t["shdin"]:
            bad.append("TRIAL: no checked frame had the shadow drawn inside the ball's box (SPEC.md 128.11.10.2)")
        if not t["orders"]:
            bad.append("TRIAL: no frame's raster order was checked")
    if "mill" in r and not r["mill"]["fails"]:
        mm = r["mill"]
        for f in MILL_FEATS:
            if f in LOW_FEATS and f not in ("behind",) and "play" not in r:
                continue                        # (the LOW scenario's: judged when the play part runs)
            if not mm["feat"][f] and not (r.get("play") or {}).get(f) and f not in FEAT_OPTIONAL[tag]:
                bad.append("MILL: no checked frame with %s (%d frames had it; SPEC.md 128.12.13.2)" % (
                    f, mm["seen"][f]))
        if not mm["exits"]:
            bad.append("MILL: no tube exit on the route: the footprint-in-the-window check never ran")
        if not mm["orders"]:
            bad.append("MILL: no frame's raster order was checked")
    if "play" in r and not r["fails"]:
        for f in PLAY_FEATS:
            need = FEAT_EACH if f in ("ridebox", "pwait") else 1
            if r["play"].get(f, 0) < need:
                bad.append("MILL play: %d checked frames with %s, at least %d (SPEC.md 128.12.13.2, 128.13.12)" % (
                    r["play"].get(f, 0), f, need))
    # THE RING'S END (SPEC.md 128.13.12): a 3- or 4-word box whose whole rows cross 2000h, checked at least
    # once a card - on BENCH, TRIAL or MILL's benchmarks
    # - on BENCH, TRIAL or MILL's benchmarks, or the MILL play's ring's-end scene (whose spot is the
    # world's: no route passes one, the final pass of wave 3b)
    legs = [r[x] for x in ("bench", "trial", "mill") if x in r]
    if (legs or "play" in r) and not r["fails"] and ("bench" in r or "play" in r) and \
            not sum(x.get("wrapck", 0) for x in legs) + (r.get("play") or {}).get("wrapbox", 0):
        bad.append("the ring's end: no checked frame wrote a 3- or 4-word box's whole rows across it "
                   "(%d frames had one; SPEC.md 128.13.12)" % sum(x.get("wraps", 0) for x in legs))
    if "w4" in r and not r["fails"]:
        bad += w4_verdict(tag, r["w4"])
    if "hud" in r and not r["fails"]:
        bad += hud_verdict(tag, r["hud"])
    return bad


# ---- wave 4 (SPEC.md 128.14.14): the props on the glass, the respawn's blank, and the HUD -------------
W4_EVERY = 41                       # the W4 replays: one presented frame in this many checked besides the rest
HUD_EACH = 3                        # the HUD legs: the first frames checked of each direction / box kind
HUD_EVERY = 29                      # ...and one presented frame in this many
HUD_MAXR = 2                        # bzgame.inc BZ_MAXR: the rect's foot this many card rows above the window's
HUD_SCENE = 40                      # the lane scene's frames after its full write
HUD_FAILS = 6                       # a HUD leg runs on past a failure until this many (a red arm's own check
                                    # may be a later frame's: the write-once check needs a scroll frame)
SENTINEL = 0x5A                     # a full write's watched rect bytes are set to this first (bz_tr), so both
                                    # writers' values show and a rect nobody writes keeps it
MODE_PORT = {"cga": 0x3D8, "herc": 0x3B8}
VBASE = {"cga": 0xB8000, "herc": 0xB0000}
HK_NAMES = {1: "union", 2: "glyph", 3: "hide", 4: "show", 5: "full"}


class Loop:
    """The frame loop under breakpoints the caller sets and re-sets: EXEC names
    of the package's (each returned by its name), the card's MODE port (an `io`
    breakpoint: returned 'io', AL the value an OUT wrote) and card bytes (`mem`
    breakpoints, any access: returned 'mem').  An io stop is reported at the
    start of the next step (os88marty.breakpoints), so whatever is not an exec
    address is the one other kind armed."""

    def __init__(self, g, names, io=None):
        self.g, self.m = g, g.m
        self.ex = {g.a(n): n for n in names}
        self.io, self.mem = io, ()

    def arm(self, mem=()):
        self.mem = tuple(mem)
        bps = [{"type": "exec", "addr": a} for a in self.ex]
        if self.io is not None and not self.mem:
            bps.append({"type": "io", "addr": self.io})
        bps += [{"type": "mem", "addr": a} for a in self.mem]
        self.m.breakpoints(bps)

    def next(self):
        m = self.m
        m.run()
        st = m.wait_stop(60)
        assert st == "breakpoint", "the frame loop stopped reaching its marks (state %r)" % st
        self.r = r = m.regs()
        flat = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
        if flat in self.ex:
            return self.ex[flat]
        return "mem" if self.mem else "io"


def card_addrs(g, rect):
    """the flat card addresses of a rect (x0 x1 y0 y1, world word columns and
    lines, inclusive: bz_hnr's shape) - the ring's (row x RB + 2 word) mod 8,192
    in its line's bank (SPEC.md 128.2)"""
    tag = g.tag
    rl, rb = RL[tag], RB[tag]
    x0, x1, y0, y1 = rect
    out = []
    for y in range(y0, y1 + 1):
        bank = (y % rl) * 0x2000
        for x in range(x0, x1 + 1):
            o = ((y // rl) * rb + 2 * x) % 8192
            out += [VBASE[tag] + bank + o, VBASE[tag] + bank + (o + 1) % 8192]
    return out


def hud_rect_lines(tag):
    """the HUD rect's window lines [y0, y1) and its pixels [8, 24): word columns
    1 - 2 of the six lines ending BZ_MAXR card rows above the foot (128.14.5.3)"""
    y1 = 200 - HUD_MAXR * RL[tag]
    return y1 - 6, y1


def with_panel(tag, rows, pan):
    """ROWS (a window's 200 rows of pixel values) with the panel's 24 bytes PAN
    composed over the HUD's rect - the oracle's picture with the HUD shown
    (SPEC.md 128.14.14 bonanzaring); PAN None: the rect MASKED to 0 on both
    sides (a panel this row has not yet seen on the card)"""
    y0, y1 = hud_rect_lines(tag)
    out = list(rows)
    for j, y in enumerate(range(y0, y1)):
        r = bytearray(out[y])
        r[8:24] = bytes(16) if pan is None else b"".join(LUT[c] for c in pan[4 * j:4 * j + 4])
        out[y] = bytes(r)
    return out


def load_demo(g, kd):
    """V with [bz_vk] poked to KD - 1: the shipped demo BZD<KD>.BIN in the log (128.14.22 item 7)"""
    m = g.m
    demo = open(os.path.join(ROOT, at("build/bonanza-art"), "BZD%d.BIN" % kd), "rb").read()
    m.pause()
    g.putb("bz_vk", kd - 1)
    m.run()
    M.until(m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)
    g.key("KeyV")
    M.until(m, lambda _: bytes(m.read(g.a("bz_rlog"), len(demo))) == demo, "V to load BZD%d.BIN" % kd, guest=20)
    return demo


def start_replay(g, log=None, poke=None):
    """R on the held log (LOG written into bz_rlog first when given), stopped at
    the first bz_t0 with POKE (bonanza_phys's poke dict) applied there"""
    m = g.m
    m.pause()
    if log is not None:
        g.write_log(log)
    m.bp_exec(g.a("bz_t0"))
    m.run()
    g.key("KeyR")
    assert m.wait_stop(60) == "breakpoint", "R did not start the replay"
    g.check_base()
    if poke:
        poke_ball(g, poke["gx"], poke["gy"], poke["gz"], poke["gvx"], poke["gvy"], poke["gvz"], air=poke["air"],
                  ztop=poke["ztop"], lvl=poke["lvl"])
        if "bz_onp" in g.sym:
            g.putb("bz_onp", poke.get("onp", 0))
            g.putb("bz_ps", (g.b("bz_ps") & ~4) | (4 if poke.get("onp") else 0))
        for k_, v in (poke.get("extra") or {}).items():
            g.putb("bz_" + k_, v)


def end_replay(g, what):
    m = g.m
    m.bp_exec()
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 0, "%s to end" % what, guest=60)
    dropped(g, what)


def replay_end(g):
    """at bz_t0: the replay's end (this bz_t0 leaves the bracket)"""
    return g.b("bz_goal") or not (g.b("bz_rn") or g.w("bz_rruns"))


def w4_replay(g, ref, label, log=None, poke=None):
    """One REPLAY on a wave-4 course with the HUD OFF, every frame under the
    loop: the card equal to the oracle at bz_presented on every frame that
    FULL-writes (the first and each respawn's cut), the CAPTURE frame (the ball
    holed: gone, its footprint restored, bz_hidn), every lip-out's frame
    (bz_nlip moved: the pop), every frame on which a FLAG's drawn pose changed
    (raised, committed or promoted: [bz_ldrw]), every PAD swap's (bz_mat
    moved) and one frame in W4_EVERY; and THE BLANK (128.14.5.6): the card's
    mode port written with its video-enable bit (08h) CLEAR before every full
    write's first row (bz_row after bz_fullw's entry), still clear at its
    bz_presented, and set again by the next frame's bz_presented.  -> (fails,
    tallies)"""
    tag = g.tag
    start_replay(g, log, poke)
    flags = [r["i"] for r in ref.c.part["props"] if r["kind"] == BB.PK_CHECKPOINT and r["lane"]]
    lp = Loop(g, ("bz_t0", "bz_tf", "bz_presented", "bz_fullw", "bz_row"), io=MODE_PORT[tag])
    lp.arm()
    fails, tal = [], {"frames": 0, "checked": 0, "full": 0, "respawn": 0, "blank": 0, "capture": 0, "lip": 0,
                      "flag": 0, "pad": 0}
    dark, infull, rowseen, fullfr, lastfull = None, False, False, False, False
    nlip0 = g.w("bz_nlip") if "bz_nlip" in g.sym else 0
    mat0, flags0, hid0 = g.b("bz_mat"), None, 0
    while not fails:
        k = lp.next()
        if k == "io":
            dark = not (lp.r["ax"] & 0x08)
            continue
        if k == "bz_t0":
            if replay_end(g):
                break
            continue
        if k == "bz_fullw":
            infull, rowseen, fullfr = True, False, True
            continue
        if k == "bz_row":
            if infull and not rowseen:
                rowseen = True
                if dark is not True:
                    fails.append("%s frame %d: the full write's first row with the card's video ENABLED (the "
                                 "blank, SPEC.md 128.14.5.6: %s)" % (label, tal["frames"] + 1,
                                                                      "never written" if dark is None else "lit"))
            continue
        if k == "bz_tf":
            continue
        tal["frames"] += 1                    # bz_presented
        fr = tal["frames"]
        why = []
        if fullfr:
            tal["full"] += 1
            tal["respawn"] += fr > 1
            if dark is not True:
                fails.append("%s frame %d: the full write's frame presented with the video ENABLED (the blank, "
                             "SPEC.md 128.14.5.6)" % (label, fr))
            else:
                tal["blank"] += 1
            why.append("full")
        elif lastfull and dark:
            fails.append("%s frame %d: the frame after a full write presented still DARK (bz_unblank, SPEC.md "
                         "128.14.5.6)" % (label, fr))
        lastfull, fullfr, infull = fullfr, False, False
        hid = g.b("bz_hid") if "bz_hid" in g.sym else 0
        if hid and not hid0:
            why.append("capture")
        hid0 = hid
        nlip = g.w("bz_nlip") if "bz_nlip" in g.sym else 0
        if nlip != nlip0:
            why.append("lip")
        nlip0 = nlip
        lanes = g.lanes()
        fl = tuple(lanes.get(i) for i in flags)
        if flags0 is not None and fl != flags0:
            why.append("flag")
        flags0 = fl
        if g.b("bz_mat") != mat0:
            why.append("pad")
        mat0 = g.b("bz_mat")
        if not why and fr % W4_EVERY:
            continue
        S, R0, c0 = g.state()[:3]
        lk, bad = g.look(ref.c)
        if bad:
            fails.append("%s frame %d (%s) at bz_presented: %s" % (label, fr, "+".join(why) or "every", bad))
            break
        if "capture" in why and not lk.tube:
            fails.append("%s frame %d: the capture frame draws the ball (bz_hidn 0, SPEC.md 128.14.19 item 4)" % (
                label, fr))
        n, box = diff(g.decode(S), ref.picture(R0, c0, lk, g.view()))
        tal["checked"] += 1
        for w in why:
            if w in tal and w not in ("full",):
                tal[w] += 1
        if n:
            fails.append("%s frame %d (%s) at bz_presented: card != oracle: %d px, lines %d-%d, x %d-%d" % (
                label, fr, "+".join(why) or "every", n, *box))
    end_replay(g, label)
    return fails, tal


def w4_part(g, art=None):
    """MOON's shipped demo (a fall into the pit by flag 0, a RETURN, its three
    pads, the flags raised, the cup), then bonanzaphys's model-proved `cup-128`
    and `cup-lip` (PEAK: a capture from a neighbour, a lip-out's pop), each
    through w4_replay with the HUD OFF.  -> (fails, tallies by replay)"""
    import bonanza_phys as P
    m = g.m
    if "bz_hmode" in g.sym:
        m.pause()
        g.putb("bz_hmode", 0)
        m.run()
    fails, out = [], {}
    load_demo(g, CRS_K["moon"])
    f, out["moon"] = w4_replay(g, Ref(g.tag, course("moon"), art), "%s W4 MOON's demo" % g.tag)
    fails += f
    scen = {s["name"]: s for s in P.w4_replays() if s["name"] in ("cup-128", "cup-lip")}
    for name in ("cup-128", "cup-lip"):
        s = scen.get(name)
        if not s or not s["ok"]:
            fails.append("W4 %s: the model found no such approach on PEAK's cup (bonanza_phys --check)" % name)
            continue
        if fails:
            break
        log = make_log(s["keys"], CRS_K[s["crs"]], s["mat"])
        f, out[name] = w4_replay(g, Ref(g.tag, course(s["crs"]), art), "%s W4 %s" % (g.tag, name), log=log,
                                 poke=s["poke"])
        fails += f
    return fails, out


def w4_verdict(tag, out):
    """the W4 part's coverage: every kind it exists to see, seen and checked"""
    bad = []
    t = out.get("moon") or {}
    for k, need in (("capture", 1), ("flag", 1), ("pad", 1), ("full", 1)):
        if t and t.get(k, 0) < need:
            bad.append("W4 MOON's demo: %d %s frame(s) checked, at least %d (SPEC.md 128.14.14 bonanzaring)" % (
                t.get(k, 0), k, need))
    if t and t.get("blank", 0) < t.get("full", 0):
        bad.append("W4 MOON's demo: %d of %d full writes blanked" % (t.get("blank", 0), t.get("full", 0)))
    for name, k in (("cup-128", "capture"), ("cup-lip", "lip")):
        x = out.get(name)
        if x is not None and not x.get(k):
            bad.append("W4 %s: no %s frame checked" % (name, k))
    return bad


# ---- the HUD (only while the build carries it, SPEC.md 128.14.16 item 4) ------------------------------
def hud_leg(g, ref, mode, label, cmode=0):
    """MILL's route demo replayed (R) with [bz_hmode] MODE and [bz_cmode]
    CMODE: at bz_tf (the shown window, the last frame's picture) and at
    bz_presented (the new window, this frame's) the card equal to the oracle
    with the PANEL composed over the HUD's rect while it is on the card
    (bz_hwas at bz_tf, the panel last seen there; bz_hon at bz_presented,
    bz_hpan - itself checked equal to the host's render of bz_hdisp's tenths),
    on every frame with a HUD box of a kind not yet seen HUD_EACH times, every
    full write, the first HUD_EACH of each scroll direction with the panel on
    the card, every REST release and one frame in HUD_EVERY; and THE WRITE-ONCE
    CHECK on those frames: the rect's card bytes (at the old window and the
    new) under `mem` breakpoints from bz_tr to bz_presented, no byte receiving
    two DIFFERENT values in the frame.  OFF: the panel never on the card.
    -> (fails, tallies)"""
    import bonanza_game as GM
    m, tag = g.m, g.tag
    m.pause()
    g.putb("bz_hmode", mode)
    g.putb("bz_cmode", cmode)
    m.run()
    start_replay(g)
    lp = Loop(g, ("bz_t0", "bz_tr", "bz_tf", "bz_presented"))
    lp.arm()
    fails = []
    tal = {"frames": 0, "checked": 0, "tf": 0, "shown": 0, "kinds": {}, "dirs": {}, "rel": 0, "watched": 0,
           "five": 0}
    prev, pan_seen, rel0, want, watch = None, None, None, False, None
    while len(fails) < HUD_FAILS:
        k = lp.next()
        if k == "bz_t0":
            if replay_end(g):
                break
            continue
        if k == "mem":
            raw = m.read(VBASE[tag], 0x4000 if tag == "cga" else 0x8000)
            for a in watch["addrs"]:
                v = raw[a - VBASE[tag]]
                if v != watch["last"][a]:
                    watch["vals"][a].append(v)
                    watch["last"][a] = v
            continue
        if k == "bz_tr":
            hwk, hon, hwas = g.b("bz_hwk"), g.b("bz_hon"), g.b("bz_hwas")
            full = g.b("bz_full")
            dr, dc = g.s("bz_dr"), g.s("bz_dc")
            dk = ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
            nrel = g.w("bz_nhrel")
            rel = rel0 is not None and nrel != rel0
            rel0 = nrel
            kn = tal["kinds"].get(hwk, 0)
            dn = tal["dirs"].get(dk, 0)
            want = bool(full) or (hwk and kn < HUD_EACH) or rel or \
                (dk != (0, 0) and (hon or hwas) and dn < HUD_EACH) or (tal["frames"] + 1) % HUD_EVERY == 0
            if hwk:
                tal["kinds"][hwk] = kn + 1
            if dk != (0, 0) and (hon or hwas):
                tal["dirs"][dk] = dn + 1
            tal["rel"] += rel
            watch = None
            if want and (hon or hwas or full):
                rects = []
                for nm in ("bz_hnr", "bz_hor"):
                    rc = struct.unpack("<4h", m.read(g.a(nm), 8))
                    if rc not in rects:
                        rects.append(rc)
                addrs = sorted(set(a for rc in rects for a in card_addrs(g, rc)))
                if full:                    # the whole window is the full write's: a sentinel first
                    for a in addrs:
                        m.write(a, bytes([SENTINEL]))
                raw = m.read(VBASE[tag], 0x4000 if tag == "cga" else 0x8000)
                watch = {"addrs": addrs, "vals": {a: [] for a in addrs},
                         "last": {a: raw[a - VBASE[tag]] for a in addrs}}
                lp.arm(addrs)
                tal["watched"] += 1
            continue
        if k == "bz_tf":
            if want and prev is not None and not g.b("bz_full"):
                pS, pR0, pc0, plk, pview, phon = prev
                exp = ref.picture(pR0, pc0, plk, pview)
                if phon:
                    exp = with_panel(tag, exp, pan_seen)
                got = g.decode(pS)
                if phon and pan_seen is None:
                    got = with_panel(tag, got, None)
                n, box = diff(got, exp)
                tal["tf"] += 1
                if n:
                    fails.append("hud %s frame %d at bz_tf: the shown window is not the last frame's picture "
                                 "(the panel %s), card != oracle: %d px, lines %d-%d, x %d-%d" % (
                                     label, tal["frames"] + 1, "on" if phon else "off", n, *box))
            continue
        # bz_presented
        tal["frames"] += 1
        fr = tal["frames"]
        hon = g.b("bz_hon")
        tal["shown"] += hon
        if mode == 0 and (hon or g.b("bz_hwk")):
            fails.append("hud OFF frame %d: the panel on the card (bz_hon %d, bz_hwk %d)" % (fr, hon, g.b("bz_hwk")))
            break
        if watch:
            twice = {a: v for a, v in watch["vals"].items() if len(set(v)) > 1}
            if twice:
                a = sorted(twice)[0]
                fails.append("hud %s frame %d: card byte %05X received two values in one frame (%s; SPEC.md "
                             "128.14.14: no card byte receives two different values in a frame)" % (
                                 label, fr, a, ", ".join("%02X" % v for v in twice[a])))
            lp.arm()
            watch = None
        S, R0, c0 = g.state()[:3]
        lk, bad = g.look(ref.c)
        view = g.view()
        if bad:
            fails.append("hud %s frame %d at bz_presented: %s" % (label, fr, bad))
        if len(g.boxes5()) >= 5:
            tal["five"] += 1
        if want:
            exp = ref.picture(R0, c0, lk, view)
            if hon:
                pan = bytes(m.read(g.a("bz_hpan"), 24))
                hd = g.w("bz_hdisp")
                if pan != GM.panel(hd):
                    fails.append("hud %s frame %d: bz_hpan %s is not the panel for %d tenths %s" % (
                        label, fr, pan.hex(), hd, GM.panel(hd).hex()))
                exp = with_panel(tag, exp, pan)
                pan_seen = pan
            n, box = diff(g.decode(S), exp)
            tal["checked"] += 1
            if n:
                fails.append("hud %s frame %d at bz_presented: card != oracle (the panel %s): %d px, lines %d-%d, "
                             "x %d-%d" % (label, fr, "on" if hon else "off", n, *box))
        prev = (S, R0, c0, lk, view, hon)
    end_replay(g, "the HUD's %s leg" % label)
    m.pause()
    g.putb("bz_hmode", 0)
    g.putb("bz_cmode", 0)
    m.run()
    return fails, tal


def hud_scene(g, ref):
    """THE LANE UNDER THE PANEL (SPEC.md 128.14.5.5): play mode on MILL with
    the HUD FOLLOW and TRICKLE, a centred full write that puts a rotor or post
    under the shown rect (bonanza_wheel.hud_plan), the ball held and the lane
    made DUE every fourth frame ([bz_ldrw] poked one pose on): at every
    bz_presented the card equal to the oracle - the lane's cells OUTSIDE the
    rect its drawn pose's, the rect the panel - so the lane is never written
    over the panel by the wheel or the LEAD; its promotions REPORTED.
    -> (fails, tallies)"""
    import bonanza_wheel as WH
    m, tag = g.m, g.tag
    m.pause()
    g.putb("bz_hmode", 2)
    m.run()
    m.bp_exec(g.a("bz_launch"))
    g.key("Enter")
    assert m.wait_stop(60) == "breakpoint", "Enter did not reach bz_launch"
    g.putb("bz_crs", CRS_K["mill"])
    m.bp_exec()
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "the MILL play runs", guest=60)
    m.pause()
    g.putb("bz_cmode", 1)
    plan, dims = WH.hud_plan(g, ref.c)
    fails, tal = [], {"frames": 0, "under": 0, "due": 0, "promo": 0}
    if plan is None:
        tal["skip"] = ("no rotor or post of MILL can be put under the rect by a centred window (H, W, rmax, cmax "
                       "%s)" % (dims,))
    else:
        lane, R0w, c0w, cen = plan
        poses = [r for r in ref.c.part["props"] if r["i"] == lane][0]["lane"]["poses"]
        names = ("bz_t0", "bz_presented") + (("bz_props.promo",) if "bz_props.promo" in g.sym else ())
        lp = Loop(g, names)
        lp.arm()
        k0 = 0
        while tal["frames"] < HUD_SCENE + 3 and not fails:
            k = lp.next()
            if k == "bz_t0":
                k0 += 1
                if k0 == 1:
                    poke_ball(g, cen[0], cen[1], cen[2], 0, 0, 0, air=1)
                    g.putb("bz_first", 1)
                else:
                    poke_ball(g, cen[0], cen[1], cen[2], 0, 0, 0, air=1, same_cell=k0 > 3)
                    if k0 > 3 and k0 % 4 == 0:
                        pose = m.read(g.a("bz_ldrw") + lane, 1)[0]
                        m.write(g.a("bz_ldrw") + lane, bytes([(pose + 1) % poses]))
                        tal["due"] += 1
                continue
            if k == "bz_props.promo":
                tal["promo"] += 1
                continue
            tal["frames"] += 1
            if k0 < 3:
                continue
            S, R0, c0 = g.state()[:3]
            hon = g.b("bz_hon")
            tal["under"] += hon and (R0, c0) == (R0w, c0w)
            lk, bad = g.look(ref.c)
            if bad:
                fails.append("hud lane scene frame %d: %s" % (tal["frames"], bad))
                break
            exp = ref.picture(R0, c0, lk, g.view())
            if hon:
                exp = with_panel(tag, exp, bytes(m.read(g.a("bz_hpan"), 24)))
            n, box = diff(g.decode(S), exp)
            if n:
                fails.append("hud lane scene frame %d (lane %d under the rect at R0 %d c0 %d): card != oracle: "
                             "%d px, lines %d-%d, x %d-%d" % (tal["frames"], lane, R0, c0, n, *box))
        if not fails and not tal["under"]:
            fails.append("hud lane scene: the panel was never on the card over lane %d (R0 %d c0 %d asked)" % (
                lane, R0w, c0w))
    m.bp_exec()
    g.putb("bz_cmode", 0)
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the lane scene's play ends on Esc", guest=60)
    dropped(g, "the lane scene")
    m.pause()
    g.putb("bz_hmode", 0)
    m.run()
    return fails, tal


def hud_part(g, art=None, legs=True):
    """the HUD's legs (only while the build carries it): MILL's route demo with
    the HUD FOLLOW, REST (GLIDE and TRICKLE) and OFF (LEGS False: none), then
    the lane scene.  -> (fails, tallies)"""
    if "bz_hmode" not in g.sym:
        print("%s hud: the build carries no HUD (SPEC.md 128.14.16 item 3): its checks are not asserted" % g.tag,
              flush=True)
        return [], {}
    ref = Ref(g.tag, course("mill"), art)
    fails, out = [], {}
    if legs:
        load_demo(g, CRS_K["mill"])
    for mode, cmode, label in ((2, 0, "FOLLOW"), (1, 0, "REST GLIDE"), (1, 1, "REST TRICKLE"),
                               (0, 0, "OFF")) if legs else ():
        f, out[label] = hud_leg(g, ref, mode, label, cmode)
        fails += f
        t = out[label]
        print("%s hud %s: %d frames, the panel shown on %d, %d checked at bz_presented and %d at bz_tf, %d watched "
              "write-once, boxes %s, scroll directions %d, releases %d, five-box frames %d: %s" % (
                  g.tag, label, t["frames"], t["shown"], t["checked"], t["tf"], t["watched"],
                  ", ".join("%s %d" % (HK_NAMES.get(k, k), v) for k, v in sorted(t["kinds"].items()) if k) or "none",
                  len(t["dirs"]), t["rel"], t["five"], "yes" if not f else "NO"), flush=True)
        if fails:
            return fails, out
    f, out["scene"] = hud_scene(g, ref)
    fails += f
    t = out["scene"]
    print("%s hud lane scene: %s" % (g.tag, t.get("skip") or "%d frames, %d with the panel over the lane, the lane "
                                     "made due %d times, %d promotion(s): %s" % (
                                         t["frames"], t["under"], t["due"], t["promo"], "yes" if not f else "NO")),
          flush=True)
    return fails, out


def hud_verdict(tag, out):
    bad = []
    if not out:
        return bad
    fo = out.get("FOLLOW") or {}
    if fo:
        if fo["kinds"].get(1, 0) == 0:
            bad.append("hud FOLLOW: no union box checked (SPEC.md 128.14.14)")
        if len(fo["dirs"]) < 8:
            bad.append("hud FOLLOW: %d of the eight scroll directions checked with the panel on the card" %
                       len(fo["dirs"]))
        if not fo["watched"]:
            bad.append("hud FOLLOW: no frame's rect watched for the write-once check")
    for lab in ("REST GLIDE", "REST TRICKLE"):
        r = out.get(lab) or {}
        if r and not (r["kinds"].get(3) and r["kinds"].get(4)):
            bad.append("hud %s: no HIDE and SHOW both checked (boxes %s)" % (lab, r["kinds"]))
    sc = out.get("scene") or {}
    if sc.get("skip") and tag == "cga":
        bad.append("hud lane scene: %s" % sc["skip"])
    return bad


# ---- the red arms and their private trees ----------------------------------------
def build_tree(td, patches, size=360, src0=None, art=None, name="bonanza", appdata=True, extra=()):
    """apps/bonanza/ copied into TD, PATCHES [(file, old, new), ...] applied
    (each OLD must occur exactly once - a red arm whose anchor moved says so),
    and the package and a floppy of SIZE KB built there from the current art -
    with SYSTEM\\APPDATA as the Makefile's bonanza*.img recipes build it
    ($(APPDATAFOLDER), SPEC.md 128.14.3.3) unless APPDATA is False (the
    `noappdata` red arm's image), and EXTRA more os88disk.py operands
    ('[DIR/..:]PATH'). -> (source dir, image)."""
    src = os.path.join(td, name)
    shutil.copytree(src0 or os.path.join(ROOT, "apps", "bonanza"), src)
    patch_tree(src, patches)
    art = art or at("build/bonanza-art")
    binp, o88, img = (os.path.join(td, n) for n in ("bonanza.bin", "BONANZA.O88", "%s%d.img" % (name, size)))
    assemble(src, art, binp)
    subprocess.run(["python3", "tools/os88pkg.py", "--compress-if=lz4", binp, "-o", o88] + part_args(art, src),
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["python3", "tools/os88disk.py", "-o", img, "--size", str(size), o88] + list(extra)
                   + (["--folder", "SYSTEM/APPDATA"] if appdata else []), cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    return src, img


def disk(td, files=(), size=360, appdata=True, name="bz", o88=None):
    """a floppy of SIZE KB holding the SHIPPED build/bonanza.o88 (the same
    package bonanzadisk ships; O88 another, a red tree's), FILES more os88disk.py operands
    ('[DIR/..:]PATH': a row's hostile BONANZA.DAT or demo files), and
    SYSTEM\\APPDATA unless APPDATA is False.  -> its path"""
    img = os.path.join(td, "%s%d.img" % (name, size))
    subprocess.run(["python3", "tools/os88disk.py", "-o", img, "--size", str(size), o88 or at("build/bonanza.o88")]
                   + list(files) + (["--folder", "SYSTEM/APPDATA"] if appdata else []), cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    return img


def disk_b(ui):
    """B:'s Disk window, raised: the ACTING one when [fm_vinst] still names a
    live instance, else the newest visible file window showing drive B.
    After W and L the chooser leaves [fm_vinst] naming BONANZA's instance, and
    once that window closes os88ui.disk_window() raises (the final pass of
    wave 4: bonanzaexit and bonanzademo's double-click legs)"""
    try:
        return ui.raise_window(ui.disk_window())
    except os88ui.UIError:
        pass
    for w in reversed(ui.windows()):
        fs = ui.fs_of(w)
        if fs is not None and fs[0] == 1 and w.visible:
            return ui.raise_window(w)
    raise os88ui.UIError("no Disk window shows B: (open: %r)" % (ui.titles(),))


def patch_tree(src, patches):
    for f, old, new in patches:
        p = os.path.join(src, f)
        t = open(p).read()
        assert t.count(old) == 1, "the red anchor in %s moved (%d matches): re-anchor the red arm" % (
            f, t.count(old))
        open(p, "w").write(t.replace(old, new))


def assemble(src, art, binp):
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", src + "/",
                    "-I", art + "/", "-o", binp, os.path.join(src, "bonanza.asm")], cwd=ROOT, check=True)


def part_args(art, src=None):
    """The --part list in the Makefile's BZ_PARTS order (SPEC.md 128.11.3.1):
    rows 0 - 2 the rubber, steel and glass balls, then course K's one part
    (bzcourse.inc's BZ_NCRS of them), then - where SRC's package carries
    them - the sound part and one part a song (SPEC.md 128.20.3)."""
    n = int(re.search(r"^BZ_NCRS\s+equ\s+(\d+)", open(os.path.join(art, "bzcourse.inc")).read(), re.M).group(1))
    files = list(A.BALL_FILES) + ["BZ%d.BIN" % k for k in range(n)]
    asm = open(os.path.join(src or os.path.join(ROOT, "apps", "bonanza"), "bonanza.asm")).read()
    if "BZS_NSONG" in asm:
        ns = int(re.search(r"^BZS_NSONG\s+equ\s+(\d+)", open(os.path.join(art, "bzsnd.inc")).read(),
                           re.M).group(1))
        files += ["BZSND.BIN"] + ["BZM%d.BIN" % i for i in range(ns)]
    if "BZ_NDEMO" in asm:                       # wave 4: one shipped demo a tour course, after the
        files += ["BZD%d.BIN" % k for k in range(1, n)]     # songs (SPEC.md 128.14.7.4, 128.14.22 item 7)
    out = []
    for p in files:
        out += ["--part", os.path.join(art, p)]
    return out


def check_reds(reds, label):
    """the HOST half of a red arm: every patch's anchor is still there once, and
    the broken copy ASSEMBLES (nasm -w+error into a temporary file).  -> lines"""
    out = []
    art = at("build/bonanza-art")
    for name, patches in sorted(reds.items()):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "bonanza")
            shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
            try:
                patch_tree(src, patches)
            except AssertionError as e:
                raise AssertionError("%s --red %s: %s" % (label, name, e))
            assemble(src, art, os.path.join(td, "bonanza.bin"))
            out.append("%s --red %s: anchors found, the broken copy assembles (%d bytes)" % (
                label, name, os.path.getsize(os.path.join(td, "bonanza.bin"))))
    return out


# the pass's six map stores (bz_wprect.col and .sl, the CGA's and the Hercules' column writers' block heads
# and tails): `mapskip` leaves each out
MAPSKIP = [
    ("    mov [bx], si                ; ...into the map\n    add si, [bp + 8]            ; SI",
     "    nop                         ; RED mapskip\n    nop\n    add si, [bp + 8]            ; SI"),
    ("    mov si, [si]\n    mov [bx], si\n    jmp short .s2\n",
     "    mov si, [si]\n    nop                         ; RED mapskip\n    nop\n    jmp short .s2\n"),
    ("    mov si, [ds:bp]             ; the block's pose word (BP would be SS's)\n"
     "    mov [bx], si                ; ...into the map\n",
     "    mov si, [ds:bp]             ; the block's pose word (BP would be SS's)\n"
     "    nop                         ; RED mapskip\n    nop\n"),
    ("    inc cx\n    mov si, [ds:bp]\n    mov [bx], si\n    jmp short .disp\n",
     "    inc cx\n    mov si, [ds:bp]\n    nop                         ; RED mapskip\n    nop\n    jmp short .disp\n"),
    (".blk:\n    mov si, [ds:bp]\n    mov [bx], si\n.c2:\n",
     ".blk:\n    mov si, [ds:bp]\n    nop                         ; RED mapskip\n    nop\n.c2:\n"),
    ("    inc cx\n    mov si, [ds:bp]\n    mov [bx], si\n    jmp short .c1\n",
     "    inc cx\n    mov si, [ds:bp]\n    nop                         ; RED mapskip\n    nop\n    jmp short .c1\n"),
]
COLFIRST_TV = ("    mov bx, BZ_PWHEEL * 4       ; (the wheel's part: appended, so the wave-2\n"
               "bz_tv:                          ; parts keep their numbers)\n    call bz_mark\n")
COLFIRST_COL = ".lit:\n    mov ax, [bz_dc]\n    or ax, ax\n    jz bz_tb\n"
REDS = {
    # the entering column moving right: the window's column W (not W - 1)
    "colright": [("bzgame.inc", "    add ax, [bz_W]              ; moving right: the right edge's\n    dec ax\n",
                  "    add ax, [bz_W]              ; moving right: the right edge's\n")],
    # the entering column before the retrace and the flip: the same bytes in the end
    "colfirst": [("bzgame.inc", COLFIRST_TV, COLFIRST_TV +
                  "    cmp byte [bz_full], 0\n    jne .redskip\n    mov ax, [bz_dc]\n    or ax, ax\n"
                  "    jz .redskip\n    mov ax, [bz_c0n]\n    js .redl\n    add ax, [bz_W]\n    dec ax\n"
                  ".redl:\n    xor bx, bx\n    mov cx, [bz_H]\n    call bz_col\n.redskip:\n"),
                 ("bzgame.inc", COLFIRST_COL, ".lit:\n    jmp bz_tb\n")],
    # every frame counted late: the bz_rlate assertion's own red
    "late": [("bzgame.inc", "bz_presented:\n    call bz_mark\n",
              "bz_presented:\n    call bz_mark\n    inc word [bz_late]\n")],
    # SPEC.md 128.9 item 6's order undone: a box at window row 0 takes the WHOLE column first
    # (still flagged a row-0 box, so bz_latechk times it from line 0 and sees the beam overtake it)
    "row0": [("bzgame.inc", "    inc ax\n    mov byte [bz_row0], 1\n.mono:\n",
              "    inc ax\n    mov byte [bz_row0], 1\n    mov ax, [bz_H]              ; RED row0: the whole column first\n"
              ".mono:\n")],
    # the occluder pass skipped: the ball is drawn over what should hide it
    "occ": [("bzvideo.inc", "bz_occ:\n    cmp byte [bz_ogate], 0\n",
             "bz_occ:\n    ret                         ; RED occ\n    cmp byte [bz_ogate], 0\n")],
    # the shadow composed into its own box only (group 1), never into the ball's
    "shadow": [("bzvideo.inc", "    cmp byte [bz_snv], 0\n    je .ball\n    mov ax, [bz_spy]\n",
                "    cmp byte [bz_snv], 0\n    je .ball\n    cmp byte [si + 18], 1       ; RED shadow: its own box only\n"
                "    jne .ball\n    mov ax, [bz_spy]\n")],
    # every box before any column row (the splits all 0, the column after the last box)
    "boxfirst": [("bzgame.inc", "    mov cx, [bz_csp]\n    ret\n.whole:\n",
                  "    xor cx, cx                  ; RED boxfirst: no column row before any box\n"
                  "    mov [bz_csp], cx\n    mov [bz_csp + 2], cx\n    mov [bz_csp + 4], cx\n"
                  "    mov [bz_csp + 6], cx\n    ret\n.whole:\n")],
    # one bit of bz_hgen's output flipped: BZ_HTAB[0][55h], solid cyan on an even line
    "htab": [("bonanza.asm", "    xor al, bh                  ; AL = b ^ ((b ^ P) & m)\n    mov [di], al\n",
              "    xor al, bh                  ; AL = b ^ ((b ^ P) & m)\n    cmp di, bz_boxbuf + 55h     ; RED htab\n"
              "    jne .redh\n    xor al, 1\n.redh:\n    mov [di], al\n")],
    # bz_latechk on the first box only (both of its checks skipped for every later box)
    "late2": [("bzgame.inc", ".t:\n    inc dh\n",
               ".t:\n    or di, di                   ; RED late2: the first box only\n    jnz .wr\n    inc dh\n")],
    # the occluder pass run once per box (inside the compose loop) instead of once a frame
    "pass2": [("bzgame.inc", "    call bz_boxc                ; the course, the shadow, the sprite\n"
               "    add si, BZ_BOXD\n    loop .comp\n    call bz_occ ",
               "    call bz_boxc                ; the course, the shadow, the sprite\n"
               "    call bz_occ                 ; RED pass2: a walk a box\n"
               "    add si, BZ_BOXD\n    loop .comp\n    nop                         ;")],
    # wave 3 (SPEC.md 128.12.13.2).  The contact choice and the wheel's box test both taken
    # out: a due lane beside the ball is the wheel's, committed over the ball's box
    "contact": [("bzwheel.inc", "    call bz_lfoot               ; ...a contact candidate ...\n    jnc .wheel\n",
                 "    call bz_lfoot               ; ...a contact candidate ...\n"
                 "    jmp .wheel                  ; RED contact: never a contact, always the wheel's\n"),
                # ...and the wheel's box filter (SPEC.md 128.12.4.2, the review's W1) gone with it, or
                # the wheel would drop every such candidate and the arm stay green
                ("bzwheel.inc", "    call bz_wboxm               ; meeting a box: never the wheel's\n    jnc .pk\n",
                 "    jmp short .pk               ; RED contact: no box filter\n")],
    # a WAITING contact lane's map words synced anyway: a box draws its new pose
    # inside, and the old stays on the card outside it
    "defer": [("bzwheel.inc", "    jnc .wheel\n    inc byte [bz_ccnt]\n",
               "    jnc .wheel\n    push ax                     ; RED defer: every contact candidate synced\n"
               "    mov al, [bz_ltru + bx]\n    call bz_lsync\n    pop ax\n    inc byte [bz_ccnt]\n")],
    # wave 3b (SPEC.md 128.13.12).  The RIDE BOX composed without the slab's layer under the ball (bz_pblit
    # skipped when the platform's box merged into the ball's group): the card loses the slab under the ball
    "ridebox": [("bzvideo.inc", "    cmp byte [bz_pov], 0\n    jne .shadow\n    call bz_pblit\n",
                 "    cmp byte [bz_pov], 0\n    jne .shadow\n    cmp byte [bz_ctype], 2       ; RED ridebox: no slab "
                 "under a ride box\n    jne .rpb\n    cmp word [bz_cgr], 0\n    je .shadow\n.rpb:\n    call bz_pblit\n")],
    # the wait's "never two running" taken out: the slab waits on EVERY crowded frame, its drawn line falls
    # behind, and the box drawn at the PWAIT scene's end is past 30 lines (past BZ_BOXL: the box-size check)
    "pwait2": [("bzwheel.inc", "    mov al, [bz_pylp]           ; (which WAITS a frame - never two running,\n",
                "    xor al, al                  ; RED pwait2: it waits two running\n")],
    # the whole-row path taken on a row that crosses the ring's end (bz_bwrows's tail no longer stops
    # there): the crossing row written down the unrolled block, past 2000h
    "fastwrap": [("bzvideo.inc", "    cmp dx, bx\n    ja .fx                      ; (it crosses the ring's end: bz_wseg's)\n",
                  "    nop                         ; RED fastwrap: no crossing test\n")],
    # the pass's map store left out (every `mov [bx], si` of bz_wprect and its column writers): a whole
    # commit's map keeps the old pose - oracle check 5
    "mapskip": [("bzwheel.inc", o, n) for o, n in MAPSKIP],
    # the pass's row-at-a-time path (a column across the ring's end) without its mask: the rows past 2000h
    # land in the wrong bank (the review of wave 3b, P1) - a `wrapcommit` frame, MILL's post 4 on the Hercules
    "wrapmask": [("bzwheel.inc", "    push ax\n    and di, 1fffh\n    call word [bp + 18]\n",
                  "    push ax                     ; RED wrapmask: no mask\n    call word [bp + 18]\n")],
    # the platform (the lift) always UNDER the ball
    "padfront": [("bzwheel.inc", "    cmp ax, cx\n    jge .out\n    mov byte [bz_pov], 1\n",
                  "    cmp ax, cx\n    jge .out\n    mov byte [bz_pov], 0        ; RED padfront: never over\n")],
    # wave 4 (SPEC.md 128.14.14).  The HUD's inset taken to 0: an entering row writes the panel's cells and
    # the HUD's box writes them again with a different value (the write-once check, a FOLLOW scroll frame)
    "hudinset": [("bzhud.inc", "    mov dx, [bz_rl]\n    shl dx, 1\n    neg dx\n"
                  "    add dx, BZ_LINES - 6        ; DX = the rect's first window line\n",
                  "    mov dx, BZ_LINES - 6        ; RED hudinset: no inset\n")],
    # FOLLOW's step without the old rect: the panel left behind where it was (the oracle at bz_presented)
    "hudold": [("bzhud.inc", "    mov si, bz_hor              ; every layer, the panel over the new\n",
                "    mov si, bz_hnr              ; RED hudold: the old rect not restored\n")],
    # the wheel's HUD-rect test removed: a commit writes the lane over the panel (the lane scene's oracle)
    "hudlane": [("bzwheel.inc", "    cmp byte [bz_hxon], 0       ; THE HUD's SHOWN RECT is a box to the wheel\n"
                 "    je .nh                      ; and the LEAD on every frame it is on the\n",
                 "    jmp short .nh               ; RED hudlane: the rect is no box to the wheel\n")],
    # the full write's span skip removed while shown: the rect gets the course, then the panel (two values)
    "hudfull": [("bzgame.inc", "    cmp byte [bz_hon], 0\n    je .whole\n",
                 "    jmp short .whole            ; RED hudfull: the rect's words written too\n")],
    # the blank left out: the mode port written with its enable bit SET at a full write (the W4 replays)
    "noblank": [("bzgame.inc", "    mov al, 22h\n    mov byte [bz_blk], 1\n",
                 "    mov al, 2ah                 ; RED noblank: the video left enabled\n    mov byte [bz_blk], 1\n")],
    # the ball DRAWN in a transit: its new footprint boxed and its sprite composed
    "hidden": [("bzgame.inc", "    cmp byte [bz_hidn], 0       ; a HIDDEN ball (in a tube, or holed) has no\n"
                "    jne .hid                    ; new footprint: its old one alone, restored\n",
                "    nop                         ; RED hidden: a hidden ball boxed as any\n"),
               ("bzvideo.inc", "    cmp byte [bz_hidn], 0\n    jne .nob\n    mov ax, [bz_py]\n",
                "    mov ax, [bz_py]             ; RED hidden: its sprite composed in a tube\n")],
}
RED_PARTS = {"colright": ("bench",), "colfirst": ("bench",), "late": ("bench",), "row0": ("probe",),
             "occ": ("bench",), "shadow": ("trial",), "boxfirst": ("trial",), "htab": ("glass",),
             "late2": ("probe",), "pass2": ("trial",), "contact": ("mill", "play"), "defer": ("play",),
             "ridebox": ("play",), "pwait2": ("play",), "fastwrap": ("play",), "mapskip": ("mill",),
             "wrapmask": ("mill", "play"),
             "padfront": ("play",), "hidden": ("mill",),
             "hudinset": ("hud",), "hudold": ("hud",), "hudlane": ("hudscene",), "hudfull": ("hud",),
             "noblank": ("w4",)}
HUD_REDS = ("hudinset", "hudold", "hudlane", "hudfull")     # asserted only while the HUD is built
# ...the cards each CAN go red on: the Hercules has 16 + 82 lines of sync and
# blank (~24.7k clocks) before its window's line 0, so the WHOLE column (at
# most ~22k on the benchmark) fits ahead of a row-0 box there and item 6's
# order is the CGA's alone to need (the final pass of wave 1 measured row0 at
# 11 late boxes of 11 on the CGA, 0 of 7 on the Hercules); a later box is late
# on the CGA alone for the same reason; and the table is the Hercules's
RED_TAGS = {"row0": ("cga",), "late2": ("cga",), "htab": ("herc",), "wrapmask": ("herc",)}
# ...and what each must go red FOR: a red arm that fails for another reason
# proves nothing about the check it is the arm of
RED_WANT = {"colright": "at bz_presented", "colfirst": "at bz_tf", "late": "bz_rlate", "row0": "FIRST box",
            "occ": " LAID ", "shadow": "card != oracle", "boxfirst": "RASTER ORDER",
            "htab": "card memory != the course", "late2": "cycle counter", "pass2": "walk entered",
            "contact": "at bz_tf", "defer": "(defer", "padfront": "pover", "hidden": "transit",
            "ridebox": "ridebox) at bz_presented", "pwait2": "waited two frames running", "fastwrap": "wrapbox) at bz_presented",
            "mapskip": "oracle check 5", "wrapmask": "wrapcommit",
            "hudinset": "two values", "hudold": "at bz_presented", "hudlane": "lane scene", "hudfull": "two values",
            "noblank": "blank"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--part", choices=PARTS, action="append",
                    help="run only these parts (default all six)")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check-reds", action="store_true",
                    help="the host half only: every red arm's anchors found and its broken copy assembles")
    a = ap.parse_args()
    if a.check_reds:
        for line in check_reds({k: v for k, v in REDS.items() if k not in HUD_REDS or "bz_hmode" in symbols()},
                               "bonanza_ring"):
            print(line)
        return
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.red:
        if a.red in HUD_REDS and "bz_hmode" not in symbols():
            print("bonanza_ring --red %s: the build carries no HUD, so its check is not asserted (SPEC.md "
                  "128.14.16 item 4) - nothing to run" % a.red)
            return
        tags = tuple(t for t in tags if t in RED_TAGS.get(a.red, tags)) or RED_TAGS.get(a.red, tags)
        with tempfile.TemporaryDirectory() as td:
            src, img = build_tree(td, REDS[a.red])
            for tag in tags:
                try:
                    r = run(tag, apps=img, src=src, parts=RED_PARTS[a.red])
                    bad = verdict(tag, r)
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(RED_WANT[a.red] in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (
                        a.red, tag, RED_WANT[a.red], bad)
                print("bonanza_ring --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_ring --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    parts = tuple(a.part) if a.part else PARTS
    allbad = []
    for tag in tags:
        bad = verdict(tag, run(tag, parts=parts))
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d ring failure(s)" % len(allbad)
    print("bonanza_ring (%s): PASS" % ", ".join(tags))


if __name__ == "__main__":
    main()
