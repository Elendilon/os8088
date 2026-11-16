# BOUNCE BONANZA: shaped floors (chutes and the pit)

*The contract is SPEC.md 128.27; where this plan and it disagree, it wins.
It builds the kind 128.24.13 reserved (kind 7) as the FIELD cell. The diary
entries are in [BOUNCE-BONANZA-DIARY.md](BOUNCE-BONANZA-DIARY.md) under
"shaped floors".*

The owner, R4: a CHANNEL is "a tile, or two tiles together, that cradle the
ball"; and next "a pit made of curved sides that you have to enter with
enough speed to make it around and over and fly up the other side, instead
of falling through to the hole in the bottom".

## Where it stands

Branch `bounce-shaped`, cut from `bounce-bonanza` at `38d7a1f`. It is kept
apart from `bounce-ground` (which changes how block faces extend into the
void, `draw_ops`' `FACE8`, and SPEC.md 128.15.8's budget): this branch
leaves both alone, so the two merge without meeting.

## The shape of the work

| wave | what | depends on |
|---|---|---|
| C0 | the contract (SPEC.md 128.27), this plan, the diary | the investigation |
| C1 | the tool: the FIELD kind, section `F`, the shape generator, the picture, the grammar, the reader | C0 |
| C2 | the model: `bbcourse.Physics` on FIELD cells, the reach; the tuning by scripted runs | C1 |
| C3 | the guest: `bzphys.inc` equal to the model under unicorn; one MartyPC measurement | C2 |
| C4 | a showcase on PLAYGROUND (or a test course); previews looked at; the disk built | C3 |
| final | the rows once (the integrator's), `test-full` | C4 |

## The stories

### Wave C0: the contract

| # | story | verified by |
|---|---|---|
| C0.1 [x] | SPEC.md 128.27 written: the cell, section `F`, the grammar, the shapes, the physics (the lift and field-to-field rule), the picture, the guest's hooks, the predicted cost; 128.24.13's reservation pointed at it | `tools/checkdocs.py` |
| C0.2 [x] | this plan and the diary's first entry | read |

### Wave C1: the tool (host only)

| # | story | verified by |
|---|---|---|
| C1.1 [ ] | `FieldTile` beside `Tile` and `Split`; kind 7 `KIND_FIELD`; `BZ_KFIELD` in `bzcourse.inc` (replacing `BZ_KCHANNEL`) | `--selfcheck` |
| C1.2 [ ] | the grammar: `chute` and `pit`, the refusals of 128.27.3 as string cases | `--selfcheck`'s field item, each refusal named |
| C1.3 [ ] | the generator: straights (level and sloped), tapers, 1- and 2-wide radial corners, the pit; the normalisation and the table search over the 8 symmetries; the slope bound and the SEAM rule | `--selfcheck`: every table under every symmetry against its world function; red arms (a symmetry's mirror wrong, a seam off by one) |
| C1.4 [ ] | the grid and section `F`: `build_cells`, `GF_FIELD`, the encoder, `decode_part`, `read_part` (and its refusals), the CELLS rule (`V` of kind 7), `expand == RAM` | `--selfcheck` item 10 on a field course; reader refusals |
| C1.5 [ ] | the picture: facets, culling, inks, faces along the profile; the occluder key; previews CGA and Hercules | the PNGs, looked at |
| C1.6 [ ] | every shipped course's part byte for byte unchanged | the identities before and after |

### Wave C2: the model

| # | story | verified by |
|---|---|---|
| C2.1 [ ] | `Physics`: the floor and the slopes of a FIELD centre, the edges and the corner with the lift and the field-to-field rule, the fallback unlifted; never SAFE, GOAL or FIRM | `--selfcheck` scripted runs, red arms (no lift, field neighbours blocking) |
| C2.2 [ ] | the reach (`build_reach`), the exits, NO TRAP, the occluders on a field course | `--selfcheck`, a field course compiles |
| C2.3 [ ] | the tuning: the corner carries round for 1- and 2-wide at several speeds, flies out over the lip when too fast, comes to rest without a dither; the pit's ride round against its fall through. The profiles' constants written into 128.27.4 | the scripted runs' table in the diary |

### Wave C3: the guest

| # | story | verified by |
|---|---|---|
| C3.1 [ ] | `bzphys.inc`: `bz_fhp`, `bz_fh4`, the hooks of 128.27.7, `BZ_FSYM`, `bz_fsb`; `bonanza.asm`: `bz_cxcel`'s `V`, the hostile bound | unicorn: the guest equals the model step for step on field courses (`tests/bonanza_dsplit.py` extended), a HOSTILE field part reads nothing outside the part |
| C3.2 [ ] | the cost: ONE MartyPC measurement of the field step and the occluder cost in a channel, against 128.27.8 | the number, in 128.27.8 and the diary |
| C3.3 [ ] | `make bonanza`: image and bss delta measured | 128.27.8 |

### Wave C4: the showcase

| # | story | verified by |
|---|---|---|
| C4.1 [ ] | PLAYGROUND (or a new test course): a 2-wide chute with two curved corners, a 1-wide chute, a sloped leg, a pit | compiles; previews looked at, CGA and Hercules |
| C4.2 [ ] | the bonanza disk builds | `make bonanzadisk` |

## The rows (named, run once in the final pass)

- `bonanzacourse` (`--selfcheck`): the field items.
- `bonanzaphys`: `tests/bonanza_dsplit.py`'s field legs (host, unicorn).
- `bonanzaperf`: the field step priced.
- `bonanzaring`, `bonanzaexit`, `bonanzademo`, `bonanzagame`: the course
  that carries the showcase, and every demo re-stamped under the new
  `BZ_PHYSV`.
