# Kernel size pass 21: sweep (the cross-file leads, on the merged tree)

The **sweep** agent's record (BRIEF.md section 4's shape). Branch
`ksp21-sweep`, cut from the merged tip `0d84b497b` (ten agents in). Owned:
every kernel file, the other agents being done, and `apps/os88ui.inc`'s
kernel and package arms (one edit, shared). Work: the CROSS-FILE leads the
ten notes left, the defect and the build trap they named, and four
whole-kernel mechanical scans that only mean something on the merged tree.
No ABI moved: `apps/os88api.inc`, `drivers/os88drv.inc`, the C SDK and
`tools/abi.lock.json` are untouched. Commits: `f952d5f9f` (batch 1),
`5240b4232` (batch 2), `59837a5a8` (batch 3), and this note's.

## BASE AND TIP

Assembled, `tools/kernsize.py --json` in this worktree. Resident = `.text` +
`.bss` + `.cold` + `.lowbss` + `.vgabuf` + `.vga` (+ `.mega`).

| kernel | `.text` | `.bss` | `.cold` | resident base -> tip | delta | `KERN_SIZE` |
|---|---:|---:|---:|---:|---:|---|
| **kern_big** | 39,140 -> 39,106 | 4,917 -> 4,913 | 37,208 -> 37,188 | 89,156 -> **89,098** | **-58** | 94,720, unchanged |
| **kern_small** | 28,737 -> 28,713 | 2,783 | 20,490 -> 20,473 | 54,878 -> **54,837** | **-41** | 56,832, unchanged |
| kern_emu | 39,382 -> 39,346 | 4,917 -> 4,913 | 37,208 -> 37,188 | 89,398 -> **89,338** | **-60** | 94,720, unchanged |
| kern_mega | 44,897 -> 44,863 | 5,144 -> 5,140 | 52,429 -> 52,399 | 133,206 -> **133,138** (`.mega` 24,800) | **-68** | conventional 61,440, unchanged |

kern_mega's conventional sections (`.text` + `.bss` + `.lowbss` + `.vgabuf`)
are 55,977 -> 55,939 (-38); the other -30 is `.cold`, above 1MB.
`os88megaseg` reads 3,787 against `tests/megaseg.txt`'s 3,793: **no change
to the allowance was needed.** `.lowbss`, `.vgabuf`, `.vga`, `.boot2`, `.ovl`
are unchanged on every kernel. Every `.text` total moved by an EVEN amount
(-34 / -24 / -36 / -34), so no `.bss` word changed parity.

**Module images** (os88rdiff, unpacked): kern_big CTRL.DRV -2, FSCHECK.DRV -4,
DISKOPS.DRV -6, STIKMENU.DRV -2, HIBER.DRV +2, EXTD.DRV +2 (**-10** in all);
kern_small DISKOPS.DRV -8, CTRL.DRV -2. **Packages**: os88ui.inc's scroll
arrow is -2 in every package that assembles the bar (browser, midirack,
notepad, redline, scribe, taskmgr, thewire, word: -16 by their listings).

**Gates** at every commit: `make -j3` (fast tier 54 passed, `hotpar` green on
both gated kernels with no pad added), `make -j3 small`; at the tip also
`make -j3 emu mega` (`os88megaseg` green). `tools/stkbalance.py` over
`kernel/*.inc`, `kernel.asm` and `apps/os88ui.inc`: 0 unbalanced paths, both
knob settings. `checkdocs` after every `git add`. **No `int 13h` call was
added or removed anywhere**: the mount items (DESK_LEARN, the BPB path) move
code and no I/O decision; the listing items (FIND, dsk_docpass) read the same
sectors; the write path's two jumps are the same branches.

## THE TWO FIXES

