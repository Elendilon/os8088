# Gating heap compaction out of kern_small — costed, measured, and REFUSED

**Status: research, nothing built. The answer is NO, on a measurement.**

The ask: kern_small's heap is small and it can load no driver, so would the
128KB machine rather have the compactor's bytes back than the compactor?

The bill is **1,725 resident bytes**, worth **1.5 KB of heap** on the tree this
was taken on. What it costs is the ability to launch a 32KB package once two
Disk windows are open — measured as an A/B on the floor machine, same disk,
same gestures:

| | `PAINT.O88` after A: and B: are open |
|---|---|
| kern_small as it ships | **loads** |
| kern_small `HEAPCOMPACT=0` | **"Out of memory"** |

and 1.5 KB of extra floor does not close that gap, because the gap is 9 KB.

**The premise about drivers is right and does not reach the answer.** No driver
image, no `SOUND.DRV` ring, no donated listing exists on kern_small — SPEC.md
51.0 gates the whole mechanism out — and none of those is what compaction is
doing there. What it is doing is moving **two 2 KB Disk-window view caches**
that sit either side of the directory read-ahead, and those 2 KB claims strand
**21.5 KB** of a 48.5 KB heap.

Every byte below is nasm's own listing of `build/smallk/kernel.bin`; every heap
figure is read out of `mem_tab` on `os8088_5150_cga_128k` under MartyPC.
Taken at `d3ffb10`, 2026-09-08.

---

## 1. What gating it out would save

Not the `HEAPCOMPACT=0` knob — see 2. This is the whole feature: the compactor,
the one predicate that decides what may move, the relocation dispatch, the
worker park (SPEC.md 66.5) and the four relocation procs in the kernel. The
`OSAPI_MEM_MOVABLE`, `OSAPI_MEM_PARKSAFE` and `OSAPI_TASK_RESTARTABLE` slots
stay and become refusing stubs, `gfx_blit1`'s precedent on this kernel — a
small-built package calls the same table at the same offsets.

| | `.cold` | `.text` |
|---|---:|---:|
| `memory.inc` — `mem_compact`, `mem_cp_end`, the seventeen `mem_cp_*`, `mem_can_move` and its five helpers (`mem_is_region`, `mem_frameless`, `mem_busy_seg`, `mem_in_nest`, `mem_in_xfer`), `mem_reloc_call`, `mem_movable_x`, `mmf_mem_movable`, the call sites | 962 | — |
| `memory.inc` — `mem_rr_walk`, `mem_region_reloc`, `mem_rr_tab` | — | 91 |
| `instance.inc` — the worker park: `inst_park_hold/wait/lk/unlk/mk/me`, `inst_of_seg`, `inst_park_req/end/all`, `inst_seg_parked`, `inst_svc_parked`, `inst_task_park`, the two setters, the `ALIVE` hook | — | 401 |
| `sched.inc` — `sch_wk_restart` | — | 66 |
| `menu.inc`, `clip.inc`, `files.inc` — `menu_reloc`, `clip_reloc`, `fm_reloc`, `fmv_movable` and their declarations | — | 107 |
| `disk.inc`, `hiber.inc`, `vga12.inc` — `[mem_pinseg]`, the two `gfx_lock` park calls | — | 27 |
| **code** | **962** | **692** |

plus 53 bytes of `.bss` (`mem_cp_busy`, `mem_cp_msk`, `mem_wpin`, `mem_parked`,
`mem_pinseg`, `mem_cp_key`, `inst_parksafe`, `inst_restart`, `inst_parkreq`,
`sch_parked`) and 4 of `.lowbss` (`mem_fptr`). **1,725 bytes.**

That is already net of ~70 bytes credited back, because **`mem_avail` IS
`mem_cp_plan`** (SPEC.md 66.10.3): the number every package sizes itself down
from is the run compaction would leave, so gating the compactor out means
writing a largest-free-run walk to replace it. The one it replaced was
`O(MEM_MAX^2)` and is not in the tree to restore.

