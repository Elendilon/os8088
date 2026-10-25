# A FULL static recompile of a Game Boy game: feasible, and the interpreter shrinks but does not vanish

**A study: feasibility, limits, ideas and options.** 2026-10-25, a four-core
cloud container, branch `realdmg-fullstatic` cut from `elendilon` at
9f83477. Nothing in it is built.
- **The question** (the owner's): translate a cartridge's code WHOLE, ahead
  of time, so that it runs without RealDMG's interpreter. The output is
  either a runnable `.o88` (the tool may be host-side) or something
  `REALDMG.O88` loads.
- **What already answers part of it:**
  - docs/reports/REALDMG-STATIC-2026-10-20.md asked whether an ahead-of-time
    translator is FASTER. It found it feasible and refused it for speed.
  - REALDMG-SPEC section 16.8 built Static, which replays a PROFILE of
    earlier sessions' blocks through the dynamic translator.
  - REALDMG-PLAN's *"A future idea ... a FULL static recompile"* names the
    case for it: **completeness, not speed.** A level the profile never saw
    is interpreted, so the stall Static was built to remove only moves.
  This study does not repeat those findings. It asks the question they left:
  **what would it take to need no interpreter at all, and what shape would
  the result have?**
- **Every figure is marked MEASURED or PREDICTED.**
  - The new MEASURED rows are `tools/gbstatic.py` runs under Peanut-GB, on
    the test ROMs the tree fetches (`tools/getgbtest.py`) and on the owner's
    own dumps of **Super Mario Land** (SHA-256 `49fbd2f6...41dc`) and
    **Kirby's Dream Land** (`0f6dba94...8d58`). Those were handed over for
    this study and are not in the repository.
    - Both reproduce the 2026-10-20 report's coverage rows to the digit.
    - The per-bank, block, heat and RAM-code figures below are new.
    - gbprof's platformer input script, frames 800-7,200: 107 s of Game Boy.
  - PREDICTED rows are priced at that report's measured rate: **20.2 bytes
    of 8086 code for each Game Boy instruction**, exits included.
  - **Kirby's Dream Land under that script is a thin sample**: 1,715
    distinct instructions ran, against Super Mario Land's 4,755. The script
    was written for a platformer that scrolls right. So Kirby's heat figures
    describe its first level, not the game.

## 1. The answer

**Feasible: yes, per game, with a host tool. The interpreter can leave the
hot path completely. It cannot be removed from the machine in general.**
- **What is solvable is engineering, and it is known.**
  - Translating every ROM instruction a game reaches.
  - Chaining blocks directly with no lookups.
  - Handling the dozen instructions today's translator hands back to the
    interpreter on purpose (section 2.2).
  - Paging translated code with its ROM bank.
- **Two things cannot be settled ahead of time in general, so they need an
  answer that runs while the game does:**
  1. **Code run from RAM.**
     - Every game copies an OAM DMA routine into HRAM and calls it every
       frame.
     - Some games keep thunks there (Looney Tunes: 45 busy instructions a
       frame, MEASURED, 2026-10-20).
     - Blargg's `cpu_instrs` runs **81%** of its busy instructions from RAM
       and `instr_timing` **100%** (MEASURED, section 3).
     - The bytes are the game's to write, so no host can know them for
       certain beforehand.
  2. **Computed jumps the walk does not resolve.**
     - Super Mario Land's sound driver: 0.12%. Looney Tunes: 2.2% (MEASURED,
       2026-10-20).
     - `dmg-acid2`'s `JP HL` dispatch is **70%** of its busy instructions to
       a plain walk and 0% once traced targets are added (MEASURED,
       section 3).
     - Whether a walk has found every target is undecidable in general. A
       host trace covers only what its run played.
- **So the realistic product is a game that RUNS ZERO interpreted
  instructions in normal play, kept correct by a fallback that is small,
  slow and cold.** Every Game Boy static recompiler surveyed keeps one too:
  gb-recompiled *"falls back safely to the interpreter when static analysis
  did not compile a target"* ([source](https://github.com/arcanite24/gb-recompiled)).
- **For the two games handed over, the general limit hardly bites**
  (MEASURED, section 3):
  - **Neither runs anything from RAM but its OAM DMA routine**: six sites,
    3 busy instructions a frame. Super Mario Land's is at FFB6h and Kirby's
    at FF80h. That one is an idiom (4.4).
  - Super Mario Land's walk misses 0.12%, its sound driver's `JP HL`
    targets in bank 3. Its trace finds all of them.
  - Kirby's walk misses nothing.
  - **So both could run STRICT, with no interpreter in the image at all**,
    on what this run played. What it did not play is the coverage loop's
    question (6.4), and it is the reason a fallback ships.
