# ksp21 agent "draw" - vga12, softgfx, icons, band, blank, splash

Kernel size pass 21 (`docs/plans/completed/ksp21/BRIEF.md`), section 2's `draw` row:
`kernel/vga12.inc`, `kernel/softgfx.inc`, `kernel/icons.inc`,
`kernel/band.inc`, `kernel/blank.inc`, `kernel/splash.inc`. Branch
`ksp21-draw`, base `3fc4e9d09` (the brief). Figures are ASSEMBLED bytes,
`tools/kernsize.py --json` absolutes; resident = `.text` + `.bss` + `.cold` +
`.lowbss` + `.vgabuf` + `.vga` (+ `.mega`). Per-routine figures are
`tools/os88rdiff.py kernel` spans.

Only this row's files were edited, and one file in no row: `tests/megaseg.txt`
(TAKEN, free: its allowance +3 with the reason, see CROSS-FILE). `band.inc`
(0 resident: `BAND=1` only) and
`splash.inc` (`.boot2`, not resident) were read and not changed; `blank.inc`
was read and gave nothing that is not a parity cost (REFUSED below).

## BASE AND TIP

| kernel | `.text` | `.cold` | `.vga` | **resident** base | **resident** tip | delta | `KERN_SIZE` |
|---|---:|---:|---:|---:|---:|---:|---|
| **kern_big** | 39,510 -> 39,444 | 37,830 -> 37,828 | 2,218 -> 2,197 | 90,225 | **90,136** | **-89** | 95,744, no rung |
| **kern_small** | 29,101 -> 29,069 | 20,860 -> 20,798 | - | 55,672 | **55,578** | **-94** | 57,344, no rung |
| kern_emu | 39,756 -> 39,690 | 37,830 -> 37,828 | 2,218 -> 2,197 | 90,471 | **90,382** | -89 | 95,744 |
| kern_mega | 45,275 -> 45,191 | 53,078 -> 53,076 | - | 134,293 | **134,207** | -86 | `.mega` 24,800 unchanged |

`.bss`, `.lowbss`, `.vgabuf`, `.boot2` and every module image are unchanged
on all four. kern_mega's -86 is all CONVENTIONAL sections (`.text` -84,
`.cold` -2); `.mega` is untouched, and its conventional footprint stays
61,952 of 68,096 (no step). Every `.text` total is EVEN against the
base (-66, -32, -66, -84): `.bss` follows `.text` unaligned (`vfollows .text`,
`valign 1` in the map), so an odd total would move the parity of every `.bss`
word - `[ticks]` and the scheduler's among them. Item 22 is the byte that
keeps kern_big's and kern_mega's even.

Knob builds (`NOVIDEXT`, `NOBLITCUT`, `NOPLANE`, `NO_COLD_SLIDE`, `BAND`)
assemble and are each smaller than at the base.

## TAKEN

