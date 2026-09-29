# HANDOFF-V20-FREEZE - os8088 stops dead on MartyPC's NEC V20

**Status: OPEN, not investigated past the first look (2026-09-29).** Found on
branch `pcspeaker` while trying to measure the Video Player's speaker
headroom on a V20 (docs/plans/completed/SPEAKER-PCM-PLAN.md). Nobody has yet
said whether the fault is os8088's or MartyPC's V20 - that is the first
question, and section 5 is the cheapest way to answer it.

## 1. What happens

MartyPC's V20 twin of the 5150 hard-disk machine boots the 360 KB system disk
to the desktop's **menu bar and the A: and B: drive icons, and stops**:

- the **dock strip is never drawn** (the bottom of the screen stays blank), and
  a black column sits at the right edge, x ~705-712 of 720;
- the CPU is parked at ONE address, sampled 100 times out of 100:
  **CS = 0060h, IP = CA71h, linear D071h = `ico_stage` + 23h** - which is
  `.bss`, not code (below);
- **IF = 1** there, yet **`[ticks]` has stopped at 37** after ~40 guest
  seconds: the tick is not being counted, so either IRQ0 is not arriving
  (PIC masked / no EOI) or the machine is not in a state to take it;
- FLAGS read **7A92h**. Bit 15 is clear. On a V20, FLAGS bit 15 is **MD, the
  mode flag**, and clear means **8080 emulation mode** - entered by `BRKEM`
  (`0F FF`), left only by `RETEM`/`RETI`. A V20 in 8080 mode executing x86
  code runs garbage, which fits a machine parked on a data address.

The same image on the same machine with an 8088 (`os8088_5150_herc_hdd_gla`)
boots to a desktop in every row of the suite.

## 2. What `ico_stage` is

`kernel/icons.inc:1135`: `ico_ibuf` / `ico_stage` is ONE `.bss` buffer with
two names (SPEC.md 25.7.2) - the icon renderer's indexed-kind decode target
and X-slot record stage - and it is also **`font_run_x`'s glyph POINTER
table** (`font_rn_tab equ ico_ibuf`, kernel/font.inc:2179) plus its two edge
rows on kern_big. It holds data and pointers, never code: nothing in the tree
jumps into it on purpose. So by the time the CPU is there, control flow has
already gone wild. **The MD bit is probably a CONSEQUENCE**: wild execution
through data that contains `0F FF` puts a V20 in 8080 mode, where an 8088
would run `POP CS` and something else.

The last things drawn were the menu bar and two drive icons; the dock (an
icon row, `DOCK.DRV` on kern_big, SPEC.md 2.8) was next and never appeared.
So the icon path - `icon_draw_ix` / `icon_draw_x`, `ico_pass`, and the
buffer they share with `font_run_x` - is the first place to look, but it is a
lead and not a finding.

## 3. Already checked

- **`cpu_detect` (kernel/cpudet.inc) is clean on the V20.** Its FLAGS test
  writes bits 12-15 through `POPF`, which on a V20 is bit 15 = MD. FLAGS
  read **F206h at its entry and at `cpu_detect.out`** (a breakpoint at
  each): MD set, the V20 still in native mode. So the probe does not flip
  it. (`[cpu_tier]` was not read; a V20 should come out `CPU_8086`.)
- **`AAM`** - the V20 ignores AAM/AAD's immediate and always uses 10. Every
  `aam` in the kernel is the base-10 form (clock.inc, clockw.inc, files.inc,
  vidsel.inc), so that difference cannot bite. `AAD` does not appear.
- Resolving the IP: a kernel address must be resolved by LINEAR address
  through `os88sym.linear()` - resolved against `.text` alone, a `.cold`
  address comes back with a plausible wrong name (docs/plans/DISK-CPU-PLAN.md
  section 1). `ico_stage+23` is the linear answer.

## 4. How to reproduce

```sh
make deps && make && make marty     # the V20 profile is baked into
                                    # build/martypc/run by `make marty`
```

