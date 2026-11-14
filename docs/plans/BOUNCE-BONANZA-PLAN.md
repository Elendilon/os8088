# BOUNCE BONANZA — an isometric rolling-ball game for the 5150 (investigation and plan)

**STATUS: WAVES 0 TO 4 DONE AND MEASURED; THE REGROUP TOWARD A RELEASE IS
NEXT (2026-11-14).** Wave 0 (the spike) was a GO (the owner, 2026-11-12:
"we are good to continue"). Since then, each with its SPEC.md section:
- wave 0b, the camera (SPEC.md 128.9);
- wave 1, the text course and physics v1 (128.10);
- wave 2, feel: three balls, replays (128.11);
- wave 3, obstacles and the wheel (128.12);
- wave 3b, the performance round (128.13);
- the SOUND, built beside them by another session (128.20);
- wave 4, a game: the tour, flags, pads, springs, the cup, demos on the
  disk, the mouse as a tilt stick, MOON and PEAK (128.14). Its HUD did not
  fit the frame and was removed. Its measured results and open items are
  128.14.26-27.

**What comes next is [Toward a release](#toward-a-release)**, the roadmap
built on the owner's end goal and eight further decisions of 2026-11-14.
Waves 5a to 15 make release 1: course clocks and time limits, the per-ball
physics with one boost, the course pathway with several finish lines and
lives, mechanics scoped to the courses that use them, a performance wave,
the tutorial, two worlds and the machines. Worlds 3 and 4 follow in
release 2. It supersedes this section 11's old wave 5 and wave 6 lists and
its "Next" list. **The next step is wave 5a, with the owner playing the
wave 4 disk beside it (gate 0).** The owner's earlier decisions are in
section 12, and the open questions are in R7.

The package is `BONANZA` (`apps/bonanza/`). Below is the
investigation as it was written, the answer to the owner's
brief of 2026-11-12, on branch `bounce-bonanza`, cut from `elendilon`: is an
overhead isometric rolling-ball game with a scrolling course feasible on the
IBM 5150, which tricks does the scrolling need, how do we make the ball look
3D, how do animated obstacles stay cheap, and what else could the game do?
**Bounce Bonanza** is the title, and `BONANZA` the package (section 12). Every figure here is
**PREDICTED** from measured unit costs unless it says otherwise. The
emulated-XT spike in section 11 (wave 0) is what turns those predictions into
measurements. Nothing here has been run on a 5150.

The brief, condensed:

- **View and scrolling.** Overhead isometric, and the course scrolls,
  probably with hardware tricks. Vertical scrolling only, as in 1942, is
  acceptable. Plan both directions if that is feasible.
- **The ball.** It is the player. A rolling texture should make it read as
  3D, done with frames in the way *Extreme Pinball* did, not with 3D maths.
- **Obstacles.** Mostly built into the level, with 2–6 animated at a time,
  paced by TITHE's wheel (SPEC.md 125.5 on `tithe-new`).
- **Course props.** Mini-golf style, including props the ball enters and is
  spat out of, some with momentum.
- **Feel.** Physics more fluid than Marble Madness's stiff controls. This is
  not a clone of its mechanics or its style.
- **Ideas.** Suggest other mechanics that suit the style and are plausible on
  a 5150.

The prototype pictures referred to below are in
[`bounce-bonanza/`](bounce-bonanza/). They were made by `ballproto.py`, a
host-only script that `make` does not use and that ships nothing.

---

## Toward a release

*The roadmap of 2026-11-14, written at HEAD `36fee621`. It supersedes
section 11's old "Wave 5: the machines" and "Wave 6: the picks" lists and
its "Next, after the owner plays wave 4" list. Each of their items now has
a home below (R9), and the old lists stay in section 11, marked
superseded.*

This section is the plan from the end of wave 4 to a first release. It is
built around two things:
- the owner's END GOAL of 2026-11-14 (the diary has it verbatim);
- the owner's EIGHT FURTHER DECISIONS of the same day, which bind it (R1).

It was drafted from an inventory of everything still open in this plan,
SPEC.md 128, the diary and the sound plan. Three reviewers then read the
draft for the engine, the game design and the scope. They returned 49
findings; R10 says which were taken, which were taken in part, and which
were rejected.

Figures are marked:
- **MEASURED**: from SPEC.md 128's rows, or measured host-side at
  `36fee621` by a scratch script (not a row) over the tool's own parts.
- **PREDICTED**: arithmetic.
- **SUGGESTION**: the planner's idea, not the owner's; R8 collects them.

No SPEC.md section is written here. Each wave writes its contract into
SPEC.md 128 before its code, as waves 1 to 4 did.

### R1 The owner's decisions this roadmap is built on

**The end goal (2026-11-14):**
- No time carry-over.
- LIVES are timeouts: running out of time ends the course, takes a life
  and returns to the course pathway.
- A fullscreen COURSE PATHWAY (Star Fox's galaxy map as a concept, not a
  style). Some courses have several finish lines; the one taken picks the
  next branch, and branches may join back up. The pathway may show a HUD.
- The first two or so courses do not branch: they are the tutorial,
  learned by playing.
- About 20 courses in all, about 10 needed to finish, built one at a time,
  with more props, refined current ones, new surfaces and challenges.
- Physics per ball:
  - RUBBER sticky: medium acceleration, good grip, the double bounce.
  - STEEL sluggish: slow acceleration, immune to traps that shatter glass
    or fling rubber, may sink in WATER.
  - GLASS fragile, light and fast: fast acceleration, very little braking
    grip.
- A better window before the game: one artwork, the few setup options,
  the keys.
- COURSE CLOCKS on the course instead of a HUD, counting down a TIME LIMIT.
  An EXPLORATION mode in the first release turns the timing off.
- A CGA PALETTE per course.
- A PERFORMANCE wave, later, not immediately.
- Course tuning after the owner plays.
- Suggestions are invited.

**The eight further decisions (2026-11-14), binding:**

| # | the owner's decision | where it lands |
|---|---|---|
| 1 | **At most ONE boost.** "Otherwise every course with rubber becomes a jump timing challenge, followed by flying over any obstacles we make. I just want a unique mechanic, not a flying ball." | Wave 6, story 6.2: one "and again" per Hop, a fixed capped apex, level floors only |
| 2 | **Space and Shift mean the same for every ball**: Space = Hop, Shift = brake (Grip), as today. Only the AMOUNT differs: rubber a decent jump with its "and again" second, higher bounce; steel today's tiny hop; glass in between. Braking grip as in the end goal: rubber good, steel moderate, glass very little | Wave 6, stories 6.1 and 6.3. This settles the inventory's B3 (no per-ball meanings for Space) |
| 3 | **Disk size: reuse a TILE AND PROP MAP across courses**, built out at load time. The owner asks whether this works, or whether there is a better idea | R2 answers it with the tool's numbers. Waves 5b and 9 |
| 4 | **Medals: yes**, as a "completed" icon or medal beside the course's icon on the pathway | Wave 8c, story 8c.3 |
| 5 | **Pickups: yes**: an hourglass (time), and timed pickups such as speed or jump height, "carefully, to not break a course; that will be a theme in course design" | Wave 9, story 9.3, with the tool's proofs |
| 6 | **Hidden finish lines: yes**, with careful course design | Wave 8b, story 8b.4 (`hidden`) |
| 7 | **Ghost: only if affordable.** Measure it | Wave 10, story T12, a one-off measurement |
| 8 | **Traps and more props and tiles**: wind, magnets, cracked tiles, water, DISAPPEARING GLASS PATHWAYS (a slight hint, then it appears when rolled onto), "and more of these". They must NOT cost the whole disk or the 64KB segment: SCOPE them to the courses that use them, and LIMIT how many one course may use | Wave 9's family framework and per-course limits; the families land with their worlds (waves 12, 13, 16, 17) |

**The owner's course-design notes (2026-11-14), binding on waves 11-13,
16 and 17 and on the course pipeline.** The diary has them verbatim.

- **CD1. Mechanics must be VISIBLE.** "Our mechanics need to be visible,
  and not have the viewer guessing about what is going on hidden." A
  hidden route is acceptable only as a deliberate SECRET (a hidden finish,
  decision 6).
  - Today every spring is completely hidden, and the owner could not find
    PEAK's end. MEASURED in
    [BONANZA-SIZE-2026-11-14](../reports/BONANZA-SIZE-2026-11-14.md)
    section 3.5:
    - PEAK's two springs, its rubber pad and its cup are 0% visible. The
      cup sits behind the x = 57 rail, 4 units above the green.
    - PEAK's drop tube mouths are 0% visible, and so are two of MOON's
      tube INs.
    - The ball is more than half hidden on 475 of PEAK's 1,902 route
      steps, 3.00 s of them in one stretch.
  - The owner offered two remedies: see-through tiles "if that is not too
    expensive", or, if it is, courses where a hidden ball goes mostly
    straight or plainly somewhere. Both are taken, at 0 clocks a frame:
    - story 11.5's tool rule and design rules;
    - story 5b.6's ghost dither.
- **CD2. INCREASING CHALLENGE.** The tutorial's and world 1's courses
  help the player, and later courses take the help away. For example:
  - early ramps guide the ball to the CENTRE, and later ones throw it to
    the edge;
  - later, the player needs speed to FLING the ball across a pit, onto a
    ramp that ends in a drop hole.
  - Each design sheet (wave 11's pipeline, step 1) names its place on
    this curve and the one new demand it makes.
- **CD3. LONGER COURSES.** About **30 s** for the early courses, **60 s**
  for the middle ones and **90 s** for the last few. This is why the
  course format must shrink (wave 5b), and why RAM, not the disk, becomes
  the wall:
  - one part holds about 73 s at MOON's and PEAK's pace with wave 5b's
    4-byte records;
  - so a 90 s course needs wave 11's RAM levers AND a slower pace, at
    least 0.425 s a block row, or the grid in a claim of its own (the
    report's section 6).
  - Each design sheet states its target time and its pace, and `--sizes`
    prints both against the part and the disk.
- **CD4. Q-61 to Q-63's defaults are the starting point.** "I'll need to
  test these to see how they feel, but this seems like a fine starting
  point." Wave 6 ships them as the defaults, and gate 1's play tunes them.

### R2 The disk question: a shared tile and prop map?

**The short answer.** Building a course out at load time is the right
mechanism, and it keeps every writer unchanged. That was wave 1's whole
objection to metatiles, which put a second lookup per block per row into
the WRITERS. But the tile map aims at the smaller part of a course. Most of
a course's bytes are its OCCLUDER RECORDS, and those can be built out at
load time too, for about seven times the saving.

**Where a course's bytes go on the floppy** (MEASURED: all six parts, each
section packed with LZ4 on its own, so a row does not sum exactly to its
total):

| course | packed | occluder index and records | masks | blocks | map | grid | props |
|---|---|---|---|---|---|---|---|
| BENCH | 17,930 | 12,558 | 478 | 1,801 | 1,459 | 1,694 | 0 |
| FIRST | 3,040 | 1,383 | 204 | 704 | 448 | 335 | 0 |
| TRIAL | 6,614 | 3,478 | 279 | 1,451 | 925 | 518 | 0 |
| MILL | 13,937 | 6,201 | 391 | 4,054 | 1,739 | 990 | 652 |
| MOON | 17,982 | 11,248 | 586 | 2,453 | 2,020 | 1,493 | 217 |
| PEAK | 23,649 | 14,388 | 654 | 3,485 | 2,636 | 1,943 | 623 |
| **all six** | **83,152** | **49,256 (59%)** | 2,592 | **13,948 (17%)** | 9,227 (11%) | 6,973 (8%) | 1,492 |

**The three forms the owner's question names, priced:**

- **(a) As today.** 83.2KB for six courses. The five play courses average
  12.9KB packed, and the newer ones are 18-24KB. Twenty courses like MOON
  and PEAK come to about 360KB of courses alone. That does not fit a 360KB
  floppy.

- **(b) A shared TILESET per world**: blocks, mask templates and prop art,
  with each course a map of tile indices, its grid, its records and its own
  unique tiles, expanded at load. MEASURED:
  - Only 224 of the 1,413 distinct 8x8 blocks appear in more than one
    course.
  - The share of each course's blocks that no other course uses: FIRST
    25%, MILL 63%, PEAK 87%, TRIAL 95%.
  - A pool shared by all six courses packs to 9,962 bytes, against 13,948
    packed separately: **3,986 bytes saved, 4.8% of the six parts**.
  - Map words as tile indices instead of absolute offsets save about 270
    bytes in all.

  The reason is that a block is cut from the COMPOSITED picture, where
  tile edges, 4 px height steps and neighbours overlap. Two courses share a
  block only where their geometry is identical. A world drawn from a small,
  deliberate vocabulary would share more, but even perfect sharing saves at
  most the blocks' 17%.

- **(c) The course as compact geometry, rendered and its occluders built
  ON THE 5150 at load.** REJECTED. MEASURED: the tool takes 0.43 s for
  FIRST, 2.4 s for MILL and **15.1 s for PEAK** on this host. Most of
  PEAK's time is the occluders' reachable-set analysis and the trap check;
  the picture alone is under 1 s.
  - CPython on this host against hand-written 8086 code on a 4.77 MHz 8088
    is a factor of several hundred. That predicts minutes per course for
    the picture alone, and an hour or more with the occluders (PREDICTED).
  - PEAK's raw picture before deduplication is 64 x 2 x 1,064 = 136KB,
    more than a 256KB 5150 has free during play.
  - The occluders depend on the reach model, so the guest would need a
    second implementation of the tool's reach, with a cross-check of its
    own.

**The better idea: (b-prime), build the OCCLUDER RECORDS out at load
time.** Today a record is 8 bytes in RAM and on the disk. On the disk it
can be 4:
- a column delta within the block row;
- `s_C - s_min`;
- `top - top_min`;
- the mask index;
- with a count of records per block row in place of `OCCIDX`.

All six courses fit these fields losslessly (MEASURED: `s_C` spans at most
103, a top at most 208 and the masks at most 122, so a byte each).

What it buys and costs:
- **Disk.** Stored structure-of-arrays, chunked per block row, the records
  pack to 20,490 bytes against 49,256: **-28,766 bytes, -35% of all six
  parts**. Per course: FIRST 2,385, TRIAL 4,740, MILL 10,230, MOON 11,298,
  PEAK 15,727, BENCH about 10,000. The play courses drop from 12.9KB to an
  average of 8.9KB. These figures pack each section on its own; story 5b.1
  replaces them with the real part's packed size (see the layout below).
- **RAM.** Unchanged. The expansion writes today's BZC1 bytes exactly,
  byte for byte, so no writer, no compose and no row changes.
- **Identity.** Unchanged too, because the course identity (SPEC.md
  128.12.8) is computed over the expanded part. The shipped demos and the
  players' bests survive the change.
- **Code.** About 150-250 bytes, launch-only (PREDICTED).
- **Load time.** About 50-80 clk a record: PEAK's 3,289 records take about
  0.2M clk, **about 0.04 s**, against its 3.9 s launch (PREDICTED).

**The layout has to follow how a part is claimed** (SPEC.md 20.12.7, a
review finding). `op_fetch` cuts the claim from the row's `len`, the
UNPACKED size, and leaves no spare tail. The compact records cannot use a
second claim either: PEAK's play leaves about 20.5KB free, against a 60.8KB
part plus about 15KB raw. So:
- the part's `len` is the full BZC1 size;
- the compact records sit at the part's TAIL;
- the bytes in front of them are zeros, which an `OP_ZFILL` row (SPEC.md
  20.12.7.5) ships as a hole rather than on the disk;
- the expander runs forward from the start of the occluder area, reading
  the compact records off the tail.

A writer that writes 8 bytes per 4 bytes read, with the reader starting 4
bytes per record ahead, never passes the reader. That is the proof, and
`--selfcheck` asserts it. On the Hercules the expansion runs before
`bz_hxlat`.

**Superseded by measurement (2026-11-14):**
[BONANZA-SIZE-2026-11-14](../reports/BONANZA-SIZE-2026-11-14.md) measured
the records inside the WHOLE packed part, and the structure-of-arrays
layout above is not the best form.
- Records stored IN PLACE as word DIFFERENCES from the record before pack
  far better, because the column steps by 0 or 1 about 95% of the time
  and LZ4 then matches whole records.
- On today's 8-byte records this saves -32,616 bytes packed at 0 clk a
  frame.
- With 4-byte records kept in RAM as well, it saves -35,379 packed and
  13,156 bytes of PEAK's RAM.
- With the four small items in wave 5b, all six courses go from 83,152 to
  42,792 bytes packed.

Wave 5b's stories follow the report.

**Recommendation:** take (b-prime) now, in wave 5b. Keep (b)'s world block
pool as an option for when worlds exist and their art is drawn from a
deliberate vocabulary. It layers on top of (b-prime) for its 5%.

**The first step is host-only**, before any guest change. Story 5b.1 is
`bbcourse.py --sizes`, which turns the scratch measurement into the tool's
own report. For every course it prints:
- each section raw and packed;
- the real padded part packed with the row's own `OP_COMP` format (LZ4 or
  LZB) and `OP_ZFILL`;
- the world pool's saving;
- the running disk total against R4's plan.

`--selfcheck` then checks `expand(BZC2) == BZC1` byte for byte for every
course, still on the host. The guest's expander comes after that.

**And the owner's other half: props and mechanics scoped to the courses
that use them.** Today's props are already scoped for their ART: a prop's
lanes and blocks are rendered by the tool into the course's own pool, so a
windmill costs nothing on a course without one. What is not scoped is CODE:
every prop's rules are resident in the image. Wave 9's FAMILY framework
scopes the code:
- a family's rules are a code part the course declares and the launch
  fetches;
- physics reaches it through a small hook table, so an unused family costs
  no image bytes and nothing per step;
- the tool's model mirrors it behind the same hooks;
- a course may use at most three families (R4).

### R3 The waves at a glance

Sizes are relative: S < M < L < XL, and wave 4 was an XL. A **gate** is an
owner play; R5 says when the scoped soak runs.

| wave | goal | size | gate after it | release |
|---|---|---|---|---|
| **5a** | Clear the decks: the dead HUD code and the stale records | S | gate 0 runs beside it | 1 |
| **5b** | The compact course format BZC2, the course budget, the disk plan | M | | 1 |
| **6** | Feel: per-ball Hop and grip, one boost, the palette, a playground course | M-L | **gate 1: the physics freeze** | 1 |
| **7** | Time: the walk narrowed by column, course clocks, time limits, music per course, the new sound events | L | | 1 |
| **8a** | The shell's code part (O46), proven on kern_mega | S-M | | 1 |
| **8b** | The loop: one bracket, the pathway, several finishes, lives, save v2, the tour removed | L | | 1 |
| **8c** | The front window, exploration, medals, intro and result cards, the pause overlay | M | **gate 2: the shell** | 1 |
| **9** | Mechanics as parts: the family framework, the per-play state contract, pickups | L | | 1 |
| **10** | Performance (the owner's "later"), the ghost measured | L | | 1 |
| **11** | The tutorial (FIRST and TRIAL rebuilt) and the course pipeline | M | gate per course | 1 |
| **12** | World 1, one course at a time | L | gate per course | 1 |
| **13** | World 2, with MOON and PEAK retrofitted as its two finales | L | gate per course | 1 |
| **14** | The machines (the old wave 5) | M | | 1 |
| **15** | Release 1 | M | **gate 3: the field run** | 1 |
| **16** | World 3 | L | gate per course | 2 |
| **17** | World 4, and release 2 | L | gate per course | 2 |

**Release 1 (SUGGESTION; the owner decides, Q-R1)** is waves 5a to 15:
- the tutorial and worlds 1 and 2, about 10-12 courses;
- a pathway that can be finished in about 8-10 courses;
- exploration mode;
- the machines.

Worlds 3 and 4 then join through the pathway graph in release 2. Story
8b.4 maps (course, exit) to the next node, so a later world is wired in
without rebuilding a shipped course. The owner's "about 20 courses, about
10 to finish" is the END state, and release 1 does not wait for it.

**The owner gates:**
- **Gate 0:** the owner plays the wave 4 disk while waves 5a and 5b run.
  Those two waves need nothing from the owner. Ball feedback goes into
  wave 6's retune. Course feedback (PEAK's O54, "the rest") is recorded
  and applied after the freeze, at each course's retrofit.
- **Gate 1:** after wave 6, the physics on the playground course. Freezing
  O11 here is what lets demos be recorded.
- **Gate 2:** after wave 8c, the shell.
- **Per course** in waves 11-13, 16 and 17: a playtest disk.
- **Gate 3:** before release 1, a field run on the 5150s.

### R4 Budgets: the frame, the disk, RAM, claims and the image

**The frame.** A CGA refresh is 4.77 MHz / 59.92 Hz, about **79.6k clk**.
Busy mean per frame and misses (MEASURED, SPEC.md 128.14.26, through `D`,
HUD off):

| demo | CGA, speaker OFF | CGA, speaker ON | Hercules OFF | Hercules ON |
|---|---|---|---|---|
| FIRST | 3 misses, 42.5k | 5, 47.7k | 0, 44.7k | 0, 48.6k |
| TRIAL | 8, 47.3k | 12, 51.7k | 2, 49.8k | 9, 54.6k |
| MILL | **47, 53.5k** | **151, 61.2k** | 12, 55.8k | 19, 59.4k |
| MOON | 16, 44.2k | 48, 47.6k | 10, 46.9k | 23, 50.8k |
| PEAK | **205, 56.0k** | **293, 60.9k** | 60, 58.0k | 96, 61.9k |

**Unit costs** (MEASURED):
- One ball-sized box of 16 lines on the CGA: fill about 4.5k, write about
  4.7k, sprite and shadow about 5.5k. The box's fixed cost is 1.6-2.1k in
  each of the compose and the write.
- A rotor's commit pass: **8.9k**. The wheel's preparation outside
  `bz_wprep`: **5.6k**.
- The walk: about 0.2k per lane per frame while the lane is in the
  window's rows.
- Speaker sound 3.3k average and 13.4k worst; AdLib 6.4k average and 29.9k
  worst.

**The HUD is the precedent.** Its REST mode was predicted at 0-3 extra
misses on MILL and measured at **+65**, because its costs landed on the
frames that were already full. So every new per-frame cost is judged on
MILL's and PEAK's heavy frames, measured on that course's demo, against the
owner's HUD rule: **at most 2 more misses a card with the speaker on.**

| feature | per frame (PREDICTED) | occasional | verdict |
|---|---|---|---|
| palette per course | 0 | one OUT to 3D9h at each course's start | fits |
| time limit, counted in steps | about 20 clk a step | none | fits |
| course clock (wave 7) | 0.2k walk in the window's rows today; 0 off the window's columns after story 7.1 | a lane commit, once a second, priced at a rotor's pass and preparation (about 8.9k plus a share of 5.6k), which the wheel may defer a frame or two | fits only with 7.1 first, and must be measured on MILL and PEAK (7.7) |
| pickup | 30-60 clk a step (a cell flag test) | a collection: a lane commit next to the ball, so a CONTACT-box frame | fits; priced as a contact frame |
| family dispatch | about 0 unused (a bit test); about 0.1k per active hook per step (a far call) | none | fits |
| wind | 0.1-0.2k a step in its region | streak lanes, wheel-paced like a rotor | fits; each lane counts against the 6 per window (O24) |
| magnet | 0.3-0.5k a step in range | none | fits |
| cracked tile, glass reveal | about 30 clk a step | a lane commit next to the ball: a contact-box frame (SPEC.md 128.12.4.2), competing with springs, bumpers and the lift | fits once red arm `contact` has its scene; the tool bounds how many can meet one window |
| rubber's boost | about 50 clk at a contact | none | fits; the bytes and bounds are priced by the tool (6.5) |
| **a full GHOST sprite** | **+12-15k** (one more box); and two more footprints in a frame bounded to four boxes; and every box keeps lanes from committing, so rotors and clocks run late | none | **no on MILL and PEAK's CGA frames** (the mean would reach 73-76k of 79.6k with the speaker on). Wave 10 measures it (T12) |
| pathway, front window, save | 0 (not in the play frame) | none | fits |

**The disk** (MEASURED today): `BONANZA.O88` is 125,162 bytes, **130 of
`bonanza360.img`'s 354 clusters**. Of that, the courses are 83.2KB packed
(BENCH 17.9KB), the balls 7.4KB, the sound 4.9KB, the demos 1.6KB and the
image and table about 28KB.

**Twenty courses on one 360KB floppy, in the compact form** (PREDICTED,
BENCH kept, see Q-L2):

| item | KB |
|---|---|
| code, balls, sound, README, APPDATA, ASSOC | about 45 |
| BENCH, compact | about 10 |
| demos, one or two per course (20 x about 1KB) | about 20 |
| new songs (about 8 x 0.7KB) | about 6 |
| the pathway part | about 6 |
| the front window's art | about 3 |
| family code parts | about 12 |
| slack (10%) | 35 |
| **left for 20 courses** | **about 217: 10.8KB a course on average** |

The five play courses already average 8.9KB in the compact form. So the
plan is:
- **one 360KB play disk;**
- **a per-course budget of about 10.5KB packed on average, a little
  under the 10.8KB available, and at most 16KB for any one course**
  (PEAK-class);
- the tool prints the budget and refuses past it (5b.3), as it refuses a
  part over 65,024 bytes. It is a design input, like the frame.

With today's encoding, the same 10.8KB would hold only courses smaller
than MILL (13.9KB today; PEAK is 23.6KB).

**Restated for the owner's longer courses (CD3; the report's section 7,
PREDICTED).** Take a set of six 30 s courses, nine 60 s and five 90 s, at
MOON's and PEAK's pace:
- In today's form it needs about 490 KiB.
- In wave 5b's form it needs about 253 KiB, against about 239 KiB
  available. That 239 is this table's 217, plus what the demo bit stream,
  ball V2, a smaller BENCH and LZB for the image give back. So it is
  about 14 KiB over.
- With LZB for the parts as well, it needs about 206 KiB and fits.

So the shortlist does most of the work, and one large lever is still the
owner's choice after 5b.1 reports the real figures:
- LZB for the parts, at about +0.9 s on a long course's launch;
- rendering the picture at load (high risk);
- this section's "Worlds" disk.

The 10.5KB-average and 16KB-maximum budget above was set for today's
course lengths. 5b.3 re-derives it from the target times.

