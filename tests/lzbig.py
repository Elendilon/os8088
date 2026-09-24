#!/usr/bin/env python3
"""File > Compress and Uncompress on files PAST 64KB (SPEC.md 20.15.4, 22.22.4).

tests/lzcomp.py is the verb on files that fit a segment; this is the same
assertion - the machine's file against `os88lz.lzb_compress_machine`'s, BYTE
FOR BYTE - on the sizes that used to answer "Too large". Each subject is a
different half of what had to change:

  BIG1.TXT   ~100KB that packs to UNDER 64KB. The encoder's SOURCE slides
             (cmz_sslide) and its output never has to; the read-back is the
             decoder crossing on its OUTPUT only, which it always could.
  BIG2.TXT   ~160KB that packs to OVER 64KB. Both of the encoder's segments
             slide, and Uncompress then hands the kernel's transparent read a
             'CZ' file whose PACKED bytes cross a segment - the decoder's
             checkpoint (SPEC.md 20.14.5.1), which nothing else in the tree
             reaches, because every shipped file is LZ4 and packed under 64KB.
  TAIL.DAT   40KB of text, then 70KB of noise: the cut falls before the noise and the
             raw tail is longer than the T word can count, so the verb must
             say `Its end won't compress` and leave the file alone. The
             mirror is asked first and must refuse too, or the fixture is
             the wrong one.

Then BOTH big files are uncompressed and must come back as the original
bytes - the round trip is the only assertion that covers the decoder, the
32-bit read and the 32-bit write in one sentence.

**A 1.44MB machine**, `os8088_xt_vga_144`: the three fixtures are 330KB
between them and every 720KB profile here is 40-cylinder (docs/
DOS-DEBUGGING.md's trap), so a 360KB or 720KB disk would either not hold them
or hand the verb a short read and a wrong answer.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import os88flush                                       # noqa: E402
import os88lz                                          # noqa: E402
import os88build                                       # noqa: E402
import os88marty                                       # noqa: E402
import os88mouse                                       # noqa: E402
import dispcp                                          # noqa: E402
import lzcomp                                          # noqa: E402
from lzcomp import S, FM_IUNCOMP, compress, cz, say    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MACHINE = "os8088_xt_vga_144"
QUIET = 400                     # guest seconds for one big verb: a 160KB
                                # parse is ~1,600 cycles a byte, ~55 s, and
                                # the reads and writes are as much again


def half_text(n, seed):
    """n bytes that pack to about half - tests/unit/t_lzfmt.py's generator,
    so the host leg and this one are about the same kind of file"""
    sys.path.insert(0, os.path.join(HERE, "unit"))
    import t_lzfmt
    return t_lzfmt.half_text(n, seed)


def noise(n, seed):
    x, out = seed, bytearray()
    while len(out) < n:
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((x >> 16) & 0xFF)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    for f in ("build/os8088.img",):
        if not os.path.exists(os88build.at(f)):
            sys.exit("lzbig: %s is missing - run `make` first" % f)

    big1 = half_text(100000, 7)
    big2 = half_text(160000, 11)
    tail = half_text(40000, 3) + noise(70000, 5)
    want1 = cz(os88lz.lzb_compress_machine(big1), len(big1))
    want2 = cz(os88lz.lzb_compress_machine(big2), len(big2))
    try:
        os88lz.lzb_compress_machine(tail)
        sys.exit("lzbig: the mirror packs TAIL.DAT, so the refusal leg would "
                 "test nothing - the fixture's tail must be past 64KB")
    except ValueError:
        pass
    if len(want1) >= 0x10000 or len(want2) <= 0x10000:
        sys.exit("lzbig: the fixtures no longer straddle 64KB packed (%d, %d)"
                 % (len(want1), len(want2)))
    say("lzbig: BIG1 %d -> %d, BIG2 %d -> %d (packed past 64KB), TAIL %d"
        % (len(big1), len(want1), len(big2), len(want2), len(tail)))

    # Per-run and removed on the way out: the verbs WRITE this disk, so a kept
    # image would hand the next run files that are already compressed
    # (tests/lzcomp.py's note on the same trap).
    img = "/tmp/lzbig-%d.img" % os.getpid()
    d = os.path.join(os88build.at("build"), "lzbig")
    os.makedirs(d, exist_ok=True)
    disk = os88marty.scratch_disk(
        img,
        lzcomp.stage(d, "BIG1.TXT", big1),
        lzcomp.stage(d, "BIG2.TXT", big2),
        lzcomp.stage(d, "TAIL.DAT", tail),
        size=1440)
    fails = []

    with os88marty.launch(os88build.at("build/os8088.img"),
                          apps=disk, machine=MACHINE) as m:
        os88marty.settle(m, gate=os88marty.desktop_up)
        mo = os88mouse.Mouse(marty=m)
        fl = os88flush.Flush(marty=m)
        dispcp.open_drive(m, mo, S, os88marty.settle, "B")
        wins = dispcp.win_list(m, S)
        if not wins:
            sys.exit("lzbig: no Disk window after double-clicking B:")
        wx, wy = dispcp.win_rect(m, S, wins[-1])[:2]

        def leg(tag, name, want, item=None, expect="Compressed"):
            kw = {"quiet": QUIET}
            if item is not None:
                kw["item"] = item
            t = compress(m, mo, wx, wy, name, fails, **kw)
            got = fl.volume(1).read(name)
            ok = t.startswith(expect) and got == want
            say("  %-9s %s  %r  (%d bytes, wanted %d)"
                % (tag, "ok " if ok else "BAD", t, len(got), len(want)))
            if not ok:
                i = next((k for k in range(min(len(got), len(want)))
                          if got[k] != want[k]), min(len(got), len(want)))
                fails.append("%s %s: said %r, %d bytes against %d, first "
                             "differing byte %d"
                             % (tag, name, t, len(got), len(want), i))

        leg("big1", "BIG1.TXT", want1)
        leg("big2", "BIG2.TXT", want2)
        leg("tail", "TAIL.DAT", tail, expect="Its end")
        leg("unbig2", "BIG2.TXT", big2, item=FM_IUNCOMP,
            expect="Uncompressed")
        leg("unbig1", "BIG1.TXT", big1, item=FM_IUNCOMP,
            expect="Uncompressed")

    try:
        os.remove(img)
    except OSError:
        pass
    for f in fails:
        say("  FAIL: " + f)
    say("lzbig: %s" % ("FAILED" if fails else "ok"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
