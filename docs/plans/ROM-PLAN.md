# Part of the system in ROM — what a 5150's sockets can hold, and what that buys

**INVESTIGATION. NOTHING IS BUILT.** It was asked for on branch `rom-plan`, cut
from `elendilon` at `351461a` (build 358). The original Macintosh kept part of
its system in a 64KB ROM. The question is whether os8088 can do the same with
the ROM sockets an IBM PC already has, in two forms:

1. **The kernel.** Put ~32KB of kernel code in ROM so it stops costing resident
   RAM. Look at two shapes: a normal disk kernel that DETECTS the ROM and does
   not load that part, and a ROM-REQUIRED build if detection is too expensive.
   Answer this for both `kern_big` and `kern_small`.
2. **System applications.** Put the Task Manager, the Control Panel and two
   common drivers (sound, hard disk) in ROM. `kern_small` has no drivers, so
   it may get another application instead.

The measurements are in [docs/reports/ROM-COLD-2026-10-04.md](../reports/ROM-COLD-2026-10-04.md).
The instrument is `tools/os88romfix.py`, which re-derives every fixup and
section figure below in about nine seconds on any built tree.

---

## 0. The answer

| | `kern_big` | `kern_small` |
|---|---:|---:|
| `.cold` (kernel code with its own CS, SPEC.md 2.6) | **37,998** bytes, rung 38,400 | **24,383**, rung 24,576 |
| `KERN_SIZE` today → with `.cold` in ROM | 99,328 → **60,928** | 65,536 → **40,960** |
| heap on a 128KB machine (arithmetic) | — (boots on 196KB today) | 62.5 KB → **86.5 KB** (+38%) |
| fits the four BASIC sockets (32,752 usable, §1.3) | **no**, 5,246 over | **yes**, 8,369 spare |
| fits all five spare sockets (40,960) | yes, with a layout catch (§3.6) | yes |
| far-pointer fixups if `.cold` changes segment | **257**, all clean | **212**, all clean |
| fixups inside `.cold` itself | 10 (8 far calls) | 2 |
| packed sectors a ROM machine need not read at boot | ~69 | ~45 |

Eight findings carry the plan.

1. **Only `.cold` can go into ROM, and it is ROM-clean today.**
   - `.text` cannot go. The near model makes `CS = DS = KERNEL_SEG` the
     contract for every task and every API cell (§2).
   - `.cold` already runs with a CS of its own. `tools/os88ovlchk.py` already
     refuses data in `.cold` and any segment taken from CS. A disassembly of
     both kernels finds **no byte of `.cold` written at runtime**, no ISR in it,
     and no vector pointing into it.
   - The one CS reference is on `kern_big`, `call [cs:fdlg_htab+bp]`
     (`kernel/fdlg.inc:647`). It READS a constant table, which a ROM serves
     perfectly well.
2. **The segment is the whole problem, and it is mechanical.**
   - `COLD_SEG` is an equate, so a different segment is a set of patched words.
   - Assembling each kernel with the segment at two values and diffing proves
     the set is complete: 257 words on `kern_big` and 212 on `kern_small`,
     **every one a plain 16-bit immediate that moved by exactly the delta**.
     There are zero non-linear diffs.
   - Of the ten inside `.cold`, eight are cold-to-cold far calls and two are
     sentinel stores. All of them can be rewritten not to name the segment, so
     one ROM image can sit at **any** segment (§3.2).
3. **There is one real defect, and every ROM design has to fix it first.**
   - Nine emitted copies on `kern_big` (seven on `kern_small`) test
     `cmp word [spl_fseg], COLD_SEG / jbe`.
   - That test means "the boot blob is gone" only because `.cold` sits
     *below* the heap. At a ROM segment such as F600, every blob segment
     compares below it, so the overlay and the splash would never be called.
   - The fix is `je` against the sentinel. It costs 0 bytes (§3.3).
4. **Detecting the ROM at runtime is cheap in resident bytes.**
   - It costs an estimated **30–50 resident bytes**, not kilobytes. The probe
     and the patcher are transient: the probe sits in stage 2's slack and the
     patch table travels in the ROM itself.
   - What it really costs is engineering in three boot loaders, plus a ladder
     reorder (§3.4).
   - The ROM-required build is therefore not needed to save cost. Its case is
     simplicity, and giving 35 clusters of the system disk back (§3.5).
5. **A ROM is welded to the kernel's LAYOUT, not to the commit count.**
   - `.cold` carries no build number. Two assemblies that differ only in
     `BUILD_NUM` have byte-identical `.cold` (only `.text` and the module
     headers move).
   - But `.cold` names `.text` routines and data by offset, so any change that
     moves one of them re-cuts the ROM. Over the last month an image lasted
     about 2.5 integration commits on `kern_big` (§3.8).
   - **A stable ROM ABI is out of reach** (§3.8). The ROM is a RELEASE
     artefact, and detection falls back to RAM when the two disagree.
