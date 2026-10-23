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
   (SOAK-PARALLEL §11.6). Put `m.disk().get("reads")` in the quiesce key
   when the work can stall on the drive with nothing changing (a DOS-box
   command: dosdirsw, dosopen).
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

10. **Profile the HOST before the guest.** When wall >> waitlog host total,
   `python3 -m cProfile -s tottime tests/<row>.py <args>`: fixture making
   (clip encoding, PBM parsing, per-sample Python loops over a capture) was
   2/3 of vidsound's wall. Vectorise it (numpy, `bytes.translate`) and check
   it equal to the loop it replaces.
11. **Ask `os88build.tree()` once per configuration per process.** A warm
   tree still costs a `make` to prove it current (~17 host s loaded); a row
   asking for the same knobs again pays it again (bootfloor: 12 asks, 5 trees).
12. **`launch(boot=<N>)` is a blind N-second pace** (cProfile: 64 of
   fishedge's 69 s were `time.sleep` inside it). `boot=False`, `m.run()`,
   `kernel_up(m)`. `grep -n 'boot=[1-9]' tests/*.py` lists the rest.

13. **`click(..., settle=N)` is a fixed N x 4.5 guest-s pace.** Spell it
   `click(..., settle=0); ui_done(m, cap=N * 4.5)`: ends when the UI idles,
   never waits longer than before, and still ends on a knob kernel whose UI
   never idles (knobhd's MOUDIAG). hdsize 196 -> 75 guest s.

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
- **`UI.chooser()` ends on `still()`, not `settle()`**: the chooser's paint
  is inside the pass that showed it. fdlgchoose 186 -> 116 guest s with its
  own settles; validated on the six fdlg rows, editmove, sbar, wimgtrip, lzmod.
- **`pxslib.open_game` takes an UNBOOTED machine**: `launch(..., boot=False)`
  -> it runs it and gates on `kernel_up` instead of a picture settle (a
  booted one is settled as before). `tools/pxsart.py` memoises
  `nearest_index` and `load_sprite` (outputs checked equal): 80+ host s of
  pxssim's 134 was the sprite set re-parsed per scene. Every pxs* row.
- **`os88marty.text_taken(m, text)`**: `key_taken` for a string - typed paused, the BIOS ring tail followed one entry a character, head caught up, then `ui_done`; bounded at `cap` a character. Replaces `type_text(); settle()` before a read or click. kdmouse.
- **`os88marty.kernel_up(m)`**: os88ui's `up` gate for a bare
  `launch(boot=False)` + `m.run()` caller - desk_rows/menu_nbar live,
  [spl_live] = 0, then `ui_done`; no picture settle. dispseam's four boots.
- **`ui_done(m, lock=False)` / `ui_idle(m, lock=False)`** (os88marty): the UI pass is over without asking the gfx lock - for a GAME whose worker holds it nearly always (Missile: a `ui_done` after a drag ran 110 guest s). The framebuffer is then not promised; settle before a capture. dispmcfs.
- **`os88marty.key_taken(m, name)`**: press a key and return when the guest has TAKEN it - BIOS ring tail moved, head caught up, ui_task asleep with nothing queued (the gfx lock NOT asked, so a package drawing on every tick ends at once); `ui=False, tail=` for a fullscreen loop that reads keys itself; capped at the old `pace(.15)`. `ui_passed(m, cap)` is its last clause alone. The replacement for `m.key(); pace(.15)` + `ui_done(cap=)`. Gorillas family.
- **`Marty.wait_stop`'s nap is capped at 4 ms** (`WAIT_STOP_NAP`, `OS88_WAIT_STOP_NAP`; was doubling to `poll`=20 ms): a few-ms guest routine bracketed by breakpoints paid up to 2x its run in the last nap. gorillasinput's VGA arm 76.5 -> 63.9 s A/B back to back; uilayer, martyconc green.
- **`os88mouse` drag: the PRESS is taken before the pointer moves** (`_press_drag_release`: `ui_done(cap=PRESS_GUEST=3, lock=False)` after the press edge). Since GAP went 0.12 -> 0.012 a drag on a BACKGROUND window sent its move+release into the raise repaint, which read as a click and left the window put: **dispsave FAILED on round 1's GAP change** (passes with GAP=0.12 or with this). No measurable cost (dispsize 112 -> 110 guest s; the wait is ~a tick on a quiet UI). drag/menu/rdrag.
- `tools/redline_profile.py` `wait()`: 5-frame steps for the first guest second, then 30 (same guest bound). The benchmark runs are minutes of guest time and each 5-frame step was a round trip plus the predicate's reads. redline* rows; validated on redlinecga/herc/v20native (pass) and redlinevga (fails identically with the old wait).
- **`tests/weavesmoke.py`'s `_open_bundle` on os88ui verbs, and `booted()`** (a quick boot): the whole Weave family's navigation (weaveprev/session/grid/gfx/one/game/lat). Validated on all eight rows.
- **`Marty.planes(offset, length, planes, card)`** (os88marty) + the server's `planes` verb (`tools/martypc/debug_server.rs`, deployed in `build/martypc/run`): VGA/EGA bit planes straight out of the card's VRAM - no guest cycle, register or latch, exact running or stopped. Falls back to a REP MOVSW guest stub given `stub=(seg, code, scratch, size)` on an older server (`use_stub=True` forces it). Byte-identical to the stub on a desktop with four distinct planes written; a whole 12h screen 0.007 s vs the stub's 0.11-0.15 s. gorillasinput/reactions 108 -> 86 CPU s together; **gorillasmenu keeps the stub** - with the zero-time read its VGA arm's second measured key never reaches gr_key (port 60h empty, IRQ1 idle; unexplained). check_repaint now also parks back at the handler's return (prefetch), which the stub's own park used to supply.
- **`Marty.batch([cmd dicts])`** (os88marty) + a pipelining server (`debug_server.rs`, deployed): several requests in ONE write, replies in order, first refusal raised by index, a `run` in it marks the resume like `run()`. The server now sets TCP_NODELAY (a pipelined burst had every reply after the first held ~40 ms by Nagle against delayed ACK - pipelining "hung") and keeps a line split across reads (it was dropped). 25 reads: 0.3 ms pipelined vs 3.1 ms serial. An old server (no `pipeline` in `ping`) is asked one at a time. n1942's `Game.call` (park + 13 setregs + bp + run + restore) is 4 round trips: 1942sound 105 -> 90 s, same figures as the old path. Any stopped-machine register/park sequence wants it.

## Ledger

| row | before | after | techniques | notes |
|---|---|---|---|---|
| tmowner | ~450 s | 41 s | 1, 2 | b787057, prior to this pass |
| 18 small rows: btngesture, vgadrop, btnmove, apple2part, cychs, pkgrun, call5, dosirq, evqfull, lzfile, mediadisk, tmload, tpstore, radio, fmtreach, imgswap, toastbar, sizesnap | declared 20-45 s | all green, 3-27 s each (in 3 lanes) | 4, quick boot | mechanical state boots, one measure each, re-declared. kdbigexe (19.5 s) re-declared only: `quick=True` breaks it (`up()` resolves its symbols against the kern_dos map the row points os88sym at). **romnodisk fails at base** (os88rom: the ROM cut disagrees with build/'s kernel at offset 0x54) |
| 29 small rows: clipkeep, cppromise, ems(+pico), dos{exe,exec,envfold,arena,est,attr,altenter}, kdcwd, desk{fdd,pen,item,modal}, lzdrv(+nohint), pxsperf, trkload, vidresident(+cga,vga), vidwin(+shd), rdmove, rdmount, clipgrow, trklcd | declared 16-56 s | all green, 7-66 s each (29 in 3 lanes, load ~8) | 4, quick boot | mechanical: `quick=True` / `kernel_up` boots (the first act a verb or a guest read; deskfdd `still()`s after, as it reads its zones off the glass too). One measure each, re-declared |
| curshape / extdmod / fsxdisp / pkgbig / linecar / rdup / drvup / tmdmg / mouseup / fmpatch / gfxptsmall | 109 / 76 / 60 / 39 / 34 / 34 / 30 / 28 / 22 / 18 / 16 s (11 in 3 lanes, load ~8) | 16 / 45 / 34 / 35 / 24 / 23 / 18 / 26 / 15 / 8 / (16) s | 4 | boots on state (`kernel_up` / `quick=True`); curshape's settles under a running MISSILE (103 guest s for one) -> `ui_done(lock=False)`: every read is `[cur_shape]`. gfxptsmall already lean, re-declared |
| pxsmd / stk0water / rdcz / hdauto / gbkeys / kdmredraw / sndplay / fmtlow | 69 / 26 / 49 / 113 / 103 / 55 / 23 / 87 s (3 lanes, load ~8); guest 67 / 41 / 75 / 185 / 120 / 78 / 22 / 28 | 65 / 15 / 26 / 77 / 74 / 35 / 23 / 70 s; 60 / 30 / 52 / 164 / 110 / 69 / 15 / 16 | 4, 8, 9 | boots on state (`kernel_up` / `quick=True`; hdauto's six boots each settled 33 guest s); settles before memory reads (panel verbs, Note Pad's fill, the stack's water, SYSTEM.CFG flushes, fmtlow's FS_EDIT) -> `ui_done`; pxsmd keeps its settles inside the brackets; gbkeys' 2-guest-s start poll -> `until`; kdmredraw's report poll 0.5 -> 0.05 |
| thm95 | 197 s / 190 guest s waited (3 lanes) | legs A+B 102 guest s waited for all five legs' worth before | 4, quick boot | the two knob-tree boots (A, B) `quick=True`; settles before an `fbuf` grab -> `ui.still()`, the rest (window records, z-order, a bp_trace cost loop, `m.vram`) -> `ui_done`. After build/ was re-synced (a stray rebuild of `build/ctrl.drv` had broken the Control Panel), legs C-E took the same: whole row **87 s / 139 guest s** |
| alertbtn / alertanim / btncp / dosram / gbwindow / tgui / lzload-lz4 / rdicon | 95 / - / 14 / 44 / 106 / 13 / 69 / 107 s (8 in 3 lanes, load ~8); guest waited 31 / - / 17 / 76 / 174 / 26 / 87 / 56 | 50 / 27 / 17 / 38 / 110 / 21 / 58 / 29 s; 24 / 15 / 16 / 30 / 156 / 18 / ~10 / 35 | 4, 12 | boots on state (`kernel_up` / `quick=True`); alertbtn's blind `advance(250/400)` -> until Paint runs / the alert's window + `ui_done`; dosram's 13 settles -> `ui_done` (none after the association open: it RUNS the program in an fsx bracket, so the UI does not idle); lzload's waits `ui_done(lock=False)` (FRACTAL draws for ever - a settle after it was 40 guest s); rdicon's `quiet` -> `ui_done`; gbwindow's 2-guest-s start poll -> `until`. gbwindow's rest is the game's own windows |
| calcflick / schacct / socktest / mcseg | 18 / 8 / 20 / 15 s (declared 90 each) | 16 / 8 / 17 / 13 s | 4 | already lean; boots gated on `kernel_up` (calcflick, socktest, mcseg; the same FLASH figures), socktest's Control Panel settles -> `ui_done`. schacct's boot settle stays: its first reading IS the bare settled desktop |
| czto / vidmsync / gfxewalk | 157 / 85 / 52 s (3 lanes, load ~8) | 106 / 59 / 45 s (same) | 4, 8 | czto: `quick=True`, its seven `ui.settle()` -> `ui_done` (every read is the claim, the mode, the toast or a flushed volume), polls 0.2 -> 0.05; vidmsync: launch's settle + `ready` -> `up` + `ui_done`; gfxewalk: `kernel_up` boots, dispcp verbs on `ui_done`. The rest: czto's joins, vidmsync's plays, gfxewalk's trace windows |
| msegz / msegw / msegwz (+ their 360 arms, same script) | 20 / 17 / 19 s at load ~12, 6-7 s CPU, ~20 guest s | unchanged | - | lean: one boot settle and a launch. Re-declared 60 -> 30 (six rows) |
| fcpcopy / fcpsmall (+ hddcp, fmcommit, tgplay, trkbigmod, rehomemove(360), dosglyph, vidxdisp, trktxsurf measured) | fcpcopy 74 s / 125 guest s, fcpsmall 59 / 60 | 33 s / 112, 20 s / 38 | 4 | fcpcopy.py: the Edit pick's menu settle (a fixed 9 guest s) and the screen settle after it -> `settle=0` + `ui_done(limit=300)` (a paste runs inside the menu body, so ui_task is not asleep until it is over; the [fcp_busy] until then only confirms); `kernel_up` boot; no glass read anywhere. The others lean (CPU 12-56 s), re-declared. **imgmount FAILS at base** ("the MOUNT clears what the earlier kernel's stop left [(33, 193)]") |
| diskclone | 41 s / 186 guest, 63 host s waited (load 9) | 41 s / 163, 38 | 4, 9 | every settle -> `key_taken` + `ui_done` (all reads are guest state or a disk flush); `kernel_up` boot. 119 guest s left are the three clone passes themselves |
| fatwpin | 173.9 s (load ~6) / 132 host s waited | 19.9 s (load 8, warm trees) / 65 guest, 14 host | 4, 8, 11 | the plain arm and the shed phase asked for two private trees (different targets = different keys): one tree with all three images; boot's settle -> `ui_done` (every read is State); dispcp verbs -> `ui_done`; polls 0.2 -> 0.05 |
| dosmem / dosmedia / timerbounce / btnall / kdmcur | 35 / 26 / 24 / 58 / 46 s at load ~12; CPU 18 / 10 / 10 / 30 / 21 s | unchanged | - | lean; re-declared 90/90/90/95/90 -> 45/30/30/70/60. **rombig fails at base, environment**: `os88rom.py` refuses `build/kernel-full.bin` (.text differs) because the prebuilt kernel carries an older commit-count build number and os88rom, unlike os88sym, does not substitute it |
| wdclick / wdpen | 97.6 / 33.2 s (load ~6); ~70 / ~38 guest s waited | 57.9 / 11.7 s; 32 / 28 | 4, 8 | boots gated on `kernel_up` (wdpen settled twice); open verbs -> `ui_done`; a capture on CGA/MDA reads video memory, so its settle -> `ui_done` (the fbuf arm keeps the settle); `done()`'s 277 polls 0.05 -> 0.01 host |
| kdmouse / kdnomouse | 41.6 / - s (declared 120 / 45) | 17.9 / 15.9 s; 88 guest s for both | 2, 4, 8 | `quick=True`; the DOS window's eight settles -> `ui_done`, its two typed strings -> `text_taken` (new); the line poll 0.2 -> 0.05 |
| pxswin / pxswin-price / ldcost / fptest / wdcaret / paccman | 70 / 64 / 28 / 20 / 76 / 66 s at load ~12; CPU 51 / 27 / 11 / 8 / 42 / 32 s | unchanged | - | lean: boot settles + the subject (PIXELSTEIN frames, Word's 333 gesture holds, capture settles). pxswin rides pxslib's 0.05 polls already. Re-declared 120/-/120/120/110/100 -> 90/-/30/30/90/80 |
| drmario / drmarioaudio | 92 / 89 s; 58 / 99 guest s; CPU 52 / 51 | 73 / 69 s; 47 / 81 guest s; CPU 45 / 43 | 2 | `quick=True` on the boots (also drmario_front's). **drmariofront FAILS at base**: `build/drmario-art/preview/drmarco-vga-splash.png` is missing - an artefact the row reads and no `wants=` declares |
| brtoolbar / brrace / brfetch / brpromise / brtest | 8.6 / 76 / 35 / 21 / 13 s; 184 guest s waited for the five | 12 / 66 / 29 / 23 / 13 s (5 in 3 lanes); 154 | 4 | boots gated on `kernel_up` (15-20 guest s of settle each); open verbs' settles -> `ui_done` where the next read is the window list. The rest is the partner link's host-stepped work and pre-capture settles |
| dockmodule / dockmark / fddpage | 21 / 25 / 40 s; 59 / 50 / 108 guest s | unchanged | - | lean (boot settles + the subject); dockmodule already rides dockpos's `ui_done` verbs. Re-declared 120/90/120 -> 30/30/60 |
| mouresume | 15.5 s / 56 guest s waited (declared 150) | 13.4 s / 49 | 4, 8 | boot gated on `ui.up` (launch's settle 33 guest s); a pre-click settle -> `ui_done`; kdreturn's text/desktop polls 0.25/0.2 -> 0.05. The rest is the HDD boot and the DOS handoff |
| frpromise / zoomsave / regmove | 61 / 90 / 47 s (load ~12); 91 / 36 / 69 guest s; CPU 31 / 53 / 20 s | unchanged | - | lean: a boot settle each and the subject's own work (frpromise's 51 guest s promise wait). Re-declared 150/150/130 -> 60/90/40 |
| gfxlk | 139 s (load) / 51 guest s waited + ~20 unlogged in advance(), 59 s CPU | 39 s / 28 guest s, 40 s CPU | 4 | `kernel_up` boot; Cyclone's two launches `advance(300)` -> until the window + `ui_done(lock=False, cap)` (a game); the close clicks' `advance(90)` -> `ui_done(cap)`. The hand-moving loop and the pixel compares' settles are the measurement. secs 150 -> 60 |
| assocflush | 129 s / 160 guest s + five unlogged 27-guest-s "no flush" paces, 72 s CPU | 47 s / 151 guest s, 45 s CPU | 2, 5 | `Flushes.settle` (pace 6.0 = 27 guest s, the NO-flush windows) -> `ui_done` + 1 guest s: a flush is posted and run inside a ui_task pass on the drive. Red with an [assoc_dapp] flush poked before the window (2 flushes caught). `quick=True` on the five boots. secs 170 -> 60 |
| hdsize / fcproom | 76 / 84 s; 196 / 136 guest s | 21 / 45 s; 75 / 125 guest s | 4, 8 | hdsize: five `click(settle=N)` fixed paces (8 host s = 36 guest s each) -> `ui_done(cap=<the old pace>)`; `kernel_up` boot. fcproom: three HD-machine boots `ready` -> `up` (+ no_saver), a row-select settle -> `ui_done`, poll 0.5 -> 0.05; its 28 guest s a boot is the XT-IDE machine itself. hdsize 60 -> 30 |
| knobhd | **FAILED** (234 s): round 1's instdeep `ui_done`s never end on its MOUDIAG=1 knob kernel (the UI never idles), "the Install button arming" timed out at 180 guest s | 125 s / 351 guest s, green; instdeep still 59 s | - | instdeep's click waits are `ui_done(cap=<the fixed pause it replaced>)`, and the copy's `ui_done` runs only when the arming wait proved the UI idles - else the old 8 x 2 guest s of disk stillness. The rest is two boot settles on a knob kernel whose diagnostics keep the screen moving (132 + 91 guest s). secs 180 -> 150 |
| wdreach / wdmove | 83 / 30 s; 91 (+ ~50 unlogged pace) / 48 guest s; CPU 39 / 18 s | 27 s / 78 guest s, 24 s CPU; wdmove unchanged | 2, 4 | wdreach: 35 hand-rolled clicks (`to` + pace 0.25 + press + pace 0.08 + release: ~1.5 guest s each, none logged) -> `mo.click(settle=0)`, every edge proven; settles -> `ui_done` (every read is Word's bss); `kernel_up` boot. The no-full-redraw window (pace 1.6) is the measurement and stays. Re-declared 200/210 -> 40/40 |
| dosseq | 76 s (load) / 94 guest s, 26 s CPU | 26 s / 91 guest s, 24 s CPU | 2, 8 | the --hdd launch's boot settle + `ready` -> `boot=False` + `ui.up` (+ no_saver; the first act is `ui.path`); the probe poll 2.0 -> 0.25 host s (a text-screen read). The rest is the probe's own 256 KB of writes. secs 240 -> 40 |
| dosopen | 112 s / 232 guest s, 64 s CPU | 49 s / 183 guest s, 48 s CPU | 1, 2, 4, 8 | a typed command's screen settle -> `quiesce` on the console bytes + the drive's read count (dropping the wait altogether before the launch `until` went RED: three checks read the console and [dos_ispkg] AFTER the window appears); clear()'s settle after confirmed `ui.close`s -> `ui_done`; `quick=True`; polls 0.3 -> 0.05. secs 240 -> 60 |
| dosdirsw | 29 s / 73 guest s | 17 s / 67 guest s (host waited 26 -> 14) | 1 | a typed command's settle -> `quiesce` on con_scr + the viewport + the drive's read count (what is asserted next). The guest seconds are the commands themselves. secs 260 -> 30 |
| tpdraw | 83 s / 169 guest s, 72 s CPU | 52 s / 117 guest s, 46 s CPU | 4 | 23 incremental-vs-full-repaint glass diffs: settles before each capture -> `ui_done` + 3 guest frames (UI.still's shape); an early capture can only ADD differing pixels, and the one place it did (the launch finishes its menu bar after the UI first idles: 282 px) keeps its settle, as does the one after `type_text`. secs 300 -> 90 |
| dockpos / fddpark | 53 / 68 s; 100 / 62 guest s | 46 / 72 s (load ~13); 50 / 22 guest s, CPU 32 -> 20 / 41 -> 27 s | 4 | dockpos reads `m.vram` (guest memory), so every settle -> `ui_done`; both boots `kernel_up`. Re-declared 300 -> 60 each. **dosshell SKIPPED**: its probe's "SHELLREF DONE" marker is missed in 2 of 3 runs at base (the text screen reads garbled) and the 240-HOST-s wait for it is then the row |
| stik* (15 rows) | stiknote 25 s / 61 guest s (declared 150); the family 7-76 s wall, 7-39 s CPU at load ~12 | `quick=True` on stikswap/stikmove/stiknote boots: anchor 42 -> 34, notevga 54 -> 47, notesmall 18 -> 11, move 60 -> 54 guest s | 2 | already lean; `quick` only where the first act is an os88ui verb or a positive guest read - NOT stikregister/stikboot/stikmiss, whose first assertion is that something did NOT appear at boot (an unsettled read could pass early). stiknote 150 -> 40, stiknotevga 80 -> 50 |
| pixelstein (x5), pxsfsx, pxs160, pxs256 | pixelstein-vga 92 s, 66 s CPU / 41 guest s waited | 56 s CPU (wall 101-127 at load ~13, all five green); pxsfsx 86 s CPU / 324 guest, pxs160 17 s, pxs256 8 s | 8 | `kernel_up` boots in the four scripts (open_game's first act is a click); pxslib's six polls 0.2-0.3 -> 0.05 (pxsfsx waits on 151 frames/brackets). The rest is the game's own frame windows (`advance`, the measurement) and pxsfsx's 48 bracket round trips (guest mode sets, ~3 guest s each). pxs160 45 -> 30 |
| vid: lyplay(+stream, disk, noroom), live(+cga, vga, vga4, xt), logo(+vga, cga) | vidlyplay 92 s / 133 guest s, vidlive 75 / 35, vidlogovga 68 / 48 (load ~12) | 76 / 139, 53 / 35, 50 / 41; all 12 green (charged CPU 12-39 s) | 2, 8 | `quick=True` (first act `ui.path`) and 0.1-0.3 polls -> 0.05. The rest is the plays themselves (vidlyplay's 110 guest s of frame waits ARE the bench). lyplay/stream re-declared 150 -> 90/80, disk/noroom 25 -> 40 (measured 48-50 loaded) |
| pxbench / pxbenchvga | 231 / 307 s (load ~10) | unchanged (polls 0.3 -> 0.05 only) | 8 | a BENCHMARK: guest decode is the time. Quick boots + ui_done tried (177 -> 146 guest waited) but BIG.BMP's "first rows" on the VGA then read 3.96 s against a **3.90 ceiling it already sits at (3.79 base, 3.82-3.96 across runs: the key lands at an uncontrolled disk phase)** - reverted to keep the measured state; the ceiling is marginal. Re-declared 700/760 -> 250/350 |
| isotron*: toggle (+ fs, twodisp, flow, win, rules, bound, sound, pace, input on the same scripts) | toggle 80 s / 145 guest s | toggle 66 s / 133 guest s; the nine siblings green (charged CPU 10-71 s; walls 2-3x that at load ~12) | 2, 8 | `quick=True` on every isotron.py/isotronlive.py boot (the first act is `open_game`); 55 polls 0.1-0.3 -> 0.05; the post-present glass pause 0.3/0.25 -> 0.1 guest s. The rest is the game's own rounds and presents (`presented`'s owed-wait is 25 guest s of real presenting). toggle secs 180 -> 90, the others left as declared |
| dispcheck / dispfit / dispherc1 / dispmode / disptext / dispmine | 72 / 67 / 73 / 23 / 17 / 13 s (heavily loaded), 9-23 s CPU charged | unchanged | - | lean: 27-56 guest s, ~20 of it the boot (several capture the first desktop, so the boot settle stays). Re-declared only |
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
| instdeep / assoc / rest / state / keep / img / cross | 260 / 270 / 236 / 309 / 369 / 372 / 261 s (load ~6); 2,946 guest s waited for the seven | 48 / 47 / 48 / 75 / 126 / 112 / 125 s; ~1,150 guest s | 4, 5 | the shared `instdeep.open_installer` clicked with FIXED settles - 90 guest s for the installer window (13 x), 36 for the HDD tick, 13.5 per arm: now the window/the drv_tab segment/`ui_done`; boots `boot=False` + `kernel_up`; the install's end is `ui_done` (the copy holds the lock throughout) + a 3 x 1 s drive quiesce instead of 8 x 2. The host-side tree checks after are the proof |
| install | declared 400 | **fails at base** | - | `HDDTOOL.DRV is still held after Close (hd_tseg C5E8): DRVU_DONE did not give it back` - also with a `ui_done` before the read, so not the read's timing; looks like a product defect (SPEC.md 117.3), not touched |
| pxsave / pxsact / pxsauto | 277 / 68 / 62 s; 315 host s waited | 224 / 39 / 39 s; 223 | 8 | polls 0.3-0.5 -> 0.05 (16 sites; the saves are guest work), pxsact's tick window poll 0.1 -> 0.02 |
| doscable / dosconcga / doscon / doscom | declared 600 / 150 / 100 / 30 | 130 / 26 / 32 / 15 s | - | already lean (doscable is host-stepped partner work, its waits ~50 guest s); re-declared only |
| wire* (8 rows: wirefleetsystem / deploy / nomouse, wireball video / mono / front / physics, wireflick) | 1,048 guest / 800 host s waited; nomouse **failed** (a settle 360 guest s: the link's search message keeps the picture moving) | 540 guest / 314 host; 87 / 101 / 29, 82 / 43 / 85 / 19, 18 s (loaded) | 2, 4 | settles before memory reads -> `ui.still()` (69 sites), `quick=True` boots, nomouse's menu pick -> `ui_passed`. wirefleetsystem then needed a wait for KeyA's placement cue to END before pricing Ready's (a settle used to outwait it). **wireballmono/video's herc gate (>= 45 fps) is flaky AT BASE**: 47.5 / 43.6 / 45.5 / 44.1 fps over four base runs - not touched |
| pxdecode | 810 s / 1,480 guest s waited | (unchanged) 685-714 s | - | polls 0.3 -> 0.05 made it FAIL 2 runs in 5: a Ctrl+R that reached the BIOS ring (tail moved, ui_idle, no busy/job) started no open, each time on the open right after a refused hostile fixture (HF15.TIF, HJ08.JPG, HG01.GIF). Reverted; possibly PiXEL ignoring a key just after a refusal - for the owner. Re-declared 1670 -> 900 |
| excitebike ega / front / load / boot360 / 720 / 1440 / lowmem | 129 / 143 / 25 / 38 / 32 / 27 / 33 s; 394 guest s waited | 78 / 106 / 35 / 20 / 23 / 36 / 22 s (load 9-10); 254 | 4 | `quick=True` boots; settles -> `ui.still()` (all before memory reads or an `fbuf` after an input). The rest is the package's load and the splash shade |
| hibernate / hibernatem / hibernatedrv / hibsumok / hibsumbad | 110 / 94 / 111 / 44 / 44 s; 359 host s waited | 54 / 49 / 53 / 26 / 32 s; 179 | 4, 8 | `quiet()` (33 calls, a settle capped at 8) -> `ui_done(cap=8)`: every read after one is memory; polls 0.5-1.0 -> 0.05. The rest is the boots and resumes themselves |
| atblit / atblitvga | 333 / 203 s (load 7) | 285 / 183 s (load 6-7) | 8 | ~4,000 one-key-at-a-time waits (two arms typing the same document; one key is ~45 guest ms) polled at 50 ms -> 5 ms. The typing IS the row (the key queue overflows otherwise); atblit re-declared UP |
| brscroll / brclick / pxfolder / wdunsel / lzbig | declared 385 / 300 / 300 / 360 / 330 | 30 / 25 / 115 / 223 / 322 s (load 6-7), unchanged | - | re-declared only: the waits are the guest's own work (pxfolder's decodes, lzbig's compress of a big file at ~100 guest s, wdunsel's 48 quiesces of real redraws). pxfolder's 0.3 polls deliberately kept: pxdecode's lost Ctrl+R appeared when PiXEL was keyed sooner after an open |
| 16 rows re-declared from one measured batch (load 6-8): dospkg 30, doslnk 60, wmchrome 73, sheetmove 57, trackmove 28, smalllaunch 205, smallboot 213, lzcomp 107, lzship-lzb 159, vidkeyclus 43, ddcorner 122, dostype 69, czjoin 160, mpupin 37, tmsmall 64, bigvol 52 s | declared 100-190 | same | - | no change made: each is dominated by guest work its waits already end on (package launches, compress/uncompress, toasts). bigvol failed once on `guest running under a tenth of real time` at load 8 and passed alone |
| vidc* (10 vidcga.py rows) | 313 guest / 185 host s waited | 262 / 141 | 8 | `quick=True` and the clip waits' poll 0.2 -> 0.05; each row is now 7-29 s. ptsmix 114, fontpick 120, pxpaint 62, icoshed 51 s measured and re-declared (boot + their own work) |
| weavepack | 67 s / 250 guest s waited (declared 1,500) | 51 s / 160 | 2, 4 | os88ui verbs (`open` confirms LOOM's window, `close` its record) and `ui_done` after ^P - Pack runs whole on the UI task - instead of three settles; quick boot. The rest is eleven LOOM launches and their packs |
| weaveprev | 79 s / 283 guest s waited | 53 s / 190 | 2, 3, 4 | six boots -> two (Forks a project); the Preview's two settles -> `ui_done` (compile + module read are UI-task); every read is `m.vram`. The rest is three LOOM launches and Previews a machine |
| weavesession | 28 s / 91 | 24 s / 66 | 2, 4 | six settles -> `ui_done` (the VM drains in WM_ONWAKE slices on the UI task; FORM has no canvas) |
| weavegrid / weavegfx | 31 / 37 s; 93 / 112 guest | 24 / 27 s; 60 / 71 | 2, 3, 4 | grid: settles and `_park`'s -> `ui_done`; gfx: four boots -> two (Forks) |
| weavesmoke / weaveone / weavegame / weavelat | 71 / 15 / 11 / - s | 33 / 16 / 10 / 13 s | 2 | the shared `_open_bundle` + quick boot only; one/game/lat were already lean - re-declared |
| viddisk family (10 rows) | viddiskfd 253 s / 750 guest; wseq 106 / 381 | 192 / 750; all ten green | 8 | bench rows: W and R ARE the measurement (575 + 104 guest s of 750). Boots launched paused with `up` + `ui_done` as the gate (an HDD boot publishes B:'s zone after [spl_live] falls - `up` alone found none); polls 2.0/1.0 -> 0.25. ~4 guest s a boot, nothing more to take |
| pxfsx | 242 s / 475 guest s waited (declared 1,500) | 207 s / 512 | 8 | guest-bound: 26 full-screen renders (209 guest s, a 640x480x16 one is 26 s of 8088) and a slideshow ARE the row; quick boot (54 -> 42 guest) and polls 0.3-0.5 -> 0.05. The baseline's 'Memory:' look costs a 5.5-s retry or two either way. Re-declared |
| blitcut / blitplane / blitp / blitpair | 132 / 156 / 30 / 14 s; 212 / 135 / 32 / 38 guest waited | 111 / 118 / 15 / 12 s; 172 / 98 / 25 / 35 | 4 | boot gate `kernel_up`; dispcp's `settle` -> `ui_done` (the verbs confirm); settles before a breakpoint window or a rect quiesce -> `ui_done`; before `fbuf`, `ui_done` + 0.1 guest s (both cards). Same pixel and cycle results; the rest is two kernels' Paint loads and the blits measured |
| vidsound (+ 26 siblings in vidsound.py) | 76 s / 94 guest s waited; resident ADPCM4 rows 172-181 s | 28 s / 94 guest; resident 53-55 s; all 27 green | 4, 8 + harness | HOST-bound: 53 of 96 host s was `read_frame`'s per-pixel PBM parse (fast path), the capture decode numpy, and `_adpcm4_viterbi` re-walked its whole window at EVERY sample once survivors failed to merge (noise does) - 228 s -> 0.6 s on 8,192 samples, the commits identical (checked on four streams). Quick boot (`up`, which needed the tick fix). Guest: the XT-IDE boot is 28 of it and the play is real time. Red with 40 capture bytes flipped |
| vidspk (15 rows) + vidsnd | 20-46 s (load 10) / 688 guest s waited | 12-20 s (load 6-8) / 622 guest | 4, 8 | quick boot (`up`); a no-op `until(lambda: True)` "beat" between Control Panel clicks -> `ui_done`; polls 0.05. The rest is the XT-IDE boot and the real-time plays |
| bootfloor-ab | 210 s warm (450 cold) / 43 guest s waited | 66 s / 28 | 5, 11 | `os88build.tree()` asked once per process (each ask is a `make` over the tree, ~17 host s, and it asked 12 times for 5 trees); one launch a boot that runs until the desktop STATE or the sector's message has held a guest second, instead of a refused boot timing out launch's gate and booting again. **The `says RAM` check was always true**: GLaBIOS's POST prints `RAM    [ 640 KB OK ]`, so it now wants a line ENDING in RAM (the sector's `msg_mem`). RAM at reset reads 'desktop' in those three words - hence the hold |
| bootstatus | 45 s | 9.6 s | 4, 10 | the per-frame sampler decoded a whole `m.vram` frame each displayed frame to look at ONE scanline: it reads that row's bytes out of video memory (same 7 distinct bands both adapters); the tail's blind `advance(240)` -> `ui_done` + 0.1 s |
| brreload | 16 s / 62 guest s waited (declared 360) | 9.5 s / 32 | 4 | boot on state; every settle and the two `pace(1)` -> `ui_done` (all reads are browser state or `m.vram`); identical ink counts |
| brtable / br14 | 9.4 / 7.4 s (declared 200 each) | 7.3 / 6.6 s | 4 | already cheap; brreload's conversion (state boot, `ui_done`) and re-declared |
| telnet / telnetherc | 25 / 29 s (declared 300 each) | 29 / 31 s (two in parallel) | - | boot on state only; the rest waits on a WORKER that draws on its own turn (the settles there are honest). Re-declared |
| vidv2 / vidvga8 / vidvga4 / vidv2bench (26 rows) | 1,172 guest s waited, rows 11-157 s (load 7) | 1,077 guest s, 9-157 s (load 6); all green | 8 + quick boot | `quick=True` on five boots; polls 0.05; `os88venc`'s PFILL mix table (3 s a build, 4 builds an encode for the same palette) made once a palette - output byte-identical. The encoded-clip rows (pgmx/pg4/ly4/lp/flmx, 100-157 s) are the ENCODER's real work under load (~45 host s a 4 s clip); not cut |
| kzboot-off / kzboot | 208 s (3 lanes) / 46 guest s waited; - | 63 / 14 s; 13 guest | 4 | the two 'reaches a desktop' settles -> `kernel_up` (state); the rest of kzboot-off is its NOKZIP tree's make check |
| atkey | 57.5 s alone (172 in 3 lanes) | 52 s | 4 | quick boots, five `ui.settle()` -> `ui_done` (it measures cycles and words, never the glass); same cycle figures. The rest is typing the scene a character at a time on two kernels |
| curdisk | 170 s (3 lanes) / 107 guest s of boot settles | 38 s | 4 | four boots gated on `kernel_up`; setup's dispcp settles -> `ui_done`; `watch()` (the measurement) untouched, same move counts |
| tmselfsu | 84 s alone (declared 300) | 94 s (noise) | - | boot on state only (20 guest s); the rest is dispcells' stop-per-call breakpoints on font_run_x/gfx_fill (host round trips; the measurement) and the Task Manager's own interval ticks. Re-declared |
| hdboot | 131 s (3 lanes) / 36 guest s waited | 37 s / 35 | 4 | the install machine's double boot settle (launch's + one more) -> `kernel_up`; the C: boot was already a frame-stepped state watch |
| deskflash / deskzoom | 103 / 109 s (3 lanes) | 45 / 93 s (load 8) | 4, 10 | quick boots; settles -> `ui.still()`, the one before `dc.verify` dropped (verify stills itself); deskflash's per-pixel Python `flashes` over 30-70 glass frames -> numpy (`OS88_FLASHCHECK=1` asserts it equal to the loop: equal on all 16 checks). deskzoom's rest is `dc.verify`'s whole-repaint compares |
| 1942sound / 1942 / 1942front | declared 752 / 216 / 180; measured 158 / 131 / 102 s (load 10), 304 guest s waited | 139 / 124 / 91 s (load 6), 223 guest s | 4 + quick boot | quick boots; splash settles -> `ui_done` / `UI.still` before the exact-pixel logo compares; `Game.call` restores only the registers a call changed. What is left is ~7,300 `call_guest`s at ~25 round trips each (park + 13 setregs + bp + run + regs + restore). **Pipelining them does NOT work on today's server** - queued lines after the first are not answered until more input arrives (tried, hung); a server-side drain of `pending` would make a 25-trip call ~3 |
| fishedge | 72 s | 14 s | 12 | two `launch(boot=40)` - a fixed pace - -> `kernel_up`; same strip counts' shape (they vary run to run with the swimmers) |
| scsize / shutdown | 136 / 92 s (3 lanes) | 60 / 79 s (2 lanes) | 8 | quick boots (scsize's launch + `ready` settles 20 guest s; shutdown's three launches 52); polls 0.3 -> 0.05. The rest is SCRIBE's loads and saves / three shutdown cycles and a warm reset |
| wdcourier / wddrag / wdcombo / wdenter / wdtype | 41 / 56 / 39 / 29 / 54 s (5 in 3 lanes, base) | 67 / 74 / 33 / 36 / 86 s (same, loaded box) | 4 | boots gated on state (they settled twice: launch's and one more); the rest waits on WORD'S LAZY WORKER (status line, height count), which `ui_done` cannot see - its quiesces and paces stay. Wall here is load noise either way. **wdenter failed once in two at base** (intermittent), passed after |
| fdlg* (6 rows) | fdlgchoose 52 s / 187 guest s; the rest 9-12 s (declared 60-300) | fdlgchoose 39-46 s / 116 guest; the rest 9-12 s | 4 + quick boot | quick boots; settles -> `ui_done`, or `still` before the ink (fbuf) compares that would go red if early; `UI.chooser`'s settle -> still. Re-declared |
| midirack* (11 rows) | midirackend 44 s (3 lanes) / boot settle 21 guest s each | 15-69 s, all green (11 in 3 lanes) | 8 | quick boot (`ui.path` is the first act), polls 0.2 -> 0.05; the playback windows are the measurement. Re-declared from this run |
| trkspk* (9 rows) | trkspkcovox 42 s (3 lanes) / launch + `ready` settles ~22 guest s a boot | all green; walls 32-105 s at load ~8, 85 s charged for the nine | 4, 8 | boots gated on `ui.up` + `ui_done` (were launch's settle AND `ready`'s); poll 0.2 -> 0.05. The `pace`s are the PLAY running (pulse rates, the ring never dry) and stay. Secs left as declared |
| mrdraw(vga), wfdraw(herc), dosext, kdnoprog, hdnoclaim, heaphi, apspk* (5) | boot settles 20-42 guest s a row (survey) | 13 rows green, 165 s for all in 3 lanes at load ~8 | 4 | quick boots / `up` + `ui_done` / `kernel_up` where launch's settle (and `ready`'s, or a second settle) gated a boot whose first act confirms itself; measurement windows untouched. Over-declared ones re-declared |
| imgtest, brlink, cmemmove, arkpuwipe(small), tmgraph, netpromise, drvscroll, tmrepair, wmartifact, heapscrl, dosargs | 27 / 11 / 26 / 29 / 43 / 57 / 35 / 73 / 74 / 60 / 26 s (survey, 3 lanes) | 14 / 15 / 44 / 53 / 18 / 25 / 17 / 31 / 37 / 24 / 32 s (12 in 3 lanes, load ~8) | 4 | launch's boot settle (20-33 guest s each) -> `kernel_up` + `no_saver`, or `quick=True`; nothing else touched. Re-declared |
| pxssim / -herc / pxsshots / pxsstate / pxsscale | 134 / 122 / 86 / 53 / 11 s (load 7), 513 guest s waited | 54 / 52 / 78 / 33 / 14 s (load 5), 459 guest | 9(host), quick boot | host-bound: pxsart's per-pixel palette search and sprite re-parse memoised; launches unbooted through `open_game`. What is left is ~715 real game frames and the package loads. pxssim-herc FAILED once (a door's shadow 121 bytes off the host's) and passed alone twice - an intermittent, not this change (it is on the boot path only) |
| desklayer (11 rows), vidrepeat(3), vidresbig, heapcheck, heapdrv, tmground, win1bpp, hdmap, kdkbd, drvcall, fmbtn, modstr, trkcompact, editmove | declared 20-150 s | 26 rows green, 9-59 s each (in 3 lanes, load ~8; 167 s charged) | 4 | the same boot conversion (quick boots / `kernel_up`, and the second settle some did after launch's); re-declared from this run |
| pxedit | declared 600 | 225 s / 558 guest s waited (load 5), unchanged | - | guest-bound: the Effects ops ARE the work (Blur 38 guest s on the 8088) and every wait already ends on its condition; re-declared only |
| czseqnone / czseq / czseqlose | 114 / 79 / 25 s (load 4), 118 guest s waited | 80 / 65 / 28 s (load 8), 88 guest | 4 + quick boot | quick boots (floppy and XT-IDE); settles before guest reads -> `ui_done`; polls 0.05. czseqnone's wall includes a ~40 s FATWNONE private-tree rebuild whenever the commit count moved (the build number), <1 s otherwise; czseq's rest is its per-`int 13h` breakpoint trace, the measurement |
| vidfskeys (13 rows) | 28-102 s (load 11), 1,114 guest s waited | 33-78 s (load 9), 1,096 guest | 8 + quick boot | quick boot, polls 0.2 -> 0.05. The rest is the VGA floppy boot (~14 guest s to `up`) and the plays' own holds and seeks, which ARE the subject |
| pxdraw / pxdrawvga | declared 200 / 200; 62 / 85 s (load 3), 343 guest s waited | 73 / 96 s (load 6), 339 guest | 4, 8 | quick boot, settles -> still, polls 0.05 - little to take: the decode, the traced gestures (their 0.3 s tails are the measurement) and the 6 s free-memory look are the work. Re-declared |
| vidkern / vidkpartbad | 36.5 / 8.8 s; 93 / 24 guest s | 28.5 / 9.1 s; 96 / 22 guest s | 8, 12 | vidkern: launch's boot settle + `ready` -> `boot=False` + `ui.up` (first act `ui.path`); polls 1.0/0.5 -> 0.05. The rest is the XT-IDE boot (28 guest s) and the bench's own brackets. vidkpartbad `quick=True`, poll 0.3 -> 0.05. secs 48/45 -> 40/20 |
| dos* (14: shrink snd drv dir dev mouse mouevt mcb gap file fcb range ren regs) | 89 s (3 lanes) / 552 guest s waited | 84 s (3 lanes, load ~10) / 435 guest | 4, 8, 9 + quick boot | already lean (10-34 s each): quick boots (boot settle 19.5 -> 13.5 guest a machine), polls 0.3-0.5 -> 0.05, the bracket exit `type_text; settle` -> `text_taken`, dosmouse's click settle=0 (both edges are proven); dossnd's remount is waited ON (`until` the drv_tab row), it lands after the UI idles |
| assoc* (7: sweep open glyph wake vol find stale) | walls 30-46 s / 261 guest | 16-39 s / 226 guest | 4, 5 + quick boot | assocopen 46 -> 17 s: its document leg's `tr.wait(1, limit=30)` (unlogged, a 90-guest-s PASS-by-timeout) ends on "UI idle across a tick" - the folder control proves the end cannot precede a same-pass repaint; bare launches -> `kernel_up`, dispcp verbs on `ui_done` |
| covox drv/auto/cp/nolpt | declared 30-45 | 8-15 s | 4, 5 + quick boot | **covoxdrv failed at base**: it searched a fixed 0x2400 window of SOUND.DRV for `cvx_ports`, and the driver (bss inside) has grown to 11,265 - now reads the header's image size. cp's fixed beats -> `ui_done` + 0.3 s tails |
| dotdel / dotdelpen / dotdelwin / dotdelmd | 123 / 62 / ? / 66 s (load 5-7), 395 guest s waited | 131 / 101 / 30 / 75 s (load 7), 363 guest | 4 + quick boot | quick boots; dotdelmd's desktop_up settle -> `kernel_up` and the dispcp verbs on `ui_done`. The rest is the 10-guest-s frame-rate windows (taken again when a repaint lands) and real play, the measurement. dotdelpen FAILED once in the 4-row batch, green alone and after: an intermittent |
| 25 small rows: videms x4, multiseg/mseg360, rehome(abort), timerrace, sbar(dlg), spantest(-vga), dtfield, minexflag, tpsaveu, cpnames(hdd), atclip, trkrate, cycweb, fsclass, icoclip, monoink, fillpat | 272 s in 3 lanes, 103 charged; 1,028 guest s waited | 244 s in 3 lanes (load 8), 105 charged; 838 guest | 4 + quick boot | the boot gate only, mostly (launch's settle 15-37 guest -> `kernel_up` 13-31; videms' EMS XT boots 37 -> 31 x4); cpnames' clock-ticking panel settles (14 guest each) -> `ui_done` before its `vram` reads, 100 -> 52 guest; spantest's blind 250 frames after the open -> `ui_done`. Walls barely move under load 8 - these are boot-bound rows |
| wdscroll | 160 s (load 12), 163 guest s waited + ~90 unlogged in `pace` | 131 s (load 8), 157 guest incl. what replaced the paces | 4 + quick boot | boot -> `kernel_up`; each gesture's quiesce(0.5) -> `ui_done` + quiesce(0.25); a tap's 0.25 s lead pace -> `ui_done(cap=<the old pause>)` (the hold before release stays: it is the press). The rest is ~95 real scrolls on a CGA XT |
| redlinescene | declared 240 | 51 s (load 12), unchanged | - | already lean; re-declared |
| pxopen / pxopenpng / pxopencga | 63 / 69 / 45 s (load 8), 257 guest s waited | 56 / 60 / 35 s, 218 guest | 4, 8 + quick boot | quick boot; settles before memory reads -> `ui_done`, before the exact pixelsim compare -> `still`; polls 0.05. The rest is PiXEL's decodes |
| mixercga / herc / vga | 96 / 57 / 60 s (load 8), 250 guest s waited | 48 / 37 / 45 s (load 11), 99 guest | 4 + quick boot | every click and key is followed by a wait on the state it changes, so the click's 1.5-cap (it never idles: the popup) and the key's 0.3 sleep went (QEMU's arm keeps them); quick boots + a `still` before the first pixel compare. Exact-pixel restore checks still green |
| dosfull / dosfix | 56 / 77 s (load 8), 162 guest / 129 host s waited | 20 / 24 s, 152 guest / 41 host | 8 + quick boot | quick boots; the READY poll (a text-screen read) 0.5-1.0 -> 0.1 host s. The rest is the DOS probe running |
| telpen | declared 300 | 13 s | - | already lean; re-declared |
| 69 small rows (altenter .. xorrect: redline x4, lzmod x5, pkgthumb x4, runclip x2, vidgrey x2, pxshud x2, kd*, usbmouse, vidhdmake, vidmove, ...) | declared 5-65 s each | all green: 610 s in 3 lanes (load 8), 281 charged, 2,336 guest waited; walls 2-60 s | 4, 12 + quick boot | MECHANICAL, applied by two scripts: `os88ui.boot(...)` -> `quick=True` + `ui.still(0)` (so the first paint is done whatever the first act is), and a bare `launch` (default boot settle, often plus a second `settle`) -> `boot=False`, `run`, `kernel_up`, `no_saver`; `ui.ready` -> `up` + `no_saver`; kdos' `boot=2` pace dropped (its text wait is the gate); pxshud/pxsmove launch UNBOOTED so `open_game` gates on `kernel_up` instead of settling a booted machine. Secs re-declared at 1.25x this run. gb* (rgbds) and vidbench (xdc) skipped here and left unedited |
| dljunk | 181 s (load 8) | 40 s | 5 | the failing value (DLJUNK=1) waited out a whole picture-settle gate's TIMEOUT and was then booted again to read `Disk error`; now one unbooted launch per value ends on whichever comes first, the kernel's desktop state (with the tick) or `Disk error` on the text screen. Both legs are the A/B's two sides, so an always-up or never-up detector goes red. A commit-count change still rebuilds its two private trees |
| wdmenusu / ftpdflick / ftpdfocus | declared 190 / 120 / 60 | 32 / 40 / 31 s | - | already lean; re-declared |
| uilayer (failed at base), kdnomouse, vgacolor, tmowner; lean: tickzero, blobsum, romsock, cylrun, splashbar/spin, pitnow, lzload, autostart | uilayer 46 s / 45.5 guest, kdmouse.py 44, tmowner 36, vgacolor 35 guest | 28 / 38, 80 (both kdmouse rows), 31, 25 guest | 4, 13 + quick boot | **uilayer's EXPECTATION changed**: "confirm <= 0.9x settle, HOST" stopped holding once settle ended on UI idle (1.09x host, 0.89x guest at load 8) - now `bc < ac` in GUEST cycles (a confirm-by-settle pays the settle AND its check, so it still cannot pass); inverted, it goes red (0.70x). kdmouse.py's four `click()` then `ui_done` -> `settle=0` (a 1.5 = 6.9-guest-s pace each). The lean ones are boot instruments (they time the boot itself) or already gate on state; secs re-declared only |
| mcperf | 42.5 s; 181 guest s waited | 11.0 s; 49 | 4, 7 | the 400-frame TOP/END trace LOGGED (800 pumped stops a run); the post-run screen settle (55 guest s of live play no seed governs) -> a hash of video memory at a stop on `mc_bshow` - the 400th frame itself; `kernel_up` boot, dispcp verbs and the pre-run settle (77 guest s under a running game) -> `ui_done`. Same C3B7 state, same per-frame cycles |
| bptrace | 25.9 s; 40 guest s | 23.7 s; 33 | 4, quick boot | lean: the rest is the trace's own subject. Re-declared 45 -> 30 |
| dmgcull | FAILS at base | - | - | the Task Manager redesign (89afd69c, one tree of groups) left the gesture painting 27 font_run cells, all inside the mover's rect, deterministically (not the pump's lost-stop flake: 3/3 retries, two runs). The scenario needs re-deriving against the new page |
| lzship | 51.4 s / 73 guest s waited, 47 s CPU | 14.7 s / 45 guest s, 15 s CPU | 1, 4 | both boots gate on `kernel_up` (every read is drv_tab, the window list, the listing or the module claim), the dispcp verbs and the folder opens end on `ui_done`; the BEVERLY.MOD open keeps its own wait (Tracker plays). secs 80 -> 30 |
| cpup / atmenusu | 17.1 / 26.5 s; 35 / 36 guest s | 8.3 / 23.8 s; 23 / 30 | 4, quick boot | cpup: `kernel_up` boot; the 1bpp glyph reads are VIDEO MEMORY so `ui_done` before them (VGA keeps the settle: `fbuf`); the press/slide paces and the settles before each `[sch_coop]` read -> `ui_done`. atmenusu: `quick=True`, the three settles before memory reads -> `ui_done` (the two before `fbuf` grabs stay). gbstate / gbdemo / gbfm / gbship SKIP: need rgbds, absent here |
| drvmove / sndmove | 19.9 / 22.2 s; 67 / 68 guest s waited | 14.7 / 18.6 s; 53 / 55 | 4, 12 | boot gates on `kernel_up`; every Control Panel click, dispcp verb and settle before a memory read (drv_tab, mem_tab, the IVT) -> `ui_done`; the closing "machine still draws" settle stays. secs 170 / 150 -> 20 / 30 (declared from before the harness pass) |
| weavefuzz | 109.5 s (77 s CPU) | 3.8 s (2.7 s CPU) | 10 | host-only: weavesim was a spawned interpreter per case (0.1 s x 1,000); `py_pack` calls `cmd_pack` in-process and maps PackError/BundleError/any traceback to the same verdict and last line. `--spawn` keeps the old path: a per-case trace (verdict, message, bundle bytes) was IDENTICAL over all 1,000 cases. Also out of build/: header, host binary and scratch project go in a mkdtemp (t_lmpack's fix). secs 180 -> 10 |
| fmthumb / cplistrow / dtwrite / dosxms / dosvec / irqgrab / kdcylrun / ddsmall / recorder / pathcost / pxsbench / dskwstage / lzfence (+ facescan(144), tmcol2, postboot, mouwheel, dualcheck measured) | 29.7 / 30.6 / 18.1 / 17.9 / 18.1 / 17.6 / 18.2 / 42.2 / 17.8 / 18.7 / 17.4 / 16.4 / - s; guest waited 26 / 29 / 33 / 33 / 28 / 26 / 47 / 83 / 30 / 29 / 29 / 19 / - (load ~8-12) | 14.5 / 14.3 / 19.5 / 9.1 / 9.9 / 19.7 / 17.0 / 40.7 / 16.7 / 26.3 / 17.6 / 18.7 / 13.5 s; 20 / 22 / 23 / 22 / 22 / 22 / 38 / 76 / 22 / 27 / 25 / 17 / 15 | 4, 8, 9, quick boot | boots on state (`quick=True` / `kernel_up`: 16-20 guest s of settle each); fmthumb's drag paces and cplistrow's / cpup's pre-read settles -> `ui_done`, with a `drawn()` that adds the settle on VGA only (1bpp reads are video MEMORY); cplistrow's two-identical-captures loop -> `ui_done` + 3 frames; dtwrite's blind `advance(frames=30/20/120)` -> `ui_done` (the 180-frame "nobody drains it" window stays: it IS the assertion); DOS exits -> `text_taken`; text-screen polls 0.25-0.5 -> 0.05. Wall here is load-noisy: compare guest |

## Resuming

The six work queues and the agent brief that drove the first session are in
`docs/plans/soak-speed-queues/`: each row is prefixed `DONE`, `SKIP <why>` or
nothing (open). Rows marked `DONE(script changed, row not re-run)` carry a
shared script edit and need one run to confirm. Run every row as
`MAKELEVEL=1 python3 tools/os88test.py soak -k <row>` in a shared checkout.
