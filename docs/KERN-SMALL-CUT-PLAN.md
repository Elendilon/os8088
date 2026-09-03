# `kern_small` — what a 128KB machine can stop carrying

> **The tree moved under this document, twice.** `elendilon` merged kernel
> size pass 3 and APP_SMALL, taking `kern_small` from `KERN_SIZE` **96,256 to
> 94,720** and the free heap from 32.5 KB to **34.0**; then **§4's C3 was
> BUILT** — associations are gated out of `kern_small` (SPEC.md §54.0), taking
> it to **92,160 and 36.5 KB**, and returning the 3,072-byte pinned claim
> docs/KERN-SMALL-MODULE-SPLIT.md §9.1 found, so a bare desktop went from
> ~31.0 KB usable to 36.5. **The per-feature rows below are pre-merge
> measurements** and are within ~1.5% of the merged tree; the tier table in
> §8.1 is the one to re-derive before anything is decided off it.
> docs/KERN-SMALL-MODULE-SPLIT.md §9.2 carries the current arithmetic.

**Research document, not a contract.** SPEC.md is the binding contract for what
the kernel *is*; this is the study of what `kern_small` could stop being, and
the arithmetic that says how far each answer gets. Nothing here has been built.
Every figure was measured on this tree at build 376 by the method in §8, and
the ones that are derived rather than measured say so.

The ask, in the requester's words:

> `kern_small` needs to run on a system with 128KB of RAM. It does, now, but
> not with enough free heap to run almost any program. I'd like there to be
> 70KB of free heap. That means `kern_small` booted in 58KB. Research what we
> can gate. What would a 128KB system not likely have hardware wise? … For
> `kern_small` everything is on the table.

---

## 0. The verdict, up front

**The whole list, taken, lands at ~66KB of free heap and not 70KB — and it
costs the ability to write a file.** The gap is not in any one place: the
kernel is dense and evenly spread, and there is no fat symbol to delete.

```
today      KERN_SIZE 96,256   heap floor 95.5 KB   free heap on 128KB = 32.5 KB
asked for  KERN_SIZE 57,856   heap floor 58.0 KB   free heap on 128KB = 70.0 KB
                              ------------------------------------------------
the cut    38,400 bytes = 39.9% of the footprint
```

Five findings:

1. **There is no big single win.** The largest symbol in the kernel is
   `osapi_table` at 1,256 bytes and the second is `kmain` at 217. Below that it
   is a long tail of 40–200 byte procedures. The cut has to come from removing
   whole *features*, and §2–§5 is that list, priced.

2. **The best lever keeps the features rather than deleting them.** `.cold` is
   34,531 bytes — 36% of the footprint — and `mod.inc` (§2.8) already moves
   10,536 bytes of it out of RAM entirely by shipping it as on-demand modules.
   Two more `.cold` residents can follow it, for **4,649 bytes net** (§6).
   **That figure was 12,997 when this document was written, and
   docs/KERN-SMALL-MODULE-SPLIT.md is the correction**: two of the four
   candidates are refused by the mechanism itself — `assoc.inc` sits inside
   `mod_need`'s own dependency cone and `diskw.inc` is the file I/O layer
   three loaders call — and `fdlg.inc`'s row includes 1,140 bytes of shared
   code that stays either way. Moving is no longer a substitute for deleting;
   §6 is rewritten and §6.1's product decision still stands.

3. **The hardware question the requester asked yields less than it looks.**
   Sound, hard disk, Ethernet, XMS, PS/2 mouse and the VGA are worth about
   **4,700 bytes** together — and most of that is not the hardware at all, it
   is `driver.inc`'s loadable-driver machinery (2,550). Every card is already
   a `.DRV` costing zero resident bytes, and the VGA, the planar decoder, the
   PS/2 mouse and XMS were gated out of `kern_small` some time ago. §2.

4. **A hard floor nobody has had to notice: the boot overlay lands on the FAT
   window.** `.ovlw` is 4,700 bytes and spills through the mount buffers above
   it, so **the FAT window and the mount buffers may shed 2,816 bytes between
   them and not one more** — which caps three of the most attractive data cuts
   at half what they would otherwise give. §7.

