#!/usr/bin/env python3
"""tests/pm2dma/hostcheck.py - by hand: python3 tests/pm2dma/hostcheck.py

Host check of tests/pm2dma's own logic: its 8237 programming, the card
command protocol, the page placement and the pattern check, against a model
of the 8237 and of the probe firmware's commands. Not the electrical question
(only the iron answers that) - whether the package would read a right answer
right, and a wrong one wrong."""
import os, re, subprocess, sys, tempfile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_INSN
from unicorn.x86_const import *

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def assemble(tmp):
    src = os.path.join(ROOT, "tests/pm2dma/pm2dma.asm")
    wrap, mapf, out = (os.path.join(tmp, n) for n in ("w.asm", "w.map", "w.bin"))
    open(wrap, "w").write("[map symbols %s]\n%%include \"%s\"\n" % (mapf, src))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", ROOT + "/apps/", "-I",
                    ROOT + "/tests/", "-o", out, wrap], check=True)
    syms = {}
    for line in open(mapf):
        m = re.match(r"\s*([0-9A-F]+)\s+([0-9A-F]+)\s+(\S+)\s*$", line)
        if m:
            syms[m.group(3)] = int(m.group(2), 16)
    return open(out, "rb").read(), syms

def p2d_byte(i):
    return ((i * 7 + 0x13) ^ (i >> 8)) & 0xFF

class Card:
    """The probe firmware's commands, and what its DRQ makes the 8237 do."""
    def __init__(self, behaviour):
        self.b = behaviour       # 'memw' drives on MEMW; 'gated' sees no IOR; 'slip' drives one late; 'none' no card
        self.status = 0
        self.dl = self.dh = 0
        self.lin = 0
        self.mode = 0
        self.ch = 0
        self.stat = [0] * 40
        self.drq = False
        self.start = self.end = 0
        self.testram = 0

    def cmd(self, c):
        d = self.dl | self.dh << 8
        if self.b == 'none':
            return
        if c == 0x0B:
            old = self.testram; self.testram = self.dl; self.dl = old
        elif c == 0xB0:
            self.lin = (self.lin & 0xF0000) | d
        elif c == 0xB1:
            self.lin = (self.lin & 0xFFFF) | (self.dl & 15) << 16
            self.mode = self.dh & 15; self.ch = (self.dh >> 4) & 3
        elif c == 0xB2:
            n = d or 0x10000
            self.stat = [0] * 40; self.stat[39] = 1
            self.start, self.end = self.lin, self.lin + n
            self.drq = True
        elif c == 0xB3:
            self.drq = False
        elif c == 0xB4:
            v = self.stat[self.dl] if self.dl < 40 else 0xFFFF
            self.dl, self.dh = v & 0xFF, v >> 8
        else:
            self.status = 3
            return
        self.status = 0

    def cycle(self, addr):
        """One write-transfer cycle at ADDR: the byte that lands in memory."""
        s = self.stat
        s[16 + 2] += 1                                   # it sees the MEMW
        if not (self.start <= addr < self.end):
            return 0xFF
        s[1] += 1
        i = addr - self.start
        if not s[5] and not s[6]:
            s[5], s[6] = addr & 0xFFFF, (addr >> 16) | 2 << 8
        s[7], s[8] = addr & 0xFFFF, (addr >> 16) | 2 << 8
        if self.mode == 1 and self.b in ('memw', 'slip'):
            s[0] += 1
            if s[0] == self.end - self.start:
                s[32] = 1
            return p2d_byte(i + (1 if self.b == 'slip' else 0))
        return 0xFF                                      # nothing drives: the bus floats

class Dma:
    def __init__(self, card, mem):
        self.card, self.mem = card, mem
        self.ff = 0
        self.addr = {1: 0, 3: 0}; self.cnt = {1: 0, 3: 0}; self.page = {1: 0, 3: 0}
        self.mode = {1: 0, 3: 0}; self.tc = 0
        self.jumper = 1

    def out(self, port, v):
        if port == 0x0C:
            self.ff = 0
        elif port in (2, 6, 3, 7):
            ch = 1 if port in (2, 3) else 3
            reg = self.addr if port in (2, 6) else self.cnt
            if self.ff == 0: reg[ch] = (reg[ch] & 0xFF00) | v
            else: reg[ch] = (reg[ch] & 0xFF) | v << 8
            self.ff ^= 1
        elif port == 0x83: self.page[1] = v
        elif port == 0x82: self.page[3] = v
        elif port == 0x0B: self.mode[v & 3] = v
        elif port == 0x0A:
            ch = v & 3
            if not v & 4 and ch == self.jumper and self.card.drq and ch in (1, 3):
                assert self.mode[ch] == 0x44 | ch, "mode %02x" % self.mode[ch]
                for k in range(self.cnt[ch] + 1):
                    a = self.page[ch] << 16 | ((self.addr[ch] + k) & 0xFFFF)
                    self.mem(a, self.card.cycle(a))
                self.tc |= 1 << ch

    def inp(self, port):
        if port == 0x08:
            v = self.tc; self.tc = 0; return v
        return 0xFF

