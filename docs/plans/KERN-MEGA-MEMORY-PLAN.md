# KERN-MEGA-MEMORY-PLAN - kern_mega's memory consolidation round

**Status: IN PROGRESS** (branch `claude/protected-mode-memory-consolidation-k1kjao`,
cut from `elendilon` at `8eac6506`, 2026-10-25). This file is the authority for
the round: the goal, what is true of the tree today, every decision the owner
took and the assumptions under them, the waves in the order they are taken, and
what each wave came to as it is built. `docs/plans/KERN-MEGA-PLAN.md` 14.72 is
the short pointer to it and records how the round was arrived at.

A bare "14.nn" below is a section of KERN-MEGA-PLAN.md; a bare "§" is SPEC.md.

---

## 0. The goal, and the rules of the round

**The owner's words.** kern_mega *"was using memory frivolously"*: the Victory
286's Task Manager showed ~374K "Above 1MB" on a 4MB machine, most of it not
memory the kernel needs (14.70). The end goal, in the owner's words:

> *On a 4MB system that gives 3.3MB above 1MB, a single claim could take all of
> the 3.3MB the system isn't using, and then all of the 640K the system isn't
> using in a second claim - or if we can bridge the two into one claim, all the
> better.*

and *"the goal here is to shrink the overall usage."*

**The rules the owner set for doing it (2026-10-25):**

1. **The end result is what ships.** No interim wave ships on its own, so a
   wave need not work alone if a later wave completes it. Do not bend a wave
   out of shape to make it stand alone.
2. **Do not create debt for the end state.** No new pinned memory, no new
   refusal, no compatibility break that a later round would have to undo.
3. **Every piece of code ever written for the OS is in this repository**, so
   converting all of it is in scope; there is no "older style" program to
   accommodate.
4. **Old hibernate images may be refused** by the new kernel.
5. **The order is this plan's to choose**; the whole round lands before any of
   it ships, the 1MB machine included.
6. **Work through the waves**; stop only for a blocker that needs the owner,
   or for a change of plan that alters these goals.

**What "done" means:**

- every byte of extended memory the system is not using can be had by ONE
  claim (`OSAPI_MEM_HUGE`), and the same claim reaches conventional memory too,
  bridged across the 640K-1MB hole, leaving a **64K** conventional reserve;
- a program can ASK how much that is, exactly, before claiming;
- the kernel's fixed footprint above 1MB falls from ~256K to ~66K: the GDT
  is ~4K, the LDT starts at 2K and grows, the HMA is pool, and there is no
  padding;
- nothing in the pool is pinned but a module whose action is running;
- a DOS trip that has nowhere to park falls back to a hibernate, which works
  with the pool full;
- `tests/megahigh.txt` is empty and cannot grow.

---

## 1. What is true of the tree today (the knowledge base)

Read off `kernel/mega.inc`, `kernel/memory.inc`, `kernel/hiber.inc` and the
build at `8eac6506` unless a measurement says otherwise.

### 1.1 The layout above 1MB

**This table is the layout the round STARTED from** (`8eac6506`). MC2
replaced it: the tables and the code are at the top of RAM and the pool runs
from 1MB - see *MC2 as built* in 7.

| linear | what | size | source |
|---|---|---|---|
| 100000h | the HMA, kept free for DOS's real-mode half and `kern_dos` | 64K | KERN-MEGA-DOS-PLAN 7, 14.25 |
| 110000h (`MEGA_GDT_LIN`) | the GDT, 8,192 entries, IDENTITY: entry i = base i x 128 | 64K | 3.1 |
| 120000h (`MEGA_LDT_LIN`) | the LDT, 2,048 entries: 0-1279 a STATIC code alias per 512 bytes of conventional memory (index = segment / 32), 1280-2047 the allocator | 16K | 13.3, `mega_ldt_alloc` |
| 124000h (`MEGA_IDT_LIN`) | the IDT | 2K | |
| 125000h (`MEGA_COLD_LIN`) | `.cold`, then `.mega` at its rung's distance (`MEGA_HI_LIN`), then the park's scratch (`MEGA_SCR_OFF`, `MPS_SIZE`) | ~58K (`.cold` 42,207 + `.mega` 14,698 + 1,484) | `mega_coldup`, KERN-MEGA-SEGMENTS-PLAN |
| to 140000h (`MEGA_XPOOL`) | padding, there only because the pool's base wants a low word of 0 | ~50K | |
| 140000h up | the pool: `mx_tab` (96 records, `.lowbss`), 1KB granular, offsets in KB from `MEGA_XPOOL` | the rest, capped at 15,360K | `mega_xminit` |

Every linear address of the fixed area is an ASSEMBLY CONSTANT today, except
the tables' when `mega_tlowf` moved them (below). `mega_gdtr`, `mega_idtr`,
`mega_ldtlin` and the bootstrap window (`mega_bwin`) are variables in `.text`
that hold them, and the 286 reset path reloads from those variables.

**The 1MB machine.** When the BIOS reports less extended memory than the
fixed area needs, `mega_tlowf` claims **82KB of CONVENTIONAL memory**
(top-down, pinned, `MEM_K_MTBL`) and lays the GDT, LDT and IDT out there in
the same shape. Such a machine has no pool, `.cold` stays low and hibernate
greys (14.17). Verified on 86Box `vm/286-525`, an AMI 286 at 1MB with no
extended memory reported. **This is the 1MB machine's largest single cost**,
and MC7 is what cuts it.

### 1.2 The pool's rules

- `mx_alloc` places in two directions (13.4.1): the kernel's own blocks
  (`MX_KOWN` FEh) and driver images (`MX_KDRV` FDh) FIRST FIT FROM THE TOP,
  everything else from the pool's base up.
- Owners: an instance's `OSAPI_XMEM_ALLOC` block is its slot (00h-7Fh); its
  region `80h|slot`; its claims `0A0h|slot`; a driver's claims `0C0h|row`;
  the cells' kernel-owned blocks FFh; the walk's fixed-area markers F0h-F4h.
- **What moves** (`mx_canmove`): `80h`-`DFh` and `MX_KDRV`. Moving is a copy
  in pieces with interrupts on between them, and every LDT descriptor whose
  base lies in the block is rebased (`mx_cpmove`, `mx_desc`); no relocation
  proc is needed because holders name a block by SELECTOR.
- **What does not move:** `MX_KOWN` (caches, modules, the LDT-block of a lone
  selector), FFh, and `OSAPI_XMEM_ALLOC` blocks, whose token IS the linear
  base the package holds.
- `.norun` in `mx_alloc` packs movable blocks DOWN once (`mx_compactf`) and
  retries; `mx_packupf` packs them UP and is used by `OSAPI_MEM_REGROW`'s last
  try. Both exist and both work in pieces.
- Measured (14.70.3): Bochs at 16MB read **AVAIL 15.26M against MAX RUN
  14.70M**: ~570K of free pool no single claim could have.

### 1.3 Conventional memory on kern_mega

- The heap starts at **1060h** once `.cold`'s rung is returned (`mem_base`,
  read off the machine), and runs to 9FC0h: 573K on a 640K machine.
- Below 1060h: the IVT, the BDA, the kernel's `.text`/`.bss` at KERNEL_SEG
  (60h), LOW_SEG's stacks and `.lowbss` (`mem_tab`, `mx_tab`). Those are the
  segments the kernel names by constant.
- With the pool free, the kernel's own conventional claims on a desktop are
  **one**: `P_RAHB`, the 5K read-ahead landing, which is the bounce every
  reflected disk transfer uses (2, measured).
- The kernel's CACHES go above 1MB as pool blocks under a selector when the
  pool has room (`mem_hitag`'s list: the window save-unders, the menu
  save-under, the icon store, the multi-file list, the clipboard, the FAT
  windows), and to conventional memory when it does not
  (`mem_claim_x`'s kern_mega arm).

### 1.4 Purgeable caches above 1MB

A pool block has no `mem_tab` record and no tag: `mega_hiclaim` takes
`MX_KOWN` and drops BX. So a cache above 1MB is never shed, never counted as
reclaimable, and billed to System by the Task Manager. On kern_big
`mem_shed_one` sheds the cheapest purgeable record strictly below the
claimant's rank (`mem_rank_bh`, §50.6.4) and tells the holder through
`mem_pg_forget`, which knows the FAT window's and the icon store's extra
naming words (`dsk_fatw_demote`, `ico_demote`).

### 1.5 Segments and selectors

- **3.1's identity map:** GDT entry i describes base i x 128, so a
  conventional segment on the 8-paragraph grid IS its own selector. This is
  what let the whole kernel and every package run unchanged in protected
  mode, and it is why the GDT is 64K: it must reach the highest segment
  anything loads (F000 the ROM, the scratch selectors at FFD0h-FFF8h, video,
  and every heap paragraph up to 9FFFh).
- **The LDT's static code aliases:** a 512-aligned image's CS is
  `(S >> 2) | 4`, an LDT selector whose index is S / 32; `mega_cs2ds`
  converts back with `shl ax, 2`. The allocator's pairs (DATA = CODE + 8) are
  the other kind, and `mega_ldt2ds` tells them apart.
- **Measured** (14.70.1): of 8,192 GDT entries **106 were ever loaded**, 78 of
  them the Task Manager's ROM scan; of 2,048 LDT entries, **31**.
- 2.3's survey of `kernel/`: 230 loads of DS/ES/SS from a general register (61
  a constant, 37 zero, 33 a stored variable, 23 a copy, ~21 arithmetic, ~55 a
  parameter), and 44 lines of paragraph arithmetic in `memory.inc` alone.
- `mega_s2segf` converts a selector to a real-mode segment for the
  reflection; `dskw_hiseg` gives the file layer a landing for a buffer above
  1MB; `mega_oddsegf` makes a scratch selector for an off-grid paragraph.
- **The gate:** `tests/unit/t_megahigh.py` (full tier) and
  `tests/megahigh.txt`, whose remaining exemptions are SHEET, REALDMG,
  BROWSER (`high` and `highmem`), XTMP3, PIXEL and LEMMINGS (`highmem`), each
  with its reason in that file.
