#!/usr/bin/env python3
"""BONANZA: the two-way ring on MartyPC's CGA and Hercules (SPEC.md 128.2, 128.8).

    make bonanzadisk && python3 tests/bonanza_ring.py [--adapter cga|herc|both]
    python3 tests/bonanza_ring.py --red colright|colfirst|late   (a red arm, below)

The oracle is tools/bonanza_assets.py: the course picture and the ball's
frame f = (py & 7) * 8 + (px & 7), composited on the HOST with none of the
guest's tricks (no shear, no ring, no boxes, no clipping).  The guest's card
memory is decoded through the ring exactly as the 6845 scans it - bank by
line, `+ 2*S` bytes, mod 8,192 - at the package's own shown start address
bz_S, and the two are compared PIXEL FOR PIXEL (2-bit inks on the CGA,
2-bit card-pixel PAIRS on the Hercules):

  1  THE GLASS (m.fbuf): play mode, no key held, so the ball rests and every
     frame re-presents one picture; the card's own rasterisation is then the
     same picture - a 320 x 200 field on the CGA, a 200-line field of 360
     pixel pairs on the Hercules with nothing lit outside it (SPEC.md
     102.7.1's R6 = 50).  Its control: the picture one word column over must
     NOT match the glass.
  2  THE BENCHMARK (B, the deterministic autopilot): the frame loop stopped
     at BOTH of these on chosen frames -
       bz_tf         the retrace has come and the start address is about to
                     change: the card at the OLD bz_S must still be the LAST
                     frame's picture exactly.  The entering rows are already
                     in it (rule 1 puts them in the slack) and nothing may
                     have touched a shown cell - a column written before the
                     flip lands on the old window's left or right edge, and a
                     box written early shows the ball moved, so this is the
                     check that holds rules 1 and 3's ORDER, not only their
                     result.
       bz_presented  the frame is done: the card at the NEW bz_S must be
                     this frame's picture (window at bz_R0/bz_c0, the ball at
                     bz_px/bz_py).
     The frames checked are the first full write and the FIRST FEW of each
     of the eight scroll directions (dr, dc) as the autopilot produces them,
     then one in every 97 with motion.  Every direction must appear, and the
     row fails if one does not - a route that stops scrolling some way is a
     ring nobody tested.
  3  NEGATIVE CONTROLS on a scrolled frame per adapter: the decode at S + 1
     must FAIL, and so must the picture after a deliberately poked wrong
     camera (bz_c0 + 1, then bz_R0 + 1, written into the guest and read back
     through the same path, then restored).

--red NAME is the row's own red arm (docs/WRITING-TESTS.md 1): it copies
apps/bonanza/ to a temporary directory, breaks one thing there, builds that
package and its 360KB floppy into the same temporary directory (never
build/), runs the checks against it and PASSES only if they FAIL:
  colright   the entering column moving right is the window's column W, not
             W - 1 (a content error: the right edge is left stale)
  colfirst   the entering column is written BEFORE the retrace wait and the
             flip - the same bytes in the end, so only the bz_tf check (the
             order) can see it
  late       every frame counts as a late row-0 box (bz_late): only the
             bz_rlate = 0 assertion can see it.  (The row-0 path itself is
             out of the wave-0b course's reach - SPEC.md 128.9 item 6 - so
             this arm proves the assertion's plumbing, not the timing.)
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

MACHINE = {"cga": "os8088_5150_cga_gla", "herc": "os8088_5150_herc_gla"}
W = {"cga": 320, "herc": 360}       # game pixels across the window
RL = {"cga": 2, "herc": 4}          # lines a card row
RB = {"cga": 80, "herc": 90}        # bytes a line
FILES = ("bonanza.asm", "bzvideo.inc", "bzgame.inc")
DIRS = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]
FIRST_EACH = 3                      # frames checked per direction, first ones
EVERY = 97                          # ...and then one moving frame in this many
LUT = [bytes(((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3)) for b in range(256)]


def at(p):
    return os88build.at(p)


def symbols(src=None, art=None):
    """Every bz_ label and VAR of the package, by assembling it with a table
    of `dw label` on the end (the guest's own offsets, no listing parsing)."""
    d = src or os.path.join(ROOT, "apps", "bonanza")
    art = art or at("build/bonanza-art")
    names = []
    for f in FILES:
        t = open(os.path.join(d, f)).read()
        names += re.findall(r"^VAR (bz_\w+),", t, re.M)
        names += re.findall(r"^(bz_\w+):", t, re.M)
    names = sorted(set(names))
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "probe.asm")
        b = os.path.join(td, "probe.bin")
        open(p, "w").write(open(os.path.join(d, "bonanza.asm")).read() + "\n" +
                           "\n".join("dw " + n for n in names))
        subprocess.run(["nasm", "-f", "bin", "-I", os.path.join(ROOT, "apps") + "/",
                        "-I", d + "/", "-I", art + "/", "-o", b, p], cwd=ROOT, check=True)
        raw = open(b, "rb").read()
        return dict(zip(names, struct.unpack("<%dH" % len(names), raw[-2 * len(names):])))


