# Disk performance — the same-volume path

**Status: proposal. Nothing here is implemented.**

`docs/FIELD-NOTES.md` note 3 records the symptom — disk access on real
hardware feels far slower than the work being done should justify — and three
mechanisms visible in the source. This is the plan for those three. It was
produced while costing `docs/ASSOC-PLAN.md`, and the two are budgeted together
(§7).

The one-line summary: **a directory change on a volume that is already mounted
re-reads and re-validates everything about that volume, and every sector of it
is a separate int 13h.**

---

## 1. The three mechanisms

**A — `dsk_chdir` is a full `disk_mount`.** The body is four lines and the
middle one is `call disk_mount`, so moving between two folders on an
already-mounted volume re-validates the BPB against SPEC.md §18.2's 17 rules
and re-snapshots the FAT window. `dsk_chdir_q` (§18.9) skips the scan, the sort
and the icon harvest — and skips none of that.

**B — the FAT window is re-read every time.** `DSK_FAT_SECS` is 9, so that is
9 sectors per directory change on a floppy, for a FAT that cannot have changed
if nothing wrote.

**C — one int 13h per sector.** `dsk_xfer`'s `.sector` loop recomputes CHS and
issues `AH=02h` with **`AL = 1`**, three attempts with a controller reset
between, then `add bx, 512` and round again. On real hardware the next call has
missed the sector under the head, so consecutive sectors plausibly cost a full
revolution each — 200 ms at 300 RPM, against the ~200 ms *per track* one
multi-sector call would take.

Measured cost of one association resolution today (ASSOC-PLAN §2.5.1): **~35
sectors**, of which the one the caller actually wanted is 1.

---

## 2. Phase 0 — count it, before touching anything

**Binding, and first.** Everything below is a hypothesis from code reading;
PERFORMANCE.md's rule is that this container is ~1000× the target and useless
for timing but *exact about work*, and all three mechanisms are work. So:

- `inc word [cs:dbg_x]` at the top of `dsk_xfer`'s `.sector`, the `dw 0` in
  `.text`, offset from `nasm -l`, read over QMP with `xp /2xh` (the recipe is
  in CLAUDE.md).
- Baseline: boot, open Drive B, walk into `APPS`, back out, into `GAMES`.
  Record sectors per navigation.
- A second counter on `int 0x13` *calls* rather than sectors makes C's win
  measurable directly once Phase 1 lands: sectors stay the same, calls drop.

No phase below is judged on anything but that pair of numbers. Only C's
**cost per call** needs the XT.

## 3. Phase 1 — multi-sector transfers (mechanism C)

`AH=02h`/`03h` take `AL` = a sector count. Issue a run in one call, splitting
only where the hardware forces it. **This is not new ground in this tree:**
SPEC.md §52.1 records that *both* hard-disk transports already batch a run into
one command, and rung 0 — a BIOS CHS call, the same interface as the floppy —
already stops at exactly the two boundaries below. The floppy path is the one
that did not follow.

Split a run at:

1. **The end of the track.** A CHS call must not cross one; the current code
   recomputes CHS per sector and so never noticed.
2. **The 64KB physical DMA page.** This is the sharp one and it is a
   *regression risk introduced by this change*: today one 512-aligned sector
   per call cannot straddle a page, so the bug cannot occur. A multi-sector run
   can, and the DMA controller answers a straddle with error 09h. CLAUDE.md
   already records this failure arriving once before, as "a Disk error on any
   save big enough to reach the next 64KB boundary". `mem_claim_dma` (§50.3)
   holds the same rule for buffers; this is its transfer-side twin.
3. **`BX` overflow.** `dsk_xfer` walks `add bx, 512` and takes `ES:BX`, so a
   run must not carry past `0xFFFF`. `dskw_norm` (§18.4.1) already normalises
   the *file* path's destination to an offset of 0..15 and advances the
   segment; `dsk_xfer` itself still walks BX, so this is a per-call-site
   question and must be checked, not assumed.

**Retries change shape and must be got right.** Today three attempts are per
sector. A multi-sector call that fails does not reliably report how many
sectors landed, so the retry unit becomes the **run**: reset the controller and
re-issue the whole run, and after three failures fall back to per-sector for
that run so a single bad sector still yields the sectors around it. Losing that
graceful degradation would trade speed for data recovery on ageing media, which
is the wrong trade on machines this old.

