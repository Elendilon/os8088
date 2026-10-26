#!/usr/bin/env python3
"""kern_mega under 86Box, behind MartyPC's `Marty` API - the second backend
of the port mechanism (docs/86BOX.md, "kern_mega rows on 86Box"; the first
is tools/os88bochsmarty.py, docs/BOCHS.md "Rows ported from MartyPC").

    OS88_MEGA=1 OS88_MEGA_EMU=86box python3 tests/<row>.py

With both set, `os88marty.launch()` answers a `BoxMarty`: a SERVER for the
debug-server requests `Marty` is built on (`cmd(**kw)`), answered out of an
86Box (tools/os88box.py: its automation socket and its GDB stub). So
os88ui, os88mouse, `until`/`settle`/`ui_done` and every row above them run
on it unchanged, as they do on Bochs.

WHY A SECOND BACKEND: 86Box models the HARDWARE Bochs does not - a CGA, a
Hercules, an MDA, TWO video cards at once (an extended desktop across a
seam), a Sound Blaster whose DMA runs on the emulated clock, 5.25" 1.2MB
drives, an AT BIOS taking the 286's reset path. Bochs is a 386 with one VGA
and an SB16 that drains several times too fast. The disk mapping, selectors,
`.cold`/`.mega` symbols and the boot toast are tools/os88megacommon.py's,
shared with Bochs.

THE MACHINE is vm/mega-port - the owner's mr286 (MR BIOS 286, 16 MHz, 4MB,
a serial mouse on COM1, an ISA IDE controller) with its CMOS SEEDED from
vm/mega-port/nvr-seed, so no boot stops in BIOS setup - and what the row's
MartyPC machine name says it has is added to it ($OS88_MEGA_VM names another
vm/ profile; `machine_config` is the mapping):

    both          a CGA and a Hercules (os8088_5150_both*: the extended
                  desktop's pair), monitor 0 and 1
    vga_herc      a VGA (OTI-067) and a Hercules; vga_mda: and an MDA
    herc / cga    that card alone; xt_vga / vga: the VGA; ega: an EGA
    (no adapter)  a CGA - MartyPC's default machine is os8088_5150_cga
    _sb           a Sound Blaster 2.0 at 220h on IRQ 7, DMA 1, as MartyPC's
                  (SB DSP 2.1 on IRQ 7 + an AdLib, which the SB2.0's OPL2 is);
                  $OS88_MEGA_SND=sb16 (or sb16:IRQ) for an SB16 instead
    _ne2k         an NE2000 at 300h on IRQ 10, on slirp ($OS88_BOCHS_NE2K too)
    _hdd          the row's own fixed disk on the IDE controller (row_disk)

and a floppy drive's TYPE follows its image (a 360KB or 1.2MB image gets a
5.25" 1.2MB drive, anything else a 3.5" 1.44MB one), CMOS included.

THE CLOCK IS THE GUEST'S, as on MartyPC. Running is 86Box released with
fast-forward on (unpaced, ~10x a real 286 at an idle desktop here); paused
is `hold`, and `advance` is an exact `step` of emulated milliseconds.
`status()["cycles"]` is emulated time at 4.77 MHz (GUEST_HZ), so every guest
budget in os88marty means the same seconds of machine time it means there -
86Box is NOT cycle-accurate (docs/86BOX.md), so a cycle COUNT is not a
measurement here, and the 1 ms quantum is its resolution.

WHAT IT MAPS
  * memory: `read`/`write` are PHYSICAL (memr/memw - paging is off);
    `readseg`/`lin` resolve a selector through kern_mega's own tables
    ([mega_gdtr], the LDT's descriptor at GDT 18h) - automation has no sreg.
  * registers: `regs` is automation's; `setreg`/`park` go through the GDB
    stub's `P` (IF and every segment register included - Bochs could not).
  * breakpoints: `exec`/`execseg`/`int` are the stub's HARDWARE breakpoints
    (Z1), linear and unlimited in number; `int` is the vector's handler (the
    IDT's gate in protected mode). A hit stops the CPU before the instruction
    runs; resuming executes it (86Box checks after each instruction, so the
    stop just left is not re-hit). `mem`/`io` are refused.
  * keys: set-1 scancodes through automation; the mouse: relative packets
    into the serial mouse, which os88mouse closes the loop on.
  * the glass: `fbuf(card)` is the card's last frame (monitor 0 is the
    config's first card, 1 its second - tools/86box/patches/05), `vram()`
    reads B8000/B0000 directly, `screen()` automation's text rows.
  * sound: with $MARTYPC_WAV set at launch the Sound Blaster's DAC output is
    written to <it>.sound_blaster.wav (tools/86box/patches/04), MartyPC's
    per-card capture, sample-and-held at 48 kHz on the emulated clock.
  * disks: `disks()` names the image AS MOUNTED (copied at launch); `flush`
    copies the live one (86Box writes a floppy through, a track at a time);
    `mount` loads another image into the drive (`fdd load`); `reset` is a
    hard reset; `disk()` (the FDC counters) is refused - 86Box keeps none.
  * refused by name: flicker, pace, snapshot/restore, planes, inb/outb,
    wheel, history.
"""
import atexit
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import os88box as ob           # noqa: E402
import os88marty as om         # noqa: E402
from os88megacommon import (MegaMixin, mega_images,  # noqa: E402
                            row_disk, _blank)

GUEST_HZ = om.GUEST_HZ
PROFILE = "mega-port"