5. **32.5KB is the number that makes the request reasonable, and it is worse
   than it looks.** `SHEET.O88` is 48,352 bytes and **cannot be loaded on a
   128KB machine at all** today; PAINT (25,944) fits with 6KB to spare and
   nothing can run beside it. At 66KB, SHEET runs with 14KB left over. The ask
   is not a round number somebody liked — it is roughly where a second program
   becomes possible.

---

## 1. The arithmetic, and where the bytes are now

`kern_small`'s footprint is one contiguous span from `KERNEL_SEG` (linear
0x00600) to `KERN_END`, and it is four rungs, each rounded up to 512 bytes:

| rung | holds | measured | rung |
|---|---|---:|---:|
| image | `.text` 40,614 + `.bss` 5,512 | 46,126 | **46,592** |
| cold | `.cold` | 34,531 | **34,816** |
| FAT | `DSK_FAT_SECS` = 9 sectors | 4,608 | **4,608** |
| low | `.lowbss` 8,712 + `STK0_SIZE` 1,024 | 9,736 | **10,240** |
| vgabuf | the planar decoder's buffers — **already zero on small** | 0 | **0** |
| | | | **96,256** |

The heap starts where the kernel actually ends, and runs to whatever `int 12h`
reports:

```
free heap = int 12h  -  (KERNEL_SEG*16 + KERN_SIZE)
          = 131,072  -  (1,536 + 96,256)  =  33,280 bytes  =  32.5 KB
```

For 70KB free the span must end at 59,392, so `KERN_SIZE` must be **57,856**
and the cut is **38,400 bytes**.

**Two things that are not levers.** The rungs currently waste 1,255 bytes in
rounding (image 466, cold 285, low 504) — that is noise, not headroom, and
CLAUDE.md's rung rule refuses it as an argument in either direction. And
`KERN_SMALL_BUDGET` has 11,264 bytes spare: that is the *guard*, not the
machine. Lowering the guard saves nothing; only lowering `KERN_SIZE` moves the
heap.

### 1.1 What the theme table says about where to look

| theme | bytes | share |
|---|---:|---:|
| the file system, end to end | 29,581 | 39.4% |
| the window system and its furniture | 21,945 | 29.2% |
| drawing: adapters, primitives, glyphs, icons | 7,619 | 10.1% |
| hardware: drivers, clock, mouse, sound, CPU, XMS | 7,179 | 9.6% |
| the kernel proper: API table, heap, scheduler, events | 6,937 | 9.2% |
| the three built-in kinds | 1,392 | 1.9% |
| the Control Panel | 492 | 0.7% |

**The file system and the window system are 69% of the code.** The requester's
own list — sound, hard disk, Ethernet, display niceties — is drawn almost
entirely from the two themes that are 20% of it together. That is the finding
that shapes everything below: a 40% cut cannot be taken out of the hardware
column, because the hardware column is not 40% of anything.

---

## 2. Hardware a 128KB machine has not got

The requester's first question, answered: **most of it is already gone, and
what is left is the machinery rather than the devices.**

Already gated out of `kern_small`, with nothing further to win: the **VGA**
(`GFX_VGA`, an adapter rather than a feature — a VGA card in a `kern_small`
machine runs as a CGA at 640x200), the **planar row decoder** (§5.4.1.3), the
**whole-column store** (§39.25), the **PS/2 mouse** (§9.9, ~690 bytes),
**memory above 1MB** (§41.4, `xmem.inc` is down to 21 bytes), the **theme**
(§76), the **zoom animation** (§11.99), the **scrollbar thumb drag** (§13.10.5),
the **band composer** (§5.9) and **SAVER.DRV** (§64). Every sound card, disk
controller and NIC is a `.DRV` and already costs zero resident bytes.

What is actually still on the table:

| # | option | `.text` | `.cold` | `.bss` | total | what it costs |
|---|---|---:|---:|---:|---:|---|
| A1 | **Sound layer** §34 (`snd.inc`) | 1,035 | — | 287 | **1,322** | no PC-speaker tone or PCM at all. 256 of the `.bss` is `snd_xlat` |
| A2 | **Clock ladder** §37 rungs 1–3 (`clock.inc`) | ~450 | — | ~60 | **~510** | a 5150 has no RTC — MC146818 arrived with the AT — so rungs 1–3 are for machines this build is not for. Keep rung 0, the BIOS tick |
| A3 | **Loadable drivers + `SYSTEM.CFG`** §51 (`driver.inc`) | 453 | 1,794 | 303 | **2,550** | no `.DRV` of any kind can be loaded. `mod.inc`'s modules (Control Panel, Format, Clone) are a different mechanism and survive |
| A4 | **Volume table 8 → 4** (`DVOL_MAX`) | 64 | — | 256 | **320** | four mounted volumes instead of eight; `dsk_bpbv` is 512 bytes of `.bss` |
| | **subtotal** | | | | **~4,700** | |

**A3 is the one to think hardest about.** It is the largest item here and it is
not a device — it is the ability to load one. A `kern_small` machine with no
drivers cannot gain a RAM disk, a hard disk, a screen saver or a network later,
and `SYSTEM.CFG` stops being read. Against that: on a 128KB machine there is no
heap to host a driver in anyway, which is close to an argument that the
mechanism is already unusable there rather than merely unused.

---

## 3. Display niceties

The requester's second question. **The distinction that matters is between a
*nicety* and *the optimised path*, and two of these are the second thing.**

| # | option | bytes | what it costs |
|---|---|---:|---|
| B1 | **Raise cache / save-under** §11.96 (`wm_su*`) | **2,433** | raising a covered window goes from ~10 ms back to the **1,026 ms** §11.96 was written to fix. The memory is a purgeable claim, so the saving is code only |
| B2 | **Drag cache** §11.96.12 (`wm_dc*`, `wm_cov*`) | **415** | a window drag repaints what it uncovers |
| B3 | **Icon renderer + harvested icons** §10 (`icons.inc`, `ico_stage`, `disk_icons`, `dsk_ico`) | **3,173** | 2,048 of it is `disk_icons` in `.lowbss` — see §7, it is capped. Files get generic glyphs |
| B4 | **`gfx_line` family** (`gfx_line`/`gfx_ls`/`gfx_lstep`) | **1,012** | an API slot, so it becomes a refusing stub. docs/GFX-FSX-PLAN.md notes three apps already carry their own Bresenham |
| B5 | **Toast** §59 (`toast.inc`) | **488** | SPEC.md §47 rule 3 wants every refusal to say something the user can act on, and §59 is where three of them say it |
| B6 | **Progress widget** §12.8 (`fprog.inc`) | **661** | long file operations go silent |
| B7 | **Screen blanker** §64 (`blank.inc`) | **158** | |
| | **subtotal** | **~8,340** | |

### 3.1 Three things that look like niceties and are not — do not cut these

- **Damage rects and the clip region** §11.90/§11.91 (`wm_dmg*` 868 +
  `wm_clip*` 862 = **1,730**). This is not an optimisation layered over the
  redraw path, it *is* the redraw path — PERFORMANCE.md part 5 makes a change
  that reintroduces a full repaint a regression against a documented number
  rather than a neutral trade. Cutting it makes every window operation cost
  the whole screen on the slowest machine that runs this build.
- **`gfx_pairtab0`/`gfx_pairtab1`** (512 bytes of `.lowbss`) and
  **`vid_rowtab`** (256). These *are* the optimised path the requester asked
  to keep. docs/MONO-RECLAIM-PLAN.md measured the row table paying for itself
  three times over on CGA (saver 4.69% → 2.85% of the whole machine).
- **`softgfx.inc`** (1,180). On `kern_small` this is the *only* renderer —
  the VGA path is already gone — so there is no second path left to collapse
  into. The "keep only an optimised path" work the requester is thinking of
  was done when `GFX_VGA` was gated.

