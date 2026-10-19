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
wave 1 - the SM83 core and the system code that hosts it, run BARE by a test
harness with no os8088 underneath. There is no package yet, no picture, no
sound, no save RAM and no MBC3 clock. Sections 10 and 11 say what exists of
those halves.

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

**The core answers the common registers itself** and leaves only for the
rest (section 9). That rule exists because the trip out - the stack switch
and the register saves - was a quarter of the 8088's time on Super Mario
Land (the report, section 4).

## 6. Time

**Every time is a dword of M-cycles since `rb_init`.** "Now" is
`S_TNEXT - BP`: `S_TNEXT` is when the next event is due and BP counts down to
it, every handler subtracting its own M-cycles (`sub bp,n`). A taken or
not-taken branch, HALT, RETI, EI and STOP check `js` and enter
`S_EVVEC`; straight-line code does not check, so an event is late by at most
one basic block.

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
`(now - S_TDIV) >> shift` does, shift being TAC's rate. A DIV write sets
`S_TDIV` = now. `instr_timing` fails without this.

### 6.1 The state at 0100h

A = 01, F = B0, BC = 0013, DE = 00D8, HL = 014D, SP = FFFE, PC = 0100, and
the I/O registers the DMG boot ROM leaves, with LCDC = 91h, STAT = 85h, BGP
= FCh and **DIV = ABh** (`S_TDIV` = -ABh x 64). The LCD is on and line 0
begins at time 0. FF4C-FF7F read FFh (section 9).

## 7. Interrupts

An enabled, pending interrupt is taken at the next event entry: IME cleared,
IF's bit cleared, PC pushed, PC = 40h + 8 x the bit, and **5 M-cycles**
charged before the handler's first instruction. A write to IF or IE takes
one **at once**, from inside the writing instruction (`rb_irqnow`), so the
pushed PC is the next instruction's. HALT ends when IF AND IE is non-zero,
whether or not IME is set. A read of IF first runs every event already due
(`rb_catchup`), so a game polling IF sees what the hardware would.

## 8. The spin-wait rule

A taken backward `JR` of **-4 to -7** to a loop head is a SPIN-WAIT, skipped
to the next event at no cost, when the loop's body is exactly one read and
one test:

| read | test |
|---|---|
| `LD A,(nn)` of WRAM or HRAM | `AND A`, `OR A`, `CP n`, `AND n`, `BIT b,A` |
| `LDH A,(n)` of HRAM (n >= 80h) | the same |
| `LD A,(HL)`, HL in WRAM or HRAM | the same |
| `BIT b,(HL)`, HL in WRAM or HRAM | (it is the test) |

Nothing in such a loop can change what it reads until an interrupt does, and
an interrupt is an event. A register is never a spin-wait's subject - LY and
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
is logged in `RB_RLOG` as (line, register, value), at most 192 a frame, and
the first one in a frame first snapshots all eight as the frame began into
`RB_SNAP`. It is the renderer's input (the plan's section 4.4); nothing
draws yet.

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
| `tests/gbcpu.py` | the correctness ROMs, with a broken-DAA control |
| `tools/gbtrace.py`, `tests/gbtrace.py` | the differential trace against Peanut-GB, with a broken-`JR NZ` control |
| `tests/rbcore/rbbench.py` | cost per M-cycle on gbclock, or a game's frames against real time |
| `tests/rbcore/rbprof.py` | where the time goes, by handler, on MartyPC or 86Box |
| `tests/rbcore/rbshot.py` | a play image's last frame, drawn from its VRAM |
