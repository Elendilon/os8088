# BOUNCE BONANZA: the course design guide

*Wave 11's working document (the plan's [wave 11](../BOUNCE-BONANZA-PLAN.md#wave-11-the-tutorial-and-the-course-pipeline-m)).
This directory holds it and, one file each, the design sheets of the shipped
courses (`<NAME>.md`). The rules here are the owner's, from the review of
every test course on 2026-11-18 (verbatim in
[the diary](../BOUNCE-BONANZA-DIARY.md), "the owner reviews the test courses"),
added to the course-design notes CD1 - CD6 of 2026-11-14 (the plan's R1).
Where a rule is checked by `tools/bbcourse.py`, the check is named; where it
is not yet, the story that adds it is named. A rule with neither is the
designer's and the owner's judgment.*

*The pathway's initial-look options (2026-11-19) are in [pathway/](pathway/README.md).*

*What 3-wide chutes would cost (a deferred study for DOWN, 2026-11-20) is [CHUTE3.md](CHUTE3.md).*

*What two lifts in a course would cost, and where DOWN could put steel's (a study, 2026-11-20), is [LIFT2.md](LIFT2.md).*

*What raising the 1,024 px course width would cost (a study, 2026-11-20) is [WIDTH.md](WIDTH.md).*

**Every existing course is a test course.** FIRST, TRIAL, PLAYGROUND, MILL,
MOON, SUMMIT (PEAK), BENCH and the props' labs ship nothing. Ideas and
components are taken from them (section 5); none is reworked into a shipped
course.

## 1. The rules

### 1.1 Length and pace

- **G1. A course runs at least 25 s, usually 35 s or more.** *(Amends CD3's
  "about 30 s for the early courses": 25 s is the floor, not the target.)*
  The design sheet states the target and the pace; the tool's route time is
  the measure. *Check: story 11.11 (a floor on the slowest finish's route).*

### 1.2 The camera

- **G2. Horizontal pans happen on the ground, at moments the design chose.**
  *(Softened 2026-11-18, after FIRST ROLL's first play: "we may not be able
  to avoid more horizontal; we want to keep the courses visually
  interesting, and I think that rule is making that hard.")* Vertical
  scrolling is smoother than horizontal (2 lines a step against 8 px), so
  vertical runs are welcome. But a course is free to go across where that
  makes it more interesting. What matters is WHERE the camera pans: on the
  ground, at a turn or a flat, never during a jump (G3), and not back and
  forth on every leg. A course whose whole picture fits one window may also
  hold the camera still across with **`lock across`** (SPEC.md 130.45;
  the owner: "We won't use this often due to visual interest, but for the
  intro course it fits fine"). The tool refuses it on a course wider than
  the window.
- **G3. A jump never needs a horizontal pan.** Plan each jump (take-off,
  flight and landing) so the camera does not scroll sideways while the ball
  is in the air. **A CANNON's throw is exempt**: the player is not steering
  it (the owner, 2026-11-18). **A SPRING's is not**: the player steers it, so
  a spring flight should not pan, with exceptions per use after a playtest. *Check: story 11.11, a report of the columns panned while
  airborne on every route and author script, and a refusal on an intended
  jump.*

### 1.3 Seeing the course (CD1, extended)

- **G4. Every mechanic is visible, and so is its result.** Springs, pads,
  cups, tube mouths and their landings: CD1 and story 11.5. A
  **precision element** (one that needs a particular speed or timing) also
  shows its approach, its outcome and the way the player gets that speed,
  such as a run-up of readable length, a boost pad or a slope. SUMMIT's two
  springs failed on every count: the springs hidden, the result unseen, and
  no clue to the control that gave the speed.
- **G5. A main-route finish is fully visible.** Only a deliberate secret
  finish (decision 6) may be hidden. SUMMIT's hidden end hole is the case
  this refuses. *Check: story 11.5's cup and goal marks.*
- **G6. Hiding the ball briefly is allowed when the mechanic stays clear.**
  MOON's tubes, fed by guide lanes into several short routes, are the model:
  where the ball goes is obvious while it cannot be seen. A path the player
  has to GUESS is never allowed, and an unguarded path that cannot be seen is
  a guess. *Check: story 11.5's hidden stretches (0.5 s, under 30 degrees of
  turn, or declared `hidden`).*

### 1.4 Never stranded

- **G7. No softlock, ever.** From anywhere the ball can reach, a finish or a
  respawn (a fall, a flag) is still reachable. MILL's left windmill (an
  invisible exit onto a side ledge) and MOON's dead-end pathway are the cases
  this refuses. *Check: story 11.12. Today `trap_check` proves it only from
  flags and pads, so it is extended to every reachable cell (and every
  family state).*
- **G8. Penalty paths are short.** Making the player slow steel for a
  stretch when they took the obvious line (SUMMIT) is fine, if it is brief
  and comes back to the course.

### 1.5 Clocks (the course's only timer)

- **G9. A clock face can be seen from the start and from every finish
  line.** *Check: `finish_clock_rule` for finishes today; story 11.13 adds
  the start.*
- **G10. Two clocks never share a screen**, including near a finish. TRIAL's
  two clocks on one screen are the case this refuses. *Check: story 11.13,
  over the camera model of every route.*
- **G11. A clock never obstructs a main pathway.** It may:
  - float, with art that reads as floating;
  - stand on a tile off the primary pathway;
  - stand on a lone pillar;
  - hang off the side of a pathway, out one tile on a stick or bracket.
  It should also look as if it belongs there. MOON's end clock was
  functionally off the route (because of the block behind it) but did not fit
  in visually. *Check: `finish_reach_rule` keeps finishes reachable today;
  story 11.13 refuses a clock on the route's cells. The new frames are story
  11.14.*
- **G12. Clocks are seen periodically, not constantly.** No stretch longer
  than about 15 s goes without a clock in view. That usually means 2 - 5 a
  course: 3 is the norm for 25 - 45 s, with more on longer courses or ones
  whose finishes are far apart. *Check: story 11.13 turns
  `clock_visibility`'s share into the LONGEST gap, refused past 15 s.*
- **G23. Clock art is high quality, standard or custom.** Clock art is placed
  per use and per course anyway, so a course may mix frames where its
  positions demand it, such as one standing and one floating or fixed to the
  side of a block. Two routes, and the owner chooses by what the bytes say:
  - **custom clock art per course**, made to fit the course's theme, or at
    least unique to it;
  - **standard-part clocks** (a pillar, a float, a side bracket, and so on),
    taken when the saving is significant, with custom art only where no
    standard one can be designed in easily.
  Either way every clock is held to the same bar of quality. *Story 11.14
  prices both routes before the second course is drawn.*
  **What decides it is the ART BEHIND a clock.** A clock's picture BAKES IN
  whatever is behind it, since nothing is composited at load. So a standard
  clock can only stand where the same thing is always behind it: in
  practice, where only the VOID is behind its head. The pillar under it is
  fine. Where a course cannot be designed round that, its clocks are custom.
  **The owner leaned to CUSTOM art (2026-11-18, FIRST ROLL's first play):**
  *"None of the clocks is fully tiled behind void, and I'm starting to think
  course design with that as a requirement is going to be very hard ...
  I'm thinking the custom art might be the way to go here."* So a clock is
  placed for the CAMERA: whole in view where it serves, never partly behind
  a block (FIRST ROLL's start clock was, and it looked bad). What is behind
  it no longer decides where it goes.
  **The brief for a clock-art agent (the owner, 2026-11-18, choosing FIRST
  ROLL's `pin`)** - repeated to every clock designer so far, so it goes in
  the brief rather than the review:
  - **The digits fit into the art.** A clock needs no "window" at all: the
    first clock arts have none, and the owner calls that *"perfectly
    acceptable and good"*. **Cyan is not forbidden**: *"it really does read
    fine on herc"* with the solid black numbers on top, so do not avoid it
    (or swap it for white) on the Hercules' account; but art that works
    well without cyan is equally welcome (the owner, 2026-11-19).
  - **No flat squares.** *"I don't like flat squares in general, because
    they don't blend in with the art usually."* A clock is an OBJECT in the
    scene that its digits belong to, not a panel stuck on a post: of
    `pin`, `tee`, `board` and `lamp` only `pin` *"kind of works because it
    is a sign hanging from a pole, which somewhat fits the art"*, and
    `lamp` maybe.
  - **Something on the clock represents where this is in the course** (the
    owner, 2026-11-21, choosing DOWNHILL DECISION's `orb`). One object, and
    what changes between its uses says where the player stands: DOWN's orb
    is the course's balls - RUBBER at the start, a SPLIT orb at the hub (its
    steel half toward the steel way, its glass half toward the glass way),
    and STEEL or GLASS at each finish, the material that finish is reached
    in (SPEC.md 130.18.5.2). LITTLE HOP's frogs turning to look down the path
    are the same idea in pose rather than material.

### 1.6 Balls

- **G13. Rubber is the main ball.** This is *Bounce Bonanza*: most of the
  game is played as rubber. Steel and glass are MECHANIC balls. The player
  becomes one, does a stretch of course that uses it, then goes back to
  rubber (so a stretch ends with a rubber pad). Each other ball may have one
  focus course.
- **G14. A pad sits where its ball is needed next.** Its purpose has to make
  sense from what is around it. Half of MOON's pads did not.
- **G15. A material trap may catch a player who rushes.** SUMMIT's skippable
  glass pad was acceptable: go too fast and you may become glass, then break
  trying to be quick on the stairs. Use it as a deliberate choice.

### 1.7 Surfaces and props: each one earns its place

- **G16. Sand is sparing and purposeful.** Use it where the player should
  slow down, or where speeding up or jumping should be hard: a strip before
  a hole, a ring round a cup. Not a big platform (MILL) and not a nuisance
  before the end (TRIAL). MOON's slight ramp up to a hole ringed in sand was
  the first good use.
- **G17. Ice needs a reason.** For example, it stops an early brake before
  something that needs speed (SUMMIT's ice was just about justified). Ice at
  a start with nothing after it (MOON) has none.
- **G18. Lifts go UP, somewhere the player could not otherwise go.** No lift
  to a place reachable by a jump. A lift that brings the player BACK up (for
  example after a keyed gate) is a valid use.
- **G19. Fast sections are entered fast.** A straightaway (MOON) is built to
  be arrived at with speed.
- **G20. A flag stands just BEFORE what can kill.** *(Revised 2026-11-18,
  from FIRST ROLL's pen-in: "We should flag right BEFORE what we think will
  kill them, not after, and avoid making them redo long sections.")* A fall
  then replays only the hazard, never a long stretch before it. There is no
  flag where nothing ahead can kill: FIRST ROLL has none past its leap. Not
  right after the start either (MOON's first flag came far too soon).
- **G21. Helping props are a difficulty setting.** Rails beside a bumper
  field (MILL) make an early course easy. A later course can use the same
  shape without them, or without the bumpers (CD2).
- **G22. Several answers to one obstacle.** FIRST's jump fails if the player
  just holds straight on, and succeeds if they slow down, Hop, or take
  either side. An obstacle that rewards thinking without a single exact
  answer is the model for the early courses. The "exactly this speed" kind
  is for later courses, and only under G4.

- **G24. Rails protect; on an easy course they never block.** A rail
  stands where a fall would be, never across the way the player is going
  (FIRST ROLL's first sketch had a rail stub across the leap's run-up). The
  STYLE is a choice per course, and even per rail: the see-through GUARD
  RAIL exists to fix occlusion, and the classic BLOCK RAIL suits an open
  course where it hides little. This is a style choice, not a rule.

### 1.8 Already binding, from 2026-11-14 (the plan's R1)

CD1 visible mechanics, CD2 increasing challenge (each sheet names its place
on the curve and its one new demand), CD3 longer courses (amended by G1), CD4
the physics defaults, CD5 three-tile gaps onto a lower floor as a rubber rung,
CD6 boost spots.

### 1.9 The checks, as built (stories 11.11 and 11.13, 2026-11-18)

A course that says **`guide`** is a real course, held to the checkable
rules. The prototype and lab courses do not say it, so nothing of theirs
moves.

- **At every compile, in milliseconds, refused:**
  - **G9**: a clock's digits inside the CGA window centred on the start.
  - **G10**: no two clocks' digits fit one CGA window ANYWHERE. This is
    checked pair by pair, which is stricter than along a route and needs no
    run.
- **`bbcourse.py --guide COURSE.bbc [--log DEMO.bzd ...]`**, over every
  complete run (the autopilot's route when it reaches a finish, and each
  demo given), on both cards, refused:
  - **G1**: a run under 25 s.
  - **G3**: a horizontal pan during a flight. A flight that ends in a fall
    is not a jump and is not counted, and nor is a tube's.
  - **G11**: the ball's footprint meets a clock's (solid) cell.
  - **G12**: more than 15 s with no clock's digits in the window.

  It prints each run's time, flights, pans and longest clockless stretch.
  With no complete run it says so and refuses nothing, so the playtest loop
  never waits on a run (section 3).
- **Broken on purpose, each went red**:
  - G9: a copy of ROLL with its start clock removed;
  - G10 and G1: the prototype FIRST (two clocks on one screen; a 2.8 s
    route);
  - G3: MILL (16 columns in one flight) and SUMMIT;
  - G11: MILL with a clock on its route;
  - G12: SUMMIT (23.5 s with no clock in view).
- **Answered (the owner, 2026-11-18)**: a cannon's throw is exempt from G3
  (the check skips a flight that leaves a tube); a spring's is not, with
  exceptions per use after a playtest.
- **Discovered on FIRST ROLL's first play: a zigzag course still pans.**
  LATTICE frames the window at positions 128 px apart and LEADS in the
  direction of travel, so its no-pan band is only about 110 px. A vertical
  course alternates +x and +y legs, and every leg of 4-wide pads crosses
  that band. The owner's 30 s play panned 16 - 24 columns five times, twice
  in the air. Re-laying the course to a 168 px route swing still left five
  or six sweeps. The course's whole picture is 320 px across, so ONE fixed
  horizontal framing would show all of it. That is a camera change (a
  per-course horizontal lock). TAKEN and BUILT: SPEC.md 130.45, `lock across`.

### 1.10 Reading the course: guidance from LITTLE HOP (2026-11-19)

*Guidance, not rules (the owner: "mostly good general guides, but not hard
constraints"). What course 2's seven revisions taught about what the player
can SEE; each is a default to depart from with a reason.*

- **Climb up the screen, drop down it.** The camera sees only a tile's +x
  and +y faces, so a step UP climbed moving +x or +y shows no riser and
  reads as flat; climbed moving -x or -y, the riser faces the player. A drop
  reads best taken moving +x or +y, the edge left behind showing its face.
- **A gap between grounded columns needs a LIP.** The near island's side face
  fills a 1-tile gap exactly as it fills a step's riser, so the two look
  alike. Floating the lip row before the gap one unit thick (`float ...
  thick 1`) leaves a black notch under it: a notch means a gap, no notch a
  step. The lip is on the island whose face is in view: the near one for a
  gap taken down the screen, the far one for a gap climbed up it.
- **Keep apart what does not connect.** Two surfaces a tile apart at nearly
  one height read as one hop, whether or not the course means it; about
  three void tiles, or a clear height difference, keeps a non-route
  neighbour from looking like the route.
- **The jump rungs** (quarter heights, SPEC.md 130.48): a 3/4-unit step
  is the EASY jump (no ball rolls up it, every ball's Hop climbs it), and a
  1-unit step is the hard single jump or rubber's easy double jump. A 1-tile
  gap is an easy Hop; a 2-tile gap needs a precise "and again".
- **Give a start some roll room.** At least three tiles before the first
  jump, so a player never has to back up to get going.
- **Signs say what to do next, where it is done**: "JUMP!" before the jump,
  not after it ("a 'here is what you need to do' instruction instead of a
  'do this to get here' instruction").
- *Specific to a TEACHING course, not general:* a long run-up before a move
  being taught (LITTLE HOP's five-tile U1 before the double jump). A test
  course may cut it short on purpose.



One per shipped course, written before its `.bbc`; it is the PEN-IN of
section 3. [FIRST-ROLL.md](FIRST-ROLL.md) is the first. The plan's pipeline step 1
lists the fields: world, families (at most 3), start ball, finishes and their
exits, time-limit target, palette, clock frame, song, and the one new idea.
From this guide it also states:

- the target time (G1) and the pace;
- the camera plan: the main direction, every horizontal stretch and why, and
  each jump's pan (G2, G3);
- the clocks: where, which frame, and how each obeys G9 - G12;
- each ball stretch: where it starts and where the rubber pad ends it (G13,
  G14);
- each surface patch and lift, and what it is for (G16 - G18);
- each precision element: what the player sees, and how they get the speed
  (G4);
- the place on the challenge curve and the help it gives or removes (CD2,
  G21).

## 3. The pipeline: pen in first, then iterate FAST

The owner's rule (2026-11-18): *"I do not want what keeps happening, to
happen again - where iteration time is 30+ minutes on each simple change."*

1. **Pen in.** Imagine the course, draw pictures and go back and forth with
   the owner, all before the engine. The design sheet holds the pictures,
   drawn by a host-only sketch script in the course's own folder
   (`first/sketch.py` is the first). Revising a sheet costs minutes.
2. **In the engine: play around and revise.** The `.bbc`, the tool's
   `--png` previews, `--selfcheck` for that course alone (`--only`), a
   playtest disk. **No soak, no long tests, no demos and no performance
   checks inside the loop.** A change is an edit, a compile, a disk sent:
   minutes, not half an hour.
3. **Demos and performance afterwards, batched.** Routes, author scripts and
   demos, the miss measurement (T11) and the course's rows are run when a
   course settles, possibly after several courses, or in the background
   while design goes on (fork rule 9). They never stand between an edit and
   the next playtest disk.

A tool check that is slow on a big course (story 11.12's softlock check is
the likely one) runs in the batched step, not in the edit loop, unless it
is fast enough not to be noticed.

## 4. Props in use: patterns

Most of the props (water, magnets, wind, boost pads, spikes and the
membrane, gates and the drawbridge, the archway, the see-saw, the
turntable, humps, the guard rail) have **no course-design patterns yet**.
They were built in labs. Each gets a short entry here when a course first
uses it: what it is for, how it is introduced, its easy and hard forms, and
what to avoid. The ones the test courses taught:

| prop | pattern | from |
|---|---|---|
| windmill | its entry and exit both plainly visible (MILL's right windmill); never an exit the player cannot see | MILL |
| bumpers | after a ramp down into them; easy to hit, never inescapable; rails beside them in an early course | MILL |
| cannon | launches from halfway up a pillar; a throw into a visual spin; "cannon into a flag" | MILL, SUMMIT |
| tube | a fan of tubes to short alternative routes, fed by guide lanes | MOON |
| spring | only where both the spring and its landing are visible (G4) | SUMMIT, as the counter-example |
| pads | where the ball is needed next (G14); a skippable trap pad (G15) | MOON, SUMMIT |

## 5. Taken from the test courses

| piece | from | as |
|---|---|---|
| the hill of ramps | SUMMIT's opening | a candidate opening for the new first course: an introduction to ramps |
| the multi-answer jump | FIRST ROLL | a pattern (G22), re-planned so the camera does not pan (G3) |
| the bounce from a height over a gap | TRIAL | the idea only, re-tuned to today's physics, with a smooth landing |
| the pit | PLAYGROUND | a STANDARD PART |
| the double hump | HUMPS (back right) | a STANDARD PART |
| the ramp into a bumper field, rails optional | MILL | a standard section (G21) |
| the gentle weave | MOON | a standard section: quick if the player is careful, slower if not |
| "drop down, jump the gap, flag" | MOON | a standard section |
| the tube fan with guide lanes | MOON | a standard section (G6) |
| the stairs, the windmill-or-stairs fork | MOON, SUMMIT | a fork pattern (its side exit re-planned) |
| a ramp up to a sand-ringed hole | MOON | a finish pattern (G16) |
| MILL's opening clock | MILL | the model of a start clock |

Standard parts belong to the kit's K3 (BOUNCE-BONANZA-KIT.md): designed once,
named by courses, copied in at load.

**Not taken**: two clocks on one screen, any softlock, the lift to nowhere,
the sand platform, the start ice with no purpose, hidden springs, the hidden
end hole, unguarded unseen paths, a finish placed only to test the pathway
(TRIAL's split double finish).
