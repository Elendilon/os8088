#!/usr/bin/env python3
"""BEVERLY.MOD, COMPRESSED, opened by a double-click (SPEC.md 20.14.5).

    make && make lzmodtest && python3 tests/lzmod.py

This is the file the whole feature is for. 116,085 bytes is 114 of a 360KB
disk's 354 clusters, which is why that geometry ships the module on a floppy of
its own (SPEC.md 24.4). LZ4 takes it to 42,177 - 36.3%, 42 clusters - so
Tracker and the module fit one disk with 294 clusters left, and ~145 sectors
of floppy time go away for ~1.2 seconds of decode.

It is also the only file in the tree that exercises the decoder's SEGMENT
CROSSING: 116KB is not a segment, so every path in SPEC.md 20.14.5 - the
bumped ES, the borrowed match source one segment down, lz_cross splitting a
copy at the boundary, and LZ_F_BUMP retiring the offset compare - runs here and
nowhere else.

FOUR ASSERTIONS, and the third is the one that makes the others worth having:

  1. the disk file really is compressed - the 'CZ' header and the directory
     hint, checked on the HOST before the machine is started, so a fixture
     that quietly stopped compressing cannot pass this row;
  2. a double-click on the .MOD row opens Tracker through the association
     (SPEC.md 54), which is the user-visible requirement in one action;
  3. all 116,085 bytes in the guest's claim are BYTE FOR BYTE the original.
     Nothing less will do: a decoder that got one match wrong across the
     64KB boundary still opens a window, still shows the title, and still
     plays - it plays a click;
  4. ...and Tracker holds it - `mp_loaded` - so the bytes above are a module
     the application accepted and not a buffer it read and rejected. Whether
     the mixer TICKS is a question about the machine's sound card and not
     about this feature, so `mp_row` is reported and not asserted, exactly as
     tests/trackmove.py does it.
"""
import argparse
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import os88marty                                       # noqa: E402
import os88mouse                                       # noqa: E402
import os88sym                                         # noqa: E402
import os88lz                                          # noqa: E402
import dispcp                                          # noqa: E402
from trackmove import pkg_syms                         # noqa: E402

SRC = "apps/tracker/beverly.mod"
PACKED = "build/lzf/BEVERLY.MOD"
IMG = "build/lzmod360.img"
CZ_MARK, CZ_M, CZ_H, CZ_L = 0x5A, 12, 13, 20   # +fmt: 20.14.2.4
ROOT = os.path.join(os.path.dirname(__file__), "..")
S = os88sym.linear


def say(*a):
    print(*a, flush=True)


def report(fails, a):
    if a.fmt == "lzb":                  # put the tree back, or every row after
        subprocess.check_call(["make"], cwd=ROOT,   # this one decodes a kernel
                              stdout=subprocess.DEVNULL)  # os88sym cannot
    for f in fails:                                       # describe
        say("  FAIL: " + f)
    say("lzmod: %s" % ("FAILED" if fails else "ok"))
    return 1 if fails else 0


def dirents(img):
    """Every root-directory entry of a FAT12 image, raw."""
    d = open(img, "rb").read()
    bps = struct.unpack_from("<H", d, 11)[0]
    res = struct.unpack_from("<H", d, 14)[0]
    nfat, nent = d[16], struct.unpack_from("<H", d, 17)[0]
    fsz = struct.unpack_from("<H", d, 22)[0]
    off = (res + nfat * fsz) * bps
    for i in range(nent):
        e = d[off + i * 32:off + i * 32 + 32]
        if e[0] not in (0, 0xE5):
            yield e


