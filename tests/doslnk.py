#!/usr/bin/env python3
"""A SHORTCUT, written and read back (SPEC.md 96.21).

A program, its arguments and its environment are a thing worth keeping, and
`.LNK` is written in Microsoft's own Shell Link layout rather than an invented
one - so the row asserts BOTH halves of that decision:

  1  os8088 can save one.  Type arguments and an environment row, press Save
     Shortcut, name it in the file dialog.
  2  THE BYTES ARE A REAL SHELL LINK.  The file is read off the floppy from
     the HOST and parsed here by an independent reader that knows nothing
     about the package: HeaderSize 0x4C, the fixed CLSID, LinkFlags with
     neither LinkTargetIDList nor LinkInfo, then three counted StringData
     entries and an ExtraData chain.  A writer that emitted a plausible file
     the format would reject is exactly what this catches, and nothing inside
     the guest could - our own reader would be equally wrong in both
     directions.
  3  os8088 reads it back.  Double-click the .LNK and the program runs with
     the arguments and the environment the link carried, not with empty ones.
  4  ...AND THE MEMORY SETTINGS, which are a SECOND ExtraData block (SPEC.md
     96.25.2).  They are the one thing in the file that changes what the
     program is HANDED rather than what it is told, so the last assertion is
     not that the bytes came back - it is that the arena the box claimed obeys
     the limit the link carried.  A setting that round-trips and is then
     ignored looks identical to one that works, from the file.
  5  THE SECOND TRY, when the disk has moved (SPEC.md 96.21.2.1).
     `WORKING_DIR` is written QUALIFIED now - `B:\BIN` - which is right until
     the floppy turns up in a different drive, so the box tries the drive the
     link NAMES and then the drive the link IS ON.  The row forges that: one
     byte of a copy of the link is patched from `B` to `A`, and the copy is
     put in the ROOT of the same floppy rather than beside the program.  So
     try 1 walks `A:\BIN`, which is the system disk and has no BIN; try 2
     walks `B:\BIN`, which does.  **THE PLACEMENT IS THE WHOLE TEST**: a link
     sitting beside its program resolves whether or not the fallback exists,
     because the folder it falls back to is the one it was already in.  From
     the root, a box with no second try looks for DOSARGS.COM in `B:\` and
     does not find it.

The disk is a SCRATCH image because step 1 writes to it.
"""
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import os88geom                                                # noqa: E402
import os88fat                                                 # noqa: E402
import dosmap                                                  # noqa: E402
import os88marty                                               # noqa: E402
import os88mouse                                               # noqa: E402
import os88build                                               # noqa: E402
import os88ui                                                  # noqa: E402
# **`os88dosdbg` IS NOT IMPORTED ANY MORE**, and the deletion is the point:
# it was here for `dos_bss` and `package_image_size`, which between them read
# the DOS box's settings at an address belonging to a package that is not on
# the disk (see `dos_state`). One map of the running package answers both.

SYS = "build/os8088-360.img"
LNK = "build/doslnk360.img"
WHERE, FOLDER = [], []
FLUSHED = "build/doslnk-out.img"   # ...the guest's live copy, flushed out
MOVED = "MOVED.LNK"                # step 5's forged copy, in the ROOT of B:
WDIR = "B:\\BIN"                    # what WORKING_DIR must say: the program is
                                   # at B:/BIN/DOSARGS.COM and the link is
                                   # written fully qualified (SPEC.md 96.21.2.1)
WDIR_OFF = 78                      # 76-byte header, then WORKING_DIR's 2-byte
                                   # count: the drive letter is the first
                                   # character of the first StringData

# **AND IT IS RESOLVED ONCE, THROUGH os88build.at, BECAUSE THREE USES OF IT
# DID NOT AGREE.** The flush wrote `os.path.abspath(FLUSHED)` - the checkout -
# while `os88ui.boot(apps=FLUSHED)` resolved the same string through
# os88build.at, which under a soak run points at the run's FROZEN TREE. So
# stage 3 booted a file nothing had written and the row died with a
# FileNotFoundError naming build/trees/plain-<hash>/, three times, having
# passed every time it was run standalone - because with no $OS88_TREE set
# `at` is the identity function and the two spellings agree.
FLUSHED_AT = os.path.abspath(os88build.at(FLUSHED))
TYPED = "/M P:220"
ENVVAR = "SOUND=SB"
LIMIT = 96                          # KB, comfortably over DOS_MIN_KB's 64 and
                                    # far under anything a machine here has, so
                                    # "the cap was applied" cannot be confused
                                    # with "the machine was small"
