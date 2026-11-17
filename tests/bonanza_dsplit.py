#!/usr/bin/env python3
"""BONANZA's SPLIT CELLS in the guest (SPEC.md 128.24, wave D3): the package's
own routines under unicorn against tools/bbcourse.py's model, on courses that
use halves and quarters - the host half of bonanzaphys's split leg (no shipped
course has a split cell until the diagonal plan's D5).

    make bonanza && python3 tests/bonanza_dsplit.py [--runs N] [--seed S] [--price]

THE METHOD is bonanza_path.py --check's: the package image assembled from the
tree (tests/bonanza_ring.py assemble, symbols), loaded at one segment of an
emulated 8086, a course's RAM form (bbcourse's compile, the bytes bz_cexp
leaves) at another, and its routines CALLED - bz_crshdr, bz_pinit, then
bz_step once a step - while bbcourse.Physics, the model SPEC.md 128.24.7 binds
the guest to, steps the same key bytes.  After EVERY step the guest's state is
read out of its own bss and compared EXACTLY with the model's (state, state2,
state6, bz_ps, the goal and its exit, the respawns): no tolerance.

  1  CELLS (D3.1): bz_cexp on each split course's STORED form equals its RAM
     form - bz_cxcel's NEAR and bz_cxsafe's SAFE read a split cell's records
     (128.24.5.3).
  2  SCRIPTED runs (D3.3), the model's own scenarios of `--selfcheck` item 7
     (_split_physics) and more: a roll off a diagonal edge (the take-off at
     the pick), a fall into a VOID half (its kill height), a goal half and its
     exit, a slide up the lane's rail (DIAG or DIAG + 1, no kick), a head-on
     hit, a wall's END met radially, the edges by their owning half, a
     quartered cell's line and its centre, R7's push out of a quartered cell
     (THE NOTCH), a fall off a diagonal step, a landing on one; a windmill's
     doorway knock and capture with a split cell in the window (THE MILLS).
  3  FUZZ: N runs from random states near split cells - on THE EDGE (split
     cells on the grid's edges) and THE MILLS (MILL's props beside split
     cells) as well as the four split courses - (position, velocity,
     airborne or grounded, material) under random held keys - every step.
  4  A COURSE WITH NO SPLIT CELL (TRIAL): the same comparison, and bz_ps bit
     3 never set (the split path never entered).

--price: each run's bz_step instructions priced by 128.11.15's method
(max(EU + EA, 4.34 x bytes), 8088 word operands) from the listing, the
split runs against the same steps on whole cells (SPEC.md 128.24.7.6).
"""
import argparse
import os
import random
import re
import shutil
import subprocess
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402

CS, PS, SS, STUB = 0x1000, 0x3000, 0x7000, 0xFFF0

# THE NOTCH (R7, verify-dtool's): a floor N quarter between WALL W and E quarters; a ball rolled down the W
# quarter's line from the cell above is pushed out of the cell by the FIRST line (nothing more of C's then)
NOTCH = ('course NOTCH "Notch"\nwidth 128\nfloor rect 5 5 18 18 flat 0\n'
         'wall quarter w tile 10 10 flat 1.5\nwall quarter e tile 10 10 flat 1.5\nstart 7 14\n')
# THE STEPS: diagonal steps between heights, both diagonals, quarters at two heights, a VOID quarter, a bumper
# half, a sloped half (the slopes the pick hands step 2), and the edges a ball meets from every side
STEPS = ('course STEPS "Steps"\nwidth 128\nfloor rect 4 4 19 19 flat 0\n'
         'floor half up tile 8 8 flat 1\nfloor half right tile 9 8 flat 1\nfloor half left tile 10 8 flat 0.5\n'
         'floor half down tile 8 9 flat 1.5\nfloor quarter n tile 11 11 flat 1\nfloor quarter s tile 11 11 flat 0.5\n'
         'hole quarter e tile 12 11\nwall half right tile 12 12 flat 2\nsurface bounce tile 12 12\n'
         'floor half left tile 13 9 ramp x 12 14 0 1\nfloor half up tile 9 12 ramp y 11 13 0 1\n'
         'floor box -1 2 26 31 flat 1\nwall quarter w tile 9 14 flat 1.5\nwall quarter n tile 10 14 flat 1.5\n'
         'hole half down tile 6 13\nhole quarter w tile 15 7\nstart 6 6\n')

# THE EDGE (verify-dguest): split cells on the grid's own edges - the window's out-of-grid cells OPEN beside them
EDGE = ('course EDGE "Edge"\nwidth 64\nfloor rect 3 3 9 9 flat 0\nfloor half up tile 3 3 flat 0.5\n'
        'hole half left tile 3 6\nwall quarter n tile 6 3 flat 1\nwall quarter w tile 3 7 flat 1\n'
        'floor half down tile 8 8 flat 0.5\nhole quarter e tile 8 5\nfloor half right tile 8 3 flat 0.5\n'
        'hole half up tile 5 8\nstart 5 5\n')
# THE MILLS (verify-dguest): MILL's props (both windmills, three bumpers, the tubes, the lift) with split cells
# beside them and GOAL pieces inside the windmills' 3 x 3 (the doorway with a split cell in the window)
MILLS_EXTRA = ("goal half right tile 8 10 flat 16\ngoal quarter e tile 10 10 flat 16\n"
               "wall half left tile 13 20 flat 9\nfloor half down tile 15 21 flat 8.5\n"
               "floor half up tile 17 19 flat 8.5\nfloor quarter n tile 15 18 flat 8.5\n"
               "floor half right tile 28 19 flat -3.5\nhole half up tile 21 21\n"
               "floor half right tile 11 10 flat 15.5\nfloor quarter e tile 10 12 flat 15.5\n"
               "floor half down tile 22 21 flat 2.5\n")


