# GFX-EMBEDDABLE-PLAN.md — the graphics library a package embeds

**Status: RESEARCH. Nothing built.** Sizes and the one performance claim that
matters are measured on this tree and reconciled (§10); everything costed as a
*wave* is an estimate against a measured comparable and says so.

`gfx_embeddable` is an app-side graphics library in the shape of
`apps/os88ui.inc` — a `%include` a package opts into capability by capability.
**Line is its first customer and is not meant to be its only one**, so the
layering in §4 is the part to get right; §8's waves are only the order the line
family goes in.

---

## 0. The premise, and the two things that make it more than a size argument

The owner's framing, which this document is an answer to:

> duplicate code only used by apps that take up most of the system resources,
> and thus are unlikely to run many at a time, instead of permanently spending
> kernel RAM on them.

Two facts turn that from a size trade into a straight win:

1. **An app-side rasteriser is measured FASTER.** PERFORMANCE.md priced a
   candidate 1bpp mask rasteriser at **24.6 µs a pixel** against `gfx_line`'s
   **31.6** with the arrival removed — **1.29×** — because what it drops is
   *"everything `gfx_line` does that a caller compositing its own figure does
   not need: clipping, the ink, the dither table, the per-row `gfx_rowbase`."*
   The library is not a worse rasteriser. It is a better one.

2. **`kern_small` has never had `gfx_line_fast`, and a library gives it back.**
   SPEC.md 5.6.4.1's interval-folded walk is **4.9×** on a 1bpp adapter and is
   `%ifdef KERN_BIG` — *"NOT ON kern_small (5.6.4.4): it is 686 bytes of `.text`
   and that machine is short of the thing it would be spent from"*. Measured
   here at **647 bytes**. In a library that is 647 bytes of **Paint's own
   package**, and the floor machine gets a 4.9× stroke it has never had.

So the question the owner posed — *the apps would have to choose between
keeping those optimisations or gating them out* — has a third answer for at
least one app: **take an optimisation the kernel never gave it.**

---

## 1. The prize, measured

Every figure from `[map all]` on this tree, per-symbol sizes reconciled against
the section lengths (§10).

| | `.text` | `.bss` | total |
|---|---:|---:|---:|
| `kern_small` | **1,377** | 69 | **1,446** |
| `kern_big` | **2,520** | 80 | **2,600** |

3.6% of `kern_small`'s `.text` and 4.9% of `kern_big`'s. The contiguous block
`gfx_linit` → `gfx_blit4` is 1,368 / 2,511; the remaining 9 bytes are
`gfx_lmtab` (8) and `gfx_lmsk` (1), which sit elsewhere in `.text`.

### 1.1 Where the difference between the builds is — the owner's prediction, confirmed

**`kern_big` carries 1,143 bytes of `.text` that `kern_small` does not**, and
every byte of it is a speed optimisation:

| symbol | small | big | what it is |
|---|---:|---:|---|
| `gfx_line_fast` | 0 | **647** | SPEC.md 5.6.4.1, the 4.9× interval walk — **1bpp**, and absent from the 1bpp-only kernel |
| `gfx_line_runs` | 0 | 157 | 4bpp/VGA major-axis run coalescing |
| `gfx_lf_wide3` | 0 | 70 | 5.6.6's three-column dilated walk |
| `gfx_line_flush` | 0 | 66 | `gfx_line_runs`' rect emitter |
| `gfx_lstep_slow` | 0 | 30 | the walk's planar per-pixel arm |
| `gfx_ls_one` | 52 | 126 | +74: display translation round the walk |
| `gfx_line` | 316 | 365 | +49: the planar dispatch |
| `gfx_line_raw` | 2 | 26 | +24 |
| `gfx_ls_box` | 173 | 183 | +10 |
| `gfx_ls_lx` / `gfx_ls_ly` | 1 / 1 | 9 / 9 | +16 |

The rest — `gfx_line_mono` 286, `gfx_lstep_mono` 212, `gfx_ls_box` 173,
`gfx_ls_adv` 71, `gfx_linit` 64, `gfx_lstepv` 59, `gfx_lm_pre` 55,
`gfx_lstep` 37, `gfx_ls_addr` 29, `gfx_ls_ink` 10, `gfx_lmtab` 8 — is
identical on both.

