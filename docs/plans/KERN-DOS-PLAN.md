# `kern_dos` — giving a DOS program the whole machine

**Status: PLAN. Nothing is built.** docs/plans/DOS-EXEC-PLAN.md §14 describes
this phase in a few sentences, which was right while it was far away. This is
that phase costed.

**The ask, in one line:** the Memory page's check box becomes a **radio** —
*Keep all* / *Dump the disk cache* / *Dump the whole OS* — and the third arm
takes os8088 out of memory entirely so a DOS program gets what it would get
under DOS.

---

## 1. The target is 600 KB, and that makes this a BUDGET

The requester's number: **600 KB free for the program**, because the RAM hogs
that motivate the work need 580 and the margin should hold a small disk cache.

That is not a goal, it is a constraint, and it decides every other question in
this document. The arithmetic on a 640 KB machine:

```
  655,360   the machine
   -1,536   the IVT and the BDA (0000:0000 .. 0000:0600)
 -614,400   the program's 600 KB
  =======
   39,424   EVERYTHING ELSE
```

**~39 KB** for the whole of `kern_dos`: its code, its sector buffers, its
stack, the PSP and environment, and whatever cache it keeps. For scale, that
is about what IBM DOS 3.30 costs, which is the right company to be in and not
a coincidence — we are building the same thing.

### 1.1 Where the 640 KB goes today, MEASURED

