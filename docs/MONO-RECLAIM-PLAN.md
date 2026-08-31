# The VGA code a mono machine cannot use — reclaimed on `kern_small`, reused on `kern_big`

**A handoff. Nothing here is built.** What is measured is the size and shape of
the VGA-only code, and what each of the two kernels can do with it — which is
**not the same thing**, and that split is the whole structure of this file.

> **Read SPEC.md §39.22 first.** It is the precedent and the argument: `.vgabuf`
> is 1,024 bytes of VGA-only *buffer* that a mono machine already declines at
> boot, and its reasoning about *why that rung and not some other* is what
> decides §3 below.

---

## 0. The verdict, up front

**There are two questions here and they have different answers.**

1. **`kern_small` stops supporting VGA at all (§2) — and that is a REAL
   reclaim.** A 128KB machine has no business with a VGA card. Gated off at
   assembly time, the bytes stop existing: `.text` shrinks, the image rung
   shrinks, the whole ladder moves down and the heap floor with it. **This is
   step 1**, and it is first because it is what makes the rest tractable: the
   grouping pass that a gate needs is the same grouping pass everything else in
   this file wants, and doing it in the other order means writing the gate twice.

2. **`kern_big` keeps VGA, so on `kern_big` the same bytes can only be REUSED in
   place (§3).** They cannot be given back to the heap — SPEC.md §39.22's ladder
   settles it and this file does not re-open it. So `kern_big` is the only
   consumer of the "I reserved this space and now it is dead, what do I put in
   it?" question, and §5 is the ranked answer.

**Measured, per body, off a `[map all]` assembly:**

| | `kern_big` | `kern_small` |
|---|---:|---:|
| VGA-only `.text` in `vga12.inc` | **1,771** | **~1,207** |
| …less `vga_solid_rect`, which is *fallen into* (§1.2) | 1,612 | ~1,048 |
| VGA-only `.text` in the rest of the kernel (§2.1) | — | **~460, estimated** |
| the `[vid_mono]` / `[vid_planes]` dispatch that folds away (§2.2) | — | **~220, estimated** |
| **what `kern_small` stops assembling** | — | **~1,700–1,900** |

**The asymmetry is the load-bearing fact and it is not an oversight.** A VGA
machine is *mono + VGA* — it can be switched to a mono display at run time
(SPEC.md §39.11) — so it needs both renderers resident for ever. A mono machine
is *just mono* and can never acquire VGA. **Only one side of the kernel is ever
reclaimable**, and the gate is `[vid_avail] & VID_A_VGA`, never `[vid_mono]`.
On `kern_small` the gate is stronger still: it is an **assembly-time** `%ifdef`,
because that build simply does not drive the card.

**Three findings that change what should be built:**

- **The row table is worth 512 bytes and step 1 pays for it three times over
  (§4).** Measured whole-machine on a CGA 5150: the screen saver **4.69% →
  2.85%** and Missile Command **1.66% → 0.75%**. It buys applications that draw
  low on the screen and buys the desktop chrome nothing.
- **`GFX_FILL_GRAY` is the wrong target for a 1bpp specialisation, and the
  biggest number is not the best target either (§5).** `sw_blit_row.abyte` is
  **27.7% of the whole machine in Paint** and it IS the mono fast path — traced,
  because Paint has fallbacks — but it is 27.7% *because it is the whole job done
  well*, having already been through SPEC.md §5.4.1.1 and §5.4.1.2 (canvas blit
  2,431 → 259 ms). **The headroom is in `sw_col`** (10.0% in WIREFRAME, no
  specialisation pass at all) **and `sw_rect`/`sw_plane_op`**.
- **TANK ATTACK is helped by NEITHER option (§5.4).** An fsx bracket that has set
  a mode owns every pixel: `apps/tank/tkraster.inc` has *"not one kernel drawing
  slot"* in it, so during play it never enters `gfx_rowbase`, `sw_col`, `sw_rect`
  or `sw_blit_row`. If a game of that shape is the target, the work is
  docs/GFX-FSX-PLAN.md's, not this file's.
- **The lost character on a straddle is not a speed problem and the glyph cache
  would not fix it (§6).** The character is not drawn slowly — it is **not drawn
  at all**, by one `ja .done` in `font_char` under SPEC.md §39.14.2's whole-cell
  rule. **docs/HANDOFF-FONTCHAR-SEAM.md is its standalone handoff.**

