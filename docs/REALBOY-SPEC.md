# REALBOY - a real-mode Game Boy emulator (`apps/realboy/`)

**The binding contract for RealBoy.** It stands to `apps/realboy/` as
docs/C64-SPEC.md stands to `apps/c64`: the register map, the layouts, the
interfaces between the core and the code that hosts it, and the rules the
timing model keeps are pinned here, and a change goes here *before* it goes
in the code. The design record - why a threaded interpreter, why two page
tables, the waves and the gates - is docs/plans/REALBOY-PLAN.md; the
measurements are docs/reports/REALBOY-CORE-COST-2026-10-19.md. This file says
what the code does today.

It is cited from outside as "REALBOY-SPEC section N"; inside it, "section N"
is a section of this file.

**What is built, stated once so no section below has to hedge:** the plan's
waves 1 and 2 and wave 3 - the SM83 core, the system code that hosts it, the
composer of section 13, and `REALBOY.O88`, the windowed package of section
14. There is no fullscreen path, no sound, no save RAM, no MBC3 clock, no
speed overlay and no ROM over 256KB.

---

## 1. What it is

A Game Boy (DMG) emulator for os8088, in **pure 8086 assembly**, one core
shared by every machine: the primary target is a ~12 MHz 286 at full game
speed, and the same core carries a HALT-heavy demo of our own on the 5150
(the plan's section 6). There is **no boot ROM**: the core starts at 0100h
with the registers and I/O state the DMG boot ROM leaves (section 6.1).

| file | what it is |
|---|---|
| `apps/realboy/rbgen.py` | the core's GENERATOR: writes `build/realboy/rbcore.asm`, one handler per opcode. Nothing generated is committed |
| `apps/realboy/rbdefs.inc` | the layout: the view, the state block's fields, exit codes, MBC types, flag bits, the PPU's clock constants. **The field table there is this contract's list of fields** |
| `apps/realboy/rbsys.inc` | the system code: init, run, events, the I/O and MBC registers rbsys answers, the raster log, the trace hook. Included by a host |
| `apps/realboy/rbppu.inc` | the picture: `rb_render` (section 13). Included by a host after rbsys.inc |
| `apps/realboy/realboy.asm` | the package: the window, the worker, the writers (section 14) |
| `tests/rbcore/` | the bare harness and the instruments (section 12) |

No ROM, test ROM or reference emulator source is ever committed. Test ROMs
are fetched by `tools/getgbtest.py`, Peanut-GB by `tools/gbprof.py`, each at
a pinned commit or SHA-256.

## 2. The register map

| SM83 | 8086 | notes |
|---|---|---|
| A | AL | |
| F | AH | in **LAHF's layout**: Z bit 6, H (AF) bit 4, C bit 0, and N kept in bit 5, which LAHF leaves alone. `RB_F2AH`/`RB_AH2F` (section 3) translate for PUSH/POP AF and the trace |
| BC | CX | |
| DE | DI | |
| HL | BX | |
| SP | SP | with **SS = the view** (section 3), so a Game Boy push is an 8086 push |
| PC | SI | with **DS = the region holding it**: the view, or ROMX for 4000-7FFF |
| - | BP | the **cycle countdown**: M-cycles to the next event, signed (section 6) |
| - | DX | dispatch scratch. **DL is 0 at every dispatch**; DH carries a read's byte between a handler and a tail |
| - | ES | scratch, any handler |

## 3. Memory: the view and ROMX

The core addresses the Game Boy's 64KB through **two segments**:

- **The view**, one 64KB claim, which SS always holds:
  - 0000-3FFF: a copy of ROM bank 0, made at init;
  - 4000-7FFF: rbsys's own data, never the game's: the state block at
    `RB_STATE` (4000h), `RB_F2AH` (4100h), `RB_AH2F` (4200h), the raster log
    `RB_RLOG` (4300h, 192 entries of 4 bytes), `RB_SERBUF` (4700h) and the
    frame-start snapshot `RB_SNAP` (4800h);
  - 8000-FFFF: the Game Boy's own RAM and registers, at their own addresses -
    VRAM, cartridge RAM (one bank), WRAM, OAM, the I/O registers and HRAM.
- **ROMX**, the current switchable bank: `S_ROMX` = `S_ROMSEG` + bank x 400h
  - 400h, so that ROMX:4000 is the bank's first byte. **A bank switch is a
  pointer change and never a copy.**

A data access tests the address (section 5.2): the view takes every address
directly but 4000-7FFF (ROMX) and FF00-FF7F (registers), and a write to
0000-7FFF is a cartridge register write.

## 4. Dispatch and the core's layout

The core is one 64KB segment. **The handler for opcode X is at X x 256, and
the handler for CB-prefixed X at X x 256 + 128**, so dispatch is

    mov dh,[si] / inc si / jmp dx        ; DL = 0

and a CB handler is reached by `mov dl,80h` instead. A handler's slow paths
follow it inside its own half-slot. The eleven opcodes the SM83 does not
have - D3, DB, DD, E3, E4, EB, EC, ED, F4, FC, FD - each begin with a stub
that stops the core (`S_BADOP`, `RBX_BADOP`), and their half-slots carry the
shared tails:

| slot | tails |
|---|---|
| D3 | `rd_slow`, `wr_slow` - a read of ROMX or a register, a cartridge or register write |
| DB | `force_ev` - make the next check fire (EI) |
| DD | `RB_DISPATCH`, which **must be at DD00h** (rbsys enters the core there), and `mbc_wr` |
| E3 | `daa_tail` - the SM83's DAA rule |
| E4, EB, EC, ED | the idle detector (section 8) and `mbc_set` |
| F4 | `io_rd` - register reads answered in the core |
| FC | `io_lcd` - STAT and LY |
| FD | `io_wr` - register writes answered in the core |

A tail is entered by a near jump with `[S_RET]` holding where to resume and
returns with `jmp word [ss:S_RET]`. A half-slot holds 128 bytes; the
generator's `times` fails the assembly when one overflows.

## 5. The core and rbsys

### 5.1 Calls a host makes

rbsys is included by a host and assembled into the host's code segment. It
asks the host for two near procs:

- `rb_putc`, AL = a byte the game sent on its link port (may be a bare RET);
- `rb_trbyte`, AL = a byte of an `RB_TRACE` core's trace record (may be a
  bare RET; preserves every register).

