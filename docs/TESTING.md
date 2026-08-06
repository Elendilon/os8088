# What can actually be tested, and where

**Short answer: QEMU covers all three video adapters and all three sound
routes.** 86Box is needed for exactly two things, and they are narrow.

This document exists because the opposite keeps getting concluded. It has
happened for Hercules — `docs/HERCULES-TESTING.md` opens by saying so, and
that claim had sat in CLAUDE.md costing people time — and it keeps happening
for sound, for a duller reason: the AdLib and Sound Blaster recipes are real,
committed and mechanical, but they live in the middle of
`docs/SOUND-PLAN.md`, an 850-line *plan*, interleaved with phase history. A
plan document is not where anyone looks to answer "can I test this?", so the
answer people reach is "no".

Every recipe below was run end to end on a stock QEMU 8.2.2 and the measured
result is quoted with it. If one of them fails, that is a finding about the
tree, not about the emulator.

**This document answers *where a test can run*. [PERFORMANCE.md](../PERFORMANCE.md)
answers *what the target machine costs* — the calibration numbers, the
standing budget every redraw path has already been measured down to, and the
three visible defects the emulator cannot show. Read that one before changing
anything that draws or loops; "Modelling the old machine from a fast one",
below, is the short version of it.**

---

## The matrix

| Capability | QEMU | How | Verified result |
|---|---|---|---|
| VGA 640x480x16 | ✅ | `make test` | boots to Locator; loads packages |
| CGA 640x200 mono | ✅ | `make test VIDEO=cga` | renders; dumps 640x400 (line-doubled) |
| Hercules 720x348 mono | ✅ | `make test VIDEO=herc HERCSEG=0x7000` | renders; 55.8% lit at the desktop |
| PC speaker | ✅ | `make test-snd` (no card) | dominant 880.0 Hz |
| AdLib / OPL2 | ✅ | `make test-snd ADLIB=1` | dominant 880.0 Hz from a keyed 440 |
| Sound Blaster 16 | ✅ | `make test-snd SB16=1` | 2.00 s at 1000.0 Hz |
| Scripted mouse / keys | ✅ | `tools/mouse.py`, `tools/qmp.py` | all adapters, incl. Hercules |
| Performance benchmarks | ✅ | `make bench` (from `tests/`, not in `all`) | numbers are always in flux — see below |
| Fullscreen exclusive (SPEC.md §53) | ✅ | `make test TESTAPPS=build/fsxtest.img` | every FSXM mode the adapter owns sets, draws and restores — the desktop screendump below the bar is byte-identical after a full sweep; Mode X dumps 640x480 (line-doubled 320x240) |
| Video **detection probe** | ❌ | `make xt-cga` / `xt-hercules` | 86Box only |
| 6845 programming | ❌ | `make xt-hercules` (and fsx id 4's real mode set) | 86Box only |
| Period-correct timing | ❌ | `make xt` (4.77 MHz), `286`, `386` | 86Box only |

`VIDEO=` forces a code path; it does not exercise the probe that would have
chosen it. That distinction is the whole of the ❌ column for video: QEMU
emulates no CGA and no Hercules card, so what is untestable here is the
*choosing*, not the *drawing* — and the drawing is almost all of the code.

---

## Video

CGA works because SeaVGABIOS's `int 10h AX=0006h` is a byte-exact CGA
framebuffer, so an ordinary `screendump` shows it. Note the dump comes back
**640x400** — QEMU line-doubles 640x200 — so a crop's Y and H are twice the
kernel's own. VGA is 1:1.

```sh
make test VIDEO=cga
python3 tools/shot.py build/qmp.sock /tmp/cga.png
python3 tools/mouse.py --screen 640x200 build/qmp.sock click X Y
```

Hercules needs its framebuffer relocated into spare RAM (B0000 is unmapped
under QEMU and silently swallows every write), and it is **never**
screendumpable — that framebuffer is guest RAM the VGA device has never heard
of, so `screendump` returns a black or stale VGA screen and does not error.
That silent non-failure is how "Hercules doesn't work" gets concluded from
one screenshot.

```sh
make test VIDEO=herc HERCSEG=0x7000
python3 tools/hercshot.py build/qmp.sock 0x70000 /tmp/herc.png   # LINEAR = HERCSEG*16
python3 tools/mouse.py --screen 720x348 build/qmp.sock click X Y
```

`HERCSEG` is a segment and `hercshot` takes the linear address; the missing
zero is the commonest mistake. Full recipe and the four ways to get it
silently wrong: `docs/HERCULES-TESTING.md`.

**`VIDEO=`/`RTC=` are tracked by a stamp file**, so a knob-built kernel is a
*different* kernel. Rebuild knob-free before committing or `make
check-images` reports STALE:

```sh
rm -f build/os8088.img build/os8088-360.img && make && make check-images
```

---

## Sound

`make test-snd` is `make test` plus a wav capture at `build/snd.wav`,
finalized when QMP `quit` stops QEMU — so **run `tools/sndcheck.py` only
after `quit`**, or you measure a partial file. The capture is stream-on time,
not wall time: a silent boot yields an empty file, which is a pass for
`--expect-silence` rather than a broken harness.

Without `ADLIB=1`/`SB16=1` there is no card, the tone route falls to the PC
speaker, and that is what gets captured:

```sh
make test-snd TESTAPPS=build/fmtest.img
# launch FMTEST, then:
python3 tools/qmp.py build/qmp.sock 'sendkey b' 'sleep 2' 'quit'
python3 tools/sndcheck.py build/snd.wav 880          # -> dominant 880.0 Hz
```

The two gate packages are the mechanical checks. Neither ever ships on the
apps disks — each rides its own scratch image.

```sh
# AdLib: click once. The patch sets carrier MULT=2, so a keyed 440 must SOUND
# at 880 - that doubling is the assertion, and it only holds if the caller's
# patch bytes reached the operator registers.
make test-snd ADLIB=1 TESTAPPS=build/fmtest.img
python3 tools/sndcheck.py build/snd.wav 880          # -> dominant 880.0 Hz

# Sound Blaster: click once for a synthesised 1 kHz square, staged in 20
# chunks and played for 2 s.
make test-snd SB16=1 TESTAPPS=build/sbtest.img
python3 tools/sndcheck.py build/snd.wav 1000         # -> 2.00 s at 1000.0 Hz
```

The window says which half failed: FMTEST shows `K` (both verbs fine), `P`
(patch refused) or `N` (note-on refused), and a bare `N` means the frequency
never reached the driver. SBTEST shows `g:` grant and `o:` open.

`make test ADLIB=1` (without `-snd`) is the same card with no capture — the
right thing when you want to watch the driver attach rather than measure a
tone. **With no card the probe correctly finds nothing**, which is the right
answer and not the one you are trying to test; `sound.drv` ships on the boot
disk and `drv_boot` loads it before the first paint, so a driver that failed
to attach announces itself by opening the Control Panel on its Drivers page.

Depth, including the underrun and capture edge cases: `docs/SOUND-PLAN.md`
Phase 4.

---

## Hard disks

QEMU has an ATA disk at 1F0h and SeaBIOS gives it to int 13h as drive 80h, so
**both rungs of the driver's transport ladder (SPEC.md §52.1) are testable
here** — and so are the partitioner, the formatter, the mount and the desktop
zone, end to end:

```sh
make test HDD=40                 # a blank 40MB raw IDE disk, KEPT between runs
# System menu -> Control Panel -> Drivers -> tick Hard Drive
# -> the 'Hard Drive' page appears in the list; select it
# -> Partition -> New -> Write -> Close
# -> Format -> Format -> Close
# -> Mount        ... one icon per FAT partition: HDD C, HDD D, ...
rm -f build/hdd.img              # start over from a blank disk
```

**Pair it with a host-side read**, exactly as the floppy write path is paired
with `os88disk.py --verify`: the in-kernel checks and a structural read catch
different bugs, and every bug found while building this was found by the host
half.

**`tools/os88disk.py --verify` is a FLOPPY fsck and will refuse a hard-disk
partition** - it checks `BPB_FATSz16 <= 10` and a real floppy geometry, both
of which a 31MB FAT16 volume legitimately breaks (SPEC.md 18.2 rule 10 drops
the cap for a driver-backed volume; 18.8 is why). Read the partition by hand
instead. The snippet below prints the BPB; the one after it is the test that
actually catches things - **compare every copied file against its source byte
for byte**, which is how a chunk-size bug that truncated a 116KB file to
64,512 bytes was found, with no error reported anywhere on screen.

```sh
python3 - <<'EOF'
d = open('build/hdd.img','rb').read()
e = d[446:462]                                   # partition entry 0
base = int.from_bytes(e[8:12],'little')
print('type', hex(e[4]), 'lba', base, 'secs', int.from_bytes(e[12:16],'little'))
b = d[base*512:base*512+512]                     # its boot sector
print('jmp', b[:3].hex(), 'spc', b[13], 'fatsz', int.from_bytes(b[22:24],'little'),
      'tot16', int.from_bytes(b[19:21],'little'), 'fstype', b[54:62])
EOF
```

And the one that earns its keep - a FAT16 reader that walks a partition and
compares every file it finds against the original on the host. `tools/` has
no hard-disk fsck, so this is it:

```sh
python3 - <<'EOF'
d = open('build/hdd.img','rb').read()
def vol(lba):
    b = d[lba*512:lba*512+512]
    return dict(spc=b[13], rsvd=int.from_bytes(b[14:16],'little'), nfat=b[16],
                root=int.from_bytes(b[17:19],'little'),
                fatsz=int.from_bytes(b[22:24],'little'), base=lba)
def rd(v,s,n=1): o=(v['base']+s)*512; return d[o:o+n*512]
def fat(v,c):
    off=c*2; b=rd(v, v['rsvd']+off//512); return int.from_bytes(b[off%512:off%512+2],'little')
def dirsec(v): return v['rsvd']+v['nfat']*v['fatsz']
def clus(v,c): return dirsec(v)+(v['root']*32+511)//512+(c-2)*v['spc']
def ents(v, first=None):
    raw = rd(v, dirsec(v), (v['root']*32+511)//512) if first is None else b''
    c = first
    while first is not None and 2 <= c < 0xFFF0:
        raw += rd(v, clus(v,c), v['spc']); c = fat(v,c)
    out=[]
    for i in range(0, len(raw), 32):
        e = raw[i:i+32]
        if not e[0]: break
        if e[0]==0xE5 or (e[11]&0x3F)==0x0F: continue
        out.append((e[:11].decode('latin1'), e[11],
                    int.from_bytes(e[26:28],'little'), int.from_bytes(e[28:32],'little')))
    return out
def content(v,c,size):
    o=b''
    while 2 <= c < 0xFFF0 and len(o) < size: o += rd(v, clus(v,c), v['spc']); c = fat(v,c)
    return o[:size]
v = vol(int.from_bytes(d[446+8:446+12],'little'))     # partition 0
for n,a,c,sz in ents(v):
    print(n, sz)
    if a & 0x10:
        for n2,_,c2,s2 in ents(v,c):
            if n2.startswith('.'): continue
            want = open('build/'+n2[:8].strip().lower()+'.o88','rb').read()
            print('   ', n2, s2, 'OK' if content(v,c2,s2)==want else '*** MISMATCH')
EOF
```

**Persistence: which half needs the panel closed, and which does not.** Mount
and Unmount write `SYSTEM.CFG` on the spot (SPEC.md 51.9 verb 2), and the
write packs the LIVE state - the driver-wanted bitmap included - so quitting
QEMU with the Control Panel still open is a fair test of the mount: reboot and
Disk A, Disk B and every hard-disk volume should be on the desktop with no
clicks at all. **A geometry typed by hand is the deferred half**, staged on
every `+` and written at the panel's teardown (SPEC.md 31.8), so *that* one
does need the window closed before the quit - and a run that skips it reboots
with the probe's numbers back, which reads exactly like the editor not
persisting. Close the window, then quit, then `make test HDD=40` again.

Worth testing once as a pair, because it is the property the blob exists for:
untick the driver, close the panel, reboot (no driver, no icons), then tick it
again - the volumes come straight back, having round-tripped through a boot
where nothing could read them.

Both dirty a **tracked, shipped artifact** - `build/os8088.img` gains
`SYSTEM.CFG` - so `rm -f build/os8088.img build/os8088-360.img && make` before
committing, exactly as for a floppy write test.

What QEMU cannot show: the **MFM** rung — rung 0 against a real XT controller's
ROM rather than SeaBIOS — and the 8-bit-bus behaviour that gates rung 1 off an
8088 in the first place. 86Box ships the XT ST-506 family (IBM/Xebec, DTC
5150X, WD1002A-WX1 and the Seagate ST-11M/R); confirm the exact `hdc =` key
with the launch-and-`kill -TERM`-and-read-back trick above, because 86Box
rewrites its config with what it actually accepted.

**And check the desktop on CGA**, always: `make test VIDEO=cga HDD=40`. A third
drive zone does not fit above the dock on a 200-line screen and wraps into a
second column to the left (SPEC.md §26.1) — which is invisible on VGA and
therefore exactly the kind of thing that ships broken.

## Everything not shipped lives in `tests/`

`tests/` holds every package that is not shipping software, and it is **not**
`apps/`. Nothing under it is built by `all`, no artifact of it is tracked,
and none of it reaches a shipped floppy — so a normal build and every image
the project ships are exactly what they were before it existed.

Two kinds live there, and the difference is what they assert.

**Gates** answer pass/fail against a capability, and are the mechanical
checks referenced throughout this document:

| Package | Asserts | Run it with |
|---|---|---|
| `fmtest` | the AdLib FM surface (SPEC.md §34.2/§51.4) | `make test-snd ADLIB=1 TESTAPPS=build/fmtest.img` |
| `sbtest` | the Sound Blaster streams (§34.5/§34.6) | `make test-snd SB16=1 TESTAPPS=build/sbtest.img` |
| `filetest` | the write path (§18.4) | `make test TESTAPPS=build/filetest.img` |
| `fsxtest` | fullscreen exclusive (§53): keys 0–8 cycle every mode with an identifying pattern, `x` runs a same-mode bracket, `t` keys a duration-0 tone for the §53.3 legs; the window shows the `fsx_caps` mask (01EF/000F/0011 by adapter) and the last result (`K`/`R`/`F`/`S`) | `make test TESTAPPS=build/fsxtest.img` (also under `VIDEO=cga` / `VIDEO=herc`; `make test-snd` + two instances for the sound legs) |
| `stackprobe` | the 256-byte task-stack margin (§8) | `make test TESTAPPS=build/stkprobe.img` |
| `trklog` | not a gate — a **recorder**. Tracker itself, built with `-DTRKLOG`, logging one record per system tick and writing it to `TRKLOG.TXT` (SPEC.md §45.14) | `make test SB16=1 TESTAPPS=build/trklog.img` |

`benchlib.inc` is the one shared source under `tests/` — the timing loop, the
48-bit arithmetic, the report arena and the file writer that `gfxbench` and
`sysbench` both use. It is shared rather than copied for the reason
PERFORMANCE.md Part 6 rule 7 gives: two harnesses that disagree is how three
of the four sizing bugs in this project were found, and two harnesses that
were copy-pasted cannot disagree.

`trklog` is the odd one out and worth reading the shape of before writing
another like it. It is not a separate program: it is `apps/tracker` assembled
a second time with `-DTRKLOG`, so the thing being measured is the shipped code
and not a copy of it that can drift from it. The hooks in `apps/tracker` are
every one of them inside `%ifdef TRKLOG`; the shipped `TRACKER.O88` carries no
records, no claims and no D/W keys. Recipe:

```
make test SB16=1 TESTAPPS=build/trklog.img   # builds the disk on demand
# double-click Disk B, launch TRKLOG.O88
# X    XT mode (5,500 Hz - what the 4.77MHz floor machine boots with)
# L    load BEVERLY.MOD (it is on the same disk), which starts playback
# D    arm the log       -> the status line counts 'LOG nnnn /1024'
# F    fullscreen; let it run through a few pattern boundaries (~9 s each)
# Esc  back to windowed  (W is refused in a bracket - the file API is
#                         UI-callback-only, SPEC.md 53.7)
# W    write TRKLOG.TXT to B:  -> 'Wrote TRKLOG.TXT'
```

Read it back off the image from the host with a FAT12 extractor, or mount
`build/trklog.img` — it is an ordinary floppy. **The disk must not be
write-protected**, for the same reason the bench disks must not be. The log
buffer is a heap claim taken at D and given back at D, so an unarmed log costs
no memory and cannot split the heap.

`filetest` also has a fragmented-volume variant, `build/filetest-frag.img`,
and its results are worth pairing with the host-side fsck — the in-kernel
free-space check and `python3 tools/os88disk.py --verify <img>` catch
different bugs.

`stackprobe` is the one gate whose QEMU answer is NOT the answer: its worker
0xCC-fills its own stack slice, spins so every interrupt the machine takes
lands there, and reports the live high-water mark against 256 (the canary
line confirms it watched the word SPEC.md §8 protects). SeaBIOS services its
interrupt entries on an internal stack, so under QEMU only this kernel's own
tick and mouse handlers land on the slice (~90 bytes with the worker's own
frames); a real IBM BIOS runs int 09h on the current task's stack and STIs
early, so the tick and the mouse nest ON TOP of it. `make stackprobe` builds
`build/stkprobe360.img` for exactly that trip: boot `os8088-360.img` on the
real machine (or `make xt`), launch `STKPROBE.O88` off the probe floppy, hold
a key down, mash the mouse, play a Tracker module — then read High water.
Measured on a real 5150 (Hercules, 20MB MFM) under a floppy-to-hard-disk
copy plus typematic plus mouse: **112 of 256, canary intact, 217 samples** —
the ~20 bytes over QEMU's 92 being the BIOS nesting this gate exists to see.

**Benchmarks** answer *how fast*. `fontbench` prices the *primitive* (SPEC.md
§6.1.1): one ten-character run drawn four ways, as the hand-written
`gfx_fill` + `font_str` pair and as one `font_run`, each byte-aligned and
again at x+5. `typebench` prices the *keystroke* (§11.94): 40 characters typed
into a 40-cell line with the whole line redrawn after each, which is what
`np_redraw` does to its dirty band. `gfxbench` prices the *whole drawing
surface* on whichever adapter it booted on; `sysbench` prices the *machine*
underneath it. All four ride one disk.

```sh
make bench                                                 # build the two disks
make test                            TESTAPPS=build/bench.img
make test VIDEO=cga                  TESTAPPS=build/bench.img
make test VIDEO=herc HERCSEG=0x7000  TESTAPPS=build/bench.img
```

### `gfxbench` and `sysbench` — the two that write a file

The first two benchmarks answer one question each and fit on a screen. These
two answer forty, and a CGA screen holds seventeen lines — so they page
(`Space`/`PgDn`/`PgUp`/`Up`/`Dn`/`Home`/`End`, or a click) and they **save
the whole report to a text file** with `S` or the Bench menu. `R` re-runs.
That file is the deliverable: it is meant to be carried off the machine and
pasted into [PERFORMANCE.md](../PERFORMANCE.md).

| what | where it lands |
|---|---|
| `gfxbench` on VGA / Hercules / CGA | `GFXVGA.TXT` / `GFXHERC.TXT` / `GFXCGA.TXT` |
| `sysbench` | `SYSBENCH.TXT` |

**The file goes to the CURRENT volume and directory** (SPEC.md §19.2), which
right after launching a package off the bench disk is that disk's root — so
the ordinary thing works. It means the bench floppy must **not** be
write-protected, and on 86Box that is the `wp://` prefix the config keeps
growing back.

`gfxbench` is ONE package for Hercules and CGA on purpose. Both are the same
1bpp software renderer over four different numbers (SPEC.md §39.3), which it
reads from `OSAPI_VIDEO` at run time; two sources would be two chances to
drift, and the whole value is that the Hercules column and the CGA column are
the same measurement. It runs on VGA too, for contrast.

What it measures, and why in that shape:

- **Raw bandwidth first**, because everything above it is explained by it.
  The same loop — 32 rows of 64 bytes — runs against plain RAM and against
  the framebuffer, so the ratio between those rows IS the bus penalty with
  the loop, the addressing and the string instruction identical on both
  sides. Word write, byte write, word read and byte read-modify-write are
  priced separately because the kernel's inner loops use all four and on an
  8-bit bus they are not proportional.
- **Primitives at TWO SIZES** wherever the cost has a per-call part and a
  per-pixel part (8×8 against 64×64, 8 px against 256 px). One size cannot
  separate them, and pricing a rect the harness never drew needs both terms.
  The derived block does that subtraction and prints its inputs beside it.
- **`gfx_blit4` twice** — a solid source and a four-pixel-run source. That
  pair is PERFORMANCE.md Part 3 item 4 made mechanical: a run coalescer that
  has quietly stopped coalescing shows as a ratio near 100, and one number
  could never show it.
- **The same ten characters as `fontbench`**, so the two harnesses check each
  other for free.

`sysbench`'s headline is the one PERFORMANCE.md Part 2 has been quoting from
memory: **8086-nominal clocks against a real 8088**, per instruction class,
with the book figure and the ratio printed beside the measurement. The
interesting part is that the ratio is not one number — it is near 1.0 for
`mul`, which is execution-bound, and much worse for `nop`, which is starved
by a 4-byte prefetch queue behind an 8-bit bus. It also prices RAM
bandwidth, the clock ladder, the API's far-call floor, **what the kernel's
own interrupts cost per second of ordinary work** (the same workload timed
with interrupts off and then on), and the floppy — twice, because the first
read pays the motor spin-up and quoting either figure alone misleads.

Three things about reading their output:

1. **A method-`t` row of 0 counts finished inside one 55 ms tick.** True on a
   fast host, and never true on the machine this is for.
2. **A `!` flag means one iteration came within a third of the PIT wrap.**
   The number is still probably right; it is no longer trustworthy.
3. **Under QEMU almost every row is noise**, and two are worse than noise:
   the retrace period (QEMU's status port toggles on every read so a poll
   always terminates) and the VRAM rows under `HERCSEG=` (B0000 is unmapped,
   so those rows measure plain RAM and the bus ratio reads 100). Both say so
   in the report's own header. `build/bench360.img` on real iron is the
   point of the exercise.

Every one of these images builds on demand — `TESTAPPS` is a prerequisite of
the test targets, so naming one is enough. `make bench` exists for building
the two benchmark disks *without* booting, e.g. to write `bench360.img` to a
real floppy.

The rest of this section is about the benchmarks, because a gate's answer is
a boolean and does not rot the way a number does.

**The `testing` branch still exists, and is now for developing these**, not
for holding them. A harness takes several rounds to get right — two of the
three corrections below were to the measuring apparatus, not the thing
measured — and that iteration does not belong in `experimental`'s history. A
finished harness lands here; the midway artifacts of writing one stay there.

**Treat every number as provisional and cite where it came from.** This is
not a caveat about tidiness — the figures have been wrong in ways only real
hardware exposed, twice in quick succession: the elapsed counter was 16-bit
and a real run overflowed it, and then the ratio overflowed because it came
from counts shifted right by 4 that real rows exceed. A third correction went
the other way: SPEC.md §6.1.1 predicted `font_run`'s true win sat near the
framebuffer-traffic figure, and a 4.77 MHz 8088 with a Hercules card measured
1.30x — the *instruction* figure to three digits. Per-cell overhead dominates
the byte-writes it guards. So a benchmark number quoted without a date and a
machine is worth very little.

**Under QEMU the numbers are not time at all.** QEMU runs the guest at host
speed, so add `-icount shift=3,sleep=off` and the PIT counts guest
*instructions* — reproducible and machine-independent (±1 count across runs),
but not microseconds, and it understates the mono win because what alignment
removes is disproportionately memory traffic. The Makefile has no knob for
it; override the whole command instead, which is the shortest correct form:

```sh
make bench
make test TESTAPPS=build/bench.img \
     QEMU="qemu-system-i386 -icount shift=3,sleep=off"
```

`build/bench360.img` on a real 4.77 MHz 8088 (or 86Box) is where the PIT is a
wall clock and the microsecond column means microseconds. That is where these
numbers are worth taking. A VGA run measures the *fallback* path by design —
`font_run`'s fast path is mono-only.

One trap if you ever track a bench artifact: `make check-images` reads its
list from `git ls-files build`, so a tracked image `all` does not build reads
as **ORPHAN** and one it builds differently reads as **STALE**. Leaving them
untracked is what lets `all` stay free of them. Tracking one would force it
back into `all` — which is exactly the arrangement this folder replaced.

---

## Modelling the old machine from a fast one

Everything above is about *where* to run a test. This is about the systematic
error in running it anywhere but the target, and it has now cost four bugs, so
it is worth stating as a method rather than a warning.

**The container is roughly three orders of magnitude faster than a 4.77 MHz
8088.** Every constant you size while looking at QEMU is sized against the
wrong machine, and the failures are not proportional — they are structural,
because the constants encode *ranges*:

| what was sized against QEMU | what a real XT did |
|---|---|
| a 16-bit elapsed counter, one subtraction start-to-end | rows are 1.5M counts; it lapped silently into a small plausible number |
| `>= 32768 means the run overran` | most legitimate rows are 32768..65535; it discarded them |
| a ratio computed from `counts >> 4` | `>> 4` is still 90,000; it overflowed the word and printed 696 for 134 |
| `OSAPI_WM_GROW` on every keystroke | free in the emulator; a visible flicker in a 13×13 corner at 33 ms a keystroke |

The rule that falls out: **when a harness has to hold a range, size it from the
slowest machine it will ever run on, not the one in front of you.** A 32-bit
accumulator folded per iteration costs a few instructions and cannot lap; a
16-bit one sized "generously" against QEMU is wrong by 20x on hardware.

### Three calibration numbers, so an estimate needs no machine

All three are measured on the 4.77 MHz IBM 5150 this project targets
(`tests/gfxbench` and `tests/sysbench`, PERFORMANCE.md Part 9), not modelled:

- **About 756 µs of fixed cost per `gfx_*` drawing call**, before it draws a
  single pixel. `GFX_PIXEL` and an 8-pixel `GFX_HLINE` measured within 1 µs of
  each other, on Hercules *and* on CGA, whose framebuffers are 13% apart — so
  the floor is CPU-side (~3,600 clocks of far call, lock, clip test, dispatch
  and `gfx_rowbase`), not bus-side. **A redraw is priced by how many primitive
  calls it makes, not by how many pixels it covers.** That is the single most
  useful sentence in PERFORMANCE.md and it is the one this project spent years
  not believing.
- **About 1 ms per 8×8 glyph cell.** Four independent measurements agree:
  `fontbench` 10.09 ms per ten cells, `typebench` 33.3 ms per forty,
  `gfxbench` 901 µs for one `font_char` and 915 µs per cell across a whole
  78×34 page. A 40-cell line redraw is ~36 ms, so a keystroke that redraws its
  row costs about that.
- **Instructions are the better proxy, not framebuffer traffic.** SPEC.md
  §6.1.1 predicted the opposite and was corrected by measurement: per-call and
  per-cell overhead dominate the byte-writes they guard. The general form is
  the **8088 instruction floor** — 4.34 clocks per instruction *byte*, which
  is what the prefetch queue can deliver — so an 8086 cycle count under-reports
  an 8088 by anywhere from 1.01× to 4.34× depending purely on encoding length.

Two figures that used to sit here were wrong and are worth knowing were wrong,
because they are still quoted in old commit messages: a framebuffer
read-modify-write is **79.6 clocks, not ~30**, and only about 7 of those are
the bus; and the "add 20–40% for the 8088" rule of thumb was replaced by the
instruction floor above. The back buffer's ~24× flush-to-render ratio was
never measured on hardware and cannot be — double buffering is VGA-only
(SPEC.md §32) and this machine has no VGA.

The full table is [PERFORMANCE.md Part 2](../PERFORMANCE.md), together with the
standing budget every redraw path in the tree has already been measured down
to. Check a change against that table before concluding it is free.

### Count work, don't time it — QEMU is exact about the first and useless at the second

The container's clock tells you nothing about a 4.77 MHz machine, but the
*amount of work* the guest does is identical on both, and QEMU will report it
exactly. So when the question is "is this slow because it does too much?",
**instrument a counter and read it over QMP** rather than reaching for 86Box:

```nasm
; kernel/font.inc, in .text so the offset is fixed
dbg_cells:  dw 0
...
font_run_cell:
    inc word [cs:dbg_cells]
```

```sh
nasm ... -l /tmp/k.lst   &&  grep dbg_cells /tmp/k.lst     # -> 0x1E78
python3 tools/qmp.py build/qmp.sock 'xp /2xh 0x2478'       # KERNEL_SEG*16 + off
```

`h` is a word; HMP's `w` is four bytes. Editing any include **before** the one
holding the counter moves the offset, so re-derive it after every rebuild.

A **package** can write the same counter — `mov ax, KERNEL_SEG / mov es, ax /
inc word [es:0x1E7E]` — which is how a walk inside an app is counted without
knowing the segment its region was claimed at.

This is what settled the Note Pad question (SPEC.md §27.4). A user reported
typing getting slower as a note grew and inferred that more than one character
was being redrawn. The cell counter said **2 cells per keystroke at every note
length and every window width** — the drawing was already right — and a
counter in the layout walk said 404 iterations, growing linearly. The cost was
in a place no screenshot could show and no wall clock here could measure.

Two rules that fall out of it:

- **Measure before redesigning.** The obvious hypothesis (the delta span is
  growing) was wrong, and the fix it would have produced was a fix to working
  code.
- **A counter is not a timer.** It tells you how many times something ran, not
  what it cost. Multiply by the calibration numbers above to get milliseconds,
  and say that you did — ~500 8086 cycles per walk iteration is a reading of
  the instruction stream, not a measurement.

### Prefer a self-checking harness to a careful one

Three of the four bugs above were caught by **one number on screen
contradicting another**, not by inspection:

- `typebench`'s CHAR row does 1.33x `fontbench`'s PAIR work, so it cannot be
  the smaller number — yet PAIR reported the overrun sentinel and CHAR
  reported 15551. Only one reading is consistent, and it identified the lap
  and its size.
- The ratio was wrong while the counts and milliseconds beside it were right,
  which localises the fault to the one column computed differently.

So put **redundant quantities on the screen**: a raw count *and* a derived
time, two rows whose relative sizes are known in advance, a ratio you can
recompute by hand from the columns next to it. A harness that reports one
number per run is one you have to trust.

### What the emulator cannot show at all

Not "shows inaccurately" — cannot show. **Do not call all of these
"flicker"**: they are three defects with three causes and three fixes, and
lumping them together is how one gets fixed and the others ship
([PERFORMANCE.md Part 1](../PERFORMANCE.md) is the full vocabulary).

- **A visible redraw, which is not a flicker at all.** A window's whole
  content, or the whole screen, being painted again. On real hardware you
  *watch it happen* — the fill sweeps, then the text lands row by row — and
  on a heavy application (Paint, the Task Manager, a full Disk window) that
  is **seconds**, not a flash. Under QEMU it is microseconds and a
  screendump taken either side of it is identical. This is the single most
  expensive mistake available in this codebase, and the one an emulator is
  least able to warn about.
- **A double-draw flash.** Anything drawn twice — background, then content.
  The erase-and-letter pair is the canonical case: it leaves a line blank
  between the fill and the last glyph, tens of milliseconds on an XT,
  several display frames. The area is smaller than a full redraw so it reads
  as a flash rather than a wait, but it is still **very plainly visible**, on
  every keystroke. Note Pad's per-keystroke flash (SPEC.md §27.2) and the
  grow box's were both found by a person watching the real machine, and
  neither appears in any timing column, because the two methods take
  comparable *time* and differ in what is on screen during it.
- **Perceived latency and input overrun.** Whether a human can outpace the
  redraw — and start losing keystrokes to a full BIOS buffer — is a property
  of the real machine's speed against a real person's typing. A view that
  costs more than its frame budget reads as a *hung* display rather than a
  slow one, which is why the tracker stops animating its grid on a tier-0
  machine (SPEC.md §45.9.1).

And one the emulator reports as a **success**, which is worse:

- **An optimisation that kept its shape and lost its substance.**
  `gfx_blit4`'s first version emitted one call per run exactly as designed,
  and decoded every pixel individually inside the scan — 75–90 clocks a pixel
  against `repe scasb`'s seven and a half, both written down rather than
  measured. **Under QEMU it measured as exactly as fast**, because QEMU models
  no 8086 timing: every screendump was right and every test passed. That is
  why the cycle counts in `kernel/vga12.inc` are written down rather than
  measured, and why rewriting something whose *reason* is speed means
  verifying the reason survived, not the structure.

  This entry used to quantify it as "a 448×280 repaint went from about a
  quarter of a second to over two". Those two figures came from the same two
  written-down cycle counts and were never measured; the primitive has since
  been priced on the target machine, and it costs **`runs × 0.5 ms`** — so
  what a blit costs is decided by how *flat* the art is, not how big it is
  (SPEC.md §5.4, PERFORMANCE.md Part 9). The lesson above survives the
  correction intact. The numbers did not.

For all of these, the emulator's role is to prove *correctness* before you
burn a floppy. The judgement is made on hardware.

**Wall clock here is still a lower bound worth having.** Paint's figures
under `make run-640` — a full-canvas flood fill in ~4 s, a 448×280 4bpp BMP
open in ~8 s — are useful precisely because they are already slow *in the
emulator*. A real 8 MHz machine is several times slower and a 4.77 MHz 8088
slower again, so anything measured in seconds here is out of reach on the
target. That is how JPEG was ruled out (docs/PAINT-NOTES.md), and the
AT-class 86Box targets (`make 286`, `make 386sx`, `make 386`) are the honest
middle of that range.

## What 86Box is genuinely for

Real period hardware: the video **detection probe**, the 6845 programming, a
4.77 MHz 8088's actual timing, a real CGA or Hercules card, an SB 2.0 on an
XT bus, and the 286/386 machines. `make xt`, `xt-640`, `xt-cga`,
`xt-hercules`, `xt-sound`, `286`, `286-sound`, `386sx`, `386`, `386-sound`.

It is not installed in the web container and needs BIOS ROMs, so those
targets do not run there. Nothing above them does.

Two 86Box-specific traps worth knowing before blaming the OS: it silently
clamps `mem_size` to the machine's maximum, and a `wp://` prefix on an
`fdd_0N_fn` path mounts that floppy write-protected — which the OS then
faithfully reports as "Write protected", and which means `SYSTEM.CFG`
settings do not survive a reboot.