---

## 1. What the space is — measured, not remembered

Method is docs/LAST-DROP-BYTES.md §8.1's: a `[map all …]` line at the top of a
*copy* of `kernel.asm`, a body's size being its address to the next label in the
same section; local labels where a VGA-only arm sits inside a shared body.

```sh
printf '[map all /tmp/k.map]\n' > /tmp/kmap.asm && cat kernel/kernel.asm >> /tmp/kmap.asm
nasm -f bin -w+error -I kernel/ -I apps/ -I build/ -o /dev/null /tmp/kmap.asm
```

### 1.1 `vga12.inc`, both builds

| body | big | small | why it is dead on a mono machine |
|---|---:|---:|---|
| `vga_blit_prow` | 290 | — | SPEC.md §5.4.1.3's planar row decoder; `GFX_PLANE` is `kern_big`'s |
| `gfx_fill_pat_raw` (VGA body) | 175 | 175 | the mono arm is `jne sw_fill_pat` at the door |
| `vga_solid_rect` | 159 | 159 | **held aside — §1.2** |
| `vga_blit_span` | 157 | 157 | |
| `gfx_fill_gray_raw` (VGA body) | 151 | 151 | the mono arm is `jne sw_fill_gray` at the door |
| `gfx_line_runs` | 141 | 141 | the major-axis run walk; mono takes `gfx_line_fast`/`gfx_line_mono` |
| `vga_prow_emit` | 115 | — | the decoder's emit |
| `vga_restore_vram` (body) | 112 | 112 | mono goes to `sw_restore` |
| `vga_save_vram` (body) | 90 | 90 | mono goes to `sw_save` |
| `vga_p4build` | 76 | — | builds `vga_p4tab`, which is in `.vgabuf` and already declined |
| `vgas_lincopy` | 73 | 73 | `gfx_scroll`'s linear copy; mono takes `vgas_bankcopy` |
| `gfx_spans.vga` | 69 | ~2 | a stub on `kern_small` |
| `gfx_blit4.vga` | 54 | ~40 | |
| `vga_set_color` / `vga_set_xor` / `vga_gc_reset` | 59 | 59 | the three GC writers |
| `vga_xor_fill_vram` + `vga_xor_rect_vram` | 24 | 24 | |
| `vga_pat_stage` | 14 | 14 | |
| `vga_sr_on` | 12 | 12 | |
| **total** | **1,771** | **~1,207** | |

**`vga_rect_setup` (123 bytes) is NOT in this table, and it is in the wrong
file.** Its masks and offsets serve **both** renderers — `softgfx.inc` says so
in its own header — so it stays in every build, and it is *hot*: PERFORMANCE.md
Set 102 profiles `vga_rect_setup.x2ok` at **7.3% of the whole machine** in the
screen saver, on a CGA. **Its name is the only VGA thing about it.** It is a
leftover from the last split of the VGA file — a shared body that stayed behind
in the adapter-specific one — and the grouping pass should **move it into
`softgfx.inc` and rename it**, because a shared body sitting inside a region
that is about to be `%ifdef`-ed out is the defect that gate would otherwise
ship. *If it is not VGA-specific it does not belong in the VGA file*, and the
same sweep should ask the question of every other body there rather than only
this one.

### 1.2 The one body that is fallen into, not called

`gfx_fill_raw` ends with the mono test and then **falls through**:

```
gfx_fill_raw:
    cmp byte [vid_mono], 0      ; 1bpp? then the software renderer IS
    jne sw_fill                 ; the renderer - and the flag store is BELOW
    mov byte [vga_xorm], 0      ; this jump, so the 1bpp arm is byte-identical
vga_solid_rect:
```

Grouping it elsewhere inserts a `jmp` into the hottest fill path in the system —
every window background, every frame, every glyph cell's erase — for 159 bytes.
**That is the trade to refuse on `kern_big`**, which is why every figure above is
quoted twice, and it is very likely the "one super hot function aside" the
earlier attempts hit.

**On `kern_small` the problem does not arise.** The gate is an `%ifdef`, so the
fall-through is *deleted* rather than moved: `gfx_fill_raw` becomes an
unconditional entry to `sw_fill` (or the label simply becomes `sw_fill`), and
there is no jump to insert. That is the second reason step 1 comes first.

