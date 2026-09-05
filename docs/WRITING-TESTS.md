# Writing a test for this tree

The suite is `tools/os88test.py` over the registry in `tests/suite.py`, and
`tools/os88soak.py` runs the whole of the soak tier in parallel
(docs/plans/SOAK-PARALLEL.md). This file is how to add a row without
reinventing what already exists, and without producing one of the four
failures that keep recurring: a `secs` nobody measured, a `builds=True` where
`wants=` or a private tree was the answer, a hand-rolled click at a remembered
coordinate, and a `time.sleep` that hands the guest less work under load.

docs/TESTING.md is the other half — what each emulator *can* show — and
docs/MARTYPC-DEBUG.md is the instrument's manual.

---

## 1. Before anything: can this row FAIL?

Write the failing case first. It is the only question that decides whether the
row is worth having: a red row gets investigated and a green one does not, so
a row that cannot fail is worse than no row.

Two rows sat green for months doing nothing. `dispcp` is a LIBRARY imported by
over a hundred test files; registered as a soak row it booted nothing,
asserted nothing and reported `ok` in 0.1s against 60 declared. `mkclick` is a
GENERATOR — it writes `build/click.mod`, a metronome for judging A/V sync by
ear — and reported `ok` in 0.0s against 10. Both are in `t_registry`'s
`UNREGISTERED` map now, with the reason.

The runner reports `UNDERRAN n% of its declared Ns` for a row that returns in
under 5% of its declaration (for declarations of 5s or more), which catches the
crudest version. It does not catch a row that boots a machine, drives a session
and then compares something that is true either way.

**So: break the thing on purpose and watch the row go red.** Comment out the
kernel line, poke the byte, feed the wrong fixture. If you cannot make it fail
in five minutes, the assertion is not about what you think it is.

The corollary is the positive control. `lzfence` is the model: hostile streams
that must be REFUSED, and a decoder that refuses everything passes all of them
— so a valid stream runs first and its twelve bytes are compared one by one.

---

## 2. Which tier

| tier | budget | what belongs there |
|---|---|---|
| `fast` | **30s, enforced** | host-side only: read what `make` just built and check an invariant that breaks silently. Runs as part of every `make`. |
| `full` | **600s, enforced** | the pre-merge gate. `fast`, plus the build configurations `all` never builds, plus a CURATED handful of emulator rows. |
| `soak` | **none, deliberately** | everything else. Where a row goes when it is worth having and does not fit the gate. |

The budgets are `BUDGET` in `tools/os88test.py`, and the runner FAILS a tier
that overruns one.

A `full` row earns its place with **breadth per second**: `bootsmoke` is about
twelve seconds for a boot to a desktop on both 1bpp adapters, and fails for
almost any serious regression, wherever it was. A row that can only fail for
one narrow reason belongs in `soak`, next to the change that would break it.
Ten minutes is about eight emulator rows, not fifty.

`soak` having no budget is not an oversight. A budget there would push rows out
of the suite, which is the opposite of the point.

---

## 3. The row

```python
Row("lzmod", "soak", py("tests/lzmod.py"), 30.0,
    "SPEC.md 20.14.5: BEVERLY.MOD, COMPRESSED, opened by a double-click. "
    "... All 116,085 bytes are compared BYTE FOR BYTE, because a decoder "
    "that got one match wrong across the boundary still opens a window, "
    "still shows the title, and still plays - it plays a click",
    needs=("marty",), serial=True,
    wants=("build/lzmod360.img",)),
```

