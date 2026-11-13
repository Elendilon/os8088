#!/usr/bin/env python3
"""BONANZA: the two-way ring on MartyPC's CGA and Hercules (SPEC.md 128.2, 128.8, 128.10.11, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_ring.py [--adapter cga|herc|both] [--part glass|bench|trial|mill|play|probe]
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
     commit meets the ball's old footprint - and at each tube's exit the
     ball's footprint inside the window.  THE MILL PLAY: the ball poked onto
     the slab and ridden (the slab's layer in the riding ball's box), then
     poked under it in its shaft (the slab OVER the ball).
  6  The row-0 probe's frames are HEAVY now (a poke runs the occluder pass:
     level 1, no column), so its ball sits within the edge clause's 24 px of
     the right edge (PROBE_EDGE), and the frame BEFORE each split frame puts
     it 40 px back.

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
             ball still on the glass - at bz_tf (the MILL leg)
  defer      a WAITING contact lane's map words synced anyway: its new pose in
             the box, the old outside it - a `defer` frame (the MILL leg)
  padfront   the platform never over the ball: a `pover` frame (the MILL play)
  hidden     the ball boxed and drawn in a transit: a `transit` frame

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
FILES = ("bonanza.asm", "bzvideo.inc", "bzgame.inc", "bzwheel.inc", "bzphys.inc")
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
              ("bz_exitchk", "leave"))
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
        names += re.findall(r"^VAR (bz_\w+),", t, re.M)
        names += re.findall(r"^(bz_\w+):", t, re.M)
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
        lk.tube = f("bz_tube", "B") if "bz_tube" in self.sym else 0
        lk.spr = BB.sprite(lk, self.tag == "herc")
        if lk.tube:                              # hidden in a tube: no sprite, no shadow
            lk.gate, lk.spy = False, None
            return lk, ("the guest drew a shadow ([bz_snv] 1) for a ball hidden in a tube"
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
        extra += ("bz_wcommit",)
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
    fview = None
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
            continue
        if k == "tf":
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
                fview = mill_feats(g, ref, commits, ndef0, dk)
                ndef0 = g.w("bz_ndef")
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
            if want:
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
        if mill:
            if any(c[0] == "lead" for c in commits):        # the LEAD is after bz_tf
                wk.feats = tuple(wk.feats) + ("lead",)
                seen["lead"] += 1
                want = want or feat["lead"] < FEAT_EACH
            if lk.tube:
                wk.feats = tuple(wk.feats) + ("transit",)
                seen["transit"] += 1
                want = want or feat["transit"] < FEAT_EACH
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
                                 " [%s]" % "+".join(getattr(wk, "feats", ())) if mill else "",
                                 *st, lk.sb, lk.zb, lk.air, lk.spr, lk.spy, n, *box))
            elif controls is None and wk.dk[0] and wk.dk[1] and not wk.full:
                ref.view = view
                try:
                    controls = negative_controls(g, ref, st, lk)
                finally:
                    ref.view = None
            want = False
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
    print("%s %s boxes a frame %s; late boxes (bz_rlate) %s" % (
        tag, leg, ", ".join("%d: %d" % kv for kv in sorted(nbox_seen.items())), late), flush=True)
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
            "shdin": shdin_checked, "feat": feat, "seen": seen, "exits": exits}


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
              "transit")
PLAY_FEATS = ("ride", "pover")
LOW_FEATS = ("ahead", "behind", "lead")     # the play's LOW scenario's: they count for the MILL leg's
FEAT_EACH = 3
# the LEAD on the Hercules: a wheel reckoned from a wait that SAW the rise
# reaches every window line there, so a lead follows only a wait that found
# the sync already high (SPEC.md 128.12.5.3) - reported on that card, required
# on the CGA
# and a lane entering in a COLUMN on the Hercules: its 45-word window holds every MILL lane's columns
# whatever c0 (cmax 19, the lanes in columns 21 - 35), so no column ever brings one in there (the final
# pass) - reported on that card
FEAT_OPTIONAL = {"herc": ("lead", "enter_col"), "cga": ()}

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
    for i in sorted(rects):
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


def mill_feats(g, ref, commits, ndef0, dk):
    """at bz_tf: the features of SPEC.md 128.12.13.2's MILL leg this frame has"""
    out = set(c[0] for c in commits if c[0] in ("ahead", "behind"))
    ct = g.b("bz_ctype")
    if ct == 1:
        kind = ref.c.part["props"][g.b("bz_cln")]["kind"]
        out.add("crotor" if kind == BB.PK_WINDMILL else "cpost")
    elif ct == 2:
        out.add("pbox")
    elif ct == 3:
        out.add("pclip")
    if g.w("bz_ndef") != ndef0:
        out.add("defer")
    # a wheel commit meeting the ball's or the shadow's OLD footprint, still on the
    # glass at bz_tf: never one in a right build (such a lane is a contact candidate,
    # SPEC.md 128.12.4.2), and the frame the `contact` red erases the ball on - so
    # every such frame is checked, not FEAT_EACH of them
    if commits and g.b("bz_oldv"):
        olds = [struct.unpack("<4H", g.m.read(g.a("bz_ofx0"), 8))]
        if g.b("bz_sov"):
            olds.append(struct.unpack("<4H", g.m.read(g.a("bz_sox0"), 8)))
        rects = lane_rects(ref.c)
        for kind, lane in commits:
            if kind not in ("ahead", "behind") or lane not in rects:
                continue
            col, brow, w, h = rects[lane][:4]
            for x0, x1, y0, y1 in olds:
                if col <= x1 and x0 < col + w and 8 * brow <= y1 and y0 < 8 * (brow + h):
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


