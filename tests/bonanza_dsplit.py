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
     (THE NOTCH), a fall off a diagonal step, a landing on one.
  3  FUZZ: N runs from random states near split cells (position, velocity,
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
import shutil
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
    g.call("bz_crshdr")
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
    ]


def courses():
    return {k: BB.compile_course(t, "<%s>" % k.upper(), _hack={"no_finish": True})
            for k, t in (("split", BB._SPLIT), ("rail", BB._RAIL), ("notch", NOTCH), ("steps", STEPS))}


def cells_check(binp, sym, cs):
    """D3.1: the package's bz_cexp on each split course's STORED form -> its RAM form"""
    bad = []
    for k, c in cs.items():
        g = Guest(binp, sym, c.stored4)
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
    st = bytearray(c.stored4)
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
    "cellsafe": [("bonanza.asm", "    cmp ah, BZ_KTB              ; split one whose record that OWNS the edge is\n"
                  "    jae .vs                     ; (128.24.5.3; BZ_SPLIT_WIN, the model's OWNER).\n",
                  "    cmp ah, BZ_KTB              ; RED cellsafe: a split neighbour read whole\n")],
    # D3.3: the corner ray dropped
    "noray": [("bzphys.inc", "    call bz_dray\n    cmp byte [bz_sfb], 0\n",
               "    mov byte [bz_sfb], 0        ; RED noray: no corner ray\n    mov word [bz_sor], 0\n"
               "    cmp byte [bz_sfb], 0\n")],
    # R7: a quartered cell's second line read after a push out of the cell
    "r7": [("bzphys.inc", "    call bz_dset\n    jnc .lx\n    mov ax, [bz_gx + 1]         ; R7: out of the cell",
            "    call bz_dset\n    jmp short .lx               ; RED r7\n    mov ax, [bz_gx + 1]         ; R7: out of"
            " the cell")],
    # 128.24.5.2: the hostile bound dropped (bz_drec accepts every offset)
    "nobound": [("bonanza.asm", "    cmp ax, [bz_dhi]\n    ja .bad\n", "    cmp ax, [bz_dhi]  ; RED nobound\n")],
}


def near_split(c, rnd):
    """a random cell within one of a split cell (its RAM form's), and an in-cell point"""
    grid = BB.Grid(c.cga)
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
        never = g.r("bz_psp") == 0 and not BB.Grid(c.cga).gflags & BB.GF_SPLIT
        print("bonanza_dsplit TRIAL, no split cell: %d steps %s; bz_psp %d" % (
            ns, "every step equal" if not err else err, g.r("bz_psp")))
        if err:
            out.append(err)
        if not never:
            out.append("TRIAL: a course with no split cell set bz_psp or GF_SPLIT")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1124)
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--reds", action="store_true", help="every red arm: each must go red")
    a = ap.parse_args()
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
