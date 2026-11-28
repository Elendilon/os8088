# DOWNHILL DECISION: clock options (2026-11-21, the owner to pick)

**THE OWNER PICKED `orb` (2026-11-21):** *"something on the clock represents where this is in the course"* -
the hub's split orb, the finishes' materials. `_clock_orb` is in `tools/bbcourse.py` now (frames `orbr`, `orbh`,
`orbs`, `orbg`, SPEC.md 137.18.5.2) and `sketch.py`'s `FRAMES` sets one a position; `frames.py`'s orb draws
through the tool's. **The PENGUIN and the WATCH are SAVED FOR A LATER COURSE** where they are, in
`clocks/frames.py` (`_clock_peng`, `_clock_watch`); the watch may need work - the owner was unsure what its
antennae are. What follows is the study as it was written, before the pick.

*Course 3's clocks are all the default `crystal` frame today (sketch.py's `CLOCKS`: start (10, 7), hub
(50, 11), steel finish (61, 43), glass finish (37, 34), each on top of the rail block it replaces). Four
concepts follow. Each one is a single object with a variant for each position. The brief is the course
guide's G23 (`../README.md` 1.5). The digits fit into the art. A window is allowed but not required. There
are no flat squares. LITTLE HOP's frog set the precedent of one object whose pose changes per use. Nothing
here changes `down.bbc`, `sketch.py` or `tools/bbcourse.py`.*

## How to look at them

| file | what |
|---|---|
| [clocks/overview-cga.png](clocks/overview-cga.png), [clocks/overview-herc.png](clocks/overview-herc.png) | one row per position (start, hub, steel finish, glass finish) and one column per concept (crystal today, sign, orb, peng, watch). Each crop comes from the course's real compiled picture, with "47" put into the digits' blocks the way the lanes would |
| `clocks/<concept>.png` | one concept at its four positions in a wider crop, CGA on the left and Hercules on the right |
| [clocks/frames.png](clocks/frames.png) | all sixteen frames on a plain block, zoomed. CGA and Hercules rows alternate (sign, orb, peng, watch) |
| `clocks/<concept>.txt` | the compile's sizes for that concept (the table below) |
| `clocks/down-<concept>.bbc` | the scratch course: today's `down.bbc` with the four `frame`s |

The frames are in `clocks/frames.py`, drawn with the tool's own machinery (`_ClockArt`, around
`clock_face_geom`'s digits' blocks, like every style in SPEC.md 137.18.5.2). `frames.install(B)` adds them to
`bbcourse`'s styles **in its own process only**. `clocks/sheet.py` compiles each scratch course with them
installed, which takes minutes per concept and runs one process per concept. `sheet.py --render` and
`--overview` redraw the pictures from the compile's cache in seconds. `clocks/preview.py` draws `frames.png`
without a compile. `clocks/outline.py` is a quick proxy for a frame's outline: its width, and how many blocks
it covers only partly.

## The options

Each one is in the course's inks: palette 1 (cyan, magenta and white on black). On the Hercules, cyan and
magenta are the same grey checker, so white and black carry every form. **All four put the digits on WHITE
rather than cyan.** In the Hercules overview they read more clearly than `crystal`'s cyan window does.

### A. `sign`: a FINGERPOST at the fork

A lit post on a collar, with a ball finial. The digits sit on a white ARROW BOARD clamped to the post. The
board has a pointed end, a swallow-tailed end, nails, a lit top bevel and a dithered under-edge. It is a sign
on a pole, which is what the owner said made First Roll's `pin` fit. A fork in the road is this course's
subject.

- `signs` (start): one arrow pointing left, up the line, with a CHEQUERED start flag flying from the post.
- `signh` (hub): THE FORK. The digits' arrow points left (south: steel) with a steel ball on its tail. A
  second, smaller arm above it points right (east: glass) with a glass ball on it.
- `signf` (steel finish): the arrow points right, with the steel ball, under a chequered FINISH banner across
  the post's head.
