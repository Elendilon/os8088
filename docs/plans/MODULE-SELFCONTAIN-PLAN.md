# A module that is fully contained on disk

**Status: W0 BUILT (6.1); W1–W5 proposed.** The measurement behind it is
`docs/reports/MODULE-RESIDENT-DATA-2026-09-12.md`, taken at `6c91a3a`, and
every byte figure in this document comes from it or from
`tools/os88modcost.py --api` on that same commit. Re-derive them with
`python3 tools/os88modcost.py [--small] [--api]` rather than quoting this file
at a tree that has moved on — section 5's list in particular changes whenever
the public table does, without anybody touching a module.

**The owner has committed to this work.** What follows is ordered and costed,
not offered.

The ask, in the owner's words:

> Make a plan to make these fully contained on disk (just like a normal app
> would be, except these get special "permissions" to play in the kernel).

## 0. Read this before costing it: the prize is HUNDREDS of bytes

**329 bytes on `kern_big`, 473 on `kern_small`**, and the documented refusals
inside those (SPEC.md 2.8.6.1's `dskw_fmt_tab`, 56 bytes, and its six Control
Panel list names) take the realistic figure to **~270 / ~420**.

**Say the share honestly, because it will be quoted.** On `kern_small` at
`6c91a3a` — `KERN_SIZE` 75,776, `.text` 37,445, `.bss` 4,242 — 473 bytes is
**0.62% of `KERN_SIZE` and 1.13% of `.text` + `.bss`**. It is not ~6% of the
kernel on any base, and the figure is written here so that nobody has to
reconstruct it later. **The work is worth doing anyway** and the owner has
called it: every byte is resident on every machine for ever, `KERN_BUDGET` is
billed in 512-byte rungs, and 473 is most of one on the machine that has the
least room.

That decides the SHAPE of it rather than whether to do it: this is a plan
with a byte budget of its own, and a wave that spends 100 resident bytes of
mechanism to recover 115 is a wave that should not be taken. Section 3's
design exists in the form it does because it costs **zero resident bytes on
three of its four parts**, and that is the whole reason the arithmetic works.
Section 5 is the same rule applied to a tempting shortcut, and it refuses it.

**Why the number is small is itself the finding.** SPEC.md 2.8.6 already
opened the door for strings and SPEC.md 2.8.6.1 records the three bodies that
walked through it — the cloner's prompts, the formatter's, and the Control
Panel's 443 bytes of page text. **The largest single body of module data left
the kernel two arcs ago.** What this plan is about is the remainder, and the
remainder is mostly *not strings*: it is `.bss` state, small tables, and
bodies that only an image calls.

And **the overlay is not part of it.** The measurement's section 3 is the
negative result: `.ovl`/`.ovlw` hold **two bytes** of resident data between
them. Do not open a wave for it.

## 1. What is true today, and it is the published rule

SPEC.md 2.8.1: *"A module's **data does not move**. It stays in `.text`,
reached through DS exactly as cold code's data is."*

`tools/os88ovlchk.py` enforces it, and `kernel/ctrl.inc:5482` carries the
comment of somebody who was caught by it. So a module today is **half** an
app: its code ships as a file and is read into a claim (SPEC.md 2.8), and its
data is welded into the kernel for the life of the machine.

The three populations, and they want three different answers:

| population | `kern_big` | `kern_small` | answer |
|---|---:|---:|---|
| read-only `.text` data — tables, strings | 114 | 184 | into the IMAGE; the door is already open (SPEC.md 2.8.6) |
| `.bss` state — the module's own variables | 55 | 202 | into the CLAIM; **no mechanism exists**, section 3 is it |
| `.text`/`.cold` bodies only an image calls | 160 | 87 | into the IMAGE; ordinary code motion |
| far shims — `cw_*`, `dskf_*`, `drvf_*` | 111 | 84 | **mostly stay** — see 1.1 and section 5 |

