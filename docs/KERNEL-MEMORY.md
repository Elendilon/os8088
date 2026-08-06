# The kernel's memory

**This document is maintained.** It is the standing account of what the
os8088 kernel spends RAM on and why, and it is expected to be updated in the
same commit as any change that moves a number in it. SPEC.md §2 is the
binding contract for the addresses; this is the reasoning behind them.

Every figure below was measured against the shipped build on the day it was
written, and the section at the end says how to re-measure each one.

---

## The rule

**The kernel is ONE contiguous span starting at linear 0x00600, and that
includes its buffers.** The span is `KERN_BUDGET` bytes — 79KB today, and
64KB for as long as that was affordable (see below). It currently runs
0x00600 through 0x139FF, and the budget's ceiling is 0x14200.

Not the code and then some scratch elsewhere: *everything*. Code, read-only
data, `.bss`, the FAT window, the directory and icon caches, the sector
buffer and every task stack are one contiguous span starting at
`KERNEL_SEG`. Guard 1 in `kernel/kernel.asm` measures that whole span
against `KERN_BUDGET` and fails the build if it is over.

**There is exactly one deliberate exception**, and it is a heap claim rather
than a reservation: the menu save-under (SPEC.md §12.4), which exists only
while a pull-down is on screen and is handed back the moment it closes. It is
not part of the kernel's footprint because on any given tick it usually is not
there — `menu_drop` claims it on the way in and releases it on the way out,
*before* the selected item runs, so a menu that launches something has already
given it back by the time the launch asks for memory.

That claim is **sized from the rect actually dropped** (`menu_save_kb`), not
from the worst case: Locator's File menu wants about 4KB on VGA and about 1KB
on Hercules, where `[vid_planes]` is 1 and three quarters of a fixed figure
would never be written to at all. `MENU_SAVE_KB` = 20 survives as the
build-time **ceiling** that guard 4 proves the arithmetic can never exceed.
Both corrections were the same bug twice: the flat 20KB was first claimed once
at `menu_init` and held for the whole session — more than a third of a 128KB
machine's heap, held permanently against nothing — and then, once it was
transient, it was still 20KB per menu, which on a machine with a sound card
(55K of heap, 38K held by the driver) could not be had at all, so every menu
there took the slow repaint path permanently.

**The size in RAM is the actual size, not a budget.** There is no growth
room anywhere in the ladder. Each rung is the measured size of what it
holds, rounded up only as far as alignment demands, so the heap starts where
*this build's* kernel happens to end and moves when the kernel does. A fixed
ceiling with slack under it is memory that nothing can ever use — which is
what the **package pool** had become: 60KB reserved above the kernel whether
or not a package was loaded. A package's region is an ordinary heap claim now
(SPEC.md §20.1), taken from the top of the heap downward while data claims
grow up from the bottom.

**If the kernel needs to grow past its budget, that is a conversation, not a
build fix.** Raise `KERN_BUDGET` only after explaining to whoever asked for
the feature what it costs and getting an explicit yes. The guard's error
message points here for that reason.

### The four raises

`KERN_BUDGET` was 65,536 — the first 64KB above the BIOS data area, which is
where the "one region" rule came from. It has moved four times, each one
asked for and granted:

| | budget | bought |
|---|---:|---|
| 1 | 65,536 → **71,680** (70KB) | the SPEC.md §41 extended-memory store, and the two API surfaces that came with it (`wm_geom`, `wm_about_set`) |
| 2 | 71,680 → **72,704** (71KB) | the loadable sound driver (SPEC.md §51) and the Control Panel pages that drive it |
| 3 | 72,704 → **76,800** (75KB) | SPEC.md §51.5's keyed `SYSTEM.CFG` — a settings file where nothing is positional costs a key table, a bounded record walker and a writer |
| 4 | 76,800 → **80,896** (79KB) | the file manager's Cut/Copy/Paste, its recursive paste engine and the drag (SPEC.md §22.3/§22.4) |

Raise 2 is the one that **bought more than it spent**: `sndfm.inc` and
`sndsb.inc` were 3,260 lines of resident kernel code on every machine whether
or not a card was in it, and the 1KB of loader machinery turned them into a
file on the system disk that a 128KB machine with no card never reads — and
the same machinery carries the next driver for nothing.

Raise 3 was granted **in advance of further work**, with an optimisation pass
to follow that should hand some of it back, so the slack under it was meant to
be temporary rather than an invitation. Raise 4 spent it: Cut/Copy/Paste
overran the 75KB figure by 512 bytes with the drag still to come, and the
4KB it costs the claim heap on every machine was named up front — Paint gives
up one canvas tier for it, and the 128KB RAM floor is untouched.

**`BOOT_RELOC` moved with every one of them** — 0x0940 → 0x0AA0 → 0x0B80 →
0x0C00 → **0x0D40** (linear 0x11000 → 0x12600 → 0x13400 → 0x13C00 →
**0x15000**) — because guard 5 pins the kernel's landing zone below the
relocated boot sector's stack. It is mirrored in `boot/boot.asm` and the two
must change together.

### The segment is what binds now, not the budget

`.text` + `.bss` are addressed through one segment with 16-bit offsets, so
guard 2 caps them at 65,536 **whatever the budget says**. That limit is
untouched and cannot be raised at all.

For most of this project's life the budget was the tighter of the two, which
is the intended order — a budget is a decision and a segment is physics. It
is no longer true:

| | headroom for `.text` + `.bss` |
|---|---:|
| guard 2, the segment | **391 B** |
| guard 1, the budget | 2,560 B |

At 65,145 bytes of image the segment still runs out first — by a factor of
six and a half — and hard-disk support (below) is what took it there; the
`.lowbss` migration (below that) is what bought the first 320 bytes back. So the next thing to hit
is not a conversation about `KERN_BUDGET` — it is a hard 16-bit ceiling that
no decision can move, and the only ways past it are doing less, doing it
smaller, or moving it out of the segment.

