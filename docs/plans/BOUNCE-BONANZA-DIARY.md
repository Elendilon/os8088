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

## 2026-11-13 (wave 3, the lanes and the wheel in the guest)

The guest half of SPEC.md 128.12.4 and 128.12.5, in a new file,
`apps/bonanza/bzwheel.inc`, with the frame loop rearranged round it:
`bz_t0` now runs `bz_foot` (the ball's screen state and its new
footprints, moved out of the camera and the box layout), `bz_props` (the
walk), then the camera; the wheel commits between the new mark `bz_tw` and
`bz_tv`; the LEAD follows the column and the boxes. Observations, not yet
the final pass:

- **A lane is map words, and that held.** Every writer that reads the map
  drew the drawn pose with no change of its own. A host emulation of the
  package's own walk, lane writer and wheel (unicorn, a simulated card, a
  fake PIT) wrote 400 random commits a card - windows round each lane,
  steps up and down, left and right - and the card came out exact: every
  shown cell and every entering-row cell from the map, nothing else
  touched, including rows that cross the 8KB ring's end.
- **The first lane writer called the row writer once a card row.** It was
  correct and cost about 13.8k clocks for a rotor on the CGA (the look
  boot's calibration), against 9.2k predicted: nine pushes and pops, the
  row multiply and the set-up, twelve times. Its own loop - the map entries
  read once a card row, the line in the block stepped by 2 rl bytes, the
  masked path only for a row that crosses the ring's end - cut the
  emulated cost by about a third. The Hercules's look, with the new writer,
  calibrated a rotor at 2,535 counts (10.1k clocks); its fixed part, about
  3.0k clocks, is twice the prediction.
- **The calibration timed the wrong span at first.** The wheel decides on a
  clock sample and then does arithmetic before the commit starts; the
  calibration timed only the commit. On the emulated Hercules that put one
  commit 14 counts past AHEAD's two-line guard. The calibration now times
  from a sample through the same reckoning (`bz_wnow`) to the commit's
  closing sample.
- **GLIDE's heavy rule matches the model to the frame.** The package's own
  camera, run frame by frame under emulation with the card oracle of wave
  2, agreed with `bbcourse.Glide` and its `Heavy` on `BENCH` and `TRIAL`
  with all three balls and at 2.2 times the step rate, on both cards, and
  with `bz_hvoff` set it is wave 2's camera exactly.
- **The look boots.** `MILL` chosen with N twice on the desktop. On the
  CGA, 819 frames: the two rotors through all eight poses, 153 commits,
  one overrun, the card equal to the window drawn from the guest's LIVE map
  on all 190 frames checked (outside the ball). On the Hercules, the ball
  poked to the windmill's doorway: 27 contact frames drew the rotor in the
  ball's box, and the card matched the live map on all 183 frames checked.
- **What is not there yet.** The windmill's gate, the bumpers' kicks, the
  tubes and the platform are the physics stage's: `bz_wol`, `bz_pkick` and
  `bz_tube` are declared and read, and nothing writes them, so no rotor is
  ever must-draw and no post ever lights. The slab's line is tracked and its
  box is laid out, but nothing draws the slab yet.

Sizes: image 18,373 bytes (14,236 at this stage's start: wave 2's 14,200
and `MILL`'s rows in the course tables), bss 6,121 (5,805); `bzwheel.inc`
alone 3,920 bytes against about 2.1KB the contract priced for these parts.

### Wave 3, the obstacles' physics (SPEC.md 128.12.6)

The windmill's gate, the tubes and their ghost, the bumpers' kick and the
platform's carry went into `bzphys.inc`, step for step against
`bbcourse.Physics`.

- **Two tests a step, kept by writing the step twice.** The contract says a
  ball with no prop near pays two byte tests a step and nothing else. The
  doorway's hooks sit inside the edge tests, and the slab's and the post's
  floors inside step 6, so a hook there would have been a third test on
  every step. Steps 4 - 6 became three NASM macros instanced twice: wave 2's
  path, which assembles to the same instructions as before, and the PROP
  path with the hooks. That costs about 700 bytes and removes the risk that
  the two paths drift apart. Priced from the code, `BENCH`'s step went from
  5,999 to 6,055 clocks: exactly the two tests.
- **The carry happens before the forces.** In the contract the carry is the
  first part of step 3's move. The guest's forces read only the window, not
  the position, so the carry runs where the step-1 test already branches,
  and adding a third test was unnecessary. The fallback's undo still returns
  the ball to the position before the carry: the prop path subtracts the
  displacement from the saved start.
- **Unicorn agreed on the first run.** The package's own `bz_step`, emulated
  on the host, matched the model on every state variable at every step:
  `MILL`'s autopilot for all three balls; the gate from every phase of both
  windmills; the house-front approach; each tube at four entry speeds for
  all three balls; post approaches from eight directions at four speeds;
  drops onto and beside the posts; ride, Hop, drop, under, roll-off and
  boarding across the platform's period; the drain's and the doorway's
  touch at every 1/256 px either side of `BZ_CLIMB`; 60 fuzzed runs near the
  props and 30 on the slab; a synthetic course with the platform beside
  walls, a raised post and a cluster; and an undo with a poked carry. The
  harness was tested by breaking the guest on purpose. Eight broken copies
  (the gate's window, the carry, `KA`, `bz_onp` on a take-off, KEEP's
  direction, the post's top, the drain's height, the undo's carry) each
  produced mismatches. Two of them did so only after targeted scenarios were
  added: the drain needed the z-boundary sweep, and the undo needed the
  poked carry beside a wall. One more broken copy stayed green, but it
  cannot change MILL: a platform owning cells two diagonals off its track
  has no such `OBS` cell to own there.
- **The model moved twice, harmlessly.** The doorway's knock-back now reads
  the record's `eG` (160, as the constant was), and the slab's floor keeps
  the track cell's surface, which is NORMAL everywhere. The guest reads the
  surface from the window's centre, so the model and the guest now agree by
  construction instead of by course content.
- **The prop path costs more than priced.** A prop-path step is about
  7.6k raw against wave 2's 5.4k on `MILL`. A carried step is 7.9k, after a
  one-entry cache for the platform's position, a kind byte per `bz_wol`
  pair and a faster `bz_lrecsi` brought it down from 10.2k. The contract
  priced 0.2k plus 0.34k a post.
- **The look.** On both cards: a windmill capture whose first touch fell on
  an open gate, the ball hidden and the camera gliding after the ghost, the
  KEEP exit, a knock-back at the other windmill, a kick on the green, the
  DROP chute's fall and bounce, and the cannon's flight onto the goal ledge.
  A second boot per card covered the ride, because the first ended at the
  goal: the ball was carried exactly 48 gu along each axis, `PMAX`, from the
  home dock to the far dock. The slab itself is not drawn yet. That is the
  compose's work, as the previous entry says, so the ball rides over a black
  moat.

Sizes: image 18,373 -> 21,387 bytes (+3,014, of which the props' physics
2,865), bss 6,121 -> 6,160, `BONANZA.O88` 64,597 -> 66,501.

### Wave 3, the slab on the glass and the engine's last pieces (SPEC.md 128.12.4.3 - 128.12.4.5)

The previous entry ended with the ball riding over a black moat. This stage
drew the slab and checked the rest of the frame's new rules: the contact
box's four-box limit, the heavy camera, the face's course list and the
replay's identity check were already in the tree and were read against the
contract rather than rewritten.

- **The slab is a layer, not a lane.** Every box that meets its drawn
  footprint composes it: under the ball after the course, or over it after
  the occluders, by one decision a frame (`bz_povr`: below the slab's top
  and not in front of its row). Three things put it on the card: its own
  box when its line changes while it is shown, its box after a full write
  (`bz_pfull` - the first version left that to the next frame, and a host
  check with the slab expected at its TRUE line, rather than at the guest's
  drawn one, caught the gap), and a box clipped to the cells a scroll brings
  in (`bz_pstrip`). The Hercules gets its pixels from the fetch's
  translation, a parity copy per line, like the ball's squash frames.
- **One slot, two claimants.** The contract said the contact group is one
  lane or the slab's box, and did not say which wins when a contact lane and
  a strip meeting the slab fall on one frame. Under GLIDE they cannot (a
  contact lane's frame scrolls nothing), but TRICKLE scrolls whatever the
  heavy rule says. As built the lane yields: its map words go back to its
  drawn pose and it waits a frame, as a second lane touching the ball
  already does. SPEC.md 128.12.4.3 now says so.
- **Checked by emulation, broken on purpose.** The package's own frame code
  ran under unicorn on `MILL` against an independent card oracle: rides
  from five phases of the slab's period, Hops, a ball under the slab (the
  slab over it), the ball rolling away and back, a camera driven across the
  slab and back in four patterns, and random keys, on both cards and both
  cameras. Four broken copies (no clipped box, the slab always under, no
  box at a full write, no layer under the ball) each failed it, and a
  forced contact lane on a strip frame showed the yield.
- **The slab's layer was slower than priced.** A byte loop cost about 10k
  clocks a slab against the 5k the contract allowed. A box exactly the
  slab's width - its own, and a ball riding it - now takes the rows as one
  run of words, about half.
- **A hidden ball is never idle.** The idle test compared the ball's
  position; a ghost whose first screen position equalled the ball's last
  would have left the ball drawn while it was in the tube.
- **The look.** One boot per card: `MILL`'s autopilot end to end (the
  rotor drawn on its must-draw frame before the capture, the transit, the
  kicks, the platform beside the route), a play with the ball put on the
  docked slab and carried to the far rim, and `TRIAL`'s benchmark under
  GLIDE. The card equalled the live map with the slab composed on every
  frame checked (440 and 330 and 200 on the CGA, 473, 330 and 200 on the
  Hercules). What the look also showed, for the final pass to measure
  rather than for this stage to argue: `MILL`'s autopilot missed refreshes
  on the platform's box frames (128 on the CGA and 44 on the Hercules, before
  the word path), the wheel overran once and let lanes wait 8 frames
  (`bz_wover` 1, `bz_wlate` 7 and 4, which the final pass asserts at 0), and
  `TRIAL` with the heavy rule missed 18 and 7 against wave 2's 8 and 2, the
  Hercules's on light frames that caught up a withheld column and two rows
  together.

Sizes: image 21,387 -> 22,235 bytes (+848: 729 of routines, the rest hooks
and the Hercules translation), bss 6,160 -> 6,179, `BONANZA.O88` 66,501 ->
67,205. The contract priced the slab's drawing and translation at about 310.

### Wave 3, the owner's preview: seven fixes (SPEC.md 128.12.16)

The owner played a preview of the wave on 86Box (a 5150 with the CGA) before
the rows ran. "Most of this looks very good." Then four defects, a tuning
ask and two things about the platform. What each turned out to be:

- **The windmill had no door out.** A windmill's tunnel is its house, so
  its exit got neither a plain tube's rim nor a mouth: the ball came out of
  a blank wall. Its house face now carries the doorway's arch where the
  ball leaves (when that face is one the viewer sees).
- **The bumpers rarely lit.** The lit pose lasted six physics STEPS, and a
  post touching the ball waits whenever the frame is busy; by the time a
  frame could draw it the post was dark again. The lit time is now the
  display's, counted in frames that actually showed it (8), and a post
  lighting is drawn whatever the frame. The look: every kick lit on its own
  frame, for 26 and 75 frames on the CGA and 10 and 10 on the Hercules.
- **The chute's ball came out above its door.** The mouth was drawn at the
  foot of the wall, on the tier's floor line; the ball leaves 3 units up.
  The mouth's sill is now the exit height, and the tool checks that the
  ball at the exit stands in it.
- **The tube blocks were missing a piece.** The chute's wall stands on the
  lower tier with the void beside it: one face reached the tier, the other
  hung the standard 3 units over the void, so the column had a bite out of
  it. A tube wall's void face now reaches as deep as its other face.
- **More push.** `K` 320 -> 384, the axis cap, +20%. The `kick` replay now
  comes in diagonally, because along an axis the cap hides the rail's floor
  and its red arm could no longer part from it.
- **The ball rolled on the lift, and falling into the lift killed it.**
  Both have one cause, and it is the projection's: a slab sliding along
  `+s` and a slab moving straight down are the same picture. The owner saw
  a LIFT. As a slide, the carry moved the ground line the roll frame reads
  (so the ball turned), and a ball rolled off the near rim fell behind the
  slab into a moat and died before it reached the slab's picture. So it IS
  a lift now: one shaft cell, the slab moving in `z` between a low rim and
  one six units over it, the shaft's kill under the low top. A ball riding
  it keeps its roll frame (the frame never reads `z`), and a ball falling
  down the shaft lands on the slab wherever it is. The guest got SMALLER
  doing it - no square test, no track scan, no start correction (-147
  bytes of physics) - while the lit posts cost 57 and their yield to a
  strip 21: the image 22,235 -> 22,218 bytes, bss +50.

How it was checked: the guest's own `bz_step` under an emulated 8086
against the model at every step (`MILL`'s autopilot with each ball, the
lift's rides, Hops and drops at every phase, boarding from both rims, and
fuzz on a second lift course with a wall beside its shaft) - integer-exact;
`--selfcheck` with new items for the mouths, the columns, the lift and the
lit posts, each with a negative control built from what the preview showed;
and one look boot a card. The rows are the final pass's.

### Wave 3, the review: what four readers found (SPEC.md 128.12.17)

Four reviewers read the built wave with different questions - what reaches
the glass, what physics does, what it costs, and what the OS sees - and
returned 22 findings. Every one was checked against the code and every one
was real. The ones worth remembering:

- **A box is a UNION, not a footprint.** The walk decided which due lanes
  the wheel could take by testing them against the ball's footprints. But a
  frame's boxes are unions - the old and new footprints together, the
  shadow merged in, the contact merged in - composed before the wheel and
  written after the flip. A post in the corner of a union but outside both
  footprints was committed lit-to-dark by the wheel and then partly painted
  back lit by the box. The wheel now drops a candidate that meets any of the
  frame's boxes; it stays due, and the box has drawn its drawn pose.
- **The slab could leave a stripe behind.** The walk asked only whether the
  lift's TRUE footprint was on screen. When the lift sank out of a resting
  window, its last drawn lines stayed. Now the drawn footprint counts too. A
  scratch harness with the camera parked and the lift crossing the bottom
  edge showed it: red with the old rule, green with the new.
- **A lighting post could overrun a buffer.** The owner's fix made a
  lighting post outrank everything but a rotor - including the lift's box,
  which cannot wait: two frames of catch-up is more than 24 lines, and the
  box buffer is 24 lines. The reviewer's fix was to put the lift first. That
  would have starved a post next to a moving lift for the whole ride - the
  very complaint the owner had just made - so both are drawn: the post is
  the contact, the lift's box a second rectangle (merged into a neighbour
  when it fits), and only on a frame with no room does the post wait one.
