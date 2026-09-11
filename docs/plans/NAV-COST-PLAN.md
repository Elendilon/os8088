# WHAT NAVIGATION COSTS, AND THE SLOT THAT MAKES IT COST THAT

**STATUS: OPEN. The finding is measured on ONE package and the audit is not
done.** It is written now because it was found while planning the DOS box's
path wave (docs/plans/DOS-EXEC-PLAN.md) and deviating to it there would have
been the tail wagging the dog - and because one of its conclusions is a
REFUSAL that is better recorded before somebody builds the thing it refuses.

---

## 1. The finding

**TANK ATTACK freezes for about six seconds to save a 40-byte high score
file**, measured by the fork owner. `apps/tank/tkhs.inc` walks
`SYSTEM` -> `APPDATA` on its own volume and back, and it does it with
`OSAPI_FILE_GOTO`.

There are **three** GOTO slots and only one of them is for navigating:

| slot | what it does |
|---|---|
| `OSAPI_FILE_GOTO` | **a REMOUNT** - real floppy I/O, then a directory scan, a sort and an icon harvest, because a Disk window is about to DRAW this folder |
| `OSAPI_FILE_GOTO_Q` (§19.2.2) | quiet. Inside the volume you are on it is **a WORD, no I/O at all**; crossing volumes it keeps the BPB and the FAT window and skips the scan, the sort and the harvest. But it moves the GLOBAL cwd and not the instance's |
| `OSAPI_FILE_GOTO_QM` (§74.1) | GOTO_Q's quiet stand **and the instance moves with it**, so the next file cell resolves there |

So the six seconds is not the cost of walking a directory tree. It is the cost
of asking, four times, for a folder to be prepared for DISPLAY by a program
that is not going to display it.

## 2. Tank's own comment is the worked example, and it is not a mistake

This is worth quoting because it shows exactly how the wrong slot gets chosen,
and the author reasoned correctly from what they had:

> **It is OSAPI_FILE_GOTO and not its quiet twin.** GOTO_Q moves the GLOBAL
> cwd and deliberately not the instance's, while FILE_FIND, _READ and _WRITE
> all resolve in the INSTANCE's folder - so a quiet move is undone by the very
> next call, and the save writes nothing at all while the load appears to work.

Every word of that is true **about `GOTO_Q`**. `GOTO_QM` is the slot that
answers it, and the SDK describes Tank's case in as many words: *"wrong for a
program whose working folder changes on every call"*. `QM` arrived for RunCPM,
where a CP/M drive is a folder, and nothing went back to tell the packages
that had already refused `Q` for the right reason.

**So the lesson for the audit is that a slow call site may be a CORRECT
refusal of the wrong alternative**, not carelessness - which is why this is a
per-site read and not a `sed`.

## 3. It is a pattern, not a package

`call OSAPI_FILE_GOTO` appears at roughly **twenty sites in eleven files**:

- **`apps/os88type.inc`** - four, and this is the one that matters most,
  because it is a SHARED INCLUDE: Word, CWord, Font Viewer and Audio all carry
  it. Its `.back` site is a pure restore (*"put the caller back where it was,
  on every path out of here"*) and wants `QM` exactly.
- `apps/skies/csset.inc` three, `apps/tank/tkhs.inc` three,
  `apps/dotdel/ddhs.inc` two, `apps/word` two, `apps/scribe` two,
  and one each in `apps/sheet`, `apps/frotz`, `apps/audio`, `apps/texpad`.

Eight packages walk to `SYSTEM\APPDATA` (§19.9): The Wire, FTPD, Clear Skies,
Tank, Dot Delirium, Cyclone and the two that reach it through `os88type.inc`.

**Some of those sites are RIGHT.** A Save As that is about to show a folder
wants the listing, the sort and the icons - that is what the slot is for. The
audit's question per site is *"is this program about to draw this folder?"*,
and only a No converts.

## 4. THE CACHE IS REFUSED, and this is the important half

The obvious next thought - *"walk once at startup, remember the cluster, and
every later save just stands there"* - is the thing §18.9.3 already refuses,
and the reason is not conservatism:

> A floppy can [be swapped], and **no predicate the kernel can evaluate
> answers it**: §18.9.1's motor timeout is physical proof for one quiet switch
> and nothing more. So the assertion is the CALLER'S: *"I am in the middle of
> a batched operation with the user interface frozen, so the disk is the same
> disk."* **AND ANY UNLOCKING OF THE USER INTERFACE ENDS IT.**

A remembered cluster is an assertion held **across** UI unlocks, which is
precisely the span the kernel says nothing can validate. A game that caches
`APPDATA`'s cluster, and whose player swaps the disk between two rounds,
writes its high score into whatever occupies that cluster on the new disk.

**That is data corruption traded for six seconds, and it is the wrong trade
in the wrong direction.** Clear Skies is not a counter-example: its parts live
INSIDE the file it already opened (§20.12), so it never navigates and has
nothing to invalidate. "Just being there" is the absence of a walk, not a
cached one.

### 4.1 ...and it is probably not needed anyway

The reason to measure before designing a cache: with `QM` the walk is **two
free cluster moves and two directory sector reads**, because `QM` inside a
volume is a word. If that lands near Clear Skies' half-second then the cache
buys nothing and risks corruption for it.

**So the order is: convert, measure, and only then ask whether anything is
left to buy.** If something is, the cheap safe shape is a cached cluster with
a **witness** - stand there quietly and confirm a known name is present before
trusting it, re-walking when it is not - which costs one directory read
instead of the whole walk. That is a design to write against a number, not
before one.

## 5. What this plan is waiting for

The DOS box's **path wave** produces the number. It walks directories with
these same slots and will establish what a level actually costs with `QM`,
on a 4.77MHz 8088, measured rather than reasoned. Doing this audit first would
mean doing it blind.

Then, in order:

1. **Convert `apps/tank/tkhs.inc`'s three sites** and measure the save against
   the owner's ~6 seconds. One package, one number, the whole case.
2. **Convert `apps/os88type.inc`'s `.back` site**, which reaches four packages
   for one edit and is an unambiguous restore.
3. **Audit the remaining sites** by §3's question, converting the Noes.
4. **Only then** ask whether §4.1's witnessed cache has anything left to buy.

## 6. What is NOT decided here

- Whether any of this wants an SDK change. It may be that the fix is entirely
  per-package and the only durable artefact is a sentence in `os88api.inc`
  next to `OSAPI_FILE_GOTO` saying which of the three to reach for - which
  would be the cheapest useful outcome and should be considered first.
- Whether §47 applies. A program that cannot reach `SYSTEM\APPDATA` currently
  fails quietly in at least one package; that is a different bug and is not
  this plan's.
