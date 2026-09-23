#!/usr/bin/env python3
"""TITHE's rules engine on the machine AGREES with tools/duelsim.py (SPEC.md 97.11).

Wave 2's gate is "the two agree": `apps/tithe/tirule.inc` is the only place the
rules exist on the machine, `tools/duelsim.py` is their second reader, and
this row replays every match of `duelsim.py bake`'s set on an 8088 and holds
the engine's STATE RECORD after setup and after every round to the
simulator's, byte for byte.

WHAT IT ASSERTS, and each one went red on purpose first:

  1. EVERY RECORD OF EVERY BAKED MATCH IS THE SIMULATOR'S. The set is chosen
     so that all 23 keywords fire at least once (`duelsim.py bake` refuses to
     build a set that misses one), so a rule the engine gets wrong is a rule
     this sees - a mismatch prints the round and both sides of it decoded.

  2. THE ENGINE REFUSED NOTHING. Every plan here is one the simulator applied,
     so an action the engine skipped as illegal is a disagreement about
     legality even where the records happen to match.

  3. IT IS CHEAP ENOUGH TO BE THE AI'S LOOKAHEAD. The replay's system ticks are
     printed a round, because TITHE-PLAN 10.3 has the AI call this engine on a
     scratch board once a candidate - a number wave 4 is sized by.

    make titherules && python3 tests/titherules.py [machine]
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402
import duelsim                                            # noqa: E402

SYMS = ("tt_match", "tt_seq", "tt_nrec", "tt_bad", "tt_ticks")
fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    """Assembled from the SOURCE with the words appended, as every tithe row's
    are, so the offsets cannot drift from the image under test."""
    src = open(os.path.join(ROOT, "tests/titherule/titherule.asm"),
               encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "titherul-off.asm")
    out = os.path.join(ROOT, "build", "titherul-off.bin")
    body, end = src.split("    OS88_BSS", 1)
    open(tmp, "w", encoding="utf-8").write(
        body + "".join("dw %s\n" % s for s in SYMS) + "    OS88_BSS" + end)
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-I", "build/", "-o", out, tmp],
                   cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "titherul.bin"))
    blob = open(out, "rb").read()
    off = {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
           for i, s in enumerate(SYMS)}
    # THE LOG IS AT THE IMAGE'S END, and the words appended above MOVE that
    # end - read out of the offset build, tt_log is twelve bytes too far and
    # every record decodes as garbage. The real image's length is its offset.
    off["tt_log"] = base
    return off


def matches():
    blob = open(os.path.join(ROOT, "build", "tirmatch.bin"), "rb").read()
    out, i = [], 1
    for _ in range(blob[0]):
        n = struct.unpack("<H", blob[i:i + 2])[0]
        out.append(blob[i + 2:i + 2 + n])
        i += 2 + n
    return out


def diff(want, got, k):
    """The first record that differs, decoded both ways."""
    R = duelsim.RECSIZE
    for r in range(0, max(len(want), len(got)), R):
        a, b = want[r:r + R], got[r:r + R]
        if a != b:
            at = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]),
                      min(len(a), len(b)))
            print("       match %d, record %d, byte %d: sim %s machine %s" % (
                k, r // R, at, a[at:at + 8].hex(), b[at:at + 8].hex()))
            print("       sim:     " + duelsim.text(a).replace("\n", "\n       "
                                                                "          "))
            print("       machine: " + duelsim.text(b).replace("\n", "\n       "
                                                                "          "))
            return


def main():
    mach = sys.argv[1] if len(sys.argv) > 1 else "os8088_5150_cga_gla"
    off = offsets()
    sets = matches()
    print("  --- %s: %d matches" % (mach, len(sets)))
    with os88ui.boot("build/os8088-360.img", apps="build/titherule360.img",
                     machine=mach) as ui:
        m = ui.m
        ui.path("B:/TITHERUL.O88")
        win = [w for w in os88geom.windows(m) if w.title == "TITHE rules"][0]
        seg = struct.unpack(
            "<H", bytes(m.read(os88geom.winptr(m, win) + os88geom.W_SEG, 2)))[0]
        ui.raise_window(win)

        def rw(name):
            return struct.unpack("<H", bytes(m.readseg(seg, off[name], 2)))[0]

        agree, rounds, ticks, refused = 0, 0, 0, 0
        for k, tmf in enumerate(sets):
            want, sim = duelsim.replay(tmf)
            m.write(seg * 16 + off["tt_match"], bytes([k]))
            s0 = rw("tt_seq")
            m.key("KeyR")
            os88marty.until(m, lambda _: rw("tt_seq") != s0,
                            "match %d's replay" % k, poll=0.2, limit=120.0)
            n, bad = rw("tt_nrec"), rw("tt_bad")
            got = bytes(m.readseg(seg, off["tt_log"], n * duelsim.RECSIZE))
            if bad:
                refused += 1
                print("       match %d: the engine refused %d action(s)" % (k, bad))
            if got == want:
                agree += 1
            else:
                diff(want, got, k)
            rounds += sim.round
            ticks += rw("tt_ticks")
        check(agree == len(sets), "every record of every match is the "
              "simulator's (%d matches, %d rounds)" % (len(sets), rounds),
              "%d of %d agree" % (agree, len(sets)))
        check(refused == 0, "the engine refused no action the simulator took",
              "%d match(es)" % refused)
        print("       %.1f ms a round of replay, on this machine's clock"
              % (ticks * 54.925 / max(rounds, 1)))
    print("titherules: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
