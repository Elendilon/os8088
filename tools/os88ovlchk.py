#!/usr/bin/env python3
"""Prove no call crosses a segment boundary inside the kernel as a NEAR call.

`.ovl` and `.cold` each have their own `vstart`, so a near call between one
of them and `.text` assembles
without complaint and emits a displacement computed between two different
address spaces.  Nothing catches that: not NASM, not the linker (there isn't
one), and not a boot on the one machine whose rung QEMU can emulate.  This
walks every `section` block in kernel/ and refuses any near control transfer
whose target label lives in a different address space: call, jmp (near and
short spellings included - `short` was once swallowed by the regex as if it
were the label, which silently exempted every `jmp short`), and the
conditional branches and loops.  Local labels (.foo) bind to their parent
and cannot cross, so they fall out of the label map untested, which is
correct.

What it CANNOT see, by construction: an indirect transfer (`call bx`,
`jmp [table]`) and a code pointer stored in data.  Those stay a review rule:
a table of `.cold` pointers may live in `.text` only if cold code alone
dispatches through it (ctrl.inc's page table is the one instance).

Run it from `make`; it is worth more than any amount of reading.
"""
import re, sys, glob

CALL = re.compile(r'\b(?:call|jmp|j[a-z]{1,3}|loop[a-z]{0,2})\s+'
                  r'(?:(?:near|short)\s+)?(?:(\w+):)?([A-Za-z_]\w*)\b')
FAR = ('.ovl', '.cold')     # sections with a vstart of their own


def sections(path):
    """yield (section, line-number, source-line) with comments stripped"""
    cur = '.text'
    for n, raw in enumerate(open(path), 1):
        line = raw.split(';')[0]
        m = re.match(r'^\s*section\s+(\.\w+)', line)
        if m:
            cur = m.group(1)
            continue
        yield cur, n, line


def main():
    files = sorted(glob.glob('kernel/*.inc')) + ['kernel/kernel.asm']
    where = {}                       # label -> section it is defined in
    for f in files:
        for sect, n, line in sections(f):
            m = re.match(r'^([A-Za-z_]\w*):', line)
            if m:
                where[m.group(1)] = sect
    bad = []
    for f in files:
        for sect, n, line in sections(f):
            for m in CALL.finditer(line):
                seg, tgt = m.group(1), m.group(2)
                tsect = where.get(tgt)
                if tsect is None:
                    continue
                a = sect if sect in FAR else '.text'
                b = tsect if tsect in FAR else '.text'
                if a != b and seg is None:
                    bad.append((f, n, '%s -> %s, near' % (a, b), tgt))
    for f, n, why, tgt in bad:
        print("%s:%d: %s: %s" % (f, n, why, tgt), file=sys.stderr)
    if bad:
        sys.exit("os88ovlchk: %d call(s) cross a segment boundary near" % len(bad))
    print("os88ovlchk: no near call crosses a segment boundary")


if __name__ == '__main__':
    main()
