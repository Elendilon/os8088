# BOUNCE BONANZA — the resident window (space plan)

The package's resident segment, image plus bss, is held to `APP_MAX_SIZE` =
0xFE00 = **65,024 bytes** (SPEC.md 20.1.1; `OS88_IMAGE_END` refuses past it).
This file is the survey of where BONANZA's bytes are, what was taken out to
make room, and the moves held in reserve for the next time it fills. The
contract is SPEC.md 130; the game's plan is
[BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md).

## The brief (the owner, 2026-11-19)

> Bounce bonanza's main package is full. We need to make at least 4k of room.
> First: anything there that we are not using. Debug, a/bs not on, anything
> from the old text title screen, etc; things left around from development.
> Then: things that could be smaller, things that could go in another part
> together, other ideas?

And, after the survey: *"anything that is a test only needs to be on a knob.
We don't ship tests"*; and *"Wave 1 and wave 2 will probably be enough. We're
at the point of just optimization. Record your wave 3 findings in a bonanza
space plan and if we run out again we'll start looking into those."* Wave 4
(the knob) stays: *"its just good practice."*

## Where the bytes were (at `bb943bde5`)

`build/bonanza.bin`: **51,607 image + 13,360 bss = 64,967**, 57 bytes free.
Code by defining file (label-to-label spans out of `build/bonanza.lst`, so
approximate; a label inside an unassembled `%if` is charged nothing):

| file | bytes | what |
|---|---|---|
| `bzphys.inc` | 10,057 | the step (`bz_step` 2.6K), props, landing, walls |
| `bonanza.asm` | 9,736 | books, BONANZA.DAT, demos, keys, the pathway, the loader |
| `bzwheel.inc` | 7,657 | lanes, the pacing wheel, its calibration |
| `bzgame.inc` | 7,101 | frame loop, camera, autopilot, instruments, the log |
| `bzvideo.inc` | 5,902 | bracket, ring writers, boxes, occluders, the anaglyph model |
| `bzsound.inc` | 3,508 | sequencer, AdLib and speaker arms |
| SDK includes | ~2,960 | `os88partsbody` 1,418, `os88ui` 733, `os88data` 396, `os88parts` 320, `os88rseq`, `os88alt` |
| others | ~4,400 | `bzmenu`, `bzcard`, `bzballgen`, `bzfam` |

The largest bss: `bz_rlog` 4,096 (the replay log), `bz_boxbuf` 1,024,
`bz_font` 512, `bz_dmine` and `bz_dat` 494 each, `bz_ltrc` 400, `bz_fhl` 384,
`bz_osum` 320.

**What the survey did NOT find** is the thing the brief expected: dead code.
Six areas were grepped label by label against every caller, `fam/`, the shell
part, `tools/` and `tests/`, and the truly unreferenced residue was a handful
of bytes (`bz_nearly`, `bz_arforce`). The old text face is not dead: its keys
(B R D W L V N M C G T S, the tour, the results page) answer only while the
harness byte `bz_dev` is set, which no player can do, and every bonanza row
sets it and drives them. That is **test-only code in the shipped image** —
wave 4 below.

## Waves

| wave | what | bytes | state |
|---|---|---|---|
| 1 | Trims: `bz_dmine` shares `bz_font` and `bz_lbuf` shares `bz_boxbuf` (584 bss, lifetimes disjoint: desktop vs bracket); `bz_nearly`, `bz_arforce`, a dead `xor`; the old face's slot keys 1/2/3, E, X (no row presses them, the Saves menu does the same); folded duplicates (`bz_vkey`'s copy, the adapter refusal, RESTORE tails, the dev-key chain); exact physics duplicates (`BZ_START` x2, the windmill door, `bz_psync`, the field symmetry table, `bz_prod`); the `bz_early` `%if BZ_PATH_NPAD` assembly bug | ~1.2K est. | in progress |
| 2 | The replay log's runs out of bss into a zero-filled tail on the kit part (fetched at open, held all session — no new claim, no new read); the 16-byte header stays resident | ~3,950 est. | in progress |
| 3 | The sound code into the sound part — **held in reserve**, below | 3,172 measured | reserve |
| 4 | Test-only code behind a `BZDEV` knob, the rows building it — below | ~1K est. | next, after 1 and 2 |

Waves 1 and 2 land with their measured numbers in this table when they merge.

## Reserve: wave 3, the sound code into the sound part (3,172 bytes, MEASURED)

Measured with a stub build at an older commit: the resident image went from
50,178 to 47,002 with five far stubs, two `op_cseg` sites and a 4-byte far
pointer in bss. `bzsound.inc` has not moved since, so the figure stands to
within a few bytes.

