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

| option | RAM cached per **app** (§2.2) | verdict |
|---|---|---|
| **page frame + 8×8 inset** | **8 bytes** | recommended |
| app's full 16×16 body + corner badge | 64 bytes | **rejected on budget**: 12 apps = 768 bytes, half of everything left |
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

### 2.2 Two tables, not one: extensions point at apps — **recommended**

A flat row of extension + stem + glyph is the obvious layout and it is the
wrong one, because **the glyph belongs to the app and not to the extension**.
`BMP` and `GIF` both mean Paint, and a flat table caches Paint's glyph twice.
Normalising costs one indirection and buys roughly triple the associations per
byte:

```
app slot - 16 bytes, indexed by shl 4
  +0   8   the app's 8.3 STEM, space-padded    'PAINT   '   ('.O88' implied)
  +8   8   the mini glyph, 8x8, one byte a row, bit 7 leftmost

ext slot - 4 bytes, indexed by shl 2
  +0   3   extension, uppercase, space-padded  'BMP'
  +3   1   app slot index
```

Both strides are powers of two on purpose: an 8086 has no `shl reg, imm` past
1, so a shift through CL is still far cheaper than the `mul` a 17- or 20-byte
stride would force, and the harvest does this lookup once per listed file.

**No flags byte in either.** "Slot free" is `stem[0] == 0` / `ext[0] == 0` — a
sanitized display name's bytes are 0x21..0x7E and can never be 0 (SPEC.md
§19.1) — and "glyph unresolved" is the 8 bytes ORing to zero, which is exactly
the all-zero sentinel `fm_draw_icon16` already uses on `disk_icons`. An icon
whose reduction is genuinely blank is indistinguishable from an unresolved one
and draws the bare page, which is the correct answer for it anyway.

Sizing is two constants, and the recommendation is the middle row:

| apps × exts | bytes | shipped defaults leave |
|---|---|---|
| 8 × 16 | 192 | 4 apps, 11 exts free |
| **12 × 24** | **288** | **8 apps, 19 exts free** |
| 16 × 32 | 384 | 12 apps, 27 exts free |

For comparison, the flat 20-byte row this replaces was 160 bytes for **8**
associations total. 12 × 24 is +128 bytes for 24 across 12 distinct programs.

One known limitation, not worth code in v1: if every extension pointing at an
app is taken over, that app's slot leaks. With 12 slots and no expected churn
that is acceptable; a compaction sweep on a full-table registration is ~30
bytes if it ever bites.

Rejected as the *primary* key: a **(drive, cluster) locator**. A cluster cannot
be written at build time, does not survive a disk rebuild, and does not survive
the floppy being swapped. A name survives all three. But a cluster **hint** is
what makes §2.7's search affordable and is carried alongside, in two parallel
arrays rather than in the slot, so the power-of-two stride survives:

```
assoc_clus   12 words   the directory cluster the app was last SEEN in
assoc_drv    12 bytes   ...and the volume it was seen on
assoc_dfold  12 bytes   build-time folder: 0 root, 1 APPS, 2 GAMES  (48 bytes)
```

`assoc_dfold` is what §2.7 rung 4 reads, and it needs a home of its own because
the 16-byte app slot is full — it is the one part of a build-time default that
cannot be a cluster, since no cluster is knowable when the kernel is built.

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
the ask, so a matching extension is repointed at the caller's app slot.
Registering an association grants nothing: the worst outcome is that the wrong
program opens a file.

Registration takes an app slot (or reuses the one already naming that stem —
which is what keeps a program registering four extensions to one slot) and
fills its glyph on the spot, out of the caller's own header at offset 32
(SPEC.md §20.2), which the kernel can read through the caller's segment.

### 2.5 The shipped glyphs are baked at build time; the rest fill in

**The first version of this plan resolved every glyph at runtime, and it failed
the one workflow that matters most.** Boot with the apps disk in B:, open
Drive B, go straight into a `DOCUMENTS` folder without detouring through
`APPS/`: `README.TXT` finds its association, finds the Notepad app slot, and
finds its glyph **unresolved** — because nothing has read `NOTEPAD.O88`'s first
sector. The document draws a bare page. Double-clicking it *works* (§2.7 rung
4 knows Notepad lives in `APPS`), so the plan opened the file in the right
program while refusing to say which program that was. Indefensible, and the
fix costs no RAM at all.

