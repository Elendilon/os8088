# BOUNCE BONANZA on VGA: a native arm with pixel-smooth scrolling (investigation and plan)

*Branch `bounce-bonanza-vga`, cut from `bounce-bonanza` at `cdb248a`
(2026-11-17). This is a plan: nothing in it is built. It extends
[BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md) section 2.8. That section
recorded the idea as "**VGA Mode X arm**: pixel-smooth scrolling both ways
(offset register plus pixel panning) and 256 colours ... **a later wave**,
not the 5150's", and nothing more. Once the owner has reviewed it, the
contract goes into SPEC.md as the next free 128.N subsection (128.41 today)
**before** any code, and this file becomes the story list.*

Figures are tagged **MEASURED** (with where), **PREDICTED** (arithmetic from
a measured or documented figure) or **ESTIMATED** (a guess to be replaced),
as in SPEC.md 128.18.

---

## 0. The answer on one screen

1. **Today a VGA is refused.** `bz_adapter` (`apps/bonanza/bonanza.asm:607`)
   accepts only `VID_CGA` and `VID_HERC`. A VGA under kern_big gets the
   toast `CGA OR HERC ONLY` and a greyed Play Game (SPEC.md 128.1, 128.26).
   The wave-14 story H5, "VGA runs the CGA arm", was never built. Both of
   its open questions (the mode-4 address wrap, and 3D9h's palette) go
   away if the VGA gets its own arm.

2. **Use mode 0Dh (`FSXM_VGA0D`, 320x200x16 planar), not Mode X.** The
   plan's note said Mode X. The investigation reverses that:

   | | mode 0Dh | Mode X (`FSXM_MODEX`) |
   |---|---|---|
   | the art (4 colours, 8 px a block line) | **2 planes x 1 byte** a block line: the same 2 bytes as the CGA word | 4 planes x 2 bytes = **8 bytes** a block line |
   | horizontal fine scroll | start address in 8 px bytes, **pel pan 0-7** | start address in 4 px, pan 0-3 (in half-pixel counts) |
   | vertical | start address **per line** | per line |
   | picture | **200 lines**, the CGA's window and aspect | 240 lines: a different window, and MartyPC captures only 200 of them (docs/TESTING.md) |
   | prior art here | **Lemmings** (start + pel pan + offset + split, SPEC.md 116.4.1) and **Excitebike's VGA arm** (sheared world, private start address, SPEC.md 102). MartyPC models 0Dh's pel pan (**MEASURED**, SPEC.md 102.7.5) | 1942 and WireBall flip pages; neither pans |

   Mode X's one advantage is 256 colours, and the art has four.

3. **The ring carries over with one change: a stride two bytes wider than
   the window.** Each plane is a 64 KB ring. Set CR13 (the offset register)
   to **42 bytes a line** while the glass shows 41 (40 columns plus the one
   a pan reveals). Then:
   - every entering column's cells fall in a **gutter that is never on the
     glass**, so there is no beam race for columns;
   - every entering row falls in 57 KB of slack.

   The CGA arm's hardest rule (128.2 rule 3: columns after the latch, top
   down, ahead of the beam) does not exist on this arm. Only the boxes (the
   ball) still race the beam, as they already do on both cards.

4. **Steps become 1 px across and 1 line down.** The start address moves a
   line or a byte, and the pel pan supplies 0-7 px. This is the smooth
   scrolling.

5. **Most of the renderer is reused unchanged.** The ball, the box compose,
   the occluders, the shadow, physics, props, lanes and LATTICE's framings
   all work in world pixels and in the CGA's 2bpp format. The box keeps
   being composed in 2bpp and is **converted to planes at write time**
   through a 512-byte table. Only the writers are new:
   - rows, the column, boxes, the full write, the wheel's commits, cards;
   - the flip and pan;
   - `bz_vinit`'s VGA arm.

   They go in a **code part loaded only on a VGA**, because the 64 KB image
   has about 3.7 KB left.

6. **The simulation does not see the camera.** A CGA play already replays
   on the Hercules "the same trajectory, step for step" (SPEC.md 128.11), so
   demos, replays and saves need nothing new. The `bonanzareplay` row gains
   a VGA leg as proof.

