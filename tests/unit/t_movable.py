#!/usr/bin/env python3
"""Every package declares its REGION movable, or says here why it does not.

    python3 tests/unit/t_movable.py

A package's region - the claim its code and its bss live in - is born PINNED
(SPEC.md 66.2), and `OS88_REGION_MOVABLE` is the one line that opts it out.
Until it is written the region is a WALL in the middle of the arena for the
whole life of the instance, and HEAP-UNPIN-PLAN 2.0 is what that costs: a
6KB image standing in the middle of ~125KB of free space, not healing, and
caused by ordinary use.

WHY A RATCHET AND NOT A RULE IN A DOCUMENT. The door opened with six asm
packages through it and the C SDK's crt0 taking every C one along for free -
and twenty-eight asm packages that never declared. Nobody noticed for a cycle,
because the six that DID declare are the ones anybody looks at, and an
undeclared region is invisible from inside the package: nothing refuses,
nothing warns, the program runs perfectly and the heap quietly cannot pack.
That is the same failure shape as SPEC.md 6.6's transparent text, and this is
t_textrules.py's answer to it - the count can only go down, and a package that
will not declare has to say so IN THE DIFF rather than in somebody's head.

TWO CHECKS, BECAUSE HALF A DECLARATION BUYS NOTHING (SPEC.md 66.6.2).
`task_spawn` writes the region's segment into the worker's frame before its
first instruction, so a package that hires one stays pinned however it
declares - `OS88_WORKER_RESTARTABLE` is the other half. A package that
declares the region and spawns a worker has written something INERT, which is
the most expensive shape available: it reads as done. So:

  * `region` - the package does not declare OS88_REGION_MOVABLE at all;
  * `worker` - it hires a worker and does not declare it restartable.

Each needs its own line in tests/movable.txt with a reason. Both turn ONE
WAY: a line for a package that now declares is a FAILURE, so the registry
cannot rot into a list of things that used to be true.

SCOPE IS apps/, which is what "a new app" means - tests/ is instruments, and
one of them (tests/pinme) exists precisely to BE pinned. A C package declares
through apps/cc/crt0.asm and needs no line of its own; that file is asserted
here too, so deleting the call from it fails this row rather than silently
un-declaring seven packages.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import check, done                           # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
REGISTRY = os.path.join(ROOT, "tests", "movable.txt")
CRT0 = os.path.join("apps", "cc", "crt0.asm")

# A package is a file that emits a package header: the SDK macro, or - for a C
# package, whose header crt0.asm emits by hand (73.2) - the include of crt0
# itself. Matched on a real line rather than anywhere, so the SDK's own
# %macro and the prose that quotes it are not packages.
HEADER = re.compile(r"^\s*OS88_HEADER\b", re.M)
CRT0INC = re.compile(r'^\s*%include\s+"cc/crt0\.asm"', re.M)

REGION = re.compile(r"^\s*OS88_REGION_MOVABLE\b", re.M)
WORKER = re.compile(r"^\s*OS88_WORKER_RESTARTABLE\b", re.M)
# ...and the hand-rolled spellings, so a package that calls the slot directly
# is not reported as undeclared. sheet.asm did exactly that for a cycle and a
# grep for the macro called it a gap.
REGION_RAW = re.compile(r"^\s*call\s+OSAPI_MEM_MOVABLE\b", re.M)
# ...and crt0's own, which must be matched EXACTLY rather than by the slot
# name. crt0.asm calls OSAPI_MEM_MOVABLE twice - once for the region and once,
# under CC_HAS_PARTS, for a part's claim - so "crt0 mentions the slot" is a
# check that passes with the region declaration deleted. It was written that
# loose first and the break-it-on-purpose run is what caught it.
CRT0_REGION = re.compile(r"mov\s+dx,\s*cs\s*\n"
                         r"\s*mov\s+ax,\s*cc_regreloc\s*\n"
                         r"\s*call\s+OSAPI_MEM_MOVABLE\b")
WORKER_RAW = re.compile(r"^\s*call\s+OSAPI_TASK_RESTARTABLE\b", re.M)
SPAWN = re.compile(r"^\s*call\s+OSAPI_TASK_SPAWN\b|\bos88_task_spawn\s*\(", re.M)
C_REGION = re.compile(r"\bos88_mem_movable\s*\(")
C_WORKER = re.compile(r"\bos88_task_restartable\s*\(")

KINDS = ("region", "worker")
MINREASON = 12          # a reason, not a shrug


def read(path):
    with open(os.path.join(ROOT, path), errors="replace") as fh:
        return fh.read()


def strip(text):
    """Source with asm and C comments dropped, so prose never counts."""
    out = []
    for ln in text.splitlines():
        t = ln.lstrip()
        if t.startswith((";", "//", "*", "/*")):
            continue
        out.append(ln.split(";")[0])
    return "\n".join(out)


def packages():
    """{package .asm path: [every source file that package owns]}.

    A package's declaration need not be in its main file - thewire's worker is
    declared in wrhttp.inc - so the unit is the DIRECTORY, which is also what
    the tree already means by a package.
    """
    out = {}
    appdir = os.path.join(ROOT, "apps")
    for name in sorted(os.listdir(appdir)):
        d = os.path.join(appdir, name)
        if not os.path.isdir(d) or name == "cc":        # cc/ is the SDK
            continue
        own = []
        for base, _dirs, files in os.walk(d):
            if os.path.basename(base) == "hosttest":     # host-side stubs
                continue
            for f in sorted(files):
                if f.endswith((".asm", ".inc", ".c", ".h")):
                    own.append(os.path.relpath(os.path.join(base, f), ROOT))
        for p in own:
            if not p.endswith(".asm"):
                continue
            body = read(p)
            if HEADER.search(strip(body)) or CRT0INC.search(strip(body)):
                out[p.replace("\\", "/")] = own
    return out


def facts(main, own):
    """(declares_region, has_worker, declares_worker) for one package."""
    blob = "\n".join(strip(read(p)) for p in own)
    is_c = bool(CRT0INC.search(strip(read(main))))
    region = bool(REGION.search(blob) or REGION_RAW.search(blob)
                  or C_REGION.search(blob) or is_c)
    worker = bool(WORKER.search(blob) or WORKER_RAW.search(blob)
                  or C_WORKER.search(blob))
    return region, bool(SPAWN.search(blob)), worker


def registry():
    """{(kind, path): reason} from tests/movable.txt."""
    out, bad = {}, []
    with open(REGISTRY) as fh:
        for n, ln in enumerate(fh, 1):
            raw = ln.rstrip("\n")
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            body, _, reason = raw.partition("#")
            parts = body.split()
            if len(parts) != 2 or parts[0] not in KINDS:
                bad.append((n, raw))
                continue
            out[(parts[0], parts[1].replace("\\", "/"))] = reason.strip()
    return out, bad


def main():
    pkgs = packages()
    reg, bad = registry()

    check(bool(pkgs), "movable: found no packages to check",
          why="the discovery walks apps/*/ for a file emitting a package "
              "header. Finding none means this row is asserting nothing, "
              "which is the one failure a green suite cannot show",
          got="%d package(s)" % len(pkgs), want="the tree's packages")

    for n, raw in bad:
        check(False, "movable: tests/movable.txt line %d is malformed" % n,
              why="one line per exemption: `<kind> <path>  # <reason>`, kind "
                  "being 'region' or 'worker'",
              got=raw.strip(), want="region|worker <path>  # <reason>")

    # The C SDK declares on behalf of every C package, so its call is part of
    # this contract rather than an implementation detail of crt0.
    crt0 = strip(read(CRT0))
    check(bool(CRT0_REGION.search(crt0)), "movable: crt0.asm no longer declares",
          why="every C package inherits its region declaration from "
              "apps/cc/crt0.asm and carries no line of its own (SPEC.md "
              "66.6.1). Removing the call there un-declares all of them at "
              "once, silently - which is why it is asserted here and not "
              "left to the seven packages to notice",
          got="no `mov dx, cs` / `mov ax, cc_regreloc` / "
              "`call OSAPI_MEM_MOVABLE` in " + CRT0,
          want="crt0.asm declares the region movable")

    need = set()
    for main_asm, own in sorted(pkgs.items()):
        region, spawns, worker = facts(main_asm, own)

        if not region:
            need.add(("region", main_asm))
            check(("region", main_asm) in reg,
                  "movable: %s does not declare its region movable" % main_asm,
                  why="SPEC.md 66.6.1: a region is born PINNED and stays a "
                      "wall in the arena for the life of the instance. Add "
                      "OS88_REGION_MOVABLE where your window exists - or a "
                      "'region' line in tests/movable.txt saying WHY not, so "
                      "the choice is in the diff",
                  got="no OS88_REGION_MOVABLE anywhere in the package",
                  want="the declaration, or a registry line with a reason")

        if spawns and not worker:
            need.add(("worker", main_asm))
            check(("worker", main_asm) in reg,
                  "movable: %s hires a worker and never declares it "
                  "restartable" % main_asm,
                  why="SPEC.md 66.6.2: task_spawn wrote this region's segment "
                      "into the worker's frame, so the region is pinned "
                      "however it is declared - a region declaration without "
                      "this one is INERT, and reads as done. Add "
                      "OS88_WORKER_RESTARTABLE at the spawn - or a 'worker' "
                      "line in tests/movable.txt saying why the worker cannot "
                      "be restarted at its entry",
                  got="OSAPI_TASK_SPAWN with no OSAPI_TASK_RESTARTABLE",
                  want="the declaration, or a registry line with a reason")

    # ...and the ratchet turns ONE WAY.
    for (kind, path), reason in sorted(reg.items()):
        if path not in pkgs:
            check(False, "movable: tests/movable.txt names %s, which is not a "
                         "package" % path,
                  why="the registry is checked against the tree so it cannot "
                      "keep a package alive that was renamed or deleted",
                  got=path, want="a package under apps/ emitting a header")
            continue
        check((kind, path) in need,
              "movable: %s is exempt from '%s' and no longer needs to be"
              % (path, kind),
              why="the exemption list only turns one way (SPEC.md 66.6.1's "
                  "ratchet, t_textrules.py's shape). The package declares now, "
                  "so deleting the line is the diff saying the work happened",
              got="a '%s' line in tests/movable.txt" % kind,
              want="no line - the package declares")
        check(len(reason) >= MINREASON,
              "movable: %s's '%s' exemption carries no reason" % (path, kind),
              why="an exemption without an argument is an exemption nobody can "
                  "review or retire. Say what blocks it and what would unblock "
                  "it",
              got="reason %r" % reason,
              want="at least %d characters after the #" % MINREASON)

    print("t_movable: %d package(s); %d declare a movable region, %d exempt; "
          "%d exemption(s) registered in total"
          % (len(pkgs), len(pkgs) - len([k for k in need if k[0] == "region"]),
             len([k for k in need if k[0] == "region"]), len(reg)))
    done("t_movable")


if __name__ == "__main__":
    main()
