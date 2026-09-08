# THE LOADER FREES ITSELF — a package's loader as a disposable segment

> **Status: RESEARCH, nothing built.** The cost below is estimated against
> measured comparables in this tree and every claim is sourced to a line of
> kernel. It is ~150 resident bytes, and §6 is where that number comes from.
>
> **Read 4.1 and 5.2 first if you read nothing else.** Two things are not
> obvious and both would have been found late.
>
> **4.1** — after the switch the running program is *inside* a claim rather
> than at the base of one, and `mem_own`, the fence on every memory slot, says
> no to it. It would pass on a floppy and fail on a hard disk, at the program's
> first `OSAPI_MEM_CLAIM`, long after a successful launch. The fix is eleven
> bytes and a routine that already exists.
>
> **5.2** — the loader's job does NOT end when it has loaded. `op_seg` is an
> *accessor* whose table is in the loader's image and whose state is in the
> loader's bss, so freeing the loader destroys "where is part N" for a program
> that still needs it. The handoff has to carry the segments, and the place it
> carries them in decided the shape of the kernel arm.

---

## 1. The ask

A package that uses parts pays for its own loader, for ever:

* the LOADER's segment claim — its image and bss — is held for the life of the
  instance, and after `op_load` returns there is nothing in it anybody needs;
* the parts standard's own code sits inside the running program's 61,440
  bytes, which is exactly the budget the program ran out of and went to parts
  to escape.

The proposal: the loader loads the parts, tells the kernel *"the program is at
segment Y"*, returns, and is freed. The program then runs from Y **as though
it had never used parts at all** — an ordinary single-segment package, no
`OS88_PARTS_*`, no `op_seg`, no gates, and the whole 61,440 to itself.

Lazy parts are excluded and that is the ask's own scope: `op_fetch` and
`op_drop` are loader code, and a loader that has been freed cannot fetch.

---

## 2. What the launch path does today, and where the seam is

`ld_start` (kernel/loader.inc:949, `.cold`) is nine numbered steps. Three
matter here:

| step | what it does |
|---|---|
| 7 | zeroes the bss: `mov di,[ld_img] / mov cx,[ld_bss] / rep stosb`, ES = the region |
| 8 | calls the entry proc — `mov ds,[ld_base]` then `call far [es:ld_fp]`, where `ld_fp` is `{PKG_DISP, ld_base}` |
| 9 | registers the instance: `I_SPTR = [ld_base]`, `I_SIZE = [ld_need]`, the name from `[ld_base]:16`, the icon flag from `[ld_base]:LD_H_FLAGS`, then binds the window the entry returned in BX and publishes `I_STATE` |

**The seam is between 8 and 9**, and it is a good one: *nothing about the
instance is committed until step 9*. `I_SPTR`, `I_SIZE`, the name, the icon
and `I_STATE` are all written there, off `[ld_base]`. Change `[ld_base]`
between the two and every one of them describes the new segment with no
further edit.

Better still: **step 8's far call is the loop-back target.** So the whole
re-home is *"re-point `ld_base`/`ld_img`/`ld_bss`/`ld_ent` at Y and jump back
to the call"* — the second entry is made by the same three instructions that
made the first, with the same contract.

**Step 7 is deliberately NOT re-entered.** It is the `rep stosb` that zeroes
the bss, and on this path the program's bss arrived zeroed inside its own part
with the loader's handoff vector written into the head of it (§5.2). Zeroing
would erase the one thing the program is waiting to read.

### 2.1 Why the kernel has to be the one to call it

The loader cannot far-call Y's entry itself and then be freed: it would be on
the call stack. Control must leave the loader's segment entirely before the claim
goes, and the only thing that can do that is the caller — `ld_start`. That is
what forces the "tell the kernel and return" shape rather than a purely
package-side one.

### 2.2 `OSAPI_PKG_RUN` is already out of scope

The second launch door refuses parted images outright —
`test byte [es:si+LD_H_FLAGS], 4 / jnz .bad`, *"parts, and no file to read
them out of"* (loader.inc:1186). Nothing to do.

---

## 3. Ownership — the part that decides whether this is cheap

A claim's `MC_OWN` (kernel/memory.inc:73) is **one of two kinds**:

* `0..INST_MAX-1` — an instance **slot**. `ld_alloc` stamps the package's
  region this way (`call ld_slot` at loader.inc:900).
* a **segment** — what `mem_own` returns for a package's own claims:
  `.yes: mov bx, es` (memory.inc:3709), and `osapi_mem_claim_dma_x` passes
  that straight through as the owner word.

