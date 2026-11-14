#!/usr/bin/env python3
"""WireArena's weapons and pickups (docs/plans/WIREARENA-WEAPONS-PLAN.md).

One boot into the Heights arena at 40 columns, then each piece of the
round checked off the game's own variables (its symbols from wirearena.asm
assembled with a map, refused unless byte-identical to the build):

  - the start: the pistol, 6 in its magazine, 100 health, all four pickups
    there (`wa_pkon`);
  - the pistol: three shots kill a dummy (34 each), and it dies by the
    pistol's death (DEATH, `F_KILL` 0);
  - the shotgun pickup on the ramp platform: taken, held, 3 and 3, gone
    from the arena; key 2 selects it again after key 1;
  - the shotgun: one direct close shot kills, red the whole time (F_FLASH
    held with F_DEAD) and by its own collapse (COLLAPSE, `F_KILL` 1);
  - the rocket launcher on the tower: taken and held; key 3 selects it;
  - dummy 0 lives with a shield (`F_SH` 100); a rocket flies (state 1, not
    instant), hits it directly and kills it outright through the shield,
    into bits (GIB, `F_KILL` 2), and once the bits have flown it is GONE
    (`F_NFR` 0 - the renderer skips it);
  - a rocket into a wall close by: its splash hurts the player;
  - the health pack in the back tunnel: health back to 100; the shield
    pack on the back room's jump platform: shield 100;
  - a taken pickup comes back after its time (the shotgun's, 10 s);
  - detail levels moved to F1..F5: F1 makes the level 0 (Very Low).

Each is a guest-memory assertion: a broken reach, a lost reload, a damage
table off by a shift or a death mapped to the wrong animation each turn a
line red. `--shots DIR` writes a picture at each step.
"""
import argparse
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import os88marty                                               # noqa: E402
import os88ui                                                  # noqa: E402
from os88fixture import need                                   # noqa: E402
from walift import Game, amap, SYS, APPS                       # noqa: E402

ITEM = "Heights arena, 40 columns"
FS = 44                         # F_SIZE (apps/wirearena/waconst.inc)


def anims():
    """The animations' first keyframes, as tools/arenagen.py made them for
    this build (build/watab.inc's WA_A_*)"""
    import re
    import os88build
    t = open(os.path.join(os.path.dirname(__file__), "..",
                          os88build.at("build/"), "watab.inc")).read()
    return {k: int(v) for k, v in re.findall(r"WA_A_(\w+) equ (\d+)", t)}


