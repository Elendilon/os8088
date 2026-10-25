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

