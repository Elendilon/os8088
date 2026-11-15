#!/usr/bin/env python3
"""WireArena's bots walk the arena's ROUTE GRAPH (docs/plans/
completed/WIREARENA-AI-PLAN.md 3): a branch taken at every node, the lift ridden.

One boot into the Heights arena at 40 columns, then, off the game's own
variables (its symbols from wirearena.asm assembled with a map, refused
unless byte-identical to the build):

  - ROAM: two minutes of the sim with the bots branching at random,
    sampled every 8 ticks. They leave their home loops (each one is seen on
    an edge of another), they cover most of the graph (at least 60% of its
    edges), no figure ever stands inside a tall box or outside the room, and
    on every edge that climbs a figure stands on the floor under it (its
    F_Z is arenagen's floor_at there, or the lift's height on the lift);
  - THE LIFT: bot 0 put at the lift's foot on the edge onto it waits for it
    at rest, walks on, rides it to the top (the lift carries it: it rises
    while the bot waits on it), walks onto the tower (F_Z 160), drops off
    it, and the lift goes home empty.

A graph whose branch never fires keeps every bot on its home loop (red); a
bot not counted as a rider leaves the lift at rest (red).
"""
import os
import struct
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import arenagen                                                 # noqa: E402
import os88marty                                                # noqa: E402
import os88ui                                                   # noqa: E402
from os88fixture import need                                    # noqa: E402
from waweapons import Arena, start, amap, SYS, APPS, FS, ITEM          # noqa: E402

GESZ = 12


def watab(name):
    """one of build/watab.inc's constants (the animations' keyframes)"""
    import re
    import os88build
    t = open(os.path.join(ROOT, os88build.at("build/"), "watab.inc")).read()
    return int(re.search(r"^%s equ (\d+)" % name, t, re.M).group(1))


SEED = 0x1357                   # the dice (wa_seed at the match's start)


