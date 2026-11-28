# CHUTE3: what 3-wide chutes cost (a costed study, 2026-11-20)

*Status (later the same day): **TAKEN, ON TRIAL.** The owner: "Have an agent do the tool work. After I test
it we'll decide if it stays, or if we go back to 2." Section 5's items 1, 2 and 4 are done: `chute 3` is in
SPEC.md 137.28.3 / 137.28.4 marked on trial, the leg-length refusals name which leg and its minimum,
`--selfcheck`'s `splitphys` section carries the CHUT3 course (8 orientations, 10 tables), the short-leg
refusals, the 15 / 13 px ring, three FIELD runs and two SEAM-rule red arms, and DOWN's sketch lays the line
3 wide (`CHUTE_W = 3` in [down/sketch.py](down/sketch.py); `CHUTE_W = 2` re-emits the 2-wide down.bbc byte
for byte). Item 3, the autopilot, is not this work. The new start is
[chute3/down-start-cga.png](chute3/down-start-cga.png) (the tool's CGA preview) and
[chute3/down-start-2v3.png](chute3/down-start-2v3.png) (the sketch, 2-wide against 3-wide). The study below is kept as it was written.*

The owner, designing course 3 (DOWN, [DOWN.md](DOWN.md)): the line from the start ramp through the
corner chute into the 3-wide hump run should be 3 wide all the way, and `chute 2 round` is only 2 wide.
*"Why are shapes limited to 2 wide? ... lets set an agent on what 3-wide chutes would cost and defer
that change for now."* This is that price. The contract it would change is SPEC.md 137.28 (137.28.3's
grammar, 137.28.4's shapes). Figures are **MEASURED** with the tool at this tree unless marked
**PREDICTED**. The prototype is in `tools/bbcourse.py` on this branch only, behind `chute 3`. DOWN is
unchanged.

## The answer in five lines

- **Guest: 0 bytes, 0 clk.** Nothing in the guest knows a chute's width. `bz_fhp`/`bz_fh4` read
  whatever table a cell names, through its symmetry. 3-wide is TOOL work: the prototype is 23 lines.
- **Tables: 10 per standard profile and depth**, against the 2-wide's 5 and the 1-wide's 3, out of a
  course's 32. That is 2,890 bytes of section `F` in RAM.
- **Steepness is not the problem.** The slope bound scales with the width, so 3-wide accepts DEEPER
  chutes: 15 px `round`, 13 px `bank`, against the 2-wide's 10 and 8.
- **The occluder cap is the real limit, as it was for 2-wide.** On DOWN's corner, 8 px gives at most 3
  records a block and 10 px gives 4, which is the bound. 12 px is refused (5 records a block).
- **DOWN with it** (ramp widened too): +1,078 bytes LZB a course part. 927 of those are `F`, because
  the 3-wide tables are not in the kit. In the kit they would cost +2,890 bytes of RAM, held for the
  session, instead.

**Recommendation:** cheap enough to take whenever DOWN wants it. Use the standard depth of
**8 px `round`** (10 px at most on DOWN). Finishing it is about half a day of SPEC and selfcheck work
(section 5). The one open behaviour is the autopilot's exit from a 3-wide taper (section 4).

## 1. Why 1 and 2

Width is a parameter almost everywhere. The profile (`fprofile`) takes the half width `W = 8 x wide`.
The tables are found generically (`build_fields`). The SEAM rule, the lift, the picture, the occluder
cut and the guest are cell-by-cell. Only `chute_cells` has a branch per width, and it had two because
the two widths differ in **where the crease runs**:

| | crease runs | `way` names | across a leg | corner block | radial centre, `R0` | end taper |
|---|---|---|---|---|---|---|
| 1-wide | through cell CENTRES | a cell | 1 cell | the way's cell | the cell's inner corner, 8 | the way's cell |
| 2-wide | along a cell EDGE | a cell corner | a pair | 2 x 2 round the point | the block's inner corner, 16 | the pair after the point |
| **3-wide** (prototype) | through cell CENTRES | a cell | 3 cells | **3 x 3 round the way's cell** | the block's inner corner, **24** | **the way's row of 3** |

An odd width is the 1-wide's geometry scaled up, and an even width is the 2-wide's. The one new rule
is the **leg length**. A 3-wide corner block reaches one cell into each of its legs, as a 2-wide's
does, but a 3-wide end taper is the way's own row, as a 1-wide's is. So the straight cells in a leg
`n` cells long are `n - 1 - (corners at its ends)`:

- end to end needs `n >= 1`;
- end to corner needs `n >= 2`;
- corner to corner needs `n >= 3`.

The prototype refuses a shorter leg with the existing message, naming the minimum.

## 2. What it needs

| | needed | in the prototype |
|---|---|---|
| grammar | `chute <1|2|3> ...`; ways are cells, as for 1-wide | yes (the parse and its error text) |
| tool code | the 3-wide arm in `chute_cells`: cross cells, straights' run origin, taper row, 3 x 3 radial corner | **yes, 23 lines** (`git diff` on `tools/bbcourse.py`) |
| tables | 10 for each (profile, depth): straight 2, taper 2, corner 6. Each sloped leg adds 2 per distinct rate | generated, MEASURED below |
| section `F`, the 32 bound | 2,890 bytes RAM a standard profile. A course holds three 3-wide profiles (30), or e.g. round + bank + one slope rate (SHP3: 22) | unchanged bound |
| guest code | **none**. No guest source mentions a chute or a width. The shape's 5 bits and the symmetry already address any of 32 tables | 0 bytes |
| `PHYS_REV`, format, `read_part` | unchanged: a 3-wide cell is an ordinary FIELD cell | - |
| records/occluders | the cut is per facet; a wider corner adds facets over taller ground at the same depth | MEASURED on DOWN3 below |
| the kit (137.37) | its F library takes every table a `KIT_POOL` course holds. When DOWN (or any pool course) uses 3-wide, its tables join | not re-cut |

**Tables, MEASURED** (`build_fields` over all 8 corner orientations together; one L-shaped chute alone
gives the same counts):

| | straight | taper | corner | total |
|---|---|---|---|---|
| 1-wide | 1 | 1 | 1 | **3** |
| 2-wide | 1 | 1 | 3 | **5** |
| 3-wide | 2 (centre, side) | 2 | 6 (3 on the diagonal + 3 mirrored pairs of 9 cells) | **10** |

**The steepness bound, MEASURED** (the deepest depth every corner orientation accepts, rounding
included; the refusal is always the inner corner's 45-degree point, slopes (-4, -4)):

| | `round` | `bank` |
|---|---|---|
| 1-wide | 5 px | 4 px |
| 2-wide | 10 px | 8 px |
| 3-wide | **15 px** | **13 px** |

The cross slope is `D / (0.75 W)` for `round`, so at equal depth a 3-wide chute is gentler. At 8 px it
is 1.78 quarter px a ground unit, against 2.67 for the 2-wide. The model says it still guides (section 4).

## 3. What it costs

**The guest, resident: 0 bytes.** **A frame and a step: 0 clk.** These hold by construction: no guest
byte changes. Shipped courses are untouched: SHAPE (1- and 2-wide chutes) compiles `cmp`-equal
(`BZ0.BIN`) with the prototype and without it.

**DOWN with a 3-wide line** ([chute3/down3.bbc](chute3/down3.bbc)). This is a study copy: ramp R widened to
3 (its rails out a cell), its flat foot cell dropped (the end taper is the foot), and
`chute 3 round depth 8 way 8 14 30 way 8 16 30 way 11 16 29` in place of the 2-wide. MEASURED with
`bbcourse.py --sizes`:

| | DOWN (2-wide) | DOWN3 (3-wide) | |
|---|---|---|---|
| picture part RAM | 49,562 | 49,678 | +116 |
| world part RAM | 14,980 | 16,420 | +1,440 (`F` 6 -> 11 tables) |
| blocks | 566 | 587 | +21 (the wider ramp and chute) |
| records / masks | 1,039 / 205 | 1,065 / 187 | +26 / -18 |
| most records in a block | 3 | 3 | bound 4 |
| `F` LZB | 23 (5 of 6 tables KITREF) | 950 (0 of 11: not in the kit) | +927 |
| `B` LZB | 3,353 | 3,479 | +126 |
| whole part LZB / LZ4 | 10,635 / 12,877 | 11,713 / 14,304 | **+1,078** / +1,427 |
| against the 12,550 budget (reported, never refused) | LZ4 over by 327 | LZ4 over by 1,754; LZB under | |
| decode, PREDICTED | 601 ms | 606 ms | +5 ms |
| route (the autopilot) | 1,204 steps | 1,233 steps | reaches the goal |

**Depth on DOWN's corner** (the occluder cap, 137.11.4.2), MEASURED:

| depth | 8 | 10 | 12 | 15 |
|---|---|---|---|---|
| most records in a block | 3 | **4** (at the bound) | **REFUSED, 5** (block row 33, col 16) | 4 (6 before the merge) |

The 15 px case passes only because the merge happens to land there. Treat **10 px as DOWN's ceiling**
and 8 px as the safe standard, as 8 px was for the 2-wide on two courses.

**The kit, PREDICTED.** Once a pool course uses 3-wide `round` 8 px, the kit gains 10 tables:
+2,890 bytes of RAM, held for the session (`BZKIT.BIN` 15,446 -> 18,336), and about +900 LZB once on the
disk. Each course using the profile then pays about 25 bytes of `F`, not 950. The kit already holds 22
tables.

**Effort.** The tool arm is done. The rest is in section 5: about half a day. Most of the work is SPEC
text and selfcheck items. No guest work, no emulator rows.

**Risks:**

1. **The occluder cap.** It binds before the slope bound does, exactly as for 2-wide. A deep 3-wide
   corner over a tall drop (DOWN's) is refused past 10 px.
2. **The 32-table bound.** One 3-wide profile is 10 tables. A course mixing a 3-wide `round`, a
   3-wide `bank`, sloped legs and pits can reach 32. The tool refuses at compile, naming the cell.
3. **The autopilot** (section 4). The route through a 3-wide round chute stalls at its exit taper on
   SHP3. It does not stall on DOWN3, where the ball comes off the ramp fast.
4. **The kit's held RAM** (+2.9KB a standard 3-wide profile), if the owner adds one to the kit.

## 4. The model (`bbcourse.Physics`), MEASURED

The probe is in the session's scratchpad, not in the tree: a rubber ball enters along the crease, 8
units before the corner block, turning +y to +x. The 2-wide's figures come from the same probe:

| chute | the turn held (+x arrows from the block on), entry 150 - 384 | coasting, no key |
|---|---|---|
| 2-wide `round` 10, 8; `bank` 8 | TURNS at every speed | comes round and stops by drag in the outgoing leg's start |
| 3-wide `round` 8, 10, 12, 15 | **TURNS at every speed** | the same; none leaves over the lip |
| 3-wide `bank` 8, 10, 13 | **TURNS at every speed** | the same |

- **Rest.** A ball dropped beside a 3-wide crease with a cross speed of 160 or 300 settles to rest
  within 7 units of the crease, every speed 0, with no dither (400 steps; `round` 8, 10, 15; `bank` 8).
- **The exit taper** behaves identically to the 2-wide's at 10 px. The taper's slope is `D / 16`
  whatever the width. With the arrows held a ball leaves at entry speed 120 or more and rolls back
  under 120. Coasting, it rolls back.
- **The autopilot on SHP3** (137.28.10's FIELD ways) stalls in the first `round` chute's exit taper,
  cell (16, 10): it arrives slow out of the bigger corner. Moving the route's ways did not fix it.
  This needs tuning before a 3-wide chute ends at a taper on a route. DOWN3's route crosses its exit
  taper with the ramp's speed, and it reaches the goal.

## 5. To finish it (when the owner takes it)

1. **SPEC.md 137.28.3 / 137.28.4.** The grammar becomes `<1|2|3>`. Add the 3-wide row of section 1's
   table, the leg-length rule, the deepest depths (15 / 13 px), the standard depths (8 px `round`,
   matching the occluder cap) and the 10 tables.
2. **`--selfcheck` (the `split` section's FIELD items):**
   - the three short-leg refusals;
   - a 3-wide leg in `_FCHUTE`, or a CHUTE3 course;
   - FIELD runs: the corner turned at 250 with the arrows held, and the ball at rest with no dither;
   - the deepest-depth ring (15 accepted everywhere, 16 refused somewhere).

   The SEAM rule, the slope bound and `read_part` already run on every cell. Red arms: the corner's
   `R0` set to 16, and a taper on the wrong row. Each must break a run or the SEAM rule.
3. **The autopilot** at a 3-wide exit taper (section 4).
4. **DOWN itself.** `docs/plans/bonanza-courses/down/sketch.py` generates `down.bbc`, so the 3-wide
   line goes in the sketch: ramp R and its rails, no flat foot cell, `chute 3 round depth 8 ...`.
   [chute3/down3.bbc](chute3/down3.bbc) is the target text. Then re-cut the kit if DOWN joins
   `KIT_POOL`.
5. **The rows** are the final pass's, not this study's: `bonanzacourse` (the selfcheck),
   `bonanza_dfield`.

## The prototype's pictures

- [chute3/down-2v3.png](chute3/down-2v3.png): DOWN's corner as built (left, 2-wide) against DOWN3
  (right, 3-wide `round` 8 px). The 3-wide corner block turns straight into the hump run's 3 rows.
- [chute3/shp3.png](chute3/shp3.png): [chute3/shape3.bbc](chute3/shape3.bbc), the scratch course.
  It has a 3-wide `round` 10 px chute (two corners the same way), a 3-wide `bank` 8 px chute with a
  leg climbing 1.5 units to a raised corner, and a `round` S whose corners turn both ways. The two
  `round` chutes share 10 tables between them; the `bank` chute's slope legs make it 12. 22 of 32
  tables, at most 2 records a block.

Both are CGA previews from `bbcourse.py --png`.
