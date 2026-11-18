#!/usr/bin/env python3
"""tests/vgaprobe.py - VGAPROBE driven on an emulator: when the card takes the
start address and the pel panning, whether its CRTC wraps at 64KB in mode
0Dh, the frame's timing, and what BONANZA's VGA writers cost
(docs/plans/BOUNCE-BONANZA-VGA.md V0; the probe is tests/vgaprobe/).

The probe flips between two pairs that SHOW THE SAME IMAGE - (page A, pan 4)
and (page B, pan 0) - once a frame, at a PHASE after vsync's rise. Taken
together the picture stands still; a frame apart it shimmers; a panning
taken line by line tears below the beam. MartyPC's `pace` compares each
completed frame with the last (the status band below the split ignored):

    still    no pixel changed over the frames sampled
    shimmer  pixels changed, from the top of the picture
    tear     pixels changed, only below a line (the bbox's top is lower)

Two ORDERS (the probe's O key):
    together  start and panning written at the phase, back to back (the
              field probe's original sweep, REALDMG-PLAN's scroll round)
    split     the start alone at the phase, the panning at the next rise:
              BONANZA's VGA arm (that plan's 2.4)

A frame is classified by WHERE the first vertical line sits on every row
above the status split: pixel 6 is the pair matched, pixel 2 a start and a
panning from different pairs. A pair taken a frame apart does NOT shimmer -
(A, pan 0) and (B, pan 4) draw one picture, 4 pixels out - so the verdicts
are still (matched), wrong (mismatched alike every frame), tear (matched
above a row, not below) and shimmer (the frames differ).

THE MODELS (V0's finding, docs/plans/BOUNCE-BONANZA-VGA.md 2.4): MartyPC and
86Box's OTI-067 take the START at the vsync rise (the pair written together
just after it is a frame apart), the real PVGA1A by blanking (RealDMG's field
probe); the PANNING is LIVE on MartyPC and the PVGA1A and taken at the
frame's top on 86Box. So the split order holds from the rise to the display's
end less a margin on all of them; the last lines before the rise are where
every instrument misbehaves (MartyPC at the display's last line, 86Box at
scattered lines after it, the real chip from blanking).

THE ASSERTIONS:
  1. the split order is STILL at every phase from the first displayed lines
     to 12 short of the display's end;
  2. sensitivity: SOME phase in some order is not still (on every model the
     pair written together just after the rise is a frame apart; on a live
     panning, together in the display tears);
  3. the CRTC wraps at 64KB (W: stripes at the top, checks below the text);
  4. the five costs are measured (non-zero, net of the measurement's own
     cost, N) and the frame is a VGA's.
`--sweep` prints the whole table, both orders, for the record. The red arms
assemble a broken copy that must fail assertion 1: `--red swap` writes the
split's halves the wrong way round, the panning at the phase and the start
at the next rise (red on every model); `--red split` writes the panning WITH
the start (red where the panning is live - MartyPC - and green on 86Box's
frame-top model, which takes the pair together). No emulator can redden the
band between the display's end and the rise that BZ_VSMARG keeps the arm
out of: MartyPC and 86Box take the start at the vsync rise, and only the
real PVGA1A takes it at blanking (the field probe).

On 86Box: OS88_EMU=86box OS88_86BOX_VM=xt-vga | xt-v20-vga | at286-port (the
OTI-067: 86Box's PVGA1A neither pans nor wraps at this pin, docs/86BOX.md).

    python3 tests/vgaprobe.py [--sweep] [--red swap|split] [--machine M]
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88marty as M          # noqa: E402
import os88sym                 # noqa: E402
import os88ui                  # noqa: E402

LINE = 38                      # PIT counts a 31.78 us scanline (VP_LINE)
ROWS = 360                     # rendered rows checked: above the status split
FRAMES = 4                     # consecutive frames compared at each phase


def build(red=None):
    """-> (the probe's floppy, {label: offset}) from a private tree"""
    tmp = tempfile.mkdtemp(prefix="vgaprobe-")
    src = os.path.join(ROOT, "tests", "vgaprobe", "vgaprobe.asm")
    if red == "split":
        # the panning written WITH the start in the split order: the rule
        # the arm exists to keep, broken. Red where the panning is LIVE
        # (MartyPC, the real PVGA1A): it tears below the beam. A frame-top
        # model (86Box) takes the pair together, so it stays green there
        s = open(src).read()
        a = ("    call vp_pairsel                 ; split: the start alone, now\n"
             "    mov [vp_ppan], al\n"
             "    mov byte [vp_pend], 1\n"
             "    call vp_setstart\n")
        assert s.count(a) == 1, "the red arm's anchor moved"
        s = s.replace(a, "    call vp_pair\n")
    elif red == "swap":
        # the split order's two halves SWAPPED: the panning written at the
        # phase, the start owed to the next rise. Red on every model: the
        # start written after the rise misses that vsync (MartyPC, 86Box) or
        # that blanking (the PVGA1A) while its panning is already taken -
        # at once on a live panning, at the frame's top on 86Box
        s = open(src).read()
        a = ("    call vp_pairsel                 ; split: the start alone, now\n"
             "    mov [vp_ppan], al\n"
             "    mov byte [vp_pend], 1\n"
             "    call vp_setstart\n")
        assert s.count(a) == 1, "the red arm's anchor moved"
        s = s.replace(a, "    call vp_pairsel\n"
                         "    mov [vp_cmin], bx\n"
                         "    mov byte [vp_pend], 1\n"
                         "    call vp_setpan\n")
        b = ("    mov al, [vp_ppan]\n"
             "    call vp_setpan\n")
        assert s.count(b) == 1, "the red arm's anchor moved"
        s = s.replace(b, "    mov bx, [vp_cmin]\n"
                         "    call vp_setstart\n")
    if red:
        src = os.path.join(tmp, "vgaprobe.asm")
        open(src, "w").write(s)
    b = os.path.join(tmp, "vgaprobe.bin")
    mp = os.path.join(tmp, "vgaprobe.map")
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I",
                    os.path.join(ROOT, "apps") + "/", "--before",
                    "[map all %s]" % mp, "-o", b, src], check=True)
    o = os.path.join(tmp, "VGAPROBE.O88")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "os88pkg.py"),
                    b, "-o", o], check=True, stdout=subprocess.DEVNULL)
    img = os.path.join(tmp, "vgaprobe360.img")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "os88disk.py"),
                    "-o", img, "--size", "360", o], check=True,
                   stdout=subprocess.DEVNULL)
    off, _, equ = os88sym._parse_map(mp)
    sym = dict(equ)
    sym.update(off)
    return tmp, img, sym


