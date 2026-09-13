# An engine of its own for each aeroplane — CLEAR SKIES, costed

> **NOT STARTED. This is a COSTING, not a design that has been agreed**, and
> the prototype it is measured off was built, read and **reverted** — the tree
> is byte-identical to its baseline. Nothing below is in `build/`.
>
> **The headline is one number and it is not the one you would look for.**
> Clear Skies has **208 bytes** of growth headroom, not the 9,664 that
> `APP_MAX_SIZE` appears to leave, and the whole feature measures **109** of
> them. So it fits — and it spends **52% of everything the program has left**.
> That is the decision, and it is the owner's rather than an implementer's.

Measured on build 220 (`6ccb3d6`), `kern_big`, a plain `make`, on the
container box. Byte figures are exact and come off nasm listings; the cycle
figures for code that does not exist yet are **predicted** from PERFORMANCE.md
Part 2's table and are marked as such. The one cycle figure that is measured
is `OSAPI_SND_TONE`'s, and it was measured by somebody else on a real
instrument (PERFORMANCE.md Set 146).

---

## 1. What is being asked for, and what the machine will actually let it be

Five aeroplanes (SPEC.md 88.7). Four have engines; the **Wassmer Bijave** has
none and is excepted by the ask — correctly, and it is already silent, because
SPEC.md 88.7.6.1 took its throttle away when it was found that the *only*
thing reading it was the engine noise. Its sound is the variometer's swoop
(88.7.6.3) and nothing here touches it.

Today all four powered aeroplanes make **exactly the same noise**, and it is
three instructions of `cs_sound_step`:

```
    mov ax, [cs_thr]        ; 0..100
    or ax, ax
    jz .st
    add ax, 50              ; ...so the engine is 51..150 Hz, whatever it is
```

A Fouga Magister and an Icon A5 are the same tone at the same lever position.

### 1.1 The instrument is one square wave, and that is binding

`OSAPI_SND_TONE` is the whole of the sound tier a game can count on: **one
voice, no waveform, no volume** — `AX` = Hz and nothing else. Timbre is not
available, so "an appropriate engine sound" can only ever be a **frequency
law over time**. Two doors that look open are shut:

- **Bit-banging the speaker for a richer timbre is FORBIDDEN, binding.**
  SPEC.md 53.7: *"touching channel 2 or any §34.1-owned sound port directly"*
  is forbidden always inside an fsx bracket. There is no PWM engine note here
  and there cannot be one.
- **PCM is not a game loop's tier.** `OSAPI_SND_PLAY` is `PCM_EXCL` — it runs
  on your task **with the scheduler locked** and freezes everything for the
  length of the clip. A looping engine sample is not merely expensive, it is
  the wrong shape. `PCM_BG` streams need a sound driver and a feeder, and a
  frame here is 125–283 ms (88.12.1), which is an underrun per frame.

`OSAPI_SND_FM` is real and is legal in the bracket ("the snd slots" are legal
throughout, 53.7) — see §6. It is not the answer for the shipped machine.

### 1.2 The update rate is 18.2 Hz, and under load it is worse

`cs_sound_step` is called once per **simulation tick** from `.sim` in
`cs_fsx_main`, so the ceiling is the system tick: **18.2 Hz, 54.93 ms**.

It is a ceiling and not a rate. `cs_steps` caps the ticks a frame may owe at
`CS_MAXSTEP` = 3 **and discards the rest** — `[cs_last]` takes the current
tick either way. So on §88.12.1's `turnhold` frame (282.8 ms = 5.15 ticks) the
sim advances three ticks and **two are dropped**: the sound updates at an
effective **10.6 Hz** exactly when the picture is heaviest.

**This is what decides how much "character" is reachable**, and the arithmetic
is brutal:

| aeroplane | what a listener actually identifies | Hz |
|---|---|---|
| Cessna 172 | 2 blades × 2,400 rpm, and a 4-cylinder firing at 2/rev | **80** |
| Pitts S-2B | 6 cylinders firing at 3/rev, 2,700 rpm | **135** |
| Icon A5 | Rotax 912 firing at 2/rev, 5,800 rpm | **193** |
| Fouga | Marboré compressor blade pass | **kHz** |

A propeller's chop is **80–135 Hz** and the update rate is **18.2 Hz**. The
chop is four orders of magnitude out of reach as *modulation*, and the only
place it can live is as the **carrier** — which is what the existing 51–150 Hz
tone already is, by accident rather than by design.

So the honest shape of the feature is:

> **a per-aeroplane frequency law** (safe, cheap, exact), and optionally
> **a slow beat of a few Hz on top** (a stylisation, not a model, and the
> risky half).

