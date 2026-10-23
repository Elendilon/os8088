#!/usr/bin/env python3
"""An install whose SOURCE is the HTTP drive (SPEC.md 120, 62.9.17.1).

    python3 tests/httpinstall.py [--noattr]

The upgrade the network mount exists for: a machine with os8088 already on
its hard disk mounts a release's system disk over HTTP and installs from it,
keeping its files. It failed at once, naming KERNEL.SYS: a redirected
volume's FIND reported every attribute as 0, so the installer took KERNEL.SYS
for a plain file and created it with OSAPI_FILE_WRITE over the hidden +
system KERNEL.SYS the kept volume already held - which the kernel refuses.

  1. The host exports build/os8088-360.img with tools/os88httpdrv.py, which
     carries each file's read-only, hidden and system bits into OS88.IDX,
     and adds HTTPMARK.TXT to the root - a file only the SERVED tree has, so
     its arrival on C: proves the install read the drive and not A:, which
     is a system disk too (hd_isrc_ck falls back to every floppy).
  2. QEMU: build/httpmount.img in A: with SYSTEM.CFG asking for HDD.DRV,
     ETHER.DRV and HTTPFS.DRV, its HTTPDRV.CFG naming this server, and an
     IDE disk whose FAT16 volume already carries a hidden + system KERNEL.SYS
     - the kept-volume case the field report is.
  3. Open the HTTP drive (the installer's source is the volume the user is
     standing on), then Control Panel -> Hard Drive -> Install -> Install,
     keeping files.
  4. Asserted on the host, off the IDE image: the MBR committed, HTTPMARK.TXT
     arrived, and every root file the system disk carries is there with its
     bytes - KERNEL.SYS and each driver hidden + system, as a floppy install
     writes them.

BREAK IT ON PURPOSE: `--noattr` serves the same tree with an index that
drops the attributes, which is what the drive had before 62.9.17.1. The
install then stops on KERNEL.SYS, nothing commits, and this row fails.
QEMU by name: MartyPC has no NIC (docs/TESTING.md, item 5).
"""
import atexit
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tests"), os.path.join(ROOT, "tools")]
os.chdir(ROOT)
import httpmount as HM                                        # noqa: E402
import os88build                                              # noqa: E402
import os88httpdrv                                            # noqa: E402
import os88qemu                                               # noqa: E402
import xmcheck                                                # noqa: E402
from os88geom import WIN_SIZE, MAX_WIN                        # noqa: E402

PORT = 8097                     # not httpmount's: the two may run side by side
NOATTR = "--noattr" in sys.argv[1:]
MARK = b"this file is on the SERVED system disk and nowhere else\r\n"
LIMIT = 120                     # host seconds for the install to commit (it takes ~2)

# kernel/ctrl.inc and drivers/hdd/ - the same constants tests/instdeep.py
# drives the MartyPC installer rows with, so a layout change breaks both
CP_I0Y, CP_IROWH = 6, 14        # the item list
CP_LVIS, CP_LAY, CP_LAH, CP_LAX1 = 8, 118, 12, 52   # ...rows shown, the arrows
CP_RX = 96                      # the right pane's left edge
HDP_BY, HDP_BH = 82, 16         # page.inc: the Hard Drive page's button row
HDP_B2X, HDP_BW2 = 74, 64       # ...Install, the middle one
HIW_BY, HIW_BH = 96, 16         # inst.inc: the installer's own button row
HIW_B0X, HIW_BW0 = 8, 88        # ...Install, the first one
WIN_BORDER, WIN_TITLE = 1, 18


class Q(HM.QH):
    """httpmount's QEMU plus an IDE disk."""

    def __init__(self, tmp, sysimg, bimg, hd):
        self.sock = os.path.join(tmp, "qmp.sock")
        self.pid = os.path.join(tmp, "qemu.pid")
        self.pidn = None
        atexit.register(self.close)
        os88qemu.own(self.pid, self.sock)
        subprocess.run(
            ["qemu-system-i386", "-machine", "pc,vmport=off", "-m", "4",
             "-drive", "file=%s,format=raw,if=floppy" % sysimg,
             "-drive", "file=%s,format=raw,if=floppy,index=1" % bimg,
             "-drive", "file=%s,format=raw,if=ide,index=0" % hd,
             "-netdev", "user,id=n0",
             "-device", "ne2k_isa,netdev=n0,iobase=0x300,irq=3",
             "-boot", "a", "-chardev", "msmouse,id=m0",
             "-serial", "chardev:m0", "-display", "none",
             "-qmp", "unix:%s,server,nowait" % self.sock,
             "-daemonize", "-pidfile", self.pid], check=True)
        self.pidn = int(open(self.pid).read().strip())


def wins(q):
    b = q.read(xmcheck.sym("wm_wins"), WIN_SIZE * MAX_WIN)
    return [(i,) + struct.unpack_from("<4H", b, i * WIN_SIZE + 2)
            for i in range(MAX_WIN)
            if struct.unpack_from("<H", b, i * WIN_SIZE)[0] & 2]


