# VIDEO-PLAN — full-motion video on a 4.77 MHz 8088

**Status: PLAN, nothing built.** This is revision 2, 2026-09-25. It
replaces revision 1 (XDC-VIDEO-PLAN.md, commit `672a72a`), which planned a
port of XDC's own file format.

**The owner's decisions, 2026-09-25:**
- We do **not** need to be compatible with XDC. The goal is a video player
  that plays as well as XDC does.
- Running code read off a disk is acceptable in principle. The hostile-input
  rule is about packages, not this.
- Up to **~500 bytes** of kernel change may be spent, and less is better.

**Section 12 is the list of open questions for the owner.**

How to read the numbers:
- *Measured* means decoded exactly from the five XDC streams the owner
  supplied (BADAPPLE, THUNDERC, TRONDISC, BBBB_BW, BBBBCOMP), or taken from
  a PERFORMANCE.md set.
- *Model* means arithmetic. The model uses XDC's own cycle constants (from
  `XDC_CODE.PAS`, with CGA wait states and DRAM refresh folded in) plus an
  estimate of our decoder's instructions.
- Wave 0 replaces every *model* figure with a MartyPC reading before any
  shipped byte is written.

## 0. Summary

We build **our own video format and player**, taking from XDC (MobyGamer,
MIT, © 2014 Jim Leonard) the three ideas that made it work:
1. **Frames are decoded inside the audio (or timer) interrupt.** That work
   fills the time the CPU would otherwise spend spinning in the BIOS while
   disk DMA runs, so decoding is nearly free while the disk streams.
2. **The audio clock is the frame clock.** One interrupt per frame gives
   sample-accurate sync with no drift logic.
3. **A budgeted delta encoder.** Frame N+1 is the byte spans that differ from
   frame N. Spans are committed largest first until a per-frame CPU budget and
   a per-second disk budget are spent, and whatever is left over converges
   over the next frames.

We do **not** take XDC's file format, in which each frame is a machine-code
program. Section 1 has the measurement behind that. In short:
- 48–65% of XDC's code bytes are `mov di,<address>`, which is addressing,
  not drawing.
- Our format ships only the operands. The player holds the instruction
  sequences once, as straight-line unrolled loops.
- On the five samples that is **19–43% less disk than XDC** (measured). The
  cost is **+2 to +4 points of CPU on the mean frame and +3 to +6 on the
  worst** (model).
- On the owner's machine the disk is what binds. BADAPPLE needs **93.8 KB/s**
  in XDC's form against the ST-225's measured **74.5 KB/s** (PERFORMANCE.md
  Set 24). In ours it needs **60.6 KB/s**, and the file is **13.0 MB instead
  of 20.1**, so it now fits the 20 MB drive.

What os8088 has to grow:
- **In the kernel, ~240–350 bytes against the 500 allowed:**
  - a caller-rated timer interrupt inside a fullscreen bracket, for machines
    with no Sound Blaster;
  - a streaming file read that does not re-walk the file on every call;
  - a one-line fence that stops the disk progress box drawing over the video.
- **In SOUND.DRV:** a "one interrupt per frame" stream that calls into the
  player.

What the user gets:
- **Fullscreen playback** on CGA, VGA and Hercules.
- **In-window playback**, where the desktop is left on screen, frozen, and
  the video plays inside the window's rect.
- **A true windowed Preview**, with a poster frame and a keyframe scrub bar.
- **Live windowed playback** for clips small enough to load entirely into
  memory.

## 1. Why not XDC's format

XDC's frame is a program: `mov di,imm16` followed by unrolled `movsw`/`movsb`,
`rep movsb` or `rep stosb`, between a fixed header and `pop ds / retf`. The
player far-calls it. Measured across the five samples:

| | BADAPPLE | THUNDERC | BBBB_BW |
|---|---|---|---|
| XDC code bytes per frame | 1,386 | 893 | 218 |
| …of which `mov di,imm16` | 898 (**65%**) | 426 (**48%**) | 135 (**62%**) |

