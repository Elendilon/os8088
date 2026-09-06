#!/usr/bin/env python3
"""WORD'S SCROLL: the bar survives it, the pixels are right, and it BLITS.

    make worddisk && python3 tests/wdscroll.py

Three field reports, all about the scroll bar (SPEC.md 27.7.2, 68.6):

  A  the down arrow blanks part of the bar. wd_vshift cut its blit span from
     [wd_rgt], the last TEXT column, rounded UP to a byte column - and the
     bar's frame begins at [wd_rgt]+1, so on the shipped window it took SIX of
     the bar's fourteen columns. wd_scrollpaint then filled that strip white
     over the whole band height and wd_sbar redrew all sixteen calls of the
     bar at the end: Part 1's double-draw flash, once per click.

  B  a track click redraws the whole window, bar and grow box included, even
     though a REFUSED blit has drawn nothing and .scrolled is only reached
     when wd_sigsame agreed - so the bar on the glass was still right.

  C  a page is [wd_vfit] rows, which with formats is band/24 - 2 of the
     shipped window's 6. Two thirds is retained and could blit, but
     wd_scrollpaint lowered [wd_rowsn] to [wd_bd0] to bound its seed and
     nothing raised it once the walk had lettered the rest, so the FIRST page
     click blitted and every one after it refused on d > rowsn.

LEG B IS THE ONE WITH TEETH. Speed is worthless if the pixels are wrong, and
a stale banked y draws a row at the wrong height - which no timing assertion
would see. It pages DOWN through the document with the blit and then back UP,
which a formatted document always full-repaints (68.6's documented degrade),
and requires the screen to come back IDENTICAL. So the fast path is checked
against the slow one on the same document, in one run.
"""
import os, sys, time, subprocess, tempfile, argparse, functools
print = functools.partial(print, flush=True)
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, "tools"); sys.path.insert(0, "tests")
import os88marty as M
from os88mouse import Mouse
import dispcp

u16 = lambda b, i=0: b[i] | (b[i+1] << 8)
s16 = lambda v: v - 65536 if v >= 32768 else v
STEP_CYCLES = 25_000
SB_CELL = 10                    # apps/os88ui.inc: OS88UI_SBCELL, the arrow
                                # cell's height. The reference box is THAT and
                                # not the whole bar head: the rule sits at
                                # y1+10 and the track below it is where the
                                # THUMB travels, so a box any taller calls a
                                # legitimate thumb move a defect.
FAIL = []


def check(name, ok, detail=""):
    print("   %-50s %s%s" % (name, "ok" if ok else "FAIL", "" if ok else "  " + detail))
    if not ok:
        FAIL.append(name)


def pkg_syms(src="apps/word/word.asm", incs=("apps/", "apps/word/")):
    with tempfile.TemporaryDirectory() as d:
        cp, mp = os.path.join(d,"p.asm"), os.path.join(d,"p.map")
        open(cp,"w").write(open(src).read()+"\n[map symbols %s]\n"%mp)
        subprocess.run(["nasm","-f","bin","-w+error"]+sum([["-I",i] for i in incs],[])
                       +["-o",os.path.join(d,"p.bin"),cp],check=True)
        out={}
        for L in open(mp):
            f=L.split()
            if len(f)==3 and all(c in "0123456789ABCDEF" for c in f[0]): out[f[2]]=int(f[0],16)
        return out, open(os.path.join(d,"p.bin"),"rb").read()


def shot(m):
    w, h, rows = m.vram()
    return w, h, bytes(b for r in rows for b in r)


def band(sh, box):
    w, _, px = sh
    x0, y0, x1, y1 = box
    return bytes(px[y*w + x] for y in range(y0, y1+1) for x in range(x0, x1+1))


