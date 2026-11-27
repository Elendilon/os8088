# Driver size pass 2: `cpwshell`, the wide Control Panel's shell, kit and assets

Branch `dsp2-cpwshell`, cut from `1b01907f1` (the brief). Agent `cpwshell`
(BRIEF.md 2) owns `kernel/cpwide.inc`, `kernel/cpwkit.inc`,
`kernel/cpwlay.inc`, `kernel/cpwfmt.inc`, `tools/cpwdat.py`,
`drivers/catalog.toml`, `kernel/cpwart/`'s converter inputs and
`tests/unit/t_cpwdat.py`, and for BRIEF 0.3 the files that section lists.
The first and largest item is BRIEF 0.3, the owner's instruction:
**`CPWIDE.DAT` is folded into `CPWIDE.DRV`** - one file, no required
sidecar, no extra `int 13h` at an open, and nothing read at a re-open with
the image kept.

Commits (each built with `make -j2`, fast tier green; `make -j2 emu` and
`make -j2 mega` at the tip):

| commit | what | CPWIDE.DRV image | file |
|---|---|---:|---:|
| `26a90806d` | CPWIDE.DAT folds into CPWIDE.DRV | 13,763 + 15,490 (the DAT claim) -> 29,012 | 11,653 + 5,281 -> 16,602 |
| `90bb11b57` | the assets: distinct 16x16 icons once, 44-byte catalog records; `cpw_icon` with `es lodsb` at constant offsets | -1,242 -> 27,770 | -81 -> 16,521 |
| `37c40eff1` | the shell's and kit's shapes; headings without padding cells | -98 -> 27,672 | -49 -> 16,472 |
| `b939111c8` | `cpk_group` off its own frame; `cpw_status` | -34 -> 27,638 | -12 -> 16,460 |
| (the note's commit) | `cpw_listev` repaints the Drivers rows alone (`cpwpages`' finding) | 0 -> 27,638 | +1 -> 16,461 |

## 1. BASE AND TIP

Measured in this worktree: the base from `make -j2` / `make -j2 emu` /
`make -j2 mega` at `1b01907f1` (build 445) before any change, the tip from
the same three at `b939111c8`. "image" is `MOD_H_IMG`, the bss tail's zeros
included (what the claim holds); "file" is the `'CZ'` (lz4) file on the disk.

| file | kernel | base image | tip image | delta | base file | tip file | delta |
|---|---|---:|---:|---:|---:|---:|---:|
| `CPWIDE.DRV` | kern_big | 13,763 (bss 26) | 27,638 (bss 874) | +13,875 | 11,653 | 16,460 | +4,807 |
| | kern_emu | 13,763 | 27,638 | +13,875 | 11,653 | 16,460 | +4,807 |
| | kern_mega | 13,793 | 27,662 | +13,869 | 11,670 | 16,454 | +4,784 |
| `CPWIDE.DAT` | big / emu / mega | 14,642 (+ the 848-byte working area in its claim) | - (inside the module) | -15,490 | 5,281 | - | -5,281 |
| **both** | kern_big / emu | **29,253** | **27,638** | **-1,615** | **16,934** | **16,460** | **-474** |
| | kern_mega | **29,283** | **27,662** | **-1,621** | **16,951** | **16,454** | **-497** |
| `CTRL.DRV` | big / emu / mega / small | 16,733 / 16,751 / 16,972 / 6,291 | unchanged | 0 | | | 0 |
| every kern_small module | small | (CTRL, FORMAT, DISKOPS, FILECP, FDLG, SERIAL, KEYBOARD) | unchanged | 0 | | | 0 |

Inside the image (kern_big; kern_mega the same +24): **code and strings
13,737 -> 13,342 (-395)**, the assets 14,642 -> 13,422 (-1,220), the bss
26 -> 874 (the working area moved in from the asset claim).

**Heap while the wide panel is open** (`mem_tab`, read on MartyPC after
the open): the module claim 13,824 + the asset claim 15,872 = **29,696 in
two claims -> 27,648 in one (-2,048)**. (BRIEF 0.3 quotes a 14,336-byte
module claim; `mem_bytes_gp_x` rounds 13,763 to 512s, 13,824, and the
machine showed 864 paragraphs.)

