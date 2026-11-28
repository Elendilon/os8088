# Kernel bytes since the #365 squash, by concept — the elendilon-pr round of 2026-11-28

**A measurement, not a description.** Taken 2026-11-28 on a four-core cloud
container: `nasm` 2.16.01, Python 3.13. Every figure comes from
`tools/kernsize.py --json --strict`, which RE-ASSEMBLES the kernel rather
than reading a build. Every point named below was measured in a clean tree
of its own:

- `git archive` of that commit's `kernel/`, `boot/`, `apps/`, `drivers/`,
  `tools/` and `fonts/`.
- That commit's `apps/stiklib.asm`, assembled into the `stiklib.bin` that
  `deskmod.inc` includes.
- That commit's `tools/cpwdat.py`, building the `cpwdat.bin` the wide
  Control Panel includes (SPEC.md 135).
- That commit's own `kernsize`, measuring **`kern_big`, `kern_small`,
  `kern_emu` and `kern_mega`**.

`associco.inc`, `buildnum.inc` and `ksig.inc` are held at B's in every tree,
each kernel's own. The build number is the commit count (SPEC.md 14.2), so a
figure here never moves because a commit was counted.

The method was checked against the last report: at `b5897f25` it gives
`kern_big` **89,738**, which is that report's figure exactly. `kern_small`
and `kern_mega` come out 1 and 2 bytes under it, the difference being the
held generated includes. B's clean-tree figures equal `kernsize` on B's real
`make`, `make small`, `make emu` and `make mega` builds.

**Coverage.**
- 176 points: every commit since the squash that changes a kernel input,
  plus its first parent.
- Kernel inputs are: `kernel/`, `boot/`, `apps/stiklib.asm`, the seven SDK
  `.inc` files the kernel or `stiklib` include, `drivers/thmpal/`,
  `tools/cpwdat.py` and `drivers/catalog.toml`.
- The point list was then widened to the eleven area merges of kernel size
  pass 21 and to the extended-desktop audit's branch.
- Along every first-parent line below, the per-commit charges sum to the
  line's end minus its start, **in every section, on all four kernels**. The
  script checks that; it is not assumed.
- Four intermediate commits inside pass 21's area branches do not assemble.
  They are not on any line measured here, and every merge that carries them
  does assemble.

It is the twenty-first of its family, after
`docs/reports/KERNEL-BYTES-SINCE-SQUASH-2026-11-16.md`, and is an edit of
none of them.

## The points

| | commit | what it is |
|---|---|---|
| **S** | `50968828` | **the #365 squash**: `main` at *Elendilon -> Main (Wire Arena, ...)*, the last time this fork's work landed |
| **A** | `f2318e0f` | **`main`** today: #408, *The Wire: run a big-file archive from an XMS RAM disk*. 36 commits after S, six of which move a kernel byte (below) |
| **B** | `c81277c7` | **`elendilon-pr`** at this report: `elendilon` (`211921ae`) cut from `main` at A and squashed onto it (`f7a9719f`), then lived in for one round, plus this branch's soak fixes. None of those fixes moves a kernel byte |

The PR is **A..B**. S..A is `main`'s own work and is here so that "what
the PR saves" is read against today's `main` and not the last squash.

## Headline

**Against `main`, the PR saves 664 resident bytes on `kern_big`, 827 on
`kern_small`, 670 on `kern_emu` and 662 on `kern_mega`. `KERN_SIZE` drops a
rung on every kernel, and `kern_mega`'s `MEGA_RESIDENT` drops one.**

Kernel size pass 21 is −1,127 / −835 / −1,133 / −1,155 of that. Everything
else in the round together is +463 / +8 / +463 / +493.

| | `kern_big` | `kern_small` | `kern_emu` | `kern_mega` |
|---|---:|---:|---:|---:|
| **S** the #365 squash, resident | 89,783 | 55,795 | 90,029 | 104,355 |
| **A** `main`, resident | 89,850 | 55,672 | 90,096 | 109,096 |
| **B** this PR, resident | **89,186** | **54,845** | **89,426** | **108,434** |
| **A − S, `main` since #365** | +67 | −123 | +67 | +4,741 |
| **B − A, this PR** | **−664** | **−827** | **−670** | **−662** |
| ...of which kernel size pass 21 | −1,127 | −835 | −1,133 | −1,155 |
| ...of which everything else | +463 | +8 | +463 | +493 |
| `KERN_SIZE` S / A / B | 95,232 / 95,232 / **94,720** | 57,344 / 57,344 / **56,832** | 95,232 / 95,232 / **94,720** | 136,704 / 141,312 / **140,800** |
| `MEGA_RESIDENT` S / A / B | | | | 61,440 / 61,952 / **61,440** |
| spare of the budget at B | 6,144 | 7,168 | 6,144 | 6,656 (61,440 of 68,096) |

