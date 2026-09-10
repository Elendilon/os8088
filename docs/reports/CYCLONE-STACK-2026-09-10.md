# Cyclone's stack overflow, reproduced — and the Sound Blaster is the term

**Taken 2026-09-10 at `f11398f`.** MartyPC, `os8088_5150_herc` and
`os8088_5150_herc_sb` — an IBM PC 5150 on the genuine `27 OCT 82` ROM,
Hercules 720, differing in **one thing**: whether a Sound Blaster 2.0 is in
the machine. docs/FIELD-NOTES.md 40 is what this is about.

## 1. Two things had to be fixed before it would reproduce at all

**The repro was never in the game.** Cyclone's title screen says
`PRESS ENTER TO START`; the script pressed Space, and sat on the title for
the whole of every run. **Every Cyclone stack figure this branch quoted before
today is the title screen's depth** — including the "114 of 192, flat" in
docs/FIELD-NOTES.md 40.2.1, which is why that document could not find its
missing bytes. The reporter's procedure names the step (*"Enter game"*) and
the script skipped it.

**And no machine here could host the question.** Seven MartyPC machines carry
a Sound Blaster and **every one is CGA or VGA**, so a 1bpp adapter with a card
in it did not exist. `os8088_5150_herc_sb` is that machine.

## 2. The A/B

The reporter's own procedure: boot, open B:, open `CYCLONE.O88`, **press
Enter**, hold Right + Space. Three paired trials, 30 s of held keys each.

| | slot 4 (`cy_worker`, 192 bytes) | outcome |
|---|---|---|
| Hercules, **no card** | **164 / 192** — three runs, identical to the byte | **survived 3/3** |
| Hercules, **SB 2.0** | 184, 188 sampled before the panel | **PANIC 3/3**, at 12 s, 10 s, 23 s |

The panel: `STACK OVERFLOW  TASK 04  SP 172C`.

**The card is the term.** The walk is deterministic and already at **85%**
with nothing else on the machine; the driver supplies the last 28 bytes.

## 3. The two SPs are the same event at two moments

Slot 4 runs **5,974 … 6,166** on this build (`sch_stacks` + the SPEC.md 8.7
class table: 128,128,128,192,…).

| | SP | where |
|---|---|---|
| the field panel | `0x1788` = 6,024 | **50 bytes ABOVE the base** — the excursion had unwound by the time `sch_switch` looked |
| this repro | `0x172C` = 5,932 | **42 bytes BELOW the base** — caught mid-excursion, in slot 3's bytes |

Both are the same overflow; `sch_diepanel` prints the **parked** SP, so
whether it reads healthy is a matter of when the check landed. That is why
docs/FIELD-NOTES.md 40.2.0 could decode a *healthy* SP off a machine that had
just died.

## 4. The mechanism, from the source rather than from the shape of the result

An SB 2.0 carries an OPL2, so `drivers/sound/sound.asm`'s attach publishes
**both** halves (lines ~113 and ~136):

```
    mov word [snd_services+DSV_TONE], opl_tone     ; the OPL leg
    mov word [snd_services+DSV_TICK], sbl_tick     ; the SB leg
```

and both are entered **from inside IRQ 0, at IF = 0, on whichever task slice
the tick interrupted**:

- **`DSV_TICK`** — `drivers/os88drv.inc`: *"near proc called from `snd_tick` —
  INSIDE IRQ0, at IF=0."* It runs **every tick, whether or not anything is
  playing**, so it is a constant addition to every slice. This is the term
  the idle floor sees: stkdiag reads the floor **32 without a card and 52
  with one** (docs/reports/STKDIAG-PC5150-2026-09-10.md), and slot 1 during
  Cyclone reads **70 against 78**.
- **`DSV_TONE`** — `kernel/snd.inc`'s `snd_tone_out` replaces a *near tail
  jump* to `spk_tone` with `push bp / drv_svc_call` — **a far call into the
  driver** — and its own comment says the path is *"Reached from `snd_tick`'s
  expiry path, so this can run INSIDE IRQ0 at IF=0."* Cyclone fires a tone
  every few frames (`cy_sfx` → `OSAPI_SND_TONE`), so expiries are frequent and
  **asynchronous to the walk**.

That second one is why the symptom keeps changing. Where in the walk chain an
expiry lands is a race, so identical starts panic at 12 s, 10 s and 23 s — and
a clean panic, a corrupted screen and a hard reboot are **three landing sites,
not three bugs**. An 8086 has no fault to triple, so the reboot is simply
execution reaching `F000:FFF0`.

**A correction to this branch's own earlier account:** it was written up first
as an *IRQ 7 DMA completion*. It is not — Cyclone plays no stream, and the
card's IRQ is not in this path at all. It is IRQ **0**, the driver reached
through two service pointers that are null on a machine with no card.

## 5. What this does not settle

- **Which of the two service calls dominates.** `DSV_TICK` is constant and
  `DSV_TONE` is the race; the A/B above turns both on together. Publishing one
  and not the other would separate them, and `snd_route` (SPEC.md 34.8) may be
  enough to do it without a build.
- **The fix.** Nothing here proposes one. The candidates docs/FIELD-NOTES.md
  40.2 already lists are unchanged, and the honest framing is now *`cy_worker`
  runs at 85% of its class with no card in the machine*, which is a margin
  question and not only a driver question.
- **The 128 class.** `tests/unit/t_stkclass.py` reads `cy_worker` at 1.28x,
  the thinnest in the tree, since GFX-EMBEDDABLE-PLAN's wave 5 took it
  66 → 86 bytes. 164 of 192 measured is the same statement from the machine.

## 6. How to re-take it

```sh
python3 - <<'PY'   # or any script; the shape is what matters
# boot os8088_5150_herc_sb, ui.path("B:/GAMES/CYCLONE.O88"),
# m.key("Enter"), then hold:
#   m.key("ArrowRight", down=True, up=False)
#   m.key("Space",      down=True, up=False)
# ...and read stkwater.water() over sch_stacks each pass. Slot 4 going
# None IS the panic: the task record is gone.
PY
```

`os8088_5150_herc_sb` needs the period ROM, so it goes through
`os88marty.machine(name, why_ibm=…)`; without a reason it resolves to
`os8088_5150_herc_sb_gla` and the run is a different machine.

The box: 4-core Xeon @ 2.10 GHz, two MartyPC instances at a time.
