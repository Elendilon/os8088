#!/usr/bin/env python3
"""DOT DELIRIUM's PEN, and the pellets that share its bug class (SPEC.md 93).

Three questions, all three of them field reports:

  A  EVERY PELLET IS REFRESHED, not just the first.  `dd_pills_blit` walked
     the pellet list with SI as its counter and `dd_tile_put` loaded SI with
     the band's address, so the first pellet trampled the loop.  The other
     three did not merely stop blinking: the first actor to cross one
     composed it in whichever phase was current, and if that was the dark
     half the pellet was gone for the rest of the board.  The report was
     *"the dot in the upper left corner is blinking, the rest can be eaten
     but not seen"*, and the upper left is pellet 0.
  B  A PENNED GHOST WANDERS THE PEN (SPEC.md 93.8.6).  The interior is six
     tiles by three; a ghost that bobs one up and one down reads as a machine
     waiting.  This asks for a real share of the box and more than one column.
  C  A GHOST THAT GOT HOME AS EYES STAYS THERE for DD_PENWAIT = 55 ticks
     before it comes back out, wandering while it waits.

BREAK IT ON PURPOSE: make `dd_pills_flip` walk its list in SI and call
`dd_tile_put`, the way it used to, and leg A goes red - the run that proved
this saw `dd_tile_put` reached for {(1,3), (1,23), (13,17)} where the fixed
build reaches every pellet.  Put `dd_gh_house` back on its up/down bob and
leg B reads three tiles in one column.  Send `dd_gh_home`'s `.arrived`
straight to GS_OUT and leg C reads a wait of 0.

WHAT THIS ROW DOES NOT READ is the pellet's colour or its shape - those are a
look, and leg B of tests/dotdel.py is where the blink's PIXELS are checked.
Leg A here is about which pellets the refresh reaches, which is a fact and
not a picture: it is read off SI at a breakpoint inside `dd_pills_flip`'s own
loop, so a walk that stops early is caught wherever it stops.

One adapter is enough for all three: none of them is about the surface.  It
runs on the Hercules 5150 because that is the machine the reports came from.
"""
import argparse
import os
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import os88build                                            # noqa: E402
from dotdel import PKG, bss, Probe                          # noqa: E402
import os88ui                                               # noqa: E402

MACHINE = "os8088_5150_herc_gla"
GS = {0: "HOUSE", 1: "OUT", 2: "ROAM", 3: "FRIGHT", 4: "EYES"}
GS_HOUSE, GS_ROAM, GS_EYES = 0, 2, 4
DDS_PLAY = 2

PENWAIT = 55                    # DD_PENWAIT, ticks
WAIT_LO, WAIT_HI = 45, 70       # ...and the window a sampled reading may land
                                # in: the sampler cannot see the tick it
                                # arrived on, so it always reads a little low
PEN_TILES = 5                   # of the pen's eighteen
PEN_COLS = 2                    # ...spread over at least this many columns


def codeoff(name):
    """The org-0 offset of a CODE label, the way dotdel.bss() reads a bss one.

    The package is assembled at org 0 into one flat binary, so a label's
    offset is what nasm emits for `dw <label>` - the same trick bss() plays,
    without os88_image_end's bias.
    """
    src = open(os.path.join(ROOT, "apps/dotdel/dotdel.asm")).read()
    probe = (src.replace("    OS88_IMAGE_END", "")
             + "\ndd_cprobe:\n    dw %s\n    OS88_IMAGE_END\n" % name)
    with tempfile.TemporaryDirectory() as td:
        asm = os.path.join(td, "probe.asm")
        binf = os.path.join(td, "probe.bin")
        open(asm, "w").write(probe)
        subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                        "-I", "apps/dotdel/", "-o", binf, asm],
                       cwd=ROOT, check=True)
        return struct.unpack("<H", open(binf, "rb").read()[-2:])[0]


def leg_a(ui, p, say):
    """Every pellet on the board gets refreshed, not only pellet 0."""
    m = ui.m
    m.pause()
    npill = p.w("dd_piln")
    where = [(p.b("dd_pilc", i), p.b("dd_pilr", i)) for i in range(npill)]
    m.go()
    if npill < 2:
        say("A  FAIL: the board has %d pellet(s) - nothing to walk" % npill)
        return 1
    # SI at the top of dd_pills_flip's loop is the pellet it is about to
    # consider, so a walk that stops early is caught wherever it stops.
    off = codeoff("dd_pills_flip.each")
    m.breakpoints([{"type": "execseg", "seg": p.seg, "off": off}])
    want = set(range(npill))
    seen = set()
    for _ in range(12 * npill):
        m.go()
        if m.wait_stop(8.0) is None:
            break
        seen.add(m.regs()["si"])
        if want <= seen:
            break
    m.breakpoints([])
    m.go()
    miss = want - seen
    if miss:
        say("A  FAIL: %d of %d pellet(s) never refreshed: %s  (the walk "
            "reached indices %s)"
            % (len(miss), npill, sorted(where[i] for i in miss), sorted(seen)))
        return 1
    say("A  ok: all %d pellets refreshed %s" % (npill, sorted(where)))
    return 0


