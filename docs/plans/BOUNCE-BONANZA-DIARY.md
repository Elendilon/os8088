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

## 2026-11-12 (evening): the owner plays it

**The owner played it on 86Box (a 5150 with CGA).** The first try said `Load
failed`. The cause was the emulator's setup: the third drive was set to an
80-track quad-density type while holding a 40-track 360KB image. A 5150 BIOS
steps one track at a time, so only track 0 (the FAT and directory) reads
right on that drive. The file is listed and its body is not. With the image
in a 360KB drive it loads. There is no package or kernel defect. The lesson
for whoever reads a field report next: **check the drive type before the
package.**

**What they saw:** "The ball animation is very impressive." But **scrolling
slowly is jerky, and speeding up it smooths out.**

That is the hardware floor showing through wave 0's camera. The CGA moves the
picture in 8 px and 2-line steps, and nothing finer exists in its graphics
mode. Wave 0's camera follows a slow ball one step at a time, so the world
hops every few frames, and the ball jumps back on the screen each time. Fast,
it hops every frame, and that reads as motion.

The fix is a camera rule rather than a renderer: **rest, or move fast; never
trickle.** Wave 0b ships three camera modes so the owner can choose by feel
(SPEC.md 128.9): GLIDE, FOLLOW, and wave 0's TRICKLE as the control. TITHE
took about twenty rounds to feel right, and this is expected to be the same
kind of loop.


## 2026-11-12 (night): wave 0b, the camera and the optimisation round

**What was built.** Three camera modes, cycled with `C` in play or on the
desktop face: GLIDE (rest inside the dead zone, then pan fast with a lead),
FOLLOW (a camera velocity that eases toward the ball's), and wave 0's
TRICKLE as the control. The optimisation list from SPEC.md 128.9, and the
Hercules ball's mid tone now follows the course's checker instead of
striping across it.

**Measured** (MartyPC, the 1,200-frame benchmark, A/B against wave 0 built
with its own art; SPEC.md 128.9 has the full table):

| | CGA wave 0 | CGA wave 0b | Hercules wave 0 | Hercules wave 0b |
|---|---|---|---|---|
| box compose | 23,515 clk | 11,490 | 23,568 | 11,839 |
| busy, of a refresh | 58% | 43% | 50% | 37% |
| misses in 1,199 | 2 | 0 | 0 | 0 |
| worst frame | 134,437 clk | 105,051 | 116,916 | 114,705 |

**Discoveries.**
- **FOLLOW cannot fix the slow-scroll jerk, and the measurement says why.**
  A camera moving at the ball's speed has to step every 8/v frames, so at a
  slow ball FOLLOW steps exactly as often as TRICKLE (every 15-17 frames
  across on the CGA). It only centres the ball and evens the gaps. GLIDE is
  the only mode that changes what the eye sees: a pan steps every second
  frame across (30 a second on the CGA) and every frame down, with long rests
  between pans.
- **The benchmark route had to change.** Under GLIDE, wave 0's route gave
  the Hercules no right-going diagonal and the CGA no pure left step, so the
  ring row's "all eight directions" check would have failed. An integer-exact
  host model of the autopilot and cameras chose new waypoints, and MartyPC
  confirmed them (3-6 of each direction).
- **The review caught a deadline that could never fail.** The row-0 corner's
  first design checked the box's last line, but the column writer outruns the
  beam, so its binding deadline is its first row. It now writes the column
  first and checks both ends of the box. The test course cannot actually put
  a box at row 0, which SPEC.md says plainly; a later wave owes it a probe.
- **The row and column writers are bound by the card, not the code.** About a
  fifth cheaper a call after the rewrite, where box compose halved. Further
  speed there would come from writing less, not from tighter loops.
- **15KB in each ball part can never be drawn** (only one shift in four is
  reachable for a given frame). Left for a later wave.

**The verifier found a real defect after the fix stage.** The CGA results
face drew 14 lines into a 13-line box, and the spill left a broken stretch
in the dock's border after the window closed. The face is now 13 lines and
`bz_line` refuses to draw past the box.

**Next:** the owner chooses a camera by feel; wave 1 (the course pipeline
and physics v1) starts now.