### 1.2 The finding nobody was looking for: the kernel carries TWO 1bpp walkers

`gfx_line_mono` (**286**) and `gfx_lstep_mono` (**212**) are the same
capability written twice — *"draw the next pixel of a Bresenham on a 1bpp
adapter"* — because the line and the resumable walk were built at different
times and share only `gfx_ls_addr` (29). **498 bytes for one capability.**

That is exactly the shape §4's rule fixes, and it is the reason the library's
total should come out *below* the 1,377 it replaces rather than equal to it.
It is also why the owner's rule is the right one and not merely tidy: a lattice
where `WALK` is built **on** `LINE` cannot express this duplication.

---

## 2. What it was blocked on, and why it no longer is

### 2.1 A windowed package has no framebuffer, and never has had

The only published framebuffer address on the machine is `FSI_SEG` in the fsx
info block, and SPEC.md 53.7 makes every kernel drawing slot illegal the moment
`fsx_mode` returns — the two are **mutually exclusive by design**.
`apps/tank/tkraster.inc` is what that permission looks like when it is granted,
and Tank pays for it by owning the whole screen. Nothing in this plan asks for
that to change.

So an app-side rasteriser must hand its result back through a slot, and the
plan lives or dies on which slot.

### 2.2 `gfx_spans` is not the one

`stc`/`ret` with no body on `kern_small`, and on `kern_big` it refuses outright
whenever a clip region is armed or a second display exists — *"both re-cut the
run, and the caller's `gfx_fill` loop does it right"*. **Every windowed package
arms a clip region before it draws.** Rule it out and stop re-deriving it.

### 2.3 `gfx_blit1` IS the one, and it is already legal

Read `gfx_blit1_x` (`kernel/vga12.inc:5972`) rather than assuming from
`gfx_spans`. It does all three things a windowed commit must:

- **`cur_unlazy`** — *"this may write any pixel on the screen, so the deferred
  hide is owed (SPEC.md 7.1.4)"*, taken above everything it could stale;
- **the display**, resolved *"BEFORE anything meets a screen extent (39.14.8)"*,
  with `.percol` for a band that straddles;
- **the clip region** — `wm_clip_rows` for the row range, `.percol` when
  `wm_clip_rows` refuses a part-width row.

Its only argument refusal is an **x off the byte grid**, *"a caller error, not a
shape to clip"*; a width off the grid has been honoured since 5.4.2.5.

### 2.4 …and `kern_small` is getting it anyway

`OSAPI_GFX_BLIT1` has **14 callers**: `arkanoid artful c64 cc os88type paccman
pacman paint skies telnet thewire weave wire word`. Filtering by `SMALLOMIT`,
**nine of them ship on the small disks** — arkanoid, artful, cc, os88type,
pacman, paint, weave, word, and any C package through the thunk — and on that
build every one takes a fallback, because `gfx_blit1` there is

```
gfx_blit1:            stc               ; kern_small carries the SLOT and not
                      ret               ; the body ... The body was measured on
                                        ; this build and refused (SPEC.md 5.4.2.5)
```

**So the +419 bytes that §12.4 of the cut plan charged against this row is not
this row's cost.** It is a decision already taken on its own merits, and this
plan should be priced with `gfx_blit1` present on both builds.

---

## 3. The commit is a FOUR-WAY choice, and all four are published and measured

The first draft of this section said *"the band commit is opaque, and that is
the sharp edge of the plan."* **Both halves of that were wrong.** There is a
transparent commit; and for the figures these programs draw it is the *worst*
of the four options, not the escape hatch. What follows is the whole published
surface with a measured price on each row.