The two are also coupled through the rounding, and that coupling is
load-bearing in both directions. **The image rung is still 65,536 bytes — the
segment maximum exactly** — so guard 1's spare cannot be spent on code at any
price; only the buffers and stacks reach it. And a byte moved from `.bss` to
`.lowbss` is guard-2 positive but guard-1 *negative* until the image falls far
enough to drop a 512-byte step: when the `.lowbss` rung is full, the very
first byte moved costs a whole step. That is why the migration below and the
stack halving had to land together — the first was not affordable without the
second.

---

## Where it goes

Measured on the shipped build. `make` prints the image size; the rest come
out of the same constants the guards use.

| region | size | what it is |
|---|---:|---|
| image (`.text` + `.bss`) | 65,536 B | all kernel code, its read-only data, and its scratch |
| task stacks | 3,840 B | 11 background slots of 256 B + task 0's 1,024 |
| `.lowbss` tables | 500 B | `mem_tab`, `menu_bar` and the two built-in state pools |
| disk buffers | 3,584 B | directory cache, icon cache, sector scratch |
| FAT window | 4,608 B | nine of the mounted volume's FAT sectors (SPEC.md §18.8) — the whole FAT on any floppy, a sliding window on a hard disk |
| **total** | **78,336 B** | of an 80,896-byte budget — 2,560 B spare |

The image rung is `.text` (59,752) + `.bss` (5,393) = 65,145, rounded up to a
whole 512 bytes; the 391-byte remainder is the only slack anywhere in the
ladder, and it is a rounding artefact rather than a reservation. That rung is
also, as of hard-disk support, the largest it can ever be.

The ladder lands on these segments: `KERNEL_SEG` 0x0060, `FAT_SEG` 0x1060,
`LOW_SEG` 0x1180, `HEAP_SEG` 0x1380.

Everything above that is the claim heap, up to whatever int 12h reports. The
arithmetic is exact and worth writing down, because every RAM figure in this
project falls out of it:

> **heap KB = what int 12h reports − 78**

`KERN_END` is 4,992 paragraphs = 79,872 bytes = exactly 78KB, and the heap
starts there. Checked against a live machine: QEMU with `-m 1M` reports
**639KB** and the Task Manager shows **561KB** of heap. Re-derive this after
any budget change — it has moved with all four of them, and again with
hard-disk support without the budget moving at all. It used to be *nothing* on a small machine: the package
pool's own top sat above 128KB, so a 128KB machine had no heap and could load
no package at all.

## What it actually takes to run

Measured, not derived — by clamping what `mem_init` believes int 12h said and
booting each size under QEMU. (The clamp is a throwaway; it is not in the
tree.) Three different questions, three different answers:

| RAM | heap | what happens |
|---|---|---|
| < 84.5KB | — | **cannot boot.** Nothing to do with the heap: `boot/boot.asm` relocates itself to `BOOT_RELOC:7C00` = linear 0x15000 and reads the kernel from there, so the machine has to have the 512 bytes through 0x151FF. Guard 5 checks the kernel clears its stack |
| 85KB | 7KB | boots, full desktop, browses both floppies, **loads a package** (`hello`) |
| 101KB | 23KB | Note Pad runs. Paint loads and puts up its "Not enough memory" notice — the designed tier, not a crash |
| 165KB | 87KB | Paint still gets the notice |
| 181KB | 103KB | **Paint runs live**, full 448×280 canvas |
| 640KB | 561KB | everything, including the 150KB back buffer |

So the honest floor is **85KB to boot and load something**, and **~181KB for
every shipped app at full function**. The often-quoted "128KB" sits between
those: it runs the OS and most of the packages, and Paint declines.

Those thresholds are properties of the **heap**, not of the machine, so the
RAM column moves by exactly whatever `KERN_END` moves — before raises 3 and 4
this table read 80KB / 96KB / 160KB / 176KB against the identical heap
figures, and hard-disk support shifted it 1.5KB again without touching the
budget. **The outcome column was measured boot by boot** with `mem_init`
clamped; the RAM column is those measurements re-derived onto today's
`KERN_END`.

Two things this table is not. It is not a promise about *speed* — these were
measured under QEMU, which does not model 8086 timing at all (SPEC.md §5.4).
And the sizes below 640KB were simulated by clamping the heap, so they
exercise every "the heap said no" path faithfully but do not exercise a BIOS
that reports a small number, which only real hardware and 86Box can do. (Nor
can the "cannot boot" row be tested here at all: QEMU/SeaBIOS will not boot
below 1MB, so that one is derived from `BOOT_RELOC` rather than observed.)

The Task Manager's memory view shows this same breakdown live, one indented
row per buffer under **System**, and paints the buffer part of the kernel
span in its own texture on the RAM bar. Every figure there is an
assembly-time constant, so the twice-a-second refresh does no arithmetic to
produce them — and it does not draw them either unless they moved: every
element on the page reduces what it is drawn from to one word and compares
that against what it last drew, so a desktop sitting still costs a few string
builds and two table hashes rather than two map interiors and a dozen rows.

The page is **one map, captioned on the line directly above it** — the
second used to magnify the package pool, and there is no pool:

```
RAM  77/639K [] HEAP   0/561K       <- the map's caption, both figures
[==============================]    <- every byte the machine has
XMS   0/64448K                      <- and what it has no address for
[==============================]
```

Its four buffer rows read `Code+data 64K`, `Stacks 4K`, `Disk bufs 4K` and
`FAT snap 5K` against a `System` row of `77K`. They sum to 78, not 77,
because each row rounds its own KB up independently while `System` rounds the
whole span once — the rows are exhaustive, not additive.

The top line is **one string**, swatch and all — the swatch is drawn into
the two spaces between the pairs — because that makes the whole line one
comparison when the refresh asks whether it needs drawing at all.

The heap has no map of its own and never will: a claim is drawn in the
conventional map at its real address, in among the kernel and everything
else, so its figures belong to that map's caption and share the top line with
RAM. **Package regions are claims too** (SPEC.md §20.1) and are drawn there
in their per-slot patterns — at the far right, because they are claimed from
the top of the heap downward while data grows up from the bottom, so the two
kinds separate visibly.