- **A "strict" build without the fallback is still worth having, as an
  INSTRUMENT.** In it, an unknown PC stops the machine and records PC and
  bank. That turns "is coverage complete?" from a question into a log the
  host tool can read and rebuild from (idea 6.4).

**Recommendation, in order** (section 7 has the waves):
1. **B0 first, a measurement that costs no package byte.** A host tool
   writes a COMPLETE `NAME.RDP` from walk plus trace, weighted by heat the
   host can actually measure. Today's Static preloads it. That answers
   whether completeness removes the transition stalls before anything is
   built for it.
2. **Then A.** A per-game `GAME.O88` built on the host from emitted
   assembly, with today's interpreter demoted to a lazy fallback part that
   normal play never reads. The strict build is its coverage instrument.
3. **B (a precompiled file `REALDMG.O88` loads) only if the owner wants one
   package rather than one per game.** It binds a data file to one build of
   the templates (section 5.3).

## 2. What "the interpreter" does in a recompiled run today

"No interpreter" means removing more than the handlers. Today's
recompiler leans on the interpreter in five places.

### 2.1 The five dependencies

| dependency | where | what a static build must do instead |
|---|---|---|
| **The resume.** `rdg_resume` enters through `[S_RESVEC]`, the interpreter's `RDG_DISPATCH`, and the recompiler is reached from there (`tr_ejd`/`tr_ekey`) | REALDMG-SPEC 5.2, 6.3 | a PC-to-code dispatcher of its own (section 4.3) |
| **The hand-backs.** An opcode with no template ends its block with `mov si,PC / jmp tr_int`, the interpreter's dispatch | `rt_ctl`, `rdgjit.inc` | write each one (2.2) |
| **RAM code.** RAM is never translated; the interpreter's own branches stay there (`JDISPATCH`). HRAM is translated behind a guard | REALDMG-SPEC 16.3 | known idioms made native; the rest to the fallback (4.4) |
| **A fixed table's misses.** Under Static a PC with no block is the interpreter's | REALDMG-SPEC 16.8 | completeness, or the fallback |
| **The tails.** `rd_slow`, `io_rd`, `io_lcd`, `io_wr`, `mbc_set`, `cnt_ff`, `stat_ff` and the rest live in the CORE's half-slots, and every template near-jumps to them at those offsets. That is why each cache segment carries copies at the same places | REALDMG-SPEC 4, 16.2 | keep them: they are the runtime and not the interpreter (2.3) |

### 2.2 The instructions handed back on purpose

- **No template, so the interpreter takes them** (`rt_ctl`):
  - HALT, STOP, RETI and the eleven invalid opcodes;
  - `LD (nn),SP`, a template over the size limit (`rdgtmpl.TMAX`).
- **A template that leaves for `tr_int` at its own instruction in a rare
  case:**
  - the `(HL)` read-modify-writes when the address is ROM, the MBC, I/O or
    IE (`rdggen.rmw_lines`);
  - the inlined bank select when `S_BANKHI` is set or the bank is not in
    memory (REALDMG-SPEC 16.1).
- **Each is a single instruction**, so the static build needs a
  SINGLE-STEP routine for each: the interpreter's own handler body, ending
  in the static dispatcher instead of `jmp dx`. That is about a dozen
  handlers of a few hundred bytes in all (PREDICTED), plus a generic
  "one instruction at PC" step for the rest.
- **This is the largest piece of hidden work, and it is not hard.**

### 2.3 What the core segment really is

- **What is in it, MEASURED** (REALDMG-PLAN's *Release memory*): **17,241
  bytes of code in a 65,536-byte carve.**
  - main handlers 6,806;
  - CB handlers 7,364;
  - shared tails 3,071;
  - 48,295 bytes of fill, now the recompiler's second tier (REALDMG-SPEC
    16.2.2).
- **The layout is an artefact of the interpreter's dispatch** (`jmp dx` onto
  opcode x 256). A static build needs neither the layout nor the fill.
- **What it does need is ~3 KB of tails.** It can also give them any
  address. `rdgtmpl.py` already knows which template bytes are relative
  jumps to which helper, and a host translator can retarget them.
- **So a static image saves most of 64 KB of carve.** That is the
  interpreter's real memory cost, and it is a cost a 640 KB machine
  notices.

## 3. Coverage: what a host walk plus a host trace finds

**`tools/gbstatic.py` measures it.** It walks from 0100h, the RSTs and the
interrupt vectors, reads `RST` jump tables, and tracks a constant `A` into
the bank write. `tools/gbprof/gbcover.c` records what ran, under Peanut-GB,
with gbprof's input script.

