# The module split, `kern_small` only

**Research document, not a contract.** SPEC.md §2.8 is the binding contract for
what an on-demand module *is*; docs/ONDEMAND-PLAN.md is why the three that ship
were chosen; this is the study of moving more of `.cold` behind that mechanism
**on `kern_small` alone**, with `kern_big` keeping every byte resident. Nothing
here has been built. Every figure was measured on this tree at build 377 by the
method in §8.

The ask, in the requester's words:

> Investigate what it would take to do the module split, for kern_small ONLY.
> Big needs those to stay fast, and to keep loading via the cyl run kernel read
> on boot.

---

## 0. The verdict, up front

**Two of the four candidates are possible and two are refused by the mechanism
itself. The net is ~4.6 KB, not the ~13.0 KB docs/KERN-SMALL-CUT-PLAN.md §6
claimed** — that figure was the four files' `.cold` added up, and this
investigation is what checked it.

| candidate | `.cold` | entries | verdict |
|---|---:|---:|---|
| `filecp.inc` — Cut/Copy/Paste | 2,141 | **5** | **possible**, and clean |
| `fdlg.inc` — Standard File dialog | 3,152 | **9** | **possible**, after two prerequisites |
| `assoc.inc` — file associations | 2,003 | 9 | **refused — a cycle**, §2.1 |
| `diskw.inc` — the FAT write path | 4,565 | **33** | **refused — it is the file I/O layer**, §3.4 |

Five findings:

1. **`kern_big` is untouched by construction, and its boot read gets no
   slower.** A module is cut out of `kernel.bin` by `tools/os88mod.py` and
   `MODC_START` is exactly where the image ends, so modules already ride
   *outside* the contiguous cylinder-run read. Gating the split on
   `%ifdef KERN_SMALL` leaves big's `.cold`, its sector count and its run
   identical — and makes `kern_small`'s boot read **shorter**, which is a
   small win in the other direction.

2. **The module loader's own dependency cone is half of `.cold` and can never
   be modular.** `mod_need`'s transitive callees are **155 symbols across 7
   files — 16,880 bytes, 48.9% of `.cold`**. Add `files.inc` (the Disk window,
   always live, 55 entry points) and 71% of `.cold` is structurally excluded
   before any judgement about frequency. §2.

3. **`assoc.inc` is *inside* that cone**, which settles it on mechanism rather
   than on the disk-swap test:
   `mod_need → drv_mounted → dsk_chdir_q_x → dsk_chdir_x → disk_mount_x →
   asc_lookup_x`. Loading any module can trigger a mount, and a mount calls
   associations. §2.1.

4. **`diskw.inc` is not "the write path", it is the by-name file I/O layer**,
   and three loaders plus two shipped modules depend on it: `mod.inc` calls
   `dskw_read_x` *to load a module*, `driver.inc` calls it to load a driver,
   `loader.inc` calls `dskw_stat_x` to load a package, and CTRL.DRV and
   CLONE.DRV far-call `dwf_dskw_*` from inside their own images. 33 entry
   points against `MOD_NENT`'s 8. §3.4.

5. **`fdlg.inc`'s 4,292 bytes include ~1,140 that are not fdlg's.**
   `apps/os88ui.inc` — the shared standard controls — is `%include`d inside
   fdlg's `.cold` extent, and its kernel copy is used by five other files
   (`os88ui_btn` in five, `os88ui_arm`/`_armed`/`_fire`/`_krect` in three
   each). It has to be lifted out first, **and it stays resident whether fdlg
   is moved or deleted** — so KERN-SMALL-CUT-PLAN §4's C2 is overstated by the
   same 1,140. §6.

---

## 1. What a module costs, measured off the one that ships

`diskw.inc`'s `section .modf` block (line 3718) is the worked example, and the
shape is worth stating because every cost below comes off it:

