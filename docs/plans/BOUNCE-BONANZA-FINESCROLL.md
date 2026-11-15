# Bounce Bonanza: one-line vertical scroll and the split camera (an experiment)

*Branch `bounce-bonanza-finescroll`, cut from `bounce-bonanza` at `e4da75a`.
The contract is SPEC.md 128.21 (BONANZA) and 53.5.2 (the kernel's
`FSXW_ANCHOR`); this file is the research behind them and the diary of the
build. Nothing here is shipped GLIDE: the new behaviour is camera modes on
`C`, for the owner to judge by eye.*

## 1. The question

The owner asked whether Area 5150's "single scanline" scroll could be adopted
for Bounce Bonanza without killing performance, and then - after the answer
below - for the kernel change and the method it pointed to, plus a second,
independent experiment: **a camera that does not move both axes in one
frame**, because the visible fault is a microstutter when the view goes
vertical AND horizontal at once (vertical alone, moving fast, is smooth
enough; horizontal alone too).

## 2. What Area 5150 does, and why it is not for BONANZA

Sources read: reenigne's own source (`github.com/reenigne/reenigne`,
`8088/cga/scanline_per_frame/lake.asm` and `1spf.txt`, `8088/cga/1linerow/`,
`8088/demo/restarts/`), MartyPC's "Emulator Debugging: Area 5150's Lake
Effect" (2025), VileR's "the CGA/CRTC phantom vsync" (int10h.org, 2023) and
"Area 5150: a reflection" (scalibq, 2022).

- **The method ("1spf")**: R4 = 1 and R9 = 0, so a 6845 FRAME is two rows of
  one scan line - and the two rows sit SIDE BY SIDE on one physical line (a
  left row of 88 characters and a right one of 26: 114, one line), so a frame
  is exactly one scan line and the start address (latched at each frame's
  start) is new on every line. The CRTC is rewritten 8 times a line, in
  200 unrolled 304-cycle bodies, the CPU in cycle-exact lockstep with the
  CGA: DRAM refresh moved to every 19 PIT ticks so its DMA lands at the same
  place on every line, IRQ0 alone unmasked, a chain of eight timer ISRs to
  place the start.
- **Why not**: (1) it is 60,800 of a frame's 79,648 cycles (76%) - BONANZA
  is busy for 58% of a refresh before it scrolls anything; (2) in CGA mode 4
  the row address bit 0 selects the bank, so R9 = 0 shows only the EVEN bank
  - 8 KB, 100 lines of 320 px - and a full 320 x 200 picture cannot be shown
  at all; (3) it takes PIT channel 0, channel 1 and the 8259 from the
  kernel; (4) a Hercules has its own crystal, so no lockstep; (5) only
  MartyPC 0.4+ runs it, after ~28 emulator fixes; (6) R7 rewrites during
  display can phantom-blank on real IBM cards.

## 3. The method that can be adopted: two frames a refresh

