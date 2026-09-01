#!/usr/bin/env python3
"""Build the two `*.O88` files SPEC.md 19.1's size rule is about.

    python3 tests/pkgbig/mkfix.py build/pkgbig

Neither is a package and neither is meant to be. The rule under test types a
file by its EXTENSION and its SIZE, before anything reads a byte of it, so
what a gate needs is exactly a `*.O88` that is not a program:

  BIGPKG.O88   70,144 bytes  - over APP_MAX_SIZE, under PKG_FILE_HI's 1MB.
                               The mount must type it 1 and the LOADER must
                               refuse it, saying `Too large`.
  HUGE.O88  1,048,576 bytes  - exactly PKG_FILE_HI << 16, the first size the
                               mount itself refuses. It must type 0 and reach
                               the loader as `Bad package`.

The pair is the experiment and neither file alone is one: BIGPKG passing on
its own is also what a rule that types EVERYTHING as a package looks like,
and HUGE passing on its own is also what the old `high word == 0` rule looks
like. Only both together say the bound is where it is meant to be.

Both carry a valid v3 header - magic, version, the dispatcher, a name - so
that the size is the ONLY thing either could be refused for. `image` cannot
equal the file size at these lengths (it is a 16-bit field), which is why
`os88disk.py --raw` has to ship them: they are unbuildable through the
validator on purpose, and that is the same 16-bit assumption stated one layer
up.
"""
import os
import struct
import sys

APP_MAX_SIZE = 0xF000           # SPEC.md 3 - the primary segment's image+bss
PKG_FILE_HI = 16                # SPEC.md 3 - the mount's file bound, <1MB

BIG = 70144                     # 137 sectors: over 60KB, well under 1MB
HUGE = PKG_FILE_HI << 16        # 1,048,576 - the first size the mount refuses


def header(name: str, total: int) -> bytes:
    """A v3 header (SPEC.md 20.2) whose only lie is the image-size word.

    It has to lie: the field is 16 bits and these files are not. The loader
    never reads it - both are refused on size, in step 1, before the peek -
    and that is precisely what the gate asserts.
    """
    h = bytearray(32)
    struct.pack_into("<HBBHHHH", h, 0,
                     0x384F,                # magic 'O8'
                     3,                     # version
                     0,                     # flags: no icon, no assoc
                     0,                     # link base
                     0x20,                  # entry: first byte after the header
                     min(total, 0xFFFF),    # image size - see the docstring
                     0)                     # bss
    h[12:16] = bytes((0xFF, 0xD5, 0xCB, 0x00))     # the dispatcher
    h[16:16 + len(name)] = name.encode("ascii")
    return bytes(h)


def write(path: str, name: str, total: int) -> None:
    body = header(name, total) + b"\x90" * (total - 32)
    assert len(body) == total
    with open(path, "wb") as f:
        f.write(body)
    print("mkfix: %-12s %9d bytes" % (os.path.basename(path), total))


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "build/pkgbig"
    os.makedirs(out, exist_ok=True)
    write(os.path.join(out, "BIGPKG.O88"), "BIGPKG", BIG)
    write(os.path.join(out, "HUGE.O88"), "HUGE", HUGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
