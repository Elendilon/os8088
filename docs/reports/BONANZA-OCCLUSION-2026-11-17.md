# BONANZA: what occlusion costs, and what could replace it (2026-11-17)

*This is a dated measurement of one tree: `28f4859dd`, branch
`bounce-bonanza`, measured on branch `bounce-bonanza-occlusion`. It answers
the owner's question of 2026-11-17: is most of a course's size occlusion, and
can occlusion be done more cheaply, not pixel-perfect, with less on the disk,
less in RAM and less CPU? It was done on the host only. No guest, course,
tool or SPEC.md byte changed. The ranked options and the plan are
[BOUNCE-BONANZA-OCCLUSION.md](../plans/BOUNCE-BONANZA-OCCLUSION.md).*

**How the figures are marked:**
- **MEASURED**: computed by the shipped tool's own code on the real courses:
  `tools/bbcourse.py`'s `_occluders`, `block_queries`, `merge_records`, the
  dither, `encode_part`, `stored_form` and `packed_len`, which packs as
  `os88pkg` packs a part.
- **SAMPLED**: MEASURED over a Monte Carlo of the binding physics model
  (`bbcourse.Physics`). Such a figure is a statement about the positions the
  sample reached.
- **PREDICTED**: priced from the 8088's instruction timings, from routines
  that were sketched rather than written.

No emulator was run. No figure here decides between options that a
MartyPC run could separate, because what decides A is a routine that does not
exist yet. Pricing it is the plan's wave A1.

**The scripts** are in `docs/plans/bounce-bonanza/`. Nothing in `make` runs
them. Their raw outputs are in `docs/plans/bounce-bonanza/occ-out/`.

| script | what it does |
|---|---|
| `occproto.py` | every option as a transform of the course's reachable set or its occluder pixels, run through the tool's pipeline to a part, and that part's bytes |
| `occmc.py` | the Monte Carlo, and the visual error of each option over its sampled positions |
| `occaskip.py` | the model alone, with no record, on the sampled falls |
| `occframes.py` | the occluder pass walked on each course's demo and priced |
| `occpics.py` | the fall pictures |
| `occ-out/summarize.py` | the totals |

## 1. Where a course's bytes are (MEASURED)

