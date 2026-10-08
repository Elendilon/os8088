# A stream's read-ahead in XMS — what it buys, what it costs a 286

**Status: INVESTIGATION. Nothing in the player or the encoder is built.**
What exists is the instrument that produced every number below
(`tools/os88vidbuf.py`) and the field row that measures the one number it
cannot compute (VIDDISK's `X`, `tests/vidbench/viddisk.asm`). Section 9 is
the build, in waves, for whoever takes it.

**The answer in four lines:**

1. **The player cannot use XMS for these clips today.** SPEC.md 98.3.18's
   hold takes a file only when the WHOLE file fits the pool, and the two
   clips are 36 MB and 75 MB. A 286 has 15 MB of address above 1 MB at most.
2. **A bank — a FIFO of chunks in XMS, ahead of the ring — takes a clip's
   disk requirement from its PEAKS down to its MEAN, and no further without a
   wait.** For the lossless 320 x 240 clip: 458 KB/s with the ring alone, 348
   with 4 MB banked, the clip's own mean being 363. Below the mean only a
   prefill buys anything, at about a second of waiting per 30 KB/s saved:
   285 KB/s with an 8 MB bank filled for 30 s before the first frame.
3. **On a 286 the bank costs CPU, and that is the whole risk.** Every banked
   byte crosses `int 15h AH=87h` twice (section 4.2 is why it cannot be
   once), and almost every byte of a busy clip is banked (87-98% in every
   model run). At an ESTIMATED 0.25 ms a KB the bank pays for itself; at
   1 ms a KB the copies make the 286 CPU-bound and **the play is worse with
   XMS than without it**. Which side a real 286 BIOS is on is unmeasured,
   and VIDDISK `X` is the row that measures it.
4. **The bigger lever is the ENCODER**, told about the bank: the same clip
   encoded at 250 KB/s must leave out 32% of what a lossless encode wants
   with today's ring, 20% with a 4 MB bank and a 17 s prefill, 7.8% with
   8 MB and 33 s (section 3.3). That is how a file gets *closer to a period
   disk*; the player change is what lets such a file play.

## 1. The two clips

Both are the Last Exile opening, `MODEX` VGA8 320 x 240 at 24 fps, 93 s,
made by `os88venc.py` (their options blocks say so, SPEC.md 98.1.1.4):

| | `05-320FS.V88` | `08-486.V88` |
|---|---|---|
| profile | `lossless` | `486`, `--frame-cap 63.5` (BIGSP) |
| sound | PCM8 11,025 Hz | PCM8 22,050 Hz |
| stream | 33.0 MB, mean **363 KB/s** | 70.4 MB, mean **780 KB/s** |
| a second's bytes: p10 / median / p90 / max | 172 / 374 / 514 / 613 KB | 455 / 797 / 1,062 / 1,272 KB |
| 5 s means, KB/s | 225 253 511 362 293 379 430 328 458 248 420 409 353 500 411 412 318 284 151 | 479 563 1083 768 638 795 852 715 970 574 921 881 776 1006 872 901 683 626 307 |
| decode, share of a period | 286-vga: median 40%, p90 67%, max 82% | 486: 29% / 50% / 65% (286: 86% / 139% / 180% - not a 286 file) |

**What matters is the median against the mean: 374 against 363, 797 against
780.** These clips are not "slow parts and fast parts" in the sense a bank
exploits - they are fast almost all the way through, with one quiet stretch
at each end. A bank smooths a clip down to its mean; it cannot take a clip
whose mean IS its typical second much below that.

## 2. What exists, and why it never engages here

SPEC.md 98.3.18 holds a streamed file in XMS **whole**: `vp_xopen` asks the
file's size and `OSAPI_XMEM_CAPS`, and takes the hold only if the pool
covers the file. It then fills from the front - the window's timer while
nothing plays (`vp_xstep`), and behind the stream while it plays
(`vp_xput`) - and every read the hold can answer is a copy (`vp_xfill`,
`vp_xrdat`). What it buys is a second pass with no disk at all: a seek, a
Repeat's lap, the next play, Live (98.3.18.1).

It is the right design for a clip that fits, and it is most of the
machinery a bank needs (section 4.1). But it is all-or-nothing: a 36 MB
file on a 4 MB pool takes no hold, and the play is the ring's.

## 3. What a bank would buy - the measurements

### 3.1 The instrument

`tools/os88vidbuf.py CLIP.V88 --minrate` plays the clip's real super-packets
through a model of the player's reader on a model of the machine, a
millisecond at a time, and bisects the slowest DISK it plays on:

- **the player**: a ring of K = 10 slots (a 640 KB VGA machine with a card,
  98.3), `vp_fill`'s rule - chunk *c* may load while *c* < the hook's
  super-packet's chunk + K - and a super-packet drawable once every chunk it
  touches is in. With `--xms N`, an N KB FIFO ahead of the ring with section
  4's policy. The play starts when the ring and the bank are full, or at
  `--wait` seconds;
- **the machine**: the hook first - each frame's decode at the profile's own
  measured cost (`os88venc.profile_table`, SPEC.md 98.2.3.3) - and the reader
  gets the rest. A disk chunk takes the media's time and, on a controller the
  CPU copies (every AT controller, IDE and MFM alike), the profile's CPU per
  KB (`--pio`: 1 / VIDDISK's idle row, 0.759 ms/KB on `286-vga`, which its
  25/50/75% rows bear out to within 5%). An XMS copy is CPU alone
  (`--xcopy`). `--dcache` is what the DRIVE reads ahead while the CPU is
  decoding: 0 for an MFM drive, which loses the turn; 64 KB here, for the
  IDE drives and CF cards that period machines are run with now;
- **a stall** is a due frame whose super-packet is not in; a play passes if
  its stalls total under 0.1 s (`--tol`).

**Calibration**: with the bank off and the CPU taken out, the model's
answer for `05-320FS` (458 KB/s) is exactly a plain bandwidth calculation's,
and on the owner's 86Box `286-vga` (an IDE disk the CPU copies at 1,318 KB/s
idle) it says the lossless clip plays with 0.01 s of stalls - the profile's
own note says *"the owner's lossless Last Exile, which plays on this
machine with nothing late"* (with no drive cache, so the model's harsher
case).

