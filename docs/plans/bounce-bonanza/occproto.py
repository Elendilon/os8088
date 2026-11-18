#!/usr/bin/env python3
"""BOUNCE BONANZA - the occlusion deep-dive's host prototype (2026-11-17).

NOT a build input and not shipped: nothing in `make` runs it.  It measures what
docs/reports/BONANZA-OCCLUSION-2026-11-17.md reports and draws its pictures, by
re-running tools/bbcourse.py's own occluder pipeline (_occluders, block_queries,
merge_records, the dither, encode_part, stored_form, packed_len) over CHANGED
reachable sets, so every figure is the shipped tool's arithmetic on a different
input and nothing is re-implemented.

    python3 docs/plans/bounce-bonanza/occproto.py [--png] [course.bbc ...]

With no courses it takes the Makefile's BZ_COURSES.  --png writes the fall
pictures into this directory (occ-*.png).

The variants (each a transform of the course's reach, SPEC.md 130.11.4.4):
  base      the shipped reach (a check: it must give the shipped records)
  novoid    no position in a VOID cell at all (130.11.4.5's last row)
  pits      void positions only in PITS (130.11.4.5's option (c))
  vlow      VOID cells keep only heights at or above THR = the lowest solid floor
            within two tiles (= the kill height + 24 px): the falling positions
            below every nearby floor are dropped; the guest would GHOST or HIDE
            a ball there instead (the report's option V)
  vlow8     the same, THR - 8 (the last 16 px of a fall dropped, the first 8 kept)
  vlow+walls  vlow, and the reach of 130.11.4.4 cut at WALLs the ball cannot
            clear (the report's option T, a tighter reach)
"""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B  # noqa: E402


class _CV:
    def __init__(self, c):
        self.sbuf, self.tbuf, self.w, self.h = c.sbuf, c.tbuf, c.width, c.lines


def course_paths():
    mk = open(os.path.join(ROOT, "Makefile")).read()
    m = re.search(r"^BZ_COURSES := ((?:.*\\\n)*.*)$", mk, re.M)
    return [os.path.join(ROOT, p) for p in m.group(1).replace("\\\n", " ").split()]


# ---------------------------------------------------------------------------
# the reach's transforms
# ---------------------------------------------------------------------------

def _rc(r, zlo, zhi):
    return B.Reach(r.wx, r.wy, zlo, zhi, r.kind, r.src)


def open_touching(c):
    """the VOID cells whose 4-connected VOID region touches an OPEN cell (not in
    c.cells): the back-edge, side-edge and front-edge bands; the rest are PITS"""
    void = {k for k, v in c.cells.items() if v[2] & 15 == B.KIND_VOID}
    seen, out = set(), set()
    for k in void:
        if k in seen:
            continue
        comp, todo, touch = [], [k], False
        seen.add(k)
        while todo:
            p = todo.pop()
            comp.append(p)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (p[0] + d[0], p[1] + d[1])
                if q not in c.cells:
                    touch = True
                elif q in void and q not in seen:
                    seen.add(q)
                    todo.append(q)
        if touch:
            out.update(comp)
    return out


def thr_of(c, r):
    """THR: the lowest solid floor within two tiles, in px - the NEAR void's kill
    height (its z0, 130.10.4.3) plus 24 px; the guest reads it off the cell"""
    return 4 * c.cells[(r.wx, r.wy)][0] + 24


def v_base(c):
    return list(c.reach)


def v_novoid(c):
    return [r for r in c.reach if r.kind != B.KIND_VOID]


def v_pits(c):
    ot = open_touching(c)
    return [r for r in c.reach if r.kind != B.KIND_VOID or (r.wx, r.wy) not in ot]


def v_vlow(c, d=0):
    out = []
    for r in c.reach:
        if r.kind != B.KIND_VOID:
            out.append(r)
            continue
        t = thr_of(c, r) - d
        if r.zhi >= t:
            out.append(_rc(r, max(r.zlo, t), r.zhi))
    return out


