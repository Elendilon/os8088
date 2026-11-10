# A PicoMEM 2's disk by DMA - what the card can do, and the plan

**Status: PLAN (2026-11-10). Nothing built.** The firmware half lives in
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
   card's. Whether the board's data buffers will drive D0-D7 during an AEN
   cycle is the one thing the source cannot answer - **wave 0 is a bench
   test on the 5150 that settles it before anything else is written.**
4. **One line means the card's Sound Blaster and its disk SHARE a channel.**
   Video Battle and Video Player stream SB sound while they read, so a
   DMA disk that only works with the SB idle buys nothing for them. Sharing
   is wave 3 and the hard part; two designs, owner's choice (section 6).
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
  channel 3. The byte is spare in June's `PMCFG_t`, so no file moves and
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
| **S1** | time-share: the card stops its SB requests (its FIFO is 1,024 samples, ~46 ms at 22 kHz), the PC saves the channel (`PCC_DMA_READ`, already in the BIOS), the disk runs, the PC restores. The 8237 cannot restore an auto-init ring mid-way (writing the address writes base AND current), so the restore programs the TAIL single-shot, and at its TC the card asks the PC, through its own interrupt as the 1.x's virtual DMA does (`IRQ_R_DMACOPY`'s "new DMA regs after the copy"), to put the ring back | the most firmware, all of it in the card; a card IRQ per disk call on a jumpered line (June: IRQ 7 fixed) | **everything**, with the SB on real DMA |
| **S2** | with HDD DMA on, run the card's SB on the 1.x's *virtual* DMA (the `USE_HWDMA=0` code, made a runtime choice on the 2.0): the line is the disk's alone | the SB's own data crosses by CPU copies (~22 KB/s, ~5% of an XT); the virtual path's DOS-game compatibility is upstream's "low", though os8088's SOUND.DRV is proven on it (the 1.x) | everything except the SB's copies |

**Recommendation: S1**, with S3 as wave 1's behaviour so that wave 1 ships
something correct. S2 is the fallback if S1's restore proves fragile on
the iron, and is cheaper to try than it looks because the code exists. The
owner chooses; section 10's question 1.

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
- **R5 - SB restore (S1)**: an ear-visible failure if wrong. Its row is
  VIDSND's tone through a battle, the instrument that found the stutter.
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
  way. *This session cannot push to Elendilon/ISA-PicoMEM (read access
  only); the merge is the first thing a session with push access does.*

## 10. Waves

Each wave ends with both firmwares built reproducibly and the 1.x image's
bytes unchanged unless the wave says why.

**Wave 0 - the bench (go / no-go, hardware).** A throwaway firmware on
`pm2-dma`: a vendor port starts a test that raises DRQ and answers nibble-6
cycles with a counting pattern. A test package (`tests/pm2dma/`, built only
by its own target, PMDMA's shape) programs the jumpered channel for 512
bytes into a page-aligned buffer, waits for TC in the 8237 status, and
paints what arrived, byte by byte, with the card's missed-cycle count.
*Owner, on 5150 #1.* Pass = 512 right bytes three times running. Fail =
R1 is real; stop and talk.

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

**Wave 3 - the SB shares the line** (S1, or S2 if chosen). The row is
VIDSND's tone through a play and through Bolt, against the `pm-pr` image:
it must be no worse anywhere and better under the hook.

**Wave 4 - writes by DMA**, on the existing `isa_dma_w_tc` path. Optional.

**Wave 5 - upstream.** Like `pm-pr`: a commit shaped to go to
FreddyVRetro/ISA-PicoMEM, the option off by default, the image into
`firmware/picomem2/` with its README's table updated.

## 11. Questions for the owner

1. **S1 or S2** for the SB on the same line (section 6) - or S3 alone to
   start, accepting that Video Battle gains nothing until wave 3?
2. **Ask Freddy about H1 first?** One sentence - "is D0-D7's buffer
   enabled for an IOR during AEN on the 2.0?" - may save wave 0.
3. **5150 #1's jumper**: the card is on DMA 1 today (FIELD-MACHINES).
   With an ST11M on 3 in the same machine (the stutter report's last
   section), 1 is the only channel the card can have, so S1/S2 is not
   optional there.
4. "Three DMA slots": the card can be on **one** channel, 1 or 3; the XT's
   others are refresh (0) and the floppy (2). If the intent was "SB on 1
   and the disk on 3", this hardware cannot do it - one DRQ pin, one
   acknowledge.
