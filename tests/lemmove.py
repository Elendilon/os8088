#!/usr/bin/env python3
"""LEMMINGS' kept level MOVES, and plays on (SPEC.md 116.6.1, NO-PINNING C4).

    make lemmingsdisk && python3 tests/lemmove.py
    python3 tests/lemmove.py --machine os8088_xt_vga     # the VGA arm (T claim)

A level kept by 'f' holds up to ~330 KB of claims on the desktop (lemload.c's
seven lem_cl_* words), and until this row's change every byte of it was
PINNED for as long as the level was kept - a wall the heap could not close
over. They are MOVABLE now while the desktop holds them and PINNED again for
the launch that uses them, and the relocation proc (lemblit.inc's
os88_onmove) range-translates eighteen words: the seven claims, the C's
segments DERIVED from lem_cl_main (lem_anseg, lem_mkseg, lem_ptseg) and
lem_far_seg, and seven the raster keeps between calls.

THE RUN. MartyPC boots the shipped package off a SCRATCH copy of
build/lemmings360.img, launches Fun 2 like a user, plays a few seconds,
PAUSES (F11 - the world cannot move), photographs the glass, and keeps the
level with 'f'. The desktop then FORCES a compaction from outside, which is
the one thing a user cannot do on cue: the row writes `[mem_cpq]` - the
posted-compaction request `OSAPI_MEM_COMPACT` itself records (SPEC.md
66.4.3) - so ui_task's step 0a runs `mem_compact` with NOTHING held, at a
rank that drops the trivial caches the launch left below the level's claims
(the icon store and a raise cache, ~35 KB on both machines here). That is a
real hole under the claims, and the pass slides them into it. Then 'f'
resumes the level.

NINE ASSERTIONS, each about a different way the move can be wrong:

  1. PINNED WHILE IN USE: inside the bracket every claim's MC_RLOC is 0 -
     a local holds a claim's segment across a file read there (bucket C).
  2. MOVABLE ON THE DESKTOP: kept, every claim's MC_RLOC is non-zero.
  3. THEY MOVED, and the C followed: every lem_cl_* changed and each names
     a live claim of the same size in the kernel's own table.
  4. THE CONTENTS SURVIVED, every claim hashed at both addresses.
  5. THE DERIVED C WORDS FOLLOWED: lem_anseg, lem_mkseg and lem_ptseg keep
     their offset INSIDE lem_cl_main. A proc that fixed only the claims'
     own words passes 3 and 4 and fails here.
  6. THE RASTER'S WORDS FOLLOWED: lm_seg = lem_cl_mask, lo_seg = lem_cl_rec,
     lb_world, lb_shadow and lb_t = their claims (read BEFORE the resume,
     whose mode set re-writes four of them and would hide a miss).
  7. THE RESUMED LEVEL IS THE SAME PICTURE: paused, the glass after the
     resume is the glass before 'f', pixel for pixel - terrain composed
     out of the moved world/T claim and every lemming drawn out of the
     moved LEMMAIN animation, so a stale word draws garbage here.
  8. PINNED AGAIN for the resumed bracket.
  9. IT STILL PLAYS: unpaused, the game's iteration counter moves.

SKIPS - exit 0, saying why - when build/lemmings360.img is not there: the
data files are fetched and never committed (SPEC.md 116.2).
"""
import argparse
import hashlib
import os
import shutil
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "tests")]
import os88geom                                             # noqa: E402
import os88marty                                            # noqa: E402
import os88mouse                                            # noqa: E402
import os88sym                                              # noqa: E402
import dispapps                                             # noqa: E402
import dispcp                                               # noqa: E402
from lemplaymarty import lemmap                             # noqa: E402

