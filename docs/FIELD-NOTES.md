# Field notes — things real hardware found that the harness did not

Symptoms observed on a **real 4.77 MHz 8088 under PCem v17** (and on period
machines generally) that are open, reproduced, and not yet fixed. Each entry
records what was *seen*, what has been *ruled out*, and the standing theory —
so the investigation starts from evidence rather than from scratch.

The rule these entries exist to serve: **the emulator is exact about how much
work the guest does and useless about how long it takes** (PERFORMANCE.md).
Notes 1 and 2 are things QEMU cannot show, because QEMU is ~1000x the target
machine. **Note 3 is the other half of that rule** and the happier case: the
symptom is only visible on hardware, but the suspected causes are all *work*
rather than timing, so QEMU can count them and the investigation should start
there. **Note 4 is a third shape again** — reproduced on hardware, its
mechanism *identified* rather than theorised, and now **fixed** (SPEC.md
§22.8) and reproduced under QEMU both ways: it never needed the iron at all,
it needed somebody to open a Disk window and save a file from a package. **Note 5 is a fourth, and the most valuable one to read**: a
correctness bug the harness cannot see at all, at any speed, because the
difference is in the *BIOS*, not in the timing.

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
> **THE TEXT FREEZE IS SOLVED, AND IT WAS NOT THE PAD.** `SHB 00` on the
> reporting machine settled the pad question — the shadow is intact — and the
> reporter then described the thing the pad was masking: *"when the scrolling
> empty lines reach roughly the middle of the screen the entire text screen
> stops updating for 1/3rd a second or so, then when it resumes it jumps."*
> **Reliably, every ~8 seconds.**
>
> Both halves of that are arithmetic. The blank reaching the middle is
> row 63; 64 rows at 125 BPM speed 7 is 50 ticks/s ÷ 7 = 7.14 rows/s =
> **8.96 s a pattern**. So the freeze is the pattern boundary, and the
> pattern boundary is `ttx_shbuild` — which formatted all 64 rows in one
> frame. Priced against PERFORMANCE.md Part 9's measured 8088 (RAM
> `rep stosw` 1.76 us/byte; the 4.34-clocks-per-instruction-byte floor;
> 4.66 MHz): the 9,676-byte blank is **17 ms**, the 3,776 `lodsb`/`stosw`
> pairs are **28–32 ms**, and 256 `mp_cell2txt` calls — each one a linear
> `mp_pfind` scan over up to 36 periods plus three hex fields — are the rest.
> **140–330 ms**, against a frame that otherwise costs about 6. The reporter's
> "1/3rd a second" sits at the top of that range, and the *jump* on resume is
> the view having advanced two rows while nothing was drawn.
>
> Fixed by spreading it: `TTX_SHCHUNK` = 4 rows a frame, cursor starting at
> the visible window and wrapping (SPEC.md §45.13.2). Worst frame ~25 ms.
>
> **What it does NOT explain is the audio**, and that has to be said plainly
> because the temptation is strong. The reporter says the hitch "usually
> occurs during that freeze, but it doesn't occur every time" — but
> `ttx_shbuild` runs on the bracket task with the worker still whitelisted and
> pre-emption still working (a full switch is 693 us, and the kernel's own
> tick + mouse + scheduler is 1–3% of a busy CPU). A 330 ms drawing stall
> cannot drain a ring that holds 2.2 s, and `UND 000` says the driver's own
> buffer never starved either. So the correlation is real and the causation
> is not established.
>
> **The first field reading of `BLK`/`WAKE` was `BLK 32 WAKE 29`, with
> `MIN 4`** — and those three are consistent with each other rather than with
> the freeze: 29 ticks is 1.59 s, at 5,500 Hz that is 8,745 bytes, and a ring
> that starts 8 halves deep and loses 4.3 of them lands at exactly `MIN 4`.
> `BLK 32` is then explained *by* `WAKE 29`, because `BLK` is sampled by the
> worker and a worker that did not run could not sample. So one ~1.6 s
> deschedule accounts for all three — and it is far more likely the load
> repaint than a pattern boundary, because the extremes reset only with the
> stream and the load is inside the window.
>
> **The meter has been retired for a LOG** (§45.14, `tests/trklog.inc`), and
> the reason is exactly the reading above: three numbers that are consistent
> with *one* event cannot say *which* event, and an extreme cannot be placed in
> time at all. `TRKLOG.O88` is Tracker assembled with `-DTRKLOG` and writes one
> record per system tick to `TRKLOG.TXT` — tick, consumed, total, stream state,
> song position, frames, feeds, flags, tempo — which answers all of it at once:
> a **gap in the TICK column** is the whole machine stopping, `CONS` spacing is
> every block-IRQ interval rather than the worst, and `FR 0` against `FD 1`
> separates the drawing freezing from the worker starving. Verified on QEMU:
> 706 records, zero tick gaps, block-IRQ median 7 ticks against 6.8 predicted.
>
> **THE FIRST FIELD LOG IS IN, and it settles the TEXT freeze completely.**
> 755 records over 62.1 s (1,130 ticks), 51.2 s of it inside the bracket.
> Every frame spacing in the whole fullscreen run: **432 × 1 tick, 247 × 2,
> 2 × 3, and nothing else.** The 1/3-second stall every ~9 seconds is gone,
> and it is gone *at the place it used to be*: all five pattern boundaries in
> the capture are `FL 07` followed by frames spaced 1–2 ticks, **indis-
> tinguishable from the baseline**. SPEC.md §45.13.2's spread rebuild is
> confirmed on the target machine, not just modelled.
>
> **And the audio chain measures clean over the same 51 seconds.** The DSP
> consumed **303.2 bytes/tick — an implied 5,521 Hz against the 5,500
> asked, 0.4% out** — so the card did not stall in aggregate for even one of
> those windows. The ring lead never fell below **5.0 halves (1.86 s)**, the
> stream state is `0` in every one of the 755 records, and `UND` (which is
> now `S 1`) never appears.
>
> Three things the log priced that nothing had measured before:
>
> - **Bracket entry costs 22 ticks (1.2 s)**, and it is not the video mode.
>   `trk_play` re-opens the stream there, and its 6-half pre-roll is 12,288
>   samples of `mp_gen`; at §45.9's ~2.1M cycles/s for 5,500 Hz that is
>   ~1.0 s on its own. The synchronous `ttx_shbuild` and the mode set are the
>   rest. That is a legitimate one-off at a moment the user expects a pause,
>   but it is the largest single stall in the file by a factor of seven.
> - **Windowed costs 4–5 ticks a frame against fullscreen's 1–2** (the tail
>   after Esc: 35 × 1 tick, 5 × 4, 14 × 5, 2 × 9). The text mode is ~3×
>   cheaper per frame in the field, which is §45.13's whole argument arriving
>   as a measurement.
> - **A feed pass can span 23 ticks (1.26 s)** — the longest gap between two
>   `FD 1` records. That is not a starved worker: it is one `TRK_MAXFEED`
>   burst mixing three halves while being pre-empted, and the ring goes 5
>   halves → 8 across it. It is worth knowing because it is the closest the
>   ring came to empty in the whole capture, and a burst twice that long
>   would drain it.
>
> **What the log cannot say is whether anything was audible during it**, and
> that is now the only missing datum. Every counter in the guest is healthy
> for 62 seconds; if a hitch happened in there, it is invisible to all of
> them — the third branch of the split above, below the block IRQ. So the
> instrument grew the one input that is not a measurement: **`M` stamps
> `FL` bit 10h into the current tick**, so the listener can mark the moment
> they hear one. A file with marks in it answers in one pass what no amount
> of counter-reading can.
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

