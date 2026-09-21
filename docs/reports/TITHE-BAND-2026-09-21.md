# TITHE wave 0 — what a sprite band actually costs

| | |
|---|---|
| machine | **MartyPC**, cycle-accurate 4.77 MHz 8088 — `os8088_xt_vga`, `os8088_5150_herc_gla`, `os8088_5150_cga_gla` |
| harness | `tests/titheband/titheband.asm` (benchlib), driven by `tests/titheband.py` |
| tree | `7c2517b8` + this branch |
| date | 2026-09-21 |
| reproduce | `make titheband && python3 tests/titheband.py` |

This is **wave 0 of `docs/plans/TITHE-PLAN.md`** (its TITHE-PLAN §3.7): the measurement that
decides the art format, taken before any art is drawn. A measurement is true of
the tree it was taken on and of no other.

---

## 1. The headline

**TITHE-PLAN's frame budget is out by a factor of two, and the reason is a term
the plan does not have.**

Every figure in TITHE-PLAN §1.3 descends from one constant — **6.15 µs a band byte** —
derived from PERFORMANCE.md Set 77's measurement of a **128×128** band. That
band is sixteen bytes a row. A 56×56 sprite is seven. `gfx_blit1` charges a
real cost **per row**, and a per-byte reading taken at the widest shape in the
system is the reading most favourable to a narrow one.

| | plan TITHE-PLAN §1.3 | measured | |
|---|---:|---:|---:|
| VGA fullscreen, 56×56 = 392 B | 2.41 ms | **4.79 ms** | **1.99×** |
| VGA windowed, 48×44 = 264 B | 1.62 ms | **3.92 ms** | **2.42×** |
| Hercules, 64×40 = 320 B | 1.97 ms | **4.34 ms** | **2.20×** |
| CGA, 48×24 = 144 B | 0.89 ms | **2.65 ms** | **2.98×** |

The error grows as the band shrinks, which is the signature of a fixed cost
being modelled as a variable one.

---

## 2. The model that replaces it

Three shapes of the **same 392 bytes** — 56×56 (7 B/row), 112×28 (14 B/row) and
224×14 (28 B/row) — separate the two terms; the 128×128 bar then fixes the
per-byte term against a known number. This is Set 108's method for `gfx_blitp`,
applied to the primitive TITHE draws with.

```
    gfx_blit1  =  ARRIVAL  +  rows × PER_ROW  +  bytes × PER_BYTE
```

| adapter | arrival | per row | per byte |
|---|---:|---:|---:|
| **VGA** | 709 µs | **52.05 µs** | **2.98 µs** |
| **Hercules** | 727 µs | 52.52 µs | 4.34 µs |
| **CGA** | 712 µs | 55.35 µs | 3.97 µs |

**It predicts every other row in the table to within 3.4%, and most to under
2%** — the 104×72 cell to 0.03% on VGA. The residual sits on the bands whose
stride is *even* (48 px = 6 bytes), which take `rep movsw` with no trailing
`movsb`; the model does not carry that term and does not need to.

Two things fall out that the per-byte model cannot express:

- **A row costs ~52 µs before a byte moves.** That is ~18 bytes' worth of
  traffic on VGA. A sprite that is tall and narrow pays most of its cost in
  rows — 56×56 spends **2,915 µs of its 4,793 on rows and arrival**, and only
  1,168 on its own pixels.
- **Shortening a sprite is worth about three times as much as narrowing it.**
  Dropping 56×56 to 56×40 saves 833 µs; dropping it to 40×56 saves 477.

The bar agrees with Set 77 to **+7.1%** (13,483 µs against 12,588), which is
what makes the rest of the table quotable: two harnesses that disagree about
the same primitive is a finding in itself, and this pair does not.

---

## 3. Every row, three adapters

Microseconds per operation. `t` = benchlib method T (tick-timed, ±1 tick over
the row: ±763 µs on the `BLITP` rows, ±1,144 on the wheel).

