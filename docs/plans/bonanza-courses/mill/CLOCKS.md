# WINDMILL LANE: clock options (2026-11-21, for the owner to pick)

**PICKED (2026-11-23): B, `vase`.** The owner chose the tulip vase to try in the game. It is now the tool's
`vases`, `vasem`, `vaset` and `vasef` (SPEC.md 137.18.5.2, `_clock_vase`): MILL has FOUR clocks since the owner's
builder edits, so a fourth frame and a fourth flower (a FLAMED tulip) were added; [MILL.md](../MILL.md) section 8.
What follows is the study as it stood.

*Course 4's DRAFT ([MILL.md](../MILL.md), [mill.bbc](../../../../apps/bonanza/courses/mill.bbc), the scratch `mill-draft.bbc` until it shipped, SPEC.md 137.54.10) has three clocks, all in the
default `crystal` frame: the START on the tee's front-left corner (7, 13), the TURNTABLE on a low pillar east of S
(34, 36), and the FINISH on the sandpit's front-left corner (22, 55), by the cup. Four concepts follow. Each is
one object with a variant for each position. The brief is the course guide's G23 ([README.md](../README.md)
1.5): the digits fit into the art, a window is allowed but not required, there are no flat squares, and
(the owner, at DOWN) "something on the clock represents where this is in the course". Here the three positions are
the TEE, a QUARTER TURN and the CUP. DOWNHILL DECISION's [clock study](../down/CLOCKS.md) is the precedent and the
method. Nothing here changes `apps/bonanza/courses/mill.bbc`, `mill/sketch.py` or `tools/bbcourse.py`.*

## How to look at them

| file | what |
|---|---|
| [clocks/overview-cga.png](clocks/overview-cga.png), [clocks/overview-herc.png](clocks/overview-herc.png) | one row per position (start, turntable, finish) and one column per concept, each captioned: `crystal` today, then `mill` with its round-2 variations `body` and `side`, `wheel` with `hub` and `post`, then `vase` and `flag`. Each crop is from the draft's real compiled picture, with "47" put into the digits' blocks the way the lanes would |
| `clocks/<concept>.png` | one concept at its three positions in a wider crop, CGA on the left and Hercules on the right |
| [clocks/frames.png](clocks/frames.png), [clocks/frames2.png](clocks/frames2.png) | every frame on a plain block, zoomed, no compile. Rows are CGA then Hercules, one pair per concept: round 1's (mill, vase, flag, wheel), then round 2's (body, side, hub, post) |
| `clocks/<concept>.txt` | the compile's sizes for that concept (the table below) |
| `clocks/mill-<concept>.bbc` | the scratch course: the draft with the three `frame`s |

