# BOUNCE BONANZA — the next props and tiles (plan)

The owner, 2026-11-17: *"magnets, blowers (wind), and possibly water, and
then a handful (4-5) traps/other small interactive when touched props, and
one or two more windmill sized larger props."* This plan is the round's
list: what was chosen, what was tabled, and what each costs, from a sweep of
every idea already written down (the main plan's sections 8 and 9 and the
owner's decision 8: [BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md)) and a
costing against the tree at the AV merge (`4675757d2`). Every cost below is
PREDICTED until a story says MEASURED.

**The yardstick.** A mechanic that fits the family hooks (SPEC.md 137.25.6:
CELL rewrites the 9-cell window per state and per ball, STEP pushes the ball
every step, timers and lanes for poses) needs no resident change and is
"doable now". Today's family parts are 203 - 680 bytes (`build/bzf-*.bin`),
and since GLASS and PICKUPS joined the resident bundle every resident family
is RAM every play pays; with five or six more, some may go home `fetch`
(137.25.6.9) - a decision for when they are built. A lane is at most 32 x 24
px, and at most 6 FAST lanes meet a window.

**How many families a course may name: ALL of them** (2026-11-18, SPEC.md
137.25.6.5). Until then a course named at most four (the hook lists' shift),
which kept every other family of a round off PLAYGROUND. The engine's slots
and hook lists are now sized to the build's whole family table, so any
course may name every family; each new family costs 14 + 8 x its hooks
bytes of bss. Only the FETCHED families (home `fetch`, the probe) keep a cap
of 3.

## The list

### Chosen - doable now (families, no resident change)

| | what | how | notes |
|---|---|---|---|
| P1 | **WATER** (the owner's design, below) | one family; the tool's depth key draws the ball behind the glass | its own section; the first to build |
| P2 | **MAGNETS**, pulling on or off the course; a 2 - 3 frame WIGGLE lane while active | STEP pulls steel toward each magnet in range (plan: 0.3 - 0.5k a step in range; PREDICTED as built about 0.6k in a field, 2.5k on a cell change) | **VERTICAL magnets**: an upward pull about gravity, so steel HOVERS across a gap under a row of them on an overhang (check: airborne over VOID is not a fall until it drops). **BUILT** on `bb-magnet`, below and SPEC.md 137.33 |
| P3 | **WIND / BLOWERS**: magnets reversed, weighted glass x2, rubber x1, steel x1/4 | STEP pushes in the blower's region (BUILT on branch `bb-wind`: SPEC.md 137.34; about 0.2 - 0.45k a blower a step, 0.23k fixed, PREDICTED) | SQUIGGLES in the air and spinning ground fans as the hint (a pennant an option); across the crumbling bridge the owner's favourite; an UPDRAFT, and a PIT WIND that lifts glass with no jump - BUILT, below |
| P4 | **BOOST PADS** (chevrons): before full courses are built, not post-release | a family pad pushing in its record's direction | a family rather than a surface: a surface moves `BZ_PHYSV` and re-authors every demo; a family moves only the FAMV of courses using it. **BUILT** on branch `bb-boost`: SPEC.md 137.40, below |
| P5 | **SPIKE PIT**: glass shatters, rubber POPS, steel is pushed up to the spikes' height and rolls on - a MATERIAL GATE | CELL per ball (the water trick): floor at spike height for steel, a kill for the others; **POP-UP SPIKES** the same family on a timer, two poses | rubber's POP is new sprite frames (the ball generator, 137.25.5). **BUILT** on `bb-spike` with P8, SPEC.md 137.38 and the section below |
| P6 | **SWITCH PLATES, KEYS, GATES** - an option, not the primary mechanic | a plate or key sets a bit; a gate cell WALL <-> FLOOR with a lane redraw (the cracked tile's state-driven cell) | keys can reuse the pickups' COLLECTED bit. **BUILT** with P7 as ONE family on `bb-gate` (SPEC.md 137.41, the section below): a channel bit in the slot, not a COLLECTED bit |
| P7 | **DRAWBRIDGE** | cells VOID <-> FLOOR on a timer or a switch, a lane a bridge cell | pairs with P6. **BUILT** with it (SPEC.md 137.41) |
| P8 | **GLASS-ONLY: a crystal MEMBRANE** | a tile that is FLOOR for glass only (the CELL-per-ball trick) | the owner asked for a glass-only idea; the updraft (P3) is the other. **BUILT** on `bb-spike`, the SPIKE family's third kind (SPEC.md 137.38) |

### Chosen - moderate

| | what | why moderate |
|---|---|---|
| P9 | **SEE-SAW / TILT PLATE** | the tilt is cell slopes (2 - 3 poses through CELL); the floor moving under a resting ball is the lift's carry adapted, not new physics - **BUILT** on `bb-tilt` (SPEC.md 137.42, below): no resident engine byte, the part 648 bytes |
| P10 | **ARCH to roll under** (also: a ball forced under it cannot boost over a pad, so rubber must take a pad) | ~~the reserved UNDERSIDE flag: resident~~ - **BUILT as a family with no resident change** (the ARCHWAY, SPEC.md 137.39, branch `bb-arch`): CELL walls the arch above the ball's clearance, STEP caps the ball under it; below |
| P11 | **TURNTABLE, quarter-turn**: half filled, a quarter turn every second or so, the cells switching; it does not carry the ball (a cell that turns to a gap drops you) | several SLOW lanes - **BUILT** on `bb-turn` (SPEC.md 137.43, the section below): a family, no resident change; a turn SWEEPS one cell a step, so a table is one pose change a step |

### Chosen - art only

| | what | how |
|---|---|---|
| P13 | **THIN RAILS** (the owner, 2026-11-17: today's rails read as blocks) | a rail stays a one-cell WALL; the ball stops at that cell's near edge, so the tool draws a thin rail ON that edge and the rest of the cell as the open edge it is - the art matches the physics with no physics change (the reserved `edge` bits, thin walls BETWEEN cells, are not needed). **BUILT as the see-through GUARD RAIL** (SPEC.md 137.35, branch `bb-rail`): `guard <shape> [height <units>]`, 2 units by default, posts and bars with the course seen through them, 0 resident bytes; its test course RAIL is the `BZRAIL=1` knob build. The shipped courses' block rails are unchanged (restyling them is the owner's call, 137.35.8 R3) |

### Possible

| | what | why |
|---|---|---|
| P12 | **HUMPS** - fits the theme; cheap to make, expensive to USE, as shapes are | the FIELD cell's height tables (137.28) already describe any height pattern; a hump rises ABOVE the lip, so it hides what is behind it - occluders the pit never needed. A **standard hump** (one shared table set, 137.28.4's STANDARD PROFILES rule) keeps its data down. **BUILT, tool only** on `bb-hump` (SPEC.md 137.44, below): 0 resident bytes, no family |

### Tabled

| what | why |
|---|---|
| a turntable that rotates smoothly and carries the ball | horizontal carry physics, and a turning pattern bigger than a lane needs FAST lanes past the window's 6 |
| loops | a non-planar floor function and a new occluder class |
| conveyors | revisit - "crystal magical minigolf course", not industrial |
| a global tilt switch | not this round |
| pinball flippers | a maybe: no extra keys that do not move the ball; on contact they are a bumper on the side |
| a retracting bumper | no use the drawbridge or pop-up spikes do not cover better |
| a rubber-only gate | rubber is the standard identity; it needs none |
| the sponge ball, golf mode | dropped (golf would be a second game, not a mode) |

## P1 WATER - the design

The owner's sketch: [bounce-bonanza/water-sketch.png](bounce-bonanza/water-sketch.png).
A walkway of floor cells; one of them is WATER (the ripples drawn on it),
flush with the walkway; below it a glass-walled column (here three cells
deep); at the bottom of the column's FRONT face an ARCH, out onto a lower
path running toward the viewer. Rubber and glass roll across the water at
the walkway's level; steel sinks down the column and rolls out of the
front. Several columns in a row with one arch at the far end are the same
thing repeated, for visual interest.

### The owner's answers (2026-11-17)

| | question | answer |
|---|---|---|
| W1 | water's feel | sand's DRAG is fine; LESS bounce than sand (rubber's rebound lower than sand's EF >> 1); a slight BOB of a floating ball kept as a thought - now if cheap, future if not |
| W2 | rubber rolling into the open arch from outside | bumps as into a wall - as the windmill's doorway does today |
| W3 | where the arch is | on the FRONT face: the ball exits "out the front" |
| W4 | hopping in water | nothing to gain - steel's Hop climbs nothing; no special rule |
| W5 | standing or flush | FLUSH with the floor round it (the sketch); this also removes the wrong-hide risk at the column's corners |
| W6 | sink speed | faster than real water - nothing may feel slow - but slow enough to read as sinking |
| W7 | ripples | optional PER USE: animated on some columns, static on others |
| W8 | the submerged ball | seen BEHIND the glass and water - never drawn whole on top of the glass art, which reads as a z-depth bug |

### How it is built (the investigation's design, checked against AV)

- **Statements.** `uses water`; `water rect X0 Y0 X1 Y1 top H bed B [ripple
  WX WY ...]` lays one `water` element a cell (grid: FLOOR at H, flat, OBS);
  `arch X Y side +x|-x|+y|-y` lays the exit's `arch` element on the cell
  outside the column (grid: floor at B, OBS).
- **CELL, per ball.** For steel every water cell in the window is FLOOR at
  B, so steel moves between columns on the bed and the column is a drop
  from the walkway; for rubber and glass FLOOR at H, one continuous top. The
  arch cell is floor at B for steel and a WALL to H or above for the others.
  The rewrite is IDEMPOTENT (kept cells are already rewritten: `bz_win9i`),
  and keeps each cell's flags byte. A material change (a pad) does not
  refill the window, so STEP compares `bz_mat` with a slot byte and sets
  `bz_fref` (about 12 bytes).
- **STEP.** Below H in a water cell, steel's fall is capped (a terminal
  velocity of about 0.5 - 0.75 px a step: a 2-unit sink in 0.4 - 0.6 s), so
  it sinks and lands under its stun threshold; sand's drag is the surface.
- **The landing.** While the centre is a water cell the family raises
  `bz_mrec + BZM_HTHR` (so glass never shatters on water) and restores it
  after - the jump pickup's way of overriding the ball's record (pickups.asm).
  Water's cells use the `sand` surface, and the family lowers the rubber
  rebound further (W1) without a new surface, so `BZ_PHYSV` does not move.
- **The draw, no resident change.** The tool renders the water cells' top
  and front faces with the depth key `s_C + 1` and top H, so the records it
  cuts lay the column's front over a ball inside it below H, and the ghost
  checker every mask carries (137.15.10.1) shows the ball as a 50% ghost
  behind the glass, on both cards. The front ARCH's opening keeps its true
  key, so steel rolling out of it is drawn whole. AV (137.29) runs only for
  a ball over VOID, so a ball in the column uses these records.
- **Reach and proofs.** A `bed` form at B (`reach_forms`), so occluders and
  bounds see both heights; `WaterFamily` in the model.
- **Art.** The tool: a water top (the crystal material's family of inks),
  glass faces with water inside, the arch from `_arch`; ripples as a lane
  posed by the POSE hook, at most 2 animated columns a window.
- **Costs.** The part about 300 - 380 bytes; resident 0; about 0.25k cycles
  a step near water; a course without water pays the existing hook-byte
  test. Most of the work is the tool's.
- **Risks.** Sand's drag may feel sluggish; a long ghosted sink on a slow
  frame; the record bounds on a wide pool; two families poking `bz_mrec` at
  once (the jump pickup) need a rule.

### Keeping the column steel's (open: the owner's to choose)

The water lets steel down; nothing yet stops rubber or glass dropping off
the walkway to the lower path. Ideas:

1. **Rails** along the walkway's edges (walls, or `bounce` bumper rails):
   built today; the simplest, but they box the walkway in. **The owner's
   choice (2026-11-17): a SEE-THROUGH GUARD RAIL** - thin, high enough that
   rubber cannot boost over it from flat ground, and never hiding the ball's
   path. BUILT (SPEC.md 137.35): a `guard` statement along the walkway's
   edge beside the column; a WALL in physics (a column at every height, so
   nothing crosses it - the jump pickup neither), drawn as posts and bars.
   The water course itself (W.2) is where the two meet: a water cell is
   laid as a flat FLOOR at the walkway's height, which is what a guard may
   touch - to be checked when WATER and the rail merge.
2. **A SPIKE PIT (P5) at the arch's mouth**: the exit corridor's first cells
   are spikes - steel rides over them, rubber pops and glass shatters if
   they drop there. Water and the material gate together.
3. **A WIND curtain (P3)** across the lower path: it pushes glass and rubber
   back off it and barely moves steel.
4. ~~**An overhang**~~ - REJECTED (the owner, 2026-11-17): a floor carried
   over the path hides it, and **the player must be able to see everywhere
   the ball goes**, with only a few hidden-path or short-tunnel exceptions
   (SUMMIT RUSH already shows the cost: a good part of it is hidden behind
   what stands in front). A design rule for every prop, not only this one.
   **The rule, as the owner clarified it (2026-11-17):** partial occlusion is
   allowed. What is forbidden is a mechanic made completely invisible, or
   blocks stacked on top of it: a mechanic (a pad, spikes, an arch's span)
   must be visible when the ball is not on it, and the BALL may be wholly
   hidden only for about ONE BALL LENGTH (16 px) of travel or less.
5. **Height**: the lower path far enough below that a fall onto it shatters
   glass (rubber still survives) - gates glass for free; partial.

The owner's reading: SPIKES gate only where they cover most of the floor
(rubber Hops one row) - worth one course that pairs them with water, two
steel-only mechanisms; WIND works if the lower path is THIN, as the sketch
draws it, blowing hard to one side; the HEIGHT gates glass.

## P3 WIND - as built (branch `bb-wind`, 2026-11-17)

SPEC.md 137.34 is the contract and the record; the diary's 2026-11-17 entry
"WIND: blowers, gusts and an updraft" is how it went. In short: one family
(ID 9, kind 40 `blower`, home `resident`, a 326-byte part, no resident code);
`prop blower X Y face +x|-x|+y|-y|up region X0 Y0 X1 Y1 [strength S] [gust ON
OFF [seed N]] [top H]`; the push added to the working velocity at STEP, so
the next step's clamps hold it to the caps; gusts a function of the step
counter (no state); the hint a pennant on the blower's pole flying downwind
over a black pinwheel fan; the updraft lifts an AIRBORNE ball below its top
while gvz is under 128 - glass rises, rubber and steel do not. The knob build
`BZWIND=1` puts the WIND test course on the pathway's pad 0.

- [x] **P3.1** SPEC.md 137.34: the contract before the code.
- [x] **P3.2** The tool: the statement and its refusals, the record, the
      reader, `WindFamily`, the updraft's reach, the fan and the pennant,
      `--selfcheck` section `wind` (red arm `nowindreach`).
- [x] **P3.3** The guest part `fam/wind.asm`, equal to the model (the
      unicorn half of `bonanza_phys --check`: eight scenes, red arms
      `wdstep`, `wdglass`, `wdmark`, `wdlift`).
- [x] **P3.4** The knob course WIND: the gust across the crumbling bridge,
      the steady wind across the thin path (rubber and glass blown off,
      steel through leaning into it), the updraft to a glass-only ledge.
- [x] **P3.5** LOOKED AT on MartyPC, CGA and Hercules (both rounds).
- [ ] **P3.5b** The per-step cost MEASURED (the final pass's `bonanzaphys` /
      `bonanzaperf` rows on a `BZWIND=1` build).
- [x] **P3.6** The owner's answers (strength per blower, power-of-two gusts:
      kept) and round 2, SPEC.md 137.34.11:
  - [x] **P3.7** PIT WIND: `lift` launches a grounded ball the updraft
        out-lifts (glass; rubber floats, steel not); a pit needs nothing new.
  - [x] **P3.8** SQUIGGLES in the air over the region: static for a steady
        blower, a WISP lane for a gusting one (there only while it blows),
        the timed lanes of a window never turning on one step.
  - [x] **P3.9** GROUND FANS spin while the ball is in their wind and 2.9 s
        after (a FAST lane, counted against the window's 6 and its pose
        changes); the pennant only with `flag`.
- [x] **P3.10** A shipped course that uses it: PLAYGROUND's WIND YARD
      (SPEC.md 137.34.12), with the GUARD RAIL's first shipped use - and the
      limit it met: `BZ_FAMMAX` is 4 by `bzfam.inc`'s shift, PLAYGROUND's
      list is full, so no other family of this round fits there without an
      engine change.

## P5 SPIKES and P8 the MEMBRANE - as built (branch `bb-spike`, 2026-11-17)

SPEC.md 137.38 is the contract and the record; the diary's 2026-11-17 entry
"SPIKES and the crystal membrane" is how it went. One family (ID 11, kinds
56 - 58, home `resident`, a 455-byte part, no resident code): `prop spikes
<wx> <wy> [<x1> <y1>]`, `prop popspikes <wx> <wy> period P on N [seed S]`,
`prop membrane <wx> <wy> [<x1> <y1>]`. CELL rewrites each cell per ball:
steel rides the tips (a climb above the base), rubber and glass drop a half
unit onto them and the hard landing's SHATTER kills them while the window's
centre is a spike (rubber's new POP frames: three entries after its stretch
in its ball part, +3,840 bytes of the resident bundle's RAM); the membrane is
a floor for glass and a near void for the others. The knob build `BZSPIKE=1`
puts the SPIKE test course on the pathway's pad 0.

- [x] **S.1** SPEC.md 137.38: the contract.
- [x] **S.2** The tool: the statements, refusals (a spiked cell beside a
      lower floor or water, popspike timers, surfaces), records, `SpikeFamily`,
      the `tip` reach form, the art (blades, slits, the film), the timed lanes'
      one-change-a-step check shared with WIND's gusts; `--selfcheck` section
      `spike` (ten refusals, records, reach, art, model scenes, two red arms).
- [x] **S.3** The part `fam/spike.asm`, equal to the model (the unicorn half of
      `bonanza_phys --check`: eleven scenes, six red arms, all MEASURED red).
- [x] **S.4** Rubber's POP frames (`bonanza_assets.pop_frame`), held by `make
      bonanza-check`.
- [x] **S.5** The knob course SPIKE: the corridor, the popspike lane, the
      membrane bridge, water over spikes (`uses spike water`); no shipped
      course, demo or identity moved (MEASURED, `cmp`).
- [x] **S.6** LOOKED AT once on MartyPC, CGA and Hercules (steel on the tips,
      rubber's pop, glass's shatter, a popspike's pop, glass on the membrane,
      steel in the water column).
- [ ] **S.7** The per-step cost MEASURED (the final pass's `bonanzaphys` /
      `bonanzaperf` rows on a `BZSPIKE=1` build).
- [ ] **S.8** The owner's answers (SPEC.md 137.38.9) and a shipped course that
      uses spikes.
- [x] **S.9** The death and squash frames cheaper (the owner's A and B, SPEC.md
      137.38.10): B one parity copy (the bundle -8,960 RAM, the image -30), A
      one shift shifted at the draw (a further -6,240 RAM for +113 image bytes,
      2.3 - 3.9 ms a dying frame, PRICED); both LOOKED AT on both cards. The
      owner's decision: **B ships**; A is parked as
      docs/plans/bounce-bonanza/patches/death-frames-a-one-shift.patch (for a
      256KB build at finalization, with short courses).
## P4 BOOST PADS - as built (branch `bb-boost`, 2026-11-17)

SPEC.md 137.40 is the contract and the record; the diary's 2026-11-17 entry
"BOOST PADS: chevrons that push" is how it went. In short: one family (ID 10,
kind 48 `boost`, home `resident`, a 166-byte part, no resident code but
`BZ_FTAB`'s byte); `prop boost X Y face +x|-x|+y|-y [strength S]`, 24 by
default; the CONTACT hook adds S to the working velocity of a GROUNDED ball on
the pad - WEIGHTED by the ball since the owner's round 2 (steel x3/4, glass
x1.25; `flat` per pad for S on every ball) - and the next step's clamps
hold it to the caps, as WIND's push relies on; an airborne ball is not pushed.
The art: a magenta plate, black rim, two white chevrons; the FLASH lane (white
plate, black chevrons) lit while the ball rolls on it and 12 steps after, one
pad lit at a time. Not rubber's BOOST (SPEC.md 137.16.4, the Hop's rebound):
the names are kept apart (`BP_*`, `bp_*`). The knob build `BZBOOST=1` puts the
BOOS test course on the pathway's pad 0.

- [x] **P4.1** SPEC.md 137.40 (written as built, in one pass with the code).
- [x] **P4.2** The tool: the statement and its refusals, the record, the
      reader, `BoostFamily`, the chevrons and the flash lane, `--selfcheck`
      section `boost` (12 refusals, the records, the scenes on the model
      against the course less its pads, red arms `nopush`, `sign`, `air`,
      `twolit`) - MEASURED green, every arm red.
- [x] **P4.3** The guest part `fam/boost.asm` (166 bytes), equal to the model
      (the unicorn half of `bonanza_phys --check`, `bp_host`: twelve scenes,
      red arms `bpstep`, `bpsign`, `bplit`, `bpout`, `bpair`, each red).
- [x] **P4.4** The knob course BOOS: a CHAIN of pads round a corner onto the
      goal with no key held; a RAMP from a one-tile pocket rubber and steel
      cannot climb without its pad; a GAP jump from a pocket no ball makes
      without its pads; a pad for each ball.
- [x] **P4.5** No shipped course, demo or identity moved (MEASURED, `cmp`);
      the bundle +176 bytes of RAM, the package +180, the image +1.
- [x] **P4.6** LOOKED AT once on MartyPC, CGA and Hercules (`build/boost`): the chain's pads
      lit in turn under a rolling ball, the ramp pocket's pad lit, the gap's pocket.
- [ ] **P4.7** The per-step cost MEASURED (the final pass's `bonanzaphys` /
      `bonanzaperf` rows on a `BZBOOST=1` build; PREDICTED about 0.2k a step,
      0.35k more on a pad).
- [x] **P4.8** The owner PLAYED BOOS (2026-11-17): *"Look and function great in the test map."* One
      change: WEIGHTED BY BALL, an option ON BY DEFAULT - the owner's weights, steel x3/4, rubber x1,
      glass x1.25 (`BP_SSH`, `BP_GSH` in the FAMV, to retune with use), `flat` per pad turning it off
      (record +18 bit 2). BUILT: the part 166 -> 192 bytes; BOOS's chain turn at strength 32 and its gap
      pads `flat`; selfcheck item 6's weighting with red arms `noweight`, `noflat`; `bp_host`'s red
      arms `bpweight`, `bpflat` (SPEC.md 137.40.1 D3, 137.40.4).
- [ ] **P4.9** A shipped course that uses pads.

## Stories

- [x] **W.1** SPEC.md: water's contract (statements, the family, the draw,
      the refusals) before the code - SPEC.md 137.36 (family ID 7).
- [x] **W.2** The model and the tool: `WaterFamily`, the statements, the
      `bed` form, the refusals, the depth key and the art; a test course
      (`BZWATER=1`, `courses/water.bbc`).
- [x] **W.3** The guest family part (`fam/water.asm`, 341 bytes, resident),
      held equal to the model.
- [x] **W.4** Rows: `bonanzaphys`'s water scene (steel sinks, no stun, out
      the arch; rubber skims lower; glass lands from height whole; a pad
      refills) with red arms; the selfcheck's cases; LOOKED AT on both
      cards (one MartyPC boot of the knob tree; the soak rows not run).
- [x] **W.5** The owner's second round (SPEC.md 137.36.9): ripples ANIMATED
      while a ball is in the column (`ripple`) or always (`always`, a FAST
      lane), marked on change only; the FLOAT LINE (rubber and glass ride a
      half unit under the top, their lower half behind the water); steel's
      WOBBLE while sinking (`WA_BOB`, 15 bytes, one constant - turned OFF after the owner saw it: the straight fall reads better); a 6-unit
      DEEP column on the test course; unicorn scenes and red arms; LOOKED AT
      on both cards.  The float line's own bob NOT built (a moving floor is
      the lift's carry; a gvz kick lands every time).
- [x] **W.6** The third round (SPEC.md 137.36.10): the floating ball's
      SURFACE BOB - B ships: the float floor alternating top / float line
      every 16 steps, a resting ball carried down with it (no landing:
      MEASURED), +83 part bytes.  E (the hover) was built for the owner's
      A/B and SET ASIDE ("it can't exit the water": the walkway's edge bumps
      it back) - its arm and the `BZWATERBOB` knob deleted.  C priced and NOT
      built (a resident floor offset and carry).  Unicorn scenes equal, red
      arms `wabsnap`, `wabflip`.
- [x] **P13 / the guard rail** (SPEC.md 137.35, branch `bb-rail`): the
      contract; the tool's `guard` statement, its refusals, art, occluders and
      `FL_FLOAT`; `--selfcheck` item 16 with four red arms (MEASURED red); the
      `BZRAIL=1` test course RAIL; the knob-less build byte-identical
      (MEASURED). Previewed on both cards (`--png`); PLAYED by the owner on
      the `BZRAIL=1` disks, 2026-11-17: "Look great and meet their function"
      (the 2-unit default kept).


## P10 THE ARCHWAY - built (branch `bb-arch`, SPEC.md 137.39)

Family ID 12, kind 64, home `resident`, a 233-byte part; no resident engine
byte, `BZ_PHYSV` and every shipped course, demo and identity unchanged
(MEASURED). `archway <shape> along x|y [under <units>]` lays the cells under
an arch (1 - 2 deep, 1 - 2 wide) and its two block LEGS; the lintel is drawn
keyed a row nearer, so it lays over a ball under it. Physics: CELL writes
each archway cell in the window as a WALL while the ball's z is above its
clearance (the engine's wall test stops it at the face, from either end, at
every height), STEP caps the ball under the underside and refills the window
when z crosses a clearance. The default 2-unit arch is the ball's height:
under it the ball cannot leave the floor, so it ROLLS - and takes a pad under
it. The owner's visibility rule as clarified (partial occlusion fine; wholly
hidden at most a ball length; the pad seen) is a REFUSAL the tool measures.

- [x] **A.1** SPEC.md 137.39: the contract before the code.
- [x] **A.2** The tool: the statement, the legs, the refusals (15 string
      cases), the records (the LAST, no OBS: a pad under an arch), the reader,
      `ArchFamily`, the lintel's art, the visibility rule; `--selfcheck`
      section `arch` with red arms `arnowall`, `arnocap`, `arkey`, `arvis`
      (MEASURED red).
- [x] **A.3** The part `fam/archway.asm` (233 bytes), equal to the model at
      every step of five unicorn scenes; red arms `arwall`, `arcap`,
      `arref`, `arcell` (MEASURED red).
- [x] **A.4** The knob course ARCH (`BZARCH=1`, pad 0): a 2-unit arch over
      a steel pad (rubber cannot boost past it: none of the sweep's runs got
      past without the pad), a bare 2-unit arch to Hop and boost into, a
      3-unit two-wide arch a Hop passes under.
- [x] **A.5** LOOKED AT on MartyPC, CGA and Hercules (the knob tree, rolled through A and C: the ball ghosted where the lintel and the front leg cover it, whole in the opening; see the diary).
- [ ] **A.6** The per-step cost MEASURED (the final pass's `bonanzaperf` /
      `bonanzaphys` on a `BZARCH=1` tree; about 0.35k a step PREDICTED).
- [ ] **A.7** The owner's answers (SPEC.md 137.39.9): the look (block legs
      hide half of a pad under a 1-deep arch - the route audit reports its
      mark BELOW, 50% against 75%; posts at the corners would show it), the
      default height, 2-deep low arches.
- [ ] **A.8** A shipped course that uses it.

## P9 THE SEE-SAW - built (branch `bb-tilt`, SPEC.md 137.42)

Family ID 14 (13 is the gates' on another branch: a gap here), kinds 80 (the
PLATE) and 81 (a LANE of one, the tool's), home `resident`, a 648-byte part;
no resident engine code (the image +2: `BZ_FTAB`'s rows), `BZ_PHYSV` and every
shipped course, demo and identity unchanged (MEASURED, `cmp`). `seesaw <x0>
<y0> <x1> <y1> along x|y pivot <units> [rest -|+]` lays a plate of 2, 4 or 6
cells along its axis and 1 - 2 across, in three poses (rest, FLAT, the other
end down), each a set of slope cells CELL writes into the window. The ball's
WEIGHT tips it: grounded on a half for 2 steps (steel), 8 (rubber) or 28
(glass) it moves toward that half down, then 4 more from FLAT; the step that
moves it CARRIES the ball (z set on the new floor: never a fall). The lanes
are the picture's change between the poses, cut by the tool; a white fulcrum
under the pivot. The diary's 2026-11-17 entry "THE SEE-SAW" is how it went.

- [x] **T.1** SPEC.md 137.42: the contract, written with the code (PLANNED
      decisions in 137.42.1, then BUILT and MEASURED).
- [x] **T.2** The tool: the statement and its nine refusals, the records and
      the reader, `TiltFamily`, the `tilt` reach form, the lanes cut from the
      poses' pictures, the fulcrum, the window bound's count of a plate's
      lanes; `--selfcheck` section `tilt` (red arms `nocarry`, `wrong`) -
      MEASURED green, every arm red.
- [x] **T.3** The guest part `fam/seesaw.asm` (648 bytes), equal to the model
      at every step of seven unicorn scenes (`tilt_host`); red arms `tlcell`,
      `tlcarry`, `tlmark`, `tlfref`, `tlweight`, `tlrst`, each red.
- [x] **T.4** The knob course TILT (`BZTILT=1`, pad 0): the LEDGE only glass
      reaches (its light weight tips the plate too late), the GATE the ball's
      weight lays down to the goal, the ROCKER.
- [x] **T.5** No shipped course, demo or identity moved; the bundle +656
      bytes of RAM, the package +406, the image +2.
- [ ] **T.6** The per-step cost MEASURED (the final pass's `bonanzaphys` /
      `bonanzaperf` on a `BZTILT=1` tree; PREDICTED 0.1 - 0.9k a step, about
      2k a refill on TILT).
- [ ] **T.7** The owner's answers (SPEC.md 137.42.10): the weights, the look,
      steel and slopes, the lanes, the occluders.
- [x] **T.8** The TIMED see-saw (branch `bb-propfix`, SPEC.md 137.42.11, the owner 2026-11-18): `period
  P [flat F] [seed S]` ignores the weight and swings on a popspike's timer through FLAT, carrying the
  ball; TILT's LIFT (a timed plate lifts every ball to a ledge) and SWING; eight refusals, five model
  scenes, four unicorn scenes and four red arms. The part 648 -> 824 bytes, the bundle +176, the image
  and bss +0; the weight plate's scenes unchanged.

## P11 THE QUARTER-TURN TURNTABLE - built (branch `bb-turn`, SPEC.md 137.43)

Family ID 15, kind 88, home `resident`, a 315-byte part; no resident engine
byte (the image's +3 are `BZ_FTAB`'s rows for 13 - 15), `BZ_PHYSV` and every
shipped course, demo and identity unchanged (MEASURED, `cmp`). `prop turntable
<wx> <wy> size 2|3 fill <cells> [quarter 32|64] [seed S] [warn W] [turn
cw|ccw]`: a 2 x 2 or 3 x 3 table (a 3 x 3 turns round a fixed PIVOT), HALF
FILLED, a quarter turn every 64 steps (1.07 s) by default; each switching cell
a FLOOR or a NEAR VOID by its rotation, so a cell that turns to a gap drops
the ball, rolling or at rest. The decisions (SPEC.md 137.43.1): the turn
SWEEPS round the ring one cell a step (67 - 133 ms: it reads as turning, and
a table costs the window's `WIN_CHG` one change a step - a 3 x 3 turning at
once could not share a screen with a clock); a floor about to open shows its
SEAM for 16 steps (fair play); a hole that closes over a fallen ball does not
lift it; the art (redone 2026-11-18 after the owner's first look: "a circle
on top of squares/columns" won't work) is a crystal PLATTER drawn in place of
the cells' tiles - a pinwheel of facets round a gem hub, a bevelled rim, a
half-unit front edge and a spindle - each cell's lane an open PORT or its
dotted seam.

- [x] **T.1** SPEC.md 137.43: the contract (written PLANNED with the code,
      then as built and measured).
- [x] **T.2** The tool: the statement, its refusals (16 string cases and the
      window bound), the records, the reader, `TurnFamily`, the sweep, the
      ring/hub art and the hole/seam lanes, the exact turntable share of a
      window's pose changes; `--selfcheck` section `turn` with model red arms
      `novoid`, `fallen` (MEASURED red).
- [x] **T.3** The part `fam/turntable.asm` (315 bytes), in the bundle, equal
      to the model at every step of eight unicorn scenes; red arms `ttcell`,
      `ttfallen`, `ttkept`, `ttmark`, `ttwarn`, `ttfast`, `ttfref` (all
      MEASURED red).
- [x] **T.4** The knob course TURN (`BZTURN=1`, pad 0): the CHAIN (two 2 x 2
      dominoes out of phase with an island between) to exit 1, the DISC (a 3 x 3
      half disc crossed by waiting on its pivot); every ball crosses on the turn
      and falls off it (the model, the unicorn scenes).
- [x] **T.5** LOOKED AT on MartyPC, CGA and Hercules (the knob tree) - see the
      diary's entry.
- [x] **T.5b** The PLATTER (the owner's first impression, 2026-11-18: the ring over
      checker tiles and columns would not work): the cells drawn as one crystal
      platter, ports for gaps; previews and one MartyPC look per card, again.
- [ ] **T.6** The per-step cost MEASURED (the final pass's `bonanzaphys` /
      `bonanzaperf` on a `BZTURN=1` tree; about 2.3k clocks a step on TURN
      PREDICTED).
- [ ] **T.7** The owner's answers (SPEC.md 137.43.10): the hole's size (a lens,
      not the whole cell, without group lanes), the period and the warning.
- [ ] **T.8** A shipped course that uses it.

## P2 MAGNETS - built (branch `bb-magnet`, SPEC.md 137.33)

Family ID 8, kind 32, home `resident` (the owner's rule; it was `fetch` on
its branch, 137.33.9). A magnet on a post pulls STEEL along a FIELD of N cells out from
it, `S >> (k - 1)` at the k-th cell toward the post; a HANGING magnet (`face
down`) lifts an airborne steel ball, `gvz += S; gvz -= gvz >> 3`, so with S
= 27 against G = 24 steel rolled off a level edge HOVERS at its height. The
investigation: an airborne ball over a NEAR void dies only below the kill
height (the near floors less 3 units), so nothing blocked hovering and
there is no resident change.

- [x] **M.1** SPEC.md 137.33, the contract, before the code.
- [x] **M.2** The tool: the statement (`prop magnet ... face ... [range]
      [strength]`), the record (+18 - +22), `MagnetFamily` (the force-field
      core `mg_scan` / `mg_force` / `mg_apply`), the refusals, the art (a
      magenta horseshoe, white tips, black outline: readable on the
      Hercules) and the WIGGLE lane (3 poses).
- [x] **M.3** The part `fam/magnet.asm` (376 bytes), STEP and POSE, equal to
      the model at every step of seven scenes (MEASURED under unicorn).
- [x] **M.4** The `BZMAGNET=1` knob's test course MAGS (the pathway's pad
      0): the PULL, the RAIL, the HOVER; no shipped course, demo or identity
      moved (MEASURED, `cmp`).
- [x] **M.5** The proofs: `--selfcheck` section `magnet` (12 refusals, the
      records, the scenes, three red arms on the model) and `bonanzaphys`'s
      `mg_host` (seven scenes, five red arms on the part), all MEASURED.
- [x] **M.6a** LOOKED AT once on MartyPC, CGA and Hercules: steel hovers
      and rides the rail on the guest, the wiggle drawn (SPEC.md 137.33.10;
      the hovering ball is hard to see against the posts' pillars on the
      Hercules - open question 5).
- [ ] **M.6b** The wiggle's frames and a step's clocks MEASURED on MartyPC
      (`bonanzaperf`-style) - the final pass's.
- [x] **M.7** The owner's answers (SPEC.md 137.33.13): the hover BOBBLES
      (+20 bytes, about 1.7 px, no drift); one head an element (a hanging
      magnet's range other than 1 refused); at most one wiggle pose change a
      step (N hanging magnets: N SLOW lanes, no FAST one); the law judged by
      the owner on the test course.
- [ ] **M.8** A shipped course that uses magnets (home `resident` since the merge).

## P12 HUMPS - built (branch `bb-hump`, SPEC.md 137.44, tool only)

No family, no resident byte, no `BZ_PHYSV` change (the round's reserved ID 16 stays free): a hump is FIELD cells
whose tables rise ABOVE the cell's base, and the guest's FIELD code runs them as they stand (proved under unicorn).
`hump <x> <y> <z> [along x|y <n> [open]] [height <px>]`: a raised-cosine DOME on the 2 x 2 cells round a cell
corner, or a RIDGE along an axis (domed ends, or `open` against a wall or the void - a speed bump nothing rolls
round); STANDARD heights LOW 6 px and HIGH 10 px (2 - 11 allowed, 11 the slope bound); the rim level with the
floor round it (refused otherwise). Physics: none of its own - a hump is a RUN-UP gate. Steel stalls at a LOW
hump's foot and needs three cells of run at a HIGH one; rubber and glass need about half a cell at a HIGH one;
nothing takes off over a crest; rubber does not bounce off a face (it is a hill, not a wall). The ink: the shapes'
two magentas in BANDS of height (rings on a dome, stripes on a ridge), readable on the Hercules. Occluders: raised
facets topped in 2 px steps, so a HIGH hump lays up to 42 lit px over a grounded ball behind it (a LOW one none:
the margin). The visibility rule is MEASURED per hump and is met BY CONSTRUCTION (11 px under a 16 px ball, a level
rim). The knob build `BZHUMP=1` puts the HUMP test course on the pathway's pad 0.

- [x] **H.1** SPEC.md 137.44: the contract and the record.
- [x] **H.2** The tool: the statement and its 15 refusals, `hump_cells`, the open ends and the level rim
      (`hump_ends`), `HumpInk`, the raised facets' tops (`HTOPQ`), the visibility rule (`hump_vis`, with its
      attribution); `--selfcheck` section `hump` with red arms `slope`, `hmtop`, `hmnoattr` - MEASURED red.
- [x] **H.3** The guest: no code. tests/bonanza_dfield.py runs HUMP (CELLS, seven scripted runs, the fuzz):
      every step equal; `symswap` red on six of the seven.
- [x] **H.4** The knob course HUMP: three LOW domes and a LOW ridge, the HIGH open ridge across a bridge (steel
      needs the bridge's run), a HIGH dome in front of a glass pad; no shipped course, demo or identity moved
      (MEASURED, `cmp`, 20 of 20 files).
- [x] **H.5** LOOKED AT once on MartyPC, CGA and Hercules (the knob tree): the humps as the previews draw them, a ball rolled past them on both cards.
- [ ] **H.6** The per-step cost MEASURED (the final pass's `bonanzaphys` / `bonanzaperf` rows on a `BZHUMP=1`
      build; PREDICTED as a chute's FIELD step, +0.4 - 0.9k clk).
- [ ] **H.7** The owner's answers (SPEC.md 137.44.9): the heights, the bands, a kicker, a bumper hump.
- [ ] **H.8** A shipped course that uses humps.

## P6 + P7 SWITCHES, KEYS, GATES and the DRAWBRIDGE - built (branch `bb-gate`, SPEC.md 137.41)

Family ID 13, kinds 72 - 75 (`plate`, `key`, `gate`, `bridge`), home `resident`, a 515-byte part; no resident
engine byte but `BZ_FTAB`'s, `BZ_PHYSV` and every shipped course, demo and identity unchanged (MEASURED, `cmp`).
A plate (rolled over, grounded) or a key (touched) OPENS its CHANNEL - one of four, each its GLYPH (ring, plus,
box, cross) black on a white plaque on every element of it, so the pairing reads on CGA and Hercules - for the
ATTEMPT (latching: the slot's bit, kept by a respawn, zeroed by a play's start). A gate is a WALL while shut and
never closes in an attempt; a drawbridge cell is FLOOR while down and a near void while up, switched (lowered by
its channel) or timed (a popspike's timer, a rect's cells a step apart); a ball under the deck when it comes down
is not lifted. Lanes redrawn on change only (`bz_fmark`); the channel's opening counts the pickup's sound.

- [x] **G.1** SPEC.md 137.41: the decisions (D1 - D8) and the statements, then the record.
- [x] **G.2** The tool: the statements and refusals (20 string cases), the records, the reader, `GateFamily`,
      the plaque art (plate, key, grille, hole), the timed bridges in the turns check; `--selfcheck` section
      `gate` (refusals, records, the glyphs' pairing, nine scenes for every ball on the model each with its
      control, red arms `noopen`, `nowall`, `lift`) - MEASURED green, every arm red.
- [x] **G.3** The part `fam/gate.asm` (515 bytes), equal to the model in 27 unicorn scenes (`gt_host`); red
      arms `gtwall`, `gtmark`, `gtstep`, `gtlift`, `gtup`, each MEASURED red.
- [x] **G.4** The knob course GATE (`BZGATE=1`, pad 0): plate -> gate, key -> gate, a timed drawbridge, a
      switched drawbridge, all three balls.
- [x] **G.5** No shipped course, demo or identity moved (MEASURED, `cmp`); the bundle +528 bytes of RAM, the
      package +298, the image +1, bss +0.
- [x] **G.6** LOOKED AT once on MartyPC, CGA and Hercules (the `BZGATE=1` tree; the diary says what was seen).
- [ ] **G.7** The per-step cost MEASURED (the final pass's `bonanzaphys` / `bonanzaperf` rows on a
      `BZGATE=1` tree; PREDICTED in SPEC.md 137.41.9).
- [ ] **G.8** The owner's answers (SPEC.md 137.41.10): latching, the bridge's hole art, a warning pose, four
      channels.
- [ ] **G.9** A shipped course that uses them.
- [x] **G.9** The art's STYLES (branch `bb-propfix`, SPEC.md 137.41.11, the owner 2026-11-18):
  `gatestyle` for a course, `style` on a gate or bridge - grille (the default), crystal, picket,
  portcullis - the bars and the deck, tool only (0 resident bytes); every course naming none
  byte for byte as before; GATE shows all four.

## The owner's verdicts on the follow-ups (2026-11-18), and what is OPEN

- **Timed see-saw (137.42.11): approved and merged.** A timed plate and a
  weight plate never sharing a window is accepted. The owner asked why the
  WHEEL does not handle it naturally - spreading a heavy step's lane changes
  over the next frames so no one frame is too heavy. It already does at draw
  time (a channel's lanes past the wheel's six candidates wait a frame and are
  never lost: 137.41's report); the refusal is the TOOL's conservative bound
  (`WIN_CHG`, counted at the worst step). Relaxing that bound to trust the
  wheel - and saying what it costs in a late lane - is an OPEN engine question,
  not done.
- **Gate styles (137.41.11): merged, NOT what the owner wants.** The four
  styles read as "a slight recolor of the same gate". The real ask is
  DESIGNER-SUPPLIED gate art per course: the course feeds the gate (and the
  drawbridge) whatever art fits it - a crumbling wall between two blocks, a
  portcullis that rises into an arch, a doorway that opens - as an animation
  of a fixed, generic frame count, with wider gates where the art needs it.
  OPEN; the four built styles stay as presets until it lands. Not started:
  the owner held new agents at the weekly capacity limit (2026-11-18).

## A path past the picture part's 65,024 bytes (a brief look, 2026-11-18; NOT pursued)

PLAYGROUND's picture part is 59,022 bytes: map 25,856, blocks 966 x 16 =
15,456, occluder records 2,665 x 4 = 10,660, masks 250 x 16 = 4,000, MTAB 500,
OCCIDX 204. The row writer's inner loop (`BZ_RWORD`, bzvideo.inc) reads the
map word and copies the block's words through DS, so splitting the MAP from
the BLOCKS would put a segment override or a row copy on every word. The path
that leaves that loop alone splits the OCCLUDERS out instead - records,
masks, MTAB and OCCIDX (about 15.4 KB) into a third part of their own: the
picture part keeps map and blocks (room for about 2,048 blocks), masks go to
512 with no ninth bit squeezed into the 4-byte record, and the cost falls on
the occluder pass (laid only near the ball), which needs reworking and a
MartyPC measurement. Predicted moderate engine work, the shape of the world
split (137.30). The owner: on disk, 13 - 14 PLAYGROUND-sized courses fit
without it, so it buys only a mix of longer and shorter courses - not pursued
for now.

  The four built styles stay as presets.
  - [x] **BUILT on `bb-gateart` (2026-11-18), SPEC.md 137.41.12**: a gate's
    art is a `.bba` of 4 frames (shut -> open) under
    `apps/bonanza/courses/gates/`, its own footprint (`# foot`, `# cells`
    1 - 3), named per gate (`art <name>`) or per course (`gateart`); the
    frames are the channel's (one 2-bit frame a channel in the slot, a
    step every 8), the cell opens at frame 3; the tool cuts the frames'
    change into lanes. GATE carries three: a crumbling wall between two
    blocks, a portcullis rising into its arch, a door swinging open.
    Shipped courses byte for byte; resident 0; the part +115 bytes.
  - [ ] a drawbridge art on a course (built, unproved), a timed bridge's
    art, per-pose occluders (SPEC.md 137.41.12.6).
