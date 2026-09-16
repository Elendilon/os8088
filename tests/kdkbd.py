#!/usr/bin/env python3
"""kern_dos keeps the BIOS key buffer off full (SPEC.md 96.50).

    python3 tests/kdkbd.py [SYSTEM.img]

The image argument is the OTHER ARM: build one with the guard gated off and
point this at it.

    python3 tools/os88build.py build NOKDKBD=1
    python3 tests/kdkbd.py build/trees/nokdkbd-<hash>/os8088-360.img

...and it reports `int 09h` back at F000:E987 with the tail still 003C - the
key dropped, which is the condition every beeping ROM is reacting to.

Reported off an 86Box 386: hold a direction key in Prince of Persia under the
whole-machine arm and the BIOS beeps, for longer than the typematic interval,
so the next repeat overflows DURING the beep and it never stops.  SPEC.md 9.8
is that failure and os8088's kernel already guards it; `kern_dos` did not,
because the handoff's step 6 has to unhook `kbm_isr` - it sits at a KERNEL_SEG
offset that is kern_dos's image one instruction later - and nothing was put
back in its place.

WHAT THIS ASSERTS, and it is SPEC.md 9.8's own verification method:

  1. `int 09h` under kern_dos is OURS, not the ROM's.  One line, and it is the
     whole answer to "which machine am I on": F000:xxxx is the ROM's handler.
  2. A key arriving on a FULL buffer is STORED, not dropped - the tail winds
     back one slot, 3Ch -> 3Ah, exactly as 9.8 records for the kernel's guard.

**THE BUFFER IS FORGED FROM INSIDE THE GUEST**, which is why the probe is a
DOS program and not four host-side pokes: a forge written from the host is
drained before the test key lands, because the guest is sitting in `int 16h`
and empties it between the write and the keystroke.  That was measured, and it
read as "both arms survived".

**AND THE BEEP IS NOT ASSERTED, because it cannot be reproduced here.**  The
probe samples port 61h's speaker line and proves its own instrument first by
sounding one deliberately - the control reads 65,536 of 65,536 - and then
reads ZERO across the window on BOTH arms and on BOTH ROMs this harness can
boot: GLaBIOS, and the genuine 27-Oct-82 IBM part.  Neither sounds its
buffer-full bell.  The beeping ROM is the reporter's 386 BIOS and MartyPC is
an 8088, so it is out of reach (docs/TESTING.md's list).

That is not a hole in the gate, because the beep is not the thing we control.
The OVERFLOW is: with the guard the buffer is never full when a key arrives,
so no BIOS - beeping or silent - reaches its overflow path at all.  A row that
asserted a beep would be asserting a property of somebody else's ROM.
"""
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosmap                                                  # noqa: E402
import os88marty                                               # noqa: E402
import os88mouse                                               # noqa: E402
import os88ui                                                  # noqa: E402
import kdhand as K                                             # noqa: E402

# **NEITHER ROM THIS HARNESS CAN BOOT BEEPS, AND THE ROW USES THE TWIN.**
# Measured, both arms, both ROMs: GLaBIOS and the genuine 27-Oct-82 IBM part
# (`501476 COPR. IBM`, run on `os8088_5150_cga` with `why_ibm=`) drop the key
# on a full buffer in SILENCE - the speaker line never moves. The beeping ROM
# is the reporter's 386 BIOS, and MartyPC is an 8088, so it cannot be hosted
# here at all (docs/TESTING.md's list). What that settles is which machine
# this row should use: it asserts the OVERFLOW, which behaves identically on
# both parts, so it takes the GLaBIOS twin like every other row and does not
# skip on a box that has no period ROM.

R_VEC = re.compile(r"KBHOLD int09=([0-9A-F]{4}):([0-9A-F]{4})")
R_CTL = re.compile(r"speaker CONTROL\s*=([0-9A-F]{8})")
R_SPK = re.compile(r"speaker-on samples\s*=([0-9A-F]{8})")
R_KB = re.compile(r"(forged FULL|after  watch)\s+head=([0-9A-F]{4}) "
                  r"tail=([0-9A-F]{4})")


def fail(msg):
    print("kdkbd: FAIL: %s" % msg)
    sys.exit(1)


def keyburst(m, stop):
    """Keys arriving THROUGHOUT the probe's window - the held key, in effect."""
    while not stop.is_set():
        try:
            m.key("KeyA")
        except Exception:
            return
        time.sleep(0.05)


