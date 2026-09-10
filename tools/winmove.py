#!/usr/bin/env python3
"""What does dragging a window BY ITS TITLE BAR cost the window itself?
(SPEC.md 11.96.12)

    python3 tools/winmove.py sol|disk [machine]

Not a card drag and not another window dragged off it: the window you are
holding, moved. This counts what draws.

It is what found SPEC.md 11.96.12 and what proves it. BEFORE the drag cache, a
move was a full W_PAINT for every window - the dragged one is FRONT, so
11.96.4 had already dropped its cache, and wm_su_ck compares the ABSOLUTE
content rect, which a move changes in all four numbers:

    disk    207 calls,  236.6 ms   (71 font_char - the listing re-lettered)
    sol   1,016 calls,  914.7 ms   (22 gfx_blit4 - every card back again)

...and after, on the same drag through `make DRAGCACHE=0` and through the
shipped build - 981 calls / 954.3 ms against 210 / 462.4, with Solitaire's own
cards going from 22 blits to ONE gfx_restore.

    DX=-64 DY=0 SHOT=/tmp/on.raw  python3 tools/winmove.py sol
    make DRAGCACHE=0
    OS88_DEFINES=NODRAGCACHE DX=-64 DY=0 SHOT=/tmp/off.raw \
        python3 tools/winmove.py sol       # ...then diff the two .raw files

DX MUST BE A MULTIPLE OF 8 to reach the fast path (11.96.12's byte phase), and
the window must not end up hanging off the screen - the default -64,0 is both.
SHOT= writes the whole screen for the pixel gate, and the DEAL IS SEEDED
before the drag because Solitaire deals from GET_TICKS and two runs otherwise
lay out different cards: the first attempt at that gate reported 782 differing
pixels that were two different games.

WHY THIS IS ITS OWN TOOL AND NOT AN os88span SCENARIO. os88span prices a SPAN
between two named symbols and its collector stops at the first gap; this
question is a COUNT of everything a burst issued, and a burst that is mostly
one primitive repeated is exactly what it is bad at. Two scenarios were
written there first and one of them silently returned three hits for an
operation that issued 207 - a harness that stops early reads as an operation
that did not happen, which is the failure this tree keeps paying for.
"""
import os
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import os88marty
from os88mouse import Mouse
import sucheck as su
import subcheck as sc

CLK = 4772727.0
QUIET = int(0.40 * CLK)

PRIMS = os.environ.get('SYMS', '').split(',') if os.environ.get('SYMS') else [
         'gfx_pixel', 'gfx_hline', 'gfx_vline', 'gfx_fill', 'gfx_frame',
         'gfx_fill_gray', 'gfx_xor_rect', 'gfx_xor_fill', 'gfx_blit4',
         'font_char', 'font_run', 'gfx_line', 'gfx_restore', 'gfx_save',
         'wm_su_try', 'wm_su_bank', 'wm_draw_win']