| field | rule |
|---|---|
| `name` | what `-k` matches (an `fnmatch` glob). Short, and the same as the script where there is one. |
| `tier` | §2. |
| `cmd` | `py("tests/x.py", "--flag")`. Run with `cwd=ROOT`, so paths are ROOT-relative. |
| `secs` | **measured**, not guessed. §4. |
| `why` | what breaks if this row goes red, with the § that owns it. Written for somebody who finds it failing in a year and does not know what it was defending. |
| `needs` | capabilities, PROBED not configured: `marty`, `qemu`, `nasm`, `cc`, `wiredisk` (`capabilities()` in the runner). A missing one SKIPS the row, and a skip is the box declining to answer — never a pass. |
| `serial` | it drives an emulator. The runner keeps those in their own lane, `--marty-jobs` wide (default cores−1); the host-side rows fan out ahead of them. Forgetting it puts an emulator row in the host lane, where it competes with every other row on the box. |
| `wants` | build artefacts this row OPENS that `make all` does not produce. §5. |
| `builds` | it shells out to `make` and writes `build/`. **You almost certainly do not want this.** §5. |
| `alone` | its ANSWER needs the cores — a rate, a frames-per-second, a millisecond redraw. Not the same claim as `builds`. §4.1. |
| `timeout` | defaults to `max(60, 4 × secs + 30)`, generous on purpose — it is there to stop a hung emulator eating the tier, not to police a slow box. Raise it for a row whose *shape* is slow, never to paper over a wait. |

---

## 4. Declaring `secs`: measure it

**Run the row and write down what it took.** That is the whole procedure, and
it is skipped constantly. The compression family arrived declaring 2,721
seconds for fourteen rows that take 701 — every declaration honest when
written, against a shape where the row's own cost was two full builds, and
none revisited when that stopped being true.

A wrong declaration is not cosmetic. `secs` is what the runner schedules by,
what `--resume` prices a restart against, what the ETA is computed from, and
what `timeout` is derived from. A row declaring 600 and taking 30 makes the
soak's own estimate useless, and a row declaring 30 and taking 600 gets killed.

* The runner reports `(declared Ns)` when a row exceeds **2× + 1s** (`SLIP`),
  which is there to catch a row that got 3× slower, not to police a loaded box.
* It reports `UNDERRAN` below **5%** (`UNDER`), which is there to catch the row
  that ran nothing.
* Between those two it says nothing, so the number is yours to keep honest.

Include a private tree's build if the row builds one — a cold tree is ~40s on
this container — and measure the rest warm, which is what it costs on every
run after the first.

### 4.1 `alone` is about cores, not the tree

A row whose assertion is a RATE cannot share four cores with two other guests.
That is not flakiness, it is the wrong measurement. `saverate`, `deskbench`,
`wirefps`, `uilat` and `curdisk` carry it.

Everything else should NOT: guest cycle counts, `disk()` counts and pixel
comparisons are exact at any oversubscription, because they are counted rather
than timed. If your row needs `alone` and is not measuring a rate, what it
actually has is a host-clock wait — see §7.

---

## 5. Never build in `build/`

`builds=True` is **three** rows (`buildmatrix`, `ctoolchain`, `fdlgthumb`).
Do not add a fourth without reading this section and deciding it applies to
you.

The hazard is reproducible in about twenty seconds: three rows that pass 3/3
against a frozen tree pass **0/3** against `build/` with a `make VIDEO=cga`
loop running, all three dying with *"the map describes a DIFFERENT kernel"*.
One row's mid-run `make` once cost a soak nine rows in a four-minute window.

There are exactly two legitimate needs, and each has its own answer.

### 5.1 A fixture: `wants=`

An image, package or driver under `tests/` that `make all` does not build.
Declare the PATH; the runner builds every declared artefact before any row
starts, when nothing else is running. An artefact that will not build is a
capability gap: the rows that named it SKIP, and the rest of the run goes on.

```python
    wants=("build/lzmod360.img",)
```

and in the script:

```python
from os88fixture import need
need("build/lzmod360.img")       # `all` builds nothing under tests/
```

`need()` is a no-op when the runner already built it, and under the runner an
UNDECLARED target is a hard error naming the row — because `need(DISK)` and
`need(a.apps)` are as common as a literal, and no static check can see through
them.

