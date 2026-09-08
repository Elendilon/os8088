# THE LOADER FREES ITSELF — a package's shell as a disposable segment

> **Status: RESEARCH, nothing built.** The cost below is estimated against
> measured comparables in this tree and every claim is sourced to a line of
> kernel. It is ~150 resident bytes, and §6 is where that number comes from.
>
> **Read §4.1 first if you read nothing else.** The mechanism does not work
> without one further kernel arm, and it is not the one this session expected:
> after the switch the running program is *inside* a claim rather than at the
> base of one, and `mem_own` — the fence on every memory slot — says no to it.
> The fix is eleven bytes and a routine that already exists.

---

## 1. The ask

A package that uses parts pays for its own loader, for ever:

* the SHELL's segment claim — its image and bss — is held for the life of the
  instance, and after `op_load` returns there is nothing in it anybody needs;
* the parts standard's own code sits inside the running program's 61,440
  bytes, which is exactly the budget the program ran out of and went to parts
  to escape.

The proposal: the shell loads the parts, tells the kernel *"the program is at
segment Y"*, returns, and is freed. The program then runs from Y **as though
it had never used parts at all** — an ordinary single-segment package, no
`OS88_PARTS_*`, no `op_seg`, no gates, and the whole 61,440 to itself.

Lazy parts are excluded and that is the ask's own scope: `op_fetch` and
`op_drop` are shell code, and a shell that has been freed cannot fetch.

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

Better still: **step 7 is the loop-back target.** It zeroes the bss and falls
into step 8. So the whole re-home is *"re-point `ld_base`/`ld_img`/`ld_bss`/
`ld_ent` at Y and jump to step 7"* — the second entry is then called by the
same three instructions that called the first, with the same contract, and Y's
bss is zeroed by the same `rep stosb`.

### 2.1 Why the kernel has to be the one to call it

The shell cannot far-call Y's entry itself and then be freed: it would be on
the call stack. Control must leave the shell segment entirely before the claim
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

* the shell's **region** is owned by the slot — it is one claim and it is the
  one to free;
* the **carve** holding the parts is owned by **X, the shell's segment** — and
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

### 4.2 What the shell may not do

Only two things stamp a segment *before* step 9:

* **a window** — `wm_create` takes `W_SEG` from ES, and every later callback
  is far-called at `{W_SEG, PKG_DISP}`. A shell that creates a window would
  leave the kernel calling back into freed memory.
* **a worker** — already impossible from an entry proc.

So the rule is one line: **a re-homing shell creates no window; Y's entry
proc does.** The kernel can enforce it for free — the entry returns BX, and a
re-homing entry must return BX = 0. That is a `cmp`/`jne` on a path that
already tests CF.

Everything else an entry proc might do is stamped by **slot**, not segment —
the sound grant (`snd_inst`, set to the record around the call at
loader.inc:1005), the XMS release record, the toast — and survives untouched.

---

## 5. The design

### 5.1 The package side

```
    OS88_HEADER 'MYAPP', sh_entry, OS88_F_ICON | OS88_F_PARTS
%include "os88parts.inc"
    OS88_PARTS_BEGIN 2
      OS88_PART OP_SEG                  ; 0  THE PROGRAM - an ordinary package
                                        ;    image, header and all
      OS88_PART OP_ASSET, OP_ZERO, 12   ; 1  ...and its bss, zeroed by op_scrub
    OS88_PARTS_END
sh_entry:
    call op_load
    jc .out
    xor al, al
    call op_seg                         ; AX = the program's segment
    call op_rehome                      ; ...and the kernel takes it from here
.out:
    xor bx, bx                          ; no window: Y's entry makes it
    ret
```

`op_rehome` is four instructions over `OSAPI_PKG_REHOME`. The shell is then
the parts library (800 bytes gated, §20.12.9) plus about thirty — call it
**~1 KB of image that is freed the moment the program starts**.

**The program is an ordinary package.** It includes no parts header, calls no
`op_*`, and does not know it was loaded this way. That is the whole point:
`apps/skies/skies.asm` would go back to being what it was before any of this,
at its full 61,440.

### 5.2 The kernel side

A new X slot, `OSAPI_PKG_REHOME` — **DX = the segment the program is at**,
ES = the caller's (the fence). It banks DX in `[ld_rehome]` and returns; it
does nothing else, because the shell is still executing and nothing may move
under it.

`ld_start` gains one arm between steps 8 and 9:

