# Driver size pass 2: `cpwpages`, the wide Control Panel's Drivers and Theme pages

Branch `dsp2-cpwpages`, cut from `1b01907f1` (the brief). Agent `cpwpages`
(BRIEF.md 2) owns `kernel/cpw_drv.inc` (the wide Drivers page, SPEC.md
135.8) and `kernel/cpw_thm.inc` (the wide Theme page, SPEC.md 135.11): 2,979
and 1,794 bytes of `CPWIDE.DRV`'s `.modv` at the base, never size-passed
(the module is new since dsp1's tip `e7668bd73`, so dsp1 has no note, no
refusal and no queue for it).
Every routine of both files was read and rewritten where a shape was found;
the speed work is the Drivers page's row, its DETAILS box, its filter strip
and its keyboard scroll, and two pixel-only trims on the Theme page's cards.

**Every change draws the same pixels.** One MartyPC session
(`os8088_xt_vga_144`: an XT at 4.77 MHz with a VGA and 1.44MB drives, BRIEF
0.2) drove sixteen gestures on the base and on the tip and compared the
panel's pixels after each (the VGA planes read whole: section 3); a QEMU
VESA 1024x768 run did the same at the 760x520 window, where the Drivers
page's columns gain air (section 9). Every gesture: same pixels.

## 1. BASE AND TIP

Measured from this worktree's own builds: `make -j2`, `make -j2 emu`,
`make -j2 mega` at the base (`1b01907f1`, build 445) and at the tip.
"image" is `MOD_H_IMG` (the bss tail, `MOD_H_SCR`, is 26 bytes on both
sides and unchanged); "file" is the lz4 file on the disk.

| kernel | image base | image tip | | file base | file tip | |
|---|---:|---:|---:|---:|---:|---:|
| kern_big | 13,763 | 12,921 | **-842** | 11,653 | 11,279 | **-374** |
| kern_emu | 13,763 | 12,921 | **-842** | 11,653 | 11,280 | **-373** |
| kern_mega | 13,793 | 12,951 | **-842** | 11,670 | 11,298 | **-372** |
| kern_small | - | - | | - | - | (SPEC.md 135 is kern_big/emu/mega only) |

By file: `cpw_drv.inc` **2,979 -> 2,436 (-543)**, `cpw_thm.inc` **1,794 ->
1,495 (-299)** (`tools/os88rdiff.py kernel 1b01907f1 .`: the shell, the
kit and the Display page are instruction-identical, shifted).

**Heap.** `mod_need` claims the unpacked file (`drv_find`'s size off the
directory hint, the bss tail being the file's last bytes) rounded to whole
512-byte granules (`mem_bytes_gp_x`): 13,763 -> 12,921 bytes is **27 -> 26
granules, one granule (512 bytes) less heap while the wide panel is open**
(derived, not measured; the brief's 14,336 for the base claim is one granule
above this derivation, and cpwshell's heap figures for the fold will say
which is right - the difference is the same granule either way).

**Disk.** The file is 23 sectors either way (11,653 and 11,279 bytes), so
**0 clusters** on the 1.44MB and 1.2MB system disks (23 of 512 bytes) and
the 720KB one (12 of 1KB); the 360KB system disk does not carry
`CPWIDE.DRV` (SPEC.md 135.2). `tools/os88diskuse.py --diff` against
this worktree's base: **+0 free clusters on all ten 360KB images** (none
carries the module). **The read is the same transfer**: one
file of 23 sectors, so no `int 13h` call is added or saved at the open.

**Resident.** `cmp` of `build/kernel.bin` and `build/smallk/kernel.bin`
against the base at one build number (445, before the first commit):
**identical**. kern_big's, kern_emu's and kern_mega's at the tip (build
447) against the base's (445): **three bytes each, the build number and
nothing else** (`cmp -l`: its last digit in the About text and the build
word twice).
No `MODS_SIZE`-style immediate moved (CPWIDE.DRV is read whole; nothing
resident is sized by it but `MOD_MAX_KB`, which it stays far under).

## 2. TAKEN

All in `kernel/cpw_drv.inc` and `kernel/cpw_thm.inc`; nothing hot (the
module is a Control Panel face), everything on a path someone waits on, so
each item's speed is in section 3. Equivalence: the MartyPC and QEMU pixel
compares (sections 3 and 9) for everything that draws, and a reading of
every changed routine against its base (recorded per item).

**The Drivers page (-543 image, -226 file)**