and offers:

- **`rb_init`** - AX = the view's segment, BX = the core's, CX = the ROM
  image's, DX = the image's size in 16KB banks. Copies bank 0, builds the
  flag tables, parses the cartridge header's MBC byte, sets the post-boot
  state (section 6.1) and points the vectors (section 5.2) at rbsys.
- **`rb_run`** - AX = a budget in M-cycles. Runs the core until a frame is
  ready, the budget is spent, the game executes STOP or a bad opcode, and
  returns AX = `RBX_FRAME` (1), `RBX_BUDGET` (2), `RBX_BADOP` (3) or
  `RBX_STOP` (4). Every register but AX is preserved.
- **`rb_trace_on`** - with an `RB_TRACE` core, trace the first instruction
  after every return to the core too (section 12.2).

### 5.2 Calls the core makes

The core leaves through far vectors in the state block, so the core's
segment never needs to know the host's:

| vector | entry | entered with | returns |
|---|---|---|---|
| `S_EVVEC` | `rb_ev_entry` | the registers live, BP <= 0 or an event forced (section 6) | `rb_resume`, or `rb_run`'s caller |
| `S_IORVEC` | `rb_ior` | BX = FF00-FF7F, `[S_RET]` | DH = the byte, at `S_RETFAR` |
| `S_IOWVEC` | `rb_iow` | BX = FF00-FF7F or FFFF, `[S_WVAL]` = the byte | at `S_RETFAR` |
| `S_MBCVEC` | `rb_mbc` | BX = 0000-7FFF, `[S_WVAL]` | at `S_RETFAR` |
| `S_TRACEVEC` | `rb_trace` | (`RB_TRACE` cores, at every dispatch) | `S_DISP` |
| `S_RESVEC` | - | where `rb_resume` enters the core: `RB_DISPATCH`, or `rb_trace` | |

**An entry switches to the host stack first** (`RB_TOHOST`): the core's
SS:SP is the Game Boy's stack inside the view, which may point anywhere - a
game that reads a table with `LD SP,HL / POP` points it into ROM - so no
host code ever pushes on it.

**For the same reason the core runs with interrupts OFF**, and rbsys, on the
host stack, with them on. An IRQ taken in the core would push its frame
below the Game Boy's SP: into HRAM's variables when the stack is there, into
the copy of bank 0 when SP points at a table in ROM. So an interrupt waits
for the core's next trip out - an event, a register, a bank switch - or the
end of `rb_run`'s budget, and **a host sizes that budget for its mouse**: a
serial mouse on an 8250 delivers a byte every 8.3 ms. On os8088 this also
means the scheduler never switches away from the core (`sch_switch` switches
only a task whose SS is `LOW_SEG`). Every trip out of the core turns them
back on, on the host's task stack, so the tick pre-empts the host between two
budgets as it would any task: no yield is needed for that, and the package
yields once a frame, for a UI task a click woke.

**What it does not cover**: a game whose SP points into 4000-7FFF reads the
view's rbsys half there, not ROMX, through its pops.

**The core answers the common registers itself** and leaves only for the
rest (section 9). That rule exists because the trip out - the stack switch
and the register saves - was a quarter of the 8088's time on Super Mario
Land (the report, section 4).