6. **System applications in ROM save TIME and the FLOPPY, not RAM — except
   kernel modules** (§4).
   - A package (`.O88`) or driver (`.DRV`) runs `CS = DS = its own segment`
     with its bss inside the image. It can only be COPIED out of ROM.
   - Their ABI is versioned (`PKG_FMT`, `DRV_VER`), so that ROM **survives
     kernel rebuilds**. This is the opposite of form 1's weld, and it makes
     them the right thing to burn.
   - The Control Panel is a kernel MODULE (`CTRL.DRV`). Modules run `.cold`'s
     contract, so they can execute in place and save their whole claim. They
     carry form 1's weld instead.
7. **The 5150 has SIX 8KB sockets, not four, and five of them are spare
   (§1).**
   - U28 at F4000 is empty. U29–U32 at F6000–FDFFF hold Cassette BASIC. U33
     holds the BIOS.
   - Replacing BASIC is allowed: the BIOS's BASIC checksum is non-fatal on
     every 5150 revision.
   - But `int 18h`, the "no boot disk" path, jumps to F600:0000. Whatever is
     burned there MUST begin with a safe stub.
8. **`kern_big` built for a ROM is smaller resident than `kern_small` is
   today** (60,928 against 65,536).
   - On a machine with the ROM, the second kernel's reason to exist may go
     away.
   - That is arithmetic and not a measurement. §3.5.1 says what has to be run
     before anyone says it out loud.

---

## 1. The hardware

### 1.1 The IBM PC 5150

