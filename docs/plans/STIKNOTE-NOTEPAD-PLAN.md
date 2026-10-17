# STIKNOTE-NOTEPAD-PLAN: Sticky Note as a pad over a folder of text files

**PLAN, nothing built.** Written 2026-10-17 on `main-size-pass` (elendilon
with main's Sticky Note and Desk Clock merged, `573b5f88`). It is the first
item of that branch's size pass and not the only one.

**The change:** Sticky Note stops being a text editor. Its notes become
ordinary `.TXT` files in `SYSTEM\APPDATA\NOTES` on the boot volume. The pad on
the desk shows them one at a time, and editing hands the file to Note Pad
through `OSAPI_PKG_START`'s document arm. The editor window, the 4 KB pool and
the checkbox marker bytes all go. The pad, the paper colours and the Sticky
App behaviour (desk widget, relaunch, place) stay.

SPEC.md §110.13 is the contract today. When this lands, §110.13 is rewritten
in the commit that lands it and this file moves to `docs/plans/completed/`.

## 1. The owner's decisions (2026-10-17)

| # | question | decision |
|---|---|---|
| 1 | where the notes live | `SYSTEM\APPDATA\NOTES` on the boot volume |
| 2 | knowing when Note Pad is done | poll the instance table the Task Manager reads (`OSAPI_SYS_SNAPSHOT`), and only while a Note Pad *we* launched is open |
| 3 | a tick on the pad while Note Pad has the file | last save wins: it is a text file, and two Note Pads on one `.TXT` do the same |
| 4 | reading notes | read the real file on demand (open, page turn, refresh); no directory slurp held in RAM |
| 5 | `kern_small` | there is no autostart, restore or shortcut there (§110.7), so a Sticky App costs RAM only when launched by hand: it stays on the small disks and the user decides |
| 6 | paper colour and other per-note data | a sidecar or a trailer inside the note are both acceptable; fewest disk reads wins (§3.7 picks) |
| 7 | what is lost (live pad while typing, `On desktop` off mode, colour in the editor) | accepted |

## 2. What already exists (no kernel byte)

| need | the slot or tool | note |
|---|---|---|
| open a file in Note Pad | `OSAPI_PKG_START` document arm, §21.5.3 | `ES:DI` = 13-byte name, folder cluster word, volume byte. **Both names upper case** (§21.5.3.2). Returns once the instance is registered and shown |
| Note Pad opening it | `OSAPI_ARG_FILE` in Note Pad's `np_arg` / `np_onwake` | already the double-click path; Note Pad adopts the name, so Ctrl+S writes back to it |
| list the folder | `OSAPI_FILE_FIND` (ordinal walk) | +0 name, +14 type (`< OSAPI_FT_DIR` = a file), +18 size, +22 bit 0 = compressed. **No date or time** |
| read the top of a note | `OSAPI_FILE_READ_AT` | |
| write, delete | `OSAPI_FILE_WRITE`, `OSAPI_FILE_DELETE` | |
| stand in the folder | `OSAPI_FILE_GOTO_QM` | the include's `stik_enter` already walks to `SYSTEM\APPDATA` and banks it |
| is the Note Pad still open | `OSAPI_SYS_SNAPSHOT` | 470-byte buffer (86 + `INST_MAX` 12 x 32); one `cli` copy; worker-safe |
| the folder on the disk | `os88disk.py --dir-slots FOLDER=N` | **the kernel never grows a directory** (§18.5); see §3.1 |

## 3. Design

### 3.1 The folder, and its size

`SYSTEM\APPDATA\NOTES` ships on every system disk: the four geometries,
`emu.img`, both small disks, and the live media. It holds one file,
`WELCOME.TXT`, so it exists. It is built with `--dir-slots
SYSTEM/APPDATA/NOTES=32`.

**Why it must ship pre-sized:** a directory never grows past the clusters it
was made with (§18.5, `FERR_DIRFULL`). A folder the kernel makes is one
cluster. With 512-byte clusters (the 360 KB, 1.2 MB and 1.44 MB system disks,
§19.3.2) that is 16 entries, so 14 notes after `.` and `..`. With 1 KB
clusters (the 720 KB system disk, the small 360 KB one) it is 30.

32 slots is 30 notes, more than today's 24. It costs 1 KB of directory on
every system disk: two clusters at 512 bytes, one at 1 KB. If the folder is
missing (a disk not built by us, a user who deleted it), the pad makes it with
`OSAPI_FILE_MKDIR` and lives with 14 or 30. `New` then answers a full folder in
words: `Notes folder is full`.

**Each note is at least one cluster.** That is 512 bytes on most system disks
and 1 KB on the 720 KB and small 360 KB ones. Today all notes share one file.
That is the cost of decision 1, and the 360 KB system disk's 17 KB free
(§19.3.2) is where it is paid.

### 3.2 What a note is

- **Any `*.TXT` in the folder**, in directory order. A `.TXT` copied in from a
  Disk window or a DOS PC is a note. Anything else in the folder is skipped.
- **New notes are `NOTEnnnn.TXT`**, with the lowest free number found by the
  same walk.
- **Line 1 is the title**, as today.
- **The text is Note Pad's:** CR LF line ends (a lone LF read as one), and
  bytes outside 32..126 are not drawn. That matches what Note Pad keeps
  (`np_nlfold`).
- **A checkbox is TEXT:** `[ ] ` or `[x] ` (also `[X] `) at the start of a
  line. The pad draws the box glyph in place of the brackets, exactly as it
  draws `SN_BOX0`/`SN_BOX1` today, and hides the text. Note Pad and a DOS PC
  show the brackets, which reads correctly. This replaces the marker bytes.
  The typing shortcuts (`[ ]` turning into a box, Ctrl+T, Enter continuing a
  list) were the editor's and go with it.

### 3.3 The pad

The pad keeps its look, its three layouts, its paper colours and its
controls: `+`, the open-in-editor arrow, `< >`, a box. What changes is where
its text comes from.

- **A 512-byte HEAD buffer** replaces the 4,176-byte payload pool. The pad shows
  a title and at most eight body lines of 21 cells, which is under 210 bytes
  of file even with CR LF on every line. 512 bytes covers any view, and a note
  longer than that shows its top, as today.
- **Turning to a note** is one `FILE_FIND` walk to its ordinal plus one
  `READ_AT` of 512 bytes. The walk also counts `N` for `n / N` and finds the
  next free `NOTEnnnn`. Decision 4 accepts that cost. It is measured in the
  final pass (§5), never estimated twice.
- **The current note is remembered by NAME** in the state file (§3.7), so
  adding or deleting a note does not move it.

### 3.4 Editing: Note Pad, and knowing when it is done

**The arrow** (and `+` after it creates the file) calls `OSAPI_PKG_START`
with an EMPTY program name, so the `.TXT` association picks the program. Note
Pad is the default, and a user who re-associated `.TXT` gets their own
editor. The locator is the note's name, the NOTES folder's cluster (banked
by the walk) and the home volume.

**The watch, decision 2:**

1. Just before the launch, take `OSAPI_SYS_SNAPSHOT` and keep a bitmask of the
   live instance slots (12 bits).
2. Launch, then take another snapshot. The new live slot is the editor. Keep
   its slot number and its `SSI_SEG`. No new slot means the launch was
   refused, and the kernel has already said why on the glass (§21.5.3): no
   watch is armed.
3. While armed, each Sticky App beat (the include's two-second tick, or the
   worker's on `kern_small`) takes a snapshot. When that slot is no longer
   live, or its `SSI_SEG` differs (the slot was reused), the editor is gone:
   disarm, and owe a re-read of the current note.
4. Nothing is polled when no watch is armed.

**Buffer:** the snapshot goes into the pad's composing band (1,920 bytes),
which holds nothing between paints. It is taken at the top of the tick,
before anything there paints, and only the slot, seg and live bit are kept.
That costs no bss.

**Several editors:** opening another note while one is being edited simply
watches the newest one, and the pad re-reads whatever is current when any
watched editor closes. A missed close costs one stale pad until the next
click, page turn or refresh. Every one of those reads the file anyway.

**On `kern_small`** the tick is a worker (§110.7), and a worker may not touch
a file (§20.6 rule 7). The snapshot is legal there, and the re-read is
handed to the UI task through the wake path the include already uses for a
save.

### 3.5 New, Delete, tick

- **New** writes `NOTEnnnn.TXT` holding `New note` + CR LF (a write needs at
  least one byte, and line 1 is the title). The pad turns to it, then it opens
  in the editor as the arrow does.
- **Delete** stays on the pad's menu and keys. It removes the file with
  `OSAPI_FILE_DELETE` after a confirm. **Recommended:** the calendar's
  press-again latch (`Delete again to confirm`), which drops os88ui's alert
  dialog (726 bytes) from the package (§4, open decision C).
- **A tick** flips the byte between the brackets in the head buffer and
  rewrites the file. The head is 512 bytes and the box is always inside it,
  but the file can be longer. So the rewrite reads the WHOLE file into a
  temporary heap claim, patches it, writes it with `OSAPI_FILE_WRITE`, and
  frees the claim. That path works on both kernels and on a compressed file.
  - A file over 16 KB (Note Pad's own ceiling, so not one Note Pad made)
    refuses the tick with a toast.
  - Last save wins (decision 3).
  - Considered and **not** taken in wave 1: an in-place one-sector
    `OSAPI_FILE_WRITE_AT` at offset 0, which `os88data.inc` already uses. It
    is faster and allocates nothing. But `kern_small` has no `WRITE_AT`
    (§18.4.7.4), so the full rewrite is needed anyway, and `WRITE_AT` is raw
    against a compressed file (it would need the `FIND` +22 test). Add it only
    if the final pass measures the full rewrite as too slow on the 5150.

### 3.6 Leaving out the editor

Gone: `sned.inc` (6,023 bytes), the editor's menu items and commands, the
`On desktop` flag and its mode, the welcome note's code (`sn_welcome` and
`F_INIT`, since `WELCOME.TXT` ships on the disk), the pool's model in
`sntext.inc` (`sn_ins`/`sn_del`/`sn_ztail`/`sn_check`), and os88ui's push buttons
if nothing left uses them. The wrap walk (`sn_vline`/`sn_vadv`) stays for the
pad, taught CR LF.

### 3.7 Per-note data: the state file is the sidecar (decision 6)

**A trailer inside the note does not survive Note Pad.** Note Pad drops every
byte outside 32..126 on load (`np_nlfold`), so a hidden trailer is gone at
the first save there. A printable one survives, but it is text the user sees
and can edit. Neither is acceptable.

**`STIKNOTE.DAT`, the state file the include already reads once at launch and
writes when owed, IS the sidecar.** It costs no extra disk read. Payload v2:

| off | size | field |
|---|---|---|
| +0 | 13 | the current note's 8.3 name, NUL-terminated |
| +13 | 1 | flags (bit 7 reserved; `On desktop` is gone) |
| +14 | 1 | entries in use, 0..30 |
| +15 | 30 x 9 | each: an 8-byte stem, space-padded, and its paper 0..4 |

That is 285 bytes, and the zero-tail rule (§110.5.3) writes only the entries
in use. Only notes with a NON-DEFAULT paper get an entry; yellow is
"absent". A walk that no longer finds a stem drops its entry. A renamed or
copied note loses its colour (accepted, decision 7).

`STIK_PAYVER` goes 1 -> 2. A v1 file is DAMAGED to the new build and is
replaced at the first save (`STIK_DMGREPLACE`). **That loses a v1 user's
notes**, so it is open decision A (§4).

### 3.8 What it should cost (ESTIMATES, to be measured)

| | today (`573b5f88`) | after (estimate) |
|---|---:|---:|
| image | 16,912 | ~8,500 - 9,500 |
| bss | 6,485 | ~3,000 (band 1,920 + head 512 + state 300 + the include's 229) |
| on disk, packed | 14,524 | ~7,500 |
| heap at rest | none | none |
| heap while ticking | none | the note's size, freed at once |
| editing | inside the 23 KB above | Note Pad: ~20 KB per instance (13.5 KB small build), only while open |

The estimates are the attribution table of this branch's breakdown, less what
§3.6 removes, plus ~600 bytes of new code: the walk, the head read, the
launch and watch, new/delete/tick and the sidecar table. Every figure is
re-measured when built. `tools/os88pkgsize.py` reads image + bss off the
built `.o88`.

### 3.9 `kern_small` (decision 5)

No change of shipping: Sticky Note stays in the small disks' `STIKAPPS\`. It
never starts by itself there (§110.7), so its RAM is the user's choice. The
small build of Note Pad (§27.16) is the editor there. The worker arm needs
§3.4's hand-off. On `kern_small` the 128 KB machine's free heap holds both
programs: ~10 KB plus 13.5 KB against a ~50 KB arena. That is measured on
`small128`'s machine in the final pass.

## 4. Open decisions for the owner

- **A. v1 notes.** Sticky Note v1 merged to `main` on 2026-10-16 (#266). If no
  user has v1 notes worth keeping, v2 replaces the file (recommended:
  nothing to build). If some do, the package converts a v1 pool into
  `NOTEnnnn.TXT` files once at launch: ~150 bytes, carried forever, for one
  day of v1.
- **B. 30 notes.** 32 directory slots is 1 KB of every system disk. 64 would
  be 62 notes for 2 KB.
- **C. Delete's confirm.** The press-again latch (recommended, −726 bytes)
  or keep the dialog.
- **D. Which editor.** By association (recommended: the user's `.TXT` program)
  or always `NOTEPAD.O88` (§21.5.3's plain arm, which also reports
  failures to the caller rather than to the user).

## 5. Waves, and the rows

Per CLAUDE.md's testing rule, no wave runs a soak row. Each verifies on the
host (`make`, `make small`, `t_stik`, `os88stik.py --selfcheck`, both
packages' sizes) and names its rows. The union runs once after the last wave.

1. **The disk.** `WELCOME.TXT` in `SYSTEM/APPDATA/NOTES` on every system
   image with `--dir-slots`. `t_stik` asserts the folder, its slot count and
   the file on every system image. The host tool learns payload v2.
2. **The pad reads the folder** (view only): walk, head read, CR LF,
   textual boxes, `< >`, the current note by name. Drop the editor (§3.6).
3. **Note Pad**: the arrow, the snapshot watch, the re-read on close,
   `kern_small`'s hand-off.
4. **New, Delete, tick, papers** (the sidecar table).
5. **Docs**: SPEC.md §110.13 rewritten, `readme.txt` (still exactly 8,088
   packed), the attribution re-measured, this file to `completed/`.

**The final pass:** `soak -k 'stiknote*' -k 'stik*' -k 'deskcal*' -k
'desklayer' -k 'small128'`. `tests/stiknote.py` is rewritten around this
design, with legs that:

- open a note in Note Pad from the pad, type, Ctrl+S, close, and require the
  pad to show the new text within one beat after the close;
- require NO snapshot poll while nothing is armed (break it on purpose: arm
  forever, the row must go red);
- tick a box and read the file back on the host;
- New and Delete, a full folder at 30, a paper colour surviving a relaunch;
- run the `kern_small` leg on the 128 KB machine;
- measure the page-turn time and the tick's rewrite on the 4.77 MHz XT
  (decision 4's cost, stated rather than predicted).
