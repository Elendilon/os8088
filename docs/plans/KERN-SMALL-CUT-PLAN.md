# `kern_small` — what a 128KB machine can stop carrying

> **THIS IS THE OPEN HALF. What has been BUILT is
> `docs/plans/completed/KERN-SMALL-CUT-BUILT.md`**, and it is worth reading
> first: it carries A3, A4, A2, C3, B5 and the D rows, and the three findings
> that bind every row still on this page - sections are not heap, a byte's
> value depends on where it is, and a claim is not a section.

> **RE-MEASURED AT BUILD 556 (2026-09-09), AND THE HEADLINE MOVED.** A
> `kern_small` desktop has **50.0 KB** of free heap, `KERN_SIZE` **78,336**,
> heap floor 78.0 KB - confirmed on a machine with 128KB in it
> (`tests/small128.py`, `os8088_5150_cga_128k`: *"HEAP_SEG 79872 = 78.0 KB ->
> 51200 bytes free = 50.0 KB, 50.0 KB usable"*, no pinned claim standing).
> The completed companion's 50.5 KB was taken at `KERN_SIZE` 77,824; the tree
> has since grown one image rung to work that landed elsewhere. **Every figure
> below is this tree's**, and the pre-merge build-376 figures the previous
> revision carried are gone rather than annotated - a stale number in a table
> reads exactly like a current one.

> **The 70KB target is RETIRED and the brief is open-ended.** It was derived
> from SHEET's region, and SHEET claims ~100KB of heap on open - more than the
> machine has - so no row in this document ever ran it (§0.1, §8.2). What is
> asked now is: take what can be taken, and weigh each feature against what
> losing it does to the machine. PAINT, the other program behind the original
> ask, was solved at the APPLICATION layer instead (SPEC.md 42.23), which is
> the shape worth noticing.

**Research document, not a contract.** SPEC.md is the binding contract for what
the kernel *is*; this is the study of what `kern_small` could stop being, and
the arithmetic that says how far each answer gets. Nothing STILL ON THIS PAGE
has been built - what was is in the completed companion above.

The ask, in the requester's words:

> `kern_small` needs to run on a system with 128KB of RAM. It does, now, but
> not with enough free heap to run almost any program. I'd like there to be
> 70KB of free heap. That means `kern_small` booted in 58KB. Research what we
> can gate. What would a 128KB system not likely have hardware wise? … For
> `kern_small` everything is on the table.

---

## 0. The verdict, up front

**The whole list, taken, lands at 66.5 KB of free heap — and it costs the
ability to write a file.** That is 1.5 KB better than the previous revision of
this document predicted, and none of the improvement is new cutting: the
baseline moved under it while the rows were being re-priced.

```
today       KERN_SIZE 78,336   heap floor 78.0 KB   free heap on 128KB = 50.0 KB
CLEAN rows  KERN_SIZE 69,632   heap floor 69.5 KB   free heap on 128KB = 58.5 KB
everything  KERN_SIZE 61,440   heap floor 61.5 KB   free heap on 128KB = 66.5 KB
                               ------------------------------------------------
the clean cut  8,704 bytes  |  everything 16,896 = 21.6% of the footprint
```

**AND THE FIRST NUMBER IS NOT THE BINDING ONE.** 66.5 KB is what the
*kernel* arithmetic allows. What a row actually costs is decided on the APPS
disk, and §10 is that audit: five of the rows below have published API slots
that packages shipped on the small floppies CALL AND DO NOT TEST — so the
refusing stub they would become is not a graceful refusal, it is silent wrong
output. **Taking only the rows that break nothing reaches 58.5 KB.**

Seven findings, of which the first four are new at this reading.

1. **A ROW'S COST IS NOT WHAT THE DESKTOP LOSES, IT IS WHAT THE SHIPPED SMALL
   PACKAGES LOSE — and no revision of this document had checked.** §10. Every
   table here priced the kernel side alone, and the "refusing stub" idiom that
   makes gating look cheap only works when the caller tests CF. Swept across
   `apps/`, filtered to what `make smallapps` actually writes: **B4 is dead**
   (Paint's pencil stroke IS `OSAPI_GFX_LINE`, and so is the menu checkmark in
   `os88ui.inc`, which ~20 packages include), and B3, C6, C8 and C1 all have
   untested callers on the small disks.

2. **The measurement method is now VALIDATED against a real gate, and it is
   exact.** §9.1 is the check: the `gfx_line` family's symbol span is 1,503
   bytes, and a build with that family actually gated out measures `.text`
   38,756 → 37,261, which is **1,495 = 1,503 less the 8 bytes of `stc`/`ret`
   stubs the gate adds**. Not close — equal. So the tables below are what a
   gate returns, not an estimate of it, wherever the row's symbols are
   contiguous.

3. **§7's cap is 288 bytes now, not 2,816 — D2 spent it.** The FAT window is
   already at two sectors, so the boot overlay very nearly fills the region it
   lands in. This is not arithmetic on this page: `DSK_NENT 32→16` **fails to
   assemble**, on `kernel.asm:7090`, *"the boot overlay's window half has
   outgrown the FAT window plus the mount buffers"*.

4. **D3 is not capped, it is IMPOSSIBLE**, and it should be struck rather than
   deferred. `files.inc:662` requires `DSK_NENT * DSK_DE_STRIDE` to be a
   multiple of 256, because `FS_IOFH` holds an icon base in one byte. At a
   stride of 24 that makes `DSK_NENT` a multiple of **32**, so the only legal
   value below today's is zero. §5.1.

5. **There is still no big single win.** The largest symbol in the kernel is
   `osapi_table` at 1,312 bytes and the second is `sch_stacks` at 1,280, which
   is the task slices and not code. Below that it is a long tail of 40–200
   byte procedures. The cut has to come from removing whole *features*.

6. **The hardware question is SPENT.** It was worth ~4,700 bytes when this
   document opened and it is worth **1,110** — the sound layer, and nothing
   else. A3, A4 and A2 are built, and A2r, the residue this revision first
   carried as a live row, turns out to be the SOFTWARE clock: §2.2.

7. **The heap COMPACTOR is not on this list**, and was costed rather than
   assumed: **docs/plans/KERN-SMALL-NOCOMPACT.md**. What looks like a nicety
   on a small machine is what makes the small machine work.

---

## 0.1 A PROGRAM'S SIZE IS ITS REGION *PLUS* THE CLAIMS IT MAKES TO RUN

This document sized programs by their `.o88`, which is the number `ls` gives
and the number a disk catalogue prints. It is not the number that decides
whether a program runs.

**SHEET makes almost 100KB of heap claims on open** — its grid, its cell
store, its undo — which is more RAM than a 128KB machine has in total, before
its 48,352-byte region is counted at all. So **SHEET will never run on
`kern_small` in its current form**, at 70KB of free heap or at any other
figure this document could reach.

**The 70KB target is retired.** It was reverse-engineered from "the heap at
which SHEET loads", and that premise is gone. The other program behind it was
PAINT, and **that one has been solved at the APPLICATION layer instead** —
SPEC.md 42.23's 1bpp canvas and SPEC.md 42.6.5's claim-first sizing. The
kernel was being asked to make room that the program was better placed to stop
needing.

**And the shape has held up.** SPEC.md 28.12 is the same move on the Task
Manager: gating the heap page and the memory view out of the `APP_SMALL` arm
takes one instance from **11,138 bytes to 6,693**, 39.9%, against a 128KB
machine's whole free heap of 50 KB. **It cost the kernel nothing at all**,
which is what makes it worth preferring to any row in §2–§5: no `KERN_SIZE`,
no rung, no feature that a 640KB machine loses.

### 0.1.1 …and a claim is INVISIBLE to every measurement in this document

`kernsize` reports sections. A heap claim is not a section — it appears in no
column of any table here, and no `%if` in `kernel.asm` can see it. Every
figure in §1–§8 is therefore a *footprint* figure.

**Two of the three claim-shaped levers this document pointed at are now
SPENT**, and the next reader should not re-derive them:

- **The pinned-claim audit is empty, and re-confirmed at this reading.**
  `tests/small128.py` walks `mem_tab` on the floor machine at a bare desktop
  and reads **0 bytes pinned, 0 purgeable**. There is no second `ASC_KB`
  hiding behind the 50.0 KB headline.
- **The menu save-under is no longer a 20KB resident claim.** `MENU_SAVE_KB`
  is 20 and reads like 20KB of a 128KB machine's heap; it is now only the
  build-time *ceiling* asserted in `kernel.asm:7442`. `menu_save_kb` sizes the
  claim from the rect and `[vid_planes]`, takes it when a menu drops and
  releases it before the routine returns — *"~4KB on VGA and ~1KB on
  Hercules"*. Three quarters of the old fixed figure was plane-count that a
  1bpp adapter was never going to write.
- **What is left is the per-instance claim**, and B5's second half is the only
  one anybody has counted: `VIEW_KB` is 2, so an open Disk window costs 2,048
  bytes of heap and four of them cost 8,192 — against a 50.0 KB arena. It
  appears in no table here because a claim never does.

---

## 1. The arithmetic, and where the bytes are now

`kern_small`'s footprint is one contiguous span from `KERNEL_SEG` (linear
0x00600) to `KERN_END`, and it is four rungs, each rounded up to 512 bytes:

