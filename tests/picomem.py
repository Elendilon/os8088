#!/usr/bin/env python3
"""THE PICOMEM, without one - SPEC.md 34.10.1 and 72.2.

    python3 tests/picomem.py [ne|sb]

No emulator in this tree has a PicoMEM, so this row runs the driver code that
talks to one - AS IT SHIPS, assembled from the tree - under an x86 core
(unicorn) whose port and interrupt hooks are a model of the card, written
from the firmware's own source (FreddyVRetro/ISA-PicoMEM, src/ne2000/ne2000.c
and the shipped src/rom/pmbios.bin's multiplexer, disassembled).

  ne  ETHER.DRV's 8390 core (tests/picomem/nehx.asm %includes ne2000.inc):
      probe, init, one transmit, two receives and thirty 900-byte frames
      round the ring, against TWO cards -
        * the PicoMEM's NE2000: an UN-DOUBLED PROM (so the pair test says
          8-bit) over the NE2000's packet memory, 32KB from 0x4000 - writes
          below it dropped, reads FFh. Must come out on the NE2000 map
          (ring 0x46..0x80) and move every frame byte for byte;
        * an EMPTY slot on a floating 8088 bus, answering AAh from the data
          window and C3h from the registers - what a 5150 showed as an
          NE2000 at AAAAAAAAAAAA. Must be REFUSED;
        * a genuine NE1000: 8KB at 0x2000. Must KEEP the NE1000 map
          (0x26..0x40) - the fix may not move a real card.
  sb  SOUND.DRV's PicoMEM attach (tests/picomem/sbhx.asm %includes
      picomem.inc, and sbl_f_irqdisc + its tables CUT OUT of sb.inc): with
      the card's own IRQ on 7 and on 5, pm_init must never offer that line,
      must learn it through PM BIOS function 0 (int 13h AX=6000h) and open
      its mask bit; sbl_f_irqdisc must then hook the SB on the line the card
      took WITHOUT the F2h probe (no DSP write, no tick read) and leave the
      multiplexer's vector exactly where the card's BIOS put it. And with no
      card at all: no write to 2A0h..2A2h, no int 13h, and discovery runs as
      it always did.

Broken on purpose (each measured): the old ne2000.inc puts the PicoMEM's
ring at 0x20 - the transmit comes from outside the card's RAM and every
receive lands outside it, which is the field report exactly (tx counted, rx
never); taking the %ifdef PICOMEM skip out of sbl_f_irqdisc makes the sb leg
FAIL on the probe running and the SB line never being hooked.

Needs nasm and the `unicorn` Python module (pip install unicorn).
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_INSN, \
        UC_HOOK_CODE, UC_HOOK_INTR
    from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT, \
        UC_X86_REG_SP, UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, \
        UC_X86_REG_SS, UC_X86_REG_IP, UC_X86_REG_AX, UC_X86_REG_BX, \
        UC_X86_REG_CX, UC_X86_REG_DX
except ImportError:
    print("SKIP: the unicorn module is not installed (pip install unicorn)")
    sys.exit(0)

SEG = 0x1000                    # the harness's CS=DS=ES=SS: clear of the IVT
BASE = SEG << 4                 # and the BIOS data area the code reads
FAILS = []


def check(cond, what):
    print(("  ok    " if cond else "  FAIL  ") + what)
    if not cond:
        FAILS.append(what)


def assemble(tmp, src, incs, name):
    """nasm `src` with a symbol map; returns (image, {symbol: offset})."""
    wrap = os.path.join(tmp, name + ".asm")
    mapf = os.path.join(tmp, name + ".map")
    with open(wrap, "w") as f:
        f.write("[map symbols %s]\n%%include \"%s\"\n" % (mapf, src))
    out = os.path.join(tmp, name + ".com")
    cmd = ["nasm", "-f", "bin", "-w+error"]
    for i in incs:
        cmd += ["-I", i.rstrip("/") + "/"]
    subprocess.run(cmd + ["-o", out, wrap], check=True)
    syms = {}
    for line in open(mapf):
        m = re.match(r"\s*([0-9A-F]+)\s+([0-9A-F]+)\s+(\S+)\s*$", line)
        if m:
            syms[m.group(3)] = int(m.group(2), 16)
    return open(out, "rb").read(), syms


class Box:
    """One 16-bit machine: the harness at SEG:0100, ports and int 13h hooked."""

    def __init__(self, image, syms, inb, outb, int13=None):
        self.syms = syms
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x100000)
        self.mu.mem_write(BASE + 0x100, image)
        self.int13_calls = 0

        def hin(uc, port, size, ud):
            return inb(port) & 0xFF

        def hout(uc, port, size, val, ud):
            outb(port, val & 0xFF)

        def hint(uc, intno, ud):
            if intno == 0x13 and int13:
                self.int13_calls += 1
                int13(self)

        def hcode(uc, addr, size, ud):
            if uc.mem_read(addr, 1) == b"\xf4":
                uc.emu_stop()
        self.mu.hook_add(UC_HOOK_INSN, hin, None, 1, 0, UC_X86_INS_IN)
        self.mu.hook_add(UC_HOOK_INSN, hout, None, 1, 0, UC_X86_INS_OUT)
        self.mu.hook_add(UC_HOOK_INTR, hint)
        self.mu.hook_add(UC_HOOK_CODE, hcode)

    def go(self, entry):
        mu = self.mu
        for r in (UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS):
            mu.reg_write(r, SEG)
        mu.reg_write(UC_X86_REG_SP, 0xFFF0)
        off = self.syms[entry] if isinstance(entry, str) else entry
        mu.emu_start(BASE + off, BASE + 0xFFFF, count=5_000_000)

    def rd(self, name, n=1):
        return bytes(self.mu.mem_read(BASE + self.syms[name], n))

    def b(self, name):
        return self.rd(name)[0]

    def w(self, name):
        return int.from_bytes(self.rd(name, 2), "little")

    def lin(self, addr, n):
        return bytes(self.mu.mem_read(addr, n))

    def put(self, addr, data):
        self.mu.mem_write(addr, data)


# =============================================================================
# leg ne - the 8390
# =============================================================================
class NIC:
    """The 8390 as the PicoMEM's ne2000.c behaves (or a real NE1000)."""

    def __init__(self, kind, mac):
        if kind == "picomem":           # BX_NE2K_MEMSTART 16K, MEMSIZ 32K
            self.memstart, self.memsize = 0x4000, 32 * 1024
            self.prom = bytes(mac) + bytes(6) + b"\x57" * 20
        else:                           # NE1000: 8KB at 0x2000
            self.memstart, self.memsize = 0x2000, 8 * 1024
            self.prom = bytes(mac) + bytes(8) + b"\x42\x42" + bytes(16)
        self.mem = bytearray(self.memsize)
        self.sent = []
        self.reset()

    def reset(self):
        self.stop, self.start, self.pg, self.rdma, self.isr = 1, 0, 0, 4, 0x80
        self.pstart = self.pstop = self.bnry = self.tpsr = self.tbcr = 0
        self.rstart = self.raddr = self.rbytes = self.curr = 0
        self.rcr = self.tcr = 0
        self.par = [0] * 6

    def chipr(self, a):
        if a < 32:
            return self.prom[a]
        if self.memstart <= a < self.memstart + self.memsize:
            return self.mem[a - self.memstart]
        return 0xFF

    def chipw(self, a, v):
        if self.memstart <= a < self.memstart + self.memsize:
            self.mem[a - self.memstart] = v

    def adv(self):
        self.raddr = (self.raddr + 1) & 0xFFFF
        if self.raddr == (self.pstop << 8):
            self.raddr = self.pstart << 8
        self.rbytes = max(0, self.rbytes - 1)
        if self.rbytes == 0:
            self.isr |= 0x40

    def inb(self, off):
        if off == 0x1F:
            self.reset()
            return 0xFF
        if off >= 0x10:
            v = self.chipr(self.raddr)
            self.adv()
            return v
        if off == 0:
            return (self.pg << 6) | (self.rdma << 3) | (self.start << 1) | self.stop
        if self.pg == 0:
            return {3: self.bnry, 7: self.isr, 8: self.raddr & 0xFF,
                    9: self.raddr >> 8}.get(off, 0)
        if self.pg == 1:
            if 1 <= off <= 6:
                return self.par[off - 1]
            if off == 7:
                return self.curr
        return 0

    def outb(self, off, v):
        if off == 0x1F:
            return
        if off >= 0x10:
            if self.rbytes:
                self.chipw(self.raddr, v)
                self.adv()
            return
        if off == 0:
            if v & 0x38 == 0:
                v |= 0x20
            if v & 1:
                self.isr |= 0x80
                self.stop = 1
            else:
                self.stop = 0
            self.rdma = (v & 0x38) >> 3
            if (v & 2) and not self.start:
                self.isr &= 0x7F
            self.start = 1 if v & 2 else 0
            self.pg = (v & 0xC0) >> 6
            if v & 4 and not self.tcr:
                a = self.tpsr * 256 - self.memstart
                ok = 0 <= a and a + self.tbcr <= self.memsize
                self.sent.append(bytes(self.mem[a:a + self.tbcr]) if ok else None)
                self.isr |= 0x02
            return
        if self.pg == 0:
            if off == 1:
                self.pstart = v
            elif off == 2:
                self.pstop = v
            elif off == 3:
                self.bnry = v
            elif off == 4:
                self.tpsr = v
            elif off == 5:
                self.tbcr = (self.tbcr & 0xFF00) | v
            elif off == 6:
                self.tbcr = (self.tbcr & 0xFF) | (v << 8)
            elif off == 7:
                self.isr &= ~(v & 0x7F)
            elif off == 8:
                self.rstart = (self.rstart & 0xFF00) | v
                self.raddr = self.rstart
            elif off == 9:
                self.rstart = (self.rstart & 0xFF) | (v << 8)
                self.raddr = self.rstart
            elif off == 10:
                self.rbytes = (self.rbytes & 0xFF00) | v
            elif off == 11:
                self.rbytes = (self.rbytes & 0xFF) | (v << 8)
            elif off == 12:
                self.rcr = v
            elif off == 13:
                self.tcr = (v & 6) >> 1
        elif self.pg == 1:
            if 1 <= off <= 6:
                self.par[off - 1] = v
            elif off == 7:
                self.curr = v

    def rx_frame(self, buf):
        """ne2000.c's ne2000_rx_frame, with its pointer arithmetic."""
        if self.stop or self.pstart == 0:
            return "stopped"
        n = len(buf)
        pages = (n + 4 + 4 + 255) // 256
        if self.curr < self.bnry:
            avail = self.bnry - self.curr
        else:
            avail = (self.pstop - self.pstart) - (self.curr - self.bnry)
        if avail <= pages:
            return "full"
        if buf[:6] != b"\xff" * 6 and buf[:6] != bytes(self.par):
            return "filtered"
        nxt = self.curr + pages
        if nxt >= self.pstop:
            nxt -= self.pstop - self.pstart
        data = bytes([0x01, nxt, (n + 4) & 0xFF, (n + 4) >> 8]) + buf
        start = self.curr * 256 - self.memstart
        if start < 0:
            return "outside the card's RAM"
        if nxt > self.curr or self.curr + pages == self.pstop:
            self.mem[start:start + len(data)] = data
        else:
            end = (self.pstop - self.curr) * 256
            self.mem[start:start + end] = data[:end]
            ps = self.pstart * 256 - self.memstart
            self.mem[ps:ps + len(data) - end] = data[end:]
        self.curr = nxt
        self.isr |= 0x01
        return "ok"


