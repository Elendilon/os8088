# Handoff: what the pass-2 soak found that is NOT pass 2's to fix

The kernel size pass ran the whole of `tests/` — 235 rows in three passes, plus
a 61-row `gfxbench`/`sysbench` comparison per adapter — against a kernel it had
just moved 4,661 bytes of. Every failure was classified against the pass's own
base commit `073d4e7` before anything was concluded from it, and **the size
work is clean**: not one failure is a regression in kernel behaviour.

What the soak *did* find is a list of defects that were already there, and it is
written down here because they cost that pass about a day of investigation each
and will cost the next session the same. `docs/HANDOFF-KERNEL-SIZE-P2.md` is
the pass's own record; this file is the queue that came out of it.

**Nothing in here is speculative.** Each item says what was observed, what was
ruled out, and what evidence exists — and where the mechanism is a hypothesis
it says so in those words.

---

## How to read the classification

Every failing row got the same two-sided treatment, cheapest step first:

1. **re-run ALONE on HEAD** — settles contention, which is the commonest cause
   and the cheapest to test.
2. **run at the base commit `073d4e7`** — settles pre-existing vs regression.
3. **bisect** — only where 1 and 2 disagreed.

The order matters: step 1 is one row of emulator time and decides whether step 2
is even the right question. Two rows were resolved by step 1 alone.

---

# A. Product defects — genuinely open, in shipped code

## A1. `trkscrl`: one scroll case of seven does nothing, at BOTH ends

**FIXED — and it was never a product defect**, which this entry called it in
bold. It is a key the test's own include bound to something the application
had already claimed.

```
down +1 rows: view  0-> 1  scrolls 1  repaints 0  ok
j    +2 rows: view  0-> 2  scrolls 1  repaints 0  ok
v    -2 rows: view  2-> 2  scrolls 0  repaints 0  FAIL
k    +3 rows: view  2-> 5  scrolls 1  repaints 0  ok
b    -3 rows: view  5-> 2  scrolls 1  repaints 0  ok
```

`tests/trkscrl.inc`'s `trk_dbg_keys` table binds `'v'` to −2. `tracker.asm`
compares `al, 'v'` for the **fullscreen SURFACE** (SPEC.md 45.13) **three lines
above** the `%ifdef TRKDBG` block that calls that table, so a `v` is answered
there and never reaches `trk_dbg_key` at all. The key was dead.

The table's own comment enumerates what not to use — *"NOT
l/p/r/x/d/w/m/1-4/f/space/Esc/Home, which the bracket already answers"* — **and
`v` is missing from that list.** The entry is `'u'` now, free in both handlers,
and all three places say why. `trkscrl` passes in 84.5 s.

**The tell was in the output the whole time and this entry wrote it down
without following it**: *"its neighbours pass, including `b -3`, which is the
same direction from a higher view and further. Nothing about `v` at view 2 is
special. That is the shape of a lost keystroke, not of broken scroll logic."*
That reasoning was right and stopped one step short — a keystroke is lost
either in flight or at the handler, and nobody looked at the handler.

## A2. `dispcheck`: a 270-second timeout, and every one of its own checks passed

**FIXED — a stale record stride, for the THIRD time in the same file.**

It hung with `TIMEOUT after 270s` and no output through the runner, which is
why nobody had looked: run directly it prints eleven lines, passes all three of
its own assertions, and then hangs in step 4, the pointer crossing.

`vid_ctx`'s per-display record is `VID_CTX_W*2+5` bytes. The row computed
`NWORD * 2 + 6` — one byte too many — so it read display 1's record a byte
late and believed

```
ctx[1] seg=5AB0 stride=768 cw=23554 ch=1 rseg=01B0 origin=(5122,256)
```

then asked the pointer to walk to **x = 16899** on a 1360-wide desktop.
`mo.to` cannot converge on that, so the row sat there until its timeout with
everything it actually tests already green.

**The file's own comment describes this failure happening twice before** — the
adapter kind moved it, then `vid_tseg` moved it, *"and it asked the pointer to
walk to x = 16769"*. The response then was to DERIVE the figure instead of
writing it down, and that is why it drifted a third time: the run's ends are
symbols and cannot drift, but the `+ 6` is a literal. `tools/os88geom.py`'s
checker could not see it either — it compares written-down copies, and this was
an expression, so it reported "267 local copies, 0 stale" over a stale one.

