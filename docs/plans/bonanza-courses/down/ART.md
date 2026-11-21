# DOWNHILL DECISION: art options (signs and interest decals)

**THE OWNER PICKED the sign `wall` and the decal `boost` (2026-11-21)** - not `fork`/`balls` (a ball could roll
over them and art occlusion was never built), not `flags` (they need it too), not lift, sink, stairs or crack.
`art.py apply` draws them off the course as `sketch.py` wrote it into `apps/bonanza/courses/down_sign.bba` and
`down_boost.bba`; `sketch.py`'s `ART` pins their anchors and emits the ART block on every re-emit. What follows
is the study as it was written.

**OPEN (rev 17): the picks collide at the hub.** STRUCT.md's D cuts the hub's free front-left corner (course
cell (46, 20), a `hole half left`), and that cell's +y face is the first of the three "GLASS >" is painted on.
The face that is left (cells 47 - 48, 32 px) is narrower than the word and its arrow (43 px), so the sign as
drawn reads "ASS >": the art is clipped to its host cells, as it must be. Neither pick was dropped; the owner
chooses - the hub's chamfer goes (L's four stay), or "GLASS >" moves (the bridge's landing, the hub's face east
of the bridge), or the word loses its arrow and shrinks.

*Status: OPTIONS for the owner to pick from (2026-11-21). Nothing here is in
`apps/bonanza/courses/down.bbc`: the lead adds the chosen pieces once picked
(`art.py --signs S --extras E,... --out DIR` writes the `art` lines and the
`.bba` files). Every figure below is MEASURED by compiling the real course
with that one option added (`art.py sheet`), not predicted.*

The generator is [art.py](art.py), the artwork's SOURCE: deterministic, host
only, nothing in `make` runs it. It draws with FIRST ROLL's machinery
(`first/decals.py`: the owner buffer, the projection, the one-pixel black
line) as LITTLE HOP's `hop/art.py` does, but every piece is DOWN's own. DOWN
is the tutorial's REWARD and its idea is the SPLIT, so the signs name the two
balls and the decals mark where a ball meets its material. The palette is 1
(cyan, magenta, white on black). Every piece carries its shape in black and
white so it reads on the Hercules, where cyan and magenta are greys.

- Sheets: [art-signs.png](art-signs.png) and [art-decals.png](art-decals.png).
  Each row shows the course without the option (CGA), with it (CGA) and with
  it (Hercules), x4 (the flags x2).
- `art.py preview DIR` is the quick look used while drawing. It lays the
  pixels over a picture and compiles nothing.

## What a piece costs

DOWN is SHEETED (SPEC.md 130.30.12): its picture part is **2 sheets of 89
block rows** (rows 0 - 88 and 55 - 143), each **53,150 bytes** in RAM, 11,874
under 65,024. Measured here, **every sheet carries the whole block table**, so
an option costs **16 bytes for each new block in EACH sheet, wherever it
stands**. Every delta below is exactly 16 x its new blocks. No option moved
the sheet plan (still 2 x 89 from rows 0 and 55), and none touched the world
part. "LZB" is the change in the packed size of both sheets on disk, added
together.

| option | where | blocks | picture part (each sheet) | LZB on disk (both sheets) |
|---|---|---:|---:|---:|
| **SIGNS** (pick one) | | | | |
| `fork` | a signpost on the hub's east rail block (52, 16), beside the steel exit. Two arrow boards: STEEL (higher) points right, toward the steel corridor; GLASS (lower) points left, toward the membrane | +34 | **+544** | +670 |
| `balls` | the same signpost, but the boards carry a PICTURE of each ball in place of the word: steel (white, a black sheen band, a magenta shade) and glass (cyan, a white glint and facets) | +30 | **+480** | +652 |
| `wall` | the words PAINTED ON THE WALLS where each leg leaves the hub, sheared with the face, white with a black keyline: "STEEL >" on the corridor's north rail over the spikes, "GLASS >" on the hub's south face beside the membrane bridge | +24 | **+384** | +560 |
| **INTEREST DECALS** (any of) | | | | |
| `stairs` | HAZARD STRIPES, white and black, along the edge of the glass stairs' 3-unit drop (the straight way's top step, its +x edge): warning paint at the decision | +15 | **+240** | +209 |
| `crack` | a STAR OF CRACKS painted on the step under that drop, showing what the fall does to glass. It can go with `stairs` or replace it | +13 | **+208** | +237 |
| `boost` | a SPEED ARROW (two bars and a head, cyan) on the far bank, from the boost pad to the gap's edge, pointing the way the boost throws | +8 | **+128** | +134 |
| `sink` | "SINK!" painted on steel's landing in front of the 6-deep water column, white on a magenta panel | +49 | **+784** | +726 |
| `lift` | an UP ARROW and LIFT painted on the face beside the lift (H's +x face, the west wall of the run south), sheared with the face | +12 | **+192** | +262 |
| `flags` | the FINISHES: a CHEQUERED FLAG on a pole at two corners of each goal. These are the race's own finish flags in black and white, not HOP's bunting | +44 | **+704** | +744 |
| **a suggested set** | `fork` + `stairs` + `sink` + `lift` + `flags` | +154 | **+2,464** (55,614: 9,410 under) | +2,630 |

The set costs exactly the sum of its parts (544 + 240 + 784 + 192 + 704 =
2,464), because no two pieces share a block.

## Notes for choosing

- **Cheapest:** `boost` (128), `lift` (192), `crack` (208) and `stairs`
  (240), each a few blocks. **Dearest:** `sink` (784) and `flags` (704). Each
  of those covers many blocks: SINK!'s panel is 4 tiles of floor, and the
  flags stand at four places.
- **Signs:** `fork` reads best on both cards. `wall` is the cheapest, but its
  sheared letters step. `balls` uses no words, but a 13-pixel ball is small
  and the steel one can read as a clock face.
- **What does not read well, honestly:** `boost` is small. Its tile is a
  single row between the pad and the edge, so the squash leaves it as a short
  cyan notch. LIFT's sheared proportional letters step on the dither face.
  `sink` is legible on the CGA but faint on the Hercules (white on a grey
  panel).
- **Depth:** every piece takes the occlusion of the surface beneath it
  (SPEC.md 130.23.2). The signpost and the flags stand up from a block or a
  floor. Their upper pixels are therefore painted over the floor or void
  behind them, and a ball passing behind draws over them, as with HOP's
  banner and pennants. The floor and face paint has no such case.
- **Rejected while drawing** (not on the sheets): STEEL and GLASS painted as
  floor arrows on the hub (the 6-wide hub leaves letters too small to read
  through the floor's 2:1 squash); white sparkles over the void round the
  finishes (too faint, and most fell on scenery); an arrow from SINK! into
  the column (the guard rails in front of it chopped it up).

## Reproducing

    python3 docs/plans/bonanza-courses/down/art.py sheet docs/plans/bonanza-courses/down/art 3

This compiles the base and every option (about 4 CPU-minutes each, 3 at a
time) into `down/art/<variant>/`, which is scratch and not committed. It
writes `costs.txt`, `signs.png` and `decals.png` there; the two sheets here
are copies of those.
