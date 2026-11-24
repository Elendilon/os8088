#!/usr/bin/env python3
"""BONANZA's AV (SPEC.md 130.29): the occluder pass with the MODEL in VOID cells, the package's own bz_occ
under unicorn against tools/bbcourse.py's binding model (bbcourse.AGrid, amodel_*) and the part's records -
the host half of the guest's model, the precedent being SPEC.md 130.15.5.2's D/C proof.

    make bonanzadisk && python3 tests/bonanza_av.py [--n N] [--seed S] [--price] [--red amodel]

THE METHOD (bonanza_dsplit's): the package image assembled from the tree (bonanza_ring's assemble and
symbols), loaded at one segment of an emulated 8086, a course's RAM form (the build's compile) at another,
bz_crshdr called on it and the grid's FLAGS poked into bz_gfl (bz_pinit's copy), then for each POSITION the
ball's state poked (bz_gx, bz_gy, bz_gz, bz_air, bz_sb, bz_py, the footprint's word columns bz_nfx0 and
bz_nfx1 as bz_foot computes them, the window bz_wtop / bz_c0n / bz_W, the gate bz_ogate 1), ONE box over the
pass's footprint (its buffer filled with random bytes) and bz_occ CALLED.  The host's expectation is the same
buffer with every block word of the footprint laid ONCE under the AND of the masks the guest's pass ANDs:
every record of the part (decode_part: the bytes the guest walks) whose verdict holds (s_b < s', z_b + m <
top) and, where the model runs (AGrid.runs: GF_ANA, the ball's cell VOID and not OBS), the model's mask -
each pixel at or under the least edge of the counting front cells in its column cleared, the checker ORed in
(130.15.10.1).  Laying a word twice under two masks is laying it once under their AND, so the order the
guest lays in cannot show.  ASSERTED at every position: the buffer EXACTLY the host's, [bz_nlay] moved by the
records the host's verdicts lay, [bz_namod] by 1 exactly where the model runs, the stack balanced.

The positions, per course (every BZ_COURSES course, the pathway and the title): --n VOID positions (a reach
cell the model runs in, a random point of it, a random height of its range and fraction, airborne), n / 30
FALLS of ten consecutive frames from a VOID position (the ball dropping 1 - 6 px a frame and drifting up to an
eighth of a cell: the guest's cell cache, SPEC.md 130.29.5, used, re-counted and left as a fall uses it) and
n / 3 others (any reach cell, grounded or airborne); one in five with the window clipping the footprint (its
top line or its left word inside it).

--price: the pass's executed instructions at the VOID positions priced by 130.11.15's method (each at max(EU
+ EA, 4.34 a byte), x 1.05; bonanza_dsplit's table), the AV part against the course compiled --occ off
(today's records, GF_ANA clear: the model never runs) at the same positions - the fall frames' cost, PRICED.
--red amodel: the guest with the right half's + 4 made + 12 (every right-half edge a line low) must fail.
--red aneigh: the guest's neighbour reuse (SPEC.md 130.29.5) keeping the old shadows on the new row 1 must fail.
--red acache: the guest's cell cache not dropped when a front cell starts to count (the speed pass's cache,
SPEC.md 130.29.5: the FALLS above are what reach it) must fail.
--red afar: a VOID cell's FAR LIST (SPEC.md 130.29.13) never read must fail; the positions in a listed cell are
counted in the report.
SPEC.md 130.49's: --red lowfl (the low flight's margin left out), --red apick (a split V's pick ignored), --red
acent (a centre half-edge a line low) and --red aflat (a flat word laid from the first laid line) must fail;
SPEC.md 130.11.4.2's: --red acum (a group's later laid records never ANDed, the least-t' test gone) must fail;
--course BBC (more than once) runs those course files alone (ROLL, HOP: the BZROLL=1 build's).

SPEC.md 130.42.15, THE SEE-SAW'S POSES: on a course with see-saw lanes (MILL), after its positions, each plate's
lanes are put in each pose P by the guest's own bz_lsync (the map's words and, through bz_ltog, the records'
TOGGLES), then --n / 3 positions round the plate (the reach whose footprint meets a block one of its poses
changes) are run as above - the host's expectation laying only the records the part's toggles lay in pose P, from
the blocks of the map as the guest holds it.  --red tltog (bz_lsync writing no toggle: the records stay as the
last pose left them) and --red tlall (every posed record laid in every pose: the pose test removed) must fail.
"""
import argparse
import os
import random
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bbcourse as BB          # noqa: E402
import bonanza_dsplit as D     # noqa: E402
import bonanza_ring as R       # noqa: E402

