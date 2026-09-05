#!/usr/bin/env python3
"""os88build - a PRIVATE build tree per knob, so a test never clobbers `build/`.

    import os88build
    t = os88build.tree("NOPLANE=1").apply()     # builds (or reuses), and
    img = t.img("os8088-360.img")               # points os88sym at it
    with os88marty.launch(img, apps=t.img("apps360.img")) as m:
        ...

`.apply()` IS THE CALL, not `env=`. `os88marty.launch` takes no `env`
argument - the emulator needs no environment, the SYMBOL READER does - so
`launch(..., env=t.env)` is a TypeError in the row's first second, which is
how three converted rows failed. `t.env` is for a SUBPROCESS you spawn
yourself; inside one process, `apply()` sets both the environment and
os88sym's module default, which is the half `env` cannot reach.

    python3 tools/os88build.py list             # what trees exist
    python3 tools/os88build.py clean            # remove them all

WHY THIS EXISTS, and it is the whole `builds=True` problem.

A row that wants a knob kernel had exactly one place to put it: `build/`.  So
it ran `make NOPLANE=1`, used the result, and ran a bare `make` in a `finally`
to put the tree back - two full builds for one measurement, and in between,
`build/kernel.bin` was a kernel nobody else asked for.  Any other row reading
the tree in that window drives a kernel its symbol map describes perfectly and
that nobody wanted.  That is why fifty-eight rows are marked `builds=True`,
why they run ONE AT A TIME however wide the lane, and why they are the floor
of a soak that no amount of parallelism improves: 3.3 declared hours.

It is also, less obviously, the whole reason `tools/martylock.py` existed.  Two
agents in one checkout could not both work, because either might `make`.  Take
away the shared destination and the hazard goes with it.

THE FIX IS FOUR LINES OF MAKEFILE THAT WERE ALREADY THERE.  `$(BUILD)` is a
variable and the Makefile uses it 965 times; `make BUILD=<dir>` has always
worked and produces a BYTE-IDENTICAL image (verified against the in-tree
build).  `tools/os88sym.py` has honoured `$OS88_BUILD` and `$OS88_DEFINES` for
just as long.  Nothing had to be invented - what was missing was somewhere to
put the trees and a helper that made using one shorter than not.

WHAT THIS GUARANTEES, and it is worth being precise because the old rule was
"one build at a time, globally":

  * two rows with DIFFERENT knobs never touch the same file;
  * two rows with the SAME knobs share one tree, and the second waits only
    for the first's BUILD, not for its run;
  * `build/` itself is never written by a row at all, so a person or another
    agent may `make` in the checkout while a soak runs.

THE LOCK IS `flock`, HELD ONLY ACROSS THE BUILD, and that is the argument for
deleting `martylock.py` rather than reusing it.  A lease was needed there
because a holder worked across many shells and PID liveness could not answer
"is the holder alive".  A build lock is taken and released inside ONE process,
so the kernel releases it when that process dies, however it dies - no lease,
no expiry, no `break` command, nothing to get wedged and nothing an agent has
to remember.

THE DEFINES ARE DERIVED, NEVER RESTATED.  A knob's make VARIABLE and its nasm
DEFINE are not the same string - `VGADIRTY=1` compiles `-DVGA_DIRTY` - and
`os88sym` needs the define, or it re-assembles a different kernel and refuses
the map with a message about a stale build.  That trap cost this file's author
twenty minutes before it was written down, so `defines` comes out of `make -n`
on the kernel target and nobody has to know the mapping.
"""
import errno
import fcntl
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Under build/, so `make clean` sweeps them and .gitignore already covers it.
# A tree is ~1.2 MB - the whole shipped set of images and packages - so twenty
# of them is 24 MB and disk is not a consideration here.
TREES = os.path.join(ROOT, "build", "trees")

# What a row almost always wants: the 360KB pair, which is what MartyPC's
# machines mount. Named here rather than defaulted per call site so that two
# rows asking for "the same knob" really do share a tree.
DEFAULT_TARGETS = ("os8088-360.img", "apps360.img")


