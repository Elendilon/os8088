# BOUNCE BONANZA: occlusion, computed instead of stored

*AV (waves A0 and A1) IS BUILT on branch `bounce-bonanza-av` (2026-11-17), SPEC.md 128.29; the story
rows below say what landed and what was measured. A3 and V are not built.*

*A PROPOSAL for the owner to review (2026-11-17). Nothing here is built: the
shipped guest, the shipped course format and SPEC.md 128 are unchanged on this
branch. The measurements, the pictures and how each figure was taken are in
[the report](../reports/BONANZA-OCCLUSION-2026-11-17.md). The contract this
would become is SPEC.md section **128.29**, reserved and not yet written. The parallel two-segment-course
work adds 128.28. This plan does not touch it, and section 7 says what each
option gives it.*

The owner, 2026-11-17: *"Course size is too big, and most of it seems to be
occlusion ... It does not need to be pixel-perfect or the same as today. Can
we just store less? ... Ideally smaller on disk, smaller in RAM, and less CPU
per frame."*

## 1. The answer in one screen

- **Occlusion is about a third of a course, not most of it.** This is
  MEASURED on the seven `BZ_COURSES` at `28f4859dd`. The occluder sections
  `I R K O` are **31% of the packed parts** (LZB 14,361 of 46,147; LZ4
  17,607 of 56,796) and **25% of the parts' RAM** (59,948 of 237,789).
  Packing each part with and without its occluders gives the cost in
  context: **14,656 bytes LZB and 58,762 bytes of RAM** over the seven.
  **The picture is the majority**: the map and the blocks are 52% of the
  packed parts and 57% of the RAM. The map alone is 41% of all course RAM.
- **58% of today's records exist only for a ball in a VOID cell**, one
  that is falling off an edge or in the air over a gap. These are the
  cheapest records to lose. They are also the ones the earlier option (c)
  lost visibly (SPEC.md 128.11.4.5).
- **Most records can be COMPUTED instead.** The ball is hidden by the cells
  in front of it that rise above it, and everything under such a cell's top
  edge is that cell's own top and face, because every face now reaches the
  ground plane (SPEC.md 128.27). A model reads up to 14 cells in front of
  the ball from the grid: their heights and their top edges. Over about 2
  million sampled positions it hides **at most 0.1% of the ball's pixels that
  the rule does not**. Records are then needed only for what the model cannot
  see, as **RESIDUAL** records that the guest walks exactly as it walks
  today's. That covers a prop's drawing, a split cell, a floating face and a
  cell further away.
- **Everywhere (A4R)**:
  - records fall from 12,403 to 1,958 over the seven courses (**-84%**);
  - the parts lose **9,862 bytes LZB**, which is 67% of what occlusion
    costs on the disk, and **46,046 bytes of RAM**;
  - PEAK's part has **28.3 KB of headroom** where it has 16.9 KB today.

  Whatever the rule shows hidden stays hidden: the union of the model and
  the residual records lays at least what the rule lays.