Teardown reads both. `mem_free_rec_x` (memory.inc:3205) sweeps the slot, then
`test byte [di+I_KIND], KIND_PKG / mov bx,[di+I_SPTR] / call mem_free_owner_x`.

So after a re-home to Y:

* the loader's **region** is owned by the slot — it is one claim and it is the
  one to free;
* the **carve** holding the parts is owned by **X, the loader's segment** — and
  once `I_SPTR` is Y, the teardown sweep looks for Y and never finds it.
  **The carve would leak for the session, and it is the largest claim the
  package holds.**

That is the one real bookkeeping job: **re-stamp `MC_OWN` from X to Y**, one
walk of `mem_tab`. It cannot collide with the slot-owned records because a
slot is 0..11 and a segment is above the heap base.

---

## 4. The fences, and the one that breaks

Everything keyed to the package's segment was audited. All of it is written in
step 9 or later and therefore describes Y for free:

| reads the segment | when | after re-home |
|---|---|---|
| `I_SPTR` / `I_SIZE` | step 9 | Y — correct |
| the instance name, `inst_set_name_x` | step 9, off `[ld_base]:16` | Y's header |
| the icon flag `LD_H_FLAGS` | step 9, off `[ld_base]` | Y's header |
| `inst_pkg_fence` — `ES == I_SPTR`, `AX < I_SIZE` | at `fsx_run` etc. | Y — correct |
| `inst_pkg_spawn` — `mov bx,[di+I_SPTR]` | worker spawn | Y — correct, and an entry proc cannot spawn anyway (`I_STATE` unpublished) |
| `wm_pkgcall` — `W_SEG` | every callback | see §4.2 |
| `mem_free_rec_x` — the teardown sweep | close | Y, once §3's re-stamp is done |

### 4.1 `mem_own` says NO to the re-homed program

`mem_own` (memory.inc:3683) asks *"does a live claim START at ES, and is it
owned by an instance slot?"* — via `mem_owner_of_x`, which matches `MC_SEG`
exactly.

**Y is inside the carve, not the base of it.** `op_seg` places part *i* at
`op_base + (slack + offset)/16`, and the head slack is the cluster alignment
(§20.12.2) — zero on a 512-byte-cluster floppy and non-zero on a hard disk.
So Y equals a claim base by luck on one volume and never on another.

`mem_own` is the fence on `OSAPI_MEM_CLAIM`, `_CLAIM_HI`, `_CLAIM_DMA`,
`OSAPI_MEM_FREE`, `OSAPI_MEM_REGROW` and `OSAPI_MEM_MOVABLE`. **A re-homed
program could not claim a byte of memory**, which is fatal, and it would fail
*after* a successful launch, at whatever moment the program first asks — a
refusal that names memory and points nowhere near the cause.

The fix is **eleven bytes and a routine that already exists**. `inst_of_seg`
(instance.inc:600) answers *"which live package instance is running at this
segment?"* by walking `inst_tab` for a matching `I_SPTR`. `mem_own` gains one
arm at `.no`:

```
    mov bx, es
    call inst_of_seg            ; is ES some live package's own segment?
    jnc .yes                    ; ...then it IS a package, by definition
```

That is not a widening of the fence — `I_SPTR` **is** the kernel's definition
of "this package's segment", and asking it directly is a narrower question
than the claim-base proxy that stands in for it today. It also makes
`mem_own` return `BX = ES` on that path, so the program's claims are owned by
Y and §3's teardown sweep frees them. The two halves agree.

**This arm is worth having on its own**, and it is the same primitive the
attribution work wants: a segment can now be asked *"are you package X"*
rather than *"are you the base of a claim"*.

### 4.2 What the loader may not do

Only two things stamp a segment *before* step 9:

* **a window** — `wm_create` takes `W_SEG` from ES, and every later callback
  is far-called at `{W_SEG, PKG_DISP}`. A loader that creates a window would
  leave the kernel calling back into freed memory.
* **a worker** — already impossible from an entry proc.

So the rule is one line: **a re-homing loader creates no window; the
program's entry proc does.** The kernel can enforce it for free — the entry returns BX, and a
re-homing entry must return BX = 0. That is a `cmp`/`jne` on a path that
already tests CF.

Everything else an entry proc might do is stamped by **slot**, not segment —
the sound grant (`snd_inst`, set to the record around the call at
loader.inc:1005), the XMS release record, the toast — and survives untouched.

---

## 5. The design

Naming, so the rows are countable: the **image** is the loader — the first
thing in the `.o88`, the thing that used to be the only thing. The **parts**
are 0..N after it. For Clear Skies that is an image plus three parts, and the
program is part 0.