def content(w):
    return w[1] + WIN_BORDER, w[2] + WIN_TITLE


def put(img, path, name):
    subprocess.run([sys.executable, "tools/os88fat.py", "del", img, name],
                   capture_output=True)
    subprocess.run([sys.executable, "tools/os88fat.py", "add", img, path, name],
                   check=True, capture_output=True)


class Fat16(object):
    """The installed partition, read on the host: root files only."""

    def __init__(self, path, lba=63):
        self.img = open(path, "rb").read()
        base = lba * 512
        bps, self.spc, rsv, nf, self.nroot = struct.unpack_from(
            "<HBHBH", self.img, base + 11)
        fsz = struct.unpack_from("<H", self.img, base + 22)[0]
        self.bps = bps
        self.fat = base + rsv * bps
        self.root = self.fat + nf * fsz * bps
        self.data = self.root + self.nroot * 32

    def files(self):
        out = {}
        for o in range(self.nroot):
            e = self.img[self.root + o * 32:self.root + o * 32 + 32]
            if e[0] == 0:
                break
            if e[0] == 0xE5 or e[11] & 0x18:
                continue
            n = e[:8].rstrip().decode()
            if e[8:11].strip():
                n += "." + e[8:11].rstrip().decode()
            c, size = struct.unpack_from("<H", e, 26)[0], struct.unpack_from("<I", e, 28)[0]
            out[n] = (e[11], self.body(c, size))
        return out

    def body(self, c, size):
        csz = self.spc * self.bps
        parts = []
        while 2 <= c < 0xFFF8 and len(parts) * csz < size:
            o = self.data + (c - 2) * csz
            parts.append(self.img[o:o + csz])
            c = struct.unpack_from("<H", self.img, self.fat + 2 * c)[0]
        return b"".join(parts)[:size]


