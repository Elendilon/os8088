# BOUNCE BONANZA: does a column touch its floor? (options, 2026-11-21)

*A PROPOSAL for the owner to choose from. Nothing here is built: no shipped
course, no SPEC.md section and no guest code changes on `bb-visuals`. The
pictures are host mock-ups from the course tool's own renderer
([edges/edges.py](edges/edges.py) hooks `tools/bbcourse.py`'s `render()`).
Every figure is MEASURED on the host unless marked.*

The owner, 2026-11-21: *"columns have no visual distinction when they are far
away, or adjoined to a floor. It is impossible to tell if there is a gap, or
not. Design some options ... both things that join to the floor when the
column does join, and things that make it look like there is a gap between
the wall and the floor when there is one."*

## 1. Why the picture cannot say it today

Every face over the void hangs down to the course's ground plane (SPEC.md
137.27). A floor in front then covers the face's lower part, so where the
face visibly ends is always **the floor's back edge**: one black outline
pixel, the same line whether that floor is the column's neighbour or a
floor further away with void in between.

The projection makes it exact. `y = 8 (wx + wy) - z` (137.10.2), so a floor
one cell further forward and **one unit higher** lands on the same line as
the neighbouring floor would. [edges/edgedemo.bbc](edges/edgedemo.bbc) is
that scene: a wall row nine units high, on the LEFT a floor at five units
that touches it, and on the RIGHT one row of void and then a floor at six.
In the top-left panel of [edge-joins.png](edges/edge-joins.png) the two halves are drawn the same.
The diagonal alias of 137.47.1 is the same effect: a cell one step forward
on both axes and two units higher.

## 2. What the mock-ups decide, per pixel

For each face pixel the hook records the cell that drew it and which face it is (`sw`, `se`).
A face's **foot** is a pixel of that face with a top of ANOTHER cell
directly under it. That top is the face's visible end. A foot is:

- **JOINED** when the top under it belongs to the record across that face's
  own edge (`(wx, wy + 1)` for `sw`, `(wx + 1, wy)` for `se`). That is a real
  contact.
- **A GAP** otherwise: the face hangs over the void, or it is cut off by
  something nearer that it does not touch. For example, a back wall behind a
  free-standing pillar is a gap at the pillar's top.

Only the face's own pixels at its foot are restyled, and the floor's
outline under it in J1. Nothing moves, and no physics, occluder or replay
input changes. Feet found, joined against gap: FIRST 111 / 46, TRIAL
270 / 104, MILL 442 / 650, ROLL 1,225 / 1,186, MOON 1,394 / 701.

## 3. The options

### Cues for a column that JOINS its floor

| | what | reads as |
|---|---|---|
| **J1 seamless join** | the floor's black outline under a joined foot is not drawn: the face's ink meets the floor's ink directly | one piece of masonry. This REMOVES ink and adds none |
| J2 cyan plinth | the face's bottom 2 px drawn cyan | a skirting board. Lost on Hercules (see below) |
| J3 white sill | the face's bottom 1 px drawn white | a lit seam. Fine on CGA, faint at a distance |
| J4 heavy joint | the face's bottom 1 px drawn black, so a contact line is 2 px | the opposite convention to G2, and too close to the rejected 2 px contour (137.47.1) to recommend |

### Cues for a column standing over a GAP

| | what | reads as |
|---|---|---|
| **G2 void band** | the face's bottom 3 visible px drawn black | dark space under the column's edge: you see the void between it and the floor |
| **G5 measured gap** | G2, but `1 + 2 x cells of void` px (1 - 7) | the same, and a FAR column shows a wider band than a near one. This is the "far away" half of the brief |
| G1 dissolve | the face fades to black over 8 px, an ordered dither | the column sinks into the abyss. A dither again: the contact band's "fuzz when moving" verdict (137.47.1) is a risk |
| G3 teeth | a sawtooth notch, 1 - 5 px, period 8 | a broken or icicled bottom, a cousin of the pathway's floating crystal look. Busy over a long wall |
| G4 band + fringe | 2 px black, then 2 px of 50% dither | between G1 and G2 |

