# THE PATH WAVE: one answer, three customers, and the trap that makes it quadratic

**STATUS: COSTED, NOT BUILT.** Everything below is read out of the tree rather
than measured on a machine; the one number that needs a 4.77MHz 8088 is named
in §6.

It exists because the same question has now been fought three times in three
places, and each time the answer was *"build a stack"*.

---

## 1. What the kernel will not tell a package

**A package cannot find out where it is standing.** `OSAPI_FILE_HERE` answers
a **cluster** and a volume index, and a cluster is not a path.

Walking up is refused at the source, by design: `dsk_find_x` filters the raw
directory sectors and four lines into its entry loop has

```
    cmp al, '.'
    je .skip                    ; the on-disk dot links (SPEC.md 19)
```

so **neither `.` nor `..` is ever reported**. Both cells go through it -
`api_file_find` and `api_file_find_raw` join at `api_ff_fence` and differ in
the size field and nothing else. `OSAPI_FT_UP` exists because `dsk_synth_up`
builds an up-entry for `disk_mount`'s **LISTING** (§19.5), a different
structure a package cannot reach.

The kernel has no such problem: `dsk_dotdot_x` reads a subdirectory's first
sector and takes entry 1's `FstClusLO`, range-checked. §19.2 states the
consequence as a design property - *"going up needs no path stack and no
memory of how the user got here: the disk itself records the parent, and that
is why there is no path string anywhere in os8088."*

**True of the kernel. Not true of anything else, and that is the gap.**

## 2. Three customers, each of whom paid separately

