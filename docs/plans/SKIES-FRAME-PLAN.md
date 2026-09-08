# CLEAR SKIES — where the frame goes, and the candidates that are left

**Status: OPEN. §3 is the one to build; §2 is priced and parked; §4 is the
queue behind them.** SPEC.md §88 is the contract, SPEC.md §88.12 is what the
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

## 3. OPEN — the cull walk: 29–60% of faces are gathered, projected and thrown away

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

### 3.1 What to try, in the order they should be tried

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