| row | VGA | Hercules | CGA |
|---|---:|---:|---:|
| `BLIT1 128x128` *(the bar)* | 13,483.45 | 16,334.49 | 15,930.50 |
| `BLIT1 104x72` *(the cell)* | 7,252.13 | 8,462.55 | 8,325.56 |
| `BLIT1 64x40` | 3,754.30 | **4,339.66** | 4,266.81 |
| `BLIT1 56x56` | **4,793.49** | 5,369.03 | 5,368.35 |
| `BLIT1 48x44` | **3,919.71** | 4,293.41 | 4,264.88 |
| `BLIT1 48x24` | 2,471.26 | 2,667.08 | **2,652.49** |
| `BLIT1 112x28` *(=392 B)* | 3,376.31 | 3,902.87 | 3,820.60 |
| `BLIT1 224x14` *(=392 B)* | 2,607.18 | 3,163.04 | 3,043.75 |
| `PEN set+restore` | 111.88 | 111.84 | 111.84 |
| `BLIT1` + default pen | 4,861.12 | 5,441.73 | 5,440.53 |
| `BLIT1` + ink/black pen | 5,020.65 | 5,489.08 | 5,494.72 |
| `BLIT1` + black/white pen | **6,174.21** | 5,488.99 | 5,494.72 |
| `BLIT1` + split pen (8 on 7) | **10,316.80** | 5,489.08 | 5,494.60 |
| `BLIT1 56x56` in 2 strips | 5,940.71 | 6,301.51 | 6,294.31 |
| `BLIT1 56x56` in 3 strips | 6,859.83 | 7,100.88 | 7,093.71 |
| `BLITP 56x56` 4 planes | **33,565.71** | *refused* | *refused* |
| `BLITP 112x28` 4 planes | 19,834.28 | *refused* | *refused* |
| `BLITP 104x72` 4 planes | 49,585.72 | *refused* | *refused* |
| `COPY 392B` strided | 1,813.47 | 1,813.47 | 1,813.47 |
| `MASKOR 240B` naive | 6,046.12 | 6,046.17 | 6,046.17 |
| `MASKOR 240B` interleaved | 5,190.91 | 5,190.85 | 5,190.84 |
| `COMPOSE body+item` | 7,881.44 | 7,881.44 | 7,881.44 |
| `COMPOSE` lean | 7,025.91 | 7,025.91 | 7,025.87 |
| `PROJECTILE` one frame | 9,590.58 | 9,849.77 | 9,831.89 |
| `PROJECTILE` lean | 8,881.79 | 9,152.45 | 9,130.94 |
| **`WHEEL` 23 × 56×56** | **110,995.72** | 124,727.15 | 124,727.15 |
| **`WHEEL` 23 × this surface's band** | **110,995.72** | **100,697.15** | **60,647.15** |
| `WHEEL` 23 × pen + band | 114,428.58 | 101,841.44 | 61,791.43 |
| `COMBAT` 4 projectiles + 4 idles | **56,070.00** | 58,358.57 | 58,358.57 |
| `SND_TONE` note-on | 395.89 | 395.84 | 395.89 |
| `SND_FM` note-on | *skipped — no FM sink* | *skipped* | *skipped* |

**Three internal controls, and all three pass.** The four **RAM** rows read
identically on all three adapters to within 0.01%, because RAM is RAM. The
**pen** rows collapse onto one value on both 1bpp adapters (spread 0.9% and
1.0%) and separate on VGA, because SPEC.md §5.4.2.2 does not read a pen on one
plane. And on VGA the two wheel rows are the *same measurement by construction*
— that surface's band **is** 56×56 — and they read **identically**.

---

## 4. The wheel, which is the brief

23 features, one update each, against a 54.925 ms frame:

| surface | band | measured | of one frame |
|---|---|---:|---:|
| VGA fullscreen | 56×56 | **110.99 ms** | **202.1%** |
| Hercules | 64×40 | 100.70 ms | 183.3% |
| CGA | 48×24 | 60.65 ms | 110.4% |

