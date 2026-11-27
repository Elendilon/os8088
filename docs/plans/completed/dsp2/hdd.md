# Driver size pass 2: `drivers/hdd/` and FSCHECK.DRV (agent hdd)

Branch `dsp2-hdd`, from `1b01907f1` (the brief's commit on `aa6b428`). Owns
`drivers/hdd/` - HDD.DRV (`hdd.asm` and its includes) and HDDTOOL.DRV
(`hddtool.asm` and its includes) - and every line under `section .modfs`
(`kernel/fsck.inc`, FSCHECK.DRV). The target was #386's additions (logical
drives in an extended partition, rung 1 past 504MB, the packet calls past
8GB, the installer's Past-BIOS-Reach refusal), read routine by routine, then
a sweep of the rest. Every figure is from this worktree's own builds (`make
-j2`, `make -j2 emu`, `make -j2 mega`), base at `1b01907f1`.

Outside the owned files: SPEC.md 52.1.5, 52.4.1, 52.11.8, 52.13.6 and
118.14.7 (figures and one routine name), `tests/hdext.py`'s docstring (a
break-on-purpose note naming a routine this pass folded away; no check
changed) and `docs/INDEX.md`. `hddabi.inc` is untouched: `HD_ABI_VER` and
`tools/abi.lock.json` are as they were.

## 1. BASE AND TIP

| | | base | tip | delta |
|---|---|---:|---:|---:|
| **HDD.DRV** | image (RAM while attached, every hard-disk machine) | 4,608 | 4,608 | 0 |
| | resident span in front of `hdsec.inc`'s `align 512` | 4,094 | **3,901** | **-193** |
| | the attach run laid over `hd_mbr` (of 512) | 498 | 502 | +4 |
| | trailing zeros off the disk ("bss") | 32 | 16 | -16 |
| | file | 4,021 | **3,927** | **-94** |
| **HDDTOOL.DRV** | image | 16,665 | **16,231** | **-434** |
| | claim while open (`HDTOOL_PARA` paragraphs, the heap's 512 granule) | 16,896 | **16,384** | **-512** |
| | pad in front of `hd_mbr` | 397 | 11 | -386 |
| | file | 12,229 | **12,191** | **-38** |
| **FSCHECK.DRV** kern_big | image / file | 6,294 / 5,280 | **6,241 / 5,239** | **-53 / -41** |
| kern_emu | image / file | 6,283 / 5,270 | 6,230 / 5,229 | -53 / -41 |
| kern_mega | image / file | 6,286 / 5,272 | 6,239 / 5,236 | -47 / -36 |
| kern_small | - | carries none of the three | | 0 |

HDD.DRV and HDDTOOL.DRV are one image on every kernel's disks. **The
resident kernel is byte-identical on all four kernels**: `cmp` of each
`kernel.bin` against the base build at one commit, and `tools/kernsize.py
--json` identical. No `.modc` byte moved, so `MODS_SIZE` and the ruling on
it were not needed.

**HDD.DRV's image did not move, and cannot in this pass's units.** It is the
resident span padded to 512 plus the 512-byte attach run: 4,608 while the
span is 3,585..4,096. At 3,901 the span is **195 bytes under the 4,096 step**
(a tenth half-KB claimed on every hard-disk machine) and **317 above the
3,584 step** (the ninth given back). The span's attach-only part is now
`hd_at_dup`, `hd_twins` and `hd_at_ident` (~280 bytes); the run they would
have to join has 10 bytes free, so the 317 is resident code, not layout.
Design was for bytes, not that step.

Clusters, base -> tip (the bytes are the result, the clusters a consequence):

| disk | HDD.DRV | HDDTOOL.DRV | FSCHECK.DRV |
|---|---|---|---|
| `os8088-360.img` (512-byte clusters, 27 free -> 27) | 8 -> 8 | 24 -> 24 | - |
| `util360.img` (1 KB clusters, 261 free -> 261) | - | - | 6 -> 6 |
| the other system geometries, kern_mega's disks | unchanged | unchanged | unchanged |

The next cluster down: HDD.DRV 343 file bytes (3,584), HDDTOOL.DRV 415
(11,776), FSCHECK.DRV 119 on util360 (5,120).

## 2. TAKEN

Seven commits after the INDEX fix. Each driver commit was assembled, packed
and put through the harness (section 3) from its own staged tree; the full
`make -j2` (fast tier, doc gates) ran on the tree holding all of them, and
again at the tip with `make -j2 emu` and `make -j2 mega`. File bytes per
ITEM below are leave-one-out readings at the tip (the item reverted alone,
re-assembled, re-packed): lz4's context moves with every byte, so they do not
add; the totals in section 1 are the measured ones.

### FSCHECK.DRV (`6a6e31058`) - image -53, file -41

| item | image | hot? | equivalence |
|---|---:|---|---|
| kmod 9's four tails: `fsk_lost_chain` falls into `fsk_save` (its `call`/`ret` were onto the next byte); `fsk_save`, `fsk_lost_rest`, `fsk_ph_sync` end in `jmp` | -7 | the lost-chain and FAT-copy phases | reading: none of the three callees reads its return address or its depth, and `fsk_die` unwinds through `[fsk_sp]` from any depth |
| `fsk_rootsec`..`fsk_wr` (the readers' fall-through chain) beside `fsk_ioerr`: both transfer `jc`s short | -6 | **every sector the engine reads or writes**: a not-taken `jc` (4 clocks) where a `jnc`/`jmp` pair took a jump (16) | reading: same code, every call in the same order |
| FSK_DELSYS's six `.bad2` refusals reach a second stub placed after an unconditional jump; `je .noent` short with them | -15 | cold | reading |
| `fsk_ph_tree`'s `.dirdone` between its five jumps (the root's was a 5-byte pair) | -3 | per root sector, the not-taken case 12 clocks faster | reading |
| `fsk_filent`'s `.done` (`jmp fsk_eback`) as two stubs in reach of its jumps | -14 | per file entry, same jumps | reading |
| `fsk_defskip` for `fsk_defent`'s first two `.skip`s; `fsk_kids`' loop tail rotated to the top | -8 | defragment only | reading |

19 of the module's 22 relaxed `jcc`s are short now; the listing of `.modfs`
was diffed base/tip and no transfer instruction moved.

### HDD.DRV: the transfer path (`bc5df5344`) - span -50, file -21; HDDTOOL file -4

| item | span | hot? | equivalence |
|---|---:|---|---|
| `hd_chs` (both images), 78 -> 71 bytes: BX banked and never used; the 1,024-cylinder test falls through, the large-disk test out of line at `.big` (#386 made the common case a taken jump); `jcxz`; a CLC_OR_STC tail | -7 | **per int 13h on rung 0, per command on rung 1**: ~39 clocks less on an 8088. The BX bank alone is +2 HDD file (leave-one-out): a hot-path speed item at a two-byte cost, the brief's welcome case; the routine as a whole is file-negative | harness; fuzz with LBAs at cylinder 1,023/1,024 and the drive's own last cylinder |
| eight `mov dx, bx / add dx, IDE_x` -> `lea dx, [bx+IDE_x]` | -16 | rung 1 (286+): 2 clocks less each; `hd_ide_drq`'s is **per sector** | harness (every port write traced); file -5 |
| `hd_xfer_ide`: the run cap tests AH; with the `lea`s its post-select `jc .fail` and its top `jz hd_xfer_ok` are short | -7 | per command, ~10 clocks less on a 286 | harness |
| `hd_xfer_ide`'s two LBA refusals through a `.refuse` stub | -3 | per LBA-mode command | harness, a partition straddling LBA 2^28 |
| `hd_xfer_rst`: rung 0's reset-and-retry, one copy for the CHS and packet runs; `hd_xfer_ext`'s run ends at `hd_xfer.next` (its `jcxz` reaches it), the walk it repeated | -17 | the retry is the error path (+1 call a retry); the packet run's jumps unchanged | harness with sectors failing 1, 2, 3, 100 times; packets traced; file -6 |

### HDD.DRV: the mount (`3b695404a`) - span -99, file -49; HDDTOOL file -9

| item | span | equivalence |
|---|---:|---|
| `hd_part_load` (both images) blanked `hd_mbr` before the read too: a read that succeeds writes all 512 bytes and every other way out blanks again, so that blank (256 stores, ~0.75 ms an XT, every table read) was never seen. Its body is now `hd_rec_load` (DX:AX = the LBA): 61 -> 11 + 45 | -5 | fuzz: a signed / unsigned / failing / failing-once LBA 0, `hd_mbr`, `hd_mbrok`, CF |
| `hd_mount_chain` (181 -> 153 bytes): each record read by `hd_rec_load`; its base, length and current record a BP frame (12 bytes of resident data gone, a byte less an access; the loop's back edge short; `add sp, 12` to tear it down, which the stack walker reads) | -40 | harness (chains of 2, 5, 24, 0Fh, a backward link). Against the same walk with memory variables: file -7, span -19. Every routine and kernel cell the walk calls keeps BP (os88api.inc's contract; `hd_xfer` banks it) |
| `hd_mount` (110 -> 94): mount each slot, then ask isext (an extended entry is no FAT type, so `hd_mount_slot` skips it); the slot in AL; `cmp [hd_xslot], al / jb` keeps the first; the 0FFh test beside the chain's call; `hd_msgc`/`hd_nmnt` one word store (asserted adjacent) | -16 | harness; file -5 |
| `hd_part_isfat`/`hd_part_isext` one test with two masks (`hd_part_istype`) | -12 (tool -2) | fuzz, types 0..FFh; file -10 HDD, -21 HDDTOOL with the installer's use of it |
| `hd_vol_new` without CX; `hd_dev_row_ck` a tail onto `hd_dev_row`, whose `add` cannot carry; `hd_mbr_blank` stores AL; `hd_entry` one compare for ATTACH (asserted below DETACH) | -15 | fuzz; HSV verbs; file -4 (`hd_dev_row_ck`), -4 (`hd_mbr_blank`) |
| `hd_svc_raw`/`hd_svc_mount`: three relaxed `jc hd_svc_out` land on their own final `jmp hd_svc_out` | -9 | every HSV verb in and out of range; file -5 |

`hd_pslot` is left at 3, not 4, after a walk with no extended partition: a
scratch nothing reads after a mount (`hdext` reads it after a chain: 5, as
before). (`hd_part_used`'s 2 bytes were in this commit and are REFUSED below.)

### HDD.DRV: attach (`2cebd4da7`) - span -46, run +4, file -25; HDDTOOL file -5

| item | bytes | equivalence |
|---|---:|---|
| `hd_at_xcyl`, a second walk of the device table, folded into `hd_at_dup`'s: sectors per track compared first, the unspent rows counted in CL, answered in AL; `hd_at_channel` sets `HDF_XCYL` before `hd_at_geom` reads it | span -36, run +5; file -20 | harness: a spent row, a translated row sharing spt, two BIOS drives one IDE unit matches. SPEC.md 52.1.5 and hdext's break-on-purpose note follow |
| `hd_at_ident`'s counts are byte loads (CH is 0 after the REP and the LOOP); `hd_at_bios` hands AH=41h the drive from BL | span -2, run -1 | harness (IDENTIFY and AH=41h traced) |
| `hd_geom_ok` (both images): `dec` and one unsigned compare a bound, a CLC_OR_STC tail | -8; file -6 HDD, -8 HDDTOOL | fuzz |

### HDDTOOL.DRV (`f38b00a59`) - image -434, file -15, claim -512

| item | bytes | equivalence |
|---|---:|---|
| `hd_tshut`, `hd_tbusy`, `hd_win_live` (78) moved past the buffers, to the END: four placements tried, that one packed smallest (12,201 against 12,203/12,204/12,206 at the time) | image -434 | layout; every routine byte-identical |
| `hd_tw_geomok`'s past-1,023 marker: one word, `or al, 3Fh / inc ax / jnz` (asserted `HP_SCYL = HP_SSEC + 1`) | -7; file -4 | tool harness |
| the installer's FAT12/16 test is `hd_part_isf16` (the type test with FAT32 masked out) | -3; file -10 | tool harness, against the inline test it replaced |
| `hd_inst_apps`'s `jmp short .out` to the next byte | -2; file -3 | reading |
| Format and Delete share `hd_tw_unmount_sel` | -9; file **+2** alone | reading. Kept on purpose: without it the code in front is ONE byte past 13,312 (image 16,743, the claim back to 16,896), and the cheapest other way back - `hd_tw_unmount_slot` moved past the buffers - is +7 file |

48 bytes freed in front of the buffers over the four driver commits, plus the
78 moved: the pad is 11.

### The refusal (`f1b3eae58`) - HDD file +1, HDDTOOL file -5

`hd_part_used`'s `cmp word [si+HP_SECS+2], 1` tail (2 bytes of image in each)
broke a match lz4 had in the tool; reverted to the base's form.

## 3. SPEED

**The harness.** In scratch, not committed: a unicorn 2.1.4 harness that
loads the base and the tip images and runs them against one model of the
machine around them - int 13h (AH=00/02/03/08/41/42/43, a CHS walk inside
the cylinder, sectors failing N times), the IDE task file (IDENTIFY with word
49, INITP, READ and WRITE in CHS and LBA mode, two units a channel), and the
OSAPI cells (far cells and the rare door). It compares the TRACE of
everything that crosses the image's edge (each int 13h's inputs, each packet,
each port write, each cell's inputs, image pointers as symbol+offset), the
final device and volume tables, the caption, the settings blob, buffers and
disks. Four parts: `t_mount` (15 boot scenarios: attach, ready, automount),
`t_xfer` (100s of random DSV_BLK transfers a scenario - rungs 0 and 1 and the
packet path, reads and writes, odd buffers, failing sectors), `t_fuzz`
(every changed routine on random inputs, every HSV verb), `t_tool` (the tool
image's pure routines). **Broken on purpose, 13 ways** (the forward test
gone, the run walked one sector short, no reset before a retry, the 28-bit
LBA refusal skipped, HDF_XCYL always, a zero-length entry used, no signature
read as OK, cylinder 1,024 taken on a BIOS row, 16 heads refused, the range
check inverted, the marker test inverted, FAT32 let in, no clamp past
1,023): every one goes red.

**The mount, int 13h calls a scenario** (issued by the driver at attach +
ready; the kernel's own mount reads are the kernel's, and the same):

| scenario | base | tip | instructions base -> tip |
|---|---:|---:|---:|
| C: only (rung 0) | 3 (08h, 41h, the MBR) | 3 | 1,065 -> 811 |
| C: + 2 logical (#386's disk) | 5 | 5 | 1,901 -> 1,717 |
| C: + 5 logical (the table full) | 8 | 8 | 3,257 -> 3,142 |
| a backward link | 5 | 5 | 1,911 -> 1,734 |
| a 24-record chain | 9 | 9 | 3,662 -> 3,565 |
| rung 1 takes the drive (286) | 3 + IDE | same | 3,063 -> 2,778 |
| 9GB through the packet calls | 3 | 3 | 1,071 -> 817 |

Instructions are unicorn's, each REP element counted; most of the saving is
the MBR's dead blank (~0.75 ms on an XT) and `hd_chs`. An extended record
costs ~90 clocks more on its own (a call into `hd_rec_load`); every
scenario's walk is still fewer instructions. **No transfer call was added
anywhere**; the one this tree could save is under WANTS THE OWNER.

**The sector transfer.** Rung 0, per int 13h: `hd_chs` ~39 clocks less (8088,
`max(clocks, 4 x bytes)`: a push and a pop gone, a taken `jb` now a
not-taken `jae`, `jcxz` for `or`/`jz`, `test al, imm` for `clc`). Rung 1,
per command: ~15 clocks less on a 286 (`lea`s, `test ah, ah`, two relaxed
pairs short); per sector, `hd_ide_drq`'s `lea` (-2). The per-sector loop's
code is otherwise unchanged; its jump TARGETS moved with the span, and on a
16-bit bus the unarmed read's taken targets went from six odd addresses to
three (`.sector`, `.rins`, `.advance`, `hd_buf_step`, `.noseg`,
`hd_ide_wait.ready` now even; `hd_ide_drq` and two return addresses odd).
The armed 386 XMS fill calls `hd_xa_read` at E6Dh (it was F30h, dword
aligned): one call a sector, against ~256 us of `rep insw` - named, not
padded (WANTS THE OWNER). Over 100 random transfers a scenario: rung 0
74,008 -> 73,542 instructions, rung 1 3,152,646 -> 3,145,832, packet calls
69,469 -> 69,000.

**FSCHECK's scan**: no transfer added, moved or reordered, so its int 13h
counts are the base's by construction; each `fsk_rd`/`fsk_wr` takes a
not-taken `jc` (4 clocks) where it took a `jnc`/`jmp` pair (16).

## 4. REFUSED

| item | image | file | why |
|---|---:|---:|---|
| `hd_part_used`'s `cmp ..., 1` tail (taken, then reverted) | -2 each | HDD -1, **HDDTOOL +5** | leave-one-out at the tip |
| `hd_cfg_mark`'s blob header by `stosw` | span -2 | **+1** | tried and measured |
| `hd_tw_unmount_slot` past the buffers, instead of the unmount share | tool A -25 | +7 | the share is the cheaper way to hold the alignment |
| a jump table for HDDTOOL's `hd_tentry` (eight relaxed `je`s, 40 bytes) | ~+5 | | every verb's registers pass straight through to the handler, BX included (the pane coordinates); the 8086 has no cheap way to bank one |
| `hd_xfer_ext` folded into `hd_xfer`'s attempt loop | ~-10 | | a mode test on every CHS attempt, rung 0's common path, for a path only a disk past 8GB takes |
| `hd_xfer_ide` before the shared tail (so `je hd_xfer_ide` and its refusals are short) | -3 / +10 | | `hd_xfer_ext`'s jumps into the tail go long instead |
| `hd_svc`'s handlers re-ordered round `hd_svc_ok` | ~0 | | what four handlers gain the next four lose; the `.out` stubs took the 9 |
| `fsk_filent`'s SHORT block above LONG (`jb .short` short) | -1 | | a reordering of the check's busiest routine for one byte |

dsp1's REFUSED items (the `hd_*dev_row` helpers, the resident ladder, the
composed confirm string) were not re-proposed: each still grows the file.

## 5. WANTS THE OWNER

- **A long chain stops reading when this walk has mounted and the table is
  full** - one int 13h (~400 ms on an XT) saved a mount of a disk with more
  FAT volumes than `hd_vols` has rows (C: + six or more logical drives, or
  several disks). Four instructions at `hd_mount_chain`'s `.ebr`: when
  `[hd_nmnt]` is non-zero and `hd_vol_new` finds no free row, end the walk.
  Behaviour-identical by construction (once this walk has mounted, the
  caption is `Mounted n`; a full table mounts nothing; each further record
  is a read that can change nothing) and by the harness (every scenario's
  volumes, caption and blob identical; the 24-record chain 9 -> 8 calls).
  **+15 resident span bytes (image 0), +10 file.** Not taken: a cold path's
  speed bought with bytes, the brief's own case for the owner.
- The armed 386 fill's call target (section 3): an `align 4` in front of
  `hdxms.inc` puts `hd_xa_read` back on a dword, 0..3 span bytes (image 0),
  if the owner wants it pinned.
- The ruling on `MODS_SIZE` was not used: FSCHECK.DRV is no `mod_tab` row.

## 6. WANTS AN ABI BREAK

None. `hddabi.inc`'s values and layouts were not needed to move; `hd_svc`'s
verbs, `HRQ_*`, the device and volume rows are as they were.

## 7. CROSS-FILE

- **`DRVM_IMG_HDD`** (`kernel/driver.inc`, the coordinator's) stays **9** =
  ceil(4,608 / 512); `DRVM_CEIL_DISK` stays 5. **No `DRVM_IMG_*` figure
  moved.**
- **HDD.DRV's image wants 317 more resident bytes** to give the ninth
  half-KB back. The attach-only code still in the span (`hd_at_dup`,
  `hd_twins`, `hd_at_ident`, ~280 bytes) cannot join the run (10 bytes free)
  and could only go by the loader shrinking a claim after attach, which dsp1
  priced at 0 for this driver (its tail is `hd_mbr`, which stays) - still so.
- **`tools/stkbalance.py`** does not model `mov sp, bp`, so a frame torn down
  that way reads as a leak and `hd_mount_chain` spends a byte on `add sp,
  12`. Teaching it `mov sp, bp` after `mov bp, sp` would let frames take the
  2-byte form.

## 8. ROWS TO RUN

Fast tier (every `make` here ran it green): `installabi`, `stkapps`.

Soak - the transport, the mount, attach (HDD.DRV): `hdext hdextloop hdextxt
hdextlba hdextebios hdtake hdtakeboot hdtakeblank hdauto hdnoclaim hdbounce
hdboot hdsize hdmap hdhiber hddgeom cpnameshdd kdhdd knobhd drvcut drvovl
drvup icohd bigvol doscopyhd vidxiphd vidxiphdhold vidxiphdnoharm viddisk
viddiskcpu vidbigclus vidhdmake vidkern hmadrv hmapool hmahiber hmadosret
hma286 megahddtick`, and on 86Box `box-hdtake box-hdtakeblank
box-hdtakeboot`.

Soak - the tool and the installer (HDDTOOL.DRV): `hddcp install instassoc
instcross instdeep instimg instkeep inststate httpinstall netinst netinstbad
megainst`.

Soak - FSCHECK.DRV: `fsckdisk fsckhd fsckmega syscheck syscheckmono`.

And `buildmatrix` for the knob arms (`diskcnt`, `instchunk`,
`instchunk-tool`, `nohdcyl`, `hdcylprobe`); every arm also assembled here by
hand at the tip, with `-DDRV_ORG=0xC000` for the HMA copy (INSTBENCH's
HDD.DRV is 4,608 now, 5,120 at the base; knob builds bind no budget).

## 9. LOOKED

One boot at the tip on MartyPC `os8088_xt_hdd` (the 8088 with an XT-IDE,
issue #386's machine), the 360KB pair, `tests/hdext.py`'s own builder making
the reporter's disk (C: primary, D: and E: logical in a 0Fh extended
partition) in a 654/16/63 VHD. HDD.DRV loaded at 9EE0h; device 0 the
XT-IDE ROM's (rung 0), 654/16/63; `hd_vols` slots 0, 4, 5, parents 0, 1, 1,
bases 63, 20223, 40383 - the three the builder placed; the walk stopped at
slot 5. The desktop shows C:, D: and E: beside A: and B:. Nothing was
clicked.

## 10. DEFECTS FOUND

- **Not fixed - a question for #386's owner.** `hd_at_dup`'s ambiguity rule
  unpairs a row that a second unit also matches but leaves its bit in
  `[hd_dupd]` ("spent"), and the HDF_XCYL count reads that bit: a row
  unpaired as ambiguous does not hold back HDF_XCYL for the second unit. A
  machine whose BIOS knows only the SLAVE of two IDE drives, reporting it
  clipped to 1,024 cylinders, with a master of the same heads and sectors,
  would give the slave both its BIOS row and an IDE row past cylinder 1,023
  - mounted twice. A corner of a corner; base and tip behave alike (the
  harness's `xcyl-spent` scenario is that shape with the BIOS row on the
  master, where it is right).
- **Documentation**: SPEC.md 52.13.6 said `hd_idbuf` is fourteen bytes; it
  has been sixteen since 52.1.5 kept word 49 (a parenthesis added). 52.4.1's
  "4 bytes left before the align" and 52.11.8's tuning history are brought
  up to date.
- **Process**: the base worktree's `make` failed `checkdocs` (the brief's
  commit left `docs/INDEX.md` one plan stale); regenerated, committed first.
- `hd_mount_chain`'s absolute LBA (`base + relative`) is not refused on a
  carry out of 32 bits; the comment's "an overflow refused" is the drive's
  END against the partition. A hostile MBR can put a primary anywhere
  anyway, so this aliases nothing a primary could not; noted, not changed.