The same family (reenigne's `1linerow.asm`, "restarts"): put TWO 6845 frames
in each 262-line refresh - A carrying the vertical sync and showing nothing,
B the 100-row window - and the length of A, set in single lines by its
vertical-total adjust (R5), decides where B sits after the sync. One line of
A's length is one line of picture: a one-line vertical step for a few
register writes a frame. Horizontal stays 8 px (no 6845 trick gives less).

**The spike** (scratchpad, MartyPC 0.4.2, IBM 5150 + CGA, a boot sector):
the picture at raster line 32 in one phase and 31 in the other, all 200 lines
intact, every one of 199 vsync-to-vsync intervals 262 lines (79,619 - 79,680
clocks: polling jitter) across the phase changes. Three things it taught that
the paper design got wrong: R7 = 0 gives NO sync at a frame's start in
MartyPC (the sync goes on A's row 1); the adjust lines ARE displayed while
the row counter is below R6 (A needs R6 = 0); and A's FIRST scan line is
displayed whatever R6 says (hidden by the video gate, 3D8h, here; R1 = 0
does not blank, R1 = 1 shrinks it to one word).

## 4. The kernel change: `FSXW_ANCHOR`, and why it re-times

The writes must land in two windows of ~20 lines EVERY refresh, from an
interrupt: a frame loop that drops a frame must not drop a sync (B's
registers left for a second frame have none). Neither existing clock fits:
`FSXF_FASTTICK`'s 54.6 Hz is not frame-locked, and `FSXF_RATE`'s phase is
wherever the bracket started.

**First design, MEASURED and abandoned**: anchor `FSXF_RATE` at the retrace
(a CGA frame is exactly 19,912 PIT counts, so a divisor of 19,912 / k holds
the phase) with a uniform divisor of 2,489 - eight periods a frame, the
slowest rate that put one inside each window. A rate period costs ~2,070
cycles (`sch_isr` to `sch_resume`: ~940 to the hook, ~700 the switch path),
so eight a frame were ~16.5k cycles - a fifth of a refresh - and MILL's demo
fell from 763 presented frames to 555 (301 over 1.5 refreshes, against 53).

**The design shipped on the branch**: `FSXW_ANCHOR` restarts channel 0 at the
retrace's start with a first and a second period of the caller's choosing,
and from then the hook RE-TIMES the rate - the AX it returns is queued as the
period after next (mode 2 loads a count written mid-period at the next
reload). The ISR's tick accumulator adds each period's own length, so
`[ticks]` stays exact. BONANZA asks for two interrupts a refresh, where it
needs them. +229 bytes of `.text` and 5 of `.bss` on kern_big, +255 of
`.text`, 16 of `.mega` and 5 of `.bss` on kern_mega, nothing on kern_small
(which refuses the new clock). The speaker door's re-rate (SPEC.md 34.11),
which sets channel 0 itself, now resets both period lengths too (`sch_rset`)
- found while choosing the final pass's rows, before any row ran: without it
a speaker play would have kept the old divisor in the tick accumulator.

## 5. BONANZA's side

- **The bracket is chosen at Enter**: `FSXF_RATE` at 21,845 (FASTTICK's own
  sub-tick) on a CGA with `C` on FINE or FINE SPLIT, `FSXF_FASTTICK` as
  before otherwise - so GLIDE, TRICKLE, SPLIT and the `B` benchmark run
  exactly the bracket wave 6b did, and FINE is reached by choosing it before
  Enter. FINE's anchor re-times the rate: 8,786 then 9,386 (the start's W0
  and W1), then 2,888 and 17,024 in turn.
- **The clock is virtual**: every part of BONANZA reads sub-ticks of 21,845
  counts; with FINE off channel 0 is exactly that and the old sampler runs;
  under FINE the hook's running total is folded into a virtual phase.
- **The camera**: FINE runs LATTICE's vertical axis in LINES (C = 2 R0 - P;
  the ring sees R0 alone); SPLIT withholds a row on a column's frame; FINE
  SPLIT keeps the free line on a column frame and carries the rest.

## 6. The diary (what the measurements caught)

1. **The uniform rate was a fifth of the machine** (section 4) - caught by
   the A/B leg against `e4da75a` before anything else was built on it.
2. **The sampler's first form overran by 2.4%**: a reload landing between
   the count latch and the 8259 read was counted against a pre-reload count.
3. **The re-timed sampler ran the clock at 106 Hz**: a total that moved
   backwards (a reload whose IRQ0 is held) was corrected by the queued
   period read AFTER the read's `popf` - by which time the held IRQ0 had run
   the hook and the queued period was the NEXT one (17,404 counted for a
   2,508), and every later sample cascaded. Found by stopping in the sampler
   and comparing the latched count with the cycles since `sch_isr`; fixed by
   reading the queued length inside the same interrupts-off window.
4. **The wheel's commit spans held W1 off by up to 31 lines** (the probe
   `bz_hlate`): FINE SPLIT fell to 304 frames. Under FINE those spans now run
   with interrupts on (`BZ_WCLI`); W1's worst is ~570 counts (7.5 lines).
