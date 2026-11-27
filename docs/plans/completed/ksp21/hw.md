# Kernel size pass 21: hw

The hw agent's record. Files: `kernel/kernel.asm` (the API table, the door,
`kmain`, the shims, `rmk_*`), `driver.inc`, `fsx.inc`, `snd.inc`,
`clock.inc`, `clockw.inc`, `xmem.inc`, `xmabi.inc`, `cpudet.inc`,
`viddet.inc`, `vidsel.inc`, `vidext.inc`, `vxabi.inc`, `ctrl.inc`,
`cpwide.inc` and the `cpw*.inc` family, `boot3.inc` and `boot/`. Branch
`ksp21-hw`, cut from `3fc4e9d09` (the brief). TAKEN edits are in those files
only, plus `tests/unit/t_api_abi.py` (a comment), `tests/megaseg.txt` (the
allowance, item 18), `SPEC.md` and `docs/plans/KERNEL-BYTE-QUEUE.md` (a
status line).

Every figure is ASSEMBLED: `tools/kernsize.py --json` on each kernel's own
tree and `tools/os88rdiff.py kernel 3fc4e9d09 .` per routine. No estimate is
quoted as a saving.

## BASE AND TIP

Resident is `.text` + `.bss` + `.cold` + `.lowbss` + `.vgabuf` + `.vga`
(kern_mega: plus `.mega`, unchanged at 24,800). The bases were measured in
this worktree and reproduce BRIEF.md 0.1 exactly.

| kernel | base | tip | delta | where |
|---|---:|---:|---:|---|
| **kern_big** | 90,225 | **90,163** | **-62** | `.text` 39,510 -> 39,474 (-36), `.cold` 37,830 -> 37,804 (-26) |
| **kern_small** | 55,672 | **55,584** | **-88** | `.text` 29,101 -> 29,013 (-88) |
| kern_emu | 90,471 | **90,409** | -62 | as kern_big |
| kern_mega | 134,293 | **134,243** | -50 | `.text` 45,275 -> 45,245 (-30), `.cold` 53,078 -> 53,058 (-20); conventional (`.text`+`.bss`+`.lowbss`+`.vgabuf`) 56,415 -> 56,385 (-30) |

`.bss`, `.lowbss`, `.vgabuf`, `.vga`, `.mega`, `.boot2` and `.ovl` did not
move on any kernel. `KERN_SIZE` is unchanged on every kernel (95,744 /
57,344 / 95,744 / 141,824): no rung was the point and none was crossed.
**No module image changed size** (every `.mod*` section identical in
`os88rdiff`); no `int 13h` call was added or removed anywhere - the one
loader path touched (`drv_load_at`, item 6) runs the same one read.

**Parity**: every `t_hotpar` routine is at an even shift on kern_big and
kern_small (`os88rdiff --hot` against the base; `hotpar` green in `make`),
and so is the door (`os88_door` -36 big, -88 small) and `rd_tab`. Odd items
were paired inside each region. kern_big: ahead of `ui_task` items 1, 2, 4,
5, 6, 15, 17 and 18 sum to -30; between `dsk_img16`'s self-adjusting pad
and the door items 10-13 sum to -6. kern_small: ahead of `ui_task` -26
(items 1, 2, 4, 5, 14, 17, 18), and in `fsx.inc` ahead of the door -62
(items 13 and 16). `.cold`'s hot `gfx_blit1_x`, `dsk_xfer`, `dsk_runcap`
and `dsk_next_clus_x` see only item 3's -6; items 7-9 are after them.

## TAKEN

Bytes are kern_big / kern_small / kern_mega (kern_emu = kern_big). Nothing
here is on a khp1 H1/H2 list; the hot-path notes give the count.

### kernel.asm