The frames are in `clocks/frames.py` (round 2's in `clocks/frames2.py`, which `frames.py` pulls in), drawn with the tool's own `_ClockArt` round `clock_face_geom`'s digits'
blocks. `frames.install(B)` adds them to `bbcourse`'s styles **in its own process only**. `clocks/sheet.py`
compiles each scratch course with them installed (about 2 min 40 s each, one process per concept), and
`sheet.py --render` / `--overview` redraw the pictures from the compiles' cache in seconds. The cache
(`clocks/cache/`) is not committed. `clocks/preview.py OUT.png [CONCEPT ...]` draws `frames.png` / `frames2.png`
without a compile.
`clocks/outline.py` gives a frame's width, the blocks it touches and how many it covers only partly.

## The options

All four use the course's inks: palette 1 (cyan, magenta and white on black; MILL names no palette). On the
Hercules, cyan and magenta are one grey checker, so white and black carry every form. **All four put the digits on
WHITE.**

### A. `mill`: a little smock WINDMILL, the digits on its gallery

A tapering eight-sided tower (a white rim of light, magenta, the right faces' dither, black facet lines) with an
arched door at its foot. A white GALLERY round the tower carries the digits. Above it are a boat cap, a hub and
four lattice sails. The cross is drawn a little turned (its X is flatter than square), which keeps the lower sails
clear of the digits. This follows the course designer's suggestion: *"whole at the start, split at the turntable, a
flag pin at the finish"*.

- `mills` (start): the sails WHOLE, all four spread (magenta cloth in white lattice), with a tee'd ball at the
  door.
- `millt` (turntable): the sails SPLIT and TURNING. They are turned on from the start's, two spread and two bare,
  with white motion arcs behind their tips. The tower stands on a turntable disc painted with a quarter-turn
  arrow.
- `millf` (finish): the sails STOPPED, their cloth furled along the stocks, and a FLAG PIN flying from the cap.

It is the most on-theme of the four, and the tallest (about 25 px over the crystal's top).

### B. `vase`: a DELFT TULIP VASE on a pedestal, the digits on its belly

A Delftware vase on a short lit pedestal: white glaze, a cyan (Delft blue) band and flutes at the shoulder and
foot, the shade dithered cyan down its right. A fine cyan line frames the digits on the white belly. TULIPS on cyan
stems come out of the neck, with magenta heads lit white. The bulbs GROW down the course:

- `vases` (start): ONE closed bud with a leaf, and a tee'd ball at the pedestal's foot.
- `vaset` (turntable): TWO, a bud and one OPENING, with the pedestal on the turntable disc.
- `vasef` (finish): THREE in full BLOOM.

It is the Dutch side of the theme rather than the minigolf side. The tulips are small: 8 px heads, which read on
the CGA and are thinner on the Hercules.

### C. `flag`: the HOLE FLAG, the digits on its cloth

The minigolf flag, but with the digits ON THE CLOTH. (First Roll's `pin` hangs a plate on its pole, so this is
not a copy of it.) A banded pole with a knob carries a big white flag, black-edged, its free end rippling. The
flag's magenta FLY carries a little white WINDMILL emblem whose sails show the position:

- `flags` (start): the pole beside the tee's two MARKERS, painted flat on the tile. The emblem's sails are an X.
- `flagt` (turntable): the flag flies the OTHER way, a quarter turn round (to the left), and the emblem's sails
  are a +. A turntable disc with its arrow is painted on the tile.
- `flagf` (finish): the pole in the CUP, with a ball at its lip and sand dithered round the hole. The sails are an
  X.

**Bent to fit:** the first `flags` had a tee'd ball (geometry) by the pole. It was REFUSED: *"block (row 22,
column 71) has 5 occluder records, over 4"*. That block is the tee's crowded corner by the guard rail. The tee
markers are now paint on the tile. Because the digits are centred over the tile and the pole stands at the cloth's
edge, **the pole stands near the tile's left corner**, not in its middle (see *Moving the digits*).

### D. `wheel`: the windmill's SAIL CROSS on a post, the digits on its hub

The mill's head alone, as a garden windmill: a lit post on a collar. On the post is a round white HUB BOARD,
black-rimmed with its lower right in the dither, carrying the digits. Four lattice sails sit round it, with the cap
peeking over its top. The hub carries the digits, so the sails can stand at any angle. That makes the turn the
clearest of the four:

- `wheels` (start): an X, all four sails spread, with a tee'd ball at the foot.
- `wheelt` (turntable): TURNING, most of a quarter on from the start's X. Two sails are spread and two bare, with
  white motion arcs. The post stands on the turntable disc.
- `wheelf` (finish): an X, the sails furled, and a pennant flying from the cap.

It is the widest frame (35 - 51 px across the sails). At the start and finish, its lower sails pass behind the
guard rails in front of the clock.

## Round 2: four more round `mill` and `wheel` (2026-11-21)

The owner: *"Tulips currently works the best, we may pick it, but first: I also like wheel and mill, though neither
quite fully work. Can we get a few more variations around those two?"*

### What fails in `mill` and `wheel` (read off the round-1 sheets first)

- **`mill`'s gallery reads as a SIGN PLATE.** A white rectangle wider than the tower, at the top, with the digits
  on it: at this size it is the crystal's plate on a stick again, not a gallery round a tower.
- **`mill`'s sails read as RABBIT EARS.** The lower two stop where they would meet the digits, so only the upper
  V shows, small and squashed above the plate. At the turntable the magenta cloth sits on S's magenta pillar wall
  and the cross all but vanishes; on the Hercules both are one grey checker.
- **`mill` is tall and narrow.** The tower under the plate is a thin magenta column (a grey stripe on the
  Hercules) and the whole thing stands about 25 px over the crystal's top.
- **`wheel`'s hub reads as an EGG**, i.e. the crystal's oval sign with sticks round it.
- **`wheel`'s lattice sails are thin.** At 45 degrees they cross the guard rail in front at the start and finish,
  where the rail's white bars and the lattice's white bars merge. At the turntable the two "bare" sails are open
  lattice over a magenta wall: noise, not a sail. On the Hercules the magenta cloth is the same grey as the wall.
- **Both cost about +30 blocks** of the draft's 44.
- **What works:** the digits on WHITE read everywhere (both cards), the turntable disc and the tee'd ball read,
  and the idea of a sail cross that turns down the course is liked.

Round 2 shares one change to the SAIL (`frames2._vane`): a 3 px stock with a white heart and a broad blade edged
all round in black, so it holds its silhouette on black, on magenta and on the Hercules. The position marks are
round 1's: a tee'd ball at the START, the turntable disc and white motion arcs at the TURNTABLE, a flag at the
FINISH.

### E. `body`: a squat whitewashed mill, its BODY the digits' window (fixes `mill`)

The tower itself is WHITE (whitewashed, black facet lines that stop short of the digits, the right faces dithered
cyan, a magenta brick plinth, an arched door) and the digits sit ON it: no plate. A boat cap sits right on the
digits' top, so the mill is lower than `mill` by the gallery's height. The cross is big (27 px sails) and seen a
little from below (a flat X), so its lower sails pass the digits' corners and run down in front of the tower; a
sail that would cross the digits goes behind the tower instead.

- `bodys`: an X, the cloth spread, a tee'd ball by the door. `bodyt`: turned on, arcs, on the disc. `bodyf`: an X,
  furled, a flag pin on the cap.
- **Reads:** the tower is now unmistakably a mill (white body, door, cap), on both cards. **Still weak:** the flat
  X reads a little like a rotor, and at the turntable the turned cross over the cap is busy.
- **With the digits moved UP a block row:** the digits on the cap's face, the tower slimmer under them, the cross
  square.

### F. `side`: the mill seen from the SIDE, its sails a tall slim X off its left (fixes `mill`)

The same white tower, turned a quarter: the cap is a long boat with its windshaft poking out LEFT, and the sails
face screen-left, foreshortened to a tall slim X standing off the cap's nose. The cross never meets the digits at
any angle, so nothing is clipped. **The strongest silhouette of the eight on both cards** (the textbook
"windmill" outline), and the cheapest of the sail options in blocks.

- `sides`: an X, the cloth spread, a tee'd ball. `sidet`: a + (one sail up, one down, two end-on), arcs, on the
  disc. `sidef`: an X, furled, a flag pin at the cap's tail.
- **Still weak:** `sidet`'s + is less clearly "turned" than the X; its end-on sails are short stubs. The frame
  reaches about 20 px left of the tile's centre.
- **With the digits moved:** RIGHT half a block would centre the tower-plus-sails on the tile (today the cross
  hangs off the left).

### G. `hub`: `wheel` with four BROAD white sails and a big round hub plate (fixes `wheel`)

The hub is a ROUND plate (a magenta rim ring between black lines round the white field), no cap; the sails are
broad WHITE blades with black bars, which read on black, on the magenta wall and on the Hercules alike. The cross
is UPRIGHT (a +) at the start, so the lower sail runs down along the post instead of across the rail.

- `hubs`: a + (the cross at rest), a tee'd ball. `hubt`: turned 30 degrees, arcs, on the disc. `hubf`: an X
  (stopped), furled, a flag pin on the plate.
- **Reads:** the turntable is the clearest turn of all eight (white blades on the magenta wall). **Still weak:**
  the most expensive (+38 blocks: only 6 left), and the furled X at the finish still crosses the rail.
- **With the digits moved UP a row:** the lower sails clear of the rail at the start and finish.

### H. `post`: the CHEAP one, a pinwheel + on a post (fixes `wheel`'s cost)

Built for the block pool: an upright +, its stocks on the digits' own block columns, its blades rectangles on
ALTERNATE quadrants (a pinwheel), white bars every 4 px so an arm's inside repeats block for block. `hub`'s round
plate carries the digits.

- `posts`: the cloth spread one way round, a tee'd ball. `postt`: the blades on the OTHER quadrants (the wheel seen
  turning), arcs between the arms, on the disc. `postf`: the cloth taken in, bare stocks, a flag pin on the top
  arm.
- **Saved less than hoped:** +22 blocks, against `wheel`'s +30. The arms are on the grid, but the plate, the arcs
  and the tee are not, and each arm's ends still need their own blocks. **Still weak:** the blades are small (6
  px), and at this size the pinwheel reads more as a road sign than as sails.