## 6. Time

**Every time is a dword of M-cycles since `rb_init`.** "Now" is
`S_TNEXT - BP`: `S_TNEXT` is when the next event is due and BP counts down to
it, every handler subtracting its own M-cycles (`sub bp,n`). A taken or
not-taken branch, HALT, RETI, EI, STOP and NOP check `js` and enter
`S_EVVEC`; straight-line code does not check, so an event is late by at most
one basic block. NOP checks because a game that has crashed runs off into
zeroed memory, and a core that never checks never gives its host the machine
back.

| event | time | does |
|---|---|---|
| `S_TVBL` | line 144 of a frame | VBlank: IF bit 0, the STAT mode-1 interrupt, `RBX_FRAME` |
| `S_TSTAT` | the next enabled STAT condition (LYC, mode 2, mode 0) | IF bit 1 |
| `S_TTIMA` | TIMA's next overflow | IF bit 2, TIMA = TMA |
| `S_TSTOP` | the end of `rb_run`'s budget | `RBX_BUDGET` |

`rb_sched` sets `S_TNEXT` to the earliest, never more than 7FFFh M-cycles
ahead, and BP to the distance. It also normalises `S_TFRAME` (the start of
the frame holding now) and sets **`S_TNF` = `S_TNEXT` - `S_TFRAME`** (low 16
bits), so the core reads the PPU's place as `S_TNF - BP` modulo a frame
without leaving it. Anything that moves `S_TNEXT` or `S_TFRAME` keeps
`S_TNF` with it (`rb_force`, `force_ev`).

The PPU's clock: **114 M-cycles a line, 154 lines, 17,556 a frame**; mode 2
for M-cycles 0-19 of a visible line, mode 3 for 20-62, mode 0 from 63
(`RB_HBL`), mode 1 on lines 144-153.

**DIV and TIMA run off one free-running counter**, as the hardware's do:
DIV is `(now - S_TDIV) >> 6`, and TIMA ticks each time
`(now - S_TDIV) >> shift` does, shift being TAC's rate - that is, when the
counter's bit `shift - 1` falls. A DIV write sets `S_TDIV` = now, and a DIV
or TAC write that makes that bit fall ticks TIMA once (rb_tbit). TIMA reloads
from TMA at the overflow itself, with none of the hardware's one-M-cycle
delay. `instr_timing` fails without the counter.

### 6.2 When inside an instruction a register is touched

A register read or write is answered **as of the M-cycle the hardware makes
it in**, counted from the instruction's first: 1 for `LD r,(HL)`,
`LD (HL),r`, `LD A,(BC)`/`(DE)`, `LDI`/`LDD`, `LD A,(C)` and the ALU's
`(HL)` forms, and `INC`/`DEC (HL)` read; 2 for `LDH A,(n)`, `LDH (n),A`,
`LD (HL),n`, `INC`/`DEC (HL)`'s write and a CB `(HL)` read; 3 for
`LD A,(nn)`, `LD (nn),A` and a CB `(HL)` write; 3 and 4 for
`LD (nn),SP`. The generator's `read8(at)`/`write8(at)` take BP back by
`at` around the slow path only, so the fast path pays nothing. `mem_timing`
fails without this.

### 6.1 The state at 0100h

A = 01, F = B0, BC = 0013, DE = 00D8, HL = 014D, SP = FFFE, PC = 0100, and
the I/O registers the DMG boot ROM leaves, with LCDC = 91h, STAT = 85h and
BGP = FCh. The counter under DIV reads **ABCCh T-states** at 0100
(`S_TDIV` = -(ABCCh / 4)), TAC F8h, DMA FFh, NR52 F1h. The LCD is on and line
0 begins at time 0. FF4C-FF7F read FFh (section 9).

## 7. Interrupts

An enabled, pending interrupt is taken at the next event entry: IME cleared,
IF's bit cleared, PC pushed, PC = 40h + 8 x the bit, and **5 M-cycles**
charged before the handler's first instruction. A write to IF or IE takes
one **at once**, from inside the writing instruction (`rb_irqnow`), so the
pushed PC is the next instruction's. HALT ends when IF AND IE is non-zero,
whether or not IME is set, and **a budget that ends inside a HALT leaves it a
HALT**: the next `rb_run` goes on to the next event rather than into the
instruction after it (a game that counts VBlanks with `HALT` counted host
budgets before this). **The HALT bug**: HALT executed with IME clear and
an interrupt already pending does not halt, and the byte after it is read
twice - the next opcode runs with PC still on itself.

