# The listing's icons: one body per MACHINE, not one per entry

**OPEN. Nothing here is built.** The measurements are taken on `eb8b847`; every
existing byte figure below is read out of the tree or out of a built floppy,
and every figure for code that does not exist yet is marked ESTIMATED.

It starts from a product question - *the Disk window lists 32 entries and DOS
directories are busier than ours ever were* - and the answer turns out not to
be "raise the number". The listing's entries are 27% of what it spends. The
other 73% is a 64-byte icon slot per entry, and **most of those slots hold
either a copy of one built-in body or 64 zero bytes.**

---

## 1. What a listing costs today

`kern_big`, a floppy, in `.lowbss`:

| | bytes | |
|---|---|---|
| `disk_dir` - 32 entries x `DSK_DE_STRIDE` 24 | 768 | 27% |
| `disk_icons` - 32 slots x `DSK_ICO_SIZE` 64 | **2,048** | **73%** |
| | **2,816** | |

`kern_small` already spends 1,824 for the same listing (SPEC.md 25.8: a 16-body
POOL and a one-byte index per entry). A driver-backed volume gets
`DSK_VENT` = 64 entries out of the 6KB its driver funds - 5,632 bytes of it.
And the whole shape is MIRRORED per open Disk window in a heap claim
(`VIEW_KB` = 3 on `kern_big`, 2 on `kern_small`, up to `VIEW_SLOTS` = 4).

`.lowbss` is the tightest rung in the kernel: **9,182 bytes, 34 left, 93% of the
current rung accrued** - and it sits BELOW `HEAP_SEG` in the ladder, so every
byte spent there comes off the heap and therefore off the DOS arena, byte for
byte. That is not an abstract cost this month:
docs/reports/DOS-GAMES-2026-09-16.md has Chip 'n Dale losing by **three
kilobytes**.

## 2. The entry is not the problem, and its 24 bytes are nearly all name

SPEC.md 19.1's meaningful prefix is name 0..15, type 16, handle 18..19, size
dword 20..23. The name is a NUL-terminated 8.3, so **13 of its 16 bytes are
used** and byte 17 is spare: 4 bytes an entry of padding, 128 of a 32-entry
listing. Worth taking eventually, worth nothing on its own.

## 3. THREE populations of icon, with three different properties

Read `disk.inc`'s harvest (step 4 of `disk_mount`, SPEC.md 18.3) and the slots
fill three ways:

| entry | what goes in its 64-byte slot | where the bytes really live |
|---|---|---|
| folder (type >= 2) | a byte-for-byte **copy** of one built-in body | already in the kernel image, `disk.inc:903` |
| document (type 0) | **64 zero bytes** - the generic-icon sentinel | nowhere; the appearance is composed at draw time |
| package (type 1) | its own icon, harvested from its `.o88` header | the file itself, and `ASSOC.DAT` |

**A document's icon was never in this array.** `assoc_compose` draws a page
frame and ORs an **8x8 glyph** into the interior (SPEC.md 54.3), and that glyph
lives in `assoc_glyph` - `ASSOC_NAPP` = 12 slots x 8 bytes = **96 bytes**,
resident, of which the first five are BAKED INTO THE KERNEL at build time by
`tools/os88mini.py`.

So only the third row needs storage that varies, and **in a DOS directory there
is no third row at all.** Measured on the game disks built for
docs/reports/DOS-GAMES-2026-09-16.md: LEMMINGS 68 entries, F15 66, TD1 41,
CHIPDALE 22 - **zero packages in every one.** Today each of those gets 64 slots
of zeros: 2,048 bytes of RAM spelling *no icon* thirty-two times.

## 4. The identity: `(stem, size)`, and it is already on the disk

A single machine-wide body store needs to answer *is the icon from volume A the
same as the one from volume B* - because SPEC.md 24.3 ships the core packages on
the system disk AND the apps disk, and a hard disk makes a third copy.

**`asc_lookup_x` already answers exactly that question, and has since SPEC.md
54.7.** It keys on the **8-byte name stem and the size word**, both read
straight out of the staged directory entry:

```asm
    mov dx, [si+20]             ; the size the directory reports
    ...
    repe cmpsb                  ; 8 bytes of stem
    cmp dx, [es:di+8]           ; the stem matches: the size must too
```

