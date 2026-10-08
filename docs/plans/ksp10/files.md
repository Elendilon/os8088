# ksp10 agent "files" - files.inc, filecp.inc, fprog.inc

Working notes, appended as decided. Figures are `kernsize` sums against the
blessed base `833f13e4`; "big"/"small" are kern_big/kern_small resident.

## TAKEN

### Batch 1 (files.inc, all `.cold` except the new key table in `.text`)

* `fm_onkey_x`: the bare letters V N A B R are a 5-row table `fm_keytab`
  (key, body) in `.text`, walked once; each body is the menu command it
  shortcuts (`fm_vflip`, `fm_c_mkdir`, `fm_c_drva`, `fm_c_drvb`,
  `fm_reload`) and still ends in fm_onkey_x's own full repaint. Backspace's
  `fm_c_up` is the word after the table (it is tested before the case fold,
  so it cannot be a table row). text +17, cold -33: **-16** both kernels.
* `.selmove`'s `push cx`/3 x `pop cx` were dead (kentc_di banked CX; nothing
  after reads it), and with them gone two `jnc x / jmp .redraw` pairs are
  `jc .redraw`. big -8 (kern_big only code).
* `fm_c_uncto` (the unpassed `3b503fd` hunk): `mov al,MOD_CLONE / call
  mod_need` -> `call clo_need`; the hunk's `cmp [clo_seg] / jne / mov al /
  call mod_drop` is fm_clone_bad's own tail, now entered as `fm_cldrop`.
  -11 big, -11 small.
* `fm_onclick_x` `.restamp`/`.select`: `[ui_click_t]` loaded once above the
  test; the restamp gets it back with `add dx,[bx+FS_CLKT]`. -5 both.
* `fm_isicon` (`cmp byte [fm_lview],0 / ret`) for eight 5-byte tests;
  `fm_rowdiv`/`fm_div80`/`fm_div` for fm_layout's and fm_hit's two row
  divides and two column divides; fm_layout's `.tot` lost its view test
  (list cols is the 1 stored just above, so ceil(n/1) = n) and its two
  `xor ax,ax / jmp` clamps fall into the divide/shift instead; `.selmove`
  loads `[fm_cols]` (1 in the list) instead of testing the view. -42 big,
  -32 small.
* `fm_tiles`: fm_more_mark's and fm_scrollpaint's byte-column band was the
  same nine instructions; `fm_cxrgt` for fm_rows_only's and fm_scrollpaint's
  clip-test openings. -21 both.
* `fm_editkey` mode ladder 3..7 is a count-down (`xor bh,bh / sub bx,3 / dec
  bx` x4). -6 both. `fm_draw_status`'s mode ladder 0..8 likewise (`cbw /
  dec ax`, mode 2 the fall-through as before; `%error` if FM_ESAVE moves).
  -7 both.

Batch 1 total: **big -116, small -98**.

### BUG FIXED (own commit eb9407ac)

* kern_big: `fm_choose .inplace` (four Disk windows up, a desktop drive icon
  or ui.inc's fmf_files_open asks for a fifth folder) loaded BX with the
  window's FS_PATH for the path seed and then did `mov si, bx / call
  fm_repaint`: the repaint was handed the PATH BUFFER as a window (W_FLAGS
  0 = PTH_LOST/buf[0] had a bit cleared, fm_cfill white-filled a rect read
  out of the path bytes, the listing drew there). Since ea48c34. The seed
  banks BX. +2 big.

### Batch 2

* `fm_pthseed`: fm_kinit's and fm_choose's identical path seeds, one proc
  that preserves BX (the bug above). -12 big.
* fm_drag on kern_small: its inline press-wait was fm_dgwait over two words
  of .bss; fm_dgwait is unconditional now and `jc .click` reaches. -10
  small code, -4 small bss, -2 big.
* `fm_kinit_x` claims its cache through `fmv_fit` after `fm_vp_set` (moved
  up from below the WM setup): fmv_fit is the claim, the movable declaration
  and the fm_vseg mirror already, and with the record published first
  fmv_owner's [fm_vinst] names THIS window - which is SPEC.md 66.5.6.2's
  owner, exactly what the hand-rolled `ld_slot` off SI computed. -29 big,
  -19 small.
* fmv_reload_all's rect union through SI = fmv_ux1 (`[si+n]` forms are a
  byte shorter each), and the `mov bx, si` before a test that can read SI.
  -8 both.
* fm_draw_core's header: one lead (nodisk/drive), the letter, one tail;
  drive and mount verdict read as ONE word (`%error` pins FS_MOK =
  FS_DRV+1). -8 both.
* `fm_linger` (the tick wait) for fm_dgwait and the drag's .track; fm_dgabs
  ends in `cmp ax, FM_DRAGMIN` for both its callers. -8 both.
* pth_push writes tentatively and takes the write back on a miss instead of
  measuring and then copying (same fit condition: sep + name + NUL <= CX;
  CX <= PTH_MAX bounds the read as the old cap did). -24 big.
* pth_lastsep answers BX (the byte before the buffer) for "no separator", so
  pth_leaf's two arms are `mov si,ax / inc si`; pth_pop falls into pth_leaf
  on both arms (pth_leaf already answers 0 for a LOST count and for an empty
  buffer, which were pth_pop's own two `xor si,si` exits). -23 big.
* fm_sel_bar divides by [fm_cols] in both views (the list's is 1) so the
  visible-row test is written once. -12 both.

Batch 2: big -124, small -65. Running: **big -240, small -163**.

Checked on MartyPC (scratch script, not a row): B:/SYSTEM/APPDATA titles
SYSTEM then APPDATA, Backspace -> SYSTEM, Backspace -> Disk; V toggles
FS_VIEW, A/B mount 0/1, N arms mode 1 and Esc ends it, R re-lists.

## REFUSED

* `fm_btn1`'s `[fdlg_gdis]` store (unpassed hunk): `test di,OS88UI_DEF` is
  4 bytes against `cmp al,FM_BGO`'s 2. Already minimal.
* `fm_rclick_x`'s Uncompress To... greying (unpassed hunk): `cmp [fdlg_win],1
  / mov ax,uncto-1 / adc ax,0` is the same 14 bytes.
* fprog: a kentc-style shared prologue for the four `pushf / FPG_BARON / push
  ax..si` entries: the helper (~20) costs what the sites save (4 x 5).
* fm_onkey_x: Cut/Copy/Paste as a (key, FMC) table: 28 bytes against the
  ladder's 25.
* fm_onkey_x: routing A/B/R/Backspace through fm_docmd - identical repaint,
  but N (FMC_MKDIR) would then draw FMD_LINE where the key draws the whole
  window: a behaviour change, and A/B/R alone do not pay.

## CROSS-FILE (for the coordinator)

(none yet)