**The fallback, if the budget breaks:** a world's courses as hostile-read
files on a second "Worlds" disk, with a disk swap at a world gate on the
pathway. O1's price: about 1KB of resident code and about 0.13 s a load
(PREDICTED). It is not recommended unless needed. `games360.img` is not a
venue, because 130 clusters or more is too large a share of it. BONANZA
keeps its own disk in all four geometries, and only the 360KB one binds.

**RAM** is unchanged by BZC2, which expands to today's form. PEAK's play
leaves about 20.5KB free on a 256KB 5150 (A18), and PEAK's part has 4,168
bytes left under 65,024. **Waves 7 to 9 each report PEAK's free RAM and its
part's headroom**, because clocks, the pathway and families all spend from
them. A SUGGESTION for wave 10 (T10): 4-byte records in RAM as well.

**Claims** (a review finding). `MEM_OWNER_MAX` is 8 on kern_big
(`kernel/memory.inc`) and 12 on kern_mega. A play already holds SEVEN
(SPEC.md 128.14.11): the region, the course, three balls and the sound's
two. So:
- **all of a course's family parts go into ONE claim** (8 of 8);
- the three ball parts move into one carved claim in wave 9 (story 9.1),
  which gives two back;
- the shell's code part (8a) and the pathway part (8b) are **dropped
  before a course is fetched**.

The tool and the framework state the count, and wave 9 adds it to the
per-course limits.

**The resident image** (SPEC.md 128.14.26 item 9): 32,640 bytes today,
grown from 27,421 at wave 3b. Twenty courses add about 31 bytes each of
names and titles, plus part rows for courses, demos, songs and families:
**about 1-1.5KB resident** (PREDICTED). Wave 10's T9 is restated as a byte
budget that includes it. Wave 8a's code part takes about 7-8KB of
launch- and desktop-only code out of the image first. Re-measured on
2026-11-14 (BONANZA-SIZE-2026-11-14 section 3.3), that is about
5.6-5.9KB: the other 2.7KB is code that runs once a launch inside the
bracket, and it stays resident.

### R5 Process, for every wave

These follow CLAUDE.md's waves and testing rules:
- Each wave writes its contract into SPEC.md 128 before its code, and keeps
  the diary.
- Each batch verifies on the host (`make`, `make KERN_SMALL=1`, the image
  figures, `bbcourse.py --selfcheck`) and NAMES the rows it reaches.
- **The scoped soak of the BONANZA rows runs at the merge points, not per
  wave:** before gate 1 (after wave 6), before gate 2 (after 8c), after
  wave 10, and at release 1. Each runs the deduplicated union of the rows
  the waves since the last pass reached, and every red arm they touched,
  once.
- **`test-full` runs when major work merges to `elendilon`**: at gate 2
  and at release 1.