Each row's legend square is the texture its memory is drawn in on the maps,
so the two can be read against each other:

| square | band | where |
|---|---|---|
| 50% gray | the kernel's own span | `System` |
| horizontal bars | its buffers | `Stacks`, `Disk bufs`, `FAT snap` |
| framed light block | a live heap claim | beside the `HEAP` figures |
| per-slot pattern | one package's region | each package row |

A row only gets a square when the texture is its own. `Code+data` has none —
it is drawn in the same gray as `System`, and a square that repeats one above
it is not a legend. `Builtins` has none because a built-in owns no band at
all: its code is already inside `Code+data`, and its memory is heap claims
billed to its own row. And the claim texture is keyed beside the `HEAP`
figures rather than in the list, because it belongs to the HEAP *column* and
not to any one row.

Every square goes through one routine over an 8-byte pattern, including the
two the maps themselves draw with `gfx_fill_gray` and a plain black fill:
`tm_pat_gray` is byte for byte what `gfx_fill_gray` lays down, so a square is
the same pixels as its band and not merely a similar grey. A set bit is
white (SPEC.md §5), which is why solid black is a pattern of eight zeroes.

A claim is the only band drawn with a **frame**, because it is the only one
that comes and goes while you watch, several sit shoulder to shoulder, and
the scale is coarse enough (4KB per pixel on a 640KB machine) that a 3KB
Disk-window cache is one column. The frame is what makes its edges readable;
the interior texture is light so it does not swallow it.

---

## Each region in detail

### The image — `.text` 59,752 B + `.bss` 5,393 B

One flat binary at `KERNEL_SEG:0000`, assembled `-f bin` with no linker.
`.bss` follows `.text` immediately and is uninitialised by definition, so it
costs nothing on the floppy and everything in RAM. Where every one of those
bytes goes is the last section of this document.

The ladder charges the pair **rounded up to a whole 512 bytes** (see the
alignment invariant below) — 65,536 B, so 391 bytes of the rung are rounding
remainder. Measure the unrounded pair by appending `section .text` /
`times KBSS_SIZE db 0` to `kernel/kernel.asm`, assembling, and taking the file
size; revert afterwards. `make`'s own `kernel: n bytes` line is `.text` alone.

**All of the kernel's code is here.** There used to be a `.fartext`
section — cold modules (the Control Panel, the Task Manager, one sound
routine) assembled at `vstart=0`, shipped at the tail of the image and
copied down to their own segment below the kernel at boot, so that their
5,455 bytes did not count against the kernel's 64KB window. It was retired
when the budget above replaced that window as the thing being steered by,
and the arithmetic is why: the mechanism needed a **10,752-byte
reservation** in low memory to hold a 5,455-byte blob, so the moment the
whole footprint became the number that mattered it was costing 5,297 bytes
to save nothing. Merging it back also deleted the shims — three `FARSHIM`
stubs, twenty-seven `FARK` wrappers, `far_init`, and two bytes on every one
of the 91 `KCALL` sites — which is why the image grew by less than the blob
it absorbed.

The consequence for anyone adding code: **there is no longer anywhere to
put a module that is "too cold to be worth the space".** Cold code is
ordinary code. If the image needs to shrink, it shrinks by doing less or by
doing it smaller, not by moving it somewhere the accounting cannot see.

### Task stacks — 3,840 B

Eleven background slots of `SCH_STACK` = **256** bytes (`MAX_TASKS-1`, since
task 0 owns no slice of `sch_stacks`), plus `STK0_SIZE` = 1,024 bytes for
task 0 itself. They live in `.lowbss`, addressed through SS, which is why
SS ≠ DS everywhere in the kernel (SPEC.md §1).

**Both numbers are measured.** A 0xCC fill over the whole stack region,
then the machine driven as hard as it goes — Clock, two Bounces, About, the
Control Panel on both its pages, the Task Manager with a window drag, a Disk
window, the Fractal with its worker task, and Paint saving a GIF into a
folder it created from the file dialog — leaves its deepest mark at **274
bytes** on task 0's stack and **142** on a background task's — the latter
confirmed twice over, by the Fractal's drawing worker and by Tracker's
streaming worker with a Sound Blaster's IRQs nesting on top of it. ISR frames are
included in that: the tick and mouse handlers run on whichever stack they
interrupt. So 256 is 1.8× the worst observed background depth and 1,024 is
3.7× task 0's.

**1.8× is thinner than this project usually runs, so it is checked rather
than trusted.** `SCH_MAGIC` sits at the bottom word of every slice, written by
`task_spawn` and compared by `sch_switch` against the task it is switching
away from; a mismatch means the next push would land in the slice below —
another task's stack — and `sch_stkdie` halts the machine instead. The check
is four instructions and no multiply, because `SCH_STACK` = 256 makes slot *n*'s
base the slot index in the high byte of BX and nothing else; a build-time
`%error` pins that assumption to the constant. Re-measured after the change
under the same load, with the canaries verified intact afterwards, the worst
slice was **118 of 256**.

Task 0 gets the larger share because it is the UI task: every window
callback, every menu track, every file-dialog interaction and every built-in
app runs on it.

**`STK0_SIZE` is a constant, and that is the whole point.** It used to be
"whatever is left between the top of `.lowbss` and the kernel segment" —
which meant task 0's stack silently absorbed every byte saved anywhere below
it. Two rounds of shrinking the buffers under that rule freed exactly
nothing: the FAT buffer gave up 7KB and task 0's stack grew by 7KB. Naming
the number is what turned those savings into memory.

Re-run the fill probe before lowering either number. Guard 3 only proves
`STK0_SIZE` is big enough to be a stack at all; `SCH_MAGIC` is what catches a task that
outgrows its own slice, and it catches it at the next switch rather than
whenever the corruption happens to matter.

### Disk buffers — 3,584 B

Three buffers in `.lowbss`, written by int 13h through ES:BX and read only
through `dsk_get_dir` / `dsk_get_icon`, which stage one entry at a time back
into the kernel segment so no drawing or parsing code has to learn about
segments:

- `disk_dir`, 1,024 B — the mount-time directory listing, 32 synthesized
  32-byte entries. The 32-entry cap is what sizes it.