- **With the digits moved:** UP a row lifts the down arm clear of the rail; this one gains least, being cheap by
  construction rather than by placement.

### Round 2's bytes (MEASURED on this commit's `mill-draft.bbc`, against `crystal`'s 980 / 185 / 55,610 / 18,564 / 15,497)

| concept | picture blocks (of 1,024) | occluder masks (of 256) | part in RAM | on disk LZ4 / LZB | against `crystal` | blocks left |
|---|---|---|---|---|---|---|
| `post` | **1,002 (+22)** | 214 (+29) | 56,604 (+994) | 19,379 / 16,180 | +815 B LZ4, +683 LZB | 22 |
| `side` | **1,008 (+28)** | 225 (+40) | 56,970 (+1,360) | 19,779 / 16,511 | +1,215 B LZ4, +1,014 LZB | 16 |
| `body` | **1,011 (+31)** | 221 (+36) | 56,934 (+1,324) | 19,685 / 16,464 | +1,121 B LZ4, +967 LZB | 13 |
| `hub` | **1,018 (+38)** | 236 (+51) | 57,280 (+1,670) | 19,793 / 16,531 | +1,229 B LZ4, +1,034 LZB | 6 |

All four compile (no refusal, all pass 137.18.5.4's one-ball-length check). For comparison: `mill` +31, `wheel`
+30, `vase` +10, `flag` -7. **No sail design here comes close to `vase` in cost**: the sails are diagonals and
detail at the 8 px grid's scale, which is what the block pool pays for. The cheapest sail is still twice `vase`.
`frames2.py`'s functions are 32 - 49 lines each, plus about 100 lines of shared helpers (`_vane`, `_smock`,
`_plate`, ...), if one is lifted into the tool.

