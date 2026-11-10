# A PicoMEM 2's disk by DMA - what the card can do, and the plan

**Status: WAVE 0 BUILT, AWAITING THE IRON (2026-11-10)** - the probe
firmware and `tests/pm2dma` (section 10), and a finding that changes the
question (section 2.1). `os8088-pm-debug` has `pm-pr` merged in (section 9).
**The owner's answers are in
(section 11): S1, with NO sound stutter as its acceptance; nobody waits
on Freddy; two machine shapes, the second a bonus.** The firmware half lives in
Elendilon/ISA-PicoMEM on a branch of its own cut from `pm-pr` (section 9);
`pm-pr` itself is not touched. The os8088 half is small and comes last.

**The answer in five lines:**

1. **The gap is the CPU, not the rate.** `pm-pr`'s firmware reads as fast as
   an ST-225 feeds a clip, but every byte still crosses the bus as the
   PC's own `rep movsw` out of the card's window
   (`PCC_Do_MemCopyW_512b`), ~12.7 ms of an eight-sector call on the twin,
   while Bolt's decode and sound feed want ~43% of the same CPU
   (docs/reports/PICOMEM2-STUTTER-2026-11-07.md, last section). An ST-225's
   bytes move by DMA and cost the CPU only the stolen bus cycles.
2. **The card has ONE DMA request line**, jumpered to channel 1 or 3, and
   its only acknowledge input is `PIN_DMAW` = DACK **and IOW** - the
   memory-to-card direction its Sound Blaster uses. A disk READ is the other
   direction (IOR + MEMW). There is no DACK-and-IOR pin.
3. **It can be done without one.** The bus loop already decodes the four
   control lines as a nibble, and MEMW + IOR together (value 6) is a cycle
   no CPU ever makes: only an 8237 *write transfer* does. With the card's
   DRQ up and no other channel moving device-to-memory, that cycle is the
   card's. **But the source says the 2.0 probably never sees that IOR**
   (section 2.1): its firmware reads no AEN, so the board must gate the I/O
   strobes with AEN, and then the card sees only the transfer's MEMW - which
   it can still answer, with a timing question attached. **Wave 0 is a bench
   test on the 5150 that settles which, before anything else is written.**
4. **One line means the card's Sound Blaster and its disk SHARE a channel.**
   Video Battle and Video Player stream SB sound while they read, so a
   DMA disk that only works with the SB idle buys nothing for them. Sharing
   is wave 3 and the hard part: S1, time-sharing the line, chosen, under a
   rule that the card's SB FIFO is never allowed to run dry (section 6).
5. **Off is the default and stays bit-identical.** A `PICOMEM.CFG` byte
   that is already spare (`Spare2`) selects DMA; with it clear the int 13h
   is today's `pm-pr` path byte for byte. The 1.x builds as now - it has no
   DRQ pin and none of this compiles there.

## 1. What was there before

No earlier disk-DMA plan is committed - not in this repository (every
`docs/plans/` file, both branches) and not on any of the fork's three
branches. What exists and is reused:

- **`tests/pmdma` / PMDMA** (docs/FIELD-NOTES.md 66) is the precedent for
  a field instrument that programs the 8237 and asks the card what it saw.
  It is about the 1.x's *virtual* SB DMA, not the disk.
- **The stutter report's last paragraph** names the one zero-copy path the
  stock firmware has (`MEM_RAM`: a buffer in RAM the card itself emulates)
  and why it does not help 5150 #1 (its conventional memory is a
  SixPakPlus).
- **The twin already has real DMA for the SB direction**
  (`tools/picomem/shim/pmhost.cpp`, `host.dma_req` / `pm_dma_byte`, 86Box's
  8237), which is most of what the disk direction needs in the emulator.

## 2. The hardware, as the source says it is

From `pm-pr` (`6204e0d`): `src/pm_boards/pm20.h`,
`src/isa_iomem_m2_v15.pio`, `src/pm_isa_rp2350_m2_v15.h`, README.

