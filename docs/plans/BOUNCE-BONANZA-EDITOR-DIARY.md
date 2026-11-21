# How It Was Built: the Bounce Bonanza course builder

*The plan is [BOUNCE-BONANZA-EDITOR.md](BOUNCE-BONANZA-EDITOR.md); the
contract SPEC.md 130.58. Entries are dated, newest last. Each separates what
was OBSERVED from what was INTENDED, and names what was actually tested.*

## 2026-11-21 - mockups, three rounds, and the contract

**The ask.** A visual course builder for every tile and prop the format has,
easy to use, with a separate shape editor tab.

**Round 1: an os8088 package.** The first mockups were a COURSE package on
the VGA desktop, drawn in the System 1 style at 2x. The owner's reply: an
in-OS builder "would be very cool, but likely not viable", because the
course compiler agents run takes minutes on modern machines. The owner suggested a
Python window like the Video Battle builder.

**What looking further found (observed).** The compiler's cost is not
parsing: parse, tiles and cells take milliseconds. It is the checks:
occluders, the reach, NO TRAP's physics runs, the visibility audit. Under
cProfile the Playground's compile spent 41 s of 92 in the trap check, about
1.08 million `Physics.step` calls. Without the profiler, at the tree of the
day, MILL's full compile took 3.5 s and PLAY's 181 s. The XT estimate (tens
of minutes to hours an edit) is a prediction from those numbers, not a
measurement.

**Round 2: a Tk window.** The window copies the battle builder's layers.
The isometric view is the compiler's own `render()`, and two facts in the
compiler made the owner's "this obstructs that" concrete:
- `owners_canvas` records which course cell drew every pixel;
- the visibility audit already names what covers a mark. For MILL it reports
  the tube mouth at (17, 20) as 50% seen, against a 50% limit, the rest
  under cells (18, 20) and (18, 21), the bounce wall in front.

The X-ray mockup recolours the real MILL picture from those two facts.

**Round 3: host play.** The model has everything a game needs except the
drawing of a frame:
- `Physics.step` on keys;
- the families' `pose()`;
- `sprite()` and `shadow()`;
- `Glide`.

100 s of play stepped in 0.03 s for MILL. A mockup frame was made by poking
the rubber ball onto MILL's ramp, stepping it, and drawing
`bonanza_assets.material_frame` onto the rendered picture.

**A trap found while measuring (observed).** `Physics` reads the compiled
part, and compiling without occluders is not always valid: PLAY's makes
1,123 blocks, over the 1,024 a map word indexes. So "compile fast and play"
is not free. It is wave 0's question.

**The owner's decisions** are listed in the plan. Two shaped the contract
most:
- only unplayable problems stop a build, and every visual check warns;
- a hidden checkpoint is a legitimate design (secret routes), so the format
  gains a `hidden` word that agents' `--strict` runs honour.

**Tested today:** the timings above, the renders and the audit on MILL, and
`tools/checkdocs.py` on the new SPEC section. No builder code exists.

## 2026-11-21 - strict is opt-in, course by course

**Decided.** The owner expects to ship courses that do not pass `--strict`.
The shipped build therefore never runs it. Agents' course runs do. A course
records its own exceptions:
- `hidden` on an element;
- `accept <warning>` for a warning it keeps, with the reason in the comment
  above;
- `strict`, once the course is finished, so it is held to `--strict` even in
  the plain build.

The goal, in the owner's words, is good courses in the end, not a gate today.

**Process.** This fork makes no pull requests; the plan carries what a PR body
would have (fork rule 11, added to CLAUDE.md and AGENTS.md).

## 2026-11-21 - waves 0 to 3, the first build to try

**Built**: the model (`tools/bbedproj.py`), the warning tier in the compiler, the jobs
(`tools/bbedjob.py`), the window (`tools/bbedit.py`) and a host row (`bbedit`). SPEC.md 130.58.10
says what each does and what is missing.