| socket | address | stock content |
|---|---|---|
| U28 | F4000–F5FFF | **empty** |
| U29 | F6000–F7FFF | Cassette BASIC, part 1 |
| U30 | F8000–F9FFF | BASIC, part 2 |
| U31 | FA000–FBFFF | BASIC, part 3 |
| U32 | FC000–FDFFF | BASIC, part 4 |
| U33 | FE000–FFFFF | BIOS (10/27/82 on the owner's machine) |

**The recollection in the request was "4 slots, 3 BASIC, one open", and it is
two short.**
- There are four BASIC chips and one empty socket. With U33 left alone, that
  is **40KB of addressable ROM space, contiguous from F4000 to FDFFF**.

**Chip type:**
- The stock parts are 24-pin 2364-type mask ROMs.
- A 2764 or 27C64 EPROM is 28-pin with a different pinout, so it needs a
  "2364 adapter" or a board such as the epictronics IBM-5150-BIOS-Adapter.
- Motorola's MCM68766 is pin-compatible with no adapter.
- No jumper option is known. Board revisions (16–64KB against 64–256KB) are
  not known to differ in the ROM sockets, but this is UNVERIFIED.

**What POST does to these sockets** (from the BIOS listings):

| | 04/24/81, 10/19/81 | 10/27/82 |
|---|---|---|
| option-ROM scan | none | C8000–F5FFF in 2KB steps, **which includes U28** |
| BASIC checksum (each 8KB module must sum to 0) | failure beeps, boot continues | failure prints `F600 ROM` (or F800…), boot continues |
| `int 18h` | F600:0000 | F600:0000 |

### 1.2 The IBM PC/XT 5160

- **1982 board:**
  - U18 is 32KB: BASIC at F8000–FDFFF plus the BIOS.
  - U19 is 8KB, mirrored four times across F0000–F7FFF, so F4000 is a mirror
    and not a free socket.
  - Replacing BASIC means re-burning the chip that carries the BIOS.
- **1986 boards:**
  - POST checksums the **whole 64KB from F0000 to FFFFF and HALTS** on a
    mismatch.
  - Every burn therefore has to re-balance a checksum byte inside the BIOS
    chip.
- **The XT's motherboard is a worse host than the 5150's.**

### 1.3 The layout the motherboard window forces

`int 18h` is the deciding fact. A 5150 with no floppy in the drive retries
four times and then executes F600:0000. If `.cold` were laid flat from F400:0,
that address is the middle of whatever proc landed at offset 0x2000. The
machine would run it with whatever is in DS. That is not a hang to shrug off:
it is arbitrary kernel code, and the file system's code is most of `.cold`.

So the window is two pieces and not one:

```
F6000  header + int 18h stub         16-64 bytes  (prints "os8088 ROM build N -
                                                   insert a system disk", int 19h)
F6010  .cold, segment F601           up to 32,752 bytes   (U29-U32)
F4000  a second segment, F400        up to 8,192 bytes    (U28, optional)
```

Two more things the image builder owns:

- **The per-chip BASIC checksum.**
  - The code spans the chip boundaries, so no chip has a free byte unless one
    is planted.
  - The answer is a one-byte `ROMPAD` slot, legal in `.cold` only after an
    unconditional transfer, placed at the start of every cold file.
  - No file is over 7,798 bytes, so every 8KB window contains at least one
    slot. That is about 20 bytes of `.cold`.
  - The builder sets each chip's slot so the chip sums to zero, and POST then
    stays quiet.
  - `os88ovlchk.py`'s no-data rule learns the one macro. The fallback is to
    accept a non-fatal `F600 ROM` line at every power-on.
- **U28 on the 10/27/82 BIOS.**
  - The scan reads F4000, F4800, F5000 and F5800 for `55AA`.
  - A code byte pair there is a 1-in-65,536 chance per boundary. It would turn
    into a `F400 ROM` error, or a far call to F400:0003.
  - The builder refuses such an image and re-cuts it with a shifted pad.

### 1.4 The alternative: an ISA ROM board

The ISA option-ROM window (C8000–EFFFF) avoids every problem in §1.3:
- no BASIC checksum;
- no `int 18h`;
- any segment;
- no 2364 pinout.

The Lo-tech 8-bit ROM boards carry 32 or 64KB of flash at a DIP-selected base.
They can be **re-flashed in the machine** with the XT-CF utility, which turns
§3.8's weld from "re-burn four EPROMs" into "run a program". The owner's 5150
already has the ST11M's ROM at C8000, so D0000–DFFFF is the natural window, and
64KB there holds all of `kern_big`'s `.cold` with room for the form 2 set.

### 1.5 Speed

There is no penalty on the target:
- The 5150 adds no wait states to memory. ROM is 250 ns against an 838 ns bus
  cycle, and an 8-bit ISA ROM is zero-wait unless the card pulls I/O CH RDY.
- DRAM refresh holds the BUS, not the RAM, so ROM fetches pay its ~5.56%
  exactly as RAM does.
- The owner's 5150 already measures SixPakPlus ISA RAM and planar RAM within
  0.02% of each other (PERFORMANCE.md Part 8.2).

The cost is on an AT-class machine:
- An unshadowed 8-bit ROM is slower there. That is `FONTSLOW`'s finding about
  a VGA BIOS (SPEC.md 6.0.1).
- A detecting kernel can therefore choose: run from ROM on `CPU_8086`, and
  copy into RAM above that tier when the RAM is there.
- `OSAPI_CPU_INFO` is the fact to test (PERFORMANCE.md rule 7).

### 1.6 The emulators

**MartyPC:**
- Every machine has an optional ROM feature `"custom"` (`machine_config.rs`
  at the pinned `e15cb04`).
- A `[[romset]]` with `provides = ["custom"]` and
  `{ filename = "OS88.ROM", addr = 0xF6000 }` maps it read-only. A filename
  entry skips the md5 check.
- `tools/martypc/build.sh` already copies `os8088_field_roms.toml` into
  `configs/rom_definitions/`, so the row is one more file.
- The 5150 sets here (`ibm5150_82_v4`, `glabios_pc`) are BIOS-only, so
  F4000–FDFFF is empty and free today.

**86Box's `ibmpc82`:**
- It loads `roms/machines/ibmpc82/ibm-basic-1.10.rom` (32KB at F6000) with no
  hash check, so swapping the file works.
- It has **no knob for U28**.
- Its generic ISA ROM board takes a file at C0000–EE000, which covers §1.4.
- **`vm/pc5150/86box.cfg` carries an `[IBM PC (1981)] bios = ibm5150_5700051`
  section belonging to the `ibmpc` machine.** Under `machine = ibmpc82` it is
  ignored, so that VM runs the default 10/27/82 BIOS with BASIC enabled. That
  is unrelated to this plan and was found on the way.

---

## 2. What can go into ROM, section by section

| section | can it be ROM? | why |
|---|---|---|
| `.text` | **no** | The near model: CS = DS = `KERNEL_SEG` for kernel code, every task and every `OSAPI_*` cell (`push cs / pop ds`). A ROM `.text` is a different kernel, not a relocation |
| `.bss`, `.lowbss`, `.vgabuf` | no | written |
| `.ovl`, `.ovlw` | pointless | already transient: they cost no RAM by the first desktop |
| **`.cold`** | **yes** | CS of its own, DS = `KERNEL_SEG`, no data, never written (§3.1) |
| on-demand modules (`CTRL.DRV`, `FDLG.DRV`, …) | **yes, mostly** | `.cold`'s contract with a different segment; the writes into their own image are listed in §4.1 |
| packages, drivers | **copy only** | CS = DS = own segment, bss in the image |

---

## 3. Form 1 — the kernel's `.cold` in ROM

### 3.1 Why `.cold` is ROM-clean today

SPEC.md 2.6's cold contract was designed for a different reason (relieving
`KERN_CODE_MAX`). Four rules already enforced by `tools/os88ovlchk.py` are
exactly what a ROM needs:
- no data in `.cold`;
- nothing may take a kernel segment from CS;
- no `.text` table dispatches to a cold body;
- macro arguments are checked as call sites.

A disassembly of both kernels' `.cold` bytes confirms it:
- no write through CS;
- no self-modification;
- no `iret`;
- no memory operand naming a `.cold` label, except `fdlg_htab`'s read on
  `kern_big`.

