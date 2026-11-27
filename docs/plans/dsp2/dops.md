# Driver size pass 2: `dops`, the disk and desktop modules

Branch `dsp2-dops`, cut from `1b01907f1` (the brief). Agent `dops`
(BRIEF.md 2) owns the lines under `.modl`, `.modf`, `.modh`, `.modx`,
`.modk`, `.modw`, `.modj`, `.modn` and `.mods`: DISKOPS.DRV (`diskops.inc`,
`diskmut.inc`, `compress.inc`), FORMAT.DRV (`diskw.inc`'s and `ascw.inc`'s
`.modf`), HIBER.DRV (`hiber.inc`, `driver.inc`'s `.modh`), EXTD.DRV
(`extmod.inc`), DOCK.DRV (`dockmod.inc`), WIN95.DRV (`winmod.inc`),
DESK.DRV (`deskmod.inc`), STIKMENU.DRV (`stikmenu.inc`) and SERIAL.DRV
(`serial.inc`).

**The finding.** DISKOPS.DRV's growth since `e7668bd73` is `diskmut.inc`:
#396 moved all four directory bodies into the module, and `7f08a100b` put
New Folder, Rename and the empty folder back RESIDENT on kern_big, kern_emu
and kern_mega - but the image kept its own copy of the empty-folder removal
(the gate, the find, the emptiness scan and the commit) for the tree to call.
On those kernels the tree now calls the kernel's own (`dskw_rmbody`,
`dskw_rmbody_n83`, through `wm_cbd`); kern_small, which has no resident
copy, keeps the image's. The rest of the module code that grew is three
shapes: far hops to the kernel's three-instruction error tails (a nine-byte
`DMO_TAIL` for a five-byte answer), banks round helpers whose caller holds
nothing (the verb is a `dskw_wrap7` body), and jumps out of a short jump's
reach - which, on a hot path, cost cycles as well as bytes, because the
relaxed form's inverted `jcc` is TAKEN on the fall-through path.

**And one rule-shaping fact about kern_mega** (CROSS-FILE 1): its resident
kernel names two module images' INTERNAL offsets as immediates - HIBER.DRV's
park stub (`megados.inc`, `add ax, mpk_stub`) and SERIAL.DRV's lease block
(`fsx.inc`, `[SRL_O_SEG]` and kin). Every byte saved in front of either moves
a resident byte on kern_mega, so on kern_mega both are now PINNED where they
stood, the bytes given up in front of them standing as zeros. Nothing else in
my modules is named that way (the resident proof below, at every batch).

Commits: `aa1ea16be`, `300526c9d`, `074c682e6` (batch 1), `bf98d0f35`,
`994e39d06`, `4d9460348`, `fc93fc75d` (batch 2), `49b156d3c` (this note),
`7a85e7827` (batch 3), and the note's update.

## 1. BASE AND TIP

Measured in this worktree: `make -j2` (kern_big and kern_small), `make -j2
emu`, `make -j2 mega` at the base and at the tip, image = the header's
`MOD_H_IMG` (image + bss tail, what the claim holds), file = the `'CZ'` file
on the disk. FORMAT, DOCK and DESK are 0 on every kernel.

