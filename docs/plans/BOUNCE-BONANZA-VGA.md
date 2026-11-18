# BOUNCE BONANZA on VGA: a native arm with pixel-smooth scrolling (investigation and plan)

*Branch `bounce-bonanza-vga`, cut from `bounce-bonanza` at `cdb248a`
(2026-11-17). This is a plan: nothing in it is built. It extends
[BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md) section 2.8. That section
recorded the idea as "**VGA Mode X arm**: pixel-smooth scrolling both ways
(offset register plus pixel panning) and 256 colours ... **a later wave**,
not the 5150's", and nothing more. Once the owner has reviewed it, the
contract goes into SPEC.md as the next free 128.N subsection (130.46 today)
**before** any code, and this file becomes the story list.*

Figures are tagged **MEASURED** (with where), **PREDICTED** (arithmetic from
a measured or documented figure) or **ESTIMATED** (a guess to be replaced),
as in SPEC.md 130.18.

---

## 0. The answer on one screen

1. **Today a VGA is refused.** `bz_adapter` (`apps/bonanza/bonanza.asm:607`)
   accepts only `VID_CGA` and `VID_HERC`. A VGA under kern_big gets the
   toast `CGA OR HERC ONLY` and a greyed Play Game (SPEC.md 130.1, 130.26).
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

   The CGA arm's hardest rule (130.2 rule 3: columns after the latch, top
   down, ahead of the beam) does not exist on this arm. Only the boxes (the
   ball) still race the beam, as they already do on both cards.

4. **Steps become 1 px across and 1 line down.** The start address moves a
   line or a byte, and the pel pan supplies 0-7 px. This is the smooth
   scrolling.

