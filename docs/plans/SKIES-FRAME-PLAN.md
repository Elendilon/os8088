# CLEAR SKIES — where the frame goes, and the candidates that are left

**Status: OPEN, and §7 is now the head of it.** §3 IS BUILT (SPEC.md 88.5.12)
— up to 5.64 ms, 2.38% of a frame; §2 is priced and parked; §4 is the queue,
§6 the wireframe question answered and closed, and **§7 is what an IN-FLIGHT
profile found that no pinned frame could — a banked turn costs 1.7× a level
one and the objects are barely any of it.** SPEC.md §88 is the contract, SPEC.md §88.12 is what the
frame costs and how it got there, and this file is only the *forward* list —
candidates with a measured ceiling apiece, in the order the evidence ranks
them.

It exists because SPEC.md §88.12's closing paragraph — *"the per-primitive
floors are the frame, and the remaining levers are content"* — is true and is
not the end of the argument. **A frame here is 170–255 ms and a tick is 54.9,
so the levers left are worth 1–3 ms each and there are several of them.**
Nothing in this file is worth 10%; two or three of them together are worth a
frame in ten.

## 0. The instrument, and the rule that makes its numbers mean anything

`make skiesprobe` + `python3 tests/skiescount.py --scene <s>` (SPEC.md
§88.11.1). **Every term is priced by ADDING it, never by removing it**, so
every arm draws the identical picture.

That rule is not fastidiousness, it is the difference between two answers.
`tests/skiesperf.py` prices a stage by NOPing its call, and **a NOPed call
takes its consequences with it**: NOP `cs_edge` and the chains keep their
+big/−big, so the polygon's rows are never filled and the reading is the
tracing PLUS the fill it removed. On `city` that is **17.50 ms by removing
and 8.47 by adding** — the first number is twice the truth, and a candidate
sized against it is a candidate sized against pixels it was never going to
save.

Both instruments are wanted. `skiesperf` answers *what does this stage cost*;
`skiescount` answers *how much of it is redundant, and what would replacing it
cost*.

### 0.1 A PIXEL A/B OF THIS PROGRAM IS NOT REPRODUCIBLE — and the control says so

Anyone changing a cull or a winding here will reach for the obvious gate: the
same pinned scene, old build against new, framebuffers compared byte for byte.
**It does not work, and it fails in the way that wastes the most time** — a
single scene of twelve differs, by a few hundred pixels in a band along the
horizon, and WHICH scene it is moves from run to run.

Four things were tried and none of them fixed it: capturing at a `cs_render`
breakpoint rather than after host frames; counting GUEST frames since the pin;
pinning the flight state the position does not (`cs_spd`, `cs_hs`, `cs_vs`,
`cs_ht`, `cs_thr`, `cs_thrust`, `cs_thracc`, `cs_rrate`, `cs_prate` — the
simulation advances by TICKS, not frames); and re-pinning all of it before
every frame, at the breakpoint, so the poke lands on the same instruction in
both arms.

**The control is what ends the argument**: two arms that are byte-identical in
behaviour AND in speed — `[cs_axoff]` = 1 on both sides of the same image —
differ in **2 runs of 6, by 865 and 896 pixels**, in the same band. So the
noise floor of this comparison is about 900 pixels and it is not the change.

