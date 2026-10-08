# ksp10 agent "new" - fdlg.inc, desk.inc (and #230's review fixes)

Base `833f13e4`. Figures are `kernsize`'s section deltas against the blessed
baseline, cumulative where marked.

## TAKEN

### 1. desk_zones_r (e890eb7's desk half): kern_big .cold -74, kern_small 0

The review fix added ~117 bytes here (the overflow count, the mask rebuild,
the up-shift). Same predicate, same bound, same zone order, same mask out:

* The mask is a 33-bit RING with CF: `rcl [m]; rcl [m+2]` rotates the last
  verdict in and the next zone's bit out in one step, and 33 steps put every
  bit back - so no register copy of the mask, no separate rebuild, no
  up-shift loop. Bits past DESK_NZ (nobody's) go back 0. Checked against the
  old code in a model, 20,000 random masks and verdicts.
* SI and DI are free with the mask in memory: SI -> wm_cl_ox1 (the compares
  are `[si+d8]`), DI the ring counter.
* The bound walk ALSO answers "is any of it revealed?" (DH = fragments
  overlapped), which was a wm_clip_walk of its own through ct_cw_mem_disp:
  the predicate is the same four compares (wm_clip_walk's swapped-corner
  overlap).
* The per-rect test is one X/Y body run twice (BX and SI two bytes on, bit 15
  of BP the pass flag).
* `cmp bp, 0x100 / adc dx, bp` with BP = 0xFF + pieces is the
  "+ max(0, pieces-1), and count it" step.
* The subtraction's CF is not read: the count is a bound on wm_clip_subr's
  peak, so it cannot overflow (proof in the header).

## REFUSED

## CROSS-FILE

* `kernel/wm.inc` wm_dmg_gray: the `jc .whole` straight after
  `call COLD_SEG:desk_zones_r_x` (~6233) is dead - desk_zones_r_x never
  answers CF=1 now. 2 bytes of `.text` (kern_big). Its comment wants the
  same edit.
