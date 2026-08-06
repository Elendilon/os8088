# File type associations — investigation and plan

**Status: proposal. Nothing here is implemented.**

The ask: a file with a known extension should show the *associated program's*
icon, marked so it reads as a document rather than as the program; and
double-clicking it should open it in that program. Build-time associations to
start; a running program must be able to register a new one or take over an
existing one. It must be small, and it must not cost kernel RAM once booted.

This document is the investigation, the design decisions with the alternatives
I rejected and why, a measured budget, and a phased plan.

---

## 1. What the tree already does, and what that buys

Four findings decided the design. Three of them are the reason this can be
cheap; the fourth is the reason it cannot be free.

### 1.1 The per-file icon is already paid for

`disk_icons` is `dsk_nmax` × `DSK_ICO_SIZE` (32 × 64 in `.lowbss`; 64 × 64 out
of the donated claim on a driver-backed volume, `disk.inc:40`), and it is
**fully rewritten every mount** (SPEC.md §18.3 step 4). A **type-0 file's slot
is currently all zero** — the generic-icon sentinel — and every viewer already
knows what to do with a slot that is not: `fm_draw_icon16` ORs the 32 words,
draws the body if anything is set, and falls back to `ico_app16` if not
(`files.inc:3458`).

So a document icon composed into that already-allocated slot at harvest time
costs **zero bytes of new per-file RAM and zero work in any paint**. Both Disk
window views (list and icon grid — `files.inc:3687` and `:3762`) get it with no
change to a single line of drawing code, the per-window view caches
(SPEC.md §22.1) copy it wholesale as they already do, and so does anything
built on the mount snapshot later. That last part is the point: the user asked
for "any future place that does file things", and putting the answer in the
snapshot rather than in a drawing path is what makes that true by construction
instead of by discipline.

**This is the load-bearing decision: compose at mount, in `disk.inc`'s harvest,
never at draw time.** PERFORMANCE.md's standing budget is untouched — no redraw
path gains an instruction, and no repaint gains a disk read.

The trap it brings: **harvest order**. The doc icon needs the app's glyph, and
the app may sit in the same directory *after* the document in the name sort
(`BEACH.BMP` before `PAINT.O88`). So the harvest becomes two passes over the
≤64 entries — pass A exactly as today (type-1 icons and folders), plus filling
any association row whose app is in this directory; pass B composing type-0
document icons. Both are loops over data already in hand; neither adds I/O.

### 1.2 The table need not touch `.bss` at all

`-f bin` zeroes nothing, so initialised data in `.text` is in the image and is
writable at runtime. The tree already leans on this deliberately — `ui_tm_cwd`
("In .text: -f bin zeroes no .bss"), `[dsk_fatw0]`/`[dsk_fatd0]`, and
`[fdlg_win]`, which is in `.text` precisely so `fdlg_grab` can read it on the
machine's first mouse press.

So the association table is **N rows of `.text` carrying the build-time
defaults**, and a runtime registration writes over a row. One copy of the data,
no `.bss`, no boot-time init code, no `.ovl` staging. Build-time and runtime
associations are the same bytes, which is also why "take over an existing one"
needs no special case.

### 1.3 The open path already has the branch

`fm_open_sel` (`files.inc:1863`) is the single open path — double-click, Enter
and File > Open all reach it — and it branches on the §19 type word: ≥2
navigates, anything else posts index+1 to `[ld_pending]` with the poster's state
block in `[ld_pwin]`, and `ui.inc` runs the loader once the lock drops. A type-0
file goes to the loader and comes back **"Bad package"**, which SPEC.md §19.1
calls "the truthful verdict for double-clicking a data file".

That is exactly the branch an association intercepts, and nothing else moves. A
type-0 file with **no** association keeps that message, byte for byte.

`ui_tm_open` (`ui.inc:973`) is the working template for the rest of it: bank the
volume with `osapi_file_here`, mount elsewhere, `dsk_find_name`, `ld_run_body`,
put the volume back, and report `LD_*` failures through `ui_note`. The
association runner is that routine with a small search in place of one fixed
mount to A:.

### 1.4 The footprint is the constraint, and it is 1,536 bytes

Measured on this tree at `a19e4a8`, by `%warning`-ing the guards:

| guard | used | limit | spare |
|---|---|---|---|
| `KERN_BUDGET` — the **footprint** | 74,752 | 76,288 | **1,536** |
| `KERN_CODE_MAX` — the **segment** (`.text`+`.bss`) | 57,361 | 65,536 | 8,175 |

