# BOUNCE BONANZA: diagonal tiles (half tiles)

*The contract is SPEC.md 128.24 (D1 - D2 BUILT); where this plan and it disagree, it
wins. Item 8R.15 of [BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md)'s wave 8R
table points here. D1 and D2 are built (ticked below); D3 - D5 are not.*

The owner, 2026-11-16: *"The ability to do diagonal tiles; the straight path
up having to add full tiles makes that apparent, and we've been hitting it on
the test courses too."*

## Where it stands

**DECIDED, to be built as soon as possible** (the owner, 2026-11-16, the
lead's round R3; SPEC.md 128.24.12 has each answer): the format is (a), half
records in section `D`; a face's ink follows the half's pattern; the
pathway's straight bands and diagonal steps, yes; the diagonal's dead band
the named `BZ_DWMIN` (11.3); PLAYGROUND first, then MOON's coast. R4 (on
the pictures `diag-q3`, `diag-q6`): **QUARTERED cells** are allowed (a
box's odd corner is the one quarter inside it - a square corner, not
the chamfer this line first said: D2's verify), Q6's occluder over-lay is accepted, and kind 7
is reserved for the owner's next core tile, the CHANNEL (SPEC.md 128.24.13).

**D1 and D2 are BUILT** (branch `8r2/dtool`, SPEC.md 128.24's "Built so
far"): the tool and the model, halves and quarters, every story below
ticked with what verified it. D3 (the guest) is next; until it lands the
tool refuses a half, a quarter or a box in a shipped course (`GUEST_SPLIT`).

What was investigated, what a half is and why this shape, the grammar, the
grid, the art, the physics and its cost, the pathway, and what it does and
does not move are SPEC.md 128.24.2 - 128.24.10. The mock-ups the owner was
sent (`diag-edge`, `diag-upband`, `diag-wall`, `diag-halves`) came from a
throwaway prototype outside the tree; story D1's `--png` previews replace them
with the tool's own.

## The shape of the work

Five waves, the tool first and the guest last, so each guest wave copies a
model that is already proved on the host. Every wave verifies on the host and
NAMES its rows (CLAUDE.md, *Testing*); the rows run once, in the final pass.
The waves go on a branch of their own off the integration branch after wave
8R lands (Q9).

| wave | what | depends on |
|---|---|---|
| D1 | the tool: grammar, tiles, grid, section `D`, the picture, the occluders' key | Q1 |
| D2 | the model: `bbcourse.Physics` and every host tool that walks the course | D1 |
| D3 | the guest: `bzphys.inc`, the CELLS rules, the window | D2 |
| D4 | the pathway's bands | D1 (picture), D3 not needed (no physics there) |
| D5 | PLAYGROUND's diagonal section, the owner's look and play | D3, D4 |
| final | the rows once, `test-full`, the disks | D5 |

## The stories

### Wave D1: the tool (host only)

| # | story | verified by |
|---|---|---|
| D1.1 [x] | **The data model.** A split tile (`Split`: the diagonal, half A, half B, each a `Tile` or `None`) beside `Tile`; `build_tiles` overrides per half, normalises two equal halves to a whole tile, and refuses a cell split both ways (128.24.4). Every consumer of `tiles` audited and named in the commit: `build_cells`, `cells_rule`, `_cells`, `draw_ops`, `render`, `_top_subquads`, the props' placement, `build_reach`, `_occluders`, `_laid`, `block_queries`, `check_bounds`, `play_geometry`, `reach_closure`, the trap and exit reach, `path_prepare`, `path_signs`, `Grid.cell`, `composite`, `visibility` | `--selfcheck`; every shipped course's part byte for byte unchanged (the identities printed before and after) - **DONE: `Split` (kinds 4, 5 and R4's 6), `build_tiles` holding pieced cells as quarters and normalising them; the consumers audited (the pathway's - `path_prepare`, `path_signs`, `_route_lay` - are D4's); `--selfcheck` ok, every shipped part byte for byte unchanged** |
| D1.2 [x] | **The grammar**: `half up|down|left|right` on `floor`, `wall`, `goal`, `hole`; the shape `box a0 a1 s0 s1`; every refusal of 128.24.4, each with a string case in `_grammar_cases` | `--selfcheck` item 2's new cases, each refusal fired by a line written to trip it - **DONE: `half`, R4's `quarter n|e|s|w`, `box` (its corners quartered); 15 refusals in `_split_cases`** |
| D1.3 [x] | **The grid**: kinds 4 and 5, the pair, section `D` (PLAIN, after `C`), `GF_SPLIT`; the NEAR and SAFE rules by halves; `read_part`'s new checks; `decode_part`, `stored_form`, `expand`, the identity over `D` | `--selfcheck` item 10 (`expand == RAM`) on a split course (a string inside the check); `read_part` refuses each bad pair (a dangling offset, a pair named twice, a split VOID-VOID, a SAFE split cell) - **DONE: `D` 8 bytes a halved cell, 16 a quartered one; six reader refusals; both stored forms expand in place; the CELLS rule without halves red** |
| D1.4 [x] | **The picture**: triangles, the cell-edge faces by the owning half, the FRONT face, the TB edge line, the order `(2 s + d, wx)`, the crystal per half; the per-pixel `(s, top)` keys with the down half at `s + 1`; the records and their bounds | `--selfcheck` item 3 (map decodes to the picture) and item 5 (records against the per-pixel buffer) on the split course; `--png` previews of the four mock-up scenes from `.bbc` text, compared by eye with the prototype's - **DONE: items 3 and 5 on THE SPLIT COURSE; `--png split:` (the SPLIT course and the five mock-up scenes, looked at against the prototype's); the down half's key with its red arm** |
| D1.5 [x] | **The bytes**: `--sizes` on the split course; `bzcourse.inc` gains `BZ_KTB`, `BZ_KLR`, `BZ_GF_SPLIT`; nothing in the guest yet reads them, and no shipped course uses a half (the tool refuses `half` and `box` in a `BZ_COURSES` file until D3 lands - one line, removed by D3) | `make bonanza`; `make` - **DONE: `--sizes split:`; `BZ_KTB`, `BZ_KLR`, `BZ_KQ`, `BZ_KCHANNEL`, `BZ_GF_SPLIT`, `BZ_PAIR`, `BZ_QUAD`, `BZ_DIAG`, `BZ_DWMIN`; `make bonanzadisk` ok** |

**D1's rows (named, not run)**: `bonanzacourse`.

### Wave D2: the model (host only)

| # | story | verified by |
|---|---|---|
| D2.1 [x] | **The half pick and the floor** (128.24.7.1): `Physics` reads the centre's RECORD wherever 128.11.8 reads C | `--selfcheck`: a roll off a diagonal edge (the take-off at the pick's boundary), a fall into a VOID half and its kill height, a goal half's exit - **DONE: `Physics.prec`; the take-off at the pick, the VOID half's kill height, a goal half's exit, each `--selfcheck` item 7, the pick swapped red** |
| D2.2 [x] | **The diagonal inside the cell** (128.24.7.2): the push and the reflection in fixed point, the clamp, the refill after a push that changes cell | a scripted slide along a diagonal rail at a shallow angle (the tangential speed kept, within 1/256 a step); a head-on hit (the normal component reflected to `e |wv| >> 8`); red arms: `σ` flipped, the clamp dropped - **DONE: `_inner`, `_dline` (its docstring the guest's arithmetic). Built finding: NO CLAMP is needed (every e <= 256), and the tangential speed is EXACT; 4,000 random states; the slide; a head-on rebound; `σ` flipped red** |
| D2.3 [x] | **The edges by the owning half** (128.24.7.3) and **the corner** (128.24.7.4): the ray, its choice, the radial fallback with "either half" | a ball run along a straight diagonal rail through whole and split cells alike stays at 6 gu from the line (no corner kicks); a wall's END met radially (the rebound along the tip's radius); red arms: the ray choice inverted (an invisible extension hits), every endpoint radial (the 45-degree kick) - **DONE: `erec`, `RAYS`, `_krec`; the slide at DIAG or DIAG + 1, no kick; a wall's END met radially, the ray choice inverted red; every end radial red; the owning halves swapped red. Built finding: no radial corner where the facing ray's piece blocks (K on a straight wall)** |
| D2.4 [x] | **`BZ_PHYSV`**: `PHYS_REV` raised, `DIAG` and the two tables hashed, the old value appended to `PHYSV_SHIPPED`; `moon.bzd`, `summit.bzd`, `playground.bzd` written again by `bbcourse.py author` (each diff its `physics` line) | the build's demo checks; `--selfcheck` item 4 (`check_physv`) - **DONE: BZ_PHYSV 21h -> B1h; the three demos' diffs their physics lines** |
| D2.5 [x] | **The host tools that walk a course** through the model: `build_reach` (the apex per half), `reach_closure` and NO TRAP, `check_exits` (every finish reachable), `play_sweep`, `trap_reach`; the shadow (`OCCG`) | `--selfcheck` on the split course: every check that runs on a shipped course runs on it - **DONE: per record (`rec_map`, `rec_adj`); RAIL with a pad, a flag, a clock and a goal half through exits, NO TRAP, the finish's reach and the clock rule** |

| R4 [x] | **QUARTERS** (the owner's Q3): kind 6, four records N E S W; `quarter`; a box's corners; the picture (front faces on W and N, the edge line on T - c and c - B, E and S keyed s + 1); the model (the pick by two tests, the quarter's two lines, the centre met radially by the opposite quarter); priced (SPEC.md 128.24.7.6, 128.24.10) - **DONE**: RAIL's wall quarter: its inner line at DIAG, the centre radial, the pick swapped red |

**D2's rows (named, not run)**: `bonanzacourse`, `bonanzademo`.

### Wave D3: the guest

| # | story | verified by |
|---|---|---|
| D3.1 | **The CELLS rules** (128.24.5.3): `bz_cxcel` and `bz_cxsafe` read a split cell's pair | the package's own `bz_cexp` under unicorn on the split course's stored form equals the RAM form (128.15.6's host check); red arm: the SAFE rule without halves, red at `bonanzaexit`'s claim leg |
| D3.2 | **The window**: `bz_nbh`, `bz_fill` and `bz_win9i` fill it under `GF_SPLIT`, `bz_ps` bit 3; the step's split path entered by the existing test | a course with no split cell: the step's instructions unchanged (the listing's diff, and `bonanzaperf`'s step price within 128.24.7.6's 20 clk) |
| D3.3 | **The step**: the pick, `bz_blocks`' split dispatch, the diagonal push, the corner ray, the fallback, the void half's kill | `bonanzaphys` on the split course (the guest equals the model at every frame); red arm: the corner ray dropped |
| D3.4 | **The price**: bytes from the listing, clocks from the instructions (unicorn, 128.11.15's method) on the split course's runs, against 128.24.7.6 and 128.24.10 | the figures written into SPEC.md 128.24 as BUILT / PRICED |

**D3's rows (named, not run)**: `bonanzaphys`, `bonanzaexit`, `bonanzaperf`, `bonanzaring`.

### Wave D4: the pathway

| # | story | verified by |
|---|---|---|
| D4.1 | **`_route_lay`'s bands** (128.24.8): up and down 32 px, across 16 lines; the merge of two routes' halves; `path.bbc` unchanged as text | `--selfcheck`'s pathway proofs; the follower's points unchanged (`bonanza_path.py --check`); a `--png` of the map |
| D4.2 | **The crystal per half** (128.22.8's inks on a triangle and on a front face) | the preview; one MartyPC look on both cards (the route from MILL up to MOON) |

**D4's rows (named, not run)**: `bonanzapath`, `bonanzacourse`.

### Wave D5: the owner's look

| # | story | verified by |
|---|---|---|
| D5.1 | **PLAYGROUND's diagonal section** (Q8): a straight-up lane with rails, a 45-degree course edge, a diagonal step with its front face, a lane that climbs (`ramp s`); `playground.bzd` written again | the build; `--selfcheck` |
| D5.2 | **The look**: MartyPC, CGA and Hercules, through `tools/os88ui.py`; the front face, the edge line, the rail's ends (Q2) | screenshots cropped and zoomed for the owner |
| D5.3 | **MOON's coast** (Q8): its straight (`floor band 0 6 48 70` between `wall band -2 -1 48 70` and `wall band 7 8 48 66`) rewritten as a `box` with straight rails; the authored demo, which meets the left rail's zigzag at a corner on every cell from (27, 26) to (31, 30), written again (`bbcourse.py author`); its NO TRAP and exits re-proved | the build's demo check; `--selfcheck`; the model's corner contacts on the coast 0 (MEASURED today: 40 corner contacts over the demo) |
| D5.4 | **The owner plays it**: the rail's feel, `BZ_DWMIN`, the lane's width, the step | the diary |

### The final pass

The deduplicated union of the waves' rows once (`bonanzacourse`,
`bonanzademo`, `bonanzaphys`, `bonanzaexit`, `bonanzaperf`, `bonanzaring`,
`bonanzapath`, `bonanzagame`), then `test-full`, then the disks.

## Footprint

Wave 9 (mechanics as parts) is built by another session in the same two
places, so the diagonal work stays local there, and this is every routine it
touches (the owner passes it on):

- **`apps/bonanza/bzphys.inc`**: `bz_step` (step 4's `bz_ps` mask at `.w4`;
  `.walls`, which calls the two new routines round the edge tests; the
  centre's RECORD pointer at `.floorh`, `.nfloor` and the fallback `.fb`;
  `.pps`, where `bz_ps` is rebuilt, keeping bit 3); `bz_psync` (bit 3);
  `bz_blocks` (`.other`'s kind dispatch to a split); `bz_corner` (`K`
  blocked by either half, and by the other ray); `bz_refl` (a second entry
  taking `BZ_DWMIN`); `bz_fill` and `bz_win9i` (`bz_nbh`, `GF_SPLIT`).
  **New**: `bz_dpick` (the half pick), `bz_diag` (the push and reflection
  off a diagonal, the cell's own or a corner's line), `bz_dray` (the
  corner's quadrant, distance and ray); bss `bz_nbh`.
- **`apps/bonanza/bonanza.asm`**: `bz_cxcel` and `bz_cxsafe` (the CELLS
  rules by halves); `GF_SPLIT` read where the grid flags are read.
- **`tools/bbcourse.py`'s model, AS BUILT (D2)**: `Grid.cell` (a split
  cell reads `(0, 0, 0, kind, flags, surface)`), new `Grid.pair` and
  `Grid.rec`; `Physics.__init__` (the red-arm switches, `wsplit`),
  `Physics.blocks` (asserts it is given a record), `Physics._fill` (bit 3,
  `wsplit`), `Physics._ps`, and `Physics.step` - step 2 (the centre's record's
  slopes, the cell's surface), step 5 (the lines inside the centre's cell
  first, the four edges through `erec`, the corner's rays and the radial
  corner's `K`), the fallback and step 6 (the centre's record). **New**:
  `Physics.erec` (an edge's owning record), `Physics.prec` (the pick),
  `Physics._inner` (a halved cell's diagonal; a quartered cell's two lines and
  its centre), `Physics._dline` (the push and reflection off any diagonal
  line - its docstring is the guest's arithmetic), `Physics._krec` (a corner's
  records); tables `RAYS`, `OWNER`, `K_RECS`, `split_tables()`;
  `PHYS_CONSTS` gains `DIAG` and `DWMIN`, `phys_tables` `split_tables()`,
  `PHYS_REV` 12. Wave 9's own changes to `bbcourse.py` (the Y0 search) meet
  the diagonal work only in `_cell_pieces` (the per-pixel keys) and the
  identities.
- **The guest's names above** (`bz_dpick`, `bz_diag`, `bz_dray`) are D3's
  plan, unbuilt; the model's routines they will copy are `prec`, `_dline`
  plus `_inner`, and step 5's ray block.
- The tool's other consumers of a course are D1.1's list (host only).

## What is not in this plan

- Halves on the courses themselves (beyond PLAYGROUND's section): the course
  waves (the 14 - 20 courses) use them as they are written.
- Quarter tiles and free polygons (128.24.1: nothing the screen shows needs
  them).
- Kinds 6 - 15 stay reserved for 128.10.4.3's non-planar floors.