```
    ; --- 8a. THE RE-HOME (a new SPEC.md 20.12 subsection) ------------------
    cmp word [ld_rehome], 0
    je .reg                     ; the ordinary launch, untouched
    <refuse a second one - once per launch>
    <BX must be 0: a re-homing entry owns no window>
    mov es, [ld_rehome]
    xor si, si
    call ld_hdr_ok              ; the .o88 prologue, on the part - it is the
    jc .abort                   ; same five tests, and it is already here
    <read LD_H_IMG / LD_H_BSS / LD_H_ENT into ld_img / ld_bss / ld_ent>
    <ld_need = image + bss, rounded as step 5 rounds it>
    mov bx, [ld_base]           ; --- the carve and every other claim the
    mov dx, [ld_rehome]         ;     shell made, re-owned X -> Y (§3)
    call mem_reown_x
    call ld_slot                ; --- and the shell's own region, freed: it
    mov dx, [ld_base]           ;     is owned by the SLOT, so this is one
    call mem_free_x             ;     claim by base and not a sweep
    mov ax, [ld_rehome]
    mov [ld_base], ax
    mov word [ld_rehome], 0
    jmp .start7                 ; ...and step 7 zeroes the bss and calls it
```

`mem_reown_x` is `mem_free_owner_x` with one instruction changed — the same
`cli`-bracketed walk of `mem_tab`, storing DX into `MC_OWN` where it matches
BX instead of clearing `MC_SEG`. It belongs beside it in memory.inc.

### 5.3 The tooling side

`tools/os88pkg.py` gains one check and no format: a part named as the program
must be a valid v2 package image, and **its header's name and icon must match
the shell's** — the Disk window draws the *file's* header before any of this
runs (`ld_icon`), so the two are seen by different readers and must agree. A
mismatch is a package whose tile says one thing and whose window says another.

---

## 6. The bill

Estimated, with the comparable each figure is taken from.

| where | what | bytes |
|---|---|---:|
| `.text` | the table cell — `OSAPI_XCELL` is 8 bytes exactly | 8 |
| `.text` | its `call COLD_SEG:..._x` thunk, as `osapi_mem_movable`'s | 5 |
| `.bss` | `ld_rehome` (word) + `ld_rehomed` (byte) | 3 |
| `.cold` | the slot body: `mem_own` fence, bank DX, refuse a repeat | ~30 |
| `.cold` | `ld_start`'s arm above | ~70 |
| `.cold` | `mem_reown_x`, measured against `mem_free_owner_x`'s 20 | ~22 |
| `.cold` | `mem_own`'s `inst_of_seg` arm (§4.1) | ~12 |
| | **total resident** | **~150** |

Against the tree as it stands: `.text+.bss` has **8,407** left of
`KERN_CODE_MAX`, and only 13 of this lands there; `.cold` has 457 left in its
current rung and this is ~134; the footprint has 17,408 spare. **No rung is at
risk**, which is stated because it is true and not because it is the argument —
CLAUDE.md's rule is that the price of a byte is a byte, and this is 150 of
them.

### 6.1 What they buy

* **The shell's claim, per instance.** ~1 KB of image plus its bss, rounded to
  the KB the allocator works in.
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

**Shrinking the shell's claim instead of freeing it** (`mem_regrow` to
nothing) — the same bookkeeping plus an allocator path, and it leaves a claim
record occupied out of `MEM_MAX`.

**Making the program its own claim** so `mem_own` accepts it without §4.1's
arm — `op_load` deliberately makes ONE claim because `MEM_OWNER_MAX` is 8
(§50), and a second one for the program would be a second thing to free and
to relocate. §4.1 is eleven bytes and answers a better question.

**Letting the shell survive and just not run** — that is today.

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
4. **A shell that returns a window.** §4.2's `BX = 0` check makes it a refusal
   rather than a callback into freed memory.
5. **Y's bss overrunning the carve.** The kernel zeroes `[ld_bss]` bytes past
   Y's image at step 7 — into memory the shell was supposed to have declared.
   The kernel can bound it against the carve only if it is told the carve's
   extent; the cheaper answer is that `op_rehome` is package code and can
   check it there, where `op_seg` and the row lengths already are.

---

## 9. The gates this needs

* **`t_rehome` (fast)** — host-side: the shell's header and the program part's
  header agree on name and icon; the program part is a valid v2 image.
* **`rehome` (soak)** — a `tests/rehome/` package in mseg's shape: shell loads,
  re-homes, program window says so. Then read the guest: `I_SPTR` is the
  program's segment, the shell's claim is **gone from `mem_tab`**, the carve's
  `MC_OWN` is Y, and a claim the program makes afterwards **succeeds** — that
  last one is §4.1's whole gate and must go red without the arm.
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
