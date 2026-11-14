# Bounce Bonanza: gate 1 notes for the owner

You play wave 6 at gate 1 (SPEC.md 128.16.11), before the physics freezes.
The story list is in [BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md),
story 6.11. This page says what to try, what each number does and how to
ask for a change. Every figure here comes from wave 6's final pass
(2026-11-14). A figure marked MEASURED was taken on MartyPC's 5150s. A figure
marked MODEL was computed on the host by `bbcourse.py`, using the same
physics as the guest, integer for integer.

## The disk

Use `bonanza360.img` (or `bonanza.img`) in B: with the system disk in A:.
BONANZA opens on FIRST. Press `N` five times to reach **PLAY**,
"Playground", then `Enter`. Its demo is `V` six times, then `R`.

Keys are the same for every ball:

| key | does |
|---|---|
| arrows | roll the ball (two arrows at once make a chord) |
| `Space` | Hop. With rubber, press it again just before the Hop lands for the BOOST |
| `Left Shift` | Grip (brake) |
| `Backspace` | return to the last flag, or to the start |
| `C` | camera: GLIDE or TRICKLE |
| `Esc` | back to the face |

## The PLAYGROUND, left to right

- **The apron.** A level floor 4 units up. All the rungs and gaps start
  from it, each with 6 tiles of run-up.
- **The step ladder.** Behind the apron stand four rungs, each 3 tiles
  wide. From left to right they are **1.5 units, 1 unit, half a unit and
  2 units** high. Every rung is a dead end: 4 tiles of void separate each
  rung from the next.
- **The mat.** A bounce mat at the apron's left end, level with it. A Hop
  that lands on the mat never boosts.
- **The gap ladder.** Three notches are cut into the apron's front edge,
  **1, 2 and 3 tiles** wide. Each crosses to the far floor at the same level.
- **The far floor.** It holds three pads, one for each ball, and the goal.
- **The brake strip.** It starts off the apron's front right. Its run-up
  has three lanes: ice, normal and sand. Then 3 tiles of normal floor end
  at a pit over a deep basin. Overrun the strip and you fall. Steel needs
  2.9 of the 3 tiles to stop (MODEL), so press Grip early with steel.
- **CGA palette 0.** The PLAYGROUND is the only course on palette 0
  (green, red and yellow). Every other course is on palette 1, as before.

A ball that drops off the brake strip's sides or over the far floor's rail
lands in the basin, which is a dead end. Press `Backspace` to get back.

## What to try, the known questions first

1. **Glass's grip is inverted.** Glass's own drag (`K` 5) does most of its
   braking. Without Shift, glass coasts 2.8 tiles where rubber coasts 5.4.
   With Grip, glass stops in 1.7 tiles and rubber in 1.5. On one arrow
   glass is the slowest ball: its top speed is 186. The end goal says
   "light and fast, very little braking grip". The lever is glass's `K`.
   At 6, glass tops 378 on one arrow, coasts 5.4 tiles and stops with Grip
   in 2.6 (MODEL).
2. **Every ball is faster on one arrow.** One-arrow top speeds went from
   189 to 252 for rubber, 155 to 186 for glass, and 255 to 384 (the cap)
   for steel. "Sluggish" steel now reaches its top on one arrow. The lever
   is steel's `K`. At 7, steel tops about 254 and coasts 9.9 tiles instead
   of 16.0 (MODEL).
3. **The Grip chain.** Hop, boost, hold Grip through the boost's landing,
   then press Space again. The second boost comes 73 steps (1.3 s) after
   the first Hop, and the cycle repeats about once a second (52 steps Hop
   to Hop), with no rolling between. Is that "a flying ball"?
4. **The two-tile gap is easy for rubber.** A Hop and its boost cross it
   from 19 take-off points. Try the 2-tile notch.
5. **Three tiles onto a LOWER floor is a known conflict.** Nobody crosses
   three tiles on the level, the boost included; the build asserts that.
   Onto a lower floor, rubber's Hop and boost do cross three tiles:

   | far floor | rubber's Hop and boost | rubber's Hop alone | glass's Hop |
   |---|---|---|---|
   | half a unit down | 2 | 0 | 0 |
   | 1 unit down | 4 | 0 | 0 |
   | 1.5 units down | 7 | 0 | 0 |
   | 2 units down | 13 | 2 | 0 |
   | 3 units down | 22 | 7 | 4 |

   Each figure is a count of take-off points (MODEL). No `BOOST` that still
   climbs the 1.5-unit ledge stops the half-unit crossing. MILL has two such
   gaps, both at wx 10: wy 12 is half a unit down and wy 13 is 2 units
   down. Each could be a new shortcut, so try them. The decision is yours:
   a course rule, or let it stand.
