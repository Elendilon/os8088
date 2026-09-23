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