def run(behaviour, seg, mode=1, ch=1, jumper=1):
    tmp = tempfile.mkdtemp()
    image, syms = assemble(tmp)
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x110000)
    base = seg * 16
    mu.mem_write(base, image)
    card = Card(behaviour)
    dma = Dma(card, lambda a, v: mu.mem_write(a, bytes([v])))
    dma.jumper = jumper

    def hin(uc, port, size, ud):
        if port == 0x2A0: return card.status
        if port == 0x2A1: return card.dl
        if port == 0x2A2: return card.dh
        return dma.inp(port)

    def hout(uc, port, size, val, ud):
        val &= 0xFF
        if port == 0x2A0:
            if card.status == 0 or val == 0:
                card.status = 1; card.cmd(val)
        elif port == 0x2A1: card.dl = val
        elif port == 0x2A2: card.dh = val
        else: dma.out(port, val)

    mu.hook_add(UC_HOOK_INSN, hin, None, 1, 0, UC_X86_INS_IN)
    mu.hook_add(UC_HOOK_INSN, hout, None, 1, 0, UC_X86_INS_OUT)
    HLT = 0xFFF0
    mu.mem_write(base + HLT, b"\xf4")

    def call(name):
        for r in (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS):
            mu.reg_write(r, seg)
        mu.reg_write(UC_X86_REG_SP, 0xFFE0)
        mu.mem_write(base + 0xFFE0, HLT.to_bytes(2, "little"))
        mu.reg_write(UC_X86_REG_SP, 0xFFE0)
        mu.emu_start(base + syms[name], base + HLT + 1, count=20_000_000)

    def w(name): return int.from_bytes(mu.mem_read(base + syms[name], 2), "little")
    mu.mem_write(base + syms["p2_ch"], bytes([ch]))
    mu.mem_write(base + syms["p2_mode"], bytes([mode]))
    mu.mem_write(base + syms["p2_rep"], b"\x01")
    call("p2_alive")
    alive = not (mu.reg_read(UC_X86_REG_EFLAGS) & 1)
    call("p2_place")
    lin = w("p2_lin") | int.from_bytes(mu.mem_read(base + syms["p2_lin"] + 2, 2), "little") << 16
    buf = w("p2_buf")
    call("p2_once")
    lines = []
    n = w("bl_nrow")
    for k in range(n):
        off = int.from_bytes(mu.mem_read(base + syms["bl_idx"] + 2 * k, 2), "little")
        raw = bytes(mu.mem_read(base + syms["bl_arena"] + off, 90))
        lines.append(raw.split(b"\0")[0].decode("latin1").rstrip())
    vals = {}
    for l in lines:
        m = re.match(r"(.{24})\s*(\d+)$", l)
        if m: vals[m.group(1).strip()] = int(m.group(2))
    return alive, lin, buf, syms["p2_area"], lines, vals

FAILS = []
def check(c, what):
    print(("  ok    " if c else "  FAIL  ") + what)
    if not c: FAILS.append(what)

print("a card that drives on MEMW, mode 1, channel 1")
alive, lin, buf, area, lines, v = run('memw', 0x2000)
check(alive, "the card answers CMD_Test_RAM")
check(lin == 0x20000 + area and buf == area, "the buffer is the area, linear %05X" % lin)
check(v.get("bytes right of 512") == 512, "512 right: %s" % v.get("bytes right of 512"))
check(v.get("first wrong (65535=none)") == 65535, "no first wrong")
check(v.get("card: driven") == 512 and v.get("card: count ran out") == 1, "the card's count")
check(v.get("TC after polls (0=none)", 0) > 0, "terminal count seen")
check(v.get("card: first addr low") == lin & 0xFFFF, "the first address the card saw is the buffer's")

print("the same on channel 3, jumper 3")
alive, lin, buf, area, lines, v = run('memw', 0x2000, ch=3, jumper=3)
check(v.get("bytes right of 512") == 512, "512 right on 3: %s" % v.get("bytes right of 512"))

print("the board gates the card out (mode 2): the bus floats")
alive, lin, buf, area, lines, v = run('gated', 0x2000, mode=2)
nff = sum(1 for i in range(512) if p2d_byte(i) == 0xFF)
check(v.get("bytes right of 512") == nff, "only the pattern's own FFh right: %s of %d" % (v.get("bytes right of 512"), nff))
check(v.get("bytes FFh") == 512, "512 FFh: %s" % v.get("bytes FFh"))
check(v.get("first wrong (65535=none)") == 0 and v.get("...wanted") == p2d_byte(0), "first wrong at 0, wanted the pattern")

print("BROKEN ON PURPOSE: a card one byte late - the row must not pass")
alive, lin, buf, area, lines, v = run('slip', 0x2000)
check(v.get("bytes right of 512", 512) < 512, "slip seen: %s right" % v.get("bytes right of 512"))

print("BROKEN ON PURPOSE: the jumper on the other channel - no TC")
alive, lin, buf, area, lines, v = run('memw', 0x2000, jumper=3)
check(v.get("TC after polls (0=none)") == 0, "no TC reported")
check(v.get("bytes still EEh") == 512, "the buffer untouched")

print("an area across a 64KB page edge is stepped past")
# find a segment where p2_area straddles: area + seg*16 crosses k*64K
tmp = tempfile.mkdtemp(); image, syms = assemble(tmp)
a = syms["p2_area"]
seg = ((0x30000 - a - 100) // 16)
alive, lin, buf, area, lines, v = run('memw', seg)
check((lin & 0xFFFF) + 511 <= 0xFFFF, "one page: linear %05X, buffer +%d" % (lin, buf - area))
check(v.get("bytes right of 512") == 512, "and still 512 right")

print("no card")
alive, *_ = run('none', 0x2000)
check(not alive, "no card answers")

print("FAILED: %d" % len(FAILS) if FAILS else "all passed")
sys.exit(1 if FAILS else 0)
