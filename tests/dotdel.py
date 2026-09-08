#!/usr/bin/env python3
"""DOT DELIRIUM on the glass: the attract screen, a game, and the bracket.

Five questions, and each one has gone wrong at least once during the build
(SPEC.md 93):

  A  THE TITLE SCREEN DRAWS.  Its own lettering, the saved table, the play
     line and a strip of playfield with actors in it - which is four separate
     compositors and any of them can come up empty without erroring.
  B  THE PLAY LINE BLINKS.  Two captures a beat apart differ in that line's
     band and NOWHERE ELSE outside the playfield strip.
  C  ENTER STARTS A GAME, and Smiles then EATS: the dot count falls and the
     score rises. A maze chase whose dots never go is a maze chase that never
     ends.
  D  THE BOARD IS CUT FROM THE SURFACE (SPEC.md 93.3).  The tile is what the
     adapter's own pixel shape and the live content box say it should be, and
     going fullscreen re-cuts it BIGGER and leaving puts it back.
  E  THE FRAME IS THE TICK (SPEC.md 93.6).  Rendered frames per guest second
     against the game's own tick counter, on a cycle-accurate 4.77 MHz 8088.
     This is the row's reason for existing: the game held 100.0% of the tick
     on every adapter when it shipped, and three separate things - a board
     walk, a `font_run` and a pair of divides - each took it to 60% while
     everything still LOOKED right (SPEC.md 93.5.3).

BREAK IT ON PURPOSE: put `dd_pills_blit` back on a board walk and leg E goes
red at ~63%, and so does copying the wall picture into every actor's band
(SPEC.md 93.5.3 item 4, which cost 12 ms of a 54.9 ms frame). What this row
does NOT read is a wrong COLOUR or a dot drawn half - those are a look, and
SPEC.md 93.5.1 and 93.5.4 are where they are written down.

DOT DELIRIUM RIDES THE ORDINARY APPS DISK at every geometry (SPEC.md 93.13):
360KB fits it at 352 of 354 clusters, which is what taking the old Pac-Man
port off that disk bought.
"""
import argparse
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import os88build                                            # noqa: E402
import os88geom as G                                        # noqa: E402
import os88marty                                            # noqa: E402
import os88ui                                               # noqa: E402

PKG = "B:/GAMES/DOTDEL.O88"

# The three adapters, with the tile SPEC.md 93.3's table says each should get
# in a window on a 360KB machine. VGA is an XT with a VGA card; the two 1bpp
# ones are 5150s with the GLaBIOS twin, because the IBM ROM is not in the tree.
ARMS = (
    ("vga",  "os8088_xt_vga",        (16, 13)),
    ("cga",  "os8088_5150_cga_gla",  (8, 4)),
    ("herc", "os8088_5150_herc_gla", (16, 9)),
)

TICK_HZ = 18.2065
CPU_HZ = 4772727.0
# The floor leg E fails under. The game measures 100.0% on all three adapters;
# 90% is a fifth of a tick of slack, and the three regressions this row exists
# to catch each cost 35-45%.
FPS_FLOOR = 0.90


def bss(path="apps/dotdel/dotdel.asm"):
    """The package's .bss offsets, from the source rather than from a copy.

    The names are `equ os88_image_end + N`, so a probe build that emits each
    one MINUS os88_image_end gives N whatever else it changes about the image.
    """
    import re
    import subprocess
    import tempfile
    src = open(os.path.join(ROOT, path)).read()
    names = re.findall(r"^\s+(?:DWORDV|DBYTEV|DBUFV)\s+(\w+)", src, re.M)
    probe = src.replace("    OS88_IMAGE_END", "") + "\ndd_probe:\n"
    for n in names:
        probe += "    dw %s - os88_image_end\n" % n
    probe += "    OS88_IMAGE_END\n"
    with tempfile.TemporaryDirectory() as td:
        asm = os.path.join(td, "probe.asm")
        binf = os.path.join(td, "probe.bin")
        open(asm, "w").write(probe)
        subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                        "-I", "apps/dotdel/", "-o", binf, asm],
                       cwd=ROOT, check=True)
        d = open(binf, "rb").read()
    vals = struct.unpack("<%dH" % len(names), d[len(d) - 2 * len(names):])
    img = struct.unpack("<H", open(os88build.at("build/dotdel.bin"),
                                   "rb").read()[8:10])[0]
    return {n: img + v for n, v in zip(names, vals)}


