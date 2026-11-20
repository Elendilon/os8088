# Bounce Bonanza: the soak rows, fast and on the game as it ships (PROPOSED)

The owner, 2026-11-19: *"lets take on bonanza's soaks next. They take
forever, are not up to date with the current game, and have been pretty
fragile. Look into optimizing wall clock time. Fix any that are broken,
bringing them up to date with the game. And if something in the game itself
is actually broken and the test is exposing it, either fix it or bring it to
me."* And: *"bundle tests together more ... one in emulator boot can test
more things at once; with custom test courses set up to test the things.
Another is remove old prototype tests; aka, the tour ... We'll eventually use
all of the props, and having test only courses is fine, but we can get rid of
all dependencies on the prototype courses as they leave the game. Only ROLL
and little hop are shipping courses right now."*

## Where the time goes (the map, 2026-11-19, at 76bb2ba8f)

Fifteen rows. The emulator rows and their DEFAULT runs:

| row | declared | boots | what costs | prototype dependence |
|---|---|---|---|---|
| bonanzaring | 1,180 s | 3 (a card each) | BENCH, TRIAL, MILL benchmarks of 1,200 frames each; MILL's scripted scenes; MOON's and PEAK's demos; the ground and camera replays (~6,000 frames a card); `symbols()` re-assembled per card; the ground scenarios recomputed per card | all legs but `glass` |
| bonanzaexit | 902 s | 3 | ~52 launches a card: FIRST x 3 balls x 6 ways out, then the 6 ways again on MILL, MOON, PEAK, PLAY (the balls are held since 130.25.5.2: the ball loop tests one thing three times); BENCH's benchmark twice | incidental (a cup, a tube, two palettes) |
| bonanzagame | 920 s | **44** (22 a card) | a boot a hostile BONANZA.DAT (16) and a physics-identity file (4), each playing FIRST to its goal by autopilot; the TOUR legs (three) | incidental; the tour |
| bonanzademo | 690 s | 2 | five full MILL runs a card; every shipped demo through V and D (8 since ROLL and HOP shipped) | the shipped prototype demos |
| bonanzareplay | 471 s | 3 | a frame-by-frame breakpoint on every presented frame; TRIAL, MILL, PLAY, MOON scripts | essential, by geometry |
| bonanzaphys | 705 s | 2 | ~97 MartyPC replays a card, each compared every frame; `replays()` and `prove()` rebuilt per card | prototypes by feature; **its `--check` half - every test-only course's scenarios under unicorn - is run by no row** |
| bonanzawheel | 162 s | 2 | MILL's lanes found by search, a benchmark of 1,200 frames | MILL by feature |
| bonanzaperf | 966 s | 4 | every shipped demo x every card x sound OFF and ON (32 runs since ROLL and HOP), BENCH, MILL x 3, rides; mostly REPORTED, a few gates | BENCH, MILL, the shipped demos |
| bonanzapath | 115 s | 3 | FIRST to its goal, Follow at every step, PEAK three times; the secret leg recompiles every course into a private art tree | **broken by the new map** (pad 0 FIRST, old routes, `SECRET_PATCH`) |
| bonanzatitle | 60 s | 2 | two title demos, two course demos; `title.bbc` compiled twice, uncached | incidental |
| bonanzasound | 60 s | 2 | F on FIRST, three model stops, 120 frames' cost; its own `symbols()` | incidental |
| bonanzamega | 333 s | 1 (86Box) | VGA benchmark x 2, FIRST plays, MILL, PLAY, PEAK's demo | by feature |

The host rows: bonanzacourse (`bbcourse.py --selfcheck`, ~1,770 CPU s, ~450 s
wall; a third of its sections name prototype courses, and `path` is broken by
the new map), bonanzaassets and bonanzamusic (a second each).

MEASURED in a scoped soak today (4 lanes): bonanzaring TIMES OUT at 1,500 CPU
s (three runs out of three today); bonanzapath took 1,482 s against 115
declared.

## The principles

1. **A boot tests many things.** A row boots once a card, on purpose-built
   TEST courses, and walks every check that card owes; a check that needs a
   fresh machine (a hostile BONANZA.DAT) gets the state by a reload, not a
   reboot, wherever the game can be made to reload without one.
2. **No prototype course, no prototype demo, no tour.** The rows run on the
   shipped courses (ROLL, HOP, the pathway, the title) and on TEST courses
   built for the job - always in the `BZDEV=1` tree the rows already run, as
   courses appended to `BZ_COURSES` there (`bz_crs` poked at `bz_launch`, as
   the rows already do). A scenario's log is MADE from the model
   (`make_log`), never a shipped demo. When the prototypes leave the build,
   no row notices.
