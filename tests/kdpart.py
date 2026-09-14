#!/usr/bin/env python3
"""kern_dos is a PART, and its bytes are reachable as absolute SECTORS.

    make kdostest && python3 tests/kdpart.py

docs/plans/KERN-DOS-PLAN.md §4.1.1 is the claim this row makes good, and it is
the one the whole handoff rests on: *the part is a byte range of `DOS.O88`,
which is a file on a volume, so the same walk that turns a hibernation image
into extents turns the part into extents too.* The stub then reads `kern_dos`
straight into low memory with `int 13h`, off a machine whose heap has already
been given away.

**IT IS ARITHMETIC AND IT IS DONE HERE BEFORE ANY ASSEMBLY DEPENDS ON IT.**
Every step below is one the kernel's walk and the stub will repeat on the
guest, and each has a way to be quietly wrong:

  1  the part table says where the part starts IN THE FILE - `OP_R_OFF` in
     512-byte units, which is not bytes and not clusters;
  2  the FAT chain says which CLUSTERS the file occupies, which are not
     contiguous and whose runs are what an extent list is;
  3  a cluster is `spc` sectors, so file sector N is the (N mod spc)'th sector
     of the (N div spc)'th cluster - the one place an off-by-one lands in the
     middle of the image rather than at its edge;
  4  and the bytes at those sectors, LZ4-expanded, have to BE `kern_dos` -
     which is the only step that cannot be fooled by a consistent mistake in
     the first three.

VERIFIED TO FAIL: starting the walk one sector LATE takes step 4 red with
`LZ4: bad offset 3956 at output 5` - a stream that starts mid-token - and
taking the part's UNPACKED length as the number of sectors to read takes step
3 red with `wants file sectors 63..153 and the file has 138`.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88fat                                                  # noqa: E402
import os88lz                                                   # noqa: E402

IMG = os.path.join(ROOT, "build", "kdos360.img")
KD = os.path.join(ROOT, "build", "kerndos.bin")
PARTS_MAGIC = b"O88PARTS"
PARTS_HDR = 10                  # magic(8) + count(1) + reserved(1)
PART_ROW = 8
DOS_PART_KD = 2                 # loader image, 0 = the box, 1 = the CORE
                                # (SPEC.md 96.44.5), 2 = kern_dos


def fail(msg):
    print("kdpart: FAIL: %s" % msg)
    sys.exit(1)


def read_chain(v, first, size):
    """A file's bytes, out of its cluster chain. `Fat12.read` is ROOT ONLY by
    design (its own docstring says why), and DOS.O88 is in APPS/."""
    out = bytearray()
    for c in v.chain(first):
        off = v.cluster_off(c)
        out += v.img[off:off + v.spc * v.bps]
    return bytes(out[:size])


def dir_entry(v, folder, raw11):
    """The 32-byte directory record for `raw11` inside root/`folder`."""
    fc = None
    for _i, _o, e in v.entries():
        if e[:11] == os88fat.Fat12.raw11(folder) and e[11] & 0x10:
            fc = struct.unpack_from("<H", e, 26)[0]
    if fc is None:
        fail("no %s folder in the root of %s" % (folder, os.path.basename(IMG)))
    for c in v.chain(fc):
        off = v.cluster_off(c)
        for i in range(0, v.spc * v.bps, 32):
            rec = bytes(v.img[off + i:off + i + 32])
            if rec[0] in (0x00, 0xE5):
                continue
            if rec[:11] == raw11:
                return rec
    return None


def main():
    for p in (IMG, KD):
        if not os.path.exists(p):
            fail("%s is missing - run `make kdostest` first" % p)

    v = os88fat.Fat12(IMG)
    ent = dir_entry(v, "APPS", b"DOS     O88")
    if ent is None:
        fail("no DOS.O88 in APPS/ of %s - `make kdostest` did not build the "
             "disk this row is about" % os.path.basename(IMG))
    fclus = struct.unpack_from("<H", ent, 26)[0]
    fsize = struct.unpack_from("<I", ent, 28)[0]
    blob = read_chain(v, fclus, fsize)
    print("kdpart: APPS/DOS.O88 is %d bytes, %d sector(s)"
          % (len(blob), -(-len(blob) // 512)))

    # --- 1: the part table, inside the image ---------------------------------
    image = struct.unpack_from("<H", blob, 8)[0]
    flags = blob[3]
    if not flags & 4:
        fail("DOS.O88's flags are 0x%02X and bit 2 (OS88_F_PARTS) is clear - "
             "this is the SHIPPED package, so `make kdostest` did not put the "
             "parted one on the disk" % flags)
    at = blob.find(PARTS_MAGIC, 0, image)
    if at < 0:
        fail("flags bit 2 is set and there is no 'O88PARTS' table in the image")
    # **kern_dos IS PART 1 AND THE IMAGE IS A LOADER** (SPEC.md 96.44.4). It
    # was part 0 of a package whose image was the box itself until W9c, which
    # made the image `apps/dos/dosload.asm` and the box part 0 - because
    # os88pkg.py refuses --compress beside parts, so whatever is the IMAGE
    # ships raw and 96.40.3 measured that at +932 ms a launch.
    n = blob[at + PARTS_HDR - 2]
    if n != 3:
        fail("the table declares %d part(s); the four-piece DOS.O88 is a "
             "loader image with THREE - the box, the INT 21h core and "
             "kern_dos (SPEC.md 96.44.5)" % n)
    kind, pflags, poff, plen, pzkb = struct.unpack_from(
        "<BBHHH", blob, at + PARTS_HDR + PART_ROW * DOS_PART_KD)
    if not pflags & 16:
        fail("part %d's flags are 0x%02X and OP_COMP (16) is clear: an "
             "uncompressed part costs the 360KB system disk eight more "
             "clusters than it has to. The pairing with OP_LAZY was refused "
             "until SPEC.md 20.12.7.4" % (DOS_PART_KD, pflags))
    if not pflags & 8:
        fail("part %d's flags are 0x%02X and OP_LAZY (8) is clear. It MUST be "
             "lazy: op_load reads every eager part into one carve and "
             "op_size refuses a carve of 64KB or more, and the box plus "
             "kern_dos unpack to ~74KB (SPEC.md 96.44.4.1)"
             % (DOS_PART_KD, pflags))
    print("kdpart: 1/5 part %d is ASSET+COMP+LAZY at file sector %d, %d bytes "
          "unpacked, %d packed" % (DOS_PART_KD, poff, plen, pzkb))

    # --- 2: the chain, as absolute LBA runs ----------------------------------
    # Exactly the shape kernel/hiber.inc's hbm_extents builds: {lba, count},
    # contiguous clusters coalesced. The volume is the boot floppy, so an
    # absolute LBA is the volume-relative one - there is no partition base.
    runs = []
    for c in v.chain(fclus):
        lba = v.cluster_lba(c)
        if runs and runs[-1][0] + runs[-1][1] == lba:
            runs[-1][1] += v.spc
        else:
            runs.append([lba, v.spc])
    print("kdpart: 2/5 the chain is %d cluster(s) in %d coalesced run(s)"
          % (len(list(v.chain(fclus))), len(runs)))

    # --- 3: file sector -> absolute sector ------------------------------------
    flat = []
    for lba, cnt in runs:
        flat.extend(range(lba, lba + cnt))
    need = -(-pzkb // 512)
    if poff + need > len(flat):
        fail("the part wants file sectors %d..%d and the file has %d"
             % (poff, poff + need - 1, len(flat)))
    want = flat[poff:poff + need]
    ext, i = [], 0
    while i < len(want):
        j = i
        while j + 1 < len(want) and want[j + 1] == want[j] + 1:
            j += 1
        ext.append((want[i], j - i + 1))
        i = j + 1
    print("kdpart: 3/5 the part is %d sector(s) in %d extent(s): %s"
          % (need, len(ext),
             ", ".join("%d+%d" % e for e in ext[:6])
             + (" ..." if len(ext) > 6 else "")))

    # --- 4: and the bytes ARE kern_dos ---------------------------------------
    got = b"".join(bytes(v.img[l * v.bps:(l + 1) * v.bps]) for l, _c in
                   [(s, 1) for s in want])
    got = got[:pzkb]
    try:
        out = os88lz.decompress(got, os88lz.LZ4, plen)
    except Exception as e:                                      # noqa: BLE001
        fail("the sectors the walk names do not decompress: %s. That is step "
             "3's arithmetic wrong, not the packer's - a part read one sector "
             "early or late is a stream that starts mid-token" % e)
    if len(out) != plen:
        fail("the part expands to %d bytes and its row says %d" % (len(out), plen))
    raw = open(KD, "rb").read()
    if out != raw:
        n = next((i for i, (a, b) in enumerate(zip(out, raw)) if a != b), None)
        fail("the part's bytes are not build/kerndos.bin - they differ at "
             "offset %s of %d" % (n, len(raw)))
    print("kdpart: 4/5 those sectors expand to build/kerndos.bin EXACTLY "
          "(%d bytes)" % len(raw))

    # --- 5: the extent list is what HS_XMAX can hold --------------------------
    # The staging area the stub reads from is fixed at assembly time
    # (SPEC.md 87.5 step 2), so a part fragmented past it cannot be handed over
    # at all - and a floppy that has been written to for a year is where that
    # would first show up.
    HS_XMAX = 1280
    if len(ext) > HS_XMAX:
        fail("the part is in %d extents and the staging area holds %d"
             % (len(ext), HS_XMAX))
    print("kdpart: 5/5 %d extent(s) against the %d the staging area holds"
          % (len(ext), HS_XMAX))
    print("kdpart: ok - kern_dos is reachable as absolute sectors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