def leg_ne(tmp):
    image, syms = assemble(tmp, os.path.join(HERE, "picomem", "nehx.asm"),
                           [os.path.join(ROOT, "drivers", "ether"),
                            os.path.join(ROOT, "drivers")], "nehx")
    mac = [0x28, 0xCD, 0xC1, 0x01, 0x02, 0x03]
    for kind, want in (("picomem", (1, 0x40, 0x46, 0x80)),
                       ("ne1000", (0, 0x20, 0x26, 0x40))):
        print("ne: %s" % kind)
        nic = NIC(kind, mac)
        box = Box(image, syms,
                  lambda p: nic.inb(p - 0x300) if 0x300 <= p < 0x320 else 0xFF,
                  lambda p, v: nic.outb(p - 0x300, v) if 0x300 <= p < 0x320
                  else None)
        box.go(0x100)
        got = (box.b("eth_word"), box.b("eth_txpg"), box.b("eth_pstart"),
               box.b("eth_pstop"))
        check(box.w("res_flags") & 1 == 0, "probe finds the card")
        check(box.rd("eth_mac", 6) == bytes(mac), "MAC read from the PROM")
        check(got == want, "map word=%d tx=%02X ring=%02X..%02X (want %d %02X "
              "%02X..%02X)" % (got + want))
        check(bytes(nic.par) == bytes(mac) and (nic.pstart, nic.pstop) ==
              want[2:], "the card was programmed with it")

        frame = bytes(range(100))
        box.put(BASE + syms["eth_txb"], frame)
        box.go("entry_tx")
        check(nic.sent[-1:] == [frame], "a transmit puts the frame on the wire")

        bad = []
        frames = [b"\xff" * 6 + bytes(8) + bytes((j * 7) & 0xFF for j in range(300)),
                  bytes(mac) + bytes(8) + bytes((j * 3) & 0xFF for j in range(300))]
        frames += [b"\xff" * 6 + bytes(8) + bytes((k * 13 + j) & 0xFF
                                                  for j in range(900))
                   for k in range(30)]
        for k, f in enumerate(frames):
            r = nic.rx_frame(f)
            box.go("entry_rx")
            n = box.w("res_len")
            ok = (r == "ok" and box.w("res_flags") & 1 == 0 and
                  box.lin(BASE + syms["eth_rxb"], n)[:len(f)] == f)
            if not ok:
                bad.append("frame %d: card %s" % (k, r))
                break
        check(not bad, "broadcast, unicast and 30 x 900 bytes round the ring "
              "arrive intact%s" % ((" - " + bad[0]) if bad else ""))

    # AN EMPTY SLOT. An 8088's undriven bus answers with a byte it carried a
    # moment before - an instruction the prefetcher fetched, or what the last
    # store wrote - so which byte depends on bus timing this model cannot
    # reproduce. It takes the shape the FIELD showed instead (FIELD-NOTES 66):
    # the data window answering AAh (`stosb`, and the byte each stosb then
    # writes back) and the register file a byte with bit 7 set (C3h, `ret`),
    # which passed RST and the PROM tests as an NE2000 at AAAAAAAAAAAA.
    print("ne: an empty slot (the floating 8088 bus the 5150 showed)")
    box = Box(image, syms,
              lambda p: (0xAA if p - 0x300 >= 0x10 else 0xC3)
              if 0x300 <= p < 0x320 else 0xFF,
              lambda p, v: None)
    box.go(0x100)
    check(box.w("res_flags") & 1 == 1, "an empty slot is NOT a card (probe "
          "CF=%d, MAC %s)" % (box.w("res_flags") & 1, box.rd("eth_mac", 6).hex()))