| rung | holds | measured | rung | slack |
|---|---|---:|---:|---:|
| image | `.text` 38,756 + `.bss` 4,819 | 43,575 | **44,032** | 457 |
| cold | `.cold` | 26,483 | **26,624** | 141 |
| FAT | `DSK_FAT_SECS` = 2 sectors | 1,024 | **1,024** | — |
| low | `.lowbss` 6,060 + `STK0_SIZE` 512 | 6,572 | **6,656** | 84 |
| vgabuf | the planar decoder's buffers — **already zero on small** | 0 | **0** | — |
| | | | **78,336** | |

The heap starts where the kernel actually ends:

```
free heap = int 12h  -  (KERNEL_SEG*16 + KERN_SIZE)
          = 131,072  -  (1,536 + 78,336)  =  51,200 bytes  =  50.0 KB
```

**`.ovl` (423) and `.ovlw` (2,789) are NOT in that sum and buy nothing when
cut.** They are boot-overlay code loaded onto memory the machine reuses once
it is up. They matter here for one reason only, and it is §7's: `.ovlw` lands
on the FAT window, so it is what *caps* the FAT and mount-buffer rows.

**Two things that are not levers.** The rungs waste 682 bytes in rounding —
that is noise, not headroom, and CLAUDE.md's rung rule refuses it as an
argument in either direction. And `KERN_SMALL_BUDGET` has 29,184 bytes spare:
that is the *guard*, not the machine. Lowering the guard saves nothing; only
lowering `KERN_SIZE` moves the heap.

### 1.1 What the theme table says about where to look

