# A multiplayer first-person shooter for the 5150, in text mode: investigation

**STATUS: WAVE 0 BUILT (the renderer spike, `apps/wirearena/`), measured in
section 16.** The owner's answers to section 14 (2026-11-12): prototype to
decide 40 vs 80 columns; spend the relative-mouse bytes (done, SPEC.md 9.14 -
38 resident bytes on kern_big and kern_mega, refused on kern_small for its
budget); raw Ethernet pausing TCP is acceptable; kern_small decided once the
size is known.

The owner asked for this on 2026-11-12, on branch `multiplayer-fps` (cut from
`elendilon` at `9f5c3c9c`):

> *Investigate a 3D, ~30FPS, multiplayer (ethernet, serial if its plausible)
> FPS for a 5150 ... block and half block characters, making effective use of
> black/negative space ... arenas; multiple layers and jumping if it is
> viable ... modern mouse aiming ... stick figure like ... a computer opponent
> ... a single pistol to start with, but investigate arcing weapons or
> projectile types that are not instant ... fluid animations ... Make other
> suggestions, and look into what performance room we have.*

This document is the answer. It separates three kinds of claim:

- **Measured** means a number was taken. Each one cites its source.
- **Predicted** means arithmetic from PERFORMANCE.md's unit costs. Nothing
  has run it.
- **Proposed** means a design choice. None of it is built.

The working title used below is **WireArena**. It follows the house naming
for link games (WireBall §109, WireFleet §114) and is the owner's to change.

---

## 1. The verdict, short

| ask | verdict |
|---|---|
| ~30 fps on a 5150 | **Plausible in text mode, and only there.** A whole 80x25 frame costs 45% of a 30 fps budget to present (measured). Presenting only the changed cells of a mostly black frame costs 13-26% (measured). The rest of the frame is predicted to fit, at about 30 fps for a 1v1 duel and 22-26 fps in a busy four-figure scene (section 4.7). No graphics mode can do it: the fastest 3D frame this tree has measured on a 5150 is 10.8 fps (Clear Skies' C160 tower, SPEC.md 88). |
| block / half-block characters, black negative space | **Yes, and the black is what makes the frame rate possible.** Present cost is per changed cell, so walls drawn as thin edges on black are cheap and filled walls are not. |
| line glyphs for wall edges, solid blocks for the opponent | **Yes, and recommended as the design's central rule** (section 4.4). It also carries over to the mono Hercules, where colour cannot do that job. |
| multiple layers and jumping | **Jumping: yes.** **Layers: "2.5D" yes** — raised platforms, tiers round a pit, steps, jump pads. **No true room-over-room**: a bridge you can walk under is out. |
| modern mouse aiming | **Yes, with one OS gap to close.** Yaw comes from mouse X. Pitch is a y-shear of the horizon, the Heretic/Duke trick, which costs nothing per pixel. **The OS has no relative mouse** (section 7). It needs about 10 resident bytes plus an API cell, or the package can borrow the UART the way WireBall does. |
| stick figures, walls never hiding or blurring them | **Yes.** Figures are drawn last, in solid bright blocks, depth-tested per column. Walls are thin and dim, with black between. |
| computer opponent | **Yes, cheaply** (section 9). It can reuse Pixelstein's line-of-sight walk and Tank's aim, and runs as a "virtual remote player". |
| pistol, plus arcing and slow projectiles | **Yes.** Projectiles are cheap to draw (one glyph each) and almost free to network (a spawn event; the flight is deterministic). Section 6. |
| fluid movement, hit and death animations | **Yes, within a cell grid.** Keyframes are pre-projected on the host and interpolated on the guest at about 4k clk per visible figure (predicted). The motion is as fluid as an 80x25 grid can show; section 5 is honest about that limit. |
| Ethernet | **Plausible, with a caveat.** No package can reach UDP. The route is `NETV_RAW` broadcast frames (section 8.2). **MartyPC has no NIC**, so development runs on QEMU and 86Box. On the owner's own hardware, 5150 #2 (the PicoMEM's NE2000) is the only XT that can play. |
| serial | **Plausible for two players at 2400 baud** (the practical XT ceiling, SPEC.md 114.3), using owner-authority state sync. **But 5150 #1's one COM port is the mouse's**, so a serial match there is keyboard-aimed. |

---

## 2. The machines it is for

From docs/FIELD-MACHINES.md:

- **5150 #1, the owner's:**
  - 8088 at 4.77 MHz, 640 KB.
  - **Hercules GB101 (it boots on this) and IBM CGA**, each on its own monitor.
  - **One serial port, COM1, with the mouse on it.**
  - An LPT port at 3BC.
  - **No sound card. No NIC.**
- **5150 #2:**
  - Stock 8088, VGA (PVGA1A).
  - A **PicoMEM 2.x: NE2000**, Sound Blaster and AdLib.
- **Victory 286:** PicoMEM 1.x Ethernet.
  - This is the natural partner for 5150 #2 in a real Ethernet match.
- **Compaq Portable III:** two serial ports, a CGA-class plasma panel, and a
  modem on COM1.

So the **primary adapter is the Hercules in text mode**, which has no snow
and no colour. The **IBM CGA is the hard case**: it has snow and the worst
VRAM contention. Both have to be first-class.

---

## 3. Performance room — what a frame can afford

**One frame at 30 fps is 159,091 clk** (4,772,727 Hz ÷ 30). At 25 fps it is
190,909 clk; at 20 fps, 238,636. Unit costs come from PERFORMANCE.md Part 2:

| | |
|---|---|
| `mul r16` | 132.5 clk |
| `div r16` | 162.9 clk |
| near `call`+`ret` | 52.1 clk |
| `mov ax,[disp16]` | 21.6 clk |
| the fetch floor | 4.34 clk a byte |

### 3.1 Presenting a frame — measured

