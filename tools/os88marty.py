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
        """The video card's text, via the card - NOT via a memory read.

        Video RAM is MMIO owned by the card; peeking its addresses returns the
        flat memory underneath, which is a blank screen rather than an error.
        """
        return self.cmd(cmd="screen")["rows"]

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

    def history(self):
        return self.cmd(cmd="history")["history"]

    def quit(self):
        return self.cmd(cmd="quit")


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
