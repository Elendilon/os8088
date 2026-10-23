# NO-PINNING-PLAN - every heap claim moves, unless it has a reason

**Status: OPEN. Wave 0 is BUILT** (the C SDK's eager overlay carve, below).
Branch `no-pinning`, cut from `elendilon`.

## 0. Why

The heap compacts (SPEC.md 66). A claim that cannot move is a WALL: free
memory either side of it cannot be joined, so the machine reports 400 KB free
and refuses a 300 KB picture. Each pin is cheap for whoever adds it, and the
cost lands on the user much later. That user cannot see a pin and cannot fix
one.

**The policy (the owner's).** A claim may be pinned for one of three reasons
and no other:

| bucket | reason | shape |
|---|---|---|
| **M** | it is an on-demand kernel MODULE (`MEM_K_MOD`, SPEC.md 2.8) | static, and temporary. Converting modules is the likely next piece of work |
| **D** | a device is armed to write into it, or is writing into it now: DMA, a bus master, an `int 13h` transfer, an ISR filling a ring | momentary: it lasts while armed |
| **C** | the program is executing in it, or using it, RIGHT NOW: a frame stands in it, a worker is mid-loop in it, the kernel holds a pointer into it across one call | momentary: it lasts while in use |

"Someone did segment arithmetic and did not make it survive a move" is not a
reason. The fix for that is a relocation proc. For almost every claim the
proc is a `ret` or one store (SPEC.md 66.3, author rule 2).

**Other candidate reasons, judged.** Only one comes close:

- *A sheddable cache with no proc.* The room comes back by SHEDDING it, so it
  is never a permanent wall. But a shed throws away contents that a move would
  keep (seconds of `int 13h` to rebuild), and a claimant with a FLOOR cannot
  shed at all (SPEC.md 50.6.6). **Verdict: not a reason.** Give each cache a
  proc (item K6). Shedding stays as the fallback.
- *The address is visible to hardware other than a DMA engine* (GDTR/IDTR on
  kern_mega). This is bucket D or nothing. A proc that reloads the
  descriptor-table registers is a few instructions. **Not a reason.**
- *The build has no compactor* (`kern_small`; `NOCOMPACT`). `NOCOMPACT` is an
  A/B knob, so it is fine. **kern_small is SETTLED (the owner, 2026-10-23):
  out of scope.** Nothing there compacts, so movable or pinned makes no
  difference. On a 128 KB machine the user is the memory manager: they can
  open one large thing or a few small ones, there are no driver interactions
  they cannot see, and what is open on the screen is what is claimed. *"You
  can run this at all"* is bought with *"you manage your own free RAM"*. Every
  kernel proc below is inside `%ifdef OS88_COMPACT`, so it costs kern_small
  nothing.

**Two more owner constraints bind every item below:**

- **RealDMG and the Video Player may not lose performance.** They still
  comply. The shape that makes that possible is a relocation proc that does
  ALL the work at MOVE time: it patches the state block, the bank table and
  the ring pointers once, when the compactor calls it. The hot loop is not
  touched, keeps its cached segments, and pays nothing per frame. The
  alternative, *"re-read your base at each use"* (SPEC.md 66.3 rule 2), is
  REFUSED for these two, because it adds a load inside the loop. Each one's
  gate is a measured frame or emulated-cycle rate before and after on
  MartyPC, and the after must not be lower.
- **Kernel bytes stay minimal.** Each kernel item is costed in 2.2, and any
  that is large may wait for a size pass.

## 1. Wave 0 - BUILT: the C SDK's eager overlay carve (what LEMMINGS pinned)

**What happened.** LEMMINGS' wave 4 (SPEC.md 116.6) found a real defect. A C
module function calling ANOTHER module function compiled to
`call far [cc_ovm_*]`. That pushes the module's own CS, and the callee's plain
`retf` pops it. A claim under that call which compacted would move the module
and leave the CS on the stack stale. `ovl_launch` -> `ovl_level_load` ->
`ovl_claim_all` claims ~329 KB three frames deep. The fix that shipped was to
PIN the eager carve on every C package (CWORD, RUNCPM, LEMMINGS), for the
program's whole life. The lazy arm and the `<NAME>.OVL` sidecar kept the
exposure and were left as an open item.

**The fix (this branch).** The pin is gone, and the call is fixed instead:

- `tools/cc8086.py` emits a module-to-module call as `mov bx, cc_ovm_<f>` /
  `call far [cc_ovvmm]`.
- `apps/cc/crt0.asm` adds `cc_ovmthunk`, which works like `cc_ovthunk`. It
  pops the 4-byte return, puts the offset in the same stash, and far-calls the
  callee from RESIDENT code. The region's CS is pinned by `mem_in_nest` while
  a callback stands, which is bucket C. The thunk then rebuilds the `retf`
  from `[cc_ovcs]`, and `cc_ovbind` re-stamps that on every move. The callee's
  frame is still four bytes above its arguments, so no compiled offset
  changes.
- `CC_OVDEPTH` goes from 16 to 32 words, because the stash now carries
  module-to-module nesting too. When the stash is full, `cc_ovmthunk` falls
  back to the direct far call, which is the old behaviour. The depth is
  therefore a safety margin, not a limit on correctness.
- `cc_ovinit` declares the eager carve movable again through `cc_ovcarve`
  when the carve holds the module alone (`OS88_PART_N` = 1): CWORD, RUNCPM,
  LEMMINGS.
- The same thunk closes the lazy arm's and the sidecar's exposure.
- `tests/ovlhigh.py` assertion 4 is flipped back: `MC_RLOC` != 0.
- `tools/ccpeep.py` treats `call far [cc_ovvmm]` as READING BX. **The first
  build broke without this**, and silently: the peephole assumes no call reads
  a register, so it deleted the `mov bx` as dead. `tests/covl` then answered
  0 where it should answer 1234. The only reason anyone saw it was a by-hand
  A/B on MartyPC, because **no suite row runs covl**. W0-T closes that gap.

**Cost.** Per module-to-module call site: 7 bytes where it was 4. Resident:
the thunk (~30 bytes) plus 32 bytes of stash. Per call: ~40 us on a
4.77 MHz 8088.

**Still to gate (W0-T).** A row that really compacts the carve UNDER a live
module-to-module frame, then returns through it. `tests/covl` already makes
module-to-module calls (`ovl_mix` -> `ovl_inner`) but no row runs it, and
nothing forces a move at that moment. Shape: cmemmove.py's recipe (heapfrag
owns the floor, the test package lands above it, heapfrag exits). The test
package makes a claim from inside `ovl_outer -> ovl_inner` that needs the
pass, then asserts three things: the carve's base changed, `ovl_outer`'s
answer is right, and the window is still alive. Then break it on purpose:
make cc8086 emit the old direct call, and the row must go red.

## 2. The inventory

Taken across the whole tree on this branch, checked against code. Each row
gives a bucket and **what retires it**. ⚑ = the reason is a derived pointer or
segment arithmetic (the case the policy refuses outright).

### 2.1 Kernel rules in `mem_can_move` (kernel/memory.inc)

| rule | bucket | verdict / work |
|---|---|---|
| `MC_RLOC` = 0 | - | the default. Every row below is this |
| `MEM_K_MOD` | M | allowed. Next piece of work (modules become movable) |
| `mem_in_nest`, `[ld_base]`, `mem_in_xfer`, worker running and not parked | C/D | allowed, all momentary |
| **ANY `[drv_wcnt]` != 0 pins EVERY driver image** | D, too broad | **K1**: count workers per image. One driver's service task should not freeze the others |
| **ANY `[drv_wcnt]` != 0 pins EVERY `MC_DMA` head** | D, too broad | **K1**: a per-claim "a chip is armed here" bit, set by the arming driver |
| region with a worker and no restart point | NONE | only FROTZ is hit (2.4) |
| kern_small: no compactor at all | - | **settled, out of scope** (0) |
| *(a gap, not a pin)* a compaction run by a task other than the UI task | traced, 2026-10-23 | **K8, ANSWERED.** The allocator checks no caller. Two non-UI paths reach it. (1) **A dying package's worker**: `OSAPI_TASK_ALIVE` → `inst_task_die` (instance.inc) takes `gfx_lock` → `inst_unwin` → `wm_destroy`'s repaint → `wm_su_bank` → `wm_su_take` → `mem_claim` → `mem_compact`, on the worker's stack, far-calling the surviving windows' `W_PAINT` there too. (2) **Fractal's worker** calls `OSAPI_MEM_REGROW` under the gfx lock; regrow never compacts. **What makes both safe today is the GFX LOCK, by accident.** Callbacks run holding it, and both paths take it first, so neither can run while the UI task is suspended inside a package. `menu_drop` holds it across its `task_yield` loop, which is why no worker can claim while a menu is down. **SPEC.md's menu sentence (*"a package worker can claim while a menu is down"*) is STALE**, and rule 7 holds in practice. Proposed: (a) correct the sentence; (b) write the gfx-lock reason into SPEC.md 66.3 as the binding one, instead of rule 7's *"None of this is enforced"*; (c) have `inst_task_die` not BANK raise caches during its repaint, so the dying worker never reaches `mem_claim`. That is the last task path, and it costs ~6 bytes (a flag tested in `wm_su_bank`). Then a non-UI compaction cannot happen at all, and no momentary pin for it is needed |

### 2.2 Kernel claims - checked against the code, and COSTED

Re-read claim by claim on this branch; that corrected the first inventory in
three places. `MEM_P_ICO`, `MEM_P_DIRW`, `MEM_P_MSAVE`, `MEM_K_CLIP`,
`MEM_K_SC` and the persistent `MEM_K_ASC` cache already declare a proc, and
`MEM_K_DRV` moves under SPEC.md 66.6.3. The comment on `MEM_P_FATW` claims
`mem_can_move` refuses any purgeable cache. That stopped being true: a cache
with a declared proc moves now (`mem_can_move`'s `.notpg` note).

**The prices.** A kernel proc follows `dsk_rah_reloc`'s or `ico_reloc`'s
shape: `cmp bx, [w] / jne / mov [w], dx / ret`, 11 bytes. The call site that
declares it, `mov ax, proc / call mem_movable_x`, is 6 bytes (8-10 through
`COLD_SEG`). So **a one-word claim is ~17 bytes, all on kern_big, behind
`OS88_COMPACT`**. These are estimates in that measured shape. Each item's own
measured cost goes in when it is built.

**A FINDING THAT SAVES BYTES. Top-down claims made at BOOT and never freed
are not walls.** They ARE the ceiling: everything claimed later lands below
them, and nothing above them is ever freed to open a hole. Pinning them costs
the arena nothing. That puts `MEM_K_FONT` and `MEM_K_MTBL` (82 KB) at
**0 bytes, no work**. Each stays listed with that reason, and the ratchet (4)
must accept the reason only when the claim is (a) top-down, (b) made before
the first desktop frame, and (c) never freed.

| claim | life / door | bucket | work | kernel bytes (est.) |
|---|---|---|---|---|
| `MEM_K_MOD` | on demand | M | the module conversion, next | - |
| `MEM_K_FONT` 1 KB | boot, top-down, never freed | ceiling | none | **0** |
| `MEM_K_MTBL` 82 KB (kern_mega) | boot, top-down, never freed | ceiling | none, while it stays boot-only | **0** |
| `MEM_K_BAND` | `BAND=1` knob only | - | none on a shipped kernel | **0 shipped** |
| `MEM_K_ASC` flush, `MEM_K_SC` compose, `MEM_K_CLONE`, `MEM_K_HIB`, `MEM_K_CMPR` | one call or operation | C/D | none: the kernel is using it for that call | **0** |
| **K1a** `[drv_wcnt]` pins every `MC_DMA` head | - | D, too broad | **delete the check**. `SOUND.DRV` pins its own ring while a double-buffered stream is open (`OSAPI_MEM_MOVABLE` with AX = 0) and re-declares it when the stream closes, which is what its DIRECT stream does already (sb.inc's pool). The kernel then has nothing to ask | **-12** (kernel), +~12 in `SOUND.DRV` |
| **K1b** `[drv_wcnt]` pins every driver IMAGE | - | D, too broad | a per-row worker count in `drv_tab`. Spawn and exit bump the row of the image the task runs in, and `.drvimg` tests that row. Only `SOUND.DRV` spawns a task (`OSAPI_DRV_TASK` has one caller), so this is worth doing only when a second driver does. **Defer** | ~45 + `DRV_MAX` `.bss` |
| **K2** `MEM_K_IMG` 1 KB per mounted `.img` | mount, mid-session, top-down: **a real wall** | NONE ⚑ | re-read `IMG_DVSEG` in `dsk_xfer`'s `.img` arm after the nested transfer, plus a proc that walks the image rows for the old base | ~40 |
| **K4a** `MEM_P_RAHB` 5 KB (kern_mega) | mount | NONE | one-word proc on `[dsk_rah_bnc]`, `dsk_rah_reloc`'s shape | ~17 |
| **K4b** `MEM_K_COPY` | one Cut/Copy/Paste, including a suspended overwrite question | C, but held across user waits | one-word proc. The transfer itself is pinned by `mem_in_xfer` already | ~17 |
| **K6a** `MEM_P_WSAVE` raise caches | bottom-up, one per covered window: **the commonest kernel wall in a normal session** | NONE (shed at rank) | a proc that finds the old base in `wm_su_segs` and stores the new one | ~22 |
| **K6b** `MEM_P_FATW` FAT windows | bottom-up per volume | NONE (shed at MED) | a proc for `dsk_fatwc` AND `[dsk_fatseg]`, the second naming word. Fix the stale comment too | ~25 |
| **K6c** `MEM_P_FLIST` multi-file clipboard, 1 KB | until the next Cut/Copy | NONE | one-word proc on `[fcp_lseg]` | ~17 |
| ~~`MEM_P_VIEW`~~, ~~`MEM_K_SAVE`~~, ~~`MEM_K_CLIP` small~~ | kern_small | - | settled, out of scope | 0 |

**Kernel total if every row is taken: ~138 bytes** (K2 + K4a/b + K6a/b/c,
less K1a's 12), plus K1b's ~45 when it is wanted. Proposed: **take K1a, K2
and K6a now**, ~50 bytes net: the two that open real walls and the one that
pays for itself. Leave K4/K6b/K6c (~76) for after the next size pass.

### 2.3 Drivers

| claim | bucket | retires it |
|---|---|---|
| `HDDTOOL.DRV`, `RAMPAGE.DRV`, `HTTPPAGE.DRV` page images (a base that is a CS, `[rd_pfar]`-style far pointers) | NONE | **R1**: load them through the `MEM_K_DRV` path, or give them a proc that re-stamps the far pointer |
| HTTPFS index (hfidx.inc), 16 KB, life of the mount | NONE | **R2**: proc re-points `hf_iseg`/`hf_tseg` |
| VOLUME save-under, 2-30 KB while the popup is up | C | allowed; a `ret` proc is free (R2) |
| Sound Blaster ring / direct pool | D | allowed (narrowed by K1) |
| install/mount/MBR bounce buffers, xmem HMA, RAM-disk write buffer | C/D | allowed |

### 2.4 Package regions and workers (`tests/movable.txt`)

| line | bucket | retires it |
|---|---|---|
| csload, wdload, scload, dosload, pxstein: launch images | C (`[ld_base]`) | correct as they stand |
| **SHEET region** - `ch_ovbind` stamps CS into `CHART.OVL`'s vectors; the 52 KB chart overlay claim is undeclared too | NONE ⚑ | **P1**: the overlay becomes a PART in the package's own segment (SCRIBE's SPEC.md 95.8.8 shape). Then both lines go |
| **FROTZ worker** - `zi_yield` holds ES = the story's PC segment across the yield | NONE | **P2**: show whether an opcode in flight at `zi_yield` has committed; if it has, declare the restart point at the burst boundary |

### 2.5 Assembly packages - undeclared data claims

Unless marked, each fix is "relocation proc is a `ret` or one store; re-read
the base at each use". The ⚑ rows are the ones that need real work.

| package | claims | work |
|---|---|---|
| **REALDMG** ⚑ | ROM, SRAM, JIT, profile, bank table, logs | **A1, PERFORMANCE-BOUND**: one proc does all the work at move time. It patches the core state block, the bank table and any JIT code that has a segment baked in. Then it **forces a resync on return**: the emulation loop re-reads its cached segments at the next slice boundary, where it already yields, never inside an instruction. Zero instructions are added to the dispatch loop. Gate: emulated cycles per host second on MartyPC with a cartridge running, before and after, and the after must not be lower. A JIT block holding an absolute segment is the case to audit first: if one exists, the proc relocates it or flushes the JIT, and is never allowed to re-read per instruction |
| **WORD**, **SCRIBE** | doc, CHP, PAP, undo, italic, picture (up to 40 KB), scratch | **A2**: "nobody has looked". Audit, then mostly `ret` procs |
| **BROWSER** | up to 63 KB + 8 + 6 | A3 |
| **TEXPAD** | source buffer (`[tp_srcseg]`) | A3: the proc is named in its own comment and not written |
| **PAINT** ⚑ | GIF staging (C), LZW 16 KB (`[pt_gbase]` derived) | A3 |
| **FROTZ** | scrollback 24 KB (outside `zf_reloc`) | A3 |
| **CLEAR SKIES** ⚑, **TANK**, **PIXELSTEIN**, **ISOTRON**, **1942** | shadows/canvases 16-64 KB | **A4**: in use only inside the fsx bracket, so they are bucket C there. Outside it, either free them or declare them. CS keeps ES from `[cs_tseg]` across spans, so its proc must also be safe at the park points |
| **EXCITEBIKE** ⚑ | compiled poses are far-called IN the claim (a CS) | **A5**: a proc that re-stamps the pose vectors |
| **VIDEO** ⚑ | ring, "page-safe and never moved" | **A6, PERFORMANCE-BOUND**: the ring is bucket D/C only WHILE A PLAY RUNS (the reader, the hook and a card may all be writing it). Declare it movable when the play ENDS, and pin it again (`OSAPI_MEM_MOVABLE` with AX = 0) when the next play STARTS. Both happen outside the frame loop, so the play path gains nothing. A move between plays is one proc storing the ring's segment. Gate: the Video Player's frame rate on its demo videos, before and after |
| **MIDIRACK**, **TRACKER**, **AUDIO**, **WIREFLEET**, **1942** PCM rings | D while armed, NONE idle | A6 |
| **THE WIRE**, **FTPD**, **CHART**, **PIXEL**, **TELNET**, **RECORDER**, DeskClock, DotDel, StikNote | assorted | A3 |
| `os88type.inc` face cache 8 KB | NONE | **A7**: shared include, so one proc covers every carrier |
| `os88parts.inc` carve ⚑ (op_claim) | "every part's segment is arithmetic on this base" | **A8**: declare from the library with a proc that stores `op_base`. A package that banks a part segment supplies a hook (as C2) |
| lazy `op_fetch` claims | declared only by DrMario, Excitebike, Pixel | A8 |
| **DOS** `dos_hk_claim` | undeclared | A3 |

### 2.6 C SDK and C packages

| item | work |
|---|---|
| eager carve, one row | **BUILT** (wave 0) |
| **C2**: eager carve, more rows (C64, APPLE2: ROM + overlay) | a C hook (`os88_onparts(was, now)`, or route through `os88_onmove` with the carve's base) so a program that banked `os88_part_seg()` is told. Then declare unconditionally |
| `os88_mem_claim` is born pinned; only CWORD declares (undo, 9 KB) | **C3**, per package below |
| **LEMMINGS** - mask 32, bank 96, main 60, rec 16, T 125 (VGA) / world + shadow; **held across a suspended level, so up to ~330 KB pinned on the DESKTOP** | **C4, first after wave 0**: `CC_HAS_ONMOVE` re-pointing the seven `lem_cl_*` words. First check that the asm rasters (`.inc`) load the segments from those words at each frame, not once per level |
| **C64** RAM 64 KB, **APPLE2** RAM 49 KB + 53 KB FSX, **RUNCPM** Z80 64 KB | C3: `os88_onmove` re-pointing `ramseg` / `rc_zseg`. Confirm the core reloads the segment at the top of each burst |
| **WEAVE** ⚑ bundle, VM, canvas, grid; lazy part 0 with `w_cmseg` copied | C3 + A8 |
| **LOOM** ⚑ 29 / 62 / 50 KB project buffers; lazy preview part with `lm_pvseg` copied | C3 + A8 |

## 3. Order

Ranked by the free memory each recovers on a real session, then by cost.

1. **W0-T** - the move-under-a-frame row for the C overlay (gates what is
   built). **K8** (c), ~6 bytes, plus the two SPEC.md corrections.
2. **C4** LEMMINGS - the largest pin on the desktop, and the package this
   branch exists for.
3. **K1a, K2, K6a** - ~50 kernel bytes net (2.2). The rest of the kernel
   rows wait for a size pass.
4. **C3/C2** C emulators and Weave/Loom - 50-64 KB walls each.
5. **P1** SHEET chart overlay as a part - 52 KB + the region.
6. **A2** WORD/SCRIBE audit, **A1** REALDMG.
7. **K4, K6b, K6c** (~76 bytes) after a size pass, and **K1b** when a second
   driver spawns a task.
8. **A3-A8** the remaining package claims, one row each.
9. **R1/R2** drivers.
10. **P2** FROTZ worker - needs a proof, not just code.
11. ~~K7~~ kern_small - settled: the user manages its RAM (0).

## 4. The ratchet (after the work)

Add a FULL-tier row, as the owner asked, in the `t_movable` shape. It is
host-side, so cheap:

- Every `OSAPI_MEM_CLAIM*` / `mem_claim*` / `os88_mem_claim` site in
  `apps/`, `drivers/` and `kernel/` must either be followed by a declaration
  (`OSAPI_MEM_MOVABLE`, `os88_mem_movable`, a kernel proc) or appear in
  `tests/pins.txt` with its bucket (M/D/C) and a reason.
- Like `tests/movable.txt`, the list turns ONE way. A line whose claim now
  declares is a failure.
- A bucket-C line has to name the call or bracket it is confined to, and a
  bucket-D line the device. A line with neither is refused.
- A runtime half on MartyPC: boot, open the heavy packages, read `mem_tab`,
  and fail on any live claim with `MC_RLOC` = 0 that is not M, not in a
  transfer, and not in the nest. This catches pins the source scan cannot
  see.
