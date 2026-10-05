#!/usr/bin/env python3
"""os88rom - build os8088's ROM for an IBM 5150's five spare sockets.

docs/plans/ROM-PLAN.md is the design and section 1.3 is the layout. The window
is U28-U32, F4000-FDFFF, 40,960 bytes, laid out as ONE option ROM:

    0x0000  55 AA 40  E9 rel16  'OS88'  fmt  bal1  dw id  kind 0    16 bytes
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
FMT = 1
KIND_SOCK, KIND_KERNEL = 1, 2

# the 1981 BIOSes never run rom_init, so int 18h still lands at F600:0000 on
# them; the socket ROM can afford a far jump there, the kernel ROM cannot
# (its .cold runs straight through F6000)
INT18_AT = 0xF6000 - ROM_BASE


def fail(msg):
    sys.exit("os88rom: " + msg)


def build_str():
    try:
        with open(os.path.join(ROOT, "build", "buildnum.inc")) as f:
            m = re.search(r"BUILD_STR\s+'([^']*)'", f.read())
            return m.group(1) if m else "?"
    except OSError:
        return "?"


def assemble_tail(kind, at):
    """boot/osrom.asm assembled at `at`; the bytes."""
    with tempfile.TemporaryDirectory(prefix="os88rom-") as tmp:
        out = os.path.join(tmp, "tail.bin")
        cmd = ["nasm", "-f", "bin", "-w+error", f"-DTAIL_AT={at}",
               f"-DROM_KIND={kind}", f"-DBUILD_STR='{build_str()}'",
               "-o", out, os.path.join(ROOT, "boot", "osrom.asm")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            fail("nasm refused boot/osrom.asm:\n" + r.stderr[-2000:])
        with open(out, "rb") as f:
            return f.read()


def sock_byte(o):
    """The socket-check pattern at window offset o - boot/osrom.asm's
    rom_sock_check computes the same: lo + 3*hi + 0x5A, mod 256."""
    return ((o & 0xFF) + 3 * (o >> 8) + 0x5A) & 0xFF


def layout(kind, payload_len, fill):
    """The window with its header, payload and tail placed, balances unset.
    `fill(img, start, end)` writes the payload bytes."""
    tail0 = assemble_tail(kind, 0)
    tail_at = ROM_SIZE - 1 - len(tail0)        # the last byte is bal2
    if HDR_SIZE + payload_len > tail_at:
        fail(f"the payload is {payload_len:,} bytes and the window holds "
             f"{tail_at - HDR_SIZE:,} after the header and the tail - "
             f"ROM-PLAN 3.6 is what to do about it")
    tail = assemble_tail(kind, tail_at)
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
    hdr[10] = FMT
    hdr[11] = 0                                 # bal1, below
    hdr[12:14] = tail_at.to_bytes(2, "little")  # rom_id
    hdr[14] = kind
    img[0:HDR_SIZE] = hdr
    # rom_id's tool-written fields (boot/osrom.asm: +10, +12, +14)
    img[tail_at + 10:tail_at + 12] = HDR_SIZE.to_bytes(2, "little")
    img[tail_at + 12:tail_at + 14] = payload_len.to_bytes(2, "little")
    img[tail_at + 14:tail_at + 16] = len(tail).to_bytes(2, "little")
    return img, tail_at


def balance(img):
    """Set bal1 and bal2; then prove both sums and the GLaBIOS boundaries."""
    img[11] = 0
    img[11] = (-sum(img[0:DECL_SIZE])) & 0xFF
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
    ap.add_argument("kind", nargs="?", choices=("socket",))
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
    ap.error("say which ROM to build")


if __name__ == "__main__":
    main()
