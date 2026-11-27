# Kernel size pass 21: the brief every agent reads first

Branch `claude/kernel-size-pass-529zgd`, cut from `elendilon` at `dbc5ef8b4`
on 2026-11-27. The pass before this one was **pass 20** (merged into the old
integration branch at `d112a6eef`, tip `c0eedd5f4`, both on
`origin/elendilon-old`; squashed home in #365). Its record is
`docs/plans/completed/HANDOFF-KERNEL-SIZE-P21.md` (named for the pass it
hands to), and its brief and agent notes are `docs/plans/completed/ksp20/`.
**`c0eedd5f4` is the last sized tree.** Everything after it is unsized.

Each agent works in its own git worktree, created by the coordinator at
`/home/user/wt/<name>` on a branch `ksp21-<name>` cut from the commit that
adds this file. Each writes its record to `docs/plans/completed/ksp21/<name>.md`. The
coordinator merges the branches. **Agents do not push.**

Read these before writing any code, in this order:

1. this file;
2. **`docs/plans/completed/ksp14/BRIEF.md` sections 2, 3 and 4**: the
   method, the environment and the note's shape. They carry over UNCHANGED
   except where this file says otherwise. Substitute `ksp21` for `ksp14`,
   `docs/plans/completed/ksp21/` for its note directory, and `(kernel size pass 21)`
   for the commit suffix everywhere. Its section 1 (rules) is replaced by
   section 1 below. **Its permission to run your own rows once is
   WITHDRAWN** (section 3 below);
3. **`docs/plans/completed/HANDOFF-KERNEL-SIZE-P21.md` in full**: pass 20's
   record, especially section 4 (WANTS THE OWNER, which is not taken), 5
   (what is left) and 7 (method lessons);
4. **`docs/plans/completed/ksp18/BRIEF.md` section 1, THE SPEED RULE**. It
   applies word for word, with "khp1" read as also covering every speed
   commit since `c0eedd5f4`;
5. **the REFUSED, DECLINED and WANTS THE OWNER lists in
   `docs/plans/completed/ksp20/*.md`, `ksp19/*.md` and `ksp18/*.md`** for
   any file you touch. A refused item is not re-proposed unless its reason
   no longer holds, and then the note says what changed;
6. `docs/plans/KERNEL-BYTE-QUEUE.md` and `docs/plans/LAST-DROP-BYTES.md`
   (§7 especially) for any item in your files;
7. CLAUDE.md's Hard rules and its banner: **bytes, not rungs**.

## 0. The brief

The owner's words: *"Its time for the next kernel size pass. Big is now in a
more stable shape, and we just had to put a few operations back into it; the
goal is to find ~350b to offset them. The kernel has been size passed many
times; you can dig deep, and start many agents to cover even smaller areas
of the kernel. This pass cannot be ABI breaking; that was the last one. More
than 350b is not refused; you don't have to stop there if agents have more
leads."*

"The few operations put back" are Rename, New Folder and empty-folder
removal, resident again on kern_big, kern_emu and kern_mega (`7f08a100b`,
+282 `.cold`; SPEC.md 18.5.3). **They stay resident**: the owner's rule is
that a module is for the File Manager's UI-sized jobs, not for a few bytes
of a file operation any package calls. Moving a package-callable operation
into a module is refused this pass.

**The goal, in resident bytes** (`.text` + `.bss` + `.cold` + `.lowbss` +
`.vgabuf` + `.vga`, from `tools/kernsize.py --json`):

* **kern_big: about -350 against the base**, and more is welcome. There
  are ten agents, so that is about 35 bytes each. Do not stop at your share
  if you have more leads.
* kern_small, kern_emu and kern_mega are reported. **None of the four may
  grow.** kern_small's 128KB heap is LOCKED (guard 1b), so a kern_small
  saving is welcome, and it is the same price as any other byte. Say each
  item's kern_small figure even when it is 0.

### 0.1 The base, assembled (`dbc5ef8b4` + this file)

| kernel | `.text` | `.bss` | `.cold` | `.lowbss` | `.vgabuf` | `.vga` | `.mega` | **resident** | `KERN_SIZE` | accrued |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **kern_big** | 39,510 | 4,973 | 37,830 | 5,358 | 336 | 2,218 | - | **90,225** | 95,744 | 113/512 |
| kern_small | 29,101 | 2,843 | 20,860 | 2,868 | 0 | 0 | - | **55,672** | 57,344 | 376/512 |
| kern_emu | 39,756 | 4,973 | 37,830 | 5,358 | 336 | 2,218 | - | **90,471** | 95,744 | 359/512 |
| kern_mega | 45,275 | 5,204 | 53,078 | 5,600 | 336 | - | 24,800 | **134,293** | conventional 61,952 of 68,096 | - |

Measure your own base in your worktree anyway (ksp14 section 2). Every
commit moves the build number's three bytes of `.text` (SPEC.md 14.2) but
no section's SIZE, so sizes compare across commits and `md5sum` does not.

### 0.2 What has not had a pass

`tools/os88rdiff.py kernel c0eedd5f4 dbc5ef8b4` on kern_big reads
`.text` +305, `.bss` +95, `.cold` +153: **about +550 resident bytes no size
pass has read**, in 147 changed and 396 new routines (most of the new ones
are module images). These are the largest resident items:

| routine | section | delta | from |
|---|---|---:|---|
| `kl_control_x` | `.cold` | +161 new | keyboard layouts (#396, SPEC.md 9.16) |
| `dskw_wck` | `.cold` | +78 new | the swapped-floppy check on directory writes (`7f08a100b`) |
| `dskw_dircall` | `.cold` | +67 new | the same |
| `kbm_isr` | `.text` | +63 (182) | keyboard layouts |
| `app_about_paint_x` | `.cold` | +52 (108) | the About box |
| `osapi_key_map`, `osapi_keyboard` | `.text` | +32, +30 new | keyboard layouts |
| `fcp_step`, `fcp_stop` | `.cold` | +29, +11 | Copy/Paste |
| `dsk_xfer` | `.cold` | +28 (1,026) | READ_SEQ (#387) and the write re-check |
| `osapi_font_glyphs`, `apic_font_run` | `.text` | +26, +20 new | font |
| `osapi_mouse_rel` | `.text` | +22 new | the Olivetti PC1 mouse (#371) |
| `pc1_row`, `drv_f_pc1` | `.text` | +16, +13 new | the same |
| `dwf_dskw_read_seq` | `.cold` | +14 | READ_SEQ |
| `kl_release_inst`, `kl_drop_x`, `mod_f_keyboard`, `mod_r_keyboard`, `mod_f_cpw` | `.text`/`.cold` | +14, +8, +13, +12, +11 new | keyboard and the wide Control Panel |
| `desk_zones_paint_x` | `.cold` | +13 | desk |
| `ld_run_body_x` | `.cold` | +11 | loader |
| `mem_cp_walk` | `.cold` | +6 (166) | `dbc5ef8b4`, the newest commit |

Regenerate the whole list yourself with `tools/os88rdiff.py kernel
c0eedd5f4 HEAD`, adding `-D KERN_SMALL` for kern_small. **Start with the
unsized routines in your files, then sweep everything else you own.** In
passes 16 to 20 the largest share of every finder's bytes came from three
shapes: single-caller routines written in at the call, callee-saves that no
caller reads, and shared tails.

## 1. The rules this pass

* **No kernel grows, and no item is taken unless it is net smaller**:
  resident bytes on every kernel it reaches, and the packages' total too.
  Small package growth that buys resident kernel bytes is fine; say the
  total.
* **THE ABI IS FROZEN.** This is the difference from passes 19 and 20.
  `tools/abi.lock.json` does not change. Neither do `apps/os88api.inc`,
  `drivers/os88drv.inc`, the C SDK (`apps/cc/`), any `OSAPI_*` slot's
  register contract, any record or structure layout a package or driver
  reads (§20), or the dispatcher and header conventions. A saving that
  needs any of those is **WANTS AN ABI BREAK**: write it in the note with
  its bytes, and do not build it. Pass 19's two (`OSAPI_BATCH_END`
  withdrawn, `W_DISP`'s offset dropped) stay there. A kernel-INTERNAL
  contract (a routine's registers, a `.bss` layout nothing outside the
  kernel reads) may change, and SPEC.md moves with it in the same commit.
  The `X`-stub and module slot tables are internal, but a module image
  built before still has to load, so do not reorder a published module
  entry.
* **Functionality**: byte-identical behaviour is the bar, refusal paths
  included. A message reworded or dropped, a feature that needs the system
  disk where it did not, or a limit lowered is WANTS THE OWNER, with its
  bytes. **A package-callable file operation does not move into a module**
  (section 0).
* **Speed**: `docs/plans/completed/ksp18/BRIEF.md` section 1, word for
  word. **No change adds an `int 13h` call to any operation.** Anything on
  the mount, listing, read-ahead, FAT-window, directory-write or loader path
  names its scenario and its call count before and after. `hotpar` is a
  gate: pad back and say so.
* **kern_mega must still build** (`make mega`) and may not grow. A shared
  change says what it did to kern_mega's conventional sections and `.mega`.
  The kern_mega-only files (`mega*.inc`) are not targets.
* **Modules are not resident.** A byte moved from `.text`/`.cold` into a
  module that QUALIFIES (CLAUDE.md, *ON-DEMAND MODULE*: the feature already
  needs the system disk) is a resident byte saved. A module image's own
  growth is disk bytes, and you report it separately. A move that makes a
  feature need the system disk where it did not is WANTS THE OWNER.
* **`.cold` IS RESIDENT.** Moving code from `.text` to `.cold` relieves
  `KERN_CODE_MAX` and nothing else, so it is not a saving. A `.cold`
  routine made smaller is a saving.
* **Do not bless** `tools/kernsize.py`'s baseline in docs/KERNEL-MEMORY.md.
  The coordinator blesses it once, at the close.

## 2. The ten agents and what each owns

**Ownership is by FILE.** A file in no row is free to whoever reaches it
first: say so in your note's TAKEN line. Anything you see in another
agent's file goes in your note's *CROSS-FILE* with its bytes, and you do
not edit it. The areas are smaller than pass 20's five on purpose, so read
EVERY routine in your files: the hot ones for shared tails and setup, the
cold ones for everything.

| agent | owns | start with |
|---|---|---|
| **files** | `files.inc`, `dskwin.inc` | `files.inc` is 8.9KB of kern_big (7.7KB `.cold`) and 527 bytes of `.bss`, the largest file in the kernel. Pass 20's files.md is the last reading |
| **wm** | `wm.inc`, `winmod.inc`, `extmod.inc`, `deskmod.inc`, `spinner.inc`, and the kernel's use of `apps/os88ui.inc` (shared with packages: a change there rebuilds every package that includes it, and the packages' total counts) | `wm_paint_dmg` (+6), `wm_paint_all` (+2). PERFORMANCE.md Part 5's budget is the bar for any repaint path. `wm.inc` is 8.4KB of `.text` and 856 of `.bss` |
| **disk** | `disk.inc`, `drvvol.inc`, `lz.inc`, `lzfilt.inc`, `fsck.inc`, `clu.inc` | `dsk_xfer` (+28, 1,026 bytes), READ_SEQ (#387: `dwf_dskw_read_seq` +14), `disk_mount_x`, the read-ahead. The int 13h counts are the bar |
| **diskw** | `diskw.inc`, `diskmut.inc`, `diskops.inc`, `loader.inc`, `compress.inc`, `ascw.inc` | `dskw_wck` (+78) and `dskw_dircall` (+67), both new and unsized, then the three bodies `7f08a100b` brought back (rename, mkdir, empty rmdir): **make them SMALLER, keep them resident**. Then `ld_run_body_x` (+11) and the loader |
| **draw** | `vga12.inc`, `softgfx.inc`, `icons.inc`, `band.inc`, `blank.inc`, `splash.inc` | the `.vga` rung's setup and slow paths, at their speed (the `KHP_VGA*` bodies are H1/H2: shared tails and setup only, or cycle-neutral with the count shown). `gfx_pt_miss` (+1). Then the kern_small-resident parts |
| **input** | `mouse.inc`, `mouproto.inc`, `vmmouse.inc`, `vmmabi.inc`, `keyboard.inc`, `keymaps.inc`, `keyfont.inc`, `keyfont-data.inc`, `serial.inc`, `font.inc` | **the keyboard layouts (#396), which are unsized**: `kl_control_x` (+161), `osapi_keyboard`, `kl_release_inst`, `kl_drop_x` (`keyboard.inc`), `kbm_isr` (+63, an ISR, so hot) and `osapi_key_map` (`mouse.inc`). Then the PC1 mouse's `osapi_mouse_rel` and `mou_apply` (+8), and the font (`font_ch_hi` +8, `font_run_cell` +3; `font_run_x` is H1) |
| **ui** | `ui.inc`, `menu.inc`, `fprog.inc`, `dock.inc`, `dockmod.inc`, `toast.inc` | `[menu_ent]` (-6, pass 20's REFUSED 1: move `uilat`/`weavelat`/`a2uilat`'s stop to `menu_cnt`), `ui_task`'s `jmp .yield` short (a `hotpar` routine), then a general sweep. `ui.inc`+`menu.inc` are 5.1KB of `.text` |
| **desk** | `desk.inc`, `desksc.inc`, `stikmenu.inc`, `assoc.inc`, `fdlg.inc`, `filecp.inc` | `fcp_step` (+29), `fcp_stop` (+11), `desk_zones_paint_x` (+13), `desk_cmark` (+4), then `assoc.inc` (2.5KB) and `fdlg.inc` (2.1KB) |
| **sys** | `memory.inc`, `instance.inc`, `sched.inc`, `mod.inc`, `events.inc`, `clip.inc`, `apps.inc`, `shutdown.inc`, `hiber.inc`, `hbstub.inc`, `hbstage.inc`, `hbmark.inc` | `app_about_paint_x` (+52) and `app_about_vx*` (`apps.inc`), `mem_cp_walk` (+6, the newest commit: read its message), `mod_need` (+5), `mod_f_keyboard`/`mod_r_keyboard`/`mod_f_cpw` (new, `mod.inc`), `inst_rel_rec` (+3). `sch_isr`/`sch_switch` are hot |
| **hw** | `kernel.asm` (the API table, the door, `kmain`, the `cw_` shims, `rmk_*`), `driver.inc`, `fsx.inc`, `snd.inc`, `clock.inc`, `clockw.inc`, `xmem.inc`, `xmabi.inc`, `cpudet.inc`, `viddet.inc`, `vidsel.inc`, `vidext.inc`, `vxabi.inc`, `ctrl.inc`, `cpwide.inc` and the `cpw*.inc` family, `boot3.inc`, `boot/` | the unsized items in `kernel.asm`: `osapi_font_glyphs` (+26), `apic_font_run` (+20 new), `rmk_11e`/`rmk_11`/`rmk_seg` (new), `api_refusec` (new), `mod_fpt` (+4); the PC1 mouse's `pc1_row` and `drv_f_pc1` (`driver.inc`); `cp_tickp` (`ctrl.inc`). Then the `cw_` shim census (KERNEL-BYTE-QUEUE.md item 1: the ~26 sites whose routine never mentions BP) and `drv_notice`'s far frame for `cp_open_x` (pass 20's "what is left": -3 `.cold`). The door is hot |

## 3. The environment

* **Ten agents at once, on 4 cores and 15GB.** Iterate with `python3
  tools/kernsize.py --json` (it assembles the kernel itself in about five
  seconds) and `tools/os88rdiff.py`. Run a full `make -j2` only to gate a
  commit, never two builds in your own tree at once, and expect them to be
  slow while nine others share the box.
* **Your worktree's `build/` is pre-seeded**: the coordinator copied a
  complete build in, so your first `make` rebuilds only what the build
  number and your edits reach. If `make` starts rebuilding every package,
  stop and say so rather than fighting it.
* **Agents run NO rows.** No soak row, no `test-full`, no row script by
  hand, no scratch MartyPC script that measures what a row measures
  (CLAUDE.md's Testing section: this pass is batches, and the coordinator
  runs the deduplicated union once after the last merge). You verify on the
  host: `make` (which runs the fast tier), `make -j2 small`, `make -j2 emu`,
  `make -j2 mega`, `kernsize`, `tools/stkbalance.py`, `hotpar`, a unicorn
  harness, or a careful reading recorded in the note. And you NAME the
  `tests/suite.py` rows that cover each change, so the coordinator's union
  is complete. A number that DECIDES a design (an int 13h count, a cycle
  count on a hot path) is taken once by you and written in your note.
  **One boot to LOOK at a change is allowed**, with at most one MartyPC
  instance of your own; MartyPC is built in the main tree, so in your
  worktree run `ln -sfn /home/user/os8088/build/martypc build/martypc`
  first.
* Your kern_small figures: `python3 tools/kernsize.py --json --build
  build/smallk --ico build/smallk -DKERN_SMALL`. kern_emu: `--build
  build/emuk --ico build/emuk -DKERN_BIG -DKERN_EMU`. kern_mega: `--build
  build/megak --ico build/megak -DKERN_BIG -DKERN_MEGA`. `make small`,
  `make emu` and `make mega` refresh those trees.
* **Remove nothing outside your worktree. Never `git stash`**: it is one
  stack for every worktree. Your scratch directory is
  `<scratchpad>/ksp21-<name>/` and nobody else's.
* `docs/INDEX.md` is generated, and it counts TRACKED files only. So
  `git add` your note FIRST, then run `python3 tools/os88index.py`, then add
  and commit both. The coordinator regenerates it after every merge.
* `apps/wireball/art/wbfront.inc`: if it shows as modified, `git checkout`
  it before you commit, and never commit it.

## 4. The note and the report

The note is ksp14 section 4's shape: BASE AND TIP (all four kernels),
TAKEN (each item with its bytes per kernel, and its cycles if it is on a hot
path), REFUSED (with the bytes and the reason), WANTS THE OWNER, WANTS AN
ABI BREAK, CROSS-FILE, ROWS (named, not run), and DEFECTS FOUND.

**Your final message to the coordinator is ONE message**: the branch tip,
the resident delta on each kernel, the WANTS THE OWNER and WANTS AN ABI
BREAK items, the rows the coordinator must run, and anything that blocked
you.
