# BOUNCE BONANZA — the sound (plan, stories and how it was built)

The contract is SPEC.md 128.20; this is the plan it was built from, the story
list with what each story's evidence actually is, and the diary. It was
built by a second session **in parallel** with the main game's waves (SPEC.md
128.12, [BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md) and its
[diary](BOUNCE-BONANZA-DIARY.md)), so it touches their files only at a few
named seams, and its SPEC section is numbered 128.20 to leave 128.13 - 128.19
to their waves.

## The brief (the owner, 2026-11-13)

> Another session is working on the mechanics and levels of bounce bonanza.
> We're going to parallelize a bit and have you work on sounds and music. Both
> the composition and the engine. Tithe-new probably has a similar engine,
> although you could pick differently to get better musical abilities if they
> fit the performance budget. Each impact should have a sound effect,
> different for each ball type. Compose a title screen music, and music for
> the initial 5 planned levels. Keep in mind both performance and size (the
> music has to fit in the parts with all the other future work too). We'll
> support pc speaker and adlib sound.

## The decisions, and why

| | decision | why |
|---|---|---|
| D1 | TITHE's MML and its "one score, two renderers" shape, but **a sequencer of this game's own** | TITHE's lives on `tithe-new`; its 18.2 Hz tick is too coarse for the musical abilities asked for |
| D2 | **The clock is the physics sub-tick, 54.6 Hz** | exactly three to a system tick, the same on both cards, and what the simulation already counts: arpeggios and drum blips on the speaker, tempos from 102 to 164 BPM with swing |
| D3 | **Pitch is a 1/256-semitone word**, through one octave's table and one `div` | slides, vibrato and macros on both arms; 24 table words, not 512; `div` and not `aam 12` because a V20 ignores AAM's base |
| D4 | **The speaker folds** effect > drum blip > lead > bass | TITHE needed hand-written speaker scores to stop "a blip then blank"; a rule costs no score bytes |
| D5 | **A note is two stamps** and one deadline | the measured profile: counting six gates a sub-tick cost ~1.2k cycles before anything happened |
| D6 | **The AdLib through the whole-chip claim and one capped batch a frame** | ARCADE's door from a bracket; measured ~2,300 cycles a batch plus ~1,050 a register, which decided everything below |
| D7 | Drums on **two** OPL channels (5 the thumps, 6 the `alt` noise family), the effect on 7; **one effect at a time** | a re-patch per hit was the worst frame of the first build (~14k cycles) |
| D8 | The AdLib's vibrato is **the chip's VIB bit**; effects set their level **once a segment** | a written vibrato or decay is a register batch every sub-tick or two |
| D8b | **No written vibrato on the speaker either**, and the speaker keys **no chord voice** | the counterfactual (below): the sound cost BENCH 7 refreshes and the windmills 2 rotor poses; a written vibrato was a tone every other sub-tick |
| D9 | Patches **resumable** across frames (`H_PPOS`), cap 8 | no frame passes the cap, a note a frame or two late at most |
| D10 | Physics is never touched for sound: **counters** it already keeps, one added (`bz_nwall`) | the main waves own physics; the counters were left for this (SPEC.md 128.11.5.2, 128.12.6.6) |
| D11 | **A part a song**, the sound part shared | only one song in memory; ~2KB held at most; the floppy pays 4.9KB packed |
| D12 | The five course themes composed by five parallel agents to one brief, the title and the bank here | each checked by the tool and reviewed bar by bar against its chords; one agent found the instrument carry-over bug (diary) |

## Stories

- [x] **S1 The format and the tool.** `tools/bbmusic.py` packs the bank and
      six songs, renders both arms to WAV (pyopl for the OPL2), and its
      selfcheck holds every packed note, gate, instrument and volume to the
      source's. *Evidence: `bonanzamusic` (0 problems).*
- [x] **S2 The bank and the effects.** 28 instruments, 21 effects, every
      ball's LAND, BOUNCE, WALL, BUMPER and KNOCK distinct, steel's STUN and
      glass's SHATTER, HOP, FALL, TUBE, GOAL. *Evidence: `bonanzamusic`'s
      material checks; `bonanzasound`'s events (each ball's bounce, wall and
      bumper poked on the guest).*
- [x] **S3 The title and five themes.** *Bounce Bonanza* (F, 136.5),
      *Fairway* (G, swung 117), *Bounce Trial* (D dorian, 136.5), *Windmill
      Lane* (C, a 3/4 street-organ waltz), *Moonlit Green* (A minor, swung
      102), *Summit Rush* (E minor, 164); 831 - 1,234 bytes each.
      *Evidence: the renders (sent to the owner); nobody here could listen -
      the review was harmonic, bar by bar.*
- [x] **S4 The speaker arm.** *Evidence: `bonanzasound` spk leg: the guest's
      state and the Hz it sent held to the model at every stop.*
- [x] **S5 The AdLib arm.** *Evidence: `bonanzasound` fm leg: the state, the
      chip's shadows against the model's registers whenever nothing is dirty,
      the OPL capture loud, the claim given back at the window's close.*
