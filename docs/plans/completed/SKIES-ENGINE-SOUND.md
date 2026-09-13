# An engine of its own for each aeroplane — CLEAR SKIES

> **BUILT.** SPEC.md 88.8.2 is the contract and SPEC.md 88.10.6 is the fix that
> had to come first; this file is the design record behind both, kept for the
> half that was hard, which was not the sounds.
>
> Four aeroplanes, four engines, and the sailplane still silent. **113 bytes**
> of image, no bss, no kernel byte, and `SKIES.O88` came out three bytes
> *smaller*. `tests/skiessound.py` is the gate — 24 checks, two red runs — and
> all 34 `skies*` soak rows are green.
>
> **The reason this file is worth reading is that it began as a costing and
> the costing was WRONG**, in a way the tree had already written down once and
> nobody had gone back to fix. §1 is that error. The bytes are §3 and take a
> paragraph.

---

## 1. The costing said 52% of everything the program had left. It was 1.1%.

The first pass at this measured the feature honestly — 109 bytes, built and
reverted — set it against Clear Skies' growth headroom of **208 bytes**, and
recommended cutting the design down to fit. Every number in that sentence is
right except the one that mattered.

**Where the 208 came from.** `skies.asm` declares its bss as

```
    OS88_BSS (CS_VOCAB_AT - (os88_image_end - $$)) + CS_VOCAB_MAX + CS_WLD_MAX
```

so `image + bss` is `CS_VOCAB_AT` plus the overlay — **a constant, whatever
the program's own size**. A gate reading that field cannot see a 2,000-byte
addition. The only honest reading of what is left is the **gap**: the middle
of the three `times` at the end of the file, the room between the top of the
ZWORD chain and the overlay's fixed base. That much the costing got right, and
it is a real and useful finding.

**What it then did wrong was treat the gap as a budget.** It is not a budget.
It is the distance to a **hand-set constant**, and the constant had stopped
tracking anything years of work ago:

| | |
|---|---|
| `CS_VOCAB_AT` goes 0xB400 → 0xBE00 | §88.4.5.5's end tables need the room |
| …and then stays at 0xBE00 while | §88.10.2 packs the art, §88.10.3 takes it out of the image, §88.10.4 makes the body a part, §88.10.5 takes the nine worlds out |
| so the program gets **thousands of bytes smaller** | and its growth room gets **no bigger at all** |

By the time anybody looked, the gap was 208 bytes, `-DCSPROBE` was 167 bytes
**over and did not assemble**, a `--vocab-at 0xC200` knob had been bolted onto
the Makefile to buy the diagnostic trees one rung back, and `skies.asm`'s own
comment said the gap was *1,444 bytes* — stale by 1,236, and believed.

**The tree had already caught this exact error and recorded it.** SPEC.md
§88.4.5.5, on the 2,560-byte end tables that were refused against this same
gap and then taken anyway:

> *"the arithmetic that refused it was correct … and it never asked what that
> gap was actually protecting."*

It protects **nothing**. It is claimed RAM that no instruction reads. The
costing made that mistake a third time, against a sentence in the binding
contract that says not to.

**The lesson is one line and it is not "check your arithmetic".** The
arithmetic was right both times. What neither pass did was ask what the number
it was measuring against was made of — and this one was made of somebody's
hand, years ago, on a program that no longer exists.

---

## 2. The fix: the address is DERIVED (SPEC.md 88.10.6)

`CS_VOCAB_AT` is `APP_MAX_SIZE - CS_VOCAB_MAX - CS_WLD_MAX` — 0xE3C0, the top
of the segment — computed in `tools/csworlds.py`, which imports `APP_MAX_SIZE`
from `tools/os88pkg.py` rather than copying it. There is no number left to
tune, so there is none left to leave behind.

| | before | after |
|---|---:|---:|
| the gap, shipped build | **208** | **9,872** |
| `CSDIAG` | 456 | 9,096 |
| `CSHZPROBE` | 871 | 9,511 |
| `CSPROBE` | **−167: did not assemble** | **8,473** |
| the heap claim | 51,776 | 61,440 |

**The claim is the whole cost and it is one this program has already paid.**
61,440 is 340 bytes above the 61,100 that `image + bss` measured before
§88.10.3 — a configuration that shipped and ran on every machine in the tree.
§88.4.5.5's three checks hold unchanged: the bss ships inside the part as a run
of zeros that LZ4 all but deletes, so the floppy does not notice; `SKIES` is in
`SMALLOMIT_GAMES`, so the 128 KB machine never loads it; and the rest is heap
on a machine this program takes whole for as long as it runs.

