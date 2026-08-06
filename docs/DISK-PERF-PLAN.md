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
| **total** | **~200** |

Phase 1 may come in near zero net: it deletes a per-sector CHS computation and
a per-sector BIOS call in exchange for a per-run splitter. It is not counted as
a saving because the retry fallback is new code that has no counterpart today.

## 9. The budget decision

`KERN_BUDGET` **76,288 → 78,336** (+2,048), asked for and granted to cover this
plan and `docs/ASSOC-PLAN.md` together: ~200 here and ~1,340 there against
1,536 spare, which the two do not fit.

Per CLAUDE.md and the constant's own comment, the raise **lands with the first
commit that needs it, not before** — a raised guard with nothing spent under it
is the "guard switched off" failure the fifth (downward) move exists to
document. The comment in `kernel/kernel.asm` gains the seventh entry, and
`docs/KERNEL-MEMORY.md` is re-derived by its own bisect recipe rather than
edited to a guessed figure.

It costs the machine nothing: `HEAP_SEG` is `KERN_END`, so the heap starts
where the kernel actually ends and never where the budget says it might.
