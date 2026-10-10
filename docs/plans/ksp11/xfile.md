# ksp11 agent "xfile" - the cross-file follow-up on the merged tree

Kernel size pass 11. The role pass 10's xfile agent had: collect what the
per-concept agents left on their cross-file lists, on the MERGED tree. Branch
`ksp11-xfile`, cut from `kernel-size-p11` at `7d426141` (base `2a05e31f` plus
the diskwrite, caption, voltake, picomem and drivers branches; multisel was
still running and owns `kernel/files.inc` and `kernel/filecp.inc`, which this
branch does not touch). Figures are `tools/kernsize.py --json` sections,
ASSEMBLED bytes, against THIS branch's start (not `2a05e31f`, and not
kernsize's blessed-baseline "+N").

## START (`7d426141`, measured)

| | text | bss | cold | lowbss | vgabuf | resident | ovl | ovlw |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kern_big | 43,374 | 5,154 | 37,857 | 5,598 | 336 | **92,319** | 2,471 | 5,075 |
| kern_small | 32,008 | 3,069 | 22,987 | 2,868 | 0 | **60,932** | 2,076 | 1,480 |

`kern_dos` (`build/kerndos.bin`): 33,114 bytes.

## TAKEN

### batch 1 - kern_small: the redirector and driver-volume arms the first gate left (small -403; big byte-identical; kern_dos -301)

The list's item 1 asked for `osapi_desk_item_x`'s driver arm on kern_small.
**It was already gone**: `desk.inc` has carried `%ifndef KERN_SMALL` round the
whole service item since it was written (kern_small's body is `stc / retf`,
and `desk_live`, `desk_zone_label` and the icon draw gate their `.svc` arms
the same way). So nothing to take there - and the question behind it, *what
else on kern_small became dead with voltake's `b2c40bee`*, had a much larger
answer one layer down.

SPEC.md 62.9.2.3 already says `kern_small` "carries none of" the redirector,
because `[dsk_vkind]` can only ever be `DVK_BIOS` on a kernel that can stamp
no other kind. The first round of that gate (a previous squash) took the
mount and the six write verbs and left **eleven arms assembled**:

| site | kern_small bytes |
|---|---|
| `dsk_xfer`: the `DVK_DRV`/`DVK_FILE` dispatch and the whole `.drv` arm (`OS88_DRIVERS`: only a driver stamps either kind); the read cache's `DVK_DRV` test | part of disk.inc's -153 |
| `dsk_vol_fixed_x`'s `cmp ah, DVK_BIOS / jne` | " |
| `dsk_up_open`'s `.fsup` arm, and `[dsk_fsup]` (.bss) | " , bss -2 |
| `dsk_free_clus_x`'s `FSV_DFREE` arm (a `jmp short .fat` over the relays in its place) | " |
| the directory enumerator's `.fsenum` | " |
| `dskw_rtbody`, `dskw_rbody` (+ `.fsread`), `dskw_stat_x`, `dskw_read_at_x` (`jmp short .fatat`), `dwf_dskw_read_seq`, `dskw_wabody`; and `dskw_fsop`/`dskw_fsstat`, whose callers are all gated now | diskw.inc -169 |
| `ld_take`'s handle test | loader.inc -7 |
| FDLG.DRV's two (`.media`, the size probe); CLONE.DRV's `cmz_sizes` | module images: fdlg.drv 1,246 -> 1,232, clone.drv 7,196 -> 7,184 (os88mod's file sizes) |

Each `jmp short` that replaces a removed arm is CHEAPER than what it replaces:
15 cycles against the `cmp byte [mem], imm8` (~20) plus a taken `jne` (16).
No path got slower.

And the zeros a reader read to learn "no driver" went with their readers:

| item | bytes |
|---|---|
| `snd_release_inst`'s `drv_svc_call` of `DSV_RELINST` (the stub refuses) - `%ifdef OS88_DRIVERS` | text -13 |
| `cp_snd_rowok` / `cp_snd_row` (CTRL.DRV): on kern_small `cmp al, 1 / cmc / ret` and `xor al, al / ret`, the answers the arms computed from zeros | ctrl.drv 4,490 -> 4,406 |
| driver.inc's stub data: `drv_svc` (36), `drv_owner` (14), `drv_memk` (8, no reader at all on kern_small), `drv_blkcls` (1) | text -59 (-55 in kernsize's attribution, the other 4 of it landing as an alignment pad) |
| the `drv_cls_fp_x`/`drv_cls_svc_x` stub - no caller left | cold -4 |

kern_small: text 32,008 -> 31,940 (-68), bss 3,069 -> 3,067 (-2), cold
22,987 -> 22,654 (-333): **resident 60,932 -> 60,529, -403**. kern_big:
the assembled image is byte-identical (listing build `cmp`'d). `kern_dos`
defines neither symbol and §96.44.9 fences every non-BIOS row out of it, so
the same arms leave it: 33,114 -> 32,813, **-301**.

Every caller proof is the chain SPEC.md 62.9.2.3 gives: a row is stamped
`DVK_DRV`/`DVK_FILE` only by `dsk_vol_add`, which is `OS88_DRIVERS`'s
(voltake batch 2), and `[dsk_vkind]` is copied from a row at the mount
(`disk.inc` 3317/3335). SPEC.md 62.9.2.3 carries a paragraph saying so.

`tools/stkbalance.py` reads both arms of a `%if`, so the gates are laid out
for it: no `pop` is duplicated across `%else`, and the redirected arms' relays
stay inside their routines (two `equ`-aliased relays outside an entry were
tried first; the walker reads an `equ` as an address taken and walked the
relay from depth 0).
