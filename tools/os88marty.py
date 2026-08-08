#!/usr/bin/env python3
"""os88marty: drive the MartyPC debug server (docs/MARTYPC-DEBUG.md).

    tools/martypc/build.sh
    cd build/martypc/run && MARTYPC_DEBUG_ADDR=127.0.0.1:9001 \\
        ./martypc_headless --mount fd:0:media/floppies/os8088-360.img &

    python3 tools/os88marty.py 127.0.0.1:9001 status
    python3 tools/os88marty.py 127.0.0.1:9001 run
    python3 tools/os88marty.py 127.0.0.1:9001 dump 0060:0000 71624 -o /tmp/k.dump
    python3 tools/os88marty.py 127.0.0.1:9001            # a REPL

The sibling of tools/os88dbg.py, and the difference is worth stating because
they answer the same question from opposite sides. os88dbg talks to DEBUG.DRV,
which is CODE RUNNING INSIDE THE GUEST: it needs a UART, an IRQ, interrupts
enabled and a machine healthy enough to service them - and it works on real
iron, which nothing else here does. This talks to the EMULATOR: it costs the
guest not one cycle, needs nothing installed, answers on a machine that has
hard-frozen, and can do the things a guest stub structurally cannot - single
step, breakpoints, cycle counts, registers.

Use this one for everything on an emulator. Use os88dbg when the machine is
on somebody's desk.

MARTYPC IS CYCLE-ACCURATE AND IT IS NOT DISK-ACCURATE. It models the 8088's
instruction timing, prefetch queue and bus contention; it models no platter,
no seek and no interleave. PERFORMANCE.md Set 11 measured a 16KB read at
0.27s against the 5150's 8.07 - 30x fast - and a boot 17x fast. So any figure
with a disk in its path is wrong here, including plenty that is not obviously
about disks: a boot time, a package launch, a module load, a SYSTEM.CFG
write. And it will not catch a disk CORRECTNESS bug either - SPEC.md 18.91's
AL bug moved 148 sectors in 34 int 13h calls on the 5150 and 34 sectors in 6
calls under QEMU, correct and silent. For anything with a disk in it the
instrument is docs/FIELD-MACHINES.md's machine and there is no substitute.

THE DUMP IS SELF-VALIDATING, and that is the point of `verify`:
docs/FIELD-MACHINES.md's rule is that linear 0x600 onward is build/kernel.bin
byte for byte apart from writable state, so a diff proves you are running the
build you think you are AND hands you every live variable at its listing
offset with no instrumentation added. `verify` is that check as one command.
"""
import argparse
import json
import socket
import sys

DEFAULT_TIMEOUT = 60.0
KERNEL_SEG = 0x0060


class MartyError(Exception):
    pass