def host_checks(fails):
    """Assertion 1, before a machine is involved."""
    plain = open(SRC, "rb").read()
    blob = open(PACKED, "rb").read()
    parsed = os88lz.cz_parse(blob)
    if parsed is None:
        fails.append("%s is not a 'CZ' file" % PACKED)
        return plain
    fmt, n = parsed
    if n != len(plain) or os88lz.cz_unwrap(blob) != plain:
        fails.append("%s does not expand to %s" % (PACKED, SRC))
    say("  packed     %d -> %d bytes (%.1f%%, %s)"
        % (len(plain), len(blob), 100.0 * len(blob) / len(plain),
           os88lz.NAMES[fmt]))
    for e in dirents(IMG):
        if e[:11] != b"BEVERLY MOD":
            continue
        hint = struct.unpack_from("<H", e, CZ_L)[0] | (e[CZ_H] << 16)
        size = struct.unpack_from("<I", e, 28)[0]
        ok = (CZ_MARK <= e[CZ_M] <= CZ_MARK + 1     # ...the mark CARRIES the
              and hint == len(plain)                # format (SPEC.md
              and size == len(blob))                # 20.14.2.4)
        say("  hint       mark=%02X unpacked=%d size=%d  %s"
            % (e[CZ_M], hint, size, "ok" if ok else "WRONG"))
        if not ok:
            fails.append("the directory hint on the disk is wrong")
        break
    else:
        fails.append("BEVERLY.MOD is not in %s" % IMG)
    return plain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_cga_gla")
    ap.add_argument("--fmt", default="lz4", choices=("lz4", "lzb"),
                    help="lzb rebuilds the FIXTURE with an LZB module and "
                         "wraps the module with the bit-oriented format - the "
                         "only way LZB's own crossing arm is ever EXECUTED "
                         "(SPEC.md 20.14.5). It is a whole kernel build and a "
                         "ten-second compression, which is why it is not the "
                         "default")
    a = ap.parse_args()

    global PACKED, IMG, S
    if a.fmt == "lzb":
        # THE SYMBOL MAP HAS TO KNOW ABOUT THE KNOB. os88sym re-assembles
        # kernel.asm and refuses an address unless the result is byte-identical
        # to build/kernel.bin (CLAUDE.md's own trap), so a knob kernel needs
        # the same -D on both sides or every row here dies saying the map
        # describes a different kernel.
        S = lambda n: os88sym.linear(n, ("LZ_HAVE_LZ4", "LZ_HAVE_LZB"))
        PACKED, IMG = "build/lzb/BEVERLY.MOD", "build/lzmodlzb360.img"
        # THE SYSTEM DISK IS THE POINT, so `all` and not just the fixture: the
        # scratch image carries the module and Tracker, and the kernel that
        # has to carry LZB is on build/os8088-360.img. Building only the
        # fixture boots the DEFAULT kernel, which does not have the decoder at
        # all - the module is refused, Tracker opens empty, and the row reads
        # exactly like a broken LZB arm. It did, once.
        # NO COMPRESS= ANY MORE: the shipped kernel carries both decoders
        # (SPEC.md 20.13.6), so `all` is the build that can read this module
        # and naming a knob here would test something nobody boots.
        subprocess.check_call(["make", "all", "lzmodlzbtest"],
                              cwd=ROOT, stdout=subprocess.DEVNULL)
    elif not os.path.exists(IMG):
        subprocess.check_call(["make", "lzmodtest"], cwd=ROOT)
    fails = []
    plain = host_checks(fails)
    P = pkg_syms("apps/tracker/tracker.asm")

    with os88marty.launch("build/os8088-360.img", apps=IMG,
                          machine=a.machine) as m:
        os88marty.settle(m, gate=os88marty.desktop_up)
        mo = os88mouse.Mouse(marty=m)
        dispcp.open_drive(m, mo, S, os88marty.settle, "B")
        wins = dispcp.win_list(m, S)
        if not wins:
            sys.exit("lzmod: no Disk window after double-clicking B:")
        wx, wy = dispcp.win_rect(m, S, wins[-1])[:2]
        say("lzmod: B: lists %r" % [r[0] for r in dispcp.listing(m, S)])

        # The ASSOCIATION opens Tracker and loads the module in one action -
        # which is the requirement, not a shortcut past the File menu.
        dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "BEVERLY.MOD")
        for _ in range(30):
            time.sleep(1)
            if len(dispcp.win_list(m, S)) > len(wins):
                break
        wins2 = dispcp.win_list(m, S)
        if len(wins2) <= len(wins):
            fails.append("no window opened: the association did not run, or "
                         "Tracker refused the module")
            return report(fails, a)
        rec = m.read(S("wm_wins") + wins2[-1] * dispcp.WIN_SIZE,
                     dispcp.WIN_SIZE)
        pseg = rec[22] | (rec[23] << 8)
        say("  window     Tracker at %04X" % pseg)

        # Give the load and the first rows time on a 4.77MHz guest.
        time.sleep(20)
        os88marty.settle(m)
        modseg = int.from_bytes(m.readseg(pseg, P["trk_modseg"], 2), "little")
        if not modseg:
            fails.append("[trk_modseg] is 0: Tracker opened and holds no "
                         "module - a read that was REFUSED looks exactly like "
                         "this, so check the kernel carries this format")
            return report(fails, a)
        say("  module     claimed at %04X" % modseg)

        got = b""
        while len(got) < len(plain):        # 116KB, in segment-sized reads
            k = min(0x8000, len(plain) - len(got))
            got += m.readseg(modseg + (len(got) >> 4), 0, k)
        if got == plain:
            say("  bytes      ok  (all %d, byte for byte)" % len(plain))
        else:
            bad = [i for i in range(len(plain)) if got[i] != plain[i]]
            fails.append("%d of %d bytes differ, first at %d (0x%X) - which "
                         "is %s the 64KB boundary"
                         % (len(bad), len(plain), bad[0], bad[0],
                            "past" if bad[0] >= 0x10000 else "before"))

        r1 = m.readseg(pseg, P["mp_row"], 1)[0]
        time.sleep(3)
        r2 = m.readseg(pseg, P["mp_row"], 1)[0]
        loaded = int.from_bytes(m.readseg(pseg, P["mp_loaded"], 2), "little")
        say("  loaded     %s  (mp_loaded=%d, row %d -> %d%s)"
            % ("ok " if loaded else "BAD", loaded, r1, r2,
               "" if r1 != r2 else " - no sound card on this machine, so the"
                                   " mixer has nothing to tick"))
        if not loaded:
            fails.append("Tracker read the bytes and did not accept them")

    return report(fails, a)


if __name__ == "__main__":
    sys.exit(main())