`kern_small` has no CS reference at all.

**`.cold` needs no change to stop writing to itself, because it never does.**

### 3.2 The segment, measured

`tools/os88romfix.py` copies `kernel/` aside and decouples `COLD_SEG` (the
segment the code executes in) from the ladder rung it occupies in RAM. It then
assembles each kernel at `COLD_SEG` = F601 and F702 and diffs the pair:

| section | `kern_big` | `kern_small` |
|---|---:|---:|
| `.text` | 94 | 60 |
| `.ovl` (blob) | 24 | 7 |
| `.ovlw` | 7 | 3 |
| `.boot2` | 1 | 1 |
| **`.cold` itself** | **10** | **2** |
| on-demand modules | 121 (`.modl` 49, `.modh` 26, `.modc` 21, `.modu` 19, `.modf` 6) | 139 (`.modp` 63, `.modl` 43, `.modd` 15, `.modu` 12, `.modf` 6) |
| **total** | **257** | **212** |

**Every site is a clean word that moved by exactly the delta.**
- No arithmetic on the segment reaches an instruction, and no length changed.
  A patch table is a complete description, and the double assembly is its
  proof of completeness. That is the same trick the old relocating EXE linkers
  used, and the build can run it as a gate.
- Of the `.text` sites, 24 are `OSAPI_FCELL` expansions and 23 are one-line
  thunks.
- Data words holding the segment:
  - `api_coldseg`;
  - `spl_fseg` and `spl_ifseg`;
  - `mod_disarm`'s `COLD_SEG:mod_gone` seed;
  - `compress.inc`'s `cmz_tfp`.

**The ten inside `.cold` on `kern_big`:**
- Eight are cold-to-cold far calls: `ld_pkg_byname`, `fcp_xfer` ×2,
  `fdlg_seed`, `fdlg_reap_x`, `desk_select`, `sc_open` and `hb_ok_x`.
  - `push cs / call near x` replaces each one.
  - That is 4 bytes against 5, so the change SAVES 8 bytes.
  - It needs one line in `os88ovlchk.py`: `push cs` in `.cold` is legal when
    the next instruction is a near call to a far-returning cold body.
- `mod_disarm.slot` stores the segment. It becomes `mov [di+2], cs`, via AX.
- `dsk_xfer.notch` is a sentinel compare, which is §3.3.

`kern_small` has only those last two. After that wave **no `.cold` byte names
its own segment**:
- The ROM image is the same at F601, F401, D000 or E000.
- The kernel patches `.text` to whatever segment it FOUND.
- One image serves the motherboard and an ISA board.
- `os88romfix.py`'s "inside `.cold`: 0" becomes a gate that keeps it that way.

### 3.3 The defect every ROM design must fix first

These sites test `cmp word [spl_fseg], COLD_SEG / jbe` to mean "the blob has
been given back, or was never there":
- `kernel.asm:5375`, `5385`, `5404` (the `SPLCALL`/`OVLCALL`/`OVLCALLC`
  bodies);
- `kernel.asm:6739` (`spl_gate`);
- `dock.inc:214`;
- `sched.inc:2359` (inside `sch_isr`);
- `memory.inc:501`.

The test is correct only because `COLD_SEG` is numerically below every heap
segment. `spl_fseg` only ever holds the seed (`COLD_SEG`) or a live blob
segment, so `je` is the same answer in the same number of bytes, and it does
not care which side of the heap `.cold` lives on. It is worth taking as wave 0
whatever else is decided: it is a latent assumption, and nothing documents it.

### 3.4 Option A — one disk kernel that DETECTS the ROM

**Orientation: bake the RAM segment, and carry the patch in the ROM.**
- `KERNEL.SYS` is assembled exactly as today. A machine with no ROM pays the
  probe and nothing else.
- The ROM image is `.cold` (segment-independent per §3.2) followed by a TAIL:
  - the header and the image hash;
  - the patcher, about 40 bytes;
  - the fixup table for the `.text`, `.ovl`, `.ovlw` and `.boot2` it was cut
    against (126 words on `kern_big`, 71 on `kern_small`).
- The ROM brings the code that adapts the kernel to it. It can, because a
  matching hash means it was cut against exactly this `.text`.

**The probe** goes in stage 2, `.boot2`:
- It must run before the kernel is expanded, because what it decides is
  whether `.cold`'s blocks are expanded at all.
- `.boot2` is 2,478 bytes against `OVL_AT` = 2,624 on both kernels, so there
  are **146 bytes of slack**.
- It scans a short list of candidate segments: F600, F400, then D000–EF80 in
  2KB steps. For each it checks the signature, compares the 8-byte hash
  `KERNEL.SYS` was built with, and sets `[rom_cold]`.
- Estimate: 40–60 bytes, transient.
- Integrity is a 16-bit sum over the image, ~0.7M cycles = **~145 ms**
  (ESTIMATE). That is against the ~2 s the ROM saves, so it is worth paying.