**Disks** (`tools/os88diskuse.py --diff`): every system disk that carries
the wide face gains a cluster and a root directory slot - `os8088.img`
1,305 -> 1,306 free, `os8088-720.img` 92 -> 93, `os8088-120.img` 829 ->
830, `emu.img` 1,673 -> 1,674, `mega.img` 1,530 -> 1,531, `mega120.img`
1,054 -> 1,055 (CPWIDE.DRV 23 -> 33 clusters, CPWIDE.DAT's 11 gone; 12 + 6
-> 17 at 720KB's 1KB clusters). The 360KB disks carry neither file: no
cluster moved on any of the ten; `SYSCHECK.O88` is 15 bytes shorter on
every disk that carries it (its manifest no longer names CPWIDE.DAT).

**Resident kernel.** `cmp -l` of each `kernel.bin`, base against tip:
kern_big, kern_emu and kern_mega differ in the build number's three sites
(445 -> 449, the commit count) and in ONE other byte, `MOD_MAX_KB`'s
immediate in resident `mod_need` (`cmp ax, MOD_MAX_KB * 1024`: its high
byte 44h -> 78h, 17,408 -> 30,720) - byte 67,311 (1-based, `cmp -l`) on
kern_big, 67,551 on kern_emu, 78,743 on kern_mega. At ONE commit (before
the first commit, build 445 both) the immediate was the ONLY byte. kern_small
differs in the build number's sites alone: `MOD_MAX_KB` stays 17 there
(`%ifdef KERN_BIG`), so its resident kernel is byte-identical. Every file
length is unchanged.

## 2. TAKEN

**2.1 BRIEF 0.3: `CPWIDE.DAT` into `CPWIDE.DRV` (`26a90806d`).** The
coordinator's recommended shape, with the working area where it said:

* `tools/cpwdat.py` writes the assets UNPACKED to `build/cpwdat.bin`, a
  prerequisite of the kernel's assembly (`$(CPWDATBIN)`, `stiklib.bin`'s
  shape; empty on kern_small). `cpwide.inc` `incbin`s it as the LAST of the
  image's initialised bytes (`cpw_dat`, aligned to a word: the mask words
  read as they did in the claim). The module file's own lz4 packs it with the
  code. Nothing writes a byte of it.
* The 848-byte working area is the image's bss tail (`cpw_wa`, in `.modvb`
  after `cpv_tlab` and `cpw_dseg`), under `MOD_H_SCR` (874): zeros in the
  file, re-zeroed by the drop of a kept image (SPEC.md 2.8.3), and still
  zeroed by `cpw_open` at every open (the KEPT bytes are per open).
* ES is the image's own DATA view: `cpw_open` does `PUSH_CSDATA / pop es`
  (`push cs` on the real-mode kernels; on kern_mega `mega_csdata`, the
  writable alias of the code selector, above 1MB or not) and stores it in
  `cpw_dseg`, which `cpw_ev` loads at every event exactly as it loaded the
  claim - so `cpw_thm.inc`'s `mov es, [cs:cpw_dseg]` still means the same
  thing.
