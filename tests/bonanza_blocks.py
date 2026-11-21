#!/usr/bin/env python3
"""BONANZA PAST 1,024 BLOCKS in the guest (SPEC.md 130.56): the package's own bz_cexp (its form 9 ROWNIBS,
bz_cxnib), bz_hgen and bz_hxlat, bz_crshdr and bz_boxc, and the VGA part's BZV_CONV, under unicorn on TBLK -
bbcourse's scratch course of 1,386 blocks (tblk_text: no course file, in no build).

    make bonanza && python3 tests/bonanza_blocks.py [--art DIR] [--red mask2|swap|noform]

THE METHOD is bonanza_wide's (bonanza_dsplit's Guest). No course of the build passes 1,024 blocks, so its
BZ_FORMS has no bit 9 and its package no bz_cxnib: the package is assembled here against a COPY of the build's
art whose BZ_FORMS carries bit 9 - the package a build with such a course would ship.  The VGA part is the
build's own art's (BZV_CONV reads the RAM form, after the expansion, and reads no form), run beside the
package it was linked against:

  1  THE EXPANSION: bz_cexp on each of TBLK's two parts' STORED forms (the picture part's map form 9) -> the
     tool's RAM forms, byte for byte; and on a synthetic MAP-ONLY part (bbcourse.rownibs_synth) whose map
     names every high nibble 0 - 15 in both cells of a byte, which no course can reach.
  2  THE CGA: bz_crshdr on TBLK, then bz_boxc on boxes over every block row whose cells name a block past
     1,023 and some random ones: the buffer is EXACTLY the part's words, map[L >> 3][c] + 2 (L AND 7).
  3  THE HERCULES: bz_hgen and bz_hxlat on TBLK's picture part -> bbcourse.herc_translate_course's bytes, the
     blocks past 1,023 among them; then item 2's boxes on the translated part.
  4  THE VGA: BZV_CONV on TBLK's picture part -> every block word w as its planar pair, tl[w & 255] OR
     tr[w >> 8] (bzvga.asm's two tables, BZV_NIBS's rule, modelled here), every block past 1,023 among them;
     the map and everything past the blocks unmoved.

--red mask2: bz_cxnib keeping two high bits (`and ah, 3`, ROWPLANES' mask) - item 1 fails.
--red swap: bz_cxnib's cells reading each other's nibble - item 1 fails.
--red noform: the dispatch table's entry 9 bz_cxret (the map left as stored) - item 1 fails.
"""
import argparse
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bbcourse as BB          # noqa: E402
import bonanza_dsplit as D     # noqa: E402
import bonanza_ring as R       # noqa: E402
import bonanza_wide as W       # noqa: E402

WS = 0x8000                     # the world part's segment (the picture part at D.PS)
VS = 0x9000                     # the VGA part's
ES0 = 0xA000                    # an empty segment: bz_vbseg (its first six bytes the zero bz_bsegs: no balls)

REDS = {
    "mask2": [("bonanza.asm", "    mov ah, dl\n    and ah, 0fh\n", "    mov ah, dl\n    and ah, 3\n")],
    "swap": [("bonanza.asm", "    mov ah, dl\n    and ah, 0fh\n    shl ax, cl\n",
              "    mov ah, dl\n    shr ah, cl\n    shl ax, cl\n"),
             ("bonanza.asm", "    es lodsb                    ; the odd cell: the high nibble\n    mov ah, dl\n"
              "    shr ah, cl\n", "    es lodsb\n    mov ah, dl\n    and ah, 0fh\n")],
    "noform": [("bonanza.asm", "    dw bz_cxnib                 ;", "    dw bz_cxret                 ;")],
}


def forms_art(td, art):
    """a copy of ART whose bzcourse.inc's BZ_FORMS carries bit 9 (ROWNIBS) -> its path"""
    out = os.path.join(td, "art9")
    shutil.copytree(art, out)
    p = os.path.join(out, "bzcourse.inc")
    t = open(p).read().split("\n")
    k = next(i for i, ln in enumerate(t) if ln.startswith("BZ_FORMS"))
    v = int(t[k].split()[2].rstrip("h"), 16)
    t[k] = "BZ_FORMS        equ %04Xh    ; (bonanza_blocks: bit 9 added, SPEC.md 130.56)" % (v | 0x200)
    open(p, "w").write("\n".join(t))
    return out