def wall_blocked(c):
    """a tighter reach (option T): a cell is reached only through a neighbour the
    ball can cross - a 4-connected flood from every solid non-WALL cell over
    cells that are not WALL, plus WALL tops no higher than the highest flight
    over the cell beside them (zhi).  -> the cells the flood never reaches"""
    zhi = {(r.wx, r.wy): r.zhi for r in c.reach}
    start = [k for k, v in c.cells.items() if v[2] & 15 in (B.KIND_FLOOR, B.KIND_GOAL) or v[2] & 15 in B.SPLIT_KINDS]
    seen = set(start)
    todo = list(start)
    while todo:
        p = todo.pop()
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            q = (p[0] + d[0], p[1] + d[1])
            if q in seen or q not in c.cells:
                continue
            k = c.cells[q][2] & 15
            if k == B.KIND_WALL:
                t = c.tiles.get(q)
                top = 4 * max(t.corners()) if t is not None and not isinstance(t, B.Split) else 1 << 30
                if zhi.get(p, -1 << 30) < top:
                    continue
            seen.add(q)
            todo.append(q)
    return {k for k in c.cells if k not in seen}


def v_vghost(c):
    """option V: no position in a VOID cell lays a record - except the lift's
    shaft, where a ball stands on the slab (130.12.6.4) - and the guest ghosts
    (or hides) the whole ball in a VOID cell below the cell's GHOST height
    (ghost_heights), which the tool stores in the cell"""
    return [r for r in c.reach if r.kind != B.KIND_VOID or (r.wx, r.wy) in c.slabcells]


def v_vghost_k(c, k):
    """option V graded: a VOID cell keeps its records for the first K px below its ghost height H (the
    ball sinking behind an edge is drawn exactly there) and ghosts the ball below H - K"""
    gh = ghost_heights(c)
    out = []
    for r in c.reach:
        if r.kind != B.KIND_VOID or (r.wx, r.wy) in c.slabcells:
            out.append(r)
            continue
        H = gh[(r.wx, r.wy)][0]
        lo = max(r.zlo, H - k)
        if lo < H:
            out.append(_rc(r, lo, min(r.zhi, H - 1)))
    return out


def ghost_heights(c):
    """-> {void cell: (H, zlo, zhi)}: H the least whole px at which NO position of
    the cell (its whole area, airborne: margin 0, the fractional line) meets a
    pixel of a shipped record the rule lays; a ball in the cell at z < H is
    ghosted whole under option V.  H = zlo where nothing ever lays there (a
    front-edge fall)"""
    out = {}
    for r in c.reach:
        if r.kind != B.KIND_VOID or (r.wx, r.wy) in c.slabcells:
            continue
        xl, xh = B.foot_x(r, c.x0)
        H = r.zlo
        cand = []
        for br in range((B.foot_top(r, r.zhi) + c.y0 - 1) >> 3, ((B.foot_top(r, r.zlo) + c.y0 + 30) >> 3) + 1):
            for bc in range(xl >> 3, (xh >> 3) + 1):
                for q in c.by_block.get((br, bc), ()):
                    if q["s"] > r.s and q["top"] > r.zlo:
                        cand.append(q)
        for z in range(min(r.zhi, max((q["top"] for q in cand), default=r.zlo) - 1), r.zlo - 1, -1):
            y0_, y1_ = B.foot_top(r, z) + c.y0 - 1, B.foot_top(r, z) + c.y0 + 30
            if any(q["top"] > z and any(xl <= x <= xh and y0_ <= y <= y1_ for (x, y) in q["pix"]) for q in cand):
                H = z + 1
                break
        out[(r.wx, r.wy)] = (H, r.zlo, r.zhi)
    return out


def hidden_set(c, s, z, px, py, bp=None):
    """the ball's lit pixels the shipped records hide (the RULE, undithered), airborne"""
    bp = bp if bp is not None else B.ball_pixels(px, py)
    hid = set()
    for br in range(py >> 3, ((py + 15) >> 3) + 1):
        for bc in range(px >> 3, ((px + 19) >> 3) + 1):
            for q in c.by_block.get((br, bc), ()):
                if s < q["s"] and z < q["top"]:
                    hid |= q["pix"] & bp.keys()
    return hid


