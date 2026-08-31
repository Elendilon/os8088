# The VGA code a mono machine cannot use — what the space is, and what to spend it on

**A handoff, and a question rather than a mechanism.** Nothing here is built.
What is measured is the *size and shape of the hole*: the bodies in
`kernel/vga12.inc` that a machine with no VGA adapter can never enter, grouped,
priced, and set against the things that machine is refused today for want of
exactly that many bytes.

> **Read SPEC.md §39.22 first.** It is the precedent and the argument: `.vgabuf`
> is 1,024 bytes of VGA-only *buffer* that a mono machine already declines at
> boot, and its reasoning about *why that rung and not some other* is what
> decides everything below. This file is the same question asked about the
> **code**, where the answer comes out differently.

---

## 0. The verdict, up front

1. **There are ~1,750 bytes of VGA-only `.text` on `kern_big` and ~1,200 on
   `kern_small`** (§1, measured). Held aside from the grouping, `vga_solid_rect`
   — the one body that is *fallen into* rather than called — leaves **~1,590 and
   ~1,050**.

2. **They cannot be given back to the heap.** SPEC.md §39.22's ladder argument
   settles it and this file does not re-open it: a byte is droppable only if
   nothing sits above it, and the only rung with nothing above it is
   `.lowbss`/`.vgabuf`. Moving hot drawing code up there makes every call to it
   far, which is the attempt that has already been made and abandoned.

3. **So the space is reusable in place and nothing else.** The question is not
   *how do we free it* but **what does a mono-only machine get to have that it
   is refused today** — and there are four candidates with numbers already
   attached, ranked in §4.

4. **The cheapest candidates cost no blob at all**, because their payload is
   *computed* at boot rather than shipped (§4.2, §4.4). A payload that is code
   costs three sectors of the loader blob, which today is **~72 ms of pre-splash
   time and no extra `int 13h` on any geometry** (§3.2).

5. **The gate is `[vid_avail] & VID_A_VGA`, never `[vid_mono]`**, and that
   asymmetry is the whole reason only one side of the kernel is reclaimable
   (§2).

**What this is not.** It is not a footprint argument. `KERN_SIZE` is 113,664 of
129,536 and `.text`+`.bss` is 58,437 of 65,536, so neither guard is tight and
nobody needs these bytes for room. Their value is that they are **a budget only
a mono machine can spend**, on a machine that is slower than the one that keeps
them.

---

## 1. What the space is — measured, not remembered

Method is docs/LAST-DROP-BYTES.md §8.1's: a `[map all …]` line at the top of a
*copy* of `kernel.asm`, a body's size being its address to the next label in the
same section. Local labels are used where a VGA-only arm sits inside a shared
body, which is most of the interesting cases.

Reproduce with:

```sh
printf '[map all /tmp/k.map]\n' > /tmp/kmap.asm && cat kernel/kernel.asm >> /tmp/kmap.asm
nasm -f bin -w+error -I kernel/ -I apps/ -I build/ -o /dev/null /tmp/kmap.asm
```

### 1.1 `kern_big`

| body | bytes | why it is dead on a mono-only machine |
|---|---:|---|
| `vga_blit_prow` | 290 | SPEC.md §5.4.1.3's planar row decoder |
| `gfx_fill_pat_raw` (VGA body) | 175 | the mono arm is `jne sw_fill_pat` at the door |
| `vga_solid_rect` | 159 | **the one held aside — see §1.3** |
| `vga_blit_span` | 157 | |
| `gfx_fill_gray_raw` (VGA body) | 151 | the mono arm is `jne sw_fill_gray` at the door |
| `gfx_line_runs` | 141 | the major-axis run walk; mono takes `gfx_line_fast`/`gfx_line_mono` |
| `vga_prow_emit` | 115 | the decoder's emit |
| `vga_restore_vram` (body) | 112 | mono goes to `sw_restore` |
| `vga_save_vram` (body) | 90 | mono goes to `sw_save` |
| `vga_p4build` | 76 | builds `vga_p4tab`, which is in `.vgabuf` and already declined |
| `vgas_lincopy` | 73 | `gfx_scroll`'s linear copy; mono takes `vgas_bankcopy` |
| `gfx_spans.vga` | 69 | |
| `gfx_blit4.vga` | 54 | |
| `vga_xor_fill_vram` + `vga_xor_rect_vram` | 24 | |
| `vga_set_color` / `vga_set_xor` / `vga_gc_reset` | 59 | the three GC writers |
| `vga_pat_stage` | 14 | |
| `vga_sr_on` | 12 | |
| **total** | **1,771** | |
| **less `vga_solid_rect`** | **1,612** | what a grouping pass can actually move |