| theme | bytes | share |
|---|---:|---:|
| the file system, end to end | 23,282 | 35.7% |
| the window system and its furniture | 21,292 | 32.6% |
| drawing: adapters, primitives, glyphs, icons | 7,337 | 11.2% |
| the kernel proper: API table, heap, scheduler, events | 6,623 | 10.2% |
| hardware: drivers, clock, mouse, sound, CPU, XMS | 4,865 | 7.5% |
| the three built-in kinds | 1,356 | 2.1% |
| the Control Panel | 484 | 0.7% |

**The file system and the window system are 68% of the code**, and the
hardware column has fallen from 9.6% to 7.5% because most of it has already
been taken. The requester's own list is drawn almost entirely from the two
themes that are 10% of it together.

### 1.2 The twelve files that hold it

Heap-bearing sections only, this tree, attributed by where each symbol is
defined. `.ovlw` is shown because §7 makes it the constraint, not because it
is worth cutting.

| file | HEAP | `.text` | `.cold` | `.bss` | `.lowbss` | `.ovlw` |
|---|---:|---:|---:|---:|---:|---:|
| `wm.inc` — window manager | **11,106** | 10,083 | 47 | 976 | — | 47 |
| `files.inc` — the Disk window | **9,104** | 1,004 | 7,770 | 330 | — | 83 |
| `disk.inc` — volumes, mount, FAT read | **6,816** | 265 | 5,929 | 622 | — | 762 |
| `diskw.inc` — the FAT write path | **5,077** | 179 | 4,740 | 158 | — | — |
| `vga12.inc` — the drawing primitives | **3,573** | 2,939 | — | 122 | 512 | — |
| `mouse.inc` — serial mouse and cursor | **3,538** | 3,259 | — | 151 | 128 | 646 |
| `menu.inc` — the menu bar | **3,175** | 2,717 | 177 | 197 | 84 | 34 |
| `ui.inc` — the UI task | **2,893** | 2,840 | — | 53 | — | — |
| `kernel.asm` — API table, `kmain`, shims | **2,883** | 2,865 | 18 | — | — | — |
| `sched.inc` — scheduling and the slices | **2,847** | 1,316 | — | 123 | 1,408 | 225 |
| `instance.inc` — instances | **2,476** | 1,566 | 236 | 674 | — | 27 |
| `dskwin.inc` — the mount-owned buffers | **2,336** | — | — | — | 2,336 | — |

`vga12.inc`'s name is misleading on this build: the VGA planar half is gated
out, and what is left is the primitive layer every adapter goes through —
of which **1,503 bytes is the `gfx_line` family alone** (§3, B4).

---

## 2. Hardware a 128KB machine has not got

