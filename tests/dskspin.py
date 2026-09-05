#!/usr/bin/env python3
"""SPEC.md 18.101: a WRITE is never issued into a spindle still spinning up.

    make && python3 tests/dskspin.py

docs/FIELD-NOTES.md 32.  The IBM ROM waits for floppy motor spin-up on a WRITE
and ONLY when that write is the call that started the motor (`test [0x3f], al
/ jnz` at ED62) - `MOTOR_STATUS` is a flag, not a clock - so a READ that starts
the motor licenses the very next write to skip the wait.  A write into a slow
platter clocks 250 kbps into an arc turning too slowly, the data field runs
long, and the write gate is still open over the NEXT sector's ID address mark.
`dsk_spinup` declines that optimisation: it takes the flag down so the ROM
performs its own documented wait.

**THIS ROW ASSERTS THE GUARD AND NEVER THE DAMAGE**, and it cannot do
otherwise: 86Box, QEMU and MartyPC all present a floppy as an array of sectors,
and MartyPC's platter model has no write gate to leave open, so a write into a
stopped spindle lands in the right slot on all three.  What is checkable is the
DECISION - SPEC.md 18.101.1's four-row table - and that is a property of this
kernel, visible byte by byte.

SO IT CALLS THE ROUTINE, rather than hunting for a workload that happens to
reach a cold spindle.  `tests/dskwstage.py`'s `Caller` is the harness (a near
`.cold` routine entered through `park`, on task 0's stack, with the scheduler
locked), and every row sets the BIOS's own `0040:003F` and the kernel's two
tracking words to a state the table names, calls `dsk_spinup`, and reads the
motor byte back.  A workload test would have had to win a race against the
ROM's 14-second motor-off timer to produce each row, and would have proved one
of them at a time; this proves all six, deterministically, in one boot.

BREAK IT ON PURPOSE (docs/WRITING-TESTS.md 1): invert `dsk_spinup`'s
`jae .out` and rows 4 and 5 go red; delete the `cmp byte [dsk_op], 0x03` and
row 2 goes red; drop the unit check and row 6 goes red.  Each row fails alone,
which is what makes the table worth having over one aggregate assertion.

`make NOSPINUP=1` builds the kernel this fixes and has no `dsk_spinup` at all,
so its arm is the symbol's ABSENCE - asserted here, because a row that silently
skipped it would pass on a kernel with the guard compiled out.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import os88marty                                            # noqa: E402
import os88sym                                              # noqa: E402
import dskwstage                                            # noqa: E402

MACHINE = os.environ.get("OS88_MACHINE", "os8088_5150_cga_gla")
IMAGE = os.environ.get("OS88_SYSIMG", "build/os8088-360.img")
APPS = os.environ.get("OS88_APPSIMG", "build/apps360.img")

MOTOR_STATUS = 0x0040 * 16 + 0x3F       # linear: the BIOS data area
NONE = 0xFF                             # dsk_mondrv's "no drive"
bad = []


def say(*a):
    print(*a)
    sys.stdout.flush()


class Bench(object):
    def __init__(self, m):
        self.m = m
        self.c = dskwstage.Caller(m)
        self.S = os88sym.linear
        self.bound = (m.read(self.S("dsk_dpt") + 10, 1)[0] * 9) // 4

    def byte(self, name, v):
        self.m.write(self.S(name), bytes((v,)))

    def word(self, name, v):
        self.m.write(self.S(name), bytes((v & 0xFF, (v >> 8) & 0xFF)))

    def rdword(self, name):
        return int.from_bytes(self.m.read(self.S(name), 2), "little")

    def row(self, label, unit, op, motor, mondrv, age, want_bit):
        """Set the state the table names, call dsk_spinup, read the flag."""
        ticks = self.rdword("ticks")
        self.m.write(MOTOR_STATUS, bytes((motor,)))
        self.byte("dsk_unit", unit)
        self.byte("dsk_op", op)
        self.byte("dsk_mondrv", mondrv)
        self.word("dsk_monat", (ticks - age) & 0xFFFF)
        self.c.call("dsk_spinup")
        got = self.m.read(MOTOR_STATUS, 1)[0]
        bit = (1 << unit) if unit < 4 else 0
        on = bool(got & bit) if bit else bool(got & 0x01)
        ok = (on == want_bit)
        say("  %-46s motor %02X -> %02X  bit %s  %s"
            % (label, motor, got, "SET" if on else "clear",
               "ok" if ok else "!! WANTED %s" % ("SET" if want_bit else "clear")))
        if not ok:
            bad.append(label)
        return got


def main():
    if "--nospinup" in sys.argv:
        # The knob arm: the guard is compiled out, so the SYMBOL is the claim.
        tree = subprocess.check_output(
            [sys.executable, "tools/os88build.py", "build", "NOSPINUP=1"]
        ).decode().split()[1].strip()
        try:
            os88sym.linear("dsk_spinup", ("NO_SPINUP",))
        except Exception:
            print("dskspin: NOSPINUP=1 has no dsk_spinup, as it must")
            return
        sys.exit("dskspin FAILED: NOSPINUP=1 still defines dsk_spinup, so the "
                 "knob does not build the kernel it claims to (%s)" % tree)

    say("== %s : SPEC.md 18.101.1's table, one call a row ==" % MACHINE)
    with os88marty.launch(IMAGE, apps=APPS, machine=MACHINE) as m:
        os88marty.no_saver(m)
        # dskwstage's own finding: `launch` settles a few hundred ms after the
        # last boot read with the motor still turning, and every row here sets
        # 0040:003F itself - so the machine is paused and taken over, and from
        # `park` on nothing but these calls executes.
        m.pause()
        b = Bench(m)
        say("  spin-up bound %d ticks (dsk_dpt+10 = %d eighths)"
            % (b.bound, m.read(os88sym.linear("dsk_dpt") + 10, 1)[0]))

        far = b.bound + 5
        b.row("1 motor STOPPED, write - the ROM waits by itself",
              0, 0x03, 0x00, NONE, 0, False)
        if b.m.read(os88sym.linear("dsk_mondrv"), 1)[0] != 0:
            bad.append("1 did not stamp dsk_mondrv")
        b.row("2 motor on, READ - a read never needed the spindle",
              0, 0x02, 0x01, 0, 0, True)
        b.row("3 motor on, write, spindle long up - nothing owed",
              0, 0x03, 0x01, 0, far, True)
        b.row("4 motor on, write, spindle NOT up - GUARD FIRES",
              0, 0x03, 0x01, 0, 0, False)
        b.row("5 motor on, write, a motor we never saw start",
              0, 0x03, 0x01, NONE, far, False)
        b.row("6 unit 0x80 (a hard disk) - no bit, untouched",
              0x80, 0x03, 0x01, 0, 0, True)

    if bad:
        sys.exit("dskspin FAILED: " + "; ".join(bad))
    print("\ndskspin: SPEC.md 18.101.1's six rows all hold")


if __name__ == "__main__":
    main()
