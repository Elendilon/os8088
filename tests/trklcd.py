#!/usr/bin/env python3
"""trklcd - the XT visualiser button, and the LCD drawn by its inputs
(SPEC.md 45.23.1, 45.21.8)

    make trkrate && python3 tests/trklcd.py

On a 5150 with XT mode pre-armed (tier 0, SPEC.md 45.9), playing BEVERLY.MOD
at 5.5 kHz:

  THE BUTTON (45.23.1) - the forced XT meter no longer greys it:
    1. live at 5.5 kHz, and a click picks Off, a second VU Meter again
    2. R to 11 kHz forces none and GREYS it, and a click there does nothing
    3. R back makes it live again

  THE LCD (45.21.8) - a line is composed only when its KEY moves, and then
  only the cells that differ from its shadow are lettered:
    4. compositions run at about one a second (the clock), not one per line
       per frame - the old face composed ~60 a second
    5. THE GLASS IS RIGHT. The emulator is stopped mid-song, the LCD and the
       status line are read, a full repaint is forced, and the same pixels
       are read again once the frame that took it has FINISHED drawing: the
       diff-drawn glass must equal the fresh one, pixel for pixel. A build
       that letters the changed span one cell short fails this with 182
       pixels wrong; a check that grabs before the repaint finishes passes
       it, which is why the wait is on [tw_inframe] and not on [tw_dirty]
       (tw_update clears that BEFORE it draws, and a full LCD is a large part
       of a second on an 8088).

Stopping the guest makes the comparison exact, and a line whose key moved
between the two reads (a second ticked) makes the attempt retry rather than
count - the keys are read beside the pixels.

It wants a Sound Blaster, which in a container means os8088_5150_herc_sb_gla
(Hercules, as the owner's 5150 is).
"""
import os
import re
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)
import os88marty, os88mouse, os88sym, dispcp, os88rate           # noqa: E402
from os88fixture import need                                      # noqa: E402
from os88rate import symbols, scan                                # noqa: E402

DISK = "build/trkship360.img"          # the SHIPPED player
MACHINE = "os8088_5150_herc_sb_gla"
HZ = 4772728.0
VIZ = 8 + 4                            # TW_NTB + the TWO_VIZ option slot
fails = []


def check(name, got, want):
    ok = got == want
    print("  %-52s %-10s %s" % (name, got, "ok" if ok else "FAIL, want %s" % (want,)))
    if not ok:
        fails.append(name)


def immediates(lst):
    """The TRKBUF names only ever used as IMMEDIATES (`mov di, tw_rects_b`),
    which os88rate.symbols() cannot see - it scrapes [name] operands."""
    out = {}
    pats = [(r"BF\[([0-9A-F]{2})([0-9A-F]{2})\]\s+(?:<\d+>)?\s*mov di, (tw_rects_b|tw_flags_b)\s*$", 3),
            (r"81C7\[([0-9A-F]{2})([0-9A-F]{2})\]\s+(?:<\d+>)?\s*add di, (tw_keys)\b", 3)]
    for L in open(lst):
        for pat, g in pats:
            mo = re.search(pat, L)
            if mo:
                out.setdefault(mo.group(g), int(mo.group(2) + mo.group(1), 16))
    return out


