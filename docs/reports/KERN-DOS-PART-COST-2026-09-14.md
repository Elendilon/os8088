# What `kern_dos` costs a disk, and why it is not a part of `DOS.O88`

*Measured 2026-09-14 on `claude/dos-exec-investigation` at 481a291, in this
container. Every figure is `nasm -f bin` output or `os88disk.py --verify` on
the tree's own 360KB images.*

This file is a **measurement** and true of
the tree it was taken on (docs/README.md): a later `kern_dos` is a new file,
not an edit of this one.

---

## 1. The finding, in one line

**docs/plans/KERN-DOS-PLAN.md §4.1's table claims `kern_dos`-as-a-part costs
`0` system-disk bytes, and it costs 43 of the 53 clusters a 360KB system disk
has left** — more than shipping it as its own compressed file, which the same
table rejected.

Three of that table's four rows are wrong, and none of them was wrong when it
was written. What changed underneath it is
docs/plans/O88-COMPRESSION-PLAN.md, which landed afterwards and made every
package compressed by default.

---

## 2. The arithmetic

`kern_dos` here is `kerndos/kdos.asm` without `KD_GATE` — W5a's real entry,
the DOS core, the kernel's disk layer and `kdback.inc`'s doors:

| | bytes | of 46,407 |
|---|---:|---:|
| `.text` | 32,999 | 71.1% |
| `.cold` | 11,397 | 24.6% |
| `.ovlw` | 762 | 1.6% |
| `.modf` | 1,235 | 2.7% |
| **the image** | **46,407** | |
| `.bss` | 13,357 | |
| `.lowbss` | 3,328 | |

Compressed with the tree's own packer (`tools/os88lz.py`):

| | bytes | ratio |
|---|---:|---:|
| raw | 46,407 | |
| LZ4 | 38,257 | 82.4% |
| LZB | 33,537 | 72.3% |

**It compresses badly and that is expected**: O88-COMPRESSION-PLAN's own note
is that *bitmaps compress and code does not*, and this is 71% `.text`.

### 2.1 On the disk

`build/os8088-360.img` has **53 of 354 clusters free** and carries `DOS.O88`
in `APPS/` (the Makefile's `SYSROOT` — SPEC.md 92's reason one step along: a
`.COM` can be on any floppy, so the program that runs one belongs on the disk
the machine booted from). `DOS.O88` is **26,443 bytes on disk against a 31,868
byte image**, because it is whole-file compressed (flags bit 3).

| | file bytes | clusters | delta |
|---|---:|---:|---:|
| `DOS.O88` today | 26,443 | 26 | |
| `DOS.O88` + a RAW part | 78,848 | 77 | **+51** |
| `DOS.O88` + an LZ4 part | 70,656 | 69 | **+43** |
| `DOS.O88` + an LZB part | 66,048 | 65 | **+39** |
| `KERNDOS.SYS` as its own LZ4 file | 38,257 | 38 | **+38** |
| `KERNDOS.SYS` as its own LZB file | 33,537 | 33 | **+33** |

### 2.2 Why the part is WORSE than a file, by about six clusters

`tools/os88pkg.py` refuses `--compress` with parts, in as many words:

> `--compress with parts is not supported yet: a part's offset is measured
> from the start of the FILE and lives in a table INSIDE the image, so
> compressing the image and laying out its parts are circular.`

So adding a part does not only add the part's bytes — it **gives back
`DOS.O88`'s own 5,425 bytes of compression**, and the two 512-byte alignments
add a little more. The part is the worse option on the exact axis §4.1 chose
it for.

---

## 3. What §4.1's table should say

| | one: `KERNDOS.SYS` | two: a loadable half | four: a PART |
|---|---|---|---|
| system-disk clusters | **+33 to +38** | ~13 KB packed | **+39 to +43** |
| new load mechanism | a stub that expands | a loader + a mini-ABI | a stub that expands |
| `DOS.O88` stays compressed | **yes** | yes | **no** |
| versions with the box | **yes** | half | yes |

Two of §4.1's objections to option one have since been answered by work that
did not exist when it was written:

- ***"a loader"*** — the stub is written either way. The argument in
  docs/plans/KERN-DOS-PLAN.md §4.1.1 is that the part is never loaded AS a
  part: the handoff walks its bytes into extents and the stub reads them with `int 13h`. A file's bytes walk exactly
  the same way and need **no part table read first**, so the file is the
  simpler of the two at the point where the code is.
- ***"a mini-ABI between two halves that rots"*** — W5a built the ABI and it
  is not a mini one. `kerndos/kdlaunch.inc` is a single list `%include`d by
  both sides; each walks it in its own direction, sums its own copy, and the
  block carries the total, so a field added on one side only is refused at the
  entry rather than scattered into the wrong fields. There is no second
  document to drift from.

What survives unchanged is ***"versions with the box"***: a `KERNDOS.SYS`
built by the same `make` out of the same source versions with it exactly as a
part does. §4.1's table scored option one "no" on that row on the assumption
of a separately shipped binary, which is not what this tree would build.

---

## 4. The real lever is `kern_dos`'s own size, not its container

Both containers are large because the thing inside them is.
docs/plans/KERN-DOS-PLAN.md §4.1.2 said the UI half *"does not come along"*;
W4 found it does not NEED to and shipped it anyway (SPEC.md 96.38), on the ground that unreached bytes cost image size and
nothing else. On disk, image size is the whole cost.

Measured spans in this image, by what W4 and §10 already establish is
unreachable on arm 3:

| | bytes | why it goes |
|---|---:|---|
| the window half (`dos.asm` 4053–7845) | 5,675 | there is no window |
| `apps/os88con.inc` | 2,090 | `[dos_inbr]` is 1 for ever (SPEC.md 96.38) |
| `apps/dos/dosc.inc` | 1,665 | the prompt IN that window |
| `apps/dos/dosnet.inc` | 3,164 | §10: arm 3 has no packet driver |
| `apps/os88sock.inc` | 31 | nothing left to call it |
| `.ovlw` + `.modf` | 1,997 | no boot overlay, no modules (SPEC.md 96.37.2) |
| | **14,622** | |

**`apps/dos/dosh.inc` (4,083 bytes) STAYS**, and the distinction is worth
keeping straight because the two files read like a pair: `dosc.inc` is the
prompt in a window and `dosh.inc` is the **built-in commands** (SPEC.md
96.30) — the `COMMAND.COM` that is not a file, which `AH=4Bh` reaches and
which Microsoft C's `system()` is. A DOS program on arm 3 shells out exactly
as it does on arm 1.

So a cut `kern_dos` is about **31,800 bytes raw, ~26 KB LZ4, ~23 KB LZB** —
which fits the 360KB system disk with 30 clusters to spare, and is the
version worth putting on it.

### 4.1 And in RAM, which is §1's actual budget

| | bytes | KB |
|---|---:|---:|
| today's image + `.bss` + `.lowbss` | 63,092 | 62 |
| cut as above | 48,470 | 47 |
| §1's budget | 39,424 | **39** |

The measured arena at W5a is **569 KB of 640**; the cut would put it near 584.
The plan's target is 600 and its own estimate was 603, so **§6.1's levers are still
the wave that closes it** — but the gap after this cut is 8 KB rather than 23,
and it is in `.cold` and `.bss` rather than in anything a container choice can
reach.

---

## 5. What this does NOT settle

- **Where `KERNDOS.SYS` goes.** `SYSTEM/` beside the modules is the obvious
  home; the root beside `KERNEL.SYS` is the other. Nothing measured here
  prefers one.
- **The other three geometries.** 720KB, 1.2MB and 1.44MB all have room for
  either option, so the 360KB disk is the only one deciding this — which is
  CLAUDE.md's standing note that it is the geometry that runs out first.
- **Whether the stub's decoder is worth its bytes.** A compressed
  `KERNDOS.SYS` needs one; SPEC.md 2.9.13 already ships that exact trick for
  `KERNEL.SYS` and SPEC.md 20.13.7's raw tail means it expands in place with
  no margin. The A/B — an uncompressed 46-cluster file against a compressed
  33-cluster one plus ~180 bytes of stub — is not close on a disk with 53
  clusters left, but nobody has built the stub yet.
