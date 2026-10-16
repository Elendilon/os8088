# Writing back what the machine learned: `ASSOC.DAT` at runtime

**Status: PLAN. Nothing here is built.** Figures are taken against
`elendilon` at `08ca1c2`. A figure marked **ESTIMATE** is counted from
instruction lengths or from a comparable routine and has not been assembled.
Every other figure was read off that build.

The ask, in the owner's words:

> Right now when we discover new associations, they live in ram only. The
> next time we reboot, or flush, they are gone and we have to re-discover
> them the expensive way. Plan a way to flush newly seen associations to
> assoc.dat at runtime. This should cost as few resident kernel bytes as
> possible. The 360k system disk is nearly out of space.

## 0. The answer in one paragraph

**The writer already exists, and only the installer can reach it.**
`hd_iassoc`
(`drivers/hdd/iassoc.inc`, SPEC.md 52.10.14) rebuilds a volume's
`ASSOC.DAT` from what is actually on it. It is 984 bytes of code and 56 of
data, and it lives inside `HDDTOOL.DRV`, where only the hard-disk installer
can reach it. The plan moves that algorithm into an on-demand kernel module
(`FORMAT.DRV`, the smallest of them), with one change: it **reuses the rows
the volume's old file already holds** instead of re-reading every package.
The resident kernel keeps only three things:

- a post at the one point where the mount learns something its cache did
  not hold;
- a two-compare dispatch on the UI task's existing document-open step;
- the module stub.

That is **~50 resident bytes** (ESTIMATE, all `kern_big`; `kern_small`
byte-identical). A resident writer would cost ~900. Wave 2 points the
installer at the same module and deletes `hd_iassoc` from `HDDTOOL.DRV`.
After that, the tree has one runtime writer of the format instead of two,
and **the 360KB system disk comes out a cluster lighter than today**, not
heavier.

---

## 1. What is learned at runtime, and where it is lost

Four things teach the machine an association or the facts behind one. All
four land in RAM, and RAM is what a reboot and a heap shed (SPEC.md 25.9.2)
take away:

| what is learned | where (today) | lands in | why it is lost |
|---|---|---|---|
| a package's **icon, document glyph and §54.6 declarations**, from a package `ASSOC.DAT` does not hold | the mount's harvest, `.h_read` in `kernel/disk.inc`: one `dsk_peek_x` per such package, on every first mount of its folder in a session | the icon store (`ico_put`), `assoc_ext`, `assoc_glyph`, the slot's hint | the store is purgeable and per-session; the tables are per-session |
| **where a program is**, found by a sweep | `assoc_locate`'s `.found` (SPEC.md 54.4.2): quiet mounts, so no harvest | `assoc_drv`/`assoc_clus` | per-session |
| a **stale row corrected**: a cluster the file names that no longer holds the program | the same `.found`, after rung 1 misses | the same hint | per-session, and the file keeps the stale cluster for ever |
| a **runtime claim**, `OSAPI_ASSOC_SET` | the claiming package (SCRIBE, CWORD, APPLE2) | `assoc_ext` with `ASSOC_STICKY` | per-session, **by design** (§5.6) |

Not persisting these costs three things, and they recur on every boot:

1. **Sector reads.** Every package a volume's cache does not hold costs one
   `int 13h`-class read on the first mount of its folder in each session
   (~400 ms on the target, PERFORMANCE.md). That is mechanism D's whole
   saving given back (SPEC.md 54.7).