### 3.2 The player: the slowest disk that plays, KB/s

`05-320FS` on `286-vga` (drive cache 64 KB; the XMS copy ESTIMATED at three
costs because nobody has measured one on a 286):

| bank | 0.25 ms/KB copy | 0.40 ms/KB | 1.0 ms/KB | prefill (at that disk) |
|---|---|---|---|---|
| none (today) | **458** | 458 | 458 | 0.7 s |
| 1 MB | 407 | 430 | CPU-bound: stalls 0.2 s at ANY disk | 3 s |
| 2 MB | 387 | 430 | stalls 0.2 s | 6 s |
| 4 MB | **348** | 410 | stalls 0.3 s | 11-13 s |
| 8 MB | 285 | 310 | stalls 0.4 s | 28-30 s |
| 15 MB | 197 | 204 | stalls 0.6 s | 77-80 s |
| 8 or 15 MB, prefill held to 10 s | 346 | 390 | - | 10 s |

`08-486` on `486` (copy 0.05 ms/KB, unreal mode - SPEC.md 41.4):

| bank | slowest disk | prefill |
|---|---|---|
| none (today) | **1,078** | 0.3 s |
| 1 MB | 865 | 1.6 s |
| 4 MB | **780** | 5.7 s |
| 8 MB | 722 | 11.8 s |
| 15 MB | 627 | 25 s |
| 15 MB, prefill held to 10 s | 712 | 10 s |

With **no drive cache** (an MFM drive, or a model of one), the CPU-copied
disk loses every turn a frame's decode holds the CPU, and the 286's ring
needs 1,192 KB/s of media for the same clip; a 4 MB bank brings that to
804-973. The cache is the difference between "a disk the CPU copies" and "a
disk that waits for the CPU", and a real drive is somewhere between.

