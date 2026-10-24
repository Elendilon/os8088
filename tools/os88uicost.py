#!/usr/bin/env python3
"""What apps/os88ui.inc costs the tree, and what sharing it would buy.

    python3 tools/os88uicost.py [--json out.json] [--disks img ...]

docs/plans/COMMON-UI-PLAN.md is the study these numbers belong to. Three
tables, each re-derived from the sources and the built floppies rather than
quoted:

  1. PER ROUTINE - how many images carry it, how many bytes in all, and how
     many distinct BYTE VARIANTS exist once relocation is masked out.
  2. PER DISK   - for every image named by --disks (default: the eight 360KB
     ones plus the 1.44MB apps disk), the library bytes its packages carry,
     the UNION of the variants they carry, and the difference: what a
     one-per-disk library (the plan's option B) could deduplicate.
  3. KERNEL     - not here: `python3 tools/os88sym.py`'s map answers it, and
     the plan quotes the os88ui_* rows of both kernels.

HOW. tools/incsize.py's method - assemble with `nasm -l`, attribute bytes by
ADDRESS to the include's labels - run over every includer, and then run AGAIN
with two bytes of padding inserted in front of the `%include`. A word that
moved by exactly two is a base-relative absolute reference (a fixup a
load-time linker would have to apply); everything else that differs between
two packages' copies of one routine is a different configuration, or an
intra-library rel16 whose distance changed because the package took a
different subset. Variants are keyed (routine, length): equal-length copies
differ only in those relative words - a byte diff of os88ui_btndrag's and
os88ui_abtn1's copies showed exactly that when the plan was written.

Packages whose sources need a generated input `make` did not produce (the
C packages, whose `.gen.asm` needs build/cc) are reported as skipped, never
estimated. Nothing is written outside a private temporary directory, and
never to /dev/null (CLAUDE.md, the testing traps).
"""
import argparse, collections, glob, json, os, re, shutil, subprocess, sys, \
    tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

INC = "apps/os88ui.inc"
DIRS = ["apps", "drivers", "tests", "build", "apps/wire", "drivers/net",
        "drivers/cdrom", "drivers/sound", "drivers/httpfs", "drivers/hdd"]
DISKS = ["os8088-360", "apps360", "office360", "network360", "games360",
         "emu360", "util360", "media360", "apps"]
LAB = re.compile(r"^\s*\d+\s+(?:([0-9A-F]{8})\s+)?(?:[0-9A-F<>\-\(\)]+\s+)?"
                 r"(?:<\d+>\s+)?([A-Za-z_.][A-Za-z0-9_.]*):")
ADDR = re.compile(r"^\s*\d+\s+([0-9A-F]{8})\s+([0-9A-F]+)")
# a routine longer than this is an attribution artefact: a label at the end
# of the include followed by unlabelled package data (SKIES's drclose read
# 4,921 bytes that way)
MAXROUTINE = 1500


def labels():
    want = set()
    for line in open(INC, errors="replace"):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", line.split(";")[0].strip())
        if m:
            want.add(m.group(1))
    return want


def includers():
    out = subprocess.run(["grep", "-rl", '%include "os88ui.inc"', "apps",
                          "drivers"], capture_output=True, text=True).stdout
    return sorted(p for p in out.split() if not p.endswith("os88ui.inc"))