**The ladder has to move.**
- `.cold` sits between the image and the FAT window, so on a ROM machine its
  RAM would be a hole in the middle of the kernel.
- The fix is to put it at the top:

  ```
  today:      [image][COLD][FAT][LOW][VGABUF] heap
  Option A:   [image][FAT][LOW][COLD][VGABUF] heap
  ```

  - With no ROM, behaviour is byte-for-byte today's.
  - `.vgabuf` stays topmost, so a mono machine still drops the heap floor
    under it (SPEC.md 39.22).
- With the ROM:
  - `mem_floor_ax` seeds the floor at `COLD_RAM` instead.
  - On a mono machine, that also covers the unused `.vgabuf` above it.
  - On VGA, the planar decoder's buffers move down to `COLD_RAM` and the floor
    sits one rung above them. `VGABUF_SEG` is named by ONE instruction
    (`vga12.inc:2568`), so that is one more fixup.
- Cost: about 9 bytes in `mem_floor_ax` and one byte of `.bss`.

**The file layout follows the ladder:**
- The file becomes `[blob][.text][bss gap][.ovlw at FAT][LOW gap][.cold]
  [modules]`.
- The gaps are zeros, which LZ4 packs to nothing. The `.bss` gap is already
  shipped this way (`COLD_START`).
- `.cold` becomes its own block run with its own destination. Today
  `os88kz.py` lays block *i* at `head + i × BLK`, and the change is one base
  switch.
- A ROM machine then reads `KZ_SECS` minus `.cold`'s sectors, and expands
  nothing for it.

**What the boot saves** (ESTIMATE, from 2.9.13's field figures of ~27.2 ms a
sector and 39.9 cycles an output byte):

| kernel | sectors not read | time not spent |
|---|---:|---:|
| `kern_big` | ~69 | ~1.9 s + ~0.3 s of decode |
| `kern_small` | ~45 | ~1.2 s + ~0.2 s |

**Three loaders have to learn it:**
- stage 2 off a floppy;
- `boot/boothd.asm` (the hard disk, 2.9.13.5);
- the `NOKZIP=1` raw path, which can simply read the gaps since it is a
  diagnostic knob.

**Modules:**
- They far-call `.cold` 121/139 times.
- `os88mod.py` emits each module's site list into its file, about 2 bytes a
  site.
- `mod_need` adds `[cold_seg] − COLD_SEG` to each one when it is non-zero.
  Estimate: 20 bytes of `.cold` plus 2 bytes of `.bss`.

**Hibernate:**
- The image excludes ROM by construction, because it saves conventional RAM
  (SPEC.md 87).
- Its header gains the `.cold` hash, and a resume on a different ROM, or none,
  refuses.
- That code is in `HIBER.DRV`, which is not resident.

**The resident bill:**

| item | bytes |
|---|---:|
| the floor conditional | ~9 |
| the module delta | ~20 |
| `[rom_cold]` / `[cold_seg]` | ~3 |
| the sentinel fix | 0 |
| the eight `push cs` calls | −8 |
| **total, per kernel** | **~25–45 (ESTIMATE)** |

**This is the finding that answers "if the earlier option is too expensive":
it is not.**
- It is a few dozen resident bytes, paid by every machine whether it has a
  ROM or not.
- The real price is the loader work, and it is shared by the 360KB, 720KB,
  1.44MB and 1.2MB geometries, by the hard-disk loader, and by §18.93.1's
  boot canary. The canary's `KSIG_OFF` band rests on the file layout this
  changes, so it has to be re-derived.

### 3.5 Option B — `CROM=1`, a ROM-required kernel

- `COLD_SEG equ ROMSEG` (a constant chosen at build), and `COLD_PARA` leaves
  the ladder.
- `KERNEL.SYS` carries no `.cold`.
- Modules are assembled against the ROM segment.
- There are no fixups and no probe beyond a hash check in stage 2. A mismatch
  REFUSES with the ROM's build and the kernel's build on the glass.

Against Option A:
- **It saves the disk as well as the RAM.** About 35KB packed comes off the
  system disk, roughly 35 clusters at 360KB.
- **It saves the same boot time**, because there is nothing to skip.
- **It is simpler.** There is no ladder reorder: `.cold`'s rung is simply
  zero.

What it costs is a fourth kernel artefact:
- It is `KERN_EMU`'s shape (an additive variant with its own build tree and
  `kernsize` baseline).
- It has its own system disks.
- It needs a `buildmatrix` row to keep it assembling.
- And it is useless to anyone without the ROM, which Option A never is.

#### 3.5.1 What `CROM=1` does to the two-kernel split

`kern_big` with `.cold` in ROM has a `KERN_SIZE` of **60,928**, smaller than
`kern_small`'s 65,536 today.

Guard 5's question is whether stage 1 can read the image under the top of a
128KB machine. Arithmetically it would answer yes. `KERN_BUDGET` already says
`kern_big` RESIDES in 128KB.

