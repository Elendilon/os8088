#!/usr/bin/env python3
"""Where RealBoy's time goes, by handler and by rbsys routine, on MartyPC.

    python3 tests/rbcore/rbprof.py GAME.GB [--secs S] [--lead S] [--machine M]
    python3 tests/rbcore/rbprof.py GAME.GB --box [VM] [--samples N] [--lead S]

Boots GAME.GB in the bare harness (tests/rbcore/rbhost.asm, MODE 3: gbprof's
platformer input) on MartyPC's cycle-accurate 8088, lets it play for --lead
guest seconds, then samples the live CS:IP from the debug server for --secs
host seconds - tools/os88prof.py's method, which costs the guest nothing. A
sample in the core's segment is charged to the handler or tail holding it, a
sample in the harness's to the rbsys.inc routine, by the nearest preceding
global label in nasm's listing; the rest is the BIOS.

--box samples 86Box's 286 instead (default vm/286, the ami286 at 12.5 MHz):
the machine is held, stepped one emulated millisecond at a time, and its
CS:IP read between steps through the automation socket - so the sample
clock is emulated time and the host's load cannot bend it. 86Box times
instructions by its model and is not cycle-accurate (docs/86BOX.md); the
8088 profile above is exact.
"""
import argparse
import bisect
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests", "rbcore"))
import os88marty  # noqa: E402
import rbimg  # noqa: E402

HOST, CORE, CACHE = 0x8000, 0x10000, 0x90000   # rbhost.asm's segments


def labels(lst, section=None):
    """(offset, name) of every global label in a nasm listing - a label line
    carries no address, so it takes the next one that emits a byte."""
    out, pending = [], []
    for line in open(lst, errors="replace"):
        m = re.match(r"\s*\d+\s+([0-9A-F]{8})\s", line)
        lab = re.search(r"^\s*\d+\s+(?:[0-9A-F]{8}\s+\S+\s+)?(?:<\d+>\s+)?([A-Za-z_][A-Za-z0-9_]*):", line)
        if lab and not m:
            pending.append(lab.group(1))
            continue
        if m:
            a = int(m.group(1), 16)
            if lab:
                pending.append(lab.group(1))
            for n in pending:
                out.append((a, n))
            pending = []
    out.sort()
    return out


def listing(src, inc, extra=()):
    lst = os.path.join(ROOT, "build", "realboy", os.path.basename(src) + ".lst")
    tmp = os.path.join(ROOT, "build", "realboy", os.path.basename(src) + ".prof.bin")
    subprocess.check_call(["nasm", "-f", "bin", "-w+error"] + sum([["-I", i] for i in inc], [])
                          + list(extra) + ["-o", tmp, "-l", lst, src])
    os.unlink(tmp)
    return lst


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("rom")
    ap.add_argument("--secs", type=float, default=60)
    ap.add_argument("--lead", type=float, default=50,
                    help="guest seconds before sampling (with --box: after the harness starts)")
    ap.add_argument("--machine", default="os8088_xt_vga")
    ap.add_argument("--box", nargs="?", const="286", metavar="VM")
    ap.add_argument("--samples", type=int, default=10000)
    ap.add_argument("--render", action="store_true", help="compose every frame too (MODE 5)")
    ap.add_argument("--nojit", action="store_true", help="the interpreter alone")
    a = ap.parse_args()
    out = os.path.join(ROOT, "build", "realboy")
    core, host = rbimg.build_core(False, out), rbimg.build_host(out)
    img = os.path.join(out, "prof.img")
    rbimg.make_image(a.rom, img, 1440 if a.box else 360, "render" if a.render else "play", 60000,
                     core=core, host=host, jit=not a.nojit)
    mine = rbimg.private(out)               # where this run built its core
    inc = [os.path.join(ROOT, "apps/realboy/"), os.path.join(ROOT, "tests/rbcore/"), mine + "/"]
    csyms = labels(listing(os.path.join(mine, "rbcore.asm"), inc))
    hsyms = labels(listing(os.path.join(ROOT, "tests/rbcore/rbhost.asm"), inc))
    hsyms = [(o, n) for o, n in hsyms if n not in ("boot", "boot_go", "load")]  # the boot section's
    ck, hk = [o for o, _ in csyms], [o for o, _ in hsyms]
    hits, tot = {}, 0

    sys.path.insert(0, os.path.join(ROOT, "apps", "realboy"))
    import rbgen
    tails = set(rbgen.TAILS)

    def charge(ip):
        if CACHE <= ip < CACHE + 0x10000:       # the recompiler's segment
            off = ip - CACHE
            if (off >> 8) in tails:             # ...its copies of the tails
                i = bisect.bisect_right(ck, off) - 1
                return "tail " + (csyms[i][1] if i >= 0 else "?")
            return "translated code"
        if CORE <= ip < CORE + 0x10000:
            i = bisect.bisect_right(ck, ip - CORE) - 1
            return "core " + (csyms[i][1] if i >= 0 else "?")
        if HOST <= ip < CORE:
            i = bisect.bisect_right(hk, ip - HOST) - 1
            return "host " + (hsyms[i][1] if i >= 0 else "?")
        return "BIOS" if ip >= 0xF0000 else "other %05X" % ip

    if a.box:
        import os88box
        b = os88box.launch(a.box, name="rbprof", hold=True, fresh=True, a=img)
        try:
            for _ in range(600):                    # to the harness's banner...
                b.cmd("step 500")
                try:
                    t = "".join(bytes.fromhex(x).decode("cp437")
                                for x in b.cmd("text").get("chars", []))
                except SystemExit:                  # not a text mode yet
                    t = ""
                if "EXIT FOR BOOT" in t:            # an AT's first boot stops in setup
                    b.tap("return")
                if "RealBoy core harness" in t:
                    break
            else:
                sys.exit("rbprof: the harness never started")
            for _ in range(int(a.lead * 2)):        # ...then into play
                b.cmd("step 500")
            for _ in range(a.samples):
                b.cmd("step 1")
                r = b.cmd("regs")
                name = charge(r["cs_base"] + (r["eip"] & 0xFFFF))
                hits[name] = hits.get(name, 0) + 1
                tot += 1
        finally:
            try:
                b.cmd("quit")
            except BaseException:
                pass
        c0, c1 = 0, a.samples * 4772.727                # printed as emulated ms below
    else:
        m = os88marty.launch(img, machine=a.machine, boot=False)
        try:
            m.run()
            os88marty.guest_sleep(m, a.lead)
            c0 = int(m.status()["cycles"])
            t0 = time.time()
            while time.time() - t0 < a.secs:
                ip = m.cmd(cmd="status")["flat_ip"]
                tot += 1
                name = charge(ip)
                hits[name] = hits.get(name, 0) + 1
            c1 = int(m.status()["cycles"])
        finally:
            m.close()
    print("%d samples over %.1f guest seconds" % (tot, (c1 - c0) / 4772727.0))
    groups = {}
    for k, n in hits.items():
        g = "core" if k.startswith("core") else ("rbsys/host" if k.startswith("host") else "BIOS/other")
        groups[g] = groups.get(g, 0) + n
    print("  " + "   ".join("%s %.1f%%" % (g, 100.0 * n / tot) for g, n in sorted(groups.items())))
    for k, n in sorted(hits.items(), key=lambda x: -x[1])[:40]:
        print("  %5.1f%%  %s" % (100.0 * n / tot, k))


if __name__ == "__main__":
    main()
