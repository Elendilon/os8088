#!/usr/bin/env python3
"""bzprof.py - BONANZA's sampling profiler (SPEC.md 130.46.13).

Plays a replay (.BZR) or a shipped demo on a MartyPC machine and reports, a
guest second at a time, the frames presented and the physics steps run (54.6
a second is real time), and a CS:IP profile by routine: a sample every 15 -
45k guest clocks (a seeded random gap, so nothing aliases with the frame),
resolved against the package's listing (build/bonanza.lst), the VGA part's
(assembled here, from the source, into a temporary listing - so it is never
stale against the build), or else named by the heap claim it falls in (the
parts arena, a course part ...) with its size.

    python3 tools/bzprof.py --machine os8088_xt_vga --demo play
    python3 tools/bzprof.py --machine os8088_5150_cga_gla --replay PLAY.BZR --secs 20

It is an instrument for an optimisation round, not a row: it asserts nothing
(tests/bonanza_perf.py's VGA leg holds the numbers that are asserted).  It
was the scratch script that found 130.46.13's three faults - the column
writer's cost, the step loop's lost game time and the long frame that waited
a refresh.
"""
import argparse
import bisect
import collections
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88ui                   # noqa: E402
import os88marty as M           # noqa: E402
import bonanza_ring as R        # noqa: E402

CPS = 4772727                   # a 4.77 MHz 8088's clocks a second


def labels(lst):
    """[(offset, label)] of a nasm listing: each global label at the next line that emits"""
    out, pend = [], []
    for ln in open(lst, errors="replace"):
        m = re.match(r"\s*\d+\s+([0-9A-F]{8})\s", ln)
        src = (re.sub(r"^<\d+> ?", "", ln[36:]) if ln[36:37] == "<" else ln[40:]).rstrip() if len(ln) > 36 else ""
        lab = re.match(r"([A-Za-z_]\w*):", src)
        if lab:
            pend.append(lab.group(1))
        if m:
            a = int(m.group(1), 16)
            out += [(a, p) for p in pend]
            pend = []
    out.sort()
    return out


def name(tab, off):
    i = bisect.bisect_right([a for a, _ in tab], off) - 1
    return tab[i][1] if i >= 0 else "?"


def vga_listing(td):
    lst = os.path.join(td, "bzvga.lst")
    out = os.path.join(td, "bzvga.bin")
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/", "-I", "apps/bonanza/",
                    "-I", R.at("build/bonanza-art") + "/", "-l", lst, "-o", out, "apps/bonanza/bzvga.asm"],
                   cwd=ROOT, check=True)
    return lst