- [x] **S6 The desktop title and S.** *Evidence: `bonanzasound` (the title's
      state, S's four choices, OFF giving the parts back); `bonanzaexit`
      (the title's two rows held before and after every launch).*
- [x] **S7 The events** - wave 2's counters, wave 3's `bz_nkick`,
      `bz_nknock`, `bz_ntube`, and the new `bz_nwall`. *Evidence:
      `bonanzasound` (bounce, wall, bumper face); kick, knock and tube are
      wired but not yet poked by a row.*
- [x] **S8 The cost**, measured and cut: speaker 8,900 -> 3,319 cycles a
      frame, AdLib 8,492 -> 6,433 (worst frames 13.4k and 29.9k), and what it
      costs the game measured against the same tree with the sound off
      (SPEC.md 128.20.7). *Evidence: `bonanzasound`'s report; the
      counterfactual runs of `bonanzaperf` and `bonanzawheel`.*
- [ ] **S9 The owner's ear.** Every patch, effect and song is PROVISIONAL
      until heard on the 5150s (#1's speaker, #2's PicoMEM AdLib).
- [ ] **S10 A course names its song** (a `music N` statement), when the
      courses' waves want it; today course K plays song K.
- [ ] **S11 The price** - BENCH's 7 missed refreshes against 1, the
      windmills' 2 poses in 36, the worst AdLib frame at 38% of a refresh -
      against wave 3's tight budget: the owner's call - `BZS_FMCAP` is the knob, and
      SOUND.DRV's OPL2 write delay (~1,050 cycles a register on an XT, about
      four times what the chip needs) is a driver-side improvement outside
      this work.

## How it was built (diary)

### 2026-11-13: the map

**Observed.** TITHE's music (on `tithe-new`) is MML packed into a part,
played at 18.2 Hz: the speaker plays the lead only, the AdLib through note-by-
Hz verbs. Bonanza's physics steps once a FASTTICK sub-tick, 21,845 PIT counts
- 54.6 Hz, three to a system tick. SOUND.DRV's whole-chip claim and register
batch exist and ARCADE drives them from a bracket. Wave 2 left counters for
"wave 4's sounds"; wave 3's contract added three more.

**Decided** D1 - D4, D6, D10, D11 (above) and wrote SPEC.md 128.20 first.

### The compositions

The title and the bank were written here. The five course themes went to
five agents in parallel, each with the tool, the bank and the title as the
worked example, a mood, a key and tempo suggestion, a 1,100-byte budget and
the speaker's fold explained. All five came back inside budget and checked.

**Found by a composer, not by a check:** the packer assumed each phrase
started on the voice's own instrument at v12, while the sequencer carried the
last phrase's instrument over - so a phrase after an `@glock` played glock,
and the selfcheck (notes and gates only) could not see it. Fixed both ways:
every pattern resets its channels (guest and model), and the selfcheck now
compares instruments and volumes. Two other agents' reports added the
speaker's re-send of a repeated same-pitch note and the bass blipping into
every one-sub-tick articulation gap; both fixed in the fold (a token for the
note; the bass only after the lead has been silent 2 sub-ticks).

### The first guest run

`bonanzasound`'s speaker leg passed on its first real run - title, S, FIRST,
each ball's effects, Esc - and priced a frame's sound at **8,900 cycles on
average, 16,058 at most**: 11% of a CGA refresh, five times the prediction.

**Profiled** (breakpoints between the phases, guest cycles): the sequencer
~3.3k a sub-tick, the event compares ~1.5k, the speaker's output ~1.5k, the
idle effects ~0.4k - all instruction-fetch bound on the 8088. Steps:

| change | average |
|---|---|
| the first build | 8,900 |
| an instrument's record once a key, a pitch only when it can move, no chord pitches on the speaker, compare pitch not Hz | 8,024 |
| inline fast path, unrolled compares, idle effects early-out, one `div` a pitch | 6,094 |
| no pitch work before a vibrato starts; a held macro leaves the dynamic set; events return early | 5,597 |
| **notes as stamps, a deadline, a dynamic mask, an AdLib dirty mask** | 5,091 |
| vibrato a step every two sub-ticks; events summed first | **4,278** |

One shortcut was wrong and the row said so at once: a freshly keyed note
with a vibrato not yet begun kept the previous note's pitch.

### The AdLib

Correct on its first run (the chip's shadows equal to the model's registers
at every quiet stop), but **8,492 cycles on average and 36,101 at most**.
Measured a batch: **~2,300 cycles plus ~1,050 a register**. The worst frames
were the drum voice re-patched every hit (11 registers); the averages were the
lead's written vibrato (a one-register batch every other sub-tick) and the
effects' per-sub-tick level. D7 - D9 took it to **6,533 average, 30,213
worst** - a downbeat's sequencing, six F-numbers and the capped batch.

### The counterfactual (after the merge)

The final pass failed `bonanzaperf`'s A/B leg (1, then 4 missed refreshes on
equal-steps frames) and `bonanzawheel`'s (7) (the rotors at 87% of their
poses) where wave 3 alone passed them. The same tree built with `bzs_open` and
`bzs_dstart` returning at once passed both: the sound was the whole
difference, ~3.4k cycles a BENCH frame. Two more cuts (no written vibrato on
the speaker; no chord key-ons there) took the speaker from 4,296 to 3,319 a
frame - not enough to pass both rows. **Decided**: those rows test the engine
and the wheel at EQUAL content, so they run with S's OFF (poked), and the
price is on the record in SPEC.md 128.20.7 for the owner to weigh, rather than
either row's threshold moved or the sound quietly thinned further.

### Merged onto wave 3

Wave 3 landed on the branch mid-way (every file this work touched). The
rebase was the face's line and `bz_launch`'s tail, both kept; wave 3's
counters were wired in; `bonanza_exit`'s "nothing fetched on the desktop" now
excepts the title's two rows and requires them held before and after every
launch; `bonanza_ring.part_args` adds the sound parts for a tree that has them.

### What is measured, and what is not

Measured on MartyPC: every cost figure above, the image (+3,805 bytes), the
parts. Not heard: anything - no one here can listen; the renders were sent to
the owner. Not run: a 5150, a real AdLib, kern_mega's sound (the final pass's
`bonanzamega` runs a play with it), the Hercules (the sound is the same code
on both; its cost row is the CGA's).