5. **Most of the renderer is reused unchanged.** The ball, the box compose,
   the occluders, the shadow, physics, props, lanes and LATTICE's framings
   all work in world pixels, and compose is bitwise. The art is
   **converted ONCE, at load, into "planar pairs"** (8 pixels as plane 0's
   byte then plane 1's); compose then runs unchanged and the box writer only
   splits even and odd bytes into the two planes (section 3). Nothing is
   converted per frame and nothing converted goes on a disk. Only the
   writers are new, with the converter and the ball's 8-pixel placement:
   - rows, the column, boxes, the full write, the wheel's commits, cards;
   - the flip and pan;
   - `bz_vinit`'s VGA arm.

   They go in a **code part loaded only on a VGA**, because the 64 KB image
   has about 3.7 KB left.

6. **The simulation does not see the camera.** A CGA play already replays
   on the Hercules "the same trajectory, step for step" (SPEC.md 130.11), so
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

8. **RealDMG has already scrolled a VGA with the CRTC, on real iron, and
   dropped it** (branch `gameboy-CRTC-scrolling-deferred`, REALDMG-SPEC
   15.3, and REALBOY-SPEC 15.4 on that branch; section 12 here). Three of its lessons bind this plan:
   - **The PVGA1A applies the pel pan LIVE, on every line.** Its
     `tests/vgaprobe/` measured this in the field. So the start address
     must be written before vertical **blanking** begins, not merely before
     the retrace (2.4).
   - **Rate beats are visible.** A 60 Hz game on a 70 Hz display
     microstuttered. Here the physics steps at 54.6 Hz, so the ball and
     camera are drawn **interpolated** between the last two steps (6,
     rule 3).
   - **A flip that only lands when it happens to hit a window loses
     lock.** The owner's field run saw whole runs of scrolls skipped, the
     picture held for 100-300 ms after a key press. This arm **waits** for
     the retrace edge every frame, so it cannot drift, and a row asserts no
     such gap (6, rule 4).

**Recommendation:** build it in five waves, V0-V4 (section 9). **V0 is a
probe and the go/no-go.** RealDMG's `tests/vgaprobe/` already answered the
real PVGA1A for two of the three things the design rests on: the 64 KB
wrap, and when the start address and pel pan are taken. V0 brings it over
and runs it on MartyPC and the 86Box profiles, so each instrument's model
is known, and measures the third thing, what a planar byte costs.

The owner decided all six questions on 2026-11-17 (section 10). This arm
**is** H5's replacement. The VGA may target a faster machine than the 5150
(a V20 or better); 4.77 MHz holding it is a bonus, not a requirement.

---

## 1. What exists today (the investigation)

| | where | what |
|---|---|---|
| adapter choice | `bz_adapter`, `bonanza.asm:607-633` (and a copy in `bzshell.asm:78`) | `OSAPI_FSX_CAPS`; CGA (`FSXM_CGA320`) -> 1, Hercules (`FSXM_HERC`) -> 2, anything else -> 0 = refused. `[bz_herc]` = AL - 1 is the card everywhere after |
| per-card dispatch | `cmp byte [bz_herc],0` at ~20 sites (bzvideo, bzwheel, bzgame, bzphys, bonanza.asm) | no jump table; per-card values in variables set by `bz_vinit` (`bzvideo.inc:150`): `bz_W`, `bz_H`, `bz_rb`, `bz_rl`, `bz_lsh`, `bz_bend`, `bz_crtc`, `bz_vrport`/`bz_vrbits`, `bz_vrlim`, `bz_mlim`, `bz_lblank`, the 7 wheel words |
| the ring | 130.2; `bz_row` (`bzvideo.inc:419`), `bz_col` (`:567`), `bz_flip` (`:229`), `bz_vr` (`:271`), `bz_fullw`/`bz_blank` (`bzgame.inc:3857`) | sheared world, `S = (W*R0 + c0) mod 4096` words; R0 in card rows (2 lines CGA, 4 Hercules), c0 in 8 px words |
| the frame | 130.4; `bz_play`, `bzgame.inc:737-1185` | `bz_t0` sim + camera, `bz_ts` compose, `bz_tr` rows, `bz_tw` wheel, `bz_tv` retrace, `bz_tf` flip + column top, `bz_tb` boxes, `bz_tc` column rest, `bz_presented` |
| compose | `bz_boxc` (`bzvideo.inc:783`), `bz_blit` (`:1062`), `bz_occ` (`:1386`), `bz_boxw` (`:2674`) | up to 4 boxes in RAM, 2bpp, world word columns x lines; then copied to the card line by line in raster order |
| art | course part `BZC2` (blocks of 8x8, 16 bytes, 2bpp), ball `BZB3` generated by `bz_ballgen` | the Hercules arm translates blocks and ball frames IN PLACE at fetch (`bz_hxlat`, 130.11.3): the model for a per-card art transform |
| camera | LATTICE, `bz_lattice` (`bzgame.inc:2785`), 130.17.6 | policy in px and lines (64 px x 32 line lattice); output in whole columns (one per 1-2 frames) and card rows (1-2 a frame) |
| wheel | `bzwheel.inc`; card writers `bz_wpc`/`bz_wph` (`:1328-1402`) chosen at `:1171` | lane commits rewrite map words, then VRAM, in the retrace wait's time, against per-card beam words `bz_wkc`/`bz_wkh` |
| image | SPEC.md 130.40 | image ~49.9 KB plus bss ~11.9 KB in one 64 KB segment: **about 3.7 KB left**. `BONANZA.O88` ~125 KB packed |
| kern_mega | 130.1, 130.15 | ordinary bracket with `FSXF_FASTTICK`; no `PKG_MEGA` arm; nothing written through CS. `bonanzamega` (86Box) refuses its Paradise VGA and runs the Hercules |

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
64 KB in 0Dh**, so a window that straddles the wrap reads continuously.
- **The PVGA1A wraps: MEASURED in the field** by RealDMG's VGAPROBE (its
  W test, on the Victory's PVGA1A; REALDMG-PLAN's scroll round: "The
  address wraps at 64KB"). That is the 5150 #2's chip.
- **MartyPC and 86Box's OTI-067 wrap: MEASURED in V0** (section 13), with
  the same probe.
- **86Box's PVGA1A does NOT wrap** at this pin: it reads on past 64 KB
  (MEASURED in V0). That is the emulation, not the chip, and it is one of
  two reasons 86Box's Paradise is not used for this work (section 13).
- Some SVGAs do not wrap (the probe's own note); a card that fails W is
  what the fallback is for.
- **Fallback if a card does not wrap:** re-home the window before it
  reaches the top of the plane with a write-mode-1 latch copy (37 clocks a
  line on MartyPC, **MEASURED**, Excitebike), hidden behind the next
  respawn or pathway transition.

### 2.4 The latch order: three models, one order that suits all of them

A scroll writes two things: the start address (CR0Ch/0Dh) and the pel pan
(AC 13h). The cards in reach take them at different moments. **V0 measured
the emulators' columns** (section 13):

| card | start address taken | pel pan taken | source |
|---|---|---|---|
| **PVGA1A (real)** | by the start of vertical BLANKING | **LIVE, on every line**: a write during display tears below the beam | **MEASURED**, VGAPROBE's sweep on the Victory (REALDMG-PLAN, scroll round) |
| **MartyPC** | **at the vsync rise**: the pair written together just after it is a frame apart | **LIVE**: the pair written together during the display tears below the beam | **MEASURED**, V0 |
| **86Box, OTI-067** | **at the vsync rise** (as MartyPC) | **at the frame's top** (`svga_poll` at `vc == vtotal`) | **MEASURED**, V0, and its source |
| 86Box, PVGA1A | | **never**: `vid_paradise.c` sets `hoverride`, which zeroes the pan at every frame top; nor does it wrap | **MEASURED**, V0, and its source |
| QEMU | | at the retrace's end | REALBOY-SPEC 15.4 on that branch |
| IBM VGA (Abrash), Lemmings' experience | at the retrace | at once | `apps/lemmings/lemblit.inc:434` |

**Every card in reach takes the START by the vsync rise, the real chip as
early as blanking**, and the PAN either live or at the frame's top.

The probe's summary for the real chip: a start and a pan written TOGETHER
land on one frame only if written **after the last displayed line and
before vertical blanking starts**. In standard 0Dh timing (display ends at
scanline 400, blanking at 406, sync at 412) that is **6 scanlines, about
190 µs**. RealDMG retimed its frame to get a 2.9 ms border, then wrote the
flip from the foreground when a clock said the beam was there.

**This arm does not write them together.** It splits them so that each
lands well inside its own safe interval on every model above:

1. **The start address, at least `BZ_VSMARG` before the display's end**.
   This comes after the rows and the column, both off-glass (2.2). Every
   card in reach takes it at the next display's end, never sooner. It
   changes nothing on the glass until then, because it is the whole frame's
   origin, not a line's. V0: the split order stood still at every phase
   from the first line after the rise to 12 lines short of the display's
   end, on MartyPC and on 86Box's OTI-067 on all three machines, in every
   run.
2. **The edge**: wait for the retrace's rising edge ("out of it, then into
   it", `FSXW_VSYNC`'s two phases), not the level `bz_vr` tests today.
3. **At the rise, the pel pan** (AC 13h with bit 5 set so the screen stays
   on; read 3DAh first to reset the flip-flop). The beam is in the bottom
   blank, so a live pan changes nothing visible until line 0. 86Box takes
   it at the frame's top, QEMU at the retrace's end, and the IBM VGA at
   once: all of them show it on the next frame, the same frame as the
   start.
4. The boxes, in raster order (130.2 rule 4's beam race, against the VGA's
   beam words, 4.2).

**The deadline is the DISPLAY'S END, not the retrace** (the field probe's
finding, and V0's on both emulators). The loop already times the
retrace's rise off the PIT (`bz_vedge`), and the period is known, so the
display's end is predicted as the next rise less the bottom blank
(449 - 37 - 400 = 12 scanlines in standard 0Dh timing, MEASURED: the rise to
the first displayed line is 1,167-1,176 µs on MartyPC and 1,172 µs on
86Box).
- The one hazard is the band between the display's end and the rise. On
  the real PVGA1A a start written there is taken a frame after the panning
  that follows it (the field probe). The emulators take the start later, at
  the rise, so they cannot redden this band; but every one of them still
  misbehaved somewhere inside it (MartyPC and 86Box, single phases at lines
  439-445 of the 449), and never once outside it.
- If step 1 would land in that band, the arm instead waits for the rise,
  lets the old frame stand for one more refresh, then writes the start (it
  is safe from the rise on: V0 found a start written just after the rise is
  taken at the next display's end, with the panning that follows) and does
  2 and 3 at the next rise. That is a counted miss and never a shear.
- 3DAh is read once as a cross-check, as RealDMG's `rw_pgtry` does: bit 3
  set means the frame is already past the rise.
- **`BZ_VSMARG` is 12 scanlines** (381 µs, 455 PIT counts) before the
  display's end: 18 scanlines (570 µs) clear of the real chip's latch at
  blanking, and of every failure V0 saw.
- **The rise and the panning are taken with interrupts OFF, always** (a V0
  finding). With them on, an IRQ0 landing at the rise put the panning past
  the frame's top: a stray failure INSIDE the window on MartyPC (one run in
  four, at line 423) and on 86Box's 4.77 MHz XT (one in every run, at a
  different phase each time). With the rise and its panning taken under
  CLI, none in nine runs. SPEC.md 130.4 does this on the CGA only when a box
  sits at window row 0; on VGA it is every frame. The cost is the edge wait
  itself, which is idle, plus about 30 clocks of panning.

**The pan must not be written in the display either**, on a live-pan card:
that tears the picture below the beam. Step 3's position, right at the
rise, is the whole reason for the split.

### 2.5 What the CGA arm's rules become

| 130.2 rule | CGA / Hercules | VGA |
|---|---|---|
| 1 entering rows before the start | yes, minus the column's cells | yes, **with** the column's cells |
| 2 retrace, then start | level, then R12/R13 | start **first** (before blanking), then the edge, then the pan (2.4) |
| 3 column after the latch, raster order | the beam race | **gone**: the column is written with the rows, off-glass |
| 4 boxes in the column's raster order (`bz_csplit`) | yes | boxes alone in raster order; no split |
| full write | blank via 3D8h/3B8h | blank via the sequencer's screen-off (SR01 bit 5) |

---

## 3. Art and compose: converted ONCE, at load

**The owner's rule (2026-11-18): convert once, up front, and do nothing
expensive every frame.** Nothing is converted per frame, and nothing
converted is stored on a disk: the arm re-lays the art in RAM when it is
fetched, as the Hercules arm already translates its blocks and balls in
place (`bz_hxlat`, 130.11.3). The 360 KB disk gains only the converter's
code, a few hundred bytes in `BZVGA.BIN` (ESTIMATED).

**The layout: a PLANAR PAIR.** Eight pixels are one word, as on the CGA,
but the word is plane 0's byte (bit 7 the leftmost pixel) then plane 1's.
A CGA word holds the same 16 bits in another order (`hl hl hl hl` twice).

**Why compose needs no change.** Every operation compose performs is
BITWISE, pixel by pixel: the fill copies block words, the ball is mask AND
then frame OR, the shadow is an AND, an occluder lays
`((buf ^ blk) & mask) ^ blk`. A fixed reordering of the bits inside every
input reorders the bits of the result the same way and changes nothing
else. So when the blocks, the occluder masks and the ball's frames, masks
and shadow are all re-laid as planar pairs, `bz_boxc`, `bz_occ` and the
shadow run unchanged and compose a planar-pair box.

**The one thing that is not bitwise is WHERE the ball goes.** The CGA
places a ball row at a 4-pixel byte (`px >> 2`), with four pre-shifted
copies (`px & 3`). A planar pair has no 4-pixel unit: the ball is placed at
an 8-pixel word (`px >> 3`), so its converted copies carry the 0-7 pixel
shift themselves. A row becomes 4 words (20 pixels plus up to 7 of shift
fit 32), and the VGA arm's blit is `bz_blit`'s word path at 4 words.
- **Roll frames** already carry `px & 7` in the frame number (`f`, 130.5),
  so each needs ONE shift, plus the pathway's fold (`bz_fold` adds 4) as a
  second: 64 frames x 2 x 16 rows x 8 bytes = **16 KB**.
- **The disc's mask**: 8 shifts x 16 rows x 8 bytes = 1 KB.
- **Squash, stretch, shatter, the shadow**: 8 shifts each, from the four
  the ball part stores (the converter shifts by 4 more pixels).
- **Only the ball in play is converted**, at the bracket's start and when
  the material changes, into one claim dropped with the bracket: about
  **20 - 30 KB (ESTIMATED; V1 measures the claim)**.

**The course's blocks are converted IN PLACE** (planar pairs are the same
16 bytes a block), so there is no second copy of them, and rows, the column,
the wheel and compose all read the one layout. V0's RP figure was taken on
exactly this layout (plane 0 at `+2L`, plane 1 at `+2L+1`): **6,068 clocks a
41-cell row-line on the 8088**, against 13,516 converting as it goes (13.3).

