#!/usr/bin/env python3
"""bzballchk - the ball generator, bz_ballgen (apps/bonanza/bzballgen.inc), run
under an emulated 8086 (unicorn) on the STORED part, in place: the result must
equal tools/bonanza_assets.py's build_ball2, every byte (SPEC.md 128.25.5).

    python3 tools/bzballchk.py            # the check; exit 77 without unicorn
    python3 tools/bzballchk.py --clocks   # + the 8088 price of one generation

`check()` is what `make bonanza-check` runs.  --clocks prices the executed
instructions at 8088 clocks (a documented EU time, with the 4 clocks a byte
fetch floor, plus the EA cost) - an estimate, which a MartyPC run can replace."""
import os, re, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bonanza_assets as B

CSEG, DSEG, ESEG = 0x1000, 0x3000, 0x5000
BOX = 0x0400


def assemble(drop_nothing=True):
    with tempfile.TemporaryDirectory() as td:
        art = os.path.join(td, "art")
        os.makedirs(art)
        with open(os.path.join(art, "bzconst.inc"), "w") as f:
            f.write(B.emit_const())
        src = os.path.join(td, "t.asm")
        with open(src, "w") as f:
            f.write("cpu 8086\nbits 16\norg 0\nBZ_BOXB equ 256\nBZB_NSTR equ 14\nbz_boxbuf equ %d\n"
                    "%%include \"bzconst.inc\"\n"
                    "start: mov ax, %d\n call bz_ballgen\n hlt\n"
                    "%%include \"%s\"\n" % (BOX, ESEG, os.path.join(ROOT, "apps/bonanza/bzballgen.inc")))
        out = os.path.join(td, "t.bin")
        lst = os.path.join(td, "t.lst")
        subprocess.run(["nasm", "-w+error", "-f", "bin", "-I", art + "/", "-l", lst, "-o", out, src], check=True)
        return open(out, "rb").read()


def run(code, stored, trace=None):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x100000)
    mu.mem_write(CSEG * 16, code)
    mu.mem_write(ESEG * 16, stored)
    mu.mem_write(DSEG * 16, bytes(0x1000))
    mu.mem_write(DSEG * 16 + BOX, bytes([0xA5]) * 1024)      # scratch is never clean
    mu.reg_write(UC_X86_REG_DS, DSEG)
    mu.reg_write(UC_X86_REG_CS, CSEG)
    mu.reg_write(UC_X86_REG_SS, 0x4000)
    mu.reg_write(UC_X86_REG_SP, 0xFFF0)
    if trace is not None:
        mu.hook_add(UC_HOOK_CODE, lambda uc, a, n, u: trace(a - CSEG * 16, n))
    mu.emu_start(CSEG * 16, CSEG * 16 + 6, count=50000000)
    return bytes(mu.mem_read(ESEG * 16, len(stored)))


def check(verbose=True):
    try:
        import unicorn  # noqa: F401
    except Exception:
        return None
    code = assemble()
    res = []
    for mat in range(3):
        st = B.build_ball3(mat)
        got = run(code, st)
        ref = B.build_ball2(mat)
        res.append((mat, got == ref, next((i for i in range(len(ref)) if got[i] != ref[i]), -1)))
    return res


if __name__ == "__main__":
    r = check()
    if r is None:
        print("bzballchk: SKIP - unicorn is not importable here")
        sys.exit(77)
    for mat, ok, at in r:
        print("  %s: %s%s" % (B.MAT_NAMES[mat], "equal" if ok else "DIFFERS at ", "" if ok else at))
    sys.exit(0 if all(o for _, o, _ in r) else 1)
