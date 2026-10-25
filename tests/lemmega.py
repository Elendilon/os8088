#!/usr/bin/env python3
"""lemmega - LEMMINGS PLAYED under kern_mega's protected mode
(docs/plans/KERN-MEGA-MEMORY-PLAN.md MC7, SPEC.md 116.6).

    make mega && make lemmingsdisk && python3 tests/lemmega.py [--keep]

Under kern_mega every claim LEMMINGS holds is an LDT selector, and the
package used to make segments by adding paragraphs to them: the style bank's
pieces at bank + off/16 (96 KB, past one selector's reach), the bank's second
part read at bank + 4032, the special picture's pieces at bank + n x 600, and
the T claim's four 32,000-byte planes at T + k x 2000 (125 KB). It opens -
tests/megasweep.py proves that much - and then faults or draws garbage the
moment a level loads. MC7 gave it fixed windows made once
(os88_seg_sub): three over the bank, four over T.

Boots kern_mega under Bochs at 16MB, LEMMINGS and the 1.44MB disk's band
files in C:\\RUN, starts it through MEGARUN, and:

  1. launches Fun 1 (Dirt, VGA mode 0Dh): the preview, then PLAY - the
     game's own iteration counter `_lem_iter` must MOVE, the level's T planes
     and bank windows must be DISTINCT selectors, and the T planes' bases
     must be T's + 32,000 x k;
  2. nukes it (F12 twice): every lemming explodes and takes terrain with it,
     which is the T-plane SYNC path (lemsprite.inc) - the iteration counter
     must keep moving through it;
  3. leaves and launches Fun 22, a SPECIAL level: its 76,800-byte picture is
     composed out of the bank through the windows, and Fire's bank (96,256
     bytes, the largest) after it - the counter must move again;
  4. no `kern_mega CLOSED` (a package's #GP, completed by closing it) or
     `kern_mega FAULT` line anywhere.

A screenshot of each stage lands in the boot's directory (--keep keeps it).

Broken on purpose (docs/WRITING-TESTS.md 1), both seen when the row was
written: lemload.c's ovl_far put back to `base + (hi << 12) + (lo >> 4)`
closes LEMMINGS at the launch (`kern_mega CLOSED LEMMINGS 0D`), and T's planes
made as T + 2000 x k in lem_wins in place of os88_seg_sub closes it there too,
at the first T-plane clear - 4 and the launch fail either way.
"""
import glob
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, "tools"), HERE]
os.environ["OS88_BUILD"] = os.path.join(ROOT, "build", "megak")
import os88bochs  # noqa: E402
from os88fixture import need  # noqa: E402
import lemplaymarty  # noqa: E402

FAILS = []


def want(cond, what):
    print("   %s  %s" % ("ok  " if cond else "FAIL", what), flush=True)
    if not cond:
        FAILS.append(what)


