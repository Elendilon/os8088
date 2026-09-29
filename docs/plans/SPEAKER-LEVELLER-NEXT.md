# The speaker's leveller: what is left, and how to go after it

**OPEN.** Written 2026-09-29, after five rounds of field listening, when the
owner asked for the remaining ideas to be written down before moving on - and
then, the same day, picked candidate 1 below as the next experiment. SPEC.md
34.11.9 is the contract for what ships; this is what might come after it, with
the measurements the choices were made on.

## 1. Where it stands

`apps/os88spkfx.inc` turns 8-bit PCM into pulse widths for the PC speaker, and
its leveller decides how loud each 256-sample span plays (512 above 11 kHz).
Four rounds of field listening on the owner's Toshiba T1100 Plus and 5150
shaped it:

| round | what was heard | what changed |
|---|---|---|
| 1 | "one volume, then super soft, then back a third of a second later" | a span after SILENCE takes its own level at once |
| 2 | ~50 ms "microdropouts" | the peak held over three spans |
| 3 | the steady low part moving with the punctuating hits | a HELD, DECAYING peak (re-armed within ~2.5 dB, 16 spans, then 1/16 a span) and a row that GLIDES a 2 dB step every 16 samples; `ZT` 2.0 -> 2.5 |
| 4 | "still some 'a loud thing happens, the soft thing goes away and fades back in', but cleaner" | chosen for the release |
| 5 | a second listener, side by side: round 3's fades out and back in are MORE obvious for being slower | round 3 REVERTED (a46deec); round 2's three-span hold ships |
| 6 | candidate 1 as a RATCHET: "basically completely fixes it - no more weird warbles, no more fades in after dropping out" | Tracker plays ONE level a song (324267f, SPEC.md 34.11.9.1) |
| 7 | a listening build with a hand on the level: 5 is the clearest on the T1100, up to 7 only louder, 10 blurs; on the 5150, 7 to 10 weakens the carrier's whine | the level SHIPS as Tracker's volume bar, and the rate as a menu (3b502c1, SPEC.md 45.25.3) |

Measured on 40 s captures (section 3), "wander" being the level's spread within
each second:

| song | shaper | wander | mean gain | at the curve's end |
|---|---|---|---|---|
| ELYSIUM.MOD | round 2 | 1.87 dB | 10.8 dB | 3.6% |
| | round 3 (reverted) | 0.65 dB | 10.4 dB | 3.5% |
| BEVERLY.MOD | round 2 | 2.21 dB | 10.3 dB | 2.9% |
| | round 3 (reverted) | 0.84 dB | 8.9 dB | 1.8% |

## 2. What is left, and why it is structural

**The gain is one number for the whole mix.** When a loud, infrequent part
arrives, the level has to come down or the part clips, and everything else in
the mix comes down with it. Round 3 made that happen less often and more
slowly, and round 5 is the lesson from it: **slower is not better, only
different.** One listener heard fewer, gentler movements; another heard the
same movements as longer, more obvious fades. Both were describing the same
defect - parts that should not change, changing - so the target is not a
better-shaped movement but NO movement where the music has none. A drum hit
still takes the bass line down with it. Every idea below either splits the
mix so the parts are levelled separately, or knows about the loud part before
it arrives - and candidate 1 does not move at all.

## 3. The instrument, so nobody re-derives it

Every candidate here was judged on the same two captures. That method is what
made four rounds possible without guessing, so it is worth keeping runnable:

- **Capture.** On MartyPC's 7.16 MHz XT (`os8088_xt_vga_hdd`, `--turbo`, which
  takes the 8,000 Hz rung), open Tracker on a module and set a breakpoint just
  after `tsp_fill`'s last `os88spkfx_emit`, at `tsp_fill.one + 3`, the
  `add [es:TSP_RL], bx`. At each stop read `mp_outbuf` (the mixed span, the
  shaper's input) and the span just written into the ring at TOTAL (its
  output). 40 s is 1,253 spans. `tests/trkspk.py`'s `Trk` class and
  `os88marty.bp_trace(..., on_hit=...)` are all it takes, and the dry-grant
  counter at `os88spk_grant.dry` rides along, so a capture also says the ring
  never starved.