5. **FINE at LATTICE's speed never showed a line**: 2-line steps to
   32-line lattice targets keep the top line even, so the phase changed
   twice in a whole demo. FINE's slow rate is now ONE line a frame, and FINE
   SPLIT's carry rule makes its lines odd on purpose (48 phase changes over
   MILL's demo).
6. **A weak red arm**: poking the hook off just restarted FINE on the next
   frame; the red arm patches W1 to a bare RET instead.
7. **The owner's first look, on 86Box: a brown screen with a green bar**
   (FINE, Windmill Lane). Three things followed, and the third was the
   defect. (a) The scoped soak had GLIDE's rows failing under the RATE
   bracket, so the bracket became a choice at Enter (section 5). (b) The
   start leaned on the 6845's row counter running past R4 to 127 and
   wrapping, and W1 sat at the very first line of its window: 86Box was
   installed and its IRQ0 measured up to 15 lines late, so the start moved
   to mode 4's own sync with nothing written there and a W0 inside the next
   frame. (c) With that, MartyPC's retrace waits began timing out under
   FINE and the new safety net (a timeout = a lost structure) tore FINE down
   every few seconds. A probe of 3DAh bit 0 inside the hook said W1 found
   the display ON in every refresh: **frame B, rows 0 - 99 with R6 = 100,
   never turns the display off** - a 6845 does that when the row counter
   EQUALS R6, and it never reached 100 - so B's 22 adjust lines showed
   memory past the window until W1 shut the gate (in MartyPC's raster: the
   picture down to line 255). The spike had found exactly this for A, which
   is why A has R6 = 0; B was not given the same thought. Worse, the
   start's first B took mode 4's 6-line adjust or W1's 22 depending on
   whether W1 got there first, so the structure settled ~13 lines early
   against the interrupts and W1 ran in the last lines of its window. **B
   is now 101 rows** (R4 = 100: row 100 is R6's and blanks itself and the
   adjust), A `7 + P` rows, W0 writes B's adjust so the start is the steady
   state from its first frame, and W1 writes R4 last (its window opens at
   the END of B's row 100). The trace of interrupts against the sync went
   from W1 at t ~ 255 - 258 with lost syncs and restarts to W1 at ~242 and
   W2 at ~18.5, every refresh; the window moved to line 36 + P.
8. **The final pass, A/B against the base** (SPEC.md 128.21.5): the wheel's
   two failures and the Hercules `bz_rwlate` are the base's own;
   `bonanzamega`'s was its harness's (a poke before the first frame's
   `bz_t0`, fixed in the row); `bonanzaring`'s guarantee 5 at `PEAK`'s
   cannon fails here and not at the base - not a camera defect (the guest
   matches the model frame for frame) but the guarantee resting on frame
   pacing, which this branch moves by a few hundred clocks a frame. The
   clock's light path was cut to one test (`bz_clkh`) on the way; it did not
   change that.

## 7. What was measured, and what was not

MEASURED on MartyPC (sound off, MILL's demo through `D`): SPEC.md 128.21.4's
table - FINE SPLIT 760 frames with 96 over 1.5 refreshes (GLIDE's leg 716 and
64), and no frame of a row and a column under SPLIT or FINE SPLIT (28 - 38
under GLIDE). On 86Box (`OS88_EMU=86box`, the same disks): MILL's demo in
FINE and `C` cycling all five modes in play, screenshots clean, no lost period
and no failed start; W1's lateness ~480 counts (6 lines) in play. NOT
measured: anything on real hardware - the two-frame structure, R6 = 0 and the
first-line leak are MartyPC's and 86Box's 6845s, which are not a 5150's.
**The owner's 5150 is the instrument for FINE.**

## 8. Trying it

`C` on the desktop cycles GLIDE, TRICKLE, FINE, SPLIT, FINE SPLIT (the
Hercules and kern_mega skip the two FINE modes). **Choose FINE or FINE SPLIT
before Enter (or `D`)**: that is what brings the re-timable clock, and in a
play entered on any other mode `C` skips the FINE modes. In a FINE play `C`
cycles all five. `D` replays a demo in the chosen mode, so the same route can
be watched in each.
