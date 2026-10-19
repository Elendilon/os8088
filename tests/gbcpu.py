#!/usr/bin/env python3
"""RealBoy's core against Blargg's CPU and timing ROMs, bare, in QEMU.

    python3 tests/gbcpu.py [-k NAME]

docs/plans/REALBOY-PLAN.md wave 1 and wave 2's `gbcpu` row. Each ROM is
booted on a bare machine through tests/rbcore/rbhost.asm - no os8088 under
the core - and the row reads what the ROM prints on its link port, which the
harness copies to COM1. A ROM passes when it says "Passed".

The ROMs are fetched by tools/getgbtest.py at pinned SHA-256s and never
committed. QEMU counts work exactly and times nothing (docs/TESTING.md), and
this asks it for nothing else: these are CORRECTNESS gates, and the cycle
counts the timing ROMs check are the core's own.

THE NEGATIVE CONTROL, last: the same harness with DAA made a no-op - the
handler's first bytes replaced by a bare dispatch - must make 01-special FAIL.
A gate that cannot go red is a row that tests nothing (docs/WRITING-TESTS.md 1).
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "rbcore"))
import rbimg  # noqa: E402
import rbqemu  # noqa: E402

# (name, ROM as getgbtest names it, frames to allow)
ROMS = [
    ("01-special", "individual/01-", 1200),
    ("02-interrupts", "individual/02-", 600),
    ("03-op sp,hl", "individual/03-", 1200),
    ("04-op r,imm", "individual/04-", 1200),
    ("05-op rp", "individual/05-", 1200),
    ("06-ld r,r", "individual/06-", 600),
    ("07-jr,jp,call,ret,rst", "individual/07-", 600),
    ("08-misc instrs", "individual/08-", 600),
    ("09-op r,r", "individual/09-", 2400),
    ("10-bit ops", "individual/10-", 2400),
    ("11-op a,(hl)", "individual/11-", 3000),
    ("cpu_instrs (all, MBC1)", "cpu_instrs/cpu_instrs", 4200),
    ("instr_timing", "instr_timing", 600),
]
DAA_NOP = "2700:8A3446FFE2"        # mov dh,[si] / inc si / jmp dx


def rom_path(name):
    return subprocess.check_output([sys.executable, os.path.join(ROOT, "tools/getgbtest.py"),
                                    "--path", name], text=True).strip()


def run(label, rom, frames, core, host):
    img = os.path.join(ROOT, "build", "realboy", "gbcpu.img")
    rbimg.make_image(rom, img, frames=frames, core=core, host=host)
    text = rbqemu.run(img, ["Passed", "Failed", "RBHOST DONE", "RBHOST BADOP"],
                      timeout=180, quiet=True)
    last = [l.strip() for l in text.splitlines() if l.strip()][-1:] or ["(nothing)"]
    return "Passed" in text, last[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-k", help="only the ROMs whose name contains this")
    a = ap.parse_args()
    subprocess.check_call([sys.executable, os.path.join(ROOT, "tools/getgbtest.py")])
    out = os.path.join(ROOT, "build", "realboy")
    core, host = rbimg.build_core(False, out), rbimg.build_host(out)
    bad = 0
    for label, name, frames in ROMS:
        if a.k and a.k not in label:
            continue
        ok, last = run(label, rom_path(name), frames, core, host)
        print("%-4s %-24s %s" % ("ok" if ok else "FAIL", label, last))
        bad += not ok
    if not a.k:
        ok, last = run("control", rom_path("individual/01-"), 1200,
                       rbimg.patch_core(core, [DAA_NOP]), host)
        print("%-4s %-24s %s" % ("FAIL" if ok else "ok", "control: DAA broken",
                                 "passed - the gate cannot go red" if ok else "failed, as it must"))
        bad += ok
    print("gbcpu: %s" % ("PASS" if not bad else "%d FAILED" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
