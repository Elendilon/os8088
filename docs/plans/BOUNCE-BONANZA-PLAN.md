# BOUNCE BONANZA — an isometric rolling-ball game for the 5150 (investigation and plan)

**STATUS: WAVE 0 (the spike) DONE, a GO (the owner, 2026-11-12: "we are good
to continue"): both cards hold the full refresh on MartyPC (CGA 59.8 Hz,
Hercules 50.8 Hz). WAVE 0b (the camera and the optimisation round, SPEC.md
128.9) IN PROGRESS, then wave 1. The owner's decisions are in section 12.** The package is `BONANZA` (`apps/bonanza/`). Below is the
investigation as it was written, the answer to the owner's
brief of 2026-11-12, on branch `bounce-bonanza`, cut from `elendilon`: is an
overhead isometric rolling-ball game with a scrolling course feasible on the
IBM 5150, which tricks does the scrolling need, how do we make the ball look
3D, how do animated obstacles stay cheap, and what else could the game do?
**Bounce Bonanza** is the title, and `BONANZA` the package (section 12). Every figure here is
**PREDICTED** from measured unit costs unless it says otherwise. The
emulated-XT spike in section 11 (wave 0) is what turns those predictions into
measurements. Nothing here has been run on a 5150.

The brief, condensed:

- **View and scrolling.** Overhead isometric, and the course scrolls,
  probably with hardware tricks. Vertical scrolling only, as in 1942, is
  acceptable. Plan both directions if that is feasible.
- **The ball.** It is the player. A rolling texture should make it read as
  3D, done with frames in the way *Extreme Pinball* did, not with 3D maths.
- **Obstacles.** Mostly built into the level, with 2–6 animated at a time,
  paced by TITHE's wheel (SPEC.md 125.5 on `tithe-new`).
- **Course props.** Mini-golf style, including props the ball enters and is
  spat out of, some with momentum.
- **Feel.** Physics more fluid than Marble Madness's stiff controls. This is
  not a clone of its mechanics or its style.
- **Ideas.** Suggest other mechanics that suit the style and are plausible on
  a 5150.

The prototype pictures referred to below are in
[`bounce-bonanza/`](bounce-bonanza/). They were made by `ballproto.py`, a
host-only script that `make` does not use and that ships nothing.

---

## 0. The answer on one screen

1. **Both directions are feasible on the CGA and on the Hercules, with no
   hardware we don't already use.** On both cards, the 6845's start address
   is a word offset into an **8 KB ring for each bank**. A vertical scroll
   moves it by one row of words, and a horizontal scroll moves it by one
   word. This tree has already shipped each half:
   - **1942** (SPEC.md 101.1) scrolls vertically on the CGA, two scan lines
     at a time.
   - **Excitebike** (SPEC.md 102) scrolls horizontally on the CGA and the
     Hercules, 8 px a column, and was **measured on MartyPC's 4.77 MHz XT at
     54.6 Hz, with two thirds of each sub-tick idle**.

   Doing both at once uses the same ring. Section 2 shows that a 40×100
   window cannot alias inside it.
