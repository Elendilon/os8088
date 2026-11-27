# ksp21 agent "ui" - the UI task, the menu bar, the progress widget, the Dock's basic half, the toast

Kernel size pass 21 (`docs/plans/completed/ksp21/BRIEF.md`), section 2's `ui` row:
`ui.inc`, `menu.inc`, `fprog.inc`, `dock.inc`, `dockmod.inc` and `toast.inc`.
Branch `ksp21-ui`, base `3fc4e9d09` (the brief). Figures are ASSEMBLED,
`tools/kernsize.py --json` absolutes on each kernel's own build tree;
resident = `.text` + `.bss` + `.cold` + `.lowbss` + `.vgabuf` + `.vga`
(+ `.mega`). Per-routine figures are `tools/os88rdiff.py kernel 3fc4e9d09 .`
(and `-D KERN_SMALL --build build/smallk`).

## BASE AND TIP

| kernel | base (`3fc4e9d09`) | tip | delta | where |
|---|---:|---:|---:|---|
| **kern_big** | 90,225 | **90,113** | **-112** | `.text` 39,510 -> 39,400 (-110), `.bss` 4,973 -> 4,971 (-2) |
| **kern_small** | 55,672 | **55,568** | **-104** | `.text` 29,101 -> 28,999 (-102), `.bss` 2,843 -> 2,841 (-2) |
| kern_emu | 90,471 | **90,359** | **-112** | `.text` 39,756 -> 39,646, `.bss` -2 |
| kern_mega (`.mega` 24,800, unchanged) | 134,293 | **134,181** | **-112** | `.text` 45,275 -> 45,165, `.bss` 5,204 -> 5,202; conventional sections 56,415 -> 56,303; footprint 61,952 of 68,096, unchanged |

`.cold`, `.lowbss`, `.vgabuf`, `.vga`, `.boot2`, `.ovl` and `.mega` are
unchanged on every kernel; no package and no module image moved a byte of
source (`dockmod.inc` is untouched). `KERN_SIZE` is unchanged (95,744 /
57,344 / 95,744; mega conventional 61,952). The `accrued` lines: kern_big
113/512 -> **1/512**, kern_small 376/512 -> 272/512.

`make -j2` (kern_big + the fast tier, 54 passed, `hotpar` green on both gated
kernels), `make -j2 small`, `make -j2 emu` and `make -j2 mega` build at the
tip. `tools/stkbalance.py` (the whole corpus) reports 96 unbalanced paths at
the tip against 98 at the base: the two gone are db_draw_tile's and
menu_inval's own pop runs (both on the `kent_di` ladder now), and none is
new. `python3 tools/os88ovlchk.py` and `checkdocs` pass.

## TAKEN

Bytes are kern_big / kern_small (kern_emu and kern_mega = kern_big). Every
item is byte-identical behaviour unless its row says otherwise.

### 1. `[menu_ent]` goes, `[menu_cell]` is stored once (`menu.inc`) - -9 / -9 (-7 `.text`, -2 `.bss`)

Pass 20's REFUSED 1, taken with the instruments moved. `menu_track` counts the
bar cell UP in DI (`xor di, di` / `inc di` / `cmp di, [menu_nbar]`) and stores
`[menu_cell]` ONCE at `.found` (`xchg ax, di` / `mov [menu_cell], al`), where
it was zeroed at the top and `inc byte`d in memory past every miss; the
`mov [menu_ent], bp` that stood at `.found` for the instruments alone, and its
word, go.