### 1.2 `kern_small`

`GFX_PLANE` is `kern_big`'s, so the decoder trio (`vga_p4build`,
`vga_blit_prow`, `vga_prow_emit` — 481 bytes) is not in the build at all,
`gfx_spans` is a 2-byte stub and `gfx_blit4` is 390 rather than 753. Measured
the same way on `-DKERN_SMALL=1`:

| | bytes |
|---|---:|
| total VGA-only `.text` | **~1,207** |
| less `vga_solid_rect` | **~1,048** |

**`kern_small` is the build where this matters**, and §4 is mostly about it: it
is the 128–256KB machine, which in the field is overwhelmingly an XT with a
Hercules or a CGA card — a machine that both *has* the dead bytes and *is
refused* the features they would pay for.

### 1.3 The one body that is fallen into, not called

`gfx_fill_raw` ends with the mono test and then **falls through** into
`vga_solid_rect`:

```
gfx_fill_raw:
    cmp byte [vid_mono], 0      ; 1bpp? then the software renderer IS
    jne sw_fill                 ; the renderer - and the flag store is BELOW
    mov byte [vga_xorm], 0      ; this jump, so the 1bpp arm is byte-identical
vga_solid_rect:
```

Grouping it with the rest inserts a `jmp` into the hottest fill path in the
system — every window background, every frame, every glyph cell's erase — for
159 bytes. **That is the trade to refuse**, and it is why every figure above is
quoted twice. It is also the reason the span is *two* spans rather than one, and
a grouping pass should say so rather than pretending otherwise.

---

## 2. Only the VGA side is reclaimable, and that is not an oversight

A mono machine can never acquire VGA — `vid_probe_avail` never probes 0xA000 on
it — but **a VGA machine always has `VID_A_CGA` too and can be switched to mono
at run time** (SPEC.md §39.11), so it may never give its VGA bodies back and it
may never lose its mono ones either. SPEC.md §39.22 states the rule for
`.vgabuf` and it binds here identically:

> **Gate on `[vid_avail] & VID_A_VGA`, never on `[vid_mono]`.**

The consequence worth writing down: **the kernel carries both renderers resident
on every machine, and only one of the two can ever be reclaimed.** The mono-only
bodies are not small — `gfx_line_fast` (647) + `gfx_lf_wide3` (71) +
`gfx_line_mono` (286) + `gfx_lstep_mono` (212) is 1,216 bytes of code a VGA
machine never enters — and none of it is available, because that machine is one
Control Panel click away from needing all of it.

`vid_probe_avail` runs before `mem_init` in `kmain`, which is what makes the bit
readable at the point a decision has to be taken. It is already in `.ovl`
(docs/LAST-DROP-BYTES.md row 2).

---

## 3. The mechanism, if one is built

### 3.1 Shape

A body in `.ovl` — call it `mono_reclaim_x` — run from `kmain` after
`vid_probe_avail` and before anything draws, which tests
`[vid_avail] & VID_A_VGA` and, when it is clear, either copies a payload over
the span or simply *publishes* it (§4.2 and §4.4 need no copy at all). The
decider dies with the blob at `spl_finish`, so it costs no resident byte, which
is docs/LAST-DROP-BYTES.md §0's rule working in this direction for once.

`.ovl` has **111 bytes free** at today's `BOOT2_SECS` of 8, which is enough for
the decider and not for a payload.

**The enforcement is the part that is not optional.** Overwriting a body is safe
only while nothing reachable on a mono machine enters it, and today that is true
by branch rather than by construction. `tools/os88ovlchk.py` plus
`tests/ovlrefs.txt` is the idiom the tree already has for exactly this — every
reference from outside a region into it, with the reason each is safe, checked
by a gate — and a `tests/vgarefs.txt` of the same shape is what stops the
seventeenth body from quietly gaining a caller that runs on a mono machine. The
failure mode without it is a freed region being executed, which is the
`desk_pdisk` freeze `os88ovlchk.py` carries in its own comments.

### 3.2 What a payload costs to deliver

Two vehicles, and the choice is decided by whether the payload is **code** (must
be shipped) or a **table** (can be computed at boot by code that is already in
the kernel).

| vehicle | cost | when |
|---|---|---|
| **computed in place** | **nothing** | the payload is a table `gfx_rowbase_calc` or a glyph shifter can fill — §4.2, §4.4 |
| **the loader blob** | `BOOT2_SECS` 8 → 11: **3 in-run sectors, ~72 ms pre-splash on every machine, and no extra `int 13h` on any geometry** | the payload is code — §4.1, §4.3 |
| a module file | one extra `int 13h`, **~400 ms, on mono only** | if the blob is ever the binding constraint |

