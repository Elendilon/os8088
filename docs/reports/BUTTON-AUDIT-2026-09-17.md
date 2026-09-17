# Every button in the tree, audited — 2026-09-17

Commit `933fc38d`, build 859, on the session container (4 cores, no MartyPC
built). A MEASUREMENT of the tree it was taken on and of no other
(`docs/README.md`): a later cycle re-takes it as a new file rather than
editing this one.

The brief was three questions over everything we own — packages, C packages,
drivers, kernel; host-side Python excepted because it does not go through our
control:

1. hand-rolled buttons
2. UI buttons broken in any way
3. buttons with two handlers, the wrong handlers, etc.

**Scope reached: 60 call sites of the shared control in 32 files, 35 record
declarations, 7 C packages, and every `gfx_frame` caller in the tree.** One
live defect, one real gesture defect, two structural gaps, and a short list of
deliberate hand-rolls with reasons.

## 1. What was LIVE, and is fixed

**Five button records were four bytes too narrow and Sheet writes past all
five of them on every dialog open.** `933fc38d`, cherry-picked to
`elendilon-next` as `c577ad9c`.

`os88ui_btninit` writes `OS88UI_BT_ONCLK` at +12 and `OS88UI_BT_NEXT` at +14,
so a twelve-byte record puts four bytes of LIBRARY state on whatever the
package declared next. Seven declarations were 12; five were live, and Sheet
calls `btninit` on all five of its dialogs:

| record | +12 lands on | +14 lands on |
|---|---|---|
| `sh_fdlg_btrec` | `sh_fdlg_count` (the kind's row count) | `sh_clipbuf` |
| `sh_ldlg_btrec` | `sh_ldsb` (`os88ui_sbar`'s seven-word block) | `sh_ldsb+2` |
| `sh_bdlg_btrec` | `sh_bdrawflags` | the byte after |
| `sh_ndlg_btrec` | `sh_idlg_win` (the Insert dialog's instance guard) | the word after |
| `sh_idlg_btrec` | `sh_rw_absc` | the byte after |

`sh_idlg_win` is the sharp one outbound: it is the `0 = none` word Sheet asks
before opening the Insert dialog, and what landed on it was a code address,
which reads as *already open*. **Inbound is worse** — `OS88UI_BT_NEXT` is the
list link `os88ui_btnclick` walks on every press, so a Copy into `sh_clipbuf`
corrupts it, and that walk then compares `[bx+OS88UI_BT_WIN]` through a
garbage pointer and can reach `call bx` on a garbage `OS88UI_BT_ONCLK`.

Word and Scribe had the same shortfall LATENTLY — `WDVAR wd_btrec, 12` /
`SCVAR sc_btrec, 12`, with `*_dgdown` ("which control is a press live on")
declared immediately after. Neither calls `btninit` today, so nothing writes
those offsets; `btninit` is exactly what a conversion adds.

Proven before it was fixed with the `times` trick `sheet.asm` already uses on
its own bss total: five assertions, five `TIMES value -4 is negative`.

## 2. What is REAL and is the owner's call

**`apps/apple2`'s Machine > Power On confirmation fires on the PRESS.** Its
Yes/No hit test is inside `os88_onclick` (apple2.c:1719), which resolves the
button, calls `a2_panel_close(win, yes)` and returns; the package defines no
`os88_onmouseup` at all. A press on **Yes** power-cycles the emulated Apple
immediately — there is no slide-off to change your mind, which is the whole of
what SPEC.md 13.7 exists to give, and this is the one press-fired button in
the tree behind a data-loss box (its own comment calls it that).

It is left for a decision because the fix has three shapes with different
costs in a GPL'd package that carries a resident/overlay split:

- hand-roll the gesture: arm on the press, act on `os88_onmouseup` only when
  the release lands on the armed button. The rects and labels are already
  resident statics, so this is ~15 lines and no overlay change — but there is
  no tracking edge available (see gap B), so the button un-presses at the
  release rather than on the way off;
- reach the shared control the way `apps/weave` does — `%include "os88ui.inc"`
  from the package's root `.asm` with `OS88UI_ARM` — which is the consistent
  answer and costs the library's bytes in the region;
- put the question through `os88ui_ask` (OS88UI_AYESNO), which `apps/loom`
  already does from C via `lm_alertdone`. Cheapest of the three and changes
  the panel's look.

## 3. Two STRUCTURAL gaps in the C SDK

**A. There is no button control in `apps/cc/os88.h` at all.** No
`os88_ui_btn`, no record, nothing — so every C package that wants a button
draws `os88_gfx_frame` + `os88_font_run` by hand and owns the gesture. Four do:

| package | what | edge | pressed look |
|---|---|---|---|
| `apple2` | About OK; **Power On Yes/No** | press | none |
| `c64` | About OK | press | none |
| `runcpm` | About OK (double frame) | press | none |
| `cword` | dialog buttons, ribbon toggles | press | ribbon lights |

The three About OKs are dismiss-only, where cancellation is meaningless, so
they are cosmetic — they show no pressed look and are inconsistent with every
other button on the machine, and nothing else. CWord's ribbon is a toggle and
arguably SPEC.md 13.6's safe prefix action.

`apps/weave` is the counter-example and the model: it includes the assembly
library from `weave.asm`, exposes `os88ui_arm`/`fire`/`armed` to its C half
through `wui.inc`, and fires on `os88_onmouseup`. `apps/loom` uses the alert
card. `apps/paccman` has no buttons.

**B. There is no `ondrag` in the C SDK either.** `os88.h` publishes
`os88_wm_onmouseup` and no drag enabler, so **no C package can implement
13.8.2's tracking edge** — press-and-slide-off cannot un-press a C button even
when the package does everything else right. Weave included.

## 4. Deliberate hand-rolls, with their reasons — NOT defects

- **`kernel/fdlg.inc`'s `fdlg_btn2`** — the two-line New/Folder button.
  `os88ui_btn` centres ONE label in both axes and this is two lines; the
  routine says so. Audited in full: geometry fits the 152px content box, the
  Save-mode loop reaches index 4, both strings resolve DS-relative on both
  kernels. (A field report of this button *missing* during the audit turned
  out to be a stale disk.)
- **`apps/modplug`** — the whole face is a skinned hardware unit (bevelled
  body, green LCD, LED transport row), so the transport is not a System-1
  button by design. Everything on it acts on `W_ONCLICK`; there is no mouseup
  or drag, so the sliders and the scrubber also set on the press and do not
  track.
- **`apps/piano`** — the KEYS keep the press and must: a note is a safe prefix
  action (already in `tests/btnsites.txt`).
- **`apps/taskmgr`** — six `gfx_frame` calls, all the heap map; `tm_dmg_hit`
  is a damage-rect test. No buttons, correctly absent from the registry.
- **`kern_small`'s Standard File dialog** — `fdlg_onclick_x` calls `fdlg_bact`
  on the PRESS there and arms on kern_big (fdlg.inc:2951). Deliberate,
  documented in place: *"kern_small keeps the old behaviour, which is all it
  can afford"*. It is the one button in the tree that still fires on the press
  by decision.

## 5. What came back CLEAN

- **Two handlers: none.** Zero direct `OSAPI_WM_ONCLICK` calls anywhere
  outside `os88ui.inc`, so nothing clobbers `os88ui_btnclick`. All six
  `os88ui_btninit` call sites pass the identical register set (AX window, BX
  record, SI up, DI drag, DX click).
- **Wrong handlers: none.** Every one of the 24 arm-driven callers has the
  textbook split — `os88ui_arm` in the press path, `os88ui_armed` in the drag,
  `os88ui_fire` in the release. Not one `os88ui_fire` in a press path. The
  three sites that arm outside a click handler are `xor ax, ax` first: they
  CLEAR a stale arm at window open, which `svcfg.inc` states as *"a window
  reopened mid-gesture must not come up with one armed"*.
- **Rect-for-a-record: none left.** All 60 sites resolved by the nearest
  preceding BX load; every `os88ui_btn` caller loads a `*_btrec`, every
  `os88ui_kbtn` caller loads `os88ui_krect` (that entry's contract), and
  ctrl/hiber pass a rect to `os88ui_btn_f`. The three apparent misses are
  `pop bx` restoring the caller's record in `os88ui.inc`'s own handlers.
- **`os88ui_btnraw` is gone** and cannot come back (`t_btnrules`).
- **The record's other fields** are aimed everywhere: no file calls
  `os88ui_btn` without writing `OS88UI_BT_RECTS` and a count.

## 6. What the instruments could not see, and now can

Three blind spots cost real bugs this cycle and all three are closed in
`tests/unit/t_btnrules.py`:

1. **A wrapper macro hides a call.** `FDX os88ui_btn` is `call os88ui_btn` on
   kern_big and `call COLD_SEG:xd_os88ui_btn` on kern_small, so neither
   spelling matches a grep for `call os88ui_btn` and `kernel/fdlg.inc` was not
   in the registry at all. The gate matches any uppercase wrapper now, because
   the tree has six more of the same shape (`FCPX`/`FCPXF`, `OVWCALL`,
   `DKXPAD`, `OSAPI_CSLOT`, `OSAPI_FARCELL`).
2. **The library's own call sites were exempt.** That is how the alert card
   shipped handing a rect to a record. Each site in `os88ui.inc` must now
   prove, inside its own routine, that it treats BX as a record.
3. **Record width was checked nowhere.** A `%if` cannot see Sheet's
   reservation — the `equ` chain is built on `os88_image_end`, a LABEL, and
   labels are not preprocessor-visible. The gate reads all four declaration
   shapes on the host instead.

And one that is still open: **`t_btnrules` had a `check()` whose condition was
a string literal**, so the row could not fail for any input. It printed
findings while `make` reported `ok btnrules`, and three of them had been
printing on every build since the row landed. Fixed; the lesson is
docs/WRITING-TESTS.md §1's, which is that nobody investigates a pass.

## 7. Still owed

**No row in the suite drives the alert card or the Standard File dialog's
buttons.** `btnall` covers the package records, `btncp` the Control Panel's far
entry, `btngesture` Telnet's Connect — and none of them touches the two
kernel-side controls that both shipped broken this cycle. That gap is why a
person found each of them.

A second row is owed for the record width on a running machine: the static
gate catches the declaration, but nothing asserts that `btninit` left the
neighbouring cell alone.
