# Toast queue and operation-wide progress: what each costs (2026-10-31)

Measured on branch `toast-n-progress`, cut from `elendilon` at `c844ccc`, in a
cloud container. Both changes were built as working prototypes so the figures
are bytes off the assembler, not estimates. `tools/kernsize.py --json` on
kern_big and on kern_small (`-DKERN_SMALL`), before and after. The fast tier
passes on the prototype. **Neither change has been driven on the glass.**

## 1. Toasts queue instead of replacing each other (SPEC.md 59)

**The defect.** `toast_show` has one buffer. Whoever calls it last wins. On
kern_mega with RLAPPLY autostarting, `mega.inc` stages `Entered protected
mode` for 146 ticks, and RLAPPLY's `Chipset settings applied` lands while that
toast is still staged or still up, so it overwrites it.

**The prototype** (`kernel/toast.inc`, `kernel/loader.inc`):

- There is **one** queued slot (`toast_qbuf`, `toast_qttl`, `toast_qinst`,
  with the `toast_qwant` flag in `.text`).
- If a toast is up or staged and a **different** raiser calls `toast_show`, the
  new message goes into the queued slot. If the slot is already full, the
  newest message wins.
- The **same** raiser still replaces its own message, as today. So Paint's
  `Encoding...` followed by `Saved X` stays one message and does not queue for
  three seconds.
- `toast_pass` promotes the queued message at the same edge that retires the
  current one (expiry or `toast_kill`). The new strip goes up in the
  composition that takes the old one down: one `menu_draw_bar`, not two.
- A retire (empty string) still kills the current toast, as before. It also
  drops the caller's own queued message, otherwise retiring would make that
  message pop up.
- `toast_owner_gone` drops a closing instance's queued message.
- The loader's `.abort` re-home (SPEC.md 19.2.1) re-homes a queued message as
  well as the current one. RLAPPLY is exactly this case: its entry proc
  returns CF = 1.

| | kern_big | kern_small |
|---|---|---|
| `.text` | +122 | +122 |
| `.bss` | +28 | +28 |
| `.cold` (loader re-home) | +23 | +23 |
| **resident total** | **173** | **173** |

The idle cost is one near call per `ui_task` pass while nothing is up:
`toast_promote` finds `toast_qwant` clear. An inline `cmp`/`je` would remove
that call for about 5 more bytes.

**Open points, priced but not built:**

- **Wait time.** The queued message waits out the current toast's whole
  life. Behind kern_mega's 146-tick toast, RLAPPLY's message would appear
  about 8 s after boot. Capping the current toast's remaining life at
  `TOAST_TICKS` when something queues behind it would be about 12-15 bytes in
  the `.queue` arm.
- **Depth.** A deeper ring would cost about 28 `.bss` bytes per slot, plus
  index code of roughly 30-40 bytes. The collision seen in practice is a pair.

## 2. One progress scale for the whole operation (SPEC.md 12.8)

**The defect.** SPEC.md 12.8.3 keeps the widget's chrome up for the whole
freeze, but re-scales the trough at every `fpg_begin`. A file-manager copy is
`dskw_read_seq` + `dskw_write_seq` once per chunk (`FCP_MAXKB` = 64KB). So a
700KB copy fills the bar about 22 times, and between fills, while the FAT and
directory are written, `fpg_busy` hatches the whole trough over what was just
filled.

**The prototype** (`kernel/fprog.inc`, plus one call site in
`kernel/filecp.inc`):

- **`fpg_opbegin`** takes `DX:CX` = the bytes the whole operation will move,
  counting every phase. For a copy that is twice the file: the read and the
  write both pass `dsk_xfer`'s step. It scales the trough once and sets a new
  `FPG_OP` bit (8) in `[fpg_on]`.
- **`fpg_end`** banks the phase's scale in `[fpg_opt]` as it zeroes
  `[fpg_total]`. `fpg_end` is reached from every `dskw_*_x` epilogue, and it
  still writes no flag.
- **`fpg_begin`** checks `FPG_OP` first. If set, it restores the banked scale
  and continues the same count instead of re-scaling. `fpg_step`, the hot path
  in `dsk_xfer`, is **unchanged**.
- **Between phases**, `[fpg_total]` is 0 as before. So metadata sectors are
  not counted, and the bar does not run ahead of the data. The hatch is drawn
  over the **unlit remainder only** (`fpg_rem`): the filled part stays, and
  the unfilled part is dithered while the FAT and directory are written. This
  is the "dithered remainder" option. When the next data phase starts, the
  remainder goes back to white with one `gfx_fill`.
- **Ending the operation.** `fpg_finish` clears `[fpg_on]` whole at the
  unlock, which also ends the operation, so there is still no bracket to
  forget. `fpg_opend` exists for a caller that ends the operation inside the
  same hold, as the copy loop does once per file.
- **The overdraw repair (`fpg_paint`)** now redraws the lit extent and then
  the hatch, instead of choosing one of them. Without an operation scale,
  `fpg_rem` zeroes the extent when it hatches the whole trough, so nothing is
  drawn twice.
- **The copy loop (`fcp_xfer`)** calls `fpg_opbegin` with twice the source
  file's size and calls `fpg_opend` at its single exit. kern_small already had
  that size from `dskw_stat_x`. kern_big did not, so it gains one
  `dskw_stat_x` before the first chunk. That is one directory lookup, almost
  always served from the directory cache, because `fcp_file1` has just walked
  that path.

| | kern_big | kern_small |
|---|---|---|
| `.text` (fprog, incl. a 1-byte PARITY pad for `ui_task`, t_hotpar) | +102 | +102 |
| `.cold` (the copy site, which is `.cold` on kern_big) | +25 | 0 |
| `FILECP.DRV` on disk (the copy site, which is a module on kern_small) | n/a | +14 |
| **resident total** | **127** | **102** |

Drawing cost per chunk boundary: one `gfx_fill_gray` over the remainder at the
first metadata sector, and one `gfx_fill` to put it back. That is a few
milliseconds against the ~400 ms of a single `int 13h` (PERFORMANCE.md
Part 2).

**Not covered by the prototype:**

- **A folder or multi-select copy** still shows one bar per *file*. A total
  for the whole set needs a sizing walk before the first byte moves. Inside a
  tree, that walk is `int 13h` calls, each about 400 ms on a floppy.
  One-folder multi-select is cheaper, because the Disk window's listing
  already holds the sizes. Not priced.
- **Packages and DOS.** A windowed DOS program that reads a file in `int 21h`
  chunks is still many phases. Publishing `fpg_opbegin`/`fpg_opend` as
  `OSAPI_*` slots would cost a cell each (SPEC.md 20.3), and adding them is an
  ABI decision (SPEC.md 20.2.0.1).
- **The icon-swap alternative** (a second glyph while metadata is being
  written) would cost about 56 bytes of icon data, plus a two-pass masked
  `icon_draw` at every phase edge. That is more resident bytes and more
  drawing calls than the dithered remainder.

## What was not done

- Neither change was exercised in an emulator. The progress widget needs
  MartyPC to be seen at all, because QEMU finishes the copy inside one frame.
  The kern_mega + RLAPPLY case needs Bochs or 86Box (docs/BOCHS.md,
  docs/86BOX.md).
- No SPEC.md section was rewritten. If either change is kept, SPEC.md 59.3 and
  12.8.3 change before the code does.
- The soak rows that cover these are `toastbar`, `toastfpg`, `fpgcold`,
  `fpgnotch`, `curdisk` and `rltune`. None of them has been run.
