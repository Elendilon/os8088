# XDC-VIDEO-PLAN — full-motion video on a 4.77 MHz 8088

**Status: PLAN, nothing built.** Written 2026-09-25 against XDC commit
`56a5dc1` (github.com/MobyGamer/XDC, MIT, (c) 2014 Jim Leonard) and five
precompiled XDC streams the owner supplied. Every number marked *measured*
comes from decoding those five files exactly, byte for byte, or from a
PERFORMANCE.md set. Every number marked *model* is arithmetic: XDC's own
cycle constants, or an estimate of ours. Wave 0 exists to replace every
*model* figure with a MartyPC reading before any shipped byte is written.

## 0. The answer on one screen

**XDC can be ported.** On the owner's own machine (5150, Hercules, SB 2.0,
ST-225; see docs/FIELD-MACHINES.md) it can plausibly match the original and
in two respects beat it. It is not a straight port, for three reasons found
while writing this plan:

1. **An XDC video frame is a PROGRAM.** The player far-calls each frame's
   bytes (`XDC_PLAY.PAS`, `call framehp`). The encoder emits `mov di` /
   `rep movsb` / `movsw` / `stosb` sequences with a fixed header and a
   `pop ds / retf` footer, and those sequences ARE the file format. Playing
   an XDV as shipped means running code off a disk.
2. **On this machine the disk binds, not the CPU.** XDC's encoder caps every
   frame at 50% of the machine by its own model, and the samples never exceed
   it. BADAPPLE, though, needs **93.8 KB/s** (measured). The ST-225 delivers
   **74,553 B/s** through os8088's own reads (PERFORMANCE.md Set 24), so the
   original stream could not keep up on the owner's disk. At 20.1 MB it does
   not even fit the drive's 20.4 MB partition with the system on it.
3. **os8088 has four gaps**, one on each side of the player (section 3). There is
   no frame-rate interrupt a package may own. There is no read that stays cheap
   20 MB into a file. The fake-windowed bracket has a hazard. And a real
   window cannot be written to directly.

**The recommendation** is a host-side converter plus an interpreting player.
`tools/os88xdv.py` decodes an XDV exactly and writes an os8088 stream
(`.XDO`, section 4.2). The frame program becomes a compact, row-grouped record list
that the player interprets inside the frame interrupt. This is
**16–37% less disk** than XDC on the five samples (measured). BADAPPLE drops
to **72.3 KB/s and 15.5 MB**, which fits the drive and fits the rate. It is
also safe by construction, and it drives every adapter and a window from one
file.

The price is CPU: the interpreter pays per delta where XDC's code pays
nothing. BADAPPLE is 65% one- and two-byte deltas, and a pessimistic
interpreter takes its mean frame from 14% to 27% of the machine and its worst
from 50% to 65% (model). That work runs in the interrupt, where on a DMA disk
it overlaps the wait for the transfer rather than competing with it (section 5.2).
**Decision D1 is whether that trade is taken, and Wave 0 measures it** with a
fallback already costed.

## 1. What XDC is

**The stream (`XDC_GLOB.PAS`).**
- A 512-byte header: `XDCV`, `numpackets`, `largestpacket`, `achunksize`,
  `samplerate`, `vidmode` (1 = 160×200×16 composite CGA, 2 = 640×200×2,
  3 = Tandy, 4 = HP 95LX), 80, 200, and an unused feature byte.
- Then one packet per frame, padded to 512 bytes. Each packet is
  `[video code][video data] … [audio chunk]`.
- A trailing index: one byte per packet, holding the packet's length in
  sectors.
- The frame rate is `samplerate / achunksize`. The encoder nudges the sample
  rate (22050 → 22058) so the division comes out even.
- There are **no keyframes**. Every frame is a delta against the screen the
  previous one left, starting from black.

**The frame program (`XDC_CODE.PAS`, `XDC_COMP.PAS`).**
- The header is `push ds / push cs / pop ds / mov si,<data> / mov ax,B800 /
  mov es,ax / mov ch,0 / cld`. The data follows the code in the same packet.
- Each delta is `mov di,imm16` followed by one of: unrolled `movsw`/`movsb`
  (≤ 6 bytes), `mov cl,n / rep movsb`, `mov al,v / rep stosb`, unrolled
  `stosb`, or `es: mov [imm],imm`.
- The DI offsets are raw CGA mode-6 addresses, so they include the bank
  interleave.
- The encoder spends a cycle pool of `76*262*4/2` cycles per 59.94 Hz frame,
  scaled to the source rate. That is exactly half the machine. It fills the
  pool **largest delta first**, so a bandwidth-starved frame converges over
  the next few (`frameIntegrity`).

**The player (`XDC_PLAY.PAS`).**
- The main loop fills a slab ring buffer from disk in reads of at least 32 KB
  and does nothing else.
- **All playback happens in the Sound Blaster's IRQ.** The DMA double buffer
  is `2 × achunksize`, so every half-buffer interrupt is one frame. The
  handler copies that frame's audio chunk into the finished half with
  `rep movsb`, then far-calls the frame's code.