```nasm
section .modf                   ; the on-demand image (SPEC.md 2.8)
modf_hdr:
    dw 0x384F                   ; MOD_H_MAGIC
    db MOD_VER
    db MOD_FMT                  ; which MOD_* row this is
    dw BUILD_NUM                ; the commit...
    dw MOD_STAMP                ; ...and this build's LAYOUT
    dw modf_end                 ; MOD_H_IMG
    dw FM_NENT
    dw modf_e_probe             ; the FAR entries, never the bodies
    ...
    times MOD_NENT - FM_NENT dw 0

modf_e_probe:   call dskw_fmt_probe_x
            retf
```

**A module is a section, not a file.** `diskw.inc` already contributes to
both `.cold` and `.modf` — the formatter is split out of that file and the
rest of it stays resident. So the unit of the split is a *named subset of
routines*, which is what makes a `%ifdef KERN_SMALL` version of it possible at
all.

The cost, per module:

| | where | bytes |
|---|---|---|
| image header | in the module | `12 + MOD_NENT*2` |
| one far entry per exported body (`call body_x` / `retf`) | in the module | 4 each |
| the shared `..._load` stub (`push ax` / `mov al, MOD_x` / `call mod_need` / `pop ax` / `ret`) | resident `.cold` | ~10 |
| one resident stub per entry — load, `call far [FP + K*4]`, and **its own refusal** | resident `.cold` | ~14 each |
| one far entry into `.cold` per outbound symbol with no existing `.text` thunk | resident `.cold` | 4 each |
| `mod_tab` row + the 8.3 file name | resident `.text` | ~16 |
| `mod_fp` | resident `.bss` | `MOD_MAX * MOD_NENT * 4` |

**Outbound is cheap and inbound is what binds.** `COLD_SEG` is an
assembly-time constant, so module code reaches resident cold code with a plain
`call COLD_SEG:xxxf_foo` — the convention already exists at scale, **80
`xxxf_` far entries** in the tree today (`drvf_` 16, `dwf_` 12, `mmf_` 11,
`cpf_` 10). Calls out to `.text` need nothing new at all: the module is cold
code by every other property, so the 102 `cw_*` shims already serve it.

**`MOD_NENT` is 8 and that is the ceiling on entry points.** It is not a free
constant: `mod_fpr` turns a row pointer into `&mod_fp[id]` with three unrolled
`shl di,1`, and `kernel/mod.inc` asserts `MODFP_STRIDE == MODR_SIZE * 8`.
Raising it to 16 is a four-line change — one more shift, the assertion's `8` to
`16` — and doubles `mod_fp`.

---

## 2. The ceiling: `mod_need`'s own cone

Walking every `.cold` call reachable from `mod_need`, `mod_check`,
`mod_free_row`, `mod_init_x` and `mod_drop`:

| file | symbols in the cone | that file's whole `.cold` |
|---|---:|---:|
| `disk.inc` | 61 | 5,746 |
| `memory.inc` | 26 | 2,388 |
| `assoc.inc` | 24 | 2,003 |
| `diskw.inc` | 20 | 4,565 |
| `driver.inc` | 11 | 1,794 |
| `mod.inc` | 8 | 366 |
| `kernel.asm` | 5 | 18 |
| | **155** | **16,880 — 48.9% of `.cold`** |

None of it can be a module: the loader would have to load itself. Add
`files.inc` (7,653, and 55 entry points — it is the Disk window, live for the
whole session) and **71% of `.cold` is excluded on structure alone**.

What is left, ranked by whether it fits `MOD_NENT` = 8 today:

| `.cold` | file | entries | out → `.cold` | verdict |
|---:|---|---:|---:|---|
| 3,173 | `fdlg.inc` | 11 names / **9 bodies** | 21 | needs `MOD_NENT` 16 |
| 2,141 | `filecp.inc` | **5** | 33 | **fits today** |
| 1,111 | `apps.inc` | 11 | 6 | the built-in kinds — multi-instance, §7.3 |
| 995 | `desk.inc` | 8 | 7 | the desktop — drawn constantly, refuse |
| 781 | `loader.inc` | 5 | 12 | the package loader — §7.3 |

### 2.1 Why `assoc.inc` is a cycle and not a judgement call