**The box writer de-interleaves, it does not convert:** per line, map mask
1 and the even bytes, map mask 2 and the odd ones. About **250 clocks a
4-word line, 6k a 24-line box, on the 8088 (PREDICTED** from 13.3's byte
costs: 8 bytes at ~18 clocks plus two `out`s and the loop). Against 1,376 a
line converted the plain way, that is the per-frame saving the rule asks
for. V1 measures it against a bar of 500 a line.

**What this costs once.** The blocks (at most 1,024 x 16 bytes) and the
ball's set are converted through a 512-byte table at the fetch, about 60
clocks a word on the 8088 (ESTIMATED): of the order of a quarter of a second
for a big course plus a ball, paid on the desktop or behind a transition,
never in play.

**VGA art of its own** (16 colours, planes 2 and 3) would be NEW parts, not
a conversion, and would not fit the 360 KB disk. If it is ever made, it
ships on a separate 1.44 MB disk (the owner, 2026-11-18). The 4-colour arm
needs nothing on any disk.

**The palette.** Each course's four CGA colours (`bz_cpals`, 130.19) map to
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

LATTICE's framings and policy are already in px and lines (130.17.6): the
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
(130.4). Two rules keep a pan smooth at any such rate:

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

3. **The ball and the camera are DRAWN interpolated between the last two
   physics steps.** The steps come at the FASTTICK's 54.6 Hz and the
   display runs at 70 (or 35). At 70 Hz, 0.78 steps fall in a refresh, so
   about one refresh in five shows no step, and the ball and a smoothly
   panning window would visibly stutter. RealDMG saw exactly this, 60 Hz
   content on a 70 Hz display: "a steady picture with a MICROSTUTTER"
   (REALBOY-SPEC 15.4 on that branch). It cured it by retiming the refresh to the game's
   60 Hz. Retiming to 54.6 Hz is not on offer: it is below what a VGA
   monitor is expected to accept.
   - So the drawn position is
     `prev + (cur - prev) * phase`, where `phase` is the elapsed fraction
     of the current sub-tick. That fraction is read off the same PIT latch
     the loop already samples, and costs two multiplies a frame.
   - The ball's footprint, its roll frame (a function of position, 130.5)
     and the camera's target all take the drawn position.
   - **The simulation is untouched**: it steps, logs and replays exactly as
     on the CGA. The drawing lags it by at most one step (18.3 ms).
   - The CGA and Hercules arms are unchanged. Their steps are 8 px and 2-4
     lines, so the beat does not show there.
