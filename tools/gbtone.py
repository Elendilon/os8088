#!/usr/bin/env python3
"""Build gbtone, RealBoy's sound-gate ROM: build/gbclock/GBTONE.GB.

    python3 tools/gbtone.py

tools/gbprof/gbtone.asm says what it plays; tests/gbsound.py listens to it.
rgbds is tools/gbclock.py's, fetched and built at the same pinned commit.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gbclock  # noqa: E402

SRC = os.path.join(ROOT, "tools", "gbprof", "gbtone.asm")


def build():
    asm, link, fix = gbclock.rgbds()
    os.makedirs(gbclock.OUT, exist_ok=True)
    obj = os.path.join(gbclock.OUT, "gbtone.o")
    rom = os.path.join(gbclock.OUT, "GBTONE.GB")
    subprocess.check_call([asm, "-o", obj, SRC])
    subprocess.check_call([link, "-o", rom, obj])
    subprocess.check_call([fix, "-v", "-p", "0xFF", "-t", "GBTONE", rom])
    os.remove(obj)
    return rom


if __name__ == "__main__":
    print(build())
