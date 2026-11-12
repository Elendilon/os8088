#!/usr/bin/env python3
"""BONANZA: the two-way ring on MartyPC's CGA and Hercules (SPEC.md 128.2, 128.8, 128.10.11).

    make bonanzadisk && python3 tests/bonanza_ring.py [--adapter cga|herc|both]
    python3 tests/bonanza_ring.py --red colright|colfirst|late|row0|occ   (a red arm, below)

THE ORACLE is tools/bbcourse.py (SPEC.md 128.10.4): the course's picture as
the compiler rendered it, with the ball's frame f = (py & 7) * 8 + (px & 7)
composited at the guest's (px, py) AND the occluder records laid back over it
by SPEC.md 128.10.4.4's rule at the guest's own s_b ([bz_sb]), z_b (the
integer px of [bz_gz]) and air flag ([bz_air]) - bbcourse.composite, the
compiler's own function, on the HOST with none of the guest's tricks (no
shear, no ring, no boxes, no clipping, no OCC gate).  The guest's card memory
is decoded through the ring exactly as the 6845 scans it - bank by line,
`+ 2*S` bytes, mod 8,192 - at the package's own shown start address bz_S, and
the two are compared PIXEL FOR PIXEL (2-bit inks on the CGA, 2-bit card-pixel
PAIRS on the Hercules, by bonanza_assets.herc_pair: the course's and the
ball's checker are one rule, SPEC.md 128.9 item 7).

  1  THE GLASS (m.fbuf): play mode (Enter: FIRST, 128.10.6.1), no key held,
     so the ball rests and every frame re-presents one picture; the card's
     own rasterisation is then the same picture - a 320 x 200 field on the
     CGA, a 200-line field of 360 pixel pairs on the Hercules with nothing
     lit outside it (SPEC.md 102.7.1's R6 = 50).  Its control: the picture
     one word column over must NOT match the glass.
  2  THE BENCHMARK (B: BENCH under physics v1, the autopilot, 1,200 frames):
     the frame loop stopped at BOTH of these on chosen frames -
       bz_tf         the retrace has come and the start address is about to
                     change: the card at the OLD bz_S must still be the LAST
                     frame's picture exactly (rules 1 and 3's ORDER).
       bz_presented  the frame is done: the card at the NEW bz_S must be
                     this frame's picture.
     The frames checked are the first full write, the FIRST FEW of each of
     the eight scroll directions (dr, dc) as the autopilot produces them, the
     first few frames where the ORACLE hides part of the ball behind a
     record (decided on the host at bz_tf from the frame's ball, not off the
     guest's [bz_nlay], so a build whose pass never runs is still checked
     there), and then one moving frame in 97.  Every direction must appear,
     and at least one checked frame must have hidden part of the ball behind
     a record (SPEC.md 128.10.11.3) - a row that never looks behind a block
     cannot see the occluder pass.  After it, bz_rlate must be 0.
  3  NEGATIVE CONTROLS on a scrolled frame per adapter: the decode at S + 1
     must FAIL, and so must the picture after a poked wrong camera (bz_c0 +
     1, then bz_R0 + 1, written and read back through the same path).
  4  THE ROW-0 PROBE (SPEC.md 128.10.11.2): play mode on BENCH ([bz_crs]
     poked at bz_launch: Enter plays FIRST) in GLIDE.  The camera settles on
     the start, with the window at the TOP CLAMP (R0 0) - the one place play
     can put a box at window row 0, a flight's apex over the course's top
     (128.10.4.1); away from it GLIDE's two rows a frame keep a rising ball
     inside its band.  Then at bz_t0 of every probe frame the ball's position
     and velocities are written so that its footprint's top is the window's
     first line and its centre right of the dead zone (so GLIDE steps a
     column at the right edge each frame, clear of the footprint) -
     airborne, high over a floor cell, drifting right.  The first probe
     frame is a LEAD-IN whose lateness is not counted (its box is the union
     of the start's footprint and the poked one, a teleport play cannot
     make).  Each later frame with a box at window row 0 ([bz_row0] set) and
     an entering column ([bz_dc] != 0) takes 128.9 item 6's path; at least
     five of them on each card, the card equal to the host picture at bz_tf
     and bz_presented on every probe frame, and [bz_late] 0 at the end.  It
     proves item 6's ORDER on the glass, and its timing on the CGA, where
     the box writer is ~1.6x slower than the beam.  (The first final pass
     ran it panning UP from low on the course's right: two rows, a column
     and a window refill every frame overran a CGA refresh, a frame play
     cannot make, and the boxes it made late were measured, not guessed -
     SPEC.md 128.10.11.2's as-built note.)

--red NAME is the row's red arm (docs/WRITING-TESTS.md 1): it copies
apps/bonanza/ to a temporary directory, breaks one thing there, builds that
package and its 360KB floppy into the same temporary directory (never
build/), runs the checks against it and PASSES only if they FAIL:
  colright   the entering column moving right is the window's column W, not
             W - 1 (a content error: the right edge is left stale)
  colfirst   the entering column is written BEFORE the retrace wait and the
             flip - the same bytes in the end, so only the bz_tf check (the
             order) can see it
  late       every frame counts as a late row-0 box: the bz_rlate assertion's
             own plumbing
  row0       item 6's order undone: a box at window row 0 takes the WHOLE
             column first again, so the probe's boxes start after the beam
             has passed line 0 and [bz_late] must go above 0 - on the CGA
             ONLY (RED_TAGS): the Hercules' 98 lines of sync and blank hold
             the whole column ahead of the box, so the order is not load-
             bearing there
  occ        the occluder pass skipped (bz_occ returns at once): a checked
             frame behind a record mismatches the oracle

The module is also the LIBRARY the other BONANZA rows share (bonanza_perf,
bonanza_phys, bonanza_exit, bonanza_mega): `symbols`, `Bz`, `Ref`, `Walker`,
`build_tree` and the course cache.
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
FILES = ("bonanza.asm", "bzvideo.inc", "bzgame.inc", "bzphys.inc")
EXTRA_SYMS = ("op_table",)          # os88parts.inc's: the part rows (bonanza_exit)
DIRS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]
FIRST_EACH = 3                      # frames checked per direction, first ones
LAY_EACH = 6                        # ...and the first frames that laid a record
EVERY = 97                          # ...and then one moving frame in this many
PROBE_MIN = 5                       # row-0 probe frames a card (SPEC.md 128.10.11.2)
PROBE_MAX = 30                      # probe frames run at most


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


def at(p):
    return os88build.at(p)


def course(name, src=None):
    """bbcourse's compile of a course, once a process (a few seconds each).
    SRC: a course file other than the shipped one (a red tree's)."""
    path = src or os.path.join(ROOT, COURSES[name])
    if path not in _COURSE:
        _COURSE[path] = BB.compile_course(path)
    return _COURSE[path]


def symbols(src=None, art=None):
    """Every bz_ label and VAR of the package (and EXTRA_SYMS), by assembling
    it with a table of `dw label` on the end (the guest's own offsets, no
    listing parsing).  A file of FILES a source does not have is skipped:
    wave 0b's package (bonanza_perf's A/B leg) has no bzphys.inc."""
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


def unpack_ball(tag):
    return A.ball_herc_pairs if tag == "herc" else A.ball_frame_indices


class Ref:
    """The host's picture of one course on one card: bbcourse's render, the
    ball over it and the records laid back (bbcourse.composite)."""

    def __init__(self, tag, crs):
        self.tag, self.c = tag, crs
        pic = crs.pic
        if tag == "cga":
            self.rows = [bytes(r) for r in pic]
        else:                       # the course's 10/01 checker by world line and column
            self.rows = [bytes(A.herc_pair(v, L, X) for X, v in enumerate(r)) for L, r in enumerate(pic)]

    def enc(self, v, L, X):
        return v if self.tag == "cga" else A.herc_pair(v, L, X)

    def foot(self, px, py, sb, zb, air, cell=None):
        """-> ({(x, y): card value} over the footprint, ball pixels the records hid).
        CELL (Bz.occkey): the ball's cell when the guest's window was centred on
        it; if that cell's OCC flag is clear the guest's gate was off and the
        ball is drawn whole - what bz_occ does, 128.10.8 item 1."""
        gated = cell is not None and not (self.c.cells.get(cell, (0, 0, 0, 0))[3] & BB.FL_OCC)
        comp = BB.composite(self.c, px, py, sb, zb, air, via="none" if gated else "records")
        hidden = 0
        for p, v in BB.ball_pixels(px, py).items():
            if comp.get(p, v) != v:
                hidden += 1
        return {(x, y): self.enc(v, y, x) for (x, y), v in comp.items()}, hidden

    def picture(self, R0, c0, px, py, sb, zb, air, cell=None):
        """200 rows (bytes) of the window whose top card row is R0 and left word
        column c0, the ball's top-left at world (px, py) in cell row sb at
        whole height zb, air 0/1 (the occluder rule's inputs), CELL as foot()."""
        top, left, w = R0 * RL[self.tag], c0 * 8, W[self.tag]
        fp, _ = self.foot(px, py, sb, zb, air, cell)
        out = []
        for y in range(200):
            L = top + y
            row = self.rows[L][left:left + w]
            if py <= L < py + BB.FOOT_H:
                row = bytearray(row)
                for x in range(max(left, px & ~3), min(left + w, (px & ~3) + BB.FOOT_W)):
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

    def occkey(self):
        """(s_b, z_b, air, cell): the occluder rule's inputs as the frame
        composed them, and the ball's cell (wx, wy) when the guest's window is
        centred on it - no POKE since the last step, [bz_pokd] 0 - else None.
        Ref.foot's input for bz_occ's GATE (128.10.8 item 1): centred and the
        cell's OCC flag clear, the flag read from the HOST's course, not the
        guest's window, so a wrong flag still shows.  The gate only matters for
        a POKED ball (the row-0 probe) at a height the tool's reachable set
        never gives its cell; for every reachable state an OCC-clear cell lays
        nothing by construction (128.10.4.6 item 5)."""
        gx, gy = self.d("bz_gx") >> 12, self.d("bz_gy") >> 12
        centred = not self.b("bz_pokd")             # every step leaves the window on the ball's cell
        return (self.w("bz_sb"), struct.unpack("<h", self.m.read(self.a("bz_gz") + 1, 2))[0], self.b("bz_air"),
                (gx, gy) if centred else None)

    def phys(self):
        """(nstep, gx, gy, gz, gvx, gvy, gvz, air): bbcourse.Physics.state()'s shape"""
        return (self.d("bz_nstep"), self.d("bz_gx"), self.d("bz_gy"), self.sd("bz_gz"),
                self.s("bz_gvx"), self.s("bz_gvy"), self.s("bz_gvz"), self.b("bz_air"))

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
    """The frame loop under breakpoints: bz_tf and bz_presented (and bz_t0)."""

    def __init__(self, g, t0=False):
        self.g, self.m = g, g.m
        self.tf, self.pr = g.a("bz_tf"), g.a("bz_presented")
        self.t0 = g.a("bz_t0") if t0 else None

    def arm(self):
        self.m.bp_exec(*[a for a in (self.t0, self.tf, self.pr) if a is not None])

    def next(self):
        """Run to the next mark; -> 't0', 'tf' or 'pr'."""
        m = self.m
        m.run()
        st = m.wait_stop(60)
        assert st == "breakpoint", "the frame loop stopped reaching its marks (state %r)" % st
        r = m.regs()
        flat = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
        if flat == self.tf:
            return "tf"
        if flat == self.t0:
            return "t0"
        assert flat == self.pr, "stopped at %05X, none of the marks" % flat
        return "pr"


def pic_now(g, ref, st=None):
    """The host picture of the frame the guest holds now (at bz_presented)."""
    st = st or g.state()
    return ref.picture(*st[1:], *g.occkey())


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
    key = g.occkey()
    exp = ref.picture(R0, c0, px, py, *key)
    n, box = diff(g.decode(S), exp)
    assert n == 0, "play mode's resting frame: card memory != the course (%d px, box %s)" % (n, box)
    fw, fh, fd = m.fbuf(0)
    wrong = ref.picture(R0, c0 + 1, px, py, *key)
    res = glass_cga(fw, fh, fd, exp, wrong) if tag == "cga" else glass_herc(fw, fh, fd, exp, wrong)
    print("%s glass (FIRST, ball at rest at %d,%d): framebuffer %dx%d; %s" % (tag, px, py, fw, fh, res),
          flush=True)
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "play mode ends on Esc", guest=60)


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