So most of the "code" is addresses. The writing instructions come from a
vocabulary of about six. Shipping them in every frame costs disk, and on this
machine disk is the scarce thing. XDC's encoder caps every frame at 50% of the
CPU, and the samples' worst frames all sit on that cap, so there is CPU to
spare and no disk to spare.

Per change, the two forms compare like this:

| | bytes on disk | cycles (model) |
|---|---|---|
| **XDC** 1-byte change: `mov di,addr / movsb` (4 code bytes + 1 data) | 5 | ~35 |
| **Ours** 1-byte change: 1 skip byte + 1 data byte, run through the player's resident `lodsb / add di,ax / movsb` | **2** | ~40 |

Our loop's instruction bytes are fetched per iteration just as XDC's are: the
8088 has no cache, only a 4-byte queue. So the difference per change is one
extra bus byte plus a register add, not a dispatch.

Two other shapes were measured and **rejected**:
- **Per-row groups.** A row header per touched row buys nothing. BADAPPLE
  averages ~2 changes per touched row, so the header is as expensive as the
  changes it groups.
- **"Hop" entries** that bridge long gaps by rewriting unchanged bytes. The
  lists are sparse over a 16 KB screen, so they needed hundreds of hops a
  frame. That made the stream bigger than XDC's (THUNDERC 105.4 KB/s).
  Segments (section 2.2) replace them.

## 2. The format

### 2.1 Canvas

The header describes the canvas geometry: bytes per row, rows, the number of
memory banks and the bank step. So a later mode is new encoder and player code
and no change to the format.

**Version 1 has one canvas.** It is 640×200, 1 bit per pixel, in **CGA
memory order**: even rows at 0000h and odd rows at 2000h, 80 bytes a row. A
mode byte tells the player how to show it:
- **mono:** 1 = white;
- **composite:** each 4-bit group is one of 16 CGA composite artifact
  colours, i.e. 160×200×16 on a composite monitor.

This is XDC's own canvas, so everything the encoder learns from XDC carries
over, and XDC streams can be imported (section 7).

### 2.2 A frame's video part: four lists of segments

```
frame video  = list(POKE1) list(POKE2) list(SLICE) list(RUN)
list         = segment* 00
segment      = count(1..255) address(16)  entry × count
POKE1 entry  = skip  byte
POKE2 entry  = skip  word
SLICE entry  = skip  len(3..80)  len × byte
RUN   entry  = skip  len(3..80)  value
```

- **`skip`** is the number of bytes from the end of the previous write in the
  same segment to the start of this one. For the first entry it is measured
  from the segment's address. It is always one byte.
- **A gap over 255 bytes starts a new segment.** That costs 3 bytes and one
  segment set-up (~70 cycles, model), and the hot loop never tests for an
  escape.
- **Entries never cross a row end.** The encoder splits them there. This is
  what lets one file drive a surface with a different memory layout
  (section 2.3).
- **The lists are disjoint** and each is sorted by address. Order between
  lists does not matter, because no byte is written twice in a frame.
- **Reserved list ids** keep room for later operations without a format
  change, first of all **COPY**: a block copied from elsewhere on the screen,
  for pans, which delta coding pays for as all-new pixels.

The decoder is one straight-line loop per list, entered Duff-style on the
segment's count. AH = 0 is an invariant, so `add di,ax` needs no
zero-extend. A sketch (Wave 0 writes the real one):

```
; POKE1 inner loop: DS:SI = entries, ES:DI = surface, AH = 0
.e: lodsb           ; skip
    add  di,ax
    movsb           ; the pixel byte
    ...             ; x16, then loop back on the remaining count
; SLICE: skip, len; then shr cx,1 / rep movsw / adc cx,cx / rep movsb
; RUN:   skip, len, value;               rep stosb
```

**Long slices use `rep movsw`.** XDC used `rep movsb`, because its cost model
prices a byte move as half a word move. On a real 8088, `rep movsw` is about
12.5–13.3 cycles a byte against `rep movsb`'s 17 (PERFORMANCE.md Set 117.2).
The model below does not credit that gain; Wave 0 measures it into CGA and
Hercules memory, where wait states may flatten it.

