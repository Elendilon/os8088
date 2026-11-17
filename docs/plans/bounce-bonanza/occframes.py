#!/usr/bin/env python3
"""BOUNCE BONANZA - what the occluder pass does on the frames the demos play
(the occlusion deep-dive, 2026-11-17).  NOT a build input; nothing in `make`
runs it.

Each course's shipped demo (MOON, PEAK and the PLAYGROUND's authored .bzd, the
route demo of the others, BENCH's autopilot) is replayed through the binding
model, and at every step the occluder pass is walked as bz_occ walks it on the
shipped part (the 4-byte records, OCCIDX, the dithered masks): the gate (OCC
airborne, OCCG grounded), the block rows, the records tested, the GROUPS laid
and the LINES laid.  Then each frame is PRICED (an 8088 model of the pass from
its instructions, below - PREDICTED, one box a frame) under:
  today         every footprint line of a laid group's block row is laid
  lineclip      a group lays only its mask's ACTIVE lines (a line that is not
                FFFFh once dithered), from a per-mask line range made at the
                launch (option X)
  vghost        option V: in a VOID cell the pass does not run; below the
                cell's ghost height the ball is drawn ghosted (+GHOST clk)
Every step is taken as a frame (the guest presents fewer, so this is the pass's
cost per PLAYED step, the same weighting on every arm).

    python3 docs/plans/bounce-bonanza/occframes.py [course.bbc ...]
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import occproto as P  # noqa: E402
B = P.B

# the pass, priced from bzvideo.inc's bz_occ / bz_olay as built (8088: 8086 clocks + 4 a word access, each
# instruction at least 4.34 clk a byte, x 1.05): ESTIMATED to the nearest ten
PASS_FIXED = 520        # the gate taken, the pushes and pops, the lines and columns, the keys (.key)
PASS_ROW = 210          # a block row: its key and clamp, the summary test, OCCIDX, the hint proved
PASS_REC = 45           # a record tested (cmp cl / jb, add si / cmp / jae, mov al / cmp / je)
PASS_PREP = 260         # bz_oprep, a row's first laid record
PASS_AND = 70           # bz_oand's overhead, per further laid record of a group (+ 60 a line)
PASS_ANDLINE = 60
LAY_GROUP = 430         # bz_olay's entry and exit and one box's clip arithmetic, per group
LAY_LINE = 105          # bz_olay's .line: lodsw, mov, xor [es:di], and [bx], xor, stosw, add, inc, inc, loop
GHOST = 520             # option V's ghosted ball: the sprite drawn through the checker, +2 ops a word,
                        # 2.5 words a line, 16 lines, and the decision (ESTIMATED)
LINECLIP = 40           # option X's per-group range read and clip (ESTIMATED)
# option A's model on the guest (ESTIMATED from a sketch, not from code: SPEC.md 128.29's story A.2 measures it)
A_CELL = 80             # a front cell read through ROWTAB, its highest corner against z_b + m (most leave here)
A_OCC = 750             # an occluding front cell: its corners on the screen, and per footprint line its span
                        # (two adds and a clamp a line, 16 lines) merged into the line's coverage
A_WORD = 50             # a PARTLY covered word of a footprint line: two edge-table lookups, AND, OR the checker, store
A_WORDFULL = 15         # a WHOLLY covered word: the checker alone, stored
A_MISS = 40             # a front cell above the ball whose top edge is below the footprint: one screen-line test
A_DEPTH = 4


def demo_log(c, K):
    stem = os.path.splitext(os.path.basename(c.fname))[0]
    f = os.path.join(B.ROOT, "apps", "bonanza", "demos", stem + ".bzd")
    if os.path.exists(f):
        d = B.parse_bzd(open(f).read(), f)
        return B.bzd_log(d, K), "authored " + stem + ".bzd"
    return B.route_demo(c, K), "route demo"


def active(mask, i0, n):
    """the lines [i0, i0 + n) of a dithered mask that lay something"""
    return [i for i in range(i0, i0 + n) if mask[2 * i:2 * i + 2] != b"\xff\xff"]


def walk(c, rows_by, px, py, sb, zb, air):
    """bz_occ's walk at one position -> (rows walked, records tested, [(group: the laid records, the lines
    [i0, i0 + n) of the block, the active lines after the AND)])"""
    m = 0 if air else B.CLIMB
    x4 = px & ~3
    c0, c1 = x4 >> 3, (x4 + B.FOOT_W - 1) >> 3
    rows = tested = 0
    groups = []
    for br in range(py >> 3, ((py + B.FOOT_H - 1) >> 3) + 1):
        recs = rows_by.get(br, ())
        rows += 1
        f0 = max(py, 8 * br)
        f1 = min(py + B.FOOT_H, 8 * br + 8)
        by = {}
        for (col, s, top, mi) in recs:
            if c0 <= col <= c1:
                tested += 1
                if sb < s and zb + m < top:
                    by.setdefault(col, []).append(mi)
        for col, mis in sorted(by.items()):
            mk = bytearray(c.masks[mis[0]])
            for mi in mis[1:]:
                for i in range(16):
                    mk[i] &= c.masks[mi][i]
            act = active(bytes(mk), f0 - 8 * br, f1 - f0)
            groups.append((len(mis), f1 - f0, len(act)))
    return rows, tested, groups


def price(rows, tested, groups, clip=False):
    clk = PASS_FIXED + PASS_ROW * rows + PASS_REC * tested
    if groups:
        clk += PASS_PREP
    for nrec, n, nact in groups:
        clk += (nrec - 1) * (PASS_AND + PASS_ANDLINE * n)
        if clip:
            clk += LINECLIP + (LAY_GROUP + LAY_LINE * nact if nact else 0)
        else:
            clk += LAY_GROUP + LAY_LINE * n
    return clk


def price_a(c, An, rrows_by, px, py, sb, zb, air, cell):
    """option A4R at one position: the model over the front cells, then the residual records' walk, the
    union laid once per covered word and block row -> (clk, front cells read, occluding)"""
    m = 0 if air else B.CLIMB
    x4 = px & ~3
    fr = [n for n in P.front_cells(cell[0], cell[1], A_DEPTH) if n in c.tiles]
    high = [n for n in fr if An.ok.get(n) and An.h[n] > zb + m]
    foot = {(x, y) for x in range(x4, x4 + B.FOOT_W) for y in range(py, py + B.FOOT_H)}
    hid = set()
    occl = []
    for n in high:
        e = An.edge.get(256 * n[0] + n[1], {})
        h1 = {(x, y) for (x, y) in foot if e.get(x) is not None and y >= e[x]}
        if h1:
            occl.append(n)
            hid |= h1
    words = {}
    for (x, y) in hid:
        words[(y, x >> 3)] = words.get((y, x >> 3), 0) + 1
    full = sum(1 for k, v in words.items() if v == 8)
    clk = (PASS_FIXED + A_CELL * len(fr) + A_OCC * len(occl) + A_MISS * (len(high) - len(occl))
           + A_WORD * (len(words) - full) + A_WORDFULL * full)
    rows, tested, groups = walk(c, rrows_by, px, py, sb, zb, air) if rrows_by else (0, 0, [])
    clk += PASS_ROW * rows + PASS_REC * tested
    segs = {(y >> 3, w) for (y, w) in words}           # one lay a covered word and block row; a residual group
    nlay = len(segs) + len(groups)                     # is counted as a lay of its own (an overcount where it
                                                       # falls on a covered word, which ANDs into that lay)
    lines = 0
    for (br, w) in segs:
        lines += min(py + B.FOOT_H, 8 * br + 8) - max(py, 8 * br)
    lines += sum(g[1] for g in groups)
    clk += LAY_GROUP * nlay + LAY_LINE * lines
    return clk, len(fr), len(occl)


def course_frames(c, K):
    log, what = demo_log(c, K)
    rows_by = {}
    for (br, col, s, top, mi) in c.model["recs"]:
        rows_by.setdefault(br, []).append((col, s, top, mi))
    gh = P.ghost_heights(c)
    An = P.Analytic(c, A_DEPTH)
    An.top_edge((0, 0))
    _raw, _recs, prec, masks, _pb, _pr = P.occ_for(c, ("res", P.residual(c, A_DEPTH), c.reach))
    rrows_by = {}
    for (br, col, s_, top, mi) in prec:
        rrows_by.setdefault(br, []).append((col, s_, top, mi))
    cA = type("C", (), {})()
    cA.masks, cA.tiles = masks, c.tiles
    _K, mat, kt, _fl = B.decode_log_t(log)
    p = B.Physics(c, play=True, mat=mat)
    st = {"steps": 0, "gated": 0, "gvoid": 0, "today": 0.0, "clip": 0.0, "vghost": 0.0, "ghosted": 0,
          "lines": 0, "act": 0, "groups": 0, "worst": 0, "worst_clip": 0, "worst_v": 0, "a": 0.0, "worst_a": 0,
          "acells": 0, "aocc": 0}
    for k, t in kt:
        p.step(k, t)
        if p.tout:
            break
        st["steps"] += 1
        if p.tube:
            continue
        cell = (p.gx >> 12, p.gy >> 12)
        cl = p.cell(*cell)
        if not cl[4] & (B.FL_OCC if p.air else B.FL_OCCG):
            continue
        st["gated"] += 1
        rows, tested, groups = walk(c, rows_by, p.px, p.py, p.sb, p.zb, p.air)
        a, b = price(rows, tested, groups), price(rows, tested, groups, clip=True)
        st["today"] += a
        st["clip"] += b
        st["worst"] = max(st["worst"], a)
        st["worst_clip"] = max(st["worst_clip"], b)
        ca, nfr, nocc = price_a(cA, An, rrows_by, p.px, p.py, p.sb, p.zb, p.air, cell)
        st["a"] += ca
        st["worst_a"] = max(st["worst_a"], ca)
        st["acells"] += nfr
        st["aocc"] += nocc
        st["groups"] += len(groups)
        st["lines"] += sum(g[1] for g in groups)
        st["act"] += sum(g[2] for g in groups)
        if cl[3] == B.KIND_VOID and cell not in c.slabcells:
            st["gvoid"] += 1
            g = gh.get(cell)
            if g and p.zb < g[0]:
                st["ghosted"] += 1
                st["vghost"] += GHOST
        else:
            st["vghost"] += a
            st["worst_v"] = max(st["worst_v"], a)
    return what, st


def main():
    paths = sys.argv[1:] or P.course_paths()
    print("per PLAYED STEP of each course's demo, the pass PREDICTED (one box; see the constants)")
    print("%-6s %-24s %6s %6s %5s %7s %7s %7s %7s %6s %6s %6s %6s  %s" % (
        "course", "demo", "steps", "gated", "void", "today", "lineclp", "vghost", "A4R", "worst", "w.clip", "w.V",
        "w.A4R", "groups, lines laid -> active; A: front cells, occluding a frame"))
    for K, path in enumerate(paths):
        c = B.compile_course(path)
        what, s = course_frames(c, K)
        g = max(s["gated"], 1)
        print("%-6s %-24s %6d %6d %5d %7.0f %7.0f %7.0f %7.0f %6d %6d %6d %6d  %d, %d -> %d (%.0f%%); %.1f, %.2f" % (
            c.name, what, s["steps"], s["gated"], s["gvoid"], s["today"] / g, s["clip"] / g, s["vghost"] / g,
            s["a"] / g, s["worst"], s["worst_clip"], s["worst_v"], s["worst_a"], s["groups"], s["lines"], s["act"],
            100.0 * s["act"] / max(s["lines"], 1), s["acells"] / g, s["aocc"] / g))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