- `signg` (glass finish): the same, with the glass ball, pointing left.

### B. `orb`: the course's three balls

A big sphere on a short stem and cup. The digits sit on a white band around its middle, bowed to the sphere
like LITTLE HOP's `ball`. The object is the course's subject: you start as rubber and finish as steel or
glass.

- `orbr` (start): RUBBER. Magenta, lit white, with a black dither in its shade.
- `orbh` (hub): THE SPLIT. The left half is steel and the right half is glass, with a zigzag seam down the
  face (steel is south, which is screen left; glass is east, which is screen right).
- `orbs` (steel finish): STEEL chrome. A dithered sky over a hard horizon, dark ground below, a bright rim
  and a glint.
- `orbg` (glass finish): GLASS. Cyan, with a window glint, a caustic low on its right, and its own stem seen
  through it.

The two finish orbs are SMALLER (29 px across, against 36). At 36 px the compile REFUSED them under SPEC.md
137.18.5.4's one ball length: *"a ball rolled behind the clock at (61, 43) [and at (37, 34)] is WHOLLY hidden
for 18 ground units"*. The slim pair also have a thinner band, so their caps still show. On the finishes'
white-and-black diamond floor, the white band and the smaller orb read less strongly than the sign or the
watch.

### C. `peng`: a PENGUIN, a downhill racer and a swimmer

A creature, like the frog the owner liked. It stands on the block's top. The digits are on its white belly.
Its back and head are a dark blue (black dithered with cyan, so its edge is not lost against the void), with
a white rim of light, a magenta beak and feet, and white eyes. The pose changes per use:

- `pengs` (start): racing GOGGLES pushed up on its forehead, flippers swept back, ready to belly-slide down
  the ramp.
