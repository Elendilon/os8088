# BONANZA: what a shared "standard kit" part would cost and save (2026-11-17)

*A dated measurement of one tree: `3ba74532a`, branch `bounce-bonanza`. It
prices the owner's idea of a SHARED KIT: standard picture blocks, occluder
masks, FIELD shape tables (SPEC.md 130.28.2) and other reusable art held once
instead of once a course. The owner's bar: it is worth doing if it saves
about 3x what it costs (2x might do), counting the ~20 release courses. The
goal is the game on ONE 360KB disk (130.15.8, 130.27.5). The work was done on
the host only. No guest, course, tool or SPEC.md byte changed, and no
emulator ran. The scripts are in the session's scratch directory, `kit/`:
`dump.py`, `kitlib.py`, `attrib.py`, `kit.py`, `kitmap.py`, `recs.py`,
`align.py` and `alignkit.py`.*

**How the figures are marked:**
- **MEASURED**: the shipped tool's own compile (`bbcourse.compile_course`,
  its stored forms), packed by an exact copy of `os88lz.lzb_compress`'s
  shortest-path parse. The copy accepts a preset dictionary and charges each
  symbol's bits to the section its output lands in. With no dictionary it
  reproduces `os88pkg`'s LZB size for every part to within 6 bytes (FIRST
  1,868 = 1,868; PLAYGROUND 12,713 against 12,707).
- **PRICED**: from 8088 instruction timings for routines that were sketched
  but not written.
- **PREDICTED**: an extrapolation, with its model stated.

LZB is the format the parts ship in (130.15.9). "The study set" is the eight
courses FIRST, TRIAL, MILL, MOON, PEAK (`summit.bbc`), PLAYGROUND and the
`BZSHAPES` knob's SHAPE and PITS. Together they pack to **52,365 bytes of LZB**
(MEASURED). BENCH, the pathway and the title are left out: the first is the
benchmark, and the other two are different art.

## 0. Numbers first

| | MEASURED / PRICED |
|---|---|
| Where a course's packed bytes go, over the study set | blocks `B` **35.8%**, map `M` 18.8%, records `R` 16.0%, FIELD tables `F` 8.1% (24 - 27% of a course that uses shapes), cells `C` 7.9%, props `P` 4.3%, masks `K` 4.2%, the rest 5% |
| **A small kit**: pieces in at least 3 courses (177 blocks, 61 masks), 3,808 bytes raw | **1,341 bytes of LZB** on the disk |
| What it saves today's 8 courses (explicit pieces, below) | **4,508 bytes: 3.4x** its packed size (with the LZ dictionary on top, 5,718 bytes: 4.3x) |
| A course NOT used to build the kit (leave-one-out: the honest figure for a NEW course) | **-530 bytes a course** (explicit + dictionary), -8% |
| **A pairwise kit**: pieces in at least 2 courses (569 blocks, 144 masks, 10 tables), 14,298 raw | **5,264 bytes of LZB** |
| What it saves today's 8 courses | 10,654 bytes explicit (2.0x), 13,347 with the dictionary (2.5x) |
| What it saves a new course (leave-one-out) | -540 bytes explicit, **-750 explicit + dictionary**, -11% |
| The ceiling: a course built ONLY from kit pieces | **-41%** over the study set (-33% to -54% a course): what is left is the map, records, cells, props and header |
| The FIELD library (every distinct table of the 3 shape courses, 36 tables) | 10,404 raw, **3,055 LZB**. Each shape course carries 1,370 - 1,490 bytes of tables today |
| **The frame, the owner's variant (kit held, pieces COPIED into the course part at load)** | **0 clk**: the RAM form has exactly today's layout |
| The assembly at load, 4.77 MHz | PRICED: **about 15 - 30 ms** a course (bitmap walk plus `rep movsw`) |
| Load time with the kit held | PRICED **0.1 - 0.2 s shorter** than today: fewer sectors to read and fewer bytes to decode |
| Load time when the kit is not held (fetched and dropped at each launch) | PRICED **+0.15 s** (small kit) to **+0.5 s** (pairwise kit) |
| Guest code | PRICED **about 150 - 200 bytes** of package image (one new section form plus the kit's hold/drop), about 4 bytes of bss. **0 kernel bytes** |
| RAM held for the kit | its raw size: **3.8KB** (small) to 14.3KB (pairwise), more with the F library |
| Referencing the kit IN PLACE from its own segment (no copy) | PRICED **+40 - 55% on the row/column/box writers' word**, or a 4-byte map. Refused: the owner's own constraint ("must not hurt frame performance") |
| Fixing the picture alignment (Y0 mod 8) for the kit | **0 records and 0 bytes on today's courses**: all 8 already ship at Y0 = 4 (mod 8), and all 5 tested also compile at 0 (mod 8) |
| A kit at all 8 alignments | **3.2x** the blocks' packed size of one alignment (1,509 against 340 blocks; 7,381 against 2,339 LZB) |
| Relocatable occlusion records | at most **575 bytes a course** (records on kit blocks, pairwise kit); realistically a third to a half of that. **Not worth doing in the first round** (section 3) |

**The answer.** Build the owner's variant: a **held kit** (claimed when there
is room, fetched on demand when there is not), with a course referencing kit
pieces by a **bitmap**. At load the pieces are **copied** into the course's
own part, so frames run exactly today's code. Start with the small kit (the
pieces 3+ courses share) plus the FIELD library, at the alignment today's
courses already use. That passes the 3x bar on today's courses as they stand,
3.4x MEASURED, and a new course built to use the kit clears it at least as
well (section 5). The LZ dictionary on top is worth only about 200 bytes a
course for a parts-standard change. It is a later option, not the design.