The segment is not the constraint; the footprint is, by more than 5×. Every
byte of `.text`, `.bss` **and** `.cold` spends the same 1,536, so moving code
cold buys this feature nothing (CLAUDE.md's standing warning). `.ovl` is free
and useless here — the table must be resident.

One small piece of slack: `kernel.bin` is 63,944 and `KIMG_PARA` rounds the
image to 512, so the first **56 bytes** of `.text` growth are already paid for.

§8 of this document is the estimate against that 1,536.

---

## 2. Design decisions

### 2.1 The icon: a page outline with the app's glyph inset — **recommended**

A 16×16 document body built at mount from two pieces: a hand-authored
dog-eared page frame in `disk.inc`'s `.text` (the `dsk_folder_ico` precedent —
"the one icon not harvested off the disk"), with the app's glyph reduced to
8×8 and OR'd into the page's cleared white interior.

| option | RAM cached per association | verdict |
|---|---|---|
| **page frame + 8×8 inset** | **8 bytes** | recommended |
| app's full 16×16 body + corner badge | 64 bytes | **rejected on budget**: 8 associations = 512 bytes, a third of everything left |
| page frame + 3 letters of the extension | 0 bytes | rejected: the ask was the program's icon |
| a diagonal or overlay across the app's icon | 64 bytes | rejected: same cost as the badge, and it destroys the glyph it is marking on a 1bpp screen |

The badge variant is the more *recognisable* of the top two and I would take it
if the budget allowed; it does not. Worth revisiting if the footprint guard is
ever raised again.

**The reduction is majority-of-2×2** — a 2×2 block lights if ≥2 of its 4 source
pixels are ink. OR-of-4 turns a typical 40%-ink Mac icon into a near-solid
blob; point-sampling drops every one-pixel stroke. Majority is the one that
keeps a silhouette at 8×8 on a 1bpp adapter. It runs **once per row**, at
resolution time, never in a paint.

Only the icon's **data** plane is reduced, not its mask: the glyph lands inside
a page interior the frame has already cleared to white, so "ink" is the whole
of what the inset means. That is what makes the cache 8 bytes and not 16.

### 2.2 The row: extension + the app's 8.3 stem — **recommended**

```
+0   3   extension, uppercase, space-padded      'BMP'
+3   8   the app's 8.3 STEM, space-padded        'PAINT   '   ('.O88' implied)
+11  1   flags: bit0 = row live, bit1 = glyph resolved
+12  8   the mini glyph, 8x8, one byte a row, bit 7 leftmost
         ------
         20 bytes; 8 rows = 160 bytes of .text
```

Rejected: a **(drive, cluster) locator**. A cluster cannot be written at build
time, does not survive a disk rebuild, and does not survive the floppy being
swapped. A name survives all three, and the search that resolves it runs once
per double-click — an operation that already costs a remount. A (drive,
cluster) **hint** filled opportunistically and tried before the search is a
sound later optimisation at +3 bytes a row; it is not needed for correctness.

Uppercase-exact comparison on the extension, matching SPEC.md §19.1's existing
`"O88"` rule and for the same reason (foreign OSes uppercase short names on
write). The extension comes off the staged display name — one dot, by 8.3
construction, and the sanitizer leaves `.` alone since 0x2E is inside
0x21..0x7E.

Associations are consulted for **type 0 only**, so a package can never be
shadowed by an `O88` row, and folders are never associated. No new rule; it
falls out of the branch's position.

### 2.3 Delivery: the app **pulls**, the kernel does not push — **recommended**

The instance record is **full**: 32 bytes with `I_CYC` ending at 31
(`instance.inc:26-45`). A push (the kernel calling a document hook) needs a
callback pointer somewhere, and the alternative — growing the window record —
means `WIN_SIZE` × every window slot and a stride change that has broken this
codebase once already (CLAUDE.md, `wm_idx2ptr`).

So one new slot, read-and-clear:

```
OSAPI_ARG_FILE   out CF=1  no document
                     CF=0  SI = NUL 8.3 name in KERNEL_SEG (ES is already
                                KERNEL_SEG on entry, per SPEC.md 20.2)
                           DX = the document's directory cluster
                           BL = its drive
```

The app then calls the **existing** `OSAPI_FILE_GOTO` (0x0230 — the same DX/BL
pair `OSAPI_FILE_HERE` answers) and `OSAPI_FILE_READ`. No new file plumbing,
and the SDK gains one call rather than a contract.

That the answer is a locator rather than "the kernel has already put you in the
right directory" is forced, not a preference: `ld_run_body` reads the app's
image out of the *app's* directory and far-calls the entry as one unit, so the
kernel cannot be standing in the document's directory when the entry proc runs.
Handing over the locator moves that one `dsk_chdir` to where it can happen.

Read-and-clear, so a second instance cannot inherit the document.

### 2.4 Registration: the app supplies its own file stem — **recommended**

