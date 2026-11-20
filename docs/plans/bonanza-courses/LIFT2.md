# LIFT2: two lifts in a course (a costed study, 2026-11-20)

The owner, designing course 3 (DOWN, [DOWN.md](DOWN.md)): *"How many lifts can
we have on a stage? I'm thinking steel will probably need a lift itself; so we
may need to take glass's lift if we can't support 2."* Today the answer is
**one**: SPEC.md 130.12.4.6's bounds table says "lifts in a COURSE: 1", because
the guest tracks one lift (`bz_pidx`, `bz_pline`, its sprite and columns: the
review, 130.12.17, finding m1), and a second one would be a bare shaft on the
glass that physics still carries a ball through. The owner's O24 also allows
only one platform per window.

This is the price of lifting that to two (or a few), still **at most one per
window**. Nothing here is implemented. Figures marked **MEASURED** come from
this tree (`bounce-bonanza` at `e60fabd65`): `nasm` symbol spans out of a map
of `build/bonanza.bin` assembled byte-identical to the Makefile's, and
`tools/bbcourse.py` run on `courses/down.bbc`. Figures marked **PREDICTED**
are counted from the design's instructions and have not been assembled.

## The answer in six lines

- **Feasible, and cheap. Physics already handles any number of lifts.** Only
  the DISPLAY tracks one. The fix is to **re-point** the one tracked lift at
  whichever lift's track the current window can reach. It is not a set of
  per-lift arrays.
- **Guest: about 170 bytes of code (PREDICTED, range 140 - 220) and 10 bytes
  of bss per lift** (+21 for two, +41 for four). That is package bytes in
  BONANZA's image, not kernel bytes. No kern_mega arm, no new segment
  arithmetic.
- **Per frame: about 25 clk on a one-lift course and about 400 clk on a
  two-lift course** (PREDICTED, 0.6% of the ~65k-clk busy frames
  130.12.11 prices). The hand-over frame costs about 1.5k clk, once per crossing. It
  draws nothing: no box is added and the 4-box frame budget does not move.
- **Each lift keeps its own phase while off-screen.** The phase is a pure
  function of the step count (`bz_ppos`). On re-entry the player sees it where
  it would be had they watched all along, as a single lift does today.
- **THE CATCH IS DOWN'S LAYOUT, NOT THE ENGINE.** In DOWN as laid out, **no
  cell anywhere on the steel leg** is far enough from glass's lift. Every
  candidate shares a Hercules window with glass's track (MEASURED), so even
  today's one-per-window bound refuses it. Steel's lift must sit at
  `wx - wy >= 45`, 5 diagonal columns past DOWN's easternmost cell (40).
  Otherwise glass gives its lift up.
- **Effort: about 2 - 3 days** for the guest, the tool, the SPEC.md
  amendment, a test course and its rows. Moving DOWN's steel leg is a
  separate design job.

## 1. What is per-lift today, and what is not

### Physics: already N-lift (MEASURED by reading, `bzphys.inc`)

Every physics routine that touches a lift takes the lift's **record**, never a
cached copy:

| routine | how it finds the lift |
|---|---|
| `bz_ppos` | `ES:SI` = the record. Its one-entry cache is keyed by the record offset (`bz_pcs`) |
| `bz_carry` | `bz_onp` = the carrying record's index + 1 |
| `bz_slabon`, `bz_ptop` | the record of the shaft cell the ball's centre is in |
| step 7's `bz_onp` keep/clear | the centre cell's prop kind (`BZ_PK_PLATFORM`) |

So a second lift is already ridden, carried, landed on and fallen through
correctly. This is what the spec means by "physics still carries a ball
through". The tool's physics model (`plat_pos`, the route model) also iterates
every platform record. Its display model (`_Disp.full_sync` and the frame
choice) keeps `pline` in a dict per record.

### Display: one tracked lift (MEASURED, `bzwheel.inc`)

`bz_pread` caches the lift's record into fixed variables. A second platform
record simply overwrites the first: the last one wins. The cached
("per-lift") state is 30 bytes:

| variables | bytes | set by |
|---|---|---|
| `bz_pidx` | 1 | `bz_pread` |
| `bz_pspr`, `bz_php`, `bz_psa`, `bz_pox`, `bz_poy`, `bz_pyb`, `bz_pyt` | 14 | `bz_pread` |
| `bz_pxlo`, `bz_pxhi`, `bz_pyh`, `bz_ppv`, `bz_ppmax` | 10 | `bz_pcache` |
| `bz_pseed`, `bz_pmask`, `bz_phalf`, `bz_ppw`, `bz_pqt` | 5 | `bz_pcache` |

They are read at about 50 sites, by `bz_ptrue`, `bz_pshown(y)`, `bz_pnear`,
`bz_cslabr`, `bz_pfull`, `bz_pstrip`, `bz_pmeet`, `bz_povr`, `bz_pblit`,
`bz_mkboxes`, the calibration corner and `bz_props`. The DISPLAY state on top
of them (`bz_pline` 14 sites, `bz_ptru`, `bz_pin`, `bz_pov`, `bz_pflag`'s slab
bits, `bz_pyld`/`bz_pylp`) describes the slab **on the card**. Only one slab
can be on the card when no window holds two.

The key fact for the design: **a lift outside the shown window is not on the
card.** `bz_props`'s `.plat` already keeps such a lift's drawn line equal to
its true line in RAM (`.pout`; 130.12.15 item 3). Its display state is
therefore a pure function of `n` and can be thrown away and rebuilt. It never
has to be saved.

## 2. The cheapest design: re-point the tracked lift

### 2.1 The rule

The tracked lift is the one whose TRACK (the slab's rectangle over its whole
rise: `bz_pox` .. `+ PL_W`, `bz_pyt` .. `bz_pyb`) meets the **widened
window**. The widened window is the shown window plus the margins the walk
already uses to see a lane before it is shown: `BZ_LCM` (2) word columns
either side (the wave-7 column band, 130.18.2) and the range's 2 block rows
above and 3 below (130.12.5.2). When no lift meets it, the tracked lift stays
as it was. It is not on the card either way.

The **tool refuses** a course in which any widened window, on either card at
any position, meets two lifts' tracks. Given that bound, at the moment a lift
enters the widened window every other lift is outside it, so it is neither
shown nor on the card. The hand-over therefore never has to erase or draw
anything.

### 2.2 The guest (PREDICTED)

- **A lift table**, filled by `bz_pread`: per lift, its record index and the
  four words of its track (`pxlo`, `pxhi`, `pyt`, `pyb`), 10 bytes with a pad,
  plus a count `bz_pnl`. `BZ_LIFTMAX` entries, sized by an `%error` like the
  per-lane tables.
- **`bz_pload`** is `bz_pread`'s existing platform block (`.nl` to `.np`, 108
  bytes MEASURED, which ends by calling `bz_pcache`, 113 MEASURED) turned into
  a routine taking BX = record, ES:SI = record. The bytes are not duplicated,
  only called. `bz_pread` calls it per platform record and copies the four
  words and the index into the table.
- **`bz_ppin`** is the 30-odd bytes of `.rng` that set `bz_pin` (the track
  against the range `[8 ra, 8 rb)`; `.rng` to `.rs` is 68 bytes MEASURED, the
  `bz_pin` part about 30), turned into a routine so the hand-over can redo it.
- **`bz_psel`** derives the widened window from `bz_pwy` and `bz_pwc` (both
  set by `bz_props` every frame, and by `bz_pfull` for a full write's new
  window), then walks the table. The first entry whose track meets the
  widened window wins. If it is `bz_pidx`, return. Otherwise run `bz_pload`
  on its record, set `bz_pline = BZ_PLNONE`, clear `bz_pyld`/`bz_pylp` and
  call `bz_ppin`.