- **The wheel could make its own frame late.** It prepared each candidate
  (about 4k clocks) before each test, and only its entry looked at the
  deadline. Now every candidate is prepared once, before the entry test,
  into a slot; every test first stops the wheel when even the cheapest
  candidate would not fit; and a test and its commit are one critical
  section, so no tick can land between "it fits" and the first write.
- **The identity was a plain sum**, so two windmills with their seeds
  swapped had the same identity and a log would replay a different run
  without complaint. It is a Fletcher pair now, and the swap is the
  self-check's negative control.

The image grew 745 bytes (22,218 -> 22,963) and bss 307 (six wheel slots,
the walk's per-lane tables and the lift's second rectangle). The walk's own cost fell from the review's
8 - 11k clocks a `MILL` frame to a mean of 3.9k (CGA) and 4.5k (Hercules)
on the host's instruction pricing - still about twice what 128.12.11
predicted, which the final pass will measure on MartyPC.

How it was checked: the physics cross-check again (integer-exact over
`MILL`, the lift, fuzz and a second lift course), the scratch harnesses for
the walk, the wheel's beam and deadline, the lead, and the frame code
against an independent card oracle (100 lift scenarios and 900 frames of
`MILL`'s autopilot a card), plus one negative control per picture fix. No
row ran; they are the final pass's.

### Wave 3, the final pass: what the rows measured (SPEC.md 128.12.18)

The nine rows ran once as one scoped soak call on MartyPC (and 86Box for
kern_mega), after a first attempt at this pass was cut off by a container
restart part-way through. Eight passed. `bonanzawheel` still fails one
check on the CGA. What the rows found, and what changed:

- **The wheel could not keep up on `MILL`.** On the benchmark, a rotor's
  pose was late 8 frames running eight times on the CGA and four on the
  Hercules, and only 69% and 84% of a rotor's poses ever reached the glass.
  A diagnostic run that logged the wheel every frame showed why. A rotor's
  commit costs about 13.4k clocks on the CGA (the prediction was 9.2k) and
  preparing it about 7.2k. Where the lift moves in view, frames are 93% busy
  on the CGA, so the retrace wait has no room for a commit. The fix is a
  rule, not more speed: a lane the wait has not taken in 3 frames takes the
  contact slot (a box) when the frame allows one, or in 5 frames on any
  frame. The lift's box gives that frame up, for one frame at a time. A
  bug came out with it: a lane drawn by a box kept counting its age, so its
  next pose started "late". After both, no lane was late on either card,
  and 92 - 97% of the rotors' poses reached the glass.
- **The route never exercised half of the wheel.** `MILL`'s rotors stand
  near the course's top, so they are always high in the window, and its
  frames are heavy. The wheel therefore never committed ahead of the beam,
  never made a LEAD, and on the CGA never committed a 2-word post. A
  scripted scene now does those: a post placed low in a centred window,
  the ball held still above it, the post lit and darkened every 6 frames.
  Both `bonanzaring` (as a phase of its poked play) and `bonanzawheel` (as
  a new leg) run it. On the CGA it gave 3 commits ahead of the beam and 3
  LEADs; on the Hercules, 3 ahead and 4 behind. The card matched the
  oracle on every checked frame.
- **The replay recording got stuck.** The recorder steers the ball with an
  autopilot that heads for one waypoint at a time. In one run a kick
  carried the ball past a waypoint without touching it, and the autopilot
  then pinned the ball against a wall for 750 steps, never reaching a tube.
  The recorder's own copy of the autopilot now skips to the next waypoint
  after 30 frames of the ball not moving. The game's autopilot is
  unchanged.
- **The A/B leg's one miss was not caused by the engine.** On the frame
  that missed, wave 3 ran two physics steps where wave 2 ran one. Each
  build decides how many steps a frame runs from its own timing, so the
  two benchmarks land their two-step frames on different frames. Wave 2's
  version of that frame had only 3.4k clocks to spare even with one step.
  The leg now reports such a miss instead of failing on it; any other miss
  still fails it. Wave 3's own cost on `BENCH` is +2.1k clocks a frame on
  the CGA and +1.9k on the Hercules.
- **The corner check never runs on the CGA, and cannot run on the
  Hercules.** The Hercules's 45-word window always holds every `MILL`
  lane's columns, so no lane can straddle its edge. That check is now
  reported there, with the reason. On the CGA, the frames that scroll
  diagonally reach the wheel 79 - 98k clocks after the retrace starts,
  against the about 54k a post's commit needs. So the wheel skips them, and
  the lane goes out in a box three frames later. This is the one check
  still failing; it needs either a cheaper commit or a course built to
  test it.

Measured against the predictions:

- **`BENCH`:** busy 44.6k on the CGA and 44.8k on the Hercules, against
  44.3k and 44.6k predicted.
- **`MILL`:** busy 50.7k and 52.3k, against 46 - 49k predicted. It missed
  111 refreshes on the CGA and 13 on the Hercules, almost all of them on
  the lift's stretch. Frames that draw the lift's box measured 93% busy,
  as predicted, but the ride's frames where the lift's line changes
  measured 120% against the 94% predicted.
- **`TRIAL` with the heavy rule:** more misses than wave 2, not fewer (14
  against 8 on the CGA, 9 against 2 on the Hercules). Open question O28
  stays open for the owner, and O30 (the lift's cost) now has numbers.
- **Sizes:** the image is 23,227 bytes (17.9 - 18.8k predicted), bss 6,542,
  and `BONANZA.O88` 68,235 bytes, still on one 360KB floppy.

## 2026-11-13 (wave 3b, the performance round)

Wave 3b added no obstacle. It went after what wave 3's final pass had
measured: the lift's frames, the wheel's commit, the heavy rule's effect on
`TRIAL`, and six red arms that never met their case. SPEC.md 128.13 is the
contract; the sound (128.20), built by another session on the same branch,
had landed first, so every target was measured with the sound off and on
instead of through a harness pad (128.13.15).

What was built, in four stages and a review round:

- **The ride box.** A ball riding the lift and the slab are now one box of
  up to 32 lines, composed once. The box buffers grew to 32 lines (+256
  bytes of bss).
- **The slab's wait.** On a crowded frame (the ball's and the shadow's
  groups two boxes) the lift's box waits one frame - never two running,
  never under a ball it carries, never as it leaves the window. A post
  kicked on such a frame lights at once.
- **The box writer's whole-row path.** A 3- or 4-word box with no overlap
  band is written a card row at a time by unrolled moves.
- **The wheel's commit.** One column-major pass from the pose map replaces
  the raster-order lane writer; per-lane tables cut the preparation; the
  walk skips a rotor until its next pose change.
- **The heavy rule.** Level 1 keeps only its slab-near-edge clause.
- **The step.** The physics step's two copies of steps 4 - 6 became one
  (-560 bytes of image, -48 in the packed file).

### Wave 3b, the final pass: what the rows measured (SPEC.md 128.13.16)

The eleven BONANZA rows ran as one scoped soak, then every red arm once.
Ten rows pass. Two things still fail, and both are written down with their
numbers rather than eased.

What the runs found, and what changed:

- **The wheel overran once a run.** About one `MILL` benchmark in two
  ended a commit just past its deadline, on either card. The cause was a
  price about 1% short: the calibration times its own path from a clock
  sample to the commit, and the wheel's real path from its test runs a
  little more code. The calibration now adds those 50 PIT counts (3 bytes).
  No benchmark has overrun since.
- **The row timed some commits wrongly.** The wheel row's LOW leg did not
  log the clock sample a commit's test is made on, so its posts looked 16%
  cheaper than their price. It logs it now, as the benchmark leg does.
- **No route crosses the ring's end.** The card's ring is anchored to the
  world, so only a few places put a box's whole row across the 8 KB end,
  and none of the three benchmarks passes one. The `MILL` play now ends in
  a scene that holds the ball at such a place. The first place it picked
  showed nothing when the red arm broke the writer: the red swaps two
  lines' crossing words, and that ball's two lines were alike there. The
  scene now prefers places where the lines differ, and the red goes red.
- **Three red arms needed their scenes adjusted.** `contact` now runs the
  play as well as the benchmark. `litsteps` had been swallowed by an
  exemption meant for the LOW leg's own pokes. `halfcal` runs on the CGA
  only, because no Hercules commit comes within its error of the deadline.
  All 63 red arms then went red at their own check.

What still fails:

- **The corner check (6) on the CGA.** The light corner step never gets
  its commit in. The lane sits at the window's bottom, so the wheel can
  only commit it before the beam reaches it - by 67.3k clocks after the
  rise - and the step frame's test lands near 65k with a 7.9k commit to
  go. The scene cannot shed what makes it the case (the row, the ball's
  box, the due lane). The wheel's preparation runs 10.9k from its mark to
  its test, about twice what it budgets, and that is the lever.
- **`BENCH`'s A/B target.** The SPEC asserted 2.0k clocks a frame less than
  wave 3 on the CGA; the measurement is 1.3k. The new box writer saves
  1.4k, as built, but `BENCH`'s boxes are 3 words wide, where the unrolled
  rows save about 80 clocks a line rather than the 160 the prediction took
  from a 4-word line.

Measured against the predictions:

- **The ride's line-change frames:** 83% of a refresh on the CGA and 71%
  on the Hercules, against 80% and 70% predicted, with no miss.
- **`MILL`:** the CGA's misses fell from wave 3's 111 to 47 and its 95th
  percentile from 90k to 81k clocks. The CGA's lift stretch with the ball
  beside the lift missed 6 - 9 refreshes with the sound off (15 - 20
  predicted) and 48 with it on; that is O33's question for the owner.
- **`TRIAL`:** 5 - 8 misses on the CGA and 4 on the Hercules, against wave
  3's 14 and 9; the heavy rule no longer makes it worse.
- **The wheel's commit:** 8.9k clocks for a rotor (7.0k predicted, 13.4k
  in wave 3) and 6.6k for a post.
