#!/usr/bin/env python3
"""RealDMG's FULL static recompiler, on the host (docs/plans/REALDMG-AOT-PLAN.md).

    python3 tools/gbaot.py cover GAME.GB              what the walk finds, no play
    python3 tools/gbaot.py build GAME.GB -o DIR       translate the whole cartridge
    python3 tools/gbaot.py check GAME.GB DIR [-n N]   run it beside the interpreter

A Game Boy cartridge's code is found by WALKING it (no play, no profile):
from 0100h, the RST and interrupt vectors, every direct JR, JP, CALL and RST,
the jump tables behind RST 28h-style dispatchers and behind the
`LD HL,table / ADD HL,BC / LD A,(HL+) / LD H,(HL) / LD L,A / JP HL` idiom,
and the bank a constant wrote to the MBC before a call into 4000-7FFF
(tools/gbstatic.py's discover). Every place a block can start is then
TRANSLATED by RealDMG's own translator - rdgjit.inc, assembled with rdgsys.inc
into tools/gbaot/aothost.asm and run under an 8086 emulator (Unicorn) - so a
block is byte for byte what the machine would make, and every gate on the
recompiler is a gate on this.

`check` is the equivalence instrument: the same cartridge run under the
interpreter and on the precompiled code, the same buttons pressed (gbprof's
platformer script), and every frame's Game Boy state - 8000-FFFF, the
registers, the time, the events and the M-cycles skipped - compared. Any
difference is a defect in the precompiled code, and the frame it appears in
says where to look.

Needs `pip install unicorn` and nasm (for the driver). No ROM is ever
committed; the games are the user's.
"""
import argparse
import collections
import hashlib
import json
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gbstatic as G  # noqa: E402

# --- the walk ---------------------------------------------------------------


def jump_tables(rom, found):
    """The JP HL dispatch idiom's tables, read at their constant base: every
    word while it is a code address in the same region, until the code the
    table points at begins. Returns {(bank, pc)} of targets."""
    out = set()
    for (b, pc), op in found.items():
        if op != 0xE9:
            continue
        if [rom.byte(b, pc - i) for i in (3, 2, 1)] != [0x2A, 0x66, 0x6F]:
            continue                                  # LD A,(HL+) / LD H,(HL) / LD L,A
        base = None
        for back in range(4, 14):
            if rom.byte(b, pc - back) == 0x21:        # LD HL,nn
                base = rom.byte(b, pc - back + 1) | rom.byte(b, pc - back + 2) << 8
                break
        if base is None:
            continue
        lo, hi = (0x4000, 0x8000) if pc >= 0x4000 else (0x0150, 0x4000)
        t, first = base, 0x10000
        for _ in range(128):
            if t >= first:
                break
            w = rom.byte(b, t) | rom.byte(b, t + 1) << 8
            if not (lo <= w < hi) and not (pc >= 0x4000 and 0x150 <= w < 0x4000):
                break
            k = (b if w >= 0x4000 else 0, w)
            if rom.byte(*k) in G.INVALID:
                break
            out.add(k)
            if w > base:
                first = min(first, w)
            t += 2
    return out


def walk(rom, seeds=()):
    """The cartridge's code: (found {(bank, pc): op}, extra seeds used)."""
    extra = set(seeds)
    for _ in range(6):
        found, _, _, _ = G.discover(rom, extra, True)
        new = jump_tables(rom, found) - extra
        if not new:
            break
        extra |= new
    return found, extra


def leaders(rom, found, extra, side=False):
    """Every place a block can start: the entries, every branch target, the
    instruction after a conditional transfer or a CALL/RST (a return lands
    there), the jump tables' words, and the instruction after a store that
    may take an interrupt or switch the bank (the IF/IE write and the guard
    leave there, REALDMG-SPEC 16.5) and after EI."""
    lead = {(0, 0x100)} | {(0, v) for v in range(0, 0x68, 8)} | set(extra)
    for (b, pc), op in found.items():
        a1 = rom.byte(b, pc + 1)
        imm = a1 | rom.byte(b, pc + 2) << 8
        nxt = pc + G.LEN[op]

        def kb(t):
            if t < 0x4000:
                return (0, t)
            return (b if pc >= 0x4000 else None, t)
        if op in G.JR:
            lead.add(kb(nxt + (a1 - 256 if a1 >= 128 else a1)))
        if op in {0xC3} | G.JPCC | {0xCD} | G.CALLCC:
            lead.add(kb(imm))
        if op in G.RSTS:
            lead.add((0, op & 0x38))
        nk = (b if nxt >= 0x4000 else 0, nxt)
        if op in G.CT and op not in (0x18, 0xC3, 0xC9, 0xD9, 0xE9):
            lead.add(nk)
        st = op in (0x02, 0x12, 0x22, 0x32, 0x77, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75,
                    0x36, 0x34, 0x35, 0xE2, 0x08, 0xFB)
        st |= op == 0xEA and (imm < 0x8000 or imm >= 0xFF00)
        st |= op == 0xE0 and (a1 < 0x80 or a1 == 0xFF)
        st |= op == 0xCB and (a1 & 7) == 6 and not (0x40 <= a1 < 0x80)
        if st and side:
            lead.add(nk)
    out = set()
    for b, pc in lead:
        if b is None:                    # bank 0 into 4000-7FFF of no known bank:
            for bb in range(1, rom.banks):   # every bank the walk found it in
                if (bb, pc) in found:
                    out.add((bb, pc))
        elif (b, pc) in found and pc < 0x8000:
            out.add((b, pc))
    return out


