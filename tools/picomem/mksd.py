#!/usr/bin/env python3
"""mksd.py - a microSD card image for libpmhost's PicoMEM (docs/plans/PICOMEM-EMU-PLAN.md 4.5).

    python3 tools/picomem/mksd.py OUT.img [--mb 32] [FILE ...] [DIR/NAME=SRC ...]
    python3 tools/picomem/mksd.py --selfcheck

The card reads its SD through FatFS (lib/FatFs_SPI, pm_disk.cpp): a
`config.txt` and a binary `PICOMEM.CFG` at the root, floppy images in
`/FLOPPY` and hard disk images in `/HDD`. This writes a FAT16 volume holding
exactly what it is given, with those two folders always present, as a
SUPERFLOPPY - the boot sector at LBA 0, which FatFS mounts as it mounts a
partitioned card. Every name is 8.3 and upper case; FatFS matches the
firmware's `0:/config.txt` against it case-blind.

    mksd.py build/picomem/sd.img                         # an empty card
    mksd.py sd.img config.txt FLOPPY/DOS.IMG=dos33.img   # with a config and a floppy

An empty card is not the same machine as no card: with none, the firmware's
CMD_FDD_Mount never counts the PC's floppies and the BIOS then clears them
from the equipment word (the plan's 6.3) - so every profile gets one.

Deterministic: the volume serial and every timestamp are fixed, so the same
inputs give the same bytes. GPL-2.0-or-later, like the firmware it feeds.
"""
import argparse
import os
import struct
import sys

SECTOR = 512
SERIAL = 0x0588_0EED
STAMP_DATE = ((2026 - 1980) << 9) | (10 << 5) | 29   # 2026-10-29, fixed
STAMP_TIME = 0


def name83(name):
    base, _, ext = name.upper().rpartition(".") if "." in name else (name.upper(), "", "")
    if not base:
        base, ext = ext, ""
    if len(base) > 8 or len(ext) > 3 or not base:
        raise SystemExit("mksd: %r is not an 8.3 name" % name)
    return base.ljust(8).encode("ascii") + ext.ljust(3).encode("ascii")


def dirent(n11, attr, clus, size):
    return struct.pack("<11sBBBHHHHHHHI", n11, attr, 0, 0, STAMP_TIME, STAMP_DATE,
                       STAMP_DATE, 0, STAMP_TIME, STAMP_DATE, clus, size)


