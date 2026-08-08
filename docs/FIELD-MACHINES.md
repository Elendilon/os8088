# FIELD-MACHINES.md — the real machines, and how to get a number off one

[PERFORMANCE.md](../PERFORMANCE.md) Part 9 records **sets**. This file records
the **machines** they came from, and how to reach the person holding one.

They are different things, and keeping them apart matters: Part 6 rule 8 says
every figure carries its machine, and Part 9's sets duly say "IBM PC 5150,
8088 at 4.77 MHz, 640KB" — but not *whose*, not what else is in the slots, and
not how a build gets from this repo onto a floppy in that machine. That last
one is the whole cost of a field run and it has never been written down.

Its sibling is [FIELD-NOTES.md](FIELD-NOTES.md), which records what real
hardware **found**. This one records what real hardware **is**.

---

## Why the register is in the repo rather than in someone's head

**An agent cannot tell one contributor from another, and the repo can.**

A session is told which account it is running as and forgets it when the
session ends; there is no memory between them. Nothing in a commit says "this
contributor owns a 5150" — the git history here is 120-odd commits authored
`Claude <noreply@anthropic.com>` plus two humans, and an author line is not a
hardware inventory. So an agent asked to "check this on the real machine" has
no way to know whether there *is* one, which one, or who to ask.

What is durable is the **fork**. `Elendilon/os8088` is visible to every
session that works in it — it is the remote, the branch name and the owner —
and it is visible to every human reading the repo. So the register is keyed on
the **full fork name** of whoever owns the iron — `Elendilon/os8088`, not
`Elendilon` — and it lives here rather than in a conversation.

The full name and not the bare handle, because **this file is written to be
merged upstream**. In the fork, "owner: `Elendilon`" is unambiguous and a
reader can work out the rest; in the parent repository, with contributors from
several forks, a bare handle names a person with no way to tell which tree
they hold the hardware for. The fork name survives the merge with its meaning
intact, and it is still exactly what an agent can see from its remote.

Handles, not email addresses: this repo is public (it ships releases and feeds
os8088.com), and a personal address in a tracked file is published, not
recorded. If you want a contact route in here, say so and put in the one you
want published.

---

## The rule that comes before any of the numbers

> **A result is not a field result because a human handed it to you.** Do not
> assume any figure came off the 5150 unless the run on it was actually
> discussed. **Ask.**

The owner of the 5150 also tests on **PCem** routinely, and Part 9's Set 4
came off **MartyPC** — and neither is QEMU, so this is not the usual
"emulators lie" caution. Both model period hardware at period speed, which
makes their numbers *plausible in the same units* as the iron's, and that is
exactly what makes an unlabelled one dangerous: a QEMU figure announces
itself by being absurd, and a PCem or MartyPC figure does not.

This is PERFORMANCE.md Part 6 rule 8 — every figure carries its machine —
applied to the conversation rather than to the document. A number whose
provenance you assumed is a number you will write into Part 9 under the wrong
heading, and the next reader has no way to catch it.

| you were given | what it is worth |
|---|---|
| a `.TXT` report the owner says came off the 5150 | a **field set**. Part 9, with its four provenance lines |
| a report from **PCem** or **MartyPC** | a good cross-check of *work* and a reasonable sanity check on *time* — but a model of the machine, not the machine. **Name the emulator in Part 9**, as Set 4 does, or leave it out |
| a report from **QEMU** | instruction counts only, and only under `-icount`. Never microseconds |
| a screenshot, a description, "it looked fine" | evidence about behaviour, not about time |

---

## The IBM 5150 — `Elendilon/os8088`'s

**The machine this project is calibrated against.** Every measured number in
PERFORMANCE.md Part 2 came off it (Part 9 Sets 1 and 2), and SPEC.md quotes it
by name in a dozen places.