2. **The steps are coarse in one direction.**
   - CGA: **2 lines** vertically, **8 px** horizontally.
   - Hercules (Excitebike's 360×200 pair-pixel field): **4 lines** and
     **8 game px**.

   So the courses are **tall first** (Marble Madness's own shape: the
   descent is mostly down the screen), up to **2–3 screens wide**, with a
   dead-zone camera so that horizontal steps happen rarely and in glides
   (section 2.6).
3. **The ball is a phase torus: 64 frames, 4 KB, no 3D maths on the
   guest.** The visible face samples a texture that is periodic in both axes
   through a fixed spherical lookup. Rolling by (dx, dy) pixels adds (dx, dy)
   to the phase modulo 8. So **every direction of travel is covered, and a
   change of direction never jumps a frame**. The prototype is
   `bounce-bonanza/roll-*.gif` (section 4).
4. **TITHE's wheel carries over almost unchanged**, as *lanes*, each with
   its own clock:
   - **Must happen every frame:** the scroll strips, the ball, and the one
     obstacle the ball is touching.
   - **Wheel:** the other 2–6 animated obstacles share a **calibrated credit
     in microseconds**. A missed slot is late by one frame and never slows
     the animation, and a rate cap stops fast machines from over-animating.
5. **The physics is a fixed-step heightfield with momentum.** Input applies
   a *force*, the surface decides grip and friction, walls and drops have
   restitution, and the step is deterministic. Determinism gives replays,
   ghosts and a link race for free (section 5).
6. **There is no new kernel slot, with one optional exception.** A
   *trackball* control (the mouse's relative motion) needs one, and is the
   owner's decision (section 5.4). The pointer can already be used as an
   analogue *tilt stick* at no kernel cost.

**Recommendation:** build it. Start with **wave 0**, a throwaway spike: the
2D ring, one test course and the ball, on MartyPC's CGA and Hercules XTs.
Its numbers are the go/no-go for the rest.

---

## 1. The machine the game is for

From docs/FIELD-MACHINES.md, the owner's 5150 #1 has:

- **CPU and RAM:** an 8088 at 4.77 MHz and **640 KB** (256 KB on the
  board, plus an AST SixPakPlus).
- **Video:** a **Hercules GB101 and an IBM CGA, both live**. It boots on the
  Hercules, and Control Panel → Display moves the desktop to the CGA.
- **Input:** a serial mouse on COM1.
- **Sound:** the PC speaker only.
- **Not listed:** a game port.

So the game must be good on **both** 1983 cards. MDA has no graphics, so it
is refused with a reason (§47).

Adapter support:

| adapter | plan |
|---|---|
| CGA | `FSXM_CGA320`, 320×200×4. The **baseline**: the art is authored for it |
| Hercules | `FSXM_HERC` with Excitebike's 360×200 pair-pixel field (SPEC.md 102.7.1: R6 = 50 rows, 4 banks, a game pixel is 2 card pixels, and the mid level is a `10/01` checker) |
| VGA / EGA | Phase 1 runs the CGA arm on a VGA, as `FSXM_CGA320` allows. **EGA is refused until proven**, which is Excitebike's rule. A later VGA arm (section 2.8) gets smooth 2D scrolling from Mode X's panning |
| MDA | refused: `CGA OR HERC ONLY` |

How the game runs on each kernel:

- **kern_big:** the main target.
- **kern_mega:** a shipped kernel, so it is in the design and not an
  afterthought. It uses the ORDINARY FSX bracket with `FSXF_FASTTICK`, as
  Excitebike does. *(Corrected 2026-11-12: this said the real-mode bracket,
  `FSXF_REAL`, SPEC.md 53.2.3, but that bracket's API table has no
  `OSAPI_SND_TONE` or `OSAPI_MEM_P`, so the speaker would go silently dead.)*
  `OSAPI_SEG` covers any segment derived from a claim, and any mega-only
  code goes under `PKG_MEGA` (SPEC.md 20.18).
- **kern_small:** the 128 KB machine cannot hold the level and art claims
  (section 7), so the game **refuses at start with that reason**. A smaller
  arm is not planned.

Clocks:

| | value |
|---|---|
| a CGA frame | 59.92 Hz = **79.6k clocks**. The 62-line blank lasts about 3.9 ms, and it is **2.4 ms** from the retrace to line 0 (SPEC.md 102) |
| a Hercules field (R6 = 50) | about 50.4 Hz = **94.9k clocks**, with about 98 blank lines (5.3 ms) after the retrace starts (SPEC.md 102.7.1) |
| one CGA VRAM word, `rep movsw` | **about 86 clocks**, against about 17 for a RAM word. Measured on MartyPC, PERFORMANCE.md Set 148. **This is the cost that shapes everything** |

---

## 2. Scrolling: the ring, both ways

### 2.1 The ring

In `FSXM_CGA320` there are two banks, 2000h apart, and a row of words is 80
bytes (40 words, 8 px each). The 6845 decodes 12 bits of its word address,
plus the scan line's low bit as A13. That makes each bank a **4,096-word
ring**: the 40×100 window uses 4,000 words, leaving **96 words of slack** per
bank.

Store the world **sheared**, as Excitebike does. The byte that holds world
row-pair *r* and world column *c* is:

    addr(l, c) = (l & 1) * 2000h + (80 * (l >> 1) + 2c) mod 8192

That address **never depends on the scroll**. The scroll is only the start
address:

    S = (40 * top_rowpair + left_col) mod 4096

**Proof that the window cannot alias.** Two cells share a word when
40·Δr + Δc ≡ 0 (mod 4096). Inside the window, |Δc| ≤ 39 and |Δr| ≤ 99, so
|40·Δr + Δc| ≤ 3,999 < 4,096. The sum is therefore zero only when
40·Δr = −Δc, which forces Δc = 0 (because |Δc| < 40), and then Δr = 0. The
argument is Excitebike's, extended with Δr. **Two-dimensional scrolling is
the same ring with two step sizes**, not a new mechanism.

### 2.2 Vertical: 2 lines a step, drawn off screen first

When the window moves down by one row-pair, the new bottom row is ring words
`S+4000 … S+4039`. That is **inside the 96-word slack**, so it is written
*before* the start address changes and is never seen half-drawn. Moving up
writes into `S+4056 … S+4095`, which is also slack.

- **Up to two row-pairs a frame** fit in the slack (80 words, against 96).
  That gives a vertical camera speed of up to **4 px a frame, about
  240 px/s**.
- **Cost:** 40 words in each of the 2 banks = 80 VRAM words, about **6.9k
  clocks**, plus about 1.5k for the RAM side. That is **about 1.8 ms a
  row-pair**, predicted.

### 2.3 Horizontal: 8 px a step, raced ahead of the beam

When the window moves right by one word, the entering column's cell (row
*r*, column 40) is the same word as (row *r*+1, column 0). That word is **on
screen** until the start address latches. So, exactly as Excitebike's CGA
arm does:

1. Write R12/R13.
2. Wait for the retrace.
3. Write the column **top-down, starting in the blank**, staying ahead of the
   beam.

**Cost:** 200 VRAM words, about **17.2k clocks, about 3.6 ms**.
Excitebike's measurement agrees: 7.6k clocks a frame at 0.43 columns a frame.
The writer stays ahead of the beam. The beam reaches line 0 only 2.4 ms
after the retrace starts, and it is at about line 19 when the column
finishes at 3.6 ms. That holds only if the column is written **in raster
order, starting at the retrace**, which is Excitebike's rule.

**Horizontal steps are 8 px.** The start address counts words, and the 6845
has no pixel panning, so there is no finer step on the CGA. Section 2.6 is
how the camera hides this.

### 2.4 Diagonal and big moves

A diagonal step is one column plus one row-pair: about **26k clocks,
5.4 ms**, predicted.

A **full window rewrite** is 8,000 words, about **690k clocks, about
145 ms**: roughly nine frames. That is used only for:

- starting a level;
- a respawn;
- a teleport.

It is always hidden behind a transition the player expects (section 6.4),
never paid in the middle of play.

### 2.5 Hercules

Excitebike's Hercules field: four banks; a row is 4 lines of 90 bytes (45
columns × 16 card px); R6 = 50 rows displayed.