- `disk_icons`, 2,048 B — one harvested 64-byte icon per listed entry.
- `dsk_secbuf`, 512 B — one sector of scratch: the directory sector being
  read-modify-written on a write, and the zero-padded final sector of a file.

Together they are exactly `.lowbss` minus the eleven background stacks, which
is how the Task Manager's `Disk bufs` row derives itself.

### FAT window — 4,608 B

`DSK_FAT_SECS` × 512 — the whole FAT on any floppy, and a sliding window on a
hard disk (SPEC.md §18.8). Re-read from the volume on **every** mount, with
`dsk_next_clus` its single reader and `dskw_setfat` its single writer, both
through ES only.

`DSK_FAT_SECS` = 9 is not a buffer with slack — it is an **acceptance
threshold**. Mount rule 10 (SPEC.md §18.2) refuses a volume whose declared
FAT is larger before a byte of it is read, so the number is exactly the
largest FAT any geometry this OS boots or builds declares: 1.44MB = 9,
1.2MB = 7, 720KB = 3, 360KB = 2.

It also decides, on its own, that **FAT16 is unreachable**: a FAT is only
FAT16 with ≥ 4,085 clusters, which needs ≥ 16 FAT sectors, so rule 10 turns
the whole class away. The FAT16 halves of `dsk_next_clus` and `dskw_setfat`
remain in the tree and nothing can call them.

---

## Two invariants that are easy to break

### Every disk-visible base is 512-byte aligned

int 13h moves one sector per call, which bounds a transfer to 512 bytes —
but **does not stop one from straddling a 64KB physical boundary**. Only
starting on a 512-byte boundary does that, and the DMA controller answers a
straddle with error 09h.

Every base in this ladder is an int 13h target: the FAT window, the disk
buffers, a package image being loaded, and a package's file buffer out of
the heap. So the image rounds up to a whole **512 bytes** rather than to a
paragraph, and because `FAT_PARA` (288) and `LOW_PARA` are both multiples of
32 paragraphs, aligning that one rung aligns the whole ladder. Guard 6 proves
it — and guard 6b proves the claim heap keeps it, since a package image is
read by int 13h into a **claim** now: `mem_claim` rounds to whole KB, so every
base it hands out is `HEAP_SEG` + n·64 paragraphs.

This held by luck until the ladder became derived: every base used to be a
round constant like `0x0300` or `0x2A00`, and nothing said why that
mattered. The symptom when it broke was a **"Disk error" toast on any save
larger than the distance from the buffer to the next 64KB boundary** —
Paint's 63KB BMP hit it immediately, a Note Pad text file never would.

### The boot sector has to get out of the way

The BIOS loads `boot/boot.asm` to 0000:7C00 and it is *still executing*
while the kernel's sectors arrive — it far-calls the splash at
`KERNEL_SEG:0008` after every one. With the kernel landing at 0x00600 and
running up to 80KB, it covers 0x7C00 long before the last sector.

So the sector's first act is to copy itself to `BOOT_RELOC:7C00` (linear
**0x15000**, above anything the kernel can reach) and far-jump there. **The
copy keeps the same offset**, so every label in the file still resolves at
`org 0x7C00` and only the segment registers change; its stack rides along at
the same offset and grows down from 0x15000, with `BOOT_STACK` = 2,048 bytes
reserved under it. Guard 5 proves the kernel ends clear of that stack, and at
today's size it does so with 2,048 bytes to spare.

`BOOT_RELOC` and `KERNEL_SEG` are mirrored in `boot/boot.asm`, which is
assembled separately. `apps/os88api.inc` carries a third copy of
`KERNEL_SEG`, because it is baked into every package's far-call targets —
**a kernel move means rebuilding every `.o88` and both apps floppies**, or a
package calls into empty memory.

---

## History

| change | budget | kernel footprint |
|---|---:|---:|
| before any of this (v1.0.20260728) | — | ~107 KB |
| low memory sized to measurement, kernel moved to 0x0800 | 64 KB | 75 KB |
| `.fartext` retired, ladder derived, buffers trimmed, kernel at 0x0060 | 64 KB | 63.5 KB |
| raise 1 — the SPEC.md §41 XMS store | 70 KB | 66 KB |
| raise 2 — the SPEC.md §51 driver subsystem | 71 KB | 70.5 KB |
| raise 3 — SPEC.md §51.5's keyed `SYSTEM.CFG` | 75 KB | not recorded |
| raise 4 — SPEC.md §22.3/§22.4 Cut/Copy/Paste and the drag | 79 KB | not recorded |
| hard disks as a driver (§18.7/§18.8/§51.2.1) — budget **not** raised | 79 KB | 78.5 KB |
| `.lowbss` migration + 256-byte task stacks | 79 KB | 76.5 KB |
| ...and where it stands now | 79 KB | **76.5 KB** (78,336 B) |

The last row is the one to re-measure rather than trust: it moves with every
commit that adds code, and it is not the budget — it is what the budget is
being spent on. Above, "Where it goes" carries the same figure to the byte,
and the Task Manager's `System` row shows it live.

`docs/MEMORY-PLAN.md` is the narrative of how it got here, step by step, and
what was rejected along the way. This document is what it looks like now.

---

## Where the code goes

The 65,145 bytes of image, module by module, and one level down inside each.
Every byte is accounted for exactly once: the child rows of a module sum to
its `.text`, and the module rows sum to the total. Bold rows are `.text` +
`.bss` together; the child rows are `.text` unless italicised.

Read this before assuming where the weight is. Three results are worth
knowing before you go looking:

- **The file system is 30.4% of the kernel** — `disk` + `diskw` + `files` +
  `filecp` + `fdlg` + `loader` come to 19,804 bytes, two thirds again as much
  as the whole window system and its furniture. FAT12 is not a small thing to
  implement twice (read and write), and the Disk window is the largest single
  module in the tree.
- **The two utility windows are 15.0%** — the Task Manager and the Control
  Panel are 9,801 bytes between them, for two windows most sessions never
  open. That is what `.fartext` used to exist to hide, and with 391 bytes left
  under guard 2 it is now the first place to look.