The requester's first question, and **most of it has now been taken**. A3
(loadable drivers), A4 (`DVOL_MAX` 8→4) and A2 (the clock ladder's probes) are
all built; the record is the completed companion's §1 and §3.

Already gated out, with nothing further to win: the **VGA** (`GFX_VGA`), the
**planar row decoder** (SPEC.md 5.4.1.3), the **whole-column store**
(SPEC.md 39.25), the **PS/2 mouse** (SPEC.md 9.9), **memory above 1MB**
(SPEC.md 41.4 — `xmem.inc` is down to 20 bytes), the **theme** (SPEC.md 76),
the **scrollbar thumb drag** (SPEC.md 13.10.5), the **band composer**
(SPEC.md 5.9), **SAVER.DRV** (SPEC.md 64) and **loadable drivers of every
kind** (SPEC.md 51.0 — `driver.inc` is down to 231 bytes from 2,550).

What is actually still on the table:

| # | option | HEAP | `.text` | `.bss` | what it costs |
|---|---|---:|---:|---:|---|
| A1 | **Sound layer** SPEC.md 34 (`snd.inc`) | **1,110** | 834 | 276 | no PC-speaker tone or PCM at all. 256 of the `.bss` is `snd_xlat` |
| A2r | ~~**Clock residue** SPEC.md 37 (`clock.inc`)~~ | ~~541~~ | — | — | **DEAD — §2.2.** There is no hardware left in it: all four rungs are already out of the assembly, and the 507 bytes are the SOFTWARE clock — the menu bar's cell, file timestamps and toast placement |
| | **subtotal** | **1,110** | | | of which A2r is unavailable — A1 is the whole group |

**A1 is deferred at the owner's instruction** — *"keep pc speaker for this
round - we may cut it later, but for now."* Worth recording for whoever picks
it up: A3 has already made **part of it dead**, because the FM and Sound
Blaster tiers are reached through `SOUND.DRV` and no driver can be loaded
here. What the speaker actually needs is the tone path and `snd_xlat`'s 256
bytes of PCM rescale, so A1 splits and the already-unreachable half is the
cheaper one to take.

### 2.2 A2r is DEAD, and it is this document's own stale sentence

A2r was carried into this revision as *"the per-rung read and write bodies,
which are dispatched at run time and are gated by nothing"*, and recommended
as *"the cheapest row in the document with a contract already behind it"*.
**That sentence was true at build 376 and A2's own build made it false.** It
was re-published rather than re-checked, which is the failure this document
warns about in its own header.

`clock.inc` compiles `%define CLK_TRY(n) 0` when `OS88_RTC` is undefined, and
the comment beside it says what that costs: *"every rung's body is out of the
assembly too"*. Checked against the symbol map rather than the source —
`clk_at_read`, `clk_at_get`, `clk_ns_read`, `clk_ns_get`, `clk_rp_get`,
`clk_bios_read` and all three probes are **ABSENT from the kern_small
build**. There is no hardware clock code left to gate.

**What the 507 bytes of `.text` actually are is the SOFTWARE clock**, and
three things render off it:

| symbol | bytes | who needs it |
|---|---:|---|
| `clk_fmt` + the formatters (`clk_put_mon`, `clk_put2/4`, `clk_h12h`, `clk_ampm`, `clk_mnames`, `str_len`) | 240 | **`menu.inc:1513` — the menu bar's clock cell**, and `toast.inc:428`, whose gap arithmetic is the clock's own length |
| `clk_tick` + `clk_inc_sec` + `clk_mlen` | 201 | `ui.inc:709` — advancing the clock off the **BIOS tick**, which is rung 0 and is the one that still works |
| `clk_snapshot` | 30 | **`diskw.inc:3654` (`dskw_now`) — every file's FAT timestamp**, and `ctrl.inc:3510`, the Control Panel's Date & Time page |

So gating it does not remove a dead hardware path. It removes the clock from
the menu bar, breaks toast placement, and puts a garbage date on every file
the machine saves. **0 bytes available.**

Even the RTC-only `.bss` is not free: all eight bytes (`clk_cent`, `clk_rb`,
`clk_rbin`, `clk_rpep`, `clk_rp24`, `clk_rtc`, `clk_tier`, `clk_dirty`) are
still read from `ctrl.inc` and `hiber.inc`, so taking them means editing the
Control Panel page as well — five bytes for a page edit.

**The general lesson is §10's, one document earlier than §10.** A2r was priced
off a *sentence in this file* rather than off the tree, exactly as B4 was
priced off the kernel and not the apps disk. The rule that catches both:
**re-derive a row before re-publishing it, especially when the row's own
companion says the thing it depends on was built.**

---

## 3. Display niceties

**The distinction that matters is between a *nicety* and *the optimised
path*, and §3.1's three are the second thing.**

| # | option | HEAP | what it costs |
|---|---|---:|---|
| B1 | **Raise cache / save-under** SPEC.md 11.96 (`wm_su*`) | **2,451** | raising a covered window goes from ~10 ms back to the **1,026 ms** SPEC.md 11.96 was written to fix. The buffer is a purgeable claim, so the saving is code only |
| B2 | **Drag cache** SPEC.md 11.96.12 (`wm_dc*`, `wm_cov*`) | **484** | a window drag repaints what it uncovers |
| B3 | **Icon renderer** SPEC.md 10 (`icons.inc`) | *1,060* | **BLOCKED — §10.** `OSAPI_ICON_DRAW`/`_PEN` are called untested by `os88ui.inc`, Paint and Solitaire. `disk_icons` is a further 1,024 of `.lowbss` and is **capped — §7** |
| B4 | ~~**`gfx_line` family**~~ | ~~1,503~~ | **DEAD — §10.1.** Paint's stroke and the menu checkmark are both `OSAPI_GFX_LINE`, neither tests CF. The 1,503 is still the honest *size*; it is simply not available |
| B5 | **Toast** SPEC.md 59 (`toast.inc`) | **458** | SPEC.md 47 rule 3 wants every refusal to say something the user can act on, and SPEC.md 59 is where three of them say it |
| B6 | **Progress widget** SPEC.md 12.8 (`fprog.inc`) | **725** | long file operations go silent |
| B7 | **Screen blanker** SPEC.md 64 (`blank.inc`) | **148** | |
| | **subtotal** | **6,829** | of which **B4 is unavailable and B3 is blocked** — the clean total is **4,266** |

**B4 WAS RECOMMENDED AS THE ROW TO TAKE FIRST, AND IT IS DEAD.** The
reasoning was that no *kernel* drawing path calls it — every caller of
`gfx_ls_*` and `gfx_line_*` is inside the family itself — so the gate would be
four `stc`/`ret` stubs and nothing else. That is true and it is the wrong
question: the family exists for PACKAGES, and §10.1 is the sweep that should
have come first. Paint's freehand stroke *is* one `OSAPI_GFX_LINE` per segment
(SPEC.md 42.8), and Paint ships on both small floppies. The remaining rows in
this group are graded against the same sweep now.

### 3.1 Three things that look like niceties and are not — do not cut these

- **Damage rects and the clip region** SPEC.md 11.90/11.91 (`wm_dmg*` 836 +
  `wm_clip*` 864 = **1,700**). This is not an optimisation layered over the
  redraw path, it *is* the redraw path — PERFORMANCE.md part 5 makes a change
  that reintroduces a full repaint a regression against a documented number.
  Cutting it makes every window operation cost the whole screen on the slowest
  machine that runs this build.
- **`gfx_pairtab0`/`gfx_pairtab1`** (512 bytes of `.lowbss`) and
  **`vid_rowtab`** (256). These *are* the optimised path the requester asked
  to keep, and **they cannot be combined or overlaid** — asked and answered,
  so that nobody derives it a third time. Both are build-once permanent lookup
  tables read **on the same call, five instructions apart**: `gfx_blit4`'s row
  loop calls `gfx_rowbase` (which reads `vid_rowtab`) and then picks a pair
  table on `(x+y)&1`. Different domains, different value widths, and neither
  is ever dead while the machine is drawing.

  Two facts that look like openings and are not. **They are lazily built and
  usually are not** — `gfx_pairbuilt` reads 0 on a desktop with a Disk window
  full of icons open, because icons go through `icon_draw`'s sprite engine —
  but they are `resb`, so the bytes are spent either way. And **Paint going
  1bpp does not free them**: `OSAPI_GFX_BLIT4` is a published slot and CHART
  is on the small apps disk and blits its canvas through it.
- **`softgfx.inc`** (1,200). On `kern_small` this is the *only* renderer — the
  VGA path is already gone — so there is no second path left to collapse into.

### 3.2 And a standing objection to B1 worth keeping on the record

`KERN_SMALL_BUDGET`'s twenty-first move raised this build's budget *for* the
window redraw optimisations, with the reasoning attached: **"a redraw
optimisation is worth most on the slowest machine, so this is not a figure
that work may be kept out of."** B1 is that decision run backwards. It is
re-decidable — a machine that cannot start a second program has a worse
problem than a slow raise — but it should be re-decided explicitly rather than
swept up with the blanker.

**And B1 does not price the way its symbol count suggests.** Its own symbols
are 2,451 bytes, but its address hull is 3,250: `wm_dc_take`, `wm_cov_add` and
`wm_draw_win.paint` are interleaved with it. So a gate on B1 alone returns
2,451 and not the hull — the row is priced at its own symbols throughout this
document, and B4's is the only row where the two coincide.

---

## 4. Features — product decisions rather than build ones

**Three of this group's four biggest rows have been taken since the previous
revision**, which is why the subtotal has fallen from ~16,700 to 8,335: C3
(associations) was gated, and C2 and C4 became on-demand modules (§6). What is
left of those two is their resident stubs.

| # | option | HEAP | what it costs |
|---|---|---:|---|
| C1 | **FAT write path** SPEC.md 18.4–18.6 (`diskw.inc`) | **5,077** | a **read-only OS**: nothing saves, formats, renames or deletes |
| C5 | ~~**Built-in kinds** SPEC.md 14 (`apps.inc`)~~ | ~~1,594~~ | **BUILT — SPEC.md 14.6.** Timer, Bounce and the Builtins menu are gated; `KERN_SIZE` 78,336 → **76,800**, free heap 50.0 → **51.5 KB** measured on the floor machine. About stays and was priced by gating it: **298 bytes that cross no rung** (14.6.3) |
| C6 | **Fullscreen exclusive** SPEC.md 53 (`fsx.inc`) | *788* | **BLOCKED — §10.** Cyclone, Missile and Paint call `OSAPI_FSX_RUN`/`_CAPS` untested; a package that believes it took the screen and did not is worse than one that cannot |
| C7 | **The dock** SPEC.md 30 (`dock.inc`) | **717** | |
| C8 | **Clipboard** SPEC.md 55 (`clip.inc`) | *159* | **CONDITIONAL — §10.** Every small caller tests `OSAPI_CLIP_SIZE`, but Sheet and TexPad do not test `_PUT` and five do not test `_GET`; wants a per-caller read before it is taken |
| C2r | **File-dialog residue** SPEC.md 38 (`fdlg.inc`) | *330* | the module's resident stub. **Not separately takeable** — deleting it deletes the feature the module already made cheap |
| C4r | **Copy/paste residue** SPEC.md 22.3 (`filecp.inc`) | *328* | as above |
| | **subtotal (C1, C5–C8)** | **8,335** | of which only **C5 and C7 (2,311) are clean** |

**C1 is 61% of the group on its own**, and it is the row that decides whether
this build is an operating system or a viewer. It is also **refused by the
module mechanism** and so cannot be moved instead of deleted — §6.

### 4.1 Trimming the Disk window rather than deleting it

`files.inc` is 9,104 bytes and is how a program gets launched, so it cannot go.
It can be thinned, and the separable behaviour re-prices higher than the
previous revision claimed:

| item | `.cold` | note |
|---|---:|---|
| inline rename (`fm_edit*`) | **711** | was priced at 451 |
| drag-and-drop (`fm_drag*`, `fm_dg*`) | **365** | contiguous — a clean gate |
| clone (`fm_clone*`) | **132** | |
| the more-files marker (`fm_more*`) | **125** | contiguous |
| | **1,333** | |

A harder pass over the scroll and view caches (`fmv_*` 967) could plausibly
find as much again, at the cost of a Disk window that lists and launches and
does nothing else. Call it **~2,300 bytes**, up from the ~1,800 this section
used to claim.

---

## 5. Sizing constants — data, with no feature lost

**Every row here was MEASURED at this reading by changing the constant and
re-assembling**, which is why three of them moved and one of them died.

| # | option | HEAP | note |
|---|---|---:|---|
| D5 | **`MAX_WIN` 12 → 6** | **414** | `.text` −36, `.bss` −378. Was priced at ~264. **Mirrored in `apps/os88api.inc`** — an ABI change, gated by `tests/unit/t_mirror.py` |
| D1b | **Partition −256 −192** (5 worker slices) | **448** | `.lowbss`. `SCH_PARTITION` is 128/128/192/192/256/384 today; `SCH_STACK` must stay the largest class, so the 384 slot cannot go |
| D6 | **`INST_MAX` 12 → 6** | **114** | `.bss` only. Was priced at ~270 — **less than half**. Same mirror, same gate |
| D7b | **`MEM_MAX` 20 → 16** | **40** | sixteen heap claims. Not worth the risk of refusing a claim on a busy heap |
| D3 | ~~**`disk_dir` 32 → 16**~~ | — | **IMPOSSIBLE — §5.1** |
| | **subtotal** | **1,016** | |

D5 and D6 are worth the least and cost the most process: they are published to
packages, so moving them means every `.o88` is built against a different bound
and the "one `.o88` serves both kernels" property is at risk. **Take them
last, or not at all.**

### 5.1 D3 is impossible, and the reason is not the boot overlay

D3 has been carried as *"capped by §7"* since this document opened. It is
worse than capped. Setting `DSK_NENT` to 16 produces **two** errors, and the
first one is fatal to the row at any value:

```
kernel/files.inc:662: error: FS_IOFH holds an icon base in ONE byte:
    nmax*DSK_DE_STRIDE must be a multiple of 256.
kernel/kernel.asm:7090: error: the boot overlay's window half has outgrown
    the FAT window plus the mount buffers
```

`DSK_DE_STRIDE` is 24. `n * 24 ≡ 0 (mod 256)` reduces to `n * 3 ≡ 0 (mod 32)`,
and since `gcd(3, 32) = 1` that means **`DSK_NENT` must be a multiple of 32**.
The only legal value below 32 is 0. The row is struck rather than deferred;
listing more than 32 files per volume would be legal, listing fewer is not.

---

## 6. The lever that keeps the features: more on-demand modules

`mod.inc` (SPEC.md 2.8) is *"`.cold` with the address changed, and nothing
else"*. On this build it already carries five modules cut out of the binary
and read into a heap claim when the feature is asked for:

```
ctrl.drv    4,580   format.drv  1,129   clone.drv   5,810
filecp.drv  2,161   fdlg.drv    3,243              = 16,923 bytes NOT in the footprint
```

**W0–W2 of docs/plans/completed/KERN-SMALL-MODULE-SPLIT.md are built** —
`assoc` gated, Cut/Copy/Paste became `FILECP.DRV`, the Standard File dialog
became `FDLG.DRV` — and **there is no fourth wave**. The two candidates left
are refused by the mechanism itself:

| module | verdict |
|---|---|
| `assoc.inc` | **refused**: `mod_need → drv_mounted → dsk_chdir_q_x → dsk_chdir_x → disk_mount_x → asc_lookup_x`. Loading any module can mount, and a mount calls associations. Gated instead (SPEC.md 54.0) |
| `diskw.inc` | **refused**: it is the by-name file I/O layer, not the write path. `mod.inc` calls `dskw_read_x` *to load a module*; `driver.inc` and `loader.inc` call it to load a driver and a package; CTRL.DRV and CLONE.DRV far-call `dwf_dskw_*` from inside their own images. 33 entry points against `MOD_NENT`'s 8 |

**So C1 can be deleted and cannot be moved**, and that is the whole of why §8's
last tier is the only one that reaches 67 KB.

### 6.1 The rule it runs into

docs/plans/completed/ONDEMAND-PLAN.md §1 states the test:

> A feature may be loaded on demand only if the **system disk is already
> required** to do it, or can be required **without interrupting what the user
> was doing** — because on a one-floppy machine every load is a disk swap.

That verdict was correct for the machine it was written against, and W1/W2
were taken past it deliberately for `kern_small` alone, on the argument that
**the alternative on the table is deletion, not the status quo**: a dialog
that sometimes will not open is worse than one that always does, and better
than one that does not exist.

### 6.2 Two structural options that are worse than they look

- **Break ABI parity for `kern_small`.** `osapi_table` is 1,312 bytes (164
  slots at 8 apiece) and it is the largest single symbol in the kernel, which
  makes it look like the answer. It is not: collapsing the refused slots saves
  a few hundred bytes and costs the property docs/history/KERN-SPLIT-PLAN.md
  §0 calls the one everything else depends on — **one `.o88` serves both
  kernels**. A slot number that exists in one build and not another is an ABI
  that depends on a knob (SPEC.md 20.8 rule 4). Bad trade, and the refusing
  stubs are nearly free anyway: the cells are in both tables already, and the
  bodies can share **one** `stc`/`ret` between them.
- **A single-adapter `kern_small`** (one binary for CGA, one for Hercules).
  `viddet.inc` 1,002 + `vidsel.inc` 211 ≈ **1,213**, and it doubles the
  shipped small images and the test matrix. Marginal.

---

## 7. The floor: `.ovlw` sits on the FAT window — and it is nearly full

The boot overlay's window half (`.ovlw`, SPEC.md 2.5.3) is loaded onto
`FAT_SEG` and spills through the mount-owned buffers immediately above it —
one contiguous region that is dead until the first mount. `kernel.asm` guards
it:

```nasm
%if ((OVLW_SIZE + 511) / 512) * 512 > FAT_PARA * 16 + DSK_WIN_BYTES
%error "the boot overlay's window half has outgrown the FAT window plus the mount buffers"
%endif
```

On this tree:

```
.ovlw            2,789  ->  3,072  rounded up to whole sectors
FAT window       1,024   (DSK_FAT_SECS = 2)
disk_dir           768
disk_icons       1,024
dsk_icoix           32
dsk_win_base       512
region           3,360
                 -----
shrink available   288   before the overlay has nowhere to land
```

**288 bytes, not the 2,816 this section used to report.** D2 took the FAT
window from 9 sectors to 2 and spent nearly all of it, which is the completed
companion's §3 lesson arriving a second time: *in a kernel with overlays a
byte's value depends on where it is.* The consequence is that **B3's
`disk_icons` (1,024) is capped to 288**, and D3 is refused by this guard as
well as by §5.1's.

**The route out is to cut `.ovlw`, and it is worth 512 bytes a sector.** The
rounding is what binds, so the useful cuts are the ones that cross a sector:

| cut from `.ovlw` | rounds to | region may fall to | frees |
|---:|---:|---:|---:|
| 0 | 3,072 | 3,072 | 288 |
| **229** | 2,560 | 2,560 | **800** |
| **741** | 2,048 | 2,048 | **1,312** |

The largest owners of `.ovlw` are `disk.inc` 762, `mouse.inc` 646,
`vidsel.inc` 262, `sched.inc` 225 and `clock.inc` 205 — and **`clock.inc`'s
205 are the probes for a ladder SPEC.md 37.0.1 says is unreachable on this
machine**, which makes A2r and this row the same work done once.

**Note the order.** `.ovlw` carries the boot halves of the very features §3
and §4 propose gating, so a build that takes those cuts has a smaller overlay
and a lower floor. Features first, buffers second, and re-measure `OVLW_SIZE`
in between.

---

## 8. The whole list, added up

```
A  hardware                        1,110     clean (A1 only; A2r is dead)
B  display niceties                6,829     4,266 clean, 1,503 dead, 1,060 blocked
C  features (C1, C5-C8)            8,335     2,311 clean, 6,024 blocked
D  sizing constants                1,016     clean
                                  ------
   raw                            17,290     of which 8,703 is CLEAN
```

Rungs round, so the tiers below are computed from the sections rather than
from that sum.

### 8.1 What each tier buys, for choosing a stopping point

| take | `KERN_SIZE` | free heap | what still works |
|---|---:|---:|---|
| ~~today~~ | ~~78,336~~ | ~~50.0 KB~~ | superseded by the row below |
| **today (C5 built)** | **76,800** | **51.5 KB** | measured on the floor machine, `tests/small128.py` |
| A | 76,800 | **51.5 KB** | everything, minus the sound layer (A2r is dead — §2.2) |
| A + D | 75,776 | **52.5 KB** | …with smaller tables and six windows |
| **every CLEAN row** (§10) | **69,632** | **58.5 KB** | …and no save-under, toast, progress, blanker, dock or built-in apps. **Nothing on the small floppies breaks** |
| + the blocked rows, callers swept first | 66,048 | **62.0 KB** | …and no icons, fullscreen or clipboard — each conditional on §10's work |
| + C1 deleted | 61,440 | **66.5 KB** | a read-only OS, and **five packages that think a save succeeded** |

**58.5 KB is the number to plan against**, and it is the one this document did
not have before: it is everything that can be taken without a package on the
small disks going quietly wrong. The rows between 58.5 and 62.0 are not
refused — they are *unpriced*, because their real cost includes a sweep of
their callers that nobody has done.

**And the last row is worse than "a read-only OS" makes it sound.** §6
establishes that `diskw.inc` cannot become a module, so C1 is delete-or-keep —
but `OSAPI_FILE_WRITE` is called by Artful, Cyclone, Frotz, `os88chart.inc`
and Paint **without testing CF**, so the failure mode is not a refusal the
user can see, it is a save that reports success. Deleting C1 means a caller
sweep first, exactly as B4 would have.

### 8.2 Where the last bytes would have to come from

The retired 70KB ask is now **3 KB** past the bottom row rather than 20, and
there are only three candidates for it: §4.1's Disk window trim (~2,300), the
damage-rect layer §3.1 refuses (1,700), or a further pass over `.ovlw` (§7).
**None of them is cheap, and the first is the only one that is not actively
unwise.**

**THE BUILT POSITION, for anything decided off the rows above.** W0–W2, A3, A4,
A2's probes, C3, the D batch and B5 are in, and they reach **50.0 KB measured
on a 128KB machine**. What remains unbuilt is group B, group C, A1, A2r and
what is left of group D.

**And the shape worth carrying out of this reading is not in any table here.**
The two programs the ask was about both moved out from under it: PAINT was
solved at the APPLICATION layer (SPEC.md 42.23), and the Task Manager's
`APP_SMALL` arm gave back 4,445 bytes an instance for **no kernel bytes at
all**. Every row in §2–§5 costs a feature on every machine that runs this
build; those cost none. **Before taking anything here, ask whether the package
could stop needing it instead.**

---

## 9. How these figures were taken

Sections and the ladder, from the project's own instrument:

```sh
make small
python3 tools/kernsize.py --modules --build build/smallk -DKERN_SMALL
```

Sub-file, from nasm's `[map all]` on a temporary copy of `kernel/kernel.asm`
assembled with `-DKERN_SMALL`, with each symbol's size taken as the distance to
the next symbol in its section. **The method reconciles exactly** — the summed
spans equal the section lengths for all four heap-bearing sections (`.text`
38,756, `.cold` 26,483, `.bss` 4,819, `.lowbss` 6,060), which is what makes a
per-feature figure quotable rather than indicative.

Group D and the two refusals in §5.1 were taken by **changing the constant and
re-assembling**, which is why three of those rows moved at this reading.

Two cautions for whoever takes the next reading. `tools/kernsize.py --modules`
reports **`kern_big`** unless `-DKERN_SMALL` is passed after the flags. And
**committing invalidates `build/kernel.bin` for the symbol reader**: the About
box's build number is the commit count, so `make` again before re-measuring.

### 9.1 The method was CHECKED against a real gate, and it is exact

Every previous revision of this document priced rows off the symbol map and
said so. It had never been checked that a symbol span is what a *gate* returns
— the difference being the refusing stubs a gate has to leave behind, and any
caller that has to be patched. So one row was built.

`gfx_line`'s family is contiguous in `vga12.inc` from `gfx_linit` to the byte
before `gfx_blit4`. Its span is **1,503 bytes**. Wrapping exactly that range in
`%ifdef KERN_BIG` and giving the four API slots `stc`/`ret` stubs measures:

```
                     .text     delta
baseline            38,756
gfx_line gated      37,261    -1,495   = 1,503 - 8 bytes of stubs
```

**Equal, not close.** Two things follow for the tables above. A row whose
symbols are contiguous is priced to the byte, and the only correction is 2
bytes per slot kept — less if they share one stub, which §6.2 notes they can.
And a row whose symbols are **interleaved with code that stays** — B1 is the
one that matters, hull 3,250 against own 2,451 — must be priced at its own
symbols, because the hull contains things a gate would have to keep. Every row
above is priced at own symbols for that reason; B4's is the one place the two
numbers agree, which is what made it the row worth building.

---

## 10. THE AUDIT THIS DOCUMENT NEVER DID: who CALLS the thing being gated

Every revision of this document, including the re-pricing in §9, measured the
**kernel** side of a row and stopped there. §6.2 even records the reassuring
half of it — the refusing stub is nearly free, because the API cell is in both
tables already and the bodies can share one `stc`/`ret`.

**That is only true when the caller tests CF, and on the small floppies it
mostly does not.**

The sweep is mechanical: take the slots a candidate owns, find every
`call OSAPI_*` in `apps/`, filter to what `make smallapps` actually writes
(`SMALLOMIT` drops Browser, FTPD, Telnet, The Wire, ModPlug, Tracker, Audio,
Tank, Skies), and look at whether a `jc`/`jnc` follows before anything clobbers
the flags — `push`/`pop`/`mov` do not, which matters, because the register
restore between the call and the test is this codebase's normal idiom.

| slot | small callers that do NOT test CF | consequence |
|---|---|---|
| `OSAPI_GFX_LINE` | `os88ui.inc`, Paint, Sheet, Missile, cc | **no ink** |
| `OSAPI_GFX_LINIT`/`_LSTEP`/`_LSTEPV` | Cyclone, Missile | **no ink** |
| `OSAPI_ICON_DRAW` / `_PEN` | `os88ui.inc`, Paint, Solitaire | **no icon** |
| `OSAPI_FSX_RUN` / `_CAPS` | Cyclone, Missile, Paint | believes it took the screen |
| `OSAPI_FILE_WRITE` | Artful, Cyclone, Frotz, `os88chart.inc`, Paint | **a save that reports success** |
| `OSAPI_CLIP_GET` | cc, Note Pad, Sheet, TexPad, Word | a paste of nothing, or of stale bytes |
| `OSAPI_CLIP_PUT` | Sheet, TexPad | a copy that did not happen |

**Three slots come out CLEAN, and the reason each is clean is worth keeping.**

- **`OSAPI_WM_SAVEU` (B1) is not a refusal slot at all.** It is a package
  *declaring* that its content does not change while it is not drawing
  (SPEC.md 11.96.1), and `wm_saveu` **preserves the flags deliberately** —
  *"Preserves the flags for wm_snap's reason: an entry proc calls this after
  wm_create and the carry riding in is its own return value."* So the twelve
  small callers that do not test CF are **correct**, not lucky: gated out, the
  slot becomes a no-op and every package still works. B1 costs the **1,026 ms
  raise** §3.2 argues about and nothing else, exactly as its row says.
- **`OSAPI_TOAST` (B5) and `OSAPI_SND_TONE` (A1) degrade to the thing being
  removed.** A toast that does not appear is what "no toast" means; silence is
  what "no sound" means. An untested CF there costs nothing the row was not
  already charging for.

### 10.1 B4 is the worked example, and it was recommended

The previous revision called `gfx_line` *"the best-value row in the document
and the one to take first"*, on the grounds that no kernel path calls it. Both
halves of that sentence are true and the conclusion is wrong, because the
family is published API that exists **for packages**:

- **Paint's freehand stroke is `OSAPI_GFX_LINE`** (`apps/paint/paint.asm:7520`,
  ungated in the `APP_SMALL` arm), and it is SPEC.md 42.8's whole point —
  *"on the field machine it is the difference between a pencil that follows the
  mouse and one that cannot"*. It does not test CF, so the pencil would not
  slow down, it would **stop leaving ink**. Paint is on the small SYSTEM disk
  *and* the small APPS disk.
