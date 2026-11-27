# Kernel size pass 21: the record, and what is left for a twenty-second

**PASS 21 HAS LANDED** on `claude/kernel-size-pass-529zgd`, cut from
`elendilon` at `dbc5ef8b4` on 2026-11-27. Like every record before it, it is
named `-P22` for the pass it hands to. The brief is
`docs/plans/completed/ksp21/BRIEF.md`. Each agent's note sits beside it and
is the authority on its own items.

## 0. The brief and the outcome

The owner's words: *"Its time for the next kernel size pass. Big is now in a
more stable shape, and we just had to put a few operations back into it; the
goal is to find ~350b to offset them. The kernel has been size passed many
times; you can dig deep, and start many agents to cover even smaller areas
of the kernel. This pass cannot be ABI breaking; that was the last one. More
than 350b is not refused; you don't have to stop there if agents have more
leads."*

The operations put back were Rename, New Folder and empty-folder removal
(`7f08a100b`, +282 `.cold`). They stay resident. diskw.md items 1 to 5 take
121 bytes out of them and out of the swapped-floppy check that came with
them.

**kern_big came down 1,127 bytes, about three times the goal.** Every kernel
shrank, and kern_big, kern_small and kern_emu each lost a rung.

- **ABI:** frozen as the brief required. `tools/abi.lock.json`,
  `apps/os88api.inc`, `drivers/os88drv.inc` and `apps/cc/` are untouched,
  and no published contract moved.
- **Disk calls:** no `int 13h` call was added or removed.
- **Speed:** `sch_isr`, `sch_switch` and the door are byte-identical.

### Kernel resident, assembled (`tools/kernsize.py --json`)

Resident = `.text` + `.bss` + `.cold` + `.lowbss` + `.vgabuf` + `.vga`
(+ `.mega`).

| kernel | base `3fc4e9d09` | tip | delta | `KERN_SIZE` |
|---|---:|---:|---:|---|
| **kern_big** | 90,225 | **89,098** | **-1,127** | **95,744 -> 94,720**, two rungs (accrued 113 -> 10 of 512) |
| **kern_small** | 55,672 | **54,837** | **-835** | **57,344 -> 56,832**, a rung (accrued 376 -> 53) |
| kern_emu | 90,471 | **89,338** | -1,133 | **95,744 -> 94,720** |
| kern_mega | 134,293 | **133,138** | -1,155 | conventional sections 56,415 -> 55,939 (-476); footprint **61,952 -> 61,440** of 68,096; `.mega` unchanged |

kern_big's sections are: `.text` 39,510 -> 39,106, `.bss` 4,973 -> 4,913,
`.cold` 37,830 -> 37,188 and `.vga` 2,218 -> 2,197. kern_small's `.text` is
29,101 -> 28,713, `.bss` 2,843 -> 2,783 and `.cold` 20,860 -> 20,473.

**Module images.** No module grew where the move did not buy resident
bytes:
- FILECP.DRV went down 44 bytes and DOS.O88 80 bytes on disk.
- kern_small's DISKOPS.DRV went down 25 bytes, and its CTRL.DRV and
  FDLG.DRV 24 each.
- EXTD.DRV is +4 and HIBER.DRV +2, which buys -2 resident each (sweep
  items 1 and 2).
- Packages that assemble the os88ui scroll bar are -2 each.

## 1. Who took what

Each agent's figures are against `3fc4e9d09` on its own branch; the sweep's
are against the merged `0d84b497b`. Bytes are big / small / emu / mega.

