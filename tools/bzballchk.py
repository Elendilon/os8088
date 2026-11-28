#!/usr/bin/env python3
"""bzballchk - the ball generator, bz_ballgen (apps/bonanza/bzballgen.inc), run
under an emulated 8086 (unicorn) on the STORED part, in place: the result must
equal tools/bonanza_assets.py's build_ball2, every byte (SPEC.md 137.25.5).

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

CSEG = DSEG = 0x1000                # one segment: the package's image (its
ESEG = 0x5000                       # constants read through DS) and its bss
ESEG_IN = 0x6000                    # ES at the call (not the part's)
BOX = 0x2000


def assemble(patch=None, listing=False):
    """the routine assembled at org 0 behind a 3-instruction driver; patch =
    (old, new) breaks the source on purpose (the selfcheck's red arm)"""
    with tempfile.TemporaryDirectory() as td:
        inc = os.path.join(ROOT, "apps/bonanza/bzballgen.inc")
        if patch is not None:
            text = open(inc).read()
            assert text.count(patch[0]) == 1, patch[0]
            inc = os.path.join(td, "bzballgen.inc")
            with open(inc, "w") as f:
                f.write(text.replace(*patch))
        art = os.path.join(td, "art")
        os.makedirs(art)
        with open(os.path.join(art, "bzconst.inc"), "w") as f:
            f.write(B.emit_const())
        src = os.path.join(td, "t.asm")
        with open(src, "w") as f:
            f.write("cpu 8086\nbits 16\norg 0\nBZ_BOXB equ 256\nBZB_NSTR equ 14\nbz_boxbuf equ %d\n"
                    "%%include \"bzconst.inc\"\n"
                    "start: mov ax, %d\n call bz_ballgen\n hlt\n"
                    "%%include \"%s\"\n" % (BOX, ESEG, inc))
        out = os.path.join(td, "t.bin")
        lst = os.path.join(td, "t.lst")
        subprocess.run(["nasm", "-w+error", "-f", "bin", "-I", art + "/", "-l", lst, "-o", out, src], check=True)
        code = open(out, "rb").read()
        return (code, _labels(lst)) if listing else code


def run(code, stored, trace=None, probe=None):
    """the routine on the stored part; probe = {} also records what the call
    must keep (SPEC.md 137.25.5.1: AX and ES, the ball's selector never left in
    ES; DS, SP, DF) and every write outside the part, bz_boxbuf's 1,024 bytes
    and the stack (kern_mega: the claim is written only through ES)"""
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.x86_const import UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS, UC_X86_REG_SP
    from unicorn.x86_const import UC_X86_REG_AX, UC_X86_REG_EFLAGS
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x100000)
    assert len(code) <= BOX
    mu.mem_write(CSEG * 16, code)
    mu.mem_write(ESEG * 16, stored)
    mu.mem_write(DSEG * 16 + BOX, bytes([0xA5]) * 1024)      # scratch is never clean
    mu.reg_write(UC_X86_REG_DS, DSEG)
    mu.reg_write(UC_X86_REG_CS, CSEG)
    mu.reg_write(UC_X86_REG_ES, ESEG_IN)                     # the caller's ES, which must come back
    mu.reg_write(UC_X86_REG_SS, 0x4000)
    mu.reg_write(UC_X86_REG_SP, 0xFFF0)
    if trace is not None:
        mu.hook_add(UC_HOOK_CODE, lambda uc, a, n, u: trace(uc, a - CSEG * 16, n))
    if probe is not None:
        ok = ((ESEG * 16, ESEG * 16 + len(stored)), (DSEG * 16 + BOX, DSEG * 16 + BOX + 1024),
              (0x40000 + 0xFFF0 - 256, 0x40000 + 0xFFF0))
        stray = probe.setdefault("stray", [])

        def wr(uc, acc, a, n, v, u):
            if not any(lo <= a and a + n <= hi for lo, hi in ok):
                stray.append(a)
        mu.hook_add(UC_HOOK_MEM_WRITE, wr)
    mu.emu_start(CSEG * 16, CSEG * 16 + 6, count=50000000)
    if probe is not None:
        probe["kept"] = (mu.reg_read(UC_X86_REG_AX) == ESEG and mu.reg_read(UC_X86_REG_ES) == ESEG_IN
                         and mu.reg_read(UC_X86_REG_DS) == DSEG and mu.reg_read(UC_X86_REG_SP) == 0xFFF0
                         and not mu.reg_read(UC_X86_REG_EFLAGS) & 0x400)
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
        pr = {}
        got = run(code, st, probe=pr)
        ref = B.build_ball2(mat)
        at = next((i for i in range(len(ref)) if got[i] != ref[i]), -1)
        if at < 0 and not (pr["kept"] and not pr["stray"]):
            at = -2                 # equal, but AX/ES/DS/SP/DF not kept or a write outside its fence
        res.append((mat, at == -1, at))
    return res


