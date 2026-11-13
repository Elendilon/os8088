# BOUNCE BONANZA — how it was built (diary)

The running diary that [BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md) links
to (CLAUDE.md, *Building an app or game in waves*, step 6). Observations are
kept apart from intentions, and every entry names what was actually tested.

## 2026-11-12: the brief and the investigation

**The brief.** An overhead isometric course that scrolls, with a ball as the
player, for the 5150. Hardware scrolling, probably vertical only as in 1942,
but both ways if that is feasible. A rolling ball that looks 3D, done with
frames rather than 3D maths, the way *Extreme Pinball* did it. Mini-golf
props, including tubes that spit the ball out with momentum. 2–6 animated
obstacles paced by TITHE's wheel. Physics more fluid than Marble Madness.

**Observed: what the tree already proves.**
- Excitebike scrolls horizontally on the CGA and the Hercules, one 8 px
  column at a time, at a **measured 54.6 Hz** on MartyPC's XT (SPEC.md 102,
  PERFORMANCE.md Set 148).
- 1942 scrolls vertically on the CGA, two scan lines at a time (SPEC.md
  101.1).
- Both do it by moving the 6845 start address through the same 8 KB ring
  per bank.

**Worked out on paper, not run: combining the two.** A 40×100 window
cannot alias inside a 4,096-word ring (the proof is the plan's section 2.1).
Entering rows fit in the ring's 96-word slack, so they can be drawn off
screen; entering columns have to race the beam.

**Prototyped, on the host only: the "phase torus" ball.**
`bounce-bonanza/ballproto.py` renders a 16 px ball that samples an
8-periodic texture through u = R·asin(x/R). Rolling adds the screen
displacement to the phase, so 64 frames cover every direction with no jump
when the ball turns. Looking at the GIFs:
- the **spots** texture reads best as rolling;
- **checker** reads as a beach ball;
- the slope checkerboard of the isometric mock shows slope direction
  clearly in 4 CGA colours.

**Not tested: anything on a guest.** No package exists yet. The budget in
the plan's section 6.5 is predicted from measured unit costs and is what
wave 0's spike is for.

## 2026-11-12 (later): wave 0, the spike, is a GO

**Built:** `tools/bonanza_assets.py` (the course generator, the ball and
their `--selfcheck`), `apps/bonanza/` (the package, 6,191 bytes plus 813 of
bss), four disks, and three soak rows: `bonanzaassets`, `bonanzaring` and
`bonanzaperf`.

**The course** is a generated isometric heightfield: a start plateau, a long
descent, steps, a traverse with pits and blocks, a climb and a sprint to a
chequered finish. It is 512 x 1600 px, which cuts into 293 distinct 8x8
blocks, so each course part is 30 KB.

**Observed on MartyPC (cycle-exact, the 1,200-frame benchmark):**

| | CGA | Hercules |
|---|---|---|
| display | 59.8 Hz (2 misses) | 50.85 Hz (0 misses) |
| busy share of a refresh | 58% | 50% |
| box compose | 23.5k clk | 23.5k clk |
| retrace wait (idle) | 33.5k | 46.6k |

The prediction was 35-45k clocks of work a CGA frame. The measurement is
46k, a little over that, but inside one refresh. **60 Hz holds on CGA**, and
`FSXF_RATE` is not needed.

**The ring is exact.** The card's memory, decoded through the ring at the
package's start address, equals the host's own picture on every checked
frame in all eight scroll directions, on both cards, and the rendered glass
equals it too.

**The order rules are now tested, not just argued.** The row stops at the
retrace start as well as at the presented frame, so it sees the ORDER of the
writes. A copy built with the column written before the flip goes red only
at that stop.

**Discovered:**
- **The box races the beam too.** The plan wrote the boxes after the
  columns. With the camera clamped at the course's top, the ball sits high in
  the window, and its box was still unwritten when the beam passed: one
  refresh showed the ball where it was. The fix writes the entering column
  in raster order round the boxes (SPEC.md 128.2 rule 4).
- **The first route never scrolled up.** A host simulation of the autopilot
  and camera found it. The route gained a return leg, and `--selfcheck` now
  asserts that every axis goes both ways.
- **The Hercules 200-line field is 50.8 Hz on MartyPC, not 50.**
- **The Hercules ball's mid tone is stripes**, because the contract pinned it
  to one pattern while the course uses a checker. It is cheap to fix, since
  the frame index already carries the ball's parity.

**Not tested:** kern_mega (MartyPC is an 8088), EGA and MDA refusals (only
VGA was tried), a two-card machine, and real hardware.

**Next:** the optimisation round (plan, wave 0b). Box compose is the largest
working part and the two CGA misses are two-row frames, so compose and rows
come first.

## 2026-11-12 (evening): the owner plays it

**The owner played it on 86Box (a 5150 with CGA).** The first try said `Load
failed`. The cause was the emulator's setup: the third drive was set to an
80-track quad-density type while holding a 40-track 360KB image. A 5150 BIOS
steps one track at a time, so only track 0 (the FAT and directory) reads
right on that drive. The file is listed and its body is not. With the image
in a 360KB drive it loads. There is no package or kernel defect. The lesson
for whoever reads a field report next: **check the drive type before the
package.**

**What they saw:** "The ball animation is very impressive." But **scrolling
slowly is jerky, and speeding up it smooths out.**

That is the hardware floor showing through wave 0's camera. The CGA moves the
picture in 8 px and 2-line steps, and nothing finer exists in its graphics
mode. Wave 0's camera follows a slow ball one step at a time, so the world
hops every few frames, and the ball jumps back on the screen each time. Fast,
it hops every frame, and that reads as motion.

The fix is a camera rule rather than a renderer: **rest, or move fast; never
trickle.** Wave 0b ships three camera modes so the owner can choose by feel
(SPEC.md 128.9): GLIDE, FOLLOW, and wave 0's TRICKLE as the control. TITHE
took about twenty rounds to feel right, and this is expected to be the same
kind of loop.


## 2026-11-12 (night): wave 0b, the camera and the optimisation round

**What was built.** Three camera modes, cycled with `C` in play or on the
desktop face: GLIDE (rest inside the dead zone, then pan fast with a lead),
FOLLOW (a camera velocity that eases toward the ball's), and wave 0's
TRICKLE as the control. The optimisation list from SPEC.md 128.9, and the
Hercules ball's mid tone now follows the course's checker instead of
striping across it.

**Measured** (MartyPC, the 1,200-frame benchmark, A/B against wave 0 built
with its own art; SPEC.md 128.9 has the full table):

| | CGA wave 0 | CGA wave 0b | Hercules wave 0 | Hercules wave 0b |
|---|---|---|---|---|
| box compose | 23,515 clk | 11,490 | 23,568 | 11,839 |
| busy, of a refresh | 58% | 43% | 50% | 37% |
| misses in 1,199 | 2 | 0 | 0 | 0 |
| worst frame | 134,437 clk | 105,051 | 116,916 | 114,705 |

**Discoveries.**
- **FOLLOW cannot fix the slow-scroll jerk, and the measurement says why.**
  A camera moving at the ball's speed has to step every 8/v frames, so at a
  slow ball FOLLOW steps exactly as often as TRICKLE (every 15-17 frames
  across on the CGA). It only centres the ball and evens the gaps. GLIDE is
  the only mode that changes what the eye sees: a pan steps every second
  frame across (30 a second on the CGA) and every frame down, with long rests
  between pans.
- **The benchmark route had to change.** Under GLIDE, wave 0's route gave
  the Hercules no right-going diagonal and the CGA no pure left step, so the
  ring row's "all eight directions" check would have failed. An integer-exact
  host model of the autopilot and cameras chose new waypoints, and MartyPC
  confirmed them (3-6 of each direction).
- **The review caught a deadline that could never fail.** The row-0 corner's
  first design checked the box's last line, but the column writer outruns the
  beam, so its binding deadline is its first row. It now writes the column
  first and checks both ends of the box. The test course cannot actually put
  a box at row 0, which SPEC.md says plainly; a later wave owes it a probe.
- **The row and column writers are bound by the card, not the code.** About a
  fifth cheaper a call after the rewrite, where box compose halved. Further
  speed there would come from writing less, not from tighter loops.
- **15KB in each ball part can never be drawn** (only one shift in four is
  reachable for a given frame). Left for a later wave.

**The verifier found a real defect after the fix stage.** The CGA results
face drew 14 lines into a 13-line box, and the spill left a broken stretch
in the dock's border after the window closed. The face is now 13 lines and
`bz_line` refuses to draw past the box.

**Next:** the owner chooses a camera by feel; wave 1 (the course pipeline
and physics v1) starts now.

## 2026-11-12 (wave 1, the host half): courses become text

The first stage of wave 1 built everything a host can check: the course
compiler (`tools/bbcourse.py`), the two shipped courses, the physics model the
guest will be written to match, and the smaller ball part. Nothing here has
run on the 5150 yet; the numbers below are the tool's own, not measurements
of the game.

- **A course is a text file now.** `apps/bonanza/courses/first.bbc` is the
  worked example from the contract, nine lines long. `bench.bbc` is the
  benchmark's course. One compiler run turns the list into two parts a course
  (one a card) and the include that lists them.
- **The ball part lost three quarters of itself.** Only one shift of each
  frame was ever drawn, so the part went from 20,816 bytes to 5,456. Every
  stored frame is byte-for-byte the old one at its own shift; one line of the
  box compose changed to match.
- **The occluders cost far more than the contract predicted.** The rule that
  draws a ball behind the scenery has to cover a ball falling off ANY edge,
  not only into pits. The worked example needs 32 records in one block row
  and 23 at one ball position, against bounds of 24 and 8; the benchmark
  needs 79 and 29. The tool refuses at 96 and 32 for now, and the choice is
  the owner's (SPEC.md 128.10.12 O8).
- **The benchmark course had to get narrower.** The void band round a course
  reaches four tiles sideways on screen, and every place the ball can be has
  to fit in the 512-pixel picture. Wave 0b's course was half again too wide.
- **A half-unit step at the bottom of a ramp cannot be climbed**, though the
  same step between two flat floors can. The floor height is sampled one
  ground unit inside the tile, which puts it a quarter pixel over the limit.
  The return route stuck there until the landing was made level.
- **Landings stopped dead in the first physics model.** The contract tested
  the walls against the ball's height after the move, so a ball landing next
  to a floor of the same height treated it as a wall. Testing against the
  height at the start of the step, as the contract already did elsewhere,
  fixed it.
- **The route was chosen by search.** With the course that narrow the camera
  is pinned at one side or the other at the end of every long leg, so no
  reversal there gives a diagonal scroll. The new landing is a square plateau
  in the middle, and a hill-climb over routes in a host model of the GLIDE
  camera found a loop round it. That loop scrolls in all eight directions at
  least 8 times on both cards, where 5 is required.

## 2026-11-12 (wave 1, the guest reads a course)

The second stage gave the guest a course. The engine still moves the ball
with wave 0b's flat motion; physics comes next.

- **Enter plays First Roll and B benchmarks Proving Ground.** The key picks
  the course and the card picks the part row. The face's second line names
  both courses by their titles, which come from the generated include.
- **Every course value is read at launch.** The engine used to assemble
  each course constant into its code. Now `bz_crshdr` copies the header into
  the package's data on the desktop: the map's shift and stride, the size,
  X0 and Y0, the route and the start. The camera's limits come from the
  course's size.
- **The column writer reads the map stride from the course part.** It
  already held that part in DS, so `add bx, [24]` replaced `add bx, 128`.
  The two instructions are the same 4 bytes, and the new one patches no code
  and works on kern_mega's selectors.
- **The start comes from the grid.** The ball begins on the start tile's
  centre on its floor. The rule is the same one the compiler uses for
  waypoints.
- **Checked by one look boot per card.** On the CGA and the Hercules, the
  card memory matched the course part's picture, away from the ball, in
  every check: First Roll at rest, First Roll after rolling to the far
  corner, and Proving Ground 400 frames into the benchmark. The benchmark
  ran its 1,200 frames on both cards with `late` 0.
  The package image is 8,994 bytes (wave 0b: 8,785) and its bss is 939
  bytes (913).

## 2026-11-12 (wave 1, the ball goes behind things)

The occluder stage put the rule of SPEC.md 128.10.4.4 into the box compose.

- **One routine, entered from the end of the compose.** `bz_occ` runs after
  the ball is drawn into a box. It visits only the new footprint's blocks,
  at most three block rows of at most three columns. For each block row it
  reads that row's records from the course part's index, skips the ones to
  the left and stops at the first one to the right. A record whose cell is
  behind the ball's and whose top is above the ball (by the 4 px margin
  while the ball rolls) puts its block's pixels back over the ball.
- **The lay needs no NOT.** `((buffer XOR block) AND mask) XOR block` is
  the contract's `(buffer AND mask) OR (block AND NOT mask)`, one
  instruction shorter a line.
- **Both boxes get the pass, not only the new one.** When the old and new
  footprints take two boxes, the card gets the FIRST box's bytes where the
  two overlap, and the first box is the old footprint's. So every box runs
  the pass, clipped to its share of the new footprint. A box with no share
  walks nothing. SPEC.md 128.10.8 item 1 now says so.
- **The cell's flag is a saving, never a verdict.** The pass runs only when
  the ball's cell is marked as one where a record could ever be laid. If a
  test has poked the ball somewhere and no step has run since, the window
  of cells may still describe the old place. Then the pass runs anyway,
  which lays exactly what the rule lays.
- **Checked on the host first.** A scratch harness ran the built package's
  compose under an 8086 emulator along physics runs on both courses, with
  the footprint's box, union boxes and boxes clipped at every edge:
  138,480 boxes against the compiler's own composite, 6,075 of them laying
  21,840 records, none different. With the records left out of the host's
  picture, 93 boxes of 1,800 on one run differed, so the check can fail.
- **One look boot per card.** Holding Right and Down on First Roll flies
  the ball off the slope and into the pit. Its last frame before the
  respawn hides 12 px of the ball behind the pit's near rim, on both cards.
  On the Hercules the benchmark was run as well. It laid records on 157
  frames. Each one decoded from the card equalled the host picture, and
  the most the rule hid in one frame was 36 px of the ball, rolling behind
  the traverse's block.
- **A finished play now shows its time in place of the benchmark's
  results.** The CGA face has room for 13 lines, and the results already
  fill it. The results come back with the next benchmark.
- **Sizes.** The package image is 11,808 bytes (the stage before: 11,413):
  +395 for the pass, the instruments and the face. The bss is 1,085 bytes
  (1,055): +30, of which 18 are the pass's working words and 12 are the
  three instruments and their copies.

## 2026-11-12 (wave 1, the rows that will judge it)

SPEC.md 128.10.11.3's rows were written in this stage and NOT run: the
final pass runs every one of them once, with its red arms, and measures
the `secs` each is registered with (all predicted here, and each row's
description says so).

- **One oracle, the compiler's.** The ring row's host picture is now
  `bbcourse.py`'s render with the ball composited and the occluder
  records laid back at the guest's own `s_b`, `z_b` and air flag - the
  compiler's `composite`, not a second copy of the rule. The frames
  checked behind a record are chosen on the host, from what the oracle
  hides, not from the guest's own counter: a build whose pass never runs
  would otherwise never be looked at where it is wrong.
- **The row-0 probe could not be built as written.** The contract asked
  for a window ten columns from either side of the course; on the
  Hercules the whole camera range on a 64-column course is 19 columns.
  And a probe ball must hang over a floor somewhere down its screen
  column, which the narrow benchmark course runs out of within a few
  columns of a pan to the right. The probe settles the window low on the
  course's right instead and pans up and LEFT; the host model gives about
  12 qualifying frames on the CGA and 8 on the Hercules, against the five
  required. SPEC.md 128.10.11.2 now says so.
- **Physics is checked exactly, every frame.** `bonanzaphys` steps the
  host model to the guest's step count at every presented frame and
  compares eight numbers with no tolerance, over the benchmark on both
  cards and over four poked scenarios on First Roll (the pit, the lip,
  the rail, the goal). Each scenario was chosen by running the host
  model first: the pit's run passes over a SAFE cell so that a respawn
  "at the start" is distinguishable from the right one.
- **Every red arm must fail at its own check.** A broken package that
  fails somewhere else proves nothing about the check it was written
  for, so each red arm names the failure it must produce.
- **The A/B leg builds wave 0b from git.** `bonanza_perf.py --ab` takes
  that commit's package source, includes and generator out of git into a
  temporary tree, runs its own generator and packs it in its own part
  order. Built on the host here, it assembles; the build of today's
  package by the same helper is byte-identical to `build/`'s.

## 2026-11-12 (wave 1, the review round)

Four reviewers read wave 1 through four lenses - the picture, the
physics, the cost and the OS - and returned fifteen findings. What they
found, and what changed:

- **The occluder pass was the expensive part, and it still is.** It laid
  every qualifying record separately, eight lines read, merged and
  written per record, so its worst frame grew with the record counts.
  The pass now treats the records of one block word as a GROUP: the
  masks of the laid ones are ANDed (only the lines the lay touches) and
  the word is laid once - the AND of two keep-masks keeps only what both
  keep, so the bytes are the same - which caps the lays at nine. Each
  block row's first candidate is found by a binary search on the column
  instead of a walk from the row's start, and the keys sit in registers.
  **Priced from the instructions the built guest executes** (a host
  trace, not a measurement): the worst reachable position costs 28.3k
  clk on First Roll and 33.5k on the benchmark's course, where laying
  each record separately priced 34.5k and 42.5k; over the benchmark's
  route the pass is gated on at 22.5% of frames, 8.2k on those, about
  +1.9k a CGA frame - against the contract's +0.7k, which assumed the
  bounds the courses do not meet. Grouping bounds the lays, not the
  tests: only fewer records (open question O8) shrinks the rest. The
  binary search turned out to save little on the mean - the benchmark's
  records are thin - and that is written down rather than hidden.
- **A per-step test paid for the harness.** Every step began by
  checking that the window was centred on the ball, which only a test's
  POKE could ever break - about 100 clk a step. A poke now raises a flag
  (`bz_pokd`), the next step refills the window and clears it, and the
  hot path pays one byte test; the occluder gate reads the same flag.
  The poke helper also writes the screen position, so a frame that runs
  no step draws the ball where it was put.
- **The oracle and the guest disagreed in a corner only a poke reaches.**
  The guest skips the pass in a cell whose OCC flag is clear; the ring's
  oracle laid records by the rule regardless, and a poked ball can sit
  at a height its cell never reaches. The oracle now applies the same
  gate, with the flag read from the host's course, not the guest's, so a
  wrong flag in the part still shows.
- **A latent off-by-one in the occluder derivation.** A ball at a whole
  height with a fraction has its footprint one line higher than the tool
  tried; the derivation now covers that line, and the selfcheck has an
  item for it with a negative control. On the shipped courses it changed
  no byte of any part.
- **Three sentences in the contract were wrong about the physics**: a
  one-arrow ball settles at 0.74 gu a step from rest (189), or 252 when
  slowing, not 1 gu - the round-up drag has a dead band; a fallback undo
  never lands an airborne ball; and the wall test is asymmetric (the
  integer `u` against east and south walls leaves the ball 1 gu closer
  and creeping), which wave 1 keeps and now says so.
- **The rows were made to survive the merge.** The A/B leg against wave
  0b skips itself, with a line, when that commit is not in the clone -
  upstream squash-merges; the kern_mega row reports a package the kernel
  closed instead of dying in a traceback; and the course list is read
  out of the Makefile and the generated include rather than copied by
  hand into the tool and the rows.
- **The launch costs per course.** The benchmark's parts pack to twice
  wave 0b's - about three more disk calls - while Enter's are smaller.

## 2026-11-12 (wave 1, the final pass)

Every row ran once, as one scoped soak call (`bonanzacourse`,
`bonanzaassets`, `bonanzaring`, `bonanzaperf --ab`, `bonanzaphys`,
`bonanzaexit` on MartyPC, `bonanzamega` on 86Box), then every red arm.
Four came back green and three red, and none of the three was the
assertion being wrong about what it guarded. What was found, all of it
measured rather than argued:

- **The row-0 box was really late on the CGA, sometimes.** The probe
  asked for `bz_late` 0 and got 4 - 6 of 12. MartyPC's cycle counter,
  read at the read that saw the sync rise and at both of `bz_latechk`'s
  checks, took it apart into three causes. The box WRITER is not "about
  the beam's speed" as wave 0b assumed: a 4-word line costs about 490
  clocks against the beam's 304, so a 16-line box at row 0 has about
  2.7k clocks of slack. `bz_latechk` reckoned the beam from a clock
  sample a whole turn of the retrace spin BEFORE the read that saw the
  sync - about 840 clocks, where it allowed one line - so on-time boxes
  were counted late. And a FASTTICK interrupt (about 2.9k clocks)
  landing between the rise and the box's last line made a box really
  late, about one row-0 frame in eleven. The guest now spins tight and
  samples the clock just after the rise, allows a measured bound
  (`BZ_VLAT`) instead of a line, and shuts interrupts from the rise to
  the end of the box write on the frames that have a row-0 box - 13k
  clocks, under a tick. 98 bytes of image and 1 of bss (and 2 more
  for the kern_mega fix below: 11,956 to 12,056 in all).
- **The probe itself asked for a frame play cannot make.** It panned UP
  two rows a frame with a column and a window refill every frame, which
  overran a CGA refresh. Play reaches window row 0 only at the top
  clamp - a flight's apex over the course's top - so the probe moved
  there: the window settled on the start, the ball poked onto the first
  line and panned right. 11 qualifying frames on the CGA, 7 on the
  Hercules. Its red arm (the whole column first) goes red on the CGA
  only, 11 of 11: the Hercules' 98 lines of sync and blank hold the
  whole column ahead of the box, so the order is the CGA's alone to need.
- **kern_mega found a real bug the real-mode kernels cannot.**
  `op_drop` restores its caller's ES after freeing the claim, and the
  bracket left a part's own selector in ES: on kern_mega that is a #GP
  the moment the claim is gone. `bz_launch` now loads its own segment
  into ES before the drops. The same row also counted the kernel's own
  286 way out of protected mode (a deliberate shutdown in
  `mega_svc_lo`) as a failure; it now resolves the reset against the
  kernel map and excludes that one, as the contract always said.
- **Two harness slips.** The goal's face line has a cell of margin
  before "Finished in", which the row read as text; and a key pressed
  the moment the play ended (the flag drops inside the bracket) could be
  lost while the bracket was still being left, so the rows now wait for
  the launch to drop its parts first, as `bonanzaexit` always did.

The numbers, all MartyPC, the benchmark on `BENCH`: busy **46.5%** of a
CGA refresh (59.96 Hz on a 59.92 Hz card) and **39.4%** of a Hercules one
(50.87 Hz), no misses, inside the contract's predicted 45 - 48% and 39 -
41%. Against wave 0b on its own course: busy +2.6k clocks a CGA frame
and +2.2k a Hercules one. Physics costs +3.0k and +3.6k in sim + camera,
more than predicted, but the occluder pass, feared at +1.9k, shows as
+0.4 - 0.5k in the box compose. The bytes went the other way: the
benchmark's course part is 54,214 bytes against a predicted 46,000, the
package 64,509 bytes on the disk against 25 - 35KB, nearly all of it
occluder records twice over - open question O8, which stays the owner's.
Story 1.3 is the one left unticked for that reason.

## 2026-11-12 (wave 2, the contract)

Wave 2 is "feel", and its contract (SPEC.md 128.11) was written before any of
its code. What it decides, and the one thing it measured to decide it:

- **Three balls, and the hard fall as a mechanic.** The owner's D4 becomes
  one table of constants a material, written once in the course tool and
  generated into the package: the rubber ball bounces (a 6-unit drop
  rebounds 3.8 units and carries nearly five tiles - the gap only it can
  cross), the steel ball is stunned for a second by a 1.5-unit drop, the
  glass ball shatters on about 2.7 units and comes back. Every number is
  PROVISIONAL until the owner has rolled them.
- **A bounce never climbs.** The rebound is a fraction of the impact with
  the floor taken as still, and the Hop works only from the ground. That is
  a design choice for the reachable set's sake: a Hop at the bounce would
  pump a rubber ball to the vertical cap anywhere on the course, and every
  occluder and `Y0` with it.
- **O8, measured before it was decided.** The course tool's own reachable
  set and records, run on the host with each candidate rule: wave 1's 3,143
  records on the benchmark's course are 1.7 a block over every block that
  can hide the ball, almost never split by their band of tops. Narrowing the
  reachable set to pits (the option recommended to the owner) halves them -
  by drawing a ball that falls off a back edge over the plateau it falls
  behind. An exact merge of the records no position tells apart takes 13%
  (21% on First Roll) at no cost to the picture. So the contract keeps the
  reachable set, merges, and bounds the records per BLOCK (4), which is what
  a frame pays; the bytes are answered elsewhere.
- **The Hercules copy goes.** A Hercules block is the CGA block through a
  pure function of the pixel and its line's parity, so the guest can make it
  at the fetch through a 512-byte table in about a tenth of a second. One
  part a course and one a ball on the disk: the package is predicted to
  SHRINK to 45 - 52KB with a third course and two more balls.
- **Replays are the cheap half of determinism.** A play is its course, its
  ball and one key byte a step, run-length coded in 4KB; the guest replays
  it on either card and the host model runs the same bytes, which is the new
  `bonanzareplay` row.

Intentions, not yet observations: every cost and size in 128.11.15 and
128.11.16 is predicted; the final pass measures them.

That was the first draft. The review below changed several of its
numbers, and SPEC.md 128.11 is the authority: the 6-unit rebound is 3.7
units, the stun's fall 2 units and the shatter's 3, a Hop also fires at a
contact (never adding to the rebound), the merge takes 10% on `BENCH` (13%
on First Roll) with the final reach, and the package is predicted at 47 -
51KB.

## 2026-11-12 (wave 2, the contract reviewed)

Three reviewers - budget, the OS, game design - read the contract before any
code and returned thirty-five findings, several of them one fault seen from
two sides. Every one was checked against the text and a scratch model of the
step; none was rejected outright, and three were taken in part. What they
found is worth keeping, because most of it was arithmetic the contract did in
its head instead of in the step:

- **The reach was measured on a different rule from the one written.** The
  records and `Y0` quoted were the Hop's reach alone; the written bounce rule
  added a 384 floor and a fall on top of each other, and claimed bounces
  could not reach `BENCH` or `FIRST`. Rewritten as an energy bound - a ball
  over a cell has at most the energy of the highest flight over it, a
  rebound keeps at most `e` of the speed - with discrete flights, and
  measured again: `BENCH` `Y0` 156, 2,938 records merging to 2,645, five
  rounds to settle. The record counts also swing up to 7% with `Y0`'s
  alignment to the 8-line blocks, which is now said rather than hidden.
- **The rubber ball overflew `FIRST`'s goal.** A one-column goal and a
  10 px bounce off the lip: every rubber run in the model fell into the void
  past it. A goal is now a finish line crossed in the air too.
- **Shifts truncated a material to nothing.** Steel's force quartered on ice
  was 0. Each material's force, drag and brake on each surface is now a
  generated number, and the self-check holds every pair to moving.
- **A hop down a ramp was judged as a fall.** Hard landings now use the
  impact relative to the floor; and a rebound off a floor falling away is
  relative to it too, or a small bounce on a steep ramp became a long flight
  onto its foot. The model then showed a crest at the cap throws any ball
  three tiles - a course rule now, not a surprise.
- **The keyboard had two traps the OS already knew about.** An interval
  test cannot see the typematic delay (SPEC.md 9.7 says so in its first
  paragraph), and the kernel's key-state map reads a 101-key keyboard's fake
  shifts as Left Shift. The desktop keys now ask `OSAPI_KEY_DOWN` whether
  the key came up; Grip reads the BIOS's shift flags; the kernel defect is
  the owner's question (O19).
- **The worst frame was priced only where no shadow is drawn.** With four
  boxes and the occluder pass it was a third over a refresh on both cards.
  The pass now decides once and lays into every box, and the shadow stays
  out of a box of its own while the ball can be hidden; what is left over a
  refresh is a fall behind geometry on the CGA, counted.
- **Smaller things that were simply wrong**: `XLAT` reads DS, not the
  part's segment; a 512-byte table the guest can build in 6 ms had been put
  in every image; the bounce chain was six bounces in 3.2 s, not eight in
  3.9; the Hop window lost Space at a Hop's own landing; and a squash was
  drawn on a ball climbing away from the floor.

Rejected or deferred, with the reason in the contract: a ground-line camera
target (it would re-prove three cameras' routes; the bob is measured
instead), a fractional drag (offered with O2 in wave 3), and a Hop that pumps
a bounce (it would carry a course's highest launch to every cell). These
are still intentions: every figure is the host model's or predicted until
the final pass.

## 2026-11-12 (late): the owner picks the camera

After wave 1 the owner played the three camera modes. **GLIDE "feels pretty
good"; FOLLOW is "no good, the most jerky"; TRICKLE is "a 'classic' style",
but slow is still jerky, so probably worse than GLIDE.** The decision: keep
GLIDE and TRICKLE as the player's choice and drop FOLLOW. That matches what
the wave-0b cadence measurement predicted - a camera that matches the ball's
speed must hop as often as the ball crosses 8 px, so FOLLOW only evened the
gaps - and the eye agreed with the numbers. Folded into wave 2 while its
build was on its first stage (SPEC.md 128.11.11.1, story 2.15).

**Two more answers the same evening.** The benchmark route: the owner had
only wave 1's, which "kind of goes in a circle a bit on a single bit of the
stage" - fine as an engine benchmark, but the real benchmark should be
**demos the owner records** once there are longer courses, so recording to
disk joins wave 4. And O8: the exact merge of occluder records is accepted
("losing nothing on screen and merging art seems fine"), with the note that
the package's size means parting it out further at some point - also wave
4, once five courses are measured.

## 2026-11-12 (wave 2, the host half)

The tools first, as in wave 1: everything the guest stages will be held to
exists on the host before a line of `bzphys.inc` changes.

**What was built.** `tools/bbcourse.py` takes `surface` and `ball`, writes
ONE part a course (the CGA's blocks; the Hercules translates them at the
fetch through a 512-byte table the guest builds, so `htab()` lives in the
host tools only as the reference), merges occluder records exactly (a
record pair no reachable position can tell apart becomes one record with
its masks ANDed), bounds them per BLOCK (4) rather than per row, sets the
new `OCCG` flag, and iterates the reach - the Hop's launch and every bounce
bounded by the energy that reached it - to a fixed point. `Physics` is
SPEC.md 128.11.8's step: the arrows' ramp, Hop with its window, Grip, half
air control, landings judged against the floor's own rate, stun, shatter,
reflecting walls with a symmetric edge test, and surfaces from a generated
force/drag/brake table. `Glide` - the GLIDE model waves 0b and 1 wrote and
threw away - is kept, with the four-frame travel test. `bonanza_assets.py`
draws three balls (rubber as wave 1's, byte for byte; steel with a seam;
glass you see the course through), each with squash frames, a shadow mask
and, for glass, a four-frame shatter.

**What the model said that the contract had guessed.** The ledge-gap table
the contract carried left the ball's radius out; generated from `Physics`
(circle included), its lower bounds are what the hand model predicted -
6-unit drop, 2 units up: 15 - 67.5 gu. The contract's "a steep down-ramp
throws" is "can throw": the take-off test sees only the first step past the
crest, and about one crossing in four at the cap goes far enough past it.
And sand takes a ball to 62 in 93 steps, not 92.

**TRIAL, and why its gap faces the viewer.** The contract asked for the gap
along a screen row first, so the flight would cross no cell that can hide
the ball. Built, it did exactly that - and the sweep passed - but the
autopilot crosses a screen row on ONE arrow, and one arrow tops out at
189 - 252 an axis (the round-up drag's dead band) where the bounce needs
256. The route fell into the gap every time. The toward-the-viewer layout
works (a 6-unit drop, a four-tile floor, a two-tile gap to a ledge two units
up, a steep ramp, ice between bumper rails, sand, a mat), and its 92
airborne steps over `OCC` cells are counted rather than hidden. Its bumper
rails stand half a unit proud: at one unit, a wall in front hides the bottom
of every rolling ball beside it, and the course was 88% `OCCG` steps.

**What moved that was not asked for.** `BENCH`'s third waypoint: with the
ramp the Hercules lost two scroll directions on wave 1's route, and a search
over the kept model moved one way line to get all eight back (at least 8
each on both cards at 0.96 - 1.04).

**Measured (host).** Parts: balls 8,256 / 8,256 / 13,376; `BENCH` 49,272,
`FIRST` 9,736, `TRIAL` 18,446. `BONANZA.O88` 45,366 with the wave-1 image -
wave 1's was 64,509 with two courses and one ball. `bbcourse.py
--selfcheck`: 100 items in about 30 s.

## 2026-11-12 (wave 2, the guest's parts and keys)

**What was built.** `bonanza.asm` fetches course `K`'s one part (row `3 + K`)
and the chosen MATERIAL's ball part (row 0 - 2) on both cards, and on the
Hercules builds the 512-byte table in the idle box buffers and translates
both parts in place before the bracket. `M` cycles the ball, `N` the course
(its ball with it), `C` the camera, each one press however long it is held;
`R` is wired to replay the log once the recorder writes one. The face names
the course, the ball and the camera.

**A decision the contract had priced the other way.** SPEC.md 128.11.3
priced the translation as an unrolled block (8 lines, about 665 clk) with a
`xor bh, 1` between tables. Two things changed it. The table lives in bss,
whose address the assembler does not know, so `xor bh, 1` toggles between
the right two pages only when the table's base happens to sit on an even
page; the shipped loop keeps the XOR of the two bases in `BP` instead, at
the same 3 clocks. And one 17-byte loop (`bz_hxrows`) serves the course's
2-byte rows and the ball's 5-byte rows, where the unrolled forms would be
about 70 bytes more for about 40 ms once at a Hercules launch - beside the
two disk reads that launch makes, at ~400 ms each. Bytes, not rungs: not
bought. A `BENCH` launch with rubber now predicts ~153 ms of table and
translation, not ~98.

**How it was checked before it ran.** The guest's own bytes for `bz_hgen`
and `bz_hxlat`, run in an emulated 8086 on the host for every course with
every ball, give exactly `bbcourse.htab()`, `herc_translate_course` and
`herc_translate_ball` - 1,806 bytes of `BENCH` and 1,965 of the glass ball
differ from the CGA's, so the check is not vacuous - and leave the box
buffers past the table untouched.

**The look (one boot a card, MartyPC, FIRST).** CGA: the rubber ball
magenta with white spots, steel cyan with a white seam band, glass a
see-through checker, each in its black rim, rolling over the course; a held
`M` (1.5 s, past the typematic delay) advanced the ball exactly once each
time. Hercules: the course's mid tones are the checker at the right parity
(no striping where a table was wrong), and the three balls are told apart by
their patterns inside the rim. The engine still draws wave 1's roll frame
and no squash, shadow or shatter; those are the engine stage's.

**Measured (host).** Image 12,624 bytes (+553), bss 5,586 (+4,096 the log,
+384 the box buffers grown to four for the table), `BONANZA.O88` 45,830.

## 2026-11-12 (wave 2, the step)

**What was built.** `bzphys.inc`'s `bz_step` is SPEC.md 128.11.8's: a key
byte a step (the arrows, Space, Left Shift); the arrows' levels ramping up
one a step and coasting down two; the Hop's six-step window, from the ground
or at a contact, leaving at `max(HOP, rebound)` so it never pumps a bounce;
Grip's brake on the ground and its catch at a contact; half-force air
control; landings judged against the floor's own rate, with the rubber
bounce, the steel stun (every velocity stopped) and the glass shatter and
its respawn; walls that REFLECT, a bumper rail at 230 for every ball; the
east and south edges tested as west and north are; ice, sand and the mat
from a generated force/drag/brake table, rebuilt when the ball's cell
changes surface; and a goal crossed in the air. `bz_input` reads Space from
the key map and Left Shift from the BIOS's shift flags, which is what keeps
a 101-key keyboard's fake shifts from reading as Grip.

**How it was checked.** The package's own bytes, assembled from the tree and
run in an emulated 8086 on the host, against `bbcourse.Physics` at every
step, comparing all of 128.11.8.1's state (the levels, the window, `kprev`,
the state and its count, the squash, `bz_gh`, the four counters, `lvz`):
the benchmark on `BENCH` and `TRIAL` with every ball, scripted plays on
`TRIAL` (the drop, the mat, the bumpers, the ice, the sand, the goal), and
200 fuzzed runs of 2,000 steps - every course plus a scratch course with
every surface, random keys with Space and Grip, random poked positions,
heights, velocities, levels and states - which put every surface under every
ball (with and without Grip), stone and bumper rebounds, 241 corners, 2,115
bounces, 542 contact Hops, 29 stuns, 63 shatters and 39 goals through it.
**One mismatch was found and fixed**: the ground force table was built from
the surface entry's BRAKE byte instead of its force (a forgotten load), seen
as a benchmark step two units fast at its second step. A deliberately broken
copy (wave 1's east edge) went red at once.

**The look (one boot a card, MartyPC, `TRIAL`, Right and Down held off the
start tier).** Rubber: off the lip, a 6-unit fall (`lvz` 768), five bounces
and onto the ledge two units up - the course's rubber-only crossing. Steel:
stunned on the floor below (`lvz` 768, 55 steps), then rolled on into the
gap and respawned. Glass: shattered there and respawned on the start tier
24 steps later. The same on the Hercules, step for step but for the frames.

**What it costs, priced from the code.** About twice what the contract
predicted: +1,431 clk a benchmark step raw (6,249 against wave 1's 4,818),
the ramp's loop and the per-axis drag and brake the most of it. An unrolled
ramp (99 bytes for 115 clk) and a flat-floor shortcut (12 bytes for 19)
were measured and not bought. Image 13,397 (+773), bss 5,646 (+60).

## 2026-11-13 (wave 2, the engine)

**What was built.** The ball now looks like what it is and where it is.
Each material's roll frames turn with the GROUND line, not the screen line,
so a bouncing ball does not spin as it rises and falls; a hard landing
squashes it for six steps (shown only while the ball is at its floor, so a
rebound climbing at 615 is round), a stunned steel ball nods two lines every
four steps, and glass breaks in four frames before it respawns. Under an
airborne ball over a floor lies a checkered SHADOW, the gap between them the
whole cue of the height. A frame now has up to FOUR boxes - the ball's old
and new, the shadow's old and new - grouped, merged when they fit, sorted by
first line and written interleaved with the entering column in raster order;
the occluder pass walks the footprint ONCE a frame and lays into every box,
and while the ball's cell can hide it the shadow is drawn only inside the
ball's own box. GLIDE's "fast" is the ball's travel over four frames, and
FOLLOW is gone, as the owner asked. A play is recorded a byte a step into
the 4,096-byte log, R replays it, and after the goal the face shows the time
and the falls, stuns and shatters.

**A rule the replay needed.** A frame used to run its remaining steps after
the goal step. The log then held a few steps past the goal, and a replay -
whose frames fall at other steps - could stop at the goal on a different
step than the play did. Now the goal step is a play's last; the replay ends
on the same step, and the face's time is that step's.

**How it was checked before it ran.** The package's own bytes under an
emulated 8086 on the host: the recorder and the player against
`encode_log`, `decode_log` and `run_log` (fuzzed keys, a run past 255 steps,
a log truncated at 2,040 runs: the same bytes, the same state at every
step); `bz_camera` against the kept GLIDE model frame by frame on both cards
at 0.5, 1 and 2.2 times the real step rate; and every frame's boxes applied
to a simulated card and compared with an independent oracle - the course,
the shadow's AND, the sprite, the occluder rule - round every footprint,
over the benchmarks, plays, fuzzed keys and drops behind geometry. Three
deliberately broken copies (no old-shadow restore, the pass laid into the
first box only, the wrong squash frame) each went red; the one-box pass
needed the drops to show it, which is why they were added. A last check ran
the column split and the box writes under emulation for nine layouts, the
static stack walker having refused the first form (a `POPF` inside the box
loop).

**The look (one boot a card, MartyPC, `TRIAL`).** CGA: rubber off the lip
with its shadow under it, the bounce chain carrying it across the gap,
glass cracking, bursting and gone, and R replaying the glass run to the same
step, position and counts as the play. Hercules: the same, with rubber's
squash at its first contact and steel's squash on its stun. No box was late
on either card. The glass's last two shatter frames are nearly invisible on
the Hercules: its see-through pieces are the course's own checker there.

**What it costs.** Image 14,076 bytes (+679, net of about 540 bytes of
FOLLOW deleted), bss 5,804 (+158), `BONANZA.O88` 47,254. Every box on a
frame that is not a full write is now timed against the beam at both ends,
about 0.8 - 1.0k clk a box the contract had not priced; the final pass
measures it.

## 2026-11-13 (wave 2, the review's fixes)

Four reviewers read the built wave against SPEC.md 128.11 - the picture, the
physics, the cost and the OS boundary - and fourteen findings came back.
Everything below was checked on the host only; no emulator row ran.

**The picture.** Glass's burst and spread had lost the black rim the whole
design rests on: a shard on a cyan tile was cyan on cyan, and on the
Hercules the course's own checker. The tool now outlines every piece in
black AFTER the clip to the footprint at each shift, and each glint of the
last frame is white on a black cross. The asset check had only looked at the
crack; it now checks every shatter entry at every shift, and a new negative
control (one burst ring pixel made cyan) is caught by that check alone. The
shatter's 24 steps and 6 a frame, typed into `bz_sprite`, are now generated
by `bbcourse` and guarded against the ball part's frame count.

**The cost.** The engine had priced its frame at its first prediction, and
the code was dearer: `bz_mkboxes` about 1.6k raw more than wave 1's on a
one-box frame, `bz_sprite` about 0.6k, and every box timed against the beam
in every mode, about 1.65k a box that only the benchmark ever reads. A
pricer that traces the four frame routines under emulation (in the session's
scratch) gave the A/B for each fix:

- the occluder pass gated by `OCCG` for a GROUNDED ball (sound by the flag's
  own definition): `TRIAL`'s gated frames 960 -> 138 of 1,093 autopilot
  steps, its four frame routines 13.28k -> 11.73k raw a frame;
- the box timing only on a benchmark's measured frame or a harness's poke
  (`bz_tpoke`, which the ring's row-0 probe now sets);
- the shadow's whole rows written by words, about 1.0k a shadow box;
- the sprite's multiplications by constants as shifts (only about 50 clk a
  frame on the pricing: bought for the composer's no-MUL rule);
- `bz_tcmid`'s two marks gone, so a frame's marks do not grow with its boxes;
- the wall restitution's `MUL` skipped when the answer is 0 by arithmetic.

128.11.15 now carries the frame priced from the code and the busy restated
from it: about 43 - 43.5k on the CGA (54 - 55%), which puts `BENCH`'s
"dying behind an edge at the bounds" frame at about 1.01 refreshes in the
benchmark. That is a prediction for the final pass to measure, not a claim.

**The OS.** The two part fetches now store their segments before the next
fetch, so `tests/pins.txt` keys each claim by its own word (`bz_cseg`,
`bz_bseg`) and `t_pins` passes again. The `overswallow` red arm could not
reach its own check (a wait raised first); the held-key test now looks after
a fixed guest interval and records a guard that never cleared as a failure
of its own. `bonanzaexit`'s and `bonanzaphys`'s `secs` are re-predicted from
wave 1's per-launch time (130 and 150).

Image 14,153 bytes (+77), bss 5,805 (+1), `BONANZA.O88` 47,302.

## 2026-11-13 (wave 2, the final pass)

Every row ran once as one scoped soak call (`bonanzacourse`,
`bonanzaassets`, `bonanzaring`, `bonanzaperf --ab`, `bonanzaphys`,
`bonanzareplay`, `bonanzaexit` on MartyPC, `bonanzamega` on 86Box). Four
passed and four failed. Each failing row was diagnosed, fixed and run
again on its own, then all 27 red arms ran once, and the last batch of
fixes was followed by one more scoped call over all eight rows: **eight
passed** (159 s, three MartyPC lanes). What the failures were, all
measured:

- **The guest: a row-0 box after a sync already high.** The ring's
  row-0 probe on the CGA reported its FIRST box late on 2 of 11 frames.
  MartyPC's cycle counter, read at `bz_t0` and at the retrace wait, gave
  the cause. Every probe frame (an entering column, a refill on every
  other frame, a two-box compose and two catch-up steps) spent 42 - 44k
  clocks before the wait, against the 39.6k left after the last frame's
  writes. Most frames missed the rise and waited a whole refresh (112 -
  120k from `bz_t0`), but two arrived inside the 16-line pulse. There
  `bz_latechk` has to reckon the sample as the sync's END, which leaves a
  16-line box no lead. Wave 1 met the same shape and moved the probe;
  this time it is the guest that changes: on the CGA, with a row-0 box
  pending, `bz_vr` lets a sync it finds already high go and takes the
  next rise. The frame is a refresh late, a counted miss, and never a
  box written behind the beam. +47 bytes (14,153 to 14,200). Measured
  after it: 36 CGA probe boxes timed, the guest's verdict and the cycle
  counter agreeing on all 36.
- **The rows, five slips, none in the package.** `bonanzareplay` kept
  the boot context instead of the UI it yields; it and `bonanzaphys`
  pressed R on a paused machine, so `wait_stop` answered with the pause
  itself; the record leg's last resume raced back into a breakpoint it
  had not yet cleared; and both rows' runaway bound (steps + 50 frames)
  failed a correct 550-step replay, which the CGA's 0.911 steps a frame
  stretch to about 604 frames. `bonanzamega` looked as if the physics
  had stalled after Space (19 steps in 120 frames). It had not: 86Box
  paces the Hercules' retrace nothing like a real card, about nine
  frames a step, so a Hop held for 4 frames fell between two steps. The
  row now holds keys for steps.
- **TRIAL never draws three boxes.** Measured over 1,200 frames on both
  cards: 0. Its shadow's line jumps only over `OCC` cells, where the
  gate keeps the shadow out of a box of its own, and the ball never
  moves fast enough to split its own group. The ring now MAKES the
  frame: the ball poked airborne across the window over an `OCC`-clear
  cell, and that frame checked against the oracle (frame 301 on both
  cards).
- **Two red arms could not go red.** `shadow` stayed green on the
  Hercules because no checked frame had the shadow inside the ball's
  box, which is the only case it breaks; the ring now checks those
  frames (6 on the CGA, 4 on the Hercules). `late2` stayed green
  because the probe's shadow box sits about 150 px below the ball (the
  floor under world line 0 on `BENCH`), 30k clocks ahead of the beam,
  so no later box was ever late. The probe now splits every other frame
  from the seventh (the ball 40 px back, so two boxes at row 0): 7 later
  boxes late by both verdicts on the CGA. Both arms then went red. 25 of
  27 arms went red at their own check the first time. `shiftmap` cannot
  be judged on 86Box: its keyboard sends no fake shift, and an explicit
  E0 2A through its automation (tried) never reaches the map.

The numbers, MartyPC, `BENCH`'s benchmark against wave 1 built out of
git (`2df3f469`): busy **42,485 clocks, 53.4%** of a CGA refresh (wave 1
37,043, 46.5%) and **42,805, 45.5%** of a Hercules one (36,842, 39.2%),
0 misses on either card. The contract predicted 48.0 - 48.6% and 40.7 -
41.3%; the review's repricing from the code, 54 - 55% and 46 - 46.5%,
is what the machine did, a little under. Sim + camera +2.5k and +2.9k,
the box compose +1.2k, the box write +1.6k (the per-box timing on the
benchmark's measured frames). `TRIAL`: 40% and 34% busy (61% of its
frames draw nothing), but 8 misses on the CGA and 2 on the Hercules.
Six of the CGA's and both of the Hercules' are the fall and the flight
over `OCC` cells, which the fallback layout allows. Two are the GROUNDED
roll down the steep ramp, with GLIDE panning two rows a frame, which
nothing allowed for; they are reported in 128.11.15 and the course is
the owner's to tune. Sizes: image 14,200 (predicted about 15,100), bss
5,805 (5,700), the region 19,968 (21.0KB), `BONANZA.O88` **47,334**
against wave 1's 64,509 (predicted 47 - 51KB).

All of wave 2's stories are ticked, and wave 1's 1.3 with them (closed
by 2.2's merge and per-block bounds). The one verification left undone
is the fake shift on a real 101-key keyboard (2.4, 2.12).
