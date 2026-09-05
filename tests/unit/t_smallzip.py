#!/usr/bin/env python3
"""What kern_small does NOT have of the compression feature (SPEC.md 24.5.3).

    python3 tests/unit/t_smallzip.py

Two gates landed together and both fail SILENTLY, which is the only reason
this file exists. A `%ifdef` written round one line too few leaves the bytes
in and nothing says a word - the kernel assembles, the disk builds, the
machine boots, and the saving somebody measured is simply not there any more.
A `%ifdef` round one line too MANY takes something kern_big needed, and that
one at least tends to fail loudly; this checks it anyway, from the same map.

  OS88_ZIPVERB   Compress and Uncompress (SPEC.md 22.22, 22.23), and with
                 them COMPRESS.DRV entirely - the mod_tab row, the mod_fp
                 block, the file name and the file
  OS88_LZWIN     the LZB sliding window (SPEC.md 20.14.2.4), 256 bytes of
                 `.bss` serving the one case a kern_small disk cannot hold

**AND THE THIRD CLAIM IS THE ONE THAT MATTERS**: READING a compressed file is
untouched on both builds. That is what makes a compressed floppy the shipped
default (SPEC.md 20.13.5) - a kern_small machine boots a packed kernel,
launches packed packages and opens 'CZ' data files, it simply cannot write
one. So the decoders and the read path are asserted PRESENT on both, and a
gate that took one of them with it is the failure this half catches.

It is host-side and costs one assembly per build, both of which the symbol
reader caches for every other row in the tier.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88sym                                          # noqa: E402

# BIG-ONLY: every symbol the two gates take out. A label per gated BLOCK and
# not per routine - the point is that the block went, and naming its head is
# what says which %ifdef to look at when one of these comes back.
BIG_ONLY = {
    "fm_c_compress":  "OS88_ZIPVERB - the File menu's verb (SPEC.md 22.22)",
    "fm_c_uncomp":    "OS88_ZIPVERB - ...and its twin (SPEC.md 22.23)",
    "fm_cmpr_go":     "OS88_ZIPVERB - the thunk that fetches COMPRESS.DRV",
    "fm_uncmp_go":    "OS88_ZIPVERB - the whole of Uncompress",
    "fm_uncmp_pkg":   "OS88_ZIPVERB - ...its package arm",
    "fm_ztab":        "OS88_ZIPVERB - the verdicts, which are `.text`",
    "fm_s_uncomp":    "OS88_ZIPVERB - the menu label",
    "fm_cmpru":       "OS88_ZIPVERB - six words of `.bss`",
    "mod_f_cmpr":     "OS88_ZIPVERB - COMPRESS.DRV's name in mod_tab",
    "cmz_verb":       "OS88_ZIPVERB - the module itself (kernel/compress.inc)",
    "cmz_pack":       "OS88_ZIPVERB - ...and its encoder",
    "dskw_usize":     "OS88_ZIPVERB - its two callers are both the verb's",
    "lz_win_x":       "OS88_LZWIN - the window's entry (SPEC.md 20.14.2.4)",
    "lz_wfill":       "OS88_LZWIN - ...its refill",
    "lz_wbuf":        "OS88_LZWIN - 256 bytes of `.bss`, the whole of it",
    "dskw_czwin":     "OS88_LZWIN - the flag that picks the arm",
}

# ...AND ON BOTH, because a gate that reached one of these took the half of
# the feature that had to stay.
BOTH = {
    "lz_decomp_x":  "the decoder itself - every read of a compressed file",
    "ld_expand":    "a compressed PACKAGE expands at launch (SPEC.md 20.13)",
    "dskw_rbody":   "the transparent read (SPEC.md 20.14)",
    "api_decomp":   "OSAPI_DECOMP, which SPEC.md 20.8 rule 4 keeps in both",
}

fails = []


def syms(defines):
    # check=False: this walks the SOURCE's map and never reads an image, so
    # the byte-identity test has nothing to be about - and requiring it would
    # make the row depend on `make` having run for the other build.
    return os88sym.syms(defines=defines, check=False)


big = syms(("KERN_BIG",))
small = syms(("KERN_SMALL",))

for name, why in sorted(BIG_ONLY.items()):
    if name not in big:
        fails.append("%s is not in KERN_BIG either - %s. The gate is round one "
                     "line too many, or the symbol was renamed and this list "
                     "was not" % (name, why))
    elif name in small:
        fails.append("%s IS STILL IN KERN_SMALL - %s. The %%ifdef does not "
                     "reach it, and nothing else would have said so" % (name, why))

for name, why in sorted(BOTH.items()):
    for label, m in (("KERN_BIG", big), ("KERN_SMALL", small)):
        if name not in m:
            fails.append("%s is missing from %s - %s. READING a compressed "
                         "file is not what either gate takes (SPEC.md 24.5.3)"
                         % (name, label, why))

print("t_smallzip: %d big-only symbols, %d shared, %d in kern_big, %d in kern_small"
      % (len(BIG_ONLY), len(BOTH), len(big), len(small)))

# ...and the FILE, which is the half a symbol map cannot see. Only when the
# disks are there: `all` does not build kern_small, so a plain tree has no
# small360.img and this is a skip rather than a failure.
DISKS = (("build/small360.img", False), ("build/small.img", False),
         ("build/os8088-360.img", True), ("build/os8088.img", True))


def rootnames(path):
    d = open(path, "rb").read()
    bps = d[11] | (d[12] << 8)
    root = ((d[14] | (d[15] << 8)) + d[16] * (d[22] | (d[23] << 8))) * bps
    out = []
    for i in range(d[17] | (d[18] << 8)):
        e = d[root + i * 32:root + i * 32 + 32]
        if not e or e[0] in (0, 0xE5) or e[11] & 0x08:
            continue
        out.append(e[:11].decode("latin-1"))
    return out


seen = 0
for path, want in DISKS:
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        continue
    seen += 1
    got = any("COMPRESS" in n.upper() for n in rootnames(p))
    if got != want:
        fails.append("%s %s COMPRESS.DRV and should %s (SPEC.md 24.5.3): the "
                     "kernel and the disk have to agree, and $(SMALLDRIVERS) "
                     "is where they stop"
                     % (path, "carries" if got else "does not carry",
                        "carry it" if want else "not"))
print("t_smallzip: %d of %d disks checked for COMPRESS.DRV" % (seen, len(DISKS)))

for f in fails:
    print("  FAIL: " + f)
print("t_smallzip: %s" % ("FAILED" if fails else "ok"))
sys.exit(1 if fails else 0)