class Probe(object):
    def __init__(self, ui, win, sym):
        self.ui, self.m, self.w, self.s = ui, ui.m, win, sym

    def rd(self, name, n=2):
        return M.pkg_read(self.m, self.w, self.s[name], n)

    def word(self, name):
        return struct.unpack("<H", self.rd(name))[0]

    def byte(self, name):
        return self.rd(name, 1)[0]

    def poke(self, name, data):
        self.m.pause()
        M.pkg_write(self.m, self.w, self.s[name], data)

    def key(self, k, frames=3):
        self.m.key(k)
        self.m.advance(frames=max(2, frames))    # let the bracket read it

    def picture(self):
        """this completed frame: per rendered row above the status band, where
        the first vertical line is - 'ok' (pixel 6, the pair matched),
        'bad' (pixel 2: a start and a panning from different pairs) or None
        (a rule or blank row)"""
        W, H, d = self.m.fbuf()
        out = []
        for y in range(0, ROWS):
            xs = [x for x in range(16) if d[(y * W + x) * 3]]
            x = xs[0] if xs else -1
            out.append({12: "ok", 4: "bad"}.get(x))
        return out

    def classify(self, phase):
        """-> (verdict, rendered row or None). still: every frame matched;
        wrong: every frame mismatched the same way (a pair taken a frame
        apart shows the picture displaced, not a shimmer); tear: matched
        above a row, mismatched below; shimmer: the frames differ"""
        self.poke("vp_phase", struct.pack("<H", phase))
        self.m.advance(frames=3)                 # the new phase settles
        frames = []
        for _ in range(FRAMES):
            self.m.advance(frames=1)
            frames.append(self.picture())
        if any(f != frames[0] for f in frames):
            return "shimmer", None
        rows = [r for r in frames[0] if r]
        if all(r == "ok" for r in rows):
            return "still", None
        if all(r == "bad" for r in rows):
            return "wrong", None
        first = frames[0].index("bad")
        return "tear", first


