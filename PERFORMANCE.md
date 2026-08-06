# PERFORMANCE.md — the machine this is for, and why your emulator lies about it

**Read this before you change anything that draws, lays out, or loops.** It
is required reading alongside [SPEC.md](SPEC.md) (what the kernel *is*),
[CLAUDE.md](CLAUDE.md) (how to work on it) and
[docs/TESTING.md](docs/TESTING.md) (where a test can run at all). This one
is about the target machine, which is not the one you are looking at.

**A bare `§` here means SPEC.md**, as it does everywhere else in this repo.
This document's own divisions are called **Part 1**..**Part 8**, so the two
can never be confused.

os8088 targets an **IBM PC/XT: an Intel 8088 at 4.77 MHz**, 4,772,727 cycles
a second, an 8-bit bus, no cache, no multiplier worth the name, and a
framebuffer on the far side of ISA. Every agent that has worked on this
project has tested it on QEMU under a container that is roughly **three
orders of magnitude faster**. QEMU is not a slow-machine simulator; it runs
the guest at host speed and models no 8086 timing whatsoever.

That gap has cost this project defect after defect — a drawing primitive nine
times slower than the one it replaced while measuring identical (Part 3), a
window operation costing two whole-screen repaints per click (§26.2), a
keystroke that flashed its line blank on every press (§27.2), a benchmark
whose own counters lapped on the machine they were written for (Part 6,
rule 3). Not one of them was visible in a screendump. Every one was found
either on real hardware or by *counting* rather than looking.

Two sentences carry the whole document:

> **QEMU is exact about how much work the guest does, and useless about how
> long that work takes.** So count work, never time it — and for the three
> defects it cannot show at all (Parts 1 and 3), the judgement is made on
> hardware.

---

## Part 1 — The vocabulary — say what you actually saw

The prose in this repo has historically called every visible drawing defect
"flicker". On a 4.77 MHz machine they are three different things with three
different causes and three different fixes, and calling them all flicker is
how one gets fixed and the other two get shipped. Use these names.

### Visible redraw — *not* a flicker

A window's whole content, or the whole screen, being painted again. On real
hardware **you watch it happen**: the fill sweeps, then the text lands, row
by row. It is not a flash you half-notice, it is a wait you sit through.
Heavy applications — Paint, the Task Manager, a Disk window full of files —
take **seconds** of it. A fractal frame is ~115 s and a full repaint used to
throw it away (REDRAW-SPEC.md).

If a change makes any operation call `wm_paint_all`, or makes a window
repaint its whole content where it used to repaint a band, that is this
defect. It will look instantaneous in a screendump and it is the single
most expensive mistake available in this codebase.

### Double-draw flash — the pixel written twice

Anything that draws a region and then draws over it: the classic is the
**erase-and-letter pair** — `gfx_fill` the rect white, then `font_char` the
glyphs into it. Between the two the region is *blank*, and on an XT that gap
is tens of milliseconds, several display frames. The area is smaller than a
full redraw, so it reads as a flash rather than a wait — **but it is still
very plainly visible**, on every keystroke, on every update.

It is invisible in QEMU at any frame rate a screendump can sample, and — the
part that matters — **no timing column reports it**, because the two methods
take comparable *time* and differ only in what is on screen during it. §6.1
is the fix (`font_run`, one store per cell, old content straight to final);
§27.2 and §11.94 are the two consumers converted for the flash rather than
for the 10.7%.

The same defect wearing other clothes: a background fill under an icon that
is then drawn; `wm_grow_paint` filling its 13×13 square before framing it,
which survived as a flashing corner after Note Pad's rows were fixed; a
pattern strip erased then re-lettered every scroll row (§45.11).

### Stall and input overrun

The machine stops answering. A held gfx lock across a long render freezes
the cursor (§20.6 rule 3 forbids it). A redraw slower than the key repeat
loses keystrokes to a full BIOS buffer. A pattern view that costs more than
the frame budget reads as a *hung* display rather than a slow one — which is
exactly why the tracker stops animating its grid on a tier-0 machine
(§45.9.1).

