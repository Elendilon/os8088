# A module that is fully contained on disk

**Status: PROPOSED. Nothing here is built.** The measurement behind it is
`docs/reports/MODULE-RESIDENT-DATA-2026-09-12.md`, taken at `6c91a3a`, and
every byte figure in this document comes from it. Re-derive them with
`python3 tools/os88modcost.py [--small]` rather than quoting this file at a
tree that has moved on.

The ask, in the owner's words:

> Make a plan to make these fully contained on disk (just like a normal app
> would be, except these get special "permissions" to play in the kernel).

## 0. Read this before costing it: the prize is HUNDREDS of bytes

**329 bytes on `kern_big`, 473 on `kern_small`**, and the documented refusals
inside those (SPEC.md 2.8.6.1's `dskw_fmt_tab`, 56 bytes, and its six Control
Panel list names) take the realistic figure to **~270 / ~420**.

That is not a disappointment and it is not an argument against the work, but
it decides the SHAPE of it: this is a plan with a byte budget of its own, and
a wave that spends 100 resident bytes of mechanism to recover 115 is a wave
that should not be taken. Section 3's design exists in the form it does
because it costs **zero resident bytes on three of its four parts**, and that
is the whole reason the arithmetic works.

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
| far shims — `cw_*`, `dskf_*`, `drvf_*` | 111 | 84 | **stay.** They are what the image calls to get OUT |

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

## 5. The waves, cheapest and least risky first

Each wave ends with `python3 tools/os88modcost.py` re-run and the figure
quoted, and with `kernsize`'s own line — a wave that moved no `KERN_SIZE`
byte still moved `.text` bytes, and those are what the report counts.

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

## 6. What is refused, and why, so it is not re-derived

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
4. **The far shims, 111 / 84 bytes.** They are the ABI out of the image.
   Moving one into the image is moving the door inside the room.
5. **A `mod_tab` size word up front** (section 3.2's fallback). Take it when
   the assertion fires. Spending 8–12 resident bytes to avoid a build error
   that has not happened is the rung-shaped reasoning CLAUDE.md refuses.
6. **Making the claim purgeable so a module can be shed under pressure.**
   Out of scope here and already designed and refused elsewhere: SPEC.md
   2.8.3 and docs/plans/completed/ONDEMAND-PLAN.md 7.1/7.2 — shed-and-retry
   would free the code that is running, and a pin is what that needs.

## 7. Open questions somebody should settle before W2

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
