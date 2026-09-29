# STREAM-WRITER-PLAN - writing a big file without paying for it again every chunk

**Status: OPEN. Stage 1 BUILT on branch `stream-writer` (SPEC.md
18.4.7.6); stages 2 and 3 not started.** This is docs/plans/DISK-CPU-PLAN.md §6 taken on. That
section named the write side and sketched a fix's SHAPE; this is the design,
staged, with what each stage costs and what it must not break.

It exists because the same defect has now come up **four times in two days
of sessions**, each time from a different program, and each time it was
written down as someone else's problem:

| where it surfaced | what was seen |
|---|---|
| VIDDISK `W` on the owner's ST-225 (docs/reports/VIDDISK-ST225-2026-09-27.md) | 12.8 MB in 400 appends of 32 KB: **700 s, 18.2 KB/s**, against 104-110 KB/s reading the same disk |
| FTPD `STOR` (DISK-CPU-PLAN §6.2) | a large upload slows down as it goes - estimated ~230 s of walking in 5 MB |
| the file manager's copy and the installer (DISK-CPU-PLAN §6.2) | chunked writes, same walk, same commits |
| Uncompress To... joining `OS8088.001` onto the ST-225 (branch `split-v88`, not yet on this one) | once the floppy stopped, the hard disk ground with far more head movement than the data explained |

## 1. What one append costs today - MEASURED

`OSAPI_FILE_APPEND` is `OSAPI_FILE_WRITE_AT` at the file's size (SPEC.md
18.4.7.3), and every call is a complete, committed operation by contract.
The owner's layout on MartyPC (`os8088_xt_hdd_720`: booted from C:, a 720 KB
part in A:, the result on C:), every `int 13h` of an Uncompress To...
logged with its cylinder, head and sector. One 32 KB append on the fixed
disk, in the tail where the floppy is no longer read:

| # | transfer | where | why |
|---|---|---|---|
| 1 | read, 3 sectors | cyl 1 | the NAME is looked up again (`dskw_find`): the directory |
| 2-5 | write, 64 sectors in 3-4 calls | cyl 13-15 | the data |
| 6-7 | write, 1 sector each | cyl 0, FAT1 and FAT2 | flush #1: the new sub-chain durable, unlinked |
| 8-9 | write, 1 sector each | cyl 0, **the same two sectors** | flush #2: the link to the old last cluster |
| 10 | write, 1 sector | cyl 1 | the directory entry: the new size |

Three long seeks per 32 KB (directory -> data -> FAT -> directory), and five
small metadata transfers, two of which rewrite exactly what the two before
them wrote. On a volume whose free space is far from cylinder 0 - any full
ST-225 - every one of those seeks is a full stroke. This is what the owner
heard.

And the CPU half, which that trace cannot show: step 1's lookup and a walk
of the cluster chain **from the front to its last cluster**, every call
(SPEC.md 18.4.7.3), so a file written in chunks costs time QUADRATIC in its
length. READ_AT measured that walk at **141.9 ms per MB** of offset
(SPEC.md 18.4.8); VIDDISK `W` on the ST-225 puts ~400 of its 700 s there.

## 2. The three costs, and which lever takes each

| cost | grows with | lever | stage |
|---|---|---|---|
| the duplicate FAT flush | calls | flush ONCE when the whole FAT update is one sector | 1 |
| the name lookup + the chain walk | calls x file length | a CALLER-KEPT cursor, READ_SEQ's mirror | 2 |
| the per-call commit (FAT + entry, 3 seeks) | calls | commit once per FILE, not once per call | 3 |

They are independent and each is worth having alone. They are ordered by
risk: stage 1 changes no contract, stage 2 adds a slot and keeps every
contract, stage 3 changes WHEN the disk is consistent and so needs a
decision from the owner before it is built.

## 3. Stage 1 - one FAT flush when one will do

**Why there are two.** SPEC.md 18.4's commit order: the data, then the FAT,
then the entry, so a crash leaks clusters rather than corrupting a file. An
append at the end refines that for the FAT itself: flush the new sub-chain
(allocated, terminated, unreachable), THEN set the link from the file's old
last cluster and flush again. A flush writes the dirty RANGE of FAT sectors
in one multi-sector transfer, and a power cut part-way through one of those
can land some sectors and not others. If the link's sector lands and the
new chain's does not, the file's last cluster points into clusters the disk
still shows FREE - and the next allocation hands them to another file. That
is a cross-link, the one failure the order exists to rule out. So the two
flushes are deliberate, and correct.

**Why one is enough when the update is one sector.** A sector is written
whole or not at all. When the link and every new entry share ONE FAT sector
(per copy), flush #1 and flush #2 write the same sector, and the second write
is the whole update: there is no partial state for the first to guard. That
is the common case by a wide margin - a 32 KB append on a 2 KB-cluster disk
is 16 FAT16 entries, 32 bytes, beside the link - and it is exactly what the
trace shows being written twice.