- **The windowed DOS is refused on kern_mega** (KERN-MEGA-DOS-PLAN 2.1): a DOS
  program runs in real mode, in the trip, where the GDT is never read. So no
  code from outside this repository ever loads a segment in protected mode.

### 1.6 The hibernate on kern_mega

- The write: the conventional picture as one write from linear 0 in 32KB
  chunks (`hbm_xwconv`, chunks from identity segments n x 800h), then an
  extended SECTION: a 512-byte head (`HIBX`, at most `HBX_HMAX` = 62 runs) and
  the runs, run 0 the GDT+LDT+IDT, then every pool block, copied through a
  **32KB conventional bounce** (`hbm_xbounce`, `MEM_K_HIB`, page-safe,
  claimed after the picture).
- The resume reads the **WHOLE FILE into one staging block above 1MB**, placed
  clear of every block the image had and every block the boot holds, and the
  park stub copies runs, then conventional memory, into place.
- **So the hibernate REFUSES when the pool is full** (`hbm_xplan`: *"whether a
  resume could place all of it in one block beside it"*). Measured, 2.
- The image is as big as the memory in use: the pool's blocks are all
  written.

### 1.7 Where kern_mega's code can go (os88megaseg at `8eac6506`)

| where | used | room | binds? |
|---|---|---|---|
| `.mega`, its own segment | 14,698 | ~50K of 64K | no |
| the slot above 1MB to `MEGA_XPOOL` | 58,678 (with `.cold`, scratch) | 51,914 | until MC2 |
| `.cold` under `%ifdef KERN_MEGA` | 42,207 | ~23K of 64K | no |
| the SHARED 64K window, `.text`+`.bss` | 52,188 | 13,348 physically | **the `tests/megaseg.txt` allowance: 3,714 of 4,029 used, 315 left** |

The allowance protects kern_big: every byte kern_mega adds to the shared
window is a byte kern_big can never grow by. So the round's logic goes in
`.mega` (or `.cold` under `%ifdef`), and the shared window gets only HOOKS
(a far call, ~5 bytes). Where hooks exceed 315 bytes, room is made first by
moving the part of `mega.inc`'s 2,456 `.text` bytes that never runs in real
mode into `.mega` (14.45 moved 1,378 that way); a raise is asked of the owner
only if that falls short, with the measured figure.

**Code is usage too.** `.mega` and `.cold` are resident above 1MB from boot,
`.text` in conventional memory. The round's code is a few KB (ESTIMATE)
against ~200K returned.

---

## 2. The measurement behind the reserve

Taken once, because it decides a design (CLAUDE.md's Testing exception),
under Bochs 2.7 at `543827bd`: kern_mega, SOUND.DRV + HDD.DRV, an SB16, booted
off C: with the system files so HIBER.DRV can write there,
`build/megaapps.img` in B:. `tools/megaconvres.py` re-takes it (`MEGS=4` for
the owner's 4MB example; `--nofill` leaves the pool free). It is not a suite
row; MC5's row keeps the reserve honest.

**Method.** After the desktop came up every free KB of the pool was covered by
pinned `mx_tab` records written through the debugger: a program holding all
of extended memory. Then ordinary actions, sampling `mem_tab` for every claim
not owned by an instance. 16MB (pool 15,104K) and 4MB (2,816K) read the same.

| action, pool full | kernel claims in conventional memory | total |
|---|---|---|
| idle desktop | `P_RAHB` 5K | 5K |
| open B:, then a folder | + `P_FATW` 5K, `P_ICO` 5K | 15K |
| open the Control Panel | + `K_MOD` 15K (CTRL.DRV), `P_WSAVE` 30K | 60K |
| System > Hibernate (dialog) | + `K_MOD` 11K (HIBER.DRV), a second `P_WSAVE` 22K | 93K |
| Hibernate | **REFUSED** (pool full); ~20 s unfilled | - |
| a file copy (`fcp_claim`, by reading) | `K_COPY`: free up to 64K, at least 3K or a cluster | 3K+ |
| the hibernate's write (`hbm_xbounce`, by reading) | `K_HIB` 32K, page-safe | 32K |

**Reading it.** The raise caches and the icon store are TRIV and are shed by
any program claim; they are not reserved. What must keep working with
everything held is the disk (landing + FAT window, 10K), the Control Panel
(CTRL.DRV 15K) and the hibernate (HIBER.DRV 11K + the 32K bounce). The worst
concurrent case is the hibernate: **5 + 5 + 11 + 32 = 53K**.

**The reserve is 64K, one run** (owner: accepted). Every conventional claim is
page-safe, so the 32K bounce must sit inside one 64KB DMA page. A 64K run
straddles at most one page boundary, so one side of it is at least 32K, and
the other 32K holds the 21K; a 53K run with the boundary near its middle
cannot hold the bounce at all. Not covered, on purpose: launching another
program (it has no pool to run in), mounting a driver mid-session (it refuses
with its reason), the holding program's own DMA ring (it claims that first).
32K was the alternative (Control Panel only); taking the hibernate under 32K
means a smaller `HBX_CHUNK`, which is the image's file chunk too.

---

## 3. Decisions, and the assumptions under them

| # | decision | by | rests on |
|---|---|---|---|
| D1 | The fixed area goes to the TOP of RAM and every claim is taken top-down, so free memory is one run from 1MB up and the HMA is reached last, just before conventional memory | owner (2026-10-25) | MC3's no-pinning pass, without which a late pinned block walls the run |
| D2 | The pool gets kern_big's no-pinning treatment: everything moves but a module in use | owner | `XMEM_ALLOC` tokens are never read in place under protected mode (A3) |
| D3 | Caches above 1MB are purgeable exactly as on kern_big | 14.70.1 | |
| D4 | The HMA is pool; a DOS trip parks what stands there | owner (14.70.1) | |
| D5 | A DOS trip with nowhere to park offers a HIBERNATE instead | owner | the streaming resume (MC4) |
| D6 | One claim can take all free memory; a program can ask the exact figure first | owner | REGION-SELF-COMPACT-PLAN 5.1.1: a refused claim is destructive |
| D7 | Huge claims BRIDGE conventional and extended memory BY DEFAULT | owner | a huge claim is a run of 64KB windows, walked by CX (A4) |
| D8 | The conventional reserve is 64K, one run | owner, on 2's measurement | |
| D9 | Every program, driver and kernel path is converted so that above the heap floor nothing needs a segment to be its own selector; the GDT is a fixed ~4K, the LDT all allocator | owner | A1, A2 |
| D10 | Old hibernate images are refused | owner | |
| D11 | The order is MC1, MC8, MC2, MC3, MC7, MC4, MC5; MC9 is a later round | this plan, owner's delegation | 4 |
| D12 | The round's logic lives in `.mega`; the shared window takes hooks only | 1.7 | |

**Assumptions** (each is checked by the wave that relies on it, and a failed
one is a stop-and-ask):

- **A1** No code outside this repository loads a segment in protected mode:
  the windowed DOS is refused on kern_mega, DOS programs run in the trip in
  real mode. Checked by MC7's census.
- **A2** Real-mode code never reads the GDT or LDT, so the reflection, the
  trip, the 286 reset landing and a ROM calling USBMOUSE.DRV's hook are
  unaffected by what the tables hold, as long as the segments handed to them
  are REAL segments (`mega_s2segf`).
- **A3** On kern_mega no package reads an `OSAPI_XMEM_ALLOC` token in place:
  `os88la.inc` (LOADALL) and `os88ub.inc` (a moment of protected mode) are
  real-mode techniques, and the Video Player takes `OSAPI_XMEM_RUN`'s
  selectors under `[vp_pm]`. Every use of a token goes through a kernel cell.
  MC3 censuses token ARITHMETIC (a token plus an offset passed back to a cell
  is fine inside the block's own range).
- **A4** A package walks a huge claim only by the CX step `OSAPI_MEM_HUGE`
  answers (the SDK says so), never by assuming windows are physically
  adjacent. MC5 censuses the callers: `apps/video/video.asm` (32KB-step, never
  bridged) and the C SDK's `os88_mem_huge`.
- **A5** The resuming boot on the same machine computes the same top-of-RAM
  layout as the hibernating one (same `int 15h AH=88h` answer). MC4 checks
  the image's recorded layout and refuses on a mismatch.
- **A6** A raw DOS allocator during a trip is caught by the sum whichever end
  it takes memory from (KERN-MEGA-DOS-PLAN 5.2's placement paragraph turns
  over with D1; updated in MC2).

---

## 4. The order (D11), and why

1. **MC1 purgeable** first: small, independent, and every later figure counts
   on caches being sheddable.
2. **MC8 14.69's three** next: small, and two of them (RAMDISK.DRV's and
   NET.DRV's paragraph folds) are MC7's first census items anyway.
3. **MC2 the fixed area to the top**, before anything shrinks it: while the
   fixed area sits below the pool, a table that shrinks leaves a hole nothing
   can claim.
4. **MC3 the no-pinning pass and every claim top-down**: free memory becomes
   one run from 1MB up.
5. **MC7 selectors everywhere**, before the hibernate and the whole-memory
   claim: it changes what a claim IS (a selector, movable by rebase), and the
   tables the hibernate saves, so the hibernate's format is reworked once, in
   MC4, on the final layout.
6. **MC4 the HMA and the streaming resume**, on the final layout.
7. **MC5 one claim for all of it**, last: it needs every wave before it.
8. **MC9 what still goes low** is a later round unless the owner says
   otherwise.

---

## 5. The waves

Each wave verifies on the host (`make`, `make mega`, `make KERN_SMALL=1`,
`tools/kernsize.py`, `tools/os88megaseg.py`) and by LOOKING under Bochs, and
NAMES its rows; the deduplicated union of the named rows runs ONCE after the
last wave, with `test-full` (CLAUDE.md, *Testing*). kern_big and kern_small
must stay byte-identical except where a wave says why not.

### MC1 - purgeable pool blocks (D3)

- `mega_hiclaim` keeps the cache's TAG. An `mx_tab` record is 8 bytes and
  full; `MX_SEL` is `OSAPI_XMEM_SEL`'s window and never used by a cache, so
  the tag rides there behind a `MX_FL` bit, `MX_FPURGE`. (MC3 widens the
  record anyway; if the tag moves then, so be it.)
- `mx_alloc`'s refusal path sheds before it gives up: the cheapest purgeable
  block strictly below the claimant's rank (`mem_rank_bh`), the holder told
  first through `mem_pg_forget`, then the block and its selector freed. A
  cache never sheds a more valuable cache, never the FAT window being written.
- `mem_claim_x`'s conventional refusal also sheds pool caches when the pool
  path is what it would retry into (to decide while building).
- `OSAPI_XMEM_WALK` reports the bit; the Task Manager files those blocks
  under `Purgeable` (14.70.3's last box).
- Rows: `megaown`, `tmowner`, `megahigh`, and a new row: fill the pool with
  raise caches, ask for a claim that fits only with them gone, assert it
  succeeds and that they were shed; red without the shed.

### MC8 - 14.69's three

- RAMDISK.DRV's `rd_fold` and NET.DRV's `net_norm` stop folding paragraphs
  into a kern_mega selector; `t_megagrid` takes `drivers/` too.
- `CDROM.DRV` declares `OS88_DRV_HIGHOK`; `megacdrom` asserts its base above
  1MB.
- `\AUTOSTRT` is walked after `mega_enter` on kern_mega, so an `OS88_HIGH`
  package it opens is placed high.
- Rows: `megagrid`, `megacdrom`, `autostart` under `make mega`.

### MC2 - the fixed area at the top of RAM; the pool from 1MB (D1)

- The top is 1MB + `[mega_extkb]`, capped at 16MB. `mega_enter` lays the
  fixed area out DOWNWARD from it, KB-granular: IDT, GDT, LDT, `.cold`,
  `.mega`, the park's scratch, with what MC7 shrinks (LDT, GDT) at the zone's
  BOTTOM edge, next to the pool.
- The `MEGA_*_LIN` constants become variables; most readers already read one
  (`mega_gdtr`, `mega_idtr`, `mega_ldtlin`, the descriptors written at run
  time). The rest is a census: `kernel.asm`'s fit checks, `mega_xmfix`, the
  park's addresses (`megados.inc`, `MEGA_SEL_PSCR`), the hibernate.
- `MEGA_XPOOL` becomes 100000h (64KB-aligned, so `add dx, MEGA_XPOOL >> 16`
  stands). `mega_xminit` records the fixed zone and the HMA (until MC4) as
  pinned marker records; `XMW_FIXED` reads them, and `Padding` disappears.
- The hibernate's section names the pool base and the tables' places: an old
  image is refused (D10).
- KERN-MEGA-DOS-PLAN 5.2's placement paragraph is updated (A6).
- `mega_tlowf`'s low-table path stays for machines with too little extended
  memory; MC7 is what shrinks it.
- Buys ~50K.
- Rows: `megahigh`, `megahiber`, `megap2hiber`, `megadosp`, `megakbtrip`,
  `megarehome`, `megapiclose`, `tmowner`.

### MC3 - the no-pinning pass, and every claim top-down (D1, D2)

- `OSAPI_XMEM_ALLOC` blocks: the token becomes a range in a TOKEN SPACE, not
  the physical base; the block's physical base moves under it and every cell
  (COPY, SEL, RUN, FREE, the walk) translates. `mx_tab` gains the token base:
  8 -> 10 bytes, +192 bytes of LOW_SEG. Census: no package does arithmetic on
  a token beyond its own block (A3).
- The kernel's cache blocks move by copy and rebase (13.1), or are shed if
  that is cheaper (MC1).
- Modules move when no frame is inside them; pinned only while their action
  runs (kern_big's rule).
- `mx_alloc` places every owner top-down; compaction packs UP against the
  fixed zone (`mx_packupf` becomes `.norun`'s pass; `mx_compactf` goes).
- Rows: `megaown`, `megavidbig`, `megavidv2`, `megaovl`, `megarehome`,
  `megahigh`, `megahiber`, `tmowner` (MAX RUN = AVAIL after a pack), and a new
  row: an `XMEM_ALLOC` block moved by a pack and read back through the same
  token.

### MC7 - selectors everywhere above the floor; a ~4K GDT, an LDT that grows (D9)

- **The end state.** Identity selectors survive only from segment 0 to the
  heap floor (1060h): the IVT window, the BDA, the kernel's image and
  LOW_SEG. The GDT is that, ~525 entries, **~4.2K, fixed**. Every claim,
  region, carve, overlay, module and driver image above the floor gets LDT
  selectors allocated with it and freed with it, in conventional or extended
  memory alike. The LDT is all allocator, starts at 2K and grows (a bigger
  pinned block, a copy, GDT entry 18h rewritten, `lldt`). The 1MB machine's
  82KB low tables (1.1) become ~8K.
- **Side effect worth having:** a conventional claim named by a selector
  moves by copy and rebase with no relocation proc - MC3's pass, extended to
  conventional memory.
- **Step 1, the census:** every site that loads a paragraph ABOVE the floor
  into a segment register in protected mode, or hands one to something that
  will:
  - **Packages** - the six `tests/megahigh.txt` exempts (1.5), converted as
    14.40-14.52 converted the rest (offsets inside 64KB selectors,
    `OSAPI_MEM_SUBSEG`, `OSAPI_MEM_HUGE`'s step, `OSAPI_MEM_CODESEL`). After
    it the file is EMPTY and `t_megahigh` refuses any line.
  - **Claims through other doors** - the DMA rings, the C64/Apple II ROM
    carve, the CWORD/RunCPM overlay carve, `os88type.inc`'s face cache, the
    re-homers' parts carves. Each keeps living where it must but is named by
    an LDT selector; a holder that programs the 8237 gets the LINEAR base
    from the DMA door beside the selector (an ABI addition, §20.2.0.1).
  - **Drivers** - the seven without `OS88_DRV_HIGHOK` (CDROM, HDDTOOL, HTTPFS,
    HTTPPAGE, RAMPAGE, USBMOUSE, VESA; VMMOUSE is kern_emu's, XMEM.DRV's cells
    are the kernel's own on kern_mega, OS88NET is a DOS program) and every
    driver's own claims.
  - **The kernel** - the loads of HEAP paragraphs: the compactor
    (`memory.inc`), `dskw_norm`'s kern_mega arm (128-byte granules ARE the
    identity map; a selector takes `dskw_hiseg`'s path), the loader's region
    and carve, `mod_check`'s `(S >> 2) | 4`, `hbm_xwconv`'s identity chunks,
    `mem_claim`'s own answer (a selector for every claimant on kern_mega).
  - **A000h and up** - video behind `[vid_*]`, the ROM font, the Task
    Manager's ROM scan, EMS page frames, any package writing A000h/B800h
    itself in an fsx bracket: allocated selectors; a hot path converted, not
    fixed up.
  - **The scratch and code selectors at FFD0h-FFF8h** - into the LDT.
  - **Claims made in real mode before the switch** (MC8's finding 3): every
    boot-time claim holds a real segment in a kernel word, and is given its
    selector AT the switch, holder by holder (`mem_hicaches_f`,
    `drv_hiboot_f` are the pattern).
  - **File drivers get the selector itself** (MC8's finding 1):
    `drv_fs_hi`'s 512-byte bounce is retired and the kernel splits a
    transfer at the selector's 64KB limit. RAMDISK.DRV, NET.DRV and
    CDROM.DRV already walk an LDT selector's offset (MC8); HTTPFS is
    checked in the census.
- **Step 2** packages and drivers, **step 3** the kernel, **step 4** cut the
  GDT's limit to the floor and drop the static aliases; a missed site then
  shows as a `#GP` past the limit, reported at the instruction (14.42).
- **Buys** ~60K of GDT and ~14K of LDT on every machine; on a 1MB machine with
  no extended memory, ~74K of its conventional memory.
- **Repercussions** (owner: accepted): a wild segment load faults instead of
  reading whatever is there; old hibernate images refused; the census is the
  cost.
- Rows: `megagrid`, `megapkg`, `megahigh` (empty list), `megaflt`, `megaovl`,
  `megarehome`, `megavidbig`, `megavidv2`, `megadosp`, `megahiber`,
  `megap2hiber`, `megatrap0`, `tmowner`, the converted packages' own rows
  under `make mega`, the adapters' boots; a new row that opens programs until
  the LDT grows and asserts the GDT's limit is the floor's.

#### MC7.1 The census (2026-10-25)

Five read-only passes over the tree at `331b47f7` (after MC3): the kernel in
three slices, the packages with the C SDK, and the drivers. Each site was
classed OPAQUE (only held and loaded: works once the value is a selector),
ARITH (a segment made by arithmetic, compared by order, or turned into a
linear address), REAL (handed to real-mode code or to hardware), CONST (an
immediate segment at or above the floor) or IDENTITY (a segment used as a
key). The findings that decide the design:

- **The kernel's claim choke point is one routine.** `mem_claim_1`'s publish
  (memory.inc) is where every conventional claim - about 45 kernel call
  sites and every package and driver claim through `mmf_osapi_mem_claim*` -
  gets its value. A selector allocated there, with the record keeping its
  physical paragraph (MC_SEG/MC_PARA bookkeeping, ~95 lines, stays
  physical), reaches every claimant at once. Four lookup helpers
  (`mem_find_own`, `mem_owner_of_x`, `mem_is_region`, `mem_in_xfer`) carry
  most of the identity compares.
- **The TI bit is used as "above 1MB" at about twenty sites** (memory.inc
  ×7, loader ×3, mod ×2, driver ×3, disk ×3, lz ×2, plus `dsk_runcap`).
  Once every claim is an LDT selector they all misroute silently. One
  predicate - "is this a pool block?", by base or by owner - replaces them.
- **The code aliases already have a pair arm everywhere.** `MEGA_CSELTOP`,
  `mega_frame_cs`, `mem_reloc_call`, `mega_cs2ds`/`dsimg`/`csdata` and
  `mega_codesel` all handle a code/data pair (code = data - 8). Once every
  CS-able claim is a pair, the `(S>>2)|4` arms are dead code. The 232
  module `CSDO`/`PUSH_CSDATA` sites need nothing.
- **The compactor's copy engine** (`mem_bcopy`) loads arbitrary paragraphs;
  it becomes a linear copy plus a descriptor rebase (MC3's pool rule), and
  the relocation protocol's kernel half (`mem_rr_tab`, the IVT rows, the
  worker restart) becomes a no-op for selector holders.
- **Video is one table.** `vid_tab`'s segment column feeds `vid_seg`,
  `vid_rseg`, `vid_tseg` and the two `vid_ctx` records; twelve planar hot
  paths load `VGA_SEG` as an immediate (`mov es, [vid_seg]` is a byte
  shorter); `fsx_mtab` hands nine framebuffer segments to packages, and no
  package does arithmetic on FSI_SEG (pages are reached by offset). The ROM
  font is one word, `font_seg`, with four origins decided in real mode.
- **The file layer**: `dsk_runcap` is the one DMA-page authority and must
  work from a LINEAR base; `dskw_hiseg`'s low arm (a real segment loaded in
  protected mode) retires, and the high arm needs a 64KB-limit split it
  does not have today; `drv_fs_hi`'s 512-byte bounce retires once file
  drivers take the selector (NET, RAMDISK, CDROM are ready; HTTPFS's
  `hf_bnorm` is not). The DISKOPS cloner and compressor and the LZ decoder
  step segments through claims over 64KB.
- **Values captured in real mode and used after the switch**: the live FAT
  window, `sc_seg`, `ico_seg` (over 63KB), `font_seg`, `vid_*`, `vid_ctx`,
  `bnd_seg`, driver rows and their IVT halves, module tables, a boot
  RAMDISK's claims, `em_frame`. `drv_hiboot_f`/`mem_hicaches_f` are the
  pattern.
- **Drivers** (one image ships to every kernel, so a kern_mega test costs
  every disk): SOUND programs the 8237 from `seg*16` (its own ring and a
  package's external ring), HDD caps a BIOS transfer by `seg*16`, RAMDISK's
  conventional arena is over 64KB, HTTPFS folds unconditionally, EMS walks
  C000h-F000h and hands out its frame, USBMOUSE must write a REAL segment
  into IVT 33h. About 150-200 bytes, plus three kernel doors: the linear
  base of a selector (`seg*16` elsewhere), a selector for a physical
  paragraph (the paragraph elsewhere), and selector-to-real-segment.
- **Packages: about 270 sites in about 30 packages and 4 shared layers.**
  - The six registry exempts (Sheet ~10, RealDMG ~25 plus two whole
    classes, Browser ~14, XT-MP3 7, PiXEL ~30, Lemmings 16).
  - Packages that DECLARE both bits but keep claims over 64KB conventional
    "by contract" and walk them in 128-byte granules, in HOT paths: Paint's
    canvas, Frotz's story, Tracker's and ModPlug's modules, MIDIRack's
    banks, the Video Player (all 31 of its claims through the DMA door on
    purpose).
  - The parts library (`op_seg`, `op_read`, `op_unpack`, `op_fetch`, the
    REHOME macro) - 18 users - and the C SDK's `cc_ovbind`, both segment
    arithmetic on a carve that may pass 64KB.
  - ROM biases (Apple II, C64: a segment BELOW the ROM part, hot), static
    `OS88_CODESEL` inside relocation procs that may not call the kernel,
    framebuffer immediates (Video, Excitebike, Gorillas), ROM/EBDA scans
    (Task Manager, Redline), `os88type`'s 512-byte alignment assert.
  - Five packages hand an external DMA ring to SOUND.DRV as a segment.
  - Lemmings cannot be run here (its data is fetched, not committed).

#### MC7.2 The decision this needs (asked of the owner, 2026-10-25)

The package half is the bulk, and most of it is ONE pattern: segment
arithmetic in 128-byte granules INSIDE one claim, in hot paths shared by
every kernel. Two ways to meet D9:

- **(A) Convert each site** to OSAPI_MEM_HUGE windows, offsets or SUBSEG
  calls. Zero run-time table cost. Thousands of lines across ~30 packages,
  each a change on the 8088 too unless it is a `PKG_MEGA` arm (two code
  paths to keep), and hot loops (Paint, Frotz, the mixers) change shape on
  the machine the project is measured on.
- **(B) A GRANULAR claim**: the kernel maps a claim with one LDT entry per
  128 bytes, consecutive, so `selector + 8k` names granule k exactly as
  `segment + 8k` does today - inside that claim and nowhere else. Every
  granule-arithmetic site works unchanged on kern_mega and no package byte
  changes on any other kernel. It costs 8 bytes of LDT per 128 bytes of
  such a claim (6.25%) while the claim is held: Paint's 150KB VGA canvas
  ~9.6KB, a 508KB Frotz story ~32KB, nothing at all on a desktop that holds
  no big claim. The GDT is still ~4K and the LDT still starts at 2K.

What (B) cannot express is converted either way: the ROM biases (a biased
SUBSEG), CS writes (a writable alias), framebuffer immediates, DMA rings
(the linear-base door), ROM scans, CODESEL inside relocation procs (the
pair rule), the parts library's off-grid slack, and the exempts' remaining
sites.

**Recommendation: (B) for in-claim granule arithmetic, (A) for the rest.**
Work common to both proceeds while the owner decides: the growable LDT,
the scratch selectors into the LDT, the doors, the video/font/ROM selectors
at the switch, the kernel's own conversion, and the drivers.

**The owner's answer (2026-10-25): (A).** (B) nets a saving everywhere -
nothing on a desktop holding no big claim, ~64K with Paint's 150KB canvas,
~42K with a 508KB story - but it gives memory back exactly when a big
document is open, and the goal is to shrink usage. (A) costs work, not RAM.
**How (A) is taken:** every site is converted. Where a conversion reshapes
a hot 8088 path, it is measured (MartyPC, guest cycles): no slower and it
is one shared path; slower and it is a `PKG_MEGA` arm built onto kern_mega's
own disks (SPEC.md 20.18), the shipped build keeping its loop.

#### MC7.3 The order of work

Packages and drivers convert BEFORE the kernel stops handing out identity
segments, so each conversion is checked on today's kernel and every kernel
keeps working at each step:

1. **The doors**, on every kernel (new cells at the table's end, no
   `PKG_FMT` bump): the LINEAR base of a segment or selector (`seg*16` on a
   real-mode kernel); a selector over a PHYSICAL paragraph range (the
   paragraph itself on a real-mode kernel); a selector's REAL segment; and
   `OSAPI_MEM_SUBSEG` answering for a CLAIM and for a conventional region,
   a BIASED base allowed (the ROM banks). Each with its real-mode answer, so
   a converted package needs no `CPU_F_PM` test for it.
2. **The shared layers**: the parts library, the REHOME macro, `crt0`'s
   overlay binder, `os88type`, `os88xgap`, `os88con`.
3. **The drivers** (SOUND, HDD, RAMDISK, HTTPFS, EMS, USBMOUSE; the three
   overlays' far pointers).
4. **The packages**: the six exempts, the big-claim arms (Paint, Frotz,
   Tracker, ModPlug, MIDIRack, the Video Player), the ROM biases, the
   framebuffer immediates, the scans. `tests/megahigh.txt` empties.
5. **The kernel flips**: every claim a selector from `mem_claim_1`, pairs
   for everything CS-able, the TI predicate, the compactor's linear copy and
   rebase, the file layer's linear DMA authority and 64KB split, the
   DISKOPS cloner and compressor, the LZ decoder, the video/font/ROM
   selectors and the boot captures at the switch.
6. **The tables**: the scratch selectors into reserved LDT entries, the
   static aliases gone, the LDT all allocator from 2K and growing, the GDT
   cut at `.cold`'s selector. A missed site is a `#GP` past the limit,
   reported at its instruction (KERN-MEGA-PLAN 14.42).

#### MC7.4 Step 5's design: the kernel stops handing out identity segments

**Taken before the packages** (a change of 7.3's order, for a reason): a
package converted against today's kernel is only checked against the
identity map, which hides exactly the mistakes a conversion can make. With
the kernel flipped first, every converted package is booted against the end
state as it lands. Packages not yet converted break on the branch meanwhile;
nothing ships between waves (0, rule 1).

- **A pair for every conventional claim.** `mem_claim_1`'s publish asks
  `.mega` for a code/data pair over the new block (16 bytes of LDT); the
  DATA selector is the claim's value, the CODE half is data - 8 for EVERY
  claim, so `OSAPI_MEM_CODESEL` and every relocation proc that converts
  without calling the kernel (`cc_ovbind`) can rely on the rule. The
  selector lives in a PARALLEL table, `mem_sel[MEM_MAX]` in `.lowbss`,
  indexed like `mem_tab`: `MC_SIZE` is in the claim snapshot's ABI and does
  not change. `MC_SEG`/`MC_PARA` stay physical; the allocator's bookkeeping
  (~95 lines) does not change.
- **Moves are rebases.** In protected mode the compactor copies a claim
  linearly (`mega_lincopy`, 32KB pieces, interrupts on between) and rebases
  every LDT descriptor based in the old block (the pool's `mx_desc` rule) -
  the pair, and any `SEG_SUB` selector inside. No relocation proc is called
  and none is needed: every holder holds a selector. So EVERY claim may move
  but a DMA claim with a head (a card may be reading it), one in an `int
  13h` transfer (`mem_in_xfer`), and one whose holder is mid-copy under
  `[sch_lock]`.
- **The switch translates.** At `mega_enter`, every live record gets its
  pair, and then the relocation protocol already in the tree runs ONCE per
  record with BX = its physical segment and DX = its new selector:
  `mem_rr_tab`'s rows (window records, instance pointers, driver rows, the
  disk layer's words, menu bars, ...) and every kernel holder's proc
  (`dsk_rah_reloc`, `ico_reloc`, `sc_reloc`, `asc_reloc`, `fm_reloc`, ...)
  rewrite their words exactly as they do for a move. What that protocol
  does not cover is listed by the census (`font_seg`, `bnd_seg`, the video
  words) and translated beside it. The IVT rows stay REAL: they are what a
  real-mode BIOS and the DOS trip read.
- **Lookups by value** (`mem_find_own`, `mem_owner_of_x`, `mem_is_region`,
  `mem_in_xfer`, `mem_fatw_dirty`) compare `mem_sel` in protected mode.
- **The TI tests** (about twenty) become an explicit question - "is this a
  pool block's?" by its descriptor's base - at each site.
- **Images**: a package region, a driver image and a module are pairs from
  the claim itself, so `MEGA_CSELTOP`'s pair arm, `mega_frame_cs`,
  `mem_reloc_call`'s alias and `mega_codesel` already do the right thing,
  and every `(S >> 2) | 4` arm is dead (step 6 deletes them). Moving one
  high (`ld_hi`, `drv_hi`, `mod_hi`) copies from a selector.
- **Sub-steps, each booting to a desktop**: (5.1) the pairs made, recorded,
  freed and rebased, while callers still receive the physical segment;
  (5.2) callers receive the selector, the lookups and TI tests converted,
  the switch's translation; (5.3) the images; (5.4) video, font and ROM;
  (5.5) the file layer's linear DMA authority, 64KB split and file drivers
  handed selectors; (5.6) DISKOPS's cloner and compressor, the LZ decoder,
  `cpc_fdtest`; (5.7) `OSAPI_MEM_HUGE`'s conventional arm as a selector run,
  with a 16KB step beside 32 and 64.

### MC4 - the HMA is RAM; the hibernate is the way out (D4, D5)

- The HMA's record is unpinned; after MC3 it is the bottom 64K of the free run
  and fills nearly last.
- A DOS trip saves the blocks in [1MB, 1MB+64K) with the park and restores
  them at the same linear addresses.
- **When the park has no room**, the trip offers a hibernate. That needs a
  **streaming resume**: the extended runs read straight to their final linear
  addresses a chunk at a time through the 32K bounce, conventional memory last
  through a stub in the text framebuffer and an extent list (§87.5's shape).
  The resuming boot takes nothing from the pool before the resume; its fixed
  zone lands where the image's did (A5).
- Costs said out loud: the image is the size of the memory in use (~3.9MB on
  the 4MB example; the volume's room is checked, and a short volume refuses
  with that reason), and the write and the resume move it all.
- Rows: `megadosp`, `megakbtrip`, `megahiber`, `megap2hiber`, `megatrap0`;
  new: a block in the HMA across a DOS trip, compared after; a DOS trip with
  the pool held full, which offers the hibernate, takes it and resumes.

### MC5 - one claim for all of it (D6, D7, D8)

- **The exact answer:** pool free + purgeable below the caller's rank (one run
  after MC3's pack) + conventional free less the 64K reserve, less the seam's
  waste. A new answer of `OSAPI_MEM_HUGE` (AX = 0 asks) or a cell of its own,
  per §20.2.0.1.
- **The bridge, by default:** when the pool alone is short, a plain huge claim
  is a pool piece and a conventional piece under one run of selectors. The
  FIRST piece is cut to whole 64KB windows (the kernel puts first the piece
  with the smaller remainder; waste under 64K). Each piece is one record. The
  32KB-step form (`MX_FH32`) overlaps its windows and is never bridged.
- **The reserve:** 64K of conventional memory left free, one run.
- Rows: a new one on a 4MB machine (Bochs, and `vm/286-mega`): ask, claim the
  answer, a pattern through every window including the seam, then with the
  claim held open the Control Panel and hibernate; free, ask again, equal to
  the Task Manager's free figure. Plus `megavidbig`, `megavidv2`.

### MC9 - what still goes low (14.53, 14.60) - a later round

- First, 14.60's lead: an AT's 8237 page register may make an 8-bit DMA ring
  above 1MB legal on every kern_mega machine. If so, the rings, `SOUND.DRV`'s
  pool and the 32KB bounce all move.
- BIGSP in place stays with the Video Player round; `mx_tab` stays low by the
  owner's deferral (14.51).

---

## 6. The whole round, estimated

About **200K** of the fixed area's 256K comes back to programs (50 padding +
64 HMA + ~60 GDT + ~14 LDT), the caches standing come back when needed, and
every free byte but the 64K reserve can be had by one claim. On the 1MB
machine with no extended memory reported, the tables' 82K of conventional
memory becomes ~8K.

---

## 7. As built

Each wave records here what it came to: the bytes (`.mega`, `.cold`, `.text`,
the megaseg overhead), what it measured and on what, what it found, and its
rows. Nothing is recorded as built that was not.

### MC1 as built (2026-10-25) - DONE

- **The record grew a word, shared with MC3.** `MX_BLKSZ` 8 -> 10, the new
  `MX_AUX` (offset 8) holding a cache's tag; MC3's token will use the same
  word for an `OSAPI_XMEM_ALLOC` block, the two never applying to one block.
  `MX_FPURGE` (4) is the `MX_FL` bit. `.lowbss` +192 bytes for 96 records.
- **`mega_hiclaim` takes the tag in BX** and gets the block's selector
  through `mega_xmsel`, so it lives in `MX_SEL` and `mx_free` frees both. A
  purgeable tag marks the entry; any other is pinned. Callers: `mem_claim_x`'s
  kern_mega arm (BX was already the tag), `mem_hicaches_f` (`MEM_P_ICO`) and
  `dsk_rah_wanthi`, which passed the read-ahead's WIDTH in BX and now passes
  `MEM_P_DIRW` - so the 32K store at the pool's top is now a HIGH cache, as
  its conventional twin always was. `mega_hiclaim2` (module pairs) passes
  BH = 0, the top rank.
- **The shed** is `mx_shedf` in `memory.inc` (`.cold`, `%ifdef KERN_MEGA`),
  beside `mem_shed_one`, using `mem_rank_bh` and `mem_pg_forget` unchanged.
  `mx_alloc` calls it (through `mx_shed`, which sets the rank: BH for
  `MX_KOWN`, the top for everyone else) at `.norun` after the compaction it
  already tried, and at `.full`, and on success runs the whole walk again
  with the compaction re-armed.
- **The walk** writes the level at `XMW_CLS` for such a block (owner FEh) -
  additive, `abi.lock.json` refreshed with no bump. The Task Manager files it
  under `Purgeable` as TYPE `Cache` with that TIER (+36 bytes of image).
  Seen under Bochs: `Purgeable 77K` = the conventional read-ahead landing
  (5K, HIGH), the read-ahead store (32K, HIGH), B:'s FAT window (5K, MED),
  the icon store (5K, TRIV) and the About box's raise cache (30K, TRIV); the
  `Kernel` group, which used to hold the 32K, is gone from the list.
- **Bytes:** kern_mega `.mega` 14,698 -> 14,837 (+139), `.cold` 42,207 ->
  42,332 (+125), `.text`/`.bss` +0 (megaseg overhead 3,714, unchanged);
  kern_big and kern_small byte-identical at one commit.
- **Row: `megashed`** (soak, Bochs, 14 s): caches standing, every free KB
  covered, the Control Panel opened; CTRL.DRV must go above 1MB, shedding
  the icon store and the raise cache (both TRIV) and leaving the FAT window
  and the read-ahead store. Green; and red with `call mx_shed` taken out
  (CTRL.DRV stays low, nothing shed) - verified.
- SPEC.md 50.6.8 is the contract; 28.4.11's cell table names the byte.

### MC8 as built (2026-10-25) - DONE

- **The folds, in the units a segment's value allows.** RAMDISK.DRV's
  `rd_fold`, NET.DRV's `net_norm` and CDROM.DRV's `cd_bnorm` now share one
  rule:
  - real mode folds paragraphs, exactly as before;
  - under `CPU_F_PM` an IDENTITY (GDT) selector folds whole 128-byte
    granules, the kernel's own `dskw_norm` rule;
  - an LDT selector does not fold at all - its offset walks.

  The LDT arm is not reachable today, because the kernel bounces any selector
  buffer through `drv_fs_hi` 512 bytes a call. It is in place for MC7, which
  hands drivers selectors directly. NET.DRV banks `OSAPI_CPU_INFO` at attach
  (`net_cpuf`), as RAMDISK.DRV already did, and so does CDROM.DRV
  (`cd_cpuf`).
- **CDROM.DRV says `OS88_DRV_HIGHOK`** (no arithmetic on its own CS or DS, PIO
  only). Seen under Bochs on `make megacdtest`'s disk: `kern_mega: above 1MB:
  CD-ROM`.
- **`t_megagrid` scans every driver**, not only the packages that declare
  `OS88_HIGH`. It flagged two A20 probes, both real-mode-only, registered with
  their reasons. NET.DRV's `CPU_F_PM` test is registered in
  `tests/megapkg.txt` (a correctness test every build needs, ~25 bytes).
- **AUTOSTART is walked after `mega_enter`.**
  - The walk is ONE macro body (`AS_WALK`, `kernel/desksc.inc`) assembled as
    `as_boot` in the blob on every other kernel and as `as_bootc` in `.cold`
    on kern_mega. `kmain` calls the latter last, after the drivers and caches
    go up.
  - The kern_mega arm holds no data and no CS idiom (`.cold`'s rules 1 and
    2): the folder's name and the skip toast are immediate stores, and the
    find's answer is a 24-byte STACK frame popped before anything opens.
  - Seen under Bochs: the autostarted CDRack's segment is `284Ch`, a pool
    selector, where it was `9640h` in conventional memory.
  - A finding on the way: `mega_tasks_ok` REFUSED protected mode for the
    whole session when an autostarted package had a worker running. A walk
    after the switch cannot cause that.
- **Bytes:**
  - kern_mega `.cold` +221 (the walk; `.mega` unchanged), shared window +4
    (the call; megaseg overhead 3,718 of 4,029);
  - kern_big and kern_small byte-identical with a clean build of the same
    commit;
  - RAMDISK.DRV, NET.DRV and CDROM.DRV each a few bytes larger.
- **A method note.** A stash-and-rebuild comparison was WRONG here: make
  keeps generated files (the packed kernel's defines) from the dirtier
  build, so the stashed "baseline" mixed two trees and showed a 1-byte
  difference in stage 2 that a clean build does not have. Byte-identity is
  checked against a clean worktree of the same commit from now on.
- **For MC7, found here:**
  1. Once every buffer is an LDT selector, keeping `drv_fs_hi`'s 512-byte
     bounce would make every file-driver transfer 512 bytes a call - over the
     LapLink cable a large slowdown. MC7 hands file drivers the selector
     directly and SPLITS a transfer at the selector's 64KB limit. The drivers
     are ready for that now.
  2. `mega_tasks_ok`'s premise (real-mode frames from before the switch)
     remains for anything else that runs before `mega_enter`.
  3. **Every claim made in real mode before the switch** (the FAT windows,
     the read-ahead landing, the icon store, the shortcuts table, the
     ASSOC.DAT cache, drivers' claims, the settings buffer) holds a real
     SEGMENT in a kernel word. Once the GDT stops covering the heap they
     must be given selectors AT the switch, holder by holder:
     `mem_hicaches_f` and `drv_hiboot_f` are the pattern, and MC7's census
     has to list every one.
- Rows named: `megagrid`, `megapkg`, `cswrite` (fast); `megacdrom` (86Box,
  now asserting both the driver and the autostarted CDRack above 1MB);
  `rdmove`, `rdup`, `rdpreserve`, `rdxms`, `rdcz`, `rdicon`, `rdmount`,
  `netcoexist`, `netpromise`, `netinst`, `cdrom`, `cdromsim`, `cdromempty`,
  `autostart` (the drivers' and the walk's real-mode paths).

### MC2 as built (2026-10-25) - DONE

- **The layout is a pure function of `mega_extkb`.** `mega_layoutf` (`.cold`,
  far, no state) answers it, so the switch and the park's probe
  (`mega_wrprobe`, which must find the anchor before anything else is known)
  compute the same places:
  - the top is 1MB + `[mega_extkb]`, capped at 16MB;
  - the CODE area, `MEGA_CODE_KB` (`.cold`, `.mega` at its rung's distance,
    the park's scratch), is the top KBs - 59K today;
  - the TABLE block, `MEGA_TBL_SIZE` = 82KB (GDT 64K, LDT 16K at
    `MEGA_LDT_OFF`, IDT 2K at `MEGA_IDT_OFF`), is under it, its GDT end
    next to the pool, where MC7's shrinking leaves the room;
  - the pool runs from `MEGA_XPOOL` = 100000h to the table block:
    `[mega_fixkb]` KB, which `mega_xminit` takes as `xm_kb`.

  Measured under Bochs: 16MB puts the tables at FDCC00h and the code at
  FF1400h with a 15,219K pool; 2MB puts them at 1DCC00h/1F1400h with 883K.
  The pool was 14,976K on 16MB before (the old base was 140000h, and 64K of
  padding came with it).
- **Every table address is a variable.** `mega_tset` (DX:AX = the block's
  base) writes `mega_gdtr`, `mega_idtr`, `mega_ldtlin`, `mega_tbllin`, the
  bootstrap window and the LDT/IDT descriptors in one place; the switch calls
  it with `mega_layoutf`'s answer and `mega_tlowf` with its conventional
  block's. `mega_coldup` reads `[mega_coldlin]` (`mega_hilin`, a `.text`
  helper, adds `.mega`'s rung distance) and gives `.cold`'s descriptor base
  coldlin - `COLD_VSTART`. `[mega_codehi]` says whether the code went up.
- **The HMA is the pool's first block**, 64K pinned, owner `XMW_HMA` (F0h).
  MC4 is what unpins it. The hibernate's run list and the DOS park's
  "everything the pool gave out" both skip it: it holds nothing of the
  session.
- **`XMW_FIXED` names three areas above the pool** (GDT, LDT+IDT, kernel
  code) at POSITIVE offsets from the base - KB past `xm_kb` - and no
  padding; the HMA is listed as the block it is. `mega_xmfix`'s table is
  gone; `XMW_PAD` stays in the SDK unused.
- **The DOS park**: `mega_dsave`'s entries are offsets from the table
  block's base and the dreg list adds `[mega_tbllin]` (`.tbl` for an
  offset under 64K, `.tblp` for the IDT's, given in paragraphs); `.cold` and
  `.mega` are saved from `[mega_coldlin]`. The parked stub's own copy of the
  GDTR/IDTR (`mpk_tabs`) is patched at staging by `mega_dstubup`, 12 bytes
  from `mega_gdtr`/`mega_idtr` (an assembly check holds the two adjacent).
- **The hibernate** writes run 0 from `[mega_tbllin]`, `MEGA_TBL_SIZE` long,
  and a restore REFUSES an image whose run 0 is not exactly that: an image
  from before MC2, or from a machine with different RAM (D10).
- **The Task Manager** reads the fixed areas as KB OUTSIDE the pool (above
  its top now, where kern_big's are under its base), so RAM stays the whole
  machine: `Ram 0.31/3.62M` on a 4MB Bochs machine, `System>1MB 205K` = HMA
  64 + GDT 64 + LDT/IDT 18 + code 59. `tm_himax` treats the HMA's record as
  the pinned block it is.
- **Bytes:** kern_mega `.text` +32, `.cold` +117, `.mega` +110 (shared
  window overhead 3,718 -> 3,750 of 4,029); `.boot2` +12 (the blob,
  discarded); the Task Manager +48 of image; kern_big's `kernel.sys` and
  kern_small's `kernel.bin` byte-identical with a clean build of the same
  commit.
- **A method note, second of its kind.** `make build/kernel.bin` alone is
  PASS 1 of the packed kernel (SPEC.md 2.9.13): the blob carries placeholder
  `KZ_*` defines, so it differs by a byte from a tree whose last build was a
  full `make`. Compare `kernel.sys` after a full `make` in both trees.
- **`tools/os88megaseg.py`** prints the code area against its 255K cap (a
  KB byte in the walk's record), the second wall the old slot was.
- Rows named: `megahigh` (full); `megashed`, `megahiber`, `megap2hiber`,
  `megadosp`, `megakbtrip`, `megarehome`, `megapiclose`, `megacdrom`,
  `tmowner` (soak).


### MC3 as built (2026-10-25) - DONE

- **`mx_canmove`: every block moves but the HMA and an `MX_FPIN` one.**
  - `MX_FPIN` (an `MX_FL` bit) marks a block whose LINEAR address something
    holds: the DOS trip's park and arena (now owner `MX_KOWN` instead of FFh,
    pinned by `mega_dosclaimf`'s `.alloc`) and a hibernate resume's staging
    block. Both live only for the moment they are used.
  - **A deviation from 5's MC3, in the direction of the goal.** The plan
    pinned a module while its action runs, kern_big's rule. On kern_mega
    that rule is not needed: a module above 1MB is named only by SELECTORS
    (its pair, `dkv`/`thv`'s far pointers, `mega_dklibf`'s lone selector),
    the compactor rebases every LDT descriptor in a block it moves, and a far
    return or a pop reloads the base. That is the same argument a package's
    own code region moving while it is the caller has stood on since
    KERN-MEGA-PLAN 14.46 (`megaown`). So nothing is pinned for being in use;
    MC5's "nothing pinned but a module in use" is met with room to spare.
- **The token** (`MX_AUX` for owners 00h-7Fh and FFh, `mx_istok`):
  - chosen at the take where the block is (`mx_tokfit`), so the two agree
    until the first move; never overlapping a live token; never 0;
  - every cell finds the block by it and goes to where it is now: `mx_free`
    and `mx_chk` through `mx_key`, `mx_copy` and `mega_xmsel` through
    `mx_tophys`, `mega_xmrunf` (`.cold`) inline;
  - the census (a subagent read every caller) found nothing that reads a
    token in place under protected mode, so A3 holds. Its list of what the
    kernel must keep true - never 0:0, bounds on the KB-rounded size, FFh
    blocks from driver context, XMEM_RUN blocks moved with care - is met;
  - the Video Player's DRAM-interleave gap (`os88xgap.inc`) reads a token's
    low bits as physical: now a guess, speed only, never correctness.
- **A defect found by the new row, kept as its red case.** `mx_tophys`
  subtracts a SIGNED distance, and a block that moved UP leaves a borrow in
  CF; `mx_chk` handed that back as "not your block" (`MEGAXM: no 03 0002`).
  It ends in `clc` now.
- **An `OSAPI_XMEM_RUN` block** moves like an `MX_FH32` claim: cut every
  64KB with the package's rate hook held (`mx_cpflags`).
- **Top-down for every owner**: `mx_alloc`'s bottom-up arm is gone; a miss
  packs UP (`mx_packupf` from KB 0) and retries, for every owner, before the
  shed. `mx_compactf` stays for `OSAPI_MEM_REGROW`'s `.hpack`.
- **The Task Manager**: `tm_himax` replays the pack with only the HMA
  pinned.
- **Tests:**
  - `tests/megaxmove.py`, a new soak row: MEGAXM (tests/megaxm) gained a
    MOVE step - a 64KB filler above its block, freed, then a claim of every
    free KB - and reads every chunk back through the first token. Seen:
    `MEGAXM: move 0AA7 0AE7` and `MEGAXM: ok` at 4MB, 16 s under Bochs; red
    with token blocks pinned (`MEGAXM: no 42`). The row writes the packed
    `ZBIG.TXT` MEGAXM's file leg reads, which KERN-MEGA-PLAN 14.70 left to a
    hand-passed `--put`.
  - `megaown` asserts its region moves UP now (MEGAHOLE's hole is above it).
  - `megashed` and `tools/megaconvres.py` cover the pool with `MX_KOWN` +
    `MX_FPIN` blocks, so the pack leaves their cover where it is.
- **Bytes:** kern_mega `.cold` +15, `.mega` +112, `.text` +0 (shared window
  3,750 unchanged); kern_big and kern_small byte-identical with a clean
  build of the same commit; the Task Manager -12 bytes of image.
- SPEC.md 50.6.10 is the contract.
- Rows named: `megaxmove` (new), `megaown`, `megashed`, `megavidbig`,
  `megavidv2`, `megaovl`, `megarehome`, `megahiber`, `megap2hiber`,
  `megadosp`, `tmowner` (soak); `megahigh` (full).

### MC7 as built, step by step

- **Step 1, the doors (2026-10-25) - DONE.** One cell, `OSAPI_SEG` (`0x04E3`,
  SPEC.md 50.6.11), five verbs in BL rather than four cells, because a cell
  is six bytes of every kernel's `.text`: `SEG_LIN`, `SEG_REAL`, `SEG_WIN`,
  `SEG_SUB`, `SEG_FREE`. Every real-mode kernel answers the caller's own
  arithmetic. On kern_mega a window is recorded per owner in `mega_wtab`
  and freed by `mx_relall`; a SUB inside a pool block is based in it, so it
  moves with it and `mx_dfree` takes it with a claim's free. Checked by
  MEGAXM under Bochs (the `megaxmove` row): a SUB read through, no real
  segment above 1MB, a ROM window reading the BIOS date, its linear base,
  the free. Cost: `.text` +6 everywhere, `.cold` +40/+39/+68, `.mega` +900,
  `.lowbss` +128. **Open for later steps:** the 1MB machine has no pool, so
  no `mx_relinst` runs there and its windows would not be freed at an
  instance's end - the teardown hook has to move when step 5 gives
  conventional claims selectors. `OSAPI_MEM_HUGE` gets a 16KB step (the
  Video Player's and RealDMG's rolling windows) in step 5. MEGAXM's
  `OSAPI_MEM_CODESEL` check asserts the static alias `(DS >> 2) | 4`, which
  step 6 retires.
- **Step 5.1, a pair for every conventional claim (2026-10-25) - DONE.**
  `mem_sel` (`.lowbss`, one word per `mem_tab` record) holds each claim's
  DATA selector, the CODE half at - 8. `mega_mpnewf` makes it at
  `mem_claim_1`'s publish (no pair, no claim) and `mega_mpall` at the switch
  for every claim real mode made; `mega_mpfreef` frees it with the record
  (`mem_free_x`, `mem_free_owner_x`, the shed, the compactor's drop) and
  every allocator data descriptor based in the block with it;
  `mega_mpmovef` rebases every descriptor based in a block the compactor or
  a regrow moved; `mega_mpsyncf` re-aims the pair when a regrow or a
  re-home's trim changes the block. Callers still receive the physical
  segment (5.2 changes that). Checked under Bochs at 4MB and 1MB (where
  every claim is conventional): every live record's pair matches its block,
  through a Disk window, the Task Manager and the Control Panel.

- **Step 5.2, callers receive the selector (2026-10-25) - DONE.** In
  protected mode `mem_claim_1` answers a claim's DATA selector, and every
  lookup by value (`mem_find_own`, `mem_owner_of_x`, `mem_is_region`,
  `mem_can_move`, `mem_fatw_dirty`, `mem_in_xfer`) compares `mem_val` -
  `mem_sel` in protected mode, `MC_SEG` otherwise; `mem_in_xfer`'s pinned
  transfer is a selector too and is tested by its descriptor's base.
  `mem_regrow` keeps the caller's value and does its arithmetic on the base.
  A compactor move in protected mode is a REBASE and calls no relocation
  proc, every holder holding a selector. **The switch translates**
  (`mem_xlatf`, `.cold`, straight after `mega_enter`): every live record
  whose base and selector differ runs the relocation protocol once, BX = the
  base and DX = the selector - the holder's proc where one is declared and
  the kernel's half (`mem_region_reloc`'s rows, the IRQ vectors and the IDT
  through them) for every record. The TI-bit tests that meant "above 1MB"
  became `MEGA_ISHI` (`mega_ishif`: an allocator selector whose base is at
  or above 1MB) in `memory.inc`, `loader.inc`, `mod.inc` and `driver.inc`;
  the ones that mean "any LDT selector" stay (the disk layer's bounce and
  `.drvhi`, `drv_fs_call`'s redirector bounce, the LZ decoder's 64KB
  refusal) until 5.5 and 5.6 hand those paths selectors properly.
  `dsk_runcap` does its DMA-page arithmetic on a selector's BASE, so a
  conventional claim is a direct transfer and only memory above 1MB
  bounces - which is also what keeps the read-ahead landing, itself a
  selector now, from bouncing into itself. **Modules (5.3's first piece,
  taken here because the boot needs it):** `mega_mods_fix` runs after
  `mega_mpall` and names each boot-loaded module by its claim's pair -
  `MODR_SEG` the data selector, its slots and the `dkv`/`thv` tables the
  code half, found by `mega_p2d` - and `mod_check`, `mod_hi`, `mod_hiboot`
  arm and re-arm with data - 8; DESK.DRV's library selector is freed with a
  conventional image too. The loader's compressed-package path converts the
  region's selector to its real segment before adding the prefix
  (`mega_s2segf`). Checked under Bochs at 4MB and 1MB: the desktop, a Disk
  window, the Task Manager (running from a selector region on the 1MB
  machine) and the Control Panel, every pair matching its block, and a scan
  of the kernel's `.bss` and `.lowbss` finding no word still holding a
  claim's physical base. Cost: kern_mega `.cold` +400, `.mega` +51, shared
  window +4; kern_big and kern_small byte-identical with a clean build of
  the same commit. **Known slow until 5.5:** a hard-disk volume served by a
  driver (`.drvhi`) and a redirector (`drv_fs_hi`) still move a selector
  buffer a sector at a time. Rows named for the final pass: `megaown`,
  `megaxmove`, `megashed`, `megaxm`, `megahigh`, `megaovl`, `megarehome`,
  `megahiber`, `megadosp`, `drvmove` on kern_mega.
- **Step 5.3, the images (2026-10-25) - DONE.** A package region, a driver
  image and a module are pairs from the claim itself, so the pair arms of
  `MEGA_CSELTOP`, `mega_frame_cs`, `mem_reloc_call`, `mega_codesel`,
  `mega_cs2ds`, `mega_dsimg` and the fault handler's `.pairq` already did
  the right thing; the modules' arming was 5.2's. What was left is
  `OSAPI_MEM_SUBSEG` (SPEC.md 50.3.6): it answered only a region placed
  above 1MB, and a conventional region is a selector now too, so the
  caller's fallback sum named some other descriptor. `mega_rgnconv` finds
  the region's claim by its selector and the rest of the body is shared;
  `mega_cdfree` frees a claim's code twins as well as its data
  descriptors, which is what a SUBSEG code window inside a conventional
  region needs at the free. Cost: `.mega` +48. **Found on the way, and a
  package's to fix rather than the kernel's:** HEAPFRAG (tests/heapfrag)
  walks each block it claimed by adding 40h paragraphs to the SEGMENT a
  kilobyte at a time - under Bochs on the 1MB machine it faults on the
  second kilobyte, `mov es, dx` with DX = the next pair's selector + 40h.
  The kernel handed it the right selectors (a trace of every pair made,
  freed and moved confirmed it). It joins the package waves' list.

---

## 8. Addendum from `mega-dmg`: what RealDMG needs from this round (2026-10-25)

A note from the RealDMG session, for MC7's step 4 (the six exempts) and
step 5. It describes RealDMG as it stands on `elendilon` at `1f013feb`,
which this branch has not merged yet: `mega-dmg` added code selectors
(REALDMG-SPEC 16.2.4), the cartridge in place above 1MB (10.3.1), more
cache tiers (16.2.5) and kern_mega's own build of the package
(`$(MEGAPKGS)`, `PKG_MEGA`). The longer design is
`docs/plans/REALDMG-HIGHCACHE-PLAN.md` on `elendilon`. Nothing here asks
the round to change course; 7.4's "a pair for every conventional claim,
code = data - 8" already answers most of it.

### 8.1 Code RealDMG enters, and where it is

RealDMG far-jumps into, and only writes code through, a DATA name, and asks
`OSAPI_MEM_CODESEL` for the code name of each (16.2.4). The code is in four
places:

| what | where | needs |
|---|---|---|
| the core | a part of the parts carve (`op_seg`) | the carve's conversion (7.3 step 2); its code name through `OSAPI_MEM_CODESEL` |
| cache A, 64KB | the first 64KB of its claim | the claim's own pair |
| **the recompiler's part**, ~21KB | **inside cache A's claim, past 64KB** (`rw_jpseg` = the claim + 1000h + the table's paragraphs; + 1000h exactly on kern_mega, where the table is in the pool) | **a code name for a range PAST a claim's first 64KB** |
| cache B and **the extra tiers** | cache B's claim, **grown with `OSAPI_MEM_REGROW` to 1 + k x 64KB** (k up to 5), the tiers at B + 1000h, + 2000h... (`rw_jitxset`) | **a code name for each 64KB window past the first** |

**The ask (the only kernel one):** a code twin for a range inside a claim -
`SEG_SUB` with a code form (a pair, code = data - 8, the 7.4 rule), or
`OSAPI_MEM_CODESEL` answering a `SEG_SUB` selector by making its twin. The
pair over a claim stops at 64KB (`mega_mpbase`'s limit), and a lone data
selector has no code view (`mega_codesel` refuses it), so without one of
these the part and the extra tiers have no CS on the end-state kernel.
`OSAPI_MEM_HUGE`'s windows want the same, for the plan's tiers above 1MB.
With it RealDMG converts its own way: SUB the part and each tier, ask each
for its code name, and keep everything else as it is.

**Not the alternative:** splitting the part and the tiers into claims of
their own would take RealDMG past **`MEM_OWNER_MAX` = 8**. A game on kern_mega
holds five claims after its load (the frames 17K, 15K, cache A, cache B and
the carve; read off `mem_tab` on 86Box), and Machine > Log, a replay (F7)
and Machine > Profile each take one more. 16.2.5's first build took a claim
per extra tier, seven after the load, and its replay was refused - "Replay:
no room" with 91KB free. Growing B's claim is how it stays at five. If the round raises the cap on
kern_mega, say so and that route opens too.

### 8.2 RealDMG's segment arithmetic, for the census

Beyond the code above, every site where RealDMG makes a segment by
arithmetic. All of them are inside one claim, and each is a `SEG_SUB` or an
offset after the flip:

- **Cartridge RAM**: `S_RAMSEG` + bank x 200h (`rdg_rambank`, rdgsys.inc),
  at most 128KB in one claim.
- **The bank cache's slots**: `rw_slotseg` + slot x 400h (rwbank.inc). On
  kern_mega's build this is only taken when the pool is too short for the
  cartridge in place.
- **A cartridge in one claim** (one that fits the heap, the shipped build on
  every kernel): the bank table names, for bank n, the segment whose 4000h
  is the bank's first byte - a BIASED base, the claim + (n - 1) x 400h.
  This is the ROM-bias case 7.2 lists (Apple II, C64).
- **The block table**: cache A's claim + 1000h in conventional memory. On
  kern_mega's build it is an extended block behind `OSAPI_XMEM_RUN`'s first
  selector (`rw_jtx`), so that arm has no arithmetic there.
- **The frames**: `rw_fseg` = `rw_pseg` + a paragraph offset (one 17KB claim).
- **The view and the core**: through the parts library (`op_seg`), 7.3 step 2.

Already selector-safe on kern_mega, needing nothing:

- the cartridge in place (`OSAPI_XMEM_RUN`'s selectors in the bank table);
- the link patches (they write through the data name, `tr_lpes`/`tr_lpx`);
- `rw_partsmv`, which skips a word with bit 2 set;
- `rw_reloc`, which re-stamps by code name.

`XMEM_ALLOC` tokens (the cartridge's, the table's) only go back to
`XMEM_RUN` and `XMEM_FREE`, so A3 holds.

### 8.3 What changes for RealDMG under 7.4

- **Moves become rebases, and that is better for RealDMG.** A cache move
  re-ran `rt_init` (a flush) through `rw_mreloc`; with no proc called, the
  translated code, its `jmp far` chains and the block table all stay valid.
  Its relocation procs go quiet on kern_mega and stay for the other kernels.
- **The recompiler converts data to code by a TABLE** (`rt_d2c`, the view's
  `S_JITCSA`/`S_JITCSB`/`S_JITXT`, filled from `OSAPI_MEM_CODESEL`), never by
  "- 8". So it works on either rule and needs no change for the pair layout.
- **Writes through CS that remain**: `rdg_init`'s two words and the lossy
  picture's `rdg_lpatch`, about 90 completed #GPs a session on the host's
  own stack (16.2.4). They are harmless, but the end state would count them.

### 8.4 An open question the round may want anyway

**A package-visible hibernate notice.** RealDMG's cache is regenerable. A
large cache in the pool should be FREED before a hibernate and claimed again
after, rather than written into the image. MC4's "the trip offers a
hibernate" makes the image the size of what is in use. Drivers have
`hbm_detach`/`hbm_reload`; packages have nothing.

### 8.5 How to check RealDMG after the flip

- **`tests/rdgmega.py`** (Bochs, `MEGATRAP=1`, about 4 minutes), three legs,
  each running blargg's `cpu_instrs` under the recompiler:
  - the shipped build;
  - kern_mega's build;
  - kern_mega's build squeezed to ~0.5KB a tier, so it recycles through
    every tier, the extra ones included.
  
  It fails on a trap charged to the core or a cache's code name.
- **`tests/rdgcore/rdgwin.py --vm 286-mega`** (86Box), for speed.
- **`tools/rdglog.py`**, which compares a field log with an emulator log of
  the same replay.

---

## 9. Addendum from `mega-video`: what the Video Player needs from this round (2026-10-25)

A note from the Video Player session. It describes the player as it stands
on `elendilon` at `08a25018`, which this branch has not merged yet:
KERN-MEGA-PLAN 14.73 there (*the Video Player on a BIOS-served disk*) fixed
four causes of pauses and over-long plays on kern_mega. The owner has asked
that the next step - **BIGSP super-packets read in place above 1MB** - wait
for this round. 5's MC9 already says "BIGSP in place stays with the Video
Player round". This section is what that round will need from this one, so
the end state does not have to be reopened for it.

### 9.1 The ask: a window the rate hook can re-aim, anywhere in a pool block

**Where things stand.** On kern_mega the player decodes in place from an
`OSAPI_XMEM_ALLOC` block - the file held whole, or the bank - through
`OSAPI_XMEM_RUN`'s run: a window every 32KB, each 64KB long. `vp_xmk`
picks window `offset >> 15` at `offset & 7FFFh`. That covers any record of
32KB or less. A BIGSP super-packet is up to **127 sectors (63.5KB)**, and
most of them, 38-63KB, run off their window. So `vp_pmbigq` refuses in
place, and a BIGSP file under protected mode copies its records through
the conventional ring instead. That is LASTX's ~5% (14.73), and it needs
room the Victory 286 runs short of.

**Why a run cannot fix it.** A run of step S holds every record up to
64KB - S. Holding 63.5KB needs a 512-byte step: on a 3MB hold that is 6,144
LDT entries, 48KB of LDT. That is exactly the usage this round exists to
remove.

**Why `OSAPI_SEG` as specified cannot fix it either.**

- The decode runs in the player's `FSXF_RATE` hook (`vp_hook`, at IRQ0), and
  §53.2.2 forbids kernel calls there. `vp_xmk` is reached from that decode.
- `SEG_SUB` takes a 16-bit paragraph offset (1MB of reach), and a held file
  can be larger.
- `SEG_SUB` has no re-aim. Asked for a new base each record, it would hold
  one LDT entry per distinct record until the block is freed - thousands in
  a play.
- `SEG_WIN` re-aims, but it takes a physical PARAGRAPH, so it cannot name
  memory above 1MB.

**What would do it.** A small number of windows (2-4) over the caller's own
pool block. The caller re-aims one to a **32-bit offset into the block**,
64KB of reach, **legal inside the rate hook**: IF = 0, no lock, nothing
that yields, inside §53.2.2's 48 bytes of stack, the cell's own frame
included. It is one descriptor's base rewritten (three bytes), checked
against the owner and the block's end. The shape is yours to choose:

- a re-aim verb on `OSAPI_SEG` that takes an existing SUB;
- a hook-safe form of `OSAPI_XMEM_SEL`;
- a rolling form of `OSAPI_XMEM_RUN`.

The contract the player needs is:

- an offset in, a selector out (or the same selector re-aimed);
- callable from the hook;
- no LDT entry per call.

One re-aim per BIGSP record is about one per frame at 25 fps.

**Moves.** D2 makes these blocks movable. The windows must be rebased with
the block (`mx_desc`, as a SUB is today), and an offset re-aim must use the
block's CURRENT base. A piece must also never be copied while the hook can
read it: either the hook is held off for each piece, the rule
`OSAPI_MEM_HUGE`'s 32KB form already has (§50.3.5), or a block with a live
window does not move. Either works for the player.

### 9.2 What must stay true, for the paths 14.73 fixed

- **`OSAPI_XMEM_RUN`'s selectors stay CONSECUTIVE** (selector + 8k). The hook
  computes them without calling the kernel (`vp_xmk`: window x 8 +
  `[vp_xrun]`). T69 and MECH2 play in place through this (the XMS bank in
  place, `[vp_einp]` 2), and step 6's LDT-as-allocator must still hand out a
  run.
- **DMA-door claims stay page-safe for their whole life.** The player claims
  through `OSAPI_MEM_CLAIM_DMA`:
  - the ring's bounce (`vp_rhtry`, CX = 32);
  - the ring's 64KB or 32KB+ head (`vp_rclaim`, `vp_rclk1`);
  - the ring's slots.

  14.73's second cause was a bounce that straddled a 64KB page. Every chunk
  then cost extra `int 13h` staging calls through `dsk_rah`. 7.4 lets every
  claim move "but a DMA claim with a head". The player needs these claims to
  be ones that stay put - or that only ever move to page-safe spots - and to
  stay direct transfers for `dsk_runcap` (5.2's base arithmetic already does
  that for conventional selectors).
- **Two kern_mega kernel fixes arrive with the merge, and step 6 must keep
  them working**:
  - `mega_svc_back` runs `sch_rhook` (through `mega_tcall`) when a
    reflection returns with `[sch_rpend]` owed (§53.2.2's kern_mega
    paragraph).
  - `mega_rmaskf` leaves an option ROM's IRQ unmasked during a service
    reflection. It recognises one by its IDT GATE: selector `MEGA_SEL_CODE`,
    offset within 14 x 6 of `mega_irv`. It does not read the IVT, because an
    IVT cell can hold a selector. If the GDT cut moves `MEGA_SEL_CODE` or the
    reflection stubs, that test must follow them.
- **SOUND.DRV's direct ring** (SPEC 34.5.2.1 on `elendilon`) now counts blocks
  from the 8237's position (`sbl_dleft`). It does offset arithmetic inside
  the ring and no segment arithmetic, so it adds nothing to the census. The
  external ring the player hands over is still a segment today, and is in
  7.1's "five packages" item.
- **Claim count.** The player's ring is a head plus slots, alongside the
  bounce and its own region. Nothing in this round should lower
  `MEM_OWNER_MAX`.

### 9.3 How to check the player after the flip

14.73's method, on 86Box `286-victory` with an XT-IDE ROM disk (BIOS-served,
the case that paused) and an SB16:

- Build `make mega`, put the VGA demo videos on a VHD, and play each one
  while counting frames drawn by 64 s.
- 14.73's table is the bar. At `08a25018`:

  | video | frames by 64 s | full play |
  |---|---|---|
  | T69 | 1,505 | all 1,838 in 72 s, 0 pauses |
  | MECH2 | 892 | |
  | LASTX | 1,273 | |
  | BCRRT | 1,407 | |
  | WILLY | 844 | |

- The rows are `megavidbig` and `megavidv2`, which 5 already names.

Once 9.1 exists, the Video Player round can delete `vp_pmbigq`'s refusal
and the copying bank's PM arm (`vp_rclk1`), and LASTX goes in place.