def fam_tables(td):
    """{family: (its built part's bytes, its listing's labels)} - every apps/bonanza/fam/*.asm assembled here
    with a listing, so a sample in the parts arena names its family by the bytes at its CS:0 and its routine
    by the offset"""
    out = {}
    fdir = os.path.join(ROOT, "apps", "bonanza", "fam")
    for fn in sorted(os.listdir(fdir)):
        if not fn.endswith(".asm"):
            continue
        name = fn[:-4]
        lst, binp = os.path.join(td, "f-%s.lst" % name), os.path.join(td, "f-%s.bin" % name)
        r = subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/", "-I", "apps/bonanza/",
                            "-I", R.at("build/bonanza-art") + "/", "-l", lst, "-o", binp, "apps/bonanza/fam/" + fn],
                           cwd=ROOT, capture_output=True)
        if r.returncode == 0:
            out[name] = (open(binp, "rb").read(), labels(lst))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--machine", default="os8088_xt_vga")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--replay", metavar="BZR", help="a replay file, played by R")
    src.add_argument("--demo", metavar="COURSE", help="a shipped demo by its course's name (trial, mill, play ...)")
    ap.add_argument("--secs", type=float, default=20.0, help="guest seconds measured (default 20)")
    ap.add_argument("--top", type=int, default=30, help="routines listed (default 30)")
    a = ap.parse_args()
    vga = "vga" in a.machine
    art = R.at("build/bonanza-art")
    sym = R.symbols(None, art)
    with tempfile.TemporaryDirectory() as td:
        pk = labels(os.path.join(ROOT, R.at("build/bonanza.lst")))
        vg = labels(vga_listing(td)) if vga else []
        fams = fam_tables(td)
        img = os.path.join(td, "apps.img")
        shutil.copy(R.at("build/bonanza360.img"), img)
        if a.replay:
            subprocess.run(["mcopy", "-o", "-i", img, a.replay, "::/PROF.BZR"], check=True)
        with os88ui.boot(R.at("build/os8088-360.img"), apps=img, machine=a.machine) as ui:
            ui.open_drive("B")
            ui.open("PROF.BZR" if a.replay else "BONANZA.O88")
            g = R.Bz(ui, "vga" if vga else "cga", sym, live=True)
            m = g.m
            ui.settle()
            if a.demo:
                R.CRS_K["bench"]
                kd = R.CRS_K[a.demo]
                demo = open(os.path.join(art, "BZD%d.BIN" % kd), "rb").read()
                m.pause()
                g.putb("bz_vk", kd - 1)
                m.run()
                g.key("KeyV")
                M.until(m, lambda _: bytes(m.read(g.a("bz_rlog"), len(demo))) == demo, "V to load the demo", guest=20)
                M.until(m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)
            g.key("KeyR")
            M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "the replay runs", guest=120)
            m.pause()
            base = g.base
            vseg = int.from_bytes(bytes(m.read(g.a("bz_vfp") + 2, 2)), "little") if vga else 0
            prof, per, foreign = collections.Counter(), [], collections.Counter()
            f0, s0 = g.w("bz_frames"), g.d("bz_nstep")
            last, t, nxt = (f0, s0), 0.0, 1.0
            rnd = random.Random(1)
            while t < a.secs and g.b("bz_fs") == 1:
                c = rnd.randint(15000, 45000)
                m.advance(cycles=c)
                t += c / CPS
                r = m.regs()
                flat = (r["cs"] << 4) + r["ip"]
                if base <= flat < base + 0x10000:
                    prof["pkg " + name(pk, flat - base)] += 1
                elif vseg and (vseg << 4) <= flat < (vseg << 4) + 0x2000:
                    prof["vga " + name(vg, flat - (vseg << 4))] += 1
                else:
                    foreign[(r["cs"], r["ip"])] += 1
                if t >= nxt:
                    f, st = g.w("bz_frames"), g.d("bz_nstep")
                    per.append(((f - last[0]) & 0xFFFF, st - last[1]))
                    last, nxt = (f, st), nxt + 1.0
            # a segment outside both listings: a FAMILY when the bytes at its CS:0 are one of the built family
            # parts' (named by routine in that part's listing), else named by the claim it falls in
            # a sample outside both listings: its 16 bytes looked for in every built family part - found once,
            # it is that family's, at that offset (named by routine in the part's listing); else named by the
            # claim it falls in.  (Not CS:0: a family's code is not entered at its part's first byte.)
            where = {}
            for (cs, ip), v in foreign.items():
                lin = ((cs << 4) + ip) & 0xFFFFF
                if lin not in where:
                    code = bytes(m.read(lin, 16))
                    hits = [(n, b.find(code)) for n, (b, _) in fams.items() if b.find(code) >= 0]
                    where[lin] = hits[0] if len(hits) == 1 else None
                h = where[lin]
                prof["fam %s %s" % (h[0], name(fams[h[0]][1], h[1])) if h else "seg %04X" % cs] += v
            import bonanza_exit as E        # the claims, to name a segment outside the two listings
            hm = E._tools_heapmap()
            mp = hm.Map(E.Q(m), {n: m.sym(n) for n in ("mem_base", "mem_top", "spl_live", "mem_tab")})
            own = [(c.seg, c.end, c.para) for c in mp.claims if c.own == base >> 4]
            m.run()
    n = sum(prof.values()) or 1
    print("bzprof %s, %s: %.1f guest seconds" % (a.machine, a.replay or "the %s demo" % a.demo, t))
    print("  a second (frames, steps; 54.6 steps is real time): %s" % per)
    if per:
        print("  mean %.1f frames and %.1f steps a second" % (sum(p[0] for p in per) / len(per),
                                                              sum(p[1] for p in per) / len(per)))
    for k, v in prof.most_common(a.top):
        where = ""
        if k.startswith("seg "):
            s = int(k[4:], 16)
            hit = [c for c in own if c[0] <= s < c[1]]
            where = "  (the package's claim %04X, %d paragraphs)" % (hit[0][0], hit[0][2]) if hit else ""
        print("  %5.1f%%  %s%s" % (100.0 * v / n, k, where))


if __name__ == "__main__":
    main()