Whether a human can outpace the redraw is a property of the real machine's
speed against a real person's hands. It cannot be measured here at all.

---

## Part 2 — Calibration — estimate without a machine

These are measured, on a real 4.77 MHz 8088 with a Hercules card unless
stated. They are what lets you price a change in your head before writing it.

| quantity | value | source |
|---|---|---|
| **One 8×8 glyph cell** | **~1 ms** | §6.1.1; two independent harnesses agree (`fontbench` 10.09 ms/10 cells, `typebench` 33.3 ms/40) |
| **One `gfx_fill`, mono, a ~27px row** | **~1.16 ms** — 3.11 PIT counts ≈ 337 instructions | §48.8; per-call overhead, near enough independent of the bytes written |
| One `-icount shift=3` PIT count | **0.359 ms** of real XT ≈ 105 instructions | derived from `fontbench`'s Hercules row against its 10.09 ms on hardware — this is what turns an icount run into milliseconds |
| Implied 8088 cycles per instruction | **~16.4** | ibid |
| A 40-cell line redraw | ~33 ms | §11.94 |
| A 50-row × 90-cell content fill+letter | **~5 seconds** | §27.2 (`np_clean` exists to stop paying it) |
| Framebuffer read-modify-write | ~30 cycles, **whether or not it changes a pixel** | §39.5 / `kernel/font.inc` |
| `repe scasb` run scan | ~15 clocks/byte ≈ 7.5 clocks/pixel at 4bpp | `kernel/vga12.inc` |
| Naive per-pixel decode (shift by CL) | **75–90 clocks/pixel** | ibid — a 4-bit `shr` by CL alone is 24 |
| A 448×280 canvas repaint | ~0.25 s coalesced; **>2 s** decoded per pixel | ibid |
| Back-buffer flush vs. its RAM render | **~24×** | §32 |
| 4-plane flush vs. 1-plane (`bb_mono`) | ~3.7× | §32 |
| A segment override | 1 byte, 2 clocks | docs/KERNEL-MEMORY.md |
| Note Pad layout walk iteration | ~500 8086 cycles | §27.4 |
| ArtfulType `at_getb` | ~32 clocks/character | `apps/artful/atdoc.inc` |
| CPU budget | 4,772,727 cycles/s | docs/SOUND-PLAN.md |
| System tick | 18.2065 Hz (~55 ms) | §8 |
| Serial mouse | 1200 baud | §9 |

**8086-nominal cycle counts under-report an 8088 by 20–40%** — the 8-bit bus
and prefetch stalls — so a margin computed from an instruction-timing table
is a bound to validate, not a fact (docs/SOUND-PLAN.md).

Multiply and say that you did. "~500 cycles per iteration × 404 iterations
≈ 42 ms" is a reading of the instruction stream presented honestly; quoting
404 as if it were a duration is not.

---

## Part 3 — What QEMU cannot show at all

Not "shows inaccurately" — **cannot show**.

1. **Visible redraw.** A full window repaint is microseconds here and
   seconds there. Nothing in a screendump, a timing column or a QMP script
   distinguishes a window that repaints from one that does not.
2. **Double-draw flash.** Both methods take comparable time; they differ in
   what is on the glass during it. There is no column for that.
3. **Perceived latency and input overrun.** A property of the real machine
   against a real person.

And one that is worse than invisible, because it looks like a *success*:

4. **A lost optimisation that kept its shape.** `gfx_blit4`'s first version
   emitted one call per run exactly as designed, and decoded every pixel
   individually inside the scan instead of comparing byte pairs. Nine times
   slower on hardware. **Under QEMU it measured as exactly as fast**, because
   QEMU does not model 8086 timing — so every screendump was right, every
   test passed, and a 448×280 repaint went from a quarter of a second to over
   two. This is why the cycle counts in `kernel/vga12.inc` are *written down*
   rather than measured.

