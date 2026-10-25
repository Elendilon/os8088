#!/usr/bin/env python3
"""RealDMG's recompiler on kern_mega: right, and with no #GP in the core
(docs/REALDMG-SPEC.md section 16.2.4).

    python3 tests/rdgmega.py                 the row
    python3 tests/rdgmega.py --keep          ...and leave the E9 log and shots
    python3 tests/rdgmega.py --pkg F.O88     run another REALDMG.O88 (the one
                                             before a change) - reports, does
                                             not gate

kern_mega COMPLETES a far jump through a data segment (mega_gpfix) and a
write through a code selector (mega_gpw), each with an exception - ~1,200
clocks on a 286. RealDMG's core runs with SS:SP the GAME BOY's stack, so a
fault taken in the core also pushes its frame into the game's own memory:
the core entered through its data segment once an event, and the recompiler
chained through its cache's data segment and patched its links through CS.
Before 16.2.4, blargg's cpu_instrs under the recompiler took 87,703 traps in
ten seconds and then looped in test 01 for good; Kirby's Dream Land's
attract took two million in a minute.

It boots `make megatrap`'s kernel (a private tree; every completed #GP is a
line on E9) under Bochs, the one emulator here that enforces a 286's segment
rules (docs/BOCHS.md), with B: holding REALDMG.O88 and cpu_instrs
(tools/getgbtest.py's, never committed), double-clicks the ROM - the
recompiler is the default CPU - and reads the bytes the game sent on its
link port out of the package's view (RDG_SERBUF, through rdg_viewseg off
the package's listing) until it says "Passed all tests" or LIMIT runs out:

  * cpu_instrs must PASS - all eleven, under the recompiler;
  * no trap may be charged to an image other than REALDMG's region: the core
    and the cache segments take none (the region's own, at init and a lossy
    toggle, are allowed up to REGION_ALLOW);
  * and no kern_mega FAULT.

THE FAILING CASE (docs/WRITING-TESTS.md 1): `--pkg` with the REALDMG.O88
from before 16.2.4 (the base of this change) - measured red when this was
written: tens of thousands of traps charged to the core and the cache, and
cpu_instrs stuck in test 01.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88bochs  # noqa: E402
import os88build  # noqa: E402
import megatraps  # noqa: E402

LIMIT = 150                     # seconds for cpu_instrs to finish (~45 s)
REGION_ALLOW = 200              # the region's own: rdg_init's two words, the
                                # lossy picture's patch (rdg_lpatch, ~90)
RDG_STATE = 0x4000
S_SERN = RDG_STATE + 0x64
RDG_SERBUF = 0x4700


def label_off(lst, name):
    for line in open(lst, errors="replace"):
        m = re.match(r"\s*\d+\s+([0-9A-F]{8})\s+\S+\s+(?:<\d+>\s+)?%s\s"
                     % name, line)
        if m:
            return int(m.group(1), 16)
    sys.exit("rdgmega: %s not in %s" % (name, lst))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--pkg", help="the REALDMG.O88 to run (default: the "
                    "tree's)")
    a = ap.parse_args()
    subprocess.check_call([sys.executable,
                           os.path.join(ROOT, "tools", "getgbtest.py")],
                          stdout=subprocess.DEVNULL)
    import getgbtest
    rom = os.path.join(getgbtest.DEST, "cpu_instrs", "cpu_instrs.gb")
    t = os88build.tree("MEGATRAP=1", targets=(
        "mega.img", "megarun.o88", "mbr.bin", "realdmg.o88"))
    out = os.path.join(t.dir, "rdgmega")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    pkg = os.path.join(out, "REALDMG.O88")
    shutil.copy(a.pkg or t.img("realdmg.o88"), pkg)
    gb = os.path.join(out, "CPUINSTR.GB")
    shutil.copy(rom, gb)
    viewoff = label_off(os.path.join(t.dir, "realdmg.lst"), "rdg_viewseg")
    disk = os.path.join(out, "rdgmega.img")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "os88disk.py"),
                    "-o", disk, "--size", "1440", "--folder", "SYSTEM/APPDATA",
                    "REALDMG:" + pkg, "REALDMG:" + gb],
                   check=True, stdout=subprocess.DEVNULL)
    t0 = time.time()
    box = os88bochs.Box(out, [], bimg=disk, btype="1_44", build=t.dir)
    fails, text = [], ""
    try:
        if not box.wait_for("kern_mega: protected mode", 300):
            print("FAIL: kern_mega never reached protected mode")
            return 1
        box.up()
        box.capture()
        box.dbl(591, 105, "B:'s Disk window")
        box.dbl(150, 123, "the REALDMG folder")
        mark = os.path.getsize(box.e9)
        box.dbl(160, 139, "the game to start", lock=False)   # CPUINSTR.GB
        end = time.time() + LIMIT
        view = None
        while time.time() < end:
            time.sleep(3)
            if any(l.startswith("kern_mega FAULT") for l in box.lines()):
                break
            if view is None:
                base = box.pkg_base("RealDMG")
                if base is None:
                    continue
                view = int.from_bytes(box.read(base + viewoff, 2), "little")
                if not view:
                    view = None
                    continue
            n = box.read(view * 16 + S_SERN, 1)[0]
            text = box.read(view * 16 + RDG_SERBUF, max(n, 1))[:n] \
                .decode("latin-1")
            if "Passed" in text or "Failed" in text:
                break
        box.shot(os.path.join(out, "end.png"))
    finally:
        box.stop()
    with open(box.e9, "rb") as f:
        f.seek(mark)
        tail = f.read().decode("latin-1").splitlines()
    for l in tail:
        if l.startswith("kern_mega FAULT"):
            fails.append("a kern_mega FAULT: %s" % l)
    traps = [l.split() for l in tail if l.startswith("T ")]
    # T <err> <CS:IP> <image> <DS/ES...> <name>: the image is the 4th field
    region = [x for x in traps if x[-1] == "REALDMG"]
    other = [x for x in traps if x[-1] != "REALDMG"]
    print("rdgmega: serial %r" % " ".join(text.split()))
    print("rdgmega: %d traps after the launch - %d the region's, %d the "
          "core's or a cache's; %.0fs under Bochs"
          % (len(traps), len(region), len(other), time.time() - t0))
    if "Passed all tests" not in text:
        fails.append("cpu_instrs did not pass under the recompiler in %ds "
                     "(its link port said %r)" % (LIMIT, text[-60:]))
    if other:
        fails.append("%d traps charged to the core or a cache segment, the "
                     "first `%s` (tools/megatraps.py %s)"
                     % (len(other), " ".join(other[0]), box.e9))
    if len(region) > REGION_ALLOW:
        fails.append("%d traps charged to REALDMG's region (%d allowed)"
                     % (len(region), REGION_ALLOW))
    if a.pkg:
        for f in fails:
            print("would FAIL: " + f)
        return 0
    for f in fails:
        print("FAIL: " + f)
    if not fails and not a.keep:
        shutil.rmtree(out, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