# W3C KeyboardEvent.code (MartyKey's names) -> set-1 scancode (0x100 = E0)
_SCAN = {
    "Enter": 0x1C, "Escape": 0x01, "Backspace": 0x0E, "Tab": 0x0F,
    "Space": 0x39, "ArrowUp": 0x148, "ArrowDown": 0x150,
    "ArrowLeft": 0x14B, "ArrowRight": 0x14D, "Home": 0x147, "End": 0x14F,
    "PageUp": 0x149, "PageDown": 0x151, "Insert": 0x152, "Delete": 0x153,
    "ShiftLeft": 0x2A, "ShiftRight": 0x36, "ControlLeft": 0x1D,
    "ControlRight": 0x11D, "AltLeft": 0x38, "AltRight": 0x138,
    "CapsLock": 0x3A, "NumLock": 0x45, "ScrollLock": 0x46,
    "Minus": 0x0C, "Equal": 0x0D, "BracketLeft": 0x1A, "BracketRight": 0x1B,
    "Backslash": 0x2B, "Semicolon": 0x27, "Quote": 0x28, "Backquote": 0x29,
    "Comma": 0x33, "Period": 0x34, "Slash": 0x35,
    "NumpadEnter": 0x11C, "NumpadAdd": 0x4E, "NumpadSubtract": 0x4A,
    "NumpadMultiply": 0x37, "NumpadDivide": 0x135, "NumpadDecimal": 0x53,
}
for _i, _n in enumerate("789", 0x47):
    _SCAN["Numpad" + _n] = _i
for _i, _n in enumerate("456", 0x4B):
    _SCAN["Numpad" + _n] = _i
for _i, _n in enumerate("123", 0x4F):
    _SCAN["Numpad" + _n] = _i
_SCAN["Numpad0"] = 0x52
for _i in range(10):
    _SCAN["F%d" % (_i + 1)] = 0x3B + _i
_SCAN["F11"], _SCAN["F12"] = 0x57, 0x58


def scancode(name):
    if name in _SCAN:
        return _SCAN[name]
    if name.startswith("Key") and len(name) == 4:
        return ob.KEYS[name[3].lower()]
    if name.startswith("Digit") and len(name) == 6:
        return ob.KEYS[name[5]]
    raise om.MartyError("os88boxmarty: no scancode for MartyKey %r" % name)


# --- the machine a row's MartyPC name describes --------------------------------

# 86Box's card -> (MartyPC's `type`, the 1bpp kind `vram` takes or None)
_CARDS = {"cga": ("cga", "cga"), "hercules": ("mda", "herc"), "vga": ("vga", None),
          "mda": ("mda", "herc"), "oti067": ("vga", None),
          "ega": ("ega", None)}


def machine_config(machine):
    """What MartyPC machine NAME has, as 86Box config lines: ([(section, key,
    value)], [card, ...], {"display": 0x14 bits, "snd": name or None}).
    See the module note for the table."""
    n = (machine or "").lower()
    if "both" in n:                     # `_mono`: the Hercules is primary
        cards = ["hercules", "cga"] if "mono" in n else ["cga", "hercules"]
    elif "vga_herc" in n:
        cards = ["vga", "hercules"]
    elif "vga_mda" in n:
        cards = ["vga", "mda"]
    elif "herc" in n:
        cards = ["hercules"]
    elif "ega" in n:
        cards = ["ega"]
    elif "vga" in n:
        cards = ["oti067"]
    else:
        cards = ["cga"]
    sets = [("Video", "gfxcard", cards[0]),
            ("Video", "gfxcard_2", cards[1] if len(cards) > 1 else None)]
    snd = None
    if "_sb" in n or os.environ.get("OS88_MEGA_SND"):
        snd = os.environ.get("OS88_MEGA_SND") or "sb2.0"
        kind, _, irq = snd.partition(":")
        sec = {"sb2.0": "Sound Blaster v2.0 #1",
               "sb16": "Sound Blaster 16 #1"}.get(kind)
        if sec is None:
            raise om.MartyError("os88boxmarty: $OS88_MEGA_SND %r is neither "
                                "sb2.0 nor sb16" % snd)
        sets += [("Sound", "sndcard", kind), (sec, "base", "0220"),
                 (sec, "irq", irq or ("7" if kind == "sb2.0" else "5")),
                 (sec, "dma", "1")]
        if kind == "sb16":
            sets.append((sec, "dma16", "5"))
    if "_ne2k" in n or os.environ.get("OS88_BOCHS_NE2K"):
        sets += [("Network", "net_01_card", "ne2k"),
                 ("Network", "net_01_net_type", "slirp"),
                 ("Network", "net_01_link", "0"),
                 ("NE2000 #1", "base", "0300"), ("NE2000 #1", "irq", "10")]
    # the CMOS equipment byte's display bits: EGA/VGA 00, CGA 80 col 10,
    # monochrome 11 - what the PRIMARY is, or MR BIOS stops at POST
    disp = {"cga": 0x20, "hercules": 0x30, "mda": 0x30}.get(cards[0], 0x00)
    return sets, cards, {"display": disp, "snd": snd}


_FDTYPE = {368640: ("525_2hd", 2), 1228800: ("525_2hd", 2),
           737280: ("35_2hd", 4), 1474560: ("35_2hd", 4)}


def cmos_seed(profile, a, b, display):
    """The profile's seeded CMOS (vm/<profile>/nvr-seed/), with the floppy
    types (0x10), the equipment byte's display bits (0x14) and the checksum
    (0x2E-0x2F, over 0x10-0x2D) made to agree with THIS machine. {} when the
    profile carries no seed."""
    d = os.path.join(ROOT, "vm", profile, "nvr-seed")
    out = {}
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else ():
        c = bytearray(open(os.path.join(d, f), "rb").read())
        if len(c) == 128 and f == "mr286.nvr":
            # (a drive with NO image is still a drive - MartyPC's `_hdd`
            # machines keep theirs, empty - so it is a 1.44MB one)
            ta = _FDTYPE.get(os.path.getsize(a), (None, 4))[1] if a else 4
            tb = _FDTYPE.get(os.path.getsize(b), (None, 4))[1] if b else 4
            c[0x10] = ta << 4 | tb
            c[0x14] = (c[0x14] & ~0x30) | display
            s = sum(c[0x10:0x2E])
            c[0x2E], c[0x2F] = s >> 8 & 0xFF, s & 0xFF
        out[f] = bytes(c)
    return out