def assemble(src, pad, want, tmp):
    """{routine: bytes} for one assembly, with `pad` bytes before the include."""
    text = open(src, errors="replace").read()
    text = text.replace('%include "os88ui.inc"',
                        'times %d db 90h\n%%include "os88ui.inc"' % pad, 1)
    p = os.path.join(tmp, "src.asm")
    open(p, "w").write(text)
    inc = []
    for d in [os.path.dirname(src)] + DIRS + glob.glob("build/*-art"):
        inc += ["-I", d.rstrip("/") + "/"]
    r = subprocess.run(["nasm", "-f", "bin"] + inc +
                       ["-l", tmp + "/a.lst", "-o", tmp + "/a.bin", p],
                       capture_output=True, text=True)
    if r.returncode:
        return None, (r.stderr.splitlines() or ["nasm failed"])[0]
    lst = open(tmp + "/a.lst", errors="replace").read().splitlines()
    blob = open(tmp + "/a.bin", "rb").read()
    marks, pending, hi = [], None, 0
    for line in lst:
        m = ADDR.match(line)
        if m:
            hi = max(hi, int(m.group(1), 16) + len(m.group(2)) // 2)
        m = LAB.match(line)
        if m:
            if m.group(2).startswith("."):
                continue
            pending = m.group(2)
            if m.group(1):
                marks.append((int(m.group(1), 16), pending))
                pending = None
            continue
        if m is None and pending:
            m = ADDR.match(line)
            if m:
                marks.append((int(m.group(1), 16), pending))
                pending = None
    if pending:
        marks.append((hi, pending))
    marks.sort()
    rows = {}
    for i, (a, name) in enumerate(marks):
        e = marks[i + 1][0] if i + 1 < len(marks) else a
        if name in want and 0 < e - a <= MAXROUTINE:
            rows[name] = blob[a:e]
    return (rows, len(blob)), None


def measure():
    want = labels()
    res = {}
    for src in includers():
        tmp = tempfile.mkdtemp(prefix="uicost-")
        try:
            a0, err = assemble(src, 0, want, tmp)
            a1, _ = assemble(src, 2, want, tmp) if a0 else (None, None)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if not a0 or not a1:
            res[src] = {"skip": err}
            continue
        rows0, image = a0
        rows1 = a1[0]
        out = {}
        for n, b0 in rows0.items():
            b1 = rows1.get(n)
            rel = 0
            norm = bytearray(b0)
            if b1 is not None and len(b1) == len(b0):
                for i in range(len(b0) - 1):
                    w0 = int.from_bytes(b0[i:i + 2], "little")
                    w1 = int.from_bytes(b1[i:i + 2], "little")
                    if w0 != w1 and (w1 - w0) & 0xFFFF == 2:
                        norm[i] = norm[i + 1] = 0xEE
                        rel += 1
            out[n] = {"len": len(b0), "rel": rel, "hex": norm.hex()}
        res[src] = {"image": image, "rows": out}
    return res


def disk_files(img):
    """Every .O88 and .DRV on a FAT12 image, subdirectories included."""
    from os88fat import Fat12
    v = Fat12(img)
    cs = v.spc * v.bps
    found = []

    def walk(raw):
        for i in range(0, len(raw) - 31, 32):
            e = raw[i:i + 32]
            if e[0] == 0:
                return
            if e[0] == 0xE5 or e[11] == 0x0F or e[11] & 8:
                continue
            name = e[:8].decode("latin1").rstrip()
            ext = e[8:11].decode("latin1").rstrip()
            if name in (".", ".."):
                continue
            first = int.from_bytes(e[26:28], "little")
            if e[11] & 0x10:
                walk(b"".join(bytes(v.img[v.cluster_off(c):v.cluster_off(c) + cs])
                              for c in v.chain(first)))
            elif ext in ("O88", "DRV"):
                found.append(name)
    walk(bytes(v.img[v.root_off:v.root_off + v.nroot * 32]))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", help="write the raw measurement here")
    ap.add_argument("--disks", nargs="*",
                    default=["build/%s.img" % d for d in DISKS])
    a = ap.parse_args()
    res = measure()
    if a.json:
        json.dump(res, open(a.json, "w"))

    users = collections.Counter()
    total = collections.Counter()
    variants = collections.defaultdict(set)
    for src, v in res.items():
        for n, r in v.get("rows", {}).items():
            users[n] += 1
            total[n] += r["len"]
            variants[n].add(r["len"])
    measured = [s for s, v in res.items() if "rows" in v]
    print("os88uicost: %d includers measured, %d skipped" %
          (len(measured), len(res) - len(measured)))
    for s, v in res.items():
        if "skip" in v:
            print("  skipped %s: %s" % (s, v["skip"][:90]))
    every = sum(total.values())
    dic = sum(sum(variants[n]) for n in variants)
    print("library bytes in all images %d; distinct (routine, length) "
          "variants %d totalling %d" % (every, sum(len(x) for x in
                                                   variants.values()), dic))
    print("\n%-20s %5s %7s  %s" % ("routine", "users", "bytes", "lengths"))
    for n, t in total.most_common(30):
        print("%-20s %5d %7d  %s" % (n, users[n], t, sorted(variants[n])))

    byname = {os.path.basename(s)[:-4].upper(): s for s in res}
    byname.update({"PXSTEIN": "apps/pixelstein/pxgame.asm",
                   "WIREFLET": "apps/wirefleet/wirefleet.asm"})
    print("\n%-24s %5s %7s %7s %7s" % ("disk", "pkgs", "sum", "union",
                                       "dedup"))
    for img in a.disks:
        if not os.path.exists(img):
            continue
        s, union, n = 0, set(), 0
        for f in disk_files(img):
            src = byname.get(f)
            rows = res.get(src, {}).get("rows") if src else None
            if not rows:
                continue
            n += 1
            for name, r in rows.items():
                s += r["len"]
                union.add((name, r["len"]))
        u = sum(x for _, x in union)
        print("%-24s %5d %7d %7d %7d" % (os.path.basename(img), n, s, u, s - u))


if __name__ == "__main__":
    main()