| agent | owns | big | small | emu | mega | the largest items |
|---|---|---:|---:|---:|---:|---|
| **diskw** | diskw, diskmut, diskops, loader | -158 | -78 | -158 | -187 | the three file operations brought back and their swapped-floppy check, -121 and still resident: `dskw_wck` -18, the tree's dispatch as a `dskw_wrap7` body -32, `dskw_rmbody_n83` with its helpers inlined -35, rename's name in BX -25. Also `dskw_alloc`/`dskw_now` bank nothing (-16) |
| **sys** | memory, instance, sched, mod, events, apps | -107 | -59 | -107 | -104 | `app_launch`'s record stamped while unpublished (-8), `inst_charge` on the KENT ladder (-7), the VESA About line as one loop (-9), `mem_hifit` through `mem_next` (-6) |
| **desk** | desk, desksc, assoc, fdlg, filecp, stikmenu | -105 | -30 | -105 | -106 | the copy engine (-61: `fcp_xfer`'s error tail -12, `fcp_fnames` written in at its call -10, `fcp_run2` -9), `osapi_desk_item_x` (-10), **`assoc_sweep`'s DI (a defect, +2)** |
| **files** | files, dskwin | -127 | -104 | -127 | -127 | the paste union built straight in `wm_dmg` (-23), `fm_reloc` by value (-16), `.bss` cells with disjoint lifetimes shared (-12), nine `kretc_di` hubs (-11) |
| **ui** | ui, menu, fprog, dock, toast | -112 | -104 | -112 | -112 | `[menu_ent]` gone (-9, pass 20's REFUSED 1, with `uilat` moved to `menu_cell`), `ui_drag_xor` through `rect_get` (-10), `db_paint` counting in SI (-10) |
| **wm** | wm, winmod, extmod, deskmod, os88ui's kernel arm | -92 | -98 | -92 | -92 | `os88ui_krec` preassembled (-24 `.cold`), `wm_draw_shadow` keeps AX/DX (-12), the os88ui `.cold` arm through `kentc_bp` (-12/-8), kern_small's `wm_dmg_bands` straight-line (-19 small) |
| **hw** | kernel.asm, driver, fsx, snd, clock, vid*, ctrl, cpw*, boot3 | -62 | -88 | -62 | -50 | `cp_open_x` its own far entry (-15 `.cold`), `osapi_font_glyphs` by `les` (-7), kern_small's `fsx_capstab` stopping at the CGA id (-61 small) |
| **draw** | vga12, softgfx, icons, blank | -89 | -94 | -89 | -86 | `gfx_spans` clipping in registers (-20), `gfx_blit4`'s guards short (-14), `vga_p4build` (-10 `.vga`), kern_small's dead complemented `gfx_blit1_x` loop (-62 small) |
| **input** | mouse, keyboard, serial, font | -88 | -58 | -92 | -91 | `kl_control_x` (-23/-32), `font_run_x`'s per-run prologues (-24, H1, fewer clocks), `kbm_isr`'s self-chain refusal into the eat tail (-8) |
| **disk** | disk, drvvol, lz, lzfilt, fsck, clu | -129 | -81 | -129 | -130 | `dsk_find_x`'s record by string stores (-21), the quiet-mount test as `dsk_mquiet` (-13), the IMG icon through the run decoder (-10), `dsk_rah_flush` (-7) |
| **sweep** | every file, after the merge | -58 | -41 | -60 | -68 | the agents' CROSS-FILE leads: `assoc_compose` and `desk_learn_x` written in at their one call in disk.inc (-18), `str_len` inline (-6), nine `jcc +2 / jmp` pairs, `dskw_czseg` as one relocation row (-4). Also **the FIND flags defect (+2)** and **the 0x0855 trap (0)** |

The ten by-file branches merged with no conflict beyond the generated
`docs/INDEX.md` and `tests/megaseg.txt`; section 7 has that lesson. The
sweep ran alone on the merged tree, because its leads crossed every owner's
files.

## 2. Speed and the disk

- **No `int 13h` call was added or removed.** Every agent on a disk path
  wrote its scenarios and their call counts in its note.
- **H1/H2 routines:**
  - `font_run_x` (input item 9) runs fewer clocks.
  - `kbm_isr` runs the same instructions and takes the same jumps on every
    path.
  - Every other H1/H2 routine is byte-identical.
- **H3/H4 costs, each under 1% of its operation:**
  - `inst_charge` on the KENT ladder: about +100 clocks per charged callback.
  - The os88ui `.cold` arm's `kentc_bp`: about +100 clocks per control draw.
  - `ui_drag_xor` through `rect_get`: about +99 clocks per draw.
  - `wm_close_req`/`wm_destroy` through `wm_dmg_bit`: about +45/+140 clocks.
  - `dskw_wck`'s common path: about +21 clocks per write, against at least
    400 ms of I/O.
  - Many other items are faster; each note gives its counts.
- **`hotpar` is green on kern_big and kern_small at every merge.** Several
  agents removed existing parity pads, each paired with a real odd saving.
  The sweep added no pad.
- **Some unpinned code sits at an odd shift** (sweep.md, draw.md):
  - kern_big: `.text`'s `clk_h12h..wm_apply_wh` and
    `wm_fullscreen..toast_place`.
  - kern_small: `.text`'s `clk_h12h..toast_place`.

  This costs a few clocks per word fetch on an 8086, V20 or 286 bus and
  nothing on the 5150's 8088. Two PARITY pads (+2) would put those runs
  back. That is not taken, and is the owner's call.

## 3. Behaviour

Byte-identical everywhere except the two defects fixed and the flag
differences listed after them.

**Defects found and FIXED:**

1. **`assoc_sweep` overwrote `assoc_tryvol`'s DI** (desk, `b4e2bde9e`, +2
   inside a -8 commit). On kern_big, kern_emu and kern_mega, the sweep's
   redirected-volume arm called `drv_cls_svc_x`, which answers in DI. So
   every volume swept after a RAM disk or file share was searched with a
   driver-table offset as its "app slot". If the program was found there,
   `assoc_locate` wrote the hint through that offset, into `.text` at
   `assoc_drv`/`assoc_clus` plus the offset. It is reachable whenever a
   redirected volume is mounted and a document's program is neither at its
   hint nor in the document's folder. No row reached it.
2. **`dsk_find_x` on a redirected volume put the next slot number's high
   byte into the +22 flags word** (disk found it, the sweep fixed it, +2).
   From ordinal 255 a RAM-disk or cable listing reported OSAPI_FIND_CZ
   (compressed), and from 511 OSAPI_FIND_FAR. The fix is `mov ch, 0` at
   `.stage`.
3. **The `COLD_HOME` = 0x0855 build trap** (sweep, 0 bytes). WIN95.DRV's
   `sub dx, 7 / cmp [di+W_H], dx` assembles to bytes that `os88rom.py hma`'s
   cfix proof reads as a far jump into `.cold`, so `make` failed at
   `build/coldhma.sys` whenever the layout put `.cold`'s home at 0x0855.
   Three agents' branches passed through that value during this pass. The
   bytes are now `add dx, -7`.
   - Before the change, the proof went red at 0x0855 (WIN95.DRV +0x265).
   - After it, the proof is clean for 0x0820..0x0870 on kern_big and kern_emu.
   - Wider, there is one hit at **0x0872**: a real far call in CTRL.DRV and
     DISKOPS.DRV whose offset's high byte is 9Ah. It is noted and not
     chased (section 5).
4. **Keypad 5 never reached the BIOS on kern_big, kern_emu and kern_mega**
   (input found it; the owner said take it, after the close, 0 bytes). Since
   #371 (`d4349a0a4`) the PC1 filter's eat tail sat between `KBM_SCAN` and
   `.chain`. The keypad-5 arm ends by falling through, so it fell into the
   tail: acknowledged and EOI'd on an XT, refused in int 15h's frame on an
   AT, and never stored, against SPEC.md 9.6.4 and 9.15. `KBM_EAT` is now
   after the chain on every kernel, kern_small's layout all along, and every
   way in is a jump.
   - Sizes are identical on all four kernels, and kern_small is
     byte-identical. On kern_big only `kbm_isr` changed, at the same
     address, and nothing shifted.
   - `tests/unit/t_pc1mouse.py` now guards that nothing sits between the
     `KBM_SCAN` expansion and `.chain:`. It went red against the old layout.

**Flag differences, none of them read by any caller and none in a
contract:**
- OSAPI_KEYBOARD's refusal returns different undocumented flags (ZF, SF, PF,
  OF and AF). CF, IF, DF and AX are identical.
