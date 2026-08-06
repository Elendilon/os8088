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
the GitHub handle of whoever owns the iron, and it lives here rather than in a
conversation.

Handles, not email addresses: this repo is public (it ships releases and feeds
os8088.com), and a personal address in a tracked file is published, not
recorded. If you want a contact route in here, say so and put in the one you
want published.

---

## The rule that comes before any of the numbers

> **A result is not a field result because a human handed it to you.** Do not
> assume any figure came off the 5150 unless the run on it was actually
> discussed. **Ask.**

The owner of the 5150 also tests on **PCem**, routinely — and PCem is not
QEMU, so this is not the usual "emulators lie" caution. It models period
hardware at period speed, which makes its numbers *plausible in the same
units* as the iron's, and that is exactly what makes an unlabelled one
dangerous: a QEMU figure announces itself by being absurd, and a PCem figure
does not.

This is PERFORMANCE.md Part 6 rule 8 — every figure carries its machine —
applied to the conversation rather than to the document. A number whose
provenance you assumed is a number you will write into Part 9 under the wrong
heading, and the next reader has no way to catch it.

| you were given | what it is worth |
|---|---|
| a `.TXT` report the owner says came off the 5150 | a **field set**. Part 9, with its four provenance lines |
| a report from **PCem** | a good cross-check of *work* and a reasonable sanity check on *time* — but it is a model of the machine, not the machine. Label it PCem in Part 9 or leave it out |
| a report from **QEMU** | instruction counts only, and only under `-icount`. Never microseconds |
| a screenshot, a description, "it looked fine" | evidence about behaviour, not about time |

---

## The IBM 5150 — `Elendilon`'s

**The machine this project is calibrated against.** Every measured number in
PERFORMANCE.md Part 2 came off it (Part 9 Sets 1 and 2), and SPEC.md quotes it
by name in a dozen places.

| | |
|---|---|
| owner | `Elendilon` — owner of this fork, `Elendilon/os8088` |
| machine | **IBM PC 5150**, Intel 8088 at 4.77 MHz |
| motherboard | the 64–256K board, **256 KB populated** |
| expansion | **AST SixPakPlus Rev 1** — carries the other **384 KB** (256 + 384 = the 640 KB every set reports) **and the clock** |
| clock | the SixPakPlus's **MM58167 at 2C0h** — §37.90's **rung 2**, and the machine the whole ladder was written for: an XT BIOS implements `int 1Ah` AH=00h/01h and nothing else, so this BIOS knows nothing about a clock sitting in its own backplane. It is also what keeps rung 3 off a SixPakPlus — rung 3 is claimed only when the BIOS *can* read the clock, and here it cannot |
| video | **Hercules GB101 → IBM 5151** (mono TTL) **and IBM CGA, new style → IBM 5153** (RGB). **Both cards and both monitors, always, in the machine.** So the second column costs a *build*, never a card swap — but the probe (§39.1) finds the Hercules first, so the CGA needs a kernel told to ignore it |
| floppy | **one** — a **Tandon TM100-2**, 360 KB 5.25" DD. There is no drive B |
| hard disk | **Seagate ST-225**, 20 MB MFM, on a **Seagate ST11M** controller, in the second bay |
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

## PCem — the other place results come from

Not a machine in the register's sense, but it belongs here because reports
come off it and they are easy to mistake for field sets.

PCem emulates period hardware at period speed, which puts it in a different
class from QEMU entirely: its numbers are in the right units and the right
order of magnitude, so nothing about them looks wrong. Treat it as a **very
good model** and never as the machine —

- it is the right tool for *reproducing* something the 5150 showed, without
  spending the seven-step trip below;
- it is the right tool for anything the 5150 must not be pointed at — a
  format, a partition, a disk tool run, anything that writes;
- and its figures go into Part 9 **labelled PCem**, or not at all. Part 9's
  four provenance lines exist for exactly this.

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
  for **everyone**, which is a mistake that has been made and is why
  `make check-images` reports it as STALE.

**Neither disk may be write-protected.** The reports are the point, and a
protected disk answers int 13h status 03h, which the OS faithfully reports as
`Write protected`.

They are 8.3-short and unambiguous at a DOS prompt on purpose: DOS 3.3 has no
tab completion and these names get typed by hand into `dskimage`.

**They are never committed.** `build/` is gitignored and these two are not
among the artifacts force-added into it, so `make check-images` cannot see
them and `all` never builds them. They are somebody's test disks, built on
demand and **sent** — attach them to the person who is going to write them to
a floppy. Adding them to the repo would put a pair of large binaries under
version control that no source change updates, which is the exact failure
`check-images` exists to catch for the ones that *are* shipped.

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
you hand it over** — quote a commit, and have `make check-images` clean at
it, so a disk that behaves oddly is a finding rather than a question about
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
branch moves. `make check-images` should be clean at the commit you quote, or
the floppy holds something the source no longer says.