| module | kernel | image base -> tip | file base -> tip | claim (512 granules) |
|---|---|---:|---:|---|
| **DISKOPS.DRV** | big | 10,849 -> **10,699** (-150) | 9,523 -> **9,411** (-112) | 22 -> **21** |
| | emu | 10,849 -> 10,699 (-150) | 9,523 -> 9,411 (-112) | 22 -> 21 |
| | small | 7,995 -> **7,880** (-115) | 7,118 -> **7,023** (-95) | 16 -> 16 |
| | mega | 12,300 -> **12,105** (-195) | 10,091 -> **10,010** (-81) | 25 -> **24** |
| **SERIAL.DRV** | big | 1,090 -> **1,062** (-28) | 998 -> **962** (-36) | 3 -> 3 |
| | emu | 1,090 -> 1,062 (-28) | 998 -> 962 (-36) | 3 -> 3 |
| | small | 1,090 -> **1,062** (-28) | 998 -> **962** (-36) | 3 -> 3 |
| | mega | 1,181 -> 1,181 (0, pinned: CROSS-FILE 1) | 1,027 -> 992 (-35) | 3 -> 3 |
| **STIKMENU.DRV** | big | 7,935 -> **7,911** (-24) | 3,586 -> **3,561** (-25) | 16 -> 16 |
| | emu | 7,935 -> 7,911 (-24) | 3,585 -> 3,560 (-25) | 16 -> 16 |
| | mega | 8,426 -> **8,390** (-36) | 3,759 -> **3,721** (-38) | 17 -> 17 |
| **EXTD.DRV** | big | 1,930 -> **1,915** (-15) | 1,831 -> **1,816** (-15) | 4 -> 4 |
| | emu | 1,930 -> 1,915 (-15) | 1,831 -> 1,816 (-15) | 4 -> 4 |
| | mega | 1,865 -> **1,850** (-15) | 1,780 -> **1,765** (-15) | 4 -> 4 |
| **HIBER.DRV** | big | 7,729 -> **7,722** (-7) | 6,181 -> **6,171** (-10) | 16 -> 16 |
| | emu | 7,729 -> 7,722 (-7) | 6,179 -> 6,169 (-10) | 16 -> 16 |
| | mega | 11,632 -> 11,632 (0, pinned: CROSS-FILE 1) | 9,345 -> 9,338 (-7) | 23 -> 23 |
| **WIN95.DRV** | big | 1,570 -> **1,568** (-2) | 1,315 -> **1,313** (-2) | 4 -> 4 |
| | emu | 1,570 -> 1,568 (-2) | 1,315 -> 1,313 (-2) | 4 -> 4 |
| | mega | 1,611 -> **1,609** (-2) | 1,333 -> **1,331** (-2) | 4 -> 4 |
| FORMAT.DRV | big/emu/small/mega | 3,179 / 3,179 / 1,280 / 3,470 | 2,944 / 2,944 / 1,226 / 3,043 | unchanged |
| DOCK.DRV | big/emu/mega | 2,232 / 2,232 / 2,303 | 2,029 / 2,028 / 2,064 | unchanged |
| DESK.DRV | big/emu/mega | 4,432 / 4,432 / 4,688 | 4,141 / 4,141 / 4,164 | unchanged |

**Totals, image / file**: kern_big **-226 / -200**, kern_emu -226 / -200,
kern_small **-143 / -131**, kern_mega **-248 / -178**. The claims are a
consequence, not the reason: DISKOPS.DRV's claim is one 512-byte granule
smaller on kern_big, kern_emu and kern_mega while it is loaded (a clone, a
compress, a folder Delete).