def _setup(bx, mono, hdd=False, guest_ms=20000):
    """The priming boot's way through MR BIOS: POST's *"Press Any Key"*
    takes it into SETUP, and F10 there records what it found. A machine
    whose PRIMARY is a monochrome card (`both_gla_mono`: the Hercules first)
    also has its Video page's *Primary Video* stepped to *Monochrome* -
    detection prefers the colour card, and a BIOS that initialised the CGA
    hands os8088 an equipment word saying so (kernel/viddet.inc's .equip),
    so the kernel would take the CGA for its primary. A machine with a
    FIXED DISK has C: made type 47 and its geometry IDENTIFIED off the drive
    (the Fixed-Disk page's `?`): no listed type is a VHD's 615/4/26, and a
    BIOS translating at a type's 17 sectors would read the wrong sectors.
    Each page is found by pressing Right until its text is on the screen."""
    def text():
        return bx.screen_text() or ""

    def page(word):
        for _ in range(12):
            if word in text():
                return
            bx.tap("right")
            bx.cmd("step 300")
        raise SystemExit("os88boxmarty: MR BIOS setup has no %r page" % word)

    def keys(*ks):
        for k in ks:
            bx.tap(k)
            bx.cmd("step 300")
    t0 = bx.ms()
    while bx.ms() - t0 < guest_ms:
        t = text()
        if "Summary   Energy" in t:
            break
        if "Press Any Key" in t:
            bx.tap("esc")
        bx.cmd("step 250")
    else:
        return                          # no setup at all: nothing to record
    if hdd:
        page("Fixed Disk 80")
        keys("down", "return", "4", "7", "return", "down", "shift+/")
        if "Type .......... 47" not in text():
            raise SystemExit("os88boxmarty: MR BIOS would not take C: as an "
                             "identified type 47")
    if mono:
        page("Primary Video")
        bx.tap("down")
        bx.cmd("step 300")
        for _ in range(4):
            if "Monochrome" in text():
                break
            bx.tap("space")
            bx.cmd("step 300")
        if "Monochrome" not in text():
            raise SystemExit("os88boxmarty: MR BIOS's Video page offers no "
                             "Monochrome primary")
    for _ in range(4):                  # out of the fields: F10 is the MENU's
        if "Summary   Energy" in text():
            break
        keys("esc")
    bx.tap("f10")


