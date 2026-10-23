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
  A/B knob, so it is fine. **kern_small is a real question for the owner**:
  SPEC.md 66.0 left the compactor out of the 128 KB build to save bytes, and
  that pins every claim on the machine that has the least memory. Item K7.

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
| kern_small: no compactor at all | NONE | **K7**, the owner decides |
| *(a gap, not a pin)* the UI task PRE-EMPTED inside a package, with a data claim's segment in ES or the overlay's CS in its interrupt frame, while another task's claim compacts | C, unguarded | **K8**: SPEC.md 66.3 context 3 says "a worker may not claim", but SPEC.md 13's menu note says a package worker can, while a menu is down. If it can, `mem_can_move` should pin the claims of every package standing in the nest whenever the compacting task is not the UI task. That is the momentary pin bucket C describes, and it is the pin that makes ALL the other declarations safe. Settle which spec sentence is true first |

### 2.2 Kernel claims

| claim | size / life | bucket | retires it |
|---|---|---|---|
| `MEM_K_MOD` (mod.inc, driver.inc, stikmenu.inc) | 2-8 KB | M | the module work |
| `MEM_K_IMG` ⚑ (diskops.inc `.build`) | 1 KB per mounted `.img`, for the mount's life | NONE | **K2**: `dsk_xfer`'s `.img` arm re-reads `IMG_DVSEG` after the nested transfer, then a one-word proc |
| `MEM_K_MTBL` (mega.inc) | 82 KB, whole session, kern_mega | NONE | **K3**: a proc that rewrites the descriptor bases and reloads GDTR/IDTR |
| `MEM_K_FONT` (font.inc) | 1 KB, boot to shutdown (copy verdict only) | NONE | **K4**: one-word proc |
| `MEM_K_BAND` (band.inc, `BAND=1` only) | `BAND_KB` | NONE | **K4**: one-word proc (`bnd_seg`) |
| `MEM_P_RAHB` (disk.inc, read-ahead bounce) | 5 KB | NONE; its comment's premise ("a page-safe claim is pinned") stopped being true at SPEC.md 66.4.2 | **K4**: proc stores `dsk_rah_bnc`; D only while a transfer is in it, which `mem_in_xfer` already covers |
| `MEM_K_COPY` (filecp.inc) | one copy | D while transferring | **K4**: `ret` proc; `mem_in_xfer` covers the transfer |
| `MEM_K_CMPR` ⚑ (compress.inc) | 2x file + 40 KB, one operation | C | allowed while compressing; a proc that rebuilds the three derived segments costs little and removes the argument (K5, low priority) |
| `MEM_K_ASC`, `MEM_K_SC`, `MEM_K_CLONE`, `MEM_K_HIB` | one call each | C/D | allowed |
| `MEM_P_WSAVE`, `FATW`, `ICO`, `FLIST`, `VIEW` | caches | NONE (shed, not moved) | **K6**: give each a proc; shedding becomes the second resort |
| kern_small `MEM_K_SAVE`, `MEM_K_CLIP` | - | NONE | K7 |

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
| **REALDMG** ⚑ | ROM, SRAM, JIT, profile, bank table, logs | **A1**: a proc that patches the core state block and the bank table |
| **WORD**, **SCRIBE** | doc, CHP, PAP, undo, italic, picture (up to 40 KB), scratch | **A2**: "nobody has looked". Audit, then mostly `ret` procs |
| **BROWSER** | up to 63 KB + 8 + 6 | A3 |
| **TEXPAD** | source buffer (`[tp_srcseg]`) | A3: the proc is named in its own comment and not written |
| **PAINT** ⚑ | GIF staging (C), LZW 16 KB (`[pt_gbase]` derived) | A3 |
| **FROTZ** | scrollback 24 KB (outside `zf_reloc`) | A3 |
| **CLEAR SKIES** ⚑, **TANK**, **PIXELSTEIN**, **ISOTRON**, **1942** | shadows/canvases 16-64 KB | **A4**: in use only inside the fsx bracket, so they are bucket C there. Outside it, either free them or declare them. CS keeps ES from `[cs_tseg]` across spans, so its proc must also be safe at the park points |
| **EXCITEBIKE** ⚑ | compiled poses are far-called IN the claim (a CS) | **A5**: a proc that re-stamps the pose vectors |
| **VIDEO** ⚑ | ring, "page-safe and never moved" | **A6**: D while playing; between plays nothing un-pins it. Declare it, and pin it through K1's armed bit |
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
   built). **K8** - settle the worker-claim question before declaring more.
2. **C4** LEMMINGS - the largest pin on the desktop, and the package this
   branch exists for.
3. **K1** - per-image and per-claim DMA pins. Small kernel change; every
   driver-heavy session gains from it.
4. **C3/C2** C emulators and Weave/Loom - 50-64 KB walls each.
5. **P1** SHEET chart overlay as a part - 52 KB + the region.
6. **A2** WORD/SCRIBE audit, **A1** REALDMG.
7. **K2-K4, K6** kernel one-word procs.
8. **A3-A8** the remaining package claims, one row each.
9. **R1/R2** drivers.
10. **P2** FROTZ worker - needs a proof, not just code.
11. **K7** kern_small compactor - the owner decides.

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