| signal | GPIO | what it is |
|---|---|---|
| `PIN_DRQ` | 38 | the card's one DMA request, active high, to DRQ1 or DRQ3 by jumper ("DMA Support: Can select DMA 1 or 3 via jumper") |
| `PIN_DMAW` | 39 | **0 during a DMA I/O WRITE** - DACK and IOW combined on the board. `isa_dma_w_tc` waits on it, then samples D0-D7 at IOW's rising edge |
| `PIN_TC` | 37 | terminal count, inverted, 2.0 only. Global on the bus: asserted on the last cycle of WHICHEVER channel ends |
| control nibble | 28-31 | MEMR, MEMW, IOR, IOW, read by core 1 off the address mux (`DetectCtrlLoop`) |

**What a disk read needs.** The 8237's *write transfer* (mode bits 3-2 =
01) moves device-to-memory: it puts the memory address on the bus, raises
AEN, and asserts **IOR** (to the device holding DACK) and **MEMW** (to
memory) together. The card sees IOR but not DACK. Core 1's dispatcher
computes the nibble and, for anything above 3, treats the cycle as I/O
(`bgt ISA_Do_IO`) and then falls through both `CTRL_IOW` and `CTRL_IOR`:
today a nibble of 6 is IGNORED. Nothing else on an XT makes it:

- a CPU cycle asserts exactly one of the four;
- refresh (channel 0, mode 58h) and the card's own SB are *read*
  transfers: MEMR + IOW, nibble 9;
- a floppy read (channel 2) or a real MFM controller's read (usually 3) is
  a write transfer: **nibble 6**. This is the one collision, and it cannot
  happen while the card's own int 13h is running, because the BIOS's disk
  calls are serial and os8088's are too (section 7, R2).

So: **arm on DRQ, answer every nibble-6 cycle from the card's buffer,
disarm at the count.** The data goes out through the existing read path of
`isa_bus` (`mov pindirs, ~null` / `out pins, 8` / wait for the strobe), as
an I/O read already does; IOCHRDY (`PIN_IORDY`, already raised for slow
cycles) stretches the cycle if core 1 needs the time, and the XT's 8237
honours I/O CH RDY on DMA cycles.

### 2.1 What a second look at the source says: the card sees MEMW, not IOR

**The 2.0's bus code never reads AEN.** The 1.x's PIO jumps on an AEN pin
to "ignore cycles during DMA" (`isa_iomem_m1.pio`); the 2.0's
(`isa_iomem_m2_v15.pio`) has the pin commented out, and core 1 decodes an
I/O cycle from ten address bits and the four strobes alone. Yet a 2.0 does
not hear the XT's refresh - channel 0, MEMR + IOW, every 15 us, at every
low address in turn - as I/O writes to its AdLib and SB ports, and it needs
a separate **DACK-and-IOW** signal for its own Sound Blaster's DMA. Both
make sense only if **the board gates IOR and IOW with AEN in hardware**.

If so, during a write transfer the card sees **MEMW alone** (nibble 2), at
the address the 8237 counts - never nibble 6, and never IOR. The plan above
survives in a different shape: **answer the transfer's MEMW** at the
buffer's next expected address while DRQ is up. A CPU write to exactly that
address at that moment does not happen (the PC is waiting in the card
BIOS's loop), so the address is the signature the missing DACK was.

**What that costs is a timing question.** The 8237's normal (late) write
asserts IOR a clock before MEMW, so a real device's data is on the bus
before memory starts writing. The card learns of the cycle only AT MEMW,
and memory may latch early: DRAM written early-write latches at CAS, a
delay-line step after the strobe. The card answers a memory READ well
inside an 8088 cycle today, so it may be fast enough; on the motherboard,
on a SixPakPlus and on the card's own RAM the answer can differ. IOCHRDY
does not help, because it stretches the cycle after the latch. Two ways
out if it is too slow: the 8237's EXTENDED write (command register bit 5)
moves MEMW a clock earlier and is a setting, not a wire - but it is
global to the 8237 and the BIOS's floppy runs with it off; or a wire from
the slot's DACK to a spare GPIO (section 6.4's kind of modification),
which gives the card the cycle from its start.

The probe (section 10, wave 0) asks all of it at once: it counts every
strobe the card sees while its DRQ is up, and drives its pattern both ways
- on the MEMW (mode 1) and as an I/O read (mode 2).