- **The three built-in apps are 1.6%.** About, Clock and Bounce cost 1,046
  bytes together — moving Note Pad out to a package (SPEC.md §27) was worth
  ~1.4KB on its own, which is more than all three of these.

| theme | bytes | share |
|---|---:|---:|
| the file system, end to end | 19,804 | 30.4% |
| the window system and its furniture | 11,851 | 18.2% |
| hardware: clock, mouse, sound, CPU, XMS, drivers | 10,643 | 16.3% |
| the two utility windows | 9,801 | 15.0% |
| drawing: adapters, primitives, glyphs, icons | 8,361 | 12.8% |
| the kernel proper: scheduler, heap, API table | 3,761 | 5.8% |
| the three task-less built-ins | 924 | 1.4% |

<!-- BEGIN generated table -->
| | bytes | of image |
|---|---:|---:|
| **`files.inc`** — the Disk window (SPEC.md §22) | **6,489** | **10.0%** |
| &nbsp;&nbsp;&nbsp;&nbsp;drawing the content, status line and selection | 1,425 | |
| &nbsp;&nbsp;&nbsp;&nbsp;clicks, keys, hit-testing and context menus | 910 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the per-window view cache (§22.1) | 778 | |
| &nbsp;&nbsp;&nbsp;&nbsp;every string, error table and the template | 739 | |
| &nbsp;&nbsp;&nbsp;&nbsp;opening, navigating, titling | 609 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the menu set and its command handlers | 446 | |
| &nbsp;&nbsp;&nbsp;&nbsp;drag and drop | 429 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the in-place rename editor | 401 | |
| &nbsp;&nbsp;&nbsp;&nbsp;layout, scroll bar and geometry | 371 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the menu item tables | 72 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *309* | |
| **`taskmgr.inc`** — the Task Manager (§28) | **6,279** | **9.6%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the memory view: rows, figures, XMS line | 1,298 | |
| &nbsp;&nbsp;&nbsp;&nbsp;sampling: the history ring and per-instance cycles | 1,076 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the process view: rows, ordering, the CPU bar | 836 | |
| &nbsp;&nbsp;&nbsp;&nbsp;strings, the template and number formatting | 774 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the chunked row painter (§11.3) | 562 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the RAM map, its textures and legend squares | 529 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *1,204* | |
| **`wm.inc`** — the window manager (§11) | **4,619** | **7.1%** |
| &nbsp;&nbsp;&nbsp;&nbsp;drawing the frame, title bar and grow box | 850 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the clip region (§11.3) | 801 | |
| &nbsp;&nbsp;&nbsp;&nbsp;damage-rect repaint (§11.91) | 735 | |
| &nbsp;&nbsp;&nbsp;&nbsp;create, resize, destroy, fit and snap | 686 | |
| &nbsp;&nbsp;&nbsp;&nbsp;z-order: show, hide, front, fullscreen | 626 | |
| &nbsp;&nbsp;&nbsp;&nbsp;hit test, record access and `wm_pkgcall` | 398 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *523* | |
| **`diskw.inc`** — the FAT write path (§18.4-18.6) | **4,051** | **6.2%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the FAT, the directory entry and the commit | 852 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`dskw_rmtree` — recursive delete | 592 | |
| &nbsp;&nbsp;&nbsp;&nbsp;folders: mkdir, rmdir and the dot entries | 579 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`dskw_write` — the 32-bit write pipeline | 571 | |
| &nbsp;&nbsp;&nbsp;&nbsp;8.3 name parsing, timestamps and free space | 477 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`dskw_read` — the 32-bit read pipeline | 370 | |
| &nbsp;&nbsp;&nbsp;&nbsp;delete and rename | 261 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`dskw_append` | 221 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *128* | |
| **`clock.inc`** — the clock ladder (§37) | **3,660** | **5.6%** |
| &nbsp;&nbsp;&nbsp;&nbsp;rung 1 — MC146818 at 70h/71h | 722 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rung 3 — RP5C01/TC8521 at 2C0h | 698 | |
| &nbsp;&nbsp;&nbsp;&nbsp;formatting and the Date/Time field editor | 598 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rung 2 — MM58167 at 2C0h | 586 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the software calendar the tick advances | 376 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the ladder walk and its dispatch | 328 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rung 4 — int 1Ah | 263 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *89* | |
| **`ctrl.inc`** — the Control Panel (§31) | **3,522** | **5.4%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the Date/Time page and its field editor | 769 | |
| &nbsp;&nbsp;&nbsp;&nbsp;every label on all five pages | 679 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the page frame: list, divider, dispatch | 452 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the Sound page | 446 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the Drivers page | 399 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the Display page (and its greying test) | 380 | |
| &nbsp;&nbsp;&nbsp;&nbsp;radios, checkboxes and their glyphs | 225 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the Scheduler page | 128 | |
| &nbsp;&nbsp;&nbsp;&nbsp;writing SYSTEM.CFG back | 44 | |
| **`fdlg.inc`** — the Standard File dialog (§38) | **3,263** | **5.0%** |
| &nbsp;&nbsp;&nbsp;&nbsp;painting the dialog, its list and its buttons | 1,024 | |
| &nbsp;&nbsp;&nbsp;&nbsp;clicks | 571 | |
| &nbsp;&nbsp;&nbsp;&nbsp;keys and the name box | 519 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the window, the modal gate and completion | 399 | |
| &nbsp;&nbsp;&nbsp;&nbsp;list state, selection and scrolling | 291 | |
| &nbsp;&nbsp;&nbsp;&nbsp;New Folder | 241 | |
| &nbsp;&nbsp;&nbsp;&nbsp;strings and the window template | 124 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *94* | |
| **`disk.inc`** — volumes, mount and the FAT read path (§18-19) | **3,195** | **4.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`disk_mount` and the 17-rule BPB check | 966 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the volume table and the FAT window (§18.7/§18.8) | 789 | |
| &nbsp;&nbsp;&nbsp;&nbsp;synthesizing the listing, and sorting it | 426 | |
| &nbsp;&nbsp;&nbsp;&nbsp;cluster-chain walking and directory scan | 354 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the current directory and entry staging | 265 | |
| &nbsp;&nbsp;&nbsp;&nbsp;int 13h with retry | 188 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the drive geometry words | 8 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *199* | |
| **`driver.inc`** — loadable drivers + SYSTEM.CFG (§51) | **2,511** | **3.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;SYSTEM.CFG: the keyed record, read and write | 600 | |
| &nbsp;&nbsp;&nbsp;&nbsp;load, attach, detach, free | 587 | |
| &nbsp;&nbsp;&nbsp;&nbsp;driver-owned Control Panel pages and the block class (§51.2.1) | 435 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the boot pass and its notice | 322 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the published service table | 221 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the five failure strings | 144 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *202* | |
| **`filecp.inc`** — Cut/Copy/Paste (§22.3-22.5) | **2,126** | **3.3%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the recursive walk and its explicit stack | 737 | |
| &nbsp;&nbsp;&nbsp;&nbsp;copying one file, in buffer-sized chunks | 540 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the destination, and the move half of a Cut | 311 | |
| &nbsp;&nbsp;&nbsp;&nbsp;arming the clipboard, and refusing self-paste | 300 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the copy buffer claim | 105 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *133* | |
| **`vga12.inc`** — the VGA planar primitives (§5) | **2,049** | **3.1%** |
| &nbsp;&nbsp;&nbsp;&nbsp;fills: solid, 50% gray and patterned | 580 | |
| &nbsp;&nbsp;&nbsp;&nbsp;XOR overlays, VRAM-direct and clipped | 448 | |
| &nbsp;&nbsp;&nbsp;&nbsp;lines, pixels and the 4bpp blit | 390 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rect setup, the GC registers and the clip run | 302 | |
| &nbsp;&nbsp;&nbsp;&nbsp;save/restore (the cursor and menu save-under) | 213 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the pen, the disabled flag and the lock | 71 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *45* | |
| **`menu.inc`** — the menu bar and pull-downs (§12) | **2,012** | **3.1%** |
| &nbsp;&nbsp;&nbsp;&nbsp;tracking, the pull-down and its save-under | 775 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`menu_relayout` — rebuilding the bar | 589 | |
| &nbsp;&nbsp;&nbsp;&nbsp;drawing the bar, the logo and the clock | 426 | |
| &nbsp;&nbsp;&nbsp;&nbsp;ownership and Locator's own set | 129 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *93* | |
| **`instance.inc`** — instances and the built-in kinds (§29) | **1,941** | **3.0%** |
| &nbsp;&nbsp;&nbsp;&nbsp;launch, close and the two teardown paths | 521 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the built-in kind table and its six icons | 480 | |
| &nbsp;&nbsp;&nbsp;&nbsp;record bookkeeping | 249 | |
| &nbsp;&nbsp;&nbsp;&nbsp;a package's worker task, and its fence | 168 | |
| &nbsp;&nbsp;&nbsp;&nbsp;staging a package's icon on demand (SPEC.md §25) | 54 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *469* | |
| **`font.inc`** — the 8x8 text renderers (§6) | **1,908** | **2.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;one glyph: the VRAM and buffer renderers | 521 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`font_run` — erase-and-letter as one op | 491 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the ROM font handover | 70 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`font_str` and width | 49 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *777* | |
| **`snd.inc`** — the sound layer (§34) | **1,607** | **2.5%** |
| &nbsp;&nbsp;&nbsp;&nbsp;PC-speaker PCM and the blocking play | 513 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the route, and handing off to a driver | 255 | |
| &nbsp;&nbsp;&nbsp;&nbsp;tones | 229 | |
| &nbsp;&nbsp;&nbsp;&nbsp;grant ownership and the IRQ0 tick | 181 | |
| &nbsp;&nbsp;&nbsp;&nbsp;init and unhook | 130 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *299* | |
| **`ui.inc`** — the UI task and the event ladder (§13) | **1,582** | **2.4%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`ui_task` — the event ladder | 692 | |
| &nbsp;&nbsp;&nbsp;&nbsp;command dispatch | 321 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`ui_drag` and its XOR outline | 270 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`ui_grow` | 267 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *32* | |
| **`vgabb.inc`** — the software renderer / back buffer (§32, §39.5) | **1,563** | **2.4%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the software renderer (also *the* mono renderer) | 535 | |
| &nbsp;&nbsp;&nbsp;&nbsp;arming, seeding from VRAM and the flush | 428 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`gfx_scroll` and its two bank copiers | 363 | |
| &nbsp;&nbsp;&nbsp;&nbsp;save/restore into the buffer | 121 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the dirty rect | 89 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *27* | |
| **`memory.inc`** — the claim heap (§50) | **1,456** | **2.2%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`mem_claim` and the DMA-page-safe scan | 547 | |
| &nbsp;&nbsp;&nbsp;&nbsp;reporting for the Task Manager | 353 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`mem_regrow` and its block copy | 245 | |
| &nbsp;&nbsp;&nbsp;&nbsp;freeing, by block, owner and record | 158 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the API cells | 143 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *10* | |
| **`icons.inc`** — the icon renderer (§10) | **1,343** | **2.1%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the icon renderer, VRAM and buffer | 727 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the three built-in icons (floppy, hard disk, app) | 582 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *34* | |
| **`xmem.inc`** — memory above 1MB (§41.4-41.5) | **1,285** | **2.0%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the 286+ block move through a GDT | 528 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the pool and its allocator | 520 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the int 15h fallback | 113 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *124* | |
| **`kernel.asm`** — the API table, entry points and `kmain` | **1,270** | **1.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the API jump table and its X/N stubs | 1,052 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the three fixed entry points and `kmain` | 118 | |
| &nbsp;&nbsp;&nbsp;&nbsp;API bodies small enough to live here | 100 | |
| **`mouse.inc`** — serial mouse and the cursor (§9) | **1,256** | **1.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;drawing the cursor, colour and mono | 523 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the IRQ4 packet decoder | 312 | |
| &nbsp;&nbsp;&nbsp;&nbsp;COM port probe and hook | 167 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the arrow bitmap | 58 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *196* | |
| **`sched.inc`** — pre-emptive scheduling (§7-8) | **1,035** | **1.6%** |
| &nbsp;&nbsp;&nbsp;&nbsp;spawn, yield, sleep, exit | 286 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the switch itself, inside IRQ0 | 198 | |
| &nbsp;&nbsp;&nbsp;&nbsp;init and the int 08h hook | 194 | |
| &nbsp;&nbsp;&nbsp;&nbsp;cycle accounting and callback billing | 171 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the pre-empt/cooperative switch | 24 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *162* | |
| **`apps.inc`** — the three task-less built-ins (§16) | **924** | **1.4%** |
| &nbsp;&nbsp;&nbsp;&nbsp;Clock | 395 | |
| &nbsp;&nbsp;&nbsp;&nbsp;Bounce | 262 | |
| &nbsp;&nbsp;&nbsp;&nbsp;About | 258 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *9* | |
| **`desk.inc`** — the desktop and volume zones (§14/§26.1) | **887** | **1.4%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the volume zones, now one per mounted volume | 534 | |
| &nbsp;&nbsp;&nbsp;&nbsp;clicks on the bare desktop | 182 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the dithered background | 157 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *14* | |
| **`splash.inc`** — the boot splash (§15) | **862** | **1.3%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the bar, the percentage and the frame | 328 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the spinner and its cosine table | 268 | |
| &nbsp;&nbsp;&nbsp;&nbsp;its own primitives (it runs before `vga12`) | 266 | |
| **`loader.inc`** — the package loader (§20) | **680** | **1.0%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`ld_run_body` — claim, read, zero bss, enter | 428 | |
| &nbsp;&nbsp;&nbsp;&nbsp;header validation and the icon donation | 128 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the post slots the UI task drains | 66 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *58* | |
| **`viddet.inc`** — adapter detection and geometry (§39) | **636** | **1.0%** |
| &nbsp;&nbsp;&nbsp;&nbsp;probe, mode set and geometry publish | 438 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the per-adapter table and ink map | 138 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`gfx_rowbase`/`gfx_nextrow`/`gfx_ink` | 60 | |
| **`dock.inc`** — the dock (§30) | **542** | **0.8%** |
| &nbsp;&nbsp;&nbsp;&nbsp;painting tiles, and the two marks | 359 | |
| &nbsp;&nbsp;&nbsp;&nbsp;clicks and keys | 119 | |
| &nbsp;&nbsp;&nbsp;&nbsp;init | 35 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *29* | |
| **`cpudet.inc`** — CPU tiers and the A20 gate (§41.1-41.3) | **324** | **0.5%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the A20 gate: probe, KBC and fast paths | 222 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the 8086/286/386 tier test | 69 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the HMA claim | 33 | |
| **`events.inc`** — the event ring (§13.1) | **268** | **0.4%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`evq_pop` | 60 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`evq_push` | 55 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`evq_init` | 19 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *134* | |
| **total** | **65,145** | |
<!-- END generated table -->