[docs/reports/TEXTMODE-WRITES-MARTYPC-2026-11-12.md](../reports/TEXTMODE-WRITES-MARTYPC-2026-11-12.md)
has the full table:

| present | clk | share of a 30 fps frame |
|---|---|---|
| whole 80x25, char+attr, `rep movsw` (CGA / Hercules) | 72,092 / 74,641 | 45% / 47% |
| whole attribute plane, i.e. "80x50 half-block" | 96,076 | 60% |
| whole 40x25 | 36,080 | 23% |
| **600 changed cells, sparse** (67.9 clk a cell CGA, 71.3 Hercules) | ~40,700 | **26%** |
| 300 changed cells | ~20,400 | 13% |
| whole C160 (160x100x16) | ~384,000 | 241%: **not a 30 fps mode** (Pixelstein measured 6.9-7.2 fps there, SPEC.md 97.15) |
| a CGA 320x200 graphics frame: 16 KB at Set 148's ~86 clk a word in mode 4 | ~690,000 | 430% |

**This is why the answer is text mode.** Only text has a whole-frame present
that fits a 30 fps budget. Only a mostly black text frame leaves room for a
3D renderer beside it.

Caveat: MartyPC prices CGA 80-column text the same as 40-column (report,
*What this cannot say* item 1). A real IBM CGA is worse in 80-column, so
budget up to ~1.3x the CGA rows until a field run confirms them.

### 3.2 What the existing 3D games say

These are the measured rates from SPEC.md:

- **Pixelstein 3D (§97):** a DDA raycaster.
  - Default 8.5-8.8 fps, peak 14.6 fps.
  - **A column costs ~1,100-1,300 clk to set up and hit.**
  - The raycaster alone (cast 166k clk) is over a whole 30 fps frame.
- **TANK (§85):** a wireframe renderer.
  - 6-14 fps.
  - Its time goes on graphics-mode line drawing and span blits, not on
    geometry.
- **Clear Skies (§88):** filled polygons, 5.7-10.8 fps.

**Lesson:** a raycaster is the wrong tool here, because it spends per COLUMN
whatever the scene holds. A **segment renderer** spends per visible WALL, and
a small arena has few walls.

---

## 4. Rendering — "edges on black", 2.5D

### 4.1 The world (proposed)

- **An arena is a set of 2D sectors with floor and ceiling heights**, the
  Doom model.
- It is **built on the host into a BSP** by a new `tools/` converter, and
  shipped as a PART (§20.12).
- **Wall directions are restricted to axis-aligned and 45°.** That has three
  payoffs:
  - BSP split tests become compares, not multiplies.
  - Collision is cheap.
  - The edge glyphs (section 4.4) have fewer slopes to approximate.
- **"Layers"** are sectors at different floor heights:
  - a raised ring round a pit;
  - stepped tiers;
  - pillars and platforms;
  - jump pads.
- **Not possible in this model:** room-over-room, i.e. bridges you walk under.
- **Arena budget:** about 40-60 wall segments, with at most ~25 visible from
  anywhere. That figure is a design rule for the arena author, and the host
  converter can CHECK it by sampling viewpoints.

### 4.2 The camera (proposed)

- **Yaw:** 1,024 steps a turn, from mouse X.
- **Pitch:** a y-SHEAR of the horizon, from mouse Y.
  - The horizon row is offset; it is not a true rotation.
  - It costs one add per projected y.
  - It reads as "looking up and down" across about ±25-30° before verticals
    visibly fail to converge, which an 80x50 grid hides well.
  - Hitscan and projectile launch use the same shear, so the angle you aim at
    is the angle that fires.
- **Jumping:** gives the eye a z. Gravity and landing are fixed-point
  physics at a fixed step.
- **Projection:** one reciprocal per projected vertex, one `div`, then `mul`s.

### 4.3 Visibility (proposed)

The BSP is walked front to back, Doom-style, with **per-column clip
arrays**: 80 top bounds and 80 bottom bounds.

- A solid wall closes its columns.
- A step's riser narrows them.
- Sectors are walked until every column is closed or the BSP runs out.

Interiors are NOT filled. Only edges are plotted, but they are clipped by the
same arrays, so a far edge never shows through a near wall. Hidden-line
removal comes from the clip arrays, with no z-buffer.

The per-column depth of the nearest wall is kept, 80 words. Figures and
projectiles are depth-tested against it.

### 4.4 Composing the cell — walls thin, figures solid (proposed)

The frame is built in a RAM shadow of 80x25 char+attr cells, 4,000 bytes, in
two layers:

1. **Wall layer — thin line glyphs, dim.**
   - Each plotted edge chooses a glyph by its sub-cell position and slope:
     `─` and `_` for near-horizontal, `/` and `\` for diagonals, `│` for
     verticals, and corner glyphs where edges meet.
   - Distant floor-grid dots `·` are optional. They are a strong motion cue
     at a few dozen cells a frame.
   - Colour (CGA, VGA, EGA): dark grey, blue or cyan, dimmer with distance.
   - Mono (Hercules, MDA): normal intensity. The MDA font's line glyphs join
     across the 9th column, which suits this.
2. **Figure layer — solid blocks, bright.**
   - A figure is drawn at **2x2 sub-cell resolution**, so 160x50 in effect.
   - Each cell's 4-bit occupancy mask maps through a 16-entry table to the
     nearest CP437 glyph: ` ▀ ▄ ▌ ▐ █`, with the two diagonal masks
     approximated.
   - So a vertical limb can sit on a HALF column (`▌`/`▐`) and a horizontal
     one on a half row (`▀`/`▄`).
   - Colour: bright white, yellow or the player's colour, on black.
   - Mono: high intensity.
   - **A figure cell overrides a wall cell** when the figure is nearer than
     that column's wall. That is how walls never hide or blur a figure in
     front of them.

**The contrast rule** is: walls thin and dim, figures solid and bright,
projectiles a single bright glyph (`•` `*` `o`), and black everywhere else.
It holds in colour and in mono. Pick a glyph palette that leaves the
figure's glyphs (`▀▄▌▐█`) to figures alone, so the two layers cannot be
confused even on the 5151.

**The glyph table is per FONT.** The CGA 8x8 ROM font and the MDA/Hercules
9x14 one place `_`, `─` and `/` differently. Wave 0 decides the palette by
looking at both, on the glass.

**A VGA/EGA bonus.** §53.7 lets a bracket program the sequencer and graphics
controller directly, so a text-mode FONT can be loaded with custom glyphs:

- 2x4 "sextant" blocks;
- line pieces at 8 slopes;
- a crosshair.

That roughly doubles effective resolution on 5150 #2's VGA at no cost per
frame. It goes behind a `[vid_planes]` = 4 door. CGA and Hercules have ROM
fonts and keep the CP437 palette.

### 4.5 Presenting it (proposed)

- **Two shadows**, previous and current, 8 KB in all.
- Each row records the min/max column touched in EITHER frame.
- Only that interval is compared, with `repe cmpsw` in RAM, and changed runs
  are copied with `rep movsw`.
  - Wall edges and limbs run horizontally, so runs are common. A run beats
    the 67.9 clk a cell sparse figure.
- **Standing still costs ~0 writes.** That is the cost of edges on black,
  and it is why the frame rate holds.
- **Turning is the worst case:** every edge moves. That case sets the
  budget, in section 4.7.

Per adapter:

| adapter | mode | presentation |
|---|---|---|
| Hercules | FSX `TEXT80`, 1 page | delta writes. No snow. Tearing is possible but short, so start the writes after `FSXW_VSYNC` |
| VGA / EGA | `TEXT80` | page-flip between two text pages through `OSAPI_FSX_PAGE`, with **damage history per page** (CLAUDE.md's rule, from WireBall); custom font as above |
| CGA, clone or compatible | `TEXT80`, 4 pages | page flip as on VGA |
| IBM CGA, 1981 card | **snows in 80 columns** | three options, below. A menu item picks; the default is the owner's call |

The three options on an IBM CGA are:

- **(a) Accept snow.** Pixelstein's C160 does. The specks scale with changed
  cells, so a calm view is clean.
- **(b) 40x25 mode.** It has no snow, half the present cost, and half the
  geometry columns, at half the horizontal resolution.
- **(c) Write only in the non-display span.** CGA-SNOW-PLAN puts vertical
  blank at ~1.2 ms. A 262-line field with 200 displayed lines has ~3.9 ms
  with display-enable low. That would be ~85-275 sparse cells a frame, which
  is enough for a calm view and not for a fast turn. It needs a measurement
  before anyone relies on it.

### 4.6 Fluid motion inside a cell grid — the honest limit

At 80x25 a figure crossing the screen moves in half-column steps (4 px).
Vertical motion moves in half-row steps (4 px on CGA, 7 on Hercules).

- **Smoothness comes from rate, not resolution.** 30 updates a second of
  4-pixel steps reads as motion. 8 updates of 1-pixel steps reads as
  stutter.
- **The sim runs at a fixed step** (proposed: 30 Hz) and **keeps fractional
  positions**. It converts to cells only when drawing (WireBall's rule), so
  motion never aliases to the frame rate.

### 4.7 The predicted frame

This is arithmetic and not a measurement. Wave 0 measures it.

| stage | 1v1 duel, walking | worst: fast turn, 4 figures, 6 projectiles |
|---|---|---|
| BSP walk and cull (axis-aligned splits) | 1.5k | 2k |
| rotate ~24 endpoints (4 `mul` each) | 15k | 18k |
| reciprocal plus screen x and up to 4 heights per endpoint | 20k | 24k |
| near-plane clipping | 2k | 4k |
| column clip walk (~200 column-steps) | 12k | 15k |
| edge plotting into the shadow (~400 cells) | 18k | 22k |
| figures (about 4k each, section 5) | 8k | 16k |
| projectiles, HUD | 3k | 6k |
| diff and present (section 4.5) | 45k | 70k |
| sim, collision, input, net, AI | 15k | 25k |
| interrupts and kernel (tick, mouse at 40 Hz) | 5k | 5k |
| **total** | **~145k: ~33 fps** | **~207k: ~23 fps** |

**What this adds up to:**

- **~30 fps for a duel looks attainable** on Hercules and VGA.
- On a real IBM CGA in 80 columns it is marginal.
- A busy scene drops into the low 20s. The fixed-step sim keeps that
  smooth, and the arena budget in section 4.1 is the lever that holds the
  rate.

---

## 5. Characters and animation (proposed)

- **Skeleton.** A stick figure has ~11 joints: head, neck, pelvis, two each
  of elbow, hand, knee and foot.
- **Animations:**

| animation | keyframes |
|---|---|
| idle | 2 |
| run | 6 |
| strafe | 4 |
| jump and land | 3 |
| shoot | 2 |
| flinch, front | 2 |
| flinch, back | 2 |
| die, falling backward | 6 |
| die, crumpling | 6 |
| a body on the floor | 1 |

- **Built on the host into 2D tables.** Joints are pre-projected for **16
  view facings** at unit scale: about 40 frames × 16 facings × 11 joints × 2
  bytes, roughly 14 KB, which is a PART.
- **On the guest, per figure:**
  - one reciprocal for its distance;
  - an 8-bit scale of 22 values (`mul r8`, ~70 clk);
  - a lerp between two keyframes for in-between frames (shifts and adds);
  - ~10 limb lines plotted into the figure layer.
  - That totals **about 4k clk a figure** (predicted).
- **Facing.** The figure's facing relative to the viewer picks the table.
  Weak perspective (one scale for the whole body) is invisible at this size.
- **Hits.**
  - The figure flashes for 2 frames: bright red on CGA, reverse video on
    mono.
  - A flinch keyframe is chosen by the side the hit came from.
  - The crosshair shows a hit marker.
- **Death.**
  - The fall direction follows the killing shot.
  - The body stays on the floor until respawn, which helps the read of
    "where the fight was".
- **Muzzle flash.** One bright cell at the hand for 1 frame. It is also a
  cue to where an off-centre shooter is.
- **Size range.** At 80x50 half-rows, a standing figure is ~40 half-rows tall
  at 2 m and ~5 at 16 m. Beyond ~20 m it is drawn as a 2-cell "marker" glyph
  pair, so a distant opponent is never sub-pixel.

---

## 6. Weapons and projectiles (proposed)

| weapon | kind | what makes it interesting here |
|---|---|---|
| **Pistol** | hitscan | the baseline. Its ray uses the same BSP as rendering |
| **Grenade launcher** | **arcing**: ballistic, bounces, fuse | it makes jumping and the pitch shear matter. Splash damage. It also needs a trail of `·` dots for 3 frames |
| **Plasma** | slow straight bolt, dodgeable | you see it coming at 30 fps, which a hitscan duel never gives |
| **Rocket** | fast bolt, splash | **rocket-jumping** follows for free from the jump physics |
| **Rail** | hitscan with a trail drawn for 3 frames | wireframe makes a line through space look superb |

**Cost:**

- A projectile is one transform, one projection and one glyph: ~600-800 clk.
- On the network a projectile is **a spawn event**: origin, velocity and
  tick. Flight is deterministic integer physics, so both machines fly it
  identically.

Pickups (health, armour, ammunition) are a cheap addition, and give the
computer opponent goals other than "chase".

---

## 7. Input — the one OS gap

Facts (SPEC.md 9, 53.1, 96.10.2, 97.11):

- In a bracket a package reads `OSAPI_MOUSE`. It gets **absolute
  coordinates, clamped to the desktop**.
- `mou_apply` keeps **no accumulator**, so motion against an edge is lost.
- There is **no relative-mouse slot**. `OSAPI_MOUSE_REL` is named as "not
  taken" in §97.11.
- There is no warp call. Pixelstein steers by "offset from centre", which is
  not modern aiming.
- The serial mouse reports ~40 times a second (1200 baud, 3-byte packets),
  which suits 30 fps.

The two ways to fix it:

- **A. Recommended — a kernel mickey accumulator plus a cell.**
  - `mou_apply` adds raw dx/dy into two words before clamping.
  - A new API cell (`OSAPI_MOUSE_REL`) reads and clears them.
  - DOS-EXEC-PLAN prices it at **~10 resident bytes** plus the cell, on
    every kernel.
  - **INT 33h's mickey counters (§96.10.2) want the same accumulator.**
    Spending these bytes buys two features, not one.
  - Adding a cell at the end is the non-bump form of §20.2.0.1's lock update.
  - SPEC.md goes first.
- **B. No kernel bytes — the package takes the UART.**
  - Mask IRQ4.
  - Poll COM1 in an `FSXF_RATE` hook (582 Hz against a byte every 8.3 ms at
    1200 baud).
  - Decode the Microsoft protocol itself, as WireBall's `wblink.inc` does
    for its link.
  - It works, but:
    - it dies on kern_small (no rate hook);
    - it ignores a PS/2 mouse;
    - it duplicates the kernel's decoder.

**Keys:** `OSAPI_KEY_DOWN` (a 128-bit held map, SPEC.md 9.7) serves WASD,
jump and crouch with any number held. That is Pixelstein's and WireBall's
pattern. Drain int 16h for Esc and F-keys.

**Keyboard-only aiming** must exist anyway: 5150 #1 cannot have a mouse and
a serial link at once. Arrows turn and PgUp/PgDn pitch, with acceleration so
turning is fast and fine aiming still works.

---

## 8. Multiplayer

### 8.1 The model (proposed): owner authority, not lockstep

Each machine simulates **its own player locally with zero input latency**.
It sends snapshots at 10-15 Hz:

- position (6 bytes)
- yaw and pitch (2)
- animation state and frame (1)
- health and armour (1)
- sequence (1)
- events (0 or more)

That is ~12-16 bytes before framing. The remote player is interpolated
between snapshots.

**Hits are judged by the SHOOTER.** It sends `HIT(victim, damage, dir)`, so
the target you saw is the target you hit. This is WireBall's
ownership-handoff spirit carried into an FPS. Projectiles are spawn events,
and splash damage is judged by the victim's machine.

**Why not lockstep:** lockstep is Doom's model. At 2400 baud it adds 2-3
ticks of input delay to your own movement, which is exactly what mouse aim
cannot tolerate.

### 8.2 Ethernet (proposed: raw broadcast frames)

- **No package can reach UDP.** The package verbs are TCP plus
  `NETV_RAW`/`RAWTX`/`RAWRX` (SPEC.md 72.22).
- **TCP is wrong for a shooter.** A lost segment stalls every later snapshot
  behind it.
- **The route is a RAW claim with a private EtherType:**
  - broadcast `HELLO` frames for discovery and lobby;
  - unicast snapshots to each peer's MAC;
  - 2-4 players.
- The receive filter is own-MAC plus broadcast (§72.8), which is exactly
  this.
- **Costs and constraints** (§72.2, 72.18, 72.22):
  - A raw claim is **exclusive and stops `eth_pump`**. DHCP and TCP stop
    while a match runs, which is acceptable during a match.
  - The NIC is **polled, not interrupt-driven**: about a 10-frame ring,
    drained only inside verbs.
  - A verb costs ~1-1.6 ms on a 5150, so 2-3 verbs a frame is ~10-15% of a
    30 fps frame. Polling every frame keeps the ring from overflowing with 3
    peers at 15 Hz.
  - Calls must come from the foreground, never from a rate hook.
- **A gap to settle in SPEC first:** §53.7's list of legal calls does not
  name `OSAPI_DRV_CALL`. `FSXL_DRV` and DOS's packet driver imply it is
  legal, and the game should not rest on an implication.
- **Cards:** NE1000 (8-bit ISA, so it fits an XT) and NE2000, including the
  PicoMEM's.
- **Where it can be tested:**
  - QEMU (closed-list entry 5);
  - 86Box (`vm/pc5150` has an NE1000, `xt-wire`);
  - **not MartyPC**, which has no NIC.
  - On real hardware: 5150 #2 against the Victory 286.

### 8.3 Serial (plausible, two players)

- **Link:** the §115 desktop lease, opened before the bracket. Read and Write
  are legal inside the bracket, and the kernel's ISR feeds 255-byte rings.
- **2400 baud.** WireFleet measured ~9% byte loss at 9600 between two XTs
  (§114.3). That gives 240 bytes/s each way: ~15-byte snapshots at 10-12 Hz
  plus events, so it fits.
- Framing and checksum: WireBall's 7Eh/7Dh format (§109.2) or WireFleet's
  CRC-16 frame, reused as SOURCE.
- **Port conflict:** the lease refuses the mouse's port. **5150 #1 has one
  port**, so a serial match there is keyboard-aimed. The Compaq has two.
- **Testing:** two QEMUs on a socket chardev (`tests/wireball.py` is the
  pattern), or two 86Box XTs on a FIFO (`tools/wireball-pair.py`). **MartyPC
  cannot link two instances.**

### 8.4 Not viable as it stands

- **NET.DRV's LapLink cable (§62)** is os8088-master to a DOS slave only,
  CPU-polled, at 3.7 KB/s.
- An os8088-to-os8088 parallel link would be NEW work. **It is worth naming
  anyway: it is the one cable 5150 #1 can use without giving up its mouse**
  (its LPT is on the Hercules card). That makes it a candidate for a later
  wave if the owner wants iron-against-iron on #1.

---

## 9. The computer opponent (proposed)

- **It is a "virtual remote player".** It produces the same input the net
  code consumes, so bot matches exercise the multiplayer path, and a 1v1
  against a bot needs no second machine.
- **Navigation** uses a waypoint graph built on the host per arena, the same
  converter as the BSP. It covers jump links and jump-pad links.
- **States:**

| state | behaviour |
|---|---|
| roam | go to a pickup |
| hunt | head to the last known position |
| engage | strafe, keep distance, pick a weapon by range |
| retreat | low health |

- **Line of sight** uses Pixelstein's `CheckLine` walk (§97), or a ray
  through the BSP.
- **Aim** uses Tank's cross and dot steering (`tk_tankai`), plus a **reaction
  delay and an aim error per difficulty**. Grenades lead by solving a fixed
  table of arcs, not by trigonometry at run time.
- **Cost:** ~2-5k clk a bot a tick (predicted). Up to 3 bots fit beside the
  renderer, with the frame rate falling as the section 4.7 table shows.

---

## 10. Sound

5150 #1 has **no sound card**. PC-speaker PCM (`OSAPI_FSX_SPK`) costs ~48%
of the machine at 5.5 kHz (§34.11.4), so it is out.

Use **`OSAPI_SND_TONE` effects**, as Pixelstein does: shot, hit, death, jump,
pickup. An opponent's footsteps are clicks whose rate follows their speed,
which is a positional cue a speaker can give.

On machines with a Sound Blaster or AdLib, SOUND.DRV's FM can play richer
effects, behind the usual refusal.

---

## 11. Kernels and adapters

| | |
|---|---|
| **kern_big** | the primary target. Every feature is designed here |
| **kern_mega** | **a shipped kernel, so the design includes it** (CLAUDE.md). In a bracket a claim is a selector: VRAM and the PARTS come through `OSAPI_SEG`, or the whole bracket goes `FSXF_REAL` (`apps/os88real.inc`). Network and serial behave the same. Its rows sit beside kern_big's |
| **kern_small** | **no `FSXF_RATE`, no NIC.** A reduced build is possible — bots or serial, keyboard aim, with a fixed step taken off the tick at 18.2 Hz (WireBall's text-court fallback is the precedent). Otherwise it refuses cleanly. The owner decides which |
| adapters | `TEXT80` on Hercules, CGA, EGA and VGA through one renderer and **per-font glyph tables**. `TEXT40` on CGA is the snow-free option |

Memory: code ~20-30 KB, the animation tables ~14 KB, arenas 4-8 KB each, and
shadows 8 KB. The code fits one segment, and the arenas and animations are
PARTS. The region must follow §66.6.1.1, `OS88_REGION_MOVABLE`.

---

## 12. How it would be verified

- **Renderer and frame rate:** MartyPC on `os8088_5150_cga_gla`,
  `_herc_gla` and `os8088_xt_vga`.
  - Guest cycles per frame.
  - **`m.flicker()` and `m.pace()`**, so smoothness is MEASURED in frames,
    not judged by eye (PERFORMANCE.md Parts 3.1-3.2).
- **Real-CGA text contention and snow:** one field run on 5150 #1's CGA. The
  report's caveat 1 is the question to ask.
- **Ethernet:** two QEMUs on a socket netdev, then 86Box `pc5150`, then
  5150 #2 against the Victory 286.
- **Serial:** two QEMUs on a socket chardev, and 86Box XT pairs.
- **The AI:** a bot-against-bot soak row with seeded RNG. Deterministic, so
  a replay is bit-exact.

---

## 13. Other suggestions

1. **Two players on ONE 5150 #1, one on each monitor.**
   - The owner's machine has a Hercules and a CGA on separate screens. Render
     P1's view to B000 and P2's to B800, at half the rate each (~15 fps).
   - Controls: the mouse plus WASD for one player, the keypad for the other.
   - No cable, and unique to that machine.
   - **Open question:** whether an FSX bracket can own BOTH cards. §53 is
     written for one display, and §39.11's extended desktop is where two-card
     work already lives.
2. **Deterministic replay and kill-cam.** Fixed-step integer sim plus
   recorded inputs replays exactly. A 3-second "kill-cam" from the killer's
   view is cheap, and so are demo files.
3. **A distance cue from the edge colour.** Near edges are bright cyan, far
   ones dark blue. On mono, near is bright and far is normal. Depth reads
   instantly in a wireframe.
4. **A floor dot-grid** under arenas with open floors. It gives strong
   parallax for a few dozen cells.
5. **Modes:**
   - duel;
   - free-for-all with bots;
   - "last stand" (waves of bots, solo);
   - a one-flag capture.
6. **Arena features that exercise the engine's strengths:**
   - jump pads (arcs);
   - teleporters (a cut, which costs nothing to render);
   - a central pit with tiers ("layers").
7. **A radar strip** in the HUD row: opponents as single glyphs by bearing.
   It is cheap, and it compensates for the narrow field of view a text grid
   forces.
8. **A host-side reference renderer** (Python) that runs the arena file and
   produces the expected cell grid for a camera. Rows then compare the
   guest's shadow against it byte for byte, which is `weavesim.py`'s role
   for WEAVE.

---

## 14. Risks and open questions for the owner

1. **Real IBM CGA in 80 columns.** Contention may be ~1.3x MartyPC's, and
   there is snow. Snow, 40-column mode or vertical-blank writes: which is the
   default?
2. **The relative-mouse cell.** It costs ~10 resident bytes plus a cell on
   every kernel, and INT 33h wants it too. Approve, or should the package
   borrow the UART?
3. **Ethernet by raw frames.** A match stops TCP and DHCP while it runs. Is
   that acceptable? And §53.7 should name `OSAPI_DRV_CALL` explicitly.
4. **kern_small:** a reduced build, or a clean refusal?
5. **The glyph palette.** It is decided by looking at the CGA 8x8 and MDA
   9x14 fonts on the glass in Wave 0. The table in section 4.4 is a starting
   point.
6. **The two-monitor local mode** needs a ruling on whether a bracket may
   own both cards.

## 15. A first cut of the waves (draft — to be rewritten as stories when approved)

- **Wave 0 — the renderer spike. This decides everything else.**
  - The host BSP converter and one arena.
  - The edge-on-black renderer plus the presenter in a bare `TEXT80` bracket.
  - The camera driven from keys.
  - Measure cycles a frame on CGA, Hercules and VGA in MartyPC, plus
    `flicker` and `pace`.
  - Exit criterion: ≥30 fps walking and ≥20 fps turning on Hercules, or a
    revised plan.
- **Wave 1:** the relative-mouse cell (SPEC first), yaw and pitch shear,
  jumping, and collision with steps and tiers.
- **Wave 2:** figures and animation tables, the pistol, hits and deaths, the
  HUD.
- **Wave 3:** the computer opponent, navigation and waypoints, and a bot
  soak row.
- **Wave 4:** the serial link, with the owner-authority model.
- **Wave 5:** the Ethernet raw link, the lobby, and 2-4 players.
- **Wave 6:** arcing and slow weapons, pickups, sound, more arenas, the CGA
  snow option and kern_mega rows.
- **Wave 7:** the field run on 5150 #1, the CGA questions, and the
  PERFORMANCE.md set.

---

## 16. Wave 0 — what was built and what it measured

**Built:** `apps/wirearena/` (`WARENA.O88`, `make wirearenadisk`). It is an
on-demand `instrument` in `apps/RETIRED.txt` until it is a game. The package
has these parts:

- `wirearena.asm`: the shell, the loop, input and the 30 Hz sim.
- `wrender.inc`: the renderer.
- `tools/arenagen.py`: builds the sine table, the arena, the patrols, and
  the stick-figure keyframes pre-projected for 16 facings.

What the prototype contains:

- A 32 m room with nine blocks.
- Three dummies running patrols. Each has run, flinch and death animations,
  blended in quarter steps.
- The pistol: hitscan through the crosshair, three hits to drop a dummy, a
  hit flash, and respawn after three seconds.
- Mouse look through `OSAPI_MOUSE_REL`, WASD, jumping, and pitch by y-shear.
- **Tab** swaps between 80 and 40 columns, live. **V** presents after
  vertical retrace. **B** runs the BENCH.
- A HUD meter showing fps, frame ms, render ms, present ms and video writes
  a frame.

**The bench** (B) is 64 frames from (1024, 700), turning 1/64 of a circle
each frame, with the dummies frozen at their path starts. It is the same work
on every build, in either width. These figures come from MartyPC on
`os8088_5150_cga`, `_herc` and `os8088_xt_vga`. The three agree to the
millisecond, because MartyPC charges their text memory alike (see the report's
caveat about a real IBM CGA):

| | render | present | frame | fps | video writes a frame |
|---|---|---|---|---|---|
| 80 columns | 69.4 ms | 13.4 ms | 76.7 ms | **13.0** | 193 |
| 40 columns | 52.0 ms | 7.8 ms | 55.3 ms | **18.0** | 113 |

These are against section 4.7's prediction of ~145k clk (~30 ms) for a
duel. **The first renderer costs ~2.5x the prediction at 80 columns.**

The sampling profile of a busy view (`flat_ip` bucketed by listing labels)
shows where the time goes:

| part | share |
|---|---|
| wall edges | ~24% |
| per-column depth raster | ~16% |
| figures (limb plotting, keyframe blends) | ~19% |
| geometry (transform, clip, project) | ~22% |
| present | ~10% |

The first version was at 7.4 fps before two rounds of tightening. Most of
that loss was a call chain four levels deep per plotted cell.

**What it looks like** is on the glass in screenshots taken during the work:

- **Walls** read as a dashed wireframe. A shallow slope becomes a staircase
  of `─` and `_` at half-row steps; box corners are `│`. They dim with
  distance: bright cyan, then cyan, then blue on colour; normal intensity on
  mono, where the MDA font's line glyphs join into solid lines.
- **The figures**, close up, read unmistakably as running stick men with the
  pistol arm out. At mid range they are a small cluster of blocks. 80 columns
  keeps limb detail further out than 40 does.
- **Snow** on a real IBM CGA at 80 columns is not measured. MartyPC does not
  show it. 86Box reportedly does (the owner); the owner's own CGA is the real
  test.

**The design levers for 30 fps**, in order of expected gain:

1. **Front-to-back "solid segment" occlusion instead of the per-column
   depth buffer.** The arena's walls are full-height, so a column closed once
   is closed. That removes the raster's per-column compares and stores. It
   also lets the edge pass step each top and bottom line incrementally across
   its visible span, rather than reloading and rounding per column.
   Front-to-back order comes from a host-built 2D BSP (section 4.1).
2. **Shared products for axis-aligned boxes.** A box's corners share x or y,
   so 8 multiplies replace 16. A reciprocal table can stand in for the
   per-vertex divides.
3. **Figures:** clip and depth-test per LIMB, not per sub-pixel, and plot
   inline.
4. **Present:** walk the two lists in one merged pass.

The decision the owner asked to make — **40 or 80** — now has both on one
disk, with the meter, switchable live.

### 16.1 Optimization round 1 — measured

The bench is unchanged: 64 frames, a fixed spin, MartyPC `os8088_5150_cga`.

| | render | present | fps | before |
|---|---|---|---|---|
| 80 columns | 64.0 ms | 13.4 ms | **13.7** | 13.0 |
| 40 columns | 50.1 ms | 7.6 ms | **18.4** | 18.0 |

**What was done**, each checked on the glass:

- **The renderer is now front to back over a box-level BSP.** Boxes are
  convex, so the tree orders only the nine boxes: 17 nodes, every split a
  clean axis-aligned line, refused at build time otherwise. The room comes
  last.
  - A box's faces are chosen by four compares.
  - A column a nearer wall drew is closed, and the walk stops once all are
    closed.
  - A wall whose reachable columns are all closed is dropped BEFORE any clip
    or divide. The reachable range is found from camera space, and an open
    column is found with one `repne scasw`.
  - Transforms are two 32-bit adds per vertex, off per-coordinate products
    made once a frame.
  - Projections are cached per vertex.
  - The left/right frustum clip is gone. Spans clamp to the screen; a guard
    band of |x| <= 8z keeps the column divide in range.
  - The per-column depth buffer and the separate edge pass are gone: a
    span draws its open columns as it steps.
  - Slope fills are tested only on spans steep enough to need them.
  - Corners are drawn after the loop. A box corner is drawn once: a face's
    start, and its end only on a silhouette.
- **The host check of the BSP order** compares the first front-facing wall
  per column against a ray-cast, over 24,000 columns from 300 viewpoints.
  It found 0 errors, and 1,112 with the walk reversed.
- **Cells are indexed by OFFSET** throughout (stamp, mask, lists, row
  tables), which removes a shift at every plot and in both present loops.
- **Figures:** sub-pixels plotted inline in the line loop. Past ~15 m a
  figure is a one-sub-column marker instead of nine limbs.

**Why it moved so little.** Two instruments explain it.

- **Counters** read off the guest: per frame 35 walls walked, 19 facing, 7
  spans set up, 79 columns opened, 27 vertices, 14 clips (before the guard
  band), and one figure of ~20 sub-pixels.
- **The listing:** an opened column ran ~260 bytes of code, and the 8088
  fetches at ~4.34 clk a byte (PERFORMANCE.md Part 2) — ~1,100 clk before
  any data moves, ~1,800 measured.

The plan's per-frame estimate (section 4.7) priced instructions at a few
clocks each; the floor is ~20. After this round the profile is FLAT: span
~29%, projection ~11%, vertices ~8%, present ~8%, figures ~9%, nothing else
over 5%. No single lever is left.

**The honest reading:**

- 30 fps at 80 columns is out of reach for this renderer on a stock 4.77 MHz
  8088.
- 40 columns is ~19 fps on the bench's worst case, a continuous fast spin
  across the busiest view. The HUD in the look-around runs read 12–16 fps
  at 40 columns, including the 30 Hz sim's ~2 ms a tick. (Wave 0's 20–24
  readings were taken while a cap bug ran the sim at a third of its rate.)
- What would still move it:
  1. A per-column path in the ~100-byte class. That means a hand-scheduled
     register loop, the accumulators out of memory, and tops and bottoms as
     8.8 values when on screen.
  2. A reciprocal table instead of the per-vertex divides.
  3. Fewer cells: for example, top edges only, or no slope fills, as a
     player option.
  4. Present merged into the span pass.

  Each is a few percent to perhaps 15%. Together they might bring 40 columns
  to the mid-20s.

### 16.2 Optimization round 2, and a sparse detail level — measured

Same bench. F is the full detail level, S the sparse one.

| | F render | F fps | S render | S fps | round 1 |
|---|---|---|---|---|---|
| 80 columns | 55.5 ms | **15.5** | 49.5 ms | **18.5** | 13.7 |
| 40 columns | 46.8 ms | **19.5** | 43.7 ms | **21.7** | 18.4 |

**The column loop is hand-tuned.** It is one NASM macro (`SPANLOOP`)
assembled four ways — top edge or not, steep-step fills or not — so no
column tests a mode. Inside it:

- The loop ends on a compare, not a counter.
- An edge's glyph comes from a half-row table.
- The distance shade is no longer chosen per column. A span is cut into at
  most three column ranges where its inverse depth crosses a threshold
  (`.bands`).
- Depth is neither stepped nor stored. A span registers its projected ends in
  a table (`wa_cov` holds the span's tag), and `wa_wallz` interpolates the
  inverse depth for the columns a figure or the trigger actually asks about
  (`wa_figcols`, `wa_colsz`).
- An opened column at full detail on a flat span is now ~120 bytes of code,
  against ~260.

After this round the loop itself is ~11% of a 40-column frame. The span
SETUP is ~18%: the occlusion scans and two divides a span.

**Tried and backed out.** Computing the per-coordinate products lazily, once
per coordinate per frame, measured SLOWER: 19.5 -> 19.0 fps. Nearly every
coordinate is used, so the stamp tests were pure cost. The note is at
`wa_products`.

**The sparse detail level (L)** draws floor lines and corner posts — no top
edges and no top slope fills. It is about 40% fewer video writes (80
columns: 149 against 240 a frame), and the posts still carry the walls'
height. The HUD shows F or S.

**Where 40 columns stands:** ~20-22 fps on the worst-case spin. The rest is
mostly fixed per frame and does not shrink with the width:

| part | share |
|---|---|
| vertex transforms, projections, products | ~22% |
| span setup | ~18% |
| figures | ~10% |
| present | ~7% |

### 16.3 The owner's first field run, and what it found

The owner ran WARENA on 5150 #1's CGA (2026-11-12):

- **40 columns:** "looks fine, as the default for CGA". It is now first in
  the Game menu.
- **The rate in play** — moving the camera, three dummies, shooting — was
  **10.4–11.7 fps**: "still too low to be playable".
- **The sparse level:** makes the room "a lot harder to read" and "doesn't
  seem to have a major impact on FPS". Its measured gain was 2 fps at 40
  columns.
- **"WASD does not seem to do anything"**, while Esc and L worked.

**WASD was not the keyboard.**

- The start position (1024, 256) was INSIDE the south stub (960..1088 x
  192..320), so every step collided and was undone. Turning and the trigger
  worked because they do not move the player.
- Wave 0's scripted walk never caught it: no shot was compared with the one
  before it.
- `tools/arenagen.py` now REFUSES a start inside a wall (and a patrol that
  runs into one). The start is (1024, 480).
- Making the start per-arena then exposed a second bug: `wa_reset` stored
  the start ANGLE into the pitch, the jump height and velocity, and the hit
  counts, which until then had relied on AX being 0. Fixed.

**The field rate was taken from inside the stub, which is no measurement of
play.** It should be re-taken.

**A second, sparser ARENA.** The menu now offers "Open arena": the same
room, only the four pillars, beside the full one. The question it answers is
how much of a frame is the scene's own complexity. Arenas are host-built
(`arenas()`), copied into working tables at launch (`wa_loadarena`); each
tree is walked where it was assembled.

A play scenario on MartyPC `os8088_5150_cga`: about 8 guest seconds of mouse
turning with the dummies running and the trigger pulled every second, read
off the HUD at the end:

| | fps in play |
|---|---|
| full arena, 40 columns | **20.1** |
| open arena, 40 columns | **24.8** |
| full arena, 80 columns | 14.5 |

These are emulator figures. The report's caveat about a real IBM CGA's
text-mode contention applies, and the field rate is the one that decides.

### 16.4 The owner on 86Box, and what followed

The owner ran 86Box (2026-11-12), and the timing there is coarser than
MartyPC's:

- **The rate:** the full arena at 40 columns ran 12–14 fps with three
  figures, the camera moving, running and shooting. The open arena ran ~2
  fps more.
- **The target:** the FULL level of detail, which will hold rooms and stairs
  on screen. The open arena is a style a level may use.
- **The look:** walls read well up close. Far away their distance "keeps
  jumping as the perspective changes", closer at the side of the view and
  pushed back at its centre.

**That has three causes.**

1. **Planar projection.** A wall's height goes with its depth ALONG the
   view, so at the edge of a 90-degree view it is 1.41x its height at the
   centre.
2. **The distance shades used that same depth**, so a wall turning to the
   centre could drop a colour band.
3. **The half-row quantum** is 15–25% of a far wall's height.

**The owner's answers, and what was built.** Each is measured on the bench
at 40 columns.

| change | how | cost |
|---|---|---|
| **Colour says what a wall IS, not how far.** Two shades never read as depth, and Hercules has none: boundary walls dark blue, items (pillars, blocks, later stairs) cyan, floor dots dark grey, figures white; mono keeps every wall normal intensity and the figures bright | a per-box colour index in each arena's data (`wa_<tag>_bcol`), set per box in the walk | the per-span band split is gone (cause 2 with it), so it costs nothing |
| **F: the field of view**, 90 -> 75 -> 60 degrees. A zoom, the vertical scales following, so proportions hold. The edge stretch is 1.41x / 1.30x / 1.15x | `wa_setfov` | none: it is a constant |
| **H: held far edges.** An edge keeps last frame's half-row until the true position is a quarter half-row past the boundary, per column. Against cause 3's flicker on slow turns | `EDGE`; `SPANLOOP` is assembled eight ways now | 20.1 -> 19.3 fps |
| **G: a floor grid**, a dark dot every 2 m within ~6 m, behind walls and under figures | one divide and three multiplies a dot | 20.1 -> 15.9 fps |

Each toggle shows at the HUD's tail: view (9/7/6), H, F/S, G. Rejected: a
true-distance (cylindrical) projection — it bends straight walls and is
slower.