3. **The host before the guest.** What the unicorn half proves step for step
   (the physics, the families) is not replayed again on MartyPC beyond a
   representative few; MartyPC is for what only it can see (frames, the
   wheel's beam, the glass, the sound, the disk, real timing).
4. **Gates gate; reports report.** bonanzaperf's matrix becomes its few
   asserted numbers on few runs; the full matrix stays `--baseline`'s, by hand.
5. **Nothing is computed twice in a process** (`symbols()`, the scenario
   sets, the ground checks).

## The phases

### Phase 1 - working and honest (now)
- [x] The TOUR's tests deleted: bonanzagame's `tour`, `stop`, `face` legs and
      helpers, the `tourx` hostile case; bonanzaexit's tour exits.
- [x] bonanzapath rewritten for the shipped map (pad 0 ROLL, pad 1 HOP) and its
      secret leg on a fixed test map; bbcourse's `path` section likewise.
- [x] bonanzaexit: the claim leg covers every K (a cheap launch per course,
      ROLL and HOP included); the three red arms whose expected text sits in a
      comment fixed.
- [x] `bonanza_phys --check` registered as a row of its own (the test-only
      courses' only gate).
- [x] The per-process caches: `symbols()`, `replays()`/`prove()`, the ground
      checks, `title.bbc`'s compile.
- [x] Stale text (song rows, three ball rows, BZD1 - BZD6) brought to the game.

### Phase 2 - the test courses

**The mechanism (BUILT, SPEC.md 130.54):** a course says `test`; the
Makefile lists it in `BZ_TESTCRS`, which only `BZDEV=1`'s block appends,
AFTER every other course; `bbcourse.py -o` refuses a `test` course without
`--dev` (make passes it under `BZDEV=1`), so none ships; a test course owes
no pad, no shipped demo and no `target` (`c.test`, which replaced
`BENCH_NAMES`); `default_paths()` is `BZ_COURSES` + `BZ_TESTCRS`, so the bare
selfcheck compiles and checks them, and its `courses` section cross-checks
the Makefile's lists against the `test` lines. BENCH is one of them now and
moved from course 0 to after the shipped courses: the test build's K are
the shipped build's.
- [x] **TPLAY** (physics and replays), BUILT as **TPLY** (`tply.bbc`, rubber,
      `limit 20`, on `BZ_TESTCRS`): the PLAYGROUND's APRON at TRIAL's start
      height - the start (19, 14), four ADJACENT rungs along its back row (2 /
      1.5 / 1 / 0.5 units up, wx 7 - 18, wy 9 - 11, approached along -wy from
      the front row wy 17; a 64-wide course has no width for apron between
      them), the BRAKE STRIP (lane wx 12, wy 18 - 20) off its front into a
      void over a well 16 units down; TRIAL turned a quarter (cell (Tx, Ty) ->
      (Ty + 8, Tx + 9)): H's lip the apron's front edge, F, the gap, G and its
      far rail, the STEEP ramp, the mat, the turn, the ICE between BUMPER
      rails, the SAND, the SPLIT GOAL (25, 17) exit 0 / (26, 17) exit 1; a
      YARD off the turn: FIRST's PLATEAU with its back RAIL and its ramp's
      2-unit LIP, the three PADS, SPRING 1 (29, 35; 640, throws rubber onto
      the plateau) and SPRING 2 (37, 30; 512), a plain EAST wall (38, 28 - 29),
      flag 0's HOLE; a 14-cell level STRIP (`box 2 6 70 98`) for the drag;
      FLAG 0 (26, 26, rubber) on the turn and FLAG 1 (19, 26, glass) on G. The
      autopilot: exit 1 in 529 steps (9.7 s), no fall, both flags; NO TRAP
      holds; one part, 30,979 bytes RAM, 91 masks (95 UNDITHERED - under the
      256, so `nodither` can compile it: PLAYGROUND's 292 cannot). **Not on
      it, and why**: the CUP (a course finishes at a goal or in a cup - TCUP
      has it); the SAFE respawn (a flag or a cup sets GF_CKPT and every
      respawn goes to the flag, so `pit` and the `respawn` arm move to BENCH,
      which has neither: +wx from its start falls at step 210 and respawns on
      (19, 14), not the start (6, 14)); the timeout's wait (TQUIK's 8 s; TPLY's
      20 s times out at step 1,100 as the model says); the FAMILIES (wave 9's
      glass, probe and pickups - open: a family test course, or the knob
      courses that already carry their hosts).
- [x] **TMILL** (the wheel and the ring): rotors and lighting posts (2- and
      3-word lanes, one crossing the ring's end), a lift with docks, a tube
      and a cannon, a clock, scrolling both ways, occluders.  BUILT as
      **TMIL** (`tmil.bbc`, "Wheel and Ring", rubber; the table below).
- [x] **TQUICK** (exits and the save), BUILT as two courses because a course
      finishes at a goal or in a cup, never both (130.14.4.1): **TQUIK**
      (`tquik.bbc`; a NAME is five characters) - rubber, the goal 165
      autopilot steps (3.0 s) from the start, flag 0 on the route and a hole
      beside it, a plain KEEP tube drain off the route (16 steps hidden, as
      MILL's drop), `palette 0` (10h), `limit 8`; **TCUP** (`tcup.bbc`) -
      steel, the cup 291 steps (5.3 s) away, the default palette (30h), the
      tool's limit (15 s). **No two-part twin**: a two-part course needs a
      picture over 65,024 bytes, a course of PLAY's size; the only two-part
      course is PLAY itself (`bzcrs2.lst`), so the world-part legs move with
      the TPLAY/TMILL decision (TWOSEG, `make bonanzatwoseg`, is generated
      from PLAYGROUND and goes with it).

  Which leg runs on what, in phase 3 (the rows are NOT rewritten yet):

  | row, leg | today | phase 3 | the feature it uses |
  |---|---|---|---|
  | exit, the six WAYS (Esc, F, Alt+Enter, the goal, a replay's end, Esc in a replay) | FIRST x 3 balls | TQUIK, once (the balls are held, 130.25.5.2) | the goal (`goal()` pokes the ball onto its GOAL cell), a log made by `make_log` on TQUIK |
  | exit, the benchmark's end (B) | BENCH | BENCH (a test course now) | B's own course |
  | exit, Esc while HIDDEN (`into_tube`) | MILL's drop | TQUIK | the KEEP tube's IN cell (6, 7) |
  | exit, the cup's way out and the `padleak` red | MOON, PEAK, PLAY | TCUP | the cup (`goal()`'s cup arm) |
  | exit, the claim leg | every K, FIRST's ways, MILL, MOON, PEAK, PLAY | every K, one cheap launch each (TQUIK and TCUP included) | `own_course` by material: TQUIK rubber, TCUP steel |
  | exit, the palette leg and `nopal` / `hercpal` | PLAY (10h), FIRST (30h) | TQUIK (10h), TCUP (30h) | `palette 0` against the default |
  | exit, `expoff1` / `rowtab1` (the first launch) | FIRST | TQUIK | any course |
  | exit, `cellsafe` (a prop's cell made SAFE) | MILL | TQUIK | its tube (a prop) - CHECK: the red must fire on a KEEP tube's cells |
  | exit, the world part's fetch and drop | PLAY (two parts) | open: no test course is two parts | - |
  | exit, wave 4's V / D / W / L / double-click | FIRST's and MOON's shipped demos | ROLL's and HOP's shipped demos for V; a TQUIK log for D, W, L | the shipped demos are the shipped courses' alone |
  | game, `pause` | FIRST free play | TQUIK free play | the goal in 165 steps (P pressed at step 40) |
  | game, `hostile` and `physdat` (the next best) | FIRST by the autopilot, a boot a file | TQUIK by the autopilot, a reload a file | the goal in 3 s |
  | game, `noapp` (two bests) | FIRST, TRIAL | TQUIK, TCUP | a goal and a cup |
  | game, `posts` | V of FIRST's and MOON's shipped demos, R, D | V of ROLL's and HOP's; R and D of a TQUIK log | - |
  | demo, `save` / `load` / `dclick` | MILL by the autopilot (five MILL runs a card) | TQUIK by the autopilot | 3 s a run, not MILL's |
  | demo, `wave4` (another build's identity) | MOON's demo with EB84h | a TQUIK log with its +14 identity changed | the identity check alone |
  | demo, `ship` | every shipped demo | ROLL's and HOP's (the shipped ones) | unchanged |
  | demo, `hostile` | MOON's demo, this build's logs | TQUIK logs made from the model | - |

  **TMIL as built** (`apps/bonanza/courses/tmil.bbc`; the file's header is the
  map).  MILL's top cell for cell - the start tier A (16), the house, both
  windmills on KEEP tubes (seeds 16 and the derived 36), B (20) and C (18) -
  so bonanzaphys's `knock` / `pass` gate logs and every poke on that part
  carry over by name; then B's ramp down along +y (20 -> 12) onto W, a strip
  at 12 the route crosses along +x, three bumpers, a DROP from W onto F (8),
  the LIFT (18, 22) between F and the low floor L (2), and the CANNON from F
  along -x over L onto the goal ledge G (4).  20,970 bytes stored, 4,590 LZB
  (MILL 26,785 RAM); compiles in about 28 s cold.  The autopilot finishes:
  goal at step 723 (13.1 s), no fall, one kick; limit the tool's 25 s.

  THE RING'S END is designed in, not poked: a card row's offset is
  (rb R + 2 x) mod 8192 for world card row R and word x (bbcourse.ring_cross),
  so the spots are fixed in the world -
  - **lanes**: post 4 (7, 13) on A, lines 192 - 208, crosses on the CGA (row
    102); post 6 (20, 16) on W, lines 352 - 368, crosses on the Hercules (row
    90) - one 2-word lane a card; post 6 has W's back, a level floor about
    60 lines above it, for the LOW scenario (post 4's, C, is unchecked: the
    CGA's LOW_NEAR is 0 and its `wrapcommit` optional);
  - **3- and 4-word ball boxes** (`wrapbox`, 0 checked on any course today):
    the route's own frames - the Hercules at (21, 15) on W (box x0 45, row
    90), the CGA at (19, 20) on F (box x0 30, row 204).

  Frames below are the HOST MODEL's (bbcourse.glide_run, the autopilot under
  LATTICE with the heavy rule, CGA / Hercules frames at the card's refresh,
  the census script of the TMILL agent): PREDICTED, not measured - the guest's
  boxes and commits are only MartyPC's, and phase 3's first run measures them.
  A leg's "frames" is the frame by which every feature it needs has appeared
  FEAT_EACH (3) times, so a benchmark can stop there (today B runs a fixed
  BZ_BENCH 1,200; stopping early is the row's - bz_fs is watched anyway).

  | row, leg | today: course, feature | TMIL: feature (cell) | frames needed (CGA / Herc) |
  |---|---|---|---|
  | wheel, BENCH (benchmark, breakpoints on every commit) | MILL, 1,200 frames: rotors shown, a kick, 2- and 3-word commits, HOLD_FROM 120 late frames | both rotors shown from frame 1; the kick of post 5 (17, 16); posts 5 and 6 shown from 256 / 212 | ~400 / ~350 (the kick at 331 / 282 and enough held frames after 120) |
  | wheel, LOW (+ the BEAM sweep) | MILL play, a post at window line 160, held ball | post 6 (Herc crossing, `wrapcommit`) from W's back; post 4 (CGA crossing) if low_plan finds C | unchanged: the scenario's own ~48 + 138 frames |
  | wheel, CORNER | MILL's post 6, scripted camera | post 4 (7, 13), column 21 (a CGA window reaches its left; the Hercules' REPORTED as today) | unchanged (<= 10 tries) |
  | wheel, STALE | MILL, a rotor above the window's top | the windmills (lines 144 - 184), ball held on the ramp or W | unchanged |
  | wheel, SIDE | MILL, a rotor / clock digit beside the column band | the clock (6, 13) beside the windmills, or the finish clock (11, 21) | unchanged |
  | wheel, CLOCK | FIRST, ball held at the start | TMIL's clock (6, 13) is in the start's window (or TQUIK's) | unchanged |
  | wheel, GATE | MILL's `knock` / `pass` logs (windmill (9, 9)) | the same windmill, the same cells and seed: the logs re-stamped for TMIL | unchanged |
  | ring, `bench` (8 directions, full write, laid records, controls) | BENCH, 1,200 frames, scripted camera | the scripted camera on TMIL: every direction 3 times by frame 60 / 60; records laid over the ball from 326 / 278 (7 / 6 frames, LAY_EACH 6) | ~340 / ~290 |
  | ring, `trial` (shadow own box, three boxes, shadow inside, raster order) | TRIAL, 1,200 frames (+ a poke for three boxes; Herc red today) | the DROP's bounces on F: shadow own 570 / 484, inside 584 / 497; THREE BOXES (ball, shadow, the lift's box) 601 / 510, on BOTH cards from the route | ~620 / ~530 |
  | ring, `mill` (crotor, cpost, defer, pbox, pclip, enter_row, enter_col, transit, exits, wrapcommit; ahead/behind/lead via LOW) | MILL, 1,200 frames | crotor 81 / 69 (windmill (9, 9)); transit 106 / 91; exits 139, ~560, ~720; enter_row ~256 / 212 (posts entering as B's ramp pans down); cpost the kick 331 / 282; defer 339 / 511; pbox 382 / 389; pclip at the lift (not in the host model: from ~380 on); enter_col ~720 / ~650 (G's clock; the Hercules' optional); wrapcommit from LOW (post 6) | ~730 / ~660 (the whole route; the goal is ~795 / ~665 frames) |
  | ring, the ring's end (`wrapbox`) | none on any route (0 checked); the MILL play's poked scene | ON THE ROUTE: Herc (21, 15) at 447, CGA (19, 20) at 692 (12 / 10 frames) | inside the `mill` leg's frames |
  | ring, MILL play: `ride`, `pover`, `ridebox`, `pwait`, DEFER, ring's-end and entering-column scenes | MILL's lift (26, 18), posts, poked spots | the lift (18, 22) (L 6, F the high dock, L the low), posts 5 / 6, the route's own ring's-end spots | unchanged (scenario lengths: RIDE_FRAMES 150, PW_FRAMES 24 / 21 ...) |
  | ring, `probe` (row 0) | BENCH play at the top clamp | TMIL's top: C (18) and B (20) under the window's top rows | unchanged (<= 30 frames) |
  | ring, `camera` | MILL's RAMP_POKE (15, 7), MILL route demo, SIDE_SCEN (21, 17), TRIAL's drop, PEAK | RAMP_POKE / SIDE_SCEN re-found on TMIL (B ends at wx 14, (21, 17) is no floor); the route a make_log of TMIL's autopilot; the drop's fall for TRIAL's | per scenario |
  | perf, `mill` (OFF x 3, ON with the lift stretch) | MILL, 1,200 frames each | TMIL's benchmark to past the lift stretch | ~730 / ~660 |
  | perf, `trial` (+ the bounce camera replay) | TRIAL, 1,200 frames | the drop's bounces on F | ~620 / ~530 |
  | perf, `ride` / `corner` | MILL's lift | TMIL's lift (18, 22) | unchanged (RIDE_STEPS 296) |
  | perf, `dover` | MILL's shipped route demo | a make_log of TMIL's autopilot (723 steps) | 723 steps |
  | perf, `avfall` | MILL's AVFALL key scripts | re-derived off A's, W's and F's edges | per fall |
  | perf, `bench` (the A/B) | BENCH | stays BENCH: the old builds carry BENCH, not TMIL | 1,200 |

  So the ring's three benchmarks (BENCH, TRIAL, MILL: 3 x 1,200 frames a card)
  become ONE TMIL run of ~730 / ~660, and the wheel's MILL benchmark ~400 /
  ~350 - if a row stops at its last feature rather than at BZ_BENCH.

  TPLAY's legs, phase 3 (the rows are NOT rewritten yet). Every home below
  was PROVED on the model (2026-11-20, `bbcourse.Physics` on the compiled
  course: the scenario's own search pointed at TPLY - `PLAY_RUNGS`,
  `PLAY_FRONT`, `PLAY_LANE`, `PLAY_STRIP`, `PLAY_GAPROW` given TPLY's cells -
  or its poke turned with the course): the event the scenario names happens
  there, and where it has a red arm, the broken model PARTS there.

  | row, scenario (its red arm) | today: course, feature | TPLY's home (or TCUP's, BENCH's, TQUIK's) |
  |---|---|---|
  | phys 2, `pit` (`respawn`) | FIRST: (5, 5) at 364 off B's lip over C into the void, SAFE (6, 5) | **BENCH** (no flag, no cup: a respawn is bz_safe's); on TPLY a fall respawns at a flag |
  | phys 2, `lip` (`takeoff`) | FIRST: (9, 6) at 100 off B's lip, a rubber bounce on C | the plateau ramp's lip: (33, 32) at +wx 100 - takeoff, bounce |
  | phys 2, `rail` | FIRST: (5, 4) at (-150, -250) into the rail at wy 3 | the plateau's back rail (wy 30): (29, 31) at (-150, -250) - gvy -243 to 89 |
  | phys 2, `goal` (the face's goal line) | FIRST: (12, 6) at 250 into C's goal column | the split goal from the sand, (25, 19) along -wy - exit 0 |
  | phys 3, `ramp-*`, `hop`, `hopagain` | TRIAL's start | the start (19, 14): the arrows, then the chord along +wy - no fall, each ball |
  | phys 3, `stepup` (`airwall`) | FIRST: a Hop up B's ramp at -200 | the plateau's ramp: (33, 32) at -wx 200, a Hop - `_no_airclimb` parts at step 4 |
  | phys 3, `grip` | TRIAL: H (5, 11) at 300 | H (19, 14) at +wy 300 - stopped, no takeoff |
  | phys 3, `catch` | TRIAL: F (10, 11), 6 units up | F (19, 19), 6 units up |
  | phys 3, `eastwall` (`edge`) | TRIAL: the chord into G's east rail | the yard's plain EAST wall: (35, 28) at +wx 300 - `_east_w1` parts (G's rail faces +wy here) |
  | phys 3, `bumper` | TRIAL: steel (13, 17) at gvy -200 | steel (25, 22) at gvx -200 into the ice's back rail - 179 = 230/256 of it |
  | phys 3, `ice`, `sand` | TRIAL: (15, 17), (12, 18) at -300 | (25, 24), (26, 21) at gvy -300 - -300 kept; 40 steps on the sand |
  | phys 3, `mat` | TRIAL_MAT (19, 14) | the mat (23, 29) |
  | phys 3, `bounce` (`bounce`), `stun` (`stun`), `shatter` (`shatter`) | TRIAL: `shot()` off H's lip over the gap | `shot()` turned: 20 gu before H's lip (wy 18) along +wy at the cap - rubber onto G; steel stunned, glass shattered on F |
  | phys 3, `ramphop-*` (`absimpact`) | TRIAL: (17, 11) down the steep ramp | G (19, 26) along +wx at the cap, a Hop - `_abs_impact` parts at 35 / 40 |
  | phys 4, the MILL replays | MILL | TMILL |
  | phys 5, `flag` (`ckpt`) | MOON's flag 0 and a pit | flag 0 (26, 26) rolled into the hole (26, 30) - respawned on it; `_ckpt_safe` parts at 137 |
  | phys 5, `flagmat-*` (`ckmat`) | PEAK's flag 3 (glass), MOON's flag 2 (rubber) | flag 1 (glass), flag 0 (rubber) |
  | phys 5, `padswap-*` (`padftg`) | every pad of MOON and PEAK | the three pads (30 / 32 / 34, 29) |
  | phys 5, `cup-128`, `cup-lip` (`cupv`), `cup-stun`, `cup-shatter` | PEAK's cup | **TCUP**'s cup (13, 5): 128 from (12, 5) holes out, 256 lips out; the stun and the shatter as PEAK's |
  | phys 5, `spring-tier` | PEAK's spring 1 onto the upper tier | spring 1 (29, 35) from (29, 36) at -wy 192 - grounded on the plateau |
  | phys 5, `spring-max` (`springsum`), `spring-shatter` | PEAK's spring 2 | either spring (589 = max(360, the rebound)) |
  | phys 5, `return` | MOON's flag 1 | flag 0 or flag 1 |
  | phys 5, `tilt` (`tiltcap`) | FIRST's start | the start |
  | phys 6, `boost`, `pumpchk` (`pump`), `bouncefirst` (`tokbst`), `steelglass-*` | PLAYGROUND's start on the apron | the start |
  | phys 6, `boostclimb`, `boostdrop`, `boostfall` (`noadd`) | PLAYGROUND's 1.5 / 1 / 2-unit rungs | the rungs 1.5 (wx 10 - 12), 1 (13 - 15), 2 (7 - 9), as found there |
  | phys 6, `rampnot` (`rampboost`) | TRIAL's or FIRST's ramp | the steep ramp (21, 25) |
  | phys 6, `sandnot`, `matnot` | PLAYGROUND's sand lane and mat | the sand (25, 18), the mat (21, 28) |
  | phys 6, `liftnot` (`slabcell`) | MILL's lift | TMILL |
  | phys 6, `flagboost` (`noflat`) | TRIAL / PEAK / MILL / MOON flags | flag 1 (19, 26) (flag 0 too) |
  | phys 6, `springarm` (`springoff`), `spentspring` (`nospent`) | PEAK's springs, (24, 33) to (27, 33) | spring 1: at (160, 0); from (26, 35) along +wx at 160 |
  | phys 6, `drag-rest`, `drag-cap` (`ceildrag`, `slowdrag`; the span) | PLAYGROUND's longest level run, RIGHT held | the STRIP, one arrow DOWN: from rest at (35, 30), 320 steps to 250 (the top 252); from the cap at (36, 32), 203 steps to 257. Phase 3 CHANGES the arrow (Right's run would need 26 cells of width) and stops the search on ANY event (its `corner` exemption picks a ball pinned in a corner on TPLY) |
  | phys 6, `gripglass`; 6b `gripsteel` | PLAYGROUND's apron | the apron's back row, (7, 12) |
  | phys 7 (6b), `armearly` (`armwin`), `armroll`, `armlate` (`nograce`, `graceoff`), `armlate5` (`grace5`), `hoponly` (`hopedge`), `armheld` (`noheld`), `ledgehold` (`heldarm`, `nogate`), `fallarm` (`nofall`), `fallnone`, `mashchain`, `gripchain` | PLAYGROUND's apron and rungs | the apron and rungs: each as written, `PLAY_RUNGS` / `PLAY_FRONT` pointed at TPLY |
  | phys 7, `timeout` (`toutoff`) | FIRST's limit | **TQUIK** (8 s); TPLY's 20 s times out at step 1,100 |
  | phys 7, `exit0`, `exit1` | TRIAL's split goal | the split goal, from (25, 19) / (26, 19) along -wy |
  | phys 9, `glass-*`, `probe` (`famrsp`), `pickups`; `--check`'s families (`famcell`) | PLAYGROUND's families and demo | OPEN: no family on TPLY |
  | phys `--check`, the no-family unicorn runs | MOON's and PEAK's demos | TPLY's route demo (TQUIK's, TCUP's) |
  | replay 1 - 3, `record`, `replay`, `inject` (`hopbit`, `framekeys`) | TRIAL: free play off H's lip and over the gap; steel stunned, glass shattered on F | TPLY from its start: H's lip 3.5 tiles along +wy, the gap, F |
  | replay 4, MILL (`propclock`, `noident`) | MILL | TMILL |
  | replay, wave 4 `mouse` (`tiltmap`) | MOON, T MOUSE, a respawn | TPLY free play (the gap or the strip's void respawns it) |
  | replay, wave 6 `play`, 6b's mouse boost | PLAYGROUND: a Hop and its boost at the start, along the apron to the brake strip, Grip | the start, -wx along the apron to the lane wx 12, down it, Grip: rubber stops 1.9 tiles onto the strip (`play_grip`; steel stops on neither course) |
  | ring ground, `boostclimb` (`camz`), `boostdrop` | PLAYGROUND (bonanzaphys's) | TPLY (bonanzaphys's) |
  | ring ground and camera, `trialdrop` (`camring`, `latpad`) | TRIAL (bonanzaphys's `bounce`) | TPLY's `bounce` |
  | ring ground, `voidfall` (`nosafe`, `nolatch`) | PLAYGROUND's strip lane into its void | the lane wx 12 into the void over the well: `play_fall` CGA kill 213, `nosafe` lost 191, `nolatch` halts at 198; Hercules kill 181, lost 169 (PLAYGROUND: 228 / 220 / 223) |
  | ring camera, `dither` (`camhyst`) | PLAYGROUND's demo at its fork | OPEN: a fork of TPLY's route demo, to be searched |
  | ring camera, `ramp-*`, `mill-demo`, `side`, `peak-demo` (`camcap`), `peak-cannon` (`campreaim`, `camprex`) | MILL, PEAK (the lift, the cannon) | TMILL |
  | ring, `nodither` (the bench leg's data) | every course undithered: PLAYGROUND's 292 masks refuse | TPLY undithered: 95 masks |
- [x] **A test pathway** for bonanzapath's secret and paging legs. BUILT as
      **THE TEST MAP** (SPEC.md 130.54.6, `apps/bonanza/courses/pathdev.bbc`,
      `test` on the pathway): the BZDEV=1 build compiles it as its pathway in
      place of `path.bbc` (`BZ_PATHDEV`; a pad-0 knob's map still wins), so
      ONE boot walks every leg and the shipped build is byte for byte what it
      was. Pads 0 ROLL and 1 HOP are the shipped map's cell for cell; then 2
      TQUIK, 3 TCUP, 4 TPLY (page 1, an icon), 5 TMIL (1 unit up), 6 BENCH
      (hidden). Routes: 0 -> 1 STRAIGHT across (ROLL's exit 0); 1 -> 2 up;
      2 -> 3 the DIAGONAL (Up and Left; TQUIK's exit 0); 3 -> 4 across the
      PAGES (TCUP's exit 0); 4 -> 5 the CLIMB, a one-cell ramp of 1 unit
      (TPLY's exit 0); 2 -> 6 SECRET, a SIDE, keyed by TQUIK's new HIDDEN exit
      1 (its goal column's front cell (14, 7)). The shipped map keeps its
      host items (bbcourse's `path` section compiles `path.bbc`), and
      bonanzapath can keep a light host-side look at it (pad 0 ROLL -> pad 1
      HOP in a non-BZDEV build's `BZPATH.BIN`) if phase 3 wants one.

  The legs on it, phase 3 (bonanzapath is NOT rewritten yet: today it walks
  the test map through its own table reads, which already find every feature
  below, and its secret leg still patches the shipped files):

  | bonanzapath leg | today (the shipped map) | on the test map |
  |---|---|---|
  | 0. a new game resting on pad 0, gates closed | pad 0 ROLL | unchanged (pad 0 ROLL, the shipped cell) |
  | 1. no arrow moves it; Space the info card | pad 0 | unchanged |
  | 2. / 2s / 2e. ROLL's finish sequence, the clock, the fall in it, Enter skipping it | ROLL poked to its goal | unchanged: ROLL (a shipped course; TQUIK's goal is the cheaper home if phase 3 wants it, as pad 2) |
  | 3. / 3r. pad 0 DONE, its gate's poses, the auto-roll | route 0 -> 1 | unchanged: route 0 -> 1, the same cells |
  | 4. every arrow takes it back and brings it back (`nodiag`'s red: pad 1's Left) | route 0 -> 1, Right / Left | unchanged |
  | 5. / 5l. the HELD pathway, Esc costs a life | HOP on pad 1 | unchanged |
  | 6. the forced fallback | HOP | unchanged |
  | 7. the game over | HOP | unchanged |
  | 8. a new game, every route poked open | the shipped routes | the test map's five open routes (the secret one left closed, as today) |
  | 8d. the DIAGONAL's two arrows | pad 5's road back to pad 2 (prototype pads) | pad 2 (TQUIK) -> pad 3 (TCUP): Up and Left, back Down and Right |
  | 9. the PAGED camera (`nopage`'s red) | pad 5 -> pad 6 (MOON -> PLAY) | pad 3 (TCUP, page 0) -> pad 4 (TPLY, page 1), Up |
  | 10. the icon's lanes walked, no other icon's marked | pad 6 (PLAY's icon) | pad 4 (TPLY, `playground32x24`); pads 0 and 1 the other icons |
  | 10b. rolled on: the icon at rest, unmarked, "up a ramp, gz > 0" | pad 6 -> 7, no ramp: SKIPPED | pad 4 -> pad 5 (TMIL) up the ramp, gz 1 unit: CHECKED |
  | s0. / s1. the SECRET route: reveal groups in order, the hidden pad shown, the visible end with the route | a private tree: ROLL's goal split by a patch, a pad and a secret route appended to path.bbc, EVERY course recompiled | the build's own: TQUIK (pad 2) finished by its hidden exit 1, route 2 -> 6 to the hidden pad 6 - no patch, no private compile, the main leg's boot (s0. at the new game, s1. after 8.) |
  | `--check`: the follower under unicorn | the shipped part's routes and the private map's | the test map's six routes both ways (the ramp's included) - one part, no private map |

  bbcourse's `path` selfcheck items, phase 3 (today they run on the shipped
  `path.bbc` and the private maps PATH_TEST / PATH_SHORT, which name only
  ROLL, HOP and a synthetic HID - no prototype course - so they need no move
  to stop depending on prototypes; what ties them is the shipped map's
  SHAPE):

  | item | today | on the test map |
  |---|---|---|
  | the shipped pathway compiles, no occluders, tables read back, no secret route | `path.bbc` | stays the shipped map's (it is the shipped part) |
  | the shipped map's layout (pad 0 ROLL, pad 1 HOP, pad 2's two exits branching, a page route) | `path.bbc` | stays (the owner's map; redrawn with it) |
  | a secret route's reveal lanes, its hidden pad's poses (SIDE) | PATH_TEST (HID's hidden exit) | the test map's route 2 -> 6 (TQUIK's exit 1, SIDE): PATH_TEST and PATH_TEST_HID can go |
  | a SHORTCUT verdict | PATH_SHORT | stays PATH_SHORT (the test map's secret route is a SIDE) |
  | the refusals edited on the shipped text (`P(...)`: pad numbering, steps, ramps, crossings, keyed twice, two diagonals, unreachable, off-window, lives, icon corner, gate off route, exit it has not) | anchored on `path.bbc`'s lines (pad 7 FIRST, route 2 5, pad 5's gate ...) | re-anchored on `pathdev.bbc`, which does not move when the shipped map is redrawn |
  | the refusals on the private map (`T(...)`: gate on a secret route, a non-hidden key, neither SHORTCUT nor SIDE) | PATH_TEST | on `pathdev.bbc`'s route 2 -> 6 |
  | the key map: straights beat a diagonal | the shipped pads 2 and 5 | the test map's pads 2 (Down a straight, Up and Left the diagonal) and 3 |
  | every route followed both ways arrives exactly | the shipped routes | both maps' (the test map's ramp included) |
  | 130.54.6: the test map's features, its secret's hidden key, the two refusals | - | BUILT (this item) |
- [ ] The B benchmark takes a course (no hard-wired BENCH).

### Phase 3 - the rows on them, bundled
- [ ] bonanzaring and bonanzawheel on TMILL/TPLAY; ground and camera one replay
      list.
- [ ] bonanzaphys: unicorn for the physics, a few MartyPC replays a card.
- [ ] bonanzagame: one boot a card - hostile and physics-identity files by
      reload.
- [ ] bonanzaexit, bonanzademo, bonanzareplay: the six ways out once on
      TQUICK; one refusal test, one save/load/double-click test; logs made
      from the model.
- [ ] bonanzaperf: its gates on few runs; the matrix `--baseline`'s.
- [ ] bonanzacourse: the prototype-tied sections moved to test courses.

### Phase 4 - measured
- [ ] Every row's `secs` re-measured; the scoped bonanza soak's wall clock
      before and after.

## Order independence and the save file (the owner, 2026-11-19)

The owner: *"having everything depend on an order that can and will change
is bad; lets not depend on that. Once those two are done, then bench can come
out of the shipping build."* Decided:

- [x] **Every course names its song** (`music` on every `.bbc`; no song by
      position). `bbcourse.course_song` refuses a course without one.
- [x] **N and M go, and so does the tour** (G, MAIN's tour line,
      `BZ_TOUR`, `BZ_CRS_TOURX`); rows poke the course and ball instead.
      BONANZA.DAT's +146 tour bytes are a reserved zero field until BZS5.
- [x] **No K in the game's defaults**: Enter's course is the pathway's
      pad 0, not `BZ_CRS_FIRST`; the demos are a table of named rows, not
      `BZD<K>`/`BZ_NCRS - 1`; the tool's exemptions name courses.
- [ ] **No K in the rows**: courses found by NAME (`CRS_K[name]` only as a
      lookup), never a literal K, never "every K but 0", never "the demo of
      K - 1".
- [x] **Then BENCH leaves the shipping build**: B benchmarks a course it is
      given (a test course in the `BZDEV=1` tree).

The save file, BZS5 (AGREED, the owner 2026-11-19: *"Progress by pad seems
good."* - after rejecting keying progress by course
name: *"The pathway is a progression tree; if we move a course from spot 5
to spot 17, then they just have a random place far ahead of their current
progress unlocked ... Now they have no way to get back."*):

- **Progress** is keyed by the pathway's PAD NUMBER and exit, which stay put
  when a course moves between pads; the pathway gets a `version` line that is
  raised to reset progress deliberately when its tree changes shape.
- **Bests** are keyed by course NAME + the course's `version` line + the
  physics version: an art change keeps a best, a raised `version` clears
  only that course's (*"Course version: Yes, this is good."*).
- **Replays** stay keyed by the course's identity (*"keep it as is"*).
- Pre-release, so no BZS4 migration: a BZS4 file is refused as any foreign
  file is.

## Measured (scoped soak `-k 'bonanza*'`, 4 lanes)

| run | tree | wall | ok / FAIL / SKIP | the reds |
|---|---|---|---|---|
| baseline, 7 emulator rows | 145bfb760 | 1:03 | 5 / 2 / 0 | ring TIMEOUT (CPU 1,500 s), sound (a stale leg) |
| phase 1, 17 rows | 7064886658 | 1:54 | 12 / 4 / 1 | course (stale checks, ROLL flag 1), ring (Herc TRIAL), demo and path (harness) |
| order + BZS5 + no BENCH, 17 rows | 42432ee993 | 1:38 | 13 / 3 / 1 | course (ROLL flag 1, PAD_MAX, PLAY), ring (Herc TRIAL), exit (F's course) |

Per row at 42432ee993, seconds: phys 2,778, demo 2,597, exit 2,528, ring
2,447, wheel 1,782, replay 1,766, perf 1,299, path 1,296, course 1,229,
physhost 1,183, sound 721, game 559 (2,756 at 7064886658: one hostile file
a boot), dquarter 450, title 44. bonanzaring finishes now (the caches);
phase 3 is where the wall clock comes down.

Owner decision open: ROLL's flag 1 at (36,42) is bounced past by a rubber
ball on section E's steps (the selfcheck's item 8; a fall at the leap then
respawns at flag 0).
