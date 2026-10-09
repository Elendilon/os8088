#!/usr/bin/env python3
"""hdtake - SPEC.md 52.1.1: on a 286 or better, HDD.DRV's own IDE rung TAKES
a drive the BIOS also knows, once it has proved it is the same disk.

    make && python3 tests/hdtake.py

THE REASON is the PC speaker. An AT BIOS moves an IDE sector by PIO with
interrupts OFF, so every int 13h read loses the IRQ0s due inside it, and a
Video Player stream on the speaker - whose clock IS one IRQ0 a sample
(SPEC.md 98.3.15) - played slow by exactly what was lost: the owner's 286 and
86Box's both played a 15.1 s file in ~17.5 through the BIOS, and in 15.1 with
the BIOS told there was no disk. Rung 1's loop runs with interrupts on.

QEMU by name: it is the one emulator here with a 286-class CPU AND a BIOS
that knows an IDE disk (SeaBIOS, if=ide) - which is exactly the pairing this
is about. MartyPC is an 8088, where rung 1 never runs.

The fixture: a raw 16-head, 63-sector disk with one FAT16 volume, CALC.O88 in
its root, and a system floppy whose SYSTEM.CFG wants HDD.DRV (bit 1).
  1. HDD.DRV's device row 0 is an IDE row (HDK_IDE) on 1F0h unit 0, carrying
     the int 13h drive it was taken from - 80h - in HDD_BIOS: the BIOS's
     report and IDENTIFY's agreed on the geometry, and LBA 0 read through both
     rungs was the same 512 bytes.
  2. ...and there is ONE row, not two: the takeover replaced the BIOS row,
     which is what keeps the volume from mounting twice.
  3. The volume works through it: C:'s window lists CALC.O88, and launching it
     - the whole package read through rung 1 - opens the Calculator.
`--blank` is the refusal: the same disk with LBA 0's 55AA wiped, which is
what two BLANK disks would share - so geometry alone would pair them - and
row 0 must stay the BIOS's, untouched (HDD_BIOS and HDD_BASE 0).
Break on purpose: hd_twins's call taken out of hd_ready, and row 0 stays a
BIOS row (step 1 fails); its signature test taken out, and --blank fails.
"""
import atexit
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tests"), os.path.join(ROOT, "tools")]
os.chdir(ROOT)
import os88build                                              # noqa: E402
import os88geom as geom                                       # noqa: E402
import os88qemu                                               # noqa: E402
import os88ui                                                 # noqa: E402
import xmcheck                                                # noqa: E402
from cycweb import pkg_syms                                   # noqa: E402

HDD_SIZE, HDD_KIND, HDD_UNIT, HDD_BIOS, HDD_BASE = 12, 0, 1, 3, 10
HDK_BIOS, HDK_IDE = 1, 2
DRVR_SIZE = 16


class QH(object):
    """A private QEMU with the floppy and an IDE disk."""

    def __init__(self, tmp, sysimg, appsimg, hdimg):
        self.sock = os.path.join(tmp, "qmp.sock")
        self.pid = os.path.join(tmp, "qemu.pid")
        self.pidn = None
        atexit.register(self.close)
        os88qemu.own(self.pid, self.sock)   # (the launch site's teardown)
        subprocess.run(
            ["qemu-system-i386", "-machine", "pc,vmport=off", "-m", "4",
             "-drive", "file=%s,format=raw,if=floppy" % sysimg,
             "-drive", "file=%s,format=raw,if=floppy,index=1" % appsimg,
             "-drive", "file=%s,format=raw,if=ide,index=0,media=disk" % hdimg,
             "-boot", "a", "-chardev", "msmouse,id=m0",
             "-serial", "chardev:m0", "-display", "none",
             "-qmp", "unix:%s,server,nowait" % self.sock,
             "-daemonize", "-pidfile", self.pid], check=True)
        self.pidn = int(open(self.pid).read().strip())

    def close(self):
        if self.pidn:
            try:
                os.kill(self.pidn, signal.SIGTERM)
                os88qemu.gone(self.pidn)
            except OSError:
                pass
            self.pidn = None

    def hmp(self, *cmds):
        return xmcheck.qmp(self.sock, *cmds)

    def read(self, linear, n):
        return bytes(xmcheck.read_bytes(self.sock, linear, n))

    def readseg(self, seg, off, n):
        return self.read((seg << 4) + off, n)


