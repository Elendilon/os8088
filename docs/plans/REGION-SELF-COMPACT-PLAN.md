# A region that can compact ITSELF — and the pass pair that has to land with it

**Status: §3's DEFECT FIX IS BUILT AND MEASURED (+35 bytes, `soak -k` 19/19
green); §5's posted request is DESIGN, not started.** Two things are wrong and
each makes the other measure as worthless. SPEC.md 66.6.1 built everything a region needs to move
and left out the only moment a package ever wants it; SPEC.md 66.4.1's
"alternatives, not cumulative" rule then means **a claim that needs both
compaction passes gets neither of them**. Fix either alone and the measured
gain is zero, which is how both have stayed invisible.

Read SPEC.md 66 first. §3 below is a defect against what SPEC.md 66 was asked
for, not a new feature, and it is the half that moves the number.

---

## 1. The report

> The program, a DOS program runner, needs massive heap for the DOS arena.
> The sound driver is mounted at the top of the heap. The DOS package runs
> under the sound driver. The DOS package calls for the sound driver to
> unmount, and it does. The DOS package asks for max heap — and it cannot
> compact into the space freed by the sound driver, so it loses 14KB of
> potential heap.

And the standing requirement it is measured against, from the ask SPEC.md 66
was built for:

> * ALL regions are movable, with the exception of the package making the call
>   and of modules. ALL packages and all workers subscribe to being movable.
> * ALL available ram is reported, and recovered when a compaction is done.

The first bullet's exception is §2. **The second bullet is not met today**, and
that is §3.

---

## 2. The caller's own region — the pin the report is about

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

### 2.1 …and the geometry it produces

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