```
OSAPI_ASSOC_SET  ES:SI -> 3 extension bytes + 8 stem bytes (an X stub:
                          the kernel needs the caller's DS to read them)
                 out CF=1 = table full and nothing was stored
```

The kernel cannot supply the stem itself: `I_NAME` holds the 16-byte **header**
name (`SOLITAIRE`), not the 8.3 file name (`SOLITAIR.O88`), and nothing in the
instance record records where the package was loaded from. The app knows both
at build time; an `OS88_ASSOC 'BMP','PAINT'` macro makes it one line.

There is deliberately **no ownership model** — "take over an existing one" was
the ask, so a matching extension overwrites the row. Registering an association
grants nothing: the worst outcome is that the wrong program opens a file.

Registration also fills the row's glyph on the spot, out of the caller's own
header at offset 32 (SPEC.md §20.2), which the kernel can read through the
caller's segment.

### 2.5 The glyph is filled opportunistically, three ways, none of them I/O

- **the loader** — a package with the embedded-icon flag has its body at header
  offset 32..95 in hand at load; if its stem names a row, reduce and store.
- **the mount** — pass A already reads every type-1 file's first sector.
  Browsing `APPS/` once lights up every association it holds.
- **registration** — as above.

Until a row is resolved, its documents draw the **bare page frame**. That is a
correct, unambiguous document icon and not a placeholder, which is the same
graceful-degradation rule SPEC.md §50 asks of every claim path.

### 2.6 1bpp

Icons are already colourless — `icons.inc` is a mask pass and a data pass, and
the page frame is 1px black on white, so this feature has no dither class
anywhere in it and cannot trip §48's "text must come from the WHITE class"
trap. §47's rule still binds the other way, though: **it is not done until it
has been looked at on CGA and on Hercules**, because an 8×8 inset inside a
16×16 frame leaves four pixels of margin, and four pixels is where a one-pixel
error shows.

---

## 3. Phase 1 — the table and the icon

No change to what double-clicking does. Icons only.

1. `kernel/assoc.inc` (new, included after `disk.inc`): the table in `.text`
   with the shipped defaults, `assoc_find` (extension → row or CF=1),
   `assoc_reduce` (16×16 data plane → 8×8 majority), `assoc_compose` (row →
   a 64-byte body in scratch), and `assoc_note_app` (this stem is here, fill
   its glyph).
2. `disk.inc`: the page frame body in `.text` next to `dsk_folder_ico`; the
   harvest split into pass A (unchanged + `assoc_note_app`) and pass B
   (type-0 → `assoc_find` → `assoc_compose` → `dsk_put_icon_k`).
3. `loader.inc`: `assoc_note_app` on a successful load.

Scratch: the compose needs a 64-byte buffer in the kernel segment.
**`dsk_ico` is a candidate to reuse** — it is `dsk_get_icon`'s staging buffer,
and nothing calls `dsk_get_icon` during a mount — which saves 64 bytes of the
footprint. It couples two modules through one buffer, so it is worth a comment
naming the invariant; I would take the saving.

Shipped defaults: `BMP`→PAINT, `GIF`→PAINT, `TXT`→NOTEPAD, `MOD`→TRACKER,
`MD`→ARTFUL. That is 5 of 8 rows, leaving 3 for runtime.

**Verify:** boot `make test`, open the apps disk, browse `APPS/` (which lights
the glyphs), then look at a folder holding a `.BMP` and a `.TXT`. Crop and zoom
(`tools/shot.py --crop`) — a 16px icon change is exactly the thing CLAUDE.md
warns reads as "nothing happened" in a full screendump. Then `VIDEO=cga` and
`hercshot.py`.

## 4. Phase 2 — the open path

4. `files.inc`: in `fm_open_sel`, before the `[ld_pending]` post, if the type is
   0 and `assoc_find` hits, stage the document (drive, cwd cluster, 8.3 name)
   and the row, and post an association open instead. No hit → unchanged.
5. `ui.inc`: `assoc_run`, modelled line for line on `ui_tm_open` — bank the
   volume, search for `<stem>.O88`, `ld_run_body`, restore, report `LD_*`
   through `ui_note`, plus one new notice for "the program was not found".
6. The search: current directory, then the root, `APPS` and `GAMES` of the
   current volume, then the same on the other. `dsk_chdir_q` (SPEC.md §18.9)
   is the right walker — it skips the scan, the sort and the per-file icon
   harvest — but it leaves the global snapshot **empty and owed**, and
   `[dsk_lstale]` must be paid on every path back to the event loop. That is
   the trap §18.9 records against `fcp_stop`, and it applies here identically.

**Verify:** double-click a `.BMP` and watch Paint open with it; double-click a
`.XYZ` with no row and confirm it still says "Bad package"; double-click a
`.BMP` with the apps floppy holding no PAINT.O88 and confirm the notice.

