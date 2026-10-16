# VIDEO-SEEN-PLAN - "error as seen" as a person sees it, and an encoder that spends by it

**Status: section 2's score BUILT as a report line (2a, 2026-10-16), in three sets - colour, grey and 1-bit dither - and judging `--aim quality`'s trials and page-ahead's keep beside today's figure; section 3 BUILT as two options off by default, awaiting the owner's eye on its one trade; the rest is PLAN.** Recorded from the owner's
review of the GasGas and Bad Carrot comparison encodes, and parked while
the encoder's choice in one scene is fixed first: the opening car shot of
GasGas (0:40), which the owner's own tune plays clean on the Victory 286
and every re-encode on this branch breaks. That is a CPU/budget question
before it is a metric question, and it is worked first.

The video encoder is `tools/os88venc.py`; its contract is SPEC.md 98.2.
"Error as seen" is the `picture:` line of an encode's summary
(`Encoder.measure`), and the same measure ranks what a cut frame draws
(`Encoder.value`, 98.2.1.2).

## 1. What the number is today, and why it reads low

Per frame, the shown picture and the target are low-passed the way an eye
averages dither (`sblur`/`tblur`), and the mean absolute colour difference
over EVERY pixel of the screen is taken (`dist`, 0..1 per channel,
averaged). The clip's figure is the mean of those means. So "0.30%" says
the average pixel is 0.3% of full scale off.

That is a fair RELATIVE gauge between two encodes of one clip and a
misleading ABSOLUTE one. The owner reads the GasGas file as 5-10% broken
"as seen" where it reports 0.26-0.30%, and the reason is in the opening
shot: the sky, the trees and the road - most of the screen - are right,
and every one of their pixels votes "fine", while the car, the thing the
eye is on, is visibly broken for seconds. A person does not average a
frame; they look at the car and judge the frame by it.

Scaling it up does not fix it: it is the POOLING that is wrong, not the
units, and a scaled mean would pass 100% on a clip that is merely busy.

## 2. Three observations, each measurable without a model

**2.1 Attention.** The eye goes to brightness, to contrast against the
surroundings, and to MOVEMENT - and in this shot to movement against the
camera's: the whole frame shakes, so "this pixel changed" calls the sky
salient too. Estimate the frame's global shift (one FFT phase
correlation between consecutive targets, cheap in numpy), and take motion
as the residual after it. The car moves against the shake; the sky moves
with it. Weight = f(luminance, local contrast, residual motion), from the
TARGET, so it is the same for every encode of the clip.

**2.2 Breaks that do not fade in.** A cut leaves a stale band of the old
picture - hard horizontal edges and a block outline that are not in the
source (the owner's screenshots: rows of the car's old position torn
across its new one). A wrong dither inside texture hides in the texture.
So compare the EDGES of the shown picture with the target's (the
structure term of SSIM): an edge the source does not have is a visible
break, and error inside existing texture counts for less (contrast
masking). Note 98.2.1.2 refused the error's own gradient as an ALLOCATION
weight - it starved mid-contrast regions for ever - which is a different
use from scoring.

**2.3 Pooling and persistence.** Judge a frame by its worst
attention-weighted patch (or a high percentile of patches), not by the
mean; and judge a stretch by how LONG the salient thing stays broken. A
car broken for 40 frames is the scene broken; the same error for one
frame is a blink. The existing `q_bad` (share of the frame off by
`VIS_BAD` or more) and `broken_spans` are the seed of this: they already
count seconds visibly broken, without attention.

The output reads "the share of where you are looking that is broken", in
0..100%. Its scale cannot be derived; it can be FITTED - the owner scores
a handful of clips by eye (GasGas ~5-10% is the first point, their tune
of it "fine" the second) and a few weights are regressed. That is a small
regression, not a trained model.

## 2a. The first calibration (2026-10-16): BUILT as a report line

