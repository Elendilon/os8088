#!/usr/bin/env python3
"""BONANZA's WIDEST COURSE in the guest (SPEC.md 130.10.4.2's amendment, 130.54.8): the package's own
bz_crshdr and box fill under unicorn on TWIDE, the 160-word-column (1,280 px) test course - the host half of
the width the MartyPC rows (bonanzaring, bonanzaperf, bonanzamega, the VGA rows) see on the glass.

    make bonanza && python3 tests/bonanza_wide.py [--art DIR] [--red mrow|shift]

THE METHOD is bonanza_dsplit's: the package image assembled from the tree (bonanza_ring's assemble and
symbols), loaded at one segment of an emulated 8086, TWIDE's RAM form (bbcourse's compile of
apps/bonanza/courses/twide.bbc) at another, and its routines CALLED:

  1  THE TABLE: bz_crshdr on TWIDE builds bz_mrow, BZ_MROWS words, word br = MAP + br ROWB (ROWB 320, a
     row width that is neither of the old shift's two); and on HOP (128 columns) the same with ROWB 256.
  2  THE FILL TO THE FAR EAST: bz_boxc (the CGA's and Hercules' box compose: the map row from bz_mrow, the
     blocks down each word column) on boxes across the picture - its west edge, its middle, and every box
     whose last word column is 159, at line offsets 0 - 7 in their first block - with the slab, the shadow
     and the ball switched off: the buffer is EXACTLY the part's words, map[L >> 3][c] + 2 (L AND 7), for
     every line and column of the box.

--red mrow: bz_crshdr's loop cut to its first word (the table NOT built past row 0) - item 1 and the fill's
boxes below block row 0 must fail.  --red shift: bz_boxc's row index made the old shift form at width 128
(`2 (L >> 3) << 7`, the map row of a 128-column course), as a writer left behind would be - the fill must fail on TWIDE and pass on HOP.
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

BOXW = 4                        # bzvideo.inc's BZ_BOXW: a buffer line's words
BUF = 0xF000                    # the box's buffer, in the package's segment past its image and bss

REDS = {
    "mrow": [("bonanza.asm", "    cmp bx, bz_mrow + 2 * BZ_MROWS\n    jne .mrow\n", "")],
    "shift": [("bzvideo.inc", "    xchg ax, bx\n    mov bx, [bz_mrow + bx]      ; MAP + (L0 >> 3) ROWB (130.10.4.2)\n"
               "    mov ax, [si]\n", "    mov cl, 7\n    shl ax, cl\n    add ax, BZC_MAP\n    xchg ax, bx\n"
               "    mov ax, [si]\n")],
}


def compiled(name):
    path = os.path.join(BB.COURSE_DIR, name + ".bbc")
    return BB.compile_course(open(path).read(), fname=path)


def table_check(g, c):
    """item 1: bz_crshdr's bz_mrow against MAP + br ROWB -> (ok, what)"""
    rowb = struct.unpack_from("<H", c.cga, 24)[0]
    bad = [br for br in range(BB.BROWS_MAX)
           if g.r("bz_mrow", 2, k=2 * br) != (BB.HDR + br * rowb) & 0xFFFF]
    return not bad, "%s: bz_mrow's %d words MAP + br x %d%s" % (
        c.name, BB.BROWS_MAX, rowb, "" if not bad else " -- %d wrong, the first at row %d" % (len(bad), bad[0]))