def expand_check(binp, sym, c):
    """item 1: bz_cexp on each stored form -> its RAM form; and on the synthetic map-only part"""
    bad = []
    parts = [("the picture part", c.stored, c.cga)] + ([("the world part", c.wstored, c.wcga)] if c.split else [])
    ram, st, idx = BB.rownibs_synth()
    parts.append(("the synthetic map (nibbles 0 - 15)", st, ram))
    for what, stored, want in parts:
        g = D.Guest(binp, sym, stored)
        g.w("bz_cseg", D.PS, 2)
        try:
            g.call("bz_cexp")
        except Exception as e:                  # (a red arm's expander can run off: that is its failure)
            bad.append("%s: bz_cexp stopped: %s" % (what, e))
            continue
        got = bytes(g.mu.mem_read(D.PS * 16, len(want)))
        if got != bytes(want):
            i = next(j for j in range(len(want)) if got[j] != want[j])
            bad.append("%s first differs from its RAM form at %d" % (what, i))
    return not bad, "TBLK (%d blocks): bz_cexp on its %d parts' stored forms (map form %d) and the synthetic map " \
        "-> the RAM forms byte for byte%s" % (len(c.model["blocks"]) // 16, 1 + c.split, BB.F_ROWNIBS,
                                              "" if not bad else " -- " + "; ".join(bad))


