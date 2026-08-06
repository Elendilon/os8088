# PERFORMANCE.md — the machine this is for, and why your emulator lies about it

**Read this before you change anything that draws, lays out, or loops.** It
is required reading alongside [SPEC.md](SPEC.md) (what the kernel *is*),
[CLAUDE.md](CLAUDE.md) (how to work on it) and
[docs/TESTING.md](docs/TESTING.md) (where a test can run at all). This one
is about the target machine, which is not the one you are looking at.

**A bare `§` here means SPEC.md**, as it does everywhere else in this repo.
This document's own divisions are called **Part 1**..**Part 9**, so the two
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

**Everything in the first table was measured on an IBM 5150 — 8088 at 4.77
MHz, 640KB — with a Hercules card and again with a CGA, by `gfxbench` and
`sysbench` (Part 9).** Where the two adapters differ, both are given. Nothing
here is an estimate; the estimates are in the second table, and they are
labelled.

### The three numbers that price almost everything

| | Hercules | CGA |
|---|---|---|
| **Any `gfx_*` drawing call — the fixed part** | **756 us** | 756 us |
| **One 8×8 glyph cell** | **901 us** | 909 us |
| **One 78-cell row of text** | **71.4 ms** | 72.7 ms |

The first is the one to internalise, because it is the one nothing in this
project believed. `GFX_PIXEL` and `GFX_HLINE 8px` measured **765.64 and
764.82 us on Hercules and 765.70 and 764.80 on CGA** — two different
routines, two physically different cards whose framebuffers are 13% apart,
agreeing to one part in ten thousand. Almost the whole cost of a small
drawing call is fixed setup, about **3,600 CPU clocks**, and it is CPU-side:
the card barely shows through.

> **A redraw is priced by how many primitive calls it makes, not by how many
> pixels it covers.** Everything below is a consequence of that sentence.

**That floor has since been taken apart and cut by about a fifth, and this
table has NOT been re-measured** (rule 8: a figure carries its machine and
its build). Part 9 Set 3 is the teardown — one `gfx_pixel` is 196 guest
instructions across eleven routines, a third of them push/pops and near
call/rets — and the work it prompted is SPEC.md §5.7. Under `-icount` the
pixel path came down 19.6% and every `gfx_*` row with it. Until somebody
runs `gfxbench` on the 5150 again, **estimate with the 756 us above**: it is
the number that was measured, the improvement is measured in a different
unit, and an inferred figure must not quietly replace a field one.

### Measured — drawing

| quantity | Hercules | CGA |
|---|---|---|
| `gfx_fill`, per scan line | 177 us | 182 us |
| `gfx_fill`, per pixel | 0.28 us | 0.33 us |
| `gfx_hline`, per pixel past the fixed cost | 1.16 us | 1.20 us |
| `GFX_FILL 64x64` | 12.4 ms | 13.0 ms |
| `GFX_FILL 256x128` | 31.7 ms | 33.9 ms |
| `font_run`, per cell of a ten-cell run | 905 us | 918 us |
| `font_run` aligned vs. the skewed hand-written pair | 1.24× | 1.24× |
| `WM_TITLE` strip (§11.92) | 43.2 ms | 44.4 ms |
| A full text page (78 cells × 34 / 16 rows) | **2.50 s** | 1.24 s |
| One vertical retrace period | ~20 ms (50 Hz) | ~16.6 ms (60 Hz) |

A fill spends **91% of a 64-pixel-wide row on arriving**: 177 us of setup
against 18 us of pixels. The per-pixel half is already at the bus (0.28 us/px
is 2.2 us per framebuffer byte against the 3.26 a raw `rep stosb` costs), so
there is nothing in the inner loop and most of an order of magnitude in the
row setup.

### Measured — the machine

| quantity | value |
|---|---|
| CPU, from `MUL` and `DIV` independently | **4.64 and 4.68 MHz** (nominal 4.7727) |
| **8088 instruction floor** | **4.34 clocks per instruction BYTE** — see below |
| A segment override | +3.78 clocks (one extra instruction byte), *not* the book's 2 |
| API far-call cell (`OSAPI_*`) | 46.7 us |
| Near `call` + `ret` | 11.0–11.5 us |
| `OSAPI_TASK_YIELD` (a full switch) | 693 us |
| RAM `rep stosw` | 1.76 us/byte |
| RAM byte read-modify-write (a 5-instruction loop) | 15.3 us/byte = 72.8 clocks |
| **Framebuffer byte read-modify-write** | **16.7 us/byte = 79.6 clocks** (CGA 81.0) |
| Framebuffer vs. RAM, word write | 1.57× (CGA 1.78×) |
| Framebuffer vs. RAM, read-modify-write | 1.09× (CGA 1.11×) |
| An ISA status-port `in` | 8.7 us |
| The kernel's own tick + mouse + scheduler | **1–3%** of a busy CPU |
| Floppy throughput | **2,100 bytes/second** |
| Floppy, per 512-byte sector | 238 ms — one sector per 200 ms revolution |
| Floppy, open and read a one-sector file | 800 ms |
| System tick | 18.2065 Hz; **65,536 PIT counts, measured exactly** |
| Serial mouse | 1200 baud |

**The framebuffer read-modify-write was quoted at "~30 cycles" here and in
§39.5 for years. It is 79.6, and only about 7 of those are the bus** — the
rest is five 8088 instructions. The figure was low, and it was attributed to
the wrong thing.

### The 8088 instruction floor — what replaced "add 20–40%"

This document used to end Part 2 with "8086-nominal cycle counts under-report
an 8088 by 20–40%", from a plan document. The measured ratio runs from **1.01
to 4.34**, and reading it against instruction *bytes* explains all of it:

| instruction | bytes | measured clk | 8086 book | ratio |
|---|---|---|---|---|
| `nop` / `inc r16` / `xchg ax,r16` | 1 | **4.34** | 3 / 2 / 3 | 1.44 / 2.17 / 1.44 |
| `mov r16,r16` / `add` / `cmp` / `shl r16,1` | 2 | **8.69** | 2 / 3 / 3 / 2 | up to **4.34** |
| `jmp short`, taken | 2 | 18.19 | 15 | 1.21 |
| `mov ax,[disp16]` | 3 | 21.61 | 14 | 1.54 |
| `call near` + `ret` | 4 | 52.13 | 27 | 1.93 |
| `mul r16` (with its reload) | 5 | 132.53 | 129 | **1.02** |
| `div r16` (with its reloads) | 7 | 162.85 | 160 | **1.01** |