docs/ONDEMAND-PLAN.md §1's test would already refuse it: `asc_lookup_x` and
`asc_take_x` are called **once per directory entry** inside `disk_mount_x`'s
icon-harvest loop, so a module load would sit in the mount's inner loop.

But it does not get as far as the test. The path is:

```
mod_need -> drv_mounted -> dsk_chdir_q_x -> dsk_chdir_x -> disk_mount_x -> asc_lookup_x
```

`mod_need` banks to the system volume, and reaching it can mount it. **Loading
the association module would call the association module.** Refused.

---

## 3. The four candidates

### 3.1 `filecp.inc` — Cut/Copy/Paste. The clean one.

Five entry points, and all of them a user gesture: `fcp_arm`, `fcp_ncopy`,
`fcp_paste`, `fcp_answer` from `files.inc`, and `fcpf_fcp_goto` — **already a
far entry**, called by CLONE.DRV from inside `.modl` and by `kernel.asm`.

Outbound is 33 symbols into other `.cold`, of which 9 already have a resident
`.text` thunk to far-call through and **24 need a new far entry** — 14 in
`disk.inc`, 6 in `diskw.inc`, 2 in `memory.inc`, plus `drv_fs_call`/`drv_fs_has`
and two `kretc_*`. At 4 bytes each that is 96 resident bytes.

The drop point is unambiguous: a copy or paste is one bounded operation with a
progress widget already on it, so `mod_drop` goes where `fpg_` comes down.

### 3.2 `fdlg.inc` — the Standard File dialog. Possible, with two prerequisites.

**Nine distinct bodies**, from eleven names — `fdf_fdlg_open` and `fdlg_open_x`
are the same body reached two ways, as are `fdf_fdlg_paint` and
`fdlg_paint_x`. The set is `open`, `paint`, `onkey`, `onclick`, `ondrag`,
`onup`, `reap`, `grab`, `top`.

**The window callbacks are already solved.** `fdlg_tpl` in `.text` holds
`dw fdlg_s_topen, fdlg_paint, fdlg_onkey, fdlg_onclick` — *thunk* names, not
cold bodies, and the thunk far-calls `fdlg_paint_x`. Turning a thunk into
"`mod_need`, then `call far [FDFP + K*4]`" leaves the template untouched and
`wm_create` none the wiser.

Two prerequisites:

- **Lift `%include "os88ui.inc"` out of `fdlg.inc`** (line 1211) into a
  resident `.cold` position of its own. Mind `kernel.asm`'s ordering trap: the
  `OS88UI_SBDRAG` define must be resolved before the include, and the file
  already carries the account of what happened when it was not.
- **Raise `MOD_NENT` to 16**, per §1.

The lifetime rule is the Control Panel's: the window may only exist while the
module does. `cp_open_x` refuses *before* `wm_create`, and `fdlg` must do the
same, or a repaint arrives with nothing to call.

### 3.3 `assoc.inc` — refused, §2.1.

### 3.4 `diskw.inc` — refused. It is the file I/O layer.

Thirty-three entry points against a ceiling of eight, and the entry list says
why the name misleads:

- `mod.inc` calls **`dskw_read_x`** — this is how a module is read off the
  disk. A module containing it could not be loaded.
- `driver.inc` calls `dskw_read_x` and `dskw_stat_x` to load a `.DRV`.
- `loader.inc` calls `dskw_stat_x` to load a **package**.
- `disk.inc` calls `dskw_flush_x` and `dskw_remount_x`.
- **CTRL.DRV** (`.modc`) far-calls `dwf_dskw_read`, `dwf_dskw_stat`,
  `dwf_dskw_write_sys`; **CLONE.DRV** (`.modl`) far-calls four more.
- `kernel.asm` publishes eleven `dwf_dskw_*` far entries as API slots.

A *subset* — the gesture-driven writes (`delete`, `mkdir`, `rename`, `rmtree`,
`ent_store`, `take_slot`, `append`, `char`) — is conceivable, but `filecp.inc`
calls ten of them, so doing both waves would need module-to-module calls. That
is more mechanism than the remaining bytes are worth; §7.2.