* `CPW_W_*` are rebased onto `cpw_wa` (`cpw_wa + n`, the same n) and
  `CPW_WSZ` is now `cpw_dat`, the assets' first byte, the name the pages use
  for the offset they add (`cpw_drv.inc`'s `add ax, CPW_WSZ`); the working
  area's length is a new name, `CPW_WAN`. Every `[es:...]` site in
  `cpw_drv.inc`, `cpw_thm.inc`, `cpw_vid.inc` and `cpwkit.inc` assembles from
  unchanged source and reads the same byte; no operand changed encoding
  (none of the rebased symbols was used as a disp8 or an imm8). NASM's `%if`
  takes a forward label through an `equ` and only so: the checks keep their
  shape, the paragraph check (`CPW_WSZ & 15`) goes with the packed read it
  guarded.
* `cpw_open` loses the volume bracket, `drv_find`, the claim, the read and
  the five checks (**306 -> 85 bytes**): the assets are the image's own
  bytes, stamped with this build by `mod_check` (SPEC.md 2.8.2). It still
  answers CF = 0 (from its last `xor`). `cpw_close` loses the free;
  `cpw_datname` goes.
* `MOD_MAX_KB` 17 -> 30 on the three kernels with the wide face, under the
  MODS_SIZE ruling (section 1's proof; WANTS THE OWNER 4.1). 30 leaves 3KB
  over the 27.6KB image, so the catalog can grow without a resident byte
  moving again. Nothing else is sized by it: `mod_need`'s bound, the module
  size checks in `kernel.asm` (all still true), kern_mega's `%if MOD_MAX_KB >
  63` (`mod_hi` copies through one 64KB descriptor); `os88mod.py`, the cache
  and `mod_hi`'s descriptor take the image's own size.
* Every file that named the DAT: `Makefile` (`DRIVERS`, `SYS360OMITDRV`, the
  rule), `os88disk.py`'s stamp, `t_image` (the attribute branch),
  `t_cpwdat` (the blob, and CPWIDE.DRV's image carrying it exactly once, on a
  word), `pins.txt` (the asset claim's pin goes with the claim), `suite.py`
  (the cpwdat row's words and inputs), the guide (CPWIDE_DAT's page, line and
  lock entry go; CPWIDE_DRV's page says it holds the icons and catalog,
  ~29KB, and is restamped), `megamodcache.py`'s comment, SPEC.md 135.1,
  135.2, 135.4, 135.5, 135.6, 135.7, 135.12 and 19.6's attribute table (its
  CPWIDE.DAT row), 2.8.3's kept-image table (a CPWIDE.DRV row it never had),
  CPWIDE-PLAN's D5. `ctrl.inc`'s two comments are CROSS-FILE.

kern_mega: the image goes above 1MB as every module does (`mod_hi` copies
the whole image, bss included); ES is its data alias, which `api_gfx_blit4`
(the icon blit's ES:SI), `apic_font_run` (BL = 2 sets DS = ES) and every
store reach in protected mode as they reached the claim's selector - the
wide face's drawing is protected-mode code end to end, no real-mode bracket
reads its data (VESA.DRV's bank switch is a reflected `int 10h` with no
buffer). The open's conventional heap is the transient read only: the asset
claim, which stayed conventional for as long as the panel was open, is gone.

**Every compact-face refusal is unchanged and silent**: CGA, Hercules, EGA,
kern_small, the 360KB system disk (it omits one file now, not two), a
missing or `mod_check`-refused `CPWIDE.DRV` and a heap that cannot fund it
are all `mod_need`'s refusal, which `cpg_open` already turned into the
compact face (and remembers - WANTS THE OWNER 4.3).

**2.2 The assets' encoding (`90bb11b57`)**, cold data, read per icon:

* **16x16 slots, -960.** Six category cells of `cp-icons-16.png` are pixel
  for pixel a page icon (Display, Sound, Storage, Input, Memory, System are
  the Display, Sound, Hard disk, Mouse, Memory and gear pages'). The block
  stores each distinct cell once, in sheet order: 26 slots. `cpwfmt.inc`
  writes each name's sheet cell after it (`; cell N`); `cpwdat.py` refuses a
  name whose slot does not hold its cell or a sheet whose distinct cells are
  not `CWI16_N`, and `t_cpwdat`'s second reader checks the same
  independently. The duplicates' names alias the page icon; CD-ROM..Warning
  are slots 16-25 (OK/ERR/WARN stay consecutive for `cpk_badge`). No file
  outside mine names a number: `cpw_drv.inc`'s bound is `CWI16_N` (26), and
  the catalog's icon field is written as the slot. The PNG is untouched.
* **Catalog records 64 -> 44, -260.** The 20 reserved bytes held nothing; the
  reader is assembled with the writer's numbers, so a field is added by
  growing the record. No field another file reads moved (`CWD_C_*` all as
  they were).
* **Block offsets as constants**: `CWD_OFF16/OFF32/OFFCAT` in `cpwfmt.inc`
  (checked against the header by `cpwdat.py` and `t_cpwdat`); `cpw_icon` adds
  one immediate where it read the header and then added `CPW_WSZ`, and
  `cpw_cat` loads one (`cpw_icon` 155 -> 140, `cpw_cat` 67 -> 61).
* **`cpw_icon`'s copy is `es lodsb` / `stosb`**: SPEC.md 2.8.6's rule for a
  module's `lods` is that the source names its segment (`os88ovlchk`), which
  `es lodsb` does. Tried and dropped: a mask word before each sixteen pixels
  (one `lodsw` a group) - it packed 310 bytes worse under lz4, so the
  pixels-then-mask layout stayed. `CWD_VERSION` 1 -> 2.

`CPWIDE.DAT` 14,642 -> 13,422 bytes, lz4 5,281 -> 5,222.

**2.3 Shapes in `cpwide.inc` and `cpwkit.inc` (`37c40eff1`, `b939111c8`)**,
all cold (paint, click) but the headings, which are a speed item too:

| routine | base -> tip | what |
|---|---:|---|
| `cpw_list` | 230 -> 222 | headings: the words alone, then the rest of their rows one fill (they were padded to 14 cells by `cpw_pad`, which goes: -38); the tail compares BX itself |
| `cpw_sty2` (new) | 0 -> 9 | DX = the status rule's row - 2, for `cpw_paint`, `cpw_list`, `cpw_under` (49 -> 45, 27 -> 23) |
| `cpw_lrow` | 111 -> 103 | one test of the full-paint flag for both colours (it was made on each arm) |
| `cpw_hdr` | 115 -> 112 | `cpw_runp` keeps AX: the second line's ink/paper load went |
| `cpw_close` | 44 -> 28 | (the free went in 2.1) and no zeroing of `cpw_dseg`: `cp_wclose` drops `MOD_CPW` straight after, the drop zeroes the tail it lives in or frees the image, and the slots are disarmed between |
| `cpw_status` | 201 -> 193 | a dead `push bx`/`pop bx` round OSAPI_MEM_AVAIL (BX is reloaded next), `cbw` for two `xor ah, ah` (counts under 128), add/sub for a bank, and the left margin's `xor ax, ax` (AX is 0 from the rule's fill) |
| `cpk_group` | 152 -> 126 | its box read off its own frame (`[bp+n]`): the four banked registers ARE the box, so the four kit-scratch stores and their reloads went |
| `cpk_tabs` | 174 -> 149 | SI walks on past each label (it was banked in the kit scratch and reloaded), the tab's left in BP, the top recovered by `sub bx, 11` |
| `cpk_tbclick` | 192 -> 180 | x relative to the table's right edge, computed once; AX on a refusal (CF = 1) is no output, and neither caller (`cpd_click`, `cpv_click`) reads it |
| `cpw_listev` | 75 -> 75 | `cpwpages`' finding, taken: a driver coming or going repaints the Drivers rows with `cpk_tbrows`, not `cpk_table` - `cpd_build` lists drv_tab rows by FILE, which a load or an unload does not move, so the count, the top (its clamp) and the selection stand and the scroll bar's picture is the one on the screen. -16 primitive calls on that path (`os88ui_sbar`'s), the same pixels |

**Equivalence.** The kit (`cpwkit.inc`): a unicorn 2.1.4 harness
(`kit_harness.py`, in the scratch directory) assembles base and tip
`cpwkit.inc` standalone with every kernel far call (`cw_gfx_fill`,
`apic_font_run`, `api_gfx_blit4`, the CPWC hops) a logging stub, and runs
2,093 cases - every icon BY NAME (so the renumbered slots are compared icon
for icon) on four grounds and two positions, the tab strip, its hit test,
group boxes, badges, text, runs, rect tests, the table and 1,536 table
presses over every scroll-bar part: the same primitive calls with the same
arguments and pen, the same staged pixels, the same registers out (AX
excepted on a refused `cpk_tbclick`, see above) and the same working area
(the kit's own scratch excepted). The shell (`cpwide.inc`): by reading -
`cpw_sty2` is `cpw_sty - 2` into DX and AX is reloaded at all three sites;
`cpw_list`'s tail used AX = BX only to compare and copy back; `cpw_lrow`'s
two arms reached the same test; `cpw_status`'s BX is reloaded with
`drv_tab` on the next line and its AX is 0 from the first fill (`cpw_fill`
keeps every register); the headings cover x 4..119 on the same 8 rows with
the same words and a white paper either way (a space cell is paper; no
heading is longer than 14). And on the glass: MartyPC's framebuffer after
the first open, the re-open and the Drivers page, base against tip, differs
in 19 pixels - the status line's free memory, 500K -> 502K, the heap this
pass gave back.

## SPEED

Measured once each, base and tip, on MartyPC `os8088_xt_vga_144` (XT 4.77
MHz, VGA, the 1.44MB system disk: the XT profile with 1.44MB drives, which
the wide face's disk needs), by `measure.py` in the scratch directory:
`os88ui` opens the panel from the Apple menu with drive A's motor stopped
first, `bp_trace` counts every `int 13h` (stops) and logs the three
primitive cells the face draws with and `cp_open_x` (logging breakpoints,
with their cycles); guest seconds are from `cp_open_x` to the last
primitive.

| operation | base | tip |
|---|---|---|
| first wide open: `int 13h` calls | 8 | **6** |
| ...guest seconds | 3.78 | **3.22** (-0.56) |
| re-open, the image kept (SPEC.md 2.8.3): `int 13h` | 2 (CPWIDE.DAT looked up and read again) | **0** |
| ...guest seconds | 1.64 | **0.90** (-0.73) |
| the open's paint: `cw_gfx_fill` / `apic_font_run` / `api_gfx_blit4` | 39 / 15 / 10 | 39 / 15 / 10 |
| ...glyph cells | | -18 (the headings: 8 + 6 + 4 padding cells, ~16 ms on the XT at ~900 us a cell) |
| page switch to Drivers: primitive calls / guest seconds | 289 / 1.40 | 289 / 1.39 |
| a driver coming or going with the Drivers page showing (`cpw_listev`) | the rows + the scroll bar | the rows: -16 primitive calls (`cpwpages`' count of `os88ui_sbar`'s; not measured here) |
| `cpw_icon`'s copy, per byte (`tools/x3cyc.py`, the 8088 model) | 132-144 clocks | 108-120 clocks |
| ...per 16x16 / 32x32 icon prepared | | ~3,800 / ~15,000 clocks less (~0.8 / ~3 ms) |
| `cpw_icon` instructions over the harness's 352 icon cases | 1,019,040 | 855,200 (-16%) |

The disk calls are the merge: one file and one read where the open made
two, and nothing at a re-open, which read the DAT every time before. Every
other path (a click, a key, the tick, a list rebuild) makes the same calls
or fewer; no change adds a transfer call anywhere.

## 3. REFUSED

* **Icons as mask-word-then-pixels groups** (one `lodsw` a group): ~25
  clocks a group faster than the tip, and 310 bytes WORSE in the lz4 file
  (masks interleaved break the matches). The file is disk and decode time;
  the layout stayed pixels-then-mask.
* **Dropping the mask for a colour key**: the 32x32 sheet uses all sixteen
  colours (magenta in 18 pixels), so no index is free to mean transparent.
* **`cpw_run` through `cpk_ds`** (-12 bytes): a call and return on every
  text run of every paint, slower; refused under BRIEF 0.2.
* **Dropping `cpw_ev`'s "not open" test** (-8): a forward before the open is
  gated by `[cp_wide]` today, but with `cpw_dseg` 0 the handlers would write
  through ES = 0 - the IVT. Kept as the module's guard.
* **The DAT header**: 16 bytes, read only for the catalog count now. Kept:
  `t_cpwdat`'s second reader and `cpwdat.py`'s verify read it, and the count
  would otherwise need a generated include.

## 4. WANTS THE OWNER

4.1 **`MOD_MAX_KB` 17 -> 30, an immediate in resident `mod_need`**, on
kern_big, kern_emu and kern_mega (kern_small keeps 17): the coordinator's
MODS_SIZE ruling, used - the instruction, its length and every resident
size unchanged; section 1 has the `cmp -l` (one byte a kernel).

4.2 **One larger contiguous claim.** The open panel holds 27,648 bytes in
one claim where it held 13,824 + 15,872 = 29,696 in two (2,048 less in
all). A heap whose largest free block is under 27.6KB but which had a 13.8KB
and a 15.9KB block refuses the wide face now where it did not. Measured on
the XT test machine the largest free block was ~500KB at the open, so it
did not bind there; it binds only on a heap fragmented below ~28KB, where
the panel opens compact.

4.3 **A heap refusal is remembered until reboot.** SPEC.md 135.2: a refused
`CPWIDE.DRV` is not asked for again (`cpg_open` zeroes `mod_f_cpw`'s first
byte), and `mod_need` gives no reason, so a refusal for want of heap was
already remembered for the 13.8KB module. The asset claim was a SECOND,
unremembered refusal: a heap that could fund the module but not the 15.9KB
assets opened compact that once and tried again at the next open. Now the
one 27.6KB claim is the whole heap case, and it is remembered: such a
machine opens compact until the next boot. **To keep the old behaviour**
(CROSS-FILE, `ctrl.inc`'s `.modu`, ~10 bytes of CTRL.DRV): in `cpg_open`,
before `mov byte [mod_f_cpw], 0`, ask `mmf_osapi_mem_avail` (the largest
claim, KB) and skip the remembering when it is under `(MODV_SIZE + 1023) /
1024` - both are this assembly's numbers. (It approximates `mod_need`'s
criterion: a purgeable cache the claim could shed counts as taken there.)

4.4 **`cpk_text` fills the rest of a line instead of padding it with
spaces** (+31 bytes, a waited path: the Drivers page's DETAILS box, five
`cpd_dl` lines, repainted at every selection change). Today every line is
padded with space cells to the box's width - 52 cells at 616x408, 70 at
760x520 - and each cell is ~900 us on the XT; the variant draws the words
alone and ONE fill of the paper after them. A pixel model over 72 cases
(widths 1 to 95, three strings, three ink/paper pairs; `text_model.py`)
shows the same pixels with 40% fewer glyph cells (4,722 -> 2,844) for one
fill a line. Predicted, not measured: ~200 cells (~180 ms) fewer per
DETAILS repaint at 616x408 and ~300 (~270 ms) at 760x520. The patch is the
`.eos` arm in `wtotree/kernel/cpwkit.inc` in the scratch directory; it
needs `jmp .line` near.

4.5 **`cpw_hdr` on a full paint: the two lines' runs without their paper
fill** (+4 bytes: `call bp` / `jmp bp` through `cpw_run` or `cpw_runp`): the
strip's ground was laid white on the same paint, so the two fills after the
runs repaint white over white. -2 fill calls (~1.5 ms on the XT) every time
the panel is painted whole, the open among them; the same pixels.

## 5. WANTS AN ABI BREAK

None. No `CWV_*`, `CPG_*`, module header, entry table, `mod_tab` row or
layout stamp moved; `CPWIDE.DAT`'s format is the build's own (BRIEF 1).

## 6. CROSS-FILE

* **`kernel/ctrl.inc` (`ctrl`)**: two comments still say `CPWIDE.DAT` is
  read at the open (line 1373, "CPWIDE.DRV's own open: CPWIDE.DAT read and
  the window's size", and 1413, "CF = 1: no CPWIDE.DAT, or no room for it") -
  0 bytes. And `cpg_open`'s arm after `CWV_OPEN` (`jnc .wide` / `mov al,
  MOD_CPW` / `CPXC mod_drop` / `jmp short .out`) can no longer run:
  `CWV_OPEN` answers CF = 0 always. ~9 bytes of `.modu` if `ctrl` takes it
  (or kept as a guard; SPEC.md 135.2 says it is still there). 4.3's ~10
  bytes are `ctrl`'s too.
* **`cpw_under` -> `cpd_groundb`, `cpwpages`' finding: it holds, for the
  MERGE.** `cpwpages`' `cpd_groundb` (BX = the top; DX = the status rule's
  row - 2; white; x `CPW_PX`..`CW` - 1; AX CX DX spent) is `cpw_under`'s fill
  exactly, entered with BX = `CPW_HB`. It does not exist on this branch, so
  it is not taken here: at the merge, `cpw_page`'s `call cpw_under` becomes
  `mov bx, CPW_HB` / `call cpd_groundb` and `cpw_under` (23 bytes at this
  tip) goes - -20 net here. `cpw_sty2` then has two callers and is worth +1
  against inlining them, so make `cpd_groundb` its third (`call cpw_sty` /
  `xchg ax, dx` / `dec dx` / `dec dx` -> `call cpw_sty2`, -3), or fold
  `cpw_sty2` back (-1).
* **`kernel/cpw_drv.inc` (`cpwpages`)**: `cpd_row` pads the name column to
  22 cells (`cpd_pad`) as 4.4 pads a line: the same fill trick would save up
  to ~20 glyph cells a row (10-16 rows a table paint). Its description lines
  go through 4.4.
* `tests/cswrites.txt`'s `cpwkit.inc` reason says the kit writes "through ES
  (the claim)" - a stale word, 0 bytes, left for whoever touches the file.
* `tools/os88ovlchk.py`'s lods rule passes `es lodsb` (it names the segment);
  its comment describes only the waiver form.
* `docs/HOW-CPWIDE-WAS-BUILT.md` is the build diary and keeps its history;
  not edited.
* BRIEF 0.3's "14,336-byte module claim" is 13,824 (`mem_bytes_gp_x` rounds
  to 512; 864 paragraphs on the machine).
* No `DRVM_IMG_*` figure moved (CPWIDE.DRV is a module, not a driver).
* Attach-only code: none (a module has no attach).

## 7. ROWS TO RUN

The wide face itself: **`cpwide`** (soak, QEMU: the open size, the page
list, QA-1 and QA-3's compares). The asset gate and the host gates the
batches touched: **`cpwdat`**, **`image`**, **`installabi`**,
**`guidelock`**, **`ovlchk`**, **`stkbalance`**, **`stkclass`** (fast);
**`pins`**, **`cswrite`**, **`guidelock-full`** (full). The module
machinery and the kept image: **`modcache`**, **`moddrop`**,
**`kernmods`**, **`megamod`**, **`megamodcache`**, **`lzmod`** (the module
files are bigger 'CZ' files). The disks and the installed system that no
longer carry `CPWIDE.DAT`: **`sysman`**, **`syscheck`**,
**`syscheckmono`**, **`icohd`**, **`install`**, **`instkeep`**. The
compact face on a VGA desktop through `tests/cpface.py`'s pin is unchanged
code; `cplistrow` and `cpnames` cover it.

## 8. LOOKED

The measurement session's captures (`shots/` in the scratch directory): the
wide face at the tip after the first open, the re-open and the Drivers page
- the list with its headings and icons, the header strip, the Drivers table
with the catalog's icons (the deduplicated slots) and names, the DETAILS
box's description lines (the 44-byte records) - each equal to the base's
pixel for pixel but the status line's "502K free" (base 500K).

## 9. DEFECTS FOUND

None in the code. Documentation: SPEC.md 2.8.3's kept-image table had no
`CPWIDE.DRV` row (added: its tail and its never-written assets), and BRIEF
0.3's module-claim figure (section 6).

## 10. NOT REACHED

* `cpw_run`'s strlen loop (~45 clocks a character before the run; a
  `repne scasb` needs ES = the string's segment and costs bytes).
* `cpk_tbsb`'s three block-to-ksb copies (ES to DS: a swap costs what it
  saves).
* `cpw_click`'s status-line test through `cpw_sty2` (-1).
* The catalog's fixed 26-byte long name and 12-byte key as offsets into the
  string block: `cpw_drv.inc` reads `CWD_C_LONG` as a field, so that is
  CROSS-FILE (~250 bytes of zeros, which lz4 packs to almost nothing).