def main():
    # A PRIVATE listing: os88rate's default is one fixed /tmp path, and two
    # instances started together read each other's - every bss read then
    # lands on the wrong word and reads as "XT mode is not armed".
    fd, os88rate.LST = tempfile.mkstemp(suffix=".lst", prefix="trklcd")
    os.close(fd)
    try:
        P, _ = symbols(())
        imm = immediates(os88rate.LST)
    finally:
        os.unlink(os88rate.LST)
    for n in ("tw_rects_b", "tw_flags_b", "tw_keys"):
        if n not in imm:
            print("FAIL: no address for %s in the listing" % n)
            return 1
    S = os88sym.linear
    need(DISK)                     # `all` builds nothing under tests/
    with os88marty.launch("build/os8088-360.img", apps=DISK,
                          machine=MACHINE, boot=False) as m:
        m.run()
        os88marty.settle(m, gate=os88marty.desktop_up)
        os88marty.no_saver(m)
        mo = os88mouse.Mouse(marty=m)
        dispcp.open_drive(m, mo, S, os88marty.settle, "B")
        slot = dispcp.win_list(m, S)[-1]
        wx, wy, _, _ = dispcp.win_rect(m, S, slot)
        dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "BEVERLY.MOD")
        seg = None
        for _ in range(60):
            time.sleep(2)
            seg, _drv = scan(m)
            if seg:
                break
        if not seg:
            print("FAIL: Tracker never loaded")
            return 1
        base = seg * 16
        b = lambda n: m.read(base + P["@" + n], 1)[0]
        wv = lambda a: int.from_bytes(m.read(base + a, 2), "little")

        def guest(secs):               # GUEST time: a loaded host cannot
            m.advance(cycles=int(secs * HZ))   # shorten it
            m.run()

        for _ in range(60):            # 116KB of module off a 360KB floppy
            if b("mp_loaded"):
                break
            guest(1.0)
        flags = lambda: wv(imm["tw_flags_b"] + VIZ * 2)

        def click():
            a = imm["tw_rects_b"] + VIZ * 8
            x1, y1, x2, y2 = [wv(a + i) for i in (0, 2, 4, 6)]
            mo.click((x1 + x2) // 2, (y1 + y2) // 2)
            guest(1.0)

        def rate(off, secs=6.0):
            m.bp_exec(base + off)
            n, c0 = 0, m.status()["cycles"]
            while True:
                m.run()
                if m.wait_stop(10.0) is None:
                    break
                if m.status()["cycles"] - c0 > secs * HZ:
                    break
                n += 1
            span = (m.status()["cycles"] - c0) / HZ
            m.bp_exec()
            m.run()
            return n / span

        print("the button (SPEC.md 45.23.1)")
        check("XT mode armed (mp_xt)", b("mp_xt"), 1)
        check("5.5 kHz (trk_xhi)", b("trk_xhi"), 0)
        m.key("Enter")
        guest(8.0)
        check("drawn: the thin XT meter (tw_vizm)", b("tw_vizm"), 4)
        check("the button is live", flags() & 1, 0)
        click()
        check("click: Off picked and drawn", (b("tw_viz"), b("tw_vizm")), (3, 3))
        check("...and the button still live", flags() & 1, 0)
        click()
        check("click: VU Meter again", (b("tw_viz"), b("tw_vizm")), (0, 4))
        m.key("KeyR")
        guest(2.0)
        check("R: 11 kHz, and nothing drawn", (b("trk_xhi"), b("tw_vizm")), (1, 3))
        check("...and the button GREYED", flags() & 1, 1)
        click()
        check("a click on it changes nothing", b("tw_viz"), 0)
        m.key("KeyR")
        guest(2.0)
        check("R back: 5.5 kHz, the meter, live",
              (b("trk_xhi"), b("tw_vizm"), flags() & 1), (0, 4, 0))
        if not b("mp_playing"):
            m.key("Enter")             # R stops the stream to reopen it
            guest(6.0)

        print("the LCD (SPEC.md 45.21.8)")
        ups = rate(P["tw_update"])
        comps = rate(P["tw_lcd_line"])
        print("  frames %.1f/s, LCD compositions %.2f/s" % (ups, comps))
        check("compositions at most ~2 a second", comps <= 2.5, True)
        check("...while frames run at over 10 a second", ups > 10.0, True)
        guest(20.0)                    # the clock and the position move

        ox, oy = wv(P["@tw_ox"]), wv(P["@tw_oy"])
        rows = list(range(oy + 4, oy + 50)) + list(range(oy + 172, oy + 180))

        def grab():
            _w, _h, px = m.vram("herc")
            return [bytes(px[y][ox + 4:ox + 412]) for y in rows]

        keys = lambda: m.read(base + imm["tw_keys"], 80)
        for attempt in range(8):
            m.pause()
            a, k1 = grab(), keys()
            m.write(base + P["@tw_dirty"], bytes([b("tw_dirty") | 1]))
            for _ in range(100):
                m.advance(cycles=int(0.02 * HZ))
                if b("tw_dirty") & 1 == 0:
                    break
            for _ in range(200):       # the frame that took it has FINISHED
                if b("tw_inframe") == 0:
                    break
                m.advance(cycles=int(0.02 * HZ))
            took = b("tw_dirty") & 1 == 0 and b("tw_inframe") == 0
            c, k2 = grab(), keys()
            m.run()
            if not took:
                check("the forced full repaint ran to the end", took, True)
                break
            if k1 != k2:
                print("  (a line's inputs moved on attempt %d - again)" % attempt)
                guest(0.7)
                continue
            lit = sum(sum(r) for r in a)
            ndiff = sum(sum(1 for p, q in zip(ra, rc) if p != q)
                        for ra, rc in zip(a, c))
            check("the LCD has text on it (%d px lit)" % lit, lit > 1000, True)
            check("diff-drawn LCD + status == a full repaint (px)", ndiff, 0)
            break
        else:
            check("found a moment with no line's inputs moving", False, True)

    print("trklcd: %s" % ("pass" if not fails else "%d FAILED" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
