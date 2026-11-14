# What else is smaller and runs at the same speed: BONANZA's bytes

**A measurement.** Taken 2026-11-14 at commit `28b13cce` on branch
`bounce-bonanza` (a clean tree), on a Linux container. It was done on the
host only: no emulator was run, and no guest, tool, course or SPEC.md byte
was changed. Every packed figure comes from the build's own compressor,
`tools/os88lz.py`, called as `os88pkg.compress_part` calls it (LZ4, with the
near-call filter tried). Raw figures are bytes in the parts as built
(`build/bonanza-art/`, current after `make bonanzadisk`). Figures are marked:
- **MEASURED**: computed from the real parts, the real image or assembled
  code;
- **PREDICTED**: arithmetic from the 8088's instruction timings, from
  `tools/x3cyc.py`'s cycle model, or from a proportional model;
- **ESTIMATED**: a clock count for code that was written down but not
  assembled.

**The owner's question** (2026-11-14): *"start an agent on 'what else is
smaller but does the same thing at the same speed'. They can look at more
than just occlusion, too."* The reason for asking is the goal of about 20
courses that are longer than today's (about 30 s early, 60 s in the
middle, 90 s for the last few), on 360KB floppies.

**What "same speed" means here.** Code that runs every FRAME or every STEP
on the 4.77 MHz 8088 must not get slower. Where it would, the clocks are
stated. Work done once at LOAD time is allowed if it is priced. A 5150
already takes about 4-5 s to launch PEAK.

**The answer on one screen.**
- **The occluder records are the lever, and they are better stored as
  DIFFERENCES than as smaller fields.** Each record differs from the one
  before it in very few bits: the column steps by 1 or 0 about 95% of the
  time, and the screen line, top and mask repeat. Stored as word
  differences, in place, and summed back at load, whole records become
  LZ4 matches.
  - On today's 8-byte records this saves **-32,616 bytes packed** over the
    six courses at exactly **0 clocks a frame** (idea C).
  - With 4-byte records in RAM as well (idea D) it saves **-35,379
    packed** and **-43,812 bytes of RAM**, and frees 13,156 bytes of
    PEAK's part. That costs about +30 clk on a typical occluder frame and
    about +450 at the worst reachable position (ESTIMATED).
  - This beats the plan's R2 layout (4 bytes, structure-of-arrays, -28.8KB
    measured section by section).
- **Five smaller course items** (the map as index planes, ROWTAB computed,
  the route compacted, the lift's sprite shared, and the grid's derivable
  fields rebuilt) add a further -5.0KB. **The whole 5b shortlist, measured
  together: 83,152 -> 42,792 bytes packed (-40,360, -48.5%)** over the six
  courses.
- **Outside the courses:**
  - The ball parts can be regenerated at fetch time, byte for byte:
    **7,380 -> 1,668 packed**.
  - The demos as a bit stream save **about 8.5KB at twenty courses**.
  - LZB for the image alone saves **-3,248 bytes** for about +0.64 s when
    the window opens.
  - LZB for the parts saves **-8,188 more on the shortlist form**, at about
    +0.9 s on PEAK's launch.
- **The binding limit for long courses is RAM, not disk.** One part is
  65,024 bytes, and PEAK already uses 60,856 of them.
  - With idea D, a part holds about 195 block rows: **about 73 s** at
    MOON's and PEAK's pace.
  - A 90 s course needs the two zero-clock RAM levers as well (section 6),
    and a slower pace per block row, or the grid moved to a claim of its
    own.
- **Twenty courses on a 360KB disk** (PREDICTED, section 7):
  - Today's form: about 490 KiB of courses, so they do not fit.
  - With the shortlist: about 253 KiB, against about 239 KiB available
    once the non-course items are taken too. It is about 14 KiB over.
  - With LZB parts as well: about 206 KiB, which fits.

## 1. Method

Five agents measured five areas: the occluders, the rest of the course,
the image, the parts, and the visibility of the mechanics. This report
adds one measurement of its own, the shortlist COMBINED (section 4). The
scripts are in the session's scratchpad and are not part of the tree:
`/tmp/claude-0/-home-user-os8088/0182ea0a-f570-5702-909a-759b39cca949/scratchpad/size/`.
The main ones:
- `occ1.py` to `occ5.py`: the occluder forms, with an in-place
  round-trip check (output in `occ3.out` and `occ5.out`).
- `loops.asm`: the load loops, assembled with nasm (`loops.lst`).
- `m1_sections.py` to `m14_project.py` and `enc.py`: the course sections.
- `routines.py`, `cg.py` and `variant.py`: the image's attribution, call
  graph and assembled variants.
- `ball1.py` to `ball7.py`, `demo.py`, `demo2.py`, `song.py` and `lzb.py`:
  the parts.