# --- the PRICE: 8088 clocks of the executed instructions -------------------
# The 8086's documented EU times (Intel's tables), +4 for every WORD memory
# transfer (the 8088's 8-bit bus moves a word in two cycles), the EA cost,
# +2 a segment prefix, a branch at its TAKEN or NOT-TAKEN time as it went,
# a shift by CL and every REP iteration at the count it really ran; and the
# BUS floor: an instruction takes at least 4.34 clocks a code byte (the
# measured fetch rate, CLAUDE.md) plus 4 a data byte it moves, which bounds
# the short instructions the EU time alone would under-price.
_R8 = ("al", "ah", "bl", "bh", "cl", "ch", "dl", "dh")
_ALU = ("add", "adc", "sub", "sbb", "and", "or", "xor")
_JCC = ("jo", "jno", "jc", "jnc", "jb", "jnb", "jae", "jnae", "jz", "jnz", "je", "jne", "jbe", "jnbe",
        "ja", "jna", "js", "jns", "jpe", "jpo", "jl", "jnl", "jge", "jnge", "jle", "jng", "jg", "jnle")


def _ea(m):
    inner = m[m.index("[") + 1:m.index("]")]
    parts = [x for x in re.split(r"[+-]", inner) if x]
    regs = sorted(x for x in parts if x in ("bx", "bp", "si", "di"))
    disp = any(x not in ("bx", "bp", "si", "di") for x in parts)
    if not regs:
        return 6
    if len(regs) == 1:
        return 9 if disp else 5
    base = 7 if regs in (["bp", "di"], ["bx", "si"]) else 8
    return base + (4 if disp else 0)


