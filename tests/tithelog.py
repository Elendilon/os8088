#!/usr/bin/env python3
"""TITHE's ROUND, fought on the glass: the log, the frame and the music.

SPEC.md 97.12.8. The owner reported the round's LOG freezing the screen and
stopping the music, fullscreen worst. Measured on a 4.77 MHz 8088: every
line added redrew the whole log, every row padded to the box, inside the
worker's frame - up to 275 ms of a lane's 330 - and the round OPENED with a
whole-window repaint of 880 ms, the music waiting at the top of the worker's
loop through all of it (worst gap 439 ms). The log now draws a line once, a
line a frame, as wide as a log line, and scrolls with OSAPI_GFX_SCROLL; the
opening redraws what moved and lets the cells arrive a frame at a time.

WHAT IT ASSERTS, fullscreen on Hercules, and each went red on purpose first:

  1. THE MUSIC KEEPS ITS TIME THROUGH THE FIGHT: the sequencer's own worst
     gap between steps (`tm_gapmax`) is at most 3 ticks. It was 7-8.

  2. A WHOLE REPAINT MID-ROUND DRAWS THE BOARD. The paint path drew the PASS
     screen for any phase but planning, so a window uncovered mid-round lost
     the board and the log to "PLAYER 1 HAS COMMITTED".

  3. THE LOG, SCROLLED, IS EXACTLY A WHOLE REPAINT. The log is capped at four
     rows (`tg_lrcap`, a test's byte) so the round's nine lines scroll it five
     times; the glass at the round's end must be what a repaint draws from
     nothing. It went red on a copy made through the wrong ES - every line
     drawn twice, and the text written into the scratch part.

    make && make tithedisk && python3 tests/tithelog.py [machine]
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402
import titheterr as te                                    # noqa: E402

SEEDS = (8, 777)
SYMS = ("tg_fillq", "tg_tseed", "tg_ph", "tg_rs", "tg_ltot", "tg_ldrn",
        "tg_lrcap", "tm_gapmax", "ti_rpq", "ti_ox", "ti_oy", "ti_cw_box",
        "ti_ch_box", "ti_by", "ti_boardh", "ti_bx", "ti_boardw")
fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    src = open(os.path.join(ROOT, "apps/tithe/tithe.asm"), encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "tithelog-off.asm")
    out = os.path.join(ROOT, "build", "tithelog-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp], cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def run(mach, off):
    print("  --- %s, fullscreen" % mach)
    with os88ui.boot("build/os8088-360.img", apps="build/tithe360.img",
                     machine=mach) as ui:
        m = ui.m
        ui.path("B:/TITHE.O88")
        win = [w for w in os88geom.windows(m) if w.title == "Tithe"][0]
        seg = struct.unpack(
            "<H", bytes(m.read(os88geom.winptr(m, win) + os88geom.W_SEG, 2)))[0]
        ui.raise_window(win)
        os88marty.guest_sleep(m, 6.0)
        rw = lambda n: struct.unpack("<H", bytes(m.readseg(seg, off[n], 2)))[0]
        rb = lambda n: m.readseg(seg, off[n], 1)[0]

        def put(name, data):
            m.write(seg * 16 + off[name], data)

        put("tg_tseed", struct.pack("<HH", *SEEDS))
        put("tg_fillq", b"\x03")
        os88marty.until(m, lambda _: rb("tg_fillq") == 0, "the deal",
                        poll=0.2, limit=60.0)
        m.key("KeyF")
        os88marty.guest_sleep(m, 10.0)
        for side in (0, 1):                     # three plays a side
            for _ in range(3):
                m.key("KeyV")
                os88marty.guest_sleep(m, 2.5)
            m.key("Enter")
            os88marty.guest_sleep(m, 2.0)
            if side == 0:
                m.key("Enter")                  # P2 sits down
                os88marty.guest_sleep(m, 8.0)
        os88marty.until(m, lambda _: rb("tg_ph") == 3, "the round",
                        poll=0.05, limit=30.0)
        put("tg_lrcap", b"\x04")                # the log scrolls
        put("tm_gapmax", b"\0\0")

        # 2. a whole repaint mid-round is the BOARD
        os88marty.until(m, lambda _: rb("tg_rs") >= 2, "lane 2", poll=0.05,
                        limit=60.0)
        put("ti_rpq", b"\x01")
        os88marty.until(m, lambda _: rb("ti_rpq") == 0, "a repaint",
                        poll=0.05, limit=30.0)
        _, _, px = te.mono(m)
        x0, y0 = rw("ti_bx"), rw("ti_by")
        lit = sum(px[y][x] for y in range(y0, y0 + rw("ti_boardh"), 2)
                  for x in range(x0, x0 + rw("ti_boardw"), 2))
        check(rb("tg_ph") == 3 and lit > 500, "2. a whole repaint mid-round "
              "draws the board, not the pass screen", "phase %d, %d lit"
              % (rb("tg_ph"), lit))

        # 1. the music, through the fight
        os88marty.until(m, lambda _: rb("tg_rs") >= 7
                        and rw("tg_ldrn") == rw("tg_ltot"), "the round's end",
                        poll=0.05, limit=120.0)
        gap = rw("tm_gapmax")
        check(0 < gap <= 3, "1. the music's worst gap through the fight is "
              "at most 3 ticks", "%d ticks (%d ms)" % (gap, gap * 55))

        # 3. the scrolled log is a whole repaint
        m.key("KeyP")
        os88marty.guest_sleep(m, 0.3)
        _, _, a = te.mono(m)
        put("ti_rpq", b"\x01")
        os88marty.until(m, lambda _: rb("ti_rpq") == 0, "a repaint",
                        poll=0.05, limit=30.0)
        os88marty.guest_sleep(m, 0.2)
        _, _, b = te.mono(m)
        m.key("KeyP")
        x0, y0 = rw("ti_ox"), rw("ti_oy")
        d = [(x, y) for y in range(y0, y0 + rw("ti_ch_box"))
             for x in range(x0, x0 + rw("ti_cw_box")) if a[y][x] != b[y][x]]
        check(rw("tg_ltot") > 4 and not d, "3. the log, scrolled %d times, is "
              "exactly a whole repaint" % max(0, rw("tg_ltot") - 4),
              "%d lines, %d px, first %s" % (rw("tg_ltot"), len(d), d[:4]))


def main():
    off = offsets()
    for mach in (sys.argv[1:] or ("os8088_5150_herc_gla",)):
        run(mach, off)
    print("tithelog: %s" % ("ok" if not fails else "FAILED %d" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
