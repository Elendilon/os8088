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

## 7. OPEN, AND THE BIGGEST THING HERE — the rolled horizon, and the ADI

`tests/skiesprof.py` (SPEC.md 88.12.1) flies five profiles instead of pinning
one, and every stage is bracketed at its call site so the accounting adds to
99.9% of the loop. Two findings dwarf everything else in this file.

### 7.1 A banked turn is 1.7x a level one, and it is the SKY that does it

| Hercules 8088, 24 flown frames | level | 45 deg held |
|---|---|---|
| frame | 164.5 ms | **282.8** |
| `cs_skyground` | 8.76 | **47.77** (5.5x) |
| `cs_blit` | 9.01 | **36.13** (4.0x) |
| the two together | 17.8 ms, 10.8% | **75.9 ms, 26.8%** |

SPEC.md 88.3.1 predicts it in its own words — *"a row whose kind changed, and
every split row, is refilled and marked whole"* — and a rolled horizon makes
every row a split row. So the sky/ground pass refills the whole view and the
blit then has the whole view to carry.

**Nothing has ever been tried here**, and it is worth more banked than every
item in §2, §3 and §6 put together. What to look at, in order:

1. **A split row's refill is a full-width `rep stosw` pair either side of the
   crossing.** It is already the cheap shape (88.4.1). What is dear is that
   there are 112 of them where level flight has a handful.
2. **The blit carries what the refill marked.** If a rolled row's ink is
   unchanged from last frame's — and for most rows of a steady bank it IS,
   the horizon having moved a pixel or two — then the mark is honest and the
   COPY is not. A per-row comparison against the shadow before marking is one
   `repe cmpsw` a row; that is the first thing to price.
3. **The horizon moves by a bounded amount between frames.** A bank changes
   the crossing x by a few pixels a row a frame. Refilling only the band the
   crossing actually swept, rather than every split row whole, is the same
   argument 88.3.1 already makes for last frame's span - applied to the
   horizon instead of to objects.

**Measure it against `turnhold`**, which lives in the rolled state, and check
it against `bank`, which passes through it.

### 7.2 The ADI is 41 ms a frame for as long as the attitude is moving

The released bank decays 45 deg to 0 over 24 frames and the panel goes with it:
**44.7 ms a frame while the roll is moving, 2.4 ms once it settles** - a cliff
in one frame at frame 10 of the trace. 88.9's items redraw when the value they
show changes, and in a turn the attitude indicator changes every frame.

**14% of a banked frame is one instrument.** The held bank is CHEAPER in the
panel than the released one (5.02 against 20.61) for exactly this reason,
which is also the proof that it is the ADI and not the panel in general.

Nothing here is a defect - it is redrawing because it changed. What is worth
pricing is HOW it redraws: 88.9.2's attitude indicator against 11.96's
save-under, or a band composer (5.9) for the one item on the page that is
never static in flight.

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
