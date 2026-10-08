# Kernel size pass 10 - agent "input" (mouse, mouproto, menu, events, icons, clip, toast)

Base `833f13e4`. Bytes are `kernsize` section deltas against the blessed base.

## TAKEN

### Batch 1 - mouse.inc, mouproto.inc, menu.inc (events.inc: a guard only)

kern_big `.text -136 .cold -11` (sum -147); kern_small `.text -131 .cold -11` (sum -142).

mouse.inc / mouproto.inc (.text -68 big):
* `mou_pout`: `add dl, ah` for the register offset - both UART bases are
  8-aligned and AH is 0..7, so the byte add cannot carry; the CX bank goes. -6
* `mou_byte` (ISR): the phase dispatch counts AH down (`dec ah` x3 for `cmp
  ah, n`), the phase-3 store writes AH = 0, and the stray `.bout: ret` joins
  `.jbout`. -5, faster
* `MOU_DECODE_MS` (shared with kern_dos): dy first so dx is built straight in
  AX (no SI bank), the redundant `and al, 3` before `shl al, 6` dropped, and
  DL masked in place. -8 per copy, 4 instructions fewer; SI no longer clobbered
* `mou_p2_byte` .b2: same reordering, `xchg ax, bx`. -5
* `mou_apply`: left event as `and ax, 1` (kbm_btn's shape, guarded in
  events.inc), right press as `and bh, bl / test bh, 2`. -5
* `cur_geom`: `[cur_b1ok]` by `cmp/sbb/inc/mov`, branch-free. -5
* `cur_shape_set`: `cbw / add ax, ax / xchg ax, bx`. -2
* `cur_move_mono` pass 1: the row-covered answer branched on through `lodsw`
  (which writes no flag) instead of carried in DL; `[cur_rows]` widened once
  outside the loop. -8, 5 instructions a row fewer
* `cur_mvcols`: the two column loops are one (j = 1, 0), each answer computed
  into AL and stored once. -24

menu.inc (.text -68, .cold -11):
* `menu_relayout`: dead DI bank round `wm_strseg`. -2
* `menu_ab_cell`: item count = Close's index + 1 (guarded `MENU_ABMAX == 2`),
  `inc bx`, zero from AX. -6
* `menu_ab_cat`, `menu_bstr`: `es lodsb`. -4
* `menu_furniture`: the cell wipe is `menu_inval` over 0..7FFFh. -13
* `menu_bar_text`: `[menu_bfirst]`/`[menu_blast]` seeded from DI = 0. -2
* `menu_bemit`: a dead `mov cx, ax`; `+1` in the displacement for two `inc si`. -4
* `menu_draw_clock`: three `jcxz` round REPs dropped (REP with CX = 0 is a
  no-op), `cbw/xchg`, the lead's x2 off CX. -10
* `menu_drop`: entry zero from AX; `.sel` takes-and-zeroes `[menu_sseg]` with
  one `xchg`. -5
* `menu_trunc`: `repne scasb` for the fit test, one `rep movsb` with the
  segments swapped for the copy. -15
* `menu_logo_glyph`: the two blank rows are not stored, a row ends at its
  last lit pixel. -6
* `menu_kbnav` (.cold): the "inside the menu?" x test asked once, DX carrying
  the placement x. -11

## REFUSED

* `cur_lazyrect` / `cur_lazyck`: the hit arm could `call cur_unlazy` before the
  shared pops instead of popping and jumping (-4 each arm, ~-12 over three
  arms) - REFUSED: it nests cursor_hide's whole frame 12 bytes deeper on
  whatever task is drawing, and the drawing chain is the deepest a slice
  carries (STACK-SLOTS-PLAN).
* `cur_move_mono`'s save-buffer flip as `xor bx, cur_save ^ cur_savex` (-5):
  NASM refuses XOR of two relocatable labels in `-f bin`; the sum form too.
* `evq_pop`'s `jmp .done` as a `mov ax, imm16` skip-byte over `popf/stc`
  (-1): no skip-byte idiom exists in this kernel and AX would be live-looking
  garbage; not worth the precedent for one byte.
* `toast_now`'s colour bank as `push word [gfx_color]`: same bytes, and it
  would restore the neighbouring byte too.
* `clip_put`'s `.toobig` ladder: every rearrangement is the same 5 bytes.
* `MOU_DECODE_MS`'s button decode (18 bytes): every rcl/sbb/swap spelling
  found was 17-18 bytes and slower.

## CROSS-FILE

(none yet)
