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
130.27). A floor in front then covers the face's lower part, so where the
face visibly ends is always **the floor's back edge**: one black outline
pixel, the same line whether that floor is the column's neighbour or a
floor further away with void in between.

The projection makes it exact. `y = 8 (wx + wy) - z` (130.10.2), so a floor
one cell further forward and **one unit higher** lands on the same line as
the neighbouring floor would. [edges/edgedemo.bbc](edges/edgedemo.bbc) is
that scene: a wall row nine units high, on the LEFT a floor at five units
that touches it, and on the RIGHT one row of void and then a floor at six.
In the top-left panel of [edge-joins.png](edges/edge-joins.png) the two halves are drawn the same.
The diagonal alias of 130.47.1 is the same effect: a cell one step forward
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
| J4 heavy joint | the face's bottom 1 px drawn black, so a contact line is 2 px | the opposite convention to G2, and too close to the rejected 2 px contour (130.47.1) to recommend |

### Cues for a column standing over a GAP

| | what | reads as |
|---|---|---|
| **G2 void band** | the face's bottom 3 visible px drawn black | dark space under the column's edge: you see the void between it and the floor |
| **G5 measured gap** | G2, but `1 + 2 x cells of void` px (1 - 7) | the same, and a FAR column shows a wider band than a near one. This is the "far away" half of the brief |
| G1 dissolve | the face fades to black over 8 px, an ordered dither | the column sinks into the abyss. A dither again: the contact band's "fuzz when moving" verdict (130.47.1) is a risk |
| G3 teeth | a sawtooth notch, 1 - 5 px, period 8 | a broken or icicled bottom, a cousin of the pathway's floating crystal look. Busy over a long wall |
| G4 band + fringe | 2 px black, then 2 px of 50% dither | between G1 and G2 |

**The pictures** (CGA at 2x, the left/right test scene first):

- [edge-joins.png](edges/edge-joins.png): today, J1 - J4, G4
- [edge-gaps.png](edges/edge-gaps.png): G1 - G3, and the pairs J1+G2, J3+G1, J2+G2
- [edge-measured.png](edges/edge-measured.png): G5 and J1+G5
- [roll.png](edges/roll.png), [roll-measured.png](edges/roll-measured.png), [mill.png](edges/mill.png): the same on the real courses
- [edge-herc.png](edges/edge-herc.png): the Hercules translation (130.11.3), horizontally squashed. The black bands survive it; the cyan plinth mostly does not

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
   do (130.47.5): no cue on, or because of, a cell that moves. A cue is
   computed from the pose-0 geometry only.
2. **PLAYGROUND is at `BLK_MAX`** already (130.47.5). Any option here makes
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

Neither is a contour line (130.47.1's rejected 1 - 2 px lines on depth
breaks), but G2 is closest to one. The way to tell is to play it, which is the next
step if the owner picks it: a knob build of the chosen pair (as `BZSHADOW`
was), with the dynamic-cell rule above, on FIRST, MILL and ROLL.

## 6. Reproducing

From the repository root, after `make deps`:

    python3 docs/plans/bonanza-courses/edges/edges.py OUT seamless+void \
        docs/plans/bonanza-courses/edges/edgedemo.bbc apps/bonanza/courses/roll.bbc
    python3 docs/plans/bonanza-courses/edges/sheet.py OUT roll 90,600,350,800 2 roll.png \
        "none=today,seamless+void=J1+G2"

`edges.py` turns the compile cache off for its own run (a styled picture
must never be stored under the real course's key).