4. **The flip never depends on luck.** RealDMG's second scheme wrote its
   flip only when the foreground happened to look while the beam was in a
   2.9 ms border. Whenever one frame ran long (a key's work, a jump), its
   border fell inside the next draw, and the next, until the phase drifted
   back. The owner's field run saw the picture held for **100-300 ms at
   each key press**: whole runs of scrolls skipped. RealDMG refused to wait
   for the retrace because the wait cost it ~7 ms on every draw.
   - BONANZA's loop is already paced by **waiting** for the retrace (130.4),
     and the wait's time is not wasted: the wheel and the early step use
     it. So a long frame costs exactly one refresh, and the next frame is
     back on the edge.
   - The wait is bounded (`bz_vrlim`), and a timeout is counted.
   - The pace row (section 8) asserts the RealDMG signature never appears:
     over a held pan with keys tapped, **no gap between two flips is longer
     than N + 1 refreshes**.

**The instrument.** MartyPC's `m.pace()` and `m.flicker()` (PERFORMANCE.md
Parts 3.1 and 3.2) measure exactly this: pixels moved per completed frame
over a held pan, with the ball's box as the `ignore` rect. The row asserts
the pan's step sequence is constant, that no frame ever shows a start
without its pan (the shear of 2.4), and rule 4's gap limit.

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
- The blocks are converted in place: no claim.
- The ball in play, converted: about 20 - 30 KB (ESTIMATED), one claim
  dropped with the bracket and rebuilt when the material changes (section 3).
