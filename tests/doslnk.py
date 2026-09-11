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

The disk is a SCRATCH image because step 1 writes to it.
"""
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import os88geom                                                # noqa: E402
import os88marty                                               # noqa: E402
import os88mouse                                               # noqa: E402
import os88ui                                                  # noqa: E402

SYS = "build/os8088-360.img"
LNK = "build/doslnk360.img"
WHERE, FOLDER = [], []
FLUSHED = "build/doslnk-out.img"   # ...the guest's live copy, flushed out
TYPED = "/M P:220"
ENVVAR = "SOUND=SB"
CLSID = bytes([0x01, 0x14, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00,
               0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46])
TITLE_H = os88geom.TITLE_H
DOS_FLDW, DOS_BTNW, DOS_SAVW, DOS_BTNY, DOS_EROWY, DOS_FLDY = 256, 104, 112, 90, 24, 64


def fail(msg):
    print("doslnk: FAIL: %s" % msg)
    sys.exit(1)


def field(text, name):
    m = re.search(r"^%s (.*?)\s*$" % name, text, re.M)
    return m.group(1) if m else None


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
        ctop = w.y + TITLE_H
        mo = os88mouse.Mouse(marty=m)

        # --- 1: fill both, then save -----------------------------------------
        mo.click(w.x + 8 + 100, ctop + DOS_FLDY + 6)
        os88marty.settle(m)
        for ch in TYPED:
            m.type_text(ch)
        mo.click(w.x + 8 + DOS_FLDW - DOS_BTNW // 2, ctop + DOS_BTNY + 7)
        os88marty.settle(m)
        mo.click(w.x + 8 + 60, ctop + DOS_EROWY + 6)
        os88marty.settle(m)
        for ch in ENVVAR:
            m.type_text(ch)
        mo.click(w.x + 8 + DOS_FLDW - DOS_BTNW // 2, ctop + DOS_BTNY + 7)
        os88marty.settle(m)

        mo.click(w.x + 8 + DOS_SAVW // 2, ctop + DOS_BTNY + 7)
        os88marty.settle(m)
        if not ui.wait_window("Save", limit=30.0):
            fail("Save Shortcut opened no file dialog")
        m.key("Enter")                      # ...accept the default name
        os88marty.settle(m)
        print("doslnk: saved, with %r and %r" % (TYPED, ENVVAR))

        # THE GUEST WRITES TO ITS OWN CLONE of the image, which is what makes
        # --marty-jobs safe - so the host's copy of the gate disk never
        # changes and reading it would report "nothing was written". flush()
        # writes the LIVE drive out.
        m.flush(drive=1, path=os.path.abspath(FLUSHED))

    # --- 2: read the bytes off the floppy, with our own reader ---------------
    raw = read_lnk(FLUSHED)
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

    # --- 3: os8088 reads its own back ---------------------------------------
    with os88ui.boot(SYS, apps=FLUSHED, machine="os8088_5150_herc_gla") as ui:
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
        if field(out, "MYPATH") != "\\BIN\\DOSARGS.COM":
            fail("the program thinks it is %r - a shortcut must make the "
                 "instance BECOME its target, name and all (SPEC.md 96.21.2)"
                 % field(out, "MYPATH"))
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
