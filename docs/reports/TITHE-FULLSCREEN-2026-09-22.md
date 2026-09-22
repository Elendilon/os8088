# TITHE — does the fullscreen RENDERER need to exist?

*Taken 2026-09-22 on branch `tithe-plan`, MartyPC `os8088_xt_vga`, guest
seconds. Every figure is the built renderer; nothing here is modelled.*

## Why it was going to exist, and why that reason is gone

SPEC.md §97.6 planned **two renderers**: windowed through `OSAPI_GFX_BLIT1`,
and a fullscreen arm inside §53's bracket where the app owns every pixel and
puts the band down by hand. The reason was the drawing budget — the windowed
arm was not believed to have one.

**Two things have happened to that premise since.** TITHE-PLAN §3.7's second
pass took the kernel's own fast path (SPEC.md §5.4.2.6) and cut fullscreen's
lead from **1.97× to 1.27×** on a whole band, and its own table already
concluded that *windowed with a dirty rect beats fullscreen without one*. And
the field has since reported the windowed arm not merely adequate but **too
fast** — the idle share was halved to 20% because 6.4 fps a feature read as
hurried (SPEC.md §97.5).

**The third option nobody had priced is `wm_fullscreen` (SPEC.md §11.2), and it
is the one that settles this: a fullscreen surface IS A REAL WINDOW.** It is
the whole 640×480 with no chrome and no §53.7 bracket, so **every kernel
drawing slot still works**. That is the *pixels* of fullscreen without the
second renderer, and it costs one API call.

`F` now takes it. It used to step the surface row inside an ordinary window,
which mostly refused — the vga-full board is 326 rows and its HUD another 36
against a 355-row content box.

## The measurement

Both arms are the SAME renderer. What changes is the geometry row: windowed is
cell 96×48 with a 64×44 band, fullscreen is cell 96×52 with a 64×48 band.

| | commits/s | frames/s | fps a feature |
|---|---:|---:|---:|
| windowed | 89.0 | 18.6 | 4.24 |
| windowed + dirty rect | 123.6 | 18.7 | 5.88 |
| windowed + dirty + bolt | 124.5 | 18.7 | 5.93 |
| **fullscreen window** | 70.8 | **18.8** | 3.37 |
| **fullscreen + dirty rect** | 105.9 | **18.6** | **5.04** |
| **fullscreen + dirty + bolt** | 106.8 | **18.7** | **5.09** |

**The frame holds a pass a tick in every arm** — 18.6 to 18.8 against the
tick's 18.2 — and `ti_trim` reads 100 throughout, so nothing is overrunning and
nothing is being trimmed to get there.

**Fullscreen costs 20% of the commit rate plain and 14% with the dirty rect.**
The arrival is *identical* at both geometries (808 µs against 809), so the
whole of the difference is four more rows a band at 43 µs each.

**And a bolt is free in both**, which is §97.5.1's lane separation doing its
job: 124.5 against 123.6 windowed, 106.8 against 105.9 fullscreen.

## What the second renderer would buy, and what it would cost

**Buy**: §97.6's 1.27× per band. Applied to the fullscreen + dirty row, that is
105.9 → ~134 commits/s, or **5.04 → ~6.4 fps a feature**.

**That is a rate the field has already rejected.** 6.4 fps a feature is the
number the idle share was halved to get *away* from — reported as *"too fast…
the rate of updates looks right"* only after `-` had been pressed repeatedly
(SPEC.md §97.5). So the second renderer's entire headline benefit is a rate
this game does not want and is currently giving back.

**Cost**: after the first `OSAPI_FSX_MODE` **no kernel drawing slot is legal**
(§53.7). The fullscreen arm would letter its own HUD, draw its own card panel,
its own frames, its own icons and its own text — a second renderer for every
surface TITHE has, not a second blit path. `docs/plans/completed/GFX-FSX-PLAN.md`
is the record of what that costs elsewhere in this tree: three apps carry their
own Bresenham because of it.

## The verdict

**REFUSED for wave 1a, on evidence rather than on schedule.** A fullscreen
window at the fullscreen geometry, drawn by the renderer that already exists,
runs at **5.04 fps a feature and 18.6 frames a second with a bolt in flight** —
better than the plain windowed arm the field signed off, and above the 3.6 fps
TITHE-PLAN §1.3 set as the bar.

**What would re-open it**, and each is a measurement rather than an opinion:

- a board that grows — more than 20 characters, or a cell pitch that makes the
  band taller, since the cost here is entirely per-row;
- a `Quad` detail arm (§97.4.6), which is fullscreen-only and is the one
  feature that genuinely needs the framebuffer;
- tear-free animation, which wants `fsx_page` (§53.10) and is not reachable
  through the WM at all.

None of those is wave 1a's, and none of them is worth a second renderer until
one of them is measured to need it.