Run it anyway — **it is what found the SI clobber in §3** that the verdict
audit could not see — but do not certify with it. **Certify with a verdict
audit**: the new test's answer against the old one, face by face, on the guest,
counted (SPEC.md 88.11.1's `cs_axoff` arm). That is deterministic, and it is
what says 0 disagreements over 12 scene-and-fill configurations.

### 0.2 …and an A/B that can silently measure NOTHING needs an arm check

`cs_axmask` was added to bisect which family of faces caused a difference.
Package bss is ZEROED, so it defaulted to 0, and `and dl, [cs_axmask]` then
cleared every axis bit: **the cull was inert in BOTH arms** and six scenes read
a tidy +0.06%. The timing looked perfectly reasonable. What caught it was
printing, beside the milliseconds, the COUNTERS OF WHAT EACH ARM ACTUALLY DID
— faces walked, faces the winding culled, faces the axis test culled — and
seeing `axis-culled 0` on both sides. Every A/B here prints that line now.

## 1. The scene decides the answer, and §88.12's three are the wrong ones

`runway`, `city` and `tower` are the frames SPEC.md §88.12 is measured on and
they are right for that. They are **wrong for any question about building
faces**: the skyline in them is far enough to be LOD-boxed (SPEC.md §88.5.4),
so it contributes no faces at all, and the polygons that actually cover the
view are the one-face FLAT models — ground, river, runway, roads — which have
no shared edges and no back faces.

`dflevel`, `dfangled` and `dfsquare` stand among La Défense's six
`cs_m_tower2` — 60 m square, 110 m tall — at ~950 m, so all three share a
projected size and an LOD rung and differ only in where the eye is. **Four
times the tracing of the pinned three**, and the discriminator is the PITCH:

* eye ABOVE the roofs → a box shows two walls AND a roof: three faces meeting
  at **three shared edges of twelve traced**, measured at 23.2% and 25.0%.
* eye BELOW them → two walls: **one shared edge of eight**, measured 11.1%.

That is the textbook arithmetic landing on the glass, and it is why a
candidate about faces must be measured on a scene that has some.

**Add a `df*` scene to any face-or-edge measurement in this file. Quote the
pinned three beside it, never instead of it.**

## 2. PRICED AND PARKED — dedup the shared edge (SPEC.md §88.4.2.1)

`cs_poly` traces all four edges of every front face, so an edge between two
front faces is scan-converted twice. `cs_wire` already refuses that for the
outline; the fill does not.

**Refused at runtime, on all six scenes**: the test (`cs_edgemark` on the
face's own indices, 295–501 cycles) is paid on 20–68 edges to save on 1–17,
and the net is **−1.12 to −2.73 ms**. With the topology precomputed per model
— a flag beside each face index, ~60 cycles — the ceiling is **+1.56% of a
frame** on `dfangled` and under +0.35% on four of the six.

Parked rather than closed, because the ceiling is real and the cost is
bounded: a topology byte per face-edge over 122 models, in a package that has
already met `APP_MAX_SIZE` at a merge (SPEC.md §88.5.9). **If §3 is built
first the two do not add**, and §3 is worth more for less — the faces §3
removes are the ones §2 would have shared edges with.

The finding worth keeping either way: **in WIREFRAME a duplicate edge is
duplicate PIXELS, and in a FILL it is duplicate BOOKKEEPING.** Two front faces
fill two different interiors, and `cs_polyrows_herc` lays a row as two masked
end bytes and a `rep stosw` between, into the shadow; only the span table is
refilled. The shape of a redundancy says nothing about its price.

## 3. BUILT — the cull walk: 29–60% of faces were gathered, projected and thrown away

`cs_faces` decides a face is back-facing from the **signed area of its
PROJECTED points** (SPEC.md §88.5.10). Correct, and exact since the quad
became its diagonals' cross — but it is decided *after* the face's vertices
have been gathered by index into `cs_pv` and the two `imul`s taken. A face
that is culled has paid all of that for nothing.

**Measured** (`cs_dupface`, which repeats the gather and the cross into
scratch, so the arm draws the identical picture):

| | runway | city | tower | dflevel | dfangled | dfsquare |
|---|---|---|---|---|---|---|
| faces walked | 9.0 | 15.8 | 14.6 | 28.1 | 28.1 | 28.1 |
| back-culled | 3.4 (38%) | 4.5 (29%) | 5.6 (38%) | **16.9 (60%)** | 11.2 (40%) | 11.2 (40%) |
| a face's preamble | — | 1,326 cy | — | 1,402 | 1,380 | 1,376 |
| **the culled ones cost** | — | **1.25 ms (0.70%)** | — | **4.96 ms (2.14%)** | **3.25 ms (1.27%)** | **3.24 ms (1.30%)** |

**`dflevel` is the case to design against and it is the ordinary one** — level
flight among buildings, where a box shows two of its five faces and three are
culled. It is also where §2 is worth least (0.35%) and this is worth most
(2.14%): the two candidates are complements, not alternatives.

The measured figure is a **lower bound** — the arm repeats the gather and the
cross and not `.cnt`, the near/side vertex count that runs in front of them.

**BUILT as `cs_axcull` (SPEC.md 88.5.12), 143 bytes**, and it took most of the
ceiling: **−5.64 ms (−2.38%) on `dflevel`**, −3.71 on `dfangled`, −3.68 on
`dfsquare`, −1.02 on `runway`, −0.64 on `city`, −0.65 on `tower`. On `dflevel`
350 walked faces become 140 and the winding is left with nothing to cull.

**It needed no per-model data and no multiply**, which was the finding that
made it worth building: a stack's side face is an axis-aligned plane in WORLD
space when its level pair is untapered, so *"the eye is behind it"* is one
compare against the eye's own world position — and `cs_scale` already has that
offset, it being the input to the rotation. `dot(M x̂, M d) = d.x` for an
orthonormal M, so the camera-space dot product a normal test would take is the
number that was there before the rotation.

### 3.1 What was tried, and what is left

**Taken: option 1**, in the form below. **Options 2 and 3 are still open and
are what would widen it** — the axis test refuses a tapered level pair, a face
with no axis flag and every `CSF_NOCULL` face, and those refusals fall through
to the winding at full price.

1. **A STACK's side faces are two of four, and the signs say which.** A box's
   four side normals in camera space are ±M₀ and ±M₂ — **columns of the matrix
   `cs_matrix` already built this frame** — so at most two of the four can face
   the eye, and which two is the sign of two dot products with the object's
   camera-space origin. Computed once per OBJECT (not per face), that skips
   two of five faces before either is gathered. The top face is a third sign
   against M₁. `CS_SIDES`/`CS_TOP` (SPEC.md §88.6) emit the faces in a fixed
   order, so the mapping from signs to face indices is a table and not a
   search.
2. **…and if that is too coupled to the model macros**, the cheaper half
   alone: gather **two vertices before four**. The diagonals' cross needs
   v0..v3, but a *sign* test on the two diagonals can be attempted from the
   projected `cs_sxv`/`cs_syv` by index without copying anything into `cs_pv`
   — the copy is what the `.cp` loop is for, and a culled face never needs it.
   This is a pure win with no per-model data at all, and it is the one to
   measure first.
3. **Order the walk so a cull is cheap to repeat.** Every consumer already has
   `cs_pinside`/`cs_pwhole` (SPEC.md §88.5.7); a per-object *facing* byte set
   once would join them.

**Do not touch the winding TEST itself.** SPEC.md §88.5.10 is a bug fix with
photographs behind it: the whole polygon's area, not one triangle. Anything
here must produce the same verdict on the same face — the gate is
`tests/skiesgeom.py --clobber-fan`, and `tests/skies.py`'s full-redraw diff is
what catches a face wrongly dropped.

**What would make it not worth doing**: if the per-object sign work costs more
than 1,326 cycles × the faces it removes. On `dflevel` that is 16.9 faces, so
the budget is generous; on `runway` it is 3.4 and the budget is ~4,700 cycles
for the whole object pass. Measure both.

## 7. THE BIGGEST THING HERE — the rolled horizon, and the ADI: BOTH BUILT

`tests/skiesprof.py` (SPEC.md 88.12.1) flies five profiles instead of pinning
one, and every stage is bracketed at its call site so the accounting adds to
99.9% of the loop. Two findings dwarfed everything else in this file, and both
have been taken: the horizon's span pass (7.1, SPEC.md 88.3.1.1) and the ADI's
erase table (7.2, SPEC.md 88.9.2.5). **What each of them LEFT is where the
next reading goes** — 7.1.3 and 7.2's own tail — and in both cases the answer
turned out to be the same shape: what is left is fixed cost a row rather than
pixels.

### 7.1 BUILT — a banked turn is 1.7x a level one, and it is the SKY that does it

| Hercules 8088, 20 flown frames | level | 45 deg held |
|---|---|---|
| frame | 164.5 ms | **280.1** |
| `cs_skyground` | 8.76 | **47.75** (5.5x) |
| `cs_blit` | 9.01 | **36.17** (4.0x) |
| the two together | 17.8 ms, 10.8% | **83.9 ms, 30%** |

SPEC.md 88.3.1 predicted it in its own words - *"a row whose kind changed, and
every split row, is refilled and marked whole"* - and a rolled horizon makes
every row a split row. So the sky/ground pass refills the whole view and the
blit then has the whole view to carry.

**COUNTED, with `CSHZPROBE`** (`make skieshzprobe`; SPEC.md 88.3.1.1), 20
flown frames a profile, Hercules, the view 400x112 and so 50 bytes wide:

| | split rows a frame | carried today | the crossing's band | crossing did not move a BYTE |
|---|---|---|---|---|
| `turnhold` 45 deg held | **112 (every row)** | 5,600 B | **336 (6.0%)** | **112 of 112 - 100%** |
| `rollsweep` 2 deg/frame | 109.1 | 5,455 | 441 (8.1%) | 64.5 (59%) |
| `bank` decaying | 29.1 | 1,452 | 123 (8.5%) | 12.6 (43%) |
| `cruise` level | 1.0 | 50 | 3 (6.0%) | 1 (100%) |

**The first reading of that table was wrong in its biggest cell and looked
right**: `cs_dbg_hzby` is a word, 112 x 50 x 20 is 112,000, and `turnhold`
reported **2,323** - one wrap divided by the frames. Rows x `[cs_wbn]` is what
caught it.

#### 7.1.1 What was built: the SPAN, in a pass of its own

A split row still LAYS the whole view; its **span** is the crossing's own byte
and one either side. The span says what CHANGED, and `cs_blit` carries the
union of this frame's set and last frame's - which holds last frame's band and
whatever an object drew - so nothing is left on the glass. A row that was not
split last frame gets `cs_fullspan`; Mode X is refused outright, `cs_r_begin`
setting every kind to 3 there so that a kind of 3 tells you nothing.

| | frame | `cs_skyground` | `cs_blit` |
|---|---|---|---|
| `turnhold`, before | 280.1 | 47.75 | 36.17 |
| ...decided INLINE in the fill loop | 280.2 | 55.88 | 28.31 |
| ...**decided in a pass of its own** | **276.0** | 51.70 | 28.37 |
| `bank`, before | 256.0 | 34.60 | 33.39 |
| ...**decided in a pass of its own** | **254.3** | 36.88 | 29.04 |
| `cruise`, before | 164.3 | 8.77 | 9.95 |
| ...decided in a pass of its own | 164.5 | 9.27 | 8.83 |

Level flight is untouched - the band there is ONE row - and `cruise`'s 164.5
against 164.3 is inside its own 4% spread.

**+125 bytes**, `tests/skieshz.py` is the gate, and `[cs_hzfull]` is the
runtime A/B (the profiler takes `--hzfull 1`).

**The lesson is the two middle rows.** Inline in the loop that was already
walking those rows, the identical arithmetic cost **533 cycles a row** and the
whole change measured **nothing**: 280.2 against 280.1. In a walk of its own,
constants hoisted into registers and the rows stepped with `lodsw`/`stosw`, it
is **~168**. Nothing was removed from the decision. What fell is the number of
BYTES of code a row runs through, which on an 8088 is the price.

#### 7.1.2 REFUSED - narrowing the fill's range

The obvious companion is to lay only `union(last frame's span, this frame's
band)`. It was built and measured, `cs_hzproc` bracketed at all 112 of its
calls a frame:

| `cs_hzrow_sh`, `turnhold` | ms a frame | cycles a row |
|---|---|---|
| the whole view - 50 bytes | 33.76 | 1,437 |
| the union - typically 4 to 10 | 29.92 | 1,273 |

**A tenth of the pixels is 11% of the time.** ~1,100 cycles of a split row's
fill is fixed - the row offset, the crossing byte, the mask lookup, two
`cs_fillrun` calls - and the 50 bytes it lays are ~350. Computing the union
costs about what it saves, and it wants `cs_hzb0`/`cs_hzbn` threaded through
all three row fillers.

#### 7.1.3 BUILT - the fill's fixed cost, measured and then cut

`cs_hzproc` bracketed at all 112 of its calls a frame, and its two
`cs_fillrun` calls inside that:

| `cs_hzrow_sh`, `turnhold` | ms a frame | cycles a row |
|---|---|---|
| the two `cs_fillrun` calls - 49 bytes of pixels | 15.60 | 664 |
| **its own body, everything else** | **17.76** | **756** |
| the whole call | 33.37 | 1,421 |

`rep stosw` over 49 bytes is ~350 cycles, so **1,070 of 1,421 is overhead**,
and all of it is work the caller had already done or the frame had already
decided. Three cuts (SPEC.md 88.3.1.2), **+8 bytes**:

1. **DI is passed and WALKS the row.** The band loop holds the row's first
   view byte and steps it by the stride; the routine rebuilt it from
   `cs_rowoff` and `cs_tbase`, reloaded ES, then bracketed the left run in
   `push di`/`pop di` to get back to it. Now the left run leaves DI on the
   crossing's byte, the blend is a `stosb`, the right run carries on.
2. **The two runs are INLINE** (`FILLRUN`). Each was a `call` into a routine
   that re-did `cld`, the odd-address test and the halving - 314 cycles a row
   between them. `cs_fillrun` survives for `cs_hzrow_modex`.
3. **The pixel mask is the FRAME's.** Which of `cs_hlm`/`cs_clm`, and whether
   the index masks to 7 or 3, is the adapter's answer; it was re-decided every
   row. `[cs_hzmt]`/`[cs_hzmm]` now, set beside the ink patterns - and the
   `push cx`/`pop cx` round the shift goes with it.

| Hercules 8088, 20 flown frames | frame | `cs_skyground` | `cs_blit` |
|---|---|---|---|
| `turnhold`, before 7.1 | 280.1 | 47.75 | 36.17 |
| ...with the span pass | 276.0 | 51.70 | 28.37 |
| ...**and the fill diet** | **267.3** | **42.74** | 28.31 |
| `bank`, before 7.1 | 256.0 | 34.60 | 33.39 |
| ...**and the fill diet** | **248.7** | **31.81** | 28.89 |
| `cruise`, before 7.1 | 164.3 | 8.77 | 9.95 |
| ...**and the fill diet** | 164.5 | 9.28 | 8.83 |

**280.1 -> 267.3 ms in a held bank, 3.57 -> 3.74 fps, for 133 bytes.**

#### 7.1.4 BUILT - and the row stops being a CALL at all

7.1.3 took the filler's half and left the seam: 1,042 cycles a row inside it
and **601 more in the band loop around it** - three push/pop pairs, the ink
pair fetched as two bytes through two pointers, the sentinel test and a
call/ret. The band is ONE loop with no call in it now, on the shadow
backends: the ink PAIR is a word in `cs_hzpat4` built once a frame, the walk
of `cs_xl` is `lodsw` against a hoisted `[cs_hzend]`, and the row's three runs
write straight through DI. Mode X keeps the per-row call; `cs_hzrow_sh` and
`[cs_hzproc]` are DELETED, so it is **+89 bytes**.

| Hercules 8088, 20 flown frames | frame | `cs_skyground` | `cs_blit` |
|---|---|---|---|
| `turnhold`, before 7.1 | 280.1 | 47.75 | 36.17 |
| ...span pass | 276.0 | 51.70 | 28.37 |
| ...fill diet | 267.3 | 42.74 | 28.31 |
| ...**fused** | **263.1** (3.80 fps) | **38.41** | 28.44 |
| `bank`, **all three** | **246.1** (4.06 fps) | 29.18 | 29.21 |

**280.1 -> 263.1 ms in a held bank for 222 bytes.**

**IT BOUGHT A QUARTER OF WHAT THE BYTE COUNT SAID.** Predicted ~936 cycles
against 1,643 (16.6 ms) by the method that made 7.1's span pass a 3x win;
measured ~1,460, so 4.3 ms. The span pass's body is ~33 bytes of register
work; a fill row is ~135 bytes with twenty memory operands and two `rep stosw`
runs whose 25 words are ~600 cycles - **41% of the row on their own**. Count
bytes where the body is registers; treat it as an upper bound where the body
is memory.

#### 7.1.5 REFUSED - the "pre-pay the horizon" table, and the cache behind it

The idea was to pre-generate the sky/ground picture for a constrained set of
attitudes and make `cs_skyground` a memory copy. **The premise is right and
better than it looks**: `cs_matrix`'s second column is `(-sr.cp, cr.cp, sp)`,
so the horizon is a function of `(roll, pitch)` ALONE - no heading, no
position, no framerate.

It is refused on two counts, and the first needs no look judgement. **A copy
is 4 bytes over the bus per byte laid where a fill is 2** (`rep movsw` reads
and writes; `rep stosw` only writes), so a pre-made picture is ~1.8x the cost
of the fill it replaces on an 8088 - and its only advantage, no per-row
decision, is what 7.1.3 and 7.1.4 buy for 97 bytes. Second, it does not fit:
one pixel at the view edge is 0.29 degrees of roll and one row is 0.20 of
pitch, so ~1,257 x 112 = 140,784 states - 788 MB of pictures, 31.5 MB of
`cs_xl` arrays, 1.1 MB of line endpoints. At a fixed roll pitch is a pure
vertical shift, so a strip per roll would do; a strip is 224 rows x 50 bytes =
11.2 KB, so even 32 roll steps is 358 KB on a machine with 50.5 KB of free
heap. (Quantisation is NOT the argument: at 3.6 fps a decaying bank already
steps ~2 degrees between displayed frames.)

**The cache behind it is refused on a measurement, and a SECOND profile was
built to attack the measurement.** "Has the horizon moved" is an exact
five-word compare once a frame, and in a held bank it has not moved at all.
`turnhold` is busy on purpose, so `sparse` was added - the same held bank over
an empty corner of Paris, the Issy aerodrome's three outbuildings (12, 10 and
15 m) and two of the Seine's western ribbons, nothing tall and no sky object:

| held 45 degree bank, 20 frames | `turnhold` | `sparse` (EMPTY) |
|---|---|---|
| frame | 263.1 ms (3.80 fps) | **77.6 ms (12.88 fps)** |
| `cs_scene` | 176.07 | 6.50 |
| `cs_skyground` | 38.41 (14.6%) | **38.64 - 49.8%** |
| `cs_blit` | 28.44 | 15.09 |
| band rows object-free | 0 of 112 | **112 of 112** |
| mean span width | 31 of 50 bytes | **3.0** |
| horizon identical to last frame | 20 of 20 | **19 of 20** |

**With nothing to draw the horizon IS the frame**, and every row is skippable
- the case the cache wanted. On a still frame 77.6 -> ~43 ms, 12.9 -> ~23 fps,
on nineteen frames in twenty. In `turnhold` and `bank` it is worth nothing.

**That 19 was 7 until the instrument was fixed.** The held-bank profiles
pinned the roll at the FRAME's start and let the model run, so what cs_matrix
saw was 45 degrees less whatever 88.7.5's easing rolled out over that frame's
ticks - and at 77.6 ms a frame takes one tick or two. The raw attitude took
exactly two values 146 units apart, one tick of roll-out, and the horizon
alternated between two positions three rows apart. It was the PIN wobbling,
not the aeroplane. Held profiles pin at the matrix now.

**THE AERODROME WAS TRIED FIRST AND IS THE WRONG SCENE.** Three short
buildings and two of the Seine's ribbons reads as sparse and measures as busy:
0 of 112 rows object-free and spans WIDER than turnhold's, 33.1 against 31,
with FEWER objects and an empty sky. `cs_markrows` marks an object's BOX
(88.3.2) and a flat ground model kilometres across whose ink is a thin
diagonal has a box the size of the view. A per-row interval represents a
diagonal horizon perfectly; ONE RECTANGLE PER OBJECT CANNOT REPRESENT A
DIAGONAL AT ALL.

#### 7.1.6 What is left, in the order the evidence ranks it

1. ~~The narrow fill~~ - **BUILT AND REFUSED, 7.1.8 below.**
2. **The horizon cache**, now that 7.1.5's `sparse` prices it properly: an
   empty turn's 77.6 ms -> ~43 on nineteen frames in twenty, and NOTHING in a
   busy one, for ~100 bytes and a second path through the band whose
   correctness rests on the key covering every input to the picture.
4. **`cs_blit`'s own per-row walk**, ~300 cycles over rows that are mostly a
   few bytes now.

Two instrument traps, both of which cost a run:

1. **A breakpoint takes a FLAT address** and the listing gives an offset in
   the package. Arm one without the load segment and nothing hits - and the
   wait then sits out its whole limit looking like a slow GUEST.
2. **`cs_hzy0`/`cs_hzy1` are not the band.** They are where the line meets the
   view's left and right edges: at 45 degrees in a 400-wide view that is rows
   -61..174 of a 112-row view, so a host-side walk that trusts them reads 236
   rows and a negative `y0` reads in FRONT of the span array.

### 7.2 BUILT — the ADI is 41 ms a frame for as long as the attitude is moving

The released bank decays 45 deg to 0 over 24 frames and the panel goes with it:
**44.7 ms a frame while the roll is moving, 2.4 ms once it settles** - a cliff
in one frame at frame 10 of the trace. 88.9's items redraw when the value they
show changes, and in a turn the attitude indicator changes every frame.

**14% of a banked frame is one instrument.** The held bank is CHEAPER in the
panel than the released one (5.02 against 20.61) for exactly this reason,
which is also the proof that it is the ADI and not the panel in general.

Nothing here is a defect - it is redrawing because it changed. What was worth
pricing is HOW it redraws, and the answer was not the line at all: **90% of
the ADI is the ERASE**, a filled ellipse whose half-width is a SQUARE ROOT A
ROW, taken again on every redraw for a radius that cannot change in flight.

**F6 now cycles four modes** (SPEC.md 88.9.2.5) and this is what they cost, on
`skiesprof`'s `rollsweep`:

| | `cs_panel` mean | worst frame | the erase per redraw |
|---|---|---|---|
| `Full` | 22.43 ms | 44.88 | **30.8 ms** |
| `Fast` | 15.84 | 33.41 | **14.6 ms** |
| `Small` | 9.06 | 20.99 | **7.5 ms** |
| `Off` | 4.28 | 8.31 | 0 |

`Fast` is the table and is **pixel-identical** - 0 differing of 5,040 over the
instrument's box. `Small` is `Fast` plus a half-radius glass in the same
bezel. `Off` is a performance option and the quickest way to price the
instrument from the glass.

**What is left is `cs_prect`, one call a row.** Going further means laying
those rows without its per-row loop and `cs_markspan`, or composing the
instrument into a band and blitting it once (5.9's shape). Neither is done,
and the second is what the screen saver already does for a whole cube.

### 7.3 ...and three smaller things the same run turned up

* **`cs_step` is 6.2% of a level frame** - three calls, one per tick. Every
  measurement in 88.12 charges it nothing, the world being paused there.
* **`cs_fclip` is 10.91 ms in the CLIMB** against 4.39 level, 7.1% of that
  frame: on the runway the strip crosses both side planes at its near end,
  which is 88.5.7's own worst case, measured in flight for the first time.
* **`cs_consider` never drops below 6.5%** - 47 objects considered every
  frame to draw 7 to 17, 9.9 to 19.0 ms. 88.5.2's skip ticks already cut it;
  what is left is the largest stage after the drawing.

## 4. The queue behind it, with what is known about each

* **The erase under a solid.** `cs_skyground` refills a row and the faces then
  write over the part they cover, so those pixels are written twice. The
  refill is already span-limited to last frame's span for the row (SPEC.md
  §88.3.1), so this is smaller than it looks — but `skyground` is 7.5% of the
  `city` frame and nobody has measured how much of it a solid immediately
  covers. **Count it before designing anything**: the arm is a counter in
  `cs_polyrows_herc` for bytes written over a row the sky pass refilled this
  frame.
* **The outline over a filled solid.** A solid above `CS_EDGEPX` draws its
  faces AND its edges (SPEC.md §88.4.7), so a shared edge's pixels are laid by
  two fills and then a `cs_seg`. `seg (in edges)` is 7.4% of the `city` frame.
  This is a LOOK question and not a free win — the outline is what makes a
  wall read as a wall at size — so what is wanted first is a screenshot pair,
  not a measurement.
* **The two `rep stosw` inits in `cs_poly`.** The chains are stored
  unconditionally by `.left`/`.right`, so the +big/−big init is only load-
  bearing for horizontal edges' `.both` and for rows no edge covers. ~28
  cycles a row per face. Small, cheap to try, and needs a proof that a convex
  polygon clamped to the view leaves no row uncovered.
* **`.cnt` when `cs_pinside` is set.** SPEC.md §88.5.7 skips the per-vertex
  side test for a whole object; the per-face `.cnt` loop in `cs_faces` still
  runs. Worth a counter before anything else.

## 6. CLOSED — the wireframe's per-pixel write (SPEC.md 88.4.3.1)

Asked because §88.13.3's dedup was worth 16.7 ms and a 1bpp pixel is a
read-modify-write of the byte around it: *is the shadow buffer's alignment
costing us, and is the bigger win still out there for wire mode?*

**No.** One `or [es:di], al` is **14.2–14.5 cycles**, every plot in a wire
frame comes to **0.9–1.5% of it**, and the plots a byte accumulator could merge
are **0.08–0.21%**. Three reasons, all measured:

* **78% of the pixels are steep or vertical**, where consecutive pixels are 80
  bytes apart and nothing can merge. A wireframe tower is made of steep lines.
* **Above six pixels a row the slice already lays whole runs** (§85.3.6) —
  23.6 segments of 47.3 take it — so the only mergeable arm is a shallow line
  under six a row.
* **The write is 14 cycles of a steep pixel's ~85.** The rest is the DDA and
  the `loop`. Nothing is 8-alignment: a polygon row's middle is `rep stosw` on
  whatever alignment, the 8088's bus being eight bits wide (§88.4.6).

**What §88.13.3's dedup actually removed was whole SEGMENTS**, not their
pixels: ~2,400 cycles of clip, mark, DDA setup and dispatch each, 47.3 of them
a frame. And its 167.5-against-184.2 figure is **Mode X**, where a pixel is an
`out` and a store rather than 14 cycles — so the pixel share there is much
larger than it is on the shadow backends.

**Where a wire frame's time actually goes is the per-segment floor**, and that
is the open question this leaves: 47.3 segments a frame at ~2,400 cycles is
~24 ms of a 172 ms frame. Nobody has priced the parts of that floor.

## 5. Ruled out, so nobody re-derives them

* **A whole-object scanline pass** — one span table for the silhouette, spans
  merged per row and emitted left to right. It collapses the per-face bounding
  box, the table init and the per-row address computation, and it costs a
  per-row span merge on an 8088. The prize it is competing for is the poly
  floor, and §2's numbers say the whole edge subsystem is 10.8% of the frame
  in its best scene: a merge that costs anything per row cannot come out
  ahead. Not measured; refused on the arithmetic.
* **Sharing the DDA rows between two faces without a topology table.** That is
  §2, and it is measured: −0.69% to −1.28%.

#### 7.1.8 REFUSED, MEASURED - the row laying the UNION and not the view

The last candidate: lay `union(last frame's span, this frame's band)` instead
of the whole view. Correct - the union is every byte that can differ from the
glass, and outside it the row already holds the pattern this frame would lay -
and `tests/skieshz.py` passes unchanged. **+109 bytes, and a regression
wherever there is anything to draw:**

| 20 flown frames | fused | + the narrow fill |
|---|---|---|
| `turnhold` | **263.1** | 270.1 (**+7.0**) |
| `bank` | **246.1** | 248.6 (**+2.5**) |
| `sparse` - the EMPTY turn | 77.6 | **71.3** (-6.3, 12.9 -> 14.0 fps) |

**A proportional saving against a fixed cost.** The union costs ~340 cycles a
row to obtain - three indexed reads, four compares, and u0/u1/the mask in
memory temporaries because the fused loop has no register left - and laying a
byte fewer saves ~10. It pays when the union is under 16 bytes of the 50:
sparse's is 3, turnhold's is 31. Halving the block would move break-even only
to 30, so it is not a code-quality problem.

**It is 7.1.7's wall from the other side.** The narrow fill fails because the
mean span is 31 and not 12; the span is 31 because a mark is an object's BOX;
tightening the box costs more than the blit it saves. Reverted,
byte-identical.

#### 7.1.9 Where this leaves the horizon

Three changes KEPT (7.1, 7.1.3, 7.1.4) and three REFUSED with numbers (7.1.5's
table and cache, 7.1.7's marks, 7.1.8's fill). **Everything that paid removed
per-row FIXED cost; nothing that tried to draw LESS paid at all**, because the
blit carries a byte for ~4.5 cycles and every scheme for carrying fewer costs
more than that to decide.

What is left, in the order the evidence ranks it:

1. ~~`cs_blit`'s own per-row walk~~ - **MEASURED AND PART-TAKEN, 7.1.10.**
2. **The horizon cache - PARKED, not refused.** Worth an empty turn's 77.6 ms
   -> ~43 on nineteen frames in twenty. The owner's reading is that it helps
   HALF-empty scenes too, not only the extreme, and that the question is
   whether it costs a busy scene anything - which it need not: the "has the
   horizon moved" test is one five-word compare a FRAME, so a still frame can
   branch to a second band loop and a moving one runs the loop it runs today,
   unchanged. Pick it up with that shape, and measure `turnhold` for a
   regression rather than assuming there is none.
3. **`cs_scene` itself**, which is 176 of turnhold's 263 ms and has had no
   attention in this round at all.

#### 7.1.10 BUILT - cs_blit's row is 490 cycles, and one of them was a segment

Breakpointing the row loop's own top and taking the delta between hits gives
the row whole, copy and all - 856 of them over `turnhold`:

| a `cs_blit` row, Hercules | cycles |
|---|---|
| **empty** - nothing in either set | **~129** |
| narrowest working row (p10) | ~518 |
| median working row | 904 |
| widest | 1,850 |

So the fixed part is **~490 a row** and a word to Hercules VRAM is **40-49** -
confirmed independently by solving the two unknowns from two scenes. That
splits turnhold's 28.4 ms blit into **12.9 walking, 14.8 copying, 0.6 empty**.
**The empty rows are not the target**: the range is rows 0..157, not the
screen's 348, so only 29.7 of 155.7 rows are walked for nothing.

**What came out of the 490 was a segment register.** The row swapped DS to the
shadow and back every iteration - 43 clocks for a value that cannot change
inside a frame. A package runs CS = DS, so DS holds the shadow for the whole
walk now and the three package-data reads take a `cs:` override. **+4 bytes,
cs_blit 28.36 -> 27.2 ms.**

#### 7.1.11 THE CONTROL MUST BE SAME-SESSION - and this is how that was found

The -1.1 ms above is quoted against a control built from the committed source
and run beside the change, because measured an hour apart **the identical
build reads 263.1 ms and then 266.6** on the same profile - 1.3%. Host-side
breakpoint overhead changes how many 18.2 Hz ticks land inside a frame, the
aeroplane flies a slightly different path, and `cs_scene` follows it: 176.07
then 177.67 for code that did not change. A change INSIDE cs_blit therefore
appeared to make cs_scene 1.8 ms slower.

`tests/skiesprof.py` is exact WITHIN a run - the brackets are cycle counts and
a stopped guest burns none - and the drift is entirely in which frames get
flown. Build the control from the tree you are comparing against, run it
beside the change, and treat any cross-session delta under ~2 ms on a 260 ms
frame as unmeasured.
