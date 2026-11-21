# BOUNCE BONANZA: the course builder

*The contract is SPEC.md 130.55; where this plan and it disagree, it wins.
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

**The first GUI build is ready for the owner to test (2026-11-21).** Built: the model
(`tools/bbedproj.py`), the warning tier in the compiler, the jobs (`tools/bbedjob.py`) and the
window (`tools/bbedit.py`) with its Build tab (Plan and Iso views, X-ray, placing, moving, the
inspector), Course tab and Source tab. Not built yet: the blend check, the Shapes tab, Test Roll,
the pathway editor and add-to-the-game. `[~]` below marks a story built in part, with what is
missing.

**How to run it**: from a checkout of `bb-editor`, `python3 tools/bbedit.py
apps/bonanza/courses/mill.bbc` - Python 3.11 or newer with Tk and Pillow (macOS: python.org's
Python and `pip3 install pillow`; Windows: `pip install pillow`; Linux: `python3-tk`, `python3-pil`).
The contract (SPEC.md 130.55) and this plan were written first.
Branch `bb-editor`, cut from `bounce-bonanza` at `abe0713d0`, and merged from
`bounce-bonanza` often: the game is changing under it (the VGA arm, the look,
the column and floor distinctions on their way), and E4 of 130.55.1 is what
keeps those changes free - the builder draws nothing the compiler draws.

## The owner's answers (2026-11-21)

1. Line-by-line saving that keeps comments: *"Sounds good."*
2. A changed-on-disk check: *"not super important ... But if it's not
   expensive to add this check, do."* It is cheap; 130.55.3 has it.
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
   130.55.6.
8. A stale full check: *"Probably canceled ... and they can't pile up."*
   130.55.8.
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
    and a course keeps a warning with `accept` (130.55.5).
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
| 0.1 [x] | SPEC.md 130.55, this plan, the diary | `tools/checkdocs.py` |
| 0.2 [x] | ROUND TRIP: a line-span reader over `parse()`; every course under `apps/bonanza/courses/` read and written unchanged; one edit of each statement kind and its undo byte-identical | a host script, its table in the diary |
| 0.3 [ ] | PLAY-ONLY COMPILE: what `Physics` needs from a part (the grid, the props, the material) and whether a part can be made without the picture's block limit; PLAY's time to first step | the measurement, in the diary; the choice written into 130.55.7 |
| 0.4 [ ] | THE COMPOSITOR: which guest drawing the frame copies (lanes, ball, shadow, occluder masks, camera window) and whether it can be a function the compiler already has | a frame of MILL drawn on the host beside MartyPC's at the same step |

### Wave 1 - the model and the warning tier (no window)

| # | story | verified by |
|---|---|---|
| 1.1 [x] | `tools/bbedproj.py`: load, save, statements with spans, edit methods for every statement kind, undo/redo, the file stamp | unit rows under `tests/unit/`, round trip on every course |
| 1.2 [x] | its command line (`check`, `set`, `add`, `remove`), JSON out, for agents | the same rows through the CLI |
| 1.3 [x] | `bbcourse.py`: the visual refusals of 130.55.4 become warnings; `--strict` restores them; the Makefile does not pass it | every shipped course's part byte-identical before and after; the warnings each shipped course now prints recorded in the diary; a course with a hidden flag refuses under `--strict`, warns without |
| 1.4 [x] | 130.55.5's statements: `hidden` on `checkpoint` and every element a visibility warning names, `accept <warning> [<wx> <wy>]`, `strict`; no identity moves | `--selfcheck`; identities before and after; a `strict` course with an unaccepted warning refuses in the plain build |
| 1.5 [x] | `tools/bbedjob.py`: a check as a process, JSON progress, cancel by process group (Windows too), the restart rule of 130.55.8 | a scripted burst of edits leaves one process alive |

### Wave 2 - the window and the Build tab, plan view

| # | story | verified by |
|---|---|---|
| 2.1 [x] | the shell: menus, toolbar, the three tabs, status bar with jobs and Cancel, recent files, settings in `~/.config/os8088/bbedit.json` | opened on Linux; a screenshot |
| 2.2 [~] | the palette: seven groups, search, every part of the catalogue board, plain names with the `.bbc` word. BUILT: groups, search, every part, a template each, `uses` added for you. MISSING: the row checking the list against `parse()`; the `.bbc` word shows in the inspector, not the palette | every statement kind placeable; the catalogue's list checked against `parse()`'s statements by a row |
| 2.3 [~] | the plan view: grid, height map toggle and legend, walls, surfaces, route, tubes, props; select, paint, rectangle, erase, pick height, pan, zoom; brushes tile, rect, band, half, quarter. BUILT: all but the legend, pick height and the band, half and quarter brushes (those are typed in the statement box for now) | edits through the model only; undo across them |
| 2.4 [~] | inspectors for every part (the inspectors board): segmented choices, sliders with plain readouts, one timeline control, the arrow pad, "More ›" for raw numbers | each statement's clauses reachable. BUILT: one inspector for every statement - position, the numeric clauses, the choices (face, along, channel, style, surface, ball), `hidden`, and the statement box for the rest. MISSING: the timeline control, the arrow pad and per-part layouts |