def main():
    keep = "--keep" in sys.argv
    pkg = os.path.join(ROOT, "build", "lemmings.o88")
    for p in ("build/mega.img", "build/megak/kernel.map",
              "build/megarun.o88", "build/lemmings.o88",
              "build/lemmings.img"):
        need(p)                     # (the image's recipe writes the bands)
    sym = lemplaymarty.lemmap()
    put = ["RUN:" + f for f in
           sorted(glob.glob(os.path.join(ROOT, "build", "lemband", "1440",
                                         "*.LEM")))]
    out = tempfile.mkdtemp(prefix="lemmega-")
    disp = os.environ.get("OS88_BOCHS_DISPLAY") or os88bochs.take_display()
    box = os88bochs.Box(out, [pkg],
                        put=put, megs=16, display=disp)
    t0 = time.time()
    try:
        box.up()
        box.megarun()
        box.until(lambda: box.pkg_base("LEMMINGS"), "LEMMINGS started", 120)
        print("lemmega: LEMMINGS up after %.0fs" % (time.time() - t0),
              flush=True)

        def rd(name, n=2):
            return int.from_bytes(box.pkg_read("LEMMINGS", sym[name], n),
                                  "little")

        def wr(name, v):
            a = box.pkg_base("LEMMINGS") + sym[name]
            box.dbg(["setpmem 0x%x 1 0x%x" % (a, v & 0xFF),
                     "setpmem 0x%x 1 0x%x" % (a + 1, v >> 8)])

        box.until(lambda: rd("_lem_screen") == 0 and rd("_lem_win") != 0,
                  "the launcher's list", 120)
        box.ui_done("the launcher's paint", secs=120)
        box.shot(os.path.join(out, "0-launcher.png"))

        def play(sel, what):
            """The launch, the preview (its picture drawn out of T and the
            mask, lemfont.inc), then PLAY: Return until the game's own
            iteration counter moves. The preview sets nothing a script can
            wait on, so the key is offered every 10 s, five times."""
            def moving():
                a = rd("_lem_iter")
                time.sleep(1)
                return rd("_lem_iter") != a

            wr("_lem_sel", sel)
            box.key("Return")                   # the launch: the preview
            box.until(box.in_fsx, what + ": the bracket", 120)
            for n in range(5):
                end = time.time() + 10
                while time.time() < end and not moving():
                    if box.fault():
                        raise RuntimeError(box.fault())
                if moving():
                    break
                if n == 0:
                    box.shot(os.path.join(out, what + "-preview.png"))
                box.key("Return")               # PLAY
            if not moving():
                raise RuntimeError(what + ": the level never ran")
            return rd("_lem_iter")

        # --- 1. Fun 1 ----------------------------------------------------
        play(0, "fun1")
        time.sleep(20)
        it1 = rd("_lem_iter")
        box.shot(os.path.join(out, "fun1-play.png"))
        raw = box.pkg_read("LEMMINGS", sym["_lem_tpl"], 8)
        tpl = [int.from_bytes(raw[i:i + 2], "little") for i in (0, 2, 4, 6)]
        raw = box.pkg_read("LEMMINGS", sym["_lem_bwin"], 6)
        bwin = [int.from_bytes(raw[i:i + 2], "little") for i in (0, 2, 4)]
        bases = [box.sel_base(s) for s in tpl]
        bb = [box.sel_base(s) for s in bwin]
        print("lemmega: T planes %s based %s; bank windows %s based %s"
              % (["%04X" % s for s in tpl], ["%06X" % b for b in bases],
                 ["%04X" % s for s in bwin], ["%06X" % b for b in bb]))
        want(len(set(tpl)) == 4 and len(set(bwin)) == 3 and
             all(s & 4 for s in tpl + bwin),
             "1. the four T planes and the three bank windows are distinct "
             "LDT selectors")
        want(bases == [bases[0] + 32000 * k for k in range(4)] and
             bb == [bb[0] + 32768 * k for k in range(3)],
             "1. T's planes 32,000 bytes apart, the bank's windows 32 KB")
        want(it1 > 0, "1. Fun 1 plays: _lem_iter %d after 20s" % it1)

        # --- 2. the nuke ----------------------------------------------------
        box.key("F12", "F12", delay=100)
        time.sleep(25)
        it2 = rd("_lem_iter")
        box.shot(os.path.join(out, "fun1-nuked.png"))
        want(it2 > it1, "2. the nuke's explosions (the T sync path): "
             "_lem_iter %d -> %d" % (it1, it2))

        # --- 3. Fun 22, a special level ---------------------------------
        box.key("Escape")
        box.until(lambda: not box.in_fsx() or rd("_lem_screen") != 0,
                  "out of the level", 120)
        time.sleep(3)
        for _ in range(3):              # the postview, then the list
            if not box.in_fsx():
                break
            box.key("Escape")
            time.sleep(3)
        box.until(lambda: not box.in_fsx(), "back on the desktop", 120)
        box.ui_done("the launcher again", secs=120)
        play(21, "fun22")
        time.sleep(20)
        it3 = rd("_lem_iter")
        box.shot(os.path.join(out, "fun22-play.png"))
        want(it3 > 0, "3. Fun 22 (the special picture) plays: _lem_iter %d"
             % it3)
    except Exception as e:      # noqa: BLE001 - the machine stopped
        want(False, "the run stopped: %s" % e)
    finally:
        bad = [l for l in box.lines() if "kern_mega FAULT" in l or
               "kern_mega CLOSED" in l]
        want(not bad, "4. no kern_mega FAULT or CLOSED%s"
             % "".join(" | " + l for l in bad[:3]))
        box.stop()
        print("lemmega: %.0fs under Bochs" % (time.time() - t0))
        if keep or FAILS:
            print("lemmega: the boot is in " + out)
        else:
            shutil.rmtree(out, ignore_errors=True)
    for f in FAILS:
        print("FAIL lemmega: " + f)
    print("lemmega: %s" % ("FAILED" if FAILS else "PASS"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
