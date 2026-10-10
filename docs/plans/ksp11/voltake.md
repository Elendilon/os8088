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

## REFUSED

## DEFECTS

## CROSS-FILE

## ROWS RUN
