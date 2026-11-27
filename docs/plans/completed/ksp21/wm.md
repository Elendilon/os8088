# ksp21 agent "wm" - the window manager, its modules' resident halves, and the kernel's os88ui.inc

Kernel size pass 21 (`docs/plans/completed/ksp21/BRIEF.md`), section 2's `wm` row:
`wm.inc`, `winmod.inc`, `extmod.inc`, `deskmod.inc`, `spinner.inc` and the
kernel's use of `apps/os88ui.inc`. Branch `ksp21-wm`, base `3fc4e9d09` (the
brief, on `dbc5ef8b4`). Figures are ASSEMBLED, `tools/kernsize.py --json`
absolutes on each kernel's own build; resident = `.text` + `.bss` + `.cold` +
`.lowbss` + `.vgabuf` + `.vga` (+ `.mega`). Per-routine figures are
`tools/os88rdiff.py kernel 3fc4e9d09 .` (and `-D KERN_SMALL`).

`spinner.inc` is the loading screen's and assembles into `.boot2` alone (the
blob), so it holds no resident byte and was not a target. `winmod.inc`'s,
`deskmod.inc`'s and `extmod.inc`'s resident halves (the `thv` doors,
`thf_apply`, `osapi_wm_desk_x`/`desk_need`/`desk_drop_x`, the EXFP slots)
were read and are at their floor in this file; the slot merge they suggest
is CROSS-FILE 6.

## BASE AND TIP

| kernel | base (`3fc4e9d09`) | tip | delta | where |
|---|---:|---:|---:|---|
| **kern_big** | 90,225 | **90,133** | **-92** | `.text` 39,510 -> 39,476 (-34), `.bss` 4,973 -> 4,953 (-20), `.cold` 37,830 -> 37,792 (-38) |
| **kern_small** | 55,672 | **55,574** | **-98** | `.text` 29,101 -> 29,031 (-70), `.bss` 2,843 -> 2,823 (-20), `.cold` 20,860 -> 20,852 (-8) |
| kern_emu | 90,471 | **90,379** | -92 | as kern_big (`.text` 39,756 -> 39,722) |
| kern_mega | 134,293 | **134,201** | -92 | `.text` 45,275 -> 45,241, `.bss` 5,204 -> 5,184, `.cold` 53,078 -> 53,040; `.mega` 24,800 unchanged; conventional sections 56,415 -> 56,361 (-54); footprint 61,952 of 68,096, unchanged |
| CTRL.DRV, FDLG.DRV (kern_small) | | | -24 each | disk bytes: os88ui_kbtn's two expansions (TAKEN 25) |