def mills():
    return open(os.path.join(ROOT, "apps", "bonanza", "courses", "mill.bbc")).read().replace(
        "\nstart 9 12", "\n" + MILLS_EXTRA + "start 9 12")


class Guest:
    """the package under unicorn: CS = DS = the image, the course part at PS"""

    def __init__(self, binp, sym, part):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE
        from unicorn import x86_const as X
        self.X, self.sym = X, sym
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x100000)
        self.image = open(binp, "rb").read()
        self.mu.mem_write(CS * 16, self.image)
        self.mu.mem_write(PS * 16, bytes(part))
        self.mu.mem_write(CS * 16 + STUB, b"\xf4")
        self.trace = None
        self.mu.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, mu, addr, size, ud):
        if self.trace is not None:
            self.trace.append((addr - CS * 16, size))

    def w(self, n, v, sz=1):
        self.mu.mem_write(CS * 16 + self.sym[n], (v & ((1 << 8 * sz) - 1)).to_bytes(sz, "little"))

    def r(self, n, sz=1, signed=False, k=0):
        return int.from_bytes(self.mu.mem_read(CS * 16 + self.sym[n] + k, sz), "little", signed=signed)

    def call(self, n, ax=0):
        X = self.X
        for reg, v in ((X.UC_X86_REG_CS, CS), (X.UC_X86_REG_DS, CS), (X.UC_X86_REG_ES, CS), (X.UC_X86_REG_SS, SS)):
            self.mu.reg_write(reg, v)
        self.mu.mem_write(SS * 16 + 0xFFEE, struct.pack("<H", STUB))
        self.mu.reg_write(X.UC_X86_REG_SP, 0xFFEE)
        self.mu.reg_write(X.UC_X86_REG_AX, ax)
        self.mu.reg_write(X.UC_X86_REG_EFLAGS, 2)
        self.mu.emu_start(CS * 16 + self.sym[n], CS * 16 + STUB, count=2000000)
        assert self.mu.reg_read(X.UC_X86_REG_SP) == 0xFFF0, "%s left the stack unbalanced" % n


def build(td, patches=()):
    """the package assembled from this tree (PATCHES applied to a copy: a red arm's) against the build's art
    -> (image path, symbols)"""
    binp = os.path.join(td, "bonanza.bin")
    art = R.at("build/bonanza-art")
    src = os.path.join(ROOT, "apps", "bonanza")
    if patches:
        src = os.path.join(td, "bonanza")
        shutil.copytree(os.path.join(ROOT, "apps", "bonanza"), src)
        R.patch_tree(src, patches)
    R.assemble(src, art, binp)
    return binp, R.symbols(src if patches else None, art)


def start(binp, sym, c, mat):
    """the guest launched on course C (its RAM form) with material MAT, a PLAY (no log written, no limit) ->
    Guest; and the model's Physics on the same course"""
    g = Guest(binp, sym, c.cga)
    g.w("bz_cseg", PS, 2)
    if "bz_mseg" in g.sym:                      # (one part: in both words, as bz_cload leaves them, SPEC.md
        g.w("bz_mseg", PS, 2)                   # 128.30.5 - bz_crshdr's bz_osmake reads the picture's)
    g.call("bz_crshdr")
    p = BB.Physics(c, play=True, mat=mat)
    fam_load(g, p)
    g.w("bz_mode", 0)
    g.w("bz_mat", mat)
    g.w("bz_crs", 0)
    g.call("bz_pinit")
    g.w("bz_tsec", 0, 2)
    g.w("bz_rtr", 1)                            # (the recorder off: nothing physics reads)
    g.w("bz_tby", BB.TILT_KEYS)
    g.w("bz_apilot", 0)
    p = BB.Physics(c, play=True, mat=mat)
    p.tsec = 0
    return g, p


FS = 0x6000                                     # story 9.8: the family parts, one a 100h paragraphs from here


def fam_load(g, p):
    """story 9.8 (SPEC.md 128.25.20): the course's FAMILY PARTS (the build's bzf-<name>.bin) in memory and
    bz_frec / bz_fhk / bz_fnf as bz_ffetch leaves them (its own fetch is bonanza_phys's unicorn half's to
    prove): the windmill's doorway and the tube are the ROTOR and TUBE families' code now"""
    fhk, rec = 0, bytearray()
    for j, (fid, fv) in enumerate(p.grid.fams):
        f = BB.FAM_BY_ID[fid]
        seg = FS + 0x100 * j
        g.mu.mem_write(seg * 16, open(R.at("build/bzf-%s.bin" % f["name"]), "rb").read())
        rec += struct.pack("<HHBB", seg, seg, fid, fv)
        fhk |= f["hooks"]
    if rec:
        g.mu.mem_write(CS * 16 + g.sym["bz_frec"], bytes(rec))
    g.w("bz_fhk", fhk)
    g.w("bz_fnf", len(p.grid.fams))


def gstate(g):
    s = (g.r("bz_nstep", 4), g.r("bz_gx", 4), g.r("bz_gy", 4), g.r("bz_gz", 4, True), g.r("bz_gvx", 2, True),
         g.r("bz_gvy", 2, True), g.r("bz_gvz", 2, True), g.r("bz_air"))
    s2 = (tuple(g.r("bz_lvl", k=i) for i in range(4)), g.r("bz_hopw"), g.r("bz_kprev"), g.r("bz_mst"), g.r("bz_mct"),
          g.r("bz_sqf"), g.r("bz_lvz", 2))
    s6 = (g.r("bz_btok"), g.r("bz_stf"), g.r("bz_nboost", 2), g.r("bz_drx"), g.r("bz_dry"), g.r("bz_bgr"),
          g.r("bz_bgd", 2, True), g.r("bz_bsp"))
    ex = (g.r("bz_ps"), g.r("bz_goal"), g.r("bz_exit") if g.r("bz_goal") else 0, g.r("bz_nfall", 2),
          g.r("bz_nland", 2), g.r("bz_safe", 2))
    return s, s2, s6, ex


