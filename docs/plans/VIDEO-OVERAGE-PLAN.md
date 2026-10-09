# Banking only the overage — what it would buy over the bank we have

**Status: INVESTIGATION (2026-10-09). One finding is BUILT** - the
encoder's charge for the bank's copies, section 3.2 - **and the rest is a
design and its arithmetic.** It follows docs/plans/VIDEO-XMS-PLAN.md, whose
waves 1-4 and E1-E3 are built (SPEC.md 98.3.18.2-98.3.18.7).

**The owner's question** (paraphrased): instead of cutting, put only the
OVERAGE - the bytes a disk at 448 KB/s and a 192 KB ring cannot carry - in
XMS or EMS. Load the early overages in the prefill, load later ones while
the disk has time to spare, and spend them as the bursts come.

## 1. The answer in five lines

1. **In BYTES it carries nothing the bank does not already carry.** A single
   sequential disk read in decode order with a bounded buffer is already the
   optimum (section 2). What a FIFO bank holds and what an overage store
   would hold are the same number of bytes at every instant.
2. **What it changes is which bytes pay for passing through the bank** - and
   on a 286's XMS that is real money: every byte that passes costs two
   `int 15h` copies with interrupts off. A FIFO bank passes EVERY byte while
   it holds anything; an overage store passes only the overage.
3. **Half of that was a modelling error, and it is FIXED.** The encoder
   charged the bank's copies on every byte of the play; the player only
   copies while the bank holds something. Charged as the player behaves, the
   same 3 MB bank filled first goes from **3.27% to 2.95%** error as seen,
   and a bank barely prefilled stops being WORSE than no bank (section 3).
4. **On EMS in place (98.3.18.7) there is no copy to save**, so the overage
   format buys nothing there but its fallback.
5. **What the format would buy that nothing else can is the FALLBACK**: a
   base stream any machine plays without a stall, and an enhancement a
   machine with a bank adds. Today a file made `--bank` plays on a machine
   without one and PAUSES in its bursts. That, and the 286's remaining copy
   traffic, are the case for building it (section 4), and it is several
   major changes.

## 2. Why the bank is already the optimum in bytes

Let D(t) be the bytes the disk has read by time t and S(t) the bytes the
decoder has consumed. Whatever ORDER bytes are read in, the bytes held in
memory are D(t) - S(t), and memory bounds it: D - S <= ring + bank. The
disk bounds D' <= its rate. A play does not stall while D(t) >= S(t) for the
bytes each frame needs. Reading in decode order is earliest-deadline-first,
and for a single resource with a bounded buffer EDF meets every deadline any
order can. So moving the overage elsewhere in the file - or into a region of
its own - cannot let a given disk and a given bank carry one more byte.

The encoder's `--bank` (98.2.1.3.2) is exactly that model: a token bucket of
depth ring + bank, refilled at the disk's rate, started fuller by the
prefill, and a frame is cut only when the bucket cannot pay for it. "Push the
overage into the bigger RAM instead of cutting" is what the deeper bucket
does: a byte is cut only when no amount of read-ahead within that RAM could
have brought it in time.

**Two consequences worth keeping:**
- **The prefill is the only lever on a clip with no calm stretches.** If the
  disk never outruns the stream during the play, nothing refills the bank,
  and what the bank holds at the start is all it ever gives (section 3.1).
- **The ideal prefill is computable.** The least initial level that leaves
  the bucket above zero is the largest cumulative deficit (want - disk)
  over any prefix. The encoder could write THAT as the file's prefill
  (`--prefill auto`, section 5) instead of the owner's default of 10 s.

## 3. Measured: Last Exile's opening, 30 s of it

`--preset vga8 --profile 286-pvga --disk 204800 --start 20 --end 50`: the
owner's 286 with a disk at 200 KB/s. "Error" is the encoder's error as
seen; "cut" the frames the disk cut.

### 3.1 The bank's whole benefit here is its prefill

With the bank 3 MB and only the prefill varied (the encoder as it shipped
in 98.2.1.3.2):

| prefill | cut by the disk | error |
|---|---|---|
| no bank | 611 | 3.81% |
| 0.5 s | 624 | **4.22%** |
| 3 s | 586 | 3.99% |
| 6 s | 524 | 3.79% |
| 9 s | 451 | 3.65% |
| 12 s | 398 | 3.49% |
| all (15 s) | 348 | 3.27% |

Linear: about 0.2 points of error per 3 s of prefill, because this clip has
no calm for the bank to refill in. And at 0.5 s the bank was WORSE than none,
which is section 3.2.

### 3.2 The encoder charged the copies on every byte - FIXED