- `pengh` (hub): its head turned left and one flipper pointing out (steel's way), the other on its hip:
  "which way?".
- `pengf` (steel finish): flippers up, cheering, wearing a little STEEL helmet (a chrome dome with a rivet).
- `pengg` (glass finish): flippers up, cheering, looking back over its shoulder at the glass goal, with a
  bead of glass balanced on its crown.

**Bent to fit:** the first, wider penguin (a 30 px body, its dark sides showing) was REFUSED. It needed
**285 occluder masks** against the 256 that a 4-byte record's mask byte can name (SPEC.md 137.15.5), even
after the tool's three re-cuts (137.49.5). The one shown is SLIM: a 25 px body, at **249 masks**. That
leaves less dark flank around the belly, so it reads less strongly as a penguin than the wide one did (set
`brx` back to `4 * n + 8.0` in `_clock_peng` and run `preview.py` to see that version). A fuller penguin
needs mask budget that DOWN does not have today (see *What the masks say*).

### D. `watch`: the race's STOPWATCH

A stopwatch in a cradle on a round foot. It has a magenta bezel, lit white at its upper left and dithered at
its lower right, and a white dial with twelve black ticks around the digits. The dial is a window, but it is
the object's own face. A crown and its bow sit on top, with a side pusher.

- `watchs` (start): the crown PRESSED, with click marks around it. The race starts.
- `watchh` (hub): a FORK (a white Y) painted on its foot.
- `watchf` (steel finish): a STEEL case (white over black-and-magenta) with a chequered ribbon from the bow.
  It is slimmer (25 px), because of 137.18.5.4's bound at (61, 43).
- `watchg` (glass finish): a GLASS case (cyan, with a white glint) and the chequered ribbon.

The positions differ least in this concept. It reads cleanly on both cards, but it is the most literal of
the four ("a clock is a clock").

## The bytes (MEASURED: each concept compiled at this commit's `down.bbc`, rev 16)

DOWN is SHEETED (SPEC.md 137.30.12): two sheets of 89 block rows (from rows 0 and 55) and a world part.
**Every sheet carries the whole block pool**, so each sheet's RAM grows by the same amount wherever a clock
stands. Both sheets' LZB figures grow about equally, even though the start clock (block row 11) is only in
sheet 0 and the steel finish (row 128) and glass finish (row 98) are only in sheet 1. The hub (row 80) is in
both. So a frame's blocks cost twice on disk, once per sheet. No option moves the sheet plan: it is still 2
sheets of 89 rows, and the largest grows each sheet's RAM by 810 of its 11,874 bytes of headroom under
65,024. The world part does not move except for the course identity (3,032 to 3,037 LZB).

| concept | picture blocks | occluder masks (of 256) | each sheet in RAM | sheet 0 LZB | sheet 1 LZB | on disk, all three parts LZB | against `crystal` |
|---|---|---|---|---|---|---|---|
| `crystal` (today) | 778 | 240 | 53,150 | 10,837 | 11,884 | 25,753 | - |
| `orb` | 799 (+21) | 237 (-3) | 53,504 (+354) | 11,417 | 12,461 | 26,913 | **+1,160 B** |
| `sign` | 808 (+30) | 242 (+2) | 53,750 (+600) | 11,486 | 12,540 | 27,063 | **+1,310 B** |
| `watch` | 797 (+19) | 252 (+12) | 53,778 (+628) | 11,595 | 12,652 | 27,283 | **+1,530 B** |
| `peng` (slim) | 814 (+36) | 249 (+9) | 53,960 (+810) | 11,715 | 12,765 | 27,514 | **+1,761 B** |

There is no code and no lane in any of them: the digits are 137.18.5's lanes. This is picture only, like
every frame so far.

### What the masks say

DOWN already uses **240 of 256** occluder masks with today's crystals. A clock's face is geometry keyed at its
cell (137.18.5.4), so a busier outline costs masks wherever a ball can pass behind it. `watch` reached 258
and was brought back to 252 only by the tool's re-cut (137.49.5). The wide penguin reached 285 and was
refused. **Whichever frame is chosen, the course has between 4 (`watch`) and 19 (`orb`) masks left for
everything the lead adds afterwards.** Any clock art drawn for DOWN later should be priced against that
first. `outline.py`'s partly-covered-blocks count is only a rough guide to it: the masks depend on what
passes behind each clock.

## Rules each one bends

- **G11 / 137.18.5.4 (a clock never hides the ball for more than one ball length):** all four pass the
  compile's check at all four positions. `orb`, `watch` and `peng` are slimmer at the finishes, which is
  LITTLE HOP's `frogb` precedent. `sign`'s hub and finish frames are the widest (34 - 35 px), but they are
  boards and banners rather than solid discs, so a ball behind them is never wholly hidden for long.
- **"No flat squares":** `sign` is a signboard. It is shaped (a point and a swallow tail) and hung on a post
  like `pin`, which the owner accepted. None of the others has a flat panel.
- **G10 / G9 (two clocks never share a screen; one in view from the start and every finish):** the positions
  are unchanged, so these hold as today (the compile ran the static checks).
- **The digits are on white, not cyan:** this is a change from `crystal` and `pin`. The owner allows either,
  and on the Hercules white is the stronger of the two.

## Tool support

Drawing them needed none, since `_ClockArt` covers all four. **Lifting the chosen concept into the tool**
means copying its function from `clocks/frames.py` into `tools/bbcourse.py` beside `_clock_frog`: about 75
lines of Python for `orb`, `peng` or `watch`, and about 110 for `sign` with its arrow, plus about 45 lines of
shared helpers (the block-top shadow, the chequer and the ball icon). It also needs its four names in `CLOCK_STYLES` and
`_CLOCK_DRAW`, and a paragraph in SPEC.md 137.18.5.2. Then `sketch.py`'s `FRAMES` names the four frames per
position (`FRAMES = {"start": "signs", "hub": "signh", "steel finish": "signf", "glass finish": "signg"}`)
and a re-emit writes them. That change costs 0 bytes of guest code. Until then, the scratch `.bbc` files
compile only through `sheet.py`, because the tool on disk does not know the names.
