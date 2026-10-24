# Common UI: what sharing `apps/os88ui.inc` would cost, three ways

**STUDY, nothing built.** Branch `common-ui`, cut from `kernel-size-14` at
`2bc3442`. The question is the owner's: the shared UI library is compiled into
every package that uses it, so its cost grows with the number of packages, on
disk and in RAM. Three options were asked about:

- **A.** A package uses the UI elements the kernel **already hosts**, because
  the Disk window and the Standard File dialog use them too.
- **B.** A **one-per-disk library file**. The loader takes the pieces a
  package needs, leaves out the rest, and the package ends up exactly as it is
  today.
- **C.** The **whole library in the kernel**, as small as possible, with one
  API per element or one API to reach all of them.

Every figure here is MEASURED on this tree unless it says ESTIMATE.
`python3 tools/os88uicost.py` re-derives the package and disk tables in about
a minute. The kernel rows come from `tools/os88sym.py`'s map on both builds.

## 0. The answer in one table

| | resident kernel bytes | what it saves | per launch | verdict |
|---|---|---|---|---|
| **A** | **~170-200 `.cold` + ~32 `.bss`** on both kernels (ESTIMATE). The bodies are already resident | **~12.2 KB of image across 33 packages and drivers** (MEASURED), so the same in RAM per open instance (242-718 B each) and ~10 KB of disk across the tree | +1 rare cell and a small copy per button or bar draw: ~2-4% of a button's draw (ESTIMATE) | **do it**: a small, fixed resident cost buys the largest saving here. kern_small's diet rule (SPEC.md 39.27.4) makes it the owner's decision there |
| **B** | ~350-450 (ESTIMATE) for a loader in the kernel, or ~200 B **per package** for one in each package | **disk only**, and by design no RAM: ~8 KB net on `apps360` (2% of the disk), ~1 KB on `games360`, a LOSS on `media360` (ESTIMATE from MEASURED dedup) | **+1 file open and read, ~0.4-0.8 s on an XT floppy** unless cached | **feasible, not recommended**. It brings back the sidecar file that O88-MULTISEG-PLAN removed from C64, and it adds version skew between the library and its packages. A gets about half the disk saving and also saves RAM |
| **C** resident | the union is **6,748 B** with every routine at its largest variant, and **9,792 B** with every variant. That is over kern_big's **2,560 spare**, and `.cold` is over the ROM window's **3,177 spare** | the whole ~50.5 KB that 56 images carry today | as A | **refused as resident**: it does not fit, and kern_small cannot pay for it at all |
| **C** as a module | ~60 B + 4 B per entry (ESTIMATE) | shared RAM, but the claim is rounded up to whole KB and loaded once for every client | `mod_need` needs the **system disk** (`[dsk_bootvol]`) | RAM is **worse than today below ~4 open UI packages**, and a one-drive machine running from the apps floppy cannot load it |
| **one door or one cell per element** | a rare cell is **6 B each**. One door is **~25-30 B plus 2 B per function** | | one table lookup, a few µs | **one door** once there are more than ~6 functions. The lookup is cheaper than the ABI it avoids |

The recommendation is in section 6. The rest of this document says where the
numbers came from and what each option breaks.

## 1. What the library costs today

`apps/os88ui.inc` is 6,586 lines and **emits code**. Each package switches its
regions on with `OS88UI_*` defines. 65 sources include it. `os88uicost.py`
assembled 56 of them. The other nine need generated inputs that a plain `make`
does not produce. Five are C
sources (Lemmings, LOOM and its preview module, PaccMan, Weave), whose
`.gen.asm` needs `build/cc`. The other four are DrMarco, Excitebike, The Wire
and HDDTOOL, which need art or defines from their own rules. All nine are
named as skipped, not estimated.

- **50,519 bytes** of library code across the 56 images. That is how much of
  each image comes from this one file.
- Only **9,792 bytes** are distinct: **152 (routine, length) variants**, after
  masking the base-relative words (section 4.1 says how).
- The heaviest routines:

| routine | images | bytes in all | variants (lengths) |
|---|---|---|---|
| `os88ui_btn` | 34 | 10,530 | 248, 256, 270 plain; 636, 728, 742 with `OS88UI_BIMG`/`BOWN` |
| `os88ui_about_d` | 39 | 6,736 | 22, 175, 179, 219 |
| `os88ui_glyph` | 14 | 1,710 | 99, 111, 135 |
| `os88ui_sbar` + `sbmove` + `sbhit` + `sbthumb` + `sbthdraw` | 11 | 5,237 | one or two each |
| `os88ui_btninit`/`btnclick`/`btndrag`/`btnup`/`bfind`/`bfrec`/`btnpress` (the gesture) | 18-22 | 4,590 | one each |
| `os88ui_bhit` | 34 | 782 | 23 |

