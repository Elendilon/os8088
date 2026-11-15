# BONANZA: the speed pass of 2026-11-15 (a dated measurement)

A report, not a contract: SPEC.md 128 is the authority on what BONANZA does,
and this file is what one tree measured on one day. Base `621bdefb`; the
pass is the merges and commits after it on `bounce-bonanza`.

The owner's brief: make room for the plan's later consumers (course clocks,
pickups, cracked tiles, wind lanes, more lanes and occluders in a window)
without hurting the frame rate. Five areas were worked in parallel, one file
each, as pure speed changes: same pixels, same physics results, same sound.

## What changed

| area | file | what |
|---|---|---|
| box path | `bzvideo.inc` | the fill's runs in registers; a sprite blit fast path when nothing is clipped; the occluder pass keeps a per-row search hint and prepares a row only when it lays a record; `bz_row` / `bz_col` by `movsw` |
| props and wheel | `bzwheel.inc` | the QUIET WALK (a walk that skipped every lane is not made again until a wake term could end a skip); per-lane tables filled at `bz_pread`; the lift's record cached |
| sound | `bzsound.inc` | the sequencer and the AdLib staging re-encoded; no `mul`; output sequence identical |
| frame loop | `bzgame.inc` | cheaper marks; GLIDE skips a redundant clamp; box records by `stosw`; THE EARLY STEP |
| physics | `bzphys.inc` | the nine-cell window refilled by moving six cells and reading three (`bz_win9i`); flat-floor paths in line; 19 single-routine commits, bit-exact |
| keys | `bzgame.inc` | one `OSAPI_KEY_MAP` (SPEC.md 9.7.3) a frame in `bz_exitchk`, in place of ten `OSAPI_KEY_DOWN` |

**The early step** (`bz_early`, knob `BZ_EARLYSTEP`, off with
`-DBZ_NOEARLYSTEP`): after the wheel, when a physics step is already due by
the clock and at least `BZ_EROOM` (8000 PIT counts) of the retrace wait
remain, that step runs in the wait. The step count is unchanged; replays and
demos end where they did. **The one behaviour change of the pass**: in live
play that step reads the keys as last sampled. `bz_noearly` is a bss byte
nothing in the package writes; a row pokes it to 1 to hold the early step
off, because the ring's and the wheel's oracles read the ball and `bz_nstep`
at `bz_tf` / `bz_presented`, after the wait.

## MEASURED (MartyPC, `tests/bonanza_perf.py --ab`, D of each demo, speaker ON)

The comparison build is the row's own A/B commit `503031d4` (just before
wave 6), so the columns are near like for like, not exactly.

| demo | card | busy mean, clk | misses | longest run of misses |
|---|---|---|---|---|
| MILL | CGA | 59,091 -> 48,484 | 122 -> 24 | 31 -> 4 |
| PEAK | CGA | 61,260 -> 51,693 | 307 -> 128 | |
| MILL | Hercules | 59,211 -> 48,546 | 22 -> 6 | 10 -> 3 |
| PEAK | Hercules | 63,187 -> 52,524 | 114 -> 21 | 15 -> 3 |

Per routine (each agent's span script, logged breakpoints, CGA MILL unless
said):

| part | before | after |
|---|---|---|
| `bz_boxc`, a box | 10,262 | 8,404 |
| the occluder pass, a frame (mean) | 9,828 | 7,559 |
| `bz_props`, a frame (mean) | 4,735 | 2,809 |
| `bz_step`, a call (mean) | 7,347 | 6,582 |
| the window refill | 6,996 | 4,030 |
| `bzs_frame`, speaker, worst | 20,776 | 18,579 |
| `bz_mark`, a play frame | 3,408 | 1,930 |
| `bz_camera` | 3,353 | 2,637 |

PREDICTED, not measured: the key map saves about 4k clk a frame of live play
(nine far calls of about 580 for one of about 650).

`build/bonanza.bin`: 33,837 -> 35,073 bytes (+1,236): box +107, wheel +485,
sound -36, frame +153, physics +505, keys +22.

## What the frame is made of (base, CGA MILL, D, clk a frame, mean / heavy)

`bz_step` 7.9k / 16.3k; `bz_props` 5.1k / 7.7k; the marks 5.6k / 6.3k
(benchmark instruments); `bz_mkboxes` 4.5k / 5.9k; `bzs_frame` 3.8k / 5.2k;
`bz_camera` 3.4k / 3.8k; `bz_exitchk` 1.6k. A frame of two steps was 13.6%
of frames and 81 of 99 of them missed. After the pass the frames that still
miss are render-bound: more early steps, or the sound's song half moved into
the wait (built on local branch `perf-snd2`, exact, +102 bytes), did not
lower the miss count.

## What the final pass found

- The box file's `BZ_CROW` / `BZ_HROW` macros are the wheel's lane writers'
  too; changing them for `bz_col` put every lane's rows in the wrong place.
  Restored byte for byte; `bz_col` has private copies.
- The quiet walk did not read `bz_lhold` / `bz_ldrw` / `bz_ltru`, which the
  game changes only inside a walk but the rows poke. Two compares added.
- `bonanzaring`'s LOW scenario is marginal on the faster build: the CGA saw
  1 or 2 LEAD commits a run and once 0 (a coverage failure). `LOW_HOLD` wants
  a retune by the row's owner.
- `bonanzawheel` check (6), the CGA's light corner, fails as it did at the
  base (the plan's T1).
- MartyPC charges about 12 clk per video-memory byte written, so `bz_boxw`,
  `bz_row` and `bz_col` are near their floor.

## Open, for the owner

1. `bz_lwhole` reads `bz_lq0` / `bz_lq1`, which `bz_wsave` / `bz_wload` do
   not carry: with two or more candidates prepared, any but the last is
   judged whole or clipped against the wrong rows (a base bug, kept).
2. An OCCIDX row summary so a row that lays nothing is skipped: about -3k on
   a pass that lays nothing (PREDICTED); a course-format change.
3. Skip the sound on a heavy frame, at most one in a row: 12-18k (speaker)
   off that frame; tones can be a frame late.
4. `BZ_WPRP` and `BZ_WMF` over-state the wheel's preparation now and could be
   re-tuned (about -55 and -60 counts, PREDICTED).