- **Sizes:** the image is 27,362 bytes, 23,706 without the sound - 479 more
  than wave 3, where 206 fewer was predicted. `BONANZA.O88` is 77,275
  bytes, still on one 360KB floppy.

### Wave 3b, the verification: what a second reader found (SPEC.md 128.13.17)

An independent verifier rebuilt everything from clean, ran every host gate
and every row's `--check`, and looked at both cards. Nothing it checked was
broken. It still failed the round, on eight points, and they sort into
three kinds.

- **Two ticked stories claimed more than the record showed.** Story 3b.5
  promised that the CGA's wait would hold two rotors. Its own measured
  paragraph says one rotor and a post, because a rotor's commit came in at
  8.9k clocks instead of 7.2k. The story is unticked now, and its note says
  what it did deliver: the preparation hit its 5.3k target. Story 3b.7
  asked for every missed frame of the lift stretch to be written into the
  SPEC. They were in the row's log, not the SPEC, so the SPEC now has all
  59 of them, each with its parts, boxes and steps.
- **The missed frames showed something new once they were in a table.**
  With the sound on, 45 of the CGA's 48 lift-stretch misses would still be
  over a refresh without the sound's own time. One late frame leaves the
  step clock owing the next frame a second step, and that frame then
  misses too. The sound starts the chain; the two boxes keep it going.