**Disks** (`os88diskuse.py --diff` against this worktree's base save):
`os8088-360.img` 27 -> **28** free clusters (+1: STIKMENU.DRV 8 -> 7; the
other five files that moved, -200 bytes, crossed none);
`small360.img` 14 -> 14 (DISKOPS.DRV -95 and SERIAL.DRV -36 bytes, no
cluster crossed). No other image changed.

**Resident proof, every batch.** The four `kernel.bin` files are
byte-identical to the base's: before the first commit by `cmp` of the build
(same build number); after it by `tools/os88rdiff.py kernel 1b01907f1 .` on
each kernel (`-D KERN_SMALL`, `-D KERN_EMU`, `-D KERN_MEGA`), which shadows
the build number, and a scratch script comparing the two assemblies' bytes up
to the first module section - the bytes `os88mod.py` keeps as `kernel.bin`
(105,456 / 62,384 / 105,808 / 150,737): **0 bytes differ on all four**. That
proof is what caught CROSS-FILE 1, twice (one byte for HIBER, ten for
SERIAL), before either was committed. No `MODS_SIZE` (`.modc`) byte is
mine, so the coordinator's ruling was not needed.

## 2. TAKEN

Bytes are image (file), kern_big unless named. Every item keeps every
answer, every refusal and every `int 13h` call; "faster" is §3's count.

### Batch 1

1. **DISKOPS: the tree calls the kernel's rmdir** (`aa1ea16be`; with items
   2-6, -150 big/emu, -116 small, -194 mega). On kern_big/emu/mega
   (`%ifndef DSKW_DIRMOD`) `dmo_rmbody_n83` is `mov bp, dskw_rmbody_n83` and
   `dmo_rmbody` (a redirected volume whose driver refused `FSV_RMTREE` with
   AX = 0) `mov bp, dskw_rmbody`, sharing one `call COLD_SEG:wm_cbd / ret`.
   `dmo_gate`, `dmo_gate83`, `dmo_isempty` and the module's own
   `dmo_rmbody(_n83)` are kern_small's alone now. **Equivalence, read**: the
   module's copy and `diskw.inc`'s `dskw_rmbody_n83` make the same find, the
   same attribute tests (`DSKW_NPROT`, `DSKW_DIR`) to the same `FERR_PROT`,
   the same `dskw_clok` to the same `FERR_IO`, the same scan (00h = empty,
   E5h skipped, '.'/'..' by the same two-byte test, anything else
   `FERR_PROT`; the walk's end empty, its read error `dskw_ioerr`) and the
   same `.delent` commit; the only difference is which registers reach
   `.delent` (SI, CX, ES), and `.delent` reads none (`dskw_ent_store`,
   `dskw_relold` take memory). `dskw_rmbody`'s gate is called NEAR from
   `dskw_rmbody`, so its stack escape discards `dskw_rmbody`'s own return and
   lands in `wm_cbd`'s `retf` - exactly what `dskw_rmbody`'s `ret` would have
   done; the hazard `diskmut.inc`'s header names is calling `dskw_gate`
   itself through `wm_cbd`, which this does not. kern_mega: the FAT32 arms
   are the same macros (`RAW_CLU_LD`/`DMO_RAWCLU`, `CLU_ST`), AX:[dsk_ch]
   reach `dsk_dirw_start_x` with the same value. Faster: one far hop where
   there were four plus one per directory sector.
2. **DISKOPS: the image answers its own refusals** (`dmo_eio`, `dmo_eprot`,
   `dmo_ename`, `dmo_enodisk`, `dmo_eexist`, a shared `stc / ret`). Each
   replaces a `DMO_TAIL dskw_rdata.corrupt|dskw_wbody.prot|
   dskw_dbody_n83.protj` (nine bytes, a far hop to `mov ax, FERR_* / stc /
   ret`), a near `jmp dmo_nbody.badarg`, or a local copy. AX and CF are the
   kernel's tails' exactly (`dskw_wbody.prot` is `mov al, FERR_PROT / cbw`,
   AX = 0008h either way); no other flag is written on either path (`mov`,
   `call far`, `call bp`, `retf` write none), so the flags out are the same
   too. BP differs, and BP is no verb's output (DSKW_DIRRUN pops its own
   over it). kern_big's `dmo_mounted` (one caller left) is written into
   `dmo_rtbody`, its `inc sp / inc sp` escape becoming a plain refusal there.
3. **DISKOPS: nothing banked round the walk's helpers.** `dmo_rt_scan` (six
   pushes), `dmo_rt_byclus` (six), kern_small's `dmo_isempty` (five, and now
   written into its one caller with its redundant `CLU_LD`), `dmo_chdir_dl`
   (DX). **Read**: `dmo_rtbody` holds nothing in a register across any of
   them - every cell the walk carries is `dskw_rt_*` - and it is a
   `dskw_wrap7` body, so all seven registers come back to its caller from the
   ladder. ES is left = SS where it was restored: no callee after them takes
   ES as an input (`dskw_find`, `dsk_byclus_x`, `dsk_copy_in_x`,
   `dskw_copy11` set or bank it; `dskw_ent_store`, `dskw_free_chain`,
   `dskw_flush_x`, `dskw_sync_x`, `disk_mount_x` document memory inputs
   only). One stale comment results, CROSS-FILE 3.
4. **DISKOPS: kern_small's four verbs are `clo_vtab` words** (-22 small):
   `dmo_dispatch` and `clo_disp_x`'s `cmp dl, CLV_DIRV / jae` go on
   kern_small; an `%error` pins CLV_MKDIR = 6. The table path keeps BX and
   leaves DX = the verb's address where `dmo_dispatch` left BX spent and DL
   = an index - no verb reads either (mkbody, rmbody, rtbody take SI; nbody
   SI and DI and writes BX first).