---

## 3. Disk access is horribly slow, and three mechanisms are already visible

**Observed.** Navigating the file manager on real hardware feels far slower
than the work being done should justify. Not a specific operation — the
general texture of using the disk.

**This entry is different from 1 and 2 in one important way**: nothing here has
been measured yet. It was found by *code reading*, while costing the file-type
association plan (`docs/ASSOC-PLAN.md` §2.5.1), and it is recorded because
three plausible mechanisms are visible in the source and each is separately
addressable. The symptom is a field report; the causes below are hypotheses
with line numbers.

**Mechanism A — `dsk_chdir` is a full `disk_mount`.** The body is four lines
and the middle one is `call disk_mount`. So moving between two folders *on the
same volume already mounted* re-validates the BPB against SPEC.md §18.2's
17 rules, re-snapshots the FAT window, re-scans, re-sorts and re-harvests every
icon. Nothing about the volume changed. `dsk_chdir_q` (§18.9) exists and skips
the second half, but skips none of the first.

**Mechanism B — the FAT window is re-read on every one of those.**
`DSK_FAT_SECS` is 9, so that is 9 sectors per directory change on a floppy,
for a FAT that cannot have changed if nothing wrote. §18.8.1 already gives
*driver-backed* volumes a banked per-volume window for exactly this reason
("that is what stops a copy reloading nine sectors on every switch: 45 mounts,
3 loads") — **and a floppy explicitly gets none**, on the reasoning that its
window is the whole FAT and never moves. That reasoning is about the window
never *sliding*; it does not cover re-reading it from the disk.

**Mechanism C — one int 13h per sector.** `dsk_xfer`'s `.sector` loop
recomputes CHS and calls the BIOS once per 512 bytes. On real hardware a
single-sector read has missed the sector under the head by the time the next
call is issued, so consecutive sectors plausibly cost a full revolution each —
200 ms at 300 RPM. Nine "consecutive" FAT sectors would then be ~1.8 s rather
than the ~200 ms one multi-sector read would take. int 13h AH=02h takes a
sector *count*; the loop exists because it also walks the destination, which
`dskw_norm` (§18.4.1) has since made unnecessary — the offset is 0..15 and the
segment advances, so a run within one track and one 64KB page could be issued
as a single call.

**Corroboration, from an unrelated route.** CLAUDE.md already records that a
`SYSTEM.CFG` write is "2+ seconds of completely frozen UI on the floor machine
(mount, data, FAT, directory, FAT, remount)" — which puts a single mount near a
second, and was observed long before this analysis.

**What the harness can and cannot answer.** PERFORMANCE.md's rule cuts
favourably here for once: QEMU is useless about the *time* but exact about the
*work*, and all three mechanisms are **work**, not timing. Counting int 13h
calls per directory change under QEMU — the `inc word [cs:dbg_x]` counter
recipe in CLAUDE.md, on `dsk_xfer`'s `.sector` — answers A and B outright and
sizes C, with no hardware needed. **Do that first**; only C's cost per call
needs the XT.

> **PARTLY FIXED, and the rest deliberately declined.** Mechanism C is done:
> `dsk_xfer` batches a run into one int 13h (SPEC.md 18.91), which took a
> directory change from 12 BIOS calls to 5 and, because the FAT window's nine
> sectors are contiguous, took most of mechanism B with it. Mechanisms A and B
> are **not** being fixed: the only honest swap test is int 13h AH=16h and a
> 5150 with a Tandon TM100 has no change line, so reusing a FAT window there
> would give a file manager that lists correctly and reads garbage. Mechanism D
> is the remaining work. Details below and in docs/DISK-PERF-PLAN.md 3.2/4.
>
> **PICKED UP.** `docs/DISK-PERF-PLAN.md` is the plan for all three
> mechanisms, with the counting phase first, and it carries the budget grant
> that funds it. The directions below are what that plan was built from and
> stay here as the evidence; the plan is where the sequencing, the traps and
> the testing live. This entry stays **open** until the counters say otherwise.

**Directions when this is picked up**, in rough order of value-for-effort:

1. **Count first.** A counter on `.sector` and a walk through two folders.
   Everything below is speculation until that number exists.
2. **Multi-sector int 13h** for a run inside one track and one 64KB DMA page.
   This is mechanism C and probably the largest single win; the run coalescer
   in `dsk_read_chain` already computes runs, and §52.1 records that *both*
   hard-disk transports already batch a run into one command — so the floppy
   path is the one that did not follow.
3. **A same-volume, same-BPB fast path in `dsk_chdir`** — if the volume index
   and the media are unchanged and nothing has written, the BPB and the FAT
   window are already right. The disk-change line (int 13h AH=16h) is the
   honest test on hardware that has it; a media change must still fall back to
   the full path.
4. **Bank the floppy's FAT window** the way §18.8.1 banks a driver-backed
   volume's, so a same-volume chdir does not re-read nine sectors. **This may
   be much smaller than it sounds, and 3 may fall out of it.**
   `dsk_fatw_pick` already states and enforces the safety rule — "only a QUIET
   mount may reuse a banked window; a full mount is a re-validation of the
   whole volume, the disk may have been swapped" — so the swap question is
   already answered, not open. A floppy is excluded from banking because it has
   no donated claim to bank *into*, and its window is `FAT_SEG`: resident, and
   by §18.8.1's own reasoning never sliding. What is missing is not policy or a
   buffer but permission — letting a quiet, same-volume mount reuse what is
   already in memory, which needs one byte recording whose FAT `FAT_SEG`
   currently holds. Check `dsk_fatw0`/`dsk_fatd0` first; they may already carry
   it.

**Mechanism D — the icon harvest re-reads every package on every mount.**
Added after the first three. `disk_mount` step 4 reads the first sector of
every type-1 file in the directory, and mechanism A means every directory
change is a mount — so entering `APPS/` (8 packages) costs 8 extra sector
reads, ~1.6 s at C's revolution apiece, **every time you open that folder**.
It is already correctly conditional — a type-0 file gets no read and a folder
uses the built-in body — so there is nothing to save per *file*; the waste is
in doing it again per *mount*. `docs/DISK-PERF-PLAN.md` §5.5 has the options.

**What this means for the earlier caution below:** it was written before D and
said "do not assume the icon harvest is the cost". Half of that stands and half
does not. A and B are still paid on **every** directory change regardless of
contents, so in a folder of *documents* they are the whole story. But in a
folder of *programs* the harvest is real and can exceed them — which is exactly
`APPS/`, the folder a user opens most. **Count both**; the counters in the plan
separate them.

---

## 4. "Bad package" on a file that is perfectly good, until the Disk window is refreshed (FIXED, verified under QEMU)

> **FIXED — SPEC.md §22.8.** Very nearly the "Directions" below, with the
> counter turned inside out: rather than a mount generation every cache
> compares itself against, `dskw_sync` — the one routine a successful file
> operation passes through — marks `FS_DIRTY` on every Disk window showing
> the folder that changed, and `fm_focus` spends the mark when that window
> next comes to the front, re-listing and repainting **together**. A
> generation counter would have re-listed on a *paint*, which is the half of
> §22.1 that must not cost I/O; a mark spent at the focus is the same
> invalidation charged where the user is already waiting for a window.
>
> Reproduced under QEMU exactly as reported, using Note Pad in place of Gfx
> Bench: Disk window open on `B:APPS`, launch `NOTEPAD.O88`, Ctrl-S (which
> writes `NOTES.TXT` into that folder), close Note Pad. Before: the promoted
> window still says `9 files`, still lists no `NOTES.TXT`, still says
> `Free 1201K`, and double-clicking the row labelled `PAINT.O88` — index 6,
> which the rebuilt globals now call `NOTES.TXT` — opens nothing at all.
> After: the window comes forward saying `10 files` with `NOTES.TXT` in its
> sorted place, and the same double-click launches Paint. **What the harness
> could always have shown, and did not, is the whole lesson of this note**:
> the mechanism was pure bookkeeping, and nothing about it needed a 5150.

**Observed.** On a real 5150, on the boot floppy (drive A:): run `GFXBENCH.O88`
from an open Disk window, press `S` to save its report — which creates
`GFXHERC.TXT` in that same directory — close Gfx Bench, then double-click
`SYSBENCH.O88` in the *still-open* Disk window. It fails as **Bad package**.
It fails again, every time, five times running. Click **Refresh** in that
window and it launches normally. A reboot also fixes it.

**Ruled out — the disk is fine, and so is the write path.** The volume was
dumped afterwards and every file compared byte-for-byte against the originals;
`SYSBENCH.O88` was intact and `os88disk.py --verify` was clean. The failure
does not survive a reboot, and it is *deterministic* within a session, which
also rules out the marginal-media and mis-seek theories that a 40-year-old
drive invites. Nothing was corrupted at any point.

**Mechanism — this one is identified, not theorised.** It is a stale
per-window listing cache (SPEC.md §22.1) resolved against a fresh global
snapshot:

1. A package's `OSAPI_FILE_WRITE` succeeds, so `dskw_write` re-runs
   `disk_mount` — "coherence by remount" (SPEC.md §18.4). The **global**
   snapshot now has the new file in it, sorted into place by name (§19.4).
2. The open Disk window's own cache — `VIEW_KB` of heap behind `FS_VSEG` — is
   **not** touched. Nothing tells a window that a package wrote to its folder;
   only the file manager's own operations rebuild caches.
3. A double-click resolves the clicked row against that cache and hands
   `loader_run` a **directory INDEX** (SPEC.md §22.1: "the loader gets the
   poster's state block in `[ld_pwin]` as well as the index").
4. `loader_run` calls `fmv_sync` — which compares `FS_DRV`/`FS_CWD` against
   `[disk_drive]`/`[dsk_cwd]`, finds them equal, and **returns without
   re-listing**. It has no notion of "the directory changed underneath me".
5. The index is then resolved against the rebuilt globals. Every entry at or
   after the inserted name has shifted by one.

In the observed case the sorted root went

```
... FONTBNCH.O88(2) GFXBENCH.O88(3) SYSBENCH.O88(4) TASKMGR.O88(5) ...
... FONTBNCH.O88(2) GFXBENCH.O88(3) GFXHERC.TXT(4)  SYSBENCH.O88(5) ...
```

so the row the window still labelled `SYSBENCH.O88` was index 4, and index 4
in the new listing is `GFXHERC.TXT`. The loader read a text file, found no
`O8` magic, and said **Bad package** — correctly, about the wrong file.

**Which is why it is rare and why it looked like corruption.** It needs a new
name that sorts *before* something you then launch. A report saved as
`SYSBENCH.TXT` would have sorted after `SYSBENCH.O88` and shifted nothing.
And the error names the file the user thinks they clicked, so it reads as that
file being damaged.

**Directions when this was picked up** (kept for the reasoning; the fix taken
is at the top of this note). The invariant to restore is SPEC.md
§22.1's own sentence — "paints read the cache, actions re-sync". Step 4 is
where it is false: `fmv_sync` re-lists on a *location* change and not on a
*content* change. The cheapest honest fix is a **mount generation counter**:
`disk_mount` bumps a word, each state block records the generation its cache
was built at, and `fmv_sync` re-lists when the generation differs as well as
when the drive or cwd does. That is one word of kernel `.bss`, one word per
state block, and one extra compare on a path that already compares two things
— and it makes every cache in the system self-invalidating, not just this one.

Worth noting what it is *not*: it is not `[dsk_lstale]` (SPEC.md §18.9), which
tracks a debt the **global** snapshot owes after a quiet mount. This is the
opposite direction — the globals are current and a *window* is behind them.
The two want the same counter and neither can serve the other.

A second, independent hardening is worth considering at the same time:
`ld_run_body` could check that the entry it resolved is a **type-1 file whose
name ends `.O88`** before reading it, so a mis-resolved index reports
something better than "Bad package" — §47's say-*why*-not, applied to the
loader.

---

## 5. Multi-sector floppy reads returned the wrong sectors (FIXED, confirmed on PCem)

**Observed.** With SPEC.md §18.91's transfer batching enabled, *every* package
hard-froze the machine as its window drew — Note Pad, Paint, Tracker, the Task
Manager alike. A kernel identical but for one line forcing `AL = 1` was fine.
Reported on PCem; never once reproduced under QEMU, on VGA or Hercules, at
1.44MB or 360KB.

**What was ruled out first, and wrongly.** `AH=02h` answers with `AL` = the
sectors actually transferred, and a real BIOS can return **short** where
SeaBIOS never does. That is true, the transfer loop now advances by the
returned count, and **it did not fix the freeze**. Three app-side handoffs
were then built on top of the still-broken kernel and their freezes read as
three new app bugs — until Note Pad, which had not been touched, froze too.
That is the tell worth keeping: *a component you did not change failing is
evidence about the component you did.*

**Cause.** SPEC.md §18.92. int 1Eh's diskette parameter table carries **EOT**,
the last sector number the FDC may touch, and the IBM PC/XT ROM ships **EOT =
8** — a DOS 1.x number that every DOS since has overwritten at boot. os8088
never did. A single-sector transfer never consults it, so this was inert for
years; the BIOS issues READ DATA with the **multi-track bit set**, so a
multi-sector run reaching sector 9 on a 9-sector track flips to the other head
and returns **head 1's sector 1** instead, with `CF = 0` and the full count.
Correct opening sectors, wrong bytes in the middle, header validates, load
"succeeds", window draws, machine dies on the substituted code.

**Why nothing here could have found it.** SeaBIOS never reads the table. The
boot sector reads `AL = 1`, so §18.91's batching introduced the only
multi-sector int 13h in the system, and the only machines that judge it are
the ones with a real BIOS and a real FDC.

**Fix.** `dsk_dpt_init` copies the ROM's table, patches EOT to the mounted
volume's `[disk_spt]` before every transfer, and installs the vector. The boot
sector does the same for its own load, into `0000:0580` (SPEC.md §18.93).
**`make FLOPPY1=1` is the A/B** — it forces `AL = 1` in both loops and changes
nothing else, so a field run can take the batching out of the picture without
a source edit.

**Confirmed on PCem**, batching on, apps launching. Kept here because the
mechanism is worth reading before anyone touches a transfer loop again: the
harness cannot see this class of bug at all, at any speed, because the
difference is in the *BIOS* and not in the timing.

---

## 6. The cursor washes out to white while the mouse is moving (Hercules) (FIXED, awaiting field confirmation)

**Observed.** On the 5150's Hercules card, moving the mouse around makes the
arrow's white outline appear to come away from the black body — "the shadow
desyncs from the pointer" — and, watched more closely, what it looks like is
that the **whole cursor turns white** for an instant. Intermittent, only while
moving, and it never persists: stop moving and the arrow is correct.

**Long-standing, and newly visible.** It predates SPEC.md §7.1's cursor work.
What changed is that the *other* cursor flicker went away: `gfx_lock` /
`gfx_unlock` used to erase and redraw the arrow on every lock hold, including
holds that drew nothing, and that blink masked this one. Fixing the loud
problem exposed the quiet one — worth recording as a shape, because it is the
second time in this file that a fix has revealed its neighbour.

**Ruled out — it is NOT the white and black passes coming apart.** That was
the first theory and it is measurably wrong on this adapter. On a 1bpp
adapter `cur_put_mono` reads the byte under the arrow, ORs the outline in,
ANDs the body out and writes it back **in one store** (§7.1), so the halo and
the body reach the glass in the same bus cycle and cannot separate. It *was*
two passes on VGA, and that has since been fused too — but the reporter is on
Hercules, so that is not this.

**Ruled out — the drawn cell is not wrong.** A checker reads the kernel's own
`cur_save`, `cur_off`, `cur_rows`, `cur_b1ok` and the two bitmap tables out of
guest RAM, reconstructs `(saved | white) & ~black`, and compares it against
the framebuffer. Sixteen cursor positions — every shift 0..7, both screen
edges, over glyphs, over the desktop dither and inside a window — all match
exactly, and the row-0 address it derives independently agrees with
`[cur_off]` every time.

**Standing theory: it is the ERASE-then-DRAW gap, and what you are seeing is
the background.** Moving the cursor is two separate framebuffer walks —
`cur_get` puts the old cell's saved bytes back, then `cur_put` saves and draws
at the new one — so between them the cell holds the *background*. Read back
from the machine, that background is `ffff` on all twelve rows inside a window
and `aaaa`/`5555` (the 50% dither) on the desktop. **A cell of `ffff` is a
solid white blob exactly where the arrow was**, which is the symptom as
reported.

The timing fits. The pair is **5.41 icount PIT counts ≈ 568 guest
instructions ≈ 1.3 ms** on a 4.77 MHz 8088 (PERFORMANCE.md Part 9 Set 7),
against a **20 ms** Hercules frame — so the window is ~6.5% of a frame, on
every mouse packet. At ~40 packets a second while moving, that is a couple of
opportunities a second for the beam to scan that cell mid-update. "Sometimes",
"only while moving", "never persists". A long-persistence monitor phosphor
would smear it further toward white rather than showing a clean flash.

**Fixed: a move writes every byte exactly once** (SPEC.md §7.1.2,
`cur_move_mono`). The property that matters is not that the walk be a union —
it is that no framebuffer byte be written twice. The two passes still walk the
old cell and the new cell exactly as they did, and each byte is written once
because **pass 1 skips the bytes pass 2 is going to write**, and **pass 2
takes their background from the save buffer rather than from the screen**. So
there is no union to bound and no gate: cells that do not overlap degenerate
to the old behaviour on their own, because the skip never fires and the
background always comes from the screen.

It needs a second 24-byte save buffer, since pass 2 reads the old one while
filling the new, and the two are swapped by pointer so nothing is copied. The
`GFX_UNLOCK+LOCK pair` row is unmoved at 544 counts against 541 (0.6%, noise)
— the move is a different path from the lock's, and the pair pays only the one
extra indirection for the buffer pointer.

**Verified the only way a save-under can be.** A dense walk — 37 moves with
byte-column deltas of 0, ±1, ±2 and larger, in every shift phase, plus the
right and bottom screen edges where the second byte and the lower rows are
clipped away — then park the cursor back where it started and compare the
whole screen: **0 differing pixels of 237,600**. A wrong background is
permanent rather than transient, so a zero there means every one of those
moves restored exactly. And the test has teeth: with pass 2's background
source deliberately broken back to "always read the screen", the same walk
leaves **98 permanent differing pixels**.

What is NOT fixed is the planar path — VGA still moves erase-then-draw,
because its save is four planes through Read Map Select and cannot take a
background from a buffer. Its *draw* is one store now (§7.1), which was the
larger of the two windows there.
