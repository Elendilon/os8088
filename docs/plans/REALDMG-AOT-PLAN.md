# RealDMG: the full static recompiler - the plan and its stories

**The owner's goals, in order** (2026-10-25, docs/reports/REALDMG-FULLSTATIC-2026-10-25.md
section 10):
1. **No stalls, without first having to play the whole game** with Profile
   for Static on.
2. **Fit a 256 KB cartridge**: on a 286 with XMS first, on a 640 KB machine
   with no XMS if it can be had.
3. **Speed** as a bonus, from counters the game itself keeps.

Running beats stopping, so a fallback ships. One `.o88` per game and one
`REALDMG.O88` with a data file are both acceptable.

The contract is REALDMG-SPEC section 20, and it says what is built. This
file is the stories and their evidence. The study it comes from is
docs/reports/REALDMG-FULLSTATIC-2026-10-25.md, whose section 11 is the
design.

## The shape that was built, and why it is not the study's

The study proposed a new code generator: emitted assembly, direct jumps and
a static dispatcher. What W1 built instead is RealDMG's OWN translator run on
the host under an 8086 emulator (Unicorn), over a complete list of block
starts that the walk makes. It has three consequences, and they are why the
shape changed:
- **A block is byte for byte the machine's**, so every gate on the
  recompiler (`gbcpu`, `rdgstatic`, the harness's event counts) is a gate on
  the precompiled code. A second generator would have needed its own.
- **The runtime is Static's** (REALDMG-SPEC 16.8): a fixed table,
  `tr_enter`, `tr_link`'s lazy chaining, the RET caches. It is already in
  the package and already measured, and nothing new is resident.
- **The memory is the recompiler's segment layout**: 64 KB segments with the
  tails copied in, and the 64 KB table. That is what W2 has to shrink.

## Stories

### W0 - the contract and the instrument

- [x] REALDMG-SPEC section 20, written before the package work.
- [x] `tools/gbaot.py cover`: the walk, the `JP HL` table rule and the block
  starts, with no play.
  - Measured: Super Mario Land 99.88% of busy execution found, Kirby's Dream
    Land 100%, Looney Tunes 2.17% missed -> 0.30% with the table rule.
- [ ] The RAM idioms: the OAM DMA routine translated ahead of time behind a
  guard. Today HRAM is interpreted in mode 3 (REALDMG-SPEC 20.5): 3 busy
  instructions a frame on both games measured.

### W1 - the host translator and its proof

- [x] `tools/gbaot/aothost.asm` + `tools/gbaot.py build`: the whole
  cartridge translated in rounds and bank groups (REALDMG-SPEC 20.4).
- [x] The cut where another block begins, with no event check
  (REALDMG-SPEC 20.3).
- [x] `tools/gbaot.py check` and `tests/gbaot.py`: equivalence against the
  interpreter, two negative controls (REALDMG-SPEC 20.6).
- [x] Evidence on the owner's games (not committed). The precompiled code
  matches:

  | game | blocks | code | segments | result |
  |---|---|---|---|---|
  | Super Mario Land | 1,874 (25 dropped) | 178 KB, 20.9 B/instr | core + 3 | identical to the interpreter, 3,000 frames |
  | Kirby's Dream Land | 2,900 (251 dropped) | 227 KB, 18.2 | core + 4 | identical to the interpreter, 3,000 frames |
  | Looney Tunes (.gb, 128 KB) | 3,757 (304) | 358 KB, 19.5 | core + 6 | identical to the dynamic recompiler, 3,000 frames; to the interpreter until its own bug at frame 1178 (REALDMG-SPEC 20.7) |
  | Looney Tunes (.gbc, 1 MB) | 4,186 (463) | 387 KB, 19.1 | core + 8 | the same |
- [ ] Speed with the CPU alone. MOVED to W3, where it is measured in the
  package on 86Box's `286-victory`: the bare harness has no room for a
  256 KB cartridge's segments.

### W2 - memory

The full form is ~20 bytes a Game Boy instruction, which is the study's
prediction confirmed. What decides the fit is the SEGMENTS: on top of the
code, each holds 7.4 KB of tails and the gaps rounding leaves.

- [x] The table: 64 KB -> 16 KB plus a sorted list the miss path searches,
  and every exit linked on the host (REALDMG-SPEC 20.9). No block is
  dropped; the four games are still identical for 3,000 frames.
- [ ] The cut's exit: carry on into the next block's entry, with no exit at
  all, when it is translated next.
- [ ] The resume through a CONTINUATION (study 4.3).
- [ ] Decide: does Looney Tunes fit at full speed on XMS? If not, the
  compact grade. MOVED to W3: it is decided by the heap the package really
  has on the machine, which W3 measures.
- Measured and LEFT: the cut's exits are ~256 (SML) to ~398 (Kirby) blocks,
  5-8 KB of code - the continuation is worth less than the measurement.

### W3 - `GAME.O88`

- [ ] `realdmg.asm`'s `RDG_AOT` arm: the parts, the load-time check, the
  fallback, the miss log.
- [ ] Measured on `286-victory` and a 640 KB 8088: memory, per-second speed,
  no translation.
- [ ] `.o88`s of the owner's games for the owner to test.

### W4 - counters and the bundle

- [ ] Per-block counters, `NAME.RDH`, promotion in the host build.
- [ ] A bundle of the compiler scripts with an interface, in `make
  vencbundle`'s shape.