def vram_cell(m, x1, x2, y1, y2):
    """The RAW framebuffer bits for columns x1..x2 of rows y1..y2, MASKED.

    CGA BY NAME, and read out of guest memory rather than through fbuf(): a
    rendered frame only changes once a video frame, so sampling it every
    STEP_CYCLES re-reads the SAME picture and a leg watching for a strip that
    is blanked and redrawn inside one frame sees nothing at all. That is a
    false green, and this gate had it - it passed with the fix backed out
    until this function replaced the frame read (docs/WRITING-TESTS.md 1).

    AND IT MASKS TO THE COLUMNS ASKED FOR, which the byte-granular version
    could not. Word's bar begins at [wd_rgt]+1 = 602 on the shipped window, so
    the byte holding its first columns ALSO holds text columns 600-601 - and
    a full repaint fills those legitimately. Rounding outward therefore
    reported one byte of honest drawing as a disturbed bar, while the bug it
    is looking for blanks 602-607 inside that same byte. Bits, not bytes.

    SPEC.md 39.3's two-bank layout, the arithmetic os88marty.vram uses.
    """
    fb = m.read(0xB8000, 0x4000)
    b1, b2 = x1 >> 3, x2 >> 3
    mask = bytearray(b2 - b1 + 1)
    for x in range(x1, x2 + 1):
        mask[(x >> 3) - b1] |= 0x80 >> (x & 7)
    out = bytearray()
    for y in range(y1, y2 + 1):
        off = (y % 2) * 0x2000 + (y // 2) * 80
        row = fb[off + b1:off + b2 + 1]
        out += bytes(v & k for v, k in zip(row, mask))
    return bytes(out)


ap = argparse.ArgumentParser()
ap.add_argument("--machine", default="os8088_5150_cga_gla")
a = ap.parse_args()
syms, image = pkg_syms()
DISK = "build/wdscrollgate.img"
M.scratch_disk(DISK, "build/word.o88", "build/WORD.OVL", "build/WELCOME.DOC")
S = lambda n: m.sym(n)

with M.launch("build/os8088-360.img", apps=DISK, machine=a.machine) as m:
    M.settle(m); mo = Mouse(marty=m)
    print("== Word's scroll (SPEC.md 27.7.2) on %s ==" % a.machine)
    dispcp.open_drive(m, mo, S, M.settle, "B")
    w = dispcp.win_list(m, S)[-1]; dx, dy = dispcp.win_rect(m, S, w)[:2]
    dispcp.open_named(m, mo, S, M.settle, dx, dy, "WELCOME.DOC")
    time.sleep(2.5); M.settle(m)

    raw = m.read(S("inst_tab"), 32*12); seg = None
    for i in range(12):
        b = i*32
        if raw[b] == 1 and (raw[b+2] & 0x80):
            c = u16(raw, b+6)
            if m.read(c*16+syms["wd_mdraw"], 48) == image[syms["wd_mdraw"]:syms["wd_mdraw"]+48]:
                seg = c; break
    if seg is None:
        sys.exit("could not locate the running package (stale build/word.o88?)")
    base = seg*16; P = lambda n: base + syms[n]
    rw = lambda n: u16(m.read(P(n), 2)); rb = lambda n: m.read(P(n), 1)[0]

    # THE HEIGHT COUNT MUST BE FINISHED FIRST. [wd_drows] is a lower bound
    # while the background walk is owed (SPEC.md 27.7.3/68.6), so the TOTAL
    # keeps moving between clicks - and wd_sbcheck answers a moved total with
    # the full sixteen-call draw, correctly, because only that can resize the
    # thumb. A leg that samples the bar while the count is running is watching
    # a legitimate redraw and calling it a defect.
    for _ in range(400):
        if rb("wd_hdirty") == 0:
            break
        m.advance(cycles=2_000_000)
    check("the height count is settled (so the total stops moving)",
          rb("wd_hdirty") == 0, "wd_hdirty still set after 800M cycles")
    print("   drows=%d after the count settled" % rw("wd_drows"))

    rgt, sbr = rw("wd_rgt"), rw("wd_sbr")
    ty, bot = rw("wd_ty"), rw("wd_bot")
    sbb = rw("wd_sbb")               # the bar's own bottom, CLEAR of the grow
                                     # box the kernel draws in the corner -
                                     # bot-4 is the grow box and clicking it
                                     # scrolls nothing at all
    vrows, vfit = rw("wd_vrows"), rw("wd_vfit")
    tx, rcols = rw("wd_tx"), rw("wd_rcols")
    barbox = (rgt+1, sbr, ty, ty+SB_CELL-1)   # the bar's UP-ARROW cell:
                                              # outside the thumb's travel, and
                                              # never drawn by a scroll at all,
                                              # so anything here is furniture
                                              # being erased
    sbx = sbr - 7
    print("   vrows=%d vfit=%d  tx=%d rcols=%d rgt=%d sbr=%d  hasfmt=%d"
          % (vrows, vfit, tx, rcols, rgt, sbr, rb("wd_hasfmt")))
    check("the document is formatted (the case under test)", rb("wd_hasfmt") == 1)
    check("a page retains rows (vfit < vrows)", vfit < vrows, "vfit=%d vrows=%d" % (vfit, vrows))

    # ---- leg A: the down arrow must never disturb the bar -----------------
    def watch(tag, y, steps=48):
        m.run(); mo.to(sbx, y); m.advance(frames=60)
        ref = vram_cell(m, *barbox)
        if vram_cell(m, *barbox) != ref:
            sys.exit("wdscroll: %s is not settled between two idle reads" % tag)
        before = rw("wd_top")
        m.pause(); m.mouse(0, 0, l=True); m.step(1)
        worst = seen = 0
        for _ in range(steps):
            m.advance(cycles=STEP_CYCLES)
            d = sum(1 for p, q in zip(ref, vram_cell(m, *barbox)) if p != q)
            worst = max(worst, d); seen += 1 if d else 0
        m.mouse(0, 0); m.step(1); m.run(); time.sleep(0.6)
        after = rw("wd_top")
        print("   %-22s %d samples, %d differ, worst %d byte(s); top %d -> %d"
              % (tag, steps, seen, worst, before, after))
        return seen, worst, before, after

    seen, worst, b4, af = watch("A down arrow", sbb-7)
    check("the down arrow scrolled (the case is arranged)", af != b4, "top %d->%d" % (b4, af))
    check("A: the bar is never blanked by the blit", seen == 0,
          "%d of 48 samples altered, worst %d byte(s)" % (seen, worst))

    seen2, worst2, b42, af2 = watch("B track below thumb", (ty+sbb)//2 + (sbb-ty)//4)
    check("the track click paged DOWN (the case is arranged)", af2 > b42,
          "top %d->%d" % (b42, af2))
    check("B: a track click leaves the bar on the screen", seen2 == 0,
          "%d of 48 samples altered, worst %d byte(s)" % (seen2, worst2))

    # ---- leg D: a page UP is REFUSED, and must still keep the bar ---------
    # A formatted document gives up the upward blit-scroll (SPEC.md 68.6: the
    # entering rows' heights are unknown), so this is the path where
    # wd_scrollpaint answers CF=1 and the full repaint runs. It drew nothing,
    # and .scrolled is only reached when wd_sigsame agreed - so the bar is
    # still right and the repaint must leave it alone. This is the ONLY leg
    # that exercises [wd_sbkeep].
    for _ in range(2):               # get away from the top so UP can happen
        m.run(); mo.to(sbx, (ty+sbb)//2 + (sbb-ty)//4); time.sleep(0.25)
        m.mouse(l=True); time.sleep(0.08); m.mouse(l=False); time.sleep(1.3)
    # LEG D IS A BEHAVIOURAL ASSERTION, not a pixel one, and deliberately.
    # The refused path DOES redraw the bar's thumb - os88ui_sbmove, three
    # calls - because the view really moved, and pinning a pixel box that
    # excludes the thumb's own travel while still covering the six columns the
    # bug blanked is a box this gate got wrong twice. What the fix CLAIMS is
    # exactly this: the whole-bar draw does not run, and the fill knows it.
    b43 = rw("wd_top")
    m.bp_exec(P("wd_sbar"))
    m.run(); mo.to(sbx, ty + (sbb-ty)//4); time.sleep(0.3)
    m.mouse(l=True); time.sleep(0.08); m.mouse(l=False)
    barfull = m.wait_stop(12)
    m.bp_exec()
    if barfull: m.run()
    time.sleep(1.2)
    af3 = rw("wd_top")
    print("   D track above thumb    wd_sbar entered: %s; top %d -> %d"
          % (bool(barfull), b43, af3))
    check("the track click paged UP (the case is arranged)", af3 < b43,
          "top %d->%d" % (b43, af3))
    check("D: a REFUSED blit does not redraw the bar WHOLE", not barfull,
          "wd_sbar ran, so the sixteen-call draw is back")

    # ---- leg C: consecutive page clicks must BLIT -------------------------
    def paged(y):
        m.bp_exec(P("wd_paint"))
        m.run(); mo.to(sbx, y); time.sleep(0.3)
        m.mouse(l=True); time.sleep(0.08); m.mouse(l=False)
        hit = m.wait_stop(12)
        m.bp_exec()
        if hit: m.run()
        time.sleep(1.0)
        return bool(hit)

    ydn = (ty+sbb)//2 + (sbb-ty)//4
    fulls = [paged(ydn) for _ in range(3)]
    print("   consecutive page-downs entering wd_paint (a FULL repaint): %s" % fulls)
    check("C: a repeated page click still blits", not any(fulls),
          "%d of 3 fell back to a full repaint" % sum(fulls))

    # ---- leg B: the pixels. Page down, page back up, require identity -----
    m.run(); mo.to(4, 4); time.sleep(1.2); M.settle(m)
    top0 = rw("wd_top")
    start = shot(m)
    yup = ty + (sbb-ty)//4
    for _ in range(3):
        mo.to(sbx, ydn); time.sleep(0.25)
        m.mouse(l=True); time.sleep(0.08); m.mouse(l=False); time.sleep(1.3)
    mid = rw("wd_top")
    # ...and back to the SAME view, driven by [wd_top] rather than by counting
    # clicks: the track auto-repeats while the button is held, so a click is
    # not reliably one page and a fixed count lands somewhere else entirely.
    for _ in range(12):
        if rw("wd_top") <= top0:
            break
        mo.to(sbx, yup); time.sleep(0.25)
        m.mouse(l=True); time.sleep(0.08); m.mouse(l=False); time.sleep(1.3)
    mo.to(4, 4); time.sleep(1.2); M.settle(m)
    backtop = rw("wd_top")
    end = shot(m)
    print("   round trip: top %d -> %d -> %d" % (top0, mid, backtop))
    check("the round trip moved and came back (case arranged)",
          mid > top0 and backtop == top0, "%d -> %d -> %d" % (top0, mid, backtop))
    box = (rw("wd_cl"), ty, sbr, bot)
    d = sum(1 for p, q in zip(band(start, box), band(end, box)) if p != q)
    check("B: blit-scrolled pixels equal the repainted ones", d == 0,
          "%d differing pixels" % d)

print()
print("wdscroll: %s" % ("FAILED: " + ", ".join(FAIL) if FAIL else "ok"))
sys.exit(1 if FAIL else 0)