- `vis.py` and `seethru.py`: the visibility audit (output under `vis/`).
- `combo/combo5b.py`: the combined shortlist (output in
  `combo/combo5b.out`).

**How each idea was checked:**
- **Lossless forms** were decoded back on the host and compared byte for
  byte with the real target. Where the form is meant to be expanded in
  place inside the course claim, the decode ran IN PLACE in one
  bytearray, as the guest would run it.
- **Packed sizes** are for the WHOLE part as os88pkg would pack it, never a
  section packed on its own. The exception is section 2's table of where
  the bytes are, which gives each section's marginal share. A form that
  ships a zero hole is packed with the hole, which costs 25-130 bytes.
- **Clocks** come from the 8088 tables: 8086 timing plus 4 for each word
  memory access, with the bus floor checked. Two load loops were also run
  through `tools/x3cyc.py`. Load milliseconds are at 4,770 clk to 1 ms.
- **Disk time** is 35.6 ms a sector, the parts agent's figure.

## 2. Where the bytes are today (MEASURED)

**The package** `BONANZA.O88` is 125,162 bytes, 123 of the 130 clusters
it uses on `bonanza360.img`:

| piece | raw | packed |
|---|---|---|
| image (code, tables, part table) | 32,640 | 27,963 |
| six courses | 223,420 | 83,152 |
| three balls (rubber, steel, glass) | 29,888 | 7,380 (2,658 / 1,908 / 2,814) |
| sound (BZSND and six songs) | | 4,904 |
| five demos | 2,062 | 1,627 |
| paragraph padding, 21 parts | | about 137 |

**The courses** (packed, in context; raw in brackets):

| section | all six |
|---|---|
| OCCIDX and occluder records | 49,221 (88,730) |
| blocks | 13,613 (27,824) |
| map | 9,182 (70,016) |
| grid cells | 5,551 (24,608) |
| masks | 2,281 (7,648) |
| props | 1,392 (3,008) |
| ROWTAB | 852 (850) |
| route | 354 (352) |

| course | records N | OCCIDX | masks | part raw | part packed |
|---|---|---|---|---|---|
| BENCH | 2,645 | 254 | 92 | 49,272 | 17,930 |
| FIRST | 290 | 68 | 35 | 9,748 | 3,040 |
| TRIAL | 786 | 102 | 44 | 18,446 | 6,614 |
| MILL | 1,324 | 158 | 70 | 33,858 | 13,937 |
| MOON | 2,619 | 256 | 115 | 51,240 | 17,982 |
| PEAK | 3,289 | 268 | 122 | 60,856 | 23,649 |
| **total** | | | | **223,420** | **83,152** |

On PEAK, the records are 26,312 bytes, 43% of the part. PEAK's part is
60,856 of the 65,024-byte `PARTMAX`, so it has 4,168 bytes left.

**The image:** 32,640 bytes, plus 7,653 of bss. Of the bss, `bz_rlog` is
4,096 and `bz_boxbuf` 1,024. The 64KB segment has about 24.9KB free, so
the segment does not bind.

| part of the image | bytes |
|---|---|
| header | 128 |
| HOT: runs every frame or step | 21,143 |
| ...of which the `bz_step` cone, every step | 6,432 |
| reached from the loop, but not every frame | 1,020 |
| launch code (in the bracket) and the parts library | 4,038 |
| desktop and front end only | 6,311 |

All 485 image labels are reachable, and no HUD code remains.

## 3. Every idea, measured

Bytes are deltas against today. A minus sign is a saving. "Per course" is
listed BENCH / FIRST / TRIAL / MILL / MOON / PEAK.

### 3.1 Occluder records (SPEC.md 128.10.4.4)