It comes from the mirror now, with a cross-check that the record's own run
still matches `VID_CTX_W`. `dispcheck` passes in 71 s: both cards up, the
pointer crossing and its round trip, a window dragged onto the secondary, and
fullscreen on both. **The gate had never once run to completion.**
`tests/dispband.py` carried the same `+6` in prose and is corrected too.

## A3. `GFX_BLITP` is 2.7% slower — CLOSED, it is the epilogue ladder

```
GFX_BLITP 256x16   +2.64% (cga)  +2.76% (herc)   3413 -> 3503 / 3409 -> 3503
GFX_BLITP 64x64    +2.76% (cga)  +2.76% (herc)   3409 -> 3503 / 3409 -> 3503
```

**It is the ladder, and the arithmetic that dismissed it divided by the wrong
number.** Built both ways on one tree — `gfx_blitp`'s epilogue as `jmp
kret_bp` against the seven pops written out, nothing else touched — the
Hercules bench reads **3,502 counts against 3,408**, which lands on the base
tree's 3,409 to one count. `GFX_BLIT4` in the same pair of runs moved by one
count in 642,000, so nothing else in `.text` shifted under it.

94 counts over 12 calls is 7.83 counts at 838 ns each: **31 clocks for one
taken near `jmp`**, the instruction table's ~18-22 plus a prefetch queue flush
it does not price. That is now measured and written down in three places —
PERFORMANCE.md's *What one rung of the ladder costs*, SPEC.md §15.1.2 (whose
"~18-22 clocks" was the basis for keeping eleven per-run exits out of the
ladder, a decision the real figure only strengthens) and
`docs/HANDOFF-KERNEL-SIZE-P3.md`'s reuse table, because pass 3 will add
sites.

**Why it was called unexplained**: 6.5 us was divided by the 756 us in
PERFORMANCE.md Part 1's table — "the FIXED PART of any `gfx_*` drawing call" —
and came out under 1%. But this row is a REFUSAL. `gfx_blitp` on a 1bpp
adapter checks its guards and returns (SPEC.md §5.4.3), so the call costs
238 us, not 756, and 6.5 of 238 is the 2.7% that was observed. PERFORMANCE.md
already carries *"never quote 756 as a floor a design must beat"* (Set 89) and
this is the same error one step along: never quote it as a denominator either.

**It is not worth reverting.** 6.5 us lands once per session on a machine that
refuses — §42.13.1 caches the refusal as a fact about the adapter — against 7
bytes of `.text` on the constraint that actually binds.

## A5. `dispmine` asked whether a cell opened, and meant whether the press arrived

**FIXED**, and it is the most instructive item on this page: the entry above
had already classified it — wrongly — as a contention artefact, and the first
fix for it was wrong too.

It failed **1 run in 4 alone on an idle box**, always with the same sentence:

```
the bottom row still cannot be played: a press at (248,194) opened nothing,
so it went past the window (frame 20..198) to the dock (SPEC.md 11.93)
```

The row pressed a control cell first — to prove the click path works — and
then asked whether the count of open cells had gone UP. **Two things in
`mines.asm`'s own reveal path make that unanswerable, and both were happening:**

```
    cmp byte [mn_state+bx], MN_S_COVER
    jne .out                     ; an OPEN cell is done: nothing happens
    cmp byte [mn_mode], MN_M_FRESH
    jne .armed
    call mn_place                ; lazy placement: first click always safe
