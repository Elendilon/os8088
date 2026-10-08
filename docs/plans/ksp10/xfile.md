# Kernel size pass 10 - xfile (the coordinator's cross-file pass, on the merged tree)

Cut at `f57e5c9b` (the merge of all ten agents). The kernsize baseline is
still `833f13e4`'s, so every `(sum N)` below is read against the merged
tree's own: kern_big `(sum -2,123)`, kern_small `(sum -1,582)` before the
first change here.

## TAKEN

1. **`cw_mem_disp equ spw_near`** (hw agent's cross-file): both are
   `call bp` / `retf` in `.text`, unconditional. Neither name is in
   `tests/ovlrefs.txt` or any tool. kern_big .text -3, kern_small .text -3.
2. **wm_dmg_gray's `jc .whole` after `desk_zones_r_x`** (new agent's):
   desk_zones_r_x leaves on `jnc .ret` (CF=0) or after `clc`, through
   `kretfc_bp` (pops and `retf`, no flag touched). kern_big .text -2
   (OS88_SHORTCUTS is kern_big's). Comment rewritten.
3. **`ui_krect4` inlined at apps.inc's Timer button** (new agent's): its
   only caller. kern_big .cold -4; kern_small .cold **-16** - the Timer
   button is not on kern_small, so the routine was dead code there. SPEC.md
   38's "what stays resident" sentence no longer names it.
4. **The word-immediate sweep (core agent's `test word` item)** - a listing
   scan of every `81 /1,/4,/6` and `F7 /0` with an immediate whose other
   byte is 00 (or FF for `and`):
   * **The wm.inc `test word [..+W_FLAGS], WF_STALE / WF_NOANIM` sites are
     REFUSED: they save NOTHING.** `W_FLAGS` is 0, so `[di]`/`[bx]` have no
     displacement and `test byte [di+1], 80h` grows one exactly where the
     immediate shrinks one (4 bytes either way). The same holds for the four
     `or`/`and word [bx+W_FLAGS]` sites beside them.
   * Taken, the register forms: memory.inc `and cx, 0x0FFF` -> `and ch, 0Fh`
     (flags dead), disk.inc dsk_next_clus_x `and bx, 0x0FFF` -> `and bh, 0Fh`
     (CF still cleared, every caller re-tests AX for ZF; faster too, a 3-byte
     instruction against a 4), diskw.inc dskw_size32 `and cx, 511` ->
     `and ch, 1`: -1 each, .cold.
   * disk.inc's free-cluster count, `and cx, 255 / sub cx, 256 / neg cx`
     (10 bytes) -> `not cx / mov ch, 0 / inc cx` (5): 256 - (SI & 255), the
     flags overwritten by the `sub ax, si` that follows. -5 .cold.
   * REFUSED: disk.inc:5306 `and dx, 0x0FFF / jnz` - the ZF is the whole
     word's.
   * CTRL.DRV (module, not resident): driver.inc's track-buffer `and cx,
     0x0FFF / neg cx` -> `and ch, 0Fh`, -1 module byte.
   kern_big .cold -8, kern_small .cold -8 (resident), CTRL.DRV -1.
5. **Comment and prose fixes, no bytes**: viddet.inc's two `menu_save_kb`
   references (it is a block inside `menu_drop` now); telnet.asm's
   `kbm_slock` (Scroll Lock through `kbm_shf`); tests/deskwhole.py's
   break-it line (`call wm_dmg_rebands`, no pops); disk.inc's `dsk_relist`
   comment; and SPEC.md's present-tense prose for `dsk_relist`,
   `dskw_remount` and `dsk_find_name` (18.9, 18.4's deferral, 51's
   `drv_find`, 28.3's chip menu, 87's `api_name`). The paragraphs that
   NARRATE their history (28.3.1, 54.9, 96.47/96.49.7) are left as they are.

## REFUSED

* **wm_su_srect's `.isect` through `gfx_rect_isectcf`** (gfx agent's): the
   best shape (`mov si, sx1 / cmp von / je .one / call isect / .vis: mov si,
   vx1 / .one: call isectcf / jc .none`) is **-6 .text**, but every call pays
   one more near call/ret (isectcf is `call gfx_rect_isect` + the compares),
   ~35-40 clocks a fragment of the save-under cache. The brief said take it
   only if not slower, and LAST-DROP-BYTES 7.10 holds the save-under cache
   for the owner. A shape that keeps one call costs more bytes than it saves
   (a mask word built from `[son] | [von]` is 44 bytes against 43).