- **The CPU is where it costs.** No option here makes the occluder pass
  much cheaper, because what dominates the pass is the LAY: copying the
  picture back over the ball. Every option that keeps the ball behind the
  scenery pays for that. Computing a mask costs more than reading a stored
  one: **+0.4k to +3.1k clocks on a frame whose gate is open**, PREDICTED
  (PEAK's demo the most). So the honest answer to "all three" is **disk and
  RAM, yes, by a lot; CPU, no**.
- **In the VOID cells alone (AV)** the model runs only on the frames of a
  fall. On the long demos that is 3 - 4% of the open-gate frames (MOON,
  PEAK; none on MILL's or PLAY's), so its CPU cost is near zero. It still saves **5,154 bytes LZB and 25,552
  bytes of RAM**, and it is exact-or-over like A4R.

**Recommended:** build the model once, and ship it in two steps. **First in
the VOID cells (AV)**, which has no CPU risk. Then **everywhere (A4R)**, once
the guest's routine is measured and the extension passes the owner's
smoothness rule (SPEC.md 128.15.5.4) as an A/B. **Option V**, which ghosts the
falling ball, is the cheap alternative if the owner would rather not have a
rasterizer in the guest. It looks worse (section 3).

## 2. The options in one table

The figures are for the seven `BZ_COURSES` together:
- **Bytes** are MEASURED on the host by the shipped tool's own pipeline and
  packers (the report, section 3).
- **Clocks** are PREDICTED (section 4).
- **"Looks"** is MEASURED against today's rule over the Monte Carlo's
  sampled falls (the report, section 5). It is the share of frames that get
  more than a quarter of the ball wrong.

`BONANZA.O88` ships its parts as LZB (SPEC.md 128.27.7).

| option | records | parts, LZB / LZ4 | RAM | clk on a frame whose gate is open | looks | guest code | risk |
|---|---|---|---|---|---|---|---|
| today | 12,403 | 46,147 / 56,796 | 237,789 | priced 1.6 - 7.1k a course (MEASURED pass, CGA: MILL 8.1k, PEAK 13.3k) | the rule | - | - |
| no occluders (the floor) | 0 | 31,491 / 38,721 | 179,027 | 0 | the ball over everything | - | - |
| **AV**: the model in VOID cells, residual records there, today's records elsewhere | 6,267 | **40,993 / 50,413** (-5,154 / -6,383) | **212,237** (-25,552) | today's, except on a fall frame (3 - 4% of the long demos' open-gate frames) | exact or over-hidden | **+700 - 1,000 bytes** (the model) | medium |
| **A4R**: the model everywhere (front cells to depth 4) + residual records | 1,958 | **36,285 / 44,646** (-9,862 / -12,150) | **191,743** (-46,046) | **+0.4k to +3.1k** (BENCH +0.7k, MILL +0.9k, MOON +1.5k, PEAK +3.1k) | exact or over-hidden (at most 0.1% of pixels) | as AV | **high**: the CPU |
| A4R-V: A4R with no residual for a VOID cell | 729 | 33,425 / 41,108 (-12,722) | 184,325 (-53,464) | as A4R | falls near props or split cells partly drawn over: 0 - 8% of fall frames (MOON 8.1%, PEAK 4.1%) | as AV | high |
| **V**: no VOID record; below a per-cell height the WHOLE ball is ghosted | 5,235 | 39,397 / 48,493 (-6,750 / -8,303) | 206,489 (-31,300) | **cheaper** on a fall frame | the ball dims early: **27 - 51%** of fall frames; with a 50% threshold, 6 - 14% | +60 - 100 bytes | low |
| (c): no VOID record and nothing in its place (rejected, 128.11.4.5) | 5,190 | 38,706 / 47,610 | 206,309 | as V | the ball drawn OVER what it falls behind: 8 - 29% of fall frames | - | low |
| vlow: no record below the lowest floor within two tiles | 8,460 | 42,506 / 52,445 (-3,641) | 221,657 | as V, on those frames | only the last part of a fall | +60 | low |
| T: the reach cut at walls the ball cannot clear | 12,403 | no change | no change | 0 | - | 0 | - |
| X: lay only a mask's active lines (CPU only) | 12,403 | 0 (built at the launch) | +256 bss | -3% (PEAK) to -10% (MILL, PLAY) of the priced pass | the same | +40 | low |
| data shortcuts: an implicit full mask, a shared mask library, a per-block depth map | | each under 1% of the disk, or worse | | | | | rejected |

## 3. The options explained

### The model, and the residual (AV and A4R)

**The model.** Take a ball in cell `V = (wx, wy)` at height `z`, with margin
`m`. It is hidden at picture pixel `(x, y)` when both of these hold:
- one of V's FRONT cells is a plain whole cell whose highest corner is above
  `z + m`. The front cells are `N = (wx + i, wy + j)` with `i, j >= 0` and
  `0 < i + j <= 4`: 14 cells;
- `y` is at or below that cell's top edge in column `x`.

Below that edge the column is N's own top, then N's face down to the ground
plane (128.27), then nearer cells. Every one of them is in front of the ball.

The model reads only the grid. N's `z0`, `sx`, `sy` and kind give its four
corners, and its top edge is two straight segments on the screen. It passes
over any front cell it cannot read: a prop's cell (`OBS`), a split cell
(kinds 4 - 6) and a floating cell.

**The residual.** The tool finds, over the whole reachable set, every
occluder pixel the rule lays at some position where the model does not. It
cuts records from those pixels alone, by today's rule, merge, bounds, dither
and 4-byte form. The guest runs the model, then walks the residual records
exactly as it walks today's, and both lay into one mask (`bz_omsk`). So the
union lays at least what the rule lays, at every reachable position.

The only difference from today is a pixel the model hides and the rule does
not (**WRONG-HIDE**): 0.00 - 0.1% of the ball's pixels over the samples. This
is a pixel of a lower cell in front, under a taller cell's face, and the
checker dither shows the ball through it anyway.

**AV** uses the model only when the ball's cell is VOID, a test the guest
already makes. Everywhere else it walks today's records. **A4R** uses the
model in every cell. The guest code is the same; the TOOL decides which
records exist.

**What it measures** (host; the report's section 3 has every course and
every depth):

| course | records today -> AV -> A4R | LZB today -> AV -> A4R | RAM today -> AV -> A4R |
|---|---|---|---|
| BENCH | 2,660 -> 1,307 -> 163 | 6,011 -> 4,805 -> 4,040 | 40,156 -> 34,474 -> 29,268 |
| FIRST | 291 -> 88 -> 36 | 2,194 -> 1,892 -> 1,751 | 10,140 -> 9,130 -> 8,760 |
| TRIAL | 707 -> 337 -> 123 | 3,798 -> 3,526 -> 3,253 | 16,880 -> 15,490 -> 14,400 |
| MILL | 1,279 -> 437 -> 144 | 7,786 -> 6,947 -> 6,448 | 29,975 -> 26,391 -> 24,715 |
| MOON | 2,535 -> 1,648 -> 528 | 8,318 -> 7,673 -> 6,371 | 43,087 -> 39,287 -> 33,835 |
| PEAK | 3,079 -> 1,608 -> 486 | 10,325 -> 9,104 -> 7,628 | 48,129 -> 41,957 -> 36,695 |
| PLAY | 1,852 -> 842 -> 478 | 7,715 -> 7,046 -> 6,794 | 49,422 -> 45,508 -> 44,070 |

Under A4R the fullest block is 2 - 3 records on six courses. BENCH keeps one
residual block at 4, the bound (128.11.4.2), and its fullest row falls from 77
to 23.

**The risk** is that the guest's model and the tool's must agree to the
pixel. So the tool's model is written from the PART's grid bytes alone, and
the guest's routine is checked against it under unicorn before any course
ships it (wave A1).

**The void choice inside A4R (the owner's).** A4R keeps residual records for
a ball in a VOID cell too. Most of them are for the deep positions of a fall,
which the conservative reach puts under every edge. A4R-V drops them and lets
the model alone draw a fall. Over the sampled falls, the share of frames with
more than a quarter of the ball wrong is:
- on plain geometry, nearly none: BENCH 0.00% (at depth 4), MILL 0.17%,
  TRIAL 0.20%;
- in front of props and split cells, more: PLAY 1.7% (at depth 3), PEAK
  4.1%, and MOON 8.1% (MOON's diagonal coast).

A4R-V buys about 2.9 KB more LZB over the seven courses for that.

### V: the falling ball ghosted

No record is laid for a ball in a VOID cell, except in the lift's shaft. In
its place the tool stores a GHOST height `H`, in 8 px steps above the kill, in
the VOID cell's free flag nibble (bits 4 - 7, which hold a goal's exit on a
goal cell). A ball in a VOID cell below `H` is drawn whole through the checker:
the sprite's mask ORed with it, 2 more instructions a word. Above `H` nothing
lays, by `H`'s definition.

It is **cheap, and it looks different**. `H` is set per CELL, and a cell is
16 px across. A ball leaving a back edge is ghosted as soon as ANY position in
its cell would be partly hidden, so it dims a frame or three before today's
ball starts to go behind the edge. The pictures show this in their third
column (`bounce-bonanza/occ-fall-mill.png`, `occ-fall-peak.png`).

Over the sampled falls, 27 - 51% of frames have more than a quarter of the ball
wrong, against 8 - 29% for (c). A threshold brings that down to 6 - 14%: `H` is
set where the cell's average share hidden reaches 50%. The price is a partly
hidden ball drawn over its occluder above `H`. The bytes are the same either
way.

### X: lay only the active lines

A group lays every footprint line of its block row, but its mask often keeps
whole lines. On TRIAL's route demo, all 26 lines it laid were all-keep. A
range of active lines kept for each mask lets the lay be clipped to it. The
ranges are built at the launch from `K`: 256 bytes of bss, no part bytes. The
saving is PREDICTED at 3 - 10% of the priced pass, and nothing on the disk.
The model's masks are exact lines, so AV and A4R get this for nothing where
the model runs.

### What does not work

- **A tighter reach (T).** Cutting the reach at WALLs the ball cannot clear
  changes no record on any course, because every such cell is reached some
  other way. The Monte Carlo bounds any reach analysis: its sampled
  positions lay 48 - 81% of today's records. So even a perfect reach would
  save less than A4R, and it would need a state-space proof.
- **Raising the kill only behind back edges** changes physics, the
  identities and every demo, and saves less than vlow.
- **A per-block depth map** costs 3 bytes for each of 2,400 - 12,000 blocks,
  against 4 bytes for each of 300 - 3,100 records.
- **An implicit full-block mask.** 24 - 48% of records do lay the whole
  block, but the mask index is one byte of four, and WDIFF and LZ already
  pack it. There is less than 1% to win.
- **A package-wide mask library.** The seven courses hold 499 masks, 253 of
  them distinct, so a byte index would have 3 slots left. And the `K`
  sections are only 4% of the disk (LZ4 2,359).
- **A direct per-block record index** in place of the binary search. It costs
  `COLS x BROWS` bytes of RAM (2.4 - 12 KB) to save a search the hint
  already makes cheap.

## 4. CPU (PREDICTED; the report's section 4)

Each course's demo is replayed through the binding model, and at every step
bz_occ's walk is done on the shipped part. Each frame is then priced from the
instructions, using `occframes.py`'s constants: ESTIMATED from bzvideo.inc as
built, one box. The priced pass is **about 0.4 of the MEASURED one** (MILL
3.2k against 8.1k, PEAK 4.8k against 13.3k, from 128.15.5.4). It under-counts
the two-box frames and the lay's arithmetic per box. So read the today column
as a ratio, and A4R's addition, which is the model's own work, as absolute.

| course, demo | steps | gate open | of them VOID | today | X | V | A4R | worst, today / A4R |
|---|---|---|---|---|---|---|---|---|
| BENCH, autopilot | 3,600 | 2,685 | 0 | 7,129 | 7,048 | 7,129 | 7,862 (+733) | 7,490 / 8,860 |
| FIRST, route | 154 | 21 | 21 | 1,587 | 1,587 | ~0 | 1,630 | 1,690 / 1,750 |
| TRIAL, route | 499 | 128 | 22 | 1,718 | 1,661 | 1,511 | 2,102 (+384) | 3,020 / 2,510 |
| MILL, route | 778 | 263 | 0 | 3,161 | 2,892 | 3,161 | 4,018 (+857) | 7,345 / 9,520 |
| MOON, `moon.bzd` | 1,983 | 1,580 | 50 | 3,373 | 3,106 | 3,216 | 4,874 (+1,501) | 11,350 / 23,840 |
| PEAK, `summit.bzd` | 2,172 | 1,393 | 58 | 4,820 | 4,672 | 4,763 | 7,914 (+3,094) | 13,045 / 24,750 |
| PLAY, `playground.bzd` | 1,504 | 31 | 0 | 2,011 | 1,800 | 2,011 | 2,855 (+844) | 3,800 / 4,400 |

Where the model's time goes:
- about 80 clk to read each of the up to 14 front cells: 10.2 a frame on
  PEAK;
- about 750 for each front cell whose top edge reaches the footprint: 0.92 a
  frame on PEAK;
- 15 - 50 for each covered word of a line.

The worst column counts a residual group as a lay of its own, even where it
ANDs into a covered word, so it over-states A4R. AV pays the model only on
the VOID column's frames: about +0.1k averaged over the demos, and the worst
frame of a fall.

Three levers lower A4R's figure, all priced in wave A1 before the smoothness
A/B:
- a per-cell bitmap built at the launch (bss, about 2 bytes a cell) of the
  front cells that can ever occlude it, which skips most of the reads;
- depth 3 where the tool proves it enough;
- X.

## 5. The plan (stories; each wave verifies on the host and names its rows)

### Wave A0: the tool's model (host only, no shipped byte moves)

| # | story | verified by |
|---|---|---|
| A0.1 [x] | **The binding model, from the part.** `bbcourse.occ_model(part, wx, wy, z, m)` reads the front cells to `OCCDEPTH` (4) through ROWTAB from the RAM form's cells. It takes the corners from `z0`/`sx`/`sy` and each top edge as two screen segments, and builds each line's coverage. It passes over a cell with `OBS`, a kind 4 - 6 cell and a `FL_FLOAT` cell (A0.3), and dithers its masks as `K`'s are. It reads nothing the guest cannot read | `--selfcheck` item 15 (new), at the reach lattice of every course: against the prototype's owner-render model (`occproto.Analytic`), and against the rule. WRONG-HIDE is reported and bounded: past `OCC_WRONG_MAX` (0.25% of ball pixels) it is refused; **DONE** (branch `bounce-bonanza-av`, SPEC.md 128.29.2): `bbcourse.AGrid` and `amodel_*`, read from the RAM form; the edge is the top polygon's first line exactly (a tie rule on the right half), WRONG-HIDE 0.0000 - 0.0005% MEASURED. Checked against the TILES' spans rather than the prototype's owner render |
| A0.2 [x] | **The residual records**: `_occluders` over the pixels the rule lays and the model does not, at every query of `block_queries`, then today's merge, bounds, dither and `R`/`K`/`I`/`O`. Behind `--occ void` (AV) and `--occ all` (A4R), default off | item 15's COMPLETENESS proof, after `merge_exact`: at every block query, the rule's pixels are a subset of the union of the model's and the residual's. Red arms, each red at item 15: the residual dropped; depth 3 (BENCH's void positions); a sloped cell read as flat (TRIAL's ramp); the dither left off the model's masks (item 11 red too); **DONE** (128.29.3): `av_records`, `--occ void` (the default) and `--occ off`; `--occ all` NOT built (A3's). Completeness and the red arms in item 15, all red |
| A0.3 [x] | **Floating cells** are marked in the grid (`FL_FLOAT`, flags bit 4 on a non-goal cell; a floating GOAL is refused), so the model passes over them. This covers the PLAYGROUND's platform and the pathway | items 14 (GROUND) and 15, on the PLAYGROUND and on `path.bbc`; **DONE, amended** (128.29.4): `FL_FLOAT` is flags bit **6**, not 4 (bits 4 - 5 stay RESERVED for `edge`); a course with a floating GOAL gets no `GF_ANA` instead of being refused. It changes 0 - 4 ball pixels on today's lattices: the flag guards later courses |
| A0.4 [x] | **The bytes and the error, MEASURED with the binding model**, both formats, on every course, the pathway and the title, under `--occ void` and `--occ all` | `--sizes`; the report's tables re-taken in a new report. **The owner rules here on AV first, and on A4R or A4R-V for later**; **DONE for AV** (128.29.6, MEASURED): the seven -5,670 LZB, -7,071 LZ4, -27,704 RAM, records 12,403 -> 5,981; the pathway unchanged, the title -444 LZB. Figures in SPEC.md rather than a new report; `--occ all` not measured |

**A0's rows (named, not run)**: `bonanzacourse`.

### Wave A1: the guest's model, then AV ships

| # | story | verified by |
|---|---|---|
| A1.1 [x] | **`bz_amodel`** in `bzvideo.inc`. At `.key`, on a part whose `BZG1` FLAGS has `GF_ANA` (bit 5, new): when the ball's cell is VOID, or on every cell when `GF_ANAALL` (bit 6) is set, it puts the front cells' coverage into `bz_omsk` for each covered word and block row. Each line's mask comes from two 8-entry edge tables, with the checker ORed in. Then today's walk over the part's records ANDs into the same mask, with one `bz_olay` a word | unicorn: `bz_occ` on every course's AV and A4R parts against `occ_model`, at 300 positions a course (as 128.15.5.2's D/C proof): the same box bytes and the same laid words. Red arm `amodel` (one edge-table entry wrong) is red there; **DONE** (128.29.5): `bz_amodel` runs AFTER the walk and lays its own words (two lays compose to the AND), so the walk is untouched; `tests/bonanza_av.py`, 400 positions on each of nine parts, every byte equal; red arm `amodel` red |
| A1.2 [x] | **The price, MEASURED**: the executed instructions of `bz_occ` per frame on the demos' positions (unicorn), today's part against AV's and A4R's; the package image and its bss; the launch-time front bitmap (section 4) priced with and without | written into the new section 128.29 as MEASURED; **the owner sees A4R's figure before wave A3**; **DONE for AV** (128.29.5, 128.29.9): PRICED +8.8k - +10.1k median a fall frame, MEASURED on MartyPC +12k - +19k median, +31k - +58k worst, both cards; image +1,031, bss +107. The front bitmap not priced; A4R not priced. **The speed pass** (branch `bounce-bonanza-av2`, 128.29.5): the model computed once a CELL and kept (the cell's cache) and the halves a flat parent shadows never computed; MEASURED on MartyPC +3.2k - +8.4k mean, +0.8k - +3.9k median, +19k - +43k worst, both cards; image +541 more, bss +236 more |
| A1.3 [x] | **AV becomes the default**: `--occ void`. Every identity moves, because the RAM form changed. So `moon.bzd`, `summit.bzd` and `playground.bzd` are written again by `bbcourse.py author`; only their `ident` lines change, and physics does not move. The pathway and the title follow only if A0.4's error holds on them | the build's demo checks; `--selfcheck`; `make bonanzadisk`, with `BONANZA.O88` and the clusters of `bonanza360.img` before and after; **DONE**: the three demos' `ident` lines only; `BONANZA.O88` 117,392 -> 112,173, `bonanza360.img` 123 -> 118 clusters |
| A1.4 [x] | **kern_mega and the Hercules**: the model reads the part through `bz_cseg` as the walk does, and the masks do not depend on the card (two bits a game pixel). So nothing differs | the A1.1 unicorn run on the Hercules arm's box; **DONE by reading and by MartyPC's Hercules measurement** (128.29.10): no `PKG_MEGA` arm; `bonanzamega` not run |
| A1.5 [ ] | **The final pass for AV** | the rows below, once; **OPEN**: the rows below, the final pass's |

**A1's rows**: `bonanzacourse`, `bonanzaassets`, `bonanzaring` (its
oracle reads `occ_model` in VOID cells), `bonanzaphys` and `bonanzareplay`
(the identities), `bonanzaperf` (a fall is rare in the demos. The row reports
the pass's span on the VOID frames), `bonanzawheel` (MILL), `bonanzapath`,
`bonanzamega`.

### Wave A3: the model everywhere (A4R), only if A1.2's price allows

| # | story | verified by |
|---|---|---|
| A3.1 [ ] | `--occ all` becomes the default, with `GF_ANAALL` set and the demos written again | as A1.3 |
| A3.2 [ ] | **The smoothness A/B**, 128.15.5.4's rule verbatim: `bonanzaperf --occ-ab`, MILL's and PEAK's demos, both cards, six runs a build, the A4R build against AV's at one commit. Red arm `occslow` (the model padded about 25k) is red at the rate clause | the rule holds on both cards, or A4R does not ship and AV stays |
| A3.3 [ ] | **The final pass** | A1's rows, once |

**The alternative, wave V**, replaces A0 - A3 if the owner prefers it. It puts
the ghost height in the VOID cell's flag nibble, draws the ghosted sprite and
keeps no VOID record. `--selfcheck` holds every VOID cell's `H` to the rule:
no record lays at or above it. Red arm: `H` one step low. Rows: as A1's.

## 6. What section 128.29 of SPEC.md would say

- 128.29.1 the decisions;
- 128.29.2 the model: the front cells, the edges, the pass-over rule, the
  dither;
- 128.29.3 the residual: completeness, and the merge and bounds unchanged;
- 128.29.4 `GF_ANA`, `GF_ANAALL`, `FL_FLOAT`, and what a part holds;
- 128.29.5 the guest: `bz_amodel`, its place in `bz_occ`, its price
  MEASURED;
- 128.29.6 the bytes, MEASURED;
- 128.29.7 `--selfcheck` item 15 and the red arms;
- 128.29.8 the rows;
- 128.29.9 kern_mega, kern_small, the Hercules.

It amends three earlier subsections:
- 128.10.4.4: a record is now the RESIDUAL;
- 128.11.4: the bounds are refused on the residual;
- 128.15.5: the record's form is unchanged.

## 7. What it buys the two-segment courses (128.28)

What binds a long course is a part's 65,024 bytes of RAM (128.15.8,
`PARTMAX`). PEAK today uses 48,129 of them: **339 bytes a block row** over 142
rows. Each option's figure, and what one part then holds at PEAK's density:

| | PEAK's RAM | a block row | one part holds |
|---|---|---|---|
| today | 48,129 | 339 | 191 rows, about 81 s at PEAK's pace |
| V | 40,651 | 286 | 227 rows (+19%) |
| AV | 41,957 | 295 | 220 rows (+15%) |
| A4R | 36,695 | 258 | 251 rows (+31%) |
| A4R-V | 35,141 | 247 | 263 rows (+38%) |
| no occluders | 33,953 | 239 | 272 rows |

A two-segment course splits its rows across two parts, so the gain applies
to each part: segments 15 - 38% longer, or fewer segments for a course of a
given length. Past that, the picture binds. The map's RAM form is two bytes a
block, 41% of all course RAM, and it is the next study.

## 8. Decisions for the owner

1. **Model or ghost?**
   - The model is AV now and A4R later: disk -5.2 KB, then -9.9 KB LZB;
     RAM -26 KB, then -46 KB; about 1 KB of resident guest code; CPU
     unchanged for AV, and a few percent of a frame for A4R, measured
     before it ships.
   - V is -6.8 KB LZB and -31 KB RAM, with cheaper CPU and a visible
     dimming of falls.
   - Or neither.
2. **Inside A4R, the void choice**: A4R is exact or over-hidden everywhere.
   A4R-V saves about 2.9 KB more, and falls near props or diagonal edges are
   then partly drawn over their occluder.
3. **If V**: V(any) dims early; V(50%) dims late and draws a little over.
   The pictures show both kinds of difference.
4. **Is "a quarter of the ball wrong on N% of fall frames" the measure you
   want** for "not pixel-perfect"? It is the one this study used to compare
   the options that are not exact.
