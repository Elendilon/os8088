# BOUNCE BONANZA — the next props and tiles (plan)

The owner, 2026-11-17: *"magnets, blowers (wind), and possibly water, and
then a handful (4-5) traps/other small interactive when touched props, and
one or two more windmill sized larger props."* This plan is the round's
list: what was chosen, what was tabled, and what each costs, from a sweep of
every idea already written down (the main plan's sections 8 and 9 and the
owner's decision 8: [BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md)) and a
costing against the tree at the AV merge (`4675757d2`). Every cost below is
PREDICTED until a story says MEASURED.

**The yardstick.** A mechanic that fits the family hooks (SPEC.md 128.25.6:
CELL rewrites the 9-cell window per state and per ball, STEP pushes the ball
every step, timers and lanes for poses) needs no resident change and is
"doable now". Today's family parts are 203 - 680 bytes (`build/bzf-*.bin`),
and since GLASS and PICKUPS joined the resident bundle every resident family
is RAM every play pays; with five or six more, some may go home `fetch`
(128.25.6.9) - a decision for when they are built. A lane is at most 32 x 24
px, and at most 6 FAST lanes meet a window.

## The list

### Chosen - doable now (families, no resident change)

| | what | how | notes |
|---|---|---|---|
| P1 | **WATER** (the owner's design, below) | one family; the tool's depth key draws the ball behind the glass | its own section; the first to build |
| P2 | **MAGNETS**, pulling on or off the course; a 2 - 3 frame WIGGLE lane while active | STEP pulls steel toward each magnet in range (plan: 0.3 - 0.5k a step in range) | **VERTICAL magnets**: an upward pull about gravity, so steel HOVERS across a gap under a row of them on an overhang (check: airborne over VOID is not a fall until it drops) |
| P3 | **WIND / BLOWERS**: magnets reversed, weighted glass x2, rubber x1, steel x1/4 | STEP pushes in the blower's region (plan: 0.1 - 0.2k a step) | a GUST lane on the blower or a FLAG as the hint; across the crumbling bridge (cracked tiles) the owner's favourite; an UPDRAFT that lifts only glass to a ledge is a glass-only gate for free |
| P4 | **BOOST PADS** (chevrons): before full courses are built, not post-release | a family pad pushing in its record's direction | a family rather than a surface: a surface moves `BZ_PHYSV` and re-authors every demo; a family moves only the FAMV of courses using it |
| P5 | **SPIKE PIT**: glass shatters, rubber POPS, steel is pushed up to the spikes' height and rolls on - a MATERIAL GATE | CELL per ball (the water trick): floor at spike height for steel, a kill for the others; **POP-UP SPIKES** the same family on a timer, two poses | rubber's POP is new sprite frames (the ball generator, 128.25.5) |
| P6 | **SWITCH PLATES, KEYS, GATES** - an option, not the primary mechanic | a plate or key sets a bit; a gate cell WALL <-> FLOOR with a lane redraw (the cracked tile's state-driven cell) | keys can reuse the pickups' COLLECTED bit |
| P7 | **DRAWBRIDGE** | cells VOID <-> FLOOR on a timer or a switch, a lane a bridge cell | pairs with P6 |
| P8 | **GLASS-ONLY: a crystal MEMBRANE** | a tile that is FLOOR for glass only (the CELL-per-ball trick) | the owner asked for a glass-only idea; the updraft (P3) is the other |

### Chosen - moderate

| | what | why moderate |
|---|---|---|
| P9 | **SEE-SAW / TILT PLATE** | the tilt is cell slopes (2 - 3 poses through CELL); the floor moving under a resting ball is the lift's carry adapted, not new physics |
| P10 | **ARCH to roll under** (also: a ball forced under it cannot boost over a pad, so rubber must take a pad) | the reserved UNDERSIDE flag (SPEC.md 128.12.3.1): a CEILING in physics (an airborne ball at its height hits the arch's top) and the arch's top drawn over a ball under it - both resident, bounded |
| P11 | **TURNTABLE, quarter-turn**: half filled, a quarter turn every second or so, the cells switching; it does not carry the ball (a cell that turns to a gap drops you) | several SLOW lanes |

### Possible

| | what | why |
|---|---|---|
| P12 | **HUMPS** - fits the theme; cheap to make, expensive to USE, as shapes are | the FIELD cell's height tables (128.28) already describe any height pattern; a hump rises ABOVE the lip, so it hides what is behind it - occluders the pit never needed. A **standard hump** (one shared table set, 128.28.4's STANDARD PROFILES rule) keeps its data down |

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
  checker every mask carries (128.15.10.1) shows the ball as a 50% ghost
  behind the glass, on both cards. The front ARCH's opening keeps its true
  key, so steel rolling out of it is drawn whole. AV (128.29) runs only for
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
   built today; the simplest, but they box the walkway in.
2. **A SPIKE PIT (P5) at the arch's mouth**: the exit corridor's first cells
   are spikes - steel rides over them, rubber pops and glass shatters if
   they drop there. Water and the material gate together.
3. **A WIND curtain (P3)** across the lower path: it pushes glass and rubber
   back off it and barely moves steel.
4. **An overhang**: the walkway overhangs the lower path, which runs back
   UNDER it into the arch, so nothing above can drop onto it - needs the
   ARCH's underside work (P10).
5. **Height**: the lower path far enough below that a fall onto it shatters
   glass (rubber still survives) - partial.

## Stories

- [x] **W.1** SPEC.md: water's contract (statements, the family, the draw,
      the refusals) before the code - SPEC.md 128.36 (family ID 7).
- [x] **W.2** The model and the tool: `WaterFamily`, the statements, the
      `bed` form, the refusals, the depth key and the art; a test course
      (`BZWATER=1`, `courses/water.bbc`).
- [x] **W.3** The guest family part (`fam/water.asm`, 341 bytes, resident),
      held equal to the model.
- [x] **W.4** Rows: `bonanzaphys`'s water scene (steel sinks, no stun, out
      the arch; rubber skims lower; glass lands from height whole; a pad
      refills) with red arms; the selfcheck's cases; LOOKED AT on both
      cards (one MartyPC boot of the knob tree; the soak rows not run).
- [x] **W.5** The owner's second round (SPEC.md 128.36.9): ripples ANIMATED
      while a ball is in the column (`ripple`) or always (`always`, a FAST
      lane), marked on change only; the FLOAT LINE (rubber and glass ride a
      half unit under the top, their lower half behind the water); steel's
      WOBBLE while sinking (`WA_BOB`, 15 bytes, one constant); a 6-unit
      DEEP column on the test course; unicorn scenes and red arms; LOOKED AT
      on both cards.  The float line's own bob NOT built (a moving floor is
      the lift's carry; a gvz kick lands every time).
- [ ] The see-through GUARD RAIL keeping the column steel's (the owner's
      choice; another agent's).
- [ ] P2 - P12 as the owner orders them.