- A refused `font_char` glyph returns different flags.
- An empty OSAPI_GFX_POINTS call returns the caller's own flags.
- Several kernel-internal routines now clobber registers they used to keep.
  Every caller was read, and each note's TAKEN line says which.

## 4. Wants the owner

1. ~~Keypad 5 eaten on kern_big, kern_emu and kern_mega~~ - **taken on the
   owner's word, 0 bytes: section 3 item 4.**
2. **No-force flag as `call bp`** in `wm_paint_dmg`/`wm_paint_all` (wm.md):
   -3 on big/emu/mega. The damage pass gets faster, but each whole-desktop
   pass costs about +22 clocks. That path was bought by the flag's own speed
   commit, so the speed rule holds it.
3. **`wm_su_flay`'s `.clamp2` as a loop** (wm.md): -5 on both kernels, about
   +58 clocks per call on the raise cache.
4. **kern_small's dock strip** (wm.md; not a size item). SPEC.md 11.91.7
   says kern_small rebuilds it on every whole-desktop pass because the
   6-byte flag did not fit. kern_small is now 835 bytes lighter, so that may
   be worth revisiting.
5. **Two parity pads (+2)** to put the odd-shifted unpinned `.text` runs
   back (section 2).
6. Still open from passes 19 and 20, and ABI, so not this pass's:
   `OSAPI_BATCH_END` withdrawn (-18) and `W_DISP`'s offset dropped (about
   -20). Also LAST-DROP 7.8.1, the Dock's patched far jumps (-42,
   self-modifying).