def mstate(p):
    return p.state(), p.state2(), p.state6(), (p.ps, p.goal, p.exit if p.goal else 0, p.nfall, p.nland,
                                               p.safe[0] | p.safe[1] << 8)


def poke(g, p, wx, wy, pu, pv, gvx=0, gvy=0, air=0, gz=None):
    """the ball at in-cell (pu, pv) of (wx, wy) (1/256 gu) on its record's floor (or gz, 24.8 px), at
    (gvx, gvy): the model's _split_physics `at`, and the guest's bss with bz_pokd (its next step refills)"""
    p.gx, p.gy = (16 * wx << 8) + pu, (16 * wy << 8) + pv
    if gz is None:
        rec = p.prec(wx, wy)
        gz = BB.Physics.h4(rec, pu >> 8, pv >> 8) << 6
    p.gz, p.gvx, p.gvy, p.gvz, p.air = gz, gvx, gvy, 0, air
    p.drx = p.dry = 0
    p._fill(wx, wy)
    p._derive(True)
    for n, v, sz in (("bz_gx", p.gx, 4), ("bz_gy", p.gy, 4), ("bz_gz", gz, 4), ("bz_gvx", gvx, 2),
                     ("bz_gvy", gvy, 2), ("bz_gvz", 0, 2), ("bz_air", air, 1), ("bz_pokd", 1, 1)):
        g.w(n, v, sz)


def run(g, p, keys, label, stop_goal=True, trace=None):
    """step both through KEYS (a key byte a step), comparing after every step -> (None or the first
    difference, steps run, the events)"""
    e0 = len(p.events)
    for i, k in enumerate(keys):
        g.w("bz_keys", k)
        g.w("bz_tilt", BB.TILT_KEYS)
        if trace is not None:
            g.trace = []
        g.call("bz_step")
        if trace is not None:
            trace.append(g.trace)
            g.trace = None
        p.step(k)
        a, b = gstate(g), mstate(p)
        if a != b:
            names = ("state", "state2", "state6", "ps/goal/exit/nfall/nland/safe")
            diff = "; ".join("%s guest %s model %s" % (n, x, y) for n, x, y in zip(names, a, b) if x != y)
            return "%s: step %d (key %02Xh): %s; events %s" % (label, p.nstep, k, diff, p.events[e0:][-4:]), i + 1, \
                p.events[e0:]
        if stop_goal and p.goal:
            break
    return None, len(keys), p.events[e0:]


def hold(k, n):
    return [k] * n


# ---- the scripted runs (SPEC.md 128.24.11, the model's own _split_physics and more) ---------------------------

def scripted():
    """(label, course key, material, poke args, keys, the events it must raise)"""
    K = BB
    U, D, L, Rt, H = K.K_U, K.K_D, K.K_L, K.K_R, K.K_HOP
    rub, stl, gls = K.MAT_RUBBER, K.MAT_STEEL, K.MAT_GLASS
    return [
        ("takeoff: off a diagonal edge at the pick", "rail", rub, (17, 10, 6 << 8, 8 << 8, 32, -32), hold(0, 40),
         ("takeoff",)),
        ("fall: into a VOID half, its kill height", "rail", rub, (17, 10, 12 << 8, 3 << 8, 0, 0, 1, 8 << 8),
         hold(0, 80), ()),
        ("goal: a GOAL half and its exit", "rail", rub, (15, 8, 8 << 8, 8 << 8, -192, 0), hold(0, 120), ("goal",)),
        ("slide: up the lane's left rail", "split", rub, (12, 12, 2048, 2048), hold(U | L, 150), ("diag",)),
        ("slide steel: up the right rail", "split", stl, (12, 12, 2048, 2048), hold(U | Rt, 150), ("diag",)),
        ("headon: into the left rail", "split", rub, (12, 12, 2048, 2048, -200, 200), hold(0, 40), ("diag",)),
        ("tip: a wall's END met radially", "rail", rub, (14, 13, 2 << 8, 10 << 8, -160, -160), hold(0, 40),
         ("corner",)),
        ("own: the edge by its owning half", "split", rub, (12, 12, 2048, 2048, -300, 0), hold(0, 30), ("diag",)),
        ("quarter: the W quarter's line L - c", "rail", rub, (8, 14, 2 << 8, 6 << 8, 100, 100), hold(0, 30),
         ("diag",)),
        ("centre: the opposite quarter met radially", "rail", rub, (8, 14, 8 << 8, 1 << 8, 0, 100), hold(0, 30),
         ("centre",)),
        ("notch: R7, pushed out of a quartered cell", "notch", rub, (10, 9, 3 << 8, 6 << 8, 60, 260), hold(D, 60),
         ("diag",)),
        ("stepdown: off a diagonal step", "split", rub, (12, 13, 2048, 2048), hold(U, 120), ()),
        ("stepup: a Hop onto a diagonal step", "split", rub, (12, 18, 2048, 2048), hold(U, 20) + [U | H] + hold(U, 80),
         ()),
        ("glass: shattered off a ledge, respawned", "steps", gls, (8, 9, 8 << 8, 14 << 8, 0, 0, 1, 40 << 8),
         hold(0, 90), ()),
        ("bumper half", "steps", stl, (11, 12, 8 << 8, 8 << 8, 250, 0), hold(Rt, 60), ()),
        ("slopes: a ramped half under step 2", "steps", rub, (13, 9, 4 << 8, 10 << 8, 0, 0), hold(Rt, 60), ()),
        ("chamfer: a box's quartered corners", "split", rub, (14, 7, 8 << 8, 8 << 8, 0, 0), hold(Rt | U, 80), ()),
        ("undo: a line pushes the centre into a blocking cell, back to the START", "steps", rub,
         (9, 14, 1024, 3072, 0, -200), hold(0, 30), ("undo",)),
        ("doorway: a windmill's knock, a split cell in the window", "mills", rub, (9, 10, 2048, 2048, 0, -250),
         hold(U, 60), ("knock",)),
        ("doorway: a windmill's capture beside split cells", "mills", rub, (9, 9, 2048, 2048, 0, -250), hold(U, 60),
         ("capture",)),
    ]