CS, PS = D.CS, D.PS
PS2 = 0x5000                    # a two-part course's WORLD part (SPEC.md 130.30)
SHS = 0x8000                    # a SHEETED course's sheets past sheet 0 (SPEC.md 130.30.12), 1000h apart
BOXD, BOXW = 20, 4
LINES = 200
CHKW = (0x3333, 0xCCCC)

REDS = {
    "amodel": [("bzvideo.inc", "    add ax, 4                   ; (the right half's + 4)",
                "    add ax, 12                  ; RED amodel"),
               ("bzvideo.inc", "    add ax, 6                   ; (flat: 2 (2 d' + 1) + 4)",
                "    add ax, 14                  ; RED amodel")],
    "aneigh": [("bzvideo.inc", "    mov byte [bz_afl + 7], 0    ; row 1: no shadow",
                "    nop                         ; RED aneigh"),
               ("bzvideo.inc", "    mov byte [bz_afl + BZ_AFL + 7], 0\n",
                "    nop\n")],
    "acache": [("bzvideo.inc", "    jl .count0                  ; a front cell counts that did not",
                "    nop                         ; RED acache\n    nop")],
    # SPEC.md 130.29.13: a VOID V's far list never read (the residual was cut with it); and the neighbour's test
    # back on the extra slots' end (a far list then forces the next V to read whole: not red - a speed, not a
    # picture - so it is not an arm)
    "afar": [("bzvideo.inc", "    or al, al\n    jz .fnone\n    call bz_afar\n", "    or al, al\n    jmp .fnone                  ; RED afar\n")],
    # SPEC.md 130.49: the low flight's margin left out; a split V's pick ignored (the model in every split
    # cell with a VOID piece); a centre half-edge's + 8 made + 24 (a line low)
    "lowfl": [("bzvideo.inc", "    cmp ax, bx\n    jge .air\n.grd:", "    cmp ax, bx\n    jmp .air          ; RED lowfl\n.grd:")],
    "apick": [("bzvideo.inc", "    test [es:bz_avm], al\n    jnz .run\n    ret\n",
               "    jmp .run                    ; RED apick\n")],
    "acent": [("bzvideo.inc", ".rxc:\n    add ax, 8\n", ".rxc:\n    add ax, 24                  ; RED acent\n")],
    # SPEC.md 130.51: a band's TB taken at the pass's first block row alone (a footprint across a band edge keeps
    # the first band's kt)
    "aband": [("bzvideo.inc", "    jnz .brow1                  ; first line a multiple of 128) takes its kt\n    call bz_otbk",
               "    jnz .brow1\n    nop                         ; RED aband\n    nop\n    nop")],
    # SPEC.md 130.52: the band's mask table not loaded (a `masks banded` course reads band 0's slice everywhere)
    "amband": [("bzvideo.inc", "    mov ax, [bx + 2]\n    mov [es:bz_mtab], ax\n",
                "    nop                         ; RED amband\n")],
    # SPEC.md 130.49.7: the flat word's lay from the first laid line, not from its edge
    "aflat": [("bzvideo.inc", "    add [es:bz_of], ax\n    sub [es:bz_on], ax\n",
               "    nop                         ; RED aflat\n    nop\n")],
    # SPEC.md 130.11.4.2: a group's later laid records passed over whatever their t' (the least-t' test gone), so
    # a record UNDER the least laid t' - an antichain's, not under any laid cumulative mask - is never ANDed
    "acum": [("bzvideo.inc", "    jae .skip                   ; every record of its block at or over it in",
              "    jmp .skip                   ; RED acum")],
    # SPEC.md 130.42.15: a see-saw lane's toggles never written; every posed record laid in every pose
    "tltog": [("bzwheel.inc", "    mov [bz_ldrw + bx], al\n    call bz_ltog\n    push ax\n",
               "    mov [bz_ldrw + bx], al\n    push ax                     ; RED tltog\n")],
    "tlall": [("bzwheel.inc", "    jnz .on\n    xor dl, dl                  ; ...or 0: not laid in this pose",
               "    jmp .on                     ; RED tlall\n    xor dl, dl")],
}


EXTRA = []                      # --course: more course files (ROLL, HOP: the knob builds' courses)
HACK = {}                       # --red lowfl's compile: the whole-cell cut, which still holds the ramp's bites


