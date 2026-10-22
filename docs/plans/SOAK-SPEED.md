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
   one disk, a window closed between them.

## Harness changes made in this pass

(one line each: what, where, which rows it speeds, how it was validated)

## Ledger

| row | before | after | techniques | notes |
|---|---|---|---|---|
| tmowner | ~450 s | 41 s | 1, 2 | b787057, prior to this pass |
| isotronload | 219 s / 199 guest s | 168 s / 139 guest s | 3 | launch and rate legs on one boot a machine (6 -> 3); a settle after `open_drive` (which confirms the listing) dropped. The rest is the 2 s rate windows and the launch itself |
