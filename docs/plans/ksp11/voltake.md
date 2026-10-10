# ksp11 / voltake - notes (agent "voltake")

Concept: the KERNEL side of merge `e002a0e9` ("video-xms"): `OSAPI_VOL_TAKE`
(SPEC.md 52.1.1), the `DRVC_EMS` class (SPEC.md 107), `xm_release_rec`'s
`EMSV_GONE` call, and `ui_timer_pass`'s re-test under the lock (13.9.2).
Files: kernel/disk.inc (the volume plumbing - NOT picomem's "B: from the
card" hunk nor diskwrite's dsk_xfer/FAT16/WSEQF hunks), driver.inc,
kernel.asm, ui.inc, xmem.inc, apps/os88api.inc, drivers/os88drv.inc.

Branch `ksp11-voltake`, cut from `elendilon` at `2a05e31f`. Bytes are
`tools/kernsize.py` section figures, assembled, against the base's ABSOLUTE
sections (not kernsize's blessed-baseline "+N").

## Base `2a05e31f`

| | text | bss | cold | lowbss | vgabuf | resident |
|---|---:|---:|---:|---:|---:|---:|
| kern_big | 43,428 | 5,190 | 37,943 | 5,598 | 336 | 92,495 |
| kern_small | 32,022 | 3,073 | 23,479 | 2,868 | 0 | 61,442 |

## TAKEN

### batch 1 - the concept's own hunks (big -30: text -18, cold -12; small -18: text -6, cold -12)

* **`OSAPI_VOL_TAKE` (cell 0x0467) is gone: a take is `OSAPI_VOL_ADD` with
  DX != 0.** DX was "RESERVED, pass 0" in main's driver SDK since SPEC.md
  22.6 retired the listing claim it carried, and every caller in the tree
  (HDD, NET, RAMDISK) passes 0, so a non-zero DX is free to mean something.
  DL = the volume index OSAPI_VOL_AT answered, AL = the driver's handle. The
  slot was unpublished (not on main `95f7e971`). What goes: the 6-byte rare X
  cell (`.text`, both kernels), the second `osapi_vol_fence` call and its
  retf, and the far call back into `osapi_vol_at_x` the old body made to
  find a row the driver had already found. The take body is behind the fence
  `osapi_vol_add_x` already runs. **text -6, cold -6 on both kernels.**
* **Kind and unit in ONE word store** (DV_KIND 0, DV_UNIT 1 - asserted). The
  take and `dsk_vol_del`'s give-back both bracketed four byte stores with
  `pushf/cli ... popf` so a transfer could never see a half-changed row; one
  `mov [bx], ax` is a single instruction and so needs no bracket, and the
  class and DV_BUNIT bytes are only read on a row of the other kind. The
  give-back is 26 -> 20 bytes, the take smaller by the bracket. Part of the
  cold -12 above (take -6 with the fold, give-back -6).
* **`xm_release_rec` converts the record ONCE** (kern_big .text -5): it
  called `inst_idx` for the EMS door and again for the XMEM dispatch, with
  two separate push/pop banks. One bank of five, AL kept across the EMS call
  on the stack (the driver eats AX and BX). `xm_dsp` sets its own ES, so
  arriving with ES = KERNEL_SEG is harmless. Teardown, not hot.
* **`ui_timer_pass` reads W_ONTIMER only under the lock** (kern_big .text
  -7): 13.9.2's fix re-reads the handler word after `gfx_lock`, which made the
  pre-lock read redundant - its only job was to skip a due timer with no
  handler, a legal no-op that now costs one lock round trip instead. The
  walk's cheap test (W_FLAGS, W_TIMER) is untouched. SPEC.md 13.9.2 says so.
* HDD.DRV (`drivers/hdd/mount.inc`, the caller - **drivers agent's file, a
  minimal edit**): `hd_mount_one`'s `.take` asks `hd_kvol` again for the
  index and calls OSAPI_VOL_ADD with DL = it; it no longer reads DI (which
  was hd_mount's device row, an undocumented register contract across two
  routines). Code -4 bytes (hd_mount_one's span 0x742 -> 0x73E in the
  listing); the image stays 3,764 because the code is followed by an `align
  512` window.

At batch 1: kern_big text 43,410, bss 5,190, cold 37,931 -> resident
92,465 (-30); kern_small text 32,016, cold 23,467 -> 61,424 (-18).

### batch 2 - kern_small: the driver-volume plumbing is stubs (small -422: cold -418, bss -4; big byte-identical)

Not the concept's own hunks but the code around them, in the same two
files (secondary, per the brief).
* On kern_small `osapi_vol_fence` walks `drv_cls_fp_x`, whose whole body
  there is `xor di,di / stc / ret`: no class is ever published, so the fence
  refuses every caller for the life of the machine, and everything behind it
  is code the IP cannot reach. Gated `%ifdef OS88_DRIVERS`: `osapi_vol_fence`,
  `osapi_vol_add_x` (with the take), `osapi_vol_del_x`, `osapi_vol_mount_x`,
  `dsk_vol_add`, `dsk_vol_del`, `dsk_vol_drop_drv_x`, `dsk_vcls`; and
  `%ifdef OS88_REDIR` `osapi_fs_ent_x`, `dsk_fslist`, `dsk_fsn` (the FSV_LIST
  arm that raises `[dsk_fslist]` is OS88_REDIR already).
* The cells keep their offsets (SPEC.md 20.4) and point at driver.inc's
  existing kern_small stubs, which give the same answers: the three fenced
  slots on `osapi_drv_cfg_x`'s `stc / retf` (AL untouched, as the fence's
  refusal left it), `osapi_fs_ent_x` on `osapi_drv_classk_x`'s `xor ax,ax /
  stc / retf` (its own `.no`), `osapi_vol_fence` on `drv_fs_has`'s `stc /
  ret` in `.cold` - the section `osapi_desk_item_x`, its other caller, is in.
  No new bytes for any stub: they are labels on bodies already there.
* `osapi_vol_at_x`'s DV_BUNIT arm (a TAKEN row) is `%ifdef OS88_DRIVERS`:
  no driver, no take, every kern_small row is BIOS or free (-7 of the 418).
* Verified kern_big is byte-identical (two archive copies of the tree, HEAD
  and HEAD + this batch, built side by side and `cmp`'d).
* SPEC.md 51.0.2 says so.

At batch 2: kern_small text 32,016, bss 3,069, cold 23,049 -> resident
61,002 (-440 from base). kern_big unchanged at 92,465.

## REFUSED

## DEFECTS

* **`mem_rr_tab` relocated five class segments of seven** (`93287205`,
  its own commit, 0 bytes). `MEM_RR_ROW drv_fseg, 5, 4` walked drv_fseg ..
  drv_fseg5; DRVC_POINT (6, on main since the CH375 mouse) and DRVC_EMS (7,
  this merge) were appended without it, so a driver image that MOVES
  (SPEC.md 66.6.3) left drv_fseg6/7 naming the old segment. EMS.DRV hooks no
  vector, so `mem_can_move` lets it move: after that compaction every
  OSAPI_DRV_CALL to it - and xm_release_rec's EMSV_GONE at every instance
  teardown - far-calls PKG_DISP in freed memory; the USB mouse's packets are
  refused by osapi_mou_feed's segment fence. The row counts DRVC_MAX now.
  tests/drvmove.py's stale-word check names drv_fseg6/7 and all seven rows.
  Found by reading; NOT reproduced (no row moves EMS.DRV or USBMOUSE.DRV).

## CROSS-FILE

## ROWS RUN
