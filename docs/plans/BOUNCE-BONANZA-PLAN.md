# BOUNCE BONANZA — an isometric rolling-ball game for the 5150 (investigation and plan)

**STATUS: WAVE 0 (the spike) DONE, a GO (the owner, 2026-11-12: "we are good
to continue"): both cards hold the full refresh on MartyPC (CGA 59.8 Hz,
Hercules 50.8 Hz). WAVE 0b (the camera and the optimisation round, SPEC.md
128.9) DONE: busy time 43% of a CGA refresh and 37% of a Hercules one, no
misses, three camera modes for the owner to choose by feel. WAVE 1 (the text
course, `tools/bbcourse.py`, physics v1, SPEC.md 128.10) DONE and measured:
busy 46.5% of a CGA refresh and 39.4% of a Hercules one, no misses; its story
1.3 waits on open question O8. WAVE 2 NEXT ("feel": three balls, bounce, stun
and shatter, the keyboard's ramp, Hop and Grip, surfaces, the shadow,
replays, and O8's answer): its contract is SPEC.md 128.11. The owner's
decisions are in section 12.** The package is `BONANZA` (`apps/bonanza/`). Below is the
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
format (`apps/bonanza/courses/*.bbc`; `apps/bounce/` is already BOUNCE,
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
blocks, so it is cheap. Some depth cases are ambiguous: a block's pixels
can have several depths and tops. Wave 1's answer (SPEC.md 128.10.4.4) is to
split rather than flag: one record for each block, occluding cell and 2 px
band of tops, so every pixel is keyed to within 2 px. What the tool REFUSES
at build time is the cost - since wave 2 (SPEC.md 128.11.4), more than 4
records in one block or 128 in a block row, after an exact merge of the
records no reachable position tells apart (wave 1's 24 a block row and 8
laid were the wrong quantities) - so ambiguity and expense land as
authoring errors at build time, not glitches at run time.

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
    (wave 1: not needed while the ground speed stays under the ball's
    radius a step, SPEC.md 128.10.7.2)

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

**Teleports and respawns** are cuts when the destination is off the
window. The 144 - 157 ms window rewrite is hidden by a two-step "iris" (a
black box closing on the ball) or simply by the CGA border flash. It is a
beat the player expects, not a hitch. A respawn whose cell is already on
the window is no cut: the ball is placed and the camera pans (SPEC.md
128.10.8, open question O5).

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
- [x] Three camera modes, `C` to cycle: GLIDE (rest or pan fast, with a
      lead; the default), FOLLOW (velocity-matched, even cadence), TRICKLE
      (wave 0's, for the A/B). The owner picks by feel.
      *Cadence measured per mode and card (SPEC.md 128.9): at a slow ball
      FOLLOW steps as often as TRICKLE; only GLIDE turns the hops into pans.*
- [x] The Hercules ball takes the course's checker for its mid level.
      *Selfcheck: 0 of 24,596 mid pixels wrong; looked at, zoomed.*
- [x] Box compose (23.5k clk, the largest working part): column-major fill
      with a `movsw`/`add di` chain, an unclipped word-wise ball path, no
      MUL.
      *23.5k -> 11.5k clk on both cards (SPEC.md 128.9's table).*
- [x] The column writer: find the wrap row once, unroll per block.
- [x] The row writer: word columns outermost (the two CGA misses are
      two-row frames: rows 19k there).
      *A row ~9.4k -> 7.5k (CGA), ~19.2k -> 13.7k (Hercules); 0 misses.*
- [x] `S` kept incrementally; `rb*R` by shifts in `bz_row`, `bz_col`,
      `bz_boxw`.
- [x] Do not write the overlap of two boxes twice; do not re-compose an
      idle ball.
- [x] The box at window row 0 (SPEC.md 128.2 rule 4's open corner).
      *Built; the wave-0b course cannot reach it (SPEC.md 128.9 item 6), so
      `bz_late` = 0 is true by construction until a later wave's physics
      reach the window's first row - that wave owes it a probe that does.*

*Open, found by wave 0b's review:* each ball part carries 15,360 bytes that
can never be drawn (`bz_boxc` takes shift `s = px & 3`, already fixed by the
frame's `px & 7`, so only 64 of the 4 x 64 shift/frame entries are reached).
Indexing the frames by `f` alone (`16 + 320 + 64 x 80` bytes a part) saves
about 15KB per heap claim and the disk bytes of both parts, and drops the
`5040 s` term from `bz_boxc`; SPEC.md 128.3 pins the part's size this round,
so it is a later wave's change. GLIDE's "fast" test is `|v|` against the
full refresh's step rate (SPEC.md 128.9); the ball's travel a frame is the
rate-proof form, a later wave's change made with the route re-checked.

**Wave 1: the course pipeline and physics v1** (the contract is SPEC.md
128.10, written before the code and revised after three review lenses).
Decided there, against this plan: the map stays FLAT, one word a block
cell, and metatiles (section 3) are not taken (SPEC.md 128.10.1); a course
is two PARTS, one a card, each carrying the picture, the occluders AND the
physics grid - one fetch and one claim a launch, as wave 0b - and not a
data file (open question O1, which a file's hostile bytes make a priced
validation pass, not a free addition); the physics cell is one tile in
ground units, the ball is a CIRCLE pushed out of walls along the contact's
normal, it leaves the ground when the floor falls away faster than gravity
and keeps the floor's vertical speed, and a ball two tiles past every solid
cell is respawned (SPEC.md 128.10.7); ramps are at most 4 half units a tile
(2 along both axes) so the camera can follow, and the speed caps are set so
D4's rubber rebound can clear 4 units (128.10.7.2), and the ground cap
(1.5 gu a step) is under the ball's 6 gu radius, so plan 5.2's sub-steps
are not needed; occluders are records cut per (block, cell, 2 px band
of tops), laid back over the NEW footprint's blocks only, with a margin that
keeps a rolling ball whole on the ground in front of it (SPEC.md
128.10.4.4); wave 1 is the wave that probes the row-0 box (SPEC.md
128.10.11.2). Every cost below is PREDICTED until the final pass.
- [x] **1.1 A course is text.** `apps/bonanza/courses/bench.bbc` ("Proving
      Ground", `K = 0`: wave 0b's test course in the format of SPEC.md
      128.10.3, its ramps inside the limits, the return leg's steps made a
      climbable ramp, and its holes off the autopilot's legs)
      and `first.bbc` ("First Roll", `K = 1`, the worked example and the
      course Enter plays) compile with ONE `tools/bbcourse.py` run over the
      Makefile's explicit `BZ_COURSES` list (never a glob), which writes
      `bzcourse.inc` whole, its `OS88_PART` rows included. Everything under
      `apps/bonanza/courses/` ships; the selfcheck's malformed inputs are
      strings inside the tool. *Verified: `bonanzacourse` items 1 and 2 -
      two compiles byte-identical, and every grammar and bound refusal fires
      on its bad line, reserved statements included.*
      *Final pass: `bonanzacourse` ok - two compiles byte-identical file for
      file (`BZ0C`/`BZ0H`/`BZ1C`/`BZ1H.BIN`, `bzcourse.inc`), and all fourteen
      refusals fire on their lines, reserved statements included.*
- [x] **1.2 The picture comes from the course.** The renderer MOVES from
      `tools/bonanza_assets.py` into `bbcourse.py` (the palette and the
      Hercules checker are imported, not copied); `BZ<K>C.BIN` and
      `BZ<K>H.BIN` in `BZC1` (absolute map offsets, `MAPSH`, `ROWB`,
      occluders, the grid); `Y0` the least that holds every reachable
      footprint, the reach bounded by the OPEN rule and the launch apex.
      The tool checks every part it wrote and prints the sizes and counts
      SPEC.md 128.10.10 quotes. *Verified: `bonanzacourse` items 3 and 6 (the
      decode back on both cards, with its negative control); the `--png`
      previews looked at on both cards.*
      *Final pass: `bonanzacourse` items 3 and 6 on both courses (the moved
      map word caught); the `--png` previews looked at on both cards;
      `bonanzaring`'s glass equal to the picture on both cards. Parts 54,214
      (`BENCH`) and 10,614 (`FIRST`) bytes a card, over SPEC.md 128.10.10's
      predictions (its measured table).*
- [ ] **1.3 The ground knows its shape.** The grid in `BZG1` inside each
      course part: heights, slopes, kinds (4 - 15 reserved for a later
      wave's shapes), NEAR and OPEN void, SAFE and OCC, the start and the route;
      the occluder records and masks inside their bounds (24 a block row, 8
      laid at any position). *Verified: `bonanzacourse` items 4 and 5 - the
      grid's plane equals the drawn geometry at every integer point, and the
      records' composite equals the per-pixel buffer's at every reachable
      cell in both air states, with its negative control.*
      *Final pass: `bonanzacourse` items 4 and 5 hold (`BENCH` 2,312 positions
      and 1,940 at the fractional-height line, `FIRST` 276 and 252, 0 differ;
      the lowered depth and the cleared OCC flag caught). NOT ticked: the
      bounds are not met - 79 / 29 on `BENCH` and 32 / 23 on `FIRST` against
      24 / 8, refused provisionally at 96 / 32 - and the choice is the owner's
      (SPEC.md 128.10.12 O8).*
- [x] **1.4 The ball part loses what it never drew.** `BZB1`, 64 frames each
      at shift `f & 3`: 5,456 bytes a part against 20,816. *Verified:
      `bonanzaassets`; `bonanzaring`'s glass on both cards.*
      *Final pass: `bonanzaassets` ok (5,456 bytes a part, every frame at
      shift `f & 3`, the checker 0 wrong); `bonanzaring`'s glass on both
      cards.*
- [x] **1.5 The ball rolls on the course.** `bzphys.inc`: the guest fetches
      the course and the ball and plays physics v1 - slopes pull, walls push
      the ball out and it slides along them at any angle, a fast ball flies
      off a lip and lands with its drop and impact speed recorded, a pit
      puts it back on the last SAFE cell (a cut only when that is off the
      window), and the goal ends the play with `Finished in <s.hh> s` on the
      face. Space and Left Shift are reserved for wave 2's Hop and Grip.
      No guest-side header check: the parts are checked at build time.
      *Verified: `bonanzacourse` item 7 (the scripted runs on `FIRST`, with
      red controls); `bonanzaphys` - the guest's state equals
      `bbcourse.Physics` at every frame of the benchmark on both cards, and
      the poked pit, lip, rail and goal scenarios on `FIRST`, with red arms
      `slope`, `respawn` and `takeoff`; and one boot to look on each card:
      the ball rolling behind the traverse's blocks and dropping into a pit
      behind its rim.*
      *Final pass: `bonanzacourse` item 7 with both red controls;
      `bonanzaphys` ok - the guest equal to the model at every frame of the
      benchmark (1,091 steps CGA, 1,286 Hercules, one trajectory) and in the
      pit, lip, rail and goal scenarios on both cards (`Finished in 0.45 s` /
      `0.54 s` by the formula); red arms `slope`, `respawn`, `takeoff` each
      red at its own leg. The look boots were the physics and occluder stages'
      (the pit, and the traverse's block on the Hercules).*
- [x] **1.6 The ball goes behind things.** The occluder pass in the box
      compose, run only on an OCC cell, over the new footprint's blocks
      only, each row's walk stopped past the footprint; the idle test
      compares the ball's cell row, height and air flag too. *Verified:
      `bonanzaring` with the oracle laying the records back, at least one
      checked frame with a record laid, red arm `occ`; `bonanzacourse` item
      8 prints the bench route's OCC share and records laid.*
      *Final pass: `bonanzaring` - 6 checked frames a card hiding ball pixels
      behind a record (69 px), 132 records laid on the CGA's benchmark and 455
      on the Hercules'; red arm `occ` red on both cards; `bonanzacourse` item
      8: 23% of the route's steps on an OCC cell, 1.11 laid on average.*
- [x] **1.7 Nothing is left behind.** Esc, F, Alt+Enter, the benchmark's
      end and the goal each drop both claims; a refused fetch drops what was
      fetched. *Verified: `bonanzaexit` on both cards - every part row with
      `OP_FETCHED` clear, `op_seg` 0 and `OP_R_ZKB` back to its pre-launch
      packed length, and the instance's claims as before the launch read
      through `tools/heapmap.py` - red arm `leak`; the desktop refusal by
      review.*
      *Final pass: `bonanzaexit` ok on both cards and all five ways out -
      every row unfetched with its packed length back, the claims as before,
      two more inside every bracket; red arm `leak` red at the goal and only
      there. The refused fetch by review (`jc .drop`). Found by `bonanzamega`:
      `bz_launch` now loads ES with its own segment before the drops
      (kern_mega's #GP at `op_drop`'s `pop es`).*
- [x] **1.8 The benchmark on a real course.** B drives the bench course
      under physics in GLIDE; the route re-chosen with a host model of GLIDE
      (not kept) so all eight step directions occur at least five times on
      both cards. *Verified: `bonanzaring` (every direction on the glass)
      and `bonanzaperf` (the floor, the instruments, the OCC frames and the
      two-box frames) in the final pass, with the A/B leg against wave 0b;
      SPEC.md 128.10.9's predictions - busy about 45 - 48% of a CGA refresh
      and 39 - 41% of a Hercules one - get their measured column.*
      *Final pass: `bonanzaring` every direction on both cards; `bonanzaperf
      --ab` - busy 46.5% of a CGA refresh (59.96 Hz) and 39.4% of a Hercules
      one (50.87 Hz), inside 128.10.9's predictions, 0 misses, against wave
      0b's 43.3% / 37.0% on its own course (SPEC.md 128.10.9's measured
      table).*
- [x] **1.9 The row-0 box, reached at last.** A poked probe holds the
      ball's box at window row 0 while GLIDE pans up and across (play
      reaches row 0 only in the air, SPEC.md 128.10.4.1). *Verified: `bonanzaring`'s probe - at least five frames
      a card with the boxes at window row 0 and an entering column, the
      card equal to the picture at `bz_tf` and `bz_presented`, `bz_late` 0 -
      and its red arm `row0` (the whole column first, item 6's order
      undone) going red.*
      *Final pass: `bonanzaring`'s probe - 11 frames on the CGA and 7 on the
      Hercules with the boxes at window row 0 and an entering column, card =
      picture at `bz_tf` and `bz_presented`, `bz_late` 0; red arm `row0` 11
      late of 11 on the CGA (the CGA only: the Hercules' blank holds the whole
      column). It failed first: the guest's beam reckoning, a FASTTICK
      interrupt and an overrunning probe, all measured and fixed - and the
      probe moved to the top clamp, where play reaches row 0 (SPEC.md
      128.10.11.2, 128.9 item 6).*
- [x] **1.10 kern_mega, built and RUN.** Every new segment is a part's own,
      used whole (the grid at `GRIDOFF` inside the course part), nothing
      written through CS and no patched immediate (the map stride is read
      from the part's header), no `PKG_MEGA` arm (SPEC.md 128.10.6.4).
      *Verified: `bonanzamega` in the final pass - kern_mega on 86Box's
      `286-mega-multimon`, the window on its Hercules display, the
      benchmark and a play: no fault, no leak; red arm `segadd`.*
      *Final pass: `bonanzamega` ok after the ES fix - benchmark and play on
      86Box's Hercules, no part fetched and no claim left after either, no
      exception charged to the package; red arm `segadd` red with a #GP.*
- [x] **1.11 The record.** README, the face's title line, `make help` lines
      for `bonanza-course-check` and the new rows, the Bonanza row in
      docs/HEAP-CLAIMS.md (both claims pinned, bucket C; the
      `tests/pins.txt` lines `bz_cseg` and `op:BZ_P_BALC` stand), SPEC.md
      128.10's measured tables, the diary's wave-1 entry, and
      `docs/INDEX.md` regenerated. *Verified: `make` (the doc gates) and
      `tools/os88index.py --check`.*
      *Final pass: README's status, the face's title, `make help` (`os88help
      --check`), the HEAP-CLAIMS row, SPEC.md 128.10.9 and 128.10.10's
      measured tables, the diary's entries, `docs/INDEX.md` current
      (`os88index.py --check`), `checkdocs` 0 problems.*

**Wave 2: feel** (the contract is SPEC.md 128.11, written before the code
and revised after three reviews of it).
Decided there, against this plan: the ball is picked on the desktop (`M`,
starting from the course's own `ball`), and section 5.5's swap pads are wave
4's; a landing is judged against the floor's own rate, and a rebound is at
most `e` times the ball's downward speed, so a bounce never climbs above the
height its energy came from - a rubber-only route is a drop and a bounce to
a ledge BELOW it, and climbing stays ramps and the spring pad (SPEC.md
128.11.5.3); Space at a contact replaces the rebound with at least a Hop but
never adds to it, so it cannot pump a bounce and the reachable set stays
bounded (SPEC.md 128.11.4.4); an airborne ball lands on a floor up to 4 px
above it, as a rolling one climbs it; a goal is a finish line crossed in the
air too; the materials' constants and each material's force, drag and brake
on each surface are generated tables, PROVISIONAL until the owner has rolled
them; section 5.2's restitution is a stone wall's per material and a bumper's
for every ball; Grip's Left Shift is read from the BIOS's shift flags,
because the kernel's key-state map takes a 101-key keyboard's fake shifts as
Shift (O19); section 4's shadow is skipped where the floor can hide a
grounded ball (`OCCG`), and kept out of a box of its own while the ball's
cell can be hidden; open question O8 is answered by building the Hercules
table and part on the guest (one part a course and one a ball on the disk),
an exact merge of the records and a per-BLOCK bound, not by narrowing the
reachable set to pits (option c, measured and declined: SPEC.md 128.11.4.5).
Sound (section 10) stays wave 4's. Every cost and size below is PREDICTED
until the final pass; the rows run once, after the last batch.
- [ ] **2.1 One part a course, one a ball.** The disk carries the CGA's
      course blocks and ball frames only; a Hercules launch builds `BZ_HTAB`
      (512 bytes) in the idle box buffers and translates the parts in place
      through it before the bracket - no table in the image. Part rows:
      three balls, then one a course. `BONANZA.O88` predicted 47 - 51KB
      against wave 1's 64,509, with a third course and two more balls.
      *Verify: `bonanzaassets` - `bbcourse.htab()` equal to `herc_pair`, the
      rubber part translated equal to wave 1's Hercules ball part, with red
      controls; `bonanzaring`'s Hercules glass checks the guest's built table
      (red arm `htab`); `bonanzaexit` over the new rows; `bonanzamega` builds
      and translates on kern_mega (red arm `hxcs`); the package size printed
      by the build.*
- [ ] **2.2 Occluders the courses meet (O8).** Records of one block that no
      reachable position tells apart are merged (exact); the bounds become
      at most 4 records a block and 128 a block row, which `BENCH` and
      `FIRST` meet before the merge (`BENCH` with no headroom on the block
      bound); the provisional 96 / 32 go; the new grid flag `OCCG`; the
      reach with the Hop's launch and bounces bounded by energy, iterated to
      a fixed point, with discrete flights. *Verify: `bonanzacourse` items
      2, 4, 5, 6 - the merge lays the same pixels as the unmerged records
      for every query (negative control: a forced merge of differing
      verdicts fails), the refusals fire, the counts, rounds and `Y0`'s
      source printed (measured on the host with the contract's rule:
      `BENCH` `Y0` 156, 2,938 records merged to 2,645; `FIRST` `Y0` 36, 334
      to 290).* This also closes wave 1's story 1.3.
- [ ] **2.3 Walls give some of it back.** Restitution at the edges, the
      corner and the fallback - a stone wall's per material (rubber 0.38,
      steel 0.13, glass 0.25), a bumper rail's 0.90 for every ball - with a
      minimum that stops a pushed ball chattering; the wall-edge test made
      symmetric (wave 1's P1: no more creep against east and south walls).
      *Verify: `bonanzacourse` item 7 (the rail's rebounds and time to rest
      per material, a bumper's, the east wall resting at 10.00 like the west
      at 6.00); `bonanzaphys`'s `rail`, `bumper` and `eastwall` scenarios on
      both cards, red arm `edge`.*
- [ ] **2.4 Keys that feel analogue.** The arrows' force ramps over 146 ms
      and coasts on release (a quick re-press resumes); Hop on Space (from
      the ground, or at a contact inside its 110 ms window, so Space at a
      Hop's landing hops again); Grip on Left Shift, read from the BIOS's
      shift flags (brakes and carves, and catches a bounce); half-force air
      control; an airborne ball lands on a half-unit step instead of
      bouncing off it. *Verify: `bonanzacourse` item 7 (each material's
      ramp, the Hop's rise, window, contact Hop and step-up, Grip's stop, the
      catch); `bonanzaphys`'s `ramp`, `hop`, `hopagain`, `stepup`, `grip`
      and `catch` scenarios, red arm `airwall`; `bonanzareplay`'s injected
      log covering every key bit; `bonanzamega`'s grey arrows with NumLock
      on leave Grip clear (red arm `shiftmap`).*
- [ ] **2.5 Three balls, and a hard fall is a mechanic (D4).** Rubber
      bounces (a 6-unit drop rebounds 3.7 units and carries 4.8 tiles, then
      settles in 3.2 s), steel is stunned and stopped dead for a second by a
      fall of 2 units, glass shatters on a fall of 3 and comes back on its
      last SAFE cell, each judged on the impact relative to the floor so a
      Hop down a ramp is not a fall; steel is the heavy ball (slow to start,
      a 13-tile coast), glass the light one (quick, a 341 top, stops in under
      a tile); `M` picks the ball on the desktop, `N` the course (its ball
      with it). *Verify: `bonanzacourse` item 7 on `TRIAL` with all three
      balls; `bonanzaphys`'s `bounce`, `stun`, `shatter` and `ramphop`
      scenarios with red arms `bounce`, `stun`, `shatter`, `absimpact`; one
      boot to look on each card at each ball's landing.*
- [ ] **2.6 Floors with a character.** Ice (no drag, a push of 1 for every
      ball), sand (a 32nd drag, a push of at least 2), a bounce mat (every
      ball bounces, none is hurt: a trampoline, 5.3 s from a 6-unit drop
      unless Grip or Space ends it), each drawn with its own top; every
      material moves on every surface. *Verify: `bonanzacourse` items 2, 4
      and 7 (every pair from rest; steel stopped on ice leaves it);
      `bonanzaphys`'s `ice`, `sand` and `mat` scenarios; the `--png`
      previews looked at on both cards.*
- [ ] **2.7 The ball looks like what it is, and where it is.** Three looks
      inside one black rim (rubber's spots, steel's seam band, glass you can
      see the course through); the spin's vertical phase off the GROUND, so
      a bouncing ball does not turn; a checkered SHADOW on the floor under a
      ball in the air; squash on a hard landing, drawn only while the ball
      is at its floor; a dazed wobble while stunned; a four-frame shatter.
      *Verify: `bonanzaassets` (`BZB2`, every material, the black ring on
      both cards, red controls); `bonanzaring`'s oracle with the shadow, the
      sprite and the ground phase on both cards, red arm `shadow`; the look
      boots, with each ball previewed over a cyan tile, a white tile, a ramp
      and a magenta face on both cards.*
- [ ] **2.8 A ball and its shadow, drawn once, in raster order.** Up to four
      boxes (the ball's and the shadow's, old and new), each composed with
      everything that meets it, written interleaved with the entering column
      in raster order; the occluder pass decides once a frame and lays into
      every box; no shadow box of its own while the ball's cell can be
      hidden; lateness checked for every box, interrupts off for the first
      only; the idle test knows the sprite and the shadow. *Verify:
      `bonanzaring`'s TRIAL leg - card equal to the oracle at `bz_tf` and
      `bz_presented`, a frame with the shadow in its own box and one with
      three or more boxes, the order check on every frame, one pass a frame
      (red arms `boxfirst`, `pass2`); the multi-box row-0 probe (red arm
      `late2`); `bonanzaperf`'s TRIAL leg counts the boxes.*
- [ ] **2.9 A course that needs the rubber ball.** `TRIAL`, "Bounce Trial"
      (`K = 2`): a 6-unit drop onto a floor at least 4 tiles deep and a
      2-tile gap to a ledge 2 units up that only the rubber bounce reaches,
      a steep ramp long enough to catch its own throw, ice with bumper rails,
      sand before the goal, a mat off the route; its flights toward the
      viewer, over no cell that can hide the ball; its route for the
      autopilot. And `FIRST`'s goal, a finish line a rubber ball can now
      cross in the air. *Verify: `bonanzacourse` items 7 and 8 (the sweep:
      rubber lands on `G` in at least a quarter of approach speeds and
      offsets, steel and glass never, no ball without the bounce; the route
      reaches the goal without a fall and with no airborne step over an
      `OCC` cell; `FIRST` finished with each ball); one play by eye on each
      card.*
- [ ] **2.10 Replays.** A play is logged as one key byte a step,
      run-length coded in 4,096 bytes of bss with the current run in two
      fixed cells; `R` on the desktop replays it on either card, the same
      steps whatever the frame rate; the host model runs the same log; a log
      is trusted only because the package wrote it. *Verify:
      `bonanzareplay` - a real-keys play on the CGA whose log the model
      reproduces at every frame, its replay on both cards with the same end
      state, and an injected log covering every key bit and state; red arms
      `hopbit` and `framekeys`.*
- [ ] **2.11 A camera that knows the frame rate, and keys that do not
      repeat.** GLIDE's "fast" test is the ball's travel over four frames
      (the per-card constants go), and the benchmark's route is re-proved
      with a host model of GLIDE that is KEPT this time; C, M and N held on
      the desktop are one press each until `OSAPI_KEY_DOWN` says the key
      came up (a window timer polls it), and a release and a second press
      are two. *Verify: `bonanzacourse` item 8 (every direction at least
      five times on both cards at 0.96 - 1.04); `bonanzaring` (all eight on
      the glass); `bonanzaexit`'s held and re-pressed keys, red arms
      `crepeat` and `overswallow`.*
- [ ] **2.12 kern_mega, run.** The table is built in the package's bss and
      the translation writes the fetched parts' own selectors (as
      `op_fetch`'s own expansion already does); the log and the boxes are
      bss; no `PKG_MEGA` arm. *Verify: `bonanzamega` - the Hercules display
      (so every launch builds and translates), the benchmark, a play with
      Hop and Grip and its replay, the grey arrows: no fault, no leak; red
      arms `segadd`, `hxcs`, `shiftmap`.*
- [ ] **2.13 What it costs.** Busy on the benchmark predicted 48.0 - 48.6%
      of a CGA refresh and 40.7 - 41.3% of a Hercules one (the step priced
      instruction by instruction and taken 1.3 times, as wave 1 measured);
      `TRIAL`'s airborne frames +4 - 12k with a shadow and 0 misses on its
      route; a fall behind geometry with the pass at its bound may present at
      2 refreshes on the CGA, counted; the image about 15,100 bytes, bss
      about 5,700, claims while playing `BENCH` about 57.5KB. *Verify:
      `bonanzaperf` - the floor and the instruments on both legs, the A/B
      leg against wave 1 (`2df3f469`, fetched, or SKIP with the reason), the
      misses and the camera's rows panned per bounce; SPEC.md 128.11.15 and
      128.11.16 get their measured columns.*
- [ ] **2.14 The record.** README, the face's lines and keys, `make help`
      for the new row, `BZ_COURSES` with `trial.bbc`, docs/HEAP-CLAIMS.md's
      Bonanza row and `tests/pins.txt`'s line REWORDED as SPEC.md 128.11.3.1
      says (one part a course, one a material, `op:BZ_P_BALR`) with the new
      sizes, the diary's wave-2 entries, `docs/INDEX.md` current. *Verify:
      `make` (the doc gates), `tools/os88index.py --check`, `checkdocs` 0
      problems.*
- [ ] **2.15 Two cameras, by the owner's choice.** After playing wave 1 the
      owner kept GLIDE (the default) and TRICKLE ("classic") and dropped
      FOLLOW ("the most jerky"): `C` toggles the two in play and on the
      desktop, the face names the mode, and FOLLOW's code is deleted
      (SPEC.md 128.11.11.1). *Verified: `bonanzaring`/`bonanzaexit` cycle two
      modes, a held `C` is one toggle, and the look boot shows both.*

**Wave 3: obstacles and the wheel.**
- [ ] Lanes; the wheel with calibrated credit, trim, seeded clocks and the
      rate cap.
- [ ] Windmill, bumper, moving platform (contact lane) and tubes (three
      kinds) with the camera glide.

**Wave 4: a game.**
- [ ] Five courses, with the props from section 8 and section 5.5's
      ball-swap pads (SPEC.md 128.11.5.4). The HUD, timer, checkpoints and
      cup.
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
- **Occlusion ambiguity.** The authoring tool keys every occluding pixel
  to within 2 px (records split by band of tops) and refuses a course past
  its record bounds (SPEC.md 128.10.4.4), so this risk lands as
  course-design constraints, not run-time bugs.
- **`BENCH` sits on the block bound.** Wave 2's bound is 4 records a block
  (SPEC.md 128.11.4.2) and `BENCH`'s fullest block holds exactly 4 before
  and after the merge, so the next route or geometry change can refuse it.
  The refusal names the block; moving the geometry, or the owner pricing a
  bound of 5, is the answer - never a quiet raise.
- **A fall behind geometry on the CGA.** With the occluder pass at its
  bound, a falling ball over a cell that can hide it is predicted at 1.06 -
  1.11 CGA refreshes (SPEC.md 128.11.15): it presents a frame late and is
  counted. `TRIAL`'s flights are built to cross no such cell; wave 4's
  courses will meet it.
- **Feel numbers off a model.** Wave 2's materials, surfaces and course
  rules are the host model's discrete figures (SPEC.md 128.11.5), checked
  against the guest frame by frame - but whether they FEEL right is the
  owner's play, and every one of them is PROVISIONAL until then (O11).