- **The results face lost a line on the CGA.** The sound added its line to
  the face, and the CGA window holds 13 lines, so the last results line
  fell off the bottom. The results' first line now goes where the adapter's
  name was and names the adapter itself (`CGA: frames 1200  59.6 Hz
  misses 6`), which brings the face back to 13. That cost 63 bytes. A
  redundant test in `bz_hv1` gave back 4.

Two findings are reported and not fixed. A lane waited 8 frames once on
the CGA's `MILL` play with the speaker on. This stage's look boot drove the
same route and could not repeat it, because the sound shifts the timing.
The code shows how it can happen: one contact group a frame, and three
kinds of group that go ahead of a waiting lane. Changing that order needs
a scene that reproduces the case first. And `TRIAL` on the Hercules
misses 4 frames, where about 1 was predicted. All four are on the steep
ramp, with the heavy rule off as the story requires.

The corner check, the `BENCH` A/B target and the image's size stay open,
as the final pass left them.

## 2026-11-13 (wave 4, the contract)

SPEC.md 128.14 was written before any code, from four questions. What is
a game here? How does a clock get onto a card with no split screen? What
does a demo on the disk have to survive? And does the package have to be
split up?

**Decided.** A game is a TOUR of the five courses after `BENCH`, raced
for time against par. There are no lives, because a fall that cost a
life would turn the owner's D4 mechanic into a thing to avoid. A fall
costs the way back from the last checkpoint flag instead, and each flag
names the ball a respawn there gets, so no flag can respawn a ball that
cannot finish. The scorecard is the desktop face, and the best times are
kept in `SYSTEM\APPDATA` on the package's own disk through the OS's own
include, keyed by each course's identity. A demo file is the log's own
bytes. It is saved and loaded through the Standard File dialog, refused
by its size before any read, and checked field by field in a transient
claim, so a bad file cannot damage the session's own log. The package
stays one file with a lazy part a course: about 134 of the 360KB floppy's
354 clusters, predicted, with six courses, five demos and the save folder.

**Measured** (MartyPC, scratch scripts, not rows). First, the box
compose's fill and the box writer, by box size, over `BENCH`'s 1,200
frames on both cards. A 3-word box at 16 lines fills in about 4.5k clocks
and writes in about 4.8k. The useful part is the fixed cost: about 1.6 -
2.1k for the fill and as much for the write, whatever the box's size. A
2-word clock panel that follows the camera therefore costs about 8 - 11k
on every frame the camera moves.

Second, after the review asked for it: every frame of `MILL`'s and
`TRIAL`'s benchmarks on both cards, sound off and on, with its busy, its
rows and column, and whether the heavy rule held it. The legs' miss counts
agreed with the 3b final pass's within a run's spread. The log showed where a clock box would land.
Half the CGA's two-row frames already miss, and with the speaker on so do
half its one-row frames. Played over the log, a clock that follows the
camera adds about 21 - 24 misses a `MILL` leg on the CGA and 10 - 11 on
the Hercules. A clock that hides while the camera moves (REST) adds 0 -
3, and it is still shown on two thirds of the frames or more. The first
draft had kept the following clock on the Hercules because its refresh
has about 15k more room. The log said the Hercules doubles its `MILL`
misses that way, so both cards now default to REST.

The same log tested one idea and threw it out. Letting GLIDE pan only
one row a frame on the long descents was meant to rescue `SUMMIT`'s
two-row frames. On the log a two-row frame misses because of everything
on it, not its second row, and splitting it into two frames predicts more
misses on the CGA, not fewer. `SUMMIT`'s predicted misses are accepted in
writing instead, and the shipped demos will measure them.