def bench(g, ref):
    """Parts 2 and 3: the benchmark, stopped at bz_tf and bz_presented on chosen frames."""
    m, tag = g.m, g.tag
    wk = Walker(g)
    wk.arm()                                # the desktop never runs these: armed before B
    g.key("KeyB")
    done = {d: 0 for d in DIRS}
    checks, tfchecks, fails, full_checked, split, controls = 0, 0, [], 0, 0, None
    laid_checked, hid_checked, hid_px, glaid = 0, 0, 0, 0
    prev = None                             # the last presented frame's (S, R0, c0, px, py) + occkey
    want = False
    moving = 0
    nlay0 = 0
    first = True
    while True:
        k = wk.next()
        if first:
            g.check_base()
            first = False
        if k == "tf":
            if g.b("bz_mode") != 1:
                raise AssertionError("B did not start the benchmark")
            full = g.b("bz_full")
            dr, dc = g.s("bz_dr"), g.s("bz_dc")
            dk = ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
            moving += dk != (0, 0)
            # does the ORACLE hide part of this frame's ball behind a record? (decided on the host,
            # not off [bz_nlay]: a build whose pass never runs must still have these frames checked)
            _, hid = ref.foot(g.w("bz_px"), g.w("bz_py"), *g.occkey())
            laid = hid > 0
            nlay = g.w("bz_nlay")
            glaid += nlay != nlay0
            nlay0 = nlay
            want = bool(full and not full_checked) or (dk in done and done[dk] < FIRST_EACH) or \
                (laid and laid_checked < LAY_EACH) or (dk != (0, 0) and moving % EVERY == 0)
            if want and prev is not None and not full:
                assert g.w("bz_S") == prev[0][0], "bz_S moved before bz_tf"
                n, box = diff(g.decode(prev[0][0]), ref.picture(*prev[0][1:], *prev[1]))
                tfchecks += 1
                if n:
                    fails.append("frame %d (%+d,%+d) at bz_tf: the shown window (S %d) is not the last "
                                 "frame's picture: %d px, lines %d-%d, x %d-%d" % (
                                     g.w("bz_frames") + 1, dr, dc, prev[0][0], n, *box))
            if want:
                wk.dk, wk.full, wk.laid = dk, full, laid
            continue
        st = g.state()
        key = g.occkey()
        fr = g.w("bz_frames")
        if want:
            n, box = diff(g.decode(st[0]), ref.picture(*st[1:], *key))
            checks += 1
            if wk.full:
                full_checked += 1
            elif wk.dk in done:
                done[wk.dk] += 1
            if wk.laid:
                laid_checked += 1
                _, hid = ref.foot(st[3], st[4], *key)
                if hid:
                    hid_checked += 1
                    hid_px += hid
            if g.w("bz_crest") and g.w("bz_cfrom"):
                split += 1
            if n:
                fails.append("frame %d (%+d,%+d)%s%s at bz_presented: S %d R0 %d c0 %d ball %d,%d (s_b %d z_b %d "
                             "air %d): %d px, lines %d-%d, x %d-%d" % (
                                 fr, wk.dk[0], wk.dk[1], " FULL" if wk.full else "",
                                 " LAID" if wk.laid else "", *st, *key[:3], n, *box))
            elif controls is None and wk.dk[0] and wk.dk[1] and not wk.full:
                controls = negative_controls(g, ref, st)
            want = False
        prev = (st, key)
        if fr >= 1199 or len(fails) >= 4:
            break
    m.bp_exec()
    m.run()
    late = None
    if not fails:
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark ends", guest=120)
        assert g.b("bz_res") == 1, "the benchmark left no results"
        late = g.w("bz_rlate")
        if late:
            fails.append("bz_rlate = %d: a box at window row 0 was not ahead of the beam" % late)
    print("%s benchmark to frame %d: %d frames checked at bz_presented and %d at bz_tf (the old window "
          "intact at the latch); the full write %d; column split round the boxes on %d of them" % (
              tag, fr, checks, tfchecks, full_checked, split), flush=True)
    print("%s occluders: %d checked frames where the oracle hides part of the ball behind a record (%d of "
          "them still at bz_presented, %d ball px); frames whose compose laid one ([bz_nlay] moved) %d; records "
          "laid over the run %s, boxes with the pass gated on %s" % (
              tag, laid_checked, hid_checked, hid_px, glaid, g.w("bz_rnlay") if late is not None else "-",
              g.w("bz_rnocf") if late is not None else "-"), flush=True)
    print("%s late row-0 boxes (bz_rlate): %s" % (tag, late), flush=True)
    print("%s directions checked (dr,dc): %s" % (
        tag, "  ".join("%+d%+d x%d" % (d[0], d[1], done[d]) for d in DIRS)), flush=True)
    if controls:
        print("%s negative controls: %s" % (tag, controls), flush=True)
    return {"fails": fails, "done": done, "full": full_checked, "controls": controls, "checks": checks,
            "hid": hid_checked}


