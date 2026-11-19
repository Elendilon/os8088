# COURSE 2, "Little Hop" (HOP; was "Island Hop"): design sheet

*Status: **IN ENGINE, revision 7** (2026-11-19): `apps/bonanza/courses/hop.bbc`,
written by `hop/sketch.py --bbc --force`, compiles with every check, and the
BZROLL=1 playtest build carries it on pad 1. The owner's verdict on the gaps
is the next step; revision 2 below supersedes attempt 1's layout, which
sections 1 - 4 still describe.*

## Revision 7 (2026-11-19): quarter heights - the start flipped east, 3/4 lips

Quarter-unit heights landed (SPEC.md 130.48): a **3/4-unit step** is the rung
the course lacked, no ball rolling up it and every ball's Hop climbing it.
The owner: *"If we start the course by flipping the current start area to
the east, and replace the void gaps with 3/4th lips, that would take the
'Jump Twice' off the initial screen? And show the lips (which display better
in that perspective)."*

- **Leg 1 runs -x from an east start**: A, then two 3/4 steps up (T1, T2),
  each riser climbed up the screen and so facing the player; the void gaps
  and their floating lips are gone from it. "JUMP!" stays on T1's north rail.
- **The easy hop L -> U1 is a 3/4 step too** (no gap): the owner's
  revision-4 ask, *"can't be climbed by rolling, but slightly lower than U1"*,
  answered exactly; then U1's six-tile run-up and the one-unit step.
- **"JUMP TWICE!" is off the spawn's screen**, *measured* with the tool's
  camera model: the CGA window at the spawn covers picture x 704 - 1023, the
  sign 613 - 667; the Hercules' two extra words on the left reach about 672.
- The first ramp is two tiles again, steep (2 units a tile), and the rest of
  the course is a quarter unit higher from U1 on; the reach spans the 60
  tiles 1024 px allows (`origin 544`). The bounce's and Hop E's gaps keep
  their lips.

## Revision 6 (2026-11-19): signs where the move is, a longer first ramp, "Little Hop"

The owner: *"Plays pretty well."*
- **"JUMP!" on T1's north rail** (*"you have to jump there too"*) and
  **"JUMP TWICE!" on U1's**, before the step: *"a 'here is what you need to
  do' instruction instead of a 'do this to get here' instruction"*.
- **The finish clock's block stands on a full column** to the ground, so it
  no longer breaks the back wall (block clocks no longer float).
- **The first ramp is six tiles** (it was four), the start one unit higher.
  Not double: the picture is 1024 px, and the reach now spans exactly the 60
  tiles it allows (`origin 560`; U2 three tiles to pay for it). The aim, to
  take "JUMP TWICE!" out of the spawn's view, is NOT met. *Measured* with the
  tool's camera model: at the spawn the CGA window covers picture x 592 - 912
  and the sign's board starts at 613. It leaves the view once the ball rolls
  right for the first Hops.
- **Flag 1 on the spring's landing** (the owner, while testing: *"move the
  checkpoint after the spring so its on the target landing area"*), H's
  waypoint cell, where the throw comes down.
- **The name: "Little Hop"**, the owner's suggestion; the island theme is
  saved for a much later course.

## Revision 5 (2026-11-19): the long platform is U1

The owner: *"For the longer platform, I meant U1 jump, not U2; aka, give them
room to get a rolling start for their jump."* U1 (the easy hop's ledge) is
six tiles long, the step's run-up; U2 is four again, and "JUMP TWICE!" stands
on its back rail. Another session is looking at an easy-jump height in the
tuning; this course goes on as if nothing changes there.

## Revision 4 (2026-11-19): the easy hop, a long U2, signs, the basin's line, K farther

The owner on revision 3: the lips *"an excellent finding ... likely one we
continue using for now"*; difficulty *"Much better"*.

- **The easy hop.** *"Do we have a level that cannot be climbed by rolling
  (aka requires a jump), but is slightly lower than U1?"* No step does:
  heights are half units, and half a unit rolls up for every ball
  (130.16.5.3). A **1-tile gap onto a ledge half a unit UP** does, measured
  with the tool's ladder (rubber at the cap): no roll, a Hop **311 ms**, a Hop
  and its "and again" 677 ms (a level 1-tile gap: 549 and 769; a 1-unit step:
  128 and 531). So L, the gap, U1 half a unit up, then U1's one-unit step to
  U2: *"an 'easy hop', followed by the 'hard single jump, or easy double
  jump'"*. A gap climbed up the screen shows its FAR island's face, so U1's
  lip is the one that floats.
- **U2 is seven tiles long** (it was four), the ramp off its far end. *(Revision 5: the owner meant U1.)*
- **Signs**: "JUMP!" on U1's back rail past the easy hop and "JUMP TWICE!" on
  U2's past the step, boards on posts (`hop/signs.py`, FIRST ROLL's decal
  machinery and the tree's 8 x 8 face). From leg 1, "JUMP!" stands in view
  just below the first two Hops as well.
