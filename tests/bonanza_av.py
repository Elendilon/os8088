#!/usr/bin/env python3
"""BONANZA's AV (SPEC.md 128.29): the occluder pass with the MODEL in VOID cells, the package's own bz_occ
under unicorn against tools/bbcourse.py's binding model (bbcourse.AGrid, amodel_*) and the part's records -
the host half of the guest's model, the precedent being SPEC.md 128.15.5.2's D/C proof.

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
(128.15.10.1).  Laying a word twice under two masks is laying it once under their AND, so the order the
guest lays in cannot show.  ASSERTED at every position: the buffer EXACTLY the host's, [bz_nlay] moved by the
records the host's verdicts lay, [bz_namod] by 1 exactly where the model runs, the stack balanced.

The positions, per course (every BZ_COURSES course, the pathway and the title): --n VOID positions (a reach
cell the model runs in, a random point of it, a random height of its range and fraction, airborne), n / 30
FALLS of ten consecutive frames from a VOID position (the ball dropping 1 - 6 px a frame and drifting up to an
eighth of a cell: the guest's cell cache, SPEC.md 128.29.5, used, re-counted and left as a fall uses it) and
n / 3 others (any reach cell, grounded or airborne); one in five with the window clipping the footprint (its
top line or its left word inside it).

--price: the pass's executed instructions at the VOID positions priced by 128.11.15's method (each at max(EU
+ EA, 4.34 a byte), x 1.05; bonanza_dsplit's table), the AV part against the course compiled --occ off
(today's records, GF_ANA clear: the model never runs) at the same positions - the fall frames' cost, PRICED.
--red amodel: the guest with the right half's + 4 made + 12 (every right-half edge a line low) must fail.
--red acache: the guest's cell cache not dropped when a front cell starts to count (the speed pass's cache,
SPEC.md 128.29.5: the FALLS above are what reach it) must fail.
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
BOXD, BOXW = 20, 4
LINES = 200
CHKW = (0x3333, 0xCCCC)

REDS = {
    "amodel": [("bzvideo.inc", "    add ax, 4                   ; (the right half's + 4)",
                "    add ax, 12                  ; RED amodel"),
               ("bzvideo.inc", "    add ax, 6                   ; (flat: 2 (2 d' + 1) + 4)",
                "    add ax, 14                  ; RED amodel")],
    "acache": [("bzvideo.inc", "    jl .count0                  ; a front cell counts that did not",
                "    nop                         ; RED acache\n    nop")],
}


def courses():
    """[(name, compiled course)] - BZ_COURSES, the pathway, the title (the build's compiles: the cache's)"""
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
        self.g.call("bz_crshdr")
        self.ag = BB.AGrid(c.cga)
        self.g.w("bz_gfl", self.ag.gflags)
        m = BB.decode_part(c.cga)
        self.recs = {}
        for br, col, s_, top, mi in m["recs"]:
            self.recs.setdefault((br, col), []).append((s_, top, m["masks"][mi]))
        info = BB.read_part(c.cga)
        self.mapsh, self.mapoff = info["mapsh"], BB.HDR
        self.cols = info["cols"]

    def block_word(self, br, w, ly):
        p = self.c.cga
        off = struct.unpack_from("<H", p, self.mapoff + ((8 * br) << self.mapsh) + 2 * w)[0]
        return struct.unpack_from("<H", p, off + 2 * ly)[0]

    def run(self, pos, wtop, c0n, rnd, trace=False):
        """bz_occ at POS with the window (WTOP, C0N): -> (the box's lines [(y, [words])] after, the host's, laid
        delta, the host's laid count, namod delta, the model's verdict, the trace or None)"""
        g, c = self.g, self.c
        gx, gy, gz, air = pos
        px = ((gx - gy) >> 8) + c.x0 - 8
        py = ((((gx + gy) >> 1) - gz) >> 8) + c.y0 - 13
        sb = (gx >> 12) + (gy >> 12)
        nfx0, nfx1 = px >> 3, ((px >> 2) + 4) >> 1
        W = self.cols - c0n if self.cols - c0n < 40 else 40
        olo, ohi = max(py, wtop), min(py + 16, wtop + LINES)
        DL, DH = max(nfx0, c0n), min(nfx1, c0n + W - 1)
        if olo >= ohi or DL > DH:
            return None
        g.w("bz_gx", gx, 4)
        g.w("bz_gy", gy, 4)
        g.w("bz_gz", gz, 4)
        g.w("bz_air", air)
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
        g.trace = [] if trace else None
        g.call("bz_occ")
        tr, g.trace = g.trace, None
        out = bytes(g.mu.mem_read(CS * 16 + bufoff, 2 * BOXW * n))
        # the host
        key = (gz >> 8) + (0 if air else BB.CLIMB)
        cell = (gx >> 12, gy >> 12)
        runs = self.ag.runs(*cell)
        emin = {}
        if runs:
            fr = [f for f in self.ag.front(*cell) if f[0] > key]
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


def positions(c, ag, n, rnd):
    """-> [(gx, gy, gz, air, void)]: n VOID positions and n / 3 others"""
    rcs = BB.av_positions(c.reach, ag, c.slabcells) if ag.gflags & BB.GF_ANA else []
    out = []
    i = 0
    while i < (n if rcs else 0):
        rc = rnd.choice(rcs)
        for _ in range(1 + rnd.randrange(3)):       # (one to three a cell in a row: the guest's cell-top test
            z = rnd.randrange(rc.zlo, rc.zhi + 1)   # remembers the cell, SPEC.md 128.29.5)
            out.append(((16 * rc.wx << 8) + rnd.randrange(4096), (16 * rc.wy << 8) + rnd.randrange(4096),
                        (z << 8) + rnd.randrange(256), 1, True))
            i += 1
    for i in range(max(1, n // 30)):            # FALLS (the speed pass, SPEC.md 128.29.5): ten frames from a
        rc = rnd.choice(rcs) if rcs else None   # VOID position, the ball dropping 1 - 6 px a frame and drifting
        if rc is None:                          # up to an eighth of a cell, so that a run keeps its cell, its
            break                               # columns or its count set for a while and then leaves them
        gx, gy = (16 * rc.wx << 8) + rnd.randrange(4096), (16 * rc.wy << 8) + rnd.randrange(4096)
        gz = (rnd.randrange(rc.zlo, rc.zhi + 1) << 8) + rnd.randrange(256)
        for _ in range(10):
            px = ((gx - gy) >> 8) + c.x0 - 8
            py = ((((gx + gy) >> 1) - gz) >> 8) + c.y0 - 13
            if px < 0 or py < 0 or px + 24 > c.width or py + 16 > c.lines:
                break                           # (off the picture: the run ends)
            out.append((gx, gy, gz, 1, True))
            gz -= rnd.randrange(256, 6 * 256)
            gx += rnd.randrange(-512, 513)
            gy += rnd.randrange(-512, 513)
    for i in range(max(1, n // 3)):
        rc = rnd.choice(c.reach)
        air = 1 if rc.kind == BB.KIND_VOID else rnd.randrange(2)
        z = rnd.randrange(rc.zlo, rc.zhi + 1)
        out.append(((16 * rc.wx << 8) + rnd.randrange(4096), (16 * rc.wy << 8) + rnd.randrange(4096),
                    (z << 8) + rnd.randrange(256), air, False))
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
            nv = nmod = bad = clip = lays = 0
            first = None
            pr = []
            for (gx, gy, gz, air, void) in positions(c, P.ag, n, rnd):
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
                r_ = P.run((gx, gy, gz, air), wtop, c0n, random.Random(seed_b), trace=price and void)
                if r_ is None:
                    continue
                got, want, dl, hl, dm, runs, tr, at = r_
                nv += void
                nmod += runs
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
                    r0 = off.run((gx, gy, gz, air), wtop, c0n, random.Random(seed_b), trace=True)
                    if r0 is not None and r0[1] == r0[0]:
                        pr.append((price_of(tr, lst), price_of(r0[6], lst), runs))
            if verbose:
                print("bonanza_av %-6s GF_ANA %s: %d positions (%d VOID, the model ran at %d; %d clipped), %d records "
                      "laid: %s" % (name, "set" if P.ag.gflags & BB.GF_ANA else "clear", nv + max(1, n // 3), nv, nmod,
                                    clip, lays, "every buffer, laid count and model verdict the host's" if not bad
                                    else "%d DIFFER, the first %s" % (bad, first)), flush=True)
            if bad:
                out.append("bonanza_av %s: %d positions differ, the first %s" % (name, bad, first))
            if price and pr:
                ran = [p for p in pr if p[2]]
                d = sorted(a - b for a, b, _r in ran)
                if d:
                    print("bonanza_av PRICE %-6s the pass at %d VOID positions the model ran at: AV mean %.0f clk "
                          "(max %.0f), today's records %.0f (max %.0f): %+.0f a fall frame in the mean, median %+.0f, "
                          "worst %+.0f; at most %.1f%% of a 79.6k refresh" % (
                              name, len(ran), sum(a for a, _b, _r in ran) / len(ran), max(a for a, _b, _r in ran),
                              sum(b for _a, b, _r in ran) / len(ran), max(b for _a, b, _r in ran),
                              sum(d) / len(d), d[len(d) // 2], d[-1], 100.0 * max(a for a, _b, _r in ran) / 79600),
                          flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1129)
    ap.add_argument("--price", action="store_true")
    ap.add_argument("--red", choices=sorted(REDS))
    a = ap.parse_args()
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
