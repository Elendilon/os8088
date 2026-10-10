# ksp11 agent "multisel" - the Disk window's multi-select (SPEC.md 22.27)

Kernel size pass 11, concept agent for merge `323f0efb` (multi-select:
`kernel/files.inc`, `kernel/filecp.inc`, `kernel/memory.inc`,
`kernel/kernel.asm`, `apps/os88api.inc`). Branch `ksp11-multisel`, cut from
`elendilon` at `2a05e31f`. The feature had already had TWO size passes by its
author (`791cc93a` -138, `d6b7904c` 1,418 -> 797); both are recorded in
docs/plans/completed/MULTISELECT-PLAN.md §A/§A.1, which has no refused list,
so this note's REFUSED section is the first one the feature has.

Figures are ASSEMBLED, `tools/kernsize.py --json` sections; resident =
`.text` + `.bss` + `.cold` + `.lowbss` + `.vgabuf`. "Feature" = kern_big minus
`make MSELOFF=1` at the same commit (`kernsize --build build/msoff -DMSELOFF`).

## Base `2a05e31f`

| | text | bss | cold | resident | KERN_SIZE |
|---|---:|---:|---:|---:|---:|
| kern_big | 43,428 | 5,190 | 37,943 | 92,495 | 98,304 |
| kern_small | 32,022 | 3,073 | 23,479 | 61,442 | 63,488 |
| MSELOFF=1 | 43,415 | 5,145 | 37,204 | 91,698 | 97,280 |
| **feature** | +13 | +45 | +739 | **797** | +1,024 |

## MSELOFF=1 and "byte-identical"

The knob's promise was that `MSELOFF=1` assembles byte-identical to the kernel
before the feature. That can only stay true while nobody touches code the
feature SHARES, and this pass did (fm_onkey_x's layout, fm_edit_commit's
Format block): the MSELOFF arm moved -32 with them, exactly as kern_small did.
What this pass keeps is the knob's MEANING - every byte the feature adds is
inside `%ifdef FM_MSEL`, so big minus MSELOFF at one commit is still the
feature's price - and that the arm ASSEMBLES (it caught one short jump that
only fits with the feature in: batch 1's `jmp .owedcf`).

## TAKEN

### Batch 1

Concept (inside `%ifdef FM_MSEL`, kern_big only):

* **fm_mset enters the bitmap itself.** Every caller of `fm_mone` called
  `fm_menter` first (the click's `.newsel`, the right-click, the plain arrow);
  `fm_mset` now does, and `fm_mto` - which entered already and reads the anchor
  `fm_menter` sets - calls `fm_mset.nm`. It has to: with nothing selected a
  second `fm_menter` inside `fm_mset` would put back the 0FFh anchor
  `fm_mto` has just replaced with the first row of a drag select. The
  arrow's own `fm_menter` went too (its Shift path is `fm_mto`). **-6**.
* **fm_mbit answers the byte's ADDRESS** (`lea bx, [bx+di+FS_MSEL]`), so its
  five users are two-byte `[bx]` forms (`test`, `or`, two `xor`s and the
  `.mctrl` toggle): +3 -5; and `mov cl, 7 / and cl, al` for `mov cl, al / and
  cl, 7` (-1). **-3**. Faster per index in `fm_mset`'s walk too: `[bx]`'s EA is
  5 clocks against `[bx+di+disp8]`'s 11, twice an index, for one `lea`.
* **fm_manyvp** (`mov di, [fm_vp]` falling into `fm_many`): the three
  callers that loaded DI inline right before `fm_many` - Delete's arm, the
  right-click and `fm_lsel_bar`. +4 -12, **-8**.
* **The drag-select arm is `or word [os88ui_armw], -1`**, FM_BBAND being all
  ones (`%error` pins it): **-1**.
* **The click's miss reaches `.newsel` straight from `fm_hit`**: with FM_MSEL
  a miss already answers AX = 0FFFFh, so `.clear`'s `mov ax, 0xFFFF` and
  `.select`'s `jmp short .newsel` are the non-MSEL arm's alone (`.select` falls
  in). -5. **And `.band` moved past `.out`** (beside `.mctrl`), which took the
  scroll bar's `jc .redraw` back inside a short jump - the feature's own
  relaxed pair (-3) - for one `jmp short .ment` (+2). **-6** together.
* Delete of a set: `mov bx, fm_mw_del` above the set test, so the single
  entry's body is `call bx`. **-1**.

Layout (shared code, so on every build - not the concept's bytes, but the
concept made two of them worse):

* **fm_onkey_x had ELEVEN relaxed jumps** (33 bytes of `j!cc +3 / jmp near`),
  one of them the feature's `je .selall`. The editor's keys moved IN LINE ahead
  of the command keys with their own three-byte exit (`.rdI`/`.outI`), the
  scroll's `.scr_move` follows the decode it is the end of (its `jmp`
  deleted), Enter sits before Cut and jumps to `.owed`, Ctrl+A sits beside the
  ladder's bodies, `.outj`'s trampoline is gone, and kern_big's arrow block
  (150 bytes with the feature) is past `.out`, where its exits are short and
  its Save-box tail joins `.owed`'s own `jnc` (`.owedcf`). **kern_big -33**
  (-31 the reorder, -2 `.owedcf`); none of them is left relaxed.
  **The margins are thin**: Ctrl+A's `je` is 126 bytes from its body and the
  scroll decode's `jnz .out` 120, so anything that grows the ladder's bodies
  will relax one of them again silently - read the listing.
