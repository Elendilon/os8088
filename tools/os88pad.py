#!/usr/bin/env python3
"""Pad kernel.bin out to the image rung the kernel published in its header.

The kernel's ladder charges `.text` + `.bss` rounded up to a whole 512 bytes
(KIMG_PARA, docs/KERNEL-MEMORY.md).  The FILE, though, is `.text` alone --
`.bss` is nobits and costs nothing on disk -- so the boot sector's contiguous
read lands sector K at offset K*512, which is somewhere inside `.bss` rather
than at the paragraph the ladder calls FAT_SEG.

Padding the file to KIMG_PARA*16 closes that gap, and two things fall out of
it that are worth more than the sectors it costs:

  * anything appended to kernel.bin lands exactly at FAT_SEG, in the SAME
    read, so a boot-time overlay needs no second loop in the boot sector and
    no gap constant -- KERNEL_SECTORS still falls out of the file size.
  * the whole of `.bss` is zeroed before kmain runs.  `nasm -f bin` zeroes
    nothing and the kernel never cleared it, which is why `[fdlg_win]` had to
    live in `.text` as a `dw 0` (fdlg_grab reads it on the machine's very
    first mouse press).  The splash is safe through it: viddet and splash keep
    all their data in `.text` precisely because they run during the load.

The kernel cannot do this to itself.  Padding inside `.text` would grow
KTEXT_SIZE, which grows KIMG_PARA, which grows the padding -- there is no
fixed point -- so the number leaves the assembly at offset 4 of the image and
this acts on it from outside.
"""
import sys

HDR_KIMG = 4                    # word: KIMG_PARA, published by kernel.asm


def main(argv):
    if len(argv) != 2:
        sys.exit("usage: os88pad.py <kernel.bin>")
    path = argv[1]
    with open(path, 'rb') as f:
        img = f.read()
    if len(img) < HDR_KIMG + 2:
        sys.exit("os88pad: %s is too short to carry a header" % path)
    want = int.from_bytes(img[HDR_KIMG:HDR_KIMG + 2], 'little') * 16
    if want == 0:
        sys.exit("os88pad: %s publishes KIMG_PARA = 0 -- wrong file?" % path)
    if len(img) > want:
        sys.exit("os88pad: %s is %d bytes, past its own %d-byte image rung"
                 % (path, len(img), want))
    if len(img) == want:
        return
    with open(path, 'ab') as f:
        f.write(b'\0' * (want - len(img)))


if __name__ == '__main__':
    main(sys.argv)
