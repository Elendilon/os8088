# FIRST ROLL: design sheet, attempt 1

*Status: **IN THE ENGINE, playtest 6, revision 7** (art prototypes) (`apps/bonanza/courses/roll.bbc`,
built by `make BUILD=build/roll BZROLL=1 bonanzadisk`). While the LAYOUT
moves, `first/sketch.py --bbc --force` writes `roll.bbc` from the sketch, and
its header lines travel in the sketch, so nothing hand-made is lost. Once
the layout settles, the `.bbc` is edited by hand. Distances are tiles,
heights are units (8 px). Times MEASURED on the tool's model are marked; the
rest are PREDICTED.*

This is the shipped course 1. The prototype course of the same title
(`apps/bonanza/courses/first.bbc`) and the other prototype courses are to be
removed later, with their tests rewritten (the plan's story 11.17). Until
then this course is built under a working name of its own in the tool,
`ROLL`, and it takes FIRST when the prototype goes.

**What each revision changed (the owner, 2026-11-18):**
- **Revision 7, art prototypes** (the owner, on the recommendations:
  floating terraces for another course, not this one; a screenshot of
  diagonal tiles; *"5: Oh, I think I like that; but we have to be careful
  about how much view we block off. Add one ... right before the leap,
  across the rail blocks; at a good height, we're not trying to prevent a
  jump here"*; *"6: I like this maybe combined with art"*; the palette as
  the first course's "default look"; *"make some art prototypes on the
  course; it needs to fit in, look natural; so same style as the general
  art and game, and high quality"*):
  - the walk elbow's lone left block is gone (the first try removed its
    twin, by the steps);
  - `first/decals.py` (host-only, deterministic: the art's source) draws in
    world coordinates and projects with the tool's own formula, one-pixel
    black lines in the course's four colours. It writes the `roll_*.bba`
    files and a marked ART block at the end of `roll.bbc`;
  - **the prototypes**:
    - a TEE mark under the start (a magenta disc, black rim, white
      highlight);
    - two CHEVRONS down the lip's ramp;
    - a FRAME before the leap: the run-up's last rail blocks raised into
      pillars, and a BANNER between them 4 units over the floor, so a Hop
      passes under it;
    - two LONE PILLARS floating in the void, each with a pennant in the
      checkpoint flag's style;
  - **cost** (MEASURED): the pillars +12 blocks and +47 occluder records,
    the art +57 blocks (records and masks unchanged). The course part
    8,622 -> **9,463 bytes** on the disk;
  - **the diagonal-tile look** is a screenshot only (`first/diagonal-
    variant.png`, today's left, chamfered right), not in the course.
- **Revision 6, from playtest 4** (the owner: the middle clock "kind of
  works there", the bottom clock and `stop down` "work great", the unwalled
  hill "plays fine, and adds a bit of visual interest", the hole "in the
  natural path of travel, though easy to avoid which works for a first
  course"):
  - the ledge's back rail is a see-through GUARD rail. Its first tile is
    left open: a guard rail may not stand beside the hill's last ramp;
  - flag 0 moves one space down, onto the line the ball takes into the
    run-up;
  - the lone rail block at the corner of the last step is gone. It read as
    a tile at the walk's height, and that corner is open now.
- **Revision 5, from playtest 3's mark-ups:**
  - **the hill has no rails and no back wall** (*"the guard here is that
    its so wide. We may or may not keep the idea; I just want to see if it
    looks and plays good"*);
  - **the lip is the prototype's**: a 4-tile ramp falling 2 units onto the
    landing, and the hole ONE BLOCK OUT from its foot, in the natural path
    (*"I'm not getting dumped into the hole like I was on the old first
    roll"*). Everything after it moved 2 rows down, and the walk's ramp is
    2 tiles shorter to take them back;
  - **the clocks follow the owner's mock-ups** (look and feel over timing;
    the owner will hand-place them):
    - the start clock sits on a tile one block out from the plateau, level
      with it;
    - the middle clock stands on top of the landing's left rail block (on
      the right rail it stood in front of the landing and hid the hole);
    - the finish clock stands on top of the block at the goal plateau's
      back-left;
  - **the camera stops once the finish is in view**: `stop down`, a course
    flag (SPEC.md 130.45.4).
- **Revision 2:**
  - the three railed corners became a SHAPED CHUTE: two tiles wide,
    unfenced, the rails back up on its exit, the far end of the corner
    after it open for a full-speed overshoot;
  - flag 1 moved to the turn at the foot of the steps;
  - there is no flag past the leap.
- **Revision 3:**
  - flag 0 is at the top of the lip's run-up, BEFORE the lip (G20);
  - the rail stub across the leap's run-up is gone (G24);
  - the rails are BLOCK rails.
- **Revision 4, from the first play** (the owner: *"30s for me, not trying
  hard just going"*):
  - **the lip, the hole and the chute's mouth lie on one straight line.**
    The chute now continues the lip's direction (+y) before turning, so
    going forward means going over the hole (*"the user is not guided
    'forward' ... so naturally we steer, and then miss the hole"*);
  - **the route is re-laid to swing less across the screen**: every +x leg
    balanced by a +y leg, 168 px of swing in the sketch against 216.
    Section 2 says why that is not enough on its own;
  - **the clocks are placed for the camera, not for the void behind them**
    (the owner leaned to custom clock art). They float on lone pillars, none
    partly behind a block, and the middle one moves later in the course, so
    no stretch goes 15 s without one;
  - **two things the engine forced**:
    - the chute is 8 px deep, not 10 (10 put 5 occluder records in one block
      of its sloping second leg, over the bound of 4);
    - the course is 3 units shallower overall, because its occluder records'
      tops may span at most 255 px. The corner after the chute (K3) is level
      with the apron before it, and the walk's first leg is level.

| field | value |
|---|---|
| place | tutorial 1: the first node of the pathway, no branch |
| world | the tutorial (none) |
| families | **none**: tiles, holes, one shaped chute (FIELD cells, SPEC.md 130.28) and rails |
| start ball | rubber, the whole way (G13) |
| finishes | one, the goal plateau; no secret |
| target time | **about 35 s** (G1). MEASURED on the model: a steered run of the sketch's route finishes in 35.7 s with no fall; the owner's first play (revision 3) was 31.4 s, "not trying hard" |
| pace | about 950 picture lines, about 120 block rows: one part |
| palette | the owner's choice |
| clocks | three, on floating pillars, placed for the camera; custom art (G23) |
| rails | block rails (*"The block rails look good"*); one see-through guard rail was tried beside the chute's exit and refused by the tool (section 6) |
| song | the owner's choice |
| the new demand (CD2) | **reading an edge**: drops kill you, and the player learns the timing at a lip, when to let the ball run and when to slow it |
| what it teaches | roll and steer; brake; ramps; a shaped chute (*"you actually have to be slightly cautious in, which is good"*); **drops kill you, and you need to learn the timing**; a Hop is always allowed and never required |
| help it gives (CD2) | rails on nearly every edge; ramps that funnel to the centre; a chute that guides with no rail; a flag just before each hazard |

![the plan, from above](first/plan.png)

*Above: the plan. +wx is right and +wy is down. The arrows mark ramps and
their downhill direction, and `~` marks the chute's cells. Yellow is a rail,
and an edge without one drops into the void. Red is the route, cyan the
clocks, pink the flags.*

![the course in the game's projection](first/iso.png)

*Above: the same course in the game's projection, drawn as plain blocks with
none of the real art. The cyan boxes are one CGA window (320 x 200) at the
start, the middle and the goal; the two vertical lines are the CGA camera's
dead zone (160 px). `first/sketch.py` draws both pictures.*

## 1. The course, section by section

Times are cumulative, from the model's steered run of revision 4.

| | section | what happens | what it teaches | 0 - s |
|---|---|---|---|---|
| A | **the start and the hill** | A railed plateau, then three ramps, alternately along +y and +x (SUMMIT's opening hill), each throwing onto a flat landing that a rail closes, so the throw turns the ball onto the next ramp | rolling, steering, what a ramp does to speed; nothing here can hurt | 0 - 8 |
| B | **the ledge** | Two tiles wide, a wall behind and its FRONT EDGE OPEN | **drops kill you**: the first fall respawns at the start | 8 - 11 |
| C | **flag 0, then the lip** | Flag 0 on the run-up. A ramp ends in a lip 3 units above a wide landing, T. A HOLE sits where the straight full-speed landing falls, and the chute's mouth is straight on beyond it, so the way forward goes over the hole. Slowing down then steering round it, a Hop over it, or either side of the ramp all succeed. Holding straight on fails | **timing at a lip**. A fall replays only the lip | 11 - 15 |
| D | **the chute** | Two tiles wide, 8 px deep, NO rails: straight on from the lip (+y), round one corner, then along +x, falling about 2.5 units. A flat apron (D3) follows, its rails up one tile after the chute; the corner after it (K3) is level, its far end OPEN | the shaped floor; then **braking**: out of the chute at full speed the ball overshoots K3 into the void. A fall respawns at flag 0 | 15 - 22 |
| E | **the steps, then flag 1** | Three one-unit steps down onto floor, railed. Flag 1 on the last step | dropping onto a floor is fine; only the void kills | 22 - 25 |
| W | **the walk** | Two tiles wide, both edges open: a level leg along +x, a railed elbow, a ramp along +y | steering with the drop on either side | 25 - 31 |
| F | **the leap** | A railed elbow and run-up along +x (no rail across its entry), a ONE-tile gap, a landing 2 units under the lip | the mirror of C: **too slow** drops into the gap. A fall respawns at flag 1 | 31 - 33 |
| H | **the finish** | A short ramp down onto a wide, railed goal plateau, all of it in view (G5). No flag: nothing here can kill | | 33 - 36 |

## 2. The camera (G2, G3): why a zigzag still pans, and the question it raises

**MEASURED on the model**, from the owner's first play (its log replayed
through the tool's physics and camera, the replay reaching the goal in 31.4
s with no fall, as the play did):
- the ball swung 229 px across the screen;
- the camera panned 16 - 24 columns (128 - 192 px) five times, at 2.4,
  7.8, 21, 25.5 and 28.8 s;
- two of the pans came in the air: down the steps, and during the leap.

**Why.** LATTICE frames the window at positions 128 px apart and LEADS in
the direction of travel. In practice its no-pan band is only about 110 px.
A vertical course alternates +x and +y legs (Down is the grid's diagonal),
and every leg between 4-wide pads crosses that band.

**Revision 4 narrowed the swing** (168 px in the sketch, 196 px on the
model's steered run), but the steered run still pans five or six times on
each card, twice in the air.

**The course's whole picture is 320 px across** (80 - 400), one CGA window.
With the camera held at that framing for the whole run (column 10, MEASURED
by pinning it in the model):
- nothing pans across, so no jump pans (G3 by construction);
- every clock is in view where it serves;
- the longest stretch with no clock in view is 10.5 s on the CGA and 11.4 s
  on the Hercules (with today's camera: 12.8 s on the CGA and 15.2 s on the
  Hercules, which fails G12).

**Taken (the owner, 2026-11-18)**: *"Yes. We won't use this often due to
visual interest, but for the intro course it fits fine, and it gives a
'smoother' introduction."* **BUILT as SPEC.md 130.45**, `lock across`:
- the tool centres the window on the course's picture: column 10 on the
  CGA, 7 on the Hercules;
- the game holds it, skipping the across axis.

MEASURED on the model's steered run: **0 columns panned on either card**,
and the longest stretch with no clock in view is 10.5 s (CGA) and 11.4 s
(Hercules). The lock costs 51 bytes of code, 2 of bss and 2 a course of
table.

## 3. The clocks (G9 - G12, G23)

Custom art (G23), so each clock is placed for the camera. All three float
on lone one-tile pillars (`float`: their faces hang 3 units rather than
running down to the ground), and none stands behind a block.

| clock | where | in view (MEASURED, the model's steered run, today's camera, CGA) |
|---|---|---|
| start | right of the start plateau, off the hill | 0 - 2.6 s (0 - 4.8 s on the Hercules) |
| middle | above the far corner after the chute (K3), high enough to clear its back rail | 15.5 - 23.0 s |
| finish | left of the goal plateau, low enough that every goal cell's centred window holds it (the shipped finish-clock rule, SPEC.md 130.22.6) | 31.3 s to the goal (with the lock) |

- G9 (start) and G10 (never two on one screen) pass at compile.
- With the lock the longest stretch with none in view is 10.5 s on the
  CGA and 11.4 s on the Hercules, and every clock stays in view to the end
  of its stretch.

## 4. Surfaces, lifts, pads and props

- **None but the chute.** No sand, no ice, no lift, no pad, no family.
  Course 2 (Hop, rubber's "and again", a spring) brings the first prop.
- **The chute is a candidate STANDARD PART** (the guide's section 5).

## 5. The owner's answers

| question | answer (2026-11-18) |
|---|---|
| C and F, the pair | "Leap is good" |
| the ledge so early | "this pacing looks pretty good"; flags go just BEFORE what can kill (G20) |
| rails | block rails, *"The block rails look good"* |
| the clocks' art | custom, leaning (G23) |
| the name | the prototype courses go later (story 11.17); this course takes FIRST then |
| length | 30 s for the owner "not trying hard" on revision 3 |
| the cannon and the spring (G3) | a cannon's throw is exempt; a spring's is not, exceptions per use after a playtest |

## 6. In the engine

- **The tool's rules shaped revision 4**:
  - slopes are whole half units a tile;
  - a block of the picture holds at most 4 occluder records, so the chute is
    8 px deep;
  - the occluder records' tops span at most 255 px, so the course is 3
    units shallower;
  - a see-through guard rail stands only beside flat floors of ONE height,
    so the rail at the chute's exit is a block rail and starts one tile
    after the chute.
  - A level chute leg was tried and dropped: a slow ball cannot climb the
    end taper out of a level channel.
- **The limit is given by hand (60 s) for the playtest.** The autopilot
  cannot follow a chute yet (another session is on it), so the tool's limit
  rule has no route to price. The batched step replaces it.
- **The model's steered run** is a scratch script in the session, not a
  row. It follows the sketch's route with a simple steering rule and
  reaches the goal in 35.7 s with no fall.

## 7. Visual interest: recommendations (2026-11-18, for the owner)

Each is priced in bytes or clocks. None is built; the owner picks.

1. **Floating terraces instead of columns** (`float`, faces 3 units deep).
   - Today every section stands on a column to the ground, so the course
     reads as one magenta monolith.
   - Floating the hill's landings, the walk and the leap's landing would
     show void between the levels: depth, a silhouette and gaps the eye
     reads as drops.
   - It also SAVES bytes, since most of the picture is those columns.
   - It is the standard column tile's twin, for the kit.
2. **Decals with `art`** (now allowed on play courses, SPEC.md 130.23.2).
   An art pixel takes the occlusion of the surface it is painted on, so a
   decal on a floor or a face IS part of it, front tiles included. Measured:
   the occluder records and masks are identical with and without.
   - A START mark on the plateau, chevrons down the lip's ramp, a warning
     ring round the hole, a painted finish banner on the goal plateau.
   - A few hundred bytes each (the unique blocks they make).
3. **Backdrop art in the void beside the course**: a sun or moon, a cloud
   bank, a distant skyline, in the locked window's black margins and never
   in front of the path. The window never pans across here, so a backdrop
   stays put like a stage set. Its blocks are the cost, so it is kept
   small.
4. **Diagonal tiles** (SPEC.md 130.24) on the outer corners of the
   landings and the goal plateau, to soften the stair-stepped edges. Tool
   and picture only.
5. **A frame at the finish**: an ARCHWAY (SPEC.md 130.39) over the goal
   line, or two pillars and a painted banner between them. The arch is a
   family part with lanes; the pillars and banner are picture only.
6. **Lone pillars and towers in the void** (single floating tiles, as the
   clock pillars are): rhythm and landmarks down the descent at a tile's
   bytes each. Placed away from the path, they can never be in the way.
7. **Palette and light**: the course's CGA palette (`palette`, SPEC.md
   130.16.6) for a bright first course, chosen by the owner on the glass.

**Suggested first try**: 1 and 2 together on the hill and the lip, one
playtest, measured against today's 8,622 bytes.