def courses():
    """[(name, compiled course)] - BZ_COURSES, the pathway, the title (the build's compiles: the cache's), and
    --course's"""
    if EXTRA:
        return [(c.name, c) for c in (BB.compile_course(p, _hack=HACK or None) for p in EXTRA)]
    out = [(c.name, c) for c in (BB.compile_course(p) for p in BB.default_paths())]
    info = [(c.name, c.title) for _n, c in out]
    out.append(("PATH", BB.compile_course(os.path.join(BB.COURSE_DIR, "path.bbc"), crsinfo=info)))
    out.append(("TITLE", BB.compile_course(os.path.join(BB.COURSE_DIR, "title.bbc"))))
    return out


class Pass:
    """one course's part under unicorn, ready for bz_occ"""

    def __init__(self, binp, sym, c):
        self.c, self.sym = c, sym
        self.g = D.Guest(binp, sym, c.cga)
        self.g.w("bz_cseg", PS, 2)
        if getattr(c, "wcga", None):            # a TWO-PART course (SPEC.md 130.30): the picture part at PS
            self.g.mu.mem_write(PS2 * 16, bytes(c.wcga))    # (bz_mseg: the walk, the masks, the lay), the
            self.g.w("bz_cseg", PS2, 2)                     # world part at PS2 (bz_cseg: the grid, the model's
        if "bz_mseg" in sym:                                # reads)
            self.g.w("bz_mseg", PS, 2)
        self.g.call("bz_crshdr")
        self.ag = BB.AGrid(BB.world_of(c))
        self.g.w("bz_gfl", self.ag.gflags)
        m = BB.course_model(c)
        self.masks = m["masks"]
        self.recs = {}
        sz = m.get("sz") or ()                  # (SPEC.md 130.42.15: a record stored s' 0 is laid at rest by none)
        for i, (br, col, s_, top, mi) in enumerate(m["recs"]):
            if i not in sz:
                self.recs.setdefault((br, col), []).append((s_, top, m["masks"][mi]))
        info = BB.read_parts(c.cga, c.wcga) if getattr(c, "wcga", None) else BB.read_part(c.cga)
        self.mapsh, self.mapoff = info["mapsh"], BB.HDR
        self.cols = info["cols"]
        self.nneigh = 0
        # SPEC.md 130.42.15: the see-saw lanes (the part's record order: lane j is record j) and each record's
        # TOGGLE byte (the part's record index: a byte its toggle run's), read from the part's own props
        self.pose = 0
        self.mrecs = m["recs"]
        self.tlanes = [d for d in info["props"] if d["kind"] == BB.FK_TILTL]
        self.tog = {}
        first = {}
        for i, rr in enumerate(m["recs"]):
            first.setdefault(rr[0], i)
        for runs in (BB.tl_togs_of(m["props"]["blob"], m["props"]["n"]).values() if m["props"] else ()):
            for br, kk, bs in runs:
                for j, t in enumerate(bs):
                    self.tog[first[br] + kk + j] = t
        # A SHEETED course (SPEC.md 130.30.12): sheet 0 at PS (above), each other sheet at a segment of its own
        # (SHS up), and the sheet SHOWN for a window chosen by the plan's rule (show(): the shown one while it
        # serves the window's top, else the first that does) - bz_mseg its segment and bz_mrow its rows clamped
        # to [m0, hic], as bz_shset leaves them (tests/bonanza_sheet.py proves bz_shchk makes exactly those).
        # The host reads each block row's map word from a sheet that HOLDS the row, sheet-relative, so a
        # window whose rows the shown sheet does not hold (a clamped read) parts from the host.
        self.sheets = BB.sheets_of(c.cga)
        self.shown = None
        if self.sheets:
            self.segs = [PS] + [SHS + 0x1000 * (i - 1) for i in range(1, len(self.sheets))]
            for s_, q in zip(self.segs[1:], self.sheets[1:]):
                self.g.mu.mem_write(s_ * 16, bytes(q))

    def set_pose(self, pose):
        """SPEC.md 130.42.15: every see-saw lane DRAWN in POSE through the guest's bz_lsync (its map words and its
        toggles), its tables poked as bz_winit makes them; the host's records those the toggles lay in it"""
        g, X = self.g, self.g.X
        for d in self.tlanes:
            j, L = d["i"], d["lane"]
            g.mu.mem_write(D.CS * 16 + self.sym["bz_lknd"] + j, bytes((d["kind"],)))
            g.mu.mem_write(D.CS * 16 + self.sym["bz_ltsz"] + j, bytes((2 * L["w"] * L["h"],)))
            g.mu.mem_write(D.CS * 16 + self.sym["bz_ltw"] + j, bytes((L["w"],)))
            g.mu.mem_write(D.CS * 16 + self.sym["bz_lhh"] + j, bytes((L["h"],)))
            g.mu.mem_write(D.CS * 16 + self.sym["bz_ltpm"] + 2 * j, struct.pack("<H", L["off"]))
            mo = g.r("bz_mrow", 2, k=2 * L["brow"]) + 2 * L["col"]
            g.mu.mem_write(D.CS * 16 + self.sym["bz_ltmo"] + 2 * j, struct.pack("<H", mo))
            g.mu.reg_write(X.UC_X86_REG_BX, j)
            g.call("bz_lsync", ax=pose)
        self.pose = pose
        self.recs = {}
        for i, (br, col, s_, top, mi) in enumerate(self.mrecs):
            t = self.tog.get(i)
            if t is None or (t >> (BB.TL_TOGS + pose)) & 1:
                self.recs.setdefault((br, col), []).append((s_, top, self.masks[mi]))

    def show(self, wtop):
        """a SHEETED course: the sheet serving the window's top WTOP (lines) made the shown one"""
        pl = self.c.plan
        if self.shown is not None and pl["sheets"][self.shown]["tlo"] <= wtop <= pl["sheets"][self.shown]["thi"]:
            return
        self.shown = next(i for i, x in enumerate(pl["sheets"]) if x["tlo"] <= wtop <= x["thi"])
        x, rowb = pl["sheets"][self.shown], 2 * self.cols
        self.g.w("bz_mseg", self.segs[self.shown], 2)
        mrow = b"".join(struct.pack("<H", BB.HDR + (min(max(br, x["m0"]), x["hic"]) - x["m0"]) * rowb)
                        for br in range(self.c.brows))
        self.g.mu.mem_write(CS * 16 + self.sym["bz_mrow"], mrow)

    def block_word(self, br, w, ly):
        if self.pose and not self.sheets:       # (SPEC.md 130.42.15: the map as the guest's bz_lsync left it)
            mw = struct.unpack("<H", self.g.mu.mem_read(PS * 16 + self.mapoff + 2 * self.cols * br + 2 * w, 2))[0]
            return struct.unpack("<H", self.g.mu.mem_read(PS * 16 + mw + 2 * ly, 2))[0]
        if not self.sheets:
            p, row = self.c.cga, br
        else:                                   # (a sheet holding block row BR: its map is rows m0 .. m0 + n - 1)
            pl = self.c.plan
            i = next((i for i, x in enumerate(pl["sheets"]) if x["m0"] <= br < x["m0"] + pl["n"]), None)
            if i is None:
                raise AssertionError("block row %d is in no sheet of %s" % (br, self.c.name))
            p, row = self.sheets[i], br - pl["sheets"][i]["m0"]
        off = struct.unpack_from("<H", p, self.mapoff + 2 * self.cols * row + 2 * w)[0]
        return struct.unpack_from("<H", p, off + 2 * ly)[0]

    def run(self, pos, wtop, c0n, rnd, trace=False):
        """bz_occ at POS with the window (WTOP, C0N): -> (the box's lines [(y, [words])] after, the host's, laid
        delta, the host's laid count, namod delta, the model's verdict, the trace or None)"""
        g, c = self.g, self.c
        gx, gy, gz, air = pos[:4]
        gh = pos[4] if len(pos) > 4 else None   # (SPEC.md 130.49.6: the floor's h4 under it, bz_gh; None: no bz_ghv)
        px = ((gx - gy) >> 8) + c.x0 - 8
        py = ((((gx + gy) >> 1) - gz) >> 8) + c.y0 - 13
        sb = (gx >> 12) + (gy >> 12)
        nfx0, nfx1 = px >> 3, ((px >> 2) + 4) >> 1
        W = self.cols - c0n if self.cols - c0n < 40 else 40
        olo, ohi = max(py, wtop), min(py + 16, wtop + LINES)
        DL, DH = max(nfx0, c0n), min(nfx1, c0n + W - 1)
        if olo >= ohi or DL > DH:
            return None
        if self.sheets:
            self.show(wtop)
        g.w("bz_gx", gx, 4)
        g.w("bz_gy", gy, 4)
        g.w("bz_gz", gz, 4)
        g.w("bz_air", air)
        g.w("bz_ghv", 0 if gh is None else 1)   # (SPEC.md 130.49.6's low flight)
        g.w("bz_gh", gh or 0, 2)
        g.w("bz_sb", sb, 2)
        g.w("bz_py", py, 2)
        g.w("bz_px", px, 2)
        g.w("bz_nfx0", nfx0, 2)
        g.w("bz_nfx1", nfx1, 2)
        g.w("bz_wtop", wtop, 2)
        g.w("bz_c0n", c0n, 2)
        g.w("bz_W", W, 2)
        g.w("bz_ogate", 1)
        g.w("bz_nbox", 1, 2)
        bufoff = self.sym["bz_boxbuf"]
        box = struct.pack("<HHHHH", DL, olo, DH - DL + 1, ohi - olo, bufoff) + bytes(BOXD - 10)
        g.mu.mem_write(CS * 16 + self.sym["bz_boxes"], box)
        n = ohi - olo
        buf0 = bytes(rnd.randrange(256) for _ in range(2 * BOXW * n))
        g.mu.mem_write(CS * 16 + bufoff, buf0)
        nl0, na0 = g.r("bz_nlay", 2), g.r("bz_namod", 2)
        cp0 = g.r("bz_acptr", 2)
        g.trace = [] if trace else None
        g.call("bz_occ")
        if g.r("bz_acptr", 2) != cp0 and g.r("bz_arue") != 0xFF:
            self.nneigh += 1                    # (a new cell whose table came from its neighbour's)
        tr, g.trace = g.trace, None
        out = bytes(g.mu.mem_read(CS * 16 + bufoff, 2 * BOXW * n))
        # the host
        oair = BB.oair_at(air, gz >> 8, None if gh is None else gh >> 2)
        key = (gz >> 8) + (0 if oair else BB.CLIMB)
        mkey = (gz >> 8) + (0 if air else BB.CLIMB)     # (the model's key: bz_air's - it runs over no floor)
        cell = BB.mcell(gx, gy)
        runs = self.ag.runs(*cell)
        emin = {}
        if runs:
            fr = [f for f in self.ag.front(cell[0], cell[1]) if f[0] > mkey]
            for x, evs in BB.amodel_cols(fr, 8 * DL, 8 * DH + 7).items():
                emin[x] = evs[0][0]
        want = bytearray(buf0)
        laid = 0
        for br in range(olo >> 3, ((ohi - 1) >> 3) + 1):
            for w in range(DL, DH + 1):
                ms = [mk for s_, top, mk in self.recs.get((br, w), ()) if sb < s_ and key < top]
                laid += len(ms)
                for y in range(max(8 * br, olo), min(8 * br + 8, ohi)):
                    ly = y & 7
                    M = 0xFFFF
                    for mk in ms:
                        M &= mk[2 * ly] | mk[2 * ly + 1] << 8
                    if runs:
                        mm = 0
                        for j in range(8):
                            x = 8 * w + j
                            if x in emin and y >= emin[x]:
                                b = 3 << (6 - 2 * (j & 3))
                                mm |= b if j < 4 else b << 8
                        M &= (~mm & 0xFFFF) | CHKW[y & 1]
                    o = (y - olo) * 2 * BOXW + 2 * (w - DL)
                    bw = want[o] | want[o + 1] << 8
                    blk = self.block_word(br, w, ly)
                    nw = ((bw ^ blk) & M) ^ blk
                    want[o], want[o + 1] = nw & 255, nw >> 8
        return (out, bytes(want), g.r("bz_nlay", 2) - nl0, laid, g.r("bz_namod", 2) - na0, runs, tr,
                (px, py, sb, gz >> 8, air, cell, olo, ohi, DL, DH))


