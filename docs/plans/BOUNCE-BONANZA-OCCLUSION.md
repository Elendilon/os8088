# BOUNCE BONANZA: occlusion, computed instead of stored

*A PROPOSAL for the owner to review (2026-11-17). Nothing here is built: the
shipped guest, the shipped course format and SPEC.md 128 are unchanged on this
branch. The measurements, the pictures and how each figure was taken are
[the report](../reports/BONANZA-OCCLUSION-2026-11-17.md). The contract it
would become is reserved as **SPEC.md 128.29**. The parallel two-segment-course
work adds 128.28; this plan does not touch it, and section 7 below says what
each option gives it.*

The owner, 2026-11-17: *"Course size is too big, and most of it seems to be
occlusion ... It does not need to be pixel-perfect or the same as today. Can
we just store less? ... Ideally smaller on disk, smaller in RAM, and less CPU
per frame."*

## 1. The answer in one screen

- **Occlusion is about a third of a course, not most of it** (MEASURED,
  the seven `BZ_COURSES` at `28f4859dd`). The occluder sections `I R K O`
  are **31% of the packed parts** (LZB 14,361 of 46,147; LZ4 17,607 of
  56,796) and **25% of their RAM** (59,948 of 237,789). In context - each
  part packed with and without its occluders - occlusion costs **14,656
  bytes LZB** and **58,762 bytes of RAM** over the seven. **The picture is
  the majority**: the map and the blocks are 52% of the packed parts and
  57% of the RAM, and the map alone is 41% of all course RAM.
- **More than half of today's records exist only for a ball in a VOID
  cell** - falling off an edge, or in the air over a gap. They are the
  cheapest records to lose and the ones the earlier option (c) lost
  visibly (SPEC.md 128.11.4.5).
- **The records can mostly be COMPUTED.** What hides the ball is the cells
  in front of it that rise above it, and the picture under each such cell's
  top edge is that cell's own top and face: every face now reaches the
  ground plane (SPEC.md 128.27). A model that reads up to 14 cells in front
  of the ball from the grid - their heights and their top edges - lays
  what the rule lays at **99.9% of the ball pixels** of 2.9 million sampled
  positions. Records are then needed only for what the model cannot see -
  a prop's drawing, a split cell, a floating face, a cell further away - as
  **RESIDUAL** records, which the guest walks exactly as today.