### Pick list, if one of these

- **`side`** for the best windmill silhouette on both cards at moderate cost.
- **`hub`** for the clearest turn, if the blocks can be found (or once the block limit is raised).
- **`body`** if the mill should face the player; it needs the digit offset to be at its best.
- **`post`** only if blocks decide it.

## The bytes, round 1 (MEASURED: each concept compiled at this commit's `mill-draft.bbc`)

MILL is ONE part (not sheeted). The blocks are the binding limit: **the draft is at 980 of 1,024**, with 44 to
spare. The world part does not move. On-disk LZ4 is the picture part plus the world part, packed by
`bbcourse.packed_len`.

| concept | picture blocks (of 1,024) | occluder masks (of 256) | part in RAM | on disk LZ4 / LZB | against `crystal` | fits? |
|---|---|---|---|---|---|---|
| `crystal` (today) | 980 | 185 | 55,610 | 18,564 / 15,497 | - | - |
| `flag` | **973 (-7)** | 190 (+5) | 55,620 (+10) | 18,803 / 15,638 | **+239 B LZ4, +141 LZB** | yes: 51 blocks left, the cheapest |
| `vase` | **990 (+10)** | 205 (+20) | 56,210 (+600) | 19,285 / 16,092 | **+721 B LZ4, +595 LZB** | yes: 34 blocks left |
| `wheel` | **1,010 (+30)** | 221 (+36) | 56,878 (+1,268) | 19,659 / 16,464 | **+1,095 B LZ4, +967 LZB** | yes, but only 14 blocks left |
| `mill` | **1,011 (+31)** | 217 (+32) | 56,826 (+1,216) | 19,720 / 16,480 | **+1,156 B LZ4, +983 LZB** | yes, but only 13 blocks left |