So **on a machine with this ROM, `kern_big` may run on 128KB with more heap
than `kern_small` has now.** That is unmeasured, and what decides it is the
boot-time claims (`dirw`, the read-ahead) that no assembler sees.
`tests/small128.py`'s shape, run on a `CROM=1` `kern_big` on the floor
machine, is the measurement. Until it is taken, this is a sentence about
arithmetic.

### 3.6 `kern_big` does not fit 32KB

`.cold` is 37,998 bytes against the BASIC window's 32,752. There are three
ways out.

**(a) Use U28 as well, as a second segment.**
- 40KB in one flat segment is ruled out by §1.3's stub.
- So U28 becomes segment F400 holding a second cold set.
- Calls between the two sets go far. This is the same cut as (b), at an
  8,192-byte limit instead of 32,752.

**(b) Split `.cold` into `.crom` and a RAM `.cold`.** This is the shape the
request suggested. The call graph is measured (the report has every edge):
- The FILE SYSTEM cluster is one dense component, with `files.inc` making 79
  calls into `kernel.asm`'s shims and `diskw.inc` making 40 into `disk.inc`.
- The natural ROM half is everything except the leaves below:
  - `files`, `disk`, `diskw`, `memory`, `fdlg`, `assoc`, `desk`, `driver`,
    `filecp`, `mod`, `drvvol`;
  - **32,465 bytes**.
- The RAM half is the leaves:
  - `apps`, `vga12`, `loader`, `lz`, `hiber`, `desksc`, `blank`, `ctrl`,
    `menu`, `wm`, `instance`, `dock`, `extmod`, `clone`, `ui`;
  - **5,533 bytes**.
- **163 jump and call sites cross the cut.**
  - 55 of them go through `kernel.asm`'s `cw_*` shims. These are a few bytes
    each and can be duplicated in both halves.
  - The remaining ~108 become far calls with a far entry per target:
    estimated **300–500 bytes**, split across both halves.
- That leaves the ROM half with almost no growth room. The cut should
  therefore sit nearer 30KB: move `assoc.inc` (1,941 bytes) to RAM too, and
  leave ~2.7KB of headroom.
- RAM saved: **~32KB, not 38**.

**(c) An ISA ROM board** (§1.4).
- All of `.cold` goes in one segment.
- There is no split, no stub and no checksum dance.

**Recommendation for `kern_big`: (c).**
- Take (b) only if the motherboard sockets are a requirement in their own
  right, a period-correct machine with nothing in its slots.
- If so, measure (b)'s cut before building it, by putting the edge count
  from the report into `os88ovlchk.py`'s call-graph pass.

### 3.7 `kern_small` fits with 8,369 bytes to spare

`kern_small`'s 24,383 bytes go into the BASIC window. The spare is almost
exactly the three modules every `kern_small` session reaches:

| module | image |
|---|---:|
| `FDLG.DRV` | 1,240 |
| `FILECP.DRV` | 2,269 (+36 of stack tail) |
| `CTRL.DRV` | 4,441 |
| **total** | **7,950** |

That leaves 419 bytes. Executing in place (§4.1), they cost no heap at all. On
a 128KB machine that is ~6 KB more of the arena while the Control Panel or a
Save dialog is open.

### 3.8 The weld

- `.cold` names `.text` by offset: **121 far calls into `cw_*` shims** on
  `kern_big` (68 on `kern_small`), and every DS-relative read of kernel data.
- So a `.text` change that moves any of those re-cuts the ROM, even when no
  cold byte of SOURCE changed. The commit count alone does not (§0 finding 5).
- How often it happens in practice is the report's history table. Over the
  82 commits on `elendilon`'s first-parent line since 1 September,
  `kern_big`'s `.cold` changed **32 times** and `kern_small`'s **23**. A burned
  image therefore lasts about **2.5 integration commits on `kern_big` and 3.4
  on `kern_small`**, which is roughly a day of this project's pace. App and
  document merges leave it alone; kernel work re-cuts it. **A ROM tracks a
  RELEASE, not the integration branch.**
- A ROM that survives kernel work would need `.cold` to reach `.text` only
  through a pinned table, and kernel data only at pinned offsets. That is a
  second internal ABI over thousands of references. **It is refused here.**
- What makes the weld livable instead:
  - **Option A falls back to RAM on a mismatch.** A stale ROM costs its saving
    and never a boot.
  - **`make rom` is a release artefact** beside the floppies.
  - **A flash board re-flashes in the machine** (§1.4).

---

## 4. Form 2 — system applications in ROM

### 4.1 Three loaders, three answers