def cmos_primed(profile, a, b, sets, nvr, mono=False, c=None):
    """THE CMOS THIS MACHINE'S BIOS ACCEPTS WITHOUT A WORD. The seed is the
    VGA machine's; a CGA, a Hercules (whose card carries an LPT port), an
    SB, a fixed disk each make MR BIOS stop at POST on *"... Configuration
    Change - Press Any Key"* and then record the new configuration. So the
    first boot of each configuration is a PRIMING boot, held, answering
    those prompts (BIOS_PROMPTS) up to os8088's desktop, and what 86Box
    saves at the power-off is cached under build/86box/nvrcache/ by a hash
    of the configuration and the seed: every later launch of the same
    machine POSTs straight through, as MartyPC's does, so a row launched
    paused at power-on (`boot=False`) runs the BIOS with nobody to answer
    it. The shutdown byte (0Fh, which kern_mega's 286 reset path writes) is
    cleared, so a power-on is never taken for a warm reset."""
    import hashlib
    if not nvr:
        return nvr
    h = hashlib.sha1(json.dumps([profile, sets, mono], sort_keys=True).encode())
    for f in sorted(nvr):
        h.update(f.encode() + nvr[f])
    d = os.path.join(ROOT, "build", "86box", "nvrcache", h.hexdigest()[:16])
    if os.path.isdir(d) and all(os.path.exists(os.path.join(d, f))
                                for f in nvr):
        return {f: open(os.path.join(d, f), "rb").read() for f in nvr}
    name = "prime-%s-%d" % (h.hexdigest()[:8], os.getpid())
    bx = ob.launch(profile, name=name, hold=True, fresh=True, a=a, b=b,
                   c=c, cfgs=sets, temp=True, nvr=nvr, eject_a=not a,
                   kmap=os.path.join(os.environ.get("OS88_MEGA_BUILD")
                                     or os.path.join(ROOT, "build"),
                                     "megak", "kernel.map"))
    try:
        _setup(bx, mono, hdd=bool(c))
        bx.kernel_up(guest_ms=240000, prompts=BIOS_PROMPTS, idle=False)
    except SystemExit as e:
        bx.quit(remove=True)
        raise om.MartyError("os88boxmarty: the priming boot of this machine "
                            "never reached the desktop: %s" % e)
    bx.quit()
    out = {}
    for f in nvr:
        c = bytearray(open(os.path.join(bx.run, "nvr", f), "rb").read())
        if len(c) == 128:
            c[0x0F] = 0
        out[f] = bytes(c)
    shutil.rmtree(bx.run, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    for f, c in out.items():
        with open(os.path.join(d, f), "wb") as fh:
            fh.write(c)
    return out


# --- the GDB stub ------------------------------------------------------------

class Gdb(object):
    """The smallest remote-protocol client that does what this needs: Z1/z1,
    P, c, s. Every packet the stub sends is acked by the reader thread (the
    stub writes nothing more until it is), stop replies (T../S..) go to
    `on_stop`, everything else to the request waiting for it."""

    def __init__(self, port, on_stop):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.s.settimeout(None)
        self.on_stop = on_stop
        self.replies = queue.Queue()
        self.wlock = threading.Lock()
        self.dead = False
        threading.Thread(target=self._reader, daemon=True).start()
        self.s.sendall(b"+")

    def _reader(self):
        buf = b""
        try:
            while True:
                d = self.s.recv(65536)
                if not d:
                    break
                buf += d
                while buf:
                    c = buf[:1]
                    if c != b"$":
                        buf = buf[1:]
                        continue
                    i = buf.find(b"#")
                    if i < 0 or len(buf) < i + 3:
                        break
                    body, buf = buf[1:i].decode("latin-1"), buf[i + 3:]
                    with self.wlock:
                        self.s.sendall(b"+")
                    if body[:1] in ("T", "S"):
                        self.on_stop(body)
                    else:
                        self.replies.put(body)
        except OSError:
            pass
        self.dead = True

    def send(self, body):
        pkt = "$%s#%02x" % (body, sum(body.encode("latin-1")) & 0xFF)
        with self.wlock:
            self.s.sendall(pkt.encode("latin-1"))

    def req(self, body, timeout=15.0):
        self.send(body)
        try:
            r = self.replies.get(timeout=timeout)
        except queue.Empty:
            raise om.MartyError("os88boxmarty: the GDB stub never answered %r"
                                % body)
        if r.startswith("E"):
            raise om.MartyError("os88boxmarty: the GDB stub refused %r: %s"
                                % (body, r))
        return r

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


GDB_REGS = {"ax": 0, "cx": 1, "dx": 2, "bx": 3, "sp": 4, "bp": 5, "si": 6,
            "di": 7, "ip": 8, "flags": 9, "cs": 10, "ss": 11, "ds": 12,
            "es": 13, "fs": 14, "gs": 15}


# --- the machine ---------------------------------------------------------------

class BoxMarty(MegaMixin, om.Marty):
    """`Marty` with the debug server replaced by 86Box: see the module note.
    `m.b` is the os88box.Box underneath."""

    box86 = True
    mega = True

    def __init__(self, b, run_dir, cards, label=None):
        self.b = b
        self.run_dir = run_dir
        self.cards_ = cards
        self.addr = "86box:%s" % b.name
        self.port = None
        st = ob.state(b.name) or {}
        self.pid = st.get("pid")
        self._gdbport = st.get("gdb")
        self._proc = None
        self._rec = None
        self._lock = threading.RLock()      # the automation socket
        self._log = []
        self._go = None
        self._pumping = 0
        self._planes_verb = False
        self._pipeline = False
        self.label = label
        self._state = "paused"
        self._stops = 0
        self._ms0 = None
        self._ms = 0
        self._at = (0, 0, 0)
        self._gdb = None
        self._bps = set()
        self._stepq = None
        self._closed = False
        self._src = {}
        self._wav = None

    # ---- the automation socket ---------------------------------------------
    def _a(self, line):
        with self._lock:
            r = self.b.cmd(line)
        if "ms" in r:
            self._ms = r["ms"]
            if self._ms0 is None:
                self._ms0 = self._ms
        if r.get("stopped") == "debugger" and self._stepq is None:
            self._hit()
        return r

    def _cycles(self):
        return int((self._ms - (self._ms0 or 0)) * GUEST_HZ / 1000.0)

    def _clock(self):
        """MegaMixin's waits (the boot toast) in GUEST seconds: the machine
        runs fast-forwarded, so ten host seconds are minutes of it"""
        if self._state == "running":
            self._a("status")
        return self._ms / 1000.0

    # ---- running and stopping ----------------------------------------------
    def _release(self):
        self._a("release")
        self._state = "running"

    def _hold(self):
        self._a("hold")

    def _hit(self, body=None):
        """A stop the GDB stub made: a breakpoint. The machine is HELD so a
        resume decides when it runs again."""
        with self._lock:
            if self._state != "running":
                return
            self.b.cmd("hold")
            self._state = "breakpoint"
            self._stops += 1
            self._regs_at()

    def _on_stop(self, body):
        if self._stepq is not None:
            self._stepq.put(body)
            return
        threading.Thread(target=self._hit, args=(body,), daemon=True).start()

    def _regs_at(self):
        r = self.b.cmd("regs")
        self._at = (r["cs"], r["eip"] & 0xFFFF, r["cs_base"] + r["eip"])
        return r

    def gdb(self):
        """The stub, connected on first use. Connecting STOPS the CPU (the
        stub's own rule) and the `c` sent straight after lets it go - with
        the machine held, so nothing ran in between."""
        if self._gdb is None:
            with self._lock:
                was = self._state
                if was == "running":
                    self.b.cmd("hold")
                self._gdb = Gdb(self._gdbport, self._on_stop)
                self._gdb.send("c")
                if was == "running":
                    self.b.cmd("release")
        return self._gdb

    # ---- memory ---------------------------------------------------------------
    def _read(self, addr, n):
        out = bytearray()
        while n:
            k = min(n, 65536)
            out += bytes.fromhex(self._a("memr 0x%X %d" % (addr, k))["data"])
            addr += k
            n -= k
        return bytes(out)

    def _write(self, addr, data):
        for i in range(0, len(data), 1024):
            self._a("memw 0x%X %s" % (addr + i, data[i:i + 1024].hex()))
        return len(data)

    def protected(self):
        return bool(self._a("regs")["cr0"] & 1)

    def gdt_base(self):
        import os88sym
        g = self._read(os88sym.linear("mega_gdtr"), 6)
        return (g[2] | g[3] << 8 | g[4] << 16 | g[5] << 24,
                g[0] | g[1] << 8)

    def ldt_base(self):
        base, limit = self.gdt_base()
        d = self._read(base + 0x18, 8)          # MEGA_SEL_LDT's descriptor
        return (d[2] | d[3] << 8 | d[4] << 16 | d[7] << 24,
                d[0] | d[1] << 8 | (d[6] & 0x0F) << 16)

    def gdt(self, sel):
        base, limit = self.gdt_base()
        if (sel & ~7) + 7 > limit:
            raise om.MartyError("os88boxmarty: GDT selector %#x is past the "
                                "table's limit %#x" % (sel, limit))
        d = self._read(base + (sel & ~7), 8)
        return (d[2] | d[3] << 8 | d[4] << 16 | d[7] << 24,
                d[0] | d[1] << 8 | (d[6] & 0x0F) << 16)

    def _vector(self, v):
        """Vector V's handler, linear: the IDT's gate in protected mode
        ([mega_idtr]), the IVT's in real mode."""
        if self.protected():
            import os88sym
            t = self._read(os88sym.linear("mega_idtr"), 6)
            base = t[2] | t[3] << 8 | t[4] << 16 | t[5] << 24
            g = self._read(base + v * 8, 8)
            off = g[0] | g[1] << 8
            if g[5] & 0x08:                     # a 386 gate
                off |= (g[6] | g[7] << 8) << 16
            return self.lin(g[2] | g[3] << 8, off)
        g = self._read(v * 4, 4)
        return ((g[2] | g[3] << 8) << 4) + (g[0] | g[1] << 8)

    # ---- the server -----------------------------------------------------------
    def cmd(self, **kw):
        c = kw.pop("cmd")
        f = getattr(self, "_c_" + c, None)
        if f is None:
            raise om.MartyError(
                "`%s` is a MartyPC instrument the kern_mega 86Box shim does "
                "not have (tools/os88boxmarty.py) - this row is not portable "
                "as it stands" % c)
        r = dict(f(**kw) or {})
        r["ok"] = True
        return r

    def _status(self):
        if self._state == "running":
            self._a("status")
        cs, ip, flat = self._at
        return {"state": self._state, "cycles": self._cycles(),
                "stops": self._stops, "cs": cs, "ip": ip, "flat_ip": flat}

    def _c_ping(self, **_):
        return {"pipeline": False}

    def _c_status(self, **_):
        return self._status()

    def _c_read(self, addr, len, **_):          # noqa: A002
        return {"data": self._read(addr, len).hex()}

    def _c_write(self, addr, data, **_):
        return {"written": self._write(addr, bytes.fromhex(data))}

    def _c_run(self, **_):
        frm = self._stops
        if self._state == "breakpoint":
            self.gdb().send("c")        # the stop just left is not re-hit
        if self._state != "running":
            self._release()
        st = self._status()
        st["resumed_from"] = frm
        return st

    def _c_pause(self, **_):
        with self._lock:
            if self._state == "running":
                self.b.cmd("hold")
                self._state = "paused"
                self._stops += 1
                self._regs_at()
        return self._status()

    def _c_step(self, n=1, over=False, **_):
        """N INSTRUCTIONS, through the stub's single step: each `s` runs one
        when the machine next runs, which a 1 ms `step` does."""
        self._c_pause()
        g = self.gdb()
        with self._lock:
            self._stepq = queue.Queue()
            try:
                for _ in range(n):
                    g.send("s")
                    self.b.cmd("step 1")
                    try:
                        self._stepq.get(timeout=10)
                    except queue.Empty:
                        raise om.MartyError("os88boxmarty: a single step "
                                            "never stopped")
                g.send("c")             # ...and the stub back to running,
            finally:                    # the machine still held
                self._stepq = None
            self._state = "paused"
            self._stops += 1
            self._regs_at()
        return self._status()

    def _c_advance(self, frames=None, cycles=None, card=None, **_):
        ms = (cycles * 1000.0 / GUEST_HZ if cycles is not None else
              (frames or 1) * 1000.0 / 60.0)
        if self._state == "breakpoint":
            self.gdb().send("c")
        with self._lock:
            self.b.cmd("hold")
            self._state = "running"
            r = self._a("step %d" % max(1, int(round(ms))))
            if r.get("stopped") != "debugger":
                self._state = "paused"
                self._stops += 1
                self._regs_at()
        return self._status()

    def _c_bp(self, list, **_):                 # noqa: A002
        want = set()
        for b in list:
            t = b.get("type")
            if t == "exec":
                want.add(int(b["addr"]))
            elif t == "execseg":
                want.add(self.lin(int(b["seg"]), int(b["off"])))
            elif t == "int":
                want.add(self._vector(int(b["addr"])))
            else:
                raise om.MartyError("os88boxmarty: a %r breakpoint is not "
                                    "available on 86Box" % t)
        if want or self._bps:
            g = self.gdb()
            for a in sorted(self._bps - want):
                g.req("z1,%x,1" % a)
            for a in sorted(want - self._bps):
                g.req("Z1,%x,1" % a)
            self._bps = want
        return {"count": len(want)}

    def _c_regs(self, **_):
        r = self._a("regs")
        out = {n: r["e" + n] & 0xFFFF for n in ("ax", "bx", "cx", "dx", "sp",
                                                "bp", "si", "di")}
        out["ip"] = r["eip"] & 0xFFFF
        out["flags"] = r["eflags"] & 0xFFFF
        for s in ("cs", "ds", "es", "ss", "fs", "gs"):
            out[s] = r[s]
        return out

    def _setregs(self, vals):
        """GDB `P` writes, the 16-bit general registers merged into their
        32-bit ones and IP made linear (the stub's EIP is CS's base + IP)."""
        g = self.gdb()
        r = self._a("regs")
        for reg, v in vals:
            if reg in ("ax", "bx", "cx", "dx", "sp", "bp", "si", "di"):
                v = (r["e" + reg] & 0xFFFF0000) | (v & 0xFFFF)
            elif reg == "flags":
                v = (r["eflags"] & 0xFFFF0000) | (v & 0xFFFF)
            elif reg == "ip":
                v = r["cs_base"] + (v & 0xFFFF)
            g.req("P%x=%s" % (GDB_REGS[reg], (v & 0xFFFFFFFF).to_bytes(
                4, "little").hex()))
            if reg == "cs":
                r = self._a("regs")
        self._regs_at()

    def _c_setreg(self, reg, value, **_):
        self._setregs([(reg, value)])
        return {}

    def _c_park(self, cs, ip, **_):
        self._c_pause()
        self._setregs([("cs", cs), ("ip", ip)])
        return {"if_cleared": False}

    def _c_key(self, key, down=True, up=True, **_):
        k = scancode(key)
        if down:
            self._a("key down 0x%X" % k)
        if up:
            self._a("key up 0x%X" % k)
        self._log.append({"cycles": self._cycles(), "kind": "key",
                          "args": {"key": key, "down": down, "up": up}})
        return {"cycles": self._cycles()}

    def _c_mouse(self, dx=0, dy=0, l=False, r=False, wz=0, **_):
        if wz:
            raise om.MartyError("os88boxmarty: no wheel on the serial mouse")
        self._a("mouse %d %d %d" % (dx, dy, (1 if l else 0) | (2 if r else 0)))
        return {"cycles": self._cycles()}

    # ---- the glass --------------------------------------------------------------
    def _card(self, card):
        i = 0 if card in (None, "pri") else int(card)
        if not 0 <= i < len(self.cards_):
            raise om.MartyError("os88boxmarty: no video card %r on this "
                                "machine (%s)" % (card, self.cards_))
        return i

    def _video(self, card=None):
        i = self._card(card)
        typ, kind = _CARDS[self.cards_[i]]
        if kind is None:                        # VGA/EGA: the BIOS's mode
            mode = self._read(0x449, 1)[0]
            text = mode in (0, 1, 2, 3, 7)
            fw, fh = (800, 524) if not text else (720, 400)
        else:
            text = False
            mode = 0x06 if kind == "cga" else 0x07
            fw, fh = (640, 200) if kind == "cga" else (720, 348)
        return {"idx": i, "type": typ, "primary": i == 0,
                "mode": "Mode%02X" % mode, "graphics": not text,
                "field_w": fw, "field_h": fh, "frames": 1}

    def _c_video(self, card=None, **_):
        return self._video(card)

    def _c_cards(self, **_):
        return {"cards": [self._video(i) for i in range(len(self.cards_))]}

    def video(self, card=None):
        return self._video(card)

    def _c_screen(self, card=None, **_):
        try:
            t = self._a("text")
        except SystemExit:
            return {"rows": []}
        return {"rows": [bytes(b if b >= 32 else 32 for b in bytes.fromhex(
            x)).decode("cp437").rstrip() for x in t.get("chars", [])]}

    def _c_fbuf(self, aperture=0, card=None, **_):
        from PIL import Image
        i = self._card(card)
        p = os.path.join(self.run_dir, "fbuf%d.png" % i)
        self._a("%s %s" % ("screenshot" if i == 0 else "screenshot1", p))
        im = Image.open(p).convert("RGB")
        return {"w": im.width, "h": im.height, "data": im.tobytes().hex()}

    def _c_disk(self, reset=False, **_):
        """MartyPC's FDC counters: READ DATA and WRITE DATA commands the
        controller completed (tools/86box/patches/06), since launch or the
        last `reset=True`"""
        r = self._a("fdc")
        base = getattr(self, "_fdc0", (0, 0))
        out = {"reads": r["reads"] - base[0], "writes": r["writes"] - base[1]}
        if reset:
            self._fdc0 = (r["reads"], r["writes"])
        return out

    def _c_mount(self, drive, path, **_):
        """A floppy swap under a running machine: a COPY of PATH is loaded
        into the drive, as MartyPC mounts a private copy; `disks` names PATH
        as mounted from then on, and `flush` writes the copy back"""
        n = len([f for f in os.listdir(self.b.run) if f.startswith("swap")])
        dst = os.path.join(self.b.run, "swap%d-%s" % (n, os.path.basename(path)))
        shutil.copyfile(path, dst)
        self._a("fdd load %d %s" % (drive, dst))
        self._live[drive] = dst
        self._src[drive] = os.path.join(self.run_dir, "%s-mounted%d.img"
                                        % ("ab"[drive], n))
        shutil.copy(path, self._src[drive])
        return {}

    def _c_reset(self, **_):
        self._a("reset hard")
        self._release()
        return self._status()

    def _c_quit(self, **_):
        self.close()
        return {}

    def vram(self, kind=None):
        """Marty.vram, and on a VGA (no flat framebuffer) the glass instead -
        lit where not black, as tools/os88bochsmarty.py answers it."""
        if kind is None and _CARDS[self.cards_[0]][1] is None:
            w, h, px = self.fbuf()
            return w, h, [[1 if (px[(y * w + x) * 3] | px[(y * w + x) * 3 + 1]
                                 | px[(y * w + x) * 3 + 2]) else 0
                           for x in range(w)] for y in range(h)]
        return om.Marty.vram(self, kind)

    def disks(self):
        return [{"drive": d, "path": self._src.get(d, self._live.get(d))}
                for d in (0, 1)]

    def flush(self, drive=0, path=None, fmt="raw"):
        src = self._live[drive]
        dst = path or self._src.get(drive)
        if dst:
            shutil.copy(src, dst)
        return {"path": dst or src}

    def _poker(self, spec):
        """$OS88_MEGA_POKE - a port's way to BREAK the thing it checks
        (megaport.txt's "seen to go red"): `SYM[+OFF]=HEX;...` written over
        the kernel once its desktop is up (desk_rows and menu_nbar written,
        [spl_live] 0), so a row needs no knob build to be shown failing.
        86Box's interpreter keeps no decoded copy of code, so a byte written
        is the byte executed; `sym` resolves `.cold`/`.mega` where kern_mega
        runs them. Each poke is printed, with the bytes it replaced."""
        import os88sym
        pokes = []
        for p in filter(None, spec.split(";")):
            where, hexb = p.split("=")
            mm = re.match(r"^(.*?)([+-](?:0x[0-9a-fA-F]+|\d+))?$", where)
            pokes.append((mm.group(1), int(mm.group(2) or "0", 0),
                          bytes.fromhex(hexb)))
        tk = None
        while not self._closed:
            try:                # (an AT's POST visits protected mode and
                up = (self.protected()      # leaves patterns in low memory:
                      and self.read(os88sym.linear("desk_rows"), 2) != b"\0\0"
                      and self.read(os88sym.linear("menu_nbar"), 2) != b"\0\0"
                      and not self.read(os88sym.linear("spl_live"), 1)[0])
                t = self.read(os88sym.linear("ticks"), 2)   # [ticks] MOVING
                up, tk = up and tk is not None and t != tk, t
            except Exception:                   # noqa: BLE001
                up = False
            if up:
                break
            time.sleep(0.05)
        for name, off, data in pokes:
            try:
                a = self.sym(name) + off
            except Exception as e:              # noqa: BLE001
                print("os88boxmarty: POKE %s: %s" % (name, e), flush=True)
                continue
            old = self.read(a, len(data))
            self.write(a, data)
            print("os88boxmarty: POKE %s+%#x (%#x): %s -> %s"
                  % (name, off, a, old.hex(), data.hex()), flush=True)

    def faults(self):
        """The CPU's exceptions and resets so far (tools/86box/patches/01),
        as `os88box.py NAME faults` prints them - the BIOS's own hidden."""
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ob.faults(self.b.name, False, self.b.kmap())
        return out.getvalue().splitlines()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._gdb:
                self._gdb.close()
        except Exception:                       # noqa: BLE001
            pass
        try:
            self.b.quit()
        except BaseException:                   # noqa: BLE001
            pass
        if self.pid and ob.alive(self.pid):     # a quit it ignored: ours,
            try:                                # so it goes
                os.kill(self.pid, 9)
            except OSError:
                pass
        keep = os.environ.get("OS88_MEGA_KEEP")
        if keep:
            print("os88boxmarty: kept %s and %s" % (self.b.run, self.run_dir),
                  file=sys.stderr)
        else:
            shutil.rmtree(self.b.run, ignore_errors=True)
            shutil.rmtree(self.run_dir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _vhd_params(path):
    """86Box's `hdd_01_parameters` (spt, heads, cylinders) for a row's disk:
    a VHD's footer, else os88megacommon's geometry by size"""
    import os88megacommon
    c, h, s = os88megacommon.hd_geometry(path)
    return s, h, c


def launch(image, apps=None, machine="", boot=True, label=None, extra=(),
           run_dir=None, cfg=None, megs=None, cimg=None, ne2k_io=None, **_):
    """os88marty.launch's shape, on 86Box and kern_mega (see the module
    note). `boot` True runs the machine to the desktop (os88box's kernel
    gate, on the emulated clock) and hands it back RUNNING; a number runs
    for that many guest seconds; False hands it back PAUSED at power-on.

    The rest are os88bochsmarty.launch's, for tests/os88qmpbochs.py's QMP
    server: `cfg` a SYSTEM.CFG driver mask written onto A:'s copy ("keep":
    A:'s own stands; an `_ne2k` machine with neither wants ETHER.DRV, 10h),
    `megs` the RAM, `cimg` the row's own fixed disk (mounted IN PLACE, as
    `--mount hd:0:` is), `ne2k_io` the card's port."""
    if cimg:
        extra = list(extra or ()) + ["--mount", "hd:0:" + cimg]
    cimg, cgeom = row_disk(machine, extra, run_dir)
    noa = bool(cimg) and (not image or _blank(image))
    a, b = mega_images(image, apps)
    bld = os.environ.get("OS88_MEGA_BUILD") or os.path.join(ROOT, "build")
    if not b:
        b = os.path.join(bld, "megaapps.img")
    if noa:
        a = None
    sets, cards, info = machine_config(machine)
    # THE MACHINE'S RAM in MB, as the Bochs shim takes it ($OS88_BOCHS_MEGS,
    # megaport.txt's `@OS88_BOCHS_MEGS=1`: a 1MB kern_mega has no pool, so
    # every claim is conventional and selector-named); the profile's 4MB
    # otherwise. ($OS88_MEGA_MEGS says the same without naming Bochs)
    megs = megs or os.environ.get("OS88_MEGA_MEGS") or os.environ.get(
        "OS88_BOCHS_MEGS")
    if ne2k_io:
        sets.append(("NE2000 #1", "base", "%04X" % ne2k_io))
    ne2k = "_ne2k" in (machine or "") or bool(os.environ.get(
        "OS88_BOCHS_NE2K"))
    if cfg == "keep":
        cfg = None
    elif cfg is None and ne2k:
        cfg = 0x10              # A:'s SYSTEM.CFG wants ETHER.DRV, as Bochs's
    if cfg is not None and a:
        a = _with_cfg(a, cfg)
    if megs:
        sets.append(("Machine", "mem_size", str(int(float(megs) * 1024))))
    profile = os.environ.get("OS88_MEGA_VM") or PROFILE
    for d, img in (("01", a), ("02", b)):
        if img:
            sets.append(("Floppy and CD-ROM drives", "fdd_%s_type" % d,
                         _FDTYPE.get(os.path.getsize(img), ("35_2hd",))[0]))
    if cimg:
        s_, h_, c_ = _vhd_params(cimg)
        sets += [("Hard disks", "hdd_01_parameters",
                  "%d, %d, %d, 0, ide" % (s_, h_, c_)),
                 ("Hard disks", "hdd_01_ide_channel", "0:0")]
    tag = re.sub(r"\W+", "", label or os.path.splitext(
        os.path.basename(sys.argv[0] or "row"))[0])[:20]
    base = os.path.join(ROOT, "build", "86box", "inst")
    os.makedirs(base, exist_ok=True)
    rdir = tempfile.mkdtemp(prefix="%s-" % tag, dir=base)
    name = "mp-" + os.path.basename(rdir)
    env = {}
    wav = os.environ.get("MARTYPC_WAV")
    if wav and info["snd"]:
        env["OS88_SBWAV"] = wav + ".sound_blaster.wav"
    nvr = cmos_primed(profile, a, b, sets,
                      cmos_seed(profile, a, b, info["display"]),
                      mono=cards[0] in ("hercules", "mda") and len(cards) > 1,
                      c=cimg)
    try:
        box = ob.launch(profile, name=name, hold=True, fresh=True, a=a, b=b,
                        c=cimg, inplace_c=bool(cimg), cfgs=sets, temp=True,
                        kmap=os.path.join(bld, "megak", "kernel.map"),
                        nvr=nvr, env=env, eject_a=not a)
    except SystemExit as e:
        shutil.rmtree(rdir, ignore_errors=True)
        raise om.MartyError("os88boxmarty: 86Box did not start: %s" % e)
    m = BoxMarty(box, rdir, cards, label=label)
    if os.environ.get("OS88_MEGA_POKE"):
        threading.Thread(target=m._poker, args=(
            os.environ["OS88_MEGA_POKE"],), daemon=True).start()
    m._live = {0: os.path.join(box.run, "fdd1" + os.path.splitext(a)[1])
               if a else None,
               1: os.path.join(box.run, "fdd2" + os.path.splitext(b)[1])}
    for d in (0, 1):                # THE MOUNTED-FROM IMAGES: 86Box writes
        if m._live[d] and os.path.exists(m._live[d]):   # through, so the
            m._src[d] = os.path.join(rdir, "%s-mounted.img" % "ab"[d])  # live
            shutil.copy(m._live[d], m._src[d])          # file is no reference
    try:
        try:                            # THIS TREE'S 86Box: patches 04-06
            m._a("fdc")                 # (the SB capture, `screenshot1`,
        except SystemExit:              # `fdc`) - an older build answers
            raise om.MartyError(        # "unknown command"
                "os88boxmarty: %s predates tools/86box/patches/04-06 - "
                "rebuild it: python3 tools/os88box.py build" % ob.BIN)
        m._a("ff on")
        m._a("status")
        if boot is False or boot == 0:
            return m
        if boot is True:
            box.kernel_up(guest_ms=240000, prompts=BIOS_PROMPTS)
            m._a("status")
            m._release()
            m.boot_toast()
            return m
        m._release()                    # BLIND for that many GUEST seconds
        end = m._cycles() + float(boot) * GUEST_HZ
        while m.status()["cycles"] < end:
            time.sleep(0.02)
        return m
    except BaseException:
        m.close()
        raise


def _with_cfg(a, bits):
    """A copy of A: whose SYSTEM.CFG wants the drivers in BITS - the file
    tools/os88bochs.Box writes (`--cfg`), so the two backends boot the same
    disk. The copy lives until the process exits (86Box copies it again)."""
    d = tempfile.mkdtemp(prefix="o88cfg-", dir=os.path.join(
        ROOT, "build", "86box", "inst"))
    atexit.register(shutil.rmtree, d, True)
    out = os.path.join(d, os.path.basename(a))
    shutil.copyfile(a, out)
    f = os.path.join(d, "SYSTEM.CFG")
    with open(f, "wb") as fh:
        fh.write(b"O88CFG\0\0" + (3).to_bytes(2, "little") + b"DW" +
                 bytes([1, 2]) + bits.to_bytes(2, "little") + b"\0\0")
    fat = os.path.join(ROOT, "tools", "os88fat.py")
    subprocess.run([sys.executable, fat, "del", out, "SYSTEM.CFG"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([sys.executable, fat, "add", out, f], check=True,
                   stdout=subprocess.DEVNULL)
    return out


# MR BIOS 286 (and the AMI the 286-525 profiles carry) on the way up: a CMOS
# that does not match the machine stops at POST (tests/rdgcore/rdgwin.py's)
BIOS_PROMPTS = (("bypass MEMORY test", "esc"), ("to RESUME", "f1"),
                ("Press Any Key", "esc"), ("EXIT FOR BOOT", "return"),
                # ...which takes MR BIOS into SETUP, where F10 records the
                # configuration it found and boots
                ("Summary   Energy", "f10"))


def main(argv):
    """`os88boxmarty.py IMAGE [APPS] [MACHINE]`: boot one and print what the
    shim sees - a smoke test of the backend."""
    m = launch(argv[0] if argv else None, apps=argv[1] if len(argv) > 1
               else None, machine=argv[2] if len(argv) > 2 else "")
    with m:
        print(json.dumps(m.status()))
        print(json.dumps(m.cards()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
