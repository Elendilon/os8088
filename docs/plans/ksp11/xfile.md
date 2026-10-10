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

### batch 2 - relaxed jumps, and `lea sp` (big -21, small -7; DOCK.DRV -12)

The sweep (item 3) is a `nasm -l` listing of both kernels searched for the
relaxed pair's signature, `7x 03 E9 lo hi` on a line whose source is a `jcc`
(the diskwrite agent's method), each hit mapped back to its file. 83 hits on
kern_big and 31 on kern_small at this branch's start, `files.inc` and
`filecp.inc` (multisel's) excluded from action. Taken:

| item | kern_big | kern_small | cycles |
|---|---:|---:|---|
| `drv_load_row`'s one-per-class check moved FIRST, ahead of the disk (it reads only `DRVR_CLASS`, the row's own expectation, and `[drv_owner]`): the five refusals under it (`jne .already`, `je .bad`, `jc .nodisk`, `jc .noent`, `jb .bad`) reach their answers short; its own exit becomes a near `jmp .fail` (+1) | cold -14 | (not built) | each refusal not taken is 12 cycles cheaper (a short `jcc` falls through in 4 where the relaxed one TOOK its `j!cc +3`, 16). A second driver in one class is now refused before a byte is read; the answer is the same DRVE_TWICE, and only a row that is BOTH a duplicate and, say, missing now reports TWICE where it reported NOENT. SPEC.md 51.2.1 says so |
| `menu_draw_clock`'s "no cells" guard: `or bx, bx / jz .out` (2 + a relaxed 5) became `jcxz .jout` after `.hash`'s `mov cx, bx` (2). With BX = 0 every step above clamps to an empty copy and one NUL into `menu_clkbuf`, and `.jout` is in short reach where `.out` is not | text -5 | text -5 | the live path pays `jcxz` not taken (6) for `or` + `jnz +3` taken (19) |
| `gfx_blit1_x`'s `.noswap`: `mov sp, bp / add sp, 18` -> `lea sp, [bp+18]` (pass 10's leftover, item 4) | cold -2 | cold -2 | 3 bytes to fetch where 5 were - on the 8088 both spellings are fetch-bound, ~20 -> ~12 cycles once per call |
| DOCK.DRV `dk_pass`'s five refusals to `.off` share one relay `.offj: jmp .off` behind the `jmp short .count` | module -12 (`dock.drv` 2,246 -> 2,233 in os88mod's count) | - | a pass that finds nothing is 12 cycles a test faster; the `.off` path pays 12 more |

**`tools/stkbalance.py` reads `lea sp, [bp+N]`** as the walk already reads
`mov sp, bp` / `add sp, N` - it never modelled `mov sp, bp`, trusting the
frame's `mov bp, sp`, so the one-instruction spelling is its `add sp, N`
half. Eight lines. `tests/unit/t_stkbalance.py` gains a QUIET fixture (both
spellings in one routine, on two paths that meet: the old walker reports the
meet at two depths, which is how the fixture was checked to discriminate -
26 passed, 1 FAILED with the tool reverted) and a LOUD one (a wrong N leaves
a word). 27/27.

At batch 2: kern_big text 43,369, cold 37,841 -> resident **92,298** (-21
from start); kern_small text 31,935, cold 22,652 -> **60,522** (-410).
