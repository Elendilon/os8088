#!/usr/bin/env python3
"""vidrmbsnd - the SOUND side of a REAL-MODE BRACKET (SPEC.md 53.2.3,
docs/plans/MEGA-VIDEO-REALMODE-PLAN.md W4).

    make mega megarun && python3 tests/vidrmbsnd.py [--keep]

The Video Player's real-mode bracket (W5) plays its sound through
OSAPI_SND_STREAM with the card as the clock, and Live's F carries a stream
that is already playing INTO the bracket and back out. W4 carries SOUND.DRV
below 1MB for it (FSXL_DRV DRVC_SOUND): its image copied down at the drop
and up at the return with IF = 0, its segment words renamed both ways off
the list SNDV_RMODE hands the kernel, the IVT cells naming it pointed at
the copy, DSV_TICK run by the real-mode tick, and the speaker door's twin
writing IVT 20h. tests/megarmb/megarmbs.asm's MEGARMBS drives every one of
those on Bochs's Sound Blaster 16 (220h, IRQ 5, DMA 1), with SOUND.DRV
mounted at boot and a 32 KB direct external ring at 8,000 Hz. Its legs (a
record each in its bss), and what is asserted:

  Z  THE CONTROL: protected mode alone, before any bracket, 2 s
  P  a real-mode bracket OPENS the stream and plays 2 s - the twin to the
     low copy, the block IRQ to the low copy's ISR - and returns with it
     still PLAYING
  Q  protected mode plays it 2 s: the words a stream opened in real mode
     stored (paragraphs) were renamed to the claim's selector at the return
  L  real mode again, 2 s - CARRIED IN: the selectors made paragraphs
  M  protected mode, 2 s
  K  real mode, 1 s, and CLOSED inside
  O  LIVE: protected mode opens a stream and plays 2 s
  I  ...carried into a real-mode bracket, 2 s
  J  ...back in protected mode 2 s, and closed there
     - each of those eight: the bracket real (SI 0, no CPU_F_PM inside),
     the stream PLAYING at the end, and the bytes the card reported a tick
     within a block and 10% of the control's - the card's clock, through
     every switch
  W  real mode: a stream opened, 0.5 s, then IRQ 3, 5 and 7 masked - only
     SOUND.DRV's DSV_TICK, which the real-mode tick runs through the low
     copy, can notice the block IRQs stopped: verb 3 must answer ENDED
  S  a real-mode FSXF_RATE bracket with NO list: OSAPI_SND_STREAM answers
     AX = 4 (no sink), FSX_SPK AL = 0 refuses AX = 1, AL = 2 opens with the
     package's real-mode sample ISR at N = 100 and answers K = 40 and the
     chain KERNEL_SEG:fsx_rtick; the ISR's samples are K a period, every
     hook call is at IF = 1, [ticks] runs on, and after the close IVT 20h
     is fsx_rtick again
  and after: no bracket up, [fsx_rwhy] FFh, the service area given back
  ([fsx_rsvc] 0), the table byte for byte, no kern_mega FAULT - and the
  card's capture (OUT/sb.wav) the ring's sawtooth with no gap or repeat
  between its first and its last ramp: the DMA never stopped across ten
  switches.

THE FAILING CASES (docs/WRITING-TESTS.md 1) are in MEGA-VIDEO-REALMODE-PLAN's
W4 entry, each a one-line break of the kernel that takes this row red.
"""
import argparse
import os
import shutil
import struct
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, "tools"), HERE]

NAME = "MEGARMBS"
PKG = os.path.join(ROOT, "build", "megarmbs.o88")
BIN = os.path.join(ROOT, "build", "megarmbs.bin")
KSEG = 0x0060
TBL, TLEN = 0x0010, 0x04D9
LEGS = "PQLMKOIJWSZ"
LEG_SZ = 32
RATE = 8000
TICK_HZ = 1193182 / 65536
PM = 0x10
FAILS = []


def want(cond, what):
    print("   %s  %s" % ("ok  " if cond else "FAIL", what), flush=True)
    if not cond:
        FAILS.append(what)


def u16(b, i=0):
    return b[i] | b[i + 1] << 8


def u32(b, i=0):
    return u16(b, i) | u16(b, i + 2) << 16


def resoff():
    with open(BIN, "rb") as f:
        return u16(f.read(12), 8)


def parse(res):
    out = {"fin": res[0], "per": u32(res, 4), "hn": u16(res, 8),
           "hif": u16(res, 10)}
    for k, c in enumerate(LEGS):
        r = res[16 + k * LEG_SZ:16 + (k + 1) * LEG_SZ]
        out[c] = dict(cf=r[0], why=r[1], feat=r[2], ran=r[3], err=u16(r, 4),
                      st=u16(r, 6), t=u16(r, 8), c=u32(r, 10),
                      x=[u16(r, 14 + 2 * i) for i in range(8)])
    return out