2. **Bare document pages.** A declared extension is known only once its
   program's header or its volume's cache has been read (SPEC.md 54.7.3).
   So `.TEX` and `.HTM` documents in `MEDIA\` draw the bare page until
   `APPS\` has been browsed, on every boot, on any disk whose cache lacks
   those rows.
3. **Sweeps.** A program the cache does not place is found by sweeping. That
   was 2,335 ms with an empty A: in SPEC.md 54.4.2.1's measurement, and the
   sweep runs again on the next boot.

**Which disks this is about.** Every shipped floppy arrives warm, because
`tools/os88disk.py` builds the file. So does every installed volume
(`hd_iassoc`). The disks that are **cold** or **stale** are the rest:

- a disk a user copied packages onto, or onto which The Wire's *Add to Disk*
  wrote one (SPEC.md 92);
- a disk DOS formatted;
- an installed volume whose programs were updated or added after the
  install, since every edit changes a package's size and the `(stem, size)`
  key then misses;
- a volume onto which DOS moved a program, which leaves a stale cluster.

**A finding on the way, recorded and not acted on.** An **iconless** package
is read again on every mount of its folder, whether or not `ASSOC.DAT` holds
it. Since SPEC.md 54.7.4 the cache is absorbed into the icon store, and
`asc_row_take` skips a blank body (`asc_inkck` / `jz .out`). The harvest's
iconless arm never calls `ico_put` either. So nothing stores the absence,
which §54.7's *"caching the ABSENCE saves that read too"* still promises.
Four packages in the tree are iconless (`CHART`, `HELLO`, `IMGTEST`, `WIRE`),
and of those only CHART ships on the apps disks. It matters to this plan in
one place: §3.2 has to choose a trigger that an iconless package cannot
fire on every mount.

## 2. The writer that already exists, and why it cannot be called as it stands

`hd_iassoc` was written for SPEC.md 52.10.14's defect: a copied cache whose
clusters named the floppy. It does exactly the job asked for here:

1. walk the volume's root and one level of folders (`build_assoc`'s shape);
2. for each package, read its first cluster, validate it (`'O8'`,
   `PKG_FMT`), and take a row (stem, size, folder cluster, icon, glyph);
3. take the package's usable declarations as association rows;
4. order declaring packages first, so that the `ASC_NAPP` = 32 cap drops a
   cached icon and never an association;
5. write the file hidden + system through `OSAPI_FILE_WRITE_SYS`, silently,
   leaving no file rather than a wrong one when anything refuses.

**It is the right algorithm for a reason that matters more at runtime than
at install.** It reads the volume it writes about, so it cannot write a
cache that describes a different disk. A floppy swapped between the
harvest and the flush gets a file built from the floppy that is actually
in the drive (§6.1 covers the one window where that fails).

**It cannot be reached from the kernel as it stands**, and moving it is
cheaper than making it reachable:

- `HDDTOOL.DRV` is `HDD.DRV`'s private half. It is loaded by that driver,
  versioned against it (`HD_ABI_VER`), and handed the resident's dispatcher
  at `HDT_INIT`. The kernel does not know it exists (`hddabi.inc`'s
  header).
- It is **13,414 bytes on disk**. Loading it to run a thousand of them is a
  ~13KB claim and a ~27-sector read on the target.
- It speaks the driver ABI (`os88_ent`, `OSAPI_FILE_FIND_RAW`,
  `OSAPI_FILE_READ_AT` of a whole cluster). A kernel module reaches the same
  internals directly, and that is where most of the savings in §3.5 come
  from.

## 3. The design

### 3.1 The shape: three things resident, the rest in a module

The rule is docs/plans/completed/ONDEMAND-PLAN.md §1 and `kernel/mod.inc`'s
header: resident code is the decision and the thunk, and the work lives in
a file read into a heap claim when it is wanted and freed afterwards. Moving
code to `.cold` relieves `KERN_CODE_MAX` and nothing else, so it is not an
answer here (CLAUDE.md: `.cold` is resident).

| part | where | ESTIMATE |
|---|---|---:|
| `asc_post`: post a flush of volume AL unless that volume has refused one this session | `.cold`, `kernel/assoc.inc` | 16 |
| its call in the harvest, on the store-take arm (§3.2) | `.cold`, `kernel/disk.inc` | 6-10 |
| the dispatch at the head of `assoc_run_x` (§3.4) | `.cold`, `kernel/assoc.inc` | 12-16 |
| the module stub: `dskw_fmt_go`, the far call, the drop | `.cold`, `kernel/diskw.inc`, beside the formatter's four | 10-16 |
| `FM_NENT` 4 -> 5 | `.bss` (`FMFP`, SPEC.md 2.8.1: an entry is 4 bytes) | 4 |
| `asc_wno`, the refused-volume byte, initialised 0xFF | `.text` | 1 |
| **total** | | **~49-63** |
| *optional:* the location trigger in `assoc_locate`'s `.found` (§3.2) | `.cold` | *~20* |

**Against what:** the writer itself, assembled resident, would be about what
`hd_iassoc` is, ~900-1,000 bytes. The module form leaves ~95% of the feature
on the disk.

**The rung, said honestly** (CLAUDE.md's banner, and not as a design input).
At `08ca1c2` the cold rung has **34 bytes left**, so ~50 bytes of `.cold`
would bill a 512-byte step: `KERN_SIZE` 98,304 -> 98,816 against
`KERN_BUDGET` 100,864, with 2,048 left. The concurrent size pass will move
that figure before this lands. The plan's number is the **~50 bytes**, not
the step.

**`kern_small` is byte-identical.** The whole of SPEC.md 54 is behind
`OS88_ASSOC` (SPEC.md 54.0). The module entry goes inside `%ifdef
OS88_ASSOC` in `.modf`, so `kern_small`'s `FORMAT.DRV` does not change
either. `kern_dos` (`KD_BUILD`) carries no `.modf` at all.

**Why `FORMAT.DRV`, and not `DISKOPS.DRV` or a new file.** Three reasons,
in order of weight:

1. **It is the cheapest image to load.** A flush pays for its module load
   every time. `FORMAT.DRV` is a 1,136-byte image in 3 sectors.
   `DISKOPS.DRV` is 10,099 bytes in 20 sectors.
2. **A new module file costs resident bytes a new entry does not**: a
   `mod_tab` row (4), its name string (~12), a `MODFP` block, and a
   directory entry and at least one cluster on every system disk.
3. **It is the module that already prepares disks.** A volume's index is
   part of the disk, not part of a program.

### 3.2 The trigger: post only where the cache was proved WRONG

The tempting trigger is "the harvest missed" (`ico_ref_try` answering
CF=1). That trigger **thrashes**:

- An iconless package misses on every mount (§1's finding).
- A full store misses on every mount for every package it did not take.

Either case would post a flush on every navigation, and each flush would
load the module, walk, find nothing new and write nothing.

**The trigger is the store-TAKE instead**: the arm in `.h_read` where
`ico_put` answered with a real row (`cmp al, ICO_R_NONE` / `je .h_noglyph`
already branches there). That arm means exactly one thing. `asc_use_x`
absorbed this volume's file at the top of this same harvest (SPEC.md
54.7.4), so a body that **was not** already in the store and **was** taken
now is a `(stem, size)` the file does not hold. Three results follow:

- iconless packages never fire it;
- a full store never fires it;
- the second mount of the same folder never fires it, because the store
  holds the body by then.

So a folder posts **at most once per session**, and only while it is holding
something the cache lacks.

**What it does not see, deliberately.** A package whose body the store
already holds *from another volume* is a hit, so no post. Its icon costs
nothing this session, and the next boot's first mount of this volume
misses on it and posts then. That is self-healing within one session, and
the alternative costs bytes on the hot path.

**The location trigger (optional, priced separately, ~20 bytes).**
`assoc_locate`'s `.found` calls `asc_use_x` and then `assoc_hint_here`. In
between, the slot's hint is whatever the volume's own cache said. If that
is not `([disk_drive], [dsk_cwd])`, then either the cache did not know where
this program was or it was wrong, and both are worth a flush of
`[disk_drive]`. This is the only path that learns a **location** without a
harvest: quiet mounts skip the harvest (SPEC.md 18.9), and the sweep is
made of quiet mounts. It also corrects SPEC.md 54.7.1's stale-cluster case
on disk. Without it, a program found only by sweeping, in a folder nobody
browses, is swept for again on every boot. Take it if that case is worth
20 bytes; §8 asks.

### 3.3 The post: `[assoc_dapp]` already has a reader, so the post costs no poll

`ui_task` already tests `cmp byte [assoc_dapp], 0xFF` on every pass behind
`[ui_post]` (`kernel/ui.inc`, `.chk_assoc`), and `assoc_post_x` already
shows how to use it: store the byte, then `inc byte [ui_post]` (SPEC.md
13.13). `ASSOC_FIND` (0xFE) proved that the byte carries a **sentinel** as
well as a slot. So the flush is one more sentinel range, and **`ui.inc` does
not change by a byte**:

| `[assoc_dapp]` | meaning |
|---|---|
| 0..`ASSOC_NAPP`-1 | open the pending document with this app slot (54.4) |
| **0xF0 + volume** | **flush that volume's `ASSOC.DAT` (this plan)**. `DVOL_MAX` is 8 on `kern_big`, so 0xF0..0xF7 |
| 0xFE | `ASSOC_FIND`: sweep for an unclaimed extension (54.4.3) |
| 0xFF | nothing posted |

`asc_post` (AL = the volume):

```
asc_post:
    cmp al, [asc_wno]           ; this volume refused a flush this session (3.5)
    je .out
    or al, ASSOC_FLUSH          ; 0xF0
    mov [assoc_dapp], al
    inc byte [ui_post]          ; SAY SO once (SPEC.md 13.13)