def price(text, size, taken, cl, cx, first):
    """8088 clocks of ONE execution (a REP string op: one iteration, +9 on the first)"""
    t = text
    pre = 0
    while True:
        m = re.match(r"(es|cs|ss|ds) ", t)
        if not m:
            break
        pre += 2
        t = t[3:]
    t, n = re.subn(r"\[(es|cs|ss|ds):", "[", t)   # ndisasm writes an override INSIDE the operand
    pre += 2 * n
    t = re.sub(r"\b(byte|word) \+(0x[0-9a-f]+)", r"\2", t)   # a sign-extended immediate: still an immediate
    rep = t.startswith(("rep ", "repe ", "repne "))
    if rep:
        t = t.split(" ", 1)[1]
        if cx == 0:             # the emulator's last look at a spent count: no iteration
            return 0
    op, _, rest = t.partition(" ")
    a = [x.strip() for x in rest.split(",")] if rest else []
    mem = [i for i, x in enumerate(a) if "[" in x]
    m = a[mem[0]] if mem else None
    regs8 = any(x in _R8 for x in a)
    word = (m is not None and m.startswith("word")) or (m is not None and not m.startswith("byte") and not regs8)
    ea = (_ea(m) + pre) if m is not None else 0
    imm = bool(a) and "[" not in a[-1] and (a[-1].startswith("0x") or a[-1].lstrip("-").isdigit())
    dst_mem = bool(mem) and mem[0] == 0
    xfer = 0            # data bytes moved
    w = 2 if word else 1
    if op == "mov":
        if not m:
            c = 4 if imm else 2
        elif imm:
            c, xfer = 10 + ea, w
        elif dst_mem:
            c, xfer = 9 + ea, w
        else:
            c, xfer = 8 + ea, w
    elif op in _ALU + ("cmp", "test"):
        rmw = dst_mem and op not in ("cmp", "test")
        if not m:
            c = 4 if imm else 3
        elif imm:
            c = (17 if rmw else 10 if op == "cmp" else 11) + ea
        elif rmw:
            c = 16 + ea
        else:
            c = 9 + ea
        xfer = (2 * w if rmw else w) if m else 0
    elif op in ("shl", "sal", "shr", "sar", "rol", "ror", "rcl", "rcr"):
        n = cl if a[-1] == "cl" else 1
        if m:
            c = (20 + 4 * n if a[-1] == "cl" else 15) + ea
            xfer = 2 * w
        else:
            c = 8 + 4 * n if a[-1] == "cl" else 2
    elif op in ("inc", "dec"):
        if m:
            c, xfer = 15 + ea, 2 * w
        else:
            c = 3 if a[0] in _R8 else 2
    elif op in ("not", "neg"):
        if m:
            c, xfer = 16 + ea, 2 * w
        else:
            c = 3
    elif op in ("lodsb", "lodsw", "stosb", "stosw", "movsb", "movsw", "scasb", "scasw", "cmpsb", "cmpsw"):
        ww = 2 if op.endswith("w") else 1
        base = {"lods": (12, 13), "stos": (11, 10), "movs": (18, 17), "scas": (15, 15), "cmps": (22, 22)}[op[:4]]
        moves = 2 if op[:4] in ("movs", "cmps") else 1
        c = (base[1] if rep else base[0]) + (9 if rep and first else 0) + pre
        xfer = moves * ww
        pre = 0
    elif op == "xlatb" or op == "xlat":
        c, xfer = 11, 1
    elif op == "lea":
        c = 2 + ea - pre
    elif op == "xchg":
        if m:
            c, xfer = 17 + ea, 2 * w
        else:
            c = 3 if "ax" in a else 4
    elif op == "push":
        c, xfer = (16 + ea if m else 10 if a[0] in ("es", "cs", "ss", "ds") else 11), 2 + (2 if m else 0)
    elif op == "pop":
        c, xfer = (17 + ea if m else 8), 2 + (2 if m else 0)
    elif op in ("pushf",):
        c, xfer = 10, 2
    elif op in ("popf",):
        c, xfer = 8, 2
    elif op == "call":
        c, xfer = 19, 2
    elif op == "ret":
        c, xfer = 16, 2           # 8 + the queue's refill, as the 8088 tables give 20 with the word
    elif op == "jmp":
        c = 15
    elif op in _JCC:
        c = 16 if taken else 4
    elif op == "loop":
        c = 17 if taken else 5
    elif op in ("loope", "loopz", "loopne", "loopnz", "jcxz"):
        c = 18 if taken else 6
    elif op == "div":
        c = (162 if not m and a[0] not in _R8 else 90) + ea
        xfer = w if m else 0
    elif op == "mul":
        c = (133 if not m and a[0] not in _R8 else 77) + ea
        xfer = w if m else 0
    elif op in ("cbw", "clc", "stc", "cmc", "cld", "std", "cli", "sti", "hlt"):
        c = 2
    elif op == "cwd":
        c = 5
    elif op in ("sahf", "lahf"):
        c = 4
    elif op == "nop":
        c = 3
    else:
        raise ValueError("bzballchk.price: no 8088 time for %r" % text)
    c += 4 * (xfer // 2)          # the 8088: a word is two bus cycles
    fetch = 0 if (rep and not first) else size
    return max(c, 4.34 * fetch + 4 * xfer)


def _labels(lst):
    """label -> address from a nasm listing (org 0); a local label is
    reported as its owner's name and itself (bz_ballgen.fy)"""
    out = {}
    pend = []
    owner = ""
    for line in open(lst):
        m = re.match(r"\s*\d+\s+([0-9A-F]{8})\s+[0-9A-F]", line)
        body = re.sub(r"^\s*\d+\s+(?:[0-9A-F]{8}\s+\S+\s+)?(?:<\d+>\s+)?", "", line)
        lab = re.match(r"(\.?[A-Za-z_][\w.]*):", body)
        if lab:
            nm = lab.group(1)
            if nm.startswith("."):
                nm = owner + nm
            else:
                owner = nm
            pend.append(nm)
        if m and pend:
            for p in pend:
                out[p] = int(m.group(1), 16)
            pend = []
    return out


def clocks(profile=False):
    """the executed instructions of one generation per material, priced;
    profile: also the clocks by PHASE (the routine's labels that start one)"""
    code, labs = assemble(listing=True)
    dis = subprocess.run(["ndisasm", "-b", "16", "-"], input=code, capture_output=True, check=True).stdout.decode()
    info = {}
    rows = [l.split(None, 2) for l in dis.splitlines()]
    for i, (ad, hx, tx) in enumerate(rows):
        nxt = int(rows[i + 1][0], 16) if i + 1 < len(rows) else len(code)
        a = int(ad, 16)
        tx = re.sub(r"\b0x0*([0-9a-f]+)\b", lambda m: "0x" + m.group(1), tx.lower())
        info[a] = (tx, nxt - a)
    sel = [n for n in labs if n.startswith("bgp_")] or [n for n in labs if not n.startswith(("start", "BG_"))]
    phases = sorted((labs[n], n) for n in sel)
    out = []
    for mat in range(3):
        ex = []
        def tr(uc, off, n):
            from unicorn.x86_const import UC_X86_REG_CX
            ex.append((off, uc.reg_read(UC_X86_REG_CX)))
        run(code, B.build_ball3(mat), trace=tr)
        tot = 0.0
        byph = {}
        prev = None
        for i, (off, cx) in enumerate(ex):
            if off not in info:
                continue
            tx, sz = info[off]
            nxt = ex[i + 1][0] if i + 1 < len(ex) else None
            taken = nxt is not None and nxt != off + sz
            first = prev != off
            c = price(tx, sz, taken, cx & 0xFF, cx, first)
            prev = off
            tot += c
            if profile:
                ph = "?"
                for a, nm in phases:
                    if a <= off:
                        ph = nm
                byph[ph] = byph.get(ph, 0) + c
        out.append((mat, len(ex), int(tot), byph))
    return out


if __name__ == "__main__":
    if "--clocks" in sys.argv or "--profile" in sys.argv:
        prof = "--profile" in sys.argv
        allc = 0
        for mat, n, c, ph in clocks(prof):
            allc += c
            print("  %-6s %8d instructions, %9d clocks = %6.1f ms at 4.77 MHz" % (B.MAT_NAMES[mat], n, c, c / 4772.727))
            for nm, v in sorted(ph.items(), key=lambda kv: -kv[1]):
                print("      %-14s %9d  %5.1f%%" % (nm, v, 100.0 * v / c))
        print("  all three %9d clocks = %6.1f ms" % (allc, allc / 4772.727))
        sys.exit(0)
    r = check()
    if r is None:
        print("bzballchk: SKIP - unicorn is not importable here")
        sys.exit(77)
    for mat, ok, at in r:
        print("  %s: %s" % (B.MAT_NAMES[mat], "equal, registers kept, writes fenced" if ok else
                            "registers not kept or a stray write" if at == -2 else "DIFFERS at %d" % at))
    sys.exit(0 if all(o for _, o, _ in r) else 1)