**The instruments.** No package, driver or `tools/` reader names `menu_ent`
(grepped: the kernel, `apps/`, `drivers/`, `tools/`, `tests/`); `a2uilat` is
`build/a2uilat.py`, an untracked script. `tests/uilat.py` (and `weavelat.py`,
which calls `uilat.click_latency`) now stop their memory breakpoint on
`menu_cell`: a MartyPC `mem` breakpoint fires on ANY data access
(`biu_bus_begin`'s `MEM_BPA_BIT` test), and nothing touches `[menu_cell]`
between the press being queued and that store - its only other access is
`menu_track`'s own read after the drop. The new stop is one instruction from
the old one, so SPEC.md 7.3's figures carry over; SPEC.md 7.3 and
APPLE2-SPEC say so. The pre-press `m.write(menu_ent, 0)` went (a write-zero
was meaningless to an any-access breakpoint, and on cell 0 it would be
harmless anyway). `tests/hdboot.py` and `tools/os88ui.py`'s `menu_pick` read
`[menu_cell]` after a drop, which the store still serves exactly; a press in
the dead zone now leaves the previous press's cell where it used to leave the
miss count, and hdboot's failure TEXT says so (its logic is unchanged).

### 2. Shared tails and dead banks

| item | file | big / small |
|---|---|---:|
| `menu_drop` leaves through `menu_track.out` (`pop es` / `jmp`: the five pops and `ret` are that frame's, in its order - `menu_popup` already left that way) | menu.inc | -3 / -3 |
| `ui_cmd`'s CMD_CTRL is `ui_clkcell.open`, the clock cell's own `call COLD_SEG:cpf_cp_open` / `ret`; `.ctrl` went, and `ui_clkcell` exists on every kernel (kern_small's `.clock_cell` inline copy became the same `call ui_clkcell` / `jmp .yj1` as kern_big's) | ui.inc | -6 / -2 |
| `toast_owner_gone` jumps into `toast_kill.body` under its own `pushf` / `cli` on a match - toast_kill's `popf` / `ret` is its exit; the `pop ax` writes no flag | toast.inc | -3 / -3 |
| `toast_say` indexes through SI (`xchg ax, si`, `mov si, [bx+si]`) and never writes BX, so BX is not banked | toast.inc | -3 / -3 |
| `menu_widest` banks no SI: menu_track never reads SI again (its frame banks it) and menu_popup loads SI before it reads it; CX/DX, menu_popup's anchor, stay banked | menu.inc | -2 / -2 |
| `menu_relayout`'s cell loop banks no CX (`font_width_x` keeps it, the string moves take none): the `push`/`pop`, the `db 0xA8` over `.full`'s `pop cx`, and the `pop` itself | menu.inc | -4 / -4 |
| `menu_bt_raw` (`menu_bar_text` / `menu_bar_clock` / `menu_bt_ent`) banks ES alone: menu_draw_bar banks every register itself, the UI task's clock step holds nothing (and on a sound-card kernel `toast_place` in menu_bt_ent already spent AX..DI there), and `menu_sound` now banks the DX it reads after `menu_bar_text` (+2 on kern_big) | menu.inc | -3 / -5 |
| `menu_sound`'s BP bank was dead: `drv_pkg_call_x` pops the BP it borrows, menu_relayout/menu_bar_text bank it, nothing else writes it (ES stays banked: the SOUND.DRV verb may leave its own) | menu.inc | -2 / 0 |

### 3. Registers that already hold the value

| item | file | big / small |
|---|---|---:|
| `menu_draw_bar`'s rule reuses the field's registers: `gfx_fill` and `thm_ink` keep every one, so `xor ax, ax` / `mov bx, [vid_pwm1]` / `mov dx, MBAR_H - 1` are `mov bx, cx` / `inc dx` | menu.inc | -6 / -6 |
| ...and the logo's notch is `mov bl` (BH = 0 from the body's y; `%error` guards that every logo coordinate fits a byte) | menu.inc | -1 / -1 |
| `ui_drag_xor` loads the outline through `rect_get` (`ui_curx..ui_dragh` are four adjacent words) - +~99 cycles a draw, twice a tick-long drag pass: under 0.1% of it | ui.inc | -10 / -10 |
| `ui_grow`'s vacated rect through `rect_get` of `ui_origx..ui_cury` and two `xchg`s - once a grow | ui.inc | -7 / -7 |
| `ui_track` stores the window and the press point by STOSW, landing DI on `ui_origx` (an `%if` pins `ui_dragwin`/`ui_startx`/`ui_starty` in front of it); CX/DX are spent, which the loop never needed (it reads `[ui_startx]`) | ui.inc | -5 / -5 |
| `ui_tdbl` takes the delta first and adds it back (`add [ui_tclkt], ax` = THIS press's tick) where `.first` reloaded and stored | ui.inc | -2 / -2 |
| `ui_lit_go` loads `[ui_armr]` once into AH and tests it there - it was compared in memory and loaded again for THV_CRECT | ui.inc | -3 / 0 |
| `ui_sys_open`'s running-instance compare reads the record through `[bx+si-1]` (BX = its name less ours), so DI is never walked or banked and `.nomatch` goes | ui.inc | -3 / -3 |
| `menu_bemit` banks and clears the spare cell in one `mov al, 0` / `xchg` (no flag written, so the caller's CF reaches its `pushf`) | menu.inc | -3 / -3 |
| `fpg_busy` asks "scaled or hatched" as `mov al, [fpg_pat]` / `cbw` / `or ax, [fpg_total]` (AX is banked; fewer clocks a sector on the armed path) | fprog.inc | -4 / -4 |
| `fpg_paint` reads `[fpg_pat]` and `[fpg_px]` in one word load (adjacent, the extent's high byte a permanent zero), zeroes the extent with `mov [fpg_px], al` and hands it to fpg_lit by two `xchg`s | fprog.inc | -3 / -3 |
| `toast_pass` stores `[menu_bdirty]` out of the 1 its `xchg` just took (every `[toast_dirty]` writer stores 0 or 1); `.up` joins past the store, toast_arm having set the flag | toast.inc | -2 / -2 |
| kern_small's `toast_show` stores the string's NUL out of CH (CX counted down from TOAST_MAX; `%error` if TOAST_MAX outgrows CL). kern_big's TOAST_Q arm has the TTL back in CX by then and keeps the immediate | toast.inc | 0 / -1 |
| `db_paint` counts what drew in SI - set to 1/0 where the forced span is spent (`.scan1`/`.scan0`, SKIPF2 over the `xor`), `inc si` per tile, `neg si` for the CF answer - where `[dock_drew]` was a 5-byte store, two 4-byte `inc`s and a 5-byte compare. The `.bss` byte stays: DOCK.DRV's dkx_paint still counts in it | dock.inc | -10 / -10 |

### 4. Data and smaller forms

| item | file | big / small |
|---|---|---:|
| `menu_ab_cell`'s 'About ' prefix is the first six bytes of `menu_s_about` (`'About '` / `menu_s_abos 'os8088...'`, an `%if` pins the length to MENU_ABPFX_LEN), copied by count through `menu_ab_cat.n` with `mov cl` (CH = 0 on every path into `.done`: out of the cell walk with CX at most MENU_APPMAX, or the 1 counted into `[menu_nbar]`; KES writes no CX). `'About ', 0` went | menu.inc | -5 / -5 |
| `menu_popup`'s empty descriptor is a `dec ax` (AX was 0: 0FFFFh, exactly what it returned) that the pull's return steps over with SKIPF1 | menu.inc | -3 / -3 |
| `menu_popup` and `menu_track` tell 0FFFFh from an item index by `cmp al, 0FFh` (an index is below MENU_POPMAX; `%error` guards it) | menu.inc | -2 / -2 |
| `menu_item_xor`'s cell bottom by `lea dx, [bx + MENU_ITEM_H - 1]` | menu.inc | -2 / -2 |
| `menu_inval` banks through `kent_di` (per OPERATION - a forced bar, the widget's show and hide, the speaker's move: ~60 cycles against the drawing each does, under 0.2%) | menu.inc | -1 / -1 |
| `db_draw_tile` banks through `kent_di` (a tile REDRAW, its key moved: ~40 cycles against a frame and a masked icon blit) | dock.inc | -2 / -2 |
| `.mup`'s spent arm `and word [ui_armw], 0` (the `or ah, ah` writes the flags next) | ui.inc | -1 / -1 |
| `.yj1`'s `jmp .yield` written `short` (in reach on every kernel; NASM never shrinks a jump it once relaxed) | ui.inc | -1 / 0 |

### Hot paths, parity and the disk

**No routine on khp1's H1/H2 lists changed** (`fpg_finish`, gfxcall-4, is
untouched; its KHP_FPG arm is kern_mega's). ui_task's idle pass runs the same
instructions; the two ui_task items are in its event handlers.

**`hotpar` green on both gated kernels at every commit, with no pad added or
removed.** The `.text` ahead of `ui_task` (menu.inc, fprog.inc, toast.inc)
moves -60 on both kernels, so ui_task's entry keeps its parity. Inside
ui_task, `.yield` and the idle ladder keep theirs relative to the entry: on
kern_big `.mup`'s -1 pairs with `.yj1`'s -1, on kern_small with
`.clock_cell`'s -7. ui.inc's `.text` after ui_task is even on both kernels
(-38 / -30 in all, ui_task included), so nothing from `apps.inc` on - and so not `disk.inc`'s
`align 2` - sees an odd shift, the `.text` total is even (-110 / -102) and
`.bss` starts at the base's parity; the `.bss` change (-2) is even too.
`.cold` is untouched. (One intermediate build had kern_big's ahead-of-ui_task
total odd - menu_draw_bar's `jmp .out` relaxed short by itself once the
routine shrank - and hotpar caught it; the logo's `mov bl` and kern_small's
`mov [di], ch` were chosen to pair it.)

Nothing here is on the mount, listing, read-ahead, FAT-window,
directory-write or loader path: **no `int 13h` call changed**. `fpg_busy`
runs once per `int 13h` call with the widget armed and is fewer clocks there.

## REFUSED

1. **`ui_drain` as `resb 1`** (-1 `.bss`): it is read and written as a byte,
   but a lone odd `.bss` byte flips the alignment of every `.bss` word after
   ui.inc's (disk.inc's among them). Held for a `.bss` partner; so is
   **`[dock_drew]`** (-1 `.bss`), which goes once DOCK.DRV's dkx_paint counts
   in a register as db_paint now does (`dockmod.inc`, module bytes).
2. **ui_task's `cmp byte [wm_wkdef], 0` / `mov byte [wm_wkdef], 0` (and
   `[cur_shchk]`'s) as `xor al, al` / `xchg` / `or`** (-2 each): the compare
   is on the idle pass, which the exchange makes ~10 clocks slower (H1/H2).
3. **Three odd bytes inside ui_task, held for parity**: the wake-redo loop's
   `popf` / `jmp short .wr_n` as SKIPF1 over a shared `popf` (-1), the close
   pass's two `gfx_unlock` tails as one with `or ax, ax` / `jnz .cl_next`
   (-1), and the timer pass's `mov word [si+W_TIMER], 0` as `and` (-1,
   kern_big). Each alone puts `.yield` or the idle ladder at an odd shift;
   no pair was found in the stretch between.
4. **`menu_popup`/`menu_pull`'s menu height as a helper** (-1 for a call on a
   menu open): pass 18's and pass 20's refusal stands, and nothing has
   changed.
5. **`ui_cmd`'s far tails through one dispatcher or a far table**: a far
   table is 16 bytes plus its dispatch for 24 of tails (pass 20's REFUSED 6
   stands).
6. **`menu_ab_cat` by `lodsb`/`stosb`**: the segments have to swap round it,
   which costs more than the `mov [di], al` / `inc di` it saves.
7. **`db_paint`'s zap test on a pre-subtracted bound** (`cmp ax, dx` / `jl`,
   -5 more): it is SIGNED where the `jb` it replaces is unsigned, and the two
   differ for a forced span starting left of x = 0 - not reachable on
   kern_big (db_force_x refuses a negative x1 there) and not proved
   unreachable on kern_small. Not taken: byte-identical is the bar.