def run(args):
    tmp, img, sym = build(args.red)
    try:
        with os88ui.boot(os.path.join(ROOT, "build", "os8088-360.img"),
                         apps=img, machine=args.machine, quick=True) as ui:
            w = ui.path("B:/VGAPROBE.O88")
            m = ui.m
            m.key("Enter")
            p = Probe(ui, w, sym)
            M.until(m, lambda _: p.word("vp_frame") != 0,
                    "the probe's first timing", guest=20)
            # the entry's timing is taken as the mode settles; T again, twice
            # (the probe's T misreads now and then by ~20 scanlines on
            #   MartyPC: the median of three, each after the mode settled)
            reads = []
            for _ in range(3):
                m.advance(frames=4)
                p.key("KeyT", frames=6)
                reads.append(tuple(p.word(n) for n in
                             ("vp_frame", "vp_vslen", "vp_vsact", "vp_lines")))
            fr, vs, va, ln = sorted(reads)[1]
            us = lambda c: c * 838 // 1000
            print("frame %d us (%.2f Hz), vsync %d us, vsync rise to the first "
                  "displayed line %d us, %d lines counted" %
                  (us(fr), 1e6 / us(fr), us(vs), us(va), ln))
            ok = True
            if not 12000 < us(fr) < 17500:
                print("FAIL: a mode 0Dh frame is 14.3 ms; this is %d us" % us(fr))
                ok = False
            # --- costs (C) ---
            p.key("KeyC", frames=2)
            for _ in range(60):                  # ~110 ms of runs: wait on
                if struct.unpack("<6H", p.rd("vp_cres", 12))[5]:   # the last
                    break
                m.advance(frames=2)
            raw = struct.unpack("<6H", p.rd("vp_cres", 12))
            n = raw[5]                       # the measurement's own cost
            costs = [max(0, c - n) for c in raw[:5]]
            print("costs, CPU clocks net of the measurement's own %d: 320 "
                  "bytes stored %d (%.1f a byte), 320 moved %d (%.1f), a "
                  "41-cell row from planar blocks %d, the same row converted "
                  "from 2bpp %d, a 4-word box line %d (a call a word)" %
                  (n, costs[0], costs[0] / 320.0, costs[1], costs[1] / 320.0,
                   costs[2], costs[3], costs[4]))
            if not all(costs) or not n:
                print("FAIL: a cost read zero")
                ok = False
            p.key("KeyC")
            # --- the sweep ---
            orders = ("together", "split")
            table = {}
            for order in orders:
                want = 1 if order == "split" else 0
                if p.byte("vp_order") != want:
                    p.key("KeyO")
                assert p.byte("vp_order") == want
                step = 10 * LINE if args.sweep else 50 * LINE
                phases = list(range(LINE, fr - 13 * LINE, step))
                phases += [va + (400 - 13) * LINE]   # the window's last line
                phases += [fr - k * LINE for k in (12, 9, 7, 5, 3, 2)]
                for ph in phases:
                    table[(order, ph)] = p.classify(ph)
                    c, top = table[(order, ph)]
                    print("  %-8s phase %6d us (line %3d from the rise): %s%s"
                          % (order, us(ph), ph // LINE, c,
                             "" if top is None else " from rendered row %d" % top))
            # 1: the arm's window - the start written anywhere up to 12 lines
            #    short of the display's end (BZ_VSMARG), the panning at the
            #    next rise - is still at every phase from the first displayed
            #    lines on. Every card in reach takes the start by the
            #    display's end (the module note)
            win0, win1 = va + 4 * LINE, va + (400 - 12) * LINE
            bad = [ph for (o, ph), (c, _) in table.items()
                   if o == "split" and win0 <= ph < win1 and c != "still"]
            if bad:
                print("FAIL: the split order is not still at %d phase(s) in "
                      "the display: %s" % (len(bad), [us(b) for b in sorted(bad)]))
                ok = False
            # 2: SENSITIVITY - some phase, in some order, is NOT still: on
            #    every model the pair written together just after the rise
            #    (the start missed, the panning taken), and on a live panning
            #    the pair together in the display tears. An instrument that
            #    calls everything still fails here
            notstill = sorted(set(c for c, _ in table.values()) - {"still"})
            if not notstill:
                print("FAIL: every phase in both orders read still - the "
                      "instrument sees nothing")
                ok = False
            live = any(c == "tear" for (o, ph), (c, _) in table.items()
                       if o == "together")
            print("model: the panning is %s%s"
                  % ("LIVE (a tear below the beam)" if live else
                     "taken at a frame boundary",
                     "" if bad else "; the split order's window holds"))
            # --- the wrap (W) ---
            p.key("KeyW", frames=4)
            stripes = checks = False
            for _ in range(3):              # (a frame caught mid-draw on
                m.advance(frames=1)         #   86Box: the best of three)
                W, H, d = m.fbuf()
                def row(y):
                    return [d[(y * W + x) * 3] > 0
                            for x in range(0, W, 2)][:320]
                top_rows = [row(2 * y) for y in (4, 30, 60)]
                st = all(len(set(r)) == 1 for r in top_rows)
                chk = row(2 * 150)
                ck = len(set(chk)) == 2 and chk[0:4] != chk[4:8]
                stripes, checks = stripes or st, checks or ck
                if st and ck:
                    break
            print("wrap: stripes at the top %s, checks below the text %s"
                  % (stripes, checks))
            if not (stripes and checks):
                print("FAIL: no 64KB wrap seen")
                ok = False
            p.key("KeyW")
            m.key("Escape")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true",
                    help="every phase, both orders, for the record")
    ap.add_argument("--red", choices=["split", "swap"],
                    help="a deliberately broken copy, which must FAIL")
    ap.add_argument("--machine", default="os8088_xt_vga")
    a = ap.parse_args()
    ok = run(a)
    if a.red:
        print("red arm %s: %s" % (a.red, "went red (good)" if not ok
                                  else "STAYED GREEN - the row sees nothing"))
        return 0 if not ok else 1
    print("vgaprobe: %s" % ("ok" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
