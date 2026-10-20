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
- **ROMX**, the current switchable bank: `S_ROMX` is the segment whose
  4000h is the bank's first byte, read out of **the bank table**, `RB_BTAB`
  (6800h in the view, a word a bank, 512 of them). For a cartridge in one
  claim it is `S_ROMSEG` + bank x 400h - 400h; bank 0's is the view's own
  0000-3FFF less 400h. **A bank switch is a pointer change and never a
  copy** - unless the bank is not in memory at all, which is section 10.3's.

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
MBC3 (not MBC5). RAM enable is recorded in `S_RAMEN` and not enforced: a
game that writes RAM it has not enabled keeps what it wrote.

### 10.1 Cartridge RAM and its battery

**A000-BFFF in the view is a window onto one 8KB bank**, so reads and
writes there are plain memory, in the interpreter and in translated code
alike. The other banks are kept elsewhere.

- **Where the banks live.** The host keeps them in `S_RAMSEG`, which holds
  `S_RAMBANKS` 8KB banks, bank 0 first. `S_RAMCUR` records what the window
  holds.
- **Switching.** A bank switch is a write to 4000 on MBC3 and MBC5, or a
  high-bits or mode write on MBC1 in mode 1. `rb_rammap` copies the window
  out to its bank and the new bank in: 16KB moved, on a switch games make
  rarely.
- **One bank.** With `S_RAMSEG` 0 nothing ever moves; that is the bare
  harness, and any cartridge with one bank and no battery.
- **What the package claims.** The header's RAM size code decides: code 1 is
  2KB, 2 is 8KB, 3 is four banks, and 4 and 5 are also kept as four banks.
  An MBC2 has 512 bytes. The package claims the banks
  (`rw_ramsetup`) when there is more than one bank, a clock or a battery,
  and fills them with FFh, as an unsaved cartridge reads.

**A battery cartridge is saved when its window closes.** Battery types are
03h, 06h, 09h, 0Fh, 10h, 13h, 1Bh and 1Eh.

- **When and where.** The close negotiator (`rw_onclose`, SPEC.md 75.1)
  runs on the UI task. It writes `<game>.SAV` **beside the game**, in the
  folder the ROM was opened from (`rw_romdir`, kept at the load), then
  always lets the close go ahead. Opening the game reads the file back from
  the same folder.
  - It was `SYSTEM\APPDATA` on the game's volume until the second field run.
    A game disk has no such folder unless someone makes one. Beside the ROM
    is also where every other emulator puts it.
- **The format is the common one.** The file is the RAM, at its header size.
  For a clock cartridge it is followed by VBA's 48-byte trailer: ten dwords
  (the live then the latched registers), then the time it was written, as
  64-bit seconds since 1970. So a save moves to and from other emulators.
- **Reset.** Machine > Reset keeps the RAM and the clock, as the cartridge
  would (`rw_ramkeep`).

### 10.2 The MBC3 clock

**The five clock registers are banks 08h-0Ch of the window.** Selecting one
fills A000-BFFF with its latched value.

- **Writes.** A value the game writes there is taken into the register when
  the window changes or the clock is latched (`rb_rtccap`).
- **Latching.** Writing 00h then 01h to 6000-7FFF latches the live registers
  (`rb_rtclatch`).
- **Counting.** The clock counts GAME time: `rb_rtcframe` adds 1,097/65,536
  of a second each Game Boy frame, unless DH's halt bit is set.
  - Seconds and minutes count past 59 to 63 and wrap without a carry, as the
    chip does. Hours do the same past 23, to 31.
  - Day 511 to 0 sets DH's carry.
- **Switched off.** A save's trailer stamp is compared with `OSAPI_CLK_GET`
  when the game is opened. The seconds in between are added at once
  (`rb_rtcadd`), so the clock has run while the game was put away. A system
  clock that reads earlier than the stamp adds nothing.

`tests/gbsave.py` is the gate. It runs GBSAVE.GB (`tools/gbprof/gbsave.asm`,
ours: MBC3, timer, four banks, battery) twice through a close.
- It checks that the four banks are four, and that the clock counts two
  seconds in 120 frames.
- It checks the `.SAV` on the flushed floppy.
- On the second boot it checks that the counters come back, with the clock
  past where it was saved.

### 10.3 The bank cache: cartridges over 256K, and the room for the recompiler

**A cartridge that does not fit as one claim lives above 1MB** and its banks
come down as the game switches to them (`apps/realboy/rwbank.inc`). It is
REALBOY-PLAN's wave 6, and the second field run is why it came first: Kirby's
Dream Land (256K) took the heap a 640KB Victory had, so its 64KB recompiler
cache could not be claimed and the game ran interpreted (its log has no J).

