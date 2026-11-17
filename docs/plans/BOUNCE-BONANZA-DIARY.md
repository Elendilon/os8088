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

## 2026-11-14 (wave 5b, the D/C decision re-opened: the owner's smoothness rule)

The owner read the verdict above and re-opened it, in these words:

> "Variance shouldn't break what we may need as a memory savings in order
> to do a course. Do try again. A few dropped frames at 50 or 60fps is not
> user noticeable; we just want to stay smooth."

The point is fair, and the record above supports it. Almost all of D's
+23.5 on the CGA was MILL's camera landing in its high mode. C landed
there in half its runs too, and PEAK differed by 2.5 misses a run. The old
rule summed raw miss totals, so a coin-flip between two camera modes
could decide a 13KB memory lever, the lever long courses need.

**What changed (intentions, not yet measured):**
- D's code is back behind the `BZREC` knob, taken from the last copies
  saved before the deletion. The default is now 8, so the shipped build is
  still C, byte for byte.
- The rule is now about smoothness. SPEC.md 128.15.5.4 has it in full;
  in short:
  - **Count missed refreshes off the flip.** A frame held three refreshes
    missed two. The time a frame is reported presented jitters too much to
    count by; the flip is locked to the refresh.
  - **Compare like for like.** Both builds play the same steps, so rates are
    per second of the same play. MILL's runs are compared only within the
    same camera mode. The mode cannot be pinned: GLIDE reads the frames
    that were actually presented, so the timing race itself picks the mode.
    So each run is classified by how far its camera panned.
  - **The rate.** D may add at most one missed refresh a second over C's.
    One isolated missed refresh a second, on an otherwise perfect display,
    takes the evenness measure of PERFORMANCE.md Part 3.2 to about 0.13 on
    the CGA and 0.14 on the Hercules, a quarter of the roughly 0.5 where
    unevenness is noticed.
  - **No new stutter.** The longest run of missed refreshes in a row, and
    how many runs of two or more there are, must stay within the range C's
    own runs show. This uses the median of D's runs, so one odd run cannot
    fail D.
- `bonanzaperf --rec-ab` now computes exactly that verdict, and it has a red
  arm, `occslow`, which pads D's walk by about 25k clocks a frame and must
  fail the rate clause.

**What is checked:** the leg's arithmetic, on made-up runs (holds when D
matches C's high mode; fails the rate at 4.6 against 29.7 a second; fails
stutter on a hitch in every run); `--check` (every red arm assembles,
`occslow` over D's art, +7 bytes); `checkdocs`. No emulator row has run.

**Read against the new rule, the old figures suggest D holds**: in MILL's
high mode D missed about what C did, PEAK's 2.5 a run is under 0.1 a
second, and the Hercules favoured D. That is a prediction. The next final
pass runs `--rec-ab` and `occslow` and decides.

## 2026-11-14 (wave 5b, the D/C decision taken again: D ships)

The re-measurement ran under the owner's smoothness rule, at one tree:
C the default build, D a private tree, MILL's and PEAK's demos through
`D`, the speaker on, six runs a build on each card. The two cards ran in
parallel, about five and a half minutes each.

**What was measured.** Missed refreshes a second of play, off each frame's
flip (D - C):

| card | MILL | PEAK |
|---|---|---|
| CGA | -0.01 in the low camera mode, -0.04 in the high one | +0.16 |
| Hercules | -0.08 (one mode) | -0.14 |

The rule allowed +1.0. Four of the five comparisons favoured D. The
longest run of missed refreshes in a row and the number of runs of two or
more stayed inside C's own range everywhere (the longest 12 - 13 on the
CGA and 10 - 11 on the Hercules in both builds; one run of two or more a
MILL run and two a PEAK run, every run of both): they are stretches of the
demos, not of the record. The occluder pass cost D a median of +382 to
+438 clk a frame over C, like for like, and at worst +850: the first
pass's figures again.

**The camera's coin.** This time D landed in MILL's low camera mode in 2
runs of 6, and C in 3. In the first pass D landed there in none, which is
what made D look 23.5 misses worse. The tipping is the timing race the
owner suspected, not the record, and comparing within a mode is what made
that visible.

**The red arm.** `occslow` pads D's walk by about 27k clk a pass frame. It
failed the rate clause by +2.10 a second on MILL and +11.50 on PEAK, and
the stutter clauses too. So the rule can see a real cost when there is
one.

**What shipped.** C's arm and the `BZREC` knob were deleted; the tool's
default stride is now 4. Nothing in D's build moved across the deletion
(`cmp` against a `BZREC=4` build taken just before it). The six courses
now hold 179,680 bytes of RAM against C's 221,764, 42,084 less. PEAK's
claim is 47,148 bytes, 17,876 under the 65,024 cap (C's was 5,592). That
is the memory the owner wanted kept for long courses. The image is 99
bytes larger than C's and the package 2,256 smaller.

**The rows, once, on the D build.** Seven of nine passed at once.
`bonanzawheel` failed only its known check (6) on the CGA. `bonanzaperf`
failed once: one wheel lane was late (`bz_rwlate` 1) in PEAK's demo on the
CGA with the sound on. Re-run alone, it passed. That is the open race in
SPEC.md 128.13.17 item 6, which was first seen on MILL in wave 3b; D's
extra clocks are one more input to it, and it stays open. The by-hand
BENCH A/B against `ef59209a` passed: +314 clk on the CGA and -143 on the
Hercules, against a limit of +500. C was at -19, so D uses most of that
guard on the CGA's BENCH.

**One test was wrong.** `recstep` (the walk stepping 8 over 4-byte
records) had never run on the emulator. On BENCH it stayed green on the
CGA: none of BENCH's six occluded frames met a skipped record. Its leg is
now the W4 part, and there it went red on MOON's demo on both cards. A red
arm that is only assembled is not yet known to work; this is why.

## 2026-11-14 (wave 6, the final pass: the rows, the arms, and what feel costs)

Wave 6 built the owner's per-ball physics. Space Hops and Shift Grips for
every ball, in different amounts. Rubber gets one boost a Hop. The drag is
now fractional. There is a CGA palette per course, a camera that follows
the ground line rather than the ball, and a seventh course, the
PLAYGROUND, for gate 1. This entry is its final pass: every BONANZA row
once, every red arm once, and the measurements SPEC.md 128.16.10 asks of
this pass. The re-baseline is the freeze's, after the owner plays.

**The rows.** One scoped soak: ten rows passed and three failed. None of
the three found a fault in the guest; all three were in how the rows
drive it.

- **`bonanzamega` hung for 37 minutes.** Its new PLAYGROUND case waited
  for the Hop's flight in a loop that read the 86Box machine's memory, but
  86Box is HELD between commands. Nothing stepped it, so the ball never
  moved. The loop now steps the machine once a pass.
- **`bonanzaring` and `bonanzawheel` failed on coverage**, all from one
  cause. Their scenes held the ball AIRBORNE over a floor far below:
  186 px in one case. That was fine while the camera followed the ball,
  but wave 6's camera follows the GROUND line under an airborne ball. So
  GLIDE and TRICKLE panned the window 36 - 44 rows down after the floor,
  and the scene's post or rotor was no longer where the scene needed it.
  The cure keeps the scenes' meaning: the cut still centres on the ball
  (the cut uses the ball's own line), and from the next frame the ball is
  held RESTING in the window's band. A grounded ball's camera line is its
  own.
- **The row-0 probe** lost a frame on the Hercules. The reach's taller top
  puts BENCH's floor 20 px further below world line 0, so the fifth
  frame's shadow fell off the window. Those frames are now put 40 px back,
  as the probe's split frames already were.

All three rows passed when re-run alone. `bonanzawheel` still fails its
check (6) on the CGA, as it has since 3b.

**The arms.** All 107 emulator arms ran, and every one went red at its
own check. Three needed a change:
- `contact` now runs on the CGA alone. The Hercules' MILL route under the
  new drag never puts a contact candidate under the wheel.
- `nosafe` is now compared against its own model, so it fails at the
  footprint and not at the window a frame earlier.
- `nolatch` could not be made to fail at its intended check. Its model,
  paced at the card's average rate, reverses the rows two frames before
  the kill. The guest's own pacing reaches the kill first, and so does the
  model paced as the guest ran. It now goes red at the window check
  against the shipped camera model instead. The row's reversal check stays
  in place, but no arm proves it.

**What the new code costs, MEASURED.**
- The fractional drag: worst 335 cycles a call, mean 325, against a price
  of 428 (priced from its instructions, the fetch floor and x 1.05).
- The camera's ground line: worst 470 cycles, means 360 - 436, against
  527.
- BENCH against 5b's commit (not like for like: the ball is faster and the
  route moved): the CGA's sim+camera part +654 clk a frame, inside the
  predicted +0.65 - 0.75k.

**What the owner will feel.** The rates held: every demo is within one
missed refresh a second of 5b's. MILL on the CGA, which the host had
predicted might cost about +5 a second, missed 8.90 against 5b's 8.52 (its
low camera mode) and 12.48 (its high one), although it now always plays
in the high mode's columns. PEAK rose 0.69 a second on the CGA and 0.37 on
the Hercules.

What changed is the SHAPE of the misses. No frame was ever held for more
than two refreshes. But where 5b's misses were scattered, wave 6's come
in runs: half-rate stretches up to 43 frames long on PEAK (about 1.4 s at
30 Hz), and 45 such runs in its 40 s, where 5b had 2. The likely cause,
not yet separated by a measurement, is the feedback 5b first saw on MILL:
a faster ball pans more, a missed frame makes the camera step further,
and the next frame costs more. Under the owner's smoothness rule this is
the stutter half. It goes to gate 1 beside the levers that would change
it, each ball's `K` and `ACC`.

**The ladders and the numbers** the owner needs at gate 1 are on one page,
[BOUNCE-BONANZA-GATE1.md](BOUNCE-BONANZA-GATE1.md): what to try on the
PLAYGROUND, both ladders, every tunable with its limits, and how a retune
is asked for and checked before it is committed.

## 2026-11-15 (wave 6b, the gate 1 retune: built, measured, and held)

The owner played wave 6's playtest disk and wrote back four things
(SPEC.md 128.17, verbatim there): braking "a bit high all around, lets try
6/3/1"; a boost they could "only get to bounce maybe 1 out of 20 tries and
never when I'm moving"; 3-tile gaps "probably fine, if we design with it in
mind"; and a camera that "bops back and forth" at the bottom of MILL's
ramp, with a transition out of MILL's chute that "slows down before it then
quickly moves over". Wave 6b is the answer to each, and this entry is how
it was built and what the final pass measured.

