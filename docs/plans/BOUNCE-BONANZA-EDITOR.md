# BOUNCE BONANZA: the course builder

*The contract is SPEC.md 130.58; where this plan and it disagree, it wins.
The diary is [BOUNCE-BONANZA-EDITOR-DIARY.md](BOUNCE-BONANZA-EDITOR-DIARY.md).
The mockups the owner reviewed are the design canvas
https://claude.ai/artifact/NPuHumAXAJiMoWR6cLAQBq (private to the owner).*

The owner (2026-11-21): a GUI course builder focused on ease of use, every
tile and prop the format has, the shape editor in its own tab; a Python
window like the Video Battle builder; top-down with a toggled height map AND
an isometric view, because authors and agents both fail to see "this
obstructs that" and "this blends into that's square pattern"; Test Roll on
the host; visual checks warn rather than refuse.

## Where it stands

**The editing phase is done (2026-11-21), shaped by four rounds of the owner's testing** (SPEC.md
130.58.10 - 130.58.15). Built so far:

- the model (`tools/bbedproj.py`) and the compiler's warning tier;
- the jobs (`tools/bbedjob.py`);
- the window (`tools/bbedit.py`):
  - select first, then act;
  - the ground as one layer: Make it, Paint, moving ground, joining ramps and rejoining;
  - multi-select, rails and hangs;
  - diagonals;
  - the picture's band;
  - Iso, X-ray, and the Course and Source tabs;
