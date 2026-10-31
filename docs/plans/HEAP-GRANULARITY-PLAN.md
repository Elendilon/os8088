# HEAP-GRANULARITY-PLAN — claims finer than a kilobyte

**STATUS: RESEARCH, NOTHING BUILT.** This document is an investigation and a
recommendation. Every figure marked *measured* was taken on `heap-size` cut
from `elendilon` at `3cf34ee` (2026-10-31), host-side, off `build/`. Every
figure marked *estimated* is arithmetic.

The question: claims have been whole KB since SPEC.md 50 was written, and the
reason was to make the Task Manager's figures easy to show. What would 512-byte
or 256-byte claims take, what would break, what would they cost, and what do we
recommend?

## 0. The answer in five lines

1. **The allocator already counts in paragraphs.** `MC_PARA` is paragraphs
   (`kernel/memory.inc:76`). The scan, the 64KB DMA page test, the compaction
   mover, `mem_regrow` and `mem_region_reloc` have no KB assumption. KB exists
   only at the doors (`mem_claim_1`'s `shl ax, 6` at `memory.inc:975`,
   `mem_regrow`'s at `:4334`), in the byte-to-KB rounders (`mem_bytes_kb`,
   `mem_bytes_kb_x`), and in the readers (`mem_avail`, `mem_sum_kb`,
   `osapi_sys_kb`, the Task Manager).
2. **512 bytes is the right unit, and the floor.** Every base the scan can
   produce is the floor, the top, a claim edge or a 64KB page edge. All of
   them stay 512-aligned when every size is a multiple of 32 paragraphs. Guard
   6b (`kernel/kernel.asm:9303`, `%if MEM_PARA_KB % 32`) already states the
   rule a finer unit must keep. **256 bytes breaks it.** `HDD.DRV` has no
   bounce path for an unaligned buffer, three packages refuse an unaligned
   base, and the loader's region must stay a sector multiple anyway. So 256
   buys almost nothing on packages (§2.1) and costs the hard disk.
3. **Keep the public API in KB.** All 311 claim-family call sites in 118 files,
   the C SDK and the parts standard keep working unchanged. Finer granularity
   is a **kernel-internal** change for the claims the kernel sizes from a byte
   count: package regions, driver images and the kernel's own caches. No
   `PKG_FMT` bump. One `DRV_VER` bump (§3.2).
4. **What it buys: about 0.5–3 KB of heap in an ordinary session, for
   roughly 60–100 resident bytes** (*estimated*, §4). The biggest single item
   is the heap's own tail. On today's kern_big the floor is 96.5 KB, so the top
   512 bytes of every machine's heap can never be claimed (*measured*:
   `HEAP 0x1820`).
5. **The Task Manager stays 4 characters wide.** It computes in paragraphs and
   rounds once, and a single dynamic formatter shows `0.5K`..`9.5K` exactly and
   `10K`+ rounded, with totals closed by cumulative rounding (§5).

## 1. Where the KB lives today

### 1.1 The allocator: only at the edges

| site | what it does | at 512 |
|---|---|---|
| `mem_claim_1` `memory.inc:970-977` | `cmp ax,1024 / shl ax,6`: KB to paragraphs, the one door every claim goes through | takes the internal unit (§3.1) |
| `mem_claim_dma_x` `:822` | DMA head, KB to paragraphs | unchanged: the head stays KB from the API, and the internal heads (§1.3) are whole halves |
| `mem_compact` `:3787` | the pending claim's KB to paragraphs | follows `mem_claim_1`'s unit |
| `mem_regrow` `:4334` | the new KB to paragraphs | public stays KB. The icon store grows a KB a step and can stay so |
| `mem_avail` `:4752` | paragraphs to KB, **rounded down** | unchanged for packages: rounding down is what makes "claim what AVAIL said" always fit |
| `mem_sum_kb` / `mem_owned_kb` `:4803-4873` | sum paragraphs, then one `shr 6` | unchanged, but under-reports by up to 0.5K per total (§5) |
| `osapi_sys_kb` `SK_HEAP` `:5749` | `(top-base) >> 6`, truncated | the heap's odd half has to be reported (§5.2) |
| `mem_bytes_kb` `:5972`, `mem_bytes_kb_x` `:6011` | bytes to KB, rounded up | a half-KB twin (§3.1) |
| `mem_hiclaims` `:3566-3571` (kern_mega) | `MC_PARA >> 6` to the KB the pool claim gets, **truncating**, while the copy after it moves the whole `MC_PARA` | **a defect a finer unit exposes**: a 1.5K claim gets a 1K pool block and the copy overruns it. Needs `add ax,63` first, 3 bytes on kern_mega only |