class Ref:
    """The host's picture: the course in this card's 2-bit units, the ball over it."""

    def __init__(self, tag):
        self.tag = tag
        course = A.course_indices()
        if tag == "cga":
            self.rows = [bytes(r) for r in course]
        else:                       # Hercules: the course's 10/01 checker by world line and column
            self.rows = [bytes(A.herc_pair(v, L, X) for X, v in enumerate(r))
                         for L, r in enumerate(course)]
        self.frames = {}

    def ball(self, f):
        if f not in self.frames:
            # Hercules: the course's checker at the ball's world position (SPEC.md
            # 128.9 item 7) - the generator's own encoder, frame-relative parity
            self.frames[f] = A.ball_herc_pairs(f) if self.tag == "herc" else A.ball_frame_indices(f)
        return self.frames[f]

    def picture(self, R0, c0, px, py):
        """200 rows (bytes) of the window whose top card row is R0 and left word column c0,
        the ball's top-left at world (px, py)."""
        top, left, w = R0 * RL[self.tag], c0 * 8, W[self.tag]
        frm = self.ball(((py & 7) * 8) + (px & 7))
        out = []
        for y in range(200):
            L = top + y
            row = self.rows[L][left:left + w]
            if py <= L < py + 16 and px + 16 > left and px < left + w:
                row = bytearray(row)
                for i, c in enumerate(frm[L - py]):
                    x = px + i - left
                    if c is not None and 0 <= x < w:
                        row[x] = c
                row = bytes(row)
            out.append(row)
        return out


class Bz:
    """One guest with BONANZA's window open; every read is of a paused machine."""

    def __init__(self, ui, tag, sym):
        self.ui, self.m, self.tag, self.sym = ui, ui.m, tag, sym
        w = ui.window("Bounce Bonanza")
        raw = self.m.read(self.m.sym("wm_wins"), G.MAX_WIN * G.WIN_SIZE)
        self.base = struct.unpack_from("<H", raw, w.i * G.WIN_SIZE + G.W_SEG)[0] << 4
        assert self.base, "the window has no package segment"

    def a(self, n):
        return self.base + self.sym[n]

    def b(self, n):
        return self.m.read(self.a(n), 1)[0]

    def w(self, n):
        return struct.unpack("<H", self.m.read(self.a(n), 2))[0]

    def s(self, n):
        return struct.unpack("<h", self.m.read(self.a(n), 2))[0]

    def d(self, n):
        return struct.unpack("<I", self.m.read(self.a(n), 4))[0]

    def put(self, n, v):
        self.m.write(self.a(n), struct.pack("<H", v))

    def state(self):
        """(S, R0, c0, px, py) as the package holds them now."""
        return (self.w("bz_S"), self.w("bz_R0"), self.w("bz_c0"), self.w("bz_px"), self.w("bz_py"))

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
    """The frame loop under two breakpoints: bz_tf and bz_presented."""

    def __init__(self, g):
        self.g, self.m = g, g.m
        self.tf, self.pr = g.a("bz_tf"), g.a("bz_presented")

    def arm(self):
        self.m.bp_exec(self.tf, self.pr)

    def next(self):
        """Run to the next mark; -> 'tf' or 'pr'."""
        m = self.m
        m.run()
        st = m.wait_stop(60)
        assert st == "breakpoint", "the frame loop stopped reaching its marks (state %r)" % st
        r = m.regs()
        flat = ((r["cs"] << 4) + r["ip"]) & 0xFFFFF
        if flat == self.tf:
            return "tf"
        assert flat == self.pr, "stopped at %05X, neither mark" % flat
        return "pr"


