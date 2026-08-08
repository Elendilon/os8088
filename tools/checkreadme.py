#!/usr/bin/env python3
"""checkreadme.py README.TXT - the two rules the system disk's manual must keep.

README.TXT ships in the root of the system disk (SPEC.md 19.6 leaves it
visible and read-only) so the machine can explain itself with no second disk
and no host computer to read it on. The reader on those disks is Note Pad, and
Note Pad imposes both of these. Neither fails loudly on its own: a file one
byte too long is REFUSED with 'Too big' and shows nothing at all, and an
over-wide line simply wraps, which reads as a formatting mistake rather than
as a rule that was broken. So they are checked here, before the file is used.

  1. WIDTH. Note Pad's default window is 260px wide. Take off the 1px border,
     the 8px left margin and the 14px scroll bar and 235px are left for text,
     which is 29 whole 8px cells. The file is authored to 28 so that a line
     ending in a space, or one glyph of drift in a future layout change, still
     does not wrap.

  2. SIZE. np_load opens the note to NP_MAXKB (16KB) and reads the file into
     it; a longer file comes back FERR_BIG and the note is left alone. The
     size that matters is the file AS IT LANDS ON THE DISK - with CRLF line
     endings, which the Makefile applies at build time - so that is what is
     measured here, not the length of the source file.

Also checked: plain printable ASCII. np_load drops anything outside 32..126
that is not a line break, so a stray tab or a typographic dash is a character
that silently disappears between the disk and the screen.

Exit 1 on any finding.
"""

import sys

MAXCOL = 28          # authored width; Note Pad's default window fits 29
NP_MAXKB = 16        # apps/notepad: NP_MAXKB, the load ceiling in KB


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: checkreadme.py README.TXT", file=sys.stderr)
        return 2
    path = sys.argv[1]
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        print(f"checkreadme: cannot read {path}: {e}", file=sys.stderr)
        return 1

    bad = 0
    text = raw.replace(b"\r\n", b"\n").decode("latin-1")
    lines = text.split("\n")

    for n, line in enumerate(lines, 1):
        if len(line) > MAXCOL:
            print(f"{path}:{n}: {len(line)} columns, over {MAXCOL}: {line!r}")
            bad += 1
        for ch in line:
            if not 32 <= ord(ch) <= 126:
                print(f"{path}:{n}: character {ord(ch)} is not printable "
                      f"ASCII and Note Pad will drop it")
                bad += 1
                break
        if line != line.rstrip():
            print(f"{path}:{n}: trailing whitespace")
            bad += 1

    ondisk = len(text.replace("\n", "\r\n").encode("latin-1"))
    limit = NP_MAXKB * 1024
    if ondisk > limit:
        print(f"{path}: {ondisk} bytes on disk (CRLF), over Note Pad's "
              f"{limit}-byte ceiling - it would refuse the file entirely")
        bad += 1

    if bad:
        print(f"checkreadme: {bad} problem(s)")
        return 1
    print(f"checkreadme: {len(lines)} lines, widest {max(len(l) for l in lines)}"
          f", {ondisk} bytes on disk ({limit - ondisk} spare)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
