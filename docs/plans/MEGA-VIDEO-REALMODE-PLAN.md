# MEGA-VIDEO-REALMODE-PLAN - the Video Player's bracket in real mode under kern_mega

**Status: PLAN, nothing built (2026-10-29).** Written against `4d3d0943`
from source and documents only. **Nothing was run for it**: no build, no
emulator, no row. Every byte and cycle figure below for code that does not
exist is an ESTIMATE. A figure that was measured says where it was measured.
A bare "14.nn" is a section of docs/plans/KERN-MEGA-PLAN.md, and a bare "§" is
SPEC.md.

**The owner's ask.** *"fullscreen/in-window video player needs a way to 'fall
back' to real mode, so it's not in-and-out and underperforming Big. It needs
to have parity. That may mean it removes 90% of the mega specific video player
code, and it may mean OS changes."* Their standing decisions: kern_mega gets
**parity** with kern_big for video; **no second set of videos** is encoded for
it; and the more capable kernel **must not underperform** the less capable
one.

**Scope, as corrected by the owner.** The unit is the **fsx bracket**
(`OSAPI_FSX_RUN`, §53). Full-screen play and in-window play are both brackets:
the in-window play is a same-mode bracket that leaves the desktop's
framebuffer as it is and decodes into it, so it only *looks* windowed
(§98.3.7). **Live play (§98.3.10) stays as it is**, in protected mode. It is
the one play that runs on a live desktop, through a worker, and it reads the
whole file into RAM before it plays, so it has no disk to be slow on.

---

## 0. The answer, in nine lines

1. **kern_mega already runs a real-mode bracket. It lasts one BIOS call.**
   `mega_svc` / `mega_svc_lo` / `mega_svc_back` (`kernel/mega.inc:2711`,
   `:2834`, `:2994`) leave protected mode, run one `int`, and come back. The
   bracket keeps the 8259 at `MEGA_PIC_BASE` with no ICW1, lets the mouse ISR
   run in real mode, and credits the ROM's ticks to the rate hook. On a 286
   it takes the reset path through `mega_r286` (`:3219`), with the Victory's
   PIC and 8042 fixes. **The proposal is to stay down for the whole fsx
   bracket**: one drop at the bracket's entry and one return at its exit,
   instead of one round trip per `int 13h` and per PicoMEM IRQ.
2. **This is the owner's own deferred fallback**: *"FSX on a BIOS-type disk
   running the player in real mode for the bracket"* (14.35, 14.56).
   KERN-MEGA-PLAN 2.7 first proposed dropping for the bracket, for DOS. The
   DOS trip (`kernel/megados.inc`) built the whole-machine version of it.
3. **The bracket is the right unit because the kernel is already parked
   under it.** §53.1 makes *"the kernel never runs while the mode is
   foreign"* true by construction. Only the UI task is eligible (§53.2).
   What the app may call is a closed list (§53.7). So a real-mode bracket
   has to supply that list and the ISRs, and nothing else.
4. **What does not survive the drop is everything above 1MB**: `.cold`
   (which holds the file layer, `dwf_dskw_read_seq`, `kernel/diskw.inc:3246`),
   `.mega`, the LDT, driver images, and the XMEM pool's own copy code. Every
   selector the package holds is also lost. kern_mega's `.text` is in
   conventional memory at `KERNEL_SEG`, is 8086 code, and partly runs in real
   mode already: the `KDS` macro reads `[k_dsel]` (`kernel/kernel.asm:262`),
   and `mega_svc_lo.rmc` sets it to `KERNEL_SEG`.
5. **So the kernel must do four things for the bracket**:
   * provide a small real-mode SERVICE MODULE for the services that live
     above 1MB: a pre-walked extent reader behind `OSAPI_FILE_READ_SEQ` and
     `_READ_AT`, a LOADALL or loaded-base `OSAPI_XMEM_COPY`, the IRQ0 rate
     arm, and an API-table swap that also enforces the whitelist;
   * copy SOUND.DRV low for the duration;
   * RENAME the package's claims from selectors to paragraphs at entry and
     back at exit, through the relocation procs the player already declares
     (§98.3.19.2);
   * keep one real-mode IVT arrangement for the whole play.
6. **The package then runs its SHIPPED (kern_big) bracket code, unchanged**:
   * its conventional ring, with no ring above 1MB and no bounce copy up;
   * its LOADALL or `ub_set` borrows for a bank in place;
   * its hook inside the `int 13h` that interrupts it, so the two-frames-a-call
     patch (§98.3.22.6) is no longer needed;
   * the PicoMEM's IRQs served natively.
   That is kern_big's mechanism over kern_big's code, which is what parity
   means here.