.out:
    ret
```

**The volume travels in the byte**, three bytes dearer than a bare constant,
because the service runs a pass later. A handler that mounts a second volume
in between would otherwise flush the wrong one. Flushing the wrong one is
harmless (§2), but the one that learned something would then not be flushed
this session.

**Can it overwrite a pending document open?** It would have to post while a
`0..0xFE` value was waiting, and the only writer of those is `assoc_post_x`
in a double-click handler. That handler mounts nothing after posting, and
`assoc_run_x` consumes the byte *before* running (`consume before running,
not after`). So a flush posted from inside an `assoc_run_x` (by the
location trigger, or by `files_refresh`'s harvest) lands after the consume
and is serviced on the next pass. Wave 1 has to **prove** that no handler
both posts a document and then harvests. The guard
`cmp byte [assoc_dapp], 0xFF / jne` costs 7 bytes and is the fallback if the
proof fails.

### 3.4 The service: two compares in `assoc_run_x`

`assoc_run_x` already runs where a flush has to run: on the UI task, with
**no lock held** (its header), after the handler that mounted has returned,
so no listing block is donated and no harvest is in flight. At the top,
after the existing `mov al, [assoc_dapp]` / `mov byte [assoc_dapp], 0xFF`:

```
    cmp al, ASSOC_FLUSH + 8     ; 0xF8: FIND and the slots fall through
    jae .doc
    cmp al, ASSOC_FLUSH
    jb .doc
    and al, 7                   ; the volume
    call asc_flush              ; the stub: dskw_fmt_go, call far [FMFP+FME_ASCW*4]
    jmp .done                   ; ...out through the routine's own epilogue