class Probe(object):
    """The package's own state, read out of its segment."""

    def __init__(self, ui, names, title="Dot Delirium"):
        self.m, self.names = ui.m, names
        w = ui.window(title)
        raw = bytes(self.m.read(G._sym(self.m, None)("wm_wins"),
                                G.MAX_WIN * G.WIN_SIZE))
        self.seg = struct.unpack_from("<H", raw, w.i * G.WIN_SIZE + G.W_SEG)[0]
        if not self.seg:
            raise RuntimeError("no package segment for %r" % title)

    def w(self, n, i=0):
        a = (self.seg << 4) + self.names[n] + i * 2
        return struct.unpack("<H", bytes(self.m.read(a, 2)))[0]

    def b(self, n, i=0):
        return bytes(self.m.read((self.seg << 4) + self.names[n] + i, 1))[0]


def screen(m):
    """(w, h, bytes-per-pixel-triple) of the glass, whichever card it is."""
    v = m.video()
    if v["type"] == "vga" or os88marty.video_is_text(v):
        w, h, data = m.fbuf(0)
        return w, h, bytes(data)
    w, h, rows = m.vram(None)
    return w, h, b"".join(bytes(r) for r in rows)


def run_arm(tag, machine, want_tile, a, say):
    fail = []
    names = bss()
    with os88ui.boot(a.image, apps=a.apps, machine=machine) as ui:
        m = ui.m
        ui.path(PKG)
        time.sleep(2)
        p = Probe(ui, names)

        # --- D: the tile is cut from the surface ---------------------------
        tile = (p.w("dd_tw"), p.w("dd_th"))
        if not p.b("dd_ok"):
            fail.append("%s: the layout refused the content box (%dx%d)"
                        % (tag, p.w("dd_cw"), p.w("dd_ch")))
        if tile != want_tile:
            fail.append("%s: tile %dx%d, want %dx%d for a windowed %s "
                        "(SPEC.md 93.3's table)"
                        % (tag, tile[0], tile[1], want_tile[0], want_tile[1],
                           tag.upper()))
        else:
            say("%s: tile %dx%d, board %dx%d, %d bpp"
                % (tag, tile[0], tile[1], p.w("dd_mw"), p.w("dd_mh"),
                   p.b("dd_bpp")))

        # --- A: the title screen has all four of its parts -----------------
        if p.b("dd_state") != 0:
            fail.append("%s: did not open on the attract screen (state %d)"
                        % (tag, p.b("dd_state")))
        if p.w("dd_titw") < 8 * 12:
            fail.append("%s: the title is %d px wide - it is twelve letters"
                        % (tag, p.w("dd_titw")))
        if p.w("dd_hs") == 0:
            fail.append("%s: the score table's first row is zero - the "
                        "built-in table never loaded" % tag)
        moved = (p.w("dd_x"), p.w("dd_y"))
        time.sleep(2)
        if (p.w("dd_x"), p.w("dd_y")) == moved:
            fail.append("%s: the demo's Smiles has not moved in two seconds - "
                        "the attract screen is a still picture" % tag)

        # --- B: the play line blinks ----------------------------------------
        seen = set()
        for _ in range(14):
            seen.add(screen(m)[2])
            time.sleep(0.35)
        if len(seen) < 2:
            fail.append("%s: the screen never changed over five seconds - "
                        "nothing on the attract screen is alive" % tag)

        # --- C: Enter starts a game and Smiles eats -------------------------
        m.key("Enter")
        time.sleep(3)
        # READY, PLAY, DIE or the flash between boards - anything but the
        # title. NOT `== PLAY`: nobody is steering Smiles for these three
        # seconds and since SPEC.md 93.8's ghosts hunt by line of sight one of
        # them catches him inside the window on the faster adapters, so an
        # exact state here failed for the AI working.
        if p.b("dd_state") not in (1, 2, 3, 4):
            fail.append("%s: Enter did not start a game (state %d)"
                        % (tag, p.b("dd_state")))
        dots0, score0 = p.w("dd_ndots"), p.w("dd_score")
        # STEER HIM, AND HOLD THE KEY. dd_input asks OSAPI_KEY_DOWN whether a
        # key IS DOWN once a logic step (SPEC.md 93.7.2), so a make-and-break
        # inside one frame is a keystroke the game is entitled to miss - which
        # is the whole point of polling rather than eventing. Left is where he
        # starts facing and a wall is where that ends, so a game nobody drives
        # eats a handful of dots and then stands still for ever.
        for k in ("ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight",
                  "ArrowUp", "ArrowRight"):
            m.key(k, down=True, up=False)
            time.sleep(1.2)
            m.key(k, down=False, up=True)
        dots1, score1 = p.w("dd_ndots"), p.w("dd_score")
        if dots1 >= dots0 or score1 <= score0:
            fail.append("%s: six seconds of steered play ate %d dots and "
                        "scored %d - Smiles is not eating (SPEC.md 93.9)"
                        % (tag, dots0 - dots1, score1 - score0))
        else:
            say("%s: ate %d dots for %d points"
                % (tag, dots0 - dots1, score1 - score0))

        # --- E: the frame is the tick ---------------------------------------
        for what in ("windowed", "fullscreen"):
            if what == "fullscreen":
                m.key("KeyF")
                time.sleep(3)
                big = (p.w("dd_tw"), p.w("dd_th"))
                if big[0] * big[1] <= tile[0] * tile[1]:
                    fail.append("%s: the bracket's tile is %dx%d against the "
                                "window's %dx%d - fullscreen did not re-cut "
                                "the board from its own surface (SPEC.md "
                                "93.4.2)" % (tag, big[0], big[1],
                                             tile[0], tile[1]))
            if p.w("dd_frames") in (0, 0xFFFF) or p.b("dd_state") == 255:
                import os88marty as _mm
                _w,_h,_d = m.fbuf(0)
                _mm.write_png_rgb("/tmp/claude-0/-home-user-os8088/359b914f-5179-53b4-9f92-36c43b355829/scratchpad/dbg2_%s_%s.png" % (tag, what), _w, _h, _d)
                say("DBG shot taken: state=%d frames=%d" % (p.b("dd_state"), p.w("dd_frames")))
            c0, t0, f0 = m.status()["cycles"], p.w("dd_anim"), p.w("dd_frames")
            time.sleep(8)
            c1, t1, f1 = m.status()["cycles"], p.w("dd_anim"), p.w("dd_frames")
            gs = (c1 - c0) / CPU_HZ
            ticks, frames = (t1 - t0) / gs, (f1 - f0) / gs
            share = frames / ticks if ticks else 0.0
            say("%s %s: %.2f frames/s against %.2f ticks/s = %.1f%%"
                % (tag, what, frames, ticks, 100.0 * share))
            if share < FPS_FLOOR:
                fail.append("%s %s: %.2f fps against a %.2f/s tick is %.1f%% "
                            "- the frame no longer fits the tick (SPEC.md "
                            "93.6, and 93.5.3 for the three things that have "
                            "cost this before)"
                            % (tag, what, frames, ticks, 100.0 * share))
        m.key("Escape")
        time.sleep(3)
        back = (p.w("dd_tw"), p.w("dd_th"))
        if back != tile:
            fail.append("%s: leaving the bracket left the tile at %dx%d, not "
                        "the window's %dx%d" % (tag, back[0], back[1],
                                                tile[0], tile[1]))
    return fail


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    ap.add_argument("--arm", default=None,
                    help="one of vga, cga, herc (default: all three)")
    a = ap.parse_args(argv)
    say = lambda s: print("  " + s)

    arms = [x for x in ARMS if a.arm in (None, x[0])]
    if not arms:
        sys.exit("dotdel: no such arm %r - one of %s"
                 % (a.arm, ", ".join(x[0] for x in ARMS)))
    fail = []
    for tag, machine, tile in arms:
        fail += run_arm(tag, machine, tile, a, say)
    if fail:
        print("dotdel: %d FAILED" % len(fail))
        for f in fail:
            print("    FAIL: %s" % f)
        return 1
    print("dotdel: %d arm(s) passed" % len(arms))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