**But read section 6's first line before scheduling it.** At today's course
density the 20 courses fit the disk WITHOUT a kit. The kit is insurance
against the courses growing, not a rescue.

## 1. The disk variants

### 1.1 What was built

The study builds the kit out of today's courses. A piece goes in the kit when
it appears in at least `MIN` courses of the POOL. The pieces are 16-byte CGA
block encodings (`B`), 16-byte masks (`K`) and 289-byte FIELD tables (`F`).
Two pools are used:
- **all**: the pool is the whole study set. This measures how much today's
  courses already share.
- **leave-one-out (LOO)**: the pool is the other seven courses. This
  predicts the saving on a course the kit was not cut from.

Each course is then packed five ways (`kit.py`):

| variant | the stored form | how the kit is used |
|---|---|---|
| base | as shipped | - |
| dict | as shipped | the kit as an LZ PREFIX (preset dictionary) |
| dict+reorder | blocks renumbered so the course's kit blocks come first, in KIT order; masks likewise (each record's mask index remapped and WDIFF'd again) | prefix |
| **explicit** | renumbered; the kit pieces CUT OUT of `B`, `K` and `F`, and a bitmap a piece added (which kit pieces this course uses) | none: the loader copies the pieces in |
| explicit+dict | as explicit | prefix, for what is left |