**The wheel costs exactly 23 bands and not a microsecond more** — 23 × 4,793.49
is 110,250 against the 110,996 measured, 0.7% — so TITHE-PLAN §3.6's pacing wheel carries
no overhead of its own. That is worth knowing: the cost is entirely the blits,
and every lever is on the band.

**What this does to TITHE-PLAN §1.3's "fps a feature"**, at the plan's own 40%-of-a-frame
share (21,970 µs):

| surface | plan | **measured** |
|---|---:|---:|
| VGA fullscreen | 7.2 fps | **3.6 fps** |
| VGA windowed | 10.8 | **4.4** |
| Hercules | 8.8 | **4.0** |
| CGA | 19.5 | **6.6** |

**This is not obviously fatal and it is not for this document to decide.** TITHE-PLAN §3.8
measured the reference game's idle cycle at **~1.0 s**; a 4-pose ping-pong at
3.6 fps is a **1.1 s** cycle. The rate halved and the *cycle length* landed on
the reference's. Whether twenty figures breathing at 3.6 fps reads as a crowd
idling or as a slideshow is TITHE-PLAN §16.1's question and only eyes can answer it —
which is exactly why wave 1a exists and why this bench comes before it.

---

## 5. The pen: four paths, and one of them is not affordable

On VGA, all against the same 392-byte band (4,793.49 µs plain):

| path | measured | over plain |
|---|---:|---:|
| the default pair, short-circuited | 4,861.12 | **+67.6 µs** |
| `B` empty — any ink over BLACK paper | 5,020.65 | +227 (+4.7%) |
| `A` empty — black on white, the complementing loop | 6,174.21 | **+1,381 (+28.8%)** |
| both — §5.4.2.2.1's **Map Mask split**, two passes | **10,316.80** | **+5,523 (+115%)** |

The default pair's +67.6 µs sits right on Set 77's *"fixed ~78 µs"*. The
complementing loop's +28.8% sits right on its *"34 clocks a word against the
rep's 25"*. **Both of SPEC.md's claims are confirmed at our band size.**

The one the plan has to act on is the last. **A faction colour over black is
+4.7%. The same colour over anything else may be +115%** — a second whole pass
over the band. TITHE-PLAN §3.5's three detail arms are all priced against the short
circuit, and that is only right for ink-over-black.

### The banded arm, priced

TITHE-PLAN §3.5(b) stacks 2–3 strips with a pen each. **The bytes are identical**; what is
added is one arrival per strip, and it is dead flat:

| | VGA | extra |
|---|---:|---:|
| one strip (ink/black pen) | 5,020.65 | — |
| two strips | 5,940.71 | **+920.1** |
| three strips | 6,859.83 | +1,839.2 (**+919.6** each) |

**+920 µs an extra strip** — the 709 µs arrival, its own pen, and a little row
set-up. Three strips buys 4–6 colours a character for **+37%**. That is a real
trade and now it is arithmetic rather than a guess.

---

## 6. Four planes: the `Rich` arm is dead on an 8088

| | measured | row-planes | bytes |
|---|---:|---:|---:|
| `BLITP 56x56` | 33,565.71 | 224 | 1,568 |
| `BLITP 112x28` | 19,834.28 | 112 | 1,568 |
| `BLITP 104x72` | 49,585.72 | 288 | 3,744 |

Fitting the three: **~122.6 µs a row-plane and ~3.76 µs a byte**, against Set
108's 114.1 and 3.98 — agreement within 7%, at sizes Set 108 never took. *(The
arrival term is not separable at method T's resolution and is not quoted.)*

**TITHE-PLAN §1.1 says this slot is "NOT MEASURED anywhere in this tree". That
is wrong — Set 108 measured it on this exact machine — and the estimate the
plan carries instead, ~3.1 µs a byte, gives 4.9 ms for a 56×56 four-plane
sprite. TITHE-PLAN §1.2's own table says 9.6 ms. The truth is 33.6 ms.**

