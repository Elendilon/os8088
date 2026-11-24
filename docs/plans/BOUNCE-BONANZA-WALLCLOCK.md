# BOUNCE BONANZA: a WALL CLOCK (RESEARCH, 2026-11-24)

**Status: research only, for the owner to decide.** Nothing in the game, the tool or SPEC.md changes. The
study is [`bonanza-courses/wallclock/wallclock.py`](bonanza-courses/wallclock/wallclock.py) (host only, about
10 s), which compiles a scratch host course ([`wall.bbc`](bonanza-courses/wallclock/wall.bbc)) and FIRST ROLL
with `tools/bbcourse.py` exactly as it is, paints clock digits onto block faces the way a lane's poses would
ink them, checks each placement and counts its lanes and blocks. Its full output is
[`numbers.txt`](bonanza-courses/wallclock/numbers.txt).

**The owner's ask:** *"A clock that is art pasted onto a column or across a couple of columns, so it needs no
additional occlusion and doesn't take up tile space on the course. May need another digit font, or two for
both directional facings. What does this cost?"*

**Labels.** MEASURED here means counted from the tool's own compiled picture by the study script (lanes,
blocks, records, which pixels a face owns). It does NOT mean a built part or a guest run: no wall clock was
compiled into a part, and no emulator ran (the pictures are the tool's pixels, as every course preview is).
PREDICTED is arithmetic from SPEC.md's measured figures, named where used.

## The answer in one table

| | today's prop clock (vase, crystal, ...) | the recommended WALL clock |
|---|---|---|
| tile space | its own floor cell, an OBS post (130.18.5.3) | **none**: it is on a face the course already has |
| static art | a frame drawn and **keyed** (130.18.5.4): new records and masks | a white plate painted on the face: **4 blocks, no record, no mask** |
| occlusion | its own key; refused past `CLOCK_HIDE` | **none new** (question 3) |
| digit lanes | 2 x (1 word x 1 block row), 11 poses | the same: **2 x (1 x 1)**, 11 poses |
| part bytes, a clock | FIRST, MEASURED: **+328 to +1,340 RAM, +152 to +332 LZ4** | PREDICTED **+492 RAM** (with the plate; +268 bare), about +150 - 250 LZ4 |
| guest code | the CLOCK lane kind, +136 bytes (built) | **0 bytes** (PREDICTED: the same record kind with no OBS cell) |
| per second | one 1-block commit (two at a ten) | the same |

**Recommendation: the LEVEL clock** - the shipped 5 x 7 digits, UPRIGHT, both digits on one line (not
following the face's slope), each on a small white plate painted on the face, on a face at least 2 units
(16 px) high, either facing. It is the only form that reads on all three cards on both facings, it needs no
new font, and its lanes are exactly today's (1 x 1 each), so its guest and frame costs are today's clock's.
Its cost is a TOOL feature (a statement, a face check, a placement), about 300 bytes of part per clock and no
guest byte. The sheared ("art painted on the wall") form is possible but costs about 2x the blocks and reads
worse; details below.

## 1. Geometry: what a digit on a face looks like

In this projection (`clock_face_geom`: screen x = 16 (wx - wy), y = 8 (wx + wy) - z) a block shows two
vertical faces. In the tool's names (`render`'s ops) they are:

- **`sw`**, the LEFT face on screen, the block's **+y** face: solid magenta on palette 1, its top edge
  falling to the right, 1 line every 2 px;
- **`se`**, the RIGHT face, the **+x** face: the magenta-and-black checker (`_SE_INK`), its top edge rising
  to the right, 1 line every 2 px.

(The owner's "-x and -y" are these two; the faces that point away from the camera are never drawn.) A cell's
face is **16 px wide** (two words) and **8 px per unit** high; between two cells' faces there is a black
1-px SEAM at x = 0 mod 16 (a word's column 0), and a black edge line under the top.

Three ways to put a digit there, all drawn by [`wallclock.py`](bonanza-courses/wallclock/wallclock.py) with
the tool's 5 x 7 `CLOCK_FONT`:

| form | what | lanes (2 digits, 8 px apart) | new pose blocks (CGA) | pictures |
|---|---|---|---|---|
| **SHEARED** | every glyph column dropped (sw) or raised (se) by the face's own staircase: the glyph painted ON the plane | **1 x 2 each** (a 5-wide glyph sheared is 9 lines, which never fits an 8-line block) | 30 - 31 (480 - 496 B) | [shear57.png](bonanza-courses/wallclock/shear57.png) |
| **STEPPED** | each digit upright, its baseline following the face (8 px on, 4 lines down/up) | one 1 x 1, one 1 x 2 (the 4-line step puts the two places at two phases of the block grid) | 29 (464 B) | [upright.png](bonanza-courses/wallclock/upright.png) rows 1 - 8 |
| **LEVEL** | each digit upright, both on ONE line | **1 x 1 each** (the same phase) | 10 bare (160 B), 20 on plates (320 B) | [upright.png](bonanza-courses/wallclock/upright.png) rows 9 - 13, [first.png](bonanza-courses/wallclock/first.png) row 4 |

The comparator, MEASURED from FIRST's compile: its two shipped clocks are 4 lanes of 1 x 1 with **20**
distinct pose blocks over pose 0's, **10 a clock** (320 B CGA).

**Can the tool shear the existing digits at build time?** Yes: the study does it from `CLOCK_FONT`, reading
the face's top edge off the compile (each column's first line), so the shear follows the face exactly. No
glyph is stored: a pose IS its blocks (130.18.5), so the sheared glyphs exist only as blocks in the part.
**How many glyph sets?** The block pool's cost is per PHASE, not per place: at an 8-px pitch a 1:2 face
moves 4 lines a digit, so the places alternate between two phases of the 8-line block grid, and a third
digit (a limit of 100 s or more) lands on the first place's phase and adds nothing (MEASURED: 2 digits 30
blocks, 3 digits 30 - 31, [three.png](bonanza-courses/wallclock/three.png)). So per facing per background: 2
phases x 10 digits, about 30 blocks; both facings on one course about 60. A blank pose is the face itself
(already in the pool).

**Is a sheared 1:2 glyph legible?** MEASURED by looking at the pictures, on the CGA and the VGA (the VGA's
mode 0Dh shows the CGA's four colours, the same blocks converted at load: 130.46.1 D6, 130.46.5, so the two
are pixel-identical) **marginally**: verticals stay vertical, a horizontal stroke becomes 2-px steps, and the
glyphs with diagonals suffer - on `sw` a 7 reads as "?", on `se` a 4 loses its crossbar and a 7 reads as a
flagged 1. On the **Hercules** (a game pixel is two card pixels; cyan and magenta are one grey checker, black
and white carry every form: `herc_pair`) black digits on the bare `sw` face are **not legible** (black on a
grey checker), and white digits on the bare `se` checker barely. A white plate under black digits fixes the
Hercules for every form. A legible sheared set would need a HAND-DRAWN font per facing (the owner's "two
fonts"): tool data only, no guest byte, but it is design work, and the block cost stays 2x the level form's.

A 4 x 7 cut, one digit a CELL (16 px apart, so both places share a phase: 1 x 1 lanes, 10 blocks) is in
[percell47.png](bonanza-courses/wallclock/percell47.png) (and the 5 x 7 level the same way in upright.png's last two rows): cheap, but the digits stand a whole cell apart and
read as two numbers. The 1-unit (8 px) face takes no 5 x 7 glyph at all; a 3 x 5 sheared fits (1 x 1 + 1 x 2,
24 blocks, [small.png](bonanza-courses/wallclock/small.png)) and is barely a digit.

## 2. Placement: what makes a face a host, and a grammar

A placement is valid (the study's `check`, the rule a tool would enforce) when **every ink pixel of every
pose is a VISIBLE pixel of the named face, off its edge line and its seams**:

1. **visible**: the final picture's key at that pixel is the face's cell (`sbuf == wx + wy`) - nothing in
   front (a taller block, a prop, a rail) covers it; the tool already has this per pixel (`sbuf`, and the
   `lk`/`lo` "which geometry" buffers, 130.47.5);
2. **height**: at least 2 units (16 px) for the 5 x 7 (MEASURED: the 1-unit face has no legal place; 2 and 3
   units both hold it); 2 units is also the least that keeps a white plate off the edge lines;
3. **width**: one cell (16 px) holds 2 digits in its two words; three digits take two cells;
4. **lanes**: a digit's blocks share no block with another lane (or it is grouped, 130.32) and are counted
   as clock lanes are (SLOW, 130.19.10; `WIN_CHG` in a window with a clock);
5. **not a post**: the cell is the wall's and stays the wall's: no OBS, no post fields (the wall is already
   solid).

**The seam between two cells**: it is a black line on word column 0 of every even word, and the 5 x 7 glyph
already sits a pixel in from its block's left (`clock_glyph`), so a digit never touches a seam (MEASURED: the
level and per-cell placements across two cells are legal). The two cells' faces have different keys
(`wx + wy` differs by 1): every pixel keeps its own, so nothing changes for the records; a single digit simply
must not straddle the seam, and on the 2-word grid it cannot.

**Draft grammar** (beside `clock`, so a clock is either a prop or a face):

    clock WX WY face sw|se [span 1|2] [form level|stepped|sheared] [plate white|none] [digits DX DY]

- `WX WY` the cell whose face holds the units digit's left edge; `face sw` (the left, +y) or `se` (the
  right, +x); `span 2` lets three digits run into the next cell along the face (to screen right: `sw` +x,
  `se` -y);
- `form` defaults to `level`, `plate` to `white`; `digits DX DY` nudges as 130.18.5.5's anchor does (the
  same legality: whole blocks plus the glyph's slack);
- refusals: the face not visible at every ink pixel (naming the first, as the art-holds check does), a face
  under 2 units, a lane shared, the cell a post's.

The record stays `PK_CLOCK` with its place at +26 and its post fields zero; the tool does not mark the cell
OBS, so the guest's post rule (`bzphys.inc`'s `bz_wolf`, which only meets a clock through an OBS cell) never
sees it.

## 3. Occlusion: "needs no additional occlusion" - CONFIRMED

This is the existing rule for a lane drawn on geometry (130.12.4.5), the windmill's rotor on its house front:

- **A ball BEHIND the face**: the face is already an occluder wherever a ball can pass behind it. MEASURED on
  the scratch course: the 3-unit block's `sw` clock blocks already hold 2 records (s 12, top 24) and its `se`
  clock blocks 1; the 2-unit block's 2. They are cut from the face's KEYS, not its ink, and every digit pixel
  is a face pixel with the face's key at every pose, so the records' verdicts do not depend on the pose and
  the lay copies the DRAWN digit through the map (130.18.5.4 item 3). No record is added, no mask changes,
  and the tool's 130.12.4.5 check passes by construction. (FIRST's plateau front: 0 records on the clock's
  blocks - nothing passes behind it.)