Read off a running `os8088_5150_herc_sb_gla` at the moment the arena is
claimed (`tests/dosarena.py`'s probe, this session):

| | KB |
|---|---:|
| the DOS arena the program actually gets | **449** |
| the DOS package's own region | 42 |
| the directory read-ahead window (`dirw`) | 32 |
| `KERN_SIZE` — the kernel, its modules and its low area | 112 |
| the IVT, the BDA and rounding | ~2 |
| | **637 of 640** |

So the three radio arms are worth, roughly:

| arm | what it gives | how |
|---|---:|---|
| Keep all | **449 KB** | today's default |
| Dump the disk cache | **~481 KB** | the 32 KB `dirw`, which is `[dos_keepc]` unticked today |
| Dump the whole OS | **~603 KB** | everything above, less `kern_dos` itself |

**603 is the estimate to beat and it has no cache in it.** A 16 KB read-ahead
would put it at ~587 — still over the 580 the hogs want, but the margin is
four kilobytes and that is not a margin. §6.6 proposes the way out.

> **WAVE 1 HAS MEASURED THEM** —
> docs/reports/KERN-DOS-BUDGET-2026-09-13.md. Arms 1 and 2 stand: **449 KB and
> 481 KB off one boot**, so the 32 KB between them is a difference rather than
> two readings, and the table above is confirmed. **Arm 3 is worse than 603**:
> the floor is 35.5 KB measured against §6's ~30.5 estimated, so the honest
> arm-3 figure before §6.1's levers is ~**603 KB with no cache and no shim
> budget at all** — 3.0 KB of the 38.5 is what is left. Two of the five levers
> are priced there and are worth 4.1 KB together.

---

## 2. The finding that changes the shape: §87 already built the hard part

The obvious hard problem is **overwriting yourself**. `kern_dos` has to land in
low memory, which is where the kernel loading it is standing.

**§87.5 solves this already, and better than the obvious answer.** The
hibernate resume:

1. walks the image's FAT chain into a list of **extents** — absolute LBA and
   sector count, coalesced, six bytes each — while the file layer is still
   alive;
2. copies a **~450-byte stub**, its parameters and that extent list into the
   **text framebuffer** (`B800:0000`, or `B000:0000` on a Hercules);
3. tears the machine down and jumps into the stub, which reads the extents
   with `int 13h` and jumps to the restored entry point.

Video RAM is the one memory on the machine that a conventional-memory image
does not cover. A top-of-RAM relocator — the obvious design, and what
`boot/boot.asm` stage 1 does — would have to be *excluded* from the image;
this needs no exclusion at all.

**So the handoff is that stub with a different payload**, and the return is
that stub with its original payload. Both directions are one mechanism that
exists, ships, and has a gate (§87.8).

### 2.1 What that does to the restore question

The requester asked for the restore to be costed rather than assumed away —
*"waiting 4-5 seconds to get to desktop again and THEN a few more for the
restore"* against *"a few seconds for the restore"*.

**The direct restore is nearly free**, because `kern_dos` does not have to
find `HIBERNAT.IMG` — the OS walks its chain into an extent list *before* it
tears itself down and hands `kern_dos` the list. `kern_dos` needs no FAT, no
directory and no file layer for the return path: it needs the stub and the
list, both of which it is given.

So the plan takes the direct restore. `int 19h` stays as the **fallback**, and
it is not a wasted path — §9's no-hard-disk arm ends in exactly that, and a
`kern_dos` that cannot make sense of what it was handed must have somewhere to
go.

### 2.2 What the round trip costs, from §87.7

> *the image is 1,280 sectors on a 640 KB machine, and both the write and the
> read go out in track-sized runs, so it is ~80 `int 13h` calls each way
> against an XT hard disk — seconds, not minutes.*

**~160 `int 13h` calls for a launch and a return.** The image is the whole of
conventional memory; there is no extent-skipping of free heap. That is a fixed
cost per launch and it is the honest price of the third arm, alongside the
losses in §10.

> **MEASURED, and the answer is ~4 SECONDS** —
> docs/reports/KERN-DOS-BUDGET-2026-09-13.md §3. The owner hibernated on
> **three machines including the real 5150 with a real ST-225 in it**, all at
> 640 KB with no XMS: **~2 s to write and ~2 s to resume** on every one, and
> the 4.77 MHz and 10 MHz machines agree — a figure the CPU speed does not
> move. So §2.1's *"a few seconds for the
> restore"* is exactly what it is, the judgement §2.1 already made stands, and
> arm 3's handoff is cheap.
>
> **The first version of that report said 43.4 seconds and it was the wrong
> instrument, not a wrong reading.** It was taken on `os8088_xt_hdd`, whose
> transport is **XT-IDE** — and MartyPC's hard disk has *no timing model at
> all*: the mechanical model this tree wrote and field-checked
> (`tools/martypc/patches/04-floppy-disk-timing.patch`, PERFORMANCE.md Part 9
> Set 37) is the FLOPPY's, and the ATA device carries one 200 ms reset
> constant and nothing per sector. So 92% of those seconds are the 8088
> grinding through the option ROM's byte-at-a-time PIO at 25 KB/s, where the
> field machine's **ST-225 on an ST-11M** does ~320. Our own batching was
> checked on the way and is fine — track-capped, ~50 `int 13h` calls each way,
> exactly what §87.7 claims.
>
> **The rule, which is the tree's and not this plan's: a hard-disk TIMING off
> MartyPC is not quotable.** Counts and call shapes are exact as ever;
> milliseconds are not. docs/TESTING.md carries it.

---

## 3. The second finding: `dos_be_*` is the whole port

The DOS box reaches the file system through **twenty `dos_k_*` back-end
targets** behind `dos_be_*` doors (§96.4.1). That layer exists for a reason
that has nothing to do with this plan — a kernel file slot must run on the UI
task's stack, because `dsk_secbuf` is `.lowbss` and reached through SS
(§96.4.1.1) — but it is exactly the seam a port needs.

Measured this session: every `OSAPI_FILE_*` / `OSAPI_VOL_*` / `OSAPI_FIND*`
call in `apps/dos/` is inside a `dos_k_*` target, except for eight in the
launch and shortcut paths (`dos_load`, `dos_lnk_*`, `dos_sav_go`,
`dos_path_make`, `dos_trace_dump`). Of those, only **`dos_load`** — reading the
program image — is needed under `kern_dos`; the rest are window-side.

> **W2 CHECKED IT PROPERLY AND FOUND THREE** (SPEC.md 96.4.2). The paragraph
> above was a grep over file names and prefixes; walking the call graph from
> the interrupt entries instead found `dos_walk_at` → `OSAPI_FILE_HERE`
> (reached from `dos_int21` via `dos_fh_enter`) and `dos_drv_count` /
> `dos_drv_sel` → `OSAPI_VOL_KIND` (both straight off `dos_int21`). **All
> three were outside for the same reason** — the slot does no disk I/O, so
> §96.4.1's stated reason does not bind and the direct call looks right. They
> are `DBE_HERE` and `DBE_VKIND` now, **22 doors**, +24 bytes of package image
> and no kernel byte.
>
> **`dos_load` turned out NOT to be an exception**: it is not in the outside
> list at all, so the port is *twenty-two doors and nothing else*.
>
> Two things the same walk establishes about §4.1.2's split, which is the
> other thing W2 owed. The reachable core touches **none** of `os88ui.inc`,
> `os88line.inc`, `os88parts.inc` or the socket layer — zero sites. It does
> reach `dosc.inc`'s console in three procs, and **all three are the
> outside-the-bracket arm**: `dos_tty` already branches on `[dos_inbr]` and
> takes the ROM's `int 10h` teletype inside the bracket, which is §6.1 lever
> 5's premise confirmed rather than assumed. And the whole non-file `OSAPI_*`
> surface the core can reach is **two slots**, `OSAPI_DRV_CALL` and
> `OSAPI_MOUSE`, registered in `tests/dosseam.txt` so it cannot grow quietly.

> **The port is a second implementation of twenty doors plus `dos_load`, and
> nothing above them changes.** `dos_fh_*`, the INT 21h dispatch, the PSP, the
> FCB layer, `AH=4Bh`, the memory chain and the mouse translation are all
> untouched source.

That is what makes this phase tractable, and it is the thing to verify FIRST
(§11 wave 2) because the whole plan rests on it.

---

## 4. The shape: neither option one nor option two

The two shapes on the table were **(one)** a second full kernel build,
`KERNDOS.SYS` on the system disk, and **(two)** a minimal kernel plus the DOS
half as a loadable part of `DOS.O88`.

Neither duplicates *source* — this tree already builds three kernels from one
source (`make small`, `make emu`) and a fourth arm is ordinary. What they
differ in is **disk bytes on the system floppy**, which is the disk about to
come under pressure from the system-app work, and **how much machinery has to
be invented**.

### 4.1 The proposal: `kern_dos` is a PART of `DOS.O88`

**One assembly root, `kerndos/kerndos.asm`**, which `%include`s the kernel's
disk layer and the DOS core from where they already live — and ships as
**part 1 of `DOS.O88`** (§20.12), not as a file on the system disk.

| | one | two | this |
|---|---|---|---|
| system-disk bytes | ~22 KB packed | ~13 KB packed | **0** |
| new load mechanism | a loader | a loader + a mini-ABI | **none — `OP_ASSET` already** |
| DOS core shipped twice | no | no | no |
| versions with the box | no | half | **yes** |

`apps/c64` is the worked example: 20,480 bytes of KERNAL, BASIC and CHARGEN as
part 0 of `C64.O88`, *"a sidecar a file copy could separate from the program"*
made part of it. A `kern_dos` image is the same thing and the same size class.

#### 4.1.1 The part costs NOTHING during an in-OS run, and nothing at the handoff either

**The requirement:** arms 1 and 2 are an ordinary windowed DOS box, and the
`kern_dos` part must not be in RAM while one runs. §20.12 has lazy parts for
exactly that, so the floor is *loaded only on the arm-3 handoff*.

**But it is better than that, and for free.** §2's handoff walks `HIBERNAT.IMG`
into an extent list and lets the stub read it with `int 13h` — and the part is
a byte range of `DOS.O88`, which is a file on a volume, so **the same walk
turns it into extents too**. The stub reads `kern_dos` straight into low memory
off the disk.

So the part is **never loaded as a part at all**: not during a windowed run,
not during the handoff, and not into a scratch claim that has to be found on a
heap the launch is about to give away. What the box holds is the part's file
offset and length — which §20.12 puts in the *image*, so reading them costs no
disk at all.

#### 4.1.2 The UI half does not come along

The part is built from the **core only** — a second assembly of the shared
source with the window, the menu, the pages, the console, the shortcut writer
and the file dialogs excluded. `apps/dos/dos.asm` is one file today and has to
be split so the core is `%include`-able; that is W2's real work and it is the
same work either of the original options needed.

**Why it beats option two specifically:** two's economy comes from loading the
DOS half separately, which needs a mini-ABI between two halves that are built
together anyway — and a mini-ABI between two things one team maintains is the
kind of interface that rots silently. Here the two halves are linked at
assembly time and the "load mechanism" is `op_load` plus the §2 stub.

**Why it beats option one:** the system disk is at 255 of 354 clusters at 360
KB, and the next development focus puts more system apps on it.

### 4.2 What "kernel" means here, and what it does NOT import

Per the requester: *the thing that sits there running DOS programs*, and
nothing else. `kern_dos` has **no boot sequence** (it is jumped into, not
booted), **no task table or scheduler**, **no API table**, **no window
manager**, **no drawing layer**, **no menu**, **no event loop**, **no driver
layer** and **no on-demand module mechanism**. It is a resident INT 21h with a
FAT reader under it.

This is why it is a new assembly root and not a fourth `%ifdef` arm of
`kernel.asm`: gating 80% of a file out is a permanent tax on the *shipping*
kernel's readability. The included files (`disk.inc`, `diskw.inc`) keep their
`%ifdef`s; `kernel.asm` gains none.

---

## 5. The shim, and the honest risk in it

`disk.inc` and `diskw.inc` do not stand alone. They take `[sch_lock]`, drive
the `fpg_*` progress widget, sit on `.lowbss` buffers reached through SS, and
call into the volume table and the driver layer.

**The shim is the work nobody can estimate from outside**, and it is §11 wave
3's first job: assemble the two files under a root that is not `kernel.asm`
and satisfy what they name. The precedent for measuring it is
docs/plans/completed/KERN-SMALL-MODULE-SPLIT.md §8, which walked `mod_need`'s
transitive cone and found **155 symbols in 7 files** — and whose own lesson was
that the first call-graph pass *undercounted*, because it could not see
`call far COLD_SEG:label`.

Expected shape of the shim, ESTIMATED:

- `sch_lock` / `sch_unlock` → `ret` (there is one task)
- `fpg_*` (the progress widget) → `ret`
- `cur_*` (the pointer) → `ret`, or the mouse's own
- the volume table → kept, but populated from what the OS **hands over**
  rather than re-probed (§7 step 3), which also skips §18.97's floppy probe
- `mem_*` → a bump allocator over the region above `kern_dos`

**If the shim comes out large, that is the finding that reopens §4.** A shim
bigger than a purpose-written FAT reader means the reuse is not paying, and
the answer is a small reader rather than a big shim. Wave 3 is allowed to
return that answer.

---

## 6. What goes in `kern_dos`, against the 39 KB

Sizes from docs/plans/KERN-SMALL-CUT-PLAN.md §1.2's attribution (heap-bearing
sections, `kern_small`) — **an upper bound**, since that table is the whole of
each file and `kern_dos` wants part of it.