A four-plane sprite is **7.00× the one-bit band**, not 4×, because 56 rows
becomes **224 row-plane operations** before a byte moves. 23 features in `Rich`
is **772 ms — fourteen frames for one update of the board.**

`gfx_blitp` refuses on both 1bpp adapters, as SPEC.md §5.4.3 says it must, and
the bench prints that refusal **in words**: a refusal and a very fast blit are
the same number.

---

## 7. RAM: composition and the projectile

Identical on all three adapters, as they must be.

| | µs | per byte |
|---|---:|---:|
| `COPY 392B` strided (56 rows of 7 out of a 52-byte-wide picture) | 1,813.47 | 4.63 |
| `MASKOR 240B` naive (12-instruction loop) | 6,046.12 | 25.19 |
| `MASKOR 240B` interleaved (8-instruction loop) | **5,190.91** | **21.63** |

**PERFORMANCE.md's 15.3 µs a byte is a FIVE-instruction loop and does no
masking; quoting it against a masked composite is comparing two programs.** The
interleaved form — item data and mask stored `data,mask,data,mask` so one
`lodsw` fetches both — is **14.1% cheaper** and costs the same bytes on disk.
It is what `tools/os88tithe.py` should emit, and the pair is in the bench so
that the naive row cannot silently over-price TITHE-PLAN §4.2.1's layers by a sixth.

