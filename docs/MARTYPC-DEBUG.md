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
| `screen` | the video card's text |
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
- **`screen` is not a memory read, and must not be one.** Video RAM is an MMIO
  region owned by the card; peeking `0xB8000` returns the flat memory
  *underneath* it, which on a machine whose card has never written through is
  a screen of zeroes. It does not error — it returns a plausible blank screen,
  which is the worst way to be wrong. This cost an hour: a machine that had
  POSTed and printed `Disk Boot Fail. You monster.` looked, through `read`,
  exactly like a machine that had hung with a blank screen.
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

**Not for:** the real 5150 — that is `DEBUG.DRV`'s job (SPEC.md §57), and the
two are complementary rather than competing. Also not for VGA: MartyPC's VGA
is in development and covers Mode 13h and Mode X, while os8088's whole VGA
path is **mode 12h**, so the CGA and MDA/Hercules configs are what work here.
That is a deferral, not a limitation of the tool — and it is the half QEMU
covers worst, so the split is a good one.

**And a number from it is still a number from an emulator.**
docs/FIELD-MACHINES.md's first rule is unchanged: a timing goes in
PERFORMANCE.md Part 9 labelled MartyPC, and a dump is evidence about *logic*,
never about time. What is new is that this one is cycle-accurate for the CPU,
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
- **Reset to the kernel's first instruction is 300,798,299 cycles — 63.02
  seconds of guest time**, 23,586,325 instructions, 12.75 cycles each, on a
  5150 with the 1982 IBM BIOS reading `build/os8088-360.img`. That is an exec
  breakpoint on `0x600` against a `reset`, which is the only honest way to
  ask: the first two attempts at this number *polled memory* every few
  seconds of wall clock while MartyPC runs faster than real time at a
  load-dependent rate, and got 81M and 313M cycles for the same event on the
  same machine — a 3.9x spread that was measuring when somebody looked.
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

- **`peek_range` was off by one.** `if address + len < self.memory.len()`
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