**The shipped defaults' glyphs are baked into the table at build time.** They
are knowable: `build/notepad.o88` bytes 32..95 *are* Notepad's 16×16 icon
(verified — v3, flags bit 0 set), so the 8×8 reduction can run on the host. The
8 bytes are already the app slot's glyph field, so this changes **where the
bytes come from and nothing about what they cost**. Boot, Drive B, Documents:
Notepad's mark on every `.TXT`, with no disk access, ever.

**Nothing is read at boot because the bytes are *in* `kernel.bin`.** They are
`db` bytes in `.text` — the boot sector already loads the kernel as one
contiguous run, and those 32 bytes (4 apps × 8) ride along inside the existing
512-byte image rounding, so not even one extra sector is read. The host does
the reading, once, at build time. This is the same standing that
`dsk_folder_ico` and the menu-bar logo already have: icons that live in the
image because there is nothing on disk to harvest them from at the moment they
are needed.

The one thing that is *not* true of a baked glyph: it describes the
`NOTEPAD.O88` this tree built. Put a different program of that name on the
disk and the mark is wrong until something re-resolves it — which the loader's
fill does the first time it is actually run.

It must be **generated, not hand-pasted**. `tools/os88mini.py` emits a `db`
line per shipped app from its `.o88`, and `kernel.bin` gains a dependency on
those four packages. Two notes: the DAG stays acyclic (packages depend on
`apps/os88api.inc`, never on `kernel.bin`), and pasted bytes would go stale
silently when an app's icon changed — a class of staleness `make check-images`
cannot catch, which is exactly why the dependency is the point rather than the
cost.

For everything else — third-party packages, and any row taken over at runtime —
the glyph fills three ways, none of them extra I/O:

- **the loader** — a package with the embedded-icon flag has its body in hand
  at load; if its stem names a slot, reduce and store. So **opening one
  document of a type fixes the icon for every document of that type**, which
  makes the cold case self-healing rather than permanent.
- **the mount** — pass A already reads every type-1 file's first sector, so
  browsing the folder an app lives in lights it up.
- **registration** — out of the caller's own header.

Rejected: **resolving during the mount by going and finding the app** — see
§2.5.1, which is also a correction: it is far dearer than the two seconds an
earlier draft of this document claimed.

Until a slot is resolved its documents draw the **bare page frame**. That is a
correct, unambiguous document icon and not a placeholder, which is the same
graceful-degradation rule SPEC.md §50 asks of every claim path.

### 2.5.1 Why "go and find the app" is not four sector reads

The four icon sectors are about **3% of the cost**. The rest is the machinery
that gets the head to them, and it is worth counting because the intuition that
this is cheap is the reason it keeps looking like the obvious fix.

**`dsk_chdir` is `disk_mount`.** Not a seek, not a cheap re-point — the body is
four lines and the middle one is `call disk_mount`, so changing directory
*within one volume* re-reads the boot sector and re-snapshots the FAT window.
`dsk_chdir_q` (SPEC.md §18.9) skips the scan, the sort and the per-file icon
harvest, and skips **none of that**. `DSK_FAT_SECS` is 9.

And **`dsk_xfer` issues one int 13h per sector** — its `.sector` loop recomputes
CHS and calls the BIOS once per 512 bytes. Consecutive sectors are separate
BIOS calls, so on real hardware each one has missed the sector that was under
the head and waits a full revolution: at 300 RPM that is **200 ms a sector**,
not 200 ms a track.

One association resolved from a `DOCUMENTS` folder, same volume:

| step | sectors |
|---|---|
| `dsk_chdir_q` to `APPS` — boot sector + FAT window | 10 |
| walk `APPS`'s directory for `NOTEPAD.O88` | ~2 |
| **the icon: `NOTEPAD.O88`'s first sector** | **1** |
| the way back — `dsk_relist` → `dskw_sync`, a **full** remount of `DOCUMENTS`, scan and sort and its own icon harvest included | ~12+ |
| | **~35** |

So four filetypes in one folder is **~140 sector reads to obtain 4**, and at a
revolution each that is on the order of **7–8 seconds**, not the two an earlier
draft of this plan claimed. The correction runs the same direction as the
verdict, which is the only reason it did not change it.

The per-revolution model is reasoning from drive mechanics and **should be
measured on the XT before it is quoted as fact** — but it does not stand alone:
CLAUDE.md independently records that a `SYSTEM.CFG` write is "2+ seconds of
completely frozen UI on the floor machine (mount, data, FAT, directory, FAT,
remount)", which puts a mount at roughly a second by a route that has nothing
to do with this arithmetic.

### 2.5.2 The on-disk icon cache — worth doing, and it composes

