# Saving and restoring machine state — research

**The question.** Can an agent dump MartyPC's whole state at a chosen point —
say when a watched value changes — reload it later, and continue from there, so
that a test starts from a *known* state rather than from whatever a fresh boot
and two minutes of clicking happened to produce?

**The short answer.** Yes, and the cheapest route needs no emulator change at
all, because **the emulator is already bit-exact deterministic**. That is the
result everything below turns on, so it was measured first rather than assumed.
What snapshots buy on top of it is not correctness but *time*.

Nothing here is built. This is the research and a recommendation.

---

## 1. What is already there

**No save-state support in MartyPC 0.4.2** (our pin). `marty_core` has no
serialize/restore path for the machine; the only files mentioning "snapshot"
are the keyboard modules, about something else. `serde` is a dependency but no
device struct derives `Serialize`, and only the PIC derives `Clone`.

**Memory watchpoints work**, which is half the request already answered. A
watchpoint on the BIOS tick counter stopped the machine within three seconds:

```sh
python3 -c "... m.breakpoints([{'type':'mem','addr':0x46C}]); m.run()"
#  -> state=breakpoint  cs=0060 ip=3124
```

`bp` takes `exec`, `execseg`, `mem`, `memseg`, `int` and `io`. So "stop when a
monitored value is touched" is available today; what is missing is only the
dump-and-reload either side of it.

---

## 2. The foundation: the emulator is deterministic

Two **independent processes**, same config, same floppy, an exec breakpoint on
the kernel's first instruction:

| | port 9911 | port 9912 |
|---|---|---|
| cycles at the breakpoint | 261,943,446 | 261,943,446 |
| instructions | 21,436,400 | 21,436,400 |
| SHA-256 of the whole 1 MB | `95c3eee02b541b52` | `95c3eee02b541b52` |

And it stays exact **through injected input**, which is the part that was not
obvious. Clearing the breakpoint, stepping a fixed 200,000 instructions,
injecting a keystroke, and stepping again:

| stage | cycles | instructions | memory |
|---|---|---|---|
| +200k | 264,816,109 | 21,634,476 | identical |
| inject `KeyA`, +200k | 267,591,794 | 21,834,469 | identical |
| +200k | 271,138,679 | 22,021,672 | identical |

Every figure matched across both processes. **Given the same starting image and
the same inputs at the same guest positions, MartyPC produces the same machine,
bit for bit.**

### 2.1 …and a wall-clock client destroys it

This is the sharp edge, and it is not a defect in the emulator. The same two
processes, free-running, paused after an identical `sleep(22)`:

| | port 9941 | port 9942 |
|---|---|---|
| cycles | 420,699,609 | **398,980,749** |
| memory | `94e91ca4dccf153f` | `d4d7e46e5598c604` |

**21.7 million cycles apart — 4.5 seconds of guest time — from one sleep.** The
emulator runs at ~3.8x real time and the host scheduler does not divide itself
equally between two of them, so a wall-clock wait lands at a different guest
position in each. Everything downstream diverges.

Two consequences, and the second is about work already in this tree:

- **Any replay must position its inputs in GUEST time** — cycles,
  instructions, frames, or a breakpoint — and never in `time.sleep`. The
  `flicker`/`pace` protocol already has this discipline (inject while paused,
  advance by frames), which is why those measurements repeat.
- **`tools/…/mdrive.py`'s navigation is wall-clock paced and is therefore NOT
  reproducible run to run.** Every scripted click in this session landed at a
  different guest position each time. It is fine for *driving* a machine to a
  state a human would recognise, and it is not a way to arrive at the *same*
  state twice. That is worth knowing independently of snapshots: it is the
  likeliest reason a measurement moves slightly between sessions.

---

## 3. What a snapshot would have to cover

`Machine` owns `cpu: CpuDispatch`, and the CPU owns the `BusInterface`, which
owns everything else:

- `memory: Vec<u8>` — the bulk, 1 MB
- ~25 optional device slots: `pit`, `pic1`/`pic2`, `dma1`/`dma2`, `ppi`,
  `serial`, `parallel`, `fdc`, `hdc`, `xtide`, `jride`, `mouse`, `ems`,
  `fantasy_ems`, `cart_slot`, `game_port`, `adlib`, `sblaster`, `sound_source`,
  `sn76489`, `a0`, `keyboard`, plus `videocards`
- machine-level counters: `cpu_cycles`, `cpu_instructions`, `system_ticks`,
  `kb_buf`, `events`

**Much of the `BusInterface` is derived, not state**: `timing_table`, `io_map`,
`mmio_map`, `desc_vec`, `cycles_to_ticks` are all built from the config at
construction. A restore should *rebuild* them by constructing the machine
normally and then overwriting only the mutable parts — that is a large
reduction in what has to be serialized, and it removes the whole class of bugs
where a saved lookup table disagrees with the config it came from.

