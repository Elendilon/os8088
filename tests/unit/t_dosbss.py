#!/usr/bin/env python3
"""THE DOS CORE'S bss IS AT THE SAME OFFSETS IN EVERY HOST (SPEC.md 96.44.2).

    python3 tests/unit/t_dosbss.py

docs/plans/KERN-DOS-PLAN.md §4.1.3 puts the INT 21h core in a part both the
box and `kern_dos` join, which means the core is assembled ONCE.  Its state is
reached DS-relative at `os88_image_end + DOS_B_*`, so every one of those
offsets has to come out the same in both builds - and `DOS_B_*` is a running
sum over the `DBSS` rows, so ONE conditional row moves every cell after it.

That is not hypothetical: §96.43.2 gated twenty-nine window rows out of
`kern_dos`, and before this rule existed a thirtieth (`DOS_B_PKTRAW`) sat
inside the packet driver's own `%ifndef KD_BACKEND` - which would have put the
whole tail of the core's state at two different offsets in the two hosts.

FOUR RULES NOW, and all of them are hard zeros. The first three read the
SOURCE's shape; rule 4 assembles all three roots and compares what they came
out as, which is the only one that could have caught what shipped:

  1. **No `DBSS` row is conditional.**  A row that only some builds emit
     belongs to a host, and a host's rows are `HBSS` - a second accumulator
     based above the core's block, where a host may have as many or as few as
     it likes.
  2. **No `HBSS` row is named from inside the core.**  `%ifndef DOS_EXTCORE`
     marks the core's spans (§96.44); a core routine that reads a host cell
     would resolve it through `dos_hbss`, which is only where it is in THIS
     host.

  3. **No host-varying arm inside the core.**  The core is assembled once, so
     a `%ifdef KD_BACKEND` region inside it is one host's code in the other
     host's image: it becomes a `DHK_*` hook the host fills (SPEC.md 96.44.3).

  4. **And the three assemblies AGREE, measured.**  Rules 1-3 are shapes a
     reader can check; this one builds `apps/dos/doscore.asm`, the box
     (`-DDOSKPART -DDOS_EXTCORE`) and `kerndos/kdos.asm`, and requires every
     `DBSS` cell to land at the same offset in all three.

**RULE 4 EXISTS BECAUSE RULES 1-3 ALL PASSED ON A BROKEN BUILD.**  `DVOL_MAX`
went 6 -> 8 in `kernel/disk.inc`; `apps/dos/dos.asm`'s mirror stayed at 6 and
`apps/dos/doscore.asm` defaults to 8 - and `DOS_B_DVCWD` is `2 * DVOL_MAX`
bytes.  The row is not conditional, no core proc names a host cell and there
is no arm inside the core, so every source-shape rule was satisfied while the
core laid that cell out SIXTEEN bytes wide and the box addressed it as TWELVE.
Every core cell after it was four bytes below where the core kept it, in the
WINDOW only - `kern_dos` takes the kernel's 8 through `disk.inc`, so the
handoff was perfect and the console was not: a bare name at the prompt
answered `Bad command or file name` about a program `DIR` had just listed,
`DIR /P` never paged, and a `.O88` would not launch.  A size is as much of the
layout as a row is, and no source rule sees a size.

It is fixed at the source too (SPEC.md 96.44.2.1): the width lives in
`apps/dos/doscall.inc`, which none of the three can be assembled without, and
`DVOL_MAX` is bound-checked against it.  This rule is what says a SECOND such
constant has not appeared.

VERIFIED TO FAIL: turning any `HBSS` row back into a `DBSS` one inside the
packet driver takes rule 1 red naming the row; reading `[dos_win]` from a core
proc takes rule 2 red naming the proc; and putting `DOS_B_DVCWD` back on
`2 * DVOL_MAX` with either copy of that constant moved takes rule 4 red
naming the cell and both offsets.
"""
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import check, done                               # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SRC = os.path.join(ROOT, "apps", "dos", "dos.asm")
OPEN = re.compile(r"^%(?:if|ifdef|ifndef)\b")

# The three roots that join the ONE core, with the include paths and defines
# the Makefile gives each. `kerndos/kdos.asm` needs `kernel/` in front of the
# rest: it %includes the kernel's own disk layer, which is what makes it a
# second host rather than a second copy.
APPINC = ("apps", "apps/dos", "drivers/net", "kerndos")
ROOTS = (
    ("the core", "apps/dos/doscore.asm", (), APPINC),
    ("the box", "apps/dos/dos.asm", ("DOSKPART", "DOS_EXTCORE"), APPINC),
    ("kern_dos", "kerndos/kdos.asm", ("DOS_EXTCORE",),
     ("kernel", "kerndos", "apps", "apps/dos", "drivers/net")),
)


def nasm_map(src, defines, incs):
    """Every symbol one root assembles to, out of nasm's own `[map all]`.

    The source is copied rather than edited, for `tests/dosmap.py`'s reason:
    the map directive is appended to a COPY in a temp directory and the real
    include paths are given with -I, so nothing under apps/ is touched.
    """
    d = tempfile.mkdtemp(prefix="os88dosbss")
    a, mp = os.path.join(d, "x.asm"), os.path.join(d, "x.map")
    with open(a, "w") as f:
        f.write(open(os.path.join(ROOT, src)).read() + "\n[map all %s]\n" % mp)
    args = ["nasm", "-f", "bin", "-w+error", "-o", os.path.join(d, "x.bin")]
    for i in incs:
        args += ["-I", os.path.join(ROOT, i) + os.sep]
    args += ["-D" + x for x in defines] + [a]
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        return None, (r.stderr or r.stdout)[-600:]
    out = {}
    for line in open(mp):
        p = line.split()
        if len(p) == 3:
            try:
                out[p[2]] = int(p[0], 16)
            except ValueError:
                pass
        elif len(p) == 2:
            try:
                out.setdefault(p[1], int(p[0], 16))
            except ValueError:
                pass
    return out, None


