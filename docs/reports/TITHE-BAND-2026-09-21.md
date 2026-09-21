# TITHE wave 0 — what a sprite band actually costs

| | |
|---|---|
| machine | **MartyPC**, cycle-accurate 4.77 MHz 8088 — `os8088_xt_vga`, `os8088_5150_herc_gla`, `os8088_5150_cga_gla` |
| harness | `tests/titheband/titheband.asm` (benchlib), driven by `tests/titheband.py` |
| tree | `7c2517b8` + this branch |
| date | 2026-09-21 |
| reproduce | `make titheband && python3 tests/titheband.py` |

This is **wave 0 of `docs/plans/TITHE-PLAN.md`** (its §3.7): the measurement that
decides the art format, taken before any art is drawn. A measurement is true of
the tree it was taken on and of no other.

---

## 1. The headline

**TITHE-PLAN's frame budget is out by a factor of two, and the reason is a term
the plan does not have.**

Every figure in §1.3 descends from one constant — **6.15 µs a band byte** —
derived from PERFORMANCE.md Set 77's measurement of a **128×128** band. That
band is sixteen bytes a row. A 56×56 sprite is seven. `gfx_blit1` charges a
real cost **per row**, and a per-byte reading taken at the widest shape in the
system is the reading most favourable to a narrow one.

| | plan §1.3 | measured | |
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
is 110,250 against the 110,996 measured, 0.7% — so §3.6's pacing wheel carries
no overhead of its own. That is worth knowing: the cost is entirely the blits,
and every lever is on the band.

**What this does to §1.3's "fps a feature"**, at the plan's own 40%-of-a-frame
share (21,970 µs):

| surface | plan | **measured** |
|---|---:|---:|
| VGA fullscreen | 7.2 fps | **3.6 fps** |
| VGA windowed | 10.8 | **4.4** |
| Hercules | 8.8 | **4.0** |
| CGA | 19.5 | **6.6** |

**This is not obviously fatal and it is not for this document to decide.** §3.8
measured the reference game's idle cycle at **~1.0 s**; a 4-pose ping-pong at
3.6 fps is a **1.1 s** cycle. The rate halved and the *cycle length* landed on
the reference's. Whether twenty figures breathing at 3.6 fps reads as a crowd
idling or as a slideshow is §16.1's question and only eyes can answer it —
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
over the band. §3.5's three detail arms are all priced against the short
circuit, and that is only right for ink-over-black.

### The banded arm, priced

§3.5(b) stacks 2–3 strips with a pen each. **The bytes are identical**; what is
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
sprite. §1.2's own table says 9.6 ms. The truth is 33.6 ms.**

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
that the naive row cannot silently over-price §4.2.1's layers by a sixth.

*(The predicted saving was 40%, from the 8088's `max(clocks, 4.34 × instruction
bytes)` fetch floor. It came out 14%, because at this size the loop is
clock-bound rather than fetch-bound. The measurement stands; the prediction was
the wrong model.)*

### The projectile — §3.9.1's four steps

| step | plan §3.9.1 | measured |
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

**The busiest frame in the game is 102% of a frame.** §3.9.1 already stops the
other four lanes idling to pay for it; that concession now buys back less than
it was thought to, and the projectile count or the projectile band is what has
to give.

---

## 8. Sound

`SND_TONE` note-on: **395.89 µs**, the same on all three adapters — **0.72% of
a frame**. §13.5 estimates the sequencer at ~0.5% of the machine; for the
speaker arm that stands, with the note-on as its expensive event.

**The FM arm is not measured and no machine in this tree can measure it.**
`SND_CAP_FM` appears only while a sound driver is loaded (SPEC.md §34.2,
§51.4) and none of the three machines boots with one. It wants a run on a
machine with an AdLib or SB attached, and until then §13.5's FM figure stays an
estimate — which the report says in words rather than printing a zero.

---

## 9. Two things this cost, both worth not repeating

### 9.1 A bench sized against its own hypothesis takes as long as the hypothesis is wrong

The first cut of `titheband.asm` took its iteration counts from TITHE-PLAN
§1.3's 2.41 ms a band — **the number under test**. The run took **seven minutes
of guest time** instead of thirty seconds.

The first reading of that was *"so `gfx_blit1` really is much slower than the
plan assumes"* — which is the conclusion the bench was built to reach, so it
looked like the finding rather than like a defect. **It was neither.** Reading
`bl_nrow` out of the running package says every measurement row completes in
**under four guest seconds**; the whole of the time was one row that never
returned (§9.2). A bench that hangs on its final row looks exactly like a bench
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

## 10. What the plan has to change

Facts, not decisions — §16.1's prototype is where the look question gets
settled and the owner's eye is the gate.

1. **§1.1 gains a per-row term and loses "6.15 µs a byte" as a modelling
   constant.** The band cost is `arrival + rows × 52 + bytes × 3`.
2. **§1.1's `GFX_BLITP` row is wrong twice**: it is measured in this tree (Set
   108), and the estimate it carries is 7× low.
3. **§1.3's whole table doubles**, and "fps a feature" halves: 3.6 on
   fullscreen VGA, 4.4 windowed, 4.0 Hercules, 6.6 CGA.
4. **§3.4's "58% off every animation commit" is 34%.** The band still wins —
   it is still the cheapest decision in the renderer — but the saving is
   per-byte only, while the per-row term and the arrival are unchanged.
5. **§3.5 needs the pen's four paths**, and a rule: *ink over black, or pay up
   to 115%.*
6. **§3.5(b)'s `Banded` arm has a price: +920 µs a strip**, +37% for three.
7. **§3.5(c)'s `Rich` arm is refused on the 8088** — 14 frames for one board
   update — and survives only as a 386 arm.
8. **§3.9.1's projectile is 8.88 ms, not 5**, and the combat frame is 102% of a
   frame rather than 55%.
9. **§4.2.1's item bank should be interleaved** `data,mask,data,mask`: 14%
   off every composition for no disk and no new mechanism.
10. **§13.5's speaker estimate stands; its FM estimate is untested** and needs
    a machine with a card.

The lever the measurement points at is **rows, not bytes**. If §16.1's eye
wants the rate back, the cheapest place to find it is a **shorter** sprite —
56×40 is 24% off the band where 40×56 is 10% — and the second cheapest is
raising the 40% animation share, since the idle phase has little else to do.