### Reading it

A few of the rows say something that is not obvious from the size alone.

- **`clock.inc` is 3,660 bytes because it is four clocks.** Each rung of
  SPEC.md §37.90's ladder is a different chip with a different register
  layout, and three of them are 500–750 bytes apiece. Only one of the four
  can ever run on a given machine, and there is no way to know which until
  the probe has walked them — which is exactly why none of it could be
  loadable the way the sound tiers are.
- **`kernel.asm`'s own 1,270 bytes are almost entirely the API table.**
  Its slots × 8 bytes is 656 bytes of `push ds / push cs / pop ds / call /
  pop ds / retf`, plus 268 bytes of the longer X and N stubs. That is the
  price of a package living in its own segment (SPEC.md §20.1), and it is
  paid once rather than at every call site.
- **`font.inc`'s `.bss` is bigger than three quarters of its code.** The
  777 bytes are the ROM font staging and the `font_run` line buffer; the
  four renderers themselves are 1,131 bytes for what is, on a 1bpp adapter
  at a byte-aligned x, a single store per cell row (SPEC.md §6.1).
- **`instance.inc` no longer keeps a copy of every package's icon.** It used
  to hold 768 bytes of `.bss` — one 64-byte body per instance, staged at load
  time — while the original sat in the package's own region at the fixed
  header offset the whole time, living exactly as long as the instance that
  owned it. `I_ICON` is a sentinel now and `inst_icon_ptr` stages 64 bytes
  only when a dock tile is actually drawn (the `dsk_get_icon` idiom), which
  is what paid for hard-disk support. Its remaining 480 bytes of art are the
  six built-in kinds' own icons.