Given §2.5.1, the case for caching the answer on disk is strong: **12 apps × 16
bytes is 192 bytes — one sector.** One read replaces ~140.

`ICONS.DAT` in a volume's root, hidden + system. The row is **stem + 8×8 glyph
+ the app's directory cluster** — 18 bytes, padded to 20 for a shiftable
stride, so 12 apps is 240 bytes and still one sector. The drive is not stored:
it is whichever volume's file this is.

**The cluster is in the row because of the move case, and it is the reason the
runtime writer is not optional.** A shipped app that gets moved keeps its baked
glyph (that lives in `kernel.bin`) and loses its *location* — so without a
writable cache, every session after the move pays §2.5.1's full search again,
for ever. The cache is the only place a discovered location can outlive a
reboot; §2.2's `assoc_clus` hint is `.text` RAM and dies with the power.

Read **once when the volume is first mounted in a session**, straight into
§2.2's table; after that the RAM table serves every lookup. §19.6's
`dskw_write_sys` already exists precisely so the kernel can rewrite a hidden +
system file, so the write plumbing is not new.

Five things about it:

- **Build it on the host.** `tools/os88disk.py` already places every `.o88` and
  knows the cluster it placed each one at, so it can write a correct, fully
  warm `ICONS.DAT` as it builds the floppy. The shipped disk then costs the
  target nothing on a machine where nothing has moved.
- **Write on a MISS, not on a move — do not hook the file operations.** The
  instinct is to update the cache when the file manager moves or deletes an
  app, and that is both more work and less complete: it catches only the moves
  *this OS* made, and the case actually worth surviving is a file moved from
  DOS, from another machine, or by a rebuild. Healing at the point of discovery
  covers all of them with one code path — the search has just paid ~35 sectors
  to learn something the cache did not know, so writing it back is cheap
  *relative to what was just spent*, and it happens once per app per move
  rather than once per paste. It also means a **deleted** app cleans itself up
  the next time one of its documents is opened, with no delete hook either.
  This is the one place where doing less is also doing more.
- **The cache may serve icons on faith; it must never serve the open path.** A
  stale hit — someone replaced `NOTEPAD.O88` with a different program of the
  same name — is a cosmetically wrong icon, which is harmless, and would be a
  *wrong program loaded*, which is not. So the locator still goes through
  §2.7's name re-check on the disk, every time. That is the same boundary the
  cluster hint already draws, and it is the one invariant this feature must not
  lose.
- **A miss is ordinary.** An app moved or deleted behind the OS's back means
  the stem is not where the cache implies; that falls through to §2.7's rungs
  exactly as an empty hint does. No new failure mode.
- **The write is affordable only because of where it sits.** It is the 2+
  second frozen-UI sequence CLAUDE.md quotes, and SPEC.md §31.8's rule is that
  no such write may land on a click. It does not: it lands immediately after a
  search the user has *already* waited seconds for, on the rare path, and it is
  what stops that wait recurring. That is the opposite of the Control Panel
  case the rule was written for — there the work was already done and only the
  record waited; here the record is the entire point. Worth stating in SPEC.md
  as an explicit exception rather than leaving it to look like an oversight.
- **A failed write is a normal outcome.** A write-protected disk — the shipped
  boot floppy on all seven 86Box machines carries `wp://` deliberately — means
  no cache, so every session re-searches. Degradation, not an error, and
  nothing user-visible.

It **composes with the build-time bake rather than replacing it**: a fresh or
foreign disk has no cache, and the shipped set must be right on the first boot
of any machine. The bake covers the four shipped apps with zero I/O forever;
the cache covers everything else with one sector.

This is Phase 2c in §6.

### 2.6 Nothing is harvested at boot, and that is the whole point

**Boot cost of this feature is zero disk reads.** Nothing walks the apps disk
looking for icons — not at boot, not ever. `drv_boot` mounts A:, whose only
*visible* type-1 file is `TASKMGR.O88` (SPEC.md §19.6 hides the kernel, the
drivers and `SYSTEM.CFG`), so the boot mount's harvest is one first-sector read
that already happens today. All this feature adds to it is a table scan per
listed entry — a few hundred cycles against a floppy access.

