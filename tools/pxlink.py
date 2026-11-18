#!/usr/bin/env python3
"""pxlink: the package's variables, by name, for a LINKED part (SPEC.md 106.20).

    python3 tools/pxlink.py build/pixel.bin -o build/pxlink.inc
    python3 tools/pxlink.py build/megak/apps/pixel.bin -D PKG_MEGA \
        -o build/megak/apps/pxlink.inc      (the kern_mega ARM's package)

PiXEL's SIMPLE part (apps/pixel/pxsimp.asm) is the five simple formats'
readers moved out of the resident package and still reading and writing the
package's own variables - [px_cur + PXR_SW], [px_spal], [px_rpos] - through
DS, which SPEC.md 106.5's rule 2 allows. A separately assembled part has to
learn where those variables are, and this is how: pixel.asm is assembled
again with a NASM symbol map, the result must be BYTE-IDENTICAL to the
build/pixel.bin it is linked against (or the map describes another package
and the tool refuses), and every symbol at or past the image's end - the
package's bss, and nothing else - is written out as an equate.

ONLY THE BSS, ON PURPOSE. A code label written out would assemble a part's
`call px_emit` as a near call into the PART's own segment at the package's
offset, which is silent and wrong; leaving every symbol below the image's
end undefined makes that an assembly error instead. Tables the moved code
reads are copied into the part.

THE STAMP. The image and bss sizes from the package's header are written as
PXL_IMAGE and PXL_BSS; the part compares them with the header of the package
it is called from (DS:8 and DS:10) before it touches a variable, so a part
from another build answers PXD_LINK rather than writing the wrong bytes.

ANOTHER PACKAGE (BONANZA's shell part, SPEC.md 130.19.2) names its source,
its include directories and its prefix:

    python3 tools/pxlink.py build/bonanza.bin --src apps/bonanza/bonanza.asm \
        -I apps/ -I apps/bonanza/ -I build/bonanza-art/ --prefix BZL --consts \
        -o build/bonanza-art/bzlink.inc

--consts PREFIXES also writes the ABSOLUTE constants the package defines under
those prefixes (the map's "No Section" symbols: its equates, never a label;
the SDK's own are the part's to include), so the part shares the
package's numbers without a second copy of where they are defined; NASM
accepts an identical redefinition and refuses a different one, so a part
that includes the same headers is checked against them.
"""
import argparse
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bin")
    ap.add_argument("-o", required=True)
    ap.add_argument("--src", default=os.path.join("apps", "pixel", "pixel.asm"),
                    help="the package's source (default PiXEL's)")
    ap.add_argument("-I", action="append", default=[], dest="inc", metavar="DIR",
                    help="an include directory, as the package was built (default PiXEL's)")
    ap.add_argument("--prefix", default="PXL", help="the stamp's prefix (PXL_IMAGE, PXL_BSS)")
    ap.add_argument("--consts", metavar="PREFIXES", default="",
                    help="also write the package's absolute constants whose names start "
                    "with one of these comma-separated prefixes")
    ap.add_argument("-D", action="append", default=[], metavar="NAME",
                    help="assembled with -DNAME, as the package was (the "
                    "kern_mega arm's PKG_MEGA, SPEC.md 106.8.1)")
    a = ap.parse_args()
    want = open(a.bin, "rb").read()
    image, bss = struct.unpack_from("<HH", want, 8)
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "p.asm")
        mp = os.path.join(d, "p.map")
        out = os.path.join(d, "p.bin")
        srcp = a.src if os.path.isabs(a.src) else os.path.join(ROOT, a.src)
        incs = a.inc or [os.path.join("apps") + "/", os.path.join("apps", "pixel") + "/"]
        incs = [i if os.path.isabs(i) else os.path.join(ROOT, i) for i in incs]
        open(src, "w").write(open(srcp).read() + "\n[map symbols %s]\n" % mp)
        cmd = ["nasm", "-f", "bin", "-w+error"] + ["-D" + n for n in a.D]
        for i in incs:
            cmd += ["-I", i.rstrip("/") + "/"]
        subprocess.run(cmd + ["-o", out, src], check=True)
        if open(out, "rb").read() != want:
            sys.exit("pxlink: %s is not %s as it stands - "
                     "rebuild it first" % (a.bin, a.src))
        syms = []
        consts = []
        for line in open(mp):
            f = line.split()
            if a.consts and len(f) == 2 and f[1].startswith(tuple(a.consts.split(","))) and len(f[0]) == 8 and all(c in "0123456789ABCDEF" for c in f[0]) \
                    and not f[1].startswith("..") and "." not in f[1]:
                consts.append((f[1], int(f[0], 16)))
            if len(f) == 3 and all(c in "0123456789ABCDEF" for c in f[0]):
                v = int(f[1], 16)
                if v >= image and not f[2].startswith("..") \
                        and "." not in f[2]:
                    syms.append((f[2], v))
    syms.sort(key=lambda s: (s[1], s[0]))
    lines = ["; GENERATED by tools/pxlink.py from %s - do not edit (SPEC.md "
             "106.20)" % os.path.basename(a.bin),
             "; the package's bss, by name, for a part linked against it",
             "%s_IMAGE   equ %d" % (a.prefix, image),
             "%s_BSS     equ %d" % (a.prefix, bss)]
    if consts:
        lines.append("; the package's absolute constants (--consts)")
        lines += ["%-24s equ 0x%X" % (n, v) for n, v in sorted(consts)]
        lines.append("; the package's bss")
    lines += ["%-24s equ 0x%04X" % (n, v) for n, v in syms]
    text = "\n".join(lines) + "\n"
    open(a.o, "w").write(text)
    print("pxlink: %d package variables into %s" % (len(syms), a.o))
    return 0


if __name__ == "__main__":
    sys.exit(main())
