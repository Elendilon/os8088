#!/usr/bin/env python3
"""The small build of a package must cost the SHIPPED one nothing (SPEC.md 27.16).

    python3 tests/unit/t_appsmall.py

`make smallapps` assembles a package a second time with -DAPP_SMALL, and two
claims hang off that. Both fail silently, which is why they are here.

**One: the gate costs the full build ZERO.** It is the same claim
docs/KERN-SPLIT-PLAN.md 6 set for the first removal from `kern_small`, and it
fails the same way - a `%ifdef` written round one line too many, or a field
moved out of a gated block "while we are here", and the shipped package
changes for a feature it still has. Nothing errors. So this ASSEMBLES THE
PACKAGE BOTH WAYS and compares the default arm against `build/<pkg>.o88`
byte for byte.

**Two: the small build is actually smaller.** A gate that stops reaching the
source is a gate that carries nothing, and the symptom is a floppy that is
simply the ordinary one under another name - `make smallapps` would still
build, still boot, and still be pointless. The margin below is deliberately
loose: it is here to catch ZERO, not to pin a number that a later feature
would have to keep.

What it does NOT check is behaviour - that a small-built package still edits,
saves and draws. Nothing host-side can: it wants a machine, and
`os8088_5150_gla_128k` under MartyPC is where that is answered.
"""
import hashlib
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import check, done                             # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
ROOT = os.path.abspath(ROOT)

# (package, source, the shipped .o88 it must still equal)
PKGS = [("notepad", "apps/notepad/notepad.asm", "build/notepad.o88"),
        ("paint", "apps/paint/paint.asm", "build/paint.o88"),
        ("calc", "apps/calc/calc.asm", "build/calc.o88")]

# The least a small build must save to be worth having, as a fraction of the
# full build's image + bss. Note Pad's real figure is ~34%; this is a floor
# under "the define stopped reaching the source", not a target.
MIN_SAVING = 0.10


def build(src, out, small):
    cmd = ["nasm", "-f", "bin", "-w+error", "-I", "apps/"]
    if small:
        cmd += ["-DAPP_SMALL"]
    cmd += ["-o", out, src]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, r.stderr.strip()


def claim(path):
    """image + bss - what ONE instance takes out of the heap (SPEC.md 20.1)."""
    with open(path, "rb") as f:
        h = f.read(32)
    return int.from_bytes(h[8:10], "little") + int.from_bytes(h[10:12], "little")


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def main():
    tmp = tempfile.mkdtemp(prefix="appsmall.")
    for name, src, shipped in PKGS:
        full = os.path.join(tmp, name + ".full.bin")
        small = os.path.join(tmp, name + ".small.bin")

        ok, err = build(src, full, False)
        check(ok, "%s assembles with no define" % name, got=err, want="exit 0")
        ok, err = build(src, small, True)
        check(ok, "%s assembles with -DAPP_SMALL" % name,
              "the small arm is built by `make smallapps` and by nothing in "
              "`all`, so this is the only thing keeping it assembling at all",
              got=err, want="exit 0")
        if not ok:
            continue

        shipped_path = os.path.join(ROOT, shipped)
        if os.path.exists(shipped_path):
            check(md5(full) == md5(shipped_path),
                  "%s: the default arm is the SHIPPED bytes" % name,
                  "APP_SMALL must cost the full build nothing. A difference "
                  "here means a %ifdef caught a line it should not have, or a "
                  "bss field moved between blocks - the shipped package has "
                  "changed for a feature it still has",
                  got=md5(full), want=md5(shipped_path))

        cf, cs = claim(full), claim(small)
        saved = (cf - cs) / float(cf) if cf else 0.0
        check(cs < cf, "%s: the small build claims less than the full one" % name,
              "if these match, -DAPP_SMALL has stopped reaching the source and "
              "build/smallapps*.img is the ordinary floppy under another name",
              got="%d vs %d bytes" % (cs, cf), want="smaller")
        check(saved >= MIN_SAVING,
              "%s: the small build saves at least %d%%" % (name, MIN_SAVING * 100),
              "a floor under 'the gates carry nothing', not a target - the "
              "real figure is ~34%% and is allowed to move",
              got="%.1f%%" % (saved * 100), want=">= %d%%" % (MIN_SAVING * 100))
    done("t_appsmall")


if __name__ == "__main__":
    main()