*(The predicted saving was 40%, from the 8088's `max(clocks, 4.34 × instruction
bytes)` fetch floor. It came out 14%, because at this size the loop is
clock-bound rather than fetch-bound. The measurement stands; the prediction was
the wrong model.)*

### The projectile — TITHE-PLAN §3.9.1's four steps

| step | plan TITHE-PLAN §3.9.1 | measured |
|---|---:|---:|
| two strided RAM→RAM copies of 192 B | ~0.8 ms | **~1.78 ms** |
| mask-OR 192 B | ~2.9 ms | **~4.15 ms** |
| commit, one `gfx_blit1` 48×32 | ~1.2 ms | **~2.95 ms** |
| **one projectile frame** | **~5 ms** | **8.88 ms** |

**1.78× the plan**, and the blit is where most of it went — the per-row term
again, on a 32-row band.

| | plan | measured |
|---|---:|---:|
| four in one lane | ~20 ms (36% of a frame) | **35.5 ms (64.7%)** |
| the whole combat frame (4 projectiles + 4 idles) | ~30 ms (55%) | **56.07 ms (102.1%)** |

**The busiest frame in the game is 102% of a frame.** TITHE-PLAN §3.9.1 already stops the
other four lanes idling to pay for it; that concession now buys back less than
it was thought to, and the projectile count or the projectile band is what has
to give.

---

## 8. Sound

`SND_TONE` note-on: **395.89 µs**, the same on all three adapters — **0.72% of
a frame**. TITHE-PLAN §13.5 estimates the sequencer at ~0.5% of the machine; for the
speaker arm that stands, with the note-on as its expensive event.

**The FM arm is not measured and no machine in this tree can measure it.**
`SND_CAP_FM` appears only while a sound driver is loaded (SPEC.md §34.2,
§51.4) and none of the three machines boots with one. It wants a run on a
machine with an AdLib or SB attached, and until then TITHE-PLAN §13.5's FM figure stays an
estimate — which the report says in words rather than printing a zero.

---

## 9. Two things this cost, both worth not repeating

### 9.1 A bench sized against its own hypothesis takes as long as the hypothesis is wrong

The first cut of `titheband.asm` took its iteration counts from TITHE-PLAN
TITHE-PLAN §1.3's 2.41 ms a band — **the number under test**. The run took **seven minutes
of guest time** instead of thirty seconds.

The first reading of that was *"so `gfx_blit1` really is much slower than the
plan assumes"* — which is the conclusion the bench was built to reach, so it
looked like the finding rather than like a defect. **It was neither.** Reading
`bl_nrow` out of the running package says every measurement row completes in
**under four guest seconds**; the whole of the time was one row that never
returned (section 9.2). A bench that hangs on its final row looks exactly like a bench
whose rows are slow.

`-DTBQUICK` exists because of this: the same rows at a handful of iterations,
a couple of guest seconds, numbers too coarse to quote and exactly good enough
to size the real run and to prove the path works before anybody waits on it.

### 9.2 `OSAPI_SND_FM` with no sound driver does not refuse — it wedges the machine

SPEC.md and `apps/os88api.inc` both say the FM slot answers **CF = 1** when no
sound driver is loaded. Called from inside benchlib's `cli` window on a machine
with no driver, **the guest does not come back**: it leaves the kernel
entirely, spins with `CS = 0`, and ~98% of its samples land in the BIOS's own
**unexpected-interrupt handler at F000:FF23** — the one that masks the
offending IRQ and stores it at `0040:006B`.

This is reported as an observation, not a diagnosis: it was found by sampling a
wedged guest, and what the kernel does between the slot and that handler has
not been traced. The bench's answer is to **ask `OSAPI_SND_CAPS` first, outside
any timed body, and not to call a sink that is not there** — which is the
honest thing regardless, since a timed refusal is not a note-on cost.

**It is worth someone's time to find out whether a package can reach this with
interrupts enabled**, because if so it is a plain robustness defect in a slot
whose documented contract is a refusal.

---

## 11. THE LEVERS — three asked for by name, and what each is worth

A second pass, asking three specific questions about *getting the rate back*.
Same machine, same harness, same day. **Every row here is a like-for-like
comparison at each adapter's own band**, which the first cut of two of them was
not (section 11.5 below).

### 11.1 Q1 — own the framebuffer, and half the cost goes away

A windowed band pays for things a fullscreen program does not have: a far call,
nine argument refusals, the deferred cursor hide, the second-display span, the
clip region, nine pushes, a display enter, a screen-extent clip, the pen, and a
rowbase multiply — **690 µs, measured directly** by an 8×1 band, which agrees
with the fitted 709 of section 2 to 3%. Then a row loop that reads **five SS-relative
operands out of a stack frame**, because all nine of `gfx_blit1`'s registers
carry geometry it needs.

Inside an `OSAPI_FSX_RUN` bracket that has set a mode (SPEC.md §53), the app
owns every pixel, `OSAPI_FSX_MODE` hands back `FSI_SEG`, and none of that work
exists. The same band, by hand, with every per-row value **in a register**:

| | windowed `gfx_blit1` | **fullscreen, own loop** | |
|---|---:|---:|---:|
| VGA, 56×56 | 4,701.66 µs | **2,379.94** | **−49.4%** |
| Hercules, 64×40 | 4,248.02 | **2,243.13** | **−47.2%** |
| CGA, 48×24 | 2,560.99 | **1,177.66** | **−54.0%** |

and the whole 23-feature wheel:

| | windowed | **own loop** | of one frame |
|---|---:|---:|---:|
| VGA | 111.00 ms | **56.07** | 202% → **102%** |
| Hercules | 100.70 | **53.78** | 183% → **98%** |
| CGA | 61.79 | **28.61** | 113% → **52%** |

**That is the plan's original budget back, exactly.** At TITHE-PLAN §1.3's 40% share a
feature updates at **7.3 fps on fullscreen VGA** against the 7.2 the document
was written with, 7.8 on Hercules and 14.8 on CGA.

**The loop is READ BACK and compared with the band on every adapter, and says
MATCH.** A hand-rolled emit that is fast and wrong is the easy mistake here,
and its time would look exactly like the win it is measuring. The first draft
of it was wrong in precisely that way — `rep movsw` plus the tail byte has
already advanced the source by a whole row, so adding the stride again
double-stepped the band and drew every other row. The read-back is what turns
that from a plausible number into a failure.

**What it costs is everything else.** After the first `OSAPI_FSX_MODE` no
kernel drawing slot is legal (§53.7): a fullscreen TITHE letters its own HUD,
composes its own card panel and draws its own menus. That is real work and it
is not new work — `apps/os88gfx.inc`'s `GFXE_BAND` is the library, `tests/
bandbench` the worked example of setting text into a band, and TANK, Skies and
Missile already do it. The windowed arm keeps `gfx_blit1` and its own rate.

### 11.2 Q2 — pairing two figures into one blit: no

The saving is **one arrival**, fixed. The cost is the **empty area inside the
union**, which scales with the cell pitch. Those two only meet per adapter, so
the pair here is cut from each adapter's own TITHE-PLAN §3.2.1 geometry — one lane's two
cells, `CW` apart in x and `RISE` in y.

| | two bands apart | one union | | whole wheel, 23 → 13 |
|---|---:|---:|---:|---:|
| VGA — union 160×76 | 9,411.07 | 9,046.89 | −3.9% | 111.00 → 107.56 ms, **−3.1%** |
| Hercules — union 184×56 | 8,503.54 | 8,997.00 | **+5.8%** | 100.70 → 105.27, **+4.5% WORSE** |
| CGA — union 128×32 | 5,139.93 | 4,431.00 | −13.8% | 61.79 → 53.78, **−13.0%** |

*(The stacked form asked about — 56×118, two figures 6 px apart — is measured
too, at 9,182.77 on VGA: **−2.4%**, the best case of the idea, and the sheared
grid does not put two characters there anyway. Two cells of one column are
`CH` = 72 apart, not 6, and that union is 56×128 — **worse** than two separate
bands.)*

**Verdict: no.** It is under the harness's own 2% repeatability on VGA
(section 11.5), negative on Hercules, and real only on CGA — and it costs TITHE-PLAN §3.6's
pacing wheel its granularity, which is the thing the wheel exists for: a pair
must be drawn together, so the credit quantum doubles and a character can no
longer animate while its neighbour holds. A 13% CGA-only win is not worth a
second code path and the loss of even degradation.

### 11.3 Q3 — the DIRTY RECT, which is the cheapest thing here

**An idle pose differs from its neighbour in part of the figure, not all of
it.** Blit only those rows. The band is still one opaque self-erasing
rectangle (TITHE-PLAN §3.4) — it is simply a shorter one — so nothing in the renderer
changes and no new mechanism appears.

| rows of 56 that differ | VGA | vs the whole band |
|---|---:|---:|
| 100% (56) | 4,701.66 | — |
| 70% (39) | 3,458.81 | **−26.4%** |
| 50% (28) | 2,666.04 | **−43.3%** |
| 35% (20) | 2,079.18 | **−55.8%** |

**It composes with section 11.1**, and together they are the whole answer:

| | one band | 23-feature wheel | of a frame | **fps a feature** |
|---|---:|---:|---:|---:|
| windowed, whole band | 4,701.66 | 111.00 ms | 202% | **3.7** |
| windowed + 50% dirty | 2,666.04 | ~62 ms | 113% | **6.5** |
| fullscreen own loop | 2,379.94 | 56.07 | 102% | **7.3** |
| **fullscreen + 50% dirty** | **1,218.30** | **29.75** | **54%** | **14.3** |

On Hercules the pair is 1,149.86 µs and **15.1 fps**; on CGA 614.65 and
**28.3 fps**.

**THE RECT IS THE TOOL'S JOB, NOT THE ARTIST'S.** It is a property of a
*transition* (A→B), not of a frame, so a 4-pose ping-pong has four of them;
and a row outside the rect that is not byte-identical between the two poses is
a stale row on the glass. `tools/os88tithe.py` diffs each consecutive pair and
emits the minimal covering band, which makes the constraint checkable instead
of a discipline. What the art has to do is keep each *transition's* motion
local — which is what the reference game's idles look like anyway (TITHE-PLAN §3.8) — and
a cycle can still cover the whole figure by moving a different region each
step.

The tool's own `--selfcheck` should print the mean coverage, because **that
number is the animation rate**: 50% coverage is 6.5 fps windowed and 14.3
fullscreen, 100% is 3.7 and 7.3.

### 11.4 …and one finding that is not TITHE's

The own loop does the same work as `gfx_blit1`'s emit and is **1.7× faster per
row** — 42.5 µs against 73.3 (the arrival removed). The difference is five
SS-relative frame reads at ~22 clocks each on an 8088, plus a per-row tail test
that a band decides once.

**That is ~30 µs a row available inside `gfx_blit1`, for every band caller in
the system** — fourteen of them, nine on the small disks. It is not a free win:
the kernel's loop also carries the tail mask, the complement path and
§5.4.2.2.1's split pass, so what it would take is a third body for the common
"no tail, no pen, no split" case, and a third body is bytes that are resident
for ever (CLAUDE.md's banner). **Recorded here as a measured opportunity rather
than a proposal**, because the measurement is TITHE's and the decision is the
kernel's.

### 11.5 What the harness's own repeatability is, and why it is a row

`BLIT1 56x56` is measured **twice**, sixty rows apart, and the later one reads
**2.0–2.2% lower on all three adapters** (4,687.74 against 4,793.60 on VGA).
That is systematic rather than noise and it is not explained here.

It is a row because **every headline in this report is a ratio between two
rows**, so 2% is the floor under all of them. Nothing in section 11.1 or 11.3 turns
on 2%; §11.2's VGA result is 3.1% and therefore does not survive it, which is
part of why that verdict is *no*.

---

## 10. What the plan has to change

Facts, not decisions — TITHE-PLAN §16.1's prototype is where the look question gets
settled and the owner's eye is the gate.

1. **TITHE-PLAN §1.1 gains a per-row term and loses "6.15 µs a byte" as a modelling
   constant.** The band cost is `arrival + rows × 52 + bytes × 3`.
2. **TITHE-PLAN §1.1's `GFX_BLITP` row is wrong twice**: it is measured in this tree (Set
   108), and the estimate it carries is 7× low.
3. **TITHE-PLAN §1.3's whole table doubles**, and "fps a feature" halves: 3.6 on
   fullscreen VGA, 4.4 windowed, 4.0 Hercules, 6.6 CGA.
4. **TITHE-PLAN §3.4's "58% off every animation commit" is 34%.** The band still wins —
   it is still the cheapest decision in the renderer — but the saving is
   per-byte only, while the per-row term and the arrival are unchanged.
5. **TITHE-PLAN §3.5 needs the pen's four paths**, and a rule: *ink over black, or pay up
   to 115%.*
6. **TITHE-PLAN §3.5(b)'s `Banded` arm has a price: +920 µs a strip**, +37% for three.
7. **TITHE-PLAN §3.5(c)'s `Rich` arm is refused on the 8088** — 14 frames for one board
   update — and survives only as a 386 arm.
8. **TITHE-PLAN §3.9.1's projectile is 8.88 ms, not 5**, and the combat frame is 102% of a
   frame rather than 55%.
9. **TITHE-PLAN §4.2.1's item bank should be interleaved** `data,mask,data,mask`: 14%
   off every composition for no disk and no new mechanism.
10. **TITHE-PLAN §13.5's speaker estimate stands; its FM estimate is untested** and needs
    a machine with a card.

The lever the measurement points at is **rows, not bytes** — and section 11 went and
priced three of them:

11. **The dirty rect is the cheapest win in the document** (section 11.3): −43% at 50%
    coverage, in both arms, no new mechanism, and the tool computes it.
12. **A fullscreen mode-setting bracket halves a band** (section 11.1) and restores
    TITHE-PLAN §1.3's original 7.2 fps exactly — at the price of drawing every other pixel
    ourselves.
13. **Pairing two figures into one blit is refused** (§11.2): under the
    harness's own repeatability on VGA, negative on Hercules, and it costs the
    pacing wheel its granularity.

Together, fullscreen and a 50% dirty rect are **14.3 fps a feature on VGA** —
four times what the plan measures today and twice what it was ever written
with.