# os88ui.inc's radio record and the box's arms (SPEC.md 96.36).  The PITCH
# offset is the SDK's, not the box's, and the arm is what the .LNK carries -
# where the check box this replaced carried a ticked/unticked 1/0 the OTHER
# WAY UP, DOS_MEM_KEEP being 0.
RD_PITCH = 14
DOS_MEM_KEEP, DOS_MEM_DUMP = 0, 1
CLSID = bytes([0x01, 0x14, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00,
               0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46])
TITLE_H = os88geom.TITLE_H
# **NO LAYOUT CONSTANTS HERE ANY MORE.** Ten of them stood here, copied from
# apps/dos/dos.asm, and every click below was computed from them - which is
# exactly the failure docs/WRITING-TESTS.md names: SPEC.md 96.32 moved the
# arguments box and Save Shortcut onto a page of their own and this row went
# on clicking an empty part of the window, reporting it as "Save Shortcut
# opened no file dialog". dosmap.centre reads each control's real rect out of
# the guest's own bss, so a layout change moves the clicks with it.


def fail(msg):
    print("doslnk: FAIL: %s" % msg)
    sys.exit(1)


def field(text, name):
    m = re.search(r"^%s (.*?)\s*$" % name, text, re.M)
    return m.group(1) if m else None


def dos_state(m, ui):
    """[dos_memkb], [dos_keepc] and [dos_akb] out of the live instance.

    **BY SYMBOL AND NOT BY CELL ORDINAL** (SPEC.md 96.44.2): `DOS_B_MEMKB`
    used to BE the offset from `os88_image_end` and is now an offset inside
    whichever of the two blocks owns the cell.  The day the table split, this
    routine read three plausible zeroes and the row failed saying the link had
    been written and not read.

    **AND IT IS `dosmap` AND NOT `os88dosdbg.dos_bss`**, which is the second
    time the same cell has been read at the wrong address.  That route asks
    the assembler for `name - os88_image_end` and then adds the image size off
    the DOS.O88 on the system disk - two right answers about two DIFFERENT
    packages since SPEC.md 96.40.3 put the PARTED one there: it was mapping
    `dos.asm` with no defines (the box is `-DDOSKPART -DDOS_EXTCORE` now, so
    every offset past the core's reservation moves ~1,800 bytes) and adding
    the LOADER's 2,092-byte image where the box's own bss begins.  It read
    `memkb=25971 keep=116` - two characters of a string.  `dosmap.package()`
    is one map of the package that is actually running, its default is the
    shipped build (see that file), and the offsets it answers are from the
    instance's own segment with nothing to add.
    """
    want = ("dos_memkb", "dos_keepc", "dos_akb")
    dm = dosmap.package()
    base = None
    for w in os88geom.windows(m, ui.sym):
        if w.used and w.visible and w.title.startswith("DOS"):
            raw = bytes(m.read(ui.sym("wm_wins") + w.i * os88geom.WIN_SIZE,
                               os88geom.WIN_SIZE))
            seg = struct.unpack_from("<H", raw, os88geom.W_SEG)[0]
            base = seg << 4
            break
    if base is None:
        fail("no DOS window to read the settings out of")
    missing = [n for n in want if n not in dm]
    if missing:
        fail("dosmap has no %s - the box's map does not carry the cells this "
             "row is about" % ", ".join(missing))
    def w16(o):
        return struct.unpack("<H", bytes(m.read(base + o, 2)))[0]
    return (w16(dm["dos_memkb"]),
            bytes(m.read(base + dm["dos_keepc"], 1))[0],
            w16(dm["dos_akb"]))


def wait_ready(m, limit=120.0, why=None):
    end = time.time() + limit
    while time.time() < end:
        rows = m.screen() or []
        if any("READY" in r for r in rows):
            return "\n".join(r.rstrip() for r in rows)
        time.sleep(0.3)
    # **`why` NAMES THE MECHANISM, because a program that never started looks
    # the same from here whatever stopped it.** Step 5's own failure is a box
    # that found no program to run, and "never reached READY" points at the
    # program rather than at the folder it was looked for in.
    fail(why or "the program never reached READY")


