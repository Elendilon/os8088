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

5. **Log, don't stop, for a timing trace.** A `bp_trace` whose hits only feed
   cycle arithmetic takes `log=True`; data the body must write while the
   guest runs (a script ring) is fed from the `until` condition instead of an
   `on_hit`, with an assert that the guest never read past it.

6. **End a collection window on `os88marty.ui_idle`, not a fixed quiet.**
   A trace that waits N guest s after the last pass for follow-ups can stop
   once ui_task has slept ~0.5 guest s (9 ticks) with every pass closed:
   its follow-ups are its own, and it only sleeps when none is left.
   Keep N as the upper bound for a UI that never idles (Task Manager).

## Harness changes made in this pass

(one line each: what, where, which rows it speeds, how it was validated)

- **Logging breakpoints** (`tools/martypc/debug_server.rs`, deployed in
  `build/martypc/run`): `os88marty.bp_trace(m, ..., log=True)` (or
  `log=[names]` for a subset) has the SERVER note (address, cycles) and resume,
  so a timing trace has no stops - a pumped stop is 2 round trips + the 5 ms
  poll. Cycle-identical to a pumped trace from one snapshot (1,013 records);
  no registers/`on_hit` on a logged hit. excitebike lap: 80 -> 20 host s for
  45 guest s. Falls back to stops on an old server. See technique 5.
- **Stopped-machine round trip 2.3 ms -> 0.15 ms** (same binary): a paused
  server no longer sleeps 2 ms between back-to-back commands, so `call_guest`
  loops, `on_hit` reads and register pokes are ~15x cheaper. Automatic.
- **`os88marty.Forks(m)`**: one boot, N legs from a fork snapshot (pauses `m`,
  `restore()` = a running Marty on a free port, quit on `with` exit; holders
  die with `m`). deskclip 6 boots -> 2; restore is 0.1 s.
- **`UI.still()`** (os88ui): `ui_done` + 3 guest frames - the cheap settle
  before an `fbuf`/`vram` read after an input the UI handles (no 2-host-s
  floor). Not for a worker drawing on its own clock. desk* rows.
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

## Ledger

| row | before | after | techniques | notes |
|---|---|---|---|---|
| tmowner | ~450 s | 41 s | 1, 2 | b787057, prior to this pass |
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
