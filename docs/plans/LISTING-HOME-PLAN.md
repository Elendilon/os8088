# The global directory listing, and whether it has to be `.lowbss`

**OPEN, nothing built.** Measured on the tree at `49a4eec9`. It starts from a
size question — *what is `DSK_NENT` buying us?* — and the answer turns out to
be that the listing is not the file manager's cache at all, and that the
mechanism for moving it is **already in the kernel and already used**.

## 1. What it is, and what it costs

`disk_dir` is **the current directory as a kernel-wide snapshot**, not a
window's cache. `disk_mount` builds it; the per-window claims are COPIES of
it, not the other way round. `disk.inc`'s own comment names the invariant it
buys: *"`disk_dir` is ALWAYS exactly a mount snapshot, with no third staleness
rule anywhere in the kernel."*

| | `kern_big` | `kern_small` |
|---|---|---|
| `disk_dir` — `DSK_NENT` × `DSK_DE_STRIDE` | 64 × 24 = **1,536** | 32 × 24 = 768 |
| `dsk_icoix` — one reference byte per entry | **64** | 32 |
| | **1,600** | 800 |

`.lowbss` is **7,966** of an 8,704 rung with 226 left, and it sits BELOW
`HEAP_SEG`, so every byte there comes off the heap and off the DOS arena.

## 2. THE CENSUS, and three of the scary ones are not consumers

`ui.inc`, `assoc.inc` and `snd.inc` all mention `dsk_get_dir` and **none of
them reads the listing**: each says *"the `dsk_get_dir` idiom"* while
describing its own staging loop. `ui.inc`'s launch path is
`ldf_ld_run_name`, whose own comment is *"BY NAME: no listing to build and
none to refresh."* That was the first thing this study got wrong.

**And `OSAPI_FILE_FIND` does not read it either.** `api_file_find` →
`dsk_find_x`, which re-walks the directory off `[dsk_cwd]` through the sector
cache (SPEC.md 19.7.1). So **no package anywhere depends on the global
listing** and this is wholly a kernel-internal question.

The real readers:

| where | what it wants |
|---|---|
| `disk.inc` | builds it, and reads it back in the icon harvest's second pass |
| `files.inc` | Disk windows — and they already hold their own copies |
| `fdlg.inc` | the modal file dialog. `fdlg_rows` is `mov ax,[disk_nfiles]`, plus ~6 read sites, and it has NO store of its own |
| `loader.inc` | launch by directory INDEX |
| `hiber.inc` | two sites, and both want only *first cluster, by name* |
| `diskw.inc` | publishes the empty listing |

## 3. THE FINDING: the mount is ALREADY two-mode

This is what makes the whole thing tractable, and it is built, shipped and in
daily use.