def far_rows(c):
    """the block rows holding a cell that names a block past 1,023"""
    return sorted(set(k // c.cols for k, i in enumerate(c.model["idx"]) if i >= BB.BLK_ROWP))


def boxes(c, rnd):
    """a 4-word box over the first cells past 1,023 in each such block row, and some random"""
    out = []
    for br in far_rows(c):
        cs = [k % c.cols for k in range(br * c.cols, (br + 1) * c.cols) if c.model["idx"][k] >= BB.BLK_ROWP]
        x0 = min(cs[0], c.cols - 4)
        out.append((x0, min(8 * br + rnd.randrange(8), c.lines - 24), 4, rnd.choice((8, 13, 24))))
    out += [(rnd.randrange(c.cols - 4), rnd.randrange(c.lines - 24), rnd.randrange(1, 5), rnd.randrange(1, 25))
            for _ in range(16)]
    return out


class Course:
    """item 2's fill_check wants .cga, .cols, .lines, .name: the part it is to read (the CGA's or the translated)"""

    def __init__(self, c, part):
        self.cga, self.cols, self.lines, self.name = part, c.cols, c.lines, c.name


def guest(binp, sym, c, pic):
    g = D.Guest(binp, sym, pic)
    if c.split:
        g.mu.mem_write(WS * 16, bytes(c.wcga))
    g.w("bz_mseg", D.PS, 2)
    g.w("bz_cseg", WS if c.split else D.PS, 2)
    g.call("bz_crshdr")
    return g


def herc_check(binp, sym, c, bx):
    """item 3: bz_hgen, bz_hxlat on the picture part -> herc_translate_course's; then the boxes on it"""
    g = guest(binp, sym, c, c.cga)
    g.call("bz_hgen")
    g.w("bz_bform", 1)                          # (the balls: translated already, as bz_bget leaves them)
    if "bz_phre" in g.sym:
        g.w("bz_phre", 0)
    g.call("bz_hxlat")
    want = BB.herc_translate_course(c.cga)
    got = bytes(g.mu.mem_read(D.PS * 16, len(want)))
    nb, blkoff = struct.unpack_from("<HxxH", c.cga, 8)
    bad = [] if got == want else ["first differs at %d (the blocks %d - %d)" % (
        next(j for j in range(len(want)) if got[j] != want[j]), blkoff, blkoff + 16 * nb)]
    g2 = guest(binp, sym, c, want)
    ok, what = W.fill_check(g2, Course(c, want), bx)
    return [(not bad, "TBLK: bz_hgen and bz_hxlat on its picture part -> herc_translate_course's bytes, its %d "
                      "blocks (%d past 1,023)%s" % (nb, nb - BB.BLK_ROWP, "" if not bad else " -- " + bad[0])),
            (ok, "the HERCULES " + what)]


def vga_model(part):
    """BZV_CONV's blocks: each word w -> tl[w & 255] | tr[w >> 8] (bzvga.asm's BZV_NIBS)"""
    def nibs(b):
        lo = hi = 0
        for k in range(4):
            px = (b >> (6 - 2 * k)) & 3
            lo |= (px & 1) << (3 - k)
            hi |= ((px >> 1) & 1) << (3 - k)
        return lo, hi
    tl = [(lambda l_, h_: (l_ << 4) | ((h_ << 4) << 8))(*nibs(b)) for b in range(256)]
    tr = [(lambda l_, h_: l_ | (h_ << 8))(*nibs(b)) for b in range(256)]
    p = bytearray(part)
    nb, blkoff = struct.unpack_from("<HxxH", p, 8)
    for o in range(blkoff, blkoff + 16 * nb, 2):
        struct.pack_into("<H", p, o, tl[p[o]] | tr[p[o + 1]])
    return bytes(p)


def vga_check(td, c, art):
    """item 4: the build's package and VGA part (linked to each other); BZV_CONV on TBLK's picture part"""
    binp = os.path.join(td, "ship.bin")
    R.assemble(os.path.join(ROOT, "apps", "bonanza"), art, binp)
    sym = R.symbols(None, art)
    lst, vbin = os.path.join(td, "bzvga.lst"), os.path.join(td, "bzvga.bin")
    subprocess.run(R.NASM + ["-f", "bin", "-w+error", "-I", "apps/", "-I", "apps/bonanza/", "-I", art + "/",
                             "-l", lst, "-o", vbin, "apps/bonanza/bzvga.asm"], cwd=ROOT, check=True)
    off, seen = None, False
    for ln in open(lst):                        # (the listing: the offset of bzv_conv's first instruction)
        f = ln.split()
        if not seen and len(f) >= 2 and f[-1] == "bzv_conv:":
            seen = True
        elif seen and len(f) >= 3 and len(f[1]) == 8:
            off = int(f[1], 16)
            break
    g = D.Guest(binp, sym, c.cga)
    if c.split:
        g.mu.mem_write(WS * 16, bytes(c.wcga))
    g.mu.mem_write(VS * 16, open(vbin, "rb").read())
    g.w("bz_mseg", D.PS, 2)
    g.w("bz_cseg", WS if c.split else D.PS, 2)
    g.w("bz_vbseg", ES0, 2)
    for n in ("bz_phre", "bz_vcp"):
        if n in g.sym:
            g.w(n, 0)
    X = g.X
    for reg, v in ((X.UC_X86_REG_CS, VS), (X.UC_X86_REG_DS, D.CS), (X.UC_X86_REG_ES, D.CS),
                   (X.UC_X86_REG_SS, D.SS)):
        g.mu.reg_write(reg, v)
    g.mu.mem_write(D.SS * 16 + 0xFFEC, struct.pack("<HH", D.STUB, D.CS))    # a far return to the stub
    g.mu.reg_write(X.UC_X86_REG_SP, 0xFFEC)
    g.mu.reg_write(X.UC_X86_REG_EFLAGS, 2)
    g.mu.emu_start(VS * 16 + off, D.CS * 16 + D.STUB, count=4000000)
    want = vga_model(c.cga)
    got = bytes(g.mu.mem_read(D.PS * 16, len(want)))
    nb = struct.unpack_from("<H", c.cga, 8)[0]
    bad = None if got == want else next(j for j in range(len(want)) if got[j] != want[j])
    return bad is None, ("TBLK: BZV_CONV (the VGA part at +%04Xh) on its picture part -> every one of its "
                                  "%d blocks (%d past 1,023) as planar pairs, the rest unmoved%s"
                                  % (off, nb, nb - BB.BLK_ROWP, "" if bad is None else
                                     " -- first differs at %d" % bad))


def check(art=None, red=None, verbose=True):
    rnd = random.Random(1386)
    c = BB.tblk_course()
    res = []
    with tempfile.TemporaryDirectory() as td:
        art0 = os.path.abspath(art or R.at("build/bonanza-art"))
        a9, at0 = forms_art(td, art0), R.at
        R.at = lambda q: a9 if q == "build/bonanza-art" else at0(q)
        try:
            binp, sym = D.build(td, REDS[red] if red else ())
        finally:
            R.at = at0
        if "bz_cxnib" not in sym:
            res.append((False, "the package assembled with BZ_FORMS bit 9 has no bz_cxnib"))
        res.append(expand_check(binp, sym, c))
        bx = boxes(c, rnd)
        ok, what = W.fill_check(guest(binp, sym, c, c.cga), Course(c, c.cga), bx)
        res.append((ok, "the CGA %s, over the %d block rows naming a block past 1,023" % (what, len(far_rows(c)))))
        res += herc_check(binp, sym, c, bx)
        if not red:
            res.append(vga_check(td, c, art0))
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
        good = not res[0][0]
        print("bonanza_blocks --red %s: %s" % (a.red, "caught (red, as it must be)" if good else "NOT CAUGHT"))
        return 0 if good else 1
    print("bonanza_blocks: %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
