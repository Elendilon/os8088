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

- [x] `realdmg.asm`'s `RDG_AOT` arm and `gbaot.py package` (REALDMG-SPEC
  20.10): the parts, the header check, the ROM opened from beside the
  package, the images claimed before the ROM and given back to fit, and what
  does not fit interpreted. `tests/gbaotpkg.py` on MartyPC's 5150, verified
  red with the attach taken out.
  - Measured, 640 KB 8088 (MartyPC, no input, the title screen): Super
    Mario Land's package holds 2 of its 3 images and runs 11.9 game frames a
    guest second against the stock recompiler's 12.9; the picture is half
    the machine there (49% of the samples in the package's own code), the
    precompiled images 26%.
  - Found: a cartridge's code in WRAM is interpreted (GBRMW.GB's loop is at
    C8xx: 9 frames a second against the recompiler's 29). Real games keep
    only HRAM's OAM routine there; W0's RAM idiom is the answer if one
    does not.
- [ ] The miss log: MOVED to W4, beside the counters it is one of.
- [x] Measured on `286-victory` (86Box, holding Right in play, 30 s) and a
  640 KB 8088 (MartyPC):

  | | images kept | speed | worst second |
  |---|---|---|---|
  | SML, Victory, REALDMG.O88 | - | 100% | - |
  | SML, Victory, precompiled | 3 of 3 | 100% | - |
  | Kirby, Victory, REALDMG.O88 | - | 100% | 89% (warming up) |
  | Kirby, Victory, precompiled, 8 slots first | 1 of 4 | 17% | 10% |
  | Kirby, Victory, precompiled, images first + filter | 2 of 4 | 100% | 95% |
  | SML, 640 KB 8088, precompiled (title, no counters) | 2 of 3 | 11.9 fps | - |
  | Looney Tunes (.gb), Victory, REALDMG.O88 | - | 98.8% | 75% (translating) |
  | Looney Tunes (.gb), Victory, precompiled + counters | some of 7 | 100% | 99% |

  The 17% was two defects, both fixed (REALDMG-SPEC 20.9, 20.10): the plan
  traded images for slots, and every interpreted jump searched the list.
  On the Victory both packages hold 100%; the precompiled one translates
  nothing, and its worst second is 95% where the recompiler's is 89%.
- [x] `.o88`s of the owner's games for the owner to test (not committed).

### W4 - counters and the bundle

- [x] Per-block counters and promotion in the host build (REALDMG-SPEC
  20.11): counted EXACTLY in the harness, over its script or a replay the
  owner recorded, so nothing in the package counts and no NAME.RDH is
  needed - the replay RealDMG already writes is the input. SML's hot code
  went from four images to one.
- [x] The miss log: the same run's ROM PCs that went to the interpreter,
  added as block starts.
- [x] `make gbaotbundle` (REALDMG-SPEC 20.12): the window, the tools and
  the prebuilt binaries; needs Python and Unicorn only.
- [ ] Not built: the RAM idiom (W0), a state with cartridge RAM as a heat
  source, and a 286 speed figure with the 100% cap lifted (both packages
  already hold the Game Boy's own speed on the Victory).

### After W4 - the field and the merge

- [x] The owner's 286 (Packard Bell Victory, 4MB, `.cold` in the HMA):
  Kirby's Dream Land `P1/4` and Super Mario Land `P3/3`, "the best it has
  ever played". Two field defects found on the way and fixed (REALDMG-SPEC
  20.10): image reads refused on a hard disk's clusters, and four images
  starving the bank cache (13,705 banks fetched in 100 s).
- [x] The ROM inside the package (REALDMG-SPEC 20.13), under 1MB.
- [x] Merged with the kern_mega RealDMG work: the shipped REALDMG.O88 and its
  kern_mega arm are byte-identical to elendilon's; the precompiled gates
  pass on the merged core.
- [ ] kern_mega's arm (REALDMG-SPEC 20.14): today it refuses there, cleanly.
- [ ] kern_mega's arm is ON HOLD at the owner's word until the mega memory
  rework lands; it and that rework are both "how kern_mega does memory".
- [x] Speed, round 1 (86Box `286-victory`, 580K heap, Looney Tunes (GBC)
  holding Right through the stretch at 20-38 s that saturates both arms;
  `tests/rdgcore/rdgwin.py --profile` now charges samples to the
  precompiled images and their blocks):

  | | images | 25 s | 40 s |
  |---|---|---|---|
  | REALDMG.O88 | - | 89.3% (23% at worst) | - |
  | precompiled, as shipped | 1 of 8 | 97.2% | - |
  | ...images claimed first, from the ceiling, the load's hold let go | 2 of 8 | 95.5% | 91.5% |
  | ...the misses walked, their heat their blocks', counted on the stretch | 2 of 8 | - | 92.5% |

  The seconds inside the stretch move by +-15 points between two runs of
  one package, so the image fix is NOT a measured speed-up here: this
  scene's hot code was in image 0 all along. What it buys is the cold
  code a different scene runs, which the stretch does not exercise.

  Found and fixed on the way (REALDMG-SPEC 20.3, 20.10, 20.11): the plan
  gave every KB to bank slots before a cold image; two of our own claims
  held mid-heap split the slots' run; a block at FF:3FFE across the bank
  boundary that a miss made a start HUNG the promoted build after frame
  3,000 (the packages sent before it carry that block); a miss's entries
  never reached its block, and a miss the first walk had not reached was
  dropped. Kirby on the owner's replay keeps 99.5% (10 slots, 4 fetched).
- [ ] Speed, round 2 - the translator, shared with REALDMG.O88. The stretch
  is the game's object loop at FF:3E44/3E52 (32 bytes to HRAM and back with
  `LD (FF00+C)`, eight objects a pass): 17% of the machine on BOTH arms,
  ~22 x86 instructions a pass of 5 Game Boy ones. What carries it: the
  `LD A,(HL+)` region compares, the HRAM store's guard, and the flags'
  `sahf / dec / lahf / or ah,20h / sahf` round trip on every DEC whose Z
  the branch reads. Kept in x86 form through a loop and made AH only on its
  exit, that last is ~5 instructions a pass. Not started: it is the shared
  flag model, and the gates are cpu_instrs, the 15 ROMs and both arms.
- [ ] The RAM idiom (W0): HRAM's DMA routine is 9,518 of the stretch's
  13,053 misses (FF:FFE9), interpreted.