- If the ring runs dry, the handler plays silence and advances nothing,
  counting a "pause".
- **Without a card**, PIT channel 0 is reprogrammed to the frame rate and the
  same procedure runs from IRQ0. The 18.2 Hz BIOS tick is kept exact by
  accumulating PIT counts and chaining on carry. No audio plays.

**Why the interrupt placement matters.** The disk read in the foreground
spends most of its time with the CPU spinning in the BIOS while DMA moves the
sectors. The frame interrupt fills exactly that spin. **Playing frames from
the foreground instead of the interrupt would stall the video for the whole
length of every read.** Everything below keeps XDC's placement.

## 2. The five samples, measured

`tools/os88xdv.py stat` will reproduce this table (Wave 1). All five files
parse against the grammar above with **zero unknown opcodes**, and every
packet carries the same 14-byte frame header apart from its 2-byte data
offset.

| file | mode | fps | audio | deltas/frame mean / p95 / max | bytes written/frame mean | XDC rate | compact rate | file |
|---|---|---|---|---|---|---|---|---|
| BADAPPLE | 2 mono | 30.000 | 22050 × 735 | 299 / 538 / 738 | 942 | 93.8 KB/s | **72.3 KB/s** (−23%) | 20.1 → **15.5 MB** |
| THUNDERC | 1 composite | 23.976 | 22058 × 920 | 142 / 269 / 623 | 2,180 | 92.8 | 77.5 (−16%) | 6.9 → 5.8 |
| TRONDISC | 1 composite | 23.976 | 22058 × 920 | 193 / 403 / 811 | 2,358 | 105.1 | 87.5 (−17%) | 5.0 → 4.1 |
| BBBB_BW | 2 mono | 60.000 | 8040 × 134 | 45 / 111 / 174 | 185 | 41.9 | 26.6 (−37%) | 0.3 → 0.2 |
| BBBBCOMP | 1 composite | 60.000 | 8040 × 134 | 41 / 95 / 174 | 256 | 46.3 | 31.4 (−32%) | 0.3 → 0.2 |

*Compact* means the record format of section 4.1, costed at 2 bytes per touched row
and 2 bytes per delta, plus the data (or 1 value byte for a run), with frames
**not** padded to 512 bytes. XDC's padding alone is 165–227 bytes a frame,
6–7 KB/s at 30 fps.

**Delta lengths** (share of all deltas):

| file | 1 byte | 2 | 3–6 | 7–16 | >16 | runs | cross a row |
|---|---|---|---|---|---|---|---|
| BADAPPLE | **37.9%** | **27.0%** | 24.8% | 8.7% | 1.5% | 2.4% | 0.60% |
| THUNDERC | 1.3% | 0.4% | 42.9% | 27.7% | 27.6% | 10.0% | 9.21% |
| TRONDISC | 2.5% | 1.2% | 42.4% | 30.3% | 23.6% | 5.7% | 2.97% |
| BBBB_BW | 20.8% | 35.5% | 29.6% | 11.2% | 3.0% | 2.5% | 0.40% |

**CPU per frame, XDC's own cycle model** (percent of the frame period on a
4.77 MHz 8088):

| file | direct (XDC) mean / max | interpreter mean / max (+45/delta, +40/row) | audio copy `movsb` → `movsw` |
|---|---|---|---|
| BADAPPLE | 14% / 50% | 27% / 65% | 7.9% → 5.8% |
| THUNDERC | 22% / 49% | 27% / 57% | 7.9% → 5.8% |
| TRONDISC | 24% / 50% | 31% / 59% | 7.9% → 5.8% |
| BBBB_BW | 6% / 50% | 10% / 54% | 2.9% → 2.1% |

What the numbers say:
- **The 50% ceiling is the encoder's own cap.** The worst frame of every file
  touches it.
- **Mode 1 ("composite") is the same bitmap as mode 2.** It is 640×200 1bpp in
  CGA layout; only port 3D8h's colour-burst bit differs. Each 4-bit group is
  a composite artifact colour. So one decoder serves both.
- **Deltas that cross a row boundary are rare but real**, up to 9.2% in
  THUNDERC, whose runs span rows. A converter that splits them at row ends
  costs a few percent of deltas and buys an address translation per row
  (section 4.3).

## 3. What os8088 has, and the four gaps

**What we can reuse as it stands:**
- **§53's fsx bracket.**
  - `OSAPI_FSX_MODE` sets `FSXM_CGA640` (int 10h mode 6) on CGA and VGA, and
    `FSXM_HERC` on Hercules.
  - Past the mode set, the 6845, 3D8h and every VGA register are the app's
    (§53.7).
  - File slots are legal inside the bracket. IRQ0, the BIOS chain and
    `TF_SERVICE` workers keep running (§53.2), so an SB stream plays across
    the bracket.
  - **Esc** and **F** are the bracket's keys by convention.
- **The same-mode bracket** (§53.7; consumers are Paint §42.7 and Dot
  Delirium). It never calls `fsx_mode`, so the desktop stays on the glass,
  frozen, and the app owns every pixel of `fsx_surf`. This is the owner's
  "fake windowed mode" and it already exists.