`disk_mount` step 3 is behind `cmp byte [dsk_quiet], 0`:

  * **quiet** — the scan, the sort and the per-file icon harvest are all
    skipped. `[disk_nfiles]` goes to **0** (deliberately, because the buffer
    still holds the PREVIOUS volume's entries and a stale count is the one
    thing that could make a reader believe they are this volume's),
    `[dsk_lstale]` = 1 is the debt, `[dsk_mntok]` = 1 because the volume is
    still validated;
  * **loud** — the listing is built into `[dsk_dseg]:[dsk_doff]`, capped at
    `[dsk_nmax]`, and `[dsk_lstale]` is cleared.

`dsk_relist_x` pays the debt with a loud remount and is idempotent, which is
what lets the copy engine call it on every exit path.

**So "give the mount a target" is not a new mechanism.** The loud/quiet split
already decides WHETHER a listing is built; `[dsk_dseg]`/`[dsk_doff]`/
`[dsk_nmax]` already decide WHERE. Those three words were a per-VOLUME
destination until SPEC.md 22.6 retired the donated claim this cycle — the
change is to make them a per-CALLER destination instead, which is the same
indirection pointed at a different question. Every reader stays
byte-identical; `dsk_get_dir_x` already stages through them.

## 4. THE DESTINATION TABLE

`disk_mount_x` has exactly **three** call sites — `osapi_vol_mount_x`,
`dsk_chdir_x` and `dskw_remount_x` — so the question is really about who
drives `dsk_chdir_x`.

**Already quiet, and therefore need nothing:**

| caller | why it is quiet |
|---|---|
| `inst_vol_enter` — EVERY package file call | *"the sort and one icon-harvest read per file are all bought for nothing here"* |
| `drv_vol_back`, `assoc_back` | same terms |

**Loud today, and what each would name:**

| caller | destination |
|---|---|
| `files.inc` Disk-window navigation | that window's `FS_VSEG` claim — it already holds exactly this |
| `fdlg.inc` × 6 | **its own claim.** Modal and temporal, so it can afford one for its lifetime; it is also the heaviest reader, so it wants the full shape |
| `dskw_remount_x` / `dsk_relist_x` | whoever is standing — the acting window. With no window standing there is no consumer, so the debt need not be paid at all |
| `hiber.inc` × 2 | **none — BUILT (wave 1).** Both wanted first-cluster-by-name; `dskw_stat_x` answers the cluster in BX and the size in DX:CX off a directory walk. It was reached through `COLD_SEG:hbk_bp` already, so re-pointing it was the same shape at the same cost — and the DOS-handoff site collapsed two thunked far calls (find-then-stage) into one. `kernel.bin` byte-identical, `hiber.drv` −14. It went first because a resume runs with **no Disk window in existence**, so it is the one reader no window's cache could ever serve |
| `osapi_vol_mount_x` | **none obviously needed.** A driver mounts a volume; the desktop draws a zone; the listing is built when a window opens it |
| `osapi_file_goto` | **none — see §8** |
| `dskw_chdir_dl` | the write path's own |

`loader.inc` is not a mount caller at all, but it is a listing READER:
`ld_run_body_x` takes AX = a directory index, bounds it against
`[disk_nfiles]`, stages the entry, checks `[si+LD_DE_TYPE] == 1`, banks the
display name (SPEC.md 20.2's "which file did I come from") and takes the size
and first cluster. **Its index is an index into the listing the acting window
is showing** — `ld_pending` is a Disk window's row + 1 — so the window's own
cache is the right source and this is one of the easier conversions, not a
blocker. The by-name entry beside it reads no listing at all.

## 5. `.lowbss` -> a heap claim is NEUTRAL, and that is the owner's correction

A pinned claim is the same memory: `.lowbss` comes off the heap already. The
move buys something only if the block can **go away** — purgeable, or
transient with the consumer that asked for it.

Purgeable is not free the way the icon store is. `MEM_P_ICO` sits at
`MEM_PG_TRIV` because *"losing it costs a REDRAW, not a read"*; losing the
LISTING costs a **re-mount**, which is real `int 13h` work, so it wants a
higher rank and every reader has to survive it vanishing — which, usefully, is
the same predicate `[dsk_lstale]` already expresses.

**Transient-with-the-consumer is the shape this study prefers**, because §4
says every loud caller either has a window, can own a claim, or should not be
loud.

## 6. THE `.ovlw` CEILING, and it is exactly tight

`.ovlw` — the boot overlay's window half — is **loaded onto this region** and
`kernel.asm` guards it:

```
FAT window                               4,608
DSK_WIN_BYTES (secbuf 512 + 1,536 + 64)  2,112
ceiling                                  6,720
OVLW_SIZE 5,074, rounded to 512          5,120     headroom 1,600
```

Take `disk_dir` and `dsk_icoix` out and the ceiling is **5,120** against an
`.ovlw` that rounds to **5,120** — **zero headroom**. It fits by nothing at
all. So `.ovlw` bodies have to move into `.ovl` FIRST, and this is not
optional.

`.ovl` has **473 bytes** of blob left (`OVL_AT` 2,624 + `OVL_SIZE` 1,511 of
`BOOT2_PAD` 4,608). Past that, `BOOT2_SECS` goes 9 → 10.

**The cost of that is not boot time** — the blob is one contiguous read and an
`int 13h` is ~400 ms near enough whatever it moves. It is `KSIG_OFF`: the
canary must sit on a sector that crosses a head on all four geometries and the
file sector is the memory sector **plus `BOOT2_SECS`**, so the legal band
moves with the blob length (the Makefile tabulates it for 8 and 9).
`tests/unit/t_canary.py` is the gate. **The owner rates this low**: §18.93.1
is a fallback for a BIOS class nobody has yet produced, so re-deriving the
band is arithmetic rather than risk.

## 7. What it buys

**~1,600 bytes of `.lowbss` on `kern_big`**, three 512-byte rungs off
`LOW_PARA`, and every one of them is heap AND DOS arena byte for byte. On
`kern_small` it is 800.

## 8. A SIDE FINDING, ASKED AND REFUSED

**`OSAPI_FILE_GOTO` builds a listing no package can read** — and it must go
on building it anyway. It is a LOUD `dsk_chdir` (scan, sort, and one
`int 13h` per type-1 file for the icon harvest) where a package reads a
directory with `OSAPI_FILE_FIND`, which re-walks the disk itself;
`inst_vol_enter` afterwards finds the machine already standing there and does
nothing. Every step of that says the harvest is pure cost, and the obvious
conclusion — make the slot quiet — is **wrong**.

**The reader is not a package, it is the next Disk window to act.**
`fmv_sync` (kernel/files.inc:1231) takes its free path only when the acting
window's `(FS_DRV, FS_CWD)` already matches `[disk_drive]`/`[dsk_cwd]` **and
`[dsk_lstale]` is 0**; that third test exists precisely because a quiet mount
leaves the globals naming the right folder with `disk_nfiles` = 0 and the
rebuild owed, and resolving an index against nothing is the silent half of
docs/FIELD-NOTES.md 4. A quiet `OSAPI_FILE_GOTO` raises that debt. So the
package that navigates would not stop paying for the listing — it would hand
the bill to the **Disk window it was launched from**, which is standing in
that very folder in the common case, turning its next action's
compare-and-ret into a full mount.

That is not a saving moved, it is a saving lost: the loud walk happens once
per navigate, the sync's free path is taken on every action after it. **The
slot stays loud**, and the reason it is loud turns out not to be that nobody
asked.

The honest remainder is narrower and is not this plan's: the **icon harvest**
specifically has no reader in a package's navigate, only the scan and sort
do. Splitting the two would want a third mount mode, and §3's finding is that
two is what the mount has; a third is a mechanism to design rather than a
flag to pass.

## 9. Open, in the order they bind

1. ~~Does anything read the global between an `OSAPI_FILE_GOTO` and the next
   loud mount?~~ **ANSWERED, and the answer closes it**: `fmv_sync`'s free
   path does, through `[dsk_lstale]`. §8.
2. Where does `fdlg`'s claim come from, and what does it do when refused? The
   dialog is modal, so "paint from nothing" is not the graceful answer a Disk
   window has.
3. Is `dsk_relist_x`'s debt collectable when nobody is standing, or does the
   flag simply stay raised until someone loud arrives?
4. `.ovlw` -> `.ovl` first, and by how much, before any of the above.