6. **Each ball on each rung.** Expected results:
   - half a unit: every ball rolls up;
   - 1 unit: rubber's Hop and glass's (glass's window is narrow), never steel;
   - 1.5 units: rubber's Hop with the boost only;
   - 2 units: nobody.
7. **The boost onto the 1.5-unit ledge.** Hop toward the leftmost rung,
   then press Space again just before the landing. Then try the 2-unit
   rung, which the boost cannot take.
8. **Grip on the brake strip.** Try each ball on each lane (ice, normal,
   sand). On ice the brakes are now 2, 1 and 1 (rubber, steel, glass).
9. **Top speeds on the apron.** One arrow, then a chord, for each ball.
10. **The boost's cue.** A sound and a 4-step STRETCH frame. Rubber's boost
    sound is a first pass, a rising slide. Judge both by feel.
11. **The camera.** Try GLIDE and TRICKLE (`C`) through the bounce chain.
    A bounce or a boost should no longer bob the view up and down: the
    camera follows the ground line now.
12. **Smoothness on MILL and PEAK with the CGA.** The rate held: every
    figure is inside +1 missed refresh a second of 5b's. The missed frames
    now come in long half-rate stretches, though, up to 43 frames (about
    1.4 s at 30 Hz) on PEAK. Play MILL and PEAK on the CGA and say whether
    it stays smooth. The figures are below.

## The ladders (MODEL, printed by `bbcourse.py --selfcheck` item 7)

The approach is 70 take-off points, 1.5 gu apart, at the cap with a chord.
A number is how many of those points make it, with the window in ms.

**The step ladder** (how high a ball climbs from level ground):

| step | rubber's Hop | rubber's Hop and boost | glass's Hop | steel's Hop |
|---|---|---|---|---|
| half a unit | rolls up | 66 (1,208 ms) | rolls up | rolls up |
| 1 unit | 7 (128 ms) | 29 (531 ms) | 3 (55 ms) | none |
| 1.5 units | none | 7 (128 ms) | none | none |
| 2 units | none | none | none | none |

**The gap ladder** (level unless it says otherwise):

| gap | rubber's Hop | rubber's Hop and boost | glass's Hop | steel's Hop |
|---|---|---|---|---|
| 1 tile | 30 (549 ms) | 42 (769 ms) | 12 (220 ms) | 7 (128 ms) |
| 2 tiles | 4 (73 ms) | 19 (348 ms) | 2 (37 ms) | none |
| 2 tiles, half a unit down | 10 | 28 | 5 | 1 |
| 3 tiles | none | none | none | none |

Lower floors are in the table under question 5.

**The up-ramp distance** (from the ramp's lip back to the ball's launch
height): rubber 6 tiles, glass 5, steel 5, a ball with no Hop 4.

**The material table** (MODEL, on normal ground). Each figure is a speed in
1/256 px a step; the cap is 384.

| | rubber | steel | glass |
|---|---|---|---|
| chord: steps to 300, and its top | 62, 384 | 104, 384 | 56, 372 |
| one arrow's top (from rest and from above) | 252 | 384 | 186 |
| coast from 384: steps, tiles | 178, 5.4 | 360, 16.0 | 110, 2.8 |
| Grip from 384: steps, tiles | 36, 1.5 | 64, 2.9 | 50, 1.7 |
| Hop: its apex | 252: 5.7 px | 160: 2.4 px | 224: 4.5 px |
| BOOST: its apex | 350: 9.3 px | none | none |

## What each tunable does

Each tunable is one field of `MATERIALS` in `tools/bbcourse.py`, except the
palette, which is one line in a course file. Nothing else is edited.

| tunable | now | what it changes | limits |
|---|---|---|---|
| `HOP` (rubber, steel, glass) | 252, 160, 224 | how high a Hop rises from the ground, and with it the 1-unit rung and the gaps | rubber above 252 refuses MOON at the occluder bound, so it needs MOON's retrofit (wave 13): a design conversation, not a retune. 240 - 248 refuse PEAK |
| `BOOST` (rubber) | 350 | the boost's apex: 9.3 px, the 1.5-unit ledge | 332 - 358 climb 1.5 units. 330 and below climb nothing. 366 crosses three tiles on the level. Every value that climbs 1.5 units crosses the half-unit-down 3-tile gap (question 5) |
| `GRIP` (rubber, steel, glass) | 8, 5, 3 | Shift's brake on each axis, per step. The ice brakes follow it (2, 1, 1) | none |
| `K`, the drag shift | 6, 8, 5 | the top speed on one arrow and how far a ball coasts. Raising it means faster and longer | glass at 6: 378 on one arrow. Steel at 7: about 254. Raising `K` raises that ball's camera pans on every course |
| `ACC` | 4, 2, 6 | how hard an arrow pushes: medium, slow, fast | none |
| `palette 0\|1 [dim] [ground N]` | PLAY 0, others 1 | a course's CGA colours. Cosmetic: no identity moves, no best is cleared | the Hercules has none |

## How to ask for a retune

Write the change in plain words. For example: "glass `K` 6, rubber `BOOST`
340, PLAY on palette 1". Then the session does the following:

1. Runs `python3 tools/bbcourse.py --tune HOP=r,s,g BOOST=b ...` with your
   values. It writes nothing. It prints:
   - whether every course still compiles under the occluder bound;
   - both ladders under the new values;
   - every route proof and every authored script, each passed or failed.

   If a value breaks a route, that route's `way` lines or script are edited
   too. That moves the course's identity and clears its best, and the
   commit says so.
2. Makes ONE constants commit:
   - the tool regenerates the generated include, the parts and the route
     demos;
   - `bbcourse.py author` rewrites the demos for MOON, PEAK and PLAY;
   - `BZ_PHYSV` moves, and the old value joins `PHYSV_SHIPPED`;
   - every best time in `BONANZA.DAT` is cleared (+5).

   Then it reruns the rows the build moved. A palette-only edit reruns
   `bonanzaexit` alone.
3. Sends you a new playtest disk. A second round of play is your call; each
   round is one more such commit.

When you are happy, the FREEZE commit marks the material table, `BOOST`
and the step's rules as binding. It takes the re-baseline (SPEC.md
128.16.10): 108 runs, six a configuration for MILL and PEAK. It also
records your review of O3, O6, O14, O15, O17 and O45. After that, your own
demo recordings replace the authored ones.