5. **DISKOPS: kern_small's `.rollax`** is `DMO_CALL dskw_refat` falling into
   the `ret`: `dskw_refat` keeps every register and flag, both ways in arrive
   with CF = 1 and AX the answer, and `[dskw_isdir]` is already 0 on both
   (nothing else sets it on kern_small; the clear after the commit runs
   before the `jc`). The bank of AX, the `stc` and the second clear went.
6. **DISKOPS, kern_mega: registers, not `[dsk_ch]`**, for the walk's home
   (`.fat`) and the folder compare (`.empty`, through DX): `[dsk_ch]` is the
   find's and `dsk_dotdot_x`'s to load, and both load it before reading it;
   `cmz_sizes`' FAT32 arm does not bank the AX that `mov ax, cx` overwrites
   (-2 mega).
7. **EXTD: the three sequences fall into their last step** (`300526c9d`,
   -12 all three kernels). `ext_kapply_eq`, `ext_kapply` and `ext_two` ended
   `call body / ret` into this image's own `VSW_EQUIP`/`VID_APPLY`/
   `VSW_UNION` copies, whose only callers they are; each body is laid under
   its sequence. kmod 9's queue item (estimated -3 to -6).
8. **STIKMENU: `stm_take`'s refusals jump to the nearest `ret`**
   (`074c682e6`, -24 big/emu, -36 mega): its one `ret` was out of short
   reach from eight refusals (twelve on kern_mega). The first three take
   `stm_gohome.r` (the byte before), the rest the no-room path's `ret` in
   the middle. `stm_scanvol` reads nothing back, flags included.

### Batch 2

9. **SERIAL: the dispatch reaches its cold verbs short and the read falls
   in** (`bf98d0f35`, -28 big/emu/small; kern_mega 0, CROSS-FILE 1).
   `srl_body`'s Open, lease and Close tests were relaxed jumps; Open and Close
   are three-byte trampolines and the refusals a block in the middle, after
   the read, which now falls through the ring dispatch (`cmp al, 2 / jne
   .other`); the other verbs are tested in the same order of distinct
   values, so every AL gets the answer it got. `srl_open`'s refusals sit
   after its first `ret` (the unlisted UART's), with its own busy and bad
   answers, so the contest's three exits to `.take` and every test reach them
   short. The lease block is EVEN (`align 2`, one pad byte): its three words
   are read on every call and every ISR byte.
10. **DISKOPS: `cmz_probe` asks its length first** (`994e39d06`, 0 bytes):
    the "fewer than three bytes" answer was out of reach, so the test was a
    `jnc` over a near jmp taken at EVERY position the pack makes. It is asked
    before the bank and answered by `xor ax, ax / ret` above the label; every
    byte after it is at the offset it had (`cmz_hash` on: +0). `cmz_pos` is
    the walk's alone (read only inside `cmz_probe`, after its write);
    `mega_dsimg` keeps AX and the flags, so kern_mega's `CSDOF` may follow
    the compare.
11. **DISKOPS: the pack's scratch is EVEN** (same commit, +0 big/emu, +1
    small and mega): `align 2` in front of the module's cells. All 25 of the
    words `cmz_pack`, `cmz_probe`, `cmz_fill` and `cmz_bit` touch per byte are
    at even distances from the block's head (checked in the map, all four
    kernels), which had been even on kern_big and odd on kern_small and
    kern_mega by whatever the code above summed to. A speed item: one byte
    for a bus cycle a word on an 8086, a V30 or kern_mega's 286 (§3).
12. **WIN95: `wn_title` asks chromeless first** (`4d9460348`, -2 all three):
    its answer at `.out` was out of reach. `WM_CHROMELESS` reads
    `[di+W_FLAGS]` alone, so it is tested before the eight pushes and
    answered by a bare `ret` above the label - nothing banked, and the near
    return under thv's `jmp far` is all that is owed; the flags out are the
    test's, as they were through `kret_es`.
