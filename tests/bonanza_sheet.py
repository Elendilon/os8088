#!/usr/bin/env python3
"""BONANZA's SHEETS in the guest (SPEC.md 130.30.12): the package's own bz_cexp, bz_crshdr, bz_pread, bz_lsync
and bz_shchk under unicorn on TTALL, the test course whose picture part does not fit one part - the host half of
what a MartyPC play of TTALL sees on the glass.

    make BZDEV=1 bonanza && python3 tests/bonanza_sheet.py [--art DIR] [--red clamp|lanes|rowplanes|serve]

THE METHOD is bonanza_wide's (bonanza_dsplit's Guest): the package image assembled from the tree against a
BZDEV=1 art (TTALL is a TEST course, SPEC.md 130.54) and loaded at one segment of an emulated 8086; TTALL's
two sheets and its world part at three others, as bz_cload leaves them; its routines CALLED:

  1  THE EXPANSION: bz_cexp on each sheet's STORED form (BZ<K>.BIN, BZ<K>S1.BIN) and the world part's -> the
     tool's RAM forms, byte for byte (a sheet's map is n block rows, not BROWS: bz_cxmap counts its length).
  2  THE LAUNCH: bz_crshdr shows sheet 0 - bz_mrow its rows clamped to [m0, hic], its bounds EMPTY (the first
     window searches) - and bz_pread lays the lanes out against it.
  3  THE WALK DOWN AND BACK: every lane given a drawn pose its picture does not hold (bz_lsync, into the shown
     sheet), then the window's top stepped down the picture two card rows a frame (BZ_MAXR, the CGA's) and
     back, bz_shchk at each step: the sheet shown is the one the host's rule names (the shown one while it
     serves the top, else the first that does); after every step bz_mrow, bz_shlo / bz_shhi and every lane's
     bz_ltmo are the sheet's; every map word a frame may read - block rows [tb - 2, tb + 28] - is the model's
     (a lane's cell its DRAWN pose's); and no byte of any sheet past its map has moved.

--red clamp: bz_shmrow's tail not clamped (the rows past hic run on past the map) - item 3's table fails.
--red lanes: bz_shset without its bz_lsync - item 3's lanes' cells fail in the second sheet.
--red rowplanes: bz_cxmap counting BROWS, as before sheets - item 1 fails (the map overruns the blocks).
--red serve: bz_shchk's bound test inverted to a never-switch - item 3's sheet fails past the first seam.
"""
import argparse
import os
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bbcourse as BB          # noqa: E402
import bonanza_dsplit as D     # noqa: E402
import bonanza_ring as R       # noqa: E402

SEGS = (D.PS, 0x8000)           # the sheets' segments (D.PS sheet 0), and the world part's
WS = 0x9000
LSH = 1                         # the CGA's card row: two lines (bz_lsh)

REDS = {
    "clamp": [("bzgame.inc", "    sub ax, dx                  ; (hic, BZ_MROWS): the hic-th's\n",
               "                                ; (red: not clamped)\n")],
    "lanes": [("bzgame.inc", "    je .n\n    call bz_lsync\n.n:\n    inc bx\n", "    je .n\n.n:\n    inc bx\n")],
    "rowplanes": [("bonanza.asm", "    xchg ax, cx                 ; SPEC.md 130.30.12.1: its RAM length / ROWB\n"
                   "    xor dx, dx                  ; counts (a SHEET's map is n rows, every other\n"
                   "    div word [es:BZC_ROWB]      ; part's BROWS)\n    xchg ax, dx\n",
                   "    mov dx, [es:BZC_BROWS]\n")],
    "serve": [("bzgame.inc", "    cmp ax, [bz_shlo]\n    jl bz_shfind\n    cmp ax, [bz_shhi]\n    jg bz_shfind\n    ret\n",
               "    ret\n")],
}


def course():
    path = os.path.join(BB.COURSE_DIR, "ttall.bbc")
    c = BB.compile_course(open(path).read(), fname=path)
    if not BB.sheets_of(c.cga):
        raise SystemExit("bonanza_sheet: TTALL compiled to one picture part - it is the course that must not")
    return c


def guest(binp, sym, c):
    g = D.Guest(binp, sym, c.cga.sheets[0])
    for s, q in zip(SEGS, c.cga.sheets):
        g.mu.mem_write(s * 16, bytes(q))
    g.mu.mem_write(WS * 16, bytes(c.wcga))
    return g