---

## 4. What it would take

Per wave, in dependency order.

**`kernel/mod.inc`**
- `MOD_MAX` 3 → 4 (wave 1) → 5 (wave 2), inside `%ifdef KERN_SMALL`.
- New ids `MOD_FILECP` / `MOD_FDLG`, two `mod_f_*` name strings, two `mod_tab`
  rows — all gated.
- Wave 2 only: `MOD_NENT` 8 → 16, `mod_fpr`'s three shifts → four, and the
  `MODFP_STRIDE != MODR_SIZE * 8` assertion → 16. **All three move together**;
  the file's own header records what happened last time two of them drifted.

**`kernel/kernel.asm`**
- `section .modp` / `.modd` declarations with `start=` / `vstart=0`, the
  `MODx_START` chain, the `MODx_SIZE` end labels, the `MOD_MAX_KB` guards and
  the `.modmap` rows — every one inside `%ifdef KERN_SMALL`, and the chain must
  reconverge so `MODMAP_START` is right on both builds.

**`kernel/filecp.inc`, `kernel/fdlg.inc`**
- The invasive part: each file carries **both shapes**, `%ifdef KERN_SMALL`
  emitting `section .modX` plus header, far entries and resident stubs, `%else`
  emitting today's `section .cold`. The bodies themselves do not change — they
  keep their near `ret`.
- 43 new `xxxf_` far entries into `.cold` (24 for filecp, 19 for fdlg), also
  gated, or `kern_big` pays for them too.

**`kernel/fdlg.inc`** — lift the `os88ui.inc` include out first (§3.2).

**`Makefile`**
- `KMODS` and `KMODARGS` conditional on `KERN_SMALL`. `os88mod.py` needs no
  change — it reads the row count out of the `.modmap` trailer — but it
  **fails loudly** if the `-m` count disagrees, which is the right failure.
- Disk placement is automatic: `DRIVERS += $(KMODS)` and `SMALLDRIVERS`
  filters that list, so a new module reaches the small floppies with no recipe
  edit. **Check the 360KB cluster budget** — two more files in the root.

**`tools/os88ovlchk.py`** — `MODS = ('.modc', '.modf', '.modl')` is a hardcoded
tuple. Adding sections without adding them here leaves the near-call check
blind to them, which is a failure this gate has already had once (its own
comment records `.modl` shipping that way).

**`tests/suite.py`** — a row that builds `kern_small` and asserts the module
count and each image's size against `MOD_MAX_KB`. `make test-full`'s build
matrix is the only thing that builds `kern_small` at all.

---

## 5. The arithmetic

| | `.cold` moved | resident added | net |
|---|---:|---:|---:|
| wave 1 — `filecp.inc` | 2,141 | 192 | **1,949** |
| wave 2 — `fdlg.inc` | 3,152 | 228 | **2,924** |
| `mod_fp` (`MOD_MAX` 3→5, `MOD_NENT` 8→16) | — | 224 | **−224** |
| | **5,293** | **644** | **4,649** |

Resident added, per wave: wave 1 is 10 + 5×14 stubs, 24×4 far entries, 16 of
`.text`; wave 2 is 10 + 9×14, 19×4, 16.

As the rungs fall on this tree:

```
.cold    34,531 - 5,293 + 388  =  29,626  ->  rung 29,696   (was 34,816)
image    .text +32, .bss +224  =  46,382  ->  rung 46,592   (UNCHANGED)
KERN_SIZE                96,256  ->  91,136
heap floor                95.5 KB  ->  90.5 KB
free heap on 128KB        32.5 KB  ->  37.5 KB
```