# --- the machine ------------------------------------------------------------

P_VIEW, P_CORE, P_ROM, P_NBANKS, P_HASH, P_PRF, P_PRFMASK, P_SEGA, P_SEGB = (
    0x10, 0x12, 0x14, 0x16, 0x18, 0x1A, 0x1C, 0x1E, 0x20)
P_MODE, P_HMASK, P_NOC, P_REASON, P_OUT, P_BUDGET, P_BANK, P_BMP = (
    0x22, 0x23, 0x24, 0x25, 0x26, 0x28, 0x2A, 0x2C)
E_INIT, E_PRELOAD, E_ROUND, E_FRAME, E_CONT = 0, 3, 6, 9, 12
STK_SEG, DRV_SEG = 0x0050, 0x0900
MEM_END = 0x10FFF0                       # what real mode can address, with A20
TOKEN = 0xF000                            # a block table's segment, as written:
                                          #   TOKEN + n names the image's segment n

INC = os.path.join(ROOT, "apps", "realdmg")


def symbols(build):
    v = {}
    for ln in open(os.path.join(aotdir(build), "rdgcore.inc")):
        p = ln.split()
        if len(p) == 3 and p[1] == "equ":
            v[p[0]] = int(p[2], 0)
    for ln in open(os.path.join(INC, "rdgdefs.inc")):
        p = ln.split(";")[0].split()
        if len(p) == 3 and p[1] == "equ":
            try:
                v[p[0]] = eval(p[2].replace("RDG_STATE", str(0x4000)), {}, v)
            except Exception:
                pass
    return v


def aotdir(build):
    return os.path.join(build, "gbaot")


def prerequisites(build, defines=()):
    """The PRECOMPILED core (rdggen.py's, assembled with RDG_AOTCORE: a fixed
    table's miss goes to the host's sorted list first, REALDMG-SPEC 20.9),
    its templates and offsets, and aothost.bin over them - all in
    build/gbaot/, rebuilt when a source moved. With `defines` (an
    instrument's: RT_DEADBUG, the negative control) a driver of its own."""
    d = aotdir(build)
    os.makedirs(d, exist_ok=True)
    gen = os.path.join(INC, "rdggen.py")
    tmpl = os.path.join(INC, "rdgtmpl.py")
    asm, core = os.path.join(d, "rdgcore.asm"), os.path.join(d, "rdgcore.bin")
    tbin, tinc = os.path.join(d, "rdgtmpl.bin"), os.path.join(d, "rdgcore.inc")

    def stale(out, *deps):
        return not os.path.exists(out) or any(os.path.getmtime(x) > os.path.getmtime(out) for x in deps)
    defs = os.path.join(INC, "rdgdefs.inc")
    if stale(asm, gen, defs):
        subprocess.check_call([sys.executable, gen, asm])
    if stale(core, asm, defs):
        subprocess.check_call(["nasm", "-f", "bin", "-w+error", "-DRDG_AOTCORE", "-I", INC + "/",
                               "-o", core, asm])
    if stale(tbin, core, tmpl, gen) or stale(tinc, core, tmpl, gen):
        subprocess.check_call([sys.executable, tmpl, core, tbin, tinc])
    drv = os.path.join(d, "aothost%s.bin" % "".join("-" + x for x in defines))
    src = os.path.join(ROOT, "tools", "gbaot", "aothost.asm")
    deps = [src, tbin, tinc] + [os.path.join(INC, f) for f in
                                ("rdgsys.inc", "rdgjit.inc", "rdgdefs.inc", "rdgaot.inc")]
    if stale(drv, *deps):
        subprocess.check_call(["nasm", "-f", "bin", "-w+error", "-I", INC + "/", "-I", d + "/"]
                              + ["-D" + x for x in defines] + ["-o", drv, src])
    return drv