def negative_controls(g, ref, st):
    """The same decode must FAIL at S + 1, and after a poked wrong camera."""
    S, R0, c0, px, py = st
    key = g.occkey()
    n1, _ = diff(g.decode((S + 1) % 4096), ref.picture(R0, c0, px, py, *key))
    assert n1 > 1000, "decode at S + 1 matches too (%d px differ): the check cannot fail" % n1
    out = ["S+1 differs in %d px" % n1]
    for name, v in (("bz_c0", c0 + 1), ("bz_R0", R0 + 1)):
        g.put(name, v)
        try:
            n2, _ = diff(g.decode(g.w("bz_S")), ref.picture(*g.state()[1:], *key))
        finally:
            g.put(name, c0 if name == "bz_c0" else R0)
        assert n2 > 1000, "a poked %s still matches (%d px differ): the check cannot fail" % (name, n2)
        out.append("%s+1 poked differs in %d px" % (name, n2))
    assert g.state() == st, "the poked camera was not put back"
    return ", ".join(out)


# ---- the row-0 probe (SPEC.md 128.10.11.2) ----------------------------------
def poke_ball(g, gx, gy, gz, gvx=0, gvy=0, gvz=0, same_cell=False):
    """The position and the velocities (SPEC.md 128.10.7.1), 24.8 values, and
    what a poke owes besides: bz_pokd = 1, so the next step refills the window
    round the ball's cell itself, and the SCREEN state derived from the poked
    position with a zero velocity - bbcourse.Physics.poke's _derive(True) -
    so that a frame which runs no step (about 9% of the CGA's) draws the ball
    where it was poked, not where the last step left it.

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
    kx, ky = g.sd("bz_kx"), g.sd("bz_ky")       # (X0 - 8) << 8, (Y0 - 13) << 8
    g.putd("bz_bx", gx - gy + kx)
    g.putd("bz_by", ((gx + gy) >> 1) - gz + ky)
    g.put("bz_vx", 0)
    g.put("bz_vy", 0)
    if not same_cell or (gx >> 12) << 4 != g.w("bz_wgx") or (gy >> 12) << 4 != g.w("bz_wgy"):
        g.putb("bz_pokd", 1)


def probe_ground(crs, px, py, grid, sx=1):
    """A contact point (24.8 gx, gy, gz) whose derived picture top-left is (px, py)
    with the by fraction at 0x80, high over a FLOOR cell (at least 16 px above
    its floor), placed so that its drift (gvx 64 SX, gvy -64 SX: at most 2 gu
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
        if c[3] != BB.KIND_FLOOR:               # (not a GOAL: play would end on it)
            continue
        gz8 = (d8 >> 1) + ky - by8
        z4 = (gz8 >> 6) - 64                    # quarter px, 16 px under the ball
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


def probe(g, ref):
    """Part 4: the POKED row-0 probe, play mode on BENCH in GLIDE."""
    m, tag = g.m, g.tag
    crs = ref.c
    grid = BB.Grid(crs.cga)
    m.bp_exec(g.a("bz_launch"))
    g.key("Enter")
    assert m.wait_stop(60) == "breakpoint", "Enter did not reach bz_launch"
    g.putb("bz_crs", CRS_K["bench"])            # play mode, on the benchmark's course
    g.putb("bz_cmode", 0)                       # GLIDE (C cycles it; it persists)
    m.bp_exec()
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 5, "play mode on BENCH runs", guest=60)
    m.pause()
    g.check_base()
    # 1. the window at the course's TOP: play starts on BENCH's start plateau
    # (6, 14), and GLIDE settles with the window clamped at R0 = 0 - the one
    # place play can put a box at window row 0 (an airborne ball at its apex
    # over the top's back edge, 128.10.4.1; away from the clamp GLIDE's two
    # rows a frame keep a rising ball inside its band).  The probe pans RIGHT
    # from there, its ball over the plateau and the descent below it.
    wk = Walker(g, t0=True)
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
    cmax, rmax = g.w("bz_cmax"), g.w("bz_rmax")
    print("%s probe: the window settled at R0 %d c0 %d on the start (cmax %d, rmax %d)" % (
        tag, R0, c0, cmax, rmax), flush=True)
    assert R0 == 0 and c0 + PROBE_MIN + 2 <= cmax, \
        "the probe's window is not at the top clamp with room to pan right: R0 %d, c0 %d, cmax %d" % (
            R0, c0, cmax)
    # 2. the probe frames.  The FIRST is a lead-in and its lateness is not
    # counted: its poke moves the ball from the start, at rest down the
    # window, to the window's first line, so its box is the union of the two
    # footprints and the column's rows down to that box's last row go first -
    # a teleport play cannot make (a ball moves a few lines a frame, and a
    # respawn lands on a floor, 16 lines or more down: 128.10.4.1).  Its
    # pictures are checked like every frame's.
    late0 = None
    lw = W[tag] // 8
    frames, hit, fails, prev = 0, 0, [], None
    while frames < PROBE_MAX:
        k = wk.next()
        if k == "t0":
            R0, c0 = g.w("bz_R0"), g.w("bz_c0")
            if R0 != 0 or c0 >= cmax:
                break
            # the ball's top on the window's first line (world line 0: the window stays clamped) and its
            # centre RIGHT of the dead zone (which is [2W, 6W] px), so GLIDE steps a column at the right
            # edge each frame, clear of the footprint
            tpx = c0 * 8 + W[tag] - lw - 8
            gp = probe_ground(crs, tpx, 0, grid, 1)
            if gp is None:              # the ball's screen column has left the course: the probe is over
                break
            poke_ball(g, gp[0], gp[1], gp[2], 64, -64, 36, same_cell=True)
            continue
        if k == "tf":
            if prev is not None and not g.b("bz_full"):
                n, box = diff(g.decode(prev[0][0]), ref.picture(*prev[0][1:], *prev[1]))
                if n:
                    fails.append("probe frame %d at bz_tf: the shown window is not the last frame's picture: "
                                 "%d px, lines %d-%d, x %d-%d" % (frames + 1, n, *box))
            continue
        frames += 1
        st, key = g.state(), g.occkey()
        n, box = diff(g.decode(st[0]), ref.picture(*st[1:], *key))
        r0, dc = g.b("bz_row0"), g.s("bz_dc")
        if late0 is None:                       # the lead-in (above)
            late0 = g.w("bz_late")
        elif r0 and dc:
            hit += 1
        if n:
            fails.append("probe frame %d at bz_presented: S %d R0 %d c0 %d ball %d,%d (row0 %d, dc %d): %d px, "
                         "lines %d-%d, x %d-%d" % (frames, *st, r0, dc, n, *box))
        prev = (st, key)
        if len(fails) >= 4:
            break
    m.bp_exec()
    late = g.w("bz_late") - (late0 if late0 is not None else g.w("bz_late"))
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the probe's play ends on Esc", guest=60)
    print("%s probe: %d frames (the first a lead-in), %d with the boxes at window row 0 and an entering column (128.9 item 6's "
          "path), card = picture on every one at bz_tf and bz_presented: %s; late row-0 boxes %d" % (
              tag, frames, hit, "yes" if not fails else "NO", late), flush=True)
    if hit < PROBE_MIN:
        fails.append("only %d probe frames took item 6's path (row 0 and an entering column); %d needed" % (
            hit, PROBE_MIN))
    if late:
        fails.append("bz_late = %d over the probe: a row-0 box started after the beam passed line 0" % late)
    return fails


