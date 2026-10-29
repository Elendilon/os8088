#!/usr/bin/env python3
"""THE PICOMEM, IN 86BOX, RUNNING ITS OWN FIRMWARE (docs/plans/PICOMEM-EMU-PLAN.md).

    make pmboxtest && tools/picomem/build.sh && python3 tests/pmbox.py [--keep DIR]

vm/xt-picomem1 is a 640KB 8088 XT with an OAK VGA and a PicoMEM 1.x on IRQ 5
- tools/86box/patches/07-picomem.patch, a thin adapter around libpmhost, the
card's own firmware (Elendilon/ISA-PicoMEM pm1x-pr) compiled for the host. It
boots build/pmsys360.img (SOUND, ETHER and USBMOUSE wanted) with
build/pmboxb360.img in B: (PMDMA and SBTEST) through os88ui under $OS88_EMU=86box, with the card's command
log (OS88_PMHOST_LOG) and its DAC (OS88_PMWAV) captured. What must hold:

  1. THE CARD CAME UP AS ITS BIOS LEAVES IT: the log shows the BIOS's IRQ
     detection (30h) and DEV_Init (09h) before os8088 sent anything;
  2. SOUND.DRV ATTACHED ON IT, in SPEC.md 34.10's order: the DSP off first
     (78h 0, 34.10.2), the AdLib on (73h 1), an IRQ that is not the card's
     own 5 (77h), then 78h at 220h - every one answered 0;
  3. THE 1.x's VIRTUAL DMA WORKS END TO END: PMDMA's R runs a 64-byte
     single-cycle transfer per way of programming channel 1 (sb.inc's
     sequence; with reads between; PMINIT's order; the page first) and every
     one of the four comes back RIGHT - the card snooped the 8237 writes,
     asked the CPU through its IRQ multiplexer, and the PicoMEM BIOS's
     handler copied the 64 bytes from where they were programmed;
  4. THE CARD'S DAC PLAYED SBTEST'S TONE: SBTEST's click plays 2 s of a
     1 kHz square at 8,000 Hz through OSAPI_SND_STREAM, and the card's own
     output (49,716 Hz, its OPL's rate) carries it - a level that moves, and
     a period of 1 ms.

Broken on purpose, OS88_PMHOST_NOSNOOP=1 (the card stops hearing the PC's
8237 writes): MEASURED below in the plan's 6.3 - A to D still read right
(the BIOS's copy takes its source from the 8237 itself), but PMDMA's
auto-init stream never ends, so its window never closes, and FAILS.
"""
import argparse
import os
import re
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

FAILS = []


def check(cond, what):
    print(("  ok    " if cond else "  FAIL  ") + what)
    if not cond:
        FAILS.append(what)


def log_cmds(text):
    """[(cmd, arg, status, answer)] off the card's command log"""
    out, open_ = [], {}
    for line in text.splitlines():
        m = re.search(r"PicoMEM: cmd ([0-9A-F]{2})h arg ([0-9A-F]{4})h", line)
        if m:
            open_ = {"c": int(m.group(1), 16), "a": int(m.group(2), 16)}
            continue
        m = re.search(r"PicoMEM: cmd ([0-9A-F]{2})h done: status (\d+) answer ([0-9A-F]{4})h", line)
        if m and open_ and open_["c"] == int(m.group(1), 16):
            out.append((open_["c"], open_["a"], int(m.group(2)), int(m.group(3), 16)))
            open_ = {}
    return out