- **§34.5's Sound Blaster driver.** It covers DSP ≥ 2.00 auto-init, rates to
  22,222 Hz (to 44,100 Hz with DSP ≥ 3.00), IRQ discovery, and verb 9's exact
  "bytes played" (§34.5.1).
- **Heap and file association.**
  - One claim may exceed 64 KB. The largest run on a 640 KB machine is
    **426 KB** with the hard disk ticked (§50.3).
  - Association works by extension (§54.6), and `OSAPI_ARG_FILE` hands the
    document to the entry proc (§54.5).
- **Documented adapter layouts.** Hercules is B000, stride 90, 4 banks. CGA
  is B800, stride 80, 2 banks. VGA is A000, stride 80, linear.

**G1 — there is no frame-rate interrupt a package may own.**
- SOUND.DRV's block is fixed at `SBL_HALF` = 2048 bytes
  (`drivers/sound/sb.inc:103`), which is 10.8 interrupts a second at
  22 kHz. `sbl_isr` has no callback, and `EVT_SND` was refused (§34.3). XDC
  needs one interrupt per `achunksize` bytes with code run inside it.
- The PIT is the kernel's. §53.7 forbids reprogramming channel 0 inside a
  bracket, and `FSXF_FASTTICK` is fixed at 54.6 Hz (§53.2.1, `FSX_SUBTICK`
  = 3, `sch_fast_on` at `kernel/sched.inc:486`).
- So neither of XDC's clocks is reachable today.

**G2 — `OSAPI_FILE_READ_AT` is priced for a 116 KB file, not a 16 MB one.**
- It is stateless on purpose (§18.4.4). Every call re-walks the directory
  and then the cluster chain from the front.
- A 20 MB partition has 2 KB clusters (§52.3), so 15 MB in is ~7,500 FAT
  steps per call. Each step is a lookup through a 9-sector FAT window that
  pages across a 41-sector FAT.
- That is **seconds of CPU per call** late in the file (model; the chain
  walk is the cost DISK-CPU-PLAN.md 3.1 names), and it runs with the
  scheduler locked.
- §18.4.4 is right that a resume token held **in the kernel** is destroyed by
  the writes a copy loop does. The answer must keep the token with the
  caller.

**G3 — the same-mode bracket does not fence the file-progress widget.**
`fpg_arm` refuses only when `[fsx_cur] ≠ 0xFF` (`kernel/fprog.inc:331`), and
a same-mode bracket leaves it at 0xFF. Streaming a video in a same-mode
bracket would draw the progress box over the picture. docs/plans/completed/GFX-FSX-PLAN.md
4.2.1 already names the gap.

**G4 — a live window cannot be written directly.**
- Every pixel reaches a window through a public entry: `OSAPI_GFX_BLIT1`,
  under the lock and the clip.
- Writing the framebuffer around it smears the cursor (`gfx_lock` only
  promises a hide, §7.1) and breaks on a straddled display (§39.14).
- `BLIT1` costs ~4.5–5 µs a byte on the 8088 (PERFORMANCE.md Set 64 and
  §5.4.2.6). A 640×200 frame is ~80 ms, and 7,800 bytes is ~37 ms.
- A live window cannot be driven from an interrupt either: the drawing needs
  the gfx lock.
- And while the UI task reads the disk, `[sch_lock]` freezes every worker
  (UI-FREEZE-PLAN 1). So a disk-streamed video cannot be both **live in a
  window** and **fed at 72 KB/s** on this machine.

## 4. Decisions

### D1 — interpret compact records, do not execute the file *(the central decision)*

**(a) Execute XDC's frame program as shipped.**
- Fastest per delta; zero decode cost.
- But the file is code, and every byte read off a disk is treated as hostile
  here. A verifier over the frame program is not cheap. BADAPPLE is
  ~723 instructions a frame, and a table-driven check is ~35 cycles each, so
  ~25 k cycles a frame (model). That is *more* than (b) costs, and it adds
  nothing: no Hercules, no window, no bandwidth saving.

**(b) Host conversion to compact records, interpreted in the frame
interrupt. RECOMMENDED.**
- Safe by construction. Every write goes through `ES:DI` computed by the
  player from a row table the player owns. A bounds check is one compare per
  row, not per byte.
- 16–37% less disk, which is the constraint that binds.
- One file serves CGA, Hercules, VGA, a same-mode window and a RAM shadow,
  because the row table is the only thing that changes (section 4.3).
- Cost: per-delta overhead. The model above is pessimistic (+45/delta). The
  record design in section 4.1 aims at parity for one- and two-byte deltas. That is
  where BADAPPLE lives, and where XDC's `mov di,imm16 / movsb` is cheapest.

**(c) Host conversion to verified code, re-emitted by the player at load.**
A JIT is the same per-delta work as (b), paid in the foreground where it does
*not* overlap the disk wait (section 5.2). It is worse than (b) on the one resource
that is short, so it is not taken.

