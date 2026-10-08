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