`os88venc.seen_share` is 2's score, and every encode's summary carries it
beside today's figure: `the view as seen: X% of it broken on average, Y%
at its worst (t); Z s with a tenth or more of it broken`. It is fitted to
the owner's scores of the GasGas car shot (0:40.6-0:41.0, 24 fps, the old
tune: 286-fast, peak 4.0, owed time, page-ahead off), frames 15-23 - the
frames the 24 fps encode broke and the 20 fps one did not:

| frame | today's figure | the owner | seen_share |
|---:|---:|---:|---:|
| 15 | 1.14% | ~33% | 35.9% |
| 16 | 2.58% | ~62% ("a bunch of blocks") | 59.7% |
| 17 | 1.55% | ~45% | 48.6% |
| 18 | 0.46% | 30-33% | 24.7% |
| 19 | 0.47% | ~28% | 29.2% |
| 20 | 0.44% | ~25% | 26.1% |
| 21 | 1.51% | ~35% | 36.8% |
| 22 | 0.33% | 15-18% | 19.5% |
| 23 | 0.42% | ~ frame 22 | 19.9% |

The clean frames either side are 0 in both. What the owner's notes taught
it, each now a term: **colour counts** (frame 22's wrong-coloured
headlight centre and the red on a black tire are hue errors at near the
right brightness - a brightness-only first cut scored that frame 9%);
**hard lines count** (stale rows through the cars' tops); **soft blur
counts least** (the blurring on both cars "is not a major contributor");
and **a fault on an object breaks the object** (the spread term). Fitted:
soft brightness 0.75, colour 0.25, edges 1.0, a patch broken at 0.04, the
spread 0.75. Persistence (a patch broken in the frame before counting
more) was fitted too and came out 0 on these frames: frame 18, nearly
frame 17's picture, is the one miss (25 against 31.5).

**The second clip says the weights are the PICTURE's** (2026-10-16). Bad
Carrot 3:05-3:20 on the owner's tune (Mode X, 64 greys, flipped, peak 4.8,
lag 208 ms): eight cut frames, rated blind - the colour weights read them
2-5 times too high (A 26% against 5, B 81 against 30, G 58 against 12),
the order right. One set for both clips missed by 11 points on average,
taking the car frames down to half the owner's - and the owner had said why
first: "black and white, so the blur ends up counting for more here, and
edges matter more". So a GREY target (every pixel R = G = B) has its own
set, fitted on those eight (rms 7.8, "we're just going for general"):
brightness 1.0, colour 0, edges 2.0, a patch broken at 0.12 on a curve of
1.5, no spread. The clip reads 2.8% broken on average, worst 78.9%, and
exactly its 46 cut frames register at all.

| frame | the owner | seen_share (grey) |
|---|---:|---:|
| A | 5% | 3% |
| B | 30% | 35% |
| C | 50% | 62% |
| D | 90% | 75% |
| E | 10% | 9% |
| F | 5% | 1% |
| G | 12% | 13% |
| H | 15% | 6% |

**The third clip says a DITHERED picture is a third kind** (2026-10-16).
Take On Me, an old Hercules file (640 x 309 mono, 24 fps, 5150-st225 at
peak 0.9 - 518 of 971 frames cut, 418 of them by the disk), its own frames
decoded as the screen and today's encoder's 1-bit targets beside them
(today's encode of the same options differs from the old file by a few
dozen pixels a frame, and scores the same: 6.0% against 5.9% on average,
7.6 s broken in both). Ten frames rated blind; the GREY set it fell under
matched six and read the blur inside the dither as breakage (D 20 against
3, E 19 against 5), because a 5-pixel box does not see past an 8 x 8
dither. No weighting fixed it while an edge lost counted the same as an
edge gained; splitting the edge term did, the owner's own reading of
every frame being that the LINES a cut leaves count and the blur does not
("the face shape survives, just blurred"). So DITHER: brightness over a
13-pixel box, edges ADDED 1.0 and LOST 0, a patch broken at 0.12 on a
curve of 3, spread 0.75 - rms 3.4 over nine frames. A 1-bit target takes
it when a quarter of its pixels average to a mid grey: Take On Me is
42-93% so in every frame, Bad Carrot on the same Hercules options 4% at
the median (solid black and white, GREY as the owner predicted for Bad
Apple on a Hercules), its 51 frames of fade dithered and taking DITHER.

| frame | the owner | seen_share (dither) |
|---|---:|---:|
| A (a scene change, the old scene dominating) | 80% | 82% |
| B | 12-15% | 10% |
| C | 0% | 1% |
| D | 3% | 6% |
| E | 5% | 9% |
| F | 2% | 0% |
| G (a scene change) | 70% | 21% |
| H | 30% | 29% |
| I | 10% | 3% |
| J | 25% | 23% |

**G is a class of its own and is left out of the fit.** It is a cut at a
scene change that leaves the OLD scene showing whole, a light sketch over
a light wide shot, so patch for patch the brightness is near and the
score reads it low. The owner: "the individual frame is VERY broken but
the 'video' is not" - in play it "looks like a fade". A is the same kind
of frame and reads 82 because its old scene is high contrast against the
new. So for the encoder's purposes the low reading is the RIGHT one and
A's is the one too high, and the term this asks for (section 3) is the
other way round from a standalone rating: a cut frame that shows a whole
coherent picture - the old scene, or the new one not yet arrived - is a
FADE and costs less than one torn between two. That is also page-ahead's
idea (98.2.1.8: a scene change built on the hidden page and swapped in
whole) and 3a's hold, which shows the old frame whole for a period; the
score should not punish what those two buy.

**In the trial encodes** (2026-10-16): `--aim quality` takes a step only
while the view as seen stays within 1.25 x the asked one's plus a point
(`AIM_SEEN0`), beside the error as seen's own test; page-ahead's keep and
its prune weigh the view's mean and its seconds a tenth broken beside the
error as seen's three (`PAGE_PICTURE`). Take On Me 0:10-0:30 at `--preset
herc`: `herc-mid` not taken, the view 1.0% broken against 0.4% (and 16%
of frames cut against 2%); GasGas 0:38-0:48 in Mode X, page-ahead KEPT
with the view 0.4% against the plain encode's 0.7%. `page_hurt` - which
build hurt its own stretch - still sums today's per-frame figure.

**Next**: section 3. A colour clip of flat cartoon colour is a fourth check.

## 3. Using it in the encoder

`Encoder.value` already decides, per pixel, what writing it now is worth
(this frame and the look-ahead), discounted to what an eye sees. Two
changes follow from section 2 and both are local:

- **Weight `value` by 2.1's attention map.** In a cut frame the car's
  spans then outrank the shaking sky's. Cheap: the map is per target and
  computed once.
- **Penalise leaving a hard edge.** When a frame is cut, a span that
  completes an object (closes a stale band's edge) is worth more than its
  pixel count says. A first form: score the stale edge each candidate
  span REMOVES, from 2.2's edge comparison.

**BUILT as two options, both off by default** (2026-10-16): `--attend S`
weights `value` by `seen_attention`'s map (its mean 1, so a frame's whole
worth is what it was and only where it is spent moves), and `--edges S`
adds the edge term priced as `plain` is - how much nearer the target's
edges the screen is for writing the pixel, less the target's own - with
the picture kind's weights (`seen_weights`: on dither only the edges a cut
ADDS). Five arms on the three clips, each on its own options (GasGas
0:40-0:50 the old tune at 24 fps, page-ahead off; Bad Carrot 3:05-3:20
the owner's 64 greys; Take On Me 0:15-0:30 the old Hercules options):

| clip | arm | the view broken | s a tenth broken | worst | error as seen |
|---|---|---:|---:|---:|---:|
| GasGas | today | 6.84% | 1.54 | 95.8 | 0.396% |
| | `--attend 1` | 6.97% | 1.54 | 95.7 | 0.392% |
| | `--edges 1` | 6.80% | 1.54 | 95.8 | 0.398% |
| | `--edges 2` | 6.81% | 1.54 | 95.8 | 0.399% |
| | both 1 | 6.93% | 1.54 | 95.6 | 0.392% |
| Bad Carrot | today | 2.76% | 0.75 | 81.8 | 0.397% |
| | `--attend 1` | 2.70% | 1.04 | 76.6 | 0.389% |
| | `--edges 1` | **2.49%** | 1.00 | **70.2** | **0.356%** |
| | `--edges 2` | 2.81% | 0.92 | 75.2 | 0.398% |
| | both 1 | 2.68% | 1.00 | 72.1 | 0.389% |
| Take On Me | today | 5.45% | 1.87 | 90.9 | 2.158% |
| | `--attend 1` | **5.18%** | **1.75** | 89.5 | 2.200% |
| | `--edges 1` | 5.37% | 1.87 | 91.2 | 2.168% |
| | `--edges 2` | 5.44% | 1.92 | 91.3 | 2.198% |
| | both 1 | 5.15% | 1.79 | 90.0 | 2.208% |

**The car is not an allocation question.** GasGas's car frames (14-23)
read the same in every arm (37 62 52 26 35 28 37 20 23 today, 36 63 51 25
36 26 37 19 22 with edges): the same frames are cut by the same ceiling,
and no order of spans makes the ~20 KB a 24 fps frame has draw what needs
27-30 KB. That is 3a's lever, a hold, and not this section's.

**Where it does move, it is a TRADE.** Bad Carrot's cut burst with
`--edges 1`: frames 44-53 read 35 69 70 50 47 46 47 30 25 56 against
today's 62 54 82 71 52 56 75 58 68 59 - frames 50 and 52 are the carrot
drawn whole where today's are torn bands - and frames 54-57 and 66-68
read 31 32 22 20 / 20 13 20 against 22 14 8 4 / 10 6 6: the worst repaired
sooner, a milder residue left longer. The owner's eye decides that trade,
and until it has, both stay off. `--attend` moved nothing a strip of
frames shows.

What NOT to do first: change allocation and the metric in the same step.
The metric is the instrument the allocation is judged by; build the score
(report only), check it against the owner's eye on the clips we have, and
only then let it steer `value`.

## 3a. A frame-rate step on the degrade ladder (the owner, 2026-10-15)

**The finding that prompted it.** The owner's GasGas tune that plays the
opening car shot whole is a **20 fps** file; the copy compared against it
for a day was the same options at **24 fps**, and at 24 the car frames
(0:40.7-0:41.0) were cut by the per-frame ceiling into stale bands - the
calibrated model and the owner's tune agree once the frame rates match.
At 20 fps each of those frames is a 27-30 KB record drawn whole; at 24 the
same moment is ~20 KB records with the car torn. So: **20 fps unbroken
looks better than 24 fps broken, and 24 fps unbroken looks better than
either.**

**The step.** Today the encoder's answer to a frame that will not fit is a
CUT, after (16 colours only) a palette step-down (98.2.15's `step_down`).
A frame-rate drop is the third kind of degrade and sits BEFORE the cuts:
HOLD a frame - write nothing, the picture stays as it is, the sound plays
on - and give its period of CPU and its bytes to the next frame, which is
drawn whole and ON TIME. 24 -> 20 is one hold in six; 24 -> 12 every other
frame. It is owed time's and the lag's idea once more (98.2.1.1,
98.2.1.1.2), with the difference that matters for sync: owed time and the
lag draw EVERY frame and draw them late; a hold draws FEWER frames and
draws each one at its own time. A high-change scene goes choppier for its
length rather than broken.

**No format change looks needed**: a record that writes nothing is a frame
today (a still scene's sound-only records are 0.5 KB), and the player shows
each record at its period whatever it holds. The encoder needs the
decision AHEAD - the look-ahead already prices the next frames, so a hold
is chosen when the frame after it fits whole in two periods and does not
in one.

**The ladder, made the user's.** Every step is ordered and bounded, e.g.:

    hold to 20 fps
    a pixel cut up to 0.x% (as seen)
    hold to 16 fps
    a coarse cut up to 0.x%
    ...

with today's palette step-down as one more rung and today's behaviour
(no holds) as the default ladder until the A/B says otherwise. The rungs'
bounds are in "as seen" terms, which is the other reason section 1 matters:
a ladder bounded by today's whole-screen mean would let the car break
"up to 0.3%".

**Also owed**: the palette step-down is 16 colours' only; the ladder is the
natural place to give the other formats theirs.

## 4. The order

1. (FIRST, not this plan) Fix why the opening GasGas shot breaks at all
   on this encoder when the owner's tune of the same frames does not -
   it is the encoder's budget/choice, not the metric. Two-second clip
   (0:40-0:42), against the owner's original file and its profile.
2. Error maps for that shot: where the wrong pixels are, and which spans
   each cut frame chose - does the budget go on the shake or the car.
3. The attention-weighted score as a REPORT line beside today's, fitted
   to the owner's scores.
4. Then the score into `value` (section 3), A/B'd on the same clips.