---

## 2. Step 1 — `kern_small` gates VGA off entirely

### 2.1 What stops assembling, beyond `vga12.inc`

Identified by reading, sized off the `kern_small` map. **These are estimates and
the plan says so**; only the gate itself can make them exact.

| file | body | ~bytes | what it is |
|---|---|---:|---|
| `vga12.inc` | §1.1's table | **1,207** | measured |
| `icons.inc` | `ico_pass` + `ico_core`'s VGA arm | ~184 | the Set/Reset masked icon passes (`ico_pass_bb` is the 1bpp twin and stays) |
| `fsx.inc` | `fsx_modex` + its CRTC table + `fsx_mode`'s VGA rows | ~120 | SPEC.md §53.7's mode X — an fsx bracket on a mono machine cannot ask for it |
| `font.inc` | `font_char.vram` | 104 | SPEC.md §6.1.10's planar cell |
| `viddet.inc` | the mode row, `vid_detect.vga`, `vid_apply`'s VGA arms | ~50 | |
| **subtotal** | | **~1,665** | |

`.vgabuf` is already 0 on `kern_small` (no `GFX_PLANE`), so there is nothing to
win there; `splash.inc`'s VGA arm is in `.boot2` and costs no resident byte
either way. `vidsel.inc`'s probe is already in the boot overlay.

### 2.2 …and the dispatch that folds away, which is both bytes and cycles

There are **28** `cmp byte [vid_mono], 0` sites and **4** `cmp byte
[vid_planes], 1` sites in the tree. With VGA gated off, `[vid_mono]` is 1 by
construction and `[vid_planes]` is always 1, so each site becomes a direct call
or nothing at all — about **7 bytes each, ~220 in total**.

**The cycles matter more than the bytes and this is the part to measure.** Those
tests are not in cold code: `gfx_fill_raw`, `gfx_fill_gray_raw`,
`gfx_fill_pat_raw`, `gfx_xor_fill_raw`, `gfx_blit4`, `gfx_spans`, `gfx_line_raw`,
`vga_save_vram` and `vga_restore_vram` all begin with one, and the last two are
entered **from inside the mouse ISR**. A compare-and-branch against a memory
byte is ~15 clocks on an 8088 plus the fetch, on the fixed cost of every drawing
call — which is exactly the shape SPEC.md §39.3.1 and §39.3.2 attacked and got
8% off the small shapes for.

**So step 1 is not only a size change**, and whoever takes it should measure it
as a performance change too: `tests/gfxbench` with `VIDEO=cga` and `VIDEO=herc`
on `make small`, before and after.

### 2.3 What it is worth

~1,700–1,900 bytes of `.text` is **three or four 512-byte image rungs**, which
come straight off `KERN_SIZE` and off the heap floor with it. That is the
figure to take to `KERN_SMALL_BUDGET`, which docs/KERNEL-MEMORY.md moves 22, 23
and 32 record as the one nobody watches — and it is a move in the direction that
table has never had one in.

### 2.4 What has to be settled before it is built

1. **What a `kern_small` machine with a VGA card actually does.** It boots today.
   After this it must fail *legibly* rather than into a black screen —
   `vid_detect` finding VGA and no renderer for it is a refusal, and SPEC.md
   §39.11.1.1's `vid_hprobe` precedent is that "not detected" needs to be
   distinguishable in the field from a screenshot. This is the one user-visible
   decision in step 1 and it is the owner's, not the implementer's.
2. **`make test-full` is the only thing that builds `kern_small` at all**, which
   is how that build has been *discovered* broken three times rather than
   reported broken. Every step here needs a row in it.
3. **The `VIDEO=` knob kernels.** `make VIDEO=cga` on a `kern_small` tree is now
   the normal case rather than a knob; `VIDEO=vga` with `KERN_SMALL=1` must
   refuse at assembly time rather than build something that cannot draw.

---

## 3. Why `kern_big` cannot do the same thing

SPEC.md §39.22, in its own words:

> `.lowbss` is the LAST rung before the heap … so a byte that leaves it lowers
> the heap floor *directly*: there is nothing above it to relocate. Anything
> lower in the ladder is pinned under 55 KB of code and would need a relocatable
> segment before it could be dropped at all.

