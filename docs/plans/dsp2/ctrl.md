# Driver size pass 2: `ctrl`, CTRL.DRV (the Control Panel's image)

Branch `dsp2-ctrl`, cut from `1b01907f1` (the brief). Agent `ctrl` (BRIEF.md
2) owns every line under `section .modc` and `section .modu`: the settings
core and the compact panel, in `ctrl.inc`, `desksc.inc`, `driver.inc`,
`shutdown.inc`, `sched.inc`, `vidsel.inc`, `wm.inc`, `desk.inc`, `dock.inc`
and `fdlg.inc`. **TAKEN, a file in no row**: `kernel/clockw.inc`, the RTC
write half. It carries no section of its own and is `%include`d only from
`ctrl.inc`'s `.modu`, so every line of it is CTRL.DRV's.

Commits: `4da176e38` (batch 1), `fb4934c7e` (batch 2), `822273428` (batch 3),
then this note. Each batch passed a full `make -j2` (the fast tier, 54 rows).
The tip passed `make -j2 emu` and `make -j2 mega` as well.

## 1. BASE AND TIP

"image" is what the claim holds (MOD_H_IMG, the 213-byte bss tail's zeros
included, SPEC.md 2.8.1). "file" is what the disk carries. CTRL.DRV ships
PLAIN on kern_big, emu and mega, so there image = file. Base is this
worktree's own build at `1b01907f1`. Tip is `822273428`.

