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
includes its buffers.** The span is `KERN_BUDGET` bytes — 72.5KB today, and
64KB for as long as that was affordable (see below). It currently runs
0x00600 through 0x11FFF, and the budget's ceiling is 0x12800.

Not the code and then some scratch elsewhere: *everything*. Code, read-only
data, `.bss`, the FAT window, the directory and icon caches, the sector
buffer and every task stack are one contiguous span starting at
`KERNEL_SEG`. The **`KERN_BUDGET`** guard in `kernel/kernel.asm` measures
that whole span and fails the build if it is over.

**The two guards are named, not numbered**, and if you have read an older
copy of this file or an older commit message they were "guard 1" and "guard
2". The numbering was the reason the distinction kept getting lost, because
nothing about "1" and "2" says which is which:

| name | what it bounds | can it be raised? |
|---|---|---|
| **`KERN_BUDGET`** | the **footprint** — this whole span, RAM taken from the machine | yes, by asking (see below) |
| **`KERN_CODE_MAX`** | the **segment** — `.text` + `.bss` in one 64KB window | **no.** It is what a 16-bit offset reaches |

They are relieved by different things, and that is the distinction that
matters in practice: the boot overlay (SPEC.md §2.5) and the cold segment
(SPEC.md §2.6) buy room against `KERN_CODE_MAX` and **nothing at all**
against `KERN_BUDGET` — overlay code is still read off the disk into the FAT
window, cold code is still resident. Moving a module cold to fix a footprint
overrun is a no-op that looks like a fix.

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

### The five moves

`KERN_BUDGET` was 65,536 — the first 64KB above the BIOS data area, which is
where the "one region" rule came from. It has moved five times; the four
raises were each asked for and granted, and the fifth move is the first one
downward:

| | budget | bought |
|---|---:|---|
| 1 | 65,536 → **71,680** (70KB) | the SPEC.md §41 extended-memory store, and the two API surfaces that came with it (`wm_geom`, `wm_about_set`) |
| 2 | 71,680 → **72,704** (71KB) | the loadable sound driver (SPEC.md §51) and the Control Panel pages that drive it |
| 3 | 72,704 → **76,800** (75KB) | SPEC.md §51.5's keyed `SYSTEM.CFG` — a settings file where nothing is positional costs a key table, a bounded record walker and a writer |
| 4 | 76,800 → **80,896** (79KB) | the file manager's Cut/Copy/Paste, its recursive paste engine and the drag (SPEC.md §22.3/§22.4) |
| 5 | 80,896 → **74,240** (72.5KB) | *nothing — this one gives back.* The optimisation passes after raise 4 (the Task Manager to the system disk, the Control Panel cold, the clock ladder and the glyph table out) left the kernel at 72,192 with **8,704 bytes** of budget above it. Slack that large is the guard switched off: any addition short of 8KB passed without the conversation this constant exists to force. 74,240 leaves 2,048 — enough that a bug fix does not trip it, small enough that a feature does. It frees **no RAM**, and is not meant to: `HEAP_SEG` is `KERN_END`, so the heap always started where the kernel actually ends. The slack was costing scrutiny, not memory |

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

### `KERN_BUDGET` is what binds, and now decisively

`.text` + `.bss` are addressed through one segment with 16-bit offsets, so
`KERN_CODE_MAX` caps them at 65,536 **whatever the budget says**. That limit
is untouched and cannot be raised at all.

For most of this project's life the budget was the tighter of the two, which
is the intended order — a budget is a decision and a segment is physics. That
stopped being true when hard-disk support took the segment to 71 bytes free,
and it is true again, by a wide margin, now that the budget has come down to
72.5KB:

| | headroom |
|---|---:|
| `KERN_CODE_MAX`, the segment | 10,434 B for `.text` + `.bss` |
| **`KERN_BUDGET`, the footprint** | **2,048 B** for the whole span |

So the next thing to hit is a conversation about `KERN_BUDGET`, and it will
be hit early rather than after 9KB of unexamined growth. The segment used to
run out first, and hard-disk support (below) is what took it to 71 bytes; the
`.lowbss` migration, the halved stacks, the boot overlay, the cold segment
and finally moving the Task Manager out to a package (SPEC.md §28) are what
bought it back — 71 bytes to 11,559 across those five, spent back down to
10,434 by the copy pipeline, the per-volume FAT windows (§18.9/§18.8.1), the
review fixes and the mouse hot-plug poller that followed them.

The two are also coupled through the rounding, and that coupling is
load-bearing in both directions. **The image rung was pinned at 65,536 bytes
— the segment maximum exactly — for as long as the segment was full**, and
while it was, the budget's spare could not be spent on code at any price;
only the buffers and stacks reached it. And a byte moved from `.bss` to
`.lowbss` helps `KERN_CODE_MAX` but *hurts* `KERN_BUDGET` until the image
falls far enough to drop a 512-byte step: when the `.lowbss` rung is full,
the very first byte moved costs a whole step. That is why the migration below
and the stack halving had to land together — the first was not affordable
without the second. With only 2,048 bytes of budget spare, that direction
matters again: **moving data out of the segment is no longer free**, and four
512-byte steps is the whole of the remaining headroom.

---

## Where it goes

Measured on the shipped build. `make` prints the image size; the rest come
out of the same constants the guards use.

| region | size | what it is |
|---|---:|---|
| image (`.text` + `.bss`) | 55,296 B | all kernel code, its read-only data, and its scratch |
| task stacks | 3,840 B | 11 background slots of 256 B + task 0's 1,024 |
| `.lowbss` tables | 1,268 B | the glyph table, `mem_tab`, `menu_bar` and the two built-in state pools |
| cold code | 3,584 B | the Control Panel's 3,074 bytes of code, resident but in a segment of its own |
| the boot overlay | 0 B | 2,504 bytes of code inside the FAT window, gone by the first mount |
| disk buffers | 3,584 B | directory cache, icon cache, sector scratch |
| FAT window | 4,608 B | nine of the mounted volume's FAT sectors (SPEC.md §18.8) — the whole FAT on any floppy, a sliding window on a hard disk |
| **total** | **72,192 B** | of a 74,240-byte budget — 2,048 B spare |

