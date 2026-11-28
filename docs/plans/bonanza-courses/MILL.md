# COURSE 4, "Windmill Lane" (MILL): design sheet

*Status: **ATTEMPT 1, SHIPPED FOR THE OWNER TO PLAY** (2026-11-21). The pen-in
step of the guide's pipeline ([README.md](README.md) section 3). `mill/sketch.py`
draws the pictures and writes this design as an engine course (`--bbc`), and since
the owner's word that the prototypes are replaced as the work develops, that course
IS `apps/bonanza/courses/mill.bbc` (course K 2, pathway pad 3; SPEC.md 137.54.10).
The prototype it replaced is TMIL's top cell for cell, and the rows that needed its
features play TMIL. It compiles with `tools/bbcourse.py`, and its numbers below are
MEASURED on it (they were taken on the scratch draft `mill/mill-draft.bbc`, the same
text, which is gone). Distances are tiles and heights are units. The cells are the
engine's own, with no offset.*

The owner's brief (2026-11-21): *"a windmill minigolf course, with windmills and
tubes"*, mid length with a target of about 60 s, *"more dense screens ... spending more
time on each screen, as the theme is not 'speed down a hill'"*. The ball is rubber at the
start. It KEEPS the prototype's *"box with bumpers - the entrance and spacing on those
is good, leading to them being annoying but not impossible, and going into a tube"*
and *"the ending style - a sandpit surrounding a hole finish"*. It adds a TWO-ROUTE
section. One route takes the ball through a forced glass pad under an archway, which
makes it the riskier GLASS route. It has a respawning jump pickup and a jump the ball
must make (or break on). The other is the easier rubber route, entered by an open tube.
Both rejoin before the finish. Later the same day the owner picked BOTH suggested
elements: *"See-saw and quarter turn both sound like good elements to introduce here,
and fit the theme."*

| field | value |
|---|---|
| place | course 4, reached by DOWN's exit 0 (the glass leg's finish) |
| ball | rubber; glass on the glass route only, which ends on a rubber pad |
| finish | ONE: a CUP in a sandpit (`cup`, SPEC.md 137.14.4.3) |
| families | `rotor tube archway turntable pickups seesaw`, all of them RESIDENT, so the course has no fetched family (137.25.6.9) |
| new to the pathway | the SEE-SAW (137.42) and the QUARTER-TURN TURNTABLE (137.43); also the respawning jump pickup and the cup |
| music | `windmill` (the prototype's song) |
| picture | 1,024 x 888 px (`width 128`, `origin 672`) |
| clocks | 4 since the owner's builder edits (start, by the arch, the turntable's pillar, finish), in the `vase` frames since 2026-11-23 (open question 6, section 8) |

![the plan](mill/plan.png)

