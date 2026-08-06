# Field notes — things real hardware found that the harness did not

Symptoms observed on a **real 4.77 MHz 8088 under PCem v17** (and on period
machines generally) that are open, reproduced, and not yet fixed. Each entry
records what was *seen*, what has been *ruled out*, and the standing theory —
so the investigation starts from evidence rather than from scratch.

The rule these entries exist to serve: **the emulator is exact about how much
work the guest does and useless about how long it takes** (PERFORMANCE.md).
Both notes below are things QEMU cannot show, because QEMU is ~1000x the
target machine.

---

## 1. Audio tails off for ~1/3 second, every few seconds (Tracker)

**Observed.** A MOD plays normally for a few seconds, then the sound "slows
down" or tails off for about a third of a second, then continues normally.
The cycle repeats. Reported on a real 8088 at 4.77 MHz.

**Ruled out — this is NOT the fsx work.** The reporter A/B'd the shipped
images against `a4facf0`, the commit immediately *before* Tracker moved onto
the §53 bracket (Tracker still on §11.2 `wm_fullscreen`, its worker still
doing `feed` then `render` in one slice). **The stutter is present in both.**
It is therefore older than the fsx adoption and is not the bracket, the
freeze, `FSXF_KEEPWORKER`, or the drawing/feeding split.

Also ruled out by the same session: it is **not** about what is on screen.
The reporter saw it fullscreen, windowed, with the Tracker window *completely
covered* by another window, and *minimized*. Covered and minimized are the
cases where the drawing path does the least work (§11.3's clip region skips
it, `wm_obscured` vetoes it) — so a redraw cost that crowds out the audio feed
is a poor fit for the evidence.