"Resident" is `.text` + `.bss` + `.cold` + `.vga` + `.lowbss` + `.vgabuf`,
the same sum as the last report. On `kern_mega` that sum includes `.cold`,
which rides above 1MB once the kernel has switched. Its conventional-memory
figure is `MEGA_RESIDENT`, the line the budget binds.

`make budget-check` passes on all four kernels at B with no branch grace:
- kern_big and kern_emu: 94,720 of 100,864.
- kern_small: 56,832 of 64,000.
- kern_mega: 61,440 of 68,096.

## `main` since #365 (S..A), for reference

None of this is the PR's. It is the base the PR is measured against.

| commit | what it is | `kern_big` | `kern_small` | `kern_emu` | `kern_mega` |
|---|---|---:|---:|---:|---:|
| `d4349a0a` (#371) | Olivetti PC1 mouse: native driver, button scans | +67 (`.text`) | 0 | +67, **`KERN_SIZE` +512** | +69 |
| `46b87ef5` (#387) | READ_SEQ reads a run only from a cursor that has one | +14 (`.cold`) | 0 | +14 | +14 |
| `d546b6c3` (#394) | **FAT32 on kern_mega** (SPEC.md 19.12) | +8 | 0 | +8 | **+4,722** (`.cold` +4,401 above 1MB, `.text` +128, `.bss` +193): **`MEGA_RESIDENT` 61,440 -> 61,952**, `KERN_SIZE` +5,120 |
| `1f0a70e6` (#396) | Spanish and French keyboard layouts: the directory mutation bodies to DISKOPS.DRV | −135 | −137 | −135, `KERN_SIZE` −512 | −177 |
| `6f69783d` (#399) | VESA desktop: icons anywhere on the grid, Theme Color | +101 | +14 | +101 | +101 |
| `8d647b34` (#402) | Wide Control Panel for VGA and VESA (SPEC.md 135) | +12 | 0 | +12 | +12 |
| **A − S** | | **+67** | **−123** | **+67** | **+4,741** |

## This PR (A..B), by concept

| concept | commit(s) | **`kern_big`** | **`kern_small`** | **`kern_emu`** | **`kern_mega`** |
|---|---|---:|---:|---:|---:|
| **Floppy writes re-check the disk first** (SPEC.md 18.9.1.3) | `ce949a88`, in the squash `f7a9719f` | **+81** (`.cold` +80, `.bss` +1) | 0 | **+81** | **+81** (`.cold`, above 1MB) |
| ...the squash's merge with `main` | `f7a9719f` | −1 | 0 | −1 (the squash crosses `KERN_SIZE` +512) | −1 |
| **The PS/2 probe's late answer** (SPEC.md 9.9.1.1, field note 69) | `fb774df9`, in the squash | 0 | 0 | 0 | 0 (`.ovl` +48, the boot overlay) |
| ...the re-check skipped inside a `dsk_batch` (SPEC.md 18.9.3) | `349168a5` | +7 | 0 | +7 | +8 |
| **Rename, mkdir, empty rmdir resident again** (SPEC.md 18.5.3; #396 had moved them to DISKOPS.DRV, so a full-screen DOS program could not rename on its second run) | `7f08a100` | **+282** (`.cold`), `KERN_SIZE` +512 | 0 (its heap rung is locked) | +282 | **+306** |
| `mem_cp_walk`: a descending pass dissolves the cheap cache its plan counted | `dbc5ef8b` | +6 | 0 | +6 | +3 |
| **Kernel size pass 21** (`docs/plans/completed/HANDOFF-KERNEL-SIZE-P22.md`) | `aa6b428c` | **−1,127** | **−835** | **−1,133** | **−1,155** |
| **The extended-desktop audit** (SPEC.md 39.16, 39.14.7) | `211921ae` | **+88** | **+8** | **+88** | **+96** |
| this branch's soak fixes (`UI_ISMONO`, the Wire's level 9, `keymap`) | `2dbbf95f`..`c81277c7` | 0 | 0 | 0 | 0 |
| **B − A, the PR** | | **−664** | **−827** | **−670** | **−662** |

### Kernel size pass 21, by area

Ten agents worked by file, then one ran a cross-file sweep. Each area landed
as one merge, measured against the previous one:

| area | merge | `kern_big` | `kern_small` | `kern_emu` | `kern_mega` |
|---|---|---:|---:|---:|---:|
| volumes, mount, the FAT read path, LZ | `0d84b497` | −129 | −81 | −129 | −132 |
| keyboard layouts, the keyboard ISR, mouse, font | `71c81608` | −88 | −58 | −92 | −91 |
| drawing primitives, icons | `55f4508e` | −89 | −94 | −89 | −86 (`MEGA_RESIDENT` 61,952 -> **61,440**) |
| `kernel.asm`, drivers, FSX, sound, clock, video | `b6cab224` | −62 | −88 | −62 | −50 |
| the window manager and os88ui's kernel arm | `29b9d964` | −92 | −98 | −92 | −92 |
| UI task, menus, toasts, progress, dock | `b8ed47dd` | −112 | −104 | −112 | −112 |
| the Disk window | `a84c91a9` | −127 | −104 | −127 | −127 |
| copy engine, associations, desk zones | `0c3891e9` | −105 | −30 | −105 | −106 |
| heap, instances, scheduler, About | `62adf977` | −107 | −59 | −107 | −104 |
| the FAT write path and the loader | `f0e02998` | −158 | −78 | −158 | −187 |
| the cross-file sweep (the FIND flags defect, the COLD_HOME 0x0855 trap) | `c8595b55` | −58 | −41 | −60 | −68 |
| **the pass** | | **−1,127** | **−835** | **−1,133** | **−1,155** |

The ABI is untouched and no `int 13h` call was added or removed. Two defects
were fixed by reading: `assoc_sweep`'s DI, and the FIND flags on a
redirected volume.

### The extended-desktop audit, by fix

| fix | commit | `kern_big` | `kern_small` | `kern_emu` | `kern_mega` |
|---|---|---:|---:|---:|---:|
| Snap: display 1's left edge snaps like x = 0 (K4, K5) | `1a2eb39a` | +16 | 0 | +16 | +16 |
| Zoom: a straddling window zooms onto the display it is mostly on | `900ea513` | +16 | −2 | +16 | +16 |
| **`OSAPI_WM_DORIGIN`** (SPEC.md 39.16.4.3): the origin of the display a window is on - a cell appended at 0x0244 | `9de7632c` | +24 | +8 | +24 | +28 |
| `gfx_scroll` preserves ES, as SPEC.md 5.5 says | `13f26df0` | +2 | +2 | +2 | +2 |
| Fullscreen from a straddle repaints the other card (K7) | `ba274c42` | +6 | 0 | +6 | +6 |
| `gfx_blit1` cuts a band at a row seam instead of dropping it (39.14.7.3) | `f8da7390` | +10 | 0 | +10 | +10 |
| `gfx_scroll` cuts a straddling rect at a column seam (39.14.7.4) | `f8d2ead9` | +14 | 0 | +14 | +14 |
| kern_mega: the pointer moves through a BIOS disk call on an extended desktop (D1) | `4c7fbda0` | 0 | 0 | 0 | +4 (`.mega` +48) |
| the branch's merge of `elendilon` (`.boot2` −6 everywhere, nothing resident) | `12677d2d` | 0 | 0 | 0 | 0 |
| **the audit** | | **+88** | **+8** | **+88** | **+96** |

## Where it lands

- **KERN_SIZE moved on four commits.** On `kern_big`, `7f08a100` crossed
  95,232 -> 95,744, and pass 21's window-manager merge took it back down to
  94,720. On `kern_emu`, the floppy write re-check's +80 in the squash
  crossed 95,232 -> 95,744, and pass 21's input merge took it down again. On `kern_small`, pass 21's window-manager merge crossed downward.
  On `kern_mega`, `MEGA_RESIDENT` came down at pass 21's drawing merge.
- **`kern_small` is a rung lower**: `KERN_SIZE` 56,832, 7,168 under its
  budget, all of it pass 21's 835 bytes. Nothing else in the round moved
  `kern_small` but the audit's +8.
- **`main`'s FAT32 on kern_mega** (+4,722, almost all `.cold` above 1MB) is
  the reason kern_mega's six-section sum is larger at B than at S. The PR
  takes 662 of it back.
- **The one new API cell, `OSAPI_WM_DORIGIN`**, cuts the Wire's level-9
  cell-fence row (SPEC.md 92.2, `e60bd0a7`). `main`'s v1.0.20261120
  released the table ending at 0x0244, so a package calling the new cell
  must not be offered to a level-8 machine.
