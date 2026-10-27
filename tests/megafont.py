#!/usr/bin/env python3
"""kern_mega: no kernel claim pins CONVENTIONAL memory - the glyph table's
copy and DESK.DRV live above 1MB (docs/plans/KERN-MEGA-PLAN.md 14.120).

    python3 tests/megafont.py            the row
    python3 tests/megafont.py --keep     ...and leave the boots' directory
    python3 tests/megafont.py --nohib    the boot leg alone (a minute)

THE REPORT: the owner's Victory 286 (an 8-bit Paradise PVGA1A option ROM)
showed the Task Manager's map with a claim at the top of 640K, and the font
and DESK.DRV listed under Kernel. On that machine FONT_PICK times the ROM
table more than a quarter slower than RAM, so font_init COPIES it into a 1KB
MEM_K_FONT claim - top-down and pinned, in real mode, before mega_enter - and
nothing ever moved it: a kilobyte of the conventional arena (the DOS trip's,
and a bridged huge claim's low piece) for a table whose every use is a
segment-register load. DESK.DRV was ALREADY above 1MB (mod_hi, 14.47); the
row holds it there.

This boots `make FONTSLOW=1 mega` (a private tree - the knob forces the copy
on any machine, the Victory's case) under Bochs at 4MB off C:'s boot
partition with the system floppy's root files beside it (HIBER.DRV), opens
C:\\RUN\\DESKCLOK.O88 - a desk widget, so the loader takes DESK.DRV - and
asserts:

  1. [font_seg] is a POOL selector (its base at or above 1MB) holding a
     glyph table - SPACE blank, `A` not;
  2. mem_tab holds NO pinned kernel record (owner FFxxh, MC_RLOC 0): no
     MEM_K_FONT, no MEM_K_MOD, nothing that walls the conventional run;
  3. DESK.DRV loaded, and its MODR_SEG a pool selector;
  4. hibernate, power off, boot the same C: and resume: `kern_mega:
     resumed`, and [font_seg] still the pool selector with the SAME bytes -
     hbm_wake's step 4a used to read a pool selector as a ROM (s2seg reads
     FFFF above 1MB) and swap the pointer for the slow ROM's, stranding the
     block;
  5. no kern_mega FAULT or CLOSED in either boot.

THE FAILING CASE (docs/WRITING-TESTS.md 1): take mem_hicaches_f's MEM_K_FONT
call out and (1) and (2) go red - `font_seg 114C base 0009F800` and a pinned
FF10 record at 9F80, the top of conventional memory. Take hbm_wake's
MEGA_ISHI out and (4) goes red on the resume.
"""
import os
import shutil
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88bochs as ob  # noqa: E402
import os88build  # noqa: E402

MC_SIZE, MEM_MAX = 10, 32
MOD_DESK, MODR_SIZE = 7, 4          # kernel/mod.inc
FONT_BYTES = 760                    # kernel/font.inc (95 glyphs x 8)


def state(box):
    M, F, T = box.reads([("mem_tab", MC_SIZE * MEM_MAX), ("font_seg", 2),
                         ("mod_tab", MODR_SIZE * (MOD_DESK + 1))])
    recs = [struct.unpack_from("<HHHHH", M, k * MC_SIZE)
            for k in range(MEM_MAX)]
    recs = [r for r in recs if r[0]]
    fseg = struct.unpack_from("<H", F, 0)[0]
    dseg = struct.unpack_from("<H", T, MOD_DESK * MODR_SIZE)[0]
    return recs, fseg, dseg


def check(box, tag, fails, want=None):
    recs, fseg, dseg = state(box)
    for s, p, o, _, r in sorted(recs):
        print("megafont: %-8s %04X %6d B own %04X%s" %
              (tag, s, p * 16, o, "  PINNED" if not r else ""))
    base = box.sel_base(fseg) if fseg & 4 else fseg * 16
    print("megafont: %-8s font_seg %04X base %08X" % (tag, fseg, base))
    pinned = [r for r in recs if r[2] >= 0xFF00 and not r[4]]
    if pinned:
        fails.append("%s: pinned kernel claim(s) in conventional memory: %s"
                     % (tag, ["%04X own %04X" % (r[0], r[2])
                              for r in pinned]))
    if base < 0x100000:
        fails.append("%s: the glyph table's copy is below 1MB (font_seg "
                     "%04X, base %05X)" % (tag, fseg, base))
        return None
    g = box.read(base, FONT_BYTES)
    if any(g[0:8]) or not any(g[33 * 8:34 * 8]):
        fails.append("%s: [font_seg] does not hold a glyph table" % tag)
    if want is not None and g != want:
        fails.append("%s: the table's bytes changed across the hibernate"
                     % tag)
    return g, dseg