- the zip (`make bbeditbundle`);
- Test Roll in part (`tools/bbplay.py`, the toolbar's Test Roll; SPEC.md 130.58.16): 0.3, and 0.4, 6.1 - 6.4 in part.

**The gap band's overlay is built (3.5, SPEC.md 130.58.21)**, the builder's half of the `bb-visuals`
session's band (SPEC.md 130.57): the Iso view shows every face the band could go on, and a click marks or
unmarks it.

**The Shapes tab is built (4.1, 4.3; 4.2 in part; SPEC.md 130.58.19).**

**Add to the game is built (8.1; 8.2 but for its MartyPC boot; SPEC.md 130.58.17).**

**The blend check is built (3.3, 3.4; SPEC.md 130.58.18).**

**The Map tab is built (7.1; 7.2 but for playing the map; SPEC.md 130.58.20).**

**Next phases**: the rest of the Shapes tab (4.2's Iso blocks), the rest of Test Roll (6), the pathway played (7.2) and
the MartyPC boot of a game with an added course (8.2). `[~]` below marks a story built in part, with what is missing.

**How to run it**: unzip `make bbeditbundle`'s `build/os8088-course-builder.zip` anywhere and run
`python3 bbedit.py` in its folder (SPEC.md 130.58.11), or from a checkout of `bb-editor`,
`python3 tools/bbedit.py apps/bonanza/courses/mill.bbc` - Python 3.11 or newer with Tk and Pillow (macOS: python.org's
Python and `pip3 install pillow`; Windows: `pip install pillow`; Linux: `python3-tk`, `python3-pil`).
The contract (SPEC.md 130.58) and this plan were written first.
Branch `bb-editor`, cut from `bounce-bonanza` at `abe0713d0`, and merged from
`bounce-bonanza` often: the game is changing under it (the VGA arm, the look,
the column and floor distinctions on their way), and E4 of 130.58.1 is what
keeps those changes free - the builder draws nothing the compiler draws.

## The owner's answers (2026-11-21)

1. Line-by-line saving that keeps comments: *"Sounds good."*
2. A changed-on-disk check: *"not super important ... But if it's not
   expensive to add this check, do."* It is cheap; 130.58.3 has it.
3. Re-recording demos an edit makes stale: *"good."*
4. Add to the game: *"does need to be in scope; we can ship the bits needed
   ... with the builder zip release. Check RealDMG ... This can be its own
   wave at the end."* Wave 8.
5. The pathway: *"We need to plan for editing pathway, but it can come as
   its own wave."* Wave 7.
6. Host play checked against MartyPC: *"Ok."*
7. Blending: *"Pattern on floor tiles matching, so visually there is no
   distinction between them, when they are not actually adjoined. Warning
   for this one and visually a way to point it out in the editor."*
   130.58.6.
8. A stale full check: *"Probably canceled ... and they can't pile up."*
   130.58.8.
9. Platforms: where the other Python windows run - macOS (Tk, Pillow),
   Windows, Linux with the dependencies.
10. Branch `bb-editor`, with frequent pulls of `bounce-bonanza`.
11. The `hidden` opt-out in the course format: *"fine to put in the
    format."* A hidden checkpoint WARNS in the builder (secret routes, a
    late-game feature) and is exempt under `--strict` when marked.
12. `--strict` and the ship: *"We're probably going to ship courses that
    don't pass strict ... But exceptions can be course by course; the goal
    in the end is to have good courses."* The Makefile never passes
    `--strict`; agents' runs do; a finished course opts in with `strict`,
    and a course keeps a warning with `accept` (130.58.5).
13. No pull requests: this fork's cycles have none (fork rule 11). Each wave
    is commits on `bb-editor`.

## Measured before planning (host, 4 cores, `abe0713d0`)

| what | MILL | PLAY |
|---|---|---|
| compile without occluders | 0.6 s | **refused**: 1,123 blocks, over 1,024 |
| full compile (changed file, no cache) | 3.5 s | 181 s |
| 100 s of play through `Physics` | 0.034 s | 0.14 s |
| `render()`, one picture | about 0.6 s | about 1 s |

`Physics` reads the compiled PART (`course.cga`), not the parsed source, so
Test Roll needs a part; that is wave 0's question.

## The waves

Each wave is reviewable on its own and lands on `bb-editor` as commits (no pull requests on this fork). Per CLAUDE.md
and fork rule 9: a wave verifies on the host and names its rows; the soak
union runs once at the end of a phase, in the background.

### Wave 0 - the contract and three spikes

| # | story | verified by |
|---|---|---|
| 0.1 [x] | SPEC.md 130.58, this plan, the diary | `tools/checkdocs.py` |
| 0.2 [x] | ROUND TRIP: a line-span reader over `parse()`; every course under `apps/bonanza/courses/` read and written unchanged; one edit of each statement kind and its undo byte-identical | a host script, its table in the diary |
| 0.3 [x] | PLAY-ONLY COMPILE: what `Physics` needs from a part (the grid, the props, the material) and whether a part can be made without the picture's block limit; PLAY's time to first step | the measurement, in the diary; the choice written into 130.58.7 - DONE: occluders off and BLK_MAX lifted is exact in all `Physics` reads (130.58.16.1); PLAY's first frame 8.6 s, MILL's about 1 s |
| 0.4 [~] | THE COMPOSITOR: which guest drawing the frame copies (lanes, ball, shadow, occluder masks, camera window) and whether it can be a function the compiler already has | a frame of MILL drawn on the host beside MartyPC's at the same step - BUILT from the compiler's pieces (130.58.16.2); NOT yet compared with MartyPC |

### Wave 1 - the model and the warning tier (no window)

| # | story | verified by |
|---|---|---|
| 1.1 [x] | `tools/bbedproj.py`: load, save, statements with spans, edit methods for every statement kind, undo/redo, the file stamp | unit rows under `tests/unit/`, round trip on every course |
| 1.2 [x] | its command line (`check`, `set`, `add`, `remove`), JSON out, for agents | the same rows through the CLI |
| 1.3 [x] | `bbcourse.py`: the visual refusals of 130.58.4 become warnings; `--strict` restores them; the Makefile does not pass it | every shipped course's part byte-identical before and after; the warnings each shipped course now prints recorded in the diary; a course with a hidden flag refuses under `--strict`, warns without |
| 1.4 [x] | 130.58.5's statements: `hidden` on `checkpoint` and every element a visibility warning names, `accept <warning> [<wx> <wy>]`, `strict`; no identity moves | `--selfcheck`; identities before and after; a `strict` course with an unaccepted warning refuses in the plain build |
| 1.5 [x] | `tools/bbedjob.py`: a check as a process, JSON progress, cancel by process group (Windows too), the restart rule of 130.58.8 | a scripted burst of edits leaves one process alive |

### Wave 2 - the window and the Build tab, plan view

| # | story | verified by |
|---|---|---|
| 2.1 [x] | the shell: menus, toolbar, the three tabs, status bar with jobs and Cancel, recent files, settings in `~/.config/os8088/bbedit.json` | opened on Linux; a screenshot |
| 2.2 [~] | the palette: seven groups, search, every part of the catalogue board, plain names with the `.bbc` word. BUILT: groups, search, every part, a template each, `uses` added for you. MISSING: the row checking the list against `parse()`; the `.bbc` word shows in the inspector, not the palette | every statement kind placeable; the catalogue's list checked against `parse()`'s statements by a row |
| 2.3 [x] | the plan view: grid, height map toggle and legend, walls, surfaces, route, tubes, props; select, paint, rectangle, erase, pick height, pan, zoom; brushes tile, rect, band, half, quarter. BUILT: all of it, the brushes as Make it, Cut a corner and Diagonal strip (130.58.13 - 130.58.15); pick height is the area's heights | edits through the model only; undo across them |
| 2.4 [~] | inspectors for every part (the inspectors board): segmented choices, sliders with plain readouts, one timeline control, the arrow pad, "More ›" for raw numbers | each statement's clauses reachable. BUILT: one inspector for every statement - position, the numeric clauses, the choices (face, along, channel, style, surface, ball), `hidden`, and the statement box for the rest. MISSING: the timeline control, the arrow pad and per-part layouts |

### Wave 3 - the Iso view, X-ray and the blend check

| # | story | verified by |
|---|---|---|
| 3.1 [x] | Iso: the compiler's picture per adapter (CGA, Hercules, and VGA once rendered), pointer readout from `owners_canvas`, select and place in Iso, one selection across both views | a screenshot on MILL; selecting the wall at 18, 20 in Iso selects it in Plan |
| 3.2 [x] | X-ray and "Hard to see": the visibility audit's covered marks drawn seen / hidden / what hides it; the game's see-through toggle | MILL's tube mouth at 17, 20 (50%, under 18, 20 and 18, 21) shown as on the mockup |
| 3.3 [x] | the blend check in `bbcourse.py` (130.58.6): the definition, the threshold set from the shipped courses, per adapter | a constructed blending pair warns; the shipped courses' result recorded. BUILT (130.58.18): CGA and Hercules, 40 px and 50%; PLAYGROUND and the title blend (reported, not accepted); the row `bbblend`. The VGA arm has no compiler picture to check |
| 3.4 [x] | blending pairs drawn striped in Iso and Plan, from the warning's Show | a screenshot. BUILT: drawn while "Hard to see" is on (both floors hatched in Plan, the seam in Iso); clicking the problem selects the first floor. No per-warning "Show" button yet |
| 3.5 [x] | the gap band's overlay (130.58.21): every candidate face boxed on Iso, filtered by width, a click marks or unmarks it as `gap` lines | the `bbedit` row's item 8; a scripted click on HOP marked `gap tile 28 15 se` and the next picture showed the band |

### Wave 4 - the Shapes tab

| # | story | verified by |
|---|---|---|
| 4.1 [x] | chutes: path points, width, round or banked, depth, the height graph | SHAPE's three chutes round-trip and edit - DONE (130.58.19): the `bbedit` row's item 9, and a scripted session on SHAPE's chute 1 (an end dragged, a leg added) |
| 4.2 [~] | pits, ramps, humps; diagonal blocks and chamfers edited in Iso by default | each kind made from nothing compiles - BUILT: pits and humps (made from nothing, compiled, in the row); ramps are the Build tab's (130.58.13); MISSING: diagonal blocks and chamfers in Iso (the Build tab cuts corners, 130.58.15) |
| 4.3 [x] | how each ball rides a shape: scripted `Physics` runs as a job, read out in words | the readout on SHAPE's chute 1 - DONE: every ball steered through in 5.7 - 7.2 s; let go, each comes to rest on the first leg |

### Wave 5 - the Course tab

| # | story | verified by |
|---|---|---|
| 5.1 [~] | settings: title, name, width, ball, palette, music (listen through `bbmusic.py`), gate style, target, limit, medals, `uses` shown as derived | each writes its statement. MISSING: Listen |
| 5.2 [x] | "Ready to play?": errors and warnings in two lists, Show links, "hidden on purpose", Treat warnings as errors | a course with one of each |
| 5.3 [ ] | stale demos named and re-record offered (130.58.3) | editing MILL names its demo |

### Wave 6 - Test Roll

| # | story | verified by |
|---|---|---|
| 6.1 [x] | the play-only compile of wave 0.3, as a job | PLAY's time to first step, measured - DONE as a `bbplay.py --job` process beside the full compile: PLAY 8.6 s to the first frame (130.58.16.1) |
| 6.2 [~] | `tools/bbplay.py`: the frame loop at `STEP_HZ`, keys, the compositor of wave 0.4, CGA and Hercules, Glide and Trickle | MILL played by hand; a screenshot - BUILT: the loop, keys, compositor, CGA and Hercules, Glide; MISSING: Trickle; MILL driven by the autopilot under Xvfb, and played by hand by the owner (2026-11-21: "test roll works well") |
| 6.3 [~] | start from the course start, a flag or a clicked cell; pause, step, ¼ and ½ speed, rewind, the run's timeline | each used once on MILL - BUILT: the start, a clicked cell (the builder's selection), pause, step, 1/2 and 1/4, rewind 5 s; MISSING: a flag as the start, the timeline |
| 6.4 [~] | ghost of the AUTHOR demo or the best run; save a run as a `.BZR`; make it the AUTHOR demo | a host-recorded run replayed on MartyPC ends where it ended on the host - BUILT: save as `.BZR` and `.bzd`, replayed through `run_log` to the same end; MISSING: the ghost, making it the AUTHOR demo, the MartyPC replay |
| 6.5 [ ] | the fidelity check: the same demo's frames, host against MartyPC, at chosen steps | a row; the box on the Test Roll window says only what it shows |
| 6.6 [ ] | Run on the real game: build the disk and launch MartyPC on it from the window | MILL launched |