---

## Part 4 — What QEMU is exact about: work

The guest does the identical amount of work on both machines, and QEMU will
report it precisely. So when the question is "is this slow because it does
too much?", **instrument a counter and read it over QMP** — do not reach for
86Box, and do not guess.

```nasm
; kernel/font.inc, in .text so the offset is fixed
dbg_cells:  dw 0
...
font_run_cell:
    inc word [cs:dbg_cells]
```

```sh
nasm ... -l /tmp/k.lst   &&  grep dbg_cells /tmp/k.lst     # -> 0x1E78
python3 tools/qmp.py build/qmp.sock 'xp /2xh 0x2478'       # KERNEL_SEG*16 + off
```

`h` is a word; HMP's `w` is four bytes. **Editing any include before the one
holding the counter moves the offset**, so re-derive it after every rebuild.

A **package** can write the same counter — `mov ax, KERNEL_SEG / mov es, ax /
inc word [es:0x1E7E]` — which is how a walk inside an app is counted without
knowing the segment its region was claimed at.

This is what settled the Note Pad question (§27.4). A user reported typing
getting slower as a note grew and inferred that more than one character was
being redrawn. The cell counter said **2 cells per keystroke** at every note
length and every window width — the drawing was already right — and a counter
in the layout walk said 404 iterations, growing linearly. The cost was in a
place no screenshot could show and no wall clock here could measure.

### Instructions, when you want a number rather than a count

Both benchmarks time against counter 0 of the 8253 read directly (a 55 ms
tick cannot resolve a 3 ms row). Under QEMU that counts *host* speed and is
worthless, so run them with `-icount` and the PIT counts guest
**instructions** instead — deterministic, ±1 count across runs, and the same
on any host:

```sh
make bench
make test TESTAPPS=build/bench.img QEMU="qemu-system-i386 -icount shift=3,sleep=off"
```

Reproducible and machine-independent, but **not time**. And it *understates*
the mono win, because what alignment removes is disproportionately memory
traffic. `build/bench360.img` on a real 4.77 MHz 8088 (or 86Box) is where the
PIT is a wall clock and the microsecond column means microseconds.

**Instructions are the better proxy, not framebuffer traffic.** §6.1.1
originally predicted the opposite and was corrected by measurement: the XT
came in at the *instruction* figure to three digits (1.30×), not the 3.6×
traffic figure. Per-cell overhead dominates the byte-writes it guards.
Traffic remains the right *explanation* of where the writes went; it is not
the right predictor of time.

---

## Part 5 — The standing budget — what is already cheap, and must stay cheap

Nearly every expensive path in this system has already been made cheap once,
by somebody who measured it. **A change that reintroduces a full repaint is a
regression against a documented number, not a neutral refactor.** This is the
list to check yourself against.

