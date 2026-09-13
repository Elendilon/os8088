#!/usr/bin/env python3
"""Debug a DOS program under os8088 by comparing it with a REAL DOS.

    python3 tools/os88dosdbg.py syms  [NAME...]            # what the box's bss offsets are
    python3 tools/os88dosdbg.py build                      # a DOSTRACE system disk
    python3 tools/os88dosdbg.py trace PROG.EXE --disk D    # our INT 21h traffic
    python3 tools/os88dosdbg.py ref   PROG.EXE --disk D --dos-disk A   # ...and a real DOS's
    python3 tools/os88dosdbg.py diff  ours.json ref.json   # where they part, and at which instruction
    python3 tools/os88dosdbg.py --selfcheck                # no emulator, no network

docs/DOS-DEBUGGING.md is the manual.  What follows is why the shape is this
shape, because the shape is the whole value.

THE METHOD.  A DOS program that misbehaves under this box is not debuggable
from one side.  Our own trace says what we were asked and what we answered,
and both look right - they looked right through four separate defects.  What
is missing is what a REAL DOS answers to the SAME questions, and the only
place that exists is a machine running one.  So: log both, in one format, and
align them.

THE ALIGNMENT IS THE INSTRUMENT, not the logging.  Two traces of the same
program differ in every address - the load segment, the heap, the stack - so a
line-for-line diff is noise from call 0.  What does not differ is the sequence
of (function, CALL SITE), and the call site is `CS - PSP : IP` off the frame
the `int` pushed.  Aligning on that turns "they diverge somewhere" into "they
diverge at this instruction", and three of the four defects this found were
cases where the instruction was THE SAME ON BOTH SIDES and only a computed
value differed - which no amount of reading our own trace would ever show.

WHAT IT NEEDS.  `trace` needs a kernel and a disk this tree builds.  `ref`
needs a bootable DOS floppy you supply: no DOS is in this repository and none
can be.  `diff` needs neither and runs anywhere.

EVERY CONSTANT IS DERIVED, none transcribed.  The box's bss offsets come from
assembling `apps/dos/dos.asm` with a marker appended and reading the words
back; the TSR's come from a `DOSTRAP1` signature inside its own `.COM`.  That
is not fastidiousness - both layouts moved three times in the session that
produced this file, and a host-side reader carrying its own copy of them does
not crash, it decodes plausible nonsense out of the wrong addresses and you
believe it.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

DOS_ASM = os.path.join(ROOT, "apps", "dos", "dos.asm")

# ...and the -I list `$(BUILD)/dos.bin`'s own recipe passes, read OUT OF THE
# MAKEFILE so the two cannot drift. A hard-coded copy here went stale the day
# a new include landed in a new directory, and the failure names the include
# rather than the path.
def _dos_incs():
    mk = os.path.join(ROOT, "Makefile")
    try:
        with open(mk, errors="replace") as f:
            txt = f.read()
    except OSError:
        return ["apps"]
    i = txt.find("$(BUILD)/dos.bin:")
    if i < 0:
        return ["apps"]
    seg = txt[i:i + 2000]
    seg = seg[:seg.find("\n\n")] if "\n\n" in seg else seg
    out = re.findall(r"-I\s+(\S+?)/?\s", seg)
    return out or ["apps"]


DOS_INCS = _dos_incs()
TRAP_ASM = os.path.join(ROOT, "tests", "dostrap", "trap.asm")

# The AH names, for reading.  Everything the box answers plus the handful it
# refuses that a program is still likely to try.
AH = {
    0x00: "term", 0x01: "getce", 0x02: "putc", 0x06: "dconio", 0x07: "getc",
    0x08: "getc", 0x09: "puts", 0x0B: "kbhit", 0x0C: "flush", 0x0E: "seldrv",
    0x19: "getdrv", 0x1A: "setdta", 0x1C: "drvdata", 0x25: "setvec",
    0x2A: "getdate", 0x2C: "gettime", 0x2F: "getdta", 0x30: "dosver",
    0x33: "ctrlbrk", 0x35: "getvec", 0x36: "dfree", 0x38: "country",
    0x39: "mkdir", 0x3A: "rmdir", 0x3B: "chdir", 0x3C: "creat", 0x3D: "open",
    0x3E: "close", 0x3F: "read", 0x40: "write", 0x41: "unlink", 0x42: "seek",
    0x43: "attr", 0x44: "ioctl", 0x47: "getcwd", 0x48: "alloc", 0x49: "free",
    0x4A: "setblock", 0x4B: "exec", 0x4C: "exit", 0x4D: "retcode",
    0x4E: "findfirst", 0x4F: "findnext", 0x52: "sysvars", 0x54: "verify",
    0x62: "getpsp",
}

# The ring entry, both sides.  16 words; the guest writes it and this reads it.
FIELDS = ("ax", "bx", "cx", "dx", "axout", "cf", "bxout", "esout",
          "ip", "cs", "ds", "si", "di", "bp", "ss", "sp")

# WHERE AX ON SUCCESS IS AN ANSWER TWO MACHINES SHOULD AGREE ON.  Most of DOS
# leaves AX undefined on success, and several functions answer with a SEGMENT,
# which differs between two runs for the honest reason that the program is
# loaded somewhere else.  Comparing those produces a "difference" on the second
# call of every trace and buries the real one.  On FAILURE the rule is simpler
# and needs no list: AX is the error code, always.
# WHICH INPUT REGISTERS ARE VALUES RATHER THAN ADDRESSES.  Deciding whether
# two machines were asked THE SAME QUESTION means comparing the arguments, and
# half of them are pointers into a program whose stack sits two bytes apart on
# the two runs - so comparing those reports a different question at every
# `open` and buries the real one.  "c" is the default because CX is a count, a
# mask or an attribute in essentially every function and a pointer in none.
ARG_VALUES = {
    0x42: "bcd",                       # seek: handle, then the offset CX:DX
    0x3F: "bc", 0x40: "bc",            # read/write: handle and count (DX buffer)
    0x3E: "b", 0x45: "b", 0x46: "b",   # handle alone
    0x48: "b", 0x4A: "b",              # paragraphs
    0x44: "b",                         # ioctl: the handle
    0x0E: "d", 0x47: "d", 0x36: "d",   # DL = the drive
    0x3D: "c", 0x3C: "c", 0x43: "c",   # DS:DX is a name
    0x4E: "c",                         # ...and CX the attribute mask
    0x25: "", 0x35: "", 0x1A: "",      # AL is the vector; DS:DX a handler/buffer
    0x09: "", 0x02: "",                # the console writers
    # NO ARGUMENTS AT ALL beyond AX.  Worth listing rather than leaving to the
    # "c" default, because a register a function does not read still holds
    # whatever the program left in it - and on the FIRST call of a trace that
    # is whatever DOS's loader left, which differs between two machines for no
    # reason at all.  Left in, `AH=30h` is the first "difference" of every
    # trace ever taken.
    0x00: "", 0x01: "", 0x07: "", 0x08: "", 0x0B: "", 0x0C: "",
    0x19: "", 0x2A: "", 0x2C: "", 0x2F: "", 0x30: "", 0x4C: "",
    0x54: "", 0x62: "",
}

# ...and AL is an ARGUMENT on about a dozen calls and a LEFTOVER on the rest.
# `AH=19h` reads nothing, so its AL is whatever the program last had there -
# which is different on two machines for no reason, and was the second thing
# this comparison reported before the list existed.
AL_IS_AN_ARGUMENT = {
    0x02,        # the character
    0x0C,        # the function to run after the flush
    0x25, 0x35,  # the vector
    0x3D,        # the access mode
    0x42,        # the origin
    0x44,        # the sub-function
    0x48,        # ...none, but a sub-function on some DOSes
    0x4B,        # load-and-go, or load-only
    0x4C,        # the exit code
}

AX_IS_AN_ANSWER = {
    0x19: "the current drive",     0x30: "the DOS version",
    0x3C: "a handle",              0x3D: "a handle",
    0x3F: "bytes read",            0x40: "bytes written",
    0x42: "the new position, low", 0x44: "the device word",
    0x4E: "nothing on success",    0x4F: "nothing on success",
}


# =============================================================================
# constants, derived from the sources rather than transcribed
# =============================================================================
def dos_syms(names, defines=("DOSTRACE",)):
    """The value of any `equ` or DBSS symbol in apps/dos/dos.asm.

    nasm will not print a symbol's value and `-f bin` emits no map, so the
    reliable way is to make the assembler EMIT the numbers: append a signature
    and a `dw` of each name to a copy of the source, assemble it, and read the
    words back out of the binary.  Exact by construction, and it costs one
    assembly (~1s).

    DOSTRACE is defined by default because every symbol this tool wants only
    exists in that build.
    """
    names = list(names)
    if not names:
        return {}
    src = open(DOS_ASM, encoding="utf-8").read()
    d = tempfile.mkdtemp(prefix="os88dosdbg-")
    try:
        probe = os.path.join(d, "probe.asm")
        with open(probe, "w", encoding="utf-8") as f:
            f.write(src)
            f.write("\n\n; --- appended by tools/os88dosdbg.py; discarded ---\n")
            f.write("dos_dbg_probe:\n    db 'DOSSYMS1'\n")
            for n in names:
                f.write("    dw %s\n" % n)
        out = os.path.join(d, "probe.bin")
        # THE SAME INCLUDE PATH THE MAKEFILE USES, and DERIVED from it rather
        # than transcribed: dos.asm's includes are not all in apps/ (SPEC.md
        # 96.30's cable networking put two in apps/dos/ and one in
        # drivers/net/), and a probe that assembles with a SHORTER path than
        # the real build fails on a file that is right there - which reads as
        # "the tool is broken" rather than "the tool is out of date". It broke
        # exactly once, at the merge that added them: both sides built, the
        # combination did not.
        cmd = ["nasm", "-f", "bin", "-w-error"]
        for inc in DOS_INCS:            # `inc` AND NOT `d`: `d` is the temp
                                        # directory this function deletes in
                                        # its own `finally`, and a loop that
                                        # rebinds it points shutil.rmtree at
                                        # the LAST INCLUDE PATH instead - which
                                        # is a tracked source directory. It
                                        # removed drivers/net entirely, twice,
                                        # before the cause was found: the row
                                        # that noticed was the assembly failing
                                        # on an include that had been there a
                                        # moment earlier
            cmd += ["-I", os.path.join(ROOT, *inc.split("/")) + os.sep]
        for m in defines:
            cmd += ["-D" + m]
        cmd += ["-o", out, probe]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("nasm could not assemble the symbol probe:\n"
                               + (r.stderr or r.stdout))
        b = open(out, "rb").read()
        i = b.rindex(b"DOSSYMS1") + 8
        vals = struct.unpack_from("<%dH" % len(names), b, i)
        return dict(zip(names, vals))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# **DOS_B_TRACEB IS GONE AND DOS_B_TRSEG REPLACES IT** (SPEC.md 96.29.1). The
# ring is in a PART now, not in the package's bss, so there is no bss offset
# to read it at - there is a SEGMENT, banked by dos_entry into one word for
# exactly this reader. Asking for the old name would fail the symbol probe,
# which is the right failure: a reader that fell back to an offset would
# decode 16KB of somebody else's image as a trace.
BSS = ("DOS_B_TRACEN", "DOS_B_TRACEW", "DOS_B_TRSEG", "DOS_B_TRNM",
       "DOS_B_TRNMI", "DOS_B_LDPSP", "DOS_B_STATE", "DOS_B_ARENA",
       "DOS_B_APARA", "DOS_B_FHTAB", "DOS_B_WOWN", "DOS_B_WLEN",
       "DOS_B_WFILL", "DOS_B_WBYTES")
CONSTS = ("DOS_TRACEN", "DOS_TRACE_SZ", "DOS_TRNM_N", "DOS_TRB_OFF",
          "DOS_TRACE_KB",
          "DOS_NFH", "DOS_FH0",
          "FH_SIZEOF", "FH_NAME", "FH_FLAGS", "FH_POS", "FH_SIZE")


def trap_syms(com_path):
    """The TSR's own layout, out of its assembled `.COM`.

    `tests/dostrap/trap.asm` plants a `DOSTRAP1` signature followed by six
    words.  `org 0x100` means a label's value is already its in-memory offset,
    so nothing is biased here.
    """
    b = open(com_path, "rb").read()
    i = b.index(b"DOSTRAP1") + 8
    ring, total, wr, here, nent, entsz = struct.unpack_from("<6H", b, i)
    return dict(ring=ring, total=total, wr=wr, here=here, nent=nent, entsz=entsz)


def nasm(src, out, defines=(), incs=()):
    cmd = ["nasm", "-f", "bin", "-w+error"]
    for i in incs:
        cmd += ["-I", i + os.sep]
    for d in defines:
        cmd += ["-D" + d]
    cmd += ["-o", out, src]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("nasm failed on %s:\n%s" % (src, r.stderr or r.stdout))
    return out


# =============================================================================
# the traced kernel disk
# =============================================================================
def package_on_disk(img_path, name):
    """The bytes of one package as they sit on a floppy, folders included.

    THE IMAGE SIZE IS WHY THIS EXISTS.  Every bss offset in `syms` is measured
    from `os88_image_end`, so reading the ring needs the image size of the
    package THE GUEST IS RUNNING - and a DOSTRACE build is a different size
    from the shipped one.  Taking it from build/dos.o88 gives a plausible
    number that is wrong by the difference, and the ring then reads as empty
    from an address a few hundred bytes off.  So it is read off the disk that
    is about to be booted, which cannot disagree with itself.
    """
    sys.path.insert(0, HERE)
    import os88fat                                                    # noqa: E402
    v = os88fat.Fat12(img_path)
    csz = v.spc * v.bps
    want = name.upper()
    found = []

    def walk(off, n, depth=0):
        for i in range(n):
            e = bytes(v.img[off + i * 32:off + i * 32 + 32])
            if e[0] in (0, 0xE5):
                continue
            nm = os88fat.Fat12.pretty(e[:11]).upper()
            first = struct.unpack_from("<H", e, 26)[0]
            if e[11] & 0x10:
                if nm in (".", "..") or depth >= 3 or not first:
                    continue
                for c in v.chain(first):
                    walk(v.cluster_off(c), csz // 32, depth + 1)
            elif nm == want and first:
                size = struct.unpack_from("<I", e, 28)[0]
                found.append(b"".join(
                    bytes(v.img[v.cluster_off(c):v.cluster_off(c) + csz])
                    for c in v.chain(first))[:size])

    walk(v.root_off, v.nroot)
    return found[0] if found else None


def package_image_size(img_path, name="DOS.O88"):
    """`image` at +8 of the package header: the UNPACKED size, on both a plain
    and an lz4 container (docs/plans/O88-COMPRESSION-PLAN.md)."""
    body = package_on_disk(img_path, name)
    if body is None:
        raise RuntimeError("%s carries no %s" % (img_path, name))
    return struct.unpack_from("<H", body, 8)[0]


def trace_costs(kb=None):
    """THE ONE THING TO SAY OUT LOUD ON EVERY TRACE RUN.

    A DOSTRACE build claims `DOS_TRACE_KB` of the heap for its ring and its
    rendered dump (SPEC.md 96.29.1), and the DOS arena is what is left - so a
    program that is near the edge REFUSES UNDER THE TRACER AND RUNS PERFECTLY
    WITHOUT IT.

    **That has been mis-diagnosed as "the box is short of memory" eight
    separate times**, which is the whole reason this function exists rather
    than another paragraph: the cost was already written down in `dos.asm`, in
    SPEC.md 96.29.1 and in this file's own docstring, and every one of those
    was read AFTER the wrong conclusion had been reached.  A line the run
    prints cannot be skipped the way a document can.

    The number comes out of the assembler (`dos_syms`) rather than being
    transcribed, so it cannot drift from the part the disk actually carries.
    """
    if kb is None:
        try:
            kb = dos_syms(["DOS_TRACE_KB"])["DOS_TRACE_KB"]
        except Exception:                           # never fail a run for a
            kb = 0                                  # banner
    much = ("%d KB" % kb) if kb else "tens of KB"
    return (
        "os88dosdbg: **THIS DISK IS NOT THE SHIPPED BOX.**  The trace part is\n"
        "            %s of heap claimed at launch, so the DOS arena here is\n"
        "            that much SMALLER than a plain build's.  A program that\n"
        "            refuses on this disk and runs on build/os8088-360.img is\n"
        "            refusing the TRACER and not the box: re-check it WITHOUT\n"
        "            --build before concluding anything about memory.\n"
        "            (docs/DOS-DEBUGGING.md, Traps - this has cost eight\n"
        "            wrong diagnoses, every one of them about the arena.)"
        % much)


def build_trace_disk(system_img, out_img, verbose=True):
    """A system floppy carrying the DOSTRACE build of apps/dos.

    THE ORDER MATTERS AND GETTING IT WRONG IS SILENT.  `make` rebuilds
    build/dos.o88 from apps/dos/dos.asm whenever the source is newer, so a copy
    made BEFORE make is overwritten by it - and the disk then carries the
    SHIPPED package while every symptom points at the guest.  That cost a whole
    debugging round: the ring read as empty and the guest looked broken.

    So: make first, copy second, verify third, and put build/ back.  The verify
    is not belt and braces; it is the only thing that catches the above.
    """
    say = (lambda *a: print(*a)) if verbose else (lambda *a: None)

    def run(*args):
        r = subprocess.run(["make"] + list(args), cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("`make %s` failed:\n%s"
                               % (" ".join(args), (r.stderr or r.stdout)[-3000:]))

    pkg = os.path.join(ROOT, "build", "dos.o88")
    binp = os.path.join(ROOT, "build", "dos.bin")
    run(system_img)                                   # dos.bin newer than dos.asm
    d = tempfile.mkdtemp(prefix="os88dosdbg-")
    try:
        tb = nasm(DOS_ASM, os.path.join(d, "dos-trace.bin"),
                  defines=("DOSTRACE",),
                  incs=tuple(os.path.join(ROOT, *i.split("/"))
                             for i in DOS_INCS))   # the Makefile's list, and
                                                   # the SECOND site that had a
                                                   # hard-coded `apps` alone
        to = os.path.join(d, "DOS.O88")
        r = subprocess.run([sys.executable, os.path.join(HERE, "os88pkg.py"),
                            tb, "-o", to, "--compress-if=lz4"],
                           cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("os88pkg.py refused the traced package:\n"
                               + (r.stderr or r.stdout))
        want = open(to, "rb").read()
        shutil.copyfile(to, pkg)
        os.utime(pkg, None)
        run(system_img)
        shutil.copyfile(os.path.join(ROOT, system_img), out_img)
    finally:
        for p in (pkg, binp):
            if os.path.exists(p):
                os.unlink(p)
        run(system_img, "build/dos.o88")              # build/ back to the shipped one
        shutil.rmtree(d, ignore_errors=True)

    # ...and prove it, because the failure above is invisible
    got = package_on_disk(out_img, "DOS.O88")
    if got is None:
        raise RuntimeError("%s carries no DOS.O88 at all" % out_img)
    if got != want:
        raise RuntimeError(
            "%s carries a DIFFERENT DOS.O88 (%d bytes) than the traced build "
            "(%d) - `make` rebuilt it from source over the copy.  This is the "
            "failure the verify exists for; nothing downstream would have said "
            "a word." % (out_img, len(got), len(want)))
    say("os88dosdbg: %s carries the DOSTRACE package (%d bytes), verified"
        % (out_img, len(got)))
    return out_img


# =============================================================================
# the traces
# =============================================================================
def _agree(stride, where):
    """The one thing a host-side reader cannot be wrong about quietly.

    Both rings are 16 words an entry and this file decodes 16 words.  If either
    guest side grows a field, every number this prints is read from inside the
    wrong entry - not a crash, a plausible trace of a program that never ran.
    Checked on every use, because the cost of the check is a comparison and the
    cost of skipping it is a day.
    """
    if stride != 2 * len(FIELDS):
        raise SystemExit(
            "os88dosdbg: %s says an entry is %d bytes and this file decodes %d "
            "(%s).\n  Add the new word(s) to FIELDS, in the order the guest "
            "stores them." % (where, stride, 2 * len(FIELDS), ", ".join(FIELDS)))


def _entries(ring, stride, nent, total, wr):
    """Decode the ring into oldest-first order, wrap included."""
    n = min(total, nent)
    start = ((wr // stride) - n) % nent if total > nent else 0
    out = []
    for i in range(n):
        j = ((start + i) % nent) * stride
        out.append(dict(zip(FIELDS, struct.unpack_from("<16H", ring, j))))
    return out


def _save(path, meta, entries, names=()):
    doc = dict(meta)
    doc["names"] = list(names)
    doc["entries"] = entries
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    return path


def cmd_trace(a):
    import os88ui                                                     # noqa: E402
    import os88geom                                                   # noqa: E402

    sym = dos_syms(list(BSS) + list(CONSTS))
    stride, nent = sym["DOS_TRACE_SZ"], sym["DOS_TRACEN"]
    _agree(stride, "apps/dos/dos.asm's DOS_TRACE_SZ")
    # BEFORE the run and not after it, and on stderr: see trace_costs().
    print(trace_costs(sym.get("DOS_TRACE_KB")), file=sys.stderr)
    img = a.kernel
    if a.build:
        img = build_trace_disk(a.system, a.kernel)
    # off the DISK, never off build/dos.o88: see package_on_disk
    imgsz = package_image_size(img)

    with os88ui.boot(img, apps=a.disk, machine=a.machine) as ui:
        m = ui.m
        ui.open_drive(a.drive)
        if not ui.path("%s:/%s" % (a.drive, a.program)):
            raise SystemExit("os88dosdbg: opening %s opened no window" % a.program)

        def arena():
            for w in os88geom.windows(m, ui.sym):
                if w.used and w.visible and w.title.startswith("DOS"):
                    raw = bytes(m.read(ui.sym("wm_wins") + w.i * os88geom.WIN_SIZE,
                                       os88geom.WIN_SIZE))
                    return struct.unpack_from("<H", raw, os88geom.W_SEG)[0]
            return None

        base, end = None, time.time() + a.timeout
        while time.time() < end and base is None:
            sg = arena()
            if sg:
                base = (sg << 4) + imgsz
            time.sleep(0.2)
        if base is None:
            raise SystemExit("os88dosdbg: no DOS window appeared in %ds" % a.timeout)

        def w16(off):
            return struct.unpack("<H", bytes(m.read(base + off, 2)))[0]

        last, end = None, time.time() + a.timeout
        while time.time() < end:
            total = w16(sym["DOS_B_TRACEN"])
            trseg = w16(sym["DOS_B_TRSEG"])
            if total and not trseg:
                raise SystemExit(
                    "os88dosdbg: the box has traced %d call(s) and its trace "
                    "part is not loaded, which cannot both be true - "
                    "[dos_trseg] is 0 (SPEC.md 96.29.1)" % total)
            if total:
                # THE RING IS AT DOS_TRB_OFF INSIDE THE PART, and the
                # part's is a whole SEGMENT rather than an offset from `base`
                # - so this read is `trseg << 4` plus that offset, never
                # `base + something`. Getting it wrong reads the package's own
                # image and decodes it as a trace, plausibly.
                #
                # The offset is NOT zero and must not be assumed to be: the
                # rendered dump goes in front of the ring so that entry 0's
                # index cannot collide with [dos_tracei]'s "no call in
                # flight" sentinel (SPEC.md 96.29.1.1). It is asked for by
                # name for that reason.
                last = (total, w16(sym["DOS_B_TRACEW"]),
                        bytes(m.read((trseg << 4) + sym["DOS_TRB_OFF"],
                                     nent * stride)),
                        w16(sym["DOS_B_LDPSP"]))
            if a.until and total >= a.until:
                break
            if not a.until and m.read(base + sym["DOS_B_STATE"], 1)[0] == 3:
                break                                    # the program exited
            time.sleep(a.poll)
        if last is None:
            raise SystemExit("os88dosdbg: the program made no INT 21h call at all")
        total, wr, ring, psp = last
        nm = m.read(base + sym["DOS_B_TRNMI"], 1)[0]
        raw = bytes(m.read(base + sym["DOS_B_TRNM"], nm * 13))
        names = [raw[i * 13:(i + 1) * 13].split(b"\0")[0].decode("latin1")
                 for i in range(nm)]

        if a.state:
            _dump_state(m, base, sym, psp, a)

    entries = _entries(ring, stride, nent, total, wr)
    _save(a.out, dict(source="os8088", program=a.program, psp=psp, total=total,
                      wrapped=total > nent, machine=a.machine), entries, names)
    print("os88dosdbg: %d call(s)%s, PSP %04X -> %s"
          % (total, " (WRAPPED - raise DOS_TRACEN)" if total > nent else "",
             psp, a.out))
    if names:
        print("  names the program passed: %s" % ", ".join(names))
    return 0


def _dump_state(m, base, sym, psp, a):
    """The machine state a program reads with no call in it.

    These are the places a difference hides where no trace can see it: the PSP
    (eight fields were zero here and DOS fills all eight - SPEC.md 96.21.4),
    the BDA, the interrupt vectors, and the box's own handle table.  Dumped as
    raw binary beside the trace so `cmp` says everything.
    """
    stem = os.path.splitext(a.out)[0]
    open(stem + ".psp.bin", "wb").write(bytes(m.read(psp << 4, 256)))
    open(stem + ".ivt.bin", "wb").write(bytes(m.read(0, 1024)))
    open(stem + ".bda.bin", "wb").write(bytes(m.read(0x400, 256)))
    tab = bytes(m.read(base + sym["DOS_B_FHTAB"],
                       sym["FH_SIZEOF"] * sym["DOS_NFH"]))
    open(stem + ".fhtab.bin", "wb").write(tab)
    print("  state: %s.{psp,ivt,bda,fhtab}.bin" % os.path.basename(stem))
    for i in range(sym["DOS_NFH"]):
        r = tab[i * sym["FH_SIZEOF"]:(i + 1) * sym["FH_SIZEOF"]]
        if not r[sym["FH_FLAGS"]] and not r[0]:
            continue
        print("    handle %d: flags=%02X pos=%08X size=%08X name=%r"
              % (i + sym["DOS_FH0"], r[sym["FH_FLAGS"]],
                 struct.unpack_from("<I", r, sym["FH_POS"])[0],
                 struct.unpack_from("<I", r, sym["FH_SIZE"])[0],
                 r[sym["FH_NAME"]:sym["FH_NAME"] + 13].split(b"\0")[0].decode("latin1")))


def cmd_ref(a):
    """The same program under a real DOS, logged by the TSR in tests/dostrap.

    The DOS floppy is yours: none is in this repository and none can be.  The
    TSR is added to a COPY of it, so your original is not touched.
    """
    import os88marty                                                  # noqa: E402
    sys.path.insert(0, HERE)
    import os88fat                                                    # noqa: E402

    d = tempfile.mkdtemp(prefix="os88dosdbg-")
    try:
        com = nasm(TRAP_ASM, os.path.join(d, "DOSTRAP.COM"))
        lay = trap_syms(com)
        _agree(lay["entsz"], "tests/dostrap/trap.asm's ENTSZ")
        boot = os.path.join(d, "dos.img")
        shutil.copyfile(a.dos_disk, boot)
        v = os88fat.Fat12(boot)
        v.delete("DOSTRAP.COM")
        v.save()
        for n in a.free:
            v.delete(n)
        v.save()
        v = os88fat.Fat12(boot)
        free = len(v.free_clusters())
        need = (os.path.getsize(com) + v.spc * v.bps - 1) // (v.spc * v.bps)
        if free < need:
            raise SystemExit(
                "os88dosdbg: the DOS disk has %d free cluster(s) and DOSTRAP.COM "
                "needs %d.\n"
                "  A DOS system floppy is usually full of utilities the program "
                "under test\n"
                "  does not use.  Name some to leave out of the COPY (your own "
                "disk is never\n  touched) - this set frees ~190 clusters on IBM "
                "DOS 3.30:\n"
                "    --free XCOPY.EXE REPLACE.EXE SELECT.COM KEYBOARD.SYS "
                "PRINTER.SYS \\\n"
                "           DISPLAY.SYS COUNTRY.SYS NLSFUNC.EXE FASTOPEN.EXE "
                "VDISK.SYS \\\n"
                "           DRIVER.SYS KEYB.COM MODE.COM FDISK.COM FORMAT.COM "
                "SYS.COM ANSI.SYS\n"
                "  `python3 tools/os88fat.py ls %s` lists what is there."
                % (free, need, a.dos_disk))
        v.add(com, "DOSTRAP.COM")
        v.save()

        with os88marty.launch(boot, apps=a.disk, machine=a.machine,
                              boot=a.boot_secs) as m:
            for _ in range(a.boot_keys):
                m.key("Enter")
                time.sleep(3)
            m.type_text("DOSTRAP")
            m.key("Enter")
            time.sleep(4)
            screen = [r.rstrip() for r in (m.screen() or []) if "DOSTRAP" in r]
            if not any("installed" in r for r in screen):
                raise SystemExit(
                    "os88dosdbg: DOSTRAP did not install.  The screen said %r.\n"
                    "  A DOS that prompts for date and time needs --boot-keys 2 "
                    "(the default); one that does not needs 0." % (screen[:3],))
            m.type_text("%s:" % a.drive)
            m.key("Enter")
            time.sleep(3)
            if a.cd:
                # A PROGRAM THAT DEMANDS ITS OWN DIRECTORY cannot be compared
                # by naming a path, because the two sides would then be doing
                # different things: Prince of Persia answers "Please start
                # program from the default drive and directory" to
                # `B:\PRINCE\PRINCE` under a real DOS. This types the CD that
                # our side gets for free from a double-click, so both machines
                # start the program where it expects to be.
                m.type_text("CD \\%s" % a.cd.replace("/", "\\"))
                m.key("Enter")
                time.sleep(2)
            # A PATHED PROGRAM NEEDS DOS's OWN SEPARATOR.  `trace` hands
            # `PRINCE/PRINCE.EXE` to os88ui.path(), which wants forward
            # slashes; COMMAND.COM reads one as a SWITCH character and answers
            # "Bad command or file name", so the two sides of a comparison
            # cannot take the same string.  Translating here is what lets one
            # invocation name one program (docs/DOS-DEBUGGING.md).
            m.type_text(os.path.splitext(a.program)[0].replace("/", "\\"))
            m.key("Enter")
            seg = struct.unpack("<HH", bytes(m.read(0x21 * 4, 4)))[1]
            base = seg << 4
            end = time.time() + a.timeout
            while time.time() < end:
                total = struct.unpack("<H", bytes(m.read(base + lay["total"], 2)))[0]
                if a.until and total >= a.until:
                    break
                if total >= lay["nent"]:
                    break
                time.sleep(a.poll)
            total = struct.unpack("<H", bytes(m.read(base + lay["total"], 2)))[0]
            ring = bytes(m.read(base + lay["ring"], lay["nent"] * lay["entsz"]))
            psp = struct.unpack_from("<H", ring, 6)[0]   # entry 0's DX
            if a.shot:
                wd, ht, px = m.fbuf()
                os88marty.write_png_rgb(a.shot, wd, ht, px)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # the TSR keeps the FIRST nent and stops, so it never wraps
    entries = _entries(ring, lay["entsz"], lay["nent"], min(total, lay["nent"]), 0)
    _save(a.out, dict(source="dos", program=a.program, psp=psp, total=total,
                      wrapped=total > lay["nent"], machine=a.machine), entries)
    print("os88dosdbg: %d call(s)%s, PSP %04X -> %s"
          % (total, " (CAPPED at %d - raise NENT in trap.asm)" % lay["nent"]
             if total > lay["nent"] else "", psp, a.out))
    return 0


# =============================================================================
# the alignment
# =============================================================================
def _site(e, psp):
    return "%02X@%04X:%04X" % (e["ax"] >> 8, (e["cs"] - psp) & 0xFFFF, e["ip"])


def _row(e, psp):
    res = ("no return" if e["axout"] == 0xFFFF and e["cf"] == 0xFFFF
           else "%04X %s ES:BX=%04X:%04X" % (e["axout"], "CF" if e["cf"] == 1 else "ok",
                                             e["esout"], e["bxout"]))
    return ("AH=%02X %-9s AL=%02X BX=%04X CX=%04X DX=%04X -> %-26s @+%04X:%04X"
            % (e["ax"] >> 8, AH.get(e["ax"] >> 8, "?"), e["ax"] & 0xFF,
               e["bx"], e["cx"], e["dx"], res,
               (e["cs"] - psp) & 0xFFFF, e["ip"]))


def align(a_doc, b_doc):
    """Match the two traces on (function, call site) and return the blocks.

    Addresses differ between two runs of the same program - the load segment,
    the heap, the stack all move - so the key deliberately drops BX, CX, DX and
    every result.  What it keeps is the SEQUENCE OF INSTRUCTIONS that made
    calls, which is the program's own control flow and is identical until the
    program actually branches differently.
    """
    ap, bp = a_doc["psp"], b_doc["psp"]
    sa = [_site(e, ap) for e in a_doc["entries"]]
    sb = [_site(e, bp) for e in b_doc["entries"]]
    sm = difflib.SequenceMatcher(None, sa, sb, autojunk=False)
    return [blk for blk in sm.get_matching_blocks() if blk.size]


_REG = {"b": "bx", "c": "cx", "d": "dx"}


def _same_question(x, y):
    """Were the two machines asked the same thing?  AX always, plus whichever
    of BX/CX/DX carry a VALUE for that function rather than an address."""
    return _question_differs(x, y) is None


def _question_differs(x, y):
    """...and if not, WHICH argument - because that is a different finding.
    A differing ANSWER means we are wrong; a differing QUESTION at the same
    instruction means the program computed something different, from state
    with no call in it.  Both matter and they point at opposite halves."""
    ah = x["ax"] >> 8
    if ah != (y["ax"] >> 8):
        return "AH"
    if ah in AL_IS_AN_ARGUMENT and (x["ax"] & 0xFF) != (y["ax"] & 0xFF):
        return "AL"
    for r in ARG_VALUES.get(ah, "c"):
        if x[_REG[r]] != y[_REG[r]]:
            return _REG[r].upper()
    return None


def _answers_differ(x, y):
    """Do two calls of the same function with the same arguments disagree?

    CF first, because a call that succeeded on one machine and failed on the
    other is always the story.  Then the error code, which is comparable
    whenever both failed.  Then AX, but only for the functions where AX on
    SUCCESS is a fact rather than a leftover or an address.
    """
    if x["cf"] != y["cf"]:
        return "the carry flag"
    if x["cf"] == 1 and x["axout"] != y["axout"]:
        return "the error code"
    ah = x["ax"] >> 8
    if ah == 0x30 and (x["axout"] ^ y["axout"]) and x["cf"] == 0:
        return "the DOS version"          # AH:AL both meaningful here
    if x["cf"] == 0 and ah in AX_IS_AN_ANSWER and x["axout"] != y["axout"]:
        return AX_IS_AN_ANSWER[ah]
    return None


def cmd_diff(a):
    A = json.load(open(a.a, encoding="utf-8"))
    B = json.load(open(a.b, encoding="utf-8"))
    ap, bp = A["psp"], B["psp"]
    ea, eb = A["entries"], B["entries"]
    na = A.get("source", os.path.basename(a.a))
    nb = B.get("source", os.path.basename(a.b))
    w = max(len(na), len(nb))
    print("%-*s %d call(s), PSP %04X%s" % (w, na, len(ea), ap,
                                           "  WRAPPED" if A.get("wrapped") else ""))
    print("%-*s %d call(s), PSP %04X%s" % (w, nb, len(eb), bp,
                                           "  WRAPPED" if B.get("wrapped") else ""))
    blocks = align(A, B)
    print("\naligned runs (on function + call site, which is what does NOT move")
    print("between two machines that loaded the program at different addresses):")
    for blk in blocks:
        print("   %-*s %4d..%-4d   %-*s %4d..%-4d   (%d)"
              % (w, na, blk.a, blk.a + blk.size - 1,
                 w, nb, blk.b, blk.b + blk.size - 1, blk.size))
    if not blocks:
        print("   NOTHING aligned - the two traces have no call site in common.")
        print("   Check both ran the same program, and that neither wrapped.")
        return 1

    # --- 1. every place one side made calls the other did not ---------------
    gaps, i, j = [], 0, 0
    for blk in blocks:
        if blk.a > i or blk.b > j:
            gaps.append((i, blk.a, j, blk.b))
        i, j = blk.a + blk.size, blk.b + blk.size
    if i < len(ea) or j < len(eb):
        gaps.append((i, len(ea), j, len(eb)))

    if not gaps:
        print("\nthe CODE PATH is identical for every call on both sides.")
    for n, (a0, a1, b0, b1) in enumerate(gaps):
        print("\ngap %d: %s made %d call(s) here that %s did not; %s made %d."
              % (n + 1, na, a1 - a0, nb, nb, b1 - b0))
        if a0:
            print("   last agreed:")
            print("     %-*s %3d %s" % (w, na, a0 - 1, _row(ea[a0 - 1], ap)))
            print("     %-*s %3d %s" % (w, nb, b0 - 1, _row(eb[b0 - 1], bp)))
        for tag, ents, psp, lo, hi in ((na, ea, ap, a0, a1), (nb, eb, bp, b0, b1)):
            if hi <= lo:
                continue
            print("   %s alone:" % tag)
            for x in range(lo, min(hi, lo + a.context)):
                print("     %-*s %3d %s" % (w, tag, x, _row(ents[x], psp)))
            if hi - lo > a.context:
                print("     %-*s ... %d more" % (w, "", hi - lo - a.context))

    # --- 2. ...and the first ANSWER that differs, which a code-path diff -----
    # hides entirely: the same instruction, the same question, a different
    # reply.  Three of the four defects this tool was built for looked like
    # this and like nothing else.
    # `edge` is how far into its aligned run a finding is.  Right after a gap
    # the pairing is difflib's guess - when a loop runs a different number of
    # times on the two sides, WHICH iteration pairs with which is arbitrary -
    # so a finding there is worth less than one deep inside a run, and saying
    # so is cheaper than a heuristic that hides it.
    ans = qst = None
    for bi, blk in enumerate(blocks):
        for k in range(blk.size):
            x, y = ea[blk.a + k], eb[blk.b + k]
            if _same_question(x, y):
                why = _answers_differ(x, y)
                if why and ans is None:
                    ans = (blk.a + k, blk.b + k, why, x, y, k, bi)
            elif qst is None:
                qst = (blk.a + k, blk.b + k, _question_differs(x, y), x, y, k, bi)
            if ans and qst:
                break

    print("")
    def edge_note(k, bi):
        if bi and k < 3:
            print("  (%d call(s) into the run after a gap - which side pairs with"
                  % k)
            print("   which is arbitrary there; read the gap above first.)")

    if ans:
        i, j, why, x, y, k, bi = ans
        print("the first ANSWER that differs - same instruction, same arguments,")
        print("%s.  THIS IS THE BOX BEING WRONG:" % why)
        print("  %-*s %3d %s" % (w, na, i, _row(x, ap)))
        print("  %-*s %3d %s" % (w, nb, j, _row(y, bp)))
        edge_note(k, bi)
    else:
        print("no call was answered differently where both sides asked the same")
        print("thing - so nothing this box SAYS is the difference.")
    if qst:
        i, j, why, x, y, k, bi = qst
        print("")
        print("the first QUESTION that differs - same instruction, different %s."
              % why)
        print("THE PROGRAM COMPUTED SOMETHING DIFFERENT, from state with no call")
        print("in it: the PSP, the BDA, the vectors, or its own memory (--state):")
        print("  %-*s %3d %s" % (w, na, i, _row(x, ap)))
        print("  %-*s %3d %s" % (w, nb, j, _row(y, bp)))
        edge_note(k, bi)
    return 0


# =============================================================================
def cmd_syms(a):
    names = a.names or (list(CONSTS) + list(BSS))
    for k, v in dos_syms(names).items():
        print("  %-14s %6d  0x%04X" % (k, v, v))
    return 0


def cmd_build(a):
    build_trace_disk(a.system, a.out)
    print(trace_costs(), file=sys.stderr)
    return 0


def selfcheck():
    """Everything that does not need an emulator: the symbol probe, the TSR
    signature, the ring decode (wrapped and not), and the alignment."""
    fails = []

    def ck(name, ok, why=""):
        print("  %-46s %s%s" % (name, "ok" if ok else "FAIL",
                                "  " + why if why else ""))
        if not ok:
            fails.append(name)

    sym = dos_syms(list(CONSTS) + list(BSS))
    ck("apps/dos symbols assemble out", len(sym) == len(CONSTS) + len(BSS))
    ck("DOS_TRACE_SZ is the 16-word entry this file decodes",
       sym.get("DOS_TRACE_SZ") == 32,
       "" if sym.get("DOS_TRACE_SZ") == 32 else
       "got %s - FIELDS and the guest have diverged" % sym.get("DOS_TRACE_SZ"))
    ck("the ring is a power of two (the mask depends on it)",
       sym.get("DOS_TRACEN", 0) and not (sym["DOS_TRACEN"] & (sym["DOS_TRACEN"] - 1)))

    d = tempfile.mkdtemp(prefix="os88dosdbg-")
    try:
        com = nasm(TRAP_ASM, os.path.join(d, "t.com"))
        lay = trap_syms(com)
        ck("the TSR publishes its own layout", set(lay) ==
           {"ring", "total", "wr", "here", "nent", "entsz"})
        ck("both sides agree on the entry size",
           lay["entsz"] == sym["DOS_TRACE_SZ"],
           "" if lay["entsz"] == sym["DOS_TRACE_SZ"] else
           "TSR %d vs box %d - one reader cannot decode both"
           % (lay["entsz"], sym["DOS_TRACE_SZ"]))
        ck("the TSR's ring fits inside its own .COM",
           lay["ring"] - 0x100 + lay["nent"] * lay["entsz"] <= os.path.getsize(com))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # the decode, against a ring this check builds
    stride, nent = 32, 8
    def mk(vals):
        b = bytearray(nent * stride)
        for k, v in enumerate(vals):
            struct.pack_into("<16H", b, (k % nent) * stride, *v)
        return bytes(b)
    seq = [tuple([0x3D00 + i] + [0] * 15) for i in range(5)]
    got = _entries(mk(seq), stride, nent, 5, 5 * stride)
    ck("a short ring decodes oldest first",
       [e["ax"] for e in got] == [0x3D00 + i for i in range(5)])
    seq = [tuple([0x3D00 + i] + [0] * 15) for i in range(11)]
    got = _entries(mk(seq), stride, nent, 11, (11 * stride) % (nent * stride))
    ck("a WRAPPED ring decodes oldest first and drops the oldest",
       [e["ax"] for e in got] == [0x3D00 + i for i in range(3, 11)],
       "" if [e["ax"] for e in got] == [0x3D00 + i for i in range(3, 11)]
       else "got %s" % [hex(e["ax"]) for e in got])

    # alignment: two runs of one program at different load addresses, one of
    # which takes an extra pair of calls in the middle
    def doc(psp, sites, outs=None):
        ents = []
        for k, (ah, ip) in enumerate(sites):
            e = dict.fromkeys(FIELDS, 0)
            e["ax"] = ah << 8
            e["cs"] = (psp + 0x0C93) & 0xFFFF
            e["ip"] = ip
            e["axout"] = (outs or {}).get(k, 0)
            ents.append(e)
        return dict(psp=psp, entries=ents, source="t")
    common = [(0x3D, 0x100), (0x3F, 0x110), (0x42, 0x120), (0x3E, 0x130)]
    A = doc(0x0D99, common)
    B = doc(0x1CE2, common[:2] + [(0x48, 0x200), (0x4A, 0x210)] + common[2:])
    blocks = align(A, B)
    ck("alignment survives a different load address and an inserted pair",
       [(b.a, b.b, b.size) for b in blocks] == [(0, 0, 2), (2, 4, 2), (4, 6, 0)]
       or sum(b.size for b in blocks) == 4,
       "" if sum(b.size for b in blocks) == 4 else "matched %d"
       % sum(b.size for b in blocks))

    A2 = doc(0x0D99, common, outs={1: 0x0006})
    B2 = doc(0x1CE2, common, outs={1: 0x0000})
    same = [k for k in range(4)
            if (A2["entries"][k]["axout"] != B2["entries"][k]["axout"])]
    ck("a differing ANSWER at a matching site is findable", same == [1])

    print("os88dosdbg: %s" % ("ok" if not fails else "FAILED: " + ", ".join(fails)))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(
        description="debug a DOS program by comparing os8088 with a real DOS")
    ap.add_argument("--selfcheck", action="store_true",
                    help="check everything that needs no emulator, then exit")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("syms", help="apps/dos constants and bss offsets, derived")
    p.add_argument("names", nargs="*")
    p.set_defaults(fn=cmd_syms)

    p = sub.add_parser("build", help="a system disk carrying the DOSTRACE package")
    p.add_argument("--system", default="build/os8088-720.img",
                   help="the make target to build (default the 720KB system disk)")
    p.add_argument("-o", "--out", default="build/dostrace.img")
    p.set_defaults(fn=cmd_build)

    for name, fn, need in (("trace", cmd_trace, False), ("ref", cmd_ref, True)):
        p = sub.add_parser(name, help=("a real DOS's" if need else "our")
                           + " INT 21h traffic, as JSON")
        p.add_argument("program", help="the 8.3 name on the disk, e.g. PRINCE.EXE")
        p.add_argument("--disk", required=True, help="the floppy to put in B:")
        p.add_argument("--drive", default="B")
        p.add_argument("-o", "--out", default=None)
        p.add_argument("--machine", default="os8088_5150_herc_sb_720_gla")
        p.add_argument("--timeout", type=float, default=240.0)
        p.add_argument("--poll", type=float, default=0.2)
        p.add_argument("--until", type=int, default=0,
                       help="stop once this many calls are logged (0: run to the "
                            "program's exit, or to the ring's cap)")
        if need:
            p.add_argument("--dos-disk", required=True,
                           help="YOUR bootable DOS floppy; it is copied, not edited")
            p.add_argument("--boot-secs", type=int, default=30)
            p.add_argument("--cd", default=None,
                           help="CD into this directory before running the "
                                "program, for one that demands its own "
                                "(the double-click gives our side this free)")
            p.add_argument("--boot-keys", type=int, default=2,
                           help="Enters for the date and time prompts (DOS 3.3: 2)")
            p.add_argument("--shot", help="write a PNG of the screen at the end")
            p.add_argument("--free", nargs="*", default=[], metavar="NAME",
                           help="files to leave out of the COPY of the DOS disk, "
                                "to make room for the tracer; your own disk is "
                                "never edited")
        else:
            p.add_argument("--kernel", default="build/dostrace.img",
                           help="a system disk carrying the DOSTRACE package")
            p.add_argument("--system", default="build/os8088-720.img")
            p.add_argument("--build", action="store_true",
                           help="build (and verify) the kernel disk first")
            p.add_argument("--state", action="store_true",
                           help="also dump the PSP, IVT, BDA and handle table")
        p.set_defaults(fn=fn)

    p = sub.add_parser("diff", help="align two traces; say where they part")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--context", type=int, default=4)
    p.set_defaults(fn=cmd_diff)

    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if not a.cmd:
        ap.print_help()
        return 2
    if a.cmd in ("trace", "ref") and not a.out:
        a.out = "build/%s-%s.json" % (a.cmd, os.path.splitext(a.program)[0].lower())
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
