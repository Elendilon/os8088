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

### Batch 2 - one cluster body for read and write (kern_big .cold -45, kern_small .cold -46)

`dskw_wdata` and `dskw_rdata` were the same 29 instructions from the take to
the last run, bar `dskw_wone`/`dskw_rone` (which `[dskw_fop]` already names:
`dskw_one` asks it, once per STAGED sector) and the next-cluster step. That
step is a continuation in BP now (`jmp bp`), and the shared body is
`dskw_xclus`. **The read path's per-cluster cost went DOWN 18 cycles** (`jmp
bp` 11 against `jmp .clus` 15 + `mov ax, [dskw_cur]` 14, the next-cluster code
falling into the body); a write pays +11 (`jmp bp` + `jmp dskw_xclus` against
`jmp .clus`) beside `dskw_alloc`'s FAT scan. `dskw_wdata.stg` /
`dskw_rdata.stg` are kept as `equ`s of `dskw_xclus.stg`, which is what
`tests/dskwstage.py` breakpoints; that row is green.

### Batch 3 - prologue/epilogue sharing, a widget helper, the bounce (kern_big .cold -60, kern_small .cold -46)

| item | bytes | note |
|---|---:|---|
| `kentc_di` / `kretc_di` in 11 routines | -29 | `dsk_synth_x`, `ico_key_doc`, `dsk_put_dir`, `ico_glyph_put`, `dsk_fat_window`, `dsk_fatw_want`, `dsk_fatw_claim`, `dsk_swapent`, `dskw_name83`, `dskw_dotents`, `dskw_free_chain`: each pushed a subset of AX..DI in ladder order and none returns SI/DI. NOT taken where SI is an output (`dsk_rah_fill` returns the slot in SI, `dsk_ico_stage`, `dsk_get_dir_x`) or a per-cluster path (`dskw_setfat`: ~+90 cycles a call, twice a written cluster) |
| `dskw_fpgb` | -13 | `mov cx, [dskw_len] / mov dx, [dskw_lenhi] / call ct_fpg_begin` at three sites |
| the DMA bounce (HANDOFF-KERNEL-SIZE-P10 3.1, SPEC.md 18.91.4) | -11 | `dsk_bnc_bx`/`dsk_bnc_es` reordered offset-then-segment (asserted), so `.bcp` is one `lds` and `.unbounce` one `les`; `.fail` clears the flag with `xchg` (AX is the frame's). Behaviour identical; the bounce path only |
| shared pop tails | -7 | `dsk_dirw_get_x` and `dskw_flush_x` end on `dsk_next_clus_x.out` (that routine, the per-cluster walk, keeps its own tail and pays nothing); `drv_find` ends on `dskw_isempty.out` |

### Batch 4 - dead test, one name formatter loop, flag-dead word stores (kern_big .cold -61, kern_small .cold -60)

| item | bytes | note |
|---|---:|---|
| `dsk_synth_name` one field routine | -35 | the KANJI test (05h -> E5h at byte 0) ran immediately before `dsk_sanit`, which folds BOTH to `_`: dead (-10). The stem and extension loops are one `.part`, BX = the field, CX = its width, a dot only before a non-blank extension |
| `mov word [m], 0xFFFF / 0` -> `or [m], -1` / `and [m], 0` | -15 | fifteen sites where the next instruction writes the flags or nothing reads them; NOT taken where a comment or a caller relies on `mov` leaving CF alone (`dsk_lbahi`'s spend, `dskw_refat`/`dskw_fatclean`, `dsk_fatw_claim.none`, `ico_demote`, `dskw_sync_x`) |
| `cbw` for `xor ah, ah` | -4 | after a load of `[dsk_spc]` (<= 64, validated) or `[dsk_nfats]` (1 or 2); `dskw_clbytes` drops it outright, a shift by 9 taking AH out the top (flags identical, CF being bit 7). `dskw_take1` and `dsk_read_chain_x`'s per-cluster step get a cycle faster |
| `dsk_vol_add` | -5 | the no-label arm wrote its own terminator and jumped over the shared one |

Verified on MartyPC by a scratch harness (tests/dskwstage.py's Caller):
`dsk_synth_name` on twelve crafted raw entries and `dskw_name83` on
seventeen strings, each against a Python model of the ORIGINAL routine - all
equal. And the DMA bounce: WRITE_AT's inside arm and READ_AT (cache stood
aside) through a buffer 0xF0 short of a 64KB page, `.bounce`/`.unbounce`
each firing once, the bytes right in the guest and on the flushed floppy.

### Batch 5 - banks nobody needed, two masks for two divides (kern_big .cold -46, kern_small .cold -46)

| item | bytes | note |
|---|---:|---|
| `dsk_ent_ofs` | -12 | both callers bank AX/CX/DX already and loaded CX = `DSK_DE_STRIDE` right after it: it clobbers them now and hands CX back as the stride. `dsk_get_dir_x` (the Disk window's per-entry read) gets faster |
| `dskw_rawn83` / `dskw_rtn83` | -13 | entry points falling into `dskw_copy11` for `dskw_rmtree`'s four `mov si / mov di, dskw_n83 / call` triples (inside `%ifndef KD_BUILD`) |
| `dskw_size32` | -7 | its three callers load or recompute AX/CX/DX before reading them |
| `dskw_read_at_x` cluster checks | -6 | `[dwr_clb]` is a power of two, so two `div`s for remainders became two `test`s with `clb - 1` (~300 cycles a call faster) |
| `dskw_norm` | -4 | five callers, none holding AX or CX across it; no FSV_* verb a redirected body calls next takes either (SPEC.md 62.9.1) |
| `dskw_last_p` | -2 | neither caller keeps AX; twice a cluster, 25 cycles faster each |
| `dskw_cmp` | -2 | `dskw_find`'s entry loop holds nothing in DI; once an entry faster |

## REFUSED

(appended as decided)

## CROSS-FILE

(appended as found)