def courses():
    """the six test courses, compiled (independent of each other: a core each, BB.par_map; the first refusal
    in this order raised)"""
    kt = (("split", BB._SPLIT), ("rail", BB._RAIL), ("notch", NOTCH), ("steps", STEPS), ("edge", EDGE),
          ("mills", mills()))
    got = BB.par_map(lambda kt_: BB.compile_course(kt_[1], "<%s>" % kt_[0].upper(), _hack={"no_finish": True}), kt)
    for _c, e in got:
        if e is not None:
            raise e
    return {k: c for (k, _t), (c, _e) in zip(kt, got)}


def cells_check(binp, sym, cs):
    """D3.1: the package's bz_cexp on each split course's STORED form -> its RAM form"""
    bad = []
    for k, c in cs.items():
        g = Guest(binp, sym, c.stored)
        g.w("bz_cseg", PS, 2)
        g.call("bz_cexp")
        got = bytes(g.mu.mem_read(PS * 16, len(c.cga)))
        if got != c.cga:
            i = next(j for j in range(len(got)) if got[j] != c.cga[j])
            bad.append("%s: bz_cexp's RAM form differs from the tool's at offset %d" % (k, i))
    return bad


def notch_sweep(binp, sym, c):
    """R7 (verify-dtool's): the model's own NOTCH sweep (bbcourse _split_physics) - a ball rolled down a WALL
    quarter's line out of the cell above, 192 starts x 30 steps - guest against model at every step; and how
    many of those runs the OLD model (_inner_on: the second line read on the new cell) parts from -> (the first
    difference or None, steps, runs the rule changes)"""
    steps, changed = 0, 0
    for gvy in (180, 260, 320):
        for gvx in (-200, -50, 0, 50):
            for pu in range(0, 4096, 256):
                g, p = start(binp, sym, c, BB.MAT_RUBBER)
                q = BB.Physics(c, play=True, mat=BB.MAT_RUBBER, _inner_on=True)
                q.tsec = 0
                poke(g, p, 10, 9, pu, 2000, gvx, gvy)
                q.gx, q.gy, q.gz, q.gvx, q.gvy, q.gvz, q.air = p.gx, p.gy, p.gz, gvx, gvy, 0, 0
                q.drx = q.dry = 0
                q._fill(10, 9)
                err, ns, _ = run(g, p, hold(0, 30), "notch pu %d gvx %d gvy %d" % (pu, gvx, gvy))
                for _ in range(ns):
                    q.step(0)
                changed += q.state() != p.state()
                steps += ns
                if err:
                    return err, steps, changed
    return None, steps, changed


