#!/usr/bin/env python3
"""Fetch the Game Boy test ROMs RealBoy is gated on, at pinned SHA-256s.

    python3 tools/getgbtest.py            # fetch into build/gbtest/, verify
    python3 tools/getgbtest.py --check    # verify what is there, fetch nothing
    python3 tools/getgbtest.py --path NAME

Blargg's CPU, timing and HALT-bug tests, from retrio/gb-test-roms at a
pinned commit. NONE IS EVER COMMITTED: they are fetched like
tools/getapple2rom.py's ROMs, every file is checked against the hash below,
and `make clean` spares build/gbtest/ so a rebuilt tree needs no network.
docs/plans/REALBOY-PLAN.md section 7 says which gate each one is.
"""
import argparse
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "build", "gbtest")
REPO = "https://github.com/retrio/gb-test-roms"
REV = "c240dd7d700e5c0b00a7bbba52b53e4ee67b5f15"
FILES = {
    "cpu_instrs/cpu_instrs.gb": "8c5e12f41e0ba5bbca796944f92ffe6de28809198682c4332e38d1b3cf56fcf2",
    "cpu_instrs/individual/01-special.gb": "fe61349cbaee10cc384b50f356e541c90d1bc380185716706b5d8c465a03cf89",
    "cpu_instrs/individual/02-interrupts.gb": "fb90b0d2b9501910c49709abda1d8e70f757dc12020ebf8409a7779bbfd12229",
    "cpu_instrs/individual/03-op sp,hl.gb": "ca553e606d9b9c86fbd318f1b916c6f0b9df0cf1774825d4361a3fdff2e5a136",
    "cpu_instrs/individual/04-op r,imm.gb": "7686aa7a39ef3d2520ec1037371b5f94dc283fbbfd0f5051d1f64d987bdd6671",
    "cpu_instrs/individual/05-op rp.gb": "d504adfa0a4c4793436a154f14492f044d38b3c6db9efc44138f3c9ad138b775",
    "cpu_instrs/individual/06-ld r,r.gb": "17ada54b0b9c1a33cd5429fce5b765e42392189ca36da96312222ffe309e7ed1",
    "cpu_instrs/individual/07-jr,jp,call,ret,rst.gb": "ab31d3daaaa3a98bdbd9395b64f48c1bdaa889aba5b19dd5aaff4ec2a7d228a3",
    "cpu_instrs/individual/08-misc instrs.gb": "974a71fe4c67f70f5cc6e98d4dc8c096057ff8a028b7bfa9f7a4330038cf8b7e",
    "cpu_instrs/individual/09-op r,r.gb": "b28e1be5cd95f22bd1ecacdd33c6f03e607d68870e31a47b15a0229033d5ba2a",
    "cpu_instrs/individual/10-bit ops.gb": "7f5b8e488c6988b5aaba8c2a74529b7c180c55a58449d5ee89d606a07c53514a",
    "cpu_instrs/individual/11-op a,(hl).gb": "0ec0cf9fda3f00becaefa476df6fb526c434abd9d4a4beac237c2c2692dac5d3",
    "instr_timing/instr_timing.gb": "646067b3d6c79fda810e9c3f1cb7c0efd5abb0a7ac06437c54e65720c15d9925",
    "mem_timing/mem_timing.gb": "791cb418fd054b482a6ada5017e2405b96c2373a0f3914c6b23afeee76fa98ce",
    "halt_bug.gb": "ddebfb81f992132954a5580e16cfb97346a4e061c762634d7701328e23fea7c6",
}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def check():
    bad = [f for f, h in FILES.items()
           if not os.path.exists(os.path.join(DEST, f)) or sha(os.path.join(DEST, f)) != h]
    return bad


def fetch():
    src = os.path.join(DEST, ".src")
    if not os.path.isdir(os.path.join(src, ".git")):
        os.makedirs(DEST, exist_ok=True)
        subprocess.check_call(["git", "clone", "-q", "--no-checkout", REPO, src])
    subprocess.check_call(["git", "-C", src, "checkout", "-q", REV, "--", "."])
    for f in FILES:
        os.makedirs(os.path.dirname(os.path.join(DEST, f)), exist_ok=True)
        with open(os.path.join(src, f), "rb") as i, open(os.path.join(DEST, f), "wb") as o:
            o.write(i.read())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--path", metavar="NAME", help="print a fetched file's path")
    a = ap.parse_args()
    if a.path:
        hits = [f for f in FILES if a.path in f]
        if len(hits) != 1:
            sys.exit("getgbtest: %r matches %d files" % (a.path, len(hits)))
        print(os.path.join(DEST, hits[0]))
        return
    if not a.check and check():
        fetch()
    bad = check()
    if bad:
        sys.exit("getgbtest: missing or wrong: " + ", ".join(bad))
    print("getgbtest: %d ROMs verified in %s" % (len(FILES), DEST))


if __name__ == "__main__":
    main()