7. **The machines.**
   - The owner's **5150 #2** has a stock 8088 at 4.77 MHz and a **PVGA1A
     with 256 KB** (docs/FIELD-MACHINES.md). It is the one real VGA in this
     register, and a field run on it is the last wave.
   - MartyPC's `os8088_xt_vga` is the 8088 emulator: exact for correctness,
     but its VGA timing is only a floor.
   - **86Box** runs period VGAs with their own BIOSes on AT-class machines:
     a **PVGA1A**, the 5150 #2's chip, on `286-victory` and
     `286-mega-multimon`, and an OTI067 on the 386 profiles. That is the
     second opinion on the latch order and the wrap, and the
     higher-spec machine the owner allows (section 10).

**Recommendation:** build it in five waves, V0-V4 (section 9). **V0 is a
probe and the go/no-go.** It checks on MartyPC, QEMU and 86Box three things
the design rests on:
- the 64 KB ring wrap in 0Dh;
- the start-address/pel-pan latch order;
- what a planar byte costs.

The owner decided all six questions on 2026-11-17 (section 10). This arm
**is** H5's replacement. The VGA may target a faster machine than the 5150
(a V20 or better); 4.77 MHz holding it is a bonus, not a requirement.

---

## 1. What exists today (the investigation)

| | where | what |
|---|---|---|
| adapter choice | `bz_adapter`, `bonanza.asm:607-633` (and a copy in `bzshell.asm:78`) | `OSAPI_FSX_CAPS`; CGA (`FSXM_CGA320`) -> 1, Hercules (`FSXM_HERC`) -> 2, anything else -> 0 = refused. `[bz_herc]` = AL - 1 is the card everywhere after |
| per-card dispatch | `cmp byte [bz_herc],0` at ~20 sites (bzvideo, bzwheel, bzgame, bzphys, bonanza.asm) | no jump table; per-card values in variables set by `bz_vinit` (`bzvideo.inc:150`): `bz_W`, `bz_H`, `bz_rb`, `bz_rl`, `bz_lsh`, `bz_bend`, `bz_crtc`, `bz_vrport`/`bz_vrbits`, `bz_vrlim`, `bz_mlim`, `bz_lblank`, the 7 wheel words |
| the ring | 128.2; `bz_row` (`bzvideo.inc:419`), `bz_col` (`:567`), `bz_flip` (`:229`), `bz_vr` (`:271`), `bz_fullw`/`bz_blank` (`bzgame.inc:3857`) | sheared world, `S = (W*R0 + c0) mod 4096` words; R0 in card rows (2 lines CGA, 4 Hercules), c0 in 8 px words |
| the frame | 128.4; `bz_play`, `bzgame.inc:737-1185` | `bz_t0` sim + camera, `bz_ts` compose, `bz_tr` rows, `bz_tw` wheel, `bz_tv` retrace, `bz_tf` flip + column top, `bz_tb` boxes, `bz_tc` column rest, `bz_presented` |
| compose | `bz_boxc` (`bzvideo.inc:783`), `bz_blit` (`:1062`), `bz_occ` (`:1386`), `bz_boxw` (`:2674`) | up to 4 boxes in RAM, 2bpp, world word columns x lines; then copied to the card line by line in raster order |
| art | course part `BZC2` (blocks of 8x8, 16 bytes, 2bpp), ball `BZB3` generated by `bz_ballgen` | the Hercules arm translates blocks and ball frames IN PLACE at fetch (`bz_hxlat`, 128.11.3): the model for a per-card art transform |
| camera | LATTICE, `bz_lattice` (`bzgame.inc:2785`), 128.17.6 | policy in px and lines (64 px x 32 line lattice); output in whole columns (one per 1-2 frames) and card rows (1-2 a frame) |
| wheel | `bzwheel.inc`; card writers `bz_wpc`/`bz_wph` (`:1328-1402`) chosen at `:1171` | lane commits rewrite map words, then VRAM, in the retrace wait's time, against per-card beam words `bz_wkc`/`bz_wkh` |
| image | SPEC.md 128.40 | image ~49.9 KB plus bss ~11.9 KB in one 64 KB segment: **about 3.7 KB left**. `BONANZA.O88` ~125 KB packed |
| kern_mega | 128.1, 128.15 | ordinary bracket with `FSXF_FASTTICK`; no `PKG_MEGA` arm; nothing written through CS. `bonanzamega` (86Box) refuses its Paradise VGA and runs the Hercules |

**The OS contract allows this without new API.** In a foreign mode, SPEC.md
53.7 says *"the 6845/CRTC, sequencer, graphics controller, attribute
controller and DAC ports may all be programmed directly, and the exit mode
set reprograms everything they touch"*. Three packages already rely on it:
- Lemmings writes start, offset, line compare and pel pan;
- Excitebike writes start and line compare;
- 1942 writes start.