def hostile(binp, sym, c):
    """128.24.5.2's bound on a HOSTILE part: the stored form with one split cell's offset pointed past the part's
    end, one aligned wrong and one record's kind made a split's; bz_cexp under unicorn with every read and write
    of the course's segment watched -> [complaints]"""
    from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    st = bytearray(c.stored)
    g0 = struct.unpack_from("<H", st, 26)[0]
    nrows, smin, amin, kw = struct.unpack_from("<HhhH", st, g0 + 4)
    diroff, nsec = struct.unpack_from("<HH", st, 38)
    sec = {}
    for j in range(nsec):
        tag, form, off, ln, dl = struct.unpack_from("<BBHHH", st, diroff + 8 * j)
        sec[chr(tag)] = (off, ln)
    co, cl = sec["C"]
    do, dl_ = sec["D"]
    splits = [i for i in range(co, co + cl, 4) if st[i + 2] & 15 in BB.SPLIT_KINDS]
    a, b = splits[0], splits[1]
    struct.pack_into("<H", st, a, do + 4 * ((0xF000 - do) // 4))   # past the part, on D's 4-byte grid
    struct.pack_into("<H", st, b, do + 2)              # inside D, not on a record
    st[do + 2] = (st[do + 2] & 0xF0) | BB.KIND_TB      # a record of a split's kind
    g = Guest(binp, sym, st)
    lo, hi = PS * 16, PS * 16 + len(st)
    bad = []

    def watch(mu, access, addr, size, value, ud):
        if 0x10000 <= addr < 0xF0000 and not lo <= addr < hi and not CS * 16 <= addr < CS * 16 + 0x10000 \
                and not SS * 16 <= addr < SS * 16 + 0x10000:
            bad.append("an access at %05Xh, outside the part" % addr)
    g.mu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, watch)
    g.w("bz_cseg", PS, 2)
    g.call("bz_cexp")
    ram = bytes(g.mu.mem_read(PS * 16, len(st)))
    if ram[a:a + 4] != bytes((0x80, 0, 0, 0)) or ram[b:b + 4] != bytes((0x80, 0, 0, 0)):
        bad.append("the two bad cells are %s, %s - not OPEN" % (ram[a:a + 4].hex(), ram[b:b + 4].hex()))
    if ram[do + 2] & 15:
        bad.append("the split-kind record is kind %d, not VOID" % (ram[do + 2] & 15))
    good = [i for i in splits[2:] if ram[i:i + 4] != c.cga[i:i + 4]]
    if good:
        bad.append("a good split cell changed: offsets %s" % good[:3])
    return bad[:4]


# the red arms (SPEC.md 128.24.11, the plan's D3.1 and D3.3): each is a broken copy of the package the check
# must find - (file, old, new) as bonanza_ring.patch_tree takes them
REDS = {
    # D3.1: the SAFE rule without halves - a split edge neighbour read as a whole cell
    "cellhalves": [("bonanza.asm", "    cmp ah, BZ_KTB              ; split one whose record that OWNS the edge is\n"
                  "    jae .vs                     ; (128.24.5.3; BZ_SPLIT_WIN, the model's OWNER).\n",
                  "    cmp ah, BZ_KTB              ; RED cellhalves: a split neighbour read whole\n")],
    # D3.3: the corner ray dropped
    "noray": [("bzphys.inc", "    call bz_dray\n    cmp byte [bz_sfb], 0\n",
               "    mov byte [bz_sfb], 0        ; RED noray: no corner ray\n    mov word [bz_sor], 0\n"
               "    cmp byte [bz_sfb], 0\n")],
    # R7: a quartered cell's second line read after a push out of the cell
    "r7": [("bzphys.inc", "    call bz_dset\n    jnc .lx\n    mov ax, [bz_gx + 1]         ; R7: out of the cell",
            "    call bz_dset\n    jmp short .lx               ; RED r7\n    mov ax, [bz_gx + 1]         ; R7: out of"
            " the cell")],
    # the split centre's START (verify-dguest): bz_dinner's first push does not take it - a push that carries
    # the centre into another cell then undoes to a stale START
    "nostart": [("bzphys.inc", "    cmp byte [bz_dsn], 0        ; bz_dinner's first push: the step's START\n"
                 "    je .h0 ", "    cmp byte [bz_dsn], 0        ; RED nostart\n    jmp short .h0 ")],
    # 128.24.5.2: the hostile bound dropped (bz_drec accepts every offset)
    "nobound": [("bonanza.asm", "    cmp ax, [bz_dhi]\n    ja .bad\n", "    cmp ax, [bz_dhi]  ; RED nobound\n")],
}


def near_split(c, rnd):
    """a random cell within one of a split cell (its RAM form's), and an in-cell point"""
    grid = BB.Grid(c.cga, c.wcga)
    cells = []
    for wx in range(64):
        for wy in range(64):
            try:
                cc = grid.cell(wx, wy)
            except Exception:
                continue
            if cc[3] in BB.SPLIT_KINDS:
                cells.append((wx, wy))
    wx, wy = rnd.choice(cells)
    return wx + rnd.randint(-1, 1), wy + rnd.randint(-1, 1), rnd.randrange(4096), rnd.randrange(4096)


def fuzz(binp, sym, cs, n, seed):
    rnd = random.Random(seed)
    bad, steps, kinds = [], 0, {}
    names = sorted(cs)
    for i in range(n):
        k = names[i % len(names)]
        c = cs[k]
        mat = rnd.choice((BB.MAT_RUBBER, BB.MAT_STEEL, BB.MAT_GLASS))
        g, p = start(binp, sym, c, mat)
        for _ in range(20):
            wx, wy, pu, pv = near_split(c, rnd)
            rec = p.prec(wx, wy) if 0 <= wx < 64 and 0 <= wy < 64 else None
            if rec is not None and rec[3] in (BB.KIND_FLOOR, BB.KIND_GOAL):
                break
        else:
            continue
        air = rnd.random() < 0.3
        gz = ((BB.Physics.h4(rec, pu >> 8, pv >> 8) << 6) + (rnd.randrange(1, 40) << 8)) if air else None
        v = BB.VMAXG
        poke(g, p, wx, wy, pu, pv, rnd.randrange(-v, v + 1), rnd.randrange(-v, v + 1), int(air), gz)
        keys = []
        while len(keys) < 160:
            kb = rnd.choice((0, BB.K_U, BB.K_D, BB.K_L, BB.K_R, BB.K_U | BB.K_L, BB.K_U | BB.K_R, BB.K_D | BB.K_L,
                             BB.K_D | BB.K_R, BB.K_HOP, BB.K_GRIP))
            keys += [kb] * rnd.randrange(1, 30)
        err, ns, ev = run(g, p, keys[:160], "fuzz %d (%s, %s, (%d, %d) %d %d)" % (i, k, BB.MAT_NAMES[mat], wx, wy,
                                                                                    pu, pv))
        steps += ns
        for e in ev:
            kk = e[0] + (":" + e[2] if e[0] == "diag" else "")
            kinds[kk] = kinds.get(kk, 0) + 1
        if err:
            bad.append(err)
    return bad, steps, kinds


# ---- D3.4: the price (128.11.15's method) -----------------------------------------------------------------
# 8086 clocks (Intel's tables), each instruction at max(EU + EA, 4 x its bytes), the 8088's +4 a WORD memory
# transfer (a read-modify-write twice), as 128.11.15 priced wave 2's step: an ESTIMATE of the instruction
# stream, not a measurement (bonanzaperf measures)
_EA = {"d": 6, "b": 5, "bd": 9, "bx+si": 7, "bp+di": 7, "bx+di": 8, "bp+si": 8, "bid": 11}
_R8 = {"al", "ah", "bl", "bh", "cl", "ch", "dl", "dh"}
_R16 = {"ax", "bx", "cx", "dx", "si", "di", "bp", "sp"}
_SREG = {"cs", "ds", "es", "ss"}


def _ea(m):
    """a memory operand's EA clocks"""
    s = m.replace(" ", "").lower()
    seg = 2 if re.search(r"\b[cdes]s:", s) else 0
    s = re.sub(r"^.*\[|\].*$", "", s)
    regs = [r for r in re.split(r"[+-]", s) if r in _R16]
    disp = any(not (x in _R16) for x in re.split(r"[+-]", s) if x)
    if not regs:
        return 6 + seg
    if len(regs) == 1:
        return (9 if disp else 5) + seg
    k = "+".join(sorted(regs, key=lambda r: ("bx", "bp", "si", "di").index(r)))
    return (_EA.get(k, 8) + (4 if disp else 0)) + seg


def price_line(text, nbytes, taken=False):
    """one instruction's clocks, 128.11.15's method"""
    s = text.split(";")[0].strip().lower()
    s = re.sub(r"^(\.\w+:|\w+:)\s*", "", s)
    if not s:
        return 0
    m = re.match(r"(rep\s+)?(\w+)\s*(.*)", s)
    rep, op, rest = m.group(1), m.group(2), m.group(3)
    ops = [o.strip() for o in re.split(r",(?![^\[]*\])", rest)] if rest else []
    mem = [o for o in ops if "[" in o]
    word = (any(o in _R16 for o in ops) or "word" in rest) and "byte" not in rest
    ea = _ea(mem[0]) if mem else 0
    w = 4 if (mem and word) else 0                  # the 8088's word transfer
    imm = len(ops) == 2 and not ("[" in ops[1] or ops[1] in _R8 | _R16 | _SREG)
    if op in ("jmp",):
        eu = 15
    elif op.startswith("j") or op == "loop":
        eu = (16 if op != "loop" else 17) if taken else (4 if op != "loop" else 5)
    elif op == "call":
        eu = 23
    elif op == "ret":
        eu = 20
    elif op == "push":
        eu = 15 if not mem else 24 + ea
    elif op == "pop":
        eu = 12 if not mem else 25 + ea
    elif op in ("pushf", "popf"):
        eu = 14 if op == "pushf" else 12
    elif op == "mov":
        if not mem:
            eu = 4 if imm else 2
        elif "[" in ops[0]:
            eu = (10 + ea if imm else 9 + ea) + w
            if not imm and ops[1] in ("al", "ax") and re.fullmatch(r"\[[^\]+]*\]", ops[0].replace(" ", "")):
                eu = 10 + w
        else:
            eu = 8 + ea + w
            if ops[0] in ("al", "ax") and re.fullmatch(r"\[[^\]+]*\]", ops[1].replace(" ", "")):
                eu = 10 + w
    elif op in ("add", "sub", "and", "or", "xor", "adc", "sbb", "cmp", "test"):
        rmw = op not in ("cmp", "test")
        if not mem:
            eu = 4 if imm else 3
        elif "[" in ops[0]:
            eu = ((17 if rmw else 10) + ea if imm else (16 if rmw else 9) + ea) + (2 * w if rmw else w)
        else:
            eu = 9 + ea + w
    elif op in ("inc", "dec"):
        eu = (15 + ea + 2 * w) if mem else (2 if ops[0] in _R16 else 3)
    elif op in ("neg", "not"):
        eu = (16 + ea + 2 * w) if mem else 3
    elif op in ("shl", "shr", "sar", "rol", "ror", "rcl", "rcr", "sal"):
        eu = (15 + ea + 2 * w) if mem else (2 if ops[1] == "1" else 8 + 4 * 4)
    elif op in ("mul", "imul"):
        eu = (74 if op == "mul" else 89) if not word else (128 if op == "mul" else 141)
        eu += ea + w
    elif op in ("cbw",):
        eu = 2
    elif op == "cwd":
        eu = 5
    elif op == "xchg":
        eu = (17 + ea + 2 * w) if mem else (3 if "ax" in ops else 4)
    elif op == "lea":
        eu = 2 + ea
    elif op in ("clc", "stc", "cld", "std", "cli", "sti", "cmc", "nop"):
        eu = 2
    elif op == "xlat":
        eu = 11
    elif op in ("lodsb", "lodsw"):
        eu = 12 + (4 if op[-1] == "w" else 0)
    elif op in ("stosb", "stosw"):
        eu = 11 + (4 if op[-1] == "w" else 0)
    elif op in ("movsb", "movsw"):
        eu = 18 + (8 if op[-1] == "w" else 0)
    elif op == "jcxz":
        eu = 18 if taken else 6
    else:
        raise ValueError("unpriced: %r" % text)
    return max(eu, 4 * nbytes)


def listing(td, patches=()):
    """address -> the instruction's source text, off nasm's listing of the tree"""
    src = os.path.join(ROOT, "apps", "bonanza") if not patches else os.path.join(td, "bonanza")
    lst = os.path.join(td, "bonanza.lst")
    art = R.at("build/bonanza-art")
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps") + "/", "-I", src + "/",
                    "-I", art + "/", "-o", os.path.join(td, "lst.bin"), "-l", lst, os.path.join(src, "bonanza.asm")],
                   cwd=ROOT, check=True)
    out = {}
    for ln in open(lst, errors="replace"):
        m = re.match(r"\s*\d+\s+([0-9A-F]{8})\s+([0-9A-F\[\]()]+)-?\s+(?:<\d+>)?(.*)$", ln.rstrip("\n"))
        if m:
            a = int(m.group(1), 16)
            if a not in out:
                out[a] = m.group(3)
                n = len(re.sub(r"[\[\]()]", "", m.group(2))) // 2
                op = m.group(3).split(";")[0].split()
                if n == 5 and op and op[0].lower().startswith("j"):     # nasm's long Jcc: Jncc +3, JMP NEAR
                    out[a + 2] = "jmp near"
    return out