![in the game's projection](mill/iso.png)

## 1. The course, section by section

```
 TEE --door--> WINDMILL 1 --tube--> B --ramp--> BUMPER BOX --drop tube--> F (flag 0)
                                                                          |
                                                              SEE-SAW --> landing
                                                                          |  (2 units down)
                                                                      FORK PLAZA
                       glass: ARCH + glass pad -> tube           |           rubber: open tube
                                  |                              |                |
            back door <-- LEDGE H (flag 2, JUMP) ; 2-tile GAP    |     S (flag 1) -> TURNTABLE
                                  |                              |                |
                        V: 2 rubber pads -> ramp                 |     U -> WINDMILL 2 -> tube
                                  \______________ REJOIN J ______/________________/
                                                     |
                                           CUP in the SANDPIT
```

| | section | what it does | why |
|---|---|---|---|
| A | **the tee** | 6 x 5, guarded; the start is 3 tiles in front of windmill 1's door | a SAFE start with roll room (the guide's 1.10). The start clock is on its front-left corner (the prototype's model start clock) |
| W1 | **windmill 1** | the prototype's right windmill: a KEEP tube through the house, entered along -y, `seed 16`. Its LEFT windmill is gone | the theme, first thing. The left one was the guide's G7 softlock case |
| B, R | **B and the ramp** | out of the house onto B, then down 12 units along +y | the prototype's. Its sides are open, as they were (see 3.2) |
| G | **the bumper box** | the prototype's green, walls and three posts, moved up 12 units: the ramp's mouth, the bumper rails (`bounce`) and the DROP tube out of its east rail | the owner's KEEP, unchanged in shape |
| F | **F** | the drop's 3 units onto plain fairway. Flag 0 is on the drop's exit line | the first thing that can kill (the see-saw's open side) is next (G20) |
| SW | **the SEE-SAW** | a 2 x 2 teeter tilting along y, pivot 14.5. At rest its near end is F's height and its far end is a unit up. The ball rolls up it, its weight tips the plate past the pivot (rubber: 0.29 s, the ball carried), and it rolls off onto a 2 x 2 landing, then steps 2 units down to the plaza | a minigolf TEETER. It sits on the course's one shared walk, so every player meets it |
| P | **the fork plaza** | 13 x 4. Its front has the open tube's mouth (rubber), and an ARCHWAY over a glass pad before the glass tube's mouth | the owner's two tubes, one behind an arch with a glass pad |
| S, T | **the rubber route: S and the turntable** | the open tube runs +y, +x and +y out onto S. Flag 1 is on its line, then comes a 3 x 3 turntable, `fill ooo/.o./.o.`, `seed 228` | the classic rotating minigolf obstacle. Its middle column is open every other quarter turn (1.07 s), and the pivot is always floor, so a player can wait on it |
| U, W2 | **U and windmill 2** | a 4 x 5 apron. The door is on the second house's +x face (entered -x), and the tube comes out of the house's FRONT (+y) onto the rejoin | the second windmill: the easy route's timing obstacle |
| Q, H | **the glass route: the arch and the ledge** | under the arch the ball rolls over the glass pad (the arch's ceiling stops a hop over it, 137.39). The tube runs -x then +y up onto LEDGE H, 2 units over the plaza. Flag 2 (glass) is on the exit line, with the JUMP pickup a tile on (`prop jump 19 36 for 10 respawn`) | the owner's forced glass choice. The jump RESPAWNS both when it wears off (`respawn`) and on a respawn (its class) |
| GAP | **the jump** | a 2-tile gap over the void to V, at the same height | the make-or-break. MEASURED (section 5): with the jump it is made, and without it glass falls every time |
| L | **the back door** | H's west edge drops 2 units onto a lane back to the plaza. Glass may step down it, and nothing climbs it | KEPT AS THE WAY BACK (no longer required): the tool once needed it (section 3.1), but since SPEC.md 137.14.4.1.2 a flag or pad also passes when it reaches a finish taking only RESPAWNING pickups. The owner keeps it as a softlock-proof way back: glass that will not jump walks back and takes the rubber route as glass |
| V | **V** | the landing, then a 2-wide neck with TWO RUBBER pads, and a ramp down to the rejoin | ends the glass stretch on rubber (G13, G14) |
| J, Z | **the rejoin and the finish** | the rejoin green, a 3-wide walk in, and a 5 x 5 SANDPIT with the cup in its middle (the cup's cell NORMAL). The finish clock is on its front-left corner | the owner's KEEP. Sand stops every ball under the cup's capture within a tile (137.14.4.3) |

### The two routes

| | rubber (easier) | glass (riskier) |
|---|---|---|
| from the plaza | the open tube, S, the turntable (wait on the pivot), U, windmill 2 (time the gate) | the arch and pad, the tube, the jump pickup, the 2-tile jump, the rubber pads, the ramp |
| what can kill | the turntable's ports (back to flag 1, a tile away) and U's east edge by the table | the gap (back to flag 2 on the ledge, the jump back with it) |
| distance from the plaza | 76.5 tiles of route in all (the sketch) | 32 tiles |
| MEASURED, start to cup | **27.4 s** (the route demo, autopilot, hopping the turntable; **31.0 s** since it waits on the pivot, SPEC.md 137.14.7.4.5) | **27.0 s** (the autopilot to the ledge, a scripted Hop at the lip, then on) |

The glass route is not faster for the autopilot. The autopilot never waited, and it
hopped over the turntable (section 4); since SPEC.md 137.14.7.4.5 it waits on the pivot
(the rubber route 31.0 s). A human who waits on the pivot and times windmill 2 pays
that on the rubber route, and the glass route pays only the jump. The glass route
saves the most when the waits are long.

## 2. Flags, clocks and the camera

- **Flags (3 of 8)**: flag 0 on F, before the see-saw (rubber). Flag 1 on S, before the
  turntable (rubber). Flag 2 on ledge H, before the jump (glass). No flag stands where
  nothing ahead can kill: nothing before F can, because the bumper box is walled and
  a fall off B or the ramp is a short way back to the tee.
- **Clocks (3)**, all G9 - G12, MEASURED by `--guide` on the route demo: the start sees
  clock 0, no two clocks share a window, no clock is touched, and the longest stretch
  with no clock in view is **13.2 s** on the CGA (13.1 on the Hercules), under 15:
  - **start**: the tee's front-left corner (the prototype's);
  - **turntable**: on a pillar tile east of S, its top 5 units under S. It is not on the route, and it
    is low so that its head is out of the see-saw's window (section 3.1);
  - **finish**: the sandpit's front-left corner, in the cup's window.
  - There is **no fork clock**. One at the plaza met the see-saw in one window: its 2
    numerals, the plate's 4 lanes and the flag's event lane make 7 pose changes on one
    step, over the 6 a window may take (SPEC.md 137.19.10).
- **The camera** follows the course down the screen. Horizontal moves come at the
  plaza (the fork), at the turntable and at the rejoin, all on the ground. G3 was
  REFUSED for the autopilot's run (section 4); it passes since the STAND (SPEC.md 137.14.7.4.5).

## 3. What the tool refused, and what changed for it

### 3.1 Refusals met, each fixed in the sketch

| refusal | fix |
|---|---|
| a ramp rate of -2/3 a tile | the walk off F made of whole half units; later replaced by the see-saw |
| a guard rail touching a ramp, or a floor at a corner no rail passes through (137.35.1) | `blockrails`: a BLOCK rail there instead |
| the course wider than 512, then 896 px | `width 128`, `origin 672` |
| 5 occluder records in a block (over 4) | the SHATTER PIT under the jump (5 units down, so glass would break visibly) is OFF (`MILL_PIT=1` puts it back). There are no rails beside the turntable or on U's east edge by it |
| windmill 1's doorway "in the shade" (OCCG in IN's 3 x 3) | the tee widened under B, and its east edge before the ramp left open: a two-height guard, then a block rail there, shaded the door |
| windmill 2's doorway in the shade | U 5 deep with the door a row up, so U's south rail is two rows in front of the door's 3 x 3 |
| the arch's pad under a third seen (A10) | the glass tube runs -x first (a +y body in front of the arch hid the pad), with no rail beside its mouth |
| over 1,024 BLOCKS, three times (a limit since lifted: SPEC.md 137.56's map form 9, ROWNIBS, chosen automatically past 1,024 blocks; the bound is now the part's 65,024 bytes) | the sand BUNKER on F (about 48 blocks, `MILL_BUNKER=1`), the finish's magenta bumper rails (`MILL_FINRAILS=1`; guard rails now) and the ramp's side rails are all gone, and heights are whole units where half units bought nothing |
| a 4-long see-saw: its picture changes over 10 lanes, over the 6 a plate may have (137.42.5) | 2 x 2 |
| the see-saw's lanes in a flag's lane block | flag 0 moved a tile back, onto the drop's exit line |
| the see-saw and a clock in one window, 7 pose changes (137.19.10) | no fork clock, and the turntable clock on a low pillar |
| the jump unreachable with no pickup (137.25.7.3, Q-92: every finish reachable with no pickup, so a pickup only shortens a route) | the BACK DOOR. Without it the glass pad and flag 2 were refused (no longer: SPEC.md 137.14.4.1.2 counts the respawning jump; the door is kept as the way back) |

Also found: rubber drifted off the see-saw's open side and respawned at the START (the
autopilot did, from F). The see-saw's west side is now block-railed. Its east side is
open, because a block rail there is in front of the plate and hid the ball on it for
1.4 s. Flag 0 on F makes a fall there cheap.

### 3.2 The draft's verdict (MEASURED, `bbcourse.py -o DIR mill-draft.bbc`)

- **It compiles.** The route demo is COMPLETE: 1,495 steps, **27.37 s**, rubber, 0 falls,
  4 Hops. NO TRAP passes from every flag and pad. *(Since the route search's STAND,
  SPEC.md 137.14.7.4.5, the shipped course's route demo is 1,695 steps, **31.03 s**,
  COMPLETE, 0 falls, NO Hop: the ball waits on the turntable's pivot.)*
- Budgets: **980 blocks**, which was the binding limit (1,024) when measured; since SPEC.md
  137.56 (map form 9, ROWNIBS) the block count is no longer a bound, only the part's
  65,024 bytes. The picture part is 55,610 bytes (9,414 under 65,024). It is **19,083
  bytes LZ4, over the 60 s target's 1.5x budget (18,825) by 258**. That is reported,
  not refused (137.27.5).
- Visibility (reported): windmill 1's drop IN 50%. The ARCH'S GLASS PAD is 50% against
  75%, because the arch's right leg covers its lower right half; that is in the shape of
  an archway along y. The second rubber pad is 74% against 75%. No hidden stretch is
  over 0.5 s.
- `--guide` with the route demo: G1 27.2 s (the floor is 25), G9, G10, G11 and G12 pass.
  **G3 was REFUSED** (it PASSES now, on the CGA and the Hercules: since SPEC.md
  137.14.7.4.5 the route demo waits on the pivot, 2 flights, 0 panned): the autopilot
  reached the turntable while its front was closing and
  hops off the pivot over it onto U. That flight pans 15 columns on the CGA and 6 on the
  Hercules as it turns toward windmill 2's door. A human who waits on the pivot makes no
  such flight. An authored "wait on the pivot" demo was tried and not finished: a ball
  gripped to rest near the pivot fell before the front opened, which is worth a look at
  where the autopilot stops (section 6, question 3).

## 4. Time: the course is SHORT of 60 s

The autopilot does the rubber route in 27.4 s and the glass route in 27.0 s. It never
waits. A player adds windmill 1's gate (up to 1.2 s), ricochets in the bumper box, the
see-saw's tip, a wait on the pivot (up to 2 quarters, 2.1 s) and windmill 2's gate.
PREDICTED for a human: about 40 - 45 s, not 60. The course was at 980 of 1,024
blocks when this was written; since SPEC.md 137.56 blocks no longer bound it (the part's
65,024 bytes do: the picture part has 9,414 bytes spare), so reaching 60 s no longer means
making block room first. See questions 1 and 2.

## 5. The jump (MEASURED on the model)

- With the pickup, a Hop at the lip of H (the jump's Hop 400 for any ball, 137.25.9)
  lands on V, 4.5 tiles on, and the run finishes (27.0 s).
- Without it (the pickup moved off the line), glass falls into the gap every time and
  respawns at flag 2: 32 falls in 4,000 steps. The jump is needed, as the brief wants,
  and the back door is the only other way (3.1).
- The SHATTER PIT the brief's "break" suggests (a floor 5 units under the gap, so glass
  breaks visibly rather than falling away) is in the sketch behind `MILL_PIT=1`, and is
  refused today for its occluder records (3.1).

## 6. Open questions for the owner

1. **Length.** The course is about 27 s for the autopilot and about 40 - 45 s PREDICTED
   for a human, against the 60 s target, and it has 980 blocks (no longer a bound, SPEC.md 137.56). Should the
   target be 45 s? Or should room be made for a third dense screen: a second bumper box
   without rails (G21) on the rubber route, or MOON's tube fan?
2. **What the block budget took** (the 1,024-block limit, lifted by SPEC.md 137.56). The sand bunker on F, the finish's magenta bumper
   rails and the ramp's side rails are all gone (each is a knob in the sketch). Which do
   you want back, and at what cost elsewhere?
3. **The turntable's G3.** ANSWERED (2026-11-21): the route search's STAND (SPEC.md
   137.14.7.4.5) waits on the pivot instead of hopping, and G3 passes on both cards. The
   question as it stood: the autopilot hopped it. Options: accept a playtest demo as the
   G3 run; make the crossing slower to need (`quarter 64` is the slow default already);
   or move the turntable to where a pan cannot happen (a straight +y run with no turn
   after it).
4. **The back door.** Kept as the way back (no longer required by the tool, SPEC.md 137.14.4.1.2; the owner keeps it as a softlock-proof way back).
   It reads as a blind alley from the plaza. Keep it, or make it a visible "chicken run"
   (a sign, a step)?
5. **The see-saw's open east side** (a block rail there hides the ball), and its fall
   back to flag 0. Is that fine, or should it be a guard-railed flat plate instead?
6. **Clocks.** ANSWERED (2026-11-23): the owner picked the TULIP VASE ([mill/CLOCKS.md](mill/CLOCKS.md) B), now the tool's `vases`, `vasem`, `vaset` and `vasef` (SPEC.md 137.18.5.2) on the four clocks; section 8. The question as it stood: There are three, in the default frame. A theme idea for art that says where
   the player is: windmill SAILS, whole at the start, split at the fork's turntable (one
   sail for each route) and a flag pin at the cup.
7. **Both new elements.** Both fit, at the costs above: the see-saw cost the fork clock,
   and the turntable cost rails and G3. If one goes, I would keep the TURNTABLE: it is the
   rubber route's reason to exist, and the see-saw sits on a walk that worked without it.
   The other candidates were the drawbridge with a switch and key (137.41), which needs
   backtracking, and a water pond (137.36). A pond that rubber floats over reads oddly
   as a minigolf hazard, and it would be a fetched family.

## 7. How the pictures and the course are made

```
python3 docs/plans/bonanza-courses/mill/sketch.py                    # plan.png, iso.png, the clocks' spacing
python3 docs/plans/bonanza-courses/mill/sketch.py --bbc apps/bonanza/courses/mill.bbc --force   # the SHIPPED course
                                                                     # (the glass route rides it as `branch GLASS` ways)
python3 docs/plans/bonanza-courses/mill/sketch.py --bbc OUT.bbc --force --glass   # the glass route's ways
python3 tools/bbcourse.py -o DIR apps/bonanza/courses/mill.bbc   # alone: about 2.5 minutes
MILL_PIT=1 / MILL_BUNKER=1 / MILL_FINRAILS=1                         # the parts the budgets took out
```

**Since 2026-11-22 the owner edits `mill.bbc` in the course builder** (SPEC.md 137.58), so `sketch.py --bbc` no
longer writes the shipped course: running it over `apps/bonanza/courses/mill.bbc` would throw the owner's edits
away. Edit `mill.bbc` itself, and keep its geometry, checkpoints and props as the owner left them.

## 8. The vase clocks and the four accepted warnings (2026-11-23)

**The clocks.** The owner picked the TULIP VASE and asked for a FOURTH flower, MILL having four clocks now. The
concept's frame is lifted into the tool (SPEC.md 137.18.5.2, `_clock_vase`), the bulbs growing one flower a clock
along the route: `vases` on the tee (7, 13), one bud and the tee'd ball; `vasem` by the arch (21, 25), a bud and
one opening; `vaset` on the turntable's pillar (34, 35), bud, opening and bloom on the turntable disc; `vasef` at
the finish (24, 46), two in bloom and two FLAMED tulips, the fourth flower (white petals streaked magenta: it
reads white on the Hercules, where the magenta heads are a grey checker on MILL's grey walls). The heads are
lit white on their left for the same reason. **No vase clock carries an occluder record**: every record a vase
cut hid a ball only in the VOID cells behind it, so those cells are `noocclude` (the start's were already, by
the owner's own `noocclude` round A). MEASURED, the picture part: blocks 1,156 -> 1,173, masks 221 -> 223,
records 1,858 -> 1,794, 62,350 -> 62,402 bytes in RAM, LZ4 22,775 -> 23,383.

**The four warnings the builder showed, each kept with `accept` and its reason in the course** (SPEC.md
137.58.5; `bbcourse.py --strict` passes, reporting each as accepted). **2026-11-25: the three `shade` rows are
history - the rule was withdrawn (SPEC.md 137.12.19, section 9's closing note below), `accept shade` is refused
by name and the course's three lines are deleted. `accept mark 20 27` is the one this course keeps.**

| warning | where | what it is | kept by |
|---|---|---|---|
| `shade` | the first windmill (line 71), cell (10, 9) | A's east guard rail (line 47) stands on the raised ramp R, and its west end reaches the lower right corner of a ball's box at (10, 9) | `accept shade 10 9` |
| `shade` | the second windmill (line 89), cells (29, 27) - (30, 29) | what (31, 28) and (31, 29) draw reaches 8 px into the box of a ball in the doorway's east cells | `accept shade 29 27` |
| `shade` | the third windmill (line 91), cells (27, 44) - (28, 45) | the guard rails on lines 65 and 66 clip a ball's box in its doorway's 3 x 3, 16 px over the floor | `accept shade 27 44` |
| the glass PAD's mark, 50% seen (needs 75%) | the pad under the archway (line 92) | the arch's near leg covers half the pad's top, as any single high arch along x would | `accept mark 20 27` (new, SPEC.md 137.58.5) |

The fourth was never the compiler's: it is the visibility audit's (SPEC.md 137.15.10.4), which the builder's
problems list shows from the picture job, and which only REPORTS - so `--strict` and `bbedjob.py check` saw
three. `accept mark` reaches the audit's three readers (the build's audit line, the picture job, the window).

Not one of the four: `--selfcheck`'s `courses` item 3 fails MILL with *"the windmill on line 89's doorway: not on
the glass"*, crystal clocks or vases alike - the owner's `wall rect 28 27 29 30 flat 8.0` stands in front of the
second windmill's doorway. It is the owner's geometry, so it is left for the owner.

## 9. Research: the windmill's OCCLUDER STOP, and how to process less of it

**CLOSED 2026-11-25 by SPEC.md 137.12.19, and 9.1's first bullet is WRONG about the guest.** There is no
"occluder stop": `bz_ogate` (`bz_mkboxes`) is the ball's cell's flag and nothing else, `bz_occ` opens on it alone,
and neither has ever read `bz_must` - so a must-draw rotor's frame runs the pass whenever the ball's cell asks.
The "no pass" was only ever the TOOL's promise, kept by refusing the course; once that became a warning with
`accept shade`, MILL shipped with the pass running on those frames. So option 4 below ("run the pass on the
must-draw frame") needed no guest byte: it was already what the guest did, and the rework is the rule's
deletion, with the frame's pass REPORTED a windmill (MILL: 9,150, 22,340 and 20,870 clocks at the worst flagged
cell of each doorway). The rest of this section is kept as it was written.

*Research only, nothing built.* The owner, of the three `shade` warnings: *"apparently we 'stop occlusion' for
the windmill, and do so in a way that goes around ground blocks in a way that doesn't make a ton of sense to me.
It barely clips a guardrail in this case so it doesn't really matter, but we'll need a way to mark that as ok for
now, and maybe an item to research how we can either process less space for this, or process occlusion."*

### 9.1 What is stopped, and where

- **The guest** (SPEC.md 137.12.5.2, 137.12.17 item 2): a windmill whose IN cell is in the ball's 3 x 3 cells
  (`bz_wol`) and whose TRUE gate state differs from its DRAWN pose is MUST-DRAW: its rotor box is the frame's
  contact group, drawn whatever the frame, so the blade a collision reads is the blade on the glass. **That
  frame runs no occluder pass at all** - not for the rotor's box and not for the ball's. It is a budget
  decision (137.12.11): the one-box rotor frame is already 64.9k clocks of the CGA's 79.6k refresh (82%) and
  65.0k of the Hercules' 93.8k, and two ball boxes with it about 88k on either card, a frame late. The stop is
  in TIME (the frames on which the gate changes while the ball is near), not in space.
- **The tool** keeps that frame correct by a rule in SPACE (137.12.4.6, `shade`): no cell of IN's 3 x 3 may
  have `OCC` or `OCCG` - a ball anywhere in such a cell can be under an occluder record (137.11.4.3), and on the
  must-draw frame the record would not be laid, so the ball would be drawn over what stands in front of it for
  that frame.

### 9.2 Why it seems to walk around ground blocks

- **The region is CELLS of the world grid, IN plus one either way, not pixels.** On the iso picture nine cells
  are a diamond; the builder's *Shade: why* paints the pixels each cell OWNS (the owners canvas: the cell whose
  drawing put a pixel there last), so a block nearer the viewer - the windmill's house, a wall, a raised floor
  - takes its pixels out of the highlight, and the yellow shape bends round it. Three of the nine cells are
  usually the house itself (walls: no flags).
- **The flags are a ball's BOX, not its sprite, and the box spills out of its cell.** A ball anywhere in a cell
  covers a box about 48 px wide (`foot_x`: the cell's width and the sprite either side), so a record drawn by
  a cell OUTSIDE the 3 x 3 flags a cell INSIDE it: on MILL a guard rail two cells away (drawn with (13, 10), a
  rail on line 47) flags (10, 9), and rails on lines 65 and 66 flag the third windmill's. The rule then reads
  as an odd shape picked out of the course, though it is exactly "every cell from which a ball might touch the
  doorway this frame, at any position in the cell".
- **The box is generous.** At (10, 9) only the box's lower right CORNER meets the rail, where a round ball's
  sprite is mostly transparent (137.58.32).

### 9.3 Options: process LESS space

1. **Test lit pixels, not the box (tool only, 0 guest bytes).** Recompute the shade test with the cutter's own
   per-position test (`feet_real`'s poses and `ball_pixels`, as `clock_vis` and 137.58.32's `needs` do): a cell
   of the 3 x 3 is in the shade only if some REAL pose of a ball in it has a LIT pixel under a record. It keeps
   the guest's rule exactly and drops the corners of boxes. PREDICTED to clear MILL's (10, 9); the other two
   reach 8 and 16 px over the floor and may stay. Cost: tool time on a windmill's nine cells.
2. **Narrow the trigger to the cells a ball can reach the doorway from (guest, a few bytes).** At the cap a
   frame of up to 8 steps moves under a cell (12 gu), so a ball touching the doorway this frame starts in IN
   or a cell sharing an edge or corner with it ON THE OPEN SIDE; the cells beside and behind the house (and
   their flags) could leave the window. The gain is small (the house cells carry no flags) and the telegraph's
   proof (`bonanzawheel` leg 10, `bonanzaphys`'s `knock` and `pass`) would have to be re-made for the smaller
   window.
3. **Stop only the rotor's box, not the ball's.** The rotor's pixels never need the pass (137.12.4.5: every
   rotor pixel is the house's), so the stop could be scoped to the rotor's rectangle and the ball's boxes
   composed with the pass as on any frame. This is option 4's cost, by another name: the pass is what the
   budget could not afford.

### 9.4 Options: process occlusion PROPERLY on the must-draw frame

4. **Run the pass on the must-draw frame, priced per doorway.** The pass's cost depends on the records at the
   ball's position: MILL's worst anywhere is 31,130 clocks (`bbcourse.py`'s "the pass at most" line), but a
   doorway cell in the shade typically has 1 - 16 records. The tool already prices a position's pass; it could
   price `64.9k + the pass at that cell's worst position` for each flagged cell of the 3 x 3 and REFUSE (or
   warn) only where that passes the refresh, so a rail that clips a box costs a few hundred clocks and is
   simply drawn right. Guest: the must-draw frame's "no pass" test made conditional on the cell's `OCC` (tens of
   bytes, PREDICTED); measure with 137.12.17 item 2's emulated-8086 pricing on MILL's three doorways.
5. **Defer the rotor a frame when the ball is in a flagged cell and cannot reach the doorway this frame.**
   The ball's box gets the pass, the rotor waits one frame as any contact lane does. Only safe off IN and the
   open side's cells (the telegraph), so it is option 2's window with a fallback; more guest logic than 4.

**Suggested order**: 1 first (tool only, it may clear the cases that "barely clip"), then 4 priced on MILL's
three doorways - if the pass at a doorway is a few hundred clocks, the shade rule turns from a warning about
the picture into a budget the tool checks, and `accept shade` stops being needed. 2 and 5 only if 4 does not fit.