`kern_big` must keep the VGA bodies in the build, because the machine may switch
to VGA — or from it. A body that is present but dead is a hole in the middle of
`.text`, and a hole in the middle of `.text` cannot be given back: the ladder
above it is at build-time segment constants. Moving the bodies to a rung of
their own above `.lowbss` makes every call to them **far** — 46.7 µs against a
near call's 11 — which is the attempt that has already been made and abandoned.
It is not recorded in this tree because it died on branches that no longer
exist; this paragraph is the record that it happened and what it concluded.

**So on `kern_big` the only move is to put something else in the hole**, decided
at boot by a body in `.ovl` that tests `[vid_avail] & VID_A_VGA` and dies with
the blob at `spl_finish`. `.ovl` has **111 bytes free** at today's `BOOT2_SECS`
of 8 — enough for the decider, not for a payload. A payload that is a *table*
can be computed in place and costs nothing; a payload that is *code* has to be
shipped, which is `BOOT2_SECS` 8 → 11: **three in-run sectors, ~72 ms of
pre-splash time on every machine, and no extra `int 13h` on any geometry**
(`tests/unit/t_blobruns.py --sectors N`; 8 through 12 are all 2 calls on all
three geometries).

**The enforcement is not optional.** Overwriting a body is safe only while
nothing reachable on a mono machine enters it, and today that is true by branch
rather than by construction. `tools/os88ovlchk.py` plus `tests/ovlrefs.txt` is
the idiom the tree already has for exactly this, and a `tests/vgarefs.txt` of
the same shape is what stops the seventeenth body quietly gaining a caller.

> **docs/LAST-DROP-BYTES.md §1 and §4 are stale on the blob and should not be
> quoted.** They describe a 19-sector blob with 583 bytes free. `BOOT2_SECS` is
> **8** on this tree and `.ovlw` has moved into the FAT window (SPEC.md §2.5.3),
> so the slack is **232 bytes**. Re-run the tool.

---

## 4. The row table, costed

The question asked of this file: *what does it cost, what performance does it
buy, and who would use that performance?* All three are already measured —
PERFORMANCE.md **Set 106** and **Set 102**, on a MartyPC cycle-accurate 5150
with a CGA — so this section is arithmetic rather than a proposal.

### 4.1 What it costs: 512 bytes, once

`vid_rowtab` is 128 rows on `kern_small` and 348 on `kern_big`. A Hercules is
**348 rows** and a CGA is **200**, so `kern_small`'s table covers the top **64%
of a CGA and the top 37% of a Hercules**; below that, `gfx_rowbase` misses and
takes `gfx_rowbase_calc`.

| rows | `.lowbss` | low rung | `KERN_BUDGET` |
|---:|---:|---:|---:|
| **128** (`kern_small` today) | 8,086 | 9,216 | — |
| 200 | 8,342 | 9,728 | **+512** |
| **348** | 8,598 | 9,728 | **+512** |
| 480 | 8,854 | 10,240 | +1,024 |

(Set 106's `.lowbss` column is `kern_big`'s, so those absolute figures do not
describe `kern_small`; **the rung deltas are what transfer** and they are what
this section spends. Re-measure the absolute column on `make small` before
quoting it.)

**200 and 348 cost the same rung, so nobody should ever pick 200.** That is also
why a *smaller* table cannot rescue `kern_small` — the step is crossed at any
size above 128 — and it is exactly the argument SPEC.md §39.3.1 uses to refuse
it there today. **Step 1 removes that argument**: ~1,700 bytes of `.text` back is
three or four image rungs, and this is one low rung. Net, `kern_small` is still
**1,000–1,500 bytes smaller** *and* has the table.

### 4.2 What it buys: the miss path goes to zero

`gfx_rowbase` + `gfx_rowbase_calc` as a percentage of the **whole machine**, CGA:

| scenario | 128 rows | 348 rows |
|---|---:|---:|
| screen saver | 4.69% | **3.14%** |
| Missile Command | 1.66% | **0.69%** |

and re-profiled against the kernel that actually shipped with it:

| scenario | CGA before | **CGA now** |
|---|---:|---:|
| screen saver | 4.69% | **2.85%** |
| Missile Command | 1.66% | **0.75%** |
| Paint | 1.94% | **1.22%** |
| **WIREFRAME** | **1.45%** | **1.46%** |