def glass(g, ref):
    """Part 1: the card's own rasterisation of a resting ball's frame."""
    m, tag = g.m, g.tag
    g.key("Enter")
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 20, "play mode runs", guest=60)
    m.pause()
    assert g.b("bz_mode") == 0, "Enter started the benchmark, not play"
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
    exp = ref.picture(R0, c0, px, py)
    n, box = diff(g.decode(S), exp)
    assert n == 0, "play mode's resting frame: card memory != the course (%d px, box %s)" % (n, box)
    fw, fh, fd = m.fbuf(0)
    if tag == "cga":
        res = glass_cga(fw, fh, fd, exp, ref.picture(R0, c0 + 1, px, py))
    else:
        res = glass_herc(fw, fh, fd, exp, ref.picture(R0, c0 + 1, px, py))
    print("%s glass: framebuffer %dx%d; %s" % (tag, fw, fh, res), flush=True)
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
    # outside the field: the border only
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
    for gy0 in range(max(0, bot - 199), min(fh - 199, top + 1)):   # the field's own black lines
                                                                    # are not lit: any window over them
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
    prev = None                             # the last presented frame's (S, R0, c0, px, py)
    want = False
    moving = 0
    while True:
        k = wk.next()
        if k == "tf":
            if g.b("bz_mode") != 1:
                raise AssertionError("B did not start the benchmark")
            full = g.b("bz_full")
            dr, dc = g.s("bz_dr"), g.s("bz_dc")
            dk = ((dr > 0) - (dr < 0), (dc > 0) - (dc < 0))
            moving += dk != (0, 0)
            want = bool(full and not full_checked) or (dk in done and done[dk] < FIRST_EACH) or \
                (dk != (0, 0) and moving % EVERY == 0)
            if want and prev is not None and not full:
                # the retrace has come and S is about to change: the card at the OLD start
                # must still be the last frame's picture, entering rows already in the slack
                assert g.w("bz_S") == prev[0], "bz_S moved before bz_tf"
                n, box = diff(g.decode(prev[0]), ref.picture(*prev[1:]))
                tfchecks += 1
                if n:
                    fails.append("frame %d (%+d,%+d) at bz_tf: the shown window (S %d) is not the last "
                                 "frame's picture: %d px, lines %d-%d, x %d-%d" % (
                                     g.w("bz_frames") + 1, dr, dc, prev[0], n, *box))
            if want:
                wk.dk, wk.full = dk, full
            continue
        st = g.state()
        fr = g.w("bz_frames")
        if want:
            n, box = diff(g.decode(st[0]), ref.picture(*st[1:]))
            checks += 1
            if wk.full:
                full_checked += 1
            elif wk.dk in done:
                done[wk.dk] += 1
            if g.w("bz_crest") and g.w("bz_cfrom"):
                split += 1
            if n:
                fails.append("frame %d (%+d,%+d)%s at bz_presented: S %d R0 %d c0 %d ball %d,%d: %d px, "
                             "lines %d-%d, x %d-%d" % (fr, wk.dk[0], wk.dk[1], " FULL" if wk.full else "",
                                                        *st, n, *box))
            elif controls is None and wk.dk[0] and wk.dk[1] and not wk.full:
                controls = negative_controls(g, ref, st)
            want = False
        prev = st
        if fr >= 1199 or len(fails) >= 4:
            break
    m.bp_exec()
    m.run()
    late = None
    if not fails:
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark ends", guest=120)
        # SPEC.md 128.9 item 6: a box at window row 0 the beam overtook is counted, and the
        # benchmark must have none (bz_rlate is the finished run's copy of bz_late)
        assert g.b("bz_res") == 1, "the benchmark left no results"
        late = g.w("bz_rlate")
        if late:
            fails.append("bz_late = %d: a box at window row 0 was not ahead of the beam" % late)
    print("%s benchmark to frame %d: %d frames checked at bz_presented and %d at bz_tf (the old window "
          "intact at the latch); the full write %d; column split round the boxes on %d of them" % (
              tag, fr, checks, tfchecks, full_checked, split), flush=True)
    print("%s late row-0 boxes (bz_rlate): %s" % (tag, late), flush=True)
    print("%s directions checked (dr,dc): %s" % (
        tag, "  ".join("%+d%+d x%d" % (d[0], d[1], done[d]) for d in DIRS)), flush=True)
    if controls:
        print("%s negative controls: %s" % (tag, controls), flush=True)
    return {"fails": fails, "done": done, "full": full_checked, "controls": controls, "checks": checks}


