# WINDMILL LANE: clock options (2026-11-21, for the owner to pick)

*Course 4's DRAFT ([MILL.md](../MILL.md), [mill-draft.bbc](mill-draft.bbc)) has three clocks, all in the
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
| [clocks/overview-cga.png](clocks/overview-cga.png), [clocks/overview-herc.png](clocks/overview-herc.png) | one row per position (start, turntable, finish) and one column per concept (`crystal` today, then mill, vase, flag, wheel). Each crop is from the draft's real compiled picture, with "47" put into the digits' blocks the way the lanes would |
| `clocks/<concept>.png` | one concept at its three positions in a wider crop, CGA on the left and Hercules on the right |
| [clocks/frames.png](clocks/frames.png) | all twelve frames on a plain block, zoomed, no compile. Rows are CGA then Hercules, one pair per concept (mill, vase, flag, wheel) |
| `clocks/<concept>.txt` | the compile's sizes for that concept (the table below) |
| `clocks/mill-<concept>.bbc` | the scratch course: the draft with the three `frame`s |

The frames are in `clocks/frames.py`, drawn with the tool's own `_ClockArt` round `clock_face_geom`'s digits'
blocks. `frames.install(B)` adds them to `bbcourse`'s styles **in its own process only**. `clocks/sheet.py`
compiles each scratch course with them installed (about 2 min 40 s each, one process per concept), and
`sheet.py --render` / `--overview` redraw the pictures from the compiles' cache in seconds. The cache
(`clocks/cache/`) is not committed. `clocks/preview.py` draws `frames.png` without a compile.
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

## The bytes (MEASURED: each concept compiled at this commit's `mill-draft.bbc`)

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
- **No code, no lanes:** the digits are 130.18.5's lanes in every option. This is picture only, like every frame
  so far.

## Rules each one bends

- **G11 / 130.18.5.4 (a clock never hides the ball for more than one ball length):** all four pass the compile's
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
- its three names in `CLOCK_STYLES` and `_CLOCK_DRAW`, and a paragraph in SPEC.md 130.18.5.2;
- the sketch's three clocks naming the frames per position.

That costs 0 bytes of guest code. Until then, the scratch `.bbc` files compile only through `sheet.py`.
