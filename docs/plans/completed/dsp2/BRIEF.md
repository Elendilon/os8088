# Driver size pass 2: the brief every agent reads first

Branch `claude/driver-size-pass-2-m8bag7`, cut from `elendilon` at
`aa6b428` on 2026-11-27. **This is the second size pass over `drivers/` and
the on-demand modules, and the first that is also a SPEED pass.** The pass
before it is driver size pass 1 (`dsp1`), merged into the old integration
branch at `e7668bd73` on 2026-11-15 and squashed home in #365; its record is
`docs/plans/completed/dsp1/RECORD.md` and each agent's note beside it.
**`e7668bd73` is the last sized tree for drivers and modules.** dsp1's
module agent (`kmod`) took nothing, so for the modules the last pass to
change bytes was kernel size pass 20; kernel size pass 21 (`ksp21`, merged
at `aa6b428`) sized the RESIDENT kernel and moved module images by a few
bytes only (`docs/plans/completed/ksp21/sweep.md`, `desk.md`, `diskw.md`).

Each agent works in its own git worktree, created by the coordinator at
`/home/user/wt/<name>` on a branch `dsp2-<name>` cut from the commit that
adds this file. Each writes its record to `docs/plans/completed/dsp2/<name>.md`. The
coordinator merges the branches. **Agents do not push.**

Read these before writing any code, in this order:

1. this file;
2. **`docs/plans/completed/dsp1/BRIEF.md` sections 0.2, 1, 3 and 4**: where
   the bytes usually are, the rules, the method and environment, and the
   note's shape. They carry over UNCHANGED except where this file says
   otherwise. Substitute `dsp2` for `dsp1`, `docs/plans/completed/dsp2/` for its note
   directory and `(driver size pass 2)` for the commit suffix everywhere;
3. **dsp1's note for your area** (`docs/plans/completed/dsp1/<area>.md`),
   and its section 3 (WANTS THE OWNER, which is NOT taken), 4 (cross-file)
   and 5 (not reached) in `RECORD.md`. A REFUSED item is not re-proposed
   unless its reason no longer holds, and then the note says what changed.
   `kmod.md` section 9 is the priced queue for the modules;
4. the SPEC.md section of everything you own (the table in section 2 names
   it), and for the Control Panel agents `docs/plans/CPWIDE-PLAN.md` and
   `docs/HOW-CPWIDE-WAS-BUILT.md`;
5. CLAUDE.md's Hard rules and its banner: **bytes, not rungs**. And its
   Performance section in full: this pass is a speed pass as well.

## 0. The brief

The owner's words: *"Do a size and speed optimization pass on any driver or
modules added (or things added to them) since the last kernel
side/driver/module pass. That is at least the new control panel, and some
hdd work. You can use agents as needed. They can dig deep."*