def run(tag, apps=None, src=None, art=None, parts=("glass", "bench", "probe")):
    """-> {"parts": the parts run, "fails": [...], and the benchmark's tallies}"""
    sym = symbols(src, art)
    out = {"parts": parts, "fails": []}
    with os88ui.boot(at("build/os8088-360.img"), apps=apps or at("build/bonanza360.img"),
                     machine=MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = Bz(ui, tag, sym)
        ui.settle()
        if "glass" in parts:
            glass(g, Ref(tag, course("first")))
        if "bench" in parts:
            out.update(bench(g, Ref(tag, course("bench"))))
        if "probe" in parts and not out["fails"]:
            out["fails"] += probe(g, Ref(tag, course("bench")))
    return out


def verdict(tag, r):
    bad = list(r["fails"])
    if "bench" not in r["parts"]:
        return bad
    missing = [d for d in DIRS if not r["done"][d]]
    if missing:
        bad.append("directions never checked: %s" % missing)
    if not r["full"]:
        bad.append("the first frame's full write was not checked")
    if not r["controls"] and not r["fails"]:
        bad.append("no diagonal frame for the negative controls")
    if not r["hid"] and not r["fails"]:
        bad.append("no checked frame hid any of the ball behind an occluder record (SPEC.md 128.10.11.3)")
    return bad


# ---- the red arms and their private trees ----------------------------------------
def build_tree(td, patches, size=360, src0=None, art=None, name="bonanza"):
    """apps/bonanza/ copied into TD, PATCHES [(file, old, new), ...] applied
    (each OLD must occur exactly once - a red arm whose anchor moved says so),
    and the package and a floppy of SIZE KB built there from the current art.
    -> (source dir, image)."""
    src = os.path.join(td, name)
    shutil.copytree(src0 or os.path.join(ROOT, "apps", "bonanza"), src)
    for f, old, new in patches:
        p = os.path.join(src, f)
        t = open(p).read()
        assert t.count(old) == 1, "the red anchor in %s moved (%d matches): re-anchor the red arm" % (
            f, t.count(old))
        open(p, "w").write(t.replace(old, new))
    art = art or at("build/bonanza-art")
    binp, o88, img = (os.path.join(td, n) for n in ("bonanza.bin", "BONANZA.O88", "%s%d.img" % (name, size)))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", src + "/",
                    "-I", art + "/", "-o", binp, os.path.join(src, "bonanza.asm")], cwd=ROOT, check=True)
    subprocess.run(["python3", "tools/os88pkg.py", "--compress-if=lz4", binp, "-o", o88] + part_args(art),
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["python3", "tools/os88disk.py", "-o", img, "--size", str(size), o88], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    return src, img


def part_args(art):
    """The --part list in the Makefile's BZ_PARTS order: the ball's two, then
    every course's two (bzcourse.inc's BZ_NCRS)."""
    n = int(re.search(r"^BZ_NCRS\s+equ\s+(\d+)", open(os.path.join(art, "bzcourse.inc")).read(), re.M).group(1))
    out = []
    for p in ["BZBALC.BIN", "BZBALH.BIN"] + ["BZ%d%s.BIN" % (k, c) for k in range(n) for c in "CH"]:
        out += ["--part", os.path.join(art, p)]
    return out


COLFIRST_TV = "bz_tv:\n    mov bx, 2 * 4\n    call bz_mark\n"
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
    # (still timed as a row-0 box, so bz_late sees the beam overtake it)
    "row0": [("bzgame.inc", ".row0:                          ; a box at window row 0 (SPEC.md 128.9 item 6):\n",
              ".row0:                          ; a box at window row 0 (SPEC.md 128.9 item 6):\n"
              "    mov cx, [bz_H]              ; RED row0: the whole column first\n"
              "    mov byte [bz_row0], 1\n    ret\n")],
    # the occluder pass skipped: the ball is drawn over what should hide it
    "occ": [("bzvideo.inc", "bz_occ:\n    cmp byte [bz_pokd], 0\n",
             "bz_occ:\n    ret                         ; RED occ\n    cmp byte [bz_pokd], 0\n")],
}
RED_PARTS = {"colright": ("bench",), "colfirst": ("bench",), "late": ("bench",), "row0": ("probe",),
             "occ": ("bench",)}
# ...the cards each CAN go red on: the Hercules has 16 + 82 lines of sync and
# blank (~24.7k clocks) before its window's line 0, so the WHOLE column (at
# most ~22k on the benchmark) fits ahead of a row-0 box there and item 6's
# order is the CGA's alone to need (22 lines after the sync; the final pass
# measured row0 at 11 late boxes of 11 on the CGA and 0 of 7 on the Hercules)
RED_TAGS = {"row0": ("cga",)}
# ...and what each must go red FOR: a red arm that fails for another reason
# proves nothing about the check it is the arm of
RED_WANT = {"colright": "at bz_presented", "colfirst": "at bz_tf", "late": "bz_rlate", "row0": "bz_late",
            "occ": " LAID "}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--red", choices=sorted(REDS))
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.red:
        tags = tuple(t for t in tags if t in RED_TAGS.get(a.red, tags)) or tags
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
    allbad = []
    for tag in tags:
        bad = verdict(tag, run(tag))
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d ring failure(s)" % len(allbad)
    print("bonanza_ring (%s): PASS" % ", ".join(tags))


if __name__ == "__main__":
    main()