**The review** (forty-nine findings on budget, the OS and the game) changed
more than the numbers. The HUD's box buffer had been sized at its own
width, and every box buffer in the package is laid out at a fixed stride,
so it would have overrun. A lane under the clock would have been drawn
only inside the clock's opaque rect, so its visible cells would never
have been drawn. The save folder is not created by the OS's include, and
`bonanza360.img` did not have one, so best times would never have been
written. The Save and Open dialogs move the program's folder, and the
package reads its own parts by name in that folder, so the next launch
after a save elsewhere would have failed. The new courses had taught
steel first in course 4 and glass first in course 5, with no choice of
ball anywhere. Now `MOON` brings in glass gently, and each new course has
an optional hard-fall line.

**Not yet true**, and each one is predicted rather than measured: the two
new courses' sizes (`MOON` 44 - 48KB, `SUMMIT` 55 - 60KB), the image's
growth (about 5.4KB), every HUD box price, and every miss count above
except the logged legs' own.

**The owner on the HUD (2026-11-13):** "Since the HUD inherently has to
scroll, we can keep it very minimal or even not have one. Gameplay and on
course features outrank it." So wave 4 builds the HUD last, OFF by default,
and ships it only if it costs MILL at most two missed frames a card with the
speaker on (SPEC.md 128.14.16); otherwise it is removed and the clock lives on
the results face.

## 2026-11-14 (wave 4, the final pass: what the rows measured, SPEC.md 128.14.26)

Wave 4 was built in seven stages on one tree: the tool and the two new
courses, the props in the guest, the round openings the owner asked for,
the game (the tour, the faces, `BONANZA.DAT`), the demos and the mouse,
the HUD, and the rows. A review then read the tree through four lenses
and seventeen findings were fixed. Nothing had been run as a row until
this pass, which ran every BONANZA row once as one scoped soak.

**The HUD did not fit, so it is gone.** The owner's rule was that the
clock ships only if it costs `MILL` at most two missed frames a card with
the speaker on. Measured on `MILL`'s route demo through `D`: the CGA
missed 93 refreshes with the HUD OFF and 158 at REST, and the Hercules 24
OFF and 69 at FOLLOW. The prediction for REST had been 0 - 3 more. The
hidden clock's per-frame bookkeeping and its show, hide and digit boxes
land on the frames that were already full. The whole HUD sat behind one
`%define`, so removing it was that line, its include and its `%ifdef`
blocks, and the package that is left is byte for byte the build without
the define. The time, the falls and the flags are on the face after every
play, as the owner asked for either way. The full write's blank, built
with the HUD, stays: it serves every respawn.

**The rows found one real defect.** On kern_mega, `V` (load the next
shipped demo) raised an exception charged to BONANZA. `op_fetch` leaves
the part's own selector in ES; `V` saved and restored that ES around its
copy and then dropped the part, and `op_drop` restores its caller's ES
after freeing the claim. Loading a freed selector into ES faults on a 286.
Wave 1's final pass met exactly this fault in the launch's drop, which is
why that path already sets ES to the package's own segment first. `V`
does too now, two bytes. The kernel kept the package running after the
fault, so the rows after it still passed, and only the fault log showed
it: a reminder that "the cases pass" and "nothing faulted" are separate
checks.

**The rest were the harness's own mistakes**, each found by running it
for the first time: a shadowing `heapmap` module; a stopped tour waiting
for its bracket to come up after Esc had already ended it; a Disk window
the chooser had left stale, so the double-click landed on the wrong row;
a full-write count read as a difference of a counter the launch zeroes.
None of them changed an assertion. One check had lost its case rather
than its code: `MILL`'s benchmark no longer brings a windmill or a post
in by a column on the CGA (wave 4's heavier frames moved which frames
step a column, and two runs saw none), so the ring row now has a scene
that puts a post just outside the window and steps the camera onto it.

**Measured** (every demo through `D`, the HUD OFF, misses with the speaker
off / on): `FIRST` 3 / 5 on the CGA and 0 / 0 on the Hercules, `TRIAL` 8 /
12 and 2 / 9, `MILL` 47 / 151 and 12 / 19, `MOON` 16 / 48 and 10 / 23,
`PEAK` 205 / 293 and 60 / 96. Every one ends at the model's state. `PEAK`
misses more than predicted on both cards, so easing its steep chains is
the owner's next call. The tour is 5,276 steps of autopilot, `PEAK`'s
launch about 4 s of disk. `BONANZA.O88` is 125,162 bytes, 130 of the
360KB floppy's 354 clusters.

**Still open.** The BENCH A/B against wave 3b is +522 - 531 clocks a
frame on the CGA (two runs) against the +500 asserted, +317 on the
Hercules. The HUD build had measured +413 with more code on the path, so
the bound sits inside the mean's spread between builds. The Hercules'
`MILL` lift stretch missed 3 refreshes in one run and 4 in the next
(at most 3; 3b measured 2). `bonanzawheel` (6) on the CGA fails as it
did in 3b.

**The red arms.** 83 broken copies were built and run, one each, and 82
went red at their own check once three were mended. One had stopped being
able to go red: the review had made the best-times save merge with the
file on the disk, keeping the smaller time, so breaking the keeper of the
smaller time in one place was hidden by the other. The arm now breaks
both. One had gone red by crashing the harness rather than by failing a
check, and one had moved to a sharper check of the same defect. The one
still open is `contact` in the ring row: with no contact choice there is
no waiting lane, and the scene built to show it never puts a wheel commit
over the ball where the oracle can see it.

**The verifier's round (2026-11-14).** An independent check found no
defect in the code, but the HUD's removal had stopped at the two
subsections that described the HUD. The game's own key table still listed
`H`, the face's settings line still read `H <HUD>`, and the box rules still
allowed five boxes. Those rows now say the HUD was not built, and they
match what the build draws. The ring row's `contact` check was a frame
marker that only selected frames for the card comparison, so a wheel commit
over the corner of the ball's footprint, where the round sprite has no
pixel, passed. It is now a failure in its own right. The right build stays
green on both cards. Breaking the package still does not turn the row red at
that check. A trace of the scene shows why: the broken wheel picks the post
up, never has the time to draw it, and the fifth frame's promotion draws it
correctly anyway, so the broken package never erases the ball there. That
arm waits for a scene with room in the wait.

