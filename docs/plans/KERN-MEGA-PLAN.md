# `kern_mega` — a 286+ protected-mode kernel

**Status: M1 IS UNDER WAY, AND kern_mega BOOTS INTO 286 PROTECTED MODE ON QEMU** (section 10.1) - plus 2.4.1's CS-write ratchet (2026-10-17, branch `protected-mode`,
cut from `elendilon` at `c783a6a`). The owner asked what a 286+ protected-mode
build would take: one with room for the kernel to grow to 512KB, though
nothing requires it to. They asked three things:

* what has to be different to take advantage of protected mode;
* what MUST be different for it to run at all;
* how much of it can be shared with `kern_big`.

This file answers those from three surveys of this tree: segment arithmetic in
`kernel/`, BIOS/ROM dependence across `kernel/` and `drivers/`, and the package
ABI across `apps/` and `drivers/`.

**Every count below comes from regex heuristics over the source.** Read them
as the size of a population, not as an exact list. Every cycle figure for the
286 comes from Intel's 80286 datasheet and is **not measured here**. The one
field figure used, the cost of a reset round trip on the Victory 286, is
measured and its source is named.

---

## 0. The answer, in eight lines

1. **What protected mode buys is not room for the kernel. It is room for the
   kernel *outside the 640KB*.** A real-mode kernel can already be 512KB:
   `.cold` is a second segment today, and nothing stops a third. What it
   cannot do is run code above 1MB+64KB, so every byte it grows is a byte the
   packages lose. kern_big already spends the HMA on `.cold` (SPEC.md 2.10.7);
   that is the 64KB real mode can reach, and it is used. Past it, only
   protected mode lets kernel code live in extended memory. Neither LOADALL
   nor a loaded CS base survives an interrupt, so neither is an alternative
   (section 6).
2. **A 286 cannot leave protected mode except by resetting the CPU.** It also
   has no V86 mode. Every BIOS call is therefore a reset round trip, measured
   at **412 µs** on the Victory 286 (docs/plans/LOADALL-PLAN.md). Or it gets
   replaced by our own driver. Today's kernel makes 65 `int` calls across 8
   vectors and chains the ROM's `int 08h` and `int 09h` on every tick and
   every key. That ROM dependence is the largest MUST.
3. **AT-class hardware makes those drivers small.** Every 286 has the same
   765 FDC, 8237 DMA, 8042 keyboard controller, MC146818 CMOS and 8259 pair,
   and normally a WD1003/ATA task file at 1F0h. HDD.DRV's rung 1 already
   drives that task file directly (SPEC.md 52.1). On a 286 the "BIOS
   replacement" is four drivers plus mode-set register tables, not a zoo.
4. **Segment values become selectors, and one design keeps most of the tree
   unchanged.** Map the first megabyte *by identity* in the GDT at 128-byte
   granularity: selector `N` has base `N × 16` for every `N` that is a
   multiple of 8. Then every baked constant (`0x0060`, `0xA000`, `0xB800`,
   `0x0040`, LOW_SEG, every heap base) keeps working, and so does every step
   of `+0x1000`, `+0x800` or `+32`. Code segments and anything above 1MB go in
   the LDT, where selectors can never collide with the identity ones
   (section 3).
5. **Code is not writable in protected mode, and the tree writes through CS a
   lot.** The kernel has **468** writes through a `[cs:]` override and **95**
   `push cs / pop ds|es` pairs. The packages have **~1,064** such writes. The
   kernel's share is mechanical. Some of the packages' share is not: on a 286
   there is no FS or GS to free up, so hot loops that keep their state in CS
   while DS and ES point at a claim or at VRAM have to be restructured.
6. **Packages: ~24 of 58 look clean, ~5 need an SDK fix, ~29 need real
   work.** That is with ring 0 and the identity map. The DOS box cannot run
   *under* 286 protected mode. It can run *beside* it: drop to real mode for
   the bracket, run kern_dos from the HMA, and park the kernel in extended
   memory. That is feasible, ~630KB, and needs no hibernate (2.7).
7. **Overlap with kern_big is high by line count and low by risk.** About
   38% of the kernel's 147,067 lines sit in the 21 files that contain any
   mode-bound code, and roughly a third of those lines are actually bound.
   So something like **85-90% of the kernel builds unchanged** under a
   `KERN_MEGA` define, after a mechanical sweep. What does change is the
   kernel's foundations: the heap allocator, interrupts, the scheduler's
   stack switch, the disk transfer layer, boot, and the module and overlay
   machinery.
8. **The binding cost is not code, it is the test bench.** MartyPC is an
   8088 and runs nothing here. QEMU is a 386+, which can hide 286 mistakes.
   86Box has 286s but cannot be scripted. Nearly every emulator row in
   `tests/suite.py` is a MartyPC row. A kern_mega starts with almost no gate
   behind it (section 9).

---

## 1. What "286 protected mode" gives, and what it does not

| | real mode, today | 286 protected mode |
|---|---|---|
| physical address space | 1MB + the HMA's 64KB | **16MB** (24-bit descriptors) |
| a segment | 64KB, base = value × 16 | 64KB, base and limit from a descriptor |
| segments addressable | 65,536 overlapping windows | 8,192 GDT + 8,192 LDT descriptors |
| code above 1MB | only in the HMA | **anywhere** |
| protection | none | limit checks, read-only code, rings 0-3 |
| paging, V86, 32-bit registers, FS/GS | — | **none, all 386** |
| way back to real mode | — | **CPU reset only** (8042 pulse or triple fault, then the CMOS shutdown byte); `lmsw` cannot clear PE |

The last row decides most of what follows. The fourth row is what the request
is really about.

**How far can a kernel grow today?** The near model puts `.text` and `.bss` in
one 64KB segment (`KERN_CODE_MAX`, 49,047 used). `.cold` is a second segment
of 38,131 bytes. Modules, the boot overlay and the blob are further segments.
Real mode has no 64KB ceiling on the *kernel*. The ceiling is on the kernel
*and the packages together*: kern_big is 98,816 resident bytes that no
package can use. In protected mode the kernel can live entirely above 1MB,
and the 640KB is all heap. For a 512KB kernel that difference is the whole
machine.

**Protected mode still has 64KB segments.** A 512KB kernel is at least eight
code and data segments with far calls between them, which is the `.cold`
pattern repeated. Protected mode gives no flat address space; only a 386
gives that, and only in 32-bit code. So the kernel's *structure* does not get
simpler. Its *placement* is what changes.

---

## 2. What MUST be different for it to run at all

### 2.1 Entering protected mode, and staying in

Stage 2 loads the kernel in real mode as it does now; the loader stays
untouched (the boot code's ~25 `int` sites are real mode by nature). Then,
before `kmain`:

* **A20 open for the life of the session.** XMEM.DRV already proves the gate
  and keeps it open (SPEC.md 41.2). The known hazard, `int 15h AH=87h`
  closing it, goes away with the BIOS.
* **The PIC moves.** IRQ0-7 arrive on vectors 08h-0Fh, which in protected
  mode are CPU exceptions: double fault, #GP, #NP and so on. The master 8259
  must be reprogrammed to 20h or above before `sti`. Real mode never has to
  care about this. Nothing today does it, and reverting it is part of every
  route back to real mode (2.6).
* **A GDT, an IDT and exception handlers.** The handlers must name the fault
  on the glass (CS:IP, the error code, the selector). In real mode, a wild
  pointer corrupts something. In protected mode it is a #GP, and that is
  only an improvement if somebody can read the report (section 5).
* **NMI masked across the switch**, as `xm_arm` and `ub_set` already do
  (SPEC.md 41.4, `apps/os88ub.inc`).
* **No 386 instruction anywhere.** NASM's `cpu 286` is the
  `cpu 8086 -w+error` of this build. The reserved high word of every
  descriptor must be zero: a 386 reads it as base bits 31-24, and a 286
  ignores it, so a careless descriptor works on QEMU and nowhere else.

### 2.2 The BIOS: replace or reflect

Survey result: **65 `int` sites in `kernel/`** —

* `13h` × 19
* `16h` × 17
* `10h` × 16
* `19h` × 5
* `1Ah` × 4
* `11h` × 2
* `12h` × 1
* `15h` × 1

— plus two chains to the ROM:

* `sch_isr`'s `call far [sch_old08]` on every tick. The ROM increments
  40:6Ch, runs the floppy motor-off countdown, and **sends the EOI**.
* `kbm_isr`'s `jmp far [cs:kbm_old9]` on every key. The ROM acknowledges the
  8042, translates scancodes with the shift state at 40:17h, and fills the
  buffer at 40:1Eh, which `ui_task` then polls through `int 16h` on every pass.

On a 286 there are two ways to keep a BIOS service:

* **Reflect it.** Reset to real mode, make the call, re-enter protected
  mode. Measured at ~412 µs fixed on the Victory 286 (the AH=87h figure in
  docs/plans/LOADALL-PLAN.md, attributed there to the reset). For the length
  of the call the machine is in real mode. Any IRQ that arrives needs a
  *real-mode* handler, and kernel data above 1MB is out of its reach.
* **Replace it** with our own driver.

What follows for each service:

| service | today | kern_mega | why |
|---|---|---|---|
| tick, EOI, motor-off | ROM `int 08h` chain | **native** | every 55 ms; reflecting it is 0.75% of the CPU for nothing |
| keyboard | ROM `int 09h` + `int 16h` poll | **native**: an 8042 ISR, a scancode-set-1 table, and our own shift state and buffer | `int 16h` is polled on every `ui_task` pass, so a reflected poll would put a reset in the idle loop. `kbm_isr` already reads port 60h; what is missing is the ROM's translation |
| floppy | `int 13h`, ~400 ms a call with IRQs live (SPEC.md 15.3.8 counted 21 ticks inside one call) | **native**: 765 + 8237 | a reflected `int 13h` is 400 ms in real mode. Pointer, tick and sound would all need real-mode twins, or would stop. The native driver is the cheaper of those two |
| hard disk | HDD.DRV rung 0 (`int 13h`) / rung 1 (ATA PIO, 286-gated) | **rung 1 native, rung 0 reflected with IRQs masked** | rung 1 already takes every BIOS-known drive on a 286 (SPEC.md 52.1.1). Only ROM-only controllers (XT-IDE, SCSI, PicoMEM) need rung 0 |
| video mode sets | `int 10h` AX=0012h / mode 6 / mode 3 / fsx modes | **reflect, IRQs masked**, then replace with register tables | rare and short. CGA and Hercules mode tables are a few dozen `out`s; VGA 12h is ~60 registers |
| font pointer | `int 10h` AX=1130h | read once **before** entering protected mode | it is a boot-time question |
| clock | CMOS rung 1 directly, `int 1Ah` as rung 4 | **CMOS only** | every 286 has the MC146818; rungs 2-4 are XT cards |
| reboot | `int 19h` | **8042 pulse** (reset line), which a 286 needs anyway | there is no warm boot from protected mode |
| equipment, memory size | `int 11h`, `int 12h`, `int 15h` AH=88h | read before entering protected mode | boot-time questions |

**The trap in "reflect everything first, replace later":** a reflected call
runs real-mode code while IRQs arrive. Today's ISRs are real-mode code at
`KERNEL_SEG`, so in principle they could run there. But under kern_mega they
would only work if they were *bimodal*: touching only identity selectors,
never a data alias, and never data above 1MB. OS/2 1.x drivers lived that way,
and it is a lifetime discipline. Making the floppy native removes the one long
reflected call and, with it, every reason for a bimodal ISR. That is why the
floppy driver is a MUST in the first wave and not an optimisation.

### 2.3 Segments are selectors

Kernel survey: **230** loads of DS, ES or SS from a general register.

| source | sites |
|---|---|
| a symbolic constant | 61 |
| zero (the IVT or the BDA through ES=0) | 37 |
| a stored variable | 33 |
| a copy of another segment register | 23 |
| arithmetic immediately before | ~21 |
| a parameter, popped, unknown | ~55 |

Beyond those, `memory.inc` alone has 44 `add`/`sub`/`cmp` lines on
`MC_SEG`/`MC_PARA`/`mem_base`/`mem_top`. There are also linear-address
computations for the DMA 64KB check (`dsk_runcap`, `disk.inc:2157`). Segment
values are also used as owner IDs: `MC_OWN` relies on a segment never
reaching 0xFBxx (`memory.inc:2964`). The identity map in section 3 is what
lets most of this stand. The rest:

* **ES = 0.** The null selector loads but faults on any access. Those 37
  sites are mostly IVT pokes, which become IDT writes, and BDA reads, which
  use selector 0x40.
* **Off-grid arithmetic**: `dec es` in `compress.inc` (9 sites), `loader.inc:1011`'s
  prefix >> 4, `KDS_CDELTA` in `hiber.inc`, and `HMA_SEG = 0xFFFF`. These need
  rewriting. The HMA is dropped outright (section 4).
* **The heap.** A claim returns a segment that *is* its address. Under the
  identity map that stays true for conventional memory. Claims above 1MB get
  an LDT selector (section 3.2).

### 2.4 Code is read-only, and CS is not DS

The near model's founding assumption is CS = DS = `KERNEL_SEG`, for the
kernel and for every package. In protected mode a selector names *one*
descriptor, either code or data, never both. A readable code segment can be
loaded into DS, but only for reading.

* **The kernel**: **473** writes through CS and **105** `push cs / pop ds|es`
  pairs, in 26 files under kernel/ and 5 under drivers/. The original
  survey's 468 and 95 were a coarser grep. The counts are exact now, because
  `tests/unit/t_cswrite.py` counts them and holds them to
  `tests/cswrites.txt` (2.4.1). **The SECTION of a site decides how it
  converts, and the split is lopsided**:

  | section | writes | what it is | kern_mega's conversion |
  |---|---|---|---|
  | `.mod*` | ~390 | on-demand MODULES writing their own image, which SPEC.md 2.8 allows (compress 124, stikmenu 105, ascw 49, hiber 45, shutdown 16, winmod 10, dockmod 9, diskops 6) | each module gets a data alias for its image. kern_mega keeps modules resident (section 4), so this is per-module restructuring and not a rename |
  | `.boot2` | ~41 | stage 2 of the boot, in real mode (splash 37, vidsel 3, desksc 1) | **none**, if the switch to protected mode comes after stage 2, which 2.1 already places it |
  | `.text`, `.cold`, `%macro` | ~42 | ISRs saving SP or state before DS is the kernel's (sched 15, mouse 3), renderer state kept through CS while DS is the caller's (font, vga12), the API's inline cells, the boot spinner, a knob's trace | per site: `push ds / mov ds, [cs:k_dsel]` or a register freed |

  So **the CS-write problem is a module problem, not a kernel-wide one**. The
  resident share is about forty sites. The pairs have three distinct
  meanings, which is why they are not one macro:
  * "DS = the kernel", in an ISR or an API stub;
  * "ES = the kernel", for a routine that takes ES:DI;
  * "DS = my own image", in a driver.

  **The API cells cannot simply grow.** `OSAPI_SLOT` is 8 bytes exactly, and
  the table's offsets ARE the ABI (SPEC.md 20.3). So kern_mega's hot cell
  becomes `OSAPI_XCELL`'s shape (`push bp / mov bp, target / jmp api_pm`,
  7 bytes plus one of padding), with the segment load done once in the
  shared stub. The rare 6-byte cells already go through shared `api_r*`
  routines, so only those change.

  The ISRs that write through CS do so because DS is unknown on entry. They
  become `push ds / mov ds, [cs:k_dsel]`: 17 clocks for the segment load in
  protected mode against 2 in real mode.

#### 2.4.1 The ratchet — BUILT (2026-10-17)

`tests/unit/t_cswrite.py` is in the fast tier, so every `make` runs it.
* A file under kernel/ or drivers/ that is not in `tests/cswrites.txt` may
  use neither idiom.
* A registered file may not exceed its counts, or fall below them: a
  conversion lowers the line.
* `--list` prints every site with its section, which is M1's worklist.

It is a ratchet and not a clean gate for `t_textrules.py`'s reason. kern_big
is correct as it stands, so the only failure worth preventing today is a NEW
site in a file kern_mega will share.

**The macro sweep is NOT done ahead of M1, on purpose.** A macro that
expanded to today's bytes on kern_big would be easy to prove harmless with
`cmp`. But one name cannot carry the three meanings above, the module half is
restructuring rather than renaming, and which sites run before the switch is
decided by where M1 puts the switch. A rename now would write those guesses
into 31 files. The ratchet holds the line instead, and the conversion
happens site by site, once, in M1.
* **The packages**: ~1,064 `[cs:]` writes in 16 packages, plus the shared
  `apps/os88spk.inc` (59), `os88spkfx.inc` (29) and `os88pcm.inc` (4).
  * The worst are pixel (593), weave (153), excitebike (104) and video (84).
  * The emulator cores (c64, apple2, runcpm) keep CPU state in CS because DS
    is the guest's memory.
  * A 286 has no spare segment register to replace CS with, so those loops
    need restructuring, not substitution.
* **Code in a claim.** Overlays and parts are far-called through the
  claim's *data* segment: `cc_ovbind` stamps `[cc_ovseg]` and `cc_ovthunk`
  `retf`s to it (`apps/cc/crt0.asm:1270,1325`). Under kern_mega a claim that
  holds code has to be handed a *code* alias. That is one SDK change and a
  rebuild of six C packages (cword, loom, weave, runcpm, apple2, c64), plus
  `apps/os88partsbody.inc` for the twelve that embed parts.

### 2.5 The package ABI survives, with one exception and one ring

`KERNEL_SEG equ 0x0060` is assembled into every package. All 186
`call KERNEL_SEG:0xNNNN` cells and the 3-byte dispatcher at `seg:000C`
(SPEC.md 20.2) are far calls through constants. **0x0060 is a well-formed
selector**: GDT index 12, TI = 0, RPL = 0.

* Make GDT[12] a *readable code* descriptor whose base is wherever the
  kernel is (base 0x600 for M1, above 1MB from M3), and every
  existing package's call into the kernel works without reassembly.
* Package reads through the callback ES (`[es:bx+W_W]`, 78 sites) work too,
  because readable code can be read.
* What breaks is *writes* through ES = 0x60: 4 in paint and 2 in
  `apps/os88stik.inc` (729, 1262). They are small fixes.

**This is the one exception to the identity map**: 0x60 is code, not data.

**It also fixes the ring at 0.** A call gate ignores the offset of a far call,
so 186 cells behind one selector cannot be gates, and a ring-3 package could
not call `0x60:NNNN` at all. So does port I/O: 22 packages program the video
card directly inside fsx brackets (SPEC.md 53.7). Ring 3 is possible, but
only as a flag day: every cell becomes its own gate selector, every package
is reassembled, and IOPL or an I/O permission policy is decided. Section 5
treats it as a later wave.

Under kern_mega the loader gives each instance **two** selectors: a code
selector for CS and for `W_SEG`'s far calls, and the identity data selector
for DS. A package that compares CS with DS, or registers CS as its data
(`os88stik.inc:629`, `crt0.asm:432`), needs to learn the difference.

### 2.6 What is real-mode by design

* **The DOS box** (SPEC.md 96) runs native real-mode code. It banks and
  rewrites the whole IVT, and its programs call the ROM, program the PIT and
  PICs, and may close A20. It cannot run *under* protected mode on a 286.
  It can run *beside* it, for the length of an fsx bracket. Section 2.7 is
  the feasibility check. The DOS box is one program and not part of this
  design, so 2.7 is a verdict, not a plan.
* **Hibernate** (`hiber.inc`, `hbstub.inc`). The resume stub lives in the
  text framebuffer and reads the image back with `int 13h`. A protected-mode
  image has state above 1MB, so the stub must be able to land it there. Use
  the reset trick: read into conventional memory, then copy up the way
  XMEM.DRV does. This is the last wave, not the first.
* **XMEM.DRV, LOADALL and `ub_set`** (SPEC.md 41.13, 41.15) become
  pointless. Extended memory is just a descriptor away. The video player's
  decode-in-place path is what it is today on a 386, but done properly.

### 2.7 The DOS box: drop to real mode for the bracket — FEASIBLE

The owner's proposal:

* Leave protected mode for the length of the fsx bracket.
* Carry the "real-mode kernel bits" as a `DOS.O88` part that ships only on
  kern_mega.
* Load that part into the HMA.
* Leave the protected-mode kernel parked, untouched, in extended memory.

The program then gets 600+KB without a hibernate. **This holds up, and most
of it is already built.**

* **The real-mode kernel bits exist.** kern_dos *is* that part. It is the
  kernel's own `disk.inc`/`diskw.inc` plus the DOS core, shipped inside
  `DOS.O88` (SPEC.md 96.49, `kerndos/`). Its image rung is
  **33KB** (`KD_IMG_KB`, `kerndos/kdlayout.inc`), so it fits the HMA's
  65,520 bytes with half to spare. `.cold` already runs from the HMA at
  `vstart=0x10` (SPEC.md 2.10.7), which is the precedent for assembling
  kern_dos the same way.
* **What stays in conventional memory**:
  * the IVT and BDA (1.25KB);
  * the mount buffers and stack (`KD_LOW_KB` = 3);
  * the FAT snapshot;
  * a low entry stub.

  The buffers must stay low: `dsk_runcap` already keeps HMA buffers out of
  `int 13h`, because a BIOS computes a 20-bit DMA address. The stub's whole
  job is to re-open A20 before jumping to `FFFF:`, which is how DOS=HIGH
  survives programs that close the gate. **Estimate: ~5-8KB low, so ~630KB
  for the program**, against 584KB through today's hibernate path.
* **The package heap has to go somewhere.** In kern_mega the conventional
  heap is full of packages. Before the drop, the kernel copies the heap up
  into extended memory, and on return copies it back *to the same
  addresses*. Identity selectors mean nothing needs relocating. At the
  Victory's ~0.3 ms/KB that is ~0.2 s each way.
* **The transitions:**
  * **In** is one reset: PIC back to 08h, the BIOS's IVT and BDA banked at
    boot and restored, shutdown code 0Ah, then 40:67 to the stub. ~412 µs,
    once.
  * **Out** is cheap: real mode to protected mode needs no reset, just
    `lmsw` and a far jump.
* **The machine has to be big enough.** It needs extended memory for the
  kernel, the parked heap (up to ~600KB) and the HMA. That is a ~1.6MB
  machine or more. Below that, the hibernate route kern_dos already uses
  stays as the fallback.
* **The risk is not real mode. It is DOS programs that use extended memory
  themselves**: `int 15h` AH=87h/88h users, VDISK-style RAM disks, and
  286 DOS extenders (DOS/16M, Phar Lap 286, Lotus 1-2-3 r3). Today none of
  them can hurt an os8088 that lives in conventional memory. Here they can
  overwrite the parked kernel. Three defences:
  1. Report AH=88h as 0.
  2. Hand out extended memory only through the box's XMS door (SPEC.md
     96.15), from what lies above the kernel.
  3. **Checksum the kernel's extended memory on the way out and on the way
     back in.** On a mismatch, refuse to resume and cold-boot with a message
     that names the program, instead of running a corrupted kernel.
  The checksum costs about 0.3 s per 512KB on a 16 MHz 286, which is an
  estimate. Programs that respect XMS or AH=88h (the ones that worked under
  HIMEM) are safe. A program that ignores both is caught by the checksum
  rather than trusted.
* **Not "every DOS program".** The box's own limits still stand (SPEC.md 96,
  and DOS-EXEC-PLAN's section 10). What changes is the memory and the speed
  of getting in and out: no hibernate write, no kernel reload.

---

## 3. The design that keeps the tree: an identity-mapped first megabyte

### 3.1 The rule

**GDT entry `i` describes base `i × 128` (that is, segment `8i`), limit
64KB, writable data, DPL 0**, for every `i` from 1 to 8191. That covers the
whole first megabyte, so selector `N` means exactly what segment `N` means
today whenever `N` is a multiple of 8.

* The GDT is the CPU's maximum, 8,192 entries, 64KB. It lives in extended
  memory and is built once.
* **The exceptions are the kernel's own named segments**: 0x0060 (the kernel
  and the API table), `COLD_SEG` and `LOW_SEG`. Their entries describe
  wherever the kernel actually is, which is above 1MB (section 4), not
  `N × 16`. 0x0060 and `COLD_SEG` are readable code, and the kernel's writes
  go through data aliases in the LDT. Nothing outside the kernel does
  arithmetic on these three, so leaving the grid costs nothing.
* Entries 1-7 (selectors 0x08-0x38, bases in the IVT) are never loaded as
  data. That makes them free for the TSS, the LDT descriptor and the IDT's
  own alias.

**Which arithmetic this keeps working:** `add seg, 0x1000` (64KB steps),
`add seg, 0x800`, `add seg, 32` (512 bytes), every whole-KB heap base,
`HEAP_SEG` (512-aligned under guard 6), LOW_SEG and FAT_SEG (512-rounded
rungs), `0xA000`, `0xB000`, `0xB800`, `0xB000:8000` aliasing `0xB800`
(`vid_cga_alias`), `0x0040` and `0xF000`. The survey found every heap base
to be a multiple of 32 paragraphs today, so the whole allocator's output is
already on the grid.

**Which arithmetic it does not keep:** anything off the 8-paragraph grid.
That means `base + (addr >> 4)` (`apps/frotz/zmem.inc:137`,
`apps/tracker/trkplay.inc:626`, `apps/runcpm/runcpm.c:734`), `dec es`, and
a PSP at segment + 16 when the segment is not on the grid. These are real
rework, one site at a time.

**What it gives up:** isolation below 1MB. Any code at ring 0 can still load
any identity selector and write anywhere in the first megabyte, *exactly as
today*. What it gains even so:

* **Limits.** Every segment stops at 64KB, so the 16-bit offset wrap that
  real mode allows is a fault.
* **Read-only code.** A wild write into code faults instead of corrupting it.
* **A hard wall around everything above 1MB.**

The kernel's growth lives up there behind LDT selectors, and nothing below
can reach it by arithmetic.

### 3.2 Above 1MB: the LDT

All selectors with TI = 1 are LDT selectors, values ≡ 4 (mod 8). **They can
never equal an identity selector**, so no arithmetic on a conventional
segment can land on one by accident.

* Kernel segments above 1MB, extended-memory claims and code aliases come
  from the LDT.
* Allocation stays below 0xFB00 so `MC_OWN`'s tag range keeps its meaning
  (2.3).
* An LDT selector is **stable across a move**. Compaction copies the bytes
  and rewrites the descriptor base, and nobody holding the selector needs to
  know. That deletes, *for LDT claims*, the whole problem
  docs/plans/HEAP-UNPIN-PLAN.md is about: `MC_RLOC`, relocation procs,
  `mem_rr_tab`, the worker frame that pins a region (SPEC.md 66.6.2), the
  66 kernel words naming a driver image.
* Identity claims keep today's rules, because their selector *is* their
  address.

**A claim over 64KB** (Sheet takes ~99KB) gets consecutive LDT selectors,
each one 8 apart, which is Windows' `__AHINCR` shape. So kern_mega needs one
new SDK constant, `OS88_HUGE_INCR`. In conventional memory the identity map
gives `0x1000` for nothing, which is why the first-wave packages need nothing
new.

---

## 4. What SHOULD differ, to take advantage of it

In rough order of what each one buys:

1. **The kernel moves above 1MB, all of it.**
   * 0x0060 is an *exception* to the identity map (3.1), so its descriptor's
     base can be anywhere. Point it above 1MB and every package's
     `call 0x60:NNNN`, and every callback read through `[es:bx+W_W]`, lands
     in a kernel that has no byte below 640KB.
   * `COLD_SEG` and `LOW_SEG` (the task stacks and disk buffers) work the
     same way. Every 286 DMA address is below 16MB, so the 8237 can still
     reach the buffers.
   * `.cold`, every module and the boot overlay's survivors move above 1MB
     as well.
   * Conventional memory becomes package heap: the ~523KB a 640KB machine
     offers a package today becomes ~600KB.
   * **The modules stay resident.** `mod_need` exists to page `CTRL.DRV` and
     its eight siblings in and out of conventional memory (SPEC.md 2.8). With
     the kernel in extended memory that saving is worth nothing, while the
     disk read and the "system disk required" failure still cost something.
2. **Most of the size machinery is not wanted, and kern_mega should NOT
   carry it.** These all exist because conventional memory is scarce and
   `KERN_CODE_MAX` binds, and in kern_mega neither holds:
   * the HMA `.cold` and its driver pool (SPEC.md 2.10.7, `COLDHMA.SYS`);
   * the ROM `.cold`;
   * the `rp_walk` fixups (257 on kern_big);
   * `mem_unblob`;
   * the `.ovl`/`.ovlw` FAT-window loading.

   Each is a `%ifndef KERN_MEGA` rather than a rewrite. The rung banner
   still applies to the *conventional* footprint: one rule, tested by booting.
3. **A heap that spans the machine.** One allocator over identity
   conventional memory and LDT extended memory. It hands out stable
   selectors, so it can compact without relocation procs. A package that
   asks for more than 64KB, or for "whatever is going"
   (docs/plans/REGION-SELF-COMPACT-PLAN.md section 8), gets megabytes.
   `OSAPI_MEM_AVAIL` answers in KB already, and its 16-bit answer reaches
   64MB, which is enough.
4. **Caches sized to the machine.** The `dirw` directory cache, the FAT
   snapshot, the read-ahead and a real sector cache stop being purgeable
   claims fighting packages for 640KB. docs/plans/DISK-CPU-PLAN.md found that
   81% of the kernel's time in a file-heavy load was the stateless-by-name
   API re-walking directories and chains. Memory to keep a whole volume's
   directory tree and FAT is part of that answer.
5. **The video player's XMS bank without a copy.** The bank is addressed in
   place through a selector. LOADALL (SPEC.md 41.13) and `ub_set` (SPEC.md
   41.15) were both attempts at exactly this, under real mode.
6. **Faults as diagnosis.** In real mode a wild write corrupts the heap and
   shows up ten minutes later. In protected mode, a write past a claim's
   limit or into code is a #GP at the instruction that did it. The kernel can
   kill that *instance* (`inst_*` already tears an instance down) and name
   the CS:IP in a toast. That is SPEC.md's "every byte read off a disk is
   hostile" given teeth.

What it should **not** do in the first build: ring 3, task gates or a TSS per
task (the scheduler's stack switch is cheaper than a 286 hardware task
switch), or any 32-bit code.

---

## 5. What it costs per call, from the datasheet

80286 clocks, real mode / protected mode at the same privilege level
(Intel's figures, not measured here):

| | real | PM |
|---|---|---|
| `mov sreg, r16` | 2 | 17 |
| `pop sreg` | 5 | 20 |
| `mov sreg, m16` | 5 | 19 |
| `call far` direct | 13 | 26 |
| `retf` | 15 | 25 |
| `int n` | 23 | 40 |
| `iret` | 17 | 31 |

An `OSAPI_SLOT` round trip (the caller's `call far`, two segment loads and
the `retf`) is about **+53 clocks** under protected mode. That is ~6.6 µs at
8 MHz and ~3.3 µs on the Victory's 16 MHz. A drawing call on a 286 costs
hundreds of µs, so this is single-digit percent per primitive. An interrupt
is about +31 clocks before its own segment loads. The tick runs at 18.2 Hz
and the mouse ISR at packet rate, so this is noise.

**Where it does bite**: inner loops that reload a segment per element. The
paragraph-stepping copies (`mem_bcopy` steps 64 paragraphs a chunk, the LZ
window slides) pay 17 clocks for every `mov es, ax` that used to cost 2.
None of those loops is per-pixel.

The figure that matters on the owner's machine is the **reflection: ~412 µs
a round trip** on the Victory 286. That is why nothing on a per-event path
may be reflected (2.2).

---

## 6. Alternatives considered and refused

* **Real mode with more of the kernel in the HMA.** It is already done
  (SPEC.md 2.10.7), and 64KB is all the HMA holds.
* **Executing above 1MB by LOADALL (286) or a loaded CS base (386, the
  `ub_set` trick).** Both leave CS's hidden base above 1MB, and the first
  interrupt reloads CS from the IVT. IRET then reloads it as `selector × 16`.
  Code can be *reached* that way but cannot keep running.
* **Identity-mapping at 1-paragraph granularity.** The GDT and LDT together
  hold 16,384 descriptors, and selector values that differ only in the RPL
  bits share one descriptor. The finest grid is 4 paragraphs using the LDT
  as well, and that leaves no room for anything above 1MB. Eight paragraphs
  in the GDT alone is the grid that keeps the LDT free.
* **A 386 floor with V86.** This is the real alternative and the owner should
  weigh it (section 8).

---

## 7. How much can be shared with kern_big

`KERN_EMU` is the precedent (SPEC.md 9.11.7): an *additive* define that
implies `KERN_BIG`, so every `%ifdef KERN_BIG` keeps the big feature set.
`KERN_MEGA` would be the same. It is *subtractive* for the size machinery of
section 4 item 2 and adds a protected-mode layer.

**By file**, of the kernel's 147,067 lines:

| class | files | lines | what happens |
|---|---|---|---|
| contains mode-bound code | memory, sched, mouse (the keyboard half), disk (the transfer layer), viddet, vidsel, loader, driver, mod, xmem, compress, lz, splash, cpudet, shutdown, fsx, hiber + hbstub/hbstage/hbmark, kernel.asm | **56,664 (38%)** | roughly a third of these lines are actually bound. That is the allocator core, ISRs, transfer sites, mode sets, the module and HMA loaders, and the boot ladder. The rest (FAT logic, the caches, `mem_avail`'s planning, the video tables) is shared |
| mode-neutral | wm, menu, ctrl, files, diskw, font, vga12, ui, events, icons, dock, desk, toast, fdlg, filecp, assoc, clock, ascw, stikmenu, … | **~90,400 (62%)** | builds unchanged after the mechanical sweep: the 468 `[cs:]` writes, 95 `push cs` pairs, `OSAPI_SLOT`'s DS load. Drawing code reaches VRAM through `[vid_seg]`, and those values are identity selectors |

So ~85-90% of lines are shared and ~10-15% are `%ifdef KERN_MEGA` or new.

The new code:

* the protected-mode entry and exit;
* GDT, LDT and IDT management;
* exception reporting;
* FDC and DMA;
* keyboard translation;
* mode-set tables;
* the 8042 reset.

At this tree's density that is plausibly **6-12KB of new code**. This is an
estimate, not a measurement.

**The real cost of the overlap is permanent.** Every change to a shared file
from then on has to stay correct under both models. For example, a new
`[cs:]` write in `wm.inc` is fine on kern_big and a #GP on kern_mega. That
needs a gate in the fast tier, and that gate is **built**: 2.4.1's
`t_cswrite.py` holds both idioms to a per-file registry. Without it the
shared 85% rots in one direction only.

**Packages** (58 live, 51 assembly and 7 C):

* ~24 run unmodified: arkanoid, bounce, browser, calc, chart, deskcal,
  fontview, fptest, fractal, ftpd, hello, imgtest, mines, pacman, paccman,
  piano, rlapply, sheet, solitaire, tamegram, texpad, thewire, timer and
  wire.
* ~5 need an SDK fix or a one-line one: notepad, taskmgr, artful, recorder
  and cword.
* ~29 need real rework.
* The DOS box goes through kern_dos.

**Drivers**: 6 of 13 are clean at ring 0. 7 need work: sound's DMA physical
address and IVT hook, hdd's `int 13h` and stepping, xmem (obsolete), usbmouse,
ems, ramdisk and hddtool.

---

## 8. The floor: 286 — DECIDED (2026-10-17)

**The owner has decided: the 286 is the target.** kern_mega is still a
build for slow, old machines, not for Pentiums, and the 286 is the oddball
any such build has to meet. The table stays as the record of what that choice
costs against a 386 floor. The one thing worth keeping from the 386 column is
a later *tier inside* kern_mega: a 386 could use V86 for unmodified packages
without changing the 286 build.

| | 286 floor (this file) | 386 floor |
|---|---|---|
| unmodified packages | ~24 of 58 | **nearly all**, each in a V86 task; a `call 0x60:NNNN` traps to the monitor (~200 clocks a call on a 386) |
| the DOS box | kern_dos handoff only | **in a V86 task beside the desktop** |
| BIOS | four native drivers + reflection by reset | **reflected through V86**, cheaply; native drivers become optional |
| leaving protected mode | reset | `mov cr0` |
| FS/GS for the `[cs:]` loops | none | yes |
| paging | none | yes: 4KB pages, and compaction is a page-table edit |
| machines it runs on | the owner's Victory 286, mr286, every AT | 386SX and up; **not** the owner's 286s |

A 386 floor is architecturally the *easier* product: it is Windows/386's
shape, and most of section 2 disappears into the V86 monitor. A 286 floor is
the one that runs on the owner's own 286 machines, and it costs roughly
half the package catalogue in rework. Whichever is chosen, the identity map
of section 3 is the right map. On a 386 it becomes page tables, but the
grid argument does not change.

---

## 9. How it would be tested — the real cost

* **MartyPC is an 8088.** None of its ~hundreds of rows can boot kern_mega.
* **QEMU** is on the fallback list for exactly this ("286 and 386",
  docs/TESTING.md). Its CPU is a 386 or better, so it executes 286 protected
  mode correctly. It does *not* catch:
  * a 386 instruction (NASM's `cpu 286` does);
  * a non-zero descriptor high word, which needs an assertion in the GDT
    builder;
  * **a store through a code segment, or past a segment's limit** -
    MEASURED in M1 (10.1, item 6): the mouse ISR wrote through CS on every
    packet and nothing faulted. 2.4.1's ratchet is the only instrument for
    that rule until a 286 runs it;
  * timing.
* **86Box** has the `286`, `286-525`, `286-sound` and `286-video` profiles
  for looking, but it cannot be scripted.
* **An 86Box harness is the owner's preferred route.** That means adding to
  86Box the socket MartyPC's debug server gives this tree: screenshot, key
  and mouse injection, and guest-memory reads, so that `os88ui` can drive
  it. It is a big, standalone project and not part of this branch. Until it
  exists, QEMU carries protected-mode semantics, and 86Box is for looking
  only.
* **MAME's `ibm5170`** is a 286 with a debugger and Lua scripting. It is
  **not evaluated here**. It is the fallback candidate if the 86Box harness
  stalls.
* **The owner's Victory 286** is the field reference, and the only place the
  reflection cost has been measured.

The suite's `os88ui` vocabulary resolves positions from guest tables through
`os88sym`. It would need a QEMU-backed transport and a protected-mode-aware
symbol reader (kernel bodies above 1MB, behind LDT bases), before a single
`disp*` row could run.

---

## 10. Waves, if it goes ahead

| wave | content | boots? |
|---|---|---|
| **M0** | decide: ring 0 (the floor is 286, section 8), the identity map, whether kern_mega is `KERN_BIG`-additive | — |
| **M1** | protected-mode entry after stage 2. GDT identity map, IDT, PIC remap, a #GP/#NP/#SS reporter. Native IRQ0, keyboard and CMOS. Floppy and video by reflection **with IRQs masked**. Kernel still at 0x0060, with code and data selectors split. The sweep: `[cs:]` writes, `push cs`, the `OSAPI_SLOT` cells, worked off `t_cswrite.py --list` (the gate itself is built, 2.4.1). Only the ~24 clean packages run | QEMU, a desktop |
| **M2** | native 765 + 8237 floppy. HDD rung 1 absorbed into the kernel. Reflection stays only for ROM-only disks, which refuse if they are slow | QEMU + 86Box 286 |
| **M3** | LDT allocator. `.cold`, modules and caches above 1MB. Conventional memory becomes package heap. Stable selectors for LDT claims, so no relocation procs | QEMU, measured heap |
| **M4** | SDK: code aliases for claims (`cc_ovbind`, `os88partsbody.inc`), `OS88_HUGE_INCR`, the shared speaker and pcm includes. The C packages are rebuilt | +11 packages |
| **M5** | per-package rework, worst first by usefulness rather than by size | — |
| **M6** | the DOS box beside protected mode (2.7); hibernate. The plan is docs/plans/KERN-MEGA-DOS-PLAN.md: the whole-machine handoff with the kernel parked above 1MB, an XMS door of its own, and a two-section hibernate image | field |
| later | ring 3 + call gates (an ABI flag day, SPEC.md 20.2.0.1); a 386 tier inside kern_mega | — |

M1 is the experiment that settles whether this is worth continuing.

### 10.1 M1 as built (2026-10-17)

`make mega` builds kern_mega into build/megak/ and `build/mega.img`, a 1.44MB
system disk that pairs with the shipped build/apps.img. kernel/mega.inc is
the switch; the rest is a sweep of the shared files, every arm of it
`%ifdef KERN_MEGA`, and **kern_big assembles byte-identical with all of it
in** (compared against a clean-HEAD build).

**What runs in protected mode, on QEMU:** the desktop and menus; the
serial mouse; the keyboard, through mega_k09 and mega_i16 (the BIOS's own
buffer, so no caller of `int 16h` changed); drives A: and B: listed, a
folder opened and B: mounted for the first time, through REFLECTED
`int 13h`; Calculator launched, driven by mouse and keyboard, and closed;
Fractal, whose worker task and VGA drawing ran to 100%; isoTron's windowed
title screen; the PS/2 mouse (QEMU's aux port, IRQ12) as well as the serial
one; the Sticky Apps menu (STIKMENU.DRV) and the Control Panel (CTRL.DRV,
every page), the first on-demand modules to run in protected mode; a desktop
shortcut dropped, which wrote SYSTEM.CFG through a reflected `int 13h` write
(the image verifies clean afterwards). A fault is reported on the debug port AND on the glass - one line under
the menu bar, vector, error code, CS:IP and SP - so a machine with no debug
port can be read by photograph.

**What the bring-up found, in the order it found it** - each is a rule for
whoever extends this:

1. **A selector is not a segment, and the BIOS only takes segments.** The
   reflection hands DS and ES to the ROM as real-mode segments, and the first
   version assumed every GDT selector was an identity one. The loader's
   scratch selector (MEGA_SEL_ODD) went down as segment 0x0030, and the
   floppy's DMA put a sector of the package over the API table, where no
   watchpoint could see it. mega_s2seg now reads the base out of the
   descriptor.
2. **"Is this the kernel?" is asked by comparing a DS with CS**, and in
   protected mode the kernel's DS is its data alias: wm_create filed the
   Disk window as a package's. kbm_isr's `.selfchain` guard is the same
   question asked the other way - "is the vector I chain to my own CS?" -
   and swallowed every key until the ROM-half chains were given a different
   selector for the same code (MEGA_SEL_BCODE).
3. **A far call into a package needs the package's CODE alias.** Every place
   the kernel enters one - wm_pkgcall, the loader's entry call, the driver
   dispatcher, a new task's frame - stored the DATA segment, which is also
   what every near pointer in the record is relative to. MEGA_PCALL,
   MEGA_CSELTOP and mega_frame_cs convert at the call.
4. **Off-grid arithmetic is real, and it is the FILE LAYER's**: the
   decompressor wants DI = 0, so the loader points ES at the body's own
   paragraph, 4 along from the region's base, and diskw's by-name I/O
   normalised every caller's ES:BX to an offset of 0..15 by moving whole
   paragraphs into the segment. On kern_mega dskw_norm moves whole 128-byte
   GRANULES (offset 0..127, the segment staying an identity selector), the
   entry points store the segment the caller's selector stands for
   (mega_s2segf), and the two places that need an exact paragraph - a
   compressed file's expansion target, and lz's 64KB slide of it - ask
   mega_oddsegf for a selector. The module loader's slot table holds the
   CODE alias (modules never move), and the modules' `*_go` trampolines push
   the kernel's code selector rather than DS (PUSH_KCODE).
5. **Bimodal state has to be where the early boot can read it.** k_dsel -
   the data selector KDS/KES read - was first placed with the rest of
   mega.inc, late in `.text`, and the boot splash calls vid_apply while that
   part of the image is still arriving: KES read 0 and the video block was
   copied over the API table. It sits beside the table now.
6. **QEMU DOES NOT ENFORCE A CODE SEGMENT'S READ-ONLY BIT.** The mouse ISR
   stored through CS on every packet and nothing faulted. So **QEMU-green is
   not 286-green for 2.4's rule**: tests/cswrites.txt is the list of what
   still faults on iron, and since this round it counts only the arms
   kern_mega actually assembles. The resident `.text` sites M1's desktop
   reaches are converted (both mouse ISRs, font_run's unaligned path, the
   inline API cells, gfx_points and the clip-table reload, vid_ctx_pre, the
   compactor's call into a relocation proc - which also far-called a
   package's proc through its DATA segment, a #GP even QEMU sees); and the
   ratchet now counts `mov reg, cs` and `mov reg, KERNEL_SEG` into DS or ES
   as well as `push cs / pop`. What is left is knob-only, real mode by
   construction (`.boot2`, `.ovl`, the hibernate stub, mega_svc's real-mode
   half), and **the on-demand modules - ~390 writes in CTRL.DRV,
   DISKOPS.DRV, DOCK.DRV, STIKMENU.DRV and the rest**, which will fault on a
   real 286 the first time each is used.
7. **A kern_mega conversion must be a no-op in REAL MODE, and the boot is
   real mode.** The first Victory run (2026-10-17) froze at *Loading Driver
   2/2 (Hard Drive)* with the floppy motor on - before the switch, in code
   QEMU had run a hundred times. The boot SNIFFS for drivers (SPEC.md
   51.3.2: an OPL2 answers, `int 13h AH=08h` reports a fixed disk), and the
   Victory's PicoMEM has both, so its boot loaded SOUND.DRV and HDD.DRV where
   every QEMU run here had loaded none. Expanding the compressed SOUND.DRV
   ran mega_oddsegf and mega_s2seg, which assumed protected mode: in real
   mode they wrote a "descriptor" into the IVT and handed back segment
   0030h, the image was expanded over the front of the kernel, and k_dsel
   read 7400h - so the next IRQ0 chained through 0000:0029. Five places had
   the same assumption and all now ask the mode first: those two helpers,
   MEGA_CSELTOP (`[cs:k_dsel]` in `.text`, `[ss:mega_pm]` in `.cold`), the
   compactor's call into a package's relocation proc, and the module slots,
   which the boot stores as segments and mega_enter converts
   (mega_mods_fix - with DOCK.DRV's and WIN95.DRV's vector tables, which
   those images fill with their own `cs`). A task that predates the switch
   cannot be converted at all - its stack holds real-mode return frames -
   so mega_enter now REFUSES the switch if a package or driver task exists,
   which only AUTOSTART can arrange, and every refusal says why on the glass
   (`real mode: ...`) as well as on E9.
8. **Every far call into a driver goes through a selector conversion**, and
   two did not: the service call (`drv_svc_call_x`, a sound driver's tick
   and play verbs) and the block call (`drv_blk_call_x`, a driver-backed
   volume's sectors - opening C: through HDD.DRV was #GP 9CC0 at
   `0C60:CE8D`). Both are MEGA_PCALL now.
9. **A reflection must not re-initialise the 8259.** It used to move the
   PIC's base to 08h for real mode and back to 20h after, and ICW1 resets
   the edge latches: a serial-mouse byte that arrived while IRQ4 was masked
   for the call was LOST, the UART kept its line high, never made another
   edge, and the mouse was dead for the rest of the session. With both
   drivers loaded the reflections were long enough to hit it every time.
   The PIC now stays at 20h throughout, mega_enter copies IVT 08h-0Fh to
   20h-27h so real mode finds the BIOS's handlers there, and the masked edge
   is still latched when the masks come off. A 286's reset hands control to
   the BIOS, which might re-initialise the 8259 on the way to 40:67:
   mega_r286 compares the masks with what it left and re-initialises only
   if they changed.

10. **A20 is XMEM.DRV's sequence, not a shorter one.** The second Victory
    run reached the desktop and refused the switch with `real mode: A20
    will not open`. mega_a20 probed once after each poke, and the 8042
    acknowledges its output-port write long before the line moves; it also
    ran the D1h/DFh pair with interrupts on, where a keyboard ISR can take
    the controller's pending command. XMEM.DRV's sequence had already opened
    this machine's gate (docs/reports/LOADALL-VICTORY286-2026-10-14.md), so
    mega_a20 is that sequence now: a probe inside `cli` that complements the
    alias and puts it back, port 92h only when it does not read as absent,
    the 8042 pair in one `cli` window, and 512 probes of settle after each.
    QEMU's BIOS leaves the gate open, so it was checked by shutting it first
    in a scratch build, once through the 8042 and once through port 92h:
    both reopened and switched.

11. **Segment 0 is the NULL selector, and QEMU does not fault on it
    either.** The third Victory run switched - A20 opened - and faulted at
    once: `#GP err 0000 at 0060:3453`, which is kbm_shf reading the BIOS's
    shift flags at 0000:0417 through DS = 0. The kernel reads the IVT and the
    BIOS data area that way all over, to save the byte `mov ax, 40h` costs,
    and loading a null selector is legal - only the access faults. kbm_shf
    runs on EVERY UI pass of a machine with no mouse found, which the
    Victory is (nothing plugged in) and no QEMU run here had been, since
    QEMU always has a PS/2 mouse. The sites kern_mega reaches after the
    switch - the keyboard pointer's shift state and buffer, the equipment
    byte, the video mode byte, CTRL.DRV's EGA records, the Disk window's
    modifier read, the compactor's IVT walk, the mouse's vector checks, the
    speaker's IRQ0 restore and the scheduler's stop - load MEGA_SEG0 now:
    MEGA_SEL_LOW0 (base 0, limit 4FFh) once mega_enter has run, 0 before.
    **And QEMU let the original run clean** - built with `NOPS2=1` and no
    serial mouse, so the keyboard pointer was live and its shift read ran
    every pass, the unfixed kbm_shf did not fault. Its TCG checks no segment
    on a data access, so this is item 6's blind spot a second time and
    `tests/unit/t_seg0.py` is item 6's answer a second time: a fast-tier
    ratchet over `tests/seg0.txt`, on t_cswrite's walker, that goes red with
    the old kbm_shf put back. What it lists that is still WRONG on kern_mega
    is the drivers: the Sound Blaster's IRQ discovery is deferred to the
    first stream, so it runs in protected mode, faults there, and hooks an
    IVT vector the IDT never reads - **digital audio through a Sound Blaster
    does not work on M1**, and how a driver hooks an IRQ under kern_mega is a
    driver-SDK decision (tools/abi.lock.json) rather than a rename. The same
    holds for HDD.DRV's XMS ring and for any driver loaded from the Control
    Panel after the switch, whose attach does its IVT work then. A related
    gap with no fault: a compaction that moves a driver image patches IVT
    vectors (mem_rr_walk) and not the IDT gates built from them.

12. **The Victory reached it: protected mode, `protected, 286 reset`, the
    mouse live - THE 286's WAY BACK WORKS ON IRON** (2026-10-17, the fourth
    disk). Opening A: then faulted, `#GP 0000 at 0C60:73B2`: the `rep movsw`
    of dsk_copy_seg_x, whose destination was KERNEL_SEG - in protected mode
    the kernel's read-only CODE selector. Three disk-layer wrappers named
    the kernel that way (`dsk_copy_in_x`, `dsk_get_dir_x`, `dsk_ico_stage`)
    and the dock's icon path named it as `mov ax, cs`, and neither ratchet
    sees a segment handed to a callee in a register. dsk_copy_seg_x takes
    the data alias for a KERNEL_SEG destination now, once, for every
    caller. Beside it, menu.inc's "is this a kernel window" asked CS and
    not the data segment (item 2's trap, harmless only because the strings
    are at one address either way).
13. **BOCHS ENFORCES WHAT QEMU DOES NOT, and is now the check before a
    field run.** Ubuntu's `bochs` 2.7 runs this tree with every segment
    check a 286 makes: it reproduced item 12 EXACTLY - the same vector,
    error code, CS:IP and even SP (1A65) as the photograph - from the disk
    the Victory ran, and passed the fixed one through A:, C:, B:,
    Calculator and Fractal, then faulted the Sticky Apps menu in
    STIKMENU.DRV's own image (`2684:0018`, an LDT code alias), which is
    the module work item 6 lists. The recipe: `BIOS-bochs-legacy` (the
    default BIOS's 32-bit init crashes before booting anything here),
    `pci: enabled=0`, `clock: sync=realtime` (otherwise the guest's clock
    runs far ahead and the screen saver and a double-click's timing are
    nonsense), `port_e9_hack: enabled=1` so the fault reporter's E9 dump
    reaches stdout, and `mouse: type=ps2` driven on Xvfb with xdotool's
    relative moves after Ctrl+middle-click grabs it (the guest moves one
    pixel per two X pixels). The Debian build has the debugger compiled
    in and stops at reset, so `c` goes in on stdin. Its CPU is a 386, so
    the reflection takes CR0 and the 286 RESET path stays the Victory's to
    prove - which it now has. A tool for it in tools/ is the next
    instrument, not yet built.

14. **The fifth disk ran everything in 10.2** - the Control Panel's pages
    too, though CTRL.DRV writes its own image on some paths - and three
    things past it: the Hard Drive page, Paint, and NumLock.
    * **An image far-calling another image** (HDD.DRV into HDDTOOL.DRV
      through `hd_tfar`, and back through `hd_rdisp`) loads a data
      selector into CS: `#GP 9500 at 2724:03A1` is `hd_tool_call`. A
      driver cannot know to convert, and the SDK is not changed for it:
      kern_mega's #GP handler (mega_gpfix) recognises the case by its
      error code - a 512-aligned identity selector below A000h, which is
      an image's base and has an exact LDT code alias - decodes the far
      CALL, JMP or RETF at CS:IP, checks the target, and finishes the
      transfer through the alias. A fault per such call, which here is a
      page click; anything that does not match goes to the reporter.
    * **A package's own segment arithmetic** is section 3's "real rework,
      one site at a time", and Paint was a site the survey missed: its
      per-row table (`pt_rowseg`, base + offset >> 4) is off the grid for
      most rows, `#GP 3588 at 25B4:0830` being `mov es, [pt_rowseg+bx]`.
      (A #GP error code drops the selector's low two bits, so 3588 is the
      descriptor named, not the value loaded.) The table holds 128-byte
      granules now - segment & ~7, offset & 127 - which real mode reads as
      the same bytes; kern_big's Paint was checked drawing on QEMU.
    * **NumLock** toggled KB_FLAG but never the keyboard's light, and
      without the ROM's "held" byte (40:18) a typematic repeat toggled it
      back. mega_k09 keeps 40:18 and sends EDh with the LED byte now;
      Bochs's status bar shows the light follow.
    All three were reproduced or checked under Bochs (item 13), Paint's to
    the CS:IP and SP of the photograph.

15. **CTRL.DRV is the first module converted, and the conversion has a
    shape now.** Closing the Control Panel after a change faulted on the
    Victory (no photograph), and Bochs reproduced it first time: `#GP 0000
    at 26E4:095E` with ES = CS, `cpc_ser` building SYSTEM.CFG in the
    image's own buffer through `push cs / pop es`. A module's CS on
    kern_mega is its LDT alias (S >> 2) | 4, so its data segment is
    (CS & ~7) << 2, and two macros in kernel.asm spell that: PUSH_CSDATA
    for `push cs`, and `CSDO op [CSEG x], ...` for `op [cs:x], ...`, which
    runs the one instruction with DS = the image and keeps FLAGS. Both are
    the original bytes off kern_mega, and kern_big was compared identical.
    All of CTRL.DRV is converted - ctrl.inc, shutdown.inc, driver.inc's
    settings macros and desksc.inc's `.modc` half, 33 writes and 9 pairs -
    and the tools learned the spelling: t_cswrite counts a `[CSEG x]`
    outside CSDO as a write, os88ovlchk reads CSEG as naming the image, and
    stkbalance knows PUSH_CSDATA and PUSH_KCODE push one word and CSDO
    moves SP as its instruction does. Bochs saves SYSTEM.CFG through it and
    the disk verifies.

16. **Every package STARTS under Bochs, and the sweep is a tool now.**
    `tests/megarun` is a package that starts every package in its folder
    one every five seconds and names each on port E9 first;
    `tools/os88bochs.py sweep` builds a C: disk with it as `0RUN.O88` (so
    it lists first) beside a batch of packages, boots `build/mega.img`
    under Bochs, opens the folder with the mouse and charges a `kern_mega
    FAULT` - or a minute with no new E9 line - to the package last named;
    the next boot carries on after it, and every start is screenshotted.
    The 44 shipped packages: all 44 start and draw, Sheet included alone
    (in a batch of six it is refused `04` for memory). Two mechanisms got
    them there, neither a package change:
    * **A CS: write** (`mov [cs:x], ax`, 125 sites in tests/cswrites.txt
      and more in packages) is completed by the #GP handler (`mega_gpw`):
      the instruction is decoded for length, copied to a trampoline with
      its CS: prefix turned into DS:, and run there with DS = the image's
      data segment; a DS or ES holding a CODE selector (`push cs / pop
      ds`) is swapped for its data segment and the instruction re-run.
      A fault per write - fine for a settings store, wrong for a loop, so
      the kernel's own sites are still converted (CSDO, PUSH_CSDATA) and
      the ratchet stays.
    * **The modules**: STIKMENU, the compressor, the association writer,
      the WIN95 theme and DOCK take CSDO/PUSH_CSDATA/KDATAR_M where they
      wrote through CS, and CSDO is two far helpers (`mega_dsimg`,
      `mega_csdata`) rather than an inline expansion, which took
      STIKMENU over `MOD_MAX_KB` when it was one.
    `mem_reloc_call` far-called a relocation proc through the region's
    DATA segment, which is what Sheet faulted on.

17. **Segment 0 is emulated for code the kernel does not own, and the IDT
    follows the IVT.** A driver hooks its IRQ through `ES = 0`
    (SB.DRV's IRQ discovery at the first stream, USBMOUSE.DRV), and the
    IDT is built once at the switch - so the hook faulted, and had it not,
    the IDT would never have seen it. `mega_null0` takes a #GP(0) whose DS
    or ES is the null selector, puts LOW0 in it and runs that ONE
    instruction under the trap flag with IF off; `mega_db` puts the 0 back
    (unless the instruction loaded the register itself) and calls
    `mega_ivt_sync`. No decoding: the CPU runs whatever it is, and a REP
    string op traps per element. `mega_ivt_sync` compares IVT 08h-0Fh and
    70h-77h with a 64-byte copy and, on a difference, writes back any
    LDT alias a driver stamped as its CS (`mov [es:si+2], cs` stores the
    PROTECTED-mode selector, which the next reflection would jump through)
    as the segment it stands for, refreshes IVT 20h-27h (where a real-mode
    IRQ lands, the 8259 staying at 20h) and rebuilds IDT 22h-27h and
    70h-77h through a new IDT alias, MEGA_SEL_IDT (GDT entry 7). **Not
    20h and 21h**: their IVT cells hold the BIOS's halves for a
    reflection while the IDT runs the kernel's, and the first build that
    rebuilt them handed the tick and the keyboard to the EOI stub - a
    desktop that froze the moment a driver hooked anything. The memory
    compactor's IVT walk (`mem_rr_walk`, a driver image moving) calls
    `mega_ivt_syncf` after it. Under Bochs with an SB16 and SYSTEM.CFG
    wanting SOUND.DRV, a WAV double-clicked on C: plays to the end through
    DMA 1 and IRQ 5 - 0.4 s of output in Bochs's capture, the length of
    the file. ETHER.DRV needed nothing new - it hooks no vector and polls
    - and with `--ne2k` (an NE2000 at 300h on Bochs's own slirp) the Wire
    zone comes up and the Browser fetches a page served on the host at
    10.0.2.2: DHCP, ARP, TCP and HTTP, all in protected mode.
    `os88bochs.py --sb --cfg BITS` is that machine, and `dbg`
    breaks into the running Bochs, runs debugger commands and continues,
    which is how IDT 20h was seen to have become `mega_eoi1`. ONE BOCHS AT
    A TIME: clicks go to the top window of the display, and two machines
    on it read exactly like a guest that froze, which cost an
    hour here; `boot` refuses while one runs and `stop` ends them.

18. **Off-grid packages are one site at a time, and two are done.** 1942
    derived band segments 2,688 bytes apart; the strides are whole
    128-byte granules now. Clear Skies decompresses three things into its
    own segment at addresses that are not multiples of 8 paragraphs - the
    vocabulary wherever the image ends, every art band 1,360 bytes along -
    so `cs_xpand` expands at the granule below and moves the bytes up,
    keeping the up-to-112 it covered on the stack; and `cs_artes` returns
    ES = the package's own segment with SI the band's offset in it,
    rather than the union's own segment. 56 bytes of image, on every
    kernel, and Skies flies in Mode X under Bochs and comes back.
    **Frotz** (`zm_map`, `zm_addr`, a jump's negative wrap, @verify's
    walk) and **Tracker** (pattern p at blob + 64 + 64p offset 60, a
    sample at blob + 8 x (start >> 7) offset start & 127) normalise to
    128-byte granules now - the same bytes in real mode, so neither
    package has a kern_mega arm: a 136KB v5 story compiled for the test
    (routines above 64KB, @verify) plays to the same transcript under the
    harness and on kern_mega, and BEVERLY.MOD plays through a Sound
    Blaster there. **RunCPM needed nothing** - the `rc_zseg + (off >> 4)`
    the survey named has `off` a multiple of 512 - and runs MBASIC under
    Bochs; CWORD, the C64, PaccMan, Weave and Loom all start too. The
    **DISKOPS compressor** was the kernel's own case: `cmz_far` and
    `cmz_move` normalised to 0..15 and the header was written at
    (ES-1):8; kern_mega normalises to granules and writes at (ES-8):120,
    a package's Uncompress takes `mega_oddsegf` for its body as the loader
    does, and a package's COMPRESS refuses in protected mode - the encoder
    wants its source at offset 0, and the body starts past the clear
    prefix. Plain files round-trip byte-exact. Still open: HDD.DRV's 386
    XMS ring (SPEC.md 52.1.4) loads ES's hidden base the unreal way and
    probes A20 through FFFF, neither of which protected mode allows - not
    reachable on M1, which ships no XMS driver for a package to arm it
    with. A generic answer was costed and refused for now: an exact selector per paragraph does not exist in an identity
    map (the GDT is full, and a value with RPL bits set names an entry
    shared with its granule), so it would mean rewriting the register's
    VALUE, which breaks every program that does arithmetic on it after.

The alternating `kernel-full.bin` noted while measuring kern_big's
identity is a `make mega` in the same tree: the sub-make leaves something
in the shared `build/` that kern_big's next assembly reads, so the identity
check is made in a fresh worktree, HEAD against the change.

Items 7-9 reproduce on QEMU once it is given the Victory's devices - an
AdLib (`-device adlib`) and a formatted IDE disk (`tools/os88hdd.py
--noboot --raw`). **That is now the QEMU configuration for kern_mega**, and
the one with no drivers is the easy case.

### 10.3 M2 and M3 as built (2026-10-17)

**M2 - the floppy is native; the fixed disk already was.**

1. **`int 13h` AH=02h/03h on drive 0 or 1 is run by the 765 and the 8237**
   (`mega_fd13`, entered from `mega_svc` before it reflects anything). It
   waits for IRQ6 with interrupts ON, so the pointer and the sound no
   longer stop for every floppy transfer - which is what a reflected call
   did, masking every IRQ but the BIOS's own for ~200 ms. The IDT's IRQ6
   gate is `mega_fdisr`, which sets the BIOS's own flag (40:3E bit 7), so a
   reflected call and the native path wait on the same bit.
2. **It is an accelerator, not a second driver.** It shares the BIOS's
   state - the recalibrated bits (40:3E), the motor bytes (40:3F/40:40,
   whose countdown `mega_t08` already ran), the last data rate (40:8B) -
   and hands everything it does not recognise to the BIOS: another
   function (reset, format, parameters stay reflected - short or rare), a
   call that is not `dsk_xfer`'s, a buffer across a DMA page, and ANY
   failure but a write-protected disk. The BIOS then does what it always
   did, so the path can only be faster or equal. Eight fallbacks in a row
   switch it off for the session, on E9 and in a toast.
3. **The media is derived, not read from 40:90.** That byte's encoding is
   the BIOS's own - Bochs's says 25h for an established 1.2MB disk, with a
   double-step bit no 1.2MB disk wants - so the rate comes from the
   volume's sectors per track (`dsk_xfer` writes it into the parameter
   table as EOT before every call) and the drive's CMOS type: 18 and 15
   are 500 kbps, 9 in a 1.2MB drive is 300 kbps double-stepped, 9
   elsewhere 250. Only `dsk_xfer`'s calls are taken (`[mega_fdx]`),
   because only for those is that EOT the volume's: a run across a head
   with a wrong one would read the wrong sectors WITHOUT failing. A wrong
   rate guess fails (missing address mark) and falls back - QEMU showed
   exactly that once, for A:'s boot sector read while B:'s spt was still
   in the table.
4. **The change line** (CCR bit 7) is cleared natively by a step pulse - a
   recalibrate and, since a recalibrate at track 0 pulses nothing, a seek
   to cylinder 1. Still set after that is no disk, the BIOS's to report.
   The kernel gives 06h no meaning of its own (it retries; a swapped disk
   is found by the volume), so nothing is lost by not reporting it.
5. **Checked under Bochs** - 1.44MB in A:, and in B: 1.2MB, 720KB in a
   1.44MB drive and 360KB in a 1.2MB drive (double-stepped, 300 kbps): a
   60KB file copied C: to B: is byte-identical on every one, every
   transfer native (`kern_mega: native floppy A`/`B` on E9, no fallback) -
   and under QEMU. One defect on the way is worth the note: replacing the
   40:90 read also deleted the line that pointed ES at the BDA, so the
   waits polled, and the motor bookkeeping WROTE, through the caller's ES
   - its buffer. A boot that does nothing but list a disk cannot see that;
   a byte-compare of a copy can.
6. **The fixed disk needs nothing**: HDD.DRV's rung 1 (ATA PIO) already
   serves a BIOS-known IDE drive on a 286 (SPEC.md 52.1.1), and a 60KB
   read from C: under Bochs reflected no transfer at all - `mega_svc` says
   on E9 the first time a fixed-disk transfer IS reflected, which is what
   a ROM-only controller (the Victory's PicoMEM) will show. "Absorbing rung
   1 into the kernel" is only owed for the kernel's OWN boot partition,
   and kern_mega has no hard-disk boot image yet, so it waits for one.
7. **`CPU_F_PM` (0x10)** is `OSAPI_CPU_INFO`'s new feature bit, set by
   `mega_enter` with `CPU_F_A20` (verified there) and on no other kernel -
   section 12.1, an SDK addition with no format bump.

**M3 - `.cold` and the XMEM pool above 1MB.**

8. **`.cold` runs above 1MB** (`mega_coldup`): copied to 0x125000, its GDT
   descriptor re-based so COLD_SEG:COLD_VSTART is the copy's first byte.
   The selector does not change, so no far reference anywhere is touched,
   and its 37KB rung becomes heap through the ROM path's own word -
   `[rom_vgabw]` moves the planar decoder's buffers to the bottom of the
   dead rung and `mem_floor_ax` drops the floor onto it (ROM-PLAN 3.4.2).
   Measured: the Task Manager's heap 534K -> 570K on Bochs. Nothing in real
   mode may run the old copy, and nothing does: every vector the kernel
   installs is in `.text` (the IVT was read back under Bochs), and a
   reflection runs only the BIOS.
9. **The XMEM cells are served by the kernel** (section 12.2): `xm_dsp`'s
   kern_mega arm calls `mx_caps`/`mx_alloc`/`mx_free`/`mx_copy`/
   `mx_relall`, which are XMEM.DRV's block table, first-fit walk, 1KB
   granularity and error codes over a pool from 0x130000 to the top of
   extended memory (16MB at most), with the copy a `rep movsw` through two
   scratch descriptors - GDT 1FFEh/1FFFh, the identity selectors of
   segments FFF0/FFF8, which nothing loads. `tests/megaxm` (on demand,
   `make megarun` builds it) allocates 64KB, writes and reads back sixteen
   4KB patterns and frees it: `caps 3B40`, `alloc 00130000`, `ok` on Bochs.
10. **What M3 still owes**, and why it did not fit this round: MODULES and
    CACHES above 1MB, and LDT claims with stable selectors. A module's data
    segment is derived from its code alias ((CS & ~7) << 2, `mega_dsimg`)
    and its claim's segment is a real segment the file layer reads into and
    normalises (`dskw_norm`, `mega_s2segf`); above 1MB neither is true, and
    the disk caches are DMA and reflection targets that real mode cannot
    reach. The shape that works is code/data selector PAIRS from the top of
    the LDT (entries 1280-2047 alias segments A000-FFE0, which nothing far-
    calls), with `mega_cs2ds`'s rule extended to "data = code + 8" there and
    a bounce for any transfer that must go through the BIOS - which is a
    round of its own, not a corner of this one.
11. **The hard-disk install runs, and the installed disk boots, under
    protected mode** (Bochs, 2026-10-18). `tools/os88bochs.py boot --c blank
    --cfg 2` gives the machine a ZEROED 20MB C: and HDD.DRV. The Hard Drive
    page's Format partitioned and formatted it, and Install copied both
    disks and wrote BOOTHD.SYS (kern_mega's own boot record, from the source
    disk) and the MBR. A reboot with `--c keep --bootc --noa`, from C: alone,
    reached protected mode and the desktop, and the Calculator launched off
    C:\APPS. Nothing faulted on either boot. Booting the harness's own
    pre-built C: (`--bootc --noa`) works too.
12. **The Victory's second run found one more far frame built with `push
    ds`**: `KGO_PAIR`, the Control Panel's own `CPXK` hop (and the boot
    blob's), pushed DS as the segment of a RETF into KERNEL_SEG. On
    kern_mega DS is the data alias 0010, so the Display page's paint
    faulted `#GP 0010 at 2644:1B08`, which is CTRL.DRV's RETF. It now pushes
    `PUSH_KCODE`, as extmod, stikmenu and winmod's trampolines already did,
    and so does fdlg.inc's `fdt_go`. All nine pages paint under Bochs, and
    Force Color ticks.
13. **Hibernate WAS greyed on kern_mega in protected mode** (withdrawn by
    item 71: M6 W5 built it), `Hibernate (PM)`
    (SPEC.md 47 rule 3), because an image would leave out everything above
    1MB - `.cold` among it - and the stub resumes in real mode. It is
    offered as soon as a hard disk exists, so an installed machine would
    otherwise have reached it. The real thing is still M6's (2.6).
14. **NMI is handled, not fatal.** Copying BEVERLY.MOD from the PicoMEM's
    C: to a floppy stopped the Victory on `FAULT 02 at 0060:5C4D`. That is
    vector 2, NMI, landing in `mega_fdirq`'s wait - where a floppy write
    spends its time, so the address says nothing about the cause. Real mode
    hands an NMI to the BIOS, and this IDT handed it to the fault reporter.
    `mega_nmi` now does what the AT BIOS does: port 61h bits 7 and 6 say
    parity or channel check, and an NMI with neither is spurious and
    dismissed. A latched one has its latch cleared and is reported -
    `NMI 61h=XX x N` in the menu bar from `ui_task` and on E9 - and after
    eight both sources stay off, so a held line cannot loop. Which line it
    was is the field run's question. It is SPECULATION that the PicoMEM is
    the source; whether kern_big's BIOS halts on the same copy is the other
    half of the answer.
15. **The floppy stutters through a C: copy on the Victory**, where it
    normally makes one smooth head move every half second. Two instruments
    now report on the glass, because the field machine has no E9. (a) The
    FIRST native fallback of a boot shows as `FD BIOS ss s0s1s2 Dmm`: the
    step, ST0-ST2, the drive and the media byte. The fallback count resets
    on every success, so a path that alternates never reaches the eight
    that switch it off, and the BIOS redoing every write is heard but not
    seen. (b) Every C: call on a 286 is a reflection through a CPU RESET
    and the BIOS's shutdown-0Ah path, which only the Victory has run.
    `mega_r286` compares 40:3E/3F with what they were before the reset, and
    the first difference shows as `RST 3E aa>bb 3F cc>dd`. A set 3E bit 7 is
    an IRQ6 inside the reset path, which means a controller reset. The
    motor bits are not asked when a tick ran the motor count out.
    (c) `mega_fdrprobe` asks the 765 itself, in `mega_r286` and at the top
    of every native transfer. A reset controller holds an interrupt for
    each drive until SENSE INTERRUPT STATUS, and an idle one answers 80h.
    A reset found this way is sensed out, every drive is marked
    uncalibrated in 40:3E, and the motors are marked off in 40:3F, so the
    next seek recalibrates first. Without that, a controller that believes
    it is at cylinder 0 steps N more from wherever the head really is. That
    is the mechanism that fits the field report: a drive that stutters, a
    copy that still succeeds (the wrong-cylinder write falls back and the
    BIOS recalibrates), no fallback ever reaching eight, and rails out of
    line at the next power-on. It shows as `FDC RESET R nn F nn`, by where
    it was found. The reports queue behind any toast already up. **Bochs
    cannot test the 286 path**: its triple fault resets the whole machine,
    devices included, where an AT resets only the CPU. A forced-286 build
    with C: through the BIOS hangs opening C:, with or without the probe.
    An earlier claim here that it copied identically was wrong: C: never
    reflected in that run. The Victory is the test.
16. **The NMI was a PARITY check**: `NMI 61h=A0 x 08` on the Victory, in
    one copy in three. A0 is bit 7 (parity) plus bit 5, the timer-2 output.
    Eight of them hit the cap, so parity checking is off for the rest of
    that session, which makes any further corruption silent. The line now
    also carries the CS:IP that the NMI interrupted.
17. **Restart hung at a blinking cursor on the Victory**: the PicoMEM's
    warm reset in `dsk_fdd_park_x` is `mov es, 0` and `jmp FFFF:0000`, and in
    protected mode FFFF is a selector. In protected mode the park now skips
    it and reaches `int 19h`, which `mega_svc` has always turned into the
    8042's reset line. It now sets the 1234h warm-boot flag first, so POST
    skips the RAM test, as Ctrl-Alt-Del does. Restart comes back to a fresh
    desktop under Bochs. (The first attempt jumped past the PicoMEM test's
    `pushf` to its `popf`, loaded a stack word into FLAGS, and stopped on a
    #DB at `dsk_fdd_park_x.unit`. That was found under Bochs and fixed.)
18. **The PicoMEM's Sound Blaster needs its option ROM's IRQ handler.** A
    PicoMEM 1.x has one line, its ROM's multiplexer owns it, and on it the
    CPU copies each 128-byte "DMA" block and the SB's IRQ is raised as a
    software `int 8+n` (SPEC.md 34.10.1). Every ROM IRQ was dismissed with
    an EOI, so no block was copied, SOUND.DRV's watchdog ended each stream,
    and Tracker cycled Buffering/Playing about three times a second. An
    IRQ whose IVT handler is an OPTION ROM's (C000-EFFF; and IRQ 9 when the
    BIOS's redirect leads to one) now goes to real mode through `mega_svc`,
    marked as an IRQ. The IMR is kept, because the multiplexer raises a
    line only when it is unmasked. The handler is entered with IF off. The
    IVT entries for IRQ 2-7 that name kernel or driver code (0Ah-0Fh and
    22h-27h) are capture stubs for the window, and each line they catch is
    replayed through its IDT gate once back in protected mode. The
    caller's flags are left alone. A throwaway Bochs build that routed the
    SB16's own IRQ 5 this way played BEVERLY.MOD through 6,434 reflections
    and 6,434 replays. Each IRQ on a 286 is a CPU reset, and a 22 kHz
    stream is ~170 blocks a second; that cost is the field run's to read.
19. **Both NMIs landed on `mega_fdirq`'s `hlt`** (0060:5C4D and 5E99 in the
    two builds), with the CPU halted, so the read that tripped parity was
    the floppy write's DMA. The line now gives the op, the 24-bit DMA
    address and the sector count when a native transfer is in flight
    (`NMI ss W llllll nn`). The `FD BIOS 08 400100 A90` the Victory showed is
    benign: a mount-time read of A: before the volume's sector count is
    known, at a guessed 250 kbps, which fails and falls back by design.
    The reset probe now skips while a native transfer is in flight and
    takes only MSR = 80h exactly as idle, so a seek's drive-busy bits keep
    it out.
20. **The reflected multiplexer now runs, and Tracker plays ONE note.**
    Restart is confirmed on the Victory with its PicoMEM. Tracker went from
    nothing to one note, then Buffering, in a loop: the first pre-rolled
    block plays and the next block IRQ misses SOUND.DRV's watchdog. The
    PicoMEM BIOS source (pmbios.asm's `PM_Int` and `IRQCMD_IRQ5`) shows the
    SB's `int 0Dh` is fire-and-forget, so capture-and-replay's ordering is
    not the cause. The suspect is the COST: every 128-byte block is an IRQ,
    and every IRQ reflection on a 286 is a CPU reset through the BIOS's
    shutdown path. `mega_rfsec` measures it with PIT channel 0 and shows
    `RFL rrrr/s uuuu` (count a second and average us, hex) once a second
    when there were 20 or more, at most every 15 seconds. Bochs's 386 CR0
    path, with the SB16's IRQ 5 forced through it, reads ~6Ch/s at ~62h us.
21. **The parity NMI is a track WRITE from conventional RAM**:
    `NMI B0 W 034600 12`, 18 sectors from 210K, at the tail of a 1MB copy.
    The DMA address is the buffer's own, so a misdirected transfer is ruled
    out. An A/B image with the native floppy off (`mega_fdoff` = 1) is the
    next question, for this and for the jitter: if both go, they are the
    native path's; if they stay, they belong to the 286 reflection.
22. **The A/B answered the NMI: it is the native floppy path's.** With
    `mega_fdoff` = 1, ten 1MB copies through the BIOS raised none. The DMA
    programming is the BIOS's byte for byte. What differs is what the CPU
    does during the transfer: `mega_fdirq` HALTED where the BIOS spins, and
    both field NMIs were on that `hlt`, the 8237 reading RAM under a halted
    286, which kern_big never does. It spins now. (Some 286 chipsets are
    reported to mis-sample parity on DMA cycles during a halt bus cycle;
    whether this one does is what the next run says.)
23. **Tracker is not a throughput problem**: 22 kHz, 11 kHz, XT Mode and
    5.5 kHz all play one note, and 5.5 kHz two. The chain from the card's
    interrupts to SOUND.DRV breaks after the first block or two at any data
    rate. `RFL 001C/s 04B1` was 28 reflections a second at 1.2 ms each, so
    the reset is cheap. A `Q cc ss oo bb vv rr` line now follows each RFL:
    per second, the PicoMEM ROM's PC-command IRQs (its DMA copies), its
    raise-an-IRQ commands (its Sound Blaster's), others, results that were
    not COMPLETED and the last of them (12h = the SB line masked, 14h = the
    same line as the card's), and the reflections that caught and replayed
    a kernel line. Read off `BV_IRQSource`/`BV_IRQStatus` at ROM segment +
    4000h, per pmbios/pm_vars.asm. **Superseded the same day**: the
    owner's firmware (`firmware/picomem1/`, Elendilon/ISA-PicoMEM
    `pm1x-pr` at 5e507be) links a PREBUILT `src/rom/pmbios.bin`, not the
    tree's `pmbios.asm`, and its multiplexer works off a request list at
    ROM + 4356h (`IRQ_VAR_OFFS`): [0] DMA copy, [1] audio IRQ, [2]-[5]
    network, mouse, keyboard, PC command. The Q line reads that now:
    `Q cc ss oo bb ii rr` = copies, audio requests, others, audio requests
    that raised none of our lines, the IMR the ROM saw, replays.
24. **The Tracker defect, found in that binary's ISR.** Its audio stub
    raises the SB's IRQ only when `in al, 21h` shows the line UNMASKED.
    `mega_r286` decided whether the BIOS's reset path had re-initialised the
    8259 by comparing the IMR with `imr1 | B8h`, the mask a SERVICE
    reflection sets. An IRQ reflection keeps the IMR, so the compare always
    failed: `mega_r286` re-initialised the PIC and wrote `imr1 | B8h`,
    masking the SB's line, and the multiplexer skipped every block IRQ. The
    stream died after its pre-roll at any rate, on the 286 only, because a
    386's CR0 path never comes through `mega_r286`. It now expects the mask
    the reflection actually set.
25. **Confirmed on the Victory 286 (2026-10-18)**: Tracker plays
    BEVERLY.MOD at 22 kHz through the PicoMEM's Sound Blaster.
    `RFL 002B/s 04CA` is 43 IRQ reflections a second at ~1.2 ms, about 5% of
    the CPU. `Q 24 08 00 00 18 08` is 36 copies and 8 audio IRQs a second,
    no audio request without a raised line, IMR 18h (the SB line open) and
    8 replays. No parity NMI in at least eight 1MB copies after the
    floppy wait stopped halting. Restart works on the PicoMEM. The jitter
    that is left is in a copy's first two seconds only, which fits
    `dskw_alloc`'s first-fit rover (back to cluster 2 at every mount)
    filling a fragmented disk's front holes before reaching contiguous free
    space. That allocator is kern_big's too, and the A/B to settle it is
    the same copy onto a freshly formatted floppy.
26. **The D: after an install, and the C: that says "No os8088 disk", are
    one defect, and it is kern_mega's alone.** Reproduced under Bochs with
    C: through the BIOS (a throwaway HDD.DRV with its rung-1 probe skipped):
    install, reboot from A: with that C: kept, open C:, Install again. An E9
    trace on the volume slots read `A2` at boot and `D2F A3` in the install:
    OSAPI_VOL_DEL(2) was REFUSED by `osapi_vol_fence`, and the install's own
    mount then took row 3. The fence compares the caller's DS with the
    published DATA segment, and HDDTOOL.DRV calls the resident with DS =
    `[hd_rseg]`, which `hd_tool_need` fills with `push cs` - on kern_mega the
    resident's LDT CODE alias. Reads through it work and the first write
    faults into `mega_gpw`, which converts DS; HSV_MOUNT and the page's
    Unmount both write a byte before their kernel call, so they passed,
    while HSV_UNMOUNT's first act is the call. So the row kept its icon and
    its letter, `hd_vols` forgot it (a C: whose handle names nothing: "No
    os8088 disk"), and every later mount of that partition - the install's,
    and the owner's Mount on the Victory - landed on D:. The fence now takes
    an LDT selector as `(S & ~7) << 2`, mega_cs2ds's rule, inside `%ifdef
    KERN_MEGA` (the same fence guards `desk.inc`'s driver test). After it the
    trace reads `D2 [2 A2` and C: comes back as C:; a blank install and a
    second install over it on rung 1 show no D: either. kern_big never had it:
    `push cs` there is the image's segment, which is also its data.
27. **The installer's refusal now says what it tried**, because the field
    machine has no debugger: `No system disk: A:k31 B:g1`. One entry per
    volume `hd_isrc_ck` asked, in the order it asked, at most four (the line
    is HIW_CELLS = 42 wide). `X:g<n>` = the quiet goto to X:'s root refused
    with FERR n, and 1 is every way a mount fails (no disk, a read error, not
    a FAT disk). `X:k<n>` = X: mounted, its root was walked n entries far and
    KERNEL.SYS was not among them; k0 is a root with nothing readable in it.
    The first entry is where the search STARTED - the volume the user was on,
    or A: when that was the destination - and the rest are the floppies in
    index order, so a first letter that is not A: says the search began
    somewhere else. Verified under Bochs with a TEST build that looked for
    KERNEL.SYX and a blank 720KB disk in B:: exactly the line above.
28. **A refusal before the erase puts the destination back.** `hd_iunmount_dst`
    runs before the source check, by design (the source must not be the
    disk about to be written), so "No system disk" and "Older disk" left C:
    unmounted until the next boot - the "nothing done" was true of the data
    and not of the desktop. It now records the slots it dropped and which one
    the user stood on, and `hd_iremount` mounts them again on those two paths,
    with the user back at that volume's root. In the KERNEL.SYX run C: came
    back as C: (`A2`), on rung 0. These two items change HDDTOOL.DRV's bytes
    on kern_big as well, deliberately: the message and the remount are right
    on both kernels. HDD.DRV and kern_big's `kernel.bin` are byte-identical.
29. **"No system disk" itself did NOT reproduce under Bochs** - rung 0 for C:,
    a kept install, the C: window open first, a 720KB disk in B: or a blank
    one. Two things differ on the Victory and neither can be shown here.
    (a) **Every floppy mount's first read takes a fallback there and never
    here.** `disk_mount` reads LBA 0 at the 9-sector fallback geometry, so
    `mega_fd13` guesses 250 kbps for a 1.44MB disk; the Victory's 765 fails
    it (item 19's `FD BIOS 08 400100 A90`) and the BIOS reads it through a
    286 RESET. Bochs does not check the data rate: no Bochs run here printed a
    single `FD BIOS` line, so the fallback inside an install's batch is a path
    only the iron has run. (b) The page's own `Need the system disk` is what
    HDD.DRV draws when the tool will not load - `hd_tool_need`'s quiet goto
    to the volume it was loaded from (A:\SYSTEM) refusing - so the owner's
    report that the PAGE refused until the panel was closed and reopened
    fits the same cause: A: transiently unmountable after the install's
    unmount, then readable again. The next photograph of item 27's line
    decides it: `A:g1` is the floppy path, `A:k<n>` is the directory walk,
    and a line that does not start with A: is the search order.

**M3, continued - the LDT allocator and the first claim above 1MB
(2026-10-18, KERN-MEGA-HANDOFF track 1).**

30. **The LDT allocator** (`mega_ldt_alloc`, `mega_ldt_free`): entries
    1280-2047 are built FREE (access byte 0) and handed out with any 24-bit
    base and limit, data or code, freed by selector; the scan and the claim
    run under `pushf`/`cli`. They are written through `MEGA_SEL_LDTD`
    (FFE8h, GDT entry 1FFDh: the identity selector of a segment nothing
    loads, `MEGA_SEL_XA`'s argument), whose limit is exactly the table so
    nothing written through it reaches the IDT or `.cold`. Every routine
    that reads a selector's base now reads the DESCRIPTOR in this range
    (`mega_selbase`, `mega_s2seg` - which answers FFFFh for a base above
    1MB, as it already did for a GDT one), and the two that turn a code
    alias into its image (`mega_cs2ds`, `mega_ivt_sync`) refuse it, so a
    #GP with DS holding one is not "fixed" into a wild segment.
31. **Kernel-owned extended memory comes out of the XMEM pool** (13.4):
    `mega_hiclaim` is `mx_alloc` under owner FEh plus a data descriptor
    over exactly the bytes asked for, `mega_hifree` the reverse. One table,
    one first-fit walk, one free figure, so the cells' CAPS (and the Task
    Manager's XMS line) count what the kernel took.
32. **The read-ahead store runs above 1MB** (SPEC.md 18.95; 13.3 step 2).
    `mega_enter` re-solves it (`dsk_rah_redof`, after `sti`): the boot's
    mount claimed it in real mode. In protected mode `dsk_rah_want` asks
    `dsk_rah_wanthi` first - the full width, DSK_RAH_RUNS, under
    `[dsk_rah_cap]` (the free-run and arena-share bounds are about
    CONVENTIONAL memory, which this does not spend) - and falls back to
    the conventional claim only when that is refused. `[dsk_rah_seg]` is
    then a data selector, only ever loaded (`dsk_copy_seg_x` is the one
    reader), and `[dsk_rah_hi]` says so. Every fill reads into a 5KB
    LANDING below 1MB and is copied up: a reflected `int 13h` reaches only
    a real-mode ES:BX, and on the Victory every C: transfer is one. The
    landing is `MEM_P_RAHB` - the store's own rank, purgeable, page-safe
    (`mem_claim_dma_x`) so a fill is one transfer - and a shed of it stops
    the fills, not the hits, until the next mount re-takes it.
    Measured under Bochs, Task Manager open from C:\RUN: the store is LDT
    2804h, base 130000h, limit 7DFFh (7 x 4,608 bytes), the pool's first
    block 32KB under FEh, and the claim table's read-ahead entry is the 5KB
    landing where the kern_mega before this held the 32KB store at 1AE0h -
    **27KB of conventional memory back**. The Task Manager's HEAP figure
    reads 16/568K on both, because it counts a purgeable cache as free; the
    gain is the RAM a shed would otherwise have had to take back (and the
    fills it would then have lost), and what M6's DOS program will see.
    PIXEL.O88 (110,489 bytes) opened off the BIOS-reflected C: and copied
    C: -> B: (a blank 1.2MB floppy) byte-identical, and A:\APPS\DOS.O88
    (47,610 bytes) A: -> B:, native floppy at both ends, byte-identical.
    `tools/os88bochs.py sweep` over the 34 packages on the shipped
    apps.img: all 34 start with no fault - SHEET and SKIES only alone,
    refused 04/05 for memory inside the batch of six that also holds
    PAINT, PIXEL and PXSTEIN, which the kern_mega before this refuses
    identically (an A/B on that batch).
    The SHED path, simulated from the debugger (`[dsk_rah_bnc]` zeroed,
    since PIXEL, SHEET, PAINT and SKIES open together without one): the
    next mount - opening C: - took a new landing, and with it zeroed again
    and no mount between, PIXEL loaded off C: and ran with the word still
    0, so the fills stayed off and the reads went direct.
33. **A reflected transfer to a buffer above 1MB is refused, not made.**
    `mega_s2seg` has always answered FFFFh for such an ES, and the BIOS was
    then handed FFFF:BX. `mega_svc` now answers an `int 13h` 02h/03h with
    that ES as the 8237 would, CF = 1 and AH = 09h, without reflecting it.
    Nothing reaches it today (the store is never a transfer's target); it
    is the fence for whatever is placed high next.
34. **Two things deliberately NOT done.** (a) The native floppy could DMA
    straight into the store (`mega_fd13` takes the base off the descriptor
    and the 8237 reaches 16MB), saving a 4.5KB copy, ~1 ms on a 286, per
    floppy fill against a ~200 ms transfer - but its fallback is the BIOS,
    which would then be refused 09h and walk `dsk_xfer`'s retry ladder.
    The landing is uniform and costs nothing measurable. (b) MODULES above
    1MB (13.3 step 2's second half) are the next round, and its shape is
    13.5.

**Track 2 - the size machinery out of kern_mega (section 4 item 2,
KERN-MEGA-HANDOFF.md).** Every figure below is kern_mega at ONE build number
against the commit before it (`OS88_BUILDNUM=1600`, `tools/kernsize.py`'s
section line), and kern_big is byte-identical across each change.

35. **ROM_COLD splits into a LADDER and an ADOPTION.** The ladder - `.cold`
    on the top rung, under `.vgabuf` - is what kern_mega STANDS on:
    `mega_coldup` drops the heap floor onto the dead rung through the ROM
    path's own word, `[rom_vgabw]`, and `mem_floor_ax` reads it. So
    `ROM_COLD` stays defined. The adoption is the new `ROM_ADOPT`, which is
    `ROM_COLD` on every kernel but kern_mega: stage 2's doorbell at F400,
    `[rom_mfp]` and its seed `rom_none`, `mod_need`'s three ROM arms (SIZE,
    COPY, FIX) and the hibernation head's "where `.cold` runs" byte. A
    kern_mega `.cold` has a home of its own at `MEGA_COLD_LIN`, nothing cuts
    a ROM or an HMA image from it, and a kern_big ROM at F400 could only
    refuse it. **`.text` -6, `.cold` -24, `.boot2` -27.** The Control Panel
    (a module, so `mod_need`) opens under Bochs. On the same commit
    `osapi_sys_kb` asks `[mega_coldhi]` rather than `[api_coldseg]` whether
    the cold rung is heap - on kern_mega that selector never changes, so the
    Task Manager billed `SK_COLD_KB` (37K) of heap to System. It reads
    **System 73K, HEAP 568K** under Bochs now.
36. **The XMEM.DRV transport is not assembled.** The HMA `.cold` and its
    driver pool (SPEC.md 2.10.7) arrive through XMEM.DRV, which loads
    `COLDHMA.SYS`; kern_mega already had neither (`HMA_DRV` was never
    defined there, `MEGADRIVERS` filters both files off `mega.img`, and
    `xm_sniff`'s kern_mega arm never wants the image). What was still
    assembled was the attach path: `xm_row` and its file name, `xm_boot_x`
    in the blob, `xm_dsp`'s image arm, the driver-call guard's `xm_row`
    compare and the compactor's `xm_row` word. None of it could run -
    `[xm_kb]`, the gate every cell tests, is written by `mega_xminit` alone,
    next to `[mega_xmnat]` - so `xm_dsp` is the native arm and nothing else.
    **`.text` -66, `.cold` -6, `.boot2` -106.** `[mega_xmnat]` itself is
    now read by nothing; it is left in `mega_xminit` for track 1, whose
    file that is.
37. **The other three return NOTHING resident, measured:**
    * **`rp_walk`'s fixups** are `boot/osrom.asm`'s - code and tables in
      the ROM and in `COLDHMA.SYS`, generated by `tools/os88romfix.py` - and
      the kernel carries no list of them. kern_mega builds neither image.
      0 bytes, and nothing to guard.
    * **`mem_unblob`** is 19 bytes of `.cold` that hand back the 5.7KB
      blob (`.boot2` 5,721 after 27). It is not scarcity machinery on any
      machine: the blob is the boot, and the boot runs in real mode on
      kern_mega exactly as on kern_big. It stays.
    * **`.ovl`/`.ovlw`** lands on `FAT_SEG` and is overwritten by the first
      mount, and the code that reads it is the blob's, so it costs 0
      resident bytes already. Folding its 5,116 bytes into `.cold` would
      cost 5,116 more conventional bytes FOR THE BOOT (the cold rung, before
      `mega_coldup` frees it), 5,116 of the 7,423 `.cold` has left under
      `MEGA_XPOOL`, and an `os88ovlchk` arm of its own, for no byte after
      the boot. Refused. The real-mode fallback (`mega_enter` refusing) is
      the other reason none of these three may go: everything the boot
      needs before `mega_enter`, it needs on that path as well.
    Total with 39 below: **`.text` -74, `.cold` -30, `.boot2` -133**. The heap
    figure does not move - `.text`+`.bss` is 58,232 against the 58,368 of
    its rung - which is the rung banner's point and not a reason to stop.
38. **The rung `mega_coldup` frees is a HOLE, and a compaction would not
    close it.** Read off `mem_tab` under Bochs after the boot: `[mem_base]`
    11A0 (the dead rung, under the moved `.vgabuf`), the `dirw` cache
    (`MEM_P_DIRW`, 32K, movable) at 1AE0 - the floor the boot claimed
    from - a FAT window (5K, purgeable but PINNED) at 24E0, then a 472K
    run. Running `mem_unblob`'s compaction after `mega_coldup` would move
    the `dirw` cache down and leave 45K under the FAT window, so the
    largest run is 472K either way; a claim bigger than that already gets
    the lot, because `mem_claim` refuses through compact, SHED, retry and
    both caches are purgeable. Nothing is added. The hole goes away with
    track 1's caches above 1MB, which is the right fix: the caches were
    what walled it.
39. **`api_far` pushes `.cold`'s selector as an immediate.** `[api_coldseg]`
    is a WORD so that a ROM or the HMA could re-point it, and on kern_mega
    nothing does after 35 - `mega_coldup` re-bases the descriptor and keeps
    the selector. So `push word COLD_SEG` (a 286's push) replaces the read
    and the word is not assembled: **`.text` -2**, every far call through an
    N cell a memory operand shorter, and the push no longer reads DS. One
    `push` line on both arms (a `%define`), because `stkbalance` reads the
    source and a constructed far jump is two pushes and a `retf` with nothing
    between them - not even a `cpu` directive.
40. **Checked, at the head of the track** (Bochs; real mode under QEMU):
    `make` and `make mega` clean, kern_big byte-identical at build 1600 after
    every change; a sweep of all 49 shipped packages and MEGAXM starts every
    one with no fault, the five refusals (`MEGAXM`, `DESKCAL`, `DESKCLOK`,
    `RLAPPLY`, `STIKNOTE`, error 04) being the base commit's too, and MEGAXM
    `ok` through the native `xm_dsp`; A:, B: and C: open; the Control Panel
    (a module) opens; with `--sb --cfg 1` Tracker plays BEVERLY.MOD, the Audio
    Player a WAV off C: and MIDIRack a `.MID` it reads by name, all with
    sound in `sb.wav`. The REAL-MODE FALLBACK, forced by `qemu -m 1` (under
    192KB above 1MB): the desktop, the Control Panel off the system disk,
    and the Task Manager billing `.cold` to System (106K) because there it
    is not heap. **One trap in the handoff's identity recipe**: a bare
    `make build/kernel.bin` builds the packed kernel's PASS ONE (`KZ_SECS=0`
    placeholders, Makefile `KZDEF`), and a tree that has run a whole `make`
    builds pass two - so the two differ from byte 4344 on with no source
    change at all. Compare like with like (both whole `make`s, or both bare
    targets in fresh trees).

**Track 1, after the merge.**

41. **The Sticky Apps refused "No desk layer (DESK.DRV)" on kern_mega** -
    all three (DESKCAL, DESKCLOK, STIKNOTE), on the kern_mega before this
    round too (62dfe2c0, the same sweep). DESK.DRV's LIB verb hands the
    library's segment back as `mov dx, cs / add dx, offset >> 4`, and in
    protected mode CS is the image's LDT code alias, so the sum named an
    unrelated descriptor and the client's magic check failed. On kern_mega
    the library sits on a 512-byte boundary of the image (up to 511 bytes
    of padding, kern_mega's image only), which gives it a code alias of its
    own, `(CS & ~7) + offset / 64`, and LIB answers that when CS is an alias,
    so the clients far-call it with no fault and read its magic through
    it (code is readable). Real mode keeps the paragraph arithmetic. kern_big's
    DESK.DRV and kernel are byte-identical. Under Bochs all three start
    and draw. This was found by the module census of 13.5.

**M4 - the SDK's code aliases (2026-10-18, KERN-MEGA-HANDOFF track 3).**
Every count below is from a throwaway kern_mega that writes one E9 line per
#GP in `mega_fault` (`T<error> <CS>:<IP>`, track 4's logger by hand), under
Bochs, old package against new on the same image and the same clicks.

42. **The selector to far call code in a claim is an SDK macro**,
    `OS88_CODESEL reg, <AH of OSAPI_CPU_INFO>` (os88api.inc): the segment
    itself on every real-mode kernel, `(S >> 2) | 4` under `CPU_F_PM`. It
    sits beside `OS88_HUGE_INCR` (0x1000, 3.2), which is a constant today
    and stops being one only when an LDT claim hands out consecutive
    selectors - an ABI decision, not an edit. It has no consumer yet: no
    code in `apps/cc/` or the parts standard steps a segment by exactly
    64KB (the carve walks in 32KB of paragraphs, `add ax, 0x800`), and
    paragraph arithmetic of that kind is what an LDT claim will need
    replacing anyway, not renaming. The parts standard gains
    `op_cseg`, opt-in with `OP_WANT_CSEG` (`OP_WANT_READ`'s reason: what
    decides it is a call no row sees), so no package that does not ask
    changed a byte. ABI lock: no bump, additions only.
43. **The C runtime far-calls its overlay through the alias.** `cc_entry`
    banks CPU_INFO's AH before anything binds; `cc_ovbind` stamps the
    module's vectors from `[cc_ovcs]` and `cc_ovthunk` returns through it,
    while `[cc_ovseg]` stays the data segment op_seg, op_drop and MEM_FREE
    want. Before: every resident->module call, module->resident return AND
    module->module call (they are far too, 73.14) was a #GP - 5 per round
    trip in `tests/covl` (25 for five SPACEs, 0 after, the gate's five
    numbers all right on the glass), 120 for CWORD's Format > Character
    (0 after, the dialog drawn), and **6,909 for opening `WELCOME.RTF`
    and typing three characters** - the RTF reader is overlay code calling
    itself and the resident half all the way down - against 0 after, the
    document rendered with its formats and the edit taken. LOOM's preview
    and WEAVE's canvas core,
    the two C packages that far-call a part themselves, bind the same way.
44. **The emulator cores wrote through CS, and that was the census's
    biggest number.** C64's and the Apple II's 6502 cores (one derived from
    the other) wrote the register file back through CS at every slice's
    exit - eight #GPs a slice - and loaded DS from CS before each C I/O
    handler, so every C store there trapped too: **57,778 and 57,168 #GPs**
    in a sweep's few seconds at READY and `]`. The exit now writes through
    ES (the package, from the run's own frame word), and the handlers take
    DS from a word banked at each door in from C. RunCPM's Z80 core never
    loaded ES, so ES is the package for the whole run and every static
    store - IX/IY halves, EXX, EX AF, IFF, IM, the exit - is `[es:x]`; its
    idle CCP was 248 #GPs. All three: **0** after, at the same prompt; the
    C64's status row read 391% -> 478% of a C64 (the logger's E9 output
    inflates the "before", so that ratio is an upper bound).
45. **kern_big byte-identical**, and so is every shipped `.o88`, `.drv` and
    floppy at one build number (OS88_BUILDNUM=1600, both trees): only
    c64, apple2, runcpm, cword, loom, weave and covl changed (and, with
    item 48, every C package by one byte). One prefix byte for another, so
    the real-mode cores run the same clocks: ZEXDOC (`make rcz80test`),
    `make a2cputest` and `make c64cputest` (Dormann's functional test and
    twelve rows each) all PASS on the converted cores. On a clean mega.img
    the sweep starts all seven C packages, Notepad and Paint, no FAULT.
46. **The speaker ring player cannot run on kern_mega yet, and that is a
    KERNEL gap, not the include's.** `os88spk_go` writes IRQ0's IVT cell
    (through segment 0, so `mega_null0` runs it) and reprograms channel 0
    to the sample rate after `OSAPI_FSX_SPK` opens. `mega_ivt_sync` builds
    gates from IRQ2 up - IRQ0 and IRQ1 are the kernel's own there - so the
    ISR is never entered and `sch_isr` would tick at the SAMPLE rate. Read,
    not run: no speaker play was tried under Bochs. The ISR's ~20 CS
    stores (`os88spk_rp`, `os88spk_left`, the `os88spk_isrm` toggle) are
    per sample, so converting them only pays once IRQ0 reaches the
    package. Until then `OSAPI_FSX_SPK` on kern_mega should refuse
    (`SPK_E_*`), which every caller already handles, and the conversion
    wants a PM-only ISR variant chosen in `os88spk_go`
    (`push ds / mov ds, [cs:banked]` per sample is what the real-mode
    ISRs were cycle-counted to avoid, SPEC.md 34.11). os88spkfx.inc and
    os88pcm.inc are the producer's side of the same play and wait with it.
47. **Left for the census (track 4)**: PiXEL's part calls (`px_pfar`,
    `px_wfar`) and PIXELSTEIN's per-column bodies (`px_qcur*`, `px_drvp`)
    are far calls through a part's DATA segment - the latter in the
    raycaster's column loop, and its relocation table adds a paragraph
    delta to those words, which is wrong for an alias (an alias moves by
    delta >> 2), so it wants `op_cseg` at bind AND the proc re-deriving
    rather than adding. Not swept here.
48. **No package region is movable on kern_mega, and it is one compare.**
    `OS88_REGION_MOVABLE` (and crt0's copy of it) hands
    `OSAPI_MEM_MOVABLE` `DX = CS`, which is the region's LDT CODE alias
    there; `mem_find_own` compares DX with `MC_SEG`, an identity segment
    whose bit 2 is always clear, so it can never match and the call refuses
    - silently, by design (`a refusal is not worth reporting`). READ OFF
    `mem_tab` under Bochs (`xp` at LOW_SEG:mem_tab, CWORD and Notepad
    started by MEGARUN): CWORD's region, owner 2, `MC_RLOC 0`; Notepad's,
    owner 3, `MC_RLOC 0` - while the claims each declared through a DATA
    segment (CWORD's overlay carve, Notepad's buffer) carry their procs.
    crt0 now passes `DX = DS`, the same word on every real-mode kernel, and
    the same read shows CWORD's region at `MC_RLOC 01D2` (`cc_regreloc`).
    The assembly macro is in every other package, already built and
    shipped, so **the fix that reaches them is the KERNEL's**: on kern_mega
    `osapi_mem_movable_x` (kernel/memory.inc, track 1's file) should map a
    DX with bit 2 set through `mega_cs2ds` before `mem_find_own` - the
    same conversion `mega_gpw` makes for a code selector in DS. Until then
    a kern_mega compaction can move no package region but a C one.
49. **WEAVE's VM and the two far-called modules: measured, not converted.**
    PONG.WAB double-clicked from C: costs 63 #GPs to load and 45 in the 30
    seconds after Serve. 38 of the 63 are two sites at the entry of the
    canvas core (`wcanvas.asm` `wsm_entry`, CS 061C): `mov [cs:wsm_cds], ds`
    and then the first store after `push cs / pop ds` - two per VERB call,
    the second because `mega_gpw` swaps the read-only DS for the data
    segment and the instruction runs again, so the rest of that call is
    free. LOOM's preview module (`lmpvmod.asm` `lpv_entry`) has the same
    two. The cure is the module's own DATA segment on entry, which the
    package has (it bound the vector from it) and the module cannot work
    out without CPU_F_PM - so it is a module ABI change (WSM_ABI, the
    preview's header, WEAVE-SPEC 1.2.2) for two #GPs a verb, and is left.
    The VM (`wvm.inc`, ~150 CS stores: DS is the VM claim and ES the
    bundle for the whole slice, so no register is free) stored per EVENT
    in this run, not per op - the remaining 25 load-time and 45 play-time
    #GPs are its - so its restructure waits on a bundle that shows a loop.
50. **What track 3 leaves outstanding**, in the order it would be taken:
    * **Kernel, not SDK** (track 1's files): `osapi_mem_movable_x` maps a
      DX with bit 2 set through `mega_cs2ds` (item 48) - one compare that
      makes every shipped assembly package's region movable on kern_mega.
      The SDK-side alternative, `mov dx, ds` in `OS88_REGION_MOVABLE`, is
      the same byte count but rebuilds ~61 packages and cannot reach the
      ones already on disks.
    * **Kernel, then SDK**: IRQ0 for a package's speaker ISR on kern_mega
      (item 46). First `OSAPI_FSX_SPK` should refuse there, so callers fall
      back; then the gate is routed, and `os88spk.inc` gains a PM-only ISR
      chosen in `os88spk_go`, with os88spkfx.inc and os88pcm.inc after it.
    * **The parts packages' own far calls** (item 47): PiXEL's `px_pfar` /
      `px_wfar` and PIXELSTEIN's per-column `px_qcur*` / `px_drvp*` to
      `op_cseg` (define `OP_WANT_CSEG`), and PIXELSTEIN's `px_reloc`
      re-deriving those words rather than adding a paragraph delta.
    * **`os88ui_gring`** (apps/os88ui.inc, the radio ring): eight CS stores
      and DS = CS per radio drawn, in ~20 packages, five drivers and
      CTRL.DRV. Not a loop, so not taken; the conversion stages the four
      points on the stack (DS = SS for the call), which has to be checked
      against every includer's stack class (SPEC.md 8.7) first.
    * **The two far-called modules' entries** (item 49): two #GPs a verb,
      a module ABI change (WSM_ABI and the preview's header), and the VM's
      ~150 CS stores if a bundle is found that stores per op.
    * **`OS88_HUGE_INCR`** (item 42) has no consumer; it stops being a
      constant only for a claim above 1MB with consecutive LDT selectors,
      which is an ABI decision.
    * **Not yet exercised**: an overlay or carve MOVED by a kern_mega
      compaction (`cc_ovreloc` / `cc_ovcarve` re-deriving `[cc_ovcs]`);
      RunCPM running a CP/M program and the Apple II booting a disk under
      Bochs (both only reached their prompts); LOOM packing on kern_mega.
    * **The Victory**: the M4 test disk (COVL, CWORD + WELCOME.RTF, C64,
      APPLE2, RUNCPM) on the 286. Everything above is Bochs, a 386 CPU.
    * **No suite row**: the #GP counts here were taken with a throwaway
      logger and scratch scripts. A row that holds them at 0 wants track
      4's trap-census knob (KERN-MEGA-HANDOFF track 4 item 1) first.

**Review of tracks 1 (to M3), 2 and 3, after their merges (2026-10-18).**
Read against the code at `4da2a7b0`. At `OS88_BUILDNUM=1600`, both trees
whole `make`s: kern_big's `KERNEL.SYS` is byte-identical across tracks 1 and
2 (the one system-disk difference being `HDDTOOL.DRV`, item 26's installer
change), and across track 3's merge `KERNEL.SYS`, all six 360KB images and
the 1.44MB pair are byte-identical, the fast tier 53/53; under Bochs PAINT, SHEET, TEXPAD, TRACKER, TASKMGR and NOTEPAD start on the
merged kern_mega. No defect was found in the code. What is NOT complete is
below, and it is the work list: item 50 stays track 3's own account, and
this repeats none of it beyond naming whose file each piece is in.

51. **Open after tracks 2 and 3**, by owner:
    * **Track 2 delivered its whole brief** - all five items of plan 4
      item 2 are either out of kern_mega (35, 36, 39) or measured and kept
      with a reason (37). Two loose ends, neither its file: `[mega_xmnat]`
      is written by `mega_xminit` and read by nothing since 36 (one byte of
      `.text` and a store, mega.inc - track 1's); and item 38's HOLE IS NOT
      CLOSED by item 32 alone. Moving the read-ahead store above 1MB frees
      its 32K beside the dead rung, so the run under the FAT window (5K,
      purgeable, PINNED, at 24E0 in 38's reading) grows to ~70K - but that
      window still walls it off from the 472K run above, so the largest
      run is unchanged until the FAT window too is claimed top-down or
      above 1MB (13.3). **Not yet re-read off `mem_tab`** after 32; the
      figures here are 38's plus 32's arithmetic.
    * **Track 3 delivered steps 1-3 of its brief and deferred step 4**
      (the speaker includes) on a kernel reason, item 46 - correctly: a
      converted ISR that IRQ0 never reaches converts nothing. Its two
      KERNEL follow-ups are in TRACK 1's files and neither is taken yet:
      `osapi_mem_movable_x` mapping a DX with bit 2 set through
      `mega_cs2ds` before `mem_find_own` (48 - every shipped assembly
      package's region stays pinned on kern_mega until then), and
      `osapi_fsx_spk` (kernel/snd.inc) refusing on kern_mega with an
      `SPK_E_*` until IRQ0 can be routed to a package (46).
    * **`OS88_CODESEL` is right only for an IDENTITY data segment, and it
      is now compiled into binaries.** `(S >> 2) | 4` is the LDT alias of a
      claim BELOW A000, the only place a claim is today. 13's direction is
      claims above 1MB behind `mega_ldt_alloc` selectors (item 30), and for
      one of those the shift names an unrelated entry - possibly one in the
      allocator's own range - with no fault to say so. The macro is in
      crt0 (every C package with an overlay), `op_cseg`, LOOM's preview and
      WEAVE's canvas core, so this is an ABI question to settle BEFORE a
      package claim can land above 1MB, not after: either such claims are
      never handed to a package that far-calls into them (the kernel keeps
      code claims below 1MB, 13.2's list grows a line), or the answer
      moves into the kernel - an `OSAPI_MEM_CODESEL`-shaped slot that
      returns a code selector for a claim, allocating an alias descriptor
      when the claim is not on the identity map - and the macro becomes its
      real-mode fast path. The second keeps the macro's binaries right on
      today's layout and is the one that does not paint 13 into a corner.
      `OS88_HUGE_INCR` (42) has the same shape and the same deadline.
    * **For the DOS round (track 6)**: the read-ahead store above 1MB (32)
      is a kernel-owned block (`MX_KOWN`) in the very pool the owner's
      answer 7 hands to the DOS program whole. The handoff must flush and
      free it first - `dsk_rah_redo` with the width at 0, or `osapi_dsk_cache`
      AL = 0 - and the return re-solve it, exactly as `mega_enter` does at
      boot. A store the DOS program overwrote and the kernel then SERVED
      would hand back another program's bytes as a disk's.
    * **The Victory has run none of 30-49.** The read-ahead landing (32) is
      the piece Bochs cannot stand for: on the Victory every C: transfer is
      a BIOS reflection through the PicoMEM's option ROM (13.2), which is
      exactly the path the landing exists for, and a C: to B: copy and
      compare there is its first real test. mega.img at `321e43c6` was
      sent for that.

**Track 1, continued.**

52. **Modules run above 1MB** (13.3 step 2's second half; 13.5 is the
    design and what it found). `mod_need` loads and checks a module as it
    always did, and then, in protected mode, `mod_hi` copies the WHOLE claim
    - image and the bss past it - into a CODE/DATA PAIR from the allocator
    (`mega_ldt_alloc2`: code at entry n, data at n + 1, one mx block under
    them), re-arms every slot that named the old alias with the pair's code
    selector, and frees the conventional claim; `[MODR_SEG]` holds the code
    selector and its TI bit tells `mod_free_row` to give the pair and the
    block back. The data half is code + 8, and that is the whole of the new
    rule: `mega_dsimg` and `mega_csdata` (CSDO and PUSH_CSDATA) add 8 for a
    selector in the allocator's range, and `mega_cs2ds` (the CS-write and
    code-in-DS fixups) asks the descriptor's executable bit first. A module
    goes high only if the census clears it (`MOD_HIOK`): DOCK, EXTD, WIN95,
    DESK and STIKMENU. DESK.DRV's library, whose LIB verb answered a sum on
    CS, gets a code descriptor of its own over the library's bytes
    (`mega_dklibf`, freed with the image). Measured under Bochs: DESK.DRV
    5KB at 138000h with its library's descriptor at 138200h (all three
    Sticky Apps draw), WIN95.DRV 2KB (the Windows theme draws), DOCK.DRV
    3KB (the strip moves to the left edge), STIKMENU.DRV 16KB (the panel
    composes every card and picture); switching the theme and the dock back
    freed both pairs and both blocks, and switching again re-took the same
    block under the same selector. CTRL.DRV stayed conventional, as the
    census says it must. kern_big's kernel and all six images are
    byte-identical.
    **Two limits, both deliberate.** A module loaded at BOOT, in real mode,
    is not moved at `mega_enter`: DOCK.DRV and WIN95.DRV store their own CS
    into kernel vector tables when they hook (`dkv`, `thv`), so moving one
    after its hook would leave those far pointers on the freed copy - a
    module loaded in protected mode moves BEFORE its hook runs, which is why
    `mod_hi` sits between `mod_check` and the return. And CTRL.DRV stays
    low: its two file writes are the census's blockers, and the panel is
    held only while it is open, so 16KB for the length of a settings
    change is not worth a staging buffer in every write path it has.

53. **The kernel's blocks come from the TOP of the pool** (13.4.1).
    `mx_alloc` searches downward for owner FEh - the candidate ends at the
    pool's top and an overlap moves it to end where that block starts, so
    it strictly falls and terminates - and upward for everybody else, as it
    always did. Under Bochs the read-ahead store's base is FF8000h and
    `tests/megaxm` still allocates at 130000h; compaction above 1MB is
    refused for the two reasons 13.4.1 gives.

**The installer, after the merge - the Victory's install refusal.**

54. **`No system disk: A:k30 B:k5` on the Victory, and the line now shows
    the compare.** The owner's run of item 27's line, booted from
    `mega.img` with a kern_big install on C: (Slot 1, 503M): A: mounted and
    its root walked to the end - 30 entries, which is that root less its
    label (31 with a SYSTEM.CFG on it), KERNEL.SYS the first - and B:'s 5
    likewise, with no name matching on either. The fence passed (a package
    would have seen 7 of A:'s 30, the rest being hidden and system), so the
    DIRECTORY was read and the NAME COMPARE never agreed. Under Bochs the
    same install says Done, natively and with every floppy access forced
    through the BIOS (item 29), so the cause is the 286 or the PicoMEM.
    `hd_istat` fetches with `push cs / pop es`, so on kern_mega the
    kernel's `rep movsb` of the name into `hd_ifind` (dsk_find_x's
    `.staged`) is a WRITE through the LDT code alias: it faults, `mega_gpw`
    converts ES in the frame and the string op runs again, and
    `hd_iname_same` then reads the buffer through DS. By reading: the bases
    agree by construction (DS is `[hd_tseg]`, the alias is `[hd_tseg] >> 2
    | 4`), a reflection cannot nest inside `mega_svc` (every gate is an
    interrupt gate, and the real-mode half's IRQs are the ROM's own), and
    `mega_gpw` restarts a `rep movsb` exactly. So the leading suspect is the
    one thing Bochs's 386 cannot show: a 286 restarting a MOVS whose WRITE
    faulted with SI or DI already stepped, which puts the name one byte off
    in every record and changes no count. Not proven, so nothing is changed
    on its strength. The refusal now carries the experiment instead -
    `hd_isd_rec`, after a `k` entry, fills the record with `#`, fetches
    ordinal 0 again and shows four fields:
    `No system disk: A:k30 RRRRRR CCC DDDD WWW`
    * **R** (6) - fetched the walk's way, ES = CS, as DS reads it;
    * **C** (3) - that same buffer read through CS;
    * **D** (4) - ordinal 0 fetched again with ES = DS, so nothing faults;
    * **W** (3) - the wanted name through DS (`KER`).

    `#` is a byte nothing wrote, `?` one that is not printable. A healthy
    record reads `KERNEL KER KERN KER` (Bochs, with a TEST build seeking
    KERNEL.SYX: `A:k31 KERNEL KER KERN KER`). **R shifted - `ERNEL.` or
    `#KERNE` - with D right** is the fault restart, and the fix is to take
    the fault out of the path (HDDTOOL's fetches with ES = DS, or a write
    to ES:DI before the string op in `dsk_find_x`); **R `######` with C
    `KER`** is a write that landed at CS's base and not DS's; **R and C
    both `######`** is a write that went somewhere else entirely; and **R,
    D and W all right** puts it in the compare. The fields cost the line
    its next entry (B: no longer fits after A:), and it is the same
    question asked twice. HDDTOOL.DRV changes on kern_big too, as items 27
    and 28 did - the line is right on both kernels; HDD.DRV (HDTOOL_KB
    still 17) and kern_big's `kernel.sys` are byte-identical, two worktrees
    with `OS88_BUILDNUM` pinned and whole `make`s. The Bochs install (blank
    C:, Format, Install) still ends `Done - remove the floppy, Restart`.
54.1. **The answer: a real 286 restarts a faulted string write one element
    late.** The Victory's line read `A:k30 #ERNEL #ER KERN KER`. The fetch
    that faults (R, and C, the same buffer read through CS) never wrote its
    FIRST byte and wrote every later one IN PLACE, while the fetch that does
    not fault (D) is right - so when `mega_gpw` converted ES in the frame
    and ran `dsk_find_x`'s `rep movsb` again, the frame's SI and DI had
    already moved one element past the write that faulted. Bochs's 386
    restarts it exactly, which is why item 54's install passed there. It is
    not the installer's defect: EVERY string write a package makes through
    its own code alias or segment 0 - `push cs / pop es` then `rep stos` or
    `movs`, 146 such pairs across the shipped packages (2.4) - loses its
    first element on a 286, and whether CX moved too decides whether it also
    writes one past the end.
    **The fix measures rather than assumes.** Nothing is ever written by
    the faulting instruction - ES names a code segment (or is null) for the
    whole of it, so the FIRST write is the one that faults - so the right
    restart is the instruction's own starting registers, and the only
    unknown is how far the CPU moved them. `mega_strcal`, once at
    `mega_enter` with interrupts off, loads ES with `KERNEL_SEG` (the code
    selector) and faults a `rep movsb` and a plain `movsb` of its own;
    `mega_strcal_gp` records the frame's SI, DI, CX and IP and resumes at a
    LABEL after each (no instruction length assumed), and the advance -
    0 or 1 element each, anything else read as 0 - lands in `mega_sdr` /
    `mega_sdp`. `mega_strfix`, called from `mega_gpw` and `mega_null0`
    wherever they have just converted ES, re-reads the faulting instruction
    off the frame and, for MOVS and STOS only, takes that advance back off
    DI (and SI for MOVS), sized by the element and signed by DF, and off CX
    when there is a REP. Everything else returns at its first test, and a
    CPU that measured 0 returns before reading the instruction at all.
    The result goes to E9 as `kern_mega: string restart r<si><di><cx><ip>
    p<si><di><cx><ip>` - the IP digit being how far past the instruction's
    first byte the CPU put the saved IP, 0 being the prefix, reported and
    acted on by nothing. **Bochs reads `r0000 p0000`**, so the 386 path is
    unchanged. Bochs cannot produce a 286's advance, so the correction was
    exercised by POKING `mega_sdr`/`mega_sdp` to 1,1 in a running guest: the
    installer then got past the name compare and failed copying KERNEL.SYS
    - the over-correction a CPU that restarts exactly would suffer, and the
    proof that the path runs and moves the registers. `tests/cswrites.txt`
    allows mega.inc one more pair, the probe's deliberate `mov ax,
    KERNEL_SEG / mov es, ax`. kern_big is untouched (mega.inc is KERN_MEGA
    only). **On the Victory the install should now read `KERNEL KER KERN
    KER` and proceed**; if it does not, the E9 line is the next reading,
    and it needs a debug port this machine does not have - the photo of the
    installer line is the field instrument.
    **CONFIRMED ON THE VICTORY 286** (mega.img at `4ef5edf7`): the install
    over the existing kern_big C: started, completed, and the machine booted
    from C: to the desktop. The C: carried an earlier SYSTEM.CFG with
    ETHER.DRV wanted, and that came up too - The Wire opened and transferred
    files, the first field run of the network stack under protected mode -
    on the PicoMEM 1.x's emulated NE2000, the same card as its SB 2.0 and
    its BIOS-only C:.
54.2. **The DOS box on the Victory: "Not our handoff record".** Every DOS
    program the owner ran was refused at `hbm_dosrun`'s first step, the
    check that the record DOS.O88 posted begins `KDH1`. Bochs runs the same
    image to `exit code 042` and back at 16MB, at 4MB (the Victory's RAM,
    `OS88_BOCHS_MEGS=4`, new in `tools/os88bochs.py`) and at 4MB with
    SOUND.DRV, HDD.DRV and ETHER.DRV loaded, so it is not the heap and not
    the drivers. DOS.O88 posts from a data segment it has just written
    through, so the pointer is an identity segment the relocation table
    follows. What only the 286 does is RESTART A FAULTED STRING WRITE
    (54.1), and that copy was one: HIBER.DRV fetched the record with
    `push cs / pop es / rep movsb`, ES its own read-only alias. **It now
    copies through `PUSH_CSDATA`** - `push cs` on every other kernel, so
    kern_big's HIBER.DRV is unchanged - and the copy never faults. That is
    the source fix 54.1 called the fast path, and it does not explain why
    `mega_strfix` would get this copy wrong where it got the installer's
    right, so **the refusal now says what it saw**: `H ssss:oooo bbbbbbbb
    rrr`, the posted pointer, the first four bytes there read directly (a
    good record is `4B444831`) and `mega_strcal`'s REP MOVS figures for SI,
    DI and CX. Bochs, with the check forced to fail in a throwaway build:
    `H 9180:AE22 4B444831 000`. If the Victory now runs DOS, the restart
    path is still owed an answer for this shape, and hiber.inc's other 45
    CS writes and 10 pairs - which the park and the way back run through on
    kern_mega - are where it would bite next.
    **Confirmed on the Victory**: Test Drive III launched and came back
    (`exit code 000 (Arena: 586KB)`, `DOSP 0639K o 0171 b 0071`).
54.3. **...and the PS/2 KEYBOARD was dead after the return, the PS/2 mouse
    alive.** Bochs reproduces it exactly (its mouse is PS/2 too), and it is
    NOT kern_mega's: after the trip the PIC has IRQ1 unmasked with nothing
    pending, IDT gate 21h is `kbm_isr`, `kbm_old9` is `mega_k09`, and keys
    leave the BIOS buffer untouched - the 8042 is not raising IRQ1 at all.
    `hbm_wake`'s PS/2 restore (SPEC.md 96.45.2.2) rewrites the command byte
    with `mou_p2_init`'s PROBE-WINDOW value, `MOU_P2KOFF` (bit 4, the
    keyboard interface disabled) set, and never sent the `0xAE` that is
    `mou_p2_init`'s own last step. So every kernel's PS/2-mouse machine came
    back from a DOS run or a hibernate with a dead keyboard - kern_big's
    HIBER.DRV is fixed with it. Bochs after the fix: `ab` typed at the DOS
    window's prompt, the BIOS buffer 1Eh -> 22h. `soak -k mouresume -k
    kdreturn` green (the serial path, which this branch does not run). Beside
    it, kern_mega's park now BANKS the 8042 command byte and `mega_dwake`
    puts it back - the 3.3 ledger item - with `0xAE` and the keyboard's
    `0xF4`, so a DOS program that leaves the keyboard off on a machine
    WITHOUT a PS/2 mouse comes home typing too.

**M5 - the trap census (track 4, 2026-10-18).** Every #GP fixup is correct
and costs a fault, so a site in a loop is a slow program that looks like a
working one. The census counts them; it also found three things that are
not slow but WRONG.

55. **The instrument.** `make megatrap` builds kern_mega with `MEGATRAP=1`
    (`-DMEGA_TRAPLOG`) into `build/megatrap/`, so `build/mega.img` is never
    the census kernel by accident. `mega_fault` then writes one E9 line per
    #GP before the fixup runs: `T error CS:IP DS ES NAME`, NAME being the
    `O8` header's name at +16 of the image CS runs in (`-` for a C overlay
    or a Pixel part, which carry none). The shipped kern_mega and kern_big
    carry none of it (kern_big byte-identical, checked at one build
    number). `tools/os88bochs.py --build build/megatrap` boots it,
    `--linger N` keeps a sweep's boot running after MEGARUN so idle loops
    reach the log, and `tools/megatraps.py E9.OUT` ranks the sites, says
    which fixup took each (`xfer` mega_gpfix, `write` mega_gpw, `null0`)
    and resolves the IP against the image's own nasm listing, found by
    header name (`--lst NAME=PATH` for a part). The handoff's hand-made
    logger was this, once.
56. **Starting is quiet; using is not.** A startup sweep of all 48 shipped
    packages logged 829 lines, 760 of them isoTron's colour presenter, and
    a second sweep that left 23 likely loopers running a minute each logged
    29 (1942's `n_pushall`, once per call). Idle loops, attract modes and
    animations trap nothing. The cost is in what a program DOES: a WAV, a
    module, a picture. So a census is an exercise with the census kernel
    (`os88bochsui.py`), not a sweep. The other startup sites, for the
    record: `os88ui_gring` stores eight corner points through CS per radio
    button drawn (`apps/os88ui.inc`, shared, not a loop).
57. **SOUND.DRV: one trap per DMA block, gone.** `sbl_isr` and the IRQ
    discovery stubs loaded DS with `push cs / pop ds`; on kern_mega that is
    the read-only code alias, so the first write of every block trapped.
    A 9 s WAV 38 -> 0; Tracker on BEVERLY.MOD ~106 a second -> 0.
    **CORRECTED at review (2026-10-18):** the first fix BANKED DS in
    `sbl_dseg` at the hook, on the ground that `mem_can_move`'s IVT scan
    pins a hooked image - which SPEC.md 66.6.3.1 replaced with a PATCH:
    `mem_region_reloc` moves a hooked, idle image and rewrites the IRQ
    vectors to follow it, and nothing tells the driver, so after any such
    move the next block's ISR loaded the OLD base - freed memory or the next
    claim's - on kern_big as much as kern_mega (`tests/sndmove.py` is that
    scenario and stays green only because it never plays after the move).
    The ISRs now DERIVE DS from CS at the interrupt (`SBL_DSCS`): CS itself
    on every real-mode kernel, `(CS & ~7) << 2` for kern_mega's LDT alias of
    an image below A000h, which is where a driver image always is (only
    kernel modules go above 1MB, `mod_hi`). No bank, nothing to go stale.
    **That is the pattern for any driver ISR**, and a banked segment is the
    one to refuse.
58. **isoTron: 760 -> 0.** `it_praw4p`'s per-row words (strip row, two
    strides, last logical row) were written through CS because DS is the
    work claim in that loop. They live in the claim's unused bytes after
    the strip now; plain stores, a byte and a prefix cheaper on an 8088 too.
59. **A segment built by PARAGRAPH ARITHMETIC is not a segment here, and
    can be worse than a fault.** Only a multiple of 8 paragraphs is an
    identity selector (3.1). Any other value either faults (RPL bits set:
    Video, `vp_khdr`'s `mov ds, dx` with DX = 138Bh, the moment a .V88 is
    opened) or - bit 2 set - loads an LDT CODE ALIAS at base index x 512,
    readable, so reads come from the wrong memory with no fault at all; and
    a WRITE through it reaches `mega_gpw`, whose `mega_cs2ds` turns the
    alias into data segment `(S & ~7) << 2` and completes the write THERE.
    That is silent corruption of whatever lives at that address. Found in
    PiXEL (the work claim's sub-buffers, the master's row address and a
    flat file's trailing palette, all rounded to one paragraph - fixed, 8
    now), in Paint (`pt_srowset`, a staged BMP's rows: opening SAMPLE.BMP
    faulted on 4E41h - fixed, and a document session in TexPad, Word, Sheet
    and Paint is then 28 traps in all) and in the Video Player, which
    normalises to one paragraph at about fifteen sites in `video.asm`
    (`vp_khdr`'s callers, `vp_rptr`, `vp_raud`, the ring and layer paths) and
    so CANNOT PLAY A FILE ON KERN_MEGA TODAY. Video is not converted here: it
    wants its own session and the `vid*` rows behind it. Two things follow
    for the owner: an SDK rule (normalise to 8 paragraphs, `and si, 127`,
    never 15), and a kernel guard - `mega_cs2ds` should refuse an LDT alias
    that names no loaded image rather than redirect a write. Neither is this
    track's file.
60. **`mega_gpw` stores the WRONG SEGMENT for `mov [cs:x], ds`.** It runs a
    CS: store in its trampoline with DS swapped to the image's data
    segment, so a store whose SOURCE is DS writes that segment and not the
    caller's. PiXEL's PNG part built its service table that way, far-called
    its own claim and ran wild on HOUSE.PNG. The parts store through AX now
    (`pxpart.inc` rule 5). Still in the tree: `apps/os88spk.inc:496` (track
    3's include), `apps/loom/lmpvmod.asm:130` and `apps/weave/wcanvas.asm:89`
    (neither on mega.img yet). The kernel fix is one case in the
    trampoline - `8C /r` with reg = DS must store the saved DS - and it is
    the right place, because nothing else can know.
61. **PiXEL opens every format on kern_mega now** - LAKE.JPG and FLOWER.JPG
    (JPEG, grey and colour), HOUSE.PNG, CAT.GIF (interlaced) - where LAKE.JPG
    faulted on the decoder scratch and HOUSE.PNG ran wild. LAKE.JPG's traps
    13,853 -> 533 (the IDCT's `pj_u` and the Huffman fill's `pj_hi` moved into
    the decoder scratch; the viewer's DDA loops stop on `cmp di, [cs:px_cend]`
    instead of decrementing a counter through CS). What is left, ranked, for
    the next census session: the JPEG colour path's SELF-MODIFYING `imul`
    displacements (three sites at 14,400 each for FLOWER.JPG - an 8088 speed
    design, so its replacement wants MartyPC's numbers beside it); GIF's
    LZW and scaler state words (`PS_*`, ~3,000 a site); PNG's inflate state
    (~11,000 a picture); and two per-row costs, `px_ks_emit`'s `push cs / pop
    ds` service entry and the part's far call into the package through the
    package's DATA segment (one `xfer` a row - the context would have to
    carry the package's code selector, which is track 3's helper).
62. **For the Victory.** `build/mega.img` from this branch in A:, and in B:
    the census exercise disk - Video, PiXEL, Paint, TexPad, Word, Sheet,
    Audio, Tracker and Note Pad in APPS, and in MEDIA the four sample
    pictures, a WAV, BEVERLY.MOD, the logo .V88 and a document for each
    editor (`os88disk.py` over `build/*.o88`, sent beside this branch at
    1.44MB and 1.2MB). Tracker and Audio as before: the SB ISR no longer
    traps, so the `RFL` line should not move and the CPU it leaves should.
    PiXEL should open all four pictures, which it could not. The Video
    Player will fault on the .V88 (item 59) and is expected to.

63. **What track 4 leaves outstanding**, in the order it would be taken:
    * **Kernel, one case in `mega_gpw`'s trampoline** (item 60, `kernel/
      mega.inc`): a CS: store whose SOURCE is DS (`8C /r`, reg = 3) must
      store the DS the code had, not the image's data segment the trampoline
      swapped in. Until it does, three source sites store the wrong segment
      on kern_mega: `apps/os88spk.inc:496` (`os88spk_rp+2`, the speaker
      include track 3 owns), `apps/loom/lmpvmod.asm:130` and
      `apps/weave/wcanvas.asm:89` (neither on mega.img yet). Each is also
      fixable at the source through AX, PiXEL's `pxpart.inc` rule 5.
      **Reviewed 2026-10-18: the fix as written is half of it** - the
      trampoline also runs with CS = KERNEL_SEG, so `8C /r` with reg = CS
      (1) stores 0060h instead of the image's code selector
      (`apps/os88spk.inc:247` and `:511`, `mov [cs:os88spk_rp+2], cs`).
      Store the saved DS (`[mega_tds]`) for reg 3 and the saved CS
      (`[mega_tret+2]`) for reg 1. It is disjoint from item 54.1's
      `mega_strfix`, which is on the no-prefix arm.
    * **Kernel, a guard in `mega_cs2ds`** (item 59): refuse an LDT alias
      that names no loaded image instead of turning a write through it into
      a write at `(S & ~7) << 2`. It costs a heap-table walk on a path that
      is already a fault, and it turns silent corruption into a report.
    * **The Video Player cannot play a file on kern_mega** (item 59). The
      one-paragraph normalisations in `apps/video/video.asm`: the key reads
      before `vp_khdr` (the `.part` loop and the `.kp` reload), `vp_rptr`,
      `vp_raud`, a landed block's `add [vp_rdseg], ax`, the step-over-a-
      record pair (`add si, ax` then normalise, twice), the `VC_PO`
      advance, the timed `.ld` path, the layer record's `mov dx, es`, the
      audio staging's `and si, 15`, the super-packet chunk address and the
      EMS page frame's. Two need more than `and si, 127` / `and al, 0xF8`:
      the walk that compares DX:SI against an end held as a paragraph and
      an offset (BP:DI) must normalise both the same way, and `vp_xmk`'s DX
      is an XMS hold handle, so check it is never loaded as a segment
      before touching it. The bar is the `vid*` soak rows on kern_big and a
      .V88 playing under Bochs with the census kernel.
    * **An SDK rule and a ratchet** (track 3's `os88api.inc`): normalise a
      far pointer to EIGHT paragraphs, never one. The scan that found
      PiXEL's and Paint's - an `and r, 15` within a few lines of a
      `shr ax, cl` or `or ax, dx` feeding `mov es`/`mov ds` - is the shape
      a `tests/cswrites.txt`-style ratchet would take. Today it finds
      Video's and three PiXEL sites the census exercise never reached:
      `pxgif.asm`'s two master-row addresses on the ANIMATION path (`.r`
      and `.c1`, the same fix as `px_mrow`), and `pxedit.asm`'s Rotate
      column walk (`pe_srow`'s caller at `.cw`), which steps the SEGMENT by
      `pe_q` paragraphs a row and is therefore off the grid by design - it
      wants an offset walk (SI += the width a row) that moves the segment
      only by multiples of 8 paragraphs when the offset nears 64KB, not a
      mask.
    * **PiXEL's decoder state through CS** (item 61), each a per-part
      conversion with `pxbench`'s ceilings beside it: the JPEG colour path's
      SELF-MODIFYING `imul` displacements (`pj_blk`, 3 x 14,400 traps on
      FLOWER.JPG - a speed design for the 8088, so the replacement is
      measured on MartyPC first); PNG's inflate words (`pz_bias`, `pz_bsb`,
      `pz_rd`, `pz_ft` - ~11,000 a picture); GIF's LZW and scaler `PS_*`
      words (~3,000 a site); and one trap a row in the part services'
      `push cs / pop ds` entries (`px_ks_emit`, `px_ks_scat`, `px_c2p`). The
      part's far call into the package (one `xfer` a row) is track 3's item
      50 and `OS88_CODESEL` (item 42) is now the way to make it.
    * **Not yet censused**: the games played with keys (Tank, Skies,
      WireBall, PIXELSTEIN, 1942 past its title), MIDIRack playing, the
      DOS box, Browser and FTPD (`--ne2k`), and the C packages that are not
      on mega.img (CWORD, WEAVE, LOOM, RUNCPM, C64, APPLE2, PACCMAN). The
      method is item 56's: the census kernel, a B: disk with the program
      and its data, and the program USED.
    * **Red on `origin/protected-mode` too, found while verifying, not
      track 4's**: `pxbenchvga`'s BIG.BMP "first rows on the glass" reads
      4.62 s against a 3.90 s ceiling, 2 of 2 runs on the base; `picomem`'s
      two "channel 1 RACING" checks and its `khx` leg, whose `kslice.inc`
      ends inside an `%if`.
    * **The Victory has not run item 62's images yet.**

**Track 1, closing item 51's kernel follow-ups.**

64. **Package regions are movable on kern_mega** (item 48). `osapi_mem_
    movable_x` maps a DX with bit 2 set - the region's LDT code alias,
    which is what `OS88_REGION_MOVABLE`'s `DX = CS` hands it there - to its
    segment before the fence, `(DX & ~7) << 2`, mega_cs2ds's rule, so every
    shipped assembly package's declaration lands with no package rebuilt.
    THE MOVE ITSELF WAS NEVER RUN before, and is now: `tests/heapfrag`
    under Bochs, `heapcheck.py`'s scenario by hand (PAINT then HEAPFRAG,
    Paint closed, R). Before the change the region suite reads R1-R4
    `0 0 1 0` - R3, *my region moved up*, FAILS, the region at 95C0 with
    `MC_RLOC 0`; after it, `0 0 0 0`, the region moved 95C0 -> 9DC0 into
    Paint's hole with its proc recorded, its three 50K claims re-owned by
    the new segment, and the package's own menu then opened and Close ran
    from the new home with no fault. The data-claim suite passes on
    both, every row it draws reading PASS.
65. **`OSAPI_FSX_SPK` refuses on kern_mega in protected mode** (item 46),
    with `SPK_E_NOTRATE` - kern_small's answer to the byte, so every
    caller's existing fallback is the path. IRQ0 is the kernel's gate
    there and never reaches a package's ISR; until it can be routed, a
    speaker ring would play nothing and channel 0 at the sample rate would
    run `sch_isr` at it.
66. **`[mega_xmnat]` is gone** - written by `mega_xminit`, read by nothing
    since item 36.
67. **The FAT windows the boot claimed no longer wall the floor** (item 38,
    and item 51's second bullet). Read off `mem_tab` under Bochs at the
    desktop: C:'s window (`MEM_P_FATW` + 2, 5K, purgeable, pinned) stood at
    2540 on a 72K hole - the dead rung and the read-ahead's freed 32K under
    it - and the largest run was **481K of 567K**. `mega_enter` now gives
    back every FAT window that is a claim, clean and not the live one
    (`dsk_fatw_lowf`, `dsk_fatw_drop` per volume, nothing at all if a FAT
    sector is dirty), and the volume's next mount takes it again first-fit
    from the floor: **558K** at the desktop, and **541K** after opening C:,
    whose window came back at 13A0, three claims above the floor. The
    remaining walls are the read-ahead's 5K landing (pinned, at the floor
    itself) and whatever the session claims.
    **For the DOS round (item 51's fourth bullet)**: the module pairs of
    item 52 are kernel-owned blocks in the same pool as the read-ahead
    store, so the handoff must drop the held modules (`mod_drop` - DESK.DRV
    and WIN95.DRV are held for as long as their feature is on) as well as
    the store before the pool is handed over, and the return re-take them
    on demand as it does today.
68. **M6 W3, the XMS door, is built on `kern_dos`'s side** (SPEC.md
    96.15.4, docs/plans/KERN-MEGA-DOS-PLAN.md 6). Under `-DKD_MEGA`,
    `kerndos/kdxms.inc` replaces the four refusing doors with a first-fit
    block table over the arena the launch block's tail names (`KDL_XBASE`,
    1KB-aligned and at or above 1MB, and `KDL_XKB`; no zeroing needed, cut at
    16MB), moves through `int 15h AH=87h` by the ROM's saved vector, and
    hooks `int 15h` for the program: `AH=88h` answers 0, and `AH=87h` with an
    end above 1MB outside the arena is refused with CF = 1, AH = 03h. The
    core's refusal of an extended-to-extended move is lifted under
    `-DDOS_MEGA` (+67 bytes, `DI = 2` with a linear source in `ES:SI`).
    **Measured** at the foot of `kerndos/kdos.asm`: `kern_dos` 33,585 ->
    34,611 bytes of image plus bss (842 code, 98 bss, 6 of calls, 80 of
    `CORE_MAX` hole), so kern_mega's `KD_IMG_KB` is 34 (35 with `DOSRMARK=1`)
    and the program pays a kilobyte; kern_mega's `DOS.O88` 47,610 -> 48,375
    bytes on disk. The plan's estimate was ~500. kern_big's `kernel.bin`,
    `hiber.drv`, `kerndos.bin`, the three other parts and `DOS.O88` are
    byte-identical at build 1600. `make build/XMSPROBE.COM` is the probe and
    its negative control (a raw `AH=87h` at linear 130000h); it has not run
    yet - the kernel's half (the arena claim in `hbm_dosrun`, the park) is
    another lane's, and Bochs is that lane's too. **Since run** (item 69):
    exit code 048 through the park, the control refused.
69. **M6 W0-W2: the DOS box parks the session above 1MB and comes back**
    (docs/plans/KERN-MEGA-DOS-PLAN.md 1.1, 2.5, 10.1; SPEC.md 96.40.9).
    Before any change Bochs confirmed both faults the plan predicted, at
    other instructions than it named: the windowed box faults in its own
    segment arithmetic (`mov es, ax` with 1A72h, off the 8-paragraph grid),
    and arm 3 in HDD.DRV's PIO write of `HIBERNAT.IMG` through
    `MEGA_SEL_LOW0`'s 4FFh limit. **And Bochs will not execute out of video
    memory at all** (`prefetch: getHostMemAddr vetoed`), so nothing of the
    park runs there: `mega_dropr` runs the loader stage from a copy under
    the top of the park, and kern_dos enters the park stub IN PLACE above
    1MB on the GDT the kernel left in the park's header. The snapshot is
    taken at `hbm_wrimg`'s moment and returns twice; the sum is one word per
    64-byte line, distributed; a mismatch restarts with a sentence naming
    the program; a small pool parks what fits and lowers `KDL_CAP`. Two
    `DOS.O88`s: `mega.img` carries a `-DDOS_MEGA`/`-DKD_MEGA` build, which
    refuses off kern_mega, and kern_mega's loader refuses kern_big's by the
    `'KMEG'` mark it lacks. **Measured** in Bochs: KDHELLO round trip,
    586 KB arena, `DOSP 0639K o 0018 b 0004`; three of four break-on-purpose
    writes caught (the fourth on an unsampled word, the accepted trade); ten
    trips with no `mx_tab` growth; a WAV through the SB16 before and after;
    a 192K park gives the program 130 KB and comes back. kern_mega `.text`
    **+2,094**, `.cold` +88, HIBER.DRV +642 of content inside its padding,
    kern_dos 35,002 (`KD_IMG_KB` 35 on kern_mega only). kern_big byte-
    identical. **The 286's way down (W2, `mega_r286`'s `[mega_drop]` branch)
    is built and has not run anywhere**: it is the Victory's.
70. **M6 W4 and W6: kern_dos in the HMA, option-ROM lines, and the keyboard**
    (docs/plans/KERN-MEGA-DOS-PLAN.md 10.2). kern_mega's kern_dos runs at
    FFFF:0010 with low trampolines that re-prove A20 on every vector; the
    arena is **621 KB** (586 before); `LOADFIX <program>` at the box's prompt
    is the off switch; `A20SHUT.COM` passes and goes red without the
    trampolines. The drop opens every option ROM's IRQ line for kern_dos and
    the wake primes it (unverified: the Victory's). And no key reached the
    desktop after a trip on a PS/2 machine, because `hbm_wake` writes the
    8042 command byte with the keyboard disabled and never sends `0xAE`;
    kern_mega sent it; **kern_big's live resume had the same defect**, and
    54.3 (b793f294) has since fixed it on every kernel, so the kern_mega-only
    copy went at the merge.
71. **M6 W5: hibernate on kern_mega in protected mode, and a resume that
    never leaves it** (docs/plans/KERN-MEGA-DOS-PLAN.md 10.3, SPEC.md 87.9).
    The image carries an extended section (the GDT, LDT and IDT, and every
    `mx_tab` block), and the fresh kernel reads the whole file into a block
    above 1MB and runs the PARK stub over it, so a 286 spends no reset on a
    resume. Three hibernate/resume rounds in a row under Bochs with a
    package holding 64KB of XMS: the 64KB equal every time, no fault, and a
    byte flipped in the section on the host is refused. Item 13 is
    withdrawn: `Hibernate (PM)` is gone. Two kernel defects found on the
    way, both fixed: **a code alias in ES across a 386 reflection** made
    every BIOS store through ES fault in real mode for ever (a 386 keeps a
    segment's attributes across the switch; `mega_svc` now loads ES from DS
    before clearing PE), and **`mega_n0` set in the image** (the picture is
    read one stepped word at a time through a null segment) made every later
    null fixup refuse. kern_big's 186 built artefacts are byte-identical
    across all of M6.

*(72-74 were written as 68-70 on a parallel track and renumbered at the
merge; their commits cite the old numbers.)*

72. **`OSAPI_XMEM_SEL` (0x0499) and `OSAPI_MEM_CODESEL` (0x049F) are in
    the table** *(renumbered at the elendilon merge of 2026-10-19, which
    brought `OSAPI_WM_ONWHEEL` in at 0x0499: kern_mega's four cells are now
    XMEM_SEL 0x049F, CODESEL 0x04A5, XMEM_WALK 0x04AB and MEM_HUGE 0x04B1,
    `osapi_table_end` 0x04B7 - none of them had shipped, so it is a
    pre-ship renumber and not a moved cell)* - the owner's decision, 2026-10-18, on 12.2's proposal and
    item 51's third bullet. SPEC.md 41.16 is the contract. Both are rare
    cells appended at the end (1,173 bytes, `osapi_table_end` 0x04A5), so no
    cell moved and `abilock` took the change without a `PKG_FMT` bump. XMEM_
    SEL hangs ONE selector off each pool block (`MX_SEL`, a word the entry
    had spare), re-aimed by a second call and freed by `mx_free` and
    `mx_relall`; CODESEL answers the segment itself in real mode and, under
    `CPU_F_PM`, the image alias, a code selector as it is, or a pair's code
    half for its data half - so `OS88_CODESEL` is its fast path and a claim
    above 1MB, the day a package has one, is answered rather than
    mis-shifted. The pool's table grew to `MX_NBLK` = 24 entries on kern_mega
    alone: the kernel's own blocks (the store, the module pairs) would
    otherwise have left a package two of `XM_MAX_BLKS`' eight. Cost:
    kern_big `.text` +26 (the cells and two bodies, the refusal written six
    bytes so every hot routine after it keeps its parity - `t_hotpar`),
    kern_small +27 with `OSAPI_XMEM_SEL` as its `xm_copy` (no body), no rung
    crossed on either. `tests/megaxm` is the gate (the block read and
    written in place, the re-aim, a window past the block refused 2, the
    alias for its own segment and the data selector refused): `sel 280C
    code 2754`, `ok` under Bochs - and `bad 0D` with `mega_codesel`
    amputated to answer DX unchanged, so the row can fail.

73. **The DOS park's region list follows the pool's table** (M6, merged
    beside item 68). `megados.inc` sized it `XM_MAX_BLKS + 10` because it
    records every pool block, and item 68 made kern_mega's table `MX_NBLK`
    = 24 entries - and a full list DROPS a region silently
    (`mega_dreg_add`'s `.full`), so a block of the kernel's own could have
    gone uncovered by the park's sum. `MPK_RMAX` is `MX_NBLK + 10` now (34
    regions, 0x518 of the header's 0x800). Checked under Bochs on the merged
    tree: KDHELLO.COM from C: through the park - `parked 027FK at 130000`,
    577 KB above its PSP, `exit code 042 (Arena: 586KB)` and `unparked`,
    with the read-ahead store's selector (2804h, FF8000h) intact after it
    and the pool holding the store alone, the park and arena rows freed.

74. **The DOS park takes the read-ahead store's KB** (KERN-MEGA-DOS-PLAN
    10.2's review: on a 1MB AT, ~192KB of pool less a 32KB store can put the
    park under `MPK_MIN_KB` and refuse the box). `mega_dosclaimf` first calls
    `dsk_rah_dropf`, which is `dsk_rah_redo` with the width ceiling held at
    0 for the one call - the store and its landing given back, the solve it
    falls into refusing at the floor, `[dsk_rah_cap]` put back as it was -
    and the next mount after the return takes the store again above 1MB.
    Bochs, KDHELLO.COM through the park: the park took the store's freed row
    0, and after the return and a B: mount the store was row 0 again at the
    pool's top under the same selector (2804h, FF8000h). The module pairs
    (DESK.DRV 5KB, WIN95.DRV 2KB while their features are on) stay summed
    and held; they are what a 1MB machine has left to argue about.
    Item 68 also answers the review's `mx_tab has 8 rows`: it is 24.

75. **M6 W7: a DOS session survives Ctrl-Alt-Del** (KERN-MEGA-DOS-PLAN
    10.3.1, SPEC.md 96.40.9). An anchor in GDT entry 0 names the park while
    it stands; the boot blob reads it before `drv_boot` - kern_mega writes
    nothing above 1MB until `mega_enter` - clears it, and enters the park
    stub as kern_dos would. Bochs: KDHELLO back after a reset, and a damaged
    park refused into an ordinary boot. `.text` +60, `.boot2` +494.
76. **M6's review answered, and the park is the runs in use**
    (KERN-MEGA-DOS-PLAN 10.4, 10.6). The park banks and restores the table
    bytes its sum's lines missed, checks its header against kern_dos's
    launch block and the build's constants, sums its own list, clears W7's
    anchor when it refuses, and puts the MSW back; the XMS door has 0Ch-0Fh,
    08h's largest block and 0Bh's handle bounds; `int 15h` E801h and its
    kin are refused; a W7 recovery tells the box why its program ended. And
    the park is `[0, mem_base)` plus the claims, a bit a KB: **196KB where it
    was 639KB**, the arena still 621KB - the 1MB AT's case.

**Packages above 1MB (13.3 step 4), wave P1: the file layer takes a buffer
there.**

77. **A selector above 1MB is a file buffer now.** It is the first step
    of packages-high, because every package's file I/O goes through it.
    It is also testable without moving any package: `OSAPI_XMEM_SEL`
    already hands out exactly such a selector. Two layers, as the survey
    found:
    * **The upper layer** (`dskw_*`, kernel/diskw.inc). The two doors ask
      `dskw_hiseg`. Where `mega_s2seg` answers FFFFh it keeps the caller's
      selector in `[dskw_seg]` and sets `[dskw_hi]`, and the body then
      moves the OFFSET and never the segment:
      - `dskw_norm` does nothing;
      - `dskw_runmax` answers 0, so every sector goes through `dskw_one`
        and the scratch;
      - `dskw_xclus`'s stage adds 512 to `[dskw_src]`.

      The compressed read keeps R as an offset inside the one window and
      refuses a stream that would cross it (U of 64KB or more, R past a
      word). `dskw_czexp` takes the selector as it is.
    * **The lower layer** (`dsk_xfer`, kernel/disk.inc).
      - `dsk_runcap` answers 0 for any LDT selector, which puts every BIOS
        volume on the existing `dsk_secbuf` bounce. That covers native
        floppy and reflected `int 13h` alike, and a CODE ALIAS used as a
        buffer, whose page arithmetic was wrong before.
      - A driver volume whose buffer is an LDT selector gets `.drvhi`, a
        sector a call through `dsk_secbuf`. HDD.DRV's rung 0 would be
        refused 09h by `mega_svc`'s fence otherwise.
    * **lz's source slide** (`lz_at`, +800h to DS) goes through
      `mega_slidef` for an LDT selector. That re-bases `MEGA_SEL_SLD`,
      GDT FFE0h, the identity of a ROM segment nothing loads. It shares
      `MEGA_SEL_ODD`'s caveat: one scratch per machine.

    **Measured** under Bochs at 4MB with `tests/megaxm`'s new file leg, off
    HDD.DRV's PIO volume and again off the BIOS boot partition
    (`--bootc`). Each run:
    - writes 40,000 bytes straight from a 64KB window above 1MB;
    - reads them back into a second window at offset 1234h with
      `FILE_READ`;
    - reads 16KB with `READ_AT`;
    - expands a 241-byte packed file into 50,000 bytes in place. Its R is
      49,759, so the decoder slides at once.

    **`MEGAXM: file C350` / `ok` on both.** kern_big's KERNEL.SYS is
    byte-identical.

    Two bugs the gate caught on the way:
    - A byte placed between `dskw_src` and `dskw_seg` broke
      `lds si, [dskw_src]` everywhere, and C: never mounted. There is an
      assertion now.
    - The high arm STORED R over the caller's offset where it must ADD it.

    **Not covered: the redirected volumes** (a RAM disk, a cable share).
    Their FSV verbs take the buffer in DX and RAMDISK.DRV normalises it,
    so a high buffer there is wrong. That is a refusal to build before a
    package placed high can run off one, and it is item 78's to settle.
    `OSAPI_XMEM_FREE` of a block whose selector the caller still holds in
    ES faults at the cell's own `pop es`. This is the SDK's "reload the
    register" rule; the test now obeys it.

78. **A package that says `OS88_HIGH` runs above 1MB** (wave P2).
    **The opt-in** is bit 7 of the header's stack-class byte (decision 14.1).
    `inst_pkg_spawn` drops it by shifting the index left first, which costs
    no byte on any kernel; `os88pkg.py` masks it before its class check;
    `abilock` took it as additive.
    **The move.** `ld_hi`, at the head of `ld_start` so the disk path and
    `OSAPI_PKG_START` share it, finds the image in an ordinary conventional
    claim with ES on it. `mega_pkghif` copies the whole region into a
    code/data pair from the pool. The block's owner is 80h | slot, which
    `mx_relall` and the cells match exactly and so never touch. The
    conventional claim goes back, and `[ld_base]` - and with it `I_SPTR`
    and `W_SEG` - becomes the pair's DATA selector. There is no room or no
    entry? It stays low, which is not a refusal.
    **The kernel's arms**, each one test of bit 2 (an LDT selector, so a
    pair's data half whose code is 8 below):
    - `MEGA_CSELTOP` and so `MEGA_PCALL` (the entry proc, `wm_pkgcall`'s
      every callback, `sch_rhook`, `drv_pkg_disp`);
    - `mega_frame_cs` (a worker's frame);
    - `mem_reloc_call`'s package arm;
    - `mega_gpfix` (a far transfer through its own DS, its code half checked
      by `mega_codesel`);
    - `mem_own`, which takes the region being loaded (`[ld_base]`) or a live
      instance's `I_SPTR`, since a pool block has no `mem_tab` record and
      the entry proc claims before step 9 publishes it.

    `mem_free_rec_x` and `ld_unreserve` give the pair and its block back.
    **Measured** under Bochs at 4MB with `tests/megahi` (OS88_HIGH,
    `OS88_STACK_192`), launched twice:
    - `ds 2814 caps 0B1B` both times. That is 5KB under the pool's 0B20,
      and the same KB the second time, so the teardown gave it back.
    - `claim ok` (an `OSAPI_MEM_CLAIM` from the entry proc, written, read
      and freed), `file ok` (its own .o88 into its bss), `tick` (a timer
      callback), `worker` (a spawned worker), `tick`, `ok` (the window
      destroyed with the worker alive in `OSAPI_TASK_ALIVE`).

    The first build's own worker RETURNED, which a worker must never do:
    there is nothing under its frame. The `ret` executed the package's
    header and ORed 47h into its own code. That was the test's bug, and
    the instrument is the record of the rule.
    **What it does not do yet**: no shipped package says OS88_HIGH. The
    census of which can (no arithmetic on their own CS/DS, no `OS88_CODESEL`
    of their own DS, no IRQ vector stamped with their own CS, no re-home,
    no RAM disk or cable share for their own buffers) is item 79's.
    `mega_idt_gate` and `mega_ivt_sync` would mis-take an IRQ vector a
    high package stamped with its own CS; the census keeps such packages
    low rather than teaching those two.

79. **The census, and 24 packages say `OS88_HIGH`.** Three read-only
    agents walked every shipped assembly package's own code and every
    `apps/*.inc` against item 78's rules: no arithmetic on its own CS/DS,
    no `OS88_CODESEL` of its own DS, no linear address of its own segment,
    no IRQ vector stamped with its own CS, no DMA from its own image, no
    re-home.
    **Opted in**: Hello, Timer, Mines, Font Viewer, Calculator, Solitaire,
    Piano, Fractal, Chart, the Task Manager, Note Pad, TexPad, Paint,
    Sheet, The Wire, Telnet, Browser, FTPD, Recorder, Frotz, ArtfulType,
    Audio, Tracker and MIDIRack, plus ModPlug (an on-demand build).
    **Kept low:**
    - Word and Scribe. Each re-homes into a parts carve (`OS88_REHOME`),
      and lifting only its loader would re-home a pool region, an untested
      path. A high-aware `OSAPI_PKG_REHOME` is what would lift them.
    - The three Sticky Apps, deliberately rather than of necessity. Their
      library calls back through each app's own DS, which costs a
      `mega_gpfix` trap per callback. That is correct but unmeasured on a
      286, and their windows redraw often.
    - Everything else, unreviewed: the fullscreen games (which hook IRQs
      and rate hooks), the C packages (crt0's `OS88_CODESEL` is applied to
      claims, but its overlay binding was not walked), and DOS.O88, PiXEL
      and Skies, which re-home.

    **The includes that are NOT clean**, so a package using them stays low:
    - `os88la`, `os88ub` and `os88xgap`: a linear address of its own DS.
    - `os88spk`: its own CS into IRQ0's vector.

      Audio, Tracker and MIDIRack use `os88spk`, and are in only because
      `OSAPI_FSX_SPK` refuses on kern_mega in protected mode
      (`kernel/snd.inc`). Should that cell ever be granted, they must come
      back out first.
    - `os88parts` where it re-homes.

    The census also found one kernel nit, fixed: `osapi_mem_movable_x`
    decoded a pair's code selector as a paragraph (`(DX & F8h) << 2`). It
    now refuses a pool pair outright, which is the right answer for a
    region that never moves.
    Two latent bugs it found, both off today:
    - Audio's `AP_HANDOFF` build compares CS with `SSI_SEG`, which is the
      DATA selector for a high instance.
    - Every package's own file I/O on a RAM disk or a cable share is not
      covered (item 77).

    **Claims stay conventional.** Paint's row table and several others do
    paragraph arithmetic on their CLAIMS, so `OSAPI_MEM_CLAIM` handing a
    high package a selector would need a second, separate opt-in. That is
    decision 14.8.

80. **The Task Manager: RAM is RAM.** Under `CPU_F_PM` (`[tm_pm]`, asked
    once at launch), memory above 1MB is memory a program runs in, not a
    store.
    - The performance page's RAM figure is the whole machine, in MB to one
      place so it keeps `tm_kpair`'s eight characters: `RAM 0.3/3.6M` on a
      4MB Bochs. That is 640KB plus the 3,040KB above 1MB; 640KB-1MB is
      video and ROM.
    - The memory page's pool line reads `HIGH used/sizeK`. It counts the
      kernel's 192KB of tables and `.cold` under the pool's base, worked out
      from `XMEM_CAPS`'s base rather than assumed.
    - A package placed high reads `HIGH` in ADDR and is left off the
      conventional map, which drew it at its selector's paragraph before.
    - Its HEAP column adds the pool blocks it holds through the XMEM cells.

    That last needs to know whose a pool block is. `OSAPI_XMEM_WALK`
    (0x04AB since item 72's renumber, SPEC.md 41.16) answers it: a rare cell at the table's end,
    `abilock` additive. On every other kernel the cell is
    `osapi_xmem_sel`'s refusal, so it costs them the 6-byte cell and no
    body.
    **Measured** under Bochs at 4MB with Calculator, Mines and the Task
    Manager all loaded high:
    - `HIGH 242/3072K`: 192 kernel, 32 the read-ahead store, 18 the three
      regions.
    - Their three rows say `HIGH` with 6K, 2K and 10K.
    - The System row and the buffer rows are unchanged.

    The small build has no memory view and is untouched.
    **The page found a bug in item 78's loader, now fixed.** The heap page
    showed `TaskMgr Data 9C40 10K HELD` for a package whose region was
    high: its CONVENTIONAL region, never freed. `ld_hi` asked `ld_slot`,
    which answers off DI, the instance record, and at `ld_start`'s head DI
    is not the record. So the free was refused for the wrong owner, and the
    pool block was stamped 80h | garbage, which the teardown's free by the
    real slot would then miss.
    After the fix, `mem_tab` read off the running machine holds no region
    claim for either high package. MEGAHI twice reads the same pool KB.

81. **A package that says `OS88_HIGHMEM` claims above 1MB** (wave P3,
    decision 14.12). Bit 6 of the class byte, beside `OS88_HIGH`'s bit 7;
    `inst_pkg_spawn` masks both with `and bx, 3Fh` (a `nop` keeps
    `ui_task` on its parity) and `os88pkg.py` the same.
    - **The claim.** `mmf_osapi_mem_claim` and `_claim_hi` ask
      `mega_claimhf` first. Under protected mode, for a package whose
      header says so, 1..64KB is a pool block owned 0A0h | slot and a data
      selector over exactly those KB, kept in the block's `MX_SEL` so
      `mx_free` takes both. Anything else - over 64KB, no room, no LDT
      entry, a driver, a package that did not ask - falls to the
      conventional heap as before. `OSAPI_MEM_FREE` routes a pool selector
      to `mega_claimfreef`; the instance's teardown frees the slot's claims
      with its XMEM blocks (`mx_relinst`).
    - **The resize.** `OSAPI_MEM_REGROW` on one stays in the pool while it
      can and keeps DX: a shrink is the block's length and the descriptor's
      limit; a grow is a new block, a scratch selector for the copy, and
      the two blocks trading selectors so the old one goes back with the
      scratch. Past 64KB, or with no room up there, the claim MOVES DOWN -
      a conventional claim, the bytes copied, the pool block freed - which
      is a path-3 regrow and answers a new DX exactly as one does.
    - **The services, censused.** An agent walked every `OSAPI_*` body
      against a pool selector in ES or DX. Fixed:
      - `OSAPI_XMEM_COPY` turned ES into ES x 16 - below 1MB for every LDT
        selector, so a copy to or from a high claim (or an `OS88_HIGH`
        package's own segment, since wave P2) silently moved CONVENTIONAL
        memory nobody named. It reads the descriptor now, and `mx_copy`
        takes a conventional end above 1MB when it is inside the caller's
        own region or claims.
      - `OSAPI_DECOMP` refuses more than 64KB of output into a pool
        selector, and `lz_dbump` leaves one where it is instead of bumping
        it onto 0FFF0h.
      - `OSAPI_PKG_REHOME` and an external sound ring (`SND_OPENF_EXT`)
        refuse one.
      - **A redirected volume** takes one now: `drv_fs_hi` moves a
        transfer verb 512 bytes a call through `dsk_secbuf` (READ and
        READAT as READATs, WRITE as a WRITE and APPENDs), because RAMDISK
        and NET do paragraph arithmetic on DX. That closes item 77's open
        end and decision 14.4.
      - `mega_gpfix`: a `pop es` or `pop ds` of a FREED allocator selector
        loads the null one. Real mode lets a program free the claim its ES
        names and carry on; the cell's own `pop es` was a #GP.
    - **The Task Manager** counts 0A0h | slot in a package's HEAP column,
      and `OSAPI_XMEM_WALK` documents the owner.

    **Measured** under Bochs at 4MB with `tests/megahi` (OS88_HIGHMEM),
    twice: `claim 281C ok`, `regrow 281C 18E0 ok` (8KB in the pool with the
    selector and both test words kept, then 80KB moved down to segment
    18E0), `claim file ok` (an 8KB claim filled by `OSAPI_FILE_READ` and
    left held), and `caps 0B1B` on both runs, so the teardown gives the
    held claim back. The first build's grow left the scratch selector in
    ES across `mx_free`, whose own `pop es` then faulted - the bug the
    gpfix arm above now also forgives in a package.
    **Opted in**: the twelve claims-safe packages that claim at all - Note
    Pad, TexPad, Sheet, Fractal, Chart, The Wire, Telnet, Browser, FTPD,
    Recorder, ArtfulType and Audio. A second census walked every claim
    each one makes for paragraph arithmetic and found none; three of them
    regrow and four declare claims movable (refused for a pool claim and
    ignored by all four, the claim never moving). **Kept low**: Paint (its
    row table is paragraph arithmetic), Frotz, Tracker and MIDIRack, and
    the eight `OS88_HIGH` packages that make no claim of their own.
    **Swept** under Bochs at 4MB: all twelve open and draw (Sheet, TexPad,
    Fractal's Mandelbrot, The Wire's no-card page among them). With Sheet,
    Fractal, Note Pad and the Task Manager up, the Task Manager reads
    `RAM 0.5/3.6M` and `HEAP 7/561K` - 7KB of the conventional heap in use
    with four programs loaded, Sheet's row reading 54K - where before this
    wave Sheet's claims alone were conventional.

82. **A driver that says `OS88_DRV_HIGHOK` runs above 1MB** (wave P4).
    Bit 7 of the header's +15, the DSV table length, which every kernel
    already clamps to its own table and kern_big now masks (decision 16).
    `drivers/os88drv.inc` sets it when the driver `%define`s
    `OS88_DRV_HIGHOK` before the include.
    - **At load.** `drv_hi`, right after `drv_bss` in `drv_load_at` - the
      image checked and zeroed and nothing of it run - copies image and bss
      into a pool block owned `MX_KOWN` under a code/data pair
      (`mega_imghif`, `mega_pkghif`'s body with the owner as an argument)
      and calls `mem_region_reloc` with the old segment and the pair's DATA
      half. That is the compactor's own walk (SPEC.md 66.6.3), so
      `drv_tab`, the class fast paths, `ss_row`, `drv_blkseg`, the claim
      owners and the IRQ vectors - and through `mega_ivt_syncf` the IDT -
      all follow without a list of their own. The claim is freed and
      `DRVR_KB` reads 0, as an HMA driver's does.
    - **At boot.** SYSTEM.CFG's drivers load in real mode, before
      `mega_enter`, so `drv_hiboot_f` runs once right after it and moves
      each loaded row that says so and that `mem_can_move` would let move
      (no frame in it, no service task), interrupts off for the copy and
      the re-pointing.
    - **The kernel's arms**: `drv_release` gives a high image's block and
      pair back (`mega_drvhifree`); `mem_own` asks `drv_owns_seg_x` for a
      selector no package owns, so a high driver's claims are its own;
      `osapi_vol_fence` maps a pair's code half to its data half
      (`mega_cs2dsf`); `mega_idt_gate` takes a pair from the IVT - the code
      half as it is, the data half (what the move re-pointed a vector to)
      as its code twin.
    - **The drivers' arms**: SOUND.DRV's `SBL_DSCS` derives DS as CS + 8
      for a pair; HDD.DRV's `hd_raw` bounces its own buffer when its image
      is a selector, as it already did in the HMA.
    **Opted in**: SOUND, HDD, ETHER, NET and EMS, and the SAVER and THMPAL
    overlays. **Kept low**: RAMDISK.DRV (its seed folds offsets into its
    own CS, `rd_seed_one`), USBMOUSE.DRV (the PicoMEM's ROM calls its
    `int 33h` hook in real mode) and HDDTOOL.DRV and RAMPAGE.DRV, which
    are a resident's second images and not `drv_load`'s.
    **Measured** under Bochs at 4MB with an SB16, an NE2000 and the ATA
    disk, SYSTEM.CFG wanting sound, the hard disk and the card:
    - `kern_mega: above 1MB: Sound`, `Hard Drive`, `ether` on E9 at boot.
    - SBTEST's click plays its two-second 1 kHz tone into `sb.wav`
      (352,256 bytes, all of it signal) - DMA, the IRQ through the moved
      vector, the refill - and again after the Control Panel unticked and
      re-ticked Sound, the reload placing it high from `drv_hi`.
    - Telnet to a server on the host (10.0.2.2:2323) connects and shows its
      banner through the moved ETHER.DRV.
    - MEGAXM's file leg (40,000 bytes written from a window above 1MB to
      C:, read back, READ_AT, the 50,000-byte expansion) passes through the
      moved HDD.DRV.
    - The Task Manager's heap page, with Sound and ETHER moved and before
      HDD.DRV was opted in, lists one driver image on the conventional
      map: HDD.DRV's 4K.
    **Not measured here**: a hibernate with a driver placed high (measured
    with item 83: it passes), and the Victory's PicoMEM, whose SB "DMA" is its ROM reading the ring in
    real mode - the ring is a conventional claim, so it is unchanged.

83. **A driver that says `OS88_DRV_HICLAIM` claims above 1MB** (bit 6 of
    +15 beside item 82's bit 7; `drv_publish` masks `3Fh`). A census of every
    driver claim found one worth it: ETHER.DRV's socket pool, the 6, 11 or
    17KB ladder `tcp.inc` claims top-down, which is only ever loaded into a
    segment register and whose `sk_reloc` is one store. SOUND.DRV's pools
    feed the 8237 or the PicoMEM's ROM through `sbl_ring_phys`'s page
    arithmetic, and HDD.DRV's claims are BIOS buffers or HDDTOOL's code, so
    neither opts in.
    - `mega_ownerof` answers the pool owner for a caller: 0A0h | slot for an
      `OS88_HIGHMEM` package, **0C0h | row** for an `OS88_DRV_HICLAIM`
      driver (`drv_row_ixf`), and every claim, free, find and regrow arm of
      item 81 now asks it.
    - `drv_release` frees the row's pool claims with its image
      (`mx_relallf`).
    - **The boot's claims are moved, not re-made**: ETHER's attach claimed
      its pool in real mode, so `drv_hiboot_f` calls `mem_hiclaims` after
      moving the image - every claim the driver holds that it declared
      movable, with no DMA head and of 64KB or less, is copied into a pool
      block under a selector with interrupts off, its relocation proc told
      through `PKG_DISP` (BX the old base, DX the selector), and the
      conventional claim freed.
    **Measured** under Bochs at 4MB with SOUND, HDD and ETHER at boot: the
    Task Manager's heap page reads `HELD 2K (1)` - one package's data claim
    - where before item 82 it read `HELD 23K (3)` (HDD.DRV's image and
    ETHER's pool among them). Telnet to the host server connects, shows its
    banner and sends a typed line through the moved pool.
    **The hibernate round trip passes with drivers high**: hibernate at
    16MB, the 4MB boot refuses with `No room above 1MB`, the 16MB boot
    resumes - the About box witness intact and SOUND and ETHER placed high
    again by their reload.

84. **The kernel's caches above 1MB** - what decision 13 deferred, taken
    because "RAM is RAM" is about the whole machine. A read-only census of
    every kernel claim on a running desktop sorted them:
    - **High now**, by tag (`mem_hitag`), at the top of `mem_claim_x` under
      `[ss:mega_pm]`, 63KB or less, falling back to conventional on any
      refusal: the window save-unders (`MEM_P_WSAVE + slot`, up to 63KB
      each), the menu save-under (`MEM_P_MSAVE`), the icon store
      (`MEM_P_ICO`), the multi-file list (`MEM_P_FLIST`) and the clipboard
      (`MEM_K_CLIP`). Every use of each is a segment-register load with
      offsets inside it, through `gfx_save`/`gfx_restore`, `rep movs` and
      the icon walk. `mem_free_x` gives a selector with one of those tags to
      `mega_hifreef`. A pool block has no `mem_tab` record, so it is never
      shed, moved or counted, which is right: shedding it would free no
      conventional memory.
    - **The boot's**, claimed in real mode: `mem_hicaches_f`, right after
      `drv_hiboot_f`, DROPS the save-unders (the next raise re-takes each
      high) and MOVES the icon store (the listings hold references into it).
    - **Stay conventional**: `MEM_P_RAHB`, the read-ahead's landing (it IS
      the bounce; the Task Manager names it `RdLand` now, where it showed as
      `FE03`); `MEM_K_COPY` and `MEM_K_CLONE` (64KB DMA-page transfers that
      a selector would serialize to a sector a call); `MEM_K_CMPR`
      (paragraph arithmetic off one base); `MEM_K_HIB` (the resume stub);
      `MEM_K_BAND` and `MEM_K_SC` (boot-time, 1-2KB, and SC regrows).
    - **Not yet: the FAT windows** (`MEM_P_FATW`, 5KB a volume). Feasible,
      but a selector window would load nine sectors one bounce at a time;
      the right shape is to load and flush through the 9-sector landing
      under `sch_lock`, which is its own change.
    **Measured** under Bochs at 4MB with SOUND, HDD and ETHER at boot and
    Note Pad, the Task Manager and the Disk window up: the heap page's
    System row reads **10K** - the landing and one FAT window - where it
    read 45K to 49K with the save-unders and icons in it; HELD 2K, PURGE
    10K. Raises redraw from their save-unders, a menu drops and restores,
    icons draw from the moved store, and Note Pad's Select All / Copy /
    Paste twice through the clipboard gives `hellohellohello`.
    The first build's KB-to-bytes conversion clobbered its own count
    (`mov cl, 10` over the KB in CX), so a 30KB save-under got a 1KB block
    behind a 64KB descriptor and overwrote the package region above it: a
    `#UD` at the region's dispatcher on the first raise.
    **The package sweep on this kernel** (items 81-84 together): 23 of the
    24 `OS88_HIGH` packages open and draw under Bochs at 4MB; Solitaire's
    file was missed by the sweep's list and passed in item 79's.

85. **A buffer above 1MB moves a RUN at a time, not a sector** - decision
    3's upgrade, taken now that 24 packages, their claims and the kernel's
    caches are all such buffers.
    - **The lower layer** (`dsk_xfer`'s `.bounce`): a BIOS volume's transfer
      into an LDT selector bounces up to nine sectors - the run the track
      allows - through the read-ahead's LANDING (`[dsk_rah_bnc]`, nine
      page-safe sectors that are scratch between fills) where it bounced one
      through `dsk_secbuf`. `[dsk_bnc_n]` is the run; `.bcp` copies it and
      `.unbounce` advances by it; a run of one keeps the `dsk_secbuf` path;
      and the read-ahead's gate refuses while a bounce is live, because a
      fill would land in the landing the bounce is using. No landing (shed,
      or never claimed) is the old path exactly.
    - **The upper layer** (`dskw_runmax`, `dskw_flushrun`): a high buffer's
      run is bounded by the OFFSET's 64KB wrap instead of being 0, and a
      spent run advances `[dskw_src]` by its bytes instead of the segment -
      so a file read or write into one coalesces exactly as a conventional
      one does and reaches the bounce as runs.
    **Measured** under Bochs at 4MB with MEGAXM run off B:, a 1.2MB floppy
    on the native 765 driver: its whole file leg passes (40,000 bytes
    written from a window above 1MB, read back into another at offset
    1234h, READ_AT, the expansion) with the writes and reads going as runs
    of 9, 5, 9, 2, 9, 8, 9, 3, 7, 7, 5, 4... sectors - one call per run where
    the old path made one per sector, which on a floppy is one revolution
    each. It passes again off HDD.DRV's volume. **Two bugs on the way**: a
    run that came out as ONE sector went to the landing while `.bcp` copied
    `dsk_secbuf` (`MEGAXM: at 3200 / bad 29`, READ_AT's sector 25), so one
    sector keeps the old path; and the cache-gate guard above.
    **RAMDISK.DRV says `OS88_DRV_HIGHOK` now** (decision 18 withdrawn for
    it): its two paragraph folds of `[rd_bufs]` are one routine, `rd_fold`,
    which leaves a pool selector's offset unfolded - the only such buffer is
    the seed's, read out of its own image. It loads and attaches above 1MB
    (`kern_mega: above 1MB: Ram Disk`); its volume, which mounts only once a
    size is set, was not exercised.

86. **The FAT windows above 1MB** - item 84's one deferral, which item 85
    made cheap: a selector window is nine sectors and loads and flushes as
    ONE run through the landing. `mem_hitag` takes the `MEM_P_FATW` range;
    `dsk_fatw_want` skips the conventional `mem_avail_lvl` gate under
    `[ss:mega_pm]` (the claim is a pool block, so the heap's figure is not
    its gate); an assertion keeps `FAT_SEG`, the pin every window is
    compared with, from ever reading as a pool selector. The pin itself and
    the boot's live window stay where they are, and `dsk_fatw_lowf` already
    drops the boot's other windows at `mega_enter`, so the next mount of
    each re-claims it - high now.
    **Measured** under Bochs at 4MB, B: a 1.2MB floppy mounted and MEGAXM's
    write, read-back and delete run off it (the FAT dirtied and flushed
    through a high window): `MEGAXM: ok`, and the Task Manager's heap page
    shows the kernel's conventional claims as **5K - the read-ahead landing
    alone**, which is the bounce and has to be conventional.

87. **The second census: 29 more packages say `OS88_HIGH`.** A read-only
    agent walked every assembly package item 79 left unreviewed and the C
    SDK, against item 78's rules plus three facts it checked in the kernel
    first: an `FSXF_RATE` hook is called through `MEGA_PCALL` (`sch_rhook`),
    so a pair is fine; `mega_gpw` decodes a pair's code half, so a `[cs:]`
    write or `push cs / pop ds` traps the same high as low (a low package's
    CS is already its LDT alias); and a re-home is refused only for a pool
    DESTINATION, so a high loader would hand its pool region to step 8a's
    free, the untested path item 79 named.
    - **Opted in, assembly (22)**: 1942, Arkanoid, Bounce, Gorillas, Missile,
      Pac-Man, TameGram, Cyclone, Dot Delirium, Dr Marco, Excitebike,
      isoTron, Tank, WireBall, the three Sticky Apps (Sticky Note, Desk
      Calendar, Desk Clock), FPTEST, IMGTEST, RLAPPLY, WIRE and PiXEL.
      `OS88_HIGHMEM` as well for the five whose claims are only ever loaded
      into a segment register: Dot Delirium, isoTron, Sticky Note, Desk
      Clock and IMGTEST.
    - **Opted in, C (all 7)**: crt0 does no arithmetic on its own segments,
      `cc_ovbind` puts the CODE half in the overlay's call-back vectors, and
      `OS88_CODESEL` is applied only to the overlay claim, which stays
      conventional. `CC_STACK_CLASS` carries the bit (Apple II, C64 and LOOM
      say it alone, keeping the default class). None says `OS88_HIGHMEM`:
      the overlay claim takes `OS88_CODESEL`'s shift, and RunCPM and LOOM do
      paragraph arithmetic on their claims.
    - **Kept low (7)**: Redline (`int 13h` and `int 15h E820` into its own
      DS), the Video Player (`os88xgap`, `os88ub`, `os88la` and `os88spk`),
      and the five re-homers - PIXELSTEIN 3D, Skies, DOS.O88's loader,
      Scribe and Word. (Item 79 named PiXEL among the re-homers; it is not
      one - the re-home was PIXELSTEIN's.)
    - **Decision 9 is withdrawn**: the Sticky Apps' library far-calls
      through the app's DS once a callback, which traps through `mega_gpfix`
      exactly as it does for a LOW package (`.gpok` there, `.pairq` here),
      so placing them high costs nothing the low placement did not.
    **Swept** under Bochs at 4MB, all 29 plus Solitaire: every one opens and
    draws - the fullscreen games, the Sticky Apps, PiXEL and the seven C
    packages (CWORD, the C64, the Apple II, RunCPM, WEAVE, LOOM, PaccMan)
    among them. RLAPPLY reports `refused 04`, which is its design: it
    applies the chipset setting, shows a toast and answers CF = 1 with no
    window, so the loader frees it - a high region freed at the entry proc's
    own refusal, which the sweep had not met before.
    **kern_big's side of items 81-87** - the class and DSV masks, HDD.DRV's
    bounce test, RAMDISK's `rd_fold`, the Task Manager - checked with the
    rows those edits can reach, one scoped soak: `sndmove drvmove drvcall
    drvup hdtake pkgrun pkgfence regapp heapcheck rdmove rdup fsclass tmload
    tmsmall lzdrv`, **15/15 ok**.
88. **Item 82 put a 286 into a boot loop, and Bochs could not have seen
    it.** Reported off 86Box's mr286 (16 MHz 286, OTI-067, SB16, NE1000,
    IDE): the loading screen, at most one frame of desktop, then POST
    again, for ever. Reproduced on the same 86Box profile and bisected:
    item 81's tree boots, item 82's (`4b840530`) loops. The fault was found
    with a locally patched 86Box that prints every exception and every
    shutdown reset to stderr: a `#GP` with error `FFE8` at
    `0028:mega_idt_gate`, the `mov es, si` of the high-image arm loading
    `MEGA_SEL_LDTD`, while CS was still the bootstrap's `MEGA_SEL_BCODE`.
    `mega_enter`'s FIRST IDT build runs on the six-entry bootstrap GDT, which
    has no entry `FFE8`; the arm is reached by any IVT segment of 2800h or
    more with bit 2 set, and this machine's ROM has one, so the `#GP` had
    nowhere to go and shut the CPU down. **Two defects in seven lines**:
    - the arm ran before anything could be above 1MB, so it now refuses
      while `[k_dsel]` still says real mode, and also refuses a FREE LDT entry
      (a real segment that only looks like a pair) rather than calling it a
      data half;
    - it also sent every 512-aligned heap segment at 2800h or above - every
      conventional driver image but the lowest - to the ROM path, where item
      81's code had given it its LDT alias. Bit 2 decides now: clear means a
      real-mode segment and the alias rule; set means a pair, looked up.
    A Bochs CPU is a 386, but that is not why it missed this: Bochs' BIOS
    simply has no such vector. **Verified on the mr286**: the fixed kernel
    reaches the desktop and stays there, B: and APPS open through the
    keyboard mouse, and CALC.O88 (`OS88_HIGH`) opens and draws above 1MB. The
    86Box patch is two `fprintf`s (`x86_doabrt` and `softresetx86` in
    `src/cpu/`); the BIOS's own triple faults at `F000:C3D2` are its memory
    test and block moves and are filtered out. **It is a tool now**:
    `tools/86box/` builds that 86Box with upstream's automation socket and
    `tools/os88box.py` drives it headless - `launch 286-mega` is this
    machine, `faults` is this diagnosis (docs/86BOX.md). The same run read
    the CALC check through it: `12*12` typed, 144 on the glass.
89. **The DOS park after packages-high, and CP/M's CALL 5 on every host**
    (KERN-MEGA-DOS-PLAN 10.7 and 10.5.1 item 3). P4 put driver images above
    1MB, and `hbm_down`'s `drv_shutdown_x` after the park's snapshot then
    freed their selectors and rewrote their state in place, so every DOS trip
    was refused as "wrote over the parked session". The park route tears
    nothing down after its snapshot now, and the tables' accessed bits are
    set before the sum. CALL 5 reaches `dos_cpm` on kern_big's windowed box
    and under kern_dos too (48 bytes of the core on both hosts),
    `tests/call5.py` the row.

### 10.2 The Victory 286 check (M1's first field run)

**What it is for:** the two things no emulator here can say - whether the
286's way back to real mode (CMOS shutdown 0Ah, 40:67, triple fault) works
on a real AT, and whether anything on the desktop's path stores through a
code segment (QEMU lets it; a 286 does not).

**Disks:** A: is `build/mega.img` (1.44MB, `make mega`); B: is the ordinary
1.2MB apps disk, `build/apps120.img`. No SYSTEM.CFG ships on mega.img, but
that does NOT mean no driver loads: the boot sniffs an OPL2 and a BIOS fixed
disk (SPEC.md 51.3.2), so on the Victory the PicoMEM's Sound Blaster and its
C: bring SOUND.DRV and HDD.DRV in (the network stays out). The first run
froze there, in real mode (10.1 item 7); the second disk carries the fix.

**Steps, and what each outcome means:**

1. **Boot.** The loading screen and the desktop are kern_big's, in real
   mode. Then the menu bar says **`protected, 286 reset`** for eight seconds.
   * No toast, but a black-on-white line under the menu bar: the switch
     faulted. Photograph the line - it is vector, error code, CS:IP and SP.
   * No toast and no line (a hang or a reboot): the switch itself failed,
     before the reporter existed.
   * The toast says **`real mode: ...`**: mega_enter refused, and the rest
     of the toast is why. The desktop is kern_big's and works; photograph it.
2. **Double-click C:** (HDD.DRV's volume, through the converted block call)
   and then **move the mouse**.
3. **Double-click B:.** The first read of a drive the boot did not mount, so
   it is a reflected `int 13h` - on a 286, **a CPU reset per call**. A
   listing means the reset path works. A hang or a spontaneous reboot here
   means it does not. **Then move the mouse**: a pointer that stops after a
   disk read is 10.1 item 9 coming back.
4. **Open APPS, double-click CALC.O88, type `12*12` and Enter** (144), then
   **close it and open FRACTAL.O88** (its worker draws the set).
5. **Expected to FAULT on a 286 and not on QEMU:** the Sticky Apps menu, the
   Control Panel and anything else that loads a module (KERN-MEGA-PLAN 10.1
   item 6) - each writes its own image through CS. A photographed fault line
   from one of those is a result, not a failure of the run.

**On the fifth disk, after A:**, the steps above stand, and the Sticky Apps
menu and the Control Panel fault as listed (Bochs has shown the first).

**Not on this run:** pressing Play in the Audio Player or anything else that
streams digital sound through the Sound Blaster - its IRQ discovery is the
known fault of 10.1 item 11. So does the speaker's SAMPLE player, which
takes IRQ0 through the IVT (spk_on). A beep or a tune through the FM chip is
fine to try.

**Timing is not the question yet**: the run answers "does it work", and one
photograph per outcome is the whole report.

**What is NOT done, and is M1's remaining work:**

* **The 286's way back is BUILT AND UNTESTED.** A 386 clears CR0.PE; a 286
  sets CMOS shutdown code 0Ah, points 40:67 at mega_r286 and triple-faults,
  and the way back into protected mode reloads GDTR, IDTR and LDTR on both
  CPUs (which QEMU does exercise, through the 386 arm). QEMU cannot test the
  286 arm - its CPU is a 386, and its reset resets the whole machine - so it
  is the Victory 286's first check.
* **The reported fault line on the glass, and on a 286.** The reporter
  draws through font_run with the gfx state forced clear; a fault inside
  font_run comes back once and then leaves only the E9 line.
* **The modules' CS writes** (above), and the drivers that point DS at their
  own image (tests/cswrites.txt's last block - Sound Blaster, NE2000 packet
  shim, LapLink, CH375, the HDD installer).
* **A package with a stack of its own** drawing unaligned text: font_run's
  kern_mega state is SS-relative and assumes LOW_SEG.
* **Interrupts during a reflected call** are the BIOS's alone: the mouse and
  every driver IRQ are masked for its length, so the pointer stops for a
  floppy transfer as it did before SPEC.md 7.4. M2's native floppy driver is
  what gives that back.
* **The modules stay on-demand** and the kernel stays in conventional
  memory: section 4's prize is M3's. It needs
no package changes, reaches a desktop with a third of the catalogue, and
shows what the sweep really costs in a shared file.

---

## 11. Open questions

1. ~~The floor~~ — **286, decided** (section 8).
2. **Minimum extended memory.** kern_mega needs the GDT (64KB) plus the
   kernel above 1MB. A 1MB 286 (384KB extended) holds today's kern_big-sized
   kernel. A 512KB kernel needs a ~1.6MB machine. Is a kern_mega machine
   *required* to have that, or does the kernel spill into conventional
   memory below some size?
3. **Is a bimodal ISR set ever wanted?** It would only be needed to keep the
   pointer and sound alive through a reflected ROM-only disk transfer. The
   recommendation is no: such disks refuse, or freeze the pointer, on
   kern_mega.
4. **MAME as the 286 bench**: whether it boots this tree's floppies and can
   be driven like `os88marty`.
5. **Whether a kern_mega machine still wants the 360KB system disk.** A 286
   has a 1.2MB or 1.44MB drive. The geometry set could shrink to two.

---

## 12. After the waves: protected mode is discoverable, and XMS becomes RAM

The owner's framing, 2026-10-17: under kern_mega **there is no XMS - it is
just RAM.** Everything above 1MB is reachable by a descriptor, so the machinery
real mode needed to reach it - XMEM.DRV, `int 15h AH=87h` and its CPU reset,
LOADALL (SPEC.md 41.13), unreal mode (`ub_set`, SPEC.md 41.15) - has nothing
left to do, and the parts of it that load a segment register the real-mode way
cannot run at all. Two things follow, and they are the end of this plan.

### 12.1 A driver or package must be able to ASK

Today nothing can tell kern_mega in protected mode from kern_big: the API
table is the same, and so is everything `OSAPI_CPU_INFO` answers. The
proposal is one more `CPU_F_*` bit in AH - **`CPU_F_PM` (0x10): segments are
SELECTORS** - set by `mega_enter` and never on any other kernel, so a binary
built before it reads 0 and keeps its real-mode behaviour on every machine it
already ran on. It is an SDK addition and not a re-contract (SPEC.md
20.2.0.1: `abilock.py --update` without a `PKG_FMT` bump). What the bit
promises, written once in os88api.inc beside the other four:

* segment arithmetic must stay on the 8-paragraph grid (section 3.1, item 18);
* no LOADALL, no unreal mode, no `int 15h AH=87h`, no `int 15h AH=88h`
  sizing of memory a program then addresses itself;
* the `OSAPI_XMEM_*` cells are the kernel's own and work from any context
  (12.2).

A refusal on the bit is the ordinary path (SPEC.md 47): a feature that has no
protected-mode route yet greys itself with the reason rather than faulting.

### 12.2 The routes, by kind of user

**Most XMS users never touch extended memory themselves** - they call
`OSAPI_XMEM_ALLOC`, `_COPY` and `_FREE`, with an opaque 32-bit base. Those
keep their ABI byte for byte if kern_mega implements the five cells itself:
a pool above its own tables (the GDT, LDT and IDT end at 0x124800; a 1MB 286
has 384KB above 1MB), and COPY as a `rep movsw` through a scratch descriptor
- no BIOS, no reset, and so no reason for the UI-task-only rule (os88api.inc's
note on tier 1), which kern_mega can drop. XMEM.DRV is then not shipped on
kern_mega at all (section 7 already said so). These users, from the survey:

| user | what it keeps in XMS | route |
|---|---|---|
| `apps/os88partsbody.inc` | lazy and scratch parts (SPEC.md 20.12) | the cells, unchanged |
| `apps/os88xgap.inc` | the shared gap buffer | the cells, unchanged |
| DOS box (`apps/dos`) | the box's XMS door (2.7) | the cells - and M6's question |
| Pixel editor | undo and layers | the cells, unchanged |
| RAM disk (`drivers/ramdisk`) | the store and its image | the cells, unchanged |
| EMS (`drivers/ems`) | EMS pages backed by XMS | the cells; the page frame is a descriptor rebase, which is a cheaper EMS than the copy |
| Video player (`apps/video`) | the XMS bank, through the cells | the cells, unchanged |
| Task Manager | shows the pool | CAPS, unchanged |

**Three users reach past the cells**, and they are the ones that need a new
route rather than an implementation:

| user | what it does | the protected-mode route |
|---|---|---|
| `apps/os88ub.inc` (Video player) | loads a segment register's HIDDEN base above 1MB (unreal) and addresses the bank in place | a selector: the bank IS addressable, which is section 4 item 5 |
| `apps/os88la.inc` (Video player, the 286) | LOADALL for the same in-place reach | the same selector - LOADALL is a 286 instruction kern_mega must never let a package run |
| `drivers/hdd/hdxms.inc` (HDD.DRV rung 1) | `rep insw` with ES's hidden base at the XMS address, and an A20 probe through FFFF | the same selector, and the probe deleted: `mega_enter` verified A20 and the bit says so |

So the one new cell the section needs is **`OSAPI_XMEM_SEL`** (BUILT,
10.3 item 72, with `OSAPI_MEM_CODESEL` beside it): DX:AX = a base
you own, CX = a window of up to 64KB inside it -> an LDT data selector whose
descriptor covers exactly that window, freed with the block. It is a refusal
(CF = 1) on every other kernel, which is what lets one binary carry both
routes and choose by `CPU_F_PM` rather than by build. The selector is stable
across a compaction (3.2), so no relocation proc is owed for it. This is M3's
LDT allocator used from outside the kernel for the first time, so it lands
after M3, and 12.1's bit can land now - it costs a byte of `mega_enter` and
makes every refusal above writable today.

## 13. Memory: high first, and the low region that must stay

The owner's direction, 2026-10-18: **load the kernel at the top of RAM and
take every claim from the top down.** Compaction packs everything but modules
and claims in use, so taking a low claim from the top no longer causes the
permanent fragmentation the lo/hi split was built to prevent. And going high
first leaves the bottom 640KB free the longest, which is what a DOS program
run beside protected mode (M6) needs most.

### 13.1 Why it works now

* **LDT selectors do not change when a claim moves** (3.2). Compacting above
  1MB copies the bytes and rewrites one descriptor base. No relocation proc,
  no `mem_rr_tab` entry, no pinned worker frame: HEAP-UNPIN-PLAN's whole
  problem does not exist for an LDT claim.
* **One direction is enough** once compaction runs. The lo/hi split kept
  long-lived claims (drivers, modules) and short-lived ones (packages) from
  walling each other in; packing toward one end does that job instead.
* **Conventional memory is used last**, so it stays contiguous for as long
  as the machine has anything above it.

### 13.2 What must stay below 1MB

High-first is the rule for everything EXCEPT a small fixed low region, and
each item in it is there because real mode or a ROM has to reach it:

| item | why it is low | found by |
|---|---|---|
| the reflection's real-mode half: `mega_svc` from `.rm` to the return, `mega_r286`, the capture stubs (`mega_cap2`..), `mega_capon/off` | it RUNS in real mode at 0060:xxxx, and a 286's BIOS jumps to `mega_r286` through 40:67 | 10.3 items 18, 24 |
| bounce buffers for BIOS-reflected transfers | a reflected `int 13h` gets a real-mode ES:BX; a BIOS-only disk (the Victory's PicoMEM C:) reads through it on every call | 10.3 item 11 |
| any DMA buffer a ROM touches | the PicoMEM's Sound Blaster "DMA" is its ROM doing a real-mode `rep movsw` from a seg:off it builds out of the 8237's page and offset, so the SB ring must be below 1MB on that card | 10.3 items 18, 20 |
| DMA buffers in general | below 16MB and inside one 64KB page, as today | the 8237 |
| the IVT, the BDA, LOW_SEG's task stacks | real mode reads them across every reflection | 2.2 |
| packages that do segment arithmetic | above 1MB a selector is not a segment, so `seg + N` is meaningless; only a package that declares itself clean (a header bit) or uses `OS88_HUGE_INCR` (M4) may be placed high | 3.1, 3.2 |

Everything else - `.cold` (done, at 0x125000), modules, the disk caches, the
FAT snapshot, the read-ahead, driver images that do no segment arithmetic, and
clean packages - is placed from the top of extended memory down.

### 13.3 The order to build it in

1. **The LDT allocator** (M3): descriptors with arbitrary base and limit from
   a reserved LDT range, code/data pairs where code lives, freed with the
   claim. Entries 1280-2047 alias segments A000-FFE0, which no image
   occupies, so they are free for it (10.3 item 10). BUILT (10.3 item 30)
   for single descriptors; the pair is 13.5.
2. **High-first for kernel-owned claims**: the caches first, through a bounce
   buffer for any transfer that goes to the BIOS, then the modules. The
   read-ahead store is BUILT (10.3 item 32), and so are the modules the census
   clears (item 52, 13.5).
3. **Compaction above 1MB** by descriptor rebase. REFUSED in favour of
   placement (13.4.1, 10.3 item 53).
4. **Packages high**, behind the clean bit and M4's SDK, after which the
   conventional heap is only what the low region and unclean packages need.


### 13.4 Extended memory has ONE allocator - decided

The handoff (track 1, step 2) left a choice: carve a region for the kernel
out of the `mx_*` pool, or give the pool and the heap one table. Neither:
the kernel takes its blocks from the pool's OWN table, under an owner byte
of its own (FEh, `MX_KOWN`). Why:

* **One free figure.** A fixed carve-out is memory the cells can never
  have and the kernel may never use; two tables would each need the other's
  figure to answer CAPS honestly. The pool's walk already does first fit
  at 1KB granularity, which is what a cache or a module wants.
* **The heap's table is the wrong shape for it.** `mem_tab` records are
  segments, relocation procs, page heads and MC_DMA doors - all of it about
  conventional memory a real-mode ES can name. A block above 1MB is named
  by a selector and moves by a descriptor rebase (3.2); none of `mem_tab`'s
  machinery applies, and the compactor's planner would have to learn to
  skip it everywhere.
* **The cells cannot reach it.** `mx_free` and `mx_copy` check the
  caller's owner byte, and no instance is FEh; `mx_relall` releases one
  instance's blocks. The kernel's own XMEM-cell blocks keep FFh, which a
  package's proc frees.

The cost is that the pool's table (`XM_MAX_BLKS` entries) is shared, so a
kernel block is one entry fewer for packages. Compaction above 1MB (13.3
step 3) is then a walk of this one table, rebasing descriptors.

#### 13.4.1 Placement instead of compaction - decided

13.3's step 3, compaction above 1MB by descriptor rebase, is REFUSED, and
what it was for is done by placement. Two facts decide it:

* **Only the kernel's own blocks could move.** A package's block is named
  by its LINEAR base (`OSAPI_XMEM_ALLOC`'s token, which `os88ub.inc` and
  `os88la.inc` even address in place), so nothing can rebase it; a
  compactor could only shuffle the read-ahead store and module pairs.
* **A module pair can be on the stack.** The running code's CS descriptor
  is cached by the CPU, so a module moved while one of its routines is
  executing goes on running the old copy - fine until the copy overlaps it.
  Every move would have to prove that no module frame is live, which is the
  pinned-worker problem of HEAP-UNPIN-PLAN in a new place.

So `mx_alloc` places the kernel's blocks (owner FEh) FIRST FIT FROM THE
TOP and packages' from the bottom, as `mem_claim_hi` and `mem_claim` split
the conventional heap (SPEC.md 50.3): the read-ahead store and the module
pairs never stand between two runs a package could have joined, and a
module dropped leaves its hole among the kernel's blocks, where the next
module refills it. Measured under Bochs: the store's descriptor base is
FF8000h, the top of 16MB, and `tests/megaxm`'s 64KB allocation still gets
130000h, the pool's base, with CAPS 32KB less than before the store
(3B20h against 3B40h).

### 13.5 Modules above 1MB - the design, BUILT (10.3 item 52)

What had to change, found while doing 13.4 and then built as written (items
2 to 4; the census of item 5 decided which modules):

1. **The read.** `mod_need` claims (`mem_claim_hi_x`) and `dskw_read_x`
   reads the whole file into the claim's segment. High, it reads into a
   conventional transient and copies up with `mega_lincopy`, then frees it.
   BUILT with no transient of its own: the module's ordinary conventional
   claim IS the transient, so the read, `mod_check` and the arming are
   unchanged and `mod_hi` runs after them.
2. **A code/data PAIR.** `mega_ldt_alloc` gains a two-entry form:
   code at entry n, data at n + 1, so the rule is DATA = CODE + 8 for an
   allocator selector - one compare in `mega_cs2ds`, `mega_dsimg` and
   `mega_csdata` (they refuse the range today, item 30) - and in
   `osapi_vol_fence` (`kernel/disk.inc`, item 26), which converts ANY LDT
   selector by the alias rule. BUILT in the first three; the fence needs
   nothing, because it compares the result with a published DRIVER
   segment, a driver is always conventional, and so a module's selector is
   refused there either way - which is the right answer for a module. A
   CS write in a module completes through `mega_gpw` exactly as before.
3. **The slots.** `mod_check` arms each slot with the image's code alias
   (`(S >> 1) | 4` after the shift it already does); high, it stores the
   pair's code selector, and `mega_mods_fix` has nothing to convert.
4. **The drop.** `mod_free_row` frees by segment through `mem_free`; high,
   by selector through `mega_hifree`, and the row has to remember which.
5. **What must stay low - the census comes FIRST, and it is why this
   round was not started on 2026-10-18.** Nothing in a module runs in
   real mode (13.2), but a module's DATA selector reaches places that
   treat it as a segment: a buffer inside its own image handed to the file
   layer is NORMALISED (`dskw_norm` adds BX >> 4 to ES - arithmetic on a
   selector), and one handed to a reflected `int 13h` is refused 09h by
   item 33's fence. CTRL.DRV writes SYSTEM.CFG, FORMAT.DRV and
   DISKOPS.DRV move whole tracks; any of them would fail on the Victory's
   BIOS-only C: and only there. So the round starts with a census of every
   module's buffers handed to `dskw_*`, `dsk_*`, `int 13h` and the
   `gfx_*` calls that take a segment, and moves high only the modules it
   clears - a row flag in `mod_tab` - with the others kept low as today.

   **The census, by reading (2026-10-18)**, for kern_big's modules:
   CTRL.DRV is blocked by the file layer (the SYSTEM.CFG save from
   `cpc_buf` and the shortcut's `.LNK` write, `dskw_write*` with ES = the
   image); DISKOPS.DRV likewise (`CLO_RSEQ cs`, a read-sequence cursor in
   the image handed to `dskw_read_seq`); HIBER.DRV by the file layer and
   by `apic_font_str` with DS = the image (and it refuses protected mode
   anyway); DESK.DRV by its LIB verb's paragraph arithmetic (item 41:
   correct on an alias now, but not on a pair). FORMAT.DRV moves tracks
   only through LOW_SEG's `dsk_secbuf`; DOCK.DRV and EXTD.DRV hand nothing
   of their own out; STIKMENU.DRV hands its own buffers only to `dsk_find`
   (a copy, no transfer) and `gfx_blit1` (no arithmetic). Every
   `dskw_*` path converts ES with `mega_s2segf`, so the file layer can
   never take a buffer above 1MB without a landing of its own. So the clean
   set is DOCK, EXTD and STIKMENU - 2 to 6KB each, transient - and the
   round is worth building only once CTRL.DRV (14KB, the largest) stages
   its two writes through a low buffer.

### 13.6 RAM is RAM - packages above 1MB, and what the machine says about it

The owner's direction, 2026-10-18: *"get to packages and kernel at the top,
and 'ram is ram' - with task manager (for kern mega) updated to show that."*
Built in waves (10.3 items 77-87):

1. **The file layer takes a buffer above 1MB** (item 77). Every package's
   file I/O goes through it, so it came first. `OSAPI_XMEM_SEL` already
   made such a buffer, so it was testable before any package moved.
2. **A package that says `OS88_HIGH` is loaded above 1MB** (item 78). Its
   region is a code/data pair from the pool, named by the data half
   wherever the segment was, and every place the kernel turns a package's
   segment into a CS learned the pair.
3. **The census opted 24 shipped packages in** (item 79). **The Task
   Manager counts the whole machine** (item 80), through
   `OSAPI_XMEM_WALK`.
4. **A package that says `OS88_HIGHMEM` claims above 1MB too** (item 81):
   its claims of 64KB or less are pool selectors, resized in the pool or
   moved down past it, and every kernel service that takes a segment takes
   one - the redirected volumes included, 512 bytes a call.
5. **Drivers run above 1MB, and ETHER.DRV's socket pool with them** (items
   82-83); **the kernel's caches and FAT windows are pool blocks** (items
   84, 86); **a high buffer moves a run at a time** (item 85); **a second
   census put 29 more packages high** (item 87), the Sticky Apps and all
   seven C packages among them.

On a Bochs desktop with SOUND, HDD and ETHER loaded and programs open, the
kernel's conventional claims come to 5K - the read-ahead landing, which is
the bounce - and every program that passed a census runs above 1MB.

What is NOT yet RAM is RAM, in the order it would be taken:
- the packages whose CLAIMS do paragraph arithmetic or far-call into a claim
  (Paint's row table, Frotz, Tracker, MIDIRack, 1942, Dr Marco, Excitebike,
  Tank, PiXEL, every C package with an overlay) - each a change in the
  package, rows or offsets inside 64KB selectors;
- a claim over 64KB, which stays conventional - a huge claim above 1MB
  wants a selector per 64KB and a package that steps them, which is a new
  ABI rather than an opt-in;
- the five re-homers (Word, Scribe, Skies, PIXELSTEIN 3D, DOS.O88's
  loader), Redline and the Video Player, which stay low by a census; a
  re-homed program runs in a conventional carve, so placing its loader high
  gains nothing;
- SOUND.DRV's rings and HDD.DRV's buffers, which the 8237, the PicoMEM's
  ROM or the BIOS must reach; USBMOUSE.DRV, whose hook a ROM calls in real
  mode;
- the kernel's own image and data, `.text` and `.bss` at KERNEL_SEG and the
  LOW_SEG stacks, which the reflection's real-mode half runs in (13.2).

`docs/plans/KERN-MEGA-HANDOFF.md` is the parallel work cut from this and
from section 10.

## 14. Decisions taken while the owner was away (2026-10-18), to look back over

Each is a call made without asking, because a reasonable default existed.
Each says where it lives, so it can be reversed.

1. **The packages-high opt-in is bit 7 of the header's stack-class byte
   (+15)**, spelled `OS88_HIGH`, rather than a new field. `LD_H_FLAGS` has
   no free bit. An out-of-range class already falls back to the default on
   every kernel (instance.inc's `cmp bx, SCH_NCLASS`), so an opted-in
   package on an older kernel gets the largest stack and nothing worse.
   The new kernel masks the bit off before the class lookup.
2. **A high region is named by its pair's DATA selector** wherever the
   segment is stored today (`I_SPTR`, `[ld_base]`, `W_SEG`, `MC_OWN`).
   Code is data - 8. That is the opposite of `MODR_SEG`, which holds the
   code half, and it is chosen because those words all come from the
   caller's DS or ES.
3. **(Upgraded by item 85: runs, through the landing.)** **A high buffer moves a sector at a time** (item 77). The file layer
   bounces through `dsk_secbuf` rather than claiming a landing of its own,
   which costs one reflection per 512 bytes on a BIOS-only C:. A
   multi-sector landing like the read-ahead store's is the upgrade if the
   Victory shows it matters.
4. **The redirected volumes are not covered** for a high buffer (item 77),
   and must refuse before a package placed high can run off one.
   **Superseded by item 81**: they are covered, by a bounce 512 bytes a
   call (`drv_fs_hi`) rather than a refusal, because a refusal would have
   been every high package's file I/O on a RAM disk.
5. **CALL 5 on kern_big stays PSP:0050's gate** (KERN-MEGA-DOS-PLAN 10.5.1
   item 3). The real CP/M dispatcher is kern_mega's HMA run only.
6. **The conventional hibernate image still has no sum on either kernel**
   (KERN-MEGA-DOS-PLAN 10.5.1 item 5).
7. **W6 primes every option-ROM line** (KERN-MEGA-DOS-PLAN 10.5.1 item 6),
   because the 8259 cannot say which line is held.
8. **A package placed high still gets CONVENTIONAL claims** (item 79).
   Paint's row table and others do paragraph arithmetic on their claims,
   so a selector from `OSAPI_MEM_CLAIM` would need a second opt-in. That
   is the next step toward all of RAM being RAM for a program, and it is
   not taken yet.
   **Taken by item 81** as exactly that second opt-in, `OS88_HIGHMEM`.
9. **(Withdrawn by item 87: the trap is the same low or high.)** **The Sticky Apps are kept low** (item 79) until a `mega_gpfix` trap
   per library callback is measured on a 286.
10. **Audio, Tracker and MIDIRack are high only because `OSAPI_FSX_SPK`
    refuses in protected mode** (item 79). If that cell is ever granted,
    they must come back out first, because `os88spk.inc` writes its own CS
    into IRQ0.
11. **The Task Manager's RAM figure counts only RAM**: conventional memory
    plus everything above 1MB. It leaves out the 384KB of video and ROM in
    between, so a 4MB machine reads 3.6M.
12. **`OS88_HIGHMEM` is bit 6 of the class byte** (item 81), the same
    argument as decision 1: no flag bit is free, and an old kernel treats
    the out-of-range class as the default one. Only claims of 64KB or less
    go high - one selector each - and a regrow past that MOVES the claim
    down rather than refusing, so a document that outgrows a segment keeps
    working exactly as on any other kernel.
13. **(Superseded by item 84 for the caches.)** **The kernel's own claims stay conventional for now** (13.3's "kernel
    claims at the top"). Measured rather than argued: 546K of the 562K
    conventional heap is free and in one run with the desktop and the high
    packages up, so the FAT window and caches are not walling anything a
    program can feel. Item 51's design stands for the day a measurement
    says otherwise.
14. **A freed selector popped back into DS or ES becomes NULL** rather than
    a fault (item 81, `mega_gpfix`). It is the closest protected mode can
    come to real mode's "a segment is only a number": the pop succeeds and
    the first USE of the register faults naming itself. Only a free entry
    in the allocator's range, and only `pop ds` / `pop es`, are forgiven.
15. **Paint stays conventional for its claims** even though its region is
    high: its row table derives each row's segment from the claim's by
    paragraph arithmetic. Making it high-claim-safe is a Paint change (rows
    as offsets inside 64KB selectors), not a kernel one. **Done in 14.14**:
    Paint declares `OS88_HIGHMEM`, and a canvas that fits one segment is
    laid out flat.
16. **A driver's high opt-in is bit 7 of +15** (item 82), the DSV table
    length. Every kernel built before it clamps that byte to its own table
    length (`drv_publish`'s `cmp cl, DSV_SIZE`), so a new driver on an old
    kernel publishes exactly what it did; the alternative, a new header
    field, would have been a `DRV_VER` bump for one bit.
17. **The boot's drivers are MOVED, not reloaded** (item 82): after
    `mega_enter`, by the compactor's own re-pointing walk. Reloading them
    would have re-read each file and re-run each attach - DHCP again for
    ETHER.DRV - where a move costs a copy.
18. **(RAMDISK.DRV: withdrawn by item 85, `rd_fold`.)** **RAMDISK.DRV and USBMOUSE.DRV stay conventional** (item 82): the RAM
    disk's seed does paragraph arithmetic on its own CS, and the PicoMEM's
    ROM runs the USB mouse's `int 33h` hook in real mode. The first is a
    small RAMDISK change if it is ever wanted; the second is not fixable
    from this side.
19. **A driver's claims have their own opt-in bit** (item 83), not
    `OS88_DRV_HIGHOK`'s: SOUND.DRV's image is clean and its pools are not.
20. **Kernel caches go high by an allowlist of tags** (item 84), not by a
    property of the claim: what makes a cache safe is how every reader
    uses its segment, which only a census can say. A new cache stays
    conventional until it is added to `mem_hitag`.

### 14.1 The owner's answers (2026-10-19)

The list put to the owner numbered the open calls 1-21; these answer its
first four.

1. **The conventional hibernate image gets a SPARSE sum, on both kernels**,
   if it costs under 200 ms. Only a sparse sum fits that on every machine: a
   full sum of ~640KB is ~2 s on a 4.77 MHz 8088 (and ~0.3 s on a 16 MHz
   286), while one word sampled every 256 bytes is ~2,560 reads - a few ms
   anywhere. It is distributed across the whole image, as KERN-MEGA-DOS-PLAN
   12.1 answer 3 asked of the park's sum, so it catches a wrong, truncated
   or cross-linked image and misses a stray byte. NOT BUILT YET (KERN-MEGA-
   DOS-PLAN 10.5.1 item 5).
2. **W6's prime stays generic** - every ROM-owned line, whatever card owns
   it. That is what is built; the PicoMEM-gated version was the
   card-specific alternative and is dropped (KERN-MEGA-DOS-PLAN 10.5.1
   item 6).
3. **`OS88_HIGH`/`OS88_HIGHMEM` stay in the class byte's top bits** (decisions
   1 and 12). Breaking new apps on old kernels would have been acceptable; not
   having to is preferred. They leave six bits for the class, against a
   handful of classes in use.
4. **The driver bits stay in +15 as well** (decisions 16 and 19). A driver ships
   only on a system disk, beside its own kernel, so it may break more
   readily still - but one `.drv` binary is shared by kern_big's, kern_small's
   and kern_mega's disks at a commit, so a change must suit all three kernels
   built from that commit. The one limit: with bits 6 and 7 taken, the
   service table (`DSV_SIZE`, 36 today) can grow to 62 bytes before +15
   stops holding its length.
5. **Two conventions for a pair are fine as long as they are clear**
   (decision 2). SPEC.md 8.7.2 now carries the table: which fields hold the
   data half, which the code half, and the interrupt vector as the one field
   that can hold either.
6. **Claims of a megabyte and more must work** for a program written for
   kern_mega, on a machine that has the memory. Decision 12's 64KB limit
   (and moving a grown claim back below 1MB) is therefore the CURRENT state,
   not the design. NOT BUILT: it needs a run of consecutive LDT selectors per
   claim (today's allocator hands out one or a pair) and 7's answer.
7. **The step between a big claim's selectors: an ADDITION is fine, a break
   probably, with more context first.** Proposed as an addition, so no
   break is needed: a new cell appended at the table's end, a "huge claim"
   taking AX = KB like `OSAPI_MEM_CLAIM` and answering DX = the first
   selector and CX = the step - 8 for a run above 1MB, 0x1000 for a claim in
   conventional memory on every kernel. `OSAPI_MEM_CLAIM` and the constant
   `OS88_HUGE_INCR` keep meaning exactly what they mean today, so nothing
   already built changes; only a program that calls the new cell walks by
   CX. The break would be making `OSAPI_MEM_CLAIM` itself answer a run: every
   `OS88_HIGHMEM` program stepping a claim by the constant 0x1000 would then
   walk into the wrong descriptors, silently, and `PKG_FMT` would bump.
   Ceiling either way: a 286 descriptor's base is 24 bits, so a claim tops
   out with the machine at 16MB.
8. **Kernel-specific app builds, and kern_mega-only apps, are acceptable
   when there is a good reason** - the two `DOS.O88`s being the first.
9. **The freed-selector leniency stays** (decision 14). The reload it
   forgives is the ordinary `push es` / free the block ES named / `pop es`
   shape, which real mode never noticed; in protected mode the `pop`
   itself would fault. Kept unless it starts hiding defects.
10. **POLICY: never hide RAM; every KB the user has is accounted for, and
    the front page's figures always add up** - "free" is what a program
    could use, the rest is the system's, and the two sum to the total.
    The front page shows the total and free (in M where that reads better)
    and one line for IVT+BIOS with today's "Pad" folded into it; the Memory
    page carries the detail and the map; the heap is the base 640K less the
    IVT, BIOS data and whatever system stays there, plus everything above
    1MB except the system at the top. Decision 11 (leave out the 384K) is
    REVERSED. It reaches kern_big's Task Manager too: a 1MB machine's HMA has
    to be shown and accounted for. NOT BUILT. What "total" can be is the
    open half: the BIOS reports base + extended (3,712K on the mr286's 4MB),
    and whether the other 384K is lost, shadowed or remapped is the board's
    business. **Settled (2026-10-19): report what is KNOWN, never guess** -
    the total is base + extended as the BIOS reports them, plus the HMA;
    the Memory page maps 640K-1MB from what can be read safely (the
    adapter's framebuffer, option ROMs by their 55AAh signature and length,
    the system BIOS) and calls the rest of that range unreported rather than
    attributing RAM to it.
11. **A BIOS transfer into a high buffer must WORK** (item 33's refusal is
    reversed): correct and fast where possible, refused only if the concept
    itself is bad. The shape: the native paths (`mega_fd13`'s DMA, which
    the AT's 8237 can aim anywhere below 16MB, and HDD.DRV's PIO) go
    straight into the high buffer; a BIOS-only disk bounces through the low
    landing a run at a time, as the file layer already does. NOT BUILT.
12. **Compaction above 1MB is in the design; placement was a stopgap**
    (13.4.1's refusal is reversed). The target: the system pinned at the
    TOP, a small real-mode part at the bottom (the part the DOS park moves),
    and EVERY program region and EVERY program claim above 1MB, compacted
    when a claim needs it, so a 2MB machine (1,664K usable on this BIOS)
    gives one program ~1,550K. The first real consumer is the Video Player.
    NOT BUILT. What it needs, all recorded here so it is not re-derived:
    - selector-named blocks move with NO relocation proc - the selector is
      stable and only its descriptor's base changes - provided nothing has
      it loaded in a segment register at the time, which is the safe point
      the conventional compactor already finds (`mem_frameless`);
    - blocks named by LINEAR address (`OSAPI_XMEM_ALLOC`'s token, read in
      place by `os88ub.inc`/`os88la.inc`) cannot move without an opt-in of
      their own - they are what pins the pool today;
    - "every claim high" needs every program clean: the ones that do
      paragraph arithmetic on a claim (Paint's row table, RunCPM, LOOM,
      item 87's kept-low seven) are fixed first, or they would be handed a
      selector and break silently;
    - a huge claim made of 64KB selectors (14.1 answers 6 and 7) needs each
      64KB piece contiguous but NOT the pieces adjacent to each other, so
      compaction need only make 64KB holes, and one claim can use
      conventional and extended memory together.
13. **The boot's drivers keep being MOVED** (decision 17): drivers are
    movable already (HEAP-UNPIN-PLAN), so a reload would buy nothing a move
    does not.
14. **The speaker must work on kern_mega** (decision 10's cell). Options in
    the owner's words: the whole program low, or a code claim that runs just
    what must be low. A third, to price first: leave the program high and
    have `OSAPI_FSX_SPK` install the IRQ0 handler as a PM gate to its code
    selector, the way `mega_ivt_sync` already builds gates for a high
    driver's vectors - nothing low at all. NOT BUILT.
15. **USBMOUSE.DRV stays low** (decision 18): it belongs with the small part
    of the system that must run in real mode. Splitting a driver into a low
    real-mode stub and a high body is a possible long-term shape, not a
    concern now.
16. **No minimum extended memory beyond FITTING** (11's question 2). Today
    `mega_enter` refuses under 192KB of extended memory and the machine runs
    in real mode, because the GDT, LDT and IDT sit at fixed addresses above
    1MB (`MEGA_GDT_LIN` 110000h - the pool at 130000h). A 1MB 286 whose BIOS
    reports no extended memory is a 640K machine and should still get
    protected mode, so the tables must be placeable in conventional memory -
    ~82KB of it (the identity GDT is a full 64KB, the LDT 16KB, the IDT 2KB),
    which is the cost to weigh against what protected mode buys there. NOT
    BUILT.

The Video Player, from 12's answer: it CRASHES on kern_mega today (its
`os88la.inc` path runs LOADALL), so it needs a protected-mode branch -
using RAM natively through the >64KB claim (answers 6, 7), not by
pretending a pool block is XMS and bouncing it. The owner notes a ~30%
difference it found from ALIGNMENT on interleaved-memory machines; the
pool's 1KB granularity already gives every base 1KB alignment, and where
that measurement lives decides whether more is needed.

How the Video Player picks its alignment (owner, 2026-10-19): it takes its
claim, speed-tests copies at offsets 0, 512, 1K and 2K into it, and wastes
the bottom of the claim when one offset is faster - interleaved memory. Its
protected-mode path must keep that probe: it works unchanged inside a
selector, the offsets being the selector's own.

14 again: the PM-gate option is the one to take if it works.
16 again: DEFERRED TO LAST. On a machine with no extended memory kern_mega
is a worse kern_big, until programs exist that need protected mode AND fit.

17. **CALL 5 reaching the real CP/M dispatcher on both kernels is wanted** -
    a compatibility gap old DOS programs may use, worth its 48 bytes.
18. **The pointer should keep moving through a reflected BIOS call**, if
    that is not a huge ordeal. What the owner sees on the PicoMEM is
    kern_big, where SPEC.md 7.4 already moves it; on kern_mega the
    reflection masks the mouse's IRQ (`mega_svc`'s B8h/3Fh) because the ISR
    is protected-mode code. The likely shape is cheap: the kernel's own code
    sits at KERNEL_SEG in conventional memory and is 8086 code, so the real
    `mou_isr` can be the vector during a reflection instead of the capture
    stub - after an audit of its path for anything that loads a SELECTOR
    (`[k_dsel]` is 10h in protected mode and means nothing in real mode).
    This reverses 11's question 3, which recommended no bimodal ISR.
    LONGER TERM, after kern_mega: a system that does not freeze for disk
    transfers at all - probably AT and up only, so that no per-controller
    driver is needed. Kept in mind, not planned.
19. **kern_mega's system disk is 1.2MB and 1.44MB only** - no 360KB or
    720KB, so a protected-mode program has room. `make mega` builds the
    1.44MB disk today; a 1.2MB twin is owed.
20. **The 86Box harness calls stand** - the patched GDB stub, the hidden
    F000 lines, `vm/286-mega` without the owner's VHD. The harness is
    expected to grow: much of what only 86Box emulates has until now meant
    a disk sent to the owner, and patching the emulator to suit the harness
    is the accepted way.

### 14.2 The work the answers make (2026-10-19), in order

1. The Video Player crashes on kern_mega (LOADALL): stop the crash first.
2. The Task Manager's RAM, by answer 10's policy, on kern_mega and on
   kern_big (the HMA). The owner's note on SYSTEM: kern_big SUBTRACTS
   `.cold` when it is placed in the HMA or a ROM, because that memory is no
   program's to use; on kern_mega the top of extended memory IS a program's
   to use, so everything the kernel keeps there - `.cold`, the modules, the
   caches, the tables - is counted in System.
3. The sparse hibernate sum, both kernels (answer 1).
4. BIOS transfers into high buffers work (answer 11).
5. The speaker on kern_mega through a PM gate (answer 14).
6. The pointer through a reflected BIOS call (answer 18).
7. Huge claims: a run of selectors per claim and the new cell (answers 6, 7).
8. **Every program works in protected mode, high and with its claims high**
   (owner, 2026-10-19). Whatever keeps a program low, or its claims low,
   because of what it does inside itself is reworked. The rule for HOW: a
   generic change when it is small; a kern_mega-only build of the program
   (answer 8's shape) when the change would grow it by more than 512 bytes
   or make it visibly slower on kern_big. The list at this commit:
   - not placed high at all (7): DOS.O88's loader, PIXELSTEIN 3D, Redline,
     Scribe, Skies, the Video Player, Word - the re-homers and the ones
     that program hardware or `int 13h`/`int 15h` into their own DS
     (item 87);
   - high, but their claims kept low (15 that claim and do not say
     `OS88_HIGHMEM`): 1942, Apple II, C64, CWORD, Excitebike, Frotz, LOOM,
     MIDIRack, ModPlug, Paint, PiXEL, RunCPM, Tank, Tracker, WEAVE. Some are
     only unaudited rather than unclean - the census (item 87) cleared the
     image and not every claim - so each is read before it is changed;
   - Audio, Tracker and MIDIRack's speaker path is item 5, not this one.
9. Compaction above 1MB, every program and claim high (answer 12) - after 8,
   since a program that is not clean breaks when its claim is a selector.
10. The Video Player's native protected-mode path, keeping its probe (12) -
    BUILT, 14.16.
11. kern_mega's 1.2MB system disk (answer 19).
12. LAST: the tables in conventional memory for a machine with no extended
    memory (answer 16).

### 14.3 Item 1 as built: the Video Player on kern_mega (2026-10-19)

**It was never LOADALL that crashed it.** The owner's report was right that
it crashed and the cause found on the mr286 (`tools/os88box.py`, the fault
log's new `OS88WHY` line) was a different one: `#GP 1528` at `vp_khdr`'s
`mov ds, dx`, 86Box's reason `loadseg(): Normal segment RPL > DPL`. A #GP's
error code masks the selector's low two bits, so DX was really 1529h-152Bh:
the player normalises a read's DX:SI to the nearest PARAGRAPH, which leaves
the segment off the 8-paragraph grid - the defect Frotz and Tracker had
(10.1 item 18). Fourteen normalisations now move whole 128-byte GRANULES
(offset 0..127, 8 paragraphs a step), which real mode reads as the same
bytes: +29 bytes of image, no measurable cost on kern_big. The LOADALL and
loaded-base arms are ALSO switched off under `CPU_F_PM` (+5 bytes), since
they cannot work there either: `[vp_xchk]` reads "in place failed" from the
start and the pool is copied with `OSAPI_XMEM_COPY`.

**Measured on the mr286 profile**: DEMO.V88 opens, draws its first frame and
PLAYS - the bar moves and the picture changes - with no fault the kernel did
not complete. **What it costs there is item 10's work**: a play takes ~5,500
`#GP`s that `mega_gpw` completes, every one a write through CS while DS is a
record's - `vp_lrget` (5 a call, 858 calls), `vp_rbnd`, and the decoder's
per-list map and its patched sites in `vdec.inc` (220 each). The player
works at those; it is not fast at them, and with no free segment register on
an 8086 the cure is to keep that state in registers or on the stack, which is
a decoder rework and belongs with the native protected-mode path.

### 14.4 Item 2 as built: the Task Manager's RAM, both kernels (2026-10-19)

SPEC.md 28.4.8 is the contract. What changed, against answer 10:

- **`IVT+Pad` is `IVT+BIOS`**, and it carries the BIOS's extended data area
  when the BIOS **states** one: 40:0Eh must be exactly `int 12h`'s top and the
  area's first byte its size, inside 640K. Both the row and the total take it,
  so base memory still adds up. Nothing is guessed: a BIOS that does not
  describe its area gets 0.
- **System includes what the kernel holds above 1MB**, on both kernels, from
  `OSAPI_XMEM_WALK`: the KB under the pool's base (kern_mega's tables and
  `.cold`; kern_big's HMA) and every block owned C0h and up. The memory view
  gets an `Above 1MB` row under System so its rows still sum.
- **RAM counts the BIOS's extended memory on kern_big too**, in MB. HEAP
  counts it only on kern_mega, where it is a program's to run in; on kern_big
  it is a store, and the `XMS` line is the pool.
- **A program's MEM column on the PROCESS page** now adds its blocks above 1MB
  (`tm_slotxkb`). Only the memory view did before, so a high-claiming program
  read smaller on the front page than on the second.
- **`OSAPI_XMEM_WALK` answers on kern_big with a store** - an ABI addition,
  a refusal that became an answer (abilock updated without a bump). The body
  is `XMEM.DRV`'s (`XMV_WALK`, overlay ABI 1 -> 2) and the kernel's half is
  24 bytes of `.text` and 2 of `.bss`.

**Measured on 86Box**: the mr286 (4MB, kern_mega) reads `RAM 0.3/3.6M`,
`HEAP 0.0/3.2M`, System 343K = Code+data 68 + Stacks 3 + Above 1MB 267 +
FAT snap 5; an AMI 286 with 2MB on kern_big reads `RAM 0.1/1.6M`, System
122K of which 64K is the HMA, `XMS 0/960K`. The rows add to RAM used on both.

**Decisions to look back over:**

1. **The AMI 286 at 1MB reports NO extended memory** (its setup reads
   `Ext. memory size: 0 KB`): the 384K over 640K is shadow on that board and
   the BIOS never offers it. So "a 1MB machine" shows 640K there, which is
   what the machine says it has. A board that does report 384K shows
   `RAM .../1.0M`.
2. **MB figures round DOWN to a tenth**, so `HEAP 0.0/3.2M` is 12K claimed.
   It is the RAM pair's existing format; a KB figure would not fit the line
   beside a total past 999K.
3. **The `Above 1MB` row costs the memory view's last instance row on a full
   slot table**: one more row was cheaper than re-deriving the window's
   height, and the clip is the one `tm_mrow_open` already does.
4. **Answer 10's read-only map of 640K-1MB is a list, not a second bar**
   (SPEC.md 28.4.9): Video A000 128K, every option ROM with a 55AAh
   signature at its segment and length, BIOS F000 64K, after the programs.
   A list says the address and the size in the window's own columns; a bar
   384K wide beside a 640K one would have needed a scale of its own.

### 14.5 Item 3 as built: the hibernate image's sum, both kernels (2026-10-19)

SPEC.md 87.4.1 is the contract. **The sum covers what the PROGRAMS hold, not
the whole of conventional memory**, and that is a finding rather than a
corner cut: `hbm_wrimg` writes the image LIVE through the file layer, so the
FAT and directory buffers it updates, the stack it runs on, the BDA, the tick
counters and the pointer's save-under are not, at any one instant, the bytes
the disk got. A whole-memory sum, taken before or after, would refuse good
images. A package's memory is what nothing touches between the sum and the
transfer (`[sch_lock]` stops its workers and the UI task is the writer).

**Checked by the RESTORED kernel at `hbm_wake`, not by the stub**: the
records, the routine and the figure are all the image's own, so nothing is
staged and neither the stub nor `kern_dos`'s resume changes. A mismatch
discards the session (pointer and image deleted, a sentence, a key, an
ordinary boot). The code is in `HIBER.DRV`, so it costs no resident byte.

**Gated by `hibsumok` and `hibsumbad`** (MartyPC, an XT with a hard disk):
Mines open across the hibernate, the machine powered off between the write
and the resume, and in the second row 1KB of Mines's region flipped inside
HIBERNAT.IMG on the host. **The broken-on-purpose row was red on its first
run for a real reason**: `hbm_psum` read `mem_tab` through DS, and `mem_tab`
is LOW_SEG's (`.lowbss`), so the sum covered nothing on BOTH sides, matched,
and the damaged session resumed with Mines's window blank. It reads through
SS now. Also green on the new kernel: `hibernate`, `hibernatem`,
`hibernatedrv`, `stikhiber`, `mouresume` and the DOS handoff's returns
(`kdhand`, `kdreturn`, `kdreturnm`, `kdreturngfx`, `kdreturncx`). **Not yet
run on kern_mega in protected mode**, where the same routine reads the
conventional records through identity selectors and skips the high ones; the
park's own Fletcher sum covers those.

**Decisions to look back over:**

1. **A mismatch DISCARDS the whole session** rather than closing only the
   damaged programs. There is no forced close in the kernel (a close runs the
   program's own code, which is the thing that is damaged), so per-program
   recovery would be a new mechanism; the discard is the safe floor.
2. **The kernel's own memory is not covered.** A damaged kernel image fails
   at once rather than quietly, so it is the programs' memory - the user's
   documents - that the sum protects.

### 14.6 Item 4 as built: a program's own int 13h into a buffer above 1MB (2026-10-19)

The file layer already bounced its own transfers (item 85) and `mega_fd13`
already DMAs straight into a high buffer for `dsk_xfer`'s calls. What was
left was a program that issues `int 13h` ITSELF with ES a selector above
1MB: item 33's fence answered it 09h. `mega_hibnc` (`.cold`) answers it
instead, a run at a time through the read-ahead's landing (nine page-safe
sectors) or `dsk_secbuf` when the landing is shed, each run a NESTED
`int 13h` that goes native or is reflected like any other, and copies the
run up or down. A request stays inside one track, so a run advances CL's
sector number and nothing else. IF stays 0 between runs, so no task can take
the landing between the copy and the transfer.

**Measured** under Bochs at 4MB: MEGAXM's new step reads drive A's track 0,
18 sectors (two runs of nine), into a window above 1MB at an odd offset,
compares sectors 1-8 and 9-16 against the same sectors read low, writes the
18 back from the window and compares again: `MEGAXM: i13 ok`, then
`MEGAXM: ok`. On the old fence that step is `no 30`.

**Decision to look back over:** it lives in `.cold` because kern_mega's
`.text` + `.bss` was 33 bytes past the one 64KB segment with it in `.text`.
That segment is now the binding quantity on kern_mega, and the next resident
mega feature will meet it.

### 14.7 Item 5 as built: the speaker in protected mode (2026-10-19)

SPEC.md 34.11.1.1 is the contract. The owner's third option, priced and
taken: the program stays high and **the door writes IRQ0's GATE**
(`OSAPI_FSX_SPK` AL = 2, kern_mega in protected mode only; AL = 0 is
refused there as before, so an older library falls back as it always did).
The door answers the chain, `KERNEL_SEG:sch_isr`, which is a code selector
in protected mode. The close and `fsx_restore` put the gate back and leave
the IVT's cell, which is the BIOS's for a reflection, alone.

**The ISR had to change as well as the door**: a high package's CS is a
read-only code alias, so `os88spk.inc`'s state writes through CS would have
trapped once a sample. The ISR family is now one macro assembled twice:
the real-mode copy is unchanged, and the protected-mode copy writes its
state through ES, loaded with the package's own data selector. 436 bytes
of each of Audio, Tracker, MIDIRack and the Video Player, and no cycle on
kern_big.

A reflected BIOS call puts channel 0 back to the ROM's rate while the door
is open, and the sample's count after, because in real mode IRQ0 is the
BIOS's handler and would count a tick per sample.

**Measured** on the mr286 profile in 86Box: SPKBENCH's speaker rows, which
were skipped on kern_mega before, play at 4,800, 5,512 and 8,000 Hz. The ISR
takes 66, 75 and 108 per mille of the machine (86Box is not cycle-accurate,
so the figures are indicative). The fault log shows **no trap in the ISR**.
kern_big's speaker rows are green: `apspk`, `apspkcovox`, `midirackspk`,
`spkbench`, `trkspk`, `trkspkcovox`, `vidspk`, `vidspk2` (two pulses a
sample), `vidspkcovox`, `spkfx`.

**What it found, for item 8**: `apps/os88spkfx.inc`, the speaker SHAPER that
Audio and SPKBENCH produce samples with, writes eight words of state through
CS for every 256-sample span, so a high Audio pays eight traps per span on
kern_mega (4,112 per site in SPKBENCH's run). It works; it is slow, and it is
the same fix as the ISR's.

### 14.8 Item 7 as built: claims of a megabyte and more (2026-10-19)

SPEC.md 50.3.5 is the contract: `OSAPI_MEM_HUGE` at 0x04B1 (0x04AB until the
elendilon merge renumbered it, item 72), appended to the
table, so an ADDITION and no `PKG_FMT` bump (answer 7). AX = KB, DX = the first
segment or selector, CX = the step: 1000h conventional on every kernel, 8 for
a run above 1MB. On kern_mega it is ONE pool block under consecutive LDT
selectors, the last selector's limit the claim's own end. `mx_unsel` frees
the whole run with the block, by the rule that a claim's block over 64KB has
a selector per 64KB. Cost: the 6-byte cell and a 10-byte body (one of them a
parity pad that keeps `dsk_xfer` even) on kern_big and kern_small; on
kern_mega the body is `.cold` and 31 bytes of `.text` (mx_unsel's count and
three 4-byte far doors).

**Measured** under Bochs at 4MB: MEGAHI claims 200KB in four pieces, writes
and reads each back, frees it and claims it again on the same first selector
(`MEGAHI: huge 2844 step 0008 ok`), and the rest of MEGAHI passes.

**Decisions to look back over:**

1. **The run is taken for `OS88_HIGHMEM` packages only.** That header bit
   already means "my claims may be selectors", so a package that walks by
   CX but did not declare it gets a conventional claim with step 1000h,
   which is still correct; it only cannot have more than the heap holds.
   Taking the run for any caller of the cell would also have needed the
   free path to recognise a non-HIGHMEM package's high block.
2. **A huge claim does not regrow above 64KB and is not compacted.** Regrow
   would mean moving the run and re-aiming every selector. Compaction above
   1MB is item 9, and the run is what it will have to move: the selectors
   stay fixed and only their bases change.
3. **The pieces are contiguous**, because the block is. Answer 12 noted they
   need not be, which would let a claim mix conventional and extended memory
   and let compaction make 64KB holes only. Contiguous is the simple first
   version; item 9 can relax it, and nothing a program sees changes.

### 14.9 Item 6 as built: the pointer moves through a reflected BIOS call (2026-10-19)

An audit of the mouse ISRs' whole path came first: `mou_isr`, `mou_isr3`
and `mou_p2_isr`, through `mou_apply`, `cur_move`, every adapter's renderer
and the save-unders. It found the cheap version true. Every
selector-dependent load on that path is `[k_dsel]`, there is no far call
into `.cold`, and no `[cs:]` write. The real-mode IVT already names the
kernel's ISRs at 23h, 24h and 74h, because `mega_enter` and
`mega_ivt_sync` copy 08h-0Fh to 20h-27h. Only the reflection's mask kept
them from running. So:

- `[k_dsel]` is KERNEL_SEG for the reflection, set where real mode begins
  (`.rmc`, shared by the 386 path and the 286 reset path) and put back where
  protected mode resumes, with IF = 0 throughout.
- `mega_rmaskf` (`.cold`) takes the mouse's line off the mask, and only
  when its ISR can run: the mouse has settled, it is not fed by a driver
  (whose ISR may be an image above 1MB), the real-mode vector is the
  kernel's (a thief the theft repair has not synced), and the call is not
  `int 10h`, where the arrow must not draw in the middle of a mode set or a
  font load. SPEC.md 7.4's gates apply inside a disk transfer as on kern_big.
- The mask is BANKED, `[mega_rmask]`, and `mega_r286` compares the masks
  this reflection actually set. Its constant 3FB8h would have read every
  286 return with the mouse open as a BIOS that re-initialised the 8259, and
  the re-initialisation is the lost-edge, dead-mouse failure the mask exists
  to avoid.

**Measured** on the mr286 profile in 86Box with MEGAI13 (tests/megai13),
forty 18-sector `int 13h` reads back to back by a package, every one
reflected. The harness sends forty mouse packets of +5 during them. **Before:
the pointer did not move at all**, every packet lost. **After: 200 pixels**,
every packet. MEGAXM, MEGAHI and MEGAI13 pass under Bochs, whose mouse is
PS/2, so the IRQ12 arm is covered too. kern_mega's `.text` grew 18 bytes; the
segment has 2 bytes left in it (65,534 of 65,536).

**Left as found, for the owner to look back over:**

1. **A BIOS that runs `int 13h` on a stack of its own** (SeaBIOS, so QEMU and
   Bochs) puts SS somewhere else when the mouse ISR interrupts it.
   `MOUPRIV_ENTER` correctly declines to swap stacks, but `gfx_rowbase`
   and `evq_push` address LOW_SEG through SS. The same hazard exists on
   kern_big today through SPEC.md 7.4. Real IBM and AT ROMs do not switch
   stacks. The cure is a small real-mode stub that sets SS for the ISR, and
   it is not built.
2. **`[ticks]` stands still during a reflection** and is credited after it,
   so two clicks inside one long reflected call carry the same birth tick.
   Minor.
3. **kern_mega's segment is full.** `.text` + `.bss` is 2 bytes short of
   64KB, so the next resident kern_mega feature needs a size pass first or
   goes in `.cold`, as both of this round's did.

### 14.10 A size pass on kern_mega's segment (2026-10-19)

Items 4 to 7 left kern_mega's `.text` + `.bss` 2 bytes short of the one 64KB
segment, so item 9 could not start. The CLAIM FAMILY moved to `.cold`:
`mega_claimhf`, `mega_claimfreef`, `mega_claimkbf` and
`mega_claimregrowf`, with their two helpers. Every entry was already far
and reached from `.cold`, they run only in protected mode, and their
`.text` helpers are reached through four-byte far doors (one new,
`mega_xmself`). The segment went 65,534 -> **65,172 bytes**, 364 spare.
MEGAHI (claim, regrow in the pool and past 64KB, free, huge), MEGAXM,
Notepad, TexPad and Sheet pass under Bochs at 4MB.

### 14.11 Item 11 as built: kern_mega's 1.2MB system disk (2026-10-19)

`make mega` builds `build/mega120.img` beside `build/mega.img`. It has the
same files, 798 of 2,371 clusters, and its own boot sector for 15 sectors a
track (`$(MEGADIR)/boot120.bin`, the rule kern_big's 1.2MB disk uses). There
is no 360KB or 720KB kern_mega disk, by answer 19.

**Booted** on `vm/286-525` in 86Box, the only profile with 5.25" HD drives.
It is an AMI 286, given 2MB because at 1MB that board reports no extended
memory and kern_mega would stay in real mode. Result: the desktop, both
5.25" drive icons, and `[k_dsel]` = 0010h, which is protected mode.

### 14.12 Item 8, part 1: the C packages' claims high, ModPlug on the grid (2026-10-19)

**The C SDK.** Three things in it kept a C package's claims low.

- `apps/os88partsbody.inc`'s two part claims (`op_claim`, `op_fetch`)
  address parts by paragraph arithmetic on the carve (`add ax, [op_base]`).
  They now claim through the DMA doors with CX = 0, which stay conventional
  on kern_mega and are an ordinary claim everywhere else. The same goes for
  the overlay claim in `apps/cc/crt0.asm`. A part is the package's own code
  and data, so "high" for it is "re-home high" (below), not a selector.
- **`os88_file_read_segoff` / `os88_file_write_segoff`** (new,
  `apps/cc/os88.h`). These are the seg:off form of the `_seg` pair. A
  package that wants a file at a place INSIDE a claim was writing
  `seg + (off >> 4)`, which is arithmetic on a selector on kern_mega. Now
  it names the claim and the offset. The rule is the same: the offset keeps
  the 512-byte alignment the `_seg` calls ask for.
- **`os88_mem_huge` / `os88_mem_huge_step`** (new): item 7's cell for C.
  The step is what a package adds to a selector to reach the next 64KB,
  and 1000h (a paragraph step) on every other kernel.

Each new thunk is gated like the rest (`CC_U__*`), so a package that does
not call it carries none of it.

**The packages.**

- **LOOM**: a source slot was `lm_srcseg + slot * 384` paragraphs. It is
  now an offset (`lm_soff`), read and written with the `_segoff` pair.
- **RunCPM**: its three reads into the Z80 claim (AUTOEXEC.TXT and the two
  transient loads) were `rc_zseg + (off >> 4)`. They now use
  `_segoff` at `rc_zseg:off`. The host harness `rcuitest.c` models the new
  call as the paragraph form.
- **Apple II, C64, CWORD and WEAVE** needed nothing beyond the SDK.
- All six now declare `OS88_HIGHMEM`. **PaccMan** claims nothing it could
  move, so it is unchanged.

**Verified.**

- `make` and the C toolchain build all six.
- A Bochs sweep at 4MB opens all six on kern_mega.
- RunCPM was run with a real `A/0` and an AUTOEXEC.TXT that runs INFO. The
  CCP took the poke and INFO.COM loaded and ran on every warm boot, which
  is RunCPM's own behaviour: both `_segoff` reads, into a 64KB claim that
  is a selector there.
- LOOM opened FORM.WML on kern_mega. One character was typed and File ▸
  Save answered "Saved FORM.WML, 919 bytes". The edited byte is on the
  disk image.
- `tools/os88bochs.py` gained `--put FOLDER:path`, and its third click now
  skips the folders `--put` makes in RUN/.

**ModPlug was faulting on kern_mega whatever HIGHMEM said.** Its patterns
lived at blob + 67 + 64p paragraphs and its samples at blob + (start >> 4),
which are both off kern_mega's 8-paragraph grid of conventional
descriptors. This is item 18's Tracker defect again in a package that was
never given Tracker's fix. It now has Tracker's layout:

- patterns at blob + 64 + 64p, offset 60;
- samples at blob + 8·(start >> 7), offset start & 127.

Every pair names the same linear address it did, so real mode reads the
same bytes. The mixer's bound moves from ≤ 60,015 to ≤ 60,127, against the
64,015 its own comment allows. No row in the suite plays a module through
ModPlug, so this is that arithmetic, not a measurement.

**Decisions for the owner to look back over.**

1. Parts are kept conventional rather than given selectors. A C package's
   parts are its own code segments, and lifting them is the re-home-high
   step below, not a claim flag.
2. The LOOM and RunCPM changes are generic: the same source on every
   kernel, a few bytes each. They are well inside answer 8's 512-byte rule.

**What the audits found for the rest of item 8.** None of these are built
yet, and every byte count is an estimate from reading the code.

- **Two more existing kern_mega faults, conventional or not:** MIDIRack's
  wavetable samples (`mwt_dseg = bseg + doff >> 4`, then `+ MRS_PARA`), and
  Frotz's picture band (`zp_bseg = zp_seg + offset >> 4`). Both are
  paragraph steps off the grid.
- **A "flat arm" for claims of 64KB or less** in Frotz, Tracker, ModPlug
  and MIDIRack. The granule trick `base + 8·(A >> 7)` is right for an
  identity selector and wrong for an LDT one. A claim of 64KB or less that
  came back a selector (`test dl, 4`) is addressed as segment = claim,
  offset = the absolute address. Claims over 64KB stay conventional by the
  contract, so the granule paths stay right for them. About 60-80 bytes a
  package; kern_big never takes the arm.
- **1942, Excitebike, Tank and Paint**: segment arithmetic on their own
  claims, plus `OSAPI_MEM_CODESEL` where compiled code is far-called out
  of a claim. PiXEL stays as it is.
- **`apps/os88spkfx.inc`**: about eight CS writes a span. That is a speed
  item rather than a placement one, and it is fixed generically by
  assembling the writers twice, the way `OS88SPK_ISRS` is.
- **The seven kept low.** All five re-homers' loaders are clean. A high
  loader buys nothing, though, because the PROGRAM runs in the
  conventional carve, and the loader step that frees it (8a) LEAKS a high
  loader's pool pair: `mem_free_x` is handed a selector, finds no record
  and the carry is ignored. The prize is a kernel **re-home high** step
  (~50-70 bytes of `.cold`), and its open question is how much of the
  carve to lift, since Word and Scribe address part 1 inside their own CS.
  Redline (its E820 buffer, `int 15h` writing to a high DS) and the Video
  Player (`xg_gap` measuring from DS) are each a few bytes from
  `OS88_HIGH`.

### 14.13 Item 8, part 2: Frotz, Tracker, ModPlug and MIDIRack high, with their claims (2026-10-19)

All four now declare `OS88_HIGHMEM`. The rule that makes it safe, written
once per package:

- **A claim over 64KB stays conventional by the contract**, so those keep
  their 128-byte granules, `base + 8·(A >> 7)`.
- **A claim of 64KB or less may come back a selector** (bit 2 of DX, the
  LDT; a conventional base is a multiple of 32 paragraphs, so the bit is
  clear there). That one is addressed **flat**: segment = the claim,
  offset = the absolute address. The granule trick is only right for an
  identity selector; added to an LDT selector it lands on another entry.
- **A selector faults past its limit where a segment reads garbage.** So
  each package makes sure every offset its inner loop can form is inside the
  claim, which is the one place the four differ.

| package | what was flat-armed | the limit rule | bytes |
|---|---|---|---|
| Frotz | `zm_map`'s high arm, `zm_addr`, `zm_norm`, `@verify`'s walk | a story claim that comes back a selector under 64KB is freed and claimed again at 64KB: a story may name any 16-bit address | +93 |
| Tracker | `mp_patseg` (one helper for the three pattern sites) and each sample's base | `trk_claimsel`: a module of 62KB or less gets a whole 64KB selector; one of 63-64KB is claimed at 65KB, which is conventional (the mixer assumes a limit of 64,015 or less); the trim is skipped on a selector | +78 |
| ModPlug | the same, `mpm_patseg` and `mpp_claimsel` | the same | +84 |
| MIDIRack | `mwt_place`: each voice's segment and start, from the bank's 32-bit data offset; the bank's 32KB chunks step by offset | `mwt_lim`: no voice's end past the claim on a selector | +104 |

Every byte count is the image against the commit before. All are generic
code, under answer 8's 512 bytes, and on kern_big a flag test per seek,
row or note-on.

**Three faults that were there whatever HIGHMEM said, now fixed:**

1. **Frotz's picture band** was `zp_seg + offset >> 4`, a paragraph step
   off the grid. It is now `zp_place`, the same two arms.
2. **MIDIRack's wavetable** had samples at `bseg + doff >> 4 + para`, the
   same defect. Reproduced first: the commit before this one, given the SB
   wavetable on kern_mega, stops with `kern_mega FAULT 0D err 19E4`.
3. **Frotz never found a story's pictures when it was opened from the
   dialog, on EITHER kernel.** `zi_load` copied the story's name with
   `rep movsb` without setting ES, and inside a callback ES is the kernel's
   (`KERNEL_SEG`, or 0010h on kern_mega). So `zi_story` stayed empty, no
   `.PIX` was looked for, and 13 bytes of KERNEL data were overwritten on
   every open. `make zgfx` never saw it because its harness opens the story
   another way. Found by E9 tracing on kern_mega. It is now
   `push ds / pop es`.

**A fourth, in MIDIRack, also on every kernel:** `mrb_start` built the
stream's open flags in BL and THEN called `OSAPI_SND_CAPS`, which returns BL
as an output. The flags reached the driver as 81h, with no EXT and no ring
size, so the external ring of SPEC.md 34.5.3 has never been used and every
card play took the grant ring. The flags now go into BL after the call
(0 bytes).

**Verified under kern_mega:**

- **Bochs at 4MB:**
  - Tracker plays a generated 30KB module through a selector. The SB
    capture has exactly the 7.7 s of signal its one note pattern holds.
  - Tracker plays the 116KB BEVERLY.MOD through granules.
  - ModPlug plays both, opened from its own dialog.
  - Frotz draws `zpictest.z6`'s three pictures at the sizes
    `zpictest.expect` names.
- **86Box (the owner's mr286 profile, 4MB, SB16):** MIDIRack plays a song
  through the SB wavetable with the synthetic 6,872-byte bank, so the bank
  is a selector. Bochs could not show this one: its SB16 underruns every
  pass and ends the song, on the old code as on the new.
- **kern_big:** `midirackwt` on MartyPC and `make zgfxpic` both pass.

**What is left of item 8** (§14.12's audit list):

- the graphics packages: 1942, Excitebike, Tank and Paint;
- `apps/os88spkfx.inc` and MIDIRack's patched `adc` immediate. Both are
  CS writes in a hot loop: traps on kern_mega, a speed item rather than a
  placement one. 86Box's fault log shows the `adc` trap firing per span;
- the re-homers and the "re-home high" kernel step;
- Redline's E820 buffer and the Video Player's `xg_gap`.

**Decisions for the owner to look back over.**

1. **A small claim that comes back a selector is RE-CLAIMED at 64KB**,
   rather than every inner loop bound-checked against the selector's limit.
   It costs up to 64KB of extended memory per open document and nothing in
   the loop. On kern_big it never happens.
2. **A module of 63-64KB is claimed at 65KB on kern_mega**, so it is
   conventional and takes the granules. The mixer's own bounds are written
   for a limit of 64,015 or less, and changing them is a hot-loop change
   for two KB of module size.

### 14.14 Item 8, part 3: the graphics packages, Redline, the Video Player, and two kernel holes (2026-10-19)

**Who now says what:**

- `OS88_HIGH | OS88_HIGHMEM`: 1942, Excitebike, Tank, Paint and Redline.
- `OS88_HIGH` alone: the Video Player. Its ring is paragraph arithmetic
  over 34 sites, and lifting it would need OSAPI_MEM_HUGE's step.

The four graphics packages were each done by an agent in a worktree and
merged here. Their records follow, with Paint's in full.

**Two kernel holes, found by Redline running above 1MB:**

- **`mega_svc`'s return to protected mode reloaded DS but not ES.** ES
  still held the segment the BIOS returned, and the `push es / pop es`
  around the tick read then loaded it as a selector. For a caller whose
  ES was above 1MB that is FFFFh (`mega_s2seg` gives the BIOS FFFFh for a
  high selector), so it faulted. ES now gets the kernel's data selector
  with DS. The caller's own ES comes back from the frame at `.out`, as it
  always did. This costs 2 bytes of `.text`.
- **`mega_gpfix`'s `.stale` arm then faulted inside the handler.** It
  indexed the LDT with what was a GDT selector and ran off the alias. It
  now refuses anything that is not an LDT selector inside the LDT.
- **Re-home step 8a** handed `mem_free_x` a high loader's selector,
  ignored the carry, and leaked the pool block and both LDT entries on every
  launch. It now frees the pair as `ld_unreserve` does. No shipped loader
  says `OS88_HIGH` yet, so this was latent.

**Redline:**

- The E820 entry is on the task stack. Placed in DS, it read back as no
  memory at all, through FFFF:DI.
- The "RAM twin" reference times LOW_SEG instead of its own DS.
- Measured under Bochs at 4MB: the whole benchmark runs, E820 reads Usable
  3,708KB, and Free conventional goes 499KB -> 559KB because Redline
  itself has left it. The commit before this one, running low, also ran
  clean. Redline running high faulted until the kernel fix above.
- -17 bytes.

**Video Player:**

- `xg_gap` (`apps/os88xgap.inc`) timed its copies from DS:0 as the
  conventional end. It now takes an 8KB scratch claim at the DMA door,
  which is conventional on every kernel.
- `vp_erate` times SS instead of DS.
- The Live demo plays on kern_mega with the package above 1MB.

**1942** (+97 bytes):

- The splash's band arithmetic is now offsets. A selector canvas
  decompresses each band through a 3KB scratch claim, because
  `OSAPI_DECOMP` wants ES:0.
- The compiled CGA sprites are far-called through `OSAPI_MEM_CODESEL`.
- `n_pushall` no longer stores its return through CS, which was item 56's
  trap per call.
- Under Bochs: the splash draws, a VGA game plays, and Esc returns.

**Excitebike** (+2 bytes):

- The art-part claim and the compiled-pose claim go through the DMA door
  with CX = 0. Both are paragraph arithmetic, and a HIGHMEM claim is a
  data-only selector that `OSAPI_MEM_CODESEL` refuses.
- The poses' code selector is set once, at load.
- Its other claims may go high.
- Under Bochs: the title and a race with the riders drawing.

**Tank** (+26 / +28 small arm):

- The HUD template was `shadow + 3E8h` paragraphs in one claim. On a
  selector it becomes a claim of its own, and the shadow claim stays 32KB
  because the device-row table sits at a constant offset in its tail.
- Under Bochs: it plays in Mode X, which takes no claim.
- On 86Box's AMI 286 with a CGA card and 2MB: it plays on the CGA shadow
  path, with the HUD panel drawn from the template, and nothing faults
  beyond the 286's own reflection resets. 832KB of the pool was free, so
  the 32KB and 16KB claims should have come from it, but their selectors
  were NOT read back.

**Decisions for the owner to look back over:**

1. **Re-home HIGH is deferred, not refused.** The five re-homers' loaders
   stay low, and so do their programs. A program's image plus bss is
   51-61KB (Skies 61,409; Word 59,392; Scribe 51,712; Pixelstein's game
   58,263), and the carve it runs in is bigger. Lifting a whole carve under
   64KB therefore almost never applies. Lifting image plus bss alone leaves
   the rest of the carve conventional at a segment the program is not
   told, which is an ABI addition, and Word and Scribe reach part 1 through
   their own CS. The gain is at most 64KB a program, for five programs that
   are not background applications. What would make it worth doing is a
   carve layout that puts the program last.
2. **Tank on kern_mega holds 48KB above 1MB a game, of which about 16KB
   is unused.** The shadow claim stays the size kern_big's blit needs.

**Not yet seen on the glass:**

- Paint's canvas resize across 64KB. kern_big's `paintmove` and
  `paintshrink` cover its real-mode arm.
- 1942's CGA fullscreen and its cartridge build.

#### Paint

Paint declares `OS88_HIGH | OS88_HIGHMEM` now. 14.13's rule, applied to the
one package whose canvas is not ONE claim walked one way but five claims
and two layouts:

- **The row table is decided by the LAYOUT, not by the claim.** A canvas
  whose layout fits one segment (`[pt_cvparas]` <= 1000h) is laid out
  **flat**: every `pt_rowseg[y]` is `[pt_base]` and `pt_rowoff[y]` the
  whole offset. A bigger one keeps the 128-byte granules, and its claim is
  over 64KB and so conventional. Deciding by the layout is what keeps the
  undo image to one table: flat, `rowseg + [pt_undelta]` is exactly
  `[pt_unseg]` whichever of the two claims is a selector; granular, the undo
  claim is the canvas claim's size and so conventional too. Deciding by the
  claim would have broken the one mixed case the pool can produce - a
  conventional canvas of 64KB or less (the pool was full when it was
  claimed, or a regrow moved it) with a selector for its undo image.
- **`pt_orowset` and `pt_mstep`** (the resize's copy-back) answer a
  selector flat and everything else on granules. **Both were one PARAGRAPH**
  before this - item 59's defect, missed because only `pt_srowset` faulted
  on the census disk - so a canvas resize could fault on kern_mega whatever
  HIGHMEM said. `pt_cvmove` puts the destination pair onto granules once,
  the flat layout's offsets being too large for `pt_mstep`'s signed step.
- **`pt_srowset`** (a staged BMP's rows) addresses a selector staging claim
  flat.
- **Limits.** The canvas and undo claims end at least two bytes past the
  pixels (the header is 2 mod 4 and the stride 0 mod 4), so `pt_cb_grab`'s
  `[es:si+1]` read stays inside. `pt_bmp_pal` read the palette at
  `14 + biSize` with nothing checking it against the file, and now stops at
  the bytes read; `pt_stagefit` keeps one byte past the file, which
  `pt_gbits`' word-and-a-byte read can touch, and no longer regrows UP when
  a file filled the claim. The GIF writer was already capped at its claim,
  the clipboard and the fill stack index inside theirs, the LZW tables are
  16KB exactly by assertion.
- **A fifth, on every kernel:** `pt_blit_1`'s band height was `65520 /
  stride`, written for 0..15-byte row offsets; with 128-byte granules a band
  of a canvas over 64KB at the widest strides could read up to 111 bytes
  past its segment. It is `65408 / stride`.

+112 bytes of `paint.bin` (26,969 -> 27,081), +115 on the small arm (17,215
-> 17,330); no kernel byte. On kern_big a canvas of 64KB or less is now
flat, which is the same bytes through the same instructions; the costs are
a test per row of a BMP decode, two per carried row of a resize, and one per
palette entry of a load - nothing per pixel. The selector arms are never
taken there.

### 14.15 Item 9 as built: the pool compacted above 1MB (2026-10-19)

**When it runs.** `mx_alloc` compacts once on any claim that finds no run
of the size it wants, and then tries again. That covers a package region
(80h|slot), a program's claim (0A0h|slot), a driver's claim (0C0h|row)
and a huge claim's single block. The kernel's own blocks (MX_KOWN) come
from the top and never need it. The claim side is untouched, because
every door already goes through `mx_alloc`.

**What it does** (`mx_compactf` / `mx_cpmove`, kern_mega `.cold`).

- The blocks are walked in ascending order of where they are. A cursor
  follows them:
  - a **pinned** block raises the cursor past itself;
  - a **movable** one slides down to the cursor, which is always free
    space, every block below it having been placed already.
- Each move copies the block down 32KB at a time. A forward copy is safe,
  because the destination is lower.
- It then **rebases every present LDT descriptor whose base lies inside
  the block**. That one scan finds a pair's two halves, a claim's
  selector, a regrow's scratch window and a huge claim's run, without
  knowing which is which.
- Each block's copy and rebase run with interrupts off, so no ISR sees half
  a move. That is up to 64KB at a time, about 10 ms on a 12MHz 286.

**What moves:**

| Moves | Stays |
|---|---|
| package regions (80h\|slot) | the kernel's own blocks (MX_KOWN), which are the system at the top |
| programs' claims (0A0h\|slot) | `OSAPI_XMEM_ALLOC`'s blocks (owner = a slot): the package holds the LINEAR address, and `os88ub.inc`/`os88la.inc` read it in place, which is what answer 12 said pins the pool |
| drivers' claims (0C0h\|row) | a huge claim (over 64KB): moving one with interrupts off for that long is not worth it until something needs it |

**Why no relocation proc is owed:**

- The selector a package holds never changes; only its descriptor's base
  does.
- A segment register picks the new base up at its next load. Every holder
  outside the call is a PUSHED register, which reloads on its pop: a
  suspended task's frame, a cell's `push ds`, an interrupted ISR's
  registers, a far return address.
- Inside the call the compactor reloads ES on its way out. DS is the
  kernel's and CS the kernel's.

`apps/os88api.inc`'s `OS88_HIGHMEM` note says so: "a pool claim MAY move…
but its SELECTOR never changes".

**Cost:** about 360 bytes of `.cold`, which is above 1MB on kern_mega, and
30 bytes of `.text`: the retry, one far door and the flag. kern_big is
byte-identical.

**Verified.** `tests/megacp` (MEGACP), under Bochs at 2MB:

1. It fills the pool with 60KB claims, then the tail with smaller ones,
   until 0 KB is free.
2. It frees every other 60KB claim, leaving 360KB in 60KB holes.
3. It claims 64KB. The compactor moves eight blocks down, from KB 121,
   241, 361, … to 61, 121, 181, … The claim comes back as selector 284Ch.
4. Every surviving block's stamps (offsets 0, 30,000 and the last word)
   read back intact through its unchanged selector, and the new block takes
   writes at both ends.
5. MEGARUN carries on to `done`, and no fault is reported.

**Still open:**

- A region moving while its OWN program is the caller is covered by the
  argument above (the cell's `retf` reloads CS), but MEGACP's region sat
  below everything it claimed and did not move. A test that starts a
  second high package first would put it in the path.
- Nothing yet gives a program the LINEAR address of an `OS88_HIGHMEM`
  claim. If a cell ever does, that claim must be pinned the way
  `OSAPI_XMEM_ALLOC`'s are.

**Decisions for the owner to look back over:**

1. **Compaction runs inside the claim, interrupts off a block at a time.**
   That is the conventional compactor's place (`mem_claim`'s refusal path),
   not a background pass. A serial mouse can drop bytes during a long one:
   at 1,200 baud a byte is 8.3 ms, so one 64KB move on a slow 286 is about
   one byte.
2. **Drivers' own IMAGES stay pinned** (MX_KOWN), and so do huge claims.
   Both could move by the same rebase, but nothing needs them to yet.

### 14.16 Item 10 as built: the Video Player's native protected-mode path (2026-10-19)

Two parts, in the order 14.2 asked for them. SPEC.md 98.3.18.16 is the
contract for the second and carries the first's summary.

**Part 1: no write through CS on a path that runs per frame or per read.**
14.3 left a play paying ~5,500 #GPs that `mega_gpw` completed. Measured
again here under Bochs with `make megatrap` and `tools/megatraps.py`, the
counts taken between the Play click and the end of the play:

| play (Bochs, 4MB, SB16) | before | after |
|---|---|---|
| `apps/video/demo/cga/11-LIVE.V88`, Live on the desktop, 300 frames | **7,048** | **0** |
| a 640x200 LIN80 clip (`tests/vidxip.py`'s), in the window, 182 frames | **2,002** | **0** |
| a VGA4 SUB2 write-mode-3 clip, window, full screen and a seek's toast | crashed (below) | **0** |

(The Live play's four other lines are SOUND.DRV's `null0` at start, not the
player's.) What they were, and what replaced each:

- **`vdec.inc`'s list map** - `[cs:vd_map]` stored and shifted at every
  list's head: eleven a frame on every play. The map is DX through the six
  poke lists, which never touch DX, and a word on the stack through the
  four span lists, which count rounds in DX. This is the decoder's own inner
  chain, so it was measured on kern_big too: MartyPC's 5150 running
  `tests/vidbench` against a synthetic `VIDBENCH.DAT` (`os88vid.py synthxdv`
  + `benchdat --synth`), base against new, `nat ram` cycles a frame:
  empty 1,440 -> 1,273, P1 x400 18,066 -> 17,892, SL16 x150 44,592 ->
  44,404, RUN40 x60 24,682 -> 24,506 - **every one of the 16 frames
  ~150-180 cycles FASTER**, the pictures checked equal on both paths. A
  `shr dx, 1` is 2 bytes where the memory shift was 5. The VD_PAR pads were
  re-derived so every `.seg` and round head keeps the parity it had, with
  one exception noted in the source: `vd_n_run`'s gate reaches
  `vd_n_slicel` at exactly 127 bytes, so no pad goes in front of the long
  lists, whose heads were never aligned to begin with.
- **`vp_rbnd`** (a resident play's load-time check, six a record): the map
  in DX, the bound read from CS where it is compared.
- **`vp_lrget`** (a Live frame's blit runs, five a call): DS is ours and the
  record is read through ES (`es lodsb`), so the runs are stored with no
  prefix at all; `vp_decrec` hands it the record's segment it pushed.
- **`vp_khdr`** (a key in parts): likewise, the read through ES.
- **`vd_walk` and the text box's clip** (`vosd.inc`): their walk state, and
  `vd_walk`'s routine and colour (which were `vw_fn` and `vp_m3c` at CS), are
  BP frames on the stack, the origin the frame's first word. +14 bytes of
  stack at the deepest; the hook runs on the UI task's stack in a bracket.
- **Four bytes a sub-record** (`vc_mask`, `vp_m3on`) go through `VP_OWNB`, an
  ES load of `[vp_self]` - our own segment, kept by the region's relocation
  proc (`vp_reloc`, which was `vp_noreloc`'s bare `ret`).

The LOADALL and loaded-base machinery (`vp_xbeg`, `vp_xld`, `vd_yield`,
`vp_xmk`'s handle table) still writes through CS - it is never reached
under `CPU_F_PM`.

**Two crashes found on the way, both on kern_mega only:**

- `vp_zero` faulted at a VGA4 RAM image's plane 1: `[vp_plsp]` is the plane
  spacing in paragraphs, `h x 80 / 16` = 500 for a 160x100 canvas, and a
  segment off the 8-paragraph grid is not a selector. Rounded up to 8 under
  `CPU_F_PM` alone, so a real-mode image is the size it was.
- `HDD.DRV`'s `HDV_ARM` ran its A20 probe (`mov ds, FFFFh`) under protected
  mode at the player's first fill of a streamed file: a #GP the kernel could
  not complete, `kern_mega FAULT` in the driver. It refuses under `CPU_F_PM`
  now (AX = 1, "not this machine", which the player banks as for good): the
  read straight into XMS is a loaded-base trick with no protected-mode
  meaning. +6 bytes of image inside its 4,096.

**Part 2: the hold and the bank read through selectors.** The owner's
answer was a >64KB claim read directly, and `OSAPI_MEM_HUGE` was the
suggested primitive. **It does not fit the reader**, and the reason is the
whole design: its run is a window every 64KB, so a super-packet or a record
that straddles a 64KB boundary of the store - which a file held at its own
offsets does wherever it likes - is cut in two, and the decoder has no way
to cross a segment mid-record. `OSAPI_XMEM_SEL`'s one window per block can
be aimed anywhere but only by the UI task, under the hook's feet. What a
reader of records of at most 32KB needs is a window every **32KB**, each
64KB long: any 32KB of the store is then wholly inside the window of
(offset >> 15), at (offset & 7FFFh). That is **`OSAPI_XMEM_RUN` (0x04B7)**,
appended at the table's end - no `PKG_FMT` bump - over the XMEM block the
player already takes, so every linear-address path it has (the fills' copies
up, the bounce, `xg_gap`, `vp_xok`'s compare, the layer's bank) is
untouched. `vp_xmk` turns the linear address into that selector; it is
below `VP_XSEL`, so every `VP_DSDX` is a plain `mov ds, dx` and `VP_DSEND`
nothing: no borrow, no interrupts off, and no yield (a selector survives
every interrupt; the yield sites stay jumps). The card says `XMS in place
(PM)` / `XMS bank in place (PM), N KB`.

Measured under Bochs: the 794KB LIN80 clip held whole at 4MB plays
**240/240 in place, 0 stalls, 0 late, 0 #GP**; at 2MB it is banked (672KB,
so the bank wraps and the mirror is read) and plays the same; each play's
last picture is identical to a `VP_NOXIP` build's copying play
(`Held whole in XMS` / `Banked in XMS`). The SUB2 clip's held play goes in
place too, with the toast drawn round in full screen.

**Sizes** (bytes; `video.bin`, the image):

| arm | before (protected-mode at bbcd7fbc) | after part 1 | after part 2 |
|---|---|---|---|
| plain | 57,783 | 57,660 | 57,840 |
| `VPDIAG=1` | 59,347 | 59,224 | - |
| `NOLIVESND=1` | 57,550 | 57,431 | - |

bss unchanged (2,484). Kernels, measured section by section against
`origin/protected-mode` with the same build number: **kern_big `.text` +6,
kern_small `.text` +6** (the cell; its body is `osapi_xmem_sel`'s refusal),
**kern_mega `.text` +34, `.cold` +273**, `.bss` +0 on all three. kern_mega's
segment binds: the first spelling was +40 of `.text` and took
`make megatrap` (MEGA_TRAPLOG) over `KERN_CODE_MAX`, so the cell's
`[mega_on]` test and `mx_unsel`'s run arithmetic live in `.cold`
(`mx_runcntf`). `.bss` now ends at FF74h: 140 bytes of the segment left.

**The probe (`xg_gap`), with numbers.** It measures a COPY between
conventional and extended memory against the board's interleave - up to
1.8x on the Victory (SPEC.md 41.14; 98.3.18.12 measured a drained 32KB
chunk 11.2 -> ~6.6 ms placed at the gap). In place, a held file makes **no
copy during a play** (25 copies of 32KB down for this 794KB clip, every
play, are gone), so the ring needs no gap slack, exactly as on the 286
(`vp_xgpad` already skips for `[vp_xip]`). A bank in place still reads
each chunk into the bounce and copies it UP - one copy a banked byte where
the copying bank made two - and that copy is the one the gap places, so it
is kept for it. The decode's reads through the selector are a sequential
stream from extended memory into the adapter, with no second RAM end to set
against the first. **The probe stays, and applies to the copies that
remain.**

**Decisions for the owner to look back over:**

1. **A new cell, not `OSAPI_MEM_HUGE`.** 64KB windows cannot serve a
   reader whose records straddle them; a 32KB-step run of 64KB windows can.
   I put it on `OSAPI_XMEM_ALLOC` blocks rather than on huge claims because
   every linear-address path in the player (fills, bounce, gap, layer bank,
   `vp_xok`) then stays as it is. The alternative - the store as a huge
   claim with overlapping windows - would also need the player to say
   `OS88_HIGHMEM`, which 14.14 found it cannot yet (34 sites of paragraph
   arithmetic on its claims).
2. **One view a block.** A block with a run refuses `OSAPI_XMEM_SEL` and
   the reverse, so `mx_unsel` knows what to free from one word (`MX_SEL`
   with bit 0 set marks a run). An XMEM block never moves, so no rebase is
   owed.
3. **The bank in place keeps its bounce.** The disk layer takes an LDT
   selector as a buffer but bounces it a sector at a time through
   `dsk_secbuf` (`dsk_runcap`'s `test al, 4`), which on a BIOS disk is a
   call a sector where the bounce is a call a run. Reading straight into
   the run is the next step and wants a 286 to price it.
4. **The speaker's clock is LIFTED in place under `CPU_F_PM`** (14.16.1),
   for the hold and for the bank. Both refusals were about interrupts held
   off - a LOADALL or loaded-base borrow for the whole decode (98.3.18.14),
   and a BIOS block move for every copy (98.3.18.5) - and neither happens
   here: a selector is a `mov ds, dx`, and kern_mega's `OSAPI_XMEM_COPY` is
   a `rep movsw` between two descriptors under `[sch_lock]` alone.
5. **The shadow is LIFTED in place under `CPU_F_PM`** (14.16.1). Its
   refusal was that its decoders have no yield sites, and a selector needs
   none.
6. **The plane-spacing rounding is `CPU_F_PM`-only.** A generic rounding is
   five bytes smaller and costs every real-mode VGA4 image up to 3 x 127
   bytes; I kept kern_big's images the size they were.

**kern_big rows, once at the end** (`os88soak.py start -k ...` on the
final tree): `vidplay vidplayvga vidplayshd vidfskeysvga4m3
vidfskeysvga4pl vidfskeysmodex vidlive vidlivevga4 vidresident vidkpart
vidxms vidxip vidxipbank vidxiphd vidposter vidscreeno` - **16/16 ok**.
`vidplay`'s timing leg (all frames, no stall, no late period, ticks within
2) is the on-time check on MartyPC's 8088; `vidxip`/`vidxipbank` are the
386 in-place paths through the changed `vp_xmk`; `vidxiphd` is HDD.DRV's
arm on a real-mode 386.

**Seen on a real 286 (86Box, 2026-10-19):** the AMI NEAT 286 profile
(`vm/286`, 12.5 MHz, 4MB, no card) running `mega.img` at bbcd7fbc plus this
work, LIN80.V88 (794KB, 640x200 VGA, 24 fps, silent) off a 1.44MB B:. The
first Play, pressed before the hold had finished filling off the floppy,
copied as it should (`[vp_xfull]` was 0 when `vp_sstart` asked): `Held whole
in XMS`, Drew 240/240, stalls 54, Late 0, 224 ticks of 182. The second Play,
with the hold whole: **`XMS in place (PM)`, Drew 240/240, stalls 0, Late 0,
182 ticks of 182** - real time. Read off the machine between the two:
`[vp_pm]` 1, `[vp_xrun]` 2834h, `[vp_xchk]` 0 (the check not yet made, since
nothing had asked). No fault but `mega_strcal`'s calibration and the 286's
deliberate shutdowns into real mode.

**Not yet seen:** the mr286 profile itself; the bank in place on a pool
big enough to fill every slot before the first frame. (The speaker play is
14.16.1's.)

#### 14.16.1 The speaker and the shadow, in place under `CPU_F_PM` (2026-10-19)

Two refusals in `vp_xipq` and `vp_xbipq` now apply only where
`[vp_pm]` is 0. Every other path decides exactly what it did before: the
two tests are skipped behind one `cmp byte [vp_pm], 0`, and a real-mode
kernel never sets that byte. VIDEO.O88 57,840 -> **57,860** bytes (+20),
bss unchanged at 2,484; no kernel or driver source changed, so kern_mega's
segment is untouched.

**Why the speaker's refusal does not apply.** The speaker's clock is its
own interrupt, one a sample (98.3.15), so what it cannot have is interrupts
held off. Two things held them off:

- **A borrow** (98.3.18.11, 98.3.18.14): the decode ran inside
  `pushf / cli` for up to `VP_XYB` record bytes, because a hidden base dies
  at the first DS an ISR loads. Under `CPU_F_PM` `vp_xmk` answers a real
  selector below `VP_XSEL`, so `VP_DSDX` is a plain `mov ds, dx`,
  `VP_DSEND` is nothing, and interrupts stay as the caller had them. An ISR
  that loads DS and pops it back gets the same selector.
- **A copy** (98.3.18.5): `int 15h AH=87h` for 32 KB on a 286, the 386's
  1 KB pieces. On kern_mega `OSAPI_XMEM_COPY` is `mx_copy` ->
  `mega_lincopy`: two scratch GDT descriptors and a `rep movsw`, with
  `[sch_lock]` raised (no task switch) and IF left alone. So the bank in
  place's one copy a chunk (`vp_xbread`, bounce -> slot) stops nothing.
  A held file in place copies nothing at all during a play.

The disk is the one thing left that can still stop the speaker. A
REFLECTED `int 13h` masks every kernel IRQ and puts channel 0 back at the
ROM's rate for the call (`mega_irqrom`'s `.nospk`), so the speaker pauses
for it. kern_mega's native floppy path (KERN-MEGA-PLAN 10) waits for IRQ6
with interrupts on. That applies to every speaker play that reads the disk,
the copying ones included, and a held file in place reads none.

**Why the shadow's refusal does not apply.** The shadow decodes a record
into a RAM image (`[vp_shseg]`): a one-bit file with `vd_native`, VGA4
with `vp_decram`, C160 with `vd_c160`. The last two have no `VD_YCK`
sites, so under a borrow they would hold interrupts off for a whole record.
Under `CPU_F_PM` no site yields anyway (`vd_ypatch` is never called). All
three reach the record through the same `VP_DSDX` sites in `vp_decrec` as
a native play, read DS:SI with `lods`, and do no segment arithmetic on DS,
so a selector with SI up to 7FFFh serves them as it serves `vd_native` on
the screen.

**Measured on the 286** (86Box `vm/286`: AMI NEAT, 12.5 MHz, OTI067 VGA,
no sound card; `mega.img` of this tree on A:, a 1.44 MB B: with VIDEO.O88
and one clip). Each clip is 240 frames of `tests/vidxip.py`'s 640x200
random-patch picture at 24 fps. The speaker clips add an 11,025 Hz PCM8
sweep. The base arm is VIDEO.O88 assembled from this branch's HEAD before
the change. Play was pressed with `[vp_xfull]` 1 for a hold.

| clip, machine | arm | card's bank line | Drew | stalls | pauses | Late | ticks |
|---|---|---|---|---|---|---|---|
| SPK.V88 (906 KB, card PCM8 shaped for the speaker), 4 MB, held | base | `Held whole in XMS` | 240/240 | 0 | 0 | **477** | **375 of 181** |
| same | new | `XMS in place (PM)` | 240/240 | 0 | 0 | **0** | **182 of 181** |
| SPK.V88, 2 MB, banked (672 KB) | base | `XMS bank idle: the speaker` | 240/240 | 0 | 0 | **546** | **403 of 181** |
| same | new | `XMS bank in place (PM), 672 KB` | 240/240 | 0 | 0 | **27** | **195 of 181** |
| same, M pressed before Play (silent) | new | `XMS bank in place (PM), 672 KB` | 240/240 | 0 | - | 0 | 183 of 181 |
| SHD.V88 (814 KB, Hercules layout: the SHADOW on a VGA, `[vp_shadow]` 1), 4 MB, held | base | `Held whole in XMS` | 240/240 | 0 | - | 0 | 183 of 182 |
| same | new | `XMS in place (PM)` | 240/240 | 0 | - | 0 | 182 of 182 |

What each row says:

- **The held speaker play is real time in place and took twice as long
  without it.** Refused, a speaker play makes no XMS copy, so the floppy
  serves a file that wants 81 KB/s. The hold was full and unused, and the
  card still said `Held whole in XMS` (`vp_bkind` gives 5 only for a bank).
  That label is pre-existing; the owner may want it to say the hold was
  idle, as the bank's line does.
- **The banked speaker play went from 403 ticks to 195.** That is not real
  time, and the silent play of the same bank is (183). The difference is
  ~14 ticks and 27 late periods. This was not taken apart. The candidates
  are the speaker ISR's own CPU (11,025 interrupts a second through a
  286's protected-mode IDT) leaving the reader less time to refill a bank
  that wraps, and any reflected `int 13h` that pauses the speaker.
- **The shadow in place plays exactly as the copying one does.** Both are
  on time. What in place buys there is the drain's copies, not a speed the
  window could see. The box's picture after the play is the same pixel for
  pixel in both arms. This clip is one-bit, so it ran `vd_native` into the
  shadow; a VGA4 or C160 shadow (`vp_decram`, `vd_c160`) was not played.
- In `[vp_*]` read off memory mid-play: the held speaker play had
  `vp_xip` 1, `vp_snd` 2 (`VP_SPK`); the banked one `vp_einp` 2,
  `vp_snd` 2; the shadow one `vp_xip` 1, `vp_shadow` 1.

**Faults** (`faults --all`, against `build/megak/kernel.map`): besides
`mega_strcal`'s probes, `mega_svc.r286` and the 286's resets into real
mode, a speaker play logs **39 #GPs "Segment can't write"** in the
player's own code. They are in `os88spk_init`, `os88spk_go`,
`os88spkfx_init` and `os88spk_acct`, so they are a play's start and end,
not its samples. Both arms log the same 39, so they are not this change's.
The shadow plays log none.

**Also checked:** SPKC.V88, the same clip with its sound stored as the
speaker's COUNTS (the encoder's `spk=True`, no shaper), held at 4 MB: in
place (`vp_xip` 1, `vp_snd` 2), 240/240, stalls 0, pauses 0, Late 0, 183
ticks. Not run against the base. Its play logs 23 of the setup #GPs above
(no `os88spkfx_init`).

**Not measured:** the sound itself. 86Box's automation has no audio
capture here, so the speaker was judged by its clock: under `VP_SPK` the
frames are paced by the speaker's interrupts (98.3.15), so 240 frames in
182 ticks means its interrupts ran at the sample rate for the whole play,
and `pauses 0` means the sound never waited on the stream. Nobody has
listened to it. Not run on the mr286 profile, nor with a Covox.

**kern_big rows, once at the end** (`os88test.py soak -k ...`, on this
tree): `vidspk vidspkcounts vidbankspk vidxip vidxipsnd vidxipbank
vidplay vidplayshd vidwinshd` - **9/9 ok**. They are real-mode plays
(MartyPC's 8088, QEMU's 386), where the change decides nothing new: they
check that the speaker still keeps its refusal there (`vidbankspk` watches
the bank stay empty) and the in-place and shadow paths are as they were.

**For the owner to look back over:**

1. The bank in place under the speaker is lifted although it measured 7%
   slow. It is half the time of the refusal, which streams off the disk.
   If the owner would rather mute a banked speaker play on a 286 under PM,
   98.3.18.9's rule is where that goes.
2. `Held whole in XMS` on a speaker play that the refusal sent to the disk
   (above) - a real-mode label too, unchanged here.

### 14.17 Item 12 as built: the tables in conventional memory (2026-10-19)

Answer 16: no minimum extended memory beyond FITTING.

**When it applies.** `mega_enter` used to refuse protected mode under 192KB
of extended memory, because the GDT, LDT and IDT sit at fixed addresses
above 1MB. Now, with less than that:

- `mega_tlowf` (`.cold`, run in real mode) claims **82KB of conventional
  memory**, top-down and pinned under the new tag `MEM_K_MTBL` (FF13h).
- The tables are laid out as they would be above 1MB: the GDT at the
  claim's base, the LDT 64KB in, the IDT 16KB after that.
- Every base the switch reads is aimed at the claim: the bootstrap's
  window, GDTR, IDTR, the LDT's descriptor, the LDT's data alias (through
  the new `mega_ldtlin`) and the IDT's alias.
- The claim is asked for after the A20 test, the last refusal, so a machine
  that refuses for another reason keeps its 82KB.
- With no room even for that, the refusal now says "no 82KB for
  kern_mega's tables".

**What such a machine does not get.** None of this needed new code; each
already refuses:

- no pool (`mega_xminit`), so there are no claims above 1MB and no
  compaction;
- `.cold` stays low (`mega_coldup`);
- Hibernate greys itself (its pool test);
- the DOS box's snapshot has no pool to go to.

What remains is protected mode itself: the fault reporter, selectors with
limits, and every program clean of segment arithmetic, at 82KB less heap
than kern_big has on the same machine.

**Cost:** about 50 bytes of `.cold` and 17 of `.text`. kern_big is
byte-identical.

**Verified** on 86Box `vm/286-525`, an AMI 286 at **1MB**, whose BIOS
reports no extended memory: `mega_extkb` = 0.

- `mega120.img` boots to the desktop in protected mode (`[k_dsel]` =
  0010h).
- `mega_ldtlin` reads 9B800h, so the LDT is at linear 9B800h and the GDT
  at 8B800h, both conventional.
- The Disk window and Mines run.
- The fault log holds only `mega_strcal`'s two calibration probes and the
  286's own reflection resets, which is how a 286 leaves protected mode
  for every BIOS call.

**Decision for the owner to look back over:** the 82KB comes out of the
heap whatever the machine runs. The owner's own words were that on such a
machine kern_mega "is a worse kern_big, until programs exist that need
protected mode AND fit". So this is offered rather than chosen: the switch
is made whenever it fits, and a SYSTEM.CFG bit to decline it is not built.

### 14.18 The CS writes in shared hot paths (2026-10-19)

Under kern_mega, CS is a read-only code alias, so every `mov [cs:x], ...`
traps into `mega_gpw`. That is correct, but costs tens of microseconds a
trap. Three shared hot paths wrote through CS per span or per glyph. They
were found by audit and by 86Box's fault log, and no longer do:

- **`apps/os88spkfx.inc`, the speaker shaper** (Audio, Tracker, the Video
  Player, SPKBENCH). It wrote about 8 traps a span, 350-700 a second.
  - The level's tail and emit's control part are assembled twice. The
    protected-mode copy brackets its state writes with DS = the package's
    own data selector.
  - The copy is chosen once, at `os88spkfx_init`, by jumps the package
    writes over its own code THROUGH DS. A per-call mode test would have
    cost kern_big ~30 cycles a call, and could not reach emit's sub-block
    exits.
  - kern_big's listings are row-for-row identical over the 688 rows.
  - +476 bytes a package, so 2,380 across the five.
  - Done by an agent and merged.
- **MIDIRack's wavetable loop** (`mrwt.inc`). It patched an `adc`
  immediate, one trap a voice a span.
  - The loop is assembled twice. The protected-mode copy does
    `adc si, [MWT_VSTEP]` through the mix claim and is entered by a jump
    written at launch.
  - kern_big's loop is unchanged.
  - +166 bytes.
- **`apps/os88ui.inc`'s radio glyph** (`os88ui_gring`). It staged its four
  corner points in its own image through CS, eight traps a glyph drawn.
  That is 120 for MIDIRack's Settings dialog, and the same in every
  package or driver that draws a radio.
  - The points are now pushed on the stack and handed to
    `OSAPI_GFX_POINTS` with DS = SS. SS is writable on every kernel and
    for every includer.
  - `glyphcost` (its time budget) and `radio` pass on kern_big.
  - Seen on 86Box: the Settings dialog draws its rings correctly and
    leaves no per-glyph traps.

**Verified:**

- The scoped rows `spkfx spkfxtab spkbench apspk trkspk trkspklevel vidspk
  vidspkcounts midirackwt radio glyphcost` all pass.
- On 86Box's mr286 profile, MIDIRack playing on the SB wavetable now logs
  no per-span `#GP`. The earlier 282C:2178 site is gone, and so are the
  glyph's eight sites at 282C:8076-809B.

**Still trapping by design:** writes through CS that run once (init,
ratchet). Excitebike's per-frame renderer state and its pose loader no
longer write through CS (14.21), and 1942's frame was already clean when
this was written: its last per-call site, `n_pushall`, went in 14.14.

### 14.19 Field: the Video Player's desktop poster off the grid (2026-10-19)

**Reported** on the owner's machine, build 1271, kern_mega installed to the
hard disk: opening a 21.8MB video stops at `kern_mega FAULT 0D err 1820 at
284C:142F`. 142F is `vp_thpic`'s `mov ds, ax` before `OSAPI_DECOMP` - the
DESKTOP POSTER (SPEC.md 98.1.3.11), which came in with the elendilon merge
(bbcd7fbc) and had never run on kern_mega. `vp_rdat` answers SI = where the
poster's bytes landed in `[vp_rdseg]` - the file offset's place in its
cluster, so anything at all - and the code made that a segment of its own,
`[vp_rdseg] + (SI >> 4)`, SI & 15. That is off the 8-paragraph grid on which
kern_mega has identity selectors, and what happens next depends on the low
three bits: with RPL bits it is #GP with the selector as the error code (the
field's 1820, the RPL bits not being in an error code), and with only bit 2
it is SILENTLY an LDT code alias of some other segment - which is what 86Box's
286 did with `tests/vidposter.py`'s STORED.V88 (`[vp_rdseg]` 15A0h, SI 148h,
DS = 15B4h): no fault, and a white box decoded out of the wrong memory.

**Fixed** the way the block read at `vp_kbrd` already was (item 1): the
segment moves on in whole 128-byte steps and SI keeps the low seven bits -
`and ax, 0xFF80` before the shift, `and si, 127` after. Generic, +3 bytes of
`video.o88` (44,147 packed), one poster an open, so no speed question on
kern_big. **A/B on 86Box's AMI 286** (4MB, `mega.img` at f40506c1, the clip
on a 1.44MB B:): the old player draws a white box, the fixed one the poster's
colour gradient. No fault either side but the deliberate ones. It was the
only `+ (SI >> 4)` against a claim in the merged poster code.

### 14.20 Field: a packed file read into a claim above 1MB (2026-10-19)

**Reported** on the owner's machine, build 1271, kern_mega on the hard disk:
double-clicking README.TXT opens Note Pad empty and toasts `Disk error`;
MIDIRack says `The file could not be read` for every song. Both read a
PACKED file (SPEC.md 20.13.5: the readme and every data file ship 'CZ') into
an `OS88_HIGHMEM` claim - a selector above 1MB. The floppy fails the same way,
so the disk was never the variable.

**The defect:** above 1MB the read walks the OFFSET and not the segment -
`dskw_rflush` and the staged sector add to `[dskw_src]`, a selector having
no paragraphs to step (`[dskw_hi]`). `dskw_czexp` then did what the
conventional arm does, `lds si, [dskw_src]`, and looked for the 'CZ' header
past the end of what it had just read; the decoder refused it, `.czbad`,
FERR_IO. Found under QEMU's GDB stub (Note Pad's read answers AX = 2 with ES =
its claim 2824h; the stop at `dskw_rdata.corrupt` from `.czbad` after the
whole chain had arrived). Two things cost the hunt time and are worth
knowing: **`.cold` is not at COLD_SEG on kern_mega** - selector 0F40's base
is 121000h, the cold rung having moved above 1MB, so the F400h copy a map
suggests is stale - and a breakpoint stops again on itself until it is
deleted and stepped over.

**Fixed:** `[dskw_czsrc]` banks the packed bytes' offset where R is folded
in, and the expansion reads it under `[dskw_hi]`. +2 bytes of `.bss` and a
few of `.cold`, kern_mega only (inside `%ifdef KERN_MEGA`). QEMU: README.TXT
loads from the first instance on a fresh boot. 86Box's MR BIOS 286 (4MB,
SB16, kern_mega INSTALLED on an IDE disk): README.TXT loads, MIDIRack loads
BATTLE1.MID and plays it through the PC speaker (`PC speaker - pulse-width
synth at 16,124 Hz`). The owner's `The PC speaker is busy` is NOT that defect: it happens with the
song loaded, double-clicked with MIDIRack's saved output the PC speaker, and
it did not reproduce on 86Box's MR BIOS 286 at all - the same double-click,
the same saved setting, SB16 fitted, plays. `-DMR_SPKDIAG` (assembled by
hand: `nasm ... -DMR_SPKDIAG apps/midirack/midirack.asm`, then `os88pkg.py
--part build/mrfaces.bin`; the shipped build is byte-identical without it)
turns the message into `Speaker refused: run fl=F ax=A spk=S`: OSAPI_FSX_RUN's
FLAGS and AX, and OSAPI_FSX_SPK's code - FFFF never asked (the bracket itself
refused), 1 not in a rate bracket, 3 the speaker taken. Sent to the owner.

**Also fixed on the way, found reading `mega_hibnc`:** the bounce for a BIOS
transfer into a buffer above 1MB split the caller's run into chunks and
advanced only CL's sector number (`add CL, AL`, "inside one track"), while
a fixed disk's run goes to the cylinder's end (SPEC.md 18.91.5) and a
floppy's may cross a head (18.91.1). A chunk past a head's last sector asked
for sector 18 of a 17-sector track. It now stops each chunk at the track's
end and carries sector, head and cylinder by `[disk_spt]`/`[disk_heads]`, the
geometry the caller's CHS was made with (+1 byte of `.text`, `[mega_hbdh]`).
Not what the field hit - this path is reached only where `dsk_xfer`'s own
landing is absent - and not separately reproduced.

### 14.21 Excitebike's and 1942's frames: no write through CS (2026-10-19)

14.18 left the per-frame renderer state of Excitebike, and "1942", on the
list of things that still trapped. Both were measured under Bochs with
`make megatrap` (`tools/megatraps.py`), from the race's first frame through
about 40 seconds of riding with Z held: Selection A before, and Selections A
and B after, with lane, lean and turbo keys. The CGA rows are a second
census tree, `make BUILD=build/megatrapcga MEGATRAP=1 VIDEO=cga`, whose CGA
modes Bochs's VGA runs. (It shows the race with the HUD at the TOP: Bochs
does not wrap the CGA's 16KB start-address ring. Both builds show the same,
so it says nothing about the change. The CGA picture is checked by
`excitebikevideocga`, on MartyPC's real CGA.)

| kern_mega, Bochs | before | after |
|---|---:|---:|
| Excitebike VGA race, 40 s | **108,763** traps at 36 sites, 2,146 frames: **50.7 a frame** | **0** |
| Excitebike VGA race, Selection B (three rivals), 40 s | not taken | **0** |
| Excitebike CGA race, Selection B, 40 s | **911,764** at 44 sites: ~343 a frame | **0** |
| the bracket's pose load, VGA (`xs_shift`, `xs_compile_v`, `xv_dicts`) | **44,304** | **0** |
| the bracket's pose load, CGA (`xs_cgarow`, `xs_compile`) | **34,247** | **0** |
| 1942 VGA, 30 s and then 50 s of play | **0** | **0** |

Two of the before rows deserve a note:

- 834,878 of the CGA's 911,764 were **one instruction**:
  `xb_clk_sample`'s store, called from `xc_vr`'s retrace spin. The spin
  waited at a trap an iteration.
- 449 more were in a NAMELESS image: the compiled CGA poses. `xc_draw`
  handed them ES = `push cs / pop es`, so every byte they wrote into the box
  trapped.

From launch to the title, each after-run logged one line, `0060:04E7`, an
`xfer` in the kernel's own image. The before runs logged the same line, so
it is not the package's.

**1942 needed nothing.** No `[cs:]` store and no `push cs` is left in
`apps/1942`. Its last per-call site, `n_pushall`, went in 14.14, and the
14.18 line was stale. `1942.o88` is byte-identical to the base.

**What changed in Excitebike.** All of it is generic: the same code on
every kernel. SPEC.md 102.11 is where the state lives now.

- **The column constants** (`xc_col` / `xh_col` with `xc_run` / `xh_run`)
  are a 10-byte frame on the stack, read through BP. `xc_setx`,
  `xh_setx` and five words of bss are gone.
- **The VGA** (`xv_sync`, `xv_erase`, `xv_col`, `xv_bike`, `xv_fp_add`,
  `xv_hud`): every store is made while DS is ours. DS moves to the card
  only for the latch-copy loops, which keep their counters in registers.
  `xv_bike`'s interpreted loop keeps the layer in BP's high byte, and its
  `push cs / pop ds` is now a `push ds` / `pop ds` pair.
- **The CGA box** is ES = DS's selector, so the compiled poses, the
  interpreter and `xc_drawc`'s three words write it without a trap.
- **The clock.** `xb_clk_sample` is DS-relative. The two callers whose DS
  is foreign (the full-window column loops) call `xb_clk_samplef`, the
  CS-relative body.
  - Under `CPU_F_PM`, `xb_pmset` writes a `jmp short` over that entry's
    first two bytes THROUGH DS, at the top of every fullscreen bracket. The
    jump goes to an arm that loads DS from `[xb_self]`, banked by the same
    routine.
  - This is the one patched dispatch. A per-call mode test or a DS reload
    would have cost kern_big the full-window frames.
  - The two bytes it replaces are two one-byte instructions, and an
    assembly-time `times` refuses a jump that would not be short.
- **The pose loaders and compilers** keep DS ours and reach the art or
  the claim through ES.
- So does the custom-course copy.

**Bytes:** the image is **216 smaller**, 31,540 -> 31,324, and the bss
**10 smaller**, 9,696 -> 9,686. Every changed frame routine is shorter:

| routine | base -> now |
|---|---|
| `xv_erase` | 327 -> 290 |
| `xv_bike` | 348 -> 315 |
| `xc_run`, `xh_run` | 111 -> 91 each |
| `xc_col` with `xc_setx` | 192 -> 152 |
| `xh_col` with `xh_setx` | 320 -> 272 |
| new: `xb_clk_samplef` | 45 |
| new: `xb_pmset` | 23 |

**kern_big is faster, not merely as fast.** Measured on MartyPC's 4.77 MHz
XT with `tests/excitebike_perf.py --scroll` (and `--herc --scroll`), run
in this tree and in a worktree of the base commit, f40506c1, in the same
pass. Mean clocks a frame, about 150 frames each:

| | base | now |
|---|---:|---:|
| VGA erase | 5,185 | **4,744** |
| VGA columns | 9,016 | **8,944** |
| VGA a column write (`xv_col`) | 6,434 | **6,389** |
| VGA sprites | 8,590 | **8,485** |
| VGA HUD / flip | 1,480 / 392 | 1,479 / 393 |
| CGA columns (0.42 columns a frame both) | 6,504 | **6,211** |
| CGA boxes (RAM) | 9,297 | **9,237** |
| Hercules columns (0.49 / 0.50 columns a frame) | 8,498 | **8,122** |

The CGA's and Hercules' HUD and box-transfer rows moved by 1-3% **both
ways**. Their code is byte-identical: the same routine at a shifted address,
which an 8088 fetches a byte at a time and so cannot price differently. The
script's frames land on different scroll positions from run to run, so those
rows are the workload's spread, not the change's.

**Rows run once, after the change:** `soak -k 'excitebike*'`, **35 of 35
ok**. That covers the three adapters' video, flow, AI, custom-course, perf,
lap, Selection B, audio, geometry, low-memory, small-claim and load rows.
1942's rows were not run: its package is byte-identical, so they would boot
the same bytes.

**For the owner to look back over:**

- **The patched entry is a real-mode byte pattern that kern_mega
  rewrites.** It is the shape `os88spkfx_init` already ships (14.18), one
  routine instead of six.
- **The CGA picture under kern_mega has only been looked at on Bochs**,
  whose CGA emulation does not wrap the ring. A real 286 with a CGA or a
  Hercules has not run this build.
- **Hercules is checked statically only.** Bochs has no Hercules. No
  `[cs:]` store is left on `xh_col`'s path, and `excitebikevideoherc` passes
  on kern_big.

### 14.22 Field: every DOS trip refused on the way home (2026-10-19)

**Reported** on the owner's machine: launching Test Drive III on kern_mega
ends at `Resume failed: the programs' memory did not read back as it was
saved`, and the program never appears. **Reproduced on 86Box's MR BIOS 286**
(the 286 reset route, kern_mega installed on IDE) with DOSHELLO.COM, which
runs, prints, takes its key and exits 42 - and the trip home then refused the
same way. So not the program's.

**The defect is mine, item 3's** (0f622b1a). The programs' sum (SPEC.md
87.4.1) is taken in `hbm_wrimg`'s step 5 and checked at `hbm_wake` 3a - and
kern_mega's park route (`hbm_dosrun`, KERN-MEGA-DOS-PLAN 2.3) never calls
`hbm_wrimg`: it sweeps, locks, snapshots and on the way home jumps straight to
`hbm_wake`. So 3a compared the live sum against whatever `[hbm_psv]` held -
zero, or the last real hibernate's - and refused every trip. Bochs's runs of
the park predate item 3, which is why nothing caught it.

**Fixed:** the park route takes the sum itself after the lock and before
`mega_dosparkf`'s snapshot, so the park holds the figure and the restore
brings it back with everything else. kern_mega only. 86Box, the `DOSRMARK=1`
build: DOSHELLO.COM `ended, exit code 042 (Arena: 622KB)`, the desktop back.

**Left open:** Test Drive III itself exits 255 at once under kern_dos on
this machine (`TD3.EXE ended, exit code 255 (Arena: 622KB)`) - the round trip
is now fine, the program is what refuses. That is a kern_dos compatibility
question and is investigated on its own (docs/DOS-DEBUGGING.md).

### 14.23 Field: Test Drive III exits 255 at once - EXEPACK under the HMA (2026-10-19)

**14.22's open item, answered.** `TD3.EXE` is packed by Microsoft's EXEPACK
(no relocation entries, entry at CS:0010, `'RB'` at CS:000E, the string
*Packed file is corrupt* before `mov ax, 4CFFh / int 21h`). Its unpacker
normalises both pointers DOWNWARD, so the bottom of its output is written
through a segment below 0 - correct only through the 1MB wrap. kern_dos in
the HMA (W4) is the one arena in the tree that is both BELOW 64KB and run
with A20 OPEN, so the wrap reaches the HMA, the unpacker reads garbage and
exits 255; its message goes to handle 2 and is gone with the program. **kern_mega
only**: kern_big's kern_dos leaves A20 as the BIOS has it, which is why the
same file runs there. Not TD3's: it is the whole EXEPACK class, and W4 named
it and answered it with `LOADFIX`, which nobody types.

**Measured, Bochs**: `TD3` exit 255 (Arena 621KB), `LOADFIX TD3` the Main
Select Screen. **Fixed** in kern_dos's loader (`kd_xpack`, SPEC.md
96.40.9.1): EXEPACK's shape below 64KB raises the floor to 1000h and reads
the image again - LOADFIX unasked, keyed on the shape EXEPACK's own
header gives it. Bochs, after: `TD3` plays and `Exit to DOS` ends `exit code 000
(Arena: 566KB)`; `XPACK.EXE` (tests/dostrap/xpack.asm) 048 at 566KB, its
spoiled-signature control `XPACKNS.EXE` 255 at 621KB, and `XPACK.EXE` on the
build before the fix 255 at 621KB. kern_dos +104 bytes on kern_mega, kern_big's
`kerndos.bin` byte-identical. **On 86Box's 286-video profile** (MR BIOS 286,
4MB, kern_mega installed on IDE, the 286 reset route): TD3 double-clicked
shows its title picture and the Main Select Screen, Esc and Y exit to DOS,
and the box reports `exit code 000 (Arena: 567KB)` with the desktop back.
The owner's own 286 is still to run it.

**And `make mega` did not rebuild it**: the two image rules reach the kernel
and DOS.O88 only through a sub-make that runs when the IMAGE is stale, and
nothing under `kernel/`, `kerndos/` or `apps/dos/` was a prerequisite - so a
change there alone printed success over the previous kern_dos. `MEGASRC` is.

### 14.24 The loader unpacks EXEPACK itself (2026-10-19)

**14.23's answer cost the class ~55KB of arena**, on exactly the programs big
enough to have been packed: Test Drive III ran at 567KB against the ~570 the
owner says it needs. The owner's call: *"1 sounds like a good fix for giving
even the most ram hungry exepack's their arena, so I think do it."* So on the
HMA arm the program's own unpacker no longer runs at all (SPEC.md 96.40.9.1):
`kd_xunp` (`kerndos/kdxpack.inc`) unpacks the image in place after
`dos_exe_setup`, from the published format and written from it - the
backward fill/copy stream, the sixteen-group relocation table after the
stub's message, both header shapes - with its pointers clamped at the load
segment where the stub's wrap below it. Everything is checked first,
including a dry walk of the whole stream, so a refusal writes nothing and
14.23's floor raise is the fallback.

**Measured, Bochs (kern_mega, 16MB)**: Test Drive III to the Main Select
Screen, Esc and Y, `TD3.EXE ended, exit code 000 (Arena: 621KB)` - against
566 before. The format probe `XUNP.EXE` (`tests/dostrap/xunp.asm`, packed by
`tools/os88xpack.py` behind a stub that only refuses) **048 at 621KB**, its
18-byte-header twin `XUNPL` 048 at 621, the spoiled-table and spoiled-stream
twins `XUNPT`/`XUNPS` 255 at 566 (refused, floor raised, stub run), and the
14.23 pair unchanged: `XPACK` 048 at 566 (shape without the format, so the
fallback), `XPACKNS` 255 at 621. **Red on purpose**: with the relocation pass
taken out `XUNP` and `XUNPL` exit 051, the probe's own code-fixup check.

**Bytes**: kern_mega's `kerndos.bin` 34,329 -> 35,305 (+976) and 38 of bss,
all of it in the HMA - `KD_IMG_KB` 36 -> 37 for the HMA arm only, the arena
unchanged; `DOS.O88` 49,763 -> 50,616 on mega.img. kern_big's `kerndos.bin`,
`doscore.bin` and `dosp.bin` byte-identical.

**Left open**: a CHILD loaded by `AH=4Bh` below 64KB still runs its own
unpacker (the core's `dos_exec_load` does not pass through `kd_entry`'s
loader); a host hook for it is the next step if a launcher program ever
needs it.

### 14.25 `Load DOS in the HMA`: a second kern_dos, low, A20 shut (2026-10-19)

**The owner's second fix**: *"Could we also have a 'load in hma' checkbox in
the settings, and thus have two possible fixes?"* 14.24 cures the class that
names itself; this one cures the wrap whoever wants it. SPEC.md 96.40.9.2 is
the contract. kern_mega's `DOS.O88` carries both kern_dos images - part 2 in
the HMA, part 3 (`-DKD_LOWDOS`) at 0060:0000 - and the box's Memory page has
a check box beside *Disable the mouse*, ticked by default, saved in a
shortcut as byte 12's bit 3. Unticked, the box posts part 3 and sets
`KDLF_LOWDOS`; `HIBER.DRV`'s stub reads the bit to choose where it expands,
copies the block into and jumps; the low image shuts A20 after `kdx_init`
(port 92h where there is one, then the 8042) and `kd_unpark` opens it again
on the way home.

**Where it lives was a choice between two conventions** and this is the one
the box's other launch-time choices already use (the Memory page, per
launch, carried by a shortcut), rather than SPEC.md 51.5's `SYSTEM.CFG`,
which is for machine-wide settings a driver or the kernel reads at boot.
Greying: the box exists only in kern_mega's `DOS.O88`, which refuses to
start anywhere but a kern_mega in protected mode, where both images run - so
there is no state in which it is a fact that it cannot be honoured. kern_big
and kern_small do not show it at all: their Memory page has no free row
(SPEC.md 96.36.2) and their `DOS.O88` stayed byte-identical.

| measured | Bochs (16MB) | 86Box 286-video (MR BIOS 286, IDE) |
|---|---|---|
| ticked: Test Drive III | 000, 621 KB | **000, 622 KB** |
| unticked: Test Drive III | 000, 585 KB | **000, 586 KB** |
| unticked: `XPACKNS.EXE` (needs the wrap, no shape) | 048, 585 KB | 048, 586 KB |
| unticked: `XPACK.EXE` | 048 | 048 |
| unticked: `A20PUB.COM` / `A20SHUT.COM` | 071 / 032 | 071 / 032 |
| ticked again: `XPACKNS` / `XUNP` | 255 at 621 / 048 at 621 | - |

The page's estimate moves with the box: 612 KB ticked against 576 unticked
on Bochs, 613 against 577 on 86Box - nine under the measurement on both
arms, the direction an estimate should err.

**Bytes**: part 3 is 33,952 bytes (13,649 packed) and `DOS.O88` on mega.img
goes 50,616 -> 64,265; the box +142 bytes, `HIBER.DRV` +35 bytes of file.
Nothing resident; kern_big's `kerndos.bin`, `doscore.bin`, `dosp.bin` and
`DOS.O88` byte-identical. The low route reads ~13KB more of `DOS.O88` at the
handoff (the one extent run covers parts 1 to 3), the default route nothing
more.

**For the owner to decide**: (1) whether the default should follow the
program rather than the box - an EXEPACK image the loader REFUSES falls
back to 14.23's floor raise at 566 KB, where the low image would have given
it 585, but kern_dos cannot switch image itself (the stub that loads it is
gone by then), so that would be the box re-posting the launch low; (2) whether a machine-wide
default belongs in `SYSTEM.CFG` as well, for a user who wants every launch
low; (3) the owner's own 286 is still to run both arms.

### 14.26 The refused EXEPACK program switches itself to the low image; and the AH=4Bh child (2026-10-19)

**14.25's open question (1) answered, and the other way round.** It asked
whether, for an EXEPACK program the HMA unpacker REFUSES, the default could
follow the program - the floor raise gives it 566 KB where the low image would
give 585 - and reasoned the only way was *"the box re-posting the launch low"*,
a full return trip to the desktop. The owner's call was to hide it entirely:
**NOT to re-post at all**. The HMA kern_dos is already in real mode with its
own file layer, so it reads part 3 of `DOS.O88` itself and becomes the low
image in place. SPEC.md 96.40.9.1 is the contract.

**Task A - the switch** (`kd_tolow`, `kerndos/kdxpack.inc`, HMA arm only).
`kd_xpack` calls it the moment `kd_xunp` refuses, before the floor raise. It:
reads part 3's file row from the launch block (the box stages `KDL_L3OFF` /
`KDL_L3ZB` in `dos_lbfill`) and `DOS.O88`'s cluster and volume (the kernel
stages `KDL_O88CL` / `KDL_O88V` at `hbm_dosrun` step 2, where the file is
found); mounts that volume; walks the chain to part 3 and reads its packed
sectors into a 64 KB staging window at the arena floor, the stream placed at
the window's TOP so the expansion below never overtakes it; expands it with
`kxl_dec`, an LZ4-only os88lz reader written for this arm (kern_dos's
`kdshim.inc` stubs `lz_decomp`, and pulling all of `kernel/lz.inc` into the
HMA kilobyte would be bigger and collide with kdshim's mirrored constants - it
is the fourth reader of the format, after os88lz.py, lz.inc and hiber.inc's
`kds_expand`, and models the last); stages the launch block with `KDLF_LOWDOS`
set and `KDLF_LOADFIX` clear; then - **touching no stack**, because the
copy-down overwrites the HMA arm's own FAT snapshot, mount buffers and stack
at 0060h (kdlayout.inc) - copies the low image to 0060:0000, the core into its
`CORE_ORG` hole from this image's own copy, and the block where the low image's
header points, and far-jumps in, exactly as `kernel/hiber.inc`'s stub would.
The park fields (`KDL_PBASE` ...) ride the block verbatim, so the way home is
the low route's. 14.23's floor raise is the fallback when part 3 cannot be
read. **Chosen only for an EXEPACK-shaped program the unpacker refused**, not
every refusal.

**Task B - the child** (`DHK_XUNP`). `AH=4Bh` does not go through
`kd_entry`'s loader, so a launcher's EXEPACK child ran its own unpacker below
64 KB with A20 open and failed. A new host hook - `DHK_XUNP`, filled with
`kd_xunp` by the HMA host only, `%ifdef DOS_MEGA` so kern_big's core stays
byte-identical - is called by `dos_exec_load` after `dos_exe_setup`, against
the same `[dos_exe_*]` cells. A child it refuses runs its own unpacker (which
works at or above 64 KB); the top-level switch is not available mid-run (the
stub is gone), so `LOADFIX` per child is what is left for a refused child that
needs the wrap.

**Measured, Bochs (16MB, kern_mega from A:)**, all on the glass:

| probe | arm it took | exit / arena |
|---|---|---|
| `XSWITCH.EXE` (shape, refused) | SWITCH -> low, A20 shut | **042 (0x2A), 585 KB** |
| `XSWITCHN.EXE` (signature spoiled) | stays HMA, A20 open | **254 (0xFE), 621 KB** |
| `XPACK.EXE` (shape, no format) | SWITCH -> low | **048, 585 KB** (was 566 via the floor raise, 14.24) |
| `XPACKNS.EXE` | stays HMA | 255, 621 KB |
| `XKIDRUN.COM` EXECs `XUNP.EXE` | child unpacked by the hook | child **48**, parent 048 @ 621 KB |
| `XKIDRUNT.COM` EXECs `XUNPT.EXE` (table spoiled) | hook declines, child's stub runs | child **255** |
| Test Drive III, ticked | HMA, `kd_xunp` unpacks | to the Main Select Screen, ~621 KB |
| Test Drive III, unticked | low, A20 shut, own unpacker | to the Main Select Screen, est 576 (585 arena) |

`XSWITCH`'s exit code is the clean proof: 042 happens ONLY on the low image
with A20 shut, which only the switch reaches from a double-clicked program.
`XPACK` moving 566 -> 585 is the same switch replacing the floor raise. The
child probe's 48-against-255 is the hook unpacking and declining correctly;
`XKIDRUN` first HUNG on the return until its own stack was moved into the 8 KB
it shrinks to - a 128 KB child overwrites a .COM's default `SP = 0FFFEh`,
which is the launcher's bug and not the kernel's (the dosexec gate's DOSKID is
too small to reach it).

**Bytes**: `kerndos.bin` (HMA) 35,305 -> 35,721 (+416, the switch and
`kxl_dec`, inside `%ifdef KD_HMA`); `dosp.bin` +16 (part 3's row);
`HIBER.DRV` +12 (`KDL_O88CL`/`KDL_O88V`, kern_mega only); the core +11 and
`CORE_BSS_SIZE` mega 3509 -> 3511 (`DHK_XUNP`); `DOS.O88` 50,616 -> 64,777.
**kern_big's `kerndos.bin`, `doscore.bin`, `dosp.bin` and `DOS.O88` are
byte-identical** - verified by `cmp` against a base build. Every byte added is
behind `KD_HMA`, `KD_MEGA` or `DOS_MEGA`.

**Still open**: the owner's own 286 is still to run both arms; 86Box's
`286-video` run of these probes (14.24/14.25's machine) is the next field step.

**Field (2026-10-20)**: both arms make the whole round trip on the owner's
286, Load DOS in the HMA ticked and unticked.

### 14.27 A write from above 1MB stamped its hint from past the end (2026-10-20)

**Reported off the owner's 286**: FTPD taking a `STOR MIDIRACK.O88` stopped
on `kern_mega FAULT 0D err 0000 at 0F40:93DE`. That is `.cold`'s first
instruction of `dskw_czhdr`, `cmp word [es:bx], DSK_CZ_MAG`, reached from
`dskw_czstamp` - the compressed-file hint (SPEC.md 20.14), which a write
derives from the file's first bytes after the data is down.

**The defect is 14.20's, on the write side.** Below 1MB the write loop
advances `[dskw_wseg]` and leaves `[dskw_seg]:[dskw_src]` on byte 0; above
1MB a buffer is one selector and the loop advances `[dskw_src]` itself, a
run at a time. So the stamp read the hint from the END of the bytes just
written - one past the limit of FTPD's selector for the file that faulted,
and for any smaller high write a word of whatever lay there, which could mark
a plain file compressed or miss a compressed one. Only whole sectors move the
offset (a partial tail goes through the stage), which is why a buffer that
ends mid-sector reads short of its limit and does not fault.

**The fix** banks byte 0's offset in `dskw_wdata`, beside `[dskw_wseg]`, into
14.20's own `[dskw_czsrc]`, and `dskw_czstamp` reads the header from there.
Below 1MB the two cells are equal, so one load serves both. Inside `%ifdef
KERN_MEGA`: kern_big and kern_small byte-identical (`md5sum` against builds
of the same commit without it).

**The gate** is a new leg of `tests/megaxm` (steps 2D-2F): 32,768 bytes, whole
sectors, written from an `OSAPI_XMEM_SEL` window exactly that size. On the
kernel without the fix Bochs reports `#GP` at `0F40:93DE`, the field's
address to the byte; with it, `MEGAXM: ok`. The existing leg's 40,000 bytes
from a 64KB window could never have caught it - the stray read landed inside
the window.

### 14.28 The installer's copy buffer, refused on every rung (2026-10-20)

**Reported off the same machine**: Control Panel -> Hard Drive -> Install
says `Not enough memory to copy`, with megabytes free.

**It is the owner test, not the memory.** `hd_ibuf_get` walks its ladder
down to 8KB and every rung is refused. The installer is HDD.DRV's SECOND
image (`HDDTOOL.DRV`, SPEC.md 52.11.7), a conventional claim HDD.DRV made -
and on kern_mega HDD.DRV is moved above 1MB at boot (item 82,
`drv_hi_move`), which re-points the tool claim's owner at the driver's new
selector and FREES the driver's own conventional claim. `mem_own` then
finds the tool's claim, takes its owner, and asks whether a `MEM_K_DRV`
claim starts there; none does any more, so the claim is refused. The arm
that answers this - `drv_owns_seg_x`, which asks `drv_tab` - was written for
a driver in the HMA, which runs in no claim either, and is compiled only
under `HMA_DRV`, which kern_mega never defines.

**The fix** compiles that arm for kern_mega too (`%if %isdef(HMA_DRV) ||
%isdef(KERN_MEGA)`), and the high arm's own copy of the same call - for a
package placed high - now falls to it instead of repeating it. kern_big and
kern_small byte-identical.

**Verified** on Bochs with `docs/BOCHS.md`'s installer recipe (blank C:,
Format, Install): the kernel without the fix stops on `Not enough memory to
copy` exactly as the 286 did, and with it the install runs to `Done - remove
the floppy, Restart`. E9 shows `above 1MB: Hard Drive` on both, the
precondition. Not yet on the owner's machine.

**Field (2026-10-20)**: FTPD's upload now works on the owner's 286; the
installer no longer refuses its copy buffer (it went on to 14.30).

### 14.29 The Video Player's bench record, off the grid (2026-10-20)

**Reported**: `kern_mega FAULT 0D err 2DC8 at 284C:5E47` the moment Play
starts. `284C:5E47` is `vp_bngen`'s first instruction, `mov es,
[vp_bnseg]`: THE BENCH (SPEC.md 98.1.9.13) is built in the ring past the
key's read and a LEAD, and the lead was added in whole paragraphs,
`([vp_alb] + 15) >> 4` - which kern_mega's grid needs in whole GRANULES
(14.16's rule, 14.19's class of fault). T69's lead is 6 x 882 bytes = 331
paragraphs, three past a granule, and selector 2DCBh's error code is 2DC8h.
**Fixed** by rounding that term up to 8 paragraphs under `[vp_pm]`
(`video.o88` +9 bytes, the real-mode arithmetic untouched). Every other
`+ [vp_ring]` in the player was read: slots are 2,048 paragraphs, the key's
lead `[vp_kbkb] << 6`, the planes 14.16's - this was the one. Not booted
here: the bench is taken only by a layout at or below Mode X, and every
such demo with a bench is 21MB or more, past Bochs's C:; SNOW (VGA8 at 320,
past Mode X) plays through and never reaches it.

### 14.30 The string-restart calibration measured nothing on a REP (2026-10-20)

**Reported**: the installer, from a mounted image and then from a real
floppy, `No system disk: A:k33 #ERNEL #ER KERN KER` - 54.1's signature
exactly: the record fetched through the faulting `rep movsb` is missing its
first byte, the one fetched without a fault is right.

**The calibration never ran its REP probe.** `mega_strcal`'s `.probe` set SI
and DI and left CX "as given", and `.take` measures the advance as `2 -
CX`, so the probe had always meant CX = 2 - but CX at `mega_enter` is
whatever the loader left. With CX = 0 the `rep movsb` moves nothing, takes
no fault, and `mega_sdr` reads 0 0 0: "this CPU restarts a REP exactly".
`mega_strfix` then corrects a plain MOVS (whose probe needs no CX) and never
a REP MOVS - and `dsk_find_x`'s name copy is a REP MOVSB. The Victory's
boot happened to arrive with CX non-zero; the owner's MR 286, booted from
its hard disk, did not.

**Measured on 86Box's `286-mega` (MR BIOS 286, the owner's board)**, reading
`mega_sdr`/`mega_sdp` (linear 62C9h) after boot: the kernel before the fix
`00 00 00 00 / 01 01 00 00`; with `.probe` setting CX = 2, `01 01 00 00 /
01 01 00 00`. 86Box models the 286's early advance, which Bochs's 386 does
not (both read 0 there). +3 bytes of `.text`, kern_mega only.

**The refusal line was changed with it**: on the owner's first attempt the
fields that would have said this were dropped for length behind `A:g1
B:g1`. The first `k` entry now starts the line over, so a volume that
mounted and failed the compare always keeps its four fields. HDDTOOL.DRV,
both kernels.

**Headroom found on the way**: kern_mega's `.text` + `.bss` is FF88h of
KERN_CODE_MAX's 10000h - **120 bytes**, against kern_big's B1F9h. `make
megatrap` overflows it by `mega_tlog` (~150 bytes) and builds with
`MSELOFF=1` beside it for now. The next kern_mega feature in `.text` meets
the segment, so it is the first thing to plan for: moving part of `mega.inc`
out of `.text` (most of it is entered from the fault and IRQ gates, which
want KDATA in DS and a near `.text` call).

### 14.31 Field, the Victory 286 (2026-10-20): what is left after 14.30

**Install now finds the system disk** (14.30 confirmed) and stops in the
COPY, naming `KERNEL.SYS`, with `FD BIOS 08 400100 A90` on the bar: the
native floppy path (`mega_fdgo`) fell back at step 8 - READ DATA's result,
ST0 40h (abnormal termination) ST1 01h (Missing Address Mark) - on drive A
at media 90h, which is 250 kbps: a 9-sector (720 KB) disk in the 1.44 MB
drive. An earlier attempt fell back at step 5 (`05 200000`), the seek's own
check. The fallback is meant to make the native path "only ever faster or
equal", and here the BIOS fallback did not rescue the copy either; an
access to A: with no disk in it then froze the machine, and the drive was
refused by the BIOS until a power cycle. OPEN: which disk was in A:, whether
the same install works from that disk on kern_big (BIOS only), and whether
the native path leaves the 765 or the BDA in a state the BIOS's own retry
cannot recover from. No emulator here reproduces a native failure.

**T69 plays to the end** (14.29 confirmed) at 1.79x its length - `Late 681,
2079 ticks of 1163` - with `RFL 003D/s 0CDC` on the bar: 61 IRQ reflections
a second at 3,292 us each, ~200 ms of every second. They are the PicoMEM's
option-ROM IRQ (mega_irqrom, SPEC.md 34.10.1): its Sound Blaster has the CPU
copy each "DMA" block in its ROM, in real mode, and a 286 reaches real mode
only by a reset - 22,050 bytes/s of PCM8 at ~361 bytes a block. The reset
is already a triple fault, so the 3.3 ms is the board's BIOS getting from
reset back to `mega_r286` plus the card's copy; fewer reflections is the only
lever. The other ~59% is not yet accounted for: whether HDD.DRV's rung 1
took C: (52.1.1's pairing and TAKE) or every read is a reflected int 13h
(not counted by RFL), and how the same file plays on kern_big on the same
machine, are the next two readings.

### 14.32 The installer's KERNEL.SYS copy: CX moves by TWO (2026-10-20)

**Reproduced on 86Box's `286-video`** (the owner's MR 286, booted from C:,
`IMGS/MEGA.IMG` mounted, Control Panel -> Hard Drive -> Install, keep the
volume): the copy stops naming `KERNEL.SYS`, and an INSTBENCH build says
step 9, `hd_iwrite_chunk`, answered FERR_PROT. That is a PLAIN
`OSAPI_FILE_WRITE` of KERNEL.SYS - the installer believed the file was not a
system one, `[hd_isys]` = 0, so `dskw_pmask` refused it as it would refuse a
package.

**Why it believed that**: `hd_istat`'s `OSAPI_FILE_FIND` record came back
with everything after the name **two bytes early** - the attribute 07 at +11
instead of +13, the size at +16 instead of +18 - so +13 read 0. The record is
written by `dsk_find_x`'s `rep movsb` of 13 name bytes into the driver's
buffer, and the driver's ES there is its CODE alias (`push cs / pop es`), so
the first write faults and 54.1's restart runs. At the fault the 286 frame
holds SI+1, DI+1 and **CX-2**: the CPU took two off the count for the one
element it never wrote. `mega_strcal` measured CX with `.one`, which answered
"1 -> 1, anything else -> 0", so it recorded 0 and `mega_strfix` gave SI and
DI back and not CX - the restart moved 11 bytes. Read off gdb on the fault
frame: entry CX 13, fault CX 11, restart CX 11, exit DI = start + 11.

**The fix measures rather than caps**: the probe runs with CX = `MEGA_SCCNT`
(8), `.take` keeps any advance below that as it is, and `mega_strfix` gives
back each register's own count - SI and DI by that many elements, CX up by
its own. +1 byte, kern_mega only; a 386 still measures 0 and runs nothing.
Re-run on the same machine, the same install reaches `done`, and the volume's
KERNEL.SYS is byte-identical to the source's (101,808 bytes).

**It is very likely the field's stop too** (14.31): the Victory's install
named KERNEL.SYS after finding the system disk, and the only record this path
moves through a faulting REP is that one. Whether the Victory's 286 takes CX
down by one or by two, the measurement now carries what it does. The
native floppy fallback on that bar (`FD BIOS 08`) is a separate question
and stays open, as does the freeze on an empty A:.


### 14.33 The kernel segment is full again: a segment of kern_mega's own (2026-10-20)

14.10 left 364 bytes in kern_mega's `.text` + `.bss`. Two days of merges later
there are **116** (65,420 of 65,536), against kern_big's 17,415. kern_mega
carries **17,299** bytes more than kern_big in that one segment, and 16,193 of
them are `mega.inc` and `megados.inc`. So the next 117 bytes kern_big adds
there break `make mega`. `.cold`'s slot above 1MB, between `MEGA_COLD_LIN`
and `MEGA_XPOOL`, has 3,247 left: the same coupling, one segment over.

**docs/plans/KERN-MEGA-SEGMENTS-PLAN.md is the plan, and its W0-W2 and most
of W3 are BUILT** (its section 8): the segment has **11,484 bytes left**,
kern_mega's overhead over kern_big there is 5,931 and `make mega` holds it to
`tests/megaseg.txt`. kern_mega gets ONE segment of its own, `.mega`. It is
protected-mode-only code under a fixed ROM-top selector (0xFFD8), placed on
the ladder after `.cold` and copied above 1MB with it. About 12.4KB moves in
its first bulk wave and ~3KB more after. That takes the segment's headroom
from 116 bytes to ~12,300, and moves ~12KB of conventional memory back to
the heap.

What stays low is what runs in REAL mode after the switch: the reflection's
real-mode half, `mega_r286`, the IRQ capture and the DOS drop. The cost is
64KB of the XMEM pool (`MEGA_XPOOL` to 0x140000). `tools/os88megaseg.py`
re-derives every per-section figure off the two maps.

### 14.34 Field, the Victory 286 (2026-10-20): after 14.32, and an empty drive

**Confirmed on the machine**: WireChat connects and chats; Install from a
mounted image completes (14.32), and so does Install from a real 1.44 MB
system disk; no freeze with A: empty. The image install put `native floppy
off: BIOS from now` on the glass on its way.

**That toast was an empty drive, not the native path.** Eight fallbacks in a
row switch native floppy off for the session (mega_fd13), and a fallback was
counted the moment the native attempt failed - before the BIOS had tried. An
EMPTY A: fails both, so an installer that walks both drives looking for the
system disk counted eight strikes against a path that had never failed a
disk it could read. 86Box does not show it: its empty drive asserts the
change line, which the native path hands to the BIOS uncounted. **Now the
BIOS decides**: the fallback is marked pending (`[mega_fdpend]`) and
`mega_fdjudge`, on `mega_svc_back`'s way out of that same call, counts it -
and puts the first-fallback toast up - only when the BIOS COMPLETED what the
native path could not. A call the BIOS failed too is the disk's. The fault
`mega_svc_lo.r286+31 [Vector > IDT limit]` that `os88box faults` shows on
these runs is the 286 reflection's own triple fault (`lidt` null, `int 3`),
not a crash.

**T69 reads through BIOS0.** The PicoMEM v1 serves its disk from its option
ROM, so HDD.DRV's rung 1 has no IDE port to pair it with (52.1.1) and every
read of the video is a reflected `int 13h` - on a 286, a CPU reset each -
beside the card's own audio IRQs (61 a second, 14.31). kern_big runs both in
real mode and pays neither. OPEN: how many `int 13h` a second the play makes,
which says whether bigger reads would buy it back.

**MIDIRack**: `The PC speaker is busy` is back with the right MIDIRACK.O88,
and kern_big does not click. Sent: MR_SPKDIAG rebuilt on this tree, and a
diagnostic kern_mega whose menu-bar `RFL` line (and the PicoMEM's `Q` line
after it) appears after any second with a reflection instead of twenty or
more - a PicoMEM raising its IRQ a few times a second would never have shown,
and each one is a ~3 ms reset gap in speaker PCM. OPEN on both readings.

### 14.35 Field, the Victory 286 (2026-10-20): after 14.34, and what is deferred

**Install from a real floppy works** on 78547a50, first thing after boot,
with no native-fallback toast - so the native floppy path served it, and
14.34's verdict-after-the-BIOS change did what it was for.

**MIDIRack is SET ASIDE by the owner** for the final-shape work: the
speaker refusal (`The PC speaker is busy` with the right MIDIRACK.O88) and
the clicks kern_big does not have are both open, with MR_SPKDIAG and the
RFL-threshold diagnostic kernel (14.34) built and sent but not read.
Resume from those two readings.

**T69 is still slow on BIOS0 (PicoMEM v1), and it does not read as
STARVED.** The owner's observation is the useful one: a disk-bound play
shows as stalls - the player waits on the ring - and this one plays smoothly
at the wrong speed, *"like its timer is wrong"*. That points at the CLOCK
rather than the disk: the Video Player paces on [ticks] (or the card), and
on a 286 every reflected `int 13h` is a reset whose time `mega_svc_back`
puts back into [ticks] from the BDA tick count (40:6C) - which only advances
if the ROM's own IRQ0 handler ran during the reflection, at 18.2 Hz
granularity. A reflection shorter than a tick, or one with IRQ0 masked,
loses that time from [ticks] altogether, and at hundreds of reflections a
second the video clock runs slow by exactly the time spent in them: a
picture paced to a clock that is itself behind never looks starved. **To
read before deciding**: the play's `int 13h` count a second, and [ticks]
against the PIT across a play. The owner's fallback - FSX on a BIOS-type
disk running the player in real mode for the bracket - is the decision
deferred behind that reading; it costs the bracket every byte above 1MB.

**The empty-drive freeze is back, and it is a STATE issue** (owner,
2026-10-20, on 78547a50): Install touched an empty floppy drive and the
machine froze, as in 14.31 - but only after the OS had been in use for a
while; first thing after boot the same install worked (above). So something
an earlier session of use leaves behind (the 765, the BDA's floppy bytes,
the native path's own state, a reflection's masks) is what the empty-drive
access then trips on. DEFERRED by the owner - recorded to come back to, not
being pursued now.

### 14.36 A reflection lost a rate bracket's periods: the clock T69 plays slow on (2026-10-20)

**The mechanism 14.35 reached for, found in the code.** A reflected call
hands the CPU to the BIOS with the IVT's int 08h the ROM's own, so every
IRQ0 that lands while it is out is the ROM's: it counts it at 40:6C and
nothing of the kernel runs. `mega_svc_back` then added the 40:6C difference
to `[ticks]` as ticks - which is right only at the ROM's rate. Inside an
FSXF_RATE bracket channel 0 runs at the BRACKET's divisor, so the ROM
counted the bracket's periods as ticks (the time of day ran ahead and
`[ticks]` was over-credited), and the periods themselves were never paid to
the hook - `[sch_rpend]` never heard of them. The Video Player paces its
frames on that hook (`vp_hook`, `[vp_owed]`), so every reflected `int 13h` on
a BIOS-served disk, and every PicoMEM IRQ reflection beside it (61 a second
at 3.3 ms in 14.31), was time its clock never saw: **a picture paced to a
clock that is itself behind plays slow and never starves**, which is the
owner's description. kern_big has no reflection, so it never happens there.
FASTTICK brackets had the same defect in the other unit.

**`mega_rfclk` pays them the way `sch_isr` would have**: under a rate
bracket the periods go to `[sch_rpend]` (the hook gets them all on its next
call) and their PIT counts into `[sch_racc]`, whose carries are the true
ticks; under FASTTICK `[sch_fcnt]` is counted down; and the time of day is
taken back by the ROM's surplus. Outside a bracket, and under the speaker's
(which already sets channel 0 to the ROM's rate for the call), nothing
changes. kern_mega only, `.mega`, ~110 bytes.

**Measured on 86Box's 286 (MR BIOS, 1MB so the play streams, native floppy
forced off so every read is reflected)**, a 20 s clip whose frames carry
their own timecode, sampled every 5.13 s of emulated time from Play:

| kernel | picture's timecode at each sample |
|---|---|
| 78547a50 | 0, 0, 1.467, 4.400, 9.400, 14.533, 19.667 |
| with `mega_rfclk` | 0, 0, 1.533, 4.533, 9.667, 14.800, 19.933 |

The old clock lost ~0.27 s over the clip and the new one ~0.07 - small,
because a reflection on 86Box is cheap and its floppy is quick; the Victory's
PicoMEM pays ~3.3 ms a reflection hundreds of times a second, which is where
the difference is the whole slowdown or none of it. **The owner's T69 run
on this kernel is the reading**; the real-mode-for-BIOS-disks fallback
(14.35) stays deferred behind it.