- **Replay.** `tools/os88spkfx.py`'s `Shaper` reproduces the machine's output
  EXACTLY (all but the first span, whose state the capture joins mid-song).
  So a variant is a subclass of `Shaper` run over the captured inputs, no
  assembly needed, and only the winner is written in asm.
- **Metrics.** Wander (above); mean gain; the share of samples at the curve's
  end (hard-clipped); level travel in dB/s; V-dips (spans 4 dB or more below
  the level on both sides). The first two are loudness and steadiness, the
  third is what the hits cost, and the last two are what "hitch" meant.

**Both halves are in the tree**:

    python3 tools/os88spkcap.py apps/tracker/beverly.mod --secs 40
    python3 tools/os88spklev.py build/beverly.pkl [more.pkl] --fixed 3,5,7

`os88spkcap.py` takes any module and writes a `.pkl` of spans (build/ by
default). `os88spklev.py` first replays the capture through the model and
says whether it is still EXACT against the machine - seeded from the state
after the capture's first span, since the capture joins the song mid-way -
and then prints the table below for each variant: today's ratchet, the
per-span leveller it replaced, and any `--fixed` levels. A candidate is a
Shaper subclass added to its `VARIANTS`. Measured when they were committed
(2026-09-29, a 20 s BEVERLY.MOD capture on the current build): EXACT over
628 spans, and 494 of them DIFFER with the model's `RTOL` off by one, so the
first line does fail when the model drifts. A capture from an older build
will not replay EXACT - the family table has changed under it - so capture
again rather than trusting an old `.pkl`. The Elysium capture needs the
owner's `ELYSIUM.MOD`, which is not in the tree; BEVERLY.MOD is.

**Cost is the other half of every row.** `tests/spkfx.py` prints the shaper's
cycles a sample. Audio's live 8,000 Hz leg on a 5150 (`tests/apspk.py`,
`pcm8`) is the tightest budget in the family. A first cut of round 3 that
scanned a 16-byte window every span cost it 13 more dry grants in 5 s, and the
constant-work hold that replaced it cost none, so read that leg's dry count
for any change here.

## 4. The candidates, most promising first