---

## 2. The budget — and why `APP_MAX_SIZE` is a mirage here

`build/skies.bin` reports `image + bss` = **51,776** against `APP_MAX_SIZE`'s
61,440, which reads as 9,664 bytes of headroom. **It is not headroom, and it
is not even a variable.** `skies.asm`'s `OS88_BSS` is declared as

```
    OS88_BSS (CS_VOCAB_AT - (os88_image_end - $$)) + CS_VOCAB_MAX + CS_WLD_MAX
```

so `image + bss` = `CS_VOCAB_AT + CS_VOCAB_MAX + CS_WLD_MAX` — a **constant**,
independent of how big the program is. The prototype below grows the image by
109 bytes and `image + bss` is 51,776 on both sides. A gate reading that field
can never see this feature at all.

**The real budget is the GAP**, and the three-`times` construction at the end
of `skies.asm` exists to make it an assertion: the image, then the ZWORD bss
chain, then a **gap written as its own subtraction**, then the overlay at its
fixed address. Write the gap as one `times` and the ZWORDs would quietly
overlap the world vocabulary; written this way nasm refuses the file.

Read off the listing, this tree:

| build | image end | `CS_BSS` | **gap** |
|---|---|---|---|
| **shipped** | 0x7B91 (31,633) | 0x419F (16,799) | **0xD0 = 208 bytes** |
| `CSDIAG` (0xC200 tree) | — | — | 456 |
| `CSHZPROBE` (0xC200 tree) | — | — | 871 |
| `CSPROBE` (0xC200 tree) | — | — | **−167: DOES NOT ASSEMBLE** |

**208 bytes is the growth headroom for the image and the ZWORD chain
together** — for every future change to Clear Skies, not just this one.

### 2.1 The source comment says 1,444 and it is stale

`skies.asm`'s own note reads *"The gap is 1,444 bytes today, and it is the
growth headroom for the image and the ZWORD chain TOGETHER."* It is **208**.
Whatever has landed since spent 1,236 of it. That sentence is the one a reader
sizing a change would trust, so it is worth fixing whether or not this feature
is taken — it is the difference between a change that looks free and one that
spends half of everything left.

### 2.2 And the counting build is already over