| mode | slot | transparent? | priced per | measured, 5150 |
|---|---|:-:|---|---|
| **opaque band** | `OSAPI_GFX_BLIT1` | no | band **AREA** | **0.40–0.77 µs/px** — `BLIT1 632×8` 2.02 ms, `BLIT1 224×8 1bpp` 1.21 ms, `GFX_BLIT1 128×128` 12.59 ms |
| **masked band** | `OSAPI_ICON_DRAW` | **YES** | band **AREA** | **~39–47 µs/px** — a 12×12 is **6.7 ms** and a 16×16 **~10 ms**, both Hercules |
| **whole line** | `OSAPI_GFX_LINE` | yes | **INK** pixel | **37.1 µs/px**, of which ~714 µs is fixed |
| **one pixel** | `OSAPI_GFX_PIXEL` | yes | **INK** pixel | **640.87 µs** |

**The two units are the point.** A band is priced by its AREA whatever it
carries; a line and a pixel by the INK they lay down. So the mode is chosen by
the figure's DENSITY, and that is a per-app fact rather than a per-library one.

Worked, on the 127×32 line PERFORMANCE.md already benches — 127 ink pixels in a
4,064-pixel band:

| | |
|---|---:|
| opaque band (`GFX_BLIT1`) | **~3.1 ms** |
| direct (`GFX_LINE`) | **4.7 ms** |
| masked band (`ICON_DRAW`) | **~158 ms** |

**For a sparse figure the transparent band is 34× worse than the thing it was
supposed to rescue.** It is not a general-purpose escape; it is what it was
built for — a *small dense* glyph, a 12×12 control.

### 3.1 …and the published masked band is capped, by a BUFFER rather than by the renderer

Worth writing down because the code and the SDK comment disagree, and the
reason matters if anyone wants to lift it:

- **`icon_draw`, the kernel-internal entry, has no cap at all.** It reads
  `wwords` and `rows` as plain bytes into `[ico_ww]`/`[ico_h]`, and every
  stride, clip and row advance is computed from them. The 1bpp pass is a real
  masked read-modify-write — `ico_bbop` selects `or` (white) or `and-not`
  (black) per byte.
- **`icon_draw_x`, the API entry, refuses everything but 16×16.**
  `cmp al, ICO_STAGE_WW / jne .refuse` and `cmp ah, ICO_STAGE_H / ja .refuse`,
  because the record is copied into a **66-byte staging buffer**
  (`ICO_STAGE_SZ = 2 + 16 × 4`) — the package's record lives in the package's
  segment and ES is the kernel's.

Lifting it is therefore not a renderer change. Two shapes, neither costed:
widen the stage (a 64×64 one is **1,026 bytes of `.bss`**, on the build with
least to give), or render straight out of the caller's segment with no stage
at all — which is what `gfx_blit1` already does. **Neither is worth doing for
this plan**, because §3's table says a general masked band is the wrong answer
for the figures in question anyway.

### 3.2 The fourth option — and it may retire the walker outright

This is the answer to *"is keeping the walker inside the app on the table?"*
**Yes, and it does not need a band at all.**

`gfx_lstep` exists because of SPEC.md 5.6.7: a trail is drawn a couple of
pixels a frame and erased as one long line, and *"Bresenham over the whole line
does not visit the union of the per-frame segments"*. **That argument is about
the KERNEL holding the state.** Once the app holds it — which is the whole
proposal — the app knows *this frame's* segment endpoints, and

```
    OSAPI_GFX_LINE(p_prev, p_now)      ; this frame's segment, in ink
    ...later...
    OSAPI_GFX_LINE(p_prev, p_now)      ; the identical segment, in paper
```

is **exact**: `gfx_line`'s pixel set is a pure function of the endpoint pair
(SPEC.md 5.6.2), so an erase replaying the same segments replays the same
pixels. No band, no shadow, no opacity question, and the union that 5.6.7 says
whole-line Bresenham misses is drawn segment by segment, which is precisely
what it is.

Two costs to name: adjacent segments share an endpoint, so **one pixel a
segment is written twice** (PERFORMANCE.md rule 2, in miniature — idempotent
in both directions, but say it out loud); and the arithmetic below is
ARITHMETIC.

#### MEASURED — PERFORMANCE.md Set 132, Hercules 5150

This was arithmetic when it was written and it has since been benched
(`tests/gfxbench`, six rows `kwalk n=N x8` / `aline n=N x8`). **The prediction
was directionally right and its crossover was wrong:**

