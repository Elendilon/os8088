#!/usr/bin/env python3
"""THE WHOLE SHIPPED SET, COMPRESSED, boots and runs (SPEC.md 20.13, 20.14).

    make zset ZFMT=lz4 && python3 tests/lzship.py --fmt lz4

Every other row in this family compresses one subject: lzload three packages,
lzdrv one driver, lzmod one module. This is the configuration a user would
actually be handed - `make zset ZFMT=...` - where every shipped package, every
shipped driver and every data file on both 360KB floppies is compressed at
once, and the kernel that reads them is built to carry that format.

It exists because that configuration has a failure mode none of the single-
subject rows can have: the system disk's drivers are expanded during BOOT, by
a kernel that has not finished starting, into a heap that is still being laid
out. Nine of them, one after another.

FOUR ASSERTIONS:

  1. it BOOTS to a desktop, which is the drivers expanding;
  2. the drivers actually ATTACHED - the count off drv_tab, not off the
     screen, because a driver that failed to expand is a driver that is
     silently absent rather than one that says so;
  3. a compressed package on the apps disk OPENS - the loader's in-place
     expansion, on a package nobody chose for being easy;
  4. BEVERLY.MOD opens from MEDIA/ on the APPS disk. That last is the point
     of the whole exercise: at 360KB the module needs a floppy of its own
     (SPEC.md 24.4), and compressed it does not.
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
import dispcp                                          # noqa: E402
import os88geom                                        # noqa: E402
from trackmove import pkg_syms, find_win               # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
# BOTH ARMS NAME A SYMBOL NOW. `zset ZFMT=lz4` builds COMPRESS=lz4, which is
# a SINGLE-format kernel and passes -DLZ_HAVE_LZ4 - where the default carries
# both and passes nothing (SPEC.md 20.13.6). An empty tuple here used to mean
# "the default, which is LZ4 alone" and now means "the default, which is
# both", so it described a kernel this row never builds and os88sym refused
# every address.
DEFS = {"lz4": ("LZ_HAVE_LZ4",), "lzb": ("LZ_HAVE_LZB",)}
DRV_TAB, DRVR_SZ = "drv_tab", 10        # SPEC.md 51.3's row, for the count


def say(*a):
    print(*a, flush=True)


def compressed(img):
    """(compressed, total) shipped files on `img`, read HOST-side.

    A file is compressed if it carries the directory hint (data, SPEC.md
    20.14.1) or if its own header has flags bit 3 (a package, 20.13) or its
    image exceeds its file (a driver, 20.13.3.1). Three signals because there
    are three formats, and reading the FILE rather than trusting the entry is
    the same discipline the kernel uses.
    """
    d = open(img, "rb").read()
    bps = struct.unpack_from("<H", d, 11)[0]
    res = struct.unpack_from("<H", d, 14)[0]
    nfat, nent = d[16], struct.unpack_from("<H", d, 17)[0]
    fsz = struct.unpack_from("<H", d, 22)[0]
    spc = d[13]
    root = (res + nfat * fsz) * bps
    data = root + nent * 32
    seen = [0, 0]

    def first_sector(clus):
        return d[data + (clus - 2) * spc * bps:][:512] if clus >= 2 else b""

    def scan(off, n):
        for i in range(n):
            e = d[off + i * 32:off + i * 32 + 32]
            if e[0] in (0, 0xE5) or e[11] & 0x08:
                continue
            clus = struct.unpack_from("<H", e, 26)[0]
            if e[11] & 0x10:
                if e[0:1] != b"." and clus >= 2:
                    scan(data + (clus - 2) * spc * bps, spc * bps // 32)
                continue
            size = struct.unpack_from("<I", e, 28)[0]
            name = e[:11].decode("ascii", "replace")
            seen[1] += 1
            hdr = first_sector(clus)
            if e[12] in (0x5A, 0x5B):               # a 'CZ' data file, either
                                                    # format (SPEC.md 20.14.2.4)
                seen[0] += 1
            elif len(hdr) >= 12 and hdr[:2] == b"O8":
                if hdr[2] == 3 and hdr[3] & 0x08:   # a package
                    seen[0] += 1
                elif hdr[2] == 4 and struct.unpack_from("<H", hdr, 8)[0] > size:
                    seen[0] += 1                    # a driver
            del name
    scan(root, nent)
    return tuple(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmt", default="lz4", choices=("lz4", "lzb"))
    ap.add_argument("--machine", default="os8088_5150_cga_gla")
    a = ap.parse_args()

    zdir = os.path.join("build", "z-" + a.fmt)
    sysimg = os.path.join(zdir, "os8088-360.img")
    appsimg = os.path.join(zdir, "apps360.img")

    # ALWAYS, and not only when the images are missing. `make zset` leaves
    # build/kernel.bin as whichever format ran last, and os88sym refuses an
    # address unless its re-assembly is byte-identical to that file - so the
    # tree has to be ON the format under test before a single symbol resolves.
    # It is a no-op when it already is. ($OS88_BUILD does not serve here: the
    # generated includes - buildnum.inc, associco.inc - live in build/ and not
    # beside the copied kernel.)
    subprocess.check_call(["make", "zset", "ZFMT=" + a.fmt], cwd=ROOT,
                          stdout=subprocess.DEVNULL)

    def S(n):
        return os88sym.linear(n, DEFS[a.fmt])

    fails = []
    for img, tag in ((sysimg, "system"), (appsimg, "apps")):
        z, n = compressed(img)
        say("  %-8s %s: %d of %d files compressed, %d bytes"
            % (tag, os.path.basename(img), z, n, os.path.getsize(img)))
        if z < 2:
            fails.append("%s carries %d compressed files - the set was built "
                         "without PKGZ" % (tag, z))
    if fails:
        for f in fails:
            say("  FAIL: " + f)
        say("lzship: FAILED")
        return 1

    P = pkg_syms("apps/tracker/tracker.asm")
    plain = open("apps/tracker/beverly.mod", "rb").read()

    with os88marty.launch(sysimg, apps=appsimg, machine=a.machine) as m:
        # 1. it boots - which IS the drivers expanding, nine of them, during a
        #    boot that has not finished laying out the heap
        os88marty.settle(m, gate=os88marty.desktop_up)
        say("  boot       ok  (a desktop, so every driver expanded)")

        # 2. ...and they ATTACHED. drv_tab and not the screen: a driver that
        #    failed to expand is silently absent, not visibly broken.
        raw = m.read(S("drv_tab"), DRVR_SZ * 16)
        live = sum(1 for i in range(16)
                   if raw[i * DRVR_SZ] | (raw[i * DRVR_SZ + 1] << 8))
        say("  drivers    %d attached" % live)
        if live < 1:
            fails.append("no driver attached: drv_tab is empty")

        mo = os88mouse.Mouse(marty=m)
        dispcp.open_drive(m, mo, S, os88marty.settle, "B")
        wins = dispcp.win_list(m, S)
        if not wins:
            sys.exit("lzship: no Disk window after double-clicking B:")
        wx, wy = dispcp.win_rect(m, S, wins[-1])[:2]
        rows = [r[0] for r in dispcp.listing(m, S)]
        say("  B: lists   %r" % rows)

        # 3. a compressed PACKAGE opens, out of APPS/
        n0 = len(wins)
        dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "APPS")
        os88marty.settle(m)
        dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "CALC.O88")
        for _ in range(20):
            time.sleep(1)
            if len(dispcp.win_list(m, S)) > n0:
                break
        if len(dispcp.win_list(m, S)) > n0:
            say("  package    ok  (CALC.O88 opened, compressed)")
        else:
            fails.append("CALC.O88 did not open: the loader refused a "
                         "compressed package off the shipped disk")

        # 4. ...and the MODULE, out of MEDIA/ on the APPS disk, which at this
        #    geometry is the whole point.
        wins = dispcp.win_list(m, S)
        dispcp.open_drive(m, mo, S, os88marty.settle, "B")
        wins2 = dispcp.win_list(m, S)
        wx, wy = dispcp.win_rect(m, S, wins2[-1])[:2]
        dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "MEDIA")
        os88marty.settle(m)
        dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "BEVERLY.MOD")
        for _ in range(40):
            time.sleep(1)
            if find_win(m, S, "Tracker")[0]:
                break
        time.sleep(20)
        os88marty.settle(m)
        # BY TITLE, and not by slot: CALC is open above, the Disk window has
        # been raised again, and wm_wins' last slot is whichever index the
        # window manager reused - not the newest window. Reading trk_modseg
        # out of CALC's segment answers a plausible number and then 116KB of
        # somebody else's memory, which is a failure that looks like a broken
        # decoder.
        pseg, _ = find_win(m, S, "Tracker")
        if not pseg:
            fails.append("no Tracker window: BEVERLY.MOD did not open from "
                         "MEDIA/ on the apps disk, which is the whole reason "
                         "this set exists")
        else:
            seg = int.from_bytes(m.readseg(pseg, P["trk_modseg"], 2), "little")
            got = b""
            while seg and len(got) < len(plain):
                k = min(0x8000, len(plain) - len(got))
                got += m.readseg(seg + (len(got) >> 4), 0, k)
            if got == plain:
                say("  module     ok  (all %d bytes, out of MEDIA/ on the "
                    "APPS disk)" % len(plain))
            elif not seg:
                # A SHOT, because [trk_modseg] = 0 means Tracker's own error
                # path ran and the reason is on the glass in words - which no
                # amount of reading memory recovers.
                shot = "build/lzship-%s-fail.png" % a.fmt
                m.shot(shot, rendered=True)
                fails.append("Tracker opened and holds no module - its own "
                             "error is in %s" % shot)
            else:
                bad = [i for i in range(len(plain)) if got[i] != plain[i]]
                fails.append("%d of %d module bytes differ, first at %d - "
                             "which is %s the 64KB boundary"
                             % (len(bad), len(plain), bad[0],
                                "past" if bad[0] >= 0x10000 else "before"))

    # ...and put the tree back on the default build, or every row after this
    # one decodes a kernel os88sym cannot describe.
    subprocess.check_call(["make"], cwd=ROOT, stdout=subprocess.DEVNULL)
    for f in fails:
        say("  FAIL: " + f)
    say("lzship: %s" % ("FAILED" if fails else "ok"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