Make the Makefile own the dependency graph. A fixture embeds the SDK, so one
cached against an earlier kernel is a stale-scratch-disk trap (a stale
`build/c64.bin` once survived a cherry-pick and `c64part` failed "not
byte-identical", which reads as a broken package); make's rules already name
those includes as prerequisites.

### 5.2 A different KERNEL: `os88build.tree()`

A knob build, `kern_small`, a `COMPRESS=` or `PKGZ=` set — anything where the
kernel under test is not the shipped one.

```python
import os88build

t = os88build.tree("NOPLANE=1").apply()          # builds, or reuses
with os88marty.launch(t.img("os8088-360.img"),
                      apps=t.img("apps360.img")) as m:
    ...
```

`tree()` builds into `build/trees/<knob>-<hash>/` (default targets
`os8088-360.img` and `apps360.img`; pass `targets=` for others) under a
per-tree `flock` held across the build and no longer. Two rows with different
knobs never meet; two with the same knob share one tree and the second waits
only for the first's BUILD. `build/` is never written, so a person can `make`
in the checkout while a soak runs.

Four things to get right:

1. **`.apply()`, not `env=`.** `os88marty.launch` takes no `env` argument — the
   emulator needs no environment, the SYMBOL READER does. `t.env` is for a
   subprocess you spawn yourself; inside one process `apply()` sets os88sym's
   module default *as well as* the environment, and that second half is what a
   row cannot do for itself: library helpers that take no `defines`
   (`no_saver` resolving `ss_idle`, `Marty.sym` resolving whatever it is asked)
   go to the module default. Setting only `OS88_BUILD` fails exactly where the
   row is not looking — `blitcut` died inside `no_saver`, three frames below
   its own code.
2. **Never restate the nasm defines.** A knob's make VARIABLE and its nasm
   DEFINE differ (`VGADIRTY=1` compiles `-DVGA_DIRTY`), and a name without its
   value re-assembles a different kernel. `tree()` asks `make -n` for them.
3. **`plain()` is the other arm of an A/B**, and it resolves through
   `$OS88_BUILD` — so under a frozen run the control arm reads the run's tree
   and not the operator's directory.
4. **`make -n` is not a dry run of the PARSE.** `$(VIDSTAMP)`'s rule deletes
   `$(BUILD)/kernel.bin` and every boot sector when the knob set differs, so a
   `make -n` with a knob in it pointed at `build/` is a DESTRUCTIVE command.
   This is also why `os88fixture.need()` may not be called from a knob gate.

### 5.3 Check whether you need a build at all

Ask what actually differs before reaching for a tree. Four of the eight
compression rows that shipped with `builds=True` needed nothing but the
shipped kernel and a fixture: `lzmod-lzb` built a whole kernel under a knob to
test the LZB decoder, and the shipped kernel carries both decoders (SPEC.md
20.13.6), so the two arms came out byte-identical and the only real difference
was which format the FIXTURE was wrapped in.

### 5.4 Reading `build/` from the host: `os88build.at()`

A row that opens a shipped artefact on the HOST — to compare it against what
the guest holds — must resolve the path:

```python
plain = os88drv.image_unwrap(open(os88build.at("build/ramdisk.drv"), "rb").read())
```

`os88marty.launch` and `scratch_disk` already do this for the paths they are
handed, and `os88sym` honours `$OS88_BUILD`. With the variable unset `at()` is
the identity function, so an interactive run is unchanged. Without it, under a
frozen soak, a row asserts about one build's fixture and boots another's.

---

## 6. Driving the machine: `tools/os88ui.py`

**Start here, not at the mouse.** Every position is resolved from the guest's
own live tables and every verb is CONFIRMED by reading guest state.

```python
import os88ui

with os88ui.boot("build/os8088-360.img", apps="build/apps360.img") as ui:
    w = ui.path("B:/APPS/CALC.O88")       # drive, folder, package - all checked
    ui.menu_pick("Calc", "Close")
```

The drive prefix matters on a fresh boot: without one, `path()` starts from
the ACTING Disk window, and there is none until something has opened one.

The verbs: `open_drive`, `open`, `path`, `window`, `wait_window`, `windows`,
`titles`, `front`, `raise_window`, `move_window`, `drag_window`, `close`,
`uncover`, `clear_desktop`, `disk_window`, `listing`, `entry`, `scroll_to`,
`menus`, `menu_pick`, `toast`, `wait_toast`, `fs_of`, `settle`. `ui.m` is the
Marty and `ui.mo` the mouse, so dropping a layer needs no second connection.

Three rules make it worth using:

1. **Nothing is aimed at a remembered coordinate.** `dsk_vtab` says which zone
   a drive owns, `wm_wins` where a window is, the staged listing which row a
   name is on, `menu_bar[]` where a menu title sits. A layout change moves them
   all at once. A row number is not a file: SPEC.md 19.4 sorts by name, so a
   folder that gains one entry renumbers every row after it.
2. **Every verb confirms by reading guest state**, which is FASTER than
   settling — polling `wm_wins` is a 408-byte read against a whole framebuffer.
   The cheap thing and the correct thing are the same one.
3. **A verb that cannot confirm RAISES**, naming the step and what it saw. The
   failure is reported where it happened rather than twenty steps later wearing
   the costume of the feature under test.

Measured (`tests/uilayer.py`): the same three-step navigation is **0.35×** the
host time and 0.35× the guest cycles of the settle-and-hope spelling.

`boot()` also does the two things scripts forget — it turns the screen saver
off (five GUEST minutes of no input is reachable in a wide lane, and what a row
then compares is a black screen; `saver=True` keeps it for a row whose subject
it is) and resolves an IBM machine name to its GLaBIOS twin unless the row
makes a case in `why_ibm`. A row that calls `os88marty.launch` directly gets
neither, and one that hardcodes an IBM ROM name runs on a box that has it and
silently not on one that does not.

**The mouse under it is `tools/os88mouse.py`** — absolute, closed-loop, reading
the cursor back rather than dead-reckoning, with `dblclick` as a verb of its
own. `tools/os88mouserel.py` is the RELATIVE one and is for a short list: the
mouse itself under test, a bit-exact replay, or motion with no destination (a
paint stroke, a window drag). A dead-reckoned click that misses raises nothing.

### 6.1 When a hand-rolled click is right

Rarely, and always for a stated reason:

* the widget is not a window, a menu or a listing row — a Control Panel radio
  button, a scrollbar arrow, a game board cell. Derive the position from the
  window rectangle and the layout constant, never from a screen coordinate;
* the row IS testing the pointer, the driver or the packet stream;
* QEMU, where `os88ui` does not run (`tests/dispcp.py` keeps a blind path for
  exactly that).

Even then, confirm afterwards by reading the state the click was supposed to
change.

---

## 7. Waiting: the guest's clock, never the host's

**`time.sleep` in a row holding a Marty is a defect.** `time.sleep(2)` means
"give the guest whatever two seconds of this box buys today" — on this
container that is 9.6 guest seconds idle and 2.4 with the box full. The same
test hands the machine four times less work under load and fails further on,
looking like the thing under test.

That is the soak's central finding (docs/plans/SOAK-PARALLEL.md 1): twelve
rows at width 1 and at width 3 with two extra CPU hogs were 1.06× slower and
12/12 passed in both arms, while the same waits cost the guest up to **37%
less work**. **Contention does not make a row slow, it makes it LESS
THOROUGH** — which is why wall times never show it.

Four tools, in the order to reach for them:

| want | use |
|---|---|
| a specific thing to HAPPEN | `os88marty.until(m, cond, what, poll=…, guest=N)` |
| guest state to STOP CHANGING | `os88marty.quiesce(m, read, guest=…, stable=…, budget=N)` |
| the SCREEN to stop changing, before a pixel comparison | `os88marty.settle(m)` |
| time to pass, and nothing else will do | `os88marty.guest_sleep(m, N)` |

All four anchor their deadline to the emulator's own cycle counter, so a loaded
box does not shorten what the wait allows — and a guest that has STOPPED
executing fails in ~2 seconds naming the machine (`it is 'paused' at
0060:3C19`) instead of sitting out the whole budget.

The mouse's own residual waits are host-timed by default; `OS88_GUEST_PACE=
<ratio>` (`tools/os88mouse.py`) spends them in guest seconds instead. It is off
by default because flipping it changes how much guest work every row gets per
click, and that wants a soak behind it.

### 7.1 Wait for the thing, not for a duration

```python
#   NO
for _ in range(30):
    time.sleep(1)
    if len(win_list(m, S)) > n0:
        break
time.sleep(20)                      # "give the load time"

#   YES
os88marty.until(m, lambda mm: len(win_list(mm, S)) > n0,
                "Tracker's window to open", poll=0.2, guest=40.0)
os88marty.until(m, claimed, "Tracker to claim the module",
                poll=0.2, guest=60.0)
```

`[trk_modseg]` going non-zero IS "the 116KB expanded and Tracker holds it". The
wait then costs what the decode costs, and on a slow box it waits LONGER rather
than reading a zero and blaming the decoder.

`for _ in range(N): if not served(): advance()` has the same defect in a
different costume — it gives the guest fewer rounds exactly when more is
happening.

### 7.2 Pick a signal that means what you think

`lzdrv` waited on `DRVR_SEG` going non-zero and called it "the driver
attached". `drv_load` writes that word the moment `mem_claim_hi_x` answers —
**before** the file is read, checked, expanded, its bss re-made and
`drv_attach` far-called. The wait returned three quarters of the way through a
load. `drv_owner` for the class is the signal, because `drv_publish` is reached
from `drv_attach` and nothing else writes it.

Read the kernel and find the write that happens LAST.

### 7.3 `settle` is expensive and often the wrong question

`settle` is **48% of a row**, and two-thirds of every settle is its own floor:
`stable` identical captures `quiet` apart is `stable × quiet` = 2.0 HOST
seconds at the defaults before it can return, and that cannot come down (a
change arriving after one whole quiet round happens 1 time in 19, so halving
it would end one settle mid-repaint per 48).

So the only way to spend less is not to settle. `quiesce` is settle's shape
over a handful of bytes instead of a framebuffer, and over guest seconds
instead of host ones — `dispcalc` went **376.3s → 197.2s** with every
assertion still passing, because one line was 30% of all its settle time and
what it was waiting for was thirteen bytes of a composition buffer.

`settle` remains right when the next line compares PIXELS. It is positively
wrong for an operation that holds the gfx lock: the screen is *more* still
while such an operation is busy than when it is finished, so a settle returns
five seconds into a hard-disk install and the `with` block kills the emulator
mid-copy. `until` on the commit is the answer there.

`OS88_WAITLOG=<path>` records every wait with its CALL SITE, which is how the
totals become a work list.

---

## 8. Asserting: guest state over pixels

Read the byte the feature actually writes. It is exact, it is cheap, and it
survives a layout change.

* `mp_loaded`, `trk_modseg`, `ld_status`, `np_len`, `drv_tab` — a number that
  is right or wrong.
* A whole image compared BYTE FOR BYTE where the subject is bytes. A decoder
  that got one match wrong still opens a window, still shows the title, and
  still plays — it plays a click.
* The HOST side of a mounted image, where the commit is a single write.

Compare pixels when pixels ARE the subject — a redraw, a glyph, a greyed
control, a straddled window — and then say which pixels and why. Three defects
are invisible in an emulator and cost this project bug after bug: a visible
redraw, a double-draw flash, and input overrun. None showed in a screendump;
every one was found on hardware or by counting.

**Ask the kernel for its own constants.** `lzship` walked `drv_tab` on a stride
of 10 where `DRVR_SIZE` is 16, over sixteen rows where `DRV_MAX` is five — 256
bytes of an 80-byte table, on a stride matching no field. It never said so,
because the only assertion was `live < 1`. `os88sym.equates()` answers both,
and answers them correctly on `kern_small` too (`DRV_MAX` is 4 there, and 6 on
`kern_emu`).

**And confirm that what you are reading has been WRITTEN.** `lzdrv` read
DRVCALL's probe strings straight after the window opened. `dc_probe` runs from
`dc_paint`, and the window's FIRST paint does not reach the driver — so the
three lines were still the image's own `Ping: ..`. Alone the row won the race
and passed; with a second emulator on the box, both the row under test and the
row at HEAD read `Ping: ..`, which looks exactly like a driver that failed to
expand.

---

## 9. Which emulator

**MartyPC is the default instrument. QEMU is a fallback with a closed list**
(docs/TESTING.md owns it):

1. 286 and 386
2. rung 1 of the hard-disk driver — gated on `CPU_286`
3. SPEC.md 9.5's awkward mouse cases — COM2, the cross-wired IRQ4 card, a modem
4. the PS/2 mouse — MartyPC is an 8088
5. the Ethernet card — MartyPC has no NIC of any kind
6. the RTC ladder's WRITE half — a 5150 has no real-time clock
7. the VMware absolute pointer (SPEC.md 9.11) — MartyPC has no backdoor

"It is quicker to type" is not on the list. Everything that runs on an 8088 —
all three adapters, input, screenshots, sound — is MartyPC, which agrees with
the field machine to 0–4% on 45 of 47 `gfxbench` rows.

Several instances run at once and nothing has to be arranged between them:
`launch()` gives each its own port, run directory and disks. Take the address
off the object (`m.addr`), never type 9001.

---

## 10. Output

One row, one verdict, on stdout, flushed. The runner prints a row's output only
when it fails or under `-v`, so write for somebody reading a failure.

```python
def say(*a):
    print(*a, flush=True)

fails = []
...
if got == want:
    say("  bytes      ok  (all %d, byte for byte)" % len(want))
else:
    bad = [i for i in range(len(want)) if got[i] != want[i]]
    fails.append("%d of %d bytes differ, first at %d - which is %s the 64KB "
                 "boundary" % (len(bad), len(want), bad[0],
                               "past" if bad[0] >= 0x10000 else "before"))

for f in fails:
    say("  FAIL: " + f)
say("lzmod: %s" % ("FAILED" if fails else "ok"))
return 1 if fails else 0
```

* **Collect failures, do not raise on the first.** A renumbering breaks fifty
  slots and the useful report is all fifty.
* **A failure message carries the numbers on either side of it** — the offset,
  the byte, the symbol it resolved to. "expanded WRONG" is not actionable;
  "%d of %d bytes differ, first at %d, which is past the 64KB boundary" is.
* **Exit non-zero on failure.** That is what the runner reads.
* Host-side rows under `tests/unit/` use `harness.check(cond, what, why=…)`
  (or `harness.eq(got, want, what)`) and `done("t_name")` instead, which does
  all of the above and adds `why=` — say what breaks, for the reader who finds
  it red in a year.

A row that hits a condition it cannot test should `sys.exit("…")` with a
sentence, or declare `needs=` so it SKIPS. Never report a pass about a machine
it never ran on.

---

## 11. Register it, or exempt it with a reason

`tests/unit/t_registry.py` requires every file under `tests/` to be in
`tests/suite.py` or in its `UNREGISTERED` map with a reason.

**The reason matters more than the exemption.** "Needs a build prerequisite"
and "needs hardware nothing here has" are facts a reader should find without
running it; an unexplained exemption is how a test that has simply broken gets
filed as one that was never meant to run.

`t_registry` also checks `builds=True` against the script rather than trusting
it — a row that gains a `make` and not the flag is a suite that fails one run
in five for no visible reason — and `BUILDS_WITHOUT_MAKE` is where a row that
writes `build/` by some other route says so.

Then run the gates:

```
python3 tools/os88test.py --list                  # the registry as the runner sees it
python3 tools/os88test.py fast                     # 30s, and part of every make
python3 tools/os88test.py soak -k '<yourrow>'      # your row, alone
python3 tools/os88test.py soak -k '<yourrow>' --marty-jobs 3   # ...and loaded
make test-full                                     # the pre-merge gate
```

**The loaded run is not optional for an emulator row.** Passing alone and
failing in a wide lane is the single most common way a new row lands broken,
and §7 is why.

---

## 12. Checklist

- [ ] I broke the thing on purpose and watched the row go red.
- [ ] `secs` is a number I measured, not one I guessed.
- [ ] No `builds=True`. A fixture is `wants=`; a different kernel is
      `os88build.tree(...).apply()`.
- [ ] No `time.sleep` anywhere near a Marty. Every wait is `until` / `quiesce`
      / `settle` / `guest_sleep`, on the guest's clock.
- [ ] Every wait is on a signal that means what I think — I found the write
      that happens LAST.
- [ ] Navigation is `os88ui` verbs, by name. Any hand-rolled click has a
      comment saying why and a confirmation after it.
- [ ] Assertions read guest state, or say why pixels are the subject.
- [ ] Kernel constants come from `os88sym.equates()`, not from my typing.
- [ ] Host-side reads of `build/…` go through `os88build.at()`.
- [ ] The row writes nothing under `build/`.
- [ ] Failures are collected, carry their numbers, and the script exits
      non-zero.
- [ ] `needs=` names what it cannot do without, so a box that lacks it SKIPS.
- [ ] Registered in `tests/suite.py` with a `why` that says what breaks.
- [ ] `make test-full` is green, and the row passes at `--marty-jobs 3`.

---

## 13. The failures this document is made of

Kept as a list because the abstract rule is forgettable and the incident is
not. Each one can still happen today.

| # | what happened | rule |
|---|---|---|
| 1 | `dispcp` (a library) and `mkclick` (a generator) registered as rows: `ok` in 0.1s and 0.0s against 60 and 10 declared | §1 |
| 2 | Fourteen compression rows declaring 2,721s and taking 701 | §4 |
| 3 | One row's mid-run `make` opened a four-minute window that cost nine rows | §5 |
| 4 | Three rows, 0/3 against `build/` under a knob hammer, 3/3 against a tree | §5.2 |
| 5 | `launch(..., env=t.env)` — no such argument; three rows died in their first second | §5.2 |
| 6 | `blitcut` died inside `no_saver`, three frames below its own code, because only `OS88_BUILD` was set | §5.2 |
| 7 | A stale `build/c64.bin` survived a cherry-pick; `c64part` failed with "not byte-identical", which reads as a broken package | §5.1 |
| 8 | Twelve rows under load: 1.06× slower, up to 37% less guest work done | §7 |
| 9 | Four of five consecutive soak failures were `for _ in range(N)` giving the guest fewer rounds under load | §7.1 |
| 10 | `lzdrv` waited on `DRVR_SEG`, which is written before the read, the expand, the bss and the attach | §7.2 |
| 11 | `settle` returning five seconds into a hard-disk install, because the gfx lock makes the screen *more* still while it works | §7.3 |
| 12 | `dispcalc` spending 30% of all settle time waiting for the screen when the subject was thirteen bytes | §7.3 |
| 13 | `lzdrv` reading DRVCALL's probe strings before the probe had run — green alone, red beside one other emulator | §8 |
| 14 | `lzship` walking `drv_tab` on a stride of 10 where the record is 16 | §8 |
| 15 | A row hardcoding an IBM ROM name, running on a box that had it and silently not on one that did not | §6 |
| 16 | A row whose screen saver came on during a wait, comparing a black screen | §6 |

---

## 14. Where the rest of it is

| document | for |
|---|---|
| **docs/TESTING.md** | what each emulator can and cannot show, per capability, with a recipe |
| **docs/MARTYPC-DEBUG.md** | the instrument: `launch`/`settle`/`sym`, the debug server, reading the guest's floppy back |
| **docs/plans/SOAK-PARALLEL.md** | the parallel runner, where the suite's time goes, and every measurement quoted above |
| **docs/plans/HANDOFF-SOAK-FINDINGS.md** | worked diagnoses of rows that failed, and what was ruled out for each |
| **PERFORMANCE.md** Part 7 | checking a change; Parts 3.1/3.2 for flicker and smoothness harnesses |
| **`tests/suite.py`** | the registry, and its header on why `full` is curated |