What that avoids is worth stating, because "harvest the app icons at boot" is
the obvious design and it is unaffordable. Calculated from 5.25" drive
mechanics — **not measured, and worth checking on the XT before it is quoted**:
300 RPM is a 200 ms revolution, so ~100 ms of average rotational latency;
average seek across 40 tracks at a 6 ms step is ~80 ms plus ~15 ms of head
settle. That is **~150–200 ms per first-sector read once the motor is up**, and
a spun-down motor adds most of a second. Thirteen shipped packages across two
folders on the *other* volume is thirteen reads plus the folder mounts plus two
volume switches: **on the order of 2.5–3 seconds of grinding at every boot**,
for icons most sessions never look at.

And on a **single-drive machine it is not merely slow but impossible** — the
apps disk is not in the drive at boot, it is what the user swaps in later.

So resolution is lazy and opportunistic (§2.5), and the icons cost their
~150 ms each exactly once, inside a mount the user asked for anyway.

### 2.7 Where the program is, and what happens when its disk is out

Three cases, and the first version of this plan got the second and third wrong.

**Resolution order** on a double-click, first hit wins:

1. **The hint** — `assoc_clus`/`assoc_drv` (§2.2): one `dsk_chdir_q` and a
   `dskw_stat` for `<stem>.O88`.
2. **The current directory** — a document beside its program is the common
   case and costs nothing at all.
3. **The volume root.**
4. **The folder `assoc_dfold` names**, for the shipped set only — `APPS` and
   `GAMES` are known at build time *for those apps*, so they are data in the
   default, not a hard-coded search path. This is the rung that carries the
   §2.5 scenario: straight from `DOCUMENTS` to Notepad, having never browsed
   `APPS/`.

**A hint must be validated by name, always.** A cluster is only meaningful on
the disk it came from; after a swap, cluster 47 is something else entirely. So
the hint is a place to *look*, never an answer — `dsk_chdir_q` there and
confirm `<stem>.O88` is present, and fall through if it is not. A stale hint
must never load the wrong file, and the name check is what makes that
structural rather than careful.

The hint is filled wherever the app is **seen**, all three free of extra I/O:
the mount's pass A (which knows the current drive and `[dsk_cwd]`), the loader,
and registration. In practice it is populated by the user having browsed to the
program once — which is how the program got onto their disk in the first place.

**Q3, an app in neither `APPS` nor `GAMES`:** covered by 1–3 above once it has
been seen, and *not* covered on a cold first double-click. Hard-coding a folder
list was the wrong instinct — this codebase's own rule is that nothing may be
built on a fixed listing position (SPEC.md §19.4). The complete fix is a
bounded tree walk, and `filecp.inc` already has the machinery for it: an
explicit frame array with `FCP_MAXD` = 6 and **no call stack**, because a task
stack cannot fund recursion. That is Phase 2b in §6 — ~150 bytes and ~1 second
for a case the hint usually pre-empts, so I would not ship it in v1.

**Q2, the program's disk is not in the drive:** the tree already makes this
*safe*, and the first version of this plan made it *rude*. `desk_init` keeps a
volume row live for a drive the machine does not have, and the comment there is
explicit that "a mount of an absent drive is an ordinary failed mount" — so the
search fails cleanly, no hang, on a one-drive XT as much as anywhere. What was
wrong was the message: "Program not found" is a lie when the program exists and
the *floppy* is out. That case needs its own notice naming the program and the
disk to insert — the Macintosh answer, and one string.

Two consequences worth having in mind:

- **The icons survive the disk leaving the drive.** The glyph is cached in the
  app slot, not resolved on demand, so browsing `APPS/` once and then swapping
  to a documents floppy still shows Paint's mark on every `.BMP`. That is a
  property of caching in the table rather than only in `disk_icons`, and it is
  most of why §2.2 spends 8 bytes a program.
- **A machine that has never seen the apps disk shows bare page icons**, and
  they are correct — an unresolved association is still a document. It is
  degradation, not breakage, exactly as SPEC.md §50 asks of a refused claim.

### 2.8 1bpp

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

0. `tools/os88mini.py` (new): 16×16 icon out of a `.o88`'s bytes 32..95 →
   the 8×8 majority reduction → a `db` line, and a Makefile rule generating
   `build/associco.inc` from the four default apps with `kernel.bin` depending
   on it (§2.5).
1. `kernel/assoc.inc` (new, included after `disk.inc`): the table in `.text`
   `%include`ing the generated glyphs, `assoc_find` (extension → slot or CF=1),
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
`MD`→ARTFUL. Five extensions across four apps, leaving 19 extension slots and
8 app slots free at the recommended 12 × 24.

