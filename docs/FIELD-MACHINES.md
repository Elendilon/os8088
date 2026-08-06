# FIELD-MACHINES.md — the real machines, and how to get a number off one

[PERFORMANCE.md](../PERFORMANCE.md) Part 9 records **sets**. This file records
the **machines** they came from, and how to reach the person holding one.

They are different things, and keeping them apart matters: Part 6 rule 8 says
every figure carries its machine, and Part 9's sets duly say "IBM PC 5150,
8088 at 4.77 MHz, 640KB" — but not *whose*, not what else is in the slots, and
not how a build gets from this repo onto a floppy in that machine. That last
one is the whole cost of a field run and it has never been written down.

Its sibling is [FIELD-NOTES.md](FIELD-NOTES.md), which records what real
hardware **found**. This one records what real hardware **is**.

---

## Why the register is in the repo rather than in someone's head

**An agent cannot tell one contributor from another, and the repo can.**

A session is told which account it is running as and forgets it when the
session ends; there is no memory between them. Nothing in a commit says "this
contributor owns a 5150" — the git history here is 120-odd commits authored
`Claude <noreply@anthropic.com>` plus two humans, and an author line is not a
hardware inventory. So an agent asked to "check this on the real machine" has
no way to know whether there *is* one, which one, or who to ask.

What is durable is the **fork**. `Elendilon/os8088` is visible to every
session that works in it — it is the remote, the branch name and the owner —
and it is visible to every human reading the repo. So the register is keyed on
the GitHub handle of whoever owns the iron, and it lives here rather than in a
conversation.

Handles, not email addresses: this repo is public (it ships releases and feeds
os8088.com), and a personal address in a tracked file is published, not
recorded. If you want a contact route in here, say so and put in the one you
want published.

---

## Machine E1 — `Elendilon`'s IBM PC 5150

**The machine this project is calibrated against.** Every measured number in
PERFORMANCE.md Part 2 came off it (Part 9 Sets 1 and 2), and SPEC.md quotes it
by name in a dozen places.

| | |
|---|---|
| owner | `Elendilon` — owner of this fork, `Elendilon/os8088` |
| machine | **IBM PC 5150**, Intel 8088 at 4.77 MHz |
| RAM | **640 KB** |
| video | **Hercules (720×348) *and* a CGA, both in the machine.** The probe (§39.1) finds the Hercules first, so the CGA column needs a `VIDEO=cga` build |
| floppies | two |
| sound | none |
| clock | a real **MM58167 card at 2C0h** — §37.90's rung 2, field-verified, and the one rung no emulator can reach *(unconfirmed that this is the same machine — see below)* |

### What it has measured

Not a specification — these are outputs, and they are here so a run that
disagrees with them is recognisable as news rather than noise.

| | |
|---|---|
| CPU, derived independently from `MUL` and `DIV` | **4.64 and 4.68 MHz** against a nominal 4.7727 |
| PIT counts per tick | 65,542, then **65,536 exactly** on the second boot |
| instruction floor | **4.34 clocks per instruction byte** |
| any small `gfx_*` call, both cards | **~756 µs** fixed — 765.64 / 765.70 µs for `GFX_PIXEL`, 0.008% apart |
| one 8×8 glyph cell | 901 µs Hercules, 909 µs CGA |
| a solid fill | 177 µs/row + 0.28 µs/px Hercules; 182 + 0.33 CGA |
| framebuffer read-modify-write | 79.6 clocks/byte Hercules, 81.0 CGA — only ~7 of them the bus |
| floppy | **238 ms per sector**, 2,100 bytes/second; a one-sector file open+read is 796 ms |
| the kernel's own interrupts | 1–3% of a busy CPU |

Two of those are the load-bearing ones. **756 µs** is the per-call floor
(SPEC.md §5.7), and **238 ms a sector** is why a 116KB module load is 57
seconds.

### Unconfirmed — `Elendilon` to fill

Written down as gaps rather than guessed, because this is a provenance file
and a plausible invention in one is worse than a blank:

1. **The floppy drives.** `bench360.img` is 9 spt / 40 cylinders, so 360KB
   5.25" DD is the assumption everything here makes. Both drives the same?
   Which one boots?
2. **How an image gets onto a floppy** — the actual turnaround for a field
   run, and the thing nothing in this repo knows. A Greaseweazle, a period
   machine with a working 5.25", a Gotek?
3. **Whether the MM58167 is in E1** or in a second machine. §37.90 says "a
   clock card at 2C0h in a 5150"; if it is this one, say so and the ladder's
   rungs get a machine.
4. **What makes it 640 KB** — a SixPakPlus or similar is implied by §37.90's
   prose, and whether the clock rides on it matters to anyone re-testing.
5. **The monitors.** Hercules wants TTL mono and CGA wants composite or RGB;
   is that two monitors, a switch, or a card swap — and does taking the CGA
   column mean physically changing something?
6. **Anything else in the slots** (Part 9 says no sound card; an XT-IDE or a
   hard-disk controller would make §52's driver testable on iron for the
   first time).

---

## How to take a set on E1

Part 9's own recipe, with the E1 specifics folded in.

```sh
make bench                    # build/bench360.img is the 5.25" one
```

- **Do not write-protect the bench floppy.** The reports are saved back to it,
  and a protected disk answers int 13h status 03h, which the OS correctly
  reports as `Write protected`.
- Boot `os8088-360.img`, open Disk B, launch `GFXBENCH.O88`.
  **`R`** runs it, **`S`** saves `GFXHERC.TXT` (or `GFXCGA.TXT` / `GFXVGA.TXT`
  — it names the file after the adapter it booted on).
- Then `SYSBENCH.O88`, likewise, to `SYSBENCH.TXT`.
- Carry the `.TXT` files off the machine and paste them into Part 9 with the
  four provenance lines Part 9 asks for.

**The second adapter needs its own build**, and it must not reach `build/`:

```sh
make BUILD=build/cga VIDEO=cga all     # its OWN directory, or build/ ships
                                       # a kernel that boots the wrong card
                                       # for everyone (check-images calls it
                                       # STALE, which is why that check exists)
```

A run is a few minutes of machine time: `gfxbench` is about fifteen seconds
now and `sysbench` about forty, most of it the two 16KB floppy reads — and the
machine is **frozen** while either runs, by design, so the screen sitting
still is not a hang.

---

## What to ask E1's owner for, and what not to

**Worth a field run** — nothing else can answer these:

- **Time.** QEMU is exact about how much work the guest does and useless about
  how long it takes (Part 4). Anything whose answer is in microseconds is a
  field question.
- **The three defects QEMU cannot show at all** (Part 3): a visible redraw, a
  double-draw flash, and input overrun. These are judged by a person watching
  the glass, and no screenshot substitutes.
- **A model this repo has been spending without measuring.** Part 9's "what
  the next set is being asked" table is the current list — the variable-shift
  slope, the table-lookup cost, the memory-form `mul`, the per-row fill term,
  and the whole-screen repaint.
- **The rungs no emulator has**: §37.90's MM58167 and RP5C01 clock tiers, and
  §39.1's video detection probe on real cards.

**Not worth a field run** — the container already answers these, faster and
reproducibly:

- **Counts.** How many fills, glyphs or walk iterations something does is
  exact under QEMU; instrument a counter and read it over QMP (Part 4).
- **Instruction counts.** `-icount shift=3,sleep=off` is deterministic to ±1
  and machine-independent.
- **Whether the pixels are right.** A byte-for-byte screendump comparison on
  `VIDEO=cga`, plus `tools/hercshot.py` for Hercules, settles rendering
  without leaving the container.

The rule of thumb: **send it a question about time or about what a human
sees; keep every question about work.**

### Handing over a build

State the **commit**, and hand over the images rather than a branch name — a
branch moves. `make check-images` should be clean at the commit you quote, or
the floppy holds something the source no longer says.
