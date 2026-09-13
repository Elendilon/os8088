# A region that can compact ITSELF — and the pass pair that has to land with it

**Status: DESIGN, not started.** Two things are wrong and each makes the other
measure as worthless. SPEC.md 66.6.1 built everything a region needs to move
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

### 3.3 The hard part is the PLAN, not the run

The run is two walks that already exist, sequenced. **The plan is a third
body**, and SPEC.md 66.4 names that as the one thing this feature cannot
promise loosely: *the plan promises a run the run has to deliver*, which is why
`mem_cp_plan` and `mem_cp_run` are two entries into one `mem_cp_walk`.

A combined plan cannot be a third `[mem_cp_msk]` value that simply lets the
existing walk move everything, and the reason is worth writing down because it
looks like it should work:

> **One walk can PLAN both directions and must not RUN both.** The ascending
> walk moves a bottom-up claim down onto paragraphs it has already passed,
> which is safe. Moving a top-down claim *up* in that same walk would write
> onto paragraphs still holding claims the walk has not visited — and the
> descending pass exists precisely so a top-down claim lands on already-passed
> ground. A plan writes nothing, so two fill points (one rising from
> `[mem_base]`, one falling from `[mem_top]`, each claim routed by its own
> `MC_DMA` door bit rather than by the pass) are sound for counting and unsound
> for copying.

That is the design question to settle first, and the eight direction routines
are where it lands: `mem_cp_fill0`, `mem_cp_step`, `mem_cp_near`, `mem_cp_far`,
`mem_cp_adv`, `mem_cp_dest`, `mem_cp_gap` and `mem_cp_tail` each branch on
`[mem_cp_msk]` today, and a combined plan needs them branching on the claim's
own door with two fill points carried. Three candidate spellings, in the order
I would try them:

| | shape | what it costs |
|---|---|---|
| A | a third `[mem_cp_msk]` state that the eight routines read as "route by the claim's own door", two fill points; `mem_cp_walk` refuses `BP = 1` in that state | the direction routines grow a case each; the plan/run agreement becomes an invariant a test has to hold rather than a property of one body |
| B | no combined plan at all: `mem_compact` commits the ascending pass on step 2's evidence and lets `mem_claim_1`'s retry discover the total | nothing new in the walk — but `mem_avail` still cannot REPORT the combined figure, so §1's second bullet stays unmet |
| C | combined plan derived arithmetically from the two single plans | rejected: barriers make the two runs non-additive, and the failure is an OVER-report, which is a refusal on a number the kernel promised |

A is the only one that meets the requirement. Its invariant is one sentence and
it is directional: **the combined plan must never exceed what running both
passes actually leaves.** Under-reporting is a lost byte; over-reporting is a
package told it can have memory and then refused.

---

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

### 5.1 `mem_avail` learns a WHAT-IF, and it is the report's own design

Two questions, because they have different contracts:

| call | answers | contract |
|---|---|---|
| `OSAPI_MEM_AVAIL` (+ the rank form) | the largest run a full compaction would leave **with my region where it is** | a PROMISE: a claim of this number must succeed now |
| …with the new what-if flag | the same, **also pretending my own region may move** | a MEASUREMENT of the current state, not a promise of a future one — the caller is making a plan |

The distinction is the load-bearing part and it is the requester's sentence:
*"the 'what if' of mem_avail is not a promise of a future state, but rather, a
measurement of a CURRENT state."* Plain `mem_avail` must stay claimable
immediately, so it cannot model a move that has not been arranged; the what-if
exists precisely so the difference between the two numbers is visible, and that
difference is what tells the package whether posting the request is worth a
callback boundary at all.

Both go through §3.3's combined plan. On §2.1's layout they read 494.5K and
502.5K.

### 5.2 One posted request, and it carries the rank

> **`OSAPI_MEM_COMPACT_WAKE`**, at the next free cell (`0x0550` today) —
> *"compact everything you can, including my own region, then wake me."*
>
> `BX` = your window. `AL` = the shed rank this compaction is to respect — the
> same `MEM_LVL_*` a rank-form `mem_avail` takes, so *"do not shed HIGH or
> above"* survives into a pass that runs after your turn ended.
> Out: CF = 0 posted — **return from your callback**, and do your sizing and
> claiming in your `OSAPI_WM_ONWAKE` handler (SPEC.md 74.1).
> CF = 1 refused: `BX` is not your window, or one of your requests is already
> standing.

**The rank has to be on the request, not read at the service point.** The
posted compaction runs on `ui_task` after the asking package's turn is over, so
there is no claimant for `mem_compact` to derive a rank from (`mem_rank_bh`
takes it from the pending claim's owner) and the default would dissolve caches
the package asked to keep. This is a requirement of the deferred shape rather
than a nicety.

**One request and one wake — there is no "twice" anywhere.** An earlier draft
of this plan said "two calls", meaning two kernel-internal `mem_compact` calls,
one per direction; §3 makes that a defect fix inside `mem_compact` instead, so
the package posts once, the kernel compacts once, and one wake comes back.

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

| piece | where | what |
|---|---|---|
| `[mem_cpq]`, `[mem_cpq_lvl]` | `.bss`, 3 bytes | the window to wake and the rank to respect; 0 = nothing posted |
| the cell | `osapi_table` 0x0550 | validate `BX` is the caller's window, store, `sch_uiwake` |
| the service | `ui.inc` `.loop` step 0, beside `[ui_rebootq]` | clear first, `mem_compact` at the posted rank, `wm_wake` |
| §3's ladder + combined plan | `memory.inc` | `mem_compact` step 3, and `mem_cp_plan`'s combined mode |

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

## 7. How it would be verified

`tests/heapfrag` is the instrument and it already builds this scenario for a
data claim (check 13). Three rows, because §3 and §2 fail independently:

1. **The combined plan agrees with the combined run.** `mem_avail`'s answer,
   then a claim of exactly that, must succeed — on a heap that needs both
   passes. This is §3.3's invariant and it is the row that matters most,
   because an over-report is a promise the allocator breaks.
2. **A claim needing both passes is satisfied.** Build the two-run heap, ask
   for more than either single pass can fund, and check it lands. Today this
   fails with nothing copied, which is the negative control.
3. **The caller's own region moves.** The package declares
   `OS88_REGION_MOVABLE`, records its base, claims through the top-down door to
   put a block ABOVE its region and frees it (§2.1's geometry, built on
   purpose), reads the what-if `mem_avail`, posts, returns. On the wake: its
   base has gone **up**, and plain `mem_avail` equals what the what-if said.
   Both halves are the assertion — a base that moved and a run that grew —
   because either alone can be true for the wrong reason.

**And the two negative controls that §3.1 exists for**, since without them a
half-built feature passes: with the region un-pinned but only one pass taken,
and with both passes taken but the region pinned, `mem_avail` must come back
**unchanged at 494.5K**. Those are the two middle rows of §3.1's table, and a
gate that does not assert them will go green on a build that gained nothing.

`tests/heaphi.py`'s pattern — MartyPC plus `tools/heapmap.py` against
`mem_tab` — reads the claim map off the running machine for the same
assertions from the host side, and `heapmap.Map.compacted()` already models
both directions, so it can say what the run SHOULD have become.