### Wave 7 - the pathway

| # | story | verified by |
|---|---|---|
| 7.1 [x] | a Map mode for `path.bbc`: pads, routes (gate, secret, path), icons, lives, pages, view, rail (130.22.2) | the shipped pathway round-trips and one route edits - DONE (130.58.20): the Map tab; the `bbedit` row's item 10; a scripted session dragged pad 1 (its routes followed) and had a pad dropped on pad 0 undone with the reason |
| 7.2 [~] | placing a course on the map: its pad, its route, its icon | a new course reachable on the map in Test Roll's pathway - BUILT: *Put a course on the map* (pad, route on a free exit, icon), `# builder-course:` for a course not in the game, `bbgame.py --path` - and a map with more pads and signs than the shipped one composes (the headroom variants, SPEC.md 130.58.17.1: XTRA on a ninth pad is byte for byte nasm's `BZHEADROOM=1` build of that list and map, the save's pad guard at 9); the full check proves it reachable; MISSING: the pathway played on the host (Test Roll plays courses), and on MartyPC |

### Wave 8 - add to the game, and the zip

| # | story | verified by |
|---|---|---|
| 8.1 [x] | the decision of 130.58.9: a prebuilt package with a data course table, or a course list read off the disk | written into 130.58.17 with its cost in bytes: the prebuilt pieces (`make bbgamebin`), the shipped package 0 bytes changed, an added course 51 resident bytes |
| 8.2 [~] | the builder writes `BONANZA.O88` with the author's courses, and optionally a floppy image (`os88disk.py`) | `tools/bbgame.py`, the Course tab's "Put this course in the game...", `--pad0` for a pad to play it from; row `bbgame`: the shipped list composed is `build/bonanza.o88`, shipped + XTRA and `--pad0 XTRA` are byte for byte the nasm builds of those lists; a pathway with more pads and signs than the shipped map (`--path`, XTRA on a ninth pad) is byte for byte nasm's `BZHEADROOM=1` build, BZ_PATH_NPAD's bytes written from a probe at every count (SPEC.md 130.58.17.1). **Missing**: the package booted in MartyPC playing the new course |
| 8.3 [x] | `make bbeditbundle`: the window, the compiler, its assets and the prebuilt parts in a zip for a machine with no os8088 tree | the zip run on a clean Linux; the macOS and Windows steps written for the owner |

### The final pass

The soak union of the rows the waves named, once, in the background; then
`test-full` once, as the integration branch's rule asks.

## Risks

- **The play-only compile (0.3)**: if no valid part can be made quickly,
  Test Roll waits on the full compile (181 s on PLAY today), and the wave
  needs another answer, perhaps the compiler made faster.
- **The compositor (0.4)**: it is the one copy of the guest's drawing; the
  fidelity row (6.5) is what keeps it honest.
- **The game moving**: `bounce-bonanza` changes the format and the look
  often; a merge that breaks the round trip shows in wave 1's rows.
