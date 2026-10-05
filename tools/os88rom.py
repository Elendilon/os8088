#!/usr/bin/env python3
"""os88rom - build os8088's ROM for an IBM 5150's five spare sockets.

docs/plans/ROM-PLAN.md is the design and section 1.3 is the layout. The window
is U28-U32, F4000-FDFFF, 40,960 bytes, laid out as ONE option ROM:

    0x0000  55 AA 40  E9 rel16  'OS88'  fmt kind  dw id  bal1 0    16 bytes
    0x0010  the payload (the kernel's .cold, or the socket-check pattern)
     ...    0xFF fill
    TAIL    boot/osrom.asm, assembled at its own offset
    0x9FFF  bal2

The header declares 32KB, and bal1 makes F4000-FBFFF sum to zero for the
option-ROM check. bal2 makes FC000-FDFFF sum to zero for the 10/27/82 BIOS's
one remaining BASIC-module check. GLaBIOS steps on through FC000-FDFFF in 2KB
looking for further option ROMs, so no 2KB boundary past the declared length
may begin 55 AA. The build refuses one that does rather than ship a ROM whose
POST behaviour depends on a coincidence in the payload.

Kinds:
    socket   the socket-check ROM - a pattern a stuck address line, a crossed
             chip select or a dropped byte cannot reproduce, and an init that
             prints `U28 ok ... U32 ok` at POST. No os8088 code is involved.
             It proves a ROM board before the kernel is asked to run on it.

Outputs, into --out (default build/rom/):
    <name>.bin               the 40KB window - MartyPC's custom ROM, at 0xF4000
    <name>-U28.bin ... -U32.bin   one 8KB file per socket, for One ROM's
                             tooling (or an EPROM burner)

Usage:
    python3 tools/os88rom.py socket
    python3 tools/os88rom.py --selfcheck
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ROM_BASE = 0xF4000
ROM_SIZE = 40960
SOCK_SIZE = 8192
SOCKETS = ("U28", "U29", "U30", "U31", "U32")
DECL_BLOCKS = 0x40                  # 32KB - ROM-PLAN 1.3 point 2, NOT 0x50
DECL_SIZE = DECL_BLOCKS * 512
HDR_SIZE = 16
BAL1 = 14                           # the header's balance byte
FMT = 1
KIND_SOCK, KIND_KERNEL = 1, 2

# the 1981 BIOSes never run rom_init, so int 18h still lands at F600:0000 on
# them; the socket ROM can afford a far jump there, the kernel ROM cannot
# (its .cold runs straight through F6000)
INT18_AT = 0xF6000 - ROM_BASE


def fail(msg):
    sys.exit("os88rom: " + msg)


def build_str(build=None):
    try:
        with open(os.path.join(build or os.path.join(ROOT, "build"),
                               "buildnum.inc")) as f:
            m = re.search(r"BUILD_STR\s+'([^']*)'", f.read())
            return m.group(1) if m else "?"
    except OSError:
        return "?"


def assemble_tail(kind, at, extra=(), bstr=None):
    """boot/osrom.asm assembled at `at`; the bytes."""
    with tempfile.TemporaryDirectory(prefix="os88rom-") as tmp:
        out = os.path.join(tmp, "tail.bin")
        cmd = ["nasm", "-f", "bin", "-w+error", f"-DTAIL_AT={at}",
               f"-DROM_KIND={kind}", f"-DBUILD_STR='{bstr or build_str()}'",
               *extra, "-o", out, os.path.join(ROOT, "boot", "osrom.asm")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            fail("nasm refused boot/osrom.asm:\n" + r.stderr[-2000:])
        with open(out, "rb") as f:
            return f.read()


def sock_byte(o):
    """The socket-check pattern at window offset o - boot/osrom.asm's
    rom_sock_check computes the same: lo + 3*hi + 0x5A, mod 256."""
    return ((o & 0xFF) + 3 * (o >> 8) + 0x5A) & 0xFF


def layout(kind, payload_len, fill, extra=(), bstr=None):
    """The window with its header, payload and tail placed, balances unset.
    `fill(img, start, end)` writes the payload bytes."""
    tail0 = assemble_tail(kind, 0, extra, bstr)
    tail_at = ROM_SIZE - 1 - len(tail0)        # the last byte is bal2
    if HDR_SIZE + payload_len > tail_at:
        fail(f"the payload is {payload_len:,} bytes and the window holds "
             f"{tail_at - HDR_SIZE:,} after the header and the tail - "
             f"ROM-PLAN 3.6 is what to do about it")
    tail = assemble_tail(kind, tail_at, extra, bstr)
    if len(tail) != len(tail0):
        fail("boot/osrom.asm changed length with its origin")
    img = bytearray(b"\xFF" * ROM_SIZE)
    fill(img, HDR_SIZE, tail_at)
    img[tail_at:tail_at + len(tail)] = tail
    init = tail_at + 32                         # rom_init follows rom_id
    hdr = bytearray(HDR_SIZE)
    hdr[0:3] = bytes((0x55, 0xAA, DECL_BLOCKS))
    rel = (init - 6) & 0xFFFF                   # jmp near at +3, next ip +6
    hdr[3:6] = bytes((0xE9, rel & 0xFF, rel >> 8))
    hdr[6:10] = b"OS88"
    hdr[10] = FMT                               # fmt and kind ADJACENT: stage
    hdr[11] = kind                              # 2 tests them as one word
    hdr[12:14] = tail_at.to_bytes(2, "little")  # rom_id
    hdr[14] = 0                                 # bal1, below
    img[0:HDR_SIZE] = hdr
    # rom_id's tool-written fields (boot/osrom.asm: +10, +12, +14)
    img[tail_at + 10:tail_at + 12] = HDR_SIZE.to_bytes(2, "little")
    img[tail_at + 12:tail_at + 14] = payload_len.to_bytes(2, "little")
    img[tail_at + 14:tail_at + 16] = len(tail).to_bytes(2, "little")
    # +24 is rom_patch's offset (the assembler's); +26 its SEGMENT, which only
    # the window knows - stage 2 does `call far [id+24]`, so a zero here is a
    # far call into the interrupt table (it was, on the first kernel ROM)
    img[tail_at + 26:tail_at + 28] = (ROM_BASE >> 4).to_bytes(2, "little")
    return img, tail_at


def balance(img):
    """Set bal1 and bal2; then prove both sums and the GLaBIOS boundaries."""
    img[BAL1] = 0
    img[BAL1] = (-sum(img[0:DECL_SIZE])) & 0xFF
    img[-1] = 0
    img[-1] = (-sum(img[DECL_SIZE:])) & 0xFF
    assert sum(img[0:DECL_SIZE]) & 0xFF == 0
    assert sum(img[DECL_SIZE:]) & 0xFF == 0
    for o in range(DECL_SIZE, ROM_SIZE, 2048):
        if img[o] == 0x55 and img[o + 1] == 0xAA:
            fail(f"F{(ROM_BASE + o) >> 4:04X}:0000 begins 55 AA - GLaBIOS "
                 f"would take it for a second option ROM. Re-cut the payload "
                 f"(ROM-PLAN 1.3 point 4)")
    return img


def build_socket():
    def fill(img, a, b):
        for o in range(a, b):
            img[o] = sock_byte(o)
    img, tail_at = layout(KIND_SOCK, 0, fill)
    # ...the pattern runs to the tail, so payload_len is reported as what it
    # covers rather than zero
    img[tail_at + 12:tail_at + 14] = (tail_at - HDR_SIZE).to_bytes(2, "little")
    # F6000: jmp far F400:rom_stub, for a BIOS that never calls rom_init.
    # rom_stub is the 2nd routine in the tail; find it by its first bytes,
    # `sti / push cs / pop ds`, rather than trusting a hand count
    stub = img.find(bytes((0xFB, 0x0E, 0x1F)), tail_at)
    if stub < 0:
        fail("cannot find rom_stub in the tail")
    img[INT18_AT:INT18_AT + 5] = bytes((0xEA, stub & 0xFF, stub >> 8,
                                        (ROM_BASE >> 4) & 0xFF,
                                        ROM_BASE >> 12))
    return balance(img)


# --- THE KERNEL ROM (ROM-PLAN 3.4.3) ------------------------------------------
# A ROM_COLD kernel's `.cold` plus the tables boot/osrom.asm's rom_patch and
# rom_modfix need: every word the kernel uses to name `.cold`'s segment, by
# the segment it is an offset into; a hash over `.text` with the build
# number's words left out; and where rom_mfp is. All of it is derived from the
# kernel ASSEMBLY rather than from the binary alone, and the assembly is
# proved to be the binary's first.

FIX_A, FIX_B = 0xF601, 0xF702       # tools/os88romfix.py's pair
KFLAGS = ["-DKZIP", "-DKZ_SECS=0", "-DKZ_RPARA=0", "-DKZ_NBLK=1",
          "-DKZ_HEADSEC=9"]          # the Makefile's first-pass kernel-full


def _sections(maptext):
    out = {}
    for m in re.finditer(r"^\s*([0-9A-F]+)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+"
                         r"[0-9A-F]+\s+progbits\s+(\S+)\s*$", maptext, re.M):
        out[m[4]] = (int(m[2], 16), int(m[3], 16))
    return out


def _symbol(maptext, section, name):
    t = maptext[maptext.index("-- Symbols"):]
    i = t.index("---- Section " + section + " ")
    j = t.find("---- Section", i + 10)
    for line in t[i:j if j > 0 else None].splitlines():
        p = line.split()
        if len(p) == 3 and p[2] == name:
            return int(p[1], 16)
    fail(f"{name} is not a symbol of {section} in this kernel")


def _assemble(tmp, build, variant, defs=(), inc_first=None, mapkind=None):
    import hashlib  # noqa: F401  (kept local: the socket path never needs it)
    tag = "_".join(d.strip("-D").replace("=", "") for d in defs) or "plain"
    out = os.path.join(tmp, f"k_{tag}.bin")
    src = os.path.join(tmp, "kernel", "kernel.asm")
    if mapkind:
        mapf = os.path.join(tmp, f"k_{tag}.map")
        asm = os.path.join(tmp, "kernel", f"_rom_{tag}.asm")
        with open(src) as f, open(asm, "w") as g:
            g.write(f"[map {mapkind} {mapf}]\n" + f.read())
        src = asm
    incs = ["-I", os.path.join(tmp, "kernel") + "/",
            "-I", os.path.join(ROOT, "apps") + "/"]
    if inc_first:
        incs += ["-I", inc_first + "/"]
    incs += ["-I", build + "/"]
    cmd = ["nasm", "-f", "bin", "-w+error", *incs, f"-D{variant}",
           *KFLAGS, *defs, "-o", out, src]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        fail("nasm refused the kernel:\n" + r.stderr[-2000:])
    with open(out, "rb") as f:
        data = f.read()
    if mapkind:
        with open(mapf) as f:
            return data, f.read()
    return data, None


def _section_symbols(maptext, section):
    t = maptext[maptext.index("-- Symbols"):]
    i = t.index("---- Section " + section + " ")
    j = t.find("---- Section", i + 10)
    out = []
    for line in t[i:j if j > 0 else None].splitlines():
        p = line.split()
        if len(p) == 3 and re.match("^[0-9A-F]+$", p[1]):
            out.append((int(p[1], 16), p[2]))
    return sorted(out)


DATA_DIR = re.compile(r"^\s*(?:times\s+[^;]+?\s+)?(?:db|dw|dd|dq|resb|resw|"
                      r"resd|incbin)\b", re.I)


def _data_labels():
    """Every kernel label whose line - or the first code line after it - is a
    data directive. Read off the source, so a new `.text` variable is left out
    of the hash without anybody listing it."""
    names = set()
    files = [os.path.join(ROOT, "kernel", f) for f in
             sorted(os.listdir(os.path.join(ROOT, "kernel")))
             if f.endswith((".inc", ".asm"))]
    for f in files:
        pending = None
        for line in open(f, errors="replace"):
            code = line.split(";", 1)[0].rstrip()
            if not code.strip():
                continue
            m = re.match(r"^([A-Za-z_]\w*):?(\s+.*)?$", code)
            if m and not code[0].isspace():
                rest = (m.group(2) or "").strip()
                if not rest:
                    pending = m.group(1)
                    continue
                if DATA_DIR.match(" " + rest):
                    names.add(m.group(1))
                pending = None
                continue
            if pending and DATA_DIR.match(code):
                names.add(pending)
            pending = None
    return names


def _symbol_any(maptext, name):
    """A KERNEL_SEG offset: `.text` or `.bss` (vfollows `.text`, so its
    virtual addresses are offsets into the same segment)."""
    for sec in (".text", ".bss"):
        try:
            for v, n in _section_symbols(maptext, sec):
                if n == name:
                    return v
        except ValueError:
            pass
    fail(f"{name} is in neither .text nor .bss")


def kernel_tables(build, variant):
    """Everything the ROM needs to know about the kernel `build` holds."""
    sys.path.insert(0, HERE)
    import os88mod
    import os88romfix
    full_path = os.path.join(build, "kernel-full.bin")
    if not os.path.exists(full_path):
        fail(f"no {full_path} - build that kernel first (`make small`)")
    with open(full_path, "rb") as f:
        full = f.read()
    with tempfile.TemporaryDirectory(prefix="os88rom-k-") as tmp:
        shutil.copytree(os.path.join(ROOT, "kernel"),
                        os.path.join(tmp, "kernel"))
        kp = os.path.join(tmp, "kernel", "kernel.asm")
        with open(kp) as f:
            src = f.read()
        with open(kp, "w") as f:
            f.write(os88romfix.decouple(src))
        a, amap = _assemble(tmp, build, variant, mapkind="all")
        f1, _ = _assemble(tmp, build, variant, (f"-DCOLD_CS=0x{FIX_A:04X}",))
        f2, _ = _assemble(tmp, build, variant, (f"-DCOLD_CS=0x{FIX_B:04X}",))
        bn = os.path.join(tmp, "bn")
        os.makedirs(bn)
        with open(os.path.join(bn, "buildnum.inc"), "w") as f:
            f.write("%define BUILD_NUM 999\n%define BUILD_STR '999'\n")
        c, _ = _assemble(tmp, build, variant, ("-DROMBN",), inc_first=bn)
    secs = _sections(amap)
    for need in (".text", ".cold", ".ovl", ".ovlw"):
        if need not in secs:
            fail(f"the kernel has no {need} section")

    # THE ASSEMBLY IS THE BINARY: every section the ROM reasons about must be
    # byte-identical to the build's own kernel-full.bin. `.boot2` is not
    # compared - the Makefile's second pass re-assembles it with the packed
    # file's numbers - and nothing the ROM touches is in it
    if len(a) != len(full):
        fail(f"{full_path} is {len(full):,} bytes and this tree assembles "
             f"{len(a):,} - rebuild that kernel from this tree first")
    for name, (st, en) in secs.items():
        if name == ".boot2":
            continue
        if a[st:en] != full[st:en]:
            fail(f"{name} differs between this tree's assembly and "
                 f"{full_path} - rebuild that kernel from this tree first")

    tst, ten = secs[".text"]
    cst, cen = secs[".cold"]
    wst, wen = secs[".ovlw"]
    if cst < wst:
        fail("`.cold` sits below `.ovlw` in this kernel's file - it was not "
             "built with ROM_COLD (kernel.asm), so nothing re-points it")
    with open(os.path.join(ROOT, "kernel", "kernel.asm")) as f:
        kseg = int(re.search(r"^KERNEL_SEG\s+equ\s+(0x[0-9A-Fa-f]+)",
                             f.read(), re.M).group(1), 16)
    for what, off in (("`.cold`", cst - tst), ("`.ovlw`", wst - tst)):
        if off % 16:
            fail(f"{what} does not start on a paragraph past `.text`")
    coldram = kseg + (cst - tst) // 16
    fatseg = kseg + (wst - tst) // 16

    _mapoff, rows = os88mod.read_map(a)
    lists = {"text": [], "ovlw": [], "ovl": [], "mods": {}}
    i = 0
    while i < len(f1):
        if f1[i] == f2[i]:
            i += 1
            continue
        w1 = f1[i] | f1[i + 1] << 8
        w2 = f2[i] | f2[i + 1] << 8
        if (w2 - w1) & 0xFFFF != FIX_B - FIX_A or w1 != FIX_A:
            fail(f"file offset {i:#x} moves with `.cold`'s segment but is not "
                 f"a plain word naming it - not a patchable site")
        if a[i] | a[i + 1] << 8 != coldram:
            fail(f"file offset {i:#x} is a site but the plain kernel does not "
                 f"hold COLD_RAM ({coldram:#06x}) there")
        if tst <= i < ten:
            lists["text"].append(i - tst)
        elif wst <= i < wen:
            lists["ovlw"].append(i - wst)
        elif i < secs[".ovl"][1] and (i >= secs[".ovl"][0] or
                                       i < secs[".boot2"][1]):
            lists["ovl"].append(i)          # .ovl and .boot2: blob offsets
        elif cst <= i < cen:
            fail(f"`.cold` names its own segment at +{i - cst:#x} - "
                 f"`tools/os88romfix.py --check` (ROM-PLAN 3.2)")
        else:
            for n, (st, sz, _ne) in enumerate(rows):
                if st <= i < st + sz:
                    lists["mods"].setdefault(n, []).append(i - st)
                    break
            else:
                fail(f"a site at file offset {i:#x} is in no section the ROM "
                     f"can reach")
        i += 2

    # the build number's words, out of the hash
    skip = set()
    for i in range(tst, ten):
        if a[i] != c[i]:
            skip.add((i - tst) // 2)
    # ...and `.text`'s DATA, which is out of it too: the boot writes it before
    # the ROM is asked (the boot timer, [spl_fseg], every vid_* the splash's
    # adapter probe fills in - measured on the first kernel ROM: 41 bytes, the
    # same on no two machines). The hash is about CODE - a routine that kept
    # its address and changed its contract - so a label declared with a data
    # directive is left out to the next label. One this misses makes the hash
    # disagree and the ROM REFUSE, which is the safe way round, and
    # tests/romsmall.py's leg A is what would show it.
    tsyms = _section_symbols(amap, ".text")
    data = _data_labels()
    addrs = [v for v, _ in tsyms]
    for k, (v, name) in enumerate(tsyms):
        if name.split(".")[0] in data and "." not in name:
            end = addrs[k + 1] if k + 1 < len(addrs) else ten - tst
            for w in range(v // 2, (end + 1) // 2):
                skip.add(w)
    nwords = (ten - tst) // 2
    spans, w = [], 0
    while w < nwords:
        if w in skip:
            w += 1
            continue
        s0 = w
        while w < nwords and w not in skip:
            w += 1
        spans.append((s0 * 2, w - s0))
    text = a[tst:ten]
    h = text_hash(text, spans)
    return {"coldram": coldram, "fatseg": fatseg, "kseg": kseg,
            "cold": a[cst:cen], "hash": h, "spans": spans, "lists": lists,
            "nmods": len(rows), "mfp": _symbol(amap, ".text", "rom_mfp"),
            "modtab": _symbol_any(amap, "mod_tab"),
            "text": text, "skipwords": sorted(skip)}


def text_hash(text, spans):
    """boot/osrom.asm's rom_patch step 2, in Python: h = rol(h, 1) ^ word."""
    h = 0
    for st, n in spans:
        for k in range(n):
            wd = text[st + 2 * k] | text[st + 2 * k + 1] << 8
            h = ((h << 1) | (h >> 15)) & 0xFFFF
            h ^= wd
    return h