| | |
|---|---|
| owner | **`Elendilon/os8088`** |
| machine | **IBM PC 5150**, Intel 8088 at 4.77 MHz |
| motherboard | the 64–256K board, **256 KB populated** |
| expansion | **AST SixPakPlus Rev 1** — carries the other **384 KB** (256 + 384 = the 640 KB every set reports) **and the clock**. That 640 is what `int 12h` answers, and since SPEC.md §2.7 the boot sector relocates itself to the top of it — so if this machine ever stops booting after a memory change, the first thing to check is the motherboard DIP switches, which are where an XT's RAM count comes from. A board the switches do not mention is a machine with plenty of RAM and a small answer, and the sector prints `RAM` and stops rather than loading a kernel over itself |
| clock | the SixPakPlus's **MM58167 at 2C0h** — §37.90's **rung 2**, and the machine the whole ladder was written for: an XT BIOS implements `int 1Ah` AH=00h/01h and nothing else, so this BIOS knows nothing about a clock sitting in its own backplane. It is also what keeps rung 3 off a SixPakPlus — rung 3 is claimed only when the BIOS *can* read the clock, and here it cannot |
| video | **Hercules GB101 → IBM 5151** (mono TTL) **and IBM CGA, new style → IBM 5153** (RGB). **Both cards and both monitors, always, in the machine.** So the second column costs a *build*, never a card swap — but the probe (§39.1) finds the Hercules first, so the CGA needs a kernel told to ignore it |
| floppy | **one** — a **Tandon TM100-2**, 360 KB 5.25" DD. There is no drive B |
| hard disk | **Seagate ST-225**, 20 MB MFM, on a **Seagate ST11M** controller, in the second bay |
| serial | **one port, at 0x3F8 (COM1)**, with the mouse on it — `sysbench`'s SPEC.md §9.4.2 block reports `COM1 03F8, COM2 0000`. Worth having written down, because it decides which half of a two-sided mouse change this machine can witness: with one port there is no §9.5 contest, `[mou_need]` is 1 by default, and everything §9.5.1 says about a modem on the other port is untestable here. The **Compaq Portable III** below is the two-port machine |
| sound | none |
| period | **intentionally, entirely period. No modern hardware is attached to the 5150.** No Gotek, no XT-IDE, no flash. That is the property that makes its floppy and disk timings mean what they say, and it is a deliberate constraint rather than an accident — do not propose "just put a Gotek in it" as a way to shorten a turnaround |

### The clock reads 1980 after a power cycle, and that is correct

A **failed diode** on the SixPakPlus means it cannot hold time across a power
*off*: the backup battery ends up trying to backfeed the whole ISA bus and
sags to 0.6 V. So a cold start comes up at **1980**, the §37.90 fallback, and
that is the hardware behaving as this hardware behaves.

**It is not a clock bug, and it is not the fallback misfiring.** Across a
*warm* start the SixPak's RTC still has its 5 V, and everything survives —
the year included. So on this machine:

- **reading and writing the clock both fully work**, which is what makes it a
  valid rung-2 witness (§37.90's verification is explicitly "survives a warm
  boot");
- a report of "the date is wrong after switching it on" from here is
  **expected**, and chasing it is chasing a diode;
- a report of the time **not surviving a warm boot, or the year being
  dropped**, is a real defect and worth acting on.

### What it has measured

Not a specification — these are outputs, and they are here so a run that
disagrees with them is recognisable as news rather than noise.

| | |
|---|---|
| CPU, derived independently from `MUL` and `DIV` | **4.64 and 4.68 MHz** against a nominal 4.7727 |
| PIT counts per tick | 65,542, then **65,536 exactly** on the second boot |
| instruction floor | **4.34 clocks per instruction byte** |
| any small `gfx_*` call, both cards | **~756 µs** fixed — 765.64 / 765.70 µs for `GFX_PIXEL`, 0.008% apart |
| one 8×8 glyph cell | 901 µs Hercules, 909 µs CGA |
| a solid fill | 177 µs/row + 0.28 µs/px Hercules; 182 + 0.33 CGA |
| framebuffer read-modify-write | 79.6 clocks/byte Hercules, 81.0 CGA — only ~7 of them the bus |
| floppy | **238 ms per sector**, 2,100 bytes/second; a one-sector file open+read is 796 ms |
| the kernel's own interrupts | 1–3% of a busy CPU |

Two of those are the load-bearing ones. **756 µs** is the per-call floor
(SPEC.md §5.7), and **238 ms a sector** is why a 116KB module load is 57
seconds.

### Two things the 5150 can test that nothing else here can

- **The MFM hard disk.** SPEC.md §52's driver has never run on real spinning
  MFM — though **the volume mounts**: that much has been tried, and it worked
  first time. This is an ST-225 behind an **ST11M**, which is a controller
  *with a ROM* — and that is §52's **rung 0**, the int 13h path, which is also the
  whole of MFM support. Rung 1 (the IDE task file) is gated on `CPU_286` for
  an arithmetic reason — an 8088's `in ax, dx` is two 8-bit bus cycles at the
  same port, so the drive's high byte is lost — so **rung 0 is the only rung
  an 8088 can ever take, and the 5150 is the only machine that can prove it.**
  Everything §52 says about partitioning, formatting, the capacity-table
  cluster sizes and the `SYSTEM.CFG` automount is, on real MFM, untested.
- **The clock ladder's rung 2.** Already field-verified here (§37.90), and
  the only rung no emulator can reach.

### The hard disk is a real DOS 3.3 install, and it is not yours

The rules for anything that touches C: on this machine, from its owner:

0. **The hard disk is only mounted when a run asks for it, and the asking
   happens BEFORE the images are sent.** The driver is off by default
   (SPEC.md §51.3 — a freshly built image carries no `SYSTEM.CFG`, so nothing
   is loaded and nothing is probed), and its owner leaves it that way. So a
   set that wants the hard-disk rows has to say so **while the disks are
   being prepared**, not after they arrive: the operator ticks
   **Drivers → Hard Disk** in the Control Panel and **closes the panel**
   (§31.8 — closing is what writes `SYSTEM.CFG`) before the run. A set that
   does not ask gets `No volume at index 2 - no hard disk mounted`, which is
   the correct answer and not a fault. **If a change makes those rows
   necessary, ask in the message that carries the images.**
1. **Do not format it. Do not partition it.** §52's disk tool is exactly the
   thing that must not be pointed at it.
2. **Do not leave anything behind.** Whatever a test writes, it removes.
3. **Do not delete anything you did not write.** Not even something that
   looks like scratch.

That rules out a whole class of measurement, and it is the right trade — a
20 MB drive with somebody's DOS install on it is not a scratch volume. What
it leaves is **reads**, which is most of what is interesting anyway, and
`sysbench`'s hard-disk block is built to that constraint: it mounts, walks
the FAT, reads one file that a DOS 3.3 disk is guaranteed to have
(`COMMAND.COM`), and puts the current volume back. **It never writes, never
creates and never deletes.** The write half of the picture stays unmeasured
on purpose, because a run interrupted between creating a scratch file and
removing it would break rule 2.

Both of its paths were verified under QEMU before it was ever pointed at real
hardware — with no hard disk it prints its refusal and the report still saves
to A:, and with a 20 MB FAT16 partition on ST-225 geometry every row produces
a number, the read returns the file's exact size, and **the disk image is
byte-for-byte identical afterwards**. That last check is the one that matters
here, and it is the one to repeat if anything in that block changes.

---

## The Toshiba T1100 Plus — `Elendilon/os8088`'s, and the only 8086 in the register

The second real machine, and it earns its place by being *nearly* the target
and not quite: an 8086 rather than an 8088, so the same instruction set over
a **16-bit bus**. That makes it the one machine that separates "this is
slow because the CPU is slow" from "this is slow because every instruction
byte is fetched one at a time".

| | |
|---|---|
| owner | **`Elendilon/os8088`** |
| CPU | **i80C86-2**, 7.16 MHz fast / 4.77 MHz slow, switchable from the keyboard; it powers on in fast mode |
| RAM | 256KB on the board + the **384KB expansion** = 640KB |
| video | CGA-compatible, LCD |
| floppy | **two 720KB 3.5" drives** — 300 RPM, 250 kbit/s, 100 ms average latency, 6 ms track-to-track |
| other | the modem expansion is fitted |
| disks | it takes the **720KB** images (`build/cga720.img`), which is why they exist — no `dd` step, unlike the 360KB pair |

Two things it has already been worth. Its `est CPU MHz` came out at **7.12 /
7.29** against the manual's 7.16, so sysbench's estimator is **0.6% out on a
machine nobody calibrated it against** — which is the only independent check
that number has ever had. And its instruction table is the 16-bit bus in
plain sight: `mov r16,r16` is 4.34 clocks a byte on the 5150 (2 bytes, 8.69
clocks) and **3.31 clocks total** here, while `mul` and `div` scale by the
clock alone. Part 2's instruction floor is a property of the 8088's bus, and
this is the machine that shows it by not having it.

It walls at the same **2,161 bytes/second** on the floppy as the 5150 does
(docs/FIELD-NOTES.md 7), which is what makes that wall two machines wide.

---

## The Packard Bell Victory 286 — in the register, results discarded once

| | |
|---|---|
| owner | **`Elendilon/os8088`** |
| board | Packard Bell Victory (theretroweb.com/motherboards/s/packard-bell-victory) |
| CPU | **16 MHz AMD 286** |
| RAM | 4MB, 100ns |
| video | onboard **Paradise PVGA1A**, 256KB — a **VGA** card |
| clock | Dallas DS1287/DS12887, potted |
| floppy | 1.44MB drive A, 1.2MB drive B |

**Its first set was thrown away, and the reason is a trap for the next
person.** It was run from a `VIDEO=cga` field disk, so a VGA machine spent
the whole suite driving the CGA framebuffer path — a fourth combination that
is not one of the three the project supports — and the reports self-identify
as `CGA 640x200 mono` while the files had been hand-renamed `GFXVGA.TXT`.
Two derived rows were worse than useless: `est CPU MHz x100` read **8866**
and `shl clk/bit x100` read **29**, both because they are computed against
**8088** instruction timings a 286 does not have.

So before this machine is worth running again it needs a **VGA field disk**,
which `make field` does not build. And whoever adds one should fix the two
8088-only derived rows to say so on a tier-1 machine rather than printing a
number. It also has a known quirk: **it sometimes decides to boot in mono**,
which may be what put it into the CGA path in the first place.

---

## The Compaq Portable III — `Elendilon/os8088`'s, and mostly unrecorded

**A second real machine, and the one that found SPEC.md §9.5's first field
bug.** It is in here because it is not the 5150 and the difference matters:
the 5150 is an 8088 at 4.77 MHz with a Hercules and a CGA, and this is a
286-class portable with a plasma display. A result from one is not a result
from the other, and PERFORMANCE.md Part 6 rule 8 applies between them exactly
as it applies between iron and an emulator.

| | |
|---|---|
| owner | **`Elendilon/os8088`** |
| machine | **Compaq Portable III** |
| serial | a **1200 baud modem on COM1**. The mouse is on the other port, which is what §9.5 was built for |
| floppy | **one 1.2MB 5.25"**, and it boots the **360KB** images — so `make field`'s disks and `make comscan`'s `comscan.img` are the ones to send, not the 1.44MB pair |
| everything else | **not recorded, because it has not been measured.** Do not fill this table in from what a Portable III generally has — ask, or read it off `comscan` |

**A 1.2MB drive writing a 360KB disk is a known hazard and the owner is
handling it by keeping those disks separate** — a 1.2M drive's head is
narrower than a 360K drive's track, so a disk it has *written* may be
unreadable in a real 360K drive afterwards. It is worth knowing which images
write: the field disks do (their whole point is that the benchmark reports
land back on the disk they came from, and the Control Panel writes
`SYSTEM.CFG` on close), and **`comscan` never writes to a disk at all**.

**What it found, and it is now diagnosed and fixed:** with §9.5's two-port
support in, the mouse was **not detected** on this machine. `tests/comscan`
(docs/TESTING.md) was written for it and answered it in one run:

```
BIOS POST found (40:00h): 03F8 02F8 0000 0000
COM1 03F8  ok  ok  --  --  8250        COM1 03F8: 0 bytes  (silent)
COM2 02F8  ok  ok  ok  ok  8250        COM2 02F8: 244 bytes  first=43 'C'
                                            pkts 81  viol 0  best clean run 81
                                       IRQ line: IRQ4
```

**The mouse is at 0x2F8 and its card drives IRQ4**, where os8088 derives IRQ3
from the base. 81 packets with zero protocol violations to a polled reader —
a perfect mouse the kernel could not hear, because the COM1 vector fired,
read 0x3F8's receive register, found nothing, and left the byte at 0x2F8
holding a line that never made another edge. SPEC.md §9.5.2 is the fix: every
hooked line now services every live port. Reproduced in QEMU first
(`-device isa-serial,iobase=0x2f8,irq=4`), which fails identically on the old
kernel and passes on the new one.

Two lessons from the same run, both about the instrument rather than the
machine. **COM1's loopback failure was comscan's own bug**, not the modem's —
the test inherited whatever divisor the previous one left, so it timed out on
one port and not the other; it programs its own divisor now and prints the
as-found one. And the modem on COM1 stayed **silent** throughout, so none of
§9.5.1's Hayes-result-code defences were exercised on real hardware — they
remain QEMU-verified only.

---

## PCem and MartyPC — the other places results come from

Not machines in the register's sense, but they belong here because reports
come off them and are easy to mistake for field sets. PCem is where the
5150's owner tests routinely; MartyPC is a cycle-accurate 5150 emulator and
produced Part 9's Set 4.

Both emulate period hardware at period speed, which puts them in a different
class from QEMU entirely: their numbers are in the right units and the right
order of magnitude, so nothing about them looks wrong. Treat either as a
**very good model** and never as the machine —

- it is the right tool for *reproducing* something the 5150 showed, without
  spending the seven-step trip below;
- it is the right tool for anything the 5150 must not be pointed at — a
  format, a partition, a disk tool run, anything that writes;
- and their figures go into Part 9 **named**, or not at all. Part 9's four
  provenance lines exist for exactly this, and Set 4 is the worked example:
  it says MartyPC on its machine line and carries its own calibration, which
  is what makes it comparable to the next run rather than to nothing.

## MartyPC — the same caveat, one class better

Also not a machine in the register's sense, and it goes in Part 9 **labelled
MartyPC** for the same reason PCem does. The difference worth knowing is that
MartyPC is **cycle accurate** rather than approximately period-correct, so it
models the 8088's prefetch queue and bus contention rather than a clock rate
— which is precisely where this project's costs live (Part 2's instruction
floor is a prefetch-starvation number). Set 4 came off it.

