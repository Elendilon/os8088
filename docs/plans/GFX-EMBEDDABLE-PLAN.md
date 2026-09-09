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

## 3. The two modes, and which programs fit which

The library has to offer both, and the capability split in §4 falls out of it.

| | **compose-and-commit** | **direct** |
|---|---|---|
| how | rasterise into the app's own 1bpp band, one `OSAPI_GFX_BLIT1` | one kernel slot per primitive |
| per pixel | **24.6 µs** + the band's blit, amortised over the figure | `GFX_PIXEL` **640.87 µs**; `GFX_LINE` **37.1 µs** |
| ground | **OPAQUE** — the band's paper is written too | leaves what is underneath |
| costs | a band claim, and the app owns the ground | nothing |
| fits | Paint (own bitmap), Sheet (grid on fresh ground), any full-window repaint | anything drawing *over* something it did not paint |

**The opaque commit is the sharp edge of the whole plan.** Two shipped programs
are on the wrong side of it:

- **Cyclone** accumulates during a warp — *"NOTHING IS ERASED: the animation
  accumulates"* — so a band commit would wipe each frame's predecessors unless
  the app keeps a full-window shadow.
- **Missile** draws trails *over terrain* it did not paint, and its erase
  replays the identical walk.

Both can be answered — a full-window 1bpp shadow is ~14.2 KB at 448×258
(PAINT-1BPP-PLAN's measured figure) and is *heap paid while running*, which is
precisely the owner's premise — but it is a real cost and it is theirs to
decide, not this document's. `OSAPI_ICON_DRAW` is the only **transparent** 1bpp
commit on the machine and it is capped at 16 px a row, so it is not a general
answer.

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
| **Cyclone** | ✓ | ✓ (`LINIT`,`LSTEPV`) | | | yes | `WALK_BATCH`; **§3's shadow question is Cyclone's** |
| **Missile** | ✓ | ✓ (all three) | ✓ | | yes | `WALK_BATCH`; same question, plus terrain |
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

## 6. `gfx_pixel`, priced honestly — it is not what it looks like

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
| **0** | `os88ui.inc`'s checkmark → glyph; document `GFX_PIXEL`'s 640.87 µs in SPEC.md 5.6 | 0 bytes; unblocks everything | none — 25 packages, one include |
| **1** | `apps/os88gfx.inc` with `GFXE_BAND` + `GFXE_LINE`; **Sheet** is the first customer, compose mode, nothing gated out of the kernel | proves the lattice; ~350 bytes of Sheet | none — the kernel is untouched |
| **2** | `GFXE_LINE_FAST`; **Paint on `kern_small`** takes it | Paint's stroke **4.9×** on the floor machine, +647 of Paint's own image | Paint's small build is size-sensitive (§24.5) |
| **3** | `GFXE_WALK` / `GFXE_WALK_BATCH`; **Cyclone and Missile**, and §3's shadow question answered on the glass | ~580 each | the opaque commit — this is the wave that can fail |
| **4** | gate `gfx_linit/lstep/lstepv` out of both kernels | **−537 / −641** | needs wave 3 landed *and* the C surface settled (§7) |
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
4. **The opaque commit, on Cyclone and Missile specifically** (§3). This is the
   one that decides whether wave 3 exists.
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