* **fm_edit_commit's Format block moved past the exit**, which took the Save
  box's `je .save` back inside a short jump. **-3**, on both kernels.

Batch 1: **kern_big 92,495 -> 92,433 (-62)**, kern_small 61,442 -> 61,435
(-7), MSELOFF 91,698 -> 91,666 (-32). **The feature is 767** (cold 709,
text 13, bss 45). kern_big `KERN_SIZE` 98,304 -> 97,792: the cold rung (55
bytes into its 75th step at the base) uncrossed - the merge's business, not a
design input.

## REFUSED

* **One global bitmap instead of eight bytes a block** (`.bss` 40 -> 9). Only
  the front window takes a gesture, but every window KEEPS its set when it
  loses the front, and its bands are XORed on the glass: a second window
  entering a set would have to take the first one's bands off - an XOR inside
  a window that is no longer on top, which `fm_sel_bar` is correct only
  because it never does (its header) - or repaint it whole. Either is more
  code than 31 bytes of `.bss` and a behaviour change besides.
* **The chooser block's eight bytes** (the fifth block never holds a set):
  FS_MSEL out of the block into a four-entry table costs an index computation
  at every one of the bitmap's seven access sites. 8 bytes of `.bss` for more
  than that in code.
* **The bitmap always mirroring the selection** (so `fm_menter`, 26 bytes,
  goes): "more than one" then needs a population count where "any bit" is four
  ORs, and a set of ONE would take the list paths - "Delete 1 items?" and a
  1KB claim to Cut a single file.
* **`fm_mods` through `kbm_shf`**: that body is in `.text` and `fm_mods` in
  `.cold`, so the call would need a far thunk; -9 of body for more than that.
* **`fm_mods`'s chooser test at the call sites** instead of in the body: the
  chooser reaches the modifier read through the shared `.ment` path and
  `fm_dgarm`, so the test would be written twice.
* **fcp_lbegin's floor store through `mmf_osapi_mem_floor`** (OSAPI_MEM_FLOOR's
  own far body): built, -2 as `push cs / call`, which os88ovlchk refuses twice
  over - the walk's model files `fcp_lbegin` as `.modp`, and `push cs` in
  `.cold` is a CS assumption (SPEC.md 2.6 rule 2). `call COLD_SEG:` is -1 and
  needs the routine moved into the trailing `.cold` block. Not worth either.
* **`fm_mdelarm`'s `mov cx, 6`** (-3): `fm_mwalk` happens to return CX >= 256
  (CH is the last index's bit), which `fm_ncpy` would accept as "to the NUL" -
  a contract nobody wrote, on a once-per-Delete path.
* **`fm_mwalk` and `fm_mset` sharing one loop** (a "for every index, call BX"
  driver, each a callee): the walk's member test and stop rule and the diff's
  SI/DX/CL all want registers the driver would hold. ~5-10 bytes at best, and
  slower per index in the drag select's diff.
* **fm_armset's two walks as one** (the first finds the entry `fcp_arm` arms;
  the second fills the list): `fcp_arm` frees any list, so the claim must
  follow it, and arming from record 0 instead needs drive, folder, type and
  name copied by hand - more than the 8 bytes the first walk costs.
* **The Cut/Copy/Paste/Delete bodies as `db 3Dh` skips** (-5): os88ovlchk
  refuses data directives in `.cold`.
* `fm_many`/`fm_mzero` as loops: `fm_many` cannot (`dec` writes ZF), and
  `fm_mzero` saves 2 for a loop on every `fmv_store`.

## Defects

(none yet)

## Cross-file list

(none yet)

## Rows run

(batch 1: see below)