- **The plan** (`rw_plan`), from the size probe and `OSAPI_MEM_AVAIL`,
  taken AFTER the damage memory and the recompiler's 80KB are claimed: the
  third field run's logs showed the heap the plan saw (346KB) holding the
  ROM and the recompiler with room over, and still no recompiler - the
  ROM's own read rebuilds the disk caches `OSAPI_MEM_AVAIL` counts as free,
  in exactly the room the cache was to have. So the recompiler is claimed
  first, and given back only if the cartridge then fits no other way. One
  claim when the ROM fits with some slack (24KB) beside it - and the
  recompiler is NOT kept a second time: it once was, the claim having moved
  in front of the plan, and the field Victory's 179K heap gave Kirby's
  Dream Land 5 slots where 9 fit, 50-80 fetches a second full screen and
  12-15% of real time in its window. Otherwise, when
  `OSAPI_XMEM_CAPS` has room for banks 1 on: the cache, with **K slots of
  16KB**, as many as the heap affords after those, at least 4 and at most 40
  or one a bank. Otherwise one claim without that room, as before, and then
  over 256K is refused (`over 256K wants XMS`). The probe answers a KB over
  an exact size (SPEC.md 20.14.6.3), so the plan takes whole banks; bank 0's
  header must then say the same size, which a compressed file - read raw
  here - does not. The log's head gives the heap the plan saw.
- **The load** (`rw_bload`, the UI task): the slots, one `OSAPI_XMEM_ALLOC`
  for banks 1 on, then the file through `OSAPI_FILE_READ_SEQ` a bank at a
  time - bank 0 straight into the view's 0000-3FFF (so `rb_init` is handed
  the view as the image and copies nothing), banks 1 to K-1 into slots, the
  rest through the last slot, and every one copied up as it comes.
