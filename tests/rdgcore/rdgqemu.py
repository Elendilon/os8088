#!/usr/bin/env python3
"""Run a tests/rdgcore image under QEMU and print what it sent on COM1.

    python3 tests/rdgcore/rdgqemu.py IMG [--until TEXT ...] [--timeout S]

Polls the serial log for any of the --until strings (default: "Passed",
"Failed", "RDGHOST DONE", "RDGHOST BADOP") rather than sleeping a fixed time,
then kills QEMU. Exit 0 if a "Passed"-like line arrived, 1 otherwise. QEMU
only counts work here (docs/TESTING.md): correctness, never speed.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time


def run(img, until, timeout, quiet=False):
    fd, log = tempfile.mkstemp(prefix="rdgq-", suffix=".log")
    os.close(fd)
    p = subprocess.Popen(["qemu-system-i386", "-drive", "file=%s,format=raw,if=floppy" % img,
                          "-boot", "a", "-display", "none", "-serial", "file:%s" % log,
                          "-no-reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0, text = time.time(), ""
    try:
        while time.time() - t0 < timeout:
            text = open(log, "rb").read().decode("latin-1")
            if any(u in text for u in until):
                time.sleep(0.3)
                text = open(log, "rb").read().decode("latin-1")
                break
            time.sleep(0.2)
    finally:
        p.kill()
        p.wait()
        os.unlink(log)
    if not quiet:
        sys.stdout.write(text)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("img")
    ap.add_argument("--until", action="append")
    ap.add_argument("--timeout", type=float, default=60)
    a = ap.parse_args()
    until = a.until or ["Passed", "Failed", "RDGHOST DONE", "RDGHOST BADOP"]
    text = run(a.img, until, a.timeout)
    sys.exit(0 if "Passed" in text else 1)


if __name__ == "__main__":
    main()
