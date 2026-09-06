#!/usr/bin/env python3
"""docs/plans/CASSETTE-PLAN.md wave 6 - the two detection gates (SPEC.md 88.1).

TAPE is a 5150-only feature and this is the row that proves the machine knows
it. **It is an A/B and it has to be**: a detector that answered "no cassette"
unconditionally would pass every negative test ever written, so the positive
arm - a machine where the offer is LIVE - is the half that makes the other
half mean anything.

    os8088_5150_cga_gla   model byte FF, ROM refuses AH=01  ->  TP_HW_BIOS
    os8088_xt_vga         model byte FE, a 5160            ->  TP_HW_MODEL

**THE TWO ARMS REFUSE FOR DIFFERENT REASONS, AND THAT IS THE ASSERTION.** One
verdict on both machines would mean a detector that answers the same thing
everywhere, which is exactly the failure a one-machine row cannot see. Here
gate 1 fires on the XT and gate 2 fires on the 5150, so both are shown working
and shown to be independent.

**AND THE 5150 ARM IS WHY GATE 2 EXISTS AT ALL.** GLaBIOS sets `CASSETTE = 1`
for `ARCH_TYPE EQ ARCH_5150`, and then the block headed *"Additional
Configuration for MartyPC emulator"* overrides it with `CASSETTE = 0 ; use all
features on 5150` - the cassette routines are traded for code space. So the
only 5150 this project can boot carries a 5150 BADGE and no cassette
whatsoever. On the model byte alone the feature would have offered itself,
the user would have pressed Go, and `int 15h AH=03` would have gone somewhere
undefined. `int 15h AH=01` - motor OFF, the one cassette call that moves no
tape, cannot hang and needs no deck - is what catches it.

**WHAT THIS ROW CANNOT DO** (SPEC.md 88.11): it cannot reach TP_HW_OK at all,
let alone read or write a tape. There is no ROM in this tree with working
cassette routines, and MartyPC's PPI returns a hardwired zero for the data
line whenever the motor is on (`ppi.rs:856-864`, `// TODO: Implement cassette
data input`). The POSITIVE arm of detection, and the transport behind it, meet
a real machine for the first time on somebody's 5150.

HOW TO MAKE IT FAIL ON PURPOSE (docs/WRITING-TESTS.md 1): change `cmp al,
0xFF` in `tp_detect` to `cmp al, 0xFE` and the two arms swap; delete the
`int 15h` gate and the XT arm still passes but a cassette-less 5150 ROM would
be reported as working, which is the case this row cannot reach and 88.11 says
so; delete `mov byte [tp_hw], TP_HW_MODEL` at the top and a machine that
never reaches the compare reports whatever the byte last held.
"""

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)

import dispcp                                           # noqa: E402
import os88build                                        # noqa: E402
import os88marty                                        # noqa: E402
import os88mouse                                        # noqa: E402
import os88sym                                          # noqa: E402

BIN = "build/tape.bin"
APPS = "build/tapehw360.img"

TP_HW_OK, TP_HW_MODEL, TP_HW_BIOS = 0, 1, 2

# machine -> (what [tp_hw] must be, what [tp_model] must be, why)
ARMS = [
    ("os8088_5150_cga_gla", TP_HW_BIOS, 0xFF,
     "a 5150 BADGE ON A ROM WITH NO CASSETTE IN IT - gate 2's whole reason"),
    ("os8088_xt_vga", TP_HW_MODEL, 0xFE,
     "a 5160: IBM dropped the socket and the relay, and port C bit 4 carries "
     "a speaker monitor where the 5150 carries cassette data in - gate 1"),
]


def say(s):
    print(s, flush=True)


