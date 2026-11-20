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
- [ ] **TPLAY** (physics and replays): ramps (one steep), a lip and gap, a void
      with a SAFE cell, rails and a bumper rail, ice, sand and mat strips, a
      split goal (two exits), an apron with rungs and 1 / 1.5 / 2-unit tops,
      a cup, pads, flags, springs, a timeout limit.
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
- [ ] **A test pathway** for bonanzapath's secret and paging legs.
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
