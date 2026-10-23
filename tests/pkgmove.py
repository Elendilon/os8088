#!/usr/bin/env python3
"""A package's declared claims MOVE, every word follows, nothing changes (NO-PINNING).

    make && python3 tests/pkgmove.py --app texpad --open B:/MEDIA/PAPER.TEX \\
        --word tp_srcseg

ONE GATE FOR THE MANY SMALL ITEMS OF docs/plans/NO-PINNING-PLAN.md (A3 and
after): a package declares a data claim movable with a relocation proc that
updates the words naming it. This row opens a document by double-click (its
association launches the package), records the claim each named WORD holds
and that claim's bytes, then posts a compaction from OUTSIDE at the TRIVIAL
purge rank - `[mem_cpq]` + `[mem_cpq_lvl]`, the door OSAPI_MEM_COMPACT posts
through (SPEC.md 66.4.3) - which drops the raise caches and the icon store and
so opens holes the claims slide into.

FIVE ASSERTIONS:
  1. every named claim is declared movable (MC_RLOC read from OUTSIDE - a
     refused declaration looks identical from inside, SPEC.md 66.5.6.2);
  2. at least one MOVED (else the run proved nothing - say so, do not pass);
  3. every word names a live claim afterwards;
  4. every moved claim's bytes are the same, hashed at both addresses;
  5. the window REDRAWS the same picture: the guest repaints everything
     (`[cp_dirty]`, tests/dispcalc.py's poke) and the content band is compared
     with the one before the move.

Each registration names its own red run: the package's proc made a bare
`ret`, which leaves the word naming the old base and fails 3.
"""
import argparse
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "tests")]
import dispapps                                         # noqa: E402
import dispcp                                           # noqa: E402
import os88geom                                         # noqa: E402
import os88marty                                        # noqa: E402
import os88mouse                                        # noqa: E402
import os88sym                                          # noqa: E402

S = os88sym.linear
MC_SIZE, MEM_MAX = os88geom.MC_SIZE, os88geom.MEM_MAX


def u16(b, i=0):
    return b[i] | b[i + 1] << 8