7. **Estimated cost**: ~2.5-3.5 KB for the module, read on demand and
   copied into a conventional claim for the play; ~250-400 resident bytes of
   kern_mega for the drop and return; an 8 KB conventional claim for the copy
   of SOUND.DRV; one reset per bracket on a 286 (14.31 puts the Victory's
   reset path at 3.3 ms). kern_big and kern_small are byte-identical apart
   from one flag bit that they accept and ignore.
8. **What it deletes from the player's kern_mega arm**: the ring above 1MB,
   `vp_paddr`, the bracket's in-place reads through selectors, the
   two-frames-a-call patch, and the speaker shaper's part. That is
   **~1,000-1,250 of the arm's 1,777 kern_mega-only lines** (55-70%) plus
   `apps/video/vfx.asm`. It is not 90%, because the session's work on the
   desktop (claims, poster, keeper, info card) and Live still run in
   protected mode. Section 3.5 says what would reach 90%.
9. **The gate** is the owner's two files on the Victory: Catch My Heart and
   Sonic 2, encoded for kern_big, with `VPDIAG=time` profiles on both
   kernels. Parity means the bank runs dry no earlier than kern_big's
   (frames 1312 and 733), the picture's median lag is 0, and the
   `MEGADIAG` reflection count inside the bracket is about 0. Re-measured
   that way, `mega_disk` (§98.2.3.8) should come out at 1.00, and the
   `--kernel mega` factor can be retired.

---

## 1. The problem, as measured

These are field and 86Box figures. None was re-taken for this plan.

* **The disk.** Replayed through the encoder's curve, kern_mega's plays run
  dry where the machine did only at **0.915 and 0.877** of kern_big's disk
  rate: Catch My Heart and Sonic 2, `286-picomem1`, §98.2.3.8. The profile
  carries `mega_disk` = 0.88.
* **The in-place reader's own cost**: another **0.159 ms a KB** on every
  chunk, on top of the copy up's 0.186 (`xrd`, §98.2.3.9).
* **The reflections in one Victory play** with the PicoMEM: **2,161 IRQs in
  77.3 s at 1.0 ms each (2.8%)**, and the services at **38.7% of the play,
  27.1 ms each** (§98.3.22.5). One reflected 32 KB read is the same length as
  kern_big's own call (28.7 against 30.5 ms, §98.3.22.6). **The read is not
  slower. What the read stops is the problem.**
* **What a reflection stops.** Under kern_big the rate hook runs inside the
  `int 13h`. Under kern_mega it is shut out, and the periods come back as one
  call (`mega_rfclk`, `kernel/mega.inc:3170`). Before §98.3.22.6 the picture
  was a median 14-35 frames behind, against kern_big's 0. 14.124 has the
  Victory's timed profiles: Catch spends 65% of the play in reads and 48%
  drawing. On kern_big those two overlap; here they **add**.
* **Four causes were found and fixed in 14.73**: the card's lost block
  count, landings straddling a 64 KB page, the hook starved, and the option
  ROM's line masked. 14.36 fixed the hook's lost periods. Each one was a
  real fix, and each one patches a symptom of being out of real mode during
  the call.
* **The reset.** A 286 leaves protected mode only by resetting the CPU.
  The figures disagree: 412 µs (`docs/reports/LOADALL-VICTORY286-2026-10-14.md`,
  via KERN-MEGA-PLAN section 0 line 2), **1.2 ms a round trip** (`RFL`,
  KERN-MEGA-DOS-PLAN 2.1), and **3.3 ms a PicoMEM IRQ reflection** (14.31, via
  14.124). None of the three is the cost of the reflection's own copy work.
  Whichever is right, it is paid on every read and every card block.

**Machines it does NOT affect**: a 286 whose disk HDD.DRV's rung 1 drives
natively. On `vm/286-video` the mr286's on-board IDE makes 0 resets in a
whole play, and T69 plays at 25 fps on kern_mega (14.73). That machine is
already at parity, and the plan must not make it worse (section 3.4, rule 1).

---

## 2. What already exists to build on

### 2.1 The one-call real-mode bracket (the reflection)

The reflection is in `kernel/mega.inc:2711-3216`. It already solves most of
what a bracket-long drop needs:

* **The PIC stays at 20h, with no ICW1.** An ICW1 loses latched edges, and
  a serial mouse then stays dead for the whole session (the comment at
  `:2814-2821`). In real mode the BIOS's handlers are reached at IVT
  20h-27h, which `mega_enter` copies from 08h-0Fh (`:487`, `:534`, `:12156`).
  The slave stays at 70h.
* **The mouse ISR is bimodal** (14.1 answer 18). In real mode the line is
  left open (`mega_rmaskf`, `:5000`), and `[k_dsel]` holds `KERNEL_SEG`
  (`:2875`).
* **Kernel lines are captured while an option ROM's IRQ runs**
  (`mega_capon` / `mega_capoff`, `:715`, `:764`). What they catch is
  replayed in protected mode (`mega_replay`, `:829`). The PicoMEM's
  multiplexer is the reason: the card raises its Sound Blaster's IRQ as a
  software `int 8+n` from its option ROM's handler (`mega_irqrom`, `:631`).
* **The 286 reset path** is `mega_svc_lo.r286` (`:2858`) out, through CMOS
  shutdown code 0Ah, and `mega_r286` (`:3219`) back. That path carries the
  Victory's quirks: a BIOS that re-initialises the 8259 on the reset path
  (masks compared, `mega_pic_pm`, `mega_kdrain`, 14.62 and 14.64,
  `PICLOSE=1` as the A/B), and a floppy controller reset with nobody told
  (`mega_fdrprobe`). **`mega_r286` already has a second landing**: the DOS
  park's, `cmp byte [mega_drop], 0 / jne mega_dropr` (`:3283`).
* **The return to protected mode is `lmsw` on both CPUs**, followed by
  `lgdt`, `lidt`, `lldt`, the data selectors, and NMI back on
  (`mega_svc_lo` `.go` onward, `:2938-2992`).
* **The speaker** puts channel 0 back to the ROM's rate for the call
  (`:2826`, `:3010`).

### 2.2 The long drop: the DOS trip

docs/plans/completed/KERN-MEGA-DOS-PLAN.md is BUILT. `kernel/megados.inc`
implements it:

* `mega_dosgo` (`:1252`) leaves protected mode through the same reset and
  lands in `mega_dropr` (`:1586`), which puts the 8259 back at 08h and
  enters kern_dos.
* The return is `kd_unpark` (`kerndos/kdpark.inc:23`), then the park stub
  (`kernel/megapark.inc`), then `mega_dwake` (`:1664`). `mega_dwake` does
  `lldt`, `mega_pic_pm`, the parked masks, a forced `mega_ivt_sync`, the 8042
  command byte, and the option ROM's prime.
* It parks all of conventional memory above 1MB (~165 ms each way, an
  estimate in its 2.4) and sums it, because a DOS program may write
  anywhere.

**What the trip teaches this plan, and what it does not:**

* The reset-and-land machinery, the PIC and 8042 sequence for the way back,
  and `mega_dwake`'s list are reusable as they are.
* The park and the sum are NOT needed. Our own package runs, and no hostile
  program does.
* KERN-MEGA-DOS-PLAN 2.2 argued *"not literally the fsx bracket"* for DOS,
  because the trip detaches drivers and takes the screen. Neither applies to
  a video play. The play wants exactly the bracket's frozen desktop, and one
  driver kept.

### 2.3 Extent lists and real-mode readers

The hibernate resume walks its file into an extent list while the file
layer is alive. It then reads that list from a stub with no file system at
all (§87.5). kern_dos is handed such a list too (§96.40.1, §96.40.2).
kern_dos is also the precedent for the kernel's disk layer assembled for
real mode, as a part (`kerndos/`). It costs ~33 KB, which this plan refuses
to pay (section 3.2, A2).

### 2.4 What the player already has

* **The session's claims are movable, with relocation procs** (§98.3.19.2:
  `vp_smov` / `vp_smove`, `vp_rmov`, `vp_pmov`). Every word naming a claim
  holds its base, and every other segment is derived where it is used.
  Those procs are exactly what a selector-to-paragraph rename needs.
* **The bracket already pins its blocks** at the call
  (`apps/video/video.asm:14615-14621`: `vp_rmov`, `vp_smov`, `vp_bset`
  just before `OSAPI_FSX_RUN` at `:14635`).