**The owner after wave 4's measurement (2026-11-14).** The HUD did not fit
(+65 / +45 misses on MILL with the speaker on) and was removed. The owner's
answer is better than a HUD: a CLOCK on the course itself - a wheel prop in a
small font of our own, updated once a second, scrolling with the course, so it
has no scroll problem and costs nothing off screen. The owner asked whether
wheel items cost only when on screen: by design a lane outside the walk's
slice (the window's rows, two either side) costs nothing, but the slice spans
the full width, so a lane in the window's rows off to the side still costs a
walk - a column bound goes on the performance wave's list. Course tuning
(PEAK's misses) waits for the owner's play; the performance wave comes later,
with half-rate sound and sound in the wait's idle time to try.

**The clock counts down a time limit (2026-11-14).** The owner: target
times per course, "I agree with the original Marble Madness that this design
makes more sense than lives, and it adds a pressure to complete the course",
with an exploration mode in the first release that turns the timing off. The
clock prop: a crystal ball held up at an angle on a stick (other frames per
course are listed in the plan). And a CGA palette per course - one write to
3D9h at the bracket's start, free at run time, with the catch that colour 0
is both the background and every outline.

**The owner's end goal for Bonanza (2026-11-14), for the release regroup.**
No time carry-over ("that worked for an arcade box trying to steal quarters").
LIVES are timeouts: timing out ends the course, takes a life and returns to
the COURSE PATHWAY - a fullscreen map (Star Fox's galaxy map as a concept,
not a style) where some courses have several finish lines and the one taken
picks the next branch; branches may join back up; the pathway can afford a
HUD. The first two or so courses do not branch: the tutorial, learning by
playing. About 20 courses in all, about 10 to finish the tour, built one at
a time, with more of the plan's props, refined current ones, new surfaces
and challenges. Physics per ball: RUBBER sticky - medium acceleration, good
grip on Shift, a DOUBLE BOUNCE (Space timed on a bounce or a fall goes
higher); STEEL sluggish - slow acceleration, immune to traps that shatter
glass or fling rubber, maybe sinks in WATER (a tile used only where its side
shows, for alternate or required paths), moderate braking on Space; GLASS
fragile but light and fast - fast acceleration, very little braking grip. A
better window before the game: one artwork, the few setup options, the keys.
Open from the engine's side: the double bounce is the pumping wave 2 forbade
(the reach model needs a cap), Space's meaning differs per ball, and twenty
courses will not fit one 360KB floppy (parting out becomes real).

## 2026-11-14 (the regroup toward a release)

After wave 4 the owner set the end goal: lives as timeouts, a course
pathway with several finish lines, about twenty courses, physics per ball,
course clocks, a palette per course, and a better front window. Then,
reading a first list of what was left, they made eight further decisions.
This entry is how that became a roadmap. The roadmap itself is the plan's
new section, "Toward a release". It supersedes the old wave 5 and wave 6
lists and the "Next" list, whose items are kept and marked with their new
homes.

**The owner's eight decisions, in their words where it matters.**
1. At most ONE boost: "otherwise every course with rubber becomes a jump
   timing challenge, followed by flying over any obstacles we make. I
   just want a unique mechanic, not a flying ball."
2. Space and Shift mean the same for every ball, Hop and brake as today.
   Only the amount differs: rubber a decent jump with its "and again"
   second, higher bounce; steel today's tiny hop; glass in between.
3. Reuse a tile and prop map across courses, built out at load time; "feedback
   on if this works please, or if there is a better idea."
4. Medals: yes, as a "completed" icon beside the course on the pathway.
5. Pickups: yes, an hourglass and timed ones such as speed or jump height,
   "carefully, to not break a course; that will be a theme in course
   design."
6. Hidden finish lines: yes, with careful course design.
7. A ghost only if it is affordable: measure it.
8. Traps, more props and tiles (wind, magnets, cracked tiles, water,
   disappearing glass paths), scoped to the courses that use them so they
   do not cost the whole disk or the 64KB segment, with a limit per course.

**The disk question had a better answer than the one asked.** The owner
proposed shared tiles, built out at load. Measuring the six parts showed
where the bytes are: 59% of a course on the floppy is its occluder
records, 17% its blocks. Only 224 of 1,413 distinct blocks appear in more
than one course, because a block is cut from the composited picture, so a
pool shared by all six saves 4.8%. Building out at load time is the right
mechanism, though, and applied to the RECORDS it saves about 35%: a 4-byte
record on the disk instead of 8, expanded in place into today's exact
bytes, so no writer, row or course identity changes. Rendering a course on
the 5150 itself was priced and refused: the tool takes 15 s for PEAK on a
modern host, which predicts an hour on a 4.77 MHz 8088.

**The draft was reviewed through three lenses**, the engine, the game and
the scope, and they returned 49 findings. The ones that changed the plan
most:
- **The claim cap.** A play already holds seven of the kernel's eight
  claims per owner, so mechanic families share one claim, and the balls
  merge into one.
- **The step ladder was wrong as first drawn.** A climb is the Hop's apex
  plus a 4 px landing margin, so glass at the first figure climbed
  nothing, and a "rubber only" 1-unit step was a frame-perfect trick. The
  ladder is now derived from the tool's own sweep and printed with each
  rung's take-off window.
- **A boost that raises a rebound does nothing after a real fall**, because
  a 2-unit fall already rebounds higher. So "and again" is defined as a
  Hop's second bounce, on level floors only, once, never reaching 2 units.
- **History-dependent props break a binding contract.** Every prop's pose
  is a function of time today; a cracked tile or a collected pickup is not.
  That needs a per-play state bitset over a grid that is never written,
  which also makes a retry instant.
- **Water cannot be a family.** A ball in the water's cell is drawn whole
  over it, and "steel sinks, the others float" needs two heights in a cell.
  It is an engine change, priced on its own, in release 2.
- **Order.** The walk's column narrowing moves forward, so a clock off to
  the side really costs nothing. The clocks are measured on MILL and PEAK
  before their wave closes, remembering the HUD's +65 misses against a
  predicted 0-3.
- **A release-1 cut** (the tutorial and two worlds, with MOON and PEAK as
  world 2's finales) instead of waiting for twenty courses, and a
  playground course for the owner to judge the physics on before it is
  frozen.

One finding was rejected, because it added scope the owner had not asked
for: gems in exploration mode for release 1. Exploration's goal there is
hunting hidden finishes. A few more were taken in part, among them limited
Continues, which go to the owner as a default with the trade stated.

**The roadmap in one line a wave:**
- 5a: clear the HUD's dead code.
- 5b: the compact course format.
- 6: feel, ending with a physics freeze.
- 7: clocks and time limits.
- 8a to 8c: the shell (its code part, then the pathway loop, then the front
  window and medals).
- 9: mechanics as parts, and pickups.
- 10: performance, and the ghost measured.
- 11: the tutorial and the course pipeline.
- 12 and 13: worlds 1 and 2.
- 14: the machines.
- 15: release 1.
- 16 and 17: worlds 3 and 4, release 2.

The owner's open questions are grouped by the gate they block (the
physics, the shell, later), each with a recommended default.

## 2026-11-14 (the size hunt, and the owner's course-design notes)

**The owner's words, after reading the release roadmap:**

> Do measure, and also start an agent on "what else is smaller but does
> the same thing at the same speed". They can look at more than just
> occlusion, too. Then we can move on, the rest of the plan sounds pretty
> good.
>
> Some comments on maps:
>
> Right now, the springs are all completely hidden. Doing that for a
> "Hidden route" might be ok, but in general our mechanics need to be
> visible, and not have the viewer guessing about what is going on hidden.
> We could implement see-through tiles for this if that is not too
> expensive, or if it is, then we need to design courses so that when the
> ball is hidden its mostly straight or obvious where to go. I couldn't
> even find the end to PEAK.
>
> For course design as well: Increasing levels of challenge. Ramps that
> guide you to the center, early, and then later do the opposite. Things
> like needing to fling yourself with speed to cross a pit that ramps into
> a drop hole.
>
> Generally longer courses, which is why I want to downsize them as much
> as possible. Target ~30s for the early courses, ~60s for the middle
> levels, and ~90s for the last few.
>
> Q61-Q63: I'll need to test these to see how they feel, but this seems
> like a fine starting point.

**Five agents measured in parallel, on the host only:** the occluders,
the rest of the course, the image, the other parts, and visibility.
Nothing in the guest or the tools changed. Every packed figure used the
build's own LZ4 call, and every lossless form was decoded back and
compared byte for byte, in place where the guest would expand it in
place. The result is a dated report,
[BONANZA-SIZE-2026-11-14](../reports/BONANZA-SIZE-2026-11-14.md).

**The surprise was in the records, and it was not their size.** The plan's
answer to the disk question had been to shrink each occluder record from
8 bytes to 4. Measured inside the whole packed part, that saves 11.6KB of
the six courses' 83KB. Storing each record as the word DIFFERENCE from the
one before it saves 32.6KB, on today's records and at exactly 0 clocks a
frame. The reason is that the column steps by 0 or 1 about 95% of the
time, and the screen line, top and mask repeat. A record that differs from
its neighbour by one column cannot be matched by LZ4, but a run of
identical differences can. Both together save 35.4KB. The 4-byte records
kept in RAM free 13KB of PEAK's 65KB part, at about +30 clocks on a
typical occluder frame (ESTIMATED). The expansion is a 10-byte loop at
load, `rec[i] += rec[i-1]`: 81 ms for PEAK.

**What else was smaller:**
- The map stored as index planes, ROWTAB computed, the route as tiles,
  one shared copy of the lift's sprite, and the grid's derivable fields
  rebuilt together save a further 5KB. With the records, the six courses
  go from 83,152 to 42,792 bytes packed, measured in combination.
- The three ball parts can be regenerated at fetch, byte for byte. Each
  material's texture turns out to be a separable sum against a threshold,
  `A[x][fx] + A[y][fy] < T`, so 7,380 packed bytes become 1,668. Rubber
  needs 16-bit tables, because its closest pixel is 0.00065 from the
  threshold.
- The demos as a bit stream halve, which is worth about 8.5KB at twenty
  courses.
- Wave 8a's code part was re-measured at 5.6-5.9KB, not the plan's
  7-8KB.

The load work the shortlist adds to PEAK (about 0.37 s, PREDICTED) is
less than the disk reading it saves (about 0.77 s), so a launch should
get faster.

**RAM is the wall now, not the disk.** At MOON's and PEAK's pace, a
block row is 0.37 s and about 381 bytes of RAM. With the 4-byte records
one part holds about 73 s of course. A 90 s course needs the two
zero-clock RAM levers (overlapped grid rows and a constant map stride)
and a slower design pace, or the grid moved to a claim of its own. On the
disk, twenty courses at the owner's 30/60/90 s mix come to about 490 KiB
in today's form and about 253 KiB in the 5b form, against about 239 KiB
available. LZB for the parts closes the remaining gap (about 206 KiB), at
about +0.9 s on a long course's launch. That is the owner's call after
5b.1's real figures.

**Why the springs vanished.** Geometry toward the viewer that stands dh
units above a floor hides that floor for about dh block rows behind it.
PEAK's springs launch +x onto a tier 5-6 units higher and a few rows in
front, so both are 0% visible. Its cup sits two rows behind a rail 4
units above the green. The visibility agent priced every see-through
idea:
- **A dithered ghost costs nothing at all.** The occluder pass lays
  `((buffer XOR block) AND mask) XOR block` whatever the mask holds, so a
  checker ORed into every mask by the tool shows a hidden ball as a 50%
  ghost: 0 clocks, 0 guest bytes, and the masks deduplicate 710 bytes
  smaller.
- **Real low rails fix PEAK's end.** On a scratch copy, rails one or two
  units above the floor they guard cut the steps with the ball hidden from
  475 to 98, and made the cup and the pad fully visible.
- The rest were refused: run-time see-through, outlines and cutaways cost
  clocks, or draw a picture that lies about the physics.

**What changed in the plan:**
- The owner's notes are binding course-design rules CD1-CD4 in R1.
- Wave 5b's stories now follow the report's shortlist:
  - 5b.2 is the difference-coded 4-byte records, measured against the
    HUD rule on MILL and PEAK, with the 0-clock form as the fallback;
  - 5b.6 is the ghost dither with the visibility audit in report mode.
- Wave 9's 9.1 regenerates the balls.
- Wave 11 gains three stories:
  - 11.5, the visibility rule, refusing;
  - 11.6, the RAM levers and the replay log's check for 90 s courses;
  - 11.7, the demo bit stream.
- The design sheet now states each course's target time, pace, place on
  the challenge curve and how its mechanics stay visible.

## 2026-11-14 (wave 5b's contract, checked cold, and the owner's answers)

SPEC.md 128.15 was written before any code, and a cold consistency check
read it against the code and re-took its sizes. It left three things to
fix, and the owner answered the open questions the same day.

**The sizes were re-measured, not re-predicted.** The first figures in
128.15.14 were a layout measurement plus two adjustments, and both
adjustments were wrong. The check built each course's stored form from
its real part at `ef59209a` (the real header and directory, row planes
with the high bits first, each section's own hole, the follow-up's
zeroing, the dither, P not taken; the ways modelled as zero pairs, so the
real figures are slightly higher) and packed it:
- the six courses are **43,264 bytes LZ4 and 35,038 LZB** under D, not
  about 42.4KB and 34.2KB; RAM is 180,156; `bonanza360.img` comes to
  about 91 clusters with LZ4 parts and about 80 with LZB;
- the platform sprite had been counted twice: +313 was added to a
  measurement that already held the props as they ship;
- the ghost dither's -710 was today's form's. On the 5b form it saves
  about -220 LZ4 (-266 LZB). It is still 0 clk and 0 guest bytes, so it
  stays;
- `PEAK` packs to 12,676 LZ4, which is **over** its 60 s budget of 12,550.
  It is far under its 18,825 cap, and under budget with LZB at 10,377.
  The tool's budget printout will say "over" for it, and that is correct.

**Two hazards in the code the contract describes.**
- `op_fetch` answers CF = 0 without decoding when the part is already
  here, and the expansion is not idempotent (WDIFF run twice corrupts the
  records). Today every launch drops the course on the way out, so 5b is
  safe. Wave 8b fetches inside one bracket, so it must drop before a
  re-fetch or keep an "expanded" flag per claim. That is now a written
  requirement in 128.15.4.5 and in the plan's wave 8b.
- In `bz_oand`, AX already holds `bz_ofl2` when the mask is read. D's
  table lookup needs AX, so it moves in front of that load. Same
  instructions, same price.

**The owner's answers.**

On LZB for the course parts:

> "'a stronger compression mode for the courses': lzb I assume? That would
> be fine."

So LZB is decided and stays the default. The owner was quoted +0.9 s on a
long course's launch; the contract's own finding is an UPPER BOUND of
about +1.6 s on `PEAK` (about 5.0 s against 3.4 s, today about 3.9-4.0 s),
because the balls go LZB with the parts table. The final pass measures it,
and the owner is told the measured figure. LZB for the image is still only
offered.

On a second disk:

> "'a second Worlds disk': I'd prefer not, but we can see what we need in
> the end. 20 is a rough want, too; it could be 19, or 18 total."

So the target is 18-20 courses on one disk, and the Worlds disk (8b.11)
is a last resort. The 239 KiB of room was sized for twenty; at 18 every
budget would be about 11% looser, and the pinned budgets stay as they are.

On "each course has to fit about 64 KB of memory":

> "This seems like we could make a larger claim, and split out art/sound
> from occlusion data? Or is there some speed penalty I'm not seeing
> there? ... we can look into the option if we actually need it."

It can be done, and it is now written down as the escape for a course
past one part: the **two-part course**, with the picture (map and block
pool) in one part and the occluders, masks, grid and props in another,
each up to 65,024 bytes. Priced from the code, not measured: one more
fetch and claim at the launch; nothing for the row writer, physics or the
wheel, which read one kind of data and only load a different segment
word; and a segment switch for each laid group in the occluder lay, the
one routine that reads the picture and the masks together, which is tens
of clocks each and a few hundred a frame at worst. It is not built in 5b.
It is taken only when a course really outgrows one part (about 73 s at
MOON's and PEAK's pace under D), and measured then.

## 2026-11-14 (waves 5a and 5b, built: what the host proved and what is owed)

Nothing here is committed yet, and no emulator row has run: everything
below is a HOST observation (builds, `--selfcheck`, unicorn runs of the
package's own routines, `cmp`), plus one look boot a card at two stages.
The rows, the red arms and the D/C and format A/Bs are the final pass's.

**5a cleared the decks.** The dead HUD came out of five rows (243 lines,
eight red arms) and out of `bbcourse.py`. One thing the contract asked for
could not be built as written: a cup "inside the old panel's rect" that now
compiles. No compilable course can put one there - the footprint rule's
two-tile void keeps every mark at least 41 px from the left edge, and the
rect ended at 24 - so the control compiles a cup on the green's front-left
cell instead. Proof that 5a moved no package byte: `cmp` of two private
trees, `0e5e46ca` against the working tree at 5a's end. 5b's edits then
landed in the same uncommitted tree, often in the same hunks, so the
commit has to say whether it splits 5a out and re-takes that `cmp`.

**5b's format, on the host.** The tool now compiles one offset-free model
and writes every form from it: the RAM form under 4-byte (D) or 8-byte (C)
records, wave 4's BZC1 (byte for byte against `ef59209a`'s parts, the proof
that only the container moved), and the stored form, each section's bytes
at the end of its own slot. The guest's `bz_cexp` expands in place; under
unicorn it equals the tool's RAM form on all six courses under both
strides, writing nothing outside the part and the box buffer.

What the instructions said that the predictions did not:
- `bz_cexp` is 342 bytes, not about 225 (WAYS alone is 101), and CELLS
  another 395, not 150 - 230.
- ROWPLANES costs about 158 clk a cell, not 75: `shl ax, cl` alone is 24.
  So `PEAK`'s expansion is about 0.58 s under D (0.68 s under C) with
  CELLS, and a launch with LZ4 parts gets about 0.37 s shorter under D -
  not 0.5 - and about the same as today under C. PRICED; the final pass
  measures it.
- The occluder pass under D prices at +320 clk on a typical frame and
  +1,300 at the worst position, against +280 / +1,200 predicted.
- A name clash: the contract's `bz_osb` was already the idle test's cell,
  so the SB bias is `bz_osbias`.
- The budget reads the D stored form whatever `BZREC` says, because
  MILL's C form packed over its cap and would have failed a C build.
- A wave 4 `.BZR` is refused twice: through `L` as "Damaged demo file"
  (the hostile pass) and only through `R` as "Another course's log".

**The ghost dither, and what a review found in it.** Every occluder mask
carries a checker, so a ball behind scenery shows as a 50% ghost, for 0
guest bytes. The first build put the checker's kept pixels on the
`x + y` EVEN lattice. A reviewer worked out that the shadow's dark pixels
are exactly that lattice, and that records DO lay over the shadow when the
ball flies low over a cell whose grounded key hides nothing - so the whole
shadow printed through the nearer block (605 of 11,520 sampled positions
on TRIAL). Moving the checker to the ODD lattice costs nothing and hides
the shadow whole again. The same review counted records whose dithered
mask lays nothing at all (PEAK 162 on the odd lattice): they are left out
of the part now, and kept in the rule's models. That moved every identity
again, and MOON's and PEAK's authored demos were re-stamped (their `ident`
lines only). `PEAK` packs to 12,547 LZ4 - three bytes under its 60 s
budget. The physics cross-check and the expander check were re-run on
these parts: ALL OK and equal.

On the Hercules the ghost reads as a 2 x 1 grey over white and cyan, but
barely at all over magenta, which that card already draws as a pattern.
That is an owner's question (SPEC.md 128.15.15), not a fix.

**The rows** gained a claim leg (`bonanzaexit`: the course claim at the
bracket equals the tool's RAM form, all six courses), a PEAK demo leg
through the hidden stretches (`bonanzaring`), the D/C acceptance and the
format A/B (`bonanzaperf`, by hand), and red arms `recstep`, `expoff1`,
`rowtab1`, `cellsafe`, `expcs`, `nodither`. Unicorn shows each broken
expander differing on the course its arm should go red at. The review
also caught `bonanzaring` reading a C tree's lane maps at D's offsets; the
row now compiles each course under the art's own stride.

Owed to the final pass: the deduplicated union of the bonanza rows, every
new red arm once, `bonanzaperf --rec-ab` (which decides D or C) and
`--fmt-ab` (the launch the owner is told), and the look at MILL's slab.

## 2026-11-14 (wave 5b, the final pass: C ships, and what the launch costs)

Everything here was MEASURED on MartyPC's 5150 machines, CGA and
Hercules, on one uncommitted tree.

**D or C.** The owner's rule was that the 4-byte record (D) could ship only
if it cost at most 2 more missed refreshes per card than the 8-byte record
(C), counted over MILL's and PEAK's demos with the speaker on. Each card's
first three runs were too noisy to decide, so each took six runs a build.
On the Hercules D came out 4 misses better. On the CGA it came out **23.5
worse**: D averaged 446 against C's 422.5. So C ships.

Almost all of the 23.5 is MILL, and it is not the occluder pass alone.
MILL's demo on the CGA plays in one of two modes. In the low mode the
camera pans 49 columns and misses about 91 refreshes. In the high mode it
pans 84 - 88 and misses about 145, because a slower frame lets the camera
fall further behind, and that costs more frames. C landed in the low mode
three times out of six. D never did. D's extra few hundred clocks a frame
(a median of +380 - +448, against +320 priced) are enough to tip MILL into
the high mode. PEAK differed by 2.5 misses a run.

D's code came out, along with the `BZREC` knob and its row legs. The C
build after the deletion is byte for byte the C build before it. The 43.8KB
of RAM D would have saved waits for wave 10, and PEAK's claim is 59,432
bytes (5,592 of headroom).

**What LZB costs at launch.** The contract's upper bound was 5.2 s for
PEAK's launch with LZB parts. Measured three times a card, it is **4.2 s
on the CGA and 4.5 s on the Hercules**, about 0.3 - 0.4 s more than with
LZ4 and about 0.2 - 0.5 s more than wave 4. The owner had been quoted
+0.9 s, so this is under that. The disk drops from 130 clusters to **83**
(94 with LZ4 parts).

**The rows.** One scoped soak ran all thirteen bonanza rows. Twelve
passed, including the claim leg on all six courses. `bonanzawheel` (6)
failed on the CGA, the corner-step failure open since 3b. BENCH against
wave 4's anchor measured -19 and -22 clk a frame. All 88 red arms went red
at their own checks once two things were mended:
- `respawn` overwrote a register its target code still needed. At wave 4's
  offsets that happened to be harmless; at 5b's it hung the frame loop. The
  arm now saves and restores the register.
- the format A/B compiled a course while the guest sat stopped at a
  breakpoint, which outlasted the wait that followed. It now compiles first.

`contact`, which wave 4 never made go red, went red. A look at MILL's lift
on both cards, with the ball riding the slab and then under it, matched
what the ring row checks.

**Owed to the owner.** The launch figures above. One new question: the
course budget is still read on D's form (PEAK 3 bytes under). On C's
shipped form PEAK is 897 bytes over in LZ4, though under its cap and under
budget in LZB.