The blob figure is `tests/unit/t_blobruns.py --sectors N` on this tree, and it
is the finding that makes shipped code affordable at all: **8, 9, 10, 11 and 12
sectors are all 2 calls on all three geometries.** Only the in-run sectors are
paid, at ~24 ms each on the field 5150, and all of it is before the first splash
pixel.

> **docs/LAST-DROP-BYTES.md §1 and §4 are stale on this point and should not be
> quoted.** They describe a 19-sector blob with 583 bytes free. `BOOT2_SECS` is
> **8** on this tree and `.ovlw` has moved into the FAT window (SPEC.md §2.5.3),
> so the blob is 2,439 + 1,425 of 4,096 — **232 bytes of slack, not 583** — and
> the growth table's sector numbers are all shifted. Re-run the tool.

---

## 4. What to spend it on — four candidates, ranked

Ranked by *evidence already in the tree*, not by appeal. Two of the four are
code that exists today and is `%ifdef`-ed out of the build that needs it, which
makes them the only two with no design risk at all.

### 4.1 Give `kern_small` one of the two drawing features it is refused (BEST)

Both of these are refused on `kern_small` for want of `.text`, and **both are
mono-favouring**:

| feature | bytes | what it buys | where it is refused |
|---|---:|---|---|
| `gfx_line_fast` + `gfx_lf_wide3` | **686** | **4.9×** on a line, and it is **mono-only code by construction** — reached only when `[vid_mono] != 0 && [vid_planes] == 1` | SPEC.md §5.6.4.4, in as many words: *"it is 686 bytes of `.text` and the 128-256KB machine is short of exactly the thing that would be spent"* |
| `gfx_blit1_x` | **698** (`.cold`) | the composed title bar, which on **both** 1bpp adapters is the *faster* bar — 36.5 ms against 40.8 on Hercules, 37.1 against 42.0 on CGA (SPEC.md §5.9.6) — and does not flash | `kern_small` has no `gfx_blit1` at all; `band.inc` says so |

**`kern_small`'s ~1,048 movable bytes buy exactly one of these, not both.** The
first is the better buy on the evidence: it is a larger multiple, it is spent on
code that only a mono machine can reach in the first place, and it needs no band
claim to succeed. The second brings a body that is far today (`COLD_SEG`) into
the segment, which is a second, smaller win on top — it would stop paying the
`cw_*` shims and could read `[cs:vid_rowadd]` again.

**The honest catch, and it is the one to settle first.** `gfx_line_fast` is
`.text` *in a build that does not contain it*, so this is not a copy — the
payload has to be assembled somewhere and shipped, which is §3.2's three
sectors. And its 686 bytes must fit the movable span **after** `vga_solid_rect`
is held aside, which on `kern_small` is 1,048: it fits with 362 to spare, and
adding §4.2 on top (440) does not fit unless `vga_solid_rect` is grouped too.

### 4.2 Give the mono adapters the rows `vid_rowtab` is missing (CHEAPEST)

SPEC.md §39.3.1, which prices the table and then says what `kern_small` does not
get:

> **`kern_small` keeps the 128-row table** … Its low rung crosses a 512-byte
> step at *any* size above 128 — 200 crosses it too, so a smaller table would
> rescue nothing — and `KERN_SMALL_BUDGET` is the figure that has to be defended.

A Hercules is **348 rows** and a CGA is **200**. So on a `kern_small` mono
machine every drawing call below row 128 misses the table and pays **362 cycles
against 132** — on a Hercules that is **63% of the screen**, and the table is
read by `gfx_rowbase`, which §39.3.1 measured being called on every drawing call
in the machine (54 calls on one window raise).

220 more rows is **440 bytes**, it fits, and **it costs no blob**:
`gfx_rowbase_calc` already fills the table lazily as rows are asked for, so the
payload is not shipped — the decider publishes the span and raises
`[vid_rowmax]`, and the existing code does the rest.

