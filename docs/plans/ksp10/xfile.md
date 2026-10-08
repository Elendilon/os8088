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