def judge(r, rtick):
    def real(c):
        d = r[c]
        want(d["cf"] == 0 and d["why"] == 0 and d["ran"] == 1
             and not d["feat"] & PM,
             "%s: a REAL-MODE bracket (CF %d, SI %d, ran %d, feat %02x)"
             % (c, d["cf"], d["why"], d["ran"], d["feat"]))

    z = r["Z"]
    zr = z["c"] / z["t"] if z["t"] else 0

    def play(c, what, inside):
        d = r[c]
        if inside:
            real(c)
        else:
            want(d["ran"] == 1, "%s: ran" % c)
        want(d["err"] == 0, "%s: no stream verb refused (%04x)" % (c, d["err"]))
        want(d["st"] == 0, "%s: the stream PLAYING at the end (state %04x)"
             % (c, d["st"]))
        # THE CARD'S CLOCK, against the control's: Bochs's SB16 runs its DMA
        # on a timer of its own (OS88_BOCHS_DMATIMER), so bytes a TICK is
        # the emulator's figure and not 8,000 / 18.2 - the same in every
        # leg is the claim, a block (2,048) either way
        got = d["c"] / d["t"] if d["t"] else 0
        if c == "Z":
            want(z["c"] > 0, "Z %s: the card consumed %d bytes in %d ticks "
                 "(%.0f a tick; %d Hz would be %.0f)" % (what, z["c"], z["t"],
                                                       zr, RATE,
                                                       RATE / TICK_HZ))
            return
        tol = 2048 / d["t"] + 0.1 * zr
        want(d["t"] > 0 and zr and abs(got - zr) <= tol,
             "%s %s: %d bytes in %d ticks, %.0f a tick against the "
             "control's %.0f" % (c, what, d["c"], d["t"], got, zr))
    print("\n   the stream")
    play("Z", "in protected mode before any bracket (the control)", False)
    play("P", "opened in real mode", True)
    play("Q", "carried OUT to protected mode", False)
    play("L", "carried back IN", True)
    play("M", "out again", False)
    play("K", "in again, and closed there", True)
    play("O", "opened in protected mode (Live)", False)
    play("I", "carried IN", True)
    play("J", "out, and closed there", False)
    print("\n   the watchdog")
    w = r["W"]
    real("W")
    want(w["st"] == 0, "W: PLAYING before the lines were masked (%04x)"
         % w["st"])
    want(0 < w["x"][0] < 90, "W: ENDED by the watchdog %d ticks after the "
         "block IRQs stopped - DSV_TICK ran in real mode" % w["x"][0])
    print("\n   the speaker")
    s = r["S"]
    real("S")
    want(s["x"][0] == 0x8004, "S: OSAPI_SND_STREAM with no sink carried: "
         "CF, AX = 4 (%04x)" % s["x"][0])
    want(s["x"][1] == 0x8001, "S: FSX_SPK AL = 0 refused, AX = 1 (%04x)"
         % s["x"][1])
    want(s["err"] == 0, "S: FSX_SPK AL = 2 opened (%04x)" % s["err"])
    k = s["x"][2]
    want(k == 4096 // 100, "S: K = %d samples a period (%d)"
         % (4096 // 100, k))
    want((s["x"][3], s["x"][4]) == (rtick, KSEG),
         "S: the chain is KERNEL_SEG:fsx_rtick (%04x:%04x)"
         % (s["x"][4], s["x"][3]))
    want((s["x"][5], s["x"][6]) == (rtick, KSEG),
         "S: IVT 20h after the close is fsx_rtick again (%04x:%04x)"
         % (s["x"][6], s["x"][5]))
    per = r["per"]
    want(s["t"] >= 30 and per >= s["t"] * 65536 // 4000 * 0.8,
         "S: %d ticks ran on, %d rate periods for the hook" % (s["t"], per))
    want(k and abs(s["c"] - k * per) <= 2 * k,
         "S: the sample ISR took %d entries, K x the periods (%d)"
         % (s["c"], k * per))
    want(r["hn"] > 0 and r["hif"] == r["hn"],
         "S: every hook call at IF = 1 under the sample ISR (%d of %d)"
         % (r["hif"], r["hn"]))


def wav(path):
    """(rate, bits, channels, mono 8-bit-ish samples) of the capture"""
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        return None
    raw = open(path, "rb").read()
    if raw[0:4] != b"RIFF" or raw[8:12] != b"WAVE":
        return None
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(raw):
        cid, sz = raw[pos:pos + 4], struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            fmt = raw[pos + 8:pos + 24]
        elif cid == b"data":
            data = raw[pos + 8:]
            break
        pos += 8 + ((sz + 1) & ~1)
    if fmt is None or data is None:
        return None
    _, ch, rate, _, _, bits = struct.unpack("<HHIIHH", fmt)
    return rate, bits, ch, data


def capture(path):
    """the capture: the ring's sawtooth (period 256 samples at 8,000 Hz) as
    Bochs resampled it - every falling edge one period after the last, from
    the first leg's to the last close's. Bochs writes samples only while the
    DMA moves, so a stall is no gap in the file; what a wrong segment, a
    stray halt or a ring re-armed elsewhere would leave is a PHASE break"""
    w = wav(path)
    if w is None:
        want(False, "the card's capture (sb.wav) is there")
        return
    rate, bits, ch, data = w
    sw = bits // 8
    n = len(data) // (sw * ch)
    if sw == 1:
        x = [(data[i * ch] - 128) << 8 for i in range(n)]
    else:
        x = [struct.unpack_from("<h", data, i * ch * 2)[0] for i in range(n)]
    print("   sb.wav: %d Hz, %d-bit, %d channel(s), %.1f s" % (rate, bits, ch,
                                                             n / rate))
    peak = max(abs(v) for v in x) if x else 0
    edges, hi = [], False
    for i, v in enumerate(x):
        if v > peak * 0.4:
            hi = True
        elif v < -peak * 0.4 and hi:
            edges.append(i)
            hi = False
    per = rate * 256 / RATE
    # THE CONTROL'S FIRST BLOCK is skipped: Bochs's first DMA block of the
    # session, in protected mode before any bracket, carries one phase step
    # (measured: 1,670 samples where 1,411 are due, at 0.1 s) - the
    # emulator's start, not a switch's
    first = rate * 2048 // RATE
    edges = [e for e in edges if e > first]
    br = sum(1 for a, b in zip(edges, edges[1:]) if abs(b - a - per) > 3)
    secs = (edges[-1] - edges[0]) / rate if len(edges) > 1 else 0
    print("   sb.wav: %d falling edges over %.1f s, %d off the %.1f-sample "
          "period" % (len(edges), secs, br, per))
    want(peak > 1000 and secs > 15 and br == 0,
         "the capture is ONE unbroken sawtooth from the first leg to the "
         "last close (%.1f s, %d phase breaks)" % (secs, br))


def bochs(a):
    import os88bochs
    import os88sym
    from os88fixture import need
    for p in (PKG, BIN, os.path.join(ROOT, "build", "megarun.o88"),
              os.path.join(ROOT, "build", "mega.img")):
        need(os.path.relpath(p, ROOT))
    out = tempfile.mkdtemp(prefix="vidrmbsnd-")
    t0 = time.time()
    os88bochs.MEGS = 4
    box = os88bochs.Box(out, [PKG], sb=True, cfg=1)
    off, sect, equ = os88sym._parse_map(os.path.join(ROOT, "build", "megak",
                                                     "kernel.map"))
    rtick = off["fsx_rtick"]
    roff = resoff()
    lines, res, after = [], None, None
    try:
        if not box.wait_for("kern_mega:", 240):
            raise RuntimeError("no kern_mega line in 240s")
        box.up()
        tbl0, = box.reads([(KSEG * 16 + TBL, TLEN)])
        box.megarun()
        end = time.time() + 400
        while time.time() < end:
            ls = box.lines()
            if any(l.startswith(NAME + ": done") for l in ls) or box.fault():
                break
            time.sleep(0.5)
        else:
            want(False, "%s finished its legs in 400s" % NAME)
        box.guest_sleep(1)
        lines = box.lines()
        if not box.fault():
            base = box.pkg_base(NAME)
            res = box.read(base + roff, 16 + len(LEGS) * LEG_SZ)
            box.ui_done("the desktop after the brackets", lock=False)
            after = box.reads([(KSEG * 16 + TBL, TLEN), ("fsx_rwhy", 1),
                               ("fsx_rmode", 1), ("fsx_task", 1),
                               ("fsx_rsvc", 2)])
    finally:
        box.stop()
    print("vidrmbsnd: %.0fs under Bochs" % (time.time() - t0))
    for l in lines:
        if l.startswith((NAME, "kern_mega FAULT", "kern_mega CLOSED")):
            print("   | " + l)
        if l.startswith(("kern_mega FAULT", "kern_mega CLOSED")):
            FAILS.append(l)
    if res is None:
        want(False, "%s's result block read" % NAME)
    else:
        r = parse(res)
        want(r["fin"] == 1, "%s ran every leg" % NAME)
        judge(r, rtick)
    if after:
        t1, why, rm, ft, svc = after
        print("\n   after")
        want(t1 == tbl0, "the table is byte for byte what it was")
        want(why[0] == 0xFF and rm[0] == 0 and ft[0] == 0xFF,
             "[fsx_rwhy] at rest (%02x), [fsx_rmode] 0, no bracket up (%02x)"
             % (why[0], ft[0]))
        want(u16(svc) == 0, "the service area's claim is given back "
             "([fsx_rsvc] %04x)" % u16(svc))
    print("\n   the card's capture")
    capture(os.path.join(out, "sb.wav"))
    if a.keep or FAILS:
        print("vidrmbsnd: the boot is in " + out)
    else:
        shutil.rmtree(out, ignore_errors=True)
    print("vidrmbsnd: %s" % ("FAIL - %d" % len(FAILS) if FAILS else "ok"))
    return 1 if FAILS else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    return bochs(a)


if __name__ == "__main__":
    sys.exit(main())