The Browser is one of the five packages in the tree that already declares
`OS88_REGION_MOVABLE` (`rloc=160` above, against the Calculator's `rloc=0`),
so the declaration is not what is missing.

**What is measured and what is modelled.** The layout above is READ off a
running machine. The close is MODELLED — the Calculator's record is dropped
from the map that was read, which is what `mem_free` does to it — and so are
§3.1's pass figures, through `heapmap.Map.compacted()`, the tree's own
host-side model of `mem_cp_plan` (`tests/heaphi.py` and `tests/drvmove.py`
already assert against it). §7 is how the whole of it gets asserted in the
guest instead.

---

## 3. The defect: a claim that needs both passes gets NEITHER

This is the half that was mis-reported the first time this plan was written,
and it is a defect against §1's second bullet rather than a design trade.

SPEC.md 66.4 gave the compactor two passes. The ascending one packs bottom-up
claims down onto the floor; the descending one (66.4.1) packs top-down claims —
every CS on the heap: regions, driver images, modules — up against the ceiling.
`mem_cp_mine` makes a claim whose door disagrees with the pass in flight a
**barrier**, so each pass moves only its own half.

`mem_compact`'s ladder then picks **one**:

```
.plan:  call mem_cp_plan        ; CX = the run THIS pass would leave
        or dx, dx
        jz .nowt                ; nothing this pass can move
        or di, di
        jz .doit                ; "compact regardless" (AX = 0)
        cmp cx, di
        jae .doit               ; it fits → run this pass and RETURN
.nowt:  ; …park, then:
.flip:  cmp byte [mem_cp_msk], 0
        jne .undo               ; already turned round: nothing left to try
        mov word [mem_cp_msk], 0xFFFF
        jmp short .plan
.doit:  call mem_cp_run
        call mem_cp_end
        clc
.undo:  call mem_cp_end
        stc                     ; ← NOTHING WAS COPIED
```

`.doit` runs one pass and returns. For a sized claim, CF = 0 comes back only
when some **single** pass's own plan already satisfies it. So:

> If the ascending pass alone is short and the descending pass alone is short,
> `mem_compact` copies nothing at all and answers CF = 1 — even when the two
> together would have satisfied the claim twice over.

`mem_claim`'s retry loop cannot rescue it: the loop re-enters `mem_compact`
only after a call that returned CF = 0, and CF = 0 means the claim already
fits. So the two passes are never sequenced for the one claim that needs them.
The claim falls through to `mem_shed_one` and then fails, with the room sitting
there in two runs.

`mem_avail` has the same hole from the reporting side. It calls `mem_cp_plan`
once, and `mem_cp_end` leaves `[mem_cp_msk]` at 0 on every path, so what it
reports is the **ascending pass alone** (`kernel/memory.inc`, `mem_avail_x`).
Its own header says under-reporting is "the error that is invisible", and this
is that error with a second cause.

### 3.1 What it costs, on the measured layout

`heapmap.Map.compacted()` over §2.1's map with the Calculator's record dropped
— the 8KB hole standing above the Browser's region:

| | ascending | descending |
|---|---|---|
| caller's region PINNED — today | **494.5K** | 418.0K |
| caller's region MOVABLE, one pass | **494.5K** | 426.0K |
| caller's region MOVABLE, both passes | **502.5K** | |

Read the middle row against the top one. `mem_compact` takes whichever single
pass is better, the ascending one wins by 68.5K, and the answer is 494.5K
**whether the caller's region is pinned or not**. Read the bottom row: both
passes together give 502.5K — 494.5 + 8.0, the hole to the byte.

So each fix measures zero on its own, for a different reason:

- **Un-pin the caller only.** The pass that could use the answer is never the
  pass that runs. 494.5K.
- **Run both passes only.** The descending pass reaches the ceiling and finds
  the caller's region pinned, so the hole above it stays a separate run.
  494.5K.

**Together: 502.5K.** That is why they are one plan and why taking either alone
would look like a feature that did nothing.

### 3.2 What the rule was protecting, and why it survives the fix

66.4.1's argument is a cost one: *"Running both would spend the ascending copy
for a claim the descending pass was going to have to satisfy anyway — and the
descending copy is the expensive one, being over the largest blocks on the
machine."*

Keep it, by asking in order and stopping early:

1. plan ascending — if it satisfies, run it and stop. (Today's behaviour, and
   the common case.)
2. else plan descending — if it satisfies alone, run it and stop. (Today's
   behaviour.)
3. else run **both**, cheapest first.
4. else refuse.

Nothing is wasted at step 3: step 2 has already established that the expensive
pass alone is not enough, so the cheap copy is needed rather than speculative.
And the ascending pass cannot make the largest run *smaller* — it only slides
bottom-up claims onto floor paragraphs the walk has already passed, which
merges holes upward — so committing it before the descending plan is taken
loses nothing even when the claim ends up refused anyway.

### 3.3 BUILT AND MEASURED: +35 bytes, and it needs no new planning machinery

The fix is the two existing walks, sequenced — `mem_compact`'s last-resort arm
stops refusing and runs the pair instead:

```
.both:
    mov word [mem_cp_msk], 0
    call mem_cp_run             ; ...the floor packs down
    mov bx, dx                  ; DX = what it moved, banked across the second
    mov word [mem_cp_msk], 0xFFFF     ; walk (mem_cp_walk preserves BX)
    call mem_cp_run             ; ...and then the ceiling packs up
    or bx, dx                   ; DID EITHER PASS MOVE ANYTHING? mem_claim's
    call mem_cp_end             ; retry loop rests on CF = 1 when nothing did -
    or bx, bx                   ; a CF = 0 that moved nothing is an infinite
    jz .none                    ; loop there (SPEC.md 66.4's termination)
    clc
```

**Measured, not estimated** (`tools/kernsize.py`, `kern_big`):

| | bytes |
|---|---|
| `.cold` | 39,352 → 39,387 = **+35** |
| `.text`, `.bss`, `.lowbss` | **0** |
| `KERN_SIZE` footprint | 110,592 → 110,592, **no rung crossed** |
| `kern_small` | **0** — `OS88_COMPACT` is `KERN_BIG` only (`kernel/kernel.asm:381`) |

It crosses no rung but leaves the cold rung with **37 bytes of headroom** where
it had 72, so the byte is what to quote and the step is not (CLAUDE.md's
banner). `.undo` became unreachable and was deleted — `t_asmrules` caught it,
which is 3 of the 35 back.

**A combined PLAN is NOT needed, and that is what makes this cheap.** The
earlier revision of this document costed one at ~150–250 bytes because
`mem_avail` has to report a number without moving anything. It does not need
one, for a reason the deferred shape supplies for free:

> After the posted compaction has run, the heap is packed in **both**
> directions — bottom-up claims at the floor, top-down at the ceiling, one run
> between. `mem_avail`'s ascending-only plan then sees that single run and is
> **exact**. The package reads its number on the wake, after the move, instead
> of predicting it before.

So there is no third walk body, no second fill point, no invariant that a plan
must not over-report a run, and none of SPEC.md 66.4's one-body rule is
touched. `mem_cp_plan` and `mem_cp_run` stay two entries into one walk.

### 3.4 What it costs in TIME, and the honest answer is "nothing that matters"

`rep movsw` is measured at **13.3 cycles a byte** (PERFORMANCE.md Set 117.2),
which is 2.79 µs a byte and **2.86 ms a KB** at 4.77 MHz. So a compaction costs
about 2.9 ms per KB it actually moves:

| | moved | cost on a 4.77 MHz 8088 |
|---|---|---|
| §2.1's measured layout (9KB of floor claims + the 20KB region) | 29 KB | **~83 ms** |
| a DOS-runner-shaped heap (a 60KB region + ~100KB of other claims) | 160 KB | **~460 ms** |

**No existing claim gets slower.** Steps 1 and 2 of §3.2's ladder are today's
code unchanged: a claim the ascending pass alone funds still runs one pass and
returns, and so does one the descending pass alone funds. The `.both` arm is
reached only where today **nothing happens at all** — so it does not make a
success dearer, it turns a refusal into a success and charges that success the
copies it needs.

**Where a combined plan WOULD have been faster is one case only**: a claim that
even both passes cannot fund. The plan would refuse before copying; `.both`
copies first and refuses after, at the 2.9 ms/KB above. And those copies are
mostly not wasted — the heap is left better packed, and `mem_claim`'s next
tier is the *shed*, which SPEC.md 66.4 already ranks as the dearer primitive
because dissolving `MEM_P_DIRW` is priced at seconds of `int 13h`.

So on the stated rule — *~300–400 ms of difference would not buy 100+ bytes* —
this is not close: the difference in the success path is **0 ms**, and in the
failure path it is a few hundred milliseconds on a claim that was going to be
refused either way. **Take the 35 bytes.**

#### 3.4.1 The one behaviour change outside the feature, and it is separable

`mem_compact(AX = 0)` — "compact regardless" — now takes both passes where it
took the ascending one. It has two callers: the posted request of §5, which
wants exactly that, and `mem_unblob` at the end of `kmain` (SPEC.md 50.6.3).
On a machine that mounted drivers from `SYSTEM.CFG` before that point, a driver
image is a top-down movable claim (SPEC.md 66.6.3), so boot now pays one
ceiling pack: **~17 ms for a 6KB image** against a hard-disk boot of 2,087 ms
(`docs/plans/completed/BOOT-PERF-PLAN.md`). That is a boot-time *improvement*
in the thing HEAP-UNPIN-PLAN §2.0 is about — the wall a boot-order mount
builds — but it is a number `tools/os88boot.py` should take rather than an
argument, and if anyone would rather not spend it, giving the posted request
its own entry instead costs about **4 bytes**.

## 4. Option 1 from the report — move the caller's region and patch its frame

*"Allow a compaction of the calling region during the compaction, and then tell
it it moved in the return."*

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

Rows four and five can only be answered by a declaration — *"my frame holds no
copy of my own segment and no register does either"* — which the kernel cannot
verify, which a package gets right on the day it is written and wrong on the
day someone adds a `push ds`, and whose violation is **not a crash but a wrong
answer**: the package reads its own data out of a segment that is no longer its
image. SPEC.md 66.3 rule 5 already refuses its sibling for that reason.

It also couples `mem_claim` — eight near calls deep by the time `mem_cp_run`
copies anything — to the byte layout of an API cell, and it does not escape §3:
a patched frame un-pins the region and the ascending pass still wins, so option
1 built alone measures 494.5K against today's 494.5K.

**Verdict: refused.** Not because it cannot be built: because what it rests on
cannot be checked.

---

## 5. The proposal

Option 2 from the report — *"take it off as the running program, compact, and
let it claim on its next turn"* — plus §3. Three pieces.

### 5.1 The EXACT combined plan — required, and not only for the what-if

This section has been wrong twice and the corrections went in opposite
directions, so here is the settled position with the reason each earlier one
failed.

**A failed claim is DESTRUCTIVE, which is what makes a pre-post estimate
necessary.** `mem_claim`'s refusal path is compact → *shed* → retry, and the
shed dissolves purgeable caches at the claimant's own rank. SPEC.md 66.4
prices rebuilding `MEM_P_DIRW` at seconds of `int 13h`. So a package that wants
**a specific amount** — Tracker opening a 400KB module — cannot be told to
"post and find out": posting throws the caches away and then refuses anyway.
Its refusal has to mean *"I could not have had this even trying my hardest"*,
and that is the question `mem_avail` exists to answer. §5.1's earlier
*"read it on the wake"* answer is right for a package that wants **all of it**
(the DOS runner) and wrong for one that wants **an exact figure**.

#### 5.1.1 …and the +35-byte fix has already made plain `mem_avail` short

This is the finding that decides it, and it is about code already committed.
`mem_claim` compacts both ways now (§3.3); `mem_avail` still plans **one**. So
the number the SDK teaches a package to ask for is smaller than the number the
allocator would hand out — measured over the same thirteen layouts
(`tools/heapwhatif.py`):

| layout | `mem_avail` says | `mem_claim` can now deliver | |
|---|---:|---:|---|
| `[free][me][gap][gap][two movable]` | 426.5 | **474.5** | short by **48** |
| two holes, one above one below | 458.5 | **482.5** | short by **24** |
| `[free][me][gap][another movable]` | 458.5 | **474.5** | short by **16** |
| either interleaved layout | 458.5 | **462.5** | short by 4 |
| the other eight | — | — | exact |

Not a regression — it under-reports, so no promise is broken, and it
under-reported before too. But it makes the both-passes fix **inert for the
ask-then-claim pattern**, which is the pattern the SDK teaches and the only one
a package with an exact requirement can use. **So the combined plan is the
other half of the change already in the tree**, and the what-if is the same
code with a flag rather than a feature of its own.

#### 5.1.2 The algorithm, validated in the model before anyone writes assembly

`tools/heapwhatif.py`'s `exact2` — **13 of 13 layouts exact**, agreeing with the
wake reading everywhere, including both interleaved ones.

**The ordering is the whole trick, and the obvious spelling is wrong in the
dangerous direction.** Two independent sweeps — floor fill rising over the
bottom-up claims, ceiling fill falling over the top-down ones — is the natural
reading of "plan both passes", and it **over-reports by 12–20K** whenever a
bottom-up claim sits above a top-down one, because the two stacks **wall each
other in**: the lo claim is a barrier to the descending pass, so the hi claim
beneath it cannot reach the ceiling; and once the descending pass has left it
there, it is a barrier to the ascending pass in turn. Two sweeps **in the order
the passes actually run** see that; two independent ones cannot.

An over-report is the failure this whole section is about — `mem_avail`
promising memory `mem_claim` cannot produce, so the package claims, the shed
fires, and the caches go for nothing.

**The kernel cannot mutate `mem_tab` inside a plan**, so the second sweep needs
each top-down claim's *post-descending* base. Two spellings:

| | cost |
|---|---|
| ask per barrier — an O(n²) ceiling re-walk over at most `MEM_MAX` = 32 records | no scratch; microseconds, and the plan is already O(`MEM_MAX`²) |
| bank them in `MEM_MAX` words of `.bss` | 64 bytes of `.bss`, one sweep |

The first is preferred on this project's own arithmetic: a `.bss` byte is worth
a `.text` byte (`docs/plans/completed/HANDOFF-KERNEL-SIZE-P3.md`), and nothing
here is on a hot path — `mem_avail` is called when a package is about to ask
for memory, not per frame.

**Estimated ~90–120 bytes**, which is the range the requester sanctioned, and
it buys three things rather than one: plain `mem_avail` telling the truth about
the kernel it now has, the what-if (the same walk with the caller's own region
excused), and a refusal a package can trust. Unlike §3.3's +35 this is an
**estimate** — the algorithm is validated, the encoding is not.

### 5.2 One posted request

> **`OSAPI_MEM_COMPACT_WAKE`**, at the next free cell (`0x0550` today) —
> *"compact everything you can, including my own region, then wake me."*
>
> `BX` = your window. `AL` = the shed rank this compaction is to respect.
> Out: CF = 0 posted — **return from your callback**, and do your sizing and
> claiming in your `OSAPI_WM_ONWAKE` handler (SPEC.md 74.1).
> CF = 1 refused: `BX` is not your window, or one of your requests is already
> standing.

**The rank, and why it is on the request.** `mem_compact` derives the rank a
cache must be cheaper than from the *pending claim's* owner (`mem_rank_bh`), and
forces 0 — dissolve nothing — when `AX` is 0. The posted pass runs after the
asking package's turn is over, so there is no claimant to derive one from and
the default would decline to shed at all. Carrying `AL` and letting the service
point store it into `[mem_pg_rank]`'s own door is about **10 bytes**.

It is worth those ten rather than leaning on `mem_claim`'s own shed at claim
time — which would also be correct, `mem_claim`'s loop being
compact → shed → retry — because a purgeable claim the posted pass may not
dissolve is a **barrier** to that pass, so the pack it produces is worse and the
wake then needs a second shed-and-compact round to reach the same place. Ten
bytes to make the number on the wake the final one.

**One request and one wake.** An earlier draft said "two calls", meaning two
kernel-internal `mem_compact` calls, one per direction; §3.3 makes that one
`mem_compact` that runs the pair, so the package posts once and one wake comes
back.

### 5.3 It is two patterns this tree already ships, composed

**`OSAPI_PKG_REHOME` solved this exact problem once.** SPEC.md 20.12.10's slot,
in the SDK's own words:

> *CALL IT FROM YOUR ENTRY PROC AND RETURN CF=0 WITH BX=0. It only RECORDS:
> you are still executing in the region this frees, so the kernel does the
> work after you return.*

Word for word the problem here, with "frees" for "moves".

**And `ui_task` already has the quiescent point.** `kernel/ui.inc`, the top of
the event loop:

```
.loop:
    ; --- 0. a posted restart, spent with NOTHING held (SPEC.md 20.10) ---
    cmp byte [ui_rebootq], 0
```

A posted action, cleared before it is acted on, spent at the top of the loop
with no lock held and no callback in flight — and `[wm_pkgd]` is 0 there by
construction, because every `wm_pkgcall` on this task has returned. That
matters beyond tidiness: `mem_compact`'s park request DROPS `[sch_lock]` for up
to `INST_PARKW` ticks (SPEC.md 66.5), which from inside a repaint pass holding
`gfx_lock` would be a deadlock against `OSAPI_MEM_PARKSAFE` rather than a slow
path.

**So `mem_can_move`, `mem_frameless` and `mem_in_nest` are untouched.** That is
the whole argument for this shape over §4: at the service point the region is
**genuinely frameless**, and the existing predicate answers "movable" because
it is TRUE, not because it was bypassed.

Kernel side, in four pieces:

| piece | where | bytes |
|---|---|---|
| §3.3's both-passes arm | `memory.inc` `mem_compact` | **+35 `.cold`, MEASURED** |
| `[mem_cpq]` + `[mem_cpq_lvl]` | `.bss` | 3 |
| the cell — validate `BX` is the caller's window, store, `sch_uiwake` | `osapi_table` 0x0550 | ~40 body + 8 table; the closest analogue in the tree, `osapi_pkg_rehome_x`, is **33 bytes counted** for the same validate-and-record shape |
| the service — clear first, `mem_compact` at the posted rank, `wm_wake` | `ui.inc` `.loop` step 0 | ~30 |
| the rank door (§5.2) | `memory.inc` | ~10 |
| the exact combined plan + the what-if flag (§5.1) | `memory.inc` | ~90-120 |
| **the region un-pin itself** | — | **0** |

**Total ≈ 215-245 bytes resident on `kern_big`, 0 on `kern_small`**, of which 35
is measured, ~90-120 is an algorithm validated in the model but not encoded,
and the rest is anchored on a counted analogue.

**The un-pin is still free, and that remains the point of the shape.** No
predicate changes: at `ui_task` step 0 `[wm_pkgd]` is 0, nothing is loading, and
the package's worker is absent or parked — so `mem_frameless` already answers
"movable" there. The feature is *where* the compaction runs, not new code to let
it run.

**The un-pin is free, and that is the point of the whole shape.** No predicate
changes: at `ui_task` step 0 `[wm_pkgd]` is 0, nothing is loading, and the
package's worker is absent or parked — so `mem_frameless` already answers
"movable" there. The feature is *where the compaction runs*, not new code to
let it run.

### 5.4 The package needs no new question answered afterwards

After the service point the region has PHYSICALLY moved, so:

- The package is not told it moved and does not need to be. `wm_pkgcall` sets
  DS from `W_SEG` live and `mem_region_reloc` put `W_SEG` right; its own data
  claims were fixed by its own relocation proc; its near offsets never moved,
  a package being `org 0` with no relocation of any kind.
- Plain `OSAPI_MEM_AVAIL` on the wake is the number to claim, and it is exact:
  the region is where it is going to stay, so the promise form answers the
  whole run.

### 5.5 The go-round, and why the decision belongs on the second trip

A package that posted, woke, found less than it hoped for and posted again
would ping-pong. Three things stop it, and only the first is the kernel's:

1. **One request per package may stand at a time** — a second post while one is
   unserviced is refused (CF = 1). That bounds the queue, not the loop.
2. **The compaction is idempotent.** A second pass immediately after the first
   finds every claim at its fill point, counts no movers and answers CF = 1
   (SPEC.md 66.4's own termination argument), so a re-post costs a walk of 32
   records and changes nothing. The loop cannot starve the machine.
3. **The contract says decide on the wake, and the SDK macro enforces it** with
   a one-shot flag: post once, and on the wake claim what plain `mem_avail`
   reports and proceed — whether or not it equals what the what-if predicted.
   The what-if was a measurement of a state that has since changed, which is
   exactly what §5.1 says it is.

The requester's own instinct is the rule: *"on the second trip it makes its
decision, and doesn't recall the max compact a second round."*

---

## 6. What this does NOT solve

1. **A claim made by the package's WORKER.** A worker pins its own region
   through `mem_busy_seg`, not through the nest, and cannot park itself while
   inside `mem_claim`. The deferred path helps where the in-line path never
   could — the service point runs on `ui_task`, so `mem_compact`'s own park
   request can stand the worker up — but only if the package also declares
   `OSAPI_TASK_RESTARTABLE` (SPEC.md 66.6.2). A sentence in the slot's
   contract, no kernel code.
2. **On-demand MODULES stay pinned**, which is the standing decision (§1's
   first bullet): each is a temporary user action and nobody has done the work.
   A module standing mid-arena is still a barrier in both passes.
3. **The mid-session mount wall itself** (`docs/plans/HEAP-UNPIN-PLAN.md` §2.0).
   This makes the wall healable on demand; it does not stop it forming.

---

## 7. How it is verified

### 7.1 What the defect fix already ran

`python3 tools/os88soak.py start -k 'heap*' -k 'reg*' -k drvmove -k sndmove -k
hdmove -k 'rehome*' -k dsegaudit -k pgrank -k small128` — every row that boots a
machine and compacts, **19/19 ok in 7:35**, plus `fast` 37/37. `t_asmrules`
caught the arm it made unreachable, which is the dead-code gate doing its job.

What that run does NOT do is prove the fix *fires*: no shipped row builds a heap
that needs both passes, which is why the defect survived. §7.2 row 1 is that
row, and it is the one to write before this is called done.

### 7.2 What the feature needs

`tests/heapfrag` is the instrument and it already builds this scenario for a
data claim (check 13). Three rows:

1. **A claim needing BOTH passes is satisfied.** Build the two-run heap, ask for
   more than either single pass can fund, and check it lands. Today it fails
   with nothing copied, which is the negative control — and it is the row §7.1
   is missing.
2. **The caller's own region moves.** The package declares
   `OS88_REGION_MOVABLE`, records its base, claims through the top-down door to
   put a block ABOVE its region and frees it (§2.1's geometry, built on
   purpose), posts, returns. On the wake: its base has gone **up**, and
   `OSAPI_MEM_AVAIL` has grown by the hole. Both halves are the assertion — a
   base that moved and a run that grew — because either alone can be true for
   the wrong reason.
3. **The wake's number is claimable.** `mem_avail` on the wake, then a claim of
   exactly that, must succeed. This is what §3.3 rests on in place of a combined
   plan: after the pass the heap is packed both ways, so the ascending-only plan
   is exact. A row that does not assert it would let a half-packed heap through
   as an over-report.

**And the two negative controls §3.1 exists for**, without which a half-built
version passes: with the region un-pinned but only one pass taken, and with both
passes taken but the region pinned, `mem_avail` must come back **unchanged at
494.5K**. Those are the two middle rows of §3.1's table.

`tests/heaphi.py`'s pattern — MartyPC plus `tools/heapmap.py` against `mem_tab`
— reads the claim map off the running machine for the same assertions from the
host side, and `heapmap.Map.compacted()` already models both directions, so it
can say what the run SHOULD have become.
