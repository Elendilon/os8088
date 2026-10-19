# Game Boy emulator - full speed on a 12 MHz 286, a demo on the 5150

**A PLAN. Nothing in it is built.** It is the design and the order of work
for a native os8088 package that runs original Game Boy (DMG) cartridges.
When the work starts, the contract will be `docs/GAMEBOY-SPEC.md`, written in
wave 1. This file stays the record of why the design reads that way.

**Every figure is marked.**
- **MEASURED** figures cite the report they come from.
- **PREDICTED** figures are hand counts from the 8088 and 80286 data-book
  timings.

The last attempt in this tree to predict an emulator's speed by hand, the
Apple II plan, was optimistic by six times (docs/APPLE2-SPEC.md, its speed
section). So the first wave measures before anything else is built on these
numbers.

## 1. The intake

The owner asked:

> Investigate a gameboy emulator, for a 4.77Mhz 5150. Is that feasible?

Two reports answer that:

- docs/reports/GAMEBOY-FEASIBILITY-2026-10-19.md (PREDICTED). Full speed is
  out of the 5150's reach. The 8088's bus moves only about 1.14 bytes for
  every Game Boy bus access, so even a perfect translator would land near half
  speed on busy code.
- docs/reports/GAMEBOY-WORKLOAD-2026-10-19.md (MEASURED on the host with
  `tools/gbprof.py`). How much of each frame a real game's CPU spends on work
  an emulator cannot skip:
  - **Super Mario Land: 23.3%** (p90 39.6%, p99 50.5%), about 2,150
    instructions a frame;
  - **libbet: 13.7%**, about 1,170 instructions a frame.

Then the owner retargeted the work:

> We'll retarget the primary goal to a ~12Mhz 286, and keep "some very light
> gameboy demo that sits in hlt most of the time" as a final wave to show off
> on the 5150.

**The reference set** was used for reading. None of it is a code base the
port derives from:
- Peanut-GB (MIT), the profiler's host core;
- Pan Docs and the gbdev community documentation, for hardware behaviour;
- Blargg's test ROMs, Mooneye's test suite and dmg-acid2, as fetched gates
  (section 7).

**Prior art.** There is no Game Boy emulator for a 286 that a search turns
up, with one exception:
- **no$gmb**'s "Special DOS XT/AT compatible version" (Martin Korth, assembly,
  1997-2000) exists in the Internet Archive.
- This container's network policy refuses that archive, so it has not been
  read or run.
- **A field run of it on the 5150 and on the 286 with a homebrew ROM is the
  cheapest calibration this plan can get**, and it is asked for in wave 1.