On disk the packages are LZ4-packed. Library code alone packs to about **85%**
of its size inside one package (Note Pad's 1,981 bytes pack to 1,734, Word's
4,331 to 3,443). The 9,792-byte deduplicated set packs to **5,642** (LZ4) or
**4,879** (LZB), about 58%. That gap is why a deduplicated library compresses
better than the same bytes spread across packages.

### 1.1 What the kernel already hosts

The kernel includes the same file once, with `OS88UI_KERNEL` defined, into
`.cold` (`kernel/fdlg.inc:1236`). The resident `os88ui_*` symbols are:

| build | `.cold` | `.bss` | routines |
|---|---|---|---|
| kern_big | **1,122** | 56 | `btn` 222, `sbar` 133, `sbmove` 101, `sbpos` 98, `sbhit` 87, `sbthumb` 85, `sbtrack` 76, `sbthdraw` 56, `sbgrab` 55, `kbtn` 49, `sbdrop` 36, `sbmine` 31, `bhit` 23, `sbfix` 14, `sbcx`/`sbrate` 12, `fire` 10, `arm`/`armed`/`arm_f`/`btn_f` 4 |
| kern_small | **772** | 42 | `btn`, `sbar`, `sbmove`, `sbhit`, `sbthumb`, `sbthdraw`, `kbtn`, `bhit`, `sbcx`, `btn_f`. There is no thumb drag (`OS88UI_SBDRAG`) and no arm (`OS88UI_ARM` is `KERN_BIG`'s) |

The glyph (check box and radio, 278 B) is in `CTRL.DRV`'s image (`.modu`) on
both builds. It is **not resident**, so A cannot reach it.

## 2. The obstacle A and C share: whose DS?

Every `os88ui_*` routine reads its arguments through DS: the rect at `[bx]`,
the record, the label at `SI`. In a package DS is the **package's** segment.
In the kernel DS is `KERNEL_SEG`, and the kernel arm also reads kernel state
directly (`[gfx_color]`, `[vid_mono]`, `os88ui_krect`, `os88ui_armw`). Its
primitives are the `ct_cw_*` trampolines, which assume DS is already the
kernel's. A cell that switches DS (`OSAPI_SLOT`) gives the body the kernel's
data and loses the caller's. The kernel already has the answer, and it is used
in two places:

- an **X cell** (`OSAPI_RXCELL`, SPEC.md 20.3) puts the caller's DS in ES;
- **staging**: `os88ui_kbtn` already draws a button from a record that it
  builds in kernel scratch (`os88ui_krec`, `os88ui_krlbl`, `os88ui_krflg`),
  and the Disk window's bar is one block, `os88ui_ksb` (7 words).

So a door copies the few bytes a draw needs from `ES:` into that scratch and
calls the existing body. **The bodies do not change**, so the Disk window and
the dialogs cannot regress. The alternative is a third arm of the library
where every caller-data operand takes an `es:` prefix. That costs about one
byte per operand in the kernel and edits bodies the kernel's own dialogs
depend on. Staging is preferred.

Four more things have to be handled. None of them is large:

1. **The pointer.** The kernel arm's text call is `cw_font_run` (DS:SI). The
   package arm's is `OSAPI_FONT_RUN`, whose X cell names `font_run_x`, which
   calls `fnt_unlazy` first (`kernel/font.inc:1125`). A door entered from a
   package must make that promised hide too, or the first button drawn under
   the pointer leaves the arrow behind. That is one call at the door.
2. **Calls back into the package.** `OS88UI_OWN` (`call si` to a package
   painter), the record's place proc and the alert's completion are near
   procs in the package. The kernel can reach them only through the package
   header's dispatcher, as it does for `W_PAINT`. A leaves all three out: it
   does not take `BOWN`, and the gesture stays in the package.
3. **Per-package state.** `os88ui_btlist`, the alert block, the drop-down
   records and `os88ui_bk` are **one per package**, and two packages can each
   have an alert up at once, so the kernel cannot hold them. `os88ui_armw` and
   the thumb drag's `os88ui_sbd_*` follow the one mouse, so a single kernel
   copy of those is correct, as the kernel's own comment argues. C has to put
   the per-package state in a block the caller owns. A never touches it.
4. **The written decision.** The header of `os88ui.inc` says *"IT IS NOT AN API
   SLOT, deliberately... the cell is not the expensive part of a slot, the
   contract is"* (SPEC.md 20.5.1). A and C reverse that, and the cost is
   specific: **the record layouts (`OS88UI_BT_*`, the 7-word bar block) become
   ABI.** `tools/abi.lock.json` fingerprints `apps/os88api.inc` and
   `drivers/os88drv.inc`, not `os88ui.inc`, so those equates move into
   `os88api.inc` (equates emit nothing) and changing them becomes a `PKG_FMT`
   bump. Today it is a rebuild. **SPEC.md 20.5.1 is rewritten before any
   code.** What the reversal buys is the file's own argument, made stronger:
   a fix to the button reaches packages that were **not rebuilt**.

## 3. Option A: reach the kernel's own copy

### 3.1 The design

- **One rare X cell, `OSAPI_UI`** (6 B), whose target is a cold dispatcher. AL
  is already an argument to `os88ui_btn`, so the function number travels as
  **an inline byte after the far call**. That is the RCELL idea (`call
  api_rx` / `dw target`) applied one level down: the door reads the byte
  through the return address and steps over it. It adds about 10 bytes of
  door and **+1 byte per call site** in packages, which costs nothing.
  Another option is a register freed per function. Measure both at build
  time.
- **`UI_BTN`**: ES:BX = the package's record, AL = index + 1, the gfx lock
  held. It copies the top half of `os88ui_btn` with `es:`: index guard,
  flags, `BT_DOWN`, latch. It copies the rect into `os88ui_krect`, copies the
  label into a new ~24-byte `.bss` buffer (truncated at 23 characters; a
  contract the SDK must state), and calls `os88ui_kbtn` with `OS88UI_DOWN`
  already resolved. ESTIMATE about 90 B.
- **`UI_SB*`**: `sbar`, `sbhit`, `sbmove`, `sbthdraw`, `sbthumb`. Each copies
  the 7-word block from ES:BX into `os88ui_ksb`, calls the body and copies it
  back (`sbmove` moves the position). ESTIMATE about 40 B shared and 2 B a row.
- **A package opts in** with one define, for example `OS88UI_KHOST`. The
  `os88ui_btn` and `os88ui_sb*` labels then become one-instruction local
  thunks (`call OSAPI_UI` / `db fn` / `ret`, 6-7 B), so **no package call site
  changes**. The define only builds for packages whose button is the plain
  variant. `BIMG` and `BOWN` are refused, because the kernel draws neither.

Total: **~170-200 bytes of `.cold` and ~32 of `.bss` on each kernel**
(ESTIMATE, priced against `os88ui_kbtn`'s 49 measured bytes, which does a
third of the button's staging). Build it before quoting a smaller number.

### 3.2 What it reaches, and what it does not

**It reaches 33 images and 12,182 bytes of them** (MEASURED from each image's
own routine sizes, less 6 bytes of thunk per entry used). Seven packages save
710-718 B each: Word, Syscheck, Scribe, Redline, TexPad, Note Pad and the
Browser, which have both a button and a bar. TaskMgr, MIDIRack and Frotz save
468. About twenty more, drivers included (ETHER, NET, SAVER, THMPAL, RAMPAGE,
HTTPPAGE), save 242-264, which is the plain button alone. The same bytes come
off **RAM for every open instance**, which the 128 KB machine notices.

Estimated disk saving per 360 KB disk, at each package's own packing ratio:
system disk ~2.7 KB, `apps360` ~4.0 KB, `office360` ~1.8 KB, `util360` ~1.6
KB, `network360` ~1.1 KB, `games360` ~0.5 KB, `media360` ~0.4 KB.

**It does not reach:**

- the **gesture** (`btninit`, `btnclick`, `btndrag`, `btnup`, `bfind`,
  `bfrec`, `btnpress`): 4.6 KB, but the kernel never hosted it. It walks its
  own rects (`fdlg_bhit`, `fm_bhit`);
- the **small routines**: `bhit` (23), `arm`/`armed` (4), `fire` (10). A far
  call site is 5 bytes against a near one's 3. Below ~30 bytes, a routine
  called from several sites gets bigger through a door. **They stay local**,
  and the rule is general: route a body through the door only when it is
  larger than its thunk plus 2 bytes times its call sites;
- `BIMG`/`BOWN` buttons (MIDIRack, Pixel, WireFleet: 636-742 B each), the
  glyph (a module, not resident), the About card, alerts, drop-downs and
  menus. **None of those is in the kernel.** Adding them is C, a routine at a
  time;
- the **thumb drag on kern_small**. `sbgrab`, `sbtrack` and `sbpos` are not
  in that build. A package with `OS88UI_SBDRAG` keeps its drag half and calls
  `sbthdraw` through the door, which kern_small does host.

### 3.3 Speed

A rare cell costs ~18 µs more than a hot one (SPEC.md 20.3). Staging copies 8
bytes of rect and a short label. ESTIMATE ~60-100 µs per button draw. A button
is at least a frame, a fill and a run, which is three primitives at a 756 µs
floor (PERFORMANCE.md), so ≥ 2.3 ms. **~2-4%, on events a person generates.**
Hit tests stay local and lose nothing. Measure it on MartyPC before calling it
done (`tests/radio.py`'s method: record the calls, then time one draw).

### 3.4 The kern_small question

Both kernels have to offer the cell. One SDK serves every build, and a
shipped package runs on kern_small. If kern_small refused the cell, packages
would have to keep their own copies and A would save nothing. So A spends
~200 bytes on kern_small, and SPEC.md 39.27.4 says *"nothing may be spent
there"*. The case for it is RAM. The 200 bytes are resident with no package
open, but **one** open package with a plain button saves 242 of heap, and
Note Pad saves 710. A typical 128 KB session comes out ahead. It is still the
owner's decision, and it is listed in section 7.

## 4. Option B: a one-per-disk library file

### 4.1 Feasible? Yes, and it can be byte-exact by construction

"The package ends up with the same thing it would have had today" means a
**load-time link** whose output is checked against today's image:

1. **Build the package exactly as today.** The packager (`os88pkg.py`) finds
   the library's byte range in the image, records which variants it holds and
   in what order, and **zero-fills the range** before LZ4. The zeros pack to
   almost nothing, so the hole costs only its selection list on disk:
   ESTIMATE 2 B offset + 2 B count + 3 B per variant (an id and an 8-bit
   check).
2. **The disk's library file** (for example `\UI.LIB`) holds each variant
   **once**, assembled at origin 0, with a fixup list. `os88uicost.py`'s pad
   test finds **base-relative words**: 30 of the 152 variants contain them,
   236 words in all. It also finds intra-library
   `rel16` calls, which change between packages that took different subsets.
   `os88ui_btndrag`'s 11 apparent variants and `os88ui_abtn1`'s 9 are all
   **one** variant each once those calls are relocated. The packager emits
   both kinds.
3. **At launch the loader** opens the library, lays the selected variants
   into the hole in the recorded order, applies the base fixups and resolves
   the `rel16` fixups against the layout it just built. Because the package
   was assembled with the same layout, **the result is byte-identical to
   nasm's image**. The packager can prove that at build time by running the
   loader's algorithm in Python and `cmp`-ing the result. That gate is what
   makes B safe to ship at all.

### 4.2 What it saves: disk only, and less than the raw bytes suggest

The MEASURED library bytes in packages on each disk, against the union of the
variants they use (`os88uicost.py`'s disk table):

| disk | packages | sum | union | duplicate |
|---|---|---|---|---|
| system (360) | 12 | 10,112 | 4,392 | 5,720 |
| `apps360` | 23 | 19,031 | 5,983 | 13,048 |
| `office360` | 9 | 14,850 | 7,183 | 7,667 |
| `util360` | 3 | 5,769 | 3,328 | 2,441 |
| `games360` | 11 | 5,224 | 2,887 | 2,337 |
| `network360` | 4 | 3,996 | 2,844 | 1,152 |
| `media360`, `emu360` | 1 each | | | 0 |
| `apps` (1.44 MB) | 34 | 30,239 | 7,754 | 22,485 |

In disk bytes (ESTIMATE): the packages' share packs at ~85%. The library packs
at ~60%, and on top of that come its fixup table (~1 KB for the whole tree's
library, less for a per-disk one) and the selection lists (~50 B a package).
That leaves **~8 KB net on `apps360`** (about eight of 354 clusters, ~2%),
~5.5 KB on `office360`, ~3.5 KB on the system disk, ~1.4 KB on `util360`, ~1 KB
on `games360` and ~0.4 KB on `network360`. On `media360` it is a **loss of
~1 KB**: one includer pays for the library and its cluster.

### 4.3 The loader

- **In the kernel** (`kernel/loader.inc`): find `UI.LIB` beside the package or
  at the root of its volume, read the index, read the variants, apply the
  fixups, check each variant's 8-bit sum, and refuse the launch with a
  sentence when something is missing. The pieces already exist (by-name read
  through `dskw_*`, LZ via `lz.inc`), so the new code is the walk and the
  fixup loop. ESTIMATE **~350-450 resident bytes, on both kernels**. That is
  twice A, and it saves no RAM.
- **In each package**, as `os88parts.inc` does for parts: zero kernel bytes,
  but ESTIMATE **~200 B per package**. On `apps360` that is 23 × 200 = 4.6 KB
  against the ~8 KB it saves, so about half of the saving goes back.

**The launch cost.** One more file means one more directory lookup and at
least one more read. The house unit is the `int 13h` call (~400 ms), not the
sector, so expect **+0.4-0.8 s per launch on an XT floppy** unless the
sectors are still in the cache. That is a large fraction of a package launch
on the target machine.

### 4.4 Why it is not recommended

- **The sidecar comes back.** O88-MULTISEG-PLAN's first real consumer was the
  C64's ROM. It stopped being a sidecar file because *"a copy that took the
  program and left it behind was a machine that could not start"*. B would
  make that true of **every UI package**: copy `CALC.O88` alone to another
  disk and it no longer launches. The Disk window's copy, The Wire's Add to
  Disk (SPEC.md 92) and the everything set would all need to carry or
  **merge** libraries, and merging is a guest-side linker job.
- **Version skew.** A variant is the bytes of one build of one
  configuration. A package from a newer build on an older disk finds its
  variant missing or different. The 8-bit check turns that into a refusal
  instead of a crash, but it is still a program that does not start.
  Searching the system disk as a fallback helps only within one release.
- **It saves no RAM**, by design. RAM was half of the owner's complaint.
- **A gets ~45% of B's disk saving with none of these problems**, and saves
  RAM too: ~4.0 against ~8 KB on `apps360`, ~2.7 against ~3.5 KB on the
  system disk.

## 5. Option C: the whole library in the kernel

### 5.1 Resident: it does not fit

The union is **6,748 B** with each routine at its largest variant, and
**9,792 B** with every variant. Making the configuration runtime flags
instead of `%ifdef`s would bring it closer to the first figure. Against that,
on this tree:

- kern_big: `KERN_SIZE 98,304 of KERN_BUDGET 100,864 -> 2,560 spare`;
- `.cold` in ROM: `37,767 of the 40,944 the 40KB window holds -> 3,177 for
  the tail and spare`, so a resident C also breaks `make rom-big`;
- kern_small: 3,072 spare and the diet rule.

So C as resident code needs a budget rework with the owner. That is a decision
to take before any design, never a build fix. It is also a rewrite: all
per-package state (section 2, item 3) moves into a block the caller owns,
callbacks go through the package dispatcher, and every caller-data operand in
roughly 6.7 KB of bodies has to be made segment-aware. That is the third arm
section 2 recommends against, applied to everything.

### 5.2 As an on-demand module: it shares the bytes, but costs more RAM in practice

`CTRL.DRV`'s shape: the bodies live in `UI.DRV` on the system disk and stay
resident only while a client is open. Each entry costs 4 B of `.bss` (SPEC.md
2.8.1), and a client refcount for the drop rule (`tests/unit/t_moddrop.py`
requires one) costs ~20 B. ESTIMATE **~60 B + 4 B per entry**. But:

- **The claim is rounded up to whole KB** (`mem_bytes_kb_x`). A 7-10 KB module
  costs more than today's 0.2-4.3 KB per package **until about four UI
  packages are open at once**. A typical 128 KB session has one or two, so RAM
  gets worse there. Splitting it per capability (button, bar, alert,
  drop-down, About) rounds each piece up to its own KB.
- **`mod_need` reads `[dsk_bootvol]` and only that**
  (docs/plans/completed/O88-MULTISEG-PLAN.md §1). On a one-drive kern_big
  machine running from the apps floppy, the first UI package cannot load its
  library. kern_small is spared only because its system disk carries every
  package (SPEC.md 24.5.6).

### 5.3 One door, or one cell per element

| | resident | per call site in a package | ABI |
|---|---|---|---|
| a rare cell per element | **6 B** each, so ~150 B for ~25 entries | 5 B | 25 published slots, each with a contract |
| **one door with a function number** | **~25-30 B** (cell, dispatcher, and the inline-byte step) **+ 2 B per function** | 6 B (the inline byte) | **one** slot. Functions are added at the end of the dispatch table, with no table renumber and no `PKG_FMT` bump |
| one cell that returns a far pointer to a jump table (`OSAPI_FONT_GLYPHS`'s shape) | the table, plus a DS/ES door per entry anyway | 5 B through memory | the pointer is cheap, but every entry still needs a door, because the bodies need DS sorted out (section 2) |

One door costs less than one cell per element once there are more than ~6
functions, and the ABI argument decides it regardless. Every new public slot
is a published contract. One slot with a sub-table publishes one contract and
lets the library grow behind it. **A uses this shape from day one**, so a later
C-style addition is one row in the table, not a new slot.

## 6. Recommendation

1. **Do A**, in two waves, with the size measured at each:
   - **wave 1**: `OSAPI_UI` with one function, `UI_BTN`, and `OS88UI_KHOST`
     opted into by the plain-button packages. That covers 33 images at ~250 B
     each.
   - **wave 2**: the bar (`UI_SBAR`, `UI_SBHIT`, `UI_SBMOVE`, `UI_SBTHDRAW`,
     `UI_SBTHUMB`), which gives the seven text and document packages their
     further ~460 B.
   - SPEC.md 20.5.1 is rewritten first (section 2, item 4). The record
     equates move into `os88api.inc` under the ABI lock.
     `python3 tools/abilock.py --update "..."` runs **without** a `PKG_FMT`
     bump, because a cell added at the end does not break any existing
     package.
2. **Then decide body by body whether to add one to the door**, using one
   rule: *resident bytes in, against image bytes out multiplied by how many
   packages carry them.* The candidate that clears it is
   **`os88ui_about_d`**: 175 B in **39 images**, 6,736 B in all, self-contained,
   arguments by register, no package state. It is a cold path (an About pick),
   so the resident ~180 B is the whole price. That is a byte decision for the
   owner (section 7), not a rung decision. The alert (`ask`, `arect`,
   `apaint`, `abtn1` and their state) is **not** a candidate, because its
   state is per package (section 2, item 3).
3. **Do not do B.** If a disk is the pressure, `apps360`'s curation (SPEC.md
   24.6.1) is the lever the project already uses. B's ~2% of that disk does
   not justify a sidecar on every program.
4. **Do not do C as resident code.** As a module it saves RAM only on a
   machine already running four UI packages, which is not the machine this
   problem is about.

## 7. Open decisions for the owner

1. **Reverse SPEC.md 20.5.1's "not an API slot"?** A and C both depend on it.
   The cost is that the record layouts become ABI.
2. **Spend ~200 B on kern_small for A?** SPEC.md 39.27.4 refuses it by
   default. Section 3.4 is the case for an exception: RAM-positive with one
   package open.
3. **Truncate a door button's caption** at 23 characters, or stage longer
   ones at a larger `.bss` cost? No shipped caption measured is near 23.
4. **The About card in the kernel (section 6, item 2)?** About 180 resident
   bytes for ~6.6 KB of images.

## 8. How this was measured

- `python3 tools/os88uicost.py [--json out] [--disks img ...]`: the routine
  and disk tables. It uses `tools/incsize.py`'s attribution for every
  includer, assembles a second time with two bytes of padding in front of the
  include to find base-relative words, and walks every 360 KB image and the
  1.44 MB apps disk with subdirectories. The nine sources it cannot assemble
  are named in its output.
- Kernel rows: `tools/os88sym.py`'s map. Each `os88ui_*` symbol's size is the
  distance to the next symbol in its section, on `build/` (kern_big) and on
  `build/smallk` (kern_small, `make small`, `OS88_BUILD=build/smallk`).
- Compression: `tools/os88lz.py`'s `lz4_compress` and `lzb_compress` over the
  extracted bytes.
- **What is ESTIMATED**, and how it would be measured: every door and loader
  size (build them), the per-draw time (MartyPC, `tests/radio.py`'s method),
  and every packed disk figure outside section 1 (rebuild the floppies and
  read the cluster counts).