`OSAPI_FSX_PAGE` presents whole pages only (start = page x 4Bh00h). CLAUDE.md's "no private CRTC flips" is about presenting those advertised pages, so this arm does not use the page API. It still parks page 0 before leaving, as the precedent does.

---

## 2. The VGA ring

### 2.1 Geometry

Mode 0Dh after `OSAPI_FSX_MODE`:
- byte addressing (CR17 = E3h, CR14 = 0);
- 200 lines, double-scanned;
- 70.1 Hz;
- 64 KB a plane at A000h.

The arm then makes these changes:

| register | value | why |
|---|---|---|
| CR13, offset | **21** (42 bytes a line) | the stride `P` (2.2) |
| AC 12h, colour plane enable | **03h** | only planes 0 and 1 reach the glass, so planes 2 and 3 never need writing or clearing |
| AC 0-3, palette | the course's four colours (`bz_cpals`) as EGA 6-bit values | the CGA palette's colours; 3D9h does not exist here |
| AC 13h, pel pan | `x0 & 7` | the fine scroll (2.4) |

The byte of world line `L`, world byte column `b`, in each of planes 0 and 1, is:

    addr(L, b) = (P*L + b) mod 65536

and the window is:

    S = (P*y0 + (x0 >> 3)) mod 65536,   pan = x0 & 7

where `(x0, y0)` is the window's top-left in WORLD PIXELS. There is no
"card row" any more: `bz_rl` = 1 and `bz_lsh` = 0.

### 2.2 Why 42: the gutter

With a pan, a line shows 41 bytes, `b0 .. b0+40`. If the stride were 41 or
less, byte `b0+41` of line `r` would be byte `b0` of line `r+1` (Excitebike
hit exactly this and left its pan off, SPEC.md 102.7.5). At **P = 42**, two
cases matter:
- **Moving right one byte:** the entering byte of line `r`, `b0+41`, is
  address `P*(r+1) + b0 - 1`. That is line `r+1`'s byte just LEFT of the
  window, which is never shown.
- **Moving left:** the entering byte `b0-1` of line `r` is line `r-1`'s
  `b0+41`, the same gutter.

So **an entering column can be written BEFORE the start address changes,
with nothing on the glass**, and so can a diagonal step's corner. A wider
stride (44: a 3-byte gutter) would allow up to 3 columns a frame. V0 picks
P from the measured column cost; 42 is enough for `BZ_MAXC` = 1, which
LATTICE never exceeds.

### 2.3 No aliasing, and the slack

- **No aliasing.** Two window cells share a byte iff
  `P*dr + db ≡ 0 (mod 65536)`. Inside the window `|dr| ≤ 199` and
  `|db| ≤ 40`, so `|P*dr + db| ≤ 8,398 < 65,536`. That is zero only at
  `dr = db = 0`.
- **Window size.** A window is 8,400 bytes a plane, which leaves **57,136
  bytes of slack**, about 1,360 lines. Entering rows can never reach the
  glass, at any `BZ_MAXR` this game would choose.

The one fact this rests on is that the VGA's CRTC address counter **wraps at
64 KB in 0Dh**, so a window that straddles the wrap reads continuously. That
is true of the standard VGA design (a 16-bit counter). It has **not** been
checked on MartyPC, on 86Box's Paradise or on the PVGA1A, and it is V0's
first probe.
- **Fallback if a card does not wrap:** re-home the window before it
  reaches the top of the plane with a write-mode-1 latch copy (37 clocks a
  line on MartyPC, **MEASURED**, Excitebike), hidden behind the next
  respawn or pathway transition.

### 2.4 The latch order (Abrash's, and Lemmings')

The two halves of a VGA scroll latch at different times:
- **the start address** latches at the start of vertical retrace;
- **the pel pan** takes effect at once.

Lemmings learned this on the glass: writing both together showed a refresh
of the old start with the new pan, a shear of up to 7 px
(`apps/lemmings/lemblit.inc:434`). RealDMG's refused arm (REALDMG-SPEC 15.3)
is the cautionary half: it wrote the start address inside the retrace, which
is one refresh late.

**The order on this arm is binding:**

1. Write the start address (`S` to CR0Ch/0Dh) **during display, before the
   retrace**: after the rows and the column (both off-glass, 2.2).