def main():
    sysimg = sys.argv[1] if len(sys.argv) > 1 else K.SYS
    for p in (sysimg, K.COM):
        if not os.path.exists(p):
            fail("%s is missing - `make` builds the system disk and the gate "
                 "floppy carries KBHOLD.COM" % p)

    with os88ui.boot(sysimg, apps=K.COM, machine=K.MACH) as ui:
        m = ui.m
        if not ui.path("B:/KBHOLD.COM"):
            fail("double-clicking KBHOLD.COM opened no window")
        K.wait_text(m, "KBHOLD READY", secs=150, what="the windowed run")
        m.type_text("x")
        os88marty.settle(m)

        dm = dosmap.package()
        pseg = dosmap.instance(m)
        mo = os88mouse.Mouse(marty=m)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_erect"))
        os88marty.settle(m)
        x1, y1, x2, _ = dosmap.rect(m, pseg, dm, "dos_mrad")
        pitch = K.rec(m, pseg, dm, K.RD_PITCH)
        mo.click((x1 + x2) // 2, y1 + K.WHOLE * pitch + pitch // 2)
        os88marty.settle(m)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_trect"))
        os88marty.settle(m)
        mo.click(*dosmap.centre(m, pseg, dm, "dos_rrect"))
        os88marty.settle(m)
        base = pseg << 4
        if K.alert_up(m, base, dm):
            mo.click(*K.alert_button(m, base, dm, 1))       # Proceed

        stop = threading.Event()
        t = threading.Thread(target=keyburst, args=(m, stop), daemon=True)
        t.start()
        try:
            rs = K.wait_text(m, "KBHOLD READY", secs=250,
                             what="the run under kern_dos")
        finally:
            stop.set()
            t.join(timeout=3)

    text = "\n".join(rs)
    print("kdkbd: under kern_dos:")
    for r in rs:
        if "KBHOLD" in r or "speaker" in r or "head=" in r:
            print("      | %s" % r.rstrip())

    v = R_VEC.search(text)
    if not v:
        fail("the probe never printed its int 09h vector")
    seg, off = v.group(1), v.group(2)
    if seg == "F000":
        fail("int 09h under kern_dos is %s:%s - the ROM's own handler, which "
             "is what a real IBM DOS 3.30 leaves too (F000:E987, the same "
             "address to the byte). SPEC.md 96.50's guard is not installed, "
             "so a key arriving on a full buffer reaches the ROM's overflow "
             "path" % (seg, off))
    print("kdkbd: int 09h is %s:%s - ours, in front of the ROM" % (seg, off))

    ctl = R_CTL.search(text)
    if not ctl or int(ctl.group(1), 16) == 0:
        fail("the probe's speaker CONTROL read zero: port 61h bit 1 never "
             "reads back set on this machine, so the sampled figure below it "
             "would be zero whatever happened. The instrument is dead, not "
             "the defect fixed")

    kb = R_KB.findall(text)
    if len(kb) != 2:
        fail("read %d head/tail lines and wanted 2: %r" % (len(kb), kb))
    (_, h0, t0), (_, h1, t1) = kb
    if (h0, t0) != ("001E", "003C"):
        fail("the probe forged head=%s tail=%s and a FULL buffer is "
             "001E/003C - it did not set up the condition under test"
             % (h0, t0))
    if t1 == t0:
        fail("a key arrived on a full buffer and the tail is still %s: it was "
             "DROPPED by the ROM, which is the overflow SPEC.md 9.8's guard "
             "exists to prevent. With the guard the tail winds back one slot "
             "(3Ch -> 3Ah) and the key is stored where the previous newest "
             "sat" % t1)
    if (h1, t1) != ("001E", "003A"):
        fail("the tail moved %s -> %s and SPEC.md 9.8 winds it back exactly "
             "one slot, to 003A, with the head untouched at 001E (it is %s)"
             % (t0, t1, h1))
    print("kdkbd: a key on a full buffer wound the tail %s -> %s and was "
          "STORED" % (t0, t1))

    spk = R_SPK.search(text)
    print("kdkbd: speaker-on samples %s across the window - neither ROM this "
          "harness can boot sounds its buffer-full bell, and the OVERFLOW is "
          "what the guard removes (see the docstring)"
          % (spk.group(1) if spk else "?"))
    print("kdkbd: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