## 5. What is left

Each item is in its note's REFUSED or CROSS-FILE list, with the arithmetic.

- **`inst_rel_rec` merged with `xm_release_rec`** (about -5, hw.md and
  sweep.md). It deepens a worker teardown's stack by 16 bytes, and needs
  the stack class proved first.
- **`ui_drain` as `resb 1` and dockmod's `[dock_drew]`** (-1 `.bss` each,
  ui.md). Every `.bss` word between them would flip parity, so they need a
  partner.
- **`desk.inc`'s two `cw_` shims** (-1 each): BP is live in `wm_paint_dmg`.
- **`mem_free(0)` as its own refusal on common paths** (-4 each):
  `menu_drop` runs on every menu close on 128KB; `clip_drop`'s CF is
  `clip_put`'s answer.
- **`clo_need`, `dskw_fmt_load` and `fm_fmt_drop`**: three copies of one
  8-byte `mod_need`/`mod_drop` shape. Pass 18 priced and refused a shared
  helper.
- **The cfix proof's other false hit, at 0x0872** (CTRL.DRV/DISKOPS.DRV).
  It is a real far call whose offset's high byte is 9Ah, and the layout
  decides whether it is reached. It is the same class of trap as 0x0855, so
  whoever next sees `coldhma.sys` refuse should look here first.
- **Latent, not fixed:**
  - **kern_mega's `dskw_wck` quiet mount** reloads only the low word of
    `[dsk_cwd]`, so it would come back in the wrong folder on FAT32. FAT32 is
    never removable, so as far as anyone can see it cannot happen. The fix
    is `CLU_LD dsk_cwd`, +6 on kern_mega (diskw.md).
  - **kern_small's `db_paint` zap** uses an unsigned compare against a
    signed span (ui.md). kern_big refuses a negative x1 before storing it;
    kern_small does not, and it is not proved unreachable there.
- **Rows that are missing** (diskw.md): no row runs kern_small's Rename.
  `fcpsmall` covers its New Folder and recursive delete, and `diskmut` is
  kern_big only.
- **Knob builds that fail at the base, and are not this pass's:**
  - kern_small with `SNAPAUDIT=1` trips guard 1b, the heap lock (wm.md).
  - kern_small with `DISK_COUNTERS` also hits the heap lock (files.md).
  - `fatwpin`'s `FATWNONE=1` kernel never reaches a desktop (pass 20).

## 6. What was run (the final pass, once)

Every agent ran on the host only (`make`, which runs the fast tier;
`make small`, `make emu`, `make mega`; `kernsize`; `stkbalance`; `hotpar`;
and unicorn A/B harnesses against the base's own bytes, in draw, input, disk
and sweep). None ran a row. The coordinator gated every merge with `make`,
and with `make emu mega` after the last three.

- **The deduplicated union of every note's named rows, once**
  (`tools/os88soak.py`, run `20261127-050324`, 387 soak rows, 55 minutes on
  4 lanes). Bochs, the C toolchain, the automation-enabled 86Box, QEMU 9 and
  the wire disk were installed for it. **373 ok, 12 FAIL, 2 SKIP**
  (`win16file`, `win16mdi`: the Win16 fixtures are not in this container).
  All twelve failures are accounted for:
  * **Eight are the harness, and fail at the base:** `hmacold`, `hmahiber`,
    `hdhiber`, `p2hiber`, `hmadrv`, `cpwide`, `mixersb16` and `mixervesa`.
    Since `4e2b007`, os88ui's menu reads wait in guest time on every
    emulator, and QEMU's `Q` has no `status`, so every QEMU row that picks a
    menu died on AttributeError. `os88marty._Progress` now counts host time
    on a machine with no guest clock (`3bfd00454`).
  * **Two were source readers this pass's moves outgrew:**
    - `assocpage` looked for `assoc_compose:`, which the sweep wrote in at
      its one call. It now reads `dsk_docpass`'s `ASSOC_COMPOSE` marker.
    - `kbdlayoutfont` sliced `font_char`'s index arithmetic from its old
      shape. It now starts at `.rows:`.

    Both are green now, and each went red against a planted break: one
    run count changed, and `font_base` read wrong.
  * **One was a registration gap in the base:** `megarehome` loads
    `build/scribe.o88`. That package is in `all` and on no shipped disk, so
    the snapshot never built it. It is now in the row's `wants`.
  * **One passed when re-run alone:** `modcache`. Its `modkeep` VGA leg's
    first launch of CALC.O88 from B: refused with `LD_EBAD` in the run.
    - **What the failing run looked like:** `CALC.O88` is fragmented on that
      disk (cluster 22, then 73-75), the box was carrying 4 lanes, and the
      soak's boot cache was live.
    - **It did not come back:** the leg booted alone on base and tip, the
      same on the snapshot's own build, and `modcache` re-run twice at the
      tip all opened the Calculator. MartyPC's guest is deterministic; where
      an injected click lands in guest time is not.
    - **Status:** recorded as an UNEXPLAINED ONE-OFF, not as a pass. `LD_EBAD`
      also comes out of the association path (ASSOC-FIND-PLAN), so a press
      that lands while B:'s listing is still being classified is the first
      thing to look at if it is seen again.