> **PARTLY RESOLVED, and the remainder has moved somewhere specific.** The
> **first** hitch — the one about half a second into the first play after a
> load, absent on a stop-then-restart — was the pre-roll boundary, and
> `TRK_PREROLL` = 6 fixed it: the cushion is now staged before the stream
> opens, with no DSP consuming anything, instead of being deepened by the
> worker in competition with playback (SPEC.md §45.2). The reporter confirms
> it is gone.
>
> The **later** hitches are still there, and the margin meter (§45.14, the D
> key) has now answered the question the analysis below was built to ask.
> On the reporting machine, across hitches, it reads **`MIN 6  LATE 000`** —
> pegged. 6 halves is the pre-roll value, so the ring was **never drawn down
> at all**: at 5,500 Hz the DSP always had 2.2 seconds of audio in hand, and
> not one feed wake ever arrived with under one half. That kills the two
> theories the analysis below spends its length on. It is **not** mixer
> throughput, and it is **not** CPU contention from drawing — a repaint
> cannot starve a ring that never drains. The meter's own doc comment
> anticipated this reading: *"MIN staying high while the audio still hitches
> says the feed was never the problem and the fault is downstream."*
>
> **Downstream means one specific buffer.** There are two in the chain and
> they have different pacers: Tracker's 16KB staging ring in its grant, fed
> by the package worker (this is all `MIN`/`LATE` can see), and the driver's
> **2 × 2KB DMA double buffer** at `SND_SEG:0`, fed by `sbl_refill_task`
> (SPEC.md §34.5). If the half the DSP wants next is not valid at the block
> IRQ, `sbl_isr` pauses output (D0h) and marks the stream `SBL_ST_UNDER` —
> bounded silence, never stale audio looping. **One 2KB half at 5,500 Hz is
> 372 ms**, which is "tails off for about a third of a second" to the
> precision of the report.
>
> Nothing in the app could see that, which is why it went unmeasured for two
> rounds: an underrun-pause stops `consumed` advancing, so `total − consumed`
> *grows*, and the meter reads healthier the worse it gets. The app was
> already polling the state (verb 3 returns it in AX every wake) and
> discarding everything but `ENDED`/`STALE`.
>
> **`UND` came back `000` too**, on the same machine, across hitches. So the
> driver believes it is playing throughout: its own double buffer was never
> starved either. Every buffer in the chain is provably full at the moment
> the sound tails off.
>
> **The content is exonerated as well**, and that one was settled here rather
> than in the field, because content is exactly what QEMU *is* exact about
> (PERFORMANCE.md). `BEVERLY.MOD` was captured through an SB16 twice —
> once in XT mode at 5,500 Hz, once at 11,000 — and the two amplitude
> envelopes match block for block, with their only two real dropouts at
> **7.50–8.75 s and 16.50–17.50 s in both**. Those are the song. There is no
> periodic tail-off anywhere in 67 and 80 seconds of capture, at either rate,
> and a mixer arithmetic bug would neither be rate-independent nor absent.
> (`make test-snd SB16=1` plus a block-RMS profile of `build/snd.wav`; the
> two rates matter because a rate-dependent overflow was the leading content
> theory, and identical envelopes kill it.)
>
> **So: the app is fine, the driver is fine, the samples are fine, and the
> emulator cannot see it.** That is a timing defect that exists only on the
> real machine, below the driver's bookkeeping — which is a much smaller
> place than where this started.
>
> **The next instrument is `BLK` and `WAKE`, on the same D line** (§45.14).
> `consumed` advances by one whole half and only from `sbl_isr`, so the
> wall-clock gap between two different readings **is** the block-IRQ
> interval — 6.8 ticks at 5,500 Hz — and `WAKE` is the same measurement for
> the worker's own pass, as a control. Baseline under QEMU: `BLK 08 WAKE 01`.
> Three outcomes, and they need no interpretation:
>
> - **`BLK` ≈ 13–14 with `WAKE` at 01** → a block IRQ arrived one whole
>   period late or was lost, while this app ran perfectly. 372 ms is the
>   reported hitch, exactly. On single-cycle DSPs (< 2.00) `sb.inc` already
>   records a known bound of that species: the ISR reprograms the 8237, whose
>   byte-pair flip-flop is shared with the BIOS's channel-2 programming
>   inside int 13h. Check the reporting machine's DSP version first — that
>   branch is the one QEMU never runs.
> - **`BLK` and `WAKE` both climb** → the whole machine was descheduled, and
>   `sch_lock` held across int 13h (§7, the one sanctioned long lock) is the
>   first suspect. That is theory 1 below, and this is how it gets confirmed
>   without instrumenting the kernel.
> - **Both stay at 08/01 through an audible hitch** → the interruption is
>   below the block IRQ, in the DSP or the analogue side, and nothing running
>   on the CPU can measure it. That is the point to stop instrumenting the
>   guest and start swapping hardware.
>
> **The text screen visibly emptying is a separate observation, and it has
> two possible meanings that matter very differently.** `SHB` (§45.14) tells
> them apart in one number, live, and the QEMU reading is `SHB 00` with the
> top nine rows of the area blank at row 0 — i.e. the expected one.
>
> - **`SHB 00` — it is the pad, and the pad is by design** (§45.13.2). The
>   shadow carries `TTX_HALF` = 9 blank rows above pattern row 0 and below row
>   63 so the blit window needs no clamp; they are on screen at the ends of
>   every pattern. Watched rather than reasoned about, the second one reads
>   exactly as reported: the lower half loses its text while the upper half
>   keeps scrolling. **The useful consequence is that it is a free, precise,
>   visible clock.** The blank reaching its full nine rows *is* row 63, so
>   "the audio hitches at the end of the missing lines" times the hitch to the
>   **pattern boundary** — the one frame in ~8 seconds that costs 256
>   `mp_cell2txt` calls and 4,838 word stores instead of 1,121. The honest
>   reading of that, though, is **correlation and not cause**: a one-frame CPU
>   stall cannot starve a ring that `MIN 6` says never drew down, and `WAKE
>   01` says the worker kept its slice. If the hitch really does land there,
>   what to look at is `BLK` on that same frame — a pattern boundary costing a
>   block IRQ would be a real finding, and a pattern boundary merely being a
>   memorable place in the music is the null result.
> - **`SHB` non-zero — something is writing into Tracker's bss**, and that
>   would change the audio investigation completely rather than adding to it.
>   The shadow is 9,676 bytes of a 30,498-byte bss, the largest single object
>   in it, so a wild write lands there first by probability alone — and the
>   *same* writer would reach `mp_voltab`, `mp_chans` and `mp_outbuf`, where
>   the symptom is not a blank row but **a channel going quiet or an
>   amplitude going wrong**. That is one root cause for both reports, and it
>   would explain the thing that is otherwise strange about them: every
>   transport counter reads perfect because the transport is faithfully
>   delivering corrupted samples. It would also have to be 8088-specific,
>   since QEMU shows neither symptom — and the one known 8088-specific
>   memory hazard in this tree is the one `tests/stackprobe` exists for (a
>   real BIOS services interrupts on the current task stack; SeaBIOS does
>   not). That lands in `LOW_SEG` rather than package bss and `SCH_MAGIC`
>   would catch it, so it does not fit as written — but it is the right
>   family to think in, and `stackprobe` on the reporting machine is the
>   cheap first move.
>
> Everything below this line is the earlier analysis, kept because its
> ruling-out is still valid and because the two theories it eliminates are
> the ones anybody would reach for again.

