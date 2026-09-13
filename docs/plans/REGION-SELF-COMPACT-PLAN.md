# A region that can compact ITSELF — the wall a package builds by asking

**Status: DESIGN, not started.** SPEC.md 66.6.1 built everything a region
needs to move and left one moment out — the only moment a package ever wants
it. This costs that moment three ways and recommends the third.

Read SPEC.md 66 first, and SPEC.md 66.6.1 in particular. This document assumes
both, and it changes none of it: what is proposed here does not weaken
`mem_can_move`, it arranges to ASK IT SOMEWHERE ELSE.

---

## 1. The report

> The program, a DOS program runner, needs massive heap for the DOS arena.
> The sound driver is mounted at the top of the heap. The DOS package runs
> under the sound driver. The DOS package calls for the sound driver to
> unmount, and it does. The DOS package asks for max heap — and it cannot
> compact into the space freed by the sound driver, so it loses 14KB of
> potential heap.

Every clause of that is right, and the last one is right for a reason that is
one line of `kernel/memory.inc`.

---

## 2. The diagnosis, and it is exact

`mem_frameless` (SPEC.md 66.6.1) asks four questions of a region before the
compactor may move it. The third is `mem_in_nest`: *is a frame standing in the
image at BX?* — answered off `wm_pkgs[0..wm_pkgd)`, the stack of segments
`wm_pkgcall` pushes before every kernel→package far call.

**A package reaches `mem_claim` only from inside its own callback.** So at the
instant package S asks for memory, `wm_pkgs` names S, `mem_in_nest` answers
yes, `mem_frameless` refuses, and `mem_can_move` pins S's region.

> A package's region is pinned at exactly the moment moving it would pay, and
> by the act of asking.

That is not a defect in `mem_in_nest`. It is telling the truth: the CPU pushed
S as the far-return CS at the `call far`, `OSAPI_SLOT` pushed S again with its
own `push ds`, and the package may have pushed it a third time itself — Paint
does `push ds` at twelve sites. Those words are real and they are stale the
moment the region moves. `wm_pkgs` is the cheap, exact proxy for them.

### 2.1 …and the geometry it produces, measured

Booted `build/os8088-360.img` on `os8088_xt_hdd`, opened the Calculator and
then the Browser, and read `mem_tab` off the running machine with
`tools/heapmap.py`:

```
99000..9E000    20.0K  inst 3 (BROWSER region)  movable  top-down  rloc=160
9E000..A0000     8.0K  inst 1 (CALC region)     PINNED   top-down  rloc=0
```

A region is claimed **top-down** (`mem_claim_hi_x`, `kernel/loader.inc`), so
the package launched FIRST sits at the ceiling and the next one lands directly
beneath it. Close the Calculator and there is an 8KB hole at the top of the
heap with the Browser's region under it — the report's shape exactly, with a
package standing in for the driver and 8KB standing in for 14.

**What is measured and what is modelled**, because the difference matters for
every number below: the layout above is READ off a running machine. The close
is MODELLED — the Calculator's record is dropped from the map that was read,
which is what `mem_free` does to it — and so are §5.4's pass figures, through
`heapmap.Map.compacted()`, the tree's own host-side model of `mem_cp_plan`
(`tests/heaphi.py` and `tests/drvmove.py` already assert against it). §8 is
how the whole of it gets asserted in the guest instead.

