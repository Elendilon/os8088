# RealBoy - a real-mode Game Boy emulator: full speed on a 12 MHz 286, a demo on the 5150

**A PLAN, BUILT THROUGH WAVE 4** (each wave below says what it came to). It
is the design and the order of work for **RealBoy** (`apps/realboy/`, `REALBOY.O88`), a native os8088 package that
runs original Game Boy (DMG) cartridges. When the work starts, the contract
will be `docs/REALBOY-SPEC.md`, written in wave 1. This file stays the record
of why the design reads that way.

**Every figure is marked.**
- **MEASURED** figures cite the report they come from.
- **PREDICTED** figures are hand counts from the 8088 and 80286 data-book
  timings.

The last attempt in this tree to predict an emulator's speed by hand, the
Apple II plan, was optimistic by six times (docs/APPLE2-SPEC.md, its speed
section). So the first wave measures before anything else is built on these
numbers, and section 2 now has a real emulator to measure against.

## 1. The intake

The owner asked:

> Investigate a gameboy emulator, for a 4.77Mhz 5150. Is that feasible?

Three reports answer that.

**docs/reports/GAMEBOY-FEASIBILITY-2026-10-19.md** (PREDICTED). Full speed is
out of the 5150's reach. The 8088's bus moves only about 1.14 bytes for every
Game Boy bus access, so even a perfect translator would land near half speed
on busy code.

**docs/reports/GAMEBOY-WORKLOAD-2026-10-19.md** (MEASURED on the host with
`tools/gbprof.py`). How much of each frame a real game's CPU spends on work
an emulator cannot skip:

| game | busy share of a frame | busy instructions a frame |
|---|---|---|
| **Super Mario Land** | **23.3%** (p90 39.6%, p99 50.5%) | 1,747 |
| **libbet** | **13.7%** | 1,089 |
| **Kirby's Dream Land** (the owner's target ROM) | **29.4%** | 2,245 |

The Kirby row is in the third report, section 5. Kirby never `HALT`s: it
spins on a flag for 70% of every frame.

**docs/reports/GAMEBOY-NOGMB-2026-10-19.md** (MEASURED in MartyPC and
86Box). What the only existing XT/AT Game Boy emulator, no$gmb's
assembly-language XT/AT build, gets out of these machines (section 2).

Then the owner retargeted the work:

> We'll retarget the primary goal to a ~12Mhz 286, and keep "some very light
> gameboy demo that sits in hlt most of the time" as a final wave to show off
> on the 5150.

They also supplied three things:
- no$gmb's XT/AT build;
- **Kirby's Dream Land** as the target ROM (256 KB, MBC1);
- **Looney Tunes** (1 MB, MBC5, CGB-enhanced but DMG-compatible) for when
  wave 6 reaches large ROMs.

**Super Mario Land is the owner's favourite, and it is the game the speed
work is judged on.** None of the cartridges is in this repository, and none
may be.

**The reference set** was used for reading. None of it is a code base the
port derives from:
- Peanut-GB (MIT), the profiler's host core;
- Pan Docs and the gbdev community documentation, for hardware behaviour;
- Blargg's test ROMs, Mooneye's test suite and dmg-acid2, as fetched gates
  (section 7).

