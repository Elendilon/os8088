# Kernel bytes since the last squash with `main`, by concept, with `main`'s arm separated

**A measurement, not a description.** Taken 2026-09-17 on a four-core cloud
container from a cold checkout — `nasm` 2.16.01, QEMU 8.2.2, MartyPC built at
the pinned commit. Every figure comes from `tools/kernsize.py --json` and its
`--bless` module table, which RE-ASSEMBLE the kernel rather than reading a
build, so each point is measured on its own tree with its own tools and no
figure is carried between them. It is true of the five commits it names and of
no other tree; a later measurement is a new file.

It is the THIRD of its family and the family has two names.
`docs/reports/KERNEL-BYTES-SINCE-SQUASH-2026-09-07.md` is the first and
`docs/reports/PR-CYCLE-ACCOUNTING-2026-09-11.md` the second — the same
three-point split under a different title, taken against the #172 squash.
Nothing here is an edit of either.

## The points

| | commit | what it is |
|---|---|---|
| **A** | `2237d1b` | **the last squash with `main`** — *Elendilon -> Main (CLEAR SKIES performance, DOT DELIRIUM, GFX Lines Library per app, Office/Games/Network 360k disks)* (#179), 2026-09-13 |
| **B** | `0ba4677` | `elendilon-next` at its tip before this session's merge, **+562 commits** over A |
| **C** | `dfd5796` | `main` at its tip, **+9 commits** over A |
| **D** | `ba34ab5` | the merge of B and C **plus the five size passes of 2026-09-17** |
| **E** | `5f20918` | an intermediate point on B's arm, used only to split one module — see *Two lanes* |

**A→B is the branch's own arm, A→C is everything `main` did, A→D is what the
tree carries now.** B and C are siblings, not ancestors: `main` squash-merges,
so A is where the two last agreed.

**The two arms overlap by exactly one commit and it is worth nothing.**
`git merge-base origin/main 0ba4677` is `8d0f363` (#180), which B already
carries, so A→B and A→C both contain it. Its whole diff is one file —
`.claude/skills/release-os8088/mkzip.py`, 1 insertion and 2 deletions — and no
kernel byte moves in it. Every other commit is on one arm or the other.

**The build number contributes nothing to any delta here.** `BUILD_STR` is the
commit count as a decimal string (SPEC.md 14.2) and the four counts are 153,
715, 162 and 743 — three digits at every point, so the About box's string is
three bytes at every point. A comparison that crossed 999→1000 would not be
able to say this, and the next one of these reports will not be able to.

**`KERN_BUDGET` is 129,536 at all four points and `KERN_SMALL_BUDGET` 107,520.**
Nothing below is a budget move; every figure is a size move.

## Headline — `kern_big`, the shipped default

| section | A base | B ours | C main | D now | **B−A** | **C−A** | **D−A** |
|---|---:|---:|---:|---:|---:|---:|---:|
| `.text` | 49,539 | 49,416 | 50,146 | 49,891 | **−123** | **+607** | **+352** |
| `.bss` | 6,016 | 6,006 | 6,151 | 6,092 | **−10** | **+135** | **+76** |
| `.cold` | 39,265 | 41,166 | 39,356 | 40,899 | **+1,901** | **+91** | **+1,634** |
| `.ovl` | 1,417 | 1,417 | 1,588 | 1,511 | 0 | **+171** | **+94** |
| `.ovlw` | 5,052 | 5,084 | 5,052 | 5,084 | +32 | 0 | +32 |
| `.lowbss` | 9,182 | 7,966 | 9,182 | 7,966 | **−1,216** | 0 | **−1,216** |
| `.vgabuf` | 848 | 848 | 848 | 848 | 0 | 0 | 0 |
| **sum** | | | | | **+584** | **+1,004** | **+972** |
| **`KERN_SIZE`** | 110,592 | 111,616 | 111,104 | 111,616 | **+1,024** | **+512** | **+1,024** |
| spare of `KERN_BUDGET` | 18,944 | 17,920 | 18,432 | 17,920 | | | |

Three rungs were spent between the two arms and **one has been given back**:
B−A is two rungs, C−A is one, and D−A is two rather than three. That last 512
is the five size passes of 2026-09-17, and it is the only reason the merged
tree is not three rungs above the squash.

## Headline — `kern_small`, the 128KB floor machine

| section | A base | B ours | C main | D now | **B−A** | **C−A** | **D−A** |
|---|---:|---:|---:|---:|---:|---:|---:|
| `.text` | 37,453 | 37,278 | 37,465 | 37,263 | **−175** | **+12** | **−190** |
| `.bss` | 4,242 | 4,179 | 4,242 | 4,179 | **−63** | 0 | **−63** |
| `.cold` | 26,197 | 26,731 | 26,197 | 26,588 | **+534** | 0 | **+391** |
| `.ovl` | 423 | 423 | 423 | 423 | 0 | 0 | 0 |
| `.ovlw` | 2,789 | 2,820 | 2,789 | 2,820 | +31 | 0 | +31 |
| `.lowbss` | 5,460 | 5,236 | 5,460 | 5,236 | **−224** | 0 | **−224** |
| **sum** | | | | | **+103** | **+12** | **−55** |
| **`KERN_SIZE`** | 75,776 | 75,776 | 75,776 | 75,264 | **0** | **0** | **−512** |
| spare of `KERN_SMALL_BUDGET` | 31,744 | 31,744 | 31,744 | 32,256 | | | |

**The floor machine is 512 bytes SMALLER than it was at the squash**, after a
cycle that added a DOS box, an icon store and a document-glyph column to the
tree. It is the only line in this document that is unambiguously good news, and
it is worth saying why it is not luck: `kern_small` gets none of `main`'s two
big features (`DOCK_OPT` is inside `%ifdef KERN_BIG`), the branch's own arm
spent only 103 bytes of section there against `kern_big`'s 584, and the icon
store's pass on 2026-09-17 took a whole `.cold` rung back.

**`main`'s twelve bytes are the second-most-useful line here.** `main`'s nine
commits cost the floor machine **12 bytes of `.text` and not one byte of
footprint** — the `kern_small` refusal stub for `OSAPI_MOUSE_FEED` (SPEC.md
20.8 rule 4) and nothing else. The previous report in this series found the same
shape and it has held for a second cycle.

## `main`'s arm, by concept

Four of `main`'s nine commits touch kernel bytes. The module deltas are
A→C, exact from `kernsize --modules`.

| concept | PRs | modules | `.text` | `.cold` | `.bss` | total |
|---|---|---|---:|---:|---:|---:|
| **the Dock — placement, auto-hide, the Control Panel page** (SPEC.md 30.5–30.6) | #189, #193 | `dock.inc` +327, `wm.inc` +78, `ui.inc` +30, `menu.inc` +22, `ctrl.inc` +15, `mod.inc` +13, `vidsel.inc` +9, `fsx.inc` +3 | +462 | +40 | +69 | **+571** |
| **the USB mouse on the CH375** (SPEC.md 9.12) | #187 | `mouse.inc` +92, `driver.inc` +54, `kernel.asm` +24 | +145 | +9 | +39 | **+193** |
| **the file dialog's size column** | #188 | `fdlg.inc` +42 | 0 | +42 | 0 | **+42** |
| incidental reductions | — | `font.inc` −8, `icons.inc` −2, `viddet.inc` −1 | −11 | 0 | 0 | **−11** |

The Dock figure is an A/B rather than an attribution: built with `DOCK_OPT`
defined and undefined on the same tree, which is why it carries `.ovl` +166 that
no module row shows. **The Dock is exactly the 512-byte rung `kern_big` crossed
on `main`'s arm**, and `.ovl` +166 on top of it.

## Our arm, by concept

Our arm is 562 commits, 131 of which touch `kernel/`, `boot/`, `kerndos/` or
`apps/os88api.inc`. Attribution below is **per module**, which `kernsize` gives
exactly, with the concept named from the commits that touched it. Where a module
carries more than one concept it is split at a measured intermediate point, not
apportioned by source lines — a line is not a byte and this project refuses that
arithmetic.

### Two lanes

One module, `kernel/disk.inc`, carries two unrelated concepts and is +909 code
across the window. It is split at **E = `5f20918`** (*The read-ahead asks what
the machine HAS as well*), the last commit of the DOS/read-ahead work and the
one before the icon store's first: A→E is the first lane, E→B the second.

| lane | `.text` | `.cold` | `.bss` | `.lowbss` | code |
|---|---:|---:|---:|---:|---:|
| **A→E** the DOS box's kernel surface, the read-ahead, the compactor | −216 | +855 | −24 | 0 | **+639** |
| **E→B** the icon store, the document glyph, the late work | +93 | +1,046 | +14 | −1,216 | **+1,139** |

### Lane 1 — what the DOS box asked the kernel for (A→E, +639)

The DOS box itself is `kerndos/` and `apps/dos/` — a package and a module
image, not resident kernel. What it cost the KERNEL is the doors it needed.

| concept | modules | code |
|---|---|---:|
| the heap's purge floor, self-compaction and `mem_regrow`'s shed (SPEC.md 50.6.6, 66.4.3) | `memory.inc` | **+193** |
| the read-ahead window: claims no DMA page, moves, asks what the machine has (SPEC.md 18.95.7, 50.6.7) plus the DOS path walkers | `disk.inc` | **+255** |
| `OSAPI_FILE_COPY` / `OSAPI_FILE_MOVE`, one door with a verb (SPEC.md 22.24–22.25) | `filecp.inc` | **+126** |
| `OSAPI_DRV_SUSPEND` and the DOS handoff as its verb 2 (SPEC.md 51.11, 96.40) | `hiber.inc` +71, `driver.inc` +33 | **+104** |
| `OSAPI_FILE_WRITE_AT` / `_APPEND` and `OSAPI_VOL_STAT` (SPEC.md 18.4.6, 18.4.7) | `diskw.inc` (`.text` −97, `.cold` +134) | **+37** |
| the file dialog, `OSAPI_FILE_PATH`'s walkers, the rest | `fdlg.inc` +39, `files.inc` +20, `wm.inc` +28, `ui.inc` +12, `snd.inc` +7, `vga12.inc` +5, `loader.inc` −3, `mouse.inc` −18 | **+90** |

### Lane 2 — the icon store and what came after (E→B, +1,139, −1,216 of `.lowbss`)

| concept | modules | code | `.lowbss` |
|---|---|---:|---:|
| the listing's **icon store**: one body per machine, a pool, purgeable (SPEC.md 25.8) | `disk.inc` +654, `dskwin.inc` | **+654** | **−1,216** |
| a package may **ship its 8x8 document glyph** (SPEC.md 54.3.2) | `assoc.inc` | **+197** | 0 |
| `ld_pkg_byname` — the DOS shell's `open <document>` arm (SPEC.md 21.5.3) | `loader.inc` | **+159** | 0 |
| **Alt+Enter** into and out of full screen (SPEC.md 96.33.5.1, 9.7.1) and the mouse work beside it | `mouse.inc` +42, `ui.inc` +25, `fsx.inc` +5 | **+72** | 0 |
| the DOS box's Memory page: a suspend mask and a class figure (SPEC.md 51.12) | `driver.inc` +29, `memory.inc` +10, `files.inc` +18 | **+57** | 0 |

**The `.lowbss` line is the one to read twice.** `.lowbss` sits BELOW `HEAP_SEG`
in the ladder, so every byte there comes off the heap and therefore off the DOS
arena byte for byte. The icon store spent 654 bytes of `.cold` to take 1,216 off
`.lowbss`, and `docs/reports/DOS-GAMES-2026-09-16.md` has Chip 'n Dale losing by
three kilobytes — which is what those 1,216 bytes are for.

### The size passes already inside this window

Our arm is **net negative in `.text` on both kernels** (−123 big, −175 small)
while adding every concept above, and that is not an accident. The
`size-pass-kernel-additions` branch ran inside this window and its record is
`docs/reports/GFXBENCH-SIZE-PASS-2026-09-16.md`: **1,820 resident bytes**,
taking `kernel.asm` −111 and `fprog.inc` −55 among others, and retiring two
cells off the API table's tail. The five passes of 2026-09-17 took a further
616 bytes of section and one 512-byte rung on each kernel.

## What each arm cost, in one line each

- **`main`** spent **+1,004 bytes of section and one rung** on `kern_big` for
  three concepts, of which the Dock is 571 and `.ovl` +166 on top. On
  `kern_small` it spent **12 bytes and no rung**.
- **We** spent **+584 bytes of section and two rungs** on `kern_big` for a DOS
  box's worth of kernel surface, an icon store and a glyph column — while
  giving back 1,216 bytes of `.lowbss` and taking `.text` DOWN on both kernels.
  On `kern_small`, **+103 bytes and no rung**.
- **Together, after the 2026-09-17 passes**, the tree stands **+972 bytes of
  section and two rungs** above the squash on `kern_big`, and **55 bytes and one
  rung BELOW it** on `kern_small`.

## Where that leaves the two kernels

| | `kern_big` | `kern_small` |
|---|---:|---:|
| `KERN_SIZE` | 111,616 | 75,264 |
| budget | 129,536 | 107,520 |
| **spare** | **17,920** (35 steps of 512) | **32,256** (63 steps) |
| `.text`+`.bss` of `KERN_CODE_MAX` | 55,983 of 65,536 — **9,553 left** | 41,442 — 24,094 left |

`KERN_CODE_MAX` cannot be raised at all (offsets are 16 bits) and is the
constraint to watch: 9,553 bytes against `KERN_BUDGET`'s 35 steps. `main`'s arm
spent 742 of those 9,553 and ours took 133 back.

## Which of these concepts has had a size optimization pass

A second question, answered off the same accounting: for the last TWO squash
cycles, has each kernel-byte-touching concept been through a pass of its own?
"Yes" means a commit or a branch that took bytes out of THAT concept after it
landed — not a measurement of it, and not a size-conscious choice made while
writing it.

### This cycle (A→D, since #179) — four outstanding

| concept | arm | code | pass |
|---|---|---:|---|
| the Dock (SPEC.md 30.5–30.6) | main | +571 | **yes** — 2026-09-17, 571 → 486 and the router 227 → 42 guest cycles |
| the USB mouse / CH375 (9.12) | main | +193 | **yes** — 2026-09-17, 145 → 94 `.text` |
| **the file dialog's size column (#188)** | main | **+42** | **NO** |
| the purge floor, self-compaction, `mem_regrow`'s shed (50.6.6, 66.4.3) | ours | +193 | **yes** — `e820ed46`, `212f3293`, `bfe562bf`, `e7d97d7a` |
| `OSAPI_FILE_COPY` / `_MOVE` (22.24–22.25) | ours | +126 | **yes** — `c54f7b0a`, −215 bytes |
| `OSAPI_DRV_SUSPEND` + the DOS handoff (51.11, 96.40) | ours | +104 | **yes** — `9b3edc6a` |
| `OSAPI_FILE_WRITE_AT` / `_APPEND`, `OSAPI_VOL_STAT` (18.4.6–18.4.7) | ours | +37 | **yes** — `eb4e7de6`, `a2ef1b6d` |
| `OSAPI_FILE_PATH` (19.2.4) | ours | — | **yes** — `e99265a1`, 393 → 137 |
| the API table's tail and its cell thunks (20.3.1–20.3.2) | ours | −111 | **yes** — `8ffb6b98`, `2985908d` |
| the busy pointer's clock, the scroll bars' release (7.5, 13.10.5.4.2) | ours | — | **yes** — `da8adbff` |
| the icon store (25.8) | ours | +654 | **yes** — 2026-09-17, −303 `.cold` and a rung on both kernels |
| the shipped document glyph (54.3.2) | ours | +197 | **yes** — 2026-09-17, same pass |
| Alt+Enter (96.33.5.1, 9.7.1) | ours | +72 | **yes** — 2026-09-17, 72 → 46 `.text` |
| the Memory page's two slots (51.12) | ours | +57 | **yes** — 2026-09-17, 111 → 52 |
| **the read-ahead cache — claims no DMA page, moves, the ladder, the width command (18.95.7, 50.6.7)** | ours | **part of +255** | **NO** |
| **`ld_pkg_byname` / `ld_pkg_upc` — the DOS shell's `open <document>` arm (21.5.3)** | ours | **+159** | **PARTIAL** — the 2026-09-17 icon-store pass took 22 of it in passing, as a duplicate of `assoc_stem_of`'s walk; the other ~137 has never been looked at |
| **the mouse wire work — a wheel mouse's fourth byte, `MOU_IDMAX` 8 → 128, `MOU_DRAINT`, `MOUROUND`** | ours | **part of `mouse.inc`** | **NO** |
| **`fdlg.inc` +39, ours** | ours | **+39** | **NO** |

### The previous cycle (what #179 carried, #172 → #179) — ALL of it outstanding

**`main` added no kernel bytes of its own in that window at all.** Of the
sixteen commits on `main` between #172 and #179, only #179 itself — our squash
— touches `kernel/`, `boot/` or `apps/os88api.inc`. Its other six (#161, #162,
#171, #176, #177, #178) are packages and release tooling. So every kernel byte
in that cycle is ours, and the concepts are the ones its diffstat names:

| concept | kernel diffstat | pass |
|---|---|---|
| the GFX lines library moved into the apps that use it | `vga12.inc` **−1,701** | **n/a — it IS the reduction** (`docs/plans/completed/GFX-EMBEDDABLE-PLAN.md`) |
| the Control Panel's glyph and line conversion | `ctrl.inc` +451 | **NO** — measured (`docs/reports/GLYPH-AND-LINE-COST-2026-09-10.md`), never passed |
| nothing permanently pinned on the heap | `memory.inc` +385 | **NO** — but reached later by this cycle's `e820ed46`/`212f3293` |
| the busy cursor, hourglass then clock | `mouse.inc` +322 | **partially** — measured (`docs/reports/BUSY-CURSOR-COST-2026-09-10.md`), then passed by this cycle's `da8adbff` |
| the package re-home and `.o88` parts | `loader.inc` +198, `instance.inc` +172 | **NO** |
| the rest | `kernel.asm` +182, `files.inc` +119, `apps/os88api.inc` +281, `sched.inc` +53, `wm.inc` +45 | **NO** |

**The evidence that no pass ran in that cycle is its own subject list.** #179
carries 326 subjects and exactly one of them is size work on the kernel's own
additions — *"The PR cycle's byte audit - and the package it found nothing was
building"*, which is `docs/reports/PR-CYCLE-ACCOUNTING-2026-09-11.md` and is an
ACCOUNTING, not an optimisation. #172's subject list has none at all. Kernel
size passes 1 to 4 all landed by #147, two squashes earlier
(`docs/plans/completed/HANDOFF-KERNEL-SIZE-P3.md`).

So the pattern across two cycles is that **a cycle's kernel additions get
audited and then passed one cycle late, if at all** — this cycle's
`size-pass-kernel-additions` reached the previous cycle's busy cursor and heap
work, and the 2026-09-17 passes reached this cycle's four biggest. What has
never been reached is listed above.