### 2.3 Surfaces

The same file drives every surface. Only the decoder variant and its base
change.

| surface | memory | decoder |
|---|---|---|
| CGA fullscreen (`FSXM_CGA640`) | B800, CGA order | **native**: ES = B800 and the entries apply as they stand |
| VGA / EGA fullscreen (`FSXM_CGA640`, the BIOS's CGA-compatible mode 6) | B800, CGA order, shown double-scanned to 400 lines | **native** |
| Hercules fullscreen (`FSXM_HERC`) | B000, 4 banks, 90 bytes a row | **translating**, letterboxed at (40,74) |
| In-window, any desktop (section 3.3) | the desktop's own layout at the window's content origin | **translating** |
| RAM shadow, for Preview and Live | 16 KB, CGA order | **native**, ES = shadow segment |

**The translating decoder** keeps the source address beside DI. On each entry
it compares against the current row's end (about +6–10 cycles per entry,
model). Only when a row changes does it walk a 200-entry row table (~30
cycles). Because entries never cross a row, the address arithmetic inside a
row is identical in every layout.

**Composite** content:
- On a CGA it switches the colour burst on (port 3D8h ← 1Ah), so a composite
  monitor shows colour and an RGB monitor shows the stripes, exactly as XDC
  did.
- On VGA it shows as the mono pattern on an 8088. On a 286 or better it can
  be shown in colour through `FSXM_VGA13` and a byte → four-pixel table built
  from the composite palette XDC ships in `palette/`, gated on
  `OSAPI_CPU_INFO`. That costs ~85 cycles per changed byte (model), which is
  too much for an 8088.

### 2.4 The format against XDC, on the samples

Four lists as above, entries split at row ends, gaps over 255 bytes starting a
new segment, and the frames exactly as XDC's encoder chose them. Our own
encoder will re-budget each frame against *our* costs, so its frames will sit
under the cap the way XDC's do.

| stream | XDC disk | ours | XDC file → ours | CPU mean, XDC → ours | CPU worst frame, XDC → ours |
|---|---|---|---|---|---|
| BADAPPLE (640×200 mono, 30 fps, 22 kHz) | 93.8 KB/s | **60.6 KB/s (−35%)** | 20.1 → **13.0 MB** | 14.5% → 18.3% | 49.9% → 56.1% |
| THUNDERC (composite, 23.976 fps) | 92.8 | **75.5 (−19%)** | 6.9 → 5.6 | 22.1% → 24.9% | 49.6% → 53.4% |
| TRONDISC (composite, 23.976 fps) | 105.1 | **82.6 (−21%)** | 5.0 → 3.9 | 24.5% → 27.9% | 50.0% → 53.5% |
| BBBB_BW (mono, 60 fps, 8 kHz) | 41.9 | **24.0 (−43%)** | 0.3 → 0.2 | 5.5% → 7.7% | 49.8% → 52.9% |
| BBBBCOMP (composite, 60 fps) | 46.3 | **29.0 (−37%)** | 0.3 → 0.2 | 7.4% → 9.6% | 23.7% → 27.4% |

- The disk columns include the audio, which is identical in both. XDC's
  column also includes its 512-byte padding per frame (165–227 bytes a frame,
  measured), where ours pads once per 32 KB super-packet.
- CPU is a percentage of the frame period. It includes the audio copy for
  neither form (section 3.1 covers that).
- **In BADAPPLE, audio is now 36% of the stream.** That makes audio the
  largest remaining lever (open question 5).

### 2.5 The container

The container is written by the host tools only. The player still checks
every field it depends on (sizes, counts, offsets), because a truncated copy
is ordinary.

- **Header** (one sector):
  - signature, version, canvas geometry, show-mode (mono/composite);
  - rate: `samplerate / achunk` = fps, as in XDC;
  - audio format: PCM8 now, one code reserved for ADPCM;
  - frame count, largest super-packet, poster frame;
  - table offsets.
