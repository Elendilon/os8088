#!/usr/bin/env python3
"""WireArena's bots see, face and shoot back (docs/plans/WIREARENA-AI-PLAN.md
4): fast more than good.

One boot into the Heights arena at 40 columns (the difficulty first set from
the Game menu), then, off the game's own variables (its symbols from
wirearena.asm assembled with a map, refused unless byte-identical to the
build):

  - THE MENU: "Bots: hard" makes the difficulty 2;
  - SIGHT: a bot stood at 40 random free points, the player at another each
    time: its verdict (F_BSEE) is the host's walk of the same sight grid
    (arenagen.sight_clear) every time;
  - THE DUEL, at each difficulty: a bot stood 400 units from the player,
    still, for 600 ticks. It turns to face the player (within ~7 degrees),
    fires at its gap (the shots within 20% of 600 / its gap), shows its cue
    (F_FLASH's yellow bit) and hits at its accuracy (within 15 points of
    45, 60 and 75%); each hit flashes the HUD's heart (wa_phit);
  - THE HUNT: a bot that sees the player, and then does not (the player
    taken out of its sight), hunts the node nearest where it saw them, gets
    there and roams again.

A bot that never turns, never fires, or hits at a wrong rate is red, and so
is a sight walk that disagrees with the host's.
"""
import math
import os
import random
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import arenagen                                                 # noqa: E402
import os88marty                                                # noqa: E402
import os88ui                                                   # noqa: E402
from os88fixture import need                                    # noqa: E402
from waweapons import Arena, amap, SYS, APPS, FS, ITEM, A_, anims  # noqa

F_BST, F_BSEE, F_BGOAL = 46, 49, 51