- **The basin**: wider (seven tiles), the flag on the ramp's centre line AND
  on the spring's row, three tiles before it, so a respawn rolls straight on.
- **K three tiles from F** (it was two). NO TRAP still proves it. *Measured*
  with the model: from rest on each of H's 16 cells holding each of the 8
  directions, 20 of 128 runs land on K, against 13 of 128 at two tiles (that
  comparison moved K's floor and not its rails, so it is a rough one). The
  owner's playtest says whether it is still EASY.
- **Fitting 1024 px**: the leg-1 islands, L and U1 three wide, the ramp off
  U2 two tiles, H four wide, F and K three deep (`origin 576`).

## Revision 3 (2026-11-19): grounded, easy, clear

The owner on revision 2: palette 0 good, but on BLACK (*"I want to introduce
non-black backgrounds later in the game, as 'special' courses"*); the fall
and bounce and the spring work; *"The level's double jumps are MUCH too hard.
This level should be telling them that 'jump, and double jump: these
mechanics exist', not testing their perfect use of them"*; *"Some of the path
is not clear, or appears to connect where it actually doesn't"* (islands a
tile apart round the start); and *"'floating' implies 'difficult jumps' ...
we should save that style (as a complete map style) for when we get to
difficult aerial jumps."*

- **Grounded**: every island a column to the ground.
- **Easy**: every Hop is a 1-tile gap (its 549 ms window), every "and again"
  a 1-unit step railed on both sides, so a miss bounces back; the only
  2-tile gap is the bounce's. Six legs: two Hops (+x), a ramp down, two
  steps (-x), the basin and its spring throwing -x onto H, the lip, drop and
  bounce (+y), then a Hop and a step once more, and the goal.
- **Clear**: parts that do not connect stand at least three void tiles apart.
- **The lips** (*observed* in the picture): between grounded columns a 1-tile
  gap shows the near island's side face, exactly as a step's riser does, so
  the two looked alike. The row before each gap floats one unit thick, so a
  black notch under the lip marks every gap and a step shows none. This is
  the only floating left, and it is a reading aid rather than the style.

## Revision 2: what changed, and why

The owner on attempt 1: *"visibility of when something is a gap, or ledge,
will be critical ... we'll need to check visually that each gap, up or down,
reads appropriately"*; *"missing ... the 'drop from high up on a ledge, then
bounce to get across a gap' that trial bounce first demoed"*; *"Island Hop
sounds like a good name, and theme"*; *"Lets go for a different palette.
New song, new clocks, but lets get it in engine and closer to done before we
set agents on those."*

- **The reading rule.** The camera sees only an island's +x and +y faces. A
  step UP climbed moving +x or +y shows no riser (attempt 1's L-to-U step
  read as one flat slab in the engine's picture), so every climb is taken
  moving **-x or -y** (up the screen), its riser facing the player, and every
  drop moving +x or +y, the edge left behind showing its face. The legs
  alternate left and right, which also keeps the course inside the 1024 px
  picture (`width 128`, `origin 688`, the reach's 60 tiles exactly).
- **The lesson climbs -x**: T2 and L give a seven-tile run-up, U is one unit
  up, then the 2-tile gap to V. The test climbs -y: K, the step S, the gap E.
- **TRIAL's drop and bounce is in**: off H's lip down a short ramp, six units
  onto F, and rubber's rebound over a 2-tile gap onto K, two units above F.
- **Thin islands, `thick 1`.** Three-unit faces hung over most of a 2-tile
  gap; at one unit the void shows between the islands. `HOP_THICK=3` renders
  the old look for comparison.
- **The palette: `palette 0 ground 1`**, green, red and yellow islands on a
  blue sea, as the proposal (colour 0 is every black pixel too: the clocks'
  digits and the goal's dark squares turn blue).
- **`trap hop`** (SPEC.md 130.14.4.1.1): NO TRAP never pressed Space, so a
  course built on the Hop failed it at its first gap; the statement proves it
  with a Hop and its "and again" pressed too. The compile takes about 25 s.
- **Fitting the checks**: W became flat (its ramp's sloped face stacked six
  occluder records in a block), B is two units down from W, and the clocks
  moved apart (G10): the start on T1's far rail, the middle on V's left rail,
  the finish on the goal plateau's far rail.

Still to do: the owner's look at each gap and ledge on the glass, G3 (no pan
during a jump) checked by a drive once played, the song and the clocks by
agents once the course settles, and `limit 70` (hand-set: the autopilot
cannot Hop).

## Attempt 1 (superseded layout)

*Pen-in, on paper. Distances are tiles, heights are units (8 px). Every
window and time below is MEASURED from the tool's step and gap ladders
(rubber at the cap with a chord) or PREDICTED from the route's length.*

Tutorial 2, the pathway's second node, no branch. First Roll taught rolling,
braking and edges. This course teaches the **Hop** (Space) and rubber's
**"and again"** (a second press before the Hop lands, for a bigger bounce),
and a **spring**. It is built of FLOATING islands, the owner's choice for a
course after the first: *"1: Floating: For another course we'll use that,
but not this one."* The islands' faces hang 3 units into the void, so every
gap is a gap you can see.

| field | value |
|---|---|
| place | tutorial 2: the second node of the pathway, no branch |
| families | `spring` |
| start ball | rubber, the whole way |
| finishes | one; no secret |
| target time | about 35 s. The sketch's route is 72 tiles; the Hops and the step's retries make it slower per tile than First Roll (88 tiles, the autopilot's 31 s) |
| camera | not locked: the course swings 416 px across, for visual interest. **Every jump is planned not to pan (G3)**, checked in the engine by `--guide` |
| the new demand (CD2) | **timing a press in the air**: the Hop, then the Hop and its "and again" |
| help it gives | a lesson that cannot kill (the step) before the one that can (the gap); rails on every landing's far edge to catch an over-Hop; the test repeated unrailed |
| clocks | three, first guesses; the owner places them (FIRST ROLL's way) |
| palette, song | the owner's. (*Bounce Trial* is kept for course 3) |

![the plan, from above](hop/plan.png)

![the course in the game's projection](hop/iso.png)

*Above: `hop/sketch.py`'s two pictures, plain blocks in the game's
projection. Pink pennants are flags, the orange coil is the spring, the
cyan boxes are a CGA window at the start, the middle and the goal.*

## 1. The course, section by section

| | section | what happens | the numbers (the ladders) |
|---|---|---|---|
| A | **the start island** | a railed back, the tee's place | |
| T1 | **the first Hop** | a 1-tile gap, level. Rolling across falls in; a Hop crosses | a Hop crosses from 30 take-off points, a 549 ms window: wide |
| T2 | **the second Hop** | a 1-tile gap, half a unit down. Easier, as a second go | easier than T1 |
| L | **a ramp down** | down to a landing | |
| U | **the step: "and again", safely** | U is ONE UNIT up from L. A Hop alone barely climbs it; the Hop and its "and again" climbs it easily. A miss only bounces back onto L, so it cannot kill: this is the lesson | a Hop: 7 points, 128 ms (hard). The Hop and "and again": 29 points, 531 ms (easy) |
| V | **flag 0, then the 2-tile gap** | flag 0 on U. A 2-tile gap, level, onto V, railed along its sides: the same two presses now cross a gap | a Hop: 4 points, 73 ms (luck). The Hop and "and again": 19 points, 348 ms |
| W, B | **the run and the spring** | a ramp down and a run to the basin B. B's SPRING, at its back, throws the ball BACK up the screen, away from the camera (CD1: the spring and the landing are both in view), over a void row onto H, 6 units up. H's back edges are railed to catch an over-throw. Flag 1 in the basin | the spring's 768 is PEAK's spring 1, which reaches 6 units 2 tiles on |
| R, D | **the long ramp down** | from the high island down to D, for speed and a view; flag 2 on D | |
| S, E | **the test** | the step again (one unit up onto S), then the 2-tile gap again onto E, with no rails beside them. The same two moves, with the help taken away (CD2) | the same windows as U and V |
| G | **the goal** | a ramp down to a wide goal plateau, in view | |

## 2. The camera (G2, G3)

Not locked. The islands spread 416 px across, which keeps the course
visually interesting (the owner, on G2). The rule that binds is G3: no pan
during a jump the player steers. The jumps:
- T1 (+y), T2 (+x) and the two 2-tile gaps (+y) each travel 1 - 3 tiles,
  16 - 48 px across;
- the spring's throw travels about 2.5 tiles up the screen and to the
  right, about 40 px.

They are placed in the middle of their windows. `--guide`'s run half
measures it once the course is in the engine, on a run of the autopilot
(which can Hop since the shapes work) or of an author script.

## 3. Flags (G20) and clocks

- Flags stand just before what can kill:
  - **flag 0** before the taught gap (V);
  - **flag 1** in the basin before the spring (a short throw falls into
    the void row);
  - **flag 2** before the test.

  The first two Hops respawn at the start, a few seconds back.
- Clocks: first guesses, the owner to place them:
  - the start's, one block out and level with the start island;
  - the middle one, floating by the high island;
  - the finish's, on the goal plateau's rail.

## 4. Questions for the owner

1. **The lesson order**: the step (safe) and then the gap (lethal) for
   "and again". Is that the right way round, or the gap first?
2. **The spring**: a basin throwing you back up the screen onto a high
   island. Is one spring enough for the tutorial, or a second one
   (higher, or onto a smaller target) as a test?
3. **The name**: "Island Hop", NAME `HOP`?
4. **Palette and song**: the default palette again, or a second look for
   course 2? And a new song, or one we have?
5. **Length**: about 35 s PREDICTED. The tests could each get one more
   island if it plays short.