- **Super-packets** of whole frames, at most 32 KB, padded to 512 bytes once
  each. A frame is `[len16][video lists][audio chunk]`. 32 KB is XDC's own
  read size and fits every cluster size up to 32 KB.
- **Super-packet index:** sectors, first frame and frame count for each. The
  ring buffer wraps only on a super-packet boundary.
- **Keyframe table** (section 2.6), plus a free-text title and credits field
  for the Preview's info panel.

### 2.6 Keyframes

- **What a keyframe is.** The encoder simulates the stream exactly and stores
  the decoded screen *after* frame *k*. It is not a source frame: a
  budget-starved frame finishes over the next few, so only the decoded state
  lets playback resume at *k+1* with no error.
- **How it is stored.** It is an ordinary frame, the four lists against a
  black screen, so the player needs no second decoder.
- **Where it lives.** Keyframes sit in their own region of the file and are
  read only by Preview and by seeks. They cost disk space and **no playback
  bandwidth**.
- **Interval.** The default is 2 seconds, and the encoder prints the space
  they took (open question 11).
- **Poster frame.** It is named in the header. The default is the first
  keyframe that is not ≥ 98% one value, since many videos open on black; frame
  0 is the fallback.
- **Seeking.** A seek snaps to the keyframe at or before the target. It
  decodes the keyframe straight to the surface, re-seeds the read at that
  super-packet and restarts the audio there. An exact seek (keyframe plus
  replay) is offered only on a paused picture: at BADAPPLE's rate, 2 s of
  replay is ~120 KB of reading.

## 3. The player

### 3.1 The engine

