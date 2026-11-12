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