The profile is `os8088_5150_herc_hdd_v20_gla` in
`tools/martypc/configs/os8088_machines.toml`: `os8088_5150_herc_hdd_gla` with

```toml
    [machine.cpu]
    upgrade_type = "NecV20"
```

MartyPC accepts `NecV20` as an upgrade of `Intel8088` only
(`COMPATIBLE_CPUS`, marty_core/src/machine_config.rs). `os88marty.launch()`
with the default `boot=True` gives up at `settle`'s desktop gate after 360
guest seconds ("the os8088 desktop never appeared"), so launch it unsettled:

```python
import sys, os; sys.path.insert(0, "tools")
import os88marty, os88sym
m = os88marty.launch("build/os8088-360.img", apps="build/apps360.img",
                     machine="os8088_5150_herc_hdd_v20_gla", boot=False)
m.run(); os88marty.pace(m, 30.0)
r = m.regs(); print(r)                       # CS 0060, IP CA71, FLAGS 7A92
w, h, rgb = m.fbuf(None)                     # the menu bar and A:/B: only
os88marty.write_png_rgb("v20.png", w, h, rgb)
m.close()
```

## 5. Where to go next, cheapest first

1. **Is it MartyPC's V20 or os8088?** Boot the same image on a V20 somewhere
   else. 86Box offers the NEC V20 on its XT boards: one run, one photograph
   (86Box has no automation socket here - docs/TESTING.md). A desktop there
   says MartyPC; the same stop says os8088. MartyPC carries a V20 CPU test
   suite of its own (the `RUN_V20_CPU_TESTS` run configurations in
   `build/martypc/src/.idea/`), which is the other half of that question.
   The owner's second machine, a Toshiba T1100 Plus, is an 80C86 and not a
   V20, so it cannot settle this.
2. **Find the first wild transfer.** Breakpoints, not samples: a MartyPC
   `exec` breakpoint on `ico_stage` (linear D04Eh) and a few bytes past it
   catches the moment of arrival, and `m.regs()` then plus the stack (`SS:SP`
   words) says who came from where - a `ret` popping a wrong word, an
   indirect `call`/`jmp` through a table, or an `iret`. `BOOTMARK=1` (the
   Makefile knob) says which `kmain` call last returned, if it dies in boot.
3. **Differences between a V20 and an 8088 that os8088 could touch**, to
   check against what the first wild transfer turns out to be:
   - opcodes `60h`-`6Fh` alias the `Jcc` row on an 8088 and are 80186
     instructions (`PUSHA`, `BOUND`, `IMUL imm`, ...) on a V20;
   - `0Fh` is `POP CS` on an 8088 and a two-byte-opcode PREFIX on a V20
     (`0F FF` = `BRKEM`);
   - shift and rotate counts in CL: an 8088 uses all eight bits, an 80186
     masks to five - check MartyPC's V20 for which it does, then any
     `sh?/ro?/rc? reg, cl` whose CL can reach 32;
   - `SALC` (`D6h`) and other undocumented 8088 opcodes;
   - `DIV`/`IDIV` corner cases, and the flags `MUL` leaves;
   - the PREFETCH QUEUE: os8088 patches its own code in places (SPEC.md
     8.1.1's `NOSMC=1` discussion is one; `mp_stepi_set` in Tracker patches
     its mixer, but that is a package, not the boot). A store into bytes
     already in the queue behaves differently on a CPU that fetches at a
     different rate, and the V20 is faster.
4. **Then fix it on whichever side it is**, with a MartyPC V20 row once the
   profile boots: nothing in `tests/` runs a V20 today.

## 6. Why it matters

A V20 is the classic XT upgrade and the Video Player's heavier speaker paths
were aimed at one (SPEC.md 34.11.9). If os8088 itself does not run on a V20,
that is a real bug for anyone who swapped the chip. If it is MartyPC's V20,
the profile needs noting as unusable until MartyPC is fixed, and V20 numbers
must come from elsewhere.