def main():
    need(APPS)
    sym = amap()
    A_.update(anims())
    boxes = [arenagen.bx(b) for b in arenagen.HEIGHTS_BOXES]
    top = arenagen.hmax(boxes)
    tall = [b for b in boxes if b.h >= top]
    grid = arenagen.sight_grid("a2", boxes)
    nodes = arenagen.HEIGHTS_GRAPH["nodes"]
    fails = []

    def check(ok, what):
        print("  %s %s" % ("ok  " if ok else "FAIL", what), flush=True)
        if not ok:
            fails.append(what)

    with os88ui.boot(SYS, apps=APPS, machine="os8088_5150_cga",
                     quick=True) as ui:
        m = ui.m
        w = ui.path("B:/WARENA.O88")
        os88marty.until(m, lambda _: any(c[0] == "Game" and any(
            i[0] == ITEM for i in c[3]) for c in ui.menus()),
            "WireArena's Game menu on the bar", guest=10)
        ui.menu_pick("Game", "Bots: hard")
        p = os88marty.Pkg(m, w)
        check(p.byte(sym["wa_diff"]) == 2, "THE MENU: 'Bots: hard' sets the "
              "difficulty (%d)" % p.byte(sym["wa_diff"]))
        ui.menu_pick("Game", ITEM)
        f0 = p.byte(sym["wa_frame"])
        os88marty.until(m, lambda _: p.byte(sym["wa_frame"]) != f0,
                        "the Heights arena's first frames", guest=20)
        m.pause()
        g = Arena(ui, w, sym)

        def fb(i, off, n=1):
            return g.p.read(sym["wa_figs"] + i * FS + off, n)

        def setb(i, off, data):
            g.p.write(sym["wa_figs"] + i * FS + off, data)

        def out_of_play(i):
            """bot i far away and dead for a while, out of the way"""
            setb(i, 17, bytes([250]))
            setb(i, 0, struct.pack('<hh', 1000, 1900))

        def place(i, x, y, ang=None, st=None):
            g.freeze(i, x, y)
            if ang is not None:
                setb(i, 4, struct.pack('<h', ang))
            if st is not None:
                setb(i, F_BST, bytes([st]))

        def free(rnd):
            while True:
                x, y = rnd.randint(40, 2008), rnd.randint(40, 2008)
                if not any(b[0] - 24 < x < b[2] + 24 and b[1] - 24 < y < b[3] + 24
                           for b in boxes if b.h > 0):
                    return x, y

        g.put("wa_hp", 30000)
        out_of_play(1)
        out_of_play(2)

        # SIGHT: bot 0 engaged (no field-of-view test), the player elsewhere
        rnd = random.Random(7)
        agree, n = 0, 40
        for _ in range(n):
            bx_, by_ = free(rnd)
            px, py = free(rnd)
            g.put("wa_hp", 30000)
            g.at(px, py, 0, ang=0)
            place(0, bx_, by_, st=1)
            g.tick(10)                  # (it looks every 8th tick)
            seen = fb(0, F_BSEE)[0] & 1
            want = arenagen.sight_clear(grid, (bx_, by_), (px, py))
            agree += (bool(seen) == want)
        check(agree == n, "SIGHT: the bot's look agrees with the host's walk "
              "of the same grid at %d of %d placements" % (agree, n))

        # THE DUEL, each difficulty
        for diff, gap, acc in ((0, 30, 45), (1, 20, 60), (2, 14, 75)):
            g.put("wa_diff", diff)
            g.put("wa_hp", 30000)
            g.at(1000, 300, 0, ang=0)
            place(0, 1400, 300, ang=0, st=1)    # engaged, facing away: it
            setb(0, 47, bytes([0, 0]))          # must turn (no reaction left)
            g.put("wa_bshots", 0)
            g.put("wa_bhits", 0)
            cue = flash = False
            angs = []
            for t in range(300):
                g.tick(2)
                if t % 5 == 0:
                    place(0, 1400, 300)
                    out_of_play(1)
                    out_of_play(2)
                g.put("wa_hp", 30000)
                if fb(0, 16)[0] & 0x80:
                    cue = True
                if g.byte("wa_phit"):
                    flash = True
                if t > 40:
                    angs.append(struct.unpack('<h', fb(0, 4, 2))[0] & 1023)
            shots, hits = g.word("wa_bshots"), g.word("wa_bhits")
            rate = 100.0 * hits / max(1, shots)
            off = max(min(abs(a - 512), 1024 - abs(a - 512)) for a in angs)
            check(off * 360 / 1024 < 8,
                  "THE DUEL (%d): it turns to face the player (worst %.1f "
                  "degrees off once on it)" % (diff, off * 360 / 1024))
            want = 600.0 / (gap + 1)          # (its gap counts on target)
            check(abs(shots - want) <= 0.2 * want + 2 and cue,
                  "THE DUEL (%d): %d shots in 600 ticks (gap %d: ~%.0f), its "
                  "yellow cue %s" % (diff, shots, gap, want,
                                     "seen" if cue else "NOT seen"))
            check(abs(rate - acc) <= 15 and flash,
                  "THE DUEL (%d): %d hits of %d, %.0f%% (its accuracy %d%%), "
                  "the heart flashed %s" % (diff, hits, shots, rate, acc,
                                            "yes" if flash else "NO"))

        # THE HUNT: seen at (1000, 300), then the player gone behind the annex
        g.put("wa_diff", 1)
        g.at(1000, 300, 0, ang=0)
        place(0, 1400, 300, ang=512, st=0)
        for _ in range(6):
            g.tick(2)
            place(0, 1400, 300)
            out_of_play(1)
            out_of_play(2)
        st0 = fb(0, F_BST)[0]
        g.at(64, 1024, 0, ang=0)                # (the back tunnel)
        hunted = goal = None
        back = False
        for t in range(300):
            g.tick(2)
            st = fb(0, F_BST)[0]
            if st == 2 and hunted is None:
                hunted = t
                goal = fb(0, F_BGOAL)[0]
            if hunted is not None and st == 0:
                back = True
                break
        x, y = struct.unpack('<hh', fb(0, 0, 4))
        nx, ny = nodes[goal] if goal is not None and goal < len(nodes) \
            else (0, 0)
        check(st0 == 1 and hunted is not None and back
              and math.hypot(x - nx, y - ny) < 150,
              "THE HUNT: engaged (%d), lost it, hunted node %r (%r) and, "
              "there (%d, %d), roams again (%s)"
              % (st0, goal, (nx, ny), x, y, back))

    if fails:
        print("wabots: FAIL - %d of the bots' checks:" % len(fails))
        for f in fails:
            print("  " + f)
        sys.exit(1)
    print("wabots: ok - the bots see, face, shoot and hunt")


if __name__ == "__main__":
    main()