| pixels a block a frame | kernel `gfx_lstepv` | app walker + `GFX_LINE` a segment | |
|---:|---:|---:|---|
| 1 | **5,243.9 µs** | 7,884.8 | kernel **1.50×** |
| 3 | **7,703.8** | 10,496.9 | kernel **1.36×** |
| 10 | 16,271.5 | **9,179.6** | app **1.77×** |

**The two sides have different shapes, and that is the finding.** The kernel
walk is LINEAR and agrees with SPEC.md 5.6.8 to within 3% — a fitted intercept
of 4,013 µs for eight blocks against 5.6.8's 480×8, and 154 µs a pixel a block
against its ~175. The `gfx_line` side is **FLAT**: 986 µs a call at two pixels
and 1,147 at eleven, because a short line is its own fixed part and little
else.

So the crossover is **about FOUR pixels a block a frame** — (9,180 − 4,013) /
1,230 = 4.2 — and not the two this section predicted. The error was the
`gfx_line` fixed part: 714 µs, taken from the intercept of a 127-pixel row,
where a SHORT line on this geometry costs **~1,150**.

**What it decides, and it is not what was hoped:**

- **Missile's drain wins app-side, decisively.** `MC_DRNBUD` is 64 pixels a
  frame over ~4 blocks — sixteen a block — modelling at **23.7 ms** for the
  kernel walk against a measured **9.2 ms**. **2.6×.**
- **An ordinary trail loses.** One to three pixels a block a frame is what
  Cyclone's warp and Missile's own missiles do, and the kernel walk is
  **1.36–1.50×** ahead there.

**And `gfx_line` is not the only thing an app-side walker can plot through.**
The same run reads **`GFX_PIXEL` at 539.52 µs**, and a walker that owns its
state knows every pixel's coordinates:

| pixels a block a frame | `gfx_lstepv` x8 | 8 × `GFX_PIXEL` | 8 × `GFX_LINE` | best |
|---:|---:|---:|---:|---|
| 1 | 5,243.9 | **4,316** | 7,884.8 | **PIXEL**, 1.21× |
| 3 | **7,703.8** | 12,948 | 10,496.9 | **walk** |
| 10 | 16,271.5 | 43,162 | **9,179.6** | **LINE**, 1.77× |

> **`gfx_lstep` is the best of the three only between about 1.3 and 4.2 pixels
> a block a frame.** Below that its per-block setup costs more than a whole
> `gfx_pixel`; above it, its 154 µs marginal pixel costs more than amortising
> one `gfx_line` across the segment.