Dropping `MC_RLOC` from the claim record as well is a further 40 bytes of
`.lowbss` on `MEM_MAX` = 20, and it crosses no rung, so it is not worth the
churn through every `MC_*` offset.

### 1.1 What that is in heap

`kernsize` for kern_small at this commit: `.text` 39,458, `.bss` 4,871,
`.cold` 27,372, `.lowbss` 6,064, `KERN_SIZE` 79,872, HEAP at 0x13E0.

| rung | now | after | |
|---|---:|---:|---:|
| cold | 27,648 | 26,624 | **−1,024** |
| image (`.text`+`.bss`) | 44,544 | 44,032 | **−512** |
| low | 6,656 | 6,656 | 0 |

**HEAP_SEG falls 1,536 bytes**, and free heap on the 128KB machine goes
**48.5 KB → 50.0 KB**. Quote the 1,725, not the 1,536: which rung a byte lands
in decides where the 512 comes from and never whether the change was free.

## 2. `HEAPCOMPACT=0` is not a preview of this

The knob stubs the bodies of `mem_compact` and `mem_can_move` and leaves every
`mem_cp_*` routine assembled, because `mem_avail` still plans through them. On
kern_small it is worth **158 bytes of `.cold` and nothing else** — no rung, no
`.text`, no `.bss`. It is a behaviour A/B and is used as one in 5 below; it is
not a size measurement and reading it as one understates the feature by 11x.

## 3. The heap kern_small actually has

**A bare kern_small desktop has no claims at all.** `tests/small128.py` asserts
it and it passes: `mem_tab` is empty, 48.5 KB free in one run. There is nothing
for a compactor to do until the user does something.

What ordinary use puts in it, read off the machine:

```
--- A: and B: Disk windows open ---
    arena 13E0..2000 = 48.5 KB
    13E0    2.0K inst0        movable   bottom-up   fm_reloc
    1460   23.0K pg:FE02      purgeable bottom-up   the read-ahead
    1A20    2.0K inst1        movable   bottom-up   fm_reloc
    1AA0    1.0K pg:FATW1     purgeable bottom-up
    1AE0    6.0K pg:WSAVE0    purgeable bottom-up
```

Shed every cache and the largest run is **23.0 KB** — the read-ahead's own
hole, walled above by a 2 KB view cache. Move those two 2 KB claims down and it
is **44.5 KB**. The 21.5 KB difference is the whole of what compaction is worth
here, and it is bought by moving 4 KB.

## 4. The claims on kern_small that are neither purgeable nor a module image

Packages aside. `MEM_K_ASC` (SPEC.md 54.0), `MEM_K_DRV` (51.0) and `MEM_K_BAND`
are compiled out of this build, so the list is short and the movable part of it
is three rows:

| claim | size on kern_small | verdict |
|---|---|---|
| `MEM_K_SAVE` menu save-under (SPEC.md 12.4) | measured **3.0 KB** live while the File menu is down; `MENU_SAVE_KB` 20 is the clamp | **MOVABLE** — `menu_reloc`. Live at exactly the moment a menu COMMAND claims |
| Disk window view cache (owner = the window's instance slot) | `VIEW_KB` = **2 KB**, up to four | **MOVABLE** — `fm_reloc`. **The one that bites**: two of them strand 21.5 KB in 3 |
| `MEM_K_CLIP` clipboard (SPEC.md 55) | sized to contents | **MOVABLE** — `clip_reloc`. Long-lived by design; outlives the app that filled it |
| `MEM_K_COPY` Cut/Copy/Paste buffer | one operation | PINNED for ever — `mem_claim_dma` with the whole block as the page-safe head |
| `MEM_K_CLONE`, `MEM_K_CMPR`, `MEM_K_HIB` | transient | UNDECLARED, so pinned; each lives for one operation |

The three purgeable families (`MEM_P_WSAVE`, `MEM_P_FATW`, `MEM_P_DIRW`) are
out of scope by the question and stay whatever is decided — the shed is a
separate mechanism and this study proposes nothing about it.

**The shape of the answer is why gating hurts.** Every claim that is *big* on
kern_small is either purgeable (sheds) or a region (top-down, and the ceiling
already refills). Everything that is *pinned mid-arena* is transient. What is
left is three small, long-lived, movable claims — too small to shed, big enough
to wall, and landing wherever the session put them. That is the population
compaction exists for, and removing the move leaves no other answer for it.

## 5. The A/B that refuses it

`os8088_5150_cga_128k`, `small360.img` + `apps360.img`, identical gestures
through `tools/os88ui.py`: open A:, open B:, open `B:/APPS/PAINT.O88`. Paint's
region is ~32 KB, which sits between the 23.0 KB the arena has and the 44.5 KB
compaction reaches.

```
kern_small (shipped)          after A: and B: -> run 23.0 KB   PAINT LOADED
kern_small HEAPCOMPACT=0      after A: and B: -> run 23.0 KB   toast: "Out of memory"
```

Both arms read the same 23.0 KB, which is the point: the run a claimant can
have is not the run lying about now, and the two kernels differ only in whether
the allocator can go and make one.

## 6. The read-ahead is the proximate fragmenter, and capping it is not the way out

`HEAPCOMPACT=0 DIRW1=1` — no compactor and no sector cache (SPEC.md 18.95) —
leaves 44.5 KB after both windows are open and loads Paint. So in *this*
scenario the 23 KB read-ahead is what splits the arena.

It does not follow that the read-ahead should be capped instead, for three
reasons:

1. `DIRW1=1` is a claim about REVOLUTIONS and no emulator here models one. The
   Makefile says so at the knob. Trading a memory feature for an I/O feature on
   the slowest machine in the tree wants the 5150, not this box.
2. The cache is **purgeable**: it is not heap the machine loses, it is heap the
   machine lends. What costs is its PLACEMENT, and moving it to the ceiling was
   tried and reverted — `mem_claim_x`'s own header records that a top-down
   cache is one the shed cannot give back.
3. It is not the only splitter. Taking it out only moves the failure one app
   along: with `DIRW1=1` and no compactor, Calc and Note Pad load and Paint
   still refuses at an 11.0 KB run — and the compacting arm of the same
   sequence refuses too, at 13.5 KB, because by then the heap is genuinely
   full. The discriminating case is the one in 5, and it is the common one.

## 7. What is worth taking anyway

Nothing large, and none of it is this study's subject:

* **`inst_svc_parked` (49 bytes) and `inst_task_park`'s body (15)** are the
  park's DRIVER half. `TF_SERVICE` is set only by `OSAPI_DRV_TASK`, so on a
  kernel that can load no driver the scan can never find one. `%ifdef
  OS88_DRIVERS` with a `clc`/`ret` fallback is ~56 bytes of `.text`, gated on
  the drivers and not on the compactor — `mem_rr_tab` already does exactly this
  for its five driver rows.
* The 1,725 bytes stay on the table for a **192KB-class** kernel that does not
  exist. Nothing here argues the feature is cheap; it argues it is earned.

## 8. How to re-take any of it

```
make small                                            # build/smallk
python3 tools/kernsize.py --build build --ico build -DKERN_SMALL
python3 tools/kernsize.py --modules --build build --ico build -DKERN_SMALL
python3 tests/small128.py                             # the bare-desktop audit
```

The A/B trees are `tools/os88build.py`'s, never `build/`:

```
python3 -c "import sys; sys.path.insert(0,'tools'); import os88build; \
            print(os88build.tree('HEAPCOMPACT=0', targets=('small','apps360.img')).dir)"
```

and every script driving one needs `OS88_BUILD=<tree>/smallk`,
`OS88_TREE=<tree>` and `OS88_DEFINES="KERN_SMALL NOCOMPACT"` — the knob's make
variable is not its nasm define, and without the define `os88sym` refuses with
"the map describes a DIFFERENT kernel", which reads like a broken kernel and is
not one.