Paths with **no** KB assumption: the overlap scan, the DMA page bump (paragraph
arithmetic at `:1025-1043`, `:1563`, `:2588`), `mem_bcopy` (64-paragraph
chunks with an exact short tail, `:1658`), the compaction walk, `mem_rr_walk`,
`mem_hifit`, shed and purge, `mega_dmapb`, and hibernate's line stepper.

### 1.2 Base alignment: why 512 is free and 256 is not

The heap floor is rounded to 512 (`mem_floor_ax`, `add ax,31 / and al,0xE0`)
and the top is KB-aligned (`int 12h`). Every candidate base `mem_claim_1`
tries is one of the floor, `top − size`, a claim's end, a claim's base −
size, a page floor, or a page floor − head. Compaction's destinations are
base + Σsizes and top − Σsizes. **All of these stay 512-aligned exactly when
sizes and heads are multiples of 32 paragraphs.** So 512 granularity keeps the
Hard Rule ("every disk-visible base is 512-byte aligned") with no new code.

At 256 bytes, bases become 256-aligned and the following fail:

- **`HDD.DRV`** (`drivers/hdd/hdd.asm:331-334`, `~612-618`;
  `drivers/hdd/hdsec.inc:7-9`). `hd_bios_run` answering 0 means CF=1, and
  there is no bounce: *"forcing a run of 1 would issue exactly the straddling
  transfer"*. The loader reads a package image into its region through
  `dsk_xfer`'s `.drv` arm, which hands the driver the raw ES:BX. So a
  hard-disk launch whose region straddles a 64KB page fails.
- **Three packages assert the alignment and refuse otherwise**:
  `apps/os88type.inc:806` (`ty_open`, the faces), `apps/pixel/pxpump.inc:34`
  (`px_dmaclaim`) and `apps/audio/audio.asm:325`. These would become
  intermittent refusals depending on heap layout.
- **Guard 6b** fails by design.

What would cope: the kernel's own BIOS floppy path (`dsk_runcap` answers 0
for an unaligned base and `dsk_xfer`'s `.bounce` stages one sector through
`dsk_secbuf`) and the file layer's staging (`dskw_runmax`, SPEC.md 18.4.1).
That is one extra `int 13h`, ~400 ms, per crossed page, on the path that copes.

### 1.3 The kernel's own byte-sized claims

The kernel caches whose byte size is not a whole KB *(measured from the
constants)*:

| claim | bytes | 1K claim | waste at 1K | waste at 512 |
|---|---:|---:|---:|---:|
| FAT window `MEM_P_FATW`, kern_big (`disk.inc:5791`, 9 sectors) | 4,608 | 5K | **512** | 0 |
| read-ahead `MEM_P_RAHB` (`disk.inc:7181`, 9 sectors, DMA head = whole) | 4,608 | 5K | **512** | 0 |
| dirw window `MEM_P_DIRW` (`disk.inc:7063`, n × 4.5K) | n × 4,608 | ⌈4.5n⌉K | 512 when n is odd | 0 |
| `VIEW_KB` per Disk window (`files.inc:1216`, holds 1,600) | 1,600 | 2K | 448 | 448 |
| assoc cache (`assoc.inc:1934`, sectors → ⌈n/2⌉K) | 512 × n | | 512 when n is odd | 0 |
| compression `cmz_kb` (`compress.inc:2039`, `(n>>10)+1`) | n | | **a whole KB too many** when n is an exact multiple (a separate defect, fix it either way) | |

The read-ahead's DMA head becomes 9 halves. The downward page bump puts its
base at `page_end − 4.5K`, which is still 512-aligned.

## 2. What finer claims would recover

### 2.1 Package regions (`kernel/loader.inc:1140-1198`)