- The whole soak tier is never run unless the owner asks for it.
- A number that DECIDES a design (the clock's form, the boost's apex, a
  course's chain easing) is taken once, by the agent choosing, and written
  in its report.
- `bonanza360.img` and `bonanza.img` are sent after every commit that
  changes their content (fork rule 3: the work's own disk).

### R6 The waves

#### Wave 5a: Clear the decks (S)

**Goal:** remove the HUD's dead code and bring the records up to date.
Host work and row edits only; no change to the package's bytes.

| # | story | verified by |
|---|---|---|
| 5a.1 | The dead HUD code leaves the rows: about 243 references in `bonanza_ring.py`, `bonanza_perf.py`, `bonanza_wheel.py`, `bonanza_game.py` and `bonanza_mega.py`, and the eight self-skipping red arms (`hudinset`, `hudold`, `hudlane`, `hudfull`, `hudon`, `hudhold`, `hudtime`, `hudrect`). `tests/suite.py`'s row texts lose the HUD legs (I1) | `os88test.py --check`; the rows import; one scoped run of the five rows at the next merge point |
| 5a.2 | `bbcourse.py`'s "NOTHING UNDER THE HUD" refusal is removed (`hud_conflicts`, `HUD_COLS`, `HUD_LINE`): it refuses layouts under a panel that no longer exists (I2) | `--selfcheck`; a course placed under the old panel compiles; every shipped part byte for byte unchanged |
| 5a.3 | The records: `apps/bonanza/README.md`'s stale tail (I3), `apps/RETIRED.txt`'s "wave 0" comment (I4), docs/HEAP-CLAIMS.md's course-part row with MOON and PEAK (I5) | `checkdocs` |
| 5a.4 | The plan's ticks: wave 5's kern_mega, the refusals and the four geometries are DONE in practice (H2-H4, with `bonanzamega`'s and the Makefile's evidence); 3.12 and 3b.10 closed with pointers (A6, A17); wave 0b's leftovers (I13) recorded as resolved | `checkdocs` |

**Rows reached:** `bonanzaring`, `bonanzaperf`, `bonanzawheel`,
`bonanzagame`, `bonanzamega`, `bonanzacourse`.

#### Wave 5b: The compact course format and the disk plan (M)

**Goal:** a disk format sized for twenty LONGER courses (R2, CD3), and the
RAM to hold them.

**The measurement this wave follows:**
[BONANZA-SIZE-2026-11-14](../reports/BONANZA-SIZE-2026-11-14.md), taken
host-side at `28b13cce` after the owner asked "what else is smaller but
does the same thing at the same speed". Its section 5 is the shortlist,
and the stories below are that shortlist. The six courses, measured
together: **83,152 -> 42,792 bytes packed (-48.5%)**, and RAM 223,420 ->
179,608.

| # | story | verified by |
|---|---|---|
| 5b.1 | `bbcourse.py --sizes`. It prints, for every course: each section raw and packed; the real padded part packed with its row's `OP_COMP` format and `OP_ZFILL`; the part's RAM against 65,024; the course's target time and pace (CD3); and the disk total against R4's plan. Its figures replace the report's and R2's in SPEC.md 128 | host; the figures match the report's section 4 within a few bytes |
| 5b.2 | **BZC2: the occluder records as word DIFFERENCES, in place** (the report's idea D). The 4-byte record `[col, s - br + SB, top - TB, mask index]` is kept in RAM. On disk each record is stored as the word difference from the record before it. OCCIDX ships as one count byte a block row. The load runs `rec[i] += rec[i-1]` (a 10-byte loop, 115 clk a record: PEAK 81 ms) and rebuilds OCCIDX. `bz_occ`, `bz_oand` and the binary search read the 4-byte records, through a 2 x NMASK word table of mask offsets. **Cost per occluder frame: about +30 clk typical, about +450 at the worst reachable position (ESTIMATED; 0 on frames where the gate is closed and 0 a step).** BZC2 has a **tagged section directory**, so waves 7 to 9 add sections (finishes, families, the per-play state list) additively. Non-physics settings (palette, song, clock frame, limit, medal times) live in the package's course table OUTSIDE the part. **The fallback is idea C**: the same disk form expanded into today's 8-byte records, at exactly 0 clk a frame and -32,616 packed, with the RAM half left to T10 | `--selfcheck`: the in-place decode equals the RAM target byte for byte on every course, and SB is checked against the tool's reach queries. One `bonanzacourse` leg reads the guest's expanded claim against the tool. **`bonanzaperf` on MILL's and PEAK's demos, both cards, speaker ON: at most 2 more misses a card (the HUD rule), or ship C.** Red arms: an expander off by one record, and a missing mask-table entry |
| 5b.3 | **The small course items**, expanded at load into the same RAM bytes, at 0 clk a frame and a step: the map as a low-byte plane plus a 2-bit high plane (-1,934 packed, 0.13 s on PEAK); ROWTAB computed (-852); the route as way tiles (-316), or dropped on courses where only the autopilot reads it. **Then, as a follow-up once those are green**, the grid's derivable fields (VOID kill heights, OPEN and SAFE) rebuilt at load (-1,791, 0.15 s on PEAK, PREDICTED) | `--selfcheck`: `expand(BZC2) == RAM` on every course |
| 5b.4 | **The course budget, re-derived for CD3.** The tool prints each course's packed size and RAM against the target time and refuses a part over 65,024 bytes. The per-course packed budget is restated from 5b.1's real figures and the owner's 30/60/90 s mix, in place of R4's 10.5KB average and 16KB maximum. The report predicts about 6.5 / 13.0 / 19.5 KiB for a 30 / 60 / 90 s course, and about 253 KiB for twenty, against about 239 KiB free | a host refusal test as a red arm |
| 5b.5 | **The disk plan, decided with the owner** (Q-L2, and now the big lever). BENCH stays in the package by default (O48). If the owner retires it from the play disk, it becomes a build knob that leaves the engine byte-identical. The owner chooses how to close the remaining gap of about 14 KiB, if 5b.1 confirms it: **LZB for the parts** (-8,188 more on the six courses; about +0.9 s on PEAK's launch), rendering the picture at load (a prototype, high risk), or R4's "Worlds" disk. **LZB for the image** (-3,248 bytes; +0.64 s when the window opens) is offered at the same time | `bonanza360.img`'s cluster count |
| 5b.6 | **The ghost dither** (CD1; the report's section 3.5 (a)). The tool ORs a checker (0xCC and 0x33 on alternate lines) into every occluder mask, so a ball behind anything shows as a 50% ghost. It costs **0 clk and 0 guest bytes**, and makes the masks -710 bytes packed. The tool's models (`composite('records')`, the merge, `bonanzaring`'s oracle) lay the mask minus the checker. **The visibility audit lands with it in REPORT mode**: every course prints its props' visibility and its hidden stretches (story 11.5 turns it into a refusal) | `--selfcheck`; a look boot on MILL (the lift slab must not be half-ghosted) and on PEAK, both cards; `bonanzaring` |

**Not in 5b, placed by the report:**
- ball V1 and V2 go to wave 9 with 9.1;
- the demo bit stream and the joined demo part go to wave 11;
- the RAM levers for long courses go to wave 11, story 11.6;
- wave 8a is restated at 5.6-5.9KB;
- the `bz_boxbuf` bss overlay (-170 bytes of RAM) can land any time.

**Identity.** The course identity (SPEC.md 128.12.8) is computed over the
part as it sits in RAM, so 5b.2's 4-byte records, and 5b.6's masks, change
it. The shipped demos are re-stamped by the tool: they are authored
scripts and autopilot routes, and the physics is not frozen until wave 6
anyway.

**Rows reached:** `bonanzacourse`, `bonanzaring`, `bonanzaexit`,
`bonanzaperf`, `bonanzamega`, `bonanzademo`, `bonanzawheel` (it reads the
records from guest memory).

**Bytes:** about +110 image bytes for 5b.2's frame code and mask table
(ESTIMATED), about +100 bytes of launch-only expanders, and up to 512
bytes of bss for the mask table. On the disk: -40.4KB packed at today's
six courses (MEASURED in combination; 5b.1 confirms it).

**Inventory:** H6's layout, D11 (the part cap stays; 5b.2's RAM records
relieve it by 13KB on PEAK, and T10 is folded in).

#### Wave 6: Feel. Three balls, one Hop, one boost (M-L)

**Goal:** the owner's per-ball physics (decisions 1 and 2), with the reach
still bounded.

**The facts the stories build on** (SPEC.md 128.11.5.3):
- A climb needs the Hop's apex plus `BZ_CLIMB`'s 4 px landing margin.
  So a 1-unit (8 px) step needs an apex of at least 4 px.
- Rubber's Hop today is 224, an apex of 4.5 px. It climbs 1 unit only from
  a take-off window of 19.5-21 gu, about one step (18 ms): "a rubber-only
  height, and a hard one".
- Glass (176, 2.9 px) and steel (160, 2.4 px) climb nothing.
- The apex scales with the square of the Hop. 1 unit needs a Hop of about
  212 or more, 1.5 units about 300, and 2 units about 367.
- A boost that only RAISED a rebound to a fixed `BOOST_V` would do nothing
  after a real fall: rubber falling 2 units already rebounds at 345.

| # | story | verified by |
|---|---|---|
| 6.1 | **Space = Hop and Shift = Grip for every ball** (decision 2). Only the Hop's amount differs, and the defaults (Q-61) are rubber about 256 (an apex of about 5.9 px: 1 unit with a comfortable window), glass about 224 (today's rubber: 1 unit, a hard window, "in between"), and steel 160, unchanged (today's tiny hop) | `bonanzaphys`: guest equals model every frame |
| 6.2 | **Rubber's "and again"** (decision 1). Space caught inside its existing 6-step window at the LANDING OF A HOP sends the rebound to a fixed `BOOST_V` (default about 318, an apex of about 9 px, Q-62). Its rules: once per Hop, never on a second contact; only on a LEVEL floor, so never on a ramp, a lip or a moving floor, where it would add to the floor's own rate; never stacked with a jump pickup (9.3); and the boosted apex reaches 1.5 units and **never 2**, which the tool asserts. Its cue: a sound of its own (7.6) and a stretched squash frame | `bonanzaphys` boost scenarios; red arms `pump` (a second boost in one chain), `rampboost` (a boost on a ramp) and the tool's apex assertion |
| 6.3 | **Grip per ball** (decision 2 and the end goal): rubber good (6 to 8), steel moderate (5), glass very little (10 to 3). Acceleration stays rubber 4, steel 2 and glass 6, which already match "medium, slow, fast" | `bonanzaphys`; the material table in SPEC.md 128 |
| 6.4 | O2's fractional drag (about 30 clk a step), so a one-arrow top speed is a property of the material and not of the ball's history (B7) | `bonanzaphys`; the table |
| 6.5 | **The reach regenerated, not asserted.** The tool's reach state gains the boost's token. RADIUS, the up-ramp exclusion distance, `ledge_gaps()` and selfcheck item 7's sweep are regenerated per ball. The tool prints the STEP LADDER that results, each rung with its take-off window's width, and each course still within its bounds. The boost's apex is priced on all courses with the boost modelled as one boost, not as every Hop raised: at 366 with every Hop raised, MOON is already refused (block row 27, column 27, 5 records against 4) | `--selfcheck`; `--sizes` delta |
| 6.6 | **A CGA palette per course** (D8, moved here from the old "Next" list so the owner's first play shows it). A course-table field, one OUT to 3D9h at each course's start (the bracket's mode set resets it). Palette 0 recolours the balls' identity colours (rubber magenta, steel cyan, glass white), so ball identity must rest on pattern as well as colour, as it does on the Hercules | look boots on both palettes; the Hercules unaffected |
| 6.7 | O9: the camera's vertical target follows the ground line, not z, so a boosted bounce does not bob the view (A21, Q-L5) | a look boot; `bonanzaring` |
| 6.8 | **The PLAYGROUND course** (a review finding): the step ladder's rungs, a gap ladder, a bounce chain onto a 1.5-unit ledge, a brake strip, a pad for each ball, and a palette. The owner judges the freeze on it, and later it can be exploration's sandbox | `bonanzacourse`; the owner's play |
| 6.9 | `BZ_PHYSV` bumped; the shipped demos regenerated (autopilot routes) or re-authored (MOON's and PEAK's scripts) (I11) | `bonanzademo` |
| 6.10 | **The re-baseline** (a review finding): one measured run of every demo through `D` (both cards, speaker OFF and ON) and of `B`, taken once at the freeze commit. Wave 10's targets and BENCH's A/B are re-anchored on it | `bonanzaperf` |
| 6.11 | **Gate 1: the owner plays, then the physics FREEZE**: O11's constants settled and marked binding in SPEC.md 128; O3, O6, O14, O15, O17 and O45 (the mouse's buttons follow decision 2) reviewed with the retune | diary entry |

**The step ladder this aims at** (PREDICTED; 6.5 prints the real one):

| step | who gets up it |
|---|---|
| half a unit | every ball rolls up |
| 1 unit | the Hop of rubber (comfortable) and glass (hard); not steel |
| 1.5 units | rubber's "and again" only |
| 2 units | a wall to every ball **from level ground**; a drop's bounce (SPEC.md 128.11.5.3's table), a ramp and a spring are the exceptions |

So ball choice becomes route choice with no new code.

**Bytes:** +100-200. **Rows:** `bonanzaphys`, `bonanzareplay`,
`bonanzacourse`, `bonanzademo`, `bonanzaperf`, `bonanzaring`.
**Inventory:** B1, B2, B3 (settled by decision 2), B6, B7, B8's review,
A21, D8, I11.

#### Wave 7: Time. Clocks, limits, music (L)

**Goal:** the course clocks and time limits, built so that "nothing off
screen" is true and the heavy frames are measured before the wave closes.

| # | story | verified by |
|---|---|---|
| 7.1 | **First: the walk's slice narrowed by COLUMN** as well as row (A12), so a lane in the window's rows but off to the side costs nothing, not about 0.2k a frame plus a RAM sync at a pose change. The owner's "costs nothing off screen" depends on it | `bonanzawheel`: a lane off to the side is never walked; red arm |
| 7.2 | **The course clock prop** (C1). Its frame (the crystal ball on a stick by default; a scoreboard, lantern, tower, stone, sundial or balloon per course) is static picture art. The digits are one wheel lane. **The form is decided by one measurement** (Q-71): (i) glyphs of our own font (about 10 glyphs of 5 lines, about 150 bytes) composed in BUSY time into the clock's own PRIVATE blocks, which the tool never shares, then committed as an ordinary lane; or (ii) per-pose digit lanes, 10-11 poses of one 16-byte CGA block each (about 160-350 bytes a digit), no new resident code, translated by `bz_hxlat`, but 2-3 lanes of the 6 per window, and up to 3 pose changes at a minute against the 2 a step. The tool gives the clock its own pose-change bound and refuses a clock lane that can stand in front of the route (O25) | `bonanzaclock` (new soak row): commits once a second, the card equals the oracle, nothing walked off the window; red arm: a commit every frame |
| 7.3 | **`limit`** replaces `par` (D4), counted in STEPS so that it is the same in a replay and a demo. A clock shows the remaining whole seconds, rounded up. P stops it. The tool computes the limit per course from its routes (Q-72): the slowest finish's route time times a factor, plus one worst-flag fall's allowance, floored at the autopilot's main route times about 1.3. It refuses a course where any finish's route does not fit. In `R` and `D` the limit is enforced as in play | `bonanzaphys` and `bonanzareplay`: the timeout step equals the model's |
| 7.4 | **Timeout** ends the course: until wave 8b it returns to the face; from 8b to the pathway, with a life lost | `bonanzagame` |
| 7.5 | **`music N`** (G2, S10): a course names its song | `bonanzamusic` |
| 7.6 | **The sound events** (G5): wave 4's unmapped counters (a flag, a pad, a lip-out, a spring, a return, a new best), the boost's cue, the clock's tick, low time at 30 s and 10 s (a tempo-up or a tick under 10 s), and the timeout. Coordinated with the sound plan's session (`docs/plans/BOUNCE-BONANZA-SOUND.md`) | `bonanzasound`, which also closes I9: kick, knock and tube get poked too |
| 7.7 | **The clocks on the heavy frames, measured before the wave closes** (a review finding): clocks on FIRST and TRIAL, and one on MILL and on PEAK, measured through `D` on both cards with the speaker on, against the HUD's rule of at most 2 more misses a card. If MILL or PEAK fails, their clocks wait for wave 10 and the course's retrofit | `bonanzaperf`; the figures in SPEC.md 128 |
| 7.8 | The flag pennant refined with the clock's art (C2): a key of its own, so a ball behind it is not drawn over it | look boot |

**Bytes** (PREDICTED): the clock's compose 400-700 (form i) or about 0
(form ii); the font about 150; the limit about 150.
**Rows:** `bonanzawheel`, `bonanzaclock` (new), `bonanzaphys`,
`bonanzareplay`, `bonanzagame`, `bonanzamusic`, `bonanzasound`,
`bonanzaperf`. **Reports:** PEAK's free RAM and part headroom.
**Inventory:** A12, C1, C2, D4, G2, G5, I9.

#### Wave 8a: The shell's code part (S-M)

**Goal:** room for the shell, proven first on the hardest kernel.

| # | story | verified by |
|---|---|---|
| 8a.1 | **O46 decided this way**: the launch-, desktop- and front-end code (the faces, the save, the demo checks, the calibration), about 7-8KB (re-measured 2026-11-14: **about 5.6-5.9KB net**, because the once-per-launch code inside the bracket and the calibration stay resident; the per-course titles, names and pars move with it, -45 resident bytes a course; disk +0.45KB; about +0.4 s for each return to the desktop), moves into a CODE PART fetched by the front end and dropped before any course fetch | the image figure; the claims count |
| 8a.2 | Running code from a part on kern_mega, checked first, as CWORD's overlay part does it | `bonanzamega` on 86Box |

**Inventory:** A19 (O46).

#### Wave 8b: The loop (L)

**Goal:** one testable loop: the pathway, the courses, the finishes, lives
and the save.

| # | story | verified by |
|---|---|---|
| 8b.1 | **One FSX bracket holds the pathway and every course.** SPEC.md 53.7 makes the file and memory slots legal throughout a bracket, so `op_fetch` runs inside it: no desktop restore and no flash between courses. Its consequences: the palette is applied at every course and pathway entry; a failed save cannot toast inside the bracket, so it shows on the result card (8c.4); on the Hercules `bz_hgen` is rebuilt before every fetch, because a play overwrites `bz_boxbuf`; on kern_mega the bracket stays `FSXF_FASTTICK`, never `FSXF_REAL`. Retry re-enters the course with NO re-fetch (a target of under 0.5 s), because no course state lives in the part (9.2) | `bonanzagame`: no bracket exit between courses; parts fetched and dropped; retry latency |
| 8b.2 | **The pathway** (E3), authored as a BZC1-format part: an empty grid, the Hercules' 45 word columns. The picture is GENERATED by a deterministic host converter from a graph source file, with placeholder nodes for courses not yet built, so a new world changes the source and not hand art. The node icons are LANES (poses: locked, open, done, the medals), so the full write, the lane commit, `bz_hxlat` and the ball box are all reused with no new draw path. The HUD is a fixed band (lives, title, best, medal, exits found n of m). The part is dropped before a course is fetched | `bonanzapath` (new): the graph walk, the icons, the drop before the fetch, both cards |
| 8b.3 | **The pathway's rules** (Q-81): any completed node can be replayed from the map; taking a different finish there opens its branch; the final node leads to an ending card and a post-game (exploration of every found node, and a hunt for exits and medals). The layout of one non-scrolling screen of about 20 nodes is fixed here, not in wave 11 | `bonanzapath` |
| 8b.4 | **Several finishes per course** (D3): `finish K cup|goal at ...` statements. Each finish carries an EXIT number, and the pathway graph maps (course, exit) to the next node, so re-wiring the map never rebuilds a course or changes its identity. Branches may join. `hidden` marks a secret finish (decision 6). Each finish is marked by a GLYPH (a letter or arrow banner in the clock's font), and the same glyph labels its edge on the pathway, because colour cannot carry it on the Hercules or across CGA palettes | the tool: each exit reachable by an autopilot or author route; `bonanzaphys` |
| 8b.5 | **Lives are timeouts** (E1, Q-82): start with 5. Running out of time costs one and returns to the pathway. Abandoning a timed course (Esc, or Retry or Map from the pause overlay) costs one as a timeout does; Backspace to the last flag stays free and costs only time. The life is taken in the save at the course's ENTRY and given back on a finish, so switching off cannot refund it. Exploration is exempt | `bonanzagame` |
| 8b.6 | **Save v2** (E6): `BONANZA.DAT`, magic `BZS2`, read as hostile as today. Three slots, each with a best and a medal per FINISH, the exits-found bits, and the pathway state (node, lives, unlocked set): about 400 bytes, one sector, **one `int 13h` per save**. A refused write (a protected or swapped floppy) is said on the result card, offers a retry, and the pathway shows "not saved" until a write succeeds. New and Erase (with a confirm) settle O52 | `bonanzagame`'s hostile set, extended |
| 8b.7 | **O44 and O7** decided for lives and several finishes: which flag a respawn returns to, and the respawn distance | `bonanzaphys` |
| 8b.8 | The tour, the scorecard, `bz_tour`/`bz_ttime`, N's course cycle and M's ball cycle and the 13-line face are removed (E4, F3); `bonanzagame` and `bonanzademo` are rewritten (I12) | rows |
| 8b.9 | **Who picks the ball** (Q-83, a review finding): a course names its start ball; pads at forks are the player's choice; the pathway node and the intro card show the start ball; exploration may allow any ball, with the tool's NO TRAP still proved for each flag's ball | `bonanzaphys`; the tool |
| 8b.10 | The shell's sound events and songs (title, pathway, life lost, game over), with the sound plan's session | `bonanzasound`, `bonanzamusic` |

#### Wave 8c: The face of the game (M)

| # | story | verified by |
|---|---|---|
| 8c.1 | **The front window** (F1), on the desktop and designed for the CGA's 42 cells first (read docs/INDEX.md first): one artwork band (1bpp for the CGA and Hercules mono desktops; the prompt kept, a deterministic converter, a lazy part); Mode (Timed or Exploration); Slot 1-3 with New and Erase; Camera (GLIDE or TRICKLE); Control (keys or mouse tilt); Sound. The key lines for both controls: arrows roll, Space hop (rubber: again on the landing), Shift brake, P pause, Backspace back to the flag, Esc out; for the mouse, left hop and right brake. Play, Continue, Demos | look boots on the CGA desktop and the Hercules; `bonanzagame` |
| 8c.2 | **Exploration** (E7, Q-84): no clock, lives, medals or bests; its own unlocks per slot, which never unlock anything in timed mode. Its purpose is hunting hidden finishes, counted as "found n of m" in both modes and never needed to progress | `bonanzagame` |
| 8c.3 | **Medals** (decision 4, Q-85): per finish, `medals G S` from the owner's playtest runs; "completed" is the base icon (any finish in time), and silver and gold above it; the node shows the best over its finishes | `bonanzapath` |
| 8c.4 | **The cards**: an INTRO card during the fetch (name, start ball, limit, medal times, exits found n of m); a RESULT card after a finish or timeout (time, medal, new best, the exit glyph, "not saved" if so), then the path lighting on the pathway; a PAUSE overlay on P (Resume, Retry, Map, and the time left). None of them is in the play frame | `bonanzagame`; look boots |
| 8c.5 | **Gate 2: the owner plays the shell.** The scoped soak and `test-full` run first, at the merge to `elendilon` | diary |

**Rows (8a to 8c):** `bonanzagame`, `bonanzademo`, `bonanzapath` (new),
`bonanzamega`, `bonanzaexit`, `bonanzasound`, `bonanzamusic`.
**Inventory:** E1-E7, E9 (O4 replaced, O48 kept, O53 open), F1-F3, I12,
A19, A20 (the cut's blank, revisited for the shell).

#### Wave 9: Mechanics as parts (L)

**Goal:** the owner's decision 8 made concrete, with an unused mechanic
costing nothing, and pickups (decision 5). The families themselves land
with the first course that uses them (waves 12, 13, 16, 17).

**The framework:**
- A **family** is three things:
  - a **code part** with its rules: hooks for cell-enter, contact, the
    per-step force and a timer;
  - its **art**, rendered by the tool into the course's own block pool as
    lanes (already scoped per course today);
  - its **model** in `bbcourse.Physics`, behind the same hook table.
- A course declares `uses wind, cracked`. The launch fetches every family
  part the course names into **one claim** (R4's claim count).
- The engine keeps a hook bitmask. An unused hook costs a bit test, about
  0 a step; an active one costs a far call, about 0.1k.
- **An unused family costs 0 image bytes and 0 clk.**
- **A family draws only through lanes and the static picture.** A family
  that needs a draw path of its own is a resident engine change and a
  decision of its own (water is one: wave 17).
- Family state lives in a fixed bss slot per family, reset by W, L, a
  replay, a retry or a respawn.
- The course identity carries each family's version byte.

**The per-course limits** (Q-91): at most **3 families**; at most **1 timed
pickup kind**; at most 6 lanes meeting a window (O24); the part at most
65,024 bytes; the packed budget (R4); and the claim count.

| # | story | verified by |
|---|---|---|
| 9.1 | The framework; the three ball parts in one carved claim; a red arm: a course using an undeclared family is refused by the tool. **With the ball claim, the ball parts are regenerated at fetch** (BONANZA-SIZE-2026-11-14 section 3.4): V1 stores every mask and frame once at shift 0 and builds the shifts, parity copies, shadow and shatter cut; V2 generates the 64 roll frames from a per-material template and phase table. The balls go from 7,380 to 1,668 bytes packed, at 0 clk a frame and about +150 ms for a three-ball launch (PREDICTED) | host; `bonanzaphys`; the generator held bit-exact against `build_ball2` under an emulated 8086, every material, as `bz_hxlat` is |
| 9.2 | **The per-play state contract** (a resident engine change, a review finding). Today every prop's pose is a function of the step, its seed and the course (SPEC.md 128.12.8). A cracked tile, a revealed path, a collected pickup and a used hourglass depend on the ball's history instead. So: a per-play STATE BITSET (broken, revealed, collected), reset at the play's start, a retry and a respawn exactly as SPEC.md 128.12.6.6's state is; **the grid is never written**, and physics reads the bitset over the grid; the true-pose routine reads the bitset; the reach model and the occluder build cover the broken-cell superset. A retry clears the bitset and re-poses the lanes: no re-fetch | `bonanzaphys` and `bonanzareplay` red arms for "retry after a crack" and "a respawn after a pickup" |
| 9.3 | **Pickups** (decision 5, Q-92): an HOURGLASS (+10 s, once per attempt); a SPEED pickup (more acceleration for N s and a bounded raise of the top speed, priced by the tool, so it is not read as broken once at the cap); a JUMP pickup (rubber's Hop amount for N s, never stacked with the boost, never over 2 units). The tool proves every finish is reachable with NO pickup, so a pickup only shortens a route, and a boosted reach stays inside the bounds or is refused. Cued by sound, not a HUD | `bonanzaphys`; the tool's routes; red arms |
| 9.4 | A test course for the framework and the pickups, built from an existing course, not a world course | `bonanzacourse`; owner look |

**Rows:** `bonanzaphys`, `bonanzareplay`, `bonanzacourse`, `bonanzamega`.
**Inventory:** C10's framework, I7's scene (with 12's first glass path),
C8's state.

#### Wave 10: Performance (L)

**When:** after wave 9, because the frame's new consumers (clocks,
families, pickups) then exist; before the worlds, so courses are built
against the faster engine and a per-course miss budget. Every target is
measured against wave 6's re-baseline (6.10).

| # | target | today (MEASURED) | target (PROPOSED; the owner accepts) |
|---|---|---|---|
| T1 | `bonanzawheel` (6), the CGA's light corner (A1); `alias` and `corner` judged (I8, A2) | `bz_tw` 53.7-61.7k against about 59.4k: FAIL | PASS. The levers are the owner's (Q-L3) |
| T2 | BENCH's A/B (A7) | CGA +522 and +531, Hercules +317, against +0.5k; builds spread about +-0.1k | re-anchored on the freeze (6.10); within +0.5k over 3 builds' spread |
| T3 | MILL's misses, CGA OFF / ON (A9) | 47 / 151 | at most 25 / 75 |
| T4 | PEAK's misses as it stands (A8); its eased form is measured at its retrofit in wave 13 | 205 / 293 CGA; 60 / 96 Hercules | recorded; the eased PEAK meets T11 |
| T5 | The Hercules' MILL lift, speaker ON (A10, I10) | 3, then 4 | at most 3 in 5 runs of 5 |
| T6 | The walk narrowed by column | done in 7.1 | held |
| T7 | Half-rate sound, and sound in the retrace wait's idle time (G4) | speaker 3.3k average | measured; the owner listens and decides |
| T8 | Box writes (A4), wheel commits (A2), the preparation and the walk (A3), `bz_wlate` (A13), TRIAL on the Hercules (A14), the two-box rotor frame (A15, priced at 88k and never measured) | open | each measured; fixed or recorded |
| T9 | The image (A5): a byte budget with the 20 courses' resident rows in it (R4) | 32,640 and growing | set from 8a's code part |
| T10 | 4-byte occluder records in RAM as well | **moved into wave 5b's story 5b.2** (2026-11-14, BONANZA-SIZE-2026-11-14); held here only if 5b ships its fallback C | about -13KB of RAM on PEAK; about +30 clk on a typical occluder frame, about +450 worst (ESTIMATED) |
| T11 | **A per-course miss budget** for the pipeline, set from T3 and T4 (for example at most X misses per 1,000 steps, CGA, speaker ON) | none | a course acceptance criterion |
| T12 | **The ghost, measured** (decision 7): a knob build draws a second ball box from a recorded log on FIRST's, MILL's and PEAK's demos, both cards, speaker ON; misses, box-bound refusals and lane lateness reported. Taken once, since it decides the design | predicted +12-15k a frame | Q-L6 answered from it |

A11 (O33: the lift slab on even lines, or accept the residue), A16 (the
O24 and O26 tunables) and G3 (`BZS_FMCAP`) go to the owner with these
measurements.

**Rows:** `bonanzawheel`, `bonanzaperf`, `bonanzaring`, `bonanzasound`,
`bonanzamusic`. **Inventory:** A1-A5, A7-A16, A18's T10, G3, G4, I8, I10.

#### Wave 11: The tutorial and the course pipeline (M)

**The pipeline, per course:**
1. **A design sheet**, `docs/plans/bonanza-courses/<NAME>.md`: the world,
   its families (at most 3), the start ball, its finishes and their exits
   (a secret one?), the time-limit target, the palette, the clock's frame,
   the song, and the new idea it teaches. **Under the owner's notes
   (CD1-CD3, binding):** the sheet also states the course's target time
   (about 30, 60 or 90 s) and its pace in seconds a block row; its place
   on the challenge curve and the one new demand it makes (CD2); and how
   every mechanic stays visible, naming any declared `hidden` stretch
   (CD1, story 11.5). **The design principle**
   (SUGGESTION, a review finding): a branching course's harder or hidden
   exit is usually MATERIAL-gated, by a pad, a rung of the step ladder or a
   family that sorts balls. Every branching course has an easier exit to
   the easier branch, and branches rejoin before the final node. The
   tutorial has no hidden finish.
2. **The `.bbc` file**, `--png` previews, `--selfcheck`, and `--sizes`
   against the budget.
3. **Routes or author scripts, one per finish**, which become demos. The
   miss measurement on both cards is taken ONCE by the agent building the
   course, against T11, because it decides the design (whether to ease a
   chain).
4. **A playtest disk to the owner** (fork rule 3).
5. **Tuning**: the limit is the tool's (7.3); gold is the owner's best
   plus 5% and silver plus 20%, per finish.
6. **Final demos recorded** after the tuning. The physics has been frozen
   since wave 6.
7. `bonanzacourse` and `bonanzademo` pick the course up by themselves.
   Performance legs are per world, not per course.

| # | story | verified by |
|---|---|---|
| 11.1 | **FIRST** becomes tutorial 1, no branch: roll, brake, a flag, the clock | owner play |
| 11.2 | **TRIAL** becomes tutorial 2, no branch: Hop, ramps, rubber's "and again", a spring | owner play |
| 11.3 | The graph source (8b.2) filled in (SUGGESTION): 2 single nodes, then columns of 2-3 nodes, about 10 courses on any path to the final course, 20 in all, including 2 secrets reached by hidden finishes | `bonanzapath` |
| 11.4 | The pipeline's tool support: per-finish `author` scripts, the budget, a playtest-disk target | host |
| 11.5 | **The visibility rule** (CD1; BONANZA-SIZE-2026-11-14 section 3.5 (c)). It runs in `bbcourse.py` at compile and in `--selfcheck`, and switches 5b.6's report into a REFUSAL. Every spring, pad and cup (mark, pin and flag) must be at least 75% visible in the static picture, and every tube mouth at least 50%. The route demo and every authored demo are run through the model. Any stretch outside a tube where the ball is more than 50% hidden for over 0.5 s (27 steps) is refused, unless the course declares it `hidden` (a deliberate secret); a declared stretch must turn less than 30 degrees. Every course prints its hidden stretches and what hides them. BENCH is exempt. **Cost: 0 on the 5150; about 0.6 s a course on the host.** The design rules go into the design sheet: springs, climbs, tube runs and drop landings go AWAY from the camera (-x or -y); a near rail stands one or two units above the floor it guards, and flat where it can (one unit still stops a roll and a rubber Hop) | a red arm: today's PEAK refused (springs, cup and pad at 0%, a 3.00 s hidden stretch); MOON refused until retrofitted |
| 11.6 | **The RAM levers for long courses** (CD3; the report's section 6), landed before the first course over about 70 s. Both cost 0 clk a frame and a step. Grid rows overlapped through ROWTAB: PEAK -788 bytes of RAM, and ROWTAB then ships one byte a row. Map rows at a constant stride of 108 bytes with a row-base table: PEAK -2.4KB, and the tool refuses art or a lane in a row's outer 10 words. With 5b.2, one part then holds about 212 block rows, about 79 s at MOON's and PEAK's pace. **A 90 s course is designed at 0.425 s a block row or slower**, or the owner chooses the grid in a claim of its own (the eighth of eight). **And the replay log is checked**: `bz_rlog`'s 4,096 bytes could truncate a jittery mouse play after about 25 s (PREDICTED), so a 90 s course's log is sized or its encoding tightened before its demos are recorded | `--selfcheck`; `bonanzacourse`; `bonanzaring`; a long mouse play through `W` |
| 11.7 | **The demos as a bit stream** (the report's section 3.4): a Huffman code for the key (with an escape for any other key) and Elias gamma for the run count, expanded into BZR1 pairs when a demo is copied into `bz_rlog`, with the header trimmed. The demos are joined into one indexed part. This saves about 8.5KB at twenty courses, at 0 clk a frame and about 28 ms at the copy | `bonanzademo`; the tool's round trip |

**Inventory:** D1, D2, D5 (as each course is retrofitted), D9, D10
(watch items the tool enforces).

#### Waves 12 and 13: Worlds 1 and 2, one course at a time (L each)

Each course goes through wave 11's pipeline, and a family lands with the
first course that uses it. Each world has a palette, a song, a clock frame
and a family set (SUGGESTION: "worlds"; the owner may prefer a single
graph without them).

| world (SUGGESTION) | courses | arriving |
|---|---|---|
| 12: Meadow | FIRST and TRIAL (wave 11), then a course after TRIAL that teaches pads and the three balls' differences BEFORE the first branch (a review finding), and 1-2 more teaching flags and springs; the first branch at its end | hourglass and speed pickups; nothing else new |
| 13: Windmill country | MILL rebuilt to the new physics with clocks and finishes (O27: the lift the autopilot cannot ride; O32: the lift carries a flight), 2-3 new courses, and **MOON and PEAK retrofitted as the world's two branch finales**, PEAK's chains eased then (O54) and measured against T11 | **wind** (weighted by mass: glass x2, rubber x1, steel x1/4), **cracked tiles** (break under steel or a hard landing; the tool proves every flag still reaches a finish with every crackable cell broken), **disappearing glass paths** (always floor to physics, drawn as void; a hint of static sparkle pixels in the picture; revealed by ROW, one lane holding several tiles' poses up to 16, and the tool bounds how many glass lanes meet one window; priced as a contact-box frame; needs red arm `contact`'s scene, I7), the jump pickup |

**Inventory:** D1, D3's courses, D5, D6 (O43: cups and flags on FIRST,
TRIAL and MILL are re-decided by each course's sheet), D7, C6
(conveyors, if a world-2 course wants one), C8, C9's groundwork, B9 (the
elements tuned as the courses use them).

#### Wave 14: The machines (M; the old wave 5)

- H1: the Hercules' pair art and its blank budget. F4: decide the vertical
  phase's wobble (a second frame set costs 5,120 bytes a claim).
- **H5: VGA runs the CGA arm**, tested on MartyPC's `os8088_xt_vga` (VGA
  is not a QEMU case). The per-course palette must reach the colours
  there. Whether a VGA honours 3D9h or needs the attribute controller is
  checked first.
- kern_mega re-verified with the family parts, the shell's code part and
  the pathway, on 86Box.
- The EGA, MDA and kern_small refusals re-checked; four disk geometries.
- O19 (`kbd_track`'s fake shifts, H10) offered to the owner as a separate
  kernel change.

#### Wave 15: Release 1 (M)

1. **Gate 3: a field run on the 5150s**: #1's speaker and #2's PicoMEM
   AdLib (H9, G1, G7), real-card VRAM wait states, and the sound by ear
   (S9).
2. The final pass: one scoped soak of every BONANZA row plus every red
   arm, then `test-full` once at the merge.
3. **The shipping checklist** (H7, on the owner's word; ARCADE's `arcrel`
   images are the precedent, ARCADE-SPEC 1.6):
   - the `local` line out of `apps/RETIRED.txt`;
   - the bonanza images into `$(SHIPIMGS)`, which also puts them in `all`;
     say what that costs every build;
   - the images into the four image gates' own lists (`t_image`,
     `t_diskverify`, `t_canary`, `t_blobruns`);
   - `release-os8088`'s image list and its `PROGRAMS/<APP>/` folder;
   - the live-media decision;
   - README.md's "on no other disk" lines;
   - fork rule 3's disk count in CLAUDE.md and AGENTS.md;
   - `apps/bonanza/README.md` rewritten; docs/HEAP-CLAIMS.md refreshed;
     t_pins re-checked for the new claims (I6).
4. The website through `release-os8088`, and the diary published, both
   only with the owner's authorization.
5. The plan moves to `docs/plans/completed/` when release 2 is done or
   dropped, not before.

#### Waves 16 and 17: Worlds 3 and 4, release 2 (L each)

| world (SUGGESTION) | arriving |
|---|---|
| 16: Moonglass | the **shatter-glass and fling-rubber traps**, with steel immune (B4; steel's stun on hard FALLS is kept, Q-L4), gates by material, magnets (steel only), more glass |
| 17: Peak and water | **WATER**. It is not a family: a ball IN the water's cell is drawn whole over it (an occluder lays only for a ball behind the face, SPEC.md 128.10.8), and "steel sinks, rubber and glass float" needs two floor heights in a cell where BZG1 has one. So it needs a grid section (a water flag and a bed height, added through BZC2's tagged directory), per-ball reach, and a submerged draw path (a masked compose or dithered frames, with their bytes per ball part): a resident engine change, its own SPEC.md contract and its own price. Then steel sinks and rolls on the bed; rubber and glass float (Q-L7) |

### R7 The owner's open questions, each with a recommended default

**Needed before wave 6 (gate 1):**

| # | question | recommended default |
|---|---|---|
| Q-61 | The Hop amounts | Rubber about 256 (1 unit, a comfortable window); glass about 224 (1 unit, a hard window, "in between"); steel 160. The owner picks from the windows 6.5 prints, on the playground |
| Q-62 | The boost: where it acts and how high | Once per Hop, at the Hop's landing, on level floors only; a fixed apex of about 9 px that reaches 1.5 units and never 2. Because a real fall already rebounds higher than that, it adds nothing after a fall: "and again" is a Hop's second bounce. Its cue is a sound and a stretch |
| Q-63 | Grip per ball | Rubber 8, steel 5, glass 3 |
| Q-64 | Palettes | Per world, with a per-course override |

**Q-61 to Q-63 answered for now (2026-11-14, CD4):** "I'll need to test
these to see how they feel, but this seems like a fine starting point."
Wave 6 ships the defaults, and gate 1's play tunes them.

**Needed before wave 8 (gate 2):**

| # | question | recommended default |
|---|---|---|
| Q-81 | The pathway's rules | Completed nodes can be replayed; a different finish opens its branch; an ending card, then a post-game hunt for exits and medals; one non-scrolling screen of about 20 nodes with a fixed HUD band |
| Q-82 | Lives, escape and game over | Start with 5. A timeout or an abandoned timed course costs 1; Backspace to a flag is free. +1 life on a first gold (cap 9). Game over goes back to the front window with a choice: Continue limited to 3 per slot, returning to the last branching node passed with 5 lives, medals and found exits kept. (A free Continue makes game over cost only map position: the owner's trade to choose) |
| Q-83 | Who picks the ball | The course's start ball; pads at forks; any ball in exploration |
| Q-84 | Exploration | Its own unlocks per slot, never unlocking timed mode; no clock, lives, medals or bests; hidden finishes count as found in both modes |
| Q-85 | Medals with several finishes | Per finish; "completed" is the base icon (any finish in time), silver and gold above it; the node shows its best |
| Q-86 | Time limits | The tool's rule (7.3): the slowest finish's route times 1.5 (tutorial) or 1.25, plus one fall's allowance, floored at the autopilot's route times about 1.3, rounded to 5 s |

**Later, with a default the plan applies unless the owner overrules it:**

| # | question | recommended default |
|---|---|---|
| Q-R1 | Release 1's content | The tutorial and worlds 1-2, MOON and PEAK as world 2's finales, about 10-12 courses; worlds 3-4 in release 2 |
| Q-71 | The clock's digits | Decided by 7.2's measurement: private-block glyphs unless per-pose lanes cost no misses and fit the lane bound |
| Q-91 | Mechanics per course | At most 3 families and 1 timed pickup kind; all family parts in one claim |
| Q-92 | Pickups | Hourglass +10 s once per attempt; speed raises acceleration and a bounded top speed; jump never stacks with the boost; every finish reachable without any |
| Q-L1 | Music | One song per world, plus title, pathway and game over: about 7-8 songs |
| Q-L2 | BENCH and the disk (O48) | BENCH stays in the package (compact, about 10KB) and `B` stays the benchmark. If the owner retires it from the play disk, it becomes a knob build proved byte-identical |
| Q-L3 | `bonanzawheel` (6)'s lever (A1) | Try a lighter preparation first; a corner case at the window's top second; a test course last |
| Q-L4 | Steel's stun with trap immunity | Keep the stun on hard falls; the immunity is to traps only |
| Q-L5 | The camera's vertical (O9) | The ground line, in wave 6 |
| Q-L6 | The ghost | Not in release 1 unless T12 shows it fits; split chimes instead (R8) |
| Q-L7 | Water for each ball | Steel sinks and rolls on the bed; rubber floats with high drag; glass floats lightly |
| Q-L8 | BENCH's A/B bound (A7) | Re-anchored on the freeze, +0.5k over 3 builds' spread |
| Q-L9 | The lift's CGA residue (O33) | Accept it unless wave 10 frees the time |
| Q-L10 | The kernel's fake shifts (O19) | A separate kernel PR, the owner's call |
| Q-L11 | Where it ships | Its own disk in all four geometries; `bonanza360.img` joins the sent set; not on `games360` or `allapps` |

### R8 Suggestions (the planner's, each priced on the 5150)

| suggestion | cost | in the frame? |
|---|---|---|
| **Three medal grades** above the owner's "completed" icon | 2 bits a finish in the save; icon lanes on the pathway | 0 in play |
| **Exit dots** on a node (n of m finishes found, secret ones as `?`) | 4 bits a course | 0 |
| **The step ladder** as the course language, with families that sort by ball (wind by mass, magnets for steel) and material-gated exits as the game's signature (R6, wave 11) | none beyond the families | yes |
| **Worlds**: a palette, song, clock frame and family set each | data only | yes |
| **Ghost-lite: split chimes**: a higher or lower note at each flag for ahead of or behind your best, and splits on the pathway | about 160 bytes of save | 0 |
| **The playground** as exploration's sandbox (6.8) | one course | yes |
| **Attract mode on the pathway**: idle 30 s plays the highlighted node's demo through the existing `D` and `V` paths | about 100-200 bytes | yes |
| **A life back** on a first gold (cap 9) | about 20 bytes | yes |
| **Difficulty**: Relaxed x1.5, Normal, Expert x0.85 on the limits; medals from Normal up | about 50 bytes | yes |
| **Key remap**: alternatives for Hop and Brake (Ctrl, for example) | a table and a setup control, about 200 bytes | yes |
| **Accessibility**: a high-contrast palette the player can choose over the course's; ball identities never resting on colour alone; exploration as the no-pressure mode | one OUT; an art rule | yes |
| **A rolling ball as the pathway cursor**, reusing the ball box (about 9k a frame on a static screen) | about 300 bytes | yes: the pathway is not the play frame |
| **Instant retry** with no re-fetch (8b.1, 9.2) | in those stories | yes |
| **4-byte records in RAM** (T10) | about -13KB of RAM on PEAK | yes, measured |
| **Gems on risky lines** for exploration (plan section 9, item 11) | a family | release 2 at the earliest |

**Post-release, each priced when chosen:** golf mode, the link race and a
full ghost (E8: each a mode beside the game, not part of it); the SPONGE
ball (B10); the "Bonanza" combo (E5, which would give the title a meaning
again); the section 8 non-planar props (the loop, volcano, banks and
funnel: grid kinds 4-15, C3); mud, grates and chevrons (C5); switches and
timed gates (C7: a family once wave 9 exists, in no world yet); see-saws,
flippers, global tilt and weather (C11); an interrupt-time voice (G6,
O38); composite 16-colour mode (H8).

### R9 Where every inventory item went

| wave | items |
|---|---|
| 5a | I1-I5, I13, A6, A17, H2-H4 |
| 5b | H6's layout, D11 |
| 6 | B1-B3, B6, B7, B8 (O3, O6, O14, O15, O17, O45), A21, D8, I11 |
| 7 | A12, C1, C2, D4, G2, G5, I9 |
| 8a-8c | E1-E7, E9, F1-F3, I12, A19, A20, B8 (O7, O44), D3 |
| 9 | C10's framework, C8's state, I7's scene (closed in 13) |
| 10 | A1-A5, A7-A16, G3, G4, I8, I10, T12 for E8's ghost |
| 11-13 | D1, D2, D5-D7, D9, D10, B8 (O32), B9, C6, C8, C9's groundwork |
| 14 | H1, H5, F4, H10 |
| 15 | H7-H9, G1, G7, I6 |
| 16-17 | B4, B5, C9, C10's traps, C11's magnets, C12, C13 |
| standing | A18: waves 7-9 report PEAK's free RAM |
| post-release (R8) | B10, C3, C4's bonus points, C5, C7, C11's rest, E5, E8's golf and link, G6, H8 |

### R10 What the review changed, and what it did not

The draft was read through three lenses (the engine, the game and the
scope), which returned 49 findings. All were checked against the tree and
SPEC.md before they were taken.

**Taken whole:** the claim cap (R4); the step ladder restated as apex plus
4 px (wave 6); the boost bounded on level floors and modelled as a token
(6.2, 6.5); the per-play state contract (9.2); the glass path revealed by
row (wave 13); the clock re-priced with the measured commit and its form
left to a measurement (7.2); the walk's column narrowing pulled forward
(7.1); the clocks measured on MILL and PEAK before wave 7 closes (7.7);
the re-baseline after the freeze (6.10); BZC2's real layout behind an
`OP_ZFILL` hole (R2); identity kept by holding settings outside the part
(5b.2); BENCH kept, and a knob build if it goes (5b.4); water as a
resident change, not a family (wave 17); the bracket's knock-on effects
(8b.1); the pathway as a BZC1 part with lane icons (8b.2); the boost's
behaviour after falls told to the owner (Q-62); the ghost's box bound and
lane lateness; the resident bytes of twenty courses (R4); the ball choice
(8b.9); time limits derived per finish with a fall allowance (7.3); lives
that cannot be dodged (8b.5); the cards and the pause overlay (8c.4);
medals per finish (8c.3); the pathway's rules (8b.3); finish glyphs, not
colours (8b.4); the playground course (6.8); the pickups' rules (9.3);
the front window's full option list (8c.1); retry without re-fetch;
save failures shown (8b.6); the questions split by gate (R7); material as
the branches' signature (wave 11); a release-1 cut (R3); one place for
PEAK's easing (wave 13); gate 0; wave 8 split; the ghost measured (T12);
the release checklist (wave 15); every inventory item placed (R9); BZC2's
tagged directory; wave 5 split; the pathway picture generated from a
graph source; the shell's songs and events (8b.10).

**Taken in part:**
- *Game over with limited Continues*: put to the owner as the default with
  its trade stated (Q-82), not decided.
- *Soak per merge point, not per wave* (R5): taken, but the owner's play
  gates, not every merge, set the points.
- *The family claim*: one claim per course's families, and the balls'
  claims merged in wave 9. The shell's part is dropped before a fetch
  rather than merged with anything.

- *The palette moved earlier*: to wave 6, not wave 5. Wave 5 is host work
  and the format, with no guest feature, and wave 6 still puts the
  palette in front of the owner at gate 1.

**Rejected:**
- *Gems in exploration for release 1* (GD11): a new family for a mode the
  owner has not asked a goal of. Exploration's purpose in release 1 is
  hunting hidden finishes, which needs no new code; gems stay a
  suggestion (R8). The rest of that finding (one default for Q-84, a
  purpose for the mode) is taken.

### R11 Risks, added to section 13's

- **The frame.** Every per-frame addition is judged on MILL's and PEAK's
  heavy frames. The HUD's +65 misses against a predicted 0-3 is the
  precedent, and 7.7 and T11 are the guard.
- **PEAK's part and RAM.** 4,168 bytes left under 65,024, and about
  20.5KB free during play. T10 is the relief; waves 7-9 report both.
- **Claims.** Seven of eight in a play today. The one-claim families and
  the merged balls are what make room.
- **The block bound.** BENCH sits on 4 records a block (D9), and MOON hits
  it at a 12 px apex. The tool refuses rather than ships; the boost's apex
  is priced against it.
- **Demos churn** with every `BZ_PHYSV` or identity change (I11). Demos are
  recorded after the wave 6 freeze and each course's tuning, and BZC2 and
  the course table keep cosmetic edits from changing identities.
- **A fall behind geometry costs a frame on the CGA** (D10). Each new
  course prices it in its one miss measurement.
- **Release 1 waits on twelve waves of work.** The release cut (Q-R1) is
  what keeps it from waiting on twenty courses as well.

---

## 0. The answer on one screen

1. **Both directions are feasible on the CGA and on the Hercules, with no
   hardware we don't already use.** On both cards, the 6845's start address
   is a word offset into an **8 KB ring for each bank**. A vertical scroll
   moves it by one row of words, and a horizontal scroll moves it by one
   word. This tree has already shipped each half:
   - **1942** (SPEC.md 101.1) scrolls vertically on the CGA, two scan lines
     at a time.
   - **Excitebike** (SPEC.md 102) scrolls horizontally on the CGA and the
     Hercules, 8 px a column, and was **measured on MartyPC's 4.77 MHz XT at
     54.6 Hz, with two thirds of each sub-tick idle**.

   Doing both at once uses the same ring. Section 2 shows that a 40×100
   window cannot alias inside it.
2. **The steps are coarse in one direction.**
   - CGA: **2 lines** vertically, **8 px** horizontally.
   - Hercules (Excitebike's 360×200 pair-pixel field): **4 lines** and
     **8 game px**.

   So the courses are **tall first** (Marble Madness's own shape: the
   descent is mostly down the screen), up to **2–3 screens wide**, with a
   dead-zone camera so that horizontal steps happen rarely and in glides
   (section 2.6).
3. **The ball is a phase torus: 64 frames, 4 KB, no 3D maths on the
   guest.** The visible face samples a texture that is periodic in both axes
   through a fixed spherical lookup. Rolling by (dx, dy) pixels adds (dx, dy)
   to the phase modulo 8. So **every direction of travel is covered, and a
   change of direction never jumps a frame**. The prototype is
   `bounce-bonanza/roll-*.gif` (section 4).
4. **TITHE's wheel carries over almost unchanged**, as *lanes*, each with
   its own clock:
   - **Must happen every frame:** the scroll strips, the ball, and the one
     obstacle the ball is touching.
   - **Wheel:** the other 2–6 animated obstacles share a **calibrated credit
     in microseconds**. A missed slot is late by one frame and never slows
     the animation, and a rate cap stops fast machines from over-animating.
5. **The physics is a fixed-step heightfield with momentum.** Input applies
   a *force*, the surface decides grip and friction, walls and drops have
   restitution, and the step is deterministic. Determinism gives replays,
   ghosts and a link race for free (section 5).
6. **There is no new kernel slot, with one optional exception.** A
   *trackball* control (the mouse's relative motion) needs one, and is the
   owner's decision (section 5.4). The pointer can already be used as an
   analogue *tilt stick* at no kernel cost.

**Recommendation:** build it. Start with **wave 0**, a throwaway spike: the
2D ring, one test course and the ball, on MartyPC's CGA and Hercules XTs.
Its numbers are the go/no-go for the rest.

---

## 1. The machine the game is for

From docs/FIELD-MACHINES.md, the owner's 5150 #1 has:

- **CPU and RAM:** an 8088 at 4.77 MHz and **640 KB** (256 KB on the
  board, plus an AST SixPakPlus).
- **Video:** a **Hercules GB101 and an IBM CGA, both live**. It boots on the
  Hercules, and Control Panel → Display moves the desktop to the CGA.
- **Input:** a serial mouse on COM1.
- **Sound:** the PC speaker only.
- **Not listed:** a game port.

So the game must be good on **both** 1983 cards. MDA has no graphics, so it
is refused with a reason (§47).

Adapter support:

| adapter | plan |
|---|---|
| CGA | `FSXM_CGA320`, 320×200×4. The **baseline**: the art is authored for it |
| Hercules | `FSXM_HERC` with Excitebike's 360×200 pair-pixel field (SPEC.md 102.7.1: R6 = 50 rows, 4 banks, a game pixel is 2 card pixels, and the mid level is a `10/01` checker) |
| VGA / EGA | Phase 1 runs the CGA arm on a VGA, as `FSXM_CGA320` allows. **EGA is refused until proven**, which is Excitebike's rule. A later VGA arm (section 2.8) gets smooth 2D scrolling from Mode X's panning |
| MDA | refused: `CGA OR HERC ONLY` |

How the game runs on each kernel:

- **kern_big:** the main target.
- **kern_mega:** a shipped kernel, so it is in the design and not an
  afterthought. It uses the ORDINARY FSX bracket with `FSXF_FASTTICK`, as
  Excitebike does. *(Corrected 2026-11-12: this said the real-mode bracket,
  `FSXF_REAL`, SPEC.md 53.2.3, but that bracket's API table has no
  `OSAPI_SND_TONE` or `OSAPI_MEM_P`, so the speaker would go silently dead.)*
  `OSAPI_SEG` covers any segment derived from a claim, and any mega-only
  code goes under `PKG_MEGA` (SPEC.md 20.18).
- **kern_small:** the 128 KB machine cannot hold the level and art claims
  (section 7), so the game **refuses at start with that reason**. A smaller
  arm is not planned.

Clocks:

| | value |
|---|---|
| a CGA frame | 59.92 Hz = **79.6k clocks**. The 62-line blank lasts about 3.9 ms, and it is **2.4 ms** from the retrace to line 0 (SPEC.md 102) |
| a Hercules field (R6 = 50) | about 50.4 Hz = **94.9k clocks**, with about 98 blank lines (5.3 ms) after the retrace starts (SPEC.md 102.7.1) |
| one CGA VRAM word, `rep movsw` | **about 86 clocks**, against about 17 for a RAM word. Measured on MartyPC, PERFORMANCE.md Set 148. **This is the cost that shapes everything** |

---

## 2. Scrolling: the ring, both ways

### 2.1 The ring

In `FSXM_CGA320` there are two banks, 2000h apart, and a row of words is 80
bytes (40 words, 8 px each). The 6845 decodes 12 bits of its word address,
plus the scan line's low bit as A13. That makes each bank a **4,096-word
ring**: the 40×100 window uses 4,000 words, leaving **96 words of slack** per
bank.

Store the world **sheared**, as Excitebike does. The byte that holds world
row-pair *r* and world column *c* is:

    addr(l, c) = (l & 1) * 2000h + (80 * (l >> 1) + 2c) mod 8192

That address **never depends on the scroll**. The scroll is only the start
address:

    S = (40 * top_rowpair + left_col) mod 4096

**Proof that the window cannot alias.** Two cells share a word when
40·Δr + Δc ≡ 0 (mod 4096). Inside the window, |Δc| ≤ 39 and |Δr| ≤ 99, so
|40·Δr + Δc| ≤ 3,999 < 4,096. The sum is therefore zero only when
40·Δr = −Δc, which forces Δc = 0 (because |Δc| < 40), and then Δr = 0. The
argument is Excitebike's, extended with Δr. **Two-dimensional scrolling is
the same ring with two step sizes**, not a new mechanism.

### 2.2 Vertical: 2 lines a step, drawn off screen first

When the window moves down by one row-pair, the new bottom row is ring words
`S+4000 … S+4039`. That is **inside the 96-word slack**, so it is written
*before* the start address changes and is never seen half-drawn. Moving up
writes into `S+4056 … S+4095`, which is also slack.

- **Up to two row-pairs a frame** fit in the slack (80 words, against 96).
  That gives a vertical camera speed of up to **4 px a frame, about
  240 px/s**.
- **Cost:** 40 words in each of the 2 banks = 80 VRAM words, about **6.9k
  clocks**, plus about 1.5k for the RAM side. That is **about 1.8 ms a
  row-pair**, predicted.

### 2.3 Horizontal: 8 px a step, raced ahead of the beam

When the window moves right by one word, the entering column's cell (row
*r*, column 40) is the same word as (row *r*+1, column 0). That word is **on
screen** until the start address latches. So, exactly as Excitebike's CGA
arm does:

1. Write R12/R13.
2. Wait for the retrace.
3. Write the column **top-down, starting in the blank**, staying ahead of the
   beam.

**Cost:** 200 VRAM words, about **17.2k clocks, about 3.6 ms**.
Excitebike's measurement agrees: 7.6k clocks a frame at 0.43 columns a frame.
The writer stays ahead of the beam. The beam reaches line 0 only 2.4 ms
after the retrace starts, and it is at about line 19 when the column
finishes at 3.6 ms. That holds only if the column is written **in raster
order, starting at the retrace**, which is Excitebike's rule.

**Horizontal steps are 8 px.** The start address counts words, and the 6845
has no pixel panning, so there is no finer step on the CGA. Section 2.6 is
how the camera hides this.

### 2.4 Diagonal and big moves

A diagonal step is one column plus one row-pair: about **26k clocks,
5.4 ms**, predicted.

A **full window rewrite** is 8,000 words, about **690k clocks, about
145 ms**: roughly nine frames. That is used only for:

- starting a level;
- a respawn;
- a teleport.

It is always hidden behind a transition the player expects (section 6.4),
never paid in the middle of play.

### 2.5 Hercules

Excitebike's Hercules field: four banks; a row is 4 lines of 90 bytes (45
columns × 16 card px); R6 = 50 rows displayed.

- **Ring:** 4,096 words a bank, and the window uses 45 × 50 = 2,250. That
  leaves **1,846 words of slack**, so whole rows can be drawn many steps
  ahead.
- **Vertical step:** 4 lines. One step is 4 banks × 45 words = 180 VRAM
  words.
- **Horizontal step:** one word, 8 game px. The column has the same
  visible-alias problem as the CGA's and the same beam race. The Hercules
  blank is about 98 lines, so there is more room.

The CGA art converts by Excitebike's pair rule, which keeps one art set.

### 2.6 The camera

- **Vertical: leads the ball** in its direction of travel, about 40% of the
  screen ahead at speed, eased so that it moves at most 2 row-pairs a frame.
  At 2 lines a step this reads as smooth.
- **Horizontal: a dead zone** of the middle 160 px. When the ball leaves it,
  the camera **glides** one column every 2–3 frames until the ball is back
  inside, rather than snapping. Courses are designed so that the long
  descents are vertical and the lateral moves are short.
- **No vertical-only fallback is needed.** A course 320 px wide simply never
  scrolls sideways, so the 1942-style game is a *level design* inside this
  engine, not a second engine.

### 2.7 The HUD rides in the picture

The CGA has no split screen; line compare is a VGA register. The HUD is
therefore a **compact composited box**, 8 lines × 12 words in a corner, drawn
with the same box path as the ball (section 6.2). On a vertical step, the old
HUD scrolls into the slack that the incoming row overwrites anyway, so
**moving the HUD costs one box, about 8k clocks**. When nothing scrolled, the
HUD costs only the cells that changed, which is Excitebike's changed-cell
list.

The border colour (3D9h) is also free: for example, a flash when the time
gets low.

**Superseded by SPEC.md 128.14.5** (wave 4). The HUD is a 2-word x 6-line
clock panel INSET from the window's bottom-left corner, not an 8 x 12 box
in a corner, and it does not "scroll into the slack": the old copy leaves
the window only when a step's lines reach the panel's height, which a CGA
step never does (128.14.5.3 prices this placement and keeps the inset).
It is a fifth box group that composes every layer and lays the panel last,
and it defaults to REST on both cards because a box that follows the
camera costs 8.3 - 11.5k on the frames that already miss (128.14.5.8).

### 2.8 Smoother options, considered

| option | gives | why not now |
|---|---|---|
| Pre-shifted background (4 copies at 2-pixel steps) | 2 px horizontal steps | 4× the dictionary, and every step rewrites the whole window (about 145 ms). Dead |
| **VGA Mode X arm** | pixel-smooth scrolling both ways (offset register plus pixel panning) and 256 colours | a whole second renderer. 1942's VGA arm is the worked example. **A later wave**, not the 5150's |
| **160×100×16 "text graphics"** (80-column text, R9 = 1, character DEh) | **16 colours**, 2 px horizontal steps, a 16 KB ring with 8 KB of off-screen slack | **an IBM CGA SNOWS in 80-column mode** (docs/plans/CGA-SNOW-PLAN.md), so every VRAM write would have to wait for blanking. That leaves about 3.9 ms a frame at roughly 10 µs a byte: about 350 bytes. A row is 80 attribute bytes and the ball box about 40, so this is *just* possible but leaves no room for obstacles. **Parked as an experiment** (open decision D5) |

---

## 3. The course: authored in 3D, shipped as blocks

The course is authored as a **heightfield of tiles plus props**, in a text
format (`apps/bonanza/courses/*.bbc`; `apps/bounce/` is already BOUNCE,
the square, SPEC.md 112). A deterministic host tool,
`tools/bbcourse.py` (to be written), compiles it into three products.

**1. The picture.** The tool renders the course isometrically on the host,
in the CGA palette. Slopes are checkered surfaces, because the checker *is*
how a 4-colour picture shows a slope (see `bounce-bonanza/mock-cga.png`). It
then cuts the render into **8×8 blocks**, deduplicates them, and groups them
into 32×16 **metatiles**:

| data | size, predicted |
|---|---|
| block dictionary: 600–1,500 unique 8×8 blocks at 16 bytes | 10–24 KB |
| metatile table: 512 × 8 block ids | 8 KB |
| metatile map: 20 × 150 for a 640×2400 course | 6 KB |

Entering rows and columns are decoded from these and written straight into
the ring. The Hercules dictionary is derived from the CGA one by the pair
rule.

**2. The physics grid.** This is world-space data, not screen-space. A cell
is 16×16 ground units and holds:

- a **height** byte;
- a **shape** nibble: flat, 4 ramps, 4 corner ramps, the bowl and funnel
  quadrants, a wall, or a rail;
- a **surface** nibble: normal, ice, sand, mud, rough, boost, conveyor ×4,
  sticky, or bouncy;
- a **feature** byte: hazard, goal, checkpoint, tube mouth, or an obstacle
  id.

A 640×2400-pixel course covers 1.5 M ground units² (the isometric map has
Jacobian 1), which is about **6,000 cells, 12 KB**, or up to 24 KB stored as
a rectangle.

**3. The occluders.** The ball must be able to pass *behind* pillars,
arches, tube bodies and the near rims of a pit. The tool marks every block
whose pixels can occlude, and gives it:

- a **mask**;
- a **depth key**: the ground depth (x + y) and the top height of the
  geometry that drew it.

After the ball is composited into its box, any marked block that is in front
of the ball is laid back over it through its mask. That is typically 0–4
blocks, so it is cheap. Some depth cases are ambiguous: a block's pixels
can have several depths and tops. Wave 1's answer (SPEC.md 128.10.4.4) is to
split rather than flag: one record for each block, occluding cell and 2 px
band of tops, so every pixel is keyed to within 2 px. What the tool REFUSES
at build time is the cost - since wave 2 (SPEC.md 128.11.4), more than 4
records in one block or 128 in a block row, after an exact merge of the
records no reachable position tells apart (wave 1's 24 a block row and 8
laid were the wrong quantities) - so ambiguity and expense land as
authoring errors at build time, not glitches at run time.

Art is source (CLAUDE.md, "Building an app or game in waves", step 5).
Tile textures may be hand-drawn or generated. Whichever is used, the source
and the prompt are kept, and the guest gets them only through `bbcourse.py`.
No generation service is ever part of `make`.

---

## 4. The ball: the phase torus

**The trick.** Give the ball a surface texture *t*(u, v) that is periodic
with period P = 8 in both axes. Each pixel of the 16 px disc samples it
through a fixed spherical lookup:

    u = R·asin(x/R) + φx,  v = R·asin(y/R) + φy

Rolling the ball by (dx, dy) screen pixels adds (dx, dy) to (φx, φy),
modulo 8. Some consequences:

- **P² = 64 frames cover every phase**, so they cover *rolling in every
  direction*. The phase space is a torus, and any path through it is a
  sequence of adjacent frames, so a **change of direction never jumps**.
- Near the centre of the disc the lookup has slope 1. A surface feature
  there moves 1 px for each pixel the ball travels, which is rolling without
  slipping.
- Near the rim, asin compresses the texture, so features slide in from one
  limb and squeeze out at the other. That is what sells the sphere.
- It is a cheat: it is not a true rotation, and a feature never visibly goes
  round the back. At 16 px on a 4-colour screen, the prototype says the
  cheat holds.

**The guest does no maths.** It keeps `frame = (φy & 7) * 8 + (φx & 7)`.
Shading is baked into each frame on the host:

- the light comes from the upper left;
- the terminator is ordered-dithered to black;
- one white specular highlight;
- a 1 px dark rim separates the ball from any floor.

| | cost, predicted |
|---|---|
| 64 frames × 16 rows × 4 bytes | **4,096 bytes**, plus **one** 64-byte mask: the silhouette never changes |
| pre-shifted for the 4 pixel phases of a CGA byte (5 bytes a row) | **20,480 bytes**. RAM is cheap on a 640 KB machine. A runtime shift through a 256-word table is the fallback if the claim matters |
| Hercules | the same bytes: a game pixel is 2 card bits, so a byte is 4 game pixels, exactly as on the CGA |
| drawing it | the union box of the old and new footprints is 3 words × at most 20 lines = 60 VRAM words, **about 5k clocks to write**, plus about 3k to fill and compose in RAM. **About 1.7 ms**, every frame |

**The prototypes** are in `bounce-bonanza/`:

- `phases-{spots,checker,band}.png`: all 64 frames for each of three
  textures.
- `roll-*.gif`: the ball rolling a figure-eight over a slope at 30 fps.
- `mock-cga.png` and `mock-herc.png`: one still, as the CGA and the
  Hercules would show it.

On the prototype, **spots** read best as rolling. **checker** reads as a
beach ball. **band** is a "seam" ball, closest to *Extreme Pinball*'s look.
The texture choice is cosmetic: a texture is another 4 KB set, so **a
different texture can mean a different ball** (section 9).

**Height and bounce.** The ball is drawn at its ground point minus *z*. Its
**shadow** stays on the ground and is a checkered AND mask: every other
pixel turns black, which needs no fourth colour. The shadow normally shares
the ball's box. When the ball is high in the air it gets a second small box.

The gap between ball and shadow is the whole 3D cue for a jump. It costs one
extra AND pass. **Squash** on a hard landing is two or three silhouette
frames for a few ticks; it is optional, and its art comes from the same host
tool.

---

## 5. Physics: fluid, not stiff

### 5.1 Units and the step

**Ground units.** The isometric map is:

    sx = x − y,   sy = (x + y)/2 − z

So 1 ground unit is 1 px of screen x. A position is a 16-bit integer plus an
8-bit fraction, and a velocity is a signed 8.8 value.

**The fixed step** uses `FSXF_FASTTICK`'s sub-tick, which is Excitebike's
clock: **54.6 Hz**, built from PIT channel 0's countdown with no new
interface. The display waits for retrace, and the simulation catches up in
whole steps, so it is **identical on every adapter and machine**.

On kern_big, `FSXF_RATE` could give a finer step, as WireBall does. Wave 0
decides whether that is needed; kern_small would refuse it anyway.

### 5.2 Forces each step

    a  = g · slope(shape, sub-cell position)        the heightfield pulls
       + input · grip(surface)                      the player pushes; ice barely bites
       + surface push (conveyor, boost, fan, magnet field)
       − v · drag(surface)                          sand and mud drag; normal surfaces barely do
    v += a;  v = clamp(v, vmax(surface))
    move in at most 4-unit sub-steps; resolve walls and edges per sub-step
    (wave 1: not needed while the ground speed stays under the ball's
    radius a step, SPEC.md 128.10.7.2)

**Walls** reflect the normal component with **restitution e** (0.3 on
stone, 0.85 on a bumper rail). The tangential component keeps most of its
speed, so a glancing hit *steers* the ball rather than stopping it. This is
the "fluid" the brief asks for: the ball carves along walls and banks.

**Banks and bowls** are shapes whose slope varies inside the cell (a
quadratic per quadrant, from a table). The ball therefore circles a funnel
without any scripting.

**Air.** When the ground drops away faster than *z* follows, the ball is
airborne:

- gravity acts on *z*, and *x*/*y* keep their momentum;
- on landing, *v_z* is reflected with the surface's restitution, so the ball
  bounces;
- **a hard landing is a MECHANIC, not a punishment** (the owner's decision
  D4). What it does depends on the BALL (section 5.5): the rubber ball
  bounces back up, which is how it clears a gap or reaches a higher tier;
  the steel ball lands dead and is stunned for a moment; the glass ball
  shatters and respawns at the last checkpoint. Falling off a high edge is
  therefore something a course *asks for* with the right ball.

### 5.3 Controls that feel analogue on a keyboard

Each arrow key applies a *force* that ramps from 0 to full over about
150 ms, and decays when the key is released. Releasing the keys means
*coast*, not *stop*. `OSAPI_KEY_DOWN` (a held-key test by scancode) is the
input. Two buttons:

- **Grip:** brakes on the current surface, more strongly on rough surfaces.
- **Hop:** a small jump, once per landing, for minor gaps and for skipping
  an obstacle's beat. It is optional per course.

Directions are **screen-relative** by default, so "up" rolls up the screen.
An option rotates them 45° to the isometric axes, for players who think in
the grid.

### 5.4 Pointer devices

**The keyboard is the primary control (owner's decision D2).** A pointer
is a bonus for the end of the project, and a non-trackball mouse is a poor
fit for this style of game, so neither row below is planned before wave 6.

| device | how | kernel cost |
|---|---|---|
| **Mouse as a tilt stick** | the pointer's offset from the screen centre is the tilt vector, and the edge is full tilt. `OSAPI_MOUSE` answers in desktop coordinates inside a bracket (`apps/missile` already relies on this), giving ±320 × ±100 of analogue range on a CGA desktop | **none** |
| **Mouse as a trackball** (Marble Madness's arcade control) | the mouse's *relative* motion becomes impulse | **a new slot.** `OSAPI_MOUSE` is clamped to the screen, and `OSAPI_MOUSE_FEED` is for drivers only. Its resident cost is tens of bytes on every budgeted kernel, to be priced exactly if chosen. **Owner decision D2** |
| Game-port joystick (201h) | read once a frame. A full-scale poll is about 1.1 ms. §53.7 does not forbid the port | none. Optional; no game port is known on 5150 #1 |

**Superseded in part by SPEC.md 128.14.8** (wave 4). The mouse as a tilt
stick IS built in wave 4, not wave 6, and it is not centred on the screen:
the neutral is the pointer at the play's first frame and at each respawn,
the full range a quarter of the bracket display each way, read inside the
bracket after the mode set, and it CAPS the arrows' force level rather
than setting a tilt vector, so the log stays one key byte and one tilt
byte a step. The trackball and the joystick are unchanged here.

### 5.5 The balls: one engine, three materials (D4)

The ball type is a record of physics constants plus its own 4 KB texture
set, so the texture tells the player what they are rolling. Pads on the
course swap it.

| ball | restitution | hard landing | what courses use it for |
|---|---|---|---|
| **rubber** | 0.85 | bounces, keeping most of v_z | the bounce that clears a gap or climbs a tier: **required** on some routes |
| **steel** | 0.15 | stunned (a wobble, about 1 s) | heavy: breaks crumbling tiles, ignores fans, sticks to magnets, sinks in water |
| **glass** | 0.40 | **shatters**: back to the last checkpoint | light and fast with high grip; the precise, fragile route |

The table is a first guess and is tuned in wave 2. A fall's "hard" speed
is per ball as well.

### 5.6 Determinism buys three features

The inputs are **one byte a step**: 55 bytes a second, about 3.3 KB a
minute. Fixed-point physics with no frame-rate dependence replays exactly,
which gives:

- **ghost** runs against your best time;
- **attract-mode** demos;
- a **test harness** that drives a recorded run on MartyPC and asserts the
  position at each checkpoint. That is how the rows in section 11 hold the
  physics, rather than relying on remembered coordinates.

---

## 6. Drawing: lanes, boxes and TITHE's wheel

### 6.1 One write per pixel

Every moving thing is drawn by the **box** method, Excitebike's and 1942's:

1. Take the union of the old and new footprints.
2. **Fill** it in RAM from the block dictionary.
3. Compose the sprites in depth order.
4. Re-apply the occluders.
5. Write the box to VRAM **once**, in raster order.

Nothing is erased on the glass, so nothing flashes, and nothing is written
twice (CLAUDE.md, Performance rule 2).

Because the ring address is world-locked, anything that did not move needs
**no** redraw when the camera scrolls: the background, an obstacle between
two of its frames, and the ball's old footprint all travel with the scroll
for free.

### 6.2 Lanes

| lane | rate | contents |
|---|---|---|
| **scroll** | must happen | the entering row-pairs (off screen, written before the flip) and columns (raced ahead of the beam) |
| **ball** | every frame | the ball, its shadow, the HUD box when the HUD moved |
| **contact** | every frame | the **one** obstacle the ball is touching or riding (a moving platform, a spinner). It is promoted out of the wheel, because a platform drawn a frame late under a ball drawn on time *looks* wrong |
| **wheel** | credit | the other 2–6 animated obstacles (section 6.3) |
| **HUD cells** | when changed | time and score digits |

### 6.3 TITHE's wheel, adapted (SPEC.md 125.5 on `tithe-new`)

The design is TITHE's, kept intact:

- **A credit in µs a frame**, after the scroll, ball and contact lanes have
  taken their share. It is **calibrated at level start** by timing one row
  and *N* rows of a box off the PIT, which gives the arrival cost plus a
  per-row cost. It is **trimmed** when a frame overruns (one
  `OSAPI_GET_TICKS` a frame).
- **The wheel resumes where it stopped**, so no obstacle starves.
- **Clocks are the tick's, not the draw count's**: a windmill that misses
  its slot is drawn one frame late at the *correct* angle, never slowed.
- **Seeded phases**, so two identical windmills never turn in lockstep.
- **A rate cap** (`IDLEFPS`-style), so a faster machine does not spin the
  windmills faster than the art was drawn for.
- **At most two frames of credit banked.**
- **Every advance is unconditional.** No commit redraws the pose it already
  drew; TITHE's `titheframe` asserts the same.

**One rule this game adds: collision uses the TRUE phase, not the drawn
one.** The simulation knows where the blade really is, and the wheel only
decides when that becomes visible. At about 4 frames a second for a
background animation, the lag is at most one frame of the obstacle's own
cadence. Obstacles that can hit the ball are therefore designed with a
**telegraphed** beat (a blade sweeps over a full second, not in one frame),
so a drawn-late blade is never one that already hit you.

**Off-screen obstacles** keep their clocks and draw nothing. One that
scrolls into view is drawn by the scroll lane as part of the entering strip,
at its current phase. The wheel only has to animate it from then on.

### 6.4 Big camera moves are transitions

**Tubes:** the ball is invisible while it is inside, so the camera *glides*
along the tube's path at the scroll lane's top speed (section 2.2). The tube
takes exactly as long to travel as the glide does. The rumble on the speaker
covers it, and the exit is on screen before the ball comes out.

**Teleports and respawns** are cuts when the destination is off the
window. The 144 - 157 ms window rewrite is hidden by a two-step "iris" (a
black box closing on the ball) or simply by the CGA border flash. It is a
beat the player expects, not a hitch. A respawn whose cell is already on
the window is no cut: the ball is placed and the camera pans (SPEC.md
128.10.8, open question O5).

### 6.5 Predicted budget for one CGA frame (79.6k clocks)

| work | k clocks | note |
|---|---|---|
| simulation, 1–2 steps | 4–8 | cell lookups, slope table, sub-steps, obstacles' true phases |
| scroll: one row-pair | 8.4 | most frames during a descent |
| scroll: one column | 17–19 | rare: the dead zone and the glide |
| ball, shadow and contact boxes | 10–16 | |
| wheel credit | what is left, to 60 | about 2–4 obstacle commits |
| HUD cells | 0–5 | |

**Typical:** about 35–45k, so **60 Hz display looks reachable on the
CGA**. **Worst** (a column, a row-pair, contact and HUD in one frame): about
60k, still inside 79.6k.

Excitebike's governor (wait for retrace and feed the simulation the real
elapsed time; never throw a frame away) is the fallback when a frame
overruns. These are predictions; **wave 0 replaces this table with MartyPC's
cycle counts.** A real card's wait states are a field question
(docs/FIELD-MACHINES.md).

---

## 7. Memory

| claim | KB, predicted |
|---|---|
| package code and bss | 25–35 |
| course: block dictionary, metatiles and map | 24–38 |
| physics grid | 12–24 |
| occluder masks | 2–4 |
| ball: 64 frames × 4 shifts, mask, squash | 21 |
| obstacle art (6 kinds × 4–8 poses) | 8–16 |
| sound, text and front end | 4 |
| **total while playing** | **about 100–140 KB** |

That fits the 5150's 640 KB comfortably. It also explains the kern_small
refusal: kern_small's heap cannot hold it.

Following 1942's pattern, the course art is **fetched into claims on the
desktop before the bracket**, so that a refusal can still draw its toast
(§53.7). On kern_mega a claim is an LDT selector, so derived segments come
from `OSAPI_SEG`.

Every package region declares `OS88_REGION_MOVABLE` (§66.6.1.1). The game
holds no segment words that point inside itself, so the relocation proc is
a `ret`.

---

## 8. The mini-golf props, and the tube

Courses are built from **props**. Each prop is static art in the course
render, plus cells in the physics grid, plus optionally one animated
obstacle.

| prop | how it plays | 5150 cost |
|---|---|---|
| **Tube** | enter a mouth at any speed. The ball disappears, the camera glides along the path, and the ball comes out of the far mouth. Three kinds: **keep** (speed kept, direction set by the mouth), **launch** (a fixed exit speed, a cannon) and **drop** (out of a high mouth onto a lower tier) | none while hidden; the glide is the scroll lane |
| **Windmill** | blades sweep across the tunnel, so the ball must time its entry. A blade hit knocks the ball back with restitution | one wheel obstacle, 8 poses |
| **Loop-de-loop** | a scripted arc drawn as a *visible* path animation of the ball. Enter faster than v_min and you go round; slower, and you roll back down. A momentum gate | the ball box follows the path |
| **Volcano / hump** | a steep cone with the cup on top: too slow and you roll back, too fast and you fly off | heightfield only |
| **Bank and half-pipe** | carve round a corner without losing speed | heightfield only |
| **Moat bridge** | a narrow plank over water; the sides are hazards | heightfield only |
| **Funnel / drain** | the ball spirals into the centre, which is a tube mouth | heightfield only, plus a tube |
| **Clown mouth / castle gate** | one of three openings, each to a different tube exit (a shortcut, a dead end, or bonus points) | static |
| **Bumper** | a radial kick of fixed speed, which flashes and scores | one wheel obstacle, 2 poses (the contact lane while lit) |
| **Spring pad** | sets v_z high to reach an upper tier; the shadow sells the height | static, plus the second shadow box |
| **The cup** | the goal. The ball must arrive slower than a capture speed, or it lips out over the rim | static |

**Superseded in part by SPEC.md 128.14.4** (wave 4). What wave 4 builds of
this table: the CUP (a grounded ball under the capture speed holes out; a
faster one lips out with a small pop and rolls on), the SPRING pad, the
MOAT BRIDGE as a one-tile plank over VOID (no water), and the CLOWN MOUTH
as three KEEP tubes behind a wall whose exits are the route, a shortcut and
a dead end (no bonus points: the game is timed, O39). The loop, the
volcano, the banks, the half-pipe and the funnel are not built (O49).

---

## 9. More mechanics that fit the style and a 5150

These are ordered roughly from cheapest to most ambitious. Each is costed
against the lanes above.

1. **Ball swaps.** *Promoted into the core game by D4: section 5.5.* A
   fourth ball, **sponge** (light, so fans and wind push it much harder), is
   still an idea.
2. **Surfaces as rules:** ice, sand, mud, grates that slow you only
   sideways, and boost chevrons. These are physics-grid nibbles only, with
   **zero drawing cost**.
3. **Conveyors and fans.** Conveyors are a surface nibble plus a wheel
   obstacle to animate the arrows. A fan is a force field that blows harder
   on a sponge ball than on a steel one.
4. **Switches and gates.** Rolling over a plate opens a gate elsewhere.
   That is a one-time redraw of a few blocks. Doors can be timed (the gate
   shuts again on a clock), which makes a route puzzle.
5. **Crumbling tiles.** A tile breaks once a steel ball, or any ball after a
   delay, has passed. Its blocks are swapped once for "hole" blocks and its
   cell becomes a hazard.
6. **See-saws and tilt plates.** A plate tips toward the side the ball is
   on. Three poses on the contact lane; the cell's shape follows the pose.
7. **Magnets.** A field pulls a steel ball onto a rail, and does nothing to
   rubber. Physics only.
8. **Pinball zone.** A walled section where **flippers** answer the grip
   key. Two contact-lane obstacles, plus bumpers. This is the closest nod to
   *Extreme Pinball*.
9. **Golf mode, on the same courses.** *D3: a possible SECOND game on
   this engine, after the first, which is direct control.* Instead of continuous control, you
   **aim and set power**, and the ball then rolls under physics alone.
   Strokes are scored against par. This mode suits a slow machine very well
   (input is rare, and the wheel gets every spare cycle), and it re-uses
   every course and prop. It is **cheap to add once the run mode exists, and
   could be the better game**.
10. **Combo scoring, the "Bonanza".** Bounces, bumpers and airtime
    *without touching the ground* chain into a multiplier. It rewards the
    fluid physics directly.
11. **Gems on the risky line.** Collectibles placed where the fast line is
    dangerous. Each is drawn in the static background, and taking it is a
    one-time block swap.
12. **Ghost race against your best time** (section 5.6). The ghost is drawn
    as a dithered ball on the wheel, at a lower rate.
13. **Link race over a null modem**, as WireBall and WireFleet do
    (`apps/os88link.inc`). Each machine renders its own view, and the other
    player's ball is a ghost fed at 18 Hz. The serial service in the bracket
    follows WireBall's hook (§53.2.2; kern_big's `FSXF_RATE`), or
    `os88link`'s polling where the hook is refused.
14. **Global tilt switches.** A switch tilts the *whole table*: a global
    gravity bias added to the slope term. The ball suddenly wants to go
    another way, and the art does not change, because the effect is pure
    physics.
15. **Weather.** Gusts of wind across an exposed bridge, telegraphed by a
    flag obstacle on the wheel.

---

## 10. Sound

*Superseded by the owner's brief of 2026-11-13 - the speaker AND the AdLib,
music and an impact a ball: SPEC.md 128.20 and
[BOUNCE-BONANZA-SOUND.md](BOUNCE-BONANZA-SOUND.md). The original plan:*

The PC speaker only, through `apps/os88spkfx.inc` and the `snd` slots. Both
are legal in a bracket (§53.7); channel 2 is never touched directly.

| sound | when |
|---|---|
| **Rolling** | a click whose rate follows speed, and whose tone follows the surface (rough surfaces click faster, ice is silent) |
| **Bounce** | a short downward sweep, pitched by impact speed |
| **Tube** | a rumble for the whole ride |
| **Bumper** | a bell |
| **Cup** | a little fanfare |

Excitebike's engine sound (SPEC.md 102.5) is the precedent for a continuous
pitch tied to speed. `SOUND.DRV`'s FM output, where it exists (5150 #2's
Picomem), is a later polish, never a requirement.

---

## 11. Waves and stories

Each wave follows CLAUDE.md's "Building an app or game in waves":

- it is one reviewable push to one draft PR;
- it is checked on the host, and the rows it touched are **named**;
- the soak union and `test-full` run **once, after the last wave**.

The SPEC.md section is written before wave 1's code. It takes the next free
number at that time; the last section on `elendilon` today is 127.

**Wave 0: the spike (go/no-go).** A throwaway package with a 2D ring and a
generated test course, with no art pipeline and no physics beyond the arrow
keys.
- [x] The CGA ring: vertical steps into the slack, columns raced after the
      retrace, and a diagonal. The ring holds what the formula says
      (decoded off the card on MartyPC, as Excitebike's `excitebike_video`
      does). *Evidence: `bonanzaring`, all 8 directions, 0 bad pixels, at
      both the presented frame and the retrace start; its red arms go red.*
- [x] The same on the Hercules field. *Same row, same result.*
- [x] The phase-torus ball at the 4 pre-shifts, with its box. *Looked at
      on both cards; the Hercules mid tone is stripes, not the course's
      checker (SPEC.md 128.3).*
- [x] A MartyPC cycle count for each item in section 6.5's table. This is
      one measurement, taken once, because it *decides the design*: 60 Hz
      or 30 Hz, and whether `FSXF_RATE` is needed. *Decided: the full
      refresh on both cards, and `FSXF_RATE` is not needed. The table is
      SPEC.md 128.8.*

**Wave 0b: the camera and the optimisation round** (SPEC.md 128.9; the
review's findings 7, 9, 11, 12, 13; the numbers are SPEC.md 128.8's). The
owner's first play (86Box, CGA): slow scrolling is jerky, fast scrolling is
smooth.
- [x] Three camera modes, `C` to cycle: GLIDE (rest or pan fast, with a
      lead; the default), FOLLOW (velocity-matched, even cadence), TRICKLE
      (wave 0's, for the A/B). The owner picks by feel.
      *Cadence measured per mode and card (SPEC.md 128.9): at a slow ball
      FOLLOW steps as often as TRICKLE; only GLIDE turns the hops into pans.*
- [x] The Hercules ball takes the course's checker for its mid level.
      *Selfcheck: 0 of 24,596 mid pixels wrong; looked at, zoomed.*
- [x] Box compose (23.5k clk, the largest working part): column-major fill
      with a `movsw`/`add di` chain, an unclipped word-wise ball path, no
      MUL.
      *23.5k -> 11.5k clk on both cards (SPEC.md 128.9's table).*
- [x] The column writer: find the wrap row once, unroll per block.
- [x] The row writer: word columns outermost (the two CGA misses are
      two-row frames: rows 19k there).
      *A row ~9.4k -> 7.5k (CGA), ~19.2k -> 13.7k (Hercules); 0 misses.*
- [x] `S` kept incrementally; `rb*R` by shifts in `bz_row`, `bz_col`,
      `bz_boxw`.
- [x] Do not write the overlap of two boxes twice; do not re-compose an
      idle ball.
- [x] The box at window row 0 (SPEC.md 128.2 rule 4's open corner).
      *Built; the wave-0b course cannot reach it (SPEC.md 128.9 item 6), so
      `bz_late` = 0 is true by construction until a later wave's physics
      reach the window's first row - that wave owes it a probe that does.*

*Open, found by wave 0b's review:* each ball part carries 15,360 bytes that
can never be drawn (`bz_boxc` takes shift `s = px & 3`, already fixed by the
frame's `px & 7`, so only 64 of the 4 x 64 shift/frame entries are reached).
Indexing the frames by `f` alone (`16 + 320 + 64 x 80` bytes a part) saves
about 15KB per heap claim and the disk bytes of both parts, and drops the
`5040 s` term from `bz_boxc`; SPEC.md 128.3 pins the part's size this round,
so it is a later wave's change. GLIDE's "fast" test is `|v|` against the
full refresh's step rate (SPEC.md 128.9); the ball's travel a frame is the
rate-proof form, a later wave's change made with the route re-checked.

**Wave 1: the course pipeline and physics v1** (the contract is SPEC.md
128.10, written before the code and revised after three review lenses).
Decided there, against this plan: the map stays FLAT, one word a block
cell, and metatiles (section 3) are not taken (SPEC.md 128.10.1); a course
is two PARTS, one a card, each carrying the picture, the occluders AND the
physics grid - one fetch and one claim a launch, as wave 0b - and not a
data file (open question O1, which a file's hostile bytes make a priced
validation pass, not a free addition); the physics cell is one tile in
ground units, the ball is a CIRCLE pushed out of walls along the contact's
normal, it leaves the ground when the floor falls away faster than gravity
and keeps the floor's vertical speed, and a ball two tiles past every solid
cell is respawned (SPEC.md 128.10.7); ramps are at most 4 half units a tile
(2 along both axes) so the camera can follow, and the speed caps are set so
D4's rubber rebound can clear 4 units (128.10.7.2), and the ground cap
(1.5 gu a step) is under the ball's 6 gu radius, so plan 5.2's sub-steps
are not needed; occluders are records cut per (block, cell, 2 px band
of tops), laid back over the NEW footprint's blocks only, with a margin that
keeps a rolling ball whole on the ground in front of it (SPEC.md
128.10.4.4); wave 1 is the wave that probes the row-0 box (SPEC.md
128.10.11.2). Every cost below is PREDICTED until the final pass.
- [x] **1.1 A course is text.** `apps/bonanza/courses/bench.bbc` ("Proving
      Ground", `K = 0`: wave 0b's test course in the format of SPEC.md
      128.10.3, its ramps inside the limits, the return leg's steps made a
      climbable ramp, and its holes off the autopilot's legs)
      and `first.bbc` ("First Roll", `K = 1`, the worked example and the
      course Enter plays) compile with ONE `tools/bbcourse.py` run over the
      Makefile's explicit `BZ_COURSES` list (never a glob), which writes
      `bzcourse.inc` whole, its `OS88_PART` rows included. Everything under
      `apps/bonanza/courses/` ships; the selfcheck's malformed inputs are
      strings inside the tool. *Verified: `bonanzacourse` items 1 and 2 -
      two compiles byte-identical, and every grammar and bound refusal fires
      on its bad line, reserved statements included.*
      *Final pass: `bonanzacourse` ok - two compiles byte-identical file for
      file (`BZ0C`/`BZ0H`/`BZ1C`/`BZ1H.BIN`, `bzcourse.inc`), and all fourteen
      refusals fire on their lines, reserved statements included.*
- [x] **1.2 The picture comes from the course.** The renderer MOVES from
      `tools/bonanza_assets.py` into `bbcourse.py` (the palette and the
      Hercules checker are imported, not copied); `BZ<K>C.BIN` and
      `BZ<K>H.BIN` in `BZC1` (absolute map offsets, `MAPSH`, `ROWB`,
      occluders, the grid); `Y0` the least that holds every reachable
      footprint, the reach bounded by the OPEN rule and the launch apex.
      The tool checks every part it wrote and prints the sizes and counts
      SPEC.md 128.10.10 quotes. *Verified: `bonanzacourse` items 3 and 6 (the
      decode back on both cards, with its negative control); the `--png`
      previews looked at on both cards.*
      *Final pass: `bonanzacourse` items 3 and 6 on both courses (the moved
      map word caught); the `--png` previews looked at on both cards;
      `bonanzaring`'s glass equal to the picture on both cards. Parts 54,214
      (`BENCH`) and 10,614 (`FIRST`) bytes a card, over SPEC.md 128.10.10's
      predictions (its measured table).*
- [x] **1.3 The ground knows its shape.** The grid in `BZG1` inside each
      course part: heights, slopes, kinds (4 - 15 reserved for a later
      wave's shapes), NEAR and OPEN void, SAFE and OCC, the start and the route;
      the occluder records and masks inside their bounds (24 a block row, 8
      laid at any position). *Verified: `bonanzacourse` items 4 and 5 - the
      grid's plane equals the drawn geometry at every integer point, and the
      records' composite equals the per-pixel buffer's at every reachable
      cell in both air states, with its negative control.*
      *Final pass: `bonanzacourse` items 4 and 5 hold (`BENCH` 2,312 positions
      and 1,940 at the fractional-height line, `FIRST` 276 and 252, 0 differ;
      the lowered depth and the cleared OCC flag caught). NOT ticked: the
      bounds are not met - 79 / 29 on `BENCH` and 32 / 23 on `FIRST` against
      24 / 8, refused provisionally at 96 / 32 - and the choice is the owner's
      (SPEC.md 128.10.12 O8).*
      *Closed by wave 2's story 2.2 (the owner's O8: the exact merge and the
      per-BLOCK bounds of SPEC.md 128.11.4.2, at most 4 records a block and
      128 a block row): `bonanzacourse` ok in wave 2's final pass on all
      three courses, the bounds met by the merged records.*
- [x] **1.4 The ball part loses what it never drew.** `BZB1`, 64 frames each
      at shift `f & 3`: 5,456 bytes a part against 20,816. *Verified:
      `bonanzaassets`; `bonanzaring`'s glass on both cards.*
      *Final pass: `bonanzaassets` ok (5,456 bytes a part, every frame at
      shift `f & 3`, the checker 0 wrong); `bonanzaring`'s glass on both
      cards.*
- [x] **1.5 The ball rolls on the course.** `bzphys.inc`: the guest fetches
      the course and the ball and plays physics v1 - slopes pull, walls push
      the ball out and it slides along them at any angle, a fast ball flies
      off a lip and lands with its drop and impact speed recorded, a pit
      puts it back on the last SAFE cell (a cut only when that is off the
      window), and the goal ends the play with `Finished in <s.hh> s` on the
      face. Space and Left Shift are reserved for wave 2's Hop and Grip.
      No guest-side header check: the parts are checked at build time.
      *Verified: `bonanzacourse` item 7 (the scripted runs on `FIRST`, with
      red controls); `bonanzaphys` - the guest's state equals
      `bbcourse.Physics` at every frame of the benchmark on both cards, and
      the poked pit, lip, rail and goal scenarios on `FIRST`, with red arms
      `slope`, `respawn` and `takeoff`; and one boot to look on each card:
      the ball rolling behind the traverse's blocks and dropping into a pit
      behind its rim.*
      *Final pass: `bonanzacourse` item 7 with both red controls;
      `bonanzaphys` ok - the guest equal to the model at every frame of the
      benchmark (1,091 steps CGA, 1,286 Hercules, one trajectory) and in the
      pit, lip, rail and goal scenarios on both cards (`Finished in 0.45 s` /
      `0.54 s` by the formula); red arms `slope`, `respawn`, `takeoff` each
      red at its own leg. The look boots were the physics and occluder stages'
      (the pit, and the traverse's block on the Hercules).*
- [x] **1.6 The ball goes behind things.** The occluder pass in the box
      compose, run only on an OCC cell, over the new footprint's blocks
      only, each row's walk stopped past the footprint; the idle test
      compares the ball's cell row, height and air flag too. *Verified:
      `bonanzaring` with the oracle laying the records back, at least one
      checked frame with a record laid, red arm `occ`; `bonanzacourse` item
      8 prints the bench route's OCC share and records laid.*
      *Final pass: `bonanzaring` - 6 checked frames a card hiding ball pixels
      behind a record (69 px), 132 records laid on the CGA's benchmark and 455
      on the Hercules'; red arm `occ` red on both cards; `bonanzacourse` item
      8: 23% of the route's steps on an OCC cell, 1.11 laid on average.*
- [x] **1.7 Nothing is left behind.** Esc, F, Alt+Enter, the benchmark's
      end and the goal each drop both claims; a refused fetch drops what was
      fetched. *Verified: `bonanzaexit` on both cards - every part row with
      `OP_FETCHED` clear, `op_seg` 0 and `OP_R_ZKB` back to its pre-launch
      packed length, and the instance's claims as before the launch read
      through `tools/heapmap.py` - red arm `leak`; the desktop refusal by
      review.*
      *Final pass: `bonanzaexit` ok on both cards and all five ways out -
      every row unfetched with its packed length back, the claims as before,
      two more inside every bracket; red arm `leak` red at the goal and only
      there. The refused fetch by review (`jc .drop`). Found by `bonanzamega`:
      `bz_launch` now loads ES with its own segment before the drops
      (kern_mega's #GP at `op_drop`'s `pop es`).*
- [x] **1.8 The benchmark on a real course.** B drives the bench course
      under physics in GLIDE; the route re-chosen with a host model of GLIDE
      (not kept) so all eight step directions occur at least five times on
      both cards. *Verified: `bonanzaring` (every direction on the glass)
      and `bonanzaperf` (the floor, the instruments, the OCC frames and the
      two-box frames) in the final pass, with the A/B leg against wave 0b;
      SPEC.md 128.10.9's predictions - busy about 45 - 48% of a CGA refresh
      and 39 - 41% of a Hercules one - get their measured column.*
      *Final pass: `bonanzaring` every direction on both cards; `bonanzaperf
      --ab` - busy 46.5% of a CGA refresh (59.96 Hz) and 39.4% of a Hercules
      one (50.87 Hz), inside 128.10.9's predictions, 0 misses, against wave
      0b's 43.3% / 37.0% on its own course (SPEC.md 128.10.9's measured
      table).*
- [x] **1.9 The row-0 box, reached at last.** A poked probe holds the
      ball's box at window row 0 while GLIDE pans up and across (play
      reaches row 0 only in the air, SPEC.md 128.10.4.1). *Verified: `bonanzaring`'s probe - at least five frames
      a card with the boxes at window row 0 and an entering column, the
      card equal to the picture at `bz_tf` and `bz_presented`, `bz_late` 0 -
      and its red arm `row0` (the whole column first, item 6's order
      undone) going red.*
      *Final pass: `bonanzaring`'s probe - 11 frames on the CGA and 7 on the
      Hercules with the boxes at window row 0 and an entering column, card =
      picture at `bz_tf` and `bz_presented`, `bz_late` 0; red arm `row0` 11
      late of 11 on the CGA (the CGA only: the Hercules' blank holds the whole
      column). It failed first: the guest's beam reckoning, a FASTTICK
      interrupt and an overrunning probe, all measured and fixed - and the
      probe moved to the top clamp, where play reaches row 0 (SPEC.md
      128.10.11.2, 128.9 item 6).*
- [x] **1.10 kern_mega, built and RUN.** Every new segment is a part's own,
      used whole (the grid at `GRIDOFF` inside the course part), nothing
      written through CS and no patched immediate (the map stride is read
      from the part's header), no `PKG_MEGA` arm (SPEC.md 128.10.6.4).
      *Verified: `bonanzamega` in the final pass - kern_mega on 86Box's
      `286-mega-multimon`, the window on its Hercules display, the
      benchmark and a play: no fault, no leak; red arm `segadd`.*
      *Final pass: `bonanzamega` ok after the ES fix - benchmark and play on
      86Box's Hercules, no part fetched and no claim left after either, no
      exception charged to the package; red arm `segadd` red with a #GP.*
- [x] **1.11 The record.** README, the face's title line, `make help` lines
      for `bonanza-course-check` and the new rows, the Bonanza row in
      docs/HEAP-CLAIMS.md (both claims pinned, bucket C; the
      `tests/pins.txt` lines `bz_cseg` and `op:BZ_P_BALC` stand), SPEC.md
      128.10's measured tables, the diary's wave-1 entry, and
      `docs/INDEX.md` regenerated. *Verified: `make` (the doc gates) and
      `tools/os88index.py --check`.*
      *Final pass: README's status, the face's title, `make help` (`os88help
      --check`), the HEAP-CLAIMS row, SPEC.md 128.10.9 and 128.10.10's
      measured tables, the diary's entries, `docs/INDEX.md` current
      (`os88index.py --check`), `checkdocs` 0 problems.*

**Wave 2: feel** (the contract is SPEC.md 128.11, written before the code
and revised after three reviews of it).
Decided there, against this plan: the ball is picked on the desktop (`M`,
starting from the course's own `ball`), and section 5.5's swap pads are wave
4's; a landing is judged against the floor's own rate, and a rebound is at
most `e` times the ball's downward speed, so a bounce never climbs above the
height its energy came from - a rubber-only route is a drop and a bounce to
a ledge BELOW it, and climbing stays ramps and the spring pad (SPEC.md
128.11.5.3); Space at a contact replaces the rebound with at least a Hop but
never adds to it, so it cannot pump a bounce and the reachable set stays
bounded (SPEC.md 128.11.4.4); an airborne ball lands on a floor up to 4 px
above it, as a rolling one climbs it; a goal is a finish line crossed in the
air too; the materials' constants and each material's force, drag and brake
on each surface are generated tables, PROVISIONAL until the owner has rolled
them; section 5.2's restitution is a stone wall's per material and a bumper's
for every ball; Grip's Left Shift is read from the BIOS's shift flags,
because the kernel's key-state map takes a 101-key keyboard's fake shifts as
Shift (O19); section 4's shadow is skipped where the floor can hide a
grounded ball (`OCCG`), and kept out of a box of its own while the ball's
cell can be hidden; open question O8 is answered by building the Hercules
table and part on the guest (one part a course and one a ball on the disk),
an exact merge of the records and a per-BLOCK bound, not by narrowing the
reachable set to pits (option c, measured and declined: SPEC.md 128.11.4.5).
Sound (section 10) stays wave 4's. Every cost and size below is PREDICTED
until the final pass; the rows run once, after the last batch.
- [x] **2.1 One part a course, one a ball.** The disk carries the CGA's
      course blocks and ball frames only; a Hercules launch builds `BZ_HTAB`
      (512 bytes) in the idle box buffers and translates the parts in place
      through it before the bracket - no table in the image. Part rows:
      three balls, then one a course. `BONANZA.O88` predicted 47 - 51KB
      against wave 1's 64,509, with a third course and two more balls.
      *Verify: `bonanzaassets` - `bbcourse.htab()` equal to `herc_pair`, the
      rubber part translated equal to wave 1's Hercules ball part, with red
      controls; `bonanzaring`'s Hercules glass checks the guest's built table
      (red arm `htab`); `bonanzaexit` over the new rows; `bonanzamega` builds
      and translates on kern_mega (red arm `hxcs`); the package size printed
      by the build.*
      *Final pass: `bonanzaassets` ok (`htab()` equal to `herc_pair`,
      the rubber part translated equal to wave 1's Hercules ball part,
      its four red controls); `bonanzaring`'s Hercules glass equal to
      the picture through the guest's BUILT table, red arm `htab` red
      there; `bonanzaexit` ok - 19 launches a card, each fetching row 3
      + K and its ball's row and dropping both; `bonanzamega` ok - the
      Hercules bracket on kern_mega builds and translates through the
      parts' own selectors with no fault, red arm `hxcs` red with an
      exception charged to the package. `BONANZA.O88` 47,334 bytes
      against wave 1's 64,509 (predicted 47 - 51KB).*
- [x] **2.2 Occluders the courses meet (O8).** Records of one block that no
      reachable position tells apart are merged (exact); the bounds become
      at most 4 records a block and 128 a block row, which `BENCH` and
      `FIRST` meet before the merge (`BENCH` with no headroom on the block
      bound); the provisional 96 / 32 go; the new grid flag `OCCG`; the
      reach with the Hop's launch and bounces bounded by energy, iterated to
      a fixed point, with discrete flights. *Verify: `bonanzacourse` items
      2, 4, 5, 6 - the merge lays the same pixels as the unmerged records
      for every query (negative control: a forced merge of differing
      verdicts fails), the refusals fire, the counts, rounds and `Y0`'s
      source printed (measured on the host with the contract's rule:
      `BENCH` `Y0` 156, 2,938 records merged to 2,645; `FIRST` `Y0` 36, 334
      to 290).* This also closes wave 1's story 1.3.
      *Final pass: `bonanzacourse` ok - the merge exact on every course
      (`BENCH` 2,938 to 2,645 records, 443,661 queries; `FIRST` 334 to
      290; `TRIAL` 1,079 to 786), the forced-merge control and every
      refusal firing; `Y0` 156 / 36 / 50, the reach settled in 5 / 2 / 3
      rounds; OCCG never without OCC and set wherever a grounded ball
      lays a record.*
- [x] **2.3 Walls give some of it back.** Restitution at the edges, the
      corner and the fallback - a stone wall's per material (rubber 0.38,
      steel 0.13, glass 0.25), a bumper rail's 0.90 for every ball - with a
      minimum that stops a pushed ball chattering; the wall-edge test made
      symmetric (wave 1's P1: no more creep against east and south walls).
      *Verify: `bonanzacourse` item 7 (the rail's rebounds and time to rest
      per material, a bumper's, the east wall resting at 10.00 like the west
      at 6.00); `bonanzaphys`'s `rail`, `bumper` and `eastwall` scenarios on
      both cards, red arm `edge`.*
      *Final pass: `bonanzacourse` item 7 ok; `bonanzaphys` ok - `rail`,
      `bumper` and `eastwall` equal to the model at every frame on both
      cards; red arm `edge` red (the broken model parts from `eastwall`
      at step 15).*
- [x] **2.4 Keys that feel analogue.** The arrows' force ramps over 146 ms
      and coasts on release (a quick re-press resumes); Hop on Space (from
      the ground, or at a contact inside its 110 ms window, so Space at a
      Hop's landing hops again); Grip on Left Shift, read from the BIOS's
      shift flags (brakes and carves, and catches a bounce); half-force air
      control; an airborne ball lands on a half-unit step instead of
      bouncing off it. *Verify: `bonanzacourse` item 7 (each material's
      ramp, the Hop's rise, window, contact Hop and step-up, Grip's stop, the
      catch); `bonanzaphys`'s `ramp`, `hop`, `hopagain`, `stepup`, `grip`
      and `catch` scenarios, red arm `airwall`; `bonanzareplay`'s injected
      log covering every key bit; `bonanzamega`'s grey arrows with NumLock
      on leave Grip clear (red arm `shiftmap`).*
      *Final pass: `bonanzacourse` item 7 ok; `bonanzaphys` ok - `ramp`
      with each ball, `hop`, `hopagain`, `stepup`, `grip` and `catch` on
      both cards, red arm `airwall` red; `bonanzareplay` ok - a
      real-keys play and three injected logs covering every key bit;
      `bonanzamega` ok - a play with Hop and Grip logged (130 steps,
      bits 4 and 5) and replayed to the same end on kern_mega. NOT
      judged: red arm `shiftmap` and the fake-shift case, a SKIP on
      86Box (its keyboard sends no fake shift and its automation drops
      an explicit E0 2A); the BIOS shift-flag read is right by
      construction (SPEC.md 128.11.7.2) and still wants a 101-key
      machine to prove it.*
- [x] **2.5 Three balls, and a hard fall is a mechanic (D4).** Rubber
      bounces (a 6-unit drop rebounds 3.7 units and carries 4.8 tiles, then
      settles in 3.2 s), steel is stunned and stopped dead for a second by a
      fall of 2 units, glass shatters on a fall of 3 and comes back on its
      last SAFE cell, each judged on the impact relative to the floor so a
      Hop down a ramp is not a fall; steel is the heavy ball (slow to start,
      a 13-tile coast), glass the light one (quick, a 341 top, stops in under
      a tile); `M` picks the ball on the desktop, `N` the course (its ball
      with it). *Verify: `bonanzacourse` item 7 on `TRIAL` with all three
      balls; `bonanzaphys`'s `bounce`, `stun`, `shatter` and `ramphop`
      scenarios with red arms `bounce`, `stun`, `shatter`, `absimpact`; one
      boot to look on each card at each ball's landing.*
      *Final pass: `bonanzacourse` item 7 on `TRIAL` with all three
      balls ok; `bonanzaphys` ok - `bounce`, `stun`, `shatter` (its
      respawn's cut) and `ramphop` (steel, glass) on both cards; red
      arms `bounce`, `stun`, `shatter` and `absimpact` each red at its
      own scenario. The look boots were the physics stage's (rubber's
      bounce chain, steel stunned and glass shattered on `F`, both
      cards).*
- [x] **2.6 Floors with a character.** Ice (no drag, a push of 1 for every
      ball), sand (a 32nd drag, a push of at least 2), a bounce mat (every
      ball bounces, none is hurt: a trampoline, 5.3 s from a 6-unit drop
      unless Grip or Space ends it), each drawn with its own top; every
      material moves on every surface. *Verify: `bonanzacourse` items 2, 4
      and 7 (every pair from rest; steel stopped on ice leaves it);
      `bonanzaphys`'s `ice`, `sand` and `mat` scenarios; the `--png`
      previews looked at on both cards.*
      *Final pass: `bonanzacourse` items 2, 4 and 7 ok; `bonanzaphys` ok
      - `ice`, `sand` and `mat` equal to the model on both cards. The
      previews were looked at in the host stage.*
- [x] **2.7 The ball looks like what it is, and where it is.** Three looks
      inside one black rim (rubber's spots, steel's seam band, glass you can
      see the course through); the spin's vertical phase off the GROUND, so
      a bouncing ball does not turn; a checkered SHADOW on the floor under a
      ball in the air; squash on a hard landing, drawn only while the ball
      is at its floor; a dazed wobble while stunned; a four-frame shatter.
      *Verify: `bonanzaassets` (`BZB2`, every material, the black ring on
      both cards, red controls); `bonanzaring`'s oracle with the shadow, the
      sprite and the ground phase on both cards, red arm `shadow`; the look
      boots, with each ball previewed over a cyan tile, a white tile, a ramp
      and a magenta face on both cards.*
      *Final pass: `bonanzaassets` ok (BZB2 for every material, the
      black ring on both cards, five red controls); `bonanzaring` ok -
      the oracle with the shadow, the sprite and the ground phase equal
      to the card on both cards, 14 / 8 checked frames with a shadow box
      of its own and 6 / 4 with the shadow inside the ball's box (CGA /
      Hercules); red arm `shadow` red on both cards once the ring
      checked the merged-shadow frames it breaks. The look boots were
      the engine stage's.*
- [x] **2.8 A ball and its shadow, drawn once, in raster order.** Up to four
      boxes (the ball's and the shadow's, old and new), each composed with
      everything that meets it, written interleaved with the entering column
      in raster order; the occluder pass decides once a frame and lays into
      every box; no shadow box of its own while the ball's cell can be
      hidden; lateness checked for every box, interrupts off for the first
      only; the idle test knows the sprite and the shadow. *Verify:
      `bonanzaring`'s TRIAL leg - card equal to the oracle at `bz_tf` and
      `bz_presented`, a frame with the shadow in its own box and one with
      three or more boxes, the order check on every frame, one pass a frame
      (red arms `boxfirst`, `pass2`); the multi-box row-0 probe (red arm
      `late2`); `bonanzaperf`'s TRIAL leg counts the boxes.*
      *Final pass: `bonanzaring`'s TRIAL leg ok on both cards - card
      equal to the oracle at `bz_tf` and `bz_presented` on every checked
      frame, the raster order on 1,199 of 1,199 frames, one pass a
      frame; the frame of three boxes is MADE (the route has none: the
      ball poked across the window at frame 301 and checked); the probe
      ok - 36 CGA boxes timed, `bz_latechk` agreeing with the cycle
      counter on all 36, the first box on time on every frame. Red arms
      `boxfirst`, `pass2` and `late2` red (`late2` after the probe's
      split frames). Found and fixed: a CGA row-0 box after a sync found
      already high was late; `bz_vr` now takes the next rise (SPEC.md
      128.11.10.3, +47 bytes). `bonanzaperf`'s TRIAL leg: boxes 0 / 1 /
      2 on 733 / 430 / 36 CGA frames.*
- [x] **2.9 A course that needs the rubber ball.** `TRIAL`, "Bounce Trial"
      (`K = 2`): a 6-unit drop onto a floor at least 4 tiles deep and a
      2-tile gap to a ledge 2 units up that only the rubber bounce reaches,
      a steep ramp long enough to catch its own throw, ice with bumper rails,
      sand before the goal, a mat off the route; its flights toward the
      viewer, over no cell that can hide the ball; its route for the
      autopilot. And `FIRST`'s goal, a finish line a rubber ball can now
      cross in the air. *Verify: `bonanzacourse` items 7 and 8 (the sweep:
      rubber lands on `G` in at least a quarter of approach speeds and
      offsets, steel and glass never, no ball without the bounce; the route
      reaches the goal without a fall and with no airborne step over an
      `OCC` cell; `FIRST` finished with each ball); one play by eye on each
      card.*
      *Final pass: `bonanzacourse` items 7 and 8 ok - the sweep: rubber
      on `G` after a bounce on `F` in 1,863 of 1,872, steel stunned and
      glass shattered on `F` in all, no ball on `G` without the bounce;
      the route to the goal at step 500 with no fall on either card;
      `FIRST` finished with each ball. DEVIATION: the flights cross
      `OCC` cells (92 airborne steps; the screen-row layout could not be
      crossed by the one-arrow autopilot, SPEC.md 128.11.13). The plays
      by eye were the physics and engine stages' look boots on `TRIAL`.*
- [x] **2.10 Replays.** A play is logged as one key byte a step,
      run-length coded in 4,096 bytes of bss with the current run in two
      fixed cells; `R` on the desktop replays it on either card, the same
      steps whatever the frame rate; the host model runs the same log; a log
      is trusted only because the package wrote it. *Verify:
      `bonanzareplay` - a real-keys play on the CGA whose log the model
      reproduces at every frame, its replay on both cards with the same end
      state, and an injected log covering every key bit and state; red arms
      `hopbit` and `framekeys`.*
      *Final pass: `bonanzareplay` ok - a real-keys play of `TRIAL` on
      the CGA (550 steps, 25 runs) whose log the model reproduces at
      every frame and at its end, its replay by R on both cards to the
      play's end state, three injected logs (rubber, steel stunned,
      glass shattered) on both cards; red arms `hopbit` and `framekeys`
      red.*
- [x] **2.11 A camera that knows the frame rate, and keys that do not
      repeat.** GLIDE's "fast" test is the ball's travel over four frames
      (the per-card constants go), and the benchmark's route is re-proved
      with a host model of GLIDE that is KEPT this time; C, M and N held on
      the desktop are one press each until `OSAPI_KEY_DOWN` says the key
      came up (a window timer polls it), and a release and a second press
      are two. *Verify: `bonanzacourse` item 8 (every direction at least
      five times on both cards at 0.96 - 1.04); `bonanzaring` (all eight on
      the glass); `bonanzaexit`'s held and re-pressed keys, red arms
      `crepeat` and `overswallow`.*
      *Final pass: `bonanzacourse` item 8 ok (every direction at least 8
      times on both cards at 0.96 - 1.04); `bonanzaring` all eight
      directions on both cards; `bonanzaexit` ok - C, M and N held 1.5 s
      advance once and pressed twice advance twice, on both cards; red
      arms `crepeat` and `overswallow` red.*
- [x] **2.12 kern_mega, run.** The table is built in the package's bss and
      the translation writes the fetched parts' own selectors (as
      `op_fetch`'s own expansion already does); the log and the boxes are
      bss; no `PKG_MEGA` arm. *Verify: `bonanzamega` - the Hercules display
      (so every launch builds and translates), the benchmark, a play with
      Hop and Grip and its replay, the grey arrows: no fault, no leak; red
      arms `segadd`, `hxcs`, `shiftmap`.*
      *Final pass: `bonanzamega` ok on 86Box's `286-mega-multimon` - the
      Hercules bracket, the benchmark's 1,200 frames, a play, a play
      with Hop and Grip and its replay ending where it did, no fault
      charged to the package, no part or claim left; red arms `segadd`
      and `hxcs` red. `shiftmap` could not be judged (story 2.4). The
      row now holds its keys for STEPS: 86Box presents about nine
      Hercules frames a step.*
- [x] **2.13 What it costs.** Busy on the benchmark predicted 48.0 - 48.6%
      of a CGA refresh and 40.7 - 41.3% of a Hercules one (the step priced
      instruction by instruction and taken 1.3 times, as wave 1 measured);
      `TRIAL`'s airborne frames +4 - 12k with a shadow and 0 misses on its
      route; a fall behind geometry with the pass at its bound may present at
      2 refreshes on the CGA, counted; the image about 15,100 bytes, bss
      about 5,700, claims while playing `BENCH` about 57.5KB. *Verify:
      `bonanzaperf` - the floor and the instruments on both legs, the A/B
      leg against wave 1 (`2df3f469`, fetched, or SKIP with the reason), the
      misses and the camera's rows panned per bounce; SPEC.md 128.11.15 and
      128.11.16 get their measured columns.*
      *Final pass: `bonanzaperf --ab` ok - `BENCH` busy 42,485 clk,
      53.4% of a CGA refresh, and 42,805, 45.5% of a Hercules one (wave
      1 measured alongside: 37,043, 46.5%, and 36,842, 39.2%), 0 misses;
      predicted 48.0 - 48.6% / 40.7 - 41.3% by the contract and 54 - 55%
      / 46 - 46.5% by the review's repricing - the first MISSED, the
      second met. `TRIAL`: busy 32.0k (40%) and 31.7k (34%); misses 8 on
      the CGA and 2 on the Hercules against a target of 0 - 6 and 2 on
      the fall and the flight (the fallback layout's allowance) and 2 on
      the steep ramp's grounded descent, which no allowance covers
      (reported, SPEC.md 128.11.15). Image 14,200, bss 5,805, `BENCH`
      with rubber 57,528 bytes of parts beside a 19,968-byte region.
      SPEC.md 128.11.15 and 128.11.16 carry the measured columns.*
- [x] **2.14 The record.** README, the face's lines and keys, `make help`
      for the new row, `BZ_COURSES` with `trial.bbc`, docs/HEAP-CLAIMS.md's
      Bonanza row and `tests/pins.txt`'s line REWORDED as SPEC.md 128.11.3.1
      says (one part a course, one a material, keyed `bz_bseg`) with the new
      sizes, the diary's wave-2 entries, `docs/INDEX.md` current. *Verify:
      `make` (the doc gates), `tools/os88index.py --check`, `checkdocs` 0
      problems.*
      *Final pass: `make` (the doc gates and the fast tier, 44 passed),
      `tools/os88index.py --check` current, `checkdocs` 0 problems; the
      rows' measured `secs` registered in `tests/suite.py`.*
- [x] **2.15 Two cameras, by the owner's choice.** After playing wave 1 the
      owner kept GLIDE (the default) and TRICKLE ("classic") and dropped
      FOLLOW ("the most jerky"): `C` toggles the two in play and on the
      desktop, the face names the mode, and FOLLOW's code is deleted
      (SPEC.md 128.11.11.1). *Verified: `bonanzaring`/`bonanzaexit` cycle two
      modes, a held `C` is one toggle, and the look boot shows both.*
      *Final pass: `bonanzaexit` ok - C counted at its handler, a held C
      one toggle on both cards; `bonanzaring` and `bonanzaperf` run
      GLIDE and replay TRICKLE (rows panned over TRIAL's bounces: 251
      against 137 on the CGA). The look boot was the engine stage's.*

**Wave 3: obstacles and the wheel** (the contract is SPEC.md 128.12, written
before the code, and revised once by three reviewers' findings before any
code). Decided there, against this plan: a LANE is a rectangle of the
course's block map (at most 4 words by 3 block rows) whose poses are sets of
map words, so the row, column and box writers draw a lane's drawn pose with
no change of their own, and a pose reaches the glass by a wheel commit, by
the LEAD after the flip, by the CONTACT box (the lane meets one of the
frame's boxes), or by the strip that brings it in (section 6.2's lanes, made
concrete); TITHE's wheel (section 6.3) keeps its calibrated TIME credit
(calibrated over the whole commit), its trim and its seeded clocks, but its
credit is the RETRACE WAIT itself with a margin listed term by term, its
order is the BEAM's (lanes ahead of the beam first, then each as the beam
passes it, the wheel spinning in the idle wait; the CGA's lowest lines on a
busy frame get one LEAD commit after the flip), its rate cap is the STEP
CLOCK (a rotor's phase is `(n + seed) AND (P - 1)`, the seeds spreading the
pose CHANGES so at most two rotors change on a step), and it banks nothing
(SPEC.md 128.12.5.1 says row by row what is taken and why); the boxes stay
FOUR (a second lane touching the ball waits a frame, display only, so
bumpers may stand in a cluster); the moving platform is a sprite with a lip
along `s`, not a lane, which carries the ball through a hop; the windmill is
a KEEP tube through a house whose DOORWAY is the house face, swallowing or
knocking back the ball that touches it, with a rotor lane standing on it
that is drawn on the frame its gate changes; the bumper is a KICKER, never
softer than wave 2's rail; section 8's three tubes (keep, launch, drop) hide
the ball and move a GHOST along the path at the ball's own speed caps, and
GLIDE re-centres on it every frame; nothing animated passes in front of the
ball (a lane's occluder verdicts must not depend on its pose); a HEAVY frame
withholds GLIDE's second row and its column, and a contact frame every row
and column (wave 2's `TRIAL` misses); a log carries its course's identity;
`BENCH` stays as it is and its A/B against wave 2 pokes the heavy rule off,
so it measures the engine, and a fourth course, `MILL`, carries the
obstacles. Every cost and size in the stories is PREDICTED until the final
pass; the rows run once, after the last batch.
The consistency check's five resolutions are SPEC.md 128.12.15: the rotor
drawn from the last step's phase, IN's whole 3 x 3 free of `OCC`, the
platform simulated always and drawn only when shown, explicit windmill
seeds where needed, and the Hercules beam checks reported, not asserted.
- [x] **3.1 Props in the course.** `tube` and `prop` are statements (`edge`,
      `checkpoint`, `pad`, `shape` stay reserved); the part's prop table
      (`BZC1` +28 / +30) holds up to 16 records in wave 3 (the format's limit
      is a word); the grid gains ONE bit, `OBS`, and keeps bits 4 - 5 for
      `edge`, the window refill listing its `OBS` cells and their props;
      every refusal of SPEC.md 128.12.3.3 (the exits checked by the model per
      ball, the facing of a windmill's doorway and a DROP's mouth, a
      platform's speed) and every bound of 128.12.4.6 fires at its line; the
      seeds spread the rotors' pose changes and the tool proves at most two a
      step in every window; `BENCH`, `FIRST` and `TRIAL` compile to wave 2's
      bytes but for the identity word. *Verify: `bonanzacourse` items 1 - 4
      and 6 (the byte identity against `848ade16`'s tool, exit 77 when it
      cannot be had), its grammar and bound negative controls.*
      *Final pass: `bonanzacourse` ok (79.5 s): its eight items on `BZ_COURSES`, the byte identity against
      `848ade16`'s tool, the grammar and bound refusals and their negative controls.*
- [x] **3.2 Lanes on the glass.** A lane's pose is its map words; the
      contact box draws a due lane beside the ball together with the ball,
      and a second lane touching the ball waits a frame; the wheel draws the
      rest in the retrace wait, only the cells in the shown window and the
      cells the entering rows write (never the entering column's); a lane
      scrolling in is drawn at its true pose by the strip; still four boxes;
      no lane's pose changes what hides the ball. *Verify: `bonanzaring`'s
      `MILL` leg on both cards (commits ahead of and behind the beam, a
      lead, a contact box for a rotor and a post, a deferred lane in the
      cluster, a lane entering by a row and by a column, the card equal to
      the oracle at `bz_tf` and `bz_presented`), red arms `contact` and
      `defer`; `bonanzacourse` item 5 over every pose, its
      rotor-off-the-house refusal.*
      *Final pass: `bonanzaring`'s `MILL` leg ok on both cards (card = oracle; AHEAD and the CGA's LEAD from
      the LOW scenario, SPEC.md 128.12.18), red arm `contact` red - but red arm `defer` stayed GREEN: open.*
      *Wave 3b's final pass: red arm `defer` red on the DEFER scene (SPEC.md 128.13.16).*
- [ ] **3.3 The wheel.** Calibrated at the launch over the whole commit
      (three sizes, eight samples each, an idempotent commit), trimmed by its
      own overruns, ordered by the beam (ahead first, then behind, spinning
      in the idle wait), skipped on a frame already past its first sync,
      with one LEAD commit after the flip for a lane the wait could not
      reach, its rate the step clock's: every commit changes a pose, none is
      ahead of the true one, none is written where the beam is or into an
      aliased cell, none ends past its deadline, a lane scrolling in shows
      its true pose, a shown rotor's poses reach the glass at its rate.
      *Verify: `bonanzawheel` (new) on both cards, red arms `repeat`,
      `ahead`, `nobeam`, `kmod`, `halfcal`, `alias`, `corner`, `lanestale`.*
      *Final pass: `bonanzawheel` FAILS (6) on the CGA - no wheel commit lands on the corner's diagonal
      step (its `bz_tw` 79 - 98k clk after the rise); red arms `nobeam` (green), `alias`, `lanestale` (red
      at (2)/(7), not their own) and `corner` (no valid leg) open. Everything else in the row passes: SPEC.md
      128.12.18.*
      *Wave 3b's final pass: every red arm but `corner` and `alias` judged and red; (6) still FAILS on the
      CGA (SPEC.md 128.13.16): open.*
- [x] **3.4 The windmill.** A ball rolled at the doorway on the house face is
      knocked back while a blade is down (at 0.625 of its speed) and
      swallowed by the tunnel while it is up, from the front or along the
      house; the blade across the doorway is on the glass on the frame of
      every knock-back and gone on the frame of every capture, and is seen
      coming down two poses before the gate closes. *Verify: `bonanzacourse`
      item 7's gate runs from every phase; `bonanzaphys` `knock`, `pass` and
      `side`, red arm `gate`; `bonanzawheel` (10), red arm `gatelate`; the
      look boot.*
      *Final pass: `bonanzacourse` item 7's gate runs ok; `bonanzaphys` `knock`, `pass`, `side` equal to the
      model at every frame on both cards, red arm `gate` red; `bonanzawheel` (10) the drawn gate right at
      every knock and capture, red arm `gatelate` red.*
- [x] **3.5 The bumper.** A ball touching a post leaves along the normal at
      least as fast as wave 2's rail would return it plus 0.25 gu a step and
      never under 1.5 gu a step (the owner's preview: "slightly more push",
      `K` 320 -> 384), keeps its tangential speed, and a hit ALWAYS shows:
      the post lights at once (a must-draw lane) and stays lit for 8 frames
      on the glass (the preview: "only rarely light up"); posts may stand in
      a cluster and the ball ricochets between them; a ball can rest on a
      post's top. *Verify: `bonanzacourse` item 7's approach and speed sweep
      and item 8's lit posts; `bonanzaphys` `kick` (diagonal), `cluster` and
      `post`, red arm `kick`; `bonanzawheel` (12), red arm `litsteps`.*
      *Final pass: `bonanzaphys` `kick`, `cluster`, `post` equal to the model on both cards, red arm `kick`
      red; `bonanzawheel` (12) both kicks' posts lit on their own frame, for 11 - 13 (CGA) and 8 - 9
      (Hercules) frames, red arm `litsteps` red.*
- [x] **3.6 The lift** (the moving platform; the owner's preview read the
      first design's slide along the screen's vertical as a lift, and it is
      one now: SPEC.md 128.12.16 items 6 and 7). A slab with a lip moves up
      and down a one-cell shaft between a low rim and one `L` units over it,
      at most 0.75 lines a step; a ball on it is carried to the other rim
      and does not SPIN on the way, a Hop on it lands back on it, a ball
      rolled off the high rim into the shaft lands on the slab wherever it
      is, a ball rolling off its open side falls, a ball entering under it
      is not lifted, and the slab is drawn over a ball below it and under
      one on it, its own box only when its line changes. *Verify:
      `bonanzaphys` `ride`, `hop`, `land`, `fall`, `board` and `under`, red
      arms `carry`, `carrys` and `stick`; `bonanzacourse` item 7's lift
      runs; `bonanzaring`'s platform frames, red arm `padfront`;
      `bonanzaperf`'s ride leg.*
      *Final pass: `bonanzaphys` `ride`, `hop`, `land`, `fall`, `board`, `under` equal to the model on both
      cards, red arms `carry`, `carrys`, `stick` red; `bonanzaring`'s riding slab (150 frames) and slab over
      the ball (12) card = oracle, red arm `padfront` red; `bonanzaperf`'s ride leg measured (its line-change
      frames 120% / 104% busy: 3.12's).*
- [x] **3.7 Three tubes and the camera glide.** KEEP spits the ball out along
      its mouth at the speed it went in with, LAUNCH fires it at a fixed
      velocity over a gap onto a floor, DROP drops it 3 units (rubber
      bounces, steel is stunned, glass shatters); a plain tube's IN is a hole
      and its OUT a rim pointing the way out; where the ball leaves through
      a wall face (the DROP, a windmill), that face has a MOUTH the ball
      comes out of, its sill at the exit height, and a tube's wall on a lower
      tier is drawn as one column (the owner's preview); the ball is hidden
      in transit, GLIDE re-centres on the hidden ball every frame and the
      exit is in the window when it comes out. *Verify: `bonanzacourse` item
      3's mouths and columns, item 7's transit and exit runs (each exit's
      outcome per ball); `bonanzaphys` `keep`,
      `launch`, and `drop` with all three balls, red arm `exit`;
      `bonanzaring`'s transit frames and exits, red arm `hidden`.*
      *Final pass: `bonanzaphys` `keep`, `launch`, `drop` (three balls) equal to the model, red arm `exit` red;
      `bonanzaring`'s transit frames (19 / 18 checked) and each tube exit's footprint inside the window, red
      arm `hidden` red.*
- [x] **3.8 The heavy frame.** On a frame that runs the occluder pass, draws
      the ball as two boxes or shows the slab at the window's edge, GLIDE
      takes at most one row and no column; on a frame that draws a contact
      box, none; each axis released near its edge, decided before the camera;
      `TRIAL`'s steep-ramp misses go and its fall misses stay inside wave
      2's allowance (PROVISIONAL). *Verify: `bonanzacourse` item 8
      (`BENCH`'s eight directions with the rule off, reported with it on);
      `bonanzaperf`'s second `BENCH` leg and its `TRIAL` leg with the busy
      of every missed frame.*
      *Final pass: measured, the claim NOT met: `TRIAL` with the heavy rule missed 14 (CGA) and 9 (Hercules)
      against wave 2's 8 and 2 (O28, the owner's).*
      *Wave 3b's final pass: level 1 is the slab-near-edge clause alone (SPEC.md 128.13.6); `TRIAL` 5 - 8
      (CGA) and 4 (Hercules) misses OFF, `bz_nhvy` 0 (SPEC.md 128.13.16).*
- [x] **3.9 Replays with moving obstacles.** Obstacles are a function of the
      step count, so a `MILL` play recorded on the CGA replays on the Hercules
      to the same state at every step, through knock-backs, kicks and
      transits; a log names its course, and a log made on another course (a
      re-seeded one) is refused rather than played wrong. *Verify:
      `bonanzareplay`'s `MILL` record, replay and refusal, red arms
      `propclock` and `noident`; `bonanzaphys` at every frame.*
      *Final pass: `bonanzareplay`'s `MILL` record (721 frames, a knock-back, the windmill's capture, kicks,
      the chute) equal to the model, replayed on the Hercules equal at every frame, the log with another
      identity refused; red arms `propclock` and `noident` red.*
- [x] **3.10 `MILL`, "Windmill Lane", and the benchmarks.** Two windmills, a
      bumper cluster, a moving platform, a cannon and a drop chute (8
      records), at most six lanes in any window and two rotor changes a
      step, the platform in a window with no windmill; the cannon's flight
      and the chute's fall over no `OCC` cell; the autopilot reaches its goal
      with no fall in 1,200 frames on both cards; `N` cycles `FIRST`,
      `TRIAL`, `MILL`; B still runs the unchanged `BENCH`. *Verify:
      `bonanzacourse` item 8 (`MILL`'s route); `bonanzaperf`'s `BENCH` A/B
      against wave 2 (`848ade16`, the heavy rule poked off) and its `MILL`
      leg.*
      *Final pass: `bonanzacourse` item 8 ok; `bonanzaperf`'s A/B (busy 44.6k / 44.8k against 42.5k / 42.9k,
      one CGA miss on a frame running two steps against wave 2's one: reported as the step clock's phase)
      and its `MILL` leg (`bz_wover` 0, `bz_wlate` 0 asserted, on both cards).*
- [x] **3.11 kern_mega.** The map's words are written through the course
      part's own selector; no `PKG_MEGA` arm. *Verify: `bonanzamega` -
      `MILL` on the Hercules display, a replay of a log the row writes with
      the model, through a knock-back, a kick, a ride and each tube kind: no
      fault, no leak, the replay's end state; red arm `mapcs`.*
      *Final pass: `bonanzamega` ok (24.5 s) on 86Box, red arm `mapcs` red.*
- [ ] **3.12 What it costs.** `BENCH`'s busy about 44.3k (55.6%) on the CGA
      and 44.6k (47.4%) on the Hercules without the wheel (the A/B leg);
      `MILL`'s wait commits inside the wait with no overrun and no lane
      late; `MILL`'s misses only on the cannon's flight and the chute's fall,
      each named with its busy; the ride's line-change frames under a
      refresh (94% on the CGA, PROVISIONAL, O30); the image about 17,900 -
      18,800 bytes, bss about 6,010, `MILL`'s part about 22 - 30KB,
      `BONANZA.O88` about 58 - 61KB, still on the 360KB `bonanzadisk`.
      *Verify: `bonanzaperf` (its five legs and the A/B), `bonanzawheel`,
      `bonanzaexit`'s heap reads; SPEC.md 128.12.10 and 128.12.11 get their
      measured columns.*
      *Final pass: measured, the targets NOT met: `BENCH` busy 44.6k / 44.8k (met); `MILL` no overrun and no
      lane late (met, after the promotion); `MILL`'s misses 111 (CGA) and 13, on the lift's stretch, not
      only the flight and the fall; the ride's line-change frames 120% / 104%; the image 23,227 bytes, bss
      6,542, `MILL`'s part 33,906, `BONANZA.O88` 68,235, still on the 360KB disk. SPEC.md 128.12.18.*
      *Wave 3b's final pass: `MILL` 47 (CGA) and 17 misses OFF, the ride's line changes 83% / 71% with no
      miss; the CGA's lift stretch still misses 6 - 9 (SPEC.md 128.13.16): open.*
- [x] **3.13 The record.** README and the face's course list, `BZ_COURSES`
      with `mill.bbc`, docs/HEAP-CLAIMS.md's Bonanza row with `MILL`'s size,
      the new row's registration in `tests/suite.py` with its predicted
      `secs`, the diary's wave-3 entries, `docs/INDEX.md` current. *Verify:
      `make` (the doc gates), `tools/os88index.py --check`, `checkdocs` 0
      problems.*
      *Final pass: the doc gates, `os88index --check` and `checkdocs` pass, `BZ_COURSES` carries `mill.bbc`,
      docs/HEAP-CLAIMS.md MILL's 33,906, the rows' `secs` registered MEASURED; README has carried no
      Bonanza entry since wave 0: left open.*
      *Wave 3b: README lists `make bonanzadisk` (SPEC.md 128.13.9).*

**Wave 3b: the performance round** (the contract is SPEC.md 128.13,
written before the code; the owner, 2026-11-13: "do the performance wave
next, then move on past sound"). Designed from MEASURED scratch runs on
wave 3's build (SPEC.md 128.13.3): a line-change frame of the ride spends
59k of its 96k on two overlapping boxes that each lay the slab and the
ball; with the ball BESIDE the lift the frame is the slab's own box and the
ball's, about 71k on both cards; the raster lane writer is 88% (CGA) and
85% (Hercules) of a commit's span, and the preparation's record reads, MULs and DIV 3.2k of
its 7.2k; and, clause by clause, the heavy rule's slab-near-edge clause is
the only part of level 1 that helps (`MILL` 81 CGA and 16 - 18 Hercules
misses with it, against 105 - 107 and 14 with the whole rule, 102 and 28 with
level 2 alone), while its other two clauses made `TRIAL` worse on both
cards. It closes wave 3's open stories 3.2, 3.3, 3.8, 3.12 and 3.13. Sound
is the other session's (wave 4): this round leaves it a reserve of 2,048
clk a frame, spent by a harness pad in the target legs, and names where it
may hook and what the engine asks of it elsewhere. Every cost and size
below is PREDICTED until the final pass; the rows run once, after the last
batch.
- [x] **3b.1 The lift rides in one box.** A ball riding the lift and the
      slab are composed ONCE - the course, the slab under, the shadow, the
      ball, the occluders, the slab over - in one box of up to 4 words by
      32 lines, and written once, where wave 3 drew two overlapping boxes
      that each laid both; the picture is the same, byte for byte. The
      ride's line-change frames fall from 120% / 104% of a refresh to about
      80% / 70%. A ball riding near the diamond's left or right corner
      keeps two boxes: reported, a counted residue. *Verify:
      `bonanzaring`'s `ridebox` frames (card = oracle, both cards), red arm
      `ridebox`; `bonanzaperf`'s ride leg, no miss on a line-change frame
      and `bz_late` 0 ASSERTED with sound's reserve spent, red arm `rideoff`
      (CGA); the corner ride sub-leg reported.*
      *Final pass: `bonanzaring`'s RIDE BOX frames card = oracle (49 CGA, 47 Hercules), red arm `ridebox`
      red; the ride's line-change frames 65.8k (83%) and 66.7k (71%), no miss OFF and `bz_late` 0 on both
      cards (ASSERTED; ON reported: 0 on the speaker, 7 with the AdLib machine's sound), red arm `rideoff`
      red; the corner ride one box on every line change, 0 misses OFF. SPEC.md 128.13.16.*
- [x] **3b.2 A crowded frame draws the lift a frame later, and a kicked
      post lights at once.** When the ball's and its shadow's groups are
      two boxes (a fast or airborne ball), the lift's box waits one frame
      (never two running, never under a ball it carries, never as it leaves
      the window): the slab is a line late for one frame, display only,
      where wave 3 drew three boxes and the slab and missed a refresh. A
      post lighting beside the moving lift on such a frame lights on its
      kick's frame and the lift's box waits, unless the box cannot wait (it
      waited the frame before, carries the ball, or is leaving the window). Decided
      before the camera, so a strip meeting the slab on a waited frame
      still draws it. A visible change (the owner looks: O37). *Verify:
      `bonanzaring`'s PWAIT scene (`pwait`, card = oracle, every platform
      box at most 30 lines, a waited frame with a strip meeting the slab),
      red arm `pwait2`; `bonanzawheel` (12) tightened (a kicked post lit on
      its kick's frame); `bonanzaperf` reports the share of line changes
      that waited.*
      *Final pass: the PWAIT scene card = oracle on both cards (13 / 12 waited frames, a waited frame with
      an entering row meeting the slab on each, the platform box at most 21 / 22 lines), red arm `pwait2`
      red at the one-wait rule; `bonanzawheel` (12) every kick lit on its frame; 4 - 5% of `MILL`'s lift line
      changes waited (OFF). SPEC.md 128.13.16.*
- [ ] **3b.3 Boxes go to the card faster.** A 3- or 4-word box with no
      overlap band is written a card row at a time by unrolled moves,
      about 160 clk a line less (wave 3 measured 490 a 4-word line where
      the row writer moves the same bytes in 284): about -2.5k a `BENCH`
      frame, -3.0k a slab box. *Verify: `bonanzaring` everywhere, its
      `wrapbox` frames (a box across the ring's end), red arm `fastwrap`;
      `bonanzaperf`'s A/B against wave 3.*
      *Final pass: the whole-row path takes 1,385 clk off `BENCH`'s CGA box writes, but the A/B's asserted
      2.0k is NOT met: mean busy 1,284 under `e781df53`'s (Hercules 514, reported) - BENCH's boxes are 3
      words, where the block saves ~80 clk a line, not 4-word's 160. `wrapbox` frames (the ring's-end scene,
      8 a card) card = oracle, red arm `fastwrap` red. Open: SPEC.md 128.13.16.*
- [ ] **3b.4 The wheel commits faster.** A commit is one column-major pass
      from the pose map - the map's words stored as they are read (through
      DS, never the stack's SS), a block's lines by the column writer's
      own macros, the uncovered cells' map words in the same span - priced
      by a model with a per-column term and a per-uncovered-cell term, and
      calibrated by the same three spans: a rotor about 7.2k on the CGA
      (its spans measured 12.2k) and 7.0k on the Hercules (8.9k). *Verify:
      `bonanzawheel` (3) - (6) on every commit at the pass's probe points,
      a whole-lane commit's cost within `CAL_TOL`, the spans reported by
      kind; red arms `alias`, `corner`, `costtab`; `bonanzaring`'s card =
      oracle and the map on `MILL`, red arm `mapskip`; on kern_mega
      `bonanzamega`'s `mapcs` re-pointed at the pass's map store (SPEC.md
      128.13.11).*
      *Final pass: a whole rotor's pass 8,917 / 8,890 clk (PREDICTED 7.0k), a post's 6,648 / 6,626; whole
      commits 0.99 of their price after `BZ_WPATH`; card = oracle and oracle check 5 on `MILL`, red arms
      `mapskip`, `costtab`, `mapcs` red. `bonanzawheel` (6) still FAILS on the CGA - the corner lane commits
      only AHEAD (by 67.3k) and the step frame's test lands near 65k - so `alias` and `corner` are unjudged.
      Open: SPEC.md 128.13.16.*
- [ ] **3b.5 Less to prepare, less to walk.** Per-lane tables filled once
      a play, a whole lane's cost from a table filled after the
      calibration, the trim's MUL and DIV only under 100: a preparation
      about 5.3k (was 7.2k), so the CGA's wait holds two rotors and the
      Hercules' three. The walk skips a rotor until its next pose change
      and a post drawn dark with no lit frames and no new kick: about -1.5k
      a `MILL` frame. *Verify: `bonanzawheel` (2), (5), (7), (9), (12), the
      new (13) (`bz_lnext` exact), red arms `lnext` and `pskip`;
      `bonanzaperf`'s padded `MILL` leg (`bz_wover` and `bz_wlate` 0
      ASSERTED, the promotions reported).*
      *Final pass: `bonanzawheel` (2), (5), (7), (9), (12) and (13) pass on both cards (`bz_lnext` exact on
      522 / 446 rotor-frames), red arms `lnext` and `pskip` red; `MILL`'s `bz_wover` and `bz_wlate` 0 on every
      benchmark after `BZ_WPATH` (one overrun a run before it). SPEC.md 128.13.16.*
      *The verification: UNTICKED - the checks pass, but the stated result does not hold. The preparation
      measured 5.06k / 5.11k (met); the commit it is weighed with is 8.9k, not 7.2k (3b.4), so the CGA's wait
      holds one rotor and a post, not two; the walk's -1.5k was never measured alone - `MILL`'s sim+camera fell
      1.6k (CGA) and 0.4k (Hercules) against `e781df53`, the steps a frame not separated. Open with 3b.4:
      SPEC.md 128.13.17 item 4.*
- [x] **3b.6 `TRIAL` is no worse for the heavy rule** (O28 and O35,
      answered by measurement). Level 1 keeps only its slab-near-edge
      clause; the occluder-pass and two-box clauses go; level 2 (a frame
      drawing a contact group takes no strip) stays. `TRIAL` and `BENCH`
      have no slab, so their camera is the no-rule camera: `TRIAL`'s misses
      are its fall's again, about 9 / 1 (wave 2's allowance 8 / 2), not 15
      / 9. *Verify: `bonanzaperf`'s `TRIAL` leg (`bz_nhvy` 0 ASSERTED,
      misses reported), red arm `level1`; its three `MILL` legs (this
      build, no rule, wave 3), unpadded; `bonanzacourse` item 8 with
      `bbcourse.Heavy` and `Glide` changed.*
      *Final pass: `TRIAL` `bz_nhvy` 0 (ASSERTED), misses 5 - 8 (CGA) and 4 (Hercules) OFF against wave 2's
      8 / 2 and wave 3's 14 / 9; red arm `level1` red; `MILL` three ways reported; `bonanzacourse` passes.
      SPEC.md 128.13.16.*
      *The verification: the Hercules' 4 is OVER the PREDICTED ~1 and wave 2's allowance of 2 - GLIDE's
      two-row frames down the steep ramp (frames 135 - 139), with no heavy frame; reported, a deviation from
      the prediction, not from the story's claim. SPEC.md 128.13.17 item 7.*
- [x] **3b.7 The lift stretch, measured with sound's reserve spent.** No
      miss on the ride's line-change frames on either card (3b.1); on
      `MILL`'s lift stretch with the ball beside the lift, at most 3 missed
      refreshes on the Hercules (PREDICTED 0 - 1); on the CGA a REPORTED
      residue (PREDICTED 15 - 20 of about 280 frames: the slab's own box
      and the ball's are two different pictures and nothing in this round
      removes that tail), each missed frame written into SPEC.md 128.13.4.5
      with its parts - the owner's O33 (the slab on even lines) is the
      lever. *Verify: `bonanzaperf`'s padded `MILL` and ride legs.*
      *Final pass: the ride's line changes no miss (OFF, ASSERTED) on both cards; the Hercules' lift stretch
      2 missed refreshes ON (at most 3 ASSERTED); the CGA's REPORTED: 6 - 9 OFF and 48 ON (PREDICTED 15 -
      20), every missed frame the slab's box and the ball's - O33 stands. SPEC.md 128.13.16.*
      *The verification: every missed frame (CGA OFF 9, ON 48; Hercules ON 2) is now written into SPEC.md
      128.13.4.5 with its parts, boxes, steps and the sound's share; the CGA's ON tail is a two-step chain (45
      of 48 over a refresh without the sound's own clk). SPEC.md 128.13.17 item 5.*
- [ ] **3b.8 Every red arm meets its case.** `defer` on a DEFER scene (a
      post really drawn lit, then due and waiting with cells outside every
      box), `nobeam` on a BEAM sweep keyed to due frames, `alias` on the
      light corner step's commit, `lanestale` on a STALE scene (a rotor
      brought in by a row after its pose changed off screen), `corner` on a
      LIGHT diagonal step (TRICKLE, a held frame before it, one row, so
      the wait has room: `bz_tw` about 57 - 60k), and `shiftmap` at case
      3's own fake-shift-release check (86Box sends the release with Left
      Shift held, MEASURED). `bonanzawheel` (6) passes on the CGA. *Verify:
      each arm run once in the final pass, red at its own check.*
      *Final pass: all 63 red arms went red at their own check after three red-arm fixes (`contact`,
      `litsteps`, `halfcal`) and the ring's-end scene - but `bonanzawheel` (6) still fails on the CGA, so
      `corner` and `alias` are unjudged. Open: SPEC.md 128.13.16.*
- [ ] **3b.9 A smaller image.** The step's wall and floor macros in one
      instance (-530 bytes, about +150 clk a step on a course with no
      props near the ball: O34), level 1's two clauses gone (-25), the
      raster lane writer gone (-323 against the pass's +260): the image
      about 23,020 bytes (wave 3: 23,227), bss about 6,993 (+256 of it the
      32-line buffers), `BONANZA.O88` about 68,105, the course parts byte
      for byte wave 3's. *Verify: `nasm` spans in SPEC.md 128.13.8's
      measured column; `bonanzaphys` and `bonanzareplay` equal to the model
      at every frame on the merged step; `bonanzaexit`'s heap reads.*
      *Final pass: `bonanzaphys`, `bonanzareplay` and `bonanzaexit` pass on the merged step; but the image
      is 27,362 bytes (23,706 without the sound's 3,656: +479 over wave 3, not the -206 PREDICTED), bss
      7,357, `BONANZA.O88` 77,275. Open: not smaller. SPEC.md 128.13.8, 128.13.16.*
      *The verification's fixes add 59 bytes (the results face's 13 lines on the CGA): 27,421, bss 7,358,
      `BONANZA.O88` 77,323. SPEC.md 128.13.17.*
- [~] **3b.10 Room for sound, and what the engine asks of it.** *SUPERSEDED by SPEC.md 128.13.15: the sound landed first, so no pad and no hook were built; its measured price is 128.20.7 and 128.13.16.* Sound may
      spend 2,048 clk a frame at one hook (after the LEAD, before the
      frame's last mark, BX preserved), reading physics' event counters;
      the step, the wheel, the wait and the beam-raced writes are places
      whose costs are budgeted, the kernel's own sound tick lands in them,
      and an interrupt-time voice is the sound session's choice with its
      costs written down. The ride and the Hercules' lift stretch hold with
      the reserve spent; the CGA's heaviest frames already miss without
      it, which the SPEC says plainly. *Verify: `bonanzaperf`'s `MILL` and
      ride legs run with `bz_spad` 1.*
      *Superseded by SPEC.md 128.13.15: the sound arrived first, so no pad and no hook were built; every
      target was measured OFF and ON instead (128.13.16). Left open as written.*
- [x] **3b.11 The record.** `bbcourse.Heavy` mirrors the promotion, the
      slab's waits and the post rule; the top-level README lists `make
      bonanzadisk`; the seven stale "PREDICTED" `tests/suite.py` texts say
      what each row asserts; `tools/bbcourse.py` pyflakes-clean; the
      diary's 3b entries; SPEC.md 128.13 gets its MEASURED columns.
      *Verify: `make` (the doc gates, `checkreadme`), `tools/os88index.py
      --check`, `checkdocs` 0 problems, `python3 -m pyflakes
      tools/bbcourse.py`.*
      *Final pass: `make` (the doc gates), `os88index --check`, `checkdocs` 0 problems, `pyflakes
      tools/bbcourse.py` clean; README lists `make bonanzadisk`; the suite texts carry the measured secs;
      the diary's 3b entry; SPEC.md 128.13.16.*

**Wave 4: a game** (the contract is SPEC.md 128.14, written before the
code). A TOUR of the five courses after `BENCH`, raced for time against
par, with no lives: a fall costs the way back from the last checkpoint
(D4 stays a mechanic), and each new course has an optional hard-fall
line. The desktop face is the scorecard, and the best times live in
`SYSTEM\APPDATA\BONANZA.DAT` on the package's own disk. The courses gain
flags, a cup, ball-swap pads and a spring pad, and two new longer courses
arrive, `MOON` (K = 4) and `SUMMIT` (K = 5), which teach the pads, glass
and the springs in that order. A HUD clock rides in the picture. Demos can
be saved to disk and loaded back as hostile input, and the shipped demos
become the benchmark. The mouse works as a tilt stick, and the
parting-out question is decided with the bytes.

The HUD's price was designed from two MEASURED things: `bz_boxc`'s fill
and `bz_boxw` by box size on MartyPC, both cards (a box has about 1.6 -
2.1k clk of fixed cost in each of its compose and its write), and a
per-frame log of `MILL`'s and `TRIAL`'s benchmarks, both cards, sound OFF
and ON (where each HUD box would land, and what a frame at that busy
misses). From them a clock that follows the camera adds about 21 - 24
misses a `MILL` leg on the CGA and 10 - 11 on the Hercules, and one that
hides during pans (REST) adds 0 - 3 and still shows two thirds of the time
or more. So REST is the default on both cards. Every other cost and size
below is PREDICTED until the final pass, and the rows run once, after the
last batch. **O39 (scoring) and O43 (cups on the old courses) are put to
the owner before 4.5 and 4.6 are built**, and **O11's constants are settled
before the owner records demos** (a retune changes the physics identity a
demo carries).

- [x] **4.1 The tour and the scorecard.** `G` plays `FIRST`, `TRIAL`,
      `MILL`, `MOON` and `SUMMIT` in order, each with its own ball. After
      each finish the face shows the scorecard: every course's time,
      falls, par and best, then `ENTER next`. After the fifth it shows the
      total time. Esc in a course or on the face stops the tour; during a
      tour only Enter, Esc, `W` and the settings act. Inside a course P
      pauses and Backspace returns the ball to its flag. Outside a tour
      Enter still plays the course `N` and `M` select, freely. *Verify:
      `bonanzagame`'s autopilot tours on both cards (each time the
      model's steps, the total their sum, the two stops, the withheld
      keys, the pause).*
      **Built** (SPEC.md 128.14.21): the tour, both faces with every line
      held to 42 cells by the assembler, PAUSE; checked on the host (unicorn)
      and looked at, one boot a card.
      *Verified in the final pass (SPEC.md 128.14.26 item 7): `bonanzagame` on
      both cards - the autopilot tour FIRST 158, TRIAL 500, MILL 676, MOON
      2,040, PEAK 1,902 steps, each the model's, total 5,276; the tour stopped
      in course 3 and on the face; the eight withheld keys; PAUSE (no step
      while paused, the play to the model's goal).*
- [x] **4.2 Best times that survive the session.** A best course time and a
      best tour are written to `SYSTEM\APPDATA\BONANZA.DAT`
      (`apps/os88data.inc`) on the package's own volume; the four
      `bonanza*.img` are built with that folder. Only a play that started
      with the course's own ball posts a best - never a replay, a demo or
      a loaded file. Each entry is keyed by its course's identity, and the
      whole file is read as hostile: a foreign or damaged entry is ignored
      on its own, and a course rebuilt with a new identity loses its best
      by itself. A save that fails says so once. *Verify: `bonanzagame`
      reads the file back off the floppy on the host and drives the
      hostile set; red arms `besttime`, `datlen`, `replaybest` and
      `noappdata`, each red at its own check.*
      **Built** (SPEC.md 128.14.21 item 5): written, read back off the floppy
      on the host and by a new instance's entry, one boot a card; the
      hostile set checked on the host (unicorn).
      *Verified in the final pass (SPEC.md 128.14.26 items 7, 11): the file
      read back off the floppy (the expected 64 bytes) on both cards; the
      hostile set (short, magic, identity, zero, tour XOR, count) each as the
      checks say and rewritten whole; R, D, V and another ball left it absent;
      `Best times not saved` once on a disk without `SYSTEM\APPDATA`; red arms
      `besttime` (re-aimed at both min sites), `datlen`, `replaybest`,
      `noappdata` each red at its own check.*
- [x] **4.3 Flags, the cup, pads and springs.** A flag flies once touched
      and becomes the respawn point; a respawn there gets the ball the
      flag names, and the tool refuses a flag or a pad from which that
      ball cannot reach the cup. A slow grounded ball over the cup holes
      out and a fast one pops and lips out. A pad swaps the ball, its
      constants and its force tables. A spring lifts any ball six units,
      the climb a bounce cannot make. Each is a `bbcourse.py` statement
      with refusals, each is drawn on both cards and looked at, and each
      is a step rule on the prop path that is integer-exact with
      `bbcourse.Physics`; so is RETURN. *Verify: `bonanzacourse`'s items
      and negative controls (`trap`, `underhud` among them);
      `bonanzaphys` `flag`, `flagmat`, `padswap`, `cup`, `spring`,
      `return` with red arms `ckpt`, `ckmat`, `padftg`, `cupv` and
      `springsum`; one look boot a card.*
      *Verified in the final pass (SPEC.md 128.14.26): `bonanzacourse` (its
      items and controls, `trap` and `underhud` among them); `bonanzaphys`
      `flag`, `flagmat` (MOON and PEAK), `padswap`, `cup-128`, `cup-lip`,
      `cup-stun`, `cup-shatter`, `spring` and `return` equal to the model at
      every frame on both cards; red arms `ckpt`, `ckmat`, `padftg`, `cupv`,
      `springsum` each red at its own check; `bonanzaring`'s W4 part (capture,
      lip-out, flag, pad swap) card = oracle.*
- [x] **4.4 The HUD clock on the glass - OPTIONAL, BUILT LAST** (the owner, SPEC.md 128.14.16: OFF by default; ships only if REST/FOLLOW add at most 2 `MILL` misses a card with the speaker on and none on `BENCH`, else removed; the clock is on the results face either way). The course time (`SS.T`) sits on
      an opaque 2-word by 6-line panel, inset from the window's bottom-left
      corner so no entering row or column ever meets it. It is drawn as a
      fifth box group that composes every layer and lays the panel last,
      and the panel is laid last in every box that meets it, so no card
      byte ever receives two different values. A lane under it is drawn
      only by a promotion to the contact group, never by the wheel. `H`
      cycles REST, FOLLOW and OFF; the default is REST on both cards, its
      boxes never on a scroll frame but a release, under either camera;
      a full write is blanked; and `B` runs with the HUD off. *Verify:
      `bonanzaring` (card = oracle with the panel, no byte two values, a
      lane under it, a five-box frame, a full write shown and hidden, the
      blank; red arms `hudinset`, `hudold`, `hudlane`, `hudfull` and
      `noblank`); `bonanzagame`'s digits and REST's no-HUD-box-on-a-scroll-
      frame under GLIDE and TRICKLE (red arms `hudhold` and `hudtime`);
      `bonanzawheel` (14) with red arm `hudrect`.*
      **Built, not yet shipped** (SPEC.md 128.14.23): behind
      `%define BZ_HUD`, OFF by default, `H` cycling OFF / REST / FOLLOW;
      host-checked and looked at on both cards (REST on the CGA, FOLLOW on
      the Hercules: the card's rect equal to the panel on every shown frame
      of `MILL`'s demo). +1,465 image bytes and +222 bss.
      *CLOSED - REMOVED, it did not fit (SPEC.md 128.14.5, 128.14.26 item 1):
      `MILL`'s route demo through `D`, the speaker on, missed 93 refreshes on
      the CGA with the HUD OFF and 158 at REST (+65), 24 on the Hercules OFF
      and 69 at FOLLOW (+45), against a bound of +2 a card. Its code, fifth
      box group and `H` key are gone (the package is the define-off build
      byte for byte); the blank stays. 128.14.16 item 3: either outcome
      closes the story.*
- [x] **4.5 Moonlit Green (`MOON`, K = 4).** A night round of about 100
      block rows (PREDICTED 44 - 48KB). It teaches the flags, the cup and
      the pads, glass last and gently: an ice approach, a steel pad for a
      stone-rail corridor and a long coast (with an optional 2-unit drop
      that trades a 1 s stun for half the zig-zag), a rubber pad before a
      rubber-only ledge, a castle wall with three KEEP tubes (the route, a
      shortcut, a dead end), then a glass pad and a terrace of one-unit
      steps where a shatter costs only the way back to the flag just
      before it, and the cup up a gentle ramp. Its shipped demo is
      AUTHORED with the model (a fall, a RETURN, every swap). *Verify:
      `bonanzacourse` (inside a part, three balls, the route to the cup
      with no fall on both cards, NO TRAP, the branch printed);
      `bonanzaphys` `cup`, `flag`, `flagmat` and `padswap`; a look on
      both cards; its demo's legs.*
      *Verified in the final pass (SPEC.md 128.14.26): `bonanzacourse` (51,240
      bytes, 127 block rows; route 2,040 steps to the cup with no fall; NO
      TRAP); `bonanzaphys` `flag`, `flagmat-moon`, `return` equal to the model
      at every frame on both cards; `bonanzaring`'s W4 part (its shipped demo:
      the capture, a flag raised, a pad swap, every full write blanked);
      `D` of `BZD4` to the model's end, CGA 16 / 48 misses (speaker OFF / ON),
      Hercules 10 / 23; the tour's `MOON` 2,040 steps.*
- [ ] **4.6 Summit Rush (`SUMMIT`, NAME `PEAK`, K = 5; SPEC.md 128.14.17 item 1).** The long demo course, a
      descent of about 128 block rows (PREDICTED 55 - 60KB, the largest a
      part holds). Rubber down steep-ramp chains and an ice chute, a
      windmill and a DROP (or an optional glass staircase past them),
      spring 1 up six units, steel through the lift and the LAUNCH, glass
      over the moat bridge and up spring 2, rubber to the cup at the
      foot; four flags, each naming its ball. Its PREDICTED misses (CGA 60
      - 100 OFF, 150 - 230 ON) are accepted in writing (O54) unless the
      final pass measures more. Its shipped demo is AUTHORED (a fall, a
      RETURN, every swap, both springs, the branch). *Verify: as 4.5,
      plus `spring` and `return`.*
      **Built and verified but its misses, open** (SPEC.md 128.14.26 items 6
      and 7): `bonanzacourse`, `bonanzaphys` (`spring`, `cup-128`, `cup-lip`,
      `cup-stun`, `cup-shatter`, `flagmat-peak`) and its demo to the cup on
      both cards pass, and its launch is 3.9 - 4.0 s. `D` of `BZD5` misses
      **205 / 293** refreshes on the CGA (speaker OFF / ON) and **60 / 96** on
      the Hercules - over O54's PREDICTED 60 - 100 / 150 - 230 and 10 - 25 /
      40 - 70, so O54's default (ease its `r` = -4 chains) is the owner's
      next call; easing it changes the course's identity and its demo.
- [x] **4.7 Sound's counters.** `bz_nckpt`, `bz_npad`, `bz_nlip`,
      `bz_nspr` and `bz_nret` are physics' own counters. A hole-out is
      `bz_goal` with `bz_hid`, and the desktop has `bz_tour` 6 and
      `bz_newb`. All are handed to the sound session, which maps them;
      its two part fetches go through `bz_pfetch`. This wave designs no
      sound. *Verify: `bonanzaphys` compares the counters with the model;
      the sound session's own row.*
      *Verified in the final pass: `bonanzaphys`'s scenarios compare the new
      counters with the model on both cards; `bonanzasound` passes. As built
      the sound's fetches go home through a bracket round `bz_launch`, `S`
      and `V` rather than `bz_pfetch` inside `bzsound.inc` (SPEC.md 128.14.22
      item 1: the sound code is the other session's).*
- [x] Sound (section 10), widened by the owner to the speaker AND the AdLib, a
      title and five course themes and an impact a ball: built in parallel,
      SPEC.md 128.20 and [BOUNCE-BONANZA-SOUND.md](BOUNCE-BONANZA-SOUND.md),
      whose stories S9 - S11 stay open.
- [x] **4.8 Demos to and from the disk.** `W` saves the held log through
      the Save dialog as `<NAME>.BZR`. `L` loads one through the Open
      dialog. The loader refuses by extension and size before any read,
      reads into a transient claim and checks every field - the course's
      identity and the physics identity among them - before any part row
      is chosen. Only then does it copy the log in, so a refused file
      leaves the session's own log untouched. `.BZR` is BONANZA's
      association, so a double-click opens the demo, through a read
      bounded by its capacity. Every part fetch goes home first, so a
      dialog that moved the instance never breaks the next launch.
      *Verify: `bonanzademo` (the round trip into another folder and a
      play after it, the double-click, the hostile set each refused with
      nothing fetched or leaked, the first three refused with no read,
      the double-click's size legs); red arms `nosum`, `readfirst`,
      `stageleak`, `inplace`, `nohome` and `argsize`.*
      **Built** (SPEC.md 128.14.22 items 1 - 5): W, L with its hostile pass,
      the association and the double-click, home round every desktop fetch;
      checked on the host (unicorn: `bz_lchk` against `bbcourse.check_log`,
      L's and the double-click's whole path with the kernel stubbed) and
      looked at, one boot a card (the save into `SYSTEM` read back off the
      floppy, a play after it, L, the double-click on the Hercules).
      *Verified in the final pass (SPEC.md 128.14.26 items 8, 11):
      `bonanzademo` on both cards - W into `SYSTEM` read back off the floppy,
      the play after it from home, L, R and D to the model's end, the 16-file
      hostile set each refused with the log, rows and claims as before, the
      double-click and three of the set refused; red arms `nosum`,
      `readfirst`, `stageleak`, `inplace`, `nohome`, `argsize` each red at
      its own check.*
- [x] **4.9 Demos as the benchmark.** `D` replays the held log with B's
      instruments and shows the results page; its misses are an upper
      bound on a play's, and it measures at most 65,535 frames. One demo
      for each tour course ships as a part, from text: the owner's when
      he has recorded one (`bbcourse.py demo` converts his `.BZR`; he
      records after O11 is settled), `MOON`'s and `SUMMIT`'s authored
      with the model, and the old courses' a route demo the build makes
      from the autopilot. Every shipped demo is checked by the model at
      build time; one recorded under other physics is re-stamped or
      demoted, never a build failure. `V` cycles them. `B` stays the
      autopilot ENGINE benchmark on `BENCH`. *Verify: `bonanzaperf`'s demo
      legs (every shipped demo, both cards, sound OFF and ON, the HUD OFF
      and REST, `MILL`'s also FOLLOW: the model's end state, `bz_wover`
      and `bz_wlate` 0, every miss reported with its parts against its
      prediction; D against R once); `bonanzacourse`'s demo item.*
      **Built** (SPEC.md 128.14.22 items 6 - 8): D as mode 3, its results
      page, the 65,535-frame stop; V through the five demo parts. Looked at:
      `MOON`'s shipped demo through D to its cup on both cards.
      *Verified in the final pass (SPEC.md 128.14.26 item 6): every shipped
      demo through D on both cards, sound OFF and ON, to the model's end with
      `bz_wover` and `bz_wlate` 0, every miss reported; D against R +4.1k a
      frame on the CGA, +3.3k on the Hercules; `bonanzacourse`'s demo item.*
- [x] **4.10 The mouse as a tilt stick.** With `T` at MOUSE, the pointer's
      offset from where it was at the play's first frame (and at each
      respawn) sets each axis's arrow and a CAP on 128.11.7.1's force
      level, over a quarter of the bracket display each way. The left
      button hops and the right grips. The log records the caps (TILT
      runs of three bytes), so a replay reads no mouse, and a keyboard
      step is wave 2's step exactly. *Verify: `bonanzaphys` `tilt` (red
      arm `tiltcap`); `bonanzareplay`'s mouse play on `MOON` replayed on
      the Hercules, its busy reported (red arm `tiltmap`).*
      **Built** (SPEC.md 128.14.22 items 9 - 11): T, the stick
      (`bbcourse.TiltStick` its model), TILT logs, the capped ramp; checked on
      the host against the models and looked at, one boot a card (a mouse play
      recorded and replayed to the same end).
      *Verified in the final pass: `bonanzaphys` `tilt` equal to the model on
      both cards (red arm `tiltcap` red at its check); `bonanzareplay`'s mouse
      play on `MOON` - 44 frames against the mapping, a TILT log of 18 runs,
      its model run equal to the play (red arm `tiltmap` red at its check).*
- [x] **4.11 Parting out, decided with the bytes.** One file, with a lazy
      part a course, as now: about 127KB, about 134 of the 360KB floppy's
      354 clusters with `ASSOC.DAT`, the README, the folders and the file. It is re-decided at
      250 clusters or when the owner wants BONANZA on a shared disk.
      Separate course files (O1), a second disk and a code part are priced
      and not taken. *Verify: the build's printed part sizes and
      `bonanza360.img`'s clusters, written into SPEC.md 128.14.9.1's table
      as MEASURED.*
      *Measured (SPEC.md 128.14.9.1, 128.14.26 item 9): `BONANZA.O88` 125,162
      bytes, 130 of `bonanza360.img`'s 354 clusters with `SYSTEM\APPDATA`
      and the README; one file.*
- [x] **4.12 kern_mega and every way out.** No `PKG_MEGA` arm is needed.
      Three ball claims, the demo's staging claim and the dialogs are each
      used whole through their own selectors. Every way out of a tour
      course, `D`, `V`, `L`, `W` and the double-click drops what it
      fetched. *Verify: `bonanzamega` (`SUMMIT` with its three balls on
      the Hercules display, the HUD FOLLOW and REST, `W`, `L`, a
      double-click, `D`; red arm `stageseg`); `bonanzaexit` (red arm
      `padleak`).*
      *Verified in the final pass (SPEC.md 128.14.26 item 2): `bonanzamega`
      on 86Box - PEAK's demo by D with its three balls on the Hercules
      display, W and L through the dialogs and D of what L read, the
      double-click opening a second BONANZA with the file, no fault charged
      to the package - after the pass found and fixed V's #GP (ES left the
      demo part's selector across its drop); `bonanzaexit` every way out of
      every course and a tour, V, D, W, L and the double-click with the rows
      and claims as before; red arms `stageseg` and `padleak` red at their
      checks.*
- [ ] **4.13 The frame, measured.** `BENCH`'s A/B against 573eec83 costs
      at most 0.5k clk a frame on the CGA (PREDICTED +0.15 - 0.3k), and B
      draws no HUD box on either card. Every shipped demo is measured with
      the HUD OFF and at REST on both cards, and `MILL`'s also with
      FOLLOW, each set beside SPEC.md 128.14.5.8's and 128.14.6's
      predictions; REST shows no HUD box on a scroll frame but a release.
      *Verify: `bonanzaperf` (red arm `hudon`).*
      **Open** (SPEC.md 128.14.26 items 4 - 6): every shipped demo measured
      through `D` on both cards, sound OFF and ON, each to the model's end
      with `bz_wover` and `bz_wlate` 0; the HUD's legs moot (removed). But
      the BENCH A/B is **+522 / +531 on the CGA** (two runs) against the
      +500 asserted, +317 on the Hercules, and `bonanzaperf`'s Hercules lift
      stretch (128.13.4.5, at most 3) missed 3 in one run and 4 in the next.
- [x] **4.14 The record.** SPEC.md 128.14 gets its MEASURED columns, and
      the diary its wave 4 entries. `apps/bonanza/README.md` gains the
      tour, the keys and the demos. `tests/pins.txt` and
      docs/HEAP-CLAIMS.md gain the three ball words and the staging claim.
      The plan's stories are ticked with their evidence. *Verify: `make`
      (the doc gates), `tools/os88index.py --check`, `checkdocs` 0
      problems.*
      *Done in the final pass: SPEC.md 128.14.26 (MEASURED), 128.14.5 and
      128.14.23 marked removed, the README's keys without `H`, the diary's
      wave 4 entry; `make` (fast tier 44), `checkdocs` 0 problems,
      `os88index --check` current. After the verifier: the HUD's removal
      carried into every binding row it touched - 128.14.1, 128.14.2,
      128.14.3.1, 128.14.3.2's line 3 and 128.14.3.4's keys (no `H`, at most
      four boxes) - and `BONANZA.DAT`'s count rule stated (128.14.17 item 6),
      SPEC.md 128.14.27.*
- [x] **4.15 Round openings (the owner, 2026-11-13).** *"For entrances/exits
      with a rounded portion on a dither, they are ending up not quite
      round."* Every arch (a windmill's doorway, every exit mouth) is a
      semicircle-topped door sheared as a whole with its face, its size,
      columns and sill unchanged, with a one-pixel solid rim on the
      checkered `+x` face; a tube's IN hole is a disc and its OUT rim a ring,
      rimmed solid on a patterned top (SPEC.md 128.14.20). `MILL`'s part
      changes in those pixels alone (a recorded deviation from 128.14.6),
      `BENCH` and `TRIAL` stay byte for byte, so the BENCH A/B is unaffected.
      *Verified on the host: `bbcourse.py --selfcheck` (the `bonanzacourse`
      row's command) items 1 (MILL 3b's but for its openings,
      with its control) and 3 (ROUND OPENINGS: sheared, symmetric, monotone,
      round, rimmed; wave 3's arch, a notch, a lopsided top, no rim and the
      square hole each failing); previews before and after on both cards;
      one look boot a card on `MILL`'s house mouth and chute mouth.*

Still open from wave 3b, and not this wave's (SPEC.md 128.13.17): 3b.4
and 3b.8 (`bonanzawheel` (6) on the CGA), 3b.3's BENCH 2.0k, and 3b.9's
image.

Still open from wave 4's final pass (SPEC.md 128.14.26): 4.6's `PEAK` misses
over O54's prediction (easing its chains is the owner's call), 4.13's BENCH
A/B (CGA +522 - 531 against +500) and the Hercules' `MILL` lift stretch (3
and 4 missed in two runs, at most 3), and `bonanzaring`'s `contact` red arm
going red at a coverage check rather than at `bz_tf`. The row now FAILS a
wheel commit over the ball's old footprint by the rule itself (green on the
right build, both cards). The arm still needs a scene in which the broken
wheel has room to commit such a lane: in the DEFER scene it never loads one
before the promotion takes it (SPEC.md 128.14.27 item 3).

*Both "still open" lists above are now carried by [Toward a
release](#toward-a-release): the wheel, BENCH's A/B, PEAK's and MILL's
misses and the image by wave 10 (T1-T9), and the `contact` arm's scene by
wave 13's first glass path (R9).*

**Next, after the owner plays wave 4 (the owner, 2026-11-14).**
*SUPERSEDED by [Toward a release](#toward-a-release) (the regroup of
2026-11-14). The items are kept as written; each one's new home is in
italics below it.*
- [~] **Course clocks instead of a HUD** (the owner's idea): a CLOCK prop the
      course author places "every so often" - a lane whose poses are digits
      in a small font of our own made to sit in the course's isometric look
      (not giant numerals), on the course itself so it scrolls with it and
      raises none of the HUD's problems (SPEC.md 128.14.16), committed by the
      wheel once a second while shown and costing nothing off screen. **It
      counts down the course's TIME LIMIT** (the owner, 2026-11-14: target
      times per course, the pressure to finish, in place of lives), and an
      **EXPLORATION mode** in the first release turns the timing off. The
      default clock is the owner's **crystal ball held up at an angle on a
      stick**; other frames for the same digits, switchable per course: a
      flip-card scoreboard on two posts (FIRST), a hanging lantern (MOON), a
      clock tower or a vane sign (MILL), a carved stone marker (PEAK), a
      sundial with a digit plate, a tethered balloon with a banner. Open:
      what happens at zero (default: the course ends and is retried; a tour
      ends), and whether time left carries over (default: no - that is
      Marble Madness's rule and this game is not a clone of it).
      *Now wave 7 (7.1-7.4, 7.7). At zero the course ends, a life is lost and play returns to the pathway (the owner's end goal); no time carries over.*
- [~] **A CGA palette per course** (the owner's idea; one OUT to 3D9h at the
      bracket's entry, which 128's other fullscreen packages already do and
      the bracket's restore undoes): palette 0 or 1, either intensity, and
      the BACKGROUND from all 16 colours (a dark blue night for MOON). The
      catch: colour 0 is both the background and the black outlines, so a
      coloured background recolours every outline - each course's choice
      wants a look. A `palette` course statement; the Hercules is unaffected.
      *Now wave 6, story 6.6, so the owner's first play gate shows it.*
- [~] **Course adjustments by play**: `SUMMIT`/`PEAK` (O54), and the rest,
      once the owner has played them.
      *Now gate 0's feedback, applied at each course's retrofit in waves 11-13; PEAK's O54 with PEAK in wave 13.*
- [~] **A performance wave** (not immediately): the targets wave 4 misses
      (BENCH's A/B bound, PEAK's and MILL's misses, the Hercules lift
      stretch, bonanzawheel (6)); the walk's slice narrowed by COLUMN as well
      as row, so props in the window's rows but off to the side cost nothing
      on wide courses (today they cost a walk, about 0.2k clk each a frame,
      and a RAM sync at a pose change); and, on the sound's price, a trial of
      half-rate sound (the owner is "not too hopeful on it sounding good") and,
      if it is not too hard, sound in the retrace wait's idle time.
      *Now wave 10 (T1-T12); the walk's column narrowing moved forward to wave 7, story 7.1.*

**Wave 5: the machines.** *SUPERSEDED by [Toward a release](#toward-a-release):
the machines are wave 14 there. kern_mega, the refusals and the four
geometries are done in practice and are ticked in wave 5a (story 5a.4).*
- [~] Hercules polish (pair art, its blank budget).
      *Now wave 14 (H1).*
- [~] kern_mega, through the ordinary FASTTICK bracket (SPEC.md 128.1).
      *Done in practice (`bonanzamega` passes on 86Box); ticked in 5a.4, re-checked in wave 14.*
- [~] VGA runs the CGA arm; EGA, MDA and kern_small refuse with reasons.
      *VGA: wave 14 (H5). The refusals are built (SPEC.md 128.1); ticked in 5a.4, re-checked in wave 14.*
- [~] Disks: `make bonanzadisk` in four geometries. The package is `local`
      in `apps/RETIRED.txt` until the owner says it ships.
      *The four images are built since wave 0; ticked in 5a.4. Shipping is wave 15's checklist, on the owner's word.*

**Wave 6: the picks from section 9**, which the owner chooses: golf mode,
ghost, link race, ball swaps, and so on.
*SUPERSEDED by [Toward a release](#toward-a-release): the ghost is
measured in wave 10 (T12); the other picks are in R8's post-release list;
ball swaps are pads, as wave 4 built them.*

A "How It Was Built" diary is started in
[BOUNCE-BONANZA-DIARY.md](BOUNCE-BONANZA-DIARY.md).

---

## 12. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
**Decided by the owner, 2026-11-12:**

| # | decision | the owner's answer |
|---|---|---|
| D1 | 2D scrolling, or vertical only? | **2D.** |
| D2 | A trackball slot, or the tilt stick? | **The keyboard is primary.** A mouse is a possible bonus at the end; a non-trackball mouse is hard for this style of game |
| D3 | Run mode, golf mode, or both? | **Direct control first.** A golf-like game may follow later as a second game on this engine |
| D4 | What a hard fall costs | **Make it a mechanic, encourage it.** The rubber ball bounces, and that is required to clear some gaps and heights; the steel ball may be stunned; a glass ball may shatter (section 5.5) |
| D5 | 16 colours | **Not the focus.** It would suit a composite monitor; consider it if the render and art budgets allow (below) |
| D6 | The name | **`BONANZA` is the package** (`apps/bonanza/`, `BONANZA.O88`); the title is *Bounce Bonanza* |

**On D5: composite is the better 16-colour route.** On a composite monitor,
the CGA's 640×200 mono mode shows *artifact colour*: 160 colour pixels a
row in 16 colours. Unlike the 80-column text trick (section 2.8), it is a
**graphics mode, so there is no snow**, and its 6845 ring is the same 8 KB a
bank with the same 80-byte rows, so **this engine scrolls it unchanged**.
The horizontal step stays one word, which is 4 colour pixels: the same
fraction of the screen as now. The cost is a second art set (the same bytes
per row as the 4-colour set), and an RGB monitor shows it as stripes, so it
is an option, never the default. The owner's CGA drives an IBM 5153 RGB, so
it needs a composite monitor to judge. Not before the game is.

## 13. Risks

*The roadmap's own risks are [Toward a release](#toward-a-release)'s R11.*

- **Real-card VRAM wait states.** MartyPC charges the measured 86 clocks a
  word, and a real IBM CGA may differ. Excitebike carries the same caveat;
  a field run settles it.
- **The beam race for columns** is the one part that a screenshot cannot
  check. `m.flicker()` on a frame with a column write is the instrument
  (PERFORMANCE.md Part 3.1).
- **Whether 8 px horizontal steps feel acceptable.** The dead zone and the
  glide are the mitigation. The fallback is narrower courses (D1 makes this
  a design choice, not a rewrite).
- **Occlusion ambiguity.** The authoring tool keys every occluding pixel
  to within 2 px (records split by band of tops) and refuses a course past
  its record bounds (SPEC.md 128.10.4.4), so this risk lands as
  course-design constraints, not run-time bugs.
- **`BENCH` sits on the block bound.** Wave 2's bound is 4 records a block
  (SPEC.md 128.11.4.2) and `BENCH`'s fullest block holds exactly 4 before
  and after the merge, so the next route or geometry change can refuse it.
  The refusal names the block; moving the geometry, or the owner pricing a
  bound of 5, is the answer - never a quiet raise.
- **A fall behind geometry on the CGA.** With the occluder pass at its
  bound, a falling ball over a cell that can hide it is predicted at 1.06 -
  1.11 CGA refreshes (SPEC.md 128.11.15): it presents a frame late and is
  counted. `TRIAL`'s flights are built to cross no such cell; wave 4's
  courses will meet it. Since wave 3b (SPEC.md 128.13.6) that frame has no camera
  relief either - the heavy rule's occluder-pass clause is gone - so wave
  4's courses price it or route around it.
- **Feel numbers off a model.** Wave 2's materials, surfaces and course
  rules are the host model's discrete figures (SPEC.md 128.11.5), checked
  against the guest frame by frame - but whether they FEEL right is the
  owner's play, and every one of them is PROVISIONAL until then (O11).
