# What a hover costs TITHE's panel — 2026-09-23

Taken on `tithe-plan` at the commit that fixed it, on `os8088_xt_vga` under
MartyPC (a cycle-accurate 4.77 MHz 8088). The instrument is
`$SP/tihovrate.py`'s shape: a FIXED number of hover changes driven between two
known points, frames counted from `ti_nframe` and elapsed taken from the BIOS
tick at `0040:006C` — **not** host wall clock, and **not** a free sweep.

**A free sweep is not a measurement.** The first attempt moved the pointer down
the seven cards and divided frames by guest seconds, and the same build read
7.8 and 9.3 back to back: how many hover changes a sweep makes depends on mouse
packet timing. Ten changes between two fixed points is repeatable.

## The numbers

Idle, pointer parked: **18.6 fps**, 88.5 commits/s — the same whether it is
parked on a card or on the board.

| ten hover changes between | before | with the block redraw | with no status redraw at all |
|---|---|---|---|
| card ↔ card | — | **12.5 fps** | 14.2 |
| card ↔ board | — | **15.4** | 16.8 |
| board ↔ board | — | **16.9** | 18.5 |

And the free sweep, in the field's own terms: **4.9 fps before, ~8.6 after**,
against 18.7 parked.

## What the work is

| | pixels |
|---|---|
| the HUD strip, whole | 640 × 36 = **23,040** |
| one card, panel width | 128 × 32 = **4,096** |
| the status LINE's own rectangle | ~310 × 6 = **~1,900** |

A hover change redraws **two cards** — the one that lost it and the one that
gained it — and the status. Blitting the whole strip made the strip three
quarters of the work, and none of it had changed: the round, the phase and the
toggle are the same bytes they were.

## What was NOT the cost

**The twenty-cell walk.** `ti_hover_ck` asks the board which cell the pointer
is over by walking all twenty and calling `ti_cellpos` on each, every frame.
That was the first suspect and it is not the answer: sweeping the *board*
exercises the same walk, changes the same status, and stayed at 18.2 fps while
sweeping the *cards* was at 4.9. The walk stays — `ti_cellpos` is the only
thing that knows where a cell is, and inverting the shear in a second place is
how two answers get to disagree.

## What is left

14.2 against 18.6 is the two card blits, and that is the design: a hover change
moves two cards. 12.5 against 14.2 is the status, at ~1,900 pixels plus one
arrival, which is proportional to what it draws. Nothing here is pathological
any more; the next lever would be deferring the status onto the lane system
(SPEC.md §97.5.1) so it competes for credit rather than being unconditional
work, and that is not worth its machinery at this rate.

---

# Part 2 — what it actually was

The first half of this report blamed the HUD strip and cut it to the status
line's own rectangle. That was real (4.9 → ~8.6 fps on a free sweep) and it was
**not the main term**. The field came back: the stutter was still there, it was
only on landing ON a card, and it ended the moment the card's figure started
moving.

**Every whole-frame A/B answered "the card draw"**, which is a routine and not
a cause: nopping the blit, the text, the frame, the invert or the unit each
left the transient unchanged, and nopping the whole of `ti_card_draw` removed
it. That is what a cost distributed across a routine looks like — and it was
wrong. The frame counter is quantised to 4 ticks per sample here, which is too
coarse to divide 110 ms among seven stages.

## The instrument that settled it

`TICARDPROF=1` brackets each stage of one card with the PIT (`ti_pit`, the same
reader `ti_calibrate` uses). One boot, one hover, six numbers:

| stage | before | after |
|---|---|---|
| clear the band | 1.3 ms | 1.3 |
| **`ti_cb_frame`** | **36–44 ms** | **2.5–2.9** |
| **`ti_cb_frame2`** (hovered) | **38–42 ms** | **2.3–2.8** |
| `ti_cb_text` | 11.6 ms | 10.6 |
| `ti_cb_unit` | 2.2 ms | 2.2 |
| `ti_cb_invert` | 5.3 ms | 4.0 |
| the blit of the finished card | 4.2 ms | 4.2 |

**A rectangle was two thirds of a system tick.** `ti_cb_set` wrote one pixel
per call and resolved the band row with a 16-bit multiply each time — ~600
cycles a pixel with its call frame — and a card's frame is ~320 pixels.
`ti_cb_span` and `ti_cb_vline` resolve the row once and then work in whole
bytes with masked ends.

## Where it stands

| | before | after |
|---|---|---|
| one card's composition, VGA | ~54 ms | **21.6 ms** |
| ...Hercules | ~53 | **19.7** |
| ...CGA | ~46 | **10.3** |
| ten card↔card hovers | 12.5 fps | **15.3** |
| idle | 18.6 | 18.6 |

## Two things to keep

**The obvious metric was the wrong one.** Frames-per-second over a hover is
quantised, adaptive (the wheel spends what it has) and blames whole routines.
The PIT bracket is thirty lines and answered in one run. PERFORMANCE.md's rule
4 says a counter is not a timer; this is the same rule one level down — a
*profile at routine granularity* is not a timer either.

**The defect measured ~54 ms and the PIT counter wraps at 54.9.** A regression
here is as likely to read as a small number as a large one, which is why
`tests/titheframe.py` asserts a WINDOW (3–28 ms) and not a ceiling.

## What is left, and what it would cost

Composition is 21.6 ms of a 54.9 ms frame, of which the text is 10.6. A hover
change is one or two compositions plus two blits plus the status. The next
lever is the one the owner named: **compose the resting bands once** and keep
them, so a hover blits rather than composes. Seven bands at the worst geometry
is 4,536 bytes, and the invalidation surface is three places (relayout, the
FRONT/REAR toggle, the face key). It is not taken here because the measured
stutter is gone and 4.5 KB plus a cache is real money; it becomes worth it when
a deck makes a card's content change more often than its layout does.
