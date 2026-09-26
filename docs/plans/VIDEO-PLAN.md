# VIDEO-PLAN — Video Player: full-motion video on a 4.77 MHz 8088

**Status: waves 0 to 7 BUILT; wave 8 under way (8a built).** Revision 3,
2026-09-25, with section 8's waves updated as they land.
- Revision 1 (commit `672a72a`) planned a port of XDC's own format.
- Revision 2 (`249f4e5`) replaced that with our own format and listed sixteen
  open questions.
- This revision records the owner's answers to those questions (section 12)
  and the design that follows from them. The four questions it raised are
  answered in section 13. Nothing is open, and Wave 0 has started.

**The owner's standing decisions:**
- Not XDC-compatible. Our own format, with the goal of playing as well as
  XDC does.
- Running code read off a disk is acceptable in principle.
- ≤ ~500 bytes of kernel, and less is better.
- No `kern_small` in this plan.

How to read the numbers:
- *Measured* means decoded exactly from the five XDC streams the owner
  supplied (BADAPPLE, THUNDERC, TRONDISC, BBBB_BW, BBBBCOMP), or taken from a
  PERFORMANCE.md set.
- *Model* means arithmetic: XDC's own cycle constants (from `XDC_CODE.PAS`,
  with CGA wait states and DRAM refresh folded in) plus an estimate of our
  decoder's instructions.
- Wave 0 replaces every *model* figure with a MartyPC reading before any
  shipped byte is written.

## 0. Summary

**Video Player** (`VIDEO.O88`, playing `.V88` files) is our own format and
player. It takes three ideas from XDC (MobyGamer, MIT, © 2014 Jim Leonard):
1. **Frames are decoded inside the audio or timer interrupt.** That work fills
   the time the CPU would otherwise spend spinning in the BIOS while disk DMA
   runs.
2. **The audio clock is the frame clock.**
3. **A budgeted delta encoder.** It commits the changed byte spans largest
   first, against a CPU pool and a disk pool, and lets a starved frame
   converge over the next few.

**The format ships operands, not code.** A frame is ten skip-coded lists of
changes. The player holds the unrolled loops that apply them. XDC's
frame-programs spend 48–65% of their bytes on `mov di,<address>` (measured).

On XDC's own 640×200 content, ours is:
- **21–46% less disk.** BADAPPLE drops from 93.8 to **57.7 KB/s**, and from
  20.1 to **12.3 MB**, so it fits the owner's ST-225.
- **+2–7 points of CPU on the mean frame.** The worst frames measure **1.01–1.28×
  XDC's cycles** on MartyPC's cycle-exact 5150: BADAPPLE's worst is 66% of a
  frame against XDC's 56%. Frames of long spans are faster than XDC's code
  (Wave 0, sections 2.2 and 2.4).

**The canvas is generic.** Any byte-aligned width and any height, in any
pixel format the target mode stores one byte at a time. So a video is encoded
for the screen it will be seen on:
- 640×200 fills a CGA, and plays unchanged on a VGA through the BIOS's CGA
  mode;
- **400×200 is 4:3 on a Hercules**;
- 320×240 or 400×300 is 4:3 on a VGA's square pixels.

Each fullscreen plays at 1:1, so no pixel is scaled at playback.

**Kernel: ~240–350 of the 500 bytes** (section 4), on `kern_big` only. It
buys a caller-rated timer interrupt for machines with no card, the streaming
file read the tree keeps needing, and a one-line fence.

**SOUND.DRV** gains a one-interrupt-per-frame stream and 4-bit ADPCM. It has
797 bytes of slack inside its 7 KB claim (measured: the image is 6,371
bytes), so that should cost no heap at all.

**What the user gets:**
- **Fullscreen** on CGA, Hercules and VGA.
- **In-window**, where the desktop stays on screen, frozen, and the video
  plays in the window at full rate.
- A windowed **Preview** with a poster frame and a keyframe scrub bar.
- The goal the owner named the tour de force: **Live windowed**, a small
  video in a window while the desktop runs, decoded in the audio interrupt so
  it keeps pace even through disk reads.

## 1. Why not XDC's format

XDC's frame is a program: `mov di,imm16` followed by unrolled `movsw`/`movsb`,
`rep movsb` or `rep stosb`, between a fixed header and `pop ds / retf`. The
player far-calls it. Measured across the samples:

| | BADAPPLE | THUNDERC | BBBB_BW |
|---|---|---|---|
| XDC code bytes per frame | 1,386 | 893 | 218 |
| …of which `mov di,imm16` | 898 (**65%**) | 426 (**48%**) | 135 (**62%**) |

Most of the "code" is addresses, and the writing instructions come from a
vocabulary of about six. XDC's encoder caps every frame at 50% of the CPU,
and the samples' worst frames all sit on that cap. So on this machine the CPU
has room and the disk does not.

Per change, the two forms compare like this:

| | bytes on disk | cycles (model) |
|---|---|---|
| **XDC** 1-byte change: `mov di,addr / movsb` (4 code bytes + 1 data) | 5 | ~35 |
| **Ours** 1-byte change: 1 skip + 1 data byte, through the player's resident `lodsb / add di,ax / movsb` | **2** | ~40 |

The 8088 has no cache, only a 4-byte queue, so our loop's instruction bytes
are fetched per iteration just as XDC's are. The difference per change is one
extra bus byte plus a register add, not a dispatch.

**Rejected after measurement:**
- **Per-row groups.** BADAPPLE averages ~2 changes per touched row, so a row
  header costs as much as the changes it groups.
- **"Hop" entries.** Bridging long gaps by rewriting unchanged bytes made
  THUNDERC 105.4 KB/s, bigger than XDC's. Segments (section 2.2) replace
  them.

## 2. The format

### 2.1 The canvas

The header names the canvas:
- **Width in bytes** (so the pixel width is a multiple of 8 at 1 bpp) and
  **height**, any value up to the target surface's.
- A **row interleave**: 1 for linear rows; 2 when the rows are stored in CGA
  bank order (even rows, then odd); 4 for Hercules order. When a canvas
  matches its surface exactly, the player decodes it with no translation at
  all (section 2.3).
- A **pixel format**. The decoder never looks at it; it moves bytes. It
  decides which fullscreen mode the player sets and which surfaces may show
  the file.
- The **aspect** the encoder assumed, so the Preview can say "made for
  Hercules" when the file is played somewhere else.

**Pixel formats.** Only version 1's are built; the rest are named so the
header has room for them.

| format | bytes mean | shown on | version |
|---|---|---|---|
| **MONO1** | 1 bpp, 1 = white | every adapter | **1** |
| **CGACOMP** | 1 bpp; each 4-bit group is one of 16 composite artifact colours (160×200×16 on a composite monitor) | **CGA only** (colour burst on). Elsewhere it plays as its mono stripe pattern, which is what an RGB monitor shows on a real CGA | **1**, and it is how XDC streams import |
| CGA4 | 2 bpp, 320×200×4, CGA mode 4, byte-native | CGA, and VGA through the BIOS's mode 4 | later: the first **colour on an 8088** with an RGB monitor |
| VGA8 | 8 bpp chunky, mode 13h, byte-native | VGA, 286+ | later: colour at 8× the bytes per pixel of MONO1 |

### 2.2 A frame's video part: ten lists of segments (settled by Wave 0)

```
frame   = [len16] [y0 16] [y1 16] video audio      (SPEC.md 98.1.3)
video   = P1 P2 P3 P4 P5 P6 SLICE RUN SLICEL RUNL     ten lists, this order
list    = segment* 00
segment = count(1..127) address(16) entry × count      skip-coded
        | 80h+count(1..127)         aentry × count     absolute (P1..P6)
entry   = skip, the change          aentry = address(16), the change
P1..P6  = 1..6 bytes
SLICE   = len8 bytes  (7..255)      RUN  = len8 value  (6..255)
SLICEL  = len16 bytes (256+)        RUNL = len16 value (256+)
```

Wave 0 changed this section more than any other. Each rule below is there
because a measurement put it there (section 8, W0).

- **The addresses are the target adapter's own memory image.** A file is
  laid out for its surface **on the host**, and nothing at playback knows
  about rows. A span that is contiguous in memory is one entry however many
  rows it crosses, so a fill of the screen is one RUNL, just as XDC makes it
  one `rep stosb`.