def wav_frames(path):
    """(rate, [(l, r)]) of a 16-bit stereo PCM WAV"""
    d = open(path, "rb").read()
    rate = struct.unpack_from("<I", d, 24)[0]
    n = struct.unpack_from("<I", d, 40)[0] // 4
    fr = struct.unpack_from("<%dh" % (2 * n), d, 44)
    return rate, list(zip(fr[0::2], fr[1::2]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", help="leave the capture and the log here")
    a = ap.parse_args()
    for f in ("build/pmsys360.img", "build/pmboxb360.img",
              "build/picomem/v1/libpmhost-v1.so"):
        if not os.path.exists(os.path.join(ROOT, f)):
            print("SKIP: %s is not built (make pmboxtest; tools/picomem/build.sh)" % f)
            return 0

    tmp = a.keep or tempfile.mkdtemp(prefix="pmbox-")
    os.makedirs(tmp, exist_ok=True)
    wav = os.path.join(tmp, "card.wav")
    os.environ.update(OS88_EMU="86box", OS88_86BOX_VM="xt-picomem1",
                      OS88_PMHOST_LOG="1", OS88_PMWAV=wav)
    import os88marty
    import os88ui
    from cycweb import pkg_syms, Pkg
    try:
        with os88ui.boot(os.path.join(ROOT, "build/pmsys360.img"),
                         apps=os.path.join(ROOT, "build/pmboxb360.img"),
                         machine="os8088_xt_vga", quick=True) as ui:
            m = ui.m
            logf = os.path.join(m.b.run, "86box.log")

            print("pmbox: the card's boot, and SOUND.DRV's attach")
            cmds = log_cmds(open(logf).read())
            names = [c for c, _, _, _ in cmds]
            check(0x30 in names and 0x09 in names and
                  names.index(0x30) < names.index(0x09),
                  "the BIOS detected the card's IRQ (30h) and ran DEV_Init (09h)")
            att = [x for x in cmds if x[0] in (0x73, 0x77, 0x78)]
            check(len(att) >= 4 and att[0][:2] == (0x78, 0) and
                  att[1][:2] == (0x73, 1) and att[2][0] == 0x77 and
                  att[3][:2] == (0x78, 0x220) and all(x[3] == 0 for x in att[:4]),
                  "SOUND.DRV: 78h 0, 73h 1, 77h, 78h 220h, all answered 0 (%s)"
                  % ["%02Xh %04Xh=%04Xh" % (c, g, r) for c, g, s, r in att])
            check(att[2][1] & 0xFF not in (5,) if len(att) > 2 else False,
                  "the SB's IRQ is not the card's own 5 (77h %04Xh)"
                  % (att[2][1] if len(att) > 2 else 0))

            print("pmbox: PMDMA's R - the 1.x's virtual DMA, four ways")
            syms, _ = pkg_syms("tests/pmdma/pmdma.asm", incs=("apps/", "tests/", "build/"))
            w = ui.path("B:/PMDMA.O88")
            m.key("KeyR")
            p = Pkg(m, os88marty.pkg_seg(m, w.i), syms)
            rd = lambda: list(m.read(p.addr("pd_res"), 4))
            # pd_run starts every variant at "no copy" (4) and reports each
            # as it lands; the R key's whole run is one callback
            try:
                os88marty.until(m, lambda _: 4 not in rd(), guest=30,
                                what="PMDMA's four variants to report")
            except os88marty.MartyError:
                pass
            res = rd()
            check(res == [0, 0, 0, 0], "every variant copied from the address "
                  "programmed (pd_res %s: 0 right, 1 page, 2 wrong, 4 none)" % res)
            # R runs on into G and E - E a 2KB AUTO-INIT stream - in the same
            # callback, so the window closes only once the stream has ended
            try:
                ui.close(w, limit=120.0)
                check(True, "PMDMA's whole run ended, its auto-init stream "
                      "included (the window closed)")
            except os88ui.UIError as e:
                check(False, "PMDMA's whole run ended, its auto-init stream "
                      "included: %s" % str(e).split(".")[0])

            print("pmbox: SBTEST's tone, through the card's DAC")
            w = ui.path("B:/SBTEST.O88")
            x, y, ww, hh = ui._rect(w.i)
            ui.mo.click(x + ww // 2, y + hh // 2, settle=0)
            os88marty.pace(m, 4.0)
    except (os88marty.MartyError, os88ui.UIError) as e:
        check(False, "the machine: %s" % str(e).split(". ")[0])

    if os.path.exists(wav) and os.path.getsize(wav) > 44:
        rate, fr = wav_frames(wav)
        left = [l for l, _ in fr]
        # the capture is the whole session - the BIOS's beep and PMDMA's
        # 64-byte transfers click too - so the tone is the LONGEST stretch of
        # 10 ms blocks with any level in them
        blk = rate // 100
        act = [max(left[i:i + blk]) - min(left[i:i + blk]) > 1000
               for i in range(0, len(left) - blk, blk)]
        runs, st = [], None
        for i, on in enumerate(act + [False]):
            if on and st is None:
                st = i
            elif not on and st is not None:
                runs.append((st, i))
                st = None
        a0, b0 = max(runs, key=lambda r: r[1] - r[0]) if runs else (0, 0)
        tone = left[a0 * blk:b0 * blk]
        secs = len(tone) / rate
        mean = sum(tone) / max(1, len(tone))
        ups = sum(1 for i in range(1, len(tone)) if tone[i - 1] <= mean < tone[i])
        hz = ups / secs if secs else 0
        pp = (max(tone) - min(tone)) if tone else 0
        check(1.8 < secs < 2.4, "the card's DAC played one stretch of %.2f s "
              "(SBTEST stages 2 s)" % secs)
        check(950 < hz < 1050 and pp > 2000, "...a %.0f Hz tone at %d peak to "
              "peak (SBTEST's 1 kHz square)" % (hz, pp))
    else:
        check(False, "the card's DAC was captured (%s)" % wav)

    if not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    if FAILS:
        print("pmbox: FAIL (%d)" % len(FAILS))
        return 1
    print("pmbox: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