**The commercial games** (frames 800-7,200; the first two MEASURED again
today on the owner's dumps and identical to the 2026-10-20 report, the other
two that report's):

| game | plain walk | with RST jump tables | plus targets seen at JP HL and RET | busy from RAM, a frame |
|---|---|---|---|---|
| Super Mario Land (64 KB, MBC1) | 31.3% | **99.88%** | 100% | 3.0 (OAM DMA) |
| Kirby's Dream Land (256 KB, MBC1) | 100% | 100% | 100% | 3.0 (OAM DMA) |
| Looney Tunes (1 MB, MBC5) | 97.8% | 97.8% | 99.7% | 45 |
| Dr. Mario (32 KB) | 94.9% | ~100% | ~100% | - |

**What a static build would have to make, MEASURED** on the two games
(`aotcount`, a scratch script over gbstatic's walk and gbcover's trace;
section 11). A *leader* is a place a block starts: an entry, a branch
target, a fall-through or a jump table's word. The device translator also
cuts a block at 40 instructions and at 4000h, so blocks are at least this
many.

| | Super Mario Land: walk / walk + trace | Kirby's Dream Land: walk / walk + trace |
|---|---|---|
| instruction starts found | 8,532 / 10,064 | 12,469 / 13,537 |
| block leaders | **1,935** / 2,601 | **3,115** / 3,222 |
| return sites (after a CALL or RST) | 341 / 368 | 955 / 1,010 |
| side entries (after a store that may reach IF/IE/MBC, or EI; 4.2) | 749 / 879 | 692 / 794 |
| instructions that ran | 4,629 / 4,755 | 1,715 / 1,715 |
| ...ran at least once every 20 frames ("hot") | 1,897 / 1,928 | 1,280 / 1,280 |
| **share of busy execution in the hot set** | **99.1%** / 99.2% | **99.9%** / 99.9% |

- **The walk + trace column over-counts.** A call from bank 0 into
  4000-7FFF whose bank no constant decided is walked in EVERY bank (11 such
  calls in Super Mario Land seeded, 1 in Kirby's), so data in banks that
  never run is read as code: Super Mario Land's bank 1, 424 instructions
  that never ran; Kirby's banks 2-4 and 7-0F, a few hundred. The walk's
  16 and 10 "invalid opcode" stops are the same thing. Whole-cartridge code
  is therefore an UPPER bound, and a bank guess the trace never confirms
  is the first thing to prune.
- **The hot set is a fifth of the code and nearly all of the time.** That is
  what makes 6.1's two grades of code worth having.

**The test ROMs, MEASURED today** (`python3 tools/gbstatic.py
build/gbtest/<rom> --frames 4000`, 3,200 frames measured):

| ROM | busy instructions a frame | of them from RAM | plain walk | plus traced targets |
|---|---|---|---|---|
| `GBDEMO.GB` (ours) | 40 | 0 | 100% | 100% |
| `dmg-acid2` | 130 | 0 | **30%** | 100% |
| `cpu_instrs` | 6,993 | **5,694 (81%)** | 99.99% of the ROM part | 100% of the ROM part |
| `instr_timing` | 5,852 | **5,852 (100%)** | - | - |

**What this means for a static build:**
- **The walk is the backbone, and a trace has to be added to it.**
  `dmg-acid2` shows that a dispatcher which is not an `RST` defeats the
  walk's one jump-table rule: 92 of 239 sites, 70% of the work. One traced
  run finds them all.
- **The trace covers only what it played.** A level never reached in the
  trace is reached only through the walk, and the walk's misses (Looney
  Tunes' 0.3%) are exactly the computed jumps. That residue is what the
  fallback is for, and what the strict build logs (idea 6.4).
- **More jump-table rules would shrink it.** The common SM83 idioms are
  `ADD A / LD E,A / LD D,0 / ADD HL,DE / LD A,(HL+) / LD H,(HL) / LD L,A /
  JP HL` with HL a constant base, and the same through `RST 28h`. Constant
  propagation already tracks A; carrying HL's base through the idiom bounds
  the table by reading words while they point at plausible code in the
  same bank. PREDICTED to take most of the sound-driver misses; it must be
  validated against the trace, never trusted alone.
- **The blargg suites cannot run "strict".** They copy the instruction under
  test into RAM. They stay the gate for the FALLBACK and for RealDMG
  itself, not for the static build's translated code (section 6).

## 4. The design problems, one by one

### 4.1 Banked code

- **Code in 4000-7FFF is keyed by (bank, PC)**, as the block table already
  keys it.
- **Statically, the walk knows a call's bank when a constant reached the
  bank register.** Otherwise the target is "4000-7FFF in some bank", and
  the exit is today's 13-byte form with its run-time `S_BANK` check
  (REALDMG-SPEC 16.4).
- **Emitted code can do better than one check.** An exit whose bank the
  walk could not know dispatches on `S_BANK` through a per-PC list of the
  banks that have a block at that PC. It is usually one entry.
- **ROM never changes**, so a translation never goes stale. That is the
  property that makes a Game Boy a good static target, where a machine with
  RAM-resident code (the C64, the Apple II) is not.

### 4.2 Interrupts and the resume

- **Events are taken only at block ends** (REALDMG-SPEC 6), so the PC an
  interrupt pushes and RETI pops is a block start by construction. Today's
  resume always lands on a block.
- **There are three exceptions**, each a statically known place:
  - an IF or IE write takes an interrupt *inside* the writing instruction,
    and pushes the NEXT instruction's PC (REALDMG-SPEC 7);
  - EI forces the next check;
  - a self-guarding store's slow path leaves through `tr_enter` with SI =
    NEXT (REALDMG-SPEC 16.5).
- **The static build makes every such NEXT a side entry**, a label inside
  the block. `LDH (FF),A`, `LD (FFFF),A` and `LD (FF0F),A` with a constant
  address are found by the walk. A store through a register that happens
  to reach IF/IE leaves through the guard, and its NEXT goes to the
  dispatcher, which needs the entry too. So every instruction after a store
  that is not provably RAM gets a side entry: **cheap, a table row each**.

### 4.3 The dispatcher

What remains dynamic is a lookup from GB PC to 8086 address, at three
points:
- RET and RETI, and a POP that becomes a return;
- `JP HL`;
- the resume after an event.

Unlike today's, the static build's set of entries is FIXED and KNOWN, so
the lookup can be a structure generated on the host:
- **Per region, a sorted list or a perfect hash** of the entries, generated
  by the tool. There is no counting, no eviction and no neighbour slot.
- **Its size, from the counts in section 3**: leaders plus side entries
  are ~2,700-3,500 for Super Mario Land and ~3,800-4,000 for Kirby's Dream
  Land. At 4 bytes an entry (the PC, the code's offset; the segment by
  region) that is **~11-16 KB**, today's small block table's size rather
  than "a few KB" (PREDICTED from MEASURED counts).
- **Most of it can be made cold** by resuming an event through a
  CONTINUATION.
  - The event exit already knows where it was going: the not-taken arm's
    8086 address. It stores that address beside `S_PC` in the state block,
    and `rdg_resume` jumps straight to it when `S_PC` is still that PC,
    with no interrupt taken.
  - RETI back to the interrupted PC can test the same saved pair, a
    one-entry cache.
  - The full table is then reached only by `JP HL`, a RET that is not to
    a return site, and a fallback's return. That is exactly today's
    6.9% of Super Mario Land's machine going to ~0 (`tr_ekey` alone is
    1.9%, MEASURED 2026-10-20).
- **RET keeps today's two-entry inline cache** (REALDMG-SPEC 16.4) in front
  of it.
- **The return-site set is the instruction after every CALL and RST**, plus
  what the trace saw. A RET to anything else (2.5 a frame of Super Mario
  Land's 49, MEASURED) takes the full lookup, and that is right.
- **GB CALL cannot become an 8086 CALL.** The Game Boy's stack is in the
  view and games read their own return addresses: `RST 28h` pops its
  return to find its table. So the pushed word must stay the GB PC.

### 4.4 RAM code

- **For both games handed over this is ALL their RAM code** (section 3):
  six sites in HRAM, the DMA routine's, 3 busy instructions a frame.
- **The OAM DMA routine is an idiom**: `LD (FF46),A / LD A,28h / DEC A / JR
  NZ / RET`, in HRAM, called every frame. Recognise the COPY from ROM to
  HRAM on the host and translate the routine from its ROM source. At run
  time a guard compares the HRAM bytes once, which is today's `rt_guard`
  with its block made ahead of time.
- **Other RAM code seen in the trace** can be translated the same way, keyed
  by its bytes. A guard miss goes to the fallback.
- **What the game writes and runs that the host never saw** (self-modifying
  routines, decompressors running code they unpacked, Pokemon's glitches)
  is the fallback's by definition.
- **A strict build stops there and logs it.** This is the one limit no host
  tool can lift, short of putting a translator back on the machine. That
  translator is exactly the dynamic recompiler this exercise removes.

### 4.5 Code size

**By bank, MEASURED counts priced at 20.2 bytes an instruction (PREDICTED
sizes); the walk with RST tables, no traced seeds:**

| | instructions found | all-template | ran | hot | two grades (6.1) |
|---|---|---|---|---|---|
| **Super Mario Land**, bank 0 | 6,260 | 123.5 KB | 3,211 | 1,202 | 45.9 KB |
| bank 2 | 522 | 10.3 KB | 315 | 68 | 3.3 KB |
| bank 3 | 1,750 | 34.5 KB | 1,103 | 627 | 17.3 KB |
| **whole cartridge** | 8,532 | **168.3 KB** | 4,629 | 1,897 | **66.6 KB** |
| **Kirby's Dream Land**, bank 0 | 6,685 | 131.9 KB | 818 | 503 | 37.1 KB |
| bank 1 | 1,206 | 23.8 KB | 0 | 0 | 5.3 KB |
| bank 5 | 2,295 | 45.3 KB | 851 | 731 | 21.3 KB |
| bank 6 | 2,283 | 45.0 KB | 46 | 46 | 10.7 KB |
| **whole cartridge** | 12,469 | **246.0 KB** | 1,715 | 1,280 | **74.4 KB** |

With the traced seeds and their over-count (section 3) the wholes are
198.5 / 73.8 KB and 267.0 / 79.1 KB.

**Three things follow:**
- **Full-template code is two and a half to three times the ROM it came
  from.**
- **Bank 0 alone does not fit one 64 KB segment all-template**: 123-133 KB.
  So bank 0's code needs at least two segments, and every bank-0 to bank-0
  jump that crosses them is a far jump. With two grades it is 37-46 KB, one
  segment with room for its tails.
- **A ROMX bank's code is small**: 22 KB at most in two grades (Kirby's
  bank 5). So code paged with its bank (6.2) is a slot of 16 KB of ROM
  plus at most ~22 KB of code.

## 5. The options

### 5.1 B0 - a complete profile for today's Static (no package change)

**What it is.** A host tool takes walk plus trace, writes every block start
it finds into `NAME.RDP`'s format (REALDMG-SPEC 16.8), and the Static the
package already has preloads it.

**What it fixes that the device never could: heat.** REALDMG-SPEC 16.8 has
*"There is no heat in the weight"*. Two device-side samplers were built and
refused, because the core runs with interrupts off. A host trace counts
every execution exactly, so the preload's heaviest-first order becomes TRUE
heat, and a cache too small for the whole game keeps the right part of it.

**Limits:**
- **The profile holds 2,048 entries** (`RW_PRFN`). Super Mario Land's walk
  has **1,935 leaders** and fits; walk + trace has 2,601, of which ~420
  are the over-count of section 3. Kirby's Dream Land has **3,115** and
  does not fit (MEASURED counts). `RW_PRFN` = 4,096 is a one-line change
  and a 17 KB claim in place of 9.
- **The code room is the tiers' ~163 KB**: 58 + the core's 47 + 58 with
  Cache: 128K (REALDMG-SPEC 16.2.1, 16.2.2). Super Mario Land's 168 KB
  all-template nearly fits; Kirby's 246 KB does not.
- **The hot set fits with room to spare**: 1,897 and 1,280 instructions,
  ~37 and ~25 KB. Heaviest-first by host heat, both games preload EVERY
  instruction that is 99%+ of their time, and only the cold remainder is
  cut off by a full cache.
- **A bank the bank cache has not got is skipped by the preload.**
- **The preload's translation time at launch is UNMEASURED for ~2,000-3,100
  blocks.** 655 blocks on a 286 were unremarkable, and an 8088 is the risk.
- **The interpreter stays**, and so does every byte of today's memory.

**Cost:** one host tool of a few hundred lines (`tools/gbstatic.py` already
has the walk), and zero package bytes. **It is the experiment that says
whether completeness is the cure** before anything is built for it.

### 5.2 A - a per-game package, `GAME.O88`, built on the host

**What it is:**
1. `tools/gbaot.py GAME.GB` writes `build/gbaot/<game>/code*.asm`.
   - **It writes ASSEMBLY, not bytes.** It reuses `rdggen.py`'s
     `template_lines()` bodies, the source the device templates are
     assembled from, so a translated instruction is still its interpreter
     handler's body.
2. nasm assembles it.
3. The package is `realdmg.asm` built with an `%ifdef RDG_AOT` arm that
   `%include`s the generated code and the same `rdgsys.inc`, `rdgppu.inc`
   and `rw*.inc`.
   - **It is one source, not a fork** (the `%ifdef` arm shape SPEC.md
     20.18's `PKG_MEGA` uses, and CLAUDE.md's "share as source").

**What the parts are** (SPEC.md 20.12, docs/plans/completed/O88-MULTISEG-PLAN.md):
- the runtime image;
- the view (a zero part, as today);
- one part per code segment of up to 64 KB, each carrying its ~3 KB of
  tails, or laid out around one copy of them (2.3);
- the ROM banks as parts, lazy or XMS-backed as the bank cache wants them;
- the fallback (5.4) as one LAZY part, which normal play never reads.

**Emitting source buys the structure the device translator cannot have:**
- **Direct chaining.** `jmp label` within a segment and `jmp far` across
  them. No link sites, no `tr_link`, `tr_lpatch` or `tr_rpatch`, no link
  log, no generation counters.
- **No block table, no counting, no eviction, no flush, no tiers.**
- **No translator on the machine.** The 20,952-byte part (REALDMG-SPEC
  16.9) and its 80-128 KB of cache and table become code sized to the game.
- **Whole-program analyses for free.**
  - flag liveness over the call graph (38.8% dead on Super Mario Land
    against the lookahead's 35.4%, MEASURED);
  - superblocks through fall-throughs (34% of conditionals fall through,
    MEASURED);
  - branching on the host's own flags after a Z-only write.
  - The 2026-10-20 report prices these at ~0.3 ms of 6.55 a frame, about
    5% (PREDICTED). They are a bonus here and not the reason.
- **Save states move between the two.** A state is the Game Boy's machine
  (GB PC, registers, the view), not the host's, so a `.SS1` written by
  `REALDMG.O88` should load in `GAME.O88` and back. That is worth a gate
  of its own (section 6).

**What it costs:**
- **The `.o88` contains the ROM**, and its code is derived from it. It is
  built from the user's `GBROMS=` into `build/` like `make realdmghd`, never
  committed, and never on a shipped disk or the Wire.
- **One build per game, per RealDMG version.**
- **A second arm of `realdmg.asm` to keep assembling.** It wants a
  `buildmatrix`-style row over one of our own ROMs (`GBDEMO.GB`, the
  `tools/gbprof` ROMs), which can be committed because they are ours.
- **Menu items that mean nothing in it**: CPU > Recompiler, Static,
  Profile and Cache. That is an `%ifdef` per item.

### 5.3 B - a precompiled file `REALDMG.O88` loads (`NAME.RDX`)

**What it is.**
- A host port of `rt_translate` writes cache-segment images and a block
  table, byte-identical to what the device would have made.
- The package loads them instead of preloading, as a fourth CPU mode.
- One package serves every game, and the user's ROM stays as it is.

**Why it is the weaker shape:**
- **The file is bound to one build.** It names tail offsets in the core and
  state-block offsets in the view (REALDMG-SPEC 4, `rdgdefs.inc`), so every
  RealDMG change that moves a tail invalidates every `.RDX`. It needs a
  fingerprint (a hash of `rdgtmpl.bin` and the core's tail table) and a
  refusal with a toast. In practice a regenerate after every update.
- **It keeps the dynamic machinery's costs**: link sites, the block table,
  the 64 KB carve and the interpreter, now resident for a fallback.
- **It gains over B0 only the launch's translation time.**
- **What it is right for**: one package, no per-game build, and a game that
  is still a document rather than a program.

### 5.4 The fallback: three grades of "no interpreter"

| grade | unknown PC or RAM code | resident cost | what it is for |
|---|---|---|---|
| **safe** | today's interpreter, demoted to a lazy part read at the first miss | 0 until a miss, then the core's 64 KB | the first build. Correct on every ROM, blargg's included |
| **compact** | a small interpreter, a switch on the opcode with no 64 KB dispatch layout | ~8-10 KB (PREDICTED: the handlers' 14.2 KB without their half-slot layout, sharing the tails) | the shipped shape. Slow, cold, correct |
| **strict** | the machine stops and records PC, bank and the bytes there in `NAME.RDM` | 0 | the coverage instrument (6.4); a game proven complete may ship strict, at the owner's word |

**REALDMG-PLAN refused a compact core for RealDMG itself, and the reason does
not carry over.** *"A smaller core costs every interpreted instruction"*
was the right refusal when the interpreter ran ~15-30% of a frame. Here it
runs none of a frame in normal play, so its speed buys nothing.

## 6. Ideas that change the numbers

### 6.1 Two grades of CODE, by heat

- **Hot code gets templates**, ~20 bytes an instruction: what ran at least
  once every 20 frames, ~1,900 instructions on Super Mario Land.
- **Cold code gets a compact form**: each Game Boy instruction becomes
  `call op_xx` with its operands inline, ~3-5 bytes. That is
  subroutine-threaded code. It does no decode and no dispatch, so it is
  still translated code, and on an 8088 a `call`/`ret` pair costs roughly
  what today's dispatch does (PREDICTED).
- **What it is not**: an interpreter by another name. Its handlers are the
  cold half of the same templates, and control flow is still direct jumps.
- **Super Mario Land 66.6 KB against 168.3 all-template, Kirby's Dream
  Land 74.4 against 246.0** (section 4.5: MEASURED counts, PREDICTED bytes,
  cold priced at 4.5 bytes an instruction). The hot grade carries
  **99.1% and 99.9%** of the busy execution.
- **The heat comes from the host trace**, and a cold block that turns out
  hot costs speed, not correctness.
  - Kirby's sample is thin (the header), so its grading is the one most
    likely to be wrong in later levels.
  - The cure is cheap: a cold block can bump a byte counter as it is
    entered, and the package writes the counters beside the strict log
    (6.4). The next host build promotes what ran hot. This is the heat the
    device could never sample (REALDMG-SPEC 16.8), because it is counted
    and not sampled.

### 6.2 Code that pages with its bank

- **A ROM bank's code is only reachable while that bank is mapped.** So
  bank n's code can be a part loaded beside bank n's data and dropped with
  it. Bank 0's code stays resident.
- **The bank cache (REALDMG-SPEC 10.3) already decides which banks are in
  memory.** A slot becomes ROM plus its code, and a fetch brings both.
- **This is what fits a 256 KB-plus cartridge's code in real mode.** It is
  the per-bank format REALDMG-PLAN's future-idea paragraph asked for,
  without the tiers.

### 6.3 Idioms ahead of time

- Today's loop idioms (REALDMG-SPEC 8, 8.1, 16.6) are recognised per block.
  Ahead of time they are found once, over the whole ROM, and a host can
  look for MORE shapes against the trace's heat. The 2026-10-20 report's
  three loops were 17-26% of Super Mario Land.
- Anything recognised must keep the M-cycle charge and the "BP covers it
  all" rule, as `cnt_ff` does.

### 6.4 The coverage loop

1. The strict build's `NAME.RDM` records every miss: PC, bank, the
   instruction bytes, how it was reached (RET, `JP HL`, resume).
2. `tools/gbaot.py` reads it back as more seeds and rebuilds.
3. Two or three rounds of play converge. A game that plays through with an
   empty `.RDM` is complete for what was played.
- **This is the only honest completeness claim available.** Static analysis
  cannot make it, and a host trace makes it only for its script.

## 7. A plan, if the owner takes it

| wave | what | answers |
|---|---|---|
| **W0** | `tools/gbaot.py cover`: walk + Peanut-GB trace union, more jump-table rules, the unresolved list; writes a COMPLETE, heat-weighted `NAME.RDP` (B0) | does completeness end the transition stalls on today's Static? What does a 2,000-3,100-block preload cost at launch on an 8088 and a 286? |
| **W1** | a host port of the translator, gated BYTE-IDENTICAL against a device cache dump (the 2026-10-20 report's 86Box dump is the method) | is the host translation exactly the device's? It is the foundation of A and B both |
| **W2** | A, safe grade: `GAME.O88` from emitted assembly, static dispatcher, side entries, the dozen single-steps, today's core as a lazy fallback part | events and skip checksum EQUAL to the interpreter's over gbprof's script (the recompiler's own gate, REALDMG-SPEC 16.1); a miss counter that reads 0 in the scripted play |
| **W3** | strict grade and `NAME.RDM`; two grades of code (6.1); code paged with its bank (6.2) | memory on a 640 KB 8088 and a 286 with XMS; the coverage loop's convergence |
| **W4** | compact fallback; whole-program flags and superblocks | the speed bonus, measured on `286-victory` and MartyPC |

**Gates the work would need:**
- **Equivalence:** the static build and the interpreter take the same events
  and skip the same M-cycles over the same input. This is what `gbcpu`,
  `gbacid` and the harness already demand of the recompiler.
- **A NEGATIVE CONTROL for each idea:**
  - a dispatcher entry removed must make the strict build stop at that PC;
  - a side entry removed must lose the IF write's interrupt (a
    `tools/gbprof` ROM of ours writes IF mid-block);
  - a stale RAM guard must be refused.
- **Save-state interchange** between `REALDMG.O88` and `GAME.O88`.
- **All of it on our own ROMs** (`tools/gbprof/*.asm`, `GBDEMO.GB`), so it
  can be a registered row. The commercial games stay the owner's field
  measurement.

## 8. Memory, per option (PREDICTED)

**The common rows:**
- the package's region with no recompiler part, ~33 KB (REALDMG-SPEC 16.9);
- the view, 64 KB;
- the frame buffers and damage memory, 32 KB;
- for A, the dispatcher's table, ~16 KB (4.3).

Code is section 4.5's whole-cartridge figures.

| | Super Mario Land (64 KB ROM) | Kirby's Dream Land (256 KB ROM) |
|---|---|---|
| today, Recompiler (REALDMG-PLAN *Release memory*) | 350 + 64 = **~414 KB** | 350 + 10 bank slots (160) = ~510 KB, a 286 with XMS |
| B0 / B | as today, + the profile's 9 (or 17) KB | as today |
| A, all-template, safe grade | 33 + 64 + 168 + 16 + 64 + 32 = **~377 KB** | 33 + 64 + 246 + 16 + 256 + 32 = ~647 KB: **does not fit 640 KB** |
| A, two grades of code (6.1) | 33 + 64 + 67 + 16 + 64 + 32 = **~276 KB** | ROM whole: 33 + 64 + 74 + 16 + 256 + 32 = ~475 KB, **~26 KB over** a 640 KB machine's ~449 KB arena |
| A, two grades, ROM in 10 bank slots (XMS) | - | 33 + 64 + 74 + 16 + 160 + 32 = **~379 KB**, a 286 |

**Reading the table:**
- **A whole-cartridge static build of a 64 KB game uses LESS memory than
  today's recompiler**, even all-template. It drops the cache, the block
  table, the translator, the templates and the core's carve.
- **A 256 KB game wants two grades of code, and the bank cache for its
  ROM.** In two grades its code is small enough to keep resident WHOLE, so
  6.2's paging is a reserve for a bigger cartridge and not a need for this
  one.
- **An 8088 cannot hold Kirby's Dream Land plus its code**, as it cannot
  hold it beside today's cache. 26 KB is the arithmetic and could be won
  (the damage memory's 15 KB, a compact cold grade). It stays a machine
  limit unless someone wants to chase it.

## 9. Limits, stated once

- **No proof of completeness ahead of time**: RAM code and unresolved
  computed jumps (sections 3, 4.4). The fallback or the strict log answers
  them, nothing else.
- **Test ROMs that run from RAM** (blargg) exercise the fallback, not the
  static code.
- **The output contains, or is derived from, the user's ROM**: personal
  builds only, the `make realdmghd` rule.
- **One build per game per RealDMG version** (A), or one file bound to one
  build (B).
- **Speed beyond completeness is small**: ~5% from what only the
  whole-program view proves (2026-10-20 report, PREDICTED). The remaining
  win is the removal of `tr_link`/`tr_rpatch`/`tr_ekey`/`tr_enter`, 6.9% of
  Super Mario Land's machine (MEASURED), less the static dispatcher's
  share.
- **What it removes for certain**: warm-up, counting, flushes, recycling
  and the stall. On a frame where Kirby's Dream Land walking spends 32% in
  the interpreter and `tr_enter` (REALDMG-SPEC 16.6), that is the part of
  the machine a static build turns into translated code. At the 8088's
  measured 21.7 clocks a busy M-cycle against 51 (REALDMG-SPEC 16.10), that
  is the largest number in this file. It is still PREDICTED for any game we
  have not run.

## 10. Questions for the owner

1. **What is the goal**: no stall (completeness), less memory, more speed,
   or a game as its own icon on the desktop? Completeness alone is B0 and
   maybe B; memory and the icon are A.
2. **Is a cold fallback acceptable** (safe or compact grade), or is strict a
   requirement? Strict means a game that misses a target stops rather than
   slows.
3. **Is one `.o88` per game, built from your ROMs and never shipped,** the
   shape you want, against one `REALDMG.O88` and a data file per game?

## 11. Reproduce

```sh
python3 tools/getgbtest.py                            # the test ROMs, pinned
python3 tools/gbstatic.py apps/realdmg/GBDEMO.GB --frames 3000
for r in cpu_instrs/cpu_instrs.gb instr_timing/instr_timing.gb dmg-acid2/dmg-acid2.gb; do
    python3 tools/gbstatic.py "build/gbtest/$r" --frames 4000
done
export OS88_GB_ROMS=<dir>                             # the commercial rows, the owner's
python3 tools/gbstatic.py $OS88_GB_ROMS/SML.GB      # writes build/gbprof/SML.GB.cov
python3 tools/gbstatic.py $OS88_GB_ROMS/KIRBY.GB
```

The per-bank, leader, return-site, side-entry and heat counts of sections
3 and 4.5 came from a scratch script over the same two calls:
`gbstatic.discover()` for the walk, `gbstatic.load_cov()` for the trace,
"hot" = busy executions >= frames / 20. It is not committed. A wave-0 tool
(section 7) would be its home.