- **The menu checkmark is two `OSAPI_GFX_LINE` calls** in `apps/os88ui.inc`,
  which about twenty packages include — Task Manager and Note Pad among them,
  both on the small disks. Every checked menu item loses its tick.
- Missile and Cyclone drive the resumable walker (`_LINIT`/`_LSTEP`/`_LSTEPV`)
  and both ship on small; only Tank, which also uses it, is in `SMALLOMIT`.

So the row is **0 bytes available**, and its 1,503 stays in the tables only as
the honest size of a body that cannot go.

### 10.2 What this changes about the method

§9.1 established that the *size* of a row is exact. §10 establishes that the
size was never the binding quantity:

> **A `kern_small` row is priced on the APPS disk, not in `kernsize`.** The
> kernel arithmetic says what a gate returns; the caller sweep says whether the
> gate may be built at all.

Two rules for the next reading, and they cost minutes rather than a rebuild:

1. **Before pricing a row, list the API slots it owns and grep `apps/` for
   them**, filtered by `SMALLOMIT`. A row with no published slot (B2, B6, B7,
   C5, C7 and every D row) is clean by construction and needs no sweep.
2. **A slot whose callers do not test CF cannot become a refusing stub**
   without a caller sweep landing first — and that sweep is package work in a
   different tree from the kernel change, which is why it belongs in the
   estimate rather than in the follow-up.
