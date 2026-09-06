# The IN-WINDOW MENU as a shared element (`OS88UI_MENU`)

**Status: PROPOSED, costed, not started.** SPEC.md 13.14.4 is the entry point;
this is the arithmetic behind it and the questions it cannot answer from the
outside.

## 0. Where it came from

Word was asked whether it could use `os88ui_drop` (SPEC.md 13.14), CLEAR SKIES'
drop-down, for its ribbon combos. Taken literally the answer is no, and the
first version of 13.14.4 said so on bytes alone — which was the wrong argument
about the wrong unit. `apps/os88ui.inc`'s own header had already settled the
first half:

> Saving bytes was never the argument … The argument is that a feature added
> to the button lands in the Standard File dialog, the Control Panel, the
> Timer AND every package at once, because there is one body rather than ten
> that agree by hand. SPEC.md 47's greying rule was fixed FIVE separate times
> in this tree, each as its own bug.

And the second half is that the unit Word shares is not a list. It is a menu.

## 1. What is actually duplicated today

Three independent implementations of one control:

| | code | table | keyboard | save-under |
|---|---:|---:|---|---|
| `apps/word` (`wd_m*`) | 3,486 | 96 | yes (~375 b) | **yes** (§68.2.1) |
| `apps/sheet` (`sh_m*`) | 1,382 | 54 | no | **no** |
| `kernel/menu.inc` | — | — | yes | §12.4's own |

Word's and Sheet's are measured by symbol span, to the next GLOBAL label, on
the shipped source. The kernel's is not comparable: `menu.inc` also owns the
desktop bar, the Apple menu, the clock and the app-menu protocol (§12, §13.10),
so only part of it is the same control.

**Sheet's is a hand copy of Word's.** `sh_mtrack`'s comment says so outright —
*"word.asm's `wd_mtrack` pattern"* — and it shows in what the copy did not
take, because §68.2.1 landed afterwards: **`sh_mclose` sets two bytes and calls
`sh_repaint`**, which white-fills `[sh_ox],[sh_oy]` to the content's full width
and height and draws it again. That is exactly the shape Word measured at
**521.4 ms** and replaced with a blit at **19.7**. Sheet's own figure is NOT
measured here — two attempts to bracket it failed to land a click on its bar
and the run was abandoned rather than guessed at; the source is what says it,
and the source is unambiguous.

## 2. What would move, and what would not

Word's 3,486 bytes split cleanly:

| | bytes |
|---|---:|
| **the CONTROL** — `wd_mbar`, `wd_mtxor`, `wd_mtitler`, `wd_mgeo`, `wd_mdraw`, `wd_mfind`, `wd_mhl`, `wd_mbarhit`, `wd_mopenm`, `wd_mclose`, `wd_mtrack`, `wd_mclick_open`, `wd_minrect`, `wd_mfire`, `wd_mgeti`, `wd_mitemp`, `wd_subank`, `wd_surest` | **1,895** |
| **WORD'S OWN** — `wd_mact`, `wd_mchk`, `wd_mrepair`, `wd_mroute`, `wd_mkey`, `wd_mstep`, `wd_suab`, `wd_sudlg` (what a pick MEANS, the greying predicates, key routing, the repair) | 1,591 |

So the trade inverts against the one 13.14.4 first evaluated:

* adopting `os88ui_drop` alone: Word **deletes ~150, adds 1,779**;
* `OS88UI_MENU`: Word **deletes ~1,895**, Sheet **deletes ~1,382**, and both
  add one element.

Whether Word breaks even depends on the element's size, and **nobody knows
that until it is built** — an element serving two looks is normally bigger
than either. What does not depend on it: Sheet is missing a fix Word has, and
a shared body is how it stops being missing.

## 3. What the element would have to carry

* **The bar**: titles laid out from a table, the highlight, the hit test.
  Word's bar is Word 1.1a's and Sheet's is its own; the geometry is already a
  pointer in this file's idiom (a 4-word rect), so the difference is table
  data rather than code — **to be proved, not assumed**.
* **The drop**: geometry, the cells, the check marks, the disabled treatment
  (§47, and the whole reason the file exists).
* **The gesture**: `wd_mtrack` and `sh_mtrack` are the same tight
  `OSAPI_MOUSE` poll with an unlock/yield/relock between reads, and neither
  uses `W_ONDRAG`. They already agree; they just agree twice.
* **The bank**: §68.2.1 and §13.14.1 are the same trade published twice
  already. This is the third and it should be the last.
* **The keyboard**, `%ifdef`-gated. Word has Alt+mnemonic traversal
  (`wd_mkey`, `wd_mstep`); Sheet has none, and must not pay for it. That is
  the file's own idiom — `OS88UI_DROP`, `OS88UI_CHK`, `OS88UI_BARONLY`.

## 4. Open questions, in the order that decides the work

1. **Is the bar difference really data?** Word's titles, spacing and the
   ruler's second strip against Sheet's single bar. If it is code, the element
   grows and Word stops breaking even.
2. **What does the kernel do?** `os88ui.inc` is ONE SOURCE FOR TWO WORLDS and
   already assembles into `.cold` with `OS88UI_KERNEL`. If the element can
   serve `menu_draw_bar`/`menu_drop` too, the third copy goes and the
   argument is settled; if it cannot, say why here.
3. **Does Word's save-under generalise?** `wd_subank` takes the rect and the
   window; `os88ui_drbank` takes a record. One of the two shapes wins.
4. **Two shipped packages change at once.** This is not a Word branch's work
   and should not ride on one.

## 5. What is NOT proposed

Converting a *skinned* control. The header's own exclusion stands: ModPlug's
bevelled well and Minesweeper's cells are intended design, not duplication.
Sheet's and Word's bars are the kernel's pull-down drawn twice, which is the
opposite case.