What the tables say:
- **A bank of 1-4 MB is worth 10-25% of disk rate** to these clips, and its
  prefill is seconds. Every MB past that is mostly bought with waiting.
- **"Buffer the whole of RAM, then spend it down" works, at the rate the
  arithmetic says**: to play at rate R below a clip's mean M for T seconds,
  the bank must hold at least (M - R) x T before the first frame.
  `05-320FS` at 285 KB/s: (363 - 285) x 93 = 7.1 MB, against the 8 MB the
  model needed - a clip's bytes do not arrive evenly, so the bank must also
  cover the worst stretch on the way.
- **The 286's copy cost decides whether the bank helps at all.** 0.40 ms/KB
  - ~2.5 MB/s, a 12 MHz 286 doing `rep movsw` with one wait state plus a
  reset - and the 4 MB bank buys 48 KB/s where at 0.25 it buys 110. At 1
  ms/KB it costs more than it buys.

### 3.2.1 The number nobody has: VIDDISK `X`

`int 15h AH=87h` on a 286 enters protected mode, copies, and gets back to
real mode by RESETTING THE CPU (through the 8042 or a triple fault - the
286 has no way back otherwise), and the BIOS's shutdown path runs on the
way. What that costs a call is a property of the BIOS and the board, and it
is not in any document in this tree. QEMU cannot say (it has no 286, and
times nothing); MartyPC is an 8088.

So VIDDISK grew an `X` key. It reports, on the machine it runs on:
- the CPU tier and the pool's free KB;
- **a 32 KB round trip, checked byte for byte** - a copy that times well and
  moves the wrong bytes is not a measurement, and the row was verified to go
  `BAD` with the copy back aimed at the wrong half;
- `OSAPI_XMEM_COPY` up and down at **32, 16, 8 and 4 KB a call**, PIT-timed
  with the copy inside the span - which splits a call's cost into its fixed
  part (the reset) and its bytes, and gives the interrupts-off window per
  piece size (on tier 1 all of the call is masked);
- **the bank filling**: 5 s of 32 KB `READ_SEQ` alone, then 5 s of the same
  with every chunk copied up - KB/s x 10, the two rows' ratio being what
  banking a byte costs over reading it.

Measured on QEMU, tier 2 (the mechanism, not a timing - QEMU's times are
the host's): the check `ok`, every row reporting, the block freed, and with
`-m 1` the run says `NO EXTENDED MEMORY` and stops. **What it needs is a run
on the owner's 286 and 486** (`tests/vidbench/FIELDDISK.TXT` says how); its
`XMS up 32K` row divided by 32,000 is `--xcopy` in ms/KB.

### 3.3 The encoder: what a bank lets a period-rate encode keep

`os88vidbuf.py --deficit R ...` takes the lossless file's own super-packets
as what an encode WANTS, runs the encoder's disk bucket (`Budget`,
`os88venc.py`) at R as deep as the read-ahead is, and sums the bytes it
could not send: the share of the picture an encode at R must leave out,
before later frames repair it. It is a proxy - a real encode chooses WHICH
bytes go (98.2.1, best first) and its error as seen is far smaller than the
share - but it ranks the configurations, and it is free.