**Second report, and it moves the needle a long way.** The hitches land at
roughly the **same point in the song** each time — so the trigger is
song-position-correlated, not wall-clock-periodic. There is **always one
about half a second into the first play after a load**, and that one **does
not happen on a stop-then-restart**. A later one lands maybe ten seconds in
(approximate — not measured).

That set is very restrictive, and the arithmetic of the ring is what makes it
so. On a tier-0 machine XT mode is auto-armed (§45.9, `osapi_cpu_info` in the
entry proc), so the rate is 5,500 Hz, and with `TRK_RING` = 16,384 and
`TRK_HALF` = 2,048:

| quantity | at 5,500 Hz (XT) | at 11,000 Hz |
|---|---|---|
| one ring half | 372 ms | 186 ms |
| whole ring | 2.98 s | 1.49 s |
| **pre-roll (2 halves)** | **744 ms** | **372 ms** |

**The first hitch is the pre-roll boundary.** `trk_play` pre-mixes two halves
and starts; that buffer is all the slack there is, and when it runs out the
worker's own refill has to carry the stream for the first time. Half a second
in is exactly where that happens. So the question is not "what stalls the
machine at 0.5 s" — nothing does — it is **"what is competing with the worker
during the first second after a load, and only then"**.

The answer that fits *"not on a restart"* is the **full-screen repaint a load
performs and a restart does not**: the completion callback ends in
`tui_draw_all`, the whole FT2 screen, which on a 4.77 MHz machine is hundreds
of glyph cells and hundreds of milliseconds of UI-task work. It cannot block
the worker (the feed takes no lock), but it does halve its CPU share while
round-robin has two runnable tasks — and if the mixer needs more than half a
CPU at this rate, the ring drains for exactly as long as the repaint lasts.
The later hitches fit the same shape at pattern boundaries, where
`tui_draw_dyn` escalates to a full pattern redraw: a 64-row pattern at 125 BPM
speed 6 is **7.7 s**, which is the right order for "maybe ten seconds", and
pattern boundaries are at fixed song positions — the "same point in the song"
observation.

**The one piece of evidence that does not fit** is from the first report:
covering the window completely and minimizing it did not help. Both should
skip the drawing outright (`wm_clip_set` refuses, `wm_obscured` vetoes). If
that holds up under a careful re-test, the drawing theory is dead and the
answer is the other one below — the mixer simply not sustaining real time on
this content, with the ring hiding it until it drains.

**Two decisive experiments, in this order.** Both are minutes of listening,
no code:

1. **The Rate menu (R, or Rate ▸).** Mixer cost is linear in output samples,
   so 22 kHz doubles it while leaving every UI cost identical. If the hitches
   get markedly worse or more frequent, the cause is **mixer throughput**; if
   they are unchanged, it is **CPU contention from drawing**.
2. **Minimize, then play through a known hitch point** (say the ~10 s one),
   twice, listening for it. This re-tests the one contradictory data point
   deliberately rather than in passing.

**Standing theories, cheapest first.**

1. **A periodic kernel activity that holds the CPU or `sch_lock` long enough
   to starve the ring.** The period ("every few seconds") and the duration
   (~1/3 s ≈ 6 ticks) are the shape of something scheduled, not something
   continuous. Candidates with a period: the menu-bar clock cell (§12.1, once
   a second — too frequent), the Control Panel's `cp_tick`, a floppy **motor
   spin-down** or any residual `disk_read` (`disk.inc` raises `sch_lock`
   across int 13h — the one sanctioned long lock, §7), and the Task Manager's
   sampler if a window is open. **A floppy access is the strongest fit**: it
   is periodic-ish, it holds `sch_lock` for exactly the kind of duration
   described, and it happens regardless of what is on screen — matching the
   covered/minimized evidence.
2. **The mixer's own cost against the ring's depth.** If a refill pass
   occasionally has to mix more than one half (`TRK_MAXFEED` bounds it at
   several), the worst-case pass on a 4.77 MHz machine may exceed the ring's
   remaining play time, and the DSP underruns until the next pass catches up.
   That would be periodic in the *music*, not the machine — checkable by
   whether the tail-off lands at the same song positions each loop.
3. **The §34.5 stream watchdog rewinding on a late refill**, which by design
   pauses output rather than playing stale samples.

**How to investigate.** The one measurement that separates theory 1 from 2:
instrument `sch_lock` hold time (or count `disk_read` entries) and see whether
a spike coincides with the tail-off. PERFORMANCE.md's counter-over-QMP recipe
is the mechanism, but the *timing* only reproduces on real hardware or a
cycle-accurate emulator — PCem is the right tool here and QEMU is not.

