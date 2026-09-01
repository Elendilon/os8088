# Task stack slots — where the bytes actually go, and what a class scheme buys

**Design not started.** This is a handoff. It exists because a session was
asked why a fresh boot with the sound driver off opens only **six** programs
that want a worker when `MAX_TASKS` is 8, and the answer — the idle task takes
one of the seven dynamic slots — turned into the larger question of whether the
per-task slice has to be as big as it is.

Every number below was measured on this tree under QEMU with the shipping
kernel, on the base that carries the `origin/main` merge. **QEMU counts work
exactly and cannot time it** (CLAUDE.md), and stack depth is work, so this is
the right instrument for everything here except the one correction §9 names.

---

## 0. The headline

**A task's slice is not sized by what the task does. It is sized by what
lands on it.**

An idle desktop's idle task — whose own footprint is at most 4 bytes — reaches
**82 of 384**. A package worker that does nothing but spin reaches **88**.
Six Bounce instances reach **92–106**. The Fractal's drawing worker reaches
**142**, which is the same figure docs/KERNEL-MEMORY.md recorded for it before
any of this.

So of the Fractal's 142, about 82 belongs to no program at all. It is the
interrupt floor, and **every task pays it simultaneously** — seven times over
in `sch_stacks`.

**The single largest item in that floor is the BIOS.** `sch_isr` chains to the
ROM's `int 08h` on every full tick, with `pushf` / `call far [sch_old08]`, and
that call runs the ROM's handler on whichever task stack it interrupted.
Measured by A/B on a bare desktop: **82 with the chain, 32 without it.**

**The BIOS timer chain costs 50 bytes of every task stack in the machine.**

---

## 1. What was measured, and how

`task_spawn` fills every slice with `0xCC` before it writes the canary and
carves the frame (§8.3), on the shipping kernel and not only a `KFZ=1` one, so
each slice carries its own high water. Three readers were used:

- `tools/stkwater.py` against a live QEMU. **Its `DEF` is `("KFZTRACE",)`**, a
  `KFZ=1` build, so `os88sym` refuses on a plain kernel and every reading here
  went through a five-line driver that passes no defines. That is a wart worth
  fixing when somebody is next in the file.
- `tests/stackprobe` — the package built for this. Its worker refills its own
  slice and then **spins**, so its reading is the floor plus its own two
  `OSAPI` calls and nothing else. It also reports every other slice.
- A word-by-word dump built on `stkwater.annotate()`, which names only the
  words a `call` actually ends at.

**The stress protocol matters and must be identical between arms.** A high
water is a sample of a nesting distribution, not a bound: an early
`NOBIOSTICK` run read 102 where the controlled re-run of the same build read
76. Every A/B below is 239 scans of the same scripted sweep — ten mouse
positions and ten keys, eight rounds — with the probe launched the same way.

### 1.1 The readings

| task | high water of 384 | above the floor |
|---|---|---|
| idle task (own footprint ≤ 4 bytes) | **82** | — it *is* the floor |
| `tests/stackprobe` worker (spins) | **88** | +6 |
| Bounce ×6 | **92–106** | +10…24 |
| Fractal drawing worker | **142** | +60 |
| Tracker streaming worker (docs/KERNEL-MEMORY.md) | 142 | +60 |
| `ETHER.DRV` service worker, QEMU after an FTP session | 232 | +144 |
| `ETHER.DRV` service worker, **5150 field**, upload + typing | 220 | — |

The idle task is the control that makes the rest readable. Its body is

```
    pushf / cli / cmp / sti / hlt / mov / popf / sti / call task_yield
```

and `task_yield`'s first two instructions are `pushf` / `cli`, so **the only
windows in which an interrupt can reach it leave it 2 or 4 bytes deep.**
Whatever it reads above 4 is not its own.

---

## 2. What is actually on the stack

Decomposed by A/B rather than by reading, because the dead region a high water
leaves is not contiguous with the parked frame and cannot simply be walked:

| component | bytes | how it was established |
|---|---|---|
| the interrupted task's own depth (idle) | ≤ 4 | source: `pushf` then `cli` |
| CPU frame + `sch_isr`'s nine register pushes | 24 | `SCH_FRAME`, source |
| `sch_switch`'s `push dx` / `push bx` / `call sch_account` | ~4 | source; `sch_account` is a leaf |
| **the ROM's `int 08h` chain** | **50** | bare desktop, 82 → 32 with the chain removed |
| the mouse path (`mou_isr` → `mou_apply` → `cur_move`) | ~58 | idle read 62 with the chain removed and the mouse driven |