- **Ring:** 4,096 words a bank, and the window uses 45 × 50 = 2,250. That
  leaves **1,846 words of slack**, so whole rows can be drawn many steps
  ahead.
- **Vertical step:** 4 lines. One step is 4 banks × 45 words = 180 VRAM
  words.
- **Horizontal step:** one word, 8 game px. The column has the same
  visible-alias problem as the CGA's and the same beam race. The Hercules
  blank is about 98 lines, so there is more room.

The CGA art converts by Excitebike's pair rule, which keeps one art set.

### 2.6 The camera

- **Vertical: leads the ball** in its direction of travel, about 40% of the
  screen ahead at speed, eased so that it moves at most 2 row-pairs a frame.
  At 2 lines a step this reads as smooth.
- **Horizontal: a dead zone** of the middle 160 px. When the ball leaves it,
  the camera **glides** one column every 2–3 frames until the ball is back
  inside, rather than snapping. Courses are designed so that the long
  descents are vertical and the lateral moves are short.
- **No vertical-only fallback is needed.** A course 320 px wide simply never
  scrolls sideways, so the 1942-style game is a *level design* inside this
  engine, not a second engine.

### 2.7 The HUD rides in the picture

The CGA has no split screen; line compare is a VGA register. The HUD is
therefore a **compact composited box**, 8 lines × 12 words in a corner, drawn
with the same box path as the ball (section 6.2). On a vertical step, the old
HUD scrolls into the slack that the incoming row overwrites anyway, so
**moving the HUD costs one box, about 8k clocks**. When nothing scrolled, the
HUD costs only the cells that changed, which is Excitebike's changed-cell
list.

The border colour (3D9h) is also free: for example, a flash when the time
gets low.

### 2.8 Smoother options, considered

| option | gives | why not now |
|---|---|---|
| Pre-shifted background (4 copies at 2-pixel steps) | 2 px horizontal steps | 4× the dictionary, and every step rewrites the whole window (about 145 ms). Dead |
| **VGA Mode X arm** | pixel-smooth scrolling both ways (offset register plus pixel panning) and 256 colours | a whole second renderer. 1942's VGA arm is the worked example. **A later wave**, not the 5150's |
| **160×100×16 "text graphics"** (80-column text, R9 = 1, character DEh) | **16 colours**, 2 px horizontal steps, a 16 KB ring with 8 KB of off-screen slack | **an IBM CGA SNOWS in 80-column mode** (docs/plans/CGA-SNOW-PLAN.md), so every VRAM write would have to wait for blanking. That leaves about 3.9 ms a frame at roughly 10 µs a byte: about 350 bytes. A row is 80 attribute bytes and the ball box about 40, so this is *just* possible but leaves no room for obstacles. **Parked as an experiment** (open decision D5) |

---

## 3. The course: authored in 3D, shipped as blocks

The course is authored as a **heightfield of tiles plus props**, in a text
format (`apps/bonanza/courses/*.txt`; `apps/bounce/` is already BOUNCE,
the square, SPEC.md 112). A deterministic host tool,
`tools/bbcourse.py` (to be written), compiles it into three products.

**1. The picture.** The tool renders the course isometrically on the host,
in the CGA palette. Slopes are checkered surfaces, because the checker *is*
how a 4-colour picture shows a slope (see `bounce-bonanza/mock-cga.png`). It
then cuts the render into **8×8 blocks**, deduplicates them, and groups them
into 32×16 **metatiles**:

| data | size, predicted |
|---|---|
| block dictionary: 600–1,500 unique 8×8 blocks at 16 bytes | 10–24 KB |
| metatile table: 512 × 8 block ids | 8 KB |
| metatile map: 20 × 150 for a 640×2400 course | 6 KB |

Entering rows and columns are decoded from these and written straight into
the ring. The Hercules dictionary is derived from the CGA one by the pair
rule.

**2. The physics grid.** This is world-space data, not screen-space. A cell
is 16×16 ground units and holds:

- a **height** byte;
- a **shape** nibble: flat, 4 ramps, 4 corner ramps, the bowl and funnel
  quadrants, a wall, or a rail;
- a **surface** nibble: normal, ice, sand, mud, rough, boost, conveyor ×4,
  sticky, or bouncy;
- a **feature** byte: hazard, goal, checkpoint, tube mouth, or an obstacle
  id.

A 640×2400-pixel course covers 1.5 M ground units² (the isometric map has
Jacobian 1), which is about **6,000 cells, 12 KB**, or up to 24 KB stored as
a rectangle.

**3. The occluders.** The ball must be able to pass *behind* pillars,
arches, tube bodies and the near rims of a pit. The tool marks every block
whose pixels can occlude, and gives it:

- a **mask**;
- a **depth key**: the ground depth (x + y) and the top height of the
  geometry that drew it.

After the ball is composited into its box, any marked block that is in front
of the ball is laid back over it through its mask. That is typically 0–4
blocks, so it is cheap. Some depth cases are ambiguous; the course design
avoids them, and the tool **flags** any block whose depth varies too much to
key with one value. A block the tool cannot key is an authoring error at
build time, not a glitch at run time.

Art is source (CLAUDE.md, "Building an app or game in waves", step 5).
Tile textures may be hand-drawn or generated. Whichever is used, the source
and the prompt are kept, and the guest gets them only through `bbcourse.py`.
No generation service is ever part of `make`.

---

## 4. The ball: the phase torus

**The trick.** Give the ball a surface texture *t*(u, v) that is periodic
with period P = 8 in both axes. Each pixel of the 16 px disc samples it
through a fixed spherical lookup:

    u = R·asin(x/R) + φx,  v = R·asin(y/R) + φy

Rolling the ball by (dx, dy) screen pixels adds (dx, dy) to (φx, φy),
modulo 8. Some consequences:

- **P² = 64 frames cover every phase**, so they cover *rolling in every
  direction*. The phase space is a torus, and any path through it is a
  sequence of adjacent frames, so a **change of direction never jumps**.
- Near the centre of the disc the lookup has slope 1. A surface feature
  there moves 1 px for each pixel the ball travels, which is rolling without
  slipping.
- Near the rim, asin compresses the texture, so features slide in from one
  limb and squeeze out at the other. That is what sells the sphere.
- It is a cheat: it is not a true rotation, and a feature never visibly goes
  round the back. At 16 px on a 4-colour screen, the prototype says the
  cheat holds.

**The guest does no maths.** It keeps `frame = (φy & 7) * 8 + (φx & 7)`.
Shading is baked into each frame on the host:

- the light comes from the upper left;
- the terminator is ordered-dithered to black;
- one white specular highlight;
- a 1 px dark rim separates the ball from any floor.

| | cost, predicted |
|---|---|
| 64 frames × 16 rows × 4 bytes | **4,096 bytes**, plus **one** 64-byte mask: the silhouette never changes |
| pre-shifted for the 4 pixel phases of a CGA byte (5 bytes a row) | **20,480 bytes**. RAM is cheap on a 640 KB machine. A runtime shift through a 256-word table is the fallback if the claim matters |
| Hercules | the same bytes: a game pixel is 2 card bits, so a byte is 4 game pixels, exactly as on the CGA |
| drawing it | the union box of the old and new footprints is 3 words × at most 20 lines = 60 VRAM words, **about 5k clocks to write**, plus about 3k to fill and compose in RAM. **About 1.7 ms**, every frame |

**The prototypes** are in `bounce-bonanza/`:

- `phases-{spots,checker,band}.png`: all 64 frames for each of three
  textures.
- `roll-*.gif`: the ball rolling a figure-eight over a slope at 30 fps.
- `mock-cga.png` and `mock-herc.png`: one still, as the CGA and the
  Hercules would show it.

On the prototype, **spots** read best as rolling. **checker** reads as a
beach ball. **band** is a "seam" ball, closest to *Extreme Pinball*'s look.
The texture choice is cosmetic: a texture is another 4 KB set, so **a
different texture can mean a different ball** (section 9).

**Height and bounce.** The ball is drawn at its ground point minus *z*. Its
**shadow** stays on the ground and is a checkered AND mask: every other
pixel turns black, which needs no fourth colour. The shadow normally shares
the ball's box. When the ball is high in the air it gets a second small box.

The gap between ball and shadow is the whole 3D cue for a jump. It costs one
extra AND pass. **Squash** on a hard landing is two or three silhouette
frames for a few ticks; it is optional, and its art comes from the same host
tool.

---

## 5. Physics: fluid, not stiff

### 5.1 Units and the step

**Ground units.** The isometric map is:

    sx = x − y,   sy = (x + y)/2 − z

So 1 ground unit is 1 px of screen x. A position is a 16-bit integer plus an
8-bit fraction, and a velocity is a signed 8.8 value.

**The fixed step** uses `FSXF_FASTTICK`'s sub-tick, which is Excitebike's
clock: **54.6 Hz**, built from PIT channel 0's countdown with no new
interface. The display waits for retrace, and the simulation catches up in
whole steps, so it is **identical on every adapter and machine**.

On kern_big, `FSXF_RATE` could give a finer step, as WireBall does. Wave 0
decides whether that is needed; kern_small would refuse it anyway.

### 5.2 Forces each step

    a  = g · slope(shape, sub-cell position)        the heightfield pulls
       + input · grip(surface)                      the player pushes; ice barely bites
       + surface push (conveyor, boost, fan, magnet field)
       − v · drag(surface)                          sand and mud drag; normal surfaces barely do
    v += a;  v = clamp(v, vmax(surface))
    move in at most 4-unit sub-steps; resolve walls and edges per sub-step

**Walls** reflect the normal component with **restitution e** (0.3 on
stone, 0.85 on a bumper rail). The tangential component keeps most of its
speed, so a glancing hit *steers* the ball rather than stopping it. This is
the "fluid" the brief asks for: the ball carves along walls and banks.

**Banks and bowls** are shapes whose slope varies inside the cell (a
quadratic per quadrant, from a table). The ball therefore circles a funnel
without any scripting.