`CSPROBE` — `make skiesprobe`, `tests/skiescount.py`'s instrument — is
**167 bytes over and does not assemble on this branch today**, before anything
here is added. This is precisely the failure SPEC.md 88.10.3 was written to
end (*"a package that cannot build its own instrument cannot be measured"*),
and it has come back for exactly the reason that section names: **nothing in
`all` builds it, so nothing in `all` can catch it.** `tests/skiescount.py` is
deliberately unregistered (`t_registry.py` carries the reason: *"an
INSTRUMENT, not a test"*), so no row goes red either.

**It is pre-existing and it is not this feature's to fix** — but it does bear
on the costing two ways: it is the arm with the least room, and a feature that
makes it *worse* should know it.

---

## 3. What it measures — a built and reverted prototype

The prototype follows the pattern the fleet already uses. `CSP_COCKPIT`,
`CSP_ATT` and `CSP_ART` each hang a per-aeroplane thing off the plane record;
this appends a fourth:

```
CSP_SND    equ 46          ; word: ITS ENGINE - the record below, or 0
CSP_SIZE   equ 48
```

**Appended and not inserted**, for `CSP_INDK`'s reason: `tests/skiesbody.py`
carries `CSP_PITCHR, CSP_TURNK, CSP_MAXROLL = 20, 24, 28` as literals, and an
insertion moves every field after it. Appending at 46 moves nothing.
`tests/skiesfleet.py` resolves its offsets off the guest and does not care.

An engine is seven bytes: base Hz, Hz added at full power, the beat's depth and
its wall-clock mask, and whether it follows the **lever** or the **spooled
thrust**. Four of them:

```
cs_snd_c172:   dw 55, 40      ; a direct-drive Lycoming: 55..95 Hz
               db 6, 3, 0     ; ...with a four-tick lump in it
cs_snd_pitts:  dw 80, 70      ; six cylinders and 260 hp: 80..150,
               db 10, 1, 0    ; and a hard bark every other tick
cs_snd_fouga:  dw 300, 900    ; two Marbore turbojets: a smooth 300..1200
               db 0, 0, 1     ; off the SPOOLED thrust
cs_snd_a5:     dw 90, 80      ; a geared Rotax revving high and turning a
               db 0, 0, 0     ; slow prop: 90..170, smooth
```

and the Bijave's word is **0**, which is the silence it already has.

### 3.1 The numbers, exact

`.text` only; `bss` is untouched; every figure is the gap moving, read off the
listing.

| | image bytes | gap after | share of the 208 |
|---|---|---|---|
| the record, the lookup, the scale (**base**) | **59** | 149 | 28% |
| …+ the jet follows its **spooled** thrust | **+30** | 119 | 14% |
| …+ the piston **beat** | **+20** | 99 | 10% |
| **all three** | **109** | **99** | **52%** |

Of the 109, **38 bytes are data** (four 7-byte records, five `CSP_SND` words)
and **71 are code**. Image 31,633 → 31,742.

The diagnostic arms after it: `CSDIAG` 456 → **347**, `CSHZPROBE` 871 → **762**
— both still assemble. `CSPROBE` goes −167 → −276, which is worse but was
already broken.

### 3.2 The disk cost is zero, measured

`build/skies.o88` is **44,229 bytes on both sides** — the body is a part and is
`OP_COMP`, the 109 bytes come out of a run of zeros that compressed to almost
nothing, and the part layout absorbs the difference. `build/apps360.img` stays
at **313 of 354 clusters**. No floppy in any of the four geometries gains a
cluster. Nothing has to come off a disk to pay for this.

### 3.3 The cycle cost is not the question, but here it is

`OSAPI_SND_TONE` costs **1,997 cycles = 418.4 µs**, measured (PERFORMANCE.md
Set 146). The added arithmetic is **predicted** from Part 2's table and the
8088's `max(clocks, 4.34 × bytes)` fetch floor — ~505 cycles a sim tick for a
piston, ~890 for the jet, the difference being one more `mul`/`div` pair.

Against §88.12.1's flown frames, at the worst case of three sim ticks a frame:

| | cycles a frame | µs | of a 164.5 ms cruise frame |
|---|---|---|---|
| the law alone, piston | 1,515 | 318 | **0.19%** |
| the law alone, jet | 2,670 | 560 | **0.34%** |
| the law **and the beat**, piston | 7,506 | 1,574 | **0.96%** |

**The beat is the only item worth naming, and it is not the arithmetic** — it
is that the beat re-issues the tone. `cs_sound_step` ends in
`cmp ax, [cs_tone] / je .out`, so steady flight costs **nothing** today. A beat
makes `[cs_tone]` change every tick, which is a 418 µs far call per sim tick
where there were none. It is still under 1% of a frame; it is simply the whole
of the new money.

---

## 4. What the money buys, per aeroplane

| | today | proposed | why that is the appropriate noise |
|---|---|---|---|
| **Cessna 172** | 51→150 Hz off the lever | **55→95**, a four-tick lump | 2 blades at 2,400 rpm is 80 Hz and a 4-cylinder fires at the same rate. The top is right; the bottom is raised because the real idle is 23 Hz and no PC speaker will say it |
| **Pitts S-2B** | identical | **80→150**, a bark every other tick | six cylinders firing 3/rev at 2,700 rpm is 135 Hz — higher and harder than the trainer, which is what a Pitts is |
| **Fouga Magister** | identical | **300→1,200**, smooth, off the **spool** | a turbojet is a high smooth whine, and the one thing a square wave *can* say about it is that it **lags the lever** — which SPEC.md 88.7.5 already models in `[cs_thracc]` and which nothing has ever been able to hear |
| **Icon A5** | identical | **90→170**, smooth | a Rotax 912 fires at 193 Hz through a 2.43:1 box onto a slow 3-blade prop: the highest-pitched and the smoothest piston here, and genuinely not a Lycoming |
| **Wassmer Bijave** | silent | **silent** | excepted, and already right (88.7.6.1) |

**The Fouga's row is the one that justifies the feature**, and it is the row
that is not merely a different number. `[cs_thracc]` is the thrust the engine
*has*, closing on what the lever asks at `CSP_SPOOL` = 5 — 95% in 5.3 seconds.
Reading it instead of `[cs_thr]` makes a jet sound like a jet for 30 bytes,
and it makes an existing, modelled, invisible mechanic audible. The other
three rows are a table.

---

## 5. The four risks, and one of them cannot be tested here

1. **The beat aliases under load, by construction.** The prototype takes the
   beat's phase off `[cs_last]` — the **wall clock** — rather than counting
   calls, which is 6 bytes and fixes the *period*. It cannot fix the
   *sampling*: at `turnhold` the frame spans 5.15 ticks and only 3 are
   stepped, so a `CSS_MASK` of 1 is sampled 3-of-5 and the tremolo goes
   irregular. A 4-tick mask suffers less. **A counted beat would go flat
   instead** — the engine would audibly sag in a banked turn, which is worse.

2. **The speaker's low end is not the emulator's low end.** A 55 Hz idle is
   near the bottom of what a real PC speaker will reproduce at any useful
   volume; an emulator synthesising a square wave has no such rolloff. So the
   two 1bpp machines will *sound fine under MartyPC and QEMU* and may be
   inaudible on the 5150. **This is a feature whose acceptance test cannot be
   run in an emulator** (docs/FIELD-MACHINES.md), and the tunable that settles
   it is `CSS_BASE`, one word per aeroplane.

3. **A beat may read as a fault rather than as an engine.** 9.1 Hz tremolo on
   a square wave is "rough", and it is equally "broken". This is a **look
   question with the project's standard answer**: it is a knob until somebody
   has listened. The cheap form is `CSS_BEAT` = 0 in all four records —
   shipping §3.1's first two rows and leaving the third assembled and inert.

4. **One silent regression in the sketch.** The prototype falls to `.st` with
   `AX = [cs_thr]` when `CSP_SND` is 0, where the old code guaranteed ≥51 Hz.
   Unreachable today (the glider's throttle never opens, 88.7.6.1) but wrong:
   it wants `xor ax, ax` on that arm, +3 bytes. Named here so it is not
   re-derived at a review.

---

## 6. The tier that is not recommended, priced anyway

`OSAPI_SND_FM` — OPL, 8 channels, real patches — is legal in an fsx bracket
and would give each aeroplane an actual timbre. It is refused here on three
counts, and the first is the one that settles it:

- **It is live only while `SOUND.DRV` is loaded**, which is not-wanted by
  default (SPEC.md 51.3). So it is a second implementation serving a minority
  of machines, and the `OSAPI_SND_TONE` path has to exist and be good anyway.
- **Nothing in `apps/` has done it for a game** — only `apps/frotz/zsnd.inc`
  uses FM at all — so it is new ground, not a lift.
- **It does not fit.** A patch is 11 bytes, a voice wants note-on/off and a
  pitch bend per tick, and the capability probe and the fallback are code on
  top. It would not be 109 bytes into a 208-byte gap.

Its one genuine attraction — a turbojet with a compressor whine on one channel
and a roar on another — is the Fouga's row, which §4 gets most of the way to
for 30 bytes.

---

## 7. What it would take, end to end

| | |
|---|---|
| `apps/skies/skies.asm` | `CSP_SND`/`CSP_SIZE`, the `CSS_*` layout. ~15 lines |
| `apps/skies/csworld.inc` | five `dw` in the fleet, four 7-byte records. ~20 lines |
| `apps/skies/csflight.inc` | `cs_sound_step`'s `.noswoop` arm. ~30 lines |
| `SPEC.md` | a new subsection under SPEC.md 88.8, and that section's *"pitch follows the throttle"* sentence is no longer true. **Write it before the change** |
| `docs/INDEX.md` | regenerate (`tools/os88index.py`) — a new plan file is a row |
| a test row | `skiessound`, soak. `tests/skiesfleet.py` already has `fly(row)` and reads records off the guest, so the row is that plus reading `[cs_tone]`: each aeroplane's law at three lever positions, the Bijave **0**, and — the assertion worth having — the Fouga's tone still **climbing** several ticks after the lever stops. ~80 lines, ~60–90 s declared |
| the listen | on the 5150, on the speaker, for risks 2 and 3. Not substitutable |

`make`, `make test-fast` (37 rows, 14 s) and `soak -k 'skies*'` are the gates.
Nothing outside `apps/skies/` and one SPEC section moves; no kernel byte, no
disk cluster, no other package.

**The doc gate will stop you** if the SPEC section is not written first —
`checkdocs.py` refused the prototype three times, once per call site, for a
heading that did not exist yet — which is the rule doing its job, and is why
the SPEC section is the first line of work and not the last.

---

## 8. Recommendation

**Take §3.1's first two rows — the law and the jet's spool, 89 bytes — and
leave the beat.** That is 43% of the gap rather than 52%, it adds no
`OSAPI_SND_TONE` calls at all, it has no aliasing behaviour to explain, and it
delivers the part of the ask that is a fact about each aeroplane rather than a
stylisation: four distinct engines, and a jet whose note lags the hand.

**The beat is 20 bytes and should follow a listen, not lead it** — build it,
leave `CSS_BEAT` = 0, and let the 5150 decide. That is also the cheapest way
to find out whether a 55 Hz idle is audible at all, which is the one question
in this file no box in this container can answer.

**And fix `skies.asm`'s "1,444 bytes" comment regardless of what is decided**
(§2.1). 208 is the number the next person sizing a change will be reasoning
against, and they will find it the way this file did: by being refused.