1. **`osapi_font_glyphs` by `les`** (-7 / -7 / 0). Both glyph pairs are
   SEGMENT then OFFSET (`font_seg`, `font_base`; `klf_saved_seg`,
   `klf_saved_base`), so `les dx, [pair]` reads either and `mov si, es`
   finishes; ES is pushed and popped round it. kern_mega keeps the four
   loads: an offset loaded into ES is no selector there. Both adjacencies
   are asserted below the includes. From #396 (keyboard layouts, +26).
2. **`kmain` loads DS and ES from CS** (-3 / -3 / -3). The loader's far jump
   is to KERNEL_SEG:0000 (`cold_entry`), and on kern_mega `[k_dsel]` is
   KERNEL_SEG until `mega_enter` at kmain's foot; `jmp kmain` in
   `cold_entry` is the only way in. Once a boot.
3. **kern_big's `api_refusec` is `dwf_dskw_vstat.bad`** (-6 `.cold` / 0 /
   0). OSAPI_FILE_PLACE's RN refusal (FAT32, #394) was six bytes of its own;
   OSAPI_VOL_STAT's no-volume exit is `mov ax, FERR_NODISK / stc / retf` by
   that cell's PUBLISHED contract (CF = 1, AX = FERR_NODISK) and writes no
   other register - OSAPI_XREFUSE's answer exactly. `FERR_NODISK = 1` is
   asserted; SPEC.md 20.3.4 and `t_api_abi`'s DOOR_OWN comment say so (the
   entry still names `api_refusec`, which the map lists at that address).
4. **`api_file_rename` stages the new name where the old one's NUL left
   DI** (-4 / -4 / -4): `push di / call api_copyname / pop di` for the two
   `mov di, api_name2`. Two names of at most 13 bytes each fit
   `api_name`'s 26 (asserted); `dskw_nbody` parses both into its own 8.3
   buffers and only reads these.
5. **The name stubs share one `pop si / pop ds / retf`** (-3 / -2 / -3):
   `api_fdlg_open`, kern_big's `api_file_write_sys` (both arms) and
   `api_file_rename` jump to `api_ff_go.tail`; OSAPI_FILE_FIND, the one
   called per entry, still falls in. +15 clocks on an open, a system write
   or a rename, each a disk operation.
6. **`api_file_write_sys` stages the name before its fence, as `api_nb`
   does** (-4 / 0 / -4): the `push ds / pop ds` round the fence and the
   second KDS go. A refused caller's name is staged and dropped; no file
   call can see it (every file call is the UI task's, SPEC.md 20.6 rule 7).

### ctrl.inc / driver.inc

7. **`cp_open_x` is its own far entry on every kernel** (-15 `.cold` / 0 /
   -15). `cpf_cp_open`'s `call cp_open_x / retf` went (-4); its KERN_BIG arm
   answers `cp_open_need`'s CF straight into the epilogue (`jc .out`, no
   `jmp short .out` and no `stc`, -3); and `drv_notice_x` TAIL-jumps it -
   `cp_open_x` keeps AX itself, so its bank went, and the test-and-clear of
   `[drv_nerr]` (only ever 0 or 1) is one `shr byte [drv_nerr], 1 / jnc`
   (-8). Pass 20's "what is left" item, taken further. Once a boot.
8. **`drv_load_at`'s tail** (-3 `.cold` / - / -3): DRVE_OK is stamped once
   before the overlay test (the attach half's `%1_att` stamps it again
   before it calls the driver, and `%1_hma` between reads no ERR byte), so
   the `.ovl` block and the `.already` hop go, the attach's refusal falls
   into the one tail, `.out` comes into short reach of `jne .already`, and
   the class-twice `jmp .fail` relaxes to short. Same one read.
