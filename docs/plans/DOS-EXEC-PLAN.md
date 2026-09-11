# DOS-EXEC-PLAN.md — running DOS `.COM` and `.EXE` programs

**STATUS: INVESTIGATION, with a first round of owner decisions folded in.
Nothing here is BUILT, and every size in it is an ESTIMATE unless the line
says MEASURED.** The three heap figures in §2.2 are measured; every byte count
for code that does not exist yet is a guess against a comparable that does.
**§12 carries the decisions taken and the questions still open**, so a reader
who wants to know what is settled should start there rather than infer it.

The ask: double-click `FOO.COM` or `FOO.EXE` in a Disk window and have it
run. Fullscreen is acceptable. The capability lives on disk until it is
wanted. A later phase carries our own drivers through to the DOS program —
mouse, hard disk, Sound Blaster, packet driver, and one day a redirector for
the RAM disk and the `OS88NET` volumes.

---

## 0. The verdict, before the detail

**It is feasible, it is smaller than it looks, and the reason is that this
machine is already an 8086 running real mode.** There is no CPU to emulate.
A DOS `.COM` is machine code for the processor we are standing on; "running"
it is setting up the memory it expects, pointing `INT 21h` at code of ours,
and doing a far jump. RunCPM (SPEC.md 74) had to interpret a Z80 to do the
equivalent; we do not.

The corollary is the same one a real XT lives with: **a program built for a
286 or a 386 will not run on a 4.77MHz 8088**, here or anywhere, and a great
deal of DOS software from 1990 onward is. This capability is worth what the
1981–88 catalogue is worth, which is most of what anyone wants it for; it is
not a route to running later software on the target machine.

Four findings shape everything below.

1. **The memory is there, and it is in the right place.** MEASURED on a
   640KB machine: **`OSAPI_MEM_AVAIL` answers 523 KB** to a package that has
   just been loaded — that call already counts purgeable caches as free and
   already includes what a compaction would recover, so it is the same
   question `mem_claim` answers and a claim of it will be served (§2.3.1).
   The free run is contiguous and **ends exactly at the top of conventional
   memory**, and a Disk window costs it nothing, because every claim the file
   manager makes is at the bottom of the heap. That is about what a 512KB PC
   running DOS 3.3 gave a program: a realistic DOS machine, not a token one.

2. **The containment answer is "exactly as contained as DOS itself, and no
   more."** An 8086 has no MMU. What we can do — and it is most of what is
   worth doing — is make the DOS program's picture of the machine *true*:
   give it a run whose top really is the top of something, and patch the one
   BIOS word every well-behaved program derives "how much memory is there"
   from. A program that respects its PSP allocation is contained by
   arithmetic. A program that scribbles at a hardcoded address is not, and
   on real DOS it was not either.

3. **The right home is a PACKAGE, not a kernel module.** A module's *data*
   is resident in `.text` (SPEC.md 2.6, 2.8) — the exact thing we are trying
   not to spend. A `.o88` package costs **zero resident bytes**, is on disk
   until double-clicked, gets its own segment, and the file-type association
   mechanism that launches it already exists and needs no kernel change
   (SPEC.md 54.5). The kernel cost of wave 1 is plausibly **nil**.

4. **The gap is file handles.** os8088's file API is whole-file and
   name-based — there is no open/close/seek/write-at-offset anywhere in it
   (SPEC.md 18.4.4 is the closest, and it is cluster-aligned and stateless).
   `INT 21h` `3Dh/3Eh/3Fh/40h/42h` are the functions every DOS program past
   1983 uses. **This is the single largest piece of work in the project**,
   and it is the piece that has to be written rather than mapped.

---

## 1. What "run a DOS program" decomposes into

Seven separable problems. They are listed in the order of how much work they
are, largest first, because that ordering is not the obvious one.

| # | problem | who provides it today | work |
|---|---|---|---|
| 1 | `INT 21h` file handles — open/close/read/write/seek | **nobody** | large |
| 2 | `INT 21h` everything else — ~50 functions | nobody | medium |
| 3 | Program load — `.COM` image, `.EXE` header + relocations, PSP, environment | nobody | small |
| 4 | Memory — an arena, an MCB chain, `48h/49h/4Ah` | the heap (SPEC.md 50) | small |
| 5 | The machine — screen, keyboard, timer, exclusive use | **fsx (SPEC.md 53)** | ~nil |
| 6 | Vector and hardware save/restore around the session | nobody | small |
| 7 | Launching it from a double-click | **assoc (SPEC.md 54)** | ~nil |

Items 5 and 7 are free, and they are the two that would have been the
frightening ones in a system that did not already have them.

---

## 2. Memory — the question that decides the design

### 2.1 How a DOS program knows what memory it has

Four mechanisms, and a DOS layer has to answer all four because different
programs use different ones. In rough order of how well-behaved they are:

1. **The PSP's word at offset `02h`** — "segment of the first byte beyond
   the memory allocated to this program". `.COM` programs that resize
   themselves read it; so does almost every self-respecting `.EXE`.
2. **`INT 21h AH=4Ah` (resize) then `AH=48h` (allocate)** — the documented
   way to get more. `48h` with `BX=FFFFh` deliberately fails and returns
   the largest available block in `BX`, which is how a program asks "how
   much is there". **This is the mechanism we control completely**, and the
   one a well-written program uses.
3. **`INT 12h`, or the BIOS data word at `0040:0013`** — "conventional
   memory in KB". Games and demos use it far more than they should. It is
   one word, we can change it, and see §2.3.
4. **The MCB chain**, reached through the undocumented `INT 21h AH=52h`
   (List of Lists; the word two bytes before the returned pointer is the
   first MCB segment). Memory-mapping utilities and some installers walk
   it. We build the chain, so we decide what they see.

An `.EXE` additionally declares `e_minalloc` and `e_maxalloc` in its header.
`maxalloc` is `FFFFh` in almost every real file, which means "give me
everything", and the DOS loader gives it everything and lets the program
give the surplus back with `4Ah`.

### 2.2 What our heap actually looks like — MEASURED

MartyPC, `os8088_5150`-class 640KB machine, `build/os8088-360.img` with
`build/apps360.img` in B:, build 186, `kern_big`. Read out of `mem_tab`
(SPEC.md 50.2, with `MC_SIZE` 10 per SPEC.md 66.2) and `mem_base`/`mem_top`:

```
heap                    0x1B20 .. 0xA000   =  531.5 KB

bare desktop            one claim, 63.0 KB at 0x2000 (purgeable read-ahead)
                        LARGEST FREE RUN   449.0 KB at 0x2FC0..0xA000
                        ...and it ENDS AT mem_top

B: Disk window open     four claims, ALL of them at 0x1B20..0x2FC0
                        LARGEST FREE RUN   449.0 KB at 0x2FC0..0xA000
                        ...and it STILL ends at mem_top

+ Paint running         ten claims; Paint's REGION is 33.0 KB at 0x97C0
                        LARGEST FREE RUN   390.0 KB at 0x3640
                        ...and the run ending at mem_top is 0.0 KB
```

**These are a HOST-SIDE WALK of `mem_tab` with the purgeable claim counted as
occupied — the at-rest picture, and NOT what a claimant can have.** The figure
a package is actually told is `OSAPI_MEM_AVAIL`'s, which counts caches as free
and includes what a compaction would recover: **523 KB**, measured in-guest on
this same machine (§2.3.1). Read the table below for where the free run
*sits*; read §2.3.1 for how big a claim may be.

Three things fall out of that table and each one matters.

- **It is a lot of DOS machine** — 449 KB at rest, **523 KB deliverable**.
  DOS 3.3 on a 640KB PC left a program about 580KB; on the 512KB machines
  most of this software was written for, about 430KB. We are in that range
  without trying, at either figure.
- **A Disk window costs the DOS program nothing**, because the file
  manager's claims are all bottom-up. The state you are in when you
  double-click is the good state.
