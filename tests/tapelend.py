#!/usr/bin/env python3
"""docs/plans/CASSETTE-PLAN.md wave 3 - the gate on OSAPI_PIT_LEND (SPEC.md 88.5).

The cell amends SPEC.md 34.1, a rule written down so the argument would stop
recurring: *"PIT channel 0 is never written."* Every claim made for that
amendment is a behaviour nothing in the tree had exercised, so this row
exercises them - on TWO kernels, because the half of the contract that matters
most only happens on the second.

  * the STOCK kernel: the claim is granted, a second claim is refused with
    AH=3, the speaker is refused while it is held and works again after the
    release, ENTER without a claim is refused, LEAVE gives AX/BX/DX and the
    flags back, RELEASE is idempotent, and [ticks] still advances.
  * a QUANTUM=2 kernel: the claim is REFUSED with AH=1, because [sch_fast] has
    moved ch0's divisor and the restore could not then be a constant. That is
    the arm the refusal exists for, and it is why this row builds its second
    kernel into a PRIVATE TREE (`os88build.tree`) rather than over `build/` -
    CLAUDE.md's trap 1: a knob kernel left in `build/` makes every later row
    die saying "the map describes a DIFFERENT kernel".

**The positive controls are the point.** A cell that refused everything would
pass every negative case here, so the claim is TAKEN first and the tone is
checked working again AFTER the release.

HOW TO MAKE IT FAIL ON PURPOSE (docs/WRITING-TESTS.md 1): delete the
`cmp byte [sch_fast], 0 / jne .busy_fast` pair from `sch_pit_lend` and the
QUANTUM arm goes red; delete `cmp byte [sch_pitcl], 0 / jne .busy_held` and
`claim2` goes red; take the `pushf`/`popf` off the LEAVE arm and `leave` goes
red; take the guard off `spk_tone` and `tone1` goes red.
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
TL_MAGIC = b"TL"

# The results block, in the order tests/tapelend/tapelend.asm lays it down.
# The layout there IS this ABI.
FIELDS = ["entnc", "claim", "clah", "claim2", "cl2h", "tone1",
          "enter", "leave", "ticks", "rel1", "rel2", "tone2"]

NR = 0x3F           # '?' - the byte the package never reached

WANT_STOCK = {
    "entnc": 0xFF,      # ENTER with no claim is refused
    "claim": 0x00,      # ...and the claim itself is granted
    "claim2": 0xFF,     # a second claim refuses
    "cl2h": 3,          #   ...with AH = 3, "somebody already holds it"
    "tone1": 0xFF,      # the speaker is refused while the claim is held
    "enter": 0x00,      # ENTER is legal once the claim is held
    "leave": 1,         # LEAVE gave AX, BX, DX and the flags back
    "ticks": 1,         # ...and the clock still advances
    "rel1": 0x00,
    "rel2": 0x00,       # RELEASE is idempotent
    "tone2": 0x00,      # ...and the speaker is the sound layer's again
}
WANT_QUANTUM = {
    "entnc": 0xFF,      # still refused - no claim can be held here at all
    "claim": 0xFF,      # THE POINT OF THIS ARM
    "clah": 1,          #   ...with AH = 1, "the kernel has re-rated ch0"
    # Everything after the claim is unreachable, and that is ASSERTED rather
    # than ignored: a cell that refused and then ran on anyway would leave
    # something other than '?' behind.
    "claim2": NR, "cl2h": NR, "tone1": NR, "enter": NR, "leave": NR,
    "ticks": NR, "rel1": NR, "rel2": NR, "tone2": NR,
}


def say(s):
    print(s, flush=True)


def leg(tree, defines, want, label, fails):
    """Boot one kernel, run TAPELEND.O88, read its results block."""
    say("\n--- %s ---" % label)
    tree.apply()                    # the map must describe THIS kernel

    def S(n):
        return os88sym.linear(n, defines)

    settle = os88marty.settle
    with os88marty.launch(tree.img("os8088-360.img"),
                          apps="build/tapelend360.img",
                          machine=MACHINE) as m:
        settle(m, gate=os88marty.desktop_up)
        mo = os88mouse.Mouse(marty=m)
        dispcp.open_drive(m, mo, S, settle, "B")
        wins = dispcp.win_list(m, S)
        if not wins:
            fails.append("%s: no Disk window after double-clicking B:" % label)
            return
        wx, wy = dispcp.win_rect(m, S, wins[-1])[:2]
        # The package REFUSES its own launch once it has run (it has nothing to
        # show), so `expect` must not be a window - what we want is the image
        # it wrote into, and the loader has already run the entry proc.
        dispcp.open_named(m, mo, S, settle, wx, wy, "TAPELEND.O88",
                          expect=None)
        settle(m)
        # Its region is freed with the refusal, so the block is wherever the
        # loader put it. Scan conventional memory for the magic: it is two
        # bytes followed by a run of the twelve result bytes, and the package
        # is the only thing in the machine that writes them.
        lo = 0x0600 * 16
        raw = m.read(lo, 0xA0000 - lo)

    hits = [i for i in range(len(raw) - 2 - len(FIELDS))
            if raw[i:i + 2] == TL_MAGIC]
    got = None
    for i in hits:
        cand = raw[i + 2: i + 2 + len(FIELDS)]
        # the block the package wrote has had at least the first byte answered
        if cand[0] != NR:
            got = cand
            break
    if got is None:
        fails.append("%s: no answered results block in memory - the entry "
                     "proc never ran (%d candidate magics)" % (label, len(hits)))
        return

    for n, name in enumerate(FIELDS):
        if want.get(name) is None:
            continue
        if got[n] != want[name]:
            fails.append("%s: %s is 0x%02X, want 0x%02X"
                         % (label, name, got[n], want[name]))
            say("    FAIL %-8s 0x%02X  want 0x%02X" % (name, got[n], want[name]))
        else:
            say("    ok   %-8s 0x%02X" % (name, got[n]))


def main():
    for p in ("build/tapelend360.img", "build/tapelend.bin"):
        if not os.path.exists(p):
            sys.exit("tapelend: %s is missing - `make tapelendtest` first" % p)
    fails = []

    leg(os88build.plain(), (), WANT_STOCK, "stock kernel", fails)
    leg(os88build.tree("QUANTUM=2"), ("SCH_QUANTUM=2",),
        WANT_QUANTUM, "QUANTUM=2 kernel", fails)

    for f in fails:
        say("  FAIL: " + f)
    say("\ntapelend: %s" % ("FAILED" if fails else "ok"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