13. **EXTD: `ui_drag_size`'s refusal takes the `retf` in the byte above**
    (`fc93fc75d`, -3 all three): `wm_disp_span.out`, a bare `retf`, where
    `ext_e_strads.r` was out of reach.

### Batch 3

14. **HIBER: `hbm_findimg` falls into `hbm_cb`; `hbm_geom`'s first refusal
    reaches short** (`7a85e7827`, -7 big/emu; kern_mega 0, pinned). kmod
    9's tail (-4): `hbm_findimg` is laid above `hbm_cb` among the doors and
    its `call hbm_cb / ret` is a fall-through; `hbm_geom`'s BIOS arm falls
    into `.check` and the driver arm is laid after the exit, so the
    `dskf_dsk_vol_row` refusal is a short `jc` where it was relaxed (-3).
    The same tests in the same order; `.no` is the same `CLC_OR_STC` tail.
    On kern_mega the park stub is pinned at 1F80h (CROSS-FILE 1) - the first
    try of this item, unpinned, moved resident `.mega` by one byte and was
    reverted before it was committed.

## 3. SPEED

Nothing here draws (no primitive call changed anywhere) and **no `int 13h`
call was added or removed**: the tree, the rmdir, the rename and New Folder
reach the same resident routines in the same order, so they read and write
the same sectors (diskw.md's table in ksp21 is still the count, scenario by
scenario). Counts are 8088 clocks, by hand, from the instruction table, with
the fetch floor (`max(clocks, 4 x bytes)`) where it binds: a 2-byte `jcc`
not taken is 8, taken 16; a relaxed `jcc +3 / jmp near` on its fall-through
path is its inverted `jcc` TAKEN, 16. A far hop through `wm_cbd` (`mov bp` +
`call far` + `call bp` + the body's `ret` + `retf`) is about 114, a near
`call`/`ret` pair 43.

| path | base -> tip | how |
|---|---|---|
| **SERIAL read a byte** (AL = 2, the poller's) | **-40** a call | 4 head tests 16 -> 8, `je .read` taken 16 -> `jne .other` not taken 8 |
| **SERIAL write a byte** (AL = 3) | **-48** a call | head -32; dispatch 64 -> 48 (three relaxed tests not taken now, one `jne .other` taken) |
| SERIAL read / write a block (AL = 5 / 4) | -31 / -24 a call | head -32; the block's own dispatch +1 / +8 |
| SERIAL lease block, 16-bit bus | 3 word reads a call, aligned | `align 2` (kern_big, small, emu); kern_mega keeps its odd 048Dh (CROSS-FILE 1) |
| **`cmz_probe`** (per position, i.e. per symbol the pack emits) | **-8** a position (-12 by the table) | the relaxed test's taken `jnc` -> a short `jb` not taken |
| **the pack's scratch, 16-bit bus** | ~25 word accesses a byte packed, all aligned | kern_mega (286) and kern_small were odd: +4 clocks a word on an 8086, an extra bus cycle on a 286 - some 6% of `cmz_pack`'s ~1,600 cycles a byte, predicted, not measured |
| **the tree, a FILE** (`dskw_rmtree`, kern_big) | **-176** an entry | `dmo_rt_scan`'s 12 pushes/pops (-161) and `dmo_rawn83` falling through (-15) |
| **the tree, a FOLDER emptied** | **about -670**, and -71 a directory sector scanned | the module's rmdir copy made 4 far hops + 1 per sector and banked 5 registers; the kernel's makes one hop and near calls (`dmo_chdir_dl` -27, `dmo_rt_byclus` -162) |
| kern_small rmdir / New Folder / Rename | fewer far hops (the error tails), -135 the scan's bank | |
| STIKMENU, a `.O88` examined in STIKAPPS | about -64, and -8 a character of its name | eight relaxed refusals not taken on the path that lists it |
| WIN95 title bar | -8 a bar | its relaxed test |
| EXTD mode switch (`ext_kapply_eq`, `ext_two`) | -86 / -43 | a `call`/`ret` pair less per sequence |
| HIBER image lookup / geometry (hibernate, resume, DOS handoff) | -43 / -8 | `hbm_findimg`'s call/ret pair; `hbm_geom`'s relaxed test |

Against the disk: a file removed is at least two `int 13h` writes (the
directory sector and the FAT), ~400 ms each on the 5150 - the tree's gain is
real and invisible. SERIAL's and the compressor's are the ones a user could
feel on a 16-bit bus; on the XT they are the per-byte counts above. No
MartyPC measurement was taken: no design decision here waited on a number.

## 4. REFUSED

1. **A module-local far-hop door for `DMO_CALL`** (`dmo_kc: call
   COLD_SEG:wm_cbd / ret`, `DMO_CALL` = `mov bp, X / call dmo_kc`): -2 a
   site, -3/-4 a tail - about -27 on kern_big's image and -55 on kern_small's
   - for +43 clocks a hop, and nearly every hop left on kern_big is on the
   tree's per-entry path, which the brief does not let get slower. Refused;
   it is the owner's if he wants the bytes over the clocks.
2. **HIBER.DRV's relaxed ladders** - `hbm_dosrun`'s eight refusals (`.b1`
   .. `.b6`, `.bimg`; about -24), `hbm_sweep`'s three (a loop rotation, -3,
   one of its back-jumps at 126 bytes), `hbm_ask`, `hbm_extat`, `hbm_wake`,
   `hbm_perform`'s four (a table is a byte longer) and the two resume stubs'
   (`kds_stub`, `hbs_stub`, run from the text page with the machine half
   back - not touched in a size pass). With the park stub pinned they are
   free on kern_mega too; NOT REACHED. kern_mega's `hbm_root` FAT32 arm as
   `cmp / cmc` (-3) is kern_mega's alone and would only become pad there.
3. **kern_big's `jae dmo_rtbody`** (5 bytes, relaxed): a table word instead
   is -6 and then needs a test to keep the tree clear of OS88_IMG's busy
   refusal (net -1); including `diskmut.inc` right after `clo_vtab` to make
   it short (-3) moves the cloner and the compressor. Neither taken.
4. **`cmz_gosrc` / `cmz_godst` / `cmz_jrmtmp`'s three loads as one helper**
   (-3 big, -11 mega): a call a hop on the join. Not taken (a join is waited
   on; the bytes do not pay for making it slower).
5. **WIN95 `wn_stick`'s `.done`** (-1, a second far `jmp` copy) and
   **`hbm_perform`'s dispatch as a table** (32 bytes against 31): no gain.
6. **FORMAT.DRV's association writer** (`ascw_flush_x`, `asw_dir`,
   `asw_one`, `asw_header`: 16 relaxed jumps, 48 bytes of relaxation): the
   shared epilogue and `.next` are on the far side of bodies longer than a
   short jump; a loop rotation in `asw_dir` and a mid-routine epilogue copy
   were priced at -1 to -10. NOT REACHED in full; the shape is recorded here.
