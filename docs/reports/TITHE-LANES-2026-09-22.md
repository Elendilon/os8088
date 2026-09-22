# TITHE — three lanes and three clocks, measured

*Taken 2026-09-22 on branch `tithe-plan`, MartyPC `os8088_xt_vga`, guest
seconds throughout. `tests/titheframe.py` is the row every number here comes
off; `docs/reports/TITHE-RATE-2026-09-22.md` is the measurement this one
follows and **partly overturns** — see the last section.*

## What was asked

Three things, off a VGA field test that otherwise signed the look off:

1. *"Pressing `A` is speeding back up all of the idle animations — the bolt
   speed feels good so that should stay the same, but it may mean we need a
   different clock for the bolt vs the idles."*
2. *"Mouse over a card sometimes has an outline, and sometimes is a solid
   block. The outline looks much better, although we need to vertically shrink
   or move things by 1px on both top and bottom to fit it."*
3. *"We'll only have 3 bases, so we can afford to give them more animation
   frames — and play them at a higher rate."*

They came in as three unrelated bugs and they are one design change:
**a feature with a tempo of its own needs a budget of its own** (SPEC.md
§97.5.1). The wheel's credit is the idle's and nothing else draws on it; the
bolt and the bases each accrue a share every frame and spend it when a commit
fits.

## 1 — the bolt was not fast, the board was

The combat allowance was **added to the wheel's share** while something was in
flight. More credit meant the wheel reached more features, so twenty figures
that were no part of the attack idled half as fast again. The bolt's own step
never moved: it was one commit a frame before and it is one commit a frame now.

| | idle, commits/s | frame, passes/s |
|---|---|---|
| no bolt | 89.0 | 18.7 |
| bolt in flight, one credit (before) | 135.7 | 18.5 |
| bolt in flight, separate lanes (after) | 88.5 | 18.7 |

**−0.6%**, where the row used to assert `>= base` and pass at **+55%**. A
one-sided check could not have said this; the assertion is a band now.

## 2 — the frame that would not hold, and why the trim could not save it

`tests/titheframe.py` carried a ratchet at 12 passes a second for the one
combination that did not hold: the dirty rect **and** a projectile together ran
at **13.3** against the wheel's 18.2, and trimming the credit to 79% did not
recover it — which said the cost was not in the commits the credit gates.

It was not. It was the same defect: the busiest frame on the machine was also
the one the wheel was told it could spend most in. Separate lanes take it to
**18.7**, and the floor is the 15 the row carried as the fix's own gate.

## 3 — the base lane

Twenty characters against three bases, so a frame of base art is drawn once for
the whole game where a frame of character art is drawn twenty times. The bases
came off the wheel — where they were 2 of 23 features moving at everyone else's
3.5 fps, and any better rate would have come out of the figures' — and into a
lane that commits **one of the two a frame, alternating**.

| | measured |
|---|---|
| base lane commits | **18.7/s**, one a frame of 18.5 |
| ...per base | 9.35 Hz, against the wheel's 3.5 |
| poses | 8, against the characters' 4 |
| cycle | 0.86 s, against a figure's 1.14 |
| idle's share cut 20% → 5% | idle **107.0 → 35.4**/s, base **18.7 → 18.8**/s |

That last row is the whole point of a lane: the thing the field tunes cannot
reach the thing it does not want tuned.

## Two defects the work found in itself

**Eight poses were two pictures.** The placeholder's keep moved only between
*centred* and *one pixel right*, so every pose past the first was identical —
four times the build cost for no more animation. A triangle over the pose count
gives `-2,-1,0,1,2,1,0,-1` at eight and the original `0,1` at two. The row
reads the band store back and counts distinct poses (**5 of 8**, which is the
ping-pong's five positions), because this is the failure that is *silent*: the
lane still commits, the rate still measures, and the picture does not move.

**A two-second freeze on every layout.** Composing the mound per pose was eight
times the work for one picture, with the gfx lock held — a window resize
stopped the machine dead. Slot 0 gets the mound, one `rep movsw` whose source
trails its destination by one slot fills the rest, each pose's keep goes on
top: under a second for the whole art build.

## The measurement that was wrong, and how

Three assertions in `tests/titheframe.py` were passing on a **baseline taken
during the art build**. The settle after launch was two guest seconds and the
build is longer than that, so the opening window read 46.6 commits/s at 9.6
passes a second — a third of the machine — and every comparison against it was
against a number the renderer never runs at. It made a bolt look like a 92%
speed-up when it was −0.2%, and it read the three sprite arms as three
*decaying* frame rates, hiding that each of them holds 19 fps. Two and a half
guest seconds after every key that relayouts, five after launch.

`docs/reports/TITHE-RATE-2026-09-22.md`'s *"The combat frame"* is the paragraph
this overturns: its *"a projectile in flight leaves the idle at 5.4 fps a
feature against 3.5, and the frame holds 18.5"* was read correctly and
concluded from wrongly — the rise was the defect, not the headroom. SPEC.md
§97.5 carries the correction.

## What is still the owner's

Wave 1a's gate is unchanged: sign off the look, and **pick a base** —
TITHE-PLAN §16.1 wants candidates and the art here is still the placeholder
mound and keep. The fullscreen renderer (§97.6) is the one wave-1a deliverable
not built.