def price(trace, lst):
    """a step's instruction trace [(address, size)] -> clocks (a conditional jump TAKEN when the next
    instruction is not the one after it)"""
    clk = 0
    for i, (a, sz) in enumerate(trace):
        nxt = trace[i + 1][0] if i + 1 < len(trace) else None
        tx = lst.get(a, "")
        if not tx.split(";")[0].strip() and a != STUB:
            raise ValueError("no listing line for the executed %04Xh" % a)
        clk += price_line(tx, sz, taken=nxt is not None and nxt != a + sz)
    return clk


def check(n=200, seed=1124, verbose=True, patches=()):
    """-> [complaints]; prints the evidence"""
    out = []
    with tempfile.TemporaryDirectory() as td:
        binp, sym = build(td, patches)
        cs = courses()
        b = hostile(binp, sym, cs["split"])
        print("bonanza_dsplit 128.24.5.2 HOSTILE: a part with a split cell's offset past its end, one off a record "
              "and a split-kind record: bz_cexp %s" % ("; ".join(b) or "reads and writes nothing outside the part, "
                                                       "makes the two cells OPEN and the record VOID"))
        out += b
        err, ns, ch = notch_sweep(binp, sym, cs["notch"])
        print("bonanza_dsplit R7 NOTCH sweep: 192 runs, %d steps: %s; the rule changes %d runs (the old model's "
              "second line)" % (ns, err or "every step equal", ch))
        if err:
            out.append(err)
        if not ch:
            out.append("the NOTCH sweep never reaches R7's push out of the cell")
        b = cells_check(binp, sym, cs)
        pth = R.at("build/bonanza-art/BZPATH.BIN")
        if os.path.exists(pth):                     # the SHIPPED pathway part (D4's halves): the guest's
            st = open(pth, "rb").read()             # expander against the tool's
            g = Guest(binp, sym, st)
            g.w("bz_cseg", PS, 2)
            g.call("bz_cexp")
            same = bytes(g.mu.mem_read(PS * 16, len(st))) == BB.expand(st, "BZPATH")
            sp = bool(BB.Grid(BB.expand(st, "BZPATH")).gflags & BB.GF_SPLIT)
            print("bonanza_dsplit the shipped pathway part (%s split cells): bz_cexp %s" % (
                "with" if sp else "no", "is the tool's expand, byte for byte" if same else "DIFFERS"))
            if not same:
                b.append("BZPATH: the guest's bz_cexp differs from the tool's expand")
        print("bonanza_dsplit D3.1 CELLS: bz_cexp under unicorn on %s's stored forms -> %s" % (
            ", ".join(sorted(cs)), "; ".join(b) or "each its RAM form, byte for byte"))
        out += b
        for label, ck, mat, pk, keys, want in scripted():
            g, p = start(binp, sym, cs[ck], mat)
            poke(g, p, *pk)
            err, ns, ev = run(g, p, keys, label)
            got = sorted({e[0] + (":" + e[2] if e[0] == "diag" else "") for e in ev})
            miss = [w for w in want if not any(x.startswith(w) for x in got)]
            if err:
                out.append(err)
            elif miss:
                out.append("%s: the model raised %s, not %s: the run does not exercise what it names" % (
                    label, got, miss))
            if verbose:
                print("bonanza_dsplit %-45s %3d steps, events %s: %s" % (label, ns, ",".join(got) or "-",
                                                                       "FAIL" if err or miss else "every step equal"))
        b, steps, kinds = fuzz(binp, sym, cs, n, seed)
        print("bonanza_dsplit fuzz: %d runs, %d steps from random states near split cells (seed %d), the model's "
              "events %s: %s" % (n, steps, seed, kinds, "%d differ" % len(b) if b else "every step equal"))
        out += b[:10]
        c = R.course("trial")
        g, p = start(binp, sym, c, BB.MAT_RUBBER)
        rnd = random.Random(seed)
        keys = []
        while len(keys) < 2000:
            keys += [rnd.choice((0, BB.K_U, BB.K_D, BB.K_L, BB.K_R, BB.K_HOP))] * rnd.randrange(1, 40)
        err, ns, _ = run(g, p, keys[:2000], "TRIAL (no split cell)", stop_goal=True)
        never = g.r("bz_psp") == 0 and not BB.Grid(c.cga, c.wcga).gflags & BB.GF_SPLIT
        print("bonanza_dsplit TRIAL, no split cell: %d steps %s; bz_psp %d" % (
            ns, "every step equal" if not err else err, g.r("bz_psp")))
        if err:
            out.append(err)
        if not never:
            out.append("TRIAL: a course with no split cell set bz_psp or GF_SPLIT")
    return out