### 1.1 The two doors, and which way each one faces

The phrase "the ABI" hides a fork, and the two halves have different answers.

**A module calling INTO the kernel is a far SHIM.** A module runs from a heap
claim with a `CS` of its own, so a near call into `KERNEL_SEG` or `COLD_SEG`
assembles happily and emits a displacement computed between two address
spaces — the bug `tools/os88ovlchk.py` exists to refuse, and
`kernel/disk.inc:7245` says so at the point of use. So each kernel routine a
module wants gets a four-byte landing pad:

```nasm
dskf_disk_read:   call disk_read_x     ; 3 bytes
                  retf                 ; 1
```

and every caller is inside an image — `call COLD_SEG:dskf_disk_read` at
`diskw.inc:4362` and `:4652` (`.modf`), `clone.inc:707` and `:2109` (`.modl`).
Two families, split by which segment they land in: **`cw_*` in `.text`**
(`call KERNEL_SEG:cw_clk_tobcd` from `clockw.inc`, which is `CTRL.DRV`'s image
on `kern_big`) and **`dskf_` / `drvf_` / `fmf_` / `mmf_` / `memf_` / `hbk_` /
`*_f` in `.cold`**.

This is why they pass a *named only from a module image* test so cleanly: it
is their definition. Nothing resident calls one — a resident caller uses the
near body (`disk_read_x`) directly. They exist solely to be far-called from an
image, which is also why they cannot move into one. The landing pad is the
thing the module calls to *leave*; moving it inside is moving the door into
the room.

**The kernel calling OUT to a module is `mod_fp`,** and it is not a shim at
all: a `.bss` table of far pointers dispatched as `call far [mod_fp + K]` with
K an assembly-time constant, armed by `mod_need` and pointed at `mod_gone`
when the module is out — never at zero, which would be a far call through the
divide-by-zero vector. It is **112 bytes on `kern_big` and 140 on
`kern_small`**, plus the resident thunks that dispatch through it (`fcp_arm`,
`fcp_load`, `cp_open`, …).

`mod_fp` is **not** in the 440/557 above and correctly so: `.text` and `.cold`
both name it, so it fails the *module only* test. It is recorded here because
the honest resident bill for the module ABI is the shims **plus** `mod_fp`
**plus** the thunks — more than the 111/84 the table shows. None of it is
movable, so the 329/473 does not change.

## 2. The two facts that make it cheap

### 2.1 The claim is already bigger than the image

`mod_need` sizes a module's claim with `mem_bytes_kb_x` — `add ax, 1023` / `shr ax, 10` — so
every module already owns memory past the end of its image, for exactly as
long as it is loaded:

| | image | claim | slack |
|---|---:|---:|---:|
| `CTRL.DRV` (`kern_big`) | 7,542 | 8,192 | 650 |
| `FORMAT.DRV` | 1,129 | 2,048 | 919 |
| `CLONE.DRV` | 5,810 | 6,144 | 334 |
| `HIBER.DRV` | 3,398 | 4,096 | 698 |
| `CTRL.DRV` (`kern_small`) | 4,709 | 5,120 | 411 |
| `FILECP.DRV` | 2,161 | 3,072 | 911 |
| `FDLG.DRV` | 3,243 | 4,096 | 853 |

**The tightest slack is 334 bytes and the largest single item in the whole
measurement is 56.** Every module's private data fits inside room the machine
has already set aside for it, so the move costs **no heap at all** — not "a
little heap", none.

### 2.2 A module may write to its own image

`mov [cs:si], al` assembles under this tree's `cpu 8086` and `-w+error`; it is one prefix byte, which on
an 8088 is the fetch floor's ~4.3 cycles (PERFORMANCE.md Part 2) rather than
the ALU's 2. SPEC.md 2.8.6 established that a module may *read* through `CS`;
nothing about writing is different, because the claim is ordinary RAM and the
module's `CS` is its base.