def write_romtab(t, path):
    L = t["lists"]
    out = [f"; generated by tools/os88rom.py - ROM-PLAN 3.4.3. Do not edit.",
           f"RT_KSEG     equ 0x{t['kseg']:04X}",
           f"RT_FATSEG   equ 0x{t['fatseg']:04X}",
           f"RT_COLDRAM  equ 0x{t['coldram']:04X}",
           f"RT_COLDLEN  equ {len(t['cold'])}",
           f"RT_HASH     equ 0x{t['hash']:04X}",
           f"RT_MFP      equ 0x{t['mfp']:04X}",
           f"RT_MODTAB   equ 0x{t['modtab']:04X}",
           f"RT_MODRSZ   equ 4",
           f"RT_NTEXT    equ {len(L['text'])}",
           f"RT_NOVLW    equ {len(L['ovlw'])}",
           f"RT_NOVL     equ {len(L['ovl'])}",
           f"RT_NMODS    equ {t['nmods']}"]

    def words(label, ws):
        out.append(f"{label}:")
        for k in range(0, len(ws), 8):
            out.append("    dw " + ", ".join(f"0x{x:04X}" for x in ws[k:k + 8]))

    out.append("rt_spans:")
    for st, n in t["spans"]:
        out.append(f"    dw 0x{st:04X}, {n}")
    out.append("rt_spans_end:")
    words("rt_text", L["text"])
    words("rt_ovlw", L["ovlw"])
    words("rt_ovl", L["ovl"])
    out.append("rt_mods:")
    for n in range(t["nmods"]):
        out.append(f"    dw rt_mod{n}, {len(L['mods'].get(n, []))}")
    for n in range(t["nmods"]):
        words(f"rt_mod{n}", L["mods"].get(n, []))
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")