def burst(m, names, trigger, first=60.0, limit=4000):
    """Run `trigger` with `names` armed; collect until the guest goes quiet.

    THE COUNT IS THE MEASUREMENT here - 207 calls against 981 is the finding -
    so a hit counted twice is a wrong published number rather than an error.
    This was a hand-rolled pump and it had that: it resumed, then broke out of
    its poll on the first `"breakpoint"` it saw, which is the stop it had just
    resumed past whenever the resume had not landed by the next round trip.
    The duplicate carried the SAME cycle count, so the `> QUIET` gap test could
    not reject it either. `bp_trace` dedupes on the server's own stop sequence.

    Its budget ran down the same way os88span's did - `t0` taken once outside
    the loop, so 4,000 iterations shared one 300-second allowance - and this
    file's own docstring says what that looks like from outside.

    THE FIRST HIT NEEDED A SPECIAL CASE AND NO LONGER DOES. The trigger used to
    be sent before the collector was entered, so the guest was already stopped
    at the first symbol and a loop opening with `run` resumed past it - the one
    hit that always vanished, reading as "the new code never runs". The trigger
    is inside the block now, so the pump is watching before it is pulled.
    """
    with os88marty.bp_trace(m, *names, cap=limit) as tr:
        trigger()
        t0, seen = time.time(), 0
        while tr.n < limit:
            if tr.n != seen:
                seen = tr.n
            elif tr.hits:
                # QUIET IS GUEST CYCLES and stays guest cycles: the gap that
                # ends a burst is a property of the machine, not of how fast
                # the host got round this loop.
                if m.status()["cycles"] - tr.hits[-1]["cycles"] > QUIET:
                    break
            elif time.time() - t0 > first:
                break                       # nothing drew at all
            time.sleep(0.004)
    return [(h["name"], h["cycles"]) for h in tr.hits]


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'sol'
    machine = sys.argv[2] if len(sys.argv) > 2 else 'os8088_5150_herc_gla'
    ddx = int(os.environ.get('DX', '-64'))
    ddy = int(os.environ.get('DY', '40'))
    apps = 'soltest.img' if which == 'sol' else 'apps360.img'
    with os88marty.launch(os.path.join(ROOT, 'build/os8088-360.img'),
                          apps=os.path.join(ROOT, 'build', apps),
                          machine=machine) as m:
        mo = Mouse(marty=m)
        mo.dblclick(*su.zone(m, 1))
        time.sleep(4)
        win = [w for w in su.windows(m) if w.visible][0]
        if which == 'sol':
            mo.dblclick(*su.row(win, 0))
            time.sleep(25)
            win = su.named(m, 'SOL')
        elif which == 'frac':
            mo.dblclick(*su.row(win, 0))        # APPS/
            time.sleep(5)
            mo.dblclick(*su.row(win, 2))        # ...FRACTAL.O88
            time.sleep(30)
            win = su.named(m, 'FRAC')
        if which == 'sol':
            # THE DEAL IS RANDOM (tools/solcheck.py says so in capitals), so
            # two runs of one binary lay out different cards and a pixel diff
            # between builds says nothing. Seed the kernel's own [osapi_seed]
            # and press N: both builds then deal the same game.
            m.write(m.sym('osapi_seed'), struct.pack('<H', 0x2A17))
            sc.pclick(mo, win.x + win.w // 2, win.y + win.h - 30)
            os88marty.settle(m)
            m.write(m.sym('osapi_seed'), struct.pack('<H', 0x2A17))
            m.key('KeyN')
            time.sleep(3)
        os88marty.settle(m)
        win = [w for w in su.windows(m) if w.visible and w.i == win.i][0]
        print('dragging %r by its title bar' % (win,))

        p = sc.titlebar(m, win)
        mo.to(*p)
        time.sleep(0.4)
        mo._edge(True)
        mo.to(p[0] + ddx, p[1] + ddy, l=True)
        time.sleep(1.0)

        # The release is what starts the repaint, and it goes INSIDE the
        # block - the pump is armed and watching before the trigger is pulled.
        hits = burst(m, PRIMS, lambda: mo._pk(l=False))
        time.sleep(1.5)
        now = [w for w in su.windows(m) if w.i == win.i][0]
        print('moved (%d,%d) -> (%d,%d): dx=%d (dx&7=%d) dy=%d'
              % (win.x, win.y, now.x, now.y, now.x - win.x,
                 (now.x - win.x) & 7, now.y - win.y))

        if not hits:
            print('nothing drew at all')
        else:
            span = hits[-1][1] - hits[0][1]
            counts = {}
            for n, _ in hits:
                counts[n] = counts.get(n, 0) + 1
            print('\n%d calls over %.1f ms of guest time' %
                  (len(hits), 1000.0 * span / CLK))
            if os.environ.get('SYMS'):
                prev = None
                for n, c in hits:
                    print('     %-14s %s' % (n, '' if prev is None else
                          '%8.2f ms' % (1000.0 * (c - prev) / CLK)))
                    prev = c
            for k in sorted(counts, key=lambda k: -counts[k]):
                print('   %-14s %d' % (k, counts[k]))
        out = os.environ.get('SHOT')
        if out:
            os88marty.settle(m)
            mo.to(8, 30)                    # the arrow parked off both windows
            time.sleep(0.6)
            w, bpp, data = su.fb(m)
            # THE MENU BAR IS DROPPED, subcheck.shot's MASK_Y for its reason:
            # the clock is up there and two runs of an A/B are minutes apart,
            # so it differs whatever the code does. Measured, that was 32
            # pixels at x 696..709 - a plausible count in a plausible place,
            # which is exactly how a harness defect gets read as a regression.
            data = bytes(data)[18 * w * bpp:]
            with open(out, 'wb') as f:
                f.write(struct.pack('<2H', w, bpp) + data)
            print('screen -> %s (%dx%s, menu bar dropped)' % (out, w, bpp))
        m.quit()


if __name__ == '__main__':
    sys.exit(main() or 0)