98.2.1.3.2 charged the disk `1 + 2 x xcopy x rate` for the whole play: 12%
of a 200 KB/s disk on a 286. The player's FIFO hands the ring its chunks
through the bank only WHILE THE BANK HOLDS SOMETHING; empty, the disk reads
into the ring and nothing is copied. A bank that is prefilled a little and
never refilled is empty for nearly the whole play, so it was charged 12% for
copies that never happen. Now the charge applies only on frames where the
bucket stands above the ring's reserve - the bank's share of it - and the
same table (`os88venc.py`'s `Encoder._drate`):

| prefill | cut by the disk | error, before | error, now |
|---|---|---|---|
| no bank | 611 | 3.81% | 3.81% (byte-identical file) |
| 0.5 s | 605 | 4.22% | **3.75%** |
| 6 s | 509 | 3.79% | **3.37%** |
| all (15 s) | 338 | 3.27% | **2.95%** |

The no-bank file is byte-identical with the code before the change, and the
encoder is byte-identical run to run.

### 3.3 What the overage format would save on top

With the model fixed, the FIFO's remaining cost is that once the bank holds
anything, EVERY byte goes through it, base and overage alike: VIDEO-XMS-PLAN's
opening (its point 3) measured 87-98% of a busy clip's bytes banked. An overage
store copies only the overage. On this clip with 3 MB filled first the
overage is ~2.1 MB of a 10.4 MB play (the 'all' encode's bytes less the
no-bank encode's), so the copies fall to about a FIFTH:

| | bytes through XMS | copy time at 0.69 ms/KB (two copies) | interrupts off |
|---|---|---|---|
| FIFO bank, filled first | ~10.4 MB (nearly all) | ~7.0 s of 30 | ~23% of the play |
| overage store | ~2.1 MB | ~1.4 s of 30 | ~5% |

ESTIMATED, not measured: the bytes are the two encodes', the 0.69 ms/KB the
owner's 286 (VIDDISK `X`, 0.345 a copy). What the 5.6 s buys is disk time -
about 1.1 MB more at 200 KB/s, roughly another 5 s of prefill's worth by
section 3.1's slope - and it is also the speaker's clock (98.3.18.5, where
every copy loses samples) and the hook's latency. On EMS in place the FIFO
already copies nothing, so none of this applies there.

## 4. The design: a base stream and an enhancement

**The shape that makes it worth building is not "move the overage" but
LAYERS**, because a layered file is what gives the fallback:

- **The base stream** is the file's stream as today, encoded to the disk and
  the ring alone - what an encode with no `--bank` makes. Every player plays
  it, with no stall, at today's quality.
- **The enhancement** is a second region of the file: for each frame, the
  writes that take the screen from what the BASE leaves to what the full
  encode wanted. It is read into the bank - by the prefill first, then while
  the disk has time - and the hook applies a frame's enhancement records
  after its base record.
- **It is not just the cut bytes.** Base records are writes of new values,
  and the base encoder leaves a byte alone when ITS screen already holds the
  next value. An enhanced screen can differ there, so the enhancement must
  carry every byte where (enhanced screen + base record) differs from the
  frame - the encoder tracks the two screens, base and enhanced, and emits
  the difference. ESTIMATE: the cut bytes plus a share of divergence that a
  first build must measure; it could be large on noisy content.
- **Losing it degrades rather than breaks.** An enhancement missing (a bank
  short, a seek, a slow disk) means the play continues on the base from an
  ENHANCED screen, and the base's later writes repair it the way a cut frame
  is repaired today. A keyframe resynchronises both screens.

### 4.1 What it costs

| piece | where | the work |
|---|---|---|
| the region and its index | format (98.1) | a block per keyframe interval, located by a table like the keys'; older players never read it - **no flag needed**, the tail word at 474 rules |
| the encoder | `os88venc.py` | two screens, two buckets (the disk's for the base, the bank's for the enhancement), and the schedule that places enhancement blocks where the disk can fetch them |
| the reader | `video.asm` | a SECOND cursor on the region, and reads that alternate between the two places on the disk - a seek each switch, so it reads the region in big blocks (64 KB or more) in the calm, and never mid-burst |
| the hook | `video.asm` | after a frame's base record, its enhancement records out of the bank: through the frame on EMS, copied down on XMS - the only copies left |
| seeking | `video.asm` | the enhancement from a key onwards is the region's block for that key; until it is in, the play is base only |

Of these the encoder is the largest and the riskiest, the hook's change the
smallest. ESTIMATE: two to three waves of work the size of 98.3.18.2-4
together, and a format version in 98.1.

### 4.2 What it does NOT do

- **It does not beat the bank on bytes** (section 2). A clip that needs
  more than disk + bank + prefill still cuts; on Last Exile at 448 KB/s the
  next limit is the CPU, which neither scheme touches (SPEC.md 98.2.1.3.2's
  table: 407 frames cut by the CPU's average once the disk binds none).
- **It does not help EMS in place**, which already copies nothing - except
  for the fallback.
- **Repeat, BIGSP and sound ahead** would each need their answer again.

## 5. Recommended, in order

1. **Done: the copy charged only while the bank holds** (section 3.2). Every
   `--bank` encode improves; no file or player change.
2. **`--prefill auto`**: the encoder computes the least prefill that the
   bank can use - the largest cumulative deficit, capped at the bank - and
   writes it in KB. The player already reads that word. One pass over the
   bucket's history after the encode; no format change. Section 3.1 says
   the prefill IS the bank on a calm-less clip, so this is the knob that
   should not be a guess.
3. **The layered format** (section 4), if the fallback - one file that plays
   everywhere, better where there is a bank - is wanted, or if the 286's XMS
   copies (section 3.3) are measured to cost a real play. Its first wave is
   the encoder alone, which can report the enhancement's size on the
   owner's clips before a byte of the player is written.

## 6. Questions for the owner

1. Is the fallback worth a format change? A `--bank` file today plays
   without a bank and pauses in its bursts; a layered one would play at
   no-bank quality instead.
2. `--prefill auto` (5.2) as the default when `--bank` is given, in place of
   10 s?
3. The two-screen enhancement's size is the unknown that decides section 4;
   measure it first (an encoder-only wave) before deciding?