class Marty:
    """One conversation with a headless MartyPC."""

    def __init__(self, addr, timeout=DEFAULT_TIMEOUT):
        host, _, port = addr.rpartition(":")
        if not host:
            host, port = "127.0.0.1", addr
        try:
            self.s = socket.create_connection((host, int(port)), timeout=timeout)
        except OSError as e:
            raise MartyError(
                f"{addr}: {e}. Is martypc_headless running with "
                f"MARTYPC_DEBUG_ADDR set?") from None
        self.f = self.s.makefile("rwb")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        try:
            self.f.close()
            self.s.close()
        except OSError:
            pass

    def cmd(self, **kw):
        self.f.write((json.dumps(kw) + "\n").encode())
        self.f.flush()
        line = self.f.readline()
        if not line:
            raise MartyError("server closed the connection")
        r = json.loads(line)
        if not r.get("ok", False):
            raise MartyError(r.get("err", "refused"))
        return r

    # --- state ---------------------------------------------------------------

    def status(self):
        return self.cmd(cmd="status")

    def regs(self):
        return self.cmd(cmd="regs")

    def setreg(self, reg, value):
        return self.cmd(cmd="setreg", reg=reg, value=value)

    def screen(self):
        """The video card's text rows, in text modes."""
        return self.cmd(cmd="screen")["rows"]

    def video(self):
        """Which card, its raster geometry, and its display apertures.

        `graphics` IS NOT TO BE TRUSTED ON VGA: the card's `mode_graphics`
        field is initialised to false and never assigned, so it answers false
        in mode 12h exactly as it does in mode 3. `field_w`/`field_h` are the
        honest question - 800x524 is mode 12h's raster and a text mode's is
        not.
        """
        return self.cmd(cmd="video")

    def fbuf(self, aperture=0):
        """The card's RENDERED framebuffer as (width, height, rgb24 bytes).

        The complement of `vram`, and the only route that works on VGA: mode
        12h is four planes behind the Graphics Controller, so there is no flat
        framebuffer in guest memory to read. This asks the CARD what it
        rasterised, which is a different assertion - `vram` says the kernel
        wrote the right bytes, this says the machine put them on a screen -
        and it works on every adapter and in every mode.
        """
        r = self.cmd(cmd="fbuf", aperture=aperture)
        return r["w"], r["h"], bytes.fromhex(r["data"])

    def vram(self, kind=None):
        """The 1bpp framebuffer as (width, height, rows-of-bits).

        `read` resolves MMIO, so video RAM comes back like any other memory -
        no screendump, no HERCSEG relocation, and no reason to start QEMU just
        to look at the screen. `kind` is 'cga' or 'herc'; None asks the
        machine which card it has.

        VGA is deliberately absent, and that is about the LAYOUT rather than
        about MartyPC: mode 12h is four PLANES behind the Graphics
        Controller's Read Map Select, so it is not readable as flat memory at
        all. `fbuf` is the route there - it asks the card what it rasterised
        instead of asking memory what is in it.
        """
        if kind is None:
            # ASK THE CARD. Sniffing memory does not work: an unmapped
            # 0xB0000 reads as zeroes rather than erroring, so "is there
            # something at the MDA aperture" answers yes on a CGA-only
            # machine - which is exactly the wrong answer, silently.
            vt = self.cmd(cmd="video")["type"]
            kind = "cga" if vt == "cga" else "herc"   # MDA and Hercules share
                                                      # a layout and an aperture
        if kind == "cga":
            base, w, h, stride, banks = 0xB8000, 640, 200, 80, 2
        elif kind == "herc":
            base, w, h, stride, banks = 0xB0000, 720, 348, 90, 4
        else:
            raise MartyError("kind must be 'cga' or 'herc'")
        fb = self.read(base, banks * 0x2000)
        rows = []
        for y in range(h):
            # SPEC.md 39.3's banked layout, byte for byte the arithmetic in
            # tools/hercshot.py - so a picture from either route is the same
            # picture, and a shear means the KERNEL's bank arithmetic moved.
            off = (y % banks) * 0x2000 + (y // banks) * stride
            rows.append(bytearray((fb[off + (x >> 3)] >> (7 - (x & 7))) & 1
                                  for x in range(w)))
        return w, h, rows

    # --- memory --------------------------------------------------------------

    def read(self, addr, length):
        """Read `length` bytes from a flat address, in one call per 64KB."""
        out = bytearray()
        while length:
            n = min(1 << 16, length)
            r = self.cmd(cmd="read", addr=addr + len(out), len=n)
            out += bytes.fromhex(r["data"])
            length -= n
        return bytes(out)

    def readseg(self, seg, off, length):
        return self.read((seg << 4) + off, length)

    def write(self, addr, data):
        return self.cmd(cmd="write", addr=addr, data=data.hex())["written"]

    def inb(self, port):
        return self.cmd(cmd="inb", port=port)["value"]

    def outb(self, port, value):
        return self.cmd(cmd="outb", port=port, value=value)

    # --- execution -----------------------------------------------------------

    def run(self):
        return self.cmd(cmd="run")

    def pause(self):
        return self.cmd(cmd="pause")

    def step(self, n=1, over=False):
        return self.cmd(cmd="step", n=n, over=over)

    def reset(self):
        return self.cmd(cmd="reset")

    def breakpoints(self, bps):
        """Replace the whole breakpoint set. `bps` is a list of dicts:

            {"type": "exec",    "addr": 0x600}      # flat CS<<4+IP
            {"type": "execseg", "seg": 0x60, "off": 0x1234}
            {"type": "mem",     "addr": 0x60C}      # any access
            {"type": "int",     "addr": 0x13}       # interrupt number
            {"type": "io",      "addr": 0x3F8}
        """
        return self.cmd(cmd="bp", list=bps)["count"]

    # --- input, through the REAL devices -------------------------------------
    #
    # No guest code is involved in either of these, which is the point: `key`
    # enters the emulator's keyboard buffer so the guest sees it through the
    # 8255 and int 09h, and `mouse` builds a real Microsoft 3-byte packet and
    # clocks it into the serial controller so the guest's own ISR decodes it.
    # A debug module poking [mouse_x] would skip the UART, the packet decoder
    # and SPEC.md 9.5's port contest - the code most likely to be wrong.

    def key(self, name, down=True, up=True):
        """One MartyKey by name: 'KeyA', 'Enter', 'Digit1', 'ArrowUp'."""
        return self.cmd(cmd="key", key=name, down=down, up=up)

    def type_text(self, s):
        """ASCII through the keyboard. Letters, digits, space and Enter."""
        for ch in s:
            if ch == "\n":
                self.key("Enter")
            elif ch == " ":
                self.key("Space")
            elif ch.isalpha():
                self.key("Key" + ch.upper())
            elif ch.isdigit():
                self.key("Digit" + ch)
            else:
                raise MartyError("no key mapping for %r" % ch)

    def mouse(self, dx=0, dy=0, l=False, r=False):
        """One packet. dx/dy are RELATIVE and clamped to a signed byte."""
        return self.cmd(cmd="mouse", dx=dx, dy=dy, l=l, r=r)

    def mouse_move(self, dx, dy, l=False, r=False, step=100):
        """A long move as several packets - a packet carries a signed byte."""
        while dx or dy:
            sx = max(-step, min(step, dx))
            sy = max(-step, min(step, dy))
            self.mouse(sx, sy, l, r)
            dx -= sx
            dy -= sy

    def click(self, l=True):
        """Press and release in place."""
        self.mouse(0, 0, l=l)
        self.mouse(0, 0)

    def history(self):
        return self.cmd(cmd="history")["history"]

    def quit(self):
        return self.cmd(cmd="quit")


def _png(path, w, h, raw, colour_type):
    import struct, zlib

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, colour_type, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


def write_png(path, w, h, rows):
    """1bpp rows out as a greyscale PNG, no dependencies (hercshot.py's)."""
    raw = b"".join(b"\x00" + bytes(255 if b else 0 for b in row) for row in rows)
    _png(path, w, h, raw, 0)


def write_png_rgb(path, w, h, data):
    """Packed rgb24 out as a truecolour PNG."""
    raw = b"".join(b"\x00" + data[y * w * 3:(y + 1) * w * 3] for y in range(h))
    _png(path, w, h, raw, 2)


def parse_addr(text):
    """`0060:0000`, `0x600` or `600` -> a flat address."""
    text = text.strip()
    if ":" in text:
        seg, _, off = text.partition(":")
        return (int(seg, 16) << 4) + int(off, 16)
    return int(text, 0)


def cmd_verify(m, args):
    """Dump the kernel and diff it against the build it should be."""
    img = open(args.image, "rb").read()
    ram = m.read(KERNEL_SEG << 4, len(img))
    diff = [i for i in range(len(img)) if ram[i] != img[i]]
    print(f"{args.image}: {len(img)} bytes")
    print(f"differing:  {len(diff)} ({100.0 * len(diff) / len(img):.2f}%)")
    bt = int.from_bytes(ram[0x0C:0x0E], "little")
    print(f"boot_ticks: {bt} live, 0x{int.from_bytes(img[0x0C:0x0E], 'little'):04x} in the file")
    if bt == 0xFFFF:
        print("  ...unstamped: this machine has not finished booting.")
    # Runs, not individual bytes: live state is contiguous variables, and a
    # list of 1,350 offsets tells you nothing a list of 60 runs does not.
    runs, start = [], None
    for i in range(len(img) + 1):
        d = i < len(img) and ram[i] != img[i]
        if d and start is None:
            start = i
        if not d and start is not None:
            runs.append((start, i - start))
            start = None
    print(f"in {len(runs)} run(s); the largest:")
    for off, ln in sorted(runs, key=lambda r: -r[1])[:8]:
        print(f"  +0x{off:04x} {ln:4d} bytes")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Drive a headless MartyPC debug server.")
    ap.add_argument("addr", help="host:port of the debug server (e.g. 127.0.0.1:9001)")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    sub = ap.add_subparsers(dest="op")

    for name in ("status", "regs", "run", "pause", "reset", "screen", "history", "quit"):
        sub.add_parser(name)

    p = sub.add_parser("key"); p.add_argument("name")
    p = sub.add_parser("type"); p.add_argument("text")
    p = sub.add_parser("mouse")
    p.add_argument("dx", type=int); p.add_argument("dy", type=int)
    p.add_argument("--click", action="store_true")

    p = sub.add_parser("shot", help="the framebuffer as a PNG - no QEMU needed")
    p.add_argument("out")
    p.add_argument("--kind", choices=("cga", "herc"), default=None)
    p.add_argument("--rendered", action="store_true",
                   help="ask the CARD what it rasterised (rgb24) instead of "
                        "decoding guest VRAM. Automatic on VGA, where there "
                        "is no flat framebuffer to decode.")
    p.add_argument("--aperture", type=int, default=0)

    p = sub.add_parser("read"); p.add_argument("where"); p.add_argument("len", type=lambda x: int(x, 0))
    p = sub.add_parser("dump"); p.add_argument("where"); p.add_argument("len", type=lambda x: int(x, 0))
    p.add_argument("-o", "--out", required=True)
    p = sub.add_parser("write"); p.add_argument("where"); p.add_argument("hex")
    p = sub.add_parser("step"); p.add_argument("n", nargs="?", type=int, default=1)
    p = sub.add_parser("verify"); p.add_argument("--image", default="build/kernel.bin")

    a = ap.parse_args()

    try:
        with Marty(a.addr, timeout=a.timeout) as m:
            if a.op in (None, ""):
                print("os88marty:", json.dumps(m.status()))
                print("commands: status regs run pause reset step screen history "
                      "read dump write verify quit.  ^D to leave.")
                while True:
                    try:
                        line = input("marty> ").strip()
                    except EOFError:
                        print()
                        return 0
                    if not line:
                        continue
                    if line in ("q", "quit", "exit"):
                        return 0
                    parts = line.split()
                    try:
                        if parts[0] == "read":
                            print(m.read(parse_addr(parts[1]), int(parts[2], 0)).hex(" "))
                        elif parts[0] == "screen":
                            for row in m.screen():
                                print(" |", row.rstrip())
                        elif parts[0] == "step":
                            print(json.dumps(m.step(int(parts[1]) if len(parts) > 1 else 1)))
                        else:
                            print(json.dumps(m.cmd(cmd=parts[0])))
                    except (MartyError, IndexError, ValueError) as e:
                        print("error:", e)
            elif a.op == "read":
                print(m.read(parse_addr(a.where), a.len).hex(" "))
            elif a.op == "dump":
                data = m.read(parse_addr(a.where), a.len)
                open(a.out, "wb").write(data)
                print(f"{len(data)} bytes -> {a.out}")
            elif a.op == "write":
                print(m.write(parse_addr(a.where), bytes.fromhex(a.hex)), "bytes written")
            elif a.op == "step":
                print(json.dumps(m.step(a.n)))
            elif a.op == "key":
                m.key(a.name); print("ok")
            elif a.op == "type":
                m.type_text(a.text); print("ok")
            elif a.op == "mouse":
                m.mouse_move(a.dx, a.dy)
                if a.click:
                    m.click()
                print("ok")
            elif a.op == "shot":
                # VGA has no flat framebuffer to decode - mode 12h is four
                # planes behind the Graphics Controller - so it takes the
                # rendered route whether or not it was asked for. The 1bpp
                # adapters keep the VRAM route by default, because that is the
                # one whose output is byte-comparable with tools/hercshot.py
                # and so with every "0 differing pixels" check in this tree.
                rendered = a.rendered or (a.kind is None and m.video()["type"] == "vga")
                if rendered:
                    w, h, data = m.fbuf(a.aperture)
                    write_png_rgb(a.out, w, h, data)
                    lit = sum(1 for i in range(0, len(data), 3)
                              if data[i:i + 3] != b"\x00\x00\x00")
                    print("%s: %dx%d rendered, %d non-black of %d (%.1f%%)"
                          % (a.out, w, h, lit, w * h, 100.0 * lit / (w * h)))
                else:
                    w, h, rows = m.vram(a.kind)
                    write_png(a.out, w, h, rows)
                    lit = sum(sum(r) for r in rows)
                    print("%s: %dx%d, %d lit of %d (%.1f%%)"
                          % (a.out, w, h, lit, w * h, 100.0 * lit / (w * h)))
            elif a.op == "screen":
                for row in m.screen():
                    print(row.rstrip())
            elif a.op == "history":
                print(m.history())
            elif a.op == "verify":
                return cmd_verify(m, a)
            else:
                print(json.dumps(m.cmd(cmd=a.op)))
        return 0
    except MartyError as e:
        print(f"os88marty: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