Both `.text` totals include 20 bytes MOVED from `.bss` (TAKEN 25), so the
code itself is kern_big -54 `.text`, kern_small -90. No `KERN_SIZE` rung
moved on any kernel. **Every package image is byte-identical** (md5 of every
`build/*.o88` against the seeded base; the three that differ - `inputchk`,
`syscheck`, `snddiag` - embed the build number or the kernel's manifest).
`tools/abi.lock.json`, `apps/os88api.inc`, `drivers/os88drv.inc` and the C
SDK are untouched; every `os88ui.inc` edit is inside `OS88UI_KERNEL`.

Gates at the tip (`955f21066`): `make -j2` (fast tier 54 passed, 4 skipped
for cc/pagedesk; `hotpar` green on both gated kernels), `make -j2 small`,
`make -j2 emu`, `make -j2 mega`. `tools/stkbalance.py` over `kernel/*.inc`,
`kernel.asm` and `apps/os88ui.inc` (the kernel corpus plus the shared
include): 0 unbalanced paths at the base and at the tip; `stkapps` (the
package corpus, which walks `os88ui.inc`'s package arm) green in the fast
tier. Knob builds assembled at the tip with `kernsize`: `NOFLUSHR`,
`REDRAWFULL`, `ANIMOFF` on both kernels, `SNAPAUDIT` on kern_big;
`SNAPAUDIT` on kern_small fails guard 1b at the base too (DEFECTS).

## TAKEN

Bytes are kern_big / kern_small; kern_emu and kern_mega = kern_big. Every
item is byte-identical behaviour.

| # | item | big / small | speed |
|---|---|---:|---|
| 1 | `wm_su_flay`: the second `xor ah, ah` (after `sub bp, ax`, which writes BP alone) | -2 / -2 | an instruction fewer per banded flay |
| 2 | `[wm_zn]` as `mov al, [wm_zn] / cbw / xchg ax, cx` for `mov ch, 0 / mov cl, [wm_zn]` (the A0 load) in `wm_top`, `wm_occl_w`, `wm_su_precover`, `wm_zabove` (taken BEFORE `wm_ptr2idx`, which keeps CX) and kern_small's `wm_dock_clear` | -4 / -5 | ~3 clocks and a byte of fetch faster each |
| 3 | `wm_band`: `cbw` for `xor ah, ah` (AL <= 3, the `ja` above) - pass 20's held lead | -1 / -1 | faster |
| 4 | `wm_minsize` FALLS INTO `wm_apply_wh`: its `jmp` assembled EB 00 | -2 / -2 | a jump fewer |
| 5 | `wm_apply_wh` (kern_big): `jnc wm_apply_out` for `jc .one / jmp short wm_apply_out` | -2 / 0 | faster on both answers: one display (CF = 1) falls through, 4 clocks where a taken `jc` was 16; an extended desktop takes the `jnc`, 16 where 4 + a 15-clock `jmp` stood |
| 6 | kern_small `wm_show_b`: `jmp short .raise` is WM_ANIM's alone (EB 00 without it) | 0 / -2 | a jump fewer |
| 7 | kern_small `wm_zone_r` falls into `wm_clip_clear` (EB 00) | 0 / -2 | a jump fewer |
| 8 | kern_small `wm_paint_dmg`'s dock force: the rect is STILL in AX..DX at `.fill` (`desk_dmg_zones_x`, `wm_dmg_gray` and `desk_paint_mask_x` keep BX..DX, AX is the reload) - `cmp dx, [vid_dock_y0]` and the call, where it reloaded three words | 0 / -10 | three memory loads fewer per damage pass |
| 9 | `wm_close_req`: the slot's bit through `wm_dmg_bit` (BX and CX kept), not its own shift | -4 / -4 | ~+45 clocks per close request (an API a package calls to close itself) |
| 10 | `wm_lf_pad`, kern_big's parity byte, goes: this file's kern_big total came out odd alone | -1 / 0 | parity |
| 11 | `os88ui.inc`'s kernel `.cold` arm banks with `call kentc_bp` (`UI_KENT bp`, UI_KRET's other half, its name BUILT for stkbalance's reason): `os88ui_btn` (kern_big; kern_small's is in two images), `os88ui_sbar`, `os88ui_sbmove` | -12 / -8 | ~+100 clocks a control draw of 4 to 15 drawing calls (3 to 11 ms on the 5150): under 1% (kernel.asm's kent_* rule: per control, never per glyph) |
| 12 | kern_small `wm_dmg_bands`: DOCK_OPT's `%else` arm is KERN_SMALL's alone (DOCK_OPT is KERN_BIG), so its display walk ran ONCE - written straight: no index, no `or si, si` twice, no banks round two calls, SI as the dock-ceiling scratch the contract already clobbers | 0 / -19 | the loop's overhead and four stack operations gone, up to three calls per damage pass |
| 13 | `wm_draw_shadow`: the bottom edge's x2 and y are the vertical's AX and DX, which `gfx_vline` (clobbers flags only) and `wm_flush` keep - an `xchg` where four loads stood | -12 / -12 | four memory loads fewer per shadow |
| 14 | `wm_draw_win .frame2`: SI is dead from `.chrome` to `.paint` (which loads it; the partial-raise arm spends it too), so y2 waits in SI and neither SI nor DI is banked. NOFLUSHR's knob vline reworked to match (assembled) | -6 / -6 | four stack operations fewer per flush-framed window |
| 15 | `wm_title_set`: one `wm_clip_clear` for both exits - it writes no flag (its header), so CF is still the answer to branch on | -3 / -3 | the same calls on both paths |
| 16 | `wm_su_rect`: y2 off y1 (`mov dx, bx / add dx, [di+W_H] / sub dx, TITLE_H + 2`), not a second load of W_Y | -1 / -1 | a register move under a load |
| 17 | `wm_destroy`: the deferred-close bit through `wm_dmg_bit` and `not`, the index after by a second `wm_ptr2idx` | -2 / -2 | ~+140 clocks per window DESTROYED (a second `div`), against a damage repaint of 100+ ms |
| 18 | `wm_dmg_wins`' shadow arm: SI (the walk's index) survives `wm_chrome_clip`, `thm_ink`, `wm_draw_shadow` and `wm_clip_clear` unbanked | -2 / -2 | ~27 clocks per shadow-owed window |
| 19 | kern_small `wm_hit`: the three box answers share one `jmp .out` through two `test ax, imm16` skips (`%if`-asserted three bytes apart; no caller reads a flag) | 0 / -2 | the minimize answer ~4 clocks faster, the close box's ~+12 (a taken `jbe`) - per click or hover over a box |
| 20 | kern_small `wm_draw_title`: the chromeless early-out leaves by `wm_znext`'s bare `ret` (`wm_znext.ret`, ~80 bytes back) where `.none` was 160 on (a relaxed 5-byte jump); SNAPAUDIT keeps `.none`, whose restore it needs | 0 / -3 | the same |
| 21 | `wm_fullscreen`: BP and DI banked once for the save AND the raise (nothing between reads DI; `wm_top_dbp` writes it first) | -2 / -2 | two stack operations fewer |
| 22 | `wm_ttl_rect`: `lea dx, [bx+TITLE_H-1]` for `mov` + `add` (no caller reads the flag) | -2 / -2 | faster |
| 23 | `wm_chrome_rect_x` (kern_big `.cold`): `lea dx, [bx+13]` | -2 / 0 | faster |
| 24 | `wm_rz_bank` beside `wm_nat_bank`, jumping short into its tail (`call wm_bank4 / pop di / ret`); its header stays with `wm_rz_paint`'s and says where the body went | -3 / -3 | ~+15 clocks per resize or zoom |
| 25 | **`os88ui_krec`, the kernel's button record, ASSEMBLED.** Its LABELS, FLAGS, N = 1 and DOWN = 0 are written by nothing in the kernel but `os88ui_kbtn`, always the same four words: the record's writers (`os88ui_btninit`, `_btnpress`, `_btndrag`, `_btnup`) are `%ifndef OS88UI_KERNEL`. So the record and its label/flag words (all DS-addressed) are `.text` words with those four preset (`%if`-bound to the `OS88UI_BT_*` offsets), and `os88ui_kbtn` stores RECTS, the label and the flags only. SPEC.md 38's sentence on where the staging record lives follows | -24 `.cold` / 0 (both: `.bss` -20, `.text` +20; kern_small's two module copies -24 each) | four stores fewer per kernel button |
| 26 | `wm_pkgcall`: the W_FLAGS+1 read, the W_SEG test and the DS load carry no `es:` byte - DS is the kernel's until that load (the `mov [gfx_mono1], al` between already says so) | -3 / -3 | three prefix fetches fewer on every package callback |
| 27 | `wm_draw_title`'s stripe inset: `mov bx, [di+W_X] / lea ax, [bx+3]` | -2 / -2 | faster |
| | **total** | **-92 / -98** | |