def parse_lnk(b):
    """An INDEPENDENT Shell Link reader - it shares no code with the guest."""
    if len(b) < 76:
        fail("the .LNK is %d bytes; the header alone is 76" % len(b))
    if struct.unpack_from("<I", b, 0)[0] != 0x4C:
        fail("HeaderSize is %#x and the format says 0x4C - that dword IS the "
             "magic" % struct.unpack_from("<I", b, 0)[0])
    if b[4:20] != CLSID:
        fail("the LinkCLSID is %r, not {00021401-0000-0000-C000-"
             "000000000046}" % (b[4:20],))
    flags = struct.unpack_from("<I", b, 20)[0]
    if flags & 0x03:
        fail("LinkFlags %#x claims a LinkTargetIDList or a LinkInfo, and "
             "SPEC.md 96.21.1 says os8088 writes neither" % flags)
    for bit, name in ((0x10, "HasWorkingDir"), (0x08, "HasRelativePath"),
                      (0x20, "HasArguments")):
        if not flags & bit:
            fail("LinkFlags %#x is missing %s" % (flags, name))
    at = 76
    out = {}
    for name in ("workdir", "relpath", "args"):
        if at + 2 > len(b):
            fail("the file ends where %s's count should be" % name)
        n = struct.unpack_from("<H", b, at)[0]
        at += 2
        if at + n > len(b):
            fail("%s says %d characters and only %d bytes are left"
                 % (name, n, len(b) - at))
        out[name] = b[at:at + n].decode("latin1")
        at += n
    out["env"] = []
    while at + 8 <= len(b):
        size, sig = struct.unpack_from("<II", b, at)
        if size < 4:
            break
        if at + size > len(b):
            fail("an ExtraData block says %d bytes and %d are left"
                 % (size, len(b) - at))
        if sig == 0xA0088088:
            blob = b[at + 8:at + size]
            out["env"] = [v.decode("latin1")
                          for v in blob.split(b"\0") if v]
        elif sig == 0xA0088089:         # SPEC.md 96.25.2 - and its fields are
            if size < 12:               # at FIXED offsets, which is the whole
                fail("the memory block says %d bytes and the layout is 12"
                     % size)            # reason it is a block of its own
            out["memkb"], out["keep"] = struct.unpack_from("<HB", b, at + 8)
        at += size
    return out