**Air.** When the ground drops away faster than *z* follows, the ball is
airborne:

- gravity acts on *z*, and *x*/*y* keep their momentum;
- on landing, *v_z* is reflected with the surface's restitution, so the ball
  bounces;
- **a hard landing is a MECHANIC, not a punishment** (the owner's decision
  D4). What it does depends on the BALL (section 5.5): the rubber ball
  bounces back up, which is how it clears a gap or reaches a higher tier;
  the steel ball lands dead and is stunned for a moment; the glass ball
  shatters and respawns at the last checkpoint. Falling off a high edge is
  therefore something a course *asks for* with the right ball.

### 5.3 Controls that feel analogue on a keyboard

Each arrow key applies a *force* that ramps from 0 to full over about
150 ms, and decays when the key is released. Releasing the keys means
*coast*, not *stop*. `OSAPI_KEY_DOWN` (a held-key test by scancode) is the
input. Two buttons:

- **Grip:** brakes on the current surface, more strongly on rough surfaces.
- **Hop:** a small jump, once per landing, for minor gaps and for skipping
  an obstacle's beat. It is optional per course.

Directions are **screen-relative** by default, so "up" rolls up the screen.
An option rotates them 45° to the isometric axes, for players who think in
the grid.

### 5.4 Pointer devices

**The keyboard is the primary control (owner's decision D2).** A pointer
is a bonus for the end of the project, and a non-trackball mouse is a poor
fit for this style of game, so neither row below is planned before wave 6.

| device | how | kernel cost |
|---|---|---|
| **Mouse as a tilt stick** | the pointer's offset from the screen centre is the tilt vector, and the edge is full tilt. `OSAPI_MOUSE` answers in desktop coordinates inside a bracket (`apps/missile` already relies on this), giving ±320 × ±100 of analogue range on a CGA desktop | **none** |
| **Mouse as a trackball** (Marble Madness's arcade control) | the mouse's *relative* motion becomes impulse | **a new slot.** `OSAPI_MOUSE` is clamped to the screen, and `OSAPI_MOUSE_FEED` is for drivers only. Its resident cost is tens of bytes on every budgeted kernel, to be priced exactly if chosen. **Owner decision D2** |
| Game-port joystick (201h) | read once a frame. A full-scale poll is about 1.1 ms. §53.7 does not forbid the port | none. Optional; no game port is known on 5150 #1 |

### 5.5 The balls: one engine, three materials (D4)

The ball type is a record of physics constants plus its own 4 KB texture
set, so the texture tells the player what they are rolling. Pads on the
course swap it.

| ball | restitution | hard landing | what courses use it for |
|---|---|---|---|
| **rubber** | 0.85 | bounces, keeping most of v_z | the bounce that clears a gap or climbs a tier: **required** on some routes |
| **steel** | 0.15 | stunned (a wobble, about 1 s) | heavy: breaks crumbling tiles, ignores fans, sticks to magnets, sinks in water |
| **glass** | 0.40 | **shatters**: back to the last checkpoint | light and fast with high grip; the precise, fragile route |

The table is a first guess and is tuned in wave 2. A fall's "hard" speed
is per ball as well.

### 5.6 Determinism buys three features

The inputs are **one byte a step**: 55 bytes a second, about 3.3 KB a
minute. Fixed-point physics with no frame-rate dependence replays exactly,
which gives:

- **ghost** runs against your best time;
- **attract-mode** demos;
- a **test harness** that drives a recorded run on MartyPC and asserts the
  position at each checkpoint. That is how the rows in section 11 hold the
  physics, rather than relying on remembered coordinates.

---

## 6. Drawing: lanes, boxes and TITHE's wheel

### 6.1 One write per pixel

Every moving thing is drawn by the **box** method, Excitebike's and 1942's:

1. Take the union of the old and new footprints.
2. **Fill** it in RAM from the block dictionary.
3. Compose the sprites in depth order.
4. Re-apply the occluders.
5. Write the box to VRAM **once**, in raster order.

Nothing is erased on the glass, so nothing flashes, and nothing is written
twice (CLAUDE.md, Performance rule 2).

Because the ring address is world-locked, anything that did not move needs
**no** redraw when the camera scrolls: the background, an obstacle between
two of its frames, and the ball's old footprint all travel with the scroll
for free.

### 6.2 Lanes

| lane | rate | contents |
|---|---|---|
| **scroll** | must happen | the entering row-pairs (off screen, written before the flip) and columns (raced ahead of the beam) |
| **ball** | every frame | the ball, its shadow, the HUD box when the HUD moved |
| **contact** | every frame | the **one** obstacle the ball is touching or riding (a moving platform, a spinner). It is promoted out of the wheel, because a platform drawn a frame late under a ball drawn on time *looks* wrong |
| **wheel** | credit | the other 2–6 animated obstacles (section 6.3) |
| **HUD cells** | when changed | time and score digits |

### 6.3 TITHE's wheel, adapted (SPEC.md 125.5 on `tithe-new`)

The design is TITHE's, kept intact:

- **A credit in µs a frame**, after the scroll, ball and contact lanes have
  taken their share. It is **calibrated at level start** by timing one row
  and *N* rows of a box off the PIT, which gives the arrival cost plus a
  per-row cost. It is **trimmed** when a frame overruns (one
  `OSAPI_GET_TICKS` a frame).
- **The wheel resumes where it stopped**, so no obstacle starves.
- **Clocks are the tick's, not the draw count's**: a windmill that misses
  its slot is drawn one frame late at the *correct* angle, never slowed.
- **Seeded phases**, so two identical windmills never turn in lockstep.
- **A rate cap** (`IDLEFPS`-style), so a faster machine does not spin the
  windmills faster than the art was drawn for.
- **At most two frames of credit banked.**
- **Every advance is unconditional.** No commit redraws the pose it already
  drew; TITHE's `titheframe` asserts the same.

**One rule this game adds: collision uses the TRUE phase, not the drawn
one.** The simulation knows where the blade really is, and the wheel only
decides when that becomes visible. At about 4 frames a second for a
background animation, the lag is at most one frame of the obstacle's own
cadence. Obstacles that can hit the ball are therefore designed with a
**telegraphed** beat (a blade sweeps over a full second, not in one frame),
so a drawn-late blade is never one that already hit you.

**Off-screen obstacles** keep their clocks and draw nothing. One that
scrolls into view is drawn by the scroll lane as part of the entering strip,
at its current phase. The wheel only has to animate it from then on.

### 6.4 Big camera moves are transitions

**Tubes:** the ball is invisible while it is inside, so the camera *glides*
along the tube's path at the scroll lane's top speed (section 2.2). The tube
takes exactly as long to travel as the glide does. The rumble on the speaker
covers it, and the exit is on screen before the ball comes out.

**Teleports and respawns** are cuts. The 145 ms window rewrite is hidden by
a two-step "iris" (a black box closing on the ball) or simply by the CGA
border flash. It is a beat the player expects, not a hitch.

### 6.5 Predicted budget for one CGA frame (79.6k clocks)

| work | k clocks | note |
|---|---|---|
| simulation, 1–2 steps | 4–8 | cell lookups, slope table, sub-steps, obstacles' true phases |
| scroll: one row-pair | 8.4 | most frames during a descent |
| scroll: one column | 17–19 | rare: the dead zone and the glide |
| ball, shadow and contact boxes | 10–16 | |
| wheel credit | what is left, to 60 | about 2–4 obstacle commits |
| HUD cells | 0–5 | |

**Typical:** about 35–45k, so **60 Hz display looks reachable on the
CGA**. **Worst** (a column, a row-pair, contact and HUD in one frame): about
60k, still inside 79.6k.

Excitebike's governor (wait for retrace and feed the simulation the real
elapsed time; never throw a frame away) is the fallback when a frame
overruns. These are predictions; **wave 0 replaces this table with MartyPC's
cycle counts.** A real card's wait states are a field question
(docs/FIELD-MACHINES.md).

---

## 7. Memory

| claim | KB, predicted |
|---|---|
| package code and bss | 25–35 |
| course: block dictionary, metatiles and map | 24–38 |
| physics grid | 12–24 |
| occluder masks | 2–4 |
| ball: 64 frames × 4 shifts, mask, squash | 21 |
| obstacle art (6 kinds × 4–8 poses) | 8–16 |
| sound, text and front end | 4 |
| **total while playing** | **about 100–140 KB** |

That fits the 5150's 640 KB comfortably. It also explains the kern_small
refusal: kern_small's heap cannot hold it.

Following 1942's pattern, the course art is **fetched into claims on the
desktop before the bracket**, so that a refusal can still draw its toast
(§53.7). On kern_mega a claim is an LDT selector, so derived segments come
from `OSAPI_SEG`.

Every package region declares `OS88_REGION_MOVABLE` (§66.6.1.1). The game
holds no segment words that point inside itself, so the relocation proc is
a `ret`.

---

## 8. The mini-golf props, and the tube

Courses are built from **props**. Each prop is static art in the course
render, plus cells in the physics grid, plus optionally one animated
obstacle.

| prop | how it plays | 5150 cost |
|---|---|---|
| **Tube** | enter a mouth at any speed. The ball disappears, the camera glides along the path, and the ball comes out of the far mouth. Three kinds: **keep** (speed kept, direction set by the mouth), **launch** (a fixed exit speed, a cannon) and **drop** (out of a high mouth onto a lower tier) | none while hidden; the glide is the scroll lane |
| **Windmill** | blades sweep across the tunnel, so the ball must time its entry. A blade hit knocks the ball back with restitution | one wheel obstacle, 8 poses |
| **Loop-de-loop** | a scripted arc drawn as a *visible* path animation of the ball. Enter faster than v_min and you go round; slower, and you roll back down. A momentum gate | the ball box follows the path |
| **Volcano / hump** | a steep cone with the cup on top: too slow and you roll back, too fast and you fly off | heightfield only |
| **Bank and half-pipe** | carve round a corner without losing speed | heightfield only |
| **Moat bridge** | a narrow plank over water; the sides are hazards | heightfield only |
| **Funnel / drain** | the ball spirals into the centre, which is a tube mouth | heightfield only, plus a tube |
| **Clown mouth / castle gate** | one of three openings, each to a different tube exit (a shortcut, a dead end, or bonus points) | static |
| **Bumper** | a radial kick of fixed speed, which flashes and scores | one wheel obstacle, 2 poses (the contact lane while lit) |
| **Spring pad** | sets v_z high to reach an upper tier; the shadow sells the height | static, plus the second shadow box |
| **The cup** | the goal. The ball must arrive slower than a capture speed, or it lips out over the rim | static |

---

## 9. More mechanics that fit the style and a 5150

These are ordered roughly from cheapest to most ambitious. Each is costed
against the lanes above.

1. **Ball swaps.** *Promoted into the core game by D4: section 5.5.* A
   fourth ball, **sponge** (light, so fans and wind push it much harder), is
   still an idea.
2. **Surfaces as rules:** ice, sand, mud, grates that slow you only
   sideways, and boost chevrons. These are physics-grid nibbles only, with
   **zero drawing cost**.
3. **Conveyors and fans.** Conveyors are a surface nibble plus a wheel
   obstacle to animate the arrows. A fan is a force field that blows harder
   on a sponge ball than on a steel one.
4. **Switches and gates.** Rolling over a plate opens a gate elsewhere.
   That is a one-time redraw of a few blocks. Doors can be timed (the gate
   shuts again on a clock), which makes a route puzzle.
5. **Crumbling tiles.** A tile breaks once a steel ball, or any ball after a
   delay, has passed. Its blocks are swapped once for "hole" blocks and its
   cell becomes a hazard.
6. **See-saws and tilt plates.** A plate tips toward the side the ball is
   on. Three poses on the contact lane; the cell's shape follows the pose.
7. **Magnets.** A field pulls a steel ball onto a rail, and does nothing to
   rubber. Physics only.
8. **Pinball zone.** A walled section where **flippers** answer the grip
   key. Two contact-lane obstacles, plus bumpers. This is the closest nod to
   *Extreme Pinball*.
9. **Golf mode, on the same courses.** *D3: a possible SECOND game on
   this engine, after the first, which is direct control.* Instead of continuous control, you
   **aim and set power**, and the ball then rolls under physics alone.
   Strokes are scored against par. This mode suits a slow machine very well
   (input is rare, and the wheel gets every spare cycle), and it re-uses
   every course and prop. It is **cheap to add once the run mode exists, and
   could be the better game**.
10. **Combo scoring, the "Bonanza".** Bounces, bumpers and airtime
    *without touching the ground* chain into a multiplier. It rewards the
    fluid physics directly.
11. **Gems on the risky line.** Collectibles placed where the fast line is
    dangerous. Each is drawn in the static background, and taking it is a
    one-time block swap.
12. **Ghost race against your best time** (section 5.6). The ghost is drawn
    as a dithered ball on the wheel, at a lower rate.
13. **Link race over a null modem**, as WireBall and WireFleet do
    (`apps/os88link.inc`). Each machine renders its own view, and the other
    player's ball is a ghost fed at 18 Hz. The serial service in the bracket
    follows WireBall's hook (§53.2.2; kern_big's `FSXF_RATE`), or
    `os88link`'s polling where the hook is refused.
14. **Global tilt switches.** A switch tilts the *whole table*: a global
    gravity bias added to the slope term. The ball suddenly wants to go
    another way, and the art does not change, because the effect is pure
    physics.
15. **Weather.** Gusts of wind across an exposed bridge, telegraphed by a
    flag obstacle on the wheel.

---

## 10. Sound

The PC speaker only, through `apps/os88spkfx.inc` and the `snd` slots. Both
are legal in a bracket (§53.7); channel 2 is never touched directly.

| sound | when |
|---|---|
| **Rolling** | a click whose rate follows speed, and whose tone follows the surface (rough surfaces click faster, ice is silent) |
| **Bounce** | a short downward sweep, pitched by impact speed |
| **Tube** | a rumble for the whole ride |
| **Bumper** | a bell |
| **Cup** | a little fanfare |

Excitebike's engine sound (SPEC.md 102.5) is the precedent for a continuous
pitch tied to speed. `SOUND.DRV`'s FM output, where it exists (5150 #2's
Picomem), is a later polish, never a requirement.

---

## 11. Waves and stories

Each wave follows CLAUDE.md's "Building an app or game in waves":

- it is one reviewable push to one draft PR;
- it is checked on the host, and the rows it touched are **named**;
- the soak union and `test-full` run **once, after the last wave**.

The SPEC.md section is written before wave 1's code. It takes the next free
number at that time; the last section on `elendilon` today is 127.

**Wave 0: the spike (go/no-go).** A throwaway package with a 2D ring and a
generated test course, with no art pipeline and no physics beyond the arrow
keys.
- [x] The CGA ring: vertical steps into the slack, columns raced after the
      retrace, and a diagonal. The ring holds what the formula says
      (decoded off the card on MartyPC, as Excitebike's `excitebike_video`
      does). *Evidence: `bonanzaring`, all 8 directions, 0 bad pixels, at
      both the presented frame and the retrace start; its red arms go red.*
- [x] The same on the Hercules field. *Same row, same result.*
- [x] The phase-torus ball at the 4 pre-shifts, with its box. *Looked at
      on both cards; the Hercules mid tone is stripes, not the course's
      checker (SPEC.md 128.3).*
- [x] A MartyPC cycle count for each item in section 6.5's table. This is
      one measurement, taken once, because it *decides the design*: 60 Hz
      or 30 Hz, and whether `FSXF_RATE` is needed. *Decided: the full
      refresh on both cards, and `FSXF_RATE` is not needed. The table is
      SPEC.md 128.8.*

**Wave 0b: the camera and the optimisation round** (SPEC.md 128.9; the
review's findings 7, 9, 11, 12, 13; the numbers are SPEC.md 128.8's). The
owner's first play (86Box, CGA): slow scrolling is jerky, fast scrolling is
smooth.
- [ ] Three camera modes, `C` to cycle: GLIDE (rest or pan fast, with a
      lead; the default), FOLLOW (velocity-matched, even cadence), TRICKLE
      (wave 0's, for the A/B). The owner picks by feel.
- [ ] The Hercules ball takes the course's checker for its mid level.
- [ ] Box compose (23.5k clk, the largest working part): column-major fill
      with a `movsw`/`add di` chain, an unclipped word-wise ball path, no
      MUL.
- [ ] The column writer: find the wrap row once, unroll per block.
- [ ] The row writer: word columns outermost (the two CGA misses are
      two-row frames: rows 19k there).
- [ ] `S` kept incrementally; `rb*R` by shifts in `bz_row`, `bz_col`,
      `bz_boxw`.
- [ ] Do not write the overlap of two boxes twice; do not re-compose an
      idle ball.
- [ ] The box at window row 0 (SPEC.md 128.2 rule 4's open corner).

**Wave 1: the course pipeline.**
- [ ] `tools/bbcourse.py`: the text course → render → blocks, metatiles and
      map → physics grid → occluders. Deterministic, with a `--selfcheck`.
- [ ] The guest loads a course into claims and plays it with physics v1.
- [ ] Desktop window, FSX bracket, Esc/F, and claims dropped on every way
      out.

**Wave 2: feel.**
- [ ] Forces, surfaces, walls with restitution, air, bounce, stun.
- [ ] Final ball art, shadow and squash; occlusion behind props.
- [ ] Replays: input logs and a recorded-run test row.

**Wave 3: obstacles and the wheel.**
- [ ] Lanes; the wheel with calibrated credit, trim, seeded clocks and the
      rate cap.
- [ ] Windmill, bumper, moving platform (contact lane) and tubes (three
      kinds) with the camera glide.

**Wave 4: a game.**
- [ ] Five courses, with the props from section 8. The HUD, timer,
      checkpoints and cup.
- [ ] Speaker sound (section 10).
- [ ] The mouse as a tilt stick.

**Wave 5: the machines.**
- [ ] Hercules polish (pair art, its blank budget).
- [ ] kern_mega, through the ordinary FASTTICK bracket (SPEC.md 128.1).
- [ ] VGA runs the CGA arm; EGA, MDA and kern_small refuse with reasons.
- [ ] Disks: `make bonanzadisk` in four geometries. The package is `local`
      in `apps/RETIRED.txt` until the owner says it ships.

**Wave 6: the picks from section 9**, which the owner chooses: golf mode,
ghost, link race, ball swaps, and so on.

A "How It Was Built" diary is started in
[BOUNCE-BONANZA-DIARY.md](BOUNCE-BONANZA-DIARY.md).

---

## 12. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
**Decided by the owner, 2026-11-12:**

| # | decision | the owner's answer |
|---|---|---|
| D1 | 2D scrolling, or vertical only? | **2D.** |
| D2 | A trackball slot, or the tilt stick? | **The keyboard is primary.** A mouse is a possible bonus at the end; a non-trackball mouse is hard for this style of game |
| D3 | Run mode, golf mode, or both? | **Direct control first.** A golf-like game may follow later as a second game on this engine |
| D4 | What a hard fall costs | **Make it a mechanic, encourage it.** The rubber ball bounces, and that is required to clear some gaps and heights; the steel ball may be stunned; a glass ball may shatter (section 5.5) |
| D5 | 16 colours | **Not the focus.** It would suit a composite monitor; consider it if the render and art budgets allow (below) |
| D6 | The name | **`BONANZA` is the package** (`apps/bonanza/`, `BONANZA.O88`); the title is *Bounce Bonanza* |

**On D5: composite is the better 16-colour route.** On a composite monitor,
the CGA's 640×200 mono mode shows *artifact colour*: 160 colour pixels a
row in 16 colours. Unlike the 80-column text trick (section 2.8), it is a
**graphics mode, so there is no snow**, and its 6845 ring is the same 8 KB a
bank with the same 80-byte rows, so **this engine scrolls it unchanged**.
The horizontal step stays one word, which is 4 colour pixels: the same
fraction of the screen as now. The cost is a second art set (the same bytes
per row as the 4-colour set), and an RGB monitor shows it as stripes, so it
is an option, never the default. The owner's CGA drives an IBM 5153 RGB, so
it needs a composite monitor to judge. Not before the game is.

## 13. Risks

- **Real-card VRAM wait states.** MartyPC charges the measured 86 clocks a
  word, and a real IBM CGA may differ. Excitebike carries the same caveat;
  a field run settles it.
- **The beam race for columns** is the one part that a screenshot cannot
  check. `m.flicker()` on a frame with a column write is the instrument
  (PERFORMANCE.md Part 3.1).
- **Whether 8 px horizontal steps feel acceptable.** The dead zone and the
  glide are the mitigation. The fallback is narrower courses (D1 makes this
  a design choice, not a rewrite).
- **Occlusion ambiguity.** The authoring tool refuses what it cannot key, so
  this risk lands as course-design constraints, not run-time bugs.