- **`skip`** is the number of bytes from the end of the previous write in the
  segment, one byte always. For a segment's first entry it is measured from
  the segment's address.
- **A list per short length.** A change of 1–6 bytes has its own list, and
  its store is XDC's own unrolling (`movsw / movsb` for 3). Sent through
  `rep movsw` + `rep movsb`, a short span cost +40–60 cycles, all of it rep
  start-up.
- **Absolute segments.** A skip segment's set-up measured ~215 cycles, and
  half of all segments held one entry. So an isolated change is pooled into
  an absolute segment, which costs ~14 cycles more per entry and no set-up of
  its own.
  - Below 4 entries the absolute form is also the smaller one, so it wins
    both ways there.
  - Between 4 and ~20 entries it is a cycles-against-bytes trade, and the
    encoder's machine profile makes it (section 6).
- **Hidden runs.** A stretch of one value, 6 bytes or longer, inside a slice
  becomes a RUN. That is XDC's own `FindHiddenRuns`, re-applied because the
  streams do not carry it through. It is 3 bytes on disk however long the
  stretch, and `rep stosw` into RAM is ~7 cycles a byte against a copy's ~13.
- **SLICE and RUN are Duff-unrolled too**, four to a round. RUN's length and
  value load as one `lodsw`. Spans of 256 bytes and up have lists of their
  own, so the short loops test for nothing.
- **The lists are disjoint** and each is sorted by address. The order between
  lists does not matter.
- **`y0`/`y1`** is the frame's dirty band of canvas rows, a word each
  because a Hercules or VGA canvas has more than 255 rows. It is what a
  shadow copies and what Live blits (section 3).
- **Reserved list ids** leave room for later operations, first of all
  **COPY**: a block copied from elsewhere on the screen, for pans.

**The decoder is `apps/video/vdec.inc`** (it moved there from
`tests/vidbench/` in W3, unchanged).
- It is one straight-line loop per list, entered Duff-style on the segment's
  count.
- AH = 0 is an invariant, so a skip is `lodsb / add di,ax`.
- BP is added to every segment address, which is how a window or a letterbox
  places the canvas.

**What each construct costs, measured.** MartyPC's CGA 5150, cycles, writing
the screen, each construct 60–400 times in one frame (`tests/vidbench.py`'s
synthetic rows):

| construct | XDC's code | ours | |
|---|---|---|---|
| a frame's fixed cost | 309 | 1,214 | ten list heads against XDC's header |
| 1-byte change (P1) | 36.0 | 49.6 | **+13.6**: reading the skip |
| 2-byte (P2) | 50.8 | 65.2 | +14.4 |
| 3-byte (P3) | 72.0 | 89.1 | +17.1 |
| 4-byte (P4) | 88.0 | 104.8 | +16.8 |
| 6-byte (P6) | 126.0 | 146.1 | +20.1 |
| 16-byte slice | 378 | 372 | parity |
| 40-byte slice | 895 | 804 | **−10%**: `rep movsw` against `rep movsb` |
| 16-byte run | 277 | 309 | +32 |
| 40-byte run | 638 | 621 | parity |
| a skip segment's set-up | — | ~215 | why isolated changes go absolute |

Raw stores, 8,000 bytes:
- **To CGA memory:** `rep movsw` is 18.0 cycles a byte and `rep movsb` 21.6.
- **To RAM:** `rep movsw` is 13.1 and `rep movsb` 18.0. CGA's wait states
  cap a long fill at ~18 cycles a byte whichever instruction writes it.

### 2.3 Surfaces, layouts and presets

**One decoder, and the layout is decided on the host.** A file's addresses
are the memory image of the surface it was made for:
- **CGA layout:** B800, two banks, 80 bytes a row. It plays natively on a CGA
  and, through the BIOS's mode 6, on a VGA or an EGA.
- **Hercules layout:** B000, four banks, 90 bytes a row.
- **VGA mode 12h layout:** A000, linear, 80 bytes a row.

A fullscreen position or a window's content origin is BP, added to every
segment address. That requires the origin to keep the bank phase: y a
multiple of the bank count, and x on a byte.