Measured against every package copy on the six shipped 360KB disks:

```
package copies:                                     53
DISTINCT (8-char stem, size) keys:                  29
copies the key correctly collapses:                 24

   BROWSER   13155 bytes  on os8088-360, apps360, network360
   PAINT     22007 bytes  on os8088-360, apps360, office360
   MINES      1818 bytes  on os8088-360, apps360, games360
   TELNET     12726 bytes  on os8088-360, apps360, network360
   ... 16 more
```

**29 keys for 29 genuinely distinct packages - no false merge in 53 copies**,
and 45% of what we ship is a duplicate the key collapses. 29 also happens to sit
inside `ASSOC.DAT`'s own 32 rows, which is presumably why 32 was chosen.

### 4.1 Why not a content hash, and why not an id in the header

**A hash costs the read it is trying to save.** The value of the `ASSOC.DAT`
path is that a hit costs NO sector read - `asc_lookup_x` answers before
`.h_read` ever runs. An identifier inside the icon body, or anywhere in the
32-byte header, is inside the FILE, so fetching it IS the read. `(stem, size)`
is the only identity available from the directory entry alone.

**And the header has no room.** SPEC.md 20.2 fills all 32 bytes: magic 0..1,
version 2, flags 3, link base 4..5, entry 6..7, image 8..9, bss 10..11, the
three-byte dispatcher 12..14, stack class 15, name 16..31. An embedded id is a
v3 -> v4 bump and a rebuild of every package, to buy immunity to two cases: two
different packages sharing a stem AND a byte size (did not occur in 53 copies,
and the failure is a wrong icon, which is cosmetic), and the same package at two
sizes - a `PKGZ=` build, or a hard disk carrying an older release - whose
failure is a cache MISS, not a wrong icon. **Not worth a format break.**

## 5. `ASSOC.DAT` IS the cache, already, on disk

```
ASC_ROW  equ 80    ; stem 8 + size 2 + cluster 2 + 4 reserved + a 64-byte icon
ASC_KB   equ 3     ; 32*80 + 16 + 24*4 = 2,672 bytes
```

The row carries **the whole body**. So the thing this plan proposes in RAM is a
read-through cache over a format that already exists, with the identity already
defined and already persisted - and it should BE the 80-byte row, so that
filling the cache is a read and not a conversion.

## 6. What may be purged, and what may not

A machine-wide store is a candidate for the heap rather than `.lowbss`, which
would cost **zero resident bytes** and leave the DOS arena alone. The question
is what a purge loses, and the two halves answer differently:

| | size | refills itself? | purgeable |
|---|---|---|---|
| the 64-byte bodies | 2,048 | **yes** - one read of the volume's `ASSOC.DAT`, ~2.7KB, one or two coalesced `int 13h` for every icon on the disk | **yes** |
| `assoc_glyph`, the 8x8 document glyphs | **96** | **no** - a LEARNED one needs a volume that may no longer be in the drive | **never** |

The glyphs are 96 resident bytes with initialisers today, so honouring that
costs nothing: they were never a candidate for the heap. And the case that looks
worst - *double-click a `.EXE` on a DOS-only floppy and `.EXE` loses its icon* -
**cannot happen**, because `.COM`, `.EXE` and `.LNK` resolve to app slot 4 of
`assoc_stem`, which is a built-in for exactly this reason:

```asm
    db 'DOS     '     ; SPEC.md 96: the handler for .COM, .EXE and .LNK (96.21),
                      ; and it has to be a BUILT-IN rather than a
                      ; declaration on the disk - see assoc_ext
```

The cold path - no `ASSOC.DAT` on the volume - is a per-file harvest at ~400 ms
a package, bounded by the packages in ONE directory. Measured worst case across
every shipped floppy: **15** (`apps.img` APPS, 17 entries). Every shipped disk
is written with a warm `ASSOC.DAT`, so that path is for foreign media, which by
definition has no packages on it.

## 7. SPEC.md 25.8.5.1 said no to this, and what overturns it

`kernel.asm:2224` carries the standing refusal, and its arithmetic is RIGHT:

> kern_big keeps one body per ENTRY and so cannot take the line above: its pool
> would need `DSK_NENT` bodies not to show fewer icons than it does today, and
> 768 + 32 + 2,048 is 32 bytes MORE than the 2,816 it spends now

A 32-body pool plus a 32-byte index is indeed 32 bytes worse than 32 bodies.
**What that argument is missing is how many bodies a directory actually needs**,
and the answer is 15 in the worst shipped case and 0 in every DOS one. The
premise *the pool must equal `DSK_NENT` or an icon degrades* is what the
measurement retires - and SPEC.md 25's generic-icon fallback is a picture the
system already has, which `kern_small` has shipped against for a cycle.

## 8. The arithmetic

Per listing, `kern_big`, entries at 24 bytes plus ONE reference byte each,
with the bodies no longer per listing at all:

| entries | `disk_dir` | index | per-listing total | vs today's 2,816 |
|---|---|---|---|---|
| 32 | 768 | 32 | **800** | **-2,016** |
| 64 | 1,536 | 64 | **1,600** | **-1,216** |
| 128 | 3,072 | 128 | **3,200** | +384 |

...plus ONE machine-wide body store, whichever entry count is chosen:

| store | bytes | where |
|---|---|---|
| 16 `ASC_ROW`s | 1,280 | heap claim, purgeable |
| 32 `ASC_ROW`s | 2,560 | heap claim, purgeable - holds all 29 distinct icons we ship |

**A 64-entry listing with a purgeable 32-row store is 1,600 resident bytes
against today's 2,816** - double the listing, **1,216 bytes given back to the
arena**, and the store costs nothing resident. A 128-entry listing - which
covers LEMMINGS (68), F15 (66) and TD1 (41) outright - is +384.

And the per-window heap mirror loses its icon half entirely: `VIEW_KB` 3 -> 2 at
64 entries, **1,024 bytes of heap per open Disk window**, four of them.

## 9. The one constraint, and it DISSOLVES rather than being lifted

`FS_IOFH` (files.inc:247) holds the icon base's HIGH BYTE in one byte, which is
why `files.inc:694` requires `nmax * DSK_DE_STRIDE` to be a multiple of 256 and
why the stride cannot fall below 24 at 32 entries.

**The first draft of this plan made widening it to a word wave 1. That was
wrong and is recorded here so nobody builds it.** `FS_IOFH`'s only job is
*where the icon slots start inside THIS WINDOW'S OWN cache* - six sites, and
`fmv_viofs` is in as many words "the only reader". Once the bodies are in a
machine-wide store, a window's cache holds entries and reference bytes and
**has no icon region at all**, so the field has no job, the `%if` that guards
it has nothing to guard, and both are deleted by wave 2 rather than widened
ahead of it. Nothing between here and there needs the stride to move: the base
is `32 * 24` = 768 throughout, which is a multiple of 256 already.

The same is true one level along of `dsk_ioff`'s driver-backed base
(`disk.inc:2419`, `DSK_VENT * DSK_DE_STRIDE`) - it is the same fact about the
same vanishing region, and it goes at the same time.

## 10. The waves

1. **The reference byte.** `dsk_ico_ofs` resolves an entry to a body through a
   one-byte reference instead of `index * 64`; folder and generic become
   sentinel values that name a built-in rather than a copy. **Every reader
   already goes through `dsk_get_icon_x`**, which stages into `dsk_ico` and
   hands back SI - so no caller changes. `kern_small` has this shape already
   (`dsk_iconext`, `dsk_icofld`); this generalises it to both kernels and
   deletes its `%ifdef`s. The bodies are still per listing at the end of this
   wave, which is what keeps it independently buildable.