def main():
    tmp = tempfile.mkdtemp(dir=os.path.join(ROOT, "build"))
    q = httpd = None
    log = HM.Log()
    bad = []
    try:
        # --- 1: the served tree ------------------------------------------
        src = os88build.at("build/os8088-360.img")
        tree, attrs = os88httpdrv.load(src)
        tree["HTTPMARK.TXT"] = MARK
        web = os.path.join(tmp, "web")
        os.makedirs(web)
        os88httpdrv.write_tree(tree, web)
        idx = os88httpdrv.index_build(tree, 0, {} if NOATTR else attrs)
        open(os.path.join(web, os88httpdrv.IDX_NAME), "wb").write(idx)
        os88httpdrv.check(web)
        print("   1. %s served with %d attribute(s)%s"
              % (os.path.basename(src), 0 if NOATTR else len(attrs),
                 " - --noattr, the index the drive had before 62.9.17.1"
                 if NOATTR else ""))
        HM.PORT = PORT
        httpd = HM.server(web, log)

        # --- 2: the machine ----------------------------------------------
        sysimg = os.path.join(tmp, "sys.img")
        shutil.copy(os88build.at("build/httpmount.img"), sysimg)
        cfg = os.path.join(tmp, "SYSTEM.CFG")
        open(cfg, "wb").write(b"O88CFG\0\0" + (3).to_bytes(2, "little")
                              + b"DW" + bytes([1, 2])
                              + ((1 << 1) | (1 << 4) | (1 << 9)).to_bytes(2, "little")
                              + b"\0\0")
        put(sysimg, cfg, "SYSTEM.CFG")
        hcfg = os.path.join(tmp, "HTTPDRV.CFG")
        u = b"http://10.0.2.2:%d/" % PORT
        open(hcfg, "wb").write(b"HD" + bytes([1, 1]) + u + bytes(96 - len(u)))
        put(sysimg, hcfg, "HTTPDRV.CFG")
        bimg = os.path.join(tmp, "b.img")
        hd = os.path.join(tmp, "hd.img")
        subprocess.run([sys.executable, "tools/os88disk.py", "-o", bimg,
                        "--size", "1440"], check=True, capture_output=True)
        subprocess.run([sys.executable, "tools/os88disk.py", "-o", hd, "--hdd",
                        "--mbr", os88build.at("build/mbr.bin"),
                        "--boot", os88build.at("build/boothd.bin"),
                        "--kernel", os88build.at("build/kernel.sys"),
                        os88build.at("build/readme.txt")],
                       check=True, capture_output=True)
        with open(hd, "r+b") as f:      # the MBR's CODE blanked, so the
            f.write(bytes(446))         # commit (hd_inst_mbr) is a change
                                        # - os88disk wrote the very bytes the
                                        # installer would; the table stays
        old = Fat16(hd).files()
        if not old.get("KERNEL.SYS", (0,))[0] & 6:
            sys.exit("httpinstall: the IDE disk's KERNEL.SYS is not hidden + "
                     "system, so this row would not be the field's case")
        mbr0 = open(hd, "rb").read(446)
        q = Q(tmp, sysimg, bimg, hd)
        os88qemu.acted(q, lambda: os.path.exists(q.sock), secs=30,
                       what="the QMP socket")
        xmcheck.wait_desktop(q.sock, "httpinstall")
        S = xmcheck.sym

        # --- 3: stand on the drive, then Install --------------------------
        row = q.read(S("drv_tab") + HM.HF_ROW * HM.DRVR_SIZE, HM.DRVR_SIZE)
        seg = struct.unpack_from("<H", row, HM.geom.DRVR_SEG)[0]
        if not seg:
            sys.exit("httpinstall: HTTPFS.DRV did not load")
        base = HM.geom.drv_base(seg)
        syms = HM.os88drvsym.symbols("httpfs.bin")
        vol = q.read(base + syms["hf_vol"], 1)[0]
        ui = HM.os88ui.UI(q, mouse=object(), sym=S, verbose=False)
        xmcheck.dblclick(q.sock, *HM.geom.drive_pt(q, chr(ord("A") + vol), S))
        q.need(lambda: HM.front_on(ui, vol) is not None, "the drive's window", 90)
        q.done()

        known = {w[0] for w in wins(q)}
        q.mouse("to", 14, 9)            # the chip menu -> Control Panel, its
        q.mouse("down")                 # second row
        time.sleep(0.5)
        q.mouse("to", 60, 44)
        q.mouse("up")
        q.need(lambda: any(w[0] not in known for w in wins(q)),
               "the Control Panel", 60)
        q.done()
        cp = next(w for w in wins(q) if w[0] not in known)
        print("   3. Control Panel at %r" % (cp[1:],))
        x0, y0 = content(cp)
        nst = q.read(S("cp_nst"), 1)[0]  # the first driver page: Hard Drive,
        for _ in range(16):              # drv_tab row 1 coming before ETHER's
            top = q.read(S("cp_ltop"), 1)[0]
            if nst < top + CP_LVIS:
                break
            q.click(x0 + CP_LAX1 + 6, y0 + CP_LAY + CP_LAH // 2)
        q.click(x0 + 40, y0 + CP_I0Y + (nst - top) * CP_IROWH + 7, cap=5.0)
        known = {w[0] for w in wins(q)}
        q.click(x0 + CP_RX + HDP_B2X + HDP_BW2 // 2, y0 + HDP_BY + HDP_BH // 2,
                cap=10.0)
        q.need(lambda: any(w[0] not in known for w in wins(q)),
               "the installer window", 60)
        iw = next(w for w in wins(q) if w[0] not in known)
        ix, iy = content(iw)
        bx, by = ix + HIW_B0X + HIW_BW0 // 2, iy + HIW_BY + HIW_BH // 2
        n0 = len(log.gets())
        q.click(bx, by, cap=5.0)        # Install: arms (keeps files)
        q.mouse("click", bx, by)        # Install: goes
        print("   3. Install pressed with drive %s: current, keeping files"
              % chr(ord("A") + vol))
        t0 = time.time()
        while open(hd, "rb").read(446) == mbr0:
            if time.time() - t0 > LIMIT:
                gets = log.gets()[n0:]
                sys.exit("httpinstall: FAIL - nothing committed in %ds; the "
                         "drive was asked %r" % (LIMIT, gets[-4:]))
            time.sleep(1)
        print("   3. the MBR committed after %.0fs, %d request(s)"
              % (time.time() - t0, len(log.gets()) - n0))
        last, still = None, 0
        while still < 5:                # ...and the disk goes quiet
            h = open(hd, "rb").read()
            still = still + 1 if h == last else 0
            last = h
            time.sleep(1)
        q.close()

        # --- 4: what landed ----------------------------------------------
        got = Fat16(hd).files()
        if "HTTPMARK.TXT" not in got:
            bad.append("4. HTTPMARK.TXT is not on C: - the install did not read "
                       "the HTTP drive")
        n = 0
        for name, body in tree.items():
            if isinstance(body, dict) or name == "ASSOC.DAT":
                continue                # ...which the installer never copies:
                                        # its rows name the SOURCE's clusters
                                        # (inst.inc, SPEC.md 54.7)
            a, data = got.get(name, (None, None))
            if data != body:
                bad.append("4. %s: %s" % (name, "missing" if data is None
                                          else "%d bytes, the disk's %d"
                                          % (len(data), len(body))))
                continue
            want = attrs.get(name, 0) & 6
            if a & 6 != want:
                bad.append("4. %s: attribute %02Xh, the disk's %02Xh"
                           % (name, a, attrs.get(name, 0)))
                continue
            n += 1
        print("   4. %d root file(s) on C: as the served disk has them; "
              "KERNEL.SYS attribute %02Xh" % (n, got.get("KERNEL.SYS", (0,))[0]))
    finally:
        if q:
            q.close()
        if httpd:
            httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        for b in bad:
            print("httpinstall: FAIL - " + b)
        sys.exit(1)
    print("httpinstall: ok")


if __name__ == "__main__":
    main()