## 3. The mechanism: a module gets a `.bss` of its own

One new idea, and the rest is `.text`/`.bss`'s own relationship one level
down.

### 3.1 A nobits section per image

Beside `section .modc` goes `section .modcb nobits vfollows=.modc`, with `MODC_BSS equ modcb_end - $$`.
Labels in it are addressed `[cs:label]` exactly as image data is, because
both are offsets from the same claim base. It emits nothing, so **the file
on the floppy does not grow**.

### 3.2 Nothing claims it, because the claim is already made

An assembly-time assertion beside the existing
`MODC_SIZE > MOD_MAX_KB*1024` one:

```
%if MODC_SIZE + MODC_BSS > ((MODC_SIZE + 1023) / 1024) * 1024
%error "the ctrl module's bss does not fit its claim's KB rounding"
%endif
```

**This is the part that costs zero kernel bytes**, and it is why the
arithmetic in section 0 works at all. Its risk is a cliff rather than a
slope: a module that grows past a KB boundary loses its bss room all at once.
The assertion is what makes that a build failure in the file that grew rather
than a corruption at run time — the same shape as `times MOD_NENT - X dw 0`
(SPEC.md 2.8.1).

**The named fallback, if a module outgrows its slack:** a word per module in
`mod_tab`, added to `AX` before `mem_bytes_kb_x`. That is 8 resident bytes on
`kern_big` and 12 on `kern_small`, and it should be taken **when the
assertion fires and not before** — spending it up front buys nothing and is
exactly the "design for rungs" argument CLAUDE.md refuses.

### 3.3 `mod_need` zeroes it, once

After `dskw_read_x` returns, the bytes between the image end and the claim end are whatever the heap had. `mod_need`
already holds both figures — `BP` is the image size and `AX` was the claim in
KB — so the zeroing is a `rep stosw` of ~12 bytes of `.cold`, and it is
`.cold` rather than `.text`. **It belongs in `mod_need` and not in each
module's arm entry**: one place cannot be forgotten by the next module, and a
forgotten one reads uninitialised state, which is silent.

Cost: **~12 bytes of `.cold`, against 329/473 recovered.** That is the only
resident spend in the whole design.

### 3.4 The part that is NOT mechanical: state that must outlive the drop

`kernel/filecp.inc:2058` states it in the design's own words:

> What makes an arm safe to drop on is that the CLIPBOARD IS `.bss`:
> `fcp_arm` records a selection in resident data and the image is not needed
> again until the paste.

So a module's `.bss` is **two populations**, and only one may move:

* **pending** — outlives `mod_drop`, because the next thing that reads it is
  a later load. For `FILECP.DRV` that is `fcp_op`, `fcp_drv`, `fcp_cwd`,
  `fcp_type`, `fcp_name`: **19 bytes, and they stay in the kernel.**
* **scratch** — alive exactly as long as the image. `FILECP.DRV`'s other
  ~123 bytes are one operation's own state, and a suspended paste still owns
  the image while the user reads the overwrite question (`fcp_fin` drops on
  every return that is not `FCPS_ASK`), so the suspension is not a gap.

**Every wave owes this classification before it moves a byte**, and the
answer is a property of the feature rather than of the variable. Getting it
wrong is silent: a clipboard that forgets what was copied, on a machine that
otherwise works.

## 4. The gate, because both directions of this mistake are silent

SPEC.md 2.8.6 already says what goes wrong: a string in the image read
through DS letters whatever is at that offset in `KERNEL_SEG`, and a string
in `.text` read through `CS` does the same in the other direction. It
assembles, it runs, and it draws rubbish.