2. Wait for the **rising edge** of retrace. That means "out of retrace,
   then into it" (`FSXW_VSYNC`'s two phases), not the level `bz_vr` tests
   today.
   - If the frame was already inside a retrace when step 1 ran, that latch
     has passed. The edge wait then costs a refresh, the frame is counted
     as a miss, and the picture is never sheared.
3. **At the rise**, write the pel pan (AC 13h, index with bit 5 set so the
   screen stays on; read 3DAh first to reset the flip-flop).
4. The boxes, in raster order (128.2 rule 4's beam race, against the VGA's
   beam words, 4.2).

### 2.5 What the CGA arm's rules become

| 128.2 rule | CGA / Hercules | VGA |
|---|---|---|
| 1 entering rows before the start | yes, minus the column's cells | yes, **with** the column's cells |
| 2 retrace, then start | level, then R12/R13 | start **first**, then the edge, then the pan (2.4) |
| 3 column after the latch, raster order | the beam race | **gone**: the column is written with the rows, off-glass |
| 4 boxes in the column's raster order (`bz_csplit`) | yes | boxes alone in raster order; no split |
| full write | blank via 3D8h/3B8h | blank via the sequencer's screen-off (SR01 bit 5) |

---

## 3. Art and compose

**Compose is untouched.** The box buffers stay 2bpp, in world word columns
and lines. `bz_boxc`, `bz_blit`, `bz_occ`, the shadow, the ball's four
shifts and the occluder masks all run as they do on the CGA. That is most of
the game's drawing code and all of its tests' oracles.

**Converting a 2bpp word to two plane bytes.**
- A CGA byte holds 4 pixels as `hl hl hl hl`.
- Plane 0 wants the 4 low bits as a nibble, plane 1 the 4 high bits.
- A 256-entry table of words gives both nibbles. A block line (one word, 8
  px) is two lookups and two nibble merges: about 60-80 clocks
  **(ESTIMATED)**.
- The box writer converts each line into a small line buffer and writes it
  in two passes: map mask 1 for plane 0, then map mask 2 for plane 1.

**The course's blocks need a decision between two shapes; V0 measures
them.**
- **(a) Convert at write.** Rows, the column and the wheel go through the
  same table. This costs no memory. A row is 41 words, about 3k clocks of
  conversion a line **(ESTIMATED)**.
- **(b) A planar copy of the blocks.** It is built at launch beside the 2bpp
  ones (which compose still reads), at 16 bytes a block, so at most 16 KB.
  It is a claim dropped with the bracket, like the course part. Rows and
  the column then copy bytes straight through.
- The target is 640 KB, so (b)'s claim is affordable. (b) is the default
  if V0 shows conversion costs more than a frame's row budget.

**The palette.** Each course's four CGA colours (`bz_cpals`, 128.19) map to
EGA 6-bit values in the attribute controller's registers 0-3:
- one 4-byte row a palette;
- written once by `bz_vinit` while the screen is blanked, and at each
  course's start inside a multi-course bracket, which is where `.vpal`
  writes 3D9h today.

---

## 4. The frame on VGA

### 4.1 Order

| mark | CGA / Hercules today | VGA |
|---|---|---|
| `bz_t0` | input, steps, camera | the same; the camera emits pixels (5) |
| `bz_ts` | compose | the same |
| `bz_tr` | entering rows | entering rows **and the column** |
| `bz_tw` | wheel | wheel (VGA writer) |
| `bz_tv` | early step, then the retrace level | early step, **start address**, then the retrace **edge** |
| `bz_tf` | start address, then the column's top | **pel pan** |
| `bz_tb` | boxes, with column rows between them | boxes |
| `bz_tc` | the column's rest | never marked (no column after the flip) |
| `bz_presented` | | the same |

The marks keep their names so `bonanzaperf` and the package's own
instruments read the same parts on every card.

### 4.2 Clocks (VGA mode 0Dh, standard 400-line timing)

