# DOWNHILL DECISION: structural visual-interest options (a study, 2026-11-21)

**THE OWNER PICKED A, C and D (2026-11-21)** - the landing floats, the maze's islands and the bridge's landing
float (the links do not), and the chamfers on L's corners and the hub's front-left. They are `sketch.py`'s own
geometry now (rev 17: `float_=True` on those floors, the cuts in `HALVES`), so the sketch alone writes them;
`struct/variants.py` still writes the study's options over it. What follows is the study as it was written.

*Options for the owner to pick from, none of them applied: `apps/bonanza/courses/down.bbc` and
`down/sketch.py` are unchanged (the lead owns them). Each option is a few lines added to the sketch's output by
[struct/variants.py](struct/variants.py), which imports `sketch.py` as it stands and writes a scratch course
(`python3 struct/variants.py base OUT.bbc` writes `down.bbc` byte for byte; `A` ... `F` add one option). Every
number below is MEASURED on the host off the real compile (`bbcourse.compile_course`, the shipped encoders) at
`bounce-bonanza` 360012de (DOWN rev 16). The pictures are the compiled CGA picture, before on the left, after on
the right. [struct/measure.py](struct/measure.py) prints a variant's sheets and sizes and writes its CGA picture;
[struct/demo.py](struct/demo.py) finds the route demo's keys on the base and replays them on a variant (each about
4 - 13 minutes a compile, run from the repository root). Clocks and decals/signs are other studies and are not touched here.*

## What "structural" can and cannot change here

The constraint is that the course PLAYS exactly as before. Three kinds of change meet it, and the options are
sorted by which kind they are:

1. **`float` (SPEC.md 137.27.2), the picture's alone.** A floating cell's faces over the void hang 3 units (or
   `thick` units) instead of to the ground. *No grid byte, no physics, no route* (137.27.2, 137.27.4): the
   world part, which is all physics reads, is the same size (20,290 bytes RAM in every float option, MEASURED).
   Options **A, B, C** (and F, their sum).
2. **Geometry on cells no ball reaches**: free-standing WALL pillars three or more tiles (Chebyshev) from every
   floor and rail (a wall is never a reachable cell, 137.10.4.1) - option **E**. The grid gains the cells, the
   play does not.
3. **Geometry on reachable cells the route never uses**: half-cell chamfers (`hole half`, 137.24.4) on corners -
   option **D**. This one IS a change to the floor (a ball that rolls into a cut corner now falls), so it is the
   one to weigh.

Tried and NOT offered, and why:

- **A back wall** behind the run or the hub: every back edge of DOWN is a fall today (the hump run, the landing,
  the snake), and a wall there would catch the ball. The hub's back already has its rails.
- **A different surface pattern**: `surface` is physics (sand, ice and bounce change the force, drag and
  restitution, 137.11.6.2); the only drawn-but-inert case is a `bounce` WALL top (magenta), and DOWN's walls are
  rails the ball meets.
- **Notches cut into long flat platforms** (the hump run, the hub): a notch is a hole in a floor the route
  crosses. B gets the same break-up from the faces under the platform instead.
- **Terracing the hub's faces with graded floats**: only a cell whose +x or +y edge is open draws a face, so
  floating the hub's front row leaves black under it rather than revealing a stepped core behind; the hub reads
  as a floating deck, not a terrace. Not worth an option of its own; A, B and C are that idea where it reads.

## Proof that the play did not move