**The rule:** after the data is written and the sub-chain allocated, set the
link FIRST if the dirty range (with the link's entry in it) is exactly one
sector, and flush once. Otherwise keep today's two flushes. FAT12's entries
straddle sectors, and a straddling link makes the range two sectors, which
takes the safe path by the same test.

**BUILT (SPEC.md 18.4.7.6)**: 81 bytes of `.cold` on each kernel,
resident. MEASURED over eleven 32 KB appends of VIDDISK's W on MartyPC
(`VD_TRACE=12 tests/viddisk.py --floppy`): one-sector writes **5.2 -> 3.2**
an append, data writes 3.3 and the directory read 1.0 unchanged. W's time
575 -> 570 guest seconds, because MartyPC's XT-IDE makes a write cheap and
the walk is what W pays for there; on the ST-225 each saved write is at
least a revolution. It does nothing about the seeks: those are stage 3's.

## 4. Stage 2 - `OSAPI_FILE_WRITE_SEQ`, the cursor (`kern_big`)

READ_SEQ's design (SPEC.md 18.4.8) carried over, with one thing more to keep.

**The cursor is the CALLER's, 16 bytes, a cache the kernel can always
rebuild from the name.** It holds the mount generation it was seeded under,
the volume, the file's LAST cluster, its size - and, because a write must
update the ENTRY, where the entry is: its directory sector and slot. A call
with a valid cursor:
- skips the name lookup (step 1): the entry's place is in the cursor;
- skips the walk: it links forward from the cursor's last cluster;
- allocates, writes, commits as stage 1 does, and hands the cursor back
  with the new last cluster and size, stamped with the generation the
  write itself produced.

**The generation needs one decision READ_SEQ did not.** Every write bumps
`[dsk_mgen]` in `dskw_sync_x` so that every READ_SEQ cursor re-seeds. A
WRITE_SEQ cursor must survive ITS OWN write, so the wrapper re-stamps it
after the call with the generation that call produced. Any OTHER write, a
remount or a media change still invalidates it, and the next call re-seeds
from the name: one lookup and one walk, which is what APPEND pays every
time today.

**What it does not change:** every call is still a complete, committed
operation. A crash between calls loses nothing that was acknowledged.

**Consumers**, in the order they are worth converting:
1. the split-set join (`Uncompress` and `Uncompress To...`, branch
   `split-v88`) - kernel-side, `CLONE.DRV`,
   through the far door the module already uses for APPEND;
2. the file manager's copy (SPEC.md 22.5) - kernel-side;
3. FTPD `STOR` - a package, through the new slot;
4. VIDDISK `W` - the instrument, so the ST-225 figure can be re-taken.

`kern_small` gets the cell and a refusal, as READ_SEQ did (SPEC.md 20.8
rule 4), unless the stage-1 measurement says the small machine's chunked
writers (the copy) need it too. That is a question for the numbers, not a
default.

## 5. Stage 3 - commit once per file (DECIDE FIRST)

This is Set 24's lever: the same bytes as 8 KB appends against one write
cost **2.36x on the floppy and 3.81x on the ST-225** (PERFORMANCE.md),
before any file was large enough for the walk to matter. With stage 2 in, it
is also the only thing left between a chunked write and the disk's own
sequential rate, because it is the three seeks per chunk.

The shape: a WRITE_SEQ cursor may be opened HELD. A held call writes the
data and extends the chain in the FAT window, but does not flush the FAT
and does not store the entry. Those happen once, at a CLOSE - and at every
point where the machine could lose track of them:
- the FAT window has to move (it already flushes then);
- the batch bracket ends (SPEC.md 18.9.3: `gfx_unlock`), which is the moment
  the user is allowed to touch anything, including the floppy;
- any other file operation on that volume.

**What it changes is the contract**: between calls, the disk does not yet
show the file's new length. A crash loses everything written since the last
commit (the data is there, unreachable). It can never cross-link, because
the close writes chain-then-link as stage 1 does, and nothing else runs.

**The decision it needs**: whether a held write may span a PROMPT. The
join's `Put FILEA.002 in A:` ends the batch, so under the rule above the
join commits at every prompt. That is correct and costs one commit per part
rather than one per file, which is still ~20x fewer than today on a 720 KB
part. Holding across a prompt would mean trusting that the user does not
take out the TARGET disk while being asked for a SOURCE disk; that is
UI-FREEZE-PLAN §3.2's removable-media consistency model, and it is not this
plan's to change.

## 6. What each stage must be measured against

- **The transfer trace** of one 32 KB append on the fixed disk (§1's table):
  10 transfers and 3 long seeks today. Stage 1: 8 and 3. Stage 2: 7 and 2
  (no directory read). Stage 3, held: 3-4 (the data) and 0 between commits.
- **VIDDISK `W`** (`tests/viddisk.py --floppy`, the `viddiskfd` row):
  guest seconds to write 12.5 MB in 400 appends. On MartyPC's XT-IDE, which
  moves bytes with the CPU, so its transfer rate is not the ST11M's; the
  WALK is CPU either way and this is where stage 2 shows.
- **An fsck** (`tools/os88disk.py --verify`) of every volume a gate writes.
- **The ST-225**, for the number that started this: 700 s for 12.8 MB.

## 7. What this plan does NOT do

- It does not make writes asynchronous. The UI task still does the disk;
  the freeze is SPEC.md 18's model, and UI-FREEZE-PLAN owns it.
- It does not add a handle table or an open-file model. The cursor is the
  caller's, as READ_SEQ's is, precisely so that there is no kernel state a
  second writer or a remount could leave stale.
- It does not touch the read side, which READ_SEQ already fixed.