### 3.2 And a standing objection to B1 worth putting on the record

`KERN_SMALL_BUDGET`'s twenty-first move raised this build's budget *for* the
window redraw optimisations, with the reasoning attached: **"a redraw
optimisation is worth most on the slowest machine, so this is not a figure
that work may be kept out of."** B1 is that decision run backwards. It is
re-decidable — a machine that cannot start a second program has a worse
problem than a slow raise — but it should be re-decided explicitly rather
than swept up with the blanker.

---

## 4. Features — product decisions rather than build ones

| # | option | bytes | what it costs |
|---|---|---:|---|
| C1 | **FAT write path** §18.4–18.6 (`diskw.inc`) | **4,899** | a **read-only OS**: nothing saves, formats, renames or deletes |
| C2 | **Standard File dialog** §38 (`fdlg.inc`) | **3,514** | no application can Open or Save. **Not 4,654**: ~1,140 of `fdlg.inc`'s `.cold` is `apps/os88ui.inc`, which five other files need and which survives deletion (docs/KERN-SMALL-MODULE-SPLIT.md §0) |
| C3 | **File associations** §54 (`assoc.inc`) | **2,526** + **3,072 of heap** | double-clicking a document no longer finds its program, and files get the generic icon. **DECIDED — gated.** The second figure is `asc_use_x`'s `ASC_KB` claim, a kernel tag rather than a purgeable class, taken at the boot mount and never freed: docs/KERN-SMALL-MODULE-SPLIT.md §9.1 |
| C4 | **Cut/Copy/Paste** §22.3–22.5 (`filecp.inc`) | **2,281** | no file management in the Disk window |
| C5 | **Built-in kinds** §14 (`apps.inc` + pools) | **1,540** | Timer, About, Ball, Bounce |
| C6 | **Fullscreen exclusive** §53 (`fsx.inc` + `fsx_mtab`) | **913** | no game or demo can take the screen |
| C7 | **The dock** §30 (`dock.inc`) | **814** | |
| C8 | **Clipboard** §55 (`clip.inc`) | **212** | |
| | **subtotal** | **~16,700** | |

**C1–C4 are 13,220 of the 16,700 — and §6 no longer argues that all four can
be moved instead.** Two of them cannot be.

### 4.1 Trimming the Disk window rather than deleting it

`files.inc` is 8,694 bytes and is how a program gets launched, so it cannot go.
It can be thinned: inline rename (`fm_edit` 314 + `fm_editkey` 137),
drag-and-drop (`fm_drag`/`fm_dgdrop` 116), clone (132), paste (63) and the
more-files marker (126) are **~890 bytes** of clearly separable behaviour, and
a harder pass over the scroll and view caches (`fmv_*` 901, `fm_pool` 96) could
plausibly find as much again. Call it **~1,800 bytes**, at the cost of a Disk
window that lists and launches and does nothing else.

---

## 5. Sizing constants — data, with no feature lost

| # | option | bytes | note |
|---|---|---:|---|
| D1 | **Task partition 13 slots → 6** (`SCH_PARTITION`, `MAX_TASKS`) | **~1,590** | `sch_stacks` is 2,816 of `.lowbss`. Thirteen slices is a 640KB machine's number; 70KB of heap holds about three packages |
| D2 | **FAT window 9 → 3 sectors** (`DSK_FAT_SECS`) | **3,072** | refuses any volume above 720KB. **Capped — §7** |
| D3 | **`disk_dir` 32 → 16 entries** (`DSK_NENT`) | **384** | sixteen files listed per floppy. **Capped — §7** |
| D4 | **`STK0_SIZE` 1,024 → 512** | **512** | 2x the measured 246-byte high-water mark instead of 4x. Task 0's is the one stack `sch_switch`'s canary skips, so this is the slice to be most careful with |
| D5 | **`MAX_WIN` 12 → 6** | **~264** | **mirrored in `apps/os88api.inc`** — an ABI change, gated by `tests/unit/t_mirror.py` |
| D6 | **`INST_MAX` 12 → 6** | **~270** | same mirror, same gate |
| D7 | **`MEM_MAX` 32 → 20** | **120** | twenty heap claims |
| | **subtotal** | **~6,210** | of which D2 and D3 are capped |