**The pictures** (CGA at 2x, the left/right test scene first):

- [edge-joins.png](edges/edge-joins.png): today, J1 - J4, G4
- [edge-gaps.png](edges/edge-gaps.png): G1 - G3, and the pairs J1+G2, J3+G1, J2+G2
- [edge-measured.png](edges/edge-measured.png): G5 and J1+G5
- [roll.png](edges/roll.png), [roll-measured.png](edges/roll-measured.png), [mill.png](edges/mill.png): the same on the real courses
- [edge-herc.png](edges/edge-herc.png): the Hercules translation (137.11.3), horizontally squashed. The black bands survive it; the cyan plinth mostly does not

## 4. What it costs

Picture only, so the cost is **blocks**: every distinct 8 x 8 block is 16
bytes of the course part before packing, and `BLK_MAX` is 1,024. The proxy below counts distinct
blocks in the mock-up picture (aligned at line 0, so off from the
part's own count by the y0 offset, but comparable column to column):

| | FIRST | TRIAL | MILL | ROLL | MOON |
|---|---|---|---|---|---|
| today | 122 | 214 | 465 | 497 | 361 |
| J1 seamless | +0 | +5 | +7 | +7 | +2 |
| G2 void band | +0 | +4 | +17 | +28 | +23 |
| G5 measured | +0 | +10 | +36 | +63 | +62 |
| G1 dissolve | +0 | +10 | +29 | +39 | +34 |
| G3 teeth | +1 | +2 | +19 | +30 | +29 |
| **J1 + G2** | +0 | +8 | +17 | +29 | +23 |
| J1 + G5 | +0 | +14 | +36 | +64 | +62 |
| J3 + G1 | +2 | +13 | +35 | +52 | +47 |

So J1+G2 is about 3 - 6% more blocks on a busy course, and G5 about twice
that. These are proxies; the real figure is the part's LZB size from
`bbcourse.py`, taken once the option is chosen.

**Two things a real build must handle that the mock-up does not:**

1. **Cells that change pose.** A cue depends on the neighbour, so when a
   cell vanishes or moves (a crack, a bridge, a see-saw, a turntable), its
   neighbours' feet turn from joined to gap. The cue is then different in
   every pose, which widens that prop's lanes. PLAYGROUND's vanishing crack at
   (35, 16) is refused under every style for exactly this ("its picture
   changes over 88 x 23 blocks"). The rule wants what cast shadows already
   do (137.47.5): no cue on, or because of, a cell that moves. A cue is
   computed from the pose-0 geometry only.
2. **PLAYGROUND is at `BLK_MAX`** already (137.47.5). Any option here makes
   that worse, so it needs the same fallback as shadows, or the owner's
   call on that course.

## 5. Recommendation

**J1 + G2, seamless join and void band.** The two say opposite things in
the plainest way the 4-colour picture has. Touching is drawn as no line at
all, and a gap is drawn as a strip of the void you would see through it.
Both are SOLID, so neither is a dither that shimmers when the picture
scrolls, and both survive the Hercules translation. J1 costs almost
nothing. If the "far away" case still reads poorly in play, **G5** is the
same idea with the band scaled to the gap and costs about twice the blocks.

Neither is a contour line (137.47.1's rejected 1 - 2 px lines on depth
breaks), but G2 is closest to one. The way to tell is to play it, which is the next
step if the owner picks it: a knob build of the chosen pair (as `BZSHADOW`
was), with the dynamic-cell rule above, on FIRST, MILL and ROLL.

## 5b. Manual, not automatic (the owner, 2026-11-21): SPEC.md 137.57

*"In the places that this works, it completely works. And then, its spread all over a ton of places that
don't need it and it just looks weird ... So lets make it manual."* The `BZEDGE=1` knob below is DELETED. G4 is now
the course statement `gap <shape> [sw|se]`, and the detector (`c.gap_faces`, `bbcourse.py --gaps`) lists the
candidates for the course builder's overlay to show, so the owner can click through them. SPEC.md 137.57 is the
contract. The sizes in 5a were for G4 on EVERY candidate face; a hand-marked course pays for its own marks only.

## 5a. G4 as a build: `BZEDGE=1` (the owner, 2026-11-21; the knob since deleted, 5b)

*"Can you put the G4 band+fringe only into a build, and see how it affects sizes?"* G4 is now a knob, off by
default: `make BUILD=build/edge BZDOWN=1 BZEDGE=1 bonanzadisk` (BZDOWN puts DOWNHILL DECISION in TRIAL's
place on the pathway). `bbcourse.py --edge` runs `look_edge()` after the picture is drawn. It uses the same
per-pixel geometry buffers as cast shadows, and its rule is the mock-up's: a foot is JOINED only when the top under it
is the cell across that face's own edge, and otherwise the face's last 2 px go black and the 2 above them 50%.
It follows the shadows' two rules (137.47.5):

- **no band on, or because of, a cell that moves or vanishes** (`_SHADOW_DYN`: the face's cell, the top's
  cell and the cell across the face's edge). So every crack, bridge, see-saw and turntable compiles.
- **a course over `BLK_MAX` with it is compiled again without it**, and the run says so. PLAYGROUND is
  1,038 blocks with the band (14 over), so it plays today's picture.

MOON's and PEAK's demos are re-stamped with the build's identity, as a shadows build does. The band changes
ink only, and the replay check after the re-stamp still passes.

**Sizes, MEASURED** at this commit, `BZDOWN=1` both sides. Raw is the part as stored, so it is also the
RAM the part takes once loaded. LZB is each part packed whole by `os88lz.lzb_compress`:

| course | raw | +G4 | | LZB | +G4 | |
|---|---|---|---|---|---|---|
| FIRST | 10,199 | 10,215 | +16 | 1,830 | 1,863 | +33 |
| TRIAL | 16,364 | 16,396 | +32 | 3,545 | 3,590 | +45 |
| MILL | 27,706 | 27,978 | +272 | 6,900 | 7,143 | +243 |
| MOON | 37,788 | 38,156 | +368 | 7,239 | 7,506 | +267 |
| PEAK | 42,478 | 42,830 | +352 | 8,973 | 9,298 | +325 |
| PLAY | 58,562 | 58,562 | +0 (fell back) | 15,427 | 15,427 | +0 |
| ROLL | 43,506 | 43,922 | +416 | 9,506 | 9,893 | +387 |
| HOP | 38,901 | 39,157 | +256 | 10,039 | 10,240 | +201 |
| DOWN | 127,684 | 128,484 | +800 | 16,269 | 16,668 | +399 |
| **total** | 403,188 | 405,700 | **+2,512** | 79,728 | 81,628 | **+1,900** (+2.4%) |

The title's part grows 128 bytes raw. `BONANZA.O88` as shipped goes from 167,385 to 169,337 bytes
(**+1,952**). A raw delta is 16 bytes a block, so DOWN gains 50 blocks, ROLL 26 and HOP 16. On
`bonanza360.img` the free space goes from 186,368 to 184,320 bytes.

## 6. Reproducing

From the repository root, after `make deps`:

    python3 docs/plans/bonanza-courses/edges/edges.py OUT seamless+void \
        docs/plans/bonanza-courses/edges/edgedemo.bbc apps/bonanza/courses/roll.bbc
    python3 docs/plans/bonanza-courses/edges/sheet.py OUT roll 90,600,350,800 2 roll.png \
        "none=today,seamless+void=J1+G2"

`edges.py` turns the compile cache off for its own run (a styled picture
must never be stored under the real course's key).
