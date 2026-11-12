# BOUNCE BONANZA — how it was built (diary)

The running diary that [BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md) links
to (CLAUDE.md, *Building an app or game in waves*, step 6). Observations are
kept apart from intentions, and every entry names what was actually tested.

## 2026-11-12: the brief and the investigation

**The brief.** An overhead isometric course that scrolls, with a ball as the
player, for the 5150. Hardware scrolling, probably vertical only as in 1942,
but both ways if that is feasible. A rolling ball that looks 3D, done with
frames rather than 3D maths, the way *Extreme Pinball* did it. Mini-golf
props, including tubes that spit the ball out with momentum. 2–6 animated
obstacles paced by TITHE's wheel. Physics more fluid than Marble Madness.

**Observed: what the tree already proves.**
- Excitebike scrolls horizontally on the CGA and the Hercules, one 8 px
  column at a time, at a **measured 54.6 Hz** on MartyPC's XT (SPEC.md 102,
  PERFORMANCE.md Set 148).
- 1942 scrolls vertically on the CGA, two scan lines at a time (SPEC.md
  101.1).
- Both do it by moving the 6845 start address through the same 8 KB ring
  per bank.

**Worked out on paper, not run: combining the two.** A 40×100 window
cannot alias inside a 4,096-word ring (the proof is the plan's section 2.1).
Entering rows fit in the ring's 96-word slack, so they can be drawn off
screen; entering columns have to race the beam.

**Prototyped, on the host only: the "phase torus" ball.**
`bounce-bonanza/ballproto.py` renders a 16 px ball that samples an
8-periodic texture through u = R·asin(x/R). Rolling adds the screen
displacement to the phase, so 64 frames cover every direction with no jump
when the ball turns. Looking at the GIFs:
- the **spots** texture reads best as rolling;
- **checker** reads as a beach ball;
- the slope checkerboard of the isometric mock shows slope direction
  clearly in 4 CGA colours.

**Not tested: anything on a guest.** No package exists yet. The budget in
the plan's section 6.5 is predicted from measured unit costs and is what
wave 0's spike is for.

## 2026-11-12 (later): wave 0, the spike, is a GO

**Built:** `tools/bonanza_assets.py` (the course generator, the ball and
their `--selfcheck`), `apps/bonanza/` (the package, 6,191 bytes plus 813 of
bss), four disks, and three soak rows: `bonanzaassets`, `bonanzaring` and
`bonanzaperf`.

**The course** is a generated isometric heightfield: a start plateau, a long
descent, steps, a traverse with pits and blocks, a climb and a sprint to a
chequered finish. It is 512 x 1600 px, which cuts into 293 distinct 8x8
blocks, so each course part is 30 KB.

**Observed on MartyPC (cycle-exact, the 1,200-frame benchmark):**

| | CGA | Hercules |
|---|---|---|
| display | 59.8 Hz (2 misses) | 50.85 Hz (0 misses) |
| busy share of a refresh | 58% | 50% |
| box compose | 23.5k clk | 23.5k clk |
| retrace wait (idle) | 33.5k | 46.6k |

The prediction was 35-45k clocks of work a CGA frame. The measurement is
46k, a little over that, but inside one refresh. **60 Hz holds on CGA**, and
`FSXF_RATE` is not needed.

**The ring is exact.** The card's memory, decoded through the ring at the
package's start address, equals the host's own picture on every checked
frame in all eight scroll directions, on both cards, and the rendered glass
equals it too.

**The order rules are now tested, not just argued.** The row stops at the
retrace start as well as at the presented frame, so it sees the ORDER of the
writes. A copy built with the column written before the flip goes red only
at that stop.

**Discovered:**
- **The box races the beam too.** The plan wrote the boxes after the
  columns. With the camera clamped at the course's top, the ball sits high in
  the window, and its box was still unwritten when the beam passed: one
  refresh showed the ball where it was. The fix writes the entering column
  in raster order round the boxes (SPEC.md 128.2 rule 4).
- **The first route never scrolled up.** A host simulation of the autopilot
  and camera found it. The route gained a return leg, and `--selfcheck` now
  asserts that every axis goes both ways.
- **The Hercules 200-line field is 50.8 Hz on MartyPC, not 50.**
- **The Hercules ball's mid tone is stripes**, because the contract pinned it
  to one pattern while the course uses a checker. It is cheap to fix, since
  the frame index already carries the ball's parity.

**Not tested:** kern_mega (MartyPC is an 8088), EGA and MDA refusals (only
VGA was tried), a two-card machine, and real hardware.

**Next:** the optimisation round (plan, wave 0b). Box compose is the largest
working part and the two CGA misses are two-row frames, so compose and rows
come first.