def main():
    need(APPS)
    sym = amap()
    boxes = [arenagen.bx(b) for b in arenagen.HEIGHTS_BOXES]
    top = arenagen.hmax(boxes)
    tall = [b for b in boxes if b.h >= top]
    nodes, edges, homes = arenagen.graph_edges("a2", boxes)
    lift = [b for b in boxes if b.kind == arenagen.LIFT][0]
    fails = []

    def check(ok, what):
        print("  %s %s" % ("ok  " if ok else "FAIL", what), flush=True)
        if not ok:
            fails.append(what)

    with os88ui.boot(SYS, apps=APPS, machine="os8088_5150_cga",
                     quick=True) as ui:
        m = ui.m
        w = ui.path("B:/WARENA.O88")
        p = start(ui, w, sym)
        f0 = p.byte(sym["wa_frame"])
        os88marty.until(m, lambda _: p.byte(sym["wa_frame"]) != f0,
                        "the Heights arena's first frames", guest=20)
        m.pause()
        g = Arena(ui, w, sym)
        gep = g.word("wa_gep", signed=False)

        def figs():
            d = g.p.read(sym["wa_figs"], FS * 3)
            out = []
            for i in range(3):
                r = d[i * FS:(i + 1) * FS]
                x, y = struct.unpack_from('<hh', r, 0)
                leg = struct.unpack_from('<H', r, 6)[0]
                z = struct.unpack_from('<h', r, 18)[0]
                out.append((x, y, z, leg // GESZ, r[17], r[45]))
            return out

        def lifth():
            return struct.unpack('<h', g.p.read(
                sym["wa_bxh"] + g.word("wa_lift"), 2))[0]

        # ROAM: two minutes, every 8 ticks
        homes_of = {}
        for k, loop in enumerate(arenagen.HEIGHTS_GRAPH["homes"]):
            for a in loop:
                homes_of[a] = k
        seen, away, bad, badz = set(), [False] * 3, [], []
        while g.word("wa_tkn", signed=False) < 3600:
            g.tick(8)                   # (the sim's first two minutes)
            lh = lifth()
            for i, (x, y, z, e, dead, wait) in enumerate(figs()):
                if dead or e >= len(edges):
                    continue
                seen.add(e)
                a, b_ = edges[e][0], edges[e][1]
                if homes_of.get(a) != i or homes_of.get(b_) != i:
                    away[i] = True
                if arenagen.inside(x, y, tall, 0):
                    bad.append((i, x, y))
                if edges[e][5] & 0x8000:
                    on_lift = (lift[0] - 8 < x < lift[2] + 8
                               and lift[1] - 8 < y < lift[3] + 8)
                    want = arenagen.floor_at(x, y, [b if b.kind !=
                                                    arenagen.LIFT else
                                                    arenagen.Box(*b, h=lh,
                                                                 kind=0)
                                                    for b in boxes],
                                             arenagen.FRAD)
                    if abs(z - want) > 6 and not on_lift:
                        badz.append((i, x, y, z, want))
        check(all(away), "ROAM: every bot leaves its home loop (%r)" % away)
        check(len(seen) >= 0.6 * len(edges),
              "ROAM: %d of the graph's %d edges walked in two minutes"
              % (len(seen), len(edges)))
        check(not bad, "ROAM: no figure inside a tall box (%r)" % bad[:3])
        check(not badz, "ROAM: on climbing edges, each on its floor (%d off, "
              "first %r)" % (len(badz), badz[:2]))

        # THE LIFT: bot 0 at its foot, on the edge onto it
        on = next(i for i, e in enumerate(edges) if e[2] == arenagen.LIFT_ON)
        e = edges[on]
        base = sym["wa_figs"]
        m.pause()
        lrest0 = g.word("wa_lrest")
        g.p.write(base + 6, struct.pack('<H', on * GESZ))
        g.p.write(base + 0, struct.pack('<hh', e[3], e[4]))
        g.p.write(base + 20, struct.pack('<H', e[5] & 1023))
        g.p.write(base + 8, struct.pack('<H', e[6]))
        g.p.write(base + 45, bytes([1]))
        g.p.write(base + 16, bytes([0, 0]))     # (alive, not flashing)
        # ...and the rest of it as a spawn leaves it, not as the ROAM run
        # did (it may have ended dead - F_HP 0, a death's keyframes - or
        # mid-flinch, or in a fight): running, whole, no shield, roaming
        # with nothing seen, the pistol; the lift at rest with nobody's
        # count running, as walift's pose() starts each ride
        a_run, n_run = watab("WA_A_RUN"), watab("WA_N_RUN")
        g.p.write(base + 10, bytes([0, a_run, n_run, 1, 0, 0]))
        g.p.write(base + 18, struct.pack('<h', 0))      # (F_Z: the ground)
        g.p.write(base + 36, struct.pack('<H', 0))      # (F_VH: step anew)
        g.p.write(base + 42, bytes([100]))              # (F_HP)
        g.p.write(base + 46, bytes(10))                 # (F_BST..F_BTGT)
        g.put("wa_bxh", lrest0, g.lift)
        g.put("wa_lon", 0)
        g.put("wa_loff", 0)
        g.p.write(sym["wa_rks"], bytes(4 * 8))  # (no rocket or grenade of
        g.p.write(sym["wa_rkn"], b"\x00")       # the ROAM's still flying)
        tkn0 = g.word("wa_tkn", signed=False)

        def park():
            """bots 1 and 2 dead and away: nobody for bot 0 to fight"""
            for i in (1, 2):
                g.p.write(base + i * FS + 17, bytes([250]))
                g.p.write(base + i * FS, struct.pack('<hh', 1000, 1900))
        park()
        lrest, ltop = g.word("wa_lrest"), g.word("wa_ltop")
        rose = top_z = dropped = False
        maxlh = 0
        for t in range(400):
            g.tick(2)
            if t % 50 == 0:
                park()
            x, y, z, ed, dead, wait = figs()[0]
            lh = lifth()
            maxlh = max(maxlh, lh)
            if edges[ed][2] == arenagen.LIFT_UP and lh > lrest:
                rose = True
            if z >= 156:
                top_z = True
            if top_z and edges[ed][2] == arenagen.DROP:
                dropped = True
            if dropped and z == 0:
                break
        ran = (g.word("wa_tkn", signed=False) - tkn0) & 0xFFFF
        check(ran >= t + 1 and g.byte("wa_quit") == 0 and
              g.byte("wa_arena") == 2 and g.word("wa_cwin") == 0,
              "THE LIFT: the match ran on under it, in the Heights (%d sim "
              "ticks in %d ticks' time, quit %d, arena %d, win shown %d)"
              % (ran, 2 * (t + 1), g.byte("wa_quit"), g.byte("wa_arena"),
                 g.word("wa_cwin")))
        check(rose and maxlh == ltop, "THE LIFT: bot 0 waited on it and it "
              "rose to the top (%d of %d)" % (maxlh, ltop))
        check(top_z and dropped, "THE LIFT: it walked onto the tower and "
              "dropped off it (top %s, drop %s)" % (top_z, dropped))
        for _ in range(150):
            g.tick(2)
            if lifth() == lrest:
                break
        check(lifth() == lrest, "THE LIFT: home again once empty (%d)"
              % lifth())

    if fails:
        print("waroutes: FAIL - %d of the routes' checks:" % len(fails))
        for f in fails:
            print("  " + f)
        sys.exit(1)
    print("waroutes: ok - the bots roam the graph and ride the lift")


if __name__ == "__main__":
    main()
