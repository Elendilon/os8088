# Driver size pass 2: the record

Branch `claude/driver-size-pass-2-m8bag7`, cut from `elendilon` at `aa6b428`
on 2026-11-27. The brief is `BRIEF.md` beside this file, and each agent's
note is the authority on its own items: `cpwshell.md`, `cpwpages.md`,
`cpwvid.md`, `ctrl.md`, `input.md`, `hdd.md`, `dops.md`, `sound.md` and
`ether.md`. Nine agents worked the drivers and on-demand modules added or
grown since driver size pass 1 (`e7668bd73`), for size AND speed.

The owner's words: *"Do a size and speed optimization pass on any driver or
modules added (or things added to them) since the last kernel
side/driver/module pass. That is at least the new control panel, and some
hdd work."* And, during the pass: *"For cpwide module and dat asset: those
both have to load for it to work at all right? We have a policy against
required sidecars, so if that is true then as part of this work combine them
so we don't need an extra int13 for every wide control panel load."*

## 1. What it bought

Assembled from the merged tree against the base (`1b01907f1`, the brief's
commit). "image" is what RAM pays while the file is loaded (a driver's image
with its bss; a module's image with its bss tail). "file" is what the disk
pays (lz4; CTRL.DRV ships plain on kern_big, emu and mega).

### 1.1 Modules

| module | kernel | image | file |
|---|---|---|---|
| **CPWIDE.DRV + CPWIDE.DAT** (now one file) | big, emu | 13,763 + 15,490 (the asset claim: 848 + 14,642) = 29,253 → **26,336** (−2,917) | 11,653 + 5,281 = 16,934 → **15,732** (−1,202) |
| | mega | 13,793 + 15,490 = 29,283 → **26,354** (−2,929) | 11,670 + 5,281 = 16,951 → **15,751** (−1,200) |
| **KEYBOARD.DRV** | big, emu, small | 5,624 → **3,879** (−1,745; 11 → 8 granules) | 2,914 → **2,502** (−412) |
| | mega | 5,674 → **3,943** (−1,731) | 2,934 → **2,534** (−400) |
| **CTRL.DRV** | big, emu | 16,733 → **16,364** (−369; emu 16,751 → 16,382) | same (plain) |
| | mega | 16,972 → **16,598** (−374) | same (plain) |
| | small | 6,291 → **6,171** (−120) | 5,871 → **5,781** (−90) |
| **DISKOPS.DRV** | big, emu | 10,849 → **10,699** (−150, a granule) | 9,523 → **9,411** (−112) |
| | mega | 12,300 → **12,105** (−195, a granule) | 10,091 → **10,010** (−81) |
| | small | 7,995 → **7,880** (−115) | 7,118 → **7,023** (−95) |
| FSCHECK.DRV | big / emu / mega | 6,294 / 6,283 / 6,286 → 6,241 / 6,230 / 6,239 (−53 / −53 / −47) | −41 / −41 / −36 |
| SERIAL.DRV | big, emu, small / mega | 1,090 → 1,062 (−28) / 1,181 → 1,152 (−29) | −36 / −36 |
| STIKMENU.DRV | big, emu / mega | 7,935 → 7,911 (−24) / 8,426 → 8,390 (−36) | −25 / −38 |
| EXTD.DRV | big, emu, mega | −15 | −15 |
| HIBER.DRV | big, emu / mega | 7,729 → 7,722 (−7) / 11,632 → 11,625 (−7) | −10 / −13 |
| WIN95.DRV | big, emu, mega | −2 | −2 |
| FORMAT, DOCK, DESK, FILECP, FDLG | all | 0 | 0 |

**The wide Control Panel's heap**, while it is open: 13,824 + 15,872 =
29,696 bytes in two claims → **26,624 in one**.

### 1.2 Drivers

| driver | image | file | claim |
|---|---|---|---|
| ETHER.DRV | 17,799 → **17,569** (−230) | 11,147 → **10,989** (−158) | 35 granules (161 bytes over the 34 step) |
| PCIETHER.DRV | 17,460 → **17,233** (−227) | 10,919 → **10,752** (−167) | **35 → 34** |
| SOUND.DRV | 10,965 → **10,835** (−130) | 9,458 → **9,354** (−104) | kept after attach −29 on every arm |
| HDD.DRV | 4,608 → 4,608; **resident span 4,094 → 3,901** (−193) | 4,021 → **3,927** (−94) | the span 195 under its step (was 2) |
| HDDTOOL.DRV | 16,665 → **16,231** (−434) | 12,229 → **12,191** (−38) | **16,896 → 16,384** while the tool is open |
| VESA.DRV | 7,564 → **7,639** (+75: +80 bss, −5 code - a faster text run, WANTS THE OWNER 10) | 3,698 → 3,765 (+67) | 7,680 either way |
| PC1MOUSE.DRV | 452 → **410** (−42) | 423 → **399** (−24) | |
| RAMDISK.DRV | 5,407 → 5,401 (−6) | 4,604 → 4,598 (−6) | |
| CDROM.DRV | 8,203 → 8,209 (+6) | 4,644 → 4,643 (−1) | **17 → 16 once attach has run** (its probe given back, `DRV_H_KEEP`) |
| NET.DRV | unchanged | unchanged | |
| OS88NET.COM | raw 13,872 → 13,756 | 10,318 → **10,244** (−74) | |

### 1.3 Disks

`python3 tools/os88diskuse.py --diff` against the base's images:

* **`os8088-360.img`: 27 → 30 free clusters** (CTRL.DRV, KEYBOARD.DRV and
  STIKMENU.DRV a cluster each).
* **`os8088.img` (1.44MB) and `mega.img`: +7 free clusters each**, and
  CPWIDE.DAT is gone from both: its 11 clusters against CPWIDE.DRV's +8,
  CTRL.DRV −1, KEYBOARD.DRV −1, PCIETHER.DRV −1, STIKMENU.DRV −1 (mega:
  SERIAL.DRV −1 for STIKMENU's). The other system-disk geometries carry the
  same files.
* `small360.img`, `util360.img`, `network360.img`: bytes only, no cluster.
  SYSCHECK.O88 is 15 bytes shorter: its manifest no longer lists CPWIDE.DAT.
* `COLDHMA.SYS` (the HMA kernel's `.cold`, packed) is 30 bytes shorter: its
  `.cold` carries the immediates of section 3.

## 2. Speed

Each figure is its agent's, and how it was counted is in its note: MartyPC
guest time for the Control Panel's open and pages (one measurement session
each), `tools/x3cyc.py`'s 8088 model over unicorn traces for the drivers'
paths, primitive and `int 13h` counts by harness.

| path | base | tip |
|---|---|---|
| **the wide Control Panel's first open** (XT, VGA, 1.44MB disk) | 8 `int 13h`, 3.78 s | **6, 3.22 s** |
| **its re-open**, the module image kept | 2 `int 13h` (the DAT), 1.64 s | **0, 0.90 s** |
| Drivers page: row click / Down / Up | 77 primitives, 424 ms | **45, 383 ms** |
| Drivers page: filter tab (1 row) / back to All | 125 / 311 primitives | **65 / 232** |
| Drivers page: keyboard scroll | 269 primitives, 1,083 ms | **204, 1,006 ms** |
| wide Display page: adapter press (two-adapter VGA) | 69 primitives | **41** |
| wide Display page: filter tab | 84 primitives, 16 `VXV_INFO` | **72, 5** |
| compact Display page: radio click | every adapter's label re-lettered (~34 ms on the XT, 3 rows) | the radio dots only |
| KEYBOARD.DRV, a keystroke (`a` make) | 2,866 clocks | **1,954** (−24.6% over 149,564 cases, none slower) |
| SOUND.DRV, single-cycle re-arm (every block on an STPC) | 2,278 clocks (dsp1: 1,990) | **2,039** |
| SOUND.DRV, every DSP write | 229 | **174** |
| ETHER, `NETV_UDPRX` one datagram | 17,400 | **5,127** |
| ETHER, raw 1,514-byte frame TX / RX | 95,035 / 92,502 | **28,498 / 28,528** |
| ETHER `ne_rx`, empty ring (every pump) | 719 | **349** |
| VESA.DRV text run (`VX_FONTRUN`) | 18.1M instructions / 800 runs | **9.96M**, same window switches |
| HDD.DRV mount | `int 13h` per scenario 3 / 5 / 8 / 5 / 9 | the same; ~25% fewer instructions (primary only 1,065 → 811) |
| HDD.DRV `hd_chs` (rung 0, per `int 13h`) | | **−39 clocks** |
| SERIAL.DRV read / write a byte | | **−40 / −48 clocks** |
| DISKOPS folder Delete | | **−176 clocks a file**, ~−670 a folder |

**No transfer call was added anywhere** (every agent's harness compares the
`int 13h`, controller, packet and XMS sequences). No hot path got slower.

## 3. The resident kernels

`tools/os88rdiff.py kernel 1b01907f1 .` on each kernel (it holds the build
number), every non-module section compared byte by byte:

* **No resident section changed size on any kernel.**
* The bytes that differ are all VALUES of immediates that name a module's
  own layout - the class the brief ruled allowed for `MODS_SIZE` (BRIEF 1)
  and that `ctrl` and `input` found has more members (WANTS THE OWNER 1):

| kernel | bytes | where |
|---|---:|---|
| kern_big, kern_emu | 7 | `osapi_font_glyphs` (KEYBOARD.DRV's `klf_saved_seg` offset), `mod_need` (`MODC_SIZE`, `MODS_SIZE`), `mod_need.whole` (`MOD_MAX_KB` 17 → 30, the high byte 44h → 78h) |
| kern_small | 2 | `osapi_font_glyphs` |
| kern_mega | 22 | `osapi_font_glyphs` (two offsets), `mod_need` (`MODC_SIZE`, `MODS_SIZE`, `MOD_MAX_KB`), `mod_hi` (`MODC_SIZE`), `kl_control_x` (`klm_scan`'s offset); and in `.mega`, `mega_dstubup` (HIBER.DRV's park stub, 1F80h → 1F79h) and `fsx_rsvcsz`/`fsx_rserdn`/`fsx_rserup` (SERIAL.DRV's lease cells, −29) - 11 low bytes |

## 4. The CPWIDE.DAT fold (the owner's instruction)

`cpwshell.md` is the record. CPWIDE.DAT's bytes are an `incbin` at the end
of CPWIDE.DRV's image; the 848-byte working area is the image's bss tail;
ES stays "the asset view" for every handler, now the image's own data view
(kern_mega: its writable alias). `cpw_open` went from 306 bytes to 85 and can
no longer refuse once `mod_need` has the image, so `cpg_open`'s
drop-and-compact arm went too. Every compact-face refusal is unchanged. The
assets also got smaller on the way in: each distinct 16x16 cell stored once
(−960) and the catalog's 20 reserved bytes a record dropped (−260).

**Three merge defects, all mine, and how they were caught.** The fold made
the working area a bss LABEL of the image, and the pages' agents had written
three expressions that need it to be a number (`lea si, [bp - CPD_ROWS]`,
`xor bx, CPT_X0 ^ CPT_Y0`, `lea ax, [di - CPV_ROWS - 1]`). nasm refused
them. My first rewrite (`label - cpw_bss + MODV_IMG`) assembled and was
wrong by 24 bytes - `cpw_bss` is not the first label in `.modvb` - and the
Drivers page drew an empty table. The fast tier did not see it.
`cpwpages`' MartyPC pixel compare against the base did, at once. The three
are now `mov`/`sub`, an `xchg` toggle and `xchg`/`sub`, with no layout
assumed (+5 bytes against the broken forms), and the same compare on the
corrected tree is the base's pixels in every gesture but the two showing
PCI Ethernet's memory figure, which this pass changed (1.2).

## 5. Defects found

Fixed:

1. **Compact Display page**: a radio click re-lettered every adapter row
   (`ctrl`).
2. **Wide Display page**: five redraws past what changed, against SPEC.md
   135.9.2's own paragraph - an adapter press repainted every row, a press
   repainted its group's box, a filter tab asked VESA.DRV again, Force Color
   redrew on any press, the startup box redrew the Running group (`cpwvid`).
3. **ETHER/PCIETHER**: `udp_queue` ran `movsw`/`stosw` before its `cld`, so
   a datagram arriving while a caller had DF set was stored BACKWARDS
   (`ether`).
4. **ETHER/PCIETHER**: the socket table and frame buffers sat at odd
   addresses since the UDP merge (`ether`).
5. **SOUND.DRV**: #363 routed the single-cycle re-arm through
   `sbl_dma_auto`, +288 cycles on every single-cycle block (every block on
   an STPC since #408); taken back to 2,039 (`sound`).
6. **`tests/essdma.py`** stubbed `OSAPI_CPU_INFO` at `0060:0155`; it has
   been `0060:0101` since the #365 flag day, so every ESS leg past
   `sbl_irq5_taken` ran into zeroed memory (`sound`; fixed by the
   coordinator).
7. Doc: SPEC.md 52.13.6's `hd_idbuf` size, stale comments in `wirezone.inc`
   (NETV_MAX), `sound.asm`, `apps.inc`, `tests/cswrites.txt`, `tests/hdext.py`.

Not fixed (described in the notes):

8. **HDD.DRV `hd_at_dup`** (`hdd.md`): a second IDE unit that also matches a
   BIOS row is unpaired as ambiguous but stays marked spent, and HDF_XCYL
   reads that mark - a BIOS that knows only the slave, clipped to 1,024
   cylinders, beside a master of the same heads and sectors could mount the
   slave twice. Base and tip alike. For whoever owns #386.
9. **HDD.DRV `hd_mount_chain`**: base + relative LBA is not checked for a
   carry out of 32 bits (a hostile disk can place nothing a primary
   partition could not already).
10. **SPEC.md 34.5.9** says a card that fails the probe refuses stereo and
    16-bit with err 7; verb 11 answers err 2, as at the base. A contract
    sentence, left for the owner.

## 6. WANTS THE OWNER

1. **The ruling, used and widened.** The brief ruled that a module saving may
   change the VALUE of `MODS_SIZE` in resident `mod_need`. The pass found the
   class has more members, and used them under the same proof (section 3):
   `MODC_SIZE` (any CTRL.DRV saving moves it), `MOD_MAX_KB` (the fold),
   KEYBOARD.DRV's internal offsets read by `osapi_font_glyphs` on every kernel
   and by kern_mega's `kl_control_x`, and HIBER.DRV's park stub and SERIAL.DRV's
   lease cells read by kern_mega's `.mega` (item 3). No instruction, length or size moved.
   **Confirm the ruling**, or each of those savings has to be padded back
   (KEYBOARD.DRV would keep its 11 granules and only its file saving).
2. **The fold's two consequences** (`cpwshell.md`): the open panel needs one
   contiguous ~26KB claim instead of two of ~14KB and ~16KB; and a refusal for
   want of heap is now remembered until reboot (SPEC.md 135.2's mark), where a
   DAT that could not be funded was not. Keeping the old behaviour is ~10
   bytes in `cpg_open`.
3. **kern_mega's resident names two module offsets** (`dops.md` CROSS-FILE 1):
   `mega_dstubup` adds HIBER.DRV's park stub offset and `fsx_rserdn` reads
   SERIAL.DRV's lease block. `dops` PINNED both with zero padding to keep
   `.mega` byte-identical under the brief's narrower ruling; the final pass's
   `buildmatrix` then failed on it - the `MEGADIAG` arms put more code above
   the stub than the fixed 1F80h allowed. Both references are labels of the
   same assembly, so the coordinator took the pins out under the widened
   ruling (item 1): `.mega` moves by 11 immediate bytes (section 3), the
   modules give the 36 bytes back, and the knob arms assemble. A fixed place
   or a run-time read would remove even those value changes; not needed.
4. **CDROM.DRV gives its probe back after attach** (`DRV_H_KEEP`, SOUND.DRV's
   mechanism): a loaded CD-ROM holds 16 granules while `DRVM_IMG_CD` (the
   before-attach figure) says 17 (`input.md`).
5. `klf_disable` clears its active byte after `sti` instead of before (−8;
   the byte is only read under the drawing lock it holds) (`input.md`).
6. Taken and stated: VESA.DRV **+85** for the text run at 55% of the
   instructions (`fe1d629bc`, can be dropped alone); CPWIDE.DRV **+36** for
   the Display page's redraw fixes; **`DRVM_CEIL_NET_PCI` 40 → 39** in the
   kernel and the SDK (a caption's ceiling DOS.O88 quotes - abilock updated
   without a `DRV_VER` bump, dsp1's precedent).
7. Not taken, priced:
   * SOUND.DRV: the re-arm's DMA programming inline, **+42** resident, the
     single-cycle re-arm 2,039 → 1,898 (faster than dsp1's 1,990).
   * ETHER/PCIETHER: the UDP queue (589 bytes) into a claim at `NETV_UDP`
     bind, **−576 RAM on every machine with a card** for ~+40 code, at the
     price of a new refusal at bind.
   * ETHER: DF now clear after `NETV_ADDR`, `NETV_RAW`, RAWTX and RAWRX (most
     verbs already left it clear).
   * HDD.DRV: stop the chain walk once the volume table is full: +15 span,
     one `int 13h` less on a disk with more volumes than rows; `align 4` for
     `hd_xa_read`.
   * CPWIDE.DRV: `cpk_text` fills instead of padding with spaces (+31, ~40%
     fewer glyph cells, ~180-270 ms a DETAILS repaint predicted); `cpw_hdr`
     without the paper fill (+4, two fills fewer a full paint).
   * VESA.DRV: `VX_ICON` by row origin (+63, but over a granule: +512 RAM on
     every VESA machine).

**WANTS AN ABI BREAK:** none, from any agent.

## 7. Cross-file and not reached

* The full-paint double writes in the wide chrome (`cpw_list`, `cpw_hdr`:
  ~13,900 pixels; `cpk_group`'s corners) - `cpwvid.md`.
* `tools/stkbalance.py` does not follow a `mov sp, bp` teardown (one byte in
  `hd_mount_chain`), a jump table (input), or an `%error` naming a label.
* `os88ovlchk` refuses `lods` in a module image (+2 in `cpd_cpyn`).
* HDD.DRV needs 317 more resident bytes for its 512 back; its attach-only
  code cannot move into the attach run (10 bytes free).
* Each note's NOT REACHED: HIBER's relaxed ladders (~−30), FORMAT.DRV's
  association writer, OS88NET.COM's ~230 bytes of zero state, the TCP
  pump's three socket walks, RAMDISK leftovers, KEYBOARD's compose table.

## 8. The final pass

**The union.** Every row the nine notes name, deduplicated: **298 soak
rows**, run once with `tools/os88soak.py` against a frozen snapshot of
`16fa9befe` (four emulator lanes, Bochs two a core). Before it, every
capability the union needs was installed so that it would answer rather than
skip: Bochs, 86Box (automation build), QEMU 9.2, the PicoMEM host firmware,
the C toolchain, DOSBox and `wiredisk`.

**Result: 290 ok, 5 FAIL, 3 SKIP in 47 minutes.** The skips are
`win16mscdex`, `win16hiber` and `win16megadgroup`, which want the WIN16
reference fixtures (`win16-reference` skill), not on this box.

| failed | cause | after |
|---|---|---|
| `buildmatrix` | `make megadiag` / `megadiag-hb`: the `MEGADIAG` arms put code above HIBER.DRV's park stub, past the 1F80h pin `dops` had added (6, item 3) | **fixed**: both pins out (`58530cfd1`); ok on re-run |
| `megap2hiber` | Bochs's debugger prompt not seen within 60 s, AFTER the guest reached its breakpoint in HIBER.DRV's wake (`hbm_wake`'s `.nowz`) | ok on re-run alone (16 s) |
| `modcache` | the modkeep VGA leg's first step, opening `CALC.O88` from B: before any module was loaded: `LD_EBAD` | ok on re-run alone |
| `ftpdflick` | its tick-release measurement was NOT SETTLED (a moving target); FTPD is untouched | ok on re-run alone |
| `stikmenu` | one read of the Desk Calendar's `W_FLAGS` just after launch (0081h, where the same window reads as a desk window a step later) | ok on re-run alone |

Because the `buildmatrix` fix moved kern_mega's HIBER.DRV and SERIAL.DRV, the
kern_mega rows over them were run again: `megahiber`, `megahibfull`,
`megadosp`, `megadosroom`, `walinkmega`, `megarmbref` - **6 ok**.

**`test-full`, once**: 78 passed, 3 failed, 1 skipped.

* `cswrite`: four sites in `cpw_vid.inc` - `cpwvid` wrote the Display page's
  tab labels into the image's `cpv_tlab` inside a `CSDO_ON` run with a call
  and string instructions in it, which is right on its branch and against
  the run's rules; after the fold ES IS the image's writable view, so the
  labels go through ES and the run is gone. **Fixed**, and `cpwide`,
  `megamodcache`, `mega-vesacp` and `mega-vesa` re-run: **ok**.
* `guidelock-full`: CPWIDE.DRV's manual page was stamped before the pages'
  and the Display page's merges; it says the same, but for the memory the open
  panel holds (29KB to 26KB). Restamped.
* `hostwait`: `tests/cpface.py`, `tests/ethcfg.py` and `tests/rdcz.py` hold
  host-time polls their lines in `tests/hostwait.txt` do not allow. **The
  same three fail at the base** (`1b01907f1`); none of the three files was
  touched by this pass. Not this pass's, and left as found.

`test-full` again after the fixes: **80 passed, 1 failed (`hostwait`, as at
the base), 1 skipped**.
