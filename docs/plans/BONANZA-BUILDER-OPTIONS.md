# Bounce Bonanza builder: every option has a control (audit, 2026-11-22)

The owner, after the see-saw's timed mode had no control: *"Want to do a check if any other props are missing
options they have available? I'd run into them as I tried to use them, but catching them ahead of time is
better."* This is that check: every statement the course grammar accepts (tools/bbcourse.py's statement dispatch
and its `_parse_*`, SPEC.md 130's grammar blocks), every optional clause, flag or mode it takes and every value
with a fixed choice set, and whether the builder (tools/bbedit.py, SPEC.md 130.58) could set it without typing
the statement by hand.

**Before** is the builder as it stood at `7ddb743cb`. Its inspector was GENERIC for most statements: coordinate
spinboxes, and a spinbox or combobox for a fixed list of clause words (`flat`, `period`, `on`, `seed`,
`strength`, `range`, `for`, `face`, `along`, `channel`, `style`, ...) **only if that word was already written**.
An optional clause the author had not typed had no control. **Now** is this change: `tools/bbedopts.py`, one
row per clause (word, kind of value, legal values or range, default, label, hint), drawn by `_option_rows` for
every statement whether the clause is written or not (SPEC.md 130.58.36).

Key: *missing* = no control unless typed; *if written* = a control only when the word was already there;
*bespoke* = a section of its own (left as it was).

## Placed parts