- **A running package sits at the TOP.** A region is claimed top-down
  (SPEC.md 50.3), so the DOS runner's own image is the highest thing in the
  heap and the free run no longer reaches `mem_top`. That is the one fact
  the design has to be built around, and §2.3 is how.

The 63KB purgeable claim is the disk read-ahead and is `MEM_PG_HIGH`; the
kernel will shed it under pressure, which merges the low fragment and gives
**531.5 KB contiguous**. Not something to design against, but it is there.

### 2.3 Giving DOS a run, and whether it stays in it

The arena: **one `OSAPI_MEM_CLAIM_HI` of N KB**, so it lands as high as the
runner's own region allows, **with N taken from `OSAPI_MEM_AVAIL` and nothing
else** (§2.3.1). With a ~16KB runner region at the top, the run sits at
roughly `0x2FC0..0x9C00`.

Inside it we build a DOS machine:

```
  base+0000   MCB 'M'  owner = PSP     ->  environment block
  base+....   MCB 'M'  owner = PSP     ->  PSP (256 bytes) + program image
  base+....   MCB 'Z'  owner = 0       ->  the rest, free
                                            ^ 'Z' is the end of the chain
```

- `PSP:0002` = the paragraph past the program's block. Mechanism 1 answered.
- `48h/4Ah/49h` walk *our* chain and nothing else. Mechanism 2 answered, and
  a `48h BX=FFFFh` probe reports our largest free block rather than the
  machine's.
- `AH=52h` returns a List-of-Lists stub of ours whose `[-2]` word names our
  first MCB. Mechanism 4 answered.
- **`0040:0013` is patched to `(top of the run) / 1024` for the duration of
  the session and restored at the end.** Mechanism 3 answered. This is
  verified safe: `int 0x12` appears **exactly twice in the whole tree** —
  `mem_init_x`, which runs once at boot, and the Task Manager's display,
  which cannot run inside a bracket because everything else is frozen
  (SPEC.md 53.2).

**What that buys.** A program that uses any of the four mechanisms is
contained by arithmetic, with no hardware help and no per-access checking.
Its picture of the machine is internally consistent: memory below its PSP is
"DOS and its drivers" (really our kernel and the low heap claims), memory
above its block's end is "not there".