**Observed, and tested here:**
- **The round trip is free.** The model keeps the text and rewrites only the lines an edit is about.
  All 35 courses read and written are byte-identical, and so is every statement moved and undone.
- **Moving a whole course one cell over exposed four position rules** the model had to learn:
  - `half right tile ...` puts its shape after a prefix;
  - an `archway` takes a shape, not a cell;
  - water's `always` and `ripple` clauses name cells too;
  - a FIELD cell's heights are quarter pixels, 32 to a unit, not eighths.

  The row now holds all 35 courses to that move.
- **Families are mandatory.** A magnet without `uses magnet` is refused, and the refusal names the
  family. So the model adds the family itself, as part of the edit that needed it.
- **The warning tier changed no shipped byte.** `bbcourse.py -o` over the shipped courses, the pathway
  and the title wrote identical parts, demos and `bzcourse.inc` before and after. Only the tool's own
  stamp file differs. No shipped course raises a warning.
- **A wholly hidden flag now builds.** Its lane spans the pennant as drawn, with empty poses. Elements
  with nothing left to draw (a blower's fan, a boost pad's flash, a gate's pose) stay errors, because
  their lanes cannot be built. The game has not yet been run with a wholly hidden flag.
- **The picture job takes 0.7 s on MILL and 7.8 s on PLAY.** The job lifts the part's block limit
  (PLAY is over it), because it keeps only the picture.
- **The X-ray shows exactly what the audit reported.** For MILL's tube mouth at (17, 20) it draws the
  seen half white, the hidden half red, and the bounce wall at (18, 20) and (18, 21) dithered orange.
- **The full check found a mark below its share on PLAY**: the pad at (24, 42) is 50% visible against
  75%. The visibility audit only reports today, so it does not block the shipped build, and it is now a
  warning in the window.
- **Debian's Pillow has no `ImageTk`.** The window hands Tk PNG bytes instead, which Tk 8.6 reads
  itself, so the window needs no ImageTk anywhere.

**Tested here**:
- `make` (the fast tier passed);
- the `bbedit` row, red by hand on both halves;
- the window under Xvfb on MILL, SHAPE and PLAY, driven by a script and looked at in screenshots:
  Plan, Iso, X-ray, picking a problem, placing a bumper and a magnet, the Course and Source tabs.

**Not tested**: macOS and Windows, by hand, by the owner. That is what this build is for.

## 2026-11-21 - the owner's first test, and select-then-act

**What the owner found (macOS):**
- **What worked:** the window opened, a new course started, the mouse wheel zoomed and the right and
  middle buttons panned.
- **The inspector's last `y` was cut off.**
- **A drag's box did not stay.**
- **Ten minutes went on trying to add one archway.** It errored with nothing to say how to fix it.
- **A floor dragged into empty space never appeared.**
- **The plan vanished after a click, with no way back.** Delete did nothing. The Iso view never
  updated.
- **The palette's order was backwards.** Choosing a part made the next click place it, so selecting
  something added things.
- **No way to make a ramp could be found.**

**Why (observed):**
- **One refusal broke everything.** When an edit was refused, `analyse()` laid no cells. With no cells,
  the plan drew nothing, clicks hit nothing, and the picture job (which waits for a course that lays
  out) never ran. A single refused placement therefore looked like the whole editor breaking.
- **The archway had two separate problems.** A drag along a path made an arch three cells DEEP, but an
  arch is at most two cells each way. And over open floor, its legs stand on floor, which the compiler
  refuses.
- **Ramps exist, but only as text.** The only way in was typing `ramp x ...` into the statement box. The
  compiler also wants a ramp to rise a whole number of half units on each tile, which nothing said.

**What changed (SPEC.md 130.58.12):**
- **Select first, then act.** A drag selects an area, and the area stays. Adding is a button in the
  palette's Add panel.
- **Heights come from the surroundings.** A wall stands one above the highest floor in or around the
  area.
- **Every edit the compiler refuses is undone at once**, with a plain-words reason and "Keep it anyway".
- **Floors, walls and goals have Flat/Ramp, a direction and their ends**, snapped to legal rates.
- **A floor's surface is a box on the floor and travels with it.**
- **Arrows point uphill.**

**Tested here:** a script drove the real mouse bindings through the owner's steps:
- a new course;
- a floor dragged into empty space: it joined at the neighbours' height of 4;
- a wall on a row of floor: height 5;
- an archway mid-floor: undone, the plan still drawn, the reason given;
- a floor made a ramp, its high end snapped from 5 to 6;
- the ramp painted ice;
- a corner widened: the ramp kept its rate and the ice followed;
- a move: the ice followed, and one undo put both back;
- a wall deleted;
- a magnet added: `uses magnet` came with it.

The `bbedit` row and the MILL drive still pass. Not tested: the owner's machine, again.

## 2026-11-21 - the owner's second test, and the ground as one layer

**What the owner found (Windows):**
- **A second floor went in, but the course could no longer be drawn**: "cell (17, 2)'s footprint ... is
  past the 512 px width".
- **The builder made the owner assemble statements.** The owner's model is one layer of ground: a floor
  or empty space, which you change. A ramp in the middle of a floor should not mean cutting the floor up
  by hand. A pad on a cell should bring its ground. An archway should go over what it is put on.

**Why (observed):**
- **A 64-wide course draws a diagonal band.** Only cells whose `x - y` runs from -14 to 14 are drawn,
  with the picture centred.
- **Only the full check tested the width.** The width is part of the full compile's checks, so the edit
  check (which lays tiles only) never saw it, and the refused edit was not undone.

**Found by measurement first:**
- **A later statement overrides an earlier one, cell for cell.**
- **A ramp's plane is absolute**: a piece of a ramped rectangle can keep `ramp x P0 P1 H0 H1` word for
  word.
- **An archway's legs may stand on walls**, so making the leg cells wall tiles at the floor's height
  compiles.

**What changed (SPEC.md 130.58.13):**
- **`replace_area` cuts the area out of the statements around it** and adds the new ground, in one edit.
- **The area panel has Make it and Paint buttons.**
- **A part on an empty cell brings a floor tile.** An archway brings its wall legs.
- **The band is checked on every edit.** It is drawn on the plan, and fixed by moving the `origin` or
  making the course wide.
- **The full check's refusals read in plain words.**

**Tested here:** a script repeated the owner's steps through the real bindings:
- a floor beside the course, past the picture: the origin moved to 160, and the message said so;
- a ramp in the middle of the floor: the floor split into four pieces round it;
- a steel pad on an empty cell: it brought a floor tile. The full check then rightly reported a trap,
  in plain words;
- a pad on floor;
- an archway mid-floor: two wall legs, compiled;
- a one-cell wall at 5;
- an ice strip.

**Shown in the Iso view, centred on the course:** the ramp, the walls, the archway's legs, the ice and the
second floor. No shipped course trips the new band check, and the `bbedit` row passes.

## 2026-11-21 - the picture's width, and upstream's merge

**The owner**: "adding a small floor next to another small floor shouldn't trip us into needing the
double segment option?"

**It does not, and the builder was wrong on two counts:**
- **It confused the picture's width with the two-part course.** `width` is the picture's word columns, any
  multiple of 8 from 64 to 160. The two-part course is about one part's bytes, and only PLAY uses it.
  Eighteen shipped courses are wider than 64 and one part each. The builder jumped straight to 128 when a
  few columns would do.
- **Its edge check was too lenient.** The compiler holds every cell the ball can REACH to the picture, and
  a flight carries it 4 to 6 diagonals past a floor's edge (MEASURED on seven shipped courses). The builder
  checked the floors alone, so a fix it called good was one the compiler refused.

**Now:**
- Floors keep 4 diagonals inside the edge.
- The builder centres the picture first, then widens by the smallest step that fits.
- MEASURED against the compiler: two 10 x 8 floors side by side ask 80 columns with origin 224, which
  builds. The compiler refuses 72 at every origin.
- The plan shades where no floor may go.

**Merged `bounce-bonanza`**, which brings the LIFE pickup and course edits. Upstream wrote the LIFE as
SPEC.md 130.55, which this branch had used, so the builder is now 130.58. Only this branch's own lines
were renumbered: the compiler's LIFE references stay 130.55. The palette has the heart, with `once`,
`respawn` and `overwrite` as tick boxes.

## 2026-11-21 - the owner's third test: a course of ramps

**What the owner found:** the owner built a course of ramps, then asked for six things:
- dragging the goal into a higher floor should cut it in, at that floor's height;
- a ramp between floors should join them;
- floors should rejoin into their fewest blocks;
- Ctrl-click should select several parts to change at once;
- a part should take its direction from the selected shape;
- there should be an easy staircase wall as rails beside a ramp.

Floating slabs were also wanted: Overhang had only ever refused.

**Observed while building it:**
- **The occluder limit.** A ramp that joins a floor at 4 to one at 8 over four tiles makes a block of the
  picture with 5 occluder records, over the renderer's 4. Making the high floor 6 builds. So joining two
  floors can be legal for the floors and refused by the picture. The problems list now says "make the ramp
  gentler" in plain words.
- **Make it Floor on a ramp took the ramp's top height** (5.5 over a floor of 4), so nothing rejoined. It
  now takes the flat floor's height.
- **A route point stole the goal's click** and moved instead of the goal. Route points now come last.
- **Rejoining has one trap.** A statement between the pieces in the file (the goal over the floor) can
  hold cells that a later piece overrode. The rejoin refuses only that case, and otherwise rejoins.

**Tested here:** a script drove the real bindings through every step:
- a high floor;
- a ramp between it and the main floor: `ramp y 12 16 4 8`;
- the goal dragged onto the high floor: height 8, cut in;
- a ramp made in the floor, then made floor again: one rectangle;
- Ctrl-click of two floors, raised;
- stepped rails at 6.5 to 9.5;
- an archway from a 1 x 3 selection: legs at its ends, vertical;
- a one-unit hang.

The `bbedit` row adds the rejoin, the one-step group and the route point's place.

## 2026-11-21 - diagonals, and a hidden element warns

**The owner asked for two things:**
- **Diagonals, set and seen in the plan.**
- **An obscured element should warn rather than error.** The example was a speed boost behind DOWNHILL
  DECISION's diagonal. Hidden routes are coming, and the rule was never meant to stop a chute hiding a
  pad.

**Observed:**
- **What still refused was the wholly hidden case.** The half-hidden cases were warnings already. When
  nothing of an element was left to draw, its lane could not be built, so 130.58.10 had kept that an
  error.
- **The fix depends on how the lane's rect is made.** For a boost pad, gate, plate, bridge, gate art and
  turntable cell, the rect is computed before any clipping, so it stands with empty poses. For a magnet,
  blower and membrane it came from the visible pixels, so it now spans their art as drawn, as the flag's
  does.
- **No shipped byte moved, and the touched selfcheck sections pass.**
- **The plan's diagonals are exact.** A `Split` is one record per half or quarter, so the plan draws
  each one as its own triangle (SPEC.md 130.24.3's corners). On PLAY's diagonal section, a click at a
  cell's two corners picks its two different halves.
- **Cut a corner** keeps whole halves of each cell's own statement, and the rest rejoins.
- **Diagonal strip** lays a `floor box`, which the compiler builds straight down the screen.
- **My first test cut the corner holding the start**, and only the full check noticed. The edit check
  now holds the start and the route to the ground, so that edit is undone with its reason.

**Tested here:**
- the `bbedit` row, with the pieces and picking and the three wholly hidden builds, red on the boost
  pad's old refusal;
- the selfcheck sections;
- a scripted run: two corners cut and a strip, both compiled;
- PLAY's diagonals drawn in the plan.
