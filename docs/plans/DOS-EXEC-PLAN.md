# DOS-EXEC-PLAN.md — running DOS `.COM` and `.EXE` programs

**STATUS: INVESTIGATION ONLY. Nothing here is built, nothing is decided, and
every size in it is an ESTIMATE unless the line says MEASURED.** The three
heap figures in §2.2 are measured; every byte count for code that does not
exist yet is a guess against a comparable that does.

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
   640KB machine at a bare desktop: **449.0 KB free, contiguous, ending
   exactly at the top of conventional memory.** With a Disk window open —
   the state you are actually in when you double-click — it is **still
   449.0 KB ending at the top**, because every claim a Disk window makes is
   at the bottom of the heap. That is about what a 512KB PC running DOS 3.3
   gave a program, and it is a realistic DOS machine rather than a token
   one.

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

Three things fall out of that table and each one matters.

- **449 KB is a lot of DOS machine.** DOS 3.3 on a 640KB PC left a program
  about 580KB; on the 512KB machines most of this software was written for,
  about 430KB. We are in that range without trying.
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
runner's own region allows, with N taken from `OSAPI_MEM_AVAIL` — whose own
SDK comment says "size yourself from THIS, not from int 12h: it is the only
number that accounts for what the kernel and every other package already
hold", which is exactly this situation. With a ~16KB runner region at the
top, the run is roughly `0x2FC0..0x9C00` — **≈433 KB** (ESTIMATE: 0x6C40
paragraphs = 443,392 bytes).

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

- claim the arena with the **bottom-up** `OSAPI_MEM_CLAIM` instead, accept a
  smaller run, and put nothing of ours above it except video memory — which
  needs the runner's own region out of the way, and there is no mechanism
  for that today;
- on a 386, V86 mode gives real trapping. Out of scope: the target machine
  is a 4.77MHz 8088 and `OSAPI_CPU_INFO` (SPEC.md 60) would gate it to
  machines this project does not calibrate against.

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
- **Save `0040:0013`** (§2.3) and the rest of the BIOS data area we care
  about. The BDA is 256 bytes; saving all of it is the same argument as the
  IVT, costs another 256 bytes, and goes in the same place. Restoring all of it is *not* obviously
  right — the ROM's tick count at `40:6C` should keep whatever it reached —
  so this wants a small explicit list rather than a blanket restore. **Open
  question.**
- **PIT channel 0.** A DOS program that wants a fast timer reprograms it,
  and the scheduler's quantum goes with it. `sch_fast_on`/`sch_fast_off`
  already exist for exactly this (SPEC.md 53.2) and `sched_unhook` already
  knows how to put channel 0 back to mode 3 divisor 65536. Restoring it is
  three `out`s we already have code for.
- **The 8259 mask.** A program that masks IRQs and does not restore them
  leaves us with no timer. Save `0x21` and `0xA1`, restore both.
- **The video mode**, via the `fsx_mode` note in §4.
- **Nothing about the disk**, at the hardware level — see §7.

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

- **Anything that wants a windowed DOS box on the cheap.** The brief asks
  whether there is a cheap trick. There is half of one: a program that does
  all its output through `INT 21h` character functions or `int 10h` TTY can
  be rendered into a window, and RunCPM's terminal (SPEC.md 74.2) is the
  working precedent for the rendering half. But **a DOS program writing
  directly to `B8000` bypasses every interception point**, and most of them
  do, because that is what made them fast. Making that work means a shadow
  buffer at `B8000` — which means the program cannot be at its real address
  — which on an 8086 means no. **Fullscreen is the honest answer**, and
  a windowed *text-only* mode is a possible later nicety with a clearly
  stated "only if the program is well-behaved" caveat.
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
| — | *deferred, needs its own design* | | |
| ? | Write-at-offset file handles — either a package-side read-modify-rewrite or a published kernel seek/write-at trio (§6.3) | 0 or ~400 | |
| ? | FCB functions | 0 | +2 KB |
| ? | Windowed text-mode DOS box (§10) | 0 | +4 KB |

**Wave 1 is the one that decides everything**, and it is worth building as a
throwaway first: a `.COM` that does nothing but `INT 21h AH=09h` (print a
string) and `AH=4Ch` (exit) exercises the arena, the PSP, the bracket, the
vector save/restore and the exit path — every load-bearing piece — in a
program small enough to hand-assemble and read.

---

## 12. Open questions — things this investigation could not settle

1. **What DOS version should `AH=30h` report?** Report too low and modern
   programs refuse; too high and they look for features we lack. 3.31 is
   the honest description of the feature set below. Needs a survey of what
   the target software actually checks.
2. **How does a user get out of a hung DOS program?** §4 note 4. There is no
   safe answer today. Ctrl-Alt-Del through the ROM reboots the machine and
   loses the session, which is at least *an* answer and is what DOS gave.
   Worth deciding deliberately rather than by default.
3. **Which BDA bytes to restore and which to let stand** (§5). The tick
   count at `40:6C` should keep what it reached; the memory size must go
   back; the rest wants a list.
4. **Read-modify-rewrite or a kernel seek?** (§6.3). This should be decided
   by measurement — build wave 1 with reads only, then find out which real
   programs need in-place writes.
5. **Is the raw-mickey pair worth ~10 resident bytes?** (§9.1).
6. **What is the first-run warning?** A DOS program can take the machine
   down with unsaved work in other windows. That is a product decision.
7. **Does the arena want to be bottom-up instead?** (§2.3). It costs free
   run length and buys a truer "top of memory". Cannot be settled without
   knowing which programs misbehave.

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

**The recommendation is to write all of it from scratch, MIT, against RBIL
and the published specifications**, and to use FreeDOS and CuteMouse the way
one uses a second opinion — to check a return value, not to supply one. That
is not licence caution for its own sake: the shim's whole job is to sit on
os8088's volume layer, heap and fsx bracket, and none of the code in those
projects knows those things exist.
