# RealDMG on kern_mega: more recompiler tiers in the heap the cartridge left (2026-10-25)

A MEASUREMENT, true of the trees named below and of no other (docs/README.md).
Base: `mega-dmg` at `c8df6b4c` (docs/reports/REALDMG-MEGA-2026-10-25.md's
tree). After: the commit that adds this file. Box: a four-core cloud
container; Bochs 2.7 (Ubuntu's) and 86Box at `tools/86box/UPSTREAM`'s pin
with this tree's patches. The cartridges are the owner's and blargg's
`cpu_instrs` (`tools/getgbtest.py`); none is committed. The contract is
docs/REALDMG-SPEC.md section 16.2.5. No kernel byte changed.

## 1. What the arm holds in conventional memory

kern_mega's arm keeps the cartridge above 1MB (REALDMG-SPEC 10.3.1), so the
heap it used to give the bank cache is free once a game is loaded. The base
spent none of it on the recompiler beyond its two cache segments:

| | base | after |
|---|---|---|
| block table (64KB) | in the cache's claim | **an extended-pool block**, `OSAPI_XMEM_RUN`'s selector |
| cache segments, 64KB each | 2 (cache A, cache B) | **4** (A, B and two extra tiers) |
| tiers in the round robin (16.2.3) | 3 (A, the core's holes, B) | **5** |

Measured by reading `[S_JITXN]` out of the view: **2 extra tiers on both
Bochs (`make megatrap`, 640KB conventional) and 86Box `286-mega` (the
owner's mr286, 640KB conventional, 4MB)**, with `RW_XRESKB` = 32KB left free
beside them. Before the table moved, the same rule found room for ONE
(both machines).

## 2. Correctness (Bochs, `tests/rdgmega.py`)

| leg | build | cpu_instrs | extra tiers | tiers recycled | traps in the core or a cache |
|---|---|---|---:|---:|---:|
| arm | `make mega`'s | passes all eleven | 2 | 0 | 0 |
| squeezed | the arm with `RT_SQUEEZE`, every cache segment ~0.5KB | passes all eleven | 2 | 6 | 0 |
| squeezed, `tr_lpx` broken (`mov es,dx` first) | links into an extra tier written through its code selector | passes - by luck | 2 | 6 | **24, the row RED** |

The squeezed leg's first turn fills all five tiers fresh, so six recycles
is every tier - both extra ones - written, recycled with its links undone,
and written again. The broken build's 24 are completed #GPs at CS `0FEC`,
an extra tier's code alias: each pushed a frame onto the Game Boy's stack,
which cpu_instrs happened not to read back, so the trap census is what goes
red and not the serial line.

## 3. Speed

Not measured as a change: no scripted play here reaches the thrash. 86Box
`286-mega`, Kirby's Dream Land:

| run | base | after |
|---|---|---|
| 60 s walking right in the first level | 361-414 blocks, 0 recycles, 100.5% | 0 recycles, 100.6% |
| 240 s of the attract, no input | 460 blocks, 0 recycles, 100.1% | 444 blocks, 0 recycles, 100.1% |

Both are inside cache A. The thrash the owner reports comes from playing
further into the game than either run gets. On the base the arm's capacity
was cache A + cache B + the core's holes (~140KB of code); after, it is
~270KB. Whether that holds all of Kirby's Dream Land's code is for a field
play to say: the F1 overlay's flush count, and `[S_JITRCY]` in the view,
are the readings.

## 4. Cost

| artefact | base | after |
|---|---:|---:|
| shipped `REALDMG.O88` | 48,894 | 48,895 (the core's `tr_lpx`, in a spare half-slot) |
| shipped image | 36,000 | 36,000, byte-identical |
| arm `REALDMG.O88` (kern_mega's disks only) | 48,894 | 49,508 |
| arm image / its recompiler part, uncompressed | 36,220 / 21,037 | 36,566 / 21,160 |
| the bare harness (`tests/rdgcore/rdghost.asm`) | byte-identical | |