- That is **option A4R**: records fall from 12,403 to 1,958 over the seven
  courses (**-84%**), the parts lose **9,862 bytes LZB (67% of what
  occlusion costs on the disk)** and **46,046 bytes of RAM**, and PEAK's
  part has **28.3 KB of headroom** where it has 16.9 KB. Nothing the rule
  shows is lost: the union lays at least what the rule lays. It is exact
  except where the model over-hides (at most 0.1% of the ball's pixels).
- **The CPU is where it costs.** On today's records each laid group is a
  table walk. Computing the masks costs about +1 to +4k clocks on a frame
  whose gate is open (PREDICTED; section 4). No option in this study makes the
  occluder pass meaningfully cheaper, because what dominates it is the LAY
  (copying the picture back over the ball), and every option that keeps the
  ball behind the scenery pays that. So the honest answer to "all three" is:
  **disk and RAM, yes, by a lot; CPU, no** - A costs a few percent of a
  frame and has to pass the owner's smoothness rule (SPEC.md 128.15.5.4)
  before it ships.

**Recommended:** option **A4R**, built in three waves (section 5), with the
smoothness A/B as its gate. If it fails that gate, **option V** (section 3) is
the fallback: it keeps nearly half of the saving at lower CPU, and it looks
worse.

## 2. The options, in one table

All seven `BZ_COURSES` together. Bytes are MEASURED on the host, with the
shipped tool's own pipeline and packers (the report, section 3). Clocks are
PREDICTED (section 4). "Looks" is MEASURED against today's rule over the
Monte Carlo's sampled positions (the report, section 5).

| option | records | LZB / LZ4 (parts) | RAM | clk, a frame whose gate is open | looks | guest code | risk |
|---|---|---|---|---|---|---|---|
| today | 12,403 | 46,147 / 56,796 | 237,789 | MILL 3.2k, MOON 3.4k, PEAK 4.8k (priced; MEASURED pass 8.1k / 13.3k) | the rule | - | - |
| no occluders at all (the floor) | 0 | 31,491 / 38,721 | 179,027 | 0 | the ball over everything | -1k | - |
| **A4R**: computed masks (front cells to depth 4) + residual records | **1,958** | **36,285 / 44,646** (-9,862 / -12,150) | **191,743** (-46,046) | **+1 to +4k** | exact or over-hidden (0.1% of pixels) | **+700 - 1,000 bytes** | **high**: a rasterizer in the guest, held to a host model |
| A4R-V: A4R with no residual for a ball in a VOID cell | ~900 | ~33,500 / ~41,500 | ~185,000 | as A4R | a fall near a prop or split cell drawn partly over its occluder: 0 - 8% of fall frames have a quarter of the ball wrong (MOON 8%) | as A4R | high |
| **V**: no record for a VOID cell; below a per-cell height the whole ball is GHOSTED | 5,235 | 39,397 / 48,493 (-6,750 / -8,303) | 206,489 (-31,300) | **cheaper** on a fall frame: about -3k to -10k there, +0.5k for the ghost | **visibly different**: 27 - 51% of fall frames have a quarter of the ball wrong (the ball dims as it leaves an edge); V(50%) 6 - 14% | +60 - 100 bytes | low |
| (c) / no VOID record, nothing in its place (rejected in 128.11.4.5) | 5,190 | 38,706 / 47,610 | 206,309 | as V | the ball drawn OVER what it falls behind: 8 - 29% of fall frames | -0 | low |
| vlow: no record below the lowest floor within two tiles (a fall's last 24 px hidden or ghosted) | 8,460 | 42,506 / 52,445 (-3,641) | 221,657 | as V, on those frames | the last part of a fall only | +60 | low |
| T: a tighter reach (walls cut it) | 12,403 | no change | no change | 0 | - | 0 | - |
| X: lay only a mask's active lines (CPU only) | 12,403 | +~200 (a range byte a mask, or none if built at launch) | +256 bss | -3% (PEAK) to -10% (MILL, PLAY) of the priced pass | the same | +40 | low |
| data shortcuts (implicit full mask, a shared mask library, a per-block depth map, field coding) | | each under 1% of the disk, or worse | | | | | rejected |

## 3. The options, explained

### A4R: occlusion computed from the grid, records for the residual

**The model.** A ball in cell `V = (wx, wy)` at height `z` (margin `m`) is
hidden at picture pixel `(x, y)` when one of V's FRONT cells
`N = (wx + i, wy + j)`, `i, j >= 0`, `0 < i + j <= 4` (14 cells) is a plain
whole cell whose highest corner is above `z + m`, and `y` is at or below N's
top edge in column `x`. Below that edge the column is N's own top, then N's
face down to the ground plane (128.27), then nearer cells, every one of them
in front of the ball. The model reads only the grid: N's `z0`, `sx`, `sy` and
kind give its four corners, and its top edge is two straight segments on the
screen. A front cell the model cannot read - a prop's cell (`OBS`), a split
cell (kinds 4 - 6), a floating cell - is passed over.

**The residual.** The tool computes, over the whole reachable set, every
occluder pixel the rule lays at some position where the model does not, and
cuts records from those pixels alone, by today's rule, merge, bounds, dither
and 4-byte form. The guest runs the model and then walks the residual records
exactly as today, and the two lay into the same mask (`bz_omsk`). So the union
lays at least what the rule lays, at every reachable position. The only
difference from today is where the model hides a pixel the rule does not
(**WRONG-HIDE**): 0.00 - 0.08% of the ball's pixels over the samples. That is
a pixel of a lower cell in front under a taller cell's face, and the checker
dither shows the ball through it anyway.

**What it measures** (host, the report's section 3; A4R is `res4`):

| course | records today -> A4R | LZB | RAM |
|---|---|---|---|
| BENCH | 2,660 -> 163 | 6,011 -> 4,040 (-1,971) | 40,156 -> 29,268 |
| FIRST | 291 -> 36 | 2,194 -> 1,751 (-443) | 10,140 -> 8,760 |
| TRIAL | 707 -> 123 | 3,798 -> 3,253 (-545) | 16,880 -> 14,400 |
| MILL | 1,279 -> 144 | 7,786 -> 6,448 (-1,338) | 29,975 -> 24,715 |
| MOON | 2,535 -> 528 | 8,318 -> 6,371 (-1,947) | 43,087 -> 33,835 |
| PEAK | 3,079 -> 486 | 10,325 -> 7,628 (-2,697) | 48,129 -> 36,695 |
| PLAY | 1,852 -> 478 | 7,715 -> 6,794 (-921) | 49,422 -> 44,070 |

BENCH's fullest block falls from 4 records (the bound, no headroom, 128.11.4.2)
to 4 and its fullest row from 77 to 23; every course's block bound gets
headroom except BENCH's, whose one full block is a residual one.

**The cost** is CPU and code: section 4. **The risk** is that the guest's
model and the tool's must agree to the pixel, so the tool's model has to be
written from the PART's grid bytes alone, and the guest's routine checked
against it under unicorn, before any course ships it (wave A1).

**The void choice (the owner's).** A4R keeps residual records for a ball in a
VOID cell too, most of them for the deep positions of a fall that the
conservative reach puts under every edge. A4R-V drops them and lets the model
alone draw a fall. On plain geometry the model alone is nearly exact (BENCH
0.00% of fall frames with a quarter of the ball wrong at depth 4, MILL 0.17%,
PLAY 1.7%), but in front of props and split cells it is not (PEAK 4.1%, MOON
8.1%: MOON's diagonal coast). A4R-V buys about 2.8 KB more LZB over the seven
for that.

### V: the falling ball ghosted

No record is laid for a ball in a VOID cell (the lift's shaft excepted). In
its place the tool stores, in the VOID cell's free flag nibble (bits 4 - 7:
a goal's exit elsewhere), a GHOST height `H` in 8 px steps above the kill. A
ball in a VOID cell below `H` is drawn through the checker, whole (the
sprite's mask ORed with the checker, `+2` instructions a word). Above `H`
nothing lays, by `H`'s definition. It reuses everything else as it stands.

It is **cheap and it is visibly different**. `H` is per CELL, and a cell is
16 px across. A ball leaving a back edge is ghosted as soon as ANY position
in its cell would be partly hidden. In the pictures it dims a frame or three
before today's ball starts to go behind the edge
(`bounce-bonanza/occ-fall-mill.png`, `occ-fall-peak.png`, column 3). Over
the sampled falls, 27 - 51% of frames have more than a quarter of the ball
wrong, against 8 - 29% for (c). A threshold
(`H` where the cell's average share hidden reaches 50%) brings that to 6 - 14%,
at the price of a partly hidden ball being drawn over its occluder above `H`.
The bytes are the same either way. V is the fallback if A fails its CPU
gate, and the owner's eye decides between V(any) and V(50%).

### X: lay only the active lines

A group lays every footprint line of its block row, but its mask often
keeps whole lines (TRIAL: all 26 of the lines its demo laid were all-keep).
If a range of active lines is kept for each mask (built at the launch from
`K`, 256 bytes of bss and no part bytes), the lay is clipped to it. The saving
is PREDICTED at 3 - 10% of the priced pass. It costs nothing on the disk. A4R
gets it for nothing, because its masks are exact lines.

### What does not work

- **A tighter reach (T)**. Cutting the reach at WALLs the ball cannot clear
  changes no record on any course: every such cell is reached some other
  way. The Monte Carlo puts an upper bound on any reach analysis: its
  sampled positions lay 48 - 81% of today's records. So a perfect reach
  analysis saves less than A4R, and it costs a state-space proof.
- **Raising the kill only behind back edges** changes physics, the
  identities and every demo, for less than vlow.
- **A per-block depth map** (a byte pair for every map block) is 3 bytes for
  each of 8,000 - 12,000 blocks, against 4 bytes for each of 2,700 records.
- **An implicit full-block mask.** 24 - 48% of records lay the whole
  block. But the mask index is one byte in four, and WDIFF and LZ already
  pack it, so there is less than 1% to win.
- **A package-wide mask library.** The seven courses hold 499 masks, 253 of
  them distinct across courses, so a byte index has 3 slots left. The `K`
  sections are only 4% of the disk (LZ4 2,359) anyway.
- **A direct per-block record index**, to replace the binary search. It
  costs `COLS x BROWS` bytes of RAM, 2.4 - 12 KB, to save a search that the
  hint already makes cheap.

## 4. CPU (PREDICTED; the report's section 4)

Each course's demo, replayed through the binding model, with bz_occ's walk
done on the shipped part at every step. Each frame is priced from the
instructions: `occframes.py`'s constants, ESTIMATED from bzvideo.inc as built,
one box. The priced pass is **about 0.4 of the MEASURED one** (MILL 3.2k
against 8.1k; PEAK 4.8k against 13.3k, 128.15.5.4): the two-box frames and the
lay's per-box arithmetic are under-counted. So read the columns as RATIOS.

| course | gated steps | today | X | V | A4R | worst today / A4R |
|---|---|---|---|---|---|---|
| see the report's table 4.1 | | | | | | |

A4R's model costs about 80 clk for each front cell read (14), about 750 for
each one that reaches the footprint, and 15 - 50 for each covered word of a
line. That is about +1 to +4k on an occluded frame, ESTIMATED from a sketch,
not from code. Wave A1 writes the routine and measures it under unicorn, and
wave A2's smoothness A/B decides.

## 5. The plan (stories; each wave verifies on the host and names its rows)

### Wave A0: the tool's model (host only, no shipped byte moves)

| # | story | verified by |
|---|---|---|
| A0.1 [ ] | **The binding model, from the part.** `bbcourse.occ_model(part, wx, wy, z, m, lines, words)`: front cells to `OCCDEPTH` (4) read through ROWTAB from the RAM form's cells, corners from `z0`/`sx`/`sy`, top edges as two screen segments, the per-line coverage, a cell with `OBS`, kind 4 - 6 or `FL_FLOAT` (new, story A0.3) passed over; the masks dithered as `K`'s are. It reads nothing the guest cannot read | `--selfcheck` item 15 (new): against the prototype's owner-render model (`occproto.Analytic`) at the reach lattice of every course, and against the rule: WRONG-HIDE reported and bounded (`OCC_WRONG_MAX`, 0.25% of ball pixels: refused past) |
| A0.2 [ ] | **The residual records**: `_occluders` over the pixels the rule lays and the model does not, at every query of `block_queries`, then today's merge, bounds, dither, `R`/`K`/`I`/`O`; behind `--occ analytic` (default off) | `--selfcheck` item 15's COMPLETENESS proof (as `merge_exact`): at every block query the rule's pixels are a subset of the model's and the residual's union. Red arms: the residual dropped (item 15 red); depth 3 (red on BENCH's void positions); a sloped cell read as flat (red on TRIAL's ramp); the dither left off the model's masks (item 11 red) |
| A0.3 [ ] | **Floating cells**: `float` cells marked in the grid (`FL_FLOAT`, flags bit 4 on a non-goal cell; a floating GOAL refused) so the model passes over them; the PLAYGROUND's platform and the pathway | item 14 (GROUND) and item 15 on the PLAYGROUND and `path.bbc` |
| A0.4 [ ] | **The bytes and the error, MEASURED with the binding model** on every course, the pathway and the title, both formats; the owner's void choice (A4R or A4R-V) recorded | `--sizes` with `--occ analytic`; the report's tables re-taken; **the owner decides A4R or A4R-V here** |

**A0's rows (named, not run)**: `bonanzacourse`.

### Wave A1: the guest's model (host-proved, not yet shipped)

| # | story | verified by |
|---|---|---|
| A1.1 [ ] | **`bz_amodel`** in `bzvideo.inc`: at `.key`, for a part whose `BZG1` FLAGS has `GF_ANA` (bit 5, new), the front cells' coverage into `bz_omsk` per covered word and block row, then today's residual walk ANDing into the same mask, one `bz_olay` per word. Masks built per line from two 8-entry edge tables, the checker ORed | unicorn: `bz_occ` on every course's analytic part against `occ_model` at 300 positions a course (as 128.15.5.2's D/C proof): the same box bytes and the same laid words; red arm `amodel` (one edge table entry wrong) red there |
| A1.2 [ ] | **The price, MEASURED**: the executed instructions of `bz_occ` per frame on the demos' positions (unicorn), today's part against the analytic part; the resident bytes `kernsize`-style (the package image, its bss) | written into SPEC.md 128.29 as MEASURED; if the mean is over +2k or the worst over +6k on PEAK, **stop and bring it to the owner** before A2 |
| A1.3 [ ] | **kern_mega and the Hercules**: the model reads the part through `bz_cseg` like the walk, and masks are card-independent (two bits a game pixel), so nothing differs. Confirmed on `bonanzamega`'s host half | unicorn on the Hercules arm's box |

**A1's rows (named, not run)**: `bonanzacourse`, `bonanzaring` (its oracle reads the model), `bonanzaassets`.

### Wave A2: the courses switch, and the final pass

| # | story | verified by |
|---|---|---|
| A2.1 [ ] | **`--occ analytic` becomes the default**: `GF_ANA` set, `R`/`K`/`I`/`O` the residual's; every identity moves (the RAM form changed), so `moon.bzd`, `summit.bzd`, `playground.bzd` are written again by `bbcourse.py author` (their `ident` lines alone: physics unmoved); the pathway and the title switch only if A0.4's error holds on them | the build's demo checks; `--selfcheck`; `make bonanzadisk`: `BONANZA.O88` and `bonanza360.img` clusters before and after |
| A2.2 [ ] | **The smoothness A/B** (128.15.5.4's rule, verbatim): `bonanzaperf --occ-ab`, MILL's and PEAK's demos, both cards, six runs a build, the analytic build against today's at one commit; red arm `occslow` (the model padded ~25k) red at the rate clause | the rule holds on both cards, or A does not ship and V (or nothing) is taken instead |
| A2.3 [ ] | **The final pass** | the rows below, once, after the last batch |

**A2's rows**: `bonanzacourse`, `bonanzaassets`, `bonanzaring`,
`bonanzaperf`, `bonanzaphys`, `bonanzareplay`, `bonanzawheel` (MILL's
lanes over the model), `bonanzapath`, `bonanzamega`, and the
visibility audit's report (128.15.10.4) on every course.

**The fallback, wave V** (only if A2.2 fails): the ghost height in the VOID
cell's flag nibble, the ghosted sprite, no VOID record; `--selfcheck` holds
every VOID cell's `H` to the rule (no record lays at or above it). Red arm:
`H` one step low. Rows: as A2.

## 6. What SPEC.md 128.29 would say

128.29.1 the decisions; 128.29.2 the model (front cells, edges, the
pass-over rule, the dither); 128.29.3 the residual (completeness, the merge,
the bounds, unchanged); 128.29.4 `GF_ANA`, `FL_FLOAT` and what a part holds;
128.29.5 the guest (`bz_amodel`, its place in `bz_occ`, its price MEASURED);
128.29.6 the bytes, MEASURED; 128.29.7 `--selfcheck` items 14 - 15 and the red
arms; 128.29.8 the rows; 128.29.9 kern_mega, kern_small, the Hercules. It
amends 128.10.4.4 (what a record is FOR: the residual), 128.11.4 (the bounds
are refused on the residual) and 128.15.5 (unchanged form).

## 7. What it buys the two-segment courses (128.28)

The binding limit for a long course is a part's 65,024 bytes of RAM
(128.15.8, `PARTMAX`). PEAK today uses 48,129 of them, which is **339 bytes
a block row** over 142 rows. Each option's per-row figure and what one part
then holds, at PEAK's density:

| | PEAK's RAM | a block row | one part holds |
|---|---|---|---|
| today | 48,129 | 339 | 191 rows, about 81 s at PEAK's pace |
| V | 40,651 | 286 | 227 rows (+19%) |
| A4R | 36,695 | 258 | 251 rows (+31%) |
| A4R-V | about 35,500 | 250 | 260 rows (+36%) |
| no occluders | 33,953 | 239 | 272 rows |

A two-segment course splits its rows across two parts, so the gain applies to
each part: the same 28 - 36% longer segments, or fewer segments for a course
of a given length. Above that the picture binds: the map's RAM form is two
bytes a block, 40% of every course's RAM, and it is the next study.

## 8. Decisions for the owner

1. **A4R, with its CPU gate?** Disk -9.9 KB LZB and RAM -46 KB over the
   seven courses, a few percent of a frame of CPU (to be measured), and about
   1 KB of resident guest code. Or **V**, which is half the saving, cheaper
   CPU and a visible dimming of falls. Or neither.
2. **The void choice inside A**: A4R (exact or over-hidden everywhere) or
   A4R-V (about 2.8 KB more, and falls near props or diagonal edges partly
   drawn over their occluder).
3. **If V**: V(any) (dims early) or V(50%) (dims late and draws a little
   over). The pictures show both kinds of difference.
4. **Is "a quarter of the ball wrong on N% of fall frames" the measure you
   want?** It is the one this study used to compare options that are not
   pixel-perfect.
