# SPEAKER-PCM-PLAN - PC speaker PCM for Audio, Tracker and the Video Player

**Status: PLAN, owner-approved 2026-09-28, nothing built yet.** Branch
`pcspeaker`, cut from `elendilon-next` at 00a4c8e. It answers
docs/plans/SPEAKER-PCM-HANDOFF.md's open questions (6) and replaces its
sections 4 and 5 as the brief; the handoff stays for its section 3, the
lessons the Video Player's wave paid for.

The owner's brief: *"extend [the Video Player's PWM] support to Tracker
and Audio ... an fsx imposter window mode like video player does, drawing
only updates to our own window. And full-screen mode for tracker (which
likely needs more than 4.77mhz?). 8khz seems to be optimal for a pc
speaker that a 5150 can actually run. Unlike video player we cannot
restrict what comes in as we are not the encoder. Look at what doing the
conversion up front on load would require, vs doing the translation on
the fly, and if it is even viable."*

## 1. Two corrections to the handoff

- Tracker's lowest rate is **5,500 Hz** (XT mode, `TRK_RATE_XT`), not
  11,000.
- Tracker's XT mixer has **no final pass**: channels add straight into
  `mp_outbuf`. The translation to counts goes where the output is copied
  into the speaker ring - which also keeps the scope (`tw_sccomp`) reading
  samples rather than pulse widths.

## 2. The finding that sets the design

On the owner's 5150 raw PCM through the speaker was *"the carrier and
nothing else"* (SPEC.md 98.2.15.1). It became listenable only after the
encoder SHAPED it: a high-pass and a treble tilt, a leveller, a drive into
a soft clip, and the carrier slid away in the quiet (98.2.15.3). So "we are
not the encoder" means **the shaping moves onto the machine**, not just the
conversion to counts.

## 3. The budget on a 4.77 MHz 5150

M = measured on MartyPC, E = estimated.

| | share |
|---|---|
| speaker at 8,000 Hz (`CYC_SPK_PULSE` 449 a pulse) | ~75% (M-derived) |
| speaker at 5,512 Hz | ~52% (M) |
| Tracker's mixer, 4 channels, 5,500 Hz | 35% (M, PERFORMANCE.md Set 21) |
| Tracker's mixer at 8,000 Hz | ~51% (E, linear in the rate) |
| a byte through a table in the producer | ~50 cycles, ~8% at 8 kHz (M) |

- **Tracker at 8 kHz**: 75 + 51 + 8 = ~134%. At 5.5 kHz ~93% before the
  sequencer, the kernel and any display. **Not viable on a 4.77 MHz 8088**;
  ~89% on the 7.16 MHz turbo XT (marginal); fine on a 10 MHz XT or a 286.
- **Audio, PCM8**: ~85-90% at 8 kHz - viable, tight. 22,050 Hz played at
  7,350 (three averaged) the same. 44,100 on an 8088 is refused (44 KB/s of
  disk plus the decimation).
- **Audio, IMA ADPCM 11 kHz**: decode ~13% (E, SPEC.md 86.4) at the SOURCE
  rate, so at 8 kHz ~93% - not viable; at 5,512 ~69% - viable with the
  5.5 kHz whine.

## 4. Up front, or on the fly

**A whole conversion up front is not viable as the default.** Counts at 8
kHz are 8 KB a second: a 3-minute song is 1.4 MB, which is neither in 640 KB
nor on a floppy. Rendering to a hard disk works, and is the last wave (8.W5)
- offered by Tracker AFTER its refusal, never as the way it plays.

**What is viable is splitting the shaping by what it IS:**

| shaping (98.2.15.1) | on the machine | Tracker | Audio / Video |
|---|---|---|---|
| high-pass + tilt (linear) | a first-order pre-emphasis, shifts only | UP FRONT: on the instrument samples at load. A linear filter commutes with the mix; ~1 s for 116 KB (E), nothing at play | per sample, on the fly |
| the leveller | a gain chosen per block (~32 ms) from the level measured in the block before | per block | per block |
| drive, soft clip, the carrier put away in the quiet, the count | ONE table family (16 levels x 256) plus a per-block centre shift | the lookup the ring needs anyway | same |