Two things went with it. **`--vocab-at` is deleted** — the overlay is hard
against the ceiling and there is nowhere to raise it to — and so is the
Makefile's `CSVOCABAT`, so a diagnostic tree and a shipped tree now assemble
against one `cswidx.inc`. **`make skiesdiag` works again**, and the row that
uses it passed in the soak below for the first time since it broke.

What this does **not** buy is room past `APP_MAX_SIZE`. The segment is 61,440
bytes because a package addresses itself with 16-bit offsets. The next time
Clear Skies runs out, the answer is another part — not another address.

---

## 3. The engines (SPEC.md 88.8.2)

`CSP_SND` at offset 46 — **appended**, for `CSP_INDK`'s reason — points at a
seven-byte record, and 0 means *no engine*. One shaper reads it:

> `Hz = CSS_IDLE + (source × CSS_SPAN) / 100`

| | idle → full | beat | source |
|---|---|---|---|
| Cessna 172 | 60 → 105 Hz | one tick in four, −5 | lever |
| Pitts Special | 75 → 160 | every other tick, −12 | lever |
| Fouga Magister | 260 → 1,200 | none | **spooled thrust** |
| Icon A5 | 95 → 190 | none | lever |
| Wassmer Bijave | *no record* | — | — |

**113 bytes of image** — 75 code, 38 data — of a 9,872-byte gap: **1.1%**.
`SKIES.O88` is 44,226 bytes, **three fewer** than before, and no floppy in any
of the four geometries moves a cluster. No bss. Under 1% of a flown frame.

Three things in it are worth more than the table:

- **A shut throttle is an IDLE and not silence.** It is the change that does
  most of the work: each aeroplane announces itself on the runway before
  anything is touched. `CSS_IDLE` = 0 *is* silence, so the field is the switch
  as well as the number and no code tests for it.
- **The Fouga follows `[cs_thracc]`, not the lever.** §88.7.5 has modelled a
  5.3-second spool since the jet shipped and nothing could ever *hear* it.
  This is the row that earns the feature; the other three are a table.
- **The beat is on the wall clock.** `cs_steps` drops sim ticks past
  `CS_MAXSTEP`, so a counted beat would slow down in a banked turn — the
  engine sagging exactly where the frame is heaviest. §88.8.2.1 is the whole
  argument.

---

## 4. What was measured, and what still cannot be

`tests/skiessound.py`, 24 checks, 62 s solo. It asks the **guest** what it is
playing — `[cs_tone]` over sixteen consecutive ticks — and computes the
expected note on the host from the record the guest holds. Two red runs:
`--clobber-shared` (every aeroplane gets the Cessna's engine: three checks go
red) and `--clobber-spool` (the jet reads the lever: one check goes red, on its
own, which is what makes it the jet's).

**All 34 `skies*` soak rows pass** — 5:35 at lane 4 — which is the scope the
overlay move reaches, every world pointer in the program having moved 0x25C0.

Three things the row's own construction had to learn, kept because each one
looked like a broken feature first:

- **`[cs_back]` is not "is it flying".** SPEC.md 88.10.5 says it is the mode
  the bracket took and is *never cleared on the way out*; the predicate is
  `cs_back ≠ 0 AND cs_quit = 0`. A loop waiting for `cs_back` to reach zero
  waits for ever.
- **`F` toggles.** Typing it again while the first is still being acted on
  walks straight back in, so the row asks once and then waits on state.
- **The Plane drop-down's clip is filled in when the title page arms it**, and
  reading it at launch answers a box whose centre is 41 pixels left of the real
  one. Every click then misses and the row that gets picked is the row that was
  already picked — which reads exactly like a drop-down that does not work.

**Two questions are left, and neither can be answered in a container.** Both
are `CSS_IDLE`'s. A real PC speaker rolls off badly below ~100 Hz and a
synthesised square wave does not, so the piston idles sound fine under MartyPC
and QEMU and may be inaudible on a 5150; and whether a 9.1 Hz tremolo reads as
an engine or as a fault is a listen. `CSS_IDLE` and `CSS_BEAT` are one word and
one byte per aeroplane, which is deliberately the cheapest thing in the design
to change once somebody has heard it (docs/FIELD-MACHINES.md).