- **Blocks.** Every option compiles, so every option fits today. `mill` and `wheel` take about 70% of the draft's
  remaining blocks. MILL.md's open questions 1 - 2 (a third dense screen, the bunker back, the finish rails) all
  need blocks, so choosing either one rules most of those out. `flag` is the only option that SAVES blocks,
  because its cloth is a block-aligned rectangle. `vase` costs a quarter of what the sails do.
- **Masks.** The draft has headroom here (185 of 256, against DOWN's 240). The worst option leaves 35 masks.
- **The 60 s budget's 1.5x (18,825 LZ4, reported not refused).** MILL.md quotes 19,083 LZ4 for the draft (the
  tool's own budget line). The sum here measures 18,564 for the same draft, so read the DELTA column against
  MILL.md's figure. Every option adds to the 258 bytes the draft is already over: `flag` by about 240 bytes, the
  sails by about 1,100.
- **No code, no lanes:** the digits are 137.18.5's lanes in every option. This is picture only, like every frame
  so far.

## Rules each one bends

- **G11 / 137.18.5.4 (a clock never hides the ball for more than one ball length):** all four pass the compile's
  check at all three positions.
- **G10 / G9 / G12:** the positions are unchanged, so these hold as in MILL.md 2. The turntable clock stays low, so
  `mill`'s extra height does not reach the see-saw's window. That is PREDICTED from the crop, not re-measured with
  `--guide`.
- **"No flat squares":** `flag`'s cloth is a rectangle, but it is a cloth on a pole with a rippled fly, which
  is the `pin` precedent the owner accepted. The others have no flat panel. `mill`'s gallery is a band round a
  tower.
- **What is in front of them:** the start and finish clocks stand on floor corners INSIDE the guard rails, so each
  one's foot is seen through the rail (the mill's door, the vase's pedestal, the tee). The turntable clock stands
  against S's magenta pillar wall, not the void. `crystal` has the same backgrounds today.

## Moving the digits (the digit-anchor offset another agent is adding)

Today the digits' blocks are fixed: centred over the tile and about 31 px up (`clock_face_geom`). Each design had
to build round that. With an offset at the lane grid's granularity:

- **`mill`: the biggest gain.** Moving the digits UP one or two block rows onto the cap, or onto a round board at
  the sails' hub (a real mill's "face"), would remove the gallery, which exists only to hold them. The tower
  could then be slimmer and the sails a full square cross, free of the digits at any angle. The turntable variant
  could turn a true quarter, as `wheel`'s does. It would also take blocks off: the gallery and the flattened cross
  are a good part of the +31.
- **`flag`: the second biggest.** Moving the digits RIGHT about half a block puts the pole at the tile's centre and
  the cup in the middle of the tile, instead of at its corner. Moving them UP a row puts the cloth at the pole's
  head, where a flag flies. `flagt`'s left-flying flag wants the mirror offset (left).
- **`vase`: small.** Moving the digits DOWN a row would let the tulips stand taller without making the clock any
  taller, and give the pedestal its full height.
- **`wheel`: small.** The digits are already on the hub. Moving them UP a row would lift the cross clear of the
  guard rails at the start and finish, where the lower sails now pass behind the rail.

## Tool support

None was needed to draw them. **To lift the chosen concept into the tool**, copy its function from
`clocks/frames.py` into `tools/bbcourse.py` beside `_clock_orb`:

- about 60 - 90 lines for one concept (`wheel` 58, `vase` 74, `mill` 79, `flag` 88);
- about 80 lines of shared helpers (`_sail`, `_arc_marks`, `_disc`, `_tee_peg`). `flag` and `vase` use only `_disc` and `_tee_peg`;
- its three names in `CLOCK_STYLES` and `_CLOCK_DRAW`, and a paragraph in SPEC.md 137.18.5.2;
- the sketch's three clocks naming the frames per position.

That costs 0 bytes of guest code. Until then, the scratch `.bbc` files compile only through `sheet.py`.