BASE = "0e0b0b5f3"                  # the guest before D3 (8r2/dtool's head: apps/bonanza untouched since 139009354)


def price_report(n, seed):
    """D3.4: every split run's steps priced from the instructions unicorn executed; TRIAL (no split cell) on
    this package and on BASE's, step for step"""
    with tempfile.TemporaryDirectory() as td:
        binp, sym = build(td)
        lst = listing(td)
        bt = os.path.join(td, "base")
        os.makedirs(bt)
        subprocess.run("git archive %s apps/bonanza | tar -x -C %s" % (BASE, bt), shell=True, cwd=ROOT, check=True)
        bsrc = os.path.join(bt, "apps", "bonanza")
        bbin = os.path.join(td, "base.bin")
        art = R.at("build/bonanza-art")
        R.assemble(bsrc, art, bbin)
        bsym = R.symbols(bsrc, art)
        blst_td = os.path.join(td, "bl")
        os.makedirs(blst_td)
        shutil.copytree(bsrc, os.path.join(blst_td, "bonanza"))
        blst = listing(blst_td, patches=True)
        # 1. a course with no split cell: TRIAL's and FIRST's play, this package against BASE's, step for step
        res = {}
        for crs in ("trial", "mill", "first"):
            c = R.course(crs)
            rnd = random.Random(seed)
            keys = []
            while len(keys) < 1500:
                keys += [rnd.choice((0, BB.K_U, BB.K_D, BB.K_L, BB.K_R, BB.K_HOP, BB.K_U | BB.K_R))] * \
                    rnd.randrange(1, 40)
            keys = keys[:1500]
            tr = {}
            for tag, b_, s_, l_ in (("new", binp, sym, lst), ("base", bbin, bsym, blst)):
                g, p = start(b_, s_, c, BB.MAT_RUBBER)
                out = []
                run(g, p, keys, crs, stop_goal=True, trace=out)
                tr[tag] = [price(x, l_) for x in out]
            d = [a - b for a, b in zip(tr["new"], tr["base"])]
            res[crs] = (len(d), sum(tr["base"]) / len(d), sum(d) / len(d), max(d), min(d),
                        sum(1 for x in d if x))
            print("bonanza_dsplit PRICE %s (no split cell, %d steps): BASE %.0f clk a step; D3 %+.1f clk a step "
                  "mean, %+d .. %+d, %d steps differ" % ((crs,) + res[crs][:1] + res[crs][1:]))
        # 2. split courses: each step's price by what it met (the four of 128.24.7.6's table)
        cs = {k: v for k, v in courses().items() if k in ("split", "rail", "notch", "steps")}
        cat = {}
        rnd = random.Random(seed)
        names = sorted(cs)
        for i in range(n):
            k = names[i % len(names)]
            c = cs[k]
            g, p = start(binp, sym, c, BB.MAT_RUBBER)
            wx, wy, pu, pv = near_split(c, rnd)
            rec = p.prec(wx, wy) if 0 <= wx < 64 and 0 <= wy < 64 else None
            if rec is None or rec[3] not in (BB.KIND_FLOOR, BB.KIND_GOAL):
                continue
            v = BB.VMAXG
            poke(g, p, wx, wy, pu, pv, rnd.randrange(-v, v + 1), rnd.randrange(-v, v + 1))
            keys = []
            while len(keys) < 120:
                keys += [rnd.choice((0, BB.K_U, BB.K_D, BB.K_L, BB.K_R, BB.K_U | BB.K_L))] * rnd.randrange(1, 30)
            out = []
            e0 = len(p.events)
            for kk in keys[:120]:
                g.w("bz_keys", kk)
                g.w("bz_tilt", BB.TILT_KEYS)
                g.trace = []
                ps0 = g.r("bz_ps")
                cq = BB.Grid(c.cga, c.wcga).cell(g.r("bz_gx", 2, k=1) >> 4, g.r("bz_gy", 2, k=1) >> 4)[3]
                g.call("bz_step")
                p.step(kk)
                ev = {e[0] + (":" + e[2] if e[0] == "diag" else "") for e in p.events[e0:] if e[1] == p.nstep}
                clk = price(g.trace, lst)
                g.trace = None
                if not ps0 & 8:
                    key = "no split cell in the window"
                elif ev & {"diag:in", "diag:ray", "centre", "corner"}:
                    key = "a diagonal contact (%s)" % ",".join(sorted(ev & {"diag:in", "diag:ray", "centre",
                                                                             "corner"}))
                elif cq == BB.KIND_Q:
                    key = "split window, the centre QUARTERED, no contact"
                elif cq in BB.SPLIT_KINDS:
                    key = "split window, the centre halved, no contact"
                else:
                    key = "split window, the centre whole, no contact"
                if ev & {"land", "bounce", "takeoff", "wall", "undo", "respawn", "hop"}:
                    key += " +other"
                cat.setdefault(key, []).append(clk)
        for key in sorted(cat):
            xs = cat[key]
            print("bonanza_dsplit PRICE split courses: %-58s %5d steps, mean %5.0f, max %5d clk" % (
                key, len(xs), sum(xs) / len(xs), max(xs)))
        return res, cat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1124)
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--reds", action="store_true", help="every red arm: each must go red")
    ap.add_argument("--price", action="store_true", help="D3.4: the steps priced (128.11.15's method)")
    a = ap.parse_args()
    if a.price:
        price_report(a.runs, a.seed)
        return
    if a.red or a.reds:
        for name in ([a.red] if a.red else sorted(REDS)):
            bad = check(a.runs, a.seed, verbose=False, patches=REDS[name])
            assert bad, "RED ARM %s: the check stayed GREEN against a broken package" % name
            print("bonanza_dsplit --red %s: went red (%d): %s" % (name, len(bad), bad[0][:160]))
        return
    bad = check(a.runs, a.seed)
    for b in bad:
        print("FAIL %s" % b)
    assert not bad, "%d difference(s) between the guest and the model" % len(bad)
    print("bonanza_dsplit: PASS")


if __name__ == "__main__":
    main()
