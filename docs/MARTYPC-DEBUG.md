# The MartyPC debugger — an instrument the guest cannot feel

**What it is.** A remote debug server bolted into [MartyPC](https://github.com/dbalsom/martypc)'s
headless frontend, and a host client. It gives a process on your machine
memory, registers, I/O ports, breakpoints, single-step and cycle counts on a
running os8088, with **no code in the guest at all** — no driver, no UART, no
interrupt, not one guest cycle spent.

**Why it exists.** 86Box has no automation socket of any kind and a real 5150
has no debugger, so until this the only way to ask "what does the kernel
think" about a machine outside the container was to ask a human for a MartyPC
dump by hand (docs/FIELD-MACHINES.md). That document rates a dump the highest
instrument in the register — *"ask for a dump whenever the question is 'what
does the kernel think'"* — and it cost a menu click and a file transfer. This
is that instrument as a command.

**It is pinned and static, on purpose** (`tools/martypc/UPSTREAM`). A debugger
that changes under you is one more variable in a session whose whole point is
removing them; re-pinning is a deliberate act, not maintenance.

**Reach for this FIRST** when the thing under test runs on an 8088 with a CGA
or a Hercules — which is most of this OS. docs/TESTING.md carries the full
ordering; the short version is MartyPC, then QEMU for what it does not cover
(VGA, 286/386, sound, scripted input), then 86Box, then the 5150.

---

## The one thing it is not: a disk

**MartyPC is cycle-accurate. It is not disk-accurate.** It models the 8088's
instruction timing, its prefetch queue and its bus contention, and it does not
model a platter turning at 300 rpm, a head seeking, or a 2:1 interleave.
PERFORMANCE.md Set 11 measured the gap on the same test, the same kernel and
the same media:

| | real 5150 | MartyPC |
|---|---|---|
| read 16 KB, cold motor | **8.07 s** | **0.27 s** — 30x fast |
| boot | **38,886 ms** | **2,306 ms** — 17x fast |

So: **if a disk is anywhere in the path, the number this tool gives you is
wrong, and wrong by more than an order of magnitude in the flattering
direction.** That catches a great deal that is not obviously about disks — a
boot time, a package launch, a Tracker module load, a `SYSTEM.CFG` save, the
Control Panel closing. When any of those is the question, the instrument is
the machine in docs/FIELD-MACHINES.md and there is no substitute.

**It will not catch a disk CORRECTNESS bug either, and that is the sharper
half.** SPEC.md §18.91's `AL` bug is the worked example: `dsk_xfer` asked the
BIOS for nine sectors, the BIOS moved nine, and answered `AL = 1` — and the
kernel believed `AL` and re-read the rest one sector at a time. On the 5150
that was 148 sectors in 34 `int 13h` calls for a 32-sector file, 4.6x the
traffic, and it made the *batching optimisation measure slower than no
batching*. **The same binary on the same image under QEMU moved 34 sectors in
6 calls** — correct, fast, and completely silent about the bug. The boot
sector carried the identical bug for as long again and it took the 5150 plus
SPEC.md §18.94's counters to find either. An emulator's floppy controller
returns what its author believed the hardware returns; real hardware is under
no such obligation, and the whole class — `int 1Eh`'s parameter table, short
`int 13h` reads, BIOS interrupt stack depth — is behaviour an emulator smooths
over rather than reproduces.

Read that as a boundary on the tool, not a complaint about it: everything on
the CPU side agrees with the 5150 to within 0–4% across 45 of 47 `gfxbench`
rows, which is the closest any emulator has come here.

---

## Build and run

Needs `cargo` (Rust) and, on Linux, `libudev-dev` + `pkg-config` — MartyPC
depends on `serialport`, whose build script hard-fails without them.

```sh
tools/martypc/build.sh              # clone at the pin, patch, stage, build
cd build/martypc/run
MARTYPC_DEBUG_ADDR=127.0.0.1:9001 ./martypc_headless \
    --mount fd:0:media/floppies/os8088-360.img &

python3 tools/os88marty.py 127.0.0.1:9001 run
python3 tools/os88marty.py 127.0.0.1:9001 verify
```

`--mount fd:N:path`, not `floppy:` — the device word is `fd`, `hd` or `cart`.
Copy `build/os8088-360.img` into `build/martypc/run/media/floppies/` first.

**The machine starts PAUSED**, whatever `auto_poweron` says, and `run` starts
it. A debugger that attaches to a machine already millions of cycles into its
boot cannot breakpoint anything it wanted to watch, and "it had already
happened" is the one failure a debugger must not have.

---

## The three machines

`tools/martypc/configs/os8088_machines.toml` is appended to MartyPC's own
`ibm5150.toml` by `build.sh`:

| config | what it is |
|---|---|
| `os8088_5150_cga` | the default: IBM 5150, 8088 at 4.77MHz, 640K, CGA, real 1982 IBM BIOS |
| `os8088_5150_herc` | the same with MDA — MartyPC models Hercules as an MDA sub-mode, so SPEC.md §39.1's probe is what decides |
| `os8088_5150_cga_gla` | the same with GLaBIOS |

All three are shaped after docs/FIELD-MACHINES.md's calibration machine, as
closely as MartyPC allows.

**Use the IBM ROM for anything you will quote.** GLaBIOS is a modern
reimplementation and is optimised in ways the 1982 ROM is not, so its POST and
its `int 13h` are **not period timings** — it is the one to iterate against
and never the one to take a number from. The BIOS in `tools/martypc/roms/` is
the 27 OCT 82 `1501476` U33 part, which is the ROM the calibration machine
actually has; MartyPC identifies it by MD5 and the machine configs name that
ROM set explicitly rather than letting `auto` pick.

*(That ROM is IBM's. It is here because the repo's owner put it here, and it
is the one file in this tree not covered by the project's own licence.)*

---

## The protocol

Newline-delimited JSON over TCP, one reply per command. `tools/os88marty.py`
is the client — a CLI, a REPL and an importable `Marty` class.

| command | |
|---|---|
| `status` | exec state, cycles, instructions, CS:IP |
| `regs` / `setreg` | all sixteen-bit registers and flags |
| `read` / `write` | memory, by flat `addr` or by `seg`+`off` |
| `inb` / `outb` | I/O ports |
| `run` / `pause` / `step` / `reset` | execution |
| `bp` | breakpoints: `exec`, `execseg`, `mem`, `memseg`, `int`, `io` |
| `screen` | the video card's text, in text modes |
| `video` | which card, and whether it is in a graphics mode |
| `key` | a keypress by MartyKey name — `KeyA`, `Enter`, `ArrowRight` |
| `mouse` | one Microsoft packet: relative `dx`/`dy` and button state |
| `history` / `callstack` | the CPU's own instruction history |
| `quit` | stop the emulator |

Three things about it are load-bearing:

- **Reads do not perturb the machine.** Memory comes back through
  `BusInterface::peek_range`, which costs no cycles and triggers no MMIO. That
  matters more than usual here: MartyPC is cycle-accurate, and an instrument
  that costs cycles cannot measure a machine whose cycles are the thing under
  test. **I/O ports are the exception and say so** — there is no peek for a
  port, so an `inb` is a real bus read and several devices clear a status or
  advance a sequencer by being read at all.
- **`read` resolves MMIO, so video RAM reads like any other memory** — and
  getting that wrong cost an hour, so it is worth the paragraph. It went
  through `BusInterface::peek_range`, which slices the flat memory vector and
  does **not** resolve MMIO, so `0xB8000` returned whatever was in RAM under
  the card: a screen of zeroes, with no error to say so. A machine that had
  POSTed and printed `Disk Boot Fail. You monster.` looked, through `read`,
  exactly like one that had hung. `get_vec_at_ex` is the one to use — equally
  side-effect-free (it peeks a mapped device rather than reading it), a plain
  slice when the range touches no device, so ordinary reads cost what they
  did. `screen` is still the right call for **text** modes, because it asks
  the card for characters rather than making you decode them.
- **`bp` replaces the whole set.** A debugger that can only add breakpoints
  accumulates them until something stops for a reason nobody remembers asking
  for.
- **`execseg` and `memseg` are folded to flat addresses, because the
  segmented breakpoint types do not work.** `BreakPointType::Execute(seg,
  off)` and `MemAccess(seg, off)` are declared in `breakpoints.rs` and matched
  by **neither** CPU — grep `cpu_808x` and `cpu_vx0` for them and you get
  nothing, while their `*Flat` twins are handled in six places each. Passed
  through, they arm silently and never fire. That is measured, not inferred:
  on `0060:37F5`, os8088's timer hook, which executes 18.2 times a second,
  `execseg` never stopped and `exec` on the same address stopped immediately.
  Folding costs one property worth naming — a flat breakpoint aliases every
  `seg:off` pair reaching the same linear address — and on a real-mode 8086
  that is nearly always what was meant.
- **`reset` does not zero the cycle counter.** It is free-running for the life
  of the process, so every span is a delta. A "cycles" figure read straight
  out of `status` after a reset is the age of the emulator, not of the run.

---

## What it is for, and what it is not

**For:** anything on an emulator. `verify` is the one to reach for first —
it dumps `KERNEL_SEG` and diffs it against `build/kernel.bin`, which proves in
one command that the machine is running the build you think it is *and* hands
you every live variable at its listing offset with no instrumentation added.
Breakpoints answer questions that previously needed a knob kernel: an `int`
breakpoint on 13h counts disk calls on an **unmodified shipped kernel**, where
SPEC.md §18.94 needs `make DISKCNT=1` and a test package on the floppy.

**Screenshots, without leaving:** `os88marty.py shot out.png` reads the
framebuffer straight out of VRAM and decodes SPEC.md §39.3's banked layout —
the same arithmetic `tools/hercshot.py` applies to QEMU, so a picture from
either route is the same picture. **Do not start QEMU just to look at the
screen**: if MartyPC is already up, that is minutes of an agent's time for
something one command already answers. Verified against QEMU's CGA on the
same desktop: **60.0% lit in both**, 76,815 pixels against 76,809, and the
six-pixel difference is the clock — MartyPC reads `Jul 04 2026`, which is
SPEC.md §37.90's no-RTC fallback, correctly, because a 5150 has no CMOS.

The card is asked which it is (`video`), never sniffed: an unmapped `0xB0000`
reads as **zeroes rather than erroring**, so "is there something at the MDA
aperture" answers yes on a CGA-only machine. That guess shipped for about ten
minutes and produced a confident 720x348 image of nothing.

It is CGA and Hercules only, and that is a property of the format rather than
of the tool: both are 1bpp, so the bytes *are* the pixels. **Mode 12h is four
planes behind the Graphics Controller's Read Map Select** and is not readable
as flat memory at all — you would have to drive the latches to get a plane
out. Moot in practice, since MartyPC does not implement mode 12h either.

**Input, without a guest module and without QEMU.** This was the last thing
on the "go to QEMU for it" list, and it should not have been. `key` enters
the emulator's keyboard buffer, so the guest sees it through the 8255 and
int 09h; `mouse` builds a **real Microsoft 3-byte packet** and clocks it into
the serial controller, so the guest's own `mou_isr` decodes it. Neither needs
a byte of code in the guest, and both exercise *more* than a poke would — a
debug module writing `[mouse_x]` would skip the UART, the packet decoder and
SPEC.md §9.5's whole port contest, which is the code most likely to be wrong.
It is better than QEMU's `msmouse` on the same grounds: that one is not a
UART-level device and ignores DTR entirely (docs/TESTING.md).

Verified, and the proof is deliberately not a screenshot. `mou_seen` — the
byte SPEC.md §9.4.2 publishes, set by the mouse ISR only on a **complete
decoded packet** — goes 0 → 1 when packets are injected, and the chip menu
opens under a press-drag. For the keyboard, the test is SPEC.md §9.6: on a
machine whose mouse has not spoken, the arrow keys *are* the mouse, so ten
`ArrowRight` presses moved `mouse_x` from 320 to 350. That is the full path —
emulator buffer, 8255, int 09h, BIOS buffer, int 16h, `kbm_poll` — and it is
a path QEMU can barely reach, because there you would have to arrange for a
machine with no mouse.

`os88marty.py` wraps both: `key`, `type_text`, `mouse`, `mouse_move`,
`click`. Long moves are chunked because a packet carries a **signed byte**,
exactly as `tools/mouse.py` chunks for QEMU. `key` names a **MartyKey**
variant — `KeyC`, `Enter`, `ArrowUp`, `Digit1` — the emulator's own
vocabulary rather than a second mapping table here; a bare `'c'` is refused
rather than guessed at.

**The speed scaler is forced to 1.0 by the `mouse` command, and that is what
makes counting in pixels work at all.** MartyPC's mouse defaults to
`DEFAULT_MOUSE_SPEED = 0.25` — a human's acceleration preference — so an
unscaled `dx` of 60 reaches the guest as 15. A script that derives absolute
position the way `tools/mouse.py` does, by slamming into a corner and
counting from the kernel's own edge clamp, then lands **a quarter of the way**
to everything it aims at. Nothing errors: the pointer moves, the chip menu
opens under a press, and every click misses — which reads as a broken
hit-test rather than a scaled delta, and cost a round of debugging before it
was found. There is no TOML key for it in this build (`SerialMouseConfig`
carries only `type` and `port`, and `bus/mod.rs` passes `None`), so the fix
is at the command. In the **GUI** build the same knob is a runtime slider at
**Input ▸ Mouse ▸ Speed**, 0.10x–2.00x, defaulting to 0.5x.

**On 86Box, none of this exists** and the question comes back. There the
keyboard has a zero-code answer anyway — poke the BIOS buffer at
`0040:001A`/`001C`, which `int 16h` reads — and the mouse would need
`DEBUG.DRV` and a guest-side injection verb. Neither is built; both are
wanted only if 86Box automation is.

**Audio capture**, which headless MartyPC did not have at all — marty_core's
`sound` feature was not even enabled for the crate, so a device's samples
went nowhere. `MARTYPC_WAV=/tmp/cap` writes **one 16-bit PCM file per sound
source** at that source's own rate (`/tmp/cap.pc_speaker.wav`), no mixing,
because the speaker and a card run at different rates and answer different
questions. The format is what `tools/sndcheck.py` already parses, so every
existing assertion — RMS, the Goertzel dominant-frequency scan,
`--expect-silence` — works against a MartyPC capture unchanged. Verified by
programming PIT channel 2 for 880 Hz through `outb` alone, with nothing in
the guest involved: `sndcheck` reported **dominant 891.0 Hz**, inside its 5%
tolerance.

Two differences from QEMU's `-audiodev wav` are worth knowing. The capture is
**continuous**, not gated — QEMU's pcspk stream only runs while the speaker
is on, so its file time *is* speaker-on time and a silent boot yields an
empty file; here the file is guest time and silence is silence. And **the
guest is also driving port 61h**, so a tone you open by hand may be closed
again by `snd_tick` a moment later — which is why the run above shows 0.26 s
of clean tone rather than the three seconds it was held for.

**And there is a Sound Blaster now** — `devices/sblaster.rs`, added by our
patch, which was the one real gap left on an 8088. Upstream had `adlib.rs`
(an OPL2 via `opl3_rs`) and `dma.rs` but no DSP, so SPEC.md §34.5's stream
tier could only be reached under QEMU. The card is a DSP 2.01 by default at
`0x220`/IRQ 7 on 8-bit DMA channel 1:

```toml
    [[machine.sound]]
    type = "SoundBlaster"
    io_base = 0x220
    irq = 7
    dsp_version = [2, 1]
```

`dsp_version` is the interesting knob and it is there for one reason: it is
what the driver branches on. At `[2, 1]` os8088 takes the classic
`0x48` + `0x1C` auto-init path; drop it to `[1, 5]` and the same driver has
to re-arm the 8237 per half-buffer instead, which is a different code path in
`sb.inc` that nothing else can make it take. The SB16-only commands (`0x41`,
`0xC6`) are **refused rather than half-implemented**, which is honest: a card
reporting a DSP below 4.00 is a card a correct driver never sends them to.

What it models, in the order it matters: the reset handshake (write 1 then 0
at base+6, read `0xAA` at base+0xA), `0xE1` version, `0xF2` forced IRQ — which
is how a driver *finds* its line, so it fires with nothing running — `0x40`
time constant, `0x48` block length, `0x14`/`0x24` single-cycle and
`0x1C`/`0x2C` auto-init in both directions, `0xD0`/`0xD4` pause and continue,
`0xD1`/`0xD3` speaker, and `0xDA` exit-auto-init-at-the-block-boundary.
Reading base+0xE acknowledges the 8-bit IRQ, and a block completing while the
previous interrupt is **still unacknowledged is counted as a missed ack**
rather than hidden — the guest not keeping up is exactly the thing a
cycle-accurate card exists to show you.

It pulls its bytes through the real 8237 (`do_dma_read_u8`, the same call the
FDC makes) and resamples to the host rate through a carried fractional
accumulator, so a long stream does not drift. Verified three ways:

- **From outside the guest entirely** — buffer written straight into RAM,
  8237 channel 1 and the DSP programmed over `outb`, nothing in the guest
  involved. A 20,000-byte square at `tc=206` (20 kHz, period 20 samples) came
  back as **1.00 s, peak rms 0.7500, dominant 1000.0 Hz** — duration,
  amplitude and pitch all exact. The auto-init variant of the same test
  looped for **53.96 s of guest time** without drifting off 1000.0 Hz.
- **Through os8088's own driver.** The Drivers page loads `SOUND.DRV`, the
  probe finds the card, and the Sound page's third radio button — `Sound
  Blaster` — comes up selected. That is the whole discovery path: reset,
  version, the `0xF2` IRQ probe against four candidate lines with the
  driver's own stubs hooked, and the 8259 mask dance around it.
- **`tests/sbtest`, the gate package**, which is the assertion that counts.
  `g:00000 o:K` in its window and **2.00 s at dominant 1000.0 Hz** in the
  capture — byte for byte the figure `docs/TESTING.md` documents for QEMU's
  SB16. Its underrun leg is the sharper one: `st:1 c:02400` (underrun-paused,
  exactly the 2,400 granted bytes consumed) with **0.30 s of tone and then
  silence** — 2,400 bytes at 8,000 Hz to the sample, and nothing looping.

**One caveat, and it is the `0x10` command.** Direct DAC writes are accepted
and dropped rather than played. Nothing in this tree uses them — os8088's
driver is DMA-only — but a program that does will hear nothing and get no
error, which is the failure mode worth writing down rather than discovering.

**Not for:** the real 5150 — that is `DEBUG.DRV`'s job (SPEC.md §58), and the
two are complementary rather than competing. Also not for VGA: MartyPC's VGA
is in development and covers Mode 13h and Mode X, while os8088's whole VGA
path is **mode 12h**, so the CGA and MDA/Hercules configs are what work here.
That is a deferral, not a limitation of the tool — and it is the half QEMU
covers worst, so the split is a good one.

**And a number from it is still a number from an emulator.**
docs/FIELD-MACHINES.md's first rule is unchanged: a timing goes in
PERFORMANCE.md Part 9 labelled MartyPC, and a dump is evidence about *logic*,
never about time. On the CPU that labelling is a formality — it agrees with
the 5150 to 0–4%. On a disk it is the whole point. What is new is that this one is cycle-accurate for the CPU,
so `step` gives real cycle counts — 50 instructions measured 719 cycles on a
booted desktop, 14.4 cycles per instruction, which is the same class of
figure as PERFORMANCE.md Part 2's instruction floor.

---

## What was verified, and how

All of the following was run end to end in the container, against
`build/os8088-360.img` and the real 27 OCT 82 IBM BIOS:

- The BIOS date string read out of `0xFFFF5` as `10/27/82`, and the reset
  vector at `0xFFFF0` as `EA 5B E0 00 F0` — `jmp F000:E05B`.
- os8088 boots, twice: once from the development tree and once from what
  `build.sh` produces from scratch, with identical results.
- **Reset to the kernel's first instruction is 300,798,299 cycles**,
  23,586,325 instructions, 12.75 cycles each, on a 5150 with the 1982 IBM
  BIOS reading `build/os8088-360.img`. That is an exec breakpoint on `0x600`
  against a `reset`, which is the only honest way to ask it: the first two
  attempts *polled memory* every few seconds of wall clock while MartyPC runs
  faster than real time at a load-dependent rate, and got 81M and 313M cycles
  for the same event on the same machine — a 3.9x spread that was measuring
  when somebody looked.
  **It is a cycle count and NOT a boot time.** Dividing it by 4.772728 MHz
  gives 63.02 s, and that figure is worth nothing: a boot is mostly POST and
  floppy, and this tool is 30x fast on the floppy. The real machine's boot is
  PERFORMANCE.md's 38,886 ms and the only way to move that number is to
  measure it there. What the cycle count IS good for is a **delta** against
  another MartyPC run — that is how you tell whether a change to the boot path
  did anything, which is a question this can answer and the 5150 answers
  slowly.
- `verify`: **71,624 bytes dumped, 1,351 differing (1.89%)** in 183 runs, with
  `boot_ticks` reading 40 live against `0xFFFF` in the file — **byte-identical
  between the development build and `build.sh`'s**, which is the check that
  the vendored patch is the thing that was tested. For scale,
  docs/FIELD-MACHINES.md's hand-taken MartyPC dump was 1,353 differing of
  71,112 — the same instrument, automated.
- `regs` at the desktop: `cs=0060 ds=0060 ss=1260 sp=2228` — SPEC.md §1's near
  model on screen, CS = DS = `KERNEL_SEG` and SS = `LOW_SEG`.
- Breakpoints: an `int 08h` breakpoint fired three times in a row at
  `0060:37F5`, os8088's own tick hook.
- `step 50`: 50 instructions, 719 cycles.
- `screen`: GLaBIOS's POST panel read back in full, including its
  `RAM [ 256 KB OK ]`, `Video [ CGA ]` and `COM [ 03F8 02F8 ]` lines.

---

## Two upstream findings

Both are in `tools/martypc/patches/01-headless-debug-server.patch` and both
are worth offering upstream:

- **`peek_range` was off by one.** (No longer load-bearing for us — `read`
  uses `get_vec_at_ex` now — but still a real bug.) `if address + len < self.memory.len()`
  refuses a range *ending* at the last byte of memory — so
  `peek_range(0xFFFF0, 16)`, the reset vector paragraph and the most-read
  sixteen bytes in an 8088 machine, was refused while fifteen bytes at the
  same address succeeded. `<=`.
- **Two breakpoint types are dead code.** `BreakPointType::Execute(seg, off)`
  and `MemAccess(seg, off)` are in the public enum and no CPU matches on
  them — so a frontend that offers them offers controls that arm and never
  fire. This works around it (above); upstream should either implement or
  retire them. **A control that looks live and is not** is the sharpest kind
  of bug in a debugger, because it makes the *absence* of a stop look like
  evidence.
- **Headless mode never mounted floppies.** `--mount fd:N:path` is parsed into
  `config.emulator.media.floppy` and then nothing reads it — mounting is done
  by the eframe frontend's file manager, which a headless run does not have.
  So a headless machine always booted with empty drives, which GLaBIOS reports
  as `Disk Boot Fail. You monster.` and the IBM BIOS reports by dropping into
  cassette BASIC. Both look like a bad image rather than an absent one.

The server itself is the answer to the crate's own standing TODO — *"We don't
have any backend to run an event loop. If we want to actually run the emulator
now we need some way of controlling / stopping it."* A socket is both.