`ld_alloc` already rounds image + bss to **512** (`add 511 / and 0FE00h`). The
loader's sector-granular read needs that rounding. `mem_bytes_kb_x` then rounds
it again to a KB. Over the 59 packages in `build/` *(measured)*:

| unit | total slack | mean per launch |
|---|---:|---:|
| 1 KB (today) | 30,373 | 515 |
| 512 | 16,037 | 272 |
| 256 | 16,037 | 272: **no better**, because the 512 rounding stays for the read |

Examples (bytes per open instance, 1K → 512): Calculator 1,004 → 492, Tracker
976 → 464, Task Manager 907 → 395, Texpad 826 → 314, Note Pad 788 → 276,
Browser 758 → 246. A package already on a KB boundary gains nothing: Paint 367,
Sheet 299, DOS 61. **About 243 bytes per open instance on average.**

### 2.2 Driver images (`kernel/driver.inc:3370`, `drv_bss` `:3596`)

Over 25 `.DRV` files, image + `DRV_H_BSSP` *(measured)*: 13,660 at 1K (mean
546), 7,004 at 512, 3,676 at 256. Per loaded driver, 512 saves **~270 bytes**
on average. Examples: ETHER 1,008, FORMAT 901, HTTPFS 945, RAMDISK 924 at 1K.
256 would save another ~130 per driver, the only place where 256 beats 512,
and §1.2 rules it out.

### 2.3 The heap's tail

