# TITHE — the idle rate, measured on the built renderer

**2026-09-22**, branch `tithe-plan`, commit at the time of measuring the
parent of this file's own. Machine: MartyPC `os8088_xt_vga`, a 4.77 MHz 8088
with a register-level VGA, in this container. `tests/` has no row for it yet;
the instrument is a commit counter and a frame counter in the package itself
(`ti_ncommit`, `ti_nframe`) read over a fixed span of **guest** seconds.

This is a MEASUREMENT and true of the tree it was taken on. A later tree wants
a new file, not an edit.

## What was asked

TITHE-PLAN §1.3 predicts **3.6 fps a feature** on a fullscreen VGA, from wave
0's model `arrival + rows × R + bytes × B` (VGA 709 / 52.05 / 2.98 µs). Wave
1a's gate is that the wheel **holds 18 fps with 23 features**, and TITHE-PLAN §16.1 says
the idle rate is the question only eyes can answer — everything downstream of
it moves if the answer is no.

## What it does

| arm | band | commits/s | fps a feature (23) | frames/s | commits/frame |
|---|---|---:|---:|---:|---:|
| 2 — the table's own | 64 × 44 | 146.1 | **6.4** | 18.5 | 7.9 |
| 2 + the dirty rect | 64 × 44, 22 rows | 210.1 | **9.1** | 18.5 | 11.4 |
| 1 — three quarters | 48 × 33 | 173.9 | 7.6 | 18.0 | 9.7 |
| 0 — half | 32 × 22 | 225.8 | 9.8 | 18.4 | 12.2 |

**The frame rate is 18.5/s on every arm**, which is one wheel pass a system
tick and is the gate. What the arms move is how many of the 23 features get a
commit inside that frame.

**The dirty rect is +43.8%**, against wave 0's predicted −43% cost at a 50%
rect — the two agree to within the measurement. The rect is 22 of 44 rows,
diffed out of the poses rather than declared.

**The rate is better than TITHE-PLAN §1.3 predicts** — 6.4 fps a feature where the model
says 3.6. The calibration explains it: a 64 × 44 band measures **2,707 µs**
here where the model gives 709 + 44 × 52.05 + 352 × 2.98 = 4,048. SPEC.md
§5.4.2.6's fast path, which wave 0 put in the kernel, is most of the
difference, and the band is 352 bytes against the plan's 392.

## The calibration

`ti_calibrate` times **two heights** and separates the model's two terms:

| | |
|---|---:|
| one blit, 44 rows | 2,707 µs |
| one blit, 1 row | 852 µs |
| **per row** | **43 µs** |
| **arrival** | **809 µs** |

Wave 0's VGA figures are 709 and 52.05 + 2.98 × 8 = 75.9 µs a row at this
stride. The arrival agrees within 14%; the per-row term is lower for the fast
path's reason above.

## Three defects this measurement found, in the order they hid each other

1. **`ti_calibrate` was never called.** It was the `R` key's alone, so the
   wheel ran on the guess — 3,340 µs against a real 2,707 — for ever. It is
   called from `ti_relayout` now, wherever the layout is cut, because the cost
   moves with the sprite arm.
2. **`TI_CALN` blits were timed in ONE PIT span.** Counter 0 counts down and
   reloads every 54.9 ms, so sixteen 4 ms blits wrap it and the subtraction
   means nothing; it read **0 µs a band**, which is a credit the wheel cannot
   divide by. It is eight samples of ONE blit each now.
3. **The wheel charged a flat price.** With `[ti_bandus]` charged per commit,
   a half-height commit cost what a full one did — so the wheel drew the same
   number of features and finished its frame earlier, and **both levers
   measured at zero**: the dirty rect read +0.6% and the sprite arms read
   3.5 fps on all three. Charging `arrival + rows × R` is what makes them
   visible, and it is what §97.5 said to do.

The third is the one worth keeping: a credit model that does not price what it
is measuring will report every optimisation as worthless, and it will do it
without failing anything.

## The combat frame

`A` sustains projectile fire down a lane, so the number is the frame's rather
than one bolt's.

| | commits/s | commits/frame | frames/s | bolts/s |
|---|---:|---:|---:|---:|
| arm 2, dirty rect | 210.6 | 11.2 | 18.7 | — |
| …+ one projectile | 169.4 | 9.7 | 17.5 | 17.5 |
| arm 2, whole band | 145.6 | 7.8 | 18.6 | — |
| …+ one projectile | 115.5 | 6.2 | 18.6 | 18.7 |