| path | runs as | from ROM | what it saves | version tie |
|---|---|---|---|---|
| package `.O88` (Task Manager) | CS = DS = own segment, bss after the image; on `kern_big` the compactor moves it (`W_SEG`) | **copy only** | load time, the floppy; **no RAM** | `PKG_FMT`, so it survives kernel rebuilds |
| driver `.DRV` (sound, hard disk) | CS = DS = own segment, bss shipped in the image, writes its own variables | **copy only** | load time at boot, the floppy; **no RAM** | `DRV_VER`, so it survives rebuilds |
| kernel module (Control Panel = `CTRL.DRV`) | CS = module, DS = `KERNEL_SEG` (`.cold`'s contract) | **execute in place** | the whole claim (12KB big / 5KB small) plus the load | `MOD_H_BUILD` = the commit count, and `MOD_STAMP` |

**Packages and drivers execute in place only with a new ABI.**
- That would be a split code and data format: a CS word separate from `W_SEG`
  in the window, instance, worker and timer records; every package with its
  data in its own section and no `push cs / pop ds` (13 files have one); and
  `os88pkg.py` and the C `crt0` changed with it.
- Making DS a RAM copy of the whole image saves nothing, so the split format
  is the only version that pays. It is out of scope here and is named so it
  is not re-derived.

**Modules have three blockers:**
- **The stamp.**
  - `mod_check` refuses a module whose `MOD_H_BUILD` is not the running
    commit count.
  - A burned module is refused one commit later, even when its bytes are
    still right.
  - A ROM arm has to compare the cold-layout hash instead. That is the same
    key as form 1, and the right one, because a module is welded exactly as
    `.cold` is.
- **Writes into the image.**
  - `kern_big`'s `CTRL.DRV` holds `cpc_buf` inside its image and writes
    `cp_fdno`.
  - `HIBER.DRV` writes through CS about 48 times.
  - `kern_small`'s `FILECP.DRV` keeps a 36-byte stack in its claim tail.
  - `FDLG`, `CLONE`, `FORMAT`, `DOCK`, `EXTD` and `kern_small`'s `CTRL` only
    READ through CS.
  - So on `kern_small`, three moves make all three daily modules ROM-able:
    put `FILECP`'s stack back in `.bss` (+36 resident), and that is the whole
    list.
- **`mod_need` claims and frees.**
  - A ROM arm sets the row's segment to the ROM's and runs the check.
  - It skips the zeroing and never frees.
  - Estimate: 30–60 bytes of `.cold`, which is itself in ROM if form 1 is.

### 4.2 Sizes

| item | packed | image (+bss) | RAM claim today |
|---|---:|---:|---:|
| `TASKMGR.O88` | 7,133 | 8,223 + 1,707 | 10,240 |
| `CTRL.DRV` (`kern_big`, ships plain) | 11,649 | 11,649 | 12KB |
| `SOUND.DRV` | 5,474 | 6,307 + 176 | 7KB |
| `HDD.DRV` | 2,994 | 3,568 + 16 | 4KB |
| `HDDTOOL.DRV` (its on-demand half) | 13,995 | 17,398 | 17KB |
| `TASKMGR` small | 4,314 | 4,980 + 1,317 | 6,656 |
| `CALC` small | 4,428 | 5,312 + 413 | 6,144 |
| `NOTEPAD` small | 10,653 | 12,724 + 1,159 | 14,336 |
| `CTRL.DRV` (`kern_small`) | 4,071 | 4,441 | 5KB |
| `FILECP.DRV` (`kern_small`) | 2,061 | 2,269 + 36 | 3KB |
| `FDLG.DRV` (`kern_small`) | — | 1,240 | 2KB |

The `kern_small` module rows come from reports and SPEC.md, and are not
re-measured here.

### 4.3 Getting the bytes out

There are two shapes, and they suit different loaders.

**A ROM VOLUME, for packages and drivers.**
- It is a third transport beside `DVK_BIOS` and `DVK_DRV`/`DVK_FILE`: a
  `dsk_xfer` arm that serves a sector as `rep movsw` out of ROM and refuses
  every write. Estimate: 30–50 bytes.
- It needs a boot-time scan and a volume row.
- Behind it, a read-only FAT12 image in ROM. The whole file layer works
  unchanged: by-name reads, `'CZ'` expansion (so files ride packed), and a
  Disk window that shows `R:`.
- Overhead is ~1.5–2 KB of ROM for the BPB, FAT and root directory, plus
  cluster slack.
- **It must never become the system volume**, because the Control Panel
  writes `SYSTEM.CFG` there. Drivers and modules search it BEFORE
  `[dsk_bootvol]`, through the one seam both use (`drvvol.inc`'s
  `drv_mounted`/`drv_find`).
- `RAMDISK.DRV` is the shape to copy, but not the vehicle. It is a driver, so
  it is loaded off the system disk, which is circular, and `kern_small` has
  no drivers at all.
- The Task Manager can skip even the volume: `OSAPI_PKG_START`'s image arm
  (`ld_pkg_start_x`) already launches a package from a far pointer by COPYING
  it. It wants the image stored unpacked (8,223 bytes), and the menu item's
  "try ROM first" is a few dozen bytes.

**An XIP DIRECTORY, for modules.**
- The ROM header lists module number, segment offset and entry count.
- `mod_need`'s ROM arm points the row at it.
- There is nothing to copy, so there is no volume.

### 4.4 What it buys

**Time, on every launch.**
- A Control Panel open is measured at **1,441–1,570 ms and 4 reads**
  (SPEC.md 2.8.7). A ROM serves it in microseconds.
- Drivers in `SYSTEM.CFG` load at boot, so a ROM `SOUND.DRV` and `HDD.DRV`
  take their reads off every power-on.

**A function, on `kern_small`.**
- `FDLG.DRV` and `FILECP.DRV` are read off the boot volume and **refuse when
  the system disk is out** (SPEC.md 38.0, 22.3.0).
- On a one-drive 128KB machine, a Save As onto a data floppy therefore does
  nothing today.
- In ROM, it works. Of everything in this file, that is the clearest reason
  to do form 2 on `kern_small`.

**RAM, for modules only** (form 2's packages and drivers save none).

### 4.5 Recommended sets

**`kern_big`, form 2 alone:**
- Task Manager + `CTRL.DRV` + `SOUND.DRV` + `HDD.DRV`.
- 29,747 bytes unpacked, 27,250 packed. That fits the BASIC window, or a 32KB
  board.
- `HDDTOOL.DRV` (17KB) does not fit beside them and is not needed to USE a
  disk.
- **On the motherboard, form 2 competes with form 1 for the same 40KB.**
  Doing both means a board.

**`kern_small`:**
- Form 1 plus the three XIP modules fill the BASIC window (§3.7).
- U28's 8KB then holds the Task Manager (4,314 packed, 4,980 unpacked) as the
  "another app". Calc as well does not fit once a ROM volume's overhead is
  paid.
- If only one form is taken on `kern_small`, it should be **form 1**: 24.5KB
  of resident heap back on a 128KB machine is the largest single gain in this
  document.

---

## 5. Recommendation and order of work

| wave | what | bytes | why first |
|---|---|---|---|
| **W0** | §3.3's nine `jbe` → `je`; §3.2's eight `push cs` calls and the two stores, so `.cold` names no segment of its own; `os88romfix.py`'s "inside `.cold` = 0" as a fast row | −8 resident | Correct on today's machines, removes a latent ordering assumption, and every later wave needs it |
| **W1** | MartyPC `"custom"` ROM row; `make rom` (header, int 18h stub, per-chip `ROMPAD` sums, U28 `55AA` check); a ROM-only boot that finds the image and prints its build | 0 | The harness every later wave is tested on; `tests/` gets a row that boots with and without the ROM |
| **W2** | **`CROM=1` on `kern_small`** | resident −24,576 | The biggest relative gain (+38% heap at 128KB), the smallest change (no reorder, no fixups), and the floor machine already has its gate (`tests/small128.py`) |
| W3 | `kern_small`'s three modules XIP (stamp by hash, `FILECP` stack to `.bss`, `mod_need` ROM arm) | +36 `.bss`, +30–60 `.cold` | Fixes Save As with no system disk in a one-drive machine |
| W4 | Option A: ladder reorder, `.cold` as its own block run, probe in `.boot2`, patcher in the ROM tail, module delta, hibernate hash | ~25–45 resident | The one-disk-kernel the request asked for; only worth it once W2 has shown the ROM on iron |
| W5 | `kern_big`: on an ISA board, Option A or `CROM=1` as built; on the motherboard, §3.6(b)'s split, cut measured first | — | |
| W6 | Form 2's ROM volume for packages and drivers on `kern_big` | ~50–100 `.cold` | The set that survives kernel rebuilds |

**What the owner decides, because no measurement can:**
1. **Motherboard EPROMs with adapters, or an ISA flash board.**
   - Only the board takes all of `kern_big`'s `.cold`, or both forms at once.
   - Only the board re-flashes in place, which is what makes §3.8's weld
     cheap.
2. **Whether losing Cassette BASIC is acceptable.** PC-DOS's
   `BASIC.COM`/`BASICA.COM` stop working on that machine.
3. **Whether a ROM matched per release is acceptable**, given §3.8's history
   numbers.

## 6. Open, unverified, and what would settle each

| question | settles it |
|---|---|
| Do the 16–64KB and 64–256KB 5150 boards wire U28–U32 identically? | a board photo or the schematic for each |
| GLaBIOS's scan range, and what its `int 18h` does with no BASIC | its source (the 5150 profiles here run it) |
| The boot saving (§3.4's table) | a `BOOTPROF=1` boot on the 5150 with and without the ROM |
| `CROM=1` `kern_big` on 128KB (§3.5.1) | `tests/small128.py`'s shape on that kernel |
| §3.6(b)'s real far-call cost | build the split; `kernsize` reads it |
| The 1986 XT BIOS's 64KB checksum with a foreign U19 | the listing; MartyPC has the ROM |
