#!/usr/bin/env python3
"""docs/plans/CASSETTE-PLAN.md wave 4 - the gate on OSAPI_COMPRESS (SPEC.md 88.6).

The cell publishes an ENCODER beside `OSAPI_DECOMP` for the first time - the
SDK has carried a decompressor with nothing to match it since SPEC.md 20.13 -
and the thing worth proving is not that it compresses. It is that **the two
agree**: a stream this machine packs has to be one this machine expands, byte
for byte, because on a tape there is no second copy to fall back to.

RATIO IS NOT ASSERTED, deliberately. It is data-dependent, it is measured on
the host by `tools/os88tape.py`, and a row that asserted a percentage would go
red the day the parse improved. What is asserted is that the bytes come back.

The NOGAIN arm is not an edge case: it is the path the tape writer takes for
every `'CZ'` file and every packed `.o88` (SPEC.md 88.7), which on a disk full
of shipped packages is most files.

HOW TO MAKE IT FAIL ON PURPOSE (docs/WRITING-TESTS.md 1): change `mov bl,
LZ_LZB` in `cmz_raw` to `LZ_LZ4` and `rt`/`same` go red, because the decoder
is then told the wrong format; drop the `mov di, [cs:cmz_w] / dec di` pair and
`cmz_pack` gets a window mask of whatever DI held, which corrupts the stream;
return the tables to the heap before `cmz_pack` rather than after and the
round trip goes red under any heap pressure.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)

import dispcp                                           # noqa: E402
import os88build                                        # noqa: E402
import os88marty                                        # noqa: E402
import os88mouse                                        # noqa: E402
import os88sym                                          # noqa: E402

MACHINE = "os8088_5150_cga_gla"
TC_MAGIC = b"TC"
TC_LEN = 2048
NR = 0x3F
OSAPI_LZ_LZB = 1
OSAPI_CMP_NOGAIN = 1


def say(s):
    print(s, flush=True)


def u16(b, i):
    return b[i] | (b[i + 1] << 8)


def main():
    for p in ("build/tapecomp360.img", "build/tapecomp.bin"):
        if not os.path.exists(p):
            sys.exit("tapecomp: %s is missing - `make tapecomptest` first" % p)
    fails = []
    os88build.plain().apply()

    def S(n):
        return os88sym.linear(n)

    settle = os88marty.settle
    with os88marty.launch("build/os8088-360.img",
                          apps="build/tapecomp360.img",
                          machine=MACHINE) as m:
        settle(m, gate=os88marty.desktop_up)
        mo = os88mouse.Mouse(marty=m)
        dispcp.open_drive(m, mo, S, settle, "B")
        wins = dispcp.win_list(m, S)
        if not wins:
            sys.exit("tapecomp: no Disk window after double-clicking B:")
        wx, wy = dispcp.win_rect(m, S, wins[-1])[:2]
        dispcp.open_named(m, mo, S, settle, wx, wy, "TAPECOMP.O88", expect=None)
        # The encoder is CLONE.DRV, fetched off the SYSTEM disk in A: - so this
        # is a disk read and takes real guest time before the block is written.
        settle(m)
        lo = 0x0600 * 16
        raw = m.read(lo, 0xA0000 - lo)

    got = None
    for i in range(len(raw) - 12):
        if raw[i:i + 2] == TC_MAGIC and raw[i + 2] != NR:
            got = raw[i + 2:i + 12]
            break
    if got is None:
        sys.exit("tapecomp: no answered results block - the entry proc never ran")

    cf, packed, fmt, regs = got[0], u16(got, 1), got[3], got[4]
    dcf, same, ncf, nax = got[5], got[6], got[7], u16(got, 8)

    def check(name, cond, detail):
        if cond:
            say("    ok   %-10s %s" % (name, detail))
        else:
            say("    FAIL %-10s %s" % (name, detail))
            fails.append("%s: %s" % (name, detail))

    say("--- compressible: %d bytes of a 16-byte cycle ---" % TC_LEN)
    check("compress", cf == 0, "CF=%d" % cf)
    if cf == 0:
        check("smaller", 0 < packed < TC_LEN,
              "%d bytes from %d (%.1f%%)" % (packed, TC_LEN, 100.0 * packed / TC_LEN))
        check("format", fmt == OSAPI_LZ_LZB, "BL=%d (want LZB=1)" % fmt)
        check("registers", regs == 1, "CX/SI/DI/BP came back" if regs == 1
              else "a promised register was clobbered")
        check("decompress", dcf == 0, "CF=%d" % dcf)
        check("round trip", same == 1,
              "the %d bytes are identical" % TC_LEN if same == 1
              else "THE BYTES DIFFER - the encoder and decoder disagree")

    say("--- incompressible: %d bytes of an LCG ---" % TC_LEN)
    check("refused", ncf == 1, "CF=%d" % ncf)
    check("nogain", nax == OSAPI_CMP_NOGAIN,
          "AX=%d (want OSAPI_CMP_NOGAIN=1)" % nax)

    for f in fails:
        say("  FAIL: " + f)
    say("tapecomp: %s" % ("FAILED" if fails else "ok"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
