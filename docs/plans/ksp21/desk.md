# ksp21 agent "desk" - the desk, the shortcuts, associations, the chooser, the copy engine

Kernel size pass 21 (`docs/plans/ksp21/BRIEF.md`, row `desk`): `desk.inc`,
`desksc.inc`, `stikmenu.inc`, `assoc.inc`, `fdlg.inc`, `filecp.inc`. Branch
`ksp21-desk`, base `3fc4e9d09` (the brief). Figures are ASSEMBLED,
`tools/kernsize.py --json` absolutes on each kernel's own build tree, and
`tools/os88rdiff.py kernel 3fc4e9d09 .` (with `-D KERN_SMALL`, `-D KERN_BIG
-D KERN_MEGA`) for the routines. Resident = `.text` + `.bss` + `.cold` +
`.lowbss` + `.vgabuf` + `.vga`.

**TAKEN outside the row**: nothing. Every edit is in the six files.

**The finding**: the largest share was **flags and registers already holding
the answer** - a `clc`/`stc` after a jump that had set it, a bank of a
register no caller reads, a compare repeated because two tests were written
in the wrong order (fcp_step's Cut test, fcp_run2's drive test, two verbs of
OSAPI_DESK_ITEM answered by one compare). Second, **two arms storing the
same cells** (fcp_fnames, now written in fcp_file1). Third, **the new
pass-20-to-21 code**: `fcp_step`'s DISKOPS hold relaxed a `jnc` and repeated
the Cut test; both went. And one **defect** (below), found by reading the
sweep's register contract against its two procs.

## BASE AND TIP

| kernel | base `3fc4e9d09` | tip | delta | where |
|---|---:|---:|---:|---|
| **kern_big** | 90,225 | **90,120** | **-105** | `.cold` -105 (37,830 -> 37,725) |
| **kern_small** | 55,672 | **55,642** | **-30** | `.cold` -26 (20,860 -> 20,834), `.bss` -4 (2,843 -> 2,839) |
| kern_emu | 90,471 | **90,366** | **-105** | as kern_big |
| kern_mega (with `.mega` 24,800) | 134,293 | **134,187** | **-106** | `.cold` -106 (53,078 -> 52,972, above 1MB); conventional `.text`+`.bss` unchanged (50,479), `.mega` unchanged |
| kern_small FILECP.DRV (`.modp`) | 0x77E | **0x752** | **-44** | not resident |

`.text`, `.lowbss`, `.vgabuf`, `.vga`, `.boot2`, `.ovl` and `.mega` are
unchanged on every kernel; kern_big's `.bss` too. FDLG.DRV, STIKMENU.DRV
and CTRL.DRV are byte-identical in content (no `.modd`/`.modn`/`.modu` line
moved). No module grew. `make`, `make small` (its sub-make), `make emu` and
`make mega` at the tip; the fast tier 54/54 with `hotpar` at every commit.

## TAKEN

