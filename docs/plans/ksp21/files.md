# ksp21 agent "files" - files.inc and dskwin.inc

Kernel size pass 21 (`docs/plans/ksp21/BRIEF.md`, row **files**): `kernel/files.inc`,
`kernel/dskwin.inc`. Branch `ksp21-files`, base `3fc4e9d09` (the brief). Figures are
ASSEMBLED, `tools/kernsize.py --json` absolutes on each kernel's own tree, and
`tools/os88rdiff.py kernel 3fc4e9d09 .` for the routines. Resident = `.text` + `.bss` +
`.cold` + `.lowbss` + `.vgabuf` + `.vga`.

**TAKEN outside the row**: none. Read but not edited: `wm.inc`'s `wm_dmg_x1..y2`
(item 2 now folds into them), `ui.inc`'s `ui_rcmd` (item 3's lifetimes), `desksc.inc`'s
`sc_m_move` (the same), `toast.inc`, `memory.inc`. `SPEC.md` follows the three internals
that moved: 29.1.1 and 66 (`fm_reloc`), 22.3.1 (the paste's union).

**dskwin.inc** is one 512-byte sector buffer and its pad in `.lowbss`: nothing to take.
**files.inc had no unsized kern_big bytes**: every change since `c0eedd5f4` is kern_mega's
FAT32 arm, which the `CLU_*`/`FS_CWD_*` macros assemble to nothing elsewhere. So this is a
sweep of the whole file, and the finding is that three shapes were left in it: **exits that
a neighbour already has** (a near `jmp kretc_di`, `jmp fm_edit_arm`, `jmp fm_go` each
written several times inside 127 bytes of one another - 30 bytes of the total), **.bss
cells whose lives never meet** (20 bytes, every later word at its parity), and **two
copies of one rect** (the paste's private union, copied into the damage rect it was built
for).

## BASE AND TIP

| kernel | base `3fc4e9d09` | tip | delta | where | `KERN_SIZE` |
|---|---:|---:|---:|---|---|
| **kern_big** | 90,225 | **90,098** | **-127** | `.text` -20, `.bss` -20, `.cold` -87 | 95,744, unchanged |
| **kern_small** | 55,672 | **55,568** | **-104** | `.text` -4, `.bss` -20, `.cold` -80 | 57,344, unchanged (HEAP_SEG 0x0E60 held) |
| kern_emu | 90,471 | **90,344** | **-127** | as kern_big | 95,744, unchanged |
| kern_mega | 109,493 + `.mega` 24,800 | **109,366** + 24,800 | **-127** | `.text` -20, `.bss` -20 (conventional -40), `.cold` -87 (above 1MB); `.mega` 0 | conventional 61,952 of 68,096, unchanged |

`.lowbss`, `.vgabuf`, `.vga`, `.boot2`, `.ovl` and `.mega` are unchanged on every kernel.
`.bss` moved by an even 20, so no `.bss` word after this file changed parity. No module
image moved (nothing of files.inc is in one). Every package is unchanged.

## TAKEN

Bytes are kern_big (= kern_emu = kern_mega) / kern_small. Commits `158b52185`,
`fbf6df2cf`, `90d7d069b` and the tip.

### 1. `fm_reloc` by value (-16 `.text` / -) - `158b52185`

The listing cache's relocation proc walked `inst_tab` through `inst_next` for live
KIND_FILES records and compared each one's block. It now compares the five `fm_pool`
blocks' `FS_VSEG` with the old base directly - the way kern_small's `mem_evw` already finds
the same words (SPEC.md 50.6.13) - and the `[fm_vseg]` mirror as before. 47 -> 31.
**Equivalence**: two live windows never share a listing (`fmv_bcast` copies one's contents
into the other's own claim), so the word equal to the moved base is the word naming it.
The one difference is a FREE block's stale `FS_VSEG` equal to the base, which is now
re-pointed too: nothing on kern_big/emu/mega reads a free block's `FS_VSEG` - `fm_kinit_x`
stores 0 over it before the new tenant runs, and KD_INIT runs before `wm_show`
(instance.inc) - and a DYING record's block, which the old walk skipped, is now moved
correctly. Faster: five compares where it was up to INST_MAX `inst_next` calls.

### 2. The paste's union is `wm_dmg_x1..y2` itself (-23 / -23: -8 `.bss`, -15 `.cold`) - `fbf6df2cf`

`fm_paste_res` seeded `fmv_ux1..uy2` empty, folded each re-listed visible window into it,
and copied the four words into `wm_dmg_x1..y2` for `wm_dmg_wins`. It now seeds and folds
into `wm_dmg_x1..y2` directly; the four `.bss` words and the `push es / rep movsw` copy go.
**The proof is the span**: between `wm_rect_empty` and `wm_dmg_wins` the code calls
`fmv_ifirst/inext`, `wm_win_rect`, `wm_runion`, `fmv_hload` and (after the loop)
`fm_sayerr`. A static walk of the kernel's call graph from `fmv_hload` (625 routines,
pessimistic: every `call`/`jmp`/`KDOOR`/`mov reg, label` an edge, fall-through included)
and from `fm_sayerr` (28) reaches **no writer of `wm_dmg_x1..y2`** (`wm_paint_dmg`,
`wm_dock_under`), **no `gfx_unlock`** and **no `wm_draw_win`/`wm_pkgcall`**; the one yield
it reaches (`inst_park_hold`, under a compaction) keeps the gfx lock, and only a lock
holder paints. The walk cannot see a driver's `drv_fs_call` image or a package's relocation
proc - the same blind spots `tools/dsegaudit.py` names. With nothing folded, the rect is
left EMPTY where it was left stale: every reader of it is a paint pass that sets it first
(`wm_paint_dmg`'s head, `wm_dock_under`). Faster: no copy.

### 3. `.bss` cells with disjoint lives (-12 / -12 `.bss`) - `fbf6df2cf`

* **`fm_dgx`/`fm_dgy` are `fm_pressx`/`fm_pressy`** (-4). The press point is written at
  `fm_onclick_x`'s entry and read for the last time to pass it to `fm_drag` in CX/DX
  (fdlg's FDH_CLICK reads it earlier still); the outline's words are written only by
  `fm_dgmove`, inside `fm_drag`'s or DESK.DRV's `sc_m_move`'s tracking loop. Both loops are
  the UI task's own, inside a click, so no click is dispatched while one tracks.
* **`fm_vrow`/`fm_vcol` are `fm_rlo`/`fm_rhi`, and `fm_by1` is `fm_cellx`** (-6). One paint
  takes ONE arm by `fm_isicon` (`fm_draw_rcore`); `fm_scrollpaint` - the only other writer
  of `[fm_rlo]/[fm_rhi]` and the only user of `[fm_by1]` - is the list's alone
  (`fm_scroll_by` sends the icon view to `.rows`, whose `.thumb` tail reads none of the
  five), and `fm_sel_bar`'s icon arm, the other writer of `[fm_cellx]`, is the icon
  view's. Every paint holds the gfx lock.
* **`fm_wased` and `fm_rcmdid` are `fm_dgdrv`'s byte** (-2). `fm_wased` is read from
  memory only by `fm_rclick_x`, before its popup; `fm_rcmdid` is written after the popup
  and read by `ui_rcmd`, which ui.inc runs the moment `fm_rclick_x` returns; `fm_dgdrv`
  lives inside `fm_dgdrop`, a left click's drag. The two that went were above
  `fm_statowed`, so every word from there down keeps its parity, and `fm_lrec`'s and
  `fm_ftype`'s go from odd to even.

### 4. A press's two procs share their question and their tail (-10 / -) - `158b52185`

`fm_onup_x` and `fm_ondrag_x` each wrote `push ax / fm_slayout / pop bx / fm_bhit / cmp al,
bl`; it is `fm_onup_x.still` now (-3), and the release that slid off its button jumps to
`fm_ondrag_x`'s own `xor al, al / fm_setdown / kretc_di` (-7) - the same `kentc_di` frame.
H4: one call and ret more per drag event over a header button.

### 5. Near ladder jumps written short to a neighbour's (-11 / -9) - `fbf6df2cf`, tip

Nine `jmp kretc_di` (3 bytes) became `jmp short` to another routine's `jmp kretc_di` -
the same ladder, so the same frame by construction: `fmv_store` -> `fmv_fit.kret`;
`fmv_load`, `fmv_sync_x`, `fmv_mark` -> `fm_measure.out`; `fmv_bcast` ->
`fm_open_body.kret`; `fm_onup_x` -> `fm_onclick_x.out`; `fm_open_sel`, `fm_mount` ->
`fm_go.tail`; `pth_push`, `fm_settitle` -> `fm_oncmd_x.out`; `fm_edit_end` ->
`fm_repaint.done`. Chosen as one hub set that is in reach on ALL FOUR kernels: kern_mega's
FAT32 arms lengthen fm_measure and fmv_sync_x, and the first choice (`fmv_sync_x.out`)
assembled on big and small and was out of reach on mega (DEFECTS). H3/H4: one taken short
jump (~15 clocks) at the exit of each, none per row or per glyph.

### 6. One near `jmp fm_edit_arm` per neighbourhood (-9 / -7) - `158b52185`

New Folder, the multi-delete and Rename/Delete's arm share `fm_arm_sel`'s `pop ax / jmp
fm_edit_arm`; Format's `.swap`/`.arm` serve the probe (mode 5), Clone's swap prompt (mode 6,
the same `mov al, 6`) and the clone plan (mode 7); `fm_c_clone`'s refusal is `fm_cloneok`'s
`ret`, and `fm_cldrop`'s `.armed` moved to `fm_cloline.out`. H4 (menu commands).

### 7. The swap refusal says its TOASTRUN through `fm_toast_si` (-9 / -9: -4 `.text`, -5 `.cold`) - `fbf6df2cf`

`fm_editkey`'s `.swapno` went through `toast_say` with a two-entry table of its own
(`dw 0, fm_s_swapno`) for one fixed string; `fm_toast_hdr` gained a second entry,
`fm_toast_si`, one instruction down, and the site is `mov si, fm_s_swapno / call
fm_toast_si`. toast_show keeps every register, DI and the flags' consumers included.
`tests/unit/t_toast.py` follows the new entry back to the TOASTRUN (green).

### 8. `fm_hit` adds the scroll once (-6 / -6) - `90d7d069b`

`add ax, [fm_lscr]` before the view test: in the list the sum IS the index, and the icon
arm multiplies it - `((row + lscr) * cols + col)` exactly as before. The list view's DI
(the x `fm_onclick_x` reads back) is untouched. H4, one jump fewer in the icon view.

### 9. Smaller ones (big / small)

* **`fm_delrep`** reads `[ticks]` once and stamps by `add [fm_delt], ax` (then + now -
  then), no BX bank (-5 / -5). Faster (~89 -> ~68 clocks, a Delete key).
* **`fm_layout`'s icon columns** are `1 + max(0, cw-96) / 80`, one clamp and one divide, for
  `max(1, (cw-16)/80)` (-4 / -4; checked equal for every cw from -300 to 2000). The list
  arm's instructions are unchanged.
* **`fm_onclick_x`'s no-row-area press** reaches the part ladder's two pops with AL = 0
  (fm_bhit's miss), which `cbw / dec / js .rows` reads as "not on the bar" (-4 / -). The
  arms are written kern_small's first, because `tools/stkbalance.py` reads both as one text.
* **kern_small's `fm_onclick_x`**: the chooser column's press takes the scroll ladder's
  `.sbq` trampoline (`jc short .sbq`, -3) and Refresh shares the toggle's near `jmp .redraw`
  (-1) (- / -4).
* **Near-jump pairs**: `fm_choose`'s two unlocks, `fm_c_open`/`fm_arm_sel`'s
  `fm_nw_none`, `fm_c_up`/`fm_c_root`'s `fm_go`, and kern_big's `fm_c_clip`/`fm_dgarm`'s
  `fcp_arm` (-4 / -3).
* **`fm_sel_bar`**'s list arm jumps to the icon arm's `gfx_xor_fill` call (-3 / -3; one
  short jump, ~3 us, against a ~1 ms fill).
* **`fm_edit_end`**: the cloner's arm is first, so mode 6 step 1 falls into it and the
  format's drop falls into `.clrit` (-2 / -2).
* **`fm_scroll_by`'s row band**: `lea dx, [bx-FM_ROW_Y0-1]` off the BX just made, for a
  second load of `[fm_cy]` and a `dec` (-2 / -2). **Faster** (H3, a row-tier scroll: ~22 ->
  ~12 clocks).
* **`fm_editkey`'s Space** swaps the two format sizes with `rol word [fm_fmtrow], cl` (CX is
  the ladder's; `.lineonly` writes the carry) (-2 / -2; +26 clocks a keystroke).
* `fm_onup_x`'s repaint is `fm_onclick_x.redraw`'s (-1 / -); `fm_settitle` picks its default
  caption in AX (-1 / -1); `fm_draw_status` banks the mode with a push and pop instead of a
  second load (-1 / -1); `fm_cfill`'s `sub dx, 2` is two `dec` (-1 / -1, faster);
  `fm_rowdiv` loads the icon height into CL (CH is FM_ROW_H's 0, pinned by `%error`)
  (-1 / -1).
* **kern_small only**: `fmv_owner` divides by BL, the output's own byte, and widens by
  `cbw` - no CX bank (-4); `fm_kinit_x`'s stale free banks no DX (nothing reads it before
  `mov dx, FM_MIN_H`; the ladder has it for the caller) (-2); `fm_kbfig`'s two arms share
  one store, AX now clobbered - both of its calls are `fm_draw_status`'s and the next
  instruction of each writes AX (-3). (- / -9)

## HOT PATHS, PARITY AND THE DISK

* **No H1/H2 routine is touched**, and nothing in files.inc precedes a pinned one: every
  `hotpar` routine sits before files.inc in its section (`.text`: ui_task at 0x716A against
  fm_fchk at 0x8201; `.cold`: dsk_xfer, dsk_runcap, dsk_next_clus_x, gfx_blit1_x before
  fm_kinit_x). `hotpar` green at every `make`.
* H3 changed: the row-tier scroll (faster), `fm_layout` (the icon arm only), the status
  line (+~11 clocks), a selection bar (+1 short jump), the listing's exits (+1 short jump
  each, item 5). H4: the press/drag/release, the editor's keys, the menu commands, the paste
  (faster), the context menu. Each is far under 1% of its operation.
* **No `int 13h` call added or removed.** Nothing on the mount, listing, read-ahead,
  FAT-window, directory-write or loader path changed but the EXIT of `fmv_load`,
  `fmv_store`, `fm_measure` and `fmv_mark` (a short jump into a neighbour's identical
  ladder jump). Every `fmv_load`/`fmv_hload`/`dsk_chdir*` call is the same call with the
  same arguments, so the bar is unchanged: open a root 2, enter a folder 2, Up 1, a cached
  launch none (by reading; not measured).
* `tools/stkbalance.py kernel/files.inc`, base and tip: 2 and 2 (the same
  `fm_szfig_k`/`fm_ultoa_x` ladder tails pass 20 recorded) - none new; the fast tier's
  whole-kernel row green.
* `make`, `make small`, `make emu`, `make mega` at the tip; the fast tier green at every
  commit (one red `canary` was a `build/megak` map left by the failed mega assembly in
  DEFECTS, green after `make mega`). Knob kernels assembled with `kernsize`: REDRAWFULL,
  ANIMOFF, MSELOFF, SBDRAGOFF, LD_DIAG, DISK_COUNTERS on kern_big, REDRAWFULL and LD_DIAG
  on kern_small, REDRAWFULL on kern_mega (kern_small + DISK_COUNTERS trips the locked heap
  guard 1b at the base too).

## REFUSED

* **`fm_editkey`'s `jmp .text`** (-3): the dispatch's eight targets span 177 bytes of
  blocks against 107-127 bytes of short reach, so every order leaves one of them (or the
  typing block itself) long.
* **`fm_onup_x`'s `.fire` merged into `fm_ondrag_x`'s tail with a flag** (+1).
* **`fm_brect` banking AX for its two callers** (-1): an extra `pop` on each exit, and the
  chooser arm's FDH_RECT answer would have to be proved not to come back in AX.
* **`fm_statowed` as `fm_wased`** (-1 `.bss` and -3 code): a right-click followed by an arrow
  in a Save chooser's box would then repaint the status line where it does not.
* **`fm_snam` sharing a buffer**: the seed rides `inst_launch_post`, a deferred launch,
  so a whole UI turn can run between the copy and `fm_kinit_x`.
* **`fm_dgidx`/`fm_dgwin` aliased**: DESK.DRV's `sc_m_new` reads both during a desk drop.
* **kern_small-only ladder hubs** (-3 small: `fm_onkey_x`, `fm_clone_res`, `fm_sel_bar`):
  in reach on kern_small alone, so each needs an `%ifdef` round one jump.
* **`osapi_ferr_text`**: every spelling is 19 bytes without touching the ABI's AX.
* **`fmv_bcast` holding `[fm_vp]` in BX** (pass 20's, re-read): kern_big's `dsk_dest_x`
  takes BX = FV_DOFF in the loop, so it is reloaded either way.
* **`fm_stage_name`'s 16-byte copy by `rep movsb`**: +3 for the ES = DS bracket.

## WANTS THE OWNER

None. Every item is behaviour-identical; item 1's free-block re-point and item 2's
empty-rect-when-nothing-folded are invisible to every reader (stated there).

## WANTS AN ABI BREAK

None found. `OSAPI_FERR_TEXT` (`osapi_ferr_text`) is this file's one published body, and a
contract change would buy nothing.

## CROSS-FILE

* **A `.cold` HOME OF 0x0855 FAILS `coldhma.sys`** (sys `mod.inc` / wm `winmod.inc`, for
  the coordinator after the merges). WIN95.DRV's `sub dx, 7 / cmp [di+8], dx` at image
  +0x262 is the bytes `EA 07 39 55 08`, which `mod_cfix`'s scan (a far call/jmp opcode three
  bytes before the segment's two bytes) reads as a far jump naming segment 0x0855 - so
  `os88rom.py`'s `cfix_prove` refuses the build ("would re-point WIN95.DRV wrongly ... at
  +0x265"), rightly: a `.cold` slide would patch that `cmp`. The base's home is 0x0857, this
  branch's 0x0854; it passed through 0x0855 mid-branch and `make` stopped. 0x084D..0x085D
  are otherwise clear (checked by re-stamping the modules' real `.cold` words with each
  candidate home and rerunning the same scan). Every agent's `.text`/`.bss` bytes move the
  home, so the merged tree's value is the one to check - `make`'s `coldhma.sys` step does.
* **wm**: `fm_paste_res` now holds its union in `wm_dmg_x1..y2` from `wm_rect_empty` across
  the re-list loop to `wm_dmg_wins` (item 2). A wm.inc change that gives those four words a
  second tenant must keep it out of that span (mount, store, toast).
* **hw** (the `cw_` census, KERNEL-BYTE-QUEUE item 1): its files.inc rows `fm_kinit_x`,
  `fm_dgdrop`, `fm_choose`, `fm_more_mark`, `fm_dgxor` are unchanged here; `fmv_repaint_all`
  in that table no longer exists (pass 18 wrote it into `fm_paste_res`).

## ROWS NAMED (none run - the coordinator's union)

The press, drag and release (items 3, 4, 9): `fmbtn`, `fmthumb`, `sbar`, `sbardlg`,
`wheel`, `msel`, `dragui`, `deskdrag`, `desksc`, `fdlgup`, `fdlgchoose`, `fdlgsmall`,
`fdlgchsmall`, `smalllaunch`. The context menu (item 3's `fm_wased`/`fm_rcmdid`):
`lzcomp`, `desksc`. The editor and the commands (items 6, 7, 9): `fmcommit`, `fmtpair`,
`fmtreach`, `diskclone`, `czto`, `wimgtrip`, `fdswap` (the swap prompt and its refusal
toast), `fcproom`. The paste (item 2): `fcpcopy`, `fcpapi`, `fcpsmall`, `fcproom`,
`clipkeep`, `dragui`, `msel`. Compaction with Disk windows open (item 1): `regmove`,
`heapcheck`, `cmemmove`. The grid and the list (items 3, 8, 9): `icoclip`, `glyphcost`,
`fmarrows`, `fmthumb`, `bigdir`. Navigation and titles (items 5, 9): `navcalls`, `fdswap`,
`bigvol` (the status line's figures), and on kern_small `smalllaunch`, `shedrelist`.
Host: `hotpar`, `stkbalance`, `toast`, `canary` (fast tier). `buildmatrix` (soak) for the
knob kernels.

## DEFECTS FOUND

None in the shipped code. Three method notes:

* **A `short` that fits kern_big can miss on kern_mega**: the FAT32 arms (fm_measure's
  32-bit free figure, fmv_sync_x's high-word test) add ~50 bytes between fmv_load and
  fmv_sync_x, and `jmp short fmv_sync_x.out` failed to assemble there while big, small and
  emu built. Writing `short` is what turned it into an error rather than a silent 3-byte
  `jmp`; assemble all four kernels after any cross-routine `short`.
* **`tools/stkbalance.py` reads `%ifdef` arms as one text** (only KHP_* are evaluated), so a
  kern_big arm that FALLS THROUGH where kern_small's arm used to follow reads as a depth
  conflict at kern_small's first label. Putting kern_small's arm first kept the text honest.
* A label inside a `pop`-ended run that another routine jumps to (`fm_saytab.ret`) is walked
  as an entry from depth 0 and goes red; point such a jump at a routine's own `ret`.