# =============================================================================
# leg sb - the attach and the IRQ
# =============================================================================
def sbslice(tmp):
    """sb.inc's candidate tables and sbl_f_irqdisc, cut out as they ship."""
    src = open(os.path.join(ROOT, "drivers", "sound", "sb.inc")).read().splitlines()
    out, take = [], False
    for line in src:
        if line.startswith("sbl_dsc_irqn:") or line.startswith("sbl_f_irqdisc:"):
            take = True
        if take:
            out.append(line)
            if line.startswith("SBL_DSC_N"):
                take = False
            elif out and out[0] != line and line.startswith("; ====") and \
                    any(l.startswith("sbl_f_irqdisc:") for l in out):
                out.pop()
                take = False
    assert any(l.startswith("sbl_f_irqdisc:") for l in out), "slice lost"
    with open(os.path.join(tmp, "sbslice.inc"), "w") as f:
        f.write("\n".join(out) + "\n")


BIOS = 0xC800                   # the PM BIOS segment int 13h reports
PMVEC = 0x2C16                  # the multiplexer's offset in the shipped ROM
DEFVEC = (0xFF53, 0xF000)       # what the ROM leaves on a line nobody hooked


def leg_sb(tmp):
    sbslice(tmp)
    image, syms = assemble(tmp, os.path.join(HERE, "picomem", "sbhx.asm"),
                           [os.path.join(ROOT, "drivers", "sound"), tmp],
                           "sbhx")
    for pmirq in (7, 5, None):
        print("sb: %s" % ("PicoMEM on IRQ %d" % pmirq if pmirq else
                          "no PicoMEM in the machine"))
        st = {"pic": 0xFF, "ramp": 0x37, "args": [0, 0], "cmds": [],
              "pmw": 0}

        def inb(p):
            if p == 0x21:
                return st["pic"]
            if pmirq and p == 0x2A3:
                st["ramp"] = (st["ramp"] + 1) & 0xFF
                return st["ramp"]
            if pmirq and p == 0x2A0:
                return 0            # READY
            if pmirq and p in (0x2A1, 0x2A2):
                return st["args"][p - 0x2A1]
            return 0xFF

        def outb(p, v):
            if p == 0x21:
                st["pic"] = v
            elif 0x2A0 <= p <= 0x2A2:
                st["pmw"] += 1
                if not pmirq:
                    return
                if p != 0x2A0:
                    st["args"][p - 0x2A1] = v
                    return
                arg = st["args"][0] | (st["args"][1] << 8)
                st["cmds"].append((v, arg))
                ans = 0
                if v == 0x77 and (arg & 0xFF) == pmirq:
                    ans = 1         # dev_sbdsp_set_irq_dma refuses BV_IRQ
                st["args"] = [ans & 0xFF, ans >> 8]

        def int13(box):
            mu = box.mu
            if mu.reg_read(UC_X86_REG_AX) == 0x6000 and \
                    mu.reg_read(UC_X86_REG_DX) == 0x1234:
                mu.reg_write(UC_X86_REG_AX, 0x2A0)
                mu.reg_write(UC_X86_REG_BX, BIOS)
                mu.reg_write(UC_X86_REG_CX, (pmirq << 8) | 0x0F)
                mu.reg_write(UC_X86_REG_DX, 0xAA55)

        box = Box(image, syms, inb, outb, int13 if pmirq else None)
        for line in (3, 5, 7):          # the IVT the ROMs left
            cell = (8 + line) * 4
            vec = (PMVEC, BIOS) if line == pmirq else DEFVEC
            box.put(cell, vec[0].to_bytes(2, "little") + vec[1].to_bytes(2, "little"))
        box.put(0x46C, b"\0\0")
        box.go(0x100)

        if not pmirq:
            check(st["pmw"] == 0, "no PicoMEM: not one write to 2A0h..2A2h")
            check(box.int13_calls == 0, "no PicoMEM: no int 13h AX=6000h")
            check(box.b("pm_up") == 0, "no PicoMEM: pm_up stays 0")
            box.go("entry_disc")
            check(box.b("res_dspwr") > 0,
                  "no PicoMEM: discovery runs as it always did (F2h issued)")
            continue

        sb_irq = 5 if pmirq == 7 else 7
        offered = [a & 0xFF for c, a in st["cmds"] if c == 0x77]
        check(box.b("pm_up") == 1, "the DSP was enabled")
        check(box.b("pm_pmirq") == pmirq, "the card's own line learned from "
              "PM BIOS function 0 (%d)" % box.b("pm_pmirq"))
        check(pmirq not in offered, "the card's own line never offered to "
              "the SB (offered %s)" % offered)
        check(box.b("pm_irq") == sb_irq, "the SB took IRQ %d" % box.b("pm_irq"))
        check(st["pic"] & (1 << pmirq) == 0, "the card's line is UNMASKED")

        box.go("entry_disc")
        cell = lambda n: (int.from_bytes(box.lin((8 + n) * 4, 2), "little"),
                          int.from_bytes(box.lin((8 + n) * 4 + 2, 2), "little"))
        check(box.b("res_al") == 1 and box.b("sbl_irq") == sb_irq,
              "sbl_f_irqdisc answers IRQ %d" % box.b("sbl_irq"))
        check(box.b("res_dspwr") == 0 and box.b("res_ticks") == 0,
              "...without the F2h probe (DSP writes %d, tick reads %d)"
              % (box.b("res_dspwr"), box.b("res_ticks")))
        check(cell(sb_irq) == (syms["sbl_isr"], SEG),
              "sbl_isr is on IRQ %d's vector" % sb_irq)
        check(cell(pmirq) == (PMVEC, BIOS),
              "the multiplexer's vector is untouched (%04X:%04X)"
              % (cell(pmirq)[1], cell(pmirq)[0]))
        check(st["pic"] & ((1 << pmirq) | (1 << sb_irq)) == 0,
              "both lines open at the 8259 (mask %02X)" % st["pic"])
        check(box.rd("sbl_oldvec", 4) == DEFVEC[0].to_bytes(2, "little") +
              DEFVEC[1].to_bytes(2, "little"), "the SB line's old vector saved")


def main():
    legs = sys.argv[1:] or ["ne", "sb"]
    with tempfile.TemporaryDirectory() as tmp:
        if "ne" in legs:
            leg_ne(tmp)
        if "sb" in legs:
            leg_sb(tmp)
    if FAILS:
        print("picomem: FAIL (%d)" % len(FAILS))
        return 1
    print("picomem: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