**What it does not buy.** Nothing stops a program doing `mov ax,0x8000 / mov
es,ax / stosw`. On an 8086 there is no mechanism that could. The honest
statement is that **our exposure is DOS's own exposure** — DOS had no
protection either, and every program that ran on it ran under exactly this
contract. The difference is consequence, not likelihood: a DOS machine that
gets scribbled on is rebooted, and ours takes unsaved documents with it.
That is a product decision (a warning on first run, or a "close your work
first" note) rather than an engineering one.

**The one place we are worse than DOS**, and it is worth saying: DOS loads
programs *low*, so "everything above me" is the program's own. We load high,
so a program that assumes it owns up to `0x9FFF` reaches over our runner.
The patched `0040:0013` fixes the programs that ask; it cannot fix the ones
that assume. Two mitigations exist if this turns out to bite, neither needed
for a first wave:

- **Load packages LOW instead.** Top-down regions are a workaround from
  before regions could be compacted, kept to hold the immovable thing out of
  the movable thing's way — and SPEC.md 50.3's own door says so in as many
  words, having been rewritten once already when §66.6.1 refuted its original
  justification. With regions movable, that asymmetry has mostly stopped
  earning its keep, and turning it round would put every os8088 claim below
  the DOS program and leave nothing but video memory above it. **That is a
  heap change and not a DOS change**, it touches every package in the tree,
  and whether it is worth taking depends entirely on a number nobody has yet:
  how many real DOS programs ignore what we tell them. **Not wave 1**, by
  decision — wave 1 is how the number gets measured.
- on a 386, V86 mode gives real trapping. Out of scope: the target machine
  is a 4.77MHz 8088 and `OSAPI_CPU_INFO` (SPEC.md 60) would gate it to
  machines this project does not calibrate against.

#### 2.3.1 Sizing the arena — `OSAPI_MEM_AVAIL`, and nothing else

**One call answers the whole question, and an earlier revision of this
document got it exactly backwards.** It claimed `OSAPI_MEM_AVAIL` reports the
run *before* any shed, and went on to propose that the runner walk
`OSAPI_CLAIM_SNAPSHOT` itself to work out the post-shed figure and then probe
for it. **All of that is wrong and none of it is needed.** The correction is
recorded here rather than quietly deleted, because it is a plausible mistake
that this project has already made once at a higher cost than a paragraph.

What `mem_avail_x` actually does, read in `kernel/memory.inc`:

- it enters at `MEM_LVL_TOP` — *"an ordinary claim's rank: **every cache
  counts as free, because `mem_claim` sheds them all**"*, in the routine's
  own first comment;
- its largest-run answer is **`mem_cp_plan`'s** — the run a **compaction**
  would leave, with those caches dissolved (on `kern_small`, which has no
  compactor, it is `mem_bigrun` over the same shed);
- and its total subtracts a claim only when that claim outranks the caller.

So **`OSAPI_MEM_AVAIL` already answers the same question `mem_claim` answers**.
A claim of the figure it returns will be served. SPEC.md 50.6.3 owns this and
says so in as many words, and it carries the history: `mem_avail` *did* report
the at-rest number once, on the reasoning that under-reporting was the
conservative direction — and that reasoning is *"exactly backwards ... every
consumer sizes itself DOWN from this number"*, so under-reporting is a feature
silently lost rather than a safe error. SPEC.md 66.10.3 is the other half, and
it is the one that put compaction into the answer.

**Measured on this build rather than argued**, driving `tests/heapfrag`
(`tests/heapcheck.py`) on the 640KB MartyPC machine — the same one §2.2 was
taken on, and the same situation the DOS runner is in, a loaded package asking
what it may have:

```
host-side walk of mem_tab, purgeable counted as occupied   449 KB
OSAPI_MEM_AVAIL, asked from inside the guest               523 KB   <- L0
```

**74 KB of difference, and the larger number is the true one.** §2.2's 449 is
this document's own naive walk and is the AT-REST picture; it is in that table
because it shows where the free run *sits*, not how big a claim can be.

Three consequences for the design, and the first is a rule rather than a
detail:

1. **The runner does not walk the claim table, and no package should.** The
   shed, the compaction and the ranking are the allocator's business, and a
   package that "allows for" them is subtracting what has already been added.
   `OSAPI_CLAIM_SNAPSHOT` exists for the Task Manager to *display* the heap,
   not for a package to *reason* about it.
2. **There is no probing.** Ask `OSAPI_MEM_AVAIL`, claim what it said. The
   compact-shed-retry loop inside `mem_claim` (SPEC.md 66.4, 50.6.2) is what
   makes that claim succeed, and it is the same walk that produced the figure.
3. **"Give the DOS program the maximum" is therefore two instructions.** No
   new slot, no user-facing choice, no `Give this program all the memory`
   check box — which was on the table and is not needed. An `.EXE` whose
   header carries a bounded `maxalloc` can still be given exactly what it
   asked for and the caches left alone; a `.COM`, and the `maxalloc = FFFFh`
   that almost every real `.EXE` carries, get the figure.

### 2.4 What about XMS and EMS

`XMEM.DRV` (SPEC.md 41) already manages memory above 1MB on a 286+.
Publishing it as an XMS driver (`INT 2Fh AX=4310h` → an entry point) is a
small, well-specified job and would let a DOS program that wants XMS find
some. **Not wave 1**, and worth noting it is `kern_big`'s alone. EMS is a
different thing entirely — it wants a page frame and hardware or a 386 — and
should be refused rather than faked.

---

## 3. Where the code lives

Three candidate homes. The table is the argument.

| | resident cost | own segment | own data | launched by |
|---|---|---|---|---|
| kernel module (SPEC.md 2.8) | **its data, in `.text`** | no — `COLD_SEG`, `DS = KERNEL_SEG` | **no** | a kernel thunk |
| driver (SPEC.md 51) | image only while attached | yes | yes | `SYSTEM.CFG` or a mount |
| **package (SPEC.md 20)** | **none** | yes | yes | **a double-click** |

**A package wins on every column.** The decisive one is the second row of
the first column: SPEC.md 2.8 says in as many words that a module's data
"stays in `.text`, reached through DS exactly as cold code's data is", and
`os88ovlchk` enforces "no data in `.cold`". A DOS layer's tables — the
handle table, the PSP scratch, the MCB cursor, the DTA, the vector save area
— are exactly the kind of data that would land resident. That is the
opposite of the brief.

A package also gets `APP_MAX_SIZE` = **60KB** of image + bss (MEASURED from
the SDK's own `equ`), against ~11KB for `ETHER.DRV` — a complete NE2000 plus
a TCP/IP stack — and ~22KB for Paint. A DOS shim is comfortably inside it.

So: **`DOSBOX.O88`** (name to be decided), in `apps/dosbox/`, shipping on the
apps floppy, declaring `COM` and `EXE` in its header's association block.
Zero kernel bytes for wave 1 is the target, and nothing found in this
investigation says it cannot be met.

The one thing a package does *not* get is the kernel's internal disk
routines — `dsk_next_clus_x`, `dskw_alloc`, `dsk_rd1_x` and the rest of the
cluster-level layer that §6.3 wants. That is the trade, and §6.3 is where it
is paid.

---

## 4. The bracket — fsx already does the hard part

`OSAPI_FSX_RUN` (SPEC.md 53.1) is very nearly purpose-built for this:

- **Multitasking is suspended** by a whitelist rather than `sch_lock`, so the
  BIOS tick chain, `sch_account` and `TF_SERVICE` driver workers keep running
  while every other instance's tasks freeze (SPEC.md 53.2).
- **The app owns the video mode** — nine of them across the three adapters
  (SPEC.md 53.4).
- **It runs on the UI task**, which is the one context allowed `int 16h`
  (SPEC.md 7), so the DOS program's keyboard just works.
- **The file API is legal mid-bracket**, which is what lets `INT 21h` reach
  the disk at all.
- **The gfx lock is held throughout**, so the mouse cursor cannot appear over
  the DOS program's screen.
- **The restore is one ordered path** (SPEC.md 53.6): mode back, BIOS key
  buffer drained, event queue drained, desktop repainted.
- Entry **silences every other instance's sound** (SPEC.md 53.3), which is
  exactly the "what do we silence" question for the audio half.

Four notes that are specific to this use and are not obvious from reading
SPEC.md 53:

1. **The runner must call `OSAPI_FSX_MODE` at least once**, even if only for
   `FSXM_TEXT`. `fsx_restore` skips `vid_setmode` when `[fsx_cur]` is still
   `0xFF` — verified in `kernel/fsx.inc` — and a DOS program will have set
   its own mode behind our back through the ROM's `int 10h`. Without our
   own mode call the desktop comes back into whatever mode the program left.
2. **The DOS program runs on its own stack**, `SS:SP` inside its own block,
   exactly as under DOS. Task 0's stack (`STK0_SIZE` = **512**, MEASURED)
   carries only the runner's frames up to the far jump, so the bracket adds
   no depth pressure.
3. **`FSXF_KEEPWORKER` is not wanted.** The runner has no feeder task.
4. **An app that hangs in the bracket hangs the machine** — SPEC.md 53.1
   says so, and it is documented rather than defended. A DOS program that
   hangs will hang os8088. There is no watchdog that could safely break in,
   because breaking in means restoring a machine mid-mutation. **A "hung
   program" escape is an open question, not a solved one** (§12).

---

## 5. The interrupt and machine-state ledger

What the kernel owns, verified by grepping every IVT write in `kernel/`:

| vector | owner | what it does | if DOS takes it |
|---|---|---|---|
| `08h` | `sch_isr` | the scheduler; **chains the ROM** | scheduler stops; sound worker starves; BIOS tick stops. Restore on exit. |
| `09h` | `kbm_isr` | **peeks port 60h and chains the ROM** | the BIOS buffer still fills either way; `int 16h` keeps working |
| `0Bh`/`0Ch` | `mou_isr` | the serial mouse, whichever COM the port is on | mouse dies for the session. Restore on exit. |
| `74h` | `mou_p2_isr` | the PS/2 aux port, on machines that have one (SPEC.md 9.9) | same |
| a discovered IRQ | `sbl_isr`, in `SOUND.DRV` | Sound Blaster DMA completion | a live stream dies |

That is the **whole** list. Nothing else in the tree installs a vector.

The `09h` row is the happy surprise: our keyboard hook is a peek-and-chain
that leaves the ROM's handler and the ROM's buffer intact, so a DOS program
polling `int 16h` needs nothing from us at all.

**The save/restore discipline**, and the answer to "do we need to?" is yes,
all of it, because DOS programs hook vectors as a matter of routine and TSR
installers never unhook:

- **Save the whole IVT** — 1KB, one `rep movsw`, restore it the same way at
  exit. Cheaper in both bytes and thought than a list of vectors to
  remember, and it is correct for vectors we do not know about (`INT 1Ch`,
  `1Bh`, `23h`, `24h`, the ROM's `1Eh` diskette table pointer, and every
  vector a TSR the program loads might take). **It must go in the runner's
  own bss and NOT in the arena** — the arena is the DOS program's to
  scribble on, and a save area the program can corrupt is worse than no save
  area, because it fails at restore time when there is nothing left to do
  about it. 1KB of the package's 60KB budget.
- **Save the whole BDA and restore a NAMED LIST out of it.** §5.1 is that
  list. It is settled rather than open, and it is short: 40 bytes restored
  out of 256 saved, four bytes zeroed, and everything else deliberately
  left as the DOS program left it.
- **PIT channel 0.** A DOS program that wants a fast timer reprograms it,
  and the scheduler's quantum goes with it. `sch_fast_on`/`sch_fast_off`
  already exist for exactly this (SPEC.md 53.2) and `sched_unhook` already
  knows how to put channel 0 back to mode 3 divisor 65536. Restoring it is
  three `out`s we already have code for.
- **The 8259 mask.** A program that masks IRQs and does not restore them
  leaves us with no timer. Save `0x21` and `0xA1`, restore both.
- **The video mode**, via the `fsx_mode` note in §4.
- **Nothing about the disk**, at the hardware level — see §7.

### 5.1 The BDA, and which of it comes back

**The BIOS Data Area is segment `0040`** — 256 bytes at linear `0x400`, written
by the ROM at POST and maintained by the ROM's own handlers for the whole life
of the machine. It is where the BIOS keeps the things it has to remember
between calls: how much memory the machine has, which video mode is set, where
the keyboard buffer is and how full, whether the floppy motor is spinning, how
many ticks since midnight. `INT 12h` is nothing but a `mov ax, [0040:0013]`.
A DOS program can write to any of it, and plenty do.

**What os8088 itself touches is a short list**, and it decides most of this
section. Grepped exhaustively for a load of segment `0040` across `kernel/`
and `drivers/` — **seven fields, nine sites**:

| field | site | what it does |
|---|---|---|
| `40:08`..`0F` LPT port base table | `lplink.inc` — `NET.DRV`'s port scan | reads it to FIND the parallel port |
| `40:10` equipment word | `vid_cga_equip` (`viddet.inc`), `vidsel.inc` | **WRITES** bits 5:4 to say which display os8088 picked |
| `40:17` keyboard flags 1 | `kbm_slock` and `kbm_isr`'s keypad-5 hatch (`mouse.inc`) | tests ScrollLock, and NumLock |
| `40:1A`/`40:1C` kbd buffer head/tail | `kbd_ovflow` (`mouse.inc`) | **every `int 09h`** — reads both, writes the tail |
| `40:3F` motor status, `40:40` motor countdown | `dsk_here_ok` and **`dsk_fdd_probe`** (`disk.inc`) | which floppy motors are spinning |
| `40:65` CGA mode-select shadow | `vid_bk` (`vidsel.inc`) | read-modify-write, to blank and unblank |
| `40:6C` tick count | `spl_clock` (`splash.inc`), `pm_ticks` (`SOUND.DRV`) | the wall clock |

Everything else in the 256 bytes, this system never looks at. **Two of those
rows change a verdict below from what it would otherwise have been**, and both
change it towards LEAVE rather than RESTORE — see `40:3F` and `40:6C`.

**The rule that generates the list**, and it is one sentence: *restore a field
if and only if the kernel reads it AND its pre-session value is still true;
zero a field whose honest value is "nothing is held"; leave everything else,
because the machine really did change.*

#### RESTORE — 40 bytes in seven spans

```
40:00  16  COM1-4 and LPT1-4 port base addresses
40:10   2  equipment word
40:13   2  conventional memory size in KB
40:1A   4  keyboard buffer head and tail pointers
40:72   2  soft-reset flag
40:80   4  keyboard buffer start and end offsets
40:98  10  INT 15h user-wait flag pointer, count and flag
```

- **`40:13`** is the one we patched ourselves (§2.3). Not restoring it leaves
  the machine reporting a small size for the rest of the session — the Task
  Manager's own display reads `int 12h`, and it is the second of the only two
  `int 12h` sites in the tree.
- **`40:80`/`40:82` is the sharpest entry in the whole ledger**, and it is not
  obvious. A DOS TSR that *enlarges the keyboard buffer* does it by repointing
  these two words at a bigger buffer **in its own memory**. When the bracket
  ends and the arena is freed, the ROM's `int 09h` keeps writing keystrokes
  into an address that is now whatever claimed that memory next — silent heap
  corruption that first shows minutes later, on an unrelated keystroke, in an
  unrelated program. Restore them and the ROM writes into `40:1E` again.
  Restore what was THERE, not the constants: `kernel/mouse.inc` records that
  these two words **do not exist on the earliest 5150 ROM**, which is exactly
  why `kbd_ovflow` uses literal `KBD_BUFB`/`KBD_BUFE` and not these.
- **`40:98`..`40:A0` is the same trap in a different field.** `INT 15h AH=83h`
  arms a wait by handing the ROM a far pointer to a flag byte to set when the
  interval expires. A program that arms one and dies leaves the ROM's tick
  handler writing into the arena after we have freed it.
- **`40:1A`/`40:1C`.** `fsx_restore` already drains the buffer through
  `int 16h`, so head and tail agree by then. What the drain cannot fix is a
  program that left them pointing **outside** `40:1E..40:3D`: `kbd_ovflow`'s
  range check then takes its `.out` arm and the overrun guard of SPEC.md 9.8
  is dead for the rest of the session, silently. Restore them with the pair
  above — the keyboard goes back as one thing or not at all.
- **`40:10`.** The kernel *writes* this to match the adapter it chose, so a
  program that rewrites it leaves the kernel's own statement about the machine
  untrue.
- **`40:72`.** `1234h` here means "warm boot, skip POST". A program that set
  it changes what the next `int 19h` does, and `ui_cmd_reboot` is an `int 19h`.
- **`40:00`..`40:0F` has a real reader and it is not the obvious one.** The
  mouse addresses its UART by port number, so the COM half (`40:00`..`40:07`)
  is in for completeness only. **The LPT half is not**: `NET.DRV`'s candidate
  scan walks `40:08`..`40:0F` to find the parallel port at all
  (`drivers/net/lplink.inc`), so a DOS program that blanks an entry — which a
  printer TSR reasonably might — leaves the parallel link with nothing to
  attach to, and the failure is "there is no cable" rather than anything that
  points here.

#### ZERO — 4 bytes, because restoring them would be worse

```
40:17  1  keyboard flags 1 (shift/Ctrl/Alt, and the lock states)
40:18  1  keyboard flags 2
40:96  1  keyboard flags 3 (101-key)
40:97  1  keyboard flags 4 (LED state)
```

These say which keys are **held right now**. The pre-session value is not the
truth and neither is the program's — the truth is whatever the user's hands are
doing when the desktop comes back, and the honest encoding of that is *nothing
is held*. Restoring the old bytes can leave a phantom Ctrl or Alt down, which
makes every menu and every keystroke behave oddly until the user presses and
releases that key by accident. A stuck ScrollLock silently disables the
keypad-5 mouse-button hatch, since that is the bit `kbm_isr` tests. The BIOS
re-asserts the LEDs on the next keystroke.

#### LEAVE — everything else, and each for a stated reason

- **`40:6C` (dword) and `40:70`** — ticks since midnight, and the midnight
  rollover flag. **Time passed.** Our `sch_isr` chains the ROM handler, so this
  counted up through the whole session exactly as it should have; putting the
  old value back would set the machine's clock back by the length of the DOS
  program's run, and `int 1Ah` off this counter is rung 0 of the clock ladder
  (SPEC.md 37.90) — the rung a 5150 with no RTC actually uses. It has **two
  live readers in this tree** (`spl_clock`, and `SOUND.DRV`'s `pm_ticks`), and
  both want it CURRENT: this is a field the kernel depends on and must not get
  back, which is why the rule at the top of this section is two clauses and
  not one.
- **`40:3E`..`40:48`** — floppy recalibrate status, motor status, the motor
  timeout counter, last status, and the 765's ST0–ST6. This is *hardware*
  state and the ROM's tick handler counts `40:40` down to turn the motor off.
  **The kernel reads `40:3F` and `40:40` in two places** — `dsk_here_ok`,
  and `dsk_fdd_probe`, whose own comment says "there is no
  readable DOR, so the BIOS's own MOTOR_STATUS is the only place the current
  motor state exists". That makes the LEAVE verdict **stronger** rather than
  weaker: restoring a pre-session motor bitmap would hand the probe a
  statement about which drives are spinning that is not true of the machine,
  and SPEC.md 18.97 retires a drive on what that probe decides.
- **`40:49`..`40:66`** — the entire video block: mode, columns, page size and
  offset, eight cursor positions, cursor shape, active page, CRTC port, and the
  `3x8h`/`3x9h` shadows. **This is the largest block in the BDA and it needs
  nothing from us**, because `fsx_restore` step 1 calls `vid_setmode`, which
  goes through the ROM's `int 10h`, and the ROM rewrites all of it as part of
  setting the mode. Restoring it before that would be overwritten; restoring it
  after would contradict the mode actually set. (`40:65` is in this block and
  is one of the four fields the kernel reads — `vid_bk`'s blank/unblank — and
  it still wants leaving, for the same reason: the mode set is what makes it
  true again.)
- **`40:74`..`40:77`** hard-disk status, drive count and the XT fixed-disk
  control pair — the ROM maintains these and `HDD.DRV`'s rung 0 goes through
  `int 13h` (SPEC.md 52.1), so the ROM's own copy is the one that matters.
- **`40:84`..`40:95`** — EGA/VGA rows, character height, the two video display
  data areas, floppy media control and per-drive media state and current track.
  Video half is `vid_setmode`'s; floppy half is hardware state.
- **`40:78`..`40:7F`** printer and serial timeouts, **`40:A1`..`40:A7`** the
  LAN bytes, **`40:A8`** the video parameter table pointer, **`40:F0`..`40:FF`**
  the inter-application communication area, and **`0050:0000`** the
  print-screen status byte. Nothing here reads any of them.

#### Why save all 256 when only 40 come back

Because the save is what makes the list **auditable** rather than a guess. One
`rep movsw` into the runner's own bss costs 256 bytes and ~1,300 cycles; having
the before-image means a diagnostic can print what the DOS program actually
changed, which is how the next field in the RESTORE column gets found. The
alternative — saving only the seven spans — saves 216 bytes of a 60KB package
and loses the evidence.

---

## 6. `INT 21h` — the actual work

### 6.1 What is free because the ROM is still there

A DOS program spends a lot of its life in the BIOS, not in DOS, and the BIOS
is untouched: `int 10h` video, `int 16h` keyboard, `int 13h` disk, `int 1Ah`
clock, `int 17h` printer, `int 14h` serial. **We provide none of these and
they all work**, which is most of why this project is tractable. It is also
why a graphics-mode game is *easier* than a text-mode utility: the game
talks to the ROM and to the framebuffer, and the utility talks to `INT 21h`.

### 6.2 The shim's own surface

Roughly fifty functions. Grouped by what they cost us:

**Trivial — a few instructions each, no state (≈20 functions).**
`30h` version (report 3.31 or 5.00 — see §12), `25h`/`35h` set/get vector,
`2Ah`–`2Dh` date and time (`OSAPI_GET_TICKS` and the clock, SPEC.md 37
is resident), `19h`/`0Eh` current/select drive (we have volume indices
already, SPEC.md 18.7), `1Ah`/`2Fh` set/get DTA, `33h` break flag,
`62h` get PSP, `50h`/`51h` set/get PSP, `59h` extended error, `0Dh` disk
reset, `54h` verify flag, `38h` country info (a stub).

**Character I/O — `01h`, `02h`, `06h`, `07h`, `08h`, `09h`, `0Ah`, `0Bh`,
`0Ch`.** Under a fullscreen bracket these go straight to `int 10h` TTY and
`int 16h` and are nearly free. They are also the functions a *windowed*
DOS box would have to intercept instead (§10).

**Process control — `00h`, `4Ch`, `31h`, `4Dh`, and `INT 20h`, `INT 27h`.**
Terminate is the interesting one: it has to unwind back to the runner's
saved `SS:SP` and return from the bracket. `INT 22h`/`23h`/`24h` are vectors
we install and the program may replace; `24h` (critical error) needs a real
handler that fails the operation rather than retrying forever.

**Memory — `48h`, `49h`, `4Ah`, `58h`, `52h`.** §2.3. A first-fit walk of
our own MCB chain; a few hundred bytes.

**EXEC — `4Bh`.** A program launching another program. `4B00h` (load and
execute) is genuinely used by installers and by anything that shells out.
It is the loader called recursively with a second PSP, and the memory has to
come from the same arena. **Deferrable**, and `4B01h`/`4B03h` (load without
executing, load overlay) more so — though `4B03h` overlays are how some
large programs are built and refusing it will lose a few titles.

**FCB functions — `0Fh`–`24h`, and `29h` parse filename.** The pre-DOS-2
file interface. Largely dead by 1985, but `29h` is used by programs parsing
their own command tail even when they then use handles, and a few stubborn
titles are FCB-only. **Wave 3 at the earliest**, and possibly never: the
cost is real and the audience is small.

**Directories — `39h`, `3Ah`, `3Bh`, `47h`.** These map almost exactly onto
`OSAPI_FILE_MKDIR`, `OSAPI_FILE_RMDIR`, `OSAPI_FILE_GOTO_Q` and
`OSAPI_FILE_HERE`. Cheap.

**Find first/next — `4Eh`, `4Fh`.** `OSAPI_FILE_FIND` is an ordinal-based
enumeration that fits this well; the work is the DTA format and wildcard
matching, both small.

**...and the handles, which are their own section.**

### 6.3 File handles — the one real gap

`3Dh` open, `3Eh` close, `3Fh` read, `40h` write, `42h` lseek, `45h` dup,
`46h` dup2, `3Ch` create, `5Bh` create-new, `41h` delete, `43h` attributes,
`56h` rename, `57h` file date, `68h` commit.

**os8088 has no file handle anywhere.** The whole published API is by name
and by whole file:

- `OSAPI_FILE_READ` reads an entire file into a buffer you sized.
- `OSAPI_FILE_WRITE` creates or replaces an entire file.
- `OSAPI_FILE_APPEND` appends, and **only at a cluster boundary**.
- `OSAPI_FILE_READ_AT` reads at an offset, and **the offset and the capacity
  must both be whole clusters**, and it **walks the chain from the front on
  every call** because it is deliberately stateless (SPEC.md 18.4.4).

So the shim has to build the handle layer itself. Two ways, and the choice
is the biggest open design question in this document.

**(a) On the published API, in the package.** A handle is a record holding
the name, a file position, and one cluster-sized buffer. `3Fh` for a read
inside the buffer is a `movsw`; a read that crosses a cluster is an
`OSAPI_FILE_READ_AT`. Writes are the problem: there is no write-at-offset in
the API at all, so an in-place update means read-modify-rewrite of the whole
file. That is correct but it is seconds per write on a floppy, and a program
that updates a record at a time (a database, a save-game slot) would be
unusable. **Reads work well; writes work badly.**

- Cost: ESTIMATE ~2–3KB of package code and one cluster buffer per handle.
- Risk: the `READ_AT` chain walk is O(clusters) per call. SPEC.md 18.4.4
  argues that is cheap against the floppy time, and for sequential reading
  it is — but a program seeking backwards in a large file pays it every time.

**(b) With a kernel addition.** A published `OSAPI_FILE_SEEK`/`READ_AT_RAW`/
`WRITE_AT` trio over the cluster layer that `diskw.inc` already has
internally. That makes the DOS side thin and fast, and it is a capability
the whole system lacks and would benefit from — but it is resident kernel
bytes, it needs a design of its own, and it is a much bigger conversation
than a DOS box.

**Recommendation: (a) for wave 1, with writes restricted to
create/append/replace, and the in-place-write case refused honestly** in
SPEC.md 47's sense — a notice naming what the program asked for. Then
measure which real programs that loses, and let that decide whether (b) is
worth a kernel design.

**But (b) is wanted on its own merits, and that changes who should pay for
it.** This is not a DOS-box problem for a DOS box to solve privately: the
whole-file API costs os8088's own programs the same thing, and the sharpest
number on the table is **TANK ATTACK taking 2-4 seconds to load or write a
high-score file of a few bytes**. No amount of buffering inside a DOS shim
fixes that, because the cost is in the layer underneath it. So the honest
framing is that **`INT 21h` is the SECOND customer for a seek/write-at API,
not the first** — and if that API gets designed, the DOS side should be built
on it rather than around it. Wave 1 shipping read-only handles is a
sequencing decision, keeping the DOS work off the critical path of a kernel
design that wants doing for its own reasons; it is not a judgement that
read-modify-rewrite is good enough.

---

## 7. Disk state — what needs saving, and what does not

**At the hardware level, nothing.** The kernel's disk layer is `int 13h`
plus a FAT driver (SPEC.md 18); it holds no controller state across calls,
and `dsk_xfer` raises `[sch_lock]` around each transfer. A DOS program
calling `int 13h` is calling the same ROM we do. The one exception is the
diskette parameter table — SPEC.md 18.92 says the `int 1Eh` table is **ours**
— and the blanket IVT save/restore of §5 covers the pointer.

**At the filesystem level, quite a lot**, and this is a correctness issue
rather than a crash one. The kernel caches three things a DOS program can
invalidate by writing to a disk behind our back:

- the **global mount snapshot** (the directory listing every window reads),
- the per-volume **FAT window** (SPEC.md 18.8), a cache of the allocation
  table,
- the per-window **listing cache** and the icon cache.

If a DOS program writes to A: through `int 13h`, or through our own `INT 21h`
(which goes through the file API and so *does* keep the kernel's own state
straight), the snapshot may be stale. The cure exists and is one call:
**`OSAPI_VOL_MOUNT` on exit**, which re-mounts and re-lists. `[dsk_lstale]`
is the kernel's own name for this debt and `dsk_relist` is what pays it.

Cheapest correct policy: **re-mount every volume the session could have
touched, at bracket exit, unconditionally.** It is a few hundred ms of
floppy per volume against a class of silent corruption, and the user is
coming back from a fullscreen program so a pause is expected.

**The removable-media hazard is real and is already documented**: SPEC.md
18.9.3's batch bracket rests on the argument that a user cannot swap a disk
while the machine is frozen. A DOS session is minutes long and the machine
is *not* frozen from the user's point of view — they can absolutely change
the floppy. The safe answer for wave 1 is that a DOS program reaches disks
through our `INT 21h` and our mount discipline, and that **`int 13h` writes
from a DOS program are out of contract** — allowed, because we cannot stop
them, but the re-mount at exit is what we promise and nothing more.

---

## 8. Launching — the double-click

Already built, and needs **no kernel change**:

1. `DOSBOX.O88` carries an association block in its header declaring the
   extensions `COM` and `EXE` (SPEC.md 54.5 — the block carries extensions
   only, and the program's stem comes from the file it was harvested from,
   which is what makes this work on any disk).
2. `disk_mount` harvests it; `.COM` and `.EXE` files get the runner's icon
   marked as documents (SPEC.md 54.1) — so they *look* runnable in a Disk
   window, which is the whole user-visible half of the ask.
3. Double-click → `assoc_locate` finds `DOSBOX.O88` → `ld_run_name` launches
   it → the new instance reads `OSAPI_ARG_FILE` and learns which file it was
   opened on.
4. It is launched standing in the clicked file's own directory (SPEC.md
   19.2.1), which is also where a DOS program expects to find its data.

Two consequences worth stating.

- **This is `kern_big` only.** SPEC.md 54.0 gates the whole association
  feature out of `kern_small`. That is the right answer anyway: a 128KB
  machine has ~31KB of heap and cannot host a DOS program.
- **A second entry point is wanted**: launching `DOSBOX.O88` directly, with
  no argument, should give a command prompt rather than an error. That is
  where a `COMMAND.COM`-ish shell would live if one is ever wanted — and the
  honest first answer is a file-picker, not a shell, because a shell means
  `4Bh` EXEC, a command parser, batch files, and internal commands.

---

## 9. Phase 2 — carrying our drivers through

The shape of every row here is the same: **we already have the device
working; what is missing is the DOS-facing interface to it.** None of these
needs a device driver to be written or ported. That is worth saying plainly
because the resources named in the brief are all *drivers*, and drivers are
the half we already have.

### 9.1 Mouse — `INT 33h`

**The cheapest and highest-value row.** The kernel's mouse ISR keeps
`mouse_x`/`mouse_y`/`mouse_btn` fresh throughout an fsx bracket — SPEC.md
53.1 states it explicitly, and it is why the pointer stays live. So an
`INT 33h` implementation is a translation layer over variables that are
already being maintained, not a driver.

Functions worth having: `00h` reset/detect, `01h`/`02h` show/hide,
`03h` position and buttons, `04h` set position, `05h`/`06h` press/release
counts, `07h`/`08h` ranges, `0Bh` motion counters, `0Ch` event handler,
`0Fh` mickeys-per-pixel. ESTIMATE **under 1KB**.

**CuteMouse is a reference, not a source.** It is GPL-2 (checked), this tree
is MIT under one licence file, and CONTRIBUTING.md §6 forbids vendored
third-party code. More to the point it is a *driver* — it talks to the
serial port and the 8042 — and we do not need one.

**One real gap.** `mou_apply` consumes the raw deltas into a screen-clamped
position and keeps no mickey accumulator (read in `kernel/mouse.inc`). Two
consequences: function `0Bh` has to be derived from position changes, which
loses motion while the pointer is against a screen edge; and the desktop's
resolution is not the DOS mode's, so everything needs scaling. Absolute
programs (menus, CAD, paint packages) will be fine. Mickey-driven ones
(anything with mouselook) will feel wrong at the edges. **A raw-mickey pair
in the ISR would fix it for an estimated ~10 resident bytes** — the one
kernel change this whole document actively recommends considering, and it
should be costed properly rather than taken on this sentence.

### 9.2 Hard disk

**Rung 0 is already free.** SPEC.md 52.1: a drive the BIOS knows is reached
through `int 13h` 80h/81h, so a DOS program sees it with no work from us at
all.

**Rung 1 is not reachable.** That rung is the IDE task file at 1F0h/170h,
for a drive the BIOS does *not* know, and it is gated on `CPU_286`. There is
no `int 13h` number to offer for it. Giving DOS access to a rung-1 drive
means either providing `INT 21h` file access to it (which the shim does
anyway, through the volume layer — so **a DOS program using `INT 21h` gets
rung-1 drives for free**) or writing an `int 13h` shim over `DSV_BLK`
(SPEC.md 51.8), which is possible and is a wave of its own.

The useful framing: **`INT 21h` covers every volume os8088 can mount,
including driver-backed ones, because the shim goes through the volume
layer** (SPEC.md 18.7 — a volume is an index, and `dsk_xfer` dispatches to
BIOS or driver). `int 13h` covers only what the BIOS knows. Programs that
use files are fine; programs that read raw sectors are not.

### 9.3 Sound Blaster

The hardest row, and the one where the honest answer is likely "don't".

`SOUND.DRV` owns the card: it hooks a discovered IRQ, drives DMA channel 1,
and has a feeding worker (`TF_SERVICE`, which keeps running inside a bracket
by design, SPEC.md 53.2). A DOS program that wants the Sound Blaster wants
to program it *itself* — reset the DSP, set its own IRQ and DMA, own the
card completely.

Two choices, and they are exclusive:

- **Detach.** `sbl_detach` / `sbl_halt` / `sbl_unhook` already exist and put
  "the vector, mask and DSP back as we found them" (their own comment). Call
  the driver's detach before the bracket, re-attach after. The DOS program
  gets a virgin card and a `BLASTER=` environment variable naming its port,
  IRQ and DMA, and everything works exactly as it does under DOS. **This is
  the right answer**, and it is mostly existing code.
- **Virtualise.** Trap the card's ports and translate to our sound layer.
  Not possible on an 8086 — there is no I/O trapping without protected mode.

So: detach for the session, re-attach at exit, and accept that os8088's own
audio is silent while a DOS program runs. Which it would be anyway: SPEC.md
53.3 already silences every other instance at bracket entry.

**"Sound Blaster from scratch" is not needed.** We are not writing a DOS
sound driver; the DOS program brings its own. We are getting out of its way.

### 9.4 Packet driver

**A packet driver is an interface, not a program**, and the brief's framing
is worth correcting: mTCP is a suite of DOS *applications* (FTP, telnet,
IRC, a web server) that **consume** a packet driver. It is GPL and it is the
wrong half. What we would provide is the **Crynwr Packet Driver
Specification** — a published interface, vectors `60h`..`80h`, with a
signature string `PKT DRVR` at offset 3 of the handler so clients can find
it, and about a dozen functions (`driver_info`, `access_type`,
`release_type`, `send_pkt`, `get_address`, `terminate`).

And it is a **very good fit**, for one specific reason: `ETHER.DRV` **hooks
no interrupt vector at all** and polls the NE2000's receive ring (verified in
`drivers/ether/ether.asm`: "DRVV_ATTACH — find a card, and hook NOTHING").
So there is no IRQ to arbitrate and no ISR to hand over. A packet driver
over `ETHER.DRV`'s existing verbs is:

- `send_pkt` → the driver's transmit verb, directly;
- receive → poll the ring from our `INT 08h` path or from the shim's idle
  points, and up-call the client's registered receiver.

The catch is that the client's receiver is called *from* the poll, so the
polling has to happen often enough. Under a bracket we control the loop, so
this is tractable. ESTIMATE **1.5–2.5KB**, and it would make mTCP's own
applications run on os8088 — a very good validation target, and a genuinely
attractive demo.

**Ordering note**: this is only worth doing after the shim's `INT 21h` is
solid, because every mTCP application is a heavy user of file handles.

### 9.5 A DOS redirector for the RAM disk and network volumes

The brief mentions this as "potential ... at some point in the future", and
the investigation turns up something better than expected: **os8088 already
has a redirector interface of its own.** `DRVC_FILE` is a driver class whose
`DSV_FS` points at an `FSV_*` verb table — `FSV_LIST`, `FSV_CHDIR`,
`FSV_STAT`, `FSV_READ`, `FSV_WRITE`, `FSV_APPEND`, `FSV_READAT`,
`FSV_DELETE`, `FSV_RENAME`, `FSV_MKDIR`, `FSV_RMDIR`, `FSV_DFREE`,
`FSV_ENUM`, `FSV_COPY`, `FSV_RMTREE` (`kernel/driver.inc`). The RAM disk
(`drivers/ramdisk/`) and the parallel-link network drive (`drivers/net/`,
SPEC.md 62) both use it.

So there is **no DOS redirector to write**. The shim's `INT 21h` goes
through the volume layer, and the volume layer already dispatches a
`DRVC_FILE` volume to its driver's `FSV_*` verbs. **A DOS program gets the
RAM disk and the network drive as ordinary drive letters, for free, the day
`INT 21h` works.** The ISA-PicoMEM redirectors named in the brief solve a
problem this system solved differently and earlier.

(The one thing that would need the real DOS redirector interface — `INT 2Fh`
`AX=11xx` — is a *third-party* DOS network client wanting to see our
volumes. That is a different and much rarer want, and it should not be
confused with the above.)

---

## 10. What will not work, stated plainly

A section written now so it does not have to be discovered later.

- **A windowed DOS box for arbitrary programs.** A program that does all its
  output through `INT 21h` character functions or `int 10h` TTY **can** be
  rendered into a window, and RunCPM's terminal (SPEC.md 74.2) is the working
  precedent for the rendering half — that is the windowed text mode §11 now
  carries as a named phase. What cannot be made to work is the general case:
  **a DOS program writing directly to `B8000` bypasses every interception
  point**, and most of them do, because that is what made them fast. Making
  *that* work means a shadow buffer at `B8000`, which means the program
  cannot be at its real address, which on an 8086 means no. So the windowed
  mode is a **capability a program either has or has not**, decided the first
  time it writes a character, and the refusal — "this program draws its own
  screen; run it fullscreen" — is a normal path in SPEC.md 47's sense rather
  than a failure.
- **TSRs that survive the session.** `31h` and `INT 27h` can be made to work
  *within* a session, but the IVT restore at exit takes them out. A resident
  DOS program outliving the bracket would mean our vectors staying replaced
  while the GUI runs, which breaks the scheduler and the mouse.
- **Anything needing DOS 5+/6 specifics**, long filenames, or `INT 2Fh`
  services from `COMMAND.COM` (`INT 2Eh`).
- **Programs that reprogram the PIT and do not restore it**, if they also
  crash before terminating. We restore at exit; a program that never reaches
  our exit path never gives us one.
- **Multitasking.** The bracket is exclusive by design. One DOS program at a
  time, and os8088 is frozen behind it.
- **`.EXE`s larger than the arena**, and any program wanting more than
  ~433KB. Not many.

---

## 11. Waves

Sizes are ESTIMATES against measured comparables (`ETHER.DRV` 11,230 bytes
for an NE2000 plus a TCP/IP stack; `HDD.DRV` 5,489; Paint 21,962).

| wave | what | kernel bytes | package bytes (EST) |
|---|---|---|---|
| 1 | `.COM` only. Arena + MCB chain + PSP + environment. fsx bracket, IVT/BDA/PIT/8259 save-restore. Character I/O, process control, memory, date/time, vectors. **Read-only file handles.** Double-click via an association block. | **0** | 6–9 KB |
| 2 | `.EXE` loader — MZ header, relocations, `minalloc`/`maxalloc`. Directory functions, find-first/next, create/replace/append writes, `INT 33h` mouse. | 0 (10 if the mickey pair is taken) | +3–4 KB |
| 3 | Sound Blaster detach/re-attach. `4Bh` EXEC. `INT 12h`/BDA polish. XMS via `XMEM.DRV`. | 0 | +2–3 KB |
| 4 | Packet driver over `ETHER.DRV`. Validation target: mTCP's own applications. | 0 | +1.5–2.5 KB |
| 5 | **Write-at-offset file handles** (§6.3) — on a published kernel seek/write-at trio if that API happens, on read-modify-rewrite if it does not. Ordered here rather than "deferred" because Tank Attack wants it too. | 0 or ~400 | +1–2 KB |
| 6 | **Windowed text mode** (§10) — the `INT 21h`/TTY subset rendered into a real window, RunCPM's terminal (SPEC.md 74.2) being the precedent; a program that writes `B8000` is refused into fullscreen instead. | 0 | +4 KB |
| 7 | **A command interpreter** in that window — the `COMMAND.COM`-shaped half. Needs wave 3's `4Bh` EXEC under it, which is what makes it wave 7 and not wave 6. | 0 | +4–6 KB |
| — | *deferred, needs its own design* | | |
| ? | FCB functions (§6.2) — cost is real, audience is small | 0 | +2 KB |
| ? | DOS 5 rather than 3.31 (§12 q1) — the version byte is free, the functions behind it are not | 0 | ? |

**Wave 1 is the one that decides everything**, and it is worth building as a
throwaway first: a `.COM` that does nothing but `INT 21h AH=09h` (print a
string) and `AH=4Ch` (exit) exercises the arena, the PSP, the bracket, the
vector save/restore and the exit path — every load-bearing piece — in a
program small enough to hand-assemble and read.

### 11.1 What must be decided before the first line of wave 1

Everything architectural is settled (§12). What is left is six things a person
has to choose, and they are listed because each one is cheap to decide now and
expensive to change after code exists.

**1. The package's name.** `DOSBOX` is the obvious one and is the wrong one:
it collides with a well-known *emulator*, and the whole point of this design
is that nothing is emulated — the code runs natively on the processor that is
already there. The stem matters beyond taste, because it is what the
association block names, what `assoc_locate` looks for on every volume, and
what a failure says out loud (`X.O88 - not on this disk`, §54.4.1).
Suggestions, in preference order: **`RUNDOS`**, `DOSRUN`, `PCDOS`. Avoid
`MSDOS` for the obvious reason.

**2. Which disk, and is it a `SYSAPPS` package?** Measured on this tree,
`apps360.img` is at **313 of 354 clusters — 41 spare**, so a 6–9 KB package
compresses into 4–6 of them and fits with room. (CLAUDE.md quotes *"346 of
354"* for this disk, which does not match what this build reports — worth
someone checking which is current before either figure is quoted again.) The open question
is not whether it fits but **where it belongs**: it is arguably infrastructure
rather than an application, which would make it `SYSTEM/` on all four system
disks like `TASKMGR.O88` and `THEWIRE.O88` (§24.3, §92) instead of an
`APPS/` entry. The argument for `SYSTEM/` is that a `.COM` can be sitting on
any floppy and the program that runs it should be on the disk you booted from.
**It is off the small disks either way** — SPEC.md 54.0 gates associations out
of `kern_small`, so a double-click cannot reach it there at all, and that is a
`SMALLOMIT` row with a *requirement* reason rather than a size one (§24.5).

**3. Does it claim `.EXE` in wave 1, when wave 1 cannot run one?** Recommend
**yes**. Claiming it means a double-click gets a refusal that names the reason;
not claiming it means the kernel answers *"Bad package"* (§54.4), which is
true and tells the user nothing. The same argument §54.4.1 already made.

**4. What the window is, and what happens after the program exits.** A bracket
is entered from a window callback (§4), so the package must create a window
before it can take the machine. The decision is what that window is *for*: the
cheap answer is a small one naming the program, which the bracket covers
immediately and which is on screen again the moment the program exits. Strong
recommendation that it **stays open and shows the exit code** — a DOS program
that terminates in a tenth of a second otherwise leaves no trace of why, and
`AH=4Ch`'s return code is the only diagnostic a DOS program is obliged to
give.

**5. `INT 21h AH=47h` (get current directory) cannot be answered truthfully,
and that is a property of the kernel rather than of this design.** `dsk_cwd`
is a **first-cluster word** (`kernel/disk.inc`), and there is no path string
anywhere in the tree — the file manager derives what it shows, and
`OSAPI_FILE_HERE` answers a cluster and a volume index, not a name. So `47h`
can return only `""`, which is the root, which is a lie whenever the program
was launched from a folder — and §19.2.1 launches it standing exactly where
the file was. A program that calls `47h`, builds a path from the answer and
then opens it will fail, and the failure will look like a file error.
Three ways out, and one of them wants deciding before the shim's shape is
fixed: accept `""` and document it; **synthesise the path by walking `..`
entries** at bracket entry (the machinery exists — `dskw_rt_*` walks parents —
and it is one walk per session, not per call); or keep a path string in the
runner as the program `3Bh`-chdirs around, seeded from the walk. The middle
one looks right and is small, but it is work nobody has costed.

**6. The drive-letter map.** Volume indices are 0..3 = A:..D: with C: reserved
for a hard disk (§18.7.4), which matches DOS closely enough that the map is the
identity. What needs saying is what a program asking for a drive we do not have
is told — `AH=0Eh` select-drive and `AH=19h` current-drive both need an answer,
and the honest one is DOS's own invalid-drive behaviour rather than a refusal
of our own invention.

**Two things that look like decisions and are not.** The bracket must call
`OSAPI_FSX_MODE` with `FSXM_TEXT` on entry whatever else it does, or the video
restore is skipped (§4 note 1) — that is a constraint, not a choice. And the
arena is `OSAPI_MEM_AVAIL` and one claim (§2.3.1) — there is no sizing policy
to pick.

---

## 12. Open questions — and the ones now settled

**Settled by the owner, recorded here so the reasoning is not re-derived:**

- **A package, not a module** (§3) — the resident cost was the whole
  objection, and a package has none.
- **Purge and compact for the maximum** (§2.3.1) — and it needs no mechanism
  at all, because `mem_claim` is already a compact-shed-retry loop. No user
  choice, no check box: an `.EXE` with a bounded `maxalloc` gets what it
  asked for and everything else gets the maximum.
- **Load packages low?** Not wave 1 (§2.3). It is a heap change touching every
  package in the tree, and the number that decides it — how many real programs
  ignore what we tell them — is what wave 1 measures.
- **Which BDA bytes come back** (§5.1) — 40 bytes restored in seven spans,
  four zeroed, the rest deliberately left.
- **Write support is not wave 1**, and it is wave 5 rather than "deferred"
  (§6.3, §11).
- **All from scratch**, MIT, with FreeDOS and CuteMouse read when a return
  value is in doubt (§13).
- **Windowed text mode and a command interpreter are waves 6 and 7** (§10,
  §11), not niceties.

**Q1. What DOS version should `AH=30h` report, and what does DOS 5 buy?**
The target is DOS 5; 3.31 is acceptable to start. Two things are worth
separating before that is implemented:

- **The version byte is free and the functions behind it are not.** Programs
  branch on it, so reporting 5.00 while lacking DOS 5 services is *worse* than
  reporting 3.31 — a program takes the DOS 5 path and fails at a function we
  answer with CF=1. **Make the reported version a SETTING** (SPEC.md 51.5 — 2
  resident bytes for a whole setting, and this one would live in the
  package's own config rather than the kernel's), so a title that wants 5.00
  gets it without a rebuild and without lying to everything else.
- **"More command hooks" needs pinning down before it is costed.** The DOS 5
  additions that plausibly matter here are `AX=3306h` (true version),
  `AH=4B05h` (set execution state), `AH=58h` subfunctions 2/3 (UMB link
  state), `INT 2Fh AX=4A01/4A02` (HMA), the `AH=6Ch` extended open that
  arrived in DOS 4, and `COMMAND.COM`'s installable-command interface over
  `INT 2Eh`/`INT 2Fh`. **Which of those the owner means is not settled here**
  — several are only reachable once wave 7 exists at all — and the honest
  next step is a survey of what the target software actually calls, not a
  guess at the list.

**Q2. Getting out of a hung program.** The backstop is what DOS's own was: a
reboot. **Ctrl-Alt-Del already works for free** whenever the program has not
taken `int 09h`, because that is the ROM's handler and we have not removed it.

Above that, a real escape is cheap enough to be worth building, in two rungs
and with its limits stated:

- **Rung 1 — the runner's own `int 09h`.** Install over `kbm_isr` for the
  session; read port 60h; on a magic combo restore the runner's saved `SS:SP`
  and jump to the exit path; otherwise chain to whatever the DOS program
  installed. ESTIMATE **40–60 bytes**. Defeated by a program that takes
  `int 09h` itself, which games routinely do.
- **Rung 2 — the same test from `int 08h`.** A tick handler samples the last
  latched scancode directly, which catches a program that took the keyboard
  but not the timer. Defeated by a program that takes `int 08h`, or that runs
  with `IF=0`.

**Why the longjmp is safe is not obvious and is worth writing down**: the exit
path restores the IVT, the BDA list, the PIT, the 8259 masks and the video
mode regardless of how it was reached, so the *machine* comes back consistent
from an abort exactly as it does from a clean `4Ch`. What does not come back
is the DOS program's own cleanup — which is fine, because our `INT 21h` owns
its file handles and can close them itself. The one thing that can defeat both
rungs is a program that scribbled over task 0's stack, where the runner's
saved `SS:SP` lives; there is no defence against that on an 8086.

**Still open:**

- **Q3. Is the raw-mickey pair worth ~10 resident bytes?** (§9.1). The one
  kernel change this document actively recommends considering, and it should
  be costed on its own rather than taken on a sentence.
- **Q4. What is the first-run warning?** A DOS program can take the machine
  down with unsaved work in other windows. A product decision, not an
  engineering one.
- **Q5. Which real programs does read-only wave 1 actually lose?** The
  measurement that sizes wave 5, and it cannot be taken before wave 1 runs.

---

## 13. Sources, and what may be taken from them

CONTRIBUTING.md §6 is binding: **"No vendored third-party code. Everything in
the OS is hand-written and the whole tree is MIT under one license file."**
The `apps/c64` and `apps/apple2` GPL departure was an explicit, stated,
user-decided exception for an *application*, and it is not a precedent for
the kernel or for a system facility.

| resource | licence | what it is good for |
|---|---|---|
| FreeDOS kernel (FDOS/kernel) | **GPL-2-or-later** (checked) | **Behavioural reference only.** It is a whole DOS — its own FAT driver, its own memory manager, its own device-driver model — for a machine where it *is* the OS. We want a shim that maps onto os8088's file system, which is a different shape, not a smaller version of the same one. Read it to settle "what does DOS actually return for X". |
| CuteMouse | **GPL-2** (checked) | Reference for the `INT 33h` function semantics. We do not need a mouse *driver* (§9.1). |
| mTCP | GPL | **A consumer, not a provider** (§9.4). Its real value is as a validation suite: if mTCP's FTP client runs, the shim's file handles and the packet driver are both genuinely working. |
| ISA-PicoMEM redirectors | — | Solving a problem os8088 already solved with `DRVC_FILE` (§9.5). |
| Ralf Brown's Interrupt List | freely usable, non-copyleft terms | **The actual reference to work from** for `INT 21h`, `INT 33h`, the PSP and the MCB layout. |
| Crynwr Packet Driver Specification | a published specification | The interface to implement in §9.4. |

**All of it from scratch, MIT, against RBIL and the published specifications
— DECIDED**, with FreeDOS and CuteMouse read the way one reads a second
opinion: to check a return value when something is stuck, not to supply one.
That is not licence caution for its own sake. The shim's whole job is to sit
on os8088's volume layer, heap and fsx bracket, and none of the code in those
projects knows those things exist — so even with the licences set aside, the
lift would be of the half that does not fit.