| | value |
|---|---|
| a refresh | 449 scanlines at 31.47 kHz = **70.1 Hz = 14.27 ms = 68.1k CPU clocks = 17,025 PIT counts** (PREDICTED from the standard timing) |
| a game line | 2 scanlines = 63.6 µs = **75.8 PIT counts** (the CGA's `wla` is 76) |
| retrace rise to window line 0 | 449 - 412 = 37 scanlines, **about 18 game lines, 1.18 ms** (CGA 2.4 ms) (PREDICTED; V0 measures `wb0`) |
| a miss (1.5 refreshes) | `BZ_MLIMV` **25,540** PIT counts |

**The refresh is 15% shorter than the CGA's.** The 8088 holds the CGA's
79.6k-clock refresh at about 58-70% busy, depending on the wave and the
course, so on the same CPU the VGA's 68.1k may or may not hold the full
70 Hz. Section 6 is what happens when it doesn't.

---

## 5. The camera: pixels

LATTICE's framings and policy are already in px and lines (128.17.6): the
lattice is 64 px x 32 lines, and the bands, hysteresis and lead are all in
px. Only its OUTPUT is quantised. On the CGA it is a column every 1-2 frames
and 1-2 card rows a frame. **On VGA the same targets are reached by a
per-pixel pan:**
- a horizontal speed in px a frame;
- a vertical speed in lines a frame;
- eased toward the target, never reversing inside the band, never stepping
  past the target (LATTICE's guarantees, restated in px).

The state becomes `bz_x0`/`bz_y0` in world pixels. `c0 = x0 >> 3` and
`R0 = y0` remain for every consumer that thinks in columns:
- the boxes' clip, which becomes **41 columns wide** whenever `pan ≠ 0`;
- the lanes' walk band, `c0 ± BZ_LCM`;
- the cards.

**Limits a frame.**
- `BZ_MAXC` stays 1 column. That is 8 px a frame, 560 px/s at 70 Hz, far
  above any LATTICE pan.
- `BZ_MAXR` becomes a line count, 8 lines a frame **(ESTIMATED)**. That is
  8 x 41 words of rows, about the CGA's 2 row-pairs.
- Beyond either limit is a full write, as today.

---

## 6. Smoothness and pacing

Smooth scrolling is not the same as small steps. A pan that moves 2 px on
one displayed frame and 4 px on the next (because the frame took two
refreshes) reads as judder. The engine already paces display on the
retrace, so the display rate is the refresh divided by a whole number
(128.4). Two rules keep a pan smooth at any such rate:

1. **The camera's pixel position is a function of game time, not of frame
   count.** It advances by sub-ticks elapsed, which the loop already counts,
   so a dropped refresh moves it the right distance.
2. **The divisor is held, not left to wander.** At the bracket's start (in
   the calibration the wheel already runs, `bz_wcalib`), the arm picks N
   from the measured busy time: 70 Hz if the frame fits, else 35 Hz. It
   then waits for the Nth retrace every frame. A frame that misses even
   that is a counted miss.
   - On a 286 or faster N = 1 everywhere.
   - On the 5150 #2 it is the measurement V4 brings back.

Rule 2 is a decision (D3): it trades a few frames at 70 Hz for a constant
rhythm.

**The instrument.** MartyPC's `m.pace()` and `m.flicker()` (PERFORMANCE.md
Parts 3.1 and 3.2) measure exactly this: pixels moved per completed frame
over a held pan, with the ball's box as the `ignore` rect. The row asserts
the pan's step sequence is constant, and that no frame ever shows a start
without its pan (the shear of 2.4).

---

## 7. Code, memory and kernels

**Where the code goes.** The resident image has about 3.7 KB left, and
every VGA routine is dead weight on the 5150 #1. So the arm is a **code
part, `BZVGA.BIN`** (`OP_SEG`, far-called, as the family parts and
`BZSHELL.BIN` are):
- it is fetched on the desktop only when `bz_adapter` says VGA;
- it is dropped with the bracket.

The resident cost is the dispatch: the `[bz_herc]` byte becomes a 0/1/2
`[bz_card]`, plus a far call at each writer site. That is **about 150-300
bytes (ESTIMATED; V1 measures the span)**. The part holds `bz_vinit`'s VGA
half, the flip and pan, the edge wait, the row, column, box and full-write
writers, the wheel's commit writer, the card glyph writer and the
conversion table, about **3-4 KB (ESTIMATED)**.

**Memory.**
- The planar block copy, if V0 picks it: at most 16 KB, a claim dropped
  with the bracket.
- No other new claim.
- The target is 640 KB (128.7), and the VGA machine has 640 KB.

**Kernels.**
- **kern_big**: the target.
- **kern_mega**: A000h is an identity selector, port I/O already works in
  the ordinary bracket (BONANZA writes 3D4h there today), and a code part
  is the same far call it is for the families. So no `PKG_MEGA` arm is
  expected.
  - `bonanzamega`'s 86Box machine has a **Paradise VGA**, which today is
    refused. It becomes the VGA arm's kern_mega and real-VGA-BIOS leg.
  - kern_mega is a shipped kernel, so this leg is part of the work, not a
    follow-up.