1. **The row in spans from a table** (`cpd_row` 495 + `cpd_g` 10, `cpd_ip`
   15, `cpd_rfill` 38, `cpd_gap` 16, `cpd_rrun` 19, `cpd_stat` 46 = 639 ->
   `cpd_row` 288 + `cpd_rects` 48 + `cpd_rtg`/`cpd_rtp` 58 + `cpd_rowp` 11
   + `cpd_name` 18 shared = 423). Every x a row is laid at is worked out ONCE
   a paint into the page block (`CPD_XA`, thirteen words, content-relative),
   and the ground and the badge's paper are a table of (x slot, x slot, y,
   y) spans one interpreter lays. **Twelve ground spans where there were
   fourteen** (rows 0-2 and 15-17 laid as wide strips past the icon rather
   than per column), and on a window wider than 616 the air between the
   name and the badge, and between the badge and the memory, is the runs'
   own spaces (the name padded to the badge, the memory's run started at
   the badge's end with the air as leading spaces) instead of two more
   fills. So **a row is 19 primitives at either width** (21 at 616 and 23
   at 760 before). Equivalence: the twelve spans, the two paper spans, the
   icon, the three runs and the box tile the row exactly as before
   (checked span by span against the base's sixteen fills, rows 0-17 by
   column band: `cpd_rtg`'s comments name each); same pixels on the glass
   at 616 (MartyPC) and 760 (QEMU). The memory figure
   is at most 7 characters (`~63.5K+`: a driver's claim is under 64KB), so
   the 8-cell column it is padded into never spills.
2. **DETAILS draws its icon and each button only when that look is not
   already on the glass** (`cpd_det`, `cpd_btn`; `CPD_DIC` and
   `CPD_DBT[4]` in the page block, 0FFh = not drawn, which `cpd_paint`
   writes before its ground fill). The look is computed from the live state
   every time and compared, so a skipped draw is pixel-identical to the
   draw: nothing but `cpd_paint`'s ground covers DETAILS, and every way a
   page or the window is repainted goes through `cpd_paint` (`cpw_paint`,
   `cpw_select`, `cpw_dsync`, `cpw_listev`'s other branch, a fresh entry
   after Theme, Display or the Ports view). The cache is five bytes of
   the page block and about twenty of code, inside `cpd_det`'s and
   `cpd_btn`'s figures.
3. **A filter change draws the two tabs whose look changed** (`cpd_tabs`
   takes a bit per category to draw and steps past the rest at
   `cpk_tabs`' widths, 9 + 8 a character; `cpd_tabhit` 81 folded into
   `cpd_click`'s `.tabs` with the same walk). The strip is All, then the
   categories in `CPD_MASK`, whose bit 0 is now All's (set by `cpd_build`),
   so one loop over `cpd_cn` (All first) draws, steps and hits. Same pixels:
   the tabs not drawn are the ones whose ground, ink and x did not change.
4. **A keyboard scroll moves the thumb** (`cpd_setsel`'s scroll branch:
   `cpk_tbrows` + `cpk_tbsb` + `os88ui_sbmove` - the kit's own bar-arrow
   sequence, SPEC.md 13.10.4 - where it called `cpk_table`, the rows AND
   the whole bar). The bar on the glass always reflects the current top
   (every top change but this one already goes through `cpk_table` or
   `cpk_tbclick`), so moving the thumb is the bar `cpk_table` would draw.
5. **`cpd_paint` with `cpd_geo` inlined and laid out by `stosw`** (the
   table block's X/Y/W/RH, the DETAILS cache, the column air, the box's top,
   `CPD_XA`): 126 + 118 -> 208, 8-bit divisions instead of 16-bit ones, the
   fresh entry's top found after one `cpd_build` call site instead of two.
   Layout checked: `CPKT_X/Y/W/RH` must stay 0, 2, 4, 6 (a division by zero
   at `cpd_rtp`'s terminator stops nasm if the kit moves them - an `%if`
   cannot see `cpwkit.inc`'s equs, the kit being included after this file).
6. **`cpd_build`** 164 + `cpd_cat` 14 -> 139: dead callee-saves (its
   callers - `cpd_paint`, the filter strip, `cpw_listev` - keep nothing
   across it), the row in CH so CL is the shift count without a push, the
   place found as `lea si, [bp - CPD_ROWS]`, the not-listed tail in DL with
   no reload of N.
7. **`cpd_hdr`** 196 + `.air` + the four padded heads (59 bytes of strings)
   -> 155 + `cpd_hd` 14 + three short heads (the Memory head is `cpd_n6`,
   the tab's label): the line is spaces to the table's right with each head
   laid over them at its cell + the air before it.
8. **`cpd_det`** 274 + `cpd_dl` 19 + `cpd_wc` 23 -> 211 + 31 + `cpd_dlb` 3
   + `cpd_sp` 12: the four "none selected: a blank" preambles are one call,
   `cpd_dlb` gives black-on-white to five lines, the icon by `xlat`, the
   description's field through `[es:bp+si]`, the text width computed in
   `cpd_dl` (no `cpd_wc` call, no saves).
9. **Small ones.** `cpd_memstr` 61 -> 47 (`stosb`/`stosw`, dead saves),
   `cpd_cpyn` 21 -> 18 (`stosb`; the read stays `mov al,[si]`, section 4),
   `cpd_pad` 16 -> 14 (`rep stosb`), `cpd_blit12` 82 -> 77 (`cs lodsw`,
   `stosb`), `cpd_row1` 66 -> 41 (no saves, the row's top by an 8-bit
   multiply; the row painter's CX/DI are the block's), `cpd_page` 44 -> 31,
   `cpd_bflags` 79 -> 61 (one load test splits the three buttons),
   `cpd_bhit` 55 -> 46 and `cpd_btn` (the button table holds content x's
   and width - 1), `cpd_rel` 120 -> 110 (Load/Unload is `CPG_DRVON` + the
   button, asserted), `cpd_key` 41 -> 30 (no 0FFFFh test: with nothing
   selected there are no rows, and either key is past the end), the badge
   papers inside the label table (`cpd_pl`, 14 bytes a badge, `cpd_pc`
   gone).

**The Theme page (-299 image, -148 file)**

10. **`cpt_elems`** 94 + `cpt_dec` 15 + `cpt_rect` 63 -> 100: the four
    coordinates in one loop over X0/Y0 and R/B (`xor bx, CPT_X0 ^ CPT_Y0`
    alternates them; `; STKBALANCE-LOOP:` names the four pushes), the pen
    resolved once before them, `[gfx_color]` untouched for a dithered
    desktop exactly as before. It keeps BP now, which two callers use.
11. **`cpt_geo`** 71 -> 51 (six consecutive words by `stosw`, asserted);
    **`cpw_thm_paint`** 332 -> 264 (the ground is `cpd_ground`, shared with
    the Drivers page; the swatches' row source walks instead of multiplying
    and their far edge is set once; the saver's origin by `stosw`);
    **`cpt_card`** 362 -> 288 (the row copied before the geometry so AL is
    not reloaded, the face byte in one store, the live flag kept in BP from
    the ring, the live bar's four spans from two registers, `cpt_ntw`
    holding the label widths that `cpt_nlen` held as lengths).
12. **`cpw_thm_click`** 289 -> 242 and **`cpw_thm_up`** 76 -> 56: the
    small-state check `cpw_click` already made (`cpw_big`) and the
    `cpw_org` `cpw_edge` already made are gone; range tests as one unsigned
    compare; 8-bit divisions for the card and the swatch; the
    Customize.../Settings... op is `CPG_THMCUST` + the button (asserted);
    the push/pop of four registers round `cpk_button` (which keeps them)
    gone. The preset install restores ES with `push es`/`pop es` instead of
    `mov es, [cs:cpw_dseg]` - three bytes, and the page no longer names the
    claim word cpwshell's fold of `CPWIDE.DAT` replaces (section 7).
13. **The cards' miniatures write fewer pixels** (0 bytes): the desktop
    rect starts at row 12, under the menu bar and its rule, and the
    window's face at row 26, under its title bar - each the rows the later
    rect covered whole. 19 rows fewer per card, and a dithered desktop
    keeps its phase (`gfx_fill_gray` is by screen parity). Same pixels
    (MartyPC, gesture 15; QEMU, gesture 7).

## 3. SPEED

**Instrument**: `cpwmeasure.py` in the scratch directory, built on
`tools/os88hot.py`'s `Run` (aligned to IRQ0, the window from the first
input to the last `gfx_unlock`, guest cycles at 4.772727 MHz) with LOGGING
breakpoints on every drawing primitive's entry (`gfx_fill`, `gfx_hline`,
`gfx_vline`, `gfx_frame`, `gfx_fill_gray`, `gfx_fill_pat`, `gfx_blit4`,
`gfx_blit1`, `gfx_xor_rect`, `gfx_xor_fill`, `gfx_scroll`, `font_run_x`,
`font_char`, `font_str_x`); after each gesture the VGA planes were read
whole (the `planes` verb, no guest cycle) and the panel's content box less
its status line compared (the status line's free-KB figure moves with the
claim by design). Machine `os8088_xt_vga_144`, the 616x408 window, 12
`drv_tab` rows (10 shown). One session: the base image (the tip's disk with
the base `CPWIDE.DRV`, same build number and layout stamp) and the tip.

| gesture | base | tip | calls base -> tip | pixels |
|---|---:|---:|---|---|
| the Drivers page's first paint (from the list) | 1,433 ms | 1,402 ms | 336 -> 316 | same |
| a row clicked (two rows, DETAILS) | 424 ms | 383 ms | 77 -> 45 | same |
| Down / Up (two rows, DETAILS) | 410 / 397 ms | 371 / 357 ms | 77 -> 45 | same |
| Down at the last row shown (a scroll) | 1,083 ms | 1,006 ms | 269 -> 204 | same |
| Up at the first row shown (a scroll) | 1,100 ms | 1,022 ms | 269 -> 204 | same |
| a filter tab (Display: one row) | 451 ms | 378 ms | 125 -> 65 | same |
| back to All | 1,168 ms | 972 ms | 311 -> 232 | same |
| a filter tab (Storage: three rows) | 586 ms | 508 ms | 165 -> 101 | same |
| back to All again | 1,149 ms | 968 ms | 311 -> 232 | same |
| the scroll bar's down / up arrow (the kit's: every row) | 849 / 854 ms | 825 / 826 ms | 217 -> 197 | same |
| a Start at boot box (one row) | 104 ms | 102 ms | 21 -> 19 | same |
| the Theme page's paint | 484 ms | 474 ms | 174 -> 174 | same |
| the Drivers page after Theme (a fresh entry) | 1,410 ms | 1,382 ms | 336 -> 316 | same |

By primitive, a selection: `gfx_fill` 52 -> 28, `font_run_x` 16 -> 12
(the four button labels), `gfx_frame` 4 -> 0 (the four buttons), `gfx_blit4`
5 -> 5 (two rows' icon and box, and DETAILS' icon, whose category changed
between those rows). A tab back to All: `gfx_fill` 236 -> 171, `font_run_x`
47 -> 38, `gfx_frame` 6 -> 2, `gfx_blit4` 21 -> 20 (DETAILS' icon kept).

**What the numbers say about the next pass.** A table row is ~85 ms of
the XT's time whatever it shows (the Start at boot gesture: one row and a
gate call, 89 ms busy) and is 19 calls; a selection's DETAILS is ~190 ms
without its buttons; the Theme page is 174 calls in 0.47 s; the Drivers
page's first paint is 1.4 s, of which the ten rows are ~0.85 s. The disk
open of the face is cpwshell's (BRIEF 0.3).

## 4. REFUSED

- **`lodsb` in `cpd_cpyn` (-2 bytes)**: `os88ovlchk` refuses `lods` in a
  module image (SPEC.md 2.8.6), and its one waiver is for a body copied out
  of its image; DS here is the string's (`cpk_ds`), but the rule is the
  rule. Spelled `mov al, [si]` / `inc si`.
- **Trailing spaces as a fill** (the DETAILS lines are padded to 52 cells,
  the name to 22): on the VGA run a repeated trailing cell is one
  `rep stosb` a row (SPEC.md 6.1.8, 6.1.10), so a fill in its place is a
  call more for cells that cost little. Not taken.
- **A `gfx_scroll` for the keyboard and bar scrolls** (one move and two
  rows instead of ten): SPEC.md 5.5 moves byte columns only, and a row is
  content x 129 to 593 in a window whose x is wherever `wm_fit` put it, so
  its ends are not on the byte grid; the strips either side would be
  per-row calls again. Not taken.
- **The icon blitted with its margins** (a 20x18 cell: four fewer ground
  spans a row): the planar decoder prices a detailed row at 107 cycles a
  pixel (SPEC.md 5.4.1.3), so the four extra columns on 16 rows cost about
  what the four spans do, and it is a second icon stager beside the kit's.
  Not taken.
- **The Theme cards in non-overlapping spans** (no pixel written twice):
  the miniature is drawn in painter's order (the frame under the face, the
  swatch's black under its two colours, the saver's black under its stars,
  the Windows card's desktop under its taskbar); a tiling of the same
  pixels is two to four times the calls, and a call is the price. Item 13
  takes the two overlaps that cost nothing to remove.

## 5. WANTS THE OWNER

None. Every item draws the same pixels; the only differences are what is
drawn in between (a skipped repaint of an unchanged button is not drawn at
all, and a row's spans go down ground first, then the badge's paper, the
icon, the runs and the box, where they went down column by column).

## 6. WANTS AN ABI BREAK

None. No module header, entry, gate op, `CWV_*` event, `CPWIDE.DAT` field
or kit contract moved.

## 7. CROSS-FILE

- **`cpd_build`'s contract** (called by `cpwide.inc`'s `cpw_listev`) is
  now "AX BX CX DX SI DI BP spent" (it kept all): `cpw_listev` keeps
  nothing across it (`call cpd_build` / `mov bx, CPD_TB` / `call
  cpk_table` / `jmp cpd_det`), and no other caller outside this file
  exists. cpwshell: do not hold a register across it.
- **`cpw_under` (`cpwide.inc`, cpwshell's)** is `cpd_groundb` with BX =
  `CPW_HB`: `mov bx, CPW_HB` / `call cpd_groundb` at its one call site in
  `cpw_page`, and the routine goes: **-23 bytes**, same pixels.
- **`cpw_listev`'s `.same` branch** (a driver came or went while Drivers
  shows) calls `cpk_table`, the rows and the whole bar; `cpd_build` there
  keeps N (`drv_tab`'s rows do not change) and clamps the top it already
  had, so `cpk_tbrows` (the rows alone) draws the same pixels: **-16
  calls** on that path, 0 bytes.
- **The working area's map (SPEC.md 135.5.1)** is unchanged outside the
  page block; inside it the Drivers page's map moved (CPD_DIC, CPD_DBT,
  CPD_MASK, CPD_KC, CPD_GT, CPD_XA, CPD_ROWS; `CPD_ROWS + DRV_MAX` = 307 of
  the block's 320, `kernel.asm`'s check still holds). Both files name
  `CPW_W_*`, `CPW_WSZ` and `CWD_*` as symbols only, and `cpw_thm.inc` no
  longer reads `cpw_dseg` (item 12), so the fold of `CPWIDE.DAT` into the
  module (BRIEF 0.3) lands under these pages without a textual conflict.
  The DAT's description offsets are read as `CPW_WSZ + offset` in
  `cpd_det.desc` - the name the brief says the fold keeps for "the DAT's
  offset in ES".
- **SPEC.md 135.12's cost table** is cpwshell's to restate after the fold;
  this pass's figures are in 135.8 and 135.11 (and this note).
- `cpd_blit12`, `cpd_ck0` and `cpd_ck1` keep their contract for
  `cpw_vid.inc` (the Display page's tick boxes).
- Attach-only code: none (a module has no attach, SPEC.md 2.8.3).

## 8. ROWS TO RUN

- **`cpwide`** (soak, QEMU): the one row that drives the wide face - the
  Drivers page drawn after Theme and after Display compared pixel for
  pixel with the one drawn first (QA-3), Theme, Display, Dock.
- **`buildmatrix`** (soak): the knob kernels assemble `CPWIDE.DRV` too.
- The fast tier, green at the tip: `ovlchk`, `stkbalance` (the
  `STKBALANCE-LOOP` mark on `cpt_elems`), `asmrules`, `btnrules`,
  `cpwdat`, `kernbudget`, `layout`, the image gates.

## 9. LOOKED

QEMU's VGA with VBE at 1024x768 (`build/vesa.img` at the tip and the same
disk with the base `CPWIDE.DRV`), the 760x520 panel: the Drivers page, a
row, Down, two filter tabs and All, Theme, Drivers again - screendumps of
the panel's content box less the status line, **identical base to tip in
all eight**, and the tip's Drivers page looked at (the columns' air at 760,
the twelve rows, DETAILS with Load live and Unload and Settings... grey).
This and section 3's session are the pixel proof of every drawing change.

## 10. DEFECTS FOUND

None that a user can reach. Read closely, for the record:

- `cpd_memstr`'s header said "every other register kept" while
  `cpw_utoa` spends CX and DX; its callers reloaded both, so nothing broke.
  The contract now says what it spends.
- `cpw_thm_click` re-tested the small state (`CPW_W_CW` < 614) that
  `cpw_click` had already refused, and `cpw_thm_up` re-read the content box
  `cpw_edge` had just laid out: dead, gone.
- The column heads' line and a row's memory figure are sized for the two
  windows `cpw_open` makes; a content box wider than ~950 would run the
  heads past `CPW_W_STR`'s 96 bytes (base and tip alike). Unreachable: the
  window is 616 or 760.