7. Still refused for their dsp1 / ksp21 reasons: `dockmod.inc:1591` (`push
   cs / call`, a far frame).

## 5. WANTS THE OWNER

None. Every message, limit and refusal is as it was. (REFUSED 1 is the
owner's to reopen.)

## 6. WANTS AN ABI BREAK

None. The module headers, entry tables, `mod_tab` rows, ids, `CLV_*`
numbers and the layout stamp are untouched.

## 7. CROSS-FILE

1. **kern_mega's resident kernel names two module images' internal
   offsets, so those images are frozen in front of them.**
   - `megados.inc`'s `mega_dstubup` (`.mega`): `add ax, mpk_stub` -
     HIBER.DRV's park stub at **1F80h** in its image. Every byte HIBER saves
     before `%include "megapark.inc"` (that is, all of `hiber.inc`'s code)
     moved it. Taken here with the stub **pinned** on kern_mega (`times
     MPK_MEGA_AT - ($ - $$) db 0`, 7 zeros now, an `%error` if the code ever
     passes it). SPEC.md 96.45's own record shows the last time this moved
     (14.62.1: "kern_mega's `.mega` moves by one immediate").
   - `fsx.inc`'s `fsx_rserdn` and its rows (W7): `[SRL_O_SEG]`,
     `[SRL_O_BUF]`, `[SRL_O_MASK]` - SERIAL.DRV's lease block at **048Dh**.
     Pinned the same way (29 zeros).
   So both images are their base size on kern_mega, and its resident kernel
   is byte-identical.

   Either fix is one resident immediate, once, and then the images are free:
   put the stub (and the lease block) at a FIXED place in the image - right
   after the entry table - so its offset no longer depends on the code in
   front of it; or read it from the image at run time. With that the 36
   bytes of pad come back on kern_mega and the two pins go. **Until then the
   two `%error`s are the only gate on the coupling**: without them a module
   change that moved either offset changed kern_mega's resident bytes
   silently (MOD_STAMP keeps the pair consistent at run time, so it was never
   a defect, only a resident byte moving under a module-only change).
2. **The resident directory bodies are near the tree's own shapes.**
   `dskw_rmbody_n83`'s find-and-check prefix is what `dmo_fdir` repeats (the
   tree's top folder): a resident entry at the check's end would let the
   module drop `dmo_fdir` (34 bytes kern_big) for a hop. Resident bytes,
   `diskw.inc`'s owner's call.
3. **`disk.inc`'s `dsk_byclus_x` header** says kern_small's one caller
   banks AX, BX and DI under its own frame: `dmo_rt_byclus` no longer banks
   anything (TAKEN 3), and its caller holds nothing. Comment only, priced 0.
4. No `DRVM_IMG_*` figure is mine (modules are not `drv_tab` drivers), and
   none moved.

## 8. ROWS TO RUN

(named, not run)

- **DISKOPS tree, rmdir, kern_small's verbs** (1-6): `diskmut` (kern_big's
  public bench: Rename, New Folder, empty and recursive RMDIR, host FAT
  read-back), `fcpcopy`, `fcpapi`, `fcproom` (a folder Cut's rmtree),
  `fcpsmall` (kern_small: folder Copy and Cut, its module mkdir and tree),
  `fat32`, `fat32big` (kern_mega: delete, New Folder on FAT32; kern_big's
  refusal).
- **DISKOPS compressor and cloner** (6, 10, 11): `cz`, `czto`, `czjoin`,
  `czdos`, `czseq`, `czseqlose`, `czseqnone`, `lzcomp`, `megacz`,
  `diskclone`, `wimgtrip`, `imgmount`.
- **SERIAL** (9): `serlease`, `walink`, `walinkmega`, `walink4`,
  `megarmbref` (the lease inside kern_mega's bracket - the pinned block),
  `wirefleetlink`.
- **STIKMENU** (8): `stikmenu`, `stik`, `stikboot`, `stikswap`, `stikmiss`,
  `stiknodesk`, `stikcard`.
- **EXTD** (7, 13): `extdmod`, `dispdrag`, `dispfit`, `dispstrad`,
  `dispzoom`, `dispsize`, `dispseam`, `dispcheck`, `dispfsx`, `megarmbext`.
- **WIN95** (12): `thm95`, `dispthm`, `disptitle`.
- **HIBER** (14; `hbm_geom` is the hibernate, the resume probe and the DOS
  handoff's geometry, `hbm_findimg` the image lookup on all three; kern_mega's
  pinned park stub is the DOS park's): `hibernate`, `hibernatedrv`,
  `hibernatem`, `hibsumok`, `hibsumbad`, `hdhiber`, `hmahiber`, `p2hiber`,
  `stikhiber`, `kbdlayouthiber`, `win16hiber`, `kdreturn`, `kdreturnm`,
  `hmadosret`, `megahiber`, `megahibfull`, `megap2hiber`, `megadosp`,
  `megadosroom`, `win16megadgroup`.
- **The module layer** (every image moved): `modcache`, `moddrop`,
  `megamodcache`, `megamod`.
- fast tier (green at every commit): `make -j2`'s 54 rows.

## 9. LOOKED

No boot: no attach, probe or ISR path changed (SERIAL's ISR body is
byte-for-byte the base's; only its data's place moved, and not on
kern_mega).

## 10. DEFECTS FOUND

None in behaviour. The coupling in CROSS-FILE 1 is the one real finding: a
module saving that silently changes kern_mega's resident kernel.