## 4. Phase 2 — bank the floppy's FAT window (mechanism B)

**The policy already exists and already permits this.** `dsk_fatw_pick` states
and enforces the rule verbatim: *"Only a QUIET mount may reuse a banked window.
A full mount is a re-validation of the whole volume — the disk may have been
swapped."* §18.8.1 banks a window per **driver-backed** volume for exactly this
reason ("45 mounts, 3 loads"). A floppy is excluded not by a correctness
argument but because it has no donated claim to bank *into* — and its window is
`FAT_SEG`: resident, and by §18.8.1's own reasoning never sliding.

So what is missing is **permission, not machinery**: let a quiet mount reuse
`FAT_SEG` when it already holds this volume's FAT. That needs one byte
recording whose FAT is loaded — check `dsk_fatw0`/`dsk_fatd0` first, they may
already carry it.

Three traps, all of which the driver-backed path already survives and which are
therefore already written down:

- **A: and B: share `FAT_SEG`**, so a volume *switch* must still load. That is
  what the identity byte is for, and it is the whole difference from a
  driver-backed volume, which owns its claim.
- **A dirty window must be flushed at a switch, not carried** — `dskw_flush`
  later would write volume-relative LBAs to the wrong disk (§18.8.1's own
  trap).
- **`dskw_refat`'s invalidate must still reach it.** The write path's rollback
  rule (§18.4 rule 2) is that any failure before the commit re-reads the FAT
  off the disk; a window that now believes itself valid would defeat exactly
  that.

## 5. Phase 3 — the same-volume quiet chdir (mechanism A)

Skip the boot sector read and the BPB re-validation when **all** of: the mount
is quiet, the volume index is unchanged, and `[dsk_mntok]` is set.

**The sharp edge is that this is a bigger claim than Phase 2 wearing the same
clothes.** Phase 2 reuses a *snapshot* on a quiet mount; this skips the
*validation* that decides whether the disk is the one we think it is. The
argument that it is nevertheless the same claim: if the disk was swapped, the
reused FAT window is already wrong, so a quiet mount has *already* been granted
that trust by `dsk_fatw_pick`. Consistency says either both are safe or neither
is — and the tree has shipped the first for a release.

That argument should be written into SPEC.md §18.9 explicitly rather than
inferred, and the media-change line (int 13h `AH=16h`) noted as the honest test
on hardware that implements it — which many XT-class floppy controllers do not,
which is why the rule leans on *quiet* rather than on the hardware.

**A full mount is untouched.** Everything a user can reach that re-lists —
opening a Disk window, Refresh, a drive change, a volume switch — still
re-validates from the disk. This phase only makes the OS stop re-proving a
volume to itself in the middle of an operation it is already inside.

## 5.5. Mechanism D — the icon harvest re-reads every package, every mount

**Found while planning associations, and it is a fourth mechanism for
FIELD-NOTES 3 rather than a consequence of that work.** It is here and not in
`docs/ASSOC-PLAN.md` because it slows the OS as it stands today.

`disk_mount` step 4 reads the **first sector of every type-1 file in the
directory** to harvest its icon. Three facts about it:

- **It is already conditional and correctly so.** A type-0 file gets no read
  at all (the slot stays the all-zero sentinel), and a folder gets
  `dsk_folder_ico` out of `.text`. Only a validated `.O88` is read. There is
  no waste *per file* to remove here.
- **The waste is per MOUNT.** The harvest runs on the current directory every
  time, and §5's mechanism A means every directory change is a mount. `APPS/`
  holds **8** packages and `GAMES/` **5**, so entering `APPS/` costs 8 extra
  sector reads — at mechanism C's revolution apiece, **~1.6 seconds every time
  you open that folder**, and again every time you come back to it.
- **It re-reads icons the kernel may already have.** With ASSOC-PLAN §2.5's
  baked glyphs, the kernel ships knowing what four of these files look like
  and reads them off the disk anyway.