**The interrupt hook**, XDC's shape:
1. Copy this frame's audio chunk into the half of the double buffer the card
   just finished, with `rep movsw`. XDC used `rep movsb`: 7.9% → 5.8% of a
   30 fps frame at 22 kHz (model, Set 117.2's rate).
2. Decode the frame's four lists onto the surface.
3. Advance.

If the ring is empty, it plays silence and counts a *pause*, as XDC does.

**The foreground** does nothing but fill the ring:
- It uses `OSAPI_FILE_READ_SEQ` (section 4.2), a whole super-packet at a
  time, into a ring claimed at start-up.
- The ring is up to ~256 KB of the 426 KB arena a 640 KB machine has with the
  hard disk ticked (§50.3). That is ~4 s of BADAPPLE.
- It also polls the keyboard (`int 16h`, legal in a bracket, §53.7).

**Where the interrupt comes from:**
- **With a Sound Blaster:** SOUND.DRV's frame stream (section 4.4). One IRQ
  per `achunk` bytes played.
- **Without one:** `FSXF_RATE` (section 4.1). IRQ0 at the frame rate, with
  the BIOS clock kept exact. There is no audio. §34.1 refused
  interrupt-driven PC-speaker audio at 36–50% of the machine, and the video
  needs that time.

**The hook runs with interrupts off.** Letting IRQ0 nest into `sch_isr` could
switch tasks on the interrupted stack. The worst frame is ~56% of a 30 fps
period, ~19 ms (model), so a second keystroke inside one frame, or a
1200-baud serial-mouse byte, can be lost. Open question 13.

**Small clips play from RAM.** A file that fits in the ring is read whole
before play (XDC does the same). A floppy (21 KB/s, Set 24) cannot stream
BBBB's 24 KB/s, but BBBB is 0.2 MB.

**At the end**, a statistics card shows pauses, CPU idle and time spent on
the disk, as XDC's does, so a field run is a photograph.

### 3.2 Fullscreen

- It uses `OSAPI_FSX_RUN` with `OSAPI_FSX_MODE` (§53.4): `FSXM_CGA640` on CGA
  and VGA, `FSXM_HERC` on Hercules.
- Past the mode set, the 6845 and 3D8h are the app's (§53.7), which is what
  the composite burst needs.
- **Hercules** is letterboxed at 1:1 by default. An optional 1.5× vertical
  stretch writes every odd row twice through a second row base, filling 300
  of 348 lines at +50% writes on those rows (open question 4).
- **Keys:** Space pauses, ← and → step a keyframe, Esc stops (§53.7's
  escape hatch).

### 3.3 The windowed tiers

| tier | what the user sees | how | on the 5150 |
|---|---|---|---|
| **Preview** | The poster frame in the window. A scrub bar over the keyframes. An info panel: fps, length, KB/s, and whether *this* machine's disk keeps up | Decode one keyframe into the 16 KB shadow, then `OSAPI_GFX_BLIT1` (§5.4.2) | always |
| **In-window** | Full-rate video with sound inside the window's rect. The rest of the desktop stays on screen, frozen, with no pointer | A **same-mode** bracket (§53.7: no `fsx_mode`, nothing cleared) and the translating decoder aimed at the content rect. On exit the rect is read back into the shadow, so the window repaints without the stream | same rate as fullscreen |
| **Live** | Video in a movable window while other programs run | A worker decodes into the shadow and blits the dirty band at ≤ 18.2 Hz, clocked by verb 9 of an ordinary SOUND.DRV ring (§34.5.1) or by `[ticks]` | **only for clips that fit in RAM**. Otherwise refused, with the reason (open question 10) |

**In-window per desktop:**
- **Hercules (720×348):** the full 640×200 at 1:1. This is the owner's
  machine.
- **CGA:** a window has ~132 content rows, so it shows the **even rows only**
  (640×100), cropped to the content width. The odd rows are one list segment
  range, skipped by address, so the lost half costs nothing to skip.
- **VGA (mode 12h):** all 200 rows at 624 columns. Map Mask stays 0Fh, the
  resting state `OSAPI_GFX_BLIT1` already keeps.

**Why Live cannot stream from disk.** A disk read holds `[sch_lock]`, which
freezes every worker (UI-FREEZE-PLAN 1), and nothing may draw from an
interrupt while the desktop is live. So a disk-fed Live window would freeze
for every read. In-window avoids both limits because the bracket owns the
screen.

## 4. What os8088 grows

### 4.1 `FSXF_RATE` — a caller-rated IRQ0 inside a bracket *(kernel)*

- It is a third `OSAPI_FSX_RUN` flag. DX is a PIT divisor, and a far hook
  goes with it.
- `sch_isr` adds the divisor to a 16-bit accumulator. It chains the BIOS tick
  and `[ticks]` only on **carry**, so the 18.2 Hz clock stays exact at any
  rate. That is XDC's `noSoundIntCaller`. `sch_fast_on` (`kernel/sched.inc:486`)
  is exact only for 65536/N.
- The hook runs on every entry with IF = 0.
- §53.6's restore removes it like `FSXF_FASTTICK`, so a crashed program
  cannot leave the PIT fast.
- It is general: a game at an exact 35 Hz, or a tracker on its row rate, can
  use it too.
- **Cost: 70–110 bytes of `.text` + 8 of `.bss`, resident** (estimate).

### 4.2 `OSAPI_FILE_READ_SEQ` — a streaming read *(kernel)*

`OSAPI_FILE_READ_AT` is stateless by design (§18.4.4): each call re-walks the
directory and the cluster chain from the front. A 20 MB partition has 2 KB
clusters (§52.3), so 13 MB into a file that is ~6,600 FAT steps per call,
seconds of CPU with the scheduler locked (model; DISK-CPU-PLAN 3.1).

§18.4.4's reason still holds: a resume token held **in the kernel** is
destroyed by the writes a copy loop does. So the token lives with the
**caller**:
- **The first call** stats by name and fills a caller-owned 16-byte cursor:
  volume, directory cluster, first cluster, size, current cluster, offset,
  and the volume's mount generation.
- **Later calls** read up to 63,488 bytes of whole clusters from the cursor's
  cluster, with no directory walk and no chain re-walk.
- **A remount or media change** answers `FERR_NAME`, and the caller re-seeds
  with one `READ_AT`.
- **The rule, stated rather than detected:** *a cursor is valid until
  anything writes that file.* In a bracket nothing else runs. Outside one,
  the player never holds a cursor across a return to the event loop.
- No sector number is ever exposed to the caller.
- **Cost: 150–220 bytes of `.cold`, resident** (estimate).

The Audio player (§86.5) streams through `READ_AT` and would gain too.

### 4.3 The progress-box fence *(kernel)*

`fpg_arm` refuses only when a *foreign* mode is up (`kernel/fprog.inc:331`,
`[fsx_cur] ≠ 0xFF`). A same-mode bracket, which is what In-window uses, would
get the disk progress box drawn over the video. The fix is to refuse whenever
**any** bracket is up.

It is a bug fix in its own right (GFX-FSX-PLAN 4.2.1 names the gap).
**Cost: < 10 bytes.**

### 4.4 SOUND.DRV's frame stream *(driver, not kernel)*

The driver's block is fixed at 2048 bytes (`drivers/sound/sb.inc:103`) and
`sbl_isr` has no callback (§34.3 refused `EVT_SND`). So the change is a new
open flag, `SND_OPENF_FRAME`:
- The caller gives a block size (= `achunk`, 64–4096) and a far callback.
- The driver runs auto-init DMA over a `2 × block` page-safe double buffer,
  with the DSP block length = `achunk`, so it raises one IRQ per frame.
- It calls the callback after the DSP acknowledge and before EOI, with
  IF = 0 and ES:DI at the half just played.
- Probing, IRQ discovery, DSP versions, the >22 kHz modes and the watchdog
  are all reused.
- **Cost: 150–250 bytes of driver image**, resident only while SOUND.DRV is
  loaded (estimate).

The alternative is to suspend the driver (§51.11.1) and program the DSP from
the player. That duplicates ~400 bytes and inherits §96.17.1's
unknown-IRQ-until-first-stream problem (open question 7).

### 4.5 The budget

| item | bytes (estimate) | resident |
|---|---|---|
| `FSXF_RATE` | 78–118 | every machine |
| `OSAPI_FILE_READ_SEQ` | 150–220 | every machine (`.cold` is resident) |
| progress fence | < 10 | every machine |
| **kernel total** | **~240–350 of the ~500 allowed** | |
| *held in reserve:* hard-disk runs that cross a head, as `CYLRUN` does for floppies (§18.91.1), **if Wave 0 shows** rung 0's stop-at-track-end (17 sectors, §52.1) is what caps the ST-225 | ~100–150 | every machine |
| SOUND.DRV frame stream | 150–250 | only while loaded |

`kernsize` will be quoted in bytes at every wave, per CLAUDE.md's banner.

## 5. Same or better? The ledger against XDC

| | XDC | ours |
|---|---|---|
| Disk, 5 samples | 41.9–105.1 KB/s | **24.0–82.6 KB/s, −19 to −43%** (measured) |
| BADAPPLE on a 20 MB ST-225 | 20.1 MB (does not fit), 93.8 KB/s | **13.0 MB, 60.6 KB/s** |
| Decode CPU, mean / worst frame | reference | **+2–4 / +3–6 points** (model; `rep movsw` not credited) |
| Audio copy | `rep movsb` | `rep movsw`, −2.1 points at 22 kHz/30 fps |
| Adapters | CGA | CGA, Hercules, VGA/EGA; composite in colour on 286+ VGA |
| Seek, pause, poster, preview, window | none | yes |

**Why the extra CPU is affordable.** It is spent in the interrupt. On a DMA
disk controller (the ST11M) the foreground's CPU spins in the BIOS for most of
each read, so interrupt work that fits in that spin does not slow the disk.

**Where the ledger must be re-read:**
- **XT-IDE or other programmed-I/O controllers**, where the CPU moves every
  disk byte itself. There the interrupt competes with the disk, and CPU is
  what binds. We are still within a few points of XDC and move 19–43% fewer
  bytes.

**The failure to watch for** is a run of heavy frames while the disk is also
near its limit. Wave 0 plays BADAPPLE's heaviest ten seconds from the
hard-disk profile and counts pauses. The count must be zero.

## 6. The host tools — `tools/os88vid.py`

- **`encode`.** XDC's encoder, ported:
  1. find the changed spans;
  2. pull hidden runs out of them;
  3. subdivide oversize spans;
  4. shave single pixels and tiny spans (optional);
  5. combine close slices;
  6. commit largest first against the pools.

  It differs from XDC in five ways:
  - the CPU pool is priced with **our** decoder's Wave 0 costs;
  - a **disk pool per second**, set by `maxdiskrate=` and defaulting to a
    named machine profile (open question 16);
  - spans split at row ends;
  - keyframes and a poster;
  - long slices as `rep movsw`.

  Input is XDC's script format (pre-dithered BMP frames, 8-bit WAV,
  `sourcefps=` …), so existing XDC projects re-encode unchanged. Whether it
  should also take ordinary video through ffmpeg and do the dithering itself
  is open question 12.
