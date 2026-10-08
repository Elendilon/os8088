# Kernel size pass 10 - agent "disk"

Files: `kernel/disk.inc`, `kernel/diskw.inc`, `kernel/dskwin.inc`,
`kernel/drvvol.inc`, `kernel/lz.inc`, `kernel/mod.inc`. Branch `ksp10-disk`,
cut at `833f13e4`. Figures are `kernsize`'s section line, bytes.

## TAKEN

### Batch 1 - dead code and small bytes (kern_big .cold -129, kern_small .cold -129)

| item | bytes | note |
|---|---:|---|
| `dskw_remount_x` deleted | -22 | no caller anywhere: `dsk_relist`, its only caller, was deleted in an earlier round. SPEC.md's table row now says so |
| `dsk_find_name_x` deleted | -38 | no caller anywhere (kern_dos's resume stopped using it, SPEC.md 96.49.7; `drv_find` moved to `dskw_stat`) |
| `dskw_dirty` takes the window byte offset | -6 | the `shr ax, cl` / `add ax, [dsk_fatw0]` pair was spelled at both of `dskw_setfat`'s call sites |
| `dskw_flush_x` | -12 | `disk_write_x` preserves every register, so the two `push ax`/`pop ax` pairs and the second `add ax, [dsk_fatlba]` go; the x512 is `mov bh, bl / mov bl, 0 / shl bh, 1` so CX needs no bank across a `mov cl, 9` |
| `dsk_fat_window` | -11 | the same fact on the read side: FAT2's retry re-loaded CX, BX and the FAT1 LBA it already had; the window base rides DX (banked by `kretc_dx`) |
| `dsk_bpb_flopzap` + `dsk_bpb_bank_zap` one loop | -15 | a row is 0, 1 or 2 and nothing else, so both are "zero every row >= AL" (AL = 2 / 1) |
| `dskw_name83` stem and extension one loop | -9 | DL = the part's width, DI moved on by 8 at the dot; a second dot is refused at `.dot` where it used to be refused by `dskw_char_x` - same answer for every input |
| `dsk_vol_fixed_x` | -3 | `dec ax` turns AL 1 -> 0 with AH (VT_BIOS) untouched |
| `dsk_swapent` | -3 | `xchg al, [es:di]` for a load and a store |
| `dskw_mark_free` asks "first free slot?" itself | -3 | both callers asked it before calling; it answers ZF for `.endmark` |
| `dskw_ent_store` | -2 | `jnc .out` falls into `.ioerr` |
| `disk_mount` listing loop | -2 | `push ax`/`pop ax` around `dsk_put_dir` banked a dead AX |
| `dsk_find_x` `.take` | -2 | the compressed-mark compare moved above the four `mov`s, so its flags ride them and AX needs no bank |

None is hot by the brief's definition. `dskw_flush_x` and `dsk_fat_window`
are per FAT-window load/flush (each a disk transfer) and lose instructions.

## REFUSED

(appended as decided)

## CROSS-FILE

(appended as found)