> **An 8088 costs `max(execution clocks, 4.34 × instruction bytes)`**, plus
> about 4 clocks per byte of memory operand, plus a queue refill after every
> taken branch.

It is a floor, not a tax. `MUL` and `DIV` measure at 1.01–1.02 because the
sequencer stays busy long enough to hide every fetch; a run of
register-to-register moves measures at 4.34× because nothing hides anything.
**A shorter encoding beats a cheaper instruction** — `xchg ax,bx` (one byte)
is twice as fast as `mov ax,bx` (two) although the book prices them at 3 and
2. So the question is never "what percentage do I add"; it is whether the
code is fetch-bound or execution-bound.

### Still written down rather than measured — treat as estimates

These are readings of the instruction stream that no field set has confirmed.
The floor above says most of them are **optimistic**, because a written-down
count is an 8086 count.

| quantity | value | source |
|---|---|---|
| `repe scasb` run scan | ~15 clocks/byte | `kernel/vga12.inc` |
| Naive per-pixel decode (shift by CL) | 75–90 clocks/pixel | ibid — the pre-coalescer `gfx_blit4`, Part 3 |
| Back-buffer flush vs. its RAM render | ~24× | §32 — **VGA only**, and the field machine has none |
| 4-plane flush vs. 1-plane (`bb_mono`) | ~3.7× | ibid |
| Note Pad layout walk iteration | ~500 8086 cycles | §27.4 |
| ArtfulType `at_getb` | ~32 clocks/character | `apps/artful/atdoc.inc` — 9 bytes of instruction, so ≥39 by the floor |

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

4. **A lost optimisation that kept its shape.** It has happened twice.
   §48.10 is the second: `mc_blob` replaced 39 one-row fills with 6 nested
   rects, which is 6.5× fewer *calls* and 4.7× more *scan lines*, because
   nested rects overlap — 37.1 ms against the 36.4 it replaced. It measured
   as a win in every counter anyone had, and only a field log from the target
   machine said otherwise. And `gfx_blit4`'s first version
   emitted one call per run exactly as designed, and decoded every pixel
   individually inside the scan instead of comparing byte pairs. **Under QEMU
   it measured as exactly as fast**, because QEMU does not model 8086 timing —
   so every screendump was right and every test passed. This is why the cycle
   counts in `kernel/vga12.inc` are *written down* rather than measured.

   The three figures this entry used to carry — "nine times slower on
   hardware", "a quarter of a second", "over two" — were all derived from
   those same written-down counts and none was ever measured. They are gone
   rather than corrected, because the field set prices the primitive a
   different way entirely and it should be the one quoted.

   What the field set adds, and what a caller of the fixed primitive needs:
   **`gfx_blit4` emits one `gfx_hline` per coalesced run, and a `gfx_hline`
   costs ~0.5 ms whatever its length.** Measured, 64×64 pixels either way:
   one run per row (64 calls) is **28 ms**; sixteen runs per row (1,024
   calls) is **561 ms**. Twenty times, for the same pixels. So the cost of a
   blit is `runs × 0.5 ms`, the pixel count barely enters it, and *how flat
   the picture is* is the whole performance story.

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

#### Turning an icount run into milliseconds

An icount PIT count is instructions, and one conversion factor makes it a
duration. It was derived by pinning `fontbench`'s Hercules row against the
10.09 ms that same row costs on hardware:

| | |
|---|---|
| one `-icount shift=3` PIT count | **0.359 ms** of real XT ≈ 105 guest instructions |
| implied 8088 clocks per instruction | **~16.4** |

**The field set cross-checks both and they hold.** 16.4 clocks for an average
instruction is what the instruction floor predicts once memory operands and
taken branches are added to `max(exec, 4.34 × bytes)` — a 2–3 byte
instruction is 8.7–13 clocks of fetch floor before either. And the figure
`§48.8` derived through this route, **~1.16 ms for one mono `gfx_fill` of a
~27px row** (3.11 PIT counts ≈ 337 instructions), lands inside the measured
model: 756 µs fixed + 177 µs for the row + 27 × 0.28 µs of pixels ≈ 0.94 ms,
and the measured `GFX_FILL 8x8` is 1.13 ms. So the conversion is sound within
about 25%, which is the right precision to quote it at.

Use it for a row a field set does not cover. Where Part 2 has the quantity
measured, prefer Part 2 — a derivation through two anchors cannot beat a
direct reading.

### The two harnesses that produce a document rather than a screen

`fontbench` and `typebench` each answer one question and fit on a screen.
`gfxbench` and `sysbench` answer forty each, so they page — and they **save
the whole report to a text file** on the current volume (`S`, or the Bench
menu). That file is the point: it is meant to be carried off the machine and
pasted into Part 9 below.

- **`gfxbench`** prices every `gfx_*` and `font_*` slot on whichever adapter
  it booted on, most of them at **two sizes** so the per-call term and the
  per-pixel term come apart, plus the raw RAM and framebuffer bandwidth
  underneath them. One package for Hercules AND CGA deliberately: both are
  the same 1bpp software renderer over four different numbers (§39.3), which
  it reads from `OSAPI_VIDEO` at run time, so the two columns are the same
  measurement rather than two sources that can drift. `GFXHERC.TXT` /
  `GFXCGA.TXT` / `GFXVGA.TXT`.
- **`sysbench`** prices the machine underneath: **8086-nominal clocks against
  a real 8088 per instruction class** (the number the last line of Part 2 has
  been quoting from memory), RAM bandwidth, the clock ladder, the API's
  far-call floor, what the kernel's own interrupts cost per second of
  ordinary work, and the floppy. `SYSBENCH.TXT`.

Both are timed the same way, and it is a deliberate departure from
`fontbench`: the `cli` window is **one iteration, not one row**, so the tick,
the mouse and any sound refill are serviced *between* iterations and land in
no measurement at all — where `fontbench`'s whole-row `cli` let one unlucky
row absorb another task's slice and move by more than the effect. Rows too
long for a 55 ms PIT wrap fall back to tick timing and are flagged `t`; a row
whose worst iteration came within a third of the wrap is flagged `!`.

Read the caution block at the top of either report before quoting anything
from a QEMU run. Two rows there are worse than noise on an emulator and say
so themselves: the retrace period (QEMU's status port toggles on every read,
so a poll always terminates) and the VRAM rows under a `HERCSEG=` kernel
(B0000 is unmapped, so they measure plain RAM and the bus ratio reads 100).