### 5.1 The loader

```
    OS88_HEADER 'SKIES', sh_entry, OS88_F_ICON | OS88_F_PARTS
%include "os88parts.inc"
    OS88_PARTS_BEGIN 3
      OS88_PART OP_SEG,   OP_COMP       ; 0  THE PROGRAM - an ordinary package
                                        ;    image, header and all, padded with
                                        ;    its own bss (5.3)
      OS88_PART OP_ASSET, OP_COMP       ; 1  the artwork
      OS88_PART OP_ASSET                ; 2  the locations, packed per world
    OS88_PARTS_END
sh_entry:
    call op_load
    jc .out
    call op_handoff                     ; part 0 is the program; every other
    jc .out                             ; part's segment goes in its bss (5.2)
.out:
    xor bx, bx                          ; NO WINDOW: the program makes it
    ret
```

**Measured, this exact shape: 1,267 bytes of image**, 1,219 of it the parts
standard (§20.12.9's gating: `OP_COMP` only, no XMS, no lazy, no scratch, no
optional). Plus `OP_BSS`'s 86 — so ~1,353 bytes, and claims are KB-granular
(`mem_claim_1`: *"AX = KB wanted (1..640)"*), which makes it a **2 KB claim
and 2 KB back**.

It is also 1,267 bytes that **cannot** be compressed on the disk, against
10,736 for the shape built in the previous round — the part table is
file-relative and lives in the image, so the image is the one thing `PKGZ`
can never touch (§20.12.3). Everything else becomes an `OP_COMP` part.
**~9.5 KB of the file moves from uncompressible to compressible**, and the
engine, which packs at 81%, is most of it.

### 5.2 The handoff — and why it needs no mechanism at all

`op_seg` is an **accessor, not a load-time routine**. It reads `op_table`,
which is in the loader's image (§20.12.3), and `op_base`, `op_slack`,
`op_first`, `op_runkb`, `op_t_n`, `op_zn` and `op_optok`, which are in the
loader's bss. **Freeing the loader destroys both the code and the data behind
"where is part N".** A program that wants its artwork at run time — which
Clear Skies does, and its locations too — has to be told before the loader
goes.

Three ways were considered.

**A magic block.** The program's image carries `db 'O88PVEC'` and a row of
words; the loader scans the program's first page for the tag and fills them
in. This has a real precedent — `os88pkg.py` finds `op_table` in an image by
scanning for `'O88PARTS'` — and costs ~25 bytes of loader and no build-time
coupling.

**A packer stamp.** The program exports the vector's offset; `os88pkg.py`
reads it out of a map at pack time and writes it into a word of the *loader's*
image. The loader then does `mov di, [sh_vec]`. ~10 bytes of loader, but it
couples the two halves through the build: the packer must map the program to
pack the loader.

**Neither is needed.** The program's own header says where its image ends
(`LD_H_IMG` at +8), and its bss starts there. So the vector goes at **the head
of the program's bss**, the loader computes the address in three instructions
from a field it is already reading, and the program declares those words first
in its bss chain like any other. No tag, no scan, no stamp, no map, no
build-time coupling — and about eight bytes of loader:

```
op_handoff:                     ; ES = the program's segment, from op_seg
    mov di, [es:LD_H_IMG]       ; ...its bss begins where its image ends
    mov al, 1
    call op_seg                 ; part 1: the artwork
    mov [es:di], ax
    ...
```

**This only works because the kernel does not zero that bss**, which is §5.3,
and that is what makes the arrangement a design rather than a trick: the
program's bss arrives already zeroed *from the part*, so the loader's writes
into the head of it are the only non-zero thing there and they survive.

### 5.3 The program's bss ships inside its part, and §51.1.2 already decided this

The program's part carries `image + bss` bytes: the trailing zeros are in the
file. That is exactly what `tools/os88drv.py` does for a driver, and §51.1.2
is the reasoning, arrived at by the same route —

> *"The answer is to make the two the same number… What that costs is zeros
> back on the floppy, and on a packed disk it costs nothing measurable — a run
> of zeros is what LZ4 is best at. Measured: the 360KB system disk is 255 of
> 354 clusters with the strip and 255 without."*

— and the part is `OP_COMP`, so the zeros cost the disk nothing here either.
It also spares the loader an `OP_ZERO` row, which would turn `OP_HAS_ZERO` on
and put `op_scrub` and its arms back into an image that has just been measured
at 1,267.