**The gate.** Wave 0 measures (a) against (b) on MartyPC, on BADAPPLE's
heaviest frames, to CGA and Hercules memory. (b) ships if its worst frame
stays under **75%** of the frame period at BADAPPLE's rate. The remaining 25%
is XDC's own ring-fill headroom halved; it is a proposed threshold for the
review, not a derived one. If (b) misses, the fallback is (a) plus a verifier
behind a per-file **trust** answer the user gives once. That fallback is
costed above and is the reason (a) is not simply deleted.

#### 4.1 The record format (candidate v0, fixed by Wave 0)

A frame's video part is a list of **row groups** in ascending source row
(0..199, in display order, not bank order). The end is marked by row = 0xFF.
Inside a group, deltas are split into **length classes**, so the interpreter
never dispatches per delta:

```
row group: row, n1, n2, nS, nR
  n1 × [skip][byte]            1-byte pokes      lodsb / add di,ax / movsb
  n2 × [skip][word]            2-byte pokes      lodsb / add di,ax / movsw
  nS × [skip][len][len bytes]  slices            … / rep movsw + movsb
  nR × [skip][len][value]      runs              … / rep stosb
```

- **`skip` is relative.** DI starts at the row base from the surface's row
  table and advances by `skip` from where the previous write ended. A row is
  ≤ 90 bytes, so `skip` is always a byte, and AH = 0 is a loop invariant, so
  `add di,ax` needs no zero-extend.
- **Loops are unrolled** Duff-style on the count, so there is no `dec/jnz` per
  delta.
- The class counts cost 4 bytes per row. In exchange the per-delta header
  shrinks to 1 byte for pokes, against XDC's 3–4 code bytes. Whether that
  beats the flat 2-bytes-per-delta the table in section 2 assumed is exactly what
  Wave 0 decides.
- **Long slices use `rep movsw`.** XDC emits `rep movsb` and its comment says
  why (it models `movsb` as half a `movsw`, which on a real 8088 it is not:
  17 vs 12.5 cycles a byte). This is one place the port should be *faster*,
  on THUNDERC and TRONDISC's long deltas especially. Wave 0 measures it on
  CGA memory, where wait states may flatten the gain.
- **Parity target.** A 1-byte poke unrolled is `lodsb / add di,ax / movsb` =
  3 code bytes and ~33 cycles. XDC's is `mov di,imm16 / movsb` = 4 code bytes
  and ~35 by its own model.

#### 4.2 The container — `.XDO`

It is written by the host tools only, and every field is validated on load as
hostile input.