**The cheap partial fix is a fingerprint, and it is nearly free.** The staged
entry already carries name and size, so `stem + size` identifies "this is the
build I know" at zero I/O (ASSOC-PLAN §2.5). Skip the read when it matches.
**But it only pays where the kernel holds the full icon**, and the baked thing
is the 8×8 *reduction* — 8 bytes, for composing document icons. Drawing the app
in a listing needs the full **16×16**, 64 bytes, so skipping the harvest for
all 13 shipped packages means baking **832 bytes** into the kernel: a quarter
of the grant, to speed up shipped disks only, duplicating bytes that are
already on the floppy.

**The better fix is the one already chosen for associations: put it on the
disk.** `ASSOC.DAT` becomes a per-volume desktop database carrying the full
16×16 icon per package keyed by (stem, size) — read **once per volume per
session** instead of 8–13 reads per folder mount, covering user-added packages
as well as shipped ones, and written warm by `tools/os88disk.py`, which already
places every `.o88` and knows its icon. The 8×8 glyph is derived from the 16×16
by the same majority reduction, so only one of the two is ever stored.

### 5.5.1 The rule: hit skips, miss harvests

Per type-1 entry in the directory, look up its `(stem, size)` fingerprint in
the loaded cache:

- **Hit** → copy the cached 64-byte icon into `disk_icons[i]`. **No read.**
- **Miss** → harvest exactly as today (read the file's first sector), and mark
  the cache **owed**.

That is what keeps a new package working: a file the cache has never seen is
harvested the first time and written into the cache after, so it is free from
then on. It also means the cache can never be *wrong* in a way that matters —
a modified file has a different size, misses, and re-harvests.

**One heal rule now covers the whole file.** The associations already heal on a
miss (ASSOC-PLAN §2.5.2); icons heal on a miss the same way, at the end of the
mount that discovered them, into the same `ASSOC.DAT`. One write trigger, one
file, one discipline.

Two limits worth stating rather than discovering:

- **The cache is capped** (16 packages is the proposal). A volume with more
  gets the first 16 cached and the rest harvested every mount — slower, never
  wrong. No eviction policy, because a policy that thrashes is worse than a cap
  that is understood.
- **Stale rows for deleted files are harmless.** Lookups are driven by the
  listing, so a row nothing names is never consulted; it costs its bytes and
  goes when the file is next rewritten.

### 5.5.2 Where it lives: one buffer, not six

DVOL_MAX is 6 — A:, B: and up to four partitions (§52.2) — so a claim *per
volume* at ~1.25KB each is up to **12KB of heap**, which on the 128KB floor
machine is over a fifth of everything above the kernel. The configuration that
costs the most (four hard-disk partitions) is the one least likely to appear on
that machine, but that is a reason not to worry, not a reason to spend.

**Take one shared buffer plus a volume-identity byte instead: ~1.25KB total,
reloaded on a volume switch.** The tree has already made this exact decision
once, for the FAT window — shared by default, per-volume *only* where a driver
donates the claim, and §18.8.1 spells out why that escalation existed: a copy
alternates between two volumes, so the window was being reloaded constantly.

**That reasoning does not transfer here, which is the point.** A copy never
consults this cache: `dskw_find` and `fcp_scan` walk directory sectors
themselves, and `dsk_chdir_q` skips the harvest entirely (§18.9). The icon
cache is read only on a **full** mount — a user navigating — so the alternating
case that justified per-volume FAT windows has no counterpart. If profiling
ever says otherwise, per-volume is the same escalation and it is already
written down.

Three tiers, each degrading into the next, which is the §50 discipline:

| tier | when | cost per mount |
|---|---|---|
| resident cache | claim held, right volume | **0 reads** |
| claim refused | `mem_claim` said no | 3 reads — scan the file a sector at a time out of `dsk_secbuf` |
| no `ASSOC.DAT` | fresh or foreign disk | today's behaviour, 8–13 reads |

### 5.5.3 What still has to be decided deliberately

- **The file grows past one sector.** ~80 bytes a row is ~3 sectors for 16
  packages against `ASSOC.DAT`'s single sector today — far better than 13
  scattered first-sector reads, but no longer one read.
- **It changes `disk_icons`' contract**, which SPEC.md §18.3 step 4 and §29.1
  both describe as harvested fresh every mount. A cached source needs that
  wording changed deliberately, not by implication.
- **`ASSOC.DAT` now serves two consumers with different lifetimes**, and
  conflating them would be easy: the *association* rows merge into the global
  `.text` table and live for the session across every volume, while the *icon*
  rows serve the current volume's mount and are dropped on a switch. One file,
  two sections, two lifetimes — say so in SPEC.md.

**Sequencing:** after Phases 1–3 and after ASSOC-PLAN Phase 3, both because it
builds on `ASSOC.DAT` and because Phase 1's counters are what say how much of a
folder-entry really is the harvest as against the mount around it. Take the
fingerprint (ASSOC-PLAN §2.5, ~50 bytes) regardless — it earns its place
validating the baked glyphs whether or not any of this lands.

## 6. What must not break

- **The write path's commit order and rollback** (§18.4 rules 1–3), which is
  the one place a wrong FAT costs a cross-link rather than a redraw.
- **"A torn mount is a failed mount"** — every failure path must still land at
  the root with `[dsk_mntok]` shut.
- **Both geometries** (1.44M/18 spt and 360K/9 spt) and **both transports**
  (BIOS and a `DRVC_DISK` driver), since Phase 1 touches the shared
  `dsk_xfer` and the driver branch sits above it.
- **Fragmented chains** — `dsk_read_chain`'s run coalescer is what feeds
  Phase 1 its runs, so a file a host OS wrote back fragmented is the
  interesting case, not the boring one.

## 7. Testing

| what | how |
|---|---|
| the counters | Phase 0's pair, before and after each phase |
| the write path | `tests/filetest`, plus the `-frag` image (docs/TESTING.md) |
| structural correctness | `python3 tools/os88disk.py --verify <img>` from the host, after every write test — the in-kernel free-space check and the host fsck catch different bugs |
| fragmentation | `tools/os88disk.py --scramble` |
| the felt speed | `make xt` / `make xt-640`; this is the only test that answers the field report |
| the other transport | `make test HDD=40` |

**The standing trap:** QEMU mounts `build/apps.img` and `build/os8088.img`
writable and the OS writes to them, so any test that saves or deletes dirties a
tracked, shipped artifact. `rm -f build/apps.img build/apps360.img
build/os8088.img build/os8088-360.img && make` before committing, and
`make check-images`.

## 8. Budget

Estimates, in the same currency as ASSOC-PLAN §8, against a `KERN_BUDGET`
raised to **78,336** (§9):

| item | est. bytes |
|---|---|
| Phase 1 — run splitter, multi-sector call, run-level retry with per-sector fallback | ~100 |
| Phase 2 — the identity byte and the quiet-reuse branch | ~40 |
| Phase 3 — the same-volume guard | ~60 |
| Mechanism D (§5.5) — the fingerprint lookup, the tiered reader and the heal | ~180 |
| **total** | **~380** |

Mechanism D's ~1.25KB buffer is a **heap claim, not footprint** — it does not
touch `KERN_BUDGET` and it is refusable, which is what makes the middle tier in
§5.5.2 a real path rather than a courtesy.

Phase 1 may come in near zero net: it deletes a per-sector CHS computation and
a per-sector BIOS call in exchange for a per-run splitter. It is not counted as
a saving because the retry fallback is new code that has no counterpart today.

## 9. The budget decision

`KERN_BUDGET` **76,288 → 78,336** (+2,048), asked for and granted to cover this
plan and `docs/ASSOC-PLAN.md` together: ~380 here and ~1,590 there against
1,536 spare, which the two do not fit. Spare after both: ~1,560.

Per CLAUDE.md and the constant's own comment, the raise **lands with the first
commit that needs it, not before** — a raised guard with nothing spent under it
is the "guard switched off" failure the fifth (downward) move exists to
document. The comment in `kernel/kernel.asm` gains the seventh entry, and
`docs/KERNEL-MEMORY.md` is re-derived by its own bisect recipe rather than
edited to a guessed figure.

It costs the machine nothing: `HEAP_SEG` is `KERN_END`, so the heap starts
where the kernel actually ends and never where the budget says it might.