It has already produced something the 5150 has not: a **77-second log of a
running application**, one row a second, rather than a benchmark that runs
once. That is a different instrument and it needs the discipline below.

**A long log is only comparable to another long log if it says how fast the
machine was.** Two earlier runs could not be compared at all — kernel code
neither of them touched moved 16–19% between them, and nothing in either log
said so, which made every conclusion drawn from the pair worthless. A run
must time a fixed, known quantity of work at each end and print it; Set 4's
`CAL` lines are that, and their CPU figure agreeing to 0.01% is what licenses
every other number in the set. If the two brackets disagree, the machine
moved *underneath* the measurement and the rows between them are suspect.

### It takes MEMORY DUMPS, and an agent should ask for one

MartyPC's debugger will dump **the full 1MB** and **the code segment**, and
that is a capability nothing else in this register has — the 5150 has no
debugger, and QEMU's QMP `xp` reaches memory but only from inside the
container, so it can never answer a question about the machine on someone
else's desk. **Ask for a dump whenever the question is "what does the kernel
think", rather than "how long did it take" or "what did it look like".** It
costs the owner one menu click and it is worth many rounds of guessing.

A dump is a strong instrument because it is **self-validating**. The kernel
image lands at `KERNEL_SEG`, so linear `0x600` onward is `build/kernel.bin`
byte for byte apart from writable state, which does three things at once: it
proves the machine was running *the build you sent* (diff it — a
mouse-identify dump came back 1,353 differing bytes of 71,112, all of it
`.text` data with real initialisers), it gives you every kernel variable at
its listing offset with no instrumentation added, and the differing bytes are
themselves the answer. `boot_ticks` at `0060:000C` is the cheapest check that
you are reading the right image at the right base: `FFFF` in the file, the
elapsed count in the dump.