.doc:
```

The stub has the formatter's four stubs' shape: `dskw_fmt_go` returns to
the stub's caller with CF=1 when the image cannot be had. That refusal is
**silent**, because nobody asked for this work and nothing to do with it is
on the glass. SPEC.md 47's "every refusal is a toast" is about a feature
the user invoked.

**The drop.** The stub drops `MOD_FMT` when it is done (`fm_fmt_drop`),
**unless the image was already held when it came in**. A format
confirmation holds it between the probe and `fm_edit_end` (`dskw_fmt_go`'s
header). A flush that freed the image under an armed prompt would cost that
prompt a reload; it would not crash, because every formatter stub reloads
through `dskw_fmt_go`. Still, it should not happen. The test is one compare
of `MOD_FMT`'s `MODR_SEG` before `mod_need`, inside the 10-16 above.

### 3.5 The module's work: rebuild from the volume, reusing what the old file already knew

`FME_ASCW`, a new far entry in `.modf`. In: AL = the volume and AH = the
mode (0 incremental, 1 full; §4 needs the second). Out: nothing. Every
register is preserved, and it never fails anything.

1. **Refuse what cannot hold a cache.** That is a volume whose row is not a
   FAT volume this kernel writes: a redirected one (the cable, SPEC.md
   62), the RAM disk (a cache that is gone at power-off), or a `DVK_FREE`
   row. This is `dsk_media_ok`'s classification (SPEC.md 54.4.2.2), so no
   new predicate is written. Then return.
2. **Bank where the user is** (`[disk_drive]`, `[dsk_cwd]`) and stand in
   the volume's root with `fcp_goto`, quietly (SPEC.md 18.9.1.1). This is
   `assoc_go`'s move, and `assoc_back` is the return.
3. **Claim two buffers**, the old file and the new, `ASC_KB` each: 6KB of
   transient heap, freed before return. A refusal returns at once, and the
   next boot's misses post again.
4. **Read the old file** if there is one, under exactly `asc_use_x`'s
   tests: version 2, counts inside the caps, the counts fitting the bytes
   read (SPEC.md 54.7.1's guards). A bad or absent file is an empty one.
5. **Walk the root and one level of folders**: `hd_ia_walk`'s shape, with
   `dsk_dirw_start_x` / `dsk_dirw_get_x` in place of `OSAPI_FILE_FIND_RAW`.
   For each type-1 entry, key it by `(stem, raw size)`, the key both the
   file and the store use (SPEC.md 25.9.4):
   - **in the old file** -> copy the row, rewrite its folder cluster (this
     fixes the stale-cluster case for free), and carry its association rows,
     re-indexed;
   - **else, in the store** (`ico_find`): the harvest saw it this session.
     Read its first sector with `dsk_peek_x` (the harvest read that sector
     moments ago, so on a floppy it is usually still in §18.95's read-ahead)
     and emit the row and declarations exactly as `hd_ia_row` /
     `hd_ia_emit` / `hd_ia_decl` do;
   - **else** -> in **incremental** mode, *omit it*. Nothing has learned
     anything about it, it was not in the file either, so nothing is lost,
     and reading it would make the first flush of a fresh disk pay for
     every folder the user never opened. In **full** mode (the installer's,
     §4), read it as `hd_iassoc` does.
6. **Order and cap**: `hd_ia_front` / `hd_ia_back`'s two-ended fill and
   `hd_ia_close`'s compaction, unchanged. Declaring packages go first, so
   the 32-row cap drops a cached icon and never an association
   (SPEC.md 54.7.1).
7. **Compare**: if the new bytes equal the old file's, **write nothing**. A
   flush that learned nothing new costs reads and no write, so no FAT
   traffic and no coherence remount.
8. **Write** with `dwf_dskw_write_sys` in the root (SPEC.md 19.6.1). That
   is the door `CTRL.DRV`'s settings core already uses for `SYSTEM.CFG`
   from a module (`kernel/driver.inc`), and it stamps hidden + system.
9. **On success**, set `[asc_vol]` to 0xFF. The next harvest on this volume
   then re-absorbs the new file (one ~3-sector read) instead of posting
   again for every folder whose bodies the store does not yet hold.
10. **On refusal** (`FERR_WPROT`, `FERR_FULL`, `FERR_DIRFULL`, `FERR_PROT`,
    `FERR_IO`), set `[asc_wno]` to the volume. `asc_post` then posts
    nothing more for it this session. Without that, a write-protected
    floppy pays one module load and one failed write for every folder of
    new packages the user opens.
11. **Put the volume back** (`assoc_back`), free both buffers, and return.

**What it does not do: touch the resident tables.** They are already right.
The harvest or the locate that posted had already taught RAM everything the
file is about to say. The only resident state the module writes is
`[asc_vol]` and `[asc_wno]`.

**Its scratch** (row indices, counts, the folder cluster, the flags of the
header in hand: `hd_ia*`'s ~30 bytes) goes in a nobits `.modfb`, `.modcb`'s
shape (`kernel/kernel.asm`; docs/plans/MODULE-SELFCONTAIN-PLAN.md 3.1). So
none of it is resident.

**ESTIMATE of the module body: 800-1,000 bytes.** `hd_iassoc` is 984 bytes
of code, and the kernel form loses the driver-ABI plumbing (`os88_ent`
frames, `FIND_RAW` staging, cluster-sized `READ_AT`) and gains the old-row
reuse and the compare (~150-200).

### 3.6 What it costs the system disk, and what a flush costs in time

**Disk.** The modules ship compressed, and code barely compresses:
`FORMAT.DRV` is 1,097 bytes for a 1,136-byte image. So price the writer at
roughly its own size. On the 360KB system disk a cluster is 1,024 bytes.
`FORMAT.DRV` is 2 clusters with **951 bytes of slack**, so a writer whose
compressed form comes in under 951 bytes costs that disk **no cluster**.
Over 951, it costs one, and wave 2 returns it (§4). The other geometries
have room (`os8088-720.img` 531/713, `os8088-120.img` 1,028/2,371).

**For scale:** at `08ca1c2` the 360KB system disk **does not build**.
`os88disk: packages need 356 clusters; disk holds 354`, with the size pass
running concurrently. This plan must not be the change that makes it worse,
which is why wave 2 is in it and not a follow-on.

**Time** (ESTIMATE: target-machine `int 13h` counts, ~400 ms each, measured
in the final pass):

| step | floppy | hard disk |
|---|---|---|
| load `FORMAT.DRV` off the boot volume | 1 call (+ the root if the directory cache is cold) | ms |
| old `ASSOC.DAT` | 1 | ms |
| the walk's directory sectors | 0-4, most already in `MEM_P_DIRW` from the browse that posted | ms |
| headers of packages seen this session | 0-N, mostly still in the read-ahead | ms |
| the write: FAT x2, the root sector, data | ~4 | ms |
| **once per learned change, per volume** | **~6-10 calls, ~2.5-4 s** | **< 0.1 s** |

That is paid **once**. What it saves is paid on **every boot**: a read per
uncached package per folder, the bare pages until `APPS\` is browsed, and
the sweeps (§1).

## 4. Wave 2: the installer calls the module, and `HDDTOOL.DRV` gives the bytes back

`FME_ASCW` in **full** mode is `hd_iassoc`'s job. So once wave 1 exists,
the installer's 984 + 56 bytes are a second copy of one algorithm, and the
copy lives on the same disk.

- **Delete `drivers/hdd/iassoc.inc`.** Its mirrored constants, and its
  entry in `tests/unit/t_mirror.py`, go with it.
- **`hd_inst_step` calls the module** where it called `hd_iassoc`, with
  `[hd_idrv]` and full mode.
- **On disk:** `HDDTOOL.DRV` is 13,414 bytes in 14 clusters with 922
  bytes of slack, so removing **102 bytes** drops it to 13 clusters.
  Removing ~1,000 does that with ~900 to spare. **Wave 1 + wave 2 is -1
  cluster on the 360KB system disk at worst-case module size, and 0 at
  best.**

How a driver reaches a kernel module is the one decision in this wave:

- **2a, recommended: a cell, `OSAPI_ASSOC_FLUSH`** (DL = volume, AH =
  mode). It is driver-callable, behind the same caller test as
  `OSAPI_FILE_WRITE_SYS` (SPEC.md 19.6.1), since a package has no business
  writing a hidden system file. Cost: a rare cell, 6 bytes or more
  (SPEC.md 20.3), whose body is the wave 1 stub. It is an **append**, so
  `abilock.py --update` runs without a version bump (SPEC.md 20.2.0.1).
  ~10 resident bytes (ESTIMATE).
- **2b: zero resident bytes, not recommended.** The installer
  full-mounts each top-level folder (`OSAPI_FILE_GOTO`, not `_Q`), the
  harvests post, and the UI task's next pass flushes incrementally. It is
  free, but it depends on a driver doing a listing mount mid-install, and
  on an incremental flush happening to cover what a full one would. That
  is two properties to prove, where 2a has none.

**One case where wave 2 is weaker than today, and it heals itself.** A
machine booted **from its hard disk** that installs a newer kernel from a
floppy copies the new `*.DRV` over `C:`'s. `mod_need` loads from the boot
volume, so it finds a `FORMAT.DRV` stamped for a kernel that is not the
running one and refuses (SPEC.md 2.8.2). The install then ends with **no**
`ASSOC.DAT`, which is SPEC.md 54.7's third tier (a cold cache, not a wrong
one). After the restart the new kernel's first harvest of `C:\APPS` posts,
and wave 1 writes the file. Today that machine gets `hd_iassoc`'s file at
install time. Wave 2 delays it to the first browse.

## 5. Refused, with the reason

1. **A resident writer.** ~900-1,000 bytes resident on every machine, for
   work done once per change. That is the trade the module mechanism exists
   to refuse.
2. **Writing inside the harvest.** The mount is mid-flight: the listing
   block is donated, `[dsk_dseg]` is live across calls that can compact
   (SPEC.md 66.5.10.2), and the sector buffer holds the header being read.
   `ui_task`'s posted-work pass is the place built for this.
3. **Writing at Restart or Shut Down.** Power-off loses everything learned,
   and on a floppy machine the disk that learned something is often no
   longer in the drive by then. It also turns the one moment the user is
   leaving into a several-second write to disks they may not be looking at.
4. **Calling `HDDTOOL.DRV` where it is.** It is `HDD.DRV`'s private ABI
   (§2), and loading it costs a 13KB load to run 1KB of code.
5. **Queueing the learned rows in RAM and appending them.** It would save
   the walk, but it costs a resident queue, or a claim plus the capture
   code at the harvest. It also loses what the walk gives for free: dropping
   packages that are gone, correcting clusters, and never describing a
   different disk.
6. **Persisting `OSAPI_ASSOC_SET`.** A runtime claim is a running program's
   choice for this session, and it is sticky precisely so that a
   declaration arriving on the next mount cannot undo it (`assoc_ext_take`).
   Writing it to a volume as a non-sticky row would change what it means.
   The persistent channel is SPEC.md 54.6's declaration, and **this plan
   persists declarations**. SCRIBE is the one package that claims at runtime
   without declaring (header flags 0x09, bit 1 clear). Its fix is the
   one-line `OS88_ASSOC*` declaration SHEET uses (`apps/sheet/sheet.asm`),
   not a kernel change.
7. **Triggering on every miss.** §3.2: it thrashes on iconless packages and
   on a full store.

## 6. Hazards, and what each one costs if it bites

1. **An XT swap mid-flush.** An XT drive has no change line, so the kernel
   trusts the medium inside a mounted volume (SPEC.md 18.9.1). A floppy
   swapped between step 5's walk and step 8's write gets a file built from
   the other disk. That is the "present and wrong" state, and it is bounded
   the way §54.7 bounds every cache error. A `(stem, size)` that does not
   match misses and is re-harvested. A wrong hint costs one mount, and the
   name re-check means it never opens a wrong file (SPEC.md 54.4.2). The
   next miss on that disk rebuilds it. Every file save shares this window
   on an XT.
2. **One-drive machines.** `mod_need` loads from the boot volume. With the
   system disk out, the module cannot be had, the flush is refused
   silently, and the volume is **not** stamped in `[asc_wno]`, because the
   refusal says nothing about the volume. The cost is one failed root
   lookup on A: per post, and posts come at most once per folder per
   session (§3.2). A one-drive machine therefore writes caches for the
   system disk and any hard disk, and for an apps floppy only on a session
   when the system disk is in the drive. That is the module rule's own
   limit (ONDEMAND-PLAN §1), stated rather than worked around.
3. **The progress widget.** `dskw_write` ends in `ct_fpg_end`, and
   `fpg_arm` puts the widget up after `FPG_WARM` = 3 sectors *inside one
   lock hold* (SPEC.md 12.8.3). The flush runs lock-free, so the
   expectation is no widget. **Measure it**: a widget that flashes up
   during a background write is PERFORMANCE.md's double-draw flash with
   the widget as the flash.
4. **The coherence remount.** `dskw_sync_x` marks every Disk window showing
   the written folder (`fmv_mark`). That folder is the root, so a window on
   that root re-lists on its next focus to show the same entries, since
   the new file is hidden. On a floppy that is a visible second of nothing.
   If the final pass measures it, the cheap fix is general: a hidden +
   system write cannot change a listing (SPEC.md 19.6), so `dskw_sync_x`
   can skip `fmv_mark` when `[dskw_syswr]` is set. That is ~6 resident
   bytes and saves `SYSTEM.CFG` saves the same re-list. Separate, and only
   on a measurement.
5. **More than 32 packages on a volume** (a full hard-disk install, or the
   everything floppy). Rows past the cap are dropped by §3.5 step 6's rule,
   and a dropped package misses on every boot. With the store-take trigger
   it posts once per session. The flush then reads that package's header,
   builds the same file and writes nothing (step 7). The cost is one
   module load and a walk per session, on a hard disk where both are
   milliseconds. Raising `ASC_NAPP` is a separate decision. The claim has
   been transient since SPEC.md 54.7.4, so the price is heap at mount and
   the file's size, not resident bytes.
6. **Where the file lands.** A runtime write goes where the FAT allocator
   puts it and may cross a track, which makes the read two calls instead of
   one (SPEC.md 54.7.5 already says this of the installer's file).
   `t_ascplace` walks shipped images only and is unaffected.

## 7. Gates

Per CLAUDE.md's Testing section, no wave runs a soak row. Each wave verifies
on the host (`make`, `make KERN_SMALL=1`, `tools/kernsize.py` on both
kernels) and names its rows. The union runs **once**, after the last wave.

**New row: `assocflush`** (MartyPC, `tools/os88ui.py`, soak). It uses a
scratch copy of `apps720.img` with `ASSOC.DAT` deleted, on the 720KB system
disk.

| leg | asserts | broken on purpose, it must go red |
|---|---|---|
| WRITE | browse `B:\APPS`. Then `B:\ASSOC.DAT` exists (`tools/os88fat.py` off the guest's floppy), and its rows equal `os88disk.py`'s `build_assoc` for the packages in `APPS\`, compared as a set | the post taken out of the harvest |
| REBOOT | `system_reset`, browse `B:\APPS`: **zero** package-sector reads in the harvest (MartyPC's `disk()` counter), and a `MEDIA\*.TEX` shows TeXPad's glyph **before** `APPS\` is browsed | `[asc_vol]` not reset after the write |
| QUIET | browse `B:\APPS` a second time in the same session: no flush, no write | the store-take trigger replaced by "every miss" |
| NOTHING NEW | the shipped (warm) apps disk: no post, no write, all session | the trigger on the hit path |
| REFUSED | the same disk write-protected: one attempt, then none for the session | `[asc_wno]` not set |
| LOCATE | (if §3.2's optional trigger is taken) a program found only by sweeping is rung 1 after a restart | that trigger taken out |

If MartyPC cannot present a write-protected floppy, REFUSED moves to QEMU
(`readonly=on`). It asserts behaviour, never time, so it does not need the
8088.

**Existing rows the waves can reach:** `assocvol`, `assocstale`,
`assocfind`, `assocsweep`, `assocglyph`, `assocopen`, `assocwake`,
`ascabsorb`, `icostore`, `icoshed`, `mediadisk`. Wave 2 adds `instassoc`,
which must still find a correct `C:\ASSOC.DAT` after an install, and
`t_mirror`, which loses `iassoc.inc`'s mirror. The fast tier runs inside
`make` regardless.

## 8. Decisions for the owner

1. **Writing to disks the user only browsed.** The flush writes a hidden +
   system file onto any FAT volume that holds os8088 packages its cache
   does not describe. A disk with no `.O88` on it is never touched, because
   nothing on it can be a store-take. **Recommended: on, with no
   setting.** A `SYSTEM.CFG` opt-out would cost a byte or two resident
   (SPEC.md 51.5.3, docs/plans/completed/SETTINGS-COST.md) if it is wanted.
2. **The location trigger** (§3.2, ~20 bytes): persist where a sweep found
   a program. **Recommended: take it.** It is the only path that persists a
   location learned without a harvest.
3. **Wave 2's door**: 2a (a cell, ~10 bytes, deterministic) or 2b (zero
   bytes, two properties to prove). **Recommended: 2a.**
4. **Immediate or deferred.** The flush runs on the pass after the browse
   that posted it, so the ~2.5-4 s write lands right after a navigation,
   once. Deferring it to an idle moment needs a timer, and that is resident
   bytes. **Recommended: immediate.**

## 9. The waves

| wave | what | resident (ESTIMATE) | 360KB system disk |
|---|---|---:|---|
| 1 | `FME_ASCW` in `FORMAT.DRV` (incremental and full modes), `asc_post`, the harvest trigger, the dispatch, the stub, `asc_wno`, `.modfb`; the new SPEC.md subsection written **first**; the `assocflush` row | ~50 | 0, or +1 if the compressed writer passes 951 bytes |
| 1b | the location trigger, if taken | ~20 | 0 |
| 2 | `OSAPI_ASSOC_FLUSH`, installer switched over, `iassoc.inc` deleted, SPEC.md 52.10.14 re-pointed | ~10 | -1 |
| **net** | | **~60-80** | **-1 to 0** |

SPEC.md is updated *before* each change (CLAUDE.md), so wave 1 opens with
a new subsection after SPEC.md 54.7.5, **"the machine writes back what
it learned"**: the trigger, the sentinel range in `[assoc_dapp]`, the module entry's contract,
`[asc_wno]`, and §6's hazards. It also amends 54.7.5's last paragraph (a
second runtime writer) and 52.10.14 (wave 2). This plan becomes that
section's design record and moves to `docs/plans/completed/` in the commit
that lands the last wave.