**Instructions are the better proxy, not framebuffer traffic**, and Part 9
settles it beyond argument. §6.1.1 originally predicted the opposite and was
corrected once by measurement: the XT came in at the *instruction* figure
(1.30×, independently 1.24× on the second harness), not the 3.6× traffic
figure. The field set then proved the general case — the same two primitives
measured **0.01% apart on a Hercules and a CGA whose framebuffers are 13%
apart at the bus**. Per-call and per-row setup dominate the byte-writes they
guard, on every adapter. Traffic remains the right *explanation* of where the
writes went; it is not the right predictor of time.

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
| An opaque text run | 228–336 framebuffer accesses, alignment-dependent | flat **80**; 1.30× on hardware (`fontbench`), 1.24× on a second harness and a second adapter (Part 9), and no flash | §6.1, §6.1.1 |
| Task Manager row update | 20 glyphs to change 3, twice a second | the changed chunks only | §28.2 |
| Menu bar redraw | every window operation | gated on `[menu_bdirty]` | §12.05 |
| Dock redraw | every window operation | per-tile keys: a focus change is 2 tiles, a quiet desktop is 0 | §30.1 |
| Arkanoid pause / resume | the whole content — background, both rails, every brick, paddle, ball, capsules, shots, status strip | the banner's 9-row band: `gfx_fill` **89 → 2**, `font_char` **10 → 6** | §44.1 |
| Missile Command explosion (1bpp / 8088) | a full disc **every** frame for 27 frames plus 12 ring erases — ~750 fills a burst, 124 ms a frame in a busy wave | three drawn states, five-rect discs — 22 fills a burst, 7.9 ms | §48.8 |
| Missile Command terrain repair | `[mc_gdirty]`, one byte: the whole ground band, six cities and three bases — **143 ms**, five times in 86 frames | a damage **span**: 16.5 ms, byte-identical to a full repaint | §48.9 |
| Missile Command score strip | the whole strip blanked and re-lettered on every kill | three `font_run` fields, space-padded — no blank interval | §48.9, §6.1 |
| Missile Command missile trails | an app-side Bresenham emitting one `gfx_hline` per **row** — a whole-trail erase was 267 fills, ~310 ms, a five-tick stall | one `gfx_line`: 59 ms worst frame, and the busy frame whole went 190 ms → **43.5 ms** | §5.6, §48.8.3 |
| Solitaire stock click | 635 wasted fill runs **every click** | 0 unless the picture changed | §43.7 |
| Solitaire column redraw | every card, backs included (634 runs each) | buried backs kept; a measured move skips 246 runs | §43.7 |
| Fractal repaint | re-render from row 0 (~115 s) | replay the pass-0 cache, resume refining | §40.1 |
| Tracker row scroll | 30+ strips erase-then-text | 2 `gfx_scroll` + 3 strips | §45.12 |
| Tracker on a tier-0 machine | a per-position repaint it does not have | one banded line | §45.9.1 |
| Tracker's XT fullscreen | the scrolling grid in pixels: **2,567 glyph cells/s**, ~2.6 s of drawing per second of music | an 80x25 text mode: **0** glyph cells, **0** `gfx_fill` — 1,121 `rep movsw` words a row change, ~4% of the machine, and the grid scrolls again | §45.13 |
| Tracker mixing at 11 kHz | ~7.9M cycles/s against a 4.77M budget | ~2.1M at 5,500 Hz, bounds check out of the inner loop | §45.9 |
| Tracker's text shadow rebuild | all 64 rows in one frame — 256 `mp_cell2txt` + 3,776 `lodsb`/`stosw` + a 9,676-byte blank ≈ **140–330 ms, once every ~9 s**, reported from the field as the screen stopping and then jumping | `TTX_SHCHUNK` = 4 rows a frame, cursor starting at the visible window and wrapping: worst frame **~25 ms** | §45.13.2 |
| Paint brush stroke | width² per pixel of travel | the dab's leading edge, one `gfx_fill` per step | docs/PAINT-NOTES.md |
| Paint undo | whole canvas | row-granular and lazy | ibid |
| Menu save-under | 20KB claimed permanently, then 20KB per menu | sized from the rect actually dropped (~4KB VGA, ~1KB Hercules) | docs/KERNEL-MEMORY.md |
| Covered background window | skipped the frame entirely | draws its visible region | §11.3 |
| Copy a file | 5 volume switches per file | 2, one `dsk_read_chain` per chunk | §22.5 |
| FAT access across a copy | re-read on every switch | a window per volume: 45 mounts → 3 loads | §18.8.1 |
| The per-call floor itself (1bpp) | one `gfx_pixel` = **196** guest instructions of generic rect machinery | **158**; `GFX_FILL 8x8` −19.3%, `64x64` −14.5%, `GFX_BLIT4` −13.8%, output byte-identical on all three adapters | §5.7, Part 9 Set 3 |
| A renderer row step | `call gfx_nextrow`: a near call plus two CS-overridden memory reads, **three times per scan line** | three register instructions, parameters hoisted out of the loop | §39.3, §32 |

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
| a per-iteration fold, guarded only *near* the wrap | a 561 ms body reported 561 mod 54.92 = 12 ms, unflagged, and made a primitive doing 20× the work look 2.4× faster (Part 9) |
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
reason survived, not the structure. (The fixed primitive's own cost model is
in Part 3 item 4: **runs × 0.5 ms**, pixels almost free.)

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
   **`font_char` and `font_run_cell` are one number and must both be
   counted**, and on a mono adapter that is not a nicety: §6.1's fast path
   letters a cell without going near `font_char`, so a counter on
   `font_char` alone read **58 cells/s** for a Tracker pattern grid that was
   drawing **2,567** (§45.13.1). A plausible small number is the failure mode
   here, exactly as in rule 3 below — and for the same reason, **sample a
   16-bit counter often enough that it cannot lap between reads** (a second
   is ample; thirty is not) and accumulate the deltas mod 65,536.
2. **Look at it on a 1bpp adapter.** `make test VIDEO=cga` and
   `make test VIDEO=herc HERCSEG=0x7000` — the two adapters a 4.77 MHz machine
   actually has, where `[bb_on]` is permanently 1 and the software renderer
   *is* the direct path. A change that is free on VGA can be the whole cost on
   mono, and vice versa. docs/HERCULES-TESTING.md, because Hercules is not
   screendumpable and the failure is silent.
3. **Price it.** Multiply the counts by Part 2's calibration and write the
   milliseconds down in the commit message.