def mill_play(g, ref):
    """the MILL leg's POKED play (SPEC.md 128.12.13.2): Enter on MILL ([bz_crs]
    poked at bz_launch), the ball poked onto the platform's slab at the first
    bz_t0 (the frame's centred full write puts the window round it) and left
    to RIDE with no key held - every riding frame whose ball box meets the slab
    checked (its layer in the ball's box) - then poked UNDER the slab, in its
    shaft, at each frame's bz_t0 for OVER_FRAMES frames: the slab drawn OVER it
    ([bz_pov] 1), checked.  The card equals the oracle at bz_tf and
    bz_presented on every checked frame.  -> (failures, {feature: frames checked})"""
    m, tag, crs = g.m, g.tag, ref.c
    P = plat_rec(crs)
    fails, cnt = [], {f: 0 for f in PLAY_FEATS}
    if P is None:
        return ["MILL has no platform"], cnt
    m.bp_exec(g.a("bz_launch"))
    g.key("Enter")
    assert m.wait_stop(60) == "breakpoint", "Enter did not reach bz_launch"
    g.putb("bz_crs", CRS_K["mill"])
    g.putb("bz_hvoff", 0)
    wk = Walker(g, t0=True, extra=("bz_wcommit",))
    wk.arm()
    frames, prev, phase = 0, None, "ride"
    plan, commits = None, []
    for f in LOW_FEATS:
        cnt[f] = 0
    while frames < RIDE_FRAMES + OVER_FRAMES + LOW_FRAMES:
        k = wk.next()
        if k == "bz_wcommit":
            commits.append(commit_kind(g, wk.r))
            continue
        if k == "t0":
            n = g.d("bz_nstep")
            if frames == 0:
                slab_ball(g, P, n, 0, 0, True)
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
            if prev is not None and not g.b("bz_full") and (phase in ("over", "low") or frames % 10 == 0):
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
        if phase == "over" and meets and slab[2]:
            feats.append("pover")
        if phase == "low":
            feats += sorted(set(c[0] for c in commits if c[0] in LOW_FEATS))
        commits = []
        if feats or frames % 10 == 0 or phase == "low":
            n_, box = diff(g.decode(st[0]), ref.picture(st[1], st[2], lk, view))
            for f in feats:
                cnt[f] += 1
            if n_:
                fails.append("MILL play frame %d (%s%s) at bz_presented, card != oracle: S %d R0 %d c0 %d ball "
                             "%d,%d (z_b %d air %d, slab %s): %d px, lines %d-%d, x %d-%d" % (
                                 frames, phase, " " + "+".join(feats) if feats else "", *st, lk.zb, lk.air, slab,
                                 n_, *box))
        prev = (st, lk, view)
        if len(fails) >= 4:
            break
    m.bp_exec()
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the MILL play ends on Esc", guest=60)
    dropped(g, "the MILL play")
    print("%s MILL play: the ball poked onto the slab and ridden %d frames, then under it %d: frames checked with "
          "the slab's layer in the riding ball's box %d, with the slab OVER the ball %d; then THE LOW SCENARIO "
          "(post %s at window line %d, %d frames): checked frames with a wheel commit AHEAD %d, BEHIND %d, a LEAD "
          "%d; card = oracle: %s" % (
              tag, RIDE_FRAMES, OVER_FRAMES, cnt["ride"], cnt["pover"], plan[0] if plan else None, LOW_F, LOW_FRAMES,
              cnt["ahead"], cnt["behind"], cnt["lead"], "yes" if not fails else "NO"), flush=True)
    return fails, cnt


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


PARTS = ("glass", "bench", "trial", "mill", "play", "probe")


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
            if not r["play"][f]:
                bad.append("MILL play: no checked frame with %s (SPEC.md 128.12.13.2)" % f)
    return bad


