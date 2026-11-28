# Bounce Bonanza: quarter-unit heights and the 60-unit course

The owner, 2026-11-19 (experimental, on its own branch `bb-quarter`): heights moved in half units (4 px), so
the step after the one every ball rolls up was a whole unit - a hard Hop - and course design had too few
rungs. The contract is [SPEC.md 137.48](../../SPEC.md); the diary's 2026-11-19 entry is how it was built.

Stories, each with what proves it:

- [x] **Q1 The contract** - SPEC.md 137.48: quarter units in every height byte, the rebase, the range
  (60.75 units of floors and walls), the CELLS rule's bias, the families' fields. *Proof*: `checkdocs`.
- [x] **Q2 The tool** - `bbcourse.py`: heights a multiple of 0.25; the rebase (`parse`, `rebase_units`);
  every byte through `zq()`; the model (`Physics`, the families, `AGrid`, the CELLS rule, the WAYS form) in
  quarter units. *Proof*: every one of the 24 courses compiles to its old picture, records, reach and route
  with its height bytes doubled (or rebased); `quarter_checks()` (selfcheck item 48) and its two reds by hand.
- [x] **Q3 The guest** - `bzphys.inc` (the floor function, the fast paths, the VOID kill, the FIELD floor),
  `fam/bzfcopy.inc`, `bonanza.asm` (the WAYS projection, the CELLS rule), `bzvideo.inc` (AV's `H / 2`), the
  families (glass, water, spike, gate, see-saw, turntable). *Proof*: `make`; `tests/bonanza_dsplit.py`,
  `tests/bonanza_dfield.py` and the new `tests/bonanza_dquarter.py` (unicorn, every step equal to the model;
  `--reds`).
- [x] **Q4 The demos** - MOON's, PEAK's and PLAYGROUND's written again by `bbcourse.py author`: the same runs,
  the `ident` lines alone.
- [x] **Q5 The ladder's quarter rungs** - 3/4, 1 1/4, 1 3/4 units, printed; 3/4's shape asserted.
- [ ] **Q6 A course that uses them** - First Roll and Island Hop are being re-tuned in another session with the
  ball's retune; quarter steps go into them there.
- [ ] **Q7 The final pass** - the bonanza soak rows (`bonanzacourse`, `bonanzaphys`, `bonanzareplay`,
  `bonanzademo`, `bonanzaexit`, `bonanzaperf`), scoped, in the background (fork rule 10).

What this does NOT do: lift the occluder records' 255 px span of tops (SPEC.md 137.15.5), which still bounds a
course's height at about 32 units - that is the occluder session's.