---

## 2. Heap fragmentation: a second Tracker load says "Out of memory"

> **RESOLVED — two real bugs, both fixed.** The reporter's order of
> operations (open Tracker, load, **play**, close, reopen the file manager,
> open the Task Manager, open Tracker again, load → refused) pinned it. The
> driver's 20KB staging pool was being stranded mid-heap two different ways:
>
> 1. **`DSV_RELINST` only released the FM half.** The cell published
>    `opl_release_inst`, which keys off OPL channels and touches nothing of
>    the Sound Blaster — so **closing a package that had streamed left its
>    staging grant behind, and with it the pool, for the rest of the
>    session**. That is the reporter's exact path. It is now
>    `snd_release_both`, which releases both halves and is published by
>    *either* half attaching (a card with no OPL still has memory to give
>    back). Measured: System heap stayed at 122K after a close-while-playing
>    and now returns to 102K.
> 2. **Tracker held its ring grant for its whole lifetime**, allocating it
>    once and leaving it to teardown — so even a *stopped* Tracker kept the
>    pool claimed. It now frees the grant in `trk_stream_close`, after the
>    worker-park handshake the SDK's one author rule requires. Measured:
>    System 122K while playing → 102K on stop → 122K on replay.
>
> The general lesson is the one §50.3 already states and this is the first
> field proof of: **a long-lived claim in the middle of the heap splits it**,
> and the total free figure will happily say there is room while the largest
> run says otherwise. The analysis below is kept because it is still the
> right way to think about the next one.


**Observed.** On a 384KB machine: launch Tracker, load `BEVERLY.MOD`
(116,085 bytes) — fine. Then load again (or run a second instance), and the
splash reads **`Out of memory`**. The Task Manager at that moment showed:

```
RAM 279/384K   HEAP 208/312K
System   0600  71K   50K heap
Packages       41K
  TRACKER 5640 33K  114K heap
  TaskMgr 5440  8K    —
```

So ~104KB of heap was free and the module needs ~114KB — but the interesting
question is *why the free space could not be reused*, because Tracker **frees
its old buffer before claiming the new one** (`tracker.asm`: the
`OSAPI_MEM_FREE` at the top of the load path runs before the
`OSAPI_MEM_CLAIM`). A straight free-then-claim of the same size should always
succeed on an unfragmented heap.

**What the code says (checked while writing this note).**

- The Sound Blaster driver's **DMA buffer** is claimed in `sbl_attach` — i.e.
  at **boot**, on an empty heap, before any app runs — and freed only at
  detach. It is not a late claim and is *not* the fragmenting party, so the
  original guess ("the driver took a buffer after Tracker had loaded") is not
  quite it for that buffer.
- The driver's **20KB staging pool** (`SBL_POOLKB`) *is* a late claim:
  `sbl_pool_get` takes it on the first stream grant — that is, **after**
  Tracker has already claimed its module buffer — and `sbl_pool_put` releases
  it when the last grant goes. **This is the fragmentation candidate**: it
  lands *above* Tracker's module claim, so when the module is freed the hole
  it leaves is bounded above by the pool, and the largest free run can be
  smaller than the total free.
- §50.3's design anticipates exactly this: package **regions** are claimed
  top-down (`mem_claim_hi`) and data claims bottom-up *because* "a long-lived
  data claim mid-heap permanently splits the space". The pool is precisely
  such a claim, and it is long-lived relative to a load/free cycle.

**Standing theory.** Free-then-claim of ~114KB fails because the freed hole is
no longer the largest contiguous run once the driver's staging pool (and
possibly the Task Manager's own claims, which were open in the screenshot)
sit inside the heap. The total says there is room; the *largest run* is what
`mem_claim` needs, and `OSAPI_MEM_AVAIL` deliberately reports both for this
reason.

**Directions when this is picked up.** In rough order of value-for-effort:
claim the staging pool at attach like the DMA buffer (trading 20KB of resident
heap for no mid-heap claim); or take it from the top like a region; or give
`mem_claim` a compaction-free "grow into the adjacent hole" path
(`mem_regrow` already does something adjacent); or have Tracker size its
request from `OSAPI_MEM_AVAIL`'s **largest-run** figure and say so honestly
rather than failing late. **Do not add a compacting allocator** — a region's
base is its CS and can never move (§50.3).

**A related honesty bug worth fixing at the same time:** the splash says only
`Out of memory`. It should say which figure failed and how short it was —
`bb_avail`'s pattern (§47: say *why* not).