`05-320FS` (the bucket is the ring less two slots, 256 KB, plus the bank;
"half / full" is the bucket started half full - today's assumption - or
full, which is the prefill, with that prefill's wait):

| R KB/s | ring | +1 MB | +4 MB | +8 MB | +15 MB |
|---|---|---|---|---|---|
| 150 | 58.6% | 57.0 / 55.5%, 8 s | 52.5 / 46.4%, 29 s | 46.4 / 34.3%, 56 s | 35.8 / 13.0%, 104 s |
| 200 | 45.1% | 43.4 / 42.0%, 6 s | 38.9 / 32.9%, 21 s | 32.8 / 20.8%, 42 s | 22.2 / 0.0%, 78 s |
| **250** | **32.2%** | 29.9 / 29.0%, 5 s | 25.3 / **19.9%**, 17 s | 19.3 / **7.8%**, 33 s | 8.6 / 0.0%, 62 s |
| 300 | 21.0% | 16.6 / 16.6%, 4 s | 11.9 / 7.5%, 14 s | 5.8 / 0.0%, 28 s | 0 / 0, 52 s |
| 400 | 4.7% | 0 / 0, 3 s | 0 | 0 | 0 |

`08-486` at the rates a 486 IDE of the period streams: at 600 KB/s, 26.4%
with the ring, 18.9% with 4 MB (7 s), 13.2% with 8 MB (14 s), 3.2% with 15
MB (26 s); at 800, 9.2% with the ring and nothing from 4 MB up.

**This is the lever the request is really about.** A file made for a 250
KB/s disk with an 8 MB bank and a 33 s prefill is within 8% of lossless
where today's is 32% short. The player change in section 4 is what lets such
a file play; the encoder change in section 5 is what makes it.

## 4. The player: a BANK, when the file does not fit

### 4.1 The shape

When `vp_xopen` finds the pool smaller than the file, it takes the largest
block it can (section 4.6) as a **bank: a FIFO of 32 KB chunks ahead of the
ring**, addressed by chunk number mod its size. Its state is three words:
the chunk at its head (the ring's next), the chunk at its tail, and its
size. The ring's rule is unchanged, and so is everything past it.

The reader (`vp_fill`, the bracket's foreground) does, in order:
1. **the ring has room and the bank has its next chunk**: copy it DOWN
   (`vp_xcopy`, DI = 1) into the slot, and the mirror after it as today;
2. **the ring has room and the bank is empty**: read the disk STRAIGHT into
   the slot, as today - no copy at all. This is what keeps a bank from
   costing a byte read while the disk is keeping up;
3. **the ring is full and the bank has room**: read the next chunk into a
   bounce claim on the BANK'S OWN cursor and copy it UP - `vp_xstep`'s body,
   run from the bracket's loop rather than the window's timer;
4. else nothing: wait a period, as today.

**Two cursors, handed over, never re-seeded.** The stream's cursor
(`[vp_cur]`) and the bank's (`[vp_xcur]`) both read the same file forward.
Step 3 advances the bank's; step 1 advances only the head. When the bank
empties, step 2 takes over **with the bank's cursor copied into the
stream's** - the FSEQ block is the state of a forward read, and copying it
is free. `vp_xfill` today zeroes the stream's cursor "but for FSEQ_OFF" so a
later disk read seeds again from the name (SPEC.md 18.4.8) - affordable
once a play for a hold, and NOT for a bank, which empties and refills many
times a play: a seed walks the chain from the front (98.1's 142 ms a MB on
the W0 machine, a 5150), which at 50 MB into `08-486` would be seconds of
disk on any machine.

**A pause fills the bank for nothing.** While paused (98.3.4) the reader's
loop runs and the hook draws nothing, so step 3 has the whole machine: on
the owner's 286 (1,318 KB/s idle, and a copy ESTIMATED at 0.40 ms/KB) ten
seconds paused is ~8.6 MB banked.

### 4.2 Why a banked byte is copied twice, and it cannot be once

The ring is contiguous in stream order - a super-packet straddling two slots
is contiguous in memory because slot *c* + 1 IS chunk *c* + 1, and the
mirror is that rule at the wrap (98.3). So the chunk a freed slot takes must
be the stream's next, and while the bank holds anything, the bank holds it.
A chunk the disk reads while the bank is non-empty therefore goes to the
bank's tail (up) and comes down later (down). Breaking that would mean a
chunk-to-slot map and a straddle the ring can no longer make contiguous -
every super-packet decode would change. **So a byte is banked only if the
bank was non-empty when the disk read it**, and that is nearly every byte of
a clip that keeps the bank in use: 87-98% in every run of section 3.2.

What it costs: one disk read and two copies a banked byte, where a direct
one is the read alone. The two copies fall at different times - UP when the
ring is full, which is when the decode has left CPU over; DOWN when a burst
is spending the bank, which is when the CPU is scarce - but a copy down is
cheaper than the disk read it replaces on a CPU-copied disk (0.25-0.40
ms/KB against 0.76), which is why the 286 still gains.

### 4.3 The prefill

A play that has a bank fills it before the first frame - the request's
"buffer the full ram at the start of play". The full screen says
**`Buffering 1,234 of 8,192 KB`** (98.3.13's box), updated a chunk at a
time; **Space starts the play at once** with what is in; Esc cancels. How
much is filled:
- the header's ask (section 5), if it has one: a file encoded for an 8 MB
  bank and a full prefill is short exactly where it was banked, and the
  player says `Low memory` (98.3) if its bank is smaller;
- otherwise the whole bank, or 10 s, whichever comes first - an unbudgeted
  file gains from a bank's smoothing (section 3.2) without asking anybody to
  wait a minute.

In the window (98.3.7) the same loop runs and the box says it.

### 4.4 What else a bank meets

- **A seek** (98.3.14) inside the banked range moves the head; outside it,
  flushes the bank and seeds the stream's cursor as today. Seeking back is
  the disk's.
- **Repeat** (98.3.9): the seam's read is the disk's, and the bank is
  flushed at the lap; the next lap's first chunks refill it.
- **F and Esc, brackets ending and starting**: the bank outlives a bracket
  as the ring does not - a play stopped and played again from the same
  key keeps what is banked.
- **Live** (98.3.10) is not a bank's: it plays from a whole hold or not at
  all, and keeps doing so.
- **A file that fits** keeps SPEC.md 98.3.18's hold, unchanged: the hold is
  strictly better where it is possible.

### 4.5 The 286's own problems

- **The interrupts-off window.** On tier 1 the whole copy is masked
  (`int 15h AH=87h`). At 0.25-1.0 ms/KB a 32 KB piece is 8-32 ms, and the
  rate hook - every 20.8 ms with a card (98.3.1) - waits it out. The hook
  draws an owed frame on its next call, so a late call is absorbed unless the
  frame was already near its period; the Sound Blaster's DMA does not stop,
  but its block interrupt waits too, and a 512-byte block at 22 kHz is
  23 ms. **The piece size is a measured choice**: VIDDISK `X` gives the
  fixed cost at 4-32 KB, and the bank copies in the largest piece whose
  window is under half a block.
- **Calibrate, don't guess** (SPEC.md 47). The player times its first bank
  copy with the PIT (benchlib's method, a dozen instructions) and refuses the
  bank - saying so on the card - where a KB costs more than the disk read it
  replaces, which is the line section 3.2 puts the 1 ms/KB column on the
  wrong side of. An unbudgeted file then plays as it does today; a file
  encoded for a bank plays with `Low memory`.
- **The worker rule.** `OSAPI_XMEM_COPY` is UI-task only (SPEC.md 41.8): the
  bracket's foreground is the UI task, which is where the copies already
  are; the hook never touches the bank.

### 4.6 How big

The pool is shared (eight blocks, SPEC.md 41.5) and other programs use it,
so the bank asks for what is free less a reserve - 256 KB, enough for a
clone's round (18.99.4) - and no more than the file. It is freed when the
file closes, and the kernel frees it with the instance.

### 4.7 What it costs

**No kernel byte.** `VIDEO.O88`: the bank's three words, the policy in
`vp_fill` (step 1 is `vp_xfill` with a modular address; step 2 is today's
path; step 3 is `vp_xstep`'s body), the cursor hand-over, the prefill's
loop and line, the calibration, the flush on seek and lap - ESTIMATED at
400-600 bytes against 98.3.18's measured 955 for the hold.

## 5. The encoder and the file

- **`--xms KB`** deepens the disk bucket by that much (`Encoder.reserve`,
  98.2.1.3), the way `--memory` sizes the ring; **`--prefill S`** starts it
  that many seconds of disk fuller, up to its depth, where it starts half
  full today ("the player fills its ring before the first frame").
- **The header says so.** A flag (1024, XBANK) and two words in the header's
  zero tail at 472 (98.1.1): the bank's KB and the prefill's. A player
  that knows the flag prefills that much and says `Low memory` with less; an
  older player REFUSES it at open, as it refuses every flag it does not
  know - which is the convention (98.1.4.1's BIGSP), and is right here too:
  a file banked for 8 MB on a player with none stalls from its first burst.
- **A profile for a bank is a VIDDISK `X` reading.** `disk_at` is already
  the disk's rate under load (98.2.1.3); a bank's refill is the `READ_SEQ +
  copy up` row, so a `286-vga-xms` profile is that row in place of the
  `READ_SEQ` one, and the encoder needs nothing else to price it.
- The window (98.2.8) gets the two boxes beside `--memory`'s.

## 6. Is this a bad example?

**It is a hard one, and a fair one.** A bank is worth what a clip's calm
stretches save for its bursts, and Last Exile's opening has few: its typical
second is its mean. Two consequences:
- these clips gain 10-25% from a bank of a few MB, and the rest only by
  waiting. A clip that is mostly talking heads, credits and slow pans, with a
  few fast cuts, would gain several times more for the same bank - its mean
  is far below its peaks, which is exactly the gap a bank closes;
- for a VGA DEMO video the wait may be the right trade: a 30 s "Buffering"
  in front of 93 s of near-lossless video off a 285 KB/s disk is a demo a
  period 286 with 8 MB could show.

**The original video would help, and is not needed for the design.**
Section 3.3's deficit is a proxy; with the source, the same clip can be
encoded at 250 KB/s with each bank size and its error AS SEEN read off the
encoder's own summary - the number the window shows - instead of a share of
bytes. That is the measurement to take before section 5 is built.

## 7. Considered and not proposed

- **EMS instead of XMS.** LIM EMS maps 16 KB pages into a frame below 1 MB
  with a few OUTs, so the ring could BE expanded memory and nothing would
  be copied at all - the period answer, and the one an 8088 with an Above
  Board or a Lo-tech EMS card could use too. os8088 has no EMS support of
  any kind (no driver, no slot, no emulator profile here carries a card),
  so it is a project of its own; worth knowing it exists if section 3.2.1's
  reading comes back at 1 ms/KB.
- **LOADALL for the 286 copy** (HIMEM.SYS's trick: no reset). Undocumented,
  286-only, and the kernel's transport, not the player's (SPEC.md 41.9).
- **Keeping what has been played**, as the hold does: a bank that kept its
  past would serve seeks back, but it is the same bytes spent on the
  direction the play does not go.

## 8. Open questions for the owner

1. **VIDDISK `X` on the 286 and the 486** - the whole of section 3.2's 286
   column, and the bank's piece size.
2. **The prefill**: a fixed cap (10 s?), the header's ask only, or both as
   section 4.3 has it.
3. **The format**: refuse on an older player (the convention), or put the
   two words in the zero tail with no flag so an older player plays a
   banked file and stalls in its bursts.
4. **The original video**, for section 6's real encodes.

## 9. Waves

0. **Measure** (this document): VIDDISK `X` on the 286 and the 486, and the
   source re-encoded at a period rate per bank size.
1. **The bank in the full-screen play**: section 4.1-4.2, 4.5, 4.6 - a
   file that does not fit plays with a bank, smoothing only (no header ask);
   the gate is `vidxms`'s shape on QEMU with a pool smaller than the clip
   (`-m 4` against a 6 MB clip): B: swapped BLANK after the prefill, and the
   play must reach the frames the bank held and stall exactly where it ran
   out - and with the bank's step 1 taken out, it must stall at once.
2. **The prefill and its line**, Space and Esc during it.
3. **The encoder's `--xms` / `--prefill` and the header**, the player's ask,
   `Low memory`; `tools/os88vidbuf.py --deficit` checked against a real
   encode's cuts.
4. **The window play, seeks inside the bank, a pause's banking.**