def fill_check(g, c, boxes):
    """item 2: bz_boxc on each (x0, y0, w, h) -> (ok, what)"""
    p = c.cga
    cols, rowb = struct.unpack_from("<H", p, 4)[0], struct.unpack_from("<H", p, 24)[0]
    g.w("bz_pov", 1)                            # (the slab over the ball: bz_pover's, not the fill's)
    g.w("bz_snv", 0)                            # (no shadow)
    g.w("bz_hidn", 1)                           # (the ball hidden: no sprite)
    wrong = []
    for x0, y0, w, h in boxes:
        desc = g.sym["bz_boxbuf"]               # (a descriptor's 10 bytes, at the first buffer's head)
        for k, v in enumerate((x0, y0, w, h, BUF)):
            g.mu.mem_write(D.CS * 16 + desc + 2 * k, struct.pack("<H", v))
        g.mu.mem_write(D.CS * 16 + BUF, b"\xa5" * (2 * BOXW * h))
        g.mu.reg_write(g.X.UC_X86_REG_SI, desc)
        call_si(g, "bz_boxc", desc)
        got = g.mu.mem_read(D.CS * 16 + BUF, 2 * BOXW * h)
        for ln in range(h):
            L = y0 + ln
            for cc in range(w):
                blk = struct.unpack_from("<H", p, BB.HDR + (L >> 3) * rowb + 2 * (x0 + cc))[0]
                want = struct.unpack_from("<H", p, blk + 2 * (L & 7))[0]
                have = struct.unpack_from("<H", got, 2 * BOXW * ln + 2 * cc)[0]
                if have != want:
                    wrong.append((x0, y0, L, x0 + cc, have, want))
    assert x0 + w <= cols
    return not wrong, "%s: bz_boxc on %d boxes (word columns %d - %d)%s" % (
        c.name, len(boxes), min(b[0] for b in boxes), max(b[0] + b[2] - 1 for b in boxes),
        "" if not wrong else " -- %d words wrong, the first box (%d, %d) line %d column %d: %04Xh, not %04Xh"
        % ((len(wrong),) + wrong[0]))


def call_si(g, n, si):
    """Guest.call with SI set (bz_boxc's descriptor): the dispatcher's call, SI written after its resets"""
    X = g.X
    for reg, v in ((X.UC_X86_REG_CS, D.CS), (X.UC_X86_REG_DS, D.CS), (X.UC_X86_REG_ES, D.CS),
                   (X.UC_X86_REG_SS, D.SS)):
        g.mu.reg_write(reg, v)
    g.mu.mem_write(D.SS * 16 + 0xFFEE, struct.pack("<H", D.STUB))
    g.mu.reg_write(X.UC_X86_REG_SP, 0xFFEE)
    g.mu.reg_write(X.UC_X86_REG_SI, si)
    g.mu.reg_write(X.UC_X86_REG_EFLAGS, 2)
    g.mu.emu_start(D.CS * 16 + g.sym[n], D.CS * 16 + D.STUB, count=2000000)
    assert g.mu.reg_read(X.UC_X86_REG_SP) == 0xFFF0, "%s left the stack unbalanced" % n


def boxes_for(c, rnd):
    """the west edge, the middle, and the far east at every first-line offset, some random"""
    cols, lines = c.cols, c.lines
    out = []
    for w in (1, 2, 3, 4):
        for j in range(8):
            y0 = min(8 * rnd.randrange(max(1, lines // 8 - 3)) + j, lines - 24)
            out.append((cols - w, y0, w, rnd.choice((8, 13, 24))))
    out += [(0, 0, 4, 24), (cols // 2 - 2, lines // 2, 4, 17), (cols - 4, lines - 24, 4, 24)]
    out += [(rnd.randrange(cols - 4), rnd.randrange(lines - 24), rnd.randrange(1, 5), rnd.randrange(1, 25))
            for _ in range(24)]
    return out


def check(art=None, red=None, verbose=True):
    rnd = random.Random(1280)
    with tempfile.TemporaryDirectory() as td:
        if art:                                 # (a private tree's art: what at() would name build/'s)
            a_, at0 = os.path.abspath(art), R.at
            R.at = lambda q: a_ if q == "build/bonanza-art" else at0(q)
        binp, sym = D.build(td, REDS[red] if red else ())
        res = []
        for name in ("twide", "hop"):
            c = compiled(name)
            g = D.Guest(binp, sym, c.cga)
            g.w("bz_cseg", D.PS, 2)
            g.w("bz_mseg", D.PS, 2)
            g.call("bz_crshdr")
            res.append(table_check(g, c))
            res.append(fill_check(g, c, boxes_for(c, rnd)))
    ok = True
    for good, what in res:
        if verbose:
            print("  %-4s %s" % ("ok" if good else "FAIL", what))
        ok = ok and good
    return ok, res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--art", help="the build's bonanza-art directory (default: build/bonanza-art, the tree's)")
    ap.add_argument("--red", choices=sorted(REDS), help="a red arm: must FAIL")
    a = ap.parse_args()
    ok, res = check(a.art, a.red)
    if a.red:
        want = {"mrow": lambda r: not r[0][0] and not r[1][0], "shift": lambda r: not r[1][0] and r[3][0]}[a.red]
        good = want(res)
        print("bonanza_wide --red %s: %s" % (a.red, "caught (red, as it must be)" if good else "NOT CAUGHT"))
        return 0 if good else 1
    print("bonanza_wide: %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