`bbcourse.py --sizes` on the seven `BZ_COURSES` gives each section's RAM and
its packed share. The share is the section's marginal bytes in the whole part,
packed. Grouped (`occ-out/sizes.txt`, `--sizes`' output):

| group | sections | RAM | LZ4 | LZB |
|---|---|---|---|---|
| **occlusion** | `I R K O` | 59,948 (**25.2%**) | 17,607 (**31.0%**) | 14,361 (**31.1%**) |
| **the picture** | `M B` | 135,856 (**57.1%**) | 29,066 (**51.2%**) | 24,071 (**52.2%**) |
| the grid | `G C D T` | 35,702 (15.0%) | 5,219 (9.2%) | 3,977 (8.6%) |
| props | `P` | 4,959 (2.1%) | 2,509 (4.4%) | 2,293 (5.0%) |
| the route | `W` | 364 | 181 | 184 |
| **the seven parts** | | **237,789** | **56,796** | **46,147** |

The single largest items:
- **The map in RAM**: 97,792 bytes, 41% of all course RAM. It is two bytes a
  block, and it packs to 9,986.
- **The blocks on the disk**: 19,080 bytes LZ4, 34% of the packed parts.
- **The records**: 14,702 LZ4 (26%) and 49,612 of RAM (21%).

Each course:

| course | RAM | occlusion | picture | LZB | occlusion | picture |
|---|---|---|---|---|---|---|
| BENCH | 40,156 | 12,522 (31%) | 21,440 (53%) | 6,011 | 2,465 (41%) | 2,691 (45%) |
| FIRST | 10,140 | 1,852 (18%) | 6,880 (68%) | 2,194 | 583 (27%) | 1,192 (54%) |
| TRIAL | 16,880 | 3,644 (22%) | 10,864 (64%) | 3,798 | 951 (25%) | 2,295 (60%) |
| MILL | 29,975 | 6,486 (22%) | 18,688 (62%) | 7,786 | 1,708 (22%) | 4,805 (62%) |
| MOON | 43,087 | 12,472 (29%) | 22,816 (53%) | 8,318 | 2,989 (36%) | 4,017 (48%) |
| PEAK | 48,129 | 14,438 (30%) | 24,944 (52%) | 10,325 | 3,706 (36%) | 4,891 (47%) |
| PLAY | 49,422 | 8,534 (17%) | 30,224 (61%) | 7,715 | 1,959 (25%) | 4,180 (54%) |

**In context**, each part was also packed with no occluder at all: `R`, `K`,
`O` empty and `I` all zeros. The difference is what occlusion costs, the way
the disk sees it:

| | today | no occluders | occlusion costs |
|---|---|---|---|
| LZ4 | 56,796 | 38,721 | **18,075 (31.8%)** |
| LZB | 46,147 | 31,491 | **14,656 (31.8%)** |
| RAM | 237,789 | 179,027 | **58,762 (24.7%)** |

**So occlusion is about a third of the disk and a quarter of the RAM, and the
picture is the majority.** This agrees with the main session's `--sizes`
reading (about 30% of RAM and 35 - 41% of LZ4 on BENCH, MOON and PEAK; the map
and the blocks about 52% of RAM and 45% of disk). On the three heaviest
courses occlusion is the larger share: 41% of BENCH's LZB and 36% of MOON's
and PEAK's.

## 2. What lays the records (MEASURED, SAMPLED)

A record exists because SOME reachable position lays it (SPEC.md 128.10.4.4,
128.11.4.4). Re-running the tool's occluder pipeline with parts of the
reachable set removed shows which positions pay for which records
(`occproto.py`; `occ-out/proto1.txt`):

| reach | records (7 courses) | LZB | RAM |
|---|---|---|---|
| all of it (today) | 12,403 | 46,147 | 237,789 |
| **no position in a VOID cell** | **5,190 (42%)** | 38,706 (-7,441) | 206,309 (-31,480) |
| VOID positions only in PITS (option (c) of 128.11.4.5) | 5,604 | 39,486 (-6,661) | 208,451 |
| VOID positions only at or above the lowest floor within two tiles (`vlow`) | 8,460 | 42,506 (-3,641) | 221,657 |
| the same, the last 16 px of each fall only (`vlow8`) | 10,628 | 44,931 (-1,216) | 230,743 |
| `vlow`, and cut at WALLs the ball cannot clear (option T) | 8,460 | no change from `vlow` | |

- **58% of the records (7,213) exist only for a ball in a VOID cell.**
  Those are the positions of a fall off an edge, or of a flight over a gap.
  On every course, the reach puts a ball in every cell of the two-tile band
  round every edge, at every height from the kill to the apex.
- **The fall's last part is not where the records are.** Dropping everything
  below the lowest floor nearby (`vlow`) takes only 41% of the void records.
  The rest are positions just behind and below an edge, where today's ball
  is partly hidden.
- **A wall-aware reach changes nothing.** No course has a cell that only an
  unclearable wall separates from the ball.
- **The Monte Carlo** gives a lower bound on what a perfect reach would need
  (`occmc.py`, 4,000 - 6,000 trials a course; `occ-out/mc2.txt`). Each
  trial starts on a random floor cell at a random ground velocity, with a
  random ball, then plays random held arrows, Hops and Grip for up to 300
  steps or until a fall. The records some sampled position lays a pixel of:

  | | BENCH | FIRST | TRIAL | MILL | MOON | PEAK | PLAY |
  |---|---|---|---|---|---|---|---|
  | any sampled position | 62% | 63% | 81% | 71% | 48% | 55% | 63% |
  | a non-VOID one | 30% | 15% | 22% | 18% | 33% | 34% | 15% |

  The truth lies between this and today's 100%. So even a perfect reach
  analysis would save less than option A below, and it would need a
  state-space proof of the physics.

## 3. Every option's bytes (MEASURED)

Each option is a part built by the tool's own pipeline, so the bytes include
everything: the new merge, the dither, the deduplicated masks, the WDIFF
records, the COUNTS index and the zero holes. `occ-out/summary.txt` has the
totals; `proto1` - `proto4.txt` have each course.

| option | records | RAM | LZ4 | LZB | dRAM | dLZ4 | dLZB |
|---|---|---|---|---|---|---|---|
| today | 12,403 | 237,789 | 56,796 | 46,147 | | | |
| no occluders | 0 | 179,027 | 38,721 | 31,491 | -58,762 | -18,075 | -14,656 |
| (c) / no VOID record | 5,190 | 206,309 | 47,610 | 38,706 | -31,480 | -9,186 | -7,441 |
| pits only | 5,604 | 208,451 | 48,573 | 39,486 | -29,338 | -8,223 | -6,661 |
| vlow | 8,460 | 221,657 | 52,445 | 42,506 | -16,132 | -4,351 | -3,641 |
| **V** (no VOID record, the ghost height in the cell's flag nibble) | 5,235 | 206,489 | 48,493 | 39,397 | -31,300 | -8,303 | -6,750 |
| the model, VOID cells, depth 3 + residual (`avoidR3`) | 7,447 | 217,947 | 52,528 | 42,730 | -19,842 | -4,268 | -3,417 |
| **AV**: the model, VOID cells, depth 4 + residual (`avoidR4`) | 6,267 | 212,237 | 50,413 | 40,993 | -25,552 | -6,383 | -5,154 |
| the model everywhere, depth 3 + residual (`res3`) | 3,381 | 199,667 | 47,751 | 38,781 | -38,122 | -9,045 | -7,366 |
| **A4R**: the model everywhere, depth 4 + residual (`res4`) | 1,958 | 191,743 | 44,646 | 36,285 | -46,046 | -12,150 | -9,862 |
| A3R-V: depth 3, residual over non-VOID positions only (`res3+V`) | 887 | 185,329 | 41,579 | 33,812 | -52,460 | -15,217 | -12,335 |
| **A4R-V**: depth 4, residual over non-VOID positions only (`res4+V`) | 729 | 184,325 | 41,108 | 33,425 | -53,464 | -15,688 | -12,722 |

**V costs bytes for its ghost height.** The nibble in every VOID cell makes
the `C` section less regular: about +60 - 170 LZ4 a course over (c)
(`proto1.txt`'s `novoid` against `vghost`).

**Graded V does not pay.** Keeping records for the first 8 or 16 px below `H`,
so the start of the sink is exact, gives back most of the saving. FIRST has 239
records that only VOID positions lay. V drops all of them; graded V drops 108
(8 px) or 72 (16 px). This is from `occproto.py --only base,vghost,vghost8,vghost16`
on FIRST: 291 -> 52, 183 and 219 records.

### 3.1 The model (option A), in detail

**The rule, and the model of it.** The rule (128.10.4.4) lays a pixel when it
was drawn by a cell row in front of the ball's and its geometry is above the
ball. In the picture as built, every face hangs to the ground plane (128.27).
So in any screen column, everything below the top edge of a cell in front is
that cell's top, its face, or a nearer cell's.

The model therefore hides ball pixel `(x, y)` when two things hold:
- some FRONT cell `(wx + i, wy + j)` (`i, j >= 0`, `0 < i + j <= D`) is a plain
  whole cell, its highest corner above `z + m`;
- `y` is at or below its top edge in column `x`.

The prototype takes each cell's top edge from an owners' render: the first
line each cell owns in each column (`occproto.Analytic`). A guest computes the
same edges from the cell's corners. The binding model has to be written that
way (the plan's A0.1). A front cell with a prop (`OBS`), a split cell, or a
cell past depth `D` is invisible to the model.

**Its residual** (`occproto.residual`) is computed over the whole reachable
set, the same box `_occluders` walks. It is every occluder pixel the rule lays
at some position where the model does not. Records cut from those pixels by
the tool's own grouping, merge and bounds lay what the model misses, so the
union lays at least what the rule lays.

**How close the model is** (SAMPLED, depth 2 except where marked;
`occ-out/mc2.txt`, `askip-*.txt`):

| | BENCH | FIRST | TRIAL | MILL | MOON | PEAK | PLAY |
|---|---|---|---|---|---|---|---|
| non-VOID positions the model can read (front cells with no prop or split): WRONG-HIDE, the share of ball pixels it hides that the rule does not | 0.1% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0% | 0.0% |
| the same positions: frames with a quarter of the ball wrong, model ALONE | 0.0% | 0.0% | 0.0% | 1.3% | 1.6% | 7.1% | 0.2% |
| VOID positions, model alone, depth 2 / 3 / 4: frames with a quarter of the ball wrong | 1.5 / 0.4 / **0.0%** | 1.7 / 0.7 / 0.6% | 4.1 / 1.7 / **0.2%** | 2.6 / 0.9 / **0.2%** | 12.2 / 9.8 / 8.1% | 6.8 / 5.2 / 4.1% | 2.5 / 1.7 / 1.6% |

Where the model alone is wrong, it is wrong by DRAWING OVER: a prop's or a
split cell's pixels it cannot see, or a cell past its depth. The residual
records exist to fix exactly that. With them, A4R's only error is WRONG-HIDE,
which is at most 0.1%.

The model alone stays wrong on MOON and PEAK at depth 4 for two reasons:
- MOON's coast is diagonal split cells (128.24.14);
- PEAK's terrain has props and steps more than four rows tall in front of
  its voids.

## 4. CPU (PREDICTED)

`occframes.py` replays each course's demo through the binding model:
- MOON, PEAK and PLAY: the authored `.bzd`;
- FIRST, TRIAL and MILL: the route demo;
- BENCH: the autopilot.

At every step it walks the occluder pass as `bz_occ` does, on the shipped
4-byte part: the gate (OCC airborne, OCCG grounded), the block rows, the
records tested, the GROUPS and the LINES laid. Each frame is priced with
constants ESTIMATED from `bzvideo.inc` as built. They are listed in the
script, at max(EU + EA, 4.34 a byte) x 1.05, one box:

| constant | clk | what it covers |
|---|---|---|
| fixed | 520 | |
| a block row | 210 | |
| a record tested | 45 | |
| `bz_oprep` | 260 | |
| `bz_oand` | 70 + 60 a line | |
| a lay | 430 + 105 a line | |

Every step counts as a frame, so the figures are a cost per PLAYED step, with
the same weighting on every arm. `occ-out/frames2.txt` has the output:

| course, demo | steps | gate open | of them VOID | today | X (active lines) | V | A4R | worst: today / X / V / A4R |
|---|---|---|---|---|---|---|---|---|
| BENCH, autopilot | 3,600 | 2,685 | 0 | 7,129 | 7,048 | 7,129 | 7,862 | 7,490 / 7,480 / 7,490 / 8,860 |
| FIRST, route | 154 | 21 | 21 | 1,587 | 1,587 | 0 | 1,630 | 1,690 / 1,690 / 0 / 1,750 |
| TRIAL, route | 499 | 128 | 22 | 1,718 | 1,661 | 1,511 | 2,102 | 3,020 / 2,185 / 3,020 / 2,510 |
| MILL, route | 778 | 263 | 0 | 3,161 | 2,892 | 3,161 | 4,018 | 7,345 / 6,810 / 7,345 / 9,520 |
| MOON, `moon.bzd` | 1,983 | 1,580 | 50 | 3,373 | 3,106 | 3,216 | 4,874 | 11,350 / 11,545 / 11,350 / 23,840 |
| PEAK, `summit.bzd` | 2,172 | 1,393 | 58 | 4,820 | 4,672 | 4,763 | 7,914 | 13,045 / 13,405 / 13,045 / 24,750 |
| PLAY, `playground.bzd` | 1,504 | 31 | 0 | 2,011 | 1,800 | 2,011 | 2,855 | 3,800 / 3,145 / 3,800 / 4,400 |

- **The pricing is about 0.4 of the MEASURED pass.** 128.15.5.4 measured
  the pass's mean span at 8,059 on MILL and 13,267 on PEAK, CGA, D. The
  priced figures are 3,161 and 4,820. What is missing is mostly the
  two-box frames and the lay's arithmetic per box. **Read today's column as
  a ratio. A4R's ADDITION is the model's own work, and it reads as
  absolute.**
- **The lay dominates.** On PEAK the priced lays are about 60% of the pass:
  4,116 groups and 22,980 lines over 1,393 frames. Only lineclip (X) cuts
  the lay itself: 12% of PEAK's laid lines keep everything, 30% of MOON's,
  37% of MILL's and 60% of PLAY's. Every option that keeps a ball behind
  the scenery pays the rest.
- **A4R adds +0.4k to +3.1k a gated frame, the most on PEAK's demo.** It
  reads 10.2 front cells a frame there (about 80 clk each), 0.92 of which
  reach the footprint (about 750 each), and it builds the masks of the
  covered words (15 - 50 each). These are ESTIMATED from a sketch, not from
  code.
- **The worst column over-states A4R.** It counts a residual group as a lay
  of its own, even where it would AND into a covered word.
- **For calibration**, the red arm `occslow` (+27k a pass frame) cost PEAK
  +11.5 missed refreshes a second (128.15.5.4). Scaled linearly, +3k is about
  +1.3 a second, past the smoothness rule's +1.0. So A4R needs its levers
  (the plan's section 4) or it does not ship.
- **V and AV change only the VOID frames.** Those are 3 - 4% of the open-gate
  frames of MOON's and PEAK's demos, none of MILL's or PLAY's, 17% of
  TRIAL's route, and all 21 of FIRST's route, whose only gated steps are over
  its pit. V makes those frames cheaper. AV makes them about as dear as A4R's.

## 5. What each option looks like

**The measure.** Over the Monte Carlo's sampled positions in VOID cells, each
frame is compared with today's rule as a share of the ball's lit pixels:
- **OVER**: drawn over what hides them today;
- **DIM**: ghosted, though nothing hides them today.

A frame is **wrong** when OVER + DIM is more than a quarter of the ball.
Today's own frames are ghosted by the checker where hidden (128.15.10), so
"hidden" means "shown at 50%".

| frames with a quarter of the ball wrong, sampled VOID positions | BENCH | FIRST | TRIAL | MILL | MOON | PEAK | PLAY |
|---|---|---|---|---|---|---|---|
| (c): drawn over | 12.7% | 7.8% | 14.3% | 15.8% | 28.6% | 20.2% | 11.7% |
| V: ghosted below `H` | 37.4% | 27.4% | 36.6% | 37.5% | 50.7% | 47.3% | 45.5% |
| V(25%): `H` where the cell's mean share hidden reaches 25% | 10.5% | 7.5% | 10.2% | 11.4% | 16.9% | 14.0% | 10.9% |
| V(50%) | 7.5% | 5.9% | 8.3% | 9.6% | 14.2% | 11.2% | 8.8% |
| the model alone, depth 4 (A4R-V's falls) | 0.0% | 0.6% | 0.2% | 0.2% | 8.1% | 4.1% | 1.6% |
| **AV, A4R**: the model + residual | 0 by construction, but WRONG-HIDE (at most 0.1% of pixels) | | | | | | |

V(any) is worse than (c) by this measure. `H` belongs to a whole cell, 16 px
across, so a ball that today is whole for the first frames past an edge is
dimmed for them under V.

**The pictures**: `docs/plans/bounce-bonanza/occ-fall-first.png`,
`occ-fall-mill.png` and `occ-fall-peak.png`. Each shows one back-edge fall
from the model: a ball poked rolling off a floor into the VOID cell behind
it, chosen as the fall with the most partly hidden frames. Eight frames run
down the page from the step before it leaves the floor to its last before the
kill, on the CGA's palette, zoomed 4x. The four columns are:
1. **today**: the shipped records, laid as the card lays them, ghost dither
   and all;
2. **(c)**: the ball drawn whole over the plateau and the props it falls
   behind. This is the fault 128.11.4.5 rejected;
3. **V**: the whole ball ghosted from the first frame whose cell is under
   `H`. On MILL and PEAK it dims 2 - 3 frames before today's ball starts to
   go behind the edge;
4. **A**: the model at depth 2 in the VOID cell, records elsewhere. It is
   today's frame, pixel for pixel by eye, in every frame of all three.

## 6. The data shortcuts (MEASURED)

- **Full-block masks**: 24% (BENCH) to 48% (PEAK) of the part's records lay
  the whole block. The mask index is one byte of the four, and WDIFF and LZ
  pack runs of it already. An implicit "full" index changes the RAM form not
  at all and the packed form by under 1%.
- **A shared mask library**: the seven courses' `K` sections hold 499 masks,
  253 of them distinct across courses, against 256 a byte can index. `K` is
  2,359 bytes LZ4 over the seven, 4% of the disk. Rejected, as 2026-11-14's
  report rejected it (idea G).
- **The mask's lines**: a mask has 5.3 - 6.5 active lines out of 8 (weighted
  by record). That is the basis of option X.
- **A per-block depth map** would be 3 bytes for every map block, 2,368
  (FIRST) to 12,032 (PLAY) of them, against today's 4 bytes a record:
  larger on every course.

## 7. The headroom this buys (MEASURED)

PEAK's part, the fullest, against `PARTMAX` 65,024:

| | RAM | headroom | a block row | rows a part holds |
|---|---|---|---|---|
| today | 48,129 | 16,895 | 339 | 191 |
| V | 40,651 | 24,373 | 286 | 227 |
| AV | 41,957 | 23,067 | 295 | 220 |
| A4R | 36,695 | 28,329 | 258 | 251 |
| A4R-V | 35,141 | 29,883 | 247 | 263 |
| no occluders | 33,953 | 31,071 | 239 | 272 |

## 8. What is MEASURED and what is PREDICTED

- **MEASURED** (host, the tool's own code):
  - every byte figure;
  - every record count;
  - the sections' shares;
  - the mask statistics;
  - the headroom.
- **SAMPLED** (MEASURED over the Monte Carlo; it holds for the positions the
  sample reached):
  - the lower bound on a perfect reach;
  - every visual-error figure;
  - the model's agreement with the rule.
- **PREDICTED**:
  - every clock figure in section 4. The constants are ESTIMATED from
    `bzvideo.inc`, and the model's are ESTIMATED from a sketch of a routine
    that does not exist yet;
  - the guest code sizes in the plan;
  - the smoothness verdict, which only 128.15.5.4's A/B can give.
- **Not measured**:
  - MartyPC (no number here needs it before the routine exists);
  - the pathway's and the title's parts (they carry 454 and 943 records,
    and the pathway floats everywhere: the plan's A0.3 and A0.4).