So one table lookup a sample does gain, clip and count, and one subtract
does the carrier's slide. `tools/os88spkfx.py` is the reference: it models
the integer shaper exactly (the gates compare the machine's port writes
against it), writes preview WAVs through `os88vid.spk_preview`, and - the
owner's question 6, NOW - shapes a WAV on the host with the encoder's full
shaper, marked so Audio copies it rather than shaping it again.

**Resampling** (Audio): an integer ratio is a box average (a cheap
anti-alias) - 16,000/32,000 to 8,000, 22,050/44,100 to 7,350, 24,000 to
8,000; 11,025 to 8,000 by stepping. Tracker's mixer simply runs at the
speaker's rate. On a 286 or better the rate goes UP (owner, question 4):
the source's own rate when it is 24,858 or under, else the largest integer
decimation under it - a pulse of 48 counts or more (SPEC.md 34.11.8).

## 5. A speaker play (both packages)

- **An `FSXF_RATE` bracket whose BODY does the work** - mix or decode, shape,
  fill the ring, draw, poll. No worker: under a sample ISR switches ride the
  18.2 Hz tick and a yield is ~2,200 cycles at IF = 0 (34.11.3). The Video
  Player plays the same way.
- **The imposter window**: a same-mode bracket (53.7) - the desktop frozen,
  the pointer gone, only the window's live parts drawn (Audio's time and
  bar, Tracker's position readout). Play shows Pause before entry; a click
  or Space pauses back to the desktop; Esc stops; F (Tracker) takes the full
  screen.
- **Tracker's full screen** keeps its text and FT2 surfaces, its bracket
  `FSXF_RATE` instead of `KEEPWORKER|FASTTICK`, its mixing moved into
  `trk_fsx_main`'s loop.
- **At 8 kHz a sample is ~596 cycles**, not the 864 the Video Player was
  measured at: any kernel drawing slot that holds IF = 0 longer loses a
  pulse. Measured before building on it; where one does, its few bytes are
  written directly (`vp_wmove`'s precedent).
- **Audio enters it AUTOMATICALLY** (owner, question 1: *"Sound and nothing
  else is better than no sound"*) when there is no `SND_CAP_PCM_BG`.
- **Tracker's gate is a live calibration** (question 5): the pre-roll it
  already mixes is timed, and mixer + speaker + overhead predicted; over the
  line it REFUSES with the numbers and an override (question 2), and then
  offers the render to disk (W5).

## 6. Owner decisions (2026-09-28)

1. Audio: automatically. *"Sound and nothing else is better than no sound."*
2. Tracker on a 4.77 MHz 8088: refuse with an override; a render to disk
   offered after the refusal, the LAST thing implemented.
3. ADPCM on an 8088: 5.5 kHz only if it is viable. *"Bad sound is better
   than none."*
4. 286 and up: the higher rates; real hardware confirms them.
5. Live calibration, if the measurement runs quickly.
6. The host tool for pre-shaped WAVs: now.
7. The Video Player adopts the shaping for clips not made for the speaker.

## 7. Costs

Kernel: **zero bytes** expected - the door (`OSAPI_FSX_SPK`) and `FSXF_RATE`
exist on `kern_big`; `kern_small` refuses the door, and neither package
ships on the small disks. Packages: the library (~480) and the shaper, plus
each package's bracket, ~1.5-2.5 KB each (E); the table family in bss or a
claim.

## 8. Waves

- **W0** measure and model: `tools/os88spkfx.py`; Tracker's mixer at 8 kHz
  under the speaker on MartyPC's 5150 and turbo; which drawing slots lose
  pulses at 8 kHz. No shipped bytes.
- **W1** `apps/os88spkfx.inc`, the shaper, exact against the model.
- **W2** Audio: listen mode in the imposter window, the resampler, the
  playlist playing on inside the bracket. **W2b** the Video Player shapes a
  card clip on the speaker.
- **W3** Tracker: the bracket body mixes, samples pre-emphasised at load,
  the imposter window, the full screen, the calibration.
- **W4** SPEC.md (34.11.5, 45, 86, 98.3.15), this file to `completed/`, the
  field listens.
- **W5** Tracker's render to disk, offered after the refusal.

Gates copy `tests/vidspk.py`: 800 port-42h writes against the model's
counts in order, the lost share, the play's time, the kernel clean, the
route obeyed - each broken on purpose once. Audio is timed on the card-less
MartyPC 5150; Tracker's function on QEMU's 386, its timing only in the
field (nothing here times a 286).