Two ISR paths, and **they cannot nest on each other** — `mou_isr` runs with
IF=0 throughout and never `sti`s — so the floor is the deeper of them, not
their sum:

```
   floor today   = max(tick 28 + BIOS 50, mouse 58)  =  78, + own  =  82
   floor without the BIOS chain
                 = max(tick 28,           mouse 58)  =  58, + own  =  62
```

Ruled out along the way, each by measurement rather than argument:

- **`snd_tick`.** It calls `drv_svc_call` from inside the ISR, which looked
  like the deep one. Booting with no sound card at all changed the probe's
  reading by **zero** (88 → 88). With no driver loaded the call returns at its
  first test.
- **`sch_account`.** A leaf: no pushes, no calls. It costs the 2 bytes of its
  own return address.
- **The splash.** `sch_isr`'s `call far [spl_ifp]` was the first suspect for
  the idle task's residue, on the theory that the idle task is spawned early in
  `kmain` and the deep bytes were boot-time. `tests/stackprobe` refutes it: a
  worker spawned at the desktop, long after the splash is gone, reads 88.

---

## 3. Is there a common base? (yes, and it is bigger than the programs)

Every task carries the same two things, and neither is the program:

1. **24 bytes at the very base, by construction.** `task_spawn` carves
   `SCH_FRAME` at the top of the slice for every task alike.
2. **The interrupt floor, ~82 bytes,** which any task can be made to pay at any
   moment because interrupts land on whichever stack they interrupt.

The program's own contribution is the *small* term for everything except the
network stack: **+6** for a spinning worker, **+10…24** for a Bounce, **+60**
for the Fractal. `ETHER.DRV`'s **+144** is the outlier and is what actually
sets `SCH_STACK` today.

That is the finding that governs the rest of this document. Shaving a program
is worth its own bytes once. Shaving the floor is worth its bytes **seven
times**, and is the difference between the small classes in §6 being possible
and being arithmetic.

---

## 4. What is compressible

### 4.1 The ROM tick chain — 50 bytes × every slot

`kernel/sched.inc`, in `sch_isr`:

```nasm
.full:
    pushf                       ; chain: BIOS ticks its count and sends EOI
    call far [sch_old08]
```

One call, made from the deepest-nesting context in the kernel, costing more
than everything around it put together. The fix is the classic one and is
**cheap because SS never changes** (§2.1 — every task runs `SS = LOW_SEG`): a
private stack for the chain needs `SP` swapped and nothing else.

```
    save SP -> a word;  SP = the shared chain stack's top
    pushf / call far [sch_old08]
    SP = the saved word
```

Six or seven instructions around the one call. What it buys: the 50 bytes stop
being per-task and become **one shared allocation**.

**And it has a re-entrancy problem that must be designed, not waved at.** The
ROM's handler sends the EOI and then typically `sti`s to call `int 1Ch`, so a
second IRQ0 can arrive while the first chain is still running, re-enter
`sch_isr`, and switch to the *same* shared stack. Two ways out, and they are
not equivalent:

- **A busy flag that falls back to the task stack.** Safe and simple — but the
  worst case is then still 50 bytes on a task slice, so **no class in §6 may be
  sized below it** and the change buys speed and RAM but not the floor.
