# BONANZA: how high can the ball go? (2026-11-16)

*A dated measurement of one tree (`37b614c`, branch `bounce-bonanza`),
taken before wave 9 to answer the owner's question: "12 px is not really
a high bounce, why is that the limit? When we fall off a ledge then boost
we go higher, right?" Host only, `tools/bbcourse.py`'s own compile, scratch
scripts (not kept). Every figure is MEASURED on the host unless marked.*

## The answer

**There is no 12 px limit on the ball.** The figure came from SPEC.md
137.16.3.2: raising every Hop to 366 (an apex of 12 px) made `MOON` refuse
to compile, with 5 occluder records in one block against the bound of 4.
That refusal is an **alignment artifact of the tool, not a property of the
height.** Raising the Hop moved the picture's top margin `Y0` by 3 px, and
the records are grouped by 8-line block, so every block boundary moved and
one block happened to collect a fifth record. Nothing about a higher
flight added a record.

And yes, falls go higher already. A ball's downward speed is capped at
`VZMAX` 768 (a fall of about six units). Rubber rebounds from that at
about 615, an apex of about 31 px, and since round 3b (SPEC.md 137.17.17)
the boost ADDS to a bounce off a firm level floor, up to `VZMAX` itself: an
apex of about **47 px**. The reach model already contains those flights,
and every shipped course compiles with them.

## The measurements

**1. The records are the same set at every Hop; only the alignment moves.**
`MOON`, with `Y0` forced through all eight alignments (`+0` is the tool's
own choice), records and the most in one block:

| `Y0` offset | Hop 252 (shipped) | Hop 366 (12 px) | Hop 420 |
|---|---|---|---|
| +0 | **2,624, max 4** | 2,788, max 5 (3 blocks over) | 3,032, max 5 |
| +1 | 2,699, 4 | **2,529, 4** | 2,624, 4 |
| +2 | 2,709, 5 | 2,725, 5 | 2,699, 4 |
| +3 | 2,788, 5 | 2,737, 5 | 2,709, 5 |
| +4 | **2,529, 4** | 3,032, 5 | 2,788, 5 |
| +5 | 2,725, 5 | 2,624, 4 | 2,529, 4 |
| +6 | 2,737, 5 | 2,699, 4 | 2,725, 5 |
| +7 | 3,032, 5 | 2,709, 5 | 2,737, 5 |

Each column is the same eight figures rotated by how far the Hop moved
`Y0`. At 12 px, three of the eight alignments compile, and the best of
them is **2,529 records, 95 fewer than the course ships with today**.
SPEC.md 137.11.4.4 already noted the records "swing with `Y0`'s alignment
to the blocks ... by up to 7%" and that "the tool does not search the
alignment". `MOON` swings by 20% (2,529 to 3,032).

`SUMMIT` at Hop 300 behaves the same way: 5 of 8 alignments compile, the
shipped alignment (+3) among them at 3,081.

**2. A higher BOOST adds nothing on any shipped course.** With the boost
launch raised from its shipped 10 px apex to 12, 16, 20, 24 and 32 px
(the bound lifted so the counts could be read), the record count and the
most in one block did not change on any of `BENCH`, `FIRST`, `TRIAL`,
`MILL`, `MOON`, `SUMMIT` or `PLAYGROUND`.

**Why height costs so little.** An occluder record is something drawn IN
FRONT of the ball: the plateau a ball falls behind, a ramp's face over the
void. A higher ball is drawn higher on the screen, away from what is in
front of it. The records come from LOW positions (behind edges, in pits)
and from how far a flight carries over voids, not from the apex. The Hop
moved the alignment because it is added to every floor's rate, ramps
included, which extends the top of the picture's reach. The boost does
not move `Y0` because it launches from level floors only.

## What really limits a jump

| limit | what it is | where it bites |
|---|---|---|
| `VZMAX` 768 | the physics cap on vertical speed | an apex of about 47 px (about 11 units), already reachable by a fall plus a boost |
| the occluder bound, 4 records a block | the frame's worst case: a footprint's 3 x 3 blocks test at most 36 records and lay at most 9 (SPEC.md 137.11.4.2) | per BLOCK, per course geometry; with the alignment searched, height is rarely what tips it |
| the camera | the CGA window is 200 lines; a ball 47 px up stays inside it | not binding |
| design | CD5 and CD6's ladders (SPEC.md 137.17.5): which ball crosses which gap | a course decision, priced by the tool |

Raising the block bound itself is not needed. If it ever is, a fifth
record a block costs up to 9 more tests (about 0.5k clk) and at worst 9
more lays (about 12.6k clk) on the frame that meets them (SPEC.md 137.10's
55 clk a test and 1.4k a lay; PREDICTED).

## Recommendation

1. **The tool searches `Y0`'s eight alignments** and keeps the one with
   the fewest records that meets both bounds. Host only, no guest change.
   It removes the false ceiling and shrinks courses as a side effect
   (`MOON` -3.6% of its records at the shipped Hop). It costs compile time
   (the occluder cut and merge run up to eight times; the reach is computed
   once) and some top-margin lines in the picture (at most 7). Every course
   identity can change, which re-stamps demos; the old courses are to be
   dropped, so that churn is short-lived. This belongs at the START of wave
   9: the jump pickup and every new family's reach depend on it.
2. **The jump pickup stacks with the boost, capped only by `VZMAX`** and
   by the tool's ordinary proofs (the reach, the bounds, every finish
   reachable without a pickup). On the shipped courses that is about 47 px.
3. **Rubber's Hop is free to retune.** Wave 6 chose 252 over Q-61's 256
   only to dodge this artifact (SPEC.md 137.16.3.2). On today's courses
   the refusals it dodged are already gone: Hop 256 compiles `MOON` (2,624
   records, the shipped alignment unchanged) and `PEAK` (`summit.bbc`,
   3,081), and so does 244, one of the values that refused `PEAK` at wave
   6, all at the tool's own alignment. With the search in place, a feel
   retune is a feel decision again. `PEAK`'s best alignment is 3,001
   records, 80 fewer than it ships with.

**Not measured here:** the guest. Every figure is the tool's compile; the
frame cost of the alignment chosen is unchanged in kind (the same bounds),
and the final pass after the search lands measures it on the rows.