| # | item | big | small | emu | mega | hotness, cycles |
|---:|---|---:|---:|---:|---:|---|
| 1 | **gfx_line / linit / lstep / lstepv's `stc / ret`**: no label names them since pass 4 deleted the cells; two unreachable bytes | -2 | -2 | -2 | -2 | none |
| 2 | **gfx_points: `jcxz gfx_hl_ret`** (gfx_hline's `ret`, a label added) for `or cx, cx / jnz .work / ret` | -3 | -3 | -3 | -3 | H2 per call: a drawing call pays a jcxz not taken (6) for `or` + a taken `jnz` (19), -13; an EMPTY call +11. The empty call now leaves the caller's flags, which SPEC.md 5.6.9 does not name (out: nothing; no package tests them - grepped) |
| 3 | gfx_pt_miss's PARITY nop (items 1, 2, 4 make kern_big's span even; kern_small keeps one, see 4) | -1 | 0 | -1 | -1 | never executed |
| 4 | **gfx_points: the `mov al, [gfx_ln_ink]` reload goes** - gfx_ls_box keeps AX, so AL is still the class | -3 | -3 | -3 | -3 | H2: a 14-clock memory read a call fewer. kern_small: an odd 9 over the span to gfx_blit4, so its PARITY nop stays |
| 5 | **gfx_disp_run: `jmp kret_bp`** for `pop bp / jmp kret_di` | -1 | 0 | -1 | -1 | the same two instructions, one byte less to fetch |
| 6 | **gfx_blit4: the CUT and the NAMED HALF behind the walk's exit** at the top, so `jne .hkforce` and `jc .cut` are short (they were relaxed five-byte jumps); `.hkforce` shares `mov [gfx_blit_hk], 1` by setting it after `gfx_disp_enter` (only gfx_blit4 reads the flag), `dec dx` for `dec dl`, and the foot's PARITY nop goes | -14 | 0 | -14 | -14 | H2: single display identical; two displays: each guard's common arm was a TAKEN `jnz +3` (16) and is a not-taken short jcc (4), -24 a blit; the named half and the cut are faster too. The run loop moves an EVEN +14 |
| 7 | **vga_p4build: a sentinel-counted shift loop** - DX starts at 1, four `shl, shl, rcl, rcl` passes carry it out of bit 16 on the fourth, `jnc` is the count | -10 `.vga` | 0 | -10 | -10 | once a boot / mode (~85k against ~88k clocks); the table modelled equal for all 256 bytes and run equal under unicorn |
| 8 | **gfx_fill_pat_raw_v leaves through gfx_fill_gray's own teardown** (the same 11 bytes as vga_solid_rect's): on the rung both `jz` and the `jc` reach it, so the two 3-byte stubs go for one 2-byte `jmp short`; without the rung (kern_mega) the `jc` still reaches it and its stub goes | -4 `.vga` | 0 | -4 | -2 | H2 per pattern fill: -15 clocks on each early exit, the interior path unchanged (a `jmp short` for a fall into a `jmp near`). kern_mega: -3, one byte taken back by disk.inc's self-adjusting parity byte after dsk_img16. `gfx_fill_gray_raw_v` is named on every build now (in `.text` without the rung) so the stub spelling is the one tools/stkbalance.py follows |
| 9 | **gfx_spans clips in registers** and writes `[gfx_sp_si]`/`[gfx_sp_n]` once, after the clip: the top clip is `neg / sub cx / jbe`, the bottom `mov bx,[vid_ch] / sub / jbe / cmp bx, cx`; `.nil` IS the packed arm's `jmp short .done`, `.no` sits behind it, and the arm's PARITY `db 0` goes | -20 | 0 | -20 | -20 | H2 per span list: ~-41 clocks on the unclipped path (no `cmp ax,[mem]`+taken `jb`, a register `cmp` for a memory one), more on a clipped one (two memory read-modify-writes gone). The row loops move an even -20 |
| 10 | **gfx_sp_next: no `cs:`** on its three inlined gfx_nextrow operands (DS is the kernel's there, as its `[gfx_sp_*]` reads say) | -3 | 0 | -3 | -3 | H1 per span row: -6 clocks and 3 bytes of fetch |
| 11 | thm_desk's `db 0x90` PARITY byte, paired with item 10's odd 3 | -1 | 0 | -1 | -1 | never executed |
| 12 | **kern_small: gfx_blitp and gfx_spans are `equ gfx_blitd.no`**, the one `stc / ret` (`.no` moved out of gfx_blitd's VID_EXT arm) | 0 | -4 | 0 | 0 | the same refusal |
| 13 | **kern_small: gfx_blit1_x's complemented loop and its test are VGA-only.** With no pen, DL was `xor dl, dl` and then `or dl, dl / jnz .rowi`: never taken, so `.rowi` (55 bytes), the test (6) and `.row`'s `jmp short .emitted` (2) were dead. One PARITY nop before `.fast` keeps its loops and `.cold`'s dsk_* placed | 0 | **-62** `.cold` | 0 | 0 | the `.row` loop moves an even -6, `.fast` -62; faster per band (no dead test) |
| 14 | kern_small: the `db 0` above gfx_sub_st and gfx_scroll's 3-byte `cmp si, 0` were two parity bytes for one job | 0 | -2 | 0 | 0 | see *Parity* |
| 15 | **gfx_blit1_x (VID_EXT builds): x back off the frame's placeholder** after the row base, where it was `push cx / pop cx` round the call; the hook's PARITY nop goes with it | -2 `.cold` | 0 | -2 | -2 | H2 per band: -8 clocks (a 21-clock frame read for a 27-clock push/pop pair). The row loops move an even -2 |
| 16 | **icon_draw_x's refusal leaves through icon_draw's pen reset**: `stc / push bp / push es / jmp short ico_draw_common.pen` - kent_di's six words and two more are kret_es's frame | -4 | -4 | -4 | -4 | refusals only |
| 17 | **icon_draw_ix: `and cx, 7 / inc cx`** for `and cl, 7 / inc cl / mov ch, 0` | -3 | -3 | -3 | -3 | H3, per run: faster |
| 18 | icon_draw_ix banks x and y after the band test, so `.band` has nothing to pop | -2 | 0 | -2 | -2 | H3 |
| 19 | **ico_core_v: the two pens are `ico_vpass`**, which falls into ico_pass, and the end tail-jumps vga_gc_reset | -7 `.vga` | 0 | -7 | -6 | H3 per VGA icon: a call+ret fewer (~35 clocks) |
| 20 | **ico_core_bb falls into ico_bbpass**: it was `jmp short ico_bbpass` of 0 bytes on kern_big and kern_small; the VGA pass moved below the 1bpp passes so kern_mega falls through too | -2 | -2 | -2 | -2 | H3 per 1bpp icon: a jump fewer |
| 21 | kern_small: ico_core falls into ico_core_bb (`.none` is `.ret`, in reach; the `jmp ico_core_bb` over it goes) | 0 | -3 | 0 | 0 | H3: a jump fewer an icon |
| 22 | icon_draw's header: `cbw` for `xor ah, ah` on kern_big's builds (every record's width is 1 or 2) | -1 | 0 | -1 | -1 | -1 clock; it is also the byte that keeps kern_big's and kern_mega's `.text` totals even |
| 23 | **sw_pairbuild: DH handed between the two `.pair` calls** - 0FFh / 0 and a `not` in `.pair`, so neither call sets it and nothing undoes it; sw_pbit's dither returns DH's low bit | -6 | -6 | -6 | -6 | once a boot |
| | **total** | **-89** | **-94** | **-89** | **-86** | |

### Parity (`hotpar`)

`tests/unit/t_hotpar.py` green on kern_big and kern_small at every commit,
from a real `make` each time. Five PARITY pads went because their partners
did (items 3, 6, 9, 11, 15). kern_small keeps gfx_pt_miss's nop (item 4),
gains one before gfx_blit1_x's `.fast` (item 13) and loses two of its own
(item 14). Every change inside a pinned routine before its
loops is even (gfx_blit4 +14/-14, gfx_blit1_x -2 and kern_small's -6).

The UNPINNED code left at an odd shift against the base, on kern_big (a cost
on an 8086/V20/286 bus, none on the 5150's 8088; pass 20 accepted the same
shape): gfx_disp_enter .. gfx_hline (the display hooks, gfx_rect_*,
gfx_clip_run - item 5's byte), gfx_pt_miss, gfx_fill_gray_cl .. thm_desk (the
gray/pattern/XOR/save/restore doors, gfx_sub_arm and the pens - item 10 to
11), icon_draw's common tail to icon_draw_ix (after ui_task) and `.vga`'s
ico_pass (after every pinned rung body). On kern_small: gfx_sub_st's three
words to gfx_scroll's head (item 14).

### Speed and the disk

No khp1 pick reverted or made slower; every H1/H2 change above is faster or
equal on its path, counted in the table in the 8088's terms. No change
touches a disk path: no `int 13h` call added or removed.

### Equivalence

Scratch unicorn harnesses against the BASE and TIP kernels' own bytes
(`os88rdiff --keep` builds of `kernel-full.bin` + map, `.text`, `.vga` and
`.cold` at their segments), khp1's VGA GC/Sequencer model with latches for
the planar paths (`docs/plans/khp1/patches/tools/equivalence/vga_planeq.py`,
reused), 1bpp framebuffers in CGA and linear geometry. Compared: every
register, CF where a contract names it, all four planes and their per-byte
write counts, the GC state, the touched cells, the framebuffer.

| kind | routines | kernels | cases | result |
|---|---|---|---:|---|
| p4 | vga_p4build: the 512-byte table, both flags | big | 1 (all 256 entries), each run | identical; red on `mov dx, 2` |
| pair | sw_pairbuild over random gfx_inktab contents | big, small | 700 + 650 | identical; red 50/50 on DH = 0 |
| pat | gfx_fill_pat_raw_v, rects incl. clipped and empty | big | 1,160 | identical; red on a `.done` for `.reset` |
| spans | gfx_spans on VGA, CGA and linear 1bpp, y far off both edges, `-n`, `h`, CX = 0, refusals | big | 960 | identical; red on `jb` for `jbe` |
| ico | icon_draw, kinds 1/2, h 1..32, clipped, pens; VGA and 1bpp | big, small | 1,660 + 650 | identical; red on the second pen |
| icox | icon_draw_x, refusals (kind, h 0, h > 16) and accepted | big, small | 1,510 + 650 | identical; red on `clc` |
| ix | icon_draw_ix, random run streams, the band path | big, small | 850 + 200 | identical; red on the band count |
| pts | gfx_points, CX = 0 (regs) and short sets | big, small | 1,310 + 450 | identical; red on `jcxz gfx_hline` |
| b1 | gfx_blit1_x, VGA (pens) and 1bpp, x/y off screen, tails, strides | big, small | 650 + 460 | identical; red 33/50 on `[bp+12]` for `[bp+14]` |

The counts are over the three commits; each kind was re-run on the tree
after the last change it covers (the tip for b1, ico, icox, ix and pat).

gfx_blit4's move (item 6) was checked by reading the instruction diff
(`os88rdiff --show gfx_blit4`): the same instructions on every path, the flag
store after the enter rather than before (gfx_disp_enter reads no
`gfx_blit_*`), and `tests/blitcut.py`'s bracket (entry, `kret_ret`) is
unchanged. kern_small's item 13 removes code whose only entry is a `jnz`
after `or dl, dl` with DL just zeroed (the swap path to `.rowi` is VGA-only);
the b1 harness runs it. gfx_sp_next (10) and gfx_scroll's `or si, si` (14)
read the same operand through the same segment and set SF the same way.

`tools/stkbalance.py` over the four files, base against tip: the same 10
pre-existing kret-ladder findings, nothing new. `make`, `make small`, `make
emu` and `make mega` build at the tip (`make mega`'s os88megaseg after the
allowance above); the fast tier 54 passed, 4 skipped (the C toolchain's
rows), at every commit.

## REFUSED

* **gfx_b4piece's `pushf / add si, di / popf` as `lea si, [si+di]`** (-2):
  `[si+di]` is not an 8086 addressing mode. No flag-free add of SI and DI
  is shorter.
* **gfx_scroll's `.no` above its entry** (-1, and ~15 clocks off every
  scroll): an odd byte with no partner short of the 1bpp renderer's loops
  (sw_rect, sw_spans, gfx_rect_setup), which it would leave at an odd shift.
* **vgas_bankcopy written in at its one call** (-1 net): odd, the same.
* **gfx_pen_dis by `cmp [gfx_mono1], 1 / sbb / and`** (-2): CF stays 0, but
  ZF/SF out of OSAPI_GFX_PEN_CF would differ, and the cell is
  documented as passing flags through.
* **gfx_xor_fill_raw without its `[vid_mono]` test** (-10): the 1bpp arm
  would pay a push, a cur_unlazy and two jumps per XOR fill (drag outlines).
* **gfx_clip_run's pops as `jmp kret_di`** (-4): +15 clocks a clipped run,
  LAST-DROP-BYTES.md 7.10's "never convert gfx_clip_run".
* **gray's own teardown as vga_solid_rect's** (-8): a jump on every gray
  fill's interior exit - pass 10 measured that +0.29% (the source says so).
* **vga_sr_dq's stub** (-3): vga_solid_rect_v is pinned, and the only pad
  in reach (before gfx_fill_gray_raw_v) is after it.
* **The pad inside gfx_blit4 after `jmp short .nextrow`** and **font.inc's
  three pads**: removing gfx_blit4's would move `.ebudget`, `.eplanar` and
  `.nextrow` (the per-row tail) to an odd shift; font.inc is input's.
* **sw_pairbuild by a two-bit class per colour**: longer.
* **gfx_disp_enter / gfx_disp_enter_n sharing their nest test**: pass 20's
  refusal holds (a nested enter would pay a display walk).
* **blank.inc**: blk_set's two `mov si`, ssf_set's `.ok` and the ss_* calls
  are each already minimal or would save one byte in a parity-pinned span
  (blank's `.text` lies between sch_switch and ui_task, its `.cold` between
  gfx_blit1_x and dsk_xfer) with no partner.
* **ico_bbop as a byte of ico_col** (-1 `.bss`): the lifetimes are disjoint
  (1bpp pass / VGA pass, each written before read), but it moves every
  `.bss` word after the icons to the other parity, for one byte.
* **gfx_blit1_x's `.pen`: `and bl, 0Fh` after `not bl`** (-3): GC1's high
  nibble would be written as 1s; real VGAs ignore it, but the port write
  differs.
* Pass 20's and 18's refusals (kent_* on the 1bpp primitives, vid_setmode's
  pops, the VGA save/restore DS/ES hoist, `aad 4`) still hold and were not
  re-proposed.

## WANTS THE OWNER

None. No picture, result, refusal, limit or message changes. (Item 2 changes
the FLAGS an empty OSAPI_GFX_POINTS returns - the caller's own rather than
`or cx, cx`'s - which no contract names and no caller in the tree reads.)

## WANTS AN ABI BREAK

None found. No slot, structure or SDK file moved; VESA.DRV's `ico_*` pointer
groups (VXB_ICOG/ICOP/ICOXY/ICOC) are untouched.

## CROSS-FILE

* `tests/megaseg.txt` (no row's; edited here): `make mega`'s os88megaseg
  gate measures kern_mega's kernel segment MINUS kern_big's, and this row
  took 3 bytes more from kern_big's than kern_mega can follow (item 8's
  early exits reach gray's teardown only on the VGA rung, item 19's tail
  `ret` was already shared on kern_mega). kern_mega did not grow, so the
  figure is 3,778 -> 3,781 with that reason in the file, as its own message
  asks. Every other agent's split between the two kernels moves the same
  reading: the coordinator should take os88megaseg's figure at the merge.
* `kernel/font.inc` (input's): three PARITY pads sit between gfx_blit4 and
  font_run on kern_big (after font_char, font_ink and fnt_unlazy), and one
  on kern_small (after fnt_unlazy). Any two of them can go together for -2
  (everything after the second keeps its parity) - the window between them
  is font.inc's own code.
* `kernel/disk.inc` (disk's): the self-adjusting parity byte after
  dsk_img16 took one of item 8's three bytes back on kern_mega. Worth
  knowing for any odd change ahead of it on kern_mega.
* `.bss` follows `.text` with no alignment on every kernel: the sum of all
  ten agents' `.text` deltas decides the parity of every `.bss` word. This
  row's is even on all four; the coordinator may want the merged total to be.

## ROWS (named, not run - the coordinator's union)

| rows | what of this row they reach |
|---|---|
| `hotpar` (fast) | every pad paired or removed |
| `gfxpoints`, `gfxptsmall`, `ptsext`, `ptsmix`, `gfxewalk`, `mcseg`, `mcperf`, `dispmodex` | gfx_points (2, 4), gfx_ls_box, the empty call |
| `blitcut`, `b4walk`, `dispblit`, `dispstrad`, `atblit`, `atblitvga`, `blitplane`, `dispblitp` | gfx_blit4's cut and named half (6), vga_p4build (7) |
| `paint1blit`, `paint1bpp`, `paint1small`, `blitpair`, `win1bpp`, `su1bpp` | sw_pairbuild's tables (23), gfx_blit4 on 1bpp |
| `fillpat`, `dispblitp` | gfx_fill_pat (8) |
| `spantest`, `spantest-vga`, `paintundo-vga`, `skiesspan` | gfx_spans and gfx_sp_next (9, 10) |
| `deskflash`, `deskpen`, `deskclip`, `desksmall`, `ddsmall`, `glyphcost`, `atblit`, `small128` | gfx_blit1_x (13, 15) |
| `icoclip`, `icohd`, `icoshed`, `icostore`, `deskfdd`, `deskflash` | icon_draw, icon_draw_x, icon_draw_ix, ico_core_v, ico_core_bb (16-22) |
| `dispstrad`, `dispnp`, `dispdepth`, `dispsaver` | gfx_disp_run (5) |
| `small128`, `npscroll`, `drvscroll` | kern_small's stubs, pads and gfx_scroll (12, 14, 21) |
| `dispthm`, `thm95` | thm_desk (11's pad only) |
| `vesablit4`, `vesa` | gfx_spans' packed arm (9) and gfx_blit4's VX arm, unchanged code at new offsets |

No row was run by this agent (BRIEF section 3), and no boot was taken: every
drawing change is identical on the planes or framebuffer under the harness,
on CGA and linear 1bpp geometry as well as VGA.

## DEFECTS FOUND

1. gfx_line / linit / lstep / lstepv's body outlived its cells by five
   passes (item 1) - nothing reached it.
2. kern_small carried 63 bytes of gfx_blit1_x that no path could reach
   (item 13): the complemented loop's `%ifdef GFX_VGA` covered the pen that
   arms it but not the loop or its test.
3. `jmp short ico_bbpass` assembled to `EB 00` on kern_big and kern_small
   (item 20).
4. The `cs:` overrides in gfx_sp_next were gfx_nextrow's, inlined into a
   routine whose DS is the kernel's.
5. tools/stkbalance.py reads every `%if` arm as straight-line code (only
   `KHP_*` is evaluated), so a jump in a build's OTHER arm to a local label
   it cannot resolve reads as a tail call at depth: it flagged a first
   spelling of item 8. Not a defect in the tool so much as its known limit;
   naming gfx_fill_gray_raw_v on every build was the fix.