- **`import`.** XDV → ours. It decodes XDC's frame programs exactly (the
  grammar is ~10 opcodes, and all five samples parse with none unknown) and
  re-expresses each frame. No re-encode is needed. This is how the owner's
  samples become test content.
- **`stat` / `decode --frame N --png` / `verify`**, and `--selfcheck` in the
  build.

## 7. Not taken, and why

- **XDC's code-as-frames format.** Section 1: the addressing it ships per
  change is disk this machine does not have.
- **Hop entries and per-row groups.** Measured worse; see section 1.
- **A JIT from our lists to XDC-style code.** It pays per change in the
  foreground, which does *not* overlap the disk wait. That is worse on the
  scarce resource than decoding in the interrupt.
- **Writing a live window's framebuffer directly.** It smears the pointer
  (`gfx_lock` only promises a hide, §7.1) and breaks on a straddled display
  (§39.14). In-window gets the same picture inside a bracket, where the
  pixels are ours.
- **PC-speaker audio when there is no card.** §34.1's refusal.
- **Retiming the Hercules 6845 into CGA's layout.** It would make Hercules
  native, at zero translation cost, but it is untested on iron. It is kept as
  an option (open question 4), not the default.
- **An on-machine encoder, or an on-machine XDV importer.** The host tools
  are the path.