def expand_check(binp, sym, c):
    """item 1: bz_cexp on each stored form -> its RAM form"""
    g = guest(binp, sym, c)
    bad = []
    for name, seg, st, ram in [("sheet %d" % i, s, st_, q) for i, (s, st_, q)
                               in enumerate(zip(SEGS, c.sstored, c.cga.sheets))] + [("world", WS, c.wstored,
                                                                                      c.wcga)]:
        g.mu.mem_write(seg * 16, bytes(st) + bytes(0x10000 - len(st)))
        g.w("bz_cseg", seg, 2)
        g.call("bz_cexp")
        got = bytes(g.mu.mem_read(seg * 16, len(ram)))
        if got != bytes(ram):
            at_ = next(i for i in range(len(ram)) if got[i] != ram[i])
            bad.append("%s first differs at %d" % (name, at_))
    return not bad, "TTALL: bz_cexp on its %d sheets' and its world part's stored forms -> the RAM forms%s" % (
        len(c.sstored), "" if not bad else " -- " + "; ".join(bad))


def want_mrow(c, s):
    pl = c.plan
    x, rowb = pl["sheets"][s], 2 * c.cols
    return [BB.HDR + (min(max(br, x["m0"]), x["hic"]) - x["m0"]) * rowb for br in range(256)]