def leg_b(ui, p, say, secs=12.0):
    """A ghost sitting in the pen moves round it."""
    m = ui.m
    tiles = {}
    t0 = time.time()
    while time.time() - t0 < secs:
        m.pause()
        for g in range(4):
            if p.b("dd_gs", g) == GS_HOUSE:
                tiles.setdefault(g, set()).add(
                    (p.b("dd_ac", g + 1), p.b("dd_ar", g + 1)))
        m.go()
        time.sleep(0.08)
    if not tiles:
        say("B  FAIL: no ghost was in the pen at all over %.0fs" % secs)
        return 1
    best = max(len(v) for v in tiles.values())
    bestc = max(len({c for c, _ in v}) for v in tiles.values())
    for g, ts in sorted(tiles.items()):
        say("     ghost %d: %d tile(s), %d column(s)"
            % (g, len(ts), len({c for c, _ in ts})))
    if best < PEN_TILES or bestc < PEN_COLS:
        say("B  FAIL: the busiest penned ghost saw %d tile(s) in %d column(s) "
            "- want %d in %d. A bob is 3 tiles in 1"
            % (best, bestc, PEN_TILES, PEN_COLS))
        return 1
    say("B  ok: %d of the pen's 18 tiles, over %d columns" % (best, bestc))
    return 0


def leg_c(ui, p, say, want=3, tries=10):
    """Eyes get home and serve DD_PENWAIT there before coming back out."""
    m = ui.m
    base = (p.seg << 4) + p.names["dd_gs"]
    lives = (p.seg << 4) + p.names["dd_lives"]
    got = 0
    fail = 0
    while got < want and tries > 0:
        tries -= 1
        g = None
        for _ in range(80):
            m.pause()
            for i in range(4):
                if p.b("dd_gs", i) == GS_ROAM:
                    g = i
                    break
            m.go()
            if g is not None:
                break
            time.sleep(0.2)
        if g is None:
            say("C  FAIL: no ghost was ever roaming, so none could be eaten")
            return 1
        m.pause()
        m.write(lives, bytes([99]))         # an unsteered Smiles dies often,
        m.write(base + g, bytes([GS_EYES]))  # and a death resets every ghost
        m.go()
        tin = None
        pen = set()
        t0 = time.time()
        verdict = None
        while time.time() - t0 < 40:
            m.pause()
            st = p.b("dd_gs", g)
            tick = p.w("dd_anim")
            state = p.b("dd_state")
            ac, ar = p.b("dd_ac", g + 1), p.b("dd_ar", g + 1)
            m.go()
            if state != DDS_PLAY:
                verdict = ("skip",)
                break
            if st == GS_HOUSE:
                if tin is None:
                    tin = tick
                pen.add((ac, ar))
            elif tin is not None:
                verdict = ("done", tick - tin, len(pen), GS.get(st, "?"))
                break
            time.sleep(0.05)
        if verdict is None:
            say("C  FAIL: ghost %d never came back out of the pen" % g)
            return 1
        if verdict[0] == "skip":
            continue                        # a death: this leg is about the pen
        _, waited, ntiles, now = verdict
        ok = WAIT_LO <= waited <= WAIT_HI
        say("     ghost %d waited %d tick(s) (want ~%d), %d tile(s), then %s%s"
            % (g, waited, PENWAIT, ntiles, now, "" if ok else "   <-- WRONG"))
        if not ok:
            fail = 1
        got += 1
    if got == 0:
        say("C  FAIL: every trial was cut short by a death")
        return 1
    if fail:
        say("C  FAIL: a wait fell outside %d..%d ticks" % (WAIT_LO, WAIT_HI))
        return 1
    say("C  ok: %d ghost(s) home, penned for ~%d ticks, then out" % (got, PENWAIT))
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default=os88build.at("build/os8088-360.img"))
    ap.add_argument("--apps", default=os88build.at("build/apps360.img"))
    ap.add_argument("--machine", default=MACHINE)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)

    out = []

    def say(s):
        out.append(s)
        if a.verbose:
            print(s, flush=True)

    names = bss()
    fail = 0
    with os88ui.boot(a.img, apps=a.apps, machine=a.machine) as ui:
        ui.path(PKG)
        p = Probe(ui, names)
        ui.m.key("Enter")
        time.sleep(3.0)
        ui.m.pause()
        ui.m.write((p.seg << 4) + names["dd_lives"], bytes([99]))
        ui.m.go()
        fail += leg_a(ui, p, say)
        fail += leg_b(ui, p, say)
        fail += leg_c(ui, p, say)

    if not a.verbose:
        for s in out:
            print(s)
    print("dotdelpen: %s" % ("ok" if not fail else "%d leg(s) FAILED" % fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