| kernel | image base -> tip | file base -> tip | sectors | `MODS_SIZE` (the core's read) | 360KB clusters |
|---|---:|---:|---|---:|---|
| kern_big | 16,733 -> **16,375 (-358)** | 16,733 -> **16,375 (-358)** | 33 -> **32** | 3,328 -> 3,307 (-21; 7 sectors either way) | os8088-360: 33 -> 32, **+1 free** (27 -> 28) |
| kern_emu | 16,751 -> **16,393 (-358)** | 16,751 -> 16,393 (-358) | 33 -> 33 (9 bytes over the 32nd) | 3,329 -> 3,308 (-21) | (no 360KB disk) |
| kern_mega | 16,972 -> **16,609 (-363)** | 16,972 -> 16,609 (-363) | 34 -> **33** | 3,522 -> 3,496 (-26) | (no 360KB disk) |
| kern_small | 6,291 -> **6,171 (-120)** | 5,871 -> **5,781 (-90)** (lz4) | 12 -> 12 | (no core row) | small360: 6 -> 6, +0 |

The bss tail is 213 on the three big kernels and 34 on kern_small, at base
and at tip: no bss byte moved. The only other 360KB disks that changed are
none (`os88diskuse --diff`: os8088-360 +1 free cluster, every other image
+0).

**The resident kernels, cmp -l at ONE commit** (`822273428`, build 447).
The base's six files were checked out over the tip and the four
`kernel.bin` rebuilt with the same targeted command, so both sides have
the same build number and the same KZ placeholders:

| kernel | bytes differing | where | what |
|---|---:|---|---|
| kern_big | 4 | 0x106E2-3, 0x106E5-6 (`mod_need.sized+0x0D`, `.cold`) | `mov ax, MODC_SIZE` 0x415D -> 0x3FF7 and `mov bp, MODS_SIZE` 0x0D00 -> 0x0CEB |
| kern_emu | 4 | 0x107D2-3, 0x107D5-6 (`mod_need.sized+0x0D`) | MODC_SIZE 0x416F -> 0x4009, MODS_SIZE 0x0D01 -> 0x0CEC |
| kern_mega | 5 | 0x1338A-B, 0x1338D (`mod_need.sized+0x0D`) and 0x13470-1 (`mod_hi+0x2C`) | MODC_SIZE 0x424C -> 0x40E1 twice, MODS_SIZE 0x0DC2 -> 0x0DA8 |
| kern_small | **0** | | kern_small has no settings-core row (no OS88_SHORTCUTS), so neither immediate is assembled |

**Every length is the same on all four** (105,456 / 105,808 / 150,737 /
62,384), and no other byte differs. The ruling in BRIEF 1 names MODS_SIZE.
**MODC_SIZE is a second immediate of the same kind, and every CTRL.DRV byte
moves it, `.modu` included.** `mod_need` sizes MOD_SETS's claim from the
whole image's length, and kern_mega's `mod_hi` copies the image above 1MB
by the same constant. So it is a second immediate on kern_big and kern_emu,
and a third on kern_mega. The instruction, its length and every resident
size are unchanged, and the value is the module's own length, so I applied
the ruling to it. It is listed in section 5 too.

## 2. TAKEN

Bytes are kern_big image = file, with emu the same. kern_mega and kern_small
are named where they differ. **Speed**: every item is cycle-neutral or
faster on the path it touches. The one exception is `clk_at_hour`'s 24-hour
arm (item 33), which runs once at the panel's close. Cycle figures are 8088
hand counts (`max(clocks, 4 x bytes)`). **Equivalence** is a recorded
reading of each item: registers, flags and stack in and out, every caller
checked for what it reads afterwards. Every moved entry was checked by
reading, and the module header and `cpg_tab` are unchanged. The LOOK boot
(section 8) opened every page, and the Display item was proved on the
glass (section 3).

### Batch 1 (`4da176e38`): -151 (small -27 image / -24 file, mega -156)

1. **`cp_isdown` folded into its two callers** (-12, KERN_BIG). The routine
   was `cmp al, [cp_down] / ret`. `cp_dngly` now compares BH itself and
   joins `cp_skipset` past its `push ax` (`.id`). `cp_dnbtn` compares AL
   and falls into `cp_skipset`. Each control a page draws saves 2 calls, 2
   returns and a push pair (about 100 cycles). Flags are identical: the
   same compare, and AL = BH.
2. **`cp_gemit` / `cp_bemit`: `shr byte [cp_skip], 1 / jc`** replaces
   `cmp / mov 0 / jne` (-6 each, -12, KERN_BIG). `[cp_skip]` is only ever 0
   or 1 (cp_skipset, now commented). The shift clears it and puts the skip
   in CF. Faster: 21 cycles + 4 bytes against 32 + 10. On the skip path the
   flags differ (CF = 1 where it was 0), and no caller of either routine or
   its wrappers (cp_chk/gnz/rad/gz, cp_btdn) reads a flag afterwards. All
   twenty-two sites were read.
3. **Strings shared inside the image** (-26, kern_big only):
   - `cp_s_vid` = `drvt_vesa + 5`, the tail of 'VESA Display' (-8, VID_EXT);
   - `cp_s_snd` = `drvt_sound`, DRV_TITLES' Sound row (-6, OS88_DRIVERS).
     Since kernel size pass 14 that block is in this image, so the "copy,
     not share" note had stopped applying. DRV_TITLES' comment now says
     that retitling either row retitles the page;
   - `cp_s_tclr` = `cp_s_vfc + 6`, Force Color's 'Color' (-6);
   - `cp_s_vrgt` = `cp_s_kright` (-6, DOCK_OPT).

   The LOOK boot shows all four headings and labels as before.
4. **`cp_v2r`: the driver arm tests before the two pushes** (-2, all
   kernels). It needs neither register, so every driver-page row it maps
   drops a push pair.
5. **`cp_r2v`: one tail** (-4, all). The miss arrives with CF = 0 (from
   `jae`) and goes `mov ch, bh / cmc` into the hit's `mov al, ch / pop / pop
   / ret`. The hit loses its `clc`, because `je` arrives with CF = 0.
   Flags are identical on both paths.
6. **`cp_vid_fcok`: `test / stc / jz / cmp kind, VID_VESA / cmc`** (-3,
   KERN_BIG). VID_VESA is the highest kind, and a `%if VID_KIND_MAX >
   VID_VESA` guard says so. Every path is as fast or faster (VGA: 41 cycles
   against 55). All three callers read only CF.
7. **Button greying by `adc di, 0`** (OS88UI_DIS = 1): `cp_thm_cust_btn` (-2,
   KERN_BIG) and `cp_vid_btn` (-2, all). The branch is gone.
8. **`cp_dock_click` `.change` as `mov ah, al / xchg ah, [dock_cfg] / cmp`**
   (-3, KERN_BIG). On the no-change path it writes the same byte back,
   which nothing can observe. It is 23 cycles where the old path took 39.
9. **Image toasts through `sc_m_say` instead of staging**: the Dock page's
   failure line (-3) and the Keyboard page's 'Keyboard not loaded' (-9,
   kern_big; kern_small keeps its inline toast, having no `sc_m_say`). Same
   text, same CX = 0, and ES:SI is the image's.
10. **`cp_vid_click` `.mode`: a dead `sub al, 2`** went (-2, KERN_BIG).
    `cp_vid_msel` reloads AL.
11. **`cp_wfwd`** (-6, KERN_BIG). The compact path is the same seven
    instructions, reordered. The wide path builds BP from `[cs:bp]` with no
    borrowed SI. It is faster.
12. **`modc_e_gate`: `cmp / cmc / jc .r`** shares the near ops' `retf` (-1).
    The flags at the refusal are the same.
13. **`cpg_none` = `cp_ctl.no`**, the same `stc / ret` (-2). A comment at
    `cp_ctl.no` keeps it two instructions.
14. **`cpg_open`'s face test: `test byte [vid_kind], 0FBh / jnz`** (-4,
    VID_EXT). VGA (0) and VESA (4) are the only bytes with no bit but bit 2,
    and a `%if` guards the two values.
15. **`cpg_drvmem`: `cbw / xchg ax, bx`** (-2): a row is under DRV_MAX.
16. **`cp_ctl`: `.act` needs no `clc`** (-1). Both ways in arrive with CF = 0.
17. **`cp_lrow`: one tail by `cmc`** (-5, DOCK_OPT). It is faster on every
    path, and its one caller reads CF.
18. **`cp_vid_rowok` = `vid_avail_test`** (-4, all). The body was a `call` /
    `ret` (kmod 9's lead).
19. **`cp_vid_slot`: one tail by `cmc`** (-4, all). The hit loses its `clc`
    (-4 cycles a row), the terminator gains a `mov al, bl`, and the paint is
    net faster. Flags are identical.
20. **`cp_vid_vxlabel`'s class decode**: BH is already 0, and the height
    loads straight into BL (-4, VID_EXT).
21. **`cp_vid_vxcall`: `cmp word [seg], 1 / jb`** shares one tail (-4,
    VID_EXT). The loaded path runs the same instructions. A loaded image's
    segment or selector is never 0.
22. **`cp_vid_mode`: the `push ax / pop ax` round `cp_brun` went** (-2).
    cp_run banks AX and cp_black is a store.
23. **`cp_time_click`'s button id as `11 - BL >> 1`** (-3, KERN_BIG; 5 for
    +1, 6 for -1). It is 9 cycles against 15-24.
24. **`cp_time_pick`: the hit's `clc`** went (-1). Two `shr`s of a multiple
    of 4 already leave CF = 0.
25. **`cp_timebtn`: one staging, of the one label** (-3). The '-' button
    used to be staged twice.
26. **`clk_step`: the two wraps to the top are one** (-3). Each path runs the
    same instructions.
27. **`cp_flush_x` (`.modc`): ES = the image set once, and `or bl, bl` for
    `cmp [cp_dsave], 0`** (-5; kern_mega -10, where PUSH_CSDATA is 6 bytes).
28. **`cp_snd_rowok`: `.yes` needs no `clc`** (-1). All three ways in arrive
    with CF = 0.
29. **Shut Down's answer: `.cancel: xor ax, ax / SKIPF2 / .yes: mov al, 1`**
    (-2). The caller reads AL alone, and nothing below reads the skip's
    flags.
30. **`sd_rebuttons`: `jmp sd_disp`** (-2, kmod 9's `shutdown.inc:237`).
31. **`modc_e_sc` dispatches by one pushed return** (-12, OS88_SHORTCUTS).
    `call .op` pushes the return once, and each operation is reached by `jz`
    (`dec ah` counted exactly as before), so every body sees the AH, the
    flags and the stack depth it always had. It is faster: the per-op
    `call` and `jmp short .out` went. A table dispatch would save 32 and is
    REFUSED (section 4).

### Batch 2 (`fb4934c7e`): -124 (small -56 / -40, mega -124)

32. **Page procs bank nothing** (-134 before the two items below). Every
    PAINT and CLICK proc in `cp_items` (all nine pages, plus the Ports
    view's paint and click) is reached only through `cp_item_paint` /
    `cp_item_click`, and both bank every register (`kentm_bp`) round the
    call. So each proc's own `kentm_si` / `kretm_si`, or its push and pop of
    AX or AX/BX, went. Their exits became `ret`, and a call before an exit
    became a jump where that saves bytes: `cp_radios`, `cp_time_rows`,
    `cp_drv_pane`, `cp_drv_boxes`, `cp_snd_note`, `cp_thm_radios`,
    `cp_thm_cust`, `cp_dock_ctls`, `cp_fdcap`, `cp_vid_btn`, `cp_vid_fc`,
    `cp_vid_arr`, `sc_m_say`. Three things this removed:
    - an internal push pair that only restored a register for the caller
      (`cp_time_click`'s field swap);
    - `cp_drv_click`'s BP push round `cp_list`, which banks BP itself;
    - `cp_sched_click`'s `mov al, [sch_coop] / cmp / mov al, ah`: AL is
      already the row's mode.

    Callers checked: the `CP_I_PAINT` / `CP_I_CLICK` words are read only at
    those two sites, no proc is named anywhere else, and no internal label
    is reached from outside. Saves ~240 cycles (one bank) on every page
    paint and every click. A comment at `CP_I_PAINT` states the rule.
33. **The Keyboard page**: the label loop steps DX the way the Sound page's
    does (-3, no push pairs, no `cp_runp` adds a row). `cp_key_dot` takes
    the row top with `lea dx, [bp+CPQ_R0Y]` (-2).
34. **`cp_vid_dots`** (+15, all kernels) - **the speed item** (section 3).

### Batch 3 (`822273428`): -83 (small -37 / -26, mega -83)

35. **Page-only helpers bank nothing either** (-24). `cp_vid_rows` /
    `cp_vid_dots`, `cp_time_rows`, `cp_snd_note` (which tail-jumps into
    `cp_drv_line`) and `cp_drv_line1`. Each one's every caller is a page
    proc, or `cp_tick_x`, which banks for itself, and reads nothing but DI
    and BP afterwards. None of the helpers writes DI or BP. Headers say so.
36. **`cp_drv_mempar` banks nothing** (-5): its one caller is `cp_drv_paint`.
37. **`cp_setdown` runs into `cp_ctlpaint`** (-10). `cp_ctlpaint` is now
    `cp_setdown`'s local `.paint`, and the BX push moved inside. The
    no-change path, which runs per mouse packet on a drag, is the same
    `push / cmp / je / pop / ret`. A press edge saves a call, a return and
    a push pair, and `xchg` writes `[cp_down]`.
38. **Three one-call doors written at their caller**: `cp_drvcall` (-4),
    `cp_schset` (-12) and `cp_drv_arrows` (-12).
    - `cp_schset`: its one caller's AL is already 0 or 1, so the
      normalising went with the call. `sched.inc`'s header says where the
      body is now.
    - `cp_drv_arrows`: its closing `cp_black` was dead, because
      `cp_drv_boxes` -> `cp_drv_box1` sets the pen before anything draws.
39. **`sc_m_cell` (`.modc`): `cmp / cmc / ret`** (-4). ZF and CF are as
    before on both ways out.
40. **`cp_item_paint`: `cp_black` hoisted above the face test** (-5). Wide
    no longer jumps.
41. **Last calls as jumps**: `cp_time_paint`, `cp_thm_paint`,
    `cp_vid_click`'s Activate (-3).
42. **`clockw.inc`**: `clk_ns_bput`'s `call / ret` became a jump (kmod's
    shape, -2). `clk_at_hour`'s 24-hour arm shares the PM tail with BL = 0
    (-5, cold: two instructions once a close, before the RTC's port I/O).

## 3. SPEED

**The compact panel's open.**
- **Disk.** kern_big's CTRL.DRV is 32 sectors where it was 33, and kern_mega's
  33 where it was 34. kern_emu stays at 33, 9 bytes over 32. kern_small's
  packed file stays at 12. The number of `int 13h` CALLS is set by the
  file's runs and track crossings, which this pass did not move. One sector
  fewer is one less sector inside the same read (about 1/9 of a revolution
  on a 360KB XT), not a call. The settings core a desktop gesture reads
  (MODS_SIZE) is 7 sectors at base and at tip.
- **The first paint** (list, divider, selected page): **the same primitive
  calls, base and tip, by reading.** No `gfx_*`, `font_*` or `os88ui_*` call
  is added or removed on any paint path.
- **CPU, per page paint:**
  - one `kentm_si` / `kretm_si` bank fewer (~240 cycles);
  - per control drawn: ~100 cycles from `cp_dngly` and ~20 from
    `cp_gemit`;
  - per driver-page list row: the push pair in `cp_v2r`;
  - per scrolled list row: `cp_lrow`'s tail.

**A page switch** (a list press): the same two `cp_listrow`s and one
`cp_page`, with the bank savings above. **A press or release on a page**:
one bank fewer per click proc, and a press edge's `cp_setdown` saves a call,
a return and a push pair. **The Date/Time tick** (once a second while
shown) runs `cp_tick_x` -> `cp_time_rows`, which is one bank fewer, and the
same seven `font_run`s.

**The Display page's radio click: fewer primitive calls** (item 34). Base
called `cp_vid_rows`, which re-composed the VESA label, then staged and
lettered EVERY adapter row's label with a `font_run`, then drew every glyph
and the Set Primary button. Tip calls `cp_vid_dots`: the same walk with no
label and no composition.

| | base | tip |
|---|---|---|
| radio click, VGA+Hercules (3 rows: 'Vga 640x480', 'Hercules 720x348', 'Cga 640x200') | 3 `font_run` (38 cells, ~34 ms at ~0.9 ms a cell) + 3 glyphs + 1 button | **0 `font_run`** + 3 glyphs + 1 button |
| class cycle on the VESA row (`.same`) | unchanged (its label changes): `cp_vid_rows` | unchanged |

**Proved the same pixels** (the measurement session, MartyPC,
`os8088_xt_vga_herc`, 360KB disks, tip). Open the panel, select Display,
click Hercules's radio, take the panel's rect from the rendered frame.
Then select Sound and Display again (a whole repaint of the page in that
state) and take it again. **0 of 48,622 pixels differ.** The click changed
511 (the dots and Set Primary un-greying). The pointer was moved off the
panel for both captures. Cost: +15 bytes, all four kernels.

**The wide face's forward** (`cp_wfwd`, every paint, click, drag and key
the wide face takes): the compact path is the same instructions. The wide
path drops a push pair and a register shuffle.

Nothing here is on a driver hot path. `cdl_*`, the only driver-facing code
in the image, is a shared macro (section 6) and was not touched.

## 4. REFUSED

Refused for speed. Each is smaller and slower on a path someone waits on
(BRIEF 0.2):

| item | bytes | cost |
|---|---:|---|
| `cp_lvis` as `cmp / cmc / jnc` | -2 | +12 cycles on the common no-scroll path |
| shared skip test for `cp_gemit` / `cp_bemit` (a helper) | -3 | +35 cycles a control |
| a FILE-test helper for `cpg_drvon` / `cpg_drvoff` / `cpg_drvttl` | -4 | +35 cycles a wide Drivers op or row |
| `cpg_drvttl` staging `cp_s_gone` for an empty row | -3 | +80 cycles on empty rows |
| `drv_errstr`'s word table as a NUL-walk | about -15 | up to ~2,000 cycles a status line, a row each Drivers paint |
| `cp_divider`'s four pushes as `kentm_si` | -3 | +100 cycles a full paint |
| `cp_key_sample` as copy-then-pad | -8 | about +500 cycles a keystroke on the Keyboard page |
| a `cp_kl_ff` helper for the three `mov dh, 0xFF / call far kl_control_x` | -4 | +35 cycles an extended key and a close |
| `cp_thm_cust_btn` tail-jumping into `cp_btdn` | -6 | +1 jump a button draw |
| `cpf_vidok`'s VESA arm through `.plain`'s `cmp al, 1` (`sub al, [vx_class] / jmp`), or CLC_OR_STC | -6 / -2 | +17 / +4 cycles on one arm |
| `cp_vid_slot` by SKIPCY1 (superseded by the `cmc` form taken) | -2 | +16 cycles |

Refused for proof:
- **`modc_e_sc` as a word table** (-32 against the -12 taken). The chain
  hands every operation AH counted down (0, but 1 to `sc_m_lnk`), the
  caller's BX and ZF = 1. A table hands it AH = the op and BX = 2 x op.
  `sc_m_lnk` re-reads AX after a pop, and `fm_dgmove` / `sc_m_move` /
  `sc_m_cell` take registers I did not trace end to end, so the
  equivalence is not proved.

Not reached (priced, not taken):
- `cp_drv_memstr` with only DX and DI banked (-1), or written into
  `cp_drv_mem1` (-6; its STKBALANCE-LOOP annotation moves with it);
- `clk_ns_write` / `clk_at_write` as table-driven writes (about -10 each);
- `cp_dock_click`'s `.pset` / `.auto` loads folded into the `xchg` (-2).

## 5. WANTS THE OWNER

1. **The `MODS_SIZE` ruling, used, and its twin `MODC_SIZE`** (section 1).
   - Every `.modc` byte moves the core's read length immediate (`mov bp,
     MODS_SIZE`, `mod_need`).
   - Every CTRL.DRV byte at all moves the whole image's length immediate
     (`mov ax, MODC_SIZE`, `mod_need`, on kern_big, emu and mega), and on
     kern_mega a third (`mod_hi`).
   - The cmp -l in section 1 shows these and nothing else, with every
     length unchanged. kern_small has neither.

   If the ruling is not meant to cover MODC_SIZE, then no CTRL.DRV saving
   can land on the three big kernels at all.
2. Nothing else. No string was reworded, no limit or refusal moved, and
   nothing now needs the system disk. `cp_vid_dots` changes what is drawn
   on a click (fewer calls) and not what is on the glass (0 pixels, section
   3).

## 6. WANTS AN ABI BREAK

None. These are unchanged:
- the module header, the entry table (CP_NENT 13 / 7) and `cpg_tab`
  (CPG_N, every opcode at its word; `cpg_none` is an alias, not a move);
- the layout stamp, `mod_tab`, `cpwlay.inc`, `apps/os88api.inc` and
  `drivers/os88drv.inc`.

## 7. CROSS-FILE

**Code assembled into CTRL.DRV from macros that other images expand too.**
Editing them changes `.boot2`, `.boot3` (resident) or another agent's
module, so none was touched:
- `vid_apply` (VID_APPLY, viddet.inc - the blob and EXTD.DRV too);
- `vid_switch` / `vid_blank` / `vid_disp_init` / `wm_refit` / `dock_apply`
  (KSW_SECT's macros - `.boot3`'s `bvs_` copies);
- `cdl_call` / `cdl_att` / `cdl_publish` / `cdl_hma` (DRV_ATTACH - `.boot3`'s
  `b3` copy);
- `cpc_*` (CFG_DATA - the boot's `ovc_*`);
- `sd_spin` / `sd_rowmk` (OS88_SPINNER - the splash);
- `os88ui_glyph` / `gring` / `gdot` (apps/os88ui.inc, the package SDK).

Two leads among them:
- `cdl_att`'s `.nohwal` and `%1_tier`'s `clc` / `stc` tails have the
  `cmc` shape taken here (a few bytes each, every copy).
- `vid_apply` (235) is the largest routine in the image and was not read
  this pass.

**Comments, 0 bytes:**
- `kernel/apps.inc:135` says `cp_schset` normalises `[sch_coop]`. The
  panel's radio now writes 0 or 1 directly (item 38), and the boot reader
  still normalises, so the claim holds but names a routine that is gone.
- `ctrl.inc`'s `cpg_open` header ("CPWIDE.DAT read") is `cpwshell`'s fold
  to describe once it lands (BRIEF 0.3). It is untouched here.

**Not affected:**
- `DRVM_IMG_*` (`driver.inc`): none moved. CTRL.DRV is a module, not a
  driver.
- The brief's ruling text: section 5.

## 8. ROWS TO RUN

The rows that drive CTRL.DRV's pages, gate, core and shutdown (named from
`tests/suite.py`, not run):

- **the panel's mechanism:** `cpup`, `btncp`, `btnall`, `cplistrow`,
  `cpnames`, `cpnameshdd`, `cppromise`, `cpwide`, `drvscroll`, `drvup`,
  `drvcall`, `drvmove`, `ethcfg`, `fddpage`, `dtfield`, `dtwrite`,
  `kbdsettings`, `kbdsettings-small`, `kbdlayoutlegacy`, `covoxcp`,
  `vidspkcp`, `vesacp`, `vesakbd`, `vesashut`, `colorpresets`, `vgacolor`,
  `thm95`, `dispthm`, `dockpos`, `dockmodule`, `extdmod`, `shutdown`,
  `cfgtrip`;
- **the settings core and desktop gestures:** `desksc`, `deskitem`,
  `deskdrag`, `deskkeys`, `desksmall`, `stikshort`;
- **the module mechanics:** `modcache`, `moddrop`, `megamodcache`,
  `romnodisk`, `rombig`, `romsmall`, `hmacold`, `coldslide`.

The fast tier (54 rows, `api-abi`, `hotpar`, `stkbalance`, `ovlchk` among
them) ran green at each batch and at the tip.

The wider list of rows that open the Control Panel for some setting is
186 names (grep of `tests/*.py` for the panel's title and symbols). The
union above is the set whose subject is the panel itself.

## 9. LOOKED

One boot: MartyPC `os8088_xt_vga_herc` (VGA + Hercules, so the Display page
shows), tip 360KB disks.
- Opened the compact panel and selected all nine static pages in turn.
- Every page draws as it did: the headings shared with DRV_TITLES
  ('Display', 'Sound') and the shared 'Color' / 'Right' labels included.
- Clicked Hercules's radio on the Display page: the dot moved, Set Primary
  un-greyed, and the labels stayed.
- The panel was still up at the end.

The same session took section 3's pixel comparison.

## 10. DEFECTS FOUND

1. **The Display page's radio click re-lettered every adapter label**
   (PERFORMANCE.md rule 1: a repaint of more than changed). Three
   `font_run`s, about 34 ms on the XT, on every such click, for pixels that
   did not change. **Fixed** (item 34, +15 bytes; the glass proved
   unchanged).
2. **A dead store** in `cp_vid_click` (`sub al, 2` before `cp_vid_msel`).
   Not a misbehaviour. Removed.
3. **The brief's ruling names one immediate where there are two (three on
   kern_mega)**. Section 5. Not a code defect, but the next pass's rule
   should say it.