D5 and D6 are worth the least and cost the most process: they are published to
packages, so moving them means every `.o88` is built against a different bound
and the "one `.o88` serves both kernels" property is at risk. **Take them last,
or not at all.**

---

## 6. The lever that keeps the features: more on-demand modules

`mod.inc` (SPEC.md §2.8) is *"`.cold` with the address changed, and nothing
else"* — a module is assembled as part of this kernel, cut out of the binary by
`tools/os88mod.py`, read into a heap claim when the feature is asked for and
freed when it is done. It already carries **CTRL.DRV 5,866, FORMAT.DRV 1,131
and CLONE.DRV 3,539 — 10,536 bytes that are not in the footprint.**

**Which of them can follow is docs/KERN-SMALL-MODULE-SPLIT.md**, and the
answer is two of four:

| module | `.cold` | entries | verdict |
|---|---:|---:|---|
| `filecp.inc` — Cut/Copy/Paste | 2,141 | **5** | **possible**, and clean |
| `fdlg.inc` — Standard File dialog | 3,152 | **9** | **possible**, after lifting `os88ui.inc` out and raising `MOD_NENT` to 16 |
| `assoc.inc` — file associations | 2,003 | 9 | **refused**: `mod_need → drv_mounted → dsk_chdir_q_x → dsk_chdir_x → disk_mount_x → asc_lookup_x`. Loading any module can mount, and a mount calls associations |
| `diskw.inc` — the FAT write path | 4,565 | **33** | **refused**: it is the by-name file I/O layer. `mod.inc` calls `dskw_read_x` *to load a module*; `driver.inc` and `loader.inc` call it to load a driver and a package; CTRL.DRV and CLONE.DRV far-call `dwf_dskw_*` from inside their own images |

Net of the resident stubs, the 43 new far entries and `mod_fp`: **4,649
bytes**, taking `KERN_SIZE` 96,256 → 91,136 as the rungs fall today.

**This section read "12,997 more by the same route … within 1,400 bytes of
what deleting them outright would give", and that was wrong.** It was the four
files' `.cold` added up, with no check on entry counts, on the module loader's
own dependency cone, or on what `%include` sits inside `fdlg.inc`. The honest
gap between moving and deleting is **8.4 KB**, because the two largest
candidates can be deleted and cannot be moved.

**It is still worth doing** — 5.0 KB of heap, +15% on a 128KB machine, with
both features intact — but it is not a substitute for the deletions, and the
last row of §8.1 is the only one that reaches 65 KB.

### 6.1 The rule it runs into

docs/ONDEMAND-PLAN.md §1 states the test and it is a good one:

> A feature may be loaded on demand only if the **system disk is already
> required** to do it, or can be required **without interrupting what the user
> was doing** — because on a one-floppy machine every load is a disk swap.

and it runs the test explicitly against two of the four:

> | Standard File dialog | **No, and the requirement is perverse** | fails |
> | Cut/Copy/Paste | **No** | fails |

That verdict is correct for the machine it was written against and it is not to
be waved away: `mod_need` calls `drv_vol_bank` → `drv_mounted`, so on a
one-drive machine with a data disk in A: the dialog refuses. Two things make
`kern_small` the one build where it is worth putting back to the requester:

1. **The alternative on the table is deletion, not the status quo.** §4's C2
   removes the file dialog from this build entirely. A dialog that sometimes
   will not open is worse than one that always does, and better than one that
   does not exist — a comparison that was not available when the rule was
   written.
2. **The rule's constraint is the swap, not the read.** A machine that leaves
   the system disk in A: — which is what a machine with 32.5KB of heap does
   anyway — pays a read.

