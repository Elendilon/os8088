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