def build(out, files, mb=32):
    """files: [(folder or "", NAME, bytes)]"""
    total = mb * 1024 * 1024 // SECTOR
    spc = 4 if mb <= 64 else 8 if mb <= 128 else 16 if mb <= 256 else 32
    reserved, nfats, root_ent = 1, 2, 512
    root_secs = root_ent * 32 // SECTOR
    fatsz = 1
    while True:                                 # the FAT that fits what it maps
        data = total - reserved - nfats * fatsz - root_secs
        clusters = data // spc
        need = ((clusters + 2) * 2 + SECTOR - 1) // SECTOR
        if need <= fatsz:
            break
        fatsz = need
    if not 4085 <= clusters < 65525:
        raise SystemExit("mksd: %d MB gives %d clusters, not a FAT16 volume" % (mb, clusters))
    csize = spc * SECTOR
    fat = [0xFFF8, 0xFFFF] + [0] * clusters
    data_start = reserved + nfats * fatsz + root_secs
    img = bytearray(total * SECTOR) if False else None
    blobs = {}                                  # cluster -> bytes
    nxt = [2]

    def alloc(payload):
        n = max(1, (len(payload) + csize - 1) // csize)
        first = nxt[0]
        if first + n - 2 > clusters:
            raise SystemExit("mksd: the card is full - use a bigger --mb")
        for i in range(n):
            fat[first + i] = first + i + 1 if i < n - 1 else 0xFFFF
        for i in range(n):
            blobs[first + i] = payload[i * csize:(i + 1) * csize]
        nxt[0] += n
        return first

    folders = {"FLOPPY": [], "HDD": []}
    root = []
    for folder, name, payload in files:
        if folder:
            folders.setdefault(folder.upper(), []).append((name, payload))
        else:
            root.append((name, payload))
    rootdir = [struct.pack("<11sB", b"PICOMEM SD ", 0x08) + bytes(20)]
    for folder in sorted(folders):
        entries = folders[folder]
        # the folder's own cluster first, then its files, then its listing
        fclus = alloc(bytes(csize))
        lst = [dirent(b".          ", 0x10, fclus, 0), dirent(b"..         ", 0x10, 0, 0)]
        for name, payload in entries:
            c = alloc(payload) if payload else 0
            lst.append(dirent(name83(name), 0x20, c, len(payload)))
        body = b"".join(lst)
        if len(body) > csize:
            raise SystemExit("mksd: too many files in %s" % folder)
        blobs[fclus] = body
        rootdir.append(dirent(name83(folder), 0x10, fclus, 0))
    for name, payload in root:
        c = alloc(payload) if payload else 0
        rootdir.append(dirent(name83(name), 0x20, c, len(payload)))
    if len(rootdir) > root_ent:
        raise SystemExit("mksd: too many files at the root")

    bs = bytearray(SECTOR)
    bs[0:3] = b"\xEB\x3C\x90"
    bs[3:11] = b"OS8088SD"
    struct.pack_into("<HBHBHHBHHHII", bs, 11, SECTOR, spc, reserved, nfats, root_ent,
                     total if total < 65536 else 0, 0xF8, fatsz, 63, 255, 0,
                     total if total >= 65536 else 0)
    struct.pack_into("<BBBI11s8s", bs, 36, 0x80, 0, 0x29, SERIAL, b"PICOMEM SD ", b"FAT16   ")
    bs[510:512] = b"\x55\xAA"
    fatb = struct.pack("<%dH" % len(fat), *fat)
    fatb += bytes(fatsz * SECTOR - len(fatb))

    with open(out, "wb") as f:
        f.write(bs)
        f.write(bytes((reserved - 1) * SECTOR))
        for _ in range(nfats):
            f.write(fatb)
        rd = b"".join(rootdir)
        f.write(rd + bytes(root_secs * SECTOR - len(rd)))
        for c in sorted(blobs):
            f.seek((data_start + (c - 2) * spc) * SECTOR)
            f.write(blobs[c])
        f.truncate(total * SECTOR)
    return clusters


def selfcheck():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "sd.img")
        build(p, [("", "config.txt", b"BIOS D000\n"), ("FLOPPY", "A.IMG", bytes(368640))])
        b = open(p, "rb").read()
        ok = b[510:512] == b"\x55\xAA" and b[54:62] == b"FAT16   " and \
            len(b) == 32 * 1024 * 1024 and b.find(b"CONFIG  TXT") > 0 and \
            b.find(b"BIOS D000") > 0
        q = os.path.join(d, "sd2.img")
        build(q, [("", "config.txt", b"BIOS D000\n"), ("FLOPPY", "A.IMG", bytes(368640))])
        ok = ok and open(q, "rb").read() == b
    print("mksd: selfcheck %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out", nargs="?")
    ap.add_argument("items", nargs="*", help="FILE (at the root) or FOLDER/NAME=SRC")
    ap.add_argument("--mb", type=int, default=32)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if not a.out:
        ap.error("OUT is required")
    files = []
    for it in a.items:
        if "=" in it:
            dst, src = it.split("=", 1)
        else:
            dst, src = os.path.basename(it), it
        folder, _, name = dst.rpartition("/")
        files.append((folder, name, open(src, "rb").read()))
    n = build(a.out, files, a.mb)
    print("mksd: %s, %d MB FAT16, %d clusters, %d file(s)" % (a.out, a.mb, n, len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
