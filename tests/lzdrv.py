#!/usr/bin/env python3
"""A COMPRESSED DRIVER loads, expands and answers (docs/O88-COMPRESSION-PLAN.md 12.6).

The subject is RAMDISK.DRV, on a system disk otherwise identical to the
shipped 360KB one. It is the right one because it has BOTH halves of wave 3:
a 2,416-byte bss that `drv_bss` re-makes, and a body `drv_expand` unpacks - so
one file exercises the whole path.

Three assertions, and the middle one is what a working driver alone would not
prove:

  * it ATTACHES - the row has a segment, so drv_load got through drv_check,
    drv_expand, drv_bss and the driver's own attach;
  * its image in memory is byte-for-byte the UNCOMPRESSED driver, with the
    stripped zeros back. A decoder that fumbled the last run would still
    attach, and this is what catches it;
  * it ANSWERS - the DRVCALL package's three probes, which is
    tests/drvcall.py's own assertion re-run against a driver that arrived
    compressed.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import os88drv                                         # noqa: E402
import os88marty                                       # noqa: E402
import os88mouse                                       # noqa: E402
import os88sym                                         # noqa: E402
import dispcp                                          # noqa: E402
import drvcall                                         # noqa: E402
from os88fixture import need                           # noqa: E402

S = os88sym.linear
MACHINE = {"cga": "os8088_5150_cga_gla", "herc": "os8088_5150_herc_gla"}
# The Control Panel geometry and the Ram Disk's row are tests/drvcall.py's,
# imported rather than copied: this row loads the SAME driver through the SAME
# page, and two files disagreeing about where that row is would be a test
# failure that means nothing about the kernel.
DRVR_SZ, DRVR_SEG = drvcall.DRVR_SZ, drvcall.DRVR_SEG
RD_ROW = drvcall.RD_ROW


def say(*a):
    print(*a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="cga", choices=sorted(MACHINE))
    a = ap.parse_args()
    need("build/lzdrv360.img", "build/drvcall360.img")   # `all`
                                   # builds nothing under tests/

    # THE SHIPPED DRIVER IS COMPRESSED TOO NOW (SPEC.md 20.13.5), so the
    # reference this whole row compares against has to be unwrapped: what the
    # guest holds after drv_expand is the IMAGE, and build/ramdisk.drv is a
    # FILE. Without this the row reports 4,832 differing bytes on a kernel
    # that expanded perfectly, which reads exactly like a broken decoder.
    plain = os88drv.image_unwrap(open("build/ramdisk.drv", "rb").read())
    packed = open("build/lzd/ramdisk.drv", "rb").read()
    say("lzdrv: RAMDISK.DRV %d bytes plain, %d compressed (%.1f%%), "
        "+%d bss" % (len(plain), len(packed), 100.0 * len(packed) / len(plain),
                     plain[31] * 16))

    fails = []
    with os88marty.launch("build/lzdrv360.img",
                          apps="build/drvcall360.img",
                          machine=MACHINE[a.adapter]) as m:
        os88marty.settle(m, gate=os88marty.desktop_up)
        mo = os88mouse.Mouse(marty=m)

        # 1. tick the Ram Disk on, exactly as tests/drvcall.py does - a
        #    driver is not attached at boot unless SYSTEM.CFG asks for it
        mo.menu(8, 8, 8, 40)                        # chip menu -> Control Panel
        os88marty.settle(m)
        cp = None
        for w in dispcp.win_list(m, S):
            x, y, ww, hh = dispcp.win_rect(m, S, w)
            if ww >= 280 and hh >= 100:
                cp = (w, x, y)
        if cp is None:
            sys.exit("lzdrv: no Control Panel window")
        _, cx, cy = cp
        x0, y0 = cx + 1, cy + 18
        mo.click(x0 + 40, y0 + drvcall.CP_I0Y
                 + drvcall.CP_IDRV * drvcall.CP_IROWH + 7)
        os88marty.settle(m)
        mo.click(x0 + drvcall.CP_RX + 40,
                 y0 + drvcall.CP_DBY1 + RD_ROW * drvcall.CP_DROWH
                 + drvcall.CP_DROWH // 2)
        # POLL drv_tab, do not sleep at it. A driver comes off a floppy and
        # `time.sleep(6)` is a HOST-clock wait for GUEST work - under a loaded
        # box the guest does about a third less of it per host second
        # (docs/SOAK-PARALLEL.md 1), so the fixed wait was right alone and
        # short beside anything else. The segment appearing IS the event.
        seg = 0
        for _ in range(40):
            seg = int.from_bytes(
                m.read(S("drv_tab") + RD_ROW * DRVR_SZ + DRVR_SEG, 2),
                "little")
            if seg:
                break
            time.sleep(0.5)
        os88marty.settle(m)
        mo.click(cx + 8, cy + 9)                    # close the panel (31.8)
        os88marty.settle(m)
        if not seg:
            fails.append("RAMDISK.DRV is not in drv_tab with a segment - it "
                         "did not attach")
        else:
            say("  attached at %04X" % seg)
            # 2. did it expand to the right bytes?
            #
            # THE IMAGE ONLY. The bss cannot be compared against zeros here
            # and the reason is not a limitation of the test: by the time the
            # row has a segment the driver has ATTACHED, and its bss is its
            # working memory - the first version of this row failed on 96
            # bytes at offset 6,406, every one of them the Ram Disk's own
            # state. What stands in for it is below.
            got = bytes(m.readseg(seg, 0, len(plain)))
            if got == plain:
                say("  %d bytes of image expanded EXACTLY" % len(plain))
            else:
                bad = [i for i in range(len(plain)) if got[i] != plain[i]]
                fails.append("expanded WRONG: %d of %d image bytes differ, "
                             "first at %d" % (len(bad), len(plain), bad[0]))

            # ...AND THERE IS NO DIRECT ASSERTION ON THE BSS'S CONTENTS,
            # which is worth stating rather than leaving as an omission. A
            # version of this row checked that the far end of the bss was
            # still zero, reasoning that an unzeroed one would hold whatever
            # the heap last had; it failed on a single 0xFF nine bytes in,
            # which is the attached Ram Disk's own state. Once the row has a
            # segment the driver has run, and nothing here can tell its data
            # from memory drv_bss missed. What stands in for it is the probes
            # below - a driver handed a bss full of floppy leftovers does not
            # answer them - and tests/unit/t_drvmem.py's host-side check that
            # the stripped file plus its bss IS the assembled image.
            bss = plain[31] * 16

            # 3. and the claim covers image + bss
            kb = int.from_bytes(
                m.read(S("drv_tab") + RD_ROW * DRVR_SZ + 8, 2), "little")
            if kb * 1024 < len(plain) + bss:
                fails.append("the claim is %d KB and the driver needs %d bytes"
                             % (kb, len(plain) + bss))

        # 3. does it answer? - drvcall's own three probes
        dispcp.open_drive(m, mo, S, os88marty.settle, "B")
        wins = dispcp.win_list(m, S)
        if not wins:
            fails.append("no Disk window after double-clicking B:")
        else:
            wx, wy = dispcp.win_rect(m, S, wins[-1])[:2]
            dispcp.open_named(m, mo, S, os88marty.settle, wx, wy,
                              "DRVCALL.O88")
            w2 = dispcp.win_list(m, S)
            if len(w2) <= len(wins):
                fails.append("DRVCALL.O88 did not open")
            else:
                rec = m.read(S("wm_wins") + w2[-1] * dispcp.WIN_SIZE,
                             dispcp.WIN_SIZE)
                pseg = rec[22] | (rec[23] << 8)
                # ...AND THE PACKAGE FILLS THESE IN ITS OWN TIME. The window
                # existing is not the answer arriving, so reading the segment
                # the instant `open_named` returns is the same host-clock race
                # one screen along: it landed on the template's dots and this
                # row reported a driver that was answering perfectly. The
                # bytes are the event, so poll them.
                size = os.path.getsize("build/drvcall.bin")
                raw = m.readseg(pseg, 0, size)
                for _ in range(40):
                    i = raw.find(b"Ping: ")
                    if i >= 0 and bytes(raw[i + 6:i + 8]) != b"..":
                        break
                    time.sleep(0.5)
                    raw = m.readseg(pseg, 0, size)
                for tag, want_txt in ((b"Ping: ", b"Ping: DR"),
                                      (b"Upcase: ", b"Upcase: HELLO WORLD")):
                    i = raw.find(tag)
                    got_txt = bytes(raw[i:i + len(want_txt)])
                    if got_txt == want_txt:
                        say("  %s" % got_txt.decode())
                    else:
                        fails.append("%r, want %r" % (got_txt, want_txt))

    for f in fails:
        say("  FAIL: " + f)
    say("lzdrv: %s" % ("FAILED" if fails else "ok"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