**The serialization blockers**, counted across `devices/`, `bus/` and
`cpu_808x/`: `Instant` in 1 file, `Sender<…>` in 5, `File` in 4, `Box<dyn …>`
in 5, `Arc` in 2. Each needs `#[serde(skip)]` plus a re-attach step on load —
the audio channels in particular are live endpoints owned by the frontend, not
state.

**The floppy images are mutable state too.** os8088 writes `SYSTEM.CFG`, and a
snapshot that restores RAM but not the disk image restores a machine whose disk
has moved on. Either the images go in the snapshot or a restore must re-mount
them from a pristine copy.

---

## 4. Three ways to do it

### A. Deterministic replay — zero emulator work, available now

Record every input with the **guest position** it was delivered at; to restore,
boot a fresh machine and replay the log to that position. Correct by §2.

- **Cost per restore:** 18.5 s wall to a settled desktop (71 s of guest time at
  3.8x real time), plus the replay of whatever navigation the state needed.
- **Strength:** no emulator change, no format to get wrong, and it reaches *any*
  point — including one you did not think to snapshot.
- **Weakness:** the deep states are the ones worth iterating on, and they are
  the expensive ones. Getting to "Tracker fullscreen playing a module" took
  ~2 minutes of scripted clicking and a 50-second module load. Paying that per
  iteration is the whole problem.

### B. `fork()` snapshot — instant, exact, in-memory

At the snapshot point the emulator forks; the child blocks, holding a
copy-on-write image of the entire process — every device, the CPU, all memory,
bit for bit, with **no serialization code at all**. Restore hands control back
to a re-fork of the child.

- **Viability confirmed:** the headless path spawns **no threads** (the only
  `thread::spawn` calls are in `cpu_test`, which we never run), so `fork` has
  no threading hazard.
- **Cost:** the debug server's TCP listener is the one awkward part — simplest
  is for the restored child to bind a new port and have the client reconnect.
  Perhaps 100–200 lines.
- **Weakness:** in-memory only (gone when the process exits), Linux-only, and
  a chain of snapshots is a chain of live processes.

### C. Serde snapshot to a file — the "real" feature

Derive `Serialize`/`Deserialize` across the CPU and the ~25 devices, skip and
re-attach the blockers, and rebuild the derived tables on load.

- **Strength:** persists across runs and across machines. A state could be
  committed, shared, or attached to a bug report.
- **Cost:** the largest of the three by a wide margin, and it lands in
  `tools/martypc/patches/`, which is carried against a pinned upstream — the
  patch is ~700 lines today and this would multiply it.
- **The risk that matters:** a snapshot missing one field restores a machine
  that looks right and is not. That is the exact failure shape this tree keeps
  getting bitten by — `peek_range` returning zeroes rather than erroring, the
  VGA reporting `graphics: false`, the cursor flattering `pace`. A partial
  snapshot would be the worst of them, because everything downstream inherits
  it silently.

---

## 5. Recommendation

**Do A now and B if the iteration cost justifies it. Do not start with C.**

A is available today at zero cost and is *definitively* correct — §2 is the
proof, not an argument. The discipline it needs (inputs positioned in guest
time) is one this harness should adopt regardless, because §2.1 shows the
current navigation helper is not reproducible without it.

B is the upgrade that actually addresses the complaint. It is instant, it is
exact for the same reason a process image is exact, and it needs no format —
which means it cannot be *subtly* wrong, only obviously broken. The threading
check above is the main thing that could have ruled it out and did not.

C is a real feature and a poor first move: the most work, carried against a
pin, for the one benefit (durability) that neither A nor B provides but that
nothing in the current workflow has actually asked for. If it is wanted later,
the honest way in is to build C's *verification* first — restore a snapshot and
diff the full machine against a replayed one, using §2's determinism as the
oracle. A snapshot format that cannot be checked against a known-good state is
a snapshot format nobody should trust.

### What to build first, concretely

1. **A guest-time input log in `os88marty.py`** — every `key`/`mouse` call
   records the cycle count it was delivered at, and a `replay` helper re-drives
   them by stepping to those positions. This is small, useful on its own, and
   it is A.
2. **Re-pace `mdrive.py` on frames rather than `time.sleep`**, so scripted
   navigation becomes reproducible. Independent of snapshots and overdue.
3. **Then** `fork` snapshot/restore in the debug server, verified by diffing a
   restored machine's full 1 MB and cycle count against a replayed one.

---

## 6. Measured facts, for anyone re-costing this

| | |
|---|---|
| boot to settled desktop | **18.5 s wall**, 71 s guest, **3.8x real time** |
| two processes to the same breakpoint | 261,943,446 cycles, identical 1 MB hash |
| divergence from one 22 s wall-clock sleep | **21.7 M cycles** (4.5 s guest) |
| memory watchpoint latency | fired within 3 s on a 18.2 Hz counter |
| devices to cover | ~25 slots + CPU + 1 MB + 3 machine counters |
| serialization blockers | `Instant` x1, `Sender` x5, `File` x4, `Box<dyn>` x5, `Arc` x2 |
| threads in the headless path | **none** |