**EI is not delayed by one instruction.** It sets IME at once and forces the
next event check, so a pending interrupt is taken at the next branch, HALT
or RETI rather than after exactly one more instruction. `EI / HALT` and
`EI / RET` come out as the hardware's; Mooneye's `ei_sequence`, `ei_timing`,
`rapid_di_ei` and `di_timing` do not (section 12.3). A read of IF first runs every event already due
(`rb_catchup`), so a game polling IF sees what the hardware would.

## 8. The spin-wait rule

A taken backward `JR` of **-4 to -16** to a loop head is a SPIN-WAIT,
skipped to the next event at no cost, when the loop's body is one read and
then only tests, each of which may be followed by a `JR cc` that goes back
to the head or forward out past the closing `JR`:

| read | then, one or more |
|---|---|
| `LD A,(nn)` of WRAM or HRAM | `AND A`, `OR A`, `CP n`, `AND n`, `BIT b,A`, `JR cc` |
| `LDH A,(n)` of HRAM (n >= 80h) | the same |
| `LD A,(HL)`, HL in WRAM or HRAM | the same |
| `BIT b,(HL)`, HL in WRAM or HRAM | (it is the test, alone) |

Nothing in such a loop can change what it reads until an interrupt does, so
every pass takes the same path, and an interrupt is an event. Kirby's
Dream Land in play waits on a read and TWO tests, `LDH A,(8C) / BIT 5,A /
JR NZ / BIT 6,A / JR NZ,-10`: when the first rule stopped at one test and
-7, the second jump was never skipped, and that scene ran at 27.8% of real
time full screen on 86Box's 286 where it runs at 37.5% now.

### 8.1 Countdowns

A taken `JR NZ,-3` back to `DEC A`, `DEC B` or `DEC C` is a COUNTDOWN, and
`cnt_ff` runs it to its end in one step: from the taken `JR`, r more `DEC`s
take 4r + 2 M-cycles, and the register ends 0 with the flags of 1 -> 0
(Z and N set, H clear, C kept). It does so only when BP covers the whole of
it, so no event can fall inside; otherwise the loop runs as it would have.
The OAM DMA routine every game copies to HRAM waits on one (`LD A,28h /
DEC A / JR NZ,-3`), and so does a delay loop. The interpreter and the
recompiler both take it. A register is never a spin-wait's subject - LY and
STAT change on their own. A loop head found NOT to be one is remembered in
`S_IDLENO`, so a busy loop pays the test once. An `RB_TRACE` core skips
nothing (section 12.2).

## 9. The registers

**Answered in the core** (`io_rd`, `io_lcd`, `io_wr`, `mbc_wr`), each
exactly as rbsys would:

- **P1 (FF00)** reads, from `S_JOY` (bits Right, Left, Up, Down, A, B,
  Select, Start; 1 = held) and the select bits; writes keep bits 4-5.
- **STAT (FF41)** and **LY (FF44)** reads, from `S_TNF - BP` (section 6):
  LY 0 and STAT mode 0 with the LCD off; the coincidence bit against LYC.
- **Sound (FF10-FF3F)** writes are stored.
- **FF4C-FF7F** - nothing on a DMG: reads FFh, writes are dropped.
- **ROM bank switches** (2000-3FFF) on an MBC1, MBC3 or MBC5 whose high bank
  bits are 0, the bank masked by `S_BMASK` (banks - 1); DS moves with ROMX
  when the game runs from 4000-7FFF.

**Read masks.** A read of FF00-FF3F answered by rbsys is ORed with the bits
a DMG reads back as 1: SC's unused bits, FF03 and FF08-FF0E, the sound
registers' write-only halves and unused bits, FF15, FF1F and FF27-FF2F
(`rb_iomask`).

**Answered by rbsys:** DIV, TIMA, TAC, IF, IE, SC (a transfer sends SB to
`rb_putc` and completes at once: nobody is on the other end, so SB reads FFh
and IF bit 3 is set), LCDC (the LCD starting restarts the frame
at line 0), STAT and LYC writes (rescheduling `S_TSTAT`), OAM DMA (FF46,
160 bytes at once), and LCDC/SCY/SCX/BGP/OBP0/OBP1/WY/WX writes, which go
through the raster log (section 11). Every other register is stored.

## 10. Cartridges

The header's byte 0147h picks the MBC: none, **MBC1**, **MBC2**, **MBC3**
or **MBC5**. Bank 0 written to a bank register reads as 1 on MBC1, MBC2 and
MBC3 (not MBC5). RAM enable is recorded in `S_RAMEN`. One 8KB bank of
cartridge RAM lives at A000 in the view; RAM banking, MBC3's clock and save
RAM are the plan's wave 5.

## 11. The raster log

A write to LCDC, SCY, SCX, BGP, OBP0, OBP1, WY or WX during the visible lines
is logged in `RB_RLOG` as (line, register, value), at most 192 a frame - the
line it takes effect on, the next one for a write in HBlank - and the first
one in a frame first snapshots all eight as the frame began into `RB_SNAP`
(LCDC, SCY, SCX, BGP, OBP0, OBP1, WY, WX), tagged with the frame's number in
`S_SNAPTAG`. It is the renderer's input (section 13).