- **`splash.inc` pays 266 bytes for primitives that already exist.** It runs
  inside the first `SPL_RESIDENT` sectors, before `vga12.inc` is aboard, so
  it cannot call `gfx_*` and open-codes its own hline, vline and fill.
- **`dock.inc` is 544 bytes** and `events.inc` is 268 — the two smallest
  things with a name in SPEC.md. Not everything that has a chapter has a
  footprint.

### How to re-measure this

The table is generated, not maintained by hand, and both halves of it are
checkable:

1. **Per-module totals.** Insert a label into `.text`, `.bss` and `.lowbss`
   after each `%include` in `kernel/kernel.asm`, append a table of
   `dw` of those labels at the end of `.text`, assemble, and read the words
   back off the tail of the binary. Labels emit no bytes, so the measurement
   does not perturb what it measures — every offset before the appended table
   is identical to the shipped build. The module deltas must sum to
   `KTEXT_SIZE` / `KBSS_SIZE` / `KLOW_SIZE`, which is the check that the
   attribution is complete.
2. **Per-routine sizes.** Assemble with `-l` and take each label's address
   from the listing; a routine's size is the distance to the next label, and
   a module's routines are the ones whose addresses fall inside its span from
   step 1. Attribute by **address range**, not by the listing's `<1>` include
   markers — macro expansions are marked at include depth too, so tracking
   depth transitions walks off the end of the include list.

