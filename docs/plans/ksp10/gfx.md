# Kernel size pass 10 — agent "gfx"

Files: kernel/vga12.inc, kernel/softgfx.inc, kernel/font.inc, kernel/band.inc,
kernel/splash.inc, kernel/spinner.inc. Branch `ksp10-gfx`, cut at `833f13e4`.

#230's review fix `3b503fd` (gfx_blit1's refusal ladder) is in the base and was
read; nothing below changes its order of refusals.

## TAKEN

### Batch 1 — kern_big .text -100, kern_small .text -28

| item | big | small | speed |
|---|---:|---:|---|
| `gfx_points` exit -> `jmp kret_es` (8 pops + ret) | -6 | -6 | +1 taken jmp a CALL, not a point |
| `gfx_spans` exit -> `clc / jmp kret_es` | -6 | 0 (stub) | +1 jmp a span LIST |
| `gfx_rect_hit` / `gfx_rect_isectcf` share one `stc/ret` and one `clc/ret` | -4 | -4 | identical branches |
| `vgas_left` deleted: `[vgas_rows]` is the countdown (two copies of `mov ax,[rows] / mov [left],ax`) | -12 | -12 | faster (two loads/stores gone a scroll) |
| `vgas_lincopy` inlined into `gfx_scroll` (one caller) | -4 | 0 (VGA only) | faster (call/ret gone) |
| `gfx_fill_gray_raw` / `gfx_fill_pat_raw` teardown -> `vga_solid_rect.reset/.done` | -10 | 0 (VGA only) | +1 taken jmp a FILL |
| `gfx_fill_pat_raw`'s two edge columns -> one local `.col` | -21 | 0 (VGA only) | +2 call/ret a pat fill (rare: TaskMgr map) |
| `gfx_restore`'s tail is `gfx_save`'s (`gfx_sr_tail`) | -6 | -3 | +1 jmp a restore (not the cursor's path) |
| `vga_sr_on` inlined at its two callers | -3 | 0 | faster (call/ret and push/pop gone) |
| `gfx_frame` shares `gfx_xor_rect_clip`'s tail | -3 | -3 | +1 short jmp a frame |
| `gfx_pt_resolve` reads each origin once, AX's short stores | -4 | 0 | faster |
| `osapi_gfx_fill_pat`'s copy: `es lodsb` | -2 | -2 | faster |
| font_run: `[font_rn_fg]`/`[font_rn_bg]` as ONE word, three sites (+ %if) | -12 | 0 | faster (per RUN) |
| `fnt_rn_edge` VGA arm: a dead push/pop AX and a DH hop | -4 | 0 | faster (per unaligned run) |

(kern_small's -28 is the rows marked; the per-row arithmetic is approximate where
an arm assembles out.)

## REFUSED

* `lea sp, [bp+18]` for `mov sp,bp / add sp,18` in gfx_blit1_x's `.noswap`
  (-2 cold, and faster): `tools/stkbalance.py` does not model `lea sp`, so the
  routine reads as unbalanced. Cross-file below.
* gfx_fill_gray_raw's edge columns as a subroutine (-12): +2 call/ret on every
  gray fill (desktop, every scrollbar trough), ~3.5% on an 8x8 gray fill.
  gfx_fill_pat took it because it is the rare fill.
* gfx_clip_run's pop run -> `jmp kret_di` (-4): per clipped primitive; the kret
  banner in kernel.asm lists it as deliberately kept.
* sw_fill_pat through sw_rect's prologue with a 4th sw_mode (~-0 net): the
  dispatch it needs in sw_rect_pl costs what it saves, and touches the SOLID
  fill's path.
* vga_seq+gc reset helper for gfx_blitp/vga_blit_prow: one beneficiary, +6 net.

## CROSS-FILE (for the coordinator)

* `tools/stkbalance.py`: teach it `lea sp, [bp+N]` (= `mov sp,bp` + `add sp,N`).
  Then vga12.inc's gfx_blit1_x `.noswap` can take it: -2 .cold, faster.

## NOTE FOR THE MERGE

`docs/INDEX.md` is regenerated in this branch only because this notes file is a
new tracked `docs/**.md` (the docindex gate). It conflicts with every other
agent's identical one-line change: resolve by re-running `tools/os88index.py`.
