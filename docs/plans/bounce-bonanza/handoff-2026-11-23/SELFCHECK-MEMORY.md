# bbcourse --selfcheck memory: handoff (2026-11-23)

**The cause.** `bonanzacourse` died with "a child died (status 9)". The child
was the `camcheck` section, and it was SIGKILLed at a 10.2 GB peak RSS, against
3.0 GB at the fork. `ramp_bottom`'s descent from `RAMP_POKE` (15, 7) never
reached the green on the owner's WINDMILL LANE: the ball sits at (15, 8) for
ever. The loop had no bound and kept one frame per step. No other section came
near that: under `BB_MEMLOG` every other section's peak private memory was
under 1 GB, and `determinism` was 2.9 GB. The parent's 3 GB is shared with the
children at the fork. The fix that landed is 89e94e10d (the ramp bottom moves
to TMIL and its descent is bounded). This worktree tested its own equivalent
before that fix arrived: `RAMP_POKE` (13, 7) on MILL plus a bound. With it,
`camcheck` ran alone in 214 s at a 3.6 GB peak RSS. That equivalent was
dropped in favour of 89e94e10d.

**Landed here (b7752453f).** A child killed before it returns a result now
reports what it was running ("section camcheck"), its signal (SIGKILL is
called out as most likely the OOM killer) and its peak RSS (from `wait4`)
against the parent's RSS at the fork. `BB_TIMES=1` also prints each section's
peak RSS. `BB_MEMLOG=<file>` has each child sample its private memory
(smaps_rollup) and append the peak, which shows what a fork really costs.

**Unfinished.**
- The whole `--selfcheck` on the merged head (5cc61ffd0 plus b7752453f) was
  stopped part-way for the account switch. It was not yet finished. System
  memory in use peaked at 10.5 GB with no kill so far.
- One full run is still owed, with
  `BB_TIMES=1 python3 tools/bbcourse.py --selfcheck`, to confirm that only the
  MILL doorway item fails.
- `SC_COST["camcheck"]` still says 54. It is now about 200 s or more, and it
  should be re-measured from that run's `times:` line.
- Possible, not done: `par_map` ignores `_NESTED`, so the `determinism`
  child's `compile_all` forks four compile children of its own beside the
  parent's four (eight compiles at once at the start).