- **kern_small**: refused at the desktop, as today.
- **EGA** stays refused (D5). It has 0Dh and pel panning, but a 64 KB EGA
  has 16 KB a plane, and nobody here has an EGA to prove it on.

**Bytes, stated per §1 of CLAUDE.md.** The resident growth is reported as a
symbol span and as `kernsize`-style bytes, not as a rung, and so is the
part's size. Nothing touches the kernel.

---

## 8. Instruments and tests

| row | change | asserts |
|---|---|---|
| **`bonanzaring`** | a **VGA card**, on MartyPC `os8088_xt_vga` | GLASS: planes 0/1 decoded through `S`, `P` and `pan` and the rendered framebuffer both equal the host's picture (the same oracle as the CGA's, palette-mapped). BENCH, restated for 2.4: at `bz_tv` (start written, edge not yet seen) the card decoded at the OLD `S` and OLD pan still equals the previous frame's picture (the rows and the column touched nothing visible), and at `bz_presented` the card at the NEW `S` and NEW pan equals this frame's. All 8 directions **and at least 8 distinct pan values** occur. Negative controls: decode at `S+1`, at `pan+1`, and poke `bz_x0+1`. New red arms: `panfirst` (pan written with the start, which must shear and go red), `stride41` (a P of 41, whose column shows on the glass), `levelwait` (the level wait, which latches a refresh late) |
| **`bonanzaperf`** | a VGA leg | the parts and period over the benchmark route; MartyPC's VGA is a **floor**, so the leg asserts the package's instruments agree with the breakpoints, and records the period rather than asserting a 70 Hz floor |
| **`bonanzareplay`** | a VGA leg | `MILL` recorded on the CGA, replayed on the VGA, equal at every frame |
| **`bonanzamega`** | VGA launches on the Paradise | no fault, no leak, the expansion through selectors, a demo's end state |
| **pace** (new part of `bonanzaring`, or its own row) | MartyPC | a held pan: constant px a completed frame; no sheared frame |
| `bonanzaexit` | a VGA leg | every way out restores the desktop (the exit mode set reprograms CR13, AC 12h, AC 13h, the palette) |

Following docs/WRITING-TESTS.md:
- every new part is broken on purpose and watched go red before it counts;
- rows drive the UI through `tools/os88ui.py`.

The tests' ring decoder is hard-coded to the 6845's banks today
(`tests/bonanza_ring.py`), so V3 adds the planar decoder beside it rather
than generalising it.

