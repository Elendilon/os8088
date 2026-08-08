#!/usr/bin/env python3
"""kernsize - what this change cost the kernel, per section and in rungs.

Run by `make` after the kernel assembles. It prints five lines and NEVER
fails the build: the guards in kernel/kernel.asm are what refuse an overrun,
and this is the thing that tells you how close you came.

WHY IT EXISTS.  docs/KERNEL-MEMORY.md's numbers went three budget moves stale
once, and one step stale again while this tool was being written - because
every one of them had to be produced by hand, by bisecting a constant or by
injecting a %warning probe into a copy of kernel.asm.  A number nobody can
produce in one command is a number that stops being produced.

WHAT IT REPORTS, and why it is not just "the total".  The footprint moves in
512-byte RUNGS: .text and .bss share one, .cold has its own, .lowbss and task
0's stack a third.  A change that adds 90 bytes to .text usually moves the
footprint by ZERO - and that is not the same thing as costing nothing.  It
spends 90 bytes of the rung's remaining slack, and the next feature is the
one that finds the rung full and pays the whole 512.  So the report leads
with the per-section bytes and the SUM, and names the slack left in each
rung; a crossing is called out separately because it is the moment the
machine's RAM actually changes.

A KNOB BUILD measures the kernel that knob produces, so `make VIDEO=cga` and
friends pass their own -D flags straight through - a report that described a
different binary from the one on disk would be worse than none.  --bless
refuses them for the same reason: the baseline is the shipped kernel.

USAGE
    tools/kernsize.py                  report against the baseline
    tools/kernsize.py --bless          ...and rewrite the baseline to match
    tools/kernsize.py --json           machine-readable, no baseline needed

The baseline lives in docs/KERNEL-MEMORY.md between the kernsize markers, so
that the document's headline figures cannot drift from the build without the
next `make` saying so.  Bless it in the same commit as the change.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KERNEL = os.path.join(ROOT, "kernel", "kernel.asm")
DOC = os.path.join(ROOT, "docs", "KERNEL-MEMORY.md")
BEGIN = "<!-- kernsize:begin -->"
END = "<!-- kernsize:end -->"

# The sections an author can actually move a byte into, in the order the
# ladder lays them out.  `ovl` is here because it has to be watched, not
# because it costs anything: the boot overlay lands in the FAT window and is
# overwritten by the first mount (SPEC.md 2.5), so its rung is somebody
# else's.  It still has a ceiling - see the guard on OVL_SIZE.
SECTIONS = ("text", "bss", "cold", "lowbss", "ovl")

# Which rung each section rounds into.  .text and .bss share one; that is why
# a byte moved from .bss to .lowbss can cost 512 rather than saving anything
# (docs/KERNEL-MEMORY.md, "Which guard binds").
RUNGS = (
    ("image", ("text", "bss"), "imgpara"),
    ("cold", ("cold",), "coldpara"),
    ("low", ("lowbss", "stk0"), "lowpara"),
)


def measure(nasm_args=()):
    """The ladder, out of NASM, from kernel.asm's own equations.

    Not re-implemented in Python on purpose: a second opinion about how
    KIMG_PARA rounds is a second opinion that can drift, and this file would
    be the last place anyone looked when it did.
    """
    out_fd, out_path = tempfile.mkstemp(suffix=".bin")
    os.close(out_fd)
    try:
        cmd = ["nasm", "-f", "bin", "-w+error", "-w-error=user", "-DKERNSIZE",
               "-I", os.path.join(ROOT, "kernel") + os.sep,
               "-I", os.path.join(ROOT, "build") + os.sep,
               *nasm_args, "-o", out_path, KERNEL]
        r = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass
    m = re.search(r"\bks: (.*?)(?: \[|$)", r.stderr, re.M)
    if not m:
        return None, (r.stderr.strip() or "nasm produced no ks: line")
    vals = {}
    for pair in m.group(1).split():
        k, _, v = pair.partition("=")
        vals[k] = int(v)
    return vals, None


def rung_bytes(v, para_key):
    return v[para_key] * 16


def rung_used(v, parts):
    return sum(v[p] for p in parts)


def kb(n):
    return f"{n:,}"


def delta(n):
    return f"{n:+,}" if n else "+0"


def report(cur, base, out=sys.stdout):
    """Five lines. The sum first, because that is the number an author
    controls; the rungs second, because that is what the machine feels."""
    p = lambda s: print(s, file=out)

    def d(key):
        return None if base is None else cur[key] - base.get(key, cur[key])

    parts = []
    total = 0
    for s in SECTIONS:
        dv = d(s)
        if dv is not None:
            total += dv
            parts.append(f"{s} {kb(cur[s])} {delta(dv)}")
        else:
            parts.append(f"{s} {kb(cur[s])}")
    p("kernsize: sections   " + "  ".join(parts)
      + (f"   (sum {delta(total)})" if base is not None else ""))

    crossed = []
    cells = []
    for name, members, para in RUNGS:
        size = rung_bytes(cur, para)
        used = rung_used(cur, members)
        slack = size - used
        cell = f"{name} {kb(size)}"
        if base is not None:
            dsz = size - rung_bytes(base, para)
            was = rung_bytes(base, para) - rung_used(base, members)
            cell += f" {delta(dsz)} ({kb(slack)} left, was {kb(was)})"
            if dsz:
                crossed.append((name, rung_bytes(base, para) // 512,
                                size // 512))
        else:
            cell += f" ({kb(slack)} left)"
        cells.append(cell)
    p("kernsize: rungs      " + "   ".join(cells))

    spare = cur["budget"] - cur["ksize"]
    line = (f"kernsize: footprint  KERN_SIZE {kb(cur['ksize'])}"
            f" of KERN_BUDGET {kb(cur['budget'])} -> {kb(spare)} spare"
            f" ({spare // 512} step{'' if spare // 512 == 1 else 's'})")
    if base is not None:
        line += (f", was {kb(base['budget'] - base['ksize'])}"
                 f"  [{delta(cur['ksize'] - base['ksize'])}]")
    p(line)

    seg = cur["text"] + cur["bss"]
    p(f"kernsize: segment    .text+.bss {kb(seg)} of KERN_CODE_MAX"
      f" {kb(cur['codemax'])} -> {kb(cur['codemax'] - seg)} left")

    # The ladder, because every base in it moves whenever a rung does - and
    # the heap's start is the figure every RAM number in this project falls
    # out of (docs/KERNEL-MEMORY.md, "heap KB = int 12h - this").
    ks = cur["kseg"]
    cold = ks + cur["imgpara"]
    fat = cold + cur["coldpara"]
    low = fat + cur["fatpara"]
    p(f"kernsize: ladder     KERNEL {ks:#06x}  COLD {cold:#06x}"
      f"  FAT {fat:#06x}  LOW {low:#06x}  HEAP {cur['kend']:#06x}"
      f" = {cur['kend'] * 16 / 1024:.1f} KB   (heap KB = int 12h"
      f" - {cur['kend'] * 16 / 1024:.1f})")

    if base is None:
        p("kernsize: no baseline in docs/KERNEL-MEMORY.md - run --bless")
    elif crossed:
        for name, a, b in crossed:
            p(f"kernsize: *** the {name} rung CROSSED: {a} -> {b}"
              f" steps of 512 - the machine's RAM moved ***")
    elif total:
        p("kernsize: no rung crossed - the machine pays nothing YET, and the"
          " slack above is what the next feature has left")
    else:
        p("kernsize: unchanged")
    return crossed


def read_baseline():
    try:
        doc = open(DOC).read()
    except OSError:
        return None
    m = re.search(re.escape(BEGIN) + r"(.*?)" + re.escape(END), doc, re.S)
    if not m:
        return None
    try:
        return json.loads(re.sub(r"^```\w*$", "", m.group(1).strip(),
                                 flags=re.M).strip())
    except ValueError:
        return None


def write_baseline(v):
    doc = open(DOC).read()
    body = json.dumps({k: v[k] for k in sorted(v)}, indent=2)
    block = f"{BEGIN}\n```json\n{body}\n```\n{END}"
    new, n = re.subn(re.escape(BEGIN) + r".*?" + re.escape(END), block, doc,
                     flags=re.S)
    if not n:
        print("kernsize: no kernsize markers in docs/KERNEL-MEMORY.md",
              file=sys.stderr)
        return 1
    open(DOC, "w").write(new)
    print("kernsize: baseline blessed in docs/KERNEL-MEMORY.md")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bless", action="store_true",
                    help="rewrite the baseline in docs/KERNEL-MEMORY.md")
    ap.add_argument("--json", action="store_true", help="the raw figures")
    # Anything else is handed to NASM verbatim - parse_known_args rather than
    # a positional, because the knobs arrive looking like options
    # (-DVID_FORCE=3) and argparse would claim them.
    a, nasm_args = ap.parse_known_args()

    cur, err = measure(nasm_args)
    if cur is None:
        # NEVER fail the build: an overrun is the guards' job to refuse, and a
        # reporter that can break `make` is a reporter someone will delete.
        print(f"kernsize: could not measure ({err.splitlines()[-1][:120]})",
              file=sys.stderr)
        return 0

    if a.json:
        print(json.dumps({k: cur[k] for k in sorted(cur)}, indent=2))
        return 0
    if a.bless:
        if nasm_args:
            print("kernsize: refusing to bless a knob build - the baseline is"
                  " the SHIPPED kernel", file=sys.stderr)
            return 1
        report(cur, read_baseline())
        return write_baseline(cur)
    report(cur, read_baseline())
    return 0


if __name__ == "__main__":
    sys.exit(main())
