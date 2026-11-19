# Bounce Bonanza: songs in their courses, the finish's tunes resident (PROPOSED)

The owner, 2026-11-19: *"Victory/death are sounds always loaded, and each
course's song will be unique to that course. This may be part of why load
times have been going up (aside from 'more data, more props'); so as the next
piece of work then lets explore putting victory/death into the shared
resident part, and each course's song in with its course part (if that means
duplication, where one song goes in multiple course parts right now that is
fine; as I said, each course gets its own song for the release)."*

This is the exploration: what a launch spends on sound today (MEASURED), the
design, and the stories. Nothing here is built yet.

## What a launch fetches today (MEASURED, 2026-11-19)

`bz_cload` fetches, in order: the course part (and a two-part course's WORLD
part), then `bzs_gfetch`'s FOUR sound parts - `BZSND.BIN` (the bank and the
effects, 1,383 bytes), the course's song (`BZM<S>`, 0.8 - 1.3 KB), the
VICTORY fanfare (224 bytes) and TIME'S UP (152 bytes) - then the families'.
The sound part and the three songs are given back at every play's end
(`bzs_gdrop0`) and fetched again at the next launch.

Measured on MartyPC's 5150 (4.77 MHz, CGA, the 360 KB disks, `BZDEV=1`
tree at ea0c09a): a breakpoint at every `op_fetch`, guest cycles and the
floppy controller's counters (`m.disk()`) at each, to the first `bz_t0`.
Each row is the time from that fetch's start to the next one's: its read,
expand and the bookkeeping after it.

| | FIRST (pathway pad) | PEAK (free play) | MOON (free play) |
|---|---|---|---|
| course part (read, expand) | 0.67 s, 2 reads | 2.35 s, 2 reads | 2.01 s, 2 reads |
| `BZSND.BIN` | 0.09 s | **0.53 s, 1 read** | **0.45 s, 1 read** |
| the course's song | 0.07 s | **0.38 s, 1 read** | 0.07 s |
| VICTORY | 0.05 s | 0.05 s | **0.28 s, 1 read** |
| TIME'S UP (+ the families) | 0.03 s | 0.06 s | 0.05 s |
| **sound, total** | **0.24 s (12%)** | **≈1.0 s (29%)** | **≈0.85 s (29%)** |
| launch to first frame | 1.98 s (from Enter on the pad) | 3.47 s | 2.95 s |

The sound parts are small; what costs is a READ: a part whose sectors are
not in the track already read is a floppy read of its own, ~0.3 - 0.5 s on
the XT. Which ones miss depends on where each lands on the disk, so it
varies course by course - two of the four missed on PEAK and on MOON, none on
FIRST. Every launch pays it again, because every part is given back.

## The design

1. **THE SOUND PART HELD, with the finish's tunes inside it.** `BZSND.BIN`
   gains the VICTORY and TIME'S UP songs (each at a paragraph-aligned offset,
   reached by a derived segment from `OSAPI_SEG`'s `SEG_SUB`, never by
   segment arithmetic - kern_mega's rule), and is fetched ONCE at the open
   and HELD while BONANZA is open, as the balls and the kit are (130.25.5.2,
   130.37.5): the arena's floor, under `op_artop`. Cost: about **1.8 KB of
   heap held** for the package's life (1,383 + 224 + 152, rounded to
   paragraphs) against **three fetches less per launch**. Sound OFF still
   fetches nothing; kern_small plays nothing, as now.
2. **EACH COURSE'S SONG IN ITS COURSE PART.** The tool writes the course's
   song into the course part as one more directory entry (BZC2's directory,
   130.15), paragraph-aligned; `bzs_gfetch` points `bzs_mseg` at it through
   `OSAPI_SEG` instead of fetching `BZM<S>`. A song two courses share is
   COPIED into both (the owner: fine; each course gets its own song for the
   release). The pathway's and the title's parts carry theirs the same way
   (the title's `attract`). The course part grows by its song's packed
   bytes - a few hundred - and its read by at most a sector; a course demo
   on the title's chain plays its course's song from the same part.
3. **What goes**: the per-launch `BZM<S>` fetch and its drop; the fanfare's
   and TIME'S UP's fetches, drops and `bzs_vseg`/`bzs_tseg` claims (they
   become derived segments of the held sound part, re-derived when the
   arena moves - 130.25.4.2's `bz_arload`); the songs' own part rows, once
   no part needs them (`BZM<S>.BIN` stays the tool's intermediate).
4. **What stays**: the music format, the sequencer, the bank, every effect;
   `bbmusic` builds the songs as now and `bbcourse` places them.

**Predicted saving**: the sound column above less the cost of a song decoded
with its course - on PEAK and MOON about **0.8 - 1.0 s a launch**, on FIRST
about 0.2 s. To be MEASURED with the same probe after.

## Questions for the owner

- **Held memory**: is ~1.8 KB held for BONANZA's life acceptable (the kit
  and the balls already are)? The alternative - fold the two tunes into a
  sound part still fetched per launch - saves two fetches, not three.
- **Order**: songs-in-course-parts (bigger saving on the courses that miss)
  and the held sound part are independent; either can land first.

## Stories

- [ ] **S1** `BZSND.BIN` carries VICTORY and TIME'S UP at paragraph offsets
      (bbmusic); the guest derives their segments (`OSAPI_SEG`), on
      kern_big and kern_mega.
- [ ] **S2** The sound part fetched at the open and HELD (the arena's
      floor); `bzs_gfetch`/`bzs_gdrop0` stop fetching and dropping it;
      `bz_arload` re-derives the tunes' segments.
- [ ] **S3** The tool writes each course's song into its course part (and
      the pathway's and the title's); the guest plays it from there.
- [ ] **S4** The song part rows retired; `crs_arena` and `BZ_CRS_ARENA`
      shrink by them; `tests/pins.txt` loses `bzs_vseg`, `bzs_tseg`.
- [ ] **S5** MEASURED: the launch probe again on FIRST, PEAK, MOON;
      `bonanzasound`, `bonanzapath`, `bonanzademo` and `bonanzaexit` in the
      final pass; the title, a course, a replay and the pathway heard.