Bytes are kern_big (= kern_emu; kern_mega's `.cold` the same unless noted) /
kern_small. Commits `5a8962cfb`, `12fec25f3`, `94fe5d4b6`, `7a0222b08`,
`b4e2bde9e`, `a705c9b07`, `ef9674cdc`.

### filecp.inc (-61 / -3, FILECP.DRV -44)

1. **`fcp_step`: a Copy goes straight to `.claim`** (-7 / -). kern_big's
   `.copyit` asked `[fcp_op]` = Cut again, which the first step had just
   answered; the first `jne` now lands past it there (`%ifdef DSKW_DIRMOD`
   keeps kern_small's route, where a folder Copy holds too).
2. **`fcp_relink` answers AX = 0 on success, so its `jnc` is `fcp_stop`
   itself** (-2 net: -3 for the relaxed `jnc .finish2`, +1 for `.done`'s
   `xor ax, ax` in place of `clc`). A short jump BACK, written `jnc short`
   so the build refuses if it stops fitting; `%if FCPS_DONE != 0` pins it.
3. **`fcp_answer`** (-5 / FILECP.DRV -5): `[fcp_all]` is stored as the answer
   less one (0 for 'this one' - the 0 a question is asked under, fcp_file1
   asks only then - and 1 for 'all'; both flags are read zero/non-zero), and
   `.stop` falls into `.idle`'s `mov al, FCPS_DONE` (AL is 0 already, and
   fcp_stop and fcp_lend keep AX). This brought kern_small's `jnc short
   fcp_stop` into reach as well.
4. **`fcp_run2` tests the DRIVE first** (-9): a different drive skips both the
   same-folder no-op and the self-check, which asked the drive again; the
   predicate is unchanged (same drive AND same folder is `.none`; type < 2 or
   another drive is `.selfok`).
5. **`fcp_fnames`: one set of stores, written at its one call in fcp_file1**
   (-10; kern_mega -12): both arms load AX/DX (and CX/DI for the FAT32 high
   words) and share the stores; the inline also let fcp_file1's `jmp
   fcp_xfer` go short.
6. **`fcp_room`'s want is `sub`/`sbb`, whose borrow is the answer** (-5).
7. **`fcp_xfer`**: `.err` moved onto the `.jerr` hop, so one relaxed `jc`
   shrank, and `.fin`'s `clc` follows CF = 0 on every way in (-6); then
   kern_big's **`fcp_rdnext` written at its one call** and the first chunk's
   create arm moved below the loop so the back edge stays short (-4; the
   later chunks now fall into `.more` where they took a `jne`, faster).
8. **`fcp_rdnext` (kern_big) stopped banking ES** (-2): fcp_xfer banks ES at
   its top and reloads it (fcp_wprep) before it reads it; dsk_goto,
   dskw_dfree and fpg_opbegin take no ES. Since folded into item 7.
9. **`fcp_stop` frees DX = 0 without a test** (-4): a 0 is mem_find_own's
   refusal on every kernel (fcp_lfree's rule; on kern_mega mega_ishif(0) is
   CF = 1, so the conventional walk refuses it). H4: a stop with no buffer
   (a same-volume move, an early error) now walks the 32 claim records under
   mem_free's cli, ~2,000 clocks (~0.4 ms) against a move's three sector
   writes.
10. **Flags already set**: `fcp_scan`'s `clc` (after `jc .out` not taken and
   the flag-keeping fcp_n13) and `.ioerr`'s `stc` (its one way in is a `jc`)
   (-2; kern_mega -1, its fcp_chi needs the clc); `fcp_relink`'s `.half`
   `stc` (three `jc`s) (-1).
11. **`fcp_claim` keeps the larger span in AX** (-2): DX is not read again
   until mem_claimp answers in it.
12. **`fcp_relink`'s '..' read keeps AX without a bank** (-2): dsk_rd1_x
   spends BX and CX alone, dsk_xfer's kentc_bp frame restoring AX.
13. **kern_small's resident half** (- / -3): `fcp_pfin`'s `je .keep / jmp
   short fcp_fin` is one `jne fcp_fin` (-2); `fcp_pfail`'s `stc` follows its
   two `jc`s (-1).

### assoc.inc (-18 / -, EVEN: dsk_xfer and its neighbours follow it in `.cold`)

14. **`assoc_ext_take`**: a sticky row and the same program's are one
   `mov al, [bx+3] / xor al, dl / jle .no` (DL is a slot < 80h; `xor` clears
   OF, so `jle` is "equal or bit 7") (-4).
15. **`assoc_glyph_take` answers in ZF** (-2): asc_inkck's ZF is the blank
   answer, and the copy ends in assoc_stage's `inc di`, which cannot reach 0.
   Its two callers test `jnz`. `assoc_img_glyph` takes the header back off
   its own frame (`pop si / push si` for `sub si, imm8`, -1).
16. **CF = 0 already there** (-3): `assoc_ext_new`'s `clc` (the `je` that got
   there, dsk_ncopy keeping flags); `assoc_app_new`'s (assoc_glyph_di's byte
   product of a slot leaves CF = 0 - now in its header and asserted);
   `assoc_locate`'s (assoc_hint_here's `shl` of a slot - now in its header).
17. **`asc_use_x`'s second `xor ax, ax`** (-2): AX was still .load's zero.
   **`assoc_run_x` consumes the post by `xchg`** (-2).
18. **`assoc_tryvol` banked BX and DX, `assoc_tryfold` SI, for nobody** (-6):
   the sweep's proc may spend BX and SI (assoc_tryext's contract says so and
   assoc_locate reads neither after the sweep), and nothing in tryvol writes
   DX. Headers updated.
19. **`assoc_sweep` banks DI round drv_cls_svc_x** (+2) - DEFECTS FOUND 1.

### desk.inc (-25 / -27)

20. **`osapi_desk_item_x`'s package arm**: one `sc_modcall` for both verbs
   and one `cmp al, 0FFh` for both answers (-10): an add answers its zone or
   0xFF, sc_m_pdel 0 (sc_m_del's) or 0xFF - and a module that cannot be read
   leaves the 0xFF going in.
21. **`desk_reflow` pass 1 drops its DSL_NONE compare** (-4): DSL_NONE is past
   every `[desk_ncell]` (<= DESK_CMAX = 255), so `.rel` stores the byte it
   already holds.
22. **`desk_cell_xy` multiplies by BYTES** (-5 / -5, and faster: ~-100 clocks
   a cell): the row by `mul byte [desk_zstep]`, the column by `mul bl`, so
   DX rides through and CX is never touched. `%if` pins the pitch and step
   below 256; a row is below [desk_rows] and a column below 256 because a
   cell is a byte.
23. **`desk_zones_paint_x`** (-4 / -1): kern_big walks SI from -256, so SI's
   LOW BYTE is the cell and `inc si / js` ends the walk at cell 255 (DSL_NONE,
   never marked; the last bit of [desk_cdirty]'s 32 bytes) - a 4-byte
   `cmp si, 255` gone (-3); the clean-byte test is `cmp [bx+desk_cdirty], bh`
   (BH = 0, the byte index is below 32) (-1, both). Faster on both.
24. **`desk_cap`'s ground is one word load** (-1).
25. **`desk_zones_r_x`'s Color refusal takes the ring's own `clc`** (-1).
26. **kern_small's `desk_draw_zone` keeps the cell's origin on its stack**
   (- / -15: -11 `.cold`, -4 `.bss`): [desk_zx]/[desk_zy] were stored and
   read back across the ground fill and nothing else on kern_small reads
   them; they are `%ifdef OS88_SHORTCUTS` now (kern_big's desk_col/desk_pic).
27. **kern_small's `desk_zone_redraw`** asks desk_zone_xy's CF and runs
   desk_rect_ax itself, with no AX bank round desk_zs (- / -2).
28. **kern_small's `desk_dmg_zones_x` stops banking SI round wm_zone_r**
   (- / -2, pass 20's lead): its one kern_small caller, wm_paint_dmg, writes
   SI (`.promote`'s `mov si, bx`) before it next reads it, and nothing
   between (wm_dmg_gray, desk_paint_mask_x, db_force_x, db_paint,
   menu_draw_bar, wm_dmg_wins) takes SI in. Header says so.
29. **kern_small's `desk_paint_mask_x`** banks AX and CX alone, all its loop
   spends, and pops its own (- / -2).

### desksc.inc (-1 / -)

30. **`sc_modcall`** banks the operation once across mod_live and mod_need
   (-1).

## HOT PATHS, PARITY AND THE DISK

* **No H1/H2 routine is touched.** H3 changed: desk_zones_paint (faster: an
  `inc/js` for a `cmp imm16/jb`, a `cmp mem, reg` for a `cmp mem, imm8`),
  desk_cell_xy (faster, byte multiplies), desk_dmg_zones_x and
  desk_paint_mask_x on kern_small (two pushes and pops fewer each), desk_cap
  (one fewer instruction). H4: the copy engine (per operation or per file,
  each cheaper, except item 9's no-buffer stop, ~0.4 ms), the association
  search, OSAPI_DESK_ITEM.
* **No `int 13h` added or removed.** The copy engine's reads, writes, gotos
  and stats are the same calls in the same order: item 4 reorders two
  memory compares before any I/O; item 7 moves code, not calls; item 9's
  mem_free(0) is a RAM walk. The association search visits the same volumes
  in the same order (the defect fix makes it ask with the right slot). No
  mount, listing, read-ahead, FAT-window or loader path is in these files.
  Rows: `navcalls`, `fdswap` for the bar.
* **Parity**: `hotpar` green at every commit. assoc.inc is the only file of
  the six ahead of dsk_xfer, dsk_runcap and dsk_next_clus_x in `.cold`; its
  total is -18, even, and every routine behind it is at an even shift
  (`os88rdiff`, 0 identical routines at an odd shift past asc_use_x). The
  other five are behind every pinned routine.
* `tools/stkbalance.py` base vs tip: desk.inc 2/2, desksc.inc 1/1, assoc.inc
  3/3, fdlg.inc 0/0, filecp.inc 0/0, stikmenu.inc 0/0 - the same
  pre-existing ladder tails, nothing new.

## EQUIVALENCE

By reading, per item: for every bank removed, every caller to the next write
of the register (items 8, 12, 18, 28, 29 above, with the routes named); for
every flag taken from elsewhere, every way into the label (items 2, 10, 13,
15, 16, 25); for reordered tests, the truth table (items 1, 4, 14, 20, 21:
each input lands where it did); for the arithmetic (items 6, 11, 22, 23), the
ranges, asserted where they are constants. `os88rdiff` at every commit: no
relaxed jump left in a resident routine of these files (a listing scan of
kern_big and kern_small: the relaxed `jcc`s left in them are fcp_xfer's top
`jc .err`, 44 bytes over, and its redirected `jnc .fin`, 11 over).

## REFUSED

* **`asc_use_x`'s `.out` freeing DX = 0 without a test** (-4, item 9's
  shape): its no-claim path is the COMMON one - every full mount of a volume
  whose cache is already loaded - and the walk would put ~0.4 ms of cli on
  each.
* **`fcp_run2`'s self-check walking with dsk_up_x instead of storing
  [dsk_cwd]** (-3): the walk leaves [dsk_cwd] at an ancestor that
  dskw_sync_x (fcp_stop's tail) may read; not provably identical.
* **`fdlg_open_x`'s caption as `AL * 5 + fdlg_s_topen`** (-4) and its mode
  word by `cbw` (-1): exact for the published AL = 0/1, different for any
  other AL (a non-zero AL is a Save chooser today). Not taken.
* **`desk_col`'s selection inverted a word at a time** (-2): ~+700 clocks on a
  selected cell's draw, over 1% of it.
* **kern_big's `desk_paint_mask_x` on kentc_di with DI as the counter** (-3):
  +~150 clocks on every damage pass for ~27 a drawn zone.
* **`lnk_open`'s two `add sp, LNK_SIZE` tails**: no flag-keeping adjust fits
  (BP is sc_walk's by then).
* **`sc_walk`'s path in SI for `es lodsb`** (-2 there, +2 for dskw_stat's SI).
* **`fcp_srcdel` written into fcp_step's `.finish`**: the same byte count.
* **fcp_dhold's new `.bss` byte** (+1 since pass 20): no byte with a disjoint
  lifetime or a free bit was found - fcp_started is rewritten every step,
  fcp_made is cleared by `shr`, fcp_op and fcp_type are compared whole.

## WANTS THE OWNER

None. Every item is behaviour-identical for every input the contracts name
(item 3's [fcp_all] = 1 for 'all' where it was 2 is read zero/non-zero only).

## WANTS AN ABI BREAK

None found. Everything changed is kernel-internal: assoc_glyph_take,
assoc_glyph_di, assoc_hint_here, assoc_tryvol, assoc_tryfold, fcp_relink,
fcp_room, desk_dmg_zones_x (kern_small) and desk_draw_zone's headers say what
changed. OSAPI_DESK_ITEM, OSAPI_FILE_COPY, OSAPI_ASSOC_SET and OSAPI_FILE_DLG
answer exactly as before.

## CROSS-FILE

* **wm.inc (wm)**: the comment at wm_paint_dmg's `call COLD_SEG:
  desk_dmg_zones_x` ("desk_dmg_zones_x spends AX alone (its header)") is now
  true of kern_big only - on kern_small it spends SI too (item 28). Comment
  only; nothing reads SI there.
* **disk.inc (disk)**: `assoc_compose` (assoc.inc, 68 bytes) has ONE caller,
  disk.inc's dsk_docpass. Written there it saves its call and ret (-4) and
  possibly its kentc_bp/kretc_es frame if dsk_docpass already banks - but
  assoc.inc is ahead of dsk_xfer, so the move must keep assoc.inc's and
  disk.inc's shifts even (hotpar). Likewise `desk_learn_x` (desk.inc, 56)
  has one caller in disk.inc.
* **any file**: `or dx, dx / jz` in front of `mem_free_x` of a word that is 0
  for "none" is -4 wherever the no-claim path is rare (mem_free(0) is a
  refusal on every kernel; item 9). Seen in disk.inc (two), diskw.inc,
  files.inc - not read for their paths' frequency.
* **diskw.inc (diskw)**: dskw_dircall's `mov al, MOD_DISKOPS / call mod_live /
  pushf / call clo_need` is fcp_step's hold sequence again; no shared form
  was found that pays (the two want different CFs back).

## ROWS NAMED (none run - the coordinator's union)

The copy engine (items 1-13): `fcpcopy`, `fcpsmall`, `fcpapi`, `fcproom`,
`fpgop` (it traces fcp_opend, which stays), `fmcommit` (the replace
question's three answers - item 3), `clipkeep`, `dragui`, `msel`, `drvcut`,
`wseqcut`, `doscopyhd`, `bigvol`, `fat32` and `fat32big` (kern_mega's FAT32
arms of items 5 and 10), `navcalls`, `fdswap`. Associations (items 14-19):
`assocopen`, `assocfind`, `assocsweep`, `assocvol`, `assocglyph`,
`assocflush`, `assocstale`, `assocwake`, `assocpage`, `ascabsorb`,
`ascplace`, `dosglyph`, `instassoc`, `doslnk`, and for the defect's arm
(a redirected volume in the sweep) `cdrom`, `cdromsim`, `megacdrom`,
`bmshare`. The desk (items 20-30): `zonedmg`, `deskwhole`, `deskdrag`,
`deskfdd`, `deskclip`, `deskclipsmall`, `desksmall`, `deskflash`,
`deskzoom`, `deskpen`, `deskfit`, `deskground`, `deskitem`, `wirezone`,
`desksc`, `stik`, `stikboot`, `stikmiss`, `stikregister`, `stikmenu`,
`stikshort`, `stiksmall`, `deskkeys`, `deskbench`, `vesa` (a 1024x768 grid:
item 22's byte products), `smalllaunch`. The chooser (fdlg.inc untouched,
but its copy of the Disk window paints through desk_cell_xy's neighbours):
`fdlgsmall`, `fdlgchoose`.

## DEFECTS FOUND

1. **`assoc_sweep` clobbered assoc_tryvol's slot - FIXED** (`b4e2bde9e`, +2,
   by reading). assoc_locate hands the program search to assoc_sweep with
   the app SLOT in DI, which assoc_tryvol reads (`mov bx, di`, `cmp di,
   ASSOC_NDEF`). The sweep's redirected-volume arm computes a DVK_FILE row's
   pass with drv_cls_svc_x, which answers ES:DI = the driver's service table
   - so every volume asked after a redirected row (a RAM disk or a file
   share, in any of the three passes) was asked with DI = that table's
   offset, and when one of them found the program, assoc_locate's `.found` /
   `.known` used it as the slot: `assoc_hint_here` wrote the volume byte to
   `[assoc_drv + offset]` and the cluster word to `[assoc_clus + 2*offset]`
   in `.text`. Reached on kern_big, kern_emu and kern_mega whenever a
   redirected volume is mounted and a document's program is neither at its
   hint nor in the document's folder. The sweep now banks DI round that arm,
   and its header says the proc's DI is kept. No row is known to reach it:
   one would need a redirected volume ahead of the program's volume in the
   sweep's order (`cdromsim` or `bmshare` beside an apps disk, a document
   whose program has no hint) - worth adding.