**Verify — and this is the acceptance test for the whole phase:** boot
`make test`, open Drive B, and go **straight into a documents folder without
entering `APPS/`**. A `.TXT` there must already carry Notepad's mark; a bare
page means the bake (§2.5) is not working and no amount of browsing will tell
you that. Then the same for a `.BMP`. Crop and zoom
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
6. The search is §2.7's four rungs, over the current volume and then the other.
   `dsk_chdir_q` (SPEC.md §18.9) is the right walker — it skips the scan, the
   sort and the per-file icon harvest — but it leaves the global snapshot
   **empty and owed**, and `[dsk_lstale]` must be paid on every path back to
   the event loop. That is the trap §18.9 records against `fcp_stop`, and it
   applies here identically.
7. Two notices, not one: **"…not found"** when the volume mounted and the
   program is genuinely absent, and **"Insert the disk holding PAINT.O88"**
   when the volume it should be on would not mount (§2.7).

**Verify:** double-click a `.BMP` and watch Paint open with it; double-click a
`.XYZ` with no association and confirm it still says "Bad package";
double-click a `.BMP` with the apps floppy holding no `PAINT.O88` and confirm
the not-found notice. Then the absent-disk case, which is the one QEMU makes
easy to get wrong — boot `make xt` (one drive, `vm/xt`) with only the system
disk, double-click a document on it, and confirm the *insert-the-disk* notice
rather than not-found. Then swap in the apps disk, browse `APPS/`, swap back,
and confirm the icons are still Paint's (§2.7) and the double-click now works
from the hint.

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
  and takes new keys, so this is mechanically easy — but the glyphs are the
  only part of §2.2's tables that need not be persisted, so the key is
  12 × 8 stems + 24 × 4 extensions = **192 bytes**, growing `CFG_NB` from 81
  to 273 and `CFG_FBUF` with it. That is ~190 bytes of `.bss` on **every**
  machine for a feature most sessions never touch, and it would take the
  estimate in §8 past what is left. I would not take it in v1; if it is
  wanted, the tables should shrink to pay for it, and write timing follows
  SPEC.md §31.8 — on panel close, never on registration.
- **Phase 2c: the on-disk icon cache** (§2.5.2) — **not optional, and it is
  reader *and* writer.** One sector in place of ~140. The host half is nearly
  free (`tools/os88disk.py` writes `ICONS.DAT` as it builds the floppy, so a
  shipped disk arrives warm), and the runtime writer is what keeps it warm once
  anything moves — including the shipped apps, whose baked glyph survives a
  move but whose *location* does not. Reader ~100 bytes (the row staging can
  borrow `dsk_secbuf`), writer ~150.
- **Phase 2b: the bounded tree walk** (§2.7). Finds a program in a folder
  nobody has browsed and no default names. `filecp.inc`'s frame array is the
  pattern — `FCP_MAXD` = 6, no call stack. ~150 bytes and ~1 second on a
  floppy, for a case the hint usually pre-empts. Worth it only if third-party
  packages in arbitrary folders turn out to be common.
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
| the two tables, 12 × 16 + 24 × 4 (§2.2) | `.text` | 288 |
| the hint + default-folder arrays (§2.2) | `.text` | 48 |
| hint validation + the second notice (§2.7) | `.text` | ~60 |
| `ICONS.DAT` reader + name (§2.5.2, staging borrows `dsk_secbuf`) | `.text` | ~100 |
| `ICONS.DAT` heal-on-miss writer (§2.5.2) | `.text` | ~150 |
| the page frame body | `.text` | 64 |
| `assoc_find` / `assoc_note_app` | `.text` | ~110 |
| `assoc_reduce` (majority 2×2) | `.text` | ~70 |
| `assoc_compose` | `.text` | ~60 |
| harvest pass B | `.text` | ~50 |
| `assoc_run` + the search | `.text` | ~180 |
| `fm_open_sel` branch + pending state | `.text` | ~50 |
| 2 API cells + the X stub | `.text` | ~40 |
| notice strings | `.text` | ~40 |
| compose scratch (0 if `dsk_ico` is reused) | `.bss` | 0–64 |
| **total** | | **~1,340** |

**This no longer fits comfortably** — 87% of the 1,536, before the estimates
have met a single instruction, and every one of them is a guess from
comparable routines. Two things follow, and neither is "hope":

- Take the 8 × 16 table sizing (−96) as the baseline, not a reserve.
- **Phase 1 must be built and measured against the guard before Phase 2 is
  written.** If the real number tracks the estimate, this feature needs a
  `KERN_BUDGET` decision — which per CLAUDE.md is a conversation with whoever
  wants it, not a build fix. The honest framing for that conversation: the
  guard has moved five times, each asked for and granted, and the fifth moved
  it *down* onto the kernel deliberately.