- No other new claim.
- The target is 640 KB (130.7), and the VGA machine has 640 KB.

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

**The probe (V0)** is RealDMG's `tests/vgaprobe/`, brought over and
extended (section 9, V0). It is a capability package in `tests/`, not a
branch in BONANZA. In 0Dh, on MartyPC, QEMU and 86Box, it shows:
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

- [x] **Bring `tests/vgaprobe/` over** from `gameboy-CRTC-scrolling-deferred`
      (with its `make vgaprobe` rule), rather than writing a new probe. It
      already asks the latch timing (the phase sweep), the 64 KB wrap (W)
      and the frame's timing (T). Add to it:
  - a COST page: a planar byte, a 41-word row in both block shapes of
    section 3, and a box line, on the 8088;
  - the split order of 2.4 as a fourth sweep mode, which must stand still
    at every phase from display to the rise.
- [x] Run its sweep on MartyPC `os8088_xt_vga` and on the 86Box profiles,
      and record each one's model in 2.4's table, so every later row knows
      which model it is testing. The real PVGA1A's answer is already in.
- [x] The two 86Box profiles, `vm/xt-vga` and `vm/xt-v20-vga` (section 8),
      each booted to the desktop once. **With an OTI-067, not the PVGA1A**:
      86Box's Paradise neither pans nor wraps (section 13).
- [x] Results written into this file (section 13):
  - [x] the wrap, on MartyPC and 86Box (the real PVGA1A: wraps, MEASURED);
  - [x] the latch models, and `BZ_VSMARG`;
  - [x] the byte/row/box costs;
  - [x] `wb0`.
- [x] Decide `P` (42 or 44) and the block shape (a or b): **42, and
      planar** - converted once at load, in place (the owner, 2026-11-18;
      section 3).
- [x] Go/no-go on the design: **GO** (section 13).
- *Check*: the probe's own row, red-tested: `vgaprobe` (MartyPC) and
  `box-vgaprobe`, `box-vgaprobe-v20`, `box-vgaprobe-286` (86Box), each seen
  red with `--red swap`, and MartyPC's with `--red split` too.

### V1: the arm, playable at today's steps (M-L) - BUILT (SPEC.md 130.46.9)

- [x] The SPEC.md subsection written: **130.46**, before the code.
- [x] `bz_cardk` (1 CGA, 2 Hercules, 3 VGA), `bz_vga`; `bz_adapter` accepts
      `VID_VGA` + `FSXM_VGA0D` in both copies; the face's adapter line, the
      refusal `CGA, HERC OR VGA ONLY`, and Play Game ungreyed on VGA.
