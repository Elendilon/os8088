"""Build a test's own fixture before it runs (tests/suite.py).

    from os88fixture import need
    need("build/muptest.img")

WHY THIS EXISTS.  `all` does not build anything under `tests/` and nothing
there ships, so a gate whose scratch disk is one of those artifacts finds
nothing on a clean tree: it dies in `os88marty.launch`'s copy with a
FileNotFoundError, in about a tenth of a second, before it has reached the
emulator at all.  That is not a failing gate, it is an ABSENT one - and it
reads as a failing one, which is worse than either.  Seven registered rows
were in that state (drvcall, fdlgup, mouseup, calcflick, fsxdisp, heapcheck,
trkrate); tests/unit/t_registry.py's UNREGISTERED list is the other honest
answer to the same question, and the one the browser and socket gates take.

`make` IS THE DEPENDENCY GRAPH, so this asks it rather than open-coding the
nasm/os88pkg/os88disk ladder each fixture needs.  A fixture embeds the SDK
(apps/os88api.inc, apps/os88ui.inc), so a cached one built against an earlier
kernel is exactly the stale-scratch-disk trap tests/dispclose.py warns about
- and make's own rules already name those includes as prerequisites, so
asking make is what keeps that true rather than a comment promising it.

It does NOT delete the artifact first.  Where a test WRITES to its own image
- QEMU mounts one writable - the guest's write leaves it newer than
everything it was built from and make cannot see the difference, so that test
removes the file itself before calling here; tests/brnav.py is the worked
example.  MartyPC's launch copies each floppy into the run directory, so the
gates that go through it never dirty the original.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def need(*targets):
    """Run `make` for each target, from the repo root. Exits on failure."""
    for t in targets:
        r = subprocess.run(["make", "-s", t], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit("%s: `make %s` failed:\n%s%s"
                     % (os.path.basename(sys.argv[0]) or "os88fixture",
                        t, r.stdout, r.stderr))