## 12. The harness and the instruments

### 12.1 The bare harness

`tests/rbcore/rbhost.asm` is a boot sector and a host: it loads itself, the
64KB core and a ROM (to 3000:0, up to 384KB) and runs it with no os8088.
`tests/rbcore/rbimg.py` builds the floppy (`--patch OFF:HEX` breaks the core
on purpose for a negative control). Modes:

| mode | does |
|---|---|
| 0 `test` | runs N frames; the link port's bytes go to the screen and COM1 |
| 1 `bench` | runs N frames as fast as it can and prints the BIOS ticks |
| 2 `trace` | an `RB_TRACE` core: COM1 carries trace records and nothing else |
| 3 `play` | as bench, pressing buttons on gbprof's platformer script, counters and ticks restarted at frame 800, then VRAM, OAM and the LCD registers on COM1 |
| 4 `idle` | as play, no buttons |

It ends with `RBHOST DONE frames F ticks T events E skipped S END`.

### 12.2 The trace

An `RB_TRACE` core calls `S_TRACEVEC` at every dispatch. The record is 14
bytes, words little-endian: **PC, A, F (as the Game Boy holds it), BC, DE,
HL, SP, and now** (low 16 bits). An `RB_TRACE` core skips no spin-wait, so
every loop iteration is in the trace.

### 12.3 The instruments

| | |
|---|---|
| `tests/gbcpu.py` | the correctness ROMs, with a broken-DAA control: Blargg's `cpu_instrs` (all), `instr_timing`, `mem_timing` and `halt_bug`, and 26 of Mooneye's DMG acceptance tests |
| `tests/rbcore/rbacid.py` | dmg-acid2 through `rb_render`, pixel for pixel, with a broken-`LDH` control |
| `tests/gbwindow.py` | `REALBOY.O88` on MartyPC: dmg-acid2 opened from the Disk window, running, and on the glass pixel for pixel through both writers - and full screen (section 15) against the same reference, then back to the desktop |
| `tests/rbcore/rbwin.py`, `tests/rbspeed286.py` | the package's game speed and frames drawn on an 86Box machine, in its window or full screen, with a profile on request; `rbspeed286` runs Super Mario Land and Kirby on the 286 (`$OS88_GB_ROMS`) |
| `tools/gbtrace.py`, `tests/gbtrace.py` | the differential trace against Peanut-GB, with a broken-`JR NZ` control |
| `tests/rbcore/rbbench.py` | cost per M-cycle on gbclock, or a game's frames against real time |
| `tests/rbcore/rbprof.py` | where the time goes, by handler, on MartyPC or 86Box |
| `tests/rbcore/rbshot.py` | a play image's last frame, drawn from its VRAM |

### 12.4 The Mooneye acceptance tests that do not pass

Of the 63 that are about a DMG (the release `tools/getgbtest.py` pins), the
core passes the 26 `tests/gbcpu.py` names. The others fail for four reasons,
each a model this core chose not to carry:

- **Instruction timing measured by OAM DMA** - `call`, `call_cc`, `jp`,
  `jp_cc`, `ret`, `ret_cc`, `reti`, `rst`, `push`, `pop`, `add_sp_e`,
  `ld_hl_sp_e` `_timing`, `reti_intr_timing`, `oam_dma/sources-GS`,
  `interrupts/ie_push`: they find an access's M-cycle by racing a DMA that
  blocks the bus, and the core's DMA is a 160-byte copy at once.
- **The PPU's variable mode 3, and STAT's finer rules** - every `ppu/` row but
  `intr_2_mode0_timing` and `intr_2_mode3_timing`: mode 3 lengthens with
  sprites and SCX on the hardware and is a fixed 43 M-cycles here, and the
  STAT line's blocking and LCD-on timing are not modelled.
- **EI's delay** (section 7) - `ei_sequence`, `ei_timing`, `rapid_di_ei`,
  `di_timing-GS`, `halt_ime1_timing2-GS`.
- **TIMA's reload delay** (section 6) - `tima_reload`,
  `tima_write_reloading`, `tma_write_reloading`, `rapid_toggle`; and the
  serial clock's phase, `boot_sclk_align`.

## 13. The picture

`rb_render` (`apps/realboy/rbppu.inc`) composes the frame that ended at the
last `RBX_FRAME` into a host's 5,760-byte buffer: **144 lines of 40 bytes,
the shade's bit 0 for pixels 0-159 (20 bytes, the leftmost pixel in bit 7)
and then its bit 1**. Shade 0 is the lightest. Every register is preserved;
its working memory is the view's 4900h-4B5Fh. `rb_render4` composes the same
frame as **the four planes `OSAPI_GFX_BLITP` takes**, into 11,520 bytes: 80 a
line, NOT bit 1 three times then NOT bit 0, which is the desktop's 15, 7, 8
and 0 for shades 0-3. It writes each line as it finishes it, so a colour
window has no second pass over the frame.