4. **Instruction-count it** if the change is inside a primitive:
   `-icount shift=3,sleep=off` and the benchmarks (Part 4). If the change is
   to a `gfx_*` or `font_*` slot, `gfxbench` already has a row for it and a
   before/after pair of its report is a diff.
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
| The real machines, whose they are, and how to take a set on one | [docs/FIELD-MACHINES.md](docs/FIELD-MACHINES.md) |
| `font_run`, and the primitive priced four ways | SPEC.md §6.1 – §6.1.4 |
| The per-call floor, taken apart, and the seven rules holding it down | SPEC.md §5.7 |
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
| The benchmarks themselves | `tests/fontbench/`, `tests/typebench/`, `tests/gfxbench/`, `tests/sysbench/` (`make bench`) |
| The field measurements they produced | Part 9, below |

---

## Part 9 — The field reports

Part 2's calibration table has fifteen rows and **two of them were ever
measured on the target**; the rest are estimates from those two, or figures
carried over from a plan document. Part 9 is where that stops being true. It
holds the reports `gfxbench` and `sysbench` write, taken on real hardware,
verbatim enough that a later reader can tell a measurement from an inference.

### How to take a set

```sh
make bench                      # build/bench360.img is the 5.25" one
# write build/bench360.img to a floppy, and DO NOT write-protect it -
# the reports are saved back to that disk
# boot os8088-360.img, open Disk B, launch GFXBENCH.O88
#   R runs it (about ten seconds on a 4.77MHz machine)
#   S saves GFXHERC.TXT / GFXCGA.TXT / GFXVGA.TXT
# then SYSBENCH.O88, likewise, to SYSBENCH.TXT
```

A machine with two adapters gets two `gfxbench` sets. The probe picks one
(§39.1), so the other needs a kernel built with `VIDEO=` forcing it:

```sh
make BUILD=build/cga VIDEO=cga all      # ...into its OWN build directory,
                                        # or build/ ships a forced kernel
```

Do that in a separate `BUILD=` directory and nowhere else. A `VIDEO=`-forced
kernel that reaches `build/` is a machine that boots the wrong adapter for
everyone, which `make check-images` now reports as STALE precisely because it
has happened.

### What the next set is being asked

Set 3 spent a model rather than a measurement in three places, and three rows
were added to the harnesses so the next field set settles them. Each has an
expected answer, which is the point — a row you cannot be surprised by is not
worth taking:

| row | what it settles | it should say |
|---|---|---|
| `sysbench: shl r16,cl (4)` and `(13)`, and the derived `shl clk/bit x100` | **the variable-shift model.** "8 clocks plus 4 per bit" is the 8086 book, and §5.7 traded two edge-mask shifts and `gfx_rowbase`'s `shl bx,13` for table lookups on the strength of it. One row can only report a total; the SLOPE needs two | the derived line near **400** (4.00 clocks a bit). Well under it and the tables bought less than claimed; well over and they bought more |
| `sysbench: mov al,[bx+disp16]` | **what a table lookup costs** — the other side of that trade, and the addressing mode all four kernel tables use (`gfx_inktab`, the two mask tables, `vid_banktab`). Nothing measured it before | ~17 clocks by the book, so **~74 us per 1,000**; it must come in well under `shl r16,cl (13)` or the trade is a wash |
| `sysbench: mov ax,i + mul [m]` | **the `mul` §5.7 did NOT remove** from `gfx_rowbase`, on the argument that the alternative is a per-row table `KERN_BUDGET` cannot fund. Only the register form was measured | close to `mul r16` plus an EA. If it is much worse, the table is worth costing again |
| `gfxbench: GFX_FILL 256x1`, and the derived `fill ns per row` | **the per-ROW term, cleanly.** Set 1 fitted `c + a*rows + b*px` to three sizes, got a NEGATIVE per-call term and over-predicted the 8x8 by 1.27x, and said so. 256x1 against 256x128 differs by 127 rows and by nothing else | `fill ns per row` near **177,000** on Hercules / 182,000 on CGA. Where it disagrees with the two-point fit, **this one is the measurement and that one is the model** |
| `gfxbench: FULLSCREEN in+out` | **the whole-screen repaint.** Part 1 calls it a "visible redraw", Part 5's entire budget table is organised around avoiding it, and no field set has ever put a number on it — because a package cannot reach one. `wm_fullscreen`'s exit is a `wm_paint_all`, and it is the ONE composition call legal from a window callback (below) | **seconds**, and it is method T for that reason. What is in it: the desktop dither, the drive zones, the dock, the menu bar and every visible window — one of which is this report, priced separately by `whole page of rows` |
| `gfxbench: GFX_FILL 64x64 clipped` | **what §11.3's clip region costs a covered background window.** `WM_CLIP_SET+CLEAR` was measured; drawing *under* one never was. It sits next to its own unclipped row, so the gap is the answer | a little over the unclipped row plus the `SET+CLEAR` cell. Much more and `gfx_clip_run`'s re-entry is dearer than the region arithmetic it saves |
| `gfxbench:` the whole **fullscreen block** | **whether a primitive costs what it costs wherever it is drawn.** Same code, same sandbox, different place on the glass, no chrome around it. The rows carry the same labels as their windowed twins so they diff by name | the primitives to be **boring** — landing on their twins. One that does not has found something position-dependent nobody believed was |

None of them says anything on an emulator, and two say so loudly: under
`-icount` both shift rows measure identically and the derived per-bit line
reads **0**, which is correct and is the caution block in miniature.

**Reading the fullscreen pairs has one trap, and it is a VGA one.**
`[bb_mono]` (§32) is one-way, and `bb_mono_chk` is five instructions cheaper
once it has retired — so if anything drawn between the two passes used a
colour that is not 0 or 15, every fullscreen row comes in slightly under its
twin for a reason that has nothing to do with fullscreen. It shows as a flat
few instructions per drawing call rather than a proportional gap, and it is
visible in the QEMU sighting run: the VGA `GFX_PIXEL` pair read 408 against
389 while the **CGA pair read 456 against 456**. On the two 1bpp adapters
`bb_init` retires the flag at boot (§39.5), so the columns that matter for
the target machine are a clean A/B.