The image rung is `.text` (51,623) + `.bss` (3,479) = 55,102, rounded up to a
whole 512 bytes; the 194-byte remainder is the only slack anywhere in the
ladder, and it is a rounding artefact rather than a reservation. **The rung
is no longer pinned at the segment maximum** — it was, from hard-disk support
until the Task Manager left, and while it was, the budget's spare could not
be spent on code at any price.

The ladder lands on these segments: `KERNEL_SEG` 0x0060, `COLD_SEG` 0x0DE0,
`FAT_SEG` 0x0EC0, `LOW_SEG` 0x0FE0, `HEAP_SEG` 0x1200.

**The cold rung is where the rounding last bit.** The Drivers-page fix added
seventeen bytes of `ctrl.inc` — 3,057 → 3,074 — which crossed the 3,072
boundary and moved the rung 3,072 → 3,584. Seventeen bytes of code, 512 bytes
of footprint. With 2,048 bytes of budget spare that is a quarter of the
headroom, and it is the clearest available demonstration of why a rung step
is the unit to reason in rather than a byte count.

Everything above that is the claim heap, up to whatever int 12h reports. The
arithmetic is exact and worth writing down, because every RAM figure in this
project falls out of it:

> **heap KB = what int 12h reports − 71.5**

`KERN_END` is 4,576 paragraphs = 73,216 bytes = 71.5KB, and the heap starts
there. Checked against a live machine: QEMU with `-m 1M` reports **639KB**
and the Task Manager shows **567KB** of heap. Re-derive this after
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
| 80KB | 7KB | would boot, full desktop, browses both floppies, **loads a package** (`hello`) — except that the boot floor above bites first, so the first machine that actually runs is 85KB, with 14KB of heap |
| 96KB | 23KB | Note Pad runs. Paint loads and puts up its "Not enough memory" notice — the designed tier, not a crash |
| 160KB | 87KB | Paint still gets the notice |
| 176KB | 103KB | **Paint runs live**, full 448×280 canvas |
| 640KB | 568KB | everything, including the 150KB back buffer |

So the honest floor is **85KB to boot and load something** — the boot
sector's landing zone, not the heap's — and **~176KB for every shipped app at
full function**. The often-quoted "128KB" sits between those: it runs the OS
and most of the packages, and Paint declines.