- **Two call sites.** `.plat` in `bz_props` (`cmp byte [bz_pnl], 2` / `jb`,
  so a one-lift course pays one compare) and `bz_pfull`. The full write is
  how a respawn, a tube's teleport or a paged camera lands next to the other
  lift. It runs before the launch's calibration, so the calibration corner's
  test of "the slab's rise" also reads the right lift.

| piece | PREDICTED bytes |
|---|---|
| `bz_psel` (window derivation 30, table walk 30, the load 35) | ~95 |
| `bz_pread`: the call, the table fill, the count's init | ~45 |
| `bz_pload` and `bz_ppin` as routines (call, `ret`, register set-up) | ~12 |
| the two call sites | ~15 |
| **code** | **~170 (140 - 220)** |
| **bss** | **10 x `BZ_LIFTMAX` + 1: 21 for two, 41 for four** |

For scale (MEASURED, this tree): `bz_pread` is 462 bytes, `bz_pcache` 113,
`bz_pfull` 55, `bz_props`'s `.plat`..`.choose` 106 and `.rng`..`.rs` 68. The
whole `build/bonanza.bin` is 50,954 bytes. These are **BYTES, not rungs**.
About 190 bytes buy a second lift (and a third or fourth for 10 bss bytes
each). They are package bytes in BONANZA's heap claim while it runs, not
kernel bytes, so no kernel budget is touched.

**The table walk beat the alternatives considered:**

- *A swap of two 30-byte blocks* (live and shadow, a 15-word `xchg` loop).
  About the same code, but 30 bytes of bss and only ever two lifts. It also
  needs the 30 bytes made contiguous: `bz_pwy`/`bz_pwc` sit inside the run
  today, and `bz_pidx` sits in the even byte group.
- *Per-lift arrays everywhere* (`[bz_pox + bx]` at all ~50 sites, and two
  slabs composed, boxed and chosen a frame). That is the **two-lifts-in-one-
  window** design and a different question. See section 6.

### 2.3 The tool (`tools/bbcourse.py`)

- `build_props`: replace "a second lift: a course holds one" (line ~6707)
  with "lifts a course: at most `BZ_LIFTMAX`". `bzconst.inc` exports the
  constant so the guest's table and the tool agree. The default seed
  (`ip * P // npl`) already spreads several lifts' phases.