def walk_check(binp, sym, c):
    """items 2 and 3"""
    res = []
    pl, B, cols, rowb = c.plan, c.brows, c.cols, 2 * c.cols
    g = guest(binp, sym, c)
    g.w("bz_cseg", WS, 2)
    g.w("bz_mseg", SEGS[0], 2)
    for i, s in enumerate(SEGS):
        g.w("bz_shseg", s, 2) if not i else g.mu.mem_write(D.CS * 16 + sym["bz_shseg"] + 2 * i,
                                                            struct.pack("<H", s))
    g.w("bz_crs", R.CRS_K["ttall"])
    g.w("bz_lsh", LSH)
    g.call("bz_crshdr")
    mrow = [g.r("bz_mrow", 2, k=2 * br) for br in range(256)]
    ok2 = (g.r("bz_mseg", 2) == SEGS[0] and g.r("bz_shn") == pl["k"] and g.r("bz_shcur") == 0
           and mrow == want_mrow(c, 0) and g.r("bz_shlo", 2) == 0x7FFF and g.r("bz_shhi", 2) == 0x8000)
    g.w("bz_R0n", 0, 2)
    g.w("bz_R0", 0, 2)
    g.call("bz_pread")
    lanes = [d for d in c.part["props"] if d.get("lane")]
    nl = g.r("bz_nlane")
    res.append((ok2 and nl == len(lanes), "TTALL: bz_crshdr shows sheet 0 of %d (bz_mrow its rows %d - %d clamped, "
                "its bounds empty); bz_pread lays out %d lanes (the part's %d)" % (
                    pl["k"], pl["sheets"][0]["m0"], pl["sheets"][0]["hic"], nl, len(lanes))))
    # every lane a drawn pose its part's map does not hold (pose 1, the map's being pose 0), into sheet 0
    drawn = {}
    for i, d in enumerate(lanes):
        L = d["lane"]
        pose = 1 % L["poses"]
        g.mu.reg_write(g.X.UC_X86_REG_BX, i)
        g.call("bz_lsync", ax=pose)
        drawn[i] = pose
    pics = [bytes(q) for q in c.cga.sheets]
    mlen = rowb * pl["n"]
    cur, worst = 0, []
    tops = list(range(0, (8 * B - 200) >> LSH, 2))
    tops += tops[::-1]
    serve = [((x["tlo"] >> LSH), (x["thi"] >> LSH)) for x in pl["sheets"]]
    switches = 0
    # every block row's map words as the model and the DRAWN poses have them, per sheet (its blocks' offset
    # and its lanes' pose words): computed once, compared a row at a time below
    lane_at = {}
    for i, d in enumerate(lanes):
        L = d["lane"]
        for br in range(L["brow"], L["brow"] + L["h"]):
            for col in range(L["col"], L["col"] + L["w"]):
                lane_at.setdefault((br, col), i)
    wrow = []
    for q in pics:
        blkoff = struct.unpack_from("<H", q, 12)[0]
        rows_ = []
        for br in range(B):
            row = []
            for col in range(cols):
                lane = lane_at.get((br, col))
                if lane is None:
                    row.append(blkoff + 16 * c.model["idx"][cols * br + col])
                else:
                    L = lanes[lane]["lane"]
                    k = drawn[lane] * L["w"] * L["h"] + (br - L["brow"]) * L["w"] + col - L["col"]
                    row.append(struct.unpack_from("<H", q, L["off"] + 2 * k)[0])
            rows_.append(tuple(row))
        wrow.append(rows_)
    for r0 in tops:
        g.w("bz_R0n", r0, 2)
        g.call("bz_shchk")
        lo, hi = serve[cur]
        if not lo <= r0 <= hi:
            cur = next(k for k, (a_, b_) in enumerate(serve) if a_ <= r0 <= b_)
            switches += 1
        shown = SEGS.index(g.r("bz_mseg", 2)) if g.r("bz_mseg", 2) in SEGS else -1
        if shown != cur or g.r("bz_shcur") != cur:
            worst.append("top %d: sheet %d shown, the rule's %d" % (r0, shown, cur))
            break
        mrow = [g.r("bz_mrow", 2, k=2 * br) for br in range(256)]
        if mrow != want_mrow(c, cur) or (g.r("bz_shlo", 2), g.r("bz_shhi", 2)) != serve[cur]:
            worst.append("top %d: sheet %d's bz_mrow or bounds wrong" % (r0, cur))
            break
        for i, d in enumerate(lanes):
            L = d["lane"]
            if g.r("bz_ltmo", 2, k=2 * i) != mrow[L["brow"]] + 2 * L["col"]:
                worst.append("top %d: lane %d's bz_ltmo %04Xh" % (r0, i, g.r("bz_ltmo", 2, k=2 * i)))
        seg = SEGS[cur]
        mem = bytes(g.mu.mem_read(seg * 16, len(pics[cur])))
        if mem[HDRM(mlen):] != pics[cur][HDRM(mlen):]:
            worst.append("top %d: sheet %d changed past its map" % (r0, cur))
            break
        tb = (r0 << LSH) >> 3
        for br in range(max(0, tb - BB.SH_WLO), min(B, tb + BB.SH_WHI + 1)):
            got_ = struct.unpack_from("<%dH" % cols, mem, mrow[br])
            want_ = wrow[cur][br]
            if got_ == want_:
                continue
            for col in range(cols):
                w, want = got_[col], want_[col]
                lane = lane_at.get((br, col))
                if w != want:
                    worst.append("top %d (block row %d): sheet %d's map word at row %d column %d %04Xh, not %04Xh%s"
                                 % (r0, tb, cur, br, col, w, want, " (lane %d)" % lane if lane is not None else ""))
                    break
            if worst:
                break
        if worst:
            break
    res.append((not worst and switches >= 2, "TTALL: the window's top down %d card rows and back (%d steps), "
                "bz_shchk at each: %d switches, the sheet the rule's, its rows, bounds and lanes' words, the "
                "map words every frame may read the model's (lanes' cells their DRAWN poses), nothing past a "
                "map moved%s" % (tops[len(tops) // 2 - 1], len(tops), switches,
                                 "" if not worst else " -- " + "; ".join(worst[:3]))))
    return res


def HDRM(mlen):
    return BB.HDR + mlen


def check(art=None, red=None, verbose=True):
    with tempfile.TemporaryDirectory() as td:
        if art:
            a_, at0 = os.path.abspath(art), R.at
            R.at = lambda q: a_ if q == "build/bonanza-art" else at0(q)
            if "-DBZDEV" not in R.NASM:
                R.NASM.append("-DBZDEV")
        else:
            R.dev()
        binp, sym = D.build(td, REDS[red] if red else ())
        c = course()
        try:
            res = [expand_check(binp, sym, c)]
        except Exception as e:                  # (a red arm's expander can run off: that is its failure)
            res = [(False, "TTALL: bz_cexp stopped: %s" % e)]
        try:
            res += walk_check(binp, sym, c)
        except Exception as e:                  # (a red arm's guest can run off: that is its failure)
            res.append((False, "TTALL: the walk stopped: %s" % e))
    ok = True
    for good, what in res:
        if verbose:
            print("  %-4s %s" % ("ok" if good else "FAIL", what))
        ok = ok and good
    return ok, res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--art", help="a BZDEV=1 build's bonanza-art directory (default: the BZDEV=1 tree's, built)")
    ap.add_argument("--red", choices=sorted(REDS), help="a red arm: must FAIL")
    a = ap.parse_args()
    ok, res = check(a.art, a.red)
    if a.red:
        want = {"clamp": lambda r: not r[2][0], "lanes": lambda r: not r[2][0],
                "rowplanes": lambda r: not r[0][0], "serve": lambda r: not r[2][0]}[a.red]
        good = want(res)
        print("bonanza_sheet --red %s: %s" % (a.red, "caught (red, as it must be)" if good else "NOT CAUGHT"))
        return 0 if good else 1
    print("bonanza_sheet: %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
