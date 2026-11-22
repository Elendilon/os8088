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

## The gap band's overlay (2026-11-21)

**The ask came from another session.** `bb-visuals` worked on telling a column that touches a floor from one
that stands over a gap. Its band (the face's last 2 px black, 2 px of dither above) looked right in some
places and wrong in others, and no rule separated them, so the owner chose to mark them by hand. That
session built the statement (`gap`), the refusal and the detector (SPEC.md 130.57); the builder's part was
to show the candidates and let a click choose.

**Observed:**
- **The detector costs nothing measurable.** HOP's picture compile ran 6 to 8.5 s with and without it.
- **Marking is easy; unmarking is the interesting half.** A face can be named by a rect, by a both-sides
  line, or by two lines at once. The builder rewrites every line naming the face as the fewest lines for
  what is left. It must drop any piece no candidate face is in, or the compiler refuses the course ("gap
  bands nothing"). The row's red arm is exactly that.
- **A filled box hid the band it marked**, so a marked face is now an outline with the real band showing
  inside it.
- **The Iso toolbar overflowed** with the new controls, so the band has a row of its own.

**Tested here:** the `bbedit` row (item 8, red when a band-less piece is kept); a scripted session on HOP
that ticked the box, clicked a 7 px face and saw the next picture confirm the mark.


## Test Roll (2026-11-21)

**The question for wave 0.3: does Physics need the slow part of a compile?** It does not. A compile with
the occluders off and the block limit lifted gives exactly the cells, the start and the props Physics
reads. Only the picture side differs: Y0 moves by 2 to 4 lines, there are no occluder flags or records, the
prop records come in another order, and the identity changes. On MILL and PLAY, six 4,000-step runs each
matched step for step.

**The window builds on that.** It rolls the ball on the quick compile (about 1 s to the first frame on
MILL, 8.6 s on PLAY) and runs the full compile beside it. When the full compile lands, it replays the run
onto it and compares the end states: MILL matched within about 5 s, PLAY at 119.5 s after 5,994 steps. Only
then do walls hide the ball and the run become saveable as a `.BZR`, because a demo has to carry the
shipped compile's identity. The frame is drawn from the compiler's own pieces: the picture, Heavy's poses,
`sprite()`, `shadow()` and `laid_at`.

**Tested here:** the `bbplay` row, red on the ball drawn one pixel off, a log without its RETURN, and the
block limit left lifted; the bundle plays MILL for 120 frames from the zip. **Not yet:** a frame compared
with MartyPC, a saved demo replayed on the game, and anyone playing it by hand. The frame's known
approximations are listed in SPEC.md 130.58.16.2.

## The Shapes tab (2026-11-21)

**Intended:** chutes, pits and humps edited as shapes rather than as numbers, with the height along them
and how each ball rides them (plan wave 4).

**Observed:**
- **A chute's line is an orthogonal path, and dragging must keep it one.** An end now slides along its
  own leg. A corner takes its two neighbours' shared coordinate with it. Because corners alternate axes,
  that keeps every leg straight, and the row's red arm (a corner dragged alone) is refused by the
  compiler with "not along one axis".
- **The ride readout needed no new physics.** The game's own autopilot already steers onto FIELD ways
  (130.28.10), so the job sets its route to points a quarter and three quarters along each leg, never on a
  corner, the way the shipped SHAPE route does by hand.
- **Recompiling per chute was the trap.** A first prototype rewrote the course's route and recompiled:
  93 s for SHAPE. Setting `Physics.route` directly on one cached compile makes the job about half a second.
- **The test plate was too wide for its picture**, exactly the owner's earlier "width" trap. The window's
  own band fix-up made the GUI run fit, and the row now uses it too.

**Tested here:** the `bbedit` row (item 9: shipped shapes round-trip; made, dragged, turned, reversed,
compiled; ridden), red on a corner dragged alone; scripted sessions on SHAPE and on a new plate with one of
each made from nothing. **Not yet:** played by hand; diagonal blocks in Iso (4.2).


## Add to the game (2026-11-21)

**Intended:** a course builder that puts a course in the game without an assembler and still produces what
nasm would (plan wave 8).

**Observed:**
- **The answer is prebuilt variants plus a patched table.** `make bbgamebin` builds the shipped package's
  pieces and four variants with 1 to 4 spare course slots, each with a map of where its per-course tables
  sit. Composing compiles the course list, holds its `bzcourse.inc` to the variant's line by line (a list
  that would move anything but the tables is refused, with the reason), and writes the tables in.
- **Composing the shipped list gives back the shipped package and its 360 KB floppy byte for byte.** Adding
  one course, or putting it on pad 0, gives exactly the package `make` builds for that list. With the
  table-writing step skipped on purpose, the row catches it in four places.
- **A cache key had never hit across processes.** The compiler's GROUND_AUTO sentinel was keyed by its
  repr, an address, so every process compiled from scratch. Fixing that made composing about a minute.
- **The cost:** about 730 KB of prebuilt pieces in a zip that grows to 1.3 MB; a spare slot is 51 bytes
  in the package; one added course of FIRST's size adds 1,918 bytes.

**Tested here:** the `bbgame` row and the bundle row (the shipped list composed inside the zip). **Not
yet:** a game with an added course booted and played on MartyPC.

## The blend check (2026-11-21)

**Intended:** warn when two separate floors read as one checker, and point at it in the editor (plan 3.3,
3.4).

**Observed:**
- **A floor 4 units lower and one row back lands on the same screen lattice with the same colours.** The
  seam vanishes; on the constructed course the check finds 190 px of it. A 2-unit drop turns the checker
  over, so the edge stays visible (17 px, under the bound).
- **The check predicts the far side's colours from the near floor's checker** and calls a run of pixel
  pairs a blend when that prediction holds; a pair warns past 40 px of seam and half of where the two
  floors' tops meet. Cyan and magenta are one ink on the Hercules, so both cards are checked.
- **Two shipped places blend:** PLAYGROUND (101 px, the floor at -8 seen past the floor at 0) and the
  title (59 px). Neither has been accepted: that is the owner's call.
- **It costs under a second a course** and changes no compiled byte.

**Tested here:** the `bbblend` row, red on the check disabled and on a colour-blind comparison; the
editor's stripes on a constructed course. **Not yet:** VGA (the compiler renders no VGA picture), a
screenshot of the Hercules view.

## The Map tab: the pathway (2026-11-22)

**Intended:** the pathway edited on its own picture, and a course put on it - pad, route, icon (plan wave 7).

**Observed:**
- **The builder's plan view showed nothing for `path.bbc`.** Its floors are laid by the compiler out of the
  routes, so the model's analysis has no cells. The map works on the picture instead: every pad, route
  point, gate, icon and lives counter drawn where the picture has it, dragged and mapped back through the
  same projection.
- **A route has to stay legal while it is dragged.** The builder bridges any step that is neither along an
  axis nor a true diagonal with one corner (the longer axis first, at the far point's height, so a height
  change is a ramp and the diagonal is level). The row's red arm (no corner) is refused by the compiler.
- **The map compiles in 0.03 - 0.3 s in the window's own process,** so every edit is checked at once and
  undone with the reason; the proofs that need every course (reachable, real exits) are the 47 s full
  check, in the background.
- **Exits are the course's, not the map's.** The first end-to-end game build refused a route on ROLL's
  exit 1, which ROLL has not; a placement now offers only pads whose course has an exit free - on the
  shipped map just its two ends.
- **A bigger map does not fit the prebuilt game.** The game is assembled with room for exactly the shipped
  map's 23 signs and 8 pads, so XTRA's map (26 signs, 9 pads) is refused by `bbgame.py --path` with that
  reason. The pad count also guards the save file, so it cannot just be raised; that is the next piece.

**Tested here:** the `bbedit` row (item 10), red on a bridge that adds no corner; a scripted session on the
shipped map (pad dragged, refusal undone, a course placed from pad 7). **Not yet:** a game with the bigger
map, the map played.

## The compiler made faster (2026-11-22)

**Intended:** the same compile, faster: the builder's full check on PLAYGROUND was minutes.

**Observed:**
- **Where the time was.** On PLAYGROUND 72% of a compile was NO TRAP stepping the physics model 2.9 million
  times, and each family's step hook walked every record of the course on every step. The bounds check
  worked out the same turntable and gust answer for each of about 40,000 window positions.
- **What changed.** The model reads its records through per-kind tables built once a grid; the bounds
  check keeps its answer per set of lanes; the picture fills a run at a time; the laid and occluder passes
  count per block; the route planner steps a leg's arrows-only head once. NO TRAP then computes the states
  it is about to ask for on every core, in a process that is not itself one of the build's children.
- **Measured on an idle four-core host, cache off:**

  | what | before | after |
  |---|---|---|
  | the builder's check, PLAYGROUND | 157 s | 30 s |
  | the builder's check, MILL | 36.5 s | 7.7 s |
  | the builder's picture, PLAYGROUND | 9.6 s | 4.2 s |
  | the builder's picture, MILL | 8.0 s | 3.6 s |
  | the build's compile of every course | 224 s | 110 s |
  | PLAYGROUND on one core | 166 s (loaded host) | 58 s |

- **The same compile.** Every file the build's compile writes is the old one byte for byte but the stamp
  that holds the tool's own hash, and its log is the old one line for line. Every attribute of every
  compiled course, full and picture, hashes as before; the one difference is that the grid's height memo
  is no longer in a course's pickle, where it recorded which cells happened to be stepped on.
- **The first fingerprint lied.** `_fp` renders an object with `__slots__` by its repr, an address, so two
  runs of one tree differed. The comparison was redone with a walk of `__dict__` and `__slots__`.

**Tested here:** the comparison above on all nine courses; the selfcheck's sections that step the model or
draw (two MILL items, the exit mouths and the round openings, fail the same way before the change);
`t_bbedit`. **Not yet:** the whole selfcheck and the builder's rows, which run after this lands.


## The owner's round of 2026-11-22: resizing, the route, two refusals

**Asked:** drag resizing; a way to edit route points ("most things I try to change break a waypoint, and
there isn't a waypoints interface"); a route point carried where its element was dragged; why a guard rail
on top of the new MILL is refused; why a jump-pickup course glass can make will not compile.

**Observed:**
- **The route problem was the builder's own rule.** Every edit was checked for a route point left on a wall
  or the void and UNDONE when it was - so on a course with a route, most edits failed. The edit now moves
  each stranded point to the nearest floor (within 4 cells) in the same undo step and says where; moved
  ground carries its route points, the start and a flag.
- **The route had no handles at all.** Points were reachable only by Shift-clicking through the floor under
  them; with Route on they are now numbered, picked first and dragged, with a panel to insert, reorder
  and delete.
- **The guard rail is the compiler's rule, not a bug.** A guard cell is a wall at every height drawn only as
  a rail on its flat floor's edge (130.35.1), so it may not touch a ramp. On MILL the one empty column
  between the start floor (A) and the ramp (R) touches both, so every rail cell there is refused. The banner
  now says so in plain words; the fix is a course change (or a rule change on `bounce-bonanza`).
- **The jump pickup's refusal could not be reproduced** without the course: the pickup raises the reach
  every bound is taken over, so which bound refused depends on the course. Asked the owner for the message.

**Tested here:** the `bbedit` row (item 11), red with no relocation; a scripted session (a point dragged,
a floor shrunk under two points, a ramp stretched, a floor moved with its start and points, insert and
reorder).

## Engine: a wall may be lower than what it touches (2026-11-22)

**Asked:** the owner tried to wall MILL's start floor off from the ramp beside it and was refused, the wall
being lower than the ramp's top: "a wall should be able to be lower than things around it, because it might
be walling off only something lower".

**Observed:**
- **The refusal guarded less than it looked.** The physics never read a wall's height against its
  neighbours (a WALL blocks at every height, in the model and the guest alike), and the renderer draws a wall
  like any solid cell. The one thing it guarded was that the ball never hits a column it cannot see.
- **So the rule became per edge** (SPEC.md 130.10.3): a wall walls off what is below it, and a higher floor
  beside it simply ends at the wall's edge. Only a wall sunk under everything it touches is still refused.
  No guest byte, physics version or demo moved; no shipped course needed changing.
- **Letting the ball roll onto a lower wall top was rejected:** on MILL it would carry the ball from the ramp
  over the wall and down into the start floor, through the very wall meant to stop it.
- **The builder's default followed the old rule** (one unit over the highest floor beside the area: 33 in
  the owner's gap). It is now, for every cell of the area, the lowest floor that cell shares an edge with,
  the highest of those, plus one: the owner's gap gets 29, and it compiles.

**Tested here:** the compiler's `grammar` and `split` sections (two new accepted cases, red under the old
rule); MILL plus the owner's wall compiles and its route demo finishes (1,695 steps, no fall); the builder's
Wall on the gap gives `flat 29`.
