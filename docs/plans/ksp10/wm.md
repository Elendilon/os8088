# ksp10 agent "wm" - kernel/wm.inc

Notes appended as decided. Figures are `kernsize` section deltas against the
blessed baseline at `833f13e4`.

## TAKEN

### Batch 1 - the damage re-seed, the empty box, one occlusion walk
kern_big `.text` -82, kern_small `.text` -66.

* **`wm_dmg_rebands`** (the #230 review fix's hunk, `e890eb7`, passed without
  losing it): `wm_dmg_gray`'s `.frames` and `.whole` re-seeded the bands by
  popping the damage off the entry frame and pushing it straight back (10
  bytes each) before `call wm_dmg_bands`. `wm_dmg_bands` already banks the
  damage in `wm_db_r` and reads AX..DX nowhere after, and nothing else writes
  `wm_db_r`, so a second entry after its four stores re-seeds with no
  register at all. -20 big (two sites), -10 small (one). The fix itself is
  unchanged: `.frames` still rebuilds the frames-only region and `.whole`
  still re-owes the zones and re-seeds the bands, not the box.
* **`wm_rect_empty`**: three boxes (`wm_db_b`, `wm_dmg_zb` at `.wdone`,
  `wm_cov_x1..y2`) each spelled six stores to seed the empty union box. One
  17-byte helper. The far-corner sentinel is now -1 for all three (it was
  8000h for the first two); equivalent because every rect folded into those
  two is on the glass (x2/y2 >= 0) and an unfolded box is refused by x1 =
  7FFFh alone in gfx_rect_hit. wm_cov_rect's was -1 already, and it is the
  one a package sees through wm_damage. -16 big, ~-16 small. SPEC.md 30.x's
  dock span sentence that cited wm_dmg_bands' idiom updated.
* **One occlusion walk**: `wm_clip_occl_r`'s loop and `wm_dmg_occl`'s were
  the same loop. Every entry now names its subtract in DI and its start in
  SI/CX and joins at `wm_occl_go`; `wm_clip_subx` and the `wm_clip_ofr` flag
  byte it read per window are gone (DI is the choice). wm_zabove leaves CX = 0
  on CF = 1, so "nothing above" needs no test. -46 big, ~-40 small. Faster per
  window too: `call di` replaces a `cmp byte [mem],0` + branch + jmp.

### Batch 2 - rect_get/rect_put at fourteen sites, the title bar, small ones
kern_big `.text` -207 (cumulative -289), kern_small `.text` -203
(cumulative -269).

* **rect_get / rect_put** (already in wm.inc, 5 bytes a site against 12 for
  four `mov`s): wm_dmg_bands' store and load (both arms), wm_paint_dmg,
  wm_dmg_gray's `.fill`, wm_su_owed (between gfx_rect_hit and its `jnc`:
  neither helper writes a flag), wm_su_sub, wm_su_vset, wm_su_srect,
  wm_su_flay, and wm_su_try's load and per-fragment store - and wm_su_try's
  two four-word COPIES (sx -> bx before the walk, bx -> sx at `.out`, 24
  bytes each) as a get+put pair, 10. -7 a site, -14 a copy. Each costs
  ~140 cycles (~30 us) over the four movs; none is in a per-pixel loop, the
  heaviest (wm_su_srect, wm_su_try's `.frag`) run per fragment/piece of a
  restore, i.e. a few times per window. RECT4 asserts added for the three
  newly addressed blocks.
* **wm_draw_title**: four `mov dx, [di+W_Y]` / `add dx, n` pairs become
  `lea dx, [bx+k]` off the BX the same block just loaded (gfx_fill, the pens
  and thm_tink preserve BX). -12. Same primitive calls, fewer instructions.
* **wm_su_flay's WSU_CLAMP2** macro (two copies, 22 bytes each) is a local
  `.clamp2`. -15. Costs two call/ret pairs (~70 cycles) per wm_su_flay, i.e.
  per window cache op; the macro's comment argued against exactly this, on
  speed. A fiftieth of one gfx primitive call - taken.
* small: wm_min_floor (CX needs no bank; the cap reloaded straight into AX)
  -4; wm_resize_nb's push/pop CX DX round wm_min_floor whose values were
  overwritten next line -4; wm_rz_swap lea + lodsw -4; wm_dmg_stale `x2 <=
  x+w-1` as `x2 < x+w`, and AX needs no bank there -6; wm_su_srect's second
  `cmp [wm_su_son]` (`.named` is only reached with it set) -7; wm_su_bget's
  `or al, al` after a `pop` (ZF already set) -2; wm_damage's four
  pop/pop/ret exits one tail -5; wm_su_drop_all walks records not indices
  -4; wm_an_lerp addresses wm_an_c as [si+16] (asserted) -6; wm_su_piece,
  wm_clip_split -1 each.

## REFUSED

* **wm_rz_swap with `scasw`** (one more byte) and **wm_an_lerp with
  `cmpsw`**: both read ES:DI, and ES belongs to nobody - a stray read of
  A000 loads the VGA latches.
* **A shared `wm_flagw` for the on/off flag setters** (wm_ownbg,
  wm_sizable...): needs a mask register or an inline-word helper that
  discards its own return address under a pushf; the saving was ~10 bytes for
  a helper nobody could read.