The control "renumbered with no kit" costs 0 to +150 bytes a course (MILL
+141, because the map's index bytes compress a little worse). Every figure
below includes it.

### 1.2 Today's sharing (pool = all), LZB bytes

| course | base | small kit (MIN 3): explicit | + dict | pairwise kit (MIN 2): explicit | + dict | everything a kit (MIN 1): explicit |
|---|---|---|---|---|---|---|
| FIRST | 1,868 | 1,392 | 1,258 | 1,290 | 1,166 | 906 |
| TRIAL | 3,427 | 2,854 | 2,683 | 2,483 | 2,244 | 1,636 |
| MILL | 6,890 | 6,241 | 6,043 | 5,238 | 4,951 | 3,167 |
| MOON | 7,587 | 7,033 | 6,853 | 6,497 | 6,186 | 4,965 |
| PEAK | 8,984 | 8,433 | 8,260 | 7,394 | 7,175 | 5,972 |
| PLAYGROUND (2 parts) | 12,707 | 11,992 | 11,817 | 9,943 | 9,661 | 6,955 |
| SHAPE | 5,140 | 4,663 | 4,558 | 4,260 | 3,617 | 3,495 |
| PITS | 5,762 | 5,249 | 5,175 | 4,606 | 4,018 | 3,852 |
| **the 8** | **52,365** | **47,857 (-4,508)** | **46,647 (-5,718)** | **41,711 (-10,654)** | **39,018 (-13,347)** | **30,948 (-41%)** |
| the kit's own LZB | | 1,341 | 1,341 | 5,264 | 5,264 | 14,866 |
| **ratio, saved : kit** | | **3.4x** | **4.3x** | 2.0x | 2.5x | (degenerate) |

### 1.3 A course the kit was not cut from (pool = the other seven), LZB bytes

| course | base | MIN 3: explicit + dict | MIN 2: explicit | MIN 2: explicit + dict | MIN 1 (the other 7's every piece): explicit + dict |
|---|---|---|---|---|---|
| FIRST | 1,868 | 1,347 | 1,433 | 1,281 | 1,200 |
| TRIAL | 3,427 | 2,878 | 2,887 | 2,615 | 2,291 |
| MILL | 6,890 | 6,252 | 6,266 | 6,004 | 4,940 |
| MOON | 7,587 | 7,007 | 7,052 | 6,786 | 6,154 |
| PEAK | 8,984 | 8,449 | 8,454 | 8,193 | 7,093 |
| PLAYGROUND | 12,707 | 12,077 | 12,019 | 11,812 | 9,602 |
| SHAPE | 5,140 | 4,734 | 4,686 | 4,535 | 3,617 |
| PITS | 5,762 | 5,359 | 5,271 | 5,150 | 4,508 |
| **the 8** | **52,365** | **48,103 (-4,262, -530 a course)** | **48,068 (-4,297)** | **46,376 (-5,989, -750 a course)** | **39,405 (-12,960, -1,620 a course)** |
| that kit's LZB (it varies with the course left out) | | 1.08 - 1.26K | 3.0 - 5.2K | 3.0 - 5.2K | 12.5 - 14.7K |

Two facts are hidden in that table:
- **The kit's FIELD tables never match out of sample.** At MIN 2, LOO shares
  0 tables. In-sample, PLAYGROUND shares 10 of its 15 with SHAPE and PITS,
  because its shaped section was built from theirs. A table is a pure
  function of (width, profile, depth, corner, taper), so the same chute
  gives the same table. The courses simply have not repeated profiles yet. A
  kit that fixes the standard profiles (section 5) would make them match by
  design. The library of all 36 is 3,055 bytes of LZB.
- **Most of the saving is blocks.** Masks are 4% of a course, and 77 - 92%
  of a course's records already point at a mask that is in the pairwise kit
  (`recs.py`). That is the "masks are shareable by content" half of question
  2, and the explicit variant above already takes it.

### 1.4 The dictionary variant: what the decoder needs

- **No kernel CODE change.** `lz_match` (`kernel/lz.inc`) refuses a match
  only when `offset > DI` (`cmp ax, di / jbe .inrange`). The fast paths in
  `KHP_LZ` make the same test. A dictionary placed at `ES:0` with the output
  starting at `ES:DI = kit length` is therefore reachable as it stands.
- **But the CONTRACT changes.** `OSAPI_DECOMP` documents `DI = 0` ("every
  caller hands over a claim's base"). A prefix is an amendment to SPEC.md
  20.13: an ABI clarification, `abilock` without a bump. It is also a change
  to the parts standard: `op_fetch` would have to claim `kit + len`, copy the
  kit to the front, read the stream to the top and decode at `DI = kit`, or
  BONANZA would need a fetch of its own.
- **The dictionary must sit BELOW the output in the same linear run.** The
  held kit's own claim cannot serve, because nothing makes two claims
  adjacent. So the kit is copied in front: about **12.5 clk a byte**
  (`rep movsw` on the 8088's byte bus), 14.3KB in about 37 ms. After the
  decode, either the course is copied down over it (40KB in about 0.1 s,
  then a shrinking regrow, which always succeeds in place, 50.3.1), or the
  kit's bytes stay dead in the claim for the whole play. The PEAK transient
  is then course + kit.
- **Offsets** reach at most 64KB back. A kit plus a PLAYGROUND picture part
  is about 64KB. A large kit therefore needs the course's `B` section near
  the front of the part, or the kit split by part (blocks and masks before
  the picture part, tables before the world part).
- **What it buys over explicit references**: 1,692 bytes over the 8
  courses LOO (MIN 2), **about 210 bytes a course**. It catches blocks that
  are near-copies of kit blocks (shared lines) and the bitmap's own bits.

**Verdict**: explicit referenced pieces carry about 75% of what the
dictionary does with nothing new in the decoder, the parts standard or the
claim layout. The dictionary is a later +3%.

### 1.5 Kit-global numbering and map runs (`kitmap.py`)

Holding the WHOLE kit at block indices 1 - NK in every course makes a map
run of standard blocks the same bytes in every course. A dictionary of the
other courses' remapped maps was then tried, as an upper bound for a library
of common map runs. It bought **45 - 110 bytes a course**. The whole kit in
RAM also costs 74 - 94 extra blocks (1.2 - 1.5KB) a course. **Not worth it**:
the map's bytes are layout, not art.

## 2. Relocatable occlusion (question 2)

**What remains.** Under AV (130.29) the VOID-cell records are computed, and
the shipped records are the residual plus every non-VOID position. Over the
study set they are 6,028 records, packed to **8,361 bytes** (`R`, 16% of the
courses), plus 2,192 of masks and 519 of `OCCIDX` counts. Per record that is
1.1 - 1.6 bytes packed: WDIFF already makes the position words cheap.

**How many sit on standard pieces** (`recs.py`; LOO kit, records whose block
is a kit block):

| | FIRST | TRIAL | MILL | MOON | PEAK | PLAY | SHAPE | PITS |
|---|---|---|---|---|---|---|---|---|
| records | 81 | 297 | 394 | 1,588 | 1,544 | 1,510 | 288 | 326 |
| on a pairwise-kit block | 26% | 32% | 45% | 55% | 71% | 47% | 56% | 65% |
| their share of `R`'s packed bytes | 43 | 136 | 254 | 1,000 | 1,414 | 1,073 | 274 | 402 |
| distinct (block, s - br, mask) shapes among them | 19 | 69 | 88 | 331 | 450 | 313 | 39 | 85 |

So **at most about 4.6KB over the 8, about 575 bytes a course** could leave
the disk if every record on a kit block came from the kit. That is an upper
bound. A record exists because of the REACH behind the piece (where the ball
can be), not because of the piece. Only a piece's INTERNAL occlusion is
determined by the piece alone, for example a chute's near lip over its
channel, or a pit's rim over its floor. Those are the FIELD courses' records,
and SHAPE and PITS carry about 490 - 620 packed bytes of `R` in total. A
realistic saving is a third to a half of the bound, **about 200 - 300 bytes a
course**.

**What the loader would do.** Each piece carries its records relative to
itself, as `(dcol, dbr, ds, dtop, mask)`. A course stores a per-block-row
script: "n of mine, then piece p's records for its row r at (col0, br0, s0,
top0)". The expander walks the script and writes the sorted 4-byte records
directly. No search is needed, because the tool emits them in the final sort
order: one pass, an add a field. It is PRICED at **about 100 - 150 clk a
record**, so 1,000 records take about 30 ms, with about 150 - 250 bytes of
code. The tool can guarantee everything at build time:
- the order (it writes the script);
- the 4-a-block and 24-a-row bounds and the laid bounds (it checks the
  assembled result exactly as today);
- the MERGE at a piece's border: where a piece record and a neighbour's
  record would merge into one (same block, same cell row, tops within 2 px),
  the tool simply does not use the piece's record there and stores the
  merged one, so the guest only adds offsets.

The format and the per-frame cost are unchanged: the result IS today's
records.

**Verdict, plainly**: at 200 - 300 bytes a course it is about a fifth of
what the blocks give, for the most delicate tool work in the plan (the
reach, the merge, the residual). **Too small for the first round.** Revisit
it for FIELD pieces once standard chutes exist, where it is the chutes'
internal records only.

## 3. Keeping the kit in memory: referenced in place, or copied (question 3 and the owner's variant)

### 3.1 Referenced in place, from its own segment: refused

Every picture reader takes `DS` = the picture part (`bz_mseg`, 130.30.5). In
the same loop it reads the map word through `DS:BX` and the block's lines
through `DS:SI`:
- `bz_row`'s `BZ_RWORD`: `mov si, [bx]`, `movsw`, ...;
- `bz_col`, and `bz_boxc`'s fill;
- `bz_olay` (`lodsw` block, `xor` box, `and` mask);
- the wheel's commit.

`ES` is the card or the box, and `SS` the stack, so a block in another
segment needs `DS` switched and switched back inside the per-word loop.

- **A flag bit in the map word**: `test si, si / js` (+4 untaken) on an own
  block; `push ds / mov ds, [cs:kit] / ... / pop ds / jmp` (about +85) on a
  kit block. Against `BZ_RWORD`'s about 70 - 90 clk a word, a course drawn
  half from the kit pays **about +40 - 55% on every writer's word** (PRICED).
- **A 4-byte (far) map** (`lds si, [bx]`): about +16 clk a word (+20%), and
  the map, already the largest section (16 - 26KB), doubles. PLAYGROUND's
  picture part (45.3KB) would pass the 65,024 a part may be.
- **No branch** needs the kit and the course in one segment, so that every
  map word is one offset. Nothing makes two claims adjacent, so that means
  the kit inside the course's claim, which is copying.
- **And it saves no RAM.** One course is held at a time (plus the pathway),
  so the kit's pieces are needed once. A resident kit referenced in place
  holds the WHOLE kit. A copy holds only the pieces that course uses, plus
  the kit itself only while it is held. In-place referencing is never
  smaller.

### 3.2 The owner's variant: held, and copied in at load (CHOSEN)

*"Copied on load into the segment space reserved for it. And then just...
not drop."*

- **The format.** `B` (and `K`, and the world part's `F`) becomes two
  sections in RAM order: `b`, the kit's pieces this course uses, in kit
  order (a new form, KITREF: stored as a bitmap of the kit's pieces, RAM as
  the pieces), followed by the course's own `B` (PLAIN). The RAM form is
  today's layout: `BLKOFF` points at the first block, the map words are
  offsets, and every writer is unchanged. **0 clk a frame and a step.** The
  directory rule "`B` = (`BLKOFF`, 16 N)" becomes "`b` + `B`", which is a
  tool rule. The guest dispatches by the directory and the form.
- **In place.** KITREF writes 16 bytes a set bit from its slot's start
  while reading the bitmap from its end. It overtakes the bitmap only when
  the course uses almost all of a long run of kit pieces, so the expander
  copies the bitmap to `bz_boxbuf` first, as ROWPLANES does with its high
  bytes (1,024 bytes of scratch holds 8,192 bits).
- **The assembly, PRICED at 4.77 MHz**:
  - the bitmap walk is about 25 clk a bit (`shl` / `jnc`);
  - a block is `rep movsw` of 8 words from the kit's segment, about 175 clk;
  - a 289-byte table is about 3.6k clk.
  - So the pairwise kit (570 bits, 300 used) takes about 66k clk, **14 ms**;
    16 tables about 58k, **12 ms**; masks about 2 ms. **15 - 30 ms a
    course.**
- **Against reading and decoding those bytes today.** The pieces a course
  takes from the kit are 500 - 1,700 packed bytes it no longer reads: 1 - 3
  sectors at 35.6 ms (130.15.4.6's figure), about 35 - 120 ms. They are also
  about 5KB less to LZB-decode, at 60 - 200 clk a byte (LZ4's 63.8;
  `kernel/lz.inc`'s literal path 207), about 0.06 - 0.2 s. So **a launch
  with the kit held is about 0.1 - 0.2 s SHORTER** (PRICED).
- **When the kit is not held** it is fetched at the launch and dropped
  after the copy. That costs one more `op_fetch` (one more `int 13h` run,
  under 0.4 s, 130.30.8) and the kit's decode: about **+0.15 s for the small
  kit** (1.3KB packed, 3.8KB raw) and **+0.5 s for the pairwise kit** (5.3KB,
  14.3KB). That is the price on the machine without room.
- **Code**, PRICED: the KITREF form (the bitmap copy, the walk, one copy
  loop parameterised by the piece size) about 70 - 90 bytes; the kit's
  fetch, hold, release and drop beside `bz_phold`/`bz_phrel` (130.22.7)
  about 60 - 100; a part row and `bzcourse.inc` fields. **About 150 - 200
  bytes of package image and 4 of bss**, nothing in the kernel and nothing
  in `os88parts.inc`. kern_mega: the kit is a claim with an LDT selector
  from `op_seg`, and the copy reads through it. No `PKG_MEGA` arm (nothing
  adds to a segment). kern_small refuses BONANZA already (130.1).
- **How it converges with the dictionary.** Both decode out of the held
  kit; the dictionary is this design plus a prefix. If the +210 bytes a
  course is ever wanted, it is added later, with the kit copied in front of
  the stream and the course slid down after it. The variant chosen here does
  not block it.

### 3.3 Memory: what BONANZA holds today (MEASURED sizes, this tree; PREDICTED sums)

| | bytes |
|---|---|
| the region: image 49,732 + bss 11,431 + header and stack | **about 61.7KB** |
| the resident bundle (the balls and the resident families, held for the instance, 130.25.5.2) | 33,376 |
| the title (desktop) / the shell part (desktop) | 28,672 / 12,072 |
| a course: PEAK (largest one-part) / PLAYGROUND (two parts) | 41,503 / 45,320 + 14,979 = 60,299 |
| the pathway, when held (130.22.7) | 21,930 |
| the arena's play parts (sound, song, fanfare, families) | about 3 - 4KB |
| **a PLAYGROUND play** | **about 159KB without the pathway, about 181KB with it** |

- **A 640KB machine** (about 540KB of heap beside kern_big's 100KB) holds a
  15KB kit beside all of it with room. **Hold it.**
- **BONANZA's stated machine is a 256KB 5150, about 156KB of heap**
  (130.10.10, 130.14.11). The 20.5KB of headroom measured there was with a
  42.5KB region. The region is now about 61.7KB, and the sum above is
  already about 159KB for PLAYGROUND without a kit (PREDICTED; **an open
  question for the owner whatever the kit decides**). On that machine the
  kit is fetched on demand: as an `OP_ARENA` row taken before the course and
  dropped right after the copy, the arena regrown down. The peak is course +
  kit for a moment. The small kit (3.8KB) makes that peak cheap; the
  pairwise kit (14.3KB) may not fit beside PLAYGROUND there.
- **The hold rule** is 130.22.7's, extended: keep the kit when the largest
  free run still takes `BZ_CRS_MAXCLAIM` + `BZ_CRS_ARMAX` with the kit held;
  otherwise drop it after each assembly. Keep the pathway in preference to
  the kit: the pathway saves a whole part's read.
- **Split the kit by class**: a blocks-and-masks kit row and an F-library
  row, so a course with no shapes never fetches 10KB of tables.

## 4. Alignment (question 4)

The block patterns depend on `Y0` (130.25.3), and on `X0`, which is a
multiple of 8 on every course. `align.py` compiled FIRST, TRIAL, MILL, MOON
and PEAK at all eight `k`:

| course | Y0 mod 8 shipped | blocks at Y0 mod 8 = 0 / 4 / odd | in the LOO kit at 4 / 0 / odd | LZB at 4 / at 0 | refused at |
|---|---|---|---|---|---|
| FIRST | 4 | 135 / 133 / 131 - 156 | 62% / 41% / 21 - 25% | 1,868 / 1,879 | - |
| TRIAL | 4 | 228 / 230 / 232 - 264 | 44% / 32% / 12 - 15% | 3,427 / 3,462 | - |
| MILL | 4 | 511 / 519 / 523 - 581 | 25% / 14% / 4 - 5% | 6,890 / 6,861 | - |
| MOON | 4 | 353 / 385 / 434 | 32% / 22% / 6% | 7,587 / 7,314 | 2, 3, 5, 6, 7 (5 records in a block, over 4) |
| PEAK | 4 | 397 / 422 / 416 - 486 | 28% / 17% / 7 - 8% | 8,984 / 8,701 | - |

- **Fixing the kit at Y0 = 4 (mod 8) costs today's courses nothing.** All
  eight study courses already ship there (the search's fewest-records
  choice), and all five tested also compile at 0 (mod 8). The two
  alignments a multiple of 4 apart are also the two with the fewest blocks:
  a half-unit height step is 4 px, so 0 and 4 are each other's height
  phase. The kit should hold both, and does so naturally because courses
  use half-unit heights.
- **The 4-a-block bound** refuses MOON at five alignments of eight, and
  neither kit alignment. A future course refused at the kit's two alignments
  loses no correctness under explicit references: it compiles at another
  `k` and simply finds fewer kit pieces (4 - 25%). The kit is a library, not
  a format constraint. The tool's search should then weigh kit hits and
  bytes, not only records.
- **Side finding**: the search picks by records, not bytes. MOON and PEAK
  are 273 and 283 bytes SMALLER at 0 (mod 8) than at the shipped 4, with
  75 - 83 more records (300 - 330 more bytes of RAM). Worth a look whatever
  the kit decides.
- **A kit at all 8 alignments** (5 courses, pieces in 2+ at each alignment):
  1,509 distinct blocks against 340 at one, **7,381 bytes of LZB against
  2,339: 3.2x, not 8x**. Alignments share edge and outline blocks. It is
  not worth carrying: fix the kit at {0, 4} (mod 8) and steer the search.

## 5. Extrapolation to ~20 courses (question 5)

**A plausible standard kit** (PREDICTED from the measured kits):
- the pairwise kit's art: floors, faces down to the ground (130.27),
  outlines and corners, at Y0 in {0, 4} (mod 8), about 570 blocks and 144
  masks, **5.3KB of LZB**;
- the FIELD library for the standard chutes:
  - 2-wide `round` 10 px, `bank` 8 px;
  - 1-wide `round` 5 px, `bank` 4 px;
  - their corners and tapers, and the pit r3 16 px;
  - today's 36 tables are 3.1KB, and fixing the profiles makes a chute's
    tables identical wherever it is laid;
- the picture blocks of those chutes and the common props, from the shape
  courses' share, **about 1 - 2KB**.

**About 9 - 10KB of LZB in all, about 25KB raw** (the RAM it holds), in two
rows.

**The model.** A release course averages today's study-set size, 6.5KB of
LZB. That is low: 130.15.8's plan is about 209 bytes a target second, and
1,170 s over 20 courses is about 12KB a course. A saving is a fraction of a
course:

| how heavily a course uses the kit | the evidence | saved a course | 20 courses at 6.5KB | at 12KB | ratio against a 9.5KB kit |
|---|---|---|---|---|---|
| lightly: drawn freely, like today's | LOO, MIN 2 + dict: -11% | 750 | 15KB | 28KB | 1.6x / 2.9x |
| as much as today's courses share with each other | in-sample, MIN 2 + dict: -25% | 1,670 | 33KB | 60KB | 3.5x / 6.3x |
| built from it, own art only for features | the MIN 1 ceiling: -41%, less a margin: -30 to -35% | 2.0 - 2.3K | 40 - 46KB | 72 - 84KB | 4 - 5x / 7.5 - 9x |
| a shape course whose chutes are standard | + its F tables: -1.4KB | + 1,400 | | | |

**The small kit** is MEASURED, not modelled: 3.4x in-sample, and -530 a
course LOO (20 x 530 = 10.6KB against 1.3KB: 8x). It clears the bar on any
assumption.

So the owner's 3x bar is passed by the small kit at once, and by the full
standard kit when courses are built to use it. It is MISSED (1.6x) only if
courses go on being drawn freely while a big kit is carried.

## 6. Recommendation

**First, the disk.** Today `bonanza360.img` is **124 of 354 clusters**: 7
courses at 46.2KB of parts and about 72KB of everything else (MEASURED,
`make bonanzadisk` at this tree). Thirteen more courses at today's 6.9KB
average are about 90KB more: about **214 of 354 clusters, on one disk with
no kit**. The disk binds only if courses average about 12KB, which is
130.15.8's per-second plan and PLAYGROUND's size (about 72 + 20 x 12 = 312KB
plus slack). In that case the kit's 28 - 60KB is the difference. **The kit
is insurance for the courses to come, and it pays for itself even on
today's courses** (3.4x), which is why it is still recommended. Say if that
is not the priority.

**Build:**
1. **The held kit, explicit references, pieces copied in at load** (3.2).
   0 clk a frame and a step; about 150 - 200 bytes of package code and 0
   kernel bytes; a launch about 0.1 - 0.2 s shorter when the kit is held,
   and +0.15 s when it is not (small kit).
2. **Start with the SMALL kit** (pieces in 3+ courses, generated by the
   tool from the shipped courses: 1.3KB packed, 3.8KB held) **and the
   F library** (3.1KB) as a second row. Grow it into the designed kit (5) as
   the owner's standard pieces settle. Each piece's place in the kit is
   fixed once it ships: a kit is append-only, because a course's bitmap
   names kit indices.
3. **The alignment**: the kit at Y0 in {0, 4} (mod 8). The Y0 search keeps
   its 8 candidates but scores bytes, kit pieces included.
4. **Not now**: relocatable records (about 200 - 300 bytes a course, section
   2), the dictionary (+210 a course, 1.4), kit-global numbering and map
   runs (45 - 110 a course, 1.5), and in-place referencing (+40 - 55% a
   writer word, 3.1).

**Waves:**

| wave | what | the guest | evidence |
|---|---|---|---|
| K1 | the tool: the kit's source and its `BZKIT.BIN` (generated from the courses at first), courses compiled kit-first, `--sizes` printing each course's kit pieces and savings, `read_part`/`expand` modelling KITREF, `--selfcheck` items (expand with the kit = the RAM form; red arms: a bit off, the kit one piece short, the bitmap read in place) | none | host |
| K2 | the guest: the kit row(s), hold/claim-when-available/drop-after-copy, KITREF in `bz_cexp`'s dispatch (`BZ_FORMS`), the Hercules translation after the copy | about 150 - 200 bytes | `bonanzaexit`'s claim compare (the RAM form after assembly), `bonanzapath` (hold with the kit, both ways), `bonanzacourse`, the kern_mega row |
| K3 | the designed kit and the F library, and the courses re-authored to use it | none | the owner's design work; identities and demos re-stamped once |
| (later) | relocatable FIELD-piece records; the dictionary | a few hundred bytes | if K3's courses show them worth it |

Every course's identity moves once at K1 (the block order changes, so the
map words change), and the demos re-stamp with it, as at 130.25.3.

**The 3x test**, MEASURED where stated:
- the small kit: **3.4x on today's 8 courses**, about 8x over 20 courses
  LOO;
- the pairwise kit: 2.0 - 2.5x today; 2.9 - 6.3x over 20 courses at the
  plan's 12KB a course, depending on how deliberately the courses use it.

The guest's 150 - 200 bytes is about 1% of either side.

**Open questions for the owner:**
1. Is the disk the priority now? At today's density 20 courses fit
   (section 6); the kit insures against courses of about 12KB.
2. Hold the kit, or the pathway, when only one fits? This study's answer:
   the pathway (a whole part's read).
3. On the 256KB 5150: today's PLAYGROUND play sums to about 159KB of heap
   against the ~156KB stated (3.3, PREDICTED; the region grew from 42.5KB to
   61.7KB since the 20.5KB headroom was measured). This needs measuring
   whatever the kit decides.
4. Is the kit append-only from the first release on? If so, a later
   course's change to a standard piece is a new piece, never an edit.
5. Should the Y0 search score bytes rather than records? It would save
   MOON 273 and PEAK 283 bytes today, for about 300 bytes of RAM each.