- **The route demo** (`route_demo`'s own choice on rev 16: the arrows alone stall at the chute's corner, so the
  HOPPING autopilot's `route_plan` keys, found in 278 s) reaches the steel finish in **2,458 steps (44.7 s),
  steel, 3 of 8 flags** on the base. Those exact keys, replayed on every variant through `bbcourse.Physics`,
  give the result in the table and a SHA-1 over every step's `(gx, gy, gz, gvx, gvy, air, material)`: the same
  hash is the same run, step for step.
- **The checks**: every variant COMPILES, which is every refusal of the tool's (the occluder bounds, the
  width, G9/G10's clocks, the sheet plan). `--guide`'s run-based half has no complete autopilot run on rev 16
  (base included: "no complete run yet"), so it refuses nothing either way; the replayed demo above is the run.
- The route demo walks the STEEL leg. The glass leg is not walked by any demo yet; options A - C cannot move it
  (no grid byte), E's pillars are nowhere near it, and D's only glass-side cut is the hub's front-left corner,
  three tiles from the glass pad and the bridge.

## The budget

DOWN is SHEETED (SPEC.md 137.30.12): its picture is **2 sheets of 89 block rows** (rows 0 - 88 and 55 - 143),
each **53,150 bytes in RAM** (11,874 under the 65,024 a part may be), plus the world part. A sheet holds every
block, record and mask (`fixed`, 24,670 bytes on the base) and its own 89 map rows, so **a new block costs 16
bytes in BOTH sheets** and a record/mask its bytes in both; only the map is per-sheet and it does not move (no
option adds a block row: the picture stays 1,152 lines, the plan 2 x 89 at rows 0 and 55 in every variant).

| | per sheet, RAM | vs base | blocks | records | LZB on disk: sheet 0 + sheet 1 + world | vs base | the route demo |
|---|---|---|---|---|---|---|---|
| base (rev 16) | 53,150 | - | 778 | 1,747 | 10,837 + 11,884 + 3,032 = 25,753 | - | goal, 2,458 steps, `43b93d2c` |
| **A** the landing floats | 53,590 | **+440** | 781 | 1,845 | 10,943 + 11,977 + 3,040 = 25,960 | +207 | the same: goal, 2,458 steps, `43b93d2c` |
| **B** the upper run on piers | 53,502 | **+352** | 800 | 1,747 | 11,112 + 12,081 + 3,048 = 26,241 | +488 | the same: goal, 2,458 steps, `43b93d2c` |
| **C** the maze's islands float | 54,310 | **+1,160** | 778 | 2,019 | 10,864 + 11,886 + 3,048 = 25,798 | +45 | the same: goal, 2,458 steps, `43b93d2c` |
| **D** chamfered corners | 53,550 | **+400** | 801 | 1,746 | 11,027 + 12,072 + 3,070 = 26,169 | +416 | the same: goal, 2,458 steps, `43b93d2c` |
| **E** a skyline of pillars | 53,182 | **+32** | 780 | 1,747 | 10,925 + 11,949 + 3,073 = 25,947 | +194 | the same: goal, 2,458 steps, `43b93d2c` |
| **F** = A + B + C together | 55,006 | **+1,856** | 797 | 2,117 | 11,174 + 12,116 + 3,062 = 26,352 | +599 | the same: goal, 2,458 steps, `43b93d2c` |

D also grows the world part by 40 bytes RAM (20,290 -> 20,330: the split cells' pair records); E's world part
is the same size in RAM (its walls are inside the grid's existing rows and width). (These are `compile_course`'s parts, without the song
the build attaches to the world part, SPEC.md 137.50.3: the build's world figure is larger by the song and is
the same in every option.) The LZB world figure moves
by a few bytes in every variant because the identity word is in it. Every variant is far inside the sheet
(F, the largest, leaves 10,018 bytes per sheet).

**Why the float options add records.** A float takes a column out of the picture, and what was hidden
behind it is now drawn - and is an occluder for some reachable ball position (137.10.4.4). C adds the most
(+272 records, about 1.1 KB a sheet): a 3 x 3 island floating over the maze exposes the islands, banks and
links behind it, each a record. It is still the cheapest on DISK (+45 bytes LZB), because the black that
replaces the columns packs to nothing.

## The options

### A. The bounce landing floats (the owner's two checkers) - +440 a sheet

`float rect 38 14 43 19` (sketch L, 34 - 38 x 10 - 14). [A-float-landing.png](struct/A-float-landing.png),
and the CGA window at 2x: [A-window.png](struct/A-window.png).

**The structural answer to the owner's note.** Today L stands on an 11-unit magenta wall that runs straight down
into the hub's and the steel leg's platforms, so its checker, its columns and the lower platforms' checkers
are one continuous field (the alias SPEC.md 137.47.1 describes, now between DIFFERENT platforms: every height
here is a whole unit, so every top sits on one diamond grid). Floating L leaves a band of black under it on
every side: it reads as an island between its two gaps, which is what it is - the wide gap and drop before it,
the bounce gap after it. It agrees with the course guide's 1.10 ("a notch means a gap"): the black under L is
the gap the player is about to bounce across. One statement, no grid byte.

### B. The upper run on piers (an arcade under the downhill) - +352 a sheet

The front edge (+y) of the hump run, descent and funnel floats, with grounded **piers** left at sketch x 11 - 12,
19 - 20 and 25; the chute's 3 x 3 corner stays grounded as a tower; the ramp's open +x side floats, so the ramp
reads as a slab coming down the hill. Five `float rect` lines. [B-arcade.png](struct/B-arcade.png).

The biggest change to the course's look: DOWN's largest single shape today is the 26-unit magenta wall under
the run (most of the picture's top-left quarter), and B turns it into a viaduct with black between the piers.
It also exposes the START CLOCK's column as a lone tall pillar to the right of the ramp - the guide's G11 "a
clock on a lone pillar" by accident, worth the clock study's look (the clock art itself is untouched).
Caveat: a pier is a strip of FRONT face only (its neighbours are floating cells, so it draws no side face);
2-wide piers read better than 1-wide (the pier at x 25 is the thin one).

### C. The glass maze's islands float - +1,160 a sheet (+45 on disk)

The maze's seven 3 x 3 islands and the bridge's landing float; the one-cell membrane LINKS do not (a `thick` on
a crack would re-lane it, 137.27.2.1). [C-maze-islands.png](struct/C-maze-islands.png).

Today the maze is a cluster of grounded columns whose faces overlap into one magenta block, so which island
joins which is hard to read until the ball is there. Floating them shows the WEB: islands over the void, the
links between them as bridges, and the two dead ends plainly dead ends. This is the most "floating" option
and runs against revision 3's "grounded columns; floating is a later, HARD course style" - but the maze IS
the glass leg's hard part, and the islands really are islands. Most RAM, least disk (the reason is above).

### D. Chamfered corners on the landing and the hub - +400 a sheet, a floor change

`hole half` on the bounce landing L's four corners (an octagon) and the hub's free front-left corner (sketch
42, 16). [D-chamfers.png](struct/D-chamfers.png) (2x).

L becomes an octagonal tower, and its cut front corner draws the split cell's dithered front face down its
column, which breaks L away from what is below it in a different way from A. **This is the one option that
changes the floor**: a ball that rolls into a cut corner now falls where it did not. No route or demo goes near
those corners (the demo lands mid-L and leaves along y 12.5; the hub's cut is 3 tiles from the glass pad), and
the replay is the proof for the steel route. Combined with A it would be an octagonal floating island.

### E. A skyline: free-standing pillars behind the landing and the hub - +32 a sheet

Three WALL pillars, tops at 28, 24 and 20 units (sketch (32, 1), (36, 3), (39, 5)), in the black behind L and the
hub: at least 3 tiles from every floor and rail, so no ball reaches one, and BEHIND everything near them, so they
never cover the ball or the route. [E-skyline.png](struct/E-skyline.png).

The cheapest option (two blocks): depth and a sense of a world beyond the course in the empty top-right of the
picture, stepping down with the hill. They stand on the ground plane, which is high on the screen at that depth,
so their feet end in open black above the course rather than on anything: they read as ruins rising out of the
deep, not as part of the route (they are wall tops, the cyan dither that says "not a floor", 137.47.3).
Placed clear of the hub clock's screen columns so the clock study's art is unaffected. More pillars cost about
16 bytes a sheet each while they repeat the same blocks.

### F. A + B + C together - +1,856 a sheet

The three float options in one compile, priced as one because bytes are not additive (blocks are shared).
[F-abc-whole.png](struct/F-abc-whole.png) is the whole picture. 55,006 bytes a sheet, 10,018 under the part.

## Recommendation (the owner decides)

**A** is the direct fix for the note and costs a statement and 440 bytes a sheet. **B** is the biggest gain in
interest for its bytes. **E** is nearly free. **C** is right for the maze if floating is acceptable on this
course. **D** is the only one that touches the floor; take it only with A, for the octagonal island.