def regions(lines, opener):
    """(line index -> True) for every line inside a block `opener` matches."""
    inside, d = [], 0
    for l in lines:
        s = l.strip()
        if d == 0 and opener(s):
            d = 1
            inside.append(False)
            continue
        if d:
            if OPEN.match(s):
                d += 1
            elif s.startswith("%endif"):
                d -= 1
        inside.append(d > 0)
    return inside


def main():
    L = open(SRC).read().split("\n")

    # --- rule 1 -------------------------------------------------------------
    host = regions(L, lambda s: re.match(
        r"^%(ifdef|ifndef)\s+(KD_BACKEND|DOSKPART|DOSTRACE|DOSNET_CARD)\b", s))
    bad = [(i + 1, L[i].strip()) for i in range(len(L))
           if host[i] and re.match(r"^\s*DBSS\s", L[i])]
    check(not bad, "no core DBSS row is conditional",
          "\n".join("  dos.asm:%d  %s" % r for r in bad[:8]) +
          "\n  a row only some builds emit moves every cell after it: make it "
          "HBSS (SPEC.md 96.44.2)")

    # --- rule 2 -------------------------------------------------------------
    hb = {m.group(1) for l in L
          for m in [re.match(r"^([a-z_][a-z0-9_]*)\s+equ\s+dos_hbss\s*\+", l)] if m}
    # ...and anything derived from one
    for l in L:
        m = re.match(r"^([a-z_][a-z0-9_]*)\s+equ\s+([a-z_][a-z0-9_]*)\s*\+", l)
        if m and m.group(2) in hb:
            hb.add(m.group(1))
    core = regions(L, lambda s: s.startswith("%ifndef DOS_EXTCORE"))
    hits, proc = [], "?"
    for i, l in enumerate(L):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", l)
        if m:
            proc = m.group(1)
        if not core[i] or re.match(r"^\s*(DBSS|HBSS)\s", l):
            continue
        for n in re.findall(r"\b([a-z_][a-z0-9_]*)\b", l.split(";")[0]):
            if n in hb:
                hits.append((i + 1, proc, n))
    check(not hits, "no core proc names a host bss cell",
          "\n".join("  dos.asm:%d  %s reads %s" % h for h in hits[:8]) +
          "\n  a host cell is only where it is in THIS host (SPEC.md 96.44.2)")

    # --- rule 3 -------------------------------------------------------------
    # The core is assembled ONCE, so a build-time arm inside it is the box's or
    # `kern_dos`'s and never both.  Five of these stood at W9b - the last
    # screen, the packet driver's poll, the console and the mouse - and each
    # became a host HOOK (SPEC.md 96.44.3).  DOSTRACE and DOSNET_CARD are not
    # on this list: they are build knobs, the same in every host.
    d, arms, kind = 0, [], None
    for i, l in enumerate(L):
        s = l.strip()
        m = re.match(r"^%(ifdef|ifndef)\s+(KD_BACKEND|DOSKPART)\b", s)
        if m:
            if d == 0:
                kind, start = m.group(0), i
            d += 1
            continue
        if d:
            if OPEN.match(s):
                d += 1
            elif s.startswith("%endif"):
                d -= 1
                if d == 0 and core[start]:
                    arms.append((start + 1, kind))
    check(not arms, "no host-varying arm inside the core",
          "\n".join("  dos.asm:%d  %s" % a for a in arms[:8]) +
          "\n  the core is assembled once: make it a DHK_* hook the host "
          "fills (SPEC.md 96.44.3)")

    # --- rule 4: ...and the three assemblies AGREE ---------------------------
    # The only rule that reads what the assembler DID rather than what the
    # source looks like - see the header for why that is the one that matters.
    cells = re.findall(r"^\s*DBSS\s+(DOS_B_[A-Z0-9_]+)", "\n".join(L), re.M)
    maps, errs = {}, []
    for label, src, defines, incs in ROOTS:
        mp, err = nasm_map(src, defines, incs)
        if err:
            errs.append("  %s (%s) did not assemble:\n%s" % (label, src, err))
        maps[label] = mp or {}
    check(not errs, "all three roots assemble", "\n".join(errs))
    if errs:
        return done("t_dosbss")

    base = maps["the core"]
    bad = []
    for label in ("the box", "kern_dos"):
        for n in cells:
            if n in maps[label] and n in base and maps[label][n] != base[n]:
                bad.append("  %-18s %s=0x%04X  the core=0x%04X  (%+d)"
                           % (n, label, maps[label][n], base[n],
                              base[n] - maps[label][n]))
    check(not bad, "every DBSS cell is at one offset in all three hosts",
          "\n".join(bad[:8]) +
          "\n  %d of %d cells disagree. The core is assembled ONCE and both "
          "hosts address it, so a cell that is not at one offset is one host "
          "reading another's bytes - and the first disagreeing name is where "
          "the layouts part (SPEC.md 96.44.2, 96.44.2.1)" % (len(bad), len(cells)))
    done("t_dosbss")


if __name__ == "__main__":
    sys.exit(main())