Those thresholds are properties of the **heap**, not of the machine, so the
RAM column moves by exactly whatever `KERN_END` moves. It has moved back:
before raises 3 and 4 this table read exactly these figures, raises 3 and 4
plus hard-disk support pushed every row up 5KB, and the Task Manager leaving
the kernel handed all of it back. **The outcome column was measured boot by
boot** with `mem_init` clamped; the RAM column is those measurements
re-derived onto today's `KERN_END`.

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
RAM  69/639K [] HEAP   0/568K       <- the map's caption, both figures
[==============================]    <- every byte the machine has
XMS   0/64448K                      <- and what it has no address for
[==============================]
```

Its four buffer rows read `Code+data 56K`, `Stacks 4K`, `Disk bufs 4K` and
`FAT snap 5K` against a `System` row of `69K`, and they sum to it **exactly**.
That is a property, not a coincidence: every rung of the ladder is a whole
number of 512-byte sectors, so half of them are an odd half-kilobyte and four
independently rounded parts can lose two kilobytes against a total that rounds
once — so `SK_IMG` and `SK_DSK` are residuals and absorb it (SPEC.md §20.9).
The rows used to sum to one more than `System` for exactly that reason, and
then to three *less*, once the cold segment was inside the span and in none of
the parts.

The figures themselves come from `OSAPI_SYS_KB` now rather than from
assembly-time constants of the kernel's own, because the window is a package
and the kernel's footprint moves with every build.

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

### The image — `.text` 50,540 B + `.bss` 3,437 B

One flat binary at `KERNEL_SEG:0000`, assembled `-f bin` with no linker.
`.bss` follows `.text` immediately and is uninitialised by definition, so it
costs nothing on the floppy and everything in RAM. Where every one of those
bytes goes is the last section of this document.

The ladder charges the pair **rounded up to a whole 512 bytes** (see the
alignment invariant below) — 55,296 B, so 386 bytes of the rung are rounding
remainder.

**The file on disk runs past that rung**, and the gap is not padding for its
own sake — it is where the boot overlay lives (below). `.bss` is nobits, so
`kernel.bin` used to be `.text` alone and the boot sector's contiguous read
landed sector K at offset K·512, somewhere inside `.bss` rather than at the
paragraph the ladder calls `FAT_SEG`. Declaring the overlay as a section with
`start=OVL_START` closes that gap: NASM emits the space between `.text` and
the rung as zeros, so the overlay lands exactly on `FAT_SEG` in the boot
sector's existing single read — no second loop, no gap constant, and
`KERNEL_SECTORS` still falls out of the file size.

The padding is not wasted either. **The whole of `.bss` is now zeroed before
`kmain` runs**, which nothing previously did — `nasm -f bin` zeroes nothing,
which is why `[fdlg_win]` has to live in `.text` as a `dw 0` (`fdlg_grab`
reads it on the machine's very first mouse press). The splash is safe through
it: `viddet` and `splash` keep all their data in `.text` precisely because
they run during the load.

Expressing it as a section start is what makes it non-circular. Padding
*inside* `.text` would grow `KTEXT_SIZE`, which grows `KIMG_PARA`, which grows
the padding, and there is no fixed point; `.ovl`'s own size is not one of the
terms in `OVL_START`, so there is nothing to converge. Measure the unrounded pair by appending `section .text` /
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

**The QEMU probe understates a real BIOS.** SeaBIOS services its interrupt
entries on an internal extra stack, so under `make test` the only foreign
frames a task slice ever carries are this kernel's own tick and mouse
handlers. A real IBM BIOS runs int 09h — which it STIs early, so the tick
and the mouse nest *on top of* it — and its int 08h chain on whichever task
stack is current. `tests/stackprobe` exists for exactly this gap: it fills
its own worker's slice from the inside and reports the high-water mark and
canary state live, so the 256-byte figure can be re-checked on the machine
it actually protects. Boot the 360KB pair on real iron (or `make xt`), run
`STKPROBE.O88` off its test floppy, and hammer the keyboard and mouse while
it counts (docs/TESTING.md).

**And it has been run there.** On a real 5150 (640K, Hercules, a 20MB MFM
disk through its controller ROM) with a floppy-to-hard-disk copy running,
the keyboard mashed for typematic and the mouse in motion, 217 samples over
~2 minutes read **112 of 256, canary intact** — against 92 for the same
probe under QEMU, so the real BIOS's interrupt nesting costs ~20 bytes the
emulator cannot show. The probe's own frames are ~30 of that 112, putting
the pure ISR + switch component near 82; add the deepest *application*
depth the 0xCC fills have ever recorded (~80, the Fractal/Tracker workers)
and the projected real-hardware worst case is ~160–170 of 256 — a ~1.6×
margin, with `SCH_MAGIC` still underneath it. The halving stands.

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
| the glyph table follows it out (§6/§20.3) | 79 KB | 76 KB |
| the boot overlay: the image padded to its rung, four boot-only routines out | 79 KB | 76.5 KB |
| the clock's probe-and-read ladder follows them (§37.90) | 79 KB | 74 KB |
| the Control Panel's code into a cold segment (§2.6) | 79 KB | 74 KB |
| four API cells for what only the kernel could see (§20.9) | 79 KB | 76 KB |
| the Task Manager becomes a package on the system disk (§28) | 79 KB | 69 KB |
| selecting a covered drive icon costs a strip of XOR (§26.1) | 79 KB | 69 KB |
| the copy pipeline, write runs and a FAT window per volume (§18.9/§18.8.1/§22.5) | 79 KB | 69.5 KB |
| the review fixes: park banks unconditionally, ES discipline, floor guards | 79 KB | 69.5 KB |
| the elendilon merge: paste and zone-grid repaints, Arkanoid pause | 79 KB | 70 KB |
| the mouse reset edge and hot-plug poller; the Drivers page's "stop asking" | 79 KB | 70.5 KB |
| the guards renamed, and `KERN_BUDGET` lowered onto the kernel (move 5) | **72.5 KB** | 70.5 KB |
| ...and where it stands now | 72.5 KB | **70.5 KB** (72,192 B) |

The last row is the one to re-measure rather than trust: it moves with every
commit that adds code, and it is not the budget — it is what the budget is
being spent on. Above, "Where it goes" carries the same figure to the byte,
and the Task Manager's `System` row shows it live.

`docs/MEMORY-PLAN.md` is the narrative of how it got here, step by step, and
what was rejected along the way. This document is what it looks like now.

---

## Where the code goes

The 54,910 bytes of image, module by module, and one level down inside each.
Every byte is accounted for exactly once: the child rows of a module sum to
its `.text`, and the module rows sum to the total. Bold rows are `.text` +
`.bss` together; the child rows are `.text` unless italicised.

Read this before assuming where the weight is. Three results are worth
knowing before you go looking:

- **The file system is 37.6% of the kernel** — `disk` + `diskw` + `files` +
  `filecp` + `fdlg` + `loader` come to 20,647 bytes, half again as much as the
  whole window system and its furniture. FAT12 is not a small thing to
  implement twice (read and write), and the Disk window is the largest single
  module in the tree.
- **The Control Panel is 1.3%, and that is the whole point of a cold
  segment** — its 689 bytes here are strings and tables; its 3,057 bytes of
  code are resident but outside the segment (SPEC.md §2.6). The Task Manager
  used to sit beside it at 6,279 and is not in this table at all any more: it
  is a package on the system disk (SPEC.md §28), which took the same weight
  off *both* guards instead of one.
- **The three built-in apps are 1.7%.** About, Clock and Bounce cost 924
  bytes together — moving Note Pad out to a package (SPEC.md §27) was worth
  ~1.4KB on its own, which is more than all three of these.

| theme | bytes | share |
|---|---:|---:|
| the file system, end to end | 20,647 | 37.6% |
| the window system and its furniture | 12,591 | 22.9% |
| hardware: clock, mouse, sound, CPU, XMS, drivers | 8,272 | 15.1% |
| drawing: adapters, primitives, glyphs, icons | 7,649 | 13.9% |
| the kernel proper: scheduler, heap, API table | 4,138 | 7.5% |
| the three task-less built-ins | 924 | 1.7% |
| the Control Panel (its code is cold) | 689 | 1.3% |

<!-- BEGIN generated table -->
| | bytes | of image |
|---|---:|---:|
| **`files.inc`** — the Disk window (SPEC.md §22) | **6,668** | **12.1%** |
| &nbsp;&nbsp;&nbsp;&nbsp;drawing the content, status line and selection | 1,425 | |
| &nbsp;&nbsp;&nbsp;&nbsp;clicks, keys, hit-testing and context menus | 910 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the per-window view cache (§22.1) | 948 | |
| &nbsp;&nbsp;&nbsp;&nbsp;every string, error table and the template | 739 | |
| &nbsp;&nbsp;&nbsp;&nbsp;opening, navigating, titling | 609 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the menu set and its command handlers | 446 | |
| &nbsp;&nbsp;&nbsp;&nbsp;drag and drop | 429 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the in-place rename editor | 401 | |
| &nbsp;&nbsp;&nbsp;&nbsp;layout, scroll bar and geometry | 371 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the menu item tables | 72 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *318* | |
| **`wm.inc`** — the window manager (§11) | **4,675** | **8.5%** |
| &nbsp;&nbsp;&nbsp;&nbsp;drawing the frame, title bar and grow box | 850 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the clip region (§11.3) | 857 | |
| &nbsp;&nbsp;&nbsp;&nbsp;damage-rect repaint (§11.91) | 735 | |
| &nbsp;&nbsp;&nbsp;&nbsp;create, resize, destroy, fit and snap | 686 | |
| &nbsp;&nbsp;&nbsp;&nbsp;z-order: show, hide, front, fullscreen | 626 | |
| &nbsp;&nbsp;&nbsp;&nbsp;hit test, record access and `wm_pkgcall` | 398 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *523* | |
| **`diskw.inc`** — the FAT write path (§18.4-18.6) | **4,238** | **7.7%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the FAT, the directory entry and the commit | 852 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`dskw_rmtree` — recursive delete | 592 | |
| &nbsp;&nbsp;&nbsp;&nbsp;folders: mkdir, rmdir and the dot entries | 579 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`dskw_write` — the 32-bit write pipeline | 750 | |
| &nbsp;&nbsp;&nbsp;&nbsp;8.3 name parsing, timestamps and free space | 477 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`dskw_read` — the 32-bit read pipeline | 370 | |
| &nbsp;&nbsp;&nbsp;&nbsp;delete and rename | 261 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`dskw_append` | 221 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *136* | |
| **`disk.inc`** — volumes, mount and the FAT read path (§18-19) | **3,570** | **6.5%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`disk_mount` and the 17-rule BPB check | 970 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the volume table and the FAT window (§18.7/§18.8) | 1,083 | |
| &nbsp;&nbsp;&nbsp;&nbsp;synthesizing the listing, and sorting it | 426 | |
| &nbsp;&nbsp;&nbsp;&nbsp;cluster-chain walking and directory scan | 354 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the current directory and entry staging | 320 | |
| &nbsp;&nbsp;&nbsp;&nbsp;int 13h with retry | 188 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the drive geometry words | 8 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *221* | |
| **`fdlg.inc`** — the Standard File dialog (§38) | **3,263** | **5.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;painting the dialog, its list and its buttons | 1,024 | |
| &nbsp;&nbsp;&nbsp;&nbsp;clicks | 571 | |
| &nbsp;&nbsp;&nbsp;&nbsp;keys and the name box | 519 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the window, the modal gate and completion | 399 | |
| &nbsp;&nbsp;&nbsp;&nbsp;list state, selection and scrolling | 291 | |
| &nbsp;&nbsp;&nbsp;&nbsp;New Folder | 241 | |
| &nbsp;&nbsp;&nbsp;&nbsp;strings and the window template | 124 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *94* | |
| **`driver.inc`** — loadable drivers + SYSTEM.CFG (§51) | **2,470** | **4.5%** |
| &nbsp;&nbsp;&nbsp;&nbsp;SYSTEM.CFG: the keyed record, read and write | 600 | |
| &nbsp;&nbsp;&nbsp;&nbsp;load, attach, detach, free | 546 | |
| &nbsp;&nbsp;&nbsp;&nbsp;driver-owned Control Panel pages and the block class (§51.2.1) | 435 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the boot pass and its notice | 322 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the published service table | 221 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the five failure strings | 144 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *202* | |
| **`filecp.inc`** — Cut/Copy/Paste (§22.3-22.5) | **2,228** | **4.1%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the recursive walk and its explicit stack | 737 | |
| &nbsp;&nbsp;&nbsp;&nbsp;copying one file, in buffer-sized chunks | 595 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the destination, and the move half of a Cut | 311 | |
| &nbsp;&nbsp;&nbsp;&nbsp;arming the clipboard, and refusing self-paste | 306 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the copy buffer claim | 144 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *135* | |
| **`ui.inc`** — the UI task and the event ladder (§13) | **2,154** | **3.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`ui_task` — the event ladder | 713 | |
| &nbsp;&nbsp;&nbsp;&nbsp;command dispatch | 321 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`ui_drag` and its XOR outline | 270 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`ui_grow` | 267 | |
| &nbsp;&nbsp;&nbsp;&nbsp;loading the Task Manager, and the notice when it will not (§28) | 551 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *32* | |
| **`instance.inc`** — instances and the built-in kinds (§29) | **2,095** | **3.8%** |
| &nbsp;&nbsp;&nbsp;&nbsp;launch, close and the two teardown paths | 521 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the built-in kind table and its five icons | 400 | |
| &nbsp;&nbsp;&nbsp;&nbsp;record bookkeeping | 249 | |
| &nbsp;&nbsp;&nbsp;&nbsp;a package's worker task, and its fence | 168 | |
| &nbsp;&nbsp;&nbsp;&nbsp;staging a package's icon on demand (SPEC.md §25) | 54 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`osapi_sys_snapshot` — one cli window over two tables (§20.9) | 234 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *469* | |
| **`vga12.inc`** — the VGA planar primitives (§5) | **2,090** | **3.8%** |
| &nbsp;&nbsp;&nbsp;&nbsp;fills: solid, 50% gray and patterned | 613 | |
| &nbsp;&nbsp;&nbsp;&nbsp;XOR overlays, VRAM-direct and clipped | 448 | |
| &nbsp;&nbsp;&nbsp;&nbsp;lines, pixels and the 4bpp blit | 390 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rect setup, the GC registers and the clip run | 302 | |
| &nbsp;&nbsp;&nbsp;&nbsp;save/restore (the cursor and menu save-under) | 213 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the pen, the disabled flag and the lock | 71 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *53* | |
| **`menu.inc`** — the menu bar and pull-downs (§12) | **2,017** | **3.7%** |
| &nbsp;&nbsp;&nbsp;&nbsp;tracking, the pull-down and its save-under | 775 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`menu_relayout` — rebuilding the bar | 589 | |
| &nbsp;&nbsp;&nbsp;&nbsp;drawing the bar, the logo and the clock | 426 | |
| &nbsp;&nbsp;&nbsp;&nbsp;ownership and Locator's own set | 134 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *93* | |
| **`clock.inc`** — the clock ladder (§37) | **1,872** | **3.4%** |
| &nbsp;&nbsp;&nbsp;&nbsp;formatting and the Date/Time field editor | 560 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the software calendar the tick advances | 376 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rung 3 — RP5C01/TC8521 at 2C0h | 276 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rung 1 — MC146818 at 70h/71h | 254 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rung 2 — MM58167 at 2C0h | 179 | |
| &nbsp;&nbsp;&nbsp;&nbsp;rung 4 — int 1Ah | 82 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the ladder walk and its dispatch | 56 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *89* | |
| **`memory.inc`** — the claim heap (§50) | **1,583** | **2.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`mem_claim` and the DMA-page-safe scan | 547 | |
| &nbsp;&nbsp;&nbsp;&nbsp;reporting for the Task Manager | 353 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`mem_regrow` and its block copy | 245 | |
| &nbsp;&nbsp;&nbsp;&nbsp;freeing, by block, owner and record | 158 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the API cells | 143 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the claim and footprint snapshot cells (§20.9) | 127 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *10* | |
| **`vgabb.inc`** — the software renderer / back buffer (§32, §39.5) | **1,563** | **2.8%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the software renderer (also *the* mono renderer) | *535* | |
| &nbsp;&nbsp;&nbsp;&nbsp;arming, seeding from VRAM and the flush | 428 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`gfx_scroll` and its two bank copiers | 363 | |
| &nbsp;&nbsp;&nbsp;&nbsp;save/restore into the buffer | 121 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the dirty rect | 89 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *27* | |
| **`kernel.asm`** — the API table, entry points, `kmain` and the segment shims | **1,520** | **2.8%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the API jump table and its X/N stubs | 1,104 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the cold/overlay shims and the Control Panel thunks | 158 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the three fixed entry points, `kmain` and the overlay shims | 155 | |
| &nbsp;&nbsp;&nbsp;&nbsp;API bodies small enough to live here | 103 | |
| **`snd.inc`** — the sound layer (§34) | **1,500** | **2.7%** |
| &nbsp;&nbsp;&nbsp;&nbsp;PC-speaker PCM and the blocking play | 513 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the route, and handing off to a driver | 255 | |
| &nbsp;&nbsp;&nbsp;&nbsp;tones | 229 | |
| &nbsp;&nbsp;&nbsp;&nbsp;grant ownership and the IRQ0 tick | 181 | |
| &nbsp;&nbsp;&nbsp;&nbsp;init and unhook | 23 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *299* | |
| **`icons.inc`** — the icon renderer (§10) | **1,343** | **2.4%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the icon renderer, VRAM and buffer | 727 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the three built-in icons (floppy, hard disk, app) | 582 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *34* | |
| **`mouse.inc`** — serial mouse and the cursor (§9) | **1,256** | **2.3%** |
| &nbsp;&nbsp;&nbsp;&nbsp;drawing the cursor, colour and mono | 523 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the IRQ4 packet decoder | 312 | |
| &nbsp;&nbsp;&nbsp;&nbsp;COM port probe and hook | 167 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the arrow bitmap | 58 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *196* | |
| **`xmem.inc`** — memory above 1MB (§41.4-41.5) | **1,164** | **2.1%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the 286+ block move through a GDT | 528 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the pool and its allocator | 399 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the int 15h fallback | 113 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *124* | |
| **`font.inc`** — the 8x8 text renderers (§6) | **1,155** | **2.1%** |
| &nbsp;&nbsp;&nbsp;&nbsp;one glyph: the VRAM and buffer renderers | 525 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`font_run` — erase-and-letter as one op | 476 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the ROM font handover and the blank cell | 80 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`font_str` and width | 57 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *17* | |
| **`sched.inc`** — pre-emptive scheduling (§7-8) | **1,035** | **1.9%** |
| &nbsp;&nbsp;&nbsp;&nbsp;spawn, yield, sleep, exit | 286 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the switch itself, inside IRQ0 | 198 | |
| &nbsp;&nbsp;&nbsp;&nbsp;init and the int 08h hook | 194 | |
| &nbsp;&nbsp;&nbsp;&nbsp;cycle accounting and callback billing | 171 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the pre-empt/cooperative switch | 24 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *162* | |
| **`apps.inc`** — the three task-less built-ins (§16) | **924** | **1.7%** |
| &nbsp;&nbsp;&nbsp;&nbsp;Clock | 395 | |
| &nbsp;&nbsp;&nbsp;&nbsp;Bounce | 262 | |
| &nbsp;&nbsp;&nbsp;&nbsp;About | 258 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *9* | |
| **`splash.inc`** — the boot splash (§15) | **862** | **1.6%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the bar, the percentage and the frame | 328 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the spinner and its cosine table | 268 | |
| &nbsp;&nbsp;&nbsp;&nbsp;its own primitives (it runs before `vga12`) | 266 | |
| **`desk.inc`** — the desktop and volume zones (§14/§26.1) | **840** | **1.5%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the volume zones, now one per mounted volume | 581 | |
| &nbsp;&nbsp;&nbsp;&nbsp;clicks on the bare desktop | 182 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the dithered background | 62 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *15* | |
| **`ctrl.inc`** — the Control Panel (§31) — code is COLD | **689** | **1.3%** |
| &nbsp;&nbsp;&nbsp;&nbsp;every label on all five pages | 519 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the page frame: list, divider, dispatch | 91 | |
| &nbsp;&nbsp;&nbsp;&nbsp;radios, checkboxes and their glyphs | 51 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the Sound page | 28 | |
| **`loader.inc`** — the package loader (§20) | **680** | **1.2%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`ld_run_body` — claim, read, zero bss, enter | 428 | |
| &nbsp;&nbsp;&nbsp;&nbsp;header validation and the icon donation | 128 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the post slots the UI task drains | 66 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *58* | |
| **`viddet.inc`** — adapter detection and geometry (§39) | **636** | **1.2%** |
| &nbsp;&nbsp;&nbsp;&nbsp;probe, mode set and geometry publish | 438 | |
| &nbsp;&nbsp;&nbsp;&nbsp;the per-adapter table and ink map | 138 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`gfx_rowbase`/`gfx_nextrow`/`gfx_ink` | 60 | |
| **`dock.inc`** — the dock (§30) | **542** | **1.0%** |
| &nbsp;&nbsp;&nbsp;&nbsp;painting tiles, and the two marks | 359 | |
| &nbsp;&nbsp;&nbsp;&nbsp;clicks and keys | 119 | |
| &nbsp;&nbsp;&nbsp;&nbsp;init | 35 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *29* | |
| **`events.inc`** — the event ring (§10) | **268** | **0.5%** |
| &nbsp;&nbsp;&nbsp;&nbsp;`evq_pop` | 60 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`evq_push` | 55 | |
| &nbsp;&nbsp;&nbsp;&nbsp;`evq_init` | 19 | |
| &nbsp;&nbsp;&nbsp;&nbsp;*.bss scratch* | *134* | |
| **`cpudet.inc`** — CPU tiers and the A20 gate (§41.1-41.3) | **10** | **0.0%** |
| &nbsp;&nbsp;&nbsp;&nbsp;the 8086/286/386 tier test | 10 | |
| **total** | **54,910** | |<!-- END generated table -->

### Reading it

A few of the rows say something that is not obvious from the size alone.

- **`clock.inc` is four clocks, and half of it now boots away.** Each rung of
  SPEC.md §37.90's ladder is a different chip with a different register
  layout. Only one of the four can ever run on a machine and there is no way
  to know which until the probe has walked them, so none of it can be
  *loadable* the way the sound tiers are — but the walking itself happens
  once, so all four probe-and-read halves live in the boot overlay now. What
  is left resident is 1,783 bytes: the four writers (the Control Panel can
  set the clock all session), the software calendar the tick advances, and
  the formatters.
- **`kernel.asm`'s own 1,270 bytes are almost entirely the API table.**
  Its slots × 8 bytes is 656 bytes of `push ds / push cs / pop ds / call /
  pop ds / retf`, plus 268 bytes of the longer X and N stubs. That is the
  price of a package living in its own segment (SPEC.md §20.1), and it is
  paid once rather than at every call site.
- **`font.inc`'s 760-byte glyph table left the segment** (below), so its
  `.bss` is 17 bytes of `font_run` line state and nothing else. The four
  renderers are 1,138 bytes for what is, on a 1bpp adapter at a byte-aligned
  x, a single store per cell row (SPEC.md §6.1).
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
are the same ones the guards use, so a build that passes `KERN_BUDGET`
already agrees with the totals above.

---

## Moving data out of the segment, and where that stops

`KERN_CODE_MAX` counts `.text` + `.bss`. It does **not** count `.lowbss`, which lives
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
| `font_glyphs` | 760 | 5 | **+755** | `font.inc` only |
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
- **`snd_xlat` (256 B) is refused on speed, not entanglement.** Only two
  sites, but they are `spk_pcm_run`'s per-sample loop, where a prefix is not
  free the way it is everywhere else on this list.

**`font_glyphs` needed the ABI amended, and was worth it.** At 760 bytes
against five dereferences it is the best ratio in the kernel — better than the
other four together — but `OSAPI_FONT_GLYPHS` published it as an offset in
`KERNEL_SEG`, and SPEC.md §20.8 rule 4 says a shipped slot keeps its contract.
The cell answers `DX:SI` now, a recorded one-time amendment on the same terms
as slots 0x0120/0x0128: exactly one package reads it (Paint's text tool), it
is in this tree, and `make` rebuilds it. Paint already kept the table as a
(segment, offset) pair and merely hard-coded the segment, so the change there
is one instruction.

The five dereferences are the glyph-row loops, so this one has a **measurable
run-time cost** where the others do not, and it was checked rather than
waved through. A segment override is one byte and 2 clocks on an 8088 — up to
4 if the four-byte prefetch queue is starved, which in these loops it will be.
Per glyph the read runs eight times (once per row) on the mono adapters and in
`font_char`'s VGA path, and 32 times in `font_char_bb` with the back buffer
armed, because there the row loop sits inside the per-plane loop:

| | clocks/glyph | of a ~4,770-clock cell |
|---|---:|---:|
| mono — the 8088 target | 16–32 | **0.34–0.67%** |
| VGA, back buffer armed | 64–128 | 1.34–2.68% |

The 1 ms figure a cell costs on a real 4.77 MHz XT with a Hercules card comes
from `tests/fontbench` (SPEC.md §6.1.1). Two thirds of one percent on the
machine this OS is for, and the machines that pay four times that are the ones
fast enough to have a back buffer in the first place.

**There is no cheaper encoding.** `[bp]` would default to SS with no prefix,
but 8086 addressing has no `mod=00` form for BP — it assembles as `[bp+0]`,
so it is the same extra byte *and* a worse effective address (9 clocks
against `[si]`'s 5). `ss:` is the floor.

**The trap this sprang, and the one to expect next time.** A field-offset
regex finds `[di+I_STATE]`; it does not find `add di, I_NAME` followed by a
bare `[di]`, and it does not find a `rep stosb` whose ES was set with
`push ds / pop es`. Both exist, both assemble, and both write to the wrong
segment at run time. Every migration here had to be checked for three shapes,
not one: field accesses, bare dereferences of an advanced pointer, and string
operations whose segment register is set from DS.

---

## The boot overlay: code that costs no memory at all

Some of the kernel runs exactly once, from `kmain`, and is then unreachable
forever. `.ovl` is where that code goes, and it is the only rung on this
ladder that costs **nothing** — not RAM, not budget, and above all not guard
2.

It works because of what the `FAT_SEG` window is doing at boot: nothing.
`disk_mount` is the only routine that writes it, it is called from three
places, and the earliest of those is `drv_boot` — the *last* thing `kmain`
does before the first paint. So there is a 4,608-byte hole in the middle of
the kernel's own ladder that is live for the whole of start-up and dead the
instant the first volume mounts. The overlay is 661 bytes of it today.

`.ovl` is declared `start=OVL_START vstart=0`, and both halves matter.
`start=` is the *file* offset — the image rung — so NASM emits the gap
between `.text` and the rung as zeros and the boot sector's existing single
read lands the overlay exactly on `FAT_SEG`. No second read loop, no gap
constant, and the splash's progress bar still spans the whole load because
there is still only one total to span. `vstart=0` makes the overlay's own
labels offsets from `FAT_SEG`, so `call FAT_SEG:ovl_cpu_detect` resolves at
assembly time.

**It is one assembly, and that is the whole trick.** A separate build would
not know where `cpu_tier`, `xm_kb` or the eighteen `snd_*` words live, and
every one of them would have to be marshalled through a hand-written ABI.
Because `.ovl` is a section of the same source, every kernel symbol resolves
normally — and because the overlay runs with **DS = KERNEL_SEG**, those
references execute exactly as they did in `.text`. Nothing was rewritten.
What moved, moved by changing one `section` line above it and one below.

The contract is `CS = FAT_SEG, DS = KERNEL_SEG, SS = LOW_SEG`, and it has one
sharp edge: **the overlay may not reach its own labels through DS.** It has
no data of its own today; anything added needs a `cs:` override, and NASM
will not warn. Two more rules fall out of the segment split: a call *into*
the overlay goes through a four-byte `call`/`retf` stub at its head, which is
what lets every routine that moved keep its near `ret` and change in no other
way; and a call *out* of it needs a resident four-byte shim (`ovw_*`), which
a routine gets only if an overlay entry needs it and it has to stay resident
for its own reasons.

What is out there now, and why each one is safe to lose after boot:

| | bytes | |
|---|---:|---|
| `cpudet.inc` minus `cpu_info` | 314 | the tier test and the whole A20 gate. `cpu_info` stays: it is API slot 0x0188 and answers all session long |
| `xm_init` | 121 | sizing the store is a once. `xm_arm` stays resident — `xm_copy` re-arms unreal mode inside the window that uses it — so it gets a shim |
| `snd_init` | 107 | saving the boot 61h bits and publishing `snd_live`. `snd_unhook` is the shutdown path and stays |
| `desk_init` | 95 | counting volumes and laying out their zones. `desk_ord` and `desk_zone_label` are called by the runtime painters and stay |
| the clock's probe-and-read ladder | 1,788 | `clk_init`, `clk_probe`, `clk_commit` and all four rungs' read halves — 26 routines |
| the entry stubs and the seven shims | 52 | |

**`drv_boot` must not go in it**, though it is single-call and looks like a
perfect candidate: it would overwrite itself mid-execution, because
`disk_mount` is what fills `FAT_SEG`. That is the edge of the idea.

### The clock was the hard one, and how its split was decided

`clock.inc` is the largest thing in the overlay and the only one that was not
two `section` lines. It interleaves each rung's *read* helpers with its
*write* helpers, and the writers stay resident because the Control Panel can
set the clock all session — so the boundary had to be derived rather than
eyeballed. It was: build the module's call graph, take everything reachable
from `clk_init`, subtract everything reachable from the six symbols called
from outside the module (`clk_tick`, `clk_snapshot`, `clk_fmt`, `clk_fld_str`,
`clk_fld_adj`, `clk_rtc_write`), and what is left is movable by construction.

That answered 26 routines, 1,788 bytes, in eight non-contiguous runs — and
five helpers that both halves use and which therefore cannot move:
`clk_at_get`, `clk_at_done`, `clk_ns_put`, `clk_ns_stamp`, `clk_rp_get`. It
also settled two that look like they could go either way: `clk_bcd` moves
(only the read paths decode BCD; the writers use `clk_tobcd`), and
`clk_commit` moves (only `clk_probe` calls it).

**`tools/os88ovlchk.py` exists because of this change.** A near call between
`.text` and `.ovl` assembles without complaint and emits a displacement
computed between two different address spaces — NASM will not warn, there is
no linker, and three of the four rungs are unreachable under QEMU, so the
one machine available here cannot execute most of the code that would be
wrong. The checker walks every section block and refuses a near call that
crosses the boundary in either direction. `make` runs it before assembling,
and it is worth more than any amount of reading: deliberately putting one
call back reproduces the failure as a build error on the exact line.

Guard 4b holds the overlay to the FAT window it is read into; guard 4c
refuses an empty one, because every `FAT_SEG:` far call in `kmain` would then
land in whatever the FAT buffer happens to hold.

---

## Cold code: resident, but not in the segment

The boot overlay works because its code is *transient*. Most cold code is not:
the Control Panel has to be there whenever the user opens it. `.cold` is for
that — a second code segment, resident for the whole session, that
`KERN_CODE_MAX` cannot see.

**This is `.fartext` returning, and both reasons it was retired have
inverted.** It died (SPEC.md §33) because the mechanism needed a fixed
10,752-byte reservation to hold a 5,455-byte blob, and because the number
being steered by was the *footprint*, so it cost 5,297 bytes to save nothing.
Today the ladder is derived — `COLD_PARA` is `ceil(size/512)` rounded, with
no slack at all — and the binding guard is the segment, which cold code
relieves one for one. What it costs is footprint-neutral: the same bytes, in
a different segment, on the same contiguous boot read.

It shares the overlay's contract exactly — **CS = `COLD_SEG`, DS =
`KERNEL_SEG`** — and that is again what makes it cheap. `ctrl.inc` keeps its
846 bytes of strings, bitmaps and page state in `.text`, so every data
reference in the module is unchanged, its own included. Only calls moved:

| | |
|---|---:|
| Control Panel code into `.cold` | −2,676 |
| 29 `cw_*` shims for what it calls back (4 bytes each) | +116 |
| 7 resident thunks for what calls *it* | +42 |
| **net off `KERN_CODE_MAX`** | **−2,518** |

**The module had already been split once**, and the split was still in the
file: two bare `section .text` directives, one of them under the comment
*"DATA, so back to the kernel segment — cp_glyph walks them through DS"*.
They are `.fartext`-era markers, left behind when it was retired and inert
ever since, and they mark exactly the boundary this change needed. The
derivation agreed with them line for line.

Three things about the wiring are worth keeping:

- **Window callbacks go through resident thunks, not through `W_SEG`.** A
  package's window carries a far pointer and `wm_pkgcall` sets DS to the
  package's own segment — which is the wrong contract here, since cold code
  wants DS = `KERNEL_SEG`. Rather than teach the window record a third case,
  `cp_paint` and `cp_onclick` are six-byte thunks in `.text` and the cold
  bodies are renamed `_x`. `cp_tpl` still names them, so nothing in
  `wm_create`, `app_launch` or the instance table changed at all.
- **A `.text` data table full of `.cold` pointers is fine** as long as only
  cold code dispatches through it. The five pages' paint/click table is
  exactly that, and it needs no thunks — the pointers are cold offsets and
  the dispatch is a near call from cold code.
- **`tools/os88ovlchk.py` generalised to this for free.** It was written for
  the overlay boundary; it now takes any section with a `vstart` of its own,
  and it caught all 92 crossings this change introduced before a single boot.

The Task Manager was the obvious next tenant — 6,279 bytes, the largest
single module left — and it went somewhere better instead. See below.

---

## The Task Manager leaves the kernel

A cold segment would have taken about 4,900 bytes off `KERN_CODE_MAX` and
**nothing** off `KERN_BUDGET`: cold code is resident, so the footprint is
unchanged. Making it
a package on the system disk took 6,040 off *both* — the span went 76 KB → 69
KB and the segment gained 5,380 — and the memory it uses is now spent only
while the window is open. SPEC.md §28 has the design; what is worth recording
here is the shape of the exchange.

**It was the only built-in that could not be lifted out**, and every reason
was one reason: it read `sch_cycles`, `sch_tasks`, `sch_cur`, `inst_tab`,
`mem_tab` and seven assembly-time constants of this very ladder directly,
because it was kernel code and could. Nothing else in the tree wanted any of
that, so no API slot had ever been written for it. SPEC.md §20.9's four cells
are that API — three table snapshots into a caller-supplied buffer and a
patterned fill — and they cost 1,240 bytes of kernel to save 6,279.

The step order mattered and is worth copying: the cells were added **first**,
with the module still built in and converted to use them, and only then did
the module move. That way the API was proved sufficient while the code was
still somewhere a debugger could reach, and a missing field showed up with
everything else unchanged.

| | `KERN_CODE_MAX` | `KERN_BUDGET` |
|---|---:|---:|
| four API cells, module still built in | +1,240 | +1,024 |
| the module leaves (`taskmgr.inc`, 6,279) | −6,279 | −5,632 |
| `ui_tm_open`, `ui_note` and `dsk_find_name` | +341 | +512 |
| unwiring the kind, its icon and `tm_init` | −682 | −1,024 |
| **net** | **−5,380** | **−5,120** |

(The `KERN_BUDGET` column moves in 512-byte steps because the image rung
rounds to whole sectors, which is why its arithmetic does not match
`KERN_CODE_MAX`'s row for row.)

The cost is real and worth stating in the same place as the saving: opening
the Task Manager now needs a working disk and about 7.3 KB of free heap, on
the machine where you are opening it precisely because something is wrong.
Two things make that acceptable. The **Control Panel** — the window you want
when a driver will not attach, and where `drv_notice` sends you — is cold and
therefore still resident. And the failure is not silent: the chip menu's item
stays live (SPEC.md §47 rule 3 — the only honest test is the load itself) and
puts up a notice naming the reason.

---

## What hard-disk support cost, and what paid for it

Adding the volume table, the FAT window, driver-owned Control Panel pages and
volume-driven desktop zones (SPEC.md §18.7, §18.8, §26.1, §31.9, §51.2.1) took
about 1,700 bytes of `.text`. It overran **`KERN_CODE_MAX`** — `.text` +
`.bss` inside one 64KB segment — which is the 16-bit offset and cannot be
raised at any price.

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

Then two performance changes spent a little more of the segment and, for the
first time in this file, **claimed heap for speed rather than for capacity**:
`DSK_FAT_SECS` sectors — 4.5KB, rounded to a 5KB claim tagged `MEM_K_FATW` —
**per driver-backed volume**, so that a copy alternating between two hard-disk
partitions stops reloading nine FAT sectors on every switch (SPEC.md §18.8.1).
Two mounted partitions is 10KB of heap that a machine with no hard disk never
pays, a floppy never asks for, and a refused claim degrades out of entirely.
The kernel-side cost is 24 bytes of `.bss` for the two per-volume arrays, four
words moved from `.bss` into `.text` so they can carry real initialisers, and
the park/pick/claim/drop routines.

Where that leaves the two guards, on this build:

```
KERN_CODE_MAX  .text + .bss   55,102 / 65,536  10,434 bytes
KERN_BUDGET    KERN_SIZE      72,192 / 74,240   2,048 bytes
```

`KERN_BUDGET` was **not** raised for any of this, and `KERN_CODE_MAX` was the
binding one for a while afterwards — 71 bytes free at its worst. Every candidate named
here at the time has since been spent, in this order: the bulk `.bss` arrays
that are walked through a pointer rather than addressed by name went to
`.lowbss` and the background stacks halved (§ *Moving data out of the
segment*); the clock's probe-and-read ladder went into the boot overlay, which
costs nothing at all (§ *The boot overlay*); the Control Panel's code went
cold (§ *Cold code*); and the Task Manager left the kernel entirely for a
package on the system disk (SPEC.md §28), which is the only one of the four
that came off **both** guards.

That is 71 bytes to 11,559 (10,434 after the copy engine, the review fixes
and the mouse poller), and `KERN_BUDGET` is the tighter of the two again — the intended
order, since a budget is a decision and a segment is physics. Lowering the
budget onto the kernel (move 5 above) is what made it tighter by 5x rather
than by a hair.