So the TARGET is the code added since `e7668bd73`, and "dig deep" means:
**read every routine of what you own that was added or changed since then,
not only the largest**, and once that is done, sweep the rest of your files
(dsp1's NOT REACHED lists are where to start). There is no byte goal. Every
item states its bytes and, where it touches a path anyone waits on, its
speed.

### 0.1 What grew, and what has never been read

Assembled at `aa6b428` (kern_big unless named), against dsp1's tip
`e7668bd73` built the same way. "image" is what RAM pays while loaded (image
+ bss / a module's image + its bss tail). "file" is what the disk pays (the
lz4 file; CTRL.DRV ships PLAIN on kern_big, emu and mega, SPEC.md 2.8.7).

**Modules** (`tools/os88rdiff.py kernel e7668bd73 HEAD`, section lengths):

| module | section(s) | at `e7668bd73` | at base | growth | never sized |
|---|---|---:|---:|---:|---|
| **CPWIDE.DRV** (the wide Control Panel, SPEC.md 135) | `.modv` | - | 13,763 (+26 bss), file 11,653 | **new** | **all of it**: the Display page 4,735 (`cpw_vid.inc`), the Drivers page 2,979 (`cpw_drv.inc`), the shell 2,835 (`cpwide.inc`), the Theme page 1,794 (`cpw_thm.inc`), the kit 1,350 (`cpwkit.inc`). kern_mega 13,793 / file 11,670 |
| **CPWIDE.DAT** (its assets, SPEC.md 135.6) | `tools/cpwdat.py` | - | 14,642 unpacked, file 5,281 | **new** | all of it. A heap claim of `CPW_WSZ` + the file's unpacked bytes for as long as the wide panel is open |
| **KEYBOARD.DRV** (layouts, SPEC.md 9.16) | `.modq` | - | 5,624 (+16 bss), file 2,914 | **new** | all of it: ~3.9KB is tables (`klf_cp850` 1,024, `klf_table` 768, four `klm_map_*` of 533), ~1.7KB code. kern_small ships it too |
| **CTRL.DRV** | `.modc` + `.modu` | 15,459 | 16,733 (emu 16,751, mega 16,972; small 6,291) | **+1,274** (`.modu` +1,194, `.modc` +80) | the wide face's gate (`modc_e_gate`, `CPG_*`), `cpg_open`, the Display page's `CPG_VIDARR`/`CPG_GLYPH`, the keyboard row, PC1 and HDD driver-page rows, and whatever else `os88rdiff` lists in `.modu`/`.modc` |
| **DISKOPS.DRV** | `.modl` | 10,216 | 10,849 (mega 12,300; small 7,995) | **+633** | FAT32 on kern_mega's arms, the cloner's and `diskmut.inc`'s additions |
| HIBER.DRV | `.modh` | 7,715 | 7,729 (mega 11,632) | +14 | |
| STIKMENU.DRV | `.modn` | 7,926 | 7,935 | +9 | |
| EXTD.DRV | `.modx` | 1,927 | 1,930 | +3 | |
| FSCHECK.DRV | `.modfs` | 6,298 | 6,294 | -4 | kmod's queue (call/ret tails) |
| FORMAT, DOCK, WIN95, DESK, SERIAL | | | unchanged | 0 | kmod's queue |

**Drivers** (`os88drv` lines, from a build of `e7668bd73` and one of the base):

| driver | dsp1 tip image / file | base image / file | growth | what was added |
|---|---:|---:|---:|---|
| **ETHER.DRV** | 17,771 / 11,116 (16,848 / 10,829 when dsp1's `ether` agent finished) | 17,799 / 11,147 | **+951 / +318** since `ether` measured; +28 / +31 since `e7668bd73` | Wire Arena's UDP verbs (SPEC.md 72.24, `ethsock.inc` +212 lines) were merged into dsp1's branch AFTER its `ether` agent finished (+923 image), so they were never sized; then `ethdrv.inc`, `inet.inc`, `tcp.inc` deltas |
| **PCIETHER.DRV** | 17,432 / 10,886 (16,509 / 10,599 when `ether` finished) | 17,460 / 10,919 | **+951 / +320** since `ether` measured; +28 / +33 since `e7668bd73` | the same shared code |
| **SOUND.DRV** | 10,265 / 8,889 | 10,965 / 9,458 | **+700 / +569** | the DMA lab and the auto-init probe (#408), ES1868/ES1869 DMA routes at attach (#363) - `sb.inc` +483 lines. `snddiag.inc` +580 is the debug arm (empty in the shipped build) |
| **HDD.DRV** | 4,096 / 3,558 | 4,608 / 4,021 | **+512 / +463** | logical drives in extended partitions, LBA past 504MB, packet calls past 8GB (#386, SPEC.md 52.1.5, 52.1.6, 52.4.1); `mount.inc` +239, `hdd.asm` +289, `hdcom.inc` +58 |
| **HDDTOOL.DRV** | 16,153 / 12,116 | 16,665 / 12,229 | +512 / +113 | the same feature's tool side (`inst.inc`, `partw.inc`, `tool.inc`) |
| **VESA.DRV** | 7,406 / 3,536 | 7,564 / 3,698 | +158 / +162 | `VXV_INFO` for the Display page (SPEC.md 120.10), CP850 text (#398), Theme Color (#399), `vx_find` |
| **PC1MOUSE.DRV** | - | 452 / 423 | **new** | the Olivetti PC1 mouse (#371) |
| NET.DRV | 4,167 / 3,471 | 4,167 / 3,471 | 0 / 0 | `netsock.inc`, `netpkg.inc` (no byte) |
| RAMDISK.DRV | 5,400 / 4,597 | 5,407 / 4,604 | +7 / +7 | `rdpkg.inc`, `ramdisk.asm` |
| CDROM.DRV | 8,203 / 4,644 | 8,203 / 4,644 | 0 | a comment-only `cdiso.inc` delta |

**HDD.DRV is resident on every machine with a hard disk**, so its image is
RAM for the whole session. Its resident span (everything before
`hdsec.inc`'s `align 512`) is **4,094 bytes** against a 4,096 step: the image
is the span padded to 512 plus the 512-byte attach run laid over `hd_mbr`
(dsp1 `hdd.md` section 1). Two bytes of growth cost the next 512 of RAM;
**511 bytes of saving give one back**. That is a consequence to report, not
a goal to design to (CLAUDE.md: bytes, not rungs) - but say in the note how
far the span ended from each step.

Measure your own base in your worktree anyway (dsp1 BRIEF 3). The figures
above are the coordinator's, from one build of each tree; your note's are
from yours.

### 0.2 SPEED: what it means in this pass

The owner asked for size AND speed. On every path someone waits on, a
change that makes it faster is in scope even when it costs bytes, and a
change that makes it smaller may not make it slower. The table in CLAUDE.md's
Performance section is the price list; the rules that matter here:

* **A redraw is priced by how many primitive calls it makes, not by how many
  pixels it covers.** A `gfx_*` call is ~756 us of fixed cost on the XT, an
  8x8 glyph cell ~900 us, an `OSAPI_*` far call 46.7 us, a near call 11 us.
  The Control Panel's paths that people wait on are: **the wide face's open**
  (module and asset reads, then the first paint), **a page switch** (the
  page's first paint), **a click or key on a page** (what it repaints), and
  **the panel's tick** (`cp_tickp` and whatever a page does per tick). Count
  the primitive calls each makes at base and at tip, by reading or with a
  counter (CLAUDE.md Performance rule 4), and put the counts in the note.
  **A repaint of more than changed is a defect** (rule 1), and so is a pixel
  written twice (rule 2: `font_run`, not a fill followed by `font_str`).
* **Disk work is priced in CALLS, ~400 ms an `int 13h` call.** No change may
  add a transfer call to any operation (an `int 13h`, a controller command,
  a packet, an XMS move). The panel's open reads `CTRL.DRV`, `CPWIDE.DRV`
  and `CPWIDE.DAT`: a smaller file is fewer sectors, which only buys time
  when it is fewer CALLS (a shorter run, or a file that stops crossing a
  track). Say which.
* **Decompression is CPU time on the XT.** A byte that packs worse is a byte
  more to read AND to decode; one that packs better is the reverse. Report
  image and file, separately, every time.
* **Driver hot paths** are as dsp1 BRIEF 1 named them: ISRs, per-byte,
  per-sample, per-packet and per-sector loops, anything per tick. They may
  change only cycle-neutral or faster, with the count shown (a unicorn
  harness against the base bytes, or a hand count in the 8088's
  `max(clocks, 4 x instruction bytes)` terms). On those paths, a change that
  is FASTER at a few bytes' cost is welcome: state both.
* **Cold paths** (attach, probe, settings, errors, a one-off tool action):
  size beats speed, unless the cold path is one a person sits and waits on
  for more than a moment (a mount, a format's plan, a page's paint), where a
  measured speedup with its bytes is a candidate under WANTS THE OWNER if it
  costs more than it saves.

**One MartyPC measurement session per agent is allowed**, for a number that
decides a design (CLAUDE.md, Testing: *the agent choosing takes it once,
writes it in its report, and nobody re-takes it to confirm*): boot the base
and the tip once each on the machine your path runs on
(`os8088_xt_vga` for the wide Control Panel; `tools/os88ui.py` to open it),
count what you need with logging breakpoints (`tools/os88hot.py`'s `Run` is
the worked example of the technique; it has no Control Panel scenario, so
write your own script in your scratch directory), and stop. That is not a
row and does not stand in for one. The final pass measures nothing again.

### 0.3 The owner's second instruction: CPWIDE.DAT goes INTO CPWIDE.DRV

The owner, during the pass: *"For cpwide module and dat asset: those both
have to load for it to work at all right? We have a policy against required
sidecars, so if that is true then as part of this work combine them so we
don't need an extra int13 for every wide control panel load."*

It is true. SPEC.md 135.2: a missing, refused or unaffordable `CPWIDE.DAT`
opens the compact face exactly as a missing `CPWIDE.DRV` does, so the two
are one feature in two files - a required sidecar. And it costs more than
one read: `cpw_open` looks the file up (`drv_find`) and reads it whole
(`dskw_read_x`) at EVERY wide open, while `MOD_CACHE` (SPEC.md 2.8.3) keeps
`CPWIDE.DRV`'s image re-adoptable with no disk read at all - so today a
re-open of the panel reads the disk only for the DAT. Nothing outside the
build writes or ships the DAT on its own (it is `tools/cpwdat.py`'s output
from `drivers/catalog.toml` and `kernel/cpwart/`).

**This is `cpwshell`'s FIRST item, and the largest of the pass.** The shape
the coordinator recommends (the agent may find a better one, and says why):

* **The DAT's bytes become part of `.modv`**, immutable data at the end of
  the image's initialised part (`incbin` of the unpacked blob
  `tools/cpwdat.py` writes, generated before the kernel assembles - or
  appended by the cut; whichever the build supports cleanly). The module
  file's own lz4 packs them as the DAT's packed today, so the disk pays
  about the same bytes in ONE file and one directory entry.
* **The 848-byte working area becomes the module's bss tail** (`.modvb`,
  `MOD_H_SCR` covering it), zero at load and at re-adoption as every
  module's scratch tail is. `cpw_open` still zeroes it (the KEEP bytes are
  per-open).
* **ES stays "the asset view" for every handler**, now the module's own
  image: on the real-mode kernels its segment; on kern_mega its DATA alias
  (`mega_dsimg`, `kernel/kernel.asm`'s `CSDO` family - the code selector is
  not writable, and the working area is written). `CPW_W_*` and the DAT
  offsets (`CPW_WSZ + CWD_*`) are rebased so that every `[es:...]` site in
  `cpw_drv.inc`, `cpw_thm.inc`, `cpw_vid.inc` and `cpwkit.inc` assembles
  unchanged and means the same byte. **Split today's `CPW_WSZ` in two** if
  needed (the working area's length vs. the DAT's offset in ES), keeping the
  name the pages use for the one they mean.
* **`cpw_open` loses** the file lookup, the claim, the read and the checks
  (the magic, version, size and block bounds guarded a file read off a disk;
  the data is now the module's own bytes, which `mod_check`'s layout stamp
  ties to this build like its code). **`cpw_close` loses** the free.
  `cpw_datname` goes.
* **`MOD_MAX_KB` rises** to what the combined image needs (~29KB) - the
  VALUE of the immediate in resident `mod_need` (`kernel/mod.inc`), under
  the same ruling as `MODS_SIZE` (section 1), with the `cmp -l` proof. Its
  build-time `%if` checks in `kernel/kernel.asm` and kern_mega's
  `%if MOD_MAX_KB > 63` stay true. Check that nothing else is sized by it
  (the module cache, `os88mod.py`, `mod_hi`'s descriptor).
* **Everything that named the file**: the Makefile (`$(BUILD)/cpwide.dat`,
  `DRIVERS`, the disk lists, `SYS360OMITDRV`), `tools/os88disk.py`,
  `tools/guide/entries.toml`, `tests/unit/t_cpwdat.py` (keep its checks,
  against the blob the module carries), `tests/unit/t_image.py`,
  `tests/suite.py`, `tests/pins.txt` (the asset claim's `MEM_K_MOD` pin goes
  with the claim), `tests/megamodcache.py`, SPEC.md 135.2, 135.6 and 135.12,
  `docs/plans/CPWIDE-PLAN.md`'s facts if any are now wrong, and the comments
  in `ctrl.inc`/`cpwlay.inc` that say "CPWIDE.DAT read" (`ctrl.inc` is
  `ctrl`'s file: a comment there is CROSS-FILE, priced 0, for the
  coordinator). `cpwshell` may edit all of these for this item.
* **What to report**: the open's disk calls before and after, first open
  and re-open (a re-open with the image cached should read NOTHING); the
  heap the open panel holds (today one 14,336-byte module claim plus a
  15,872-byte asset claim: 30,208 bytes in two claims; after, one claim);
  the file bytes on each system disk; kern_big, kern_emu and kern_mega
  figures. **And two consequences to put under WANTS THE OWNER**, measured:
  (1) the module is one larger CONTIGUOUS claim instead of two smaller
  ones; (2) SPEC.md 135.2's *"a refused CPWIDE.DRV is not asked for
  again"* - a refusal for want of heap is remembered until reboot, where a
  DAT that could not be funded was NOT remembered. Say what that changes
  and what it would cost to keep the old behaviour.
* **Everything the compact face does, and every refusal, stays exactly as it
  is**: CGA, Hercules, EGA, kern_small, the 360KB system disk (which omits
  the module, and now omits one file instead of two) and a heap that cannot
  fund the module all open compact, silently.

The pages' agents (`cpwpages`, `cpwvid`) work in parallel with this: **treat
`CPW_W_*`, `CPW_WSZ` and the `CWD_*` offsets as symbols, never as numbers,
and never assume ES is a claim of its own** (do not free it, do not do
segment arithmetic on it). Then the merge lands under them without a textual
conflict.

## 1. The rules this pass

dsp1 BRIEF section 1 applies, with these changes and additions:

* **Functionality: byte-identical behaviour is the bar**, refusal paths
  included. What is drawn is behaviour: a pixel moved, a colour changed, a
  string reworded are WANTS THE OWNER (with bytes and, for a picture, a
  cropped screenshot of each). **A repaint that drew the SAME pixels with
  fewer calls is not a behaviour change** - that is the speed half of the
  pass - but you prove it (the same final framebuffer, by a harness or a
  MartyPC capture).
* **The ABI is frozen**: `DRV_VER`, the driver header, every verb number,
  `apps/os88api.inc`, `drivers/os88drv.inc`, the C SDK, the package-facing
  headers dsp1 BRIEF 1 lists (`ether/netpkg.inc`, `sound/sndpkg.inc`,
  `kernel/vxabi.inc`, ...), and `hddabi.inc` (`HD_ABI_VER`,
  `tools/abi.lock.json`). A win that needs one goes under WANTS AN ABI BREAK
  with bytes and every includer.
* **The module ABI is frozen**: the module header, each module's entry
  table, `mod_tab` rows, the layout stamp, and the module ids.
* **The resident kernel may not move by a byte** on kern_big, kern_small,
  kern_emu or kern_mega (dsp1 BRIEF 2.1): `tools/kernsize.py --json`
  absolutes, and `cmp` of each kernel's `kernel.bin`, at ONE commit (the
  build number is the commit count). **One ruling, the coordinator's, on
  dsp1 `kmod`'s open question**: a `.modc` saving changes the VALUE of
  `MODS_SIZE`, an immediate in resident `mod_need` (`kernel/mod.inc`), and
  that is allowed - the instruction, its length and every resident size are
  unchanged and the value is the module's own length. Prove it with
  `cmp -l` showing ONLY those immediate bytes differ (one site on kern_big,
  emu and mega each; name them), and list the item under WANTS THE OWNER as
  well, so the owner sees the ruling used. A module saving that needs any
  other resident change is CROSS-FILE.
* **`kern_small` modules count**: CTRL, DISKOPS, FORMAT, FILECP, FDLG,
  SERIAL and KEYBOARD ship on the 128KB machine's disk. Its resident kernel
  is frozen like the others; its modules may shrink. Report its figures
  even when 0.
* **kern_mega runs every driver and its own module images.** A claim there
  is an LDT selector (SPEC.md 20.18, 50.6.11); module arms under
  `%ifdef KERN_MEGA` must keep building and may not grow. `make -j2 mega` at
  your tip, and report kern_mega's module figures.
* **No feature may come to need the system disk** where it did not, and the
  wide panel's refusal to the compact face (SPEC.md 135.2) stays exactly as
  it is: every way CPWIDE.DRV or CPWIDE.DAT can be missing, refused or
  unaffordable must still open the compact face silently.
* **`CPWIDE.DAT`'s format** (`kernel/cpwfmt.inc`) is internal to the build:
  `tools/cpwdat.py` writes it and `CPWIDE.DRV` reads it, and `t_cpwdat`
  (fast tier) checks one against the other. Its owner may change it, but
  **a field that another agent's file reads** (`cpw_drv.inc` reads the
  driver catalog, `cpw_thm.inc` and `cpw_vid.inc` may read icons) may not
  move under them: that is CROSS-FILE, priced, for the coordinator.
* **`kernel/cpwlay.inc`** (the gate's `CPG_*` opcodes and the shared
  layout) is assembled into BOTH `CTRL.DRV` and `CPWIDE.DRV`. Its owner may
  change what only CPWIDE.DRV reads. Anything `ctrl.inc` reads or dispatches
  is CROSS-FILE.
* **Ownership is by FILE (and, in a kernel file, by SECTION).** A kernel
  `.inc` is mostly resident code with a module section inside it: you own
  only the lines under your module's `section .mod*` switch. Anything you see
  elsewhere goes in CROSS-FILE with its bytes. A file in no row is free to
  whoever reaches it first: say so in your note's TAKEN line.
* **SPEC.md**: your areas' sections, where a figure you moved is quoted
  (135.12's cost table, 52's sizes, 9.16, 120.10). A stale figure is a doc
  bug. Do not move a contract sentence.
* **`tests/`**: only where a host-side gate in the fast tier mirrors a
  figure of yours and fails because you moved it (`drvmem`'s
  `DRVM_IMG_*` figures live in `kernel/driver.inc` - that one is the
  coordinator's: put the new figure in your final message and do not edit
  `driver.inc`; `t_install`, `t_cpwdat`, `tests/textsites.txt`,
  `tests/btnsites.txt`, `tests/megapkg.txt`). Update in the direction the
  ratchet turns, never loosen, and say so.

## 2. The nine agents and what each owns

| agent | owns | modules / drivers | start with |
|---|---|---|---|
| **cpwshell** | `kernel/cpwide.inc`, `kernel/cpwkit.inc`, `kernel/cpwlay.inc`, `kernel/cpwfmt.inc`, `tools/cpwdat.py`, `drivers/catalog.toml`, `kernel/cpwart/` (the converter's inputs, not the PNG art itself), `tests/unit/t_cpwdat.py`; for section 0.3's merge, also the files that section lists | CPWIDE.DRV's shell and kit (4,185 bytes), CPWIDE.DAT | **section 0.3 first: CPWIDE.DAT into CPWIDE.DRV.** Then `cpw_open` (306), `cpw_status` (201), `cpw_list` (230), `cpw_icon` (155), `cpk_tbclick` (192), `cpk_tabs` (174), `cpk_group` (152). **The wide open is the speed target**: what it reads, what it decodes, what it paints first. CPWIDE.DAT is 14,642 bytes of heap while the panel is open: what in it is the icons (4bpp + mask), what is the catalog, and does any of it pack or encode tighter for the same pixels? SPEC.md 135.2-135.6 |
| **cpwpages** | `kernel/cpw_drv.inc`, `kernel/cpw_thm.inc` | CPWIDE.DRV's Drivers page (2,979) and Theme page (1,794) | `cpd_row` (495), `cpt_card` (362), `cpw_thm_paint` (332), `cpw_thm_click` (289), `cpd_det` (274), `cpd_hdr` (196). The Drivers page's list paint and scroll, and the Theme page's cards, are what people wait on. SPEC.md 135.8, 135.11 |
| **cpwvid** | `kernel/cpw_vid.inc`, `drivers/vesa/` | CPWIDE.DRV's Display page (4,735, the largest file in the module), VESA.DRV | `cpv_build` (351), `cpv_prev` (334), `cpv_click` (280), `cpv_modes` (252), `cpv_rbox` (207). VESA.DRV's growth (`VXV_INFO`, `vx_find`, the CP850 run, Theme Color) and its drawing paths, which are HOT (`gfx_*` on a VESA desktop). SPEC.md 135.9, 120 |
| **ctrl** | every line under `section .modc` and `section .modu` (`ctrl.inc`, `desksc.inc`, `driver.inc`, `desk.inc`, `dock.inc`, `fdlg.inc`, `sched.inc`, `shutdown.inc`, `vidsel.inc`, `wm.inc`) | CTRL.DRV on all four kernels | `os88rdiff`'s changed and new `.modu`/`.modc` routines first: `modc_e_gate`, `cpg_open`, the `CPG_*` handlers, the driver-page rows added for HDD/PC1/keyboard. Then `sd_confirm` (309), `vid_apply` (235), `cdl_call` (222), `cp_vid_click` (213). kmod 9's `cp_vid_rowok` and `shutdown.inc:237` tails. The compact panel's open and page paints are its speed paths. SPEC.md 31, 2.8.7 |
| **input** | every line under `section .modq` (`keyboard.inc`, `keyfont.inc`) and the data only it reads (`keymaps.inc`, `keyfont-data.inc`, where no resident code names it); `drivers/pc1mouse/`, `drivers/ramdisk/`, `drivers/cdrom/` | KEYBOARD.DRV, PC1MOUSE.DRV, RAMDISK.DRV and CDROM.DRV's deltas | KEYBOARD.DRV is 2/3 tables: four 533-byte layout maps and two font tables - is any of that derivable, shareable between maps or smaller in a different encoding at the same lookup cost? `klm_scan` (357) and `klm_translate` (195) are **per keystroke** (hot). PC1MOUSE's ISR is hot. SPEC.md 9.16, the PC1 mouse's section |
| **hdd** | `drivers/hdd/`, every line under `section .modfs` (`kernel/fsck.inc`) | HDD.DRV, HDDTOOL.DRV, FSCHECK.DRV | the #386 additions: the extended-partition walk in `mount.inc`, the LBA and packet paths in `hdd.asm`/`hdcom.inc`, the installer's refusal. **The mount is a speed path** (count its `int 13h` calls per scenario before and after: `hdext`, `hdextloop`'s chain); the sector transfer is hot. HDD.DRV's resident span (section 0.1). kmod 9's four FSCHECK tails. SPEC.md 52, 118.14 |
| **dops** | every line under `section .modl`, `.modf`, `.modh`, `.modx`, `.modk`, `.modw`, `.modj`, `.modn`, `.mods` (`diskops.inc`, `diskmut.inc`, `compress.inc`, `diskw.inc`, `ascw.inc`, `hiber.inc`, `driver.inc`'s `.modh`, `extmod.inc`, `dockmod.inc`, `winmod.inc`, `deskmod.inc`, `stikmenu.inc`, `serial.inc`) | DISKOPS, FORMAT, HIBER, EXTD, DOCK, WIN95, DESK, STIKMENU, SERIAL | DISKOPS.DRV's +633 (+800 on kern_small): `os88rdiff`'s changed `.modl` routines, kern_mega's FAT32 arms. Then kmod 9's tails (EXTD, HIBER) and the shapes kmod did not reach in DISKOPS and STIKMENU. The cloner's and compressor's per-sector loops are hot (`cmz_pack` 752, `cmz_jloop` 526); their `int 13h` counts are the bar |
| **sound** | `drivers/sound/` | SOUND.DRV (and the `snddiag/` debug build, `NOPICOMEM`, `SNDDEF`) | `sb.inc`'s +483 lines: the auto-init probe, the DMA routes, the ES1868 setup. The ISRs, the mixer and the stream are HOT and real-time (read the SPEC.md section for the ISR before touching it); the probes are cold. `tests/unit/t_debugdisk.py` holds the shipped arm byte-identical to the hooks-not-taken build |
| **ether** | `drivers/ether/`, `drivers/pciether/`, `drivers/wirezone.inc`, `drivers/net/` | ETHER.DRV, PCIETHER.DRV, NET.DRV, OS88NET.COM | Wire Arena's UDP verbs (`ethsock.inc`, SPEC.md 72.24), never sized: +951 image in BOTH drivers. `ethdrv.inc` is shared, so a byte there counts twice. The per-packet receive and the UDP send/receive are hot. **dsp1's cable-transport rewrite (`lplink.inc`) stays REFUSED** until a harness holds the real cable's timing (dsp1 RECORD 2.1) |

## 3. Method and environment

dsp1 BRIEF section 3 applies, with these changes:

* **First command**: `cd /home/user/wt/<name> && git status`. You should be
  on `dsp2-<name>`. Never `cd` into `/home/user/os8088` (the coordinator's
  tree) and never write there. Never `git stash`, fetch, rebase or merge.
* **Your worktree's `build/` was copied from the coordinator's base build**,
  so your first `make -j2` rebuilds only what the new commit and the build
  number reach (minutes, not the whole tree). Run it first, in the
  background, held, and record your base from it: the `os88drv:` and
  `os88mod:` lines for what you own, and `python3 tools/os88diskuse.py
  --save <scratch>/base.json`. Then `make -j2 emu`, `make -j2 mega`
  (kern_small comes out of `make`). **Your base is the build at your
  branch's first commit, before you change a byte.**
* **Measuring a module.** `os88mod:` prints each module's FILE; the image is
  the module header's `MOD_H_IMG` word (offset 8), and `os88drv.image_unwrap`
  (`tools/os88drv.py`) unpacks any `.drv`. Module images live in `build/`
  (kern_big), `build/smallk/`, `build/emuk/` and `build/megak/`.
  `python3 tools/os88rdiff.py kernel <base> .` diffs every routine of every
  module section (add `-D KERN_SMALL` for kern_small, `-D KERN_MEGA` for
  kern_mega). A module routine is reached far through its entry table, so
  verify every moved entry by READING.
* **Scratch**: `<scratchpad>/dsp2-<name>/`.
* **The box**: 4 cores and 15 GB, shared by nine agents. `make -j2` always,
  never two builds in your tree at once.
* **MartyPC**: `mkdir -p build && ln -sfn /home/user/os8088/build/martypc
  build/martypc` in your worktree once the coordinator's build exists. Never
  build a second copy, and never kill an emulator you did not start.
* **Rows: you run NO soak rows**, by hand or otherwise (CLAUDE.md Testing:
  this pass is batches; the coordinator runs the deduplicated union once
  after the last merge). NAME the `tests/suite.py` rows that cover every
  change. The one boot to LOOK (dsp1 BRIEF 3) and the one measurement
  session (section 0.2 above) are not rows.
* **Commit in small batches** on `dsp2-<name>`, one subject per commit:
  `<name>: <what> - <IMAGE> image -N, file -M[, <path> -K calls] (driver
  size pass 2)`. End each with the attribution trailer the session gives
  you; never put a model name in a commit or a file. After adding or editing
  your note, run `python3 tools/os88index.py` and commit `docs/INDEX.md` with
  it.

## 4. The note

dsp1 BRIEF section 4's nine sections, plus one: **SPEED** (after TAKEN):
for every path you changed that anyone waits on, the operation, its count
at base and tip (primitive calls, `int 13h` calls, cycles), and how it was
counted. And in BASE AND TIP, give kern_small and kern_mega's figures for
every module you own.

**Your final message to the coordinator is ONE message**, containing: the
branch tip; per module and driver, image and file base to tip on every
kernel that builds it; the speed results; the WANTS THE OWNER and WANTS AN
ABI BREAK items; any `DRVM_IMG_*` figure that moved; the rows you name; any
defects; anything that blocked you.