| idea | what it changes | raw / RAM | packed (per course; total) | speed | risk | verdict |
|---|---|---|---|---|---|---|
| **C** | today's 8-byte records stored IN PLACE as the word difference from the previous record; OCCIDX as one count byte a row at the end of its area. The load runs `rec[i] += rec[i-1]` and rebuilds OCCIDX. RAM is byte-identical to today | 0 | -9,499 / -643 / -2,081 / -4,043 / -7,462 / -8,888; **-32,616** (byte deltas: -32,711) | **0 a frame and a step.** Load: 213 clk a record and 63 a row. PEAK 709k clk = 149 ms, BENCH 120, MOON 119, MILL 60, TRIAL 36, FIRST 13 ms. PEAK also reads about 17 fewer sectors | low: about 50 bytes of launch code, and the frame code is untouched. Host rows that read records from the PART file must decode first | **yes, if the frame code may not change by one clock** |
| **D** | the 4-byte record `[col, s - br + SB, top - TB, mask index]` kept IN RAM, stored on disk as in C (word differences in place, count bytes a row); `bz_occ` compares bytes | **-10,580 / -1,160 / -3,144 / -5,296 / -10,476 / -13,156; -43,812.** PEAK's claim goes from 60,856 to 47,700, so its `PARTMAX` headroom grows from 4.2KB to 17.3KB | -9,988 / -768 / -2,319 / -4,421 / -8,092 / -9,791; **-35,379** (83,152 -> 47,773, -42.5%) | Load: 115 clk a record (a 10-byte loop) and 63 a row. PEAK 387k clk = 81 ms, BENCH and MOON 65, MILL 33, TRIAL 20, FIRST 7 ms. **Per frame, ESTIMATED** (see the breakdown below): about **+30 clk** on a typical occluder frame, about **+450** at the worst reachable position (about 1.4% of that pass's 28-34k). Frames where the occluder gate is closed, and the step: 0 | medium. `bz_occ`, `bz_oand` and the binary search change. A 2 x NMASK word table goes in bss (at most 512 bytes). About +110 image bytes (ESTIMATED). SB must be chosen from the tool's reach queries (MOON's minimum key is -4). A future course whose top span exceeds 254 or whose s span exceeds 255 is refused. Every row that reads records from guest memory changes, and so does the course identity | **YES: recommended.** It is the only form that frees part RAM for longer courses |
| E | D's 4-byte RAM records with no difference coding | as D | -3,033 / -262 / -491 / -1,636 / -3,133 / -3,541; -12,096 | load: only the counts (PEAK 1.8 ms); per frame as D | as D, without the load loop | only if the load loop is refused |
| A | 4-byte records on disk in a zero hole, expanded backward into today's 8-byte records | 0 | -2,853 / -226 / -430 / -1,546 / -2,966 / -3,362; -11,383 | load 172 clk a record (PEAK 122 ms); 0 a frame | low | no: C saves three times as much for similar load work |
| B | 4-byte records with every field delta-coded (AoS, SoA and variable-length variants), decoded into today's records | 0 in RAM | AoS -35,247; variable-length -35,529; SoA -32,442 | load 190-220 clk a record, and it needs a scratch buffer (PEAK 13.3KB, or 9.1KB for the variable-length form): none of them decodes in place | medium: a second claim at load | no: D packs as well, in place |
| F | OCCIDX as a count byte a row, on its own | 0 in RAM | -129 / -24 / -39 / -63 / -119 / -117; -491 | load 63 clk a row | low | yes, inside C or D, where it is already counted |
| G | one mask part shared by all courses, indexed by a byte | disk -2,240; RAM +3,456 while playing PEAK | about -730 | one more part fetch, about 0.4 s | high: twenty courses will exceed 256 distinct masks (six already have 338) | no |
| H | other splits: SoA field streams, s relative to the row, top as a running delta | 0 | SoA is 2.8-3KB WORSE than interleaved records; the others are within 14 bytes | SoA cannot decode in place | | no |

**D's per-frame breakdown** (ESTIMATED from `bz_occ` and `bz_oand` in
`apps/bonanza/bzvideo.inc`):
- each record tested: `cmp cl,[si+1]` (18 clk) replaces `cmp cx,[si+2]`
  (22), so -4;
- each record that passes the s test: -4 in the same way;
- each LAID record: about +22, for the mask's table lookup;
- each block row: +3;
- each frame: about +45 to +50 for the keys.

The measured occluder footprint averages 7.8-9.8 records and at most 28.
The worst laid count is 20-28 per course. So a typical occluder frame (9
tested, 4 passing, 1.1 laid) costs about +30, and the worst about +450.

**Why differences beat smaller fields.** Packing records to 4 bytes alone
saves 11.6KB packed. Differences on today's 8-byte records save 32.6KB.
Both together save 35.4KB. LZ4 cannot match a record that differs from its
neighbour by one column, but it can match a run of identical difference
words.

### 3.2 The rest of the course

All of these are expanded at load into today's BZC1 bytes. Their cost is
0 a frame and 0 a step, and none of them changes the course identity
unless the row says so.