def v_avoid(c, depth=2):
    """option A on VOID cells only: a VOID cell whose front cells the model can read (plain whole cells, no
    prop, no split) lays no record - the guest computes the mask from those cells - and the rest keep theirs"""
    A = Analytic(c, depth)
    out = []
    for r in c.reach:
        if r.kind != B.KIND_VOID or (r.wx, r.wy) in c.slabcells:
            out.append(r)
            continue
        if any(n in c.tiles and not A.ok.get(n) for n in front_cells(r.wx, r.wy, depth)):
            out.append(r)
    return out


def v_aall(c, depth=2):
    """option A everywhere: only a cell with a front cell the model cannot read keeps its records"""
    A = Analytic(c, depth)
    return [r for r in c.reach if (r.wx, r.wy) in c.slabcells
            or any(n in c.tiles and not A.ok.get(n) for n in front_cells(r.wx, r.wy, depth))]


def hidden_frac(c, s, z, px, py):
    """the share of the ball's lit pixels the shipped records hide (the RULE, undithered) for a ball at
    top-left (px, py) in cell row s at whole height z, airborne"""
    bp = B.ball_pixels(px, py)
    hid = set()
    for br in range(py >> 3, ((py + 15) >> 3) + 1):
        for bc in range(px >> 3, ((px + 19) >> 3) + 1):
            for q in c.by_block.get((br, bc), ()):
                if s < q["s"] and z < q["top"]:
                    hid |= q["pix"] & bp.keys()
    return len(hid) / float(len(bp))


def ghost_heights_q(c, q):
    """option V with a THRESHOLD: H_q of a VOID cell is one more than the highest whole px z at which the
    ball, averaged over the cell's area (a 4 px lattice), has at least Q of its lit pixels hidden by the
    rule today.  Below H_q the ball is ghosted whole; at or above it, drawn whole (no record lays in a VOID
    cell) - so between H_q and H (ghost_heights) a ball less than about Q hidden is drawn over its occluder"""
    g0 = ghost_heights(c)
    out = {}
    for (wx, wy), (H, zlo, zhi) in g0.items():
        Hq = zlo
        for z in range(H - 1, zlo - 1, -1):
            fs = []
            for gx in range(16 * wx, 16 * wx + 16, 4):
                for gy in range(16 * wy, 16 * wy + 16, 4):
                    px = gx - gy + c.x0 - 8
                    py = (gx + gy) // 2 - z + c.y0 - 13
                    if 0 <= px and 0 <= py and px + 20 < c.width and py + 16 < c.lines:
                        fs.append(hidden_frac(c, wx + wy, z, px, py))
            if fs and sum(fs) / len(fs) >= q:
                Hq = z + 1
                break
        out[(wx, wy)] = (Hq, zlo, zhi)
    return out


def ghost_error(c, gh, step=2):
    """how far option V is from today, over every VOID position it ghosts (each
    cell's z from zlo to H - 1 in STEP px, the ball's top-left over the cell's
    area on a 4 px lattice): -> (positions, the mean share of the ball's lit
    pixels the rule hides today, the share of positions where today hides
    under a quarter of the ball, the share where it hides none)"""
    n = tot = few = zero = 0
    for (wx, wy), (H, zlo, zhi) in gh.items():
        s = wx + wy
        for z in range(zlo, H, step):
            for gx in range(16 * wx, 16 * wx + 16, 4):
                for gy in range(16 * wy, 16 * wy + 16, 4):
                    px = gx - gy + c.x0 - 8
                    py = (gx + gy) // 2 - z + c.y0 - 13
                    if px < 0 or py < 0 or px + 20 >= c.width or py + 16 >= c.lines:
                        continue
                    bp = B.ball_pixels(px, py)
                    hid = set()
                    for br in range(py >> 3, ((py + 15) >> 3) + 1):
                        for bc in range(px >> 3, ((px + 19) >> 3) + 1):
                            for q in c.by_block.get((br, bc), ()):
                                if s < q["s"] and z < q["top"]:
                                    hid |= q["pix"] & bp.keys()
                    f = len(hid) / float(len(bp))
                    n += 1
                    tot += f
                    few += f < 0.25
                    zero += f == 0
    return n, (tot / n if n else 0), (few / float(n) if n else 0), (zero / float(n) if n else 0)


