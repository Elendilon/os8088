#!/usr/bin/env python3
"""Build a bootable floppy that runs RealBoy's core on a bare machine.

    python3 tests/rbcore/rbimg.py ROM.GB -o build/realboy/t.img
        [--geom 360|720|1200|1440] [--mode test|bench|trace|play|idle|render] [--frames N]
        [--patch OFF:HEX]

tests/rbcore/rbhost.asm is the boot sector and the harness; this assembles
it and the core (apps/realboy/rbgen.py, then nasm; `--trace` builds the
RB_TRACE core that reports every instruction; `--patch` breaks it on purpose
for a negative control), patches the geometry and the
lengths into the boot sector, and appends harness, core and ROM. The image
is padded to the geometry's full size so any emulator takes it as a floppy.
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEOM = {360: (9, 2, 40), 720: (9, 2, 80), 1200: (15, 2, 80), 1440: (18, 2, 80)}
MODES = {"test": 0, "bench": 1, "trace": 2, "play": 3, "idle": 4, "render": 5}


def build_core(trace, out_dir):
    stem = os.path.join(out_dir, "rbcore_t" if trace else "rbcore")
    asm, binf = stem + ".asm", stem + ".bin"
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


def patch_core(core, patches):
    """OFF:HEX pairs written over the core - a deliberately broken core is
    how a gate shows it can go red (docs/WRITING-TESTS.md 1)."""
    core = bytearray(core)
    for p in patches or ():
        off, hexb = p.split(":")
        b = bytes.fromhex(hexb)
        off = int(off, 16)
        core[off:off + len(b)] = b
    return bytes(core)


def make_image(rom_path, out, geom=1440, mode="test", frames=600, core=None, host=None):
    out_dir = os.path.join(ROOT, "build", "realboy")
    os.makedirs(out_dir, exist_ok=True)
    if core is None:
        core = build_core(mode == "trace", out_dir)
    if host is None:
        host = build_host(out_dir)
    boot, body = bytearray(host[:512]), host[512:]
    body += b"\0" * (-len(body) % 512)
    rom = open(rom_path, "rb").read()
    rom += b"\0" * (-len(rom) % 512)
    spt, heads, cyls = GEOM[geom]
    boot[3] = spt
    boot[4] = heads
    boot[5:7] = (len(body) // 512).to_bytes(2, "little")
    boot[7:9] = (128).to_bytes(2, "little")
    boot[9:11] = (len(rom) // 512).to_bytes(2, "little")
    boot[11] = MODES[mode]
    boot[12:14] = frames.to_bytes(2, "little")
    img = bytes(boot) + body + core + rom
    size = spt * heads * cyls * 512
    if len(img) > size:
        sys.exit("rbimg: %d bytes do not fit a %dKB floppy" % (len(img), geom))
    img += b"\0" * (size - len(img))
    with open(out, "wb") as f:
        f.write(img)
    return len(body), len(rom)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("rom")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--geom", type=int, default=1440, choices=sorted(GEOM))
    ap.add_argument("--mode", default="test", choices=sorted(MODES))
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--patch", action="append", metavar="OFF:HEX",
                    help="overwrite core bytes at hex offset OFF (a negative control)")
    a = ap.parse_args()
    out_dir = os.path.join(ROOT, "build", "realboy")
    os.makedirs(out_dir, exist_ok=True)
    core = patch_core(build_core(a.mode == "trace", out_dir), a.patch)
    nb, nr = make_image(a.rom, a.out, a.geom, a.mode, a.frames, core=core)
    print("%s: harness %d, core 65536, ROM %d bytes, %dKB" % (a.out, nb, nr, a.geom))


if __name__ == "__main__":
    main()