**What moves:** `bzs_open`, `bzs_close`, `bzs_frame`'s body, `bzs_ctab`,
`bzs_events` .. `bzs_patch`, and the bodies of `bzs_ev` and `bzs_victory`.
Both arms go: the AdLib arm is ~720 bytes, the speaker arm ~245, `bzs_tab` (59)
is shared.

**Why it is safe:** all of it runs only while `bzs_arm` is not NONE, and
`bzs_open` sets an arm only once the sound part is fetched, so "an arm is
open" already implies "the code is present". It calls nothing resident; its
outside calls are OSAPI far cells, which the shell part already makes from a
part. It reads package bss that `bzlink.inc` names, writes only through DS,
and its five read-only tables take a `cs:` prefix (legal through kern_mega's
code alias, as the shell's tables are).

**What stays resident:** `bzs_toggle`, `bzs_gfetch`, `bzs_gdrop`/`bzs_gdrop0`,
`bzs_fsnd`, `bzs_fsong`, `bzs_dsong`, the stubs. The stub `bzs_frame` keeps
its `.fend` label after the far call (bonanza_perf, bonanza_ring and the cost
leg of bonanza_sound use it); a resident `call bzs_victory` stays
(bonanza_sound checks `bonanza.lst` for it).

**The home:** the existing `BZ_P_SND` row, as a combined file (`BZSNDX.BIN`):
`BZSND.BIN` padded to a paragraph, then the code assembled at that origin,
linked against `bzlink.inc` the way `bzshell.asm` is, row kind `OP_SEG`. No
extra fetch or disk read, and the RAM is spent only when sound is on.
`bzs_fsnd` and `bz_arload` refresh the far pointer's segment with `op_cseg`,
since the arena can move — and so must any VGA-arm path that reaches sound
(`bzvga.*`; the stopped attempt was checking exactly this). Rejected
alternatives: its own arena row (one more fetch, ~0.4 s on the XT, per
launch); a pseudo-family in the resident bundle (no disk read, but ~3.2K of
heap held all session with sound off).

**What changes with it:**
- `tools/bbcourse.py` `crs_arena` / `crs_maxclaim` size the sound part from
  `bbmusic.load_parts()`, not from the built file. Add the code's paragraphs
  as a ceiling constant checked against the built binary: `bzcourse.inc` ->
  `bonanza.bin` -> `bzlink.inc` -> the part is a cycle.
- `tests/bonanza_sound.py`: `stop()` breaks at `bzs_tp`, which moves (give it
  a part-label resolver like `bonanza_ring.py`'s `shell_symbols`); the
  `noboost` red arm patches `bzsound.inc` and rebuilds, so build the part from
  the same source (split the file into a resident half and a part half);
  `parts()` reads `BZSND.BIN` as pure data, so keep that file pure.
- The Makefile's `--part` list (in `OS88_PART` order) and its dependencies;
  SPEC.md 130.20 and the arena's sizing subsection.
- Rows: bonanza_sound, bonanza_perf, bonanza_ring, bonanza_exit,
  bonanza_game, bonanza_wheel, on kern_mega as well as kern_big.

**Cost:** one far call and return a frame, ~60 cycles on the 8088.

If wave 3 is not taken, `bzs_events` could be table-driven (~60–90, keep the
trigger order and the `bzs_ctab` line the `noboost` arm patches) and the
unrolled 15-counter sum looped (~45, but ~500 cycles a frame).

## Wave 4, test-only code behind a knob (~1K est.)

Not a reserve: the owner, 2026-11-19, *"Wave 4 is still good after because
its just good practice."* It follows waves 1 and 2.

The owner's rule: *anything that is a test only needs to be on a knob.* The
code that exists only for the rows:

| part | bytes (est.) |
|---|---|
| `bz_onkey`'s `.dev` dispatch and the old face's handlers (`bz_game`, `bz_tgo`, `bz_camkey`, `bz_ballkey`, `bz_crskey`, `bz_dkey_d`, `bz_wkey`/`bz_lkey`/`bz_wdone`, `bz_vkey`, `bz_tkey`, `bz_skey`, `bz_ttotal`, `bz_post`'s and the books' tour arms) | ~700 |
| measured marks (`bz_mark .meas`, `bz_markm` and sites), `bz_presented`'s period/max/miss, the beam-lateness check, `bz_rcopy`/`bz_res` | ~440 |
| the autopilot (`bz_auto`, `bz_want`), the scripted camera, `bz_hspin` | ~350 |
| the `bz_r*` result copy and pure counters | ~100 bss |

Shape: a `BZDEV=1` build knob into a private tree (the `BZSHAPES` precedent),
which every bonanza row builds and runs instead of `build/bonanza.o88`. The
harness bytes (`bz_dev`, `bz_phforce`, `bz_apilot`) go with it. Two things to
settle first: whether a row that is ABOUT the shipped game (the title, the
pathway, the menus) should still run the shipped build, and TRICKLE — the C
key switches it in real play (`bz_input`, ungated), though the About card does
not list C, and ~10 bonanza_ring legs use it as their held-window camera
(~200 bytes if it goes too).

## Reserve: other moves, roughly by bytes per effort

| move | bytes (est.) | the catch |
|---|---|---|
| **The course loader into a part** (`bz_cexp`, `bz_dfind`, `bz_drec`, `bz_dval`, `bz_cxtab`..`bz_cxsafe`, `bz_fsbset`, `bz_crshdr`, `bz_osmake`, and the Hercules translation `bz_hgen`..`bz_hxrows`): a closed call graph run once per course load | ~1,850 | runs while a course is held, so not the shell part: its own lazy part (+1 read a load) or code linked into the held kit. ~12 rows call `bz_cexp` or patch these lines |
| **The anaglyph model** (`bz_amodel`, `bz_arange`, `bz_ahalf`) fetched only with a `BZ_GF_ANA` course, as a family is | ~1,800 | per-frame path: a far call on every `bz_olay`/`bz_oprep`; re-measure 130.29.9's fall frame |
| **The pathway's code into `BZPATH.BIN`** (`bz_pw*`, `bz_follow`, `bz_ppad1`.., its cards `bz_kinfo`.., `bz_gfsave`/`bz_gfload`) | ~1,200–2,200 | needs a part-to-package call door (below); `tests/bonanza_path.py` breaks on `bz_pwdep`/`bz_follow` by name |
| **`bz_ballgen` into a part** (once per ball fetch, self-contained, already checked standalone under an emulated 8086) | ~1,200 | its refetch runs with a course held; `bg_nib` becomes `cs:` |
| **BONANZA.DAT's checks into the shell part** (`bz_dsave`'s merge, `bz_dnorm`, `bz_dslots`, `bz_dchk`, `bz_dload`, with `od_read`/`od_write` behind a new `os88data.inc` opt-out) | ~550–650 | a refused shell fetch would then lose a save, not just a picture; bonanza_game's red arms patch `bz_dnorm` |
| **The wheel's calibration** (`bz_wcalib` arithmetic, `bz_wcorner`, `bz_wctry`, `bz_kmeet`, `bz_lq`) held with the course | ~480 | `bz_wspan` stays resident: a far hop inside the timed span biases it |
| **The bumper as a family** (`bz_posts`, `bz_circle`, `bz_ptop`, `bz_otab`..) | ~650 | a far dispatch per step on four courses; bonanza_phys reads `bz_circle` |
| `bz_step` step 5 as `call bz_swalls.edges` | ~410 | hot path, +15–30 clk a step; equivalence by reading only |
| `bz_osum` into the picture part's slack | 320 | fetch-side work; the read loses an `es:` |
| the finish dissolve (`bz_fdis`, `bz_fdor`/`bz_fdand`, `bz_fdtab`) | ~245 | needs a part held during play |
| `bz_ltrc` / `bz_ltq0`/`bz_ltq1` derived instead of cached | ~135–400 | reverses 130.13.5.2's no-MUL choice; walk-hot |
| the About card's strings into the shell part | ~200 | `os88ui_about_d` writes an inline cell through DS: needs an `os88ui.inc` opt-in first |
| `%define OP_NO_FSOP` | 39 | a course fetch stops being one progress bar (WireFleet ships so) |

**The enabler most of these share:** a part cannot call package code —
`tools/pxlink.py` exports bss and constants, never a code label. The
precedent is `bz_fmkp` (`bzfam.inc`): a far pointer in bss rewritten before
each far call because the region is movable. Generalised, a resident
`bz_back: call [bx + bz_btab] / retf` (5 bytes, 2 a routine) lets a part
`mov bx, k / call far [bz_bkp]`. A call-back must not claim or fetch
(SPEC.md 20.12.5), and a compaction while `bz_shcall`'s far frame is on the
stack would strand the package's CS — so file I/O, toasts and drawing are
fine and `op_fetch`, `bz_home`/`bz_back`, `bz_launch` stay resident-side.
**Two homes exist for code that runs inside the bracket**: fetched with the
course, or a member of the resident bundle (`bz_fbfind` finds it and makes
its kern_mega code selector; at most 255 paragraphs, `BZF_HPARAS` is a byte).
The shell part never coexists with a course (`bz_shdrop`), so it serves only
the desktop.

**Checked and refused:** a second shell-like part (frees no more window than
widening the shell part, and costs a row, a read and a generalised
`bz_shcall`); an eager `OP_ZERO` row (turns on the carve path, adds code);
shrinking `bz_fhl`/`bz_frec`/`bz_fsl` (the owner's NO FAMILY LIMIT, 130.25.6.5);
bss over one-shot entry code (~180 at most, WM_CREATE may paint during open);
`bz_boxbuf` as a claim (a third segment in the hottest code).