- **A ball IN FRONT of the face**: the ball is drawn over the picture. A due digit whose lane meets the
  frame's boxes is never the wheel's or the lead's that frame (130.12.4.2): it is composed in the CONTACT box
  with the shadow, the ball and the occluders, or waits a frame and stays due - exactly as a vase clock's
  digits and a rotor do today. A redraw never overwrites the ball.
- **The ghost dither** (130.15.10.1) applies to the face's records as before.

So the wall clock needs **no mechanism at all** beyond today's lanes - cheaper than the prop clock, which had
to become an occluder of its own (130.18.5.4: on FIRST that keying is most of the clock's part cost; FIRST
with no clocks has no records at all, MEASURED below). The one condition is rule 1 of question 2: digits only
on the face's own visible pixels. A digit inked over a neighbouring top or a different cell's face would mix
keys across poses and be refused by the existing 130.12.4.5 check.

## 4. Cost

**Guest code: 0 bytes** (PREDICTED). The CLOCK lane kind (`bzwheel.inc`'s `.clock`, `bz_tdig`, `bz_tdset`,
the walk's second test, the finish's clock group) reads a record's place and the seconds; the lane writer is
generic up to 4 x 3 blocks (`LANE_WMAX`, `LANE_HMAX`), so even the 1 x 2 sheared lanes need no code. The post
path is reached only through an OBS cell. Risk to check when built: any site that assumes a CLOCK record
stands on its own floor cell (`clock_vis`, the finish-clock rule 130.22.6's "in the window centred on it",
`bonanza_ring`'s oracle) - tool and row code, not guest.

**Data, per clock** (CGA blocks 16 bytes each; the Hercules and the VGA convert the same blocks in place at
load - `bz_hxlat`, `bzv_conv` - so they STORE nothing more; a record 32 bytes and its pose map 11 x h x w
words, 130.12.3.1):

| form | pose blocks | static plate | records + maps | RAM a clock |
|---|---|---|---|---|
| level, bare | 10 (160) | 0 | 108 | **268** |
| **level, white plates** | 20 (320) | 4 (64) | 108 | **492** |
| stepped, plates | 29 (464) | 4 (64) | 130 | 658 |
| sheared, bare | 30 - 31 (480 - 496) | 0 | 152 | 632 - 648 |
| sheared, white band | 30 - 31 | 5 (80) | 152 | 712 - 728 |
| 3 digits (any) | as 2 (the phases repeat) | | +76 a place | |

(MEASURED counts from the study; bytes PREDICTED from them. Pose blocks deduplicate across a course's clocks
on the same face ink and phase, as today's do.)

**Against a prop clock** (MEASURED, FIRST compiled with its two clocks, with only the (3, 6) one, and with
none): the (11, 4) clock costs **+328 bytes RAM, +152 LZ4** (blocks 135 -> 140, records 32 -> 58, masks
24 -> 26); the (3, 6) one **+1,340 RAM, +332 LZ4** (blocks 95 -> 135, records 0 -> 32, masks 0 -> 24). Most
of that is the frame's art and its keying, which a wall clock does not have. Where the glyphs live: in the
COURSE part, as every lane's poses do; a kit-wide glyph set would need a new pool and is not worth it at 160 -
320 bytes a clock.

**Tool**: a statement, the face's visibility and edge test, the placement and plate painter, the refusals and
a `--selfcheck` section with red arms; PREDICTED 200 - 300 lines of Python, about the size of 130.18.5.5's
anchor (+12 KB of source with its selfcheck).

**Per second, on the 8088**: a digit change is a lane commit. From 130.11.3's **1,070 clk a block** written
and the commit's own overhead (130.13.5.2's model: a few hundred clk fixed; `bz_lmap`'s copy, priced 590
fixed, only when a commit is not the whole lane): a 1 x 1 change about **1.1 - 1.7k clk**, a 1 x 2 about
**2.2 - 2.8k** (PREDICTED). The units change every second and the tens every tenth: about 1.1 changes a
second, so **about 1.2 - 1.9k clk a second** for the level clock (today's clock exactly) and about 2.4 - 3.1k
for the sheared one - on one frame of roughly 55 - 60, in the retrace wait's wheel or the contact box. Between
seconds the walk skips a clock's lanes (`bz_lcsec`), so an unchanged clock costs about nothing a frame.

**The frame risk the HUD had (130.14.5, 130.14.26: +65 missed refreshes on the CGA `MILL` leg)** does not
apply, for the reason the prop clocks avoided it: the HUD was a FIFTH box, composed from every layer and
written again whenever the camera moved, at a fixed window position, so it landed on the frames that already
missed. A wall clock is part of the PICTURE: it scrolls in with the course from the map (an entering strip
carries the drawn pose, 130.12.4.2) at no cost, and it changes once a second through the lane path the prop
clocks use. The figure that applies is the prop clocks' own (130.18.7, MEASURED, form (ii)): on the CGA's
`MILL` about **+1.6 missed refreshes a second** with a clock in view on a third of the route, inside the
rule's +2. A level wall clock is the same lanes, so PREDICTED the same; a sheared one adds a block a change.
Because a wall clock needs no keyed art, it does not add the records that 130.18.5.4's keying added on the
prop clocks.

## 5. Alternatives

| alternative | cost | verdict |
|---|---|---|
| **one facing only** | halves the pose blocks only for the sheared form (level/stepped use the same glyphs on both facings anyway) | not needed for level |
| **one digit a cell** (4 x 7 sheared or 5 x 7 level, 16 px apart) | 1 x 1 lanes, 10 blocks (160 B) | cheapest, but reads as two numbers |
| **sheared, hand-drawn per facing** (the owner's "two fonts") | as sheared (about 2 x 30 blocks a course for both facings) + font design; 0 guest | the most "painted on" look; legibility only as good as the drawing |
| **a FLOOR clock**, projected onto a top | the digits sprawl over 32 x 13 px; MEASURED **shared blocks** between the two places (product poses: refused by today's format) and 84 blocks | unreadable ([floor.png](bonanza-courses/wallclock/floor.png)) and does not fit the lane format |
| **a floor DECAL** (upright digits painted on a top) | as the level wall clock, 1 x 1 lanes; but it lies under the ball's path, so its changes meet the ball's boxes more often (contact-box composes) and it takes floor the course may want | legible; a fallback for a course with no 2-unit face in view |
| **a 1-unit face** (3 x 5) | 24 blocks | barely legible; not recommended |

## What was not done

No guest or tool change, no part built, no emulator boot (the pictures decide nothing an emulator would add:
they are the compiled pixels the card shows, and the Hercules is drawn through `herc_pair` as the course
previews are). No soak rows. Before building: a host compile of the statement into real parts (FIRST and MILL)
would MEASURE the RAM / LZ4 lines above, and `bonanzawheel`'s CLOCK leg covers the lanes unchanged.

## The owner's answer to round 1 (2026-11-24)

*"A good first pass, but these would need worked into artwork themselves (sit on top of), and the artwork would
need to be able to span multiple columns. The artwork would, just like with today's clock, host the digits."*

- **No generic white plate**: "these make them not fit into the world" - a clock's art may occasionally contain
  a plate, but that is not the general case.
- **The wall clock is ART on a face**, spanning one or more columns, drawn over the face like a decal, hosting
  the digits as the vase art hosts today's.
- **The floor clock is a real option**, also on its own art; a ball rolling over it only obstructs it for a
  moment, which is fine.

Round 2 (below, when it lands) costs those two: art-hosted clocks on a face and on a floor.

## Round 2: art-hosted clocks (2026-11-24)

**Status: research only, for the owner to decide.** Nothing in the game, the tool or SPEC.md changes. The study
is [`round2/wallclock2.py`](bonanza-courses/wallclock/round2/wallclock2.py) (host only, about 6 minutes, 25 s
with `--quick`, which skips MILL), with the per-facing digits in
[`round2/fonts.py`](bonanza-courses/wallclock/round2/fonts.py); its output is
[`round2/numbers.txt`](bonanza-courses/wallclock/round2/numbers.txt). It reuses round 1's machinery (the face
reader, the lane counter, the three-card panels) and adds:

- **art authored FLAT** (an elevation: `u` px along the face, `v` px down it, the course's four inks), with a
  declared **digit window**, written as a text pixmap in the `art` statement's own format (130.23.2) with a
  `# digits U0 V0 U1 V1` line: [`art_station.bba`](bonanza-courses/wallclock/round2/art_station.bba),
  [`art_board.bba`](bonanza-courses/wallclock/round2/art_board.bba),
  [`art_strip.bba`](bonanza-courses/wallclock/round2/art_strip.bba),
  [`art_delft.bba`](bonanza-courses/wallclock/round2/art_delft.bba);
- **projection onto a real face**: each column `x` of the art drawn at `plane(x) + 1 + V0 + v`, where `plane` is
  the face's own top-edge staircase read off the compile (`sw`: `off + (x + 1) // 2`; `se`:
  `off - (x + 1) // 2`) and extended over the whole run of columns, then clipped to the host cells' VISIBLE
  pixels (`sbuf`), so what stands in front is never painted;
- **the digit lanes** placed in the window (every ink pixel of every pose inside it), in three forms and two
  inks;
- **the part MEASURED**: the course compiled again with the projected art as a real `art` statement, and again
  with the digits' new pose blocks laid in the picture's void as art (a pose IS its blocks, 130.12.3.1, so this
  carries exactly the blocks the lanes would add), RAM and LZ4 of the picture part (`packed_len`), against the
  course as shipped.

**Labels.** MEASURED = counted from the tool's compile (blocks, records, part bytes) or by the study's
placement check. PREDICTED = arithmetic from SPEC.md's figures. No emulator ran (the pictures are the
compile's pixels, as every course preview is; the Hercules through `herc_pair`).

### The pieces and the pictures

| | art | host | pictures |
|---|---|---|---|
| **E1** | a STATION CLOCK: a white enamel case hung on a black bracket, a bell, a dithered shaded edge, a CYAN dial with four hour pips | FIRST's plateau front, 2 columns, `sw` (4, 6) - (5, 6) | [e1_station_sw.png](bonanza-courses/wallclock/round2/e1_station_sw.png) |
| **E2** | a SCOREBOARD: a black board in a white-and-cyan frame lit from the upper left, "TIME" in white, two lamps; a black field (or cyan) | FIRST's plateau front, 3 columns, `sw` (6, 6) - (8, 6) | [e2_board_sw.png](bonanza-courses/wallclock/round2/e2_board_sw.png) |
| **E3** | **the same scoreboard SOURCE** as E2, unchanged | MILL, 3 columns, `se` (35, 25) - (35, 23) | [e3_board_se.png](bonanza-courses/wallclock/round2/e3_board_se.png) |
| **E4** | a DELFT TILE PANEL for WINDMILL LANE (its clocks are Delft vases): white tiles, one tile column a face column, cyan corner motifs, a cyan windmill across the tiles, and a long cartouche tile whose white holds the digits | MILL, 4 columns, `sw` (26, 49) - (29, 49) | [e4_delft_sw.png](bonanza-courses/wallclock/round2/e4_delft_sw.png) |
| **E5** | a RAIL BANNER: a cyan band with white chevrons, on a 2-UNIT face | FIRST's back rail, 4 columns, `sw` (3, 3) - (6, 3) | [e5_banner_sw.png](bonanza-courses/wallclock/round2/e5_banner_sw.png) |
| **E6** | a SUNDIAL painted on the floor: a white dial, black rim and hour marks, the gnomon's shadow, a cyan field disc at its middle | FIRST's plateau top, (3 - 6, 4 - 6), the start's own floor | [e6_sundial_floor.png](bonanza-courses/wallclock/round2/e6_sundial_floor.png) |

Each sheet is the art blank, then each digit form and ink with "47" on it, every row CGA | Hercules | VGA (the
VGA's mode 0Dh shows the CGA's four colours, the same blocks converted at load: round 1). The whole of FIRST
with E1, E2, E5 and E6 and live digits is [first_context.png](bonanza-courses/wallclock/round2/first_context.png)
(an illustration: four clocks on FIRST would break the 6-lanes-a-window bound, below). The per-facing digit sets
are [fonts.png](bonanza-courses/wallclock/round2/fonts.png); today's crystal clock with white digits is
[crystal_ink.png](bonanza-courses/wallclock/round2/crystal_ink.png).

### The digit forms

| form | what | lanes (2 digits) | needs a window (flat) of about |
|---|---|---|---|
| **level** | the shipped 5 x 7 (`CLOCK_FONT`), upright, both on one level line (round 1's legible form) | 1 x 1, 1 x 1 | 17 wide x 18 - 20 tall: a level row 13 px wide crosses 7 lines of the face's slope, and the block grid adds a few |
| **stepped** (per-facing) | a hand-shaped 4 x 7 drawn IN the facing's perspective, the units 8 px right and 4 lines down (`sw`) or up (`se`): the digit line lies on the face | 1 x 2 (one place), 1 x 1 | 20 x 10: the digit line follows the face, so the window is just a glyph tall |
| **italic** (per-facing) | the same glyphs on ONE level line: each digit leans with the face, the line does not | 1 x 1, 1 x 1 | 20 x 14 |

**The per-facing font** (the owner's "a font per facing", [fonts.png](bonanza-courses/wallclock/round2/fonts.png)):
a 4-px glyph on a face falls exactly ONE line across its width (the face steps on odd columns), so a 4 x 7 drawn
in the face's perspective is **8 lines, one block** - where round 1's mechanical shear of the 5 x 7 was 9 lines
and always a 1 x 2 lane. Each glyph is drawn by hand for its facing: a "horizontal" stroke is two pixels then a
line down (`sw`) or up (`se`), parallel to the face's edge; verticals stay vertical; diagonals are redrawn, not
sheared. A glyph must start on an odd picture column (word column 1 or 3), the tool's legality rule.

### R2.1 The wall art: authoring, placement, facings, seams, digits

- **Authoring**: FLAT, an elevation in face pixels, with the digit window declared in the same coordinates.
  The tool projects it: every column offset by the face's own staircase (1 line per 2 px), so the art lies ON
  the face (the "TIME" on E2/E3 and the tile joints on E4 are flat source, projected). Width is free: 1 - 4
  columns is just the art's width; the run of cells is the host. MEASURED: 2 (E1), 3 (E2, E3) and 4 (E4, E5)
  columns, every pixel clipped to the host's visible face pixels (a pixel above a column's lower top, as over
  FIRST's ramp at (7, 6) and (8, 6), would simply not be painted; E2 sits under it).
- **One source serves both facings** (MEASURED: E2's and E3's source is the same file). The projection is the
  only per-facing step: an elevation has no facing, and text in it reads left to right on both. What does NOT
  carry over is LIGHT: the course lights `sw` faces solid and `se` faces as a dither, and an art piece lit from
  the upper left keeps its own lighting on both (E3's frame reads fine). A piece that wants the face's shading
  mirrored is a second source, the author's choice, not a rule.
- **Seams**: the art paints over the face's black seam pixels (they are face pixels with the cell's key); a
  piece that wants them (E4's tile joints ARE the seams: one tile column a face column) draws its own lines
  there. Every pixel keeps its own cell's key, so a seam under the art changes nothing in the records.
- **The digits**: in the window, in any of the three forms above (per clock), placed by the tool on the block
  grid. The art's offset on the face is free per pixel, so when the window and the grid do not agree the tool
  names the nearest offset that does (the study's `fit`, as 130.18.5.5 names the nearest legal anchor).
  **Height decides the form**: on a 2-unit face (E5, 16 px) only the STEPPED per-facing form fits (MEASURED:
  level and italic have no legal place); 3 units and up take all three.
- **Legibility on the Hercules comes from the art's field**, not a plate: a BLACK field (E2/E3's board: white
  digits, full contrast on both cards) or a WHITE one (E4's tiles: black digits) carries the digits on every
  card; a CYAN or MAGENTA field (E1's dial, the cyan variants) is the Hercules' grey checker and takes black or
  white digits as the bare face does - the owner reads black digits on the bare face as fine, and the pictures
  show both inks on every field that allows them.

### R2.2 The floor art

- Authored in PLAN (cells; E6 is a function of the floor point, the way `first/decals.py` and `down/art.py`
  draw floor decals), projected onto the top (`(16 (X - Y), 8 (X + Y) - 4 z0)`), clipped to the host tops'
  visible pixels. MEASURED: E6 on FIRST's plateau, around the start.
- **Digits LEVEL** (the 5 x 7, upright on the floor, 1 x 1 lanes): legal in the dial's field. Projected digits
  stay as round 1 found them (unreadable, shared blocks, refused by the format). A per-floor hand font is not
  worth it: a floor squashes a glyph 2:1, so a legible one would be about 9 lines and 1 x 2 at best.
- **The ball over it**: the ball is drawn over the picture, so it hides the digits for a moment (the owner's
  "fine"); a due digit whose lane meets the ball's boxes is composed in the contact box or waits a frame
  (130.12.4.2), as a rotor does. It is the clock most often in the contact box (the route crosses it), the
  per-second cost's worst case, not a new mechanism.
- **Conflicts with the floor's own occluders and props** (MEASURED for E6): the lanes' blocks hold **0** of
  the course's records and share no block with another lane. A floor clock can share no block with a prop's
  lane (a pad, a boost, a flag; 130.12.4.6, refused as every lane is) and must leave the start window's free
  4 x 3 corner (130.12.4.6); E6, beside FIRST's start, passes the study's lane check, and a real build would
  also run the start-window rule.

### R2.3 Example art pieces

The six above, each on CGA, Hercules and VGA, with black and white digits wherever the field allows both.

### R2.4 Cost

**Per art piece** (MEASURED: the course compiled with the piece as an `art` statement, picture part):

| piece | blocks | RAM | LZ4 |
|---|---|---|---|
| E1 station clock, 2 col | +19 | +304 | +228 |
| E2 scoreboard, 3 col (FIRST) | +18 | +288 | +223 |
| E3 the same scoreboard on MILL's `se` | +19 | +304 | +203 |
| E4 Delft panel, 4 col x 58 px | +40 | +640 | +459 |
| E5 rail banner, 4 col, 2 units | +9 | +144 | +128 |
| E6 sundial (floor) | +23 | +368 | +281 |

**Records and masks: none.** MEASURED: FIRST with E2, E5 and E6 compiled in has 58 records and 26 masks, the
same records in the same blocks with the same masks as without them (130.23.2: art writes colour, the keys
are the surface's).

**Per clock, the digits** (MEASURED blocks and part bytes, the poses laid in the course; records and pose maps
PREDICTED, 32 bytes a lane and 11 x w x h words, 130.12.3.1):

| form | pose blocks | RAM (blocks) | LZ4 | + records/maps |
|---|---|---|---|---|
| level, a UNIFORM field (E1, E2, E4 cyan) | **10** | 160 | 128 - 143 | 108 |
| level, a non-uniform field (E3, E4's tiles, E6's dial) | 20 | 320 | 178 - 242 | 108 |
| italic | 10 - 20 | 160 - 320 | 124 - 182 | 108 |
| stepped | 28 - 30 | 448 - 480 | 239 - 306 | 130 |

A uniform field halves the level digits: both places' blocks are then the same 10 (the background under each
place is identical), which no prop clock had (its face is shaded under each place).

**A whole clock** (art + digits + records, RAM): the station clock, level, **about 572 bytes**; the scoreboard,
level, about 556; the rail banner, stepped, about 722; the sundial about 796; MILL's Delft panel, level, about
1,068. LZ4 about 350 - 650 plus the records' share. Today's prop clocks on FIRST (round 1, MEASURED): **+328 to
+1,340 RAM, +152 to +332 LZ4** a clock - most of the upper figure the keyed frame's masks and records, which art
does not have; MILL's vase restyle moved its four clocks' picture by 17 blocks (130.18.5.2). So an art clock
costs about what a prop clock costs, spent on picture rather than on keying, and none of it is tile space.

**The per-facing font's storage** (MEASURED, the 10 digits on a plain field laid in FIRST's void): **10 blocks,
160 bytes RAM, 110 - 129 bytes LZ4 in the part**, for each facing, ink and field (121 - 129 bytes LZ4 for the 10
alone). On a non-uniform field each place adds its own (20), and the STEPPED form's 1 x 2 place about 18 more.
**Who pays**: a course pays for the facings, inks and fields it USES (a pose is blocks in the course's own pool);
one with only `sw` clocks never carries the `se` set. **In the kit**: the kit already holds every block at
least 3 pool courses hold, lane poses included (130.37.2, 130.37.3), so digits on a STANDARD field (black board,
white tile, cyan) used by 3 courses would move into `BZKIT.BIN` with no new mechanism: on disk a course then
NAMES them (a bit each in its `KITREF` bitmap) instead of carrying ~120 LZ4 bytes, and the kit carries them
once; in RAM nothing changes (the kit's pieces are copied into the course's part at load, 130.37), so **RAM stays
160 a set per course; only the disk is saved** (PREDICTED from 130.37's rules). A font held ONCE in RAM and drawn
onto any background would need the guest to compose a glyph into a block (a new lane draw, about 40 - 80 bytes,
PREDICTED) - not worth it at 160 bytes a course.

**Digit colour** (black or white, per clock): a BUILD-TIME choice, **no guest code** - the ink is only which
pixels the tool writes into the pose blocks (`clock_glyph` hard-codes black today). MEASURED on today's crystal
clocks (FIRST, `clock_glyph` patched to white,
[crystal_ink.png](bonanza-courses/wallclock/round2/crystal_ink.png)): **140 blocks either way, 9,192 bytes RAM
either way, LZ4 2,796 -> 2,798**. A clock pays for one ink; only a course that puts BOTH inks on the same field
pays twice (another 10 - 20 blocks). On the vase clocks white digits need a non-white belly - an art change,
not a cost. The tool's work: an `ink black|white` clause on `clock` (and on the art clock's statement), a few
lines.

**Guest code: 0 bytes** (PREDICTED, as round 1): the CLOCK lane kind draws any pose blocks in a 1 x 1 or 1 x 2
lane; ink and font are the tool's. Round 1's risk list stands (any site assuming a CLOCK record stands on its
own floor cell).

**Per second on the 8088** (PREDICTED from 130.11.3's 1,070 clk a block and round 1's commit model): level and
italic are today's clock exactly, **about 1.2 - 1.9k clk a second**. Stepped has one 1 x 2 place: on the TENS
(the tool chooses which place takes the 4-line phase; the study took the nearer placement, which gave it to the
units) it costs one extra block every tenth second, about 1.3 - 2.0k; on the units about 2.4 - 3.1k. The floor
clock is the same, more often composed in the contact box. **Bound**: a clock is 2 lanes against the 6 a window
and 8 a range (130.12.4.6); FIRST already shows 4 clock lanes, so ONE art clock fits beside its two prop clocks
and a second would not.

**Tool work** (PREDICTED): a statement, e.g.

    clock WX WY face sw|se|top art FILE.bba [at U V] [digits level|stepped|italic] [ink black|white]

(`WX WY` the first host cell; for a wall the run goes along the face to screen right; `at` the art's offset,
refused off the legal grid with the nearest legal one named), the `.bba` reader taking the `# digits` window
line, the projection (about 40 lines: `down/art.py`'s `paste_y`/`paste_x` grown into the tool), the per-facing
font tables (2 x 10 glyphs, data), the window placement and its refusals (no legal place; ink off the window; a
host pixel hidden; a lane shared; a run that is not one plane), and a `--selfcheck` section with red arms. About
300 - 400 lines with the selfcheck, the size of 130.18.5.5's anchor (+12 KB).

### R2.5 Occlusion: round 1's conclusion HOLDS

- **Several columns**: each art pixel keeps the key of the face that drew it (MEASURED: the same records and
  masks with and without the art); a digit block across a seam has two keys, but neither changes with the pose,
  which is all 130.12.4.5 asks. No record, no mask, no OBS, no post.
- **A floor**: the same - the floor's keys, unchanged by the art or the pose; a ball over it is drawn over it; a
  ball behind and below a raised floor is laid over by that floor's records exactly as without the art. E6's
  lanes hold 0 records.
- **A ball behind a wall**: the face's existing records lay the DRAWN digit through the map (round 1).

### R2.6 Recommendation

1. **Build the WALL art clock first**, with LEVEL digits on a UNIFORM field as the default: one statement, 0
   guest bytes, 1 x 1 lanes (today's per-second cost), 10 pose blocks (160 B) and the art's own blocks (about
   300 B for a 2 - 3 column piece). The scoreboard (E2/E3) is the safe first piece: black board, white digits,
   full contrast on all three cards, one source on both facings.
2. **Add the per-facing STEPPED digits** as the form for LOW faces (2 units, where nothing else fits: E5) and
   wherever the digits should lie on the wall: two hand-drawn 10-glyph tables in the tool (drafted here in
   [fonts.py](bonanza-courses/wallclock/round2/fonts.py), to be redrawn to taste), 28 - 30 blocks a clock, the
   1 x 2 on the tens. ITALIC is a cheap middle (10 - 20 blocks, 1 x 1) if its look is liked.
3. **The FLOOR clock** next: the same statement with `face top`, level digits; it costs a little more
   (non-uniform dials: 20 blocks) and meets the ball's boxes more often, which the owner's terms allow.
4. **Ink** as a per-clock clause on every clock (today's too): free in guest bytes and in blocks.

**What the owner authors**: the art as a `.bba` FLAT source (an elevation for a wall, a plan for a floor, or
drawn by a script as `down/art.py` and these pieces are), with one `# digits U0 V0 U1 V1` line naming the
window, and one `clock ... art` statement placing it; the tool projects, clips, places the digits and refuses
what will not fit, naming why.

### What was not done

No guest, tool or SPEC change; no part built with lanes (the poses were laid as art to measure their blocks); no
emulator boot (the pictures are the compile's pixels). No soak rows. The art pieces are study quality, to show
the shapes and the costs; E4's windmill in particular is a sketch.
