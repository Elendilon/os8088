# `kern_mega` — a 286+ protected-mode kernel

**Status: RESEARCH. Nothing is built** (2026-10-17, branch `protected-mode`,
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
   on a 286 under protected mode at all. Its route is kern_dos's handoff
   (SPEC.md 96.49), which resets to real mode and gives the program the
   machine.
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

* **The kernel**: 468 `[cs:]` writes (led by `compress.inc` 124,
  `stikmenu.inc` 102, `ascw.inc` 49, `hiber.inc` 45 and `splash.inc` 35),
  95 `push cs / pop ds|es` pairs, and every `OSAPI_SLOT` cell, which is
  literally `push ds / push cs / pop ds`. These turn into a data-alias
  selector loaded from a variable. That is mechanical, macro-able and
  greppable. The ISRs that write through CS do so because DS is unknown on
  entry. They become `push ds / mov ds, [cs:k_dsel]`: 17 clocks for the
  segment load in protected mode against 2 in real mode.
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
  PICs, and may close A20. On a 286 under protected mode it is impossible.
  What remains is the **kern_dos** handoff (SPEC.md 96.49): drop the OS
  entirely, reset to real mode, give the program the machine, and come back
  through a resume. kern_mega's resume has to rebuild protected mode, which
  kern_dos's does not.
* **Hibernate** (`hiber.inc`, `hbstub.inc`). The resume stub lives in the
  text framebuffer and reads the image back with `int 13h`. A protected-mode
  image has state above 1MB, so the stub must be able to land it there. Use
  the reset trick: read into conventional memory, then copy up the way
  XMEM.DRV does. This is the last wave, not the first.
* **XMEM.DRV, LOADALL and `ub_set`** (SPEC.md 41.13, 41.15) become
  pointless. Extended memory is just a descriptor away. The video player's
  decode-in-place path is what it is today on a 386, but done properly.

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
needs a gate in the fast tier: a script that refuses `[cs:]` writes and
`push cs / pop ds` outside an allow-listed macro, in `t_movable.py`'s
ratchet shape. Without it the shared 85% rots in one direction only.

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

## 8. The decision to take first: 286 or 386

The owner said 286+. That choice is the most expensive word in the request,
so here it is costed against the alternative.

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
  * timing.
* **86Box** has the `286`, `286-525`, `286-sound` and `286-video` profiles
  for looking, but it cannot be scripted.
* **MAME's `ibm5170`** is a 286 with a debugger and Lua scripting. It is
  **not evaluated here**, and it is the one candidate for an automatable
  286.
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
| **M0** | decide: the floor (section 8), ring 0, the identity map, whether kern_mega is `KERN_BIG`-additive | — |
| **M1** | protected-mode entry after stage 2. GDT identity map, IDT, PIC remap, a #GP/#NP/#SS reporter. Native IRQ0, keyboard and CMOS. Floppy and video by reflection **with IRQs masked**. Kernel still at 0x0060, with code and data selectors split. The sweep: `[cs:]` writes, `push cs`, the `OSAPI_SLOT` cells. **The `[cs:]` gate lands here.** Only the ~24 clean packages run | QEMU, a desktop |
| **M2** | native 765 + 8237 floppy. HDD rung 1 absorbed into the kernel. Reflection stays only for ROM-only disks, which refuse if they are slow | QEMU + 86Box 286 |
| **M3** | LDT allocator. `.cold`, modules and caches above 1MB. Conventional memory becomes package heap. Stable selectors for LDT claims, so no relocation procs | QEMU, measured heap |
| **M4** | SDK: code aliases for claims (`cc_ovbind`, `os88partsbody.inc`), `OS88_HUGE_INCR`, the shared speaker and pcm includes. The C packages are rebuilt | +11 packages |
| **M5** | per-package rework, worst first by usefulness rather than by size | — |
| **M6** | the DOS box through a kern_dos handoff with a protected-mode resume; hibernate | field |
| later | ring 3 + call gates (an ABI flag day, SPEC.md 20.2.0.1); a 386 tier inside kern_mega | — |

M1 is the experiment that settles whether this is worth continuing. It needs
no package changes, reaches a desktop with a third of the catalogue, and
shows what the sweep really costs in a shared file.

---

## 11. Open questions

1. **The floor.** 286 or 386 (section 8). Everything else depends on it.
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
