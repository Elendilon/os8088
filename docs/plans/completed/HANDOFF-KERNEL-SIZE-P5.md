# Kernel size pass 4: the record, and what is left for a fifth

**PASS 4 HAS LANDED.** Ten batches and a fix on `kernel-size-p4`, cut from
`elendilon` at `6519baaa`. The brief was *"reduce kernel size by 2KB or more"*,
with the owner's permission to look at the kernel as a WHOLE, to change the
ABI (every package in the tree is rebuilt), and to spawn agents on targets
worth the effort; hot drawing paths were not to lose speed.

The file name is `-P5` because `HANDOFF-KERNEL-SIZE-P4.md` is **pass 3's**
record (each pass's record was named for the pass it handed to). This is pass
4. Its companions, and this file repeats none of them:

* **`docs/plans/completed/HANDOFF-KERNEL-SIZE.md`** — pass 1's handoff, still
  the authority on **method**.
* **`docs/plans/completed/HANDOFF-KERNEL-SIZE-P4.md`** — pass 3's record. Its §2
  (what was left) and §3 (the refusals that are proofs) were this pass's
  starting brief.
* **`docs/KERNEL-MEMORY.md`** — where the budgets stand. Blessed at the close
  of this pass.

---

## 0. THE OUTCOME

**Both kernels cleared the 2KB target**, measured by `tools/kernsize.py` as
the sum of the RESIDENT sections (`.text` + `.bss` + `.cold` + `.lowbss` +
`.vgabuf`) against the base tree — never against a rung count:

| | kern_big base | kern_big close | Δ | kern_small base | kern_small close | Δ |
|---|---:|---:|---:|---:|---:|---:|
| `.text` | 50,358 | 49,194 | −1,164 | 37,423 | 36,397 | −1,026 |
| `.bss` | 6,114 | 5,552 | −562 | 4,189 | 3,539 | −650 |
| `.cold` | 41,020 | 40,337 | −683 | 26,394 | 26,066 | −328 |
| `.lowbss` | 6,366 | 6,366 | 0 | 3,636 | 3,636 | 0 |
| `.vgabuf` | 848 | 336 | −512 | 0 | 0 | 0 |
| **resident** | **104,706** | **101,785** | **−2,921** | **71,642** | **69,638** | **−2,004** |
| `.text`+`.bss` (the binding segment) | 56,472 | 54,746 | **−1,726** | 41,612 | 39,936 | −1,676 |
| `KERN_SIZE` | 111,104 | **107,520** | −3,584 | 74,240 | **71,680** | −2,560 |

`KERN_SIZE` moved further than the byte sum because rungs round separately —
the banner in CLAUDE.md is why that figure is quoted beside the byte sum and
never instead of it. On kern_big the segment (`KERN_CODE_MAX`) goes 9,064 →
10,790 left.

**What a VGA machine and a mono machine each get.** `.vgabuf` is the one rung
a mono machine never reserves (SPEC.md 39.22), so batch 8's −512 is a VGA
machine's alone. A Hercules or CGA kern_big machine gets the other −2,409.

## 1. WHERE THE BYTES CAME FROM

| batch | what | kern_big | kern_small |
|---|---|---:|---:|
| 1 | `.bss` sized to its use: the BPB bank 64 → 32 a volume, `inst_tab` from `INST_MAX`, a one-plane cursor save-under with no VGA | −288 | −424 |
| 2 | `font_run`'s glyph table and edge bytes are a union with the icon renderer's scratch cell | −196 | −180 |
| 3 | four dead `disk.inc` routines, dead `os88ui` button tracking in the kernel's copy, four dead far shims, a case fold in `fm_onkey_x`, shared failure tails in `drv_load_row` | −274 | −100 |
| 4 | **the API table's rare cells shrink to six bytes** (an ABI flag day, below) | −402 | −402 |
| 5 | two more dead shims; nine kern_big-only shims gated out of kern_small | −8 | −48 |
| 6 | a shared push prologue (`kentc_di`/`kentc_bp`) for `.cold` routines | −135 | −42 |
| 7 | the BPB bank and stage shrink again, to the 18 bytes rules 3–16 read | −125 | −69 |
| 8 | **the VGA decode table shares the mono pair tables** (a measured speed trade, below) | −505 | 0 |
| 9 | **the window record absorbs its eleven side tables**; drag and grow share one loop; the built-in dock icons are row runs | −600 | −533 |
| 10 | cold-side trampolines for multi-site `.cold` → `.text` far calls; kernel windows call their `.cold` callbacks directly | −388 | −206 |
| | **total** | **−2,921** | **−2,004** |

### 1.1 The two ideas that were new

**The API table has two cell sizes (batch 4, SPEC.md 20.3).** Every cell was
8 bytes because the plain SLOT is — `push ds / push cs / pop ds / call / pop
ds / retf`, the fastest segment switch there is. That is right for the 48
cells some package calls per frame, per draw or per event, and they are
byte-identical. The other 106 became `push bp / call api_r<kind> / dw
target`: the rare body pops its own return address, which IS the address of
the target word. ~18 µs a call on a 4.77 MHz 8088, estimated rather than
measured. Eight withdrawn cells were deleted rather than kept as `stc`/`ret`
stubs, which retires SPEC.md 20.3.1's free list: with a renumber-anything
ABI, a withdrawn cell's SDK name is deleted and the source that still names
it fails to assemble.

**The window record absorbs its side tables (batch 9).** Eleven per-slot
tables sat beside `wm_wins` on the argument that a field in the record costs
every reader the stride. On an 8088 that is false: there is no cache, and a
record field is the same `[bx+disp8]` as any other. What the side tables
DID cost was a `wm_ptr2idx` — a `div` — and a scale on every access, and
eight `*_slot` helpers existed only for that. So this is the one batch that
made hot paths faster while saving bytes. `WIN_SIZE` 72 / 65.

### 1.2 The one speed trade, and the owner took it

Batch 8 puts `vga_p4tab` (512 bytes) over `gfx_pairtab0`/`gfx_pairtab1` in
`.lowbss`: the two serve different adapters, each builder clears the other's
built flag, and both flags are tested at every `gfx_blit4` under the gfx
lock. The decoder then reaches the table through `SS`, which is an `ss:` on
its four table loads per eight pixels. **Measured** with `tests/blitplane.py`
on MartyPC `os8088_xt_vga`: even phase 5,405,546 → 5,543,959 cycles
(**+2.6%**), odd 7,341,227 → 7,481,582 (**+1.9%**), pixels identical, the
decoder still 6.2× / 4.6× the span writer. The owner's reading, and the
right one: 2–3% off an optimisation that is itself 5–6×, touching nothing
but `gfx_blit4`'s planar row decoder. SPEC.md 39.22.1.

### 1.3 A defect this pass introduced and fixed

**Batch 4 renumbered the table and three on-demand modules did not follow.**
`HIBER.DRV`, the cloner and its compressor carried their cell offsets as
literal equates, and six of ten moved: `hb_ok_x` far-called the middle of
another cell, the `hibernate` soak row failed (the window never appeared),
and after batch 10 moved the code underneath it the same press CRASHED.
`t_api_abi.py` compares the SDK with the table and could not see a module's
private constant. Fixed in `7e50a94f`: every one is an `apic_*` label on the
cell itself, so the assembler derives the address and a renumber cannot
strand it. **Whoever renumbers the table again: grep `kernel/` for
`KERNEL_SEG:` targets that are not labels** — there are none now, and a gate
that says so would be cheap.

### 1.4 Batch 10's commit message lost a fragment

The shell ate a backquoted `call COLD_SEG:wm_cbd`, so `0fc1c465`'s message
reads *"wm_pkgcall's kernel arm is (call bp / retf)"*. It is **`call
COLD_SEG:wm_cbd`**, where `wm_cbd` in `.cold` is `call bp / retf` — the old
thunk's four transfers in the other order, so the cost and the stack depth at
the callback are unchanged.

## 2. WHAT IS LEFT, costed

| candidate | kern_big | kern_small | why not taken |
|---|---:|---:|---|
| `rect_get`/`rect_put` for 37 four-word load/store sites | −298 | −245 | ~30 µs a rect on repaint and raise paths; the 12 cold sites alone are ~−70 |
| boot-only code into the blob (`kmain`'s pre-mount half, `vid_detect`, `vid_init`, `hb_probe_x`; a `BLOBCALL` macro and three `os88ovlchk` rules) | −270 | −208 | built and green, but leaves kern_small's blob 50 bytes and breaks kern_small's `BOOTMARK=1` build by 157. Prototype and reachability tool in the pass's scratch findings |
| the extended desktop's WM code as a kern_big on-demand module | ~−850 | 0 | `MOD_NENT` = 7 entry points; a design decision |
| inline cells whose routine fits in 8 bytes (`get_ticks`, `set_color`, …) | −55 | −55 | FASTER; needs an INLINE shape in `t_api_abi.py` |
| `ui_tm_errs` duplicates `fm_stattab` | −125 | | changes the Task Manager's error wording — the owner's call |
| eleven near-identical block pairs (`dskw_mkbody`/`rmbody`/`dbody`, `dskw_wdata`/`rdata`, …) | ~−280 | | eleven separate edits, each small |
| `mov word [wm_clip_n], 0` → `call wm_clip_clear` at ~18 non-hot sites | ~−54 | | |
| `inst_icobuf` onto `ico_ibuf` | −64 | | REFUSED: it is filled on a dying package's WORKER while task 0 may be staging |

**Two enablers, not savings.** Reordering `.lowbss` so the worker stack pool
(`sch_stacks`, 2,816 bytes, unused before the first spawn) follows
`dsk_secbuf` would raise the `.ovlw` ceiling by ~2.7KB at no resident cost —
which is what would let boot-only bodies move into `.ovlw` again, kern_big's
`.ovlw` being at 5,110 of 5,120. And the `jcc` residual pass 3 costed is
unchanged in kind.

## 3. THE REFUSALS

* **String compression**: resident strings are 2,118 bytes; every consumer
  hands `DS:SI` straight to `font_run`, a toast, a menu or the file layer, so
  each needs a decode buffer. Under ~200 net, with risk on every notice path.
* **Boot-only data**: ~26 bytes on either kernel, and already overlaid (the
  clock probe's scratch in `clk_str`). The owner's instinct was right in kind
  and previous passes had already spent it.
* **Moving FDLG/FILECP to modules on kern_big**: ~5–7KB and the machinery
  exists, but the owner's standing decision (KERN-SMALL-MODULE-SPLIT) is that
  kern_big keeps them resident for speed.
* **Unions refused on lifetime**: `snd_xlat` (a worker can call the sound API
  without the gfx lock), `wm_clip_tab` (live through every painter hold),
  `dsk_ico` (staged by the mount without the gfx lock), the UI text buffers
  (they nest), the file-copy/dialog/loader scratch (those operations suspend
  to the event loop).

## 4. METHOD LESSONS

* **Six agents in parallel, each with a topic and a private worktree**,
  produced patches measured on their own base; the main tree applied them
  with `git apply -3`. Every agent's figure reproduced on the branch.
* **A worktree made mid-session silently takes the newer base.** Two agents
  reported against a HEAD that had moved; both said so. Quote the base.
* **An ABI renumber needs a search for PRIVATE copies of the address**, not
  only the SDK. §1.3.
* **`stkbalance` learns entry depths from jumps.** Deleting the unused 8-byte
  cold macros left `api_xc`/`api_n` as labels reached only by fall-through,
  and the walker then started them at depth 0 and reported two false leaks.
  They are comments now.
* **A build that reads the source tree while it is being edited sees a
  half-written file.** One `small128` run failed on `kernel.asm:6207`,
  `parser: instruction expected`, mid-edit; the re-run was green.

## 5. WHAT WAS RUN

The fast tier on every batch; per batch, the MartyPC soak rows the batch
could reach (mount and copy: `deskfdd`, `fcpapi`, `fcpcopy`, `fcpsmall`,
`hddcp`, `volsig`; the API: `pkgrun`, `pkgbig`, `kernresident`; the window
system: 16 rows from `bootsmoke` to `wmartifact`; the decoder: `blitplane`,
`blitcut`, `dispseam`; the modules: `hibernate*`, `diskclone`, `xmcheck`,
`lzmod-lzb`; the callbacks: 17 rows from `fmcommit` to `dockmodule`), plus
`small128` and `bootsmoke` throughout. `soak -k buildmatrix` at the close.
The whole soak tier was not run: it is the owner's to ask for.