* **The XMEM token equals the physical address until the block first
  moves**: tokens are chosen where the block is (`mx_tokfit`,
  `kernel/mega.inc:7356`; §50.6.10). The shipped player's LOADALL path reads
  a token as a linear base (§98.3.18.13, `apps/os88la.inc`).
* **The SHIPPED build refuses at its entry on a protected-mode kernel**
  (`OS88_MEGA_REFUSE`, `apps/os88mega.inc:42`; the header comment at
  `video.asm:50-63`). Every refusal reason it names is a real-mode technique,
  which is why it would be correct inside a real-mode bracket.

---

## 3. The options

### 3.1 A: a REAL-MODE BRACKET (`FSXF_REAL`) - RECOMMENDED

`fsx_run` (`kernel/fsx.inc:180`) gains a flag: CX bit 3, `FSXF_REAL`, and
only with `FSXF_RATE`. On kern_mega the bracket is armed as today, and
then, before the entry proc is called, the kernel leaves protected mode. It
returns to protected mode after the entry proc returns and before
`fsx_restore`. kern_big and kern_small accept the bit and ignore it: they
are already in real mode. §53.1's rule that undefined bits refuse means the
bit has to be defined everywhere in one change. The cell does not move, so
this is a clarified contract with no `PKG_FMT` bump
(`tools/abilock.py --update`).

**What the kernel does at the drop**, in protected mode, in this order. A
refusal at any step leaves the ordinary protected-mode bracket running,
which is today's player and a normal path (§47):

1. **Refuse unless it pays**: the stream's volume is BIOS-served (a rung-0
   or BIOS0 volume), or the sound card's IRQ belongs to an option ROM
   (`mega_irqrom`). A rung-1 ATA disk, a floppy (native, `mega_fd13`), a RAM
   disk, a CD or the HTTP drive keeps the protected-mode bracket. Also
   refuse if any `TF_SERVICE` task is alive or `FSXF_KEEPWORKER` is set: a
   real-mode bracket runs ONE task.
2. **Load the service module** (section 3.1.1) and copy it into a
   conventional claim. Modules live above 1MB on kern_mega, so the copy is
   needed.
3. **Walk the stream into an extent list**. The package names the file: DX
   is a NUL 8.3 name in its image, or ES:DI the `READ_SEQ` cursor it already
   holds, with `RSQ_VOL` and `RSQ_CUR`. Each cluster run becomes an absolute
   sector run on its BIOS unit, in a conventional scratch. Fragmented past a
   cap (an estimated 256 runs, 1.5 KB) refuses.
4. **Copy SOUND.DRV's image low, if the session holds a stream**. Its image
   is a `MX_KDRV` block above 1MB. Copy it into an 8 KB conventional claim
   at a paragraph with bit 2 clear, so that `SBL_DSCS`
   (`drivers/sound/sb.inc:840`) yields DS = CS, and tell it with a new verb
   (`DSV_RMODE`). The driver renames the segments it holds (the package's
   external ring, its double buffer) and its open-time `CPU_F_PM` choices
   (`sbl_dpm`, `sb.inc:1711`, `:3898`). The card is halted between brackets
   (§98.3.7), so no DMA is armed against the move.
5. **Rename the package**. For every claim the instance owns, call its
   relocation proc with (old = selector, new = paragraph). The memory does
   not move, so this is a rename, and it is safe for an `MC_DMA` claim too.
   **A claim with no proc refuses the real-mode bracket.** The region itself
   is renamed through `OS88_REGION_MOVABLE`'s proc. The player's is not a
   bare `ret` today: `[vp_self]` holds the region (`VP_OWNB`, §98.3.18.16).
   XMEM blocks are not renamed: the module translates a token through
   `mx_tab`, which is in `.lowbss` (conventional) and is frozen while
   nothing runs.
6. **Swap the API table** at `KERNEL_SEG:0x200`. This is the table LOADALL
   already borrows, so it is writable and in conventional memory. Bank the
   table into the module and write a real-mode table:
   * the §53.7 whitelist, pointed at real-mode bodies;
   * every other cell `stc` / `retf` with AX = "not in a real-mode bracket".
   This is the whitelist enforced for free. The table is ~0x2D0 bytes (cells
   0x0200-0x04D0), an estimate from `apps/os88api.inc`'s highest cell
   0x04CB.