| statement | clause / value | legal | before | now |
|---|---|---|---|---|
| `floor` `wall` `goal` | `flat H` / `ramp AX P0 P1 H0 H1` | heights, rate whole half units | bespoke (Slope) | unchanged |
| | surface, hang (`surface`, `float`) | normal ice sand bounce; hang depths | bespoke | unchanged |
| | `half SIDE`, `quarter N`, `box ... chamfer N` | pieces | missing | **left**: a piece's shape is a picture interaction; the area's Cut a corner and Diagonal strip make the common ones |
| `goal` | `exit E` | 0 - 3 | missing | row |
| | `hidden` (a secret finish) | flag | missing | tick box |
| `hole` | - | | | |
| `surface` | the surface | normal ice sand bounce | combobox | unchanged |
| `water` | `top H`, `bed B` | units | if written (always is) | rows |
| | `open` | flag (after `bed`) | missing | tick box |
| | `ripple` / `always` cells | cells of the pool | missing | **left**: naming cells is a picture interaction (coord_slots already moves them) |
| `arch` | its face | `+x` `+y` (positional) | missing (the generic `face` looked for a word) | radio |
| | `guard` | flag | missing | tick box |
| | `height H` | 1.5 - 3 units, after `guard` | if written | row, shown with `guard`; unticking `guard` takes it out |
| `float` | `thick U` | 0.25 - 3 units | missing | row |
| `gap` | `sw` / `se` | one side, or both | missing | radio (both faces / sw / se) |
| `guard` | `side +x -x +y -y \| all` | any of four | missing | four tick boxes (none: the floor's open edges) |
| | `height H` | 1.5 - 3 units | if written | row |
| `seesaw` | size, axis, `period [flat] [seed]` | 130.42.2, 130.42.11 | bespoke (the lead, 130.58.35) | unchanged |
| | `rest -\|+` | after `pivot` | missing | radio |
| | `pivot H` | units | if written (always is) | unchanged |
| `archway` | `along x\|y` | | combobox | row |
| | `under U` | 2 - 4 units | if written | row |
| `chute` `pit` `hump` `tube` | every clause | | bespoke (shape editor, 130.58.29 / 33) | unchanged: the shape editor's forms cover all of them |
| `cup` | `capture V` | 64 - 384, right after the cell | missing | row |
| | `exit E`, `hidden` | 0 - 3; flag | missing | row, tick box |
| `checkpoint` | `ball M` | rubber steel glass | missing | combobox |
| `clock` | `frame STYLE` | 16 styles, before `digits` | missing | combobox |
| | `digits DX DY` | px | missing | two spinboxes |
| `spring` | its gvz (positional) | 256 - 768 | missing | spinbox |
| `pad` | the ball (positional) | rubber steel glass | combobox | radio |
| `label` | `ink C` | 0 - 3 | missing | row |
| `way` | `branch NAME` | 1 - 5 of A-Z 0-9 | missing (the route list only shows it) | entry |
| `start` | - | | | |
| `prop windmill` | `period P` | 32 64 128 256 | if written | radio |
| | `closed C0 C1` | pose boundaries | missing | two spinboxes |
| | `seed S` | under P | if written | row; a shorter period drops a seed or `closed` it no longer holds |
| `prop bumper` | `kick K` | 1 - 384 | if written | row |
| `prop platform` | its rise L (positional) | 1 - 8 units | missing | spinbox |
| | `period`, `dwell`, `seed` | 64 128 256; under P/4; under P | if written | rows |
| `prop turntable` | `size N` | 2 3 | missing | radio; a new size starts a legal `fill` |
| | `fill` | half filled rows | missing | entry (the pattern) |
| | `quarter`, `turn`, `seed`, `warn` | 32 64; cw ccw; under 4Q; under Q | `seed` if written | rows; a shorter quarter drops a seed or warning past it |
| `prop bridge` | `channel C` **or** `period P on N [seed S]` | the two forms | the written words only | **Opened by** a channel / a timer, then its rows |
| | `style`, `art` | 4 styles; gates/*.bba drawn for a bridge | `style` if written | style row; no art row (no bridge art is drawn yet), noted |
| `prop gate` | `channel`, `along`, `style`, `art` | 4; x y; 4; gates/*.bba drawn for a gate | `channel` `along` `style` if written | rows; `style` and `art` exclude each other |
| `prop plate` `prop key` | `channel` | 4 | if written (always is) | row |
| `prop boost` | `face`, `strength`, `flat` | 4 dirs; 1 - 127; flag | `face` `strength` if written | rows |
| `prop magnet` | `face [down] WAY`, `range`, `strength` | 4 dirs; 1 - 8 (1 hanging); 1 - 127 | `face` read `down` as the direction and offered to overwrite it | rows; **Hangs** ticks `down` in after `face` and drops `range` |
| `prop blower` | `face` | +x -x +y -y **up** | combobox without `up` | radio with `up`; up adds `top 4`, another way takes `top` and `lift` out |
| | `strength`, `top`, `seed` | 1 - 127; 1 - 24; under the gust | if written | rows (`top` with up, `seed` with a gust) |
| | `gust ON OFF`, `lift`, `flag` | on + off a power of two 32 - 1024; flags | missing | rows |
| `prop popspikes` | `period`, `on`, `seed` | 32 - 256; 1 - P-1; under P | if written | rows; a shorter period halves an `on` past it |
| `prop crack` | `hole` | small band wide | missing | radio |
| `prop speed` `prop jump` | `for S`, `overwrite`, `respawn` | seconds; flags | `for` if written; flags bespoke | rows |
| `prop life` | `once` | flag | bespoke | row |
| `prop hourglass` `glass` `spikes` `membrane` | - (spikes and membrane: an optional `X1 Y1` rect, written by their templates) | | From / To | unchanged |
| `prop probe` (BZDEV) | `reset attempt\|respawn` | | missing | **left**: a test element, not in the palette |
| any of `checkpoint spring pad clock prop archway label` | trailing `hidden` (no warning) | flag | tick box | unchanged |

## Course-level statements

Not the inspector's: the Course tab sets `course`, `width`, `ball`, `music`, `palette`, `gatestyle`, `target`,
`limit`, `medals` and `strict`; `uses` is kept by the builder itself; `noocclude` by the occluder view
(130.58.32); `accept` from the Checks list. `view [drop]`, `origin`, `lock`, `stop`, `fshow`, `masks`, `art`,
`title`, `version`, `trap`, `guide`, `test` and `pathway` are written by hand (they belong to the picture and the
pathway rather than to a part) and were outside this audit.

## Palette templates placed on a plain floor

Each part of the palette added on a flat floor (a cell, or a 3 x 3 area for a rect part) by `add_part`: all
compile except

- **Windmill, Lift, Seesaw**: refused there and explained in plain words (a windmill on a KEEP tube's mouth, a
  lift in an empty shaft, a see-saw over empty space) - the template is right, the place is not.
- **Gate, Pressure plate, Key**: each is refused ALONE in every placement, because a gate and its opener are a
  pair (130.41.7) and the palette adds one at a time. Now explained (EXPLAIN in bbedit.py): *Keep it anyway*,
  then add the other half on the same channel - which then compiles (checked). A later change could add both
  halves at once.

## Checks

- `tests/unit/t_bbedit.py` item 17: every clause in `bbedopts.GRAMMAR` (this audit's list) has its row and every
  row is in it; each row reads its value off a statement with every clause written, and cleared and set back the
  statement is legal again (so a clause goes back where the grammar wants it); on the bare statement each row's
  default is legal and clearing it gives the bare statement back. Red by hand: crack's `hole` row deleted, or
  the see-saw's `rest` row appended at the end instead of after `pivot`.
- Under Xvfb (python3.12, Tk): boost, magnet, blower, popspikes, crack, gate, cup, checkpoint, spring, speed,
  guard, bridge, clock, goal and way on a constructed course; windmill, turntable, see-saw and archway on
  mill.bbc; lift, water, arch and float on down.bbc - each control invoked, the statement and the compiler's
  verdict printed, and the inspectors looked at.