- **The table is the host's** when `rb_nres` is not 0: `rb_init` zeroes it
  and calls `rb_bfill`, and a switch to a bank with no segment goes to rbsys
  (the core's `mbc_set` leaves through `S_MBCVEC` when the entry is 0), whose
  `rb_setbank` calls `rb_bmiss`.
- **A fetch** (`rw_bfetch`) takes the slot whose bank the game switched to
  least since the last fetch: `mbc_set` counts every switch in `RB_BUSE`
  (6C00h, a word a bank), and a fetch halves every count after, so what was
  used lately stays. `OSAPI_XMEM_COPY` is UI-task context, so the WORKER
  posts the bank (`rw_bankreq`), wakes the window and sleeps a tick at a time
  until the UI task has it in (`rw_onwake`, and `rw_fsenter`'s wait); full
  screen runs the machine on the UI task, which fetches for itself. A
  window closing while the worker waits ends it at `OSAPI_TASK_ALIVE`.
- **What it costs is nearly nothing**, because a game's working set is small.
  gbprof's LRU column (`tools/gbprof.py`), two minutes of its platformer
  script: Kirby uses **6 banks of 16** in play and Looney Tunes **8 of 64**,
  and with that many slots or more a fetch comes **under once a second**.
  Looney Tunes (1MB, MBC5) runs at **101% of real time in its window on
  86Box's 286** with 18 slots and one bank fetched in ten seconds, and with
  the slots cut to 4 it fetched 12 in ten seconds and kept running.

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
64KB core and a ROM (to 3000:0, up to 368KB) and runs it with no os8088.
`tests/rbcore/rbimg.py` builds the floppy (`--patch OFF:HEX` breaks the core
on purpose for a negative control). Modes:

| mode | does |
|---|---|
| 0 `test` | runs N frames; the link port's bytes go to the screen and COM1 |
| 1 `bench` | runs N frames as fast as it can and prints the BIOS ticks |
| 2 `trace` | an `RB_TRACE` core: COM1 carries trace records and nothing else |
| 3 `play` | as bench, pressing buttons on gbprof's platformer script, counters and ticks restarted at frame 800, then VRAM, OAM and the LCD registers on COM1 |
| 4 `idle` | as play, no buttons |
| 5 `render` | as play, composing every frame with `rb_render` |
| 6 `damage` | as play, and every third frame composed both by `rb_renderd` and whole, counting the frames that differ (section 13.2) |

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
| `tests/gbwindow.py` | `REALBOY.O88` on MartyPC's VGA XT, 5150 Hercules and 5150 CGA: dmg-acid2 opened from the Disk window, running, and on the glass pixel for pixel through each writer - and full screen (sections 15 and 15.1) against the same reference, then back to the desktop |
| `tests/gbdamage.py` | `rb_renderd` against `rb_render` every third frame of a game, under QEMU (section 13.2) |
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
its working memory is the view's 4900h-4B5Fh (and the tables up to 66FFh). `rb_render4` composes the same
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

- **What a line costs is the code a 286 fetches**, since every byte of it
  crosses a bus with wait states: the background's fetch is unrolled
  (`ppu_fshift`, `ppu_fcopyb`, `ppu_fcopyw`), the two tile rows alternating
  between AX and DX and the outputs absolute; `ppu_list` builds the 21 tile
  addresses a line reads from its first column, once a map row and column;
  and with BGP the identity and no sprite on the line, the line is left
  where it was composed (`PPU_OSRC`) rather than copied through the palette.
  On 86Box's 286 Super Mario Land's composition fell from **39.8 to 27.0 ms
  a frame**, every line every frame (`tests/rbcore/rbbench.py --render`).

`tests/rbcore/rbacid.py` holds it to dmg-acid2's reference, all 23,040
pixels. It is the composer only: the writers that take the planes to a
screen are the package's.

### 13.2 By damage: rb_renderd

**`rb_renderd` is `rb_render` that composes only what changed since its last
call.** It composes only the lines whose inputs changed, and writes only the
lines whose pixels then differ. The caller's buffer is ES:DI, and it holds
the last frame. `[rb_dmgseg]` is `RB_DMG_SIZE` bytes of the host's memory
(about 12.4KB); with it 0, `rb_renderd` is `rb_render` and every line has
changed. On return, `RB_DCHG` in that memory holds a byte for each line (1:
it changed), and AX holds the count.

- **A line's inputs** are its eight registers and the window's line counter,
  the map cells and tile rows under its background and window, and its
  sprites: their OAM entries and their tiles.
- **VRAM and OAM are compared** against a shadow of what the last call saw
  (`ppu_dscan`). The comparison runs `repe cmpsw` over the tile data a tile
  at a time and over both maps a word at a time. A changed tile, map byte,
  map row or sprite sets its byte, and a sprite that changed marks the lines
  it left and the lines it covers now.
- **Each line is then looked up** (`ppu_ldirty`). Its registers are compared
  with what the last call kept for it. Its background row and window row are
  judged once per map row and first column and the verdict kept
  (`ppu_rowdirty`). Each sprite that may cover it has its tiles checked.
- **FAST**: in a frame whose raster writes are the last call's frame's -
  none after none, or the same writes at the same lines (a status bar's
  split every frame: `ppu_logsame`, up to 64 entries kept in `RB_DLOG`) -
  and with the registers as they were at its start, every line's registers
  are known to be the same. The rows and sprites are then judged a map row or a sprite at a
  time (`ppu_dfast`), not a line at a time. With nothing changed at all, no
  line is visited.
- **`RB_DFULL`** = 1, set by the host after it cleared the screen or when its
  buffer holds something else, composes and writes everything, and takes
  the shadows whole.
- **A SCROLL is composed whole** (`RB_DFULL` = 2, set by `rb_renderd`
  itself): when SCY or SCX moved since the last call - as the frame began,
  or in a raster write the last call's frame had not - every line under it
  changes anyway, so the VRAM scan would only find what is composed
  regardless. The shadows are copied instead of compared and every line is
  composed, and `ppu_dput` still writes only those that differ. While it
  scrolls the shadows are not even taken (`RB_DSTALE`): the first still
  frame after it is composed whole once more and takes them (a stale shadow
  could only make a call compose more, never less). The bare harness's
  MODE 7 (`rbbench.py --renderd`, the package's composer timed) read a
  scrolling Super Mario Land's frame, the CPU with it, 26.32 ms before and
  24.40 after on `286-victory`.
  Super Mario Land splits its status bar every frame, so until the log was
  compared it was never FAST: standing still on the Victory's 86Box twin,
  judging 144 lines was 5 ms a draw and the picture 23 frames a second; it
  is 41 now, the judging 0.15 ms.
- **What it costs** an 8088 is the comparison, ~20 ms of 8KB a call. It
  saves ~4 ms of composition for every line it skips. On Super Mario Land it
  composed 38 lines a call of 144, and on Kirby's Dream Land 27.

It took gbclock's do-nothing variant in a Hercules window on MartyPC's 5150
from **43% of real time to 100%**: the drawing had been most of the machine.

`tests/gbdamage.py` is the gate. The bare harness's MODE 6 composes every
third frame both ways, by damage into a buffer it keeps and whole by
`rb_render`, and counts the frames whose pictures differ.
- It runs on gbclock's frame counter (ours), and with `$OS88_GB_ROMS` on
  Super Mario Land and Kirby's Dream Land.
- Taking out the map-row marks fails it on 497 frames of 500.

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
  off, and 4,000 while the recompiler is on, where 2,000 are ~2 ms on a 286
  (each run is an `rb_sched` and an event exit, and halving them took
  Kirby's Dream Land from 85.9% to 90.5% of real time on `286-victory`;
  8,000 read 91.8% and is a mouse byte nearer the edge); and composes and blits a frame when it has caught up or every three
  ticks whatever happens, so a machine that is behind still shows ~6 frames
  a second. F1 puts the game's speed and the frames drawn a second over the
  picture. The joypad is the held keys - arrows, X = A,
  Z = B, Enter = Start, Space = Select - and nothing while another window
  has the keyboard. Reset is the worker's to do (`rb_init` again); Pause
  stops the clock.
- **The writers** both start from `rb_renderd`'s changed lines (section
  13.2), and blit only those, a band for each run of them. A frame that
  changed nothing draws nothing.
  - On a colour display, `OSAPI_GFX_BLITP` with the clip walk, of the four
    planes `rw_planes` makes from those lines (NOT bit 1 three times, then
    NOT bit 0: `rb_render4`'s layout). Damage took Super Mario Land's window
    on 86Box's 286 from 7 frames drawn a second to 28.
  - On a 1bpp display, or where BLITP refuses, `OSAPI_GFX_BLIT1` through a
    2x2 ordered dither: shade 0 lit, 1 a quarter dark, 2 a checkerboard, 3
    dark.
  - F1's line over the picture starts the next draw from every line, as it
    covers or uncovers pixels the game did not change. The damage memory is claimed
  with the game (`rw_dmgclaim`); a buffer that held the other format, a
  reset and full screen all start the next draw from every line. The buffer remembers which
  it holds, and a paint on the other kind of display (the window moved
  between two) is white until the worker's next frame. A refusal dithers
  until the next paint asks BLITP again.
- **Alt+Enter** is Machine > Full Screen (SPEC.md 11.2.1.1, `apps/os88alt.inc`):
  the window's W_ONKEY takes the kernel's synthesised `KEY_ALTENTER`, and the
  bracket's loop polls `os88alt_edge` to leave, seeded so the press that got
  it there does not take it out again. While Alt is held the joypad reads
  nothing, so the Enter of the chord is not the game's Start.
- **Its region is movable**, its worker restartable at the top of its loop;
  `rw_reloc` re-points the six state-block vectors that name its code
  segment. The core, view and ROM claims are pinned.
- **A bad opcode** stops the machine and the window says so.

### 14.1 The log

**Machine > Log keeps a record a second and writes them as text beside
REALBOY.O88**, when the log is turned off or the window closes
(`apps/realboy/rwlog.inc`). It is the field run's instrument: the F1 line
says how a game runs this second, and the log says how it ran for minutes,
on a machine with no debugger.

- **Each log takes a name of its own**: the game's first six letters, two
  digits and `.LOG`, the first such name not already in the folder
  (`SUPER-00.LOG`, `SUPER-01.LOG`; `rw_lname` asks with a zero-length read).
  The folder is the program's own, kept at entry (`rw_pkgdir`). These two
  are the second field run's asks: no folder to make by hand, and no files
  to rename between runs.
- **The head says what ran on what**, in two lines:
  - the game's name, its ROM size, its MBC and its RAM banks, and whether
    it has a battery or a clock;
  - the CPU tier, the display's bits per pixel, which full-screen writer
    the display offers, whether a recompiler cache was claimed, the heap's
    largest run as the load found it, and - for a cartridge in the bank
    cache (section 10.3) - its slots and the banks fetched so far.

- **A record** (32 bytes, the latest 256 kept, about four minutes) holds
  the seconds since the log began, the game's speed and frames run, the
  frames drawn, the lines composed and the lines changed (section 13.2),
  the milliseconds spent drawing and the longest draw, the most frames
  owed, and W or F (window or full screen) with J when the recompiler ran.
- **Where a second went**, which the third field run asked for: of the
  drawing's milliseconds, those comparing VRAM and OAM (**scan**,
  `ppu_dscan`, timed through `rb_dhook`) and those composing lines
  (**cmp**), the rest being the writer's; and the milliseconds running the
  Game Boy (**cpu**, `rw_frame` to its yield). Then four counters: the
  core's event entries, the blocks the recompiler translated, its cache
  flushes and the banks the bank cache fetched (section 10.3). A machine
  whose cpu and draw add up to about 1,000 is the machine's limit; one
  that does not is waiting.
- **And what the user did in that second**, by name: RESET, PAUSE, GO
  (unpaused), FS+ and FS- (into and out of full screen), JIT+ and JIT-
  (Machine > Recompiler), F1.
- **The clock** is the 8253's counter 0 extended by the BIOS tick
  (`apps/os88pit.inc`, 838 ns a count). Inside a rate bracket the counter
  runs at the bracket's divisor, so there it is the hook's period count and
  the counter within the period (`rw_clk`).
- **Who does what.** The worker and the bracket record, in `rw_stat`, once
  a second. Only the UI task writes (SPEC.md 20.6 rule 7). Nothing
  recorded, nothing written.

`tests/gblog.py` takes two logs over the demo, one through the menu and
one at the close, with a pause inside the first. It reads both on the
host: the names, the head, PAUSE and GO, and the speed.

**A second at a time the speed jitters**: it read 89-111% here across a run
that averaged 101.1%. That is the field run's "90 to 110". The frames are
run in bursts, a tick's worth or a draw's worth at a time, and a burst
straddles a second's edge, so one second is credited with frames another
earned. It is the F1 line's sampling, not the game's pace.

## 15. Full screen

Machine > Full Screen runs the machine **on the UI task inside an
`OSAPI_FSX_RUN` bracket** (SPEC.md 53), in `apps/realboy/rwfsx.inc`. The
mode depends on the display (`rw_fspick`, `OSAPI_FSX_CAPS`, asked at every
paint): VGA's mode 0Dh, else a Hercules page, else CGA's 320x200 in four
colours (section 15.1). It is greyed without a game and on a display with
none of the three. Esc leaves; it is looked for between frames and after
every draw, as a turn of frames on an 8088 is longer than a key press.

- **The worker keeps out of the machine.** It is frozen in the bracket, so it
  must not be frozen in the core, or in `rb_render`, whose working memory is
  the view's. It raises `[rw_incore]` at its loop's top and drops it at
  `.sleep` or when its render is done, before it asks for the gfx lock; it
  backs off at the top while `[rw_fsq]` is set. `rw_fsenter` sets `[rw_fsq]`
  and yields until `[rw_incore]` is clear. The worker raises its byte BEFORE
  it reads ours, so once ours is set and its is seen clear, every later entry
  of its sees ours.
- **The screen** is mode 0Dh, 320x200 planar, with the picture at 1x at
  (80, 28). `rb_renderd`'s two shade planes go to VGA planes 0 and 1 as they
  are, a `rep movsw` for each line it changed. It already compared them, so
  the RAM shadow this writer once kept was a second comparison of the same
  bytes. Plane 2 is set everywhere but the picture: the border is DAC
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

### 15.1 Hercules and CGA

**On a Hercules the page is 720x348, with the picture at 2x2 from (200, 26):
320x288.** Each Game Boy pixel is a 2x2 dither of its shade: four lit, three,
a checkerboard, or none. **On a CGA the mode is 320x200 in four colours, with
the picture at 2x1 from (0, 28): 320x144.** The shades are white, cyan,
magenta and black, the BIOS's palette 1.

- **Only the changed lines are written**, straight to the page:
  `rb_renderd`'s lines (section 13.2), so a still frame writes nothing.
- **A table does the work** (`rw_fstab`). A Game Boy byte (eight pixels,
  two shade bits each) is two nibble indices, `(bit 0's four pixels << 4) |
  bit 1's`. Each index is one entry: two bytes on a Hercules (the dither's
  top and bottom rows of those four pixels, doubled), and one word on a CGA
  (the four pixels doubled in four colours).
- **The page is cleared at entry**, and F1's speed line goes under the
  picture in the glyphs' own bits.

`tests/gbwindow.py` reads both out of the card's memory, against the same
dmg-acid2 reference as the window, on MartyPC's 5150 Hercules and CGA.

### 15.2 When a frame is drawn

**The game keeps its speed; the picture takes what is left.** The draw clock
is `rw_clk`'s, 838 ns a count, and each draw measures itself (`rw_timed`).
A draw is due (`rw_drawdue`) in one of two cases:
- **The game has caught up**: once as long as the last draw took has passed
  since it ended. So drawing takes at most half the machine.
- **The game is behind**: another such length later still. So drawing takes
  a third of the machine and the rest goes to catching up.
- **On a 286** a draw is milliseconds, and the rule comes down to "every
  frame it has caught up".
- **On an 8088** a draw is a large part of a second, and the picture rate
  falls while the game holds its speed.

**The first field run is why "behind" is a share and not a period.** The
first form drew every three ticks whenever the game was behind at all. On
the Victory, Super Mario Land slips under 100% for a moment with an enemy
on screen as it scrolls, and that dropped it from ~30 frames drawn to 4.
The clock was a tick then, 55 ms, which could not tell a 286's draw from
nothing.

**A draw that a clock change ran across counts for nothing.** The window's
worker can sit inside a draw, waiting for the gfx lock, for the whole of a
full-screen session. It then measured a 34-second "draw", and put its next
draw 34 seconds out: the second field run's log showed a window that drew
nothing after leaving full screen. `rw_drawnow` counts the clock changes
(`[rw_dgen]`), and `rw_timed` keeps nothing from a draw that saw one.

**Catching up has a limit.** A machine that falls behind catches up at most
`RW_BEHIND` (30) frames, half a second. That is longer than an 8088's draw,
whose frames would otherwise be lost. A fresh start, and the change of clock
going into or out of full screen, make the next draw due at once
(`rw_drawnow`).

The window and full screen keep the same rules. In full screen, Esc and
Alt+Enter are also looked for after each draw.

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
- The read-modify-writes of `(HL)` - INC/DEC `(HL)` and the CB group on it
  but BIT - carry the read's and the write's slow paths both and are over
  80 bytes, so they are chosen by operand too (`rbgen.rmw_lines`): the
  address is checked once for what both paths take directly, 8000-FEFF and
  FF80-FFFE, and everything else - ROM, the MBC, I/O, IE - goes to
  `tr_int` at the instruction itself, the template's IMM16 being its PC and
  BP exact (it is not pure). They used to end the block, and the interpreter
  ran on from there to the next branch and `tr_enter`: Kirby's Dream Land's
  sound driver alone is a DEC (HL) per channel per frame. With them, the CPU
  alone on `286-victory` went from 9.06 to 8.19 ms a frame on Kirby's Dream
  Land and from 7.19 to 6.91 on Super Mario Land. `tools/gbprof/gbrmw.asm`
  (`gbcpu`) runs them on WRAM and on TMA and must see the two agree.
- A template over 80 bytes is the interpreter's: LD (nn),SP.
- `LD (C),A` and `LD A,(C)` have templates of their own (rbgen's JIT arm):
  C 80h and up is HRAM, one access through SS with SI = C, and only I/O and
  IE take the general path.
- A memory template keeps the slow path's stub BEFORE the fast access, so
  the common case takes one jump and none over the stub; the 286 here is
  bound by fetching code bytes, so a jump and its bytes are the cost. The
  stub is two instructions, `mov word [ss:S_RET],.k / jmp rd_sN` (or
  `wr_sN`), N the M-cycle of the instruction the access is in: the shared
  `rd_s1`-`rd_s3` answer ROMX at once and `wr_s1`-`wr_s4` hand the MBC on,
  and only for an I/O register (`rw_io`) is BP taken back by N around
  `io_rd`/`io_wr` and forward by N after (`S_ATN`), not restored, since an
  I/O write may reschedule it. That took eight bytes out of every memory
  access the cache holds - and the cache is what binds: Super Mario Land
  had come to flush it twice in play instead of once.
- `LDH (n)` and `LD (nn)` on an address the interpreter's own fast path takes
  directly - HRAM, WRAM, VRAM, bank 0 - are chosen by operand: one `MOV`
  through SS and the M-cycles (`rbgen.EXTRA`).

### 16.1.1 Pure templates share their M-cycles

A template whose last three bytes are `sub bp,n`, that names BP nowhere
else, has no tail and jumps nowhere out of itself is **pure** (`rbtmpl.py`,
flags bit 3; 398 of 445): nothing in it reads the time, so the translator
copies it without its `sub bp,n` and adds n to the block's pending count,
which it takes off BP in one `sub` (`rt_flushbp`) before the next template
that is not pure, a control transfer or the block's fall-through. Super
Mario Land, the CPU alone: 9.57 to 9.29 ms a frame.

### 16.2 The cache

The code goes into a 64KB segment of its own. It holds copies of the core's
helper tails - the slots `rbgen.TAILS` uses - at their own offsets, so a
template reaches every helper with a near jump; ~58KB is left for code, in
the free ranges `rbtmpl.py` lists. **The block table has a 16KB segment of
its own** (`S_JITHSEG`), in the package the 16KB after the cache in one 80KB
claim and in the harness 8C00h. It was slots 00-3F of the cache, and the
cache had ~44KB for code: Kirby's Dream Land's working set is ~500 blocks
of ~96 bytes, so in the package it flushed every five seconds and ran no
faster recompiled than interpreted (61.7% of real time against 62%). With
the table out, 0 flushes in 30 seconds and **84.4%**; the bank cache it
shares the heap with went from eight slots to seven. A helper
that leaves for rbsys records its CS in `S_RETFAR` first, so rbsys comes back
to the copy that called it, and every way out of the cache to the
interpreter is a far jump. When the cache is full everything is forgotten
and translation starts again. The package claims it on a 286 or later, after
the ROM, and the load's plan keeps 80KB for it - a cartridge that would not
leave it goes to the bank cache (section 10.3); without the memory there is
no recompiler.

### 16.3 Blocks and tr_enter

A block is straight-line code from a PC to the first control transfer, at
most 40 instructions, never across 4000h or 8000h, keyed by its PC and - in
4000-7FFF - the ROM bank. `tr_enter` finds it: a direct-mapped table of 2,048
entries (PC, bank key, a count, the block's offset), indexed by the PC's low
11 bits with the bank key and **the PC's top five bits** folded into the low
byte - so blocks 2KB apart, which bank 0 and every bank of 4000-7FFF are
full of, do not take turns at one slot. That fold took Kirby's Dream Land,
the CPU alone, from 15.15 to 13.73 ms a frame on 86Box's 286.

**A slot has a NEIGHBOUR** (its index XOR 1), which `tr_new` and `tr_link`
both look in when the slot holds another key, and a new key
takes whichever of the two is worth less - a counting entry before a
translated one, and of two counting ones the colder (`tr_new2`); the
translator writes a block into the slot its PC counted in (`S_JITSLOT`).
Counters in the package showed why: with one slot, two hot PCs that shared
it took it from each other before either was counted to `RB_JITHOT`, so
both ran interpreted for ever, and every exit to them missed its link -
in Super Mario Land walking, 10 lost slots, 17 entries counting and 17
failed links a frame. With the neighbour the CPU alone (`rbbench.py --box
286-victory`) went from 9.29 to 7.32 ms a frame on Super Mario Land and from
11.35 to 9.75 on Kirby's Dream Land. **A PC is translated
only on its 64th entry** (`RB_JITHOT`; it was 16), so code that runs a few
times is interpreted and never takes the cache's room; a translated entry
gives its slot up only after 64 others have asked for it. At 16 Kirby's
Dream Land walking translated 2,933 blocks in 15 seconds and flushed the
cache 7 times; at 64, 605 and once. **A flush forgets everything**, the table with the code. Keeping what was
hot (an entry that had a block counting again from near `RB_JITHOT`) was
tried and REFUSED: on the bare harness it took Kirby's Dream Land from 7.64
to 7.14 ms a frame, but in the package on `286-victory`, the recompiler
forced on, it went from 61.7% of real time to 45.3% (counting again from
`RB_JITHOT - 16`) and 19.8% (`- 1`), with 22 and 83 flushes in 30 seconds
against 6 - a working set bigger than the cache refills it at once after
every flush when nothing has to earn its place again. Tried a second time
once the block table had left the cache and the working set fitted (a flush
every 15-20 seconds, from code a level left behind): counting again from
`RB_JITHOT - 8` read 85.9% over 40 seconds against the plain flush's 93.2%. RAM is never translated - the interpreter's own
control transfers stay in the interpreter there (`JDISPATCH`) - **but HRAM
is** (FF80-FFFE, `tr_hram`), where games keep their OAM DMA routine and
thunks such as Looney Tunes' `LD (DE),A / RET` that a `RST` jumps to in a
copy loop: an HRAM block is at most 16 bytes and is entered through a GUARD
(`rt_guard`) that compares its bytes with HRAM as it is now, and a block
whose bytes changed is forgotten (`tr_stale`) and its code interpreted.
`gbrmw` rewrites a routine there once it has been translated. **With no
recompiler** - an 8088, no memory for the cache, or Machine > Recompiler off
- `rt_dispatch` writes the plain dispatch over the first five bytes of all
45 `JDISPATCH` sites (rbtmpl.py lists them), so the interpreter is the one
there was before the recompiler, and writes them back when it is turned on. Translated code does not keep DS;
`tr_int` sets it for SI before it dispatches.

### 16.4 Chaining

An exit to a constant address in bank 0 is `mov dx,SITE / jmp tr_lsite`,
six bytes that `tr_link` rewrites into `jmp near` the block once it is
translated, or that the translator writes so at once when it is already
there. An exit into 4000-7FFF gets eleven: a check of `S_BANK` and the jump,
falling onto the exit's own `mov si,T / jmp tr_enter` when the bank is
another. An exit sets SI only on the ways that need it - the event's
(`jmp far [ss:S_EVVEC]`) and the bank's fall - and not before its `js`, so
a chained exit is the event check and the jump: `tr_lsite` takes T out of
the exit's own code (the `mov si,T` after its jump, SITE + 7, or SITE + 12
after the five spare bytes of one into a bank). With the stubs below, it
took the CPU alone on `286-victory` from 6.77 to 6.59 ms a frame on Super
Mario Land, 7.87 to 7.64 on Kirby's Dream Land and 2.01 to 1.97 on Dr.
Mario. Every
`RET` carries an inline cache, `cmp si,PC / jne / cmp byte [ss:S_BANK],B /
jne / jmp near BLOCK`, else `mov dx,SITE / jmp tr_link`: `tr_link` looks the
return up as it does an exit and, seeing the site's `cmp` (81h) where an
exit has its `mov dx`, fills the cache with the last return (`tr_rpatch`) -
the bank check made a `jmp short` over itself when the block is in bank 0.
A routine called in a loop then returns without a lookup. It once cached
bank-0 returns only, and every return into 4000-7FFF went the whole way
round `tr_enter`: 35 a frame in Kirby's Dream Land walking, and caching them
took the CPU alone from 9.75 to 9.06 ms a frame on `286-victory`.

### 16.5 Guards

Translated code does not keep SI either, so a store that can reach the I/O
path must say where it is: `rb_irqnow` takes an interrupt inside an IF or IE
write by moving SI to the vector. A store whose address is not known - LD
(HL),r, LD (DE),A, LD (C),A and the rest of `rbgen.SELFGUARD` - GUARDS
ITSELF, in its slow path, which is the only one that can take an interrupt
or reach the MBC: SI = NEXT (the template's IMM16, record flag 16) before
`wr_slow`, and after it the block is left through `tr_enter` when SI moved
or the write went below 8000h, where the bank may have changed. The fast
path, a write to RAM, carries no guard at all; the guards around every such
store used to be 12 bytes, and 23 in a block running from 4000-7FFF, and
taking them out of the RAM path took the CPU alone on `286-victory` from
8.19 to 7.87 ms a frame on Kirby's Dream Land and from 6.91 to 6.77 on Super
Mario Land. `LDH`/`LD (nn)` to IF or IE keep `mov si,NEXT` and a check after;
a block running from 4000-7FFF compares the bank after an `LD (nn),A` below
8000h, and leaves when it changed.

### 16.6 What it buys, MEASURED on 86Box's 286

gbclock's busy loop costs **13.95 clocks a busy M-cycle against the
interpreter's 26.2**. Super Mario Land, the CPU alone on gbprof's script, is
11.67 ms a frame against 13.04; in the package, in play, **80.1% of real
time in the window and 76.0% full screen**, against 59.5% and 58.0%
interpreted. docs/reports/REALBOY-JIT-2026-10-19.md has the record.

**With drawing by damage and the draw clock** (sections 13.2 and 15.2),
Super Mario Land runs at **100.7% in the window and 101.5% full screen**,
drawing 7 and 34 frames a second. Kirby's Dream Land runs at 31.6% and
37.2%, bound by the Game Boy CPU: 48% of its time is in translated code and
32% in the interpreter and `tr_enter`. **That is Kirby walking**, and walking
is what costs: standing in the same scene it runs at **78.7%** in the window
drawing 16 frames a second, and walking right 35.8% drawing 2 - the scroll's
own code, not the picture (`rbwin.py`, the hash fold of section 16.3 in).
docs/reports/REALBOY-DAMAGE-2026-10-19.md has the record.

### 16.7 Auto: the recompiler when it is the cheaper

**The recompiler is not always faster.** On the Victory's 86Box twin
(`vm/286-victory`) Kirby's Dream Land walking ran at **59% of real time
interpreted and 46-51% recompiled**: its hot code is broad (no block over
3% of the translated samples) and a block ends at every branch, so the
blocks are short and their entries and exits (`tr_enter` alone 11%) cost
more than the dispatch they save. Super Mario Land is the other way round.
So Machine > Recompiler has three settings, **Auto** (the default), On and
Off, and Auto measures (`rw_jitauto`, once a second from `rw_stat`):

- a window of two seconds with the recompiler that is NOT timed, its cache
  filling there - a cold cache timed it dearer than it was, and that alone
  had Kirby's Dream Land interpreted at 62% when it ran recompiled at 86%;
- four windows of two seconds - with the recompiler, without, with,
  without - each's cost a frame being the machine's own time (`rw_frame` to
  its yield) over the frames it ran;
- then the recompiler unless the interpreter was cheaper by an eighth or
  more (a title screen times both alike, and a near tie there once handed
  Super Mario Land's levels to the interpreter), for a minute - five when
  the recompiler won by a quarter or more, since every timing spends four
  seconds half of them on the slower - and the windows again, since a
  game's working set is a level's. An interpreter's verdict holds the
  minute only.

Turning it off keeps the cache, and turning it back on (`rt_resume`) forgets
nothing: the cache holds only ROM's translations, keyed by PC and bank, and
neither changes while it is off. With the block table out of the cache
(16.2), Auto holds the recompiler on both: Kirby's Dream Land at 85.9% of
real time and Super Mario Land at 100%.

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
  - **The channel playing stays** while it sounds, unless the other is
    louder by 4 or more (`[rw_sch]`). Without that, two voices whose
    envelopes cross made the one speaker hop between melody and harmony
    note by note, which the first field run heard as "very odd".
  - It passes that pitch to `OSAPI_SND_TONE`, but only when the pitch has
    changed. Volume 0, and a pitch outside 20 to 15,000 Hz, are silence.
  - A refusal (another owner of the speaker) is asked again the next frame.
  - A paused or stopped machine turns the tone off (`rw_quiet`).
- **The pitch is exact and the timing is the game's.** Notes follow the
  game's frames. A game running at half speed plays its tune at half speed,
  at the right pitch.

`tests/gbsound.py` is the gate. GBTONE.GB (`tools/gbprof/gbtone.asm`,
assembled by `tools/gbours.py` with the pinned rgbds) plays a trigger, a DAC
switched off, and a length counter that runs out. The row captures
MartyPC's speaker and asserts all three. With the length counter broken it
fails, naming the counter.

## 18. The 5150 demo

**`GBDEMO.GB` is RealBoy's own Game Boy ROM, written for an IBM PC 5150**
the way WireBall is written for it. It is assembled with the pinned rgbds by
`tools/gbours.py` from `tools/gbprof/gbdemo.asm`, and it runs on a real Game
Boy as well. What it does:
- It draws a still scene once, with the LCD off: a title, three lines of
  text, a band of the four shades and a ground strip.
- One 8x8 sprite, a ball, bounces on the ground in a 40-frame parabola, and
  between the walls a pixel a frame.
- A clock, MM:SS, is four map bytes rewritten once a second.
- Square channel 2 blips at 659 Hz each time the ball lands, and its length
  counter ends the blip.
- It HALTs for the rest of every frame.

So a frame costs the core a few dozen instructions. Drawing it costs the
lines the ball crossed, and once a second the clock's (section 13.2).

**MEASURED on MartyPC's 5150 with a Hercules** (cycle-exact, so these are
the 5150's numbers): **1.000 of real time** full screen, drawing 4 frames a
second; 0.999 in a window, at 3. The draw clock of section 15.2 is what
holds the game at full speed, and with it always due the game falls to
0.388. `tests/gbdemo.py` is the gate.

On a real machine the F1 line reads the same two numbers: the game's speed
and the frames drawn a second.

## 19. The disk and the Wire listing

**`make realboydisk`** writes the package's floppy in all four geometries:
`build/realboy.img` (1.44MB), `realboy720.img`, `realboy120.img` and
`realboy360.img`, each `--verify`'d.
- **The REALBOY folder holds three files**: `REALBOY.O88`, `GBDEMO.GB` and
  `README.TXT`. That is 64 of a 360KB disk's 354 clusters, so there is room
  for the user's own games.
- **It is on demand**, because `GBDEMO.GB` is assembled with the pinned
  rgbds, which is fetched and built on first use. The everything set
  (`make allapps`) and the live media carry the same folder.
- **No game ships.** A cartridge is the user's own.

**The Wire record is PREPARED and NOT PUBLISHED.** It goes in os8088-web's
`data/wire.json` when the owner says go, and that repository is outside this
one. It was validated by packing it with `tools/os88wire.py --pack` and
reading the result back with `--verify`:

| field | value |
|---|---|
| `stem` | `REALBOY` (7 characters, so a `REALBOY.TXT` sidecar fits the 11-character field) |
| `title` | `RealBoy` |
| `kind` | 0 (Applications) |
| `tier` | **1** (286): the primary target, and where the measured speed is |
| `flags` | `new`. `WF_DISK` is derived: the package carries parts, and the record has sidecars |
| `files` | `REALBOY.O88`, `GBDEMO.GB`, and `{name: REALBOY.TXT, source: apps/realboy/README.TXT}` - the README under a name of its own, as `public/wire/pkg/` is one flat directory (APPLE2-SPEC section 18.2) |
| `summary` | `A Game Boy (DMG) emulator: your own cartridges, in a window or full screen.` |
| `description` | `A Game Boy for your PC. Bring your own cartridges. Near full speed on a 12MHz 286; its demo runs full speed on a 5150.` (5 lines at 27) |

The record is 27,407 bytes of package, 62,566 with its sidecars. The
description's "near full speed" stands on 86Box's 286 figures (section
16.6), not yet on the owner's iron. It is the field run's to confirm or to
correct before the record is published.