def build_kernel(build, variant):
    t = kernel_tables(build, variant)
    with tempfile.TemporaryDirectory(prefix="os88rom-t-") as tmp:
        tab = os.path.join(tmp, "romtab.inc")
        write_romtab(t, tab)
        cold = t["cold"]

        def fill(img, a, b):
            img[a:a + len(cold)] = cold
        img, tail_at = layout(KIND_KERNEL, len(cold), fill,
                              extra=(f'-DROMTAB="{tab}"',),
                              bstr=build_str(build))
    return balance(img), t


def model_adopt(img, kernel, blob, t):
    """rom_patch, in Python, against an expanded kernel - the ROM's three
    tests and its patch. `kernel` is the bytes at KERNEL_SEG (patched in
    place); returns True when the ROM would adopt it."""
    cold = img[HDR_SIZE:HDR_SIZE + len(t["cold"])]
    off = (t["coldram"] - t["kseg"]) * 16
    if kernel[off:off + len(cold)] != cold:
        return False
    if text_hash(kernel, t["spans"]) != t["hash"]:
        return False
    fat = (t["fatseg"] - t["kseg"]) * 16
    sites = ([(kernel, o) for o in t["lists"]["text"]]
             + [(kernel, fat + o) for o in t["lists"]["ovlw"]]
             + [(blob, o) for o in t["lists"]["ovl"]])
    if any(b[o] | b[o + 1] << 8 != t["coldram"] for b, o in sites):
        return False
    rcs = (ROM_BASE >> 4) + 1
    for b, o in sites:
        b[o:o + 2] = rcs.to_bytes(2, "little")
    return True


