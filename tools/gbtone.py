#!/usr/bin/env python3
"""Build RealBoy's own gate ROMs into build/gbclock/: GBTONE.GB (the sound
gate) and GBSAVE.GB (battery RAM and the MBC3 clock).

    python3 tools/gbtone.py [gbtone|gbsave]

tools/gbprof/gbtone.asm says what it plays (tests/gbsound.py listens to it);
tools/gbprof/gbsave.asm what it counts (tests/gbsave.py reads it). rgbds is
tools/gbclock.py's, fetched and built at the same pinned commit.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gbclock  # noqa: E402

# name: the rgbfix arguments past the title (the cartridge's header)
ROMS = {
    "gbtone": [],
    "gbsave": ["-m", "0x10", "-r", "3"],    # MBC3+TIMER+RAM+BATTERY, 32KB
}


def build(name="gbtone"):
    asm, link, fix = gbclock.rgbds()
    os.makedirs(gbclock.OUT, exist_ok=True)
    src = os.path.join(ROOT, "tools", "gbprof", name + ".asm")
    obj = os.path.join(gbclock.OUT, name + ".o")
    rom = os.path.join(gbclock.OUT, name.upper() + ".GB")
    subprocess.check_call([asm, "-o", obj, src])
    subprocess.check_call([link, "-o", rom, obj])
    subprocess.check_call([fix, "-v", "-p", "0xFF", "-t", name.upper()] + ROMS[name] + [rom])
    os.remove(obj)
    return rom


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else "gbtone"))