- [x] `BZVGA.BIN`, the last part row, fetched on the desktop by the first
      course's `bz_cload` and held through the bracket; `bz_vinit`'s VGA arm
      (CR13 21, AC 12h 03h, the course's palette, `BZV_MLIM`, the wheel's
      words).
- [x] The converter: blocks, occluder masks and the slab's sprites in place
      at the fetch; ALL THREE balls (not only the one in play: the material
      can change mid-course, `bz_setmat`) into two copies each, one claim of
      62,496 bytes, converted again only when the held balls change. The
      dissolve's CGA copies converted as they are laid (its fade only).
- [x] The writers: rows (one line each, `bz_lsh` 0), the column (before the
      start, in the gutter), the boxes (de-interleaved, unrolled per width:
      **508 clocks a line** with the mark inside, the bar 500), the full
      write (the sequencer's blank), the wheel's commits, the cards' cells,
      the blit (8-pixel placement, the cue's sparkles from a VGA table).
- [x] The frame order of 2.4 (start, edge under CLI every frame, pan 0), the
      camera in whole columns and one-line rows.
- [x] The exit: the start address home, the exit mode set (the kernel's).
- *Checked*: BENCH's benchmark on `os8088_xt_vga`, every presented frame's
  card memory against `bonanza_ring`'s host picture - 600 frames, 0 pixels,
  all nine directions (a scratch script; `bonanzaring`'s VGA card in V3);
  looks on MartyPC and 86Box's `xt-v20-vga`; the 8088's frame MEASURED
  (busy 51.1k clocks, 410 misses in 1,200: V2's divisor). Rows named:
  `bonanzaring`, `bonanzaperf`, `bonanzaexit` (their VGA legs are V3's).

### V2: smooth (M) - V2a BUILT (SPEC.md 130.46.10); V2b the roll (130.46.11)

- [x] The pixel camera, as a DISPLAY over LATTICE rather than inside it:
      the engine's window 42 columns (P 44), LATTICE unchanged, the display a
      320 px slice at x0 following LATTICE's target through a three-tap
      filter (a column's pan 2, 4, 2 px; LATTICE's every-second-frame pan a
      steady 4; never outside the window).
- [x] The pel pan at the rise, x0 & 7.
- [x] Pacing rule 2 (D3): 64-frame windows, the first with 8 late frames
      latching 35 Hz one way. Rule 1 is NOT taken: LATTICE's cadence stays a
      function of frames (130.9), as on the CGA, so the cards agree.
- [x] Rule 4: the edge wait is the only pacing (it was already).
- [x] **V2b: what the owner's look found** - not judder from the steps but
      the roll spinning BACKWARDS at speed (35 Hz aliasing of an 8-periodic
      texture). BZV_ROLL shows phases that never step against the ball and
      at most 3 a frame (SPEC.md 130.46.11). Rule 3 (the ball between steps)
      stays unbuilt: nothing on the glass asked for it.
- *Checked*: the oracle on MartyPC - LATTICE 600 frames and the scripted
  camera 400, 0 pixels in card memory, the rendered glass (the panning
  applied) exact on every sampled frame; the 8088's benchmark: 35 Hz held,
  50 misses in 1,200 (V1: 410).

### V2c: the VGA's own camera (SPEC.md 130.46.12) - BUILT

- [x] The owner, after V2b: the camera judders as LATTICE chooses to move.
      LATTICE won on the CGA and Hercules because they scroll in 8 px and 2
      lines; the VGA scrolls 1 px, so it gets its own camera, not a mode.
- [x] A follower with a dead zone (spring 1/32 a px, damping 1/4 a 70 Hz
      tick), tuned on the host first; hard margins; the window from it, the
      nearest column; the VGA's four rows a frame.
- [x] LATTICE kept for the benchmark, the fixed and paged windows, the
      finish, cuts and the scripted camera.
- [x] The A/B: `C`'s second mode on the VGA was LATTICE while the owner
      compared; removed once they had (`C` does nothing on the VGA).
- [x] The owner's first look: stop-start microstutter, skips, a slow game
      on the 5150. Measured: 70 Hz held with one frame in 17 missed, a
      velocity rounded to 0, 1, 0, 1, and a snap that became a full write.
      Now whole steady steps with hysteresis, margins that push not snap,
      and 35 Hz latched at 2 late frames (misses counted).
- [x] The owner's feel: the edges braked, the finish coasted, the pathway
      faster (V2c); then the inching at a slow pace answered by framings and
      tracking (V2d, SPEC.md 130.46.14): *"it basically always moves like
      lattice, except for one section in MILL where it smoothly followed the
      ball vertically ... which felt natural."* The A/B dropped.
- *Checked*: MartyPC, BENCH's route on the camera 800 frames (0 px, glass
  exact, one full write, steps of at most 2 px), FIRST's free play 500.

### V3: the rows, kern_mega and the record (M)

- [ ] `bonanzaring`'s VGA card: the planar decoder, BENCH restated for 2.4,
      the negative controls and red arms of section 8, each seen red.
- [ ] `bonanzaperf`, `bonanzareplay` and `bonanzaexit` VGA legs;
      `bonanzamega` on the Paradise VGA.
- [ ] SPEC.md 130.1's adapter paragraph and 130.26's greying updated;
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
  `wb0`. A box at window row 0 is the same case 130.9 item 6 handled on the
  CGA (the CLI at the rise).
- **The 64 KB image.** The part keeps the arm out of it, but every
  `[bz_herc]` site that grows a third arm costs resident bytes. V1 reports
  the span. If it is large, more of the per-card code moves behind the
  part's dispatch.
- **Plan 2.8 said "Mode X"**, and anyone reading only that will expect it.
  If D1 is taken, 2.8's row gets a pointer here.
- **A 54.6 Hz simulation on a 70 Hz display.** Interpolation (6, rule 3)
  is the answer. If a judder survives it on the glass, the fallback is
  RealDMG's: retime the refresh. 60 Hz at 525 lines makes 1.10 steps a
  refresh, a smaller beat than 70's 0.78, but still a beat.

---

## 12. What RealDMG's CRTC round taught (branch `gameboy-CRTC-scrolling-deferred`)

RealDMG (the Game Boy emulator package) followed a game's scroll with the
VGA's CRTC twice. Both attempts drew the right picture, were run on the
owner's hardware, and were refused or deferred. Its record is
REALDMG-SPEC 15.3 and REALDMG-PLAN's scroll round (both in this tree) and
REALBOY-SPEC 15.4 (only on that branch, where the package is still called
RealBoy).

| RealDMG | what happened | BONANZA's VGA arm |
|---|---|---|
| **15.3: one page, start and pan follow SCX/SCY** | Mario and the status bar **jittered by the scroll's step every draw**. The lines were composed for the NEW origin while the card still showed the OLD one, on 86Box and on the Victory alike | Not this arm's shape. The world is stored **sheared**: a cell's VRAM address never depends on the scroll. Rows and the column are written off-glass, and the boxes only after the edge, so nothing is ever drawn for an origin the card is not showing |
| 15.3: the cure needed a retrace wait, ~7 ms a draw, more than the scroll saved on a 286 | refused on cost | BONANZA already waits for the retrace every frame, and spends that time on the wheel and the early step (130.4) |
| **15.4: three pages, the flip written by the foreground when it finds the beam in the bottom border** | worked at speed, but the field run **held the picture 100-300 ms at each key press**: a long frame put its border inside the next draw until the phase drifted back. Fixed by looking for the border during the draw as well (`rw_pgtryd`). The twin still showed 5 of 87 frames twice under tapping | 6, rule 4: the flip is waited for, not found, so the phase cannot drift. The gap is asserted by a row |
| **15.4: 60 Hz content on 70.09 Hz mode 0Dh** | **microstutter**: one frame in six held for two refreshes. Cured by retiming the refresh to 59.71 Hz (527 lines) | 6, rule 3: drawn positions interpolated between steps. 54.6 Hz is no refresh to retime to |
| **VGAPROBE** (`tests/vgaprobe/`) | the real PVGA1A **wraps at 64 KB** and **pans live, line by line**. The safe window for a start + pan pair is the bottom border, before blanking. AR10 bit 5 only stops panning below a line-compare split | 2.3 and 2.4: wrap trusted on that chip; start and pan split across the blanking. V0 brings the probe over |
| Pre-shifted copies; "motion reuse" of lines | refused on memory and on cost on a 286 | not needed: the sheared ring writes only entering rows and the column |
| The VGA retrace interrupt | "not in 86Box, varies by clone. Not generic" | not used. The edge is polled, as everywhere in this tree |

The difference that matters: RealDMG had to **follow** a game it did not
write, whose frame takes longer than a refresh and whose scroll moves
under it. BONANZA **owns** its frame: it chooses when to scroll, by how
much, and in what order its writes happen.

---

## 13. V0's results (2026-11-18)

The probe is RealDMG's `tests/vgaprobe/`, brought over, given a split
order (O), a cost page (C) and a class for this tree's windows, and driven
by `tests/vgaprobe.py` (the `vgaprobe` row; its 86Box ports
`box-vgaprobe`, `-v20`, `-286`). Each phase is judged off four consecutive
completed frames by where the probe's vertical line sits: pixel 6 means the
start and the panning came from one pair, pixel 2 from different pairs.
**A pair taken a frame apart does not shimmer**, as the probe's on-screen
legend says: (A, pan 0) and (B, pan 4) draw one picture, 4 pixels out, so
the row reads the line's POSITION, not the frames' difference.

### 13.1 The machines

| | CPU | card | BIOS |
|---|---|---|---|
| MartyPC `os8088_xt_vga` | 8088, 4.77 MHz, cycle-exact | MartyPC's VGA | GLaBIOS + BOCHS VGABIOS |
| 86Box `vm/xt-vga` (new) | 8088, 4.77 MHz | OTI-067 | GLaBIOS + Oak's |
| 86Box `vm/xt-v20-vga` (new) | V20, 10 MHz | OTI-067 | GLaBIOS + Oak's |
| 86Box `at286-port` | 286, 16 MHz (the owner's mr286) | OTI-067 | MR BIOS + Oak's |

**86Box's PVGA1A was the plan and cannot be used**: at this pin
`vid_paradise.c` sets `svga->hoverride`, which zeroes the panning at every
frame's top, so it never pans; and in mode 0Dh it reads past 64 KB instead
of wrapping (both MEASURED, the first also read off the source). The real
PVGA1A does both, so the 5150 #2's own card is the field run's (V4) alone.
`$OS88_86BOX_CARD` now names a card for a row, a name asking for a VGA
keeps a `$OS88_86BOX_VM` profile's own, and the adapter knows a V20 profile
is an XT (`necv20` was missing from its list: GLaBIOS said "Disk Boot Fail").

### 13.2 What each machine does

| | MartyPC | 86Box OTI-067 (all three) | real PVGA1A (field) |
|---|---|---|---|
| frame | 14,266 - 14,279 µs, **70.07 Hz** | 14,266 - 14,276 µs | |
| vsync | 980 µs (31 scanlines: MartyPC's, not a VGA's 2) | 525 - 534 µs | |
| rise to the first displayed line (`wb0`) | **1,166 - 1,176 µs**: 36.8 scanlines, **18.4 game lines** (PREDICTED 18) | 1,172 - 1,175 µs | |
| start taken | at the vsync rise | at the vsync rise | by blanking |
| panning taken | live | at the frame's top | live |
| 64 KB wrap | **yes** | **yes** | yes |
| split order, the rise to 12 lines short of the display's end | **still, every phase, every run** | **still, every phase, every run** | (V4) |
| split order, the last 12 lines before the rise | single failures at 439 - 445 | single failures at 439 - 446 | fails by blanking |
| together, in the display | tears below the beam | still | tears below the beam |

### 13.3 Costs (CPU clocks, net of the measurement's own; the least of 16)

| | 8088 4.77 (MartyPC) | 8088 4.77 (86Box) | V20 10 MHz (86Box) | 286 16 MHz (86Box) |
|---|---|---|---|---|
| a byte stored (`rep stosb`, 320) | **10.5** | 16.1 | 6.9 | 5.2 |
| a byte moved from RAM (`rep movsb`, 320) | **18.3** | 23.6 | 9.3 | 5.0 |
| a 41-cell row-line, PLANAR blocks | **6,068** | 6,540 | 2,488 | 1,312 |
| the same, 2bpp converted | **13,516** | ~13,000 | 5,536 | 1,992 |
| a 4-word box line converted (a call a word) | **1,376** | 1,328 | 596 | 208 |

MartyPC is the 8088's truth for the CPU; its VGA bus is a floor (an 8-bit
ISA VGA's wait states are not charged), so the field run's numbers will be
higher. 86Box is not cycle-accurate, and its figures are relative only.

### 13.4 What V0 decided, and what it hands V1

- **GO.** The ring, the wrap and the split order hold on every instrument.
- **P = 42**: one column a frame is all LATTICE asks, and nothing measured
  argues for a wider gutter.
- **Blocks: planar, converted once at load** (section 3; in place, as the
  Hercules arm translates its own): 2.2x cheaper a row-line than converting
  as it goes.
- **`BZ_VSMARG` = 12 scanlines** before the display's end, and **the rise
  and its panning under CLI every frame** (2.4).
- **The box writer is no longer a risk** (the owner's rule, 2026-11-18:
  convert once, up front). Converted every frame the plain way, a 24-line
  ball box was about 33k clocks on the 8088, half a 70 Hz refresh. Instead
  the art is converted at load into planar pairs (section 3), compose runs
  unchanged, and the box writer only de-interleaves: about 250 clocks a line
  (PREDICTED), measured in V1 against a bar of 500.
- **The 8088 will likely run at 35 Hz** (PREDICTED from the CGA arm's busy
  time and the costs above; D7 accepts it). The V20 and the 286 have the
  headroom for 70.