def main():
    blank = "--blank" in sys.argv[1:]
    bad = []
    tool = os.path.getsize(os88build.at("build/hddtool.bin"))
    syms, img = pkg_syms("drivers/hdd/hdd.asm",
                         ("drivers/hdd/", "drivers/", "apps/", "build/"),
                         ("HDTOOL_KB=%d" % ((tool + 1023) // 1024),))
    if img != open(os88build.at("build/hdd.bin"), "rb").read():
        sys.exit("hdtake: build/hdd.bin is not this source - run `make`")
    tmp = tempfile.mkdtemp(dir=os.path.join(ROOT, "build"))
    q = None
    try:
        hdimg = os.path.join(tmp, "hd.img")
        subprocess.run([sys.executable, "tools/os88hdd.py", "--raw",
                        "--noboot", "--out", hdimg, "--heads", "16",
                        "--spt", "63", "--cyls", "130", "--file",
                        "CALC.O88=" + os88build.at("build/calc.o88")],
                       check=True, capture_output=True)
        if blank:                       # (LBA 0's signature, gone)
            with open(hdimg, "r+b") as f:
                f.seek(510)
                f.write(b"\0\0")
        sysimg = os.path.join(tmp, "sys.img")
        shutil.copy(os88build.at("build/os8088.img"), sysimg)
        cfg = os.path.join(tmp, "SYSTEM.CFG")
        open(cfg, "wb").write(b"O88CFG\0\0" + (3).to_bytes(2, "little")
                              + b"DW" + bytes([1, 2])
                              + (1 << 1).to_bytes(2, "little") + b"\0\0")
        subprocess.run([sys.executable, "tools/os88fat.py", "add", sysimg,
                        cfg, "SYSTEM.CFG"], check=True, capture_output=True)
        appsimg = os.path.join(tmp, "apps.img")   # (B:, which the desktop
        shutil.copy(os88build.at("build/apps.img"), appsimg)  # wait reads)
        q = QH(tmp, sysimg, appsimg, hdimg)
        os88qemu.acted(q, lambda: os.path.exists(q.sock), secs=30,
                       what="the QMP socket")
        xmcheck.wait_desktop(q.sock, "hdtake")
        S = xmcheck.sym
        row = S("drv_tab") + 1 * DRVR_SIZE + geom.DRVR_SEG
        seg = struct.unpack("<H", q.read(row, 2))[0]
        if not seg:
            bad.append("HDD.DRV is not loaded - SYSTEM.CFG's bit 1 was not "
                       "read, and this tests nothing")
            return report(bad)
        base = seg << 4
        nd = q.read(base + syms["hd_ndev"], 1)[0]
        rows = [q.read(base + syms["hd_devs"] + i * HDD_SIZE, HDD_SIZE)
                for i in range(nd)]
        for i, r in enumerate(rows):
            print("   1. device %d: kind %d unit %02Xh bios %02Xh base %04Xh "
                  "geometry %d/%d/%d" % (
                      i, r[HDD_KIND], r[HDD_UNIT], r[HDD_BIOS],
                      struct.unpack_from("<H", r, HDD_BASE)[0],
                      struct.unpack_from("<H", r, 4)[0],
                      struct.unpack_from("<H", r, 6)[0],
                      struct.unpack_from("<H", r, 8)[0]))
        if blank:
            r = rows[0] if rows else None
            if r is None or r[HDD_KIND] != HDK_BIOS or r[HDD_BIOS] or \
                    struct.unpack_from("<H", r, HDD_BASE)[0]:
                bad.append("a disk with no 55AA at LBA 0 was taken, or its "
                           "BIOS row left changed")
            return report(bad)
        if not rows or rows[0][HDD_KIND] != HDK_IDE or \
                rows[0][HDD_BIOS] != 0x80 or rows[0][HDD_UNIT] != 0 or \
                struct.unpack_from("<H", rows[0], HDD_BASE)[0] != 0x1F0:
            bad.append("the BIOS's drive 80h was not taken by rung 1 (row 0 "
                       "is not IDE 1F0h unit 0 with HDD_BIOS 80h)")
        if nd != 1:
            bad.append("%d device rows for one disk, not 1" % nd)
        ui = os88ui.UI(q, mouse=object(), sym=S, verbose=False)
        try:
            before = set(o.i for o in ui.windows())
            xmcheck.dblclick(q.sock, *geom.drive_pt(q, "C", S))
            box = {}

            def disk():
                for o in ui.windows():
                    if o.i not in before and o.visible:
                        box["w"] = o
                        return True
                return False
            if not os88qemu.acted(q, disk, secs=30, what="C:'s window"):
                raise RuntimeError("C:'s window never opened")
            w = box["w"]
            os88qemu.pace(q, 1)
            i, _ = ui.entry("CALC.O88", w)
            print("   3. C: lists CALC.O88 at entry %d" % i)
            before = set(o.i for o in ui.windows())
            xmcheck.dblclick(q.sock, *ui.row_xy(w, i - ui.scroll(w)))
            opened = os88qemu.acted(
                q, lambda: any(o.i not in before and o.visible
                               for o in ui.windows()), secs=30,
                what="the Calculator")
            print("   ...launched through rung 1: %s" % opened)
            if not opened:
                bad.append("CALC.O88 off C: did not open")
        except Exception as e:                  # (os88ui raises naming it)
            bad.append("C: did not work through rung 1: %s" % e)
    finally:
        if q is not None:
            q.close()
        shutil.rmtree(tmp, ignore_errors=True)
    return report(bad)


def report(bad):
    for b in bad:
        print("   FAIL: %s" % b)
    print("hdtake: %s" % ("FAIL" if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