### Wave 3 - the Iso view, X-ray and the blend check

| # | story | verified by |
|---|---|---|
| 3.1 [x] | Iso: the compiler's picture per adapter (CGA, Hercules, and VGA once rendered), pointer readout from `owners_canvas`, select and place in Iso, one selection across both views | a screenshot on MILL; selecting the wall at 18, 20 in Iso selects it in Plan |
| 3.2 [x] | X-ray and "Hard to see": the visibility audit's covered marks drawn seen / hidden / what hides it; the game's see-through toggle | MILL's tube mouth at 17, 20 (50%, under 18, 20 and 18, 21) shown as on the mockup |
| 3.3 [ ] | the blend check in `bbcourse.py` (130.55.6): the definition, the threshold set from the shipped courses, per adapter | a constructed blending pair warns; the shipped courses' result recorded |
| 3.4 [ ] | blending pairs drawn striped in Iso and Plan, from the warning's Show | a screenshot |

### Wave 4 - the Shapes tab

| # | story | verified by |
|---|---|---|
| 4.1 [ ] | chutes: path points, width, round or banked, depth, the height graph | SHAPE's three chutes round-trip and edit |
| 4.2 [ ] | pits, ramps, humps; diagonal blocks and chamfers edited in Iso by default | each kind made from nothing compiles |
| 4.3 [ ] | how each ball rides a shape: scripted `Physics` runs as a job, read out in words | the readout on SHAPE's chute 1 |

### Wave 5 - the Course tab

| # | story | verified by |
|---|---|---|
| 5.1 [~] | settings: title, name, width, ball, palette, music (listen through `bbmusic.py`), gate style, target, limit, medals, `uses` shown as derived | each writes its statement. MISSING: Listen |
| 5.2 [x] | "Ready to play?": errors and warnings in two lists, Show links, "hidden on purpose", Treat warnings as errors | a course with one of each |
| 5.3 [ ] | stale demos named and re-record offered (130.55.3) | editing MILL names its demo |

### Wave 6 - Test Roll

| # | story | verified by |
|---|---|---|
| 6.1 [ ] | the play-only compile of wave 0.3, as a job | PLAY's time to first step, measured |
| 6.2 [ ] | `tools/bbplay.py`: the frame loop at `STEP_HZ`, keys, the compositor of wave 0.4, CGA and Hercules, Glide and Trickle | MILL played by hand; a screenshot |
| 6.3 [ ] | start from the course start, a flag or a clicked cell; pause, step, ¼ and ½ speed, rewind, the run's timeline | each used once on MILL |
| 6.4 [ ] | ghost of the AUTHOR demo or the best run; save a run as a `.BZR`; make it the AUTHOR demo | a host-recorded run replayed on MartyPC ends where it ended on the host |
| 6.5 [ ] | the fidelity check: the same demo's frames, host against MartyPC, at chosen steps | a row; the box on the Test Roll window says only what it shows |
| 6.6 [ ] | Run on the real game: build the disk and launch MartyPC on it from the window | MILL launched |

### Wave 7 - the pathway

| # | story | verified by |
|---|---|---|
| 7.1 [ ] | a Map mode for `path.bbc`: pads, routes (gate, secret, path), icons, lives, pages, view, rail (130.22.2) | the shipped pathway round-trips and one route edits |
| 7.2 [ ] | placing a course on the map: its pad, its route, its icon | a new course reachable on the map in Test Roll's pathway |

### Wave 8 - add to the game, and the zip

| # | story | verified by |
|---|---|---|
| 8.1 [ ] | the decision of 130.55.9: a prebuilt package with a data course table, or a course list read off the disk | written into 130.55.9 with its cost in bytes |
| 8.2 [ ] | the builder writes `BONANZA.O88` with the author's courses, and optionally a floppy image (`os88disk.py`) | the package boots in MartyPC and plays the new course |
| 8.3 [ ] | `make bbeditbundle`: the window, the compiler, its assets and the prebuilt parts in a zip for a machine with no os8088 tree | the zip run on a clean Linux; the macOS and Windows steps written for the owner |

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
