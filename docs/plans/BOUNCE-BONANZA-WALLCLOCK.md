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