Both steps are throwaway; nothing in the tree needs to carry them. The
constants they check (`KTEXT_SIZE`, `KBSS_SIZE`, `KLOW_SIZE`, `KERN_SIZE`)
are the same ones the guards use, so a build that passes guard 1 already
agrees with the totals above.

---

## Moving data out of the segment, and where that stops

Guard 2 counts `.text` + `.bss`. It does **not** count `.lowbss`, which lives
in `LOW_SEG` and is reached through SS — so a table moved from one to the
other costs the kernel nothing in RAM and hands its whole size back to the
binding guard. `SS` is `LOW_SEG` from `kmain` onwards and never changes
again, so the access is an `ss:` prefix with no register to set up, nothing
to save and restore, and no ordering hazard: one byte and about two cycles
per field.

Four objects made the trip. What decides it is not size but **how many places
dereference the pointer**, which is not the same question as how many places
take its address:

| object | bytes | `ss:` prefixes | net | where |
|---|---:|---:|---:|---|
| `mem_tab` | 256 | 64 | **+192** | `memory.inc` only |
| `app_ball_pool` | 80 | 16 | **+64** | `apps.inc` only |
| `app_clk_pool` | 80 | 21 | **+59** | `apps.inc` only |
| `menu_bar` | 84 | 34 | **+50** | `menu.inc` only |

Three that were candidates on size alone did not go, and the reasons are
worth keeping:

- **`fm_pool` (80 B) is a net loss.** `[fm_vp]` points into it and the Disk
  window dereferences that pointer 111 times, so the prefixes cost more than
  the table is worth. Bytes-per-dereference is the metric, not bytes.
- **`inst_tab` (384 B) is entangled, not merely expensive.** Its 115 field
  accesses are only the visible half: `I_NAME` is handed out as an ordinary
  near string pointer — a Disk window's `W_TITLE` aims *into* the record
  (`files.inc`), and the dock, the menu bar and the Task Manager all letter it
  through DS. Moving the table would need a segment beside every one of those
  pointers, which is exactly the `MB_SEG` trap of SPEC.md §12.2. This was
  tried, and it failed the way that trap always does: the build was clean and
  the machine booted to a desktop that could not launch anything.
- **`font_glyphs` (760 B) is the largest candidate left and is ABI-blocked.**
  `OSAPI_FONT_GLYPHS` publishes it as an offset in `KERNEL_SEG`, and SPEC.md
  §20.8 rule 4 says a shipped slot keeps its contract. Exactly one package
  reads it (Paint), so a recorded one-time amendment — the slot answering with
  a segment as well — would free more than the four objects above put
  together. `snd_xlat` (256 B) is a different refusal: only two sites, but
  they are `spk_pcm_run`'s per-sample loop, where a prefix is not free.

**The trap this sprang, and the one to expect next time.** A field-offset
regex finds `[di+I_STATE]`; it does not find `add di, I_NAME` followed by a
bare `[di]`, and it does not find a `rep stosb` whose ES was set with
`push ds / pop es`. Both exist, both assemble, and both write to the wrong
segment at run time. Every migration here had to be checked for three shapes,
not one: field accesses, bare dereferences of an advanced pointer, and string
operations whose segment register is set from DS.

---

## What hard-disk support cost, and what paid for it

Adding the volume table, the FAT window, driver-owned Control Panel pages and
volume-driven desktop zones (SPEC.md §18.7, §18.8, §26.1, §31.9, §51.2.1) took
about 1,700 bytes of `.text`. It overran **guard 2** — `.text` + `.bss` inside
one 64KB segment — which is the 16-bit offset and cannot be raised at any
price.

**What paid for it was the per-instance icon table**: 768 bytes of `.bss`
holding a COPY of each loaded package's 16x16 icon body, made at load time.
The original was in the package's own region the whole time, at the fixed
offset every package header puts it at, and it lives exactly as long as the
instance that owns it — so the copy was pure duplication. `I_ICON` is a
sentinel now and `inst_icon_ptr` stages 64 bytes when a dock tile is actually
drawn, which is the `dsk_get_icon` idiom and costs nothing on any path that
does not draw one.

The FAT window itself cost **no memory at all**: `FAT_SEG` is the same 4,608
bytes it always was, and only its meaning changed.

Then the driver's *settings* moved into the kernel's file, which cost 254
bytes more and is the least intuitive line here — the point of it was to make
the driver's boot path **cheaper**, and it did (a `rep movsb` instead of two
volume remounts, a directory search and a read), but the memory went the other
way. `DRV_BLOB_SZ` = 34 bytes of `.bss` for the blob, 38 more of `drv_cfgbuf`
for its record in the file, and about 180 of `.text` for the slot, its stub
and the fence. All of it is reserved on **every** machine, including a 128KB
one with no hard disk — that is the honest cost of not making the one file the
boot already reads into two, and it is why one blob is shared by whichever
driver asks rather than one being reserved per class.

Eleven of those bytes came back by making `CFG_FBUF` **derived** rather than
chosen: the keys tile the settings struct exactly, so the file's length is
`CFG_REC0 + CFG_NKEY * CFR_HDR + CFG_NB + 2` and there is nothing to round up.
Slack in a buffer whose exact size is an expression anyone can evaluate is
`.bss` nothing can ever use.

Where that leaves the two guards, on this build:

```
guard 2  .text + .bss   65,145 / 65,536     391 bytes
guard 1  KERN_SIZE      78,336 / 80,896   2,560 bytes
```

`KERN_BUDGET` was **not** raised for any of this. **Guard 2 is still the binding
one**, and it is the one that cannot be raised at any
price — so the next feature that wants kernel `.text` or `.bss` should expect
to find its own 768-byte icon table before it starts, not afterwards. The
measured candidates, in the order they pay: the Task Manager and the Control
Panel (9,801 bytes, and the only lever big enough to change the situation
rather than postpone it), the clock's probe-and-read ladder (about 1,700, and
boot-only by construction), and the bulk `.bss` arrays that are walked through
a pointer rather than addressed by name (about 1,100).
