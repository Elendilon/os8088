# WireArena: bots that shoot back, and the match around them

**STATUS: building, wave by wave.** Section 1 records the owner's rulings
on what is left of WireArena (2026-11-14); sections 2–6 are the bots and the
match flow, priced; section 7 the questions and the owner's answers;
section 8 what was built and measured, wave by wave.

WireArena is `apps/wirearena/`. Its history is
[MULTIPLAYER-FPS-PLAN](MULTIPLAYER-FPS-PLAN.md) §16,
[WIREARENA-HEIGHTS-PLAN](WIREARENA-HEIGHTS-PLAN.md) §9 and
[WIREARENA-WEAPONS-PLAN](WIREARENA-WEAPONS-PLAN.md). The computer opponent
was proposed in MULTIPLAYER-FPS-PLAN §9; this plan replaces that section's
design with the owner's brief: **fast more than good**.

Claims are marked as in the parent plans: **Measured** (a number taken, the
method given), **Derived** (arithmetic from measured unit costs) and
**Forecast** (a cost for code nobody has written yet).

## 1. What is left, as the owner ruled (2026-11-14)

| item | ruling |
|---|---|
| **Bots / shooting back** | **Next.** Fast more than good: routes like today's patrols, with branches a bot picks between; a time to shoot and an accuracy. This plan |
| **Player death, respawn timer, respawn points** | Yes - and a **scoreboard on a held Tab**; 40/80 columns move to **- and +** (Clear Skies' view-size keys). Section 5 |
| **Dummies on lifts** | Yes. Section 3.4 |
| **The serial link, then Ethernet and the lobby** | After the bots (MULTIPLAYER-FPS-PLAN waves 4–5) |
| **kern_mega** | Before shipping: tested, with soak rows of its own |
| **Keyboard-only aiming** | Adjust it (turn acceleration) - or the owner tests serial play with the PicoMEM v2 that is in the 5150 for Video Battle |
| **Real-CGA snow** | **Accept it; the user picks.** 80 columns is not performant on a 5150 today, and the 5150 is the only machine with a snowing card (MULTIPLAYER-FPS-PLAN §14 question 1, answered) |
| **Game modes** | Yes to all: duel, free-for-all with bots, last stand, and **capture the flag** especially |
| **Jump pads, teleporters** | Liked: they connect points of a map |
| **Replay, kill-cam** | A good feature |
| **More arenas** | **Last**, after every change that affects performance |
| **Footsteps, more sounds** | Maybe |
| **Radar** | Maybe: a prototype first. Maps are small and will stay small |
| **Two players on one 5150** | Too slow on a 5150; a bonus after everything else |

## 2. The shape: a bot is a figure that walks a ROUTE and rolls dice

Today's dummies already cost what a bot's body costs: a figure record, a
patrol walked a leg at a time with the leg's step worked out once
(`wa_figtick`, ~780 clk a figure a tick, Measured: the whole-frame traces
of WEAPONS-PLAN 3.3). A bot adds a little to that, and nothing a frame:

- **where to go**: at the end of each leg, a branch picked (section 3);
- **what it sees**: the player, every fourth tick, along a grid (section
  4.1);
- **when it shoots, and whether it hits**: a reaction delay, a gap between
  shots, an accuracy roll (section 4.3);
- **which way it faces**: turned toward its target by the sign of a cross
  product, 48 a tick, as figures turn today (section 4.2).

No bot ever traces a ray through the renderer, plans a path at run time or
takes a square root. Everything that is search is done on the host by
`tools/arenagen.py`, which already builds and checks the patrols, and
everything at run time is a table lookup, a compare or a dice roll.

**The renderer does not change** for a bot: a bot is drawn as a dummy is.
The one exception is the firing cue (4.3), a figure's attribute.

**For the network later**: a bot's state is a figure record (where it is,
which way it faces, its animation) plus events (it fired, it hit, it died).
That is exactly what a remote player's packets will carry under the owner-
authority model (MULTIPLAYER-FPS-PLAN §8.1). So the bots exercise the same
records and events the serial and Ethernet waves will fill, and a match
against bots is a match against "players" whose input happens to be local.

## 3. Routes

### 3.1 The route graph (arenagen)

An arena's patrols become a GRAPH: **nodes** (points on the floor, a
platform or a lift) and **legs** between them, each walkable both ways.
arenagen checks every leg as it checks a patrol today: every tick's rise
within a step, no wall or lift crossed, and bit 15 where the leg leaves the
ground (`wa_figz` reads the floor only there).