- **The twelve, re-run once at the tip with the fixes: 12 ok.**
- **`test-full`, once: 79 ok, 2 FAIL, 1 SKIP** (`pd360`, which needs
  PageDesk):
  * `cswrite`: `kmain`'s `push cs / pop ds / push cs / pop es` (hw item 2)
    was not registered. It runs in real mode on every kernel, and kern_mega
    switches only at `kmain`'s foot. Registered in `tests/cswrites.txt` with
    that reason; green.
  * `hostwait`: `tests/cpface.py`, `tests/ethcfg.py` and `tests/rdcz.py`
    each carry a host `poll` wait over their allowance. They are
    **identical at the base**, `t_hostwait` run in a worktree of
    `3fc4e9d09`. No file this pass touched; open for whoever owns those
    rows.
- **`make budget-check`, at the tip, with no grace:** kern_big 94,720 of
  100,864 (6,144 spare), kern_small 56,832 of 64,000 (7,168), kern_emu
  94,720 of 100,864 (6,144), kern_mega 61,440 of 68,096 (6,656).
  `os88megaseg` reads 3,787 against an allowance set to exactly that.
- The `kernsize` baseline in docs/KERNEL-MEMORY.md was blessed at the tip on
  all four kernels.
- **Not run:** a MartyPC before/after timing pass (`os88hot ab`). Every
  hot-path item carries its count in its note, and the A/B is the owner's
  call.

## 7. Method lessons

* **Ten agents by FILE, and smaller areas than pass 20's five, worked.**
  Each found 60 to 160 bytes in a few thousand bytes of source that several
  passes had already read. The single-file owners (files, wm) went deepest,
  and the bundles (hw, input) found the most kern_small bytes per file. The
  only merge conflicts were generated files: `docs/INDEX.md` every time, and
  `tests/megaseg.txt` three times.
* **A shared allowance file conflicts, and the sum of its branches is
  wrong.** Three agents each raised `tests/megaseg.txt` from the same base
  (+6, +3, +6). The merged tree read +15 by text and **+9 by the gate**.
  The coordinator sets such a figure from the gate's own reading after the
  merge, not by adding the branches' deltas.
* **Pre-seeding each worktree's `build/` saved the first build.** The
  coordinator copied a complete build (without MartyPC's 700MB), then set
  every tracked file in the worktree to an older mtime. Each worktree's
  first `make` then took 16 seconds instead of minutes, and assembled
  nothing.
* **`tools/os88index.py` counts TRACKED files only.** `git add` the new note
  before regenerating, or `make` fails `docindex` on the next build.
* **A layout-dependent build failure travels between branches.** The 0x0855
  trap fired on three agents' branches as their savings walked `COLD_HOME`
  past it. None of them owned `winmod.inc`, so each stepped round it and
  wrote it down. The sweep fixed it at the source and proved the range
  clean. One agent saying "a value my branch passed through fails" is a
  defect report, not a curiosity.
* **The cross-file sweep paid for itself:** -58 on kern_big from leads that
  no single owner could take. Run it after every by-file pass, on the merged
  tree, with every note's CROSS-FILE section as its brief.
* **Defects keep turning up by reading.** This pass found three (section 3)
  and one for the owner (section 4) by reading code for bytes. None of them
  was reachable by an existing row.