def verify_model(build, img, t):
    """Run rom_patch's Python model against the kernel this ROM was cut from,
    as stage 2 leaves it: it must ADOPT that one, and REFUSE it with one code
    byte of `.text` changed and with one byte of `.cold` changed. Each answer
    is a property of the tables the ROM carries, asked before it ships."""
    probs = []
    kb = open(os.path.join(build, "kernel.bin"), "rb").read()
    # the blob is the file's head up to `.text`, which starts where the
    # kernel's first .text byte sits; find it from the cold image instead of
    # restating BOOT2_PAD: `.cold`'s RAM offset is known from the tables
    off = (t["coldram"] - t["kseg"]) * 16
    pos = kb.find(bytes(t["cold"][:64]))
    if pos < 0:
        return ["the ROM's .cold is not in kernel.bin at all"]
    b2 = pos - off
    kern, blob = bytearray(kb[b2:]), bytearray(kb[:b2])
    if not model_adopt(img, bytearray(kern), bytearray(blob), t):
        probs.append("the model refuses the kernel this ROM was cut from")
    skip = set(t["skipwords"])
    code = next(w for w in range(len(t["text"]) // 2) if w not in skip)
    k2 = bytearray(kern)
    k2[code * 2] ^= 0x01
    if model_adopt(img, k2, bytearray(blob), t):
        probs.append("the model adopts a kernel with a code byte changed")
    k3 = bytearray(kern)
    k3[off + 100] ^= 0x01
    if model_adopt(img, k3, bytearray(blob), t):
        probs.append("the model adopts a kernel whose .cold differs")
    return probs


def write(img, out, name):
    os.makedirs(out, exist_ok=True)
    whole = os.path.join(out, name + ".bin")
    with open(whole, "wb") as f:
        f.write(img)
    for i, sock in enumerate(SOCKETS):
        with open(os.path.join(out, f"{name}-{sock}.bin"), "wb") as f:
            f.write(img[i * SOCK_SIZE:(i + 1) * SOCK_SIZE])
    return whole


def check(img):
    """What the two BIOSes will ask of the window, asked here."""
    probs = []
    if img[0:2] != b"\x55\xAA":
        probs.append("no 55 AA at F4000")
    if img[2] != DECL_BLOCKS:
        probs.append(f"declares {img[2]} blocks, not {DECL_BLOCKS}")
    if sum(img[0:DECL_SIZE]) & 0xFF:
        probs.append("F4000-FBFFF does not sum to zero")
    if sum(img[DECL_SIZE:]) & 0xFF:
        probs.append("FC000-FDFFF does not sum to zero")
    if img[3] != 0xE9:
        probs.append("+3 is not a near jmp")
    init = (int.from_bytes(img[4:6], "little") + 6) & 0xFFFF
    rid = int.from_bytes(img[12:14], "little")
    if img[rid:rid + 8] != b"OS88ROM\0":
        probs.append("the header's identity pointer does not land on rom_id")
    if init != rid + 32:
        probs.append("the init jmp does not land on rom_init")
    if int.from_bytes(img[rid + 26:rid + 28], "little") != ROM_BASE >> 4:
        probs.append("rom_id+24 is not a far pointer into the window - "
                     "stage 2 far-calls it")
    return probs


def selfcheck():
    img = build_socket()
    probs = check(img)
    # the pattern the ROM's own loop recomputes, re-derived independently
    tail_at = int.from_bytes(img[12:14], "little")
    bad = [o for o in range(HDR_SIZE, tail_at)
           if not (INT18_AT <= o < INT18_AT + 5) and img[o] != sock_byte(o)]
    if bad:
        probs.append(f"{len(bad)} pattern byte(s) wrong, first at {bad[0]:#x}")
    if probs:
        fail("selfcheck: " + "; ".join(probs))
    print(f"os88rom: selfcheck ok - socket ROM {len(img):,} bytes, tail at "
          f"{tail_at:#06x} ({ROM_SIZE - tail_at - 1} bytes), both sums zero")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("kind", nargs="?", choices=("socket", "kernel"))
    ap.add_argument("--build", help="the kernel tree (kernel kind): its "
                    "kernel-full.bin and generated includes")
    ap.add_argument("--small", action="store_true",
                    help="the tree holds kern_small (default kern_big)")
    ap.add_argument("--name", help="output name (default osrom-<variant>)")
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "rom"))
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        selfcheck()
        return
    if a.kind == "socket":
        img = build_socket()
        probs = check(img)
        if probs:
            fail("; ".join(probs))
        path = write(img, a.out, "osrom-socket")
        print(f"os88rom: {os.path.relpath(path, ROOT)} and its five sockets - "
              f"the socket-check ROM, build {build_str()}")
        return
    if a.kind == "kernel":
        if not a.build:
            ap.error("kernel needs --build <tree>")
        variant = "KERN_SMALL" if a.small else "KERN_BIG"
        img, t = build_kernel(os.path.abspath(a.build), variant)
        probs = check(img) + verify_model(os.path.abspath(a.build), img, t)
        if probs:
            fail("; ".join(probs))
        name = a.name or ("osrom-small" if a.small else "osrom-big")
        path = write(img, a.out, name)
        tail_at = int.from_bytes(img[12:14], "little")
        L = t["lists"]
        print(f"os88rom: {os.path.relpath(path, ROOT)} and its five sockets - "
              f"{variant}'s .cold ({len(t['cold']):,} bytes) at F401, build "
              f"{build_str(a.build)}; {len(L['text'])}+{len(L['ovlw'])}+"
              f"{len(L['ovl'])} kernel sites, "
              f"{sum(len(v) for v in L['mods'].values())} in "
              f"{t['nmods']} modules; {tail_at - HDR_SIZE - len(t['cold']):,} "
              f"bytes of the window spare")
        return
    ap.error("say which ROM to build")


if __name__ == "__main__":
    main()
