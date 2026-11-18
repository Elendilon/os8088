# BOUNCE BONANZA: shaped floors (chutes and the pit)

*The contract is SPEC.md 130.28; where this plan and it disagree, it wins.
It builds the kind 130.24.13 reserved (kind 7) as the FIELD cell. The diary
entries are in [BOUNCE-BONANZA-DIARY.md](BOUNCE-BONANZA-DIARY.md) under
"shaped floors".*

The owner, R4: a CHANNEL is "a tile, or two tiles together, that cradle the
ball"; and next "a pit made of curved sides that you have to enter with
enough speed to make it around and over and fly up the other side, instead
of falling through to the hole in the bottom".

## Where it stands

**C0 - C4 BUILT** (SPEC.md 130.28 "Built so far"), with C4 partly: the pit
is not on a shipped course (story C4.1). The rows below are named, not run.

Branch `bounce-shaped`, cut from `bounce-bonanza` at `38d7a1f`. It is kept
apart from `bounce-ground` (which changes how block faces extend into the
void, `draw_ops`' `FACE8`, and SPEC.md 130.15.8's budget): this branch
leaves both alone, so the two merge without meeting.

## The shape of the work

| wave | what | depends on |
|---|---|---|
| C0 | the contract (SPEC.md 130.28), this plan, the diary | the investigation |
| C1 | the tool: the FIELD kind, section `F`, the shape generator, the picture, the grammar, the reader | C0 |
| C2 | the model: `bbcourse.Physics` on FIELD cells, the reach; the tuning by scripted runs | C1 |
| C3 | the guest: `bzphys.inc` equal to the model under unicorn; one MartyPC measurement | C2 |
| C4 | a showcase on PLAYGROUND (or a test course); previews looked at; the disk built | C3 |
| final | the rows once (the integrator's), `test-full` | C4 |

## The stories

### Wave C0: the contract

| # | story | verified by |
|---|---|---|
| C0.1 [x] | SPEC.md 130.28 written: the cell, section `F`, the grammar, the shapes, the physics (the lift and field-to-field rule), the picture, the guest's hooks, the predicted cost; 130.24.13's reservation pointed at it | `tools/checkdocs.py` |
| C0.2 [x] | this plan and the diary's first entry | read |

### Wave C1: the tool (host only)

| # | story | verified by |
|---|---|---|
| C1.1 [x] | `FieldTile` beside `Tile` and `Split`; kind 7 `KIND_FIELD`; `BZ_KFIELD` in `bzcourse.inc` (replacing `BZ_KCHANNEL`) | `--selfcheck` |
| C1.2 [x] | the grammar: `chute` and `pit`, the refusals of 130.28.3 as string cases | `--selfcheck`'s field item, each refusal named |
| C1.3 [x] | the generator: straights (level and sloped), tapers, 1- and 2-wide radial corners, the pit; the normalisation and the table search over the 8 symmetries; the slope bound and the SEAM rule | `--selfcheck`: every table under every symmetry against its world function; red arms (a symmetry's mirror wrong, a seam off by one) |
| C1.4 [x] | the grid and section `F`: `build_cells`, `GF_FIELD`, the encoder, `decode_part`, `read_part` (and its refusals), the CELLS rule (`V` of kind 7), `expand == RAM` | `--selfcheck` item 10 on a field course; reader refusals |
| C1.5 [x] | the picture: facets, culling, inks, faces along the profile; the occluder key; previews CGA and Hercules | the PNGs, looked at |
| C1.6 [x] | every shipped course's part byte for byte unchanged | the identities before and after |

### Wave C2: the model

| # | story | verified by |
|---|---|---|
| C2.1 [x] | `Physics`: the floor and the slopes of a FIELD centre, the edges and the corner with the lift and the field-to-field rule, the fallback unlifted; never SAFE, GOAL or FIRM | `--selfcheck` scripted runs, red arms (no lift, field neighbours blocking) |
| C2.2 [x] | the reach (`build_reach`), the exits, NO TRAP, the occluders on a field course | `--selfcheck`, a field course compiles |
| C2.3 [x] | the tuning: the corner carries round for 1- and 2-wide at several speeds, flies out over the lip when too fast, comes to rest without a dither; the pit's ride round against its fall through. The profiles' constants written into 130.28.4 | the scripted runs' table in the diary |

### Wave C3: the guest

| # | story | verified by |
|---|---|---|
| C3.1 [x] | `bzphys.inc`: `bz_fhp`, `bz_fh4`, the hooks of 130.28.7, `BZ_FSYM`, `bz_fsb`; `bonanza.asm`: `bz_cxcel`'s `V`, the hostile bound | unicorn: the guest equals the model step for step on field courses (`tests/bonanza_dsplit.py` extended), a HOSTILE field part reads nothing outside the part |
| C3.2 [x] | the cost: ONE MartyPC measurement of the field step and the occluder cost in a channel, against 130.28.8 | the number, in 130.28.8 and the diary |
| C3.3 [x] | `make bonanza`: image and bss delta measured | 130.28.8 |

### Wave C4: the showcase

*After the merge with bounce-bonanza (130.27 GROUNDED FACES, the pickups yard) PLAYGROUND's section no
longer fits its part (69.7KB in the RECB 8 layout): it was taken off, and the knob build's two test
courses (C5) carry every shape instead.*

| # | story | verified by |
|---|---|---|
| C4.1 [~] | PLAYGROUND (or a new test course): a 2-wide chute with two curved corners, a 1-wide chute, a sloped leg, a pit | **PARTLY**: PLAYGROUND carries the 2-wide chute (two radial corners, a climbing leg, a falling one) and the 1-wide chute; the PIT does not fit (its RECB 8 layout would be 73.7KB, SPEC.md 130.28.8) and a new course is a tour course (MAIN's 13 lines are full: `bzface.inc`), so the pit is in `--selfcheck`'s PIT course and the guest's harness only - the owner's call where it goes. Previews looked at, CGA and Hercules |
| C4.2 [x] | the bonanza disk builds | `make bonanzadisk` |

### Wave C5: the knob build (the owner, 2026-11-17)

| # | story | verified by |
|---|---|---|
| C5.1 [x] | `BZSHAPES=1` (Makefile, `#> [Knobs]`, stamped): SHAPE and PITS added after the shipped courses, not on the TOUR; the pathway compiled through `courses/pathshapes.sed` with SHAPE on pad 0 (Play Game, Enter) and PITS and FIRST on pads 6 and 7 | the knob's private tree builds; the knob-less `bonanza.o88` `cmp`-identical with and without the knob code |
| C5.2 [x] | the two courses: both chute widths in both profiles, corners both ways, tapers, a climbing and a falling leg, pits with and without a hole, a SAFE plate round everything | previews looked at, CGA and Hercules; each part inside one part and the RECB 8 limit |
| C5.3 [x] | the FIELD faces over the void follow 130.27's ground rule and `float` | `_field_ops` |

### Wave C6: the occluder cut and 32 tables (the owner, 2026-11-17)

*The owner, having played the knob build: "none of the fronts of the shapes could hide the ball; only
falling through the hole in the center, or falling completely behind the tile". Measured: the FIELD
cells' records were cut for a ball at a channel's bottom height anywhere in the cell - under the lip, a
pose that does not exist. And: "32 shape tables", approved.*

| # | story | verified by |
|---|---|---|
| C6.1 [x] | every record the shapes add CLASSIFIED (SHAPE, PITS against their plates): by the balls whose poses need it - on the surface, in the pit's hole, behind the edge - and by the geometry that drew it | 130.28.6's table |
| C6.2 [x] | the cut takes a FIELD cell's ball at its REAL poses (the floor at its integer point, its lit circle), the merge's queries its 4 x 4-unit squares; the behind-the-edge records counted and left to the edge's own occlusion work | `--selfcheck`: sampled real poses laid exactly as the rule hides them, the pit's hole too; red, the floor 3 px high; the model never under that floor, red 1 px high |
| C6.3 [x] | `FTOPQ` re-measured with the new cut: still needed (1 and 4 px break the four-a-block bound, 8 px costs 71 - 164 records) | 130.28.6 |
| C6.4 [x] | 32 tables: the +1's bit 7 the shape's fifth bit - SPEC first, then the tool, `read_part`, the guest (`bz_fhp`, `bz_dval`, `bz_fsb`), the harness (a course MANY of 17 tables; `nofifth` red) | `make bonanza` +5 image, +32 bss; `tests/bonanza_dfield.py` |
| C6.5 [x] | the STANDARD profiles (the owner's design rule): courses reuse a small set of chute profiles and depths so tables are shared, a one-off special shape still allowed at its own tables' cost; the tool prints each shape statement's tables added and shared | the course report |

### Wave C7: the picture (the owner, 2026-11-17)

*The owner: "We might work on the dither visuals a bit"; after two rounds of options, "it was the
colors ... mchkgrid2 is the winner of them".*

| # | story | verified by |
|---|---|---|
| C7.1 [x] | two rounds of shading options (eight, then eleven magenta-only) previewed on both cards with their sizes, for the owner to choose | the diary's account; the owner's choice |
| C7.2 [x] | the chosen ink: the cell's parity as two magentas (solid, and black every other line) under the floor's black cell lattice carried over the shape, by a per-facet screen-to-ground map; no light | SPEC.md 130.28.6; the previews, CGA and Hercules |
| C7.3 [x] | no floor ink inside a shape: a facet is the floor only when its three corners lie on the LIP (each FIELD tile's lip heights, the piece's function without its depth) - the cyan corners inside a bowl and at chute corners and tapers gone | before/after crops of the bowl, the dish, the corners and the tapers |
| C7.4 [x] | picture only: every section but `M`, `B` and the offsets into them byte-identical to the first ink's | the sections' hashes, both test courses |
| C7.5 [x] | the JOIN rule (the owner, 2026-11-17: a raised corner "looks 'see-through' ... only join into the corner if another tile at the same elevation exists", per touching side): a lip-level triangle takes the floor's ink only when joined, edge by edge, to plain floor at its own height; a raised corner or a corner over the void is wholly magenta | before/after crops of SHAPE's raised and upper-left corners, the chute ends, the pit rims, PLAYGROUND's back corners, CGA and Hercules; `--selfcheck` (red: every lip-level triangle joined); every section but `M`, `B`, the offsets into them and the identity byte-identical (SHAPE, PITS, PLAYGROUND), PLAYGROUND's demo re-authored (its `ident` line only) |

### Wave C8: occlusion that happens, and the SHOW rule as a toggle (the owner, 2026-11-17)

*Play found the gap: a GROUNDED ball on a chute or a pit was never occluded, because the guest gates
the pass for a grounded ball on the cell's `OCCG` and no FIELD cell carried one. The owner played two
builds - A, the real-pose cut with `OCCG` on the FIELD cells, and B, the SHOW rule (branch
`bounce-shapeocc`, 154aee730) - and chose: "A is actually better, having now played with occlusion
happening at all. B is still cheaper, in every way; so can we keep it around as a toggle we can turn on
at will?"*

| # | story | verified by |
|---|---|---|
| C8.1 [x] | A, THE DEFAULT: a FIELD cell is `OCCG` where a grounded ball at one of its REAL grounded poses (each integer point at its floor, margin `BZ_CLIMB`) meets a laid record - SHAPE 80 of 81 reachable FIELD cells, PITS 50 of 94, PLAYGROUND 55 of 71 (the whole-cell form: 80, 56, 58) | SPEC.md 130.11.4.3, 130.28.6; `--selfcheck`: every grounded model step on a FIELD cell a record hides is on an `OCCG` cell (red: no FIELD `OCCG`, all ungated) |
| C8.2 [x] | B, THE TOGGLE, off by default: 154aee730's SHOW rule brought in whole, on with `make BZFSHOW=1` (`bbcourse --fshow`) for every course or a course's `fshow` statement; off, A's parts; on, exactly 154aee730's (the same records, masks, sizes and identities) | `--selfcheck`: the SHOW items on the toggle's arm with their red arms; `fshow` and `--fshow` give the arm's part, `fshow` twice refused; the knob build `build/shapesb` |
| C8.3 [x] | every course without FIELD cells byte-identical; PLAYGROUND's demo re-authored (ident line only, 8803h -> D427h), and a `BZFSHOW=1` build re-stamps it (the rule moves the picture alone; the replay still checks it) | `cmp` of every part against the base tree; the four builds |
| C8.4 [ ] | A's grounded pass on a chute, PREDICTED about 2.2k clk a grounded step (SHAPE, median 1.4k, worst 12.9k): to be MEASURED on MartyPC in the final pass | `bonanzaperf`, a chute's grounded run |

## The rows (named, run once in the final pass)

- `bonanzacourse` (`--selfcheck`): the field items.
- `bonanzaphys`: `tests/bonanza_dsplit.py`'s field legs (host, unicorn).
- `bonanzaperf`: the field step priced.
- `bonanzaring`, `bonanzaexit`, `bonanzademo`, `bonanzagame`: the course
  that carries the showcase, and every demo re-stamped under the new
  `BZ_PHYSV`.
