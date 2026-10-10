# Kernel size pass 11 - agent "diskwrite"

Concept: two merges on the disk path - `bc6b0d87` ftp-speed (SPEC.md 18.4.9.3
`WSEQF_KEEP`/`WSEQF_CKPT`, 18.4.10 the FAT16 free-cluster search) and
`42e0db93` disk-cpu (SPEC.md 18.91.6, `dsk_xfer` asks once a run whether a
bar is live) - plus pass 10's leftover relaxed jumps in `disk.inc` /
`diskw.inc`. Branch `ksp11-diskwrite`, cut from `elendilon` at `2a05e31f`.
Figures are `tools/kernsize.py --json`'s sections, bytes, ASSEMBLED.

## Base and tip

| | base `2a05e31f` | tip | delta |
|---|---:|---:|---:|
| kern_big `.text` / `.bss` / `.cold` | 43,428 / 5,190 / 37,943 | (see below) | |
| kern_big resident | 92,495 | | |
| kern_small `.text` / `.bss` / `.cold` | 32,022 / 3,073 / 23,479 | | |
| kern_small resident | 61,442 | | |

## Why ftp-speed cost kern_big twice what it cost kern_small, and why it touched ui.inc and vga12.inc

The merge is two features of different reach. **18.4.10** (the FAT16 search,
`dskw_alloc16`, +114 `.cold`) is in `dskw_alloc`, which both kernels have:
that is kern_small's whole +114. **18.4.9.3** (`WSEQF_KEEP`/`WSEQF_CKPT`,
+108: `.text` +34, `.bss` +2, `.cold` +72) is WRITE_SEQ, which is
`DSK_STREAM` - kern_big's and kern_dos's only (kern_small's cell answers
FERR_NAME). It touches `ui.inc` and `vga12.inc` because a HELD stream's commit
points are where the user can reach the drive: `gfx_unlock` (every UI-task
unlock commits a pending hold; a KEPT hold inside a wake is the one exception,
so the unlock has to know "kept" and "inside a wake"), `ui_task`'s wake arm
(which marks "inside a wake", `[dws_inwk]`) and `ui_task` step 0 (a posted
restart or hibernate must commit a kept hold first). Those are `.text`, so
the `.text` +34 is the unlock's compares, the wake arm's stores and step 0's
far call.

## TAKEN

### 1. `dskw_alloc`: the FAT16 scan shares the loop's wrap (kern_big .cold -42, kern_small .cold -42)

`dskw_alloc16` was a routine of its own with a second copy of the rover wrap,
its own `push/pop` of BX, a window-end computed from `[dsk_fatw0] +
[dsk_fatwn]`, and BOTH bounds (the last cluster and the candidates left). It
is now `dskw_alloc`'s `.scan`, entered from the loop's `.check` after the
shared wrap; the window's entries are `[dsk_fatwn]*256 - BX/2` straight off
`dsk_fat_ofs_x`'s offset; and the scan is bounded by the window and the last
cluster only, the candidates being CHARGED with what each window asked
(`sub cx, bx / ja .try`). Past the last candidate lie only clusters the same
search has already seen used, so an overrun finds nothing a bounded scan
would not - checked in a Python model of both against the per-cluster loop
over 20,000 random FATs (sizes 3..65,524 clusters, densities 0 to full,
rovers out of range both ways, the padding tail zero): identical answers. A
window that will not load asks that ONE cluster the per-cluster way (which
retries the load) where the old code handed the whole remainder back; the
answer is the same, a failed window being asked again either way.

Cycles: the FAT16 per-window cost is the old one less a `call`/`ret` and
two pushes; a FAT12 candidate (every floppy) now pays the `cmp byte
[dsk_fattype], 0 / jne` it did not (~24 cycles against a `dsk_next_clus_x`
of several hundred, and only on the first allocation after a mount, which
walks the used run). Once per allocation, not hot by the brief's list.

### 2. `WSEQF_KEEP` / `WSEQF_CKPT` (kern_big .text -9, .cold -22; kern_small 0)

| item | bytes | note |
|---|---:|---|
| the checkpoint arm shares the door's hot test | -16 | `.close` was its own copy of `cmp di, [dsk_mgen] / dws_ours.vol`; now a CKPT close jumps into `.hot`, where `jcxz .ckpt` tells a checkpoint from a write once the token is known hot. Same answers on every path |
| the keep verdict | -4 | `mov al, [dws_flg] / and al, WSQF_KEEP` gives AL = 0 for "not asked" for free; `dsk_vol_fixed_x`'s CF=1 arm cannot happen on a volume just written, and were it ever taken AL = 4 is not 1, so the unlock commits |
| `dsk_vol_del` | -7 | `[dws_vol]` alone is asked: `dws_commit` tests `[dws_hold]` itself (a stale `[dws_vol]` costs a near call that returns) |
| `gfx_unlock`'s banked test moved to the bank | -7 text, +5 cold | `dws_hswap` clears `[dws_keep]` whichever way it swaps, so the unlock asks one word. A hold that hopped off its volume and BACK within one wake now commits at the next unlock where it used to stay - safe direction, rare case; SPEC.md 18.4.9.3 says so |
| the wake arm's stores | -2 text | `inc`/`dec byte [dws_inwk]` for `mov 1`/`mov 0`: `.bss` is zero at boot (SPEC.md 2.5) and a nested wake reads 2, which commits |

### 3. Relaxed jumps (pass 10's leftover)

See batch 3 below.

## REFUSED

| candidate | bytes | why refused |
|---|---:|---|
| drop `WSEQF_CKPT`: every close of a HOT token hands back a hot token | ~-6 | a semantic change for seven other WRITE_SEQ callers (filecp, clone, compress x3, ramdisk, the HDD installer, kern_dos) that would each have to be audited for reusing a closed token on a new file |
| make `WSEQF_KEEP` implied by `WSEQF_HELD` | ~-6 | every HELD writer that runs inside a wake on a fixed disk would keep its hold to the next non-wake unlock; `wsequnclosed`'s premise is that the unlock commits |
| fold `[dws_inwk]` into `[dws_keep]` (one byte, two bits) | +3 | the door must then preserve the wake bit (`and`/`or`, +6) to save one byte at the unlock |
| commit a kept hold in `ui_cmd_reboot` and `hbf_perform` instead of `ui_task` step 0 | 0 | 5 + 4 bytes against the 9 it replaces |
| `dsk_xfer`'s per-run bar test (disk-cpu, +15) | 0 | already minimal: `[spl_fseg]`'s dead value is `COLD_SEG` (imm16, 6 bytes, SPLCALL's own test) and `[fpg_total]` is a word; reordering the two moves no cycle in the common case (neither bar live: ~64 cycles a run against two far-ish calls a SECTOR) |

## Defects found

## Cross-file

## Rows run