def claims(m):
    raw = m.read(S("mem_tab"), MEM_MAX * MC_SIZE)
    return {u16(raw, i * MC_SIZE): (u16(raw, i * MC_SIZE + 2),
                                    u16(raw, i * MC_SIZE + 8))
            for i in range(MEM_MAX) if u16(raw, i * MC_SIZE)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--open", required=True,
                    help="D:/FOLDER/.../FILE to double-click")
    ap.add_argument("--word", action="append", required=True)
    ap.add_argument("--disk", default="build/apps360.img")
    ap.add_argument("--first", help="D:/.../FILE opened BEFORE the target and "
                    "closed after it, so its claims leave a hole UNDER the "
                    "target's (a claim already on the floor cannot move)")
    ap.add_argument("--machine", default="os8088_5150_cga_gla")
    a = ap.parse_args()
    MAP = dispapps._map(a.app)
    fails = []
    done = lambda mm, **k: os88marty.ui_done(mm)

    def front(m):
        # THE FRONTMOST window, not the last slot: open_drive FRONTS a Disk
        # window that is already open (a second file at the same volume's
        # root - office360's CHART.O88 after ARTFUL.O88), and a launched
        # package's window may take a lower free slot than the last one
        t = os88geom.top(m, S)
        return [i for i in dispcp.win_list(m, S)
                if os88geom.winptr(m, i, S) == t][0]

    def walk(m, mo, spec):
        drive, path = spec.split(":/", 1)
        parts = path.split("/")
        dispcp.open_drive(m, mo, S, done, drive)
        for name in parts[:-1]:
            wx, wy, _, _ = dispcp.win_rect(m, S, front(m))
            dispcp.open_named(m, mo, S, done, wx, wy, name)
        wx, wy, _, _ = dispcp.win_rect(m, S, front(m))
        before = dispcp.win_list(m, S)
        dispcp.open_named(m, mo, S, done, wx, wy, parts[-1])
        os88marty.until(m, lambda _: len(dispcp.win_list(m, S)) > len(before),
                        "%s's window" % parts[-1], poll=0.3, limit=60)
        os88marty.quiesce(m, lambda: sorted(claims(m)), guest=2.0,
                          what="the claims")
        return [i for i in dispcp.win_list(m, S) if i not in before][0]

    with os88marty.launch("build/os8088-360.img", apps=a.disk,
                          machine=a.machine, boot=False) as m:
        m.run()
        os88marty.kernel_up(m)
        os88marty.no_saver(m)
        mo = os88mouse.Mouse(marty=m)
        first = walk(m, mo, a.first) if a.first else None
        win = walk(m, mo, a.open)
        if first is not None:            # its claims under ours become a hole
            fw = [o for o in os88geom.windows(m, S) if o.i == first][0]
            mo.click(*os88geom.tile_xy(m, fw, S))
            os88marty.until(m, lambda _: os88geom.top(m, S)
                            == os88geom.winptr(m, first, S),
                            "the first window fronted", limit=20)
            mo.click(fw.x + 8, fw.y + 9)
            os88marty.until(m, lambda _: not any(
                o.i == first and o.visible for o in os88geom.windows(m, S)),
                "the first window closed", limit=20)

        def pseg():
            rec = m.read(S("wm_wins") + win * dispcp.WIN_SIZE,
                         dispcp.WIN_SIZE)
            return u16(rec, 22)
        os88marty.quiesce(m, lambda: sorted(claims(m)), guest=2.0,
                          what="the package's claims")
        os88marty.ui_done(m)

        def words(seg):
            return {w: u16(m.read(seg * 16 + MAP[w], 2)) for w in a.word}

        seg0 = pseg()
        w0 = words(seg0)
        held = claims(m)
        print("%s at %04x: %s" % (a.app, seg0, "  ".join(
            "%s=%04x" % kv for kv in w0.items())))
        hashes = {}
        for w, c in w0.items():
            if c not in held:
                fails.append("%s = %04x names no claim before the move"
                             % (w, c))
                continue
            hashes[w] = hashlib.md5(m.read(c * 16, held[c][0] * 16)).digest()
        decl = [w for w, c in w0.items() if c in held and held[c][1]]
        print("  1 declared movable   %d of %d" % (len(decl), len(w0)))
        if len(decl) != len(w0):
            fails.append("not declared: %s" % sorted(set(w0) - set(decl)))
        x, y, w, h = dispcp.win_rect(m, S, win)

        def repaint():
            m.write(S("cp_dirty"), b"\x01")
            os88marty.ui_done(m)
            os88marty.settle(m)
            return m.fbuf()

        shot0 = repaint()
        wptr = os88geom.winptr(m, win, S)
        m.write(S("mem_cpq_lvl"), bytes([0xFC]))
        m.write(S("mem_cpq"), bytes([wptr & 0xFF, wptr >> 8]))
        os88marty.until(m, lambda _: u16(m.read(S("mem_cpq"), 2)) == 0,
                        "the posted compaction", poll=0.2, limit=30)
        os88marty.ui_done(m)

        seg1 = pseg()
        w1 = words(seg1)
        held = claims(m)
        print("%s at %04x: %s" % (a.app, seg1, "  ".join(
            "%s=%04x" % kv for kv in w1.items())))
        moved = [k for k in w1 if w1[k] != w0[k]]
        print("  2 moved              %s" % (", ".join(moved) or "NOTHING"))
        if not moved:
            fails.append("nothing moved: the run proves nothing")
        stale = [k for k, c in w1.items() if c not in held]
        print("  3 every word live    %s" % ("yes" if not stale else
                                             "STALE: %s" % stale))
        if stale:
            fails.append("stale words: %s" % stale)
        bad = [k for k in moved if k in hashes and w1[k] in held and
               hashlib.md5(m.read(w1[k] * 16, held[w1[k]][0] * 16)).digest()
               != hashes[k]]
        print("  4 contents survived  %s" % ("yes" if not bad else
                                             "CHANGED: %s" % bad))
        if bad:
            fails.append("contents changed: %s" % bad)
        shot1 = repaint()
        W = shot0[0]

        def band(f):
            return b"".join(f[2][(yy * W + x) * 3:(yy * W + x + w) * 3]
                            for yy in range(y, y + h))
        same = band(shot0) == band(shot1)
        print("  5 redraws the same   %s" % ("yes" if same else "NO"))
        if not same:
            fails.append("the window does not redraw identically")

    print("pkgmove %s: %s" % (a.app, "FAIL: " + "; ".join(fails) if fails
                              else "5 checks passed"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