**Prior art.** No search turns up a Game Boy emulator for a 286 except
no$gmb's XT/AT build, which section 2 measures. Every other DOS Game Boy
emulator found asks for a 386DX-33 (no$gmb's own 386 build) or a Pentium
(GaelCathelin's Game-Boy-DOS, DJGPP).

## 2. Why a 286 and not a 5150, and the bar that is set there

| | 5150, 8088 at 4.77 MHz | ami286 at 12.5 MHz (`vm/286`, `vm/286-525`) | Victory 286, 16 MHz (the owner's) |
|---|---|---|---|
| clocks per Game Boy frame (59.73 Hz) | 79,909 | **209,284** | 267,884 |
| clocks per Game Boy M-cycle | 4.3 (after refresh) | **11.9** | 15.3 |
| memory bus | 8-bit, 4 clocks a byte | 16-bit, 2 clocks a word, DRAM at 1 wait state | 16-bit, with wait states 86Box does not model |
| VGA writes | - | - | **1.15 us a byte** (`rep movsb` to mode 12h, MEASURED, docs/reports/VM3BENCH-PVGA286-2026-10-13.md) |
| against a 5150 | 1x | - | **~20x on RAM copies, ~4.6x on screen writes** (MEASURED on 86Box mr286, docs/reports/VIDEO-86BOX-286-2026-09-26.md) |

### 2.1 The bar, MEASURED: no$gmb's XT/AT build

no$gmb runs at its fastest settings, timed with gbclock, our counting ROM
(docs/reports/GAMEBOY-NOGMB-2026-10-19.md):

| | 286, 12.5 MHz (86Box) | 8088, 4.77 MHz (MartyPC) |
|---|---|---|
| a game that does nothing (gbclock 0.7% busy) | **100%**, held at real time | **26.6%** |
| gbclock 25.7% busy, close to Super Mario Land's average | **47.1%** | **10.8%** |
| **Super Mario Land, in play** (no$gmb's own meter) | **~36%** (32-50%) | - |
| **its fixed cost per Game Boy frame** | ~14.5 ms | ~60 ms |
| **its cost per busy M-cycle** | **~58 clocks** | ~100 clocks |

**At no$gmb's cost per M-cycle, the 286 cannot carry Super Mario Land even
drawing nothing.** Its ~4,100 busy M-cycles a frame would be ~238,000 clocks,
against 209,284.

### 2.2 The budget RealBoy has to meet, PREDICTED

The interpreter in section 4.1 costs, by hand count:
- **on an 80286: ~20-26 clocks per M-cycle**, which is 45-60 per average
  Game Boy instruction, its 16-bit bus and cheaper jumps doing most of the
  work;
- **on an 8088: ~35-45 per M-cycle**, 80-100 per instruction.

**That is 2.2-2.9 times leaner than no$gmb on both CPUs.** It is plausible,
because no$gmb is a debugger as much as an emulator and its XT/AT build is
the generic one, "a bit slower" in its own words. But it is the claim this
plan stands or falls on, and **wave 1 measures it before anything else is
built.**

At that cost, Super Mario Land's 1,747 busy instructions a frame are:

| | ami286 at 12.5 MHz | 5150 |
|---|---|---|
| average frame | **37-50% of the frame** | 1.7-2.2 times the frame |
| p90 frame (39.6% busy) | 64-85% | - |

Kirby's 2,245 busy instructions are 48-64% on the ami286, **provided its
70% spin-wait costs nothing** (section 4.1, Events).

**So the 286 carries an ordinary game's logic at full speed, with between
half and two thirds of the machine left for the picture on an average frame
and much less on a busy one.** The 5150 cannot carry these games. It can
carry a program written to be idle (section 6, wave 8).

**"Full speed" in this plan means GAME speed**: the cartridge's logic, timers
and music run at 59.73 Hz. The display drops frames when it must. That is how
every period emulator was measured, and it is the only definition the
arithmetic supports. A full 60 frames a second is a stretch figure (section
5).

## 3. Decisions

### 3.1 The owner's, all taken

**At intake:**
- **Primary target: a ~12 MHz 286 with VGA.** The tree's machine is `vm/286`
  (ami286, 12.5 MHz, OTI-067), and the field machine is the Victory 286.
- **Final wave: a very light demo on the 5150** that sits in `HALT` most of
  the time.
- **Assembly is allowed**, and Peanut-GB is a reference, not a base.

**After the first plan:**
1. **Pure NASM, not a C shell.** The tree's other emulators are C packages
   with hand-written assembly cores (SPEC.md 73; `apps/apple2`, `apps/c64`).
   Here the core, the memory map and the renderer are all assembly anyway,
   and `apps/os88ui.inc` already supplies the shell. So there is no SmallerC
   dependency, none of C's four extra rules, and one build.
2. **One core, 8086 code, no `cpu 286` island.** SPEC.md 1 rule 1 is
   "8086 only", and no 286 island exists anywhere in the tree. The **same
   core runs the 5150 demo** in wave 8. If wave 1 measures a 286 island as
   worth it, that is a written exception to rule 1, decided then on a number.
3. **The name is RealBoy**: a real-mode Game Boy emulator, `apps/realboy/`,
   `REALBOY.O88`.
4. **The 5150 demo is our own ROM**, its source committed and assembled with
   rgbds. rgbds is fetched and built at a pinned commit and never committed
   (`tools/gbclock.py` already does this). It is written to *feel*
   impressive while doing the least work possible outside `HALT`.
5. **No boot ROM.** The core starts at `$0100` with the documented post-boot
   register and I/O state. **Compatibility means a core set of games running
   well, not every game.** Super Mario Land is the one the owner cares about
   most, and Kirby is the target.

### 3.2 Fall-outs, recorded so they are not re-opened

- **No cartridge ROM is ever committed or shipped.** The user supplies their
  own. The gates use fetched, freely licensed test ROMs at pinned SHA-256s
  (`tools/getapple2rom.py`'s shape) and our own gbclock. A commercial ROM is
  used only from a path the user gives (`$OS88_GB_ROMS`), and a row that
  needs one SKIPS without it and says so.
- **Banking is a page-table write, never a copy** (section 4.2). Super Mario
  Land makes 7.8 MBC writes a frame and Kirby 8.35.
- **Register writes are logged with their line**, and the frame is drawn in
  bands between them (section 4.4). The status bar in Super Mario Land
  depends on it.
- **A spin-wait costs nothing** (section 4.1, Events). Kirby, the target,
  never `HALT`s.
- **No worker task.** The windowed machine runs in wall-clock slices on the
  UI task, the way APPLE2 does (APPLE2-SPEC section 4.3.1). The fullscreen
  machine runs inside the `OSAPI_FSX_RUN` bracket, which owns the CPU.
- **The region is movable** (`OS88_REGION_MOVABLE`, enforced by
  `tests/unit/t_movable.py`). The guest-memory claims are declared movable
  with one relocation proc, which re-derives the page tables from the claim
  bases (section 4.2). The tables are derived data, so the proc is short and
  there is no stale pointer for it to miss.

## 4. The design

### 4.1 The CPU core: a threaded interpreter

**The register map.** The SM83 descends from the 8080, as the 8086 does:

| SM83 | 8086 |
|---|---|
| A | AL |
| F | AH, as `lahf` leaves it. ZF, AF and CF are Z, H and C directly; N has its own byte |
| BC | CX |
| DE | DX |
| HL | DI |
| PC | SI (a host pointer into the current code region) |
| cycles to the next event | BP |
| dispatch | BX, with BL held at 0 |

**Dispatch.** Each opcode's handler sits at `opcode x 256` in a 64 KB code
segment of its own. The `CB` page has a second segment, or a compact table:
its operations are regular, and a handler that decodes its own register
field may be the smaller choice. Each handler ends with the dispatch inline:

```
mov  bh,[si]     ; the next opcode is the high byte
inc  si
jmp  bx
```

That is ~28 clocks on an 8088 and ~16 on a 286, PREDICTED.

**Program counter.** SI is a host offset and DS is the segment of the region
being executed. A jump or call recomputes both, and only there can execution
change region. Straight-line code crosses a region boundary only at
`$4000`/`$8000`, and that is caught by a guard handler placed past the end of
each region.

**What the measured opcode mix says** (the workload report, section 2):
- `jr nz/z` are ~18% of Super Mario Land's busy cycles;
- `ldh a,(n)` / `ldh (n),a` are 12.7%;
- `call` and `ret` are ~8%.

So `ldh` with `n >= $80` (HRAM) is a direct byte access with no I/O test. A
taken backward `jr` is where the event check lives (`sub bp,n / js event`),
so straight-line code carries no check at all. `call` and `ret` use the
memory map's fast RAM path, because SP is in WRAM or HRAM in every game.

**Events.** BP counts M-cycles down to the next scheduled event. Events are:
the PPU line (every 114 M-cycles), the timer overflow, the serial transfer
and the end of the wall-clock slice. Each handler subtracts its own cost, and
the check runs on control transfers and memory-mapped I/O.

A **read** of `LY` or `STAT` is computed from the cycle position, not
stepped. That is how Super Mario Land's 21.5 `STAT` reads a frame stay cheap.
**`HALT` skips straight to the next event**, and that is where 75-87% of each
measured frame goes, free.

**So does a spin-wait, and the target ROM depends on it.** Kirby never
`HALT`s. It spends **70% of every frame** in a loop that re-reads one flag
and writes nothing: `ld a,(nn)` 32% and `jr nz` 26% of its non-HALT cycles
(docs/reports/GAMEBOY-NOGMB-2026-10-19.md section 5). An emulator that pays
for that loop carries ~3.4 times Kirby's real load. no$gmb's XT/AT build runs
Kirby's title at 1-5% on the 8088.

The check is in the taken backward branch handler, which already holds the
event check. A taken branch back by 12 bytes or fewer, to the same target as
last time, whose iteration made no write (one flag byte, set by every write
handler, cleared by the branch), is idle: BP goes to zero and the scheduler
runs the next event. `gbprof`'s classifier is exactly this rule, and it finds
70.1% of Kirby's frame and 0.9% of Super Mario Land's. A false positive
would only wake early, never late, because the next event (the frame
interrupt) is what the loop waits for anyway.

### 4.2 The memory map: two page tables, no copies

There are two tables of 256 words, `rdseg[H]` and `wrseg[H]`, indexed by the
high byte of the address. Each entry is a segment chosen so that
`segment:address` is the host byte. The game's own 16-bit address is
therefore the 8086 offset, and a plain RAM access is:

```
look up the segment for H, load ES, mov al,[es:di]
```

**A bank switch is 64 identical stores.** Every page in `$4000-$7FFF` maps
through the same segment, `bank_base - $400`. That is one `rep stosw` of 64
words: about 200 clocks on a 286 and about 900 on an 8088, PREDICTED. At
Super Mario Land's 7.8 switches a frame, that is about 1% of a 286.

Each write page has a **kind** byte. Zero means plain RAM and stays inline.
Anything else calls a handler:
- `$0000-$7FFF`: the MBC;
- `$8000-$9FFF`: VRAM, which also marks the line range dirty;
- `$FE00-$FEFF`: OAM;
- `$FF00-$FF7F`: I/O, with its side effects (DMA, `DIV` reset, `LCDC`, the
  register log).

Reads of `$FF00-$FF7F` go through one compare to an I/O read handler.

**Guest memory is heap claims, paragraph-aligned:**
- the ROM, as banks of 16 KB;
- WRAM 8 KB, VRAM 8 KB, OAM and HRAM;
- cartridge RAM up to 32 KB.

**ROM size.** On a 640 KB machine the arena is about 449 KB
(docs/plans/KERN-DOS-PLAN.md). **Version 1 takes ROMs up to 256 KB**, which
covers most of the DMG library's best-known titles (Tetris, Super Mario Land,
Dr. Mario, Kirby's Dream Land and many more). It refuses larger ones, with
the arithmetic on screen. Wave 6 is the follow-on for larger ROMs: a bank
cache in conventional memory over `XMEM.DRV`. It would hit nearly always,
because a game's hot banks are few, and wave 6 measures that first with
`gbprof`'s per-bank counts.

### 4.3 MBCs

- **Version 1:** ROM-only, MBC1, MBC2 and MBC5.
- **MBC3** comes with its real-time clock in wave 5. The clock reads the
  host's time on the switches that latch it.

### 4.4 The picture: band rendering from a register log

**The register log.** Every write to `LCDC`, `SCX`, `SCY`, `WX`, `WY`, `BGP`,
`OBP0` or `OBP1` while a line is visible is appended to a log with its `LY`.
VRAM writes mark a line range dirty.

**Drawing.** Drawing a frame walks the log and renders each band between two
logged changes with the state that held there. The background, the window
and up to 10 sprites a line are composed into a **line buffer of bit-planes**.
The Game Boy's own tile format is two bit-planes: the low bits' byte, then
the high bits' byte. So the composer never converts a pixel. It shifts tile
bytes into place for the fine scroll and masks the sprite planes over them.

**The writers.** Each takes the line buffer to a screen, comparing it against
a shadow of the last frame in RAM first. On a 286, RAM is about 20 times
faster than the VGA (section 2), so a compare that saves a VGA write nearly
always pays. Large plain areas, the sky in Super Mario Land, are the common
case.

| writer | where | format | per full frame |
|---|---|---|---|
| **VGA0D** (SPEC.md 53.4, mode 5) | fullscreen | 320x200 planar; the picture at 1x | planes 0 and 1 ARE the Game Boy's two bit-planes; planes 2 and 3 select the sprite palette. **5,760 bytes** |
| **VGA12** (mode 7) | fullscreen | 640x480 planar; the picture at 2x | each byte doubled through a 256-word table, each row written twice. 23,040 bytes |
| **window, VGA desktop** | windowed | `OSAPI_GFX_BLITP` (planar, x a multiple of 8) | the desktop's black, dark grey, light grey and white are indices 0, 8, 7 and 15. After the `BGP` map, planes 0-2 are the high bit inverted and plane 3 the low bit inverted, so it is two bytes per 8 pixels, still no per-pixel work |
| **window, 1bpp desktops** | windowed | `OSAPI_GFX_BLIT1`, 2x2 ordered dither | the 5150's and Hercules' path |
| **HERC / CGA320** | fullscreen | wave 8 | section 6 |

**The palette.** In a bracket the application owns the screen. `BGP`, `OBP0`
and `OBP1` become **DAC entries**, so a palette fade costs the renderer
nothing. A write to them mid-frame is logged like any other.

**What the frame costs on the ami286, PREDICTED.** Composing all 2,880 tile
rows is ~40 clocks each, about 115,000 clocks. VGA0D's 5,760 bytes at the
measured 1.15 us are about 6.6 ms, roughly 82,000 clocks. **A full frame with
no shadow savings is ~94% of a 209,284-clock frame.**

Against Super Mario Land's 46-62% for the CPU, that is about **25-35 frames
a second** at full game speed, before the shadow compare's savings. Both
terms are wave 1's and wave 3's to measure.

### 4.5 Pacing, frame-skip and sound

**Pacing.** Game time runs off the PIT. A bracket that asks for
`FSXF_RATE` (SPEC.md 53.2.2, `kern_big`, which every 286 runs) gets a hook
at a rate of its own, so game time is counted exactly without polling. The
emulator runs the CPU to the end of a frame, then draws that frame only if
the wall clock has time left before the next one. Otherwise it skips the
draw and runs on, so **the game holds 59.73 Hz and the display takes what is
left**.

The hook obeys SPEC.md 53.2.2's rules: no kernel calls, at most 48 bytes of
stack, armed before the entry proc runs. The windowed machine uses APPLE2's
duty-cycle slice instead (APPLE2-SPEC section 4.3.1).

**Joypad.** `OSAPI_KEY_DOWN` is polled once a frame for held state, which is
how WireBall does it inside the bracket (`apps/wireball/wbgame.inc`). The key
map is configurable.

**Sound, wave 5.** Version 1 plays the louder square channel on the speaker
with `os88_snd_tone`'s pattern (C64-SPEC section 11.4), with one stop path
and the busy-grant retry. After that, a Sound Blaster's OPL2 can carry both
square channels and an approximation of the wave channel through
`SOUND.DRV`. PCM mixing all four channels through `OSAPI_FSX_SPK` (SPEC.md
34.11) is priced in wave 5 and taken only if the measured 286 has the
cycles.

**Save RAM.** Battery-backed cartridge RAM is written to
`SYSTEM/APPDATA/` (SPEC.md 19.9) when the user closes the window, and on an
explicit Save. It is only ever done from the UI task.

## 5. The levers, if wave 1 measures worse than section 2

These are ordered by cost. **None is built until a measurement asks for it.**

1. **Superinstructions.** Fuse the measured hot pairs into one handler each:
   `dec r / jr nz`, `ldh a,(n) / cp n / jr`, and `ld a,(hl+) / ld (de),a`.
   `gbprof` can rank the pairs on the host before any assembly is written.
2. **Wider idle-loop recognition.** The basic rule is not a lever but part
   of the core (section 4.1, Events), because Kirby needs it. What is left is
   recognising countdown delay loops (`dec b / jr nz` with nothing read),
   which are 1-3.4% of the measured frames.
3. **Hardware panning for a scrolled background.** The attribute controller's
   pixel panning plus the CRTC start address would replace the composer's
   fine-scroll shifts. Its cost is the mid-frame split a status bar needs.
   Priced in wave 3, not before.
4. **A dynamic recompiler.** It would cut the CPU term about 2x (the
   feasibility report, section 4.2), and it is the largest and riskiest item
   in this list. It is wave 7, and it is conditional.
5. **A static recompiler** - translating the cartridge ahead of time - is
   investigated and NOT TAKEN (docs/reports/REALBOY-STATIC-2026-10-20.md).
   It is feasible: a disassembler that reads `RST 28h`'s jump table finds
   99.88% of Super Mario Land's busy instructions. But what only the
   ahead-of-time view proves is worth ~0.3 ms of a 6.55 ms frame on the
   Victory twin, at ~170 KB of code against today's 35.6 KB. The time is in
   three short counted loops, 17-26% of the machine while it scrolls with
   enemies on screen. Replacing one of them took the CPU from 6.55 to 6.22
   ms a frame, and the dynamic recompiler can recognise all three.

## 6. The 5150 demo

What the 5150 has room for, PREDICTED:
- **The CPU budget is ~600-800 interpreted instructions a frame with nothing
  drawn.** That is about 79,900 clocks at ~90-130 clocks per instruction.
- **The demo should stay under ~250 busy instructions a frame**, about 3% of
  a frame's CPU. That leaves about two thirds of the machine for the picture.

**What no$gmb shows about the 5150, MEASURED.** Its XT/AT build runs a game
that does *nothing* (gbclock at 0.7% busy) at **26.6%** on the 8088, because
its fixed cost is ~60 ms per Game Boy frame
(docs/reports/GAMEBOY-NOGMB-2026-10-19.md). On the 5150, then, the CPU core
is only half the demo's problem. **The fixed cost has to come under ~16 ms
a frame**, and a frame in which nothing changed must cost close to nothing:
- no line is composed unless the register log or a VRAM write touched it;
- `HALT` skips straight to the next event;
- the PPU's per-line events collapse to one per frame when nothing reads
  `LY`/`STAT` and no `LYC` or mode interrupt is enabled.

**The demo ROM is ours.** It is written for the 5150 the way WireBall is
written for it: a scene that only changes a few sprites and a scroll register
each frame, then `HALT`s. `gbprof` on the host checks its busy share against
that bound before it ever reaches an 8088.

**The writers:**
- **HERC**: the owner's 5150 has a Hercules. 720x348 at 2x2 with an ordered
  dither gives four shades, and each tile row becomes 4 bytes through two
  nibble tables.
- **CGA320**: the Game Boy's four shades as CGA's four colours.

Both writers use **damage tracking**, so a frame redraws only the tiles whose
map entry, tile data or sprite overlap changed. That works because the demo
is designed not to scroll the whole screen.

**The gate is MartyPC on `os8088_5150_herc_gla`**: game frames against wall
frames over 60 seconds, which must equal 1.00. Running libbet on the same
machine is a curiosity row that reports what it gets, which is PREDICTED at
about 65-80%.

## 7. Verification

**The instruments:**
- **MartyPC** (CLAUDE.md, Testing) is exact for 8088 cycles, so it is the
  automated speed guard. The core is the same code on both CPUs, so an 8088
  cycle regression is a 286 regression.
- **QEMU is on the closed list for the 286** (item 1). It runs the core's
  correctness gates in raw mode and the package's functional rows, and it
  times nothing.
- **86Box times the 286, and it is scripted now** (`tools/os88box.py`,
  docs/86BOX.md). `step MS` runs exactly MS of emulated time, and `memr`
  reads RealBoy's own frame counter out of the guest by symbol, so a 286 speed
  is a row rather than a photograph. This is how
  docs/reports/GAMEBOY-NOGMB-2026-10-19.md was taken, and `vm/286-525`
  (ami286, 12.5 MHz) is the machine. 86Box models the 286 per instruction and
  is not cycle-accurate, so a 286 figure says which emulator it came from. The
  Victory 286 in the field (docs/FIELD-MACHINES.md) is the iron check.
- **gbclock** (`tools/gbclock.py`) is the load. One ROM of our own counts
  emulated frames and keeps the Game Boy CPU busy for a set share of each
  frame, so RealBoy and no$gmb are timed on the same footing. The slope across
  its variants is the core's cost per M-cycle, and the intercept is the fixed
  cost per frame.
- **`tools/gbcal.py`** re-times no$gmb (the user's copy, under the user's DOS)
  on either machine, so every RealBoy number can be put beside the existing
  emulator's.
- **The package also draws its own speed and frame rate** (an `F1` overlay,
  timed by PIT), for the iron, where no harness reaches.

**The fetched test ROMs.** Each is pinned by commit and SHA-256 in
`tools/getgbtest.py` and never committed:
- Blargg's `cpu_instrs`, `instr_timing`, `mem_timing` and `halt_bug`;
- Mooneye's acceptance subset for timers, interrupts and the PPU's mode
  timing;
- **dmg-acid2** (MIT), compared pixel for pixel against its reference image.

**The differential trace.** `gbprof` grows a `--trace` mode that prints
Peanut-GB's registers per instruction. The core's raw-QEMU harness prints
the same, and a host script diffs the two up to the first divergence. That is
docs/DOS-DEBUGGING.md's lesson about tracing both sides, applied before
anything is wrong.

## 8. Waves

| wave | title | in this PR |
|---|---|---|
| 0 | Investigation: feasibility, workload, `gbprof`, the no$gmb bar, the 86Box harness | **yes, done** |
| 1 | The contract, the core and the measurement that decides the rest | |
| 2 | The machine: timers, interrupts, PPU timing, MBCs | |
| 3 | The picture, and the package on the desktop | |
| 4 | The fullscreen speed path on VGA | |
| 5 | Sound, save RAM, MBC3, polish | |
| 6 | ROMs over 256 KB (bank cache) | conditional |
| 7 | The speed levers (section 5) | conditional |
| 8 | The 5150 demo, disks, Wire record | |

### Wave 1 - the contract, the core, and the measurement that decides the rest

**BUILT.** docs/REALBOY-SPEC.md is the contract and
docs/reports/REALBOY-CORE-COST-2026-10-19.md the measurement: `cpu_instrs`
and `instr_timing` pass bare, the first 10,000,000 instructions agree with
Peanut-GB (registers and clock, after correcting the reference where it is
not the hardware), and the core costs **26.20 clocks per busy M-cycle on
86Box's 286** (the gate is 26) and 47.78 on the 8088. **The number that
matters more came after**: real games in play, with no picture, take
**77.9% of the 286 (Super Mario Land) and 104.2% (a busy scene of Kirby's)**,
about 35 and 31 clocks per busy M-cycle all-in, and on the 286 the time is
the interpreter's own dispatch rather than any one handler. So waves 2 and 3
proceed on the gate, and the recompiler of section 5 item 4 is the lever the
measurement names; superinstructions are worth about 2%. The files differ
from the list below: the core is generated (`apps/realboy/rbgen.py`) and
the system half is `apps/realboy/rbsys.inc`.

**Features**
- `docs/REALBOY-SPEC.md`: its own contract, cited as "section N".
- The SM83 interpreter (section 4.1) with the minimal machine `cpu_instrs`
  needs: ROM-only and MBC1, the serial port as text output, `DIV`/`TIMA`,
  interrupts, `HALT` and the spin-wait rule.
- A raw-QEMU harness that runs a ROM headless and captures the serial output,
  `apps/apple2/a2memtest.asm`'s shape.
- `tools/getgbtest.py`.
- A bench build with rendering off, run on gbclock's variants. On the 8088
  its frame counter is read against MartyPC's cycle counter. On the 286 it is
  read through `tools/os88box.py` against 86Box's emulated clock.

**Files**
- `apps/realboy/rbcpu.inc`, `rbmem.inc`;
- `tests/rbcore/` (harness, bench);
- `tools/getgbtest.py`, `tools/gbtrace.py`;
- `docs/REALBOY-SPEC.md`.

**Done when**
- `cpu_instrs` prints `Passed all tests` in the raw harness.
- The differential trace agrees with Peanut-GB over the first 10 million
  instructions of `cpu_instrs`.
- **A report carries the core's measured cost per M-cycle**, fitted across
  gbclock's variants, on MartyPC's 8088 and on 86Box's `vm/286-525`, beside
  no$gmb's ~100 and ~58 from the same ROMs.
- Kirby's measured spin-wait is skipped: `gbprof`'s 70.1% shows up as idle in
  the core's own counters.

**The gate on the rest.** On the ami286, section 2.2 predicts 20-26 clocks
per M-cycle, against no$gmb's ~58.
- **At 26 or under, waves 2-5 proceed as written.**
- **Over 26**, wave 7's levers move ahead of wave 3, because the picture is
  then fighting the CPU for a frame that is not there.
- **Over 40**, the owner hears about it before anything else is built. At
  that cost Super Mario Land's average frame takes ~78% of the 286 on the CPU
  alone, and full speed is a recompiler's or not at all.

### Wave 2 - the machine

**BUILT.** `tests/gbcpu.py` passes `cpu_instrs`, `instr_timing`,
`mem_timing` (register accesses timed to their M-cycle), `halt_bug` (the
HALT bug) and 26 of Mooneye's 63 DMG acceptance tests; REALBOY-SPEC section
12.4 says which of the rest fail and on what model. The trace still agrees
for 10,000,000 instructions. **dmg-acid2 matches pixel for pixel** through
wave 3's renderer, and it found the wave's worst bug: STAT interrupts had
never fired (`rb_statsch` lost STAT to a DIV), so a status bar on LYC - Super
Mario Land's - did nothing. With them firing, **Super Mario Land in play
takes 90.8% of the 286 on the CPU alone** (it was 77.9% without its LYC
handler running), and the composer, line by line, is ~40 ms a frame there:
section 4.4's ~115,000 clocks is out by about four. That is the argument
for wave 4's tile-level, hardware-panned path over composing every line,
and for the recompiler.

**Features**
- PPU mode timing, with `LY`/`STAT`/`LYC` computed on read and the `STAT`
  interrupts;
- OAM DMA and the joypad register;
- MBC2 and MBC5;
- `instr_timing`, `mem_timing`, `halt_bug` and the Mooneye subset.

**Done when**
- Every listed test ROM passes in the raw harness.
- `tests/suite.py` carries the core rows in soak:
  - `gbcpu`: the core's correctness ROMs in the raw harness, in QEMU.
  - `gbtrace`: the differential trace against Peanut-GB.

### Wave 3 - the picture, and the package on the desktop

**BUILT** (REALBOY-SPEC sections 13 and 14). `gbwindow` holds dmg-acid2
pixel for pixel on MartyPC's VGA and Hercules. In the window on 86Box's 286
Super Mario Land plays at **59.5%** of real time with 6 frames drawn a
second (`tests/rbcore/rbwin.py`); the worker had been sleeping a tick it did
not have whenever it was behind (52% and 3 fps before that was found), and
it draws by the clock now, so a machine that is behind still shows a
picture. The Keys item and the 256 KB refusal's arena figure are not built.

**Features**
- The band renderer (section 4.4) and the windowed writers, `BLITP` on VGA
  and dithered `BLIT1` on 1bpp.
- The package shell on `apps/os88ui.inc`: open a `.GB` from the Standard File
  dialog or the Disk window (an `ASSOC.DAT` row), a Machine menu (Reset,
  Pause, Keys), and the About handler (SPEC.md 12.2).
- The guest claims, declared movable, with the relocation proc.
- The refusal of a ROM over 256 KB, with its size and the arena's on screen.
- The `F1` speed overlay.

**Done when**
- dmg-acid2 matches its reference **pixel for pixel**, read out of the
  harness's buffer and in a QEMU screenshot of the window.
- `gbwindow` boots a fetched homebrew ROM in the window on QEMU and on
  MartyPC, and reads frames advancing.

### Wave 4 - the fullscreen speed path

**BUILT, at 1x only** (REALBOY-SPEC section 15): VGA0D, DAC greys, the
`FSXF_RATE` clock and governor, the shadow compare and the restore.
`gbwindow`'s VGA arm is the gbfsx gate (the same reference through the
bracket, then back to the window) and `rbspeed286` the speed row. On
86Box's 286 full screen: **Super Mario Land 58.0%** of real time at 8 frames
drawn a second, **Kirby's Dream Land 37.5%** at 5 - after its spin-wait,
which the one-test rule missed, was found by sampling the Game Boy PC
(REALBOY-SPEC section 8). **What decides wave 7**: inside the bracket the
package's composer and VRAM writes are ~50 ms a drawn frame and the core
alone is ~78% of the machine at full speed on Super Mario Land, so no
governor setting reaches full speed with a picture. VGA12 at 2x is not
built.

**Features**
- The `OSAPI_FSX_RUN` bracket:
  - VGA0D at 1x as the default, and VGA12 at 2x as an option;
  - DAC palettes;
  - `FSXF_RATE` pacing and the frame-skip governor (section 4.5);
  - the shadow compare;
  - a clean return to the desktop.
- `kern_small` refuses `FSXF_RATE`, so that path falls back to the window.

**Done when**
- `gbfsx` passes on QEMU: enter, play N frames, leave with the desktop
  restored.
- On MartyPC's VGA XT (`os8088_xt_vga`) the frames are pixel-identical to the
  windowed composer's.
- **`rbspeed286` reads Super Mario Land's and Kirby's game speed and frame
  rate on 86Box `vm/286-525`** through `tools/os88box.py`. It SKIPS without
  `$OS88_GB_ROMS`, and quotes no$gmb's figure from the same machine beside
  each. The Victory 286's figures come from the overlay, and the report says
  so.

### Wave 5 - sound, save RAM, MBC3, polish

**The speaker voice is BUILT** (REALBOY-SPEC section 17), and `gbsound` is
its row. It plays the louder square channel, with envelopes, length counters
and the DAC switch tracked once a frame. Building it found that a budget
ending inside a HALT used to resume after the HALT (REALBOY-SPEC section 7),
and that the worker's draw clock compared unsigned. Between them they had the 8088 running
GBTONE at 3% of real time.

**Battery RAM and the MBC3 clock are BUILT** (REALBOY-SPEC sections 10.1
and 10.2), and `gbsave` is their row.
- RAM banking uses a window: the bank on view is copied out and in when a
  game switches.
- A battery's RAM is saved to `<game>.SAV` beside the game when the window
  closes, in VBA's format, with its clock trailer.
- The clock counts game time, and is caught up from the system clock when a
  save is opened.

None of the owner's three cartridges has RAM, so this is for the games that
do.

**Features**
- The speaker voice (section 4.5);
- OPL2 through `SOUND.DRV` if wave 4 left the cycles for it;
- battery RAM to `SYSTEM/APPDATA/`;
- MBC3 with its real-time clock;
- a key-map dialog.

**Done when**
- `gbsave` writes the save RAM, reboots and reads it back.
- The sound row asserts the tone stream, in the shape of
  `tests/covox.py`/`tests/vidsound.py`.

### The field run (wave 8's last row, and the first of wave 7)

**The emulators' numbers are in** (docs/reports/REALBOY-DAMAGE-2026-10-19.md):
- Super Mario Land is at full speed on 86Box's 286, in the window and full
  screen.
- Kirby's Dream Land is at 32-37%, bound by the Game Boy CPU.
- The demo is at 1.000 on MartyPC's 5150.

The owner's machines are next. They are what decides wave 7, since 86Box
times a 286 by its own model and not by the iron.

**What to run**, from `make realboydisk`'s floppy (the four geometries are
`build/realboy*.img`), with the owner's own `SML.GB` and `KIRBY.GB` copied
into its REALBOY folder:

1. **On the Victory 286, or a Compaq Portable III / PB286LP**, boot os8088
   and open REALBOY\SML.GB. Start the game, press F1, and walk right for 20
   seconds. Read the F1 line: the game's speed and the frames drawn a
   second. Do the same in Machine > Full Screen, then with Machine >
   Recompiler set Off, then the same four readings for KIRBY.GB.
2. **On the 5150 (Hercules)**, open REALBOY\GBDEMO.GB, take Machine > Full
   Screen, press F1, and read the line after a minute. The emulated figure
   is 100% at 4 frames a second, and the iron should read the same. If it
   does not, that is a finding about MartyPC.
3. **Anything that looks wrong**: the picture (a photograph), the speaker
   (the demo blips once a bounce), a save (a battery game's `.SAV` beside
   it), and Esc out of full screen.

The F1 line is the instrument because it needs no debugger. Both of its
numbers come off the machine's own clock.

### Wave 6 - ROMs over 256 KB (conditional)

**BUILT** (REALBOY-SPEC section 10.3), and it came in by the second field
run's door rather than the large ROMs': Kirby's Dream Land took the heap a
640KB Victory had, so its recompiler cache could not be claimed and it ran
interpreted. The plan now keeps the recompiler's 80KB (its cache and block
table) and sends a cartridge
that would not leave it to the cache. gbprof's LRU column measured the
working sets first, as this wave said it would: **Kirby 6 banks of 16, Looney
Tunes 8 of 64**, a fetch under once a second with that many slots. Looney
Tunes runs at 101% of real time in its window on 86Box's 286.

**Features**
- A bank cache in conventional memory over `XMEM.DRV`, sized from `gbprof`'s
  per-bank counts.
- Taken only if the owner wants the 512 KB and 1 MB titles.

### Wave 7 - the speed levers (conditional)

**Features**
- Section 5, in order, each one measured before the next is started.

#### Note: what the static-recompiler study found for the DYNAMIC one

The study (docs/reports/REALBOY-STATIC-2026-10-20.md, branch
`gameboy-static`) did not recommend a static recompiler. It did measure
where Super Mario Land's time goes while it scrolls with enemies on screen,
which is the 30-frames-a-second target. These are its findings for the
recompiler of REALBOY-SPEC section 16, best first.

The figures are on `vm/286-victory`, 16 MHz, the CPU alone in the bare
harness, at **6.55 ms a frame** recompiled. MEASURED and PREDICTED are as
in the report.

1. **Loop idioms, the largest lever. BUILT** (`add_ff` and `cpy_ff`,
   REALBOY-SPEC section 16.6): the frame 6.55 -> 6.22 ms, 3EF9's share
   measured at -0.23 ms and the copy pair's at -0.10 on the bench's own
   play. Three blocks that each jump to their
   own start are 17% of the machine over 12 s of play and 26% over the 3 s
   with most enemies (MEASURED, `rbprof --blocks`):
   - **3EF9**, `ADD HL,DE / DEC B / JR NZ,-4` with B = 32, a background-map
     row address. A closed form is HL += DE x B, B = 0, charged 6B - 1
     M-cycles. Its flags are dead, being overwritten two instructions
     later, but keep Z, N, H and C as the loop leaves them unless a
     lookahead (item 2) proves them dead. **The same result in 12 Game Boy
     bytes, patched into a scratch copy of the ROM, took the frame from 6.55
     to 6.22 ms** (MEASURED). That is about what the idiom buys.
   - **2CF0 and 2D02**, `LD A,(HL+) / LD (DE),A / INC DE / DEC B / JR NZ`
     and `LD A,(DE) / LD (HL+),A / ...`, a 13-byte copy of an enemy's slot
     between D100h + 16n and HRAM at FFC0h, out and back. One pass is ~33
     x86 instructions today: four compares for the read, four for the write,
     the store's guard and three SAHF/LAHF. The idiom is:
     - check once that [HL, HL+B) and [DE, DE+B) lie wholly in the fast
       regions (the write side in 8000-FEFF or FF80-FFFE);
     - copy, charged 10B - 1 M-cycles;
     - otherwise run the loop as now.

     **PREDICTED: 0.3-0.4 ms a frame on average and ~1 ms in a frame with
     enemies**, where the pair is 19% of the machine.
   - Take each only when BP covers the whole loop, as `cnt_ff` does
     (REALBOY-SPEC section 8.1). Then no event can fall inside it.
     `rt_jrt` already examines exactly this shape (a taken JR back to the
     block's own head) for the spin-wait.
2. **Flag liveness by lookahead at translate time.** Following the direct
   successors 16 Game Boy instructions past a flag write, through ROM,
   proves **35.4%** of Super Mario Land's 643 flag writes a frame dead. A
   whole-program analysis gets 38.8%, and the game in fact reads 57.5% of
   them (MEASURED, `tools/gbstatic.py`). Stop the walk at RET and JP HL.
   Kirby's Dream Land: 45.5% dead by the lookahead, 50.8% in fact.
   - A dead write drops its `LAHF`, its `OR AH,20h` or `AND AH,40h`, and an
     INC/DEC's `SAHF`.
   - A Z-only write followed in the block by its branch can branch on the
     host's own flags: 35% of writes are Z-only with that lookahead, 51% in
     fact.
   - PREDICTED: 0.15-0.2 ms a frame for all of it, at the measured ~1.7
     clocks a translated byte.
3. **Lookups and returns are 6.9% of the machine** (MEASURED): `tr_link`
   1.6%, `tr_rpatch` 1.1%, `tr_ekey` 1.9% and `tr_enter` 0.8%. Two places
   to look:
   - The RET cache's misses still patch in steady play. Super Mario Land
     makes 49 returns a frame, 2.5 of them not to the instruction after a
     CALL or RST.
   - `tr_ekey`/`tr_enter` run after events. Rbsys could resume an event's
     return straight into the translated code it left, instead of looking
     SI up again.
4. **Fall-through layout.** 34% of Super Mario Land's 364 conditional
   transfers a frame fall through (MEASURED). Today each one ends a block
   with `sub bp / js / jmp` to the next. A superblock that continues
   through the not-taken side saves the jump and its prefetch refill there.
   That is PREDICTED at ~0.1 ms.
5. **Pointer-region proofs are not worth chasing.** Constant propagation
   proves the region of only 9% of Super Mario Land's (HL)/(DE)/(BC)
   accesses, whether one block or whole functions are analysed
   (MEASURED). A pointer comes from memory or walks through a loop.
6. **A correction for whoever prices the core.** RealBoy runs **2,039** busy
   instructions a frame of Super Mario Land, not gbprof's 1,747, which
   skips every short loop that writes nothing. 3EF9 is one of those loops,
   and RealBoy runs it. Use `tools/gbprof/gbcover.c`'s count (REALBOY-SPEC
   section 8's rules).

#### Note: what other Game Boy emulators do that RealBoy does not

**Where this comes from.** A survey on 2026-10-20 of emulators that run on
slow hosts or are known for speed. Each source was read at the commit given
and file:line references are into it; nothing was built or run:
- **TI-Boy SE**, calc84maniac/tiboyse 105bf35: a Z80 calculator running the
  Game Boy's near-Z80;
- **Goomba Color**, Dwedit/goombacolor 35c3ffd: a 16.78 MHz ARM, full
  speed;
- **jitboy**, sysprog21/jitboy 418d1c5: an x86-64 dynamic recompiler;
- **gnuboy**, rofl0r/gnuboy 4c2f6c4;
- **CrankBoy** (Playdate), CrankBoyHQ/crankboy-app 3aab67f, plus Peanut-GB,
  RP2040-GB, mGBA, Gambatte, SameBoy and GameYob (Nintendo DS).

The proxy blocked no$gmb's, gbdev's and the Playdate forum's pages, so
nothing here rests on them.

**Neither Goomba Color nor TI-Boy SE has a recompiler.** Both reach their
speed with a lean interpreter and by SKIPPING work. That is where most of
what follows points. Items are ranked for 30 frames drawn a second while
Super Mario Land scrolls with enemies on screen.

1. **Skip STAT and LY polling loops exactly.** Four emulators do this:
   - **Goomba Color** (`LCD_HACKS_ACCURATE`): it matches the loop shape at
     the STAT read, caches the verdict per PC, and advances the clock a whole
     number of loop passes to the wanted mode (`src/lcd.s:3572-3770, 3839,
     3911`), or to the line's end for an LY wait (`:4344`).
   - **CrankBoy's "HLE warp"**: it decides at the read and idles to the next
     mode or LY change (`libs/peanut_gb.h:1771-1868, 2391`;
     `libs/peanut_gb_core.h:2176-2238`).
   - **jitboy**: it rewrites the shapes into a special HALT (`optimize.c:123-149`).
   - **TI-Boy SE**: it fast-forwards a recorded wait loop
     (`hardware.z80:830-1075`).

   RealBoy refuses any register read in a spin-wait on purpose. Its rule
   (REALBOY-SPEC section 8) is that LY and STAT change on their own, and
   `idle_chk`/`rt_idle` reject `LDH` with n < 80h.

   **MEASURED on Super Mario Land:** all of its ~20 STAT reads a frame are
   one shape, `LDH A,(41) / AND 3 / JR NZ,-6`, a wait for HBlank before a
   VRAM write, at 0156h, 0097h and 015Dh. `io_lcd` is 5.4% of the machine
   and those blocks are another ~4%.

   RealBoy can do this EXACTLY, because LY and STAT are a function of
   `S_TNF - BP`. When the shape is recognised and the mode is not yet the
   wanted one:
   - take BP down by whole passes up to the mode boundary, capped at the
     next event, keeping the loop's phase;
   - then let it run once more to read the mode.

   **Make the read itself cheaper too.** Today a translated `LDH A,(41h)`
   goes by its slow stub to `rd_sN`, `rw_io` and `io_rd`'s compares before it
   reaches `io_lcd`'s subtract-and-wrap loop and `div`. Two fixes:
   - a `rbgen.EXTRA` template for `LDH A,(41h)` and `LDH A,(44h)` that enters
     `io_lcd` directly (gnuboy's agent's suggestion);
   - keeping the current line's start, so that a read in the same line is a
     subtract and a compare (Goomba Color reads STAT in two compares,
     `lcd.s:3533`).

   **PREDICTED: most of that ~9%.**

2. **Loop idioms, generalised.** This is item 1 of the note above, with the
   evidence that others take it:
   - **Goomba Color** collapses known loops per game (`src/gamespecific.s:6-26,
     589-640`); its own comment credits one with "+13 FPS".
   - **jitboy** classifies self-loops by what they touch (`optimize.c:6-91,
     166-246`) and fuses `LD A,(HL+) / LD (DE),A / INC DE` into one copy
     (`:110-121`), unsafely, with no range check.

   **Two refinements over the note above:**
   - When BP does not cover the whole loop, run `k = min(n, BP / period)`
     passes in one step and leave PC at the head. That stays exact without
     giving up the shortcut.
   - Fuse a copy idiom with one range check even when it is unrolled rather
     than a loop.

3. **Blocks that run on through a conditional branch** (jitboy: a branch is
   `jz >1 / <exit> / 1:` and translation continues, `emit.dasc:105-118`;
   blocks end only at unconditional transfers, `gbz80.c:582`).
   - **Where the bytes go.** The taken side goes to an out-of-line stub at
     the block's end, which flushes the pending M-cycles, checks BP and
     chains as `rt_exit` does. The fall-through keeps accumulating cycles,
     with a not-taken `sub bp,n / js` kept to stay exact.
   - **Why.** REALBOY-SPEC section 16.7 already blames short blocks for
     Kirby's Dream Land (`tr_enter` 11%).
   - **The risk** is duplicated code in a cache that already binds. Cap the
     side exits per block.

4. **Carry the pending M-cycles through memory templates** (jitboy writes
   its cycle sum only at exits, `emit.dasc:142, 258`). Today `rt_flushbp`
   runs before every memory template, because all of them are impure. But:
   - a RAM fast path and the ROMX reads `rd_s1`-`rd_s3` answer never read
     the time;
   - only `rw_io` and an MBC write need BP exact.

   So the slow stub can take the pending count off BP itself, found by a
   small table the translator keeps, keyed by the stub's `S_RET`. That saves
   ~3 bytes a memory instruction. The self-guarded stores and `rb_irqnow`
   must still see the right BP.

5. **Index the lookup directly by PC.**
   - **Who does it.** jitboy looks a block up as `compiled_blocks[bank][pc]`
     (`core.h:416`); TI-Boy SE's PC is the host pointer, so a jump costs no
     lookup.
   - **For RealBoy.** A 32 KB word table for bank 0 (one word a Game Boy
     byte) would take `tr_enter`, `tr_link` and an event's resume to
     `shl bx,1 / jmp [es:bx]`, with no key compare and no neighbour probe.
     Lookup and the RET cache's misses are 6.9% of the machine today.
   - **Cost.** 32 KB of heap, plus 32 KB for each hot ROMX bank if those
     are done too.

6. **A persistent background image for scrolling** (Goomba Color: dirty
   bits on VRAM writes, `lcd.s:4597-4627`; only dirty tiles and map cells
   converted at VBlank, `:822, 2376`).
   - **The VGA equivalent.** Keep the 256x256 background as two shade
     planes, 32 bytes a row and 16 KB in all, updated only for the cells
     `rb_renderd`'s scan finds changed. A scrolled frame's background is
     then, per line, 21 words per plane read at `(SCY+L)&255`, from byte
     `SCX>>3` (wrapping at 32), shifted by `SCX&7`.
   - **What it removes** is the map and tile lookups from today's whole
     recomposition of a scrolling frame, ~18 ms on the Victory twin. That
     is UNMEASURED; the agent guessed a few ms.
   - **What it needs.** The scan, skipped today while scrolling
     (`RB_DSTALE`), would have to run over at least the 2 KB of map to keep
     the image current.
   - **VGA hardware scrolling is rejected** by three of the surveys: a
     CRTC start address plus pel panning cannot keep Super Mario Land's
     status bar, which is at the TOP, because line compare fixes only the
     part of the screen below the split.
   - **It was built anyway, and refused on the glass** (REALBOY-SPEC
     15.3): the surveys were right about the status bar. A draw is longer
     than a refresh, so what it recomposes was shown at the wrong origin
     until the card latched the new one, and the flip that cures it waits
     for a retrace every draw - more than the 4% it saved Super Mario Land.
   - **The owner's form of it was MEASURED, and not built** (2026-10-20:
     "a 5% win is another 5% win if it pans out - they stack up into
     playability"). A background wider than the screen in RAM, the newly
     showing edge composed into it, each line's background copied from it
     at the scroll's offset and wrapping at its end - and the game's own
     map is already exactly that buffer, 256 wide and wrapping, so the
     image is the map's and wide in both directions for free.
   - **What it would cost is the scan.** The image has to be kept current
     on every scrolled frame, which `rb_renderd` skips there today: **+2.4
     ms a scrolled frame in Super Mario Land**, against ~1.5-2 ms of
     lookups taken away (`ppu_list` and the tile-address load before each
     tile row; the shift stays, the card cannot do it for free). A net loss
     for Super Mario Land, ~5% for Kirby's Dream Land at best. (STALE: the
     figure predates the write marks - see the scroll round below.)
   - **What the measurement found instead, and took** (REALBOY-SPEC 13.3):
     the still frame after a scroll COMPARED rather than composed whole
     (Kirby's Dream Land -3.8%), and a line that is one tile all along
     filled from its one tile row (Super Mario Land **-6.8%**, 44% of its
     playfield lines). The same fill a segment at a time - runs of one
     tile inside a mixed line - was built and refused: both games slower.
   - **A status bar is a line of its own** (its own scroll): composed as
     today, not from the image.

7. **Drop a raster-register write that changes nothing** (gnuboy
   `lcd.c:820`, `mem.c:139-151`; Goomba Color `lcd.s:4086-4093`).
   - **BUILT in the recompiler's `io_wr`** (`rbgen.py`): a write to
     FF40-FF4B of what is there stops before the far trip to rbsys, so
     `rb_rlog` never logs it and `ppu_logsame`'s FAST frame survives; DMA
     always runs. Kirby's Dream Land 11.08 -> 10.76 ms a frame (the CPU and
     `rb_renderd`), Super Mario Land level.
   - **The interpreter's `rb_iowrite` was measured and left alone**: the
     same compare there reads level on `286-victory` with the recompiler
     off (Super Mario Land 561 ticks either way, Kirby's Dream Land 1,248
     -> 1,250), the far trip and `rb_now` costing what the log would.

8. **The recompile stall.** No emulator surveyed forgets its whole cache and
   re-counts:
   - jitboy translates a block on its first entry and never flushes
     (`core.c:123-127`);
   - Goomba Color and TI-Boy SE never translate, and cold code just runs
     interpreted at a steady speed.

   **Two hypotheses to check before redesigning:**
   - (a) whole flushes followed by bursts of translation: plot `S_JITFL`
     and `S_JITNB` per second against the slow periods;
   - (b) Auto's timing windows (REALBOY-SPEC section 16.7): 2 s untimed plus
     four of 2 s, half of them interpreted. That is a 10 s cycle, though it
     repeats only every 1-5 minutes.

   If it is (a), what the survey argues for is a budget of translations a
   frame, or a flush of the oldest part of the cache, not forgetting
   everything.

**What came of it** (measured on `286-victory`, 2026-10-20):
- **1, BUILT** as `stat_ff` (REALBOY-SPEC section 16.6): Super Mario Land's
  CPU alone 6.22 -> 6.13 ms a frame, short of the predicted ~9% because
  the waits are short; what is left is the reads themselves. The direct
  template for `LDH A,(41h)` is NOT built: a translated `LDH A,(n)` with n
  < 80h already jumps straight to `io_rd`, whose first test is 41h, so it
  would save two compares.
- **7, BUILT** in `io_wr` (REALBOY-SPEC section 16.6's neighbour, the core
  tail itself): Kirby's Dream Land's CPU and `rb_renderd` every frame 11.08
  -> 10.76 ms; Super Mario Land unchanged.
- **8**: hypothesis (b) was the field run's - Auto timed the level start's
  translating and chose the interpreter for Super Mario Land. Auto re-runs
  such a window now; the fourth field run then showed Auto's timing itself
  to be the slowdown, so the default is Recompiler: On and Auto only times
  a thrashing cache (REALBOY-SPEC section 16.7). `RB_JITHOT` 16 was tried
  and refused in the field (section 16.3). Kirby's Dream Land still flushes every ~25 seconds, and a block
  table of 4,096 entries made it WORSE (1,872 blocks and 3 flushes in 50 s
  against 1,321 and 2): its code over a minute is simply bigger than the
  64KB cache, so the levers are smaller blocks (a memory template is 38-64
  bytes against 4-12 for a register operation) or more cache.
- **6, set aside**: `rb_renderd` on Super Mario Land spends 13.6% in
  `ppu_fshift` and 2.5% in `ppu_list`, already unrolled and cached by map
  row; the image would take only the tile's indirection out of that, and
  add the map's scan to the scroll that skips the scan today. `ppu_dscan`
  is the larger item (15.6%) on frames that do not scroll.

**Looked at and rejected for a 286:**
- **TI-Boy SE's PC as the host SP** (fetch by `pop`). Its interrupt repair
  depends on a Z80 interrupt pushing exactly the 2 bytes just popped.
- **Updating LY, STAT and the timers eagerly each line** (TI-Boy SE,
  gnuboy). That is 154 or more events a frame against RealBoy's sparse
  scheduler.
- **gnuboy's decoded-tile cache.** Game Boy tiles are already planar.
- **Shrinking the core to fit a cache** (CrankBoy, for the Playdate's
  ITCM). A 286 has no cache.
- **jitboy's register load and store at every block, its C calls for
  writes, and its per-pixel renderer.**

### Static - the recompiler run before the game (a wave 7 lever, BUILT)

**BUILT** (REALBOY-SPEC section 16.8), on branch `gameboy-static`. The
owner's call: the dynamic recompiler slows the game for seconds whenever it
translates or flushes, and no fix for that was in sight on the dynamic side.
docs/reports/REALBOY-STATIC-2026-10-20.md had found a static recompiler
feasible but not worth building for SPEED; the stall is what made it worth
building.

**What it is.**
- **No second code generator.** Machine > Recompiler: Static runs the
  dynamic recompiler's own translator over a PROFILE before the game runs,
  then fixes the block table.
- **The profile** is every block the recompiler translated in the game's
  earlier sessions, kept beside the game as `NAME.RBP`.
- **The fallback is the interpreter.** Two caches would not fit a 640KB
  machine's heap beside the ROM, so the memory is the recompiler's own 80KB
  plus the profile's 9KB.

**What it does, MEASURED on `vm/286-victory`:**
- **Super Mario Land**, the profile from an earlier session's 30 s:
  - 437 blocks preloaded;
  - 97-105% of real time EVERY second over 40 s, 26 pictures a second;
  - nothing translated, nothing flushed.
- **Kirby's Dream Land:** more code than the 64KB cache in 45 s of play.
  Static is steady at 85% where the dynamic recompiler settles at ~100%
  after its first seconds' slump, so On stays the setting for it.

**Found on the way:**
- File > Close had never saved a battery's RAM (REALBOY-SPEC section 10.1).
- Two ways to weigh a block by heat were built and refused (16.8): events
  and budget ends both fall where the game waits.

**Then, on the same branch (REALBOY-SPEC 16.2.1, 14.1, 16.8):**
- **A second 64KB cache segment**, claimed by need: when the game's
  profile names more blocks than one segment holds, or Machine > Cache:
  128K says so (a setting, in `SYSTEM\APPDATA\REALBOY.CFG`). It was not
  protected mode after all: a block's segment went into the block table's
  spare word, and the exits and RET caches grew by 2 bytes each so a far
  jump fits. Kirby's Dream Land, measured on `286-victory`:
  - Static, 655 blocks preloaded: 100.0% of real time, 24 pictures a
    second (85.1% and 12 with one segment);
  - the dynamic recompiler: 98.2%, no flush in 40 s (94.3% and a 47-57%
    slump at the flush with one), for 3 bank slots of 11.
- **Machine > Profile** (Off by default): the 9KB claim and the close's
  `.RBP` write only when asked for, or when the game has a profile.
- **The log's 4KB of records** became a claim taken when the log is on.

**Open:**
- A field run on the Victory.
- Why a profile that missed a transition stalls Static there harder than
  the interpreter would (REALBOY-SPEC 16.8).

### The scroll round - research, the field probe, and the plan (2026-10-21)

The owner's brief: scrolling is the last major blocker; several approaches
"came out roughly equal and were marked as refused", and some of those may
have been the MACHINERY rather than the idea. Five agents re-priced them
on `286-victory` (the bare harness, 1,200 frames of play; baseline Super
Mario Land 18.72 ms a frame, Kirby's Dream Land 39.27 ms, every frame
composed). The ceiling is a scrolled frame composing NOTHING: 9.0 / 17.8
ms. Findings:

- **The "+2.4 ms scan" that refused lever 6 is stale.** It was taken
  before REALBOY-SPEC 13.2.2's write marks; with them the VRAM part of a
  scrolled frame's scan is ~0.1 ms. What was left was OAM: a scroll moves
  every sprite's X, and each differing entry marked 32 lines nothing reads
  (1,280 marks a frame). Copying the OAM shadow whole on a scroll instead
  measured Super Mario Land +2 ticks, Kirby's Dream Land **-4.9%**. A list
  of marked blocks filled by `vr_wr` makes the scan proportional to what
  was written - in play one 16-byte block a frame, and not one tile write.
- **The CRTC experiment (REALBOY-SPEC 15.3) measured its machinery.** It
  had one page, composed sprite lines whole, recomposed the status bar
  every draw, scanned 8KB every call and shifted every line twice
  (composed screen-aligned, then shifted again for the panning): ~32% of
  its samples. Commander Keen's adaptive tile refresh - floating pages in
  a 64KB ring, a master page, an update matrix per page, latch-copy
  erase, the status bar a sprite - is the period answer, and it is not
  what was built.
- **The ~7 ms retrace wait is not a property of page flipping.** The
  field probe (`tests/vgaprobe/`, the Victory's PVGA1A) settled where a
  start address and a pel panning written together land on one frame:
  **after the last line of the page being flipped and before vertical
  blanking starts**. The chip applies the panning LIVE (a write during
  display tears below that line; one after blanking starts shifts the
  whole next frame) - the strictest of the three models, so the window
  is generic: 86Box and the IBM VGA as QEMU describes it are consistent
  there too. In RealBoy's timing, with a line-compare split 32 lines
  above the display's end (line 275), it was stable from 11.46 to
  13.92 ms after vsync start (the split at 11.38, blanking at 14.08);
  with no split it ends at the display's end. AR10 bit 5 (PPM) only
  stops the region below the split panning (the WD90C00 datasheet: a
  line compare disables the panning "until VSYNC occurs"). The address
  wraps at 64KB. So: THREE pages and a timer hook that writes the flip
  in that window, never a wait.
- **Motion reuse of the last frame's lines was built and refused**:
  correct (`gbdamage` 12/12) and +17% on Super Mario Land - moving a line
  costs what composing it costs, ~70-90 us on the 286. Pre-shifted phase
  images: 32-128KB, refused on memory. The VGA retrace interrupt: not in
  86Box, varies by clone. Not generic.

The plan, in order:

1. **The composer's scrolled frame made cheaper** - BUILT (REALBOY-SPEC
   13.3, the scroll round): -10.0% / -5.8%, frame-identical.
2. **The scan kept current while scrolling** - BUILT (REALBOY-SPEC 13.3):
   the OAM shadow taken whole on a scroll, `ppu_dlines` as one clipped
   fill, the marked-block list. Kirby's Dream Land -5.9%.
3. **The no-wait three-page flip, and lines composed aligned to the
   panning** - BUILT (REALBOY-SPEC 15.4): estimated Kirby's Dream Land
   -7-9% and Super Mario Land -2-3%, measured -2.4% and -1.0% on 86Box,
   which does not price the shifts it removes. Two of the design's
   assumptions were wrong: the flip cannot be a hook's, because the core
   runs with interrupts off for milliseconds (a 9x rate lost a quarter of
   its periods and slowed the game to 77%), so the foreground writes it
   between core runs; and the line type has to be judged once a register
   changes rather than every line, or it eats the gain.
4. **The torus canvas**: the whole 256x256 background in VRAM, three
   pages, scrolled by the start address and panning; only the newly
   exposed cells, the sprites and the status bar drawn. ESTIMATED Super
   Mario Land 20.3 -> ~10-11.5 ms on the card, Kirby's Dream Land 42.8 ->
   ~22-24. VGA only; animated tiles and raster effects fall back to the
   copying writer.

### Wave 8 - the 5150 demo, disks and the Wire record

**The writers and damage tracking are BUILT** (REALBOY-SPEC sections 13.2
and 15.1). The damage is tracked at the line, not the tile: `rb_renderd`
compares VRAM and OAM against a shadow at each draw and composes only the
lines whose inputs changed, and the Hercules and CGA writers put only those
lines on the page. It is exact against `rb_render`, frame for frame
(`gbdamage`), and the window's monochrome path uses it too. On MartyPC's
5150 in a Hercules window, gbclock's do-nothing variant went from 43% of
real time to **100%**. The drawing, not the CPU, had been most of the
machine, which is section 6's prediction: the fixed cost decides the 5150.

**The demo is BUILT and meets the bar** (REALBOY-SPEC section 18).
`GBDEMO.GB` (ours, `tools/gbprof/gbdemo.asm`) runs full screen on MartyPC's
5150 Hercules at **1.000 of real time**, drawing 4 frames a second; `gbdemo`
is the row. The last piece was the draw clock, not the core: a draw is due
only after as long as the last one took (REALBOY-SPEC section 15.2), so the
picture can never take more than half the machine.
- Without that clock the game ran at 0.39 in full screen and 0.84 in the
  window.
- With it, the machine's spare time shows up as frames drawn instead of as
  lost game time.

The libbet curiosity row is not built.

**Features**
- The HERC and CGA320 fullscreen writers with damage tracking.
- The demo ROM's source and its rgbds build (section 6).
- The package on an on-demand floppy in all four geometries (CLAUDE.md,
  Package pipeline), on `allapps` and on the live media (`t_livefull`'s
  sweep).
- `README.TXT` and `COPYING` for every third-party file it carries.
- A Wire record at **tier 1 (286)**.

**Done when**
- `gbdemo` on MartyPC `os8088_5150_herc_gla` reads game frames equal to wall
  frames (ratio 1.00) over 60 seconds.
- The curiosity row reports libbet's ratio on the same machine.

## 9. Risks

- **The interpreter estimate is a hand count, and the last one in this tree
  was out by six.** Wave 1 measures before anything is built on it, and the
  gate in wave 1 reorders the waves if the number is bad. The workload side
  is MEASURED, so only the per-instruction cost is open.
- **The 286 is timed by an emulator that is not cycle-accurate.** 86Box
  models the 286 per instruction (docs/86BOX.md, *What it is NOT*). Its
  figures are a consistent ruler, which is what comparing against no$gmb on
  the same machine needs, but they are not the iron. The Victory 286 is the
  check, and MartyPC's exact 8088 counts are the automated regression guard.
- **The best period implementation sets the bar at 2.2-2.9 times RealBoy's
  predicted cost.** no$gmb's XT/AT build is ~58 clocks per M-cycle on the 286
  (MEASURED), and section 2.2 needs 20-26. If wave 1 lands nearer no$gmb than
  the prediction, the plan is a recompiler's (wave 7) or a smaller game set.
- **The real Victory 286 is slower than 86Box's.** Its RAM runs at about 2.5x
  the cost of 86Box's mr286 (docs/reports/VIDBENCH-PVGA286-2026-10-08.md),
  and its decode is 12-29% slower. An interpreter is memory-heavy, so the
  field figure may land below the 86Box one. Read both and quote both.
- **Mid-frame effects beyond a status bar.** Per-line wave effects and
  `STAT`-interrupt rasters mean bands one line tall, and the renderer then
  costs more per frame. The register log makes that correct, not fast.
  Super Mario Land needs one split a frame (MEASURED); a game with 144 needs
  measuring.
- **Accuracy against speed.** A Mooneye suite that passes completely costs
  per-M-cycle PPU timing, which this design does not do. The bar is
  Blargg's CPU and timing ROMs, dmg-acid2 and the PPU-mode subset of Mooneye.
  The rest is recorded as not attempted rather than failed.
- **The 256 KB ceiling.** Many well-known titles are larger: Link's
  Awakening is 512 KB, Pokemon Red/Blue 1 MB. Version 1 refuses them by name
  with the arithmetic, and wave 6 exists for them.
- **Trademark.** The package is RealBoy (section 3.1). "Game Boy" appears
  in its documentation only as the name of the machine it emulates.

## 10. What is in this PR (wave 0)

- docs/reports/GAMEBOY-FEASIBILITY-2026-10-19.md: the 5150 question,
  PREDICTED.
- docs/reports/GAMEBOY-WORKLOAD-2026-10-19.md: busy shares and event rates
  for Super Mario Land, libbet and a control, MEASURED on the host.
- docs/reports/GAMEBOY-NOGMB-2026-10-19.md: no$gmb's XT/AT build timed on
  MartyPC's 8088 and 86Box's 12.5 MHz 286, and Kirby's and Looney Tunes'
  workloads, MEASURED.
- `tools/gbprof.py` and `tools/gbprof/gbprof.c`: the workload instrument.
  Peanut-GB is fetched at a pinned commit into `build/gbprof/`, and no ROM is
  committed.
- `tools/gbclock.py` and `tools/gbprof/gbclock.asm`: gbclock, our counting
  ROM, with rgbds fetched at a pinned commit into `build/rgbds/`.
- `tools/gbcal.py`: a DOS Game Boy emulator timed on 86Box or MartyPC.
- `tools/os88box.py`, `tools/86box/`, `tools/os88bochs.py`,
  `tools/os88bochsui.py`, docs/86BOX.md and docs/BOCHS.md: the 86Box and
  Bochs harness, brought over from the `protected-mode` branch.
- This plan.