**The diagnosis came first, on the host.** Scratch copies of the model at
`4d69985c` reproduced the owner's experience before anything changed. The
boost's window closed ON the contact step and had no late side: a press
one step late did nothing, and a press aimed at the landing the player SEES
falls one or two steps late, because the display shows a contact a frame
or two after its step. Rolling did not move the contact, but the camera's
pans dropped the CGA to half rate, which made presses later still. The
camera's back-and-forth was GLIDE's trailing-edge target (a few pixels back
swung the whole lead) re-aimed from the ball's own speed at every apex; the
chute's "slow, then quick" was the heavy rule stopping a pan with no limit
(30 frames at MILL's chute, 246 on PEAK).

**The boost became a press in the flight, with a late grace.** A second
Space press any time in the Hop's flight arms it; the first contact boosts
if armed and the floor is a plain level one. A press up to three steps
AFTER an unarmed bouncing contact converts the rebound into the boost
exactly, as if it had been armed (`gvz` gains the difference, and `gz` the
height it would have gained since). On the model's timing-error maps a
player aiming at the landing now boosts 81% of the time against wave 6's
43% (65% while moving, against 33%), and a mid-flight tapper 95% against
25%. Holding
Space through the landing does nothing, so a Hop held onto a ledge never
boosts by accident; whether "holding" was what the owner meant is a
question back to them.

**Two camera designs were judged, and one was built.** The first sketch
kept GLIDE and patched it. The second, LATTICE, replaced it: a band with
return hysteresis (a few pixels back move nothing), targets on a lattice
of whole columns and 32-line rows, a pan that only extends forward and
whose rate only rises, the urgent edge at half the window, tubes pre-aimed
at their exit, and the heavy rule a DELAY of at most three steps instead
of a stop. Authored "transition points" (the owner's first suggestion)
were prototyped as `view` statements and measured; the rule alone met
every case, so they were not built. On the model LATTICE took reversals
from 84 to 7, stalls from 9 to 0, the dither test's reversals from 186 to
0, and the CGA's priced pan work by 22% outside BENCH. The review moved the
urgent edge from the window's width to half of it: at the full width it
coincided with the return band and made every return pan a run of column
frames.

**The guest matches the model exactly.** The physics (`bz_step`, every
state byte with the grace's two) was cross-checked under unicorn on every
course, and on the glass `bonanzaphys`'s twenty boost and Grip replays
equal the model frame for frame on both cards. The camera (`bz_camera`,
LATTICE) equals `bbcourse.Glide` on every frame of the CAMERA leg's seven
scenarios on both cards, 11,666 frames, with MILL's ramp bottom reversing
zero times. Its worst frame costs 6,405 cycles, 11% over its price from
the instructions and inside the row's bound.

**What the final pass measured, and why the disk is held.** The decision
the owner's smoothness rule needed was written down before the
measurement: LATTICE ships on round 2's disk if, on MILL's route demo, the
misses a second AND the longest run of misses are no worse than wave 6's
beyond the spread of three runs, on both cards. They were measured like
for like (the same key bytes, no Space or Grip in them). LATTICE takes the
CGA's misses from about 9.2 to 5.1 a second and its half-rate stretches
from 16 - 20 a run to 5 - 10, and wins everything on the Hercules. But in
two CGA runs of three one stretch is LONGER: 39 and 46 frames against wave
6's worst 29. It is B's ramp descent, where the ball rolls two steps a
frame, the row pan turns fast at the urgent edge and stays fast, and a
column joins every other frame: more work than a CGA refresh holds, every
frame, for over a second. The contract had named this case as a risk (the
half-rate pass's MILL exception). So by the rule written in advance the
disk is held, and the figures go to the owner with three choices: ship
LATTICE as it is, hold it for a change at that descent, or ship wave 6's
camera with 6b's boost and Grip. The same descent is why `bonanzawheel`'s
rotor-rate check now fails on the CGA (86 - 89% of a rotor's pose changes
shown, 90% asserted): the wheel gets no time on a frame that moves two
rows.

**The rows' own fixes.** Four rows failed the first soak, and three of the
four were their harness meeting LATTICE's different frames: the ring's
MILL benchmark no longer saw the slab's box (its checked frames now come
from the poked play's PWAIT scene, which has them); the replay's pilot left
the ball ricocheting among MILL's bumpers (a second rescue now gives up a
waypoint after 200 frames on it); and `bonanzaperf`'s new fall leg ended at
FIRST's goal (a replay ends there; the leg now runs FIRST's autopilot as
the benchmark, where the goal ends nothing, and reports all nine falls).
`bonanzaperf`'s 3b check that no one-step frame of BENCH misses now
applies to frames that pan nothing, since BENCH's pans are LATTICE's now.
One failure is real and left open: a wheel lane shown late on PEAK's
Hercules demo (`bz_rwlate` 1), an old race (128.13.17 item 6) that LATTICE
made reproducible.

**The arms.** Seventy emulator arms ran once, every one the wave added or
carried; 67 went red at their own check at once. The camera's cap arm,
whose scenario had been chosen on the model at the nominal frame rate,
stayed green on MILL, where the guest's own pacing never holds the camera
long; it was re-found on PEAK's lift, where the shipped camera holds at
its cap, and went red there. One wheel arm needed a second run for the
Hercules' phase, and one performance arm was retired from `bonanzaperf`
(its overrun never happens under LATTICE's MILL frames) and kept where it
still bites, in `bonanzawheel`.

Round 2's notes, the held-disk figures and the play list are at the top of
[BOUNCE-BONANZA-GATE1.md](BOUNCE-BONANZA-GATE1.md).

## 2026-11-15 (wave 6b, round 2: the owner plays it and keeps it)

Six hours into the wave the owner asked for the build to test the physics
before the independent verify had finished, and got the final pass's disks
as a preview. The verdict came back in three sentences: *"Camera end
position is much better, feels natural. Keep that. Double bounce with
"preprime" works. Grip is better; less overpowered."*

That settled the one decision the measurements could not. The final pass
had HELD the disk by 6b.7's rule: LATTICE cut `MILL`'s CGA misses a second
by 45% but its longest run of misses went past wave 6's spread, so the
rule handed the choice to the owner. Played on the target, the view's
resting position is what reads, and the owner kept it. The longest runs,
and the two rows that moved with them (`bonanzawheel` (7) and the
Hercules' `bz_rwlate` on `PEAK`), are wave 10's, with their measurements;
no assertion was loosened to make them pass.

Observed: the verify's clean rebuild produced disks byte-identical to the
preview (md5 compared), so what the owner played is what was committed.

## 2026-11-15 (gate 1, round 3: a held boost, a fall's boost, a grace of 4)

The owner's next notes were short and concrete: a late window of 4 steps
instead of 3; Space HELD should arm the boost; a ball that falls off a ledge,
not only one that jumped, should get one boost; and after a boost the ball
has to stop bouncing before it can boost again - *"We'll use that eventually
to make them 'not boost' after multiple fall and forward jumps to make it
over the final gap."*

Two of the four were already priced. Round 2's contract had held the "held"
reading back because of one measured hazard: a Hop pressed at the lip of a
half-unit step meets the ledge one to four steps later, while any ordinary
press is still down, so "held at the contact" boosts on every such climb
and the boost's radius throws the ball off the back of a narrow rung. The
remedy was written down then too, a TAKE-OFF GATE (held arms only onto a
floor no higher than the one the ball left), at about 25 bytes and a byte
of bss. It went in as priced, near enough: one word, `bz_zoff`, written by
`bz_toff`, which every take-off already goes through. Its control,
`nogate`, boosts on 5 of the 5 lip take-off points that the gate keeps
quiet.

The fall needed no new mechanism. Step 6 already had the two branches that
take a grounded ball off its floor without a Hop; each now sets the token,
and the Hop's own write moved into the `.launch` they share. Everything
downstream - arming in flight, the held contact, the grace - then works for a
fall exactly as for a Hop. The model's sweep of five drops at four speeds:
16 of 20 boost with Space held at the landing, and the four that do not are
the 3-unit drop, whose bounce (442) is already above the boost (350).

The fourth note turned out to be true by construction rather than something
to build. The token is set only when a GROUNDED ball leaves the ground,
every contact clears it, and a bouncing ball is airborne from contact to
contact. So after a boost there is no way to take a new token until a
contact has landed the ball. Rather than spend a resident flag on a rule
the engine already keeps, item 7 now asserts it over 2,303 steps of held
and mashed Space, including falls, and the carried `pump` control (a
contact Hop re-arming the token) breaks it eleven times. The rule is still
written down as binding (SPEC.md 128.17.16.3), because the owner means to
lean on it in a course.

Measured on the host: +36 bytes and +2 bss; the ladders unchanged; the
grace exact at k = 1 to 4 on 2,425 ladder cases; the who-hits-it table at
88% for a player aiming at the landing (round 2: 81%) and 100% for one who
holds. One byte of the 36 is a short jump made near: the held test pushed
the stun's `jmp short .ground` close enough to its limit that two red arms'
patches no longer assembled. That was caught by the row's own `--check`,
which assembles every arm, before anything ran in an emulator.

## 2026-11-15 (gate 1, round 3b: every launch arms, and the boost adds)

The owner answered round 3's questions with "yes to all" - springs, tube
exits and the cup's lip-out arm a boost too - and asked for one new rule:
a boost after a fall should ADD to the bounce, by "the difference between a
bounce and a boost", because "fall bounces did feel a bit low". Mid-build a
second note arrived: none of today's courses is more than a test.

The first part turned out to need the one flag round 3 had argued away.
"Stop bouncing before the next boost" was true by construction while only
a grounded ball could take a token. A spring under a contact and a tube's
exit launch a ball that may still be bouncing from a boost, so the rule
needed state after all: `bz_bsp`, set by a boost and cleared by any step on
the ground. A search on PEAK found the case that proves it - a boost whose
bounce carries the ball onto the spring - and `nospent` boosts twice there.

The second part had a clean reading hiding in the owner's words. On the
level a boost is 350 and the Hop's bounce 201; the difference is 149. "The
boost is the bounce plus 149, never less than 350" changes nothing on the
level and makes every fall gain - so it was built as that, with 149 derived
from each material's own Hop rather than written down. The cost is the
boost's fixed apex: from a 1.5-unit drop down, the boosted ball rises above
the ledge it fell from, the reach grows, three courses' parts move, and the
PLAYGROUND's unreachable 2-unit rung becomes reachable. Under the owner's
note those became reports rather than refusals. The question he did ask -
offscreen - came back clean on the camera model: nothing leaves the window
on either card, even after a 6-unit drop.

One control lost a leg honestly: with the larger reach, MILL's occluders
and so the heavy rule's frames moved, and no ramp-bottom pattern (about
fifty tried) reverses without hysteresis any more. The control is held red
where it still is, and the search is written down.

## 2026-11-15 (gate 1 closed: a baseline, not a freeze)

The owner played round 3b - *"Tested, feels much better"* - and closed gate
1 with a correction to the plan's language: the physics are a BASELINE, not
frozen, because no real course exists yet and half the props and mechanics
are still to come. In the same exchange the owner moved the soak cadence
(every 4 - 5 rounds, or when something breaks) and deferred the 108-run
performance re-baseline to wave 10, all the more because a parallel speed
pass had just landed on this branch: 398 commits, MILL's CGA misses 122 to
24 and its longest run 31 to 4 (docs/reports/BONANZA-SPEED-2026-11-15.md).
That pass merged every round of this gate as it went, so the branch came
back together by fast-forward. Next: wave 7, time.

## 2026-11-15 (wave 7: the clocks, and then the clocks are solid)

Wave 7 put time on the course. A limit replaced the par, counted in steps so
a replay and a demo agree on it; running out ends the course; the music and
the sound events found their places (a tick under ten seconds, a low note at
thirty and ten). The clock itself was the owner's choice of form: digits in
a crystal ball, because *"an analog clock will be hard to read and can't
really display more than a minute cleanly"*. The digits are lanes, two poses
a second at most, and the A/B against the speed pass's tree put form (ii)
inside the rule on both cards (CGA MILL 4.02 missed refreshes a second
against 1.89 - 3.09). The owner liked the digits and asked for the static
art to be more integrated - *"that part is cheap; so we can afford to have
it look very good"* - and of the candidates picked *"the middle with the
longer pole"*.

Then: *"Let's give clocks collision; if it looks solid and has height we
shouldn't just roll through it."* The cheapest honest form was to make a
clock a bumper post that does not kick: the same circle, the same push and
restitution, seven guest bytes to record its cell under the bumper's kind.
The first build let the reach climb onto the clock's top as a launch, and
MILL's part grew 462 packed bytes past its cap for a place nobody would see
as somewhere to stand - so a clock's post is taller than anything reaches,
and nothing lands on a crystal ball. FIRST, the smallest course, is all
scripted runs; of its two clocks the one that survived is the one in the
only cell no script crosses.

## 2026-11-15 (wave 8a: the face moves out)

Wave 8 starts with room. The plan's 8a takes the desktop's code out of the
resident image into a code PART, fetched on the desktop and dropped before
any course, so a play never pays for it. The first decision was what to
move: the plan named the face, the save, the demo checks - but 8b rewrites
the save and 8b and 8c replace the face. Moving code only to delete it is
wasted work, so 8a moved the FACE (the code 8c will rewrite, now to be born
in the part) and left the save and the demo files resident until their
rewrite: each of those either claims memory, which a part may not, or runs
inside the bracket with a course held.

The mechanism is PiXEL's linked part, taken whole: a flat binary with a
vector table at its head, far-called through the claim's code alias so it
runs unchanged on kern_mega, reading its own strings through CS and the
package's variables through DS. The link tool that tells the part where the
package's variables are grew two options for it - another source, and the
package's constants as well as its bss - and still refuses to name a code
label, so a call into the package from the part cannot assemble.

The one surprise was the paint after a play. The kernel restores the
desktop before the bracket returns, and so asks the window to paint while
the course is still in memory; the shell part may not be fetched beside a
course. So that paint is put off, and made once the course is dropped and
the part fetched again. Three rows had set a breakpoint on the face's
`bz_line` before a play; the part can come back somewhere else, so they now
arm it from the resident door, where the part is known to be held.

Measured: the resident image 2,604 bytes smaller, the file 282 bytes
larger, and on kern_mega's Hercules the face drawn from the part with no
exception charged to the package.

## 2026-11-15 (wave 8b: several finishes, and a pathway you roll across)

The plan's pathway was a graph walk: the ball sitting on a node, the arrows
jumping it to the next. Building it would have meant a step mode of its own
in a frame loop that has been tuned for a year. The owner had said the
pathway was a prototype, so it was built the other way round: the pathway
is a COURSE, and the ball rolls across it with every rule of physics. A
node is a finish whose exit number is the node's number, so rolling onto
an open node ends the pathway's play the way a goal ends a course's, and
the loop plays that node's course next. The frame loop, the camera, the
lanes and the ball box are all a course's; the new code is the loop and a
gate that lets only an open node finish.

That needed courses with more than one way out first. A goal or a cup now
takes an exit number; a goal cell keeps it in four bits of its flags byte
that had always been zero, and physics writes it beside the goal flag.
TRIAL's goal column was split in two to test it, and the pathway uses that
split as its first branch: TRIAL's back cell leads to MILL, its front cell
to the PLAYGROUND, and both lead on to MOON.

Each node's state is shown on a sign beside it: the crystal ball the owner
liked for the clocks, holding one glyph instead of digits - empty for
locked, a ring for open, a tick for done. The pathway's own clock shows the
lives. The map holds five nodes because a window may show six lanes at
most, and the lives take the sixth; PEAK waits for a bigger map.

Everything happens in one full-screen bracket: no trip back to the desktop
between the map and a course. A fetch inside the bracket may not toast, so
the parts library grew a define-gated byte that keeps it quiet there.
Enter on the face now starts the game; F is the free play Enter used to
be, and every row that meant a free play presses F now.

Measured: the loop and its tables cost 496 bytes of image and 24 of bss.
A new row, `bonanzapath`, plays the loop on both cards - a locked node
rolled over, FIRST finished by the autopilot opening TRIAL, an Esc costing
a life, the last life ending the game with the memory as it was - and its
red arm (the gate removed) goes red where it should.

## 2026-11-15 (wave 8c: cards, slots, exploration and medals)

Inside the bracket nothing may draw with the desktop's routines, so the
game had no way to put words on the screen. It has now: before the mode is
set, the desktop font's glyphs are copied out, and a small writer puts them
straight into the page the display shows - one routine for both cards,
because a text cell is a word of video memory on each (eight two-bit pixels
on the CGA, eight pairs of the Hercules' pixels). A card is drawn over the
frozen frame and the next frame is drawn whole, which takes it away with no
restore of its own.

The first card was PAUSE, with a retry and the map; then an intro card while
a course loads, a result card with the time and the exit, and GAME OVER.
Two bugs on the way were worth their lessons. A new include file was not in
the package's Makefile rule, so an edit to it rebuilt nothing and the tests
read a stale package against new symbols - the build rule now names it. And
a routine inserted between two procedures broke a fall-through: the
pathway's setup had always run on into the course fetch below it, and with a
new routine between them the pathway was never fetched. Breakpoints on the
handful of routines involved found it in one run.

Then the slots and modes: three save slots on 1, 2 and 3; E toggles the
slot between TIMED and EXPLORE, where every node is open, no clock runs and
nothing costs a life; X twice erases a slot. Medals come from each course's
route until the owner times them (gold at 1.15 times the autopilot, silver
at 1.5), and a node's sign turns silver or gold with the slot's best.

Left for the front window proper, with the owner's art: the tour's removal
and the artwork band.

## 2026-11-16: lanes at scale, and wave 8 was a misreading

The owner read wave 8's result and found two misreadings. The first was
an engine limit: the window bound counted every lane the same, so the
pathway held five nodes "because a screen can show at most six signs".
The brief meant 2 - 6 ACTIVELY ANIMATING items a screen, with slow ones
(a crystal that changes once a second) cheap enough to have many, and
maps with many more than six. SPEC.md 128.19.10 is the rework, all six
items approved: lanes bounded by RATE (rotors at most 6 a window, pose
changes at most 6 a step); the tables sized by the largest course; a
full write that syncs the shown window only; a binary-searched owner
index; no clock cap; and every lane walked only when something MARKED it.

A STRESS course in a private tree (85 posts, 2 clocks, 89 lanes) was the
instrument, measured on MartyPC's CGA. Before the marks, rolling among
the posts cost the walk 17 - 25k clk on 22 frames of 80, because one lit
post made every other lane in the range pay about 800 clk to be skipped.
After them, the most is 10.1k, on 1 frame of 80, and MILL is no worse
(a mean of 3.5k against 3.8k). The marks' first run of the rows went red
in exactly the place they should: `bonanzawheel`'s beam sweep KICKED a
post by poking `bz_pkick` and marked nothing, so the walk never saw the
kick. Every harness poke of lane state now marks the lane, as the guest's
own writers do.

The second misreading was the pathway. It is a Star Fox-style path
screen, not a course you roll across: the exit taken picks the route,
the marble auto-rolls along branch art between glowing pads, the camera
pages vertically, and locked or secret routes are drawn that way. The
cards also go, because they froze the screen; a flashing finish clock
replaces them. The plan's "Wave 8 rework" holds the design and ten
questions, and nothing in it is built until they are settled.

## 2026-11-16 (the title screen: the brief and the contract)

The owner sketched the title screen in Paint and wrote four little films
for it: a rubber ball dropped onto a high platform that rolls down a ramp and
springs back up; a steel ball that lands too hard, is stunned, misjudges a
spring over a pit and has to take the tube instead; a glass ball that does a
lap of the high platform until it gets careless and shatters; and a rubber
ball that runs the whole screen - a boost, a spring over the pit, behind the
ramp, through a hidden tube, a windmill, and a last boost over a tube's mouth
into the void. The title is a course nobody plays, with the lettering and the
key hints painted into it; it never scrolls; a demo of a real course follows
each film; a song ends exactly when the film does.

**Observed, reading the tree first.** Three findings made the design small.
The boxes the ball is drawn through were already clipped to the window, so a
camera that does not follow the ball needed no new clip at all - a ball off
the glass is simply not drawn. Every course picture is at least 512 pixels
wide, so the glass shows 320 of them on the CGA and 360 on the Hercules, and
the rest is where the balls can roll off and where a hidden tube can carry
them round. And a spring's power was already set per spring.

What did not exist: a demo is only a list of key presses from the course's
start, so it cannot drop a ball from above or begin with one already moving.
The title demos get a start block of their own - position, velocity, a
respawn cell - and the build writes their course identity itself, because
that identity is a checksum over every pixel of the picture, and the owner
expects to repaint the art.

**Decided** (SPEC.md 128.23): the title is a course after the pathway; a
`view` statement pins the window; `art` paints a committed pixmap over the
finished picture; a `label` lane shows the slot digit; four `.bzt` demos of
exactly 832 steps (15.23 s); a seventh song of exactly that length whose
last pattern is silence. Enter on the desktop face opens the title, P plays
and the game returns to the title.

**Tested so far: nothing on a guest.** The contract passes `checkdocs`.

## 2026-11-16 (the title screen: a course, four films and a song)

**The layout took five tries, and the reason is worth keeping.** The sketch
is drawn straight on: platforms in rows across the screen. An isometric
course has no "across": a tile's x runs right-DOWN and its y left-down, so
a low platform at the screen's lower left is one at a large y, not a small
x - the first try put it top left, exactly where the lettering goes. The
second lesson was size: a tile is 32 x 16 pixels and the CGA window 320 x
200, so the screen is about ten tiles across, and every first draft filled
it twice over. What survived: the pillar with the windmill in its face,
the high platform up and to the right with two tube mouths on its back
row, a strip under the sky with the brown tube's entry, the lower left
platform with a spring aimed over a pit, and a short steep ramp with a low
row behind it.

**The four films, on the model.** Each is a start (where the ball is, how
fast it goes) and a list of key presses, written by a script the model
plays: "steer through these tiles until a spring fires", "hold left-up
until the windmill takes you". Three of the owner's films came out as
written. Two bent: the steel ball is too heavy to get a speed that clears
the platform's last tile off a spring, so it is sprung, lands on the edge
stunned, and rolls into the pit; and the rubber ball arriving at speed
bounced clean off the course to the east, so the hidden tube went where it
was going - its mouth in an off-screen rail on the right, which is the
owner's own guess ("hidden tube offscreen?"). A ball that shatters at the
end of a film respawns OFF the glass, so it is not seen again.

**Measured on MartyPC's CGA**: the window held still for a whole film (R0
64, c0 51); S, 1, 2, 3 change the slot and the label's digit with it (the
first attempt changed the number and not the picture: a clock's lane is
skipped while its second has not changed, and the title has no clock); P
plays the game, its Esc comes back to the title, and Esc there leaves.

**The song** is G major, 832 sub-ticks to the step, the last bar a ball
bouncing to a stop; a fifth, silent pattern is where it loops, so it ends
with the film. The session cannot hear it: the WAVs went to the owner.

**Not yet**: the row that proves all of this (`bonanzatitle`), the
Hercules on the guest, and the guest's replay checked step by step against
the model.

## 2026-11-16 (the title screen: the rows, and a run that tested nothing)

`bonanzatitle` was written red-first and its red arm stayed GREEN twice
before it bit. The first broke the window's every-frame hold, but the ball
never left the camera's rest band in 40 frames, so nothing moved; the second
compared the flag against FFh where the code jumps on equal, so the "broken"
build fixed the window anyway. The third skips the first frame's placement,
and the window lands at (0, 36) instead of (64, 51). The row also caught a
race of its own: the bracket's restore can paint the face before the title's
tail has fetched the desktop's song back, so the claims were read one disk
read too early - it now waits for the song.

The first scoped soak reported twelve failures in eight minutes, and none of
them was about the title: the tree had been merged with the pathway session's
work WHILE the run read it, so every row assembled a probe from the new
source against the frozen run's old tables. The lesson is the soak's own
rule, learned the expensive way: nothing touches the checkout until the run
is finished. The second run, on the merged tree, is the plan's T5.2.

## 2026-11-16 (the title screen, round 2: the owner watched it)

The owner liked the music and the letters, and asked for the letters lower:
the bob took the tallest of them off the top of the glass. `bbtitle.py`'s
`TOP` went from 10 to 16. The letters now sit on lines 4 - 44, and the
closest scene pixel is 9 px under them, so they still fit at their size.

**The black flash was two things.** A respawn CUTS the camera, which is a
full write, and a full write blanks the video for its frame. That is right
on a scrolling course, where the whole window changes, and wrong on a fixed
one, where nothing does: the glass went black for a frame at every death,
which read as the demo ending. `bz_camera` now skips the cut on a fixed
window. The second flash was the gap between plays. The glass lit again for
the last frames of a play and then went dark for the load. Now `bz_tround`
blanks once a play is closed, and the next play's first frame is the only
thing that lights it. A glass ball's shatter is therefore seen to the end.
`bonanzatitle`'s new check 4b counts the full writes in a demo with a fall:
there must be exactly one.

**The demos changed because the course is not the sketch.** The brief was
written against a rough drawing, and the owner said so: the demos work
better a little different. Demo 1 lost its pause and now ends off the glass
to the right. Demo 2's steel tries the gap from the spring and fails, and
the respawn puts it back on the SAME side. A half-unit step from LL down to
LS lets it reach the brown tube without jumping, so it never seems to
jump the gap by dying. A ramp was the first try, and it broke the occluder
limit: six records in one block where four are allowed. Demo 4 starts a
tile further north. Its hidden tube's mouth moved to the glass's bottom
edge, where its sprung bounce lands anyway: every bounce after the spring
went to row 16 however it was steered, so the mouth went to the ball. Its
boosted bounce off the windmill run now clears the brown tube's mouth and
leaves to the left.

**Tested**: `bonanzatitle` PASS on CGA and Hercules (with 4b), the course
selfcheck (item 13 and its four controls), `bbtitle.py --check`. Not looked
at by the session on the glass: the owner's eyes are the check of how
the new films read.

## 2026-11-16 (the title screen, round 3: a drawn path)

The owner sent a screenshot with the changes drawn on it: the plaque moved
down and over, two patches outlined in green, and a red line for demo 4.
Mapping a 4x screenshot back onto the course is the projection run
backwards: a screen point and a floor height give one cell. The green
patches were a 2 x 2 corner of LC and two cells of the south rail, both
beside the pit. They made the gap read as floor, so they are gone, and the
pit now shows as a pit from LS's step to the bottom of the glass.

**The windmill's exit came round to face the viewer.** It used to shoot
the ball back out to -x, behind the pillar, which read as going backwards.
The tool already draws an arch on a wall face for a windmill whose OUT is in
front of its house along +x or +y, so the exit moved to (14, 11) on the
pillar's +x face, and the ball comes out rolling the way it went in. The
hidden tube's mouth moved to the bottom right, where the red line leaves
the glass. Its first place was refused: a tube's body must run in walls, and
(21 - 23, 10) are floor, so it went to (23, 11) against the east rail.

**Demo 4 was found by search, not by hand.** The start state (position,
height, velocity) was swept over 1,296 combinations on the model, each scored
against the red line's three landings. The best lands on the step, on LC
and on the front floor, within half a tile of each mark. The windmill's
blades are periodic, so the entry was timed the same way: a set of waits and
approaches, keeping the ones with no wall or knock event before the capture.
Two circles of UR fill the time so the last bounce leaves the glass about a
second before the demo ends. Removing LC's corner broke demo 3's route (it
rolled over the corner), so it goes down the step instead, with a longer
pause on UR that keeps its shatter near the end.

**Tested**: the course selfcheck (item 13, its controls), `bbtitle.py
--check`, and `bonanzatitle` PASS on CGA (it drew the new demo 4, the guest
equal to the model at its end, one full write) and Hercules (demo 3). One
boot to look: the plaque, the label and the arch on MartyPC's CGA.

## 2026-11-16 (wave 8R: the path screen, built by seven agents in an afternoon)

The owner answered the ten questions, and the answers made the design small:
pages scroll only when the marble leaves them; it stops at every pad; a
diagonal route answers both of its arrows; gates, not dither; a secret route
appears as it is first rolled; each finish kind has its own rule, and a
checkered finish lets the ball roll off an edge without dying. Mid-build
they added the last of those, and that the screen must not scroll during the
finish.

SPEC.md 128.22 was written first, then the work fanned out
(`story-fanout`): the course tool (Opus), the finish sequence, the cards and
save, the sounds and the art (Sonnet), then the guest's pathway (Opus) once
the tool's formats were fixed. Every branch got an independent Opus
verifier, and every verifier found something real: the art's picture origin
had its sign wrong; the finish froze the windmills while the ball rolled on
and turned a timeout into a finish when a cup was met; an EXPLORE save
emptied its slot, bests and all; the re-stamp of the old demos would have
accepted any edit that left a replay unchanged; the pathway kept a stale
retry, so a later Esc retried instead of costing a life.

A title-screen session worked on the same branch at the same time. The two
sessions traded messages instead of editing each other's routines: one
camera flag each beside the other's, its slot label turned into our new SIGN
lane, and a song order agreed before either pushed (victory 6, attract 7).
The merges were mechanical because of that.

The sound agent found a bug from the first sound commit: the music tool read
every `;` as a comment, so 21 effects had only ever played their first
segment. The fix makes them whole; the owner has before and after renders to
judge.

The final pass ran fifteen rows. The new failures were all in tests, not in
the game: the rewritten `bonanzapath` had never run, and its first run read
the pathway's frames as the finish's, because a host compile in the middle
let the whole 2-second sequence go by. A wheel scene that had SKIPPED on every
soak since wave 3 ran for the first time, because TRIAL's new finish clock
gave it a lane to judge, and its plan put the ball in the camera's dead zone.
The one perf failure was older than the wave: the same late frame appears on
the commit before it, the open item wave 10 owns.

What it cost: the resident image 36,184 -> 39,897 bytes across the
afternoon, the title screen's own code (128.23) included; wave 8R's share is
the finish +343, the cards and save +513, the sounds +161 and the signs,
camera, follower and loop +1,832 net (2,849). The bss 9,080 -> 10,087, most
of 8R's part the lane tables the pathway's 23 lanes size. The pathway part
is 6,410 bytes packed.

## 2026-11-16 (the title screen, round 3b: something to do on UR)

The owner liked demo 4 but found the two circles of UR dull, and asked
for ideas. The one taken was theirs: the ball makes a run at the back rail
and boosts, its HIGHEST bounce, and still falls short. A boosted bounce
off UR rises 9 px; the rail's top is 24 px up, so the miss reads at once.
Then it comes back round the right end and runs along UR's front edge,
hanging over the drop, and goes smoothly into the windmill. The behind-the-
ramp loop was turned down: the strip behind the ramp exists but cannot be
seen from this view, and the spring back up is demo 1's.

The edge run needed the authoring tool to aim at a point INSIDE a cell, not
only at its centre: `(16.3, 8.99)` is that spot of the cell's floor. With
the centre-only points the autopilot cut the corner and the ball never came
closer than 0.6 tile to the edge. With points on the edge it runs with its
centre 0.1 tile from it. The pause after the boost and the route were swept
again against the windmill's blades, keeping only runs with no bump.

**Tested**: the build's demo checks (every expect), and demo 4 on MartyPC's
CGA, found on the seventh title round: the guest's end equal to the model's,
one full write.

## 2026-11-16 (wave 9: the contract)

Wave 8 was rebuilt because its plan and the owner had drifted apart, so wave
9 began with a review of the plan before any contract. The plan's wave 9 had
been written two days and a whole rework earlier, and the review turned up
places where it no longer described the tree: the "at most 6 lanes a window"
limit that 128.19.10 had already replaced with rate bounds, a claim table
already full, and a test course that was going to be thrown away.

The owner's framing settled the scope: this is the wave that lets every
prop, tile type and mechanic be built without overloading the renderer or
bloating course size. Their answers made it bigger and more concrete: one
real family end to end (the glass: a cracked tile and a path that appears
when rolled onto), and PICKUPS as a second to prove the recipe works; every
element declaring how it resets, so nothing can trap the player; a pickup is
part of the course, so a best run may be a hard trick to grab one; the jump
pickup STACKS with the boost, *"fun isn't always being strict"*; today's
props moved into families before the courses start; PLAYGROUND as the only
test course, since the current ones are to be dropped.

**The 12 px question.** The owner asked why a jump could not go higher than
12 px, when a fall plus a boost already does. It cannot be a height limit:
the tool's occluder records are grouped in 8-line blocks from a top margin
the tool never chose, and raising the Hop had only moved that margin. MOON at
three Hop heights gave the same eight record counts, rotated
([BONANZA-APEX-2026-11-16](../reports/BONANZA-APEX-2026-11-16.md)). The real
ceiling is the vertical speed cap, about 47 px. The fix is the tool trying
all eight alignments, and it goes first.

**Claims.** A play already holds eight of the eight claims one program may
have. The owner remembered a 16-claim limit: it had been 16 once, while
regions came from a pool of their own, and is 8 (12 on kern_mega) now. The
remedy is an ARENA in the shared parts standard, sized to what the launch
needs and grown with `MEMP_REGROW` (which survives the KB doors' withdrawal
as a verb of the paragraphs call, carrying the bytes when it must move the
block). Only the small parts go in it: one block holding the course and the
pathway too would need about 105KB in one run, where today the largest run a
play needs is the course's 47KB. Reading the fetch code for this also found
that `BZ_CRS_MAXCLAIM` leaves out the victory fanfare's claim.

**Two sessions, one engine.** The diagonal tiles are being built at the same
time, in the same physics and tool files. The two sessions agreed an order
through the owner: the Y0 search lands first, the hook table before the
diagonal's guest wave, every hook placed outside the routines the diagonal
changes. The CELL overlay that lets a broken tile read as a hole without
writing the grid sits at the start of `bz_wtail`, the one routine every
window refill ends in and the diagonal does not touch.

**Measured for the contract** (`make bonanza`, `a5bd683c`): image 40,181,
bss 10,660; the balls unpack to 31,168 bytes and pack to 5,974 with LZB.
Nothing of wave 9 is built yet.

## 2026-11-16 (wave 8R, round 2: the owner played it)

The owner played the path screen and sent eight things back. Seven agents took
one each; every branch but two small ones got an Opus verifier, and each
verifier found something. Gates that read as gates (a frame with an open middle,
tilted, a 3/4 view on the edge-on routes). TRIAL's new finish clock had walled
off its second exit, which is why the owner never found it: the tool now
proves every finish reachable with its clocks in place, and the verifier moved
the clock again when the first new cell turned out to sit on the autopilot's
route (the demo's finish moved from step 499 to 796 and nobody had checked).
The marble not rolling right was temporal aliasing - 6 px a frame reads as 2
backwards on an 8-phase texture - folded on the pathway only. The finish now
DITHERS the ball out over 0.73 s while it rolls on (the owner asked whether the
machine had the power: measured, 69.7k of a CGA's 79.5k-clock refresh at the
worst fading frame, no refresh missed). The music under the info card ran at
half tempo because the wait sampled the PIT once a frame against an 18.3 ms
sub-tick. The save holds 23 courses (24 made the file a whole sector, and
`od_write` then rewrites the FAT and the entry on every save: about 1.6 s
against 0.4), and reads no older format (the owner: nothing is released).
The four known-broken checks were all fixed, none removed; and a flaky sound
row turned out to be the test racing FIRST's own 15-second clock.

Diagonal tiles became a contract (SPEC.md 128.24) with pictures, and the owner
chose HALF and QUARTER cells, with CHANNELS (a tile that cradles the ball) as
the next core type the format reserves room for. Wave 9 started in another
session the same afternoon; the two sessions trade file and routine lists
through the owner.

## 2026-11-16 (wave 9, story 9.0: the Y0 search, and a camera guarantee that was luck)

The search itself was small: compile each of the eight alignments as far as
the merged occluder records and no further, keep the one with the fewest
records that meets the bounds, then compile it for real. The trap check,
which is most of PEAK's compile time, runs once. Every play course but BENCH
and TRIAL chose +4; PEAK's compile went from about 20 s to 26 s, and the
demos re-stamped without being re-authored, because the identity they are
checked against is taken with no occluders.

Then the camera check failed, and only on PEAK. Inside a tube the camera
pans straight to the exit's framing with the heavy rule switched off, so
the exit has nothing left to do; the tube-exit guarantee says a pan still
running at the exit is never held back afterwards. That had been MEASURED
on 22 exits and never built: the heavy rule comes back on at the exit, and
no heavy frame had ever happened to land in the 90 frames after one. The new
alignment moved the occluders, so it moved which frames are heavy, and one
landed one frame after PEAK's cannon exit. The fix makes the guarantee true
by construction: a pan a tube made fast is never withheld until it ends. It
costs one byte on each of the camera's two axis records and two instructions.

The pre-aim's own control had been riding on the same luck: switching the
pre-aim off only ever failed the guarantee through the heavy rule. Measured
directly, what the pre-aim buys is the pan finished inside the tube: with
it, 247 camera steps are left in the 90 frames after all the exits across
every demo and autopilot; without it, 458 (MILL's chute 2 against 32). The
control now asserts that, and a new one removes the exemption.

Three of the tool's deliberate refusals also leaned on the alignment: two
lanes sharing blocks, a start window with no calibration corner, and the
wave 5b byte comparison. They now pin it, and a real course whose best
alignment a later rule refuses falls back to the next best.

**Tested** (host): `--selfcheck`, `make bonanza`, `bonanza_ring.py
--check-reds` (both camera arms' models red at their checks, every arm
assembled), `bonanza_phys.py --check`. **Not yet run**: `bonanzaring`'s
camera leg on MartyPC, the guest's `BZL_PRE` against the model; it is in
wave 9's final pass.

## The window (SPEC.md 128.26; the plan BOUNCE-BONANZA-WINDOW.md)

*2026-11-16, a session beside wave 9's.* The owner's brief: the desktop window
"up to spec", and the development keys and decided experiments out of a
player's way. What the window had been was a page of thirteen lines of key
hints and instrument read-outs - the right face for the waves that built the
engine, and the wrong one for somebody who has just double-clicked a game.

**Decisions.**
- The window's art is drawn from code (`tools/bzwinart.py`), as the title
  screen's is: the in-game lettering's own strokes (imported from
  `bbtitle.py`, not copied) at 0.62 of its size, re-sampled at the
  desktop's resolution, and a ledge with the rubber marble from
  `bonanza_assets.py`'s ball formula. Two aspects, because a 640 x 200 CGA
  desktop's pixel is the game's pixel halved across and a VGA's is square.
- The instruments stayed: their keys and their text face answer to a
  harness byte, `bz_dev`, which every row pokes through `bonanza_ring.Bz`.
  Deleting them would have deleted most of the suite's eyes.
- A toggle's "check mark" is `* `: the kernel's pull-down has none and its
  font has no tick (SPEC.md 12.2, 45.17.1's precedent).
- The desktop's song and `title.bmu` are gone; every song moved down one.

**Observed.** OSAPI_GFX_BLIT1 at an x off a screen byte wrapped the band's
first partial column onto the end of each row (MartyPC's CGA): the B of the
title lost its stem and a bar stood after the A. Every picture is put down
at a byte's start now; the kernel's unaligned path is a finding for its own
owner, not fixed here.

**The owner's second look** (the same afternoon): the art "perfect", the
button moved into the empty space left of the ledge - drawn by them in
Paint "by feel, not math", which came out as the button centred left of the
ledge with its middle on the ledge's top face - and the window made a fixed
size, because the art does not scale. The About card lost its description
line and gained "Contributed by Elendilon".

**Lessons for whoever drives these rows next.** Never rebuild `build/` or
merge into `apps/` while a soak reads them: one rebuild mid-run turned 13
rows red at once (their symbol tables described another image), and one
merge cut a row's second leg. And the attribution of a red is a run at the
base, not an argument: `bonanzapath`'s red was already there, and
`bonanzaring`'s MILL coverage was not.

## 2026-11-16 (grounded faces: the courses stop floating)

*SPEC.md 128.27; the plan's story 9.10.* The owner looked at the courses and
asked why everything floated. Every face over the void hung three units
(24 px, the tool's `FACE8`) and stopped, so a terrace six units up and a
field at the bottom read the same: thin slabs in the dark. The question was
what deeper faces would cost, since a face is picture, picture is blocks, and
blocks are bytes on a disk that was already being counted to the byte.

**Priced first, on MOON, MILL and PEAK** (a scratch hook in `draw_ops`, each
variant compiled whole; LZ4 bytes of the stored part against today's):

| variant | the face over the void hangs | MOON | MILL | PEAK | picture lines |
|---|---|---|---|---|---|
| today | 3 units | 10,157 | 9,406 | 12,552 | - |
| fix9 | 9 units, everywhere | +233 | +224 | +74 | +16 each |
| near3 | to the lowest floor within 3 tiles, less 3 units | +107 | +143 | +1 | 0 |
| **ground3** | **to ONE plane a course: its lowest floor less 3 units** | **+47** | **+102** | **+78** | PEAK +56 |
| fade3_2_2 | 3 units solid, then 2 at half and 2 at a quarter dither | +667 | +384 | +494 | 0 |

The surprise was that the deepest look was among the cheapest: a column's
interior repeats, and the block pool shares it, so a taller face is often
fewer blocks (`FIRST`, `TRIAL` and `MOON` came out SMALLER in RAM). The
dithered fade, which looked like the gentle option, was the most expensive by
far - every dither row a block of its own.

**The owner chose ground3**, with three riders: floating stays possible but
only on purpose; there is no per-course opt-out; and the course budget, not
the look, is what gives. MILL at 9,508 LZ4 was 96 bytes over its 1.5 x line
of 9,412, and the owner's words settled it: "we wanted to hit 'seconds per
course for one 360k disk for 20 courses' but it is very obvious that is not
going to happen now. So that limit is the thing wrong; we'll end up with less
courses, or two disks." The 1.5 x refusal became a reported figure; the
65,024-byte part and the occluder bounds stayed refusals.

**Decisions.**
- `float <shape>` is a region statement in the grain of `surface`: whole
  cells (a cell's faces float together, so `half` is refused), applied after
  every room and hole, refused when it floats nothing. The PLAYGROUND's
  chamfered platform floats - a dead end out over the void - which also kept
  its picture from growing 40 lines.
- The ground is one plane for the whole course, counted over the secret
  routes and glass tiles too, so a reveal draws to the same floor.
- The kill height did not move: it was always a separate "3 units" of its
  own (`_near_low - 6` half units), and the physics, the grid and
  `BZ_PHYSV` are untouched. The finish-sequence fall drawing over a deep face
  is accepted.

**Observed.**
- Every grid section decoded byte-identical, but for five PLAYGROUND cells
  whose `OCCG` flag came on: the brake strip's column now really stands in
  front of the basin's back corner, so a ball there can be hidden - the
  picture changed what can occlude, and the flag followed. Not physics.
- Every identity moved (the identity covers the picture), so the three
  authored demos were written again with `bbcourse.py author`. Their runs
  came out identical; only the `ident` lines changed, which is the replay's
  own proof that nothing physical moved. PEAK's demo had been the last one
  shipping RE-STAMPED from its pre-clock course; it now carries its own
  identity and the re-stamp has nobody left to serve.
- Wave 5b's cross-commit check (the old tool run from git on today's texts)
  still holds byte for byte with the ground rule switched off - the
  cleanest evidence that the rule touches the faces and nothing else.
- The tour's six courses: +266 bytes LZ4, +110 LZB; PEAK's picture +56 lines.

**Tested:** host only - `make`, the bonanza disk, `bbcourse.py --selfcheck`
with its new item 14 and the red arms (each broken on purpose, each seen
red), previews on both cards. The emulator rows are the final pass's.

### Wave 9: the recipe corrected, and the checks made fast (story 9.7)

**What the recipe missed.** SPEC.md 128.25.6.8 was written before any family
existed, as six steps. GLASS took it first, PICKUPS second, and the crack
bug a third time; story 9.7 rewrote it as eight. The new steps are the ones
nobody thought of until a family needed them:
- **the reach** - a family that changes where a ball can go needs a pass
  after the tool's reach, or the compiler proves a course against a ball
  that cannot do what the family lets it;
- **the marks** - a hook that changes a tile's pose has to WAKE the walk,
  not only mark the lane. The owner saw what that costs: steel sank through
  a cracked tile with no hole ever drawn, because a still camera skipped the
  walk that would have drawn it. Now there is one resident door,
  `bz_fmark`, and the unicorn half of the physics check fails any step that
  moves a pose without it.

Smaller corrections:
- the family ID is the table's order, not a choice;
- physics changes go in working values, never the shared material table;
- what a part cannot do itself (a cue every frame) is resident bytes, priced
  as such.

**A layout change can disarm a test.** Moving the pickups yard on
PLAYGROUND (and then grounding its faces) left the camera's hysteresis
control - `camhyst` in the ring check, `nohyst` in the self-check - with a
scenario where even a camera with no hysteresis never reverses. The camera
was fine; the test had stopped being able to fail. It was found because the
whole chain ran at a merge, and is now a line in the recipe's proofs step.

**The checks.** The owner: *"when every action invokes another action that
takes this long ... it slows everything to a crawl."* Measured first:
- 69% of the self-check was course compiles, and wave 9's own alignment
  search was 1,287 of its 1,896;
- the ring and physics checks spent 72 - 94% compiling the shipped courses
  again.

A compile cache keyed on everything a compile reads, forked sections a core
each, and one shared reach for the eight alignment probes took the chain
from **23 minutes to 5.5**. Every output matched line for line, and the built
art and package were byte-identical. Nothing that ships is built from the
cache. docs/TESTING.md now says which checks each kind of change owes: a
guest-only change about 75 s, a merge of verified branches under a minute.

### Wave 9: the final pass (story 9.9)

**What one pass found that no wave did.** The BONANZA rows ran once, scoped,
in the background: 18 rows in 32 minutes. Fourteen passed. Each of the four
failures was a different kind of thing:
- **A real bug on kern_mega.** The family lookup adds a segment distance to
  the part's base. In real mode that distance is 0; on kern_mega it is the
  selector pair's -8 (FFF8h), so the sum always carried. The leftover carry
  read as "not found", and every course with a resident family - MILL,
  MOON, SUMMIT - silently refused to start. No MartyPC row could see it,
  and no wave had run families on kern_mega. One `clc`, one byte.
- **A test that had been wrong since 9.4.** The ring's reference still read
  the ball files raw, but since the ball generator they ship compressed. So
  its expected frame drew every resting ball as a black hole. The glass leg
  is the row's first check, which is why it showed now.
- **A test disarmed by a layout change.** The camera hysteresis control's
  PLAYGROUND scenario no longer reversed even without hysteresis. It was
  re-anchored to a column at step 1028, now on both cards (the
  self-check's version used to require only the CGA).
- **A registry with no lines for wave 9's claims.** Three of the five claims
  were older than the wave. The honest verdict on the arena is debt: it is
  pinned for as long as the window is open.

The four re-run green. `test-full` failed only `guidelock-full`, on
WireArena's undescribed package - older than this wave and outside it - and
`budget-check` was under on every kernel.

**Tested:** the scoped soak and its re-run (MartyPC, 86Box for kern_mega),
`test-full`, `budget-check`, and the host checks at every merge. **Not
tested:** the owner's play of PLAYGROUND's new sections, and the pickups
yard in its new place on real glass.

## 2026-11-17 (the tour and the face stop counting the courses)

**The story.** BONANZA is about to go from six tour courses to about
twenty, and a seventh would not even have assembled. Two things tied the
face to the course count. The tour was every course but BENCH, and MAIN,
the old text face, gave each tour course a scorecard line. Six courses
made thirteen lines, exactly what a CGA window holds, and `bzface.inc`
refused to build unless the line count was seven plus the tour. Since the
window became pictures and a Play Game button (SPEC.md 128.26), MAIN and
the tour only answer while a test row sets `bz_dev`. They are
instruments. The owner: *"1 and 2 seem good; those are both knob/test
only now"*: drop the scorecard, and stop making every course a tour
course.

**What was done (SPEC.md 128.26.8).**
- MAIN is seven lines: the tour line, then the six it always had. The
  scorecard builder, its columns, its strings and its fit check went from
  the shell part. RESULTS still uses all thirteen lines.
- The tour is a named list in the course tool, `TOUR`. The tool turns the
  names into course numbers, refuses a bad list, and writes `BZ_TOUR` and
  `BZ_NTOUR` beside `BZ_CRS_TOURX`. Its content is the same six courses,
  so the save file's tour identity is unchanged (B0E5h before and after).
- `[bz_tour]` still counts the tour's steps. Two places used the step as
  the course number: launching the next course and the `ENTER next:` line.
  Both now look the course up in a small table. The package's table has
  BENCH at byte 0, so kern_small's refused `G` asks for the same course
  as before.

**Measured.** The package image went from 47,097 to 47,110 bytes (+13:
the table and the lookup), with bss unchanged. The shell part shrank
from 12,259 to 12,072 bytes (-187), and `BONANZA.O88` from 117,724 to
117,612.

**The seventh course.** I copied FIRST as `SEVEN`, with its pit moved one
tile so it has its own identity, and passed eight courses to the
Makefile's `BZ_COURSES` in a private tree. The whole package built: 34
part rows instead of 32 (a course part and its shipped demo). With SEVEN
added to the tour too, the package and the shell part still assemble.
Before this change, `bzface.inc`'s assertion stopped both.
`bbcourse.py --selfcheck` passes on the eight-course list. `--sizes`
accepts it too, but its BONANZA.O88 figure fails the same way on the
shipped list. That figure packs only the balls, courses, sound, songs and
demos against `build/bonanza.bin`. It leaves out the shell, the pathway,
the title and the family rows, which are 32 parts against its 26. That is
older than this change, not a course cap.

**Tested:** host only - `make`, `bbcourse.py --selfcheck`, `checkdocs`,
the scratch builds. **Not run:** the emulator rows that walk the tour
(`bonanzagame`, `bonanzaexit`), which were updated to read `BZ_TOUR`.

## 2026-11-16 (shaped floors, C0: chutes and the pit as one table-driven cell)

*Branch `bounce-shaped`; the contract SPEC.md 128.28, the plan
[BOUNCE-BONANZA-SHAPED.md](BOUNCE-BONANZA-SHAPED.md).* The owner had
reserved kind 7 for a CHANNEL (128.24.13) and asked next for a pit "made of
curved sides that you have to enter with enough speed to make it around and
over and fly up the other side". An investigation before this wave rolled
prototype channels built from today's ramps and halves through the model.

**Observed (the investigation, the model's runs).** A channel whose corner
is two ramps folded along the cell's diagonal does not turn the ball: at
384 with no key it bounced back up the run and stalled at 200 - 300. A
grounded-only corner model with the cross-section swept RADIALLY round the
corner's inner point carried the ball round at 190 - 384 in a 2-wide,
14 px deep channel; a 1-wide, 7 px one threw it out from 252. A pure V
never settles - the cross speed flips by 7 a step for ever. A wall capping a
channel's end put five occluder records in one block. And the near lip's
occluders, not the shading, are the biggest byte cost.

**Decisions.**
- One mechanism, not a channel and a pit: the FIELD cell, whose floor is a
  17 x 17 table of heights read through one of the square's eight
  symmetries. A straight, a taper, each corner cell and each piece of a bowl
  is a table; a chute turning the other way is the same tables mirrored.
- The cell's own four bytes carry it: the slopes byte became the shape and
  the symmetry, as 128.10.4.3 had always planned for its reserved kinds; no
  record in section `D`. The tables are a new section `F`.
- The slopes are forward differences of the table - two more byte reads -
  so no multiply enters the floor path, and the bound `|sx| + |sy| <= 7`
  keeps the floor rate under `BZ_VZMAX`.
- A rule the corners force: a cell's edge tests are axis-aligned and a
  corner's bank is radial, so a ball six units inside a corner block meets
  its neighbour's height six units further up the bank and would bounce off
  an invisible wall halfway up. A FIELD centre therefore never blocks on a
  FIELD neighbour (the tool guarantees the seam is exact), and lifts its
  edge test to its own height at the shared point for a plane neighbour - a
  floor at the lip is a lip, a floor above it a wall. The fallback is not
  lifted, so nothing rolls up into a field from below.

## 2026-11-16 (shaped floors, C1 - C4: the tool, the model, the guest and PLAYGROUND)

**Built.** The tool lays a chute or a pit as FIELD cells from one height
function per piece (a straight, a taper, a radial corner, the bowl),
sampled at each cell's 17 x 17 points; each cell's relative heights are
matched against the tables already stored under all eight symmetries
before a new table is added. THE CHUTES test course (a 2-wide chute with
two corners and a 1-wide one with a climbing leg) needs 9 tables for 66
FIELD cells; the pit's 32 cells need 5. The picture draws a field's top as
4 x 4-unit facets and drops every facet that faces away - the near bank of
a channel - so the bottom is seen over the lip, as it would be. The first
render looked right first time; the shading is the facet's normal against
a light from the upper left, in the 4 colours, world-fixed dithers.

**Discoveries.**
- The slope bound bites at a radial corner's 45-degree points, where both
  slopes are large at once: a profile that is fine on a straight is refused
  in a corner. And rounding half up is not mirror-symmetric, so a depth
  passes a corner turning one way and is refused turning the other. The
  profile became a curved bottom and a STRAIGHT bank at the slope the curve
  reached - steepest at the lip, which also makes the lip a crest - and the
  deepest every orientation accepts is 10 px (2-wide) and 5 px (1-wide).
- The model's first guided runs "stalled" at every speed: a coast on the
  ordinary floor is about v / 4 units, so a ball started eight cells back
  never reached the corner. Measured from just before the block, with the
  turn held, the 2-wide carries a ball round at every speed to the cap; the
  1-wide throws it out over the lip at 384.
- The guest was wrong in exactly two places before it equalled the model on
  48,000 fuzzed steps: the tables' offsets were filled by the expander,
  which the unicorn harness (and nothing that hands the package a RAM form)
  runs - so they moved to `bz_crshdr`; and `bz_blocks` must keep DI, which
  `bz_corner` holds across the call and the new height read used.
- Occluder records, not code, are the cost. A facet's top in whole px broke
  the four-records-a-block bound; tops in steps of 8 px, then 16, fixed it.
  A FIELD section on PLAYGROUND hits the RECB 8 layout's 65,024 bytes (the
  identity is taken over it) before anything else: the 2-wide and 1-wide
  chutes fit with 460 bytes to spare, the pit does not. A new course would
  be a TOUR course, and MAIN's 13 lines are full. So the pit is the tool's
  and the harness's only, for the owner to place.

**Measured.** One MartyPC measurement (CGA 5150, logged breakpoints at
`bz_step`): a step on a FIELD cell, median 9.4k clk in the 2-wide chute and
8.5k in the 1-wide, against 8.9k coasting on the apron - about +0.4 - 0.9k a
step on the mean, against 2.6 - 3.5k predicted; nothing to optimise.
BONANZA.O88 +680 bytes resident, +36 bss.

## 2026-11-17 (shaped floors, C5: grounded faces merged in, and a knob build to play)

*SPEC.md 128.28 (renumbered from 128.27, which bounce-bonanza's GROUNDED FACES took first).* The
owner asked for "a knob build with various shapes on a course to try ... a course I can easily
launch". Merging bounce-bonanza first moved three things. A FIELD cell's faces over the void now follow
the ground rule (and `float`) sample by sample along the profile, as `draw_ops` does for a plane. The
per-second budget became report-only, so PLAYGROUND's `target` went back to 30. And PLAYGROUND, with
the pickups yard and the ridge, no longer had room for the C4 chutes: its RECB 8 layout came to 69.7KB
against 65,024, so the section came off and no shipped course has a FIELD cell now.

**Decisions.** The knob (`BZSHAPES=1`) adds TWO courses, because a course holds 16 shape tables and
the shapes the owner asked for need 21 - 27 (a climbing bank chute alone takes 7). SHAPE carries the
2-wide chutes in both profiles and the 1-wide round one; PITS the 1-wide bank chute, a shallow 2-wide
one and two pits, one round a hole and one a dish. Both are a level plate with the shapes set in, so a
ball that leaves one lands on SAFE ground beside it. The pathway is the shipped one put through a sed
script: SHAPE on pad 0, so Play Game then Enter plays it, PITS and FIRST on pads either side of it.
Getting there took six tries against the pathway's own rules - a pad must sit inside a page's window,
a route needs room for its gate's lane, and no two routes leaving one pad may share an arrow key - and
the answer was routes leaving pad 0 straight left and straight right on the screen, both dead ends.


## 2026-11-17 (two-segment courses: a course past 64KB, at no cost a frame)

The owner's brief: unmerged work pushes even PLAYGROUND past the 65,024
bytes one part may be, so a course needs a second segment - and *"this
must not hurt frame performance. Be smart about it."* Plan story 11.9,
SPEC.md 128.30.

**The escape on file was the wrong one.** 128.15.8 had sketched the
two-part course in wave 5b: the picture (map and blocks) in one part,
everything else in the other, "a segment switch per laid group in the
occluder lay, tens of clocks". It was an estimate nobody had built. So
this round started by reading every place the guest touches the course
part and writing down which sections each one reads, and through which
segment register (128.30.2). Three hot loops each read two kinds of
section at once:
- the occluder lay's line loop reads a block line (the picture), the box,
  and a mask (the occluders) - three segments in one loop;
- the wheel's commit reads a lane's pose word (kept in the props), writes
  it into the map and then reads that block's lines, per block;
- physics holds ES on the course for the whole step and reads cells and
  prop records in turn.

Those three chain every section together, so the sketch's split cuts the
first one. Priced from the instructions (PREDICTED), it costs about 400
clk a laid occluder group - up to about 3,600 on a heavy frame - and about
500 a committed lane, and since the code cannot tell a one-part course
from a two-part one for free, every course would pay.

**The split that costs nothing.** Keep the occluders WITH the picture, and
move the one thing that crosses: the lanes' pose maps. They are block
offsets, only the wheel's three map writers read them, and nothing in a
step does. So the PICTURE part is `M B I R K O` plus `L` (the pose maps),
and the WORLD part is `G C D T W P`. Every hot routine then reads one part,
and each just loads a different segment word (`bz_mseg` for the picture,
`bz_cseg` kept for the world, so physics, the families' parts and the
wheel's record reads did not change at all). Both parts carry the same
48-byte header, each offset field naming its section in the part that
holds it, so no header read moved either. A build with no two-part course
assembles `bz_mseg` as an alias of `bz_cseg` and none of the new code, so
the shipped package is byte for byte today's.

The price of choosing it: the picture part has less room than the
sketch's would. PLAYGROUND's picture plus occluders are about 39KB of the
65,024, so about 26KB of growth; past that the next lever is a third part
for the occluders, at clocks (128.30.10, an open question for the owner).

**What was measured.**
- The shipped `bonanzadisk`, built before and after in private trees:
  `bonanza.bin`, `BONANZA.O88`, every disk image and every part `cmp`
  equal. Only `bzcourse.inc` and the shell's `bzlink.inc` text differ.
- A test course, `TWOSG`: PLAYGROUND with its diagonal lane run on off
  the platform's foot (`bbcourse.py twoseg`). One part would be 67,264
  bytes; as two, a picture part of 51,956 and a world part of 15,364.
  `make bonanzatwoseg` builds it as course 7 into a private tree.
- The guest's code with a two-part course: 71 bytes, plus a part row and
  a byte a course of table, plus 2 of bss.
- The hot routines (the writers, the box fill and blit, the occluder
  pass, the wheel's commit and map writers, the slab, the step and its
  window fill) are the same length from the same lines with and without
  the support - the two listings compared. No frame was timed: there is
  no difference to time, and there is no one-part twin of TWOSG to time
  against.
- One look boot on each card (MartyPC, `_gla` machines): at the bracket's
  start the two parts sit in two claims and equal the tool's RAM forms
  byte for byte (the Hercules' after its translation), the identity is
  the tool's 1551h, and the autopilot rolls to the goal in 235 steps on
  both cards - exactly the model's 235 - with both parts dropped after.
- `bbcourse.py --selfcheck` passes whole, with the new item 15 and its
  five negative controls, all refused as they should be.

**Predicted, not measured.** A two-part launch costs one more fetch and
claim - about one more `int 13h` run, under 0.4 s - and nothing else
worth timing.

**Not run** (named for the final pass): the emulator rows. Because the
shipped package is byte-identical, those rows would run yesterday's bytes;
the ones that do read the changed tool or Makefile are `bonanzacourse` and
`bonanzaassets` on the host and `bonanzaring` (its part list now reads
`bzcrs2.lst`).

## 2026-11-17 (PLAYGROUND ships as two parts: what it costs)

The shaped floors and two-segment courses met in one tree: PLAYGROUND got
wave C4's walkway and chutes back, and the radius-3 pit that never fit,
which took it to 65,513 bytes as one part - so it became the first shipped
two-part course (SPEC.md 128.30.11). The owner played it and asked one
question: *what does it cost - the package, the image, any CPU?*

**Three trees, not two.** Comparing the owner's branch (A) with the merged
one (B) mixes two things: the mechanism and the bigger course. So a third
tree (C) is B with PLAYGROUND's old text and demo put back. C turned out
to be A byte for byte - package, shell, `BONANZA.O88` and every disk - so
everything that differs between A and B is the course using the
mechanism.

**What was measured** (MartyPC, the CGA 5150, 640KB, one run each):
- The package: +83 bytes of image, +2 of bss. `BONANZA.O88` +6,450 bytes,
  nearly all PLAYGROUND's packed parts (7,715 bytes of LZB became 11,057 +
  3,026). The 360KB floppy: 124 to 130 clusters of 354.
- The frame: PLAYGROUND's demo through D, 1,649 frames, busy mean 40,455
  clk on A and 40,224 on B, 3 misses each. The routines that run every
  frame or step were checked to be the same instructions by comparing the
  two assembler listings routine by routine. What did change is the
  course's own work: the occluder pass costs 941 clk more on the 23 frames
  it runs, because the course has more records.
- The launch: 0.9 s slower the first time (3.90 to 4.80 s to the first
  frame), 0.63 s the second. Timing each step with logged breakpoints
  showed where it goes: reading and decoding 6.4KB more of packed data and
  expanding 16KB more of RAM. The second part's own fetch is part of
  that, not a fixed toll on top.
- The heap: 16KB less free during PLAYGROUND's play (358 to 342KB on a
  640KB machine) and one more claim (4 for BONANZA, 9 on the heap).

**What making it merge-ready found.** The scratch merge's selfcheck did
not just fail item 15 "by design" - it crashed: items 1, 3, 10 and 11 each
assumed every shipped course is one part, and so did the compiler's own
early refusal, which turned the two-part test course away once PLAYGROUND
grew (its one-part least was 68,613 bytes although its two parts fit).
Each now reads a two-part course whole. Several host checks behind the
emulator rows had the same assumption (the unicorn guest of `bonanzaphys`
loaded the picture part where the world part goes, and `bonanzaexit`
compared the wrong claim); and two of `bonanzaphys`'s drag scenarios
picked the new pit's plate as "the longest level run", because a FIELD
cell's bytes look like a level floor to that search. All fixed; the
emulator rows themselves are the final pass's.

## 2026-11-17 (shaped floors, the picture: magenta, and the floor's grid bending into the shape)

*SPEC.md 128.28.6.* The owner, looking at the knob build: "We might work on the dither visuals a bit."
The first ink shaded each facet against a light from the upper left in six bands - white, white/cyan,
the parity ink, parity/magenta, magenta, magenta/black - and on the glass the chute walls were a dark
checker with lighter speckled edges: noise. The picture blocks were also the largest packed cost of a
shaped course (SHAPE 302 against a flat plate's 85), so the first round of options was asked to say
what each cost as well as how it looked.

**Round 1: eight options, one question about colour nobody had asked.** Solid inks in four bands; a
light from the VIEWER (far wall white, near bank black); the dark band as scanlines instead of a
checker; contours where the band changes; the floor's cell checker carried down the walls a step
darker (`chkdark`); an ordered 4 x 4 dither; and two "Hercules-safe" mixes. Every one was looked at in
2x crops on both cards. The sizes came out within a few hundred bytes of each other (the best saved 56
blocks of the roughly 220 the shapes add): a chute leg one cell along moves exactly a whole number of
8 x 8 blocks, so the straights already repeat, and what does not is where facet edges cut the grid -
which no ink moves. The finding that mattered was in the Hercules column: the card translates by
colour, magenta and cyan are the same half grey there, and a shape drawn in floor colours with black
contours vanished on it.

**The owner's verdict on round 1** turned the question round: "Herc reads well on most of these, so
I'm thinking my 'reading the curve' issue is more color. Of these options, chkdark reads the best,
and, weirdly, outline the second best, with today's the third. Lets try using magenta (in this
palette) only, for the shapes ... All of those sizes were within spitting distance of each other, so
it looks like size savings may be minimal here."

**Round 2: magenta only.** Eleven options, every tone magenta mixed with black or white. The one new
mechanism was a per-pixel map from the screen back to the ground for each facet (three corners give
an affine map), which let the floor's black cell LATTICE be carried over the shape - a pixel is black
where its ground point is in another cell than the pixel above's, exactly as a floor cell outlines the
top edges of its diamond - and let iso-height contours be drawn every few px of depth. What read: the
lattice (the curve shows as the grid bending), contours in a pit (a topographic bowl). What did not:
light-graded tones (the magenta/white and the quarter-magenta mixes turned back into speckle),
scanlines beside horizontal contours (they merge), and a white lip line (too few lip pixels have a
FIELD facet above them for it to show). The owner: "Every single one of those reads much better; it
was the colors. ... mchkgrid2 is the winner of them; it reads clearly, it fits our art style."

**The winner, and its one bug.** `mchkgrid2` is the floor's own checker in two magentas - a white
cell solid magenta, a cyan cell magenta with a black line every other line - with no light at all,
and the lattice over it. The bug the owner found: "There are still blue corners within the bowl, and
sometimes around odd places." The cause was the test for "this facet is the floor": level-ish and at
the CELL's highest point. A cell wholly inside a bowl has a highest point of its own, below the plate,
so its top facets were drawn in floor cyan and white inside the bowl; and gentle facets just under the
lip at chute corners and tapers passed too. The fix gives every FIELD tile its LIP heights beside its
real ones - the piece's own function with the depth taken out (a chute's lip with its legs' climb, a
pit's plate), sampled on the same 17 x 17 points - and a facet is the floor only when all three of its
corners lie exactly on the lip. Those take the plain floor cell's ink by the same parity, so a pit's
square remainder outside its radius is indistinguishable from the tiles round it; everything below
the lip is magenta.

**Measured** (against the first ink at 295a993, after the occluder-cut work): SHAPE 302 -> 243 blocks,
whole part LZB 6,378 -> 5,590, LZ4 7,778 -> 6,990; PITS 348 -> 291, 6,848 -> 5,989, 8,448 -> 7,489.
Every section but the map, the blocks and the offsets into them is byte-identical: the records, masks,
grid and tables did not move. **Tested**: the tool's previews on CGA and Hercules (bowl, dish, chute
corners, tapers, the S), `--selfcheck`, `tests/bonanza_dfield.py`, the shipped and knob builds; no
emulator rows - the picture is the tool's, and no shipped course has a FIELD cell.

## 2026-11-17 (shaped floors: the join rule)

The owner, on the knob build's raised `bank` corner: "The red circled corner looks 'see-through',
because its elevated above the tile below it ... only join into the corner if another tile at the same
elevation exists ... per touching side". The plate rule drew a facet as floor whenever its corners lay
on the lip, and a corner's lip stands a unit over the plate there, so a patch of floor checker hung in
the air beside the raised side face. The rule now asks what the facet JOINS: a lip-level triangle with
an edge on its cell's border against plain floor at the same heights all along that edge seeds the
floor, and the floor spreads over shared edges of lip-level triangles, across FIELD cells too.
**Observed**: SHAPE's raised corner turned wholly magenta and nothing else on SHAPE moved; PITS did not
change at all (its pits' plates and chute tapers all join the plate round them); on PLAYGROUND the two
chute corners at the back edge, over the void, lost their floor patches. SHAPE costs two blocks
(243 -> 245, LZB 5,590 -> 5,596), PLAYGROUND none (LZB 13,474 -> 13,454); every section but the map, the blocks, the offsets into them and the identity is
byte-identical on all three. **Tested**: previews (CGA, Hercules), `--selfcheck` with its new item and
red arm, `tests/bonanza_dfield.py`, the shipped and knob builds; no emulator rows.



## 2026-11-17 (shaped floors: occlusion that happens, and the SHOW rule kept as a toggle)

**What play found.** The owner, on the knob build: no part of the ball was ever hidden on a chute.
The cut was right and the guest never used it: the occluder pass for a GROUNDED ball runs only on a
cell with `OCCG`, and the tool derived `OCCG` over plain floors, goals and split floors - never a FIELD
cell. Every record cut for a resting or rolling ball on a shape was carried, walked past for airborne
frames, and never laid. Two ways out were built and played: **A** (the cut as it stood, plus `OCCG` on
the FIELD cells - a scratch tool, the whole cell over its whole height range) and **B** (the SHOW rule:
draw a ball on a shape whole and stop cutting for it). The owner: *"A is actually better, having now
played with occlusion happening at all. B is still cheaper, in every way; so can we keep it around as a
toggle we can turn on at will?"*

**A, done properly.** `OCCG` on a FIELD cell is now taken at the ball's REAL grounded poses - each
integer point at the floor there, a line higher when the height carries a quarter, margin `BZ_CLIMB`,
over the blocks the guest's pass walks - rather than the scratch form's whole cell. **Observed**: it
sets 80 of SHAPE's 81 reachable FIELD cells (the same as the scratch form: a chute's cells nearly all
meet a lip record somewhere), 50 of PITS's 94 against 56, 55 of PLAYGROUND's 71 against 58 - fewer, and
the same coverage, since the poses the whole-cell form adds are ones no grounded ball holds. Records,
masks and RAM do not move; the packed forms move by a few bytes of flags (PITS LZB 5,989 -> 6,003), and
PLAYGROUND's identity 8803h -> D427h, its demo re-authored. `--selfcheck` replays the model (the
scripted runs and 60 seeded ones) and checks that every grounded step on a FIELD cell where a record
hides a lit pixel is on an `OCCG` cell: 457 such steps of 2,712, none ungated, and all 457 ungated
with the old derivation (the red arm).

**B, kept.** 154aee730 came over whole (its tool code, SPEC bullet and self-check items) behind a
switch: `make BZFSHOW=1` passes `bbcourse.py --fshow` (stamped, like `BZSHAPES`), and a course's own
`fshow` statement turns it on for that course. With it on the parts are exactly 154aee730's - SHAPE 653
records, PITS 668, PLAYGROUND 2,761 and identity 0BF2h - and no FIELD cell has `OCCG`. One thing the
first B did not have to face: with the rule as a toggle, the committed PLAYGROUND demo names the
default's identity, so a `BZFSHOW=1` build re-stamps it with its own (only when the demo's identity is
the course compiled with the rule off; the rule moves the picture and never the physics, and the
model's replay still checks the demo step for step) - otherwise the toggle would refuse to build.

**What A costs, PREDICTED** (128.10.9's 55 clk a record passed over, 1.4k a record laid, on the
model's grounded steps on FIELD cells): about 2.2k clk a grounded step on SHAPE's chutes (median 1.4k,
worst 12.9k), 1.5k on PITS, 2.4k on PLAYGROUND - where B spends nothing. Not measured on a 5150; the
final pass's `bonanzaperf` is where that number comes from. **Tested**: host only - `make`, the shipped
and both knob builds (`BZSHAPES=1`, and with `BZFSHOW=1`), `--selfcheck`, `tests/bonanza_dfield.py`,
`cmp` of every course part against the base tree (BENCH - PEAK, the pathway and the title identical);
no emulator rows.

## 2026-11-17 (the pathway drops its occluders)

The owner: "For pathway: yes, drop the occlusion." The pathway's ball is the follower - always grounded,
never a physics step - and none of its cells was OCCG, so its 452 occluder records were never laid. The
tool now compiles a `pathway` course with no occluders (a rule, not a statement; no guest change). MEASURED:
its part 24,150 -> 21,994 bytes of RAM, LZ4 8,390 -> 7,627, LZB 7,153 -> 6,551; identity C78Ah -> 98BAh,
so a game in progress saved by an older build starts afresh (its slot names the old pathway). `--selfcheck` holds it at 0 records, with a negative control and a red arm (the rule
removed: 452 records, red). The pathway's growth to 14 - 20 pads is parked. SPEC.md 128.31, plan 11.10.

## 2026-11-17 (the glass demo, again: a bridge, a ramp and a spring)

The owner liked three of the title's four demos and not the glass one:
it reused the steel ball's tube, waited on UR, did circles that were not
quite circles, and rolled off the edge on purpose. The brief this time
was open: *find an interesting route, and things for the ball to do*.

**What the stage really is.** The picture is wide, but the CGA window
shows only a band of front floor in front of UR's cliff (about x 14 - 20,
y 9 - 12) and a pocket behind the ramp; most of LC is below the glass. A
route sketched on the whole picture runs off the bottom.

**What glass can and cannot do,** found on the model rather than assumed:
it cannot climb the ramp (it stalls a third of the way up), it is slow to
get going under the autopilot (which lets go of the arrows near its
target speed, so held keys drive the fast parts), and spring 2 throws any
ball 6 units up (the cap, BZ_VZMAX 768). Landing on UR from there is 443,
under glass's 552, so **no spring breaks glass on top of UR**; landing
back on the floor is 768, which does.

**The design, between the session and the owner.** The session's first
route was a setup and a payoff: glass stops beside spring 2, backs off,
and later skids onto it at speed. The owner had been about to propose the
same path, and changed two things: glass should TRY the ramp and fail,
then try the spring to get up; and it should enter over a hidden glass
bridge (the GLASS family's path tiles, 128.25.8) that steel never found,
which also lets the pit become a real gap. The bridge is on LL's back
row, because spring 1 and steel's fall are on the centre row.

**The lip.** Searching the approach speed for the spring found three
outcomes: too slow and it goes straight up and down onto the spring;
about right and it rises level with UR's edge, catches the lip, and
drops back onto the spring (shattered); faster and it makes it onto UR.
The demo uses the middle one, so it fails trying rather than by being
pushed.

**Tested:** host only - the model's replay of all four demos (1, 2 and 4
identical step for step to the course before the change; 3's expects
met), the course preview, a host GIF. **Not yet:** the guest
(`bonanzatitle`), named for the phase's soak.

**The owner's notes on the first bridge** (the same day). The bridge was
laid on LL's back row at LL's height, so its far end stood 1.5 units over
the channel - and the tool put its hint, the jagged teeth, on THAT end,
because `glass_first` picked the edge nearest the course's start cell,
which on the title is out on the front floor. The teeth hung in the air.
Two changes: the hint now only ever joins ground LEVEL with the glass
tile at their shared edge (the rule the art was drawn for), and the
bridge moved to the strip's row (12 - 13, 12) at LS's height. No row of
the pit is level on both sides - LS 2.5, the step 3, LL 3.5, against the
channel's 2 - so this is the least drop, half a step, which every ball
rolls. The owner asked for the half step first, with LS lowered to 2 (and
demos 2 and 4 re-authored) as the next try if it does not look good
enough. Demo 3 now goes down the step and across; the autopilot is slow
with glass, so the run at the ramp is held keys, searched for the run
that gets a third of the way up (3.25 units at step 469). The shatter is
at 798 now, its shards done ten steps before the demo ends.

The owner also expected every resident family in ONE part with the ball
art, and a glass bridge with a 2 x 3 LEVEL mode replacing the teeth; neither
is on any branch of the repository yet (another session's merge, still
waiting on its soak). The bridge here is laid in the flat mode this tree
has, and nothing in demo 3 depends on how it is drawn.

## 2026-11-17 (the victory tune that never played, and the lives counter says LIVES)

**The fanfare.** The owner remembered a VICTORY tune that never played: the
course's song ran on through every finish. The call from the finish
sequence to `bzs_victory` was inside `%ifdef BZ_SONG_VICTORY`, and the
music tool defines that name with `equ`, which `%ifdef` does not see, so
NASM never assembled the call. Every check of the fanfare passed, because
each asked whether the routine and the song's index EXISTED. The listing
told the truth: the call line had no expansion under it. The guard is gone,
and `bonanzasound`'s host half now reads the listing for the assembled call
(green on the fix, red on the old source). No other `%ifdef` in the
package tests an `equ` name.

**The lives counter.** The pathway's counter was a crystal ball holding a
digit - a clock, to look at. Four options were mocked on the real picture,
both cards (BOUNCE-BONANZA-LIVES.md): the ball with a caption, a plaque, the
marble "x N", and the lives as marbles. The owner liked all four and chose
the marble "x N" (C): LIVES and the "x" in the map's own label face, the
course names', with the player's marble on a plinth. The marbles-as-lives
idea, with one shattering on the way back to the map after a lost life, is
parked in that plan for the end of development. Built as a `lives` frame of
the clock record, so the guest is unchanged; both pages' counters looked at
on host renders, CGA and Hercules, and inside their windows.

A finding on the way: on the Hercules the old counter's black digit sat on
cyan's grey checker. The owner judged that it reads, and prefers it to a
black box round the digit, which looks pasted on.

## 2026-11-17 (occlusion: what it costs, and computing it instead)

The owner: *"Course size is too big, and most of it seems to be occlusion ...
It does not need to be pixel-perfect or the same as today. Can we just store
less?"* A host-only deep-dive answered it.
[BONANZA-OCCLUSION-2026-11-17](../reports/BONANZA-OCCLUSION-2026-11-17.md)
is the measurement, and
[BOUNCE-BONANZA-OCCLUSION.md](BOUNCE-BONANZA-OCCLUSION.md) is the proposal.

- **Occlusion is a third, not most.** Over the seven courses it is 31% of the
  packed parts and 25% of their RAM: 14,656 bytes LZB and 58,762 of RAM, in
  context. The picture is 52% and 57%. The map alone is 41% of course RAM.
- **58% of the records exist only for a ball in a VOID cell**: falls and
  flights over gaps.
- **Most records can be computed.** Since every face reaches the ground
  plane (128.27), the picture under a front cell's top edge is that cell's.
  A model that reads up to 14 cells in front of the ball hides at most 0.1%
  of the ball's pixels that the rule does not. "Residual" records cover
  what it cannot see: props, split cells, cells further away. Everywhere
  (A4R), that takes the records from 12,403 to 1,958, the parts' LZB down
  9,862 and their RAM down 46,046. In the VOID cells alone (AV) it is -5,154
  and -25,552.
- **CPU is the cost, not a saving.** The lay dominates the pass whatever
  stores the masks, and computing a mask costs more than reading one: +0.4k
  to +3.1k clocks a gated frame, PREDICTED. The proposal ships AV first,
  which only touches fall frames, and A4R only if the measured routine passes
  the owner's smoothness rule.
- **The ghost (V)** was priced too. It is cheaper and smaller than AV, and
  the pictures show its fault: the ball dims a few frames before it goes
  behind the edge.

**Tested**: host only, the tool's own pipeline, a Monte Carlo of about 2
million positions of the binding physics, and the fall pictures in
`bounce-bonanza/`. **Not run**: any emulator row (nothing shipped changed).

## 2026-11-17 (AV: the occlusion computed in the void, built and timed)

The owner: *"Let's try AV so I can play with it ... and see how much those
fall-frame costs are."* AV is built (SPEC.md 128.29, branch
`bounce-bonanza-av`): when the ball is in a VOID cell the occluder pass
computes what hides it from the 14 cells in front of it, out of the grid's
own bytes, and the part keeps only the residual records the computation
cannot see. Every other position keeps today's records.

- **The bytes (MEASURED, the shipped tool's pipeline).** Over the seven
  courses the records fall from 12,403 to 5,981, the parts by **5,670 bytes
  LZB** and **27,704 bytes of RAM** - better than the prototype's -5,154 and
  -25,552, because the binding residual keeps only the pixels the model
  misses. `BONANZA.O88` loses 5,219 bytes and `bonanza360.img` goes from 123
  to 118 clusters. PEAK's part gains 6.6 KB of headroom.
- **The picture (MEASURED on the host).** Nothing the rule hides is drawn
  over - proved at every height of every VOID cell of all nine parts - and
  what the model hides that the rule does not is 0.0000 - 0.0005% of the
  ball's pixels. On the glass it should look like today; one MartyPC CGA boot
  of MILL's falls showed the front-edge falls drawn as today. A back-edge fall
  was not looked at on the glass.
- **The fall frames (MEASURED on MartyPC, both cards; the owner's
  question).** The first routine was a surprise: **+36k to +42k clocks a
  fall frame**, half a refresh, where the contract predicted +1k to +4k.
  Pricing it from the instructions under unicorn agreed (+30k), and the
  profile said why: the model built a mask for every word of the footprint
  and laid about one. Skipping words whose edges are all under (or all over)
  the lines, and testing the front cells inline, brought it to **+12k to
  +19k in the median and +31k to +58k at worst** - 15 - 30% of a 79.6k
  refresh typically, up to two thirds at worst. Over MILL's scripted falls
  about one frame in 17 fall frames is lost; over PEAK's demo 0.3 frames a
  second. Play off the void is untouched.
- **What the prediction missed**: it priced the model's own arithmetic and
  forgot that a model has to look at every word to find out it lays nothing.
  The records never pay that, because a record that lays nothing is never
  read.
- **Decisions taken here**: `FL_FLOAT` went to flag bit 6, not 4 (4 - 5 are
  reserved for `edge`); a floating GOAL keeps its course on today's records
  rather than being refused; the model lays its own words after the walk
  instead of ANDing into the walk's groups (two lays are one lay under the
  AND), which left the walk untouched; F's right half takes `+ 4` so the edge
  is exactly the renderer's (the pathway's 45-degree cell found it).
- **Open for the owner**: whether the fall frames' cost is acceptable, or AV
  waits for the next lever (a launch-time bitmap of the front cells that can
  ever occlude each cell, which would skip most reads; or depth 3 where the
  tool proves it enough). The smoothness A/B was not run.

**Tested**: `--selfcheck` (item 15 new, all red arms red), `make`,
`make bonanzadisk`, the guest against the host under unicorn on nine parts,
MartyPC's fall-frame A/B on both cards, one look-boot. **Not run**: the soak
rows (the final pass's: `bonanzacourse`, `bonanzaassets`, `bonanzaring`,
`bonanzaphys`, `bonanzareplay`, `bonanzaperf`, `bonanzawheel`,
`bonanzapath`, `bonanzatitle`, `bonanzaexit`, `bonanzamega`).

**Later the same day: the cell's top test.** The owner pointed out that a ball jumping high over a gap is above every front tile, so one test against the tile tops should end the model. It skipped a cell whose top was not above the ball but read all 14 cells every frame anyway. It now remembers the last cell and the highest top in front of it: the same cell with the ball at or over that top costs one compare. TRIAL's gap jump went from +10.6k a frame to +713 after the frame that enters each cell (PRICED). MEASURED on MartyPC, the median fall frame on MILL and PEAK's demo dropped from +12k to under +2k on the CGA; PEAK's scripted falls, which really go behind its terrain, still cost about +21k in the median.

## 2026-11-17 (AV: an independent speed pass)

The owner, on AV's fall frames costing four to ten times the prediction:
*"half the time when these come in so much higher it's because someone did it
totally differently, and there is a cheaper way to do it after all."* An
independent pass over the code and the approach (branch
`bounce-bonanza-av2`, SPEC.md 128.29.5 and 128.29.9).

- **Why the estimate missed (PRICED from the instructions on the real fall
  frames).** The plan priced one frame's work: read the front cells, build 4
  - 6 words, lay them - at 60 - 90 clocks a cell and about 30 a column. The
  routine as built spent 9.4k a PEAK fall frame reading the 14 cells (670 a
  cell: an 8088 pays 15 - 20 clocks an instruction, and each one touched
  memory through a segment override), 6.7k on edges and 2.9k on each word's
  bounds - **19k of 22k recomputed every frame, though none of it changes
  while the ball falls straight down through one cell.** The work was the
  right work; it was done once a frame where it needs doing once a cell.
- **What was priced and dropped.** A coarser model - each edge taken at its
  least over 4 or 8 columns - saves no byte at all (the records do not move)
  and hides 0.24 - 0.76% of the ball's pixels that the rule does not, past the
  0.25% bound on most courses (MEASURED on the host). Per-word or per-span
  mask building would cost about the same per column on an 8088 (ESTIMATED
  from the instruction counts); the general shadow test
  needs a multiply a half for three more halves dropped on the worst frame.
- **What was built.** The model is now computed once a cell and kept: the
  front cells read once into a table, the count set as an interval of the
  key, each footprint word's edges computed the first frame it is needed.
  80 - 90% of the model's frames over the scripted falls change neither the
  cell nor the count set (the host's replay). A cell's half that its flat parent covers is never
  computed (three compares; the worst frame's 28 halves become 13). Exact: no
  part byte, no tool change; the unicorn proof now drives ten-frame FALLS
  through the cache and has a second red arm for it.
- **MEASURED on MartyPC** (the same legs, once; AV - today's pass on the fall
  frames). Mean +11.2k -> **+4.6k** on the CGA's MILL falls, +22.8k ->
  **+7.9k** on PEAK's, +9.0k -> **+3.2k** on PEAK's demo; the Hercules the
  same shape. PEAK's falls' median **+20.7k -> +3.3k**. The worst frame,
  72% -> 46% of a refresh on MILL and 44% -> 24% on PEAK's demo - but one
  frame entering a cell deep behind PEAK's terrain still costs +43k.
- **The bytes**: +541 of code and +236 of bss over the AV head; `BONANZA.O88`
  +448, `bonanza360.img` 118 -> 119 clusters. That is 8% of what AV saves on
  the disk, bought for a mean fall frame two and a half times cheaper.
- **Left, PREDICTED**: reusing nine of the 14 front cells when the ball moves
  to a neighbouring cell (the entering frame's reads about 10k -> 4k), and
  folding the model's mask into a residual group's lay of the same word.

**Tested**: `tests/bonanza_av.py` (nine parts, 500 positions each, falls
included; both red arms red), `make`, `make bonanzadisk`, the MartyPC fall
legs on both cards. **Not run**: the soak rows (the final pass's:
`bonanzacourse`, `bonanzaassets`, `bonanzaring`, `bonanzaphys`,
`bonanzareplay`, `bonanzaperf`, `bonanzawheel`, `bonanzapath`,
`bonanzatitle`, `bonanzaexit`, `bonanzamega`); `bbcourse.py --selfcheck`
(the tool did not change).

## 2026-11-17 (AV: the neighbour, and AV merged with the shaped floors, two-part courses and the bare pathway)

The owner on the speed pass's two levers: build the neighbour reuse (*"the
performance is worth it"*), hold the fold as a future item; then make AV
merge-ready against `bounce-bonanza` (SPEC.md 128.29.5, 128.29.9, 128.29.11).

- **The neighbour (built).** A ball stepping one cell forward sees the old
  cell's front rows 2 - 4 as its rows 1 - 3, so only row 4 is read and two
  shadow bits are cleared. +227 bytes against the 120 predicted. MEASURED it
  bought little: the means fell 0.1 - 0.4k and CGA PEAK's worst frame 43.3k ->
  38.7k. Most cell changes over the scripted falls are not a step forward, and
  an entering frame's cost is the words it computes and lays more than the
  reads. Recorded as it is, not as the prediction said.
- **The fold (held, `BOUNCE-BONANZA-PLAN.md` T13).** About -1k a PEAK fall
  frame, twice on two-box frames, PREDICTED; deferred because it touches the
  walk every occluder frame runs.
- **The merge.** Three things AV had not met, resolved on purpose: 128.28 had
  taken the same flag bit (`GF_ANA` moved to bit 6); FIELD cells' records are
  cut at the ball's real poses, so AV's non-void records pass the tiles too;
  a two-part course keeps the grid in the world part, so the model reads it
  through `bz_cseg` in the two places it reads it at all and the host reads it
  through `world_of`; and the pathway, which now cuts no occluder, gets no
  model. Two checks met AV for the first time and now count the model: the
  pit's hole (item 5) and an all-keep record (item 15).
- **MEASURED on MartyPC (once, against the merged tree with no model).** AV -
  today on the fall frames, mean / median / worst: CGA MILL +4.2k / +0.8k /
  +36.0k, PEAK +7.8k / +3.8k / +38.7k, PEAK's demo +3.0k / +0.8k / +19.2k; the
  Hercules +4.2k / +0.7k / +46.5k, +8.1k / +4.6k / +37.9k, +3.0k / +0.7k /
  +25.2k. Frames presented within 1% of today's but on MILL's falls (1,049
  against 1,057 on the CGA, 887 against 905 on the Hercules).
- **The bytes, merged.** The seven courses -28,468 bytes of RAM, -5,760 LZB;
  `BONANZA.O88` -4,481 with the model's 1,890 bytes of code in it;
  `bonanza360.img` 129 -> 124 clusters; PLAYGROUND's picture part 4,926 bytes
  more headroom.

**Tested**: `bbcourse.py --selfcheck` in full; `tests/bonanza_av.py` on all
nine parts (PLAYGROUND's two, the pathway with no model) with falls forward,
its red arms `amodel`, `acache` and `aneigh` red; `make`, `make
bonanzadisk`; the three authored demos' `ident` lines; the MartyPC fall legs,
both cards. **Not run**: the soak rows (the final pass's).


## 2026-11-17 (WIND: blowers, gusts and an updraft)

The props round's P3 (docs/plans/BOUNCE-BONANZA-PROPS.md), built on branch
`bb-wind` beside water and magnets (IDs 7, 8 and 9 fixed ahead so the three
merge). The owner's design: a blower PUSHES the ball in its region, weighted
glass x2, rubber x1, steel x1/4 (*"the push amounts sound right"*); steady
or in gusts, so a bridge can be crossed between them; a flag or a small lane
as the hint; and the gate the owner picked for the water's column - a wind
across a THIN lower path, blowing hard to one side. SPEC.md 128.34 is the
contract, written first, and the as-built record.

- **No resident byte.** The push is added to the working velocity in the
  STEP hook; the next step's force block clamps it like the arrows, so the
  wind can never carry a ball past a cap the reach already assumes. A gust is
  a function of the step counter (a windmill gate's rule), so there is no
  state bit and nothing for a respawn to reset; the slot only lists the
  blowers. The image moved +3 bytes (the ID table's gap, 7 - 9), the part is
  326 bytes in the resident bundle.
- **The arrows push TWICE on one axis.** Right with Down is 2 x the force
  table on +x. So rubber's best stand against a cross-wind is 8, glass's 12,
  steel's 4: a wind of 10 is a real gate for rubber and glass and steel leans
  through it. Found on the model before tuning anything; the first guess
  (strength 12, against forces of 4) was reasoning about one arrow.
- **The scenes lied once.** Every ball fell off the thin path at the same
  step - because the scripted route to it rolled over the GLASS PAD, so every
  ball was glass. The pads moved off the start's diagonals.
- **Steel cannot test the crumbling bridge from rest**: it breaks a crack
  under it in 14 steps unless it is above 293, so the gust scene is rubber's
  and glass's; steel's weighting is shown on the thin path.
- **A play's RESET runs before the lanes are counted.** The slot's list was
  first built over `bz_nlane`, which `bz_pread` sets AFTER `bz_pinit`: the
  unicorn half caught it (an empty list in the guest, three blowers in the
  model) at step 0. It scans `bz_nprop` now.
- **The window's centre is the ball's cell.** Working the cell out of the
  24.8 position cost about 0.15k a step; `bz_nwin` is one word, and the model
  reads its own `wcell`, so the two stay equal by construction.
- **The updraft** lifts only an airborne ball (the grounded step rewrites
  gvz from the slopes), and only while gvz is under 128 - a steady climb and
  a hover band of a few pixels under its top, instead of a 20 px overshoot.
  MEASURED on the model on the WIND course: glass rises to 49 px and onto the
  ledge's finish; rubber's best apex there, pumping Hop and boost, 23 px;
  steel's 18 - the ledge is at 36.
- **The fan and the flag, looked at four times.** White blades on magenta
  read on the CGA and were white specks on the Hercules' grey checker; black
  blades on white read on both cards. The checkpoint's own pennant, the
  precedent, was too small to read at 320 x 200 on a white tile (MartyPC,
  the knob build); a bigger magenta one on a taller pole vanished against the
  magenta face behind the thin path's blower; STRIPED magenta and white like
  a windsock, one of the two shows on any ground. SEEN on MartyPC, CGA and
  Hercules: the bridge's pennant flying in a gust and furled between.

**Measured**: the part 326 bytes; `BONANZA.O88` +259; the bundle +336 RAM;
image +3; bss 0. **Predicted, not measured**: about 0.2 - 0.45k a blower a
step (0.23k fixed; a gusting blower 0.33k more), against the plan's 0.1 -
0.2k, which was the push alone. **Tested**: `make bonanzadisk`, the
`BZWIND=1` knob build, `bbcourse.py --selfcheck --only wind` (25 items, red
arm `nowindreach`), `bonanza_phys.py --check` with `wind_host` (eight scenes
equal at every step; red arms `wdstep`, `wdglass`, `wdmark`, `wdlift` red),
the tool's previews and one MartyPC look on both cards. **Not run**: the
soak rows, MartyPC measurements (the final pass's).

## 2026-11-17 (WIND, round 2: a pit that lifts, squiggles in the air, fans that spin)

The owner's answers on WIND (through the lead): strength per blower and
power-of-two gusts are fine as they are; and three changes - an updraft that
lifts WITHOUT a jump, squiggles drawn in the air as the hint, and ground fans
that spin when the ball is in their wind, the pennant only as an option.
SPEC.md 128.34.11 is the record.

- **The launch is the take-off's three writes.** The grounded step rewrites
  gvz from the slopes, so a push there was lost; a `lift` updraft whose push
  beats gravity now sets `bz_air`, `bz_gvz` and the take-off z itself, in the
  STEP hook, and the airborne rule does the rest. A PIT needed nothing: a ball
  rolling into one is airborne already. Glass (32 against gravity's 24) is
  launched; rubber (16) floats when it is in the air and drops into the pit
  slowly; steel all but ignores it - the owner's "glass rises, rubber partly,
  steel not" falls out of the weighting unchanged.
- **One element is one lane.** A fan that spins is the blower's lane, so a
  gusting blower's squiggles - which must come and go - needed a second
  element: the tool makes a WISP at the region's centre, owning no cell, its
  lane the cluster and its record naming its blower. Steady squiggles are
  plain marks in the picture: no lane, no step, never over the ball.
- **The window's budget decided the course.** A spinning fan is a FAST lane
  and a pose change a step; the test course's two clocks (4 digits) and two
  fans in one window were 7 changes a step, over 6, so the ledge's finish
  moved beside the main goal and one clock serves both. With one clock and an
  event lane in view, 3 fans can spin at once.
- **Two timed lanes, one step.** The lead's note from the magnets: a window's
  event lanes are one pose change a step. Gust turns are the one kind known
  ahead, so the tool checks every step of the 1,024 the periods divide and
  refuses two gusting lanes of one window turning together.
- **The scenes needed a smaller course.** The default build's `bz_fst` is
  the shipped courses' five bytes; five cracks and four fan bytes would not
  fit, so the unicorn half plays WIND less its cracks (GLASS's own scenes
  prove those).

**Measured**: the part 525 bytes (+199); `BONANZA.O88` +157 on round 1 (+416
on the base); image +3, bss 0. **Tested**: `make bonanzadisk`, the
`BZWIND=1` build, `--selfcheck` section `wind` (32 items, red arms
`nowindreach`, `fanfast`, the pit wind's without `lift`), `bonanza_phys`'s
`wind_host` (eleven scenes equal at every step; red arms `wdstep`,
`wdglass`, `wdfan`, `wdgust`, `wdspin`, `wdlift`, `wdpit`). **SEEN** on
MartyPC, CGA and Hercules: the bridge's squiggles in a gust and gone after,
the fan turning frame by frame under a poked ball, the static squiggles, the
pit's plate and flag. **Not run**: the soak rows; the per-step cost on
MartyPC.