**The probe (V0)** is a small capability package in `tests/` (§ "tests/ is
everything not shipped"), not a branch in BONANZA. In 0Dh, on MartyPC, QEMU
and 86Box, it shows:
- (1) a window straddling the 64 KB wrap, read back from the rendered frame;
- (2) start-then-edge-then-pan against both-at-once, with MartyPC's
  `flicker()` seeing the shear in the second;
- (3) the cost of a planar byte, a row (both block shapes of 3) and a box
  line on MartyPC's 8088;
- (4) the rise-to-line-0 distance, `wb0`.

QEMU and 86Box answer (1) and partly (2); only MartyPC answers (3) and (4).
86Box's **PVGA1A** (`286-victory`) is the same chip as the 5150 #2's, with
its own BIOS, so it is the closest emulated answer to (2) on that card. It
is not cycle-accurate (docs/86BOX.md, *What it is NOT*), so its frame rates
are not quoted. The field run (V4) is the only real answer to (2) and to the
timing.

**86Box also carries the faster-machine leg (D7).** On a 286 the arm
should hold N = 1 (70 Hz). A held pan is driven on `286-victory` through
`tools/os88box.py` (screenshots at successive emulated times) to look for
shear and judder, which is a behaviour check rather than a timing one.
`bonanzamega` covers kern_mega on `286-mega-multimon`'s PVGA1A.

**New 86Box profiles (the owner: "you can make any profile you need").**
No 86Box profile has an XT with a VGA today, so V0 adds two, each an ISA
**PVGA1A** (the 5150 #2's chip and BIOS), with a CGA-free XT board and a
serial mouse on COM1, made the way docs/86BOX.md's existing `vm/`
directories are:
- **`vm/xt-vga`**: an 8088 at 4.77 MHz, the 5150 #2's shape. It is the
  second opinion beside MartyPC on the latch order and the wrap, on the real
  card's BIOS and an XT bus.
- **`vm/xt-v20-vga`**: a turbo XT with a **V20** (8-10 MHz). It is D7's
  "higher-spec" floor: the cheapest machine the arm is meant to hold 70 Hz
  on.

Whether 86Box offers its PVGA1A on an 8-bit XT board is checked first; if
it does not, the profiles take an 8-bit ISA VGA it does offer, and say so.
Neither is cycle-accurate, so neither is quoted for timing. They answer
behaviour: shear, wrap, judder by timed screenshots, and the divisor the
arm's own calibration picks. Each is checked to boot the desktop first, and
listed in `make help` as the existing machines are.

---

## 9. Waves and stories

Process per CLAUDE.md's *Building an app or game in waves*:
- the contract in SPEC.md first;
- one draft PR into `bounce-bonanza`, a wave a commit, the PR's checklist
  kept true;
- the diary (BOUNCE-BONANZA-DIARY.md gains a VGA chapter) written as it
  happens.

Testing per fork rule 9: each wave verifies on the host and with at most a
boot to look, and **names** its rows. One scoped soak over the union runs in
the background at the end. Disks per fork rule 3. BONANZA ships on its own
`bonanza*.img` (`local` in RETIRED.txt), so those four are the disks sent.

### V0: the probe and the go/no-go (S)

- [ ] `tests/vgapan/`: the probe package of section 8, and its row.
- [ ] The two 86Box profiles, `vm/xt-vga` and `vm/xt-v20-vga` (section 8),
      each booted to the desktop once.
- [ ] Results written into this file:
  - [ ] the wrap, on each of the three emulators;
  - [ ] the latch order;
  - [ ] the byte/row/box costs;
  - [ ] `wb0`.
- [ ] Decide `P` (42 or 44) and the block shape (a or b).
- [ ] Go/no-go on the design. A failed wrap means the re-home fallback
      (2.3). A shear MartyPC cannot show means the field run carries that
      answer alone.
- *Check*: the probe's own row, red-tested (a deliberately wrong order must
  shear).

### V1: the arm, playable at today's steps (M-L)

- [ ] The SPEC.md subsection written (the next free 128.N): sections 2-7 of this file, as the contract.
- [ ] `bz_card` (0 CGA, 1 Hercules, 2 VGA); `bz_adapter` accepts
      `VID_VGA` + `FSXM_VGA0D` in both copies; the face's adapter line
      and Play Game ungreyed on VGA.
- [ ] `BZVGA.BIN` part, fetched on the desktop; `bz_vinit`'s VGA arm (CR13,
      AC 12h, the palette, `BZ_MLIMV`, the beam words `bz_wkv`).
- [ ] The writers: rows (1 line each, `bz_lsh` = 0), the column (before the
      start, 2.2), the boxes (the 2bpp-to-planar table), the full write
      (screen-off), the wheel's commits, the cards.
- [ ] The frame order of 2.4 (start, edge, pan), at first with `pan` = 0
      and the camera in whole columns. So **vertical smoothness (1 line)
      arrives in this wave** and horizontal stays 8 px.