## Smoothness, MEASURED in this pass

These are missed refreshes per second of play through `D`, speaker ON, from
one run each. 5b's figures are 128.15.5.4's: six runs, speaker ON, the
build that shipped.

| demo | CGA, 5b | CGA, wave 6 | Hercules, 5b | Hercules, wave 6 |
|---|---|---|---|---|
| MILL | 8.52 (49 columns) / 12.48 (84 - 88) | **8.90** (108 columns) | 2.46 | **1.68** |
| PEAK | 8.07 | **8.76** | 2.87 | **3.24** |
| PLAY | - | 0.48 | - | 0.07 |

MILL on the CGA now pans 108 columns, so it plays in 5b's HIGH camera mode
every time. Its rate, 8.90 a second, sits between 5b's two modes and below
5b's high mode (12.48). PEAK is up 0.69 a second on the CGA and 0.37 on the
Hercules. Both are within the +1 a second that 128.16.15 set, but they come
from one run each against 5b's six.

**What changed is how the misses fall.** No frame was held more than two
refreshes on any demo, on either card. But the missed frames now come in
runs, where 5b's were scattered. Speaker ON:

| | runs of two or more missed frames | the longest run |
|---|---|---|
| CGA MILL | 15 (5b: 1) | 33 (5b: 13) |
| CGA PEAK | 45 (5b: 2) | 43 (5b: 13) |
| Hercules MILL | 4 (5b: 1) | 11 (5b: 10 - 11) |
| Hercules PEAK | 16 (5b: 2) | 24 (5b: 10 - 11) |

A run is a stretch at half rate (30 Hz on the CGA), not a hitch. The likely
cause, not yet separated by a measurement: the faster balls pan more, and a
missed frame makes the camera step further on the next frame. If it does
not feel smooth, the levers are each ball's `K` and `ACC`: slower cruising
means fewer pans. The re-baseline at the freeze takes six runs a
configuration for MILL and PEAK, and those are the figures wave 10 is held
to.