def main():
    for p in (SYS, LNK):
        if not os.path.exists(p):
            fail("%s is missing - `make doscom` builds the gate disks" % p)

    with os88ui.boot(SYS, apps=LNK, machine="os8088_5150_herc_gla") as ui:
        m = ui.m
        if not ui.path("B:/BIN/DOSARGS.COM"):
            fail("could not launch the gate program")

        # --- 0: THE ASSOCIATION DOOR FILLS THE PATH BOX (SPEC.md 96.33.10.1) -
        # This row already came in through the door the field reported - a
        # .COM double-clicked, opening DOS.O88 by association - and asserted
        # nothing about the box, so it watched an empty field for as long as
        # it has existed.
        #
        # **THE ASSERTION IS THE FIELD'S LN_LEN AND NOT THE BUFFER**, which is
        # the whole shape of the defect: [dos_path] held a perfect
        # `B:\BIN\DOSARGS.COM` while the box drew NOTHING, because
        # dos_fld_init had left LN_LEN at 0 and dos_path_make wrote the buffer
        # without re-measuring. A check that read the buffer would have been
        # green throughout.
        # **THE MAP FIRST, THE SEGMENT SECOND** (SPEC.md 66.6.1.2).
        # `dosmap.package()` shells out to nasm, which is seconds of host time
        # with the guest free-running - and the DOS box's region MOVES now, so
        # a segment taken before that call can be stale by the time it is
        # used. It read nine bytes of machine code out of `[dos_path]`.
        _dm = dosmap.package()
        _ps = dosmap.instance(m)
        _buf = m.read((_ps << 4) + _dm["dos_path"], 40).split(b"\0")[0]
        _len = int.from_bytes(
            m.read((_ps << 4) + _dm["dos_pln"] + 12, 2), "little")
        if not _buf.upper().endswith(b"DOSARGS.COM"):
            fail("an association launch left [dos_path] = %r, and the entry "
                 "proc composes it from OSAPI_ARG_FILE (SPEC.md 96.32.3)"
                 % _buf)
        if _len != len(_buf):
            fail("the path box holds %r and its LN_LEN is %d - the field "
                 "draws LN_LEN characters, so it is %s on the glass (SPEC.md "
                 "96.33.10.1)"
                 % (_buf, _len, "EMPTY" if not _len else "truncated"))
        print("doslnk: the association door fills the path box - %r, LN_LEN %d"
              % (_buf.decode("latin-1"), _len))

        wait_ready(m)
        m.type_text("x")
        os88marty.settle(m)
        w = ui.window("DOS")
        ui.raise_window(w)
        mo = os88mouse.Mouse(marty=m)
        pseg = dosmap.instance(m)
        dm = dosmap.package()

        # --- 1: fill both, then save -----------------------------------------
        # The arguments box is behind the bar's Environment button now
        # (SPEC.md 96.32.2), so getting to it is a click on that first.
        mo.click(*dosmap.centre(m, pseg, dm, "dos_erect"))
        os88marty.settle(m)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_ln"))
        os88marty.settle(m)
        for ch in TYPED:
            m.type_text(ch)
        os88marty.settle(m)

        # **ONE PAGE HOLDS ALL FOUR NOW** (SPEC.md 96.32.2): the arguments box,
        # one environment row, the memory limit and the cache box are the Setup
        # page's two halves, so this walks controls instead of walking pages -
        # and every one of them is resolved OUT OF THE GUEST by name rather
        # than computed from a host-side copy of the layout, which is what
        # broke this row when the layout moved.
        mo.click(*dosmap.centre(m, pseg, dm, "dos_eln"))
        os88marty.settle(m)
        for ch in ENVVAR:
            m.type_text(ch)
        os88marty.settle(m)
        # The cache choice is a RADIO of three now (SPEC.md 96.36), so this
        # PICKS AN ARM rather than toggling a box - and the row is resolved
        # out of the guest's own rect and pitch, like every other control
        # here.  Arm DOS_MEM_DUMP is "take the disk cache too", which is what
        # this row used to say by unticking.
        x1, y1, x2, _ = dosmap.rect(m, pseg, dm, "dos_mrad")
        pitch = int.from_bytes(
            m.read((pseg << 4) + dm["dos_mrad"] + RD_PITCH, 2), "little")
        mo.click((x1 + x2) // 2, y1 + DOS_MEM_DUMP * pitch + pitch // 2)
        os88marty.settle(m)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_mln"))
        os88marty.settle(m)
        m.type_text(str(LIMIT))
        os88marty.settle(m)

        # ...and Save Shortcut is on this page's own bottom row, beside Return.
        # It reads the limit on the way out for dos_mem_take's reason (96.25):
        # a number typed with nothing pressed after it is still the setting.
        mo.click(*dosmap.centre(m, pseg, dm, "dos_srect"))
        os88marty.settle(m)
        if not ui.wait_window("Save", limit=30.0):
            fail("Save Shortcut opened no file dialog")
        m.key("Enter")                      # ...accept the default name
        os88marty.settle(m)
        print("doslnk: saved, with %r, %r, a %dK limit and arm %d - take the "
              "cache too" % (TYPED, ENVVAR, LIMIT, DOS_MEM_DUMP))

        # THE GUEST WRITES TO ITS OWN CLONE of the image, which is what makes
        # --marty-jobs safe - so the host's copy of the gate disk never
        # changes and reading it would report "nothing was written". flush()
        # writes the LIVE drive out.
        m.flush(drive=1, path=FLUSHED_AT)

    # --- 2: read the bytes off the floppy, with our own reader ---------------
    raw = read_lnk(FLUSHED_AT)
    print("doslnk: the file is %d bytes" % len(raw))
    got = parse_lnk(raw)
    print("doslnk: an independent Shell Link reader says %r" % (got,))
    if got["args"] != TYPED:
        fail("COMMAND_LINE_ARGUMENTS is %r and %r was typed"
             % (got["args"], TYPED))
    if not got["relpath"].startswith(".\\"):
        fail("RELATIVE_PATH is %r and Windows wants it link-relative - `.\\` "
             "is the spelling that is valid there AND parseable here"
             % got["relpath"])
    if ENVVAR not in got["env"]:
        fail("our ExtraData block carries %r, not %r" % (got["env"], ENVVAR))
    if "memkb" not in got:
        fail("there is no memory ExtraData block in the file at all - "
             "SPEC.md 96.25.2 writes one beside the environment's")
    if got["memkb"] != LIMIT:
        fail("the memory block says a %dK limit and %dK was typed"
             % (got["memkb"], LIMIT))
    if got["keep"] != DOS_MEM_DUMP:
        fail("the memory block carries arm %d and arm %d was picked "
             "(SPEC.md 96.36 - DOS_MEM_KEEP is 0 now, where the check box's "
             "ticked ON byte was 1, so the polarity is the other way up)"
             % (got["keep"], DOS_MEM_DUMP))
    # **AND WORKING_DIR CARRIES THE DRIVE** (SPEC.md 96.21.2.1).
    # OSAPI_FILE_PATH answers no drive letter by design (19.2.4), so the box
    # wrote `\BIN` and the link resolved against whichever volume it happened
    # to be READ from - right exactly as often as the shortcut and its program
    # sit on one disk, and silently wrong otherwise.
    if got["workdir"] != WDIR:
        fail("WORKING_DIR is %r and the program is at B:/BIN/DOSARGS.COM - a "
             "shortcut is written FULLY QUALIFIED (SPEC.md 96.21.2.1), so "
             "this is %s" % (got["workdir"],
                             "drive-less" if got["workdir"].startswith("\\")
                             else "the wrong folder"))
    if raw[WDIR_OFF:WDIR_OFF + len(WDIR)].decode("latin1") != WDIR:
        fail("WORKING_DIR parses as %r but is not at byte %d - the forgery "
             "below patches that byte and would silently edit something else"
             % (got["workdir"], WDIR_OFF))
    print("doslnk: WORKING_DIR is %r - qualified" % got["workdir"])

    # --- the forged copy, for step 5 ---------------------------------------
    # ONE BYTE, so every count and offset in the file is untouched: `B:\BIN`
    # becomes `A:\BIN`, which is the system disk and has no BIN on it. And it
    # goes in the ROOT rather than beside the program, which is what makes the
    # fallback observable at all - see the docstring.
    forged = bytearray(raw)
    forged[WDIR_OFF] = ord("A")
    tmp = os.path.join(os.path.dirname(FLUSHED_AT), "doslnk-moved.lnk")
    with open(tmp, "wb") as f:
        f.write(forged)
    v = os88fat.Fat12(FLUSHED_AT)
    if v.find(MOVED)[2] is not None:
        v.delete(MOVED)
    v.add(tmp, MOVED)
    v.save()
    print("doslnk: forged %s into the ROOT of B: - WORKING_DIR %r, a drive "
          "that has no BIN" % (MOVED, "A:" + WDIR[2:]))

    # --- 3: os8088 reads its own back ---------------------------------------
    with os88ui.boot(SYS, apps=FLUSHED_AT,
                     machine="os8088_5150_herc_gla") as ui:
        m = ui.m
        where = "B:/%s/%s.LNK" % (FOLDER[0], WHERE[0]) if FOLDER \
            else "B:/%s.LNK" % WHERE[0]
        print("doslnk: the shortcut landed at %s" % where)
        if not ui.path(where):
            fail("double-clicking the shortcut opened no window - the .LNK "
                 "association is dos.o88's third (SPEC.md 96.21)")
        out = wait_ready(m)
        print("doslnk: the shortcut ran:")
        for r in out.splitlines()[:8]:
            if r.strip():
                print("   | %s" % r)
        if field(out, "ARGS") != TYPED:
            fail("the shortcut ran with ARGS %r and it carries %r - the link "
                 "was opened but its arguments did not reach the PSP"
                 % (field(out, "ARGS"), TYPED))
        if ENVVAR not in (field(out, "SET") or "").split("|"):
            fail("the shortcut ran without %r in its environment; the set is "
                 "%r" % (ENVVAR, field(out, "SET")))
        # **AND IT CARRIES THE DRIVE** (SPEC.md 96.19.3.1): DOS's program path
        # is fully qualified, this box wrote it drive-less, and a program that
        # reads its own path to find its FILES then has no drive to look on.
        if field(out, "MYPATH") != "B:\\BIN\\DOSARGS.COM":
            fail("the program thinks it is %r - a shortcut must make the "
                 "instance BECOME its target, drive, path and name (SPEC.md "
                 "96.21.2, 96.19.3.1)" % field(out, "MYPATH"))

        # --- 4: ...AND THE SETTINGS WERE OBEYED, not merely carried ---------
        # The bss is read from OUTSIDE because no DOS program can report what
        # the box decided before it was loaded, and because the three numbers
        # have to agree: what the link said, what the box believes, and what it
        # actually claimed. A limit that round-trips and is then ignored looks
        # identical to one that works, from the file alone.
        memkb, keep, akb = dos_state(m, ui)
        print("doslnk: the relaunched box has memkb=%d keep=%d, arena %dK"
              % (memkb, keep, akb))
        if memkb != LIMIT or keep != DOS_MEM_DUMP:
            fail("the shortcut ran with memkb=%d arm=%d and the link carries "
                 "%d/%d - the second ExtraData block was written and not read"
                 % (memkb, keep, LIMIT, DOS_MEM_DUMP))
        if akb > LIMIT:
            fail("the box claimed %dK against a %dK limit - the setting "
                 "reached [dos_memkb] and dos_run ignored it (SPEC.md 96.25.1)"
                 % (akb, LIMIT))
        m.type_text("x")

    # --- 5: THE SECOND TRY, when the disk has moved (SPEC.md 96.21.2.1) -----
    # A fresh boot, because this is a second double-click from the desktop and
    # a second box on the same screen would make `wait_ready` ambiguous about
    # which console it is reading.
    with os88ui.boot(SYS, apps=FLUSHED_AT,
                     machine="os8088_5150_herc_gla") as ui:
        m = ui.m
        if not ui.path("B:/" + MOVED):
            fail("double-clicking B:/%s opened no window" % MOVED)
        out = wait_ready(m, why=(
            "a shortcut naming A:\\BIN, sitting in the ROOT of B:, started no "
            "program at all. The drive it NAMES is not there, so the second "
            "try is the drive it IS ON - B: - with the same path (SPEC.md "
            "96.21.2.1). Without that try the box keeps the link's own "
            "folder, which is B:\\ here, and DOSARGS.COM is not in it"))
        if field(out, "ARGS") != TYPED:
            fail("the moved shortcut ran with ARGS %r and it carries %r"
                 % (field(out, "ARGS"), TYPED))
        if field(out, "MYPATH") != "B:\\BIN\\DOSARGS.COM":
            fail("a shortcut naming A:\\BIN, sitting in the ROOT of B:, made "
                 "the box become %r. The drive it NAMES is not there, so the "
                 "second try is the drive it IS ON - B: - with the same path "
                 "(SPEC.md 96.21.2.1). Without that try the box keeps the "
                 "link's own folder, which is B:\\ here, and DOSARGS.COM is "
                 "not in it" % field(out, "MYPATH"))
        print("doslnk: the moved shortcut ran from %s - the second try found "
              "it on the drive the link was on" % field(out, "MYPATH"))
        m.type_text("x")

    print("doslnk: ok")
    return 0


def read_lnk(img):
    """The .LNK on the image, straight off the FAT - geometry from the BPB.

    THE BPB AND NOT CONSTANTS: a 360KB volume is 2 sectors to a CLUSTER, and
    assuming 1 finds the right directory entry and then reads the wrong half
    of the disk - which presents as a file of the right SIZE full of the
    wrong bytes, and reads exactly like a writer that emitted rubbish.
    """
    with open(img, "rb") as f:
        data = f.read()
    secsz = struct.unpack_from("<H", data, 0x0B)[0]
    spc = data[0x0D]
    resv = struct.unpack_from("<H", data, 0x0E)[0]
    nfat = data[0x10]
    nroot = struct.unpack_from("<H", data, 0x11)[0]
    spf = struct.unpack_from("<H", data, 0x16)[0]
    root = (resv + nfat * spf) * secsz
    rootsz = nroot * 32
    datastart = root + rootsz

    def at_of(clus):
        return datastart + (clus - 2) * spc * secsz

    def scan(base, nbytes, depth=0):
        for off in range(base, base + nbytes, 32):
            ent = data[off:off + 32]
            if len(ent) < 32 or ent[0] in (0x00, 0xE5):
                continue
            clus = struct.unpack_from("<H", ent, 26)[0]
            if ent[8:11] == b"LNK":
                size = struct.unpack_from("<I", ent, 28)[0]
                WHERE.append(ent[:8].decode("latin1").strip())
                return data[at_of(clus):at_of(clus) + size]
            if ent[11] & 0x10 and ent[0] != ord(".") and clus >= 2 and depth < 3:
                here = ent[:8].decode("latin1").strip()
                got = scan(at_of(clus), spc * secsz, depth + 1)
                if got:
                    FOLDER.append(here)
                    return got
        return None

    got = scan(root, rootsz)         # the root, then the folders under it: the
    if got:                          # dialog defaults to where the INSTANCE
        return got                   # stands, which is BIN and not the root
    fail("no .LNK anywhere on %s - Save Shortcut wrote nothing" % img)


if __name__ == "__main__":
    sys.exit(main())