§51.1.2 also supplies the one thing that must not be skipped: **a bound test.**
*"The header is a FILE: a foreign tool may write any `DRV_H_BSSP` it likes."*
Y's header is a part, read off a disk, and the same is true of it — so
`OSAPI_PKG_REHOME` takes **AX = the bytes available at DX** (the loader knows
it: it is the part's own `len`), and the kernel refuses when Y's
`image + bss` exceeds it.

### 5.4 The kernel side

A new X cell, `OSAPI_PKG_REHOME` — **DX = the program's segment, AX = the
bytes available there**, ES = the caller's (the fence). It banks both and
returns; it does nothing else, because the loader is still executing and
nothing may move under it.

`ld_start` gains one arm between steps 8 and 9:

```
    ; --- 8a. THE RE-HOME ---------------------------------------------------
    cmp word [ld_rehome], 0
    je .reg                     ; the ordinary launch, untouched
    <refuse a second one - once per launch>
    <BX must be 0: a re-homing entry owns no window (4.2)>
    mov es, [ld_rehome]
    xor si, si
    call ld_hdr_ok              ; the .o88 prologue's five tests, on the part -
    jc .abort                   ; already written, already .cold, already near
    <ld_img / ld_bss / ld_ent from Y's header; ld_need = img + bss>
    <refuse if ld_need > [ld_rehsz] - 5.3's bound test>
    mov bx, [ld_base]           ; --- the carve and every other claim the
    mov dx, [ld_rehome]         ;     loader made, re-owned X -> Y (3)
    call mem_reown_x
    call ld_slot                ; --- and the loader's own region, freed: it
    mov dx, [ld_base]           ;     is owned by the SLOT, so this is one
    call mem_free_x             ;     claim by base and not a sweep
    mov ax, [ld_rehome]
    mov [ld_base], ax
    mov word [ld_rehome], 0
    jmp .call8                  ; ...straight to step 8's far call
```

**It jumps to step 8, not step 7**, and that is load-bearing: step 7 is the
`rep stosb` that zeroes the bss, and on this path the bss arrived zeroed in
the part with the loader's handoff vector written into its head. Zeroing it
would erase the one thing the program is waiting to read. It is also fewer
kernel bytes than looping through step 7 would have been.

`mem_reown_x` is `mem_free_owner_x` with one instruction changed — the same
`cli`-bracketed walk of `mem_tab`, storing DX into `MC_OWN` where it matches
BX instead of clearing `MC_SEG`. It belongs beside it in memory.inc.

### 5.5 The tooling side

`tools/os88pkg.py` gains two things and no format:

* **the pad** — a part declared as the program is padded to `image + bss` from
  its own header, §51.1.2's strip in reverse;
* **one check** — that part is a valid v3 package image, and **its header's
  name and icon flag match the loader's**. The Disk window draws the *file's*
  header before any of this runs (`ld_icon`), and step 9 registers the
  *program's*, so two different readers see two different headers and they
  must agree.

## 6. The bill

Estimated, with the comparable each figure is taken from.

| where | what | bytes |
|---|---|---:|
| `.text` | the table cell — `OSAPI_XCELL` is 8 bytes exactly | 8 |
| `.text` | its `call COLD_SEG:..._x` thunk, as `osapi_mem_movable`'s | 5 |
| `.bss` | `ld_rehome` + `ld_rehsz` (words) + `ld_rehomed` (byte) | 5 |
| `.cold` | the slot body: `mem_own` fence, bank DX and AX, refuse a repeat | ~34 |
| `.cold` | `ld_start`'s arm above, the bound test included | ~80 |
| `.cold` | `mem_reown_x`, measured against `mem_free_owner_x`'s 20 | ~22 |
| `.cold` | `mem_own`'s `inst_of_seg` arm (4.1) | ~12 |
| | **total resident** | **~165** |

Against the tree as it stands: `.text+.bss` has **8,407** left of
`KERN_CODE_MAX`, and only 13 of this lands there; `.cold` has 457 left in its
current rung and this is ~148; the footprint has 17,408 spare. **No rung is at
risk**, which is stated because it is true and not because it is the argument —
CLAUDE.md's rule is that the price of a byte is a byte, and this is 150 of
them.

### 6.1 What they buy

* **The loader's claim, per instance.** 1,267 bytes of image plus `OP_BSS`'s
  86, which is a **2 KB claim** at the allocator's KB granularity — measured,
  on Clear Skies' own shape (5.1).
* **The parts standard leaves the program's segment entirely.** 800 bytes
  today for a plain consumer (§20.12.9) — and, more to the point, the program
  stops being charged for its own loader at all.
* **The program is an ordinary package again.** No gates, no `op_seg`, no
  second segment discipline, no `cs:` on its own tables. For Clear Skies that
  is the difference between the engine being a far-called part and the engine
  simply being the program.

### 6.2 What it does not buy

The **carve is the same size** — the program and its bss occupy exactly the
memory they occupied as parts. This is not a memory-saving change of any
scale; it is ~1 KB of heap and a clean segment. Anyone hoping for more should
read §6.1's third bullet as the actual prize.

---

## 7. Refusals and alternatives

**The kernel doing the loading itself** — a flags bit meaning "the real image
is part N". That is the design
docs/plans/completed/O88-MULTISEG-PLAN.md §1 built to five waves and threw
away at **2,560 resident bytes**. Re-home is ~150 because the *package* does
every hard thing (sizing, claiming, reading, expanding) and the kernel only
re-points at the end.

**Shrinking the loader's claim instead of freeing it** (`mem_regrow` to
nothing) — the same bookkeeping plus an allocator path, and it leaves a claim
record occupied out of `MEM_MAX`.