| table | what | bytes (Forecast, 24 nodes and 40 legs) |
|---|---|---|
| nodes | x, y; its legs' indices (up to 4) | ~200 |
| legs | its two nodes; its heading and step count each way | ~320 |
| next hop | for each node and each GOAL node, the leg to take first (a breadth-first search on the host) | 24 x 24 = 576 |
| nearest node | for each 128-unit PVS cell, the nearest node reachable from it | 256 |
| tall grid | a bit a 64-unit cell, set where a tall box stands (section 4.1) | 128 |

About 1.5 KB more in the arena's part, copied into the game's half at load
(the game's segment has ~44 KB free). **arenagen refuses** a graph with an
unreachable node, a leg no walker can walk, or a tall box off the grid.

### 3.2 Picking a branch

At the end of a leg, a bot picks its next leg by its STATE (4.4):

| state | picks |
|---|---|
| roam | a random leg, not the one it came by (unless it is a dead end) |
| hunt | the next hop toward the node nearest where it last saw the player (the nearest-node table, then the next-hop table: two lookups) |
| engage | it keeps walking its leg - a moving target is harder to hit - and turns to face the player |
| fetch | the next hop toward a pickup's node (health when low, a weapon spawn when it has only the pistol) |

**Cost: two table reads a leg** (Forecast: under 200 clk, a few times a
second).

### 3.3 Weapons for bots

A bot walking over a pickup's node takes it as the player does
(`wa_pktake`'s checks, against the bot's own health, shield and arms). A bot
fires its best weapon for the range: the shotgun close, a projectile far.
Projectiles fly through the existing code; they need an OWNER, so a rocket
does not hurt the bot that fired it. Wave 4.

### 3.4 Bots on lifts

`wa_ltick` counts a rider who is the player. It will count any figure
standing on the lift (four compares a figure a tick). A leg that ends on a
lift is a WAIT: the bot stands until the lift is up, then walks off on the
leg that leaves it. The bot's floor is read on that node (bit 15), so it
rides as the player does. This is HEIGHTS-PLAN wave 4's remainder.

## 4. Seeing, turning, shooting

### 4.1 Line of sight: a grid walk, every fourth tick

The tall boxes are the only occluders, and they all stand on a 64-unit grid
(arena 2's 7 tall boxes do; arenagen will refuse one that does not). So a
bot sees the player when a walk from it to the player, a 64-unit step at a
time, enters no tall cell.

**Measured on the host** (`arena 2`, 20,000 random pairs of free floor
points, against exact segment-against-box tests):

| step | wrong | of which "sees through" | steps: mean / 95% / max |
|---|---|---|---|
| **64 (a cell)** | **1.81%** | all of them | **11.3** / 23 / 31 |
| 32 | 0.92% | all of them | 21.8 / 46 / 62 |
| 16 | 0.45% | all of them | 42.9 / 91 / 124 |

It is never wrong the other way: a clear line is never called blocked. The
errors are lines that graze a wall's corner within a few units. Sees
through a corner's tip, a bot can shoot the player round it by a hair.
**Recommended: 64.**

**Cost** (Derived): a step is a fixed-point add on each axis and a bit
test, ~70 clk on the 8088: ~800 clk a check on average. Staggered, each
bot checks every fourth tick: **~200 clk a bot a tick**.

Low boxes (platforms, ramps) do not block a bot's sight. Heights matter
only through the tall boxes, as in the renderer's PVS (HEIGHTS-PLAN 9.8.2).
A bot also notices the player only within 90 degrees of its facing, unless
it is already hunting or engaging (one dot product's sign).

### 4.2 Turning to face: a cross product's sign

An engaging bot turns toward the player by up to 48 a tick (`wa_figtick`'s
turn rate). The direction is the sign of `dx sin - dy cos` at its facing,
two multiplies. Its facing is where it shoots: no arctangent anywhere. A
bot turns while walking its leg (its body faces the player, its legs carry
it on), which the animation already allows.

**Cost**: ~300 clk a tick per engaging bot (Derived).

### 4.3 Shooting: a reaction, a gap, a roll

| | easy | normal | hard |
|---|---|---|---|
| reaction (from first sight to the first shot) | 24 ticks (0.8 s) | 15 (0.5 s) | 9 (0.3 s) |
| accuracy at 4 m, standing target | 45% | 60% | 75% |
| ...falls by | 5% a further 4 m, and a quarter more if the player is moving | | |

- A shot fires once the bot is facing the player within a few degrees,
  past its reaction and its weapon's gap.
- **A hit is a dice roll** against that accuracy (the weapon spawns' LCG).
  The weapon's damage goes to the player through `wa_phurt`, which already
  takes the shield first.
- No ray, no TRACE: line of sight said the player is visible.
- A projectile is launched along the bot's facing, and hits or misses by
  flying.

**The player must SEE it coming:**

- The firing bot's figure draws yellow for two ticks: `wa_figure` already
  picks an attribute by `F_FLASH`; a flag picks `A_CROSS`'s yellow. That
  is one byte test a figure.
- Each weapon's tone, as the player's.
- A hit on the player flashes the HUD's heart and plays a low tone.

**Cost**: a few compares a tick, and a roll a shot (Forecast: under 100
clk).

### 4.4 States

| state | enters when | leaves when |
|---|---|---|
| roam | it spawns; it lost the player 5 s ago | it sees the player (hunt or engage) |
| engage | it sees the player | it loses sight (hunt) |
| hunt | it lost sight | it sees the player (engage); 5 s pass (roam) |
| fetch | its health is under 40, or it has only the pistol and a spawn is near | it has the pickup, or it sees the player |

A byte a bot, and one switch at the leg's end or on a sight change.

### 4.5 What it costs, in all

| | a bot a tick | 3 bots, a frame at ~15 fps (2 ticks) |
|---|---|---|
| walking its route (today's patrol, Measured) | ~780 clk | (already paid today) |
| line of sight, every fourth tick | ~200 | ~1.2k |
| facing an engaged target | ~300 (only while engaging) | up to ~1.8k |
| states, branches, shots, rolls | ~100 | ~0.6k |
| **added** | | **~2–4k clk: 0.4–0.8 ms, 1–2% of a frame** (Forecast) |

The renderer pays nothing new but the firing cue's byte test. A bench row
will measure it on the P bench with the bots running, against the dummies.

## 5. Death, respawn, the score

- **The player dies at 0.** The view tips to the floor: the eye drops
  over half a second, nothing is drawn differently. Then a **respawn timer**
  (3 s, its count on the HUD) and a **respawn point**.
- **Respawn points**: a few per arena, from arenagen. The game takes the one
  farthest (by the sum of the axis distances) from the nearest live bot:
  four compares a point, at a respawn.
- **Bots respawn the same way**, at a respawn point's nearest node, no
  longer at their patrol's start.
- **The score**: kills and deaths per player and per bot. A kill is
  credited to whoever fired the shot or the projectile (projectiles carry
  an owner, 3.3).
- **The scoreboard, while Tab is held**: an overlay box of names, kills and
  deaths, built once when Tab goes down. Two ways to draw it (question 2):
  - over the live view: up to ~100 overlay cells, ~2 ms a frame while held
    (Derived from WEAPONS-PLAN 3.3's overlay cost);
  - in place of the view: free while held, and a full redraw when it is
    let go.
- **40/80 columns move to - and +**, as Clear Skies sizes its view, and Tab
  is the scoreboard's.
- **A match's end** (a kill limit, or a time) is the game modes' (after the
  network waves), not this plan's.

## 6. Waves

Each ends with its outcome on the glass and its rows named; the soak union
and `test-full` run once after the last (CLAUDE.md).

| wave | builds | outcome | checked by |
|---|---|---|---|
| **B1: routes** | the route graph, next hop, nearest node (arenagen and its checks); bots walking it with ROAM's random branches; bots on the lift | the dummies wander the whole arena, ride the lift to the tower | arenagen's refusals; a soak row: every leg walked by some bot within N minutes of sim, the lift ridden, no figure ever inside a wall |
| **B2: seeing and shooting** | the tall grid and the sight walk; facing; ENGAGE and HUNT; reaction, gap, accuracy; the firing cue; hits on the player | the bots turn, shoot back, and hit at the difficulty's rate | a soak row: a staged duel per difficulty, hits counted against the expected rate within a bound; sight against the host's exact test on sampled poses |
| **B3: death and the score** | the player's death and respawn timer, respawn points, bots' respawns, kills and deaths, Tab's scoreboard, - and + | a match that goes on: die, wait, respawn, the score on Tab | a soak row: deaths, respawn points chosen away from bots, the score's counts |
| **B4: bots' arms** | FETCH; bots taking pickups; bots firing every weapon by range; projectiles' owners | bots that pick up the rocket launcher and use it | the row's duel with each weapon |

Measured at the end of each wave, as the weapons were: the P bench with bots
against dummies, and the heights poses.

## 7. Questions for the owner

1. **Line of sight's step**: 64 (1.8% corner grazes seen through, ~800 clk a
   check) or 32 (0.9%, twice the cost)? Recommended: 64.
2. **The scoreboard**: over the live view (~2 ms a frame while Tab is held)
   or in place of the view (free while held)? Recommended: over the view -
   in a fight, holding Tab should not blind you.
3. **Difficulty**: chosen how? Recommended: three items on the Game menu
   (Easy, Normal, Hard), remembered for the session.
4. **How many bots**: today's three figures (the PARTS-PLAN ruling: at most
   three). Keep three for bots-only play, and later share them between bots
   and remote players?
5. **The bots' names** on the scoreboard: fixed (Bot 1-3), or a short list
   of names?

### 7.1 The owner's answers (2026-11-14)

1. **64** - "slightly seeing around corners is not a big issue".
2. **Over the view** - try it, and see whether it is both readable and
   performant.
3. **The Game menu**, yes - though the menu "will need a lot of work in
   general before we go live (match setup)".
4. **Three, shared** with remote players. More might be a 286+ thing later,
   if it is easy.
5. **A short list of robotic names.**

## 8. As built

### 8.1 B1: routes, and bots on the lift (2026-11-14)

**The graph** (`tools/arenagen.py`: `graph_of`, `graph_edges`,
`graph_block`). The Heights arena's is laid by hand (`HEIGHTS_GRAPH`):

- 18 nodes, 27 legs, 51 one-way edges;
- its three old patrol loops, unchanged, as the bots' HOME loops: over the
  ramps (split at the platform's middle, the shotgun spawn), the annex's
  hallways and corridor (through the health pack), and round it all;
- seven legs between the loops;
- the lift: a leg onto it at rest (`LIFT_ON`), one off it raised onto the
  tower (`LIFT_UP`, through the rocket spawn), and a DROP off the tower's
  west face.

The flat arenas' graphs are PATHS' three loops joined by four legs
(`PATH_LINKS`): 14 nodes, 36 edges.

arenagen refuses a leg that runs into a wall or climbs more than a step (a
drop may fall any height), a node with more than four ways out, a node that
cannot reach every other, and a home loop that is not walkable. The checks
replace the patrols' own.

**The bytes**: the graph rides in the arena's part (descriptor words 38 and
40, where its patrols were): 762 bytes for arena 2, 550 for the flat ones.
The game copies it straight out of the part at load, into `wa_gph`
(`WA_GPHSZ`). The renderer never sees it, so the patrols' block is gone from
ARENA in both halves.

**The walk** (`wirearena.asm`):

- a figure's `F_PATH` names the edges and `F_LEG` its edge, x 12;
- an edge's first 8 bytes are a patrol leg's row, so `wa_figtick` walks an
  edge as it walked a leg;
- at an edge's end, `wa_bnext` takes the node's next edge: at random, any
  but the way back (the way back from a dead end);
- in a bench (`wa_bdet`) it takes the node's FIRST edge, its home loop's
  next, so the benches' dummies walk their old patrols exactly. The graph
  puts each loop's own leg first.

**The lift**: an edge onto it waits at its start (`F_BWAIT` 1) for the lift
at rest. One off it waits ON it (`F_BWAIT` 2), and a waiting bot counts as
a rider (`wa_lbn`, read by `wa_ltick` the next tick). So the lift rises
under the bot, and the bot walks off at the top. While waiting, its floor
is read every tick, so it rides up with the lift.

**`F_SIZE` is 56** (the bots' bytes, 44–55, the game's alone; `WR_ABI` 6).

**Checked**: `tests/waroutes.py`, a soak row (~45 s).

- **Two minutes of roaming**: every bot left its home loop, 50 of 51 edges
  were walked, no figure stood in a tall box, and on every climbing edge
  every figure stood on its floor.
- **Bot 0 at the lift's foot**: it waited, rode to 160, walked onto the
  tower, dropped off, and the lift went home.
- **Red** with the branch never taken (4 checks) or the bot not counted as
  a rider (2).
- `waweapons` now stands the bots on their home loops: it is about the
  weapons.

**Speed**: the benches as before within 0.3 ms (P 20.1 / 16.7; heights 40
13.2 / 14.9 / 33.0 / 12.5 / 26.0). The benches walk the home loops, so
their scenes are the same; the cost is a call at each edge's end and a byte
test a figure a tick.