def negative_controls(g, ref, st):
    """The same decode must FAIL at S + 1, and after a poked wrong camera."""
    S, R0, c0, px, py = st
    n1, _ = diff(g.decode((S + 1) % 4096), ref.picture(R0, c0, px, py))
    assert n1 > 1000, "decode at S + 1 matches too (%d px differ): the check cannot fail" % n1
    out = ["S+1 differs in %d px" % n1]
    for name, v in (("bz_c0", c0 + 1), ("bz_R0", R0 + 1)):
        g.put(name, v)
        try:
            n2, _ = diff(g.decode(g.w("bz_S")), ref.picture(*g.state()[1:]))
        finally:
            g.put(name, c0 if name == "bz_c0" else R0)
        assert n2 > 1000, "a poked %s still matches (%d px differ): the check cannot fail" % (name, n2)
        out.append("%s+1 poked differs in %d px" % (name, n2))
    assert g.state() == st, "the poked camera was not put back"
    return ", ".join(out)


def run(tag, apps=None, src=None, art=None):
    sym = symbols(src, art)
    ref = Ref(tag)
    with os88ui.boot(at("build/os8088-360.img"), apps=apps or at("build/bonanza360.img"),
                     machine=MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = Bz(ui, tag, sym)
        ui.settle()
        glass(g, ref)
        return bench(g, ref)


def verdict(tag, r):
    missing = [d for d in DIRS if not r["done"][d]]
    bad = list(r["fails"])
    if missing:
        bad.append("directions never checked: %s" % missing)
    if not r["full"]:
        bad.append("the first frame's full write was not checked")
    if not r["controls"] and not r["fails"]:
        bad.append("no diagonal frame for the negative controls")
    return bad


# ---- the red arm ---------------------------------------------------------------
REDS = {
    # the entering column moving right: the window's column W (not W - 1)
    "colright": ("bzgame.inc", "    add ax, [bz_W]              ; moving right: the right edge's\n    dec ax\n",
                 "    add ax, [bz_W]              ; moving right: the right edge's\n"),
    # the entering column before the retrace and the flip: the same bytes in the end
    "colfirst": None,
    # every frame counted late: the bz_rlate assertion's own red
    "late": ("bzgame.inc", "bz_presented:\n    call bz_mark\n",
             "bz_presented:\n    call bz_mark\n    inc word [bz_late]\n"),
}


def red_tree(name, td):
    src = os.path.join(td, "bonanza")
    shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
    gp = os.path.join(src, "bzgame.inc")
    t = open(gp).read()
    if name in ("colright", "late"):
        _, old, new = REDS[name]
        assert t.count(old) == 1, "the %s anchor moved: re-anchor the red arm" % name
        t = t.replace(old, new)
    else:
        # colfirst: at bz_tv, write the whole entering column (from the window's top) and
        # then let bz_tf skip its own column write
        old_tv = "bz_tv:\n    mov bx, 2 * 4\n    call bz_mark\n"
        old_col = ".col:\n    mov ax, [bz_dc]\n    or ax, ax\n    jz bz_tb\n"
        assert t.count(old_tv) == 1 and t.count(old_col) == 1, "the colfirst anchors moved: re-anchor"
        t = t.replace(old_tv, old_tv +
                      "    cmp byte [bz_full], 0\n    jne .redskip\n    mov ax, [bz_dc]\n    or ax, ax\n"
                      "    jz .redskip\n    mov ax, [bz_c0n]\n    js .redl\n    add ax, [bz_W]\n    dec ax\n"
                      ".redl:\n    xor bx, bx\n    mov cx, [bz_H]\n    call bz_col\n.redskip:\n")
        t = t.replace(old_col, ".col:\n    jmp bz_tb\n")
    open(gp, "w").write(t)
    art = at("build/bonanza-art")
    binp, o88, img = (os.path.join(td, n) for n in ("bonanza.bin", "BONANZA.O88", "bonanza360.img"))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", src + "/",
                    "-I", art + "/", "-o", binp, os.path.join(src, "bonanza.asm")], cwd=ROOT, check=True)
    parts = []
    for p in ("BZCRSC.BIN", "BZCRSH.BIN", "BZBALC.BIN", "BZBALH.BIN"):
        parts += ["--part", os.path.join(art, p)]
    subprocess.run(["python3", "tools/os88pkg.py", "--compress-if=lz4", binp, "-o", o88] + parts,
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["python3", "tools/os88disk.py", "-o", img, "--size", "360", o88], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    return src, img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--red", choices=sorted(REDS))
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = red_tree(a.red, td)
            for tag in tags:
                try:
                    r = run(tag, apps=img, src=src)
                    bad = verdict(tag, r)
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
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