- **The state** each line is drawn with is the frame's own: `RB_SNAP` with
  `RB_RLOG` applied at each entry's line when `S_SNAPTAG` is the frame just
  ended (`S_FRAMES` - 1), the registers as they stand otherwise. VRAM and OAM
  are read as they stand: the frame is composed at VBlank's start, before
  the game's VBlank handler has touched either.
- **A byte - eight pixels - at a time, never a pixel.** The background is 21
  tile rows from the map, each already two bit-planes, shifted left by
  `SCX AND 7`. The window replaces it from X = WX - 7 when LCDC bits 0 and 5
  are set, WY <= LY and WX <= 166, with **its own line counter**, which
  counts only the lines it was drawn on. LCDC bit 0 clear makes the
  background and window colour 0 and every sprite visible over them.
- **Palettes** are four minterm masks: colour k's shade bits as 00h or FFh,
  so a byte's shade is `(c0 AND m0) OR ... OR (c3 AND m3)` for each bit.
- **Sprites**: the first ten in OAM order whose rows cover the line (8 or 16
  tall; a 16-tall sprite ignores its tile number's bit 0), then **sorted by
  X, equal X keeping OAM order**, and drawn highest priority first through a
  CLAIMED mask: a pixel the first opaque sprite took stays its, so a sprite
  behind the background still hides the sprites under it, and it shows only
  over background colour 0.

`tests/rbcore/rbacid.py` holds it to dmg-acid2's reference, all 23,040
pixels. It is the composer only: the writers that take the planes to a
screen are the package's.

## 14. The package

`REALBOY.O88` (`apps/realboy/realboy.asm`, `OS88_STACK_384`) is a window of
160x144 content that runs one game.

- **Its parts** (SPEC.md 20.12): 0 and 1 are the core's two 32KB halves, LZ4
  on the disk - one part is at most 65,024 bytes, and two adjacent rows are
  one segment in the carve - and 2 is the view, a zeroed 64KB carve with no
  file bytes. `op_load` claims all three at launch and refuses there, in its
  own toast, on a heap without 128KB.
- **A game** opens from File > Open or as a document: the `.GB` association
  launches the package with it. `rw_load` asks the file its size with the
  size probe (a read with no room answers the KB it needs, unpacked, with a
  compressed file's slack), claims that, reads, and then checks the bytes
  that came in: **whole 16KB banks, 32KB to 256KB**, refused in a toast
  otherwise. One game a window: another opens in another.
- **The worker** owns the machine. It counts BIOS ticks into frames owed, 840
  of 256 a tick (59.7275 Hz against 18.2065), at most eight behind, and
  reads the clock again after every frame - so it sleeps only when nothing
  is owed. It runs the core a frame at a time in budgets of 2,000 M-cycles,
  700 on an 8088 (`OSAPI_CPU_INFO`), where 2,000 is ~20 ms with interrupts
  off; and composes and blits a frame when it has caught up or every three
  ticks whatever happens, so a machine that is behind still shows ~6 frames
  a second. F1 puts the game's speed and the frames drawn a second over the
  picture. The joypad is the held keys - arrows, X = A,
  Z = B, Enter = Start, Space = Select - and nothing while another window
  has the keyboard. Reset is the worker's to do (`rb_init` again); Pause
  stops the clock.
- **The writers**: on a colour display `OSAPI_GFX_BLITP` with the clip walk,
  of `rb_render4`'s planes; on a 1bpp display, or where BLITP refuses,
  `OSAPI_GFX_BLIT1` through a 2x2 ordered dither of `rb_render`'s - shade 0
  lit, 1 a quarter dark, 2 a checkerboard, 3 dark. The buffer remembers which
  it holds, and a paint on the other kind of display (the window moved
  between two) is white until the worker's next frame. A refusal dithers
  until the next paint asks BLITP again.
- **Its region is movable**, its worker restartable at the top of its loop;
  `rw_reloc` re-points the six state-block vectors that name its code
  segment. The core, view and ROM claims are pinned.
- **A bad opcode** stops the machine and the window says so.

## 15. Full screen

Machine > Full Screen runs the machine **on the UI task inside an
`OSAPI_FSX_RUN` bracket** (SPEC.md 53), in `apps/realboy/rwfsx.inc`. It is
greyed, with the reason, without a game and on a display that cannot set mode
0Dh (`OSAPI_FSX_CAPS`, asked at every paint); Esc leaves.

- **The worker keeps out of the machine.** It is frozen in the bracket, so it
  must not be frozen in the core, or in `rb_render`, whose working memory is
  the view's. It raises `[rw_incore]` at its loop's top and drops it at
  `.sleep` or when its render is done, before it asks for the gfx lock; it
  backs off at the top while `[rw_fsq]` is set. `rw_fsenter` sets `[rw_fsq]`
  and yields until `[rw_incore]` is clear. The worker raises its byte BEFORE
  it reads ours, so once ours is set and its is seen clear, every later entry
  of its sees ours.
- **The screen** is mode 0Dh, 320x200 planar, with the picture at 1x at
  (80, 28). `rb_render`'s two shade planes go to VGA planes 0 and 1 as they
  are, through a RAM shadow of the last frame, so a word is written only when
  it changed. Plane 2 is set everywhere but the picture: the border is DAC
  entry 4, and F1's speed line over it, in glyphs copied before the mode
  (`OSAPI_FONT_GLYPHS`), entry 7. Shades 0-3 are DAC 0-3, greys. The DAC is
  ours in there; the restore's BIOS mode set puts the desktop's back.
- **The clock** is `FSXF_RATE` at the Game Boy's own 59.7275 Hz (PIT divisor
  19,977): the hook counts frames owed and does nothing else. The loop runs
  the machine to the count, at most eight behind, in budgets of 6,000
  M-cycles (1,400 on an 8088) - with no mouse to serve only IRQ0 bounds them,
  and a 286 spends ~7 ms on 6,000 busy ones against a 16.7 ms period. It
  draws a frame when it has caught up, or after four undrawn; with nothing
  owed it waits for the next period (`FSXW_FRAME`). It empties the BIOS key
  buffer every pass, since a full one beeps. `kern_small`, which refuses the
  rate and has no VGA, is retried without it and paced by the tick.
- **Coming back**: the window's buffer was the bracket's shadow, so it is
  marked empty and the restore's repaint is white until the worker's next
  frame; the worker's clock restarts from the moment the bracket ended.

## 16. The recompiler

On a 286 RealBoy translates the Game Boy's ROM code into 8086 code, a block
at a time, and runs that instead of interpreting it (`apps/realboy/rbjit.inc`,
`rbtmpl.py`; `tests/rbcore/rbhost.asm`'s `b_jit` and the package's Machine >
Recompiler turn it off). What it saves is the interpreter's fixed cost: the
three-instruction dispatch, which flushes a 286's prefetch queue every time,
and the operand fetches through SI.

### 16.1 Templates

A translated instruction is its interpreter handler's own body. `rbgen.py`'s
`template_lines()` writes each handler with the dispatch taken off, `[si]`
operands as `IMM8`/`IMM16`, `xor dl,dl` dropped (DL = 0 is the dispatch's
invariant, which `tr_int` restores) and external jumps `near`; `rbtmpl.py`
assembles every one three times - at its origin, 2000h further on, and with
other operand values - and finds by comparing the bytes where the operands
are, which words are references to the template itself (`S_RET = .k`) and
which are relative jumps out of it to a core helper. **So translated code
computes exactly what the interpreter does**, and `gbcpu`, `gbacid` and the
harness's event counts hold it to that: Super Mario Land's 1,200 frames of
gbprof's script take the same events and skip the same M-cycles either way.

- Control transfers have no template: the translator writes their M-cycles,
  the event check the interpreter makes at a branch, and the way on (16.4).
  An opcode with neither - HALT, STOP, RETI, an invalid one - ends the block
  with SI = its PC and `tr_int`, the interpreter's dispatch.
- A template over 80 bytes is the interpreter's too: the read-modify-writes
  of `(HL)`, whose read and write slow paths are both inline.
- A memory template keeps the slow path's stub BEFORE the fast access, so
  the common case takes one jump and none over the stub; the 286 here is
  bound by fetching code bytes, so a jump and its bytes are the cost.
- `LDH (n)` and `LD (nn)` on an address the interpreter's own fast path takes
  directly - HRAM, WRAM, VRAM, bank 0 - are chosen by operand: one `MOV`
  through SS and the M-cycles (`rbgen.EXTRA`).

### 16.2 The cache

The code goes into a 64KB segment of its own. It holds copies of the core's
helper tails - the slots `rbgen.TAILS` uses - at their own offsets, so a
template reaches every helper with a near jump, and the block table in slots
00-3F; ~44KB is left for code, in the free ranges `rbtmpl.py` lists. A helper
that leaves for rbsys records its CS in `S_RETFAR` first, so rbsys comes back
to the copy that called it, and every way out of the cache to the
interpreter is a far jump. When the cache is full everything is forgotten
and translation starts again. The package claims it on a 286 or later, after
the ROM; without the memory there is no recompiler.

### 16.3 Blocks and tr_enter

A block is straight-line code from a PC to the first control transfer, at
most 40 instructions, never across 4000h or 8000h, keyed by its PC and - in
4000-7FFF - the ROM bank. `tr_enter` finds it: a direct-mapped table of 2,048
entries (PC, bank key, a count, the block's offset). **A PC is translated
only on its 16th entry**, so code that runs a few times is interpreted and
never takes the cache's room; a translated entry gives its slot up only after
16 others have asked for it. RAM is never translated - the interpreter's own
control transfers stay in the interpreter there (`JDISPATCH`). **With no
recompiler** - an 8088, no memory for the cache, or Machine > Recompiler off
- `rt_dispatch` writes the plain dispatch over the first five bytes of all
45 `JDISPATCH` sites (rbtmpl.py lists them), so the interpreter is the one
there was before the recompiler, and writes them back when it is turned on. Translated code does not keep DS;
`tr_int` sets it for SI before it dispatches.

### 16.4 Chaining

An exit to a constant address in bank 0 is `mov dx,SITE / jmp tr_link`, six
bytes that `tr_link` rewrites into `jmp near` the block once it is
translated, or that the translator writes so at once when it is already
there. An exit into 4000-7FFF gets eleven: a check of `S_BANK` and the jump,
falling onto the exit's own `jmp tr_enter` when the bank is another. Every
`RET` carries an inline cache, `cmp si,PC / jne +3 / jmp near BLOCK`, which
`tr_retlink` fills with the last return to a bank-0 block; a routine called
in a loop then returns without a lookup.

### 16.5 Guards

Translated code does not keep SI either, so a store that can reach the I/O
path - any store whose address is not known, and `LDH`/`LD (nn)` to IF or IE
- is preceded by `mov si,NEXT` and followed by a check that it did not move:
`rb_irqnow` takes an interrupt inside an IF or IE write by moving SI to the
vector. A block running from 4000-7FFF compares the bank after every store
that could reach the MBC, and leaves when it changed.

### 16.6 What it buys, MEASURED on 86Box's 286

gbclock's busy loop costs **13.95 clocks a busy M-cycle against the
interpreter's 26.2**. Super Mario Land, the CPU alone on gbprof's script, is
11.67 ms a frame against 13.04; in the package, in play, **80.1% of real
time in the window and 76.0% full screen**, against 59.5% and 58.0%
interpreted. docs/reports/REALBOY-JIT-2026-10-19.md has the record.

## 17. Sound

**The speaker plays the louder of the two square channels.** The wave and
noise channels make no sound. rbsys keeps a record of the two square
channels (`S_SQ1`, `S_SQ2`) from the writes that decide whether they sound,
and the package turns that record into one tone. All other sound registers
are plain memory.

- **The writes rbsys takes**: NR12/NR22, NR14/NR24 and NR52. The core's
  `io_wr` sends each of them to `rb_iowrite`.
  - A trigger (bit 7 of NRx4) turns a channel on at NRx2's starting volume,
    unless NRx2's top five bits are zero: then the DAC is off and the trigger
    does nothing.
  - An NRx2 write that switches the DAC off silences the channel at once.
  - Bit 6 of NRx4 arms the length counter at `64 - (NRx1 & 3Fh)` steps of
    256 Hz.
  - NR52 with bit 7 clear silences both channels.
- **Time**: `rb_vblank` calls `rb_sqframe` once a Game Boy frame. Each call
  adds 274/256 of a step to the 64 Hz envelope and 1,097/256 of a step to
  the length counter: 64 / 59.7275 and 256 / 59.7275 Hz, kept in 1/256ths.
  An envelope steps the volume towards 0 or 15. A length counter that
  reaches zero turns its channel off.
- **The speaker**: after every frame it runs, the worker calls `rw_sound`.
  It does this in the window and in full screen alike.
  - It takes the channel that is on with the higher volume, channel 1 on a
    tie, and computes `131,072 / (2048 - x)` Hz from its NRx3/NRx4.
  - It passes that pitch to `OSAPI_SND_TONE`, but only when the pitch has
    changed. Volume 0, and a pitch outside 20 to 15,000 Hz, are silence.
  - A refusal (another owner of the speaker) is asked again the next frame.
  - A paused or stopped machine turns the tone off (`rw_quiet`).
- **The pitch is exact and the timing is the game's.** Notes follow the
  game's frames. A game running at half speed plays its tune at half speed,
  at the right pitch.

`tests/gbsound.py` is the gate. GBTONE.GB (`tools/gbprof/gbtone.asm`,
assembled by `tools/gbtone.py` with the pinned rgbds) plays a trigger, a DAC
switched off, and a length counter that runs out. The row captures
MartyPC's speaker and asserts all three. With the length counter broken it
fails, naming the counter.