**Wave 0 built and measured the alternative, and it is REFUSED.** It was a
translating decoder that placed a canvas on a surface of another layout
through a row table at playback:
- it cost **~480 cycles per row change**, and the frames change rows almost
  every entry (3–12× XDC's cycles on the samples);
- it forced every span to be split at its row end, and that split is what
  turned the heaviest frames into ~290 runs where XDC has one `rep stosb`.

So translation moved to the host. **`os88vid import --target herc|vga`**
re-lays an XDV out for another adapter, and the result plays natively there.

**A file on a surface it was not laid out for** decodes natively into a RAM
**shadow**, and the frame's dirty band is copied (or, in a window, blitted)
to the screen:
- **Decode stays real-time and in sync with the sound.** Only the DISPLAY
  rate drops, because a full-screen copy measured **3–5× a native decode**:
  the dirty band spans nearly the whole screen on real content.
- It is the Live window's path too (section 3.4), where the canvases are
  small.
- The Preview says the file was made for another screen and names the
  import that makes it native.

**Fullscreen modes**, all at 1:1, each canvas centred:

| adapter | mode | 4:3 presets the encoder offers | notes |
|---|---|---|---|
| CGA | `FSXM_CGA640` (mode 6) | **640×200** (full screen); **320×100** (a quarter of the data, which also fits a window) | CGACOMP turns the burst on (3D8h ← 1Ah); the 6845 and 3D8h are the app's past the mode set (§53.7) |
| Hercules | `FSXM_HERC` (720×348) | **400×200** (the fast default); **480×232**; 720×348 (full, heavy) | Hercules layout. The 6845 is never retimed (section 7) |
| VGA / EGA | `FSXM_VGA12` for square-pixel canvases; `FSXM_CGA640` for CGA canvases | **320×240** (the fast default); **400×300**; 640×480 (full, heavy) | In mode 12h, Map Mask 0Fh with write mode 0 puts a MONO1 byte into all four planes, so MONO1 is byte-native there. A CGA canvas plays through mode 6 and looks exactly as it does on a CGA |

**Data cost follows pixel count, not screen area.** Against 640×200's
128,000 pixels:

| canvas | pixels | relative data |
|---|---|---|
| 400×200 (Hercules) | 80,000 | ×0.63 |
| 320×240 (VGA) | 76,800 | ×0.60 |
| 320×100 (CGA small) | 32,000 | ×0.25 |

This is an estimate from pixel count; Wave 1 re-encodes to measure it.
**CGACOMP off a CGA** plays as its mono pattern.

### 2.4 The format against XDC, on the samples

These are XDC's 640×200 frames exactly as XDC's encoder chose them,
re-expressed in the format above (`os88vid verify`: all 11,192 frames of the
five streams decode to XDC's screen exactly). Our encoder will re-budget on
*our* costs, so its frames will sit under their cap the way XDC's do.

| stream | disk, XDC → ours | file, XDC → ours | CPU mean, XDC → ours (model) | worst frame, XDC → ours (measured) |
|---|---|---|---|---|
| BADAPPLE (mono, 30 fps, 22 kHz) | 93.8 → **57.7 KB/s (−39%)** | 20.1 → **12.3 MB** | 14.8% → 21.5% | 56.1% → 65.9% |
| THUNDERC (composite, 23.976 fps) | 92.8 → **72.9 (−21%)** | 6.9 → 5.4 | 24.4% → 26.8% | 54.5% → 57.6% |
| TRONDISC (composite, 23.976 fps) | 105.1 → **80.8 (−23%)** | 5.0 → 3.8 | 27.0% → 30.3% | 56.3% → 62.2% |
| BBBB_BW (mono, 60 fps, 8 kHz) | 42.1 → **22.9 (−46%)** | 0.3 → 0.2 | 5.9% → 9.4% | 54.8% → 52.9% |
| BBBBCOMP (composite, 60 fps) | 46.4 → **28.0 (−40%)** | 0.3 → 0.2 | 7.9% → 11.3% | — |

How the columns were taken:
- **Disk** includes the audio, identical in both. XDC's figure also carries
  its 512-byte padding per frame; ours pads once per 32 KB super-packet.
- **CPU mean** applies the measured per-construct costs of section 2.2 to
  every frame of the stream.
- **Worst frame** is a direct measurement on MartyPC's CGA 5150, as a
  percentage of the frame period. XDC's column is XDC's heaviest frame. Ours
  is the heaviest of the frames the model ranks worst for us, all measured.
- **Neither CPU column includes the audio copy.**

What the table says:
- **Frames of long spans are FASTER than XDC's code.** They measured
  0.67–0.98× on CGA and 0.48–0.90× on VGA, which MartyPC models without wait
  states.
- **Frames of many small changes are slower,** 1.2–1.6×. They are cheap
  frames either way.
- **The heaviest frames are 1.01–1.28× XDC's.**

On the owner's machine the disk binds and the CPU has room (section 3.2), so
that trade buys a **39% smaller BADAPPLE for a worst frame at two-thirds of
the machine**.

**Audio is ~38% of BADAPPLE's stream in our form**, which is why section 2.5
carries ADPCM.

### 2.5 Audio

The header names the audio format, and both are built.
- **PCM8**: 8-bit unsigned mono at the encoder's chosen rate, as XDC.
- **ADPCM4**: Creative's 4-bit ADPCM, which a DSP 2.00 or later decodes in
  hardware at **no CPU cost**. It is half PCM8's bytes, so BADAPPLE would
  drop from 57.7 to ~47 KB/s.
  - It is noisier than 8-bit PCM at the same rate. The trade is between
    ADPCM at a high rate and PCM at half that rate for the same bytes, and
    that is a listening test Wave 0 sets up.
  - The DSP's rate ceiling for ADPCM is unverified, and **MartyPC does not
    emulate ADPCM** (its `sblaster.rs` says so, and wave 0 read zero
    interrupts). It is a field item: `tests/vidsnd.py`'s bench carries the
    row.

The encoder picks per stream, and its profile says which one hits the disk
budget. **No card means silent video.** A PC-speaker path may come later for a
video small enough to leave the CPU it needs (§34.1 priced it at 36–50%).

### 2.6 The container

**SPEC.md 98.1 is the contract now** (wave 1), and it changed two things
below. **The stream has no index**: each super-packet carries the next one's
size, so a player holds nothing but the super-packet it is reading, where a
one-hour index would have been ~54 KB. **Everything the Preview reads is at
the front** (the header, the keyframe table and every keyframe), because
`READ_AT`'s cost grows with the offset. The list below is the design as it
was proposed.

It is written by the host tools only. The player checks every field it
depends on, because a truncated copy is ordinary.

- **Header** (one sector):
  - signature, version;
  - a **rendition count** (always 1 in version 1) and a table of renditions,
    each a canvas (section 2.1) with its own super-packet index and keyframe
    table. A later version can then carry several canvases in one file, and a
    player reads only the one it plays (section 13, answer A);
  - rate: `samplerate / achunk` = fps, as in XDC; audio format;
  - frame count, largest super-packet;
  - the **poster keyframe**;
  - table offsets, and a title and credits field for the Preview.
- **Super-packets** of whole frames, at most 32 KB, padded to 512 bytes once
  each. 32 KB is XDC's own read size and fits every cluster size up to
  32 KB.
- **Super-packet index:** sectors, first frame and frame count for each. The
  ring wraps only on a super-packet boundary.
- **Keyframe table** (section 2.7).

### 2.7 Keyframes and the poster

- **What a keyframe is.** The encoder simulates the stream exactly and stores
  the decoded screen after frame *k*, every **2 seconds**. It is an ordinary
  frame of lists against black, so the player needs no second decoder.
  It lives in its own region and costs disk space and **no playback
  bandwidth**.
- **Space.** The encoder prints what the keyframes took. If they come to a
  large share of the file, the interval is the knob (the owner's rule: a
  bonus feature does not get half the disk).
- **The poster** is a keyframe index in the header, chosen at encode time. It
  defaults to the first keyframe that is not ≥ 98% one value, and it can be
  overridden.
- **Seeking** snaps to the keyframe at or before the target: decode it to the
  surface, re-seed the read at its super-packet, restart the audio there. An
  exact seek (keyframe plus replay) is offered only on a paused picture.

## 3. The player

### 3.1 The engine

**The interrupt hook**, XDC's shape:
1. Copy the frame's audio chunk into the half of the double buffer the card
   just finished, with `rep movsw` (7.9% → 5.8% of a 30 fps frame at 22 kHz
   against XDC's `rep movsb`, model). ADPCM chunks are copied the same way.
2. Decode the frame's lists onto the surface.
3. Advance.

If the ring is empty, it plays silence and counts a *pause*.

**The foreground** fills the ring and polls the keyboard:
- It reads a whole super-packet at a time through `OSAPI_FILE_READ_SEQ`
  (section 4.2).
- The ring is claimed at start-up, up to ~256 KB of the 426 KB arena a
  640 KB machine has with the hard disk ticked (§50.3). A clip that fits is
  read whole before it plays.
- **Esc always stops**, whatever the frame rate. The hook runs with
  interrupts off (the owner accepts a lost second keypress), but the
  keyboard latches a scancode and the foreground sees Esc at its next poll.

**Where the interrupt comes from:**
- **With a card:** SOUND.DRV's frame stream (section 4.4).
- **Without one:** `FSXF_RATE` (section 4.1).

**At the end**, a statistics card shows pauses, CPU idle and time on the
disk, so a field run is a photograph.

### 3.2 The CPU budget — what the cap is and what sets it

XDC's encoder caps every frame at 50% of the machine. That figure was
calibrated on hardware, and the rest is left for the disk and the audio. With
decoding in the interrupt, the question is not "video or audio". It is:
**how much CPU does the foreground need to keep the disk streaming?**

- **On a DMA disk (the ST-225 on its ST11M)**, the controller moves the bytes
  while the CPU spins in the BIOS, and the interrupt uses that spin. The
  foreground needs little: issuing each transfer, walking the cursor's
  clusters, bookkeeping. Plus the DMA's own bus cycles (~4 a byte, ~5% at
  60 KB/s) and DRAM refresh, which the cost model already carries. So the
  cap there can plausibly go **well above 50%**.
- **On a disk the CPU copies**, which is likely the PicoMEM 2's path and is
  certainly XT-IDE's, every byte read is foreground CPU. The cap must be
  lower.
- **A silent video** hands the audio copy's share (~6% at 22 kHz/30 fps) back
  to the picture. A PIT interrupt is otherwise the same as the card's.

**So the cap is a property of the machine's disk path, and the encoder takes
it from a profile.** It sets two limits:
- **An average over any one second.** This is the real constraint, because
  it is what the foreground has to live beside. The default is 50%, XDC's
  proven figure, raised per profile once Wave 0 and a field run have
  measured the ceiling.
- **A per-frame ceiling, 85% by default.** One frame may spend far more than
  the average, so a scene cut is drawn in one or two frames instead of
  converging over ten, as XDC's `frameIntegrity` must. It still has to finish
  inside its own frame period.

The burst allowance is the one encoder change that should make ours look
*better* than XDC at the same average cost, and Wave 8 measures it.

### 3.3 The windowed tiers

| tier | what the user sees | how |
|---|---|---|
| **Preview** | The poster in the window; a scrub bar over the keyframes; an info panel with fps, length, KB/s, the screen the file was made for, and whether *this* machine's disk keeps up | Decode one keyframe into a RAM shadow, then `OSAPI_GFX_BLIT1` (§5.4.2) |
| **In-window** | Full-rate video with sound in the window's rect. The rest of the desktop stays on screen, frozen, with no pointer | A **same-mode** bracket (§53.7: no `fsx_mode`, nothing cleared), with the decoder's BP at the content origin when the file's layout is the desktop's, and the shadow path otherwise (section 2.3). On exit the rect is read back into the shadow for repaints. **Only canvases that fit the content area are offered**: on CGA that is 320×100, on Hercules up to 640×200 (so XDC's 640×200 plays in a window there), on VGA anything to ~624×400 |
| **Live** | A video in a movable window while the desktop runs: small canvases (e.g. 160×120, 240×180, CGA 320×100) | Section 3.4 |

### 3.4 Live windowed — the tour de force

**Two walls** stood in the way, and both come from the kernel's shape, not
from speed:
- A disk read holds `[sch_lock]`, which freezes every worker
  (UI-FREEZE-PLAN 1).
- Nothing may draw from an interrupt while the desktop is live.

**The design goes round both. Decode and display are split:**
- **Decode stays in the interrupt.** SOUND.DRV's frame stream calls the hook
  outside a bracket as well. The hook decodes into the **RAM shadow**, which
  is not the screen, so it keeps pace with the audio *through* disk reads,
  just as fullscreen does. It also ORs each frame's `y0`/`y1` into a
  pending dirty band.
- **Display is a worker.** At ≤ 18.2 Hz it takes the gfx lock and the window
  clip, and `OSAPI_GFX_BLIT1`s the pending band of the shadow (the Wire
  pattern, `apps/wire/wire.asm`). At ~5 µs a byte (PERFORMANCE.md Set 64), a
  whole 240×180 frame is ~27 ms, and a typical frame's band far less.
- **The disk is read on the UI task** (§20.6 rule 7), in `W_ONWAKE`, one track
  at a time (~8.5 KB on an ST-225) so each freeze is short.
- **During a read the picture holds** for the read's length, ~100 ms twice a
  second at ~15 KB/s. The sound does not break, and when the read ends one
  blit shows the *current* frame. It never falls behind.
- **A clip that fits in memory has no holds at all.**

**Without a card**, Live decodes in the worker from `[ticks]`. It then stops
during reads and catches up afterwards, so on such machines Live is offered
for RAM-resident clips only.

**The region must not move** while an interrupt can call into it. Every
package declares its region movable (§66.6.1.1), so Live pins it for the
length of the stream. The pin itself is section 13's question C.

## 4. What os8088 grows

**The kernel items are `kern_big` only, per the owner's decision.**

### 4.1 `FSXF_RATE` — a caller-rated IRQ0 inside a bracket *(kernel)*

- It is a third `OSAPI_FSX_RUN` flag. DX is a PIT divisor, and a far hook
  goes with it.
- `sch_isr` adds the divisor to a 16-bit accumulator. It chains the BIOS tick
  and `[ticks]` only on **carry**, so the 18.2 Hz clock stays exact at any
  rate. That is XDC's `noSoundIntCaller`. `sch_fast_on`
  (`kernel/sched.inc:486`) is exact only for 65536/N.
- The hook runs on every entry with IF = 0.
- §53.6's restore removes it like `FSXF_FASTTICK`, so a crashed program
  cannot leave the PIT fast.
- It is general: a game at an exact 35 Hz, or a tracker at its row rate, can
  use it.
- **70–110 bytes of `.text` + 8 of `.bss`, resident** (estimate).

### 4.2 `OSAPI_FILE_READ_SEQ` — the streaming read *(kernel)*

The owner notes the tree keeps needing this and keeps finding it has only
been danced around. `OSAPI_FILE_READ_AT` re-walks the directory and the
cluster chain on every call (§18.4.4). A 20 MB partition has 2 KB clusters
(§52.3), so 13 MB into a file that is ~6,600 FAT steps per call (model;
DISK-CPU-PLAN 3.1).

§18.4.4's reason for statelessness stands: a token held **in the kernel** is
destroyed by the writes a copy loop does. So the token is the **caller's**:
- **The first call** stats by name and fills a caller-owned 16-byte cursor:
  volume, directory cluster, first cluster, size, current cluster, offset,
  and the volume's mount generation.
- **Later calls** read up to 63,488 bytes of whole clusters from the cursor's
  cluster.
- **A remount or media change** answers `FERR_NAME`, and one `READ_AT`
  re-seeds.
- **The rule:** *a cursor is valid until anything writes that file.* No
  sector number is ever exposed to the caller.
- It is published as a general slot. The Audio player (§86.5) is the next
  consumer.
- **150–220 bytes of `.cold`, resident** (estimate).

### 4.3 The progress-box fence *(kernel)*

`fpg_arm` refuses only in a *foreign* mode (`kernel/fprog.inc:331`), so a
same-mode bracket, which is In-window, gets the disk box drawn over the
video. The fix is to refuse in **any** bracket. It is a bug fix in its own
right (GFX-FSX-PLAN 4.2.1). **< 10 bytes.**

### 4.4 SOUND.DRV *(driver, not kernel)*

**Superseded by what W4 built** (section 8, W4; SPEC.md 34.5.3): an
external ring the card plays in place, not a frame stream with a callback.
What follows is the design as it was costed before §34.5.2 existed.

The driver's block is fixed at 2048 bytes (`drivers/sound/sb.inc:103`) and
`sbl_isr` has no callback (§34.3). So:
- **`SND_OPENF_FRAME`.** The caller gives a block (= `achunk`, 64–4096) and a
  far callback. The driver runs auto-init DMA over a `2 × block` page-safe
  double buffer with DSP block length = `achunk`, so it raises one IRQ per
  frame. It calls the hook after the DSP acknowledge and before EOI, with
  IF = 0 and ES:DI at the half just played.
- **ADPCM4 auto-init** (section 2.5).
- **The owner's limit: no more than 1 KB of heap growth, and no loss of
  performance.** The image is 6,371 bytes in a 7,168-byte claim (measured),
  so **up to 797 bytes cost no heap at all**. The two items are estimated at
  ~250–400 bytes. If they cross 797, one more KB is claimed: still inside the
  limit, but it will be reported.
- **The fallback** is to suspend the driver (§51.11.1) and program the DSP
  from the player. That duplicates ~400 bytes of driver code and inherits
  §96.17.1's unknown-IRQ problem.

### 4.5 The budget

| item | bytes (estimate) | **measured, W2** | resident |
|---|---|---|---|
| `FSXF_RATE` | 78–118 | **~180 `.text` + 11 `.bss`** | kern_big |
| `OSAPI_FILE_READ_SEQ` | 150–220 | **252 `.cold` + 9 `.text` + 21 `.bss`** (W3 moved the buffer to DX:BX: +55 / +20) | kern_big (`.cold` is resident) |
| progress fence | < 10 | **3**, plus **7** for the nested-chain switch guard it found | both kernels |
| **kernel total** | **~240–350 of ~500** | **kern_big 483** (`.text` +199, `.bss` +32, `.cold` +252); **kern_small 26** | |

**Wave 2 came in at 408 of the owner's ~500.** It was 574 on the first
build. Two changes brought it down:
- `READ_SEQ` became a wrapper around `READ_AT`, 331 → 197 bytes: its cursor
  stands in for READ_AT's stat and walk rather than duplicating them.
- The rate hook reaches the package's dispatcher through its window record
  (`wm_pkgcall`'s own way) instead of a kernel copy of the pointer, −16.

The estimates were low for `FSXF_RATE` because the hook has to be safe, not
just called:
- it skips while nested in the ROM's chain or on a ROM's stack;
- it runs under `[sch_lock]`;
- it counts the periods it skipped.

The `.cold` bytes crossed one 512-byte cold rung (footprint +512, 45 steps
of `KERN_BUDGET` left).
| *in reserve:* hard-disk runs that cross a head, as `CYLRUN` does for floppies (§18.91.1), **if Wave 0 shows** rung 0's stop at each track end (17 sectors, §52.1) is what caps the ST-225 | ~100–150 | kern_big |
| SOUND.DRV frame stream + ADPCM | ~250–400 | inside the driver's existing 7 KB claim. **Built as an external ring + ADPCM4: 194 bytes**, 6,371 → 6,565, no heap (W4) |

`kernsize` is quoted in bytes at every wave, per CLAUDE.md's banner.

## 5. Same or better? The ledger against XDC

| | XDC | ours |
|---|---|---|
| Disk, XDC's content | 42.1–105.1 KB/s | **22.9–80.8, −21 to −46%** (measured) |
| BADAPPLE on a 20 MB ST-225 | 20.1 MB (does not fit), 93.8 KB/s | **12.3 MB, 57.7 KB/s**; ~47 with ADPCM4 |
| Decode CPU, mean | reference | **+2–7 points** (measured costs, applied to every frame) |
| Decode CPU, worst frame | reference | **1.01–1.28×** (measured); long-span frames 0.67–0.98× |
| Scene cuts | converge over several frames | drawn inside the per-frame ceiling (section 3.2) |
| Adapters | CGA (composite colour) | CGA (composite colour); Hercules and VGA with canvases made for them |
| Windowed, seek, poster | none | Preview, In-window, Live, keyframes |

**Why the extra CPU is affordable.** It is spent in the interrupt, which on a
DMA disk overlaps the transfer rather than competing with it.

**The failure to watch for** is a run of heavy frames while the disk is also
near its limit. Wave 0 plays BADAPPLE's heaviest ten seconds from the
hard-disk profile and counts pauses. The count must be zero.

## 6. The host tools — `tools/os88vid.py`

**The first user is the developer**, so version 1 is the tool that works best
for building and testing the player. The friendly tool comes after the player
works.

- **`encode`.** XDC's encoder, ported:
  1. find the changed spans;
  2. pull hidden runs out;
  3. subdivide oversize spans;
  4. shave (optional);
  5. combine close slices;
  6. commit largest first.

  Beyond XDC it adds:
  - our own cost model, taken from Wave 0;
  - a per-second disk pool;
  - section 3.2's average and per-frame CPU limits;
  - spans split at row ends;
  - any canvas, keyframes and a poster;
  - PCM8 or ADPCM4;
  - long slices as `rep movsw`.

  **Machine profiles** hold the disk rate, the CPU limits and the default
  canvas. The first two:
  - **`5150-st225`**, the default: the owner's machine, disk capped around
    64 KB/s for margin;
  - **`5150-picomem2`**: the owner's second machine, whose storage is
    effectively unlimited and much faster. It is the machine to test on
    before a stream meets the ST-225's limits, and whether its disk path
    costs the CPU is a Wave 0 question.

  Version 1 takes XDC's script format (pre-dithered BMP frames, a WAV,
  `sourcefps=` …) and PNG frames.
- **`import`.** XDV → `.V88`. It decodes XDC's frame programs exactly (the
  grammar is ~10 opcodes, and all five samples parse with none unknown).
- **`stat`, `decode --frame N --png`, `verify`**, and `--selfcheck` in the
  build.
- **Later: a friendly front end.** Any video through ffmpeg, with our own
  scaling and dithering to each preset, and composite colour matching.
- **Also later: an os8088 logo video**, the owner's end goal for a showpiece.

## 7. Not taken, and why

- **XDC's code-as-frames format.** Section 1.
- **Translating layouts at playback.** It was built and measured in Wave 0 at
  ~480 cycles per row change, and it forced row splits that multiplied the
  heaviest frames' entries. Layout is the host's job (section 2.3).
- **Per-row groups; hop entries.** Measured worse, section 1.
- **A JIT from our lists to XDC-style code.** It pays per change in the
  foreground, which does not overlap the disk wait.
- **Scaling at playback.** A canvas is encoded for its screen and played at
  1:1. The owner's rule: speed before filling pixels.
- **Retiming the Hercules 6845 into CGA's layout.** The owner's call: it
  needs real research before it goes near real hardware. The Hercules
  presets make it unnecessary.
- **Writing a live window's framebuffer directly.** It smears the pointer
  (§7.1) and breaks a straddled display (§39.14). Live blits a shadow
  instead.
- **CGA In-window at half height.** The owner found dropping rows "not really
  windowed". CGA's In-window offers only canvases that fit.
- **`kern_small`.** Not in this plan. It can be reconsidered when the shape is
  known.

## 8. Waves

Each gate follows docs/WRITING-TESTS.md: break it on purpose and watch it go
red. A row about one package goes in `soak`.

- **W0 — measure. No shipped byte.** A bench package in `tests/vidbench/`.
  - (a) **DONE** (`tests/vidbench.py`). The list decoder against XDC's own
    frame code, on picked, model-worst and one-construct synthetic frames,
    into CGA, Hercules and VGA memory, all verified against the host's
    picture. It reshaped the format (sections 2.2 and 2.3):
    - ten lists, not four;
    - absolute segments;
    - no row splits and host-side layout, with the translating decoder
      REFUSED at ~480 cycles a row change;
    - hidden runs.

    Two emulator facts belong beside the numbers. MartyPC charges Hercules
    memory exactly what it charges CGA's, where the field measured 40–49
    cycles a word (§88.3.6). And its XT VGA has no wait states at all.
  - (b) **DONE** (`tests/viddisk.py`). `READ_AT` grows **142 ms per MB of
    offset**: 32 KB costs 220 ms at 0 MB and 1,922 ms at 12 MB, so a
    57.7 KB/s stream dies ~2 MB in. The ROM's own `int 13h` reads a track at
    237 KB/s. That was measured on XT-IDE (CPU-copied); the owner's DMA ST11M
    is a field item. Section 4.2 is confirmed.
  - (c) **DONE** (`tests/vidsnd.py`). One interrupt per frame off an
    SB 2.0: **30.01/s** at 22,050/735 and **60.02/s** at 8,040/134. The line
    was found with DSP F2h. **ADPCM4 is unanswerable here**, because MartyPC's
    Sound Blaster has no ADPCM; it is a field item, and the bench carries the
    row for it.
  - (d) **DONE**: section 2.2's raw stores.
  - (e) **DONE for a CPU-copied disk**: an interrupt burning 25/50/75% of
    each frame leaves the reader 72/47/19% of its rate. The DMA curve is a
    field item.
  - **The profile exists now**: `os8088_5150_herc_hdd_sb[_gla]` has
    Hercules, the fixed disk and an SB 2.0. Its disk is XT-IDE, not a DMA
    controller, and its comment says so.
  - **The measurement is docs/reports/VIDEO-W0-2026-09-25.md.**
  - **Still for the field** (the owner's 5150):
    - the ST-225's streaming rate once `READ_SEQ` exists;
    - the DMA ceiling curve;
    - Hercules' real wait states (MartyPC charges it exactly CGA's);
    - ADPCM4 on a real SB 2.0.
- **W1 — host tools. DONE** (SPEC.md 98, `tools/os88vid.py`,
  `tests/vidfmt.py`). `import`, `encode`, `info`, `decode`, `verify` and
  `--selfcheck`. All five samples import and verify **frame by frame
  against XDC's screen and audio**, the whole row in 16 s. `import --target
  herc|lin80` came forward from W5, because it is the same machinery as the
  encoder: BADAPPLE re-laid for Hercules and for mode 12h verifies against
  XDC too.

  | stream | `.V88` | stream rate | keyframes, share of the file | CPU (model) mean / worst |
  |---|---|---|---|---|
  | BADAPPLE | 13.3 MB | 58.2 KB/s | 110, 1.6% | 21.5% / 67.7% |
  | THUNDERC | 6.0 MB | 73.6 | 39, 4.0% | 26.8% / 58.9% |
  | TRONDISC | 4.3 MB | 81.6 | 25, 5.9% | 30.3% / 62.2% |
  | BBBB_BW | 0.19 MB | 23.2 | 4, 8.5% | 9.4% / 57.0% |
  | BBBBCOMP | 0.25 MB | 28.6 | 4, 14.7% | 11.3% / 33.8% |
  | BADAPPLE on HERC | 13.5 MB | 59.0 | 110, 1.8% | 22.0% / 68.2% |
  | BADAPPLE on LIN80 | 13.1 MB | 57.6 | 110, 1.6% | 20.8% / 67.4% |

  The CPU columns are wave 0's CGA-screen model. Keyframes every 2 s cost
  1.6–15% of a file, so the owner's rule (a bonus does not get half the
  disk) holds with room to spare. The encoder is lossless and has no budget;
  that is W8.
- **W2 — kernel. DONE** (SPEC.md 53.2.2, 12.8.5.2, 18.4.8; `tests/vidkern.py`,
  a soak row, on `os8088_5150_herc_hdd_sb_gla`). All three green, and all
  three red when broken on purpose.
  - **`FSXF_RATE` at 30.0 Hz:** 150 periods against 91 ticks, 1.6484 against
    the exact 1.6478; the BIOS's 40:6C moved with `[ticks]`. A hook that
    `sti`s and runs two periods long every 16th call was skipped and handed
    up to 3 periods at once, with none lost.
  - **The fence:** a read before the bracket armed the widget (the
    control), the same-mode bracket's door took it down, and a read inside
    did not arm it.
  - **`READ_SEQ`, 32 KB a call on the XT-IDE disk:** **226.6 ms at 0 MB and
    219.7 at 12 MB**, against `READ_AT`'s 1,922 at 12 MB. At 12 MB its 28
    `int 13h` calls went nowhere near the FAT. A seek costs one walk, the
    same 1,922 ms, once. Every byte arrived at its offset across a seek, a
    write and a delete mid-run, and the end of the file.
  - **What the gate found:**
    - The cursor needs less than the plan gave it: no first cluster, only
      the size, because a stale cursor re-seeds from the name.
    - The nested-chain guard: a `FSXF_FASTTICK` sub-tick landing inside the
      ROM's own tick handler would have switched tasks on the chain's
      private stack (SPEC.md 53.2.2). That fault predates this wave.
  - **What it leaves for the field:**
    - `READ_SEQ` streams 32 KB in ~220 ms on this CPU-copied disk, ~145
      KB/s against the controller's 237. The rest is the chain reader's
      per-cluster work, the reserve row above.
    - What the ST-225's DMA controller makes of it is the field's to say.
- **W3 — player, fullscreen CGA, silent (`FSXF_RATE`). DONE** (SPEC.md 98.3,
  `apps/video/`, `tests/vidplay.py` as two soak rows).
  - **Frame-exact:** with the ring held to 2 slots the stream wraps it, and
    at every hold the adapter equals the host's decode byte for byte, on CGA
    and on Hercules (native HERC layout, centred). The holds include one
    after each frame whose video runs into the mirror slot, found on the
    host; with the mirror copy deleted they go red.
  - **On time:** 150 frames at 30 fps in 91 ticks (ideal 91.0), no stall,
    no late period.
  - **What it found:**
    - **A deadlock in the ring rule** (SPEC.md 98.3): a super-packet's
      chunks must be released when its last frame is drawn, not when the
      next one is entered.
    - **`READ_SEQ`'s first shape could not serve a ring.** The cursor had to
      share the buffer's segment, so the buffer moved to DX:BX; that cost
      the kernel +55 `.cold` and +20 `.bss`, now 483 of the owner's ~500.
    - **Content outside a CPU budget runs LATE, and must.** A synthetic
      frame of 16 KB of slices is ~67 ms of decode against a 33 ms period.
      The player counts it and never draws a wrong picture; the encoder
      that prevents it is W8.
  - **LIN80 (mode 12h) plays on time on the XT VGA** (`vidplayvga`), but
    its picture is not read back: mode 12h is planar, and a CPU read of A000
    is one plane. That check is W5's, with the shadow path and the CGACOMP
    burst.
  - **The player is on every apps disk** (`$(APPS_TOOLS)`, 4 clusters of
    the 360KB one) and on no kern_small disk (`SMALLOMIT`: `FSXF_RATE` and
    `READ_SEQ` are kern_big's).
  - **The field hard disks** (`make vidfieldhd XDCSAMPLES=<dir>`): bootable
    VHDs for the PicoMEM machine and 86Box, a Hercules and a CGA layout
    (five streams are ~24 MB in one layout) at three geometries - 615/4/26
    plain (MartyPC's XT-IDE), 615/4/17 for the IBM/Xebec MFM card (20 MB, so
    no THUNDERC), and the SEAGATE ST11 layout (`os88hdd.py --st11`) at
    615/4/26 for an ST11R and 615/4/17 for an ST11M, the owner's own card. **A disk is only readable at the geometry and
    layout it was written with**, and the owner's 86Box found that the hard
    way: the ST11M and WD1002A-WX1 are MFM (17 sectors) and saw nothing,
    the ST11R saw a drive with no record of its own. Read off a disk that
    ST11R formatted and os8088's installer then wrote: the card keeps a
    40-byte record (`DA BE`, the geometry, "SEAGATE30M") in sectors 1-2 of
    heads 0 and 1 of cylinder 0, hides that cylinder, and hands the BIOS
    two fewer - the installer partitioned 63,726 sectors from LBA 26. The
    generated image matches that disk's record, footer, partition entry,
    MBR and VBR byte for byte. An ST11M-formatted ST-225 then read the same:
    the same record at 17 sectors with the name "SEAGATEST225", the volume
    a cylinder in, 41,667 sectors from LBA 17 (613 cylinders again), and
    the ST11M image matches its record, partition entry, MBR and BPB. MartyPC mounts only the drive types on its
    own list, so the ST11R volume is proven by booting it cut out and
    padded back to 615 cylinders: BADAPPLE plays with no stall. Each
    carries the player, the streams and the four benches - each of which now SAVES its report as a
    `.TXT` beside itself (benchlib's `bl_save`). What the benches gained
    from W1-W3: VIDBENCH three kinds a frame instead of five and the worst
    frame in thousandths of a period at 30 and 23.976 fps (its report had
    been truncating); VIDDISK the `READ_SEQ` rows, the int 13h calls one
    makes, and the SILENT PLAYER'S CEILING - `READ_SEQ` streaming inside an
    `FSXF_RATE` bracket whose 30 Hz hook holds 0-75% of every period;
    VIDSND a 50% row with interrupts ON, as the player's hook runs; VIDKERN
    a run-all for a person, with the fence's parks timed. Verified in
    MartyPC off the images themselves: on the Hercules 5150 all five
    videos draw every frame with **no stall and no late period** -
    BADAPPLE's 6,570 frames in 3,988 ticks against 3,987.2 - and every
    bench's `.TXT` reads back off the disk whole.
  - **The ceiling, on this XT-IDE (CPU-copied):** 198 KB/s with the hook
    idle, 150 / 99 / 49 at 25 / 50 / 75%, so the disk share falls exactly
    as the decode takes the CPU. Interrupts on or off make no difference
    HERE because an XT-IDE raises none; on the owner's ST11M (DMA, IRQ 5)
    that row is the question. A `READ_SEQ` of 32 KB is 219.7 ms at the
    desktop and ~161 ms inside the bracket.
  - **A player with the benches open gets a 2-slot ring** and a 60 fps
    stream then stalls (44 of 437 frames), and a second instance is refused
    for memory. Every bench keeps its claims until its window closes; the
    field README says so.
- **W4 — sound. DONE** (SPEC.md 34.5.3, 98.1.1.1, 98.3.1;
  `tests/vidsound.py` as two soak rows).
  - **The shape changed, and section 4.4 is why.** 4.4 asked for a frame
    stream - a block per frame and a far callback per interrupt. By the time
    W4 was built, SOUND.DRV already played a package's ring IN PLACE
    (§34.5.2) and could say exactly how much it had played (verb 9), so
    what was missing was smaller: a ring the hook may WRITE, since it may
    call nothing. So:
    - **SOUND.DRV** takes an external ring in the package's own `MC_DMA`
      claim, whose block interrupt reads the package's total and writes the
      consumed count back, and an ADPCM4 start (7Dh). **194 bytes**, inside
      its 7KB claim: no heap at all, against the owner's 1 KB.
    - **The player** walks the records twice - the video cursor draws, an
      audio cursor ahead of it copies each frame's audio into the ring -
      and the hook's clock is the card: the frames wholly played at its last
      block interrupt, plus the periods since, capped at a block's worth. No
      callback into a package from a driver's interrupt, and the kernel's
      hook protections (§53.2.2) stay in force.
  - **The gate**, 60 s of 22 kHz PCM8 off a fixed disk: every frame, no
    stall, **no pause**, the picture never more than 2 frames behind the
    sound, the play as long as the sound at the card's real rate, and **the
    card's captured output byte for byte the clip's sound**.
  - **What it found:**
    - **The timer at the frame rate was too coarse.** The card reports every
      93 ms, and a heavy frame plus a report's lag put the picture 3 frames
      behind the sound four times in 60 s. At twice the frame rate, none.
    - **A clock that stops at the last frame has no end.** The silent play
      ended when the stream's chain did; with sound the picture never asks
      for a frame past the last, so the end is the header's frame count.
    - **MartyPC's card had no ADPCM** (wave 0 read zero interrupts), so it
      was added (`tools/martypc/patches/06`), with DOSBox's tables - the ones
      `os88vid` encodes against. That makes the path testable here and the
      TABLES the field's: 86Box's card and a real one.
  - **ADPCM4 wants an even chunk.** BADAPPLE's 735 is odd, so its ADPCM
    version waits for wave 8's encoder; THUNDERC's, TRONDISC's and BBBB's
    convert.
  - **The owner's verdict on ADPCM4** (86Box, the field disks' `TRONDA4`
    and `BBBBA4`): no noise and no buzz, so the tables agree with a card
    that is not ours - and **noticeably worse sound** than PCM8. So it stays
    an ENCODER OPTION for videos that are on the line, and W8's profiles
    pick it only when the disk budget needs it. On MartyPC's CPU-copied disk
    TRONDISC paused once in PCM8 and not at all in ADPCM4, which is the case
    it is for.
- **W5 — surfaces. DONE** (SPEC.md 98.3.2, 98.3.3). The native Hercules
  and VGA plays and `import --target` had come forward into W1 and W3; the
  presets are W8's encoder profiles. What W5 added:
  - **The shadow path**: a file whose mode the display lacks decodes into a
    RAM image of its own layout and the dirty band is copied, re-addressed a
    row at a time, to the first screen here that holds it. A CGA file plays
    on a Hercules frame-exact in 95 ticks against 91. **What it found**: a
    shadow play must not FORGIVE frames the way a native one does - that
    made it 20% slow, because the copy is once a call and the decode is
    cheap - so the frames past a call's cap stay owed, the cap is 8, and
    while the play is behind the copy waits (at most 8 calls).
  - **The CGA composite burst**: a CGACOMP file on a real CGA clears 3D8h's
    black-and-white bit; not through an EGA's or VGA's mode 6.
  - **Mode 12h read back**: a MONO1 byte goes to all four planes, so the
    plane a debug read returns is the picture, and `vidplayvga` is now
    frame-exact at every hold instead of timing-only.
- **W6 — Preview. DONE** (SPEC.md 98.4, 98.3.4, 98.3.5). The association
  and the Open dialog came forward into W3. What W6 added:
  - **The window is the Preview**: the poster keyframe halved 2x2 with an
    ordered dither into a box, a scrub bar over the keyframes, an info
    panel (canvas, screen, fps, length, KB/s, sound, where Play starts,
    what the last play cost), and Tracker's transport pictures as four
    buttons - Open, previous key, Play, next key. It fits CGA's desktop
    band. A key step is 1.2-1.5 s on the 5150 off a floppy.
  - **SEEK came forward from W7**: Play starts at the picked keyframe -
    decoded onto the screen (or the shadow) before the ring is filled over
    it, the stream from its super-packet with *idx* records stepped over,
    the frame count and the card's clock based at *k*+1. Frame-exact at
    every hold, natively and through the shadow, with sound too.
  - **Space pauses**, with sound: SOUND.DRV's **verb 10** halts the card
    mid-block (+65 bytes, 259 of the 1 KB now spent), verb 1 resumes it,
    and the hook counts no period while paused. Not a frame drawn and not a
    byte consumed in a 2 s pause, and the play still on time without it.
  - **What it found**:
    - **ADPCM4 could not seek.** The card restarts its decoder at 80h and
      scale 0, and Creative's ADPCM never decays an error, so a seek played
      the rest of the file ~40 of 128 off centre - and a true sample alone
      left 24, the scale being wrong too. The encoder now steers the scale
      to 0 at every keyframe's frame k+1 (three samples, 0.14 ms every 2 s)
      and the keyframe record carries the sample there: a seek is exact,
      sample for sample. **This changes the file**: the field disks'
      `TRONDA4`/`BBBBA4`, made before it, still play and still seek, from
      80h, and fail `verify` until re-made.
    - **The W5 shadow was claimed at the image's size**, 16-38 KB, which a
      hostile list could write past (SPEC.md 98.1.6). It is 64 KB now, and
      claimed before the ring.
    - **A play based at a keyframe needs its clock SEEDED there**: the
      frames due are counted from the card's played bytes plus the base, and
      until the first block interrupt the count was 0 - three frames held,
      then due at once.
    - **A 638-wide window cannot be snapped** on a 640-wide screen, so its
      content sat at x = 2 and `OSAPI_GFX_BLIT1` refused the poster. 628
      wide at frame x 7 is on the byte, and the poster rounds to the
      screen's byte anyway.
  - **Play does not yet become Pause**: that is a play in the window, W7.
  - **The owner's interface round** (after testing W6 on the field disk):
    **F and Alt+Enter** go full screen PAUSED and back (SPEC.md 98.3.6), the
    card opened at the first Space so its sound starts on the frame shown;
    Alt+Enter's poll is the foreground's, so it costs no frames. **A play
    left part way leaves Play at the keyframe at or before where it got
    to**, and one played out rewinds to the start. **The layout is
    dynamic** (98.4.1): the picture at the video's own size where the
    screen has room (Hercules, for a 640 x 200 video), the buttons centred
    under the bar with an `i` for the info card - and on CGA over the dock,
    which took **16 bytes of kernel** (`OSAPI_WM_RESIZE` now honours
    `WF_KEEPH`, SPEC.md 11.93.1). **The thumb drags** (98.4.2), loading on
    the release on an 8088 and every 9 ticks mid-drag on a 286.
- **W7 — In-window. DONE** (SPEC.md 98.3.7). The play is a SESSION that
  brackets come and go on - ring, cursors, the card, and a keeper copy of
  the canvas - so it can pause back to the desktop with its frame in the box
  and resume, and swap between the window and the full screen playing or
  paused. In the window it is a same-mode bracket and the decoder writes the
  desktop's own framebuffer, in place when the file's layout is the
  desktop's (every adapter's desktop is one of the three layouts) and
  through the shadow otherwise: 92 ticks of 91.0 on the Hercules 5150. Play
  shows Pause while it plays there; with no pointer, a click anywhere
  pauses. Offered only where the picture is at its own size - on CGA a
  640 x 200 video is shown at half, so it plays full screen, as the plan's
  3.3 said. **Not taken, and now declined**: the exact seek on a paused
  picture. It would replay every frame from the keyframe - up to 2 s of
  stream, ~115 KB off the ST-225 and ~60 decodes, 2-3 s a step on the
  5150 - and the owner, asked, finds keyframe accuracy enough.
- **W8 — the encoder. W8a IS BUILT** (SPEC.md 98.2.1, `tools/os88venc.py`):
  any video ffmpeg reads, to a canvas of the source's displayed shape in a
  preset's box (the layout's pixels are not square), grey levels stretched
  to the range the clip uses, an ORDERED dither anchored to the canvas with
  a dead band so a still picture costs nothing, and then the budgets of
  3.2 - a disk bucket and a CPU bucket a second deep, a per-frame ceiling,
  the cycles MEASURED on each record and the frame retried when the model
  under-priced it - with a cut frame committing its spans best-first by
  pixels fixed per unit of the scarcer budget, aged so an old error
  outranks a new one. The owner's first three clips, on the ST-225 profile
  (PCM8 11 kHz):

  | clip | canvas | KB/s | frames exact | CPU mean / worst |
  |---|---|---|---|---|
  | Bad Apple (4:3), Hercules | 400 x 193 | 44.4 | 6,368 of 6,563 | 21.4% / 84.7% |
  | Bad Apple, CGA | 640 x 200 | 51.1 | 5,766 of 6,563 | 25.5% / 85.0% |
  | Bad Carrot (16:9), Hercules | 400 x 145 | 38.6 | 6,767 of 6,770 | 18.2% / 84.7% |
  | Bad Carrot, CGA | 640 x 150 | 45.8 | 6,532 of 6,770 | 22.4% / 84.6% |
  | Trackmania 3-15 s, Hercules | 400 x 145 | 56.5 | 359 of 360 | 27.6% / 83.0% |
  | Trackmania 3-15 s, CGA | 640 x 150 | 61.7 | 144 of 360 | 31.0% / 83.7% |

  **The budget is not what spoils a picture; one bit is.** Trackmania's
  budgeted CGA frame against the same frame with no limits differs by a
  handful of pixels: both are a mid-grey road dithered to a mid-grey
  stipple. Hercules' 400 x 145 of near-square pixels reads far better than
  CGA's 640 x 150 of tall ones. **The dither is the clip's choice**: a
  plain threshold is 6% smaller than Bayer on Bad Apple, which is black
  and white already, and blue noise 8% larger. **The owner's first look**
  (5150 and 86Box): *"very similar in quality to the originals, or even
  better"*, Trackmania with *"very little ghosting"*. It found an even grid
  of single dots over every flat black and white - the threshold map's
  extreme cells at grey 2 and 253, lit by the MP4's noise - so the ends of
  the map are solid now (`--clip`, 3,222 isolated pixels a frame to 46),
  and posters can be chosen (`--poster-at`, the keyframe nearest a moment;
  Bad Apple's and Bad Carrot's are key 4, the apple and the carrot held
  out). **W8b and W8c are BUILT.** ADPCM4 is searched rather than chosen
  a nibble at a time (SPEC.md 98.2.1): a Viterbi pass over the decoder's
  1,024 states, **~7 dB better** than the greedy encoder (27.3 against
  19.9), stitched across cores byte-identically. Composite colour comes
  from a video (98.2.2) through reenigne's model - the one MartyPC and
  86Box use - ported to `tools/os88cgacomp.py`, with Knoll's pattern
  dither over the 16 nibbles; it is expensive (115 KB/s of picture for
  640 x 150 with no limits) and plays on time under the ST-225 budget by
  cutting. **What is left of W8 is the field's**: the profiles' figures
  (`floppy`, `picomem2` and `286` are arithmetic) and how composite
  and the searched ADPCM4 look and sound on a real monitor and card.
- **W9 — Live windowed.** The encoder's `live-*` presets (240 x 116 on
  Hercules, 320 x 100 on CGA, 160 x 120 on VGA) are its canvases, so a clip
  can be made for it before it plays.
- **W10 — ONE FILE FOR EVERY SCREEN, IN MEMORY.** The owner's end goal: an
  os8088 logo video, small, that plays Live on any adapter, carrying every
  format it needs in one file, loaded whole before it plays, each format
  compressed on its own. What it needs, and what it does NOT:
  - **The header already has the room.** 98.1.1 reserved four rendition
    slots of 64 bytes, 32 of each unused, for exactly this (13, answer A).
    Version 2 adds header flag bit 0, RESIDENT, and uses the spare bytes:
    a slot gains its BLOCK - offset, packed and unpacked bytes, and the
    packing (none, LZ4, LZB) - and the header's 16 bytes at 176 gain the
    AUDIO block. A version 1 reader refuses the flag, as it does any.
  - **A block is the rendition's records back to back** - no super-packets,
    no padding, no chain: those exist to be read a sector at a time, and a
    resident file is read once. Each record keeps its length word, so the
    decoder is unchanged.
  - **The sound is ONE block for every rendition**, not a part of every
    record: carried per record it would be stored once per format. The
    hook takes frame *f*'s audio at *f* x abytes into it.
  - **Loading copies nothing it does not have to.** The player claims the
    rendition's UNPACKED size, reads the packed block into the TOP of that
    claim, and `OSAPI_DECOMP` expands it in place: SPEC.md 20.13.7's raw
    tail is what makes a buffer of exactly the output enough, so there is
    no scratch buffer and no second copy. The decoder then reads records
    where they lie - no ring, no READ_SEQ. The one copy left is Live's
    shadow-to-screen blit, which 3.4 requires (a live desktop may not be
    written under its pointer). An unpacked block is read straight in.
  - **Each block packs with LZB where that is worth it, LZ4 otherwise.**
    MEASURED on 10 s of Bad Apple and of Trackmania at the three Live
    sizes: LZ4 keeps **83-94%** of a record stream and LZB **74-87%** -
    ten points better, at a decode that costs once, at load. **So
    compression is not what makes it small**: a dithered picture's changes
    are close to incompressible, and 10 s of Bad Apple at 160 x 120 is
    ~100 KB even packed. A logo is SMALL BY BEING MADE SMALL - flat
    shapes, few changes a frame, a low frame rate, a few seconds - and the
    encoder's job is to say how big it came out, per rendition, and to
    refuse past a stated size. `--resident --max-kb N` makes the disk
    bucket a SIZE bucket (N over the length) and keeps the CPU's, at Live's
    share of the machine rather than a fullscreen play's.
  - **A loop is a record.** With header flag bit 1, LOOP, a block carries
    one record more than it has frames: the change from the last frame
    back to the first. Looping then costs a frame like any other, where
    re-decoding the first keyframe would be a whole canvas every lap.
  - **The player picks the rendition that is native to the desktop** (no
    shadow copy), else the first that fits through the shadow, else it
    refuses with the arithmetic - the same rule as 13, answer A.
  - **The gate** encodes a fixture logo in three renditions, loads each on
    its own adapter under MartyPC, asserts the claim is exactly the
    unpacked size and nothing else was claimed, and compares every frame
    of a lap and the loop's seam with the host's decode.
- **Field.** The owner's 5150 with the ST-225: BADAPPLE with sound, zero
  pauses, fullscreen and In-window. Then the PicoMEM 2 machine for the
  streams the ST-225 cannot carry.

## 9. Credit

The architecture is XDC's, and the About card says so: Jim Leonard
(Trixter / Hornet), XDC, 2014, MIT, with the Sound Blaster shell credited to
Stefan Goehler as XDC's own card does. The format and every line of code are
new.

## 10. Where the numbers came from

Throw-away scripts decoded the five samples frame by frame against XDC's
grammar and priced each candidate format. Wave 1's `os88vid.py stat` is
those scripts made permanent, and it regenerates section 2.4's table.

## 11. Relation to other plans

- DISK-CPU-PLAN 3.1 prices the chain re-walk that section 4.2 removes.
- GFX-FSX-PLAN 4.2.1 is section 4.3's gap.
- UI-FREEZE-PLAN 1 is why Live splits decode from display.

## 12. The owner's answers to revision 2's questions (2026-09-25)

| # | question | answer, and where it went |
|---|---|---|
| 1 | Names | **Video Player**, `VIDEO.O88`, `.V88` |
| 2 | Canvases | 640×200 is the start; Hercules and VGA should look less awkward, and speed matters more than filling the screen; ideally arbitrary resolutions, at least for mono → **section 2.1's generic canvas and section 2.3's presets** |
| 3 | Colour | XDC-style composite colour on CGA via a CGA-only format; mono first; VGA/RGB colour 286+ if possible → **CGACOMP in v1; CGA4 and VGA8 named for later** |
| 4 | Hercules | Prefer a smaller, less squashed canvas; do not retime the 6845 without research → **400×200 preset; retime not taken** |
| 5 | Audio | Whatever hits the speed goals; possibly both, typed in the header → **PCM8 and ADPCM4** |
| 6 | No card | Silent is fine; speaker audio maybe some day |
| 7 | SOUND.DRV | Fine if it stays within 1 KB of heap growth and is as fast → **section 4.4: 797 bytes of slack** |
| 8 | Streaming read | Yes, and it is overdue → **section 4.2, a general slot** |
| 9 | `kern_small` | Not in this plan |
| 10 | Windowed | CGA half-rows is not really windowed; restrict CGA to canvases that fit; Live, even small and in memory, is the tour de force → **sections 3.3 and 3.4** |
| 11 | Keyframes | 2 s; reduce if they eat the disk; the poster is a keyframe named in the header, chosen at encode, default first mostly-not-empty |
| 12 | Encoder | Easy Python with ffmpeg and our own scaling and dithering eventually; the first tool is whatever works for the developer |
| 13 | Interrupts off | Fine, as long as a video can always be stopped without a reboot → **Esc, section 3.1** |
| 14 | CPU cap | The developer's call → **section 3.2: a profile's per-second average plus a per-frame burst ceiling** |
| 15 | Samples | May be used as test content; an os8088 logo video is a later goal |
| 16 | Target | The 5150 with the ST-225; also a 5150 with a PicoMEM 2 for fast storage, and the emulators |

## 13. The owner's answers to revision 3's questions (2026-09-25)

| # | question | answer |
|---|---|---|
| A | A file on a screen it was not made for | **Play it at 1:1, centred, when it fits; refuse it when it is larger than the screen.** The header must stay able to carry **several canvases in one file**. That comes after the basics work, so version 1 reserves a rendition count (always 1) and a per-rendition table slot rather than building the feature |
| B | Live without a card | **RAM-resident clips only.** A live desktop cannot be fed from the disk without the card's interrupt, and the kernel bytes it would take to try are not worth it |
| C | Live's region pin | The developer's call. **The player pins its own region for the length of a Live stream and unpins it at close**, and the frame stream carries no pin. This keeps SOUND.DRV ignorant of packages' regions, the same shape §66.5.7.1 uses for a file read into a movable claim. W9's SPEC section fixes the mechanism |
| D | The first colour format after mono | **CGA4 first, if it can be made to work; VGA8 after.** |

**Wave 0 is started** (section 8). The owner supplied the IBM 5150 27-Oct-82
ROM for the emulator, so W0 runs on the genuine ROM as well as the GLaBIOS
twins. **The ROM image is the owner's and is never committed.**