- Every other DOS Game Boy emulator found asks for a 386DX-33 (no$gmb's own
  386 build) or a Pentium (GaelCathelin's Game-Boy-DOS, DJGPP).

## 2. Why a 286 and not a 5150

| | 5150, 8088 at 4.77 MHz | ami286 at 12.5 MHz (`vm/286`) | Victory 286, 16 MHz (the owner's) |
|---|---|---|---|
| clocks per Game Boy frame (59.73 Hz) | 79,909 | **209,284** | 267,884 |
| clocks per Game Boy M-cycle | 4.3 (after refresh) | **11.9** | 15.3 |
| memory bus | 8-bit, 4 clocks a byte | 16-bit, 2 clocks a word | 16-bit, with wait states 86Box does not model |
| VGA writes | - | - | **1.15 us a byte** (`rep movsb` to mode 12h, MEASURED, docs/reports/VM3BENCH-PVGA286-2026-10-13.md) |
| against a 5150 | 1x | - | **~20x on RAM copies, ~4.6x on screen writes** (MEASURED on 86Box mr286, docs/reports/VIDEO-86BOX-286-2026-09-26.md) |

**The CPU budget, PREDICTED.** The interpreter in section 4.1 costs:
- on an 8088: about 80-100 clocks per average Game Boy instruction;
- on an 80286: about **45-60 clocks**, its 16-bit bus and cheaper jumps
  doing most of the work.

Super Mario Land's 2,153 busy instructions a frame then cost:

| | ami286 at 12.5 MHz | 5150 |
|---|---|---|
| average frame | **46-62% of the frame** | 2.2-2.7 times the frame |
| p90 frame | 79-105% | - |

libbet's 1,167 instructions are 25-33% on the ami286 and 1.2-1.5 times the
frame on the 5150.

**So the 286 carries an ordinary game's logic at full speed, with between a
third and a half of the machine left for the picture.** The 5150 cannot carry
either game. It can carry a program written to be idle (section 6, wave 8).

**"Full speed" in this plan means GAME speed**: the cartridge's logic, timers
and music run at 59.73 Hz. The display drops frames when it must. That is how
every period emulator was measured, and it is the only definition the
arithmetic supports. A full 60 frames a second is a stretch figure (section
5).

## 3. Decisions

### 3.1 The owner's, taken at intake

- **Primary target: a ~12 MHz 286 with VGA.** The tree's machine is `vm/286`
  (ami286, 12.5 MHz, OTI067), and the field machine is the Victory 286.
- **Final wave: a very light demo on the 5150** that sits in `HALT` most of
  the time.
- **Assembly is allowed**, and Peanut-GB is a reference, not a base.

### 3.2 Recommended, for the owner to confirm before wave 1

1. **Pure NASM, not a C shell.** The tree's other emulators are C packages
   with hand-written assembly cores (SPEC.md 73; `apps/apple2`, `apps/c64`).
   Here the core, the memory map and the renderer are all assembly anyway.
   What C would add is the shell, and `apps/os88ui.inc` already supplies
   that to every native package. Pure NASM drops the SmallerC dependency and
   C's four extra rules, and leaves one build.
2. **The core is 8086 code. No `cpu 286` island.** SPEC.md 1 rule 1 is
   "8086 only", and no 286 island exists anywhere in the tree. The
   interpreter gains little from 286 instructions: `shl reg,imm` and
   `push imm` are the only ones it would reach for. And the **same core is
   what wave 8 runs on the 5150**. If wave 1's measurement says a 286 island
   would pay, that is a written exception to rule 1, decided then on a
   number.
3. **The package name.** The working name here is `apps/gameboy/`. Other
   packages in the tree carry the machine's name (`APPLE2`, `C64`), but "Game
   Boy" is Nintendo's trademark, and something like `GB88` or `DMG88` may be
   preferred. The owner's call.
4. **The demo for the 5150.** Recommended: **a demo of our own**, its source
   committed and assembled at build time by rgbds, which would be fetched and
   built at a pinned commit the way `tools/setup-cc.sh` does SmallerC, and
   never committed. libbet (zlib) is the alternative: it is measured at 13.7%
   busy, which is too heavy for full speed on the 5150 (section 2).
5. **No boot ROM.** The DMG boot ROM is Nintendo's. The core starts at
   `$0100` with the documented post-boot register and I/O state, as every
   homebrew-friendly emulator does.

### 3.3 Fall-outs, recorded so they are not re-opened

- **No cartridge ROM is ever committed or shipped.** The user supplies their
  own. The gates use fetched, freely licensed test ROMs at pinned SHA-256s
  (`tools/getapple2rom.py`'s shape). A commercial ROM is used only from a path
  the user gives (`$OS88_GB_ROMS`), and a row that needs one SKIPS without it
  and says so.
- **Banking is a page-table write, never a copy** (section 4.2). The workload
  report measures Super Mario Land at 7.8 MBC writes a frame.
- **Register writes are logged with their line**, and the frame is drawn in
  bands between them (section 4.4). The status bar in Super Mario Land
  depends on it.
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
2. **Idle-loop recognition.** A short backward loop that re-reads one address
   and writes nothing skips to the next event. It is 0.9% of Super Mario
   Land's frame and 0.2-3% elsewhere, so it is cheap to add and is the
   last few percent, not a rescue.
3. **Hardware panning for a scrolled background.** The attribute controller's
   pixel panning plus the CRTC start address would replace the composer's
   fine-scroll shifts. Its cost is the mid-frame split a status bar needs.
   Priced in wave 3, not before.
4. **A dynamic recompiler.** It would cut the CPU term about 2x (the
   feasibility report, section 4.2), and it is the largest and riskiest item
   in this list. It is wave 7, and it is conditional.

## 6. The 5150 demo

What the 5150 has room for, PREDICTED:
- **The CPU budget is ~600-800 interpreted instructions a frame with nothing
  drawn.** That is about 79,900 clocks at ~90-130 clocks per instruction.
- **The demo should stay under ~250 busy instructions a frame**, about 3% of
  a frame's CPU. That leaves about two thirds of the machine for the picture.

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
- **The 286's speed is read off the glass.** The package draws its own
  measured game speed and frame rate (an `F1` overlay, timed by PIT). It is
  read on 86Box `vm/286` by a person, and on the Victory 286 in the field
  (docs/FIELD-MACHINES.md). No row can gate on it, so every 286 figure
  quoted later names which machine it came from.

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
| 0 | Investigation: feasibility, workload, `gbprof` | **yes, done** |
| 1 | The contract, the core and the measurement that decides the rest | |
| 2 | The machine: timers, interrupts, PPU timing, MBCs | |
| 3 | The picture, and the package on the desktop | |
| 4 | The fullscreen speed path on VGA | |
| 5 | Sound, save RAM, MBC3, polish | |
| 6 | ROMs over 256 KB (bank cache) | conditional |
| 7 | The speed levers (section 5) | conditional |
| 8 | The 5150 demo, disks, Wire record | |

### Wave 1 - the contract, the core, and the measurement that decides the rest

**Features**
- `docs/GAMEBOY-SPEC.md`: its own contract, cited as "section N".
- The SM83 interpreter (section 4.1) with the minimal machine `cpu_instrs`
  needs: ROM-only and MBC1, the serial port as text output, `DIV`/`TIMA`,
  interrupts and `HALT`.
- A raw-QEMU harness that runs a ROM headless and captures the serial output,
  `apps/apple2/a2memtest.asm`'s shape.
- `tools/getgbtest.py`.
- A bench build that runs a fixed ROM for a fixed number of frames, then
  prints clocks per instruction: from MartyPC's cycle counter on the 8088,
  and from the PIT on any machine.

**Files**
- `apps/gameboy/gbcpu.inc`, `gbmem.inc`;
- `tests/gbcore/` (harness, bench);
- `tools/getgbtest.py`, `tools/gbtrace.py`;
- `docs/GAMEBOY-SPEC.md`.

**Done when**
- `cpu_instrs` prints `Passed all tests` in the raw harness.
- The differential trace agrees with Peanut-GB over the first 10 million
  instructions of `cpu_instrs`.
- **A report carries the measured clocks per instruction on MartyPC's 8088,
  and the same bench read off 86Box `vm/286`.**

**The gate on the rest.** On the ami286, section 2 predicts 45-60 clocks.
- **At 60 or under, waves 2-5 proceed as written.**
- **Over 60**, wave 7's levers move ahead of wave 3, because the picture is
  then fighting the CPU for a frame that is not there.

The no$gmb field run (section 1) is asked for here, as a cross-check.

### Wave 2 - the machine

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
- **A report quotes Super Mario Land's game speed and frame rate on 86Box
  `vm/286` and on the Victory 286**, from the overlay. These are read on the
  glass, and the report says so.

### Wave 5 - sound, save RAM, MBC3, polish

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

### Wave 6 - ROMs over 256 KB (conditional)

**Features**
- A bank cache in conventional memory over `XMEM.DRV`, sized from `gbprof`'s
  per-bank counts.
- Taken only if the owner wants the 512 KB and 1 MB titles.

### Wave 7 - the speed levers (conditional)

**Features**
- Section 5, in order, each one measured before the next is started.

### Wave 8 - the 5150 demo, disks and the Wire record

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
- **No row can time a 286.** QEMU counts and does not time, MartyPC is an
  8088, and 86Box has no automation socket. The 286 figures come from the
  overlay, read by a person, and that is written beside every one of them.
  MartyPC's 8088 cycle counts are the automated guard for regressions.
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
- **Trademark.** The package name is the owner's decision (section 3.2).

## 10. What is in this PR (wave 0)

- docs/reports/GAMEBOY-FEASIBILITY-2026-10-19.md: the 5150 question,
  PREDICTED.
- docs/reports/GAMEBOY-WORKLOAD-2026-10-19.md: busy shares and event rates
  for Super Mario Land, libbet and a control, MEASURED on the host.
- `tools/gbprof.py` and `tools/gbprof/gbprof.c`: the instrument. Peanut-GB is
  fetched at a pinned commit into `build/gbprof/`, and no ROM is committed.
- This plan.