def _pt(rc, rnd):
    """a random in-cell point (1/256 gu) of an AvPos: the whole cell, or one of a split square's VOID points"""
    if rc.pts is None:
        return (16 * rc.wx << 8) + rnd.randrange(4096), (16 * rc.wy << 8) + rnd.randrange(4096)
    u, v = rnd.choice(rc.pts)
    return (16 * rc.wx + u << 8) + rnd.randrange(256), (16 * rc.wy + v << 8) + rnd.randrange(256)


def positions(c, ag, n, rnd):
    """-> [(gx, gy, gz, air, void[, gh])]: n VOID positions (a VOID cell, or a split cell's VOID piece: SPEC.md
    130.49.1) and n / 3 others, a third of the airborne ones over a floor a LOW FLIGHT (gh its h4, 130.49.6)"""
    rcs = BB.av_positions(c.reach, ag, c.slabcells) if ag.gflags & BB.GF_ANA else []
    out = []
    i = 0
    while i < (n if rcs else 0):
        rc = rnd.choice(rcs)
        for _ in range(1 + rnd.randrange(3)):       # (one to three a cell in a row: the guest's cell-top test
            z = rnd.randrange(rc.zlo, rc.zhi + 1)   # remembers the cell, SPEC.md 130.29.5)
            gx, gy = _pt(rc, rnd)
            out.append((gx, gy, (z << 8) + rnd.randrange(256), 1, True))
            i += 1
    for i in range(max(1, n // 15)):            # FALLS (the speed pass, SPEC.md 130.29.5): ten frames from a
        rc = rnd.choice(rcs) if rcs else None   # VOID position, the ball dropping 1 - 6 px a frame and drifting
        if rc is None:                          # up to an eighth of a cell, so that a run keeps its cell, its
            break                               # columns or its count set for a while and then leaves them
        gx, gy = _pt(rc, rnd)
        gz = (rnd.randrange(rc.zlo, rc.zhi + 1) << 8) + rnd.randrange(256)
        fwd = i % 2                             # (every other fall runs FORWARD, a quarter of a cell a frame in
        dx_, dy_ = rnd.choice(((1, 0), (0, 1)))     # x or in y: the next cell in front, the neighbour's table)
        for _ in range(10):
            px = ((gx - gy) >> 8) + c.x0 - 8
            py = ((((gx + gy) >> 1) - gz) >> 8) + c.y0 - 13
            if px < 0 or py < 0 or px + 24 > c.width or py + 16 > c.lines:
                break                           # (off the picture: the run ends)
            out.append((gx, gy, gz, 1, True))
            gz -= rnd.randrange(256, 6 * 256)
            gx += rnd.randrange(800, 1400) * dx_ if fwd else rnd.randrange(-512, 513)
            gy += rnd.randrange(800, 1400) * dy_ if fwd else rnd.randrange(-512, 513)
    sps = [q for q in rcs if q.pts is not None]
    for i in range(max(1, n // 15) if sps else 0):     # CORNER FALLS (SPEC.md 130.49): ten frames from a split
        q = rnd.choice(sps)                     # cell's top down through its VOID piece, 1 - 3 px a frame - its
        t = c.tiles[(q.wx, q.wy)]               # own pieces' edges and the flat word's lay are what they cross
        top = int(4 * max(max(h.corners()) for h in t.halves if h is not None))
        gz = (min(max(top - rnd.randrange(6), q.zlo), q.zhi) << 8) + rnd.randrange(256)
        gx, gy = _pt(q, rnd)
        for _ in range(10):
            out.append((gx, gy, gz, 1, True))
            gz -= rnd.randrange(256, 3 * 256)
            if (gz >> 8) < q.zlo:
                break
    ramps = [rc for rc in c.reach if isinstance(c.tiles.get((rc.wx, rc.wy)), BB.Tile)
             and c.tiles[(rc.wx, rc.wy)].kind == BB.KIND_FLOOR and (c.tiles[(rc.wx, rc.wy)].sx or c.tiles[(rc.wx, rc.wy)].sy)]
    for i in range(n // 10 if ramps else 0):    # LOW FLIGHTS on ramps (SPEC.md 130.49.6: what the margin is for)
        rc = rnd.choice(ramps)                  # (the cell's FRONT quarter, by the next cell of the ramp)
        gx, gy = (16 * rc.wx + 8 << 8) + rnd.randrange(2048), (16 * rc.wy + 8 << 8) + rnd.randrange(2048)
        f = BB.pose_floor(c.tiles, rc.wx, rc.wy, gx, gy)
        z = f + rnd.randrange(BB.CLIMB)
        out.append((gx, gy, (z << 8) + rnd.randrange(256), 1, False, 4 * f))
    for i in range(max(1, n // 3)):
        rc = rnd.choice(c.reach)
        air = 1 if rc.kind == BB.KIND_VOID else rnd.randrange(2)
        z = rnd.randrange(rc.zlo, rc.zhi + 1)
        gx, gy = (16 * rc.wx << 8) + rnd.randrange(4096), (16 * rc.wy << 8) + rnd.randrange(4096)
        f = BB.pose_floor(c.tiles, rc.wx, rc.wy, gx, gy) if air else None
        if f is not None and rnd.randrange(3) == 0:     # a LOW FLIGHT over the floor there (130.49.6)
            z = f + rnd.randrange(BB.CLIMB + 2)
            out.append((gx, gy, (z << 8) + rnd.randrange(256), 1, False, 4 * f))
            continue
        out.append((gx, gy, (z << 8) + rnd.randrange(256), air, False))
    return out


def price_of(tr, lst):
    """a trace's clocks: each instruction at max(EU + EA, 4.34 a byte), x 1.05 (bonanza_dsplit's EU table)"""
    clk = 0.0
    for i, (a, sz) in enumerate(tr):
        nxt = tr[i + 1][0] if i + 1 < len(tr) else None
        tx = lst.get(a, "")
        if not tx.split(";")[0].strip():
            continue
        eu = D.price_line(tx, 0, taken=nxt is not None and nxt != a + sz)
        clk += max(eu, 4.34 * sz)
    return 1.05 * clk


def check(n=300, seed=1129, patches=(), price=False, verbose=True):
    """-> [complaints]; prints the evidence"""
    out = []
    rnd = random.Random(seed)
    with tempfile.TemporaryDirectory() as td:
        binp, sym = D.build(td, patches)
        lst = D.listing(td, patches) if price else None
        cl = courses()
        info = [(q.name, q.title) for _n, q in cl[:-2]]
        for name, c in cl:
            P = Pass(binp, sym, c)
            off = None
            if price:
                offc = BB.compile_course(c.fname if os.path.isabs(c.fname) else os.path.join(ROOT, c.fname),
                                         _hack={"occ": "off"}, crsinfo=info if c.pth is not None else None)
                off = Pass(binp, sym, offc)
            nv = nmod = bad = clip = lays = nfar = 0
            first = None
            pr = []
            for pos_ in positions(c, P.ag, n, rnd):
                gx, gy, gz, air, void = pos_[:5]
                gh = pos_[5] if len(pos_) > 5 else None
                py = ((((gx + gy) >> 1) - gz) >> 8) + c.y0 - 13
                px = ((gx - gy) >> 8) + c.x0 - 8
                wtop, c0n = max(0, py - 92), max(0, (px >> 3) - 18)
                if rnd.randrange(5) == 0:
                    clip += 1
                    if rnd.randrange(2):
                        wtop = py + rnd.randrange(1, 12)
                    else:
                        c0n = (px >> 3) + rnd.randrange(1, 3)
                seed_b = rnd.randrange(1 << 30)
                r_ = P.run((gx, gy, gz, air, gh), wtop, c0n, random.Random(seed_b), trace=price and void)
                if r_ is None:
                    continue
                got, want, dl, hl, dm, runs, tr, at = r_
                nv += void
                nmod += runs
                nfar += bool(runs and P.ag.far_list(*BB.mcell(gx, gy)[:2]))
                lays += dl
                if got != want or dl != hl or dm != int(runs):
                    bad += 1
                    if first is None:
                        k = next((i for i in range(len(got)) if got[i] != want[i]), None)
                        first = "%s at px %d py %d s %d z %d air %d cell %s lines %d - %d words %d - %d: %s" % (
                            name, at[0], at[1], at[2], at[3], at[4], at[5], at[6], at[7], at[8], at[9],
                            "buffer byte %s: guest %02Xh, host %02Xh" % (k, got[k], want[k]) if k is not None else
                            "laid %d / %d, model %d / %d" % (dl, hl, dm, runs))
                if price and void and off is not None:
                    r0 = off.run((gx, gy, gz, air, gh), wtop, c0n, random.Random(seed_b), trace=True)
                    if r0 is not None and r0[1] == r0[0]:
                        rw_ = P.ag.raw(gx >> 12, gy >> 12)
                        pr.append((price_of(tr, lst), price_of(r0[6], lst), runs,
                                   rw_ is not None and rw_[2] & 15 in BB.SPLIT_KINDS))
            if P.tlanes and not P.sheets and getattr(c, "tl_rep", None):   # SPEC.md 130.42.15: the poses
                near = BB.tl_occ_reach(c.reach, c.tl_rep["rb"][1] | c.tl_rep["rb"][2], c.x0, c.y0)
                for pose in (2, 1, 0):
                    P.set_pose(pose)
                    npos = nbad = nlay = 0
                    pfirst = None
                    for _ in range(max(1, n // 3)):
                        rc = rnd.choice(near)
                        air = 1 if rc.kind == BB.KIND_VOID else rnd.randrange(2)
                        z = rnd.randrange(rc.zlo, rc.zhi + 1)
                        gx, gy = (16 * rc.wx << 8) + rnd.randrange(4096), (16 * rc.wy << 8) + rnd.randrange(4096)
                        gz = (z << 8) + rnd.randrange(256)
                        py = ((((gx + gy) >> 1) - gz) >> 8) + c.y0 - 13
                        px = ((gx - gy) >> 8) + c.x0 - 8
                        r_ = P.run((gx, gy, gz, air, None), max(0, py - 92), max(0, (px >> 3) - 18),
                                   random.Random(rnd.randrange(1 << 30)))
                        if r_ is None:
                            continue
                        got, want, dl, hl, dm, runs, tr, at = r_
                        npos += 1
                        nlay += dl
                        if got != want or dl != hl or dm != int(runs):
                            nbad += 1
                            if pfirst is None:
                                k = next((i for i in range(len(got)) if got[i] != want[i]), None)
                                pfirst = "pose %d at px %d py %d s %d z %d air %d cell %s: %s" % (
                                    pose, at[0], at[1], at[2], at[3], at[4], at[5],
                                    "buffer byte %s: guest %02Xh, host %02Xh" % (k, got[k], want[k])
                                    if k is not None else "laid %d / %d" % (dl, hl))
                    if verbose:
                        print("bonanza_av %-6s see-saw pose %d (its %d lanes by bz_lsync): %d positions round the "
                              "plate, %d records laid: %s" % (name, pose, len(P.tlanes), npos, nlay,
                                                              "every buffer and laid count the host's" if not nbad
                                                              else "%d DIFFER, the first %s" % (nbad, pfirst)),
                              flush=True)
                    if nbad:
                        out.append("bonanza_av %s see-saw pose %d: %d positions differ, the first %s" % (
                            name, pose, nbad, pfirst))
            if verbose:
                print("bonanza_av %-6s GF_ANA %s: %d positions (%d VOID, the model ran at %d, %d of them a new cell's "
                      "table from its neighbour's, %d in a cell with a far list; %d clipped), %d records laid: %s" % (
                          name, "set" if P.ag.gflags & BB.GF_ANA else "clear", nv + max(1, n // 3), nv, nmod,
                          P.nneigh, nfar, clip, lays, "every buffer, laid count and model verdict the host's" if not bad
                                    else "%d DIFFER, the first %s" % (bad, first)), flush=True)
            if bad:
                out.append("bonanza_av %s: %d positions differ, the first %s" % (name, bad, first))
            for lab, sel in (("VOID cells", False), ("SPLIT pieces", True)):     # (SPEC.md 130.49: apart)
                ran = [p for p in pr if p[2] and p[3] == sel] if price else []
                d = sorted(a - b for a, b, _r, _s in ran)
                if d:
                    print("bonanza_av PRICE %-6s the pass at %d %s the model ran at: AV mean %.0f clk "
                          "(max %.0f), today's records %.0f (max %.0f): %+.0f a fall frame in the mean, median %+.0f, "
                          "worst %+.0f; at most %.1f%% of a 79.6k refresh" % (
                              name, len(ran), lab, sum(p[0] for p in ran) / len(ran), max(p[0] for p in ran),
                              sum(p[1] for p in ran) / len(ran), max(p[1] for p in ran),
                              sum(d) / len(d), d[len(d) // 2], d[-1], 100.0 * max(p[0] for p in ran) / 79600),
                          flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1129)
    ap.add_argument("--price", action="store_true")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--course", action="append", metavar="BBC", help="these course files alone")
    a = ap.parse_args()
    EXTRA.extend(a.course or ())
    if a.red == "lowfl":            # (SPEC.md 130.49.6: the real-pose cut holds no record a low flight's margin
        HACK["realcut"] = False     # keeps off the ball, so its red arm reads the whole-cell cut, which does)
        EXTRA[:] = EXTRA or [os.path.join(BB.COURSE_DIR, "roll.bbc")]
    bad = check(a.n, a.seed, REDS[a.red] if a.red else (), a.price)
    if a.red:
        print("bonanza_av red %s: %s" % (a.red, "RED as it must be" if bad else "NOT CAUGHT"))
        return 0 if bad else 1
    for b in bad:
        print("FAIL %s" % b)
    print("bonanza_av: %s" % ("ok" if not bad else "FAILED"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
