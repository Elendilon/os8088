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

The disk is a SCRATCH image because step 1 writes to it.
"""
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import os88geom                                                # noqa: E402
import dosmap                                                  # noqa: E402
import os88marty                                               # noqa: E402
import os88mouse                                               # noqa: E402
import os88build                                               # noqa: E402
import os88ui                                                  # noqa: E402
import importlib.util                                          # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "os88dosdbg", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "tools", "os88dosdbg.py"))
dbg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dbg)

SYS = "build/os8088-360.img"
LNK = "build/doslnk360.img"
WHERE, FOLDER = [], []
FLUSHED = "build/doslnk-out.img"   # ...the guest's live copy, flushed out

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

    The offsets come from tools/os88dosdbg.py, which makes the ASSEMBLER emit
    them - nasm prints no symbols and `-f bin` writes no map, so a layout
    transcribed here would decode plausible nonsense the day a field moves.
    The image size is taken off SYS and not off the apps floppy for the same
    reason: the bss begins at os88_image_end, so it is the DOS.O88 that was
    LOADED that decides where it starts - and that one is on the system disk
    (SPEC.md 24.3), which is also the disk a knob build would change.
    """
    sym = dbg.dos_syms(["DOS_B_MEMKB", "DOS_B_MCHK", "DOS_MCHKON",
                        "DOS_B_AKB"], defines=())
    base = None
    for w in os88geom.windows(m, ui.sym):
        if w.used and w.visible and w.title.startswith("DOS"):
            raw = bytes(m.read(ui.sym("wm_wins") + w.i * os88geom.WIN_SIZE,
                               os88geom.WIN_SIZE))
            seg = struct.unpack_from("<H", raw, os88geom.W_SEG)[0]
            base = (seg << 4) + dbg.package_image_size(SYS)
            break
    if base is None:
        fail("no DOS window to read the settings out of")
    def w16(o):
        return struct.unpack("<H", bytes(m.read(base + o, 2)))[0]
    return (w16(sym["DOS_B_MEMKB"]),
            bytes(m.read(base + sym["DOS_B_MCHK"] + sym["DOS_MCHKON"], 1))[0],
            w16(sym["DOS_B_AKB"]))


def wait_ready(m, limit=120.0):
    end = time.time() + limit
    while time.time() < end:
        rows = m.screen() or []
        if any("READY" in r for r in rows):
            return "\n".join(r.rstrip() for r in rows)
        time.sleep(0.3)
    fail("the program never reached READY")


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
        mo.click(*dosmap.centre(m, pseg, dm, "dos_mchk"))   # untick the cache
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
        print("doslnk: saved, with %r, %r, a %dK limit and the cache OFF"
              % (TYPED, ENVVAR, LIMIT))

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
    if got["keep"] != 0:
        fail("the memory block says keep-the-cache %d and the box was "
             "UNTICKED" % got["keep"])

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
        if memkb != LIMIT or keep != 0:
            fail("the shortcut ran with memkb=%d keep=%d and the link carries "
                 "%d/0 - the second ExtraData block was written and not read"
                 % (memkb, keep, LIMIT))
        if akb > LIMIT:
            fail("the box claimed %dK against a %dK limit - the setting "
                 "reached [dos_memkb] and dos_run ignored it (SPEC.md 96.25.1)"
                 % (akb, LIMIT))
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