**What the source cannot say (H1).** The 2.0 schematic is not in the fork
(`hw/` has only `PicoMEM1.14.pdf`). If the data transceiver's enable or
direction is gated by AEN or by an address decode in hardware, the card
cannot drive the bus during a DMA cycle however the firmware is written.
README's "Support DMA from PicoMEM emulated RAM" says the board answers
*memory reads* under AEN (a channel reading the card's RAM), which is
encouraging but is the MEMR strobe, not IOR. Wave 0 answers H1 on the
iron; Freddy can answer it from the schematic in one line, and it is worth
asking him first.

**Single mode, and the price.** In single-transfer mode the 8237 gives the
CPU a bus cycle between every byte however long DRQ stays up, so the card
may hold DRQ for a whole run. On a 4.77 MHz XT a DMA cycle is ~5 clocks
with the DMA wait state; an unpaced run moves roughly 400-450 KB/s and
leaves the CPU about half its bus while it runs. A 4 KB run is ~9-10 ms of
half-speed CPU against ~12 ms of no CPU at all today. **These are
estimates from the 8237's cycle, not measurements**; wave 2 measures them,
and a pacing knob (DRQ duty) is in the design so the trade can be set
rather than argued.

## 3. Writes are the easy direction, and the less useful one

A disk WRITE is a *read* transfer (MEMR + IOW + DACK): `PIN_DMAW` sees it,
`isa_dma_w_tc` already samples it, and the TC flag already comes back. The
hardware question H1 does not arise. But nothing os8088 streams is a write
- a save is seconds of floppy-class work at most - so writes are wave 4,
taken only when the read path is in.

## 4. How the transfer is driven

Everything happens inside the card's own int 13h, so DOS programs gain
exactly what os8088 gains and the kernel needs almost nothing (section 8).

The PC side of a card int 13h is already a command loop
(`pmbios/pm_cmd.asm`, `BIOS_DoPCCMD`): the PC executes what the Pico asks
(copy 512 bytes, OUT a port, read the 8237's channel) **with interrupts
enabled** (`PM_Int13h`'s STI), so os8088's IRQ0 hook already runs between
commands - that is what `pm-pr`'s wait hook was for.

The DMA read path, per run (the 1/2/4-sector runs `pm-pr` already reads):

1. Read the run from the SD into a card buffer, as now.
2. One new PC command, **`PCC_DMA_SETUP`** (channel, mode 44h + channel =
   single / increment / write / no auto-init, page, address, count): mask,
   clear the flip-flop, program, unmask, in ONE round trip. `PCC_OUT8`
   could do it in eight, which is eight command handshakes; the new entry
   is a few dozen bytes of the card BIOS.
3. Arm core 1, raise DRQ, keep mixing (`pm_pccmd_wait_hook`) and read the
   NEXT run from the SD while the 8237 moves this one. The PC sits in its
   command loop; the hook decodes.
4. At the count (core 1's) - cross-checked by TC - drop DRQ, disarm, and
   let the next `PCC_DMA_SETUP` or the end of the call mask the channel.

Fallbacks, each per run, each to today's copy:

- the buffer is RAM **the card emulates** (`MEM_RAM`): already zero-copy -
  write it directly, no DMA;
- PSRAM or EMS (`MEM_PSRAM` / `MEM_EMS`) or a run that mixes types: the
  8237 cycle would land on the card itself; copy as now;
- a run that crosses a 64KB physical page: split into two DMA programs (an
  ST-225's BIOS answers 09h there; the card can be kinder, and the os8088
  kernel never asks it, SPEC.md 18.91.4);
- the SB streaming on the same channel until wave 3 is in: copy as now.

## 5. Selecting it - the old path stays

- **`PM_Config->Spare2` becomes `HDD_DMA`**: 0 = off (the default and the
  value every existing `PICOMEM.CFG` already holds), 1 = channel 1, 3 =
  channel 3 - shared with the card's SB on the jumper's line (shape A,
  section 6.4) - and 83h = channel 3 on a line of its own (shape B, the
  bonus, which needs a board modification). The byte is spare in June's `PMCFG_t`, so no file moves and
  the 1.x's "delete `PICOMEM.CFG`" trap does not return. The setup menu
  (`pmbios/bios_menu.asm`) gets the one line; it must say "the DMA jumper's
  channel", because the firmware cannot read the jumper.
- **The card's SB needs the same fact** - June's firmware has no SB DMA
  setting at all ("defaults are used") and os8088 sets the SB's channel
  through the DSP (SPEC.md 34.10). A user who puts the jumper on 3 to free
  1 must get both the SB and the disk on 3; the setup screen says so.
- **The capability goes in BX.** `pm-pr` answers function 3 with
  BX = 8088h ("mixes while it waits"). DMA on answers **8089h**; off answers
  8088h, so an os8088 that reads 8089h knows DMA is on *now*, not merely
  compiled in.
- **Who chooses off**: anyone whose jumper is not on a free channel - the
  usual case is a real MFM controller on 3 AND an SB game that wants 1, or
  a machine whose other card already uses the channel. The old path costs
  nothing to keep: it is the code that is there.

**The 1.x still builds.** Every firmware change sits under
`#if BOARD_PM20` (the 1.x has no `PIN_DRQ`, `PIN_TC` or `isa_dma_w_tc`);
the card BIOS's new command is shared source and inert on a 1.x, but the
1.x's `pmbios.bin` must still fit its ROM window - checked at every wave,
along with both reproducible builds (`firmware/picomem1/`,
`firmware/picomem2/`'s READMEs, `tools/picomem/build.sh` for both twins).

## 6. The Sound Blaster on the same line - the decision

Both of the card's DMA clients pull the one DRQ, and the 8237 channel has
one address and one count. While SOUND.DRV's ring plays (auto-init, the
whole ring as base and count), a disk transfer on that channel overwrites
both. Three ways through, cheapest first:

| | how | cost | gives Video Battle |
|---|---|---|---|
| **S3** | DMA only when the SB's stream is idle on that channel; copy otherwise | none beyond wave 1 | **nothing** - it always plays sound |
| **S1** | time-share: the card stops its SB requests (its FIFO is 1,024 samples, ~46 ms at 22 kHz), the PC saves the channel (`PCC_DMA_READ`, already in the BIOS), the disk runs, the PC restores. The 8237 cannot restore an auto-init ring mid-way (writing the address writes base AND current), so the restore programs the TAIL single-shot, and at its TC the card asks the PC, through its own interrupt as the 1.x's virtual DMA does (`IRQ_R_DMACOPY`'s "new DMA regs after the copy"), to put the ring back | the most firmware, all of it in the card; a card interrupt only when a ring's tail runs out before the next disk call (6.1), on the card's jumpered line (June: IRQ 7 fixed) | **everything**, with the SB on real DMA |
| **S2** | with HDD DMA on, run the card's SB on the 1.x's *virtual* DMA (the `USE_HWDMA=0` code, made a runtime choice on the 2.0): the line is the disk's alone | the SB's own data crosses by CPU copies (~22 KB/s, ~5% of an XT); the virtual path's DOS-game compatibility is upstream's "low", though os8088's SOUND.DRV is proven on it (the 1.x) | everything except the SB's copies |

**Chosen: S1 (the owner, 2026-11-10), on one condition: it may not
stutter.** No dropout and no stutter in the card's SB while the disk moves
by DMA - the defect `pm-pr` exists to cure is not to be reintroduced by
the next thing. S3 is wave 1's behaviour so wave 1 ships something
correct; S2 stays the fallback if S1's restore proves fragile on the iron.

### 6.1 Why S1 can be made stutter-free, and the rule that makes it so

A dropout is exactly one event: **the card's SB FIFO runs dry**. The FIFO
is mixed into the card's output at the sample rate and refilled by the
SB's DMA; while the disk owns the line the refill stops and the FIFO only
drains. On `pm-pr` it is **2,048 samples** (`AUDIO_FIFO_SIZE`), ~92 ms at
os8088's 22,222 Hz. Everything below keeps the line away from the SB for a
bounded time that the FIFO covers with margin, and the card - which is the
only party that knows both the FIFO's level and the disk's progress -
enforces it, rather than any timing the PC is trusted to keep.

**The switch is not instant, and that is what the rule is about.** Only
the PC can program the 8237, and the PC runs the card's commands only
between interrupts: a `PCC_DMA_SETUP` that hands the line back to the SB
can wait behind a whole run of os8088's IRQ0 hook (Video Battle's period
is 13.7 ms, and a decode can fill most of it). So the time the SB is
starved is *the disk burst plus the worst wait for the switch back*, and
the rule is written in those terms:

- **Watermark rule.** The card starts a disk burst only when
  `FIFO level >= burst time + T_switch + margin`, where `T_switch` is the
  longest hold the PC may put between two commands (a config constant,
  default 20 ms, above any os8088 hook) and the margin is a further 10 ms.
  At 92 ms of FIFO that leaves bursts of up to ~60 ms - several
  eight-sector calls' worth at the rates in section 2.
- **Top up first.** If the FIFO is below the mark, the disk waits with
  the line given to the SB until it is above it - the call takes a little
  longer and the sound does not notice.
- **Bursts, not calls.** A long call (`pm-pr` lifts the run cap, so a call
  can be a cylinder) is cut into bursts that each satisfy the rule, with
  the SB's line restored and the FIFO topped up between them. Each
  hand-over is one command round trip, inside the same int 13h.
- **The FIFO may grow.** If wave 3's measurements leave the margin thin,
  4,096 samples on the 2.0 is 2 KB of a 512 KB RAM of which ~130 KB is
  free; the 1.x already runs 2,048.

**Leaving the call.** After the last burst the SB has its line back but
the 8237 cannot be put back as it was: writing an address writes the
channel's base AND current, so an auto-init ring cannot be restored part
way round. The card restores the ring's **tail** single-shot (current
address and count, which it knows - it counted every byte the SB took
since the ring was programmed, and snoops every 8237 write in
`dev_dma.cpp`). Then:

- **Usually the next int 13h repairs it for free.** A stream that reads
  does so every few tens of ms, and a 16 KB player ring (SPEC.md 34,
  `SBL_PLAYKB`) lasts ~740 ms at 22 kHz, so the next call's first switch
  re-programs the ring whole (base = ring start, auto-init) at the position
  the tail reached.
- **Otherwise the card's interrupt does.** If the tail's TC comes first
  (no disk call in time), the SB stops requesting and the card raises its
  own interrupt - the mechanism the 1.x's virtual DMA already uses to have
  the PC rewrite the 8237 (`IRQ_R_DMACOPY`'s "new regs after the copy") -
  with the whole FIFO, ~92 ms, as its latency budget against the PC's
  20 ms worst hold.
- **Rejected: fast-forwarding.** Re-programming the whole ring and burning
  dummy DMA reads up to the right offset needs no interrupt, but costs up
  to a ring's length of bus cycles (~16 ms of a 16 KB ring) at the end of
  every call - more than the copy it replaces.

**What os8088's SOUND.DRV sees: nothing.** The card raises the SB's block
IRQ off its own byte count, as now, and the ring's bytes arrive in order;
kern_big's block IRQ does not read the 8237 (SPEC.md 34.5.2.2: only
kern_mega's does, and kern_mega's buffers stay below 1 MB, R6). The wave-3
row checks this directly: the bytes the card's SB consumed must be the
ring's, in order, with no repeat and no skip, across every hand-over.

### 6.2 What "no stutter" is measured as

The acceptance for wave 3, all against the `pm-pr` image on the same
machine:

- **VIDSND's tone rows, T and R**, through `tools/vstone.py`: **zero**
  breaks in every row, the 16 ms hold-inside-a-copy row included, as
  `pm-pr` has (SPEC.md 18.91.7.1);
- **Bolt under VBPROF**: sound frames late no worse than `pm-pr`'s, frames
  stalled better;
- **the card's own count of FIFO underruns** (a counter the diagnostic
  build prints, DK01's shape): zero;
- **and the row fails on purpose**: with the watermark set to 0 and
  `T_switch` to 0 in a test build, the same row must report breaks. A
  no-stutter row that cannot see a stutter tests nothing
  (docs/WRITING-TESTS.md 1).

### 6.3 What it costs if the rule bites

The rule spends disk time, never sound. On a machine where the hook holds
the PC long and the clip is loud and fast, bursts get shorter and calls
longer; the worst case degrades toward `pm-pr`'s copy rate, not below it -
and if a burst can never fit (a FIFO too small for `T_switch`), the call
falls back to the copy path, which is the S3 behaviour. Wave 2 and 3
report how often each happened.

### 6.4 The two machine shapes

**Shape A - the ST11M owns DMA 3 (the requirement).** 5150 #1 with its
ST-225 in: the ST11M is on channel 3 and IRQ 5, so the card's jumper is on
**1** and its SB and its disk share channel 1 under S1. The stutter
report's coexistence notes apply (ROM at D000h, NE2000 off 320h, the SB
off IRQ 5). The ST11M's own reads are nibble-6 cycles on channel 3 too,
which is R2's collision; it does not arise because os8088's disk calls are
serial (and so is the BIOS's).

**Shape B - the card owns DMA 1 and 3 (the bonus).** The stock 2.0 cannot
do this. It has one request pin and one acknowledge input; the jumper
picks which channel's pair reaches them, and tying two channels' DACK
lines together would short two driven outputs. But the plan's disk
direction never uses DACK - it recognises its cycles by the nibble - so
the disk needs only **a second DRQ output**: a spare RP2350 GPIO wired to
the slot's DRQ3. Then the SB keeps channel 1 by the jumper, with its real
acknowledge, the disk runs on 3, nothing is shared, and section 6.1's rule
is not needed at all (the SB's line is never taken).

- What it needs: a GPIO that is free in the firmware AND reaches a pad
  you can solder to. `pm20.h` leaves GPIO 0, 4-7 and 12-17 unnamed, but
  other modules (I2S audio, USB host, PSRAM, the Wi-Fi chip) claim pins
  outside that file, and without the 2.0 schematic which of them reach a
  pad is unknown. Finding one is the first step of this shape and is a
  continuity-meter job on the owner's board.
- What it costs the firmware: a second "DRQ owner" in the arbitration
  wave 1 writes anyway, and `HDD_DMA = 83h`. Both shapes are one firmware.
- Both at once on one machine is impossible: shape B takes channel 3, which
  is the ST11M's. Shape A and shape B are two machines, or the same one with
  the ST11M out.
- The answer is wave 3b, after S1 works: S1 is what every stock card gets,
  and B only shortens the path for a modified one.

## 7. Risks

- **R1 - H1 above.** If the board cannot drive the bus under AEN, the
  read direction is dead on this hardware and the plan collapses to
  wave 4 (writes) plus whatever a later board revision brings. Wave 0
  exists to find out in a day, not in a month.
- **R2 - a second write-transfer channel.** A floppy read or a real MFM
  read running at the same time as the card's would be answered by the
  card too. Inside one int 13h nothing else of the BIOS's runs; os8088's
  disk calls are serial (`dsk_xfer`). A DOS program that reads the floppy
  from an interrupt while calling the card's disk would break; that is
  written down, not defended. The 1.x had the mirror image of this bug
  (FIELD-NOTES 66: a DMA cycle decoded as an 8237 register write).
- **R3 - TC is global.** Core 1 counts its own bytes; TC is a cross-check,
  never the only stop.
- **R4 - the PC never sees the count it asked for.** If core 1 misses a
  cycle the 8237 still counts it and the buffer and the memory slip by a
  byte. Wave 1's row compares every byte, and the firmware keeps a missed-
  cycle counter the diagnostic build reports (DK01's shape,
  `os8088-pm-debug`).
- **R5 - SB restore (S1)**: an ear-visible failure if wrong - a stutter,
  which the owner made the acceptance condition. Section 6.1 is the rule
  that prevents it and 6.2 the rows that prove it, including the build
  that breaks it on purpose.
- **R6 - kern_mega**: its int 13h runs in the real-mode bracket with
  buffers below 1MB already (the BIOS cannot DMA above 1MB, HMA-PLAN), so
  nothing changes; its row is the existing `pmbox2` leg left out today.

## 8. The os8088 half

Small, and deliberately so:

- `drv_sniff` (driver.inc, the window half - at 5,120 of 5,120, so the
  bytes are found as 18.91.7 found them) reads **8089h** as well as 8088h.
  With DMA on, the run cap stays off, as at 8088h. Whether the kernel then
  wants a LONGER run per call (the card overlaps SD and DMA inside a call,
  so fewer calls is better) is the measurement wave 2 makes, not a guess.
- SPEC.md **18.91.7.2** pins what the kernel relies on: BX = 8089h, the
  channel the user chose, and that the destination is always conventional
  RAM 512-aligned inside one 64KB page (true of every `dsk_xfer` run
  today).
- `firmware/picomem2/README.md` gains the setting and the jumper rule;
  docs/FIELD-MACHINES.md's 5150 #1 row gets its jumper and channel.
- Nothing in SOUND.DRV moves under S1 or S3. Under S2 it already works
  (it is the 1.x's path).

## 9. Branches

- **`pm-pr` stays as it is** - one commit, upstream-shaped, the image in
  `firmware/picomem2/`.
- **The work branch: `pm2-dma`, cut from `pm-pr` (`6204e0d`)**, one commit
  per wave so each can be reviewed and, if upstream wants it, taken alone.
- **`os8088-pm-debug`** is on the 1.x line (`338a2ae` + `OS88_DIAG`) and
  has none of `pm-pr`'s 2.0 parts: the `BV_FW_Rev` = 8088h stamp and the
  2.0 wait hook in `pm_cmd.cpp`, the 2.0 CMake defaults, `pm_pccmd.h`'s
  copy-wait comment, and `isa_dma.cpp`'s run sizing. **Merge `pm-pr` into
  it** (conflicts expected in `bios_disk.cpp`, `sbdsp.cpp`, `pm_pccmd.*`,
  where the debug branch carries the earlier 1.x versions plus diag), so
  that a diagnostic 2.0 image exists before wave 2 needs one; `pm2-dma`
  then merges into the debug branch for field diag builds, never the other
  way. **DONE 2026-11-10** (`fafe50b`): every conflict was the same fix
  with and without its counters, and the instrumented side is kept; the
  8088h stamp is put back and `PICOMEM_BOARD` is a cache variable so the
  one tree builds both cards. Built here: the 1.x and the 2.0, diagnostics
  off and on, all four link; the 2.0 with diagnostics off differs from
  `pm-pr`'s image in 6 bytes, all address constants moved by 16.

## 10. Waves

Each wave ends with both firmwares built reproducibly and the 1.x image's
bytes unchanged unless the wave says why.

**Wave 0 - the bench (go / no-go, hardware). BUILT 2026-11-10.**

- **The probe firmware**: Elendilon/ISA-PicoMEM `pm2-dma` (`e8950c3`),
  built `-DPM2DMA_PROBE=1` for the 2.0:
  `PM2_11_10_26_OS8088_DMAPROBE.uf2`, sha256 `ab5b2695...35d9`, rebuilt
  from the pushed commit to the same hash. Without the switch the 2.0 image
  is byte-identical to `pm-pr`'s (`03fd63df...`); the 1.x builds from the
  same tree. Five card commands, B0h-B4h (`src/pm_libs/pm2dma_probe.h`):
  address, mode and channel, go (raises DRQ), stop, and forty counters. A
  test image only, never a release, and it is flashed back to `pm-pr`'s
  image afterwards.
- **`tests/pm2dma` (PM2DMA.O88, `make pm2dma`)**: programs the channel for
  a single-mode write transfer of 512 bytes into a buffer no 64KB page edge
  crosses, arms the card, unmasks with interrupts off, polls for the
  channel's TC, and reports: TC or not, bytes right against the card's
  pattern, bytes left at EEh, bytes FFh (a floating bus), the first wrong
  byte, and the card's counters - every strobe it saw by kind, the first and
  last in-buffer address and strobe, and the 8237 programming as the card
  snooped it (S1 needs that snoop). Mode 0 once, modes 1 and 2 three times
  each; R or a click for channel 1, key 3 for channel 3.
- **`tests/pm2dma/hostcheck.py`** (by hand) runs the package's own code
  under Unicorn against a model of the 8237 and of the probe's commands: a
  card that answers right reads 512 right on either channel, a gated card
  reads a floating bus, and two models broken on purpose - a card one byte
  late, the jumper on the other channel - do not pass. It checks the
  instrument, not the board.

*Owner, on 5150 #1, the SB quiet:* flash the probe image, run PM2DMA,
bring back PM2DMA1.TXT, flash `pm-pr`'s image back. **Reading it:**

| mode 0 says | means |
|---|---|
| MEMW cycles in the buffer = 512, MEMW+IOR = 0, IOR = 0 | section 2.1 is right: the card sees MEMW alone |
| MEMW+IOR or IOR in the buffer = 512 | the board passes IOR under AEN: mode 2 is the design |
| nothing in the buffer, but TC came | the card's address decode is not what the probe assumes - stop and look |
| no TC | DRQ is not reaching that channel - the jumper, or the SET pin's sense |

Pass = mode 1 or mode 2 with 512 right, three runs running. Mode 1 with a
few wrong bytes, all near the start of a run or all in one kind of memory,
is the timing question of 2.1 and points at the extended write or the DACK
wire. Fail everywhere = R1 is real; stop and talk.

**Wave 1 - the read path, SB idle (S3).** `PCC_DMA_SETUP` in the card
BIOS; core 1's nibble-6 arm; the run loop in `bios_disk.cpp` with the
section-4 fallbacks; `HDD_DMA` in the config and the setup menu; BX =
8089h. The twin: `pmhost` grows the device-to-memory half (86Box's
`dma_channel_write`), so `pmbox2` gains a leg that boots off the card's
disk with DMA on and reads VIDDISK's V pattern back byte-exact - and
**fails on purpose** with the wrong page register and with a run across a
64KB page (docs/WRITING-TESTS.md 1). The os8088 half of section 8.

**Wave 2 - measure it.** On the twin: int 13h calls, the hook's latency,
sound frames late, over Bolt with the SB off (S3 can only win there). On
the iron (owner): VIDDISK R and V at 0/25/50/75% hook, `pm-pr` against
`pm2-dma`, the same rows SPEC.md 18.91.7 quotes; whether pacing DRQ helps
the hook. MartyPC has no DMA hard disk (98.2.15.4) and its PicoMEM is the
1.x snoop; giving it a 2.0 disk device is the only way to a cycle-exact
number off the iron and is scoped here, not promised.

**Wave 3 - the SB shares the line (S1).** Section 6.1's arbitration,
watermark, bursts, tail restore and repair, and the card-interrupt
fallback; the underrun counter in the diagnostic build. On the twin
first, where the hook's hold can be set as long as the row likes: the
ring-order check, and the break-on-purpose build. Then the iron, with
section 6.2 as the acceptance - zero breaks, or the wave is not done.

**Wave 3b - shape B (bonus).** The spare GPIO found on the board, the
second DRQ owner, `HDD_DMA = 83h`; the same rows with the SB never
starved.

**Wave 4 - writes by DMA**, on the existing `isa_dma_w_tc` path. Optional.

**Wave 5 - upstream.** Like `pm-pr`: a commit shaped to go to
FreddyVRetro/ISA-PicoMEM, the option off by default, the image into
`firmware/picomem2/` with its README's table updated.

## 11. The owner's answers (2026-11-10)

1. **S1**, "as long as that doesn't cause sound stutter or sound dropouts
   with the SB while we are doing disk DMA." That condition is section
   6.1's rule and 6.2's acceptance.
2. **Freddy has not answered the `pm-pr` questions**, so H1 is settled by
   wave 0 on the iron, not by asking. The question stays worth sending
   when he can be reached.
3. **Two shapes**: the ST11M owns DMA 3 and the card shares 1 under S1
   (the requirement, shape A); or the card owns 1 and 3 (a bonus, shape
   B). Running both was a wish, not a requirement. Shape B needs one wire
   on the board (section 6.4); both shapes cannot be on one machine at
   once, because B's channel is the ST11M's.