**The miss path is 0.00% in all four on CGA at 348.** The per-call arithmetic
behind it: a table hit is **132 cycles**, a miss **362**, and the pre-table body
was 319 — so a miss costs **+230 cycles on the fixed part of a drawing call**,
against a minimal `gfx_fill`'s 2,459.

### 4.3 Who uses it — and who does not

**Applications that draw low on the screen, and nothing else.** The menu bar is
at the top and rows 0–127 already hit, so the desktop chrome gains nothing; this
is not a redraw-budget item.

**WIREFRAME is the counter-example and it should be quoted alongside the wins:
1.45% → 1.46%, no gain at all.** The saver gains 1.84 points of the whole
machine because it is full-screen; Missile Command gains 0.91 because a game's
window is in the bottom third.

**But read that counter-example correctly: it is a fact about WHERE THAT WINDOW
WAS IN THAT RUN, not a property of WIREFRAME.** A window that opens high can be
dragged low, and the same application then lands on the other side of the
figure. So the honest statement is not *"WIREFRAME does not benefit"* — it is
**the benefit is a function of the window's y, and every profile of it is a
sample of one position.** What that costs the ranking in §5.4 is that the row
table's win has a *floor of zero* and its quoted numbers are upper-ish samples,
while a loop specialisation's win is the same wherever the window is.

### 4.4 The gap in the evidence, stated plainly