## 8. Waves

Each gate follows docs/WRITING-TESTS.md: break it on purpose and watch it go
red. A row about one package belongs in `soak`.

- **W0 — measure. No shipped byte.** A bench package in `tests/vidbench/`.
  - (a) Our four list loops against XDC's own frame code, on the heaviest
    BADAPPLE and THUNDERC frames, into CGA and Hercules memory. This fixes
    the cost model and the list layout.
  - (b) A 13 MB sequential read through `READ_AT` against a bench-only
    cursor. This sizes 4.2, and the reserve row in 4.5.
  - (c) A Sound Blaster auto-init stream with a 735-byte block at 22,050 Hz.
    This proves one IRQ per frame on MartyPC's SB.
  - (d) `rep movsw` against `rep movsb` into both kinds of video memory.
  - (e) Whether the SB 2.0's hardware ADPCM auto-init is available at the
    rates we want (open question 5).
  - It needs a MartyPC profile shaped like the owner's machine: 5150,
    Hercules, hard disk and SB. `os8088_xt_hdd_sb` exists, but there is no
    Hercules twin.
  - Output: a `docs/reports/` measurement.
- **W1 — host tools.** `os88vid.py` import, stat, decode, verify and a
  minimal encoder. Gate: decode(import(x)) equals XDC's decoded screen on
  every frame, on a generated stream and on the samples when their path is
  given. **Fixtures are generated, never committed.** The samples are
  copyrighted and stay outside the tree (open question 15).
- **W2 — kernel.** Sections 4.1–4.3, each with its SPEC section written
  first and its own gate row.
- **W3 — player, fullscreen CGA, silent (`FSXF_RATE`).** Gate: guest video
  memory after frame *N* equals the host decoder's frame *N*, and the frame
  rate is measured against guest cycles.
- **W4 — sound.** SOUND.DRV's frame stream, then the player on it. Gate: one
  IRQ per frame, bytes played = frames × `achunk`, and zero pauses across a
  60 s stream off the hard disk.
