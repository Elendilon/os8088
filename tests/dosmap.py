#!/usr/bin/env python3
"""Symbol offsets for the DOS box and for a probe running INSIDE it.

    import dosmap
    dm = dosmap.package("DOSNET_CARD")      # DOS.O88's own near offsets
    pm = dosmap.probe()                     # DOSPKT.COM's, org 100h

WHY NOT `dispapps._map`. That one takes `defines` and means exactly ONE thing
by them - `-DAPP_SMALL` - so it compares the result against
`build/smallapp/<app>.o88` and exits naming a file a knob build never writes.
And its source path is `apps/<app>/<app>.asm` or `tests/<app>/<app>.asm`,
which `tests/dostrap/dospkt.asm` is neither. Two small differences, both of
which fail as a message about the wrong subject.

**THE PROBE'S OFFSETS ARE FROM THE PSP**, which needs saying because there are
two plausible bases and one of them reads plausible rubbish. A `.COM` is
loaded at PSP:0100 with CS = DS = the PSP, and the file is assembled `org
0x100` - so a map value already carries the 0x100 and the base is the PSP
itself, not PSP+0x10. With the segment biased by a paragraph-of-0x100 the
first reading of this was `lastflags=0000` for a program that had recorded a
SYN|ACK, which points at the box and is a bug in the reader.
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE = {}


def _map(src, defines, incs):
    key = (src, tuple(defines))
    if key in _CACHE:
        return _CACHE[key]
    d = tempfile.mkdtemp(prefix="os88dosmap")
    a, mp = os.path.join(d, "x.asm"), os.path.join(d, "x.map")
    open(a, "w").write(open(src).read() + "\n[map all %s]\n" % mp)
    args = ["nasm", "-f", "bin", "-w+error", "-o", os.path.join(d, "x.bin")]
    for i in incs:
        args += ["-I", os.path.join(ROOT, i) + os.sep]
    args += ["-D" + x for x in defines] + [a]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        sys.exit("dosmap: could not map %s:\n%s" % (src, r.stderr[:400]))
    out = {}
    # **TWO SHAPES, AND THE SECOND ONE IS THE CLAIM.** Inside a section nasm
    # writes "<real> <virtual> <name>"; under its "---- No Section ----"
    # heading it writes "<value> <name>" for every ABSOLUTE equate - which is
    # where PKB_STATE, DNB_LSN, dn_lsn and DOS_ENVBUF live, because an offset
    # into a heap CLAIM is a plain number and not an address in this image.
    # A reader that took only the three-field lines could see dos_pkt_bseg
    # (`equ os88_image_end + N`, relocatable) and not the offset to apply to
    # what it holds, which left a test hardcoding the layout - the one thing
    # DOS_TRACE_SZ's own comment says not to do.
    nosect = False
    for line in open(mp):
        if line.startswith("---- "):
            nosect = line.startswith("---- No Section")
            continue
        p = line.split()                # "<vaddr> <raddr> <name>", HEX
        if len(p) == 3:
            try:
                out[p[2]] = int(p[0], 16)
            except ValueError:
                pass
        elif nosect and len(p) == 2:
            try:
                out.setdefault(p[1], int(p[0], 16))
            except ValueError:
                pass
    for f in (a, mp):
        try:
            os.unlink(f)
        except OSError:
            pass
    if "os88_image_end" not in out and "start" not in out:
        sys.exit("dosmap: %s's map looks empty" % src)
    _CACHE[key] = out
    return out


def package(*defines):
    """Every label and equate in apps/dos/dos.asm, as a near offset.

    Packages are assembled at org 0 and never relocated (SPEC.md 20), so the
    map value IS the offset inside the instance's segment - bss included,
    since `dos_pkt_xl` and friends are `equ os88_image_end + N`.
    """
    return _map(os.path.join(ROOT, "apps", "dos", "dos.asm"), defines,
                ("apps", os.path.join("apps", "dos"),
                 os.path.join("drivers", "net")))


def probe(name="dospkt"):
    """Every label in one of tests/dostrap/'s `.COM` probes, from the PSP."""
    return _map(os.path.join(ROOT, "tests", "dostrap", name + ".asm"), (),
                (os.path.join("tests", "dostrap"),))