**This is a decision for whoever owns the product, not a change to make
quietly.** A third argument stood here and is **withdrawn**: that the write
path was never tested against the rule and might pass on its own terms.
`diskw.inc` is refused by the mechanism before the rule is reached.

### 6.2 Two structural options that are worse than they look

- **Break ABI parity for `kern_small`.** `osapi_table` is 1,256 bytes (157
  slots at 8 apiece) and the refusing stubs for big-only slots are 8 bytes
  each. Collapsing them saves a few hundred bytes and costs the property
  docs/KERN-SPLIT-PLAN.md §0 calls the one everything else depends on: **one
  `.o88` serves both kernels.** Bad trade.
- **A single-adapter `kern_small`** (one binary for CGA, one for Hercules).
  `viddet.inc` 918 + `vid_rowtab` 256 + `vidsel.inc` 281 ≈ **1,455**, and it
  doubles the shipped small images and the test matrix. Marginal.

---

## 7. The floor nobody has had to notice: `.ovlw` sits on the FAT window

The boot overlay's window half (`.ovlw`, SPEC.md §2.5.3) is loaded onto
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
.ovlw            4,700  ->  5,120  rounded up to whole sectors
FAT window       4,608
disk_dir           768
disk_icons       2,048
dsk_secbuf         512
region           7,936
                 -----
shrink available 2,816   before the overlay has nowhere to land
```

**So D2 (3,072) + D3 (384) + B3's `disk_icons` (2,048) want 5,504 bytes
between them and may only have 2,816.** Three of the most attractive
data-only cuts in this document are, together, worth half what their rows say.

**It is not a permanent floor.** `.ovlw` carries the boot halves of the very
features §3 and §4 propose gating, so a build that takes those cuts has a
smaller overlay and a lower floor. The right order is therefore **features
first, buffers second, and re-measure `OVLW_SIZE` in between** — sizing the
FAT window against today's overlay would leave bytes on the table.

---

## 8. The whole list, added up

Taking §2 through §5 in full, with §7's cap applied once:

```
A  hardware                        4,700
B  display niceties                8,340
C  features                       16,700
D  sizing constants                6,210
                                  ------
   raw                            35,950
   less the .ovlw cap (§7)        -2,688
                                  ------
   cut                            33,262