**Quote the 4,649**, not the 5,120 the rungs happen to give: the image rung
absorbing 256 bytes of `.bss` for free is this change standing in the right
place, not value it created (CLAUDE.md's rung rule).

---

## 6. What this corrects in docs/KERN-SMALL-CUT-PLAN.md

That document's §6 is wrong and this is the correction, made in place there
too:

- **§6's 12,997 was the four files' `.cold` summed**, with no check on entry
  counts, on the loader's own dependency cone, or on what `%include` sits
  inside `fdlg.inc`. The module route yields **4,649**.
- **§4's C2** (delete the Standard File dialog, 4,654) is overstated by the
  ~1,140 bytes of `apps/os88ui.inc`, which five other files need and which
  survives either route. C2 is **3,514**, and the C subtotal 17,840 → 16,700.
- **§8.1's recommended row moves from 61.4 KB to 53.2 KB**, and the argument
  in §6 that the module route lands "within 1,364 bytes" of deleting C1–C4
  does not survive: the honest gap is **8.4 KB**, because `diskw.inc` and
  `assoc.inc` can be deleted and cannot be moved.

**The recommendation therefore changes.** The module split is still worth
doing — 5.0 KB of heap, +15% on a 128KB machine, with both features intact —
but it is no longer a substitute for the deletions, and §8.1's last row is the
only one that reaches 65 KB.

---

## 7. Refusals and risks

### 7.1 The disk-swap cost is real and this does not dodge it

`mod_need` calls `drv_vol_bank` → `drv_mounted`, so the system disk must be
reachable when the feature is asked for. On the calibration machine — one
360KB drive — opening the file dialog to browse a **data** disk means the
system disk is not in the drive, `drv_mounted` fails, and the dialog refuses.
That is docs/ONDEMAND-PLAN.md §1's objection exactly, and it is the reason
this is a product decision and not a build fix. It is not fatal — the refusal
is clean and the toast can say what to do — but *"the file dialog sometimes
will not open"* is the feature being bought.

### 7.2 Do not build module-to-module calls

`filecp.inc` calls ten `diskw.inc` bodies. If a `diskw` write subset ever
became a module too, one module would have to `mod_need` another from inside
its own image. It is mechanically possible — `mod_fp` is `.bss` at
`KERNEL_SEG`, reachable through DS — and it is a lifetime problem nobody
should have: two claims, two drop points, and a compaction between them.
**One level of modules.**

### 7.3 Three that were measured and are not proposed

- **`apps.inc`** (1,111, 11 entries) — the built-in kinds are **multi-instance**
  windows. `mod_drop` is caller-decided and has no refcount, so the second
  Timer closing would free the first one's code. It needs a pin, which is
  ONDEMAND-PLAN §7.1's purgeable design, deliberately not built.
- **`desk.inc`** (995, 8 entries) — the desktop is drawn on every repaint.
- **`loader.inc`** (781, 5 entries) — the package loader, and `memory.inc`
  calls into it during compaction.

### 7.4 What stays resident either way

`.bss` does not move: `fdlg` 121 and `filecp` 144 stay, and so does every
`.text` byte of both files. The saving is `.cold` alone.

---

## 8. How these figures were taken

Per-file `.cold` from `tools/kernsize.py --modules --build build/smallk
-DKERN_SMALL`. Sub-file sizes from nasm's `[map all]`, each symbol sized by the
distance to the next in its section — the summed spans equal the section
lengths exactly, and nasm-local labels are attributed to their parent.

The call graph is a source scan of `kernel/*.inc` and `kernel/*.asm`: section
state tracked per line, labels owned by the section they are defined in, and
`call`/`jmp`/`dw` targets resolved against that. **One correction is worth
recording**: the first pass missed `call far COLD_SEG:label`, matching the
segment rather than the label, which understated every inbound count — fdlg
read 2 entries instead of 11 and `diskw` 21 instead of 33. A cross-segment
call graph that cannot see segment-prefixed calls is measuring the wrong thing,
and the numbers it gives are plausible.

The 1,140 bytes attributed to `apps/os88ui.inc` are the `.cold` the map
accounts for and the kernel source does not define — `fdlg.inc`'s
`%include` is the only one of its kind in a `.cold` block, which
`tools/os88ovlchk.py`'s own `EXTRA` table independently confirms.

**Nothing here has been built.** Every figure is what the code costs today.
