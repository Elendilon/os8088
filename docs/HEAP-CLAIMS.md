# Every claim in the tree, and whether the compactor can move it

The per-claim inventory behind SPEC.md §66. §66.3 is the mechanism
(`mem_can_move` is the one predicate and every pinning rule is in it), §66.9
is the shape of what stays pinned and why; this file is the register, one row
per claim, so "can this move?" is looked up rather than re-derived.

**A verdict here is a declaration, not an observation.** `MC_RLOC` in the claim
record (§66.2: 0 = pinned, else the holder's relocation proc) is the fact, and
`tools/heapmap.py` / `tests/heapmap.py` read it out of `mem_tab` on a running
machine. §66.5.6.2 is the case for checking: a declaration whose owner fence
refused it, silently, left this table saying MOVABLE for a cache that was
pinned. When a row here matters, boot and read the map.

---

## The verdicts

| | meaning |
|---|---|
| **MOVABLE** | declares a relocation proc and `mem_can_move` accepts it |
| **UNDECLARED** | nothing structural stops it; it has no proc, so it is pinned by default (§66.2) |
| **PINNED (rule)** | refused by `mem_can_move` for a reason a declaration cannot overturn |
| **PINNED (forever)** | its base *is* a CS, or a bus master is looking at it |
| **PURGEABLE** | never moved and never a barrier: the compactor **drops** it under pressure (§66.10) |
| **nothing to declare** | the package makes no heap claim at all (its region is a claim, and a region's base is its CS) |

**Three things can never move, and no API will change that.** A package
**region**, a **driver image** and an **on-demand kernel module** are each
addressed by a CS, so relocating one invalidates every far pointer, every
`MB_SEG`, every claim owner word and every saved CS on every stack (§66.6). A
claim carrying **`MC_DMA`** is the fourth: the 64KB page rule is a property of
the address, and the chip may be mid-transfer.

**Purgeable caches are refused by `mem_can_move` too**, and it costs nothing:
a cache that is in the way is dissolved by `mem_cp_drop` when a claim is
waiting and outranks it (§66.10.1), which is the same room at none of the copy.

---

## Kernel-owned claims

| claim | size / lifetime | verdict | why, and what it would take |
|---|---|---|---|
| `MEM_K_SAVE` menu save-under | `MENU_SAVE_KB` = 20KB, one menu | **MOVABLE** | `menu_reloc`. 20KB mid-arena at exactly the moment a *menu command* claims |
| `MEM_K_ASC` ASSOC.DAT cache | `ASC_KB` = 3KB, one volume at a time, long-lived | **MOVABLE** | `asc_reloc`. Claimed on a **volume switch**, so on a used machine it lands mid-arena — measured holding 40KB out of reach before it was declared (§66.5.6) |
| `MEM_K_CLIP` clipboard | sized to contents, long-lived | **MOVABLE** | `clip_reloc`. Outlives the app that filled it (§55). `clip_put` pins its *source* through `[mem_pinseg]` across its own claim (§66.5.6) |
| Disk window view cache (owner = the window's instance slot) | `VIEW_KB` = 3KB per open window (2KB on kern_small) | **MOVABLE** | `fm_reloc` — `FS_VSEG` **and** the `[fm_vseg]` mirror, the pair that killed the word-poke design (§66.1). Declared from the claim site with the owner in hand (§66.5.6.2) |
| `MEM_K_COPY` copy buffer | one Cut/Copy/Paste | **PINNED (forever)** | claimed through `mem_claim_dma` with the whole buffer as the page-safe head (§22.5.1) |
| `MEM_K_DRV` driver image | per loaded driver | **PINNED (forever)** | its base is the driver's CS |
| `MEM_K_MOD` on-demand module | per loaded module | **PINNED (forever)** | its base is the module's CS. Claimed top-down |
| `MEM_K_CLONE` disk cloner buffer | up to 640KB, one clone | **UNDECLARED** | transient, and the `int 13h` target throughout — cannot be a barrier longer than the clone |
| `MEM_K_CMPR` Compress working block | twice the file plus up to 40KB, one compress | **UNDECLARED** | transient; three segments are paragraph arithmetic off one base |
| `MEM_K_HIB` hibernate extent list | `HB_XKB`, the resume stub's lifetime | **UNDECLARED** | claimed on the way into the stub; the machine it is in is about to be overwritten |
| `MEM_K_BAND` band composer buffer | `BAND_KB`, boot to shutdown | **UNDECLARED** | `BAND=1` builds only. Taken once at boot, so it sits on the floor and is not in anybody's way |
| `MEM_P_WSAVE` window raise cache | one per window | **PURGEABLE** | |
| `MEM_P_FATW` FAT window | ~5KB per volume that did not get the `FAT_SEG` pin (the boot volume takes the pin, §18.8.3) | **PURGEABLE** | §18.8.4. It was `MEM_K_FATW`, a long-lived pinned claim and the first bottom-up claim of the boot, with a relocation proc; both were deleted when it became a cache, and `dsk_fatw_demote` now carries the second naming word (`[dsk_fatseg]`) that proc existed for |
| `MEM_P_DIRW` directory read-ahead | 63KB, one 64KB page | **PURGEABLE** | |

## Package-owned claims

### Declared

| claim | verdict | note |
|---|---|---|
| **Paint** canvas, undo, clipboard, scratch | **MOVABLE** | §66.5.1. `pt_reloc` shifts the per-row segment table (`pt_rowseg`, `PT_CH_MAX` entries) and recomputes `[pt_undelta]`; the BMP save pins the canvas for the write (`pt_pin`/`pt_unpin`) |
| **Paint** GIF/LZW staging buffer | **PINNED (rule)** | `[pt_gbase]` is a paragraph derived off `[pt_gseg]` at four sites, it is the `OSAPI_FILE_READ` target, and it lives for one file |
| **Tracker** module (up to 116KB) | **MOVABLE** | §66.5.2. `trk_reloc` fixes 36 words: `[mp_blobseg]`, 31 `MS_SEG` sample bases, 4 `MP_SEG` channel segments. Declared only after `mp_load` succeeds |
| **Frotz** story (up to 508KB, the largest claim this OS hands out), Z-stack, undo snapshot | **MOVABLE** | §66.5.9. `zf_reloc`. The story costs **three** words — `[zf_sseg]`, the live program counter `[zf_pcseg]` (shifted, never set) and `[zf_sdelta]`, the running total `zi_yield` differences to repair an `ES` pushed before the move. It **cannot** declare `OSAPI_MEM_PARKSAFE` and does not need to (§66.5.9.1) |
| **Frotz** save staging, transcript (`ZI_SCRKB`), picture buffer, `.mg1` probe | **PINNED (rule)** | file-operation targets, or transients freed inside the call that made them |
| **Note Pad** document + undo arena | **MOVABLE** | §66.5.7. `np_reloc`, two words, one proc — `BX` picks between them. A load pins the note for the read (`np_dmov`, §66.5.7.1) |
| **Note Pad** CR/LF staging buffer | **PINNED (rule)** | transient and the `OSAPI_FILE_WRITE` target throughout — pinned by having no declaration, the cheapest correct answer |
| **ArtfulType** document + undo/redo/clip arena | **MOVABLE** | §66.5.7. `at_reloc`, two words; `at_dmov` pins across both file operations |
| **Fractal** run cache | **MOVABLE** | §66.5.7. `fr_reloc`, one word — every cursor into it is an offset |
| **ModPlug** module (up to 116KB) | **MOVABLE** | §66.5.8. `mpp_reloc`, 36 words. §56.1's bill: the replayer is an independent copy of Tracker's at *different strides* (`MPS_SZ` 12, `MPM_CHSZ` 40), so a renamed `trk_reloc` walks the tables wrong and yields plausible garbage |
| every package **region** | **PINNED (forever)** | base is CS |

### Undeclared

Every package below claims heap and declares none of it movable, so each is
pinned by default and is a barrier for as long as it is held. None has been
audited for §66.3's author rules; a row is "nobody has looked", not "it cannot
be done". Sizes are the `equ`s at the claim sites.

| package | claims |
|---|---|
| **Word** | document and CHP arena (grown in lockstep from `WD_KB0`), PAP dictionary 1KB, undo arena, italic glyph table + staging `WD_ITKB` 9KB, `WORD.OVL` image `WD_OVKB` 8KB (a CS, so that one is forever), `WD_LSTGKB` 62KB load staging (transient), a `2*WD_SCHALF` scratch |
| **Sheet** | cells 32KB, text 8KB, staging 32KB, borders 4KB, notes 4KB, chart 19KB — ~99KB for the session, the largest undeclared holder |
| **Chart** | chart 19KB, staging 32KB |
| **Browser** | link table `BR_LINKKB` 6KB, document up to `BR_DOCMAX` 63KB, line table 8KB, fetch buffer `BR_MAXKB` 32KB |
| **FTPD** | staging `FD_STGKB` 8KB |
| **TeXpad** | source `TP_SRC_KB` 8KB; export `TP_EXP_KB` 24KB (transient) |
| **Audio** | `AP_LA_SZ` 32KB look-ahead ring |
| **Tank Attack** | `TK_SHKB` 16KB CGA/Hercules shadow |
| **Frotz** | scrollback `ZW_SBKB` 24KB (8KB fallback) — `zwin.inc`'s claim, outside `zf_reloc` |
| **every C package** (C64, RunCPM, Weave, Loom, CWORD) | `os88_mem_claim` is the whole of the C SDK's heap surface: there is no `os88_mem_movable`, so a C package cannot declare. C64's 64KB RAM, RunCPM's 64KB Z80 space, Weave's bundle/VM/canvas/grid, Loom's 29/50/62KB project buffers, and every `apps/os88parts.inc` scratch part are all pinned. The C overlay (`crt0.asm`, §73.14) is a CS and forever |

Word and Sheet are the two worth an afternoon: session-lived, tens of KB,
claimed after the user has been working — exactly the profile that stranded
Tracker's module in the field (docs/FIELD-NOTES.md 2).

### Nothing to declare

Task Manager, Solitaire, Arkanoid, Missile, Tamegram, Minesweeper, Piano,
Recorder, Hello, Calculator, Cyclone, Telnet: no `OSAPI_MEM_CLAIM` in any of
them. The Task Manager's "~7.3KB of heap while open" (§28) is its *region*,
image plus bss, whose base is its CS. (`tests/heapfrag` claims and declares,
and does not ship.)

## Driver-owned claims

| claim | verdict | note |
|---|---|---|
| **SB staging pool** (`SBL_POOLKB` 20KB, stepping down) | **MOVABLE** | §66.5.5. `sbl_reloc`, one word, because a grant is an *offset* and the staging copy is the v3 boundary; every copy into or out of it goes in `SBL_DCHUNK` chunks under `cli`, re-reading `[sbl_poolseg]` per chunk |
| **SB DMA double-buffer** | **PINNED (forever)** | `MC_DMA`, claimed top-down |
| **HDD** install buffer (`hd_ibufsz` ladder) | **PINNED (rule)** | §66.5.10. An `OSAPI_FILE_READ`/`WRITE` target at all four uses, claimed for one install and freed at its end |
| **HDD** per-partition listing (`HDD_LISTKB` 6KB) | **MOVABLE** | §66.5.10.2. Donated to the kernel by `osapi_vol_add`, so three words name it: `mem_reloc_call` calls `dsk_dseg_reloc` for **every** move first (the kernel's `DV_SEG` and `[dsk_dseg]`), then the owner's `hd_lst_reloc`, one word. Stays claimed LOW (§50.3.2.1): sent high it cost 9KB |
| **HDD** second image (`HDDTOOL.DRV`) | **PINNED (forever)** | base is CS (§52.11.7). Claimed top-down |
| **RAM disk** second image (`RAMPAGE.DRV`) | **PINNED (forever)** | base is CS (§62.9.9) — `[rd_pfar]` is `PKG_DISP:segment`. Claimed top-down |
| **RAM disk** store | **MOVABLE** | §66.5.10. `rd_reloc`, one word — nothing outside `ramdisk.asm` sees the arena, and every handle into it is an offset |
| **ETHER.DRV** socket pool | **UNDECLARED** | one bulk pair plus `SK_NLEAN` lean sockets, sized at attach, claimed top-down (`OSAPI_MEM_CLAIM_HI`) for the driver's life |

---

## Placement is a second axis this table does not have

Every verdict above answers *can the compactor move this block*. Which END of
the heap it was claimed from is a separate question (§50.3.2, and
`OSAPI_MEM_CLAIM_HI` is the top-down door), and PINNED settles the first while
saying nothing about the second.

**The rule is not "pinned belongs high"**, measured rather than assumed. A
pinned claim's cost is decided by **what is above it**: below every movable
claim it costs nothing, because `mem_cp_plan` resumes its fill point above
each barrier and the movables pack straight past; above them it cuts the
arena in two for as long as it is held. The HDD's listing claim is the case
that separated the two while it was still pinned — under the 63KB read-ahead
it was free where it was, and sent high it measured 9KB worse (§50.3.2.1).
`tests/heaphi.py` asserts the compaction number rather than a predicate over
the map, because no predicate over the map tells the two apart. And where a
first-fit claim lands is a property of the session, not of the code: the same
6KB first-fits *above* the view cache on a desktop that has been used
(§66.5.6.2), which is why the listing was made movable after all.

## What limits compaction today

Not the mechanism. Two things, in the order they cost:

**1. A worker that draws and NEVER SLEEPS must declare `OSAPI_MEM_PARKSAFE`**
or its claims are unreachable whenever the triggering claim comes from a
callback holding the gfx lock (§66.5.3/§66.5.4). A worker that sleeps between
passes reaches `OSAPI_TASK_ALIVE` inside `INST_PARKW` (4 ticks) on its own, so
Note Pad, Fractal, ArtfulType and ModPlug move with the gfx-lock park removed
and Tracker does not (§66.5.7.2); all five declare it as a widening. Frotz is
the one app that **must not** (§66.5.9.1): `zx_lock` pushes the program
counter's segment across `OSAPI_GFX_LOCK` by design, and its claims move at
the ordinary `ALIVE` park regardless.

**2. A driver's claims move only while every `TF_SERVICE` task is parked**,
all-or-nothing, because `TF_SERVICE` is the only handle the kernel has on "a
task running inside a driver" and it does not say *which* one (§66.5.5). One
Sound Blaster stream mid-refill pins the RAM disk's store and the HDD listing
too, neither of which owns a worker. A finer handle is a task-table change,
not a claim-side one.

And behind both: **every undeclared row above.** A pinned block is a barrier
whatever its size — the measured case was a 3KB cache holding 40KB out of
reach, and unpinning it moved a 114KB module and the sound driver's pool on
the very next run with nothing else changed (§66.5.6).