KERN_SIZE   96,256 - 33,262  =  62,994
heap floor   1,536 + 62,994  =  64,530  =  63.0 KB
free heap  131,072 - 64,530  =  66,542  =  65.0 KB
```

**~65KB of footprint-derived heap, against 70KB asked for** — and **~68KB
usable** once C3's pinned 3,072-byte association cache is counted
(docs/KERN-SMALL-MODULE-SPLIT.md §9.1), which is within 2KB of the ask — and that is with no file writing, no file
dialog, no copy/paste, no associations, no icons, no sound, no clock beyond the
BIOS tick, no loadable drivers, no dock, no fullscreen, no built-in apps and no
raise cache.

Substituting §6's modules for C1–C4 does **not** land near the same number:
two of the four cannot be moved at all, so the two routes stopped being
alternatives. §8.1 gives both.

### 8.1 What each tier buys, for choosing a stopping point

**The cap in §7 applies to each combination separately**, because it bites only
on the rows that take B3, D2 and D3 together — so a tier is not the sum of the
tiers above it:

| take | cut | free heap | what still works |
|---|---:|---:|---|
| today | — | **32.5 KB** | one mid-size program; SHEET cannot load |
| A | 4,700 | **37.1 KB** | everything, minus sound and loadable drivers |
| A + D | 10,270 | **42.5 KB** | as above, with smaller tables and a 720KB volume cap |
| A + B + D | 16,562 | **48.7 KB** | …and no save-under, icons or `gfx_line` |
| A + B + D + §6 | 21,211 | **53.2 KB** | …and the file dialog and Cut/Copy/Paste intact, loaded on demand |
| A + B + D + §6 + C5–C8 | 24,690 | **56.6 KB** | …and no dock, fullscreen, clipboard or built-in apps |
| everything, C1–C4 deleted (§8) | 33,262 | **65.0 KB** (68.0 usable) | a read-only browser with windows |

**The last row is now the only one that reaches 65 KB, and the gap to the row
above it is the correction.** §6's module route keeps the file dialog and
Cut/Copy/Paste for 4,649 bytes, but `diskw.inc` and `assoc.inc` can only be
deleted — so the two middle rows keep file *writing* and associations and pay
8.4 KB of heap for them. That is the trade to put to the owner, and it is a
different one from the trade this table gave before
docs/KERN-SMALL-MODULE-SPLIT.md was written.

### 8.2 If 70KB is firm

The last ~4KB has to come from somewhere structural, and there are only three
candidates: §4.1's Disk window trim (~1,800), the damage-rect layer §3.1
refuses (1,730), or a fifth and sixth on-demand module out of what `.cold` has
left (`memory.inc` 2,388 and `disk.inc` 5,771 — the second of which is the
mount path itself and cannot be on the disk it mounts). **None of them is
cheap, and the first is the only one that is not actively unwise.**

**And there is a fourth candidate that costs no feature at all: audit the
pinned boot claims.** docs/KERN-SMALL-MODULE-SPLIT.md §9.1 found one by
accident — the association cache holds 3,072 bytes of a 128KB machine's heap
before the user has done anything, and no assembler can see it. Nothing had
ever pointed a `mem_tab` walk at `kern_small`.

**THAT AUDIT HAS NOW BEEN DONE, on a machine with 128KB in it, and it is
EMPTY — so this lever is spent.** `tests/small128.py` boots the floor machine
(`os8088_5150_cga_128k`, the only profile in this tree that is not 640KB) and
walks the table at a bare desktop:

```
int 12h   131,072 bytes (128.0 KB)
HEAP_SEG   89,600 bytes  (87.5 KB)  ->  41,472 free = 40.5 KB
  16E0  1,152 para = 18,432 bytes  owner FE02  purgeable
PINNED on a bare desktop: 0 bytes
USABLE for a program    : 41,472 bytes = 40.5 KB
```

Three things follow. **The 40.5 KB headline is honest** — there is no second
`ASC_KB` hiding behind it, so nothing here can be recovered without giving up
a feature. **The one claim standing is purgeable** (`0xFE` = rank *high*, the
directory read-ahead), 18KB here against 64KB on a 640KB machine, and it goes
back to whoever asks. And **`MIN_RAM_KB` has stopped being arithmetic**: guard
5 compared two constants at assembly time and no machine in this tree had ever
been asked to run the result. It runs, and it reaches a desktop with four
drive zones on it.

So the remaining gap to the ask is the whole gap: **30,208 bytes**, and every
byte of it is a feature in §2–§5.

Worth putting back to the requester: **65KB runs SHEET with 13KB spare**, and
SHEET is the largest package in the tree. The difference between 65 and 70 may
not buy a program.

---

## 9. How these figures were taken

Per-file, from the project's own instrument:

```sh
make kernsplit
python3 tools/kernsize.py --modules --build build/smallk -DKERN_SMALL
```

Sub-file, from nasm's `[map all]` on a temporary copy of `kernel/kernel.asm`
assembled with `-DKERN_SMALL`, with each symbol's size taken as the distance to
the next symbol in its section. **The method reconciles exactly** — the summed
spans equal the section lengths for all four sections (`.text` 40,614, `.cold`
34,531, `.bss` 5,512, `.lowbss` 8,712), which is what makes a per-feature figure
quotable rather than indicative.

Two cautions for whoever takes the next reading. `tools/kernsize.py --modules`
reports **`kern_big`** unless `-DKERN_SMALL` is passed after the flags — the
module and theme tables in docs/KERNEL-MEMORY.md are the default variant's by
design. And **committing invalidates `build/kernel.bin` for the symbol
reader**: the About box's build number is the commit count, so `make` again
before re-measuring.

**Nothing in this document has been built or gated.** Every figure is what the
code costs today; what a gate actually returns is that figure less its call
sites, rounded down to the 512-byte rung it lands in.
