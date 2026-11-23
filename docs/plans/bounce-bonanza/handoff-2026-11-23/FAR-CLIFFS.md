# Handoff: AV's far list ("far cliffs") - research done, build next

Written 2026-11-23 at the end of a builder session on `bb-editor` (merged into `bounce-bonanza`). This is a
working note (docs/plans/), not the contract: **SPEC.md 130.29.12** holds the measurements and is the authority;
the paragraph to start from is *"A precomputed far list, and the cheap float, MEASURED in the model"*.

## The owner's ask

> "The issue with the forward cliffs is the '4 layers in front of it'. In this case, those blocks don't have 4
> layers (or any layers other than themselves that matter; a max of 2 for the one wall if they somehow jump
> behind it). Is that something we could make a very simple, coarse mask for and build ahead of time? Would
> that save AV calculation time in general? ... this would need to be a very simple dataset to be a win."

AV (130.29) hides a ball in a VOID cell using the whole front cells at diagonal depth `d = 1..4`. MILL's tall
cliffs 5 - 18 diagonals in front still cover a falling ball, so the tool ships records for them: the largest
class AV leaves (130.29.12's table, "past the depth").

## What was found (MEASURED in the model unless marked)

- **Ceiling**: the residual cut at depth 18 instead of 4 saves at most **2,785 bytes LZB** over the eight
  `BZ_COURSES` (records 10,415 -> 9,226). MILL is the biggest share (-882); depth 12 already gets -848.
- **Forms tried**: a skyline per grid row x word column (MILL 10,624 bytes raw - 12x the ceiling, PREDICTED,
  not taken); a "nothing past 4" flag (nothing to skip: AV reads nothing past 4); a cover threshold to skip the
  walk (only 0.4% of MILL's positions are wholly hidden - no general speed-up). **Not a speed-up in any form.**
- **The far list pays**: for each VOID cell, the few whole front cells 5 - 18 deep that hide a residual pixel.
  MILL: 102 of 540 VOID cells need one, at most 4 entries.

| course | records | masks | parts LZB | dataset LZB | net |
|---|---|---|---|---|---|
| FIRST | 68 -> 58 | 30 -> 26 | -105 | +16 | -89 |
| DOWN | 2,058 -> 1,877 | 198 -> 187 | -393 | +185 | -208 |
| MILL | 1,808 -> 1,455 | 223 -> 187 | -868 | +328 | -540 |
| MOON | 912 -> 827 | 60 -> 55 | -184 | +142 | -42 |
| PEAK | 1,237 -> 1,086 | 60 -> 58 | -297 | +233 | -64 |
| PLAY | 2,427 -> 2,296 | 221 -> 229 | -214 | +171 | -43 |
| ROLL | 1,064 -> 985 | 139 -> 133 | -246 | +117 | -129 |
| HOP | 841 -> 684 | 109 -> 103 | -353 | +107 | -246 |
| **total** | **10,415 -> 9,268** | **1,040 -> 978** | **-2,660** | **+1,299** | **-1,361** |

Guest code PREDICTED about 280 - 300 bytes, so `BONANZA.O88` about **-1.1 KB net**. (The course figures were
taken on the tree of 2026-11-23 evening; the owner's MILL has moved since - re-measure before quoting.)

- **Clocks (PREDICTED, instruction-level, not run)**: entering a cell with no list +0.1k; with a list +1.36k an
  entry plus 0.78k + 0.11k a footprint column per counting half; frames staying in a cell unchanged. MILL's
  route demo mean 1.6k -> 1.7k; HOP's 1.7k -> 2.0k mean, worst 11.7k -> 17.4k (under the course's worst).
- **The cheap float (idea B) is NOT worth building**: it adds bytes even before guest code (DOWN +80, PLAY +79
  LZB, masks up) and slows the worst entering frame (PLAY 17.8k -> 26.1k; MILL's glass islands up to +16.3k).
  The fuller float model was built and rejected earlier: `docs/plans/retired/bonanza-av-float-slab.patch`.

## The two filters the build must keep

1. **Worst frame**: each list is trimmed until no height of its cell costs more than the course's current worst
   entering frame (trimmed 1 entry on MILL, 6 PEAK, 3 MOON, 32 PLAY).
2. **Wrong-hide**: unfiltered, MILL's wrong-hide rose 0.0018% -> 0.19% (under the 0.25% bound) with ONE
   position hiding a whole ball - a ball fallen below the ground plane behind a far cliff. Refusing candidates
   that would hide a visible pixel (15 on MILL, none elsewhere) restores today's figure exactly on MILL, PEAK,
   DOWN and HOP.

## Where the data would live (to AUDIT before building)

Each listed VOID cell's grid byte +1 (its slopes byte, 0 on every VOID cell today) indexes a lists blob of at
most 255 bytes in the world part. In the physics routines read (`bz_blocks`, `bz_tslope`, the floor function)
that byte is read only after a kind check, so a VOID cell never reaches it - **but this needs a full audit of
every reader of the grid's +1 byte** (guest and tool: `read_part`, the grid cross-checks, the builder's grid
readers) before relying on it, and the tool's grid reader must accept a non-zero value there.

## Build plan (the research agent's, checked)

1. SPEC first: a 130.29.13 (or a new row in 130.29.4) for the far list - the pick, both filters, the byte, the
   blob, the guest's walk.
2. Port the pick and both filters from `far-cliffs/avfar.py` (the variant `far 18 0 budget nowrong`) into the
   tool's residual cut; store the list in byte +1 and the blob.
3. Guest: the far cells go into the existing extra slots `bz_arange` and the count loop already walk (almost no
   new bss).
4. Completeness (item 15, 130.29.7) stays as it is; add red arms for **a dropped list entry** (completeness
   red) and **the wrong-hide filter off** (wrong-hide red on MILL).
5. Re-price on the BUILT guest with `tests/bonanza_av.py --price` before trusting the worst-frame budget.
6. Shipped course parts change (fewer records); re-stamp any `.bzd` `ident` the identity moves (compile and take
   `c.ident`, as `moon.bzd`/`summit.bzd` were).
7. Soak rows to name: `bonanzacourse`, `bonanzaphys`, `bonanzaphyshost`, `bonanzaperf` (AV fall legs),
   `bonanzareplay`, plus `bbedit`/`bbplay`.

## Files in this directory

- `far-cliffs/` - the research: `avfar.py` (the model patch; `far 18 0 budget nowrong` is the variant to build,
  `float cell|col` is idea B), `avdata.py` (the dataset as stored, packed LZB), `avproxy.py` / `avrun.py` (the
  clock proxy and its replay over route demos), `avcover.py` (the cover-threshold measurement), `avwrong.py`
  (wrong-hide with the far lists), `price.py` + `sk_far.asm` + `sk_half.asm` (instruction-level pricing).
- `tools/` - session scratch tools, kept because they were useful; **they carry scratch-pad paths from the
  session that wrote them - edit the paths before running**:
  - `legs.py`, `whole.py`, `human.py` - test every leg of a route (from rest and chained), the whole-route
    planners, and a human key sequence for a timed Hop (MILL's see-saw);
  - `route_stuck.py` - where the plain autopilot stalls on each route (now in the builder as Autopilot, 130.58.50);
  - `why.py`, `count.py` - colour a course's shipped records by who needs them (floor / reachable void /
    doubtful), the picture behind 130.11.4.7;
  - `render_notrap.py` - render a course's preview PNGs with NO TRAP off, as the builder compiles.
- `courses/` - the owner's in-progress MILL before the route fix and with it (`mill-routefix.bbc`: 4 `way`
  edits, both routes finish), for the leg tools.

## State of the branch at handoff

`bb-editor` and `bounce-bonanza` hold the same tree. Two agents were still working when this was written: the
see-saw not tipping in the game (MILL; the builder's model tips it) and a self-check memory follow-up (the other
session's camcheck fix found the OOM's cause; the follow-up names a killed child's section). Their results land
on `bb-editor` and are merged on.
