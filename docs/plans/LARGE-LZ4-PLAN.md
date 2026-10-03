# Large LZ4 — decompression past 64KB, in one stream

> **STATUS: INVESTIGATED AND PROTOTYPED, NOT LANDED.** Every byte figure below
> was measured by assembling the change (`tools/kernsize.py` for the kernel, the
> package's own `.bin` for package-side code). Unless a figure is marked
> *estimate*, it is measured. The prototype is
> `docs/plans/LARGE-LZ4-PLAN.patch` (`git apply` on the commit this file
> landed on). It passes the 17 soak rows listed in §6. It also passes a new
> fixture whose carve is 92KB, and the shipped loader refuses that fixture.
> SPEC.md has **not** been updated. CLAUDE.md requires the SPEC to change
> before the code does, so §7 lists what is owed before any of this ships.

## 1. The answer

**The decoder already crosses 64KB on its output, for both formats, and on its
input for LZB.** BEVERLY.MOD (116,085 bytes) has decoded as one stream since
SPEC.md §20.14.5. Three walls are left, and they are what keeps biting:

| wall | where | what it does today |
|---|---|---|
| **LZ4 input is one segment** | `kernel/lz.inc` entry (`or al, al / jz .early`) | an LZ4 stream that *packs* to 64KB or more is refused. `os88lz.cz_wrap` therefore stores such a file **plain** (`CZ_SRCMAX`), and `os88cz.py` says *"try --lzb, or split it"* |
| **`OSAPI_DECOMP` takes a 16-bit length** | the cell zeroes `AH` (§20.13.3) | a **package** cannot hand the decoder more than 64KB of stream in either format, even though the kernel's own file read can (`lz_decomp_big`, §20.14.5.1) |
| **the parts carve is under 128 sectors** | `op_size`'s `cmp dx, 128`, `op_cap`/`op_want`/`op_bend` are words, `os88pkg.py` mirrors it | the eager run of a parted package, packed **or** unpacked, must stay under 64KB. Programs that would pass it are forced into lazy rows, private packers and loaders (§3) |

**What lifting all three costs, measured:**

| change | kern_big | kern_small | a package |
|---|---:|---:|---:|
| LZ4 input crosses a segment | **+37** `.cold` | **+37** `.cold` | — |
| `OSAPI_DECOMP` takes 24 bits of input (AL bit 7) | **+6** `.cold` | **+6** `.cold` | — |
| parts carve past 64KB, up to 1,920 sectors | — | — | **+14** plain table, **−6** with `OP_COMP`, **+6** with `OP_COMP`+`OP_LAZY` |
| host tools: drop `CZ_SRCMAX`, raise the packer's bound | — | — | — |
| **total** | **+43 `.cold`** (41,877 → 41,920; the rung has 107 → 64 left) | **+43 `.cold`** (25,466 → 25,509; 134 → 91 left) | **≤ +14** |

Nothing is resident in `.text`, `.bss` or `.lowbss`, there is no new API slot,
and `KERN_SIZE` does not move on either kernel. The LZ4 change also makes the
decoder's hot path *shorter* (§4.1): **−1.9% instructions executed on
BEVERLY.MOD and −2.5% on 60KB of text**. That is a count and not a timer; the
time on the 5150 is still to be measured (PERFORMANCE.md rule 4).

Packages that use parts today, rebuilt with the prototype loader: `dosload`
2,187 → 2,193 (+6), `csload` 2,256 → 2,262 (+6), `pxstein` 2,895 → 2,900 (+5),
`wdload` 1,436 → 1,430 (−6).

**And a latent bug in both host encoders, found on the way (§5), costs 0 bytes
to fix.**

## 2. Why one stream and not split volumes

Splitting a stream into blocks that each fit a segment is the workaround every
consumer has reached for, and the tree has measured what it costs twice:

- **BEVERLY.MOD in two 61,440-byte blocks: +18,766 bytes, 44% of the whole
  win** (docs/plans/O88-COMPRESSION-PLAN.md 13.4). A MOD's sample data matches
  back tens of KB into itself, and a block boundary throws that history away.
- **The kernel image in two LZ4 blocks: +1,076 bytes, 2 sectors**
  (`tools/os88kz.py`'s header). Machine code matches mostly locally, so here
  the cost is small (§8.3).

The split pays in ratio on exactly the data that is big enough to need it.
Making the decoder cross the boundary costs 43 bytes once, against one block
header and lost history per 64KB of every file, for good.

## 3. What it unlocks — the consumers that are bent today

From a sweep of `apps/` and `tools/`, each checked at its source:

| consumer | bent how | which wall |
|---|---|---|
| **Pixelstein** part 3 (levels, 9,831 bytes) | LAZY and stored **plain**, with a hand RLE: *"the eager run would have been 111 + 20 = 131 unpacked sectors, past the 128"* (`pxstein.asm` 25-31) | carve |
| **Pixelstein** part 4 (art, 37,440 → 8,890) | LAZY, packed by `pxsart.py` and expanded by a private `pxl_art` | carve |
| **Clear Skies** part 1 (title art, 10,480 → 4,487) | LAZY, packed by `csart.py` and expanded by a private `csl_art`: *"eager bands would make 131 and op_size would refuse the package"* (`csload.asm` 203-217) | carve |
| **Clear Skies** world rows | LAZY *"to keep op_size's 128-sector bound clear"* (`csload.asm` 219-227) | carve (one of two reasons) |
| **DOS box** part 2 (`kern_dos`, ~29KB) | LAZY; an eager pair is ~45 + ~29KB and *"would be refused outright before a sector was read"* (`dosload.asm` 26-30). It would stay lazy anyway, because nothing ever fetches it | carve (not the deciding reason) |
| **Word** part 1 | its origin is capped at `WD_P1ORG + part1 ≤ 65,024`, *"127 sectors, op_size's bound"* (`wdload.asm` 13-17) | carve |
| **Video player** resident blocks | a block packed past 61,440 (`BLK_PACKED_MAX`) is written **stored** (`os88vid.py` 2030-2044) | cell |
| **`'CZ'` files** | an LZ4 file packing to 64KB or more is stored plain (`cz_wrap`), and `os88cz.py pack` refuses it | LZ4 input |

The comments in `csload.asm`, `pxstein.asm` and `csart.py` also give a second
reason: *"a lazy row cannot also be OP_COMP"*. **That reason is stale.**
SPEC.md §20.12.7.4 lifted the refusal. With the carve bound gone, both art
streams can be ordinary eager `OP_COMP` rows, and `csl_art`, `pxl_art` and the
two private pack paths can be deleted. Each package then *gives back* bytes;
how many is not measured here.

## 4. The design, and what each byte buys

### 4.1 LZ4 input crosses a segment — +37 `.cold`

§20.14.5.1 lets an LZB input cross through a **checkpoint**. `LZ_F_TSI` is
`0x8000` until the tail is within reach. `lz_at` slides `DS` up by 32KB when
`SI` reaches the top half, and the per-symbol compare is unchanged. LZ4 was
kept out for one stated reason: its literal **runs** go through `lz_copy`,
whose slow arm bumps `DS` by 64KB when `SI` wraps, and a bump there would leave
the checkpoint describing the wrong segment.

**The fix is to make sure no legitimate literal run can wrap, rather than to
teach the wrap about the checkpoint:**

1. **The entry refusal goes** (`jz .reach / or al, al / jz .early`, −6 bytes).
2. **The literal length is read inline** rather than through `call lz_len`, so
   that a run of 15 or more is the only one that reaches the extension loop.
   The hot path loses a `call`, a `ret` and a taken `jne`, and gains an
   untaken `je`. That is where the −1.9% / −2.5% instruction counts come from.
3. **A run of 16KB or more** (`cmp ch, 0x40` in the extension path, so a
   shorter run never executes it) is claimed whole by `lz_take`. It is then
   copied **16KB at a time**, with `lz_at` called between pieces to slide `DS`
   and re-arm the checkpoint. `SI` is under `0x8000` + 258 when a piece
   starts, so a piece ends under `0xC102`: no piece can wrap, and nothing the
   arm reads afterwards (an offset and at most 257 length bytes) can either.
   A run under 16KB fits the existing 32KB in-line budget, which is
   §20.14.5.1's own argument unchanged.
4. **A hostile stream still only reads.** Every write is still bounded by
   `lz_take` and the match-offset test. A run that slides past its own tail
   drives `K` to 255 and runs out of declared output, exactly as LZB's does.

The `'CZ'` file read needs nothing more. `dskw_rbody` already enters at
`lz_decomp_big` with `AH:CX`, and §20.14.2 says the LZ4 refusal *"comes from
the decoder rather than from a size test here"*. **0 bytes there.**

### 4.2 The published cell takes 24 bits — +6 `.cold`, no slot

`lz_decomp_x` currently zeroes `AH`. The prototype makes **`AL` bit 7** mean
*"AH is the input length's high byte"*:

```
lz_decomp_x:
    test al, al
    js .big
    mov ah, 0
.big:
    and al, 0x7F
lz_decomp_big:
```

It needs **no new slot** (a new `OSAPI_FCELL` would be 6 bytes of `.text` plus
4 of `.cold`, and `.text` is the scarcer of the two). It is also **safe on an
older kernel by refusal**: `cmp al, LZ_LZB / ja .early` already refuses an
unknown format, so a package that sets bit 7 on a kernel before this change gets
`CF=1` and not a misread. SPEC.md §20.8 rule 4 is satisfied, because the cell is
unchanged in both kernels.

### 4.3 The parts carve passes 64KB — package-side, ≤ +14

`apps/os88partsbody.inc` measures the run in a few 16-bit byte counts. The
prototype changes their *units* rather than their *width* wherever it can:

| word | was | now |
|---|---|---|
| `op_cap` | bytes the read asks for | **paragraphs** — `op_read`'s `DI` counts paragraphs, so its chunk loop needs no 32-bit counter, and `op_runkb` becomes `(R + cap + 63) >> 6` |
| `op_rpara` (R) | `(ubytes − bytes + 512 + 15) >> 4` | `(usecs − secs + 1) << 5` — the same number from sector counts, so `op_bytes` and `op_ubytes` are no longer needed |
| `op_bend` | 16 bits | 32 bits, its high word in **`op_bytes`'s old slot** (`op_bendh`), so no offset in the bss chain moves and `apps/cc/crt0.asm` is untouched |
| `op_want` | 16 bits | 32 bits, in the word `op_tail` left unnamed (§20.12.7.3) |
| the bound | `secs < 128` (both ends) | `secs < OP_SECMAX` = **1,920** (960KB): R plus the read, in paragraphs, still fits a word on a volume with 32KB clusters |

`op_unpack` and `op_seg` were already segment arithmetic and need nothing.
`op_fetch` writes `op_want`'s high word and converts its capacity to
paragraphs. A **single part** stays at most 65,024 bytes, because `op_size`
refuses a larger one with `jc .ovfd`. The prototype makes `os88pkg.py` say so
at pack time (it accepted 65,535). **Contiguous plain rows are contiguous in
the carve**, so an asset over 64KB can already be two adjacent rows read as one
block. Only a *compressed* one still pays a stream boundary per 63.5KB (§8.1).

The packer's two 128-sector refusals become `OP_SECMAX`. The `OP_XMS` span
keeps its 128-sector bound: `op_xload` is a separate loop, no package uses
`OP_XMS`, and nothing here needs it.

### 4.4 Host tools — 0 bytes

- `os88lz.cz_wrap`: delete the `CZ_SRCMAX` refusal. An LZ4 `'CZ'` file then
  packs at any size.
- `os88pkg.py`: `OP_SECMAX` in place of 128, and a per-part ceiling of 0xFE00.
- `os88cz.py`: its *"the LZ4 stream is over 64KB - try --lzb, or split it"*
  refusal goes.
- `os88vid.py`: `BLK_PACKED_MAX` can rise once the player passes bit 7. The
  player-side cost is not measured.

## 5. The latent encoder bug — 0 bytes to fix

**Both host encoders can write a match of 64KB or more, which the kernel cannot
decode.** `lz4_compress` and `lzb_compress` call `Chains.find` with
`maxlen = mend − i` / `n − i`, uncapped. `kernel/lz.inc` counts a length in one
register (`lz_len`'s `CX`, `.gamma`'s `AX`), so a longer match wraps. Measured
through the harness (§6):

| subject | host decoder | kernel decoder |
|---|---|---|
| 65,541 zero bytes, LZ4 | round-trips | decodes |
| **65,545 zero bytes, LZ4** | round-trips | **refuses (CF=1)** |
| 70,000 zero bytes, LZB | round-trips | **refuses** |

The build's only check is `cz_wrap`'s round trip through the **host** decoder,
so a file containing a 64KB run of one byte would ship compressed and answer
`FERR_IO` on the machine. **Nothing shipped is affected today**: BEVERLY.MOD is
the only file over 64KB unpacked, and its longest match is 9,919 bytes. The
machine's own encoder caps at `CMZ_MAXM` = 0x3FF0 and is not affected.

The fix is in the prototype: `LZ_MAXLEN` = 0xFFFF passed as `find`'s cap in
both encoders, and an LZ4 literal run over 0xFFFF raises `ValueError`. Nothing
but a match can break a run, so that case is stored plain. **It is worth
landing on its own, ahead of everything else here**, together with a
`t_lzfmt` subject that would have caught it (a 70KB run of one byte, in both
formats, round-tripped through the *kernel's* decoder rather than only the
host's).

## 6. How it was verified

1. **A host harness runs `kernel/lz.inc` itself** under Unicorn (an 8086
   emulator, `pip install unicorn`), against `os88lz.py` as the reference. The
   corpus:
   - text of 120, 200 and 400KB, packing to 75, 125 and 246KB;
   - seven fixtures with 16–65KB of incompressible noise placed mid-stream at
     varied offsets, so the 16KB-piece path runs (it ran 2–4 pieces on the
     fixtures that needed it);
   - BEVERLY.MOD, and BEVERLY.MOD doubled (232KB → 82KB).

   Every one decodes byte for byte, **with the source read in place**,
   `U − P` above its destination, which is how the kernel actually uses it.
   200 randomly corrupted 150KB streams produced **no write past the declared
   length**. The shipped decoder refuses every LZ4 case over 64KB packed,
   which is the negative control.
2. **The 17 soak rows that cover this code pass on the prototype.** The kernel,
   parts and host-tool changes were all applied at once:
   `mseg360 msegz msegz360 msegnomem mseglazy msegxms rehome rehomemove
   rehomemove360 rehomeabort lzload lzfile lzfence lzmod lzmod-dialog
   lzmod-nohint lzmod-lzb` — 17 passed, 0 failed.
3. **A wide carve.** MSEG's part 1 was padded with 45,000 bytes of noise and
   part 2 with 40,000 bytes of text, and the same `tests/multiseg.py` was run:
   - plain carve: 179 sectors;
   - `--comp`: 146 sectors packed, 179 unpacked;
   - parts at segments `0x8620`…`0x9CC0`, **92KB** of carve.

   Result: **`MSEG 7/7 OK` on all four of 360 / 1440 × plain / `--comp`**,
   with the 360KB disk's 512-byte head slack applied. With the **shipped**
   loader, the same file is refused at launch (`ld_status` 4, `LD_EABORT`),
   so the row tells the two apart.

**Not done:** no machine row exercises an LZ4 `'CZ'` *file* over 64KB packed
through `OSAPI_FILE_READ`. The harness covers the decoder; the read path is
unchanged code, but a row should still say so. No field timing has been taken.

## 7. What is owed before this lands

In this order, because SPEC.md moves first:

1. **The encoder fix (§5) on its own**, with its `t_lzfmt` subject.
2. **SPEC.md**: §20.14.5 / §20.14.5.1 (*"LZ4 is still one segment of input"*
   becomes the piecewise literal copy), §20.13.3 (the cell's `AL` bit 7),
   §20.14.2's second refusal bullet, §20.12.2–4 (the carve's units and
   `OP_SECMAX`), and §20.12.7's *"it is under 64KB because..."* wording. Also
   the `OSAPI_DECOMP` comment in `apps/os88api.inc`, which still says
   *"the input need not [cross], because a stream over 64KB is a file that
   compressed badly"*. That has been untrue for LZB since §20.14.5.1.
3. **Gates**: `t_lzfmt` asserts *"an LZ4 source is still one segment"* and
   has to flip (it is the one row the prototype turns red). A `msegwide` row
   (the §6.3 fixture, made by the Makefile rather than by hand) belongs beside
   `mseg360`/`msegz`. A file row should read an LZ4 `'CZ'` file over 64KB
   packed.
4. **Field timing** of the inlined literal length on the 5150, against
   PERFORMANCE.md's 50.6 cycles a byte.
5. **Then the consumers**: Pixelstein's art and levels and Clear Skies' title
   art become eager `OP_COMP` rows, and `pxl_art`/`csl_art` and the private
   pack paths go.

## 8. Considered and not recommended

### 8.1 A single part past 65,024 bytes — estimate +60–90 package bytes

The row's `len` and `zkb` are words. The free bits are in `kind` (1 bit used)
and `flags` (5 used). A part's high length bits could ride there, with
`op_size`, `op_lazykb`, `op_unpack` and `op_fetch` taking 32-bit lengths and
calling the cell with bit 7. **Not prototyped.** It only buys a *compressed*
asset over 63.5KB its full history, because plain ones are already contiguous
across rows (§4.3). Nothing in the tree wants it yet.

### 8.2 A raw tail over 64KB — estimate ~25 `.cold`

`T` is a word, so a file whose net-expanding suffix is over 64KB (good data and
then 70KB of noise) cannot be packed at all. `Compress` says
*"Its end won't compress"* and `cz_wrap` stores it plain. Widening `T` is a
**stream-format** change: a flag to carry, both decoders, both host encoders,
`compress.inc`'s writer, and `lz_tail` copying more than a segment. The case is
a file that is mostly noise at its end. **Not worth a format change today.**

### 8.3 One stream for the kernel image — estimate +40–60 bytes of `.boot2`

`boot2.asm`'s `kz_expand` is a separate, unbounded LZ4 copy, about 60 bytes,
that never leaves a segment. That is why `os88kz.py` cuts the kernel into
61,440-byte blocks, which costs 1,076 bytes, 2 sectors, about 71 ms of read on
the 5150. Crossing would need both pointers renormalised per sequence and a
borrow on a back-reference. That is a test in the decode loop, and at
39.9 cycles a byte over 799 ms of decode, a few percent of slowdown eats most
of the 71 ms. The blob is transient, so the bytes are free; the time is not.
**Not recommended without a field measurement saying otherwise.**

### 8.4 A multi-block container

Still refused on §20.14.5's measurement (44% of BEVERLY.MOD's win). It is the
thing this plan exists to avoid.