| idea | raw | packed (per course; total) | load (PEAK) | risk | verdict |
|---|---|---|---|---|---|
| **map as block indices**: a low-byte plane plus a 2-bit high plane (up to 1,024 blocks; MILL has 469) | disk 2 -> 1.25 bytes a cell (PEAK 17,024 -> 10,640) | -350 / -111 / -247 / -421 / -415 / -390; **-1,934** | about 75 clk a cell, 0.64M clk = 0.13 s; about 50 bytes of code | low | **5b** |
| **ROWTAB computed** at load (`celloff + 4 KW r`) | -2 x NROWS (PEAK -224) | -206 / -44 / -64 / -100 / -213 / -225; **-852** (an arithmetic sequence does not compress) | about 3k clk, under 1 ms | low. If the grid rows are overlapped (section 6), ship one byte a row instead | **5b** |
| **route as way tiles** (2 bytes a way), positions computed at load | 352 -> 176 over six | -50 / -6 / -13 / -44 / -90 / -113; **-316** (about -354 if dropped from courses where only the autopilot reads it) | about 4k clk | low | **5b** |
| **platform sprite shipped once** (576 bytes, the same in every course) and copied in at load | -576 a course with a lift | MILL -156, PEAK -157; **-313** | one 576-byte copy, about 5k clk | low, but it needs a shared part to live in (the claims are 7 of 8) | with the first shared part |
| **grid's derivable fields rebuilt**: VOID kill heights, the OPEN marker and the SAFE flag (OCC and OCCG stay shipped) | 0 (more zeros) | -523 / -94 / -115 / -272 / -334 / -453; **-1,791** on top of the items above | a separable 5x5 minimum and a SAFE pass, about 0.7M clk = 0.15 s (PREDICTED); about 200 bytes of launch code | medium: the tool's logic duplicated in the guest. The guard is `expand == BZC1` on every course | **5b follow-up** |
| LZB for every part | 0 | today: -4,406 / -647 / -1,454 / -2,942 / -4,092 / -5,160, **-18,701**. On the shortlist form: **-8,188** (section 4) | about 191 against 63.8 clk an output byte. Today's PEAK: +1.26 s at launch. On the shortlist form about +0.9 s (PREDICTED) | low technically: the kernel ships both decoders. The format byte is the part TABLE's, so it is all or nothing | **the owner's call** |
| render the PICTURE at load from the grid (map and blocks); lane poses and occluders still shipped | PEAK's compact form 39,263 -> 23,719 | -19,052 against the plan's compact form (25,161 with LZB) | about 9M clk = 1.9 s +-50% for PEAK (PREDICTED from counted work) | high: a second renderer that must match the tool pixel for pixel | prototype later (wave 10 or before world 3) |
| a world BLOCK POOL | 1,739 blocks -> 1,413 distinct; MOON and PEAK share 8 | -3,986 for one pool of six, but only -1,640 split into shared and own blocks | the pool in RAM at load (about 20KB a world) | medium-high | defer; moot if the picture is rendered at load |
| measured and REJECTED for the map, blocks and grid | | index words -404; byte planes -1,788; 12-bit -1,357; trimmed rows -226; predictor codes +760; block SoA +9,950; block XOR +1,747; sorted +103; 2-colour +306; grid SoA +219; pose maps as indices +19 | | | no: LZ4 already finds the isometric map's 2-row period |

### 3.3 The image