```

* the control click's flood opens **anywhere from 1 to 62 of the 81** cells,
  measured, and if it reached the bottom-left one the press under test had
  nothing left to do;
* and the bottom-left cell can be one of the **10 mines**, in which case the
  press ended the game — `mn_mode` 1 → 2, `MN_M_LIVE` → `MN_M_LOST` — and
  `mn_revealed`, the only thing the row looked at, did not move.

Both read as "it went past the window to the dock" and blamed SPEC.md 11.93.

**The first fix caught only the mine** — predicate widened to "a cell opened OR
the mode changed" — and still failed 2 runs in 8, because the flood case is a
press that genuinely does nothing at all and no predicate can tell it from a
press the dock swallowed. **The fix is the ORDER.** The press under test goes
first, on a FRESH board: every cell is `MN_S_COVER` and `mn_place` puts the
mines around it, so it must open at least itself and must take the mode
`FRESH` → `LIVE`. The control is asked only when that press did nothing, which
is the one case where it has something to distinguish. **10 of 10 runs pass,
every one opening a cell**, against a measured 1-in-4 baseline.

**What this cost, and it is the page's own lesson three times over.** The
symptom named the dock, so the investigation went to `wm_hit`/`dock_hit` —
verified byte-identical to the base, correctly, and that was read as supporting
a harness explanation rather than as evidence the kernel was not involved.
Then one passing re-run closed it. Then a predicate fix was measured at 6 runs
and looked done at the 7th. The numbers were in the failure output the whole
time and nobody read the second column.

## A4. Four orphaned local blocks outside the kernel

**FIXED, and all four were dead by design drift** — each one's own comment
explains why the reachable world moved on without it:

| | |
|---|---|
| `apps/texpad` `tp_bact.next` | a copy of the routine's own FALL-THROUGH, which already calls `tp_next_page` |
| `apps/ftpd` `fd_drawctl.no` | a `stc`/`ret` in a routine that never sets CF and whose callers never test it |
| `drivers/hdd` `hd_iw_click.refused` | the greyed-control sentence. `hd_ibhit` answers 0 for a greyed button, so nothing could reach it — and its own comment half concedes it: *"a greyed control explains itself (SPEC.md 47 rule 5), so this says nothing new"* |
| `drivers/hdd` `hd_inst_apps.nboot` | *"the files are all there and the disk simply will not boot"* — a real distinction that is **no longer this phase's to make**. SPEC.md 52.10.10 moved the boot commit into the SYSTEM phase, and the branch went with it: that phase has its own `.nboot` with two live `jc`s into it. This copy stayed behind |

`ftpd.o88` −3 bytes and `texpad.o88` −5. The HDD tool driver's image is
byte-different and the same LENGTH — its packaged layout absorbed the ~13
bytes — so that half is a reachability fix rather than a size one.

**`t_asmrules` check 4 now walks `drivers/` as well as the kernel** (45 → 99
files), and the mutation test still fires. It does **not** walk `apps/`, and
that is a limit of the detector rather than a judgement: it reads fall-through
and named jumps, so a routine dispatching through a TABLE looks to it like a
wall of unreachable arms — `apps/weave/wfx.inc`'s `_wfx_eval` has 22 and
`apps/modplug`'s glyph picker 9, every one of them live. Adding `apps/` would
mean 31 exceptions to find 0 more defects, and an exception list is where this
class comes back.

# B. Harness defects — every one produces a FALSE failure

These are the expensive ones. A row that fails because the box has no compiler,
or because another row has not run yet, is noise that buries the failures that
mean something — which is exactly what the owner asked to have watched.

## B1. Install-then-boot is broken by per-instance disk isolation

**FIXED.** `os88marty.stage_run_dir()` is a run tree the CALLER owns —
`launch(run_dir=...)` leaves its media alone, so the VHD survives the install
instance closing, and `launch` re-clones the FLOPPY on every call, so the boot
gets its blank one in the same directory. `hdboot` and `knobhd` install and
boot over one disk again, in-process rather than through a subprocess.
`hdboot` 106.5 s, `knobhd` 203.9 s on both adapters, `instdeep` still 98.9 s.

**And the first attempt failed for a reason worth more than the fix.** The
install timed out after 600 s: `instdeep` watched for the MBR to differ from
**the shared master's** bytes, on its docstring's reasoning that the master
"is never written and is the pristine master by construction". It was written
— by this session's own base-side classification runs, which execute code that
predates the isolation work and installs straight onto it. Every clone then
starts with an installed MBR, the installer writes the same bytes, and the
commit is invisible. `run_install` compares against **this instance's own
disk** now, and `install` refuses an already-installed one up front with the
cure in the sentence, instead of ten minutes of nothing.


**`hdboot`, `knobhd` and probably `blitcut`.** Bisected on a clean master to
`79d34b2` — *"Take the MartyPC concurrency work into size pass 2 (host-side
only)"* — 16 files, **zero** kernel, boot, driver or app source.

`tests/hdboot.py` runs `tests/instdeep.py` as a **separate subprocess** to do
the install, then opens **its own machine** to boot it:

| | where the install lands | what the boot sees |
|---|---|---|
| before `79d34b2` | the shared master VHD | the same disk — the install |
| after | `instdeep`'s own clone, discarded with the subprocess | a fresh clone of the pristine master — nothing |

So the boot finds an empty disk and reports "no desktop from drive C:".
`knobhd` installs-then-boots the same way.

**The per-instance isolation that makes `--marty-jobs 3` safe broke the one
workflow that needs state to persist BETWEEN instances.** That is a real trade
the concurrency work made without noticing, not a mistake in either direction on
its own.

**The fix**: do both halves in ONE instance, which is also what the rows are
actually asserting. (The alternative — let `instdeep` take a target disk and
have `hdboot` pass its own instance's — keeps two processes for no gain.)

**The kernel is independently exonerated.** `make DISKCNT=1` at both commits,
same workload, counters read through SPEC.md §57's debug registry:

```
base(073d4e7)  mounts=1  sectors=9  int13=2  max=8  resets=0  -> 4.50 sec/call
HEAD           mounts=1  sectors=9  int13=2  max=8  resets=0  -> 4.50 sec/call
```

Stated with its limit: that is the boot-time mount, not an install's payload
streaming, so it corroborates rather than proves. The proof is that the guilty
commit contains no kernel code.

## B2. `blitcut` — established, and the bisect was WRONG

**FIXED, and the entry above it was the right instinct.** The mechanism is not
B1's and not the concurrency commit's at all: **it is the size pass's own
epilogue ladder.**

The row breakpointed the return of `gfx_blit4` at `S("gfx_blit4.pops") + 7` —
seven bytes of `pop` and then the `ret`, counted by hand. SPEC.md 15.1.2's
shared ladder replaced that run with a three-byte `jmp kret_bp`, so `+7` landed
on unrelated code and the breakpoint never fired. The row then waited out its
whole 240 s and reported *"no straddling canvas blit arrived"* — **a sentence
about the kernel for a fault in one host-side line**, which is why it read as a
harness or boot problem and why a bisect placed it on a host-side commit.

What found it was making the row say which of its three failure modes it was
in, which it could not do before: *"the drag finished; gfx_blit4 entered 3
time(s), 2 of them wide (cx > 200), 0 matched returns"*. The drag ran, the
blits happened, the return never fired. One line.

**The ladder's `ret` is labelled `kret_ret` now** — a label is zero bytes,
A/B'd rather than asserted — so no test needs arithmetic to point at it. A
sweep of every other computed address in `tests/` came back clean: the rest are
struct-field offsets into DATA (`drv_tab + 2*16 + 2`, `ss_row + 2`), which the
ladder cannot touch, and `tests/blitp.py` already reads its return address off
the stack, which is the idiom that cannot go stale.

**This is a regression the pass caused**, and the summary's "not one failure is
a regression in kernel behaviour" survives it only on a technicality worth
stating: the kernel is correct, the row's address went stale. It is still the
pass's doing and it was mis-attributed for a week.

## B3. `os88layout.cold_span` measures `.cold` to EOF, and `.ovlw` sits after it

**FIXED** (`e8e1110`). The span runs to `OVLW_START` now, and the two messages name what actually disagrees rather than telling the reader to rebuild a current build. Both rows pass, at 259.6s and 260.1s against a declared 60 — nobody knew what they cost because nobody had seen one finish, and the declared times are 300 now.

**`dispcold` and `dispreboot`**, both:

```
RuntimeError: .cold is 42591 bytes from file offset 60416, against a
37376-byte rung below FAT_SEG - the map and the binary disagree, so
rebuild before trusting this
```

The arithmetic settles it in one line:

```
  37,376   the .cold rung