def symbols(names):
    """label -> offset in the REAL-arm image, out of a NASM listing.

    It refuses unless the re-assembly is byte-identical to the binary under
    test (tapesim.py's discipline, and os88sym's one layer out): a listing that
    describes a different binary makes every offset plausible and wrong.
    """
    want = set(names)
    with tempfile.TemporaryDirectory() as d:
        lst = os.path.join(d, "tape.lst")
        out = os.path.join(d, "tape.bin")
        r = subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                            "-I", "apps/tape/", "-l", lst, "-o", out,
                            "apps/tape/tape.asm"], capture_output=True)
        if r.returncode:
            sys.exit("taperefuse: the source no longer assembles:\n"
                     + r.stderr.decode("latin-1"))
        if open(out, "rb").read() != open(BIN, "rb").read():
            sys.exit("taperefuse: %s is not what apps/tape/tape.asm assembles "
                     "to - run `make tapehwtest` first" % BIN)
        text = open(lst, "r", errors="replace").read()
    syms = {}
    for line in text.splitlines():
        mm = re.match(r"^\s*\d+\s+([0-9A-F]{8})\s", line)
        if not mm:
            continue
        for hit in re.finditer(r"(?:^|\s)([A-Za-z_][\w]*):", line):
            n = hit.group(1)
            if n in want and n not in syms:
                syms[n] = int(mm.group(1), 16)
    missing = want - set(syms)
    if missing:
        sys.exit("taperefuse: no address for %s" % ", ".join(sorted(missing)))
    return syms


def leg(machine, want_hw, want_model, why, syms, fails):
    say("\n--- %s : %s ---" % (machine, why))

    def S(n):
        return os88sym.linear(n)

    settle = os88marty.settle
    with os88marty.launch("build/os8088-360.img", apps=APPS,
                          machine=machine) as m:
        settle(m, gate=os88marty.desktop_up)
        # The model byte first, straight out of the ROM - so a wrong verdict
        # can be blamed on the detector rather than on the machine.
        rom = m.readseg(0xF000, 0xFFFE, 1)[0]
        say("    ROM model byte F000:FFFE = %02X" % rom)
        if rom != want_model:
            fails.append("%s: the ROM reports %02X, not %02X - this machine is "
                         "not what the row thinks it is" % (machine, rom, want_model))
            return

        mo = os88mouse.Mouse(marty=m)
        dispcp.open_drive(m, mo, S, settle, "B")
        wins = dispcp.win_list(m, S)
        if not wins:
            fails.append("%s: no Disk window" % machine)
            return
        wx, wy = dispcp.win_rect(m, S, wins[-1])[:2]
        before = len(wins)
        dispcp.open_named(m, mo, S, settle, wx, wy, "TAPE.O88", expect=None)
        settle(m)
        wins2 = dispcp.win_list(m, S)
        if len(wins2) <= before:
            fails.append("%s: TAPE.O88 opened no window - the package refused "
                         "its own launch, which it must not do on either arm "
                         "(SPEC.md 88.1 says the REFUSAL is a panel)" % machine)
            return
        rec = m.read(S("wm_wins") + wins2[-1] * dispcp.WIN_SIZE, dispcp.WIN_SIZE)
        pseg = rec[22] | (rec[23] << 8)
        hw = m.readseg(pseg, syms["tp_hw"], 1)[0]
        model = m.readseg(pseg, syms["tp_model"], 1)[0]

    say("    [tp_hw] = %d   [tp_model] = %02X" % (hw, model))
    if hw != want_hw:
        fails.append("%s: [tp_hw] is %d, want %d" % (machine, hw, want_hw))
        say("    FAIL [tp_hw] %d, want %d" % (hw, want_hw))
    else:
        say("    ok   [tp_hw] %d" % hw)
    if model != want_model:
        fails.append("%s: [tp_model] is %02X, want %02X"
                     % (machine, model, want_model))
        say("    FAIL [tp_model] %02X, want %02X" % (model, want_model))
    else:
        say("    ok   [tp_model] %02X" % model)


def main():
    for p in (BIN, APPS):
        if not os.path.exists(p):
            sys.exit("taperefuse: %s is missing - `make tapehwtest` first" % p)
    os88build.plain().apply()
    syms = symbols(("tp_hw", "tp_model"))
    fails = []
    for machine, hw, model, why in ARMS:
        leg(machine, hw, model, why, syms, fails)

    # THE A/B IS THE ASSERTION. Two arms that agreed would mean the detector
    # answers the same thing everywhere, which is exactly the failure a
    # one-machine row cannot see.
    say("")
    for f in fails:
        say("  FAIL: " + f)
    say("taperefuse: %s" % ("FAILED" if fails else "ok"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
