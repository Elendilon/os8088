#!/usr/bin/env python3
"""Build a bootable floppy that runs RealBoy's core on a bare machine.

    python3 tests/rbcore/rbimg.py ROM.GB -o build/realboy/t.img
        [--geom 360|720|1200|1440] [--mode test|bench|trace] [--frames N]
        [--trace]

tests/rbcore/rbhost.asm is the boot sector and the harness; this assembles
it and the core (apps/realboy/rbgen.py, then nasm; `--trace` builds the
RB_TRACE core that reports every instruction), patches the geometry and the
lengths into the boot sector, and appends harness, core and ROM. The image
is padded to the geometry's full size so any emulator takes it as a floppy.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEOM = {360: (9, 2, 40), 720: (9, 2, 80), 1200: (15, 2, 80), 1440: (18, 2, 80)}
MODES = {"test": 0, "bench": 1, "trace": 2}


def build_core(trace, out_dir):
    asm = os.path.join(out_dir, "rbcore.asm")
    binf = os.path.join(out_dir, "rbcore_t.bin" if trace else "rbcore.bin")
    subprocess.check_call([sys.executable, os.path.join(ROOT, "apps/realboy/rbgen.py"), asm])
    cmd = ["nasm", "-f", "bin", "-w+error", "-I", os.path.join(ROOT, "apps/realboy/"),
           "-o", binf, asm]
    if trace:
        cmd.insert(3, "-DRB_TRACE")
    subprocess.check_call(cmd)
    data = open(binf, "rb").read()
    assert len(data) == 65536, len(data)
    return data


def build_host(out_dir):
    binf = os.path.join(out_dir, "rbhost.bin")
    subprocess.check_call(["nasm", "-f", "bin", "-w+error",
                           "-I", os.path.join(ROOT, "apps/realboy/"),
                           "-I", os.path.join(ROOT, "tests/rbcore/"),
                           "-o", binf, os.path.join(ROOT, "tests/rbcore/rbhost.asm")])
    return open(binf, "rb").read()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("rom")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--geom", type=int, default=1440, choices=sorted(GEOM))
    ap.add_argument("--mode", default="test", choices=sorted(MODES))
    ap.add_argument("--frames", type=int, default=600)
    a = ap.parse_args()
    out_dir = os.path.join(ROOT, "build", "realboy")
    os.makedirs(out_dir, exist_ok=True)
    core = build_core(a.mode == "trace", out_dir)
    host = build_host(out_dir)
    boot, body = bytearray(host[:512]), host[512:]
    body += b"\0" * (-len(body) % 512)
    rom = open(a.rom, "rb").read()
    rom += b"\0" * (-len(rom) % 512)
    spt, heads, cyls = GEOM[a.geom]
    boot[3] = spt
    boot[4] = heads
    boot[5:7] = (len(body) // 512).to_bytes(2, "little")
    boot[7:9] = (128).to_bytes(2, "little")
    boot[9:11] = (len(rom) // 512).to_bytes(2, "little")
    boot[11] = MODES[a.mode]
    boot[12:14] = a.frames.to_bytes(2, "little")
    img = bytes(boot) + body + core + rom
    size = spt * heads * cyls * 512
    if len(img) > size:
        sys.exit("rbimg: %d bytes do not fit a %dKB floppy" % (len(img), a.geom))
    img += b"\0" * (size - len(img))
    with open(a.out, "wb") as f:
        f.write(img)
    print("%s: harness %d, core 65536, ROM %d bytes, %dKB" % (a.out, len(body), len(rom), a.geom))


if __name__ == "__main__":
    main()