S = os88sym.linear
HZ = 4772727.0
MC_SIZE, MEM_MAX = os88geom.MC_SIZE, os88geom.MEM_MAX
IMG = os.path.join(ROOT, "build", "lemmings360.img")
SCRATCH = os.path.join(ROOT, "build", "lemmove360.img")
CLAIMS = ("_lem_cl_mask", "_lem_cl_bank", "_lem_cl_main", "_lem_cl_world",
          "_lem_cl_shadow", "_lem_cl_rec", "_lem_cl_t")
DERIVED = ("_lem_anseg", "_lem_mkseg", "_lem_ptseg")    # inside lem_cl_main
RASTER = (("lm_seg", "_lem_cl_mask"), ("lo_seg", "_lem_cl_rec"),
          ("lb_world", "_lem_cl_world"), ("lb_shadow", "_lem_cl_shadow"),
          ("lb_t", "_lem_cl_t"))


def u16(b, i=0):
    return b[i] | (b[i + 1] << 8)


def mem_tab(m):
    """{base: (paragraphs, MC_RLOC)} of every live claim."""
    raw = m.read(S("mem_tab"), MEM_MAX * MC_SIZE)
    out = {}
    for i in range(MEM_MAX):
        o = i * MC_SIZE
        if u16(raw, o):
            out[u16(raw, o)] = (u16(raw, o + 2), u16(raw, o + 8))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    a = ap.parse_args()
    if not os.path.exists(IMG):
        print("lemmove: SKIP - build/lemmings360.img is not there; it needs "
              "the fetched data (tools/getlemmings.py) and `make "
              "lemmingsdisk`")
        return 0
    sym = lemmap()
    shutil.copyfile(IMG, SCRATCH)
    bad = []

    def check(n, ok, text):
        print("  %d %-34s %s" % (n, text, "OK" if ok else "FAIL"))
        if not ok:
            bad.append(n)

    try:
        with os88marty.launch("build/os8088-360.img",
                              apps=os.path.relpath(SCRATCH, ROOT),
                              machine=a.machine, label="lemmove") as m:
            os88marty.no_saver(m)
            mo = os88mouse.Mouse(marty=m)
            dispcp.open_drive(m, mo, S, os88marty.settle, "B")
            w = dispcp.win_list(m, S)
            wx, wy, _, _ = dispcp.win_rect(m, S, w[-1])
            dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "LEMMINGS")
            w = dispcp.win_list(m, S)
            wx, wy, _, _ = dispcp.win_rect(m, S, w[-1])
            dispcp.open_named(m, mo, S, os88marty.settle, wx, wy,
                              "LEMMINGS.O88")
            os88marty.settle(m)
            pk = dispapps.pkg_seg(m, 0)
            if not pk:
                print("lemmove: FAIL - LEMMINGS did not launch")
                return 1
            base = pk[1] * 16

            def rd(name):
                return u16(m.read(base + sym[name], 2))

            def wr(name, v):
                m.write(base + sym[name], struct.pack("<H", v))

            def cls():
                return {n: rd(n) for n in CLAIMS if rd(n)}

            def glass():
                return m.fbuf()[2]

            # --- launch Fun 2 (the 360KB disk carries it; Fun 1 it does not,
            # tests/lemplaymarty.py) and play until the lemmings are out ----
            wr("_lem_sel", 1)
            m.key("Enter")
            os88marty.until(m, lambda _: rd("_lem_claimed"),
                            "the level's claims", poll=1)
            m.advance(cycles=int(20 * HZ))      # the preview, drawn
            m.run()
            m.key("Enter")
            it0 = rd("_lem_iter")
            os88marty.until(m, lambda _: rd("_lem_iter") != it0,
                            "the level to start", poll=1)
            m.advance(cycles=int(15 * HZ))      # ten out of the trap door
            m.run()
            tab = mem_tab(m)
            c0 = cls()
            check(1, c0 and all(tab.get(s, (0, 1))[1] == 0
                                for s in c0.values()),
                  "pinned while in use (%d claims)" % len(c0))

            # --- paused, photographed, kept --------------------------------
            m.key("F11")
            m.advance(cycles=int(3 * HZ))
            m.run()
            os88marty.quiesce(m, glass, guest=1.0, what="the paused level")
            g0 = glass()
            m.key("KeyF")
            os88marty.until(m, lambda _: rd("_lem_suspended"),
                            "the level to be kept", poll=1)
            os88marty.settle(m)
            tab = mem_tab(m)
            c0 = cls()
            check(2, all(tab.get(s, (0, 0))[1] != 0 for s in c0.values()),
                  "movable on the desktop")
            size = {n: tab[s][0] for n, s in c0.items()}
            h0 = {n: hashlib.md5(m.read(s * 16, size[n] * 16)).hexdigest()
                  for n, s in c0.items()}
            off0 = {d: rd(d) - c0["_lem_cl_main"] for d in DERIVED if rd(d)}
            print("  kept: %s" % " ".join("%s=%04x" % (n[8:], s)
                                         for n, s in c0.items()))

            # --- the forced compaction --------------------------------------
            lw = [x for x in os88geom.windows(m, S)
                  if x.visible and x.title.startswith("Lemmings")]
            m.write(S("mem_cpq_lvl"), bytes([0xFC]))    # drop TRIV caches
            m.write(S("mem_cpq"),
                    struct.pack("<H", os88geom.winptr(m, lw[0].i, S)))
            os88marty.until(m, lambda _: u16(m.read(S("mem_cpq"), 2)) == 0,
                            "the posted compaction", poll=0.5)
            os88marty.settle(m)
            tab = mem_tab(m)
            c1 = cls()
            print("  after: %s" % " ".join("%s=%04x" % (n[8:], s)
                                          for n, s in c1.items()))
            check(3, set(c1) == set(c0)
                  and all(c1[n] != c0[n] for n in c0)
                  and all(tab.get(c1[n], (0,))[0] == size[n] for n in c0),
                  "moved, and lem_cl_* followed")
            check(4, all(hashlib.md5(m.read(c1[n] * 16, size[n] * 16))
                         .hexdigest() == h0[n] for n in c0 if n in c1),
                  "contents survived")
            off1 = {d: rd(d) - c1.get("_lem_cl_main", 0) for d in off0}
            check(5, off0 and off1 == off0,
                  "derived C words followed (%d)" % len(off0))
            if off1 != off0:
                print("      offsets inside LEMMAIN %r, now %r" % (off0, off1))
            ras = {r: (rd(r), c1.get(c, 0)) for r, c in RASTER}
            check(6, all(v[0] == v[1] for v in ras.values()),
                  "raster words followed")
            if not all(v[0] == v[1] for v in ras.values()):
                print("      %r" % ras)

            # --- resume: the same picture, pinned again, still playing ------
            m.key("KeyF")
            os88marty.until(m, lambda _: not rd("_lem_suspended")
                            and rd("_lem_lvl_ok"), "the resume", poll=1)
            os88marty.quiesce(m, glass, guest=1.0, what="the resumed level")
            g1 = glass()
            diff = sum(1 for i in range(0, min(len(g0), len(g1)), 3)
                       if g0[i:i + 3] != g1[i:i + 3])
            check(7, len(g0) == len(g1) and diff == 0,
                  "resumed picture identical (%d px)" % diff)
            tab = mem_tab(m)
            check(8, all(tab.get(s, (0, 1))[1] == 0 for s in cls().values()),
                  "pinned again for the bracket")
            it1 = rd("_lem_iter")
            m.key("F11")
            m.advance(cycles=int(5 * HZ))
            m.run()
            it2 = rd("_lem_iter")
            check(9, it2 > it1, "still plays (iter %d -> %d)" % (it1, it2))
    finally:
        try:
            os.unlink(SCRATCH)
        except OSError:
            pass
    print("lemmove: %s" % ("PASS" if not bad else
                           "FAIL - assertion(s) %s" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