Three rules, all learned on the one dump this register has so far:

- **Say what state you want it taken IN, because the interesting state is
  usually the untouched one.** The mouse dump had to be taken at the desktop
  with the mouse *deliberately not moved* — the whole question was what the
  kernel believed before any packet arrived, and one nudge erases it.
- **Re-derive every offset from a listing of the exact commit**, and never
  from an earlier session's numbers. `nasm … -l` and then `0x600 + offset`;
  anything before `font.inc` moves them all.
- **Find a value that pins the reading before you trust any of it.**
  `mouse_x`/`mouse_y` sitting on `[vid_w]/2, [vid_h]/2` said "Hercules, and
  nothing has moved yet" in one word each, and without it a `mou_seen` of 0
  beside a moved cursor looked like a contradiction in the kernel rather than
  a correct reading of an untouched machine.

What it still cannot do is the register's own first rule: it is an emulator,
so its **timings go in Part 9 labelled MartyPC** and a dump is evidence about
*logic*, never about time.

---

## How to take a set on the 5150

### `make field` — two bootable disks, because there is no drive B

```sh
make field          # -> build/herc.img and build/cga.img, both 360KB bootable
```

Both are shaped by the machine, and neither decision in them is cosmetic:

- **The benchmarks are on the BOOT disk**, in the root, beside `TASKMGR.O88`
  and for the same reason it is there (§28.3). With one floppy drive, a
  benchmark on a separate data floppy means a disk swap mid-session — and on
  this machine a disk swap is a walk to another room and back (below). Boot
  either image and the four harnesses are one double-click away in Disk A,
  and the reports they save land back on the disk they came from.
  `os88disk.py` marks them visible + read-only (§19.6), so they list and
  cannot be deleted by accident.