## WANTS THE OWNER

None new. Every item is byte-identical behaviour. (LAST-DROP-BYTES 7.8.1, the
Dock's fourteen entries as patched far jumps, -42 resident, stays the open
row it is: self-modifying `.text` is the owner's question.)

## WANTS AN ABI BREAK

None taken or needed: nothing here moved `apps/os88api.inc`,
`drivers/os88drv.inc` or the C SDK (`abilock` untouched). Every contract
changed is kernel-internal and written at the routine (menu_bar_text /
menu_bar_clock, menu_widest, ui_track's header was already "AX..DX
clobbered").

## CROSS-FILE

1. **`wm.inc`'s `wm_band` `cbw`** (-1, wm's): still free to pair with any
   odd kern_big byte ahead of ui_task; this branch's ahead-of-ui_task total
   is even, so it needs its own partner.
2. **`dockmod.inc`'s `dkx_paint`** (DOCK.DRV, this row's file, module
   bytes): the same SI count as db_paint's item 3 would let `[dock_drew]` go
   (-1 resident `.bss`, REFUSED 1 for its pairing). Not built - the module's
   paint is shaped differently (it zeroes the byte twice) and is disk bytes.
3. **`ct_toast_say` (kernel.asm, hw's)**: toast_say still preserves every
   register; nothing here changes the trampoline's site count.

## ROWS (named; none run - BRIEF section 3)

| rows | what of this pass they reach |
|---|---|
| `uilat`, `weavelat`, `hdboot`, `uilayer` | the latency stop moved to `[menu_cell]` (the two `*lat` rows), `[menu_cell]`'s single store (hdboot's bar check, os88ui's `menu_pick`) - **uilat and weavelat are the instrument change and want a break-on-purpose look** |
| `dispapp`, `dispapps`, `dispcalc`, `alertbtn`, `atmenusu`, `sheetmsep`, `stikmenu`, `desksc`, `deskclose`, `dispclose`, `mouwheel` | menu_track's count, menu_drop's tail, menu_popup's tail and AL test, menu_widest, menu_item_xor, menu_relayout's cell loop and the About prefix (the name cell), `.mup`'s arm |
| `dispfsx`, `deskbench`, `saver` | menu_draw_bar's furniture (a forced bar) |
| `toast`, `toastfpg`, `deskcalremind`, `hdhiber`, `assocstale` | toast_pass, toast_say, toast_owner_gone, toast_show's NUL (kern_small), menu_bemit's strip |
| `fpgop`, `fpgnotch`, `fpgcold`, `curdisk`, `dosbar` | fpg_busy's test, fpg_paint's restore, menu_inval |
| `mixercga`, `mixerherc`, `mixervga`, `mixersb16`, `mixervesa`, `sndcap` | menu_sound (BP, DX across menu_bar_text), menu_bt_raw's bank |
| `cpup`, `cpcost`, `cppromise` | CMD_CTRL through ui_clkcell.open, the clock cell on kern_small |
| `tmload`, `tmsmall` | ui_sys_open's name compare |
| `dispdrag`, `dispsize`, `paintrz`, `sizesnap`, `paintshrink`, `extdmod`, `dualcheck` | ui_track, ui_drag_xor, ui_grow's vacate |
| `deskzoom`, `dispzoom` | ui_tdbl (the title-bar double-click) |
| `wmchrome`, `thm95` | ui_lit_go (a held chrome box) |
| `dockmark`, `dockpos`, `deskdock`, `paintdock`, `paintdocksmall`, `dockmodule` | db_paint's count, db_draw_tile |

No row drives a dead-zone bar press with a FAILING hdboot (the reworded
diagnostic) or `menu_popup` with an empty descriptor (no caller passes one):
both are checked by reading.

## DEFECTS FOUND

- **`menu_bar_clock`'s header said "all registers preserved"** while on every
  sound-card kernel `menu_bt_ent`'s `toast_place` already spent AX..DI before
  the composition ran. Harmless (its UI-task caller holds nothing); the
  header now states what it spends.
- **`db_paint`'s banner said SI was untouched** "between here and the exit";
  the forced span's zap loop had used SI as its bound since kernel size pass
  9. Comment corrected (SI is the count now).
- **db_paint's zap compare is unsigned** against a span the comments call
  signed: a forced span with x1 < 0 would skip clearing the keys of tiles it
  covered. kern_big's db_force_x refuses such a span before it is stored;
  kern_small's does not clamp. Not changed (REFUSED 7); recorded.