That is what the slot's 537/641 bytes actually buy — a **window**, not a
category. Whether Cyclone's warp and Missile's missiles sit inside it is a
reading nobody has taken, and it is now the cheapest thing left to measure
(this plan's 9.1).

### 3.3 So the per-program answer, restated

| program | figure | mode |
|---|---|---|
| **Paint** | dense, own bitmap | opaque band, or `GFX_LINE` direct as today |
| **Sheet** | grid on fresh ground | opaque band |
| **Cyclone** | sparse, accumulating | **app walker + `GFX_LINE` a segment** — §3.2, no band, no shadow |
| **Missile** | sparse, over terrain | **app walker + `GFX_LINE` a segment** — and it is the one the arithmetic most favours |
| **Mines, Word, Weave** | small dense marks | opaque band, or `ICON_DRAW` where it fits 16×16 |

**No program in the tree needs a full-window shadow**, which is what the first
draft of this section thought Cyclone and Missile would have to carry.

---

## 4. The capability lattice

The rule, as set:

> wanting one capability should not drag in unused others. So walk drags in
> "how to draw a line", but "how to draw a line" does not drag in the walk.

The idiom is `apps/os88ui.inc`'s, unchanged: `%define GFXE_<CAP>` before the
`%include`, `%ifdef` blocks inside, and an implication written as a `%define`
at the top the way `OS88UI_BARONLY` already defines `OS88UI_NOBTN`.

```
    %define GFXE_WALK          ; implies GFXE_LINE
    %define GFXE_LINE_FAST     ; implies GFXE_LINE
    %include "os88gfx.inc"
```

### 4.1 The layers

| capability | implies | what it is | ~bytes |
|---|---|---|---:|
| `GFXE_BAND` | — | compose into your own 1bpp band; commit with `OSAPI_GFX_BLIT1`. **The pixel primitive lives here** — a bit-set, not a slot | ~80 |
| `GFXE_LINE` | `GFXE_BAND`¹ | Bresenham + the 1bpp per-pixel walk (`gfx_line_mono`'s body) | ~350 |
| `GFXE_LINE_FAST` | `GFXE_LINE` | SPEC.md 5.6.4.1's interval walk, **4.9×**. **Not one choice — §4.1.1** | **647**, or ~350 |
| `GFXE_WIDE` | `GFXE_LINE` | 5.6.5/5.6.6 dilation — the three-pass and the three-column mask walk | ~130 |
| `GFXE_RUNS` | `GFXE_LINE` | major-axis run coalescing, for a **4bpp** target | ~223 |
| `GFXE_WALK` | `GFXE_LINE` | resumable state: `linit`, `lstep`, replay-to-erase | ~230 |
| `GFXE_WALK_BATCH` | `GFXE_WALK` | `lstepv`'s many-walks-one-arrival | ~60 |

### 4.1.1 `GFXE_LINE_FAST` is not one choice — the menu is already measured

**[docs/plans/completed/LINE-PERF-PLAN.md](completed/LINE-PERF-PLAN.md) is
`gfx_line_fast`'s design record and its LINE-PERF-PLAN §5.2 is a gift to this plan**: it
prices three ways of making the fast walk *smaller* against exactly what each
costs in speed, on the 5150, with `tools/os88linecost.py pieces` as the
instrument. In the kernel those were rejected — a kernel cannot ask the caller
which trade it wants. **A library can**, and that is what turns the owner's
*"keep the optimisation or gate it out"* into a dial:

| sub-capability | bytes | what dropping it costs |
|---|---:|---|
| the eight octant loop bodies | 324 | dropping all of them is **no fast walk at all** — back to `GFXE_LINE` |
| four steep bodies behind one indirect jump | ~38 | **+6%** on a 32×127 line, **+24%** on a 45° one; the steep/shallow spread goes 1.18× → 1.47× |
| ink specialisation (an ink-independent plot: two RMWs a pixel) | ~148 | **+25% steep, +30% shallow, on every line** |
| the black loops | ~148 | **every erase back to 723 cyc/px — 4.8×**. Free for a package that never erases |
| `gfx_lf_wide3` (5.6.6.1's dilated steep) | 71 | `GFXE_WIDE`'s fast arm; a thin-only caller never wanted it |
| the eligibility setup | 161 | **not droppable** — LINE-PERF-PLAN §5.1 explains why the two octant blocks are mirror images that cannot share code on an 8086 |

So **Sheet, which draws grid lines in one ink and never erases**, plausibly
takes `GFXE_LINE_FAST` at ~350 bytes rather than 647. **Cyclone, whose whole
warp is a draw/erase pair**, must keep the black loops. This is the per-package
conversation the owner asked for, and it is already priced.

LINE-PERF-PLAN §4.5 also records the one thing measured and **refused**, so
nobody costs it again: *accumulating a framebuffer byte* — one RMW per byte
rather than per pixel — is worth **10%**, not the 8× the store count suggests,
because at 127×32 the row changes every fourth pixel and the byte must be spent
then anyway.

¹ `GFXE_LINE` implies `GFXE_BAND` only in compose mode. A caller that wants a
line drawn **directly** takes `GFXE_LINE_DIRECT` instead, which is a thin
adapter onto `OSAPI_GFX_LINE` and costs ~20 bytes — the point of naming it is
that a program keeping the kernel's line must not silently pull in a
rasteriser.

### 4.2 What the lattice buys over today's kernel

`GFXE_WALK` implying `GFXE_LINE` is what deletes §1.2's duplication: the
resumable walk becomes *"`GFXE_LINE`'s recurrence, with the state in the
caller's block instead of in `.bss`"*, so `gfx_lstep_mono`'s 212 bytes are the
`GFXE_LINE` body it already had. **A package taking `GFXE_WALK` should come out
around 580 bytes where the kernel spends 498 on the two plotters alone.**

This is the one claim in this document that is a *design* claim rather than a
measurement, and §9 owes evidence for it.

---

## 5. Who ships on the small disks, and what each would choose

The small apps disk is `APPS_TOOLS` less `SMALLOMIT` plus `APPS_GAMES` less
`SMALLOMIT_GAMES` — so **artful, calc, chart, fontview, fractal, hello,
notepad, paint, piano, sheet, texpad** and **arkanoid, cyclone, mines, missile,
pacman, solitair, tamegram**, plus the `SYSAPPS` and the core copies on the
system disk.

| package | `LINE` | `WALK` | `PIXEL` | `BLIT1` | on small? | likely choice |
|---|:-:|:-:|:-:|:-:|:-:|---|
| **Paint** | ✓ | | | ✓ + `SPANS` | yes | `LINE` + **`LINE_FAST`** + `WIDE` — §42.8's stroke is the reason, and 4.9× is new to this build |
| **Sheet** | ✓ | | | | yes | `LINE` only; grid on fresh ground, so compose mode fits |
| **Cyclone** | ✓ | ✓ (`LINIT`,`LSTEPV`) | | | yes | `WALK` + `LINE_DIRECT` — §3.2, no band |
| **Missile** | ✓ | ✓ (all three) | ✓ | | yes | `WALK` + `LINE_DIRECT`; the case §3.2's arithmetic most favours |
| **Mines** | | | ✓ (two 10px diagonals) | | yes | `BAND` alone — the X becomes 20 bit-sets and one blit |
| **Word** | | | ✓ (one pixel) | ✓ | yes | `BAND`; it already blits |
| **Weave** | | | ✓ (44–64 calls, **35–50 ms**) | ✓ | yes | `BAND` — the biggest single win in this column |
| **Artful, Arkanoid, PacMan, os88type** | | | | ✓ | yes | nothing; they are already band callers |
| **Tank** | ✓ | ✓ | | | **no** (`SMALLOMIT_GAMES`) | `WALK` for `tkattr.inc`; `tkraster.inc` is unaffected |
| **Skies, Telnet, The Wire** | | | | ✓ | **no** (`SMALLOMIT`) | — |
| **`SAVER.DRV`** | | ✓ | ✓ | | **no** (`SMALLDRIVERS = $(KMODS)`) | `WALK_BATCH` on `kern_big` |
| **`os88ui.inc`** | ✓ (checkmark) | | (macro, **0 users**) | | 25 packages | **neither** — see §6.1 |
| **`apps/cc`** | ✓ | ✓ | ✓ | ✓ | yes | the C SDK is its own question (§7) |

---

## 6. `gfx_pixel` — DEFERRED, and priced here so the deferral is informed

**This is a separate piece of work and comes AFTER the line waves**, by the
owner's decision. It is recorded here rather than started because the pricing
below is what makes the sequencing obviously right: `GFXE_BAND` is what gives
the callers somewhere better to go, so retiring the slot before the library
exists would be a caller sweep with no destination.

The proposal is to retire `OSAPI_GFX_PIXEL` outright as a benchmarking relic
that confuses readers. **Three corrections, and the conclusion still mostly
stands.**

1. **It is 12 bytes.** Not a primitive with a body — a wrapper:

   ```
   gfx_pixel:
       ...
       call gfx_fill               ; a pixel is a 1x1 solid rect
   ```

   Retiring it returns **12 bytes of `.text`**; the API cell stays either way,
   pointing at the shared refusing stub. `gfx_hline` (13 bytes) is the same
   shape and the same argument.

2. **It has shipping callers, not benchmark ones.** `word` (one pixel, the
   decimal tab's point), `mines` (two 10px diagonals), `weave`
   (44–64 calls, *"35–50 ms field-measured"*), `saver/svstars.inc`,
   `gfxbench`, and — the one that binds — **`os88_gfx_pixel()` published in
   `apps/cc/os88.h:475`**, so retiring it is a C SDK break.

3. **The confusion is real but it is about COST, not existence.** The slot reads
   like a cheap per-pixel primitive and is **640.87 µs**, because it is a whole
   `gfx_fill` arrival. That is a documentation defect, and SPEC.md 5.6's entry
   for it should say so in one line whatever else is decided.

**The library's answer is better than either keeping or retiring it**: under
`GFXE_BAND` a pixel is a bit-set in the app's own band and the commit is one
blit. Weave's 44–64 calls at 35–50 ms become **one** blit; Mines' X becomes 20
bit-sets. So the sequence is *give the callers somewhere better to go, then
retire the slot* — and the 12 bytes are the least of what that is worth.

### 6.1 `os88ui.inc` is not an obstacle, and its `UI_PIXEL` is dead

37 files across **25 packages** include `os88ui.inc`, which is where the
"everyone would embed a rasteriser" objection comes from. It does not hold:

- the include's only line use is the **menu checkmark**, two *fixed* ±45°
  strokes 4 and 5 pixels long (`apps/os88ui.inc:3986`, `:3993`). A glyph, or an
  `OSAPI_ICON_DRAW` record, replaces it — **no library**;
- `UI_PIXEL` is a macro with **zero call sites** anywhere in `apps/` or
  `drivers/`. It is not a caller of `OSAPI_GFX_PIXEL`; it is a definition
  nobody expanded.

**The checkmark change can land on its own, before any of this**, and it should:
it is the only thing standing between `OSAPI_GFX_LINE` and a caller list of
four programs.

---

## 7. The C SDK is a separate decision

`apps/cc/os88.h` publishes `os88_gfx_pixel`, `os88_gfx_line`,
`os88_gfx_linit/lstep/lstepv`. A C package cannot `%include` a NASM library, so
`gfx_embeddable` reaches C only as either

- **a linkable object** compiled from a C source of its own — which is new
  ground for this SDK, or
- **the thunks staying exactly as they are**, calling the kernel slots.

**The second is the answer for now**, and it means the kernel keeps a `gfx_line`
body for as long as any C package wants one — so §8's waves are about
*shrinking* the kernel's line surface, not deleting it, unless the C surface is
withdrawn first. That is a decision to take deliberately and it is not this
plan's to take.

---

## 8. Waves, in the order the evidence ranks them

Each is independently landable and each is a separate PR.

| wave | what | prize | risk |
|---|---|---|---|
| **0** | `os88ui.inc`'s checkmark → one `OSAPI_GFX_BLIT1` band. **Sequenced AFTER `gfx_blit1` lands on `kern_small`** (§2.4), which is happening for its own reasons | takes `OSAPI_GFX_LINE`'s caller list from **25 packages to four programs**, and the checkmark gets **~2× faster** — ~780 µs against today's two `gfx_line` calls at ~1.68 ms | the band's x must be on the byte grid (SPEC.md 5.4.2) and the check column is `MRECT+2`, so compose a 16px band at the enclosing 8-aligned column with the mark shifted inside it |
| **1** | `apps/os88gfx.inc` with `GFXE_BAND` + `GFXE_LINE`; **Sheet** is the first customer, compose mode, nothing gated out of the kernel | proves the lattice; ~350 bytes of Sheet | none — the kernel is untouched |
| **2** | `GFXE_LINE_FAST`; **Paint on `kern_small`** takes it | Paint's stroke **4.9×** on the floor machine, +647 of Paint's own image | Paint's small build is size-sensitive (§24.5) |
| **3** | `GFXE_WALK` on **Missile's drain only** — §3.2 is BENCHED (Set 132) and the drain is 2.6× better app-side; its missiles and Cyclone's warp are 1.4× worse and stay on the kernel walk | ~230, and 14.5 ms a frame off the drain | a package on both paths at once — Missile would carry the library AND call the slot |
| **4** | gate `gfx_linit/lstep/lstepv` out of both kernels | **−537 / −641** | **Set 132 narrows this to one question**: the walk beats both published alternatives only at **1.3–4.2 px a block a frame**. Read what Cyclone and Missile actually step (this plan's 9.1); outside that window they lose nothing by leaving, and a program that spans it — Missile does, `MC_DRN_RATE` being jittered — picks per effect |
| **5** | gate `gfx_line_fast`, `gfx_line_runs`, `gfx_lf_wide3` out of `kern_big` | **−874** from `kern_big` alone | Paint and Sheet must be on the library first |
| **6** | gate `gfx_line` itself | the remainder, ~660 / ~800 | blocked on §7 outright |

**Waves 0–3 take nothing out of either kernel.** That is deliberate: every one
of them is reversible and none of them can break a shipped program, so the
whole risky half of the plan is waves 4–6 and each of those is gated on a
program actually being on the library first.

---

## 9. What is NOT settled — evidence owed before wave 3

1. **§4.2's layering claim is a design claim, not a measurement.** *"`GFXE_WALK`
   is `GFXE_LINE`'s recurrence with the state in the caller's block"* has to be
   written and assembled before the ~580 is quotable. If the two walkers turn
   out not to unify, wave 3's prize is ~790 and wave 4 is still worth taking.
2. **The commit's real cost is per BAND AREA, not per pixel.** A 127×32 line's
   band is 508 bytes whether it carries 127 pixels or 4,064. **Measure a real
   figure** — Sheet's grid, Paint's stroke — never a single line.
3. **Clip and ink come back.** The 24.6 µs is a rasteriser with no clipping, no
   ink and no dither. A caller that needs them pays them, and `gfx_blit1` still
   refuses an x off the byte grid.
4. ~~§3.2 is arithmetic and is the single most valuable thing to bench.~~
   **DONE — PERFORMANCE.md Set 132.** What it left owed is one cheap reading
   and it is now the top of this list: **instrument Cyclone and Missile for
   the pixels-a-block-a-frame they actually step.** The walk's window is
   1.3–4.2; a counter in `cy_warp_render` and in Missile's `mc_dsc` build is
   one rebuild and it decides wave 4 outright. Missile spans the window inside
   ONE `gfx_lstepv` call — `MC_DRN_RATE` is jittered per trail and `MC_DRNBUD`
   caps the queue at 64 a frame — so the answer there is per EFFECT, not per
   program.
5. **Nothing here has been measured on the glass.** Every µs figure is quoted
   from PERFORMANCE.md's 5150 sets; every byte figure is from this tree's map.
   No wave has been built.

---

## 10. Method, and how to re-derive any of it

Sizes are per-symbol from `nasm [map all]` on a whole-kernel re-assembly,
summed per section and **reconciled against the section lengths from the
summary block** — that equality is what makes a per-feature figure quotable
rather than indicative (KERN-SMALL-CUT-PLAN §9.1's method, and the same
`symmap.py`). A symbol's size is the distance to the next symbol in the same
section, with NASM's anonymous macro locals attributed to the preceding
top-level label.

Reconciliation for the family total: the contiguous block `gfx_linit` →
`gfx_blit4` is **1,368** (small) / **2,511** (big); the per-symbol sum is
**1,377** / **2,520**; the difference is `gfx_lmtab` (8) and `gfx_lmsk` (1),
which sit elsewhere in `.text`. Both numbers are right and they answer
different questions — quote the contiguous block for *"what a gate returns"*
and the per-symbol sum for *"what the capability weighs"*.

Timings are PERFORMANCE.md's, all from the field 5150:
`GFX_PIXEL` 640.87 µs, `GFX_LINE` 37.1 µs a pixel (31.6 less the arrival), the
candidate mask rasteriser 24.6, the walk's marginal pixel ~175, its block setup
~480, an arrival 128.7.

---

## 11. Sequencing, as decided

1. **The line waves first** (§8 waves 0–6). `gfx_pixel` (§6) is a different
   piece of work and follows them.
2. **Keeping the walker inside the app is fully in scope** and is `GFXE_WALK`.
   §3.2 is what it plots through, and the answer is likely to be
   `OSAPI_GFX_LINE` a segment rather than a band.
3. **`gfx_blit1` on `kern_small` is not this plan's to justify** — it is
   already wanted for its own reasons (§2.4), and this plan assumes it.