1. **A static gain for Tracker, from a pre-pass at load. THE NEXT
   EXPERIMENT** (the owner, 2026-09-29: "the problem are all the changes and
   the fading of things that shouldn't change, so this seems like it has
   promise").

   **SHIPPED, as a RATCHET rather than a pre-pass, and with the user's hand
   on it** (SPEC.md 34.11.9.1 and 45.25.3). The volume bar, `+` and `-` are
   the level with no card: the ratchet picks it and the bar shows it, and
   the first move makes it the user's for the session. What is still open
   of this candidate is the pre-pass below, for the quiet intro.

   The first cut (`TSP_RATCHET`): the level starts at `TSP_LSTART` = 8 and only
   ever steps down, for a span that overdrives it by more than 3 levels, so
   it finds the song's loud parts in its first seconds and then holds -
   ELYSIUM settles on 6 in 1.5 s, BEVERLY on 5 in 2.4 s. No pattern walk is
   needed, and a song whose loudest part comes late steps down once when it
   arrives. The pre-pass below is still the way to remove even that one step
   and the too-loud opening a quiet intro gets at 8; it is the next cut if the
   ear asks for it. `TSP_RATCHET=0` builds the per-span leveller back for the
   A/B. Tracker is the one
   player that knows its whole piece in advance: the patterns say which
   sample plays at which volume, and every sample's peak is known once the
   module is loaded (`tsp_natural` already walks them). A pass over the
   pattern data, with no mixing, can bound the song's loud passages and pick
   ONE level for the whole song, so nothing pumps because nothing moves, and
   the soft clip takes the rare hit above it. Captured Elysium at a fixed
   level 5 clips 25% of samples, far too hot, so the level has to come from
   the pre-pass (aim for 3-5% at the curve's end), not from a constant. Cost:
   load time (a pattern walk is fast next to `tsp_natural`'s filter) and no
   cycle in the play loop at all, since the level scan could be skipped.
   Risk: a song with a quiet intro and a loud chorus gets the chorus's level
   throughout; a slow leveller on top (hold of seconds, not spans) would
   cover that.
2. **Two bands.** Split the mix at ~300 Hz with a one-pole filter, level
   each band on its own, and sum. A hit in the highs no longer takes the bass
   down. Cost is per sample, not per span: a one-pole split plus a second
   table lookup is ~25-40 cycles on an 8088, which Audio's 8 kHz leg on a
   5150 cannot afford. It is a V20/T1100/286 rung, chosen by the tier the way
   Tracker's rates are. It changes the family table's shape (two families,
   or one family indexed twice), so it wants the model first.
3. **Look-ahead by delay.** Tracker already runs a ring seconds deep, so
   delaying the shaper by one span would let the level fall exactly AT the hit
   instead of at the top of the span holding it. Finer detection costs
   per-sub-block peaks: reading 1 sample in 8 instead of 1 in 32, a few more
   cycles a sample. Addresses the pre-duck; does nothing for the fade-back
   after.
4. **Host-side quality for pre-shaped files.** A `.WAV` the encoder shapes
   for the speaker (`tools/os88venc.py`'s WAV target, SPEC.md 98.2.8) is
   played as counts: the machine does no levelling at all. So the host can
   run a proper leveller (true look-ahead, RMS detection, two or three bands,
   soft knee) at no cost to any 8088. Today it runs the machine's model, so a
   file sounds exactly like live playback; it need not. Counts files (kind 2)
   need no change on the machine to benefit.
5. **Tuning the shipped shape.** Ratio 3 -> 2 moves the level less and leaves
   the lows quieter. 1 dB rows instead of 2 give a finer glide but a family
   of 21 rows, 5.4 KB of every carrier's bss against 2.8 KB. An RMS detector
   in place of the sparse peak is less spiky, but per-span squares need a
   table. Each is a column in the section 3 table before it is a build.

## 5. How to decide

The owner's ear decides, on the owner's machines, and what worked in round 4
should be kept: **two Trackers side by side**, the shipped build and the
candidate, the same module, switching between them. The numbers in section 3
say which candidate is worth an ear; they have never been the verdict. Keep
each candidate one self-contained commit, as round 3 was, so the one that
loses is a `git revert`.

## 6. Also open, found on the way

- **Tracker's rate prediction over-counts a 286.** Since `TSP_CS` went to
  104 (SPEC.md 45.25.1), Auto on the owner's 16 MHz 286 opens at 16,000 Hz
  predicting ~75%, where 22,050 Hz had held with the spectrum at full speed.
  SPKBENCH's 286 numbers put 22,050 at ~107% (the ISR 32.6%, the shaper ~7%
  and the mixer term ~63%), so it is the MIXER term: it is priced at the
  worst case, four channels and the longest looped sample. A measured load
  during the play, or a per-tier constant, is the fix. The Rate menu lets
  the user pick 22,050 meanwhile.
- **The carrier's whine against the level.** On the 5150, levels 7 to 10
  weaken the whine: the louder the level, the more of the time the pulse
  sits near an extreme, where the carrier is weak. Moving the carrier's
  resting point towards an extreme in quiet passages might buy that at
  level 5. Untried; the replay above can measure the duty spread first.
- **BEVERLY.MOD's low notes** are gone on the speaker at every level. Not
  investigated: it may be the speaker, or the load-time filter
  (`tsp_natural`).

- **The 86 against 108.** SPKBENCH's shaper loop runs at ~86 cycles a sample
  on a 5150 where Tracker's calibration of the same call reads ~108 (Ne =
  9,728 in four ticks); neither the source data nor the pre-emphasis explains
  it (SPEC.md 45.25.1). `TSP_CS` is expressed against Tracker's figure, so
  this does not move the constant, but it is an unexplained 25%.
- **The 286's ISR is a quarter dearer** against its shaper than an 8088's
  (SPEC.md 45.25.1's ratio column), so Tracker under-predicts a 286 by ~7
  points at 22,050 Hz. The 16 MHz machine holds it; a 10-12 MHz one is the
  field test to ask for. A per-tier `TSP_CS` is the fix if it fails.