- **A busy flag that skips the chain** (EOI only, as the sub-tick path at
  `sch_isr`'s `.tick` already does for its own reason). Bounds the floor for
  real, at the price of the ROM's tick count losing an occasional increment
  under a load that is already a tick behind.

**The second is the one that makes the small classes possible, and it is a
behaviour change somebody has to agree to.** It is the central open question
of this plan.

### 4.2 The mouse ISR — 54 bytes, and it moves for 21

**Measured, not estimated.** `make STKDIAG=1 MOUPRIV=1` runs the whole mouse
ISR on a stack of its own and reads its high water off it: **54 bytes**, on
QEMU, after 45 seconds of continuous movement.

Of those 54, only **six** have to be on the interrupted task's stack — the
FLAGS/CS/IP the CPU pushed before we had control. Everything after that can be
somewhere else, because the swap needs no register:

```nasm
    mov [cs:mou_psave], sp      ; 2E 89 26 xxxx   5 bytes
    mov sp, mou_pstack + MOU_PSTK   ; BC xxxx     3 bytes
```

`mov [cs:x], sp` and `mov sp, imm16` both work with nothing to spare, which is
what makes this possible at all at an interrupt gate where every register
belongs to the interrupted task. CS is `KERNEL_SEG` at the gate, so the save
slot is reached before DS is ours; SS is already `LOW_SEG` for every task
(§1/§2.1), so the private stack lives in `.lowbss` and the swap is SP alone.

**It needs no re-entrancy guard, and that is a property rather than a hope.**
`mou_isr` runs with IF=0 from the CPU's gate to the `iret` and never `sti`s
(§7/§9), so it cannot interrupt itself, and IRQ3 and IRQ4 cannot interrupt each
other. §4.1's chain needs a busy flag precisely because a real BIOS `sti`s
inside it; this one does not. `mou_eoi` is the single exit — one `iret` in the
whole ISR — so there is exactly one place to swap back.

**The cost, counted off the listing rather than estimated:**

| | bytes |
|---|---|
| `.text` — the 8-byte entry at **both** vectors, plus a 5-byte restore | **21** |
| `.bss` — the saved SP | 2 |
| `.lowbss` — one shared 256-byte stack (4.4× the measured 54) | 256 |
| **removed from every task slice** | **48** |

**The entry is duplicated on purpose**, and it is the duplication this document
was told to spend if it helped: there are two vectors and the swap has to
happen before the first `push`, so the eight bytes are written twice. Sixteen
bytes of `.text`, once, against 48 bytes of every task stack in the machine —
seven times over today and seventeen under §7.

### 4.2.1 The two fixes compose, and not additively

The ROM's `int 08h` handler sends the EOI and then `sti`s before `int 1Ch`, so
**IRQ4 can arrive inside the tick's chain** — and when it does, one task stack
carries `sch_isr`'s frame *and* the ROM's chain *and* the whole mouse ISR at
once.

That is the 130-byte excursion §10.3 caught: 24 (`SCH_FRAME`) + 4 (the idle
task's own) + ~50 (the ROM) + 54 (the mouse) ≈ 132. It is rare — three
controlled 45-second runs since have peaked at 84, 88 and 84 — which is exactly
why it must be designed for rather than sampled for. **Either fix removes the
product case**, and both together leave `sch_isr`'s own 28.

### 4.2.2 Why relocation and not compression

Compressing the 54 in place was priced and is the worse trade:

- **24 of it is the entry frame** — the CPU's 6, `push bx`, and eight more
  registers the body genuinely uses across a call into the drawing layer.
- **`mou_byte` already tail-`jmp`s to `mou_apply`** rather than calling it, so
  the obvious flattening is done and cost nothing.
- The remaining ~26 is inside `cur_move`'s drawing chain, and shortening that
  means restructuring the graphics layer for less than the 48 that 21 bytes of
  `.text` buys outright.

**And the earlier refusal still stands, because it is a different change.**
§4.2's predecessor refused moving `cur_move` *out* of the ISR — that would cost
the ISR-paced pointer that docs/SCHED-IDLE-PLAN.md §6.3 rests on. Running the
same ISR, drawing included, on a different stack changes no behaviour at all.

### 4.2.3 A size pass makes this worse, not better

`origin/claude/kernel-size-optimization-*` rewrites `kernel/mouse.inc` by ~500
lines and `kernel/sched.inc` with it. **A size optimisation that factors common
code into shared helpers makes stacks deeper** — every new call is two more
bytes of return address on every path through it — so the 54 above is a
measurement of the tree it was taken on and wants re-taking when that lands.
`MOUPRIV=1` is what makes the re-take one boot rather than an argument.

### 4.3 What is not compressible

`SCH_FRAME`'s nine register pushes are the context. There is nothing to win
there and an attempt would only move where it is spent.

---

## 5. The idle task's own stack (Q3)

Its own footprint is ≤ 4 bytes (§1.1), so what it needs is the floor plus
margin, and nothing else. Against this project's convention of ~1.75× the
measured figure:

| idle stack | floor today (82) | floor with §4.1 taken (62) |
|---|---|---|
| 128 | 1.56× — **too thin**, and thinner still on iron (§9) | 2.06× — **viable** |
| 192 | 2.34× — **viable today** | 3.10× — comfortable |
| 256 | 3.12× | 4.13× |

So the answer to *"192 now, 128 if we find real compressibility"* is
**exactly that, and the compressibility is §4.1's**. 128 is not safe against
today's floor and is safe against §4.1's — which is the same sentence as "128
depends on the ROM chain moving off the task stack, in its bounding form".

**It does not free a slot on its own.** The slot and the slice are separate
resources: `task_spawn` allocates a `sch_tasks` record and *derives* the slice
from its index, so moving the idle task's stack out leaves `sch_tasks[1]`
occupied and the worker count still six. Getting the seventh back needs
`MAX_TASKS` 8 → 9, and that is an ABI change — `apps/os88api.inc` mirrors the
constant and it sizes `SS_TSTATE`, `SS_TCYC` and the `SS_INST` offset, hence
`SYS_SNAPSHOT_SIZE`, so every `.o88` is rebuilt. There is no way round it: the
Task Manager's meter reads the idle bucket out of the snapshot, and the header
has no spare byte to name it another way (§20.6, and the `SS_TSTATE` comment in
the SDK).

---

## 6. Pre-declared slot classes (Q4), and the canary

### 6.1 The canary gets simpler, not harder

Today `sch_switch` derives the slice base from the slot index with an 8-bit
multiply and a shift — about 75 clocks, and a `%if SCH_STACK == 256` special
case beside it for the arrangement that no longer ships. Variable sizes make
that arithmetic impossible, which is the objection; the answer is that the
arithmetic should not have been there in the first place.

**A per-slot base table replaces it.** `sch_stkbase: resw MAX_TASKS` — 16 bytes
of `.bss` — and the canary check becomes an index and a compare:

```nasm
    mov bl, [sch_cur]
    xor bh, bh
    shl bx, 1
    mov bx, [bx+sch_stkbase]
    cmp word [ss:bx], SCH_MAGIC
    jne sch_stkdie
```

Cheaper than what is there now, shorter, and it deletes the 256-byte special
case and the `SCH_STACK % 128` guard with it. **The canary is not weakened at
all** — `SCH_MAGIC` still sits at the bottom word of every slice, still written
by `task_spawn`, still compared on every switch away.

The four instruments that derive the same base independently — the `KFZ` deep
sampler in `sch_isr`, `tests/stackprobe`, `tools/stkwater.py` and
`tools/kfzread.py` — all read kernel symbols already, so they read the table
too. A parallel `sch_stksize` byte table (8 more bytes) is what lets them
report a size they did not assume. **That is the whole cost of the exception**,
and it is worth saying plainly that the comment at `sch_switch`'s canary
records two of those instruments having already read garbage once by deriving a
base the wrong way — a table is what stops that class of bug, not what invites
it.

### 6.2 Fragmentation is avoided by partitioning, not by allocating

Variable-size slices handed out and given back will fragment. The cheap answer
is a **fixed partition** — the classes exist as slices from boot, a spawn takes
the smallest free slice that is big enough, and a refusal is
`OSAPI_TASK_SPAWN`'s existing CF=1, which §20.6 already requires every package
to degrade on and retry. No allocator, no compaction, no new failure mode.

A package declares its class in its header, which is a header-version change of
the shape `.DRV` version 4 already was. **A package that declares nothing gets
the largest class**, so nothing existing has to be touched to keep working.

### 6.3 What the classes have to be

Sized from §1.1's readings, not from round numbers:

| class | fits | on today's floor | on §4.1's floor |
|---|---|---|---|
| 128 | the idle task; a spinning service worker | no (1.5×) | yes |
| 192 | Bounce, Timer, most simple workers | yes | yes |
| 256 | Fractal (+60), Tracker (+60) | tight | yes |
| 384 | `ETHER.DRV` (+144), ftpd | yes | yes |

**The Fractal is the case that stops the class list being shorter.** At +60
over a floor of 82 it needs 142 and a 192 slice gives it 1.35× — thin by this
project's standards. On §4.1's floor it needs 122 and 192 gives it 1.57×.
`ETHER.DRV` stays at 384 either way; it is the reason `SCH_STACK` is 384 and
nothing here changes that.

---

## 7. What it buys — and the goal is SLOTS, not saved bytes

**The requester's framing, and it changes the arithmetic:** anything freed here
is to be spent on **more task slots**, not returned to the heap, and the budget
for `sch_stacks` may grow to about **3,072 bytes** (from 2,688 today). The
target is to settle this once — a slot count nobody has to come back to.

That makes the floor the whole game, because the floor is what every slot pays:

```
   slots that fit  =  budget / (floor + the deepest program in that class)
```

`sch_stacks` is 7 × 384 = **2,688** today, and one of those seven is the idle
task's, so **six are usable**.

| | `.lowbss` | usable worker slots |
|---|---|---|
| today | 2,688 | **6** |
| classes only, idle external at 192 | 2,048 | **7** |
| **§4.1 taken, classes on the lower floor, 3,072 budget** | **3,008** | **17** |

The bottom row is the one to aim at, and it is arithmetic on measured numbers
rather than a hope. With the ROM chain off the task stack the floor measured
**38** (§10.3), so above it a Bounce needs ~62, the Fractal ~98 and
`ETHER.DRV` ~182:

| class | fits | slices | bytes |
|---|---|---|---|
| 128 | the idle task, Timer, Bounce, most simple workers | 12 | 1,536 |
| 192 | the Fractal, Tracker | 4 | 768 |
| 256 | `ETHER.DRV`, ftpd | 2 | 512 |
| the shared chain stack (§4.1) | — | 1 | 192 |
| | | **17 usable + idle** | **3,008** |

**Seventeen against today's six, inside the stated budget.** The 1.75× margin
this project sizes stacks with is kept throughout: 128 against a 100-byte
Fractal-class worst case is 1.28×, which is why the Fractal is in the 192 class
and not the 128 one.

**What binds after that is not RAM, it is the ABI.** `MAX_TASKS` is mirrored in
`apps/os88api.inc` and sizes `SS_TSTATE` (one byte per task) and `SS_TCYC`
(four), so `SYS_SNAPSHOT_SIZE` grows **5 bytes per slot** and every `.o88` is
rebuilt. Going 8 → 18 is +50 bytes of every package's snapshot buffer and one
flag day. That is the decision to take deliberately, and taking it once is
exactly the "not coming back to this" the requester asked for.

**Design for bytes, never for rungs** (CLAUDE.md) — none of the above is quoted
as a rung and the ledger position is whoever takes this on to report with
`kernsize`.

## 8. Refusals

- **Moving `cur_move` out of the mouse ISR.** §4.2.2, and it still stands: it
  costs the ISR-paced pointer that docs/SCHED-IDLE-PLAN.md §6.3 rests on.
  Running the *same* ISR on a different stack (§4.2) is a different change and
  is not refused — it changes no behaviour at all.
- **Shrinking `SCH_FRAME`.** §4.3.
- **Deleting the idle task.** It is what `sch_switch` picks where it used to
  resume the outgoing task, and with a `ui_task` that can sleep that fallback
  would resume a sleeper. It can be moved off a worker slot (§5); it cannot be
  removed.
- **An allocator for the slices.** §6.2 — a fixed partition has no
  fragmentation and no new refusal path.

---

## 9. What must be measured on the 5150 before any of this is built

**One standing claim in the tree is contradicted by §2 and has to be settled
first.** docs/KERNEL-MEMORY.md's "Task stacks" says SeaBIOS services its
interrupt entries on an internal stack, "so under `make test` the only foreign
frames a task slice ever carries are this kernel's own tick and mouse
handlers". The A/B in §2 says otherwise: removing `call far [sch_old08]` moved
a bare desktop's idle reading from 82 to 32, so **50 of those bytes are the
ROM's handler on our stack, under QEMU.**

That matters twice over. It means the floor is bigger than that paragraph
implies, and it means the **+46-byte QEMU-to-5150 correction quoted beside it
may be double-counting** — a real ROM's `int 08h` will cost a different number,
not the QEMU number plus a constant. Nobody can size a 128 class until the two
are separated.

`tests/stackprobe` is the instrument and it already reads every slice. The run
wanted is the one its own header describes — hold keys, mash the mouse, play a
module — on the machine, with and without a package that spawns a worker, and
the number to bring back is the idle task's line and the probe's own.

---

## 10. The measurement disk — `make stkdiag`

**Built, and it answers §9 on any machine.** `STKDIAG=1` (`kernel/stkdiag.inc`)
is a kernel that measures itself and draws the answer on the desktop, in all
three geometries, with **no package to launch and nothing to click**. That is
why it is a knob: a package would need a double-click, and the double-click
lands inside the quiet phase it would be perturbing.

### 10.1 How the ROM number is taken

`sch_isr`'s `pushf` / `call far [sch_old08]` is replaced by `sd_chain_call`,
which fills a private 512-byte stack in `.lowbss` with a sentinel, **swaps SP
to it** (SS is already `LOW_SEG` for every task, so it is an SP swap and
nothing else), runs the chain, swaps back, and scans down for the first
surviving sentinel byte. What came back scrubbed is what the chain cost.

**No task stack is touched**, which is what makes it safe to ship to a machine
nobody here can debug. Two earlier designs sentinelled the free bytes below SP
on a task stack instead; the first took zero samples (on a desktop the tick
lands on task 0, not the idle task) and the second left the panel half drawn.

**It runs on alternate ticks.** Measuring every chain on the private stack would
make the floor a lie — it becomes the floor of the machine §4.1 *proposes*, not
the one that ships. So odd ticks are measured and even ticks run plainly on the
task stack where the `0xCC` fill records them. Both numbers on the panel are
then true of the kernel they describe, **and the difference between them is what
§4.1 is worth on that machine.**

### 10.2 What the operator does

Three phases on a wall clock, 90 seconds in total, with a five-second **HANDS
OFF** window before each reading is taken:

| | | |
|---|---|---|
| 0–30s | `QUIET — TOUCH NOTHING` | needs no operator at all |
| 30–55s | `MOVE THE MOUSE NOW` | |
| 60–85s | `HOLD DOWN A KEY` | |
| 90s | `DONE — WAIT 2 MIN, THEN PHOTOGRAPH` | |

A phase nobody performs reads equal to the one before it, which is a reading
and not a hole — and **the quiet phase, the one that matters most, is the one a
human cannot perturb.**

**`FLOOR MAX` is the row to quote.** The high water is a sample of a nesting
distribution, not a bound: on QEMU the quiet phase latched 84 while the machine
was still climbing to 130 a minute later. The MAX row only rises, which is why
the panel asks for two more minutes before the photograph.

On an emulator nothing needs photographing: the same values are published in
§57's registry as `SD` and `tools/stkdiagread.py` prints them.

### 10.3 What it reads here, and the cross-check that validates it

QEMU/SeaBIOS, one 95-second run:

```
ROM int08 chain          56
floor  quiet             84
floor  +mouse            84
floor  +keys             86
FLOOR MAX                130
chain samples taken     1146
```

**56 is the independent confirmation of §2's A/B.** That A/B removed `pushf` +
`call far [sch_old08]` and moved a bare desktop from 82 to 32 — 50 bytes. This
measures the same chain including the 6 bytes of `pushf` and the far call's own
frame that the A/B also removed: **50 + 6 = 56**. Two instruments, different
mechanisms, agreeing to the byte.

And it demonstrates the fix at the same time: with every chain on the private
stack the floor fell **82 → 38**, which is §4.1 working, measured, on a machine.

## 11. Instruments, and one wart

- `tests/stackprobe` — the probe. Its worker spins, so its reading is the floor.
- `tools/stkwater.py` — reads the fill back. **Its `DEF` defaults to
  `("KFZTRACE",)`**, so it refuses on a shipping kernel with "the map describes
  a DIFFERENT kernel"; it wants a defines argument.
- `tools/stkdepth.py` — static, and **it is not usable on `kernel/kernel.asm`**:
  its linear walk runs past routines that end in `iret` or fall through, and it
  reported `snd_tick: 0 bytes` and an 84-byte chain for the leaf `sch_account`.
  It works as documented on a driver or package `.asm`. Every kernel-side
  number in this document came from an A/B on the machine instead.
- A temporary `NOBIOSTICK` A/B — replacing the ROM chain with a bare EOI — is
  what priced §4.1. It is **not** proposed as a shipped knob: it stops the ROM's
  tick count advancing and changes motor timeout, so it is a measuring tool and
  its stressed readings are indicative only. §4.1's own busy-flag form is the
  shippable shape.