- **Header** (one sector).
  - Signature, version, mode (1/2), width in bytes, rows, fps as
    `samplerate / achunk`, frame count, and audio format (8-bit unsigned mono
    PCM; one feature bit is reserved for section 7's ADPCM).
  - Largest super-packet, poster frame index, and the offsets and counts of
    the three tables below.
- **Super-packets.**
  - Each is a run of whole frames, `[len16][video records][audio chunk]`
    repeated, padded to 512 **per super-packet**, not per frame.
  - A super-packet is at most 32 KB. That is XDC's own read size and one
    §18.4.4 chunk at any cluster size up to 32 KB.
  - Padding overhead is ~0.8% where XDC's per-frame padding was ~7%.
- **Super-packet index.** Sector count, first frame and frame count for each,
  so the player reads whole super-packets into a ring that wraps only at
  super-packet granularity.
- **Keyframe table** (section 6). Frame number, file offset and size for each, plus
  the super-packet to resume from.
- **No executable byte anywhere.** A converter that sees an XDV opcode
  outside the grammar refuses the file and names the frame.

#### 4.3 Surfaces — one file, a row table per target

| adapter | fullscreen mode | layout | 640×200 placement | mono (mode 2) | composite (mode 1) |
|---|---|---|---|---|---|
| CGA | `FSXM_CGA640` | B800, 2 banks, 80 | whole screen | native | burst on (3D8h ← 1Ah): real colour on a composite monitor, stripes on RGB, exactly as XDC |
| VGA / EGA | `FSXM_CGA640` | the BIOS's CGA-compatible mode 6, double-scanned to 400 lines | whole screen | native | **8088:** mono stripes (the RGB-monitor look). **286+:** `FSXM_VGA13` with a 256-entry byte → four-pixel table from XDC's own composite palette, tiered on `OSAPI_CPU_INFO` (rule 7). ~85 cycles a changed byte, which is too much for an 8088 (model) |
| Hercules | `FSXM_HERC` | B000, 4 banks, 90 | letterboxed at (40,74) | native, through the row table | mono stripes |

**Hercules needs no retiming.** The row table puts source row *y* at
`0x2000·((y+74) mod 4) + 90·⌊(y+74)/4⌋ + 5`. Reprogramming the 6845 to CGA
geometry (2 scan lines per row) was considered and is not taken: the row
table gives the same zero-copy result with no field risk. An optional
**1.5× stretch** writes every odd source row twice through a second row base,
filling 300 of 348 lines. It costs +50% writes on those rows, so it is a menu
choice measured in Wave 5, not a default.

**In-window (same-mode bracket)** uses the same interpreter with a row table
aimed at the window's content rect, in the desktop's own layout:
- **Hercules desktop, 720×348:** the full 640×200 fits in a window at 1:1.
  This is the owner's machine.
- **CGA desktop:** ~132 content rows. Show the **even rows only**, 640×100
  cropped to the content width. XDC calls this `cheating` and offers it
  itself. The row groups make skipping odd rows free, because a group is
  skipped by its length and never decoded.
- **VGA desktop, mode 12h:** 624 columns and all 200 rows, with Map Mask 0Fh
  so one byte lands in all four planes. That is the resting state
  `OSAPI_GFX_BLIT1` already keeps (§5.4.2).

### D2 — the frame clock: extend SOUND.DRV, and give fsx a rate

**With a Sound Blaster: a FRAME stream in SOUND.DRV. RECOMMENDED.**
- A new open flag, `SND_OPENF_FRAME`. The caller supplies a block size
  (= `achunk`, 64–4096) and a far callback.
- The driver runs auto-init DMA over a `2 × block` page-safe double buffer,
  with DSP block length = `achunk`, so it raises **one IRQ per frame**, as
  XDC does.
- In the ISR, after the DSP acknowledge and before EOI, it far-calls the
  callback with IF = 0 and ES:DI at the half just played.
- The existing probe, IRQ discovery, DSP-version handling, >22 kHz modes and
  the `sbl_tick` watchdog are all reused.
- Cost: driver image bytes, **not kernel bytes**, resident only while
  SOUND.DRV is loaded.

The alternative, `OSAPI_DRV_SUSPEND` plus programming the DSP from the player
(§51.11.1 permits it, and the DOS box does it, §96.17), duplicates ~400 bytes
of driver in the package. Worse, it inherits the deferred-IRQ problem: the
IRQ is 0FFh until some stream has been opened (§96.17.1). It is kept as the
**fallback** if the driver change is refused.

**Without one: `FSXF_RATE`, a caller-rated IRQ0 inside the bracket.**
- A third `OSAPI_FSX_RUN` flag. DX is a PIT divisor, and a far hook is
  registered with it.
- `sch_isr` accumulates the divisor into a 16-bit counter and chains the BIOS
  tick and `[ticks]` **on carry**. That is XDC's `noSoundIntCaller` exactly,
  and it keeps the 18.2 Hz clock exact at any rate, where `sch_fast_on`'s
  divide keeps it only for 65536/N.
- The hook is called on every entry with IF = 0.
- It is torn down by §53.6's restore like `FSXF_FASTTICK`. The bracket owns
  it, so a crashed app cannot leave the PIT fast.
- **This is the one resident kernel change the plan needs** (estimated
  70–110 bytes of `.text` in `sched.inc`, plus 8 of `.bss`). Per CLAUDE.md's
  banner, the question is whether ~100 bytes on every machine is worth a PIT
  clock any exclusive app can use: a game at 35 Hz, a tracker at an exact
  row rate. The plan says yes and the review decides.

**Both paths call the same package hook.** Anything else the player does is
identical with or without a card. With the card, the audio clock is also the
frame clock, sample-accurate, as XDC.

**The hook runs with interrupts off**, for up to 65% of a frame on the worst
BADAPPLE frame (model), ~21 ms. That loses at most one keyboard scancode if
two keys land in one frame, and can overrun the 8250 at 1200 baud (one byte
per 8.3 ms). The mouse is unused in the bracket and its ISR resyncs on the
sync bit. Re-enabling interrupts inside the hook would let IRQ0 nest into a
possible task switch on the interrupted stack, so it is open question 9 in
section 10 rather than a design.

### D3 — streaming: a caller-held cursor, `OSAPI_FILE_READ_SEQ`

A new slot beside `OSAPI_FILE_READ_AT`:
- **The first call** stats the file by name, like `READ_AT`, and fills a
  **caller-owned** 16-byte cursor: volume, directory cluster, first cluster,
  size, current cluster, current offset, and the volume's mount generation.
- **Each later call** reads the next N whole clusters (N up to 63,488 bytes of
  capacity) **from the cursor's cluster**. It never re-walks the directory or
  the chain.
- It refuses rather than mis-reads when the generation moved, i.e. a media
  change or a remount, and answers `FERR_NAME`. The caller then falls back to
  one `READ_AT` at its offset to re-seed.

Why this answers §18.4.4's objection:
- The token is in the caller's memory, so the kernel's own copy loop cannot
  destroy it.
- The one writer that could invalidate it is another program writing the same
  file. Inside an fsx bracket, that program is frozen.
- Outside one, the rule is stated rather than detected: **a cursor is valid
  until anything writes that file**. That is the contract `READ_AT`'s
  statelessness was protecting, and the player's own windowed paths never
  hold a cursor across a return to the event loop.

Other properties:
- **No raw sector is exposed.** The cursor's cluster numbers are only ever
  handed back to the kernel, never used by the caller.
- **Seeking** is one `READ_AT`-priced re-seed. A keyframe seek re-seeds at the
  keyframe's super-packet.
- **Where the bytes go:** `.cold` (resident), estimated 150–220 bytes,
  mostly the chain step `dskw_read` already has.

Wave 0 measures `READ_AT` against a prototype cursor on MartyPC's hard-disk
profile. The prize is known. The unknown is whether rung 0's
stop-at-track-end (17 sectors, §52.1) caps the ST-225 below 72 KB/s once the
chain walk is gone. If it does, the second half of D3 is letting a hard-disk
run cross a head the way `CYLRUN` does for floppies (§18.91.1).

### D4 — close G3

`fpg_arm` refuses whenever **any** bracket is up, not only a foreign mode:
- One compare against the bracket's owner byte.
- A few bytes of `.text`.
- A gate row that streams in a same-mode bracket and asserts that no widget
  pixel lands.

It is a bug fix that stands on its own, and it ships in Wave 2 whatever
else is decided.

### D5 — what "windowed" means, in three tiers

| tier | what the user sees | how | viable on the 5150 |
|---|---|---|---|
| **Preview** (true windowed) | The poster frame in the window. A scrub bar picks any keyframe, and the window shows that frame. Info: fps, length, KB/s, and whether *this* disk keeps up | Decode one keyframe (section 6) into a 16 KB RAM shadow, then `OSAPI_GFX_BLIT1` the content rect. ≤ ~80 ms a picture | **Yes, always**. This is the owner's "first frame by default" plus the keyframe scrubber |
| **In-window** (same-mode bracket) | Full-rate video with audio **inside the window's rect**. The rest of the desktop is left on the glass, frozen. Space pauses and returns to Preview on the current frame; Esc stops | D1's interpreter in D2's interrupt, writing through the in-window row table (section 4.3). On exit the content rect is read back into the shadow, so the window can repaint without the stream | **Yes**, at the same rate as fullscreen. This is the owner's "fake windowed" |
| **Live windowed** (desktop running) | Video in a movable window while other programs run | Worker decodes into the RAM shadow, blits the dirty row band at ≤ 18.2 Hz, clocked by verb 9 of a normal SOUND.DRV ring (§34.5.1) or by `[ticks]` | **Only for clips that fit in RAM** (BBBB is 0.2 MB of a 426 KB arena). A disk-streamed clip cannot be both live and fed at this rate (G4). The feature REFUSES a stream it cannot keep up, with the arithmetic, instead of stuttering (rule 6) |

Fullscreen is the fourth mode and is the headline. The window's menu offers
**Play fullscreen**, **Play in window**, and **Play live** (the last greyed
with its reason when the clip does not fit in RAM).

### D6 — the encoder is ported too, to Python

XDC's encoder is ~1,300 lines of Turbo Pascal. `tools/os88xdc.py` ports its
algorithm, in the same order:
1. find deltas;
2. extract hidden runs;
3. subdivide oversize ones;
4. shave pixels and deltas;
5. combine nearby slices;
6. fill a cycle and byte pool, largest first.

It reads XDC's own script format (BMP frames, WAV, `sourcefps=`, `shavepixels=`
…), so existing XDC projects re-encode unchanged. Four changes from XDC:
- **The cost model is OURS**, taken from Wave 0's measurements of the
  interpreter per surface, not `XDC_CODE.PAS`'s constants.
