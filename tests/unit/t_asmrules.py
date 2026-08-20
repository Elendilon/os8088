#!/usr/bin/env python3
"""Two source rules NASM cannot refuse and a reader does not see.

    python3 tests/unit/t_asmrules.py

1. UNREACHABLE CODE AFTER AN UNCONDITIONAL TRANSFER.

CLAUDE.md records what this costs, in the tracker's sequential-boundary work
(SPEC.md 45.13.5): *"It shipped once as DEAD CODE - two `jmp short`s in a row,
the old `jmp short .out` above the new `jmp short .carry` - which assembles
under `-w+error`, boots, and puts the field's original complaint back in the
field's original words."*  That is the whole failure mode.  An instruction
after an unconditional `jmp`/`ret`/`iret` with no label between them can never
execute, so the assembler is content, the machine boots, and the feature you
just wrote is simply not there.  It is the residue of an edit that inserted a
new path above an old one, which is exactly what a merge does.

Its first run on this tree found one, in `drivers/hdd/tool.inc` - a duplicated
`jmp short .out`, benign because both went to the same place, and two bytes of
a driver that could never run.

`jmp short $+2` IS NOT A TRANSFER AWAY and must not be reported: it jumps to
the very next instruction and is the 8086 I/O settling idiom (it flushes the
prefetch queue), used nine times in `clock.inc`, `mouse.inc` and
`lplink.inc`.  Anything whose target is `$`-relative is skipped.

WHAT IT CANNOT SEE, by construction and worth stating so nobody trusts it too
far: a jump table, a computed `jmp bx`, and a label that is referenced only
through a macro.  It is a lint, not a proof - so it only ever reports a line
that is unreachable by the plainest possible reading.

2. THE 8086 CONSTRAINT IS REACHABLE FROM EVERY ROOT.

SPEC.md 1's first hard rule is that this is an 8086 target, and the mechanism
is one `cpu 8086` directive - after which NASM refuses `pusha`, `movzx`, a
32-bit register and `shl reg, imm`.  Without it those assemble silently and
fault on the machine the whole project is calibrated against.  The kernel
declares it; a package gets it from `OS88_HEADER` in `apps/os88api.inc` and a
driver from `drivers/os88drv.inc`.

`boot/boot.asm` had NO 8086 constraint at all until this check was written -
512 bytes that run on a 5150 before anything has probed anything.  Adding it
changed `build/boot.bin` by **0 bytes**, which is what says the sector was
already clean and that what was missing was the refusal, not a fix.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from harness import check, done                           # noqa: E402

# The 8086 mnemonic set. A whitelist rather than "anything that looks like an
# instruction", because the noise this has to reject is `equ`, `db`, `section`
# and the tree's UPPERCASE macro invocations - all of which are perfectly
# legal after a `ret`.
MNEMONIC = set("""
aaa aad aam aas adc add and call cbw clc cld cli cmc cmp cmps cmpsb cmpsw cwd
daa das dec div hlt idiv imul in inc int into iret ja jae jb jbe jc jcxz je jg
jge jl jle jmp jna jnae jnb jnbe jnc jne jng jnge jnl jnle jno jnp jns jnz jo
jp jpe jpo js jz lahf lds lea les lock lods lodsb lodsw loop loope loopne
loopnz loopz mov movs movsb movsw mul neg nop not or out pop popf push pushf
rcl rcr rep repe repne repnz repz ret retf retn rol ror sahf sal sar sbb scas
scasb scasw shl shr stc std sti stos stosb stosw sub test wait xchg xlat xlatb
xor
""".split())

UNCOND = re.compile(r"^\s*(jmp|ret|retf|iret)\b(.*)$", re.I)
LABEL = re.compile(r"^\s*([.A-Za-z_][\w.$@]*:|%)")
SELFREL = re.compile(r"\$")            # `jmp short $+2` - the I/O settle idiom

SDK_WITH_CPU = ("os88api.inc", "os88drv.inc")


def sources():
    for sub in ("kernel", "boot", "apps", "drivers"):
        for dirpath, _, files in os.walk(os.path.join(ROOT, sub)):
            for f in sorted(files):
                if f.endswith((".asm", ".inc")):
                    yield os.path.join(dirpath, f)


def dead_code(path):
    """[(line, after, dead)] - instructions that cannot be reached."""
    out = []
    with open(path, errors="replace") as f:
        lines = f.read().split("\n")
    prev = None
    for i, raw in enumerate(lines):
        s = raw.split(";")[0].rstrip()
        if not s.strip():
            continue
        if LABEL.match(s):
            prev = None                    # a label makes the next line reachable
            continue
        word = s.strip().split()[0].lower()
        # A dead `nop` is PADDING and can never be a lost feature: every FAT
        # boot sector in this tree opens `jmp short entry` / `nop` so that the
        # BPB starts at offset +3 (SPEC.md 18.2 rule 2 tests the first byte),
        # and that `nop` is unreachable by design and mandatory.
        if prev is not None and word in MNEMONIC and word != "nop":
            out.append((i + 1, lines[prev].strip(), s.strip()))
        m = UNCOND.match(s)
        prev = i if (m and not SELFREL.search(m.group(2))) else None
    return out


def main():
    files = list(sources())
    for path in files:
        rel = os.path.relpath(path, ROOT)
        for line, after, dead in dead_code(path):
            check(False, "%s:%d is unreachable" % (rel, line),
                  "nothing can transfer here - the line above is an unconditional "
                  "jump and there is no label between them. An edit that inserted a "
                  "new path above an old one leaves exactly this (SPEC.md 45.13.5)",
                  got=dead, want="a label, or the line deleted")

    # Every root NASM is pointed at must be able to see a `cpu 8086`.
    # A "root" is an .asm that nothing %includes. Reading the Makefile for
    # the name instead was tried and is UNSOUND: `runcpm.asm` and
    # `ccsmoke.asm` are built through pattern rules that never spell the file
    # out, so both dropped silently out of the list - and a root that is not
    # detected is a root that is not checked, which is the one failure a gate
    # may not have.
    included = set()
    for q in files:
        with open(q, errors="replace") as f:
            for i in re.findall(r'^\s*%include\s+"([^"]+)"', f.read(), re.M):
                included.add(os.path.basename(i))
    roots = [p for p in files
             if p.endswith(".asm") and os.path.basename(p) not in included]
    checked, gated = 0, 0
    for path in sorted(set(roots)):
        rel = os.path.relpath(path, ROOT)
        with open(path, errors="replace") as f:
            src = f.read()
        # A C package's body is `<name>.gen.asm`, written by SmallerC, which
        # targets an 80386 even in 16-bit mode. `tools/cc8086.py` is that
        # output's 8086 gate - it LOWERS the seven 386-isms SmallerC emits and
        # refuses the rest - so the constraint lives there and a bare
        # `cpu 8086` here would refuse the compiler's own output instead.
        if re.search(r'^\s*%include\s+"[\w.]+\.gen\.asm"', src, re.M):
            gated += 1
            continue
        if re.search(r"^\s*cpu\s+8086\b", src, re.M):
            checked += 1
            continue
        inc = re.findall(r'^\s*%include\s+"([^"]+)"', src, re.M)
        via = [i for i in inc if os.path.basename(i) in SDK_WITH_CPU]
        if check(bool(via), "%s can reach a `cpu 8086`" % rel,
                 "SPEC.md 1: without the directive NASM accepts pusha, movzx, a "
                 "32-bit register and `shl reg, imm` - all of which fault on the "
                 "4.77MHz 8088 this project targets, having assembled in silence",
                 got="no `cpu 8086` and no SDK include",
                 want="cpu 8086, or %include an SDK"):
            checked += 1

    print("t_asmrules: %d sources scanned for dead code, %d roots 8086-constrained "
          "(%d C roots gated by tools/cc8086.py instead)" % (len(files), checked, gated))
    done("t_asmrules")


if __name__ == "__main__":
    main()