The Browser is one of the five packages in the tree that already declares
`OS88_REGION_MOVABLE` (`rloc=160` above, against the Calculator's `rloc=0`),
so the declaration is not what is missing. **Everything needed to move that
region exists and is live in shipped software.** What is missing is a moment
at which the kernel is allowed to.

### 2.2 The hole is reachable, and by the pass that already exists

SPEC.md 66.4.1's descending pass packs the ceiling: a top-down claim slides
**up** into the hole above it. Move the Browser's region up by 8KB and the
free run beneath it grows by 8KB — one `rep movsw` of 20KB, and the wall is
gone. The pass is built, it is reached from `mem_compact`'s `.flip` arm
whenever the ascending plan comes back short, and `tests/heapfrag`'s check 13
already asserts it works — **on a claim the package holds, never on the region
the package runs in.**

So the missing piece is not a mechanism. It is one predicate answering
honestly at a moment chosen badly — **and a second piece §5.4 measures, which
is that the pass able to use the answer is never the pass the compactor
picks.**

---

## 3. What the fix must not do

`mem_in_nest`'s answer is correct. Three things follow, and they are the fence
every option below is judged against:

1. **No stack scan, and no stack patch it cannot prove.** SPEC.md 66.3 rule 5:
   a heap segment number shares a 16-bit range with kernel return addresses and
   with a package's own near pointers, so a sweep that patched would corrupt a
   return address silently.
2. **A declaration the kernel cannot check must not be load-bearing.** SPEC.md
   66.2's own rule — "declared and named nothing" is the one shape the kernel
   cannot tell from "declared and forgot".
3. **Whatever runs must run with nothing held.** `mem_compact` raises
   `[sch_lock]` across the plan and the moves, and its park request DROPS that
   lock for up to `INST_PARKW` ticks (SPEC.md 66.5). Doing that from inside a
   repaint pass — which holds `gfx_lock` across `wm_pkgcall` — is a deadlock
   against `OSAPI_MEM_PARKSAFE`, not a slow path.

---

## 4. Option 1 — move the caller's region and patch its return frame

*"Allow a compaction of the calling region during the compaction, and then
tell it it moved in the return."*

**What it would take.** The two words the KERNEL pushed are at computable
offsets, and that is the half that works. An `OSAPI_SLOT` cell is eight bytes
of fixed shape:

```
push ds        ; the PACKAGE's DS  ── stale after a move
push cs
pop ds
call <routine>
pop ds
retf           ; pops the far-return CS the CPU pushed ── stale after a move
```

so at entry to the kernel routine the frame is `[SP+0]` near return, `[SP+2]`
DS = S, `[SP+4]` far IP, `[SP+6]` far CS = S. Patch +2 and +6 and the package
comes back with DS and CS already correct and never knows it moved.

**Why it is refused.** Those are the only two copies the kernel can find, and
they are not the only two copies:

| copy | where | can the kernel find it? |
|---|---|---|
| far-return CS | `[SP+6]` | yes |
| `OSAPI_SLOT`'s `push ds` | `[SP+2]` | yes |
| `api_x`'s conditional `push es` | frame | yes, per cell family |
| **whatever the package pushed itself** | anywhere | **no** |
| **whatever the package holds in a register** | ES, a spare | **no** |
| a second frame, if S appears twice in `wm_pkgs` | anywhere | no |

Rows four and five are fence 2 exactly: the only way past them is a
declaration — *"my frame holds no copy of my own segment and no register does
either"* — which the kernel cannot verify, which a package gets right on the
day it is written and wrong on the day someone adds a `push ds`, and whose
violation is **not a crash but a wrong answer**: the package reads its own
data out of a segment that is no longer its image. That is the single worst
failure shape this tree ships, and SPEC.md 66.3 rule 5 already refuses its
sibling.

It also couples `mem_claim` — eight near calls deep by the time
`mem_cp_run` copies anything — to the byte layout of an API cell.

**Verdict: refused.** Not because it cannot be built: because what it rests on
cannot be checked, and the thing it buys is a saved callback boundary.

---

## 5. Option 2 — take the package off, compact, hand it back

*"Allow a package to request a 'max compaction', which takes it off as the
running program and compacts, then on its next turn it can make whatever
claims it needs."*

**This is the right shape, and it is already the house pattern — twice.**

### 5.1 `OSAPI_PKG_REHOME` solved this exact problem once

SPEC.md 20.12.10's slot, in the SDK's own words:

> *CALL IT FROM YOUR ENTRY PROC AND RETURN CF=0 WITH BX=0. It only RECORDS:
> you are still executing in the region this frees, so the kernel does the
> work after you return.*

A package that wants its own region disposed of **records the wish and
returns**, and the loader does it in the window where nothing is standing in
the region any more. Word for word the problem here, with "frees" for "moves".

### 5.2 …and `ui_task` already has the quiescent point

`kernel/ui.inc`, the top of the event loop:

```
.loop:
    ; --- 0. a posted restart, spent with NOTHING held (SPEC.md 20.10) ---
    cmp byte [ui_rebootq], 0
```

A posted action, cleared before it is acted on, spent at the top of the loop
with no lock held and no callback in flight. That is fence 3 satisfied by a
site that already exists and is already audited — and `[wm_pkgd]` is 0 there
by construction, because every `wm_pkgcall` on this task has returned.

### 5.3 So the proposal is those two composed

> **`OSAPI_MEM_COMPACT_WAKE`**, at the next free cell (`0x0550` today) — *"compact everything you can at
> the next quiescent point, then wake me."*
>
> `BX` = your window. Out: CF=0 posted — **return from your callback**, and do
> your sizing and claiming in your `OSAPI_WM_ONWAKE` handler (SPEC.md 74.1).
> CF=1 refused: `BX` is not your window, or a request is already posted.

Kernel side, in four pieces:

| piece | where | what |
|---|---|---|
| `[mem_cpq]` | `.bss`, 2 bytes | the window to wake, 0 = nothing posted |
| the cell | `osapi_table` 0x0550 | validate `BX`, store, `sch_uiwake` |
| the service | `ui.inc` `.loop` step 0, beside `[ui_rebootq]` | clear first, `mem_compact_max`, `wm_wake` |
| `mem_compact_max` | `memory.inc` | the descending pass and then the ascending one, both unconditional (§5.4) |

**Nothing else changes.** `mem_can_move`, `mem_frameless` and `mem_in_nest`
are untouched, and that is the whole argument for this option: at the service
point the region is **genuinely frameless** — the existing predicate returns
"movable" because it is TRUE, not because it was bypassed.

### 5.4 `mem_compact_max` is the second half — and ALONE, THE UN-PIN IS WORTH ZERO

This is the part nobody would have costed, and it is the most useful thing
measured here. SPEC.md 66.4.1: *"The two passes are ALTERNATIVES and not
cumulative… whichever single pass satisfies the claim is the one that runs."*
That is right for a sized claim. For this request it is the difference between
the feature working and the feature doing **nothing at all**.

`tools/heapmap.py`'s model of both passes, run over the §2.1 layout with the
Calculator's record dropped — the 8KB hole standing above the Browser's region:

| | ascending | descending |
|---|---|---|
| region PINNED — today | **494.5K** | 418.0K |
| region MOVABLE, one pass | **494.5K** | 426.0K |
| region MOVABLE, both passes in sequence | **502.5K** | |

Read the middle row. `mem_compact` takes whichever single pass is better, the
ascending one wins by 68.5K, and **the answer is 494.5K whether the region is
pinned or not**. Unpinning the caller's region — the whole of §4 and §5.1–5.3 —
buys *exactly nothing* on its own, because the pass that would have used it is
never the pass that runs.

Run the ceiling pass and then re-plan the floor against the result and the run
is 502.5K: 494.5 + 8.0, the hole to the byte. The two passes act on **disjoint
sets** — bottom-up claims and top-down ones — and both grow the SAME middle
run, so for a request that is not sized against anything they are cumulative
and the alternatives rule is simply the wrong rule.

So the two halves have to land together, and a plan that takes one of them
should take neither.

**What it costs.** `mem_compact(AX=0)` is already "compact regardless,
dissolve nothing" (SPEC.md 66.10.1, `mem_unblob`'s call). What is new is
seeding the direction, so the request is two calls and ~20 bytes:

```
mem_compact_max:                ; SPEC.md 66.4.1's two passes, both taken
    mov byte [mem_cp_seed], 1
    xor ax, ax
    call mem_compact            ; the ceiling packs up, opening the wall…
    mov byte [mem_cp_seed], 0
    xor ax, ax
    call mem_compact            ; …and then the floor packs down into one run
    ret
```

with `mem_compact`'s `mov word [mem_cp_msk], 0` seeded from that byte.
**Ceiling first**: the table's last row is the descending pass followed by an
ascending plan made against the result, and that ordering is what produced
502.5K. The other order leaves the ascending pass planning around a wall that
the descending pass is about to remove.

### 5.5 The package needs no new question answered

After the service point the region has PHYSICALLY moved, so:

- `OSAPI_MEM_AVAIL` is correct with no change at all. It plans through
  `mem_cp_plan` in the ascending direction only (`kernel/memory.inc`,
  `mem_avail_x`), and once the region is at the ceiling that single plan sees
  one long run. **Had we tried to answer this by making `mem_avail` model both
  directions instead, it would have had to promise a run `mem_claim` could only
  deliver by running both passes — a second place for the two to disagree.**
- The package does not need to be told it moved. `wm_pkgcall` sets DS from
  `W_SEG` live, and `mem_region_reloc` put `W_SEG` right. Its own data claims
  were fixed by its own relocation proc, and its near offsets never moved —
  a package is `org 0` with no relocation of any kind.

### 5.6 What it costs the package

One callback boundary: ask, return, claim on the wake. For the reported
program that boundary is free — *the user picked a program to run* and *size
the arena for it* are already two steps — and it is the shape this OS uses
everywhere else for work that cannot finish in one turn (SPEC.md 7.4's
resumable copy, `OSAPI_WM_ONWAKE`, the posted restart above).

---

## 6. Recommendation

**Option 2, as §5.3, WITH §5.4.** Its correctness argument is one sentence —
*the compactor is asked the question it already asks, at a moment when the
answer is yes* — and it invents no invariant to get there.

Option 1 buys one callback boundary and pays for it with a rule no test can
enforce. It also does not escape §5.4: patching the frame un-pins the region
and the ascending pass still wins, so option 1 built alone measures 494.5K
against today's 494.5K. **Whichever option is taken, §5.4 is the half that
actually moves the number.**

---

## 7. What this does NOT solve

Written down so nobody costs them as part of it:

1. **A claim made by the package's WORKER.** A worker pins its own region
   through `mem_busy_seg`, not through the nest, and it cannot park itself
   while it is inside `mem_claim`. The deferred path helps here where the
   in-line path never could — the service point runs on `ui_task`, so
   `mem_compact`'s own park request can stand the worker up — but only if the
   package also declares `OSAPI_TASK_RESTARTABLE` (SPEC.md 66.6.2). Worth a
   sentence in the slot's contract and no kernel code.
2. **A region whose package owns a window the user is dragging**, or any other
   state that makes the callback boundary unwelcome. The request is advisory:
   the service point compacts what it can and wakes the asker either way.
3. **`mem_avail` still under-reports before the request runs.** §5.5 explains
   why that is left alone. A package that wants the true ceiling asks for the
   compaction and reads `mem_avail` on the wake.
4. **The mid-session mount wall itself** (`docs/plans/HEAP-UNPIN-PLAN.md` §2.0).
   This makes the wall healable on demand; it does not stop it forming.

---

## 8. How it would be verified

`tests/heapfrag` is the instrument and it already builds this scenario for a
data claim (check 13). The new row is the same check one level up:

1. The package declares `OS88_REGION_MOVABLE` and records its own base.
2. It claims through the top-down door, to put a block ABOVE its region, and
   frees it — the §2.1 geometry, built on purpose.
3. It reads `OSAPI_MEM_AVAIL`, posts `OSAPI_MEM_COMPACT_WAKE`, and returns.
4. On the wake: its base has gone **up**, and `OSAPI_MEM_AVAIL` is larger by
   the hole. Both halves are the assertion — a base that moved and a run that
   grew — because either alone can be true for the wrong reason.
5. **Two negative controls, and the second is the one §5.4 exists for.**
   With the post NOT made, the base must not move — today's behaviour, so the
   row goes red on a build without the fix. And with the region un-pinned but
   only ONE pass taken, `OSAPI_MEM_AVAIL` must come back unchanged: that is
   the 494.5K row of §5.4's table, and a row that does not assert it will pass
   on a build where half the feature is missing.

`tests/heaphi.py`'s pattern — MartyPC plus `tools/heapmap.py` against
`mem_tab` — reads the claim map off the running machine for the same
assertions from the host side, and `heapmap.Map.compacted()` already models
both passes, so it can say what the run SHOULD have become.