- **Deltas never cross a row.**
- **It writes `.XDO`** with keyframes.
- **A byte pool per second, not per frame** (`maxdiskrate=`). This targets the
  disk the stream is for, e.g. `maxdiskrate=70` for the ST-225.

## 5. Same or better? The ledger against XDC

**5.1 Where the port is better (measured or arithmetic):**

| | XDC | port | |
|---|---|---|---|
| Disk bandwidth | 41.9–105.1 KB/s | 26.6–87.5 KB/s | **−16 to −37%** (measured, section 2) |
| BADAPPLE on a 20 MB ST-225 | does not fit (20.1 MB) and needs 93.8 KB/s | fits (15.5 MB), needs 72.3 KB/s | measured file sizes; 74.5 KB/s is Set 24's |
| Audio copy per frame | `rep movsb`, 17 cycles a byte | `rep movsw`, 12.5–13.3 (PERFORMANCE.md Set 117.2) | 7.9% → 5.8% of a 30 fps frame |
| Long slices | `rep movsb` | `rep movsw` | to be measured on CGA memory (section 4.1) |
| Adapters | CGA | CGA, Hercules, VGA/EGA; composite in colour on 286+ VGA | |
| Seek, pause, poster, preview | none | keyframes (section 6) | |
| Malformed file | runs it | refused with the frame number | |

**5.2 Where it pays, and why that is affordable.** The interpreter's
per-delta overhead is the one cost XDC does not have: +13 points on
BADAPPLE's mean frame and +15 on its worst (pessimistic model). It is spent
in the frame interrupt, and on a DMA hard-disk controller (the ST11M) the
foreground's CPU is spinning in the BIOS for most of each read. So interrupt
work that fits in that spin does not slow the disk. What it can do is starve
the ring-fill loop's own bookkeeping. At 72 KB/s that is ~3 reads a second,
microseconds each.