- `check_bounds`: replace "two platforms in one window" with the WIDENED
  test above (columns `C - 2` .. `C + W + 2`, the range's rows), on both
  cards, at every window position (a paged course's fixed columns). It
  subsumes the old test.
- **Optionally, one sprite for every lift.** `slab_bytes(slab_pixels())` is
  the same 576 bytes for every lift. Today each record gets its own copy and
  the part reader insists on `so == tail` (line ~15255). Pointing every
  record at one copy saves **576 bytes of course part per extra lift**: RAM
  while the course plays, and disk. It costs 0 guest bytes (`bz_pload` reads
  `BZP_PSPR` as a pointer) and a few tool lines.
- The display model (`_Disp`) gains the same "tracked" rule, so that its
  route statistics (platform boxes, waits) keep matching the guest's counters.
- `--selfcheck` red arms: a course with two lifts whose tracks share a
  widened window but no plain window must be refused (this proves the margin
  is checked). A course with three lifts when `BZ_LIFTMAX` is 2 must be
  refused.

### 2.4 SPEC.md

130.12.4.6's row becomes "lifts in a COURSE: `BZ_LIFTMAX`; no widened window
(the walk's margins) meets two tracks". The reason becomes the re-point rule.
130.12.17's m1 row gets a note that it was closed by a design, not by the
refusal. 130.12.5.2's THE PLATFORM paragraph gains the hand-over sentence.
O24 is unchanged (one platform per window).

## 3. Independent phases, and what the player sees

**Yes, both lifts move all the time.** A lift's height is
`min(PMAX, max(0, q - W) v)` with `q` from `(n + seed) AND (P - 1)`
(`bz_ppos`, `bbcourse.plat_pos`). It depends on the global step count and the
lift's own seed, never on whether anyone is looking. Physics never reads the
display. The tool's default seeds put two lifts half a period apart.

**On re-entry** the newly tracked lift starts with `bz_pline = BZ_PLNONE`.
The next `.plat` computes its true line from `n`. While it is outside the
window it follows that in RAM (`.pout`). When it enters, the strip that
brings its columns or rows in draws it clipped (`bz_pstrip`), or its box
does. The player sees it **mid-cycle, wherever the clock says**, with no jump
and no reset. This is exactly what happens today when the one lift leaves the
window and comes back. Replays and demos are unaffected, because the phase
is deterministic in `n`.

## 4. DOWN: where a steel lift could go (MEASURED)

`courses/down.bbc` at this tree. Glass's lift is `prop platform 46 27 4`
(world; the sketch's (42, 23) + OFF 4). Its track is pixels
x 544 - 576, y 732 - 782. The course is 1,024 x 1,008 px. Windows are 320 x
200 (CGA, 40 words) and 360 x 200 (Hercules, 45 words). Every cell from
wx 52 - 67 and wy 15 - 33 was tried as a steel shaft with L = 4, about 3
units under glass's landing, against every window position of both cards:

| test | the diagonal `wx - wy` a steel lift needs |
|---|---|
| today's bound, plain windows, both cards | **43 or more** |
| the re-point design's widened windows, both cards | **45 or more** |
| DOWN's easternmost cell of any kind | **40** |

**No cell on the steel leg as it is laid out can take a lift under either
bound.** The steel leg's cells sit 80 - 352 px across from glass's track, and
between overlapping it vertically and 122 lines below it. A Hercules window is
360 px wide and 200 lines tall. The
course's right edge clamps the windows, which is why `wx - wy` 43 clears at
all.

The guest work does not change this geometry, so the owner's choice is one
of the following:

1. **Move steel's lift east.** Its shaft at `wx - wy >= 45` (e.g. a spur off
   the spikes' row at about world (63, 18)), still inside the 1,024 px width:
   x 960 - 992 at 45. Then the re-point design gives DOWN both lifts.
2. **Take glass's lift** (the owner's fallback). Steel's lift then goes
   anywhere the single-lift rules allow, and nothing in this study is needed.
3. **Two lifts in one window** (section 6). This is the only way to keep
   both lifts where the current layout would put them, and it is the
   expensive design.

A taller course does not help cheaply. Separating the tracks vertically needs
a gap of about 240 lines (the window plus the range's margins). Every steel
floor is within 122 lines of glass's track today.

## 5. Risks, cards, kern_mega

- **Performance (PREDICTED).** On a two-lift course `bz_psel` runs every
  frame: about 20 instructions of set-up and four memory compares a table
  entry, about 400 clk, or 0.6% of 130.12.11's ~65k-clk busy frames. A one-lift
  course pays `cmp`/`jb`, about 25 clk. The hand-over (`bz_pload` with
  `bz_pcache`'s `div`) is about 1.5k clk, once per crossing, on a frame where
  the new lift is by construction not shown. No box, no wheel candidate and no
  `bz_heavy` input is added. The hand-over could be gated on "the window
  moved" (the quiet walk's test), but 400 clk does not justify the bytes.
- **The 4-box frame budget** is untouched. At most one slab is on the card
  and the tracked lift's boxes are today's.
- **CGA and Hercules.** The widened test uses each card's own window width.
  The Hercules window is wider (45 words), so it is the binding card, as it
  was in section 4. `bz_hxlat`'s slab frame translation is per card, not per
  lift. The parity copies are in the sprite, which `bz_pload` re-points.
- **The camera's speed.** The hand-over relies on the margins, as the walk's
  lanes already do: the camera may not cross 2 word columns or 2 block rows
  in one frame without a full write, and a full write runs `bz_psel` through
  `bz_pfull`. If that assumption is ever broken, it is broken for lanes too.
- **kern_mega.** No arm is needed. The change is package code and bss in the
  package's own segment, reading course records through `bz_cseg` exactly as
  `bz_pread` does today (a selector on kern_mega, used only as `ES`). There
  is no segment arithmetic and no `PKG_MEGA` code. Per the kern_mega rule its
  row is still named: `bonanzamega` should get one launch and play of the
  two-lift test course.
- **The course part.** Each extra lift is a 32-byte record, plus a 576-byte
  sprite unless the shared-sprite option is taken.

## 6. The design not recommended: two lifts in one window

If the owner wants both lifts where the current DOWN layout would put them,
the slab state becomes per-lift arrays and two slabs can be on the card at
once. The cost goes well beyond the ~50 read sites:

- **The contact group** (130.12.4.3) holds one slab box. That box "cannot
  wait" while it carries the ball or while it is leaving. Two slabs can both
  be in that state on one frame, which needs a new group or a fifth box, and
  the 4-box budget and 130.12.11's busy table are priced on four.
- **The compose.** `bz_pblit`, `bz_povr` and `bz_mkboxes`'s second rect
  (`bz_crect2`) assume one slab. A box meeting both slabs needs an occluder
  order between them.
- **The tool.** The windmill exclusion, the lane-versus-sprite check, the
  start window's corner and the display model all assume one slab per window.

Rough size: **700 - 1,200 bytes** of guest code (PREDICTED, not itemised) and
a SPEC.md amendment to 130.12.4.3 and 130.12.11. It is not recommended
before DOWN's layout has been tried against option 1.

## 7. Tests that would cover it

Every row named here runs in the final pass of the work, scoped. A
sub-agent does not soak (fork rule 10).

| row | what it would check |
|---|---|
| `bonanzacourse` (`bbcourse.py --selfcheck`) | the widened bound refuses the margin case and accepts the far case. `BZ_LIFTMAX`. The shared sprite, if taken, read back by the part reader |
| `bonanzaring` | the card oracle (`plat`: `[bz_pidx]`, `[bz_pox]`, `[bz_pline]`) across a hand-over, on CGA and Hercules: the second lift appears at its true line, the first is never on the card again. Red arm: `bz_psel` disabled by a BZDEV knob turns this row red, because a bare shaft is on the glass while the slab is due |
| `bonanzaphys` / `bonanzaphyshost` | the guest against the host model, riding both lifts on one run. Physics is already generic, but no course has ever had two |
| `bonanzareplay` | a run riding both lifts replays to the same end |
| `bonanzawheel` | platform boxes and waits against the display model's counts |
| `bonanzaperf` | the frame cost on a two-lift course and on the hand-over frame |
| `bonanzamega` | one launch and play of the test course on kern_mega's Hercules |
| `bonanzademo`, `bonanzapath` | only if DOWN gains a second lift (its route demo is regenerated) |

**A test course**, BZDEV-only like TPLY and TMIL (SPEC.md 130.54): two lifts,
a widened Hercules window apart, a route riding both, and a start window
holding neither.

## 8. Effort

| piece | estimate |
|---|---|
| guest: `bz_pload`, `bz_ppin`, `bz_psel`, the table, the two call sites, the VAR and `%error` work | 0.5 - 1 day |
| tool: the bound, `BZ_LIFTMAX` export, the shared sprite, `_Disp`'s rule, the red arms | 0.5 day |
| SPEC.md 130.12.4.6, 130.12.5.2, 130.12.17 m1 | 0.25 day |
| the test course and the row changes above | 1 day |
| **total** | **about 2 - 3 days**, plus DOWN's layout change (option 1), which is design work |

## 9. Recommendation

Do **not** build the guest work for DOWN yet. Decide the layout first, since
section 4 shows that DOWN as laid out cannot hold a steel lift under any
one-per-window rule:

- If the steel leg can grow a spur to `wx - wy >= 45`, build the re-point
  design (section 2, about 190 package bytes and 2 - 3 days) and set
  `BZ_LIFTMAX` to 2. Each lift beyond that costs 10 bss bytes and is worth
  allowing only when a course asks for it. Take the shared sprite at the
  same time.
- If it cannot, take glass's lift, as the owner suggested. That is cheaper
  than the two-lifts-in-one-window design by a wide margin.