def main():
    keep = "--keep" in sys.argv
    t = os88build.tree("FONTSLOW=1", targets=(
        "mega.img", "megarun.o88", "mbr.bin")).apply()
    out = os.path.join(t.dir, "megafont")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    t0 = time.time()
    fails = []
    glyphs = None
    box = ob.Box(out, [os.path.join(ROOT, "build", "deskclok.o88")],
                 build=t.dir, bootc=True, noa=True, csys=True, megs=4)
    try:
        if not box.wait_for("kern_mega: protected mode", 300):
            print("FAIL: kern_mega never reached protected mode")
            return 1
        box.up()
        r = check(box, "desktop", fails)
        box.capture()
        box.dbl(591, 160, "C:'s Disk window")
        box.dbl(150, 123, "RUN's listing")
        box.dbl(160, 155, "DESKCLOK")
        if not box.wait_for("above 1MB: DESK.DRV", 60):
            fails.append("DESK.DRV was never loaded above 1MB")
        box.ui_done("the clock widget")
        r = check(box, "widget", fails)
        if r:
            glyphs, dseg = r
            if not dseg or not dseg & 4 or box.sel_base(dseg) < 0x100000:
                fails.append("DESK.DRV's MODR_SEG %04X is not a pool "
                             "selector" % dseg)
        box.shot(os.path.join(out, "widget.png"))
        if "--nohib" not in sys.argv:
            box.goto(10, 5)             # System menu > Hibernate...
            box.xd("mousedown", 1)
            for _ in range(5):          # 83 guest pixels, two X pixels each
                box.xd("mousemove_relative", "--", 0, 30)
                time.sleep(0.04)
            box.xd("mousemove_relative", "--", 0, 16)
            time.sleep(0.5)
            box.xd("mouseup", 1)
            box.ui_done("the Hibernate dialog")
            box.goto(225, 225)          # Hibernate
            box.xd("click", 1)

            def off():
                s = box.read(0xB8000, 160 * 6)[0::2].decode("latin-1")
                return "hibernated" in s
            try:
                box.until(off, "the hibernate's `os8088 has hibernated`",
                          400, poll=1.0)
            except RuntimeError as e:
                fails.append(str(e))
        lines = box.lines()
    finally:
        box.stop()
    for ln in lines:
        if ln.startswith(("kern_mega FAULT", "kern_mega CLOSED")):
            fails.append("boot: " + ln)
    if "--nohib" not in sys.argv and not fails:
        box = ob.Box(out, [], build=t.dir, cmode="keep", bootc=True,
                     noa=True, megs=4)
        try:
            if not box.wait_for("kern_mega: protected mode", 300):
                fails.append("the second boot never reached protected mode")
            else:
                box.up()                # the desktop and its Resume card
                box.capture()
                box.goto(225, 225)      # Resume
                box.xd("click", 1)
                if not box.wait_for("kern_mega: resumed", 120):
                    fails.append("no `kern_mega: resumed`")
                box.ui_done("the resumed desktop")
                box.shot(os.path.join(out, "resumed.png"))
                check(box, "resumed", fails, glyphs)
            lines = box.lines()
        finally:
            box.stop()
        for ln in lines:
            if ln.startswith(("kern_mega FAULT", "kern_mega CLOSED")):
                fails.append("resume: " + ln)
    print("megafont: %.0fs under Bochs" % (time.time() - t0))
    for f in fails:
        print("FAIL: " + f)
    if keep or fails:
        print("megafont: the boots are in " + out)
    else:
        shutil.rmtree(out, ignore_errors=True)
    if not fails:
        print("megafont: ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