- **W5 — surfaces.** Hercules letterbox (plus the stretch option), VGA mode 6,
  the CGA composite burst, and 286+ composite in `VGA13` (a QEMU row, per
  docs/TESTING.md's list).
- **W6 — Preview.** File association (§54.6), the Open dialog, poster, scrub
  bar and info panel.
- **W7 — In-window and seek.**
- **W8 — the whole encoder** on W0's cost model.
- **W9 — Live windowed**, for RAM-resident clips, if the owner wants it.
- **Field.** The owner's 5150: BADAPPLE with sound off the ST-225, zero
  pauses, fullscreen and in-window.

## 9. Credit

The architecture is XDC's, and the About card says so: Jim Leonard
(Trixter / Hornet), XDC, 2014, MIT, with the Sound Blaster shell credited to
Stefan Goehler as XDC's own card does. The format and every line of code are
new.

## 10. Where the numbers came from

Four throw-away scripts decoded the five samples frame by frame against
XDC's grammar and priced both forms. Wave 1's `os88vid.py stat` is those
scripts made permanent, and it regenerates section 2.4's table.

## 11. Relation to other plans

- DISK-CPU-PLAN 3.1 prices the chain re-walk that section 4.2 removes.
- GFX-FSX-PLAN 4.2.1 is the progress-box gap in section 4.3.
- UI-FREEZE-PLAN 1 is why Live cannot stream from disk.

## 12. Open questions for the owner

1. **Names.** Proposed: the file extension `.V88`, the package in
   `apps/video/`, and *Video* in the dock.
2. **Version 1 canvases.** Proposed: 640×200 1bpp (mono and composite) only,
   with the header geometry-general so more come later. Candidates for later:
   - Hercules-native 720×348: sharper on the owner's machine, at ~2× the data
     for the same content;
   - CGA 160×100×16 on an RGB monitor, using §88.15's text-mode trick;
   - a VGA-native mode.
3. **Composite on VGA.** Colour on a 286 or better only; an 8088 with VGA
   shows the mono pattern. Is that acceptable?
4. **Hercules presentation.** A 1:1 letterbox by default, plus an optional
   1.5× stretch at +50% writes on the doubled rows. Should the 6845 retime
   also be tried as a third option?
5. **Audio.** 8-bit PCM at the encoder's chosen rate is the default. The
   SB 2.0 can decode 4-bit ADPCM in hardware, which would halve audio
   (BADAPPLE 60.6 → ~50 KB/s) at lower quality and possibly a lower rate
   ceiling (unverified). Version 1, or later?
6. **No card.** Silent video, clocked exactly by `FSXF_RATE` (~80–120
   resident bytes). Confirm.
7. **Sound Blaster route.** Extend SOUND.DRV with the frame stream
   (recommended), or suspend it and drive the DSP from the player?
8. **Streaming read.** The caller-held cursor of section 4.2, as a general
   published slot?
9. **kern_small.** Should a fullscreen-only player run on the 128 KB machine?
   That puts sections 4.1 and 4.2 in both kernels, resident on the 128 KB
   machine too.
10. **Windowed tiers.** Preview and In-window as described. Is Live, for
    RAM-resident clips only, wanted at all?
11. **Keyframes.** A 2 s interval, snap-to-keyframe seeking, the poster rule.
12. **Encoder input.** XDC's script format only, or also ordinary video
    through ffmpeg, with our own dithering and composite colour matching (the
    hard part)?
13. **Interrupts off while a frame decodes** (worst ~19 ms at 30 fps). A
    second keystroke or a serial-mouse byte can be lost. Acceptable?
14. **The 50% CPU cap.** Keep XDC's per-frame cap for our encoder, or make it
    a profile setting?
15. **The five samples.** May they be used as local test content, outside the
    repository, with rows that take a path?
16. **Default encode target.** The machine profile `encode` assumes unless
    told otherwise. Proposed: the owner's 5150 and ST-225, with the disk pool
    capped around 64 KB/s for margin.