9. **`drv_bss`'s paragraphs-to-bytes by the byte multiply** (-2 `.cold` /
   - / -2): `mov ah, 16 / mul ah` (drv_row_x's form) for `xor ah, ah / mov
   cl, 4 / shl ax, cl`; ~+45 clocks once a driver load.
10. **`drv_pkg_call_x`'s second `mov al, bh`** (-2 / - / -2): AL is still
    BH - drv_cls_svc_x keeps AX.
11. **...and its `jc .noes`** (-2 / - / 0): the DSV_PKGCALL read is
    unguarded; on a refusal it reads a word a few bytes into whatever ES
    is, harmless in real mode, and `mov` keeps the CF the next `jc` reads.
    -4 clocks on every package-to-driver call. kern_mega keeps the jump (a
    null selector there would fault).

### snd.inc / fsx.inc / clock.inc / vidsel.inc

12. **`spk_off` tail-jumps `spk_pcm_idle`** (-1 / - / -1), its `.out` and
    `.err`'s `ret` one byte.
13. **`fsx_mine`'s first exit is SKIPAX2 over the second's `or`** (-1 / -1
    / -1): `mov ax, imm16` writes no flag and AX is popped. ~+12 clocks a
    call (fsx_wait / fsx_page, once a frame: under 0.02% of a frame).
14. **kern_small's two parity pads, as a pair** (0 / -2 / 0):
    `api_file_path`'s never-executed `nop` and `vid_reboot`'s near `jmp`
    (short again), the only two odd pads ahead of kern_small's hot
    routines.
15. **`vid_ctx_act` by KSEGR** (-1 / - / 0): `mov cx, cs` for `mov cx,
    KERNEL_SEG` - a byte and two clocks less (kern_mega's macro is the same
    data-alias load).
16. **kern_small's `fsx_mtab` and `fsx_bmodes` stop at id 4** (0 / -61 / 0).
    `fsx_capstab`'s VGA slot - never read there, no kern_small kind being
    VID_VGA - holds the CGA's 0x000F on a build with no VGA renderer, so no
    kind offers ids 5-8 BY CONSTRUCTION IN fsx.inc (the old note declined the
    one Mode X byte because the proof crossed into viddet.inc; this makes it
    local), and the four VGA rows (56), their four BIOS modes and id 4's
    hole (5: id 4 is `.herc`'s and never reaches the `xlatb`) go. SPEC.md
    53.4 says so.
17. **`clk_tick`'s "already decided" test** (-4 / -4 / -4): after the
    catch-up loop each arm sets bit 1 again or leaves it, so `test al, 2 /
    jnz .pend` bought nothing but a shortcut on the >= 60 s path.
18. **`clk_inc_sec` written in `clk_tick`'s loop, its one caller** (-4 / -4
    / -4): the call and the `ret`, ~35 clocks a second faster. The guard is
    still per second (SPEC.md 37's rule 1, reworded to say where).

`tests/megaseg.txt` 3,778 -> **3,784** with a line: items 1, 11 and 15 are
kern_big savings kern_mega cannot follow (+10 to the difference, the 4 bytes
of slack first), and no kern_mega byte went up.

Sum: kern_big 7+3+6+4+3+4+15+3+2+2+2+1+1+1+4+4 = **62**; kern_small
7+3+4+2+2+1+61+4+4 = **88**; kern_mega 3+4+3+4+15+3+2+2+1+1+4+4 = **46**,
assembled -50 (alignment after `.cold`'s rung).

## REFUSED

1. **The `cw_` shim census (KERNEL-BYTE-QUEUE item 1) is exhausted in its
   old form**: pass 19's `KDOOR` took the kernel's own shims, and 20 bodies
   are left on kern_big - the drawing doors, `wm_pkgcall` (it takes BP),
   `clk_snapshot` (kern_dos's), `cw_kretf`, the dual-display pair. The
   single-site ones are `gfx_blit1_x`'s (refused twice already) and four in
   other files (CROSS-FILE 5). The queue's status line says so.
2. **The `ct_` trampolines, recounted off the listing by target address**:
   none pays for its removal on either kernel (kern_big `ct_cw_xor_fill` 2
   calls + 1 tail, +1; `ct_cw_font_run` 1 + 1, -1 only with files.inc's
   site, CROSS-FILE 6; the 3-call ones are washes).
3. **`api_seg`'s `push cs / call api_far / ret` as a tail** (-2): a tail
   cannot build the far frame in the right order.
4. **`cp_tickp` back to an immediate** (-3): it is the wide Display page's
   test countdown's gate (SPEC.md 135.9.4); no smaller shape keeps both.
5. **`drv_dlg_name` (14 `.bss`) into `cp_sbuf` or `fdlg_name`**: the first
   is a UI-task buffer and OSAPI_DRV_DLG's task is not fenced; the second is
   the last answer `diskops.inc` reads after a commit. Lifetimes not proved.
6. **`clk_fbuf` (5 `.bss`) into `cp_sbuf`**: `tests/dtfield.py` reads
   `[clk_fbuf]` as "the last field drawn", which a later stage would
   overwrite.
7. **`mod_fpt` as a byte table** (-3 at best, mod.inc's `mod_fpr` grows by
   12 and mega.inc has a copy).
8. **`osapi_seg`'s `test bl, bl` on kern_big** (-1 `.cold`): still no odd
   `.cold` partner ahead of `gfx_blit1_x` (only `osapi_img_name` is there).
9. **`drv_pkg_disp`'s HMA arm by an `add` on the frame** (-1): +12 clocks
   on every heap driver's dispatch.
10. **`vid_ctx_act` as `push cs / pop ds / push cs / pop es`** (-3): +24
    clocks a display activation, per primitive on a dual-display desktop;
    item 15 is the faster -1.
11. **Two-display `osapi_img_name` rows folded into the drv_tab loop**:
    `thmv_row` would then answer THMPAL.DRV's name, which is CF = 1 today.
12. Pass 18-20's refusals in these files still hold and were not
    re-proposed (`snd_town_off` on the KENT ladder, `vid_setmode`'s pops as
    `kret_es`, `drv_load_at` reordered for 0, `xm_release_rec`'s banks).

## WANTS THE OWNER

None. No message, limit, refusal or disk requirement changed.

## WANTS AN ABI BREAK

None found or needed. `tools/abi.lock.json`, `apps/os88api.inc`,
`drivers/os88drv.inc` and the C SDK are untouched; the VXB block, the DRVR
row layout and the FSI table a package reads are unchanged.

## CROSS-FILE

1. **`extmod.inc` (wm): `KDOOR vid_disp_of` x2 -> `EXK vid_disp_of`**, and
   then `rd_tab`'s `RDENT RDK_RS, vid_disp_of` (kernel.asm) goes: -2 `.text`
   big/emu/mega, +4 EXTD.DRV. Its only `KDOOR` sites are those two (listed
   off the assembler on all four kernels).
2. **`hiber.inc` (sys): `KDOOR wm_paint_all` -> HIBER.DRV's `hbg_kgo` hop**,
   and `rd_tab`'s `wm_paint_all` entry goes on KERN_BIG (kern_small has a
   `.cold` site and keeps it): -2 big/emu/mega, +2 HIBER.DRV.
3. **`disk.inc:925` (disk) and `sched.inc:1858` (sys): `KDATAR r` ->
   `KSEGR r`** in `.text`: -1 each on kern_big/emu/small, two clocks faster,
   kern_mega identical (item 15's shape).
4. **`str_len` (clock.inc, mine) has one caller, `toast.inc`'s
   `toast_place` (ui)**: written at the call, -4 every kernel.
5. **`cw_gfx_fill_pat`, `cw_vga_xor_rect_vram` (files.inc) and
   `cw_wm_dmg_hit`, `cw_wm_zone_r` (desk.inc)**: one site each, -1 each
   through `cw_mem_disp` (`mov bp, body`, +3 at the site, -4 the shim) if BP
   is dead at the site and owed to no caller; drawing paths, ~+4 clocks.
6. **`files.inc`'s `fm_brun` (files)**: `call KERNEL_SEG:cw_font_run / ret`
   for `jmp ct_cw_font_run` on kern_big as on kern_small, then
   `%define ct_cw_font_run KERNEL_SEG:cw_font_run` on kern_big and the
   trampoline goes: -1 `.cold`, and both sites skip a near call.
7. **`diskw.inc` (diskw): `dwf_dskw_vstat.bad` is kern_big's `api_refusec`
   now** (item 3) - keep it `mov ax, FERR_NODISK / stc / retf`, writing no
   other register, or give the alias another home.
8. **`winmod.inc` (wm) - a FRAGILITY, not a saving**: WIN95.DRV's `sub dx, 7
   / cmp [di+W_H], dx` assembles as `EA 07 39 55 08`, which `mod_cfix`'s scan
   reads as a far jump naming segment 0x0855. With `COLD_HOME` at exactly
   0x0855, `tools/os88rom.py`'s proof fails `build/coldhma.sys` ("mod_cfix
   would re-point WIN95.DRV wrongly"). This branch passed through that value
   (`.text`+`.bss` 44,449..44,464) and left it; **the merged tree must not
   land there** (it is a property of the sum, so the coordinator sees it at
   the merge if anyone does). No other value from 0x0820 to 0x0860 matches
   in any kernel module image.
9. **`instance.inc`'s `inst_rel_rec` (sys) and `xmem.inc`'s
   `xm_release_rec` (mine)**: both compute `inst_idx` for one teardown and
   `xm_release_rec` has no other caller now; merging them is ~-5 but moves
   the sound and serial releases under a 16-byte-deeper frame on a worker's
   teardown - a stack-class question, so not taken here.

## ROWS (named, not run - BRIEF section 3)

- the API table, the door, the refusal rows: `api-abi` (fast), `api-abi-all`
  (full: all four kernels' DOOR_OWN, item 3), `abilock`, `fat32`,
  `fat32big` (FILE_PLACE on kern_mega);
- font glyphs (item 1): `fonts`, `kbdlayouttransitions` (kern_mega's arm,
  unchanged), `kbdlayoutfont`, `kbdlayouts`, `megafont`, `paintdraw` or any
  Paint text-tool row, `wireballvideo` (copies OSAPI_FONT_GLYPHS);
- boot and kmain (item 2): `bootsmoke`, `smallboot`, `small128`, `bootfence`,
  `bootstatus`, `postboot`, `kzboot`;
- the Control Panel open and the boot driver notice (items 7, 8): `hdauto`
  (reads `[drv_nerr]`), `drvup`, `cpup`, `cppromise`, `cpwide`, `cpnames`,
  `cpnameshdd`, `hddcp`;
- the driver loader and calls (items 8-11): `lzdrv`, `lzdrv-nohint`,
  `drvcall`, `drvclaim`, `drvmem`, `drvmove`, `drvverb`, `drvovl`,
  `heapdrv`, `hmadrv`, `ems`, `socktest`, `ethernet`, `netcoexist`;
- file API stubs (items 4-6): `dosren` (rename), `fdlgchoose`, `fdlgup`,
  `fdlgsmall`, `install` and `hdtake` (OSAPI_FILE_WRITE_SYS), any
  OSAPI_FILE_FIND listing row;
- the clock (items 17, 18): `dtfield`, `dtwrite`, `deskclock`;
- fsx and the speaker door (items 12, 13, 16): `wireball`,
  `wireballvideo`, `wireballmono`, `dispfsx`, `dispfsxherc`, `dispfsxcga`,
  `dispmodex`, `vidmodex`, `pxfsx`, `spkfx`, `vidspk`, `trkspk`, and on
  kern_small any fsx row run there (`fsxclip`, `isotronsmall`);
- dual display (item 15): `dispcheck`, `dispfit`, `dispdrag`, `dualcheck`;
- the gates `make` already ran green at the tip: `hotpar`, `stkbalance`,
  `stkclass`, `ovlchk`, `megaseg` (via `make mega`).

## DEFECTS FOUND

None in behaviour. One build fragility, CROSS-FILE 8: a module's ordinary
instruction bytes can match `mod_cfix`'s far-call pattern for one
`COLD_HOME` value, and `os88rom.py` (correctly) refuses that layout.