**And the drag is not there, which is an API fact rather than an omission.**
A benchmark runs inside a window callback, which holds the gfx lock, and
every call that moves or resizes a window forbids it — `OSAPI_WM_RESIZE` says
"Do NOT hold the gfx lock" in as many words, and `WM_SHOW`/`WM_HIDE`/
`WM_FRONT` take it themselves, so from a callback they are a deadlock rather
than a measurement. `wm_fullscreen` and `wm_title_set` are the two exceptions,
and `FULLSCREEN in+out` is what a drag's repaint looks like through them: the
frame changes size and position, and the screen is put back. Timing a real
`ui_drag` would mean a **worker task** doing the composition unlocked while
the UI task formats the results — possible under §20.6, and the reason it was
not done here is that a harness bug is worse than a missing row (rule 8).

### What to record with the numbers

**Every figure here is provisional and carries its machine** (Part 6 rule 8).
A report without the four lines below is worth very little — and *which*
machine, who holds it, and how a build gets onto its floppies are in
[docs/FIELD-MACHINES.md](docs/FIELD-MACHINES.md), because an agent is told
which account it is running as and forgets it, while a fork's name is in the
repo forever:

| | |
|---|---|
| machine | make, CPU, clock, RAM |
| adapter | which card, and whether the kernel probed it or was forced |
| build | the commit the images were built from |
| date | when it was run |

### Set 1 — IBM 5150, 4.77 MHz 8088, 640KB, Hercules

| | |
|---|---|
| machine | IBM PC 5150, 8088 at 4.77 MHz, 640KB, two floppies, no sound card |
| adapter | Hercules (720x348), auto-detected. The machine also holds a CGA |
| build | `62c4172` (`gfxbench`/`sysbench` in `tests/`) |
| reports | `GFXHERC.TXT`, `SYSBENCH.TXT` |

**Take the harness's own agreement first, because everything below rests on
it.** The two suites share no measurement code path beyond `benchlib`, and
their four common quantities land on top of each other:

| cross-check | gfxbench | sysbench | apart |
|---|---|---|---|
| RAM `rep stosw`, 2048 B | 34,313 counts | 34,317 | 0.012% |
| RAM read-modify-write | 149,090 | 149,084 | 0.004% |
| loop overhead, 400 iters | 29,701 | 29,699 | 0.007% |

And the timebase checks itself twice. `PIT counts per tick` measured **65,542
against the 65,536 the whole conversion assumes** — 0.009% — so method P and
method T really are the same unit. The CPU-speed estimate, derived
independently from the `MUL` row and the `DIV` row, came back **4.64 and 4.68
MHz** against a nominal 4.7727; the 2% shortfall is the book figure for those
two being a range (118–133 clocks for `MUL`), not a slow machine.

#### The 8088's real instruction cost is a straight line, and it is not a percentage

Part 2 has been ending on "8086-nominal cycle counts under-report an 8088 by
20–40%", from a plan document. That is not the shape of it:

| instruction | bytes | measured clk | 8086 book | ratio |
|---|---|---|---|---|
| `nop` | 1 | 4.34 | 3 | 1.44 |
| `inc r16` | 1 | 4.34 | 2 | 2.17 |
| `xchg ax,r16` | 1 | 4.34 | 3 | 1.44 |
| `mov r16,r16` | 2 | 8.69 | 2 | **4.34** |
| `add r16,r16` | 2 | 8.69 | 3 | 2.89 |
| `cmp r16,r16` | 2 | 8.69 | 3 | 2.89 |
| `shl r16,1` | 2 | 8.69 | 2 | **4.34** |
| `mov al,[si]` | 2 | 15.22 | 13 | 1.17 |
| `mov al,[es:si]` | 3 | 19.00 | 15 | 1.26 |
| `jmp short`, taken | 2 | 18.19 | 15 | 1.21 |
| `mov ax,[disp16]` | 3 | 21.61 | 14 | 1.54 |
| `mov [disp16],ax` | 3 | 24.08 | 15 | 1.60 |
| `push ax`+`pop ax` | 2 | 29.70 | 19 | 1.56 |
| `call near`+`ret` | 4 | 52.13 | 27 | 1.93 |
| `mov ax,i`+`mul r16` | 5 | 132.53 | 129 | **1.02** |
| `xor`+`mov ax,i`+`div r16` | 7 | 162.85 | 160 | **1.01** |

Read the first seven rows down the *bytes* column: **4.34 clocks per
instruction byte, identically, whatever the instruction does.** That is the
4-byte prefetch queue behind an 8-bit bus, and it is a floor, not a tax:

> **An 8088 costs `max(execution clocks, 4.34 x instruction bytes)`**, plus
> ~4 clocks per byte of memory operand, plus a queue refill (~4 clocks per
> byte of the next instructions) after every taken branch.

So the useful question is never "what percentage do I add" — it is whether the
code is execution-bound or fetch-bound. `MUL` and `DIV` measure at 1.01–1.02
because the sequencer is busy long enough to hide every fetch; a run of
register-to-register moves measures at 4.34x because nothing hides anything.
**Shorter encodings are faster than cheaper instructions.** A `shl ax,1` and a
`mov ax,bx` cost exactly the same 8.69 clocks despite the book pricing them at
2 apiece, and `xchg ax,bx` — one byte — beats both at 4.34.

#### The glyph cell: the Part 2 anchor is right

| | |
|---|---|
| `FONT_CHAR`, one cell | **901 us** |
| `FONT_RUN`, per cell of ten | 905 us |
| a whole 78x34 page, per cell | 915 us |

Three routes, three numbers within 1.6%. **Part 2's "~1 ms per 8x8 glyph
cell" is confirmed** — it is 0.90 ms on a Hercules 5150, and that is the
number to keep estimating with.

`font_run` against the hand-written erase-and-letter pair came out at
**1.24x** for the skewed case (`skewPAIR/RUN x100 = 124`). tests/fontbench,
written separately and measured on different hardware, says **1.30**
(SPEC.md §6.1.1). Two harnesses, two machines, 5% apart.

#### A mono fill is bound by its ROWS, not its pixels

This is the finding the two-size design existed to produce, and the third
size is what proved it.

```
GFX_FILL   8x8     (  8 rows,     64 px)   1,128 us
GFX_FILL  64x64    ( 64 rows,  4,096 px)  12,443 us
GFX_FILL 256x128   (128 rows, 32,768 px)  31,682 us

fit to the two large sizes:   177 us per ROW  +  0.28 us per pixel
```

177 us is **840 clocks of setup per scan line**. A 64-pixel-wide row spends
177 us arriving and 18 us drawing: **91% overhead**. The per-pixel half is at
or below what a raw store costs — 0.28 us/px works out to 2.2 us per
framebuffer byte against the 3.26 us/byte a raw `rep stosb` to B000 measures
— so there is nothing to win in the inner loop and most of an order of
magnitude to win in the row setup, on every fill in the system.