### Speed and the speed rule

No routine on `t_hotpar.py`'s lists changed a byte, and `hotpar` is green at
every commit on both gated kernels with no pad added (one removed: TAKEN 10).
`wm_paint_dmg` and `wm_paint_all` are byte-identical on kern_big (TAKEN 8 is
kern_small's arm). The khp1-sped routines this touches - `wm_draw_win`
(wm-1, wm-7), `wm_raise`, `wm_dmg_stale`'s callers - only lose instructions
on their paths; the few items that add clocks are H3/H4 and under 1% of the
named operation (items 9, 11, 17, 19, 24, each with its figure above). Items
whose cost would land on a path a speed commit sped up are WANTS THE OWNER
1 and 2, not taken.

The unpinned code between the hot routines now sits at odd shifts in places
(`wm_dmg_wins`, `wm_draw_win`, `wm_su_flay` and others on both kernels -
rdiff's shift runs): a cost on an 8086/V20/286 bus, none on the 5150's 8088,
as pass 20's record says of its own. `dsk_img16`'s self-adjusting `align 2`
is not engaged: this file's `.text` total is even on both kernels.

**No `int 13h` call changed**: nothing here is on the mount, listing,
read-ahead, FAT-window, directory-write or loader path.

## REFUSED

1. **`wm_ptr2idx` as `lea ax, [bx-wm_wins]`** (-1): does not assemble - nasm
   refuses a NEGATED section label in an effective address ("impossible
   segment base multiplier"). The same holds for every CROSS-FILE 3 lead that
   subtracts a label (`inst_tab`, `dsk_vtab`, `font_rn_tab`, ...).
2. **`wm_draw_win`'s six pushes as `call kent_di`** (-3): khp1 sped it up
   (wm-1, wm-7) and ~+95 clocks per window drawn is not cycle-neutral there.
3. **`wm_su_take` / `wm_su_try` as `kent_di` + `push es`** (-3 each): the
   raise cache, S3, held by the owner for cycles (LAST-DROP-BYTES 7.10).
4. **kern_big `wm_dock_clear`'s zero-extend** (TAKEN 2's form): its `xor ch,
   ch` also gives `jcxz .out` CF = 0 (an empty z-order is "clear"), so `cbw`
   costs a `clc` back: 0.
5. **kern_big `wm_draw_title_b`'s relaxed early-out** (`jnz .none`, 5
   bytes): its `.none` is `jmp wm_chrome_relit`, no copy of which is in
   short reach; a second copy ahead of the routine costs what the jcc saves.
6. **`wm_nest_pop` through an index** (`mov bx, wm_pkgd / ... inc bx / dec
   byte [bx]`, -2 `.cold`): +~25 clocks on every package callback's return.
7. **`os88ui_sbthdraw`'s `add ax, 2` / `sub cx, 2` as inc/dec pairs under
   `OS88UI_KERNEL`** (-2 `.cold`): khp1 refused it as shared source; a
   kernel-only arm doubles the text for two bytes and +1 clock a pair on a
   286. `os88ui_sbpos`'s second `[bx+8] - [bx+10]` (-1) likewise.
8. **`wm_clip_rect` (kern_small) and `wm_clip_subl` (kern_big)
   restructured**: no shape found that is smaller without a jump back or a
   write to the window record.
9. **`wm_an_setw` by `stosw`** (-3): `wm_an_open` reads DI after it ("DI is
   still wm_an_d").
10. **`wm_fs_drop` without its SI/DI bank**: `wm_hide_b` holds SI across it,
    and `wm_fullscreen` promises every register.
11. Pass 18-20's refusals were not re-proposed (`wm_su_try`'s `wm_cpy4`
    copies, the S2/S3 rect helper sets, `wm_draw_win` billing, `W_DISP`,
    `[menu_ent]` - the ui agent's).

## WANTS THE OWNER

1. **`wm_paint_dmg`'s no-force flag as an indirect call** (-3 kern_big,
   kern_emu, kern_mega; 0 kern_small). `wm_paint_dmg`'s entry loads BP =
   `dock_force_r`, `wm_paint_all`'s BP = `kret_ret` (a bare `ret`), and
   `.fill`'s `or bp, bp / jnz .dock / call dock_force_r` becomes `call bp`:
   11 bytes -> 8. Every damage pass gets ~10-20 clocks faster; every
   WHOLE-DESKTOP pass gets ~+22 (a `call` and a `ret` where an `or` and a
   taken `jnz` stood) - 0.0008% of a CGA fullscreen exit, but that path is
   the one the flag's own speed commit (since `c0eedd5f4`) bought, and the
   speed rule asks it to stay cycle-neutral. Priced from the listing (the
   clocks by the 8088's table), not built.
2. **`wm_su_flay`'s `.clamp2` as a two-pass loop** (`mov cx, 2 / ... /
   loop`; CX is dead there, -5 both kernels): ~+58 clocks per flay, S3.
3. Not a size item: SPEC.md 11.91.7 says kern_small still rebuilds every
   tile of the strip on a whole-desktop pass because "the six bytes did not
   fit". This pass is -98 on kern_small and TAKEN 8 left that arm at 9
   bytes; the 6-byte no-force flag is the owner's to revisit.

## WANTS AN ABI BREAK

None. Nothing here moved `apps/os88api.inc`, `drivers/os88drv.inc`, the C
SDK or any `OSAPI_*` contract (`wm_close_req`, OSAPI_WM_CLOSE's body, keeps
every register).

## CROSS-FILE

Leads found by scanning the WHOLE kernel listing for the shapes this file
yielded. Each is a few bytes; each wants its own owner's read of the flags
and labels around it.

1. **A jump to the very next byte** (EB 00 - an `%ifdef` emptied what it
   jumped over), -2 each: `icons.inc:575` `jmp short ico_bbpass` (draw;
   both kernels, `.cold`), `desk.inc:1311` `jmp short .out` (desk;
   kern_small - `.drag` is empty without OS88_SHORTCUTS). In module images
   (disk bytes only): `diskops.inc:2224` (diskw), `fsck.inc:2395` (disk),
   `ctrl.inc:1545` and `ctrl.inc:2288`'s `jc .static` (hw; kern_small).
2. **`jcc +2 / jmp short X`** - the inverted jcc to X, -2 each and faster
   both ways, if no label sits on the `jmp`: `clock.inc:621` (hw - its
   comment says "reach either way"), `memory.inc:4929` (sys),
   `disk.inc:12350`, `12486` (disk), `diskw.inc:1706`, `4798`,
   `diskmut.inc:185`, `compress.inc:2458`, `2669`, `diskops.inc:684`, `2508`
   (diskw), `driver.inc:2458`, `6485` (hw), `font.inc:2145` (input),
   `filecp.inc:2549` (desk), `stikmenu.inc:1272` (desk, module),
   `fsck.inc:1543` (disk, module), `vga12.inc:6369` (draw - "NEAR" on
   purpose there; check why).
3. **`mov r, base / add|sub r, imm` as `lea r, [base+imm]`** (-2; -1 where r
   is AX, whose imm form is short; a flag read after the add forbids it; a
   NEGATED label does not assemble, REFUSED 1): `font.inc:1528` (`mov si,
   bx / sub si, 4`), `mod.inc:889` (`mov cx, bp / sub cx, 4`),
   `lzfilt.inc:54` (`mov cx, di / sub cx, 2`), `compress.inc:574`, `631`
   (`mov cx, di / add cx, 8`), `836`, `dock.inc:963`/`967` (`mov dx, bx /
   add dx, DOCK_TILE_H-1`; 963 also loads-and-copies), `serial.inc:315`,
   `drvvol.inc:5057`, and in module images `dockmod.inc:980`, `1080`,
   `fsck.inc:724`, `2707`, and the `cpw*.inc` family (~25 sites, hw).
4. **`files.inc:2884`** `mov ch, 0 / mov cl, [wm_zn]` -> `mov al, [wm_zn] /
   cbw / xchg ax, cx` (-1) where AX is free. `keyboard.inc:542` is the same
   load but bounds a byte an IRQ reads, so `cbw` is NOT equivalent there.
5. **`viddet.inc:719`** `push ax / mov ax, 0x0101 / mov [vid_mono], ax /
   pop ax` -> `mov word [vid_mono], 0x0101` (-2, hw).
6. **EXTD.DRV's slots** (`kernel.asm`'s `EXT_*` table, hw's, and
   `extmod.inc`): EXT_STRADS and EXT_APPLY both start with `wm_strads` and
   have one site each; one entry taking CF as the selector (`stc` / `clc`
   at the two sites, one byte each; mod_gone's CF = 1 at rest is the right
   answer for both) frees a 4-byte `.bss` slot: -2 resident. Not built - it
   moves `kernel.asm`'s table.
7. **`fdlg.inc:1344`'s comment** ("os88ui_krect and the staging record stay
   in `.bss`") is stale after TAKEN 25 (desk's file; SPEC.md 38 is updated).

## ROWS (named; none run - BRIEF section 3)

| rows | what of this pass they reach |
|---|---|
| `deskbench`, `dmgcull`, `paintcull`, `deskwhole`, `zonedmg`, `tmdmg`, `tmrepair`, `paintsu`, `deskclip`, `deskflash`, `wmchrome`, `chromesites` | the damage pass's windows: `wm_dmg_wins`' shadow arm, `wm_draw_shadow`, `wm_draw_win .frame2`, `wm_su_flay`, `wm_su_rect`, `wm_su_precover`, `wm_occl_w`, `wm_top` |
| `deskclipsmall`, `desksmall`, `dispclose-small`, `paintdocksmall`, `paint1small`, `paintgrowsmall`, `tmsmall`, `smallboot`, `smalllaunch`, `small128` (full) | kern_small's straight `wm_dmg_bands`, its dock force off the registers, `wm_zone_r`, `wm_hit`, `wm_draw_title`, `wm_show_b`, `wm_dock_clear` |
| `dispdrag`, `dispsize`, `dispzoom`, `deskzoom`, `zoomsave`, `paintrz`, `sizesnap`, `dispfit`, `dispseam`, `dispstrad`, `extdmod`, `dualcheck` | `wm_rz_bank`, `wm_apply_wh`'s `jnc` (a straddling window on a second display), `wm_minsize`, the flush frame |
| `dispfsx`, `dispfsxcga`, `dispfsxherc`, `fsxclip`, `win1bpp` | `wm_fullscreen` |
| `dispclose`, `deskclose`, `stikmenu`, `wsequnclosed` | `wm_destroy`'s bit, `wm_close_req` (OSAPI_WM_CLOSE and the Sticky Apps close) |
| `disptitle`, `sheettitle`, `int0sweep` (its IBM-ROM half may SKIP here) | `wm_title_set`'s one disarm, `wm_ttl_rect`'s `lea` (int0sweep's own reason: wm_ttl_rect and wm_ptr2idx's divide) |
| `alertbtn`, `btngesture`, `deskhover`, `deskhovercga`, `deskhoverherc`, `uilat` | `wm_hit` (kern_small's arm), `wm_draw_title`'s stripes and early-out, `wm_chrome_rect_x` |
| `sbar`, `sbardlg`, `fmthumb`, `fdlgchoose`, `fdlggrey`, `fdlgsmall`, `fdlgchsmall`, `btncp`, `btnall`, `fmbtn`, `cpup`, `cpcost`, `cppromise`, `shutdown`, `hibernate` | `os88ui_sbar` / `_sbmove` / `_btn` on `kentc_bp`, `os88ui_kbtn` on the assembled record (the file dialog, the Disk window's header buttons, the Control Panel, the shutdown card, the hibernate dialog) |
| `dispapp`, `dispapps`, `dispband` | `wm_pkgcall` through DS on every package callback; `wm_band`'s `cbw` |
| `gfxclob` | `wm_draw_shadow` and `.frame2` lean on `gfx_vline` and `gfx_hline` clobbering flags alone |
| `stkbalance`, `stkapps`, `hotpar`, `swallow`, `api-abi` (fast; green at the tip) | the banks, `UI_KENT`, parity, the `test ax, imm16` skips, OSAPI_WM_CLOSE's cell |

## DEFECTS FOUND

* None in this pass's code.
* Observed, not mine: a kern_small `SNAPAUDIT=1` knob build fails guard 1b
  (the 70.5KB heap lock) at the base `3fc4e9d09` as at the tip - the knob's
  audit code is bigger than the slack under the lock. Whoever owns the
  buildmatrix's knob list should know it cannot build that arm.