The real failure mode is different: a **run** of heavy frames while the disk
is also near its limit. Wave 0's streaming bench plays BADAPPLE's heaviest
10 seconds from the hard-disk profile and counts ring underruns. XDC's
"pauses" is the metric, and it must be zero.

**5.3 Open against "better".**
- **XT-IDE / PIO controllers.** There the CPU *does* move every byte, so
  interrupt time competes with the disk. XDC's original target was such a
  machine. The port plays there, but the ledger must be re-read.
- **Worst-frame jitter at 60 fps.** BBBB's 8040 Hz / 134-byte frames leave
  16.7 ms per frame. The worst BBBB_BW frame is 54% of that under the
  pessimistic model.

## 6. Keyframes and the preview

**XDC has none, so the converter makes them.** It simulates the stream on
the host and snapshots the **decoded screen**, not a source frame, after
frame *k* every *K* seconds. Because the snapshot is the exact state the
stream leaves, playback can resume at frame *k+1* with no error. This
matters: XDC's frames are lossy over time (`frameIntegrity` lets a starved
frame finish over the next few), so a *source* frame would not match.

**A keyframe is stored as an ordinary video record list against a black
screen.** The decoder is the one the player already has, and no second codec
ships. Its size is the frame's own complexity. BADAPPLE's silhouettes are
mostly runs, and a busy composite frame approaches 16 KB plus row headers.

**Keyframes live in their own region**, read only by the preview and by
seeks. They cost disk space and **zero playback bandwidth**.
- The default *K* = 2 s is a proposal: 110 keyframes for BADAPPLE, at
  1–16 KB each.
- The converter prints the measured total, and `--kf=` changes the interval.

**Poster frame.** Many videos open on black, so the header names one. It
defaults to the first keyframe whose decoded screen is not ≥ 98% one value,
and `--poster=` overrides it. Frame 0 is always the fallback, per the ask.

**Seek granularity is the keyframe.**
- A seek snaps to the nearest keyframe at or before the target. It decodes
  that keyframe straight to the surface, re-seeds D3's cursor at its
  super-packet, and restarts audio there.
- An exact seek would mean replaying up to *K* seconds of deltas, ~150 KB of
  reading at BADAPPLE's rate, about 2 s on the ST-225. It is offered only on
  a paused picture, never on the scrub bar.

## 7. Not taken, with the reason

- **Executing XDC code** as shipped. See D1; kept as the costed fallback.
- **Retiming the Hercules 6845** into CGA geometry. The row table does the
  same job with no field risk (section 4.3).
- **Writing a live window's framebuffer directly.** It smears the cursor and
  breaks straddled displays (G4). In-window playback gets the same effect
  inside a bracket, where the pixels are the app's.
- **PC-speaker PCM when no card is present.** Interrupt-paced speaker PCM
  was refused at 36–50% of the floor machine (§34.1), and the video needs
  that CPU. The no-card path is silent, as XDC's is. It can be reopened for a
  286+ tier.
- **An in-OS XDV → XDO converter.** Converting in the player costs a parse
  per frame (~25 k cycles, model) on top of a 23% larger read. As a one-off
  batch job on a 5150 it would be ~20 minutes for BADAPPLE. It is possible,
  but it is a later wave if at all. The host tool is the path.
- **Creative ADPCM audio** (DSP ≥ 2.00 decodes 4-bit ADPCM in hardware).
  It would halve audio's 21.5 KB/s at zero CPU cost. It is not taken yet
  because the DSP's ADPCM rate ceiling and quality at 22 kHz are unverified.
  A feature bit is reserved (section 4.2), and it is the first thing to try if
  BADAPPLE's 72.3 KB/s proves too close to the ST-225's 74.5.

## 8. Waves

Each wave names its gate. docs/WRITING-TESTS.md applies: every gate is
broken on purpose once and watched going red, and a row about one package
belongs in `soak`, not `fast`.

- **W0 — measure. No shipped byte.** A bench package under `tests/xdcbench/`
  plus a MartyPC script:
  - (a) Direct XDC code against candidate interpreters, on BADAPPLE's and
    THUNDERC's 20 heaviest frames, to CGA and Hercules memory. This decides
    D1 and freezes section 4.1.
  - (b) `READ_AT` against a package-side prototype cursor (a private copy of
    the chain walk, bench only), reading a 16 MB file at 32 KB. This sizes D3.
  - (c) A SB auto-init stream with a 735-byte DSP block at 22,050 Hz, bench
    only via `OSAPI_DRV_SUSPEND`. This proves one IRQ per frame on MartyPC's
    SB.
  - (d) `rep movsb` against `rep movsw` into CGA and Hercules VRAM.
  - It needs a MartyPC profile with the owner's machine shape: 5150,
    Hercules, hard disk and SB. `os8088_xt_hdd_sb` and `os8088_xt_vga_hdd_sb`
    exist, but there is no Hercules + hard disk + SB twin.
  - Output: a `docs/reports/` measurement and the go/no-go on D1.