`mem_floor_ax` rounds the floor to 512 and `mem_top` is whole KB. When the
floor sits on a half (today's kern_big: `HEAP 0x1820` = 96.5 KB), every
claim is a KB multiple measured from one end or the other. So **the odd 512
bytes can never be claimed**, whatever the layout. It moves with the kernel's
size: kern_small is at 60.0 today and loses nothing, and the next size pass
can flip either build. SPEC.md 28.4.7 calls it *"dead memory"*. At 512
granularity it is ordinary heap.

### 2.4 Modules: leave them on the KB

On-demand modules (CTRL, HIBER, WIN95, FILECP, FDLG) **use the KB slack as
their bss** (MODULE-SELFCONTAIN-PLAN 3, `%error` asserts at `kernel.asm:8645,
8801, 8815, 8831, 8839`, and the 1024-boundary pads at `:8692`, `:8769`).
At 512 *(measured)*:

| module | image | bss | slack at 1K | slack at 512 |
|---|---:|---:|---|---|
| CTRL (big) | 15,092 | 164 | 268, fits | 268, fits |
| HIBER (big) | 7,169 | 594 | 1,023, fits | 511, **cannot ever fit** |
| WIN95 (big) | 1,440 | 126 | 608, fits | 96, **fails** |
| FILECP (small) | 1,821 | 76 | 227, fits | 227, fits |
| FDLG (small) | 1,587 | 16 | 461, fits | 461, fits |

A module's claim exists only while it is in use, and its "waste" is mostly bss
it needs anyway. So `mod.inc` keeps calling the **KB** rounder (`:434`, `:521`,
`:766`) and nothing in the module machinery changes. The alternative is a
per-module bss word in `mod_tab` (MODULE-SELFCONTAIN-PLAN 3.2, 8–12 bytes)
plus re-tuned pads, for at most a few hundred bytes while a module is
loaded. Not worth it.

### 2.5 A session, added up (*estimated*)

kern_big with three windowed packages and two drivers open:

| item | bytes back |
|---|---:|
| the heap tail, when the floor is on a half (today) | 512 |
| FAT window | 512 |
| read-ahead | 512 |
| 3 packages × ~243 | ~730 |
| 2 drivers × ~270 | ~540 |
| **total** | **~2.8 KB** |

kern_small has a 1 KB FAT window and no read-ahead. A 128 KB machine with two
packages and no drivers gets ~0.5 KB, plus 512 on any day its floor lands on a
half. That machine has 50 KB of heap, so it is still worth having.

## 3. What it would take

### 3.1 Kernel (the work)

1. **One internal unit at `mem_claim_1`.** The cleanest shape: `mem_claim_1`
   and `mem_compact` take **half-KB** in AX (`cmp ax, 2048 / mov cl, 5 /
   shl`). The public KB doors (`osapi_mem_claim*`, `mmf_osapi_mem_claim`, and
   the internal `mem_claim_x` family that kernel callers with KB constants
   use) gain a `shl ax, 1` on the way in. A matching **half-unit door** for the
   three byte-sized callers: `mem_claim_hi_h` for the loader and driver
   loader, and `mem_claim_h` / `mem_claim_dma_h` for the FAT window,
   read-ahead and dirw. The `jae .fail0` bound and its trampoline must stay in
   short reach (the routine's own note at `:1000`).
2. **`mem_bytes_hk_x`**, the half-KB twin of `mem_bytes_kb_x`: `dec / mov cl,
   9 / shr / inc`, 7 bytes. It returns CL = 9. `loader.inc:1217`'s `shl ax,
   cl`, which rebuilds `I_SIZE` in bytes, **stays correct unchanged** because
   it reads CL. The two ownership fences that use `I_SIZE` (`fsx.inc`,
   `instance.inc`) get a tighter bound, which is the safe direction. The
   saturation at 64 KB still holds: 128 halves << 9 is 0 with CF set.
3. **Driver loader**: `driver.inc:3370` and `drv_bss` `:3605` use the half
   rounder. `DRVR_KB` either becomes half-KB units (rename `DRVR_HK`, and
   `osapi_drv_classk_x` converts with `inc / shr 1` for its KB answer) or
   stays KB as a reported figure beside the claim. `DRV_MAX_KB` checks against
   80 halves.
4. **The caches**: FAT window, read-ahead and dirw ask in halves. Their
   steal thresholds (`DSK_FATW_MINK`) double.
5. **Reporting**: `osapi_sys_kb` gains `SK_HEAPH`, the heap in half-KB, or
   equivalently a flag bit for "plus a half". `SYSKB_SIZE` 20 → 22, an
   append, so no ABI break. `SK_HEAP` stays as it is (floor KB) so
   `apps/dos/dos.asm:8128`'s `SK_KERN + SK_HEAP` identity keeps cancelling.
6. **kern_mega**: the `mem_hiclaims` ceiling (§1.1), 3 bytes, kern_mega
   only.

### 3.2 Tools and the ABI

- **`tools/os88drv.py:166-168` strips a driver's trailing zeros down to the
  1024 rung**, and `drv_bss` refuses (`.nofit`) when image + bss exceeds the
  claim sized from the file. At a 512-unit claim, a driver stripped to the 1K
  rung can be refused. `os88drv.py` moves to the 512 rung in the same diff,
  and that is a **`DRV_VER` bump**: an old driver can be refused by the new
  kernel. It is mechanical, and every driver is in the tree. `drivers/os88drv.inc:29-30`
  also says the kernel "GROWS" the claim, which contradicts `drv_bss` and
  SPEC.md 51.1.2; correct it in the same diff.
- **No `PKG_FMT` bump**: the `.o88` header is bytes and the loader rounds
  them. The public contracts do not change, so `tools/abilock.py --update`
  is needed only if a contract comment is reworded.
- The parts standard (`apps/os88partsbody.inc`), `crt0.asm` and `os88.h`
  round to KB themselves and keep doing so. Not fingerprinted, unaffected.

### 3.3 SPEC.md first (CLAUDE.md: update it before the change)

50 ("KB-granular" and "the heap's unit is the kilobyte" become "the PUBLIC
unit"), 50.2's record table, 51.1.2 (the strip rung), 28.4.7 (the dead
half-KB paragraph is withdrawn), 28.4.10's closing identity, 20.9
(`SK_HEAPH`), and the five places §1.2 lists that state "every claim is whole
KB" (around SPEC.md 51604, 9828, 36278, 103502, 362).

## 4. The kernel byte cost (*estimated*; measure the SPAN, not the rung)

| piece | kern_big | kern_small |
|---|---:|---:|
| `mem_claim_1` / `mem_compact` unit change | ~0–4 | ~0–4 |
| `shl ax,1` on the KB doors (claim, hi, dma, dma_hi, compact's pass-through) | ~10 | ~8 |
| half-unit doors (hi, plain, dma) | ~12–18 | ~10–14 |
| `mem_bytes_hk_x` | 7 | 7 |
| driver loader and `DRVR_*` conversion | ~10–15 | ~10–15 |
| caches switched to the half doors | ~0–6 | ~0–4 |
| `SK_HEAPH` in `osapi_sys_kb` | ~6 + 2 `.bss` | ~6 + 2 |
| **total** | **~50–70** | **~45–60** |
| kern_mega `mem_hiclaims` ceiling | +3 | |

Mostly `.cold`, so it is resident. Against it: ~0.5–3 KB of heap given back
in every session (§2.5). By the banner rule this is a clear trade: *N ≈ 60
resident bytes buys M ≈ 1–5× N of heap in normal use*. The win is
**runtime** heap, not footprint, so `kernsize` will not show it. The gate
has to read the heap (§6).

256 bytes adds nothing on the kernel side, but needs: a bounce path in
`HDD.DRV` (estimated 60–120 bytes of driver, plus one extra `int 13h` per
crossed page), the loader keeping its 512 rounding (so packages gain nothing),
three packages rewritten to round their own bases, and every module reworked
(§2.4). The measured extra over 512 is ~130 bytes per loaded driver. **Refuse
256.**

## 5. The Task Manager: accurate in the same width

### 5.1 What goes wrong if only the kernel changes

From the survey of `apps/taskmgr/taskmgr.asm`:

- `tm_hkb` (`:4397`) says *"the heap deals in whole KB, so this divides
  exactly"* and truncates each claim. Group totals (`tm_gkb`) then
  undercount by up to 0.5K per claim, while `SK_CLAIM` truncates once per
  total. **IVT+BIOS + System + Programs ≠ RAM used**, which
  `tests/megatmmem.py` leg 2 asserts exactly.
- The process page shows a region as ⌈bytes/1024⌉ and the memory page as
  ⌊para/64⌋, so a 19.5K region reads 20K on one page and 19K on the other.
- **A sub-KB claim prints `-`** (`tm_kcol`, `tm_memcol_kb0` print 0 that
  way), and a group whose claims are all under 1K totals 0 and is
  **hidden** (`:5246`, `:5446`, `:5458`). That is SPEC.md 28.4.6's "memory
  on no row" defect again.
- `TM_LOWKB` = 2 (`:239`) bakes in the dead half-KB argument.
- RAM free = ⌊H⌋ − ⌊C⌋ but AVAIL = ⌊H − C⌋, which disagree by 1K whenever
  frac(H) < frac(C).

### 5.2 The fix: paragraphs in, one rounding out, no new width

Every row is locked to 25 characters by `%error` and every KB field is 4
characters. The system font has no `½` (glyphs 32–126 only,
`kernel/font.inc:22`). So:

1. **Carry paragraphs, not KB.** `tm_hkb` stops dividing. `tm_gkb[]`
   becomes a paragraph sum (a word holds 1 MB in paragraphs, so the sums
   fit). The process page's MEM is `SSI_SIZE` in paragraphs plus the data
   claims, from the raw `CLS_PARA` records the snapshot already returns,
   instead of `SSI_KB`. Both pages then quote the same number by
   construction.
2. **One dynamic formatter, `tm_pfig`, 4 characters**, modelled on
   `tm_kfig`'s existing `d.dM` arm:
   - `< 10K`: `d.dK`, exact at 512 granularity (`0.5K`, `2.5K`, `9.5K`), so
     **a 512-byte claim never prints `-` and no group vanishes**.
   - `10K–999K`: `nnnK`, **rounded to nearest**, so the error is at most
     0.5K in 10K (5%), falling as values grow.
   - `≥ 1000K`: the existing `d.dM`.
   The half digit only exists where it is a large share of the number. Where
   it is a small share, the cell drops it rather than gaining a column.
3. **Totals that close: cumulative rounding.** The convention `SK_*` already
   uses (SPEC.md 20.9: *"rounded cumulatively"*). Each row prints
   `round(running_sum) − round(previous_running_sum)`, so the printed rows
   always add up to the printed total, and every row is within 0.5K of its
   true value. That restores 28.4.10's "SIZE sum + AVAIL = Ram total" and
   `megatmmem`'s identity *exactly*. It also retires `TM_LOWKB`'s fudge:
   IVT+BIOS becomes `1.5K + EBDA` rounded in the same chain.
4. **The heap total** reads `SK_HEAPH` (§3.1.5).

Cost: `tm_pfig` is ~40–60 bytes of TASKMGR.O88, plus a few bytes where
`tm_hkb`'s callers change. **Zero resident bytes.** The small build
(SPEC.md 28.12) keeps only the process list's MEM column and the RAM/HEAP pair,
so it takes the formatter and the paragraph MEM and nothing else.

Other displays need nothing: every package that prints `OSAPI_MEM_AVAIL`
(Pixel, Sheet, Browser, isoTron, Win16, Redline) still gets floor-KB, which
remains true and claimable. `tools/heapmap.py` already prints `%.1fK`.

## 6. Tests

**Rows that cover what this touches** (run them in the final pass, per the
Testing section): `soak -k 'heap*' 'reg*' drvmove sndmove tmowner heapdrv
megatmmem small128 kernresident pins pinsrt trkcompact`. Of these, `heapcheck`'s
model (`tests/heapcheck.py:198-308`, `//64`) and `tools/heapwhatif.py`'s
`PARA = 64` constructor need their KB arithmetic made paragraph-exact.

**New gates, each broken on purpose first** (docs/WRITING-TESTS.md 1):

1. **`t_heapgran`** (fast, host-side): assemble-time already holds guard 6b at
   32 paragraphs. Add a host check that every kernel claim constant and every
   package's `roundup512(image+bss)` maps to a whole number of halves, and
   that `os88drv.py`'s strip rung equals the kernel's claim unit. Red if
   `os88drv.py` keeps the 1024 rung.
2. **`heaptail`** (soak, MartyPC): boot kern_big with the floor on a half,
   claim until refused, and assert the free remainder is **0**, not 512.
   Red on today's kernel.
3. **`heapalign`** (soak): open a dozen packages in varying order, read
   `mem_tab` through `os88sym`, and assert every base is 32-paragraph
   aligned. This catches anyone later reaching for 256.
4. **`tmhalf`** (soak): a package holding a 512-byte claim shows `0.5K` on
   both Task Manager pages, its group is present, and IVT+BIOS + System +
   Programs = RAM used exactly. `megatmmem` already gives the identity half.
5. **Driver strip A/B**: a `.DRV` stripped to the 1K rung loads on the old
   kernel and is refused `.nofit` on the new one. That is the reason for the
   `DRV_VER` bump.

## 7. Recommendation

**Do 512, kernel-internal, public API unchanged, in three waves:**

1. **Wave 1, the kernel** (§3.1 items 1, 2, 5, 6): the half unit at
   `mem_claim_1`, the half-KB rounder, the loader on it, the heap tail
   claimable, `SK_HEAPH`, the kern_mega ceiling. With the SPEC.md edits
   first. Fix `cmz_kb`'s over-claim on the way (independent, free).
2. **Wave 2, drivers and caches**: driver images on the half unit,
   `os88drv.py` to the 512 rung, `DRV_VER` bump, and the FAT window,
   read-ahead and dirw asking in halves.
3. **Wave 3, the Task Manager**: paragraph sums, `tm_pfig`, cumulative
   rounding, `TM_LOWKB` retired. It can land after wave 1 because wave 1 alone
   only adds halves the old Task Manager rounds down. That is inaccurate but
   harmless. Better to land it with wave 1 so the totals never disagree on a
   shipped build.

**Do not** move modules (§2.4), **do not** change the package-facing KB
API (311 call sites, the C SDK and the parts standard gain nothing they can
use), and **refuse 256** (§1.2, §4).

Open questions for the owner:

- A new public `OSAPI_MEM_CLAIM_H` (AX = halves) costs ~6 bytes for the
  cell. Is it worth offering to packages that size from bytes (Note Pad's
  growing note, Browser's buffers)? The recommendation is to wait for a
  package that asks, because nothing in the survey needs it.
- `DRVR_KB`: rename it to half units, or keep a KB field for the Control
  Panel's driver column? Either works; renaming is fewer bytes.