+  5,215   .ovlw
= 42,591   exactly what it measured
```

`cold_span` computes `.cold` as `filesize − offset`, on its own stated
assumption that *".cold is the last thing in kernel.bin and ends at EOF"*.
`.ovlw` sits after it, so the check subtracts nothing for it. The layout is
identical at the base — same `OVLW_START` equate, same section order — and the
check fails identically there.

**The fix is one line**: bound `.cold` by `OVLW_START` rather than by EOF. It
belongs to whoever owns `.ovlw`.

**A warning about this one.** Its message says *"rebuild before trusting this"*,
and that sentence is wrong here and cost a wrong diagnosis: nothing was stale.
`build/kernel.bin` is smaller than a raw assembly because `make` cuts the
`.modc`/`.modf`/`.modl` module images out of it, and `bootsmoke` passed on that
very build minutes later. **A check whose failure message names the wrong cause
is worse than one with no message.** Fix the message with the arithmetic.

## B4. The suite models TOOLS, not ARTEFACTS

**FIXED** (`e8e1110`), including the half this entry did not see. `fdlggrey` and `sbar` ask for `build/muptest.img` now — verified by deleting it, after which both build it and pass. **And the helper that builds a fixture runs `make`**, which `t_registry` already requires a row to declare: THIRTEEN rows were calling it from the shareable emulator lane with `builds=False`, invisible because the detector looked for a quoted `make` at the head of an argv list and the literal is one level down. It keys on the import now.

Three rows failed where they should have skipped, for one structural reason.
`marty`, `qemu`, `nasm` and `cc` are capabilities a box either has or lacks, and
a row naming one skips cleanly. *"The wire disk has been built"* and
*"`WEAVE.WSM` exists"* are **not** capabilities, so a row needing one has no way
to say so and fails instead.

| row | wanted | did |
|---|---|---|
| `weavegame` | `build/WEAVE.WSM` (needs `cc`) | FAILED where nine siblings SKIPPED |
| `wireflick` | `build/wire360.img` (`make wiredisk`; `all` deliberately does not) | FAILED, 0.1 s, a traceback |
| `fdlggrey` | `build/muptest.img`, built by ANOTHER SUITE ROW | FAILED, 0.1 s, `FileNotFoundError` |

**Two are fixed** — `weavegame` gained `needs=("marty", "cc")`, and a `wiredisk`
capability was added beside `cc`, satisfied by the artefact's presence, which
`wireflick`/`wirefps`/`uilat` now name.

**`fdlggrey` is NOT fixed and is a different animal**: `build/muptest.img` is
built by another row of the same suite, so whether it fails depends on the
ORDER rows ran in — and with `--marty-jobs` that order is not fixed. A
capability cannot express "after that other row". Either the artefact gets its
own build step, or the dependency gets stated.

**Why this matters more than three rows.** A skip says *this box cannot answer
this question*; a failure says *the answer is wrong*. Three rows said the second
when they meant the first. `wireflick` and `uilat` are two of the five rate rows,
so a soak's pass B would have failed half its rows for a reason that has nothing
to do with rates.

## B5. `settle()` is host wall-clock, so emulator rows are box-speed dependent

`os88marty.settle(m, quiet=1.0, stable=2)` compares rendered frames one **host**
second apart. How much GUEST time a settle covers is therefore a property of the
box, and every row that settles before clicking inherits that. So do
`os88mouse`'s `time.sleep(GAP)` and `_edge`'s `time.sleep(0.02)`, which run with
the machine going.

This is the root of three separate observations:

* **`dispmine` and `tmowner` failed in the 3-wide lane and passed alone** —
  46.5 s and 203.5 s with the whole box. `dispmine`'s symptom, a press at
  (248,194) reaching the dock instead of the window, reads exactly like a real
  hit-test defect, and `wm_hit`/`dock_hit` were verified byte-identical to the
  base before the re-run was believed.

  **AND THE `dispmine` HALF OF THAT WAS WRONG — see A5.** It is not contention
  at all. It fails **one run in four ALONE on an idle box**, and the cause is
  in the test's own predicate. The classification was made on a single passing
  re-run and it should not have been: N=1 is not a rate, and "passes alone" is
  the answer contention predicts *and* the answer an intermittent gives three
  times in four.

  `tmowner`'s half stands as far as it goes — it passed at width 3 in an
  eight-row slice with three guests on four cores (205.4 s) — and stands with
  the same caveat, which is now a demonstrated one rather than a hedge: **one
  passing run is not a classification.** Neither row is marked `alone=True`.
* **`deskbench`'s scene is not reproducible to the pixel** — 78,821 / 78,825 /
  78,830 lit pixels across three runs of the same build, because
  `new_window` waits on `time.time()`.
* **`weavepack` flaked once in two runs** (D2).

**MartyPC is bit-exact deterministic in guest time.** Everything above is the
harness re-introducing host time on top of it. `m.advance(frames=N)` is the
deterministic instrument and `os88marty.until` is the bounded observable wait;
the fix in each case is to wait on something the guest publishes rather than on
stillness or on the clock.

**STILL OPEN, and deliberately not taken yet.** Rewriting `settle` onto guest
time reaches 194 files that import `os88marty`, changes how much guest work
every row gets per settle, and would want a full soak behind it. The evidence
that it is causing failures has just weakened rather than strengthened (see the
first bullet), so the honest order is: run the next full soak with B4 fixed,
and take this if anything still moves. What is NOT in doubt is the property
itself — `deskbench`'s scene really does differ by nine lit pixels between runs
of the same build, because `new_window` waits on `time.time()`.

## B6. Rows that must not share a box have no way to say so

**FIXED** — and the entry as first written was wrong about the mechanism,
which is worth keeping rather than editing away.

It said *"`serial=True` exists and `dispmine`/`tmowner` do not set it"*. Both
DO set it, and setting it does not make a row run alone: `serial=True` is what
puts a row in the SHAREABLE emulator lane, which `--marty-jobs N` then widens
to N. The only flag that made a row run alone was `builds=True`, which is a
claim about rewriting the tree. **So a row that needed the cores could only say
so by lying about building** — and the four rate rows did not even do that,
they were excluded from the wide run by hand and taken in a second one, a
workaround written into two handoffs and remembered by whoever read them.

`alone=True` says it now, and the two flags are different claims: `builds`
cannot share the TREE, `alone` cannot share the CORES. An `alone` row runs in
the one-at-a-time lane of the SAME run, so the soak is one command again.
`saverate`, `deskbench`, `uilat` and `wirefps` carry it.

**`dispmine` and `tmowner` deliberately do NOT**, and that is measured rather
than assumed: see B5.

## B7. `trkrate` never calls `no_saver()`

**FIXED** (`e8e1110`). `trkrate` passes in 106.2s. `blitcut` got the same call on `no_saver`'s own rule — it sits still for 240 HOST seconds, over thirteen guest minutes — and NOT on evidence that the saver is its current failure, which it is not. The other three are argued below and get nothing.

```
os88marty.MartyError: the screen was still changing after 120s because
SPEC.md 79's SCREEN SAVER IS RUNNING - [blk_on] is set.
```

The harness names its own cause, which is the standard to hold the others to.
The saver arms on **guest** idleness — which is exactly what a row produces when
it sets something up and then waits — so host load is not needed, only waiting.
23 test files call `no_saver`; **`dispmine`, `hdboot`, `trkrate`, `trkscrl` and
`blitcut` do not.**

**Do not conclude from this that the saver explains the other four.** It was
tried: `dispmine`'s own saved screen refutes it outright — desktop up, menu bar
reading "Mines / Game", the grid live, **no saver** — and the picture instead
shows the window overlapping the dock band. A hypothesis that explains five
failures at once is attractive precisely when it should be distrusted, and the
way to test it was to open the picture the failing row had already saved. It
cost one `Read`.

## B8. `tests/sbar.py` has three unguarded `live[-1]`

**FIXED** (`e8e1110`). One guarded reader, naming the step that lost the window.

Found while fixing `deskbench`'s crash of exactly that shape. `sbar` builds a
window list and indexes `[-1]` three times with no emptiness check, so a window
that fails to open dies with `IndexError` rather than a sentence. Not currently
failing; cheap to make legible.

## B9. A failing QEMU row leaks its emulator, and an unrelated row pays

**FIXED** (`a472b8e`). `tests/os88qemu.py` is the teardown written once; every one of the thirteen launchers registers it at its launch site, and `tests/unit/t_qemuown.py` in the fast tier keeps that true. Verified end to end: `trkscrl` FAILS, nothing survives it, and `ps2mouse` — the row the leak broke — passes straight afterwards.

Found by the PRE-MERGE GATE rather than by the soak, which is why it is here.
`make test-full` on the merge failed `ps2mouse`:

```
qemu-system-i386: Failed to get "write" lock
Is another process using the image [build/os8088.img]?
```

Two `qemu-system-i386` processes were still alive, **five hours old**, both
mounting `build/trkscrl.img` — left by the `trkscrl` classification runs of A1.
`ps2mouse` passed the moment they were killed. So a row that FAILS can leave its
emulator holding `build/os8088.img`, and the bill lands on an unrelated row much
later, wearing a message about the wrong subject.

CLAUDE.md documents the stale-QEMU trap from the other end — a previous
session's instance still answering on `build/qmp.sock` and serving the OLD
kernel, which reads exactly like a change that did nothing. Same leak, different
symptom.

**The fix belongs in the row, not the runner**: a QEMU row must tear its
instance down on the failure path as well as the success path. Worth one sweep
of every `qemu-system` launcher under `tests/` for a `finally`.

---

# C. Measurement and documentation

## C1. Hercules write cost — CLOSED, and this entry's own mechanism was wrong

The correction landed: PERFORMANCE.md's *The framebuffer is barely slower than
RAM* now carries **two figures per cell**, one per BIOS ROM, all four rows at
N=48, plus the controls. Every documented ratio was low — `rep stosw` 1.57
against 1.75/1.82, `rep stosb` 1.36 against 1.67/1.50, the read-modify-write
1.09 against 1.126/1.125 — and the section's conclusion (the mono renderer's
inner step is instruction-bound, not bus-bound) survives at 82.0 clocks per
byte end to end against RAM's 72.8.

**But the mechanism this entry named is not the mechanism.** It said the
quantity "needs N=48" and that eight samples of a bimodal cost do not average.
Two measurements say otherwise:

- **N is not the variable.** One kernel reads `rep stosb` at 8,218.0 us with
  N=8 and 8,218.6 with N=48 — 0.01% apart.
- **Nothing is aliasing against the 19.19 ms frame.** Rebuilding the block at
  33 rows instead of 32 — which moves the sample's duration, the only thing
  that moves a phase orbit — scales every row by 33/32 to within 0.02%, RAM
  and VRAM alike.

What actually moves it is the **machine**. The same tree booted on GLaBIOS and
on the IBM 10/27/82 ROM, all rows N=48, puts the four RAM rows inside 0.014%
and the VRAM rows up to **10.2%** apart, in both directions. The report's
`ISA status port in` row — an `in` from the card's own status register,
touching no memory — moves 5.5% in the same pair, which bounds it sharply:
everything that goes to the video card moves and nothing else does.

**How the wrong mechanism got written down** is worth more than the mechanism.
N was the one thing deliberately varied between two runs that gave different
answers, so it got the credit — and the table in this entry that appeared to
prove it (*"base, N=48"* against *"HEAD, N=48"*, agreeing to five figures) is
**two runs of the same kernel**: the run filed as `base` reports `kernel span
106 KB` and `boot ticks 170`, which are HEAD's, against the real base tree's
111 and 177. The five-figure agreement was real and meant nothing. A control
that cannot be told apart from its treatment is not a control, and the report
printed the field that would have said so.

**N=48 is still the right thing to run**, for a reason this entry had right:
N=8 is not biased, it is *arbitrary* — one iteration is 36% of a frame — and
it costs seconds to remove that as a question.

**One trap for whoever raises N next**: the report's derived `VRAM/RAM word
x100` row divides raw COUNTS, so it means what it says only while both rows
share an N. Patching one side alone leaves it reading 6x high.

## C2. `deskbench` had no recorded numbers — CLOSED, the table is taken

`docs/LAST-DROP-PERF.md` named `deskbench` on VGA as the measurement that would
settle whether an XOR-rect change is felt, and recorded that it *"has not been
taken"*. It has now, on all three adapters, and the table is in PERFORMANCE.md
under *What a BUSY DESKTOP costs* with its two caveats attached.

It answers less than the entry that asked for it hoped, and the reason is
worth keeping: **there is no before.** A first reading is a baseline, not a
comparison, so it cannot say the flash is new. What it can say is that the
asymmetry the entry predicts is there in the row that exercises the path —
moving the bottom window reads transient÷changed of 0.96 / 0.97 / **3.15**
across CGA / Hercules / VGA, the only row of eleven where the adapters differ
in kind — and that a second thing, which nobody was looking for, is four times
larger: **the fullscreen exit writes every pixel seven to eight times**, on
all three adapters equally, because §11.2 repaints the desktop and then each
window over it in z-order.

`docs/LAST-DROP-PERF.md`'s bullet now carries that, and says plainly that the
honest test it named — a flicker run over a held drag, built both ways — is
still the one that would settle it.

---

# D. Fixed during the pass, recorded so they are not re-derived

## D1. `deskbench` crashed on noise and three rows priced nothing

Fixed. `measure()` guarded `if not any(ch)` where the threshold has a floor of
64, so a capture holding sub-64-pixel noise passed the guard with an empty
`live` and indexed it. `release()` spent a FIXED 24 frames of the mouse packet's
flight before opening the capture and the commit was over by frame 22, so three
of eleven rows read NOTHING DREW; it waits on the guest's own `mouse_btn` now. A
press row's held XOR outline was counted as redraw where the redraw was small,
which truncated `raise Control Panel` at 4,005 ms for an operation taking nine
frames; the row calibrates its own noise floor from its capture's second half.
A `burst="last"` arm with a docstring prescribing it for release rows had **no
caller and never had one**.

## D2. `weavepack` flakes — classified, not fixed

Failed once on `TSHEET.WAB` (17 of 18 checks passed; six of seven projects
matched the host packer byte for byte), then passed alone at the same commit in
1828.6 s. It cannot be a regression by construction: `tests/weavepack.py`,
`apps/loom/` and `apps/cc/` are byte-identical at both ends of the pass, and
`apps/weave/wvm.inc`'s only change is five lines of comment.

The mechanism is B5, and `pack_one` states the hazard itself: *"a package LOAD
draws nothing while it runs, and so does a PACK, so `settle` sees perfect
stillness partway through either and returns."* It waits on the window for the
load and then falls back to three settles and a hope for the pack.

**The fix, if it is wanted:** `m.disk(reset=True)` before `^P` and poll
`m.disk()` until the write count moves — the guest's own answer to "has the pack
happened", bounded, so a pack that never writes becomes a *reported* refusal.
And screenshot the sidebar when the write never comes: the row's own `why` says
*"the sidebar has the sentence saying why"*, and the row throws that sentence
away. `weavesmoke._shot` is the family's helper.

---

# The tally

| | |
|---|---|
| rows run | 235 (pass A) + 5 (rate rows, serial) + 13 (C toolchain) |
| failures investigated | 15 |
| **regressions in kernel behaviour** | **0** |
| host-timing artefacts (B5) | 3 — `dispmine`, `tmowner` (both pass alone), `weavepack` |
| harness regressions, from a host-side commit (B1) | 3 — `hdboot`, `knobhd`, `blitcut` |
| pre-existing, identical at both ends | 4 — `trkscrl`, `dispcheck`, `dispcold`, `dispreboot` |
| missing artefact or registration (B4) | 3 — `weavegame`, `wireflick`, `fdlggrey` |
| a missing `no_saver()` call (B7) | 1 — `trkrate` |
| found by the pre-merge gate, not the soak (B9) | 1 — a leaked QEMU breaking `ps2mouse` |
| fixed during the pass | 3 — `deskbench`, and `weavegame`/`wireflick`'s registrations |
| **closed since, in this queue** | **15** — A1, A2, A3, A4, A5, B1, B2, B3, B4, B6, B7, B8, B9, C1, C2 |
| **left open** | **1** — B5, deliberately (it reaches 194 files and wants a full soak behind it, and its evidence weakened rather than strengthened) |
| **classifications this queue got WRONG and corrected** | **6** — `trkscrl` (A1, called in bold "the one genuine product defect" and it is a shadowed key in the test's own include), `dispmine` (A5, called contention on one passing re-run), `blitcut` (B2, bisected to a host-side commit and it is the size pass's own ladder), B6's own mechanism, **C1's mechanism** (it blamed N, which two measurements clear, and the table that appeared to prove it is one kernel run twice — the report printed the field that says so), and **A3's arithmetic** (it divided 6.5 µs by 756 µs, which is not this call's cost) |
| **product defects found in shipped software** | **0** |

**The one lesson, and it is one lesson.** Not one of these was a check that
failed. Every expensive hour went to a check that **passed for the wrong
reason**, or failed while naming the wrong cause: a benchmark reporting 0.0 ms
for a window that visibly moved, a layout check saying "rebuild" about a
build that was current, a bisect that skipped hangs while hunting a hang, a
baseline script that would have read an argparse error as a result. The defence
that worked, every time, was to break the thing on purpose and confirm the gate
noticed.