- **W1 — host tools.**
  - `tools/os88xdv.py` with `stat`, `verify`, `decode --frame N --png`, and
    `convert` to `.XDO` with keyframes and a poster.
  - A minimal `tools/os88xdc.py` encoder, frames plus WAV to `.XDO` without
    the optimizer, so tests have fixtures that are **generated, not
    committed**. The owner's five samples are copyrighted material and never
    enter the tree; rows that want real content take a path.
  - Gate: `--selfcheck`, i.e. decode(convert(x)) equals decode(x) screen for
    screen on every frame of a synthetic stream, and of the samples when
    given.
- **W2 — kernel.** SPEC first, per CLAUDE.md:
  - `OSAPI_FILE_READ_SEQ` (§18.4.x), `FSXF_RATE` (§53.2.x) and D4's fence.
  - Each gets its own soak row, and `kernsize` is quoted in bytes.
- **W3 — the player, fullscreen, CGA, silent.**
  - `apps/xdc/`, a new SPEC section.
  - PIT clock, streaming ring, Esc/Space, and XDC's end-of-play statistics
    (pauses, CPU idle, time in disk).
  - Gate: the guest's VRAM after frame *N* equals the host decoder's frame
    *N*, pixel for pixel, at several *N*, and a frame count against guest
    cycles proves the rate.
- **W4 — sound.** SOUND.DRV's `SND_OPENF_FRAME` (§34.5.x), then the player on
  it. Gate: one IRQ per frame, the audio bytes played equal
  frames × `achunk`, and no underrun across a 60 s synthetic stream from the
  hard disk.
- **W5 — surfaces.**
  - Hercules letterbox, VGA mode 6, and composite burst on CGA.
  - Composite in `VGA13` on the 286+ tier (a QEMU row, per docs/TESTING.md's
    list).
  - The Hercules 1.5× stretch as a measured option.
- **W6 — Preview.** The window, association (`OS88_ASSOC_EXT` for `XDO`), the
  Open dialog, the poster, the keyframe scrub bar, and the info panel with
  *this* disk's measured rate against the stream's.
- **W7 — In-window playback and seek.** Same-mode bracket, in-window row
  tables for all three desktops, pause back to Preview, and seek from the
  scrub bar.
- **W8 — the encoder, whole.** XDC's optimizer on the W0 cost model,
  `maxdiskrate=`, and XDC script compatibility.
- **W9 — Live windowed, RAM-resident clips.** Conditional on W0 and W6's
  numbers.
- **Field.** The owner's 5150 is the acceptance machine: BADAPPLE with sound
  from the ST-225, zero pauses, fullscreen and in-window.

## 9. What the bytes cost (estimates until built)

| where | what | bytes | resident? |
|---|---|---|---|
| kernel `.text` | `FSXF_RATE` in `sch_isr` / `fsx.inc` | 70–110 (+8 `.bss`) | **yes, every machine** |
| kernel `.cold` | `OSAPI_FILE_READ_SEQ` | 150–220 | **yes** (`.cold` is resident) |
| kernel `.text` | D4's fence | < 10 | yes |
| SOUND.DRV | `SND_OPENF_FRAME` | 150–250 | only while the driver is loaded |
| `apps/xdc/` | player: interpreter × surfaces, hooks, Preview, In-window | 6–10 KB image + ring claim | only while running |
| host | `os88xdv.py`, `os88xdc.py` | — | — |

**`kern_small`.** The player is a `kern_big` package first. `kern_small` has
§53 and could carry a fullscreen-only arm on its 128 KB floor machine with a
~40 KB ring. That needs `FSXF_RATE` and `READ_SEQ` to be on both kernels, and
the review should say whether they are.

## 10. For the review

1. **D1**: interpreted records (recommended) or executed XDC code. And is
   75% of the frame period the right gate for Wave 0?
2. **D2**: extend SOUND.DRV (recommended) or suspend it and drive the DSP
   from the player.
3. **D2**: is ~100 resident bytes for `FSXF_RATE` worth a general
   exact-rate PIT clock for every exclusive app?
4. **D3**: `READ_SEQ`'s caller-held cursor, or a different shape for the
   streaming read.
5. **D5**: are the three windowed tiers the right cut? Is In-window's
   even-rows-only on CGA acceptable?
6. The **names**: `.XDO` for the stream, `apps/xdc/` for the package, and
   what the dock calls it (*Video*?).
7. **Keyframe interval** default (2 s) and the poster rule.
8. Whether the original `.XDV` should be **associated** too, opening into a
   Preview that says "convert this on the host with `tools/os88xdv.py`"
   (a refusal with its reason), or left unassociated.
9. Whether the frame hook may ever run with interrupts **on**. Today's answer
   is no (D2): IRQ0 nesting into `sch_isr` could switch tasks on the
   interrupted stack. Wave 0 can measure what IF = 0 actually costs the
   keyboard and the serial mouse at 21 ms per worst frame.