# ---------------------------------------------------------------------------
# option A: ANALYTIC occlusion from the grid's cells in front of the ball
# ---------------------------------------------------------------------------

def front_cells(wx, wy, depth):
    """the cells in front of (wx, wy) a guest would read: every (wx + i, wy + j), i, j >= 0, 0 < i + j <= DEPTH
    (depth 1: the two edge neighbours in front; depth 2: and the corner and the two two-out)"""
    return [(wx + i, wy + j) for i in range(depth + 1) for j in range(depth + 1) if 0 < i + j <= depth]


class Analytic:
    """option A's model: a ball in cell V at height z is hidden at pixel (x, y) when one of V's FRONT cells N
    (front_cells) is a plain whole cell (not a WALL-less prop's, not split) whose highest corner is above
    z + m, and (x, y) lies at or below N's TOP EDGE in that column - the first line N owns there (from an
    owners' render, which is what a guest would compute from N's z0, sx and sy).  Below the edge it takes
    the column as N's (its top, its face to the ground: SPEC.md 130.27's grounded faces)."""

    def __init__(self, c, depth):
        self.c, self.depth = c, depth
        cv = B.render(c.tiles, c.ops, c.x0, c.y0, c.width, c.lines, owners=True)
        self.ob = cv.obuf
        self.edge = {}
        props = set(c.pcell)
        self.ok = {}
        for k, t in c.tiles.items():
            self.ok[k] = not isinstance(t, B.Split) and k not in props
        self.h = {k: 4 * max(t.corners()) for k, t in c.tiles.items() if not isinstance(t, B.Split)}

    def top_edge(self, cell):
        if not self.edge:
            for y in range(self.c.lines):
                row = self.ob[y]
                for x in range(self.c.width):
                    o = row[x]
                    if o >= 0:
                        e = self.edge.setdefault(o, {})
                        if x not in e:
                            e[x] = y
        return self.edge.get(256 * cell[0] + cell[1], {})

    def hidden(self, wx, wy, z, m, pix, skip=False):
        """-> the pixels of PIX the model hides, or None when a front cell is not one the model can read
        (skip: such a cell is passed over instead - the residual records' model)"""
        out = set()
        for n in front_cells(wx, wy, self.depth):
            if n not in self.c.tiles:
                continue
            if not self.ok.get(n):
                if skip:
                    continue
                return None
            if self.h[n] <= z + m:
                continue
            e = self.top_edge(n)
            for (x, y) in pix:
                ey = e.get(x)
                if ey is not None and y >= ey:
                    out.add((x, y))
        return out


def group_records(occ):
    """bbcourse._occluders' grouping, over an occluder pixel map {(x, y): (s, top)}: one record per (block,
    cell row, band of tops)"""
    groups = {}
    for (x, y), (sp, tp) in occ.items():
        groups.setdefault((y >> 3, x >> 3, sp), []).append((tp, x, y))
    records = []
    for (br, bc, sp) in sorted(groups):
        px = sorted(groups[(br, bc, sp)])
        band = []
        for p_ in px:
            if band and p_[0] - band[0][0] > B.BAND:
                records.append((br, bc, sp, band))
                band = []
            band.append(p_)
        records.append((br, bc, sp, band))
    out = []
    for br, bc, sp, band in records:
        mask = bytearray(b"\xff" * 16)
        for _, x, y in band:
            ly, lx = y & 7, x & 7
            mask[2 * ly + (lx >> 2)] &= ~(3 << (6 - 2 * (lx & 3))) & 0xFF
        out.append({"brow": br, "col": bc, "s": sp, "top": max(p_[0] for p_ in band), "mask": bytes(mask),
                    "pix": frozenset((x, y) for _, x, y in band)})
    out.sort(key=lambda r: (r["brow"], r["col"], r["s"], r["top"], r["mask"]))
    return out


