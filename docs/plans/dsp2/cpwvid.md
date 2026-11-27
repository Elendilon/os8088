# Driver size pass 2: cpwvid (the wide Display page, VESA.DRV)

Branch `dsp2-cpwvid`, cut from `1b01907f1` (the brief). Brief: [BRIEF.md](BRIEF.md),
row `cpwvid`: `kernel/cpw_vid.inc` (CPWIDE.DRV's Display page, SPEC.md 135.9)
and `drivers/vesa/` (VESA.DRV, SPEC.md 120). Base measured in this worktree
at `1b01907f1` (build 445), tip at `fe1d629bc` plus this note.

## 1. BASE AND TIP

"image" is what RAM pays (a module's `MOD_H_IMG`, its bss tail included; a
driver's image with bss); "file" is the lz4 file on the disk.

| file | kernel | image base -> tip | file base -> tip | heap claim |
|---|---|---:|---:|---|
| CPWIDE.DRV | kern_big | 13,763 -> **13,322** (-441) | 11,653 -> **11,382** (-271) | 14,336 -> 13,824 (one 512 less) |
| CPWIDE.DRV | kern_emu | 13,763 -> **13,322** (-441) | 11,653 -> **11,382** (-271) | 14,336 -> 13,824 |
| CPWIDE.DRV | kern_mega | 13,793 -> **13,345** (-448) | 11,670 -> **11,401** (-269) | 14,336 -> 13,824 |
| CPWIDE.DRV | kern_small | not built (no SPEC.md 135 there) | | |
| VESA.DRV | all three | 7,564 -> **7,639** (+75) | 3,698 -> **3,765** (+67) | 7,680 -> 7,680 (`DRVM_IMG_VESA` 15, unchanged) |

Of which, by commit: the Display page's size pass -477 / -309; its redraws
+36 / +38; VXV_INFO -10 / -10; VX_FONTRUN's one-pass rows +85 / +77 (the one
item bought with bytes, for speed: section 3). `cpw_vid.inc`'s own bytes
(every `cpv_` label, strings included): 4,749 -> 4,308.

Disks (`os88diskuse --diff`): `os8088-360.img` VESA.DRV 3,698 -> 3,765, 8 -> 8
clusters, free 27 -> 27. CPWIDE.DRV is on no 360KB disk (`SYS360OMITDRV`).
No other 360KB image changed. On the 1.44MB/720KB/1.2MB system disks
CPWIDE.DRV is 271 bytes smaller and VESA.DRV 67 larger.

Resident kernels: `cmp -l` of `kernel.bin` against the base on kern_big,
kern_emu, kern_mega and kern_small shows exactly three bytes on each, the
build number (445 -> 449: its ASCII digit and both copies of its low byte).
No module immediate moved (MOD_CPW has no size immediate resident).

## 2. TAKEN

Equivalence for every CPWIDE.DRV item: `cpvh.py`/`run.py` (scratch), a
unicorn harness that loads the module image in a model machine whose kernel
is stubs - every far call out (`cw_gfx_fill`, `apic_font_run`,
`api_gfx_blit4`, the KGO hops to `os88ui_*`/`vid_dual_ok`, the KDOOR, the
`CPE_GATE` far pointer with a VESA.DRV model behind `CPG_VXCALL`) logs its
arguments - and drives `cpw_ev` through scripted tours and seeded random
sequences (press/release/drag on every control, row, tab, slot and the
scroll bar, Test/tick/Keep/Revert/Esc, the small state, page switches,
the driver unloaded, close mid-test) over 16 machine set-ups (VGA alone;
VGA with EGA/Hercules/CGA, paired or not; VESA loaded and not lit; VESA
running; QEMU's ten records; a card with 15bpp-only geometries; 16 records
and more; a record that refuses; no answer; zero records; a VIDSET that
fails; a revert that fails; obscured ticks; both window sizes). Coverage of
`cpw_vid.inc`: every instruction but one unreachable `ret`. Mutation: a
one-byte change of the tie rule goes red at the first paint.

### 2.1 The Display page's code (`ab31b47f4`) - image -477, file -309

Cold (the page's paint and presses), and FASTER on every event: the harness
compares the call LOGS - the same primitives, arguments and order, the same
gate ops and far calls - and the returned registers and the page's state,
event by event: 36,469 scenario-steps, 0 differences; no event ran more
instructions than the base (per-operation counts, section 3).

- **One row per class decided while the records are read.** Each class keeps
  one holder: a later record that is deeper takes it from the earlier one
  (whose `CPV_CLS` goes 0), one that is not is 0 itself - `vx_find`'s rule
  (deepest, ties to the first) as a tournament, transitivity making the
  single pass exact. `cpv_reach` (68 bytes) and its two passes over the
  records go; `CPV_CLS` bit 5 now marks a **16bpp** record, so `cpv_dbit`
  is a shift and `and`, and 0 is "no row"; the filter's tabs hold depth BITS
  (All = 7), the rows filter is one `test`; `.depth`/`.depthb` go; the tab
  labels are copied inside one `CSDO_ON` (kern_mega: one far call, not one a
  byte); `CPV_NTAB` gone (only its clamp read it).
- `cpv_bsel`: build, the running record's row (`repne scasb`) and the top -
  the fresh page and the adapter press. `cpv_rowof` goes.
- `cpv_sclass` answers in ZF: `CPV_LIVE`'s bit 1 and the three `test`s that
  read it go; `cpv_msrec`, `cpv_aron` shared; `cpv_ctlok` and `cpv_hit` end
  in `CLC_OR_STC`; `cpv_testing` is two `cmp ..., 1` (-5).
- `cpv_row` pads with `repne scasb`/`rep stosb` (-12); `cpv_srow` copies its
  label itself and leaves SI past it, so the radios' and the check boxes'
  labels are walked as runs (adjacency asserted after the strings); `cpv_rrow`
  for the black-on-white rows to the page's right (three sites); the preview
  keeps X, Y and the depth on the stack and divides by registers
  (`CPV_GX/GY/GD` gone, -22); `cpv_new` one word store.
- Tables: `cpv_slot` (kind and bit pairs, `cs lodsw`), `cpv_cols` (the five
  depths >> 2 index a word table: constant time where the chain took up to
  five tests), `cpv_geo`'s planar depth; `cpv_test` stores its four bytes as
  one `stosb` run; `cpv_revert` reads kind and class as a word; `cpv_big`
  goes (`cpw_big` is the same test).
- Order: `cpv_rbox` falls out of `cpv_page`, `cpv_ctl1` out of `cpv_kbox`,
  `cpv_srow` out of `cpv_ctls`; `cpv_click` laid out so its nine relaxed
  conditional jumps are short (-27).

Strings: the same `db` strings in the same order (`tools/guidelock.py`: 0
owed). State bytes that changed meaning (bit 5, the tab bits, the dead
`CPV_NTAB`/`GX/GY/GD`, `CPV_LIVE` bit 1) were normalised in the comparison
and nothing else was masked but two image addresses (`CPKT_ROW`, `CPK_S_I`).

### 2.2 A press redraws what it changed (`169971e30`) - image +36, file +38

SPEC.md 135.9.2's own paragraph, which the code did not keep (CLAUDE.md,
Performance rule 1: "a repaint of more than changed is a defect"). Proven
by the same harness in FRAMEBUFFER mode: a model framebuffer (fills; runs
through a real 8x8 face; blits; buttons, glyphs and scroll bars stamped as
coded rects) must be identical after every event, with the persistent state
and the acting gate ops (VIDSET, VIDARR, WDSET, VGC, REPOST, arms) in the
same order - 7,686 scenario-steps, 0 differences; no event writes more
pixels twice than the base did.

- the adapter press redraws the two rows that changed (it redrew all four
  slots) - `cpv_arows` takes the rows as `[vid_avail]` bits in BH, 80h the
  empty slots - and the preview's and the Modes group's INSIDES only
  (`cpv_prevc`, `cpv_modesc`: a box and its title never change after the
  paint);
- a filter tab re-filters the rows from the records the last paint read
  (`cpv_build.rows`) instead of asking the card for every record again;
- a press redraws the controls it can change - the startup box and its
  label, Apply and Test... - and Force Color only on its own press, which
  draws its glyph alone;
- the startup box no longer redraws the Running mode group, which names no
  startup mode (SPEC.md 135.9.1). SPEC.md 135.9.2 now says all of this.

### 2.3 VXV_INFO (`5dd3eaa53`) - VESA.DRV image -10, file -10

Cold. The KB a record's framebuffer needs is one `div` of (bytes + 1023) by
1024 (bytes under 4096 x 768: no overflow); the card answer restores
`vx_cur` with `pop`/`xchg`; the out-of-range refusal shares the record
answer's tail through the skip byte where it was a relaxed jump. Unicorn
(`vxi.py`, scratch): VXV_INFO on 5,000 random tables, every register, CF
and the table agree but for two non-answers - DI on the card answer is
`vx_choose`'s pointer (compared as an index), and CL for a record whose X no
class byte names (dsp1's open 9.3) was the 06h a `mov cl, 6` left and is
now the 00h `mov cx, 1024` leaves: neither has `VXC_SET`, which is all its
one reader (`cpv_build`) tests. A mutation (the `adc` dropped) goes red.

### 2.4 VX_FONTRUN's one-pass rows (`fe1d629bc`) - VESA.DRV image +85, file +77

HOT (the VESA desktop's text, selector 15). A glyph row whose eight pixels
end short of the window's last byte - no VXW would fire, DI + 8 (or + 16)
does not carry - goes down as one `stosb` (8bpp) or `stosw` (16bpp: the two
words looked up once a run, `vx_fw`/`vx_bw`, +4 bytes of state) loop; a row
that reaches the edge takes the old per-pixel `vx_px` loop, so every window
crossing happens where it did. The cell loop reads its character once (a
second read and a dead `mov ah, al` gone). Unicorn (`vxf.py`, scratch): a
VBE whose 4F05h banks a multi-page framebuffer (the window's 64KB saved and
restored per switch, a BIOS that spends BX-DI), the kernel's cells behind
the pointer bank, a random face with CP850 spans, 8/15/16bpp, five
granularities, padded strides, runs on window-edge rows and off both edges:
every framebuffer page, `gfx_color`, the registers out, CF, `vx_win` and the
4F05h count agree on 1,100 runs; a mutation of the 16bpp edge test goes red.
**55% of the base's instructions** (18,109,861 -> 9,959,599 over 800 runs),
the same 13,744 window switches. The claim is 7,680 bytes either way.

## 3. SPEED

Counted by the harness on one scripted visit per machine (`measure.py`,
scratch): primitive calls (fills, runs, blits, buttons, scroll bars, gate
glyphs - the chrome's included in a paint) / text cells in the runs /
VXV_INFO calls / module instructions, base -> tip. Nothing here is an XT
time; on the XT a primitive's fixed part is ~756 us (CLAUDE.md), so the
two-adapter press below is ~21 ms of fixed cost lighter, PREDICTED.

VGA with a second (CGA) card - what an XT with VGA shows:

| operation | primitives | text cells | VXV_INFO | instructions |
|---|---|---|---|---|
| open the page (full paint) | 171 -> 171 | 671 -> 671 | 0 -> 0 | 36,412 -> 34,430 |
| adapter press + release | **69 -> 41** | **345 -> 241** | 0 -> 0 | 8,584 -> 4,947 |
| Force Color press + release | **11 -> 2** | **50 -> 0** | 0 -> 0 | 3,161 -> 1,593 |
| Test... (press: the switch) | 1 -> 1 | 0 -> 0 | 0 -> 0 | 1,180 -> 1,149 |
| a countdown tick | 4 -> 4 | 33 -> 33 | 0 -> 0 | 756 -> 608 |
| Keep | 18 -> 18 | 78 -> 78 | 0 -> 0 | 2,391 -> 2,072 |

VESA running at 800x600x16, QEMU's ten records:

| operation | primitives | text cells | VXV_INFO | instructions |
|---|---|---|---|---|
| open the page (full paint) | 214 -> 214 | 1,091 -> 1,091 | 22 -> 22 | 46,982 -> 41,006 |
| adapter press (to VGA) | **69 -> 41** | 345 -> 241 | 12 -> 12 | 10,740 -> 5,483 |
| adapter press (to VESA) | **124 -> 96** | 761 -> 657 | 20 -> 20 | 19,997 -> 12,932 |
| filter tab | **84 -> 72** | 398 -> 361 | **16 -> 5** | 13,487 -> 7,757 |
| filter All | **93 -> 81** | 572 -> 535 | **19 -> 8** | 16,480 -> 10,183 |
| table row | **44 -> 32** | 212 -> 175 | 2 -> 2 | 5,866 -> 4,257 |
| startup box | **64 -> 43** | 592 -> 489 | **9 -> 7** | 13,336 -> 8,849 |
| a countdown tick | 4 -> 4 | 33 -> 33 | 0 -> 0 | 756 -> 608 |

The page's open (the module's read and the claim) is cpwshell's; the page's
first paint is unchanged in calls and 5-13% lighter in instructions.

VESA.DRV's text (section 2.4): 55% of the instructions, same window
switches. `VXV_INFO` is cold (the panel only).

No MartyPC session was taken: no design here waited on a time, and the
harness counts are exact; the counts above are the speed record.

## 4. REFUSED

- **`cpv_rect` as words** (no byte reads): +15 (the table doubles). The byte
  table stays.
- **`cpv_hit` with a mask of the live controls computed once**: about -6,
  but it needs a register the loop does not have; not done.
- **The radios' and buttons' labels walked by skipping strings** (no
  pointer table): -3 for the buttons, but ~36 characters skipped every paint
  (~190 us on the XT): slower, refused. The radios' walk (taken) costs
  nothing: their labels are drawn in that order anyway.
- **`cpv_rbox` -> `cpv_kbox` relaxed jump** (3 bytes): every order that
  shortens it lengthens another.
- **Re-wording or merging any string** (e.g. `Auto` + padding + `(best)` as
  one, -5): strings are behaviour and the guide's lock fingerprints them.
- **VESA.DRV: a one-pass row for 16bpp alone** (~20 bytes less than both):
  8bpp modes are the common real-card case, so both depths were taken.
- **VESA.DRV: `vx_attach`/`vx_offer` cuts**: they live in the attach-only
  region padded to `VX_STK` (898), so bytes there buy no image.

## 5. WANTS THE OWNER

- **Taken, but say so: VESA.DRV +85 image / +77 file for 1.8x fewer
  instructions in VX_FONTRUN** (section 2.4). The claim does not move (7,680)
  and no 360KB cluster moves; the commit (`fe1d629bc`) stands alone and can
  be dropped.
- **Taken, but say so: CPWIDE.DRV +36 / +38 for the press redraws**
  (section 2.2), filed as defects against SPEC.md 135.9.2's own paragraph.
- dsp1's **9.3** (an unnameable VBE mode) is still open: `vx_offer` accepts
  widths and heights no class byte names (768, 960; 576, 720), and VXV_INFO
  answers CL without `VXC_SET` for them (00h now, 06h before); the Display
  page shows no row for them. dsp1's ~+6 byte refusal at offer time stands.

## 6. WANTS AN ABI BREAK

None. `kernel/vxabi.inc` untouched; the module ABI, the gate's ops and the
working area's map unchanged.

## 7. CROSS-FILE

- **cpwshell (`cpwide.inc`)**: `cpw_vid.inc` now calls `cpw_big` (it had a
  byte-identical copy, `cpv_big`) and enters `cpw_click.list`, `cpw_small`,
  `cpw_org`, `cpw_sty`, `cpw_strcat`, `cpw_utoa`, `cpw_gate` as before. It no
  longer relies on `cpw_strcat` leaving SI past the NUL (its own `cpv_srow`
  copy does). `CPW_W_*`/`CPW_WSZ`/`CWD_*` are used as symbols only; nothing
  assumes ES is a claim of its own.
- **cpwshell (`cpwide.inc`), rule 2**: the chrome's full paint writes about
  13,900 pixels twice on 616x408 - `cpw_list` lays the ground under every
  row's icon and name and then blits and runs over it, `cpw_hdr` fills the
  strip and then draws its icon and two runs over it (the harness's
  double-write count; the Display page's own drawing writes none twice).
- **cpwshell (`cpwkit.inc`)**: `cpk_group` draws its left and right rules
  down to the bottom row and the bottom rule across them: 2 pixels a group
  written twice (5 groups on this page).
- **cpwshell**: SPEC.md 135.12's cost table carries per-wave history; the
  module's figures after dsp2 belong with the DAT fold's. This note's
  CPWIDE.DRV figures are against the brief's base, before that fold.
- **coordinator**: `DRVM_IMG_VESA` unchanged (15).

## 8. ROWS TO RUN

- CPWIDE.DRV's Display page: `cpwide` (the one row that opens the wide face;
  it visits Display, QA-3), `megamodcache` and `syscheck` (they open the
  panel on a VGA desktop). Fast: `cpwdat`, `guidelock`, `ovlchk`,
  `stkbalance`. (`vesacp` and `vesakbd` are pinned to the compact face, so
  they are VESA.DRV's rows here, not this page's.)
- VESA.DRV: `vesa`, `vesa8`, `vesacp`, `vesashut`, `vesablitd`,
  `vesablit4`, `vesafsx`, `vesapref`, `vesagor`, `vesasu`, `vesabench`,
  **`vesakbd`** (CP850 text through VX_FONTRUN - the row for 2.4),
  `mixervesa`, `boratypevesa800`, `boratypevesa1024`, `megatree`; kern_mega's
  ports `mega-vesa`, `mega-vesa8`, `mega-vesacp`, `mega-vesablit4`,
  `mega-vesafsx`, `mega-vesashut`, `mega-vesakbd`. Fast: `drvmem`, `vidext`.

## 9. LOOKED

One boot, QEMU, `build/vesa.img` at the tip (1024x768x16 on QEMU's VBE): the
wide Control Panel (760x520) opened, the Display page selected, then the
VGA adapter row, the VESA row, a table row and the `256` filter tab pressed,
a screendump after each. Every line of text (VX_FONTRUN's new rows) crisp;
the adapter press re-barred VGA and unbarred VESA with the CGA row and both
group boxes untouched; the `256` filter listed Auto and the four 8bpp rows
with Auto selected and the startup box greyed and ticked; the preview
followed each selection.

## 10. DEFECTS FOUND

1. **FIXED: the Display page redrew more than changed** against SPEC.md
   135.9.2's own paragraph: all four adapter slots on an adapter press, both
   group boxes on every press, the Running mode group on a startup-box
   press, Force Color's label and box on every press, and every record
   asked again on a filter tab (section 2.2). Found by reading, measured by
   the harness.
2. **Not a defect, recorded**: the chrome's double writes and `cpk_group`'s
   corners (section 7).
3. dsp1 9.3 remains (section 5).

## NOT REACHED

- VESA.DRV's other per-pixel bodies (`VX_BLIT1`, `VX_BLIT4`, `VX_ICON`,
  `VX_GRAY`, `VX_PAT`): each puts a pixel through `vx_px` (a call and, at
  16bpp, a push/lookup/pop) where a row the window holds whole could be one
  pass as VX_FONTRUN's now is. Priced at ~40-60 bytes each for similar
  ratios; `vxf.py` extends to their selectors.
- The countdown tick (`cpv_kline`): already one ROW; nothing left there.
- No MartyPC session (section 3).