`tools/os88ovlchk.py` already carries the two halves that catch it —
half 1 (*a memory operand naming module data must carry a `cs:`*) and half 2
(*a module-data label may appear only at its own definition or as an argument
of that image's registered macros*). **`.modc` has both halves; `.modl` and
`.modf` have half 1 only** (SPEC.md 2.8.6), and `.modd`/`.modp` have never
needed either because they have no image data yet.

So the gate work per wave is: extend half 1's notion of "module data" to the
new `.mod?b` sections, and **give the image a registered macro pair before
moving its first string** — half 2 is a construction rule rather than an
analysis, which is what makes it exact, and it only works on an image that
was written for it.

**And a ratchet, in `soak`.** `tools/os88modcost.py` prints the figure; a
row that asserts it against a checked-in number, which may only go **down**,
is SPEC.md 6.6's shape for the same reason — a new module-only `.text` word
should be an argument somebody wins, not a thing that accretes. It is **7.4
seconds per build arm**, so it is a `soak` row and not a `fast` one:
`fast` is 13.7 s of a 30 s budget and is paid for by everybody
(docs/WRITING-TESTS.md 2.1).

## 5. Can a shim be replaced by a now-public call? Six of them, and no more

**The question was the owner's and it is the right one to ask**: this tree has
been publishing disk and other internals as `OSAPI_*` slots, and a public slot
is already a far door. If the module could call the public cell, the private
shim deletes.

**It works mechanically, and exactly.** An `OSAPI_*` slot is a far address
literal in the SDK — `%define OSAPI_MEM_AVAIL KERNEL_SEG:0x0210` — so
`call OSAPI_MEM_AVAIL` assembles to the same `call far seg:off` a module
already emits at `call COLD_SEG:dskf_disk_read`. No new mechanism, no new
instruction, same cost. And `OSAPI_SLOT` is

```nasm
push ds
push cs          ; the cell is in .text, so CS = KERNEL_SEG
pop ds
call <near body>
pop ds
retf
```

which for a module — whose DS is *already* `KERNEL_SEG` — is the shim's
semantics precisely, plus four wasted instructions. The substitution is exact
rather than nearly so.

### 5.1 …but it only pays where the slot ALREADY exists

**A cell is 8 bytes and a shim is 4**, both asserted in their macro comments
(`OSAPI_SLOT 1 ; 8 bytes exactly`). The table is **contiguous** — 167 cells
across 168 positions at `6c91a3a`, one hole — so a new slot goes on the end
and costs its 8.

> **Publishing a routine in order to delete its shim spends 8 to save 4.** It
> is a net loss of 4 resident bytes, and it also commits the SDK for ever:
> a slot number is a promise to every package ever built against it.

So this avenue is worth exactly what is already lying on the ground, and the
tree was walked to find out. `python3 tools/os88modcost.py --api [--small]`
resolves every shim and every cell through its thunk chain to the body it
lands on, and reports where they meet:

| shim | → body | public cell | `kern_big` | `kern_small` |
|---|---|---|---:|---:|
| `mmf_mem_avail` | `mem_avail_x` | `0x0210` SLOT | 4 | 4 |
| `cw_osapi_snd_tone` | `osapi_snd_tone` | `0x00E8` SLOT | 4 | 4 |
| `cw_wm_saveu` | `wm_saveu` | `0x0378` SLOT | 4 | 4 |
| `cw_gfx_vline` | `gfx_vline` | `0x0030` SLOT | — | 4 |
| `cw_wm_create` | `wm_create` | `0x0078` **XCELL** | — | 4 |
| `cw_wm_destroy` | `wm_destroy` | `0x0398` SLOT | — | 4 |
| | | | **12** | **24** |

**TAKEN — W0, and it came to −28 / −24; 6.1 says why it beat the row above.**

**Six of thirty-five, and the other twenty-nine stay.** `mmf_mem_avail` is the
clean worked example and shows the shape of the duplication: `memory.inc`
carries `mmf_mem_avail: call mem_avail_x` for the module *and*
`mmf_osapi_mem_avail: call osapi_mem_avail_x` for the public path — and
`osapi_mem_avail_x` is a bare `jmp mem_avail_x`. Two doors, one room.

### 5.2 What the twenty-nine are, and why publishing them is refused

* **The raw sector transfers** — `dskf_disk_read`, `dskf_disk_write` — have
  **no public equivalent and should not get one.** The published disk surface
  is file- and volume-level (`OSAPI_FILE_READ`, `OSAPI_FILE_READ_AT`,
  `OSAPI_VOL_*`); `disk_read_x`/`disk_write_x` are `int 13h` sector moves the
  formatter and cloner need precisely *because* they work below the file
  layer. Publishing them hands every package an unvalidated sector writer to
  save 8 bytes of shim while spending 16 bytes of cell.
* **The driver internals** — nine `drvf_*`, `kern_big`'s alone, 36 bytes —
  are `drv_*_x` bodies behind the Control Panel's Drivers page. `kern_small`
  has **no loadable drivers at all** (`OS88_DRIVERS` is `KERN_BIG`-only), so
  those labels do not assemble there and the row reads 0 — the same reason
  `drv_sysname` measures 0 on that build.
* **The clock's six `cw_clk_*`** are `CTRL.DRV`'s write half (SPEC.md 37.0.1)
  and are internal by design: the panel writes the chip, nothing else may.
* The rest (`fmf_*`, `hbk_*`, `cw_menu_*`, `cw_vid_*`, `cw_thm_set`,
  `cw_inst_fhome_idx`, `cw_wm_pkgcall`) are one-caller helpers with no
  package-facing meaning at all.

### 5.3 One caution before the wave

`cw_wm_create`'s cell is an **XCELL**, not a SLOT — `push bp / mov bp,
wm_create / jmp api_x`, and `api_x` stamps ES from the caller's DS. For a
module that lands ES = `KERNEL_SEG`, and the template a module passes IS
kernel data, so it is very probably right — but it is the one row here that
must be **checked at the call site** rather than substituted on the strength
of the table. The other five are plain SLOTs and are exact.

## 6. The waves, cheapest and least risky first

Each wave ends with `python3 tools/os88modcost.py` re-run and the figure
quoted (`--api` too, after W0), and with `kernsize`'s own line — a wave that moved no `KERN_SIZE`
byte still moved `.text` bytes, and those are what the report counts.

**W0 — the six redundant shims. BUILT: −28 bytes on `kern_big`, −24 on
`kern_small`.** Section 5's table, taken: each call site points at the public
cell and the private shim is gone. Six shims, seven call sites, no mechanism
and no data touched. See 6.1 for what it came to, which is **more than this
plan predicted, for a reason worth keeping**.

### 6.1 What W0 came to, and the two things it found

`.text` **49,524 → 49,504** and `.cold` **39,264 → 39,256** on `kern_big`
(−28); `.text` **37,445 → 37,425** and `.cold` **26,176 → 26,172** on
`kern_small` (−24). Measured against a baseline taken on the same tree before
the change — **not** against `kernsize`'s blessed baseline, which was stale
here and reported `-1,547` for a twenty-byte edit (CLAUDE.md's own warning
about that line, and it is why the figures above are a before/after and not a
`sum`).

**It beat section 5's prediction of 12 on `kern_big`, and the reason is a hole
in the measurement rather than luck.** The audit counts only what is named
*exclusively* from a module image, so three of the six — `cw_gfx_vline`,
`cw_wm_create`, `cw_wm_destroy` — did not appear in `kern_big`'s tally at all:
on that build `fdlg.inc` is resident `.cold` rather than `.modd`, so `.cold`
names them too. **But a `.cold` caller cannot near-call `.text` either** — it
has its own vstart — so it wants the identical far call, and the public cell
serves it just as well. The lesson for W1–W5: *the audit's figure is a floor
for shims as well as for data, and a shim shared with `.cold` is still worth
deleting.*

**The `wm_create` XCELL paid twice.** 5.3 flagged it as the one row to check
at the call site rather than substitute on the strength of the table — and the
check turned up a bonus. `api_x` sets `ES` = the caller's DS and puts it back,
which for a module is `ES = KERNEL_SEG`; `fdlg.inc` was spelling that out by
hand (`push es / push ds / pop es` … `pop es`) around the shim call. Those
four bytes went with it, which is why `.cold` fell 8 on `kern_big` where only
one 4-byte shim lived there. On `kern_small` the same four bytes come out of
`FDLG.DRV`'s image instead of the kernel, so they do not show in `kernsize` at
all — a file getting smaller, which is the shape this whole plan is after.

**A measurement trap, recorded because it cost a cycle.** The cells are named
with a bare `apic_*` label so the address is DERIVED rather than a second copy
of the slot number (`tests/unit/t_mirror.py`'s subject). A bare label inside
the table then **absorbs every unlabelled cell after it** in any tool that
sizes a label by the distance to the next one — `os88modcost.py` read
`apic_wm_destroy` at **440 bytes** and the totals jumped 440 → 1,116. The cell
is resident for the package ABI whether a module names it or not, so its
marginal cost here is zero; the tool excludes `apic_*` now and says why. The
totals came back to **428 / 533**, which is 440 − 12 and 557 − 24 exactly.

**W1 — `FORMAT.DRV`'s boot-sector template. ~30 bytes, no UI risk.**
`dskw_fmt_jmp` (11), `dskw_fmt_lab` (11) and `dskw_fmt_typ` (8) are bytes the
formatter *writes into a sector*, so SPEC.md 2.8.6's ordering rule is
satisfied trivially: nothing draws them, and nothing can want them while the
image is out. Half 1 of the gate covers the reads. **It is first because it
proves the route with no screen in it.** `dskw_fmt_tab` (56) is NOT in this
wave — SPEC.md 2.8.6.1 refuses it, and re-arguing that is a separate decision
with `dskw_fmt_row_x`'s `SI`-into-the-table contract to answer.

**W2 — the mechanism, proved on `FILECP.DRV`'s scratch state. ~123 bytes of
`kern_small`.** Section 3 built: the nobits section, the assertion, the
`mod_need` zeroing, the gate extension. `FILECP.DRV` is the right first
customer because section 3.4's split is *already written down in its source*,
so the wave spends its effort on the mechanism rather than on the
classification. It is also `kern_small`'s, which is the machine with 128KB in
it.

**W3 — `FDLG.DRV`. ~94 bytes of `.text` data and ~81 of `.bss`,
`kern_small`.** Eleven short strings (`fdlg_s_*`) and `fdlg_tpl`, plus
`fdlg_row`/`fdlg_nsave`/`fdlg_num`. The strings need half 2 and therefore a
registered macro pair, which is the `CPS`/`CPSTAGE` treatment `.modc` already
has — write it before the first string moves, not after. **The ordering
argument is the wave's real work**: a file dialog's labels are drawn by
`fdlg_paint` inside the image, but `inst_fname` is the ANSWER buffer and a
caller reads it *after* the dialog closes, so it stays.

**W4 — bodies only an image calls. ~160 bytes, `kern_big`.**
`drv_status_x` (40), `sched_mode_set` (20), `vid_disp_relayout` (10),
`drv_cp_count_x` (6), `ssf_cfg` (6), `hb_onup` (6) and the rest. This is
ordinary code motion — `.cold`/`.text` into `.modc` — and its hazard is the
near/far rule rather than the data rule: a body that moves into an image must
reach the kernel through a shim, and `tools/os88ovlchk.py`'s near-call check
is what says so. **Check the shim arithmetic before assuming a win**: a
40-byte body that needs a 4-byte far shim nets 36, and one that needs three
nets 28.

**W5 — `CTRL.DRV`'s leftovers and `HIBER.DRV`'s. ~90 bytes.** `cp_sbuf` (28)
is the interesting one and it is shared between `.modc` and `.modh`, so it is
the first case where two images want one buffer — the honest answer is
probably a copy in each (SPEC.md 2.8.6's *"A string in an image may be COPIED
rather than shared"*, in the other currency), and 28 bytes of two *files*
against 28 of RAM is the trade to state rather than assume.

## 7. What is refused, and why, so it is not re-derived

1. **The boot overlay.** Two bytes. The measurement's section 3 has the
   arithmetic and the false positive that makes it look like 492.
2. **`dskw_fmt_tab`, 56 bytes.** SPEC.md 2.8.6.1 already refused it:
   `dskw_fmt_row_x` hands callers an `SI` into it and every one dereferences
   `[si+DFMT_*]`. Re-opening that means changing the contract of a routine
   with resident callers, which is a bigger change than 56 bytes buys.
3. **The six Control Panel list names.** SPEC.md 2.8.6.1: *"a list name may
   equally be a driver's staged one and `cp_list` draws it through DS."*
   They are the reason tier 2 of the measurement is 62 bytes rather than a
   second prize.
4. **The far shims, 111 / 84 bytes** — except section 5's six. They are the
   door a module calls to LEAVE its image (1.1), so moving one inside is
   moving the door into the room.
5. **Publishing a kernel routine in ORDER to delete its shim.** A cell is 8
   bytes and a shim is 4, and the table is contiguous, so it spends 8 to save
   4 and commits the SDK for ever (5.1). Where a slot already exists the
   substitution is free and W0 takes it; where one does not, the shim is the
   cheaper of the two doors. This is the one avenue that looks like a
   shortcut and is not.
6. **A `mod_tab` size word up front** (section 3.2's fallback). Take it when
   the assertion fires. Spending 8–12 resident bytes to avoid a build error
   that has not happened is the rung-shaped reasoning CLAUDE.md refuses.
7. **Making the claim purgeable so a module can be shed under pressure.**
   Out of scope here and already designed and refused elsewhere: SPEC.md
   2.8.3 and docs/plans/completed/ONDEMAND-PLAN.md 7.1/7.2 — shed-and-retry
   would free the code that is running, and a pin is what that needs.

## 8. Open questions somebody should settle before W2

1. **Does anything read a module's `.bss` while the image is out, other than
   the classified "pending" set?** The measurement's instrument cannot answer
   it — a source scan sees the reference, not the lifetime. The honest test
   is per label and by reading the call sites, and W2's `FILECP.DRV` is the
   worked example because its source already states the answer.
2. ~~**Does `drv_find` answer the UNPACKED hint for a `'CZ'` module?**~~
   **ANSWERED: yes.** `kernel/drvvol.inc:189` says it in capitals — *"THE
   SIZE IS WHAT THE FILE BECOMES, NOT WHAT IT OCCUPIES"* — and the code reads
   `dskw_raw+DSK_R_CZL`/`DSK_R_CZH` when the entry carries a `'CZ'` mark
   (SPEC.md 20.14.1). So `mem_bytes_kb_x` already rounds the UNPACKED size,
   which is the figure section 3.2's assertion is written against, and the
   slack table in section 2.1 is real on a compressed floppy as well as an
   uncompressed one. Nothing to do.
3. **What does `mod_need`'s zeroing cost on a 4.77 MHz 8088?** ARITHMETIC,
   not measured: 650 bytes is 325 words, and `rep stosw` on an 8088 splits
   each into two bus cycles at ~17 clocks a word, so ~5,500 cycles — about
   **1.2 ms** against a module load that is already one or more `int 13h` at
   ~400 ms each (PERFORMANCE.md). It is noise, but W2 should say the measured
   number rather than this one.
4. **Is there a module whose slack is about to close?** `CLONE.DRV`'s is 334
   and it carries the LZB compressor as its second entry (SPEC.md 20.15).
   Check its growth before giving it a bss.