def residual(c, depth, reach=None):
    """option A + RESIDUAL records: the occluder pixels the rule lays at some reachable position where the
    analytic model (front cells to DEPTH, unreadable ones SKIPPED rather than refused) does not - a prop's
    drawing, a split cell's, a cell past DEPTH, a floating face's underside.  The guest runs the model AND
    walks these records; the union lays at least what the rule lays.  -> the residual pixel map"""
    A = Analytic(c, depth)
    A.top_edge((0, 0))
    occ = {}
    sbuf, tbuf = c.sbuf, c.tbuf
    for r in (reach if reach is not None else c.reach):
        xl, xh = B.foot_x(r, c.x0)
        xl, xh = max(xl, 0), min(xh, c.width - 1)
        fr = []
        for n in front_cells(r.wx, r.wy, depth):
            if n in c.tiles and A.ok.get(n):
                fr.append((A.h[n], A.edge.get(256 * n[0] + n[1], {})))
        base = 8 * r.s + c.y0
        y0_ = max(B.foot_top(r, r.zhi) + c.y0 - 1, 0)
        y1_ = min(B.foot_top(r, r.zlo) + c.y0 + 30, c.lines - 1)
        for y in range(y0_, y1_ + 1):
            sr, tr = sbuf[y], tbuf[y]
            zlo_y = max(r.zlo, base - 14 - y)
            zhi_y = min(r.zhi, base + 17 - y)
            if zlo_y > zhi_y:
                continue
            for x in range(xl, xh + 1):
                sp = sr[x]
                if sp <= r.s:
                    continue
                tp = tr[x]
                za = -1 << 30
                for h, e in fr:
                    ey = e.get(x)
                    if ey is not None and y >= ey and h > za:
                        za = h
                if max(zlo_y, za) <= min(zhi_y, tp - 1):
                    occ[(x, y)] = (sp, tp)
    return occ


def analytic_cells(c, depth, step=2, tol=0):
    """-> ({cell: (positions, positions where the model differs from the rule by more than TOL ball pixels,
    unreadable)}): every reach cell's positions (z in STEP px, the ball's top-left on a 4 px lattice over the
    cell's area, airborne; a FLOOR's lowest heights grounded too) - the rule's hidden ball pixels against the
    model's"""
    A = Analytic(c, depth)
    sb_, tb_ = c.sbuf, c.tbuf
    out = {}
    for r in c.reach:
        if (r.wx, r.wy) in c.slabcells:
            continue
        n = bad = unread = 0
        for z in range(r.zlo, r.zhi + 1, step):
            for m in ((0, B.CLIMB) if r.kind != B.KIND_VOID and z <= r.zlo + 8 else (0,)):
                for gx in range(16 * r.wx, 16 * r.wx + 16, 4):
                    for gy in range(16 * r.wy, 16 * r.wy + 16, 4):
                        px = gx - gy + c.x0 - 8
                        py = (gx + gy) // 2 - z + c.y0 - 13
                        if px < 0 or py < 0 or px + 20 >= c.width or py + 16 >= c.lines:
                            continue
                        bp = B.ball_pixels(px, py)
                        rule = {(x, y) for (x, y) in bp if sb_[y][x] > r.s and tb_[y][x] > z + m}
                        n += 1
                        a = A.hidden(r.wx, r.wy, z, m, bp)
                        if a is None:
                            unread += 1
                            continue
                        if len(rule ^ a) > tol:
                            bad += 1
        out[(r.wx, r.wy)] = (n, bad, unread)
    return out


def v_analytic(c, depth=2, tol=0, cells=None):
    """option A's record reach: the positions of every cell the model does NOT reproduce at every position"""
    ac = cells if cells is not None else analytic_cells(c, depth, tol=tol)
    keep = {k for k, (n, bad, unread) in ac.items() if bad or unread}
    return [r for r in c.reach if (r.wx, r.wy) in keep or (r.wx, r.wy) in c.slabcells]


def v_vlow_walls(c):
    cut = wall_blocked(c)
    return [r for r in v_vlow(c) if (r.wx, r.wy) not in cut]