| operation | was | is | contract |
|---|---|---|---|
| Show / raise a window | whole-screen repaint: dither, drive icons, dock, bar, every window's frame and `W_PAINT` | the bar, the dock, the outgoing title bar, this window | §11.90 |
| Raise an already-frontmost window | a screen | **no window at all** | §11.90 |
| Click a background window's title bar | two full screen redraws (raise + drag release) | two title bars | §11.90, `ui_drag` |
| Hide / destroy / drag a window | a screen | the damage rect, and only the windows in it | §11.91 |
| Retitle a window | full frame repaint | one `TITLE_H` strip | §11.92 |
| Mount / unmount a volume | `wm_paint_all` | the zone grid — measured **371 glyphs → 182** | §26.3 |
| Select a covered drive icon | **two** whole-screen repaints per click | one XOR strip, zero repaints; byte-identical output | §26.2 |
| Select a file row (Disk window) | ~130 glyphs + a dozen fills | two XOR bands; **zero** `font_char`, **zero** `gfx_fill` for most cases | §22.2 |
| Type into the file dialog's name box | ~120 glyphs + a 298×151 fill | `font_char` **972 → 36**, scanlines **7,600 → 184** (8 chars) | §38.8 |
| Note Pad keystroke | full content fill + a glyph per character | **2 cells**; `font_char` **8,410 → 350**, scanlines **5,020 → 1,960** (20 keystrokes, 410-char note) | §27.2 |
| Note Pad layout per keystroke | 404 walk iterations at 200 chars, growing | 35, and flat | §27.4 |
| Note Pad caret keys | Up 1,608 iterations / Home 1,608 / Left 804 | 184 / 90 / 60 | §27.5 |
| Note Pad walk below the view | 6 walks, 10,079 iterations (72% off-screen) | 2 walks, 1,015 | §27.7.1 |
| Note Pad scroll | letter 19 rows | one blit + 4 rows | §27.7.2 |
| Note Pad insert at the front | 1,600 cells ≈ most of a second | a scroll, settled later | §27.3 |
| An opaque text run | 228–336 framebuffer accesses, alignment-dependent | flat **80**; 1.30× on hardware, and no flash | §6.1, §6.1.1 |
| Task Manager row update | 20 glyphs to change 3, twice a second | the changed chunks only | §28.2 |
| Menu bar redraw | every window operation | gated on `[menu_bdirty]` | §12.05 |
| Dock redraw | every window operation | per-tile keys: a focus change is 2 tiles, a quiet desktop is 0 | §30.1 |
| Arkanoid pause / resume | the whole content — background, both rails, every brick, paddle, ball, capsules, shots, status strip | the banner's 9-row band: `gfx_fill` **89 → 2**, `font_char` **10 → 6** | §44.1 |
| Missile Command explosion (1bpp / 8088) | a full disc **every** frame for 27 frames plus 12 ring erases — ~750 fills a burst, 124 ms a frame in a busy wave | three drawn states, five-rect discs — 22 fills a burst, 7.9 ms | §48.8 |
| Solitaire stock click | 635 wasted fill runs **every click** | 0 unless the picture changed | §43.7 |
| Solitaire column redraw | every card, backs included (634 runs each) | buried backs kept; a measured move skips 246 runs | §43.7 |
| Fractal repaint | re-render from row 0 (~115 s) | replay the pass-0 cache, resume refining | §40.1 |
| Tracker row scroll | 30+ strips erase-then-text | 2 `gfx_scroll` + 3 strips | §45.12 |
| Tracker on a tier-0 machine | a per-position repaint it does not have | one banded line | §45.9.1 |
| Tracker mixing at 11 kHz | ~7.9M cycles/s against a 4.77M budget | ~2.1M at 5,500 Hz, bounds check out of the inner loop | §45.9 |
| Paint brush stroke | width² per pixel of travel | the dab's leading edge, one `gfx_fill` per step | docs/PAINT-NOTES.md |
| Paint undo | whole canvas | row-granular and lazy | ibid |
| Menu save-under | 20KB claimed permanently, then 20KB per menu | sized from the rect actually dropped (~4KB VGA, ~1KB Hercules) | docs/KERNEL-MEMORY.md |
| Covered background window | skipped the frame entirely | draws its visible region | §11.3 |
| Copy a file | 5 volume switches per file | 2, one `dsk_read_chain` per chunk | §22.5 |
| FAT access across a copy | re-read on every switch | a window per volume: 45 mounts → 3 loads | §18.8.1 |

Two entries in that table are load-bearing beyond their own numbers.
**`OSAPI_WM_GROW` was called on every Note Pad keystroke** — free in the
emulator, a visible flashing corner at 33 ms a keystroke on hardware. And
**the covered-icon click cost two whole-screen repaints**, found by putting a
counter on `wm_paint_all` and watching a single click take it from 4 to 6.
Both are the same lesson: the emulator will not tell you.

---

## Part 6 — The rules that fall out

