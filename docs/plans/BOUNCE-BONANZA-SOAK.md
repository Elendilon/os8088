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
- [ ] The TOUR's tests deleted: bonanzagame's `tour`, `stop`, `face` legs and
      helpers, the `tourx` hostile case; bonanzaexit's tour exits.
- [ ] bonanzapath rewritten for the shipped map (pad 0 ROLL, pad 1 HOP) and its
      secret leg on a fixed test map; bbcourse's `path` section likewise.
- [ ] bonanzaexit: the claim leg covers every K (a cheap launch per course,
      ROLL and HOP included); the three red arms whose expected text sits in a
      comment fixed.
- [ ] `bonanza_phys --check` registered as a row of its own (the test-only
      courses' only gate).
- [ ] The per-process caches: `symbols()`, `replays()`/`prove()`, the ground
      checks, `title.bbc`'s compile.
- [ ] Stale text (song rows, three ball rows, BZD1 - BZD6) brought to the game.

### Phase 2 - the test courses
- [ ] **TPLAY** (physics and replays): ramps (one steep), a lip and gap, a void
      with a SAFE cell, rails and a bumper rail, ice, sand and mat strips, a
      split goal (two exits), an apron with rungs and 1 / 1.5 / 2-unit tops,
      a cup, pads, flags, springs, a timeout limit.
- [ ] **TMILL** (the wheel and the ring): rotors and lighting posts (2- and
      3-word lanes, one crossing the ring's end), a lift with docks, a tube
      and a cannon, a clock, scrolling both ways, occluders.
- [ ] **TQUICK** (exits and the save): a goal a few autopilot steps from the
      start, a cup, a tube drain, a palette of its own; a two-part twin.
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
