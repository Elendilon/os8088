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


def _price(text, size):
    """8088 clocks of one instruction: the 8086 EU time, +4 a word memory
    access (the 8-bit bus), floored at 4 a byte fetched.  A table for the
    instructions bz_ballgen uses; branches are priced taken (the loop's case)"""
    t = text.replace("es ", "").strip()
    pre = 2 if text.startswith("es ") else 0
    op, _, rest = t.partition(" ")
    a = [x.strip() for x in rest.split(",")] if rest else []
    mem = [x for x in a if x.startswith(("[", "word [", "byte ["))]
    word = any(x.startswith("word") for x in a) or (mem and not any(r in a for r in ("al", "ah", "bl", "bh", "cl", "ch", "dl", "dh")))
    ea = 0
    if mem:
        m = mem[0]
        ea = 6 if re.fullmatch(r"(word |byte )?\[0x[0-9a-f]+\]", m) else 5 if "+" not in m else 9
        if "+" in m and re.search(r"0x[0-9a-f]+\]", m):
            ea += 4
    wa = 4 if (mem and word) else 0
    imm = bool(a) and a[-1].startswith("0x") or (len(a) > 1 and a[-1].lstrip("-").isdigit())
    if op == "mov":
        c = (8 + ea if mem and a[0] not in [m for m in mem] else 9 + ea) if mem else (4 if imm else 2)
    elif op in ("add", "sub", "and", "or", "xor", "cmp"):
        c = (9 + ea if mem and a[0] not in mem else (10 if op == "cmp" else 16) + ea) if mem else (4 if imm else 3)
        if mem and imm and a[0] in mem:
            c = (10 if op == "cmp" else 17) + ea
    elif op in ("shl", "shr", "rcl", "rcr", "ror", "sar"):
        c = 2 if a[-1] == "1" else 8
    elif op in ("inc", "dec"):
        c = 15 + ea if mem else (3 if a[0][-1] in "lh" else 2)
    elif op in ("not", "neg"):
        c = 3
    elif op in ("lodsb", "lodsw"): c = 12
    elif op in ("stosb", "stosw"): c = 11
    elif op == "movsw": c = 18
    elif op == "loop": c = 17
    elif op in ("jz", "jnz", "jc", "jnc", "jb", "jnb", "ja", "jna", "je", "jne", "jae"): c = 16
    elif op in ("jmp",): c = 15
    elif op == "call": c = 19
    elif op == "ret": c = 16
    elif op == "xchg": c = 4
    elif op == "div": c = 85
    elif op == "lea": c = 2 + ea
    elif op == "push": c = 11
    elif op == "pop": c = 8
    elif op == "cld": c = 2
    else: c = 4
    return max(c + wa + pre, 4 * size)


def clocks():
    """the executed instructions of one generation per material, priced"""
    code = assemble()
    dis = subprocess.run(["ndisasm", "-b", "16", "-"], input=code, capture_output=True, check=True).stdout.decode()
    info = {}
    rows = [l.split(None, 2) for l in dis.splitlines()]
    for i, (ad, hx, tx) in enumerate(rows):
        nxt = int(rows[i + 1][0], 16) if i + 1 < len(rows) else len(code)
        a = int(ad, 16)
        tx = re.sub(r"\b0x0*([0-9a-f]+)\b", lambda m: "0x" + m.group(1), tx.lower())
        info[a] = (tx, nxt - a)
    out = []
    for mat in range(3):
        cnt = {}
        def tr(off, n):
            cnt[off] = cnt.get(off, 0) + 1
        run(code, B.build_ball3(mat), trace=tr)
        tot = sum(_price(*info[a]) * n for a, n in cnt.items() if a in info)
        out.append((mat, sum(cnt.values()), tot))
    return out


if __name__ == "__main__":
    if "--clocks" in sys.argv:
        for mat, n, c in clocks():
            print("  %-6s %8d instructions, %9d clocks = %6.1f ms at 4.77 MHz" % (B.MAT_NAMES[mat], n, c, c / 4772.727))
        sys.exit(0)
    r = check()
    if r is None:
        print("bzballchk: SKIP - unicorn is not importable here")
        sys.exit(77)
    for mat, ok, at in r:
        print("  %s: %s%s" % (B.MAT_NAMES[mat], "equal" if ok else "DIFFERS at ", "" if ok else at))
    sys.exit(0 if all(o for _, o, _ in r) else 1)
