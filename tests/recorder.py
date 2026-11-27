#!/usr/bin/env python3
"""RECORDER, end to end on a Sound Blaster - SPEC.md 35.

    make && python3 tests/recorder.py [--o88 F --src F] [--break-sweep]

build/recorder.o88 goes onto a scratch 720KB floppy of its own (it ships on
no floppy, SPEC.md 35.1) and is opened from B: on MartyPC's Hercules 5150
with a Sound Blaster, where SOUND.DRV attaches at boot. Every step is
confirmed off the package's own variables, read through its window's W_SEG:

  1. THE BUTTONS FIRE. A click on DEMO, pressed and released over it, stages
     the sweep: [rc_len] = 8,000 and the status line says so. The press only
     ARMS (SPEC.md 13.7); the release is where the action is, and the release
     hit-tests the pointer against the button rects - so a release handler
     that lost the pointer's y to OSAPI_WM_CONTENT's DX never fires anything.
  2. THE SWEEP IS THE SWEEP, byte for byte. The demo is read back out of the
     grant by the speaker path (step 4), and all 8,000 samples must equal the
     model below: a 256-entry sine at 128 + round(88 sin), stepped by a phase
     accumulator whose increment is Bresenham-swept 400 -> 800 -> 400 Hz.
  3. PLAY ON THE CARD: Sound > Play opens the PCM_BG stream (PLAYING (SB)),
     and a repaint after it has run out retires it (PLAY DONE (SB)).
  4. PLAY ON THE SPEAKER: with PCM_BG taken out of the caps word the app
     queried at launch, Play takes the PCM_EXCL path - each 0.5 s chunk read
     back through verb 5 and handed to os88pcm_play. Every call's ES:SI/CX is
     read at its entry and must be the model's next 4,000 samples; the run
     ends PLAY DONE (SPEAKER); and the heap holds no claim of the package's
     but its region afterwards (the play buffer is a claim for the length of
     one play, SPEC.md 35.2).
  5. REC / STOP: the REC button opens the input stream (RECORDING...) into a ring of
     the package's own (SPEC.md 34.6.4), and with NOTHING clicked the
     window timer's pump moves [rc_len] - the take grows by itself; the
     STOP button, clicked on a paused guest stepped in guest time, closes it
     BEFORE the grant fills ('STOPPED', not the FULL path's message), and the
     ring's claim is gone (rc_rseg 0, the package's claims what they were).

Broken on purpose - `--break-sweep` flips one sample of the model, and step
2 FAILS; the base package (b13cfe60) FAILS step 1, its release handler
hit-testing (x, content top) after OSAPI_WM_CONTENT clobbered DX.
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88marty as M, os88ui, os88geom, heapmap     # noqa: E402
from cycweb import pkg_syms, Pkg, u16               # noqa: E402

MACHINE = "os8088_5150_herc_sb_720_gla"
IMG = "build/os8088-720.img"
SND_CAP_PCM_BG = 0x04
RC_IDLE, RC_REC, RC_PLAY = 0, 1, 2
RC_D_LEN = 8000


def sweep():
    """The demo take, as SPEC.md 35 describes it and not as the code does."""
    import math
    sine = [128 + int(math.floor(88 * math.sin(2 * math.pi * i / 256) + .5))
            for i in range(256)]
    out, ph, inc, err, step = [], 0, 3277, 0, 1
    for n in range(RC_D_LEN):
        if n == RC_D_LEN // 2:
            step = -step
        out.append(sine[ph >> 8])
        ph = (ph + inc) & 0xFFFF
        err += 6554 - 3277
        if err >= RC_D_LEN // 2:
            err -= RC_D_LEN // 2
            inc += step
    return bytes(out)


def fail(msg):
    print("FAIL " + msg, flush=True)
    sys.exit(1)


def build(tmp, o88):
    img = os.path.join(tmp, "rec720.img")
    dst = os.path.join(tmp, "RECORDER.O88")
    with open(o88, "rb") as f, open(dst, "wb") as g:
        g.write(f.read())
    subprocess.run([sys.executable, "tools/os88disk.py", "-o", img, "--size",
                    "720", dst], check=True, capture_output=True)
    return img


def every(hm):
    """Every claim: the conventional arena's, and on kern_mega the pool's
    above 1MB as well (tools/heapmap.py's pool), where a package's own
    claims usually are - empty on every other kernel"""
    return hm.claims + getattr(hm, "pool", [])


def stepped_click(m, mo, x, y, box):
    """Move the pointer into BOX = (x1, y1, x2, y2), aiming at (x, y), then
    press and release - all on a PAUSED guest handed only guest time, so the
    gesture's length is the machine's and not the host's. Leaves it paused.

    MartyPC: each serial packet is sent on the stopped guest and the machine
    advanced until the published pointer moves; the edges are os88mouse's
    stepped `_gedge`. Bochs: os88megabochs.paced_input, every xdotool chain
    sent stopped and the guest run EXACTLY `gap` after it (Bochs's serial
    mouse builds a packet only at its 100 ms poll, so its gap is longer)."""
    def inside():
        cx, cy, _ = mo.where()
        return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]
    m.pause()
    bochs = getattr(m, "bochs", False)
    if bochs:
        import os88bochs
        gap = 0.15 if os88bochs.MOUSE == "serial" else 0.04
    for _ in range(12):
        if inside():
            break
        cx, cy, _ = mo.where()
        dx = max(-100, min(100, x - cx))
        dy = max(-100, min(100, y - cy))
        if bochs:
            # two X pixels a guest pixel (os88megabochs._c_mouse)
            # STAY: left stopped where the exact run ended, or the guest
            # runs a host round trip between chains (0.3-0.5 guest s)
            if not m.paced_input([("mousemove_relative", "--", 2 * dx,
                                   2 * dy)], gap, stay=True):
                fail("5: no exact paced input here")
        else:
            m.mouse(dx, dy)
            for _ in range(60):                 # ~0.25 guest s a packet
                m.advance(cycles=20000)
                if mo.where()[:2] != (cx, cy):
                    break
    if not inside():
        fail("5: the pointer did not reach the button %r (at %r)"
             % (box, mo.where()[:2]))
    if bochs:
        # EACH EDGE PROVED, as _gedge proves it: the press, then the
        # release, each confirmed by the published mouse_btn before the
        # next goes, and an edge not taken is SENT AGAIN (a packet carries
        # the level, so a repeat is the same level - os88megabochs._c_mouse).
        # ...and the press HELD a whole guest tick, as os88mouse holds one
        # (HOLD_TICKS: a loop polling the level sees a press only if a poll
        # lands inside it) - 0.04 s of press lost REC's click 1 run in 8
        hold = max(gap, mo.HOLD_TICKS / 18.2065)
        for down in (True, False):
            for k in range(8):
                if not m.paced_input([("mousedown" if down else "mouseup",
                                       1)], hold if down else gap,
                                     stay=True):
                    fail("5: no exact paced input here")
                if bool(mo.where()[2] & 1) == down:
                    break
                sys.stderr.write("recorder: the %s was not taken in %.2f "
                                 "guest s; again\n"
                                 % ("press" if down else "release", gap))
            else:
                fail("5: the %s never reached the guest (mouse_btn %02x)"
                     % ("press" if down else "release", mo.where()[2]))
    else:
        mo._gedge(True)                 # tap()'s gesture: the press held
        m.advance(cycles=int(mo.HOLD_TICKS * M.GUEST_HZ / 18.2065))
        mo._gedge(False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--o88", default="build/recorder.o88")
    ap.add_argument("--src", default="apps/recorder/recorder.asm")
    ap.add_argument("--break-sweep", action="store_true")
    ap.add_argument("--demo-by-menu", action="store_true",
                    help="stage the demo through Sound > Demo instead of the "
                         "button: how the old package (whose buttons never "
                         "fired) is driven through steps 2-5 for an A/B")
    a = ap.parse_args()
    want = bytearray(sweep())
    if a.break_sweep:
        want[4321] ^= 1
    syms, _ = pkg_syms(a.src)
    tmp = tempfile.mkdtemp(prefix="rectest-", dir=os.path.join(ROOT, "build"))
    img = build(tmp, a.o88)
    with os88ui.boot(IMG, apps=img, machine=MACHINE, quick=True) as ui:
        m = ui.m
        ui.path("B:/RECORDER.O88")
        seg = None
        for w in os88geom.windows(m, ui.sym):
            if w.title == "Recorder":
                seg = u16(m.read(os88geom.winptr(m, w.i, ui.sym)
                                 + os88geom.W_SEG, 2))
                win = w
        if not seg:
            fail("no Recorder window")
        p = Pkg(m, seg, syms)

        def msg():
            return bytes(m.readseg(seg, p.rw("rc_msg"), 32)).split(b"\0")[0] \
                .decode("latin-1")

        def wait_msg(text, what, limit=20):
            M.until(m, lambda _: msg() == text, what, poll=.1, limit=limit)

        caps = p.rw("rc_caps")
        print("caps %04X, status %r" % (caps, msg()), flush=True)
        if not caps & SND_CAP_PCM_BG:
            fail("no PCM_BG at launch - SOUND.DRV did not attach the card")

        # --- 1. the buttons fire on the release -------------------------------
        # the window is up before its first W_PAINT has run, and the paint is
        # what stashes the origin and lays the button rects out
        M.until(m, lambda _: p.rw("rc_oy") and p.rw("rc_rects"),
                "the first paint", poll=.1, limit=20)
        ox, oy = p.rw("rc_ox"), p.rw("rc_oy")
        bx, by = ox + 166 + 26, oy + 100 + 8          # DEMO's centre
        if a.demo_by_menu:
            ui.menu_pick("Sound", "Demo")
        else:
            ui.mo.click(bx, by)
        try:
            M.until(m, lambda _: p.rw("rc_len") == RC_D_LEN, "DEMO staged",
                    poll=.1, limit=20)
        except M.MartyError:
            fail("1: a click on DEMO staged nothing (status %r, len %d)"
                 % (msg(), p.rw("rc_len")))
        wait_msg("DEMO STAGED - 400-800 HZ", "the demo's status")
        print("PASS 1: DEMO %s, %d bytes staged"
              % ("picked off the menu (no button tested)" if a.demo_by_menu
                 else "button fired on its release", p.rw("rc_len")),
              flush=True)

        # --- 3. play on the card ----------------------------------------------
        ui.menu_pick("Sound", "Play")
        # WAITED FOR, not read once: menu_pick returns when the menu is down,
        # and the Play command's state and status can land a poll later - a
        # single read here failed a soak with 'st 2, PLAYING (SB)', both
        # already right by the time the message was formatted
        try:
            M.until(m, lambda _: p.rb("rc_st") == RC_PLAY
                    and msg() == "PLAYING (SB)", "Play's stream",
                    poll=.05, guest=5.0)
        except M.MartyError:
            fail("3: Play did not open the stream (st %d, %r)"
                 % (p.rb("rc_st"), msg()))
        M.guest_sleep(m, 1.6)
        # the poll runs on a paint, a fired button or a menu command - and a
        # move is put back by the raise cache WITHOUT a paint (SPEC.md
        # 11.96). Taking the About card down is the one way to ask for a
        # poll that does nothing else: rc_abdismiss polls and redraws
        ui.menu_pick("Recorder", "About Recorder")
        M.until(m, lambda _: p.rb("rc_abon") == 1, "the About card",
                poll=.1, limit=10)
        ui.mo.click(ox + 100, oy + 30)
        M.until(m, lambda _: p.rb("rc_abon") == 0, "the card dismissed",
                poll=.1, limit=10)
        wait_msg("PLAY DONE (SB)", "the stream retired", limit=5)
        print("PASS 3: PCM_BG played and retired (About card up and down)",
              flush=True)

        # --- 4. play on the speaker, and 2. the sweep -------------------------
        p.ww("rc_caps", caps & ~SND_CAP_PCM_BG)
        pc = p.base + syms["os88pcm_play"]     # (a selector's base on
        # kern_mega, where c.sel below is the claim's selector: heapmap)
        got = bytearray()
        heap = {n: ui._S(n) for n in ("mem_base", "mem_top", "spl_live",
                                       "mem_tab")}
        mine = sorted((c.seg, c.para) for c in every(heapmap.Map(m, heap))
                      if c.own == seg)
        m.bp_exec(pc)
        # the pick itself returns into a callback that BLOCKS, so drive it by
        # hand: Sound > Play, and the stops arrive while the menu tracks
        try:
            ui.menu_pick("Sound", "Play", limit=4)
        except Exception:
            pass
        for k in range(2):
            m.wait_stop(limit=30)
            r = m.regs()
            if getattr(m, "lin", lambda s_, o_: (s_ << 4) + o_)(
                    r["cs"], r["ip"]) != pc:
                fail("4: stopped at %04X:%04X, not os88pcm_play"
                     % (r["cs"], r["ip"]))
            es, si, cx = r["es"], r["si"], r["cx"]
            held = [c for c in every(heapmap.Map(m, heap))
                    if c.own == seg and c.sel == es]
            if es == seg:
                print("note: chunk %d plays from the package's own segment"
                      % k, flush=True)
            elif not held or held[0].para * 16 < si + cx:
                fail("4: chunk %d plays from %04X:%04X, which is neither "
                     "the package nor a claim of its own that holds %d bytes"
                     % (k, es, si, cx))
            else:
                print("chunk %d: %d bytes at %04X:%04X, a %.1f KB claim of "
                      "the package's own" % (k, cx, es, si,
                                             held[0].para / 64.0), flush=True)
            got += bytes(m.readseg(es, si, cx))
            if k == 0:
                m.bp_exec(pc)
            else:
                m.breakpoints([])
            m.run()
        if len(got) != RC_D_LEN:
            fail("4: the speaker path played %d bytes, want %d"
                 % (len(got), RC_D_LEN))
        bad = [i for i in range(RC_D_LEN) if got[i] != want[i]]
        if bad:
            fail("2: %d of %d samples differ from the model, first at %d "
                 "(%d, want %d)" % (len(bad), RC_D_LEN, bad[0],
                                    got[bad[0]], want[bad[0]]))
        print("PASS 2: all %d samples are the 400-800-400 Hz sweep"
              % RC_D_LEN, flush=True)
        wait_msg("PLAY DONE (SPEAKER)", "the speaker play's end", limit=30)
        after = sorted((c.seg, c.para) for c in every(heapmap.Map(m, heap))
                       if c.own == seg)
        if after != mine:
            fail("4: the package's claims were %s before Play and %s after"
                 % (mine, after))
        print("PASS 4: PCM_EXCL played both chunks, claims %s unchanged"
              % mine, flush=True)
        p.ww("rc_caps", caps)

        # --- 5. rec / stop ----------------------------------------------------
        # THE REC BUTTON, CLICKED ON A PAUSED GUEST stepped in guest time
        # (stepped_click), and the Record command's state then waited for in
        # GUEST steps. It was Sound > Record off the menu, which returns at
        # the release with the guest running: everything this process did
        # after it was host time the guest spent recording - 0.4 s of a 2 s
        # grant on an idle box, before the Stop below had even started. The
        # menu's dispatch is Play's to test (steps 3 and 4); both reach the
        # same rc_cmd
        def rect(i):
            r = m.read(p.addr("rc_rects") + 8 * i, 8)
            x1, y1, x2, y2 = (u16(r[j:j + 2]) for j in range(0, 8, 2))
            return ((x1 + x2) // 2, (y1 + y2) // 2,
                    (x1 + 2, y1 + 2, x2 - 2, y2 - 2))
        stepped_click(m, ui.mo, *rect(0))           # rect 0: REC
        for _ in range(250):                    # 5 guest seconds at most
            if p.rb("rc_st") != RC_IDLE:
                break
            m.advance(cycles=int(0.02 * M.GUEST_HZ))
        if p.rb("rc_st") != RC_REC or msg() != "RECORDING...":
            fail("5: Record did not open the input (st %d, %r, a press "
                 "armed button %d)" % (p.rb("rc_st"), msg(), p.rw("rc_down")))
        if not p.rw("rc_rseg"):
            fail("5: recording with no ring claimed")
        # EXACTLY 0.5 guest seconds, run by the server, and the take's GROWTH
        # over them read paused at both ends: ~4,000 bytes, well inside the
        # smallest grant tier (RC_D_LEN). It was guest_sleep, which polls the
        # guest's clock every 20 ms of HOST time and reads after it - so a
        # host that preempted this process overshot by whatever the guest ran
        # meanwhile (8,192 bytes, 'the pump is not running'). And it was then
        # the TOTAL rc_len after the advance - which also counted every guest
        # moment between Record opening and the pause, the three reads above
        # taken on a running guest: host time again, 9,216 bytes on a loaded
        # box (mega-recorder, soak 20261127-002230) and a pass alone
        base = p.rw("rc_len")
        m.advance(cycles=int(0.5 * M.GUEST_HZ))
        grown = p.rw("rc_len") - base
        if not 1500 <= grown <= 6000 or p.rb("rc_st") != RC_REC:
            fail("5: 0.5 s of recording with nothing clicked took %d bytes, "
                 "state %d %r - the timer's pump is not running (cap %d)"
                 % (grown, p.rb("rc_st"), msg(), p.rw("rc_cap")))
        # STOP, PRESSED AND RELEASED ON THE GUEST'S CLOCK, the machine still
        # paused. It was Sound > Stop off the menu, a gesture of 1.6-2.0
        # GUEST seconds on both emulators, and the take's grant is 16,000
        # bytes - 2 s - so the take was FULL before the pick ever landed:
        # every run ended 'NOT RUNNING', the ring freed by rc_poll's FULL
        # path, and the check below passed with Stop doing nothing at all.
        # Stepped, the whole gesture is a few hundred guest ms and nothing
        # the host does can lengthen it
        stepped_click(m, ui.mo, *rect(1))           # rect 1: STOP
        for _ in range(100):                    # 2 guest seconds at most
            if p.rb("rc_st") == RC_IDLE:
                break
            m.advance(cycles=int(0.02 * M.GUEST_HZ))
        took, said = p.rw("rc_len"), msg()
        m.run()
        # ...AND IT WAS STOP THAT ENDED IT: rc_do_stop's own message, with
        # the take short of the grant - the FULL path says 'REC STOPPED
        # (FULL)', and a Stop that lands after it 'NOT RUNNING'
        if p.rb("rc_st") == RC_IDLE and (said != "STOPPED"
                                         or took >= p.rw("rc_cap")):
            fail("5: the take ended %r at %d of %d bytes - not by Stop"
                 % (said, took, p.rw("rc_cap")))
        if p.rb("rc_st") != RC_IDLE:
            fail("5: Stop left state %d (%r)" % (p.rb("rc_st"), msg()))
        after = sorted((c.seg, c.para) for c in every(heapmap.Map(m, heap))
                       if c.own == seg)
        if p.rw("rc_rseg") or after != mine:
            fail("5: the ring was not freed (rc_rseg %04x, claims %s against "
                 "%s)" % (p.rw("rc_rseg"), after, mine))
        print("PASS 5: Record opened the ring, the pump took %d bytes in .5 s "
              "unclicked, the STOP button closed it at %d of %d bytes and "
              "freed the ring (%r)" % (grown, took, p.rw("rc_cap"), msg()),
              flush=True)
    print("recorder: ok", flush=True)


if __name__ == "__main__":
    main()