# ---- the red arms and their private trees ----------------------------------------
def build_tree(td, patches, size=360, src0=None, art=None, name="bonanza"):
    """apps/bonanza/ copied into TD, PATCHES [(file, old, new), ...] applied
    (each OLD must occur exactly once - a red arm whose anchor moved says so),
    and the package and a floppy of SIZE KB built there from the current art.
    -> (source dir, image)."""
    src = os.path.join(td, name)
    shutil.copytree(src0 or os.path.join(ROOT, "apps", "bonanza"), src)
    patch_tree(src, patches)
    art = art or at("build/bonanza-art")
    binp, o88, img = (os.path.join(td, n) for n in ("bonanza.bin", "BONANZA.O88", "%s%d.img" % (name, size)))
    assemble(src, art, binp)
    subprocess.run(["python3", "tools/os88pkg.py", "--compress-if=lz4", binp, "-o", o88] + part_args(art),
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["python3", "tools/os88disk.py", "-o", img, "--size", str(size), o88], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    return src, img


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


def part_args(art):
    """The --part list in the Makefile's BZ_PARTS order (SPEC.md 128.11.3.1):
    rows 0 - 2 the rubber, steel and glass balls, then course K's one part
    (bzcourse.inc's BZ_NCRS of them)."""
    n = int(re.search(r"^BZ_NCRS\s+equ\s+(\d+)", open(os.path.join(art, "bzcourse.inc")).read(), re.M).group(1))
    out = []
    for p in list(A.BALL_FILES) + ["BZ%d.BIN" % k for k in range(n)]:
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
            patch_tree(src, patches)
            assemble(src, art, os.path.join(td, "bonanza.bin"))
            out.append("%s --red %s: anchors found, the broken copy assembles (%d bytes)" % (
                label, name, os.path.getsize(os.path.join(td, "bonanza.bin"))))
    return out


COLFIRST_TV = ("    mov bx, BZ_PWHEEL * 4       ; (the wheel's part: appended, so the wave-2\n"
               "bz_tv:                          ; parts keep their numbers)\n    call bz_mark\n")
COLFIRST_COL = ".col:\n    mov ax, [bz_dc]\n    or ax, ax\n    jz bz_tb\n"
REDS = {
    # the entering column moving right: the window's column W (not W - 1)
    "colright": [("bzgame.inc", "    add ax, [bz_W]              ; moving right: the right edge's\n    dec ax\n",
                  "    add ax, [bz_W]              ; moving right: the right edge's\n")],
    # the entering column before the retrace and the flip: the same bytes in the end
    "colfirst": [("bzgame.inc", COLFIRST_TV, COLFIRST_TV +
                  "    cmp byte [bz_full], 0\n    jne .redskip\n    mov ax, [bz_dc]\n    or ax, ax\n"
                  "    jz .redskip\n    mov ax, [bz_c0n]\n    js .redl\n    add ax, [bz_W]\n    dec ax\n"
                  ".redl:\n    xor bx, bx\n    mov cx, [bz_H]\n    call bz_col\n.redskip:\n"),
                 ("bzgame.inc", COLFIRST_COL, ".col:\n    jmp bz_tb\n")],
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
    # the platform (the lift) always UNDER the ball
    "padfront": [("bzwheel.inc", "    cmp ax, cx\n    jge .out\n    mov byte [bz_pov], 1\n",
                  "    cmp ax, cx\n    jge .out\n    mov byte [bz_pov], 0        ; RED padfront: never over\n")],
    # the ball DRAWN in a transit: its new footprint boxed and its sprite composed
    "hidden": [("bzgame.inc", "    cmp byte [bz_tube], 0       ; a HIDDEN ball (in a tube) has no new\n"
                "    jne .hid                    ; footprint: its old one alone, restored\n",
                "    nop                         ; RED hidden: a hidden ball boxed as any\n"),
               ("bzvideo.inc", "    cmp byte [bz_tube], 0\n    jne .nob\n    mov ax, [bz_py]\n",
                "    mov ax, [bz_py]             ; RED hidden: its sprite composed in a tube\n")],
}
RED_PARTS = {"colright": ("bench",), "colfirst": ("bench",), "late": ("bench",), "row0": ("probe",),
             "occ": ("bench",), "shadow": ("trial",), "boxfirst": ("trial",), "htab": ("glass",),
             "late2": ("probe",), "pass2": ("trial",), "contact": ("mill",), "defer": ("mill",),
             "padfront": ("play",), "hidden": ("mill",)}
# ...the cards each CAN go red on: the Hercules has 16 + 82 lines of sync and
# blank (~24.7k clocks) before its window's line 0, so the WHOLE column (at
# most ~22k on the benchmark) fits ahead of a row-0 box there and item 6's
# order is the CGA's alone to need (the final pass of wave 1 measured row0 at
# 11 late boxes of 11 on the CGA, 0 of 7 on the Hercules); a later box is late
# on the CGA alone for the same reason; and the table is the Hercules's
RED_TAGS = {"row0": ("cga",), "late2": ("cga",), "htab": ("herc",)}
# ...and what each must go red FOR: a red arm that fails for another reason
# proves nothing about the check it is the arm of
RED_WANT = {"colright": "at bz_presented", "colfirst": "at bz_tf", "late": "bz_rlate", "row0": "FIRST box",
            "occ": " LAID ", "shadow": "card != oracle", "boxfirst": "RASTER ORDER",
            "htab": "card memory != the course", "late2": "cycle counter", "pass2": "walk entered",
            "contact": "at bz_tf", "defer": "defer", "padfront": "pover", "hidden": "transit"}


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
        for line in check_reds(REDS, "bonanza_ring"):
            print(line)
        return
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.red:
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