| idea | raw | packed | speed | risk | verdict |
|---|---|---|---|---|---|
| **wave 8a, re-measured**: the desktop and front-end code moves to a lazy CODE part | 5,813 bytes leave the image; net **about 5.6-5.9KB** resident after about 170 bytes of thunks and about 300 of `bz_post` moved. **Not the plan's 7-8KB**: that also needs the 1,971 bytes of once-per-launch code inside the bracket and the 750-byte calibration, which stay resident | disk **+0.45KB** worse (split packing +286, a row, padding, thunks) | 0 a frame and a step. About +0.4 s for each return to the desktop (one more fetch). Calls from the shell into resident code become far calls (+20 clk, desktop only) | medium: far gateways, the face strings need `CS:` reads or must stay resident, and kern_mega needs a code selector | yes, restated as 5.6-5.9KB |
| course metadata (titles, names, pars, ids, balls) into the shell part | 53 resident bytes a course today. Only the 8-byte course row stays: **-45 a course, about -900 at twenty** | about 0 | 0 | low | yes, with 8a |
| titles as packed NUL-terminated strings | 150 -> 79 (-71; about -230 at twenty) | about half of that | a walk of at most twenty strings when the face is drawn, about 4k clk | very low | yes, small |
| the desktop's scratch bss overlaid on `bz_boxbuf + 512` | bss 7,653 -> 7,483 (**-170 RAM**) | -11 | 0 | low; an `%error` guard is needed | yes |
| `bz_prod` generated at load | image -232, bss +256 (RAM +27) | -215 | load about 7 ms; 0 a step | low | only if the disk binds |
| instruments as a rows-only build variant (20 counters, harness hooks, B/D's per-part breakdown) | -161 / -83 / -344 (-574 together) | -154 / -76 / -271 (-469) | play gets FASTER: about 1.2-1.6k clk a frame without the marks (PREDICTED) | the rows would then test a binary that does not ship | hold. A cheaper middle step: an early `cmp [bz_meas],0` in `bz_mark` costs +6 bytes and saves about 1k clk a frame in play (PREDICTED) |
| the three ball parts joined into one | 2 rows, -16 resident | -528 | RAM +8-13KB at play when a course needs fewer balls | high against the 256KB play budget | no |
| once-per-launch code as a second lazy part | about 2.7KB | +0.3KB | +1 fetch | it is resident at the RAM peak anyway, and it would take claim 8 of 8 | no |
| shared code runs (749 bytes of identical runs of 16 or more bytes) | about 0 realistically | LZ4 already folds them | +35 clk for each shared call on a hot path | breaks deliberate unrolling | no |
| generated physics tables | at most about 70 | under 50 | an indirection in `bz_corner` (hot) | touches `BZ_PHYSV` | no |
| strings, padding, dead code | about 170 | under 50 | | | no on its own; the strings leave with 8a |

### 3.4 Balls, demos, sound and the package

| idea | raw | packed | speed | risk | verdict |
|---|---|---|---|---|---|
| **ball V1**: every mask and frame stored once, at shift 0. The four shifts, both parity copies, the shadow (`shadow(p,s) = shift(base[(p+s)&1], s)`) and the shatter cut (with a 64-byte edge-black rule) are built at fetch | stored 8,256 -> 4,480 (rubber, steel); 13,376 -> 5,312 (glass) | 2,658 / 1,908 / 2,814 -> 1,962 / 1,357 / 1,493; **-2,568** | 0 a frame and a step: the heap layout is identical. Load, net of the shorter decode and disk read (x3cyc): rubber +23 ms, steel +33, glass -12. About 150-200 image bytes | low; a host-under-8086 check, as `bz_hxlat` has. Without the edge bitmaps, 54 bytes differ | yes, as V2's first stage |
| **ball V2**: V1, plus the 64 roll frames generated from a per-material 2-bit template and one phase table, `A[x][fx] + A[y][fy] < T`. Steel and glass use byte tables. Rubber needs words: its closest case is 0.00065 from the threshold | rubber 707, steel 579, glass 1,411 stored | **7,380 -> 1,668 (-5,712, -77%)**; about -5.4KB net of about 410 image bytes | 0 a frame. Load: rubber +41 ms, steel +62, glass +48; a three-ball launch about +150 ms | medium: every future texture must stay template plus a separable sum. In-place expansion needs the tool to order the bytes, or about 700 bytes of scratch | **yes, in wave 9 with 9.1's one ball claim** |
| parity copies held once in the heap, on the CGA only | heap -1,280 / -1,280 / -3,840 | 0 | +4-8 clk a frame in `bz_sprite` | a per-card claim size | no |
| **demos as a bit stream**: a Huffman code for the key (with an escape for any key the code does not list) and Elias gamma for the run count, expanded into BZR1 pairs at the copy into `bz_rlog`; the header trimmed to about 5 bytes | 1,976 bytes of runs -> about 775 | 1,627 -> 855 (**-772**; -55 more for the header). **About 18KB -> 9.5KB at twenty courses** (PREDICTED: 1,170 s of demo at 15.5 packed bytes a second) | 0 a frame. At the copy about 300 clk a run, BZD5 28 ms | low; the code table is generated into `bzcourse.inc` | **yes: the one item that grows with the course count** |
| demos as one byte a run (`key<<4 | count`) with an escape | 2,062 -> 1,249 | -414 (about -4.4KB at twenty) | about 20 clk a run | very low | only if the Huffman decoder is judged too much code |
| the demos joined into one part with an index | 8 bytes a row (-152 at twenty) | -141 today | a few KB more decoded at `V` | low; the claim needs a ceiling check | yes, at about 10 demos or more |
| **LZB for the IMAGE only** (`LZBPKGS`) | 0 | **27,963 -> 24,712 (-3,248, -3 clusters)** | about +0.64 s each time the window opens; 0 at a course launch | low: the existing mechanism, and `t_lzbclust` checks it | **yes, if the owner accepts +0.6 s** |
| songs without a stored gate (the other session's area, SPEC.md 128.20) | 6,041 -> 5,100 | -270 | +40-60 clk on a sub-tick that keys a note | medium, and it is the other session's code | suggestion, low priority |
| the six songs joined into one part | 0 | -150 | all the songs held in memory | low | no |
| part headers and paragraph padding | about 4-10 bytes a part | padding about 137 over 21 parts | 0 | low | minor: only the demo header trim |

### 3.5 Visibility: the springs, the cup and PEAK's end

This was measured from each course's own picture: each pixel's owner tile
from `bbcourse.render(owners=True)`, and the autopilot's route stepped
through `bbcourse.Physics`. The ball's pixels were tested against the
records the guest would lay (`laid_at`). "Hidden" below means more than
50% of the ball covered.

**The geometric rule.** Geometry toward the viewer (+x or +y) that stands
dh units above a floor hides that floor for about dh block rows behind it.

**What is hidden today:**
- **PEAK**:
  - Both springs: 0 of 136 px visible. Spring 1 is behind the front of
    U1, the tier it launches onto. Spring 2 is behind L4's tops and the
    corridor walls.
  - The cup: 0 of 76 px, with the pin at 1 of 28. It is behind the x = 57
    rail, which stands 4 units above the green and 2 rows in front. **This
    is why the owner could not find the end.**
  - The rubber pad: 0 of 136 px.
  - The drop tube: its IN and OUT are both 0% visible.
  - The ball is hidden on 475 of the route's 1,902 steps (274 of them
    completely), including 3.00 s in the moat corridor.
- **MOON**:
  - Two tube INs are 0% visible and a third is 38%.
  - The ball is hidden for 0.86 s and 0.68 s, the second while it turns
    through 35 degrees.
- **MILL**: one tube IN is exactly 50% visible.
- **FIRST and TRIAL**: nothing is hidden.

| idea | bytes | speed | verdict |
|---|---|---|---|
| **(c) a visibility rule in `bbcourse.py`** (compile and `--selfcheck`). Every spring, pad and cup must be at least 75% visible. Every tube mouth must be at least 50% visible. No stretch over 0.5 s (27 steps) where the ball is more than 50% hidden outside a tube, unless the course declares it `hidden`; a declared stretch must turn less than 30 degrees. Every course prints its hidden stretches | 0 | 0 on the guest; host 0.6 s for PEAK | **YES**. It reports first, and refuses once PEAK and MOON are redesigned |
| **(a) the ghost dither in the data**: the tool ORs a checker (0xCC and 0x33 on alternate lines) into every occluder mask. The lay is `((buf XOR block) AND mask) XOR block` whatever the mask holds, so a ball behind anything shows as a 50% ghost | masks -896 raw; **-710 packed** (PEAK -577) | **0 clk, 0 guest bytes** | **YES**, as the safety net. Glass reads as a dotted ring. The checker is fixed in the world, so a moving ghost shimmers; on the Hercules it reads as a 2x1 grey |
| (a) only on walls, or on walls marked `seethru` | +986 packed | 0 | no, unless the owner dislikes ghosts in pits |
| (a) at run time (a flag bit, with the checker ORed in by the guest) | +40-60 image bytes | about 250-350 clk a laid group, ESTIMATED | no |
| (a) as an outline (the ball's rim redrawn over the occluders) | about 6KB a material | about 2.5-3k clk a box | no |
| ghosts of the props painted into the static picture | PEAK +310 packed | 0 | no: it reads poorly on the checkered faces |
| (b) cutaway walls drawn low while the physics keeps them tall | | 0 | no: the picture would lie to an airborne ball |
| **(b) real low near rails**, one or two units above the floor they guard. One unit still stops a roll, which climbs 4 px, and a rubber Hop (5 px apex) | PEAK, four changes: +914 raw, +1,234 packed. The moat walls alone: -53 | 0 | **YES, as a design rule**. On a scratch PEAK the route was unchanged (1,902 steps, holed out). Hidden steps fell from 475 to 98, and the cup and pad went from 0% to 100% visible |
| **design direction**: springs, climbs, tube runs and drop landings go AWAY from the camera (-x or -y) | 0 | 0 | **YES** |

## 4. The 5b shortlist, measured together (MEASURED)

`combo/combo5b.py` stacks the items into one compact stream:
- **D**: the records' word differences and count bytes;
- **M**: the map planes;
- **R**: ROWTAB computed;
- **W**: the route in 2.25 bytes a way, losslessly (a stand-in for the
  course agent's way tiles);
- **P**: no per-course platform sprite;
- **G**: the grid's derivable fields zeroed, as the course agent's m12 did.

Every section except G is decoded back on the host and compared. The
stream is packed as a whole part, behind a zero hole for in-place
expansion:

| form | BENCH | FIRST | TRIAL | MILL | MOON | PEAK | **total packed** | total RAM |
|---|---|---|---|---|---|---|---|---|
| today | 17,930 | 3,040 | 6,614 | 13,937 | 17,982 | 23,649 | **83,152** | 223,420 |
| D alone | 7,943 | 2,273 | 4,297 | 9,518 | 9,892 | 13,859 | **47,782** | 179,608 |
| D + M + R + W + P | 7,377 | 2,109 | 3,975 | 8,830 | 9,237 | 13,039 | **44,567** (-46.4%) | 179,608 |
| **D + M + R + W + P + G** | **6,858** | **2,013** | **3,863** | **8,564** | **8,910** | **12,584** | **42,792 (-40,360, -48.5%)** | 179,608 |
| that, with LZB parts | 5,437 | 1,593 | 3,093 | 6,949 | 7,227 | 10,305 | **34,604** | 179,608 |
| today, with LZB parts | 13,524 | 2,393 | 5,160 | 10,995 | 13,890 | 18,489 | 64,451 | 223,420 |

A few cross-checks:
- "D alone" reproduces the occluder agent's 47,773 to within 9 bytes. The
  two are packaged differently: a tail stream here, in place there.
- With C instead of D, about 2.8KB more is packed and RAM is unchanged.
- The items do not add up exactly. Taken one at a time, M, R, W, P and G
  sum to -5,206 against today's records. On top of D they give -4,990.

**The load work it adds to PEAK** (PREDICTED; section 3 prices each item):
- the records 81 ms;
- the map 0.13 s;
- the grid fields 0.15 s;
- ROWTAB, the route and the sprite about 2 ms.

That is **about +0.37 s**. Against it, the part is 11,065 bytes smaller
on the disk, about 21 sectors, about **-0.77 s** of reading, and the LZ4
decoder writes 13KB less. **A launch should get shorter, not longer.**
MartyPC measures that in the final pass.

## 5. The shortlist

**Do these in wave 5b** (ranked by bytes for the risk):

1. **D: occluder records as word differences in place, 4-byte records in
   RAM, OCCIDX as count bytes.**
   - Saves -35,379 packed and -43,812 of RAM; PEAK's headroom goes from
     4.2KB to 17.3KB.
   - Per frame: about +30 clk typical and +450 worst (ESTIMATED).
     `bonanzaperf` measures it on MILL's and PEAK's demos, against the HUD
     rule of at most 2 more misses a card with the speaker on.
   - **The fallback is C**: the same disk form expanded into today's
     8-byte records, at exactly 0 clocks a frame and -32,616 packed. The
     RAM half then waits for T10.
2. **The map as index planes:** -1,934, 0.13 s of load.
3. **ROWTAB computed:** -852, under 1 ms.
4. **The route as way tiles:** -316. Drop it on play courses if only the
   autopilot reads it.
5. **The grid's derivable fields** (a 5b follow-up, after the four above
   are green): -1,791, 0.15 s of load. The guard is `expand == BZC1` on
   every course.
6. **The ghost dither in the masks:** -710 packed, at 0 clocks. Its
   audit's report mode lands with it (section 8).

Together, measured: **83,152 -> 42,792 packed**. That is about half of
today's course bytes on the disk (51.5%), and 80% of today's RAM.

**Later, each in the wave named:**
- **Ball V1 then V2** (wave 9, with 9.1's single ball claim): -5,712
  packed, about +150 ms a three-ball launch.
- **Demos as a bit stream, joined into one indexed part** (wave 11, the
  pipeline; before the first recorded demo of a new course): -772 now,
  about -8.5KB at twenty.
- **LZB for the image** (any time, the owner's call): -3,248, +0.64 s when
  the window opens.
- **Wave 8a's code part:** 5.6-5.9KB resident, not 7-8KB. Course
  metadata goes into it (-45 resident bytes a course), and so do the
  packed titles.
- **The `bz_boxbuf` bss overlay:** -170 bytes of RAM, any time.
- **The platform sprite**, once a shared part exists: -313.
- **The RAM levers for long courses** (wave 11, before the first course
  over about 70 s; section 6):
  - grid rows overlapped (PEAK -788 of RAM, 0 clk);
  - map rows at a constant stride with a row-base table (PEAK -2.4KB,
    0 clk or less).
- **LZB for the parts** (the owner's call, after 5b): -8,188 more on the
  shortlist form, about +0.9 s on PEAK's launch.
- **Rendering the picture at load** (a prototype, wave 10 or before world
  3): about -19KB more, at about 1.9 s of PEAK's load and a second
  renderer to keep exact.

**No:** A, B, E on their own, G (shared masks), the SoA layouts, joined
balls, parity copies held once in the heap, shared code runs, generated
physics tables, per-row map overlap, joined songs, prop ghosts in the
picture, cutaway walls drawn low, and the dither done at run time.

**The instruments** are the owner's call. Without them play gets faster
and the image smaller, but B, D and three rows depend on them. The
middle step, an early exit in `bz_mark` while not measuring, costs 6 bytes
and saves about 1k clk a frame (PREDICTED).

## 6. Long courses: RAM is the wall (PREDICTED)

**The model.** From MOON and PEAK:
- par pace is 0.373 s a block row, and the demo pace 0.306;
- PEAK spends 381 bytes of RAM a block row (map 128, occluders 200, grid
  53), on top of about 10.2KB fixed;
- one part is at most 65,024 bytes.

The model is proportional. It ignores that blocks and masks grow more
slowly than rows, so long courses are slightly overstated.

| RAM form | bytes a block row | rows in one part | at par pace |
|---|---|---|---|
| today | 381 | 144 | 54 s |
| with D | about 281 | about 195 | **about 73 s** |
| D, grid rows overlapped, map at a constant stride (both 0 clk) | 258.5 | 212 | 79 s |
| that, with map rows overlapped per row (+15-25 clk a block row stepped, REJECTED) | 242.5 | 226 | 84 s |

**What a 90 s course needs** (241 block rows at par pace):
- with every 0-clock lever it is about 72KB, still over one part;
- so it must be designed at a SLOWER pace, at least 0.425 s a block row
  (MOON is at 0.394; FIRST at 0.12);
- or the grid goes into a claim of its own, which takes the eighth of
  eight claims;
- or the course becomes two segments.

A 60 s course (161 rows) fits with D alone.

**A second wall: the replay log.** `bz_rlog` is 4,096 bytes, which holds
2,040 key runs or 1,360 TILT runs. A 90 s course is about 4,900 steps. A
mouse play whose tilt byte changes nearly every step would truncate its
demo after about 25 s (PREDICTED; not measured on a real play). Keyboard
plays are far from the limit. **Check it before the first long course**
(wave 7 or 11).

## 7. Twenty courses on a 360KB disk (PREDICTED)

**Per course.** This is proportional to MOON's and PEAK's packed bytes a
block row: 260 rows, at par pace. KiB = 1,024 bytes.

| form | bytes a row | 30 s (80 rows) | 60 s (161) | 90 s (241) | the set: 6 x 30 s + 9 x 60 s + 5 x 90 s (3,134 rows) |
|---|---|---|---|---|---|
| today | 160.1 | 12.5 KiB | 25.2 | 37.7 | **490 KiB** |
| today, LZB parts | 124.5 | 9.7 | 19.6 | 29.3 | 381 |
| D alone | 91.3 | 7.1 | 14.4 | 21.5 | 280 |
| the 5b shortlist without G | 85.7 | 6.7 | 13.5 | 20.2 | 262 |
| **the 5b shortlist** | **82.7** | **6.5** | **13.0** | **19.5** | **253** |
| **the shortlist with LZB parts** | **67.4** | **5.3** | **10.6** | **15.9** | **206** |

**Against the plan's R4 budget.** R4 leaves about 217 KiB for twenty
courses, after code, demos, songs, the pathway, the front art, the family
parts and 10% slack. The non-course items measured here give some of that
back:
- demos as a bit stream: about +10.5;
- ball V2: about +5.4;
- BENCH at 6.9 rather than 10: about +3.1;
- LZB for the image: about +3.2.

That makes **about 239 KiB** for the twenty courses.

| with... | courses need | fits? |
|---|---|---|
| today's format | 490 KiB | no, by about 250 KiB |
| the 5b shortlist | 253 KiB | **no, about 14 KiB over** |
| the shortlist, LZB parts | 206 KiB | **yes, about 33 KiB spare** |
| the shortlist, and the five 90 s courses designed at 0.425 s a row, 212 rows each (as RAM requires anyway) | about 241 KiB | about 2 KiB over |
| the shortlist, with the picture rendered at load | not measured in combination (the course agent's figure with the plan's records: 66 bytes a row, about 202 KiB) | probably yes, at about 1.9 s of PEAK's load and high risk |

**So:** the shortlist does most of the work, but one large lever is
still needed. LZB for the parts is the cheapest and lowest-risk one, at
about +0.9 s on a long course's launch. Rendering at load is the larger,
riskier one. The fallback that needs neither is R4's second "Worlds"
disk. **The owner decides after 5b.1's `--sizes` reports the real
figures.**

## 8. Recommendation on visibility

The owner's note: *"our mechanics need to be visible."* Take the
following.

**(c) as a binding tool rule in the course pipeline:**
- every spring, pad and cup at least 75% visible;
- every tube mouth at least 50% visible;
- no hidden stretch of the route over 0.5 s unless the course declares it
  `hidden`, and a declared one must be nearly straight.

The rule costs nothing on the 5150. It reports at first, and starts to
refuse once PEAK and MOON are redesigned.

**(a)'s dither as the safety net.** It costs 0 clocks and 0 guest bytes,
and it makes the parts 710 bytes smaller packed. The ball is then never
wholly invisible.

**Two design rules:**
- Springs, climbs and tube runs go away from the camera.
- A near rail stands one or two units above the floor it guards.

**PEAK's end is fixed first.** Its x = 57 rail lowered to one or two units
above the green makes the cup and the pad 100% visible. The four rail
changes measured on a scratch copy cost +1,234 packed. Cutaways and
run-time see-through cost clocks or lie about the physics, and are
refused.