**Two caveats on those coefficients, because the model does not quite fit.**
Solving all three sizes for `c + a*rows + b*px` gives a NEGATIVE per-call
term, which means the 8x8 point does not lie on the plane the other two
define; the two-point fit above over-predicts the 8x8 by 1.27x. So treat 177
and 0.28 as a decomposition of the large sizes, not as a law — the *shape*
(row-dominated, inner loop already at the bus) is solid, the coefficients
have a quarter-stop of slack in them.

And the single-slope figure this set's report printed (`fill ns per pixel =
2806`) is wrong as a model: it came from the 8x8/64x64 pair, where the row
cost dominates and is charged to the pixels. The harness prints two slopes
now, so a cost that is not linear in pixels shows itself.

#### The framebuffer is barely slower than RAM, which nothing here assumed

| 2,048 bytes, identical loops | RAM | Hercules B000 | ratio |
|---|---|---|---|
| `rep stosw` | 3,595 us | 5,651 us | **1.57** |
| `rep stosb` | 4,918 us | 6,668 us | 1.36 |
| byte read-modify-write | 31,238 us | 34,169 us | **1.09** |

A Hercules card costs about **4.8 extra clocks per byte written** and almost
nothing on a read-modify-write, because on a 4.77 MHz 8088 the *instructions*
are the bottleneck and the card's wait states hide inside them. The
read-modify-write measures **79.6 clocks per byte** end to end — SPEC.md §39.5
quotes "~30 cycles" — but only ~7 of those 79.6 are the bus. **The figure was
low and it was attributed to the wrong thing:** the mono renderer's inner step
is expensive because it is five 8088 instructions, not because it touches
video memory.

#### What a screenful costs

| operation | measured |
|---|---|
| one `GFX_PIXEL` / `GFX_HLINE 8px` call | 765 us |
| `GFX_FILL 8x8` | 1.13 ms |
| `GFX_FILL 64x64` | 12.4 ms |
| `GFX_FILL 256x128` | 31.7 ms |
| `GFX_SCROLL 256x128` by 8 | 48.2 ms |
| `WM_TITLE` strip (§11.92) | **43 ms** |
| full 78x34 text page | **2.50 s** |
| whole-screen fill, extrapolated | ~0.76 s |
| one vertical retrace period | 18.7 ms (53.5 Hz) |

**2.5 seconds for a page of text** is Part 1's "visible redraw" with a number
on it at last, and it is why §11.90/§11.91's incremental repaints exist. A
title strip at 43 ms is a fifth of a floppy revolution — cheap, and worth the
17 rows §11.92 bought.

The API floor is small enough to ignore and worth knowing exactly:
`GET_TICKS` through the far-call table is **46.7 us**, a near `call`+`ret` is
11.5 us, `SET_COLOR` 48 us, `WM_GEOM` 79 us, `WM_CLIP_SET`+`CLEAR` 328 us,
an ISA status-port `in` 8.7 us.

#### The floppy is one sector per revolution

| | |
|---|---|
| 16 KB read, cold motor | 7.63 s |
| 16 KB read, warm | 7.80 s |
| a one-sector file, open and read | 796 ms |
| throughput | **2,100 bytes/second** |

32 sectors in 7.63 s is **238 ms per sector**, and a 360KB floppy turns once
every 200 ms — so `dsk_xfer`'s one-`int 13h`-per-sector loop (§18.4.1) catches
**one sector per revolution and misses the other eight**. Warm is not faster
than cold, which confirms it: this is rotational latency, not motor spin-up
and not bandwidth.

That prices two things that were guesses. A 116KB Tracker module is **57
seconds**. And a per-track batch — nine sectors per revolution instead of one
— is worth about **9x on every load in the system**, which is the largest
single number in this document.

#### The kernel's own interrupts cost 1–3%

The same 800-iteration workload, timed with the `cli` window excluding every
interrupt and then again with all of them included. Two runs:

```
run 1   3,430,961 excluded   3,473,408 included   1.2%   (53 ticks)
run 2   3,430,971            3,538,944            3.1%   (54 ticks)
```

The excluded halves agree to 0.001%; the included halves differ by exactly one
tick, because method T quantises to 54.92 ms and this row is only ~1.9 s long.
**So the answer is 1–3% and the method resolves to ±1.9%** — quoting the 1.2%
alone, as the first draft of this section did, was reading a difference of two
numbers to a precision neither has. The tick, the mouse poll and the scheduler
are somewhere under a twentieth of a busy 8088 either way, and there is no
headroom problem.

`TASK_YIELD` — a full switch away and back — is **693 us**. `FILE_DFREE`,
which the SDK correctly says does no disk I/O, is **40 ms**, which is a lot of
FAT walking for a "free" call and is worth a look.

### Set 2 — the same 5150, driven as a CGA, plus a second `sysbench`

| | |
|---|---|
| machine | as Set 1 |
| adapter | **CGA (640x200)**, `VIDEO=cga` forced — the probe finds the Hercules first |
| build | `62c4172` (so it carries Set 1's two bad rows too) |
| reports | `GFXCGA.TXT`, a second `SYSBENCH.TXT` |

#### The harness repeats to 0.05% across two boots

`sysbench` measures nothing adapter-dependent, so running it on both boots is a
straight reproducibility test — twelve rows, two separate power-ups, a
different video card live:

```
loop overhead 29,699 / 29,695     mul       106,029 / 106,030
nop           27,807 / 27,822     div        78,171 /  78,153
mov r16,r16   55,672 / 55,676     RAM stosw  34,317 /  34,311
TASK_YIELD   248,030 / 248,033    FILE_DFREE 2,860,360 / 2,860,368
```

**Worst disagreement: 0.054%.** `PIT counts per tick` read 65,542 the first
time and **65,536 exactly** the second. Whatever else is wrong in these
reports, the measurement is not noisy.

#### The floor is in the CPU, not the framebuffer — and this is the proof

The four RAM rows match Set 1 to 0.015%, as they must. The framebuffer rows do
not, because they are the actual card:

| 2,048 bytes, identical loops | Hercules | CGA | |
|---|---|---|---|
| `rep stosw` | 5,651 us | 6,393 us | CGA **+13%** |
| `rep stosb` | 6,668 us | 7,418 us | +11% |
| word read | 12,777 us | 13,922 us | +9% |
| read-modify-write | 34,169 us | 34,774 us | +2% |
| **VRAM/RAM, word write** | **1.57x** | **1.78x** | |

So a CGA is measurably slower to write than a Hercules — the contention every
period programmer knows about, and it is 13%, not the order of magnitude
folklore suggests, because at 4.77 MHz the 8088 cannot go fast enough to
suffer much. Now put the primitives beside it:

| | Hercules | CGA | |
|---|---|---|---|
| `GFX_PIXEL` | 765.64 us | 765.70 us | **+0.008%** |
| `GFX_HLINE 8px` | 764.82 us | 764.80 us | **-0.003%** |
| `FONT_CHAR` one cell | 901.37 us | 908.56 us | +0.8% |
| `FONT_RUN` 10 aligned | 9,049 us | 9,175 us | +1.4% |
| `GFX_FILL 64x64` | 12,443 us | 12,961 us | +4.2% |

**Two physically different video cards, 13% apart at the bus, and the two
smallest primitives agree to one part in ten thousand.** That is as clean a
proof as this project will ever get that the ~756 us floor is CPU-side setup
and not framebuffer access — and it explains the gradient down the table:
the more of a call's time is actually spent writing pixels, the more the card
shows through (0.0% for a single pixel, 4.2% for a 4,096-pixel fill).

The fill decomposition agrees across the two adapters as well: **182 us per row
+ 0.33 us per pixel** on CGA against 177 + 0.28 on Hercules — the per-row
constant, which is pure setup, is 3% apart; the per-pixel term, which is the
bus, is 16% apart.

#### And the page repaint agrees across two screen heights

| | rows | measured | per row | per cell |
|---|---|---|---|---|
| Hercules | 34 + status | 2,499 ms | 71,403 us | 915 us |
| CGA | 16 + status | 1,236 ms | 72,696 us | 932 us |

Half the screen, half the time, **1.8% apart per row** — two independent
measurements of the same quantity on the same machine. A text page costs
roughly **72 ms per 78-cell row** on a 4.77 MHz 8088 whatever it is displayed
on.

#### Three rows of these sets are wrong

Recorded here rather than quietly re-run, because Part 6 rule 8 applies to the
apparatus too:

- **`RAM repe scasb` (25.77 us) is meaningless.** `repe` repeats *while
  equal*, so scanning for a byte that is never there stops at the first
  comparison. It should be `repne`. Fixed after this set; the row is junk in
  this one.
- **`one full-width row` (14.5 ms) is not a row of text.** It draws ten
  glyphs and 68 spaces, and a space cell is ~5x cheaper than a glyph on
  `font_run`'s fast path — 186 us/cell against the 915 us/cell a real page
  measures. That is exactly why the report prints `page predicted` beside
  `page measured`: they came out 0.49 s and 2.50 s, the check fired, and the
  fault was in the predictor. Fixed after this set; **the 2.50 s measurement
  is the good one**.
- **`one retrace period` is biased low by up to one frame in N.** The body
  waits for the retrace bit to fall and then rise, so it *leaves* the phase at
  a rising edge and every later iteration is a whole frame — but the first
  starts wherever the suite happened to be and can return almost at once. At
  N = 4 that is a quarter of the answer: the CGA read **80.6 Hz** where three
  of its four iterations were a clean **60.4 Hz**, and Hercules read 53.5 Hz
  against a card that runs at 50. Fixed after these sets with an untimed
  priming call and N = 12; **treat both retrace figures here as ~1 frame low.**
- **`GFX_BLIT4`'s striped row LAPPED THE COUNTER TEN TIMES**, on both adapters
  (Hercules 12.0 ms, CGA 13.2 ms reported; both ~10 laps short of ~20x their
  solid row). Everything that looked wrong about the blit was that. See below.

#### The blit anomaly was a lapped counter, and settling it produced the real finding

As published, the set said `GFX_BLIT4` was **2.36x slower with a solid source
than with 4-pixel runs** — 28.2 ms against 12.0 ms for the same 4,096 pixels.
That is backwards: a long run is the coalescer's best case, and the same
package measures 13-20x the *other* way on every adapter under QEMU.

Reading `gfx_blit4` cleared the primitive: the scanner is right, and
`gfx_blit_run` emits exactly one `gfx_hline` per coalesced run — so the solid
source makes 64 calls of 64 px and the striped one makes 1,024 calls of 4 px.
The striped source therefore does about **20x the work**, which is exactly what
the emulator says. The arithmetic then falls out:

```
reported striped         12.0 ms
+ 10 PIT laps (54.92 ms) 549.2 ms
= true                  561.2 ms   -> 19.87x the solid row
QEMU/Hercules work ratio             20.3x
```

**`bl_fold`'s modular subtraction is correct and its `!` guard is not enough.**
The guard flags an iteration *approaching* the wrap; an iteration that laps
reports its remainder, which is small, plausible, and unflagged. A 561 ms body
published itself as 12 ms.

The harness now brackets every method-P row with the tick counter and re-runs
it under method T when they contradict each other (flag `w`). One subtlety cost
a debugging round and is worth repeating: **ticks cannot measure a lapping row,
only detect one.** With IF = 0 the 8259 latches a single pending IRQ0 however
many the PIT raises, so a body that laps ten times still yields one tick — the
tick count under-reports by the lap factor. The usable test is `ticks >= N`,
which says *every* iteration crossed a tick boundary and contradicts any PIT
total claiming they were shorter than 54.92 ms. Verified by injecting a body
that laps deliberately: unflagged and 5x low before, flagged and correct after,
with no false positive anywhere else in the suite.

#### And so: a `gfx_hline` costs ~0.5 ms whatever its length

With the blit row corrected, the number that looked like a contradiction
becomes the corroboration:

| route to one `gfx_hline` | per call |
|---|---|
| solid blit, 64 calls in 28.2 ms | 441 us |
| striped blit, 1,024 calls in 561 ms | 548 us |
| `GFX_HLINE 8px` through the API | 765 us |

`GFX_PIXEL` measured 765.64 us and `GFX_HLINE 8px` 764.82 us — two different
routines agreeing to 0.1% — and fitting the two hline sizes gives **756 us
fixed + 1.16 us per pixel**. So the cost of a small drawing call is almost
entirely a fixed **~3,600 clocks**, three independent routes agree on it to
within the difference between a 4-, 8- and 64-pixel line, and the API far-call
cell is not it (`GET_TICKS` through the same table is 46.7 us).

**That is the largest single lever in the graphics system, and it is the same
lever the fill block found from the other side.** A fill costs ~177 us per
scan line with the pixels nearly free; an hline costs ~756 us with the pixels
nearly free. Both say the per-call and per-row setup in the mono renderer
dwarfs the drawing, and both say the inner loops are already at the bus. A
redraw is priced by **how many primitive calls it makes**, not by how many
pixels it covers — which is the opposite of the assumption every estimate in
Part 2 was built on.

### Set 3 — the floor taken apart, and a fifth of it removed

| | |
|---|---|
| machine | **not a machine** — QEMU with `-icount shift=3,sleep=off`, so the PIT counts guest INSTRUCTIONS (Part 4). Reproducible, machine-independent, **not time** |
| adapter | CGA 640x200 (`VIDEO=cga`) for the mono renderer; VGA 640x480 for the planar one; Hercules for the pixel check only |
| build | `dc92330` against the same tree plus the §5.7 changes |
| date | 2026-08-06 |

Set 1 and Set 2 said the floor was CPU-side setup but not **which** setup, so
the first thing done here was to count it rather than guess (rule 4). One
`gfx_pixel` on the 1bpp renderer is **196 guest instructions**, and the
static path agrees: they are spread over eleven routines with no hot spot
anywhere — the API far-call cell, `gfx_pixel`'s rect marshalling, §11.3's
clip test, `bb_mono_chk`, the `[bb_on]` dispatch, `vga_rect_setup`,
`gfx_rowbase`, `bb_dirty_rect`, `bb_ink`, `bb_plane_op`, `bb_col`. **About a
third of it was register discipline and call structure** — 13 push/pop pairs
at Part 2's measured 29.7 clocks and ~10 near call/rets at 52.1 — and none
of it was drawing. SPEC.md §5.7 lists the seven changes and why each is a
rule rather than a tidy-up.

The mono renderer, before and after, in PIT counts over N iterations:

| row | N | before | after | repeat | per call |
|---|---|---|---|---|---|
| `GFX_PIXEL` | 300 | 560 | 451 | 449 | **−19.6%** |
| `GFX_FILL 8x8` | 200 | 531 | 430 | 427 | −19.3% |
| `GFX_VLINE 8px` | 200 | 538 | 437 | 435 | −18.9% |
| `GFX_FRAME 64x64` | 24 | 573 | 468 | — | −18.3% |
| `GFX_HLINE 8px` | 200 | 375 | 314 | 310 | −16.8% |
| `GFX_FILL 64x64` | 24 | 688 | 588 | 587 | −14.6% |
| `GFX_BLIT4 4px runs` | 6 | 15,930 | 13,713 | 13,711 | −13.9% |
| `GFX_FILL_GRAY 64x64` | 24 | 680 | 586 | 585 | −13.9% |
| `GFX_BLIT4 solid` | 12 | 2,637 | 2,276 | 2,275 | −13.7% |
| `GFX_XOR_FILL 64x64` | 24 | 710 | 616 | 614 | −13.4% |
| `WM_TITLE strip` (§11.92) | 4 | 420 | 368 | 367 | −12.4% |
| `GFX_FILL 256x128` | 6 | 419 | 372 | — | −11.2% |

**The control rows are the point of the table, not an afterthought** (rule
7): `GFX_FILL_PAT 64x64` (806 → 802), `GFX_SCROLL 256x128` (1,351 → 1,354)
and `one full-width row` of text (2,220 → 2,219) are the three drawing paths
none of these changes touch, and all three sat still. A harness that had
moved them would have been measuring itself.

The same suite on **VGA**, where the planar VRAM bodies run and `bb_col`
never does, so only the shared coordinate core changed: `GFX_PIXEL` 424 →
404 (−4.7%), `GFX_FILL 8x8` 338 → 317 (−6.2%), `GFX_BLIT4 4px runs` 13,110
→ 12,192 (−7.0%), `GFX_FILL 64x64` and `GFX_SCROLL` unmoved. Nothing on
either adapter got worse.

**Two honest limits.** First, a repeat run of the whole suite on the
unchanged kernel puts the noise floor where you would expect: rows in the
hundreds of counts repeat to under 1% (`GFX_BLIT4 solid` to 0.04%), and rows
in single digits — `GET_TICKS`, `MOUSE`, `ISA status port in`, `GFX_HLINE
256px` — swing by more than the effect and **must not be quoted from this
set at all**. Second and more important, **icount counts instructions and
the question was clocks**. Three of the seven changes remove clocks without
removing instructions: two variable shifts (8 clocks plus 4 per bit), a
`shl bx,13` (60), and push/pop pairs (one instruction, 15 clocks each). A
hand model over the changed sequences, priced from Set 1's own measured
per-class table, puts the pixel path at about **−620 clocks of 3,600, −17%**
— which agrees with the −19.6% instruction figure to within the precision
either deserves. **What would settle it is `gfxbench` on the 5150 again**,
and until that happens Part 2's 756 us stands as the number to estimate
with.

Rendering was verified byte-for-byte rather than by eye, on all three
adapters and both renderers, over a fixture of desktop dither, window
frames, a file listing, an XOR selection band, a pull-down menu and its
save-under restore: **CGA pixel-identical** bar the menu-bar clock's last
glyph cell, **VGA pixel-identical** with the §32 back buffer both off and
on, and **Hercules** differing by 10 pixels of menu bar — against 17 between
two boots of the *same* kernel, so below that fixture's own reproducibility.

#### What is left, and what it would cost

Priced from the same teardown, for whoever comes next:

| still on the floor | worth | why it was not taken |
|---|---|---|
| `gfx_rowbase`'s `mul` by the stride | ~145 clocks, 4% | a per-row table is 2 bytes x `[vid_h]` — 960 on VGA, and `KERN_BUDGET` has 1,536 left |
| `bb_rect`'s eight push/pop pairs | ~240 clocks, 7% | it is `gfx_fill`'s "clobbers flags" contract, which every caller in the tree leans on |
| the API far-call cell | ~223 clocks, 6% | the package ABI (§20.1) |
| a dedicated 1-row body for `gfx_hline`/`gfx_pixel` | maybe 25% of what remains | a second implementation of the same pixels, ~100 bytes, and Part 3 item 4's exact failure mode |
| a one-entry memo on `gfx_rowbase` | ~4% of a text row (78 cells share a y) | it is a *loss* on the single-call case this section is about — the wrong trade for the headline number, the right one for text |