| customer | what it built | what it cost |
|---|---|---|
| `apps/ftpd` | `FD_CDMAX`, a 16-level descent stack, because `CDUP` needs one | its own comment: *"CDUP NEEDS A STACK BECAUSE THE KERNEL CANNOT ANSWER IT"* |
| `apps/dos` | the launch directory became the program's root, path maintained by `AH=3Bh` | DOS-EXEC-PLAN §15.2: the walk *"was abandoned"*, and `AH=47h` answers a string it keeps itself |
| `apps/tank` (and docs/plans/NAV-COST-PLAN.md's other sites) | walks `SYSTEM` -> `APPDATA` on every save | ~6 seconds, measured by the fork owner |

Three independent arrivals at the same shape is the strongest evidence
available that this is the problem's actual shape and not an oversight. It is
also the argument for a slot: **the kernel holds the answer and each package
is paying to re-derive it.**

## 3. The cost is NOT what it looks like, and this is the section to read

The instinct is that a walk costs one disk revolution per level, so that four
levels is seconds and the design needs a cache in front of it. **Checked, and
it does not.** Every part is already answered from memory:

- **"Is this the same disk?" is asked ONCE PER MOUNT, not once per level.**
  `[dsk_sigcur]` - the position-sensitive sum of the boot sector (§18.8.2) -
  is computed by the mount that already read that sector. Nothing in a walk
  recomputes it.
- **A same-volume move is a WORD.** `OSAPI_FILE_GOTO_Q`/`_QM` inside the
  volume you are on is *"a WORD, no I/O at all"* (§19.2.2); across volumes it
  keeps the BPB and the FAT window.
- **The no-op test reads the BIOS MOTOR BIT.** `dsk_here_ok` (§18.9.1) does
  not merely compare: it reads `0040:003F` and uses a still-running motor as
  **physical evidence** that the floppy has not been swapped. That is a memory
  read, and it is a stronger test than a cached signature rather than a weaker
  one.
- **Directory sectors come out of a CACHE.** §19.2.3's window - `MEM_P_DIRW`,
  16KB purgeable, eight runs, keyed on volume + `[dsk_sigcur]` - answers the
  second climb of a `..` chain from memory. `dsk_dotdot_x` reads through it.
- **`inst_vol_enter` is free when nothing moved**: six compares, and a mount
  *"is paid only when something really did move the volume underneath this
  app."*

So os8088 already has DOS's three speed mechanisms: a resident per-volume
parameter block (the BPB + FAT window survive a quiet mount, as a DPB does),
a walk that never re-validates mid-operation, and `BUFFERS=` (§19.2.3).
**There is no missing infrastructure.**

### 3.1 The trap: `GOTO_Q` makes exactly the bad shape

There is one way to get the pathological *"check, step, check, step"* walk,
and it is a two-letter mistake.

`OSAPI_FILE_GOTO_Q` moves the machine but **not the calling instance's own
record**. Every name-taking cell begins with `inst_vol_enter`, which re-stands
the machine in the instance's folder - so the next `FILE_FIND` **undoes the
step**, and a walk built on `Q` re-stands on every call. Within one volume
that is still free, which is worse rather than better: it is silent, and it
produces a walk that goes nowhere.

`OSAPI_FILE_GOTO_QM` (§74.1) moves the instance with it, so the next cell
resolves where the walk left it. **`QM` is the slot a walk is built on**, and
`Q` is for a copy loop that wants to come home.

This is the same distinction docs/plans/NAV-COST-PLAN.md turns on, one
consequence along, and `apps/tank`'s comment is the record of somebody
refusing `Q` correctly and never being told `QM` had arrived.

## 4. What IS expensive: the API boundary and the ordinal restart

The walk's real cost is not the disk, and naming it decides the slot's shape.

To learn its own name at each level, a package must find the entry in the
parent whose first cluster (+16) matches the child's. `OSAPI_FILE_FIND` is
**ordinal-based and restarts the directory walk on every call**:

```
    mov bp, cx                  ; BP counts the ordinals still to skip
    ...
    call dsk_dirw_start_x
```

So enumerating a parent of K entries is K far calls, each re-walking from
entry 0 - O(K) API crossings at 46.7us apiece and O(K^2/16) window lookups.
The window makes those lookups memory rather than revolutions, which is why
this is milliseconds and not minutes, but it is still work done K times to
answer one question.

**A kernel-side path builder walks each level's directory once**, with no API
crossing per entry and no ordinal restart. That is the whole of the win, and
it is a constant-factor argument rather than a complexity one: O(K) internal
steps against O(K) far calls plus O(K^2/16) lookups.

## 5. The slot

One call, the whole path, which is also what DOS does - `AH=47h` is GETCWD and
not GETPARENT, and for this reason.

```
OSAPI_FILE_PATH   ES:DI = a buffer, CX = its size
                  out CF=0, the NUL path from the volume root written there,
                      CX = its length
                      CF=1, AX = FERR_* (FERR_TOOBIG if CX was short)
```

Four things it must settle, none of them expensive:

1. **It walks and RESTORES.** The caller's instance must stand where it did,
   which is `OSAPI_FILE_HERE` then `inst_vol_mark` - both already exist.
2. **A bounded buffer, and the bound is the caller's.** `FD_CDMAX` is 16 and
   FAT12 has no depth limit, so the refusal path is real and must name itself
   rather than truncate (§47).
3. **A corrupt `..` is a refusal, not a crash.** `dsk_dotdot` already
   range-checks against `[dsk_maxclus]`; the loop above it needs its own guard
   against a `..` cycle, which a corrupt disk can present.
4. **It is a `.cold`/module candidate** (§2.8). Nothing on a boot path needs
   it, and its three customers all call it at most once per operation.

## 6. What has to be measured before it is built

One number, on a 4.77MHz 8088 under MartyPC: **what a four-level path costs
today**, built out of the published slots, warm window and cold. If that is
tens of milliseconds then §4's argument is correct but the prize is small and
the slot should be judged on the three packages' code rather than on speed. If
it is hundreds, the slot pays for itself on `apps/tank` alone.

`tests/dosdir.py`'s gate program already makes a subdirectory and stands in
it, so the fixture exists.

## 7. What this plan does NOT propose

- **No directory cache.** §19.2.3 is built, measured and keyed correctly.
- **No `OSAPI_VOL_SIG`, and no per-package banked cluster.**
  docs/plans/NAV-COST-PLAN.md §4.3 records why: the kernel already banks that
  data against that signature for every package at once.
- **No change to `dsk_find_x`'s dot filter.** Reporting `.` and `..` to
  packages would put two entries into every listing every caller then has to
  skip, to serve a question this slot answers directly.
