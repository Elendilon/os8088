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

TWO RULES, and both are hard zeros:

  1. **No `DBSS` row is conditional.**  A row that only some builds emit
     belongs to a host, and a host's rows are `HBSS` - a second accumulator
     based above the core's block, where a host may have as many or as few as
     it likes.
  2. **No `HBSS` row is named from inside the core.**  `%ifndef DOS_EXTCORE`
     marks the core's spans (§96.44); a core routine that reads a host cell
     would resolve it through `dos_hbss`, which is only where it is in THIS
     host.

VERIFIED TO FAIL: turning any `HBSS` row back into a `DBSS` one inside the
packet driver takes rule 1 red naming the row; reading `[dos_win]` from a core
proc takes rule 2 red naming the proc.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import check, done                               # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SRC = os.path.join(ROOT, "apps", "dos", "dos.asm")
OPEN = re.compile(r"^%(?:if|ifdef|ifndef)\b")


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
    done("t_dosbss")


if __name__ == "__main__":
    sys.exit(main())
