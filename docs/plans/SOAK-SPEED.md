# SOAK-SPEED — making each soak row cheaper, one row at a time

**OPEN.** Working notes for the soak-speed pass: every emulator row in the
soak tier, taken one at a time, looked at in depth and made cheaper without
making it less able to fail. The findings here are to be folded into
docs/WRITING-TESTS.md when the pass ends; this file is the raw material, so it
stays short and is rewritten rather than appended to where a technique
generalises.

Background: docs/plans/SOAK-PARALLEL.md §11 (where a row's time goes:
`settle` is ~half of it) and `tests/tmowner.py` (b787057: ~450 s → 41 s by
reading the guest state the page is drawn from instead of pumping the screen).

## How to measure a row

- `python3 tools/os88test.py soak -k <row>` is the wall time; under contention
  (six agents on four cores) wall time is noisy, so also quote **guest
  seconds** - `OS88_WAITLOG=<file>` logs every wait with its call site and
  guest cost, which is the work list.
- Before and after on the same box state; a failing row's time is
  time-to-failure and is not a "before".
- **Prefix `MAKELEVEL=1`** in a shared checkout: a row with `wants=` makes
  `os88test.py` run a plain `make` in `build/` first (and it fails on a
  half-edited doc); `MAKELEVEL` makes it only check the artefacts exist.

## Techniques (numbered; cite by number in the ledger)

1. **Read the state, don't settle the screen.** If what follows a wait is a
   guest-memory read, wait on those bytes (`os88marty.quiesce`) or on the
   flag that says the work is done, not on the framebuffer
   (SOAK-PARALLEL §11.6).
2. **Drive with `tools/os88ui.py`.** Verbs confirm by reading guest state, so
   the check replaces the wait (~0.35x of settle-and-hope).