class Tree(object):
    """One private build directory, and how to point a test at it."""

    __slots__ = ("dir", "args", "defines", "targets")

    def __init__(self, d, args, defines, targets):
        self.dir, self.args = d, tuple(args)
        self.defines, self.targets = tuple(defines), tuple(targets)

    def img(self, name):
        return os.path.join(self.dir, name)

    @property
    def env(self):
        """The environment a symbol reader needs to describe THIS kernel.

        Both halves are required and each fails differently without the other:
        without `OS88_BUILD` the identity check compares this map against
        `build/kernel.bin` and refuses; without `OS88_DEFINES` it re-assembles
        the plain kernel and refuses against the knob's image. The refusal is
        right both times - a map of a different kernel is a wrong answer, not
        a missing one - which is exactly why it is worth handing out ready-made.
        """
        e = dict(os.environ)
        e["OS88_BUILD"] = self.dir
        if self.defines:
            e["OS88_DEFINES"] = " ".join(self.defines)
        return e

    def apply(self):
        """Point THIS process's symbol reader at this tree, and return self.

        Call it before the first `syms()`, and call it again when switching
        arms - os88sym caches on (directory, defines), so the two arms of an
        A/B get different entries and neither is stale.

        IT SETS THE MODULE DEFAULT AS WELL AS THE ENVIRONMENT, and that is the
        half a row cannot do for itself. A row threading `defines` through its
        own lookups still calls LIBRARY helpers that do not take them -
        `os88marty.no_saver` resolves `ss_idle`, `Marty.sym` resolves whatever
        it is asked for - and those go to os88sym's module default. Setting
        only `OS88_BUILD` therefore fails exactly where the row is not
        looking: `blitcut` died inside `no_saver`, three frames below its own
        code, with a message about a stale build.
        """
        os.environ["OS88_BUILD"] = self.dir
        os.environ.pop("OS88_DEFINES", None)
        if self.defines:
            os.environ["OS88_DEFINES"] = " ".join(self.defines)
        import os88sym
        os88sym.default_defines(*self.defines)
        return self

    def __repr__(self):
        return "<Tree %s %s>" % (os.path.relpath(self.dir, ROOT),
                                 " ".join(self.args) or "plain")


def plain():
    """The SHARED tree as a Tree - for the other arm of an A/B.

    A row that compares a knob kernel against the shipped one needs to put the
    symbol reader back between the two, and `plain().apply()` is that. It
    builds nothing and writes nothing: the shared tree is what `make`
    maintains and what a row may READ, and the whole point of this module is
    that a row never writes it.

    **"SHARED" IS `at("build")` AND NOT LITERALLY `build/`** (14.2). Under a
    frozen run the directory every row reads is the run's own tree, so
    answering `build/` here would send exactly the rows that take an A/B -
    blitcut, blitplane, dispseam, curdisk, fatwpin, kzboot - back to the
    operator's directory for their SHIPPED arm while the knob arm came out of
    a tree. That is the one arrangement worse than either: half a row against
    a directory somebody may be building in, and only on the arm that is
    supposed to be the control. With $OS88_BUILD unset this is `build/`, which
    is what every interactive run gets.
    """
    root = os.environ.get("OS88_BUILD")
    return Tree(os.path.abspath(root) if root else os.path.join(ROOT, "build"),
                (), (), DEFAULT_TARGETS)


def _key(args, targets):
    """A stable directory name for one (knobs, targets) pair.

    The knobs are SORTED, so `make A=1 B=1` and `make B=1 A=1` are one tree
    rather than two identical ones - and the hash covers the targets too,
    because a tree built for `os8088.img` has not got `os8088-360.img` in it
    and reusing it would hand a row a path that does not exist.
    """
    tag = "-".join(a.split("=")[0].lower() for a in sorted(args)) or "plain"
    h = hashlib.sha1(("\0".join(sorted(args)) + "|"
                      + "\0".join(sorted(targets))).encode()).hexdigest()[:8]
    return "%s-%s" % (tag[:40], h)