| | bytes | note |
|---|---:|---|
| `disk.inc` — volumes, mount, FAT read | 6,816 | less mount UI, less multi-volume |
| `diskw.inc` — the FAT write path | 5,077 | less the batch/undo machinery |
| `dskwin.inc` — the mount buffers | 2,336 | `.lowbss`, needed as-is |
| `mouse.inc` — serial mouse | 3,538 | **the cursor half is not wanted** |
| the DOS core from `apps/dos/` | ~12,000 | ESTIMATE; the box's image is 30,731 and most of it is window |
| PSP, environment, MCB chain, `dos_load` | ~1,500 | existing source |
| the shim (§5) | ? | **the unknown** |
| | **~31 KB + shim** | against 39 |

> **MEASURED, and the table above is 5,100 bytes light** —
> docs/reports/KERN-DOS-BUDGET-2026-09-13.md §2. Today's tree, `kern_small`,
> `.text` + `.cold` + `.bss` + `.lowbss` per file: `disk.inc` **7,206**,
> `diskw.inc` **5,473**, `dskwin.inc` **2,336**, `mouse.inc` **3,698** —
> 18,713 against 17,767. And the DOS core row is the one that moved: it is
> **17,667** (14,636 of image and 3,031 of bss, measured by symbol span with
> `tools/os88doscost.py`) and not ~12,000 + ~1,500, because *"most of it is
> window"* is false — the window half is 38% of the image, not most of it.
> The 1,500 for the PSP, environment and MCB chain is already inside that
> figure rather than beside it.
>
> **Floor 36,380 = 35.5 KB against a budget of 39,424 = 38.5 KB**, so **3.0 KB
> is left for the shim and any cache**. The levers below stop being an
> ordering suggestion.