class Arena(Game):
    def byte(self, n, off=0):
        return self.p.read(self.sym[n] + off, 1)[0]

    def fig(self, i):
        d = self.p.read(self.sym["wa_figs"] + i * FS, FS)
        w = lambda o: struct.unpack_from('<h', d, o)[0]
        return dict(x=w(0), y=w(2), sh=d[10], anim=d[11], nfr=d[12],
                    flash=d[16], dead=d[17], z=w(18), head=w(20) & 1023,
                    hp=d[42], kill=d[43])

    def arms(self):
        return dict(wpn=self.byte("wa_wpn"), own=self.byte("wa_own"),
                    mag=list(self.p.read(self.sym["wa_mag"], 3)),
                    res=list(self.p.read(self.sym["wa_res"], 3)),
                    rld=self.byte("wa_rld"), hp=self.word("wa_hp"),
                    sh=self.word("wa_sh"), pkon=self.byte("wa_pkon"),
                    level=self.byte("wa_level"))

    def at(self, x, y, feet, ang=None):
        """The player standing at (x, y) on `feet`, every key up."""
        self.m.pause()
        for n, v in (("wa_px", x), ("wa_py", y), ("wa_pxf", 0), ("wa_pyf", 0),
                     ("wa_pitch", 0), ("wa_jz", 0), ("wa_jv", 0),
                     ("wa_feet", feet), ("wa_fpx", -1)):
            self.put(n, v)
        if ang is not None:
            self.put("wa_ang", ang << 6)
        self.tick(2)

    def ahead(self, i, d):
        """d units ahead of dummy i on its patrol, facing it: it walks into
        the crosshair, so no shot depends on the frame it lands in."""
        f = self.fig(i)
        a = f["head"] * 2 * math.pi / 1024
        self.at(int(f["x"] + d * math.cos(a)), int(f["y"] + d * math.sin(a)),
                f["z"], ang=(f["head"] + 512) & 1023)

    def press(self, key, ticks=4):
        """A key held long enough for a frame to poll it at any frame rate
        here (the trigger and the keys are read once a frame)."""
        self.m.key(key, up=False)
        self.tick(ticks)
        self.m.key(key, down=False)
        self.tick(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", help="write a picture at each step here")
    a = ap.parse_args()
    need(APPS)
    sym = amap()
    A = anims()
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
        ui.menu_pick("Game", ITEM)
        p = os88marty.Pkg(m, w)
        f0 = p.byte(sym["wa_frame"])
        os88marty.until(m, lambda _: p.byte(sym["wa_frame"]) != f0,
                        "the Heights arena's first frames", guest=20)
        m.pause()
        g = Arena(ui, w, sym)

        def shot(name):
            if a.shots:
                os.makedirs(a.shots, exist_ok=True)
                wd, ht, d = m.fbuf(0)
                os88marty.write_png_rgb(os.path.join(a.shots, name + ".png"),
                                        wd, ht, d)

        g.tick(4)
        s = g.arms()
        check(s["wpn"] == 0 and s["mag"][0] == 6 and s["hp"] == 100
              and s["sh"] == 0 and s["pkon"] == 15,
              "the start: the pistol, 6 loaded, 100 health, four pickups "
              "(%r)" % s)
        shot("00-start")

        n = 0
        while n < 4 and not g.fig(1)["dead"]:
            g.ahead(1, 300)
            g.press("ControlLeft")
            n += 1
        f = g.fig(1)
        check(f["dead"] and n == 3 and f["kill"] == 0
              and f["anim"] == A["DEATH"],
              "the pistol: three shots kill, by the fall (%d shots, %r)"
              % (n, f))
        check(g.arms()["mag"][0] == 3, "the pistol: three spent of six")
        shot("01-pistol-kill")

        g.at(1248, 1000, 80, ang=256)
        g.tick(2)
        s = g.arms()
        check(s["own"] & 2 and s["wpn"] == 1 and s["mag"][1] == 3
              and s["res"][1] == 3 and not s["pkon"] & 4,
              "the shotgun on the ramp platform: taken, held, 3 and 3, gone "
              "(%r)" % s)
        g.press("Digit1")
        g.press("Digit2")
        check(g.arms()["wpn"] == 1, "keys 1 then 2: the shotgun again")
        shot("02-shotgun")

        g.tick(10)
        g.ahead(2, 110)
        g.press("ControlLeft")
        f = g.fig(2)
        check(f["dead"] and f["kill"] == 1 and f["anim"] == A["COLLAPSE"]
              and f["flash"] > 0 and abs(f["flash"] - f["dead"]) <= 1,
              "the shotgun: one close shot kills, red as long as it lies "
              "(%r)" % f)
        g.tick(6)
        shot("03-shotgun-kill")

        g.at(1952, 1000, 160, ang=512)
        g.tick(2)
        s = g.arms()
        check(s["own"] & 4 and s["wpn"] == 2 and s["mag"][2] == 3
              and not s["pkon"] & 8,
              "the rocket launcher on the tower: taken and held (%r)" % s)
        g.press("Digit1")
        g.press("Digit3")
        check(g.arms()["wpn"] == 2, "keys 1 then 3: the launcher again")

        f = g.fig(0)
        check(f["sh"] == 100 or f["dead"], "dummy 0 lives with a shield "
              "(%r)" % f)
        g.tick(30)
        g.ahead(0, 420)
        shot("04-shielded")
        g.press("ControlLeft")
        flew = 0
        for _ in range(40):
            rk = [struct.unpack('<4h', g.p.read(sym["wa_rks"] + 8 * k, 8))
                  for k in range(3)]
            if any(r[3] == 1 for r in rk):
                flew += 1
            if g.fig(0)["dead"]:
                break
            g.tick(1)
        shot("05-explosion")
        f = g.fig(0)
        check(f["dead"] and f["kill"] == 2 and f["anim"] == A["GIB"]
              and flew >= 2,
              "the rocket: it flies (%d ticks seen in flight) and a direct "
              "hit kills through the shield, into bits (%r)" % (flew, f))
        g.tick(6)
        shot("06-bits")
        g.tick(30)
        check(g.fig(0)["nfr"] == 0, "the rocket's kill: gone once its bits "
              "have flown")

        hp0 = g.arms()["hp"]
        g.tick(80)                      # (the launcher reloads: 2.5 s)
        g.at(1790, 1024, 0, ang=0)      # the tower's face 66 units ahead
        g.press("ControlLeft")
        g.tick(10)
        hp1 = g.arms()["hp"]
        check(hp1 < hp0, "a rocket into a wall close by: its splash hurts "
              "the player (%d -> %d)" % (hp0, hp1))

        g.at(64, 1050, 0, ang=768)
        g.tick(2)
        s = g.arms()
        check(s["hp"] == 100 and not s["pkon"] & 1,
              "the health pack in the back tunnel: health 100 (%r)" % s)
        g.at(480, 1050, 48, ang=768)
        g.tick(2)
        s = g.arms()
        check(s["sh"] == 100 and not s["pkon"] & 2,
              "the shield pack on the jump platform: shield 100 (%r)" % s)
        shot("07-shield")

        g.tick(300)
        check(g.arms()["pkon"] & 4, "the shotgun's pickup back after 10 s")

        g.press("F1")
        check(g.arms()["level"] == 0, "F1: the detail level Very Low")
        g.press("F3")
        check(g.arms()["level"] == 2, "F3: Medium")

    if fails:
        print("waweapons: FAIL - %d of the round's checks:" % len(fails))
        for f in fails:
            print("  " + f)
        sys.exit(1)
    print("waweapons: ok - three weapons, four pickups, three deaths")


if __name__ == "__main__":
    main()