## 5. Phase 3 — registration and the document handoff

7. Two API cells at **0x02E8** and **0x02F0** (the table's next free pair —
   `osapi_table_end` is 0x02E8 today) and the `91 * 8` length assertion in
   `kernel.asm:781` bumped to 93. `OSAPI_ASSOC_SET` is an **X stub** (the
   kernel must read the caller's bytes); `OSAPI_ARG_FILE` is a plain cell.
8. `apps/os88api.inc`: both `%define`s and the `OS88_ASSOC` macro.
9. Paint reads `OSAPI_ARG_FILE` in its entry proc and opens the document
   instead of starting blank — the reference consumer, and the one that proves
   the handoff end to end.

**Note:** renumbering is not involved — these are appended past the last cell,
so no existing `.o88` is invalidated (SPEC.md §20.8 rule 4).

## 6. Optional phases, each with its own cost

- **The file dialog gets icons.** `FD_ROWH` is already 16 (`fdlg.inc:65`), so
  the geometry is free — it is a 16px inset on the text origin and one
  `fm_draw_icon16`-shaped call per row. The dialog reads the global snapshot
  directly *because it is modal* (SPEC.md §38.2), so the icons are already
  there. Small, and genuinely the other half of "file save/load".
- **Persistence in `SYSTEM.CFG`.** It is a keyed record file (SPEC.md §51.5)
  and takes new keys, so this is mechanically easy — but 8 rows × 11 bytes
  grows `CFG_NB` from 81 to ~169 and `CFG_FBUF` with it, which is ~90 bytes of
  `.bss` on **every** machine for a feature most sessions never touch. I would
  not take it in v1. If it is wanted, note that the glyph must not be
  persisted (it re-resolves) and that write timing follows SPEC.md §31.8: on
  panel close, never on registration.
- **A second document into a running app.** The pull model reaches a fresh
  instance only. Today a second document launches a second instance, and at an
  app's cap it fronts the running one and the document is dropped with a
  notice. A push hook is the fix and it needs the record space §2.3 says is not
  there — worth doing only if the dropped-document case turns out to annoy.

## 7. What this does *not* change

`fm_draw_icon16`, `icon_draw16`, `ico_core`, the view caches, `fm_repaint`,
`wm_paint_dmg`, the dock, the Task Manager, and every §11.3 clip path. No
redraw path gains an instruction and no paint gains a disk read.

## 8. Budget estimate

Against the **1,536 bytes** of §1.4, less the 56 already paid for by the image
rounding. These are estimates from comparable routines in the tree, not
measurements — the guard is the arbiter and Phase 1 should be measured before
Phase 2 is written.

| item | section | est. bytes |
|---|---|---|
| the table, 8 × 20 | `.text` | 160 |
| the page frame body | `.text` | 64 |
| `assoc_find` / `assoc_note_app` | `.text` | ~90 |
| `assoc_reduce` (majority 2×2) | `.text` | ~70 |
| `assoc_compose` | `.text` | ~60 |
| harvest pass B | `.text` | ~50 |
| `assoc_run` + the search | `.text` | ~180 |
| `fm_open_sel` branch + pending state | `.text` | ~50 |
| 2 API cells + the X stub | `.text` | ~40 |
| notice strings | `.text` | ~40 |
| compose scratch (0 if `dsk_ico` is reused) | `.bss` | 0–64 |
| **total** | | **~800** |

About half of what is left. That is affordable and it is not nothing, and per
CLAUDE.md the decision to spend it belongs with whoever wants the feature —
not with the build.

Two levers if it comes out tight: drop the table to 6 rows (−40), and drop
`GIF`/`MD` from the defaults so the shipped set is `BMP`/`TXT`/`MOD` with 3
free rows.

## 9. Open questions

1. **8 rows enough?** Five are spoken for by the shipped apps. 8 is the
   proposal; 6 and 12 are both one constant.
2. **Persistence?** Not proposed for v1 (§6, ~90 bytes of `.bss` on every
   machine). Say if a registration surviving a reboot is part of the ask.
3. **Full icon + corner badge instead of the inset?** More recognisable,
   8× the cached RAM (§2.1). Worth it only if the footprint guard moves.
4. **The dialog's icons in scope now, or later?** Cheap, and it is the "file
   save/load" half of the request.

## 10. SPEC.md

SPEC.md is the binding contract and it is updated **before** any of this is
written, not after: a new **§54, File type associations**, covering the row
layout, the harvest's two passes and their ordering rule, the resolution
sources, `OSAPI_ARG_FILE`'s read-and-clear contract, and the two new slot
numbers. §19.1's icon paragraph gains the sentence that a type-0 slot is no
longer always blank, and §22's open path gains the association branch.