3. **One boot for the legs that start from the same state.** A boot plus
   opening the package is ~20-30 host s on MartyPC under load; legs that each
   begin "booted, app open, idle" share one if each leaves that state behind
   (and the next ASSERTS it found it). Several files for several legs go on
   one disk, a window closed between them. When the legs diverge right
   after boot (different panel settings), boot once, `m.snapshot()`, run leg
   1, then `m.restore(id, port)` for leg 2 (tests/paintback.py's `run`).
   `os88marty.Forks(m)` packages that (free port, run, quit on exit):
   `with Forks(ui.m) as fk: with fk.restore() as r: leg(os88ui.UI(r))`.
4. **`ui_done` before `settle`, and `ui_done` alone when the next read is
   memory.** `settle`'s short window (~0.6 guest s) only opens if the UI task
   is idle at its FIRST sample; a settle begun mid-repaint paid a full
   `quiet` (~4.5 guest s) - now cut when the UI idles (harness changes), but
   `ui_done` is still ~0.3 guest s cheaper and exact. A test whose every
   assertion is memory can pass `lambda m, **k: os88marty.ui_done(m)` as the
   `settle` the dispcp verbs take (dispprefer).
   Before an `fbuf` read keep the settle (glass lags framebuffer); before a
   `quiesce`/`m.read` the settle can go and the quiesce's `guest=` can drop
   to ~0.3. Typically halves a drive-and-read row. **`m.advance(frames=N)`
   is a blind sleep the waitlog does not even log** (paintrz had ~80 guest s
   of them a row); after an input it is `ui_done`, and where the old wait
   was proving the work happened, assert the state moved instead.
   Work a package posts as `OSAPI_WM_WAKE` slices (Weave's VM) is UI-task
   work, so `ui_done` covers it; a WORKER's drawing (a canvas game) is not.
5. **A wait whose PASS is a timeout is the most expensive line in a row.**
   `until(..., required=False)` / a fixed `cycles` window for "X must NOT
   happen" pays its whole budget (often 30-180 guest s) on every green run.
   End it at `ui_done` (the work X would be part of is finished) plus a
   short guest tail, and break the subject once to see X caught in it.

7. **Log, don't stop, for a timing trace.** A `bp_trace` whose hits only feed
   cycle arithmetic takes `log=True`; data the body must write while the
   guest runs (a script ring) is fed from the `until` condition instead of an
   `on_hit`, with an assert that the guest never read past it.

6. **End a collection window on `os88marty.ui_idle`, not a fixed quiet.**
   A trace that waits N guest s after the last pass for follow-ups can stop
   once ui_task has slept ~0.5 guest s (9 ticks) with every pass closed:
   its follow-ups are its own, and it only sleeps when none is left.
   Keep N as the upper bound for a UI that never idles (Task Manager).

8. **A poll is a host floor per wait.** `until(..., poll=0.3)` costs >= 0.3
   host s even when the guest is there in 0.05 - a row with 60 holds paid
   ~20 s for it. 0.05 (os88ui's own POLL) is a ~1 ms read; never coarser.
   Likewise a breakpoint whose only job is "did X run at all" is disarmed at
   its first hit, not stopped at per row/frame.

9. **A key is taken when the guest has read it, not after a pace.** `key_taken`
   (harness changes); then assert the state the key set. Check fullscreen
   exits: the kernel drains the key ring at the end of `fsx_restore`.

## Harness changes made in this pass

(one line each: what, where, which rows it speeds, how it was validated)

- **Logging breakpoints** (`tools/martypc/debug_server.rs`, deployed in
  `build/martypc/run`): `os88marty.bp_trace(m, ..., log=True)` (or
  `log=[names]` for a subset) has the SERVER note (address, cycles) and resume,
  so a timing trace has no stops - a pumped stop is 2 round trips + the 5 ms
  poll. Cycle-identical to a pumped trace from one snapshot (1,013 records);
  no registers/`on_hit` on a logged hit. excitebike lap: 80 -> 20 host s for
  45 guest s. Falls back to stops on an old server. See technique 7.
- **Stopped-machine round trip 2.3 ms -> 0.15 ms** (same binary): a paused
  server no longer sleeps 2 ms between back-to-back commands, so `call_guest`
  loops, `on_hit` reads and register pokes are ~15x cheaper. Automatic.
- **`os88marty.Forks(m)`**: one boot, N legs from a fork snapshot (pauses `m`,
  `restore()` = a running Marty on a free port, quit on `with` exit; holders
  die with `m`). deskclip 6 boots -> 2; restore is 0.1 s.
- **`UI.still()`** (os88ui): `ui_done` + 3 guest frames - the cheap settle
  before an `fbuf`/`vram` read after an input the UI handles (no 2-host-s
  floor). Not for a worker drawing on its own clock. desk* rows.
- **`os88marty.until`'s default poll is adaptive** (20 ms doubling to 250 ms,
  was a flat 1 s host): every `until` without `poll=` stops paying up to a
  second after its condition is already true. Explicit `poll=` unchanged.
- **`Marty.wait_stop` polls from 1 ms, doubling to `poll`** (was a flat
  20 ms): every `run(); wait_stop()` - a harness-called guest routine
  (`call_guest`, n1942's `Game.call`) - stops paying 20 ms each.
- `OS88_MARTY_BIN=<path>` runs another emulator build in an instance (for
  trying a `debug_server.rs` change before staging it; name it
  `martypc_headless` so the instance registry recognises it).
- **`os88ui.boot(..., quick=True)`**: launched paused, run, and `ui.up()`
  ([spl_live] = 0) is the whole boot gate - no picture settle at all, neither
  launch's nor `ready`'s. VGA XT 360KB: up at ~15 guest s vs launch's settle
  ~20-30. Only when the first act is an os88ui verb or a guest read. Opt-in;
  validated on the 22 vidpage.py rows.

- **`settle`'s long window ends when the UI idles** (`os88marty.settle`):
  spent in 0.2-guest-s slices and cut on `_ui_mark`; a cut window counts for
  nothing (fresh `last`), so the stillness proof is the short-window one an
  idle start gets. dispprefer 287 -> 185 guest s waited with no test change.
  A UI that never idles pays the full window as before.
- **`os88mouse.GAP` 0.12 -> 0.012** (a `pace()` argument: 0.54 -> 0.054
  guest s a packet, the UART needs 0.025; `to` proves arrival anyway). Six
  moves 5.3 -> 1.2 guest s. Every row that moves the pointer. Validated on
  uilayer, martyconc, dispdrag, dispthm, dispprefer.

- **`UI.up` / `kernel_up` need [ticks] to MOVE across the gate** (one tick):
  between the kernel image landing and kmain clearing `.bss`, desk_rows /
  menu_nbar / spl_live are loader junk that passes the old test (XT-IDE boot:
  0.5 guest s of it), and a quick boot's first mouse packet then landed in the
  mouse probe - the pointer never moved again (vidsound hung). Also
  `os88vid.read_frame` has a P4 fast path (bytes inverted, pad bits cleared;
  equal to the per-pixel path on 200 random sizes): 30 ms -> ~0 a frame, which
  was 53 of vidsound's 96 host s - every row that encodes a clip from PBMs.
- **`os88marty.kernel_up(m)`**: os88ui's `up` gate for a bare
  `launch(boot=False)` + `m.run()` caller - desk_rows/menu_nbar live,
  [spl_live] = 0, then `ui_done`; no picture settle. dispseam's four boots.
- **`ui_done(m, lock=False)` / `ui_idle(m, lock=False)`** (os88marty): the UI pass is over without asking the gfx lock - for a GAME whose worker holds it nearly always (Missile: a `ui_done` after a drag ran 110 guest s). The framebuffer is then not promised; settle before a capture. dispmcfs.
- **`os88marty.key_taken(m, name)`**: press a key and return when the guest has TAKEN it - BIOS ring tail moved, head caught up, ui_task asleep with nothing queued (the gfx lock NOT asked, so a package drawing on every tick ends at once); `ui=False, tail=` for a fullscreen loop that reads keys itself; capped at the old `pace(.15)`. `ui_passed(m, cap)` is its last clause alone. The replacement for `m.key(); pace(.15)` + `ui_done(cap=)`. Gorillas family.
- **`Marty.wait_stop`'s nap is capped at 4 ms** (`WAIT_STOP_NAP`, `OS88_WAIT_STOP_NAP`; was doubling to `poll`=20 ms): a few-ms guest routine bracketed by breakpoints paid up to 2x its run in the last nap. gorillasinput's VGA arm 76.5 -> 63.9 s A/B back to back; uilayer, martyconc green.
- **`os88mouse` drag: the PRESS is taken before the pointer moves** (`_press_drag_release`: `ui_done(cap=PRESS_GUEST=3, lock=False)` after the press edge). Since GAP went 0.12 -> 0.012 a drag on a BACKGROUND window sent its move+release into the raise repaint, which read as a click and left the window put: **dispsave FAILED on round 1's GAP change** (passes with GAP=0.12 or with this). No measurable cost (dispsize 112 -> 110 guest s; the wait is ~a tick on a quiet UI). drag/menu/rdrag.
- `tools/redline_profile.py` `wait()`: 5-frame steps for the first guest second, then 30 (same guest bound). The benchmark runs are minutes of guest time and each 5-frame step was a round trip plus the predicate's reads. redline* rows; validated on redlinecga/herc/v20native (pass) and redlinevga (fails identically with the old wait).
- **`tests/weavesmoke.py`'s `_open_bundle` on os88ui verbs, and `booted()`** (a quick boot): the whole Weave family's navigation (weaveprev/session/grid/gfx/one/game/lat). Validated on all eight rows.

## Ledger

| row | before | after | techniques | notes |
|---|---|---|---|---|
| tmowner | ~450 s | 41 s | 1, 2 | b787057, prior to this pass |
| disp: title, blit, brow, depth, thm, fsx, np, save, band, zoom, app, drag, fsxherc, vy, fsxcga, strad, saver | ~30-75 s each (loaded) | 12-45 s (3 lanes, loaded); guest 23-53 | 4 | mechanical: the boot's picture settle -> `kernel_up` where the first act is a click (~5 guest + the 2-host-s floor a row); the rest are lean or capture-bound. **dispsave failed at base** (round 1's GAP: see harness changes) and passes with the drag fix. Re-declared to measured |
| dispclose / dispclose-small / dispcalcx / dispreboot | 33 / - / 49 / 74 s (load); 66 / - / 68 / 45 guest s | 20 / 12 / 35 / 41 s; 42 / 46 / 44 / 33 guest s | 4, 5 | nothing reads the glass (`m.vram` is guest memory): every settle -> `ui_done`, `kernel_up` boots; dispreboot's post-release watch tail 5 -> 1.5 guest s (it already ends only on `ui_idle`). Re-declared 90/100/90/100 -> 20/30/45/60 |
| dispfreeze | 87 s (loaded) / 50 guest s | 18.5 s / 39 guest s | 4, 5 | `alive()`'s pass-counting window (a mem breakpoint STOPPING on every ui_task pass, 2-4 guest s fixed) ends at 3 passes + a moved tick - only a frozen/reset machine pays the window; clicks' settles -> `ui_done`; `kernel_up` boot |
| dispcorner / dispmodex | 166 / 159 s (heavily loaded) / 65 / 69 guest s | 43 / 33 s / 63 / 68 guest s | - | `kernel_up` boot only; the rest is pixel-capture settles (the measurement) and Missile's own quiesces. Re-declared 120 -> 60 / 45 |
| dispapps | 232 s (loaded) / 168 guest s | 33 s / 58 guest s | 4 | three games draw all the time, so settle (98 guest s over two adapter switches) -> `ui_done(lock=False)`; the switched facts are `quiesce`d where read (an early read is RED: before==after fails); `kernel_up` boot. secs 120 -> 45 |
| dispblitp | 49 s / 124 guest s, 2 boots | 23 s / 58 guest s, 1 boot | 3, 4, 8 | both legs (`pt_planar` is one-way) fork the boot after Paint opens instead of re-booting; each leg now ASSERTS its fork is still four planes; setup settles -> `ui_done`, the capture keeps its settle. secs 180 -> 30 |
| dispmcfs | 88 s / 234 guest s | 76 s / 190 guest s | 4, 8 | `kernel_up` boot; settles before window-record reads -> `ui_done(lock=False)` (Missile draws all the time, so plain `ui_done`/settle waited out ~110 guest s of its animation); `state()`'s settles before the lit-pixel counts are the measurement and stay. secs 180 -> 120 |
| dispfrac | 21 s / 45 guest s | 21-56 s (noisy) | - | `kernel_up` boot; the adapter-switch settles vary 17-70 guest s with the fractal rendering and stay (pixels never still). secs 180 -> 60 |
| dispsize | 54 s / 148 guest s (round-1 harness already in; declared 210) | 43 s / 112 guest s | 4 | `kernel_up` boot; every settle -> `ui_done` (all reads are window records / bss) except leg C's capture pair; the rest is four package launches. secs 210 -> 60 |
| excitebikeaudiolap | 450 s / 356 guest s | 126 s / 268 guest s | 3, 7 | the lap traced with logging breakpoints (80 -> 20 host s a lap), the script ring fed from `until`; mute/on laps from one boot (snapshot at the splash); a tightened gate goes red |
| excitebikelap | 237 s / 165 guest s | 88 s / 158 guest s | 7 | as audiolap, one lap an adapter |
| excitebikeperf | 89 s / 134 guest s | 59 s / 85 guest s | 3, 7 | scroll and governor on one boot an adapter (4 -> 2); the scroll trace logged |
| excitebikeselfb | 132 s / 152 guest s | 73 s / 142 guest s | - | stop-per-frame `on_hit` reads (must stop: the state block swaps); the gain is the fast stopped round trip |
| excitebikelapherc / selfbherc / perfherc | 109 / 57 / 41 s | 40 / 54 / 16 s | 3, 7 | as above |
| excitebikeaudio / fm / cap | declared 300 / 300 / 150 | 56 / 40 / 42 s | - | `call_guest`-heavy; the fast stopped round trip and wait_stop's poll alone |
| excitebikeref | declared 170 | 376 s / 528 guest s | - | not reducible: 29,465 steps at the game's own 60 Hz step clock ARE the measurement; re-declared at what it costs |
| excitebikevideo / cga / herc / smallclaim | declared 170 / 150 / 245 / 110; herc 309 s measured | 129 / 102 / 103 / 65 s | 1 | `Game.go`'s 336 tpause waits on the adaptive `until` (was 145 host s of 1 s polls), and its 0.12 s card window a server `advance` instead of a polled guest_sleep + pause |
| excitebikeai / flow / custom (+herc) | declared 180 / 120 / 70 (90 / 60 / 55) | 140 / 171 / 80 (57 / 66 / 49) s | 2 | settles after `open_drive`/`open` (both confirm) dropped or made `ui_done`; flow re-declared UP at what it costs |
| isotronload | 219 s / 199 guest s | 168 s / 139 guest s | 3 | launch and rate legs on one boot a machine (6 -> 3); a settle after `open_drive` (which confirms the listing) dropped. The rest is the 2 s rate windows and the launch itself |
| paintbig | 72 s / 103 guest s | 38 s / 59 guest s | 4 | eight settle+quiesce(1.0) pairs -> ui_done+quiesce(0.3); the 20 guest s left is the boot |
| paintpack | ~180 s, 2 boots (blitpair + paintbig) | 49 s / 67 guest s | 3, 4 | `paintbig --pair` runs blitpair's `check_canvas` (factored out, one copy) on paintbig's own boot; red with one file pixel flipped |
| paintback | 142 s / 129 guest s | 110 guest s (wall unmeasurable at load 14) | 3 | two legs, two boots -> one boot + snapshot/restore; the rest is two picture loads and the panel |
| deskclip | 198 s / 148 guest s waited | 80-115 s (load 12-17) / 78 guest s | 3, 4, 6 | 6 boots -> 2 (Forks); settles before reads -> `dc.still` (ui_done + 3 frames); armed's 13.5-guest-s quiet ends on ui_idle (27 -> 2.4 host s). verify red with 4 VRAM rows poked (64 px) |
| vidscreen | 208 s / 155 guest s | 120 s / 83 guest s | 3 | five screens' clips on one disk, one boot, the player closed between; per-pixel glass compare as numpy arrays (checked equal to the loop; red with the palette shifted) |
| vidscreeno | 232 s | 124 s / 82 guest s | 3 | the same script, `--own` |
| deskwhole | 215 s declared | 117 s (load 14) / 101 guest s waited | 4, 6 | dc's armed/verify gains; four settles -> `dc.still`; boot unsettled. The rest is the seven-window setup |
| dispprefer | 270 s / 461 guest s (load 11) | 208 s / 235 guest s (load 11) | 4 + both harness changes above | all waits memory reads -> `ui_done` as dispcp's `settle`; the switch confirmed on `[vid_kind]` (Set Primary's press was the one unconfirmed click). The rest is 12 VGA/CGA/Herc repaints and panel opens - guest work |
| paintmove | 50 s / 85 guest s | (unchanged) | - | already lean: 35 guest s boot + heapfrag's own work; secs 150 -> 60 |
| paint1blit | 126 guest s, 3 boots | 53 s / 67 guest s | 3, 4 | one disk with both fixtures, one boot + snapshot, an arm per restore; blind `advance(400/300)` -> ui_done; settles -> ui_done (every read is memory). Red with the refuse flags swapped (and proves a restore does not carry the previous arm's poke) |
| desksc | 122 s / 72 host s waited | 106 s / 56 | 4 | boot and both reboots unsettled (`up` + `no_saver`: every read after is guest state); four pre-`fbuf` settles -> `ui.still()`. The rest is three boots and CTRL.DRV loads |
| paintrz, paintrz-1bpp | 282 / 186 s (heavy load) | 54 / 44 s (load ~10) | 4 | five `advance(900)` after Enter/grow -> ui_done (+ a new SETUP check that the size really changed); settles -> ui_done |
| dispcold | 79 s / 131 guest s | 41 s / 73 guest s | 4 | **fails-open at base**: the carpet was clamped to COLD_LEN where the witnesses are COLD_SEG offsets from COLD_VSTART, so LO > HI and ZERO breakpoints were armed - fixed (2,816 now) with an assert. The click watch ends on 1 guest s of `ui_idle` instead of 5 of a free lock |
| deskbench | 89 s / 44 host s waited | 95 s (noise) / 36 | 4 | a MEASUREMENT row: only setup settles before guest reads -> `ui_done`, a double boot settle dropped; the flicker windows and the settles before them are the measurement and stay. Re-declared 180 -> 120 |
| paintblank | 196 s (heavy load), ~180 guest s incl. unlogged windows | 45 s / 60 guest s | 4 | four flat 30-guest-s breakpoint windows -> ui_done + 3 s tail (measured: identical stop counts at ui_done, 0.5-0.7 s, and at 30 s); advance(250/90) -> ui_done |
| paintsu | 137 s (heavy load) incl. an unlogged 180 guest s timeout | 33 s / 55 guest s | 4, 5 | the uncover's "no canvas blit" `until(limit=60)` -> ui_done + 3 s tail; red with `wm_su_segs` zeroed before the close |
| wcdraw (x4) | 26 / 29 / 45 / 42 s | same | - | declared 200 s each; already cheap, re-declared only. **wcdrawwired FAILS at base** (identity: 17 px differ at (593,13)-(597,18) of the content, twice in a row); wcdrawcga failed once in three |
| paintpal | 105 s (heavy load) / 61 guest s | 28 s / 55 guest s | 4 | the zoom pair's settles -> ui_done, settle only before the capture; the rest is the boot (17 guest s) |
| paintdirty | 131 s (load 18) / ~73 guest s incl. 37 unlogged in advance() | 30 s / 36 guest s | 4 | five advance(250/400)+settle -> ui_done; every read is [pt_dirty] or the window list |
| paintcull | 154 s (load 18) / ~38 + 17 unlogged guest s | 40 s / 41 guest s | 4 | advances -> ui_done; the restore's bp_trace now STAYS IN THE BLOCK to ui_done (it exited at the dblclick's return - a pt_topacked after that was unwatched). Red on the NOPLANE tree |
| deskclock / deskclockherc | 182 s + 85 s / 261 guest s waited | 105 s + 46 s / 146 | 4 | `quick=True`; a fixed 0.8-14 guest s sleep per key and click -> `ui.still()` (every assertion after one detects a CHANGE, so an early read goes red); the reset's `ready` -> `up` (a ticking clock made its settle 45 guest s) |
| paintfill | 60 guest s | 50 s (load 16) / 57 guest s | 4 | already lean (boot 20 + load 8 + the fill); idle()'s quiesce+lock-until -> ui_done |
| paintdraw | 45 guest s | 51 s (load 16), unchanged | - | lean: boot + load + its own timed stroke; secs re-declared only |
| dispseam | 430 s (incl. knob build) / 366 guest s | 204-298 s (load 14) / 146 guest s | 4 | four boots (2 machines x fixed/NOSEAMCUT) gated by `kernel_up`; every wait after is `ui_done` - the bars are read from VRAM (`m.vram`), not the glass. The NOSEAMCUT leg is its own red: still loses 18 px |
| isotronperf | 947 s / 634 guest s | 534 s / 409 guest s | 3 | the windowed, full-screen and sweep legs share one boot a machine (12 boots -> 4); the rest is whole traced rounds, which ARE the measurement. A faster bp_trace pump poll (5 -> 0.5 ms) was tried and bought nothing: a stop costs ~1 ms of round trips either way |
| isotronega | 281 s | 225 s | 3 | its windowed and full-screen halves on one boot (both loaded-box walls; declared 110 was an idle figure) |
| paintsize, paintundo(-vga), paintshrink, paint1small, paintanchor, paint1bpp(-colour), paint1load(-vga), paintwalk | blind `advance(60..600)` after the load / zoom / undo / resize, 4-15 unlogged guest s a site | all green, 20-65 s each at load ~15 | 4 | mechanical: advance+run[+settle] -> ui_done, settles -> ui_done unless the next line reads the glass (then ui_done+settle); measurement windows (paintsize's timed restore loop) untouched; secs left as declared |
| vidv2bench | declared 240 s | 18 s / 32 guest s, unchanged | - | already lean (boot 21 guest s + an 8088-exact breakpoint span per frame); secs re-declared only. Its -mx/-4/-1 siblings share the script and are likely the same - measure before re-declaring |
| dispcalc | 173 s / 444 guest s (load ~13, harness changes already in) | 141 s / 375 guest s | 4 | a key is `ui_done(cap=<the old pace>)` instead of a fixed 0.68 guest s; `typed`'s quiesce follows a `ui_done` at guest=0.25. The rest is ~290 keystrokes' real redraws and nine full-repaint diffs |
| deskcal* (8 rows) | 1bpp 176, cards 199, grid 64, edit 295, remind 116, perf 166, snooze 86, task 44 s (3 parallel, load 9-13) | 70, 90, 33, 127, 99, 132, 90, 32 s (load 7-9); guest waited 742 -> 706 | 4 | `quick=True`; Cal.press/type and post-key paces (4.5 guest s each) -> `ui.still`/`ui_done`; grid's 13.5-guest-s refusal windows -> `ui_done` (an accepted PageUp is always landed when it returns: 3/3 checked). Negative 'nothing written' windows and measurement sleeps kept. Rows need `mtools` (installed) |
| vidpage8n | 127 s / waits 96 guest, 81 host | 80 s / 84 guest, 42 host | 2, 8 | `quick=True` boot; polls 0.3 -> 0.05 (60 holds); PAGENK reuses the main clip's bytes instead of regenerating. Same script: all 22 vidpage.py rows green (3 lanes, loaded); only 8n's secs re-declared |
| vidpal / vidplayvga / vidpreview / vidpagetext4 | 142 / 86 / 105 / 51 s (waits 117 / 77 / 82 / 51 guest) | 79 / 39 / 60 / 33 s (99 / 58 / 75 / 35 guest) | 2, 8 | same two; vidpal's 640x480 per-hold glass compare vectorised with numpy (same count and box, checked against the loop on noisy frames; loop kept as fallback). Loaded-box walls, base and new run back to back |
| vidposter, vidpage | 162 s / 124 guest; 71 s / 72 guest | 184 s / 115 guest; 90 s / 72 guest | 2, 8 | no real gain: 11 package launches at ~4.3 guest s each + poster loads are the guest's disk work; wall is load noise. Floor is guest-bound |
| skieshaze | 110 s / waits 41 guest | 53 s / 29 guest | 2, 8 | `cs_hzfill` breakpoint disarmed after its first hit (it only proves the fill runs; it stopped once per split row of 77 frames). `--clobber-ends` still FAILS (69 frames, worst 13 bytes). Secs 187 -> 70 |
| skies (+ every skies*.py) | skies 66 s / 37 guest | 49 s / 25 guest | 2 | `quick=True` on the 29 os88ui.boot scripts; `skies.open_game` (6 launch-based scripts) is `ui.up` + `ui.path` instead of four dispcp settles, launched `boot=False`. Whole skie family run green after; secs left as declared |
| redline (cga, herc, v20native) | cga 172 s | cga 148 s; herc 222, v20 233 (loaded) | - | the guest benchmark runs (two full runs, the rerun is a tested behaviour) ARE the row; only the poll step shrank. **redlinevga FAILS at base**: `ru_buttons+10 == 2` (held press, redline.py:312), identically with the old wait |
| gorillas | 180 s / 352 guest s waited + ~175 unlogged in key paces | 110 s / 300 | 2, 9 | `key_taken` for ~330 keys (0.675 guest pace + up to 0.5 ui_done cap each -> 0.07); `quick=True`. A windowed key now waits `[fsx_task]` = 0xFF first: `fsx_restore` DRAINS the key ring after `[gr_fs]` clears, so a key in that window was eaten (gorillasfront went red on it) |
| gorillasfront / menu / input / reactions / music / city | declared 305 / 160 / 300 / 300 / 253 / 100 | 78 / 156 / 160 / 157 / 62 / 66 s (load 5-7) | 2, 9 | the same `key`; menu/input's post-measure `pace+ui_done` -> `ui_passed`; menu needed a `ui_done` after `[gr_state]`=5 (state is set before the setup text). input/reactions are ~70% `check_repaint`'s VGA plane readback (153,600 bytes through a guest stub, 4 reads a key) - a debug-server plane read would be the next win |
| weavepack | 67 s / 250 guest s waited (declared 1,500) | 51 s / 160 | 2, 4 | os88ui verbs (`open` confirms LOOM's window, `close` its record) and `ui_done` after ^P - Pack runs whole on the UI task - instead of three settles; quick boot. The rest is eleven LOOM launches and their packs |
| weaveprev | 79 s / 283 guest s waited | 53 s / 190 | 2, 3, 4 | six boots -> two (Forks a project); the Preview's two settles -> `ui_done` (compile + module read are UI-task); every read is `m.vram`. The rest is three LOOM launches and Previews a machine |
| weavesession | 28 s / 91 | 24 s / 66 | 2, 4 | six settles -> `ui_done` (the VM drains in WM_ONWAKE slices on the UI task; FORM has no canvas) |
| weavegrid / weavegfx | 31 / 37 s; 93 / 112 guest | 24 / 27 s; 60 / 71 | 2, 3, 4 | grid: settles and `_park`'s -> `ui_done`; gfx: four boots -> two (Forks) |
| weavesmoke / weaveone / weavegame / weavelat | 71 / 15 / 11 / - s | 33 / 16 / 10 / 13 s | 2 | the shared `_open_bundle` + quick boot only; one/game/lat were already lean - re-declared |
| viddisk family (10 rows) | viddiskfd 253 s / 750 guest; wseq 106 / 381 | 192 / 750; all ten green | 8 | bench rows: W and R ARE the measurement (575 + 104 guest s of 750). Boots launched paused with `up` + `ui_done` as the gate (an HDD boot publishes B:'s zone after [spl_live] falls - `up` alone found none); polls 2.0/1.0 -> 0.25. ~4 guest s a boot, nothing more to take |
| pxfsx | 242 s / 475 guest s waited (declared 1,500) | 207 s / 512 | 8 | guest-bound: 26 full-screen renders (209 guest s, a 640x480x16 one is 26 s of 8088) and a slideshow ARE the row; quick boot (54 -> 42 guest) and polls 0.3-0.5 -> 0.05. The baseline's 'Memory:' look costs a 5.5-s retry or two either way. Re-declared |

## Resuming

The six work queues and the agent brief that drove the first session are in
`docs/plans/soak-speed-queues/`: each row is prefixed `DONE`, `SKIP <why>` or
nothing (open). Rows marked `DONE(script changed, row not re-run)` carry a
shared script edit and need one run to confirm. Run every row as
`MAKELEVEL=1 python3 tools/os88test.py soak -k <row>` in a shared checkout.