**Making the program its own claim** so `mem_own` accepts it without §4.1's
arm — `op_load` deliberately makes ONE claim because `MEM_OWNER_MAX` is 8
(§50), and a second one for the program would be a second thing to free and
to relocate. §4.1 is eleven bytes and answers a better question.

**Letting the loader survive and just not run** — that is today.

**A magic block or a packer stamp for the handoff** — both were costed and
both are unnecessary; 5.2 has the reasoning and the eight bytes that replace
them.

---

## 8. Risks, in the order they would bite

1. **§4.1.** Without the `mem_own` arm this ships and fails at the first
   `OSAPI_MEM_CLAIM` a re-homed program makes — which for most packages is
   after the window is up. Build the arm first, with its own gate.
2. **Compaction.** A package region is claimed `mem_claim_hi_x`, top-down and
   pinned. The carve is an ordinary claim and is *also* pinned by default
   (`MC_RLOC` = 0, §66), so a re-homed program is as unmovable as it was — but
   `mem_cp_plan` and `mem_frameless` were written when "the instance's region"
   and "a claim base" were the same thing. Audit both before building.
3. **`ld_unreserve` on an abort after the re-home.** It frees by slot and by
   `[ld_base]`; the arm sets `[ld_base] = Y` before anything can fail, so the
   carve is swept. Worth a red-run test rather than an argument.
4. **A loader that returns a window.** 4.2's `BX = 0` check makes it a
   refusal rather than a callback into freed memory.
5. **Y's bss overrunning its part.** Y's header is a FILE and a foreign tool
   may write any `LD_H_BSS` it likes - SPEC.md 51.1.2's own warning, one
   format along. `OSAPI_PKG_REHOME` takes AX = the bytes available at DX and
   the kernel refuses `image + bss` past it (5.3).
6. **A part that arrives short.** The handoff vector lives in the program's
   bss, which arrives IN THE PART rather than being zeroed by the kernel
   (5.4). The parts standard already guarantees the run arrives - `op_want`,
   `op_bend` and `op_unpack`'s own expansion check - but this is the first
   thing that depends on that being true of the TRAILING bytes, which is
   where SPEC.md 20.12.2's `op_tail` arithmetic lives. Worth a gate that reads
   the vector back rather than an argument.

---

## 9. The gates this needs

* **`t_rehome` (fast)** — host-side: the loader's header and the program
  part's header agree on name and icon; the program part is a valid v3 image;
  and it is padded to `image + bss` (5.3).
* **`rehome` (soak)** — a `tests/rehome/` package in mseg's shape: the loader
  loads, re-homes, and the program's window title says so. Then read the
  guest: `I_SPTR` is the program's segment, the loader's claim is **gone from
  `mem_tab`**, the carve's `MC_OWN` is Y, **the handoff vector in the
  program's bss names the other parts** and their bytes are what they should
  be, and a claim the program makes afterwards **succeeds** — that last one is
  4.1's whole gate and must go red without the arm.
* **`rehomeclose` (soak)** — close it and assert `mem_avail` returns to what it
  was before the launch. The leak §3 describes is invisible until you look.

---

## 10. Sequencing

1. **`mem_own`'s `inst_of_seg` arm**, on its own, with a gate. It is
   independently correct, it is the attribution primitive, and everything else
   here depends on it.
2. `mem_reown_x`, and the `MC_OWN` re-stamp.
3. `OSAPI_PKG_REHOME` and `ld_start`'s arm.
4. `tests/rehome/`, the three gates.
5. `os88pkg.py`'s header agreement check.
6. Only then, a real consumer.
