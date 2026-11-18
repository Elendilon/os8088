# FIRST ROLL: design sheet, attempt 1

*Status: **PEN-IN**. On paper only, for the back and forth with the owner
before anything goes into the engine (the guide's pipeline, section 3).
Nothing here is built. Distances are tiles, heights are units (8 px), and
times are PREDICTED from the route's length; the tool measures them once the
course is in the engine.*

The test course of the same title (`apps/bonanza/courses/first.bbc`, FIRST)
stays a test course. This is the shipped course 1. Its NAME in the tool is
proposed as `ROLL`, leaving FIRST free for the test course.

| field | value |
|---|---|
| place | tutorial 1: the first node of the pathway, no branch |
| world | the tutorial (none) |
| families | **none**: tiles, holes and guard rails only (the rails are tool art, 0 resident bytes) |
| start ball | rubber, the whole way (G13) |
| finishes | one, the goal plateau; no secret |
| target time | **about 35 s** (G1). The sketch's route is 87.5 tiles; at the 2.5 - 3 tiles a second a careful first play averages, that is about 30 - 35 s (PREDICTED) |
| pace | about 950 picture lines, about 120 block rows, so about 0.29 s a block row: one part, well inside the limits |
| palette | the owner's choice: a bright daytime palette, to read as the first course |
| clocks | three, all standard-part pillars (section 3 below; G23) |
| song | the owner's choice |
| the new demand (CD2) | **reading an edge**: drops kill you, and the player learns the timing at a lip, when to let the ball run and when to slow it |
| what it teaches | roll and steer; brake; ramps; **drops kill you, and you need to learn the timing** (the lesson the test FIRST ROLL got right); a Hop is always allowed and never required |
| help it gives (CD2) | guard rails on nearly every edge; ramps that funnel to the centre; corners that lose their rails one at a time; respawns close behind every hazard |

![the plan, from above](first/plan.png)

*Above: the plan. +wx is right and +wy is down; the arrows mark ramps and
their downhill direction. Yellow is a guard rail, and an edge without one
drops into the void. Red is the route, cyan the clocks, pink the flags.*

![the course in the game's projection](first/iso.png)

*Above: the same course in the game's projection, drawn as plain blocks with
none of the real art. The cyan boxes are one CGA window (320 x 200) at the
start, at K1's clock and at the goal. The two vertical lines are the CGA
camera's dead zone (160 px). `first/sketch.py` draws both pictures.*

## 1. The course, section by section

Times are cumulative and PREDICTED.

| | section | what happens | what it teaches | 0 - s |
|---|---|---|---|---|
| A | **the start and the hill** | A railed plateau, then three ramps, alternately along +y and +x (the shape of SUMMIT's opening hill), each throwing onto a flat landing that a rail closes, so the throw turns the ball onto the next ramp | rolling, steering, what a ramp does to speed; nothing here can hurt | 0 - 9 |
| B | **the ledge** | Two tiles wide, a wall behind and its FRONT EDGE OPEN. Holding Down drifts the ball off the front; the edge's chord (Down+Right) runs it straight | **drops kill you**: the first fall respawns at the start, 9 s back, which is cheap | 9 - 12 |
| C | **the lip** | A short run-up and a ramp end in a lip 3 units above a wide landing, T. A HOLE sits where the straight full-speed landing falls. Slowing down (then steering round it), a Hop (over it), or either side of the ramp (past it) all succeed. Holding straight on fails | **timing at a lip**: the test FIRST ROLL's good jump, re-planned so its flight crosses about 32 px on screen, inside the dead zone (G3) | 12 - 15 |
| T | **flag 0** | On T's far side, after the lip (G20) | | 15 |
| D | **three corners** | Gentle ramps down, alternately +x and +y, 3 tiles wide and railed along their sides. Corner K1's outer edge is railed; K2's is HALF railed, the gap where a fast ball goes; K3's is open | **braking**: Shift before a corner. Each corner takes away one more piece of help | 15 - 24 |
| E | **the steps** | Three one-unit steps down onto floor, railed | dropping onto a floor is fine; only the void kills | 24 - 26 |
| W | **the walk** | Two tiles wide, both edges open, an easy bend: a straight ramp, a railed elbow, a ramp the other way | steering with the drop on either side; going steady rather than slow | 26 - 31 |
| F | **the leap** | A railed run-up along +x into a ramp, a ONE-tile gap in the void, and a landing 2 units under the lip | the mirror of C: here **too slow** drops into the gap, so the player must keep the speed the run-up gives (G4: the run-up is in plain view, and the arrow held down is the whole answer) | 31 - 33 |
| G | **flag 1** | On the landing past the leap | | 33 |
| H | **the finish** | A short ramp down onto a wide, railed goal plateau, the goal line across its far rows, all of it in view (G5) | | 33 - 36 |

**C and F are the course's pair**: one punishes too much speed, the other
too little. Together they are the lesson the owner named: drops kill you,
and you learn the timing.

## 2. The camera plan (G2, G3)

- **Down the screen.** Every run alternates +x and +y (or uses Down, the
  grid diagonal), so the course falls about 950 lines and swings at most
  216 px across. There are no long horizontal runs.
- **The swing is a little more than the dead zone.** The CGA's is 160 px
  and the Hercules' 180 px, so the camera should make a framing move
  (LATTICE's 8 columns) or two. The intent is for those moves to come at the
  corners K1 - K3, on the ground. **To check (story 11.11)**: where they
  actually fall, and whether a tighter swing removes them.
- **The two jumps do not pan.** C's flight runs along +y, about 2 tiles,
  32 px left. F's runs along +x, 2 tiles including the gap, 32 px right.
  Both are about 32 px, against a dead zone of 160 px. **To check**: 11.11's
  airborne column; the sketch cannot model the camera's position at take-off.

## 3. The clocks (G9 - G12)

| clock | where | seen | frame |
|---|---|---|---|
| start | on a lone pillar off the plateau's left corner, beside R1 | from the start; through A | pillar (standard) |
| middle | on a pillar inside K1's bend, off the route | from T (flag 0) through K3, about 14 - 24 s | pillar (standard) |
| finish | on a pillar off the goal plateau's right corner | from F onward and from the goal line | pillar (standard) |

- **Never two on one screen**: the clocks are more than 350 lines apart.
- **The longest stretch without a clock in view**: about the middle of A to
  T, and K3 to F, each about 6 - 8 s (PREDICTED), under 15 s.
- **Open**: whether the middle clock's pillar, in front of the D legs, hides
  any of the K1 - K2 leg. That is the visibility check's to say (11.5).

## 4. Surfaces, lifts, pads and props

- **None.** No sand, no ice, no lift, no pad, no family. The first course is
  the bare physics. Its only hazards are edges and one hole (G16 - G18).
  Course 2 (Hop, rubber's "and again", a spring) brings the first prop.

## 5. Open questions for the owner

1. **The pair, C and F.** Is "too fast" then "too slow" the right shape for
   "learn the timing"? Or should the lip come back a second time, harder (a
   narrower landing, the hole moved), in place of the leap?
2. **The ledge, B**, so early: the first open edge comes about 9 s in, and a
   fall costs 9 s. Is that too soon, or just right for "drops kill you"?
3. **Rails.** Nearly every edge is railed, with the open edges chosen (B,
   K2's gap, K3, the walk, the leap). Is that too much help? Or should the
   walk keep one rail?
4. **The clocks' art**: standard pillars here, or this course's own (the
   guide's G23)?
5. **The name in the tool**: `ROLL`?
6. **Length**: about 35 s PREDICTED. If the first play comes in short, the
   lengthener is a fourth ramp on the hill, or a second walk.