# A TREE PAYS FOR ITS OWN ASSEMBLY AND NOTHING ELSE.
#
# Not this file's idea: `tests/unit/t_buildmatrix.py` found it, uses it for all
# 81 of its rows, and its header is the account - each row used to be a whole
# cold build "of which the assembly under test was under a third". Both
# variables here are gates whose answer is a function of `kernel/` alone, so
# running them once per tree is one answer N times:
#
#   NOOVLCHK=1    the overlay gate takes no argument and expands no %ifdef.
#   NOKERNSIZE=1  the size REPORT, which the Makefile's own comment calls "the
#                 single most expensive thing in a knob build and pure waste
#                 when the caller is going to discard the text" - it
#                 RE-ASSEMBLES the finished kernel to measure it.
#
# NEITHER CHANGES A BYTE of any kernel, which is the property that makes them
# safe, and `tests/unit/t_bmshare.py` is the gate that asserts it. Neither is
# in $(KNOBS) or the build stamp, for the same reason.
#
# `ICODIR=build` is the third variable that pair uses and it is NOT here: it
# shares the default build's packages, which is right for a knob that reaches
# only the kernel and WRONG for one in $(PKGSBDEF), and getting that
# distinction wrong means a row silently no longer assembling the package it
# exists for. t_buildmatrix derives the exclusion from the Makefile; a tree
# here does not know which knob it was given, so it pays for its own packages.
NO_GATES = ["NOOVLCHK=1", "NOKERNSIZE=1"]


# The two things a private tree must NOT rebuild, and may share.
#
# Both are PINNED UPSTREAM ARTEFACTS - `tools/martypc/UPSTREAM` names a commit,
# `tools/setup-cc.sh` fetches SmallerC at one - so every tree's copy would be
# identical by construction, and `make clean` deliberately spares both. The C
# one is not optional: `CC_SC := $(BUILD)/cc/SmallerC`, so a tree without the
# link fails any C package with "The C compiler is not built. Run
# tools/setup-cc.sh" - which is true of that directory and false of the
# checkout, and reads as a broken machine.
#
# NOTHING ELSE MAY BE SHARED. docs/plans/completed/HANDOFF-KERNEL-SIZE-P3.md 3 says why in one
# line: a shared writable DISK is what contaminated pass 2's first bisect.
SHARED = ("cc", "martypc")


def _sweep_truncated(d):
    """Delete zero-length build products before make looks at the tree.

    A TREE LEFT HALF-BUILT IS POISON, and make cannot see it. An interrupted
    `make` - a timeout, a killed agent, a container reclaimed - can leave an
    output file created and empty, and an empty file is NEWER than everything
    it was built from: make reports the tree up to date and the next consumer
    fails somewhere else entirely. Measured: `build/trees/plain-1c902f1e`
    kept a 0-byte `kernel-full.bin`, and `t_buildmatrix`'s `make small` row
    failed with `os88mod: kernel image is impossibly short` - which reads as
    kern_small being broken and is a truncated file nobody rebuilt.

    A zero-length product is never legitimate here (every rule in the
    Makefile writes bytes), so removing it is safe and make does the rest.
    One `listdir` per tree, only at the top level, which is where every
    artefact a row asks for lives.
    """
    try:
        names = os.listdir(d)
    except OSError:
        return
    for n in names:
        p = os.path.join(d, n)
        try:
            if os.path.isfile(p) and not os.path.islink(p) \
                    and os.path.getsize(p) == 0:
                os.remove(p)
        except OSError:
            pass


def _share_instruments(d):
    """Link the pinned instruments into a tree rather than rebuilding them."""
    for name in SHARED:
        src = os.path.join(ROOT, "build", name)
        dst = os.path.join(d, name)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                os.symlink(src, dst)
            except OSError:
                pass


def _goals(d, targets):
    """Turn a row's `targets` into make goals against the private tree.

    Two kinds, told apart by whether the name looks like a FILE:

      * `os8088-360.img` is an artefact, and make wants it by path, so it is
        joined onto the tree - `make BUILD=<d> <d>/os8088-360.img`;
      * `small` is a PHONY target whose own prerequisites are already spelled
        `$(BUILD)/...`, so joining it would ask make for a file that has no
        rule. It is passed verbatim and `BUILD=<d>` does the rest.

    The test is a dot in the last path component, which is what every artefact
    in this tree has and no phony target does.
    """
    out = []
    for t in targets:
        out.append(os.path.join(d, t) if "." in os.path.basename(t) else t)
    return out