VARIANTS = (("base", v_base), ("novoid", v_novoid), ("pits", v_pits), ("vlow", v_vlow),
            ("vlow8", lambda c: v_vlow(c, 8)), ("vlow+walls", v_vlow_walls), ("vghost", v_vghost),
            ("vghost8", lambda c: v_vghost_k(c, 8)), ("vghost16", lambda c: v_vghost_k(c, 16)),
            ("avoid", v_avoid), ("aall", v_aall),
            ("res2", lambda c: ("res", residual(c, 2), c.reach)), ("res3", lambda c: ("res", residual(c, 3), c.reach)),
            ("res4", lambda c: ("res", residual(c, 4), c.reach)),
            ("res3+V", lambda c: ("res", residual(c, 3, v_vghost(c)), c.reach)),
            ("res4+V", lambda c: ("res", residual(c, 4, v_vghost(c)), c.reach)),
            ("avoidR3", lambda c: ("res", avoid_r(c, 3), c.reach)), ("avoidR4", lambda c: ("res", avoid_r(c, 4), c.reach)))


def avoid_r(c, depth):
    """option A in VOID cells only, rigorous: the rule's occluder pixels over every NON-void position (today's
    records), and over the VOID positions only the residual the model (DEPTH) misses"""
    nv = v_vghost(c)
    _r, occ = B._occluders(_CV(c), nv, c.x0, c.y0, c.cols, c.brows)
    occ = dict(occ)
    occ.update(residual(c, depth, [r for r in c.reach if r.kind == B.KIND_VOID and (r.wx, r.wy) not in c.slabcells]))
    return occ


# ---------------------------------------------------------------------------
# a variant's part
# ---------------------------------------------------------------------------

def occ_for(c, reach):
    """the tool's occluder pipeline over REACH: -> (merged records, part records,
    part masks, the per-block and per-row counts).  REACH may instead be ('res', occ map, the reach the
    records are walked over): option A's residual records"""
    if isinstance(reach, tuple):
        raw = group_records(reach[1])
        reach = reach[2]
    else:
        raw, _occ = B._occluders(_CV(c), reach, c.x0, c.y0, c.cols, c.brows)
    q = B.block_queries(reach, c.x0, c.y0, c.width)
    recs = B.merge_records(raw, q)
    masks, mindex, prec = [], {}, []
    for r in recs:
        km = B.dither(r["mask"])
        if km == B.ALLKEEP:
            continue
        if km not in mindex:
            mindex[km] = len(masks)
            masks.append(km)
        prec.append((r["brow"], r["col"], r["s"], r["top"], mindex[km]))
    pb, prow = {}, {}
    for r in recs:
        pb[(r["brow"], r["col"])] = pb.get((r["brow"], r["col"]), 0) + 1
        prow[r["brow"]] = prow.get(r["brow"], 0) + 1
    return raw, recs, prec, masks, pb, prow