2. **The machine-wide store**, as `ASC_ROW`s, keyed `(stem, size)`. The
   per-listing and per-window icon regions go here, and `FS_IOFH`,
   `fmv_viofs`, `dsk_ioff` and the multiple-of-256 `%if` go with them.

   **IT IS A NEW CLAIM AND NOT THE `ASSOC.DAT` BUFFER**, which is what the two
   questions below settled. `asc_seg` is read from the file with one
   `dsk_read_chain_x` straight into the claim at offset 0 and is WIPED on a
   volume switch, so making it multi-volume would mean staging the file
   somewhere else to merge from - a second buffer either way. A separate
   ADDITIVE store leaves `asc_use_x` untouched and takes its rows from
   whatever answered: an `asc_lookup_x` hit, a harvest, or a compose.

   - **There is no writer to break.** The kernel never writes `ASSOC.DAT` -
     `asc_s_name` has two occurrences, its definition and the directory walk
     that FINDS the file, and `tools/os88disk.py` writes it warm at image-build
     time. Merging volumes in RAM cannot corrupt a file nothing writes.
   - **32 rows is not enough, and the file's cap is not the store's.** Distinct
     package icons a machine can demand at once, measured over the shipped
     images: 9 with the system disk alone, **26** with system + apps, **29**
     with everything mounted - plus up to `ASSOC_NAPP` = 12 composed document
     bodies, one per app slot. `ASC_NAPP` is 32 and its own comment reads
     *"was 16, and the shipped apps disk holds 15 - one package of headroom,
     with no guard"*. The FILE stays at 32 rows, which is ample for one volume
     (the busiest holds 15); the STORE is sized for the machine at **48**.
3. **Purgeable.** A `MEM_P_` class below `MEM_P_VIEW`; refill on the next
   mount. The glyph table is NOT in it.
4. **Raise `DSK_NENT`.** The number is a product decision once it is nearly
   free; 64 is a net saving, 128 costs 384 bytes.

## 11. What the gates must say

- `tests/unit/t_lowwin.py` - the `.lowbss` window's ORDER, already exists.
- `kernel.asm`'s `SKB_DSK` assertion - recut per arm; it is written in terms of
  `DSK_NENT`, `DSK_DE_STRIDE` and `DSK_ICO_SIZE` and all three move.
- `files.inc:338`'s `VIEW_KB` assertion - recut.
- **A NEW ROW, and it is the one that matters**: two volumes mounted in turn,
  each carrying a copy of the same package, and the body stored ONCE - read off
  the guest, not off the screen. Break it by keying on the stem alone and watch
  two different packages collide; break it by keying on the size alone and watch
  the same package store twice.
- A row that lists a 68-entry DOS directory and asserts the store is EMPTY.
- `soak -k 'disp*'` for the drawing, which is the half a byte count cannot see.

## 12. What would kill it, and what is still open

- **The per-window mirror CAN drop its bodies - settled, and it is the reason
  the whole thing works.** `fmv_copy_in` already falls back to the global
  snapshot when a window's own claim was refused, so "paint from somewhere
  else" is a path that exists. What stops a BACKGROUND window using it today is
  that the global snapshot is the CURRENT mount: a window listing volume B
  cannot read bodies staged for volume A, and there has never been a
  volume-independent way to name one. **`(stem, size)` is exactly that name**,
  so a background window holding entries and reference bytes resolves every one
  of them against the shared store whatever is mounted now - which is strictly
  more than it can do today.
  The residual risk is EVICTION, not reach: a reference whose row has been
  purged resolves to the generic icon, which is SPEC.md 25's existing fallback
  and not a crash, and the row returns at the next mount. Sizing is what keeps
  it rare, and 29 distinct icons across the entire shipped set fit in 32 rows
  with three spare.
- **The hard disk's 64 entries come out of the DRIVER's 6KB claim**, so shrinking
  the listing there changes `HDD_LISTKB` and rebuilds a `.DRV`. Wave 5 only.
- **`ASSOC_NAPP` is 12 with five built-ins**, so a machine can know **seven
  learned document appearances at once**. THIS CONSTRAINT IS NOT NEW and it is
  not this work's - it is recorded here because the same measurement pass is
  what surfaced it, and because it may bind before the entry count does on a
  hard disk full of applications. **It is a FOLLOW-ON, to be researched once
  the icon work is done**: raise it to ~24, and the questions are what that
  costs `assoc_stem` (8 bytes a slot), `assoc_glyph` (8 more), `assoc_drv` and
  `assoc_clus`, whether `ASC_KB`'s 3KB still holds the file it implies, and
  what a machine with a hard disk full of applications actually needs. Nothing
  in waves 1-5 depends on the answer and nothing in it should be taken before
  they land.