### 8.1 The "fix the disk instead" argument, and what is left of it

An earlier draft of this section claimed that fixing FIELD-NOTES note 3's
same-volume `chdir` "may well be smaller than the code it lets `assoc_run`
avoid". **That is wrong twice over and is corrected here rather than quietly
deleted, because the shape of the error is the useful part.**

**Wrong 1: a fast path adds code, it does not remove any.** Both spends land
against the same `KERN_BUDGET`. Fixing `disk.inc` cannot fund `assoc.inc`;
there is no ledger in which speed work in one module buys footprint in
another. The sentence read as though there were.

**Wrong 2: the fix does not retire the cache.** Count it. Today one resolution
is ~35 sectors (§2.5.1). With a same-volume fast path the boot sector and the
nine FAT sectors go from both the outbound `chdir_q` and the return `relist`,
leaving the `APPS` directory walk (~2), the icon (1), and re-scanning
`DOCUMENTS` on the way back (~2) — call it **5 sectors, so ~20 for four
filetypes**. Better by 7×, and at mechanism C's revolution-per-sector that is
still **~4 seconds**. `ICONS.DAT` at one sector still wins decisively, so the
250 bytes stay.

**What survives is a conditional, and it needs both halves of note 3.** With a
same-volume fast path *and* multi-sector reads, those 20 sectors become a
handful of int 13h calls in a few revolutions — under a second, at which point
the cache is genuinely arguable and its reader, its writer, the hint arrays and
their validation (~360 bytes together) become a UX preference rather than a
necessity. That is a real prospect. It is two fixes and a judgement call, not a
free win, and nothing in this plan should be sequenced as though it were.

**What survives unconditionally is where the bytes are best spent.** A
same-volume fast path looks small — `dsk_fatw_pick` already carries the exact
safety rule ("only a QUIET mount may reuse a banked window; a full mount is a
re-validation, the disk may have been swapped"), and §18.8.1 already banks a
window per driver-backed volume. A floppy is excluded not by a correctness
argument but because it has no claim to bank into, and its window is `FAT_SEG`
— resident, and by that section's own reasoning never sliding. So the policy,
the buffer and the swap rule all exist; what is missing is letting a quiet
same-volume mount reuse what is already in memory. Those bytes fix a reported
symptom in every operation the OS performs. The cache's bytes work around that
symptom for one feature and carry an invariant (§2.5.2: never serve the open
path) that must hold for ever. **If only one of the two gets spent, it should
be the disk.** The build-time glyph bake (§2.5) is in this table
at zero — it changes where the app slot's 8 bytes come from, not what they
cost — and `tools/os88mini.py` runs on the host. That is affordable and it is not nothing, and per
CLAUDE.md the decision to spend it belongs with whoever wants the feature —
not with the build.

The lever if it comes out tight is the table sizing alone, and it is two
constants: 8 × 16 gives back 96 bytes and still allows 16 associations —
double the flat design this replaced. Phase 1 should be measured against the
guard before Phase 2 is written.

## 9. Open questions

1. **Is 12 apps / 24 extensions the right cap?** Both are one constant each
   (§2.2), and the byte cost is 16 and 4 respectively — 32 extensions is only
   32 bytes more than 24. Five extensions across four apps are spoken for by
   the shipped set.
2. **Persistence?** Not proposed for v1 (§6, ~90 bytes of `.bss` on every
   machine). Say if a registration surviving a reboot is part of the ask.
3. **Full icon + corner badge instead of the inset?** More recognisable,
   8× the cached RAM (§2.1). Worth it only if the footprint guard moves.
4. **The dialog's icons in scope now, or later?** Cheap, and it is the "file
   save/load" half of the request.
5. **Is the cold third-party case worth Phase 2b?** Without the tree walk, a
   program in a folder nobody has browsed and no build-time default names
   cannot be found on a first double-click — it works after the program has
   been seen once. ~150 bytes buys the cold case (§2.7).

## 10. SPEC.md

SPEC.md is the binding contract and it is updated **before** any of this is
written, not after: a new **§54, File type associations**, covering the row
layout, the harvest's two passes and their ordering rule, the resolution
sources, `OSAPI_ARG_FILE`'s read-and-clear contract, and the two new slot
numbers. §19.1's icon paragraph gains the sentence that a type-0 slot is no
longer always blank, and §22's open path gains the association branch.