**One bolt costs about 1.6 feature commits and the frame still holds.**
TITHE-PLAN §3.9.1 predicts 8.88 ms for a projectile frame — 16% of a 54.9 ms
tick — against the ~20% measured here, so the model and the machine agree and
its *"one a side is 51% of a frame and comfortable"* reading is confirmed. Four
a side, which that section measures at 102% of a frame, is not tested here.

## The row that keeps it

`tests/titheframe.py`, `soak -k titheframe`, 150 s. It asserts the frame holds
a pass a tick, that the calibration ran and its two heights are ordered, that
the dirty rect buys at least 20%, that the three sprite arms differ, and that a
projectile costs the idle something without stalling the frame.

**Broken on purpose first** (`docs/WRITING-TESTS.md` §1): charging the flat
`[ti_bandus]` again fails exactly one check — the dirty rect's, at +0.3% —
which is the defect it exists to catch.

## The clash, and what tier B taught

`C` fires a clash in one lane's front line; `V` steps its tier.

**Tier A is two ordinary bands** — each fighter steps 8 pixels toward the line
and back, in its own rectangle — so it costs exactly what two idle commits
cost and works on every adapter at every sprite size.

**Tier B's band is a cell tall PLUS A RISE.** Columns 1 and 2 are one `RISE`
apart vertically, so a two-cell band is not a rectangle in board space: cut to
one cell's height it composes both figures at the same y and puts one of them
a whole rise out of place. Built correctly it is 24 × 68 = 1,632 bytes on a
windowed VGA against TITHE-PLAN §3.9.2's estimate of 1,456 for a
non-sheared 208 × 56 — the rise is the difference, and it is 12% the plan did
not have.

## What is NOT built

**The fullscreen renderer (§97.6, TITHE-PLAN §3.1.1).** It is a second
renderer rather than an arm: after `OSAPI_FSX_MODE` no kernel drawing slot is
legal (§53.7), so that arm letters its own HUD and draws its own panel. `F`
steps the fullscreen *geometry row* in a window today, which is the surface
table's other row and not the other renderer, and it refuses where the row will
not fit — which is the honest answer rather than a silent half-measure.

## The field answered the rate question — the other way round

**Reported off a Hercules**: at the 40% share the idle is **too fast**. The
share had to be stepped down repeatedly before the pose cycle looked right.
TITHE-PLAN §16.1 calls this the sharpest question in the document and frames it
as *"does 3.6 fps read as a crowd idling or as a slideshow"* — and the built
renderer runs at 6.4, which reads as neither: it reads as hurried.

Keeping 40% would mean **doubling the pose count** so each step is smaller,
which is art nobody has room for. Halving the share costs nothing and lands the
cycle on 3.6 fps a feature, which is the rate TITHE-PLAN §1.3 predicted all
along.

| | commits/s | fps a feature | frames/s |
|---|---:|---:|---:|
| idle, 20% share | 81.6 | **3.5** | 18.6 |
| …+ dirty rect | 113.5 | 4.9 | 18.6 |
| …+ a projectile (no rect) | 124.9 | 5.4 | 18.5 |
| …+ both | 133.3 | 5.8 | **13.3** |

**The surplus pays for combat beside the idle rather than instead of it.**
`TI_COMBAT` is 25% more of a frame while something is in flight, so a
projectile no longer takes lanes out of the idle — the idle *rises* to 5.4 fps
with a bolt flying, because the allowance is larger than the bolt. The plan's
TITHE-PLAN §3.8 concession is one the machine does not have to make.

### The one combination that does not hold — OPEN

**Dirty rect AND a projectile together runs at ~13.3 passes a second** against
the wheel's 18.2. §97.5's overrun watch is built now and it *fires* — the trim
falls to 79% — and **trimming the credit does not recover the rate**, so that
frame's cost is not in the commits the credit gates. The projectile's own path
is the suspect: `ti_pj_step` runs before the credit walk and is bounded by
nothing.

`tests/titheframe.py` carries it as a **ratchet at 12 frames/s** rather than a
silence: raising that floor to 15 is the fix's own gate, and a drop below 12 is
a regression on top of it.

## A hover bug the field caught

*"The mouse over only worked for one frame."* On a hover change only the card
that **lost** it was redrawn; the one that gained it was left to feature 22,
which draws the **unit alone** at a box `ti_card_draw` banks — and nothing had
banked one for the new card. So the hover animated only while a full repaint
happened to have set the box up. Both cards are redrawn on a change now.
