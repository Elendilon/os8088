# The Last Drop Of Bytes

> Companion: **docs/LAST-DROP-PERF.md** is the same idea for CYCLES — optimisations
> built, measured, found correct, and shelved because they did not clear the price of
> their own footprint. This file is BYTES: code whose lifetime is **boot-only**, which
> could therefore move into `.ovl` and stop costing RAM at all, and which is not being
> moved today only because the blob has no room for it.

**Bodies that are provably boot-only, priced and ranked, so that the next time the
boot blob grows for any reason the rest can join it as a lookup rather than a fresh
investigation.**

This is not a list of things that are wrong. Every body below works, is in the right
section for the constraint that was live when it was written, and costs the machine
exactly what a resident byte costs. What each one *also* is, is a byte the machine is
paying for **for the whole session** to hold code that last executed before the
desktop appeared. `.ovl` is handed back to the heap at `spl_finish`
(`kernel/kernel.asm:2207` — *"It costs no RAM after that at all, and — this is the
point —"*), so an `.ovl` byte is a footprint byte **returned** where a `.text` or
`.cold` byte is one **kept**. Moving a boot-only body there is the only class of
change in this tree that gives a `KERN_BUDGET` rung *back*.

The reason for writing it down rather than re-deriving it is that an unmeasured
`.ovl` candidate list is wrong in **both** directions at once, and the mouse case
proved both in one afternoon: it was nearly disqualified wholesale by an edge that
turned out not to reach it (`mou_hotplug`, called from `ui_task` every pass), and the
register that nearly disqualified it had also silently **omitted 421 bytes** nobody
had counted. Every row here was closed by reverse reachability and measured by
whole-kernel re-assembly, and the negative results are in §7 with the killing edge
named, so nobody derives them a second time.

**Every entry carries the same five things**: the body and its bytes, the call-graph
evidence that it is boot-only, how it was measured, the price (blob, sectors,
`int 13h`, shims), and — the part that matters — **what would have to change for it
to become worth taking**. For almost every row that last answer is the same:
*the blob grows for another reason.*

---

## 0. The rule that decides every row

**`.ovl` is released at `spl_finish`, so a body with a single post-boot caller is
disqualified completely. There is no partial credit.**

The disqualifier to hunt is a body reached from `ui_task` on any pass, or from an
ISR, or from a published `OSAPI_*` slot, or from a pointer stored in a table that
outlives the boot. A body that is 99% boot-only and 1% reachable afterwards is a
freed heap claim being executed — the `desk_pdisk`/`desk_phdd` freeze whose story
`tools/os88ovlchk.py` carries in its own comments.

The precise window: `[spl_fseg]` is published by stage 2 at `boot/boot2.asm:288`, so
the overlay is live from `kmain`'s **first instruction**; it is retired at
`kernel/kernel.asm:4396` (`mov word [spl_fseg], COLD_SEG`) and the memory is given
back one instruction later at `:4397` (`call COLD_SEG:mem_unblob_x`). Every call site
in this register lies between `kernel.asm:4072` and `:4349`, comfortably inside it.

---

## 1. The blob at nineteen sectors — the arithmetic, derived from the source

`kernel/kernel.asm` sets three constants and asserts two bounds at its own foot:

```
BOOT2_SECS  equ 19            ; SPEC.md 2.9.12: was 13
OVL_AT      equ 2560          ; where `.ovl` starts inside the blob - UNCHANGED
BOOT2_PAD   equ BOOT2_SECS * 512                       =  9,728

%if BOOT2_SIZE > OVL_AT            -> "the loader has outgrown its share"   (:6068)
%if OVL_AT + OVL_SIZE > BOOT2_PAD  -> "the boot overlay does not fit"       (:6087)
```

**THIS SECTION SUPERSEDES THE ONE THAT SAID 194 BYTES AND `BOOT2_SECS` 15.** That
arithmetic was D8's, before this register was merged into the pass; it priced the
mouse cluster alone and nothing else. 194 bytes takes `sched_init` and stops.

Measured on the tree this landed on: `.boot2` **2,469**, `.ovl` **3,969**.

```
blob      BOOT2_SECS 19 sectors = 9,728 bytes
  .boot2  2,469                                                of OVL_AT 2,560   ->    91 free
  .ovl    3,969                                                of 7,168          -> 3,199 free
                                                               TOTAL BLOB SLACK    3,290 bytes
```

**Those bytes are ONE POOL.** `OVL_AT` is a byte offset with no alignment requirement
— the only constraints are the two `%if`s above — and moving it costs nothing at all:
`kernel.asm` says so in the file's own words, *"the blob is BOOT2_SECS sectors either
way, so no image byte, no RAM and no extra int 13h changes — only the split."* So the
correct way to read the pair is a single figure:

> **`.ovl` may grow by 3,290 bytes today without touching a sector, an `int 13h`, or
> one byte of any image.** The whole register is +1,766 of that and D8's mouse subset
> +1,112, which is 2,878 — so the merged pass lands with roughly 410 bytes still in
> the pool, and §4 is what the next claim after that costs.

Two standing caveats on that number. `.boot2`'s share is not freely tradable *down*:
its fifth sector is SPEC.md §15.3.4's row composer, which ships, so `OVL_AT` cannot
go to 2,048. And the free figure is **not** the one in the tree's own prose: D3/D4
record `kernel.asm:~2137` saying 159 and `docs/SETTINGS-COST.md` §7.1 saying ~738,
against a measured 127 before any of this. **A wrong headroom number in the one
section with double-digit slack is how a design gets approved that does not fit** —
quote this section, and re-derive it after any change to either side.

**One constant moves WITH `BOOT2_SECS` and is not in the list above**: `KSIG_OFF`
(the Makefile and `boot/boot2.asm`, one number typed twice). It is a *memory* offset
and SPEC.md §18.93.1's canary is a question about a *file sector*, so growing the blob
slides the probe six sectors further into the file — out of the band where it lands in
a transfer run's second half, and into the half that loads correctly on exactly the
machine the canary exists to catch. It went 11,776 → **8,704** here, which puts the
file sector back at 36. `tests/unit/t_canary.py` is the fast-tier row that refuses the
build otherwise, and it is what found this.

## 2. The register, ranked

Every row measured by assembling a **copy** of `kernel/` under `/tmp/lastdrop/` with
`tools/kernsize.py`'s own flags and reading `kernel.asm`'s `ks:` line. Nothing in the
repository was edited, `make` was not run, no emulator was launched, git was untouched.
**All twenty-five builds pass all seven `tools/os88ovlchk.py` checks**, and so does
the combined build of the whole register (§2.24).

"Resident returned" is `−(Δ.text + Δ.cold)` — the bytes that stop existing on the
machine after `spl_finish`. It is what D2 calls a TRUE REDUCTION, and it is the
column to rank by for footprint. `Δ.text` on its own is the **segment** column
(guard 2, `KERN_CODE_MAX`), which is the scarcer of the two and the one a
`.text` → `.ovl` move buys while a `.cold` → `.ovl` move sells.

| # | body | now | bytes | Δ`.text` | Δ`.cold` | Δ`.ovl` | resident returned | shims needed |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | **`drv_boot_x`** (+ the four gate collapses) | `.cold` | 288 | **+2** | **−276** | **+229** | **274** | 3 `.cold` far shims; `drv_boot` thunk deleted |
| 2 | **`vid_probe_avail` + `vid_memchk` + `vid_cga_alias`** (`Fmisc-27`) | `.text` | 262 | **−254** | 0 | **+262** | **254** | 1 `SPLSTUB`; **zero outbound** |
| 3 | **`sched_init`** | `.text` | 174 | **−166** | 0 | **+174** | **166** | 1 `SPLSTUB`; **zero outbound** |
| 4 | `dsk_boot_from_x` + `dsk_bootltr` | `.cold` | 160 | +6 | −160 | +160 | 154 | 1 `SPLSTUB`; the pair moves together |
| 5 | `xm_boot_x` | `.cold` | 100 | +6 | −92 | +106 | 86 | 3 `.cold` far shims; `xmf_xm_boot` deleted |
| 6 | `files_init_x` | `.cold` | 83 | +6 | −83 | +83 | 77 | 1 `SPLSTUB`; zero outbound |
| 7 | **`font_init`** (`Fmisc-33`) | `.text` | 80 | **−72** | 0 | **+80** | **72** | 1 `SPLSTUB`; zero outbound |
| 8 | `drv_init_x` + `drv_svc_clear_all` | `.cold` | 80 | +6 | −76 | +82 | 70 | 1 `.cold` far shim |
| 9 | `dsk_flop_add_x` | `.cold` | 70 | +6 | −70 | +70 | 64 | 1 `SPLSTUB` (see note) |
| 10 | `vid_detect` | `.text` | 67 | −57 | 0 | +67 | 57 | 1 `SPLSTUB`; `spw_vid_detect` re-pointed |
| 11 | `mem_init_x` | `.cold` | 62 | +6 | −58 | +64 | 52 | 1 `.cold` far shim |
| 12 | `dsk_dpt_init_x` | `.cold` | 60 | +6 | −60 | +60 | 54 | 1 `SPLSTUB`; zero outbound |
| 13 | `vid_ctx_init` | `.text` | 50 | −34 | 0 | +54 | 34 | 2 new `cw_` shims |
| 14 | `wm_init` | `.text` | 47 | −39 | 0 | +47 | 39 | 1 `SPLSTUB`; zero outbound |
| 15 | `dock_init` | `.text` | 35 | −19 | 0 | +39 | 19 | 2 new `cw_` shims |
| 16 | `sch_idle_start` | `.text` | 31 | −23 | 0 | +33 | 23 | `cw_task_spawn` **already exists** |
| 17 | `menu_init` (`Fmenu-04`'s move half) | `.text` | 30 | −14 | 0 | +34 | 14 | 2 new `cw_` shims — see note |
| 18 | `inst_init` | `.text` | 27 | −19 | 0 | +27 | 19 | 1 `SPLSTUB`; zero outbound |
| 19 | `loader_init_x` | `.cold` | 24 | +6 | −24 | +24 | 18 | 1 `SPLSTUB`; zero outbound |
| 20 | `mod_init_x` | `.cold` | 24 | +6 | −16 | +28 | 10 | 2 `.cold` far shims |
| 21 | `evq_init` | `.text` | 22 | −14 | 0 | +22 | 14 | 1 `SPLSTUB` — **and a test edit, §7.3** |
| 22 | `vid_init` | `.text` | 17 | −9 | 0 | +23 | 9 | the three `spw_*` shims already exist |
| — | *(10 + 22 taken as a PAIR)* | `.text` | 84 | −68 | 0 | +88 | 68 | one fewer crossing than taken apart |
| **Σ** | **the whole register, measured as ONE build** | | **1,793** | **−666** | **−915** | **+1,766** | **1,581** | |

`Fmouse-01`'s 1,024-byte subset (D8) is **not** in these totals — it is already
committed and is what takes `BOOT2_SECS` to 15.

### 2.1 `drv_boot_x` — 288 bytes, and the only row better than 1:1

**What it is.** `driver.inc:3937`, the whole of SPEC.md §51.3: mount the settings
volume, read `SYSTEM.CFG`, apply the display adapter, load each wanted driver, say
so on the splash bar. `kmain:4331` calls it once, through a 6-byte `.text` thunk
(`kernel.asm:5916`), and nothing else in the tree names it.

**Evidence.** `drv_boot_x ← drv_boot ← kmain`, one edge each; closure §8.2 confirms
no other inbound of any kind. It is *already* `.cold`, so it already far-calls
everything it needs, and it already reaches the overlay five times.

**Measurement.** `.text` +2 · `.cold` −276 · `.ovl` +229 · all seven gate checks pass.

**Price.** 229 blob bytes. Three `.cold` far shims (`drv_mounted`, `drv_row_x`,
`drv_load_x`, 4 bytes each) and one `SPLSTUB`; the `drv_boot` thunk is deleted.

**Why it beats 1:1.** Four of its five overlay entries — `ovl_spl_msg_cfg`,
`ovl_cfg_load`, `ovl_spl_msg_drv`, `ovl_spl_msg_boot` — have **`drv_boot_x` as their
only caller**. Once the caller is inside `.ovl` those become plain near calls in one
address space, and four 20-byte `OVLCALL`/`OVLCALLC` sites collapse to 3 bytes each.
That is worth **69 bytes**, measured: `.ovl` +229 with the collapse against +298
without. The four bodies' terminating `retf` becomes `ret` in the same edit — the
gate checks that and is what caught it (`os88ovlchk: ... is near-called, ends in
RETF`). The fifth, `SPLCALL splf_reset`, points into `.boot2` and stays as it is.

**What would flip it.** Nothing about the body — it is the best row here on every
axis but one. It needs **229 of a 194-byte pool**, so it is 35 bytes short of fitting
today. A 16-sector blob takes it with 477 to spare.

**Correction to carry.** `PLAN.md` §7.1 prices `drv_boot_x` at "~120". It is **288**
— `0x9F01 − 0x9DE1 = 0x120`, a hex length read as decimal. `Fdriver-06` rejected the
move on the real 127-byte `.ovl` headroom and was right to; at 194 bytes it is still
right, and at 16 sectors it stops being.

### 2.2 The vidsel probe trio — 262 bytes, the cleanest body in the tree

**What it is.** `vidsel.inc:119–333`: which adapters this machine actually has.
`vid_probe_avail` (136) calls `vid_memchk` (55) three times and `vid_cga_alias` (71)
once, and calls **nothing else at all**.

**Evidence.** One inbound edge tree-wide, `kmain:4165`. Zero outbound. The only other
mentions of either name in the repository are prose in
`tools/martypc/configs/os8088_machines.toml`.

**Measurement.** `.text` −254 · `.ovl` +262 · gate OK. Independently it also crosses
an image rung: `KERN_SIZE` 120,320 → 119,808.

**Price.** 262 blob bytes, one `SPLSTUB` (8 `.text`), no shims of any kind.

**What would flip it.** 262 of a 194-byte pool: **68 bytes short**. Either 68 bytes
of blob from anywhere, or one more sector. This is the row that most nearly fits and
is worth the most per byte of review.

### 2.3 `sched_init` — 174 bytes, and a find this pass did not have

**What it is.** `sched.inc:120`: seed the task table, save the BIOS `int 08h` vector,
programme the PIT, install `sch_isr`. Once, from `kmain:4126`.

**Evidence.** One inbound edge. **Zero outbound.** Nothing re-initialises the
scheduler — the reboot path is `sched_unhook` (`sched.inc:316`), which *restores* the
old vector and is a different routine; `sch_fast_on`/`sch_fast_off` re-programme the
PIT without going near this body.

**Measurement.** `.text` −166 · `.ovl` +174 · gate OK · `KERN_SIZE` −512 in isolation.

**Safety.** It installs a vector, which is the class that nearly bit `Fmouse-01` — but
it writes `mov word [es:0x22], KERNEL_SEG`, an explicit constant, **not `cs`**. There
is no CS store anywhere in this register (§6.2). It carries one `%ifdef KFZTRACE` arm,
which assembles in `.ovl` unchanged.

**Price.** 174 blob bytes, one `SPLSTUB`, no shims.

**What would flip it.** It **fits today**, with 20 bytes of the 194 left over. See §3.

### 2.4 `vid_detect` — 67 bytes, and the one the automated sweep missed

Worth its own note because of *how* it was found. `vid_detect` (`viddet.inc`, 67
bytes) has two callers: `vid_init` (from `kmain`) and `spw_vid_detect`, the 4-byte
`.text` far shim the **splash** calls at `splash.inc:517`. A reachability walk that
treats the splash timer ISR as a runtime root — which is the safe default, and what
the first sweep here did — marks the whole splash chain live and loses this body.
`spl_isr` is in fact the *pre-`kmain`* `int 08h` handler, replaced by `sched_init`,
so everything reached only from it is boot-only too.

**Measurement.** Alone: `.text` −57 · `.ovl` +67. Paired with `vid_init` (§39, viddet.inc),
which is its other caller: `.text` −68 · `.ovl` +88 — better than the two taken
separately, because `vid_init → vid_detect` becomes a near call inside `.ovl`.
Both gate OK.

**Mechanism.** `spw_vid_detect` keeps its 4 bytes and becomes
`call splg_vid_detect / retf`, so `.boot2`'s far call is unchanged and the new
`SPLSTUB` does the crossing. **A bonus falls out**: the splash's first tick currently
needs `vid_detect` to be *aboard* from `.text`, which is what `SPL_RESIDENT` measures;
in `.ovl` it is aboard before stage 1 jumps, by construction.

**What would flip it.** The blob grows. It is also the row most improved by the
owner's unlock (b) — consolidating `.ovl` and `.boot2` — since `.boot2` could then
call it directly and the `SPLSTUB` disappears.

### 2.5 The `.cold` rows as a class — rows 1, 4, 5, 6, 8, 9, 11, 12, 19, 20

These behave identically to one another and the arithmetic is worth stating once,
because it is not the same trade as a `.text` row.

* A `.cold` body is called `call COLD_SEG:X` (5 bytes). In `.ovl` that becomes
  `OVLGATE X` (3 bytes) plus one `SPLSTUB` (8): **`.text` +6, every time.**
* `.cold` and `.ovl` have the **same calling discipline** — CS of their own,
  `DS = KERNEL_SEG`, far calls out through `cw_` shims — so nothing inside the body
  changes. That is why these rows are mechanically the cheapest in the register.
* The exception is a near call to a `.cold` body that is **staying**: it becomes far
  (+2 at the site) and wants a 4-byte `retf` shim in `.cold`. Rows 5, 8, 11 and 20
  each pay this; rows 4, 6, 12 and 19 have no outbound calls at all.

So a `.cold` row **sells 6 bytes of the 64KB segment to buy back its whole body of
RAM.** Whether that is the right trade depends which guard is tighter when the
question is asked — which is exactly why §2's table keeps the two columns apart.

**Note on row 17.** `menu_init` measures **30 bytes**, and moving it is worth
`.text` −14. `PLAN.md` §7.1 prices `Fmenu-04` at "~75 / `.text` −59" and
`CONSOLIDATED.md` at −67 — those figures are the move **plus** the separate fold of
`menu_relayout`'s constant cell 0, which is a deletion and not a section move. Only
the move half belongs in this register. It is the weakest `.text` row here and D4's
own verdict stands: **marginal — do not buy a sector for it.**

**Note on row 9.** `dsk_flop_add_x` is reached from `desk_init`, which is *already*
in `.ovl`, through a 6-byte `.text` thunk. Calling it directly from `.ovl` instead
of routing through a `SPLSTUB` is worth a further **12 bytes of `.text` and 2 of
blob** — but the gate refuses it as filed, because `dsk_flop_add_x` ends `retf` and
would then be near-called (`os88ovlchk` says so in terms). The return kind has to be
settled in the same edit. The table quotes the conservative route.

### 2.24 The whole register measured as one build

Not a sum of rows — one assembly with every body moved:

| | `.text` | `.bss` | `.cold` | `.ovl` | `KERN_SIZE` |
|---|---:|---:|---:|---:|---:|
| baseline | 57,149 | 5,955 | 40,784 | 3,969 | 120,320 |
| whole register in `.ovl` | 56,483 | 5,955 | 39,869 | 5,735 | **118,272** |
| delta | **−666** | 0 | **−915** | **+1,766** | **−2,048** |

**1,581 resident bytes returned for 1,766 blob bytes** — and, because `.text` and
`.cold` each cross rungs, **four 512-byte rungs of `KERN_SIZE`**. All seven gate
checks pass, and so does `$SCRATCH/integration/I3-os88ovlchk-fixed.py`'s eighth.

The rows are additive to within **two bytes**: the individual `Δ.ovl` figures sum to
1,768 against a measured 1,766, and `Δ.text` to −664 against −666. Those two bytes are
the `vid_init`/`vid_detect` pairing (§2.4) and nothing else; `Δ.cold` reconciles
exactly at −915. There is no other interaction between rows, which means **the
register can be taken in any subset, in any order** — price a subset by summing its
rows and it will be right.

At 18 sectors the register is **36 bytes short** of fitting whole (1,730 available
against 1,766). At 19 it fits with 476 to spare, and 19 costs exactly what 16 costs.

Under every knob (measured, all assemble):

| build | `.text` | `.cold` | `.ovl` | `KERN_SIZE` |
|---|---:|---:|---:|---:|
| plain | −666 | −915 | +1,766 | −2,048 |
| `KERN_SMALL=1` | −614 | −776 | +1,571 | −1,536 |
| `BOOTMARK=1` | −666 | −915 | +1,766 | −2,048 |
| `SPLSTARS=1` | −666 | −915 | +1,766 | −2,048 |

---

## 3. FITS NOW — what 194 bytes buys with no further growth

**This is the part to act on first.** Nothing below needs a sector, an `int 13h`, or
one byte of any image. Every option was measured; pick by which guard is tighter.

**Best for the 64KB segment (guard 2 — the physics one):**

> **`sched_init` alone. 174 of the 194 bytes. `.text` −166, `.ovl` +174, 20 bytes
> left over.**
> One body, one call site, zero outbound calls, one `SPLSTUB`, no shims, no `%if`
> arm to reason about, no CS store, no `MARK`, no test or tool that names it. It is
> the smallest diff per byte in the whole register.

**Best for the footprint (`KERN_BUDGET`):**

> **`dsk_boot_from_x` + `dsk_bootltr` (160) with `sch_idle_start` (33) = 193 bytes.
> `.text` −17, `.cold` −160, 177 resident bytes returned, 1 byte spare.**

**Other combinations that fit**, for completeness — all measured, all additive:

| set | blob | Δ`.text` | Δ`.cold` | resident |
|---|---:|---:|---:|---:|
| `sched_init` | 174 | −166 | 0 | 166 |
| `dsk_boot_from_x`+`dsk_bootltr` + `sch_idle_start` | 193 | −17 | −160 | 177 |
| `dsk_boot_from_x`+`dsk_bootltr` + `inst_init` | 187 | −13 | −160 | 173 |
| `files_init_x` + `dsk_dpt_init_x` + `wm_init` | 190 | −27 | −143 | 170 |
| `font_init` + `wm_init` + `sch_idle_start` + `inst_init` | 187 | −153 | 0 | 153 |
| `vid_detect` + `files_init_x` + `dock_init` | 189 | −70 | −83 | 153 |

**What does NOT fit today, and by how much:**

* the vidsel trio (§2.2) — 262, **68 over**
* `drv_boot_x` (§2.1) — 229, **35 over**

Both are the two largest single wins in the register, and both are within a hundred
bytes. If any other work donates blob bytes — the `.boot2`/`.ovl` consolidation, a
`.boot2` deletion, `Fkernel-11`/`Fmisc-29`-shaped donations — check this line again
before deciding those bytes are spare.

---

## 4. The growth table — what a sector costs and what it admits

`tests/unit/t_blobruns.py --sectors N` prices this host-side in 0.1 s, per geometry,
against the images already in `build/`. Run afresh, this tree:

| `BOOT2_SECS` | blob | 360KB | 720KB | 1.44MB | `.ovl` free over 3,969 |
|---:|---:|---:|---:|---:|---:|
| 13 (pre-2.9.12) | 6,656 | 2 | 2 | 2 | 218 |
| 14 | 7,168 | 2 | **3** | 2 | 730 |
| 15 (D8's) | 7,680 | 2 | 3 | 2 | 1,242 |
| 16 | 8,192 | **3** | 3 | 2 | 1,754 |
| 17 | 8,704 | 3 | 3 | 2 | 2,266 |
| 18 | 9,216 | 3 | 3 | 2 | 2,778 |
| **19 (SHIPPED)** | **9,728** | **3** | **3** | **2** | **3,290** |
| 20 (`SPLSTARS`) | 10,240 | 3 | 3 | 2 | 3,802 |
| 21 | 10,752 | 3 | 3 | 2 | 4,314 |
| 22 | 11,264 | 3 | 3 | **3** | 4,826 |
| 23 | 11,776 | 3 | **4** | 3 | 5,338 |

("free" = `BOOT2_PAD − .boot2` 2,469 − `.ovl` 3,969, `OVL_AT` set wherever the split
needs to be; the two sides are one pool, §1. The 23 row was measured here and is not
in any earlier copy of this table.)

**Read the call columns and not the sector numbers.** A run is bounded by the TRACK
and `KERNEL.SYS` starts wherever each BPB puts the data area, so the boundary is in a
different place on each geometry. One `int 13h` is 1–2 revolutions **whatever it
moves** — 199 ms for one sector and 384 ms for a nine-sector track on the field 5150
(PERFORMANCE.md Part 2, Sets 14/22), and SPEC.md §15.3.8.5 prices the marginal sector
at "near enough 400 ms". A sector *inside* an existing run is ~24 ms.

So the ladder has exactly **four prices**, and everything in between is free:

| step | what it costs | what it admits |
|---|---|---|
| 13 → 14 | one extra `int 13h`, **720KB only** | 730 bytes |
| 14 → 15 | nothing | 1,242 |
| **15 → 16..21** | one extra `int 13h`, **360KB only** (~400 ms on the field XT) | **3,290 at the shipped 19 — the entire register (1,766) and D8's mouse subset (1,112) with ~410 left.** 20 and 21 are free after that |
| 21 → 22 | a third `int 13h` on **1.44MB** — the release geometry, and the one most tests boot | 4,826 |
| 22 → 23 | a **fourth** on 720KB | 5,338 |

> **The load-bearing line: 16 through 21 all cost the same single extra call**, and
> the shipped blob sits at 19 of them. **The next claim of any size has 1,024 free
> bytes behind it and then hits a price that has not been approved** — 22 buys 1.44MB
> its third call. That is the conversation to have before spending sector 22, not
> after.

**What the call table hides, and it is not small.** The in-run sectors land on
**every** geometry, including the one that pays no call: 13 → 19 is six more sectors
inside an existing run on 1.44MB, ~144 ms at 24 ms each, with nothing in the call
column to show for it. All of it is pre-splash — stage 1 reads the blob before the
first splash pixel — so it is time on a blank screen rather than a slower-looking
boot, and `docs/BOOT-PERF-PLAN.md`'s phase tables want re-taking because of it.

**`tests/unit/t_blobruns.py`'s ratchet is PER GEOMETRY now**, which is what that file
says it exists for: 3 on 360KB, 3 on 720KB, **2 on 1.44MB**, each with its reason
beside it. One number for all three was the shape of the original mistake.
`tests/unit/t_buildmatrix.py` gained a `MOUDIAG` row in the same commit — it had none,
and a knob whose blob nothing measures is how the last break went unfound.

---

## 5. What each knob needs at nineteen sectors — D5, not a new rule

A knob is bound by physics, never by a documented limit, and *"all knobs together
fit"* is not required. `SPLSTARS=1` is the model already in the tree:
`BOOT2_SECS_STARS` sits beside the shipped value and the Makefile's `sed` is
deliberately anchored to find only the shipped one.

Measured on the tree the blob resize landed on, before any body has moved:

| build | `.ovl` | `.boot2` | its `OVL_AT` | fits the 19-sector blob? |
|---|---:|---:|---:|---|
| shipped (kern_big) | 3,969 | 2,469 | 2,560 | ✔ 3,290 free |
| `KERN_SMALL=1` | 3,886 | 2,469 | 2,560 | ✔ 3,373 free |
| `BOOTMARK=1` | 4,060 | 2,469 | 2,560 | ✔ 3,199 free |
| `MOUDIAG=1` | 3,969 | 2,475 | 2,560 | ✔ 3,284 free |
| `SPLSTARS=1` | 3,969 | **2,798** | **3,072** | **only at 20** — its `.boot2` is 329 bytes over the shipped split and it is over *wherever* `OVL_AT` falls |

**At 19, `SPLSTARS` is the only knob that still needs a `BOOT2_SECS` of its own**
(`BOOT2_SECS_STARS equ 20`). At D8's 15, `BOOTMARK` and `MOUDIAG` needed one each as
well. That is D5 honoured with *less* machinery rather than more — and it is a
maintenance risk in the same breath, because a mechanism with one user is a mechanism
nobody notices breaking. `tests/unit/t_buildmatrix.py` is what watches it, and it now
carries a `MOUDIAG` row: it had none, which is how D8's short-jump break went
unfound.

**Do not lower the shipped `OVL_AT` to make `SPLSTARS` fit 19.** It would work and it
costs the shipped side nothing, but it is a shipped constant re-tuned for a knob's
overflow, which is the shape D5 refuses. The knob has a sector.

---

## 6. Standing caveats — read before adding a row

### 6.1 `.ovl` is a different address space, and the gate enforces it
A near call from `.text` into `.ovl` (or back) is a displacement computed between two
address spaces. `tools/os88ovlchk.py` refuses it, and that gate stays. Inbound is an
`OVLGATE`/`SPLSTUB` pair; outbound is `call KERNEL_SEG:cw_X` / `call COLD_SEG:cwc_X`
to a 4-byte `retf` shim.

`.boot2` and `.ovl` are the exception that is *not* an exception in practice: they are
already **one** address space (`.boot2 start=0 vstart=0`, `.ovl start=OVL_AT
vstart=OVL_AT`, one segment), so a near call between them is already correct today and
the gate's refusal is safe over-strictness rather than a correctness requirement. **Do
not weaken it for bytes** — it was measured at 34 bytes on the mouse cluster and
refused there. Do the consolidation properly or pay the gate.

### 6.2 CS may never be stored from `.ovl`, and today nothing checks it
`os88ovlchk.py` exempts `.ovl` from the `.cold` CS check **by design**, because the
overlay's data rides with it and `[cs:si]`, `push cs` and `cs lodsw` are correct
idioms there. **Storing CS into memory never is** — it always means "the kernel's
segment", and in `.ovl` it is the blob's. D8 adds the check for exactly this reason.

**No body in this register contains a CS store.** The only five in the kernel are
`mouse.inc:388/410/1439` (D8's own, which is why the check is a prerequisite there),
`splash.inc:1472` (legitimate — `spl_isr` really does live in the blob) and
`kernel.asm:5355` (`mark_hook`, `BOOTMARK`-only, `.text`). So no row here *depends*
on the new check — but every row here is protected by it against the next edit, and
that is the reason to have it.

The generalisation worth writing down: **an `.ovl` body may take the address of a
`.text` label freely** — `.text` has `vstart=0` and the consumer supplies
`KERNEL_SEG`, so `mov ax, sch_idle_body` in `.ovl` is correct — **but an address of
an `.ovl` label stored anywhere that outlives the blob is a pointer into freed heap.**

### 6.3 No `MARK` site is in this register
`MARK n` is not textually a call — the `call mark_here` is in the macro body — so
today's gate is blind to it in either destination, and D8 needs
`$SCRATCH/integration/I3-os88ovlchk.patch` for the eight sites inside `mouse_init`.
Audited: **not one body in §2 contains a `MARK` or `BPMARK`.** The I3 patch is a
prerequisite for D8, not for this file. (Take it anyway; it is 0 bytes and it is what
would catch the *next* one.)

### 6.4 A string op in `.ovl` may not take a `cs:` source
Seven rows contain `rep movs`/`rep stos` — `font_init`, `wm_init`, `inst_init`,
`files_init_x`, `drv_init_x`, `mem_init_x`, `dsk_dpt_init_x`. All are correct as
written, because they address kernel data through `DS`/`ES` and `DS = KERNEL_SEG` in
`.ovl` exactly as it is in `.text`. The rule to preserve: the 8086 **loses the segment
prefix when a string instruction is restarted after an interrupt**, so if an `.ovl`
body ever grows data of its own, a block move out of it must load a segment register
and never wear a `cs:` prefix.

### 6.5 A pre-existing `section` directive inside a body's span
`dsk_bootltr` and `mod_init_x` each have a `section` line between their label and the
next one. A bracket placed at the "next top-level label" therefore swallows it and
silently re-sections whatever follows — in the harness for this file it moved a
12-byte `.text` table into `.cold` and made a clean measurement read `−6` instead of
`+6`. Bracket to the **first section directive** inside the span, not to the next
label, and check the map afterwards.

The related rule that always applies: a NASM local `.foo` belongs to the last
non-local label, so a `section` line inserted mid-body re-parents nothing but a
*moved* body re-parents everything. Every measurement in this file was made by
inserting brackets **in place**, so no body changes file position and no local label
is re-parented.

### 6.6 A knob takes its own `BOOT2_SECS` — see §5.

### 6.7 `.ovl` fails silently, and that is the standing risk
A future maintainer who adds a runtime path into any body in this register gets a
**silent no-op**, not a crash: `spl_gate` tests `[spl_fseg]` and returns. That is a
safe failure (no wild jump) and an invisible one. It is the strongest argument for
keeping this file next to the code — the rows here name what may never gain a
runtime caller.

---

## 7. Disqualified — with the killing edge named

Everything below looks boot-only and is not. Recorded so nobody derives it twice.

### 7.1 Reached after the blob is retired

`kmain` gives the memory back at `:4397`. Three `.cold` bodies are called at or after
that point and can never be in it:

| body | bytes | killing edge |
|---|---:|---|
| `mem_unblob_x` | 14 | **it is the routine that releases the blob** (`kmain:4397`) |
| `mem_floor_ax` | 14 | called from `mem_init_x` (before) **and `mem_unblob_x`** (after) |
| `drv_notice_x` | 23 | `kmain:4423`, after `spl_finish` — "and only NOW say what did not load" |

### 7.2 Reached from `ui_task`, an ISR, or a published slot

| body | bytes | killing edge |
|---|---:|---|
| `osapi_sys_snapshot` (`Fmisc-22`) | 258 | `osapi_table` cell — a **published slot**, called about once a second by the Task Manager |
| `menu_kbnav` (`Fmenu-01`) | 177 | `kbm_move` (`mouse.inc:1920`) — an arrow key, for the session |
| `ui_tm_open` + `ui_note` (`Fui-01`) | 143 + 57 | `ui_cmd ← ui_dispatch ← ui_task` — a Task Manager pick, and `cw_ui_note` besides |
| `vid_disp_init` | 135 | called by `kmain:4176` **and** `vid_disp_relayout` — Control Panel → Display, SPEC.md §39.19.1. The largest lookalike in the tree |
| `mou_hotplug` | 131 | `ui_task` **every pass** — the worked example, and the edge that nearly disqualified the whole mouse cluster |
| `mouse_unhook` | 116 | `sched_unhook` ← Chip → Restart. Runs at **reboot**, when the blob is long gone |
| `vid_apply`, `vid_setmode` | — | `vid_switch`, `fsx_enter` — a runtime mode change |
| `mou_pall`, `mou_pout`, `mou_newround`, `mou_lockon`, `mou_p2_off` and the four `mou_p2*` writers | 339 | `mou_hotplug` / `mouse_unhook`. This is `Fmouse-01`'s remaining half, and it goes to `.cold` under D8 for exactly this reason |
| `mou_claim` | — | `mou_isrs`, the ISR vector table |

`Fui-01` and `Fmenu-01` appear in D4's own list as boot-only candidates. **They are
not**, and `PLAN.md` §7.1 already corrects it — recorded again here because the
correction is the useful half.

### 7.3 Boot-only, but a host instrument names the symbol

**`evq_init` (22 bytes) — take it only with a test edit.** `tests/evqfull.py:96` pokes
a **near** `call evq_init` into `snd_xlat` inside `KERNEL_SEG` and executes it with
`CS = KERNEL_SEG`:

```python
rel = (sym["evq_init"] - (at + 3)) & 0xFFFF
m.write((KERNEL_SEG << 4) + at, bytes([0xE8]) + rel.to_bytes(2, "little") + ...)
```

In `.ovl`, `sym["evq_init"]` is an `OVL_AT`-relative offset in the blob's segment, so
that near call from `KERNEL_SEG` lands somewhere arbitrary and **executes it**. This
is the one row in the register with a cost outside the kernel, and it is 14 resident
bytes — almost certainly not worth the edit, but recorded so the trap is seen before
it is sprung rather than after. (`tests/unit/t_wakedrain.py` also matches on
`call evq_init`; `OVLGATE evq_init` simply stops matching, which is harmless.)

Checked and **clear**: `vid_init` (`tools/os88boot.py`, a docstring), `sch_idle_start`
(`tests/uiblock.py`, a message string), `xm_boot_x` (`tests/dispcold.py`, its own
maintenance history), `vid_probe_avail`/`vid_cga_alias`
(`tools/martypc/configs/*.toml`, comments). No other candidate is named anywhere
under `tests/` or `tools/`.

`tools/os88boot.py`'s phase table survives every row: it breaks on the **return**
address of each `call` in `kmain`, and `OVLGATE X` is still `call splg_X` in `.text`.
The phase label it prints changes from `X` to `splg_X`.

### 7.4 Cannot move by construction

| body | bytes | why |
|---|---:|---|
| `kmain` | 196 | a hub of ~35 near calls plus 13 `.text`-only gate sites. In `.ovl` every gate reverts to the 20-byte inline `SPLCALL` (+208) and every call goes far. **Deeply negative** — D4's own refusal, re-confirmed |
| the eleven `SPLSTUB`s + `spl_gate` | 103 | `.text`-only *by construction* (SPEC.md §2.9.5.2): they exist **because** a near call out of another address space is refused |
| the `spw_*` / `cw_*` / `ovw_*` / `dkf_*` far shims | 4 each | a shim in `.ovl` is a shim that cannot be reached from `.text` |
| `dsk_fdd_probe`, `clk_init`, `cpu_detect`, `xm_sniff`, `snd_init`, `desk_init`, `drv_snd_sniff` and the rest of `.ovl` | 3,969 | **already there** |

### 7.5 Whole modules that contribute nothing
Closure over the entire kernel (§8) returns **59 boot-only bodies and no more**. Every
routine in `wm.inc`, `menu.inc` (bar `menu_init`), `ui.inc`, `files.inc`, `fdlg.inc`,
`icons.inc`, `clip.inc`, `blank.inc`, `toast.inc`, `fprog.inc`, `assoc.inc`,
`filecp.inc`, `clone.inc`, `diskw.inc`, `fsx.inc`, `snd.inc`, `band.inc`, `font.inc`
(bar `font_init`), `vga12.inc` and `softgfx.inc` is either session-lifetime or already
`.cold`. **The register above is complete for this tree.**

---

## 8. Method, and how to re-derive it

Everything here was produced from a copy of the tree at commit
`950c9679d4157d6ed5b13606adab186a5961d8c9`, working tree clean, under `/tmp/lastdrop/`.

### 8.1 Sizes — whole-kernel re-assembly, never fragment arithmetic
A `[map all …]` line at the top of a **copy** of `kernel.asm` makes NASM emit every
symbol with its section and address; a body's size is its address to the next
**top-level** label in the same section (NASM locals appear as `parent.child` and are
excluded). The probe is proved non-perturbing: the `ks:` line is byte-identical with
and without it. The harness reproduces `OVL-MOUSE.md`'s nine mouse routines to
1,024 bytes exactly, and `PLAN.md`'s `Fmisc-27` and `Fmisc-33` figures to the byte.

Every row was then **built** — the body bracketed into `.ovl` in place, the call site
converted, the shims added — and measured with
`nasm -f bin -w+error -w-error=user -DKERNSIZE`, reading `kernel.asm`'s own `ks:`
line, which is `tools/kernsize.py`'s exact procedure. Twenty-three individual variants
plus two combined ones — twenty-five whole-kernel assemblies in all.

### 8.2 Boot-only — closure, not inspection
The call graph carries six edge kinds, because a plain `call` scan misses four of them:

* **CALL** — `call`/`jmp`/`jcc`/`loop`, near and far
* **CELL** — `OSAPI_SLOT`/`JSLOT`/`NSTUB`/`XSTUB` (the macro body near-calls its argument)
* **MAC** — `%macro` bodies mapped onto every expansion site (`MARK` → `mark_here`)
* **GATE/STUB** — `SPLGATE`/`OVLGATE`/`SPLCALL`/`OVLCALL`/`OVLCALLC`/`SPLSTUB`, whose
  target is pasted into a generated label and is invisible to every regex above
* **DATA** — `dw`/`dd <label>`, a stored proc address
* **ADDR** — *any other* immediate mention of a known code label (`mov reg, sym`,
  `push sym`, `mov word [x], sym`). Deliberately over-broad: an IVT install is this
  and nothing else, and a candidate must survive it.

A body is boot-only iff **every** direct caller is boot-only, computed as a fixpoint
from `{cold_entry, kmain, the stage-2 splash chain, everything already in `.ovl`}`,
with three classes blocked from ever joining: `ui_task` (which `kmain` hands control
to permanently), every ISR, and every body whose inbound edges are *only* ADDR/DATA —
a stored pointer entered later.

Two cross-checks that make the result trustworthy:

* the **near-miss list is empty** — no body is excluded by a soft ADDR/DATA edge
  alone, so the over-broad rule costs no candidates;
* the closure independently reproduces `OVL-MOUSE.md`'s partition, including its
  correction of G2 (`mou_p2_init` is **not** reachable from `mou_hotplug`;
  `mou_hotplug → mou_lockon` and `mouse_unhook` both reach `mou_p2_**off**`).

Then every row was closed by hand: an exhaustive grep of each symbol across
`kernel/ boot/ apps/ drivers/ tools/ tests/`, and a per-body audit for `MARK`, CS
stores, string ops, `%if` arms and stray `section` directives.

### 8.3 Gates
`tools/os88ovlchk.py` (all seven checks) on every variant and on both combined builds;
`$SCRATCH/integration/I3-os88ovlchk-fixed.py`'s eighth on the combined build. All
green. The gate earned its place twice during this work — it caught the four
`retf`/near-call mismatches in §2.1 and the dead `xmf_xm_boot` shim in row 5, both of
which assemble cleanly and are wrong.

### 8.4 Blob cost
`python3 tests/unit/t_blobruns.py --sectors N` against the three images in `build/`,
host-side, read-only, per geometry. §4's table is that tool's output, not arithmetic.

### 8.5 Reproducing

```sh
nasm -f bin -w+error -w-error=user -DKERNSIZE \
     -I <kerneldir>/ -I apps/ -I build/ -o /dev/null <kerneldir>/kernel.asm   # read ks:
python3 tests/unit/t_blobruns.py --sectors 19
python3 tools/os88ovlchk.py                    # from a tree root
```

---

## 9. Evidence still owed before any of this ships

Nothing static substitutes for these, and the register does not claim otherwise.

1. **A boot.** Every row is a body that ran during boot and now runs from a different
   segment. One MartyPC boot to a desktop settles most of them at once.
2. **`sched_init` specifically** — it installs `int 08h`. Read `0000:0020` after boot
   and confirm the segment word is `0x0060` (`KERNEL_SEG`) and not `[spl_fseg]`.
3. **The vidsel trio and `vid_detect`** — the adapter probe decides the mode. Both
   1bpp adapters (`VIDEO=cga`, `VIDEO=herc`) and the `xt-multimon` two-card XT, since
   `vid_cga_alias` runs *only* when the mono card is primary.
4. **`drv_boot_x`** — it mounts a volume and loads drivers from it, and the four
   collapsed gates change how the splash bar is written. A boot with a `SYSTEM.CFG`
   that asks for a driver, on a machine that has one.
5. **A 720KB boot and a 360KB boot** for whichever `int 13h` step is bought.
   **MartyPC cannot host a 720KB drive with the ROM sets in this tree**, which is
   precisely how SPEC.md §15.3.8.5's boundary was missed the first time. 86Box, or
   the field 5150.