class _Lock(object):
    """flock on one tree's own lock file, held across the build and no longer.

    Per TREE and not global: two rows with different knobs never meet here,
    and two with the same knob meet for the length of one `make` - after which
    both read the same finished tree.

    The kernel drops it when the holder exits, so there is no lease to expire,
    nothing to renew, and no way to leave one behind. That is the property
    `martylock.py` could not have and had to work around with leases: it was
    held ACROSS many shells, so no PID could answer for it.
    """

    def __init__(self, path):
        self.path, self.fh = path, None

    def __enter__(self):
        d = os.path.dirname(self.path)
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        self.fh = open(self.path, "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        finally:
            self.fh.close()
            self.fh = None


# THE COMPRESSED KERNEL'S FOUR DEFINES ARE NOT REPORTED, and that is the
# Makefile's rule rather than this one's: `$(KZDEF)` on the assembler line is
# PASS ONE'S PLACEHOLDERS (KZ_SECS=0, KZ_RPARA=0), and `build/kernel.bin` on
# disk is pass TWO - re-assembled with the real numbers by the `kernel.sys`
# rule (SPEC.md 2.9.13). So the line `make -n` prints is the one set of values
# that is certainly wrong for the image a map gets checked against. The
# Makefile says who owns them - "a tool that re-assembles the kernel for a
# SYMBOL MAP reads the same json itself" - and tools/os88sym.py does exactly
# that, from build/kernel.kz.json, but only if nobody has already named KZIP.
# Reporting them therefore did not merely pass stale numbers, it TOOK THE JSON
# OUT OF PLAY: `KZIP` with no value at all reached nasm and boot2.asm answered
# six "expression syntax error"s about a kernel that builds perfectly.
def _kz(d):
    n = d.split("=")[0]
    return n == "KZIP" or n.startswith("KZ_")


def defines_for(args, target="kernel-full.bin", build=None):
    """The nasm defines `make <args>` would compile the kernel with.

    ASKED, never restated. A knob's make variable and its nasm define differ
    often enough to be a trap - VGADIRTY=1 gives -DVGA_DIRTY, and passing the
    variable name to os88sym re-assembles the PLAIN kernel and refuses the map
    with a message about a stale build, which reads as "run make" and is not.

    A DEFINE'S VALUE IS PART OF IT. Ten knobs assemble to `-DX=<n>` rather
    than a bare `-DX` (RTC=, QUANTUM=, HERCSEG=, SBRATE=, ...), and a name
    without its number re-assembles a DIFFERENT kernel - or, where the value
    is what an expression is built from, no kernel at all. `_kz` below is the
    one family deliberately left out, for a reason of its own.

    **`make -n` IS NOT A DRY RUN OF THE MAKEFILE'S PARSE**, and this function
    was written with a bug that proves it. Two `$(shell ...)` assignments run
    at parse time whatever goal is asked for and whatever `-n` says:

      * `BUILDNUM` regenerates `$(BUILD)/buildnum.inc`; harmless.
      * `$(VIDSTAMP)`'s rule **deletes `$(BUILD)/kernel.bin`, kernel-full.bin,
        three drivers and every boot sector** whenever the knob set differs
        from the one that built that directory. That is deliberate - it is
        what stops a knob build silently booting the previous configuration -
        and it means a `make -n` with a knob in it, pointed at `build/`, is a
        DESTRUCTIVE command.

    The first draft defaulted `build` to `build/`, and `os88build.py defines
    NOPLANE=1` duly emptied the shared tree. So the directory is REQUIRED to
    be a private one: passing none makes a throwaway rather than reaching for
    the default. `tools/os88fixture.py` carries the same warning from the
    other end ("DO NOT CALL IT FROM A KNOB GATE") and it is the same trap.

    `--always-make` because an up-to-date tree prints no recipe at all, and
    the recipe is the whole answer. It costs nothing under `-n`.
    """
    tmp = None
    if build is None:
        tmp = tempfile.mkdtemp(prefix="os88def")
        build = tmp
    b = build
    try:
        rel = os.path.relpath(b, ROOT) if not b.startswith(tempfile.gettempdir()) else b
        out = subprocess.run(["make", "-n", "--always-make", "BUILD=%s" % rel]
                             + list(args) + [os.path.join(rel, target)],
                             cwd=ROOT, capture_output=True, text=True).stdout
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    for line in out.replace("\\\n", " ").splitlines():
        if "nasm" in line and "kernel.asm" in line and " -o " in line:
            return tuple(d for d in
                         (m.group(1) for m in
                          re.finditer(r"-D([A-Za-z_][A-Za-z_0-9]*(?:=[^\s]+)?)",
                                      line))
                         if not _kz(d))
    return ()


def at(path):
    """A `build/...` path, resolved against $OS88_BUILD.

    **THE ONE THING THAT LETS A SOAK SURVIVE SOMEBODY ELSE'S `make`**
    (docs/plans/completed/SOAK-PARALLEL.md 14.2). Rows name `build/os8088-360.img` and its
    siblings as literal strings - 725 of them across 256 files, and 356 are
    those two images - so pointing a run at a frozen tree cannot be done by
    editing the callers. It is done where the path is USED instead, and there
    are few of those: os88marty's launch stages both floppies in one loop,
    `scratch_disk` reads its inputs in another, and os88sym has honoured
    $OS88_BUILD since it was written.

    Anything that is not under `build/` is returned unchanged, so a row that
    names /tmp, an absolute path or a private tree of its own is untouched -
    and with $OS88_BUILD unset this is the identity function, which is what
    every interactive run and every standalone `python3 tests/x.py` gets.

    It resolves the string, not the file: a path that does not exist in the
    tree comes back pointing into the tree, and the caller's own open() says
    so. Falling back to `build/` on a miss would be worse - it would half-run
    a soak against the directory the tree exists to avoid, and only sometimes.
    """
    root = os.environ.get("OS88_BUILD")
    if not root or not isinstance(path, str):
        return path
    q = path.replace("\\", "/")
    if q == "build" or q.startswith("build/"):
        return os.path.join(root, q[len("build/"):]) if q != "build" else root
    return path


def tree(*args, **kw):
    """Build (or reuse) a private tree for these make arguments.

        t = os88build.tree("NOPLANE=1")
        t = os88build.tree("VGADIRTY=1", targets=("os8088.img", "apps.img"))

    Reuse is `make`'s own: the directory persists, so a second call with the
    same knobs re-runs make over an up-to-date tree and returns in under a
    second. Deleting the directory is always safe.
    """
    targets = tuple(kw.pop("targets", DEFAULT_TARGETS))
    quiet = kw.pop("quiet", True)
    if kw:
        raise TypeError("tree() got %s" % ", ".join(sorted(kw)))
    args = tuple(a for a in args if a)

    d = os.path.join(TREES, _key(args, targets))
    with _Lock(d + ".lock"):
        try:
            os.makedirs(d)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        _sweep_truncated(d)
        _share_instruments(d)
        # RELATIVE, and it has to be. The Makefile spells the C toolchain's
        # PATH as `$(CURDIR)/$(CC_SC)` where `CC_SC := $(BUILD)/cc/SmallerC`,
        # so an ABSOLUTE BUILD produces `$(CURDIR)//tmp/...` - a path that
        # does not exist - and every C package fails with `smlrpp` not found
        # rather than with anything about the directory. make runs with
        # cwd=ROOT here, so a relative BUILD is the same tree and the
        # concatenation comes out right.
        rel = os.path.relpath(d, ROOT)
        cmd = (["make", "BUILD=%s" % rel] + NO_GATES + list(args)
               + _goals(rel, targets))
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(
                "os88build: `%s` failed:\n%s%s"
                % (" ".join(cmd), r.stdout[-2000:], r.stderr[-2000:]))
        if not quiet:
            sys.stderr.write(r.stdout)
        defines = defines_for(args, build=d)
    return Tree(d, args, defines, targets)


def _cli():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("verb", nargs="?", default="list",
                    choices=["list", "clean", "build", "defines"])
    ap.add_argument("args", nargs="*", help="make arguments, for build/defines")
    a = ap.parse_args()
    if a.verb == "list":
        if not os.path.isdir(TREES):
            print("os88build: no private trees")
            return 0
        tot = 0
        for n in sorted(os.listdir(TREES)):
            p = os.path.join(TREES, n)
            if not os.path.isdir(p):
                continue
            sz = sum(os.path.getsize(os.path.join(p, f))
                     for f in os.listdir(p)
                     if os.path.isfile(os.path.join(p, f)))
            tot += sz
            print("  %-44s %6.1f MB" % (n, sz / 1e6))
        print("os88build: %.1f MB in %s" % (tot / 1e6,
                                            os.path.relpath(TREES, ROOT)))
    elif a.verb == "clean":
        shutil.rmtree(TREES, ignore_errors=True)
        print("os88build: removed %s" % os.path.relpath(TREES, ROOT))
    elif a.verb == "defines":
        print(" ".join(defines_for(a.args)) or "(none)")
    else:
        t = tree(*a.args, quiet=False)
        print("os88build: %s\n  defines: %s" % (t.dir, " ".join(t.defines)))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