### 6.1 The levers, in the order they should be pulled

1. **Drop the file-window handle layer.** §96.11's 8 KB cluster-aligned window
   exists because os8088's file API is by-name and whole-file. Under
   `kern_dos` the FAT chain is right there, so `AH=3Fh` reads straight into the
   program's buffer. **−8 KB of buffer and ~−3 KB of code**, and it makes the
   box *more* like DOS rather than less. This is the single biggest lever and
   it should be taken first.
   **MEASURED: the 8 KB is a heap CLAIM** (`dos_wseg` holds a segment), so it
   is not in the floor at all and comes off the *budget*; the code half is
   **1,803** of `dos_fh_*`'s 2,186, the other 383 being the handle TABLE,
   which stays because DOS needs handles whatever is under them.
2. **Drop the cursor half of `mouse.inc`.** INT 33h needs the packets and the
   scale; nothing draws an arrow. ESTIMATE −1.5 KB.
   **MEASURED at 1,440, so the estimate was right — and there is a second
   781 beside it nobody counted**: `kbm_*`/`kbd_*`, the keyboard, which
   `kern_dos` does not want either (no event ring to feed, and the ROM's own
   `int 09h`/`int 16h` serve INT 21h's character input). `mouse.inc`'s
   carried share is ~1,007 of 3,419.
3. **Drop `diskw.inc`'s long-operation machinery** — the batch bracket, the
   progress widget, the copy engine (§22.24/§22.25 are the file manager's).
4. **One volume class.** BIOS floppies and the boot partition; no driver
   volumes, no RAM disk, no redirected volumes. This also removes `DVK_FILE`'s
   refusal paths, which several `dos_k_*` doors carry.
5. **No console.** The program owns the screen; `AH=02h`/`AH=09h` go to the
   ROM's teletype, which is what they do inside the fsx bracket today.

### 6.2 …and the cache, which is the interesting one

At ~31 KB plus shim, a **16 KB read-ahead** takes the program to ~587 KB.
Over the 580 the hogs want, but only by seven.

> **MEASURED: it cannot be funded out of slack.** The floor leaves 3.0 KB, and
> 7.1 KB with levers 1 and 2 taken — before the shim is written. So the
> purgeable shape is not the nicer of two options, it is the only one that
> works, and it has to be purgeable in the strong sense: claimed only when the
> program has not taken the memory, rather than merely given back on demand.

**Make it purgeable** — approved.  `kern_dos` claims the cache at the top of free memory
and gives it back the moment the program's own `AH=48h` needs it. A hog that
takes everything at startup gets its 603 KB and no cache; a modest program
that never asks gets 587 KB and a much faster disk. That is os8088's own
`MEM_PG_*` idea (§50.6) in miniature, it is ~50 bytes of the allocator, and it
means the cache never has to be argued about against the target.

---

## 7. The handoff, in order

With arm 3 picked and the program named, on `dos_run`'s wake:

1. **Confirm** (§9, floppy-only machines) or **hibernate** (§8).
2. **Walk two chains into extent lists, while the file layer is still alive**:
   `DOS.O88`'s `kern_dos` part, and `HIBERNAT.IMG`. §87.5 step 2 is the code.
3. **Bank the transport facts** the OS already knows: the `int 13h` unit, the
   partition base, sectors per track, heads (§87.5 step 1) — and the volume
   table, so `kern_dos` skips §18.97's floppy probe entirely.
4. **Bank the launch block**: the program's name, its arguments, the working
   directory's cluster, the environment, the arm, and `[dos_memkb]`.
5. **Tear down**: `cp_flush_close`, `drv_shutdown`, `gfx_lock`, `vid_reboot`
   to text — §87.5 step 3's order, unchanged, because it is the order a
   restart already uses.
6. **Stage into the text framebuffer**: the stub, the `kern_dos` extents, the
   `HIBERNAT.IMG` extents, the transport facts and the launch block.
7. **Jump into the stub.** It reads `kern_dos` low, copies the restore extents
   and the launch block into `kern_dos`'s own image — *not* video RAM, because
   the program will write there — and jumps to `kern_dos`'s entry.
8. `kern_dos` hooks INT 21h/22h/23h/24h/33h, builds the PSP and the
   environment, loads the program with `dos_load`, and runs it.

**Step 7's copy out of video RAM is the one new idea in the sequence**, and it
is forced: §87's stub is the last thing to run before the restored kernel, so
it never had to survive a program.

---

## 8. The return, on a machine with a hard disk

On `AH=4Ch` (or `INT 20h`, or a fault `kern_dos` cannot survive):

1. Copy the stub and the banked `HIBERNAT.IMG` extents back into the text
   framebuffer.
2. Jump into it. It is §87.5 step 4 onward, byte for byte.
3. The image comes back over everything including `kern_dos`, and control
   returns to the UI task's loop where the hibernate left it.

**The "no question box on resume" is a flag, not a mechanism.** §87.5's probe
posts `UI_RBQ_ASK` and the window asks. A hibernate written for a DOS handoff
sets a byte in `HIBERNAT.PTR` meaning *this was not the user leaving the
machine*, and the probe posts `UI_RBQ_RESUME` directly. The DOS window is
still open on the other side, and `dos_wake` finds `DST_RAN` with the exit
code the stub carried back.

**What the exit code rides in** is an open question — §12, question 3.

---

## 9. No hard disk: the first time this OS throws work away

There is nothing to hibernate to, so the machine cannot come back. The program
runs, and then the machine **reboots**.

This is the first deliberately destructive action in os8088 and it should read
like one:

- The third radio arm is **greyed with the reason** on a machine with no fixed
  disk (§47 — grey a fact, never a guess): *"needs a hard disk to come back
  to"*. It is not offered and then refused.
- Unless the user asks for it, which they will. So: a **second, separate
  confirmation** naming what is lost — *every open window, every unsaved
  document, and the machine restarts when the program exits* — with the
  destructive verb on the button and **Cancel as the default**.
- The confirmation is not a toast and not a rider on the Memory page. It is
  its own window, at the moment of launch, and it lists the open packages by
  name so the loss is concrete rather than abstract.

**The greying predicate is `hb_pick`'s** (§87.2) — the same question hibernate
already asks about whether there is a fixed disk to write to — so there is one
answer and not two.

---

## 10. What arm 3 LOSES, stated rather than discovered

Arm 3 is **not a superset of arm 2**, and the Memory page has to say so:

- **no packet driver** — §96.23's Crynwr interface is `ETHER.DRV` over the
  kernel, and neither is there. **A future phase may reopen this**: a thinner
  DOS-side rework of `ETHER.DRV`, offered as an option rather than carried
  always, and §12 question 7 is the one thing the design must not box out;
- **no windowed mode** — the program is fullscreen by definition;
- **no console capture** (§96.34), no Task Manager row, no clipboard;
- **no `DOS.O88` overlay** and no second instance;
- **a launch and an exit cost ~160 `int 13h` calls** (§2.2);
- **and on a floppy-only machine, everything open** (§9).

---

## 11. Waves

| | what | gate |
|---|---|---|
| **W0** | **BUILT** (SPEC.md 96.36). `[dos_keepc]` is three-way over `os88ui_rad` — the control's **first caller in the tree** — and arm 3 is greyed with its reason on the glass. +364 package bytes, +6 bss, **zero kernel**. | `soak -k dosmem`, and its three verified failures |
| **W1** | **DONE** — docs/reports/KERN-DOS-BUDGET-2026-09-13.md. Arms 1 and 2 confirmed at 449/481 KB with a 32 KB cache between them, the floor re-derived at **35.5 KB against 38.5**, and the hibernate round trip at **~4 s on iron** (§2.2 — the 43.4 s this first reported is MartyPC's XT-IDE PIO and not the field's controller). | the report, and `tools/os88doscost.py` to re-derive it |
| **W2** | **DONE, and the seam held with three breaches to fix** (§3, SPEC.md 96.4.2). Two new doors, +24 package bytes and no kernel byte; `tests/unit/t_dosseam.py` is the gate and walks the CALL GRAPH. | `soak -k dosseam` — **soak and not the fast this row first said**, by docs/WRITING-TESTS.md §2.1 rule 1 |
| **W3** | **The shim and the root.** `kerndos/kerndos.asm` assembles `disk.inc`+`diskw.inc` and reads a file. **Allowed to return "the shim is too big, write a reader instead."** | a host-side FAT read against `os88fat.py` |
| **W4** | **A `.COM` runs.** The DOS core over the new back end, no handoff yet — `kern_dos` booted directly on a test disk. | MartyPC, a `.COM` that prints |
| **W5** | **The handoff.** §7 steps 2–8, ending in `int 19h`. No hibernate yet. | the program runs and the machine reboots |
| **W6** | **The return.** §8, and the no-question flag. | launch, run, exit, desktop back with the same windows |
| **W7** | **The floppy arm.** §9's confirmation and the greying. | the refusal, and the confirmed path |
| **W8** | **The budget.** §6.1's levers until the measured figure clears 600 KB. | `dosarena`'s shape, arm 3 |

**W0 and W1 land before anything is designed further.** W2 is the go/no-go for
the whole shape; W3 is the go/no-go for §4's reuse.

### 11.1 What W0 came to, and the one line W6 changes

The wave cost 364 package bytes and no kernel byte at all, and it landed
where it was aimed — but three things in it are worth writing down, because
two of them are the sort of thing that gets re-derived.

**The greying is ONE routine and W6 replaces its body.** `dos_mem_whole`
answers *may the program have the whole machine?* in CF with the reason in
SI, and today it refuses unconditionally with *"not in this build yet"*.
Three consumers read it — the DIS bit, the caption, and `dos_mem_fix` at the
block's commit point — so when the mechanism exists, that body becomes
`hb_pick`'s question (§9) and **nothing else in the package moves**: not the
layout, not the record, not the three call sites, not the `.LNK` format.

**Consumer three does not belong on `dos_run`,** which is where it was put
first. A `.LNK` written on a machine that HAS the feature can carry
`DOS_MEM_WHOLE` to one that does not, and a greyed control refuses a click
and not a file — but `dos_run` is not reached until a launch, and an empty
path box never reaches it at all. It sits on `dos_mem_take` instead, which is
the memory block's one commit point (all four of its callers are a page being
left or a launch), so the page comes back showing what the machine will
really do.

**The third FIGURE is deliberately absent.** The two on the page are
`OSAPI_MEM_AVAIL_LVL`'s and `OSAPI_MEM_AVAIL`'s real answers; what arm 3
would give the program is not a number this build can ask anything for, and
§47 rule 5 refuses a guess sitting beside two measurements. It arrives with
W1, which is the wave that measures it.

---

## 12. Open questions

1. **How big is the shim, and can levers 3–5 find the rest?** (§5) The plan's
   largest unknown, and W3 answers it. A shim near the size of a
   purpose-written FAT reader reopens §4. **W1 sharpened this**: the budget
   after the two priced levers is 7.1 KB, and levers 3, 4 and 5 are each a
   subset of a file rather than a family of symbols — so pricing them means
   classifying `disk.inc` and `diskw.inc` proc by proc, which is W3's work and
   not a measurement that can be taken without it.
2. **Does the DOS core assemble outside a package at all?** It is `org 0` with
   bss at `os88_image_end` and a three-byte dispatcher header (§20). W2 should
   check this, not assume it. **PARTLY ANSWERED**: W2's walk shows the
   reachable core calls into none of the package libraries — `os88ui.inc`,
   `os88line.inc`, `os88parts.inc` and the socket layer are zero sites — and
   reaches the console only on the arm `kern_dos` never takes. What is left is
   the mechanical half, `org 0`, `os88_image_end` and the header, and that
   cannot be answered without doing the split: it is W3/W4's, not a scan's.
3. **How does the exit code come back?** The stub restores conventional memory
   over everything, so a byte in `kern_dos`'s image does not survive. Candidates:
   a word in the BDA's unused area, a word in `HIBERNAT.PTR` rewritten before
   the restore, or a fixed offset in the image itself that the stub patches.
4. **XMS.** The box publishes `OSAPI_XMEM_*` to DOS programs today. Does
   `kern_dos` carry an XMS provider, or does arm 3 lose extended memory too?
   §87.7 already owes extended memory to hibernate, so the two are related.
5. **Which volumes does the program see?** A: and B: from the BIOS is the
   floor. Does the boot partition appear as C:, and does `kern_dos` carry
   FAT16?
6. **Does `kern_dos` need `diskw.inc` at all in W4?** A read-only first arm is
   a smaller target and many programs never write. It is not the shipping
   answer but it may be the right W4.

7. **Where would an optional packet driver go?** A thinner DOS-side rework of
   `ETHER.DRV` is a named future phase, so the design must leave room: the
   launch block should be able to say *"and load this too"*, the low-memory
   layout must not assume `kern_dos` is the only resident piece, and the
   arithmetic on the Memory page has to be able to report what the option
   costs — because it comes out of the same 39 KB and the user is the one
   trading it against their program. **Nothing here needs building now; what
   is needed now is not making it impossible.**

---

## 13. What would kill this

Written down so it is recognised early rather than argued about late:

- **The budget.** If `kern_dos` measures over ~39 KB after §6.1's levers, the
  600 KB target is not reachable by this route and the honest answer is to say
  so rather than ship 560.
- **The seam.** If the INT 21h core turns out to reach the kernel outside the
  `dos_k_*` doors in ways that matter, the port stops being a back end and
  becomes a rewrite.
- **The stub's reach.** §87's stub reads through `int 13h` rung 0. A machine
  whose hard disk is IDE rung 1 (§52.1) cannot hibernate today (§87.7 owes it)
  and so cannot use arm 3 either. That is an existing limitation inherited,
  not a new one — but it decides who the feature is for.