def part_of(c, prec, masks, ghost=None):
    m = dict(c.model, recs=prec, masks=masks)
    if ghost:                               # option V: H - zlo in 8 px steps (rounded UP), in the VOID cell's
        g = m["grid"]                       # flags bits 4 - 7 (a goal's exit there; free on a VOID cell)
        cb = bytearray(m["cells"])
        for (wx, wy), (H, zlo, zhi) in ghost.items():
            s_, a_ = wx + wy, wx - wy
            i = 4 * ((s_ - g["smin"]) * g["kw"] + ((a_ - g["amin"]) >> 1))
            cb[i + 3] |= min(15, -(-(H - zlo) // 8)) << 4
        m["cells"] = bytes(cb)
    ram = B.encode_part(m, 4, c.fname)
    st = B.stored_form(m, 4, ram, c.fname)
    return m, ram, st


def sec_lens(ram):
    import struct
    diroff, nsec = struct.unpack_from("<HH", ram, 38)
    out = {}
    for j in range(nsec):
        tag, form, off, ln, dl = struct.unpack_from("<BBHHH", ram, diroff + 8 * j)
        out[chr(tag)] = (ln, dl)
    return out


def occ_ram(ram):
    s = sec_lens(ram)
    return sum(s.get(t, (0, 0))[0] for t in "IRKO")


def report_course(path, variants, png):
    t0 = time.time()
    c = B.compile_course(path)
    base_ram = c.cga
    rows = []
    for name, fn in variants:
        reach = fn(c)
        raw, recs, prec, masks, pb, prow = occ_for(c, reach)
        gh = ghost_heights(c) if name.startswith("vghost") else None
        if gh and name != "vghost":           # (graded: H - K is the stored height)
            k_ = int(name[6:])
            gh = {k: (max(zlo, H - k_), zlo, zhi) for k, (H, zlo, zhi) in gh.items()}
        m, ram, st = part_of(c, prec, masks, gh)
        if gh and name == "vghost":
            ge = ghost_error(c, gh)
            hs = [H - zlo for (H, zlo, zhi) in gh.values()]
            print("  vghost: %d VOID cells, %d ghosted somewhere; H - kill px: max %d, mean %.1f; over %d ghosted "
                  "positions today hides %.0f%% of the ball on average, under a quarter at %.0f%%, none at %.0f%%"
                  % (len(hs), sum(1 for h in hs if h), max(hs), sum(hs) / float(len(hs)), ge[0], 100 * ge[1],
                     100 * ge[2], 100 * ge[3]))
        rows.append({
            "v": name, "raw": len(raw), "recs": len(recs), "prec": len(prec), "masks": len(masks),
            "blk": max(pb.values(), default=0), "row": max(prow.values(), default=0),
            "ram": len(ram), "occram": occ_ram(ram),
            "lz4": B.packed_len(st, "lz4"), "lzb": B.packed_len(st, "lzb"),
            "ncells": len(reach) if not isinstance(reach, tuple) else len(reach[2]),
        })
    # the part with NO occluders at all: what occlusion costs, both ways, in context
    m0, ram0, st0 = part_of(c, [], [])
    none = {"ram": len(ram0), "lz4": B.packed_len(st0, "lz4"), "lzb": B.packed_len(st0, "lzb")}
    assert rows[0]["prec"] == len(c.model["recs"]) and rows[0]["ram"] == len(base_ram), \
        "the base variant does not reproduce the shipped part"
    return c, rows, none, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("courses", nargs="*")
    ap.add_argument("--only", help="comma-separated variant names")
    a = ap.parse_args()
    paths = a.courses or course_paths()
    vs = VARIANTS if not a.only else [v for v in VARIANTS if v[0] in a.only.split(",")]
    tot = {}
    for p in paths:
        c, rows, none, secs = report_course(p, vs, False)
        b = rows[0]
        print("\n%s (%s): %d cols x %d block rows; RAM %d, LZ4 %d, LZB %d; with NO occluders RAM %d, LZ4 %d, "
              "LZB %d  [%.0fs]" % (c.name, os.path.basename(p), c.cols, c.brows, b["ram"], b["lz4"], b["lzb"],
                                   none["ram"], none["lz4"], none["lzb"], secs))
        print("  %-11s %6s %6s %6s %5s %4s %4s %7s %7s %6s %6s %7s %7s" % (
            "variant", "raw", "rule", "part", "masks", "blk", "row", "RAM", "occRAM", "LZ4", "LZB", "dLZ4", "dLZB"))
        for r in rows:
            print("  %-11s %6d %6d %6d %5d %4d %4d %7d %7d %6d %6d %+7d %+7d" % (
                r["v"], r["raw"], r["recs"], r["prec"], r["masks"], r["blk"], r["row"], r["ram"], r["occram"],
                r["lz4"], r["lzb"], r["lz4"] - b["lz4"], r["lzb"] - b["lzb"]))
            t = tot.setdefault(r["v"], [0] * 6)
            for i, k in enumerate(("prec", "ram", "occram", "lz4", "lzb", "recs")):
                t[i] += r[k]
        t = tot.setdefault("(none)", [0] * 6)
        t[1] += none["ram"]
        t[3] += none["lz4"]
        t[4] += none["lzb"]
        sys.stdout.flush()
    print("\nALL: variant, part records, RAM, occluder RAM (I R K O), LZ4, LZB")
    for k, t in tot.items():
        print("  %-11s %7d %8d %8d %8d %8d" % (k, t[0], t[1], t[2], t[3], t[4]))


if __name__ == "__main__":
    main()
