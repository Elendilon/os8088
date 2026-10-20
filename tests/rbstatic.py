#!/usr/bin/env python3
"""RealBoy's Static recompiler (REALBOY-SPEC 16.8), bare, in QEMU.

    python3 tests/rbstatic.py [-k NAME]

Each ROM runs TWICE through tests/rbcore/rbhost.asm with b_jit = 2:
- a first pass with the recompiler recording its profile;
- then the game again from its start, the profile preloaded and the block
  table fixed.

A row passes when BOTH passes report "Passed", and the DONE line says that
nothing was translated after the switch ("after 0"). Static is the dynamic
recompiler's own translator run early, so these are the same correctness
ROMs as tests/gbcpu.py, now with the blocks made before the game ran, and
the table never changed while it ran.

Then the two rows the claim "a fixed table translates nothing" rests on,
both on the first ROM with recording broken in the harness (`rt_prfadd`'s
`je` made a `jmp`), so the second pass preloads NOTHING and every hot loop
is a miss:
- the table fixed: "after" must still be 0 - Static with an empty profile
  is the interpreter;
- THE NEGATIVE CONTROL: the table never fixed as well - rt_preload's `mov
  byte [S_JITFIX],1` made 0, which disarms both of its guards, tr_new2's
  and rb_jit's (taking out either alone changes nothing; each covers the
  other). Misses then count, the translator runs in the second pass, and
  "after" must NOT be 0. A gate that cannot go red tests nothing
  (docs/WRITING-TESTS.md 1). With a full profile it could not go red: every
  hot block is preloaded.

Then the cache's SECOND SEGMENT (REALBOY-SPEC 16.2.1), with both segments
squeezed to 1KB of code so the test ROMs, which fit one 64KB segment many
times over, fill both:
- every ROM again, Static, both passes "Passed" and "after 0";
- cpu_instrs translated as it runs: it must pass having moved into the
  second segment twice and so flushed both (the DONE line's "seg2", and
  "flushes" past rt_init's own), which is where code crosses between them;
- THE NEGATIVE CONTROL: the translator's check that a target is in the
  segment being written (rt_exit's `cmp dx,[S_JITSEG] / jne`) made two NOPs,
  so an exit is written as a near jump into the other segment's offsets.
  cpu_instrs must then NOT pass.
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests", "rbcore"))
import rbimg  # noqa: E402
import rbqemu  # noqa: E402

# (name, ROM as getgbtest names it, frames a pass)
ROMS = [
    ("cpu_instrs (all, MBC1)", "cpu_instrs/cpu_instrs", 4200),
    ("instr_timing", "instr_timing", 600),
    ("mem_timing", "mem_timing/mem_timing", 1200),
]
RMW_ROM = "gbrmw"                       # ours: tools/gbprof/gbrmw.asm
# rt_preload's mov byte [S_JITFIX],1 - S_JITFIX is RB_STATE + 0F6h = 40F6h
SETFIX = bytes.fromhex("C606F64001")
# rt_prfadd's first test: cmp word [S_PRFSEG],0 / je - S_PRFSEG is 40F8h
PRFCHK = bytes.fromhex("833EF84000") + b"\x74"

def rom_path(name):
    return subprocess.check_output([sys.executable, os.path.join(ROOT, "tools/getgbtest.py"),
                                    "--path", name], text=True).strip()


# rt_exit's same-segment check: cmp dx,[S_JITSEG] / jne - S_JITSEG is 40CCh
SEGCHK = bytes.fromhex("3B16CC4075")


def run(rom, frames, core, host, jit="static", seg2=False):
    img = os.path.join(ROOT, "build", "realboy", "rbstatic.img")
    rbimg.make_image(rom, img, frames=frames, core=core, host=host, jit=jit,
                     seg2=seg2, squeeze=seg2)
    text = rbqemu.run(img, ["RBHOST DONE", "RBHOST BADOP"], timeout=400, quiet=True)
    if jit != "static":
        m = re.search(r"flushes (\d+) seg2 (\d+)", text)
        return text.count("Passed"), (int(m.group(1)), int(m.group(2))) if m else None
    m = re.search(r"static (\d+) after (\d+)", text)
    return text.count("Passed"), (int(m.group(1)), int(m.group(2))) if m else None


def norec(host):
    """The harness with rt_prfadd recording nothing: its je made a jmp."""
    i = host.find(PRFCHK)
    if i < 0 or host.find(PRFCHK, i + 1) >= 0:
        sys.exit("rbstatic: rt_prfadd's test is not in the harness exactly once")
    host = bytearray(host)
    host[i + len(PRFCHK) - 1] = 0xEB
    return bytes(host)


def crossseg(host):
    """The harness with rt_exit chaining into the other cache segment."""
    i = host.find(SEGCHK)
    if i < 0 or host.find(SEGCHK, i + 1) >= 0:
        sys.exit("rbstatic: rt_exit's segment check is not in the harness exactly once")
    host = bytearray(host)
    host[i + len(SEGCHK) - 1:i + len(SEGCHK) + 1] = b"\x90\x90"
    return bytes(host)


def unfix(host):
    """The harness with rt_preload never fixing the table."""
    i = host.find(SETFIX)
    if i < 0 or host.find(SETFIX, i + 1) >= 0:
        sys.exit("rbstatic: rt_preload's store is not in the harness exactly once")
    host = bytearray(host)
    host[i + len(SETFIX) - 1] = 0
    return bytes(host)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-k", help="only the ROMs whose name contains this")
    a = ap.parse_args()
    subprocess.check_call([sys.executable, os.path.join(ROOT, "tools/getgbtest.py")])
    import gbours
    out = os.path.join(ROOT, "build", "realboy")
    core, host = rbimg.build_core(False, out), rbimg.build_host(out)
    rows = [(label, rom_path(name), frames) for label, name, frames in ROMS]
    rows.append(("rmw (HL), RAM and I/O", gbours.build(RMW_ROM), 2000))
    bad = 0
    for label, rom, frames in rows:
        if a.k and a.k not in label:
            continue
        n, st = run(rom, frames, core, host)
        ok = n == 2 and st is not None and st[1] == 0
        print("%-4s %-24s passed %d of 2, %s" % (
            "ok" if ok else "FAIL", label, n,
            "%d blocks preloaded, %d translated after" % st if st else "no DONE line"))
        bad += not ok
    if not a.k:
        rom, frames = rows[0][1], rows[0][2]
        nohost = norec(host)
        n, st = run(rom, frames, core, nohost)
        ok = n == 2 and st is not None and st[0] == 0 and st[1] == 0
        print("%-4s %-24s passed %d of 2, %s" % (
            "ok" if ok else "FAIL", "empty profile, fixed", n,
            "%d blocks preloaded, %d translated after" % st if st else "no DONE line"))
        bad += not ok
        n, st = run(rom, frames, core, unfix(nohost))
        red = st is None or st[1] > 0
        print("%-4s %-24s %s" % ("ok" if red else "FAIL", "control: table not fixed",
                                 "%d translated after the switch, as it must" % st[1]
                                 if st and red else "nothing translated - the gate cannot go red"))
        bad += not red
    for label, rom, frames in rows:                 # two segments, squeezed
        if a.k and a.k not in label:
            continue
        n, st = run(rom, frames, core, host, seg2=True)
        ok = n == 2 and st is not None and st[1] == 0
        print("%-4s %-24s passed %d of 2, %s" % (
            "ok" if ok else "FAIL", "seg2: " + label[:18], n,
            "%d blocks preloaded, %d translated after" % st if st else "no DONE line"))
        bad += not ok
    if not a.k:
        rom, frames = rows[0][1], rows[0][2]
        n, st = run(rom, frames, core, host, jit=True, seg2=True)
        ok = n == 1 and st is not None and st[0] >= 2 and st[1] >= 2
        print("%-4s %-24s passed %d of 1, %s" % (
            "ok" if ok else "FAIL", "seg2: translated as run", n,
            "%d flushes, %d moves into the second" % st if st else "no DONE line"))
        bad += not ok
        n, st = run(rom, frames, core, crossseg(host), jit=True, seg2=True)
        red = n == 0
        print("%-4s %-24s %s" % ("ok" if red else "FAIL", "control: cross-segment",
                                 "fails, as it must" if red else
                                 "passed - the gate cannot see a cross-segment jump"))
        bad += not red
    print("rbstatic: %s" % ("PASS" if not bad else "%d FAILED" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