7. **Drop**:
   * On a 386, clear PE in CR0 and far-jump.
   * On a 286, take `mega_svc_lo.r286`'s reset with a new `[mega_drop]`
     value. `mega_r286` already branches on that byte.
   * Land in real mode with `[k_dsel]` = `KERNEL_SEG`, `lidt` the IVT, A20
     left OPEN, and the PIC still at 20h.
   * IVT 20h: the module's tick. IVT 21h: the BIOS's keyboard handler, as
     copied. IVT 24h and 74h: `mou_isr`, which is bimodal already. The
     SB's line: the option ROM's handler where there is one, and its
     software vector (0Dh or 0Fh) to the low copy's `sbl_isr`; otherwise
     IVT 25h or 27h straight to `sbl_isr`. The disks' lines: the BIOS's.
   * Call the entry proc far, at the region's paragraph, through its
     dispatcher, with DS = CS = that paragraph, ES = `KERNEL_SEG`, SI = the
     window, and `OSAPI_CPU_INFO` answering `CPU_F_PM` clear.

**During the bracket**, the module's tick does `sch_isr`'s rate arm and
nothing else (`kernel/sched.inc:1883`, §53.2.2):

* add the divisor to `[sch_racc]`;
* on a carry, chain the ROM's IRQ0 handler, bump `[ticks]`, and run
  `snd_tick` if it is mode-clean;
* otherwise send its own EOI;
* call the hook under `sch_rhook`'s three skip rules (`sched.inc:595`).

There is no task switch, because there is only one task. Because this
handler is IRQ0 inside the BIOS's `int 13h` as well, **the hook decodes
inside the read, as on kern_big**. `mega_rfclk` and the catch-up after a
reflection are not involved.

**At exit**, in reverse:

* A20 proven open (`mega_a20`'s sequence).
* `lmsw`, then `lgdt`, `lidt`, `lldt`, the data selectors, and `[k_dsel]` =
  `KDATA`.
* `mega_dwake`'s tail: masks, a forced `mega_ivt_sync`, the 8042 command
  byte, and the option ROM's prime.
* The table put back, the package and SOUND.DRV renamed back, SOUND.DRV's
  image copied up, the module's claim freed.
* Then `fsx_restore` as today. Its mode set reflects once, as it does now.

#### 3.1.1 The real-mode service module (ESTIMATES)

It is an on-demand module (§2.8), kern_mega only, and is never resident
while no real-mode bracket runs.

| piece | what | est. bytes |
|---|---|---|
| entry/exit real-mode half | IVT arrangement, entry far call, way back to `lmsw` | 300-400 |
| tick | the rate arm, the ROM chain, the hook call | 150-200 |
| `READ_SEQ` / `READ_AT` | cursor offset to extent to `int 13h` (CHS, or AH=42h where the unit takes it), cut at 64 KB pages (`dsk_runcap`'s rule) and the unit's track or cylinder bound (§18.91.5), with retries | 500-800 |
| `XMEM_COPY` / `_CAPS` | token to physical through `mx_tab`, with `os88la.inc` (286) or `os88ub.inc` (386) assembled in, and A20 probed per call as XMEM.DRV does | 500-700 |
| the API table's bank and its real-mode cells | | ~1,000 (720 of them the bank) |

**What is NOT in the module, and why it need not be**: `.text` bodies that
are mode-clean run as they are. In real mode an `int 10h` goes to the IVT,
which is the BIOS, not to `mega_svc`. Candidates: `fsx.inc` (`.text`
throughout, `fsx_wait`, `fsx_page`, `fsx_mode`), `OSAPI_GET_TICKS`,
`OSAPI_MOUSE`, `OSAPI_VIDEO`, `OSAPI_SET_COLOR`, the font glyphs, and the
snd slots' `.text` half. **Each needs the audit 14.1 answer 18 gave
`mou_isr`**: no selector loaded, no alias, no data above 1MB. The ones that
fail move into the module.

The resident cost in kern_mega is `fsx_run`'s bit, the drop and return in
`.text` or `.mega`, and SOUND.DRV's two verbs: an estimated **250-400 bytes**
(§1: *design for bytes*). kern_big and kern_small take the bit's accept and
ignore, an estimated 0-6 bytes, or they stay byte-identical if the flag
test already masks CL.

#### 3.1.2 What the package does

* **The arm passes `FSXF_REAL` with DX or ES:DI naming the stream**, at the
  one call site (`video.asm:14635`). On a refusal (CF=1, a new reason code),
  it calls again without the bit, which is the protected-mode bracket it has
  today.
* **Inside a real-mode bracket it runs the shipped build's bracket code**:
  `[vp_pm]` reads 0 because `OSAPI_CPU_INFO` says so. A conventional ring,
  the LOADALL or `ub_set` borrows, its own speaker shaper, no `vp_paddr`
  patch, and `vp_fcap` = 1.
* **Its claims must all have procs.** §98.3.19.2 says all but the sound
  ring's `MC_DMA` claim do already, so the ring gains a proc.
* **The ring has to be CONVENTIONAL for a real-mode session.** So the
  session decides before `vp_sstart` claims it: a stream about to play in a
  real-mode bracket never takes §98.3.18.17's ring above 1MB. A switch
  between the two kinds of bracket (F) keeps whichever ring the session
  made.

#### 3.1.3 What can go wrong

* **The 286 has only the reset way out.** It is the reflection's own path,
  taken once per bracket instead of on every read, so the Victory's reset
  quirks are already handled (14.62, 14.64). A bracket-long drop makes them
  *rarer*, not new.
* **A BIOS that shuts A20 inside `int 13h` or `int 15h`.** The way back to
  protected mode must prove A20 open before `lmsw`, as `kd_unpark` does
  (KERN-MEGA-DOS-PLAN 2.5 item 3). Each LOADALL borrow probes it, as
  XMEM.DRV does.
* **A fault inside the bracket is a real-mode fault**: no `kern_mega FAULT`
  line and no `mega_fkill`. A bad record in a real-mode bracket hangs the
  machine where kern_big's would hang it too. It is a parity loss in
  diagnosability and nothing else. `MEGATRAP` does not see it either.
* **Edges across the two mode changes.** No ICW1 is ever issued, so the
  only exposure is the 286 reset path's own BIOS behaviour, which
  `mega_r286`'s mask compare already catches.
* **The extent list is stale if the file changes mid-play.** It cannot:
  nothing runs that could write.
* **SOUND.DRV's state**: a verb the driver gets wrong is silence or a stuck
  card. The Victory has already seen exactly that (§98.3.22.7). Its gate
  must play the card's clock through several brackets (section 4, W4).
* **The prefill before the bracket stays a protected-mode read** (reflected
  on a BIOS disk). It is untimed start latency, not play speed. Moving the
  first fill inside the bracket is a later option (section 6, question 4).

### 3.2 A2: the same bracket over a full real-mode kernel - REFUSED

Assemble the kernel's file layer for real mode, as kern_dos is assembled,
instead of an extent reader. It costs ~33 KB of image (`KD_IMG_KB`) to
serve one sequential stream whose clusters are known before the bracket
starts. It would also need the FAT window and the mount state, both of
which kern_mega keeps in claims that may be above 1MB. The extent reader is
the hibernate stub's proven shape at about 2% of the size.

### 3.3 B: windowed play with the desktop live - DISSOLVED

The owner's correction makes this the same as A. The in-window play is a
same-mode fsx bracket, so A covers both kinds of play. The one play on a
live desktop is Live, which reads no disk and stays in protected mode.

### 3.4 C: the package's whole session in real mode ("real-mode residency") - REFUSED

That means keeping the kernel in real mode whenever the player's window is
open. The desktop, the window manager and every other task are
protected-mode code, so nothing else could run. That is the windowed DOS's
problem, which KERN-MEGA-DOS-PLAN 2.1 refused for the same reason.

**Rule 1 for A**, from this option's failure: the real-mode bracket is
taken only when it pays (section 3.1, step 1), so `vm/286-video`'s
native-disk machine keeps the protected-mode bracket, which is already at
parity.

### 3.5 D: native protected-mode drivers for what is reflected - NOT INSTEAD, MAYBE AS WELL

14.124 had this queued: *"Before building a protected-mode handler for the
card's multiplexer..."*. A protected-mode PicoMEM multiplexer handler would
take the 2.8% of IRQs back, and a PicoMEM disk rung in HDD.DRV would take
the reads (the card's own firmware is in the tree, `tools/picomem/`).

**It is narrower**: it covers one card, while an XT-IDE, SCSI or any other
option ROM's disk still reflects (14.73 reproduced the problem on an
XT-IDE). It also depends on the card's protocol, and the hook is still not
inside the read unless the disk path is interrupt-driven. **A fixes every
ROM-served disk at once**, so D is a later, separate question.

### 3.6 E: park kern_mega and run kern_big for the play - REFUSED

E reuses the DOS trip's park to bring up a kern_big. A session is not
portable between kernels, the park costs ~0.2 s each way plus the sum, and
a bracket toggle (F, a seek) would pay that every time.

### 3.7 How much of the kern_mega arm A deletes (measured lines, estimated split)

**What is measured**: `apps/video/video.asm` has **164 `%if*` PKG_MEGA
blocks**. They hold **1,777 kern_mega-only lines** and 180 shipped-only
lines (the `%else` arms), out of 25,230 lines. One block is 637 lines
(`video.asm:13935`): `vp_rhiq`, `vp_rhkb`, `vp_rhtry`, `vp_rhfit`,
`vp_rhoff`, `vp_rhpat`, `vp_paddr`, `vp_at`/`vp_sub`, `vp_rslot`,
`vp_pmbig`, `vp_lymk`/`vp_plmk`, `vp_bnc`, `vp_rhcp`. That is the ring
above 1MB (§98.3.18.17), the selector arithmetic (MC7), and the bounce.
Beside it: `vp_fmt` 140, `vp_bget` 120, `vp_mfree` 95, `vp_rfree` 94,
`vp_xipq` 51, `vp_sstart` 49, `vp_fill` 41, and so on. Also
`apps/video/vfx.asm` (69 lines, the speaker shaper's part, §98.3.15.2) and
21 `VB_PM` sites in `apps/video/vblk.asm` (§98.3.23.2).

**What goes with A** (an ESTIMATE until W0 classifies every block):

* the ring above 1MB and `vp_paddr` patching (most of the 637);
* the bracket's selector-run reads for a bank in place (§98.3.18.16's bank
  half, `vp_xmk`, `vp_xbread`, `vp_xbup`);
* §98.3.22.6;
* the hook's protected-mode arms;
* `vfx.asm`;
* the bounce;
* the PM tiers glue (§98.3.18.18, where it is protected-mode-only).

That comes to **~1,000-1,250 lines, 55-70%**.

**What stays**:

* `OSAPI_SEG` arithmetic for the session's claims, poster and keeper on the
  desktop;
* Live's reads of its hold through selectors (§98.3.18.16's hold half);
* `vp_rq` diagnostics;
* the header;
* `VB_PM`, if Live plays version 2 block files.

**90% would need** the session's desktop half to be protected-mode-free
too: every claim made inside the bracket and dropped at its end, so that
nothing the player holds on the desktop is a claim at all except Live's.
That is a player redesign and is section 6, question 2.

---

## 4. Recommendation and waves

**Take A.** Every wave verifies on the host (`make`, `make mega`,
`tools/kernsize.py` on all three kernels) and names its rows. The rows run
once, after the last wave, as the Testing rule says. The final pass is the
deduplicated union below, plus `test-full`.

* **W0. The census, which decides every estimate above.** It builds and
  runs nothing that ships.
  1. Classify each of the 164 PKG_MEGA blocks as bracket-only,
     session-on-desktop, or Live.
  2. Walk the shipped player's calls between `vp_main`'s entry and its
     return. That gives the real whitelist this player needs.
  3. Audit each `.text` body it reaches for selector loads, the way 14.1
     answer 18 audited `mou_isr`.
  4. List the instance's claims and which have procs.
  5. List SOUND.DRV's stored segments.
  Output: this file's 3.1.1 and 3.7 tables replaced by measured ones.
* **W1. The drop and return with an empty bracket.** `FSXF_REAL` with an
  entry proc that only loops on `[ticks]` and the hook. Gates:
  * new row `megarmb` (Bochs): hook periods against PIT counts are exact
    (`tests/vidkern.py`'s arithmetic), `[ticks]` and 40:6C agree after,
    the desktop and mouse come back, and the IDT is rebuilt;
  * `megarmb286` (86Box `vm/286-victory`, the reset path);
  * existing `megapiclose` (with `PICLOSE=1`, edges lost on the way out),
    `megaxmove`, `vidkern`.
  Break on purpose: skip the forced `mega_ivt_sync` and the row goes red.
* **W2. The rename and the table.** The package side, plus the API swap.
  Gate: `megarmbref`, a refusal arm for each step 1 reason, a claim with no
  proc, and a non-whitelisted call answering CF=1. Each must fall back to
  the protected-mode bracket and still play. Existing: `vidclose`,
  `vidxipbanktier`.
* **W3. The extent reader and `XMEM_COPY`**. A silent play.
  Gates:
  * `vidplayvga`, `vidvga4`, `vidmodex`, `vidxipbank`, `vidxiphd` and
    `vidpage`, through the real-mode bracket: holds equal to the reference
    decode;
  * a new `vidrmbfrag` (a fragmented file walked to the cap, and refused
    past it);
  * `vidxiphd` on an `HDD=` C: (BIOS rung 0 under QEMU, `TESTHD=`).
  Break on purpose: an extent off by one sector shows as a hold mismatch.
* **W4. SOUND.DRV low.** Gates:
  * existing `vidsound` (86Box, SB2.0 the clock, 1,800 frames, capture
    byte-exact), `vidxipsnd`, `vidsnd`;
  * a new `vidrmbswap`: F toggles the bracket five times mid-play with the
    card's clock exact;
  * `pmbox` / `pmbox2` with the PicoMEM's own firmware: its multiplexer
    served natively in the bracket, and `MEGADIAG`'s IRQ count at 0 inside
    it.
* **W5. The player.** The arm takes the real-mode bracket and deletes what
  W0 classified as bracket-only. `t_megapkg` must still pass (fast tier).
  Gates: the megaport `vid*` rows (`vidvga4`, `vidmodex`, `vidplayvga`,
  `vidvga8`, `vidresidentvga`, `vidlivevga`, `vidpage`, `vidfskeysvga4`,
  `vidclose`, `vidwin`, `vidpreview`, `vidsound`, `vidcard`) and the
  `vidxip*` family. `vidlivevga` proves Live untouched.
* **W6. Parity, on the Victory** (field, docs/FIELD-MACHINES.md). Send
  `make VPDIAG=time` and `make megadiag` builds of both kernels' players.
  * **The measurement**: Catch My Heart and Sonic 2, the owner's
    kern_big-encoded files, played on kern_big and on kern_mega with the
    real-mode bracket. Profiles `VPPROFn.DAT`, read by
    `tools/os88vfit.py FILE.V88 VPPROFn.DAT --reads`.
  * **Parity**:
    * the bank runs dry no earlier than kern_big's (Catch 1312, Sonic 733),
      or not at all;
    * the frames behind median is 0, as kern_big's is;
    * the reads' rate is within 2% of kern_big's;
    * the `MEGADIAG` service and IRQ reflections inside the bracket are 0
      (the trailer's `vp_rq` words);
    * the share in reads and in drawing OVERLAPS as on kern_big, where
      14.124 shows them adding.
  * Then re-take `mega_disk` from those plays. At 1.00, `--kernel mega`
    keeps its meaning and changes nothing, and no second encode is ever
    needed (the owner's rule).
  * Repeat on `vm/286-victory` with the XT-IDE disk (14.73's reproduction)
    as the in-house twin.

---

## 5. Open questions for the owner

1. **Only when it pays, or always?** The real-mode bracket for every
   streamed play, or (recommended) only on a BIOS-served disk or an option
   ROM's card. Always means one code path, but it gives up rung 1's native
   PIO on machines already at parity.
2. **Is 55-70% of the arm enough**, or should the session's desktop half be
   redesigned so the player holds no claim on the desktop (section 3.7's
   route to 90%)?
3. **A real-mode fault inside the bracket hangs without a `kern_mega FAULT`
   line.** That is kern_big's behaviour. Acceptable?
4. **The first fill.** Leave it in protected mode, which costs start
   latency only, or take it inside the bracket too?
5. **Other fsx programs.** `FSXF_REAL` is a general bracket flag. Open it to
   other packages now (games with a fullscreen disk loader), or keep it to
   the Video Player until the field says it holds?

---

## 6. What this plan could not determine

* Which kern_mega `.text` bodies on the bracket's whitelist are mode-clean.
  That is W0's audit. Each one that is not moves into the module and adds
  to 3.1.1.
* Whether the PicoMEM's option ROM IRQ handler behaves identically with the
  PIC based at 20h for a whole play. The reflections already run that way,
  one call at a time, so it is likely.
* The true reset cost on the Victory: 412 µs, 1.2 ms and 3.3 ms are all
  quoted (section 1). It does not decide anything here, being paid once a
  bracket.
* Whether Live needs `VB_PM` (version 2 block files under Live), which
  decides whether `vblk.asm`'s protected-mode assembly survives.
* Whether `apps/os88xgap.inc`'s placement guess, which reads a token's low
  bits as physical (§50.6.10), needs `mx_tophys` once the bank is read in
  real mode. Correctness is unaffected either way.