class Machine:
    """An 8086 under Unicorn with aothost.bin in it."""

    def __init__(self, build, rom, defines=()):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_INTR
        from unicorn import x86_const as X
        self.X = X
        drv = open(prerequisites(build, defines), "rb").read()
        self.sym = symbols(build)
        self.rom = rom
        self.u = Uc(UC_ARCH_X86, UC_MODE_16)
        self.u.mem_map(0, 0x110000)
        self.u.mem_write(DRV_SEG * 16, drv)
        self.core_bin = open(os.path.join(aotdir(build), "rdgcore.bin"), "rb").read()
        self.u.hook_add(UC_HOOK_INTR, self._intr)
        self.slots = []                   # (segment of the 16KB slot, bank or None)
        self.prefer = None                # the banks rdg_init's fill maps first
        self.lru = collections.OrderedDict()

    # memory
    def w(self, seg, off, data):
        self.u.mem_write(seg * 16 + off, bytes(data))

    def r(self, seg, off, n):
        return bytes(self.u.mem_read(seg * 16 + off, n))

    def w16(self, seg, off, v):
        self.w(seg, off, struct.pack("<H", v & 0xFFFF))

    def r16(self, seg, off):
        return struct.unpack("<H", self.r(seg, off, 2))[0]

    def p(self, off, v, size=2):
        self.w(DRV_SEG, off, struct.pack("<H" if size == 2 else "<B", v))

    def pr(self, off, size=2):
        d = self.r(DRV_SEG, off, size)
        return struct.unpack("<H" if size == 2 else "<B", d)[0]

    # the INT 3 stops
    def _intr(self, uc, intno, ud):
        if intno == 3:
            self.stopped = True
            uc.emu_stop()
        else:
            raise RuntimeError("interrupt %d at %04X:%04X" % (
                intno, uc.reg_read(self.X.UC_X86_REG_CS), uc.reg_read(self.X.UC_X86_REG_IP)))

    def enter(self, entry):
        X = self.X
        self.u.reg_write(X.UC_X86_REG_SS, STK_SEG)
        self.u.reg_write(X.UC_X86_REG_SP, 0x7FF0)
        self.u.reg_write(X.UC_X86_REG_DS, DRV_SEG)
        self.u.reg_write(X.UC_X86_REG_ES, DRV_SEG)
        self.u.reg_write(X.UC_X86_REG_CS, DRV_SEG)
        self.u.reg_write(X.UC_X86_REG_IP, entry)
        self.run()

    def run(self):
        X = self.X
        while True:
            self.stopped = False
            cs = self.u.reg_read(X.UC_X86_REG_CS)
            ip = self.u.reg_read(X.UC_X86_REG_IP)
            self.u.emu_start(cs * 16 + ip, MEM_END + 0xF, timeout=60 * 1000000)
            if not self.stopped:
                raise RuntimeError("the machine stopped at %04X:%04X" % (
                    self.u.reg_read(X.UC_X86_REG_CS), self.u.reg_read(X.UC_X86_REG_IP)))
            if self.pr(P_REASON, 1) == 1:
                self.bank_service()
                continue
            return

    # the ROM: bank 0 at p_rom, the rest in 16KB slots the host fills
    def set_slots(self, first_seg, last_seg):
        # a bank is addressed as S_ROMX:4000h with S_ROMX = slot - 400h, a
        # 16-bit segment: no slot may begin past 103FFh
        self.slots = [[s, None] for s in range(first_seg, min(last_seg - 0x3FF, 0x10400), 0x400)]

    def bank_service(self):
        view = self.view
        want = self.pr(P_BANK)
        if want == 0xFFFF:                # rdg_init's fill: what fits, the
            order = self.prefer or range(1, self.rom.banks)   # host's choice first
            for n in list(order)[:len(self.slots)]:
                self.map_bank(n)
            return
        self.map_bank(want // 2)

    def map_bank(self, n):
        view = self.view
        if n in self.lru:
            self.lru.move_to_end(n)
            return
        free = [s for s in self.slots if s[1] is None]
        if free:
            slot = free[0]
        else:
            old, _ = self.lru.popitem(last=False)
            slot = next(s for s in self.slots if s[1] == old)
            self.w16(view, self.sym["RDG_BTAB"] + 2 * old, 0)
        slot[1] = n
        self.lru[n] = slot
        self.w(slot[0], 0, self.rom.d[n * 0x4000:(n + 1) * 0x4000].ljust(0x4000, b"\xFF"))
        self.w16(view, self.sym["RDG_BTAB"] + 2 * n, slot[0] - 0x400)

    def init(self, mode, view, core, hash_, sega, segb, rom_seg, prf=0, prfmask=0, hmask=31,
             noc=0, core_image=None):
        self.view = view
        self.w(core, 0, core_image if core_image is not None else self.core_bin)
        self.w(rom_seg, 0, self.rom.d[:0x4000])
        self.p(P_VIEW, view)
        self.p(P_CORE, core)
        self.p(P_ROM, rom_seg)
        self.p(P_NBANKS, max(2, self.rom.banks))
        self.p(P_HASH, hash_)
        self.p(P_PRF, prf)
        self.p(P_PRFMASK, prfmask)
        self.p(P_SEGA, sega)
        self.p(P_SEGB, segb)
        self.p(P_MODE, mode, 1)
        self.p(P_HMASK, hmask, 1)
        self.p(P_NOC, noc, 1)
        self.lru.clear()
        for s in self.slots:
            s[1] = None
        self.enter(E_INIT)

    def frame(self, joy, budget=4000):
        self.w(self.view, self.sym["S_JOY"], [joy])
        self.p(P_BUDGET, budget)
        self.enter(E_FRAME)
        return self.pr(P_OUT)

    def serial(self):
        n = self.pr(0x2E)
        buf = self.r(DRV_SEG, self.pr(0x30), 1024)
        if n <= 1024:
            return buf[:n]
        k = n % 1024
        return buf[k:] + buf[:k]

    def state(self):
        """What two runs must agree on, frame by frame."""
        v, s = self.view, self.sym
        regs = self.r(v, s["S_AF"], 12)              # AF BC DE HL SP PC
        bp = struct.unpack("<h", self.r(v, s["S_BP"], 2))[0]   # "now", what the
        tn = struct.unpack("<I", self.r(v, s["S_TNEXT"], 4))[0]   #   game sees: where a
        timing = struct.pack("<I", (tn - bp) & 0xFFFFFFFF)    #   budget ended is not
        stats = self.r(v, s["S_SKIPPED"], 4) + self.r(v, s["S_EVCOUNT"], 2)
        mem = self.r(v, 0x8000, 0x8000)
        return regs, timing, stats, hashlib.sha1(mem).hexdigest()


def joy_script(f):
    """gbprof's platformer script, as tests/rdgcore/rdghost.asm's joy_script
    (S_JOY: Rt Lf Up Dn A B Se St from bit 0)."""
    j = 0x01
    if 150 <= f < 156 or 400 <= f < 406 or 700 <= f < 706:
        j |= 0x80
    if f % 50 < 14:
        j |= 0x10
    if f % 400 > 370:
        j |= 0x20
    return j


# --- translate --------------------------------------------------------------

def slot_of(pc, key, hmask):
    """tr_ekey's slot for a PC and its bank key (rt_preone), x 8."""
    bx = pc
    bl, bh = bx & 0xFF, bx >> 8
    bl ^= key
    bl ^= bh >> 3
    bh &= hmask
    return ((bh << 8) | bl) * 8


def translate(build, rom, entries, hmask=31, log=print, defines=(), rhm=7):
    """Every entry (bank, pc) translated, in rounds of two cache segments
    (the first round also fills the core's holes), the code's banks mapped a
    group at a time when they do not all fit. Returns the image."""
    m = Machine(build, rom, defines)
    s = m.sym
    CORE, VIEW, HASH, PRF, SEGA, SEGB, ROMSEG = 0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000, 0x7000
    BMP = 0x4800                           # the profile's segment's second half
    m.set_slots(0x7400, MEM_END // 16)
    m.prefer = sorted({b for b, pc in entries if pc >= 0x4000})
    keyed = [(pc, 0xFF if pc < 0x4000 else b) for b, pc in sorted(entries)]
    n = len(keyed)
    mask = 1
    while mask < n:
        mask <<= 1
    if mask > 8192:
        raise SystemExit("gbaot: %d block starts: the profile holds 8,192 here" % n)
    def bitmap(banks):
        """The block starts as a bitmap, so a block ends where another
        begins: bank 0's region and each of `banks` (14 at most)"""
        bmp = bytearray(0x100 + 0x800 * (1 + len(banks)))
        for i, k in enumerate(banks):
            bmp[k] = i + 1
        for pc, key in keyed:
            if key != 0xFF and not bmp[key]:
                continue
            base = 0x100 if key == 0xFF else 0x100 + 0x800 * bmp[key]
            o = pc & 0x3FFF
            bmp[base + (o >> 3)] |= 1 << (o & 7)
        m.w(BMP, 0, bmp.ljust(0x8000, b"\0"))
    m.p(P_BMP, BMP)
    m.init(2, VIEW, CORE, HASH, SEGA, SEGB, ROMSEG, prf=PRF, prfmask=mask - 1, hmask=hmask, noc=0)
    # the code's banks in groups that fit beside the translator: each group
    # mapped in turn, and only its entries (and bank 0's) offered
    width = min(len(m.slots), 14)          # (0x100 + 0x800 x 15 fits the 32KB)
    groups = [m.prefer[i:i + width] for i in range(0, len(m.prefer), width)] or [[]]
    segs = [None, None, None]              # the images, in order: 0 is the core
    live = {CORE: 0, SEGA: 1, SEGB: 2}     # the segments being written: image n
    blocks = {}                            # (pc, key) -> (image segment n, offset)
    dropped = set()
    rnd, cont, cleared = 0, False, False
    for gi, group in enumerate(groups):
        if gi:
            for sl in m.slots:             # the last group's banks out
                if sl[1] is not None:
                    m.w16(VIEW, s["RDG_BTAB"] + 2 * sl[1], 0)
                    sl[1] = None
            m.lru.clear()
            for k in group:
                m.map_bank(k)
        gset = set(group)
        bitmap(group)
        todo = {k: None for k in keyed if (k[1] == 0xFF and gi == 0) or k[1] in gset}
        while todo:
            prf = bytearray(mask * 4)
            for i, (pc, key) in enumerate(todo):
                struct.pack_into("<HBB", prf, i * 4, pc, key, 1)
            m.w(PRF, 0, prf)
            fresh = False
            if cont:
                m.enter(E_CONT)            # on where the last round stopped
            elif rnd:
                m.w(SEGA, 0, bytes(0x10000))
                m.w(SEGB, 0, bytes(0x10000))
                m.enter(E_ROUND)
                live = {SEGA: len(segs), SEGB: len(segs) + 1}
                segs += [None, None]
                fresh = True
            m.enter(E_PRELOAD)
            # what this round made: its entries out of the profile, its
            # segments named by token in the table, the images read out
            table = bytearray(m.r(HASH, 0, (hmask + 1) * 256 * 8))
            got = 0
            for e in range(0, len(table), 8):
                pc, key, cnt, off, seg = struct.unpack_from("<HBBHH", table, e)
                if off and seg in live:
                    struct.pack_into("<H", table, e + 6, TOKEN + live[seg])
                    blocks[(pc, key)] = (live[seg], off)
                    todo.pop((pc, key), None)
                    got += 1
            m.w(HASH, 0, table)
            for sg, idx in live.items():
                segs[idx] = m.r(sg, 0, 0x10000)
            log("gbaot: round %d: %d blocks translated (%d left)" % (rnd, got, len(todo)))
            rnd += 1
            if not todo:
                cleared = False
                cont = True                # room left: the next group goes on here
                continue
            # what is left went unmade for one of two reasons: the segments
            # filled, or its slot and the slot's neighbour hold blocks. The
            # table is only the translator's bookkeeping here - the host keeps
            # every block it made and builds the machine's table itself
            # (finish) - so a collision empties it and the round goes again
            # in the same segments; a full cache takes fresh ones
            def free(k):
                e = slot_of(k[0], k[1], hmask)
                return not (struct.unpack_from("<H", table, e + 4)[0] and
                            struct.unpack_from("<H", table, (e ^ 8) + 4)[0])
            if any(free(k) for k in todo):
                cleared, cont = False, False   # full: fresh segments
                if not got and fresh:
                    dropped |= set(todo)   # (fresh and still nothing: should not)
                    break
                continue
            if cleared and not got:
                dropped |= set(todo)       # (should not happen)
                break
            m.w(HASH, 0, bytes((hmask + 1) * 256 * 8))
            cleared, cont = True, True
    used_imgs = {n for n, _ in blocks.values()} | {0}
    while segs and (segs[-1] is None or len(segs) - 1 not in used_imgs):
        segs.pop()
    tails = {p << 8 for p in tailpages(build)}
    used = 0
    core0 = m.core_bin
    for i, sg in enumerate(segs):          # code bytes: in the core what is
        if i == 0:                         #   not its own any more, elsewhere
            used += sum(1 for a, b in zip(sg, core0) if a != b)   # what is
            continue                       #   not zero outside the tails
        for o in range(0, 0x10000, 256):
            if o in tails or o >= 0xFE00:
                continue
            used += sum(1 for x in sg[o:o + 256] if x)
    img = {"segs": segs, "blocks": blocks, "dropped": sorted(dropped), "entries": n,
           "code_bytes": used}
    finish(img, m.sym, rom, keyed, rhm)
    return img


def priorities(rom, keyed):
    """The order block starts claim the machine's table in: where a lookup
    is likeliest to come from first - the vectors, then the places a RET
    lands (the instruction after a CALL or RST), then the jump tables'
    words, then the rest - and what does not fit goes to the sorted list"""
    def rank(k):
        pc, key = k
        b = 0 if key == 0xFF else key
        if pc < 0x68 and pc % 8 == 0:
            return 0
        prev3 = rom.byte(b, pc - 3)
        prev1 = rom.byte(b, pc - 1)
        if prev3 == 0xCD or prev3 in G.CALLCC or prev1 in G.RSTS:
            return 1
        return 2
    return sorted(keyed, key=lambda k: (rank(k), k[1], k[0]))


def finish(img, sym, rom, keyed, rhm):
    """The machine's half of an image, made by the host:
      - the TABLE it runs with, (rhm + 1) x 256 entries, every block start
        placed by priority in its slot or the slot's neighbour (tr_ekey's
        two places), the rest in the LIST, sorted (rdgaot.inc);
      - every segment's three table masks (tr_hm0-2, rt_init's) made rhm;
      - every exit PRE-LINKED, as tr_link would on its first run - which
        also means a block the table could not hold costs a search only
        where the machine dispatches for itself (a RET, JP HL, a resume);
      - the far jumps among them as RELOCATIONS, image and offset, for the
        loader to give the segment;
      - one generation in every segment's FFF0h (16.2.3)."""
    blocks, segs = img["blocks"], [bytearray(x) for x in img["segs"]]
    table = bytearray((rhm + 1) * 256 * 8)
    listed = []
    for pc, key in priorities(rom, [k for k in keyed if k in blocks]):
        n, off = blocks[(pc, key)]
        e = slot_of(pc, key, rhm)
        for e2 in (e, e ^ 8):
            if not struct.unpack_from("<H", table, e2 + 4)[0]:
                struct.pack_into("<HBBHH", table, e2, pc, key, 0, off, TOKEN + n)
                break
        else:
            listed.append((key, pc, off, n))
    lst = bytearray()
    for key, pc, off, n in sorted(listed):
        lst += struct.pack("<HBBHH", pc, key, 0, off, TOKEN + n)
    for sg in segs:
        for name in ("RDGC_TR_HM0", "RDGC_TR_HM1", "RDGC_TR_HM2"):
            sg[sym[name]] = rhm
        struct.pack_into("<H", sg, 0xFFF0, 1)
    # pre-linking: an exit's site is `mov dx,SITE / jmp tr_lsite`, SITE its
    # own offset, then mov si,T at SITE + 6 (bank 0) or after seven spare
    # bytes at SITE + 13 (4000-7FFF) - rdgjit.inc's rt_exit
    lsite, sbank = sym["RDGC_TR_LSITE"], sym["S_BANK"]
    by_pc = collections.defaultdict(list)
    for (pc, key), v in blocks.items():
        by_pc[pc].append((key, v))
    import bisect
    starts = collections.defaultdict(list)  # image -> sorted (offset, key):
    for (pc, key), (n, off) in blocks.items():   # a site belongs to the
        starts[n].append((off, key))       #   nearest block start below it
    for v in starts.values():
        v.sort()
    relocs, linked, lazy = [], 0, 0
    for n, sg in enumerate(segs):
        i = sg.find(b"\xBA")
        while i != -1 and i < 0xFFF0:
            if (struct.unpack_from("<H", sg, i + 1)[0] == i and sg[i + 3] == 0xE9
                    and (i + 6 + struct.unpack_from("<h", sg, i + 4)[0]) & 0xFFFF == lsite):
                if sg[i + 6] == 0xBE:
                    t, at, bank = struct.unpack_from("<H", sg, i + 7)[0], i, None
                else:
                    t, at = struct.unpack_from("<H", sg, i + 14)[0], i + 8
                    k = bisect.bisect_right(starts[n], (i, 0x100)) - 1
                    src = starts[n][k][1] if k >= 0 else 0xFF
                    if src != 0xFF:          # a bank's code: the same bank (a
                        bank = src           #   switch leaves the block)
                    else:                    # bank 0's: the one bank that has it
                        cand = [kv for kv in by_pc.get(t, []) if kv[0] != 0xFF]
                        bank = cand[0][0] if len(cand) == 1 else -1
                tgt = None
                if t < 0x4000:
                    tgt = blocks.get((t, 0xFF))
                elif bank is not None and bank >= 0:
                    tgt = blocks.get((t, bank))
                if tgt is None:
                    lazy += 1               # left for tr_link to make at run time
                else:
                    if at != i:             # cmp byte [ss:S_BANK],B / jne +5
                        sg[i:i + 3] = b"\x36\x80\x3E"
                        struct.pack_into("<H", sg, i + 3, sbank)
                        sg[i + 5] = bank
                        sg[i + 6:i + 8] = b"\x75\x05"
                    tn, toff = tgt
                    if tn == n:
                        sg[at] = 0xE9
                        struct.pack_into("<H", sg, at + 1, (toff - (at + 3)) & 0xFFFF)
                    else:
                        sg[at] = 0xEA
                        struct.pack_into("<HH", sg, at + 1, toff, TOKEN + tn)
                        relocs.append((n, at + 3, tn))
                    linked += 1
            i = sg.find(b"\xBA", i + 1)
    img["segs"] = [bytes(x) for x in segs]
    img.update(table=bytes(table), list=bytes(lst), relocs=relocs, hmask=rhm,
               linked=linked, lazy=lazy, listed=len(listed))


def tailpages(build):
    t = open(os.path.join(aotdir(build), "rdgtmpl.bin"), "rb").read()
    sym = symbols(build)
    o, n = struct.unpack_from("<HH", t, sym["RDGT_HTAIL"])
    return list(t[o:o + n])


def save(img, out, rom):
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.startswith("seg") and f.endswith(".bin"):
            os.remove(os.path.join(out, f))
    for i, seg in enumerate(img["segs"]):
        open(os.path.join(out, "seg%02d.bin" % i), "wb").write(seg)
    open(os.path.join(out, "table.bin"), "wb").write(img["table"])
    open(os.path.join(out, "list.bin"), "wb").write(img["list"])
    meta = {"segs": len(img["segs"]), "hmask": img["hmask"], "entries": img["entries"],
            "blocks": len(img["blocks"]), "listed": img["listed"], "linked": img["linked"],
            "lazy": img["lazy"], "relocs": img["relocs"], "code_bytes": img["code_bytes"],
            "dropped": ["%02X:%04X" % (k, p) for p, k in img["dropped"]],
            "rom_sha256": hashlib.sha256(rom.d).hexdigest(), "header": rom.d[0x134:0x150].hex()}
    json.dump(meta, open(os.path.join(out, "aot.json"), "w"), indent=1)


def load(out):
    meta = json.load(open(os.path.join(out, "aot.json")))
    segs = [open(os.path.join(out, "seg%02d.bin" % i), "rb").read() for i in range(meta["segs"])]
    table = open(os.path.join(out, "table.bin"), "rb").read()
    meta["list"] = open(os.path.join(out, "list.bin"), "rb").read()
    return meta, segs, table


# --- run --------------------------------------------------------------------

def run_arm(build, rom, mode, frames, img=None, prove=False, defines=()):
    """Yields each frame's state: mode 0 the interpreter, 1 the dynamic
    recompiler, 3 the precompiled code in `img` (meta, segs, table)."""
    m = Machine(build, rom, defines)
    CORE, VIEW, HASH = 0x1000, 0x2000, 0x3000
    if mode == 3:
        meta, segs, table = img
        seg_at = [CORE] + [0x4000 + 0x1000 * i for i in range(len(segs) - 1)]
        LIST = seg_at[-1] + 0x1000 if len(segs) > 1 else 0x4000
        segs = [bytearray(x) for x in segs]
        for n, at, tn in meta["relocs"]:   # the far jumps' segments
            struct.pack_into("<H", segs[n], at, seg_at[tn])
        for i in range(1, len(segs)):
            m.w(seg_at[i], 0, segs[i])

        def reseg(b):
            t = bytearray(b)
            for e in range(0, len(t), 8):
                seg = struct.unpack_from("<H", t, e + 6)[0]
                if seg >= TOKEN and struct.unpack_from("<H", t, e + 4)[0]:
                    struct.pack_into("<H", t, e + 6, seg_at[seg - TOKEN])
            return t
        t = reseg(table)
        lst = reseg(meta["list"])
        m.w(HASH, 0, t)
        m.w(LIST, 0, lst)
        m.p(0x32, LIST)
        m.p(0x34, len(lst) // 8)
        romseg = LIST + (len(lst) + 15) // 16 + 1
        m.set_slots(romseg + 0x400, MEM_END // 16)
        m.init(3, VIEW, CORE, HASH, seg_at[1] if len(seg_at) > 1 else CORE, 0, romseg,
               hmask=meta["hmask"], core_image=bytes(segs[0]))
        if prove:                          # count what runs in the code segments:
            from unicorn import UC_HOOK_BLOCK  # the core's own handlers are
            m.ran = collections.Counter()   #   outside the holes the code is in
            code_ranges = [(sg * 16, sg * 16 + 0x10000) for sg in seg_at[1:]]

            entries = {}                    # a block's entry, linear -> its key
            for tb in (t, lst):
                for e in range(0, len(tb), 8):
                    pc, key, cnt, off, seg = struct.unpack_from("<HBBHH", tb, e)
                    if off:
                        entries[seg * 16 + off] = (pc, key)

            def blk(uc, addr, size, ud):
                m.ran["code"] += 1
                k = entries.get(addr)
                if k:
                    m.ran[k] += 1
            for lo, hi in code_ranges:
                m.u.hook_add(UC_HOOK_BLOCK, blk, begin=lo, end=hi - 1)
    else:
        SEGA, SEGB, romseg = 0x4000, 0x5000, 0x6000
        m.set_slots(romseg + 0x400, MEM_END // 16)
        m.init(mode, VIEW, CORE, HASH, SEGA, SEGB, romseg, hmask=31)
    for f in range(frames):
        x = m.frame(joy_script(f) if f else 0)   # (the harness's: no buttons in frame 0)
        yield f, x, m.state(), m


# --- commands ---------------------------------------------------------------

def cmd_cover(a):
    rom = G.Rom(open(a.rom, "rb").read())
    found, extra = walk(rom)
    lead = leaders(rom, found, extra)
    banks = collections.Counter(b for b, _ in found)
    print("%s: %d KB, %d banks" % (os.path.basename(a.rom), len(rom.d) // 1024, rom.banks))
    print("  %d instructions found, %d jump-table targets read, %d block starts" % (
        len(found), len(extra), len(lead)))
    print("  by bank: " + "  ".join("%02X: %d" % kv for kv in sorted(banks.items())))


def cmd_build(a):
    rom = G.Rom(open(a.rom, "rb").read())
    found, extra = walk(rom)
    lead = leaders(rom, found, extra, side=a.side)
    print("gbaot: %d instructions, %d block starts" % (len(found), len(lead)))
    img = translate(a.build, rom, lead, hmask=a.hmask, rhm=a.table // 2 - 1)
    save(img, a.out, rom)
    code = sum(len(s) for s in img["segs"])
    print("gbaot: %d blocks in %d segments (the core and %d more), %d dropped; %d code bytes, "
          "%.1f a Game Boy instruction found; table %dKB with %d in the list; %d exits linked, "
          "%d left to link; written to %s" % (
              len(img["blocks"]), len(img["segs"]), len(img["segs"]) - 1, len(img["dropped"]),
              img["code_bytes"], img["code_bytes"] / max(1, len(found)),
              len(img["table"]) // 1024, img["listed"], img["linked"], img["lazy"], a.out))


ARMS = {"interp": 0, "dyn": 1, "aot": 3}


def hottest(build, rom, img, frames=600):
    """The block entered most often in `frames` of the precompiled code"""
    for f, x, s1, m1 in run_arm(build, rom, 3, frames, img, prove=True):
        pass
    return max(((k, v) for k, v in m1.ran.items() if k != "code"), key=lambda kv: kv[1])


def broken(img, which):
    """`img` with one block's first byte made a different instruction: the
    NEGATIVE CONTROL, which must show"""
    meta, segs, table = img
    segs = list(segs)
    for e in range(0, len(table), 8):
        pc, key, cnt, off, seg = struct.unpack_from("<HBBHH", table, e)
        if off and "%02X:%04X" % (key, pc) == which.upper():
            sb = bytearray(segs[seg - TOKEN])
            sb[off] ^= 0x01
            segs[seg - TOKEN] = bytes(sb)
    return (meta, segs, table)


def compare(build, rom, img, frames, ref="interp", arm="aot", serial=False, defines=(),
            log=print):
    """Run two arms side by side. Returns (identical, what was found)."""
    r = run_arm(build, rom, ARMS[ref], frames, img if ref == "aot" else None, defines=defines)
    k = run_arm(build, rom, ARMS[arm], frames, img if arm == "aot" else None,
                prove=(arm == "aot"), defines=defines)
    m0 = m1 = None
    if serial:                            # a ROM that reports on its link port:
        for (f, x0, s0, m0), (_, x1, s1, m1) in zip(r, k):   # its words, not its
            pass                                               # frames
        t0, t1 = m0.serial().decode("latin-1"), m1.serial().decode("latin-1")
        tail = " ".join(t1.split())[-100:]
        return bool(t0) and t0 == t1, ("link port IDENTICAL: " if t0 == t1 else
                                       "link port DIFFERS: %s / " % " ".join(t0.split())[-60:]) + tail
    for (f, x0, s0, m0), (_, x1, s1, m1) in zip(r, k):
        if (x0, s0) != (x1, s1):
            what = [n for n, p, q in zip(("registers", "time", "events/skips", "memory"), s0, s1) if p != q]
            return False, "frame %d DIFFERS (%s)" % (f, ", ".join(what))
    ran = getattr(m1, "ran", collections.Counter())["code"]
    nbr = m1.r16(m1.view, m1.sym["S_JITNBR"])
    return True, "%d frames IDENTICAL, %s against %s; %d precompiled blocks entered, %d translated " \
        "while running" % (frames, arm, ref, ran, nbr)


def cmd_check(a):
    rom = G.Rom(open(a.rom, "rb").read())
    img = load(a.dir)
    if a.break_hot:
        (pc, key), n = hottest(a.build, rom, img, min(a.frames, 600))
        a.break_block = "%02X:%04X" % (key, pc)
        print("gbaot: the hottest block is %s, entered %d times" % (a.break_block, n))
    if a.break_block:
        img = broken(img, a.break_block)
        print("gbaot: block %s broken" % a.break_block)
    ok, what = compare(a.build, rom, img, a.frames, a.ref, a.arm, a.serial)
    print("gbaot: " + what)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--build", default=os.path.join(ROOT, "build"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cover")
    c.add_argument("rom")
    b = sub.add_parser("build")
    b.add_argument("rom")
    b.add_argument("-o", "--out", required=True)
    b.add_argument("--hmask", type=int, default=31, help="the TRANSLATOR's table mask")
    b.add_argument("--table", type=int, default=16, choices=(16, 32, 64),
                   help="KB of the table the machine runs with")
    b.add_argument("--side", action="store_true", help="a block at every resume point too")
    k = sub.add_parser("check")
    k.add_argument("rom")
    k.add_argument("dir")
    k.add_argument("-n", "--frames", type=int, default=1200)
    k.add_argument("--serial", action="store_true",
                   help="compare what the game says on its link port, not each frame")
    k.add_argument("--ref", default="interp", choices=("interp", "dyn", "aot"))
    k.add_argument("--arm", default="aot", choices=("interp", "dyn", "aot"))
    k.add_argument("--break-block", help="BB:PPPP: break this block on purpose (must go red)")
    k.add_argument("--break-hot", action="store_true", help="break the most entered block")
    a = ap.parse_args()
    return {"cover": cmd_cover, "build": cmd_build, "check": cmd_check}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