**1. Nothing repaints more of the screen than it changed.** This is the whole
architecture, not an optimisation: §11.3's clip region, §11.90/§11.91's
damage rects, §11.92's title strip, §27.2's row signatures, §28.2's chunks,
§38.8's bodies-and-wrappers, §43.7's per-pile redraw. If your change makes
something repaint a superset of what it altered, you have spent a second of
somebody's afternoon.

**2. Nothing writes a pixel twice.** The erase-and-letter pair is the
canonical violation and `font_run` (§6.1) is the answer — one decision per
cell, on both its paths, so it cannot even produce §11.3's granularity
failure. Where a run is not available, ask whether the erase is needed at all
(`sol_covers`, `np_clean`), and if it is, whether it can be the *inside* of
the changed branch rather than in front of it (§28.2 — "what is not redrawn
must not be blanked either").

**3. Size every range from the slowest machine it will ever run on.** A
constant sized while looking at QEMU encodes the wrong range, and the
failures are structural rather than proportional:

| sized against QEMU | what a real XT did |
|---|---|
| a 16-bit elapsed counter, one subtraction start-to-end | rows are 1.5M counts; it lapped silently into a small plausible number |
| `>= 32768 means the run overran` | most legitimate rows are 32768..65535; it discarded them |
| a ratio computed from `counts >> 4` | `>> 4` is still 90,000; it overflowed the word and printed 696 for 134 |
| `OSAPI_WM_GROW` on every keystroke | free in the emulator; a flashing 13×13 corner at 33 ms a keystroke |

A 32-bit accumulator folded per iteration costs a few instructions and cannot
lap; a 16-bit one sized "generously" against QEMU is wrong by 20×.

**4. Measure before redesigning.** The obvious hypothesis is wrong often
enough to matter — Note Pad's drawing was already correct when a user reported
it slow, and the fix that hypothesis would have produced was a fix to working
code. Put a counter in. It costs one rebuild.

**5. A counter is not a timer.** It says how many times something ran, not
what it cost. Multiply by Part 2 and say that you did.

**6. Keeping the shape of an optimisation is not keeping the optimisation.**
`gfx_blit4` is the standing example: one call per run, exactly as designed,
and 75–90 clocks a pixel inside it. Nine times slower, and QEMU said it was
identical. When you rewrite something whose *reason* is speed, verify the
reason survived, not the structure.

**7. Prefer a self-checking harness to a careful one.** Three of the four in
that table were caught by **one number on screen contradicting another**, not
by inspection — `typebench`'s CHAR row does 1.33× `fontbench`'s
PAIR work, so it cannot be the smaller number, and it was. Put redundant
quantities on the screen: a raw count *and* a derived time, two rows whose
relative sizes are known in advance, a ratio you can recompute by hand from
the columns beside it. A harness that reports one number per run is one you
have to trust.

**8. Treat every number as provisional, and cite where it came from.** A
benchmark figure without a date and a machine is worth very little. The
figures in §6.1.1 have been corrected by real hardware three times — twice
because a harness was wrong, and once because the *prediction* was (traffic,
not instructions).

**9. Refusal is a normal path.** Where the floor cannot deliver, say so at
call time and in prose — the `bb_avail` idiom, three layers deep: the probe
flag gates the setter *and* the caption *and* the click (§47). Do not ship
a feature that silently costs seconds on the target; ship one that greys
itself with the reason (§47 rule 3: grey a **fact**, never a guess).

**10. Degrade by tier, and know which tier you are on.** `OSAPI_CPU_INFO`
answers `CPU_8086` for the target machine, and two apps key real behaviour
off it: the tracker pre-arms XT mode and stops animating its pattern grid
(§45.9/§45.9.1), and Note Pad enables the visual break (§27.3). That is a
**fact the code can test**, unlike a guess about speed — and it is the
honest way to spend an optimisation that only the slow machine needs.
Everything else that is sized for the floor — Missile Command's fifteen
in-flight missiles, the tracker's 3-row VU bars — is simply sized for the
floor on every machine.

---

## Part 7 — Checking a change

In rough order of cost, and you do not always need all of it.

1. **Count the work.** Put a counter at the drawing primitive your change
   touches (`font_char`, `font_run_cell`, `gfx_fill`, `wm_paint_all`) and read
   it over QMP before and after. If the count went up, stop here.
2. **Look at it on a 1bpp adapter.** `make test VIDEO=cga` and
   `make test VIDEO=herc HERCSEG=0x7000` — the two adapters a 4.77 MHz machine
   actually has, where `[bb_on]` is permanently 1 and the software renderer
   *is* the direct path. A change that is free on VGA can be the whole cost on
   mono, and vice versa. docs/HERCULES-TESTING.md, because Hercules is not
   screendumpable and the failure is silent.
3. **Price it.** Multiply the counts by Part 2's calibration and write the
   milliseconds down in the commit message.
4. **Instruction-count it** if the change is inside a primitive:
   `-icount shift=3,sleep=off` and the two benchmarks (Part 4).
5. **Run it on period hardware** if the change is about *time* rather than
   *work* — `make xt` (4.77 MHz 8088), `make 286`, `make 386sx`, `make 386`
   for the middle of the range. 86Box is not installed in the web container;
   those targets do not run there, and that is a real limit on what a web
   session can conclude.
6. **Watch it with your eyes** if the change is about flash or redraw. That
   judgement is made on hardware and by a person. Nothing above substitutes.

**Under QEMU, wall clock is still a lower bound worth having.** Paint's
measured figures under `make run-640` — a full-canvas flood fill in ~4 s, a
448×280 4bpp BMP open in ~8 s, a 448×280 GIF at ~125,000 dictionary walks —
are useful precisely because they are already slow *here*. A real 8 MHz
machine is several times slower and a 4.77 MHz 8088 slower again. If it is
seconds in the emulator, it is out of reach on the target: that is how JPEG
was ruled out (tens of seconds per 448×280 frame before the dither).

---

## Part 8 — Where the numbers live

| what | where |
|---|---|
| The testing matrix, and modelling the old machine from a fast one | [docs/TESTING.md](docs/TESTING.md) |
| `font_run`, and the primitive priced four ways | SPEC.md §6.1 – §6.1.4 |
| `gfx_blit4` / `gfx_scroll`, and the cycle counts written down | SPEC.md §5.4, §5.5; `kernel/vga12.inc` |
| The clip region, and the granularity rule | SPEC.md §11.3 |
| Show / hide / drag / retitle costs | SPEC.md §11.90 – §11.92 |
| `WF_SNAP`, and the keystroke priced | SPEC.md §11.94 |
| Note Pad's redraw optimisations, seven of them | SPEC.md §27.2 – §27.7.2 |
| The Task Manager's chunks | SPEC.md §28.2 |
| Double buffering, and the flush's 24× | SPEC.md §32 |
| The mono renderer's inner loop | SPEC.md §39.3, §39.5 |
| The fractal's restore cache | SPEC.md §40.1; [REDRAW-SPEC.md](REDRAW-SPEC.md) |
| Solitaire's incremental repaint | SPEC.md §43.7 |
| Arkanoid's pause band, and what an erase in the play area owes | SPEC.md §44.1 |
| The tracker on an 8088 | SPEC.md §45.9 – §45.12 |
| ArtfulType's performance contract | SPEC.md §46.1 |
| Greying a control honestly | SPEC.md §47 |
| Paint's design notes and what it cost | [docs/PAINT-NOTES.md](docs/PAINT-NOTES.md) |
| Per-device cycle budgets on the floor machine | [docs/SOUND-PLAN.md](docs/SOUND-PLAN.md) |
| Memory, and why there is no growth room | [docs/KERNEL-MEMORY.md](docs/KERNEL-MEMORY.md) |
| The benchmarks themselves | `tests/fontbench/`, `tests/typebench/` (`make bench`) |