- [ ] The exit: page 0 parked, the exit mode set (`bonanzaexit`'s leg).
- *Check*: a boot to look on `os8088_xt_vga`, the benchmark's numbers in
  the window; rows named: `bonanzaring`, `bonanzaperf`, `bonanzaexit`.

### V2: smooth (M)

- [ ] The pixel camera of section 5: `bz_x0`/`bz_y0`, LATTICE's output in
      px and lines, the 41-column clip.
- [ ] The pel pan at the edge.
- [ ] Pacing rule 1 (camera from game time), and rule 2 if the owner takes
      it (D3).
- *Check*: a boot to look on MartyPC and on 86Box `xt-v20-vga` and
  `286-victory`, a held
  pan captured frame by frame (`pace` on MartyPC, timed screenshots on
  86Box); rows named: `bonanzaring` (pace), `bonanzareplay`.

### V3: the rows, kern_mega and the record (M)

- [ ] `bonanzaring`'s VGA card: the planar decoder, BENCH restated for 2.4,
      the negative controls and red arms of section 8, each seen red.
- [ ] `bonanzaperf`, `bonanzareplay` and `bonanzaexit` VGA legs;
      `bonanzamega` on the Paradise VGA.
- [ ] SPEC.md 128.1's adapter paragraph and 128.26's greying updated;
      H5 closed in the plan (D4); README and docs/INDEX.md regenerated.
- [ ] The scoped soak over the union, in the background (fork rule 9).

### V4: the field run (owner's machine)

- [ ] A request to the owner per docs/FIELD-MACHINES.md: the 5150 #2 with
      its PVGA1A, and any faster VGA machine the owner has to hand (D7).
      Read off the window after a benchmark:
  - [ ] the display rate and N;
  - [ ] misses;
  - [ ] by eye, shear and judder on a held pan.
- [ ] The results in the diary and in this file. They are not quoted as
      period numbers (the 5150 #2 rule).

---

## 10. Decisions for the owner

| | question | recommended | why |
|---|---|---|---|
| **D1** | Mode 0Dh or Mode X? | **0Dh** - DECIDED | Two plane bytes against eight a block line; 200 lines (the CGA's window); 1-px pan; Lemmings and Excitebike as precedent. Mode X buys 256 colours the art doesn't use |
| **D2** | The VGA camera | **LATTICE's framings, reached by pixel pans** - DECIDED | Same courses, same framings on every card; LATTICE's rules already hold in px. The alternative, a continuous follow camera, is a redesign and changes how courses read |
| **D3** | Pacing | **camera on game time (always); hold the divisor N, 70 or 35 Hz, chosen by a short test at the bracket's start** - DECIDED (*"35 or 70 on a short test is fine"*) | A constant 35 Hz reads smoother than 70/35 alternating; a 286 still gets 70 |
| **D4** | H5, "VGA runs the CGA arm" | **retire it: this arm is H5's replacement** - DECIDED | The native arm replaces it, and the CGA arm on a VGA has two unproven questions (the mode-4 wrap, the palette) and no smooth scrolling |
| **D5** | EGA | **stays refused**; later or never - DECIDED | 0Dh would work in principle, but there is no EGA to prove it on and a 64 KB EGA has a 16 KB plane |
| **D6** | Colours | **the CGA's four** - DECIDED (*"unless it's super cheap to redo the art"*). It is not cheap: see below | 16 are available in 0Dh (planes 2 and 3), but every piece of art and every test's oracle is 4-colour |
| **D7** | The machine the VGA arm is for | **a V20 or better is allowed; 4.77 MHz is a bonus** - the owner's, 2026-11-17 | VGA machines are rarely 4.77 MHz XTs. MartyPC's 8088 and the 5150 #2 still measure it, and say which divisor they get, but a 35 Hz there is not a failure |

**Why 16 colours is not cheap.** Everything that draws is 2 bits a pixel:
- `tools/bbcourse.py`'s renderer emits four indices;
- the blocks, the ball's frames and masks, the occluder masks and the box
  compose (`bz_boxc`, `bz_blit`, `bz_occ`) all work in packed 2bpp bytes.

16 colours means 4bpp art from every generator, a second compose path at
twice the bytes, VGA-only parts at twice the size, and a second oracle in
every test. That is a separate project on top of this one. What is
genuinely cheap, and inside this plan, is **choosing the four colours
freely**: the attribute controller takes any of 64 EGA colours (any of
262,144 through the DAC) for each of the four indices. So a course's VGA
palette need not be one of the CGA's two fixed sets. The tables are 4
bytes a palette and are offered in V1 as an option, with the CGA's
colours as the default.

---

## 11. Risks

- **MartyPC's VGA timing is a floor.** An 8-bit VGA on a real XT bus has
  wait states MartyPC doesn't charge. The PVGA1A's real byte cost may make
  70 Hz out of reach where MartyPC says it fits. D3's held divisor is the
  answer, D7 says a 35 Hz there is acceptable, and V4 is the measurement.
- **Latch behaviour differs between cards.** The order of 2.4 is Abrash's,
  for IBM's VGA. The Paradise is a clone, and QEMU applies a frame's
  registers when it renders it. V0 asks every instrument; V4 is the truth.
- **The box still races a faster beam.** It has the same 63.6 µs a game
  line as the CGA, but about 18 lines from the rise to line 0 against the
  CGA's 38. `bz_latechk` and the wheel's AHEAD/BEHIND passes take the VGA's
  `wb0`. A box at window row 0 is the same case 128.9 item 6 handled on the
  CGA (the CLI at the rise).
- **The 64 KB image.** The part keeps the arm out of it, but every
  `[bz_herc]` site that grows a third arm costs resident bytes. V1 reports
  the span. If it is large, more of the per-card code moves behind the
  part's dispatch.
- **Plan 2.8 said "Mode X"**, and anyone reading only that will expect it.
  If D1 is taken, 2.8's row gets a pointer here.