- **One image per card.** Both cards live in the machine permanently, so the
  probe can only be asked one question at a time and it answers *Hercules*
  (§39.1). `herc.img` is the ordinary shipped kernel — it exercises the probe
  on the way past — and `cga.img` is a `VIDEO=cga` kernel that ignores the
  Hercules. That kernel is built in `build/cgak/`, never in `build/`: a
  forced kernel that reaches `build/` is a machine that boots the wrong card
  for **everyone**, and that is a mistake that has been made.

**Neither disk may be write-protected.** The reports are the point, and a
protected disk answers int 13h status 03h, which the OS faithfully reports as
`Write protected`.

They are 8.3-short and unambiguous at a DOS prompt on purpose: DOS 3.3 has no
tab completion and these names get typed by hand into `dskimage`.

**They are never committed**, and neither is anything else under `build/` —
it is gitignored outright (SPEC.md §16), and `all` never builds these two in
any case. They are somebody's test disks, built on demand and **sent** —
attach them to the person who is going to write them to a floppy. Adding them
to the repo would put a pair of large binaries under version control that no
source change updates, which is exactly why the shipped images stopped being
tracked.

### Then, on the machine

- Boot the image, open **Disk A**, launch `GFXBENCH.O88`.
  **`R`** runs it, **`S`** saves the report. It names the file after the
  adapter it found: `GFXHERC.TXT` / `GFXCGA.TXT` / `GFXVGA.TXT`, so the two
  disks cannot produce a file that overwrites the other's.