**The wrinkle to cost before believing this.** `gfx_rowbase` reads
`[ss:bx + vid_rowtab]`, and `SS` is `LOW_SEG` for all kernel code, where the
reclaimed span is in `KERNEL_SEG`. Either the extension is reached DS-relative
(which is *cheaper* — no override byte — but is a second compare and a second
load in a routine whose whole point is that it is one of each), or the table
moves, or the instruction is patched. **None of the three is free and the third
is self-modifying code**, which this tree has contemplated exactly once and not
adopted (docs/SCHED-IDLE-PLAN.md §8's `NOSMC=1`). Cost it properly before
ranking it above §4.1.

### 4.3 Specialise the 1bpp inner loops (the `kern_big` answer)

`kern_big` already has §4.1's two features, so its ~1,612 bytes need a new
payload, and the standing evidence says where: **the software renderer is one
parameterised core.** `sw_rect` is `SWM_SOLID`/`SWM_GRAY`/`SWM_XOR` behind a
per-row `[sw_mode]` test, and PERFORMANCE.md's three-adapter table is what that
costs — `GFX_FILL_GRAY 64x64` is **4,266 µs on VGA against 8,081 on CGA and
7,797 on Hercules**, and the reason given there is exactly this: *"VGA's interior
`rep` covers four planes at once through Set/Reset, so the loop is short … where
`sw_plane_op` walks a plane with `stosw` and does more work per turn."*

1,612 bytes is roughly three specialised bodies. This is the largest prize and
the only candidate with no existing code to lift, so it is also the only one
that has to be *written* before it can be measured. `tests/gfxbench` on MartyPC
with `VIDEO=cga` and `VIDEO=herc` is the instrument and the rows already exist.

### 4.4 A per-phase pre-shifted glyph cache (SMALLEST REMAINING PRIZE — read the caveat)

A text run has **one pen phase**: every cell advances 8 pixels, so `x & 7` is
invariant across the whole run. A cache of the kernel's 95 glyphs pre-shifted
for *one* phase is 95 × 8 rows × 2 bytes = **1,520 bytes**, which is the span
almost exactly, and it would take the per-cell `shr ax, cl` out of
`FONT_RN_UPX` entirely.

**And most of this prize has already been taken, which is why it is last.** The
raw appeal comes from PERFORMANCE.md Set 64 — `FONT_RUN` 78 cells at x+5 costing
**67.94 ms on CGA against 24.37 aligned, 2.79×** — but **Set 64 predates SPEC.md
§6.1.11**, whose whole point is that *"6.1.4 argued that unaligned cannot be made
fast, and it is right about a CELL and wrong about a RUN"*. Set 100 measures what
is left on a CGA 5150: `FONT_RUN 10 skewed` **76,205 against aligned 46,603 —
1.64×**, not 2.79×. So the headroom is real and it is *bounded by 1.64×*, most of
which is not the shift.

Quote Set 100, never Set 64, for this. It is the trap this section exists to
mark.

---

## 5. Evidence owed by whoever takes a row

1. **The grouping is a refactor of the hottest file in the tree**, and PERFORMANCE.md
   Part 1 rule 5 is the standing warning: keeping the shape of an optimisation is
   not keeping the optimisation. `tests/gfxbench` on all three adapters, before
   and after the grouping **and with no payload at all**, is the first
   measurement — the grouping must be free on VGA before anything is spent on
   mono.
2. **A boot on both 1bpp adapters and on VGA**, because the decider runs between
   `vid_probe_avail` and the first paint.
3. **The `xt-multimon` two-card XT**, which is the machine where `[vid_mono]` is
   a property of a *display* and not of the machine (SPEC.md §39.14.6) — the one
   configuration in which getting §2's gate wrong is visible.
4. **`make test-full`**, which is the only thing that builds `kern_small` at all,
   and §4.1 and §4.2 are `kern_small` changes.

---

## 6. What was looked at and refused

**Returning the bytes to the heap.** SPEC.md §39.22 is why not, in its own
words: *"`.lowbss` is the LAST rung before the heap … so a byte that leaves it
lowers the heap floor directly: there is nothing above it to relocate. Anything
lower in the ladder is pinned under 55 KB of code and would need a relocatable
segment before it could be dropped at all."* Hot drawing code in a rung of its
own above `.lowbss` is reached far from `KERNEL_SEG`, and a far call is 46.7 µs
against a near call's 11. The attempt has been made and it is not recorded in
this tree because it died on branches that no longer exist; this paragraph is
the record that it happened and what it concluded.

**Making the span a heap claim on mono.** SPEC.md §39.22 refused the same idea
for `.vgabuf` and the reasons carry: it would report system memory as a
program's in §28's RAM view, spend one of `MEM_MAX`'s 32 records, and buy a
refusal path that cannot fire. A hole in the middle of `.text` is worse than
`.vgabuf` was, because the heap cannot be extended *downwards* into it at all.

**Doing nothing.** It remains the right answer until somebody wants one of §4's
four things, and this file is written so that the next person to notice the dead
bytes spends ten minutes rather than an afternoon. Neither guard is tight: 15,872
bytes of `KERN_BUDGET` and 7,099 of the 64KB segment are free today, so **this is
not a size argument and must not be sold as one.**