* **The FIND flags defect (disk.md's DEFECTS FOUND): FIXED, +2** `.cold`
  (kern_big, emu, mega; kern_small has no redirected arm). `dsk_find_x`'s
  `.stage` (FSV_ENUM's answer, the DSK_DSCAN build) loaded CL with +24 and
  left CH as dsk_dscan's returned CX - the next ROW - so the +22 flags word
  read `(row+1) >> 8`: OSAPI_FIND_CZ ("compressed") on entries 255..510 of a
  RAM disk or cable folder, OSAPI_FIND_FAR from 511. Verified by reading
  dsk_dscan's `.fsenum` (`pop cx / inc cx / jnc .out`) and the `.staged`
  tail (`mov al, ch / mov ah, 0 / stosw` is +22). It has been there since
  62.9.17 (`xor cl, cl` cleared CL only); the non-DSCAN arm (kern_dos) had
  the driver's CH and gets the same fix. `mov ch, 0`, as disk.md proposed.
  REFUSED in its place: `mov cx, [dsk_ent+24]` (0 bytes), which leans on +25
  being zero - SPEC.md 19.1 declares it, but a third-party driver is not
  ours to trust for a flags word.
* **The COLD_HOME = 0x0855 trap: GONE, 0 bytes.** `winmod.inc`'s `sub dx, 7`
  (`83 EA 07`, then `cmp [di+W_H], dx` = `39 55 08`) is `add dx, -7`
  (`83 C2 F9`): the same DX, and `cmp` writes every flag the next `jl`
  reads. **Proof, by os88rom.py's own code**: a scratch driver wraps
  `os88rom.cfix_prove`, and for every candidate home H it re-stamps each
  module image's real `.cold` words with H and runs the unmodified
  `cfix_prove(images, names, mods, H, vst)` - the exact proof `make` runs
  for the tree's real home - plus a raw scan for any non-site
  `9A|EA lo hi H_lo H_hi`. **Broken on purpose first**: with the base's
  winmod.inc and a rebuilt `kernel-full.bin`, H = 0x0855 fails at WIN95.DRV
  +0x265, exactly the agents' finding; with the fix, **0 failures for every
  H from 0x0820 to 0x0870 on kern_big (home 0x0839) and on kern_emu (home
  0x0848)**, at the tip. Widened to 0x0800..0x0890 it finds one more,
  **0x0872** (CTRL.DRV +0xced, DISKOPS.DRV +0xfeb): `9A 96 9A 39 08 72 08` is
  a real `call 0839:9A96` and a `jc +8`, read as `9A ... 0872` because the
  routine's OFFSET has a high byte of 9Ah. That one is layout-dependent (the
  offset moves with `.cold`), so it is a property of this tree and not a
  standing trap like WIN95.DRV's; noted, not chased.

## TAKEN

Bytes are kern_big / kern_small / kern_emu / kern_mega, resident. "all" =
the four. Nothing changes behaviour; every refusal answers as it did.

### Batch 1 (`f952d5f9f`): -31 / -14 / -31 / -28

1. **FIND flags defect**: +2 / 0 / +2 / +2 (above).
2. **WIN95.DRV trap**: 0 (above).
3. **extmod.inc's two `KDOOR vid_disp_of` are `EXK`s; `rd_tab`'s word
   goes** (hw lead 1): -2 / 0 / -2 / -2, EXTD.DRV +4. The private block is
   before RD_P, so no published index moves. ~390 clocks a hop against the
   door's ~420 (ext_e_ylow at a drag's release, ext_org_disp on
   OSAPI_WM_DISPLAY's path).
4. **hiber.inc's `KDOOR wm_paint_all` takes HIBER.DRV's own `hbg_kgo`**
   (hw lead 2; `hbg_kgo` had no caller): -2 / 0 / -2 / -2, HIBER.DRV +2.
   kern_small keeps the word (desk.inc's `.cold` site) and its door site.
5. **`str_len` written in `toast_place`, its one call** (hw lead 4): -4 all
   here; item 25 makes it -6.
6. **`fm_more_mark` and `fm_dgxor` bank BP (`kentc_bp`/`kretc_bp`) and reach
   `gfx_fill_pat` / `vga_xor_rect_vram` through `cw_mem_disp`**, so their
   one-site shims go (hw lead 5): -2 all (-1 each). ~+45 clocks a call
   against a fill or a four-edge XOR outline (thousands): under 1%.
7. **`fm_brun` makes the far call; `ct_cw_font_run` goes** (hw lead 6):
   -1 / 0 / -1 / -1. kern_big's one other site (os88ui's `UI_RUN`) is the far
   call through the `%define` block above the includes.
8. **`dskw_czseg` beside `dskw_wseg`: one `MEM_RR_ROW dskw_seg, 3, 2`**
   (sys lead): -4 / 0 / -4 / -4 (OS88_COMPACT). The `%error` beside the
   declarations covers all three words; SPEC.md's relocation table already
   named the three.
9. **`assoc_compose` written in `dsk_docpass`** (desk lead): -10 / 0 / -10 /
   -10. The slot is stored first (the `cli` keeps every reader out), ES is
   banked round it, CX/DI/SI are the pass's to spend; `mov di, dsk_ico +
   ASSOC_INSET` replaces the push/pop/add. assoc.inc's -68 is even ahead of
   `dsk_xfer`; the body lands after `dsk_next_clus_x`.
10. **`desk_learn_x` written in `disk_mount_x`** (desk lead): -8 all. AX
    and BX are nobody's there (`dsk_bpb_bank_put` clobbers AX..DI with
    nothing carried across); the block is +48 inside [dsk_runcap,
    dsk_next_clus_x), even, and no jump relaxed. kern_dos (`KD_BUILD`) had a
    `ret` stub and now has neither.

### Batch 2 (`5240b4232`): -21 / -21 / -23 / -34

11. **`jcc +2 / jmp short X` as one inverted jcc** (wm scan), -2 each and
    faster both ways; where the target is out of reach nasm writes
    `jncc $+5 / jmp near`, the bytes that stood: `gfx_points`' `%%skip`
    (three loops: -6 / 0 / -6 / -6), dskw's chain-write arm (-2 big/emu),
    `drv_call`'s ss_row test (-2 big/emu/mega), kern_mega's FAT32 read walk
    and its restart park (-4 mega), and on kern_small `gfx_blit1_x`'s band
    test (the "NEAR on purpose" one: near on kern_big still, short on
    kern_small, -2) and `font_run_cell`'s clip test (-2). Both H1 bodies are
    faster on both paths (a taken jcc where a not-taken one plus a `jmp`
    stood, and the other way round) and change by an even amount inside.
12. **kern_small `desk_click_x`**: `.sel` falls into `.out` (EB 00, -2).
13. **`lea` for `mov` + `add`/`sub`** (wm scan), where no flag is read:
    `font_run_x`'s trail scan (`lea si, [bx-4]`, per run, ~8 clocks faster;
    -2 all), `db_rect_ax` (-2 all), `desk_colr` (-2 big/emu/mega), and
    os88ui.inc's scroll arrow, `lea bx, [bp+si]` (-2 all, and -2 in every
    package with a bar).
14. **`font_ch_spill` hands `ext_fcut` the glyph INDEX** (input lead): -2 /
    0 / -2 / -2, EXTD.DRV -2. AL reaches `font_ch_drop` as the index now,
    and `font_char.done` pops AX.
15. **kern_small `vid_depth_set`**: the pair as `mov [vid_mono], word
    0x0101`, AX never touched (-2). ONE source line still writes
    `[vid_mono]` and it is a word store, so `t_invariants` holds unchanged.
16. **files.inc's `[wm_zn]` load as `mov al / cbw / xchg`** (-1 all).
17. **`KSEGR` for `KDATAR`** (hw lead 3): task_yield's VMM poll, kern_emu
    -2 (-1 and a jump it brought into short reach); `dsk_dbg_raw` is the
    DISKCNT knob's alone.
18. **`mem_free_x`'s own refusal of 0 for an `or dx, dx / jz`** on three
    rare paths (desk lead): kern_mega's two read-ahead landings (a shed
    took them: -8 mega) and kern_small's window open (-4 small). mem_ishidx
    (0) is CF = 1 and no live record has base 0, so it walks the records
    and refuses: ~2,000 clocks under `cli` on those paths alone.
19. **kern_small's two adjacent `.cold` PARITY nops** (blank.inc's tail and
    wm.inc's next byte, both 0x20C/0x20D): they cancelled (-2).

### Batch 3 (`59837a5a8`): -6 / -6 / -6 / -6

20. **EXT_STRADS and EXT_APPLY as one entry, CF in the selector** (wm lead
    6): `stc` at `wm_apply_wh`, `clc` at `wm_snap_w`; mod_gone's CF = 1 out
    answers both. EXT_DEAD, the last entry, moves into slot 3 (pass 20's
    shape for slot 10) and EXT_NENT is 14: -2 / 0 / -2 / -2 (`.bss` -4,
    `.text` +2), EXTD.DRV +2. **EXTD.DRV's entries are no package's** -
    only EXTCALL names them, and a module image is refused unless its
    MOD_STAMP is this kernel's - so this reorders no published entry.
    SPEC.md 39.19.6's table follows.
21. **`clk_h12h` as `sub / ja / add / jnz`** (-2 all): the same 1..12 for
    every 0..23 (checked exhaustively); both callers read AL alone.
22. **`toast_place` counts from -1** (-2 all; item 5 is -6 with it).
23. **kern_small `dskw_write`'s commit: `jnc dskw_relold`** (-2; kern_big
    keeps nasm's old `jc $+5 / jmp near`).
24. **Module images only**: one jcc for `jcc +2 / jmp` in DISKOPS.DRV
    (`clo_boot0`, diskmut's rmtree, compress's chain write), STIKMENU.DRV,
    FSCHECK.DRV and CTRL.DRV (`driver.inc`'s track buffer); FSCHECK.DRV's
    `jmp fsk_aftlost` to the next byte, and kern_small's two EB 00s
    (DISKOPS.DRV's `clo_boot0` tail, CTRL.DRV's key path). The three
    `jmp short $+2` in CTRL.DRV are I/O delays and were left.

## THE SCANS (whole kernel, merged tree, both gated kernels' listings)

* **Jumps to the next byte** in resident sections: only kern_small's
  desk_click_x (item 12); mega.inc's two are kern_mega's own file.
* **`jcc +2 / jmp`**: item 11's nine; the rest of the list is module bytes
  (item 24). Every `jcc +3 / jmp near` pair in a resident section is out of
  short reach.
* **Relaxed jumps now in short reach** (a 3-byte E9 or nasm's 5-byte
  `jncc +3 / E9` whose target a short form reaches): **none**, on kern_big
  or kern_small. The merged tree's nasm pass converged.
* **`mov r, base / add|sub r, imm`**: item 13's four; `mod.inc`'s and
  `lzfilt.inc`'s read the flags (`jbe`), and every label subtraction is
  nasm's REFUSED 1 (a negated section label does not assemble - nor in an
  immediate: `mov cx, -1 - toast_buf` was tried for item 5).
* Also scanned, nothing left: `cmp r, 0`, `jmp` to a bare `ret`, adjacent
  `push r / pop r`, `xchg` pairs.

## REFUSED

1. **desk.inc's `cw_wm_dmg_hit` and `cw_wm_zone_r` through `cw_mem_disp`**
   (hw lead 5, -1 each): BP is LIVE across their routine -
   `desk_dmg_zones_x`'s callers are `wm_paint_dmg`, which holds its flag in
   BP to `.fill`, and `desk_dmg_zones_x` promises every register but AX
   (and SI on kern_small). A `push bp / pop bp` is +2 against -1.
2. **`or dx, dx / jz` before `mem_free_x` on the COMMON paths**: menu_drop's
   save-under (-4; on the 128KB machine the save-under is refused every
   time, so the walk would ride every menu close), `wm_su_drop` (-4; the
   raise cache, S3), `clip_drop` (-4; its CF = 0 is clip_put's answer,
   which mem_free(0) would turn to 1), diskw's `dskw_hzfree` (the 0 there
   is a different action, the pool).
3. **`ui_drain` as `resb 1` with `[dock_drew]`** (ui and draw leads, -1
   `.bss` each): the two are ui.inc's and dock.inc's, and every `.bss` word
   between them - apps, assoc, mod, lz, disk, diskw, files, filecp, fdlg,
   icons, desk - would flip parity. No partner inside ui.inc.
4. **draw's "any two of three PARITY pads between gfx_blit4 and font_run"**:
   the input agent took two of them in this pass (font.inc's own note);
   one span on kern_big now holds at most one pad, so each pad is held for
   an odd saving in its own span (there were none: see the scans).
5. **`inst_rel_rec` + `xm_release_rec`** (hw's CROSS-FILE 9, ~-5): left as
   the brief says - the merge runs the sound and serial releases under a
   16-byte-deeper frame on a worker's teardown, and that stack class was
   not proved here.
6. **`clk_ampm`, `clk_put2`, `toast_place`'s bar arithmetic**: every
   rewrite found is the same length; SALC and AAM-with-12 are not V20-safe.
7. **A single-caller sweep**: 245 candidates on kern_big's listing, almost
   all alternate entries, `FCPX`/`SMK` far calls from images, or bodies a
   pass already chose to keep. Not taken wholesale; items 5, 9 and 10 are
   the ones the notes priced.

## ODD SHIFTS (unpinned code, for the coordinator)

`hotpar` is green with no pad, but these runs of UNPINNED code now sit at an
odd shift against `0d84b497b` (`os88rdiff kernel 0d84b497b .`'s shift runs):

* kern_big `.text`: `clk_h12h .. wm_apply_wh` and `wm_fullscreen ..
  toast_place` (str_len's -13 and the inline's +7, item 20's `stc`/`clc`
  between them); `.cold`: `fm_count .. fm_dgxor` and `fm_2line .. fm_brun`
  (files.inc's items 6, 7 and 16, +3 / +3 / -1 / +3).
* kern_small `.text`: `clk_h12h .. toast_place` (396 routines: wm.inc,
  memory.inc, instance.inc, menu.inc); `.cold`: four short runs in files.inc,
  os88ui.inc and desk.inc, and the tail `ser_api_x .. cold_kretf` (the
  `kentc_*` helpers), `.cold` being an odd -17 there.

A cost on an 8086/V20/286 bus and none on the 5150's 8088, which is what
pass 20 and this pass's wm agent recorded of theirs. **Two PARITY pads (+2:
one where str_len stood, one after toast_place) put the `.text` runs back on
both kernels** except kern_big's 41 routines between the `stc` and the
`clc`, if the coordinator wants that at the close; not taken here (bytes,
not rungs).

## WANTS THE OWNER

None new. Left alone as the brief says: the keypad-5 defect in `kbm_isr`
(input.md), diskw's latent kern_mega FAT32 `dskw_wck` reload (diskw.md).

## WANTS AN ABI BREAK

None.

## CROSS-FILE

None outstanding: every file was this row's. `tests/zrestart.py`'s stale
comment (sys.md CROSS-FILE 4) and fdlg.inc:1344's (wm.md CROSS-FILE 7) are
still prose-only and untouched.

## ROWS (named, not run - the coordinator's union)

* The FIND flags fix (1): `rdcz`, `rdmount`, `httpmount`, `httpmountname`,
  `httpinstall`, `install`, `thewire`, `stiknote`, `assocfind`, `dosdirsw`.
* WIN95.DRV and the cfix proof (2): `thm95`, `dispthm`, `hmacold`,
  `megahma`, `hmadrv`, `api-abi-all`.
* EXTD.DRV (3, 14, 20): `extdmod`, `megarmbext`, `dispdrag`, `dispfit`,
  `dispstrad`, `dispzoom`, `dispsize`, `dispseam`, `dualcheck`,
  `dispcheck`.
* HIBER.DRV's hop (4): `hibernate`, `hibernatedrv`, `hibernatem`,
  `megahiber`, `hmahiber`, `stikhiber`.
* toast_place, str_len, clk_h12h (5, 21, 22): `toast`, `toastbar`,
  `toastfpg`, `deskclock`, `dtfield`.
* files.inc (6, 7, 16, 18): `deskdrag`, `dragui`, `fmarrows`, `fmthumb`,
  `fmbtn`, `fmrefuse`, `fdlgchoose`, `fdlgsmall`, `sbar`, `sbardlg`.
* The relocation row (8): `lzship`, `lzship-lzb`, `czto`, `czjoin`,
  `wdheapmove`, `heapcheck`.
* dsk_docpass, disk_mount_x (9, 10): `assocglyph`, `dosglyph`, `icoshed`,
  `deskfdd`, `rdmount`, `kerndos`.
* Drawing (11, 13, 15): `gfxpoints`, `gfxptsmall`, `fonts`,
  `kbdlayoutfont`, `blitp`, `dispblit`, `smallboot`, `small128`,
  `dockmark`, `dockpos`, `deskdock`, `deskzoom`, `desksc`, `npscroll`,
  `wdscroll`, `brscroll`.
* Drivers, the write path, kern_mega (11, 17, 18, 23): `drvcall`, `saver`,
  `savervga`, `dirwsize`, `dskwstage`, `fcpcopy`, `fat32`, `fat32big`,
  `megarsq`, `hdbounce`, `vmmouse`.
* Module images (24): `fsckdisk`, `fsckhd`, `fsckmega`, `stikmenu`,
  `stik`, `czjoin`, `cpup`, `cpwide`.

## DEFECTS FOUND

* **FIND's flags word on a redirected volume** (disk.md's) - fixed, +2.
* **The 0x0855 build trap** (hw/wm/sys/files notes) - fixed, 0 bytes, and
  proved clear for 0x0820..0x0870 by os88rom's own proof.
* No new behavioural defect.