- Then `SYSBENCH.O88`, likewise, to `SYSBENCH.TXT`.
- `gfxbench` is about fifteen seconds. `sysbench` is about a minute on a
  floppy-only machine and **two or more with the hard disk mounted** — its
  read row calibrates itself off the first read and then runs for about six
  seconds, because a benchmark here has to be accurate and useful rather than
  quick, and method T quantises to 54.92 ms. It prints the iteration count it
  chose. **The machine is frozen while either runs, by design** — the screen
  sitting still is not a hang, and the bottom line says which block it is on.
- Bring the `.TXT` files back and paste them into Part 9 with the four
  provenance lines it asks for.

### The path an image takes to get there

This is the real cost of a field run, and it is why "just rebuild and try
again" is not a thing anyone should ask for casually. The 5150 has no modern
storage in it by design, so an image travels:

1. Fetch the SD card from the **writer machine** — a second period box with
   both a genuine 360 KB drive and a **picomem** (a modern card that boots it
   from `.vhd` images on SD). The picomem is on *that* machine, never on the
   5150.
2. Mount the VHD on the primary system.
3. Copy the `.img` into the VHD.
4. Unmount the VHD, then the SD card.
5. SD card back into the writer machine; boot it to **DOS 3.3**.
6. `dskimage` writes the 360 KB image to a real 360 KB disk. **It has to be a
   real 360 KB drive** — head geometry differs between 360 KB and 1.2 MB
   drives, and a 360 KB disk written in a 1.2 MB drive is not reliably
   readable in one.
7. Carry the disk to the 5150 and boot.

Two consequences worth acting on. **Batch the questions**: everything a set
can answer should be in the image before it is written, because the marginal
cost of one more benchmark row is nothing and the marginal cost of one more
*trip* is the seven steps above. And **make the build deterministic before
you hand it over** — quote a commit and build the image from a clean checkout
of it, so a disk that behaves oddly is a finding rather than a question about
which build it was.

---

## What to ask the 5150's owner for, and what not to

**Worth a field run** — nothing else can answer these:

- **Time.** QEMU is exact about how much work the guest does and useless about
  how long it takes (Part 4). Anything whose answer is in microseconds is a
  field question.
- **The three defects QEMU cannot show at all** (Part 3): a visible redraw, a
  double-draw flash, and input overrun. These are judged by a person watching
  the glass, and no screenshot substitutes.
- **A model this repo has been spending without measuring.** Part 9's "what
  the next set is being asked" table is the current list — the variable-shift
  slope, the table-lookup cost, the memory-form `mul`, the per-row fill term,
  and the whole-screen repaint.
- **The rungs no emulator has**: §37.90's MM58167 and RP5C01 clock tiers, and
  §39.1's video detection probe on real cards.
- **What a real PERIPHERAL does on a real card.** Not the same question as
  "what does the emulator model" — SPEC.md §9.4.1 turns on whether a real
  serial mouse answers a DTR/RTS raise with `'M'`, and QEMU's `msmouse`
  ignores DTR outright while MartyPC's is a model of one. `sysbench`'s mouse
  block is a **state dump rather than a measurement** for exactly this
  reason, and it is the shape to copy: when the field question is about
  logic and not time, publish the state and let the machine print it.

**Not worth a field run** — the container already answers these, faster and
reproducibly:

- **Counts.** How many fills, glyphs or walk iterations something does is
  exact under QEMU; instrument a counter and read it over QMP (Part 4).
- **Instruction counts.** `-icount shift=3,sleep=off` is deterministic to ±1
  and machine-independent.
- **Whether the pixels are right.** A byte-for-byte screendump comparison on
  `VIDEO=cga`, plus `tools/hercshot.py` for Hercules, settles rendering
  without leaving the container.

The rule of thumb: **send it a question about time or about what a human
sees; keep every question about work.**

### Handing over a build

State the **commit**, and hand over the images rather than a branch name — a
branch moves. Build them from a clean checkout of the commit you quote, with
no `VIDEO=`/`RTC=`/`DISKCNT=` knob set, or the floppy holds something the
source no longer says.