**Every figure above is CGA.** A Hercules is 348 rows against a CGA's 200, so
`kern_small`'s 128-row table covers **37%** of a Hercules screen against 64% of
a CGA's — the miss rate is roughly *twice* as high and the win should be
correspondingly larger. **Nobody has measured it.** Set 106 profiled CGA and
VGA only. The Hercules reading is one `make small VIDEO=herc` and one profiler
run (PERFORMANCE.md Set 20's `flat_ip` sampler, which costs the guest nothing),
and it should be taken before this row is banked rather than after — it is the
adapter with the most to gain and the one the figure is being justified on.

---

## 5. Specialised 1bpp inner loops — and `GFX_FILL_GRAY` is the wrong target

### 5.1 What the profiles actually say

PERFORMANCE.md **Set 102**: a CS:IP sampling profiler at ~210 Hz, 8,700–9,500
samples per scenario over ~150 guest seconds, MartyPC `os8088_5150_cga_gla` —
**a CGA 5150, so every routine below is the 1bpp renderer**. The top of each
profile:

| scenario | the top of its profile |
|---|---|
| **Paint** | **`sw_blit_row.abyte` 27.7%** — one routine, more than a quarter of the machine |
| **WIREFRAME** | **`sw_col.row` 10.0%**, then six `gfx_line_fast` arms totalling ~20% |
| **screen saver** | `vga_rect_setup.x2ok` 7.3%, **`sw_rect`/`sw_col`/`sw_plane_op` ~12%** |
| Missile Command | `sch_switch` + `sch_account` + `task_yield` ≈ 22% — scheduler-bound before it is draw-bound |

**60–85% of every one of these four scenarios is in kernel drawing code**, which
is Set 102's own headline.

### 5.2 `sw_blit_row` IS the fast path on mono — checked, because it has fallbacks

Paint holds its canvas two ways and the layering matters, so this was traced
rather than assumed (`apps/paint/paint.asm:3145–3175`):

* **planar** — `OSAPI_GFX_BLITP`, SPEC.md §5.4.3's four-plane form;
* **packed nibbles** — `OSAPI_GFX_BLIT4` → `gfx_blit4`.

**On a 1bpp adapter the planar form is REFUSED**, and Paint's own comment says
so: *"A 1bpp adapter under us, a canvas origin off the byte grid, a straddled
seam: every refusal means 'you cannot hold your picture that way here'"* — so
`pt_topacked` converts the canvas once and every repaint after it is
`GFX_BLIT4`. Inside `gfx_blit4`, a mono block that is on screen in x sets
`[gfx_blit_fst] = 1` and the row loop calls **`sw_blit_row` for the whole row,
with no run scan at all** (`kernel/vga12.inc:2745`). `sw_blit_row` has exactly
one caller in the tree and that is it.

**So yes: on mono it is the fast path, not a fallback**, and Set 102's 27.7% was
measured on a CGA — the very adapter that forces the packed form. The only way
back off it is a blit clipped in x, which Paint, ArtfulType and Solitaire all
avoid by clipping their own blits (`softgfx.inc`'s header says so).

**…and that is also the argument against picking it first.** `sw_blit_row` is
27.7% because it is *the whole job done well*, not because it is naive. It has
already been through **two** optimisation passes: SPEC.md §5.4.1.1 replaced the
run scan with a 256-byte pair table (canvas blit **2,431 → 517 ms** on CGA) and
§5.4.1.2 gave each x-parity a body of its own (**517 → 259 ms even, 508 → 299
odd**) — docs/HANDOFF-REDRAW.md carries both. `.abyte` is that second pass's
aligned body, already down to **37 bytes per eight pixels**. A third pass is
possible but its headroom is nothing like its share.

### 5.3 So the ranking, corrected

1. **`sw_col`** — 10.0% of the machine in WIREFRAME and part of the saver's ~12%,
   and **it has had no specialisation pass at all**. Its row body is a
   read-modify-write pair (`and [es:di],bl` / `or [es:di],al`) plus a pattern
   `xor` plus the bank-wrap test, ~25 bytes of traffic a row on an 8088's 8-bit
   bus. A full-mask solid column is one `mov [es:di],al` — the RMW pair is ~40
   clocks of ~100 and a specialised entry does not owe it. The wrap test is
   hoistable within a bank. **This is the one with headroom and evidence both.**
2. **`sw_rect` / `sw_plane_op`** — the parameterised core, `SWM_SOLID` /
   `SWM_GRAY` / `SWM_XOR` behind a per-row `[sw_mode]` test. `sw_rect` alone
   spends **~216 clocks, about 7%, on eight pushes and eight pops** it takes only
   to honour `gfx_fill`'s "clobbers flags" contract (PERFORMANCE.md Part 2). A
   specialised entry that does not owe that contract is bytes well spent.
3. **`sw_blit_row`** — the largest single number in the profile set and the
   smallest remaining headroom, for §5.2's reason. Worth revisiting only with a
   measurement in hand.

**`GFX_FILL_GRAY` is correctly refused as a target.** `UI_GRAY` is the shared
scrollbar trough and `fprog.inc`'s progress widget — a scrollbar is nowhere near
the capacity of any machine, and it appears in **none** of Set 102's four
profiles. docs/LAST-DROP-BYTES.md §7 records the owner's ruling on the same body
from the other direction (a 33% regression refused because the slot is public);
the two agree.

### 5.4 …and what neither option does: TANK ATTACK

**Neither the row table nor the 1bpp loops help TANK ATTACK, at all**, and this
is the finding that should decide where effort goes if a game like it is the
target. `apps/tank/tkraster.inc`, in its own header:

> Three backends behind four entries … and **NOT ONE kernel drawing slot among
> them**, because SPEC.md §53.7 makes every one of them illegal the moment
> `fsx_mode` returns. What is here is what the kernel would have had to lend and
> cannot.

An fsx bracket that has set a mode owns every pixel: TANK ATTACK carries its own
Bresenham, its own dirty-span tracking and its own per-adapter blit, and during
play it never enters `gfx_rowbase`, `sw_col`, `sw_rect` or `sw_blit_row`. **The
work that helps it is docs/GFX-FSX-PLAN.md's, not this file's** — and that file
already names the shape of it, including a `gfx_line` batch form priced and
deliberately not built.

**What this file's options do help** is everything that draws *through the
kernel*: the screen saver (full-screen, `sw_rect`/`sw_col`/`sw_plane_op` ~12%),
Paint's live canvas (`sw_blit_row` 27.7%), WIREFRAME (`sw_col.row` 10.0%), and
windowed games — though Missile Command is **scheduler-bound at ~22%** before it
is draw-bound, so a windowed real-time game is a docs/SCHED-IDLE-PLAN.md
question first.

### 5.5 The two options are not competing for the same build

| | `kern_small` | `kern_big` |
|---|---|---|
| row table 128 → 348 | **available**, 512 B, funded by step 1 | **already 348** — nothing to buy |
| the 1bpp loops | available from the reclaim | **the only option**, from the hole |

`kern_big` already carries every row of both 1bpp adapters, so on the build that
*has* the hole the row table is not on the menu at all. **The either/or exists
only on `kern_small`**: bank the ~1,700 reclaimed bytes, or spend 512 on the
table and the rest on loops. On the criterion of *games and live drawing*, the
loops win on every scenario that is measured — and on `kern_big` they win by
default.

### 5.6 What 1,612 bytes buys

Roughly three specialised bodies, and §5.3 says which three. This is the only
candidate in this file with **no existing code to lift**, so it has to be written
before it can be measured — but the instrument is in place (`tests/gfxbench` for
the primitive, PERFORMANCE.md Set 20's `flat_ip` sampler for the application,
which costs the guest nothing) and the baseline numbers to beat are §5.1's.

**One warning, and it is PERFORMANCE.md Part 1 rule 5:** the reason for these
bodies is speed, so the measurement must show the reason survived, not the
structure. A specialisation that emits the designed number of instructions and
walks the plane the same way is `gfx_blit4`'s first version again.

## 6. The lost character on a straddle — a defect, and the glyph cache does not fix it

### 6.1 What is actually happening

**Reported behaviour:** on an extended desktop, dragging a window into a
straddle loses a character from unaligned text such as a title bar.

**The cause is `font_char`, `kernel/font.inc:236`:**

```
    GFXDENTERCD                 ; the cell goes WHOLE onto the display holding
                                ; its top-left corner (SPEC.md 39.14.2)
    ...
    cmp cx, [vid_cwm8]          ; unsigned: negative x fails this too
    ja .done                    ; -> the cell draws NOTHING
```

`[vid_cwm8]` is the current display's width less 8. A cell whose top-left is on
display A but which extends past A's right edge is entered on A and then fails
that test, so **the whole cell is dropped** — not clipped, dropped.

**Why only unaligned text loses one.** SPEC.md §39.14.6 already exempted the
*run* from §39.14.2: a run that does not fit one display goes **per cell,
untranslated**, and each `font_char` picks its own display. That fixed the
straddled Note Pad in the field. But the individual cell is still whole-shape,
and the seam is at the primary's own width — **640 or 720, both multiples of
8**. So:

* **aligned run** — cells sit at multiples of 8, the seam falls *between* two of
  them, nothing straddles, nothing is lost;
* **unaligned run** — cells sit at `x mod 8 ≠ 0`, so **exactly one cell straddles
  the seam and exactly one character disappears.**

That is the report, exactly, and it explains why the alignment work made it rare
rather than fixing it.

### 6.2 So the glyph cache is the wrong tool

A per-phase pre-shifted glyph table makes an unaligned cell *cheaper to draw*.
The straddling cell is not drawn slowly — **it is not drawn at all**, and it
would not be drawn by a cache either, because the `ja .done` is above everything
a cache would touch. **The two are unrelated, and the cache should be judged on
its own (much reduced) merits: §7.**

### 6.3 The fix, sketched — and it now has a handoff of its own

> **docs/HANDOFF-FONTCHAR-SEAM.md is the standalone write-up**, self-contained
> for somebody with no context here: the mechanism, why it is exactly one
> character, the §39.14.2/§39.14.6 history that must not be re-litigated, the
> `TITLESNAP=1` A/B that reproduces and controls it in one knob, the fix, and
> the evidence owed. What is below is the summary.


The precedent is in the same routine, eight lines down. For the **clip region**
`font_char` already degrades rather than refusing — *"a cell an edge crosses
horizontally draws the rows on our side of it rather than nothing at all, which
is what left a half-covered Timer frozen at the second it was covered"*. The
display seam is the one edge that still drops the whole cell.

The straddling cell wants the same treatment one axis over: issue it **twice,
once per display**, each pass writing only the columns on its own side.
SPEC.md §39.14.7.2 is the precedent for the cut itself — a straddling
`gfx_blit4` is cut at the seam and run once per half, and there is exactly one
seam because displays are edge to edge. Two properties make the text case
easier than the blit case:

* the seam is a **multiple of 8**, so each half is a sub-byte masked write and
  never a nibble-phase problem;
* `font_char` already **has** a masked path — the one it takes on a planar
  target or at an unaligned x — so the pass exists and only the column mask is
  new.

**Cost it before building it.** At most one cell per run straddles, and only
while a window is *dragged across a seam*, which SPEC.md §39.14.2 itself calls a
transient state rather than a configuration. The counter-argument is §39.14.2's
own: *"on two physically separate monitors with a bezel between them there is
nothing to see."* That argument is strong for a rect and weak for a letter —
§39.14.6 already conceded it once for the run, and this is the same concession
one level down. **It is the owner's call whether a missing character in a
straddled title bar is worth the bytes**, and this section exists so the call is
made against the real cause rather than against a glyph cache that would not
have fixed it.

**`TITLESNAP=1` already avoids it for titles** by centring the caption on the
nearest 8px cell (docs/TEXT-PLAN.md §6.1), and `wm_snap` avoids it for windows.
Neither is a fix — they move the text so the case does not arise — but between
them they are why this is rare enough to have gone unwritten until now.

---

## 7. The glyph cache — what is left of it

A text run has **one pen phase**: every cell advances 8 pixels, so `x & 7` is
invariant across a run. A cache of the kernel's 95 glyphs pre-shifted for one
phase is 95 × 8 rows × 2 bytes = **1,520 bytes** — the `kern_big` span almost
exactly.

**Most of the prize has already been taken, twice.**

* **SPEC.md §6.1.11 took the algorithmic half.** *"6.1.4 argued that unaligned
  cannot be made fast, and it is right about a CELL and wrong about a RUN."* The
  shift is now one instruction a cell and no table. PERFORMANCE.md Set 64's
  2.79× penalty **predates it**; Set 100 measures what is left on a CGA 5150 at
  **1.64×** (`FONT_RUN 10 skewed` 76,205 against aligned 46,603). Quote Set 100,
  never Set 64.
* **The alignment work took the exposure.** `wm_snap` is on by default and most
  applications have been converted, so unaligned runs are the exception rather
  than the rule.

What is left is a bounded fraction of a 1.64× case that is now uncommon, against
1,520 bytes and a rebuild cost whenever the phase changes. **On that evidence it
is last of the four and should stay unbuilt** unless somebody produces a
profile in which unaligned text is near the top — which none of Set 102's four
scenarios is.

---

## 8. Order of work

1. **Group the VGA-only bodies and put them behind one gate** (`%ifdef GFX_VGA`,
   on for `kern_big`, off for `kern_small`), moving `vga_rect_setup` into
   `softgfx.inc` on the way and leaving `vga_solid_rect`'s fall-through alone on
   `kern_big`. Prove the grouping is **free on VGA** with `gfxbench` before
   anything is spent — PERFORMANCE.md Part 1 rule 5.
2. **`kern_small` builds with the gate off** (§2). Measure it as a *speed* change
   as well as a size one (§2.2), and settle §2.4's three questions first.
3. **The row table on `kern_small`** (§4), funded by step 2 — after the Hercules
   reading of §4.4 is taken.
4. **`kern_big`'s reuse** (§3 mechanism, §5 payload), which is the only step that
   needs the `.ovl` decider, the blob sectors and the `tests/vgarefs.txt`
   ratchet.
5. **The straddle fix** — **docs/HANDOFF-FONTCHAR-SEAM.md**, independent of all
   of the above and separated from it deliberately: it is a correctness change
   and everything else here is a budget change.

**And one thing that is NOT on this list.** If the goal is a game like TANK
ATTACK, none of steps 1–4 reaches it (§5.4). That work is
docs/GFX-FSX-PLAN.md's, and it should be picked up there rather than smuggled
in here — this file's options all live on the kernel's side of a boundary that
an fsx bracket has already crossed.

## 9. Evidence owed by whoever takes a row

1. **A boot on both 1bpp adapters and on VGA**, plus `xt-multimon` — the two-card
   XT is the one machine where `[vid_mono]` is a property of a *display* rather
   than of the machine (SPEC.md §39.14.6), and the only configuration in which
   getting the gate wrong is visible.
2. **`make test-full`**, which is the only thing that builds `kern_small`.
3. **A `kern_small` machine offered a VGA card** — §2.4's first question, and the
   one thing in this file a user can see.
4. **`gfxbench` on all three adapters before and after the grouping alone**, with
   no payload and no gate, so that step 1's cost is separated from step 2's win.
