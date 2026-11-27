# Kernel size pass 21: sys

The sys agent's record. Files: `memory.inc`, `instance.inc`, `sched.inc`,
`mod.inc`, `events.inc`, `clip.inc`, `apps.inc`, `shutdown.inc`,
`hiber.inc` (resident half), `hbstub.inc`, `hbstage.inc`, `hbmark.inc`.
Branch `ksp21-sys`, cut from `3fc4e9d09` (the brief). TAKEN: no file
outside that list was edited except SPEC.md 8.8's one sentence about the
death panel's evidence (it moves with item 18).

Every figure is ASSEMBLED: `tools/kernsize.py --json` on each kernel, and
`tools/os88rdiff.py kernel 3fc4e9d09 HEAD` (and `-D KERN_SMALL`) per
routine. No estimate is quoted as a saving.

## BASE AND TIP

Resident is `.text` + `.bss` + `.cold` + `.lowbss` + `.vgabuf` + `.vga`
(kern_mega: plus `.mega`, unchanged at 24,800). The bases were measured in
this worktree and reproduce BRIEF.md 0.1 exactly.

| kernel | base | tip | delta | where |
|---|---:|---:|---:|---|
| **kern_big** | 90,225 | **90,118** | **-107** | `.text` 39,510 -> 39,468 (-42), `.bss` 4,973 -> 4,972 (-1), `.cold` 37,830 -> 37,766 (-64) |
| **kern_small** | 55,672 | **55,613** | **-59** | `.text` 29,101 -> 29,067 (-34), `.bss` 2,843 -> 2,842 (-1), `.cold` 20,860 -> 20,836 (-24) |
| kern_emu | 90,471 | **90,364** | **-107** | as kern_big: `.text` 39,756 -> 39,714, `.bss` -1, `.cold` -64 |
| kern_mega | 134,293 | **134,189** | **-104** | `.text` 45,275 -> 45,233 (-42), `.bss` 5,204 -> 5,203 (-1), `.cold` 53,078 -> 53,017 (-61), `.mega` unchanged; conventional (`.text`+`.bss`+`.lowbss`+`.vgabuf`) 56,415 -> 56,372 (-43) |

`accrued` at the tip: kern_big **6/512** (base 113), kern_small **317/512**
(base 376). kern_mega's footprint line is unchanged: resident 61,952 of
68,096 once `.cold` and `.mega` are above 1MB (image rung 50,688, 252
left). `KERN_SIZE` is unchanged on every kernel. `.lowbss`, `.vgabuf`,
`.vga`, `.boot2`, `.boot3` and every module image are unchanged in size (the
module headers' layout stamps move, as they do with any section size).

**No `int 13h` call added or removed.** No disk path was touched: the file
API's `inst_where`/`inst_vol_mark` (item 27) changed only how the caller's
slot is found, and `mod_need` is untouched.

**`hotpar` is green on both kernels at every commit** (checked with
`os88rdiff --hot` against the base as well as by the fast tier). One parity
pad went: `sch_dphex2`'s `nop` for `ui_task`, paired with `app_close_now`'s
odd byte (item 11). Every other odd item is paired inside the same window
of pinned routines (the four .text items before `sch_isr` sum to -4; the
window `sch_switch`..`ui_task` sums even on both kernels; the `.cold` items
before `dsk_xfer` sum even on both), so the routines between a pair sit at an
odd shift (an 8086/V20/286 cost only). `sch_isr` and `sch_switch` are
byte-identical. `stkbalance` over the kernel (the row's file list) is
0 -> 0 findings.

**COLD_HOME.** This branch moves `COLD_HOME` 0x0857 -> 0x0854 (three
paragraphs of `.text`+`.bss`). One item earlier it was 0x0855, and at that
value `make` FAILS at `coldhma.sys`: os88rom's cfix proof finds WIN95.DRV's
`83 EA 07 39 55 08` (`sub dx, 7` / `cmp [di+8], dx`) reading as a far call's
segment half. A coincidence of the value, not of this work - see CROSS-FILE 3.

## TAKEN

Bytes are kern_big / kern_small (kern_emu = kern_big; kern_mega said where
it differs). "Hot" is BRIEF.md 1's speed rule.

### memory.inc

1. **`mem_unblob_x` spends AX** (-4 / -2): its one caller, kmain, reads AX
   nowhere after the call (the boot timer and `ticks` loads write it first),
   so the `push ax` / `pop ax` go; and on the compacting kernels the rank's
   zero is `xor ax, ax` / `mov [mem_pg_rank], al` for a `mov byte` and the
   same `xor`. Contract updated in its banner.
2. **`mem_hifit` walks the claims through `mem_next`** (-6 / -6): BX is the
   best base now and SI the walk, so the hand-spelled table walk (bound
   compare, `jcxz` over a free record, the `add bx`) is `call mem_next` /
   `jc`. mem_runfree banks its own SI. H4 (a regrow): one call more a
   candidate, against each candidate's own mem_runfree walk of the table.
3. **`mem_in_xfer` without `or ax, ax` / `jz .no` off kern_mega** (-4 / 0,
   kern_mega 0): BX is a live record's base, never 0, so a 0 [mem_pinseg] is
   below it and the `jb .no` answers. kern_mega keeps the test: it hands AX
   to mega_selbasef.
4. **`mem_is_region` leaves DI = the record** (-5 / 0, kern_mega -5):
   mem_can_move's `.frameless` looked the same slot up again (`mov ax, bx` /
   `KDOOR inst_ptr`, -5 and an int 81h door call faster); mem_is_region loses
   its DI bank (-2) and mem_reloc_call, its other caller, banks DI round it
   (+2) so a relocation proc gets the DI it always had.
5. **`mem_cp_fill0` and `mem_cp_step` spend AX** (-4 / 0): both callers'
   walks hold no value in AX across them (mem_cp_walk's own banner, and
   mem_avail_lvl_p reloads AX before every read). Faster per claim per pass.
6. **`mem_regrowp`'s path 3 keeps no AX/CX bank round the copy** (-4 / -4):
   mem_bcopy preserves AX, CX and DI, and DI IS the new base, so the record
   and DX take DI.
7. **`mem_find_own`'s own-segment arm falls out on equal** (-2 / -2):
   `jne .scan` for `je .out` / `jmp short .scan`; equal is CF = 0.
8. **`mem_region_reloc`'s worker restart takes DX from BX** (-2 / 0):
   inst_fhome_idx's slot x 2, halved, IS the instance index the frame wants
   (inst_pkg_spawn spawned the worker with that DX, whose DL is the T_INST
   this used to re-read). `.text`.
19. **...and drops its second `cld`** (-1 / 0): DF is still the entry's.
20. **`mem_pg_forget` walks a `mem_pg_own` row with `lodsw`** (-3 / -3,
    kern_mega -4): the tag, then two more past the base and the count, so at
    `.hit` SI is the row + PGO_BASE and the arms compare and read there
    (`add cx, [si]`). An %error holds the layout. DF = 0 on entry is SPEC.md
    1 rule 3, which the claim doors already rely on (clip_put's `rep
    movsb`); no caller is an ISR.
21. **`osapi_mem_p`'s CLAIM and REGROW share one `mem_own` fence and one
    `call cx`** (-3 / -3): mem_regrowp reads AX, DX and the owner and keeps
    SI and DI, so the head and door worked out for a claim are harmless to
    it. CX is banked (the cell promises it back).
25. **`mem_compact`'s `.end` clears [mem_parked] and [inst_parkreq] as one
    word** (-5 / 0): [inst_parkreq] moves from instance.inc's `.bss` to
    memory.inc's, after [mem_parked] (an %error keeps them adjacent); -3 on
    the store, and `.none` is back in the prologue's short reach, so the
    `.none0` relay goes (-2).
26. **`mem_cp_dest` masks the length in** (-1 / 0): `mov ax, [MC_PARA]` /
    `and ax, [mem_cp_msk]` / `sub di, ax`, mem_cp_gap's own idiom, for the
    compare and branch. AX is the routine's to spend.

### apps.inc

9. **The VESA line is one loop over a string/word list** (-9 / 0): each
   string is followed by the word whose number goes after it, 0 for none;
   fm_scat, `lodsw`, fm_utoa, round again. -19 of `.cold` code, +10 of
   `.text` data. The buffer fm_hdrbuf receives exactly the bytes it did
   (the intermediate 'x', 0 is overwritten by the height's digits).
10. **The scheduler word by index** (-2 / -2): 'pre-emptive' and
    'cooperative' are both 12 bytes, so SI = s3p + 12 x [sch_coop]
    (`mul`), [sch_coop] being 0 or 1 by every writer (cp_schset normalises,
    the settings reader range-tests). An %error holds the lengths equal.

### instance.inc

11. **`app_close_now`'s hide arm tail-jumps `wm_hide`** (-1 / -1): wm_hide
    takes BX and keeps every register, so DI is popped first. `app_close_ret`
    is an `equ` of the routine's own `ret` now, so `.hide` stays in scope.
    Pays for **`sch_dphex2`'s parity nop** (-1 / -1).
15. **`inst_minimize` tail-jumps `wm_hide`** (-1 / -1), the same shape.
16. **`inst_unmin`'s not-minimized arm takes the other arm's `ret`** (-1 /
    0, WM_ANIM).
17. **`inst_minimize` sets IF_FSMIN with IF_MIN and clears it unless the
    window is fullscreen** (-4 / 0, WM_ANIM), for a clear and a set.
23. **`inst_charge` on the KENT ladder** (-7 / -7): `call kent_bp` and `jmp
    kret_si` after its own `pop bp` / `pop di`. H3: ~+100 clocks a CHARGED
    CALLBACK (a W_PAINT, a dispatched event), whose own bracket's two
    sch_account charges are ~1,000 and whose body is at least one primitive
    (PERFORMANCE.md: 756 us fixed) - under 1%. Same stack peak (kent_bp's
    transient word is where the old seventh push sat).
24. **`app_launch` keeps the kind in BL to the pool scan** (-1 / -1).
27. **`inst_caller_bx`**, inst_caller and its answer as an index with the
    range compare, for inst_where's and inst_vol_mark's common head (-3 /
    -3). H4: one call more per file operation.
28. **`app_launch` stores I_KIND / I_TASK at `.alloc`** (-8 / -8: -7 `.text`,
    -1 `.bss`): AL is still the kind there (inst_alloc keeps AX), the record
    is unpublished (no walker reads an I_STATE = 0 row), and a refusal below
    leaves it free for inst_alloc to zero again. The [inst_knd] byte, its
    store, its reload and the later store go.
29. **`app_launch`'s singleton front reuses the show's own `ui_lcall`**
    (-3 / -3): `jmp .lcall` with BP = inst_restore for `call ui_lcall` /
    `jmp .ok`. [inst_lkhd] is 0 on that path: fdlg_open sets it only to
    launch KIND_FILES, whose cap is above 1, so it never reaches the front.
30. **`inst_park_mk` reads the instance straight into BL** (-4 / 0):
    sch_currec's record offset has BH = 0 (MAX_TASKS x T_SIZE < 256, an
    %error), so the `mov ah` / `mov bl, ah` / `xor bh, bh` round trip goes.
    Faster on the gfx-lock block arm.
31. **`inst_park_req` drops the KIND_PKG test** (-6 / 0): a built-in's
    I_TASK is always 0xFF - only inst_pkg_spawn writes a slot there, behind
    inst_pkg_fence's KIND_PKG test, and app_launch and the loader publish
    0xFF - so `cmp byte [di+I_TASK], 0xFF` already skips every built-in.
22. **[sch_coop] moves under [sch_cur]** (-2 / -2): the snapshot reads the
    pair as one word and `xchg`s it into SS_CUR/SS_COOP order, for two byte
    loads. An %error in sched.inc keeps them adjacent; [sch_cur] /
    [fsx_task] stay adjacent for fsx_mine.

### sched.inc / events.inc

13. **`task_spawn` keeps the slot index doubled** until the cycle counter
    wants it x 4 and the answer x 1 (-3 / -3): the `shr cx, 1`, one `shl di,
    1` and a `mov` for an `xchg` go. Spawn only.
14. **`task_sleep` tail-jumps `task_yield`** (-1 / -1): task_yield takes no
    register and keeps them all, so BX and AX are popped first and the `ret`
    its frame resumes at is ours. Faster on ui_task's idle block (~-24
    clocks a sleep).
18. **`sch_diepanel` pushes its three fields straight out of the task
    table** (-5 / -5): `push word [bx+T_INST]`, `push word [bx+T_SP]`,
    `push word [sch_cur]` (the slot in AL, [fsx_task] above it) for three
    loads into DX/AX, three pushes and the last field's `xchg`. SPEC.md 8.8's
    sentence moved with it.
32. **`evq_mup` leaves through `evq_drain`'s `ret`** (-1 / -1), both answers
    with their flags.

Sum: kern_big 4+6+4+5+4+4+2+2+9+2+1+1 (batch 1) + 3+1+1+1+4+5+1+3+3+2
(batch 2) + 7+1+5+1 (batch 3) + 3+8+3+4+6+1 (batch 4) = **107**; kern_small
2+6+4+2+2+1+1 + 3+1+1+5+3+3+2 + 7+1 + 3+8+3+1 = **59**; kern_mega 107 - 4
(item 3) + 1 (item 20) = **104**.

## REFUSED

1. **`mem_cp_next` through `mem_next`** (-3): mem_avail and every
   compaction pass walk it per claim, an O(MEM_MAX^2) walk, and a call per
   record would make that ~half again slower. The speed rule.
2. **`osapi_sys_kb_x` and `mem_pg_forget` on `kentc_di`** (-3 each): +2
   words of stack on paths a package worker reaches (OSAPI_SYS_KB from any
   task; on kern_small a worker's claim sheds, so mem_pg_forget runs on a
   worker slice). Not proved safe; not taken.
3. **`inst_icon_ptr`'s `inc di` / `inc di` as `scasw`** (-1): reads ES:DI
   with ES unknown at both callers (a selector on kern_mega), +11 clocks a
   word.
4. **`clip_drop` reading and zeroing [clip_seg] with one `xchg`** (-1): the
   word would be 0 before the free, a window in which another task's
   clip_get sees [clip_bytes] set and copies from segment 0.
5. **`inst_park_hold`'s marks as `inc` / `dec`** (-2): relies on the byte
   being 0 at entry; the `mov`s are self-healing.
6. **`mem_pg_forget`'s `.ico` arm falling into the generic zero** (-2):
   fmv_icostale spends CX and SI.
7. **`mod_need`'s KERN_BIG id bank at `.held`** (+2 since pass 20, the
   `.race` fix): no cheaper way back to DI = the id (re-derived from the row
   is 10 bytes, off the KENT frame 6).
8. **The About box's four fixed rows composed from shared tails** (' - 16
   colors', ' - mono'): -17 of strings for +8 of table and ~20 of code.
9. **`hb_pick_x`'s loop counted in CX** so the fall-out keeps hb_pick1's CF
   (+1 with the bank).
10. **`mem_shed_one`'s two range compares as one subtract** (0, and unsafe
    if a floor puts the rank below MEM_PG_MIN).
11. Pass 18's, 19's and 20's REFUSED items in these files still hold and
    were not re-proposed (`inst_icobuf` as `dsk_ico` above all: the worker's
    dock repaint against a mount's staging window is unchanged).

## WANTS THE OWNER

None. No behaviour changed; every refusal answers as it did.

## WANTS AN ABI BREAK

None. No SDK, `apps/os88api.inc` or `drivers/os88drv.inc` byte moved;
`tools/abi.lock.json` is untouched. The snapshot's SS_CUR/SS_COOP order
(ABI) is unchanged: only the kernel's own `.bss` order moved.

## CROSS-FILE

1. **`diskw.inc` (diskw): declare `dskw_czseg` right after `dskw_wseg`**,
   then memory.inc's `mem_rr_tab` names the three as `MEM_RR_ROW dskw_seg,
   3, 2` and its `MEM_RR_ONE dskw_czseg` goes: **-4 `.text`** on the
   compacting kernels (both edits together; on kern_mega put it before
   `dskw_hi`). Not built here.
2. **`kernel.asm` (hw): the comment at kmain's `call COLD_SEG:mem_unblob_x`**
   says "mem_unblob keeps it" of AX; it spends AX now (item 1). AX is dead
   there either way. Documentation only.
3. **The coordinator: `COLD_HOME` = 0x0855 fails `make`** (os88rom's cfix
   proof, `coldhma.sys`) because WIN95.DRV (`winmod.inc`, wm's) carries `83
   EA 07 39 55 08`. Every agent's `.text`/`.bss` change moves COLD_HOME, so
   the merged tree may land on it; a paragraph either way clears it.
4. **`tests/zrestart.py`'s comment** says mem_compact clears [inst_parkreq]
   only when it asked; it has cleared it unconditionally since pass 16.
   Harness prose only.

## ROWS

None run here (BRIEF.md 3). The fast tier passed at every commit (`make`),
with `hotpar`, `stkbalance`, `stkclass`, `asmrules`, `ovlchk`, `api-abi`;
`make small`, `make emu` and `make mega` build at the tip.

NAMED for the final pass:

- the compactor, the shed and the claim map: `memp`, `heapcheck`,
  `regrowshed`, `smallfrag`, `pins`, `pinsrt`, `regpin`, `regmove`,
  `rehome`, `rehomemove`, `pxsmove`, `zrestart`, `trkcompact`,
  `shedrelist`, `icoshed`, `dirwshed`, `fatwpin` (fails at the base:
  HANDOFF-P21 section 6), `heapmap`, `dosarena`, `megashed`, `heaphi`;
- modules: `modcache`, `moddrop`, `megamodcache`;
- the scheduler, spawn, the panel, the park: `stkclass`, `stk0water`,
  `stkpanel`, `instkeep`, `thewire`, `cpup` ([sch_coop]), `tmload`,
  `tmsmall`, `megatmmem` (the snapshot), `kbdpreempt`;
- launch, close, minimize, restore: `smalllaunch`, `deskdock`, `deskclose`,
  `dockmark`, `alertanim`, `hibernate`, `win16mdi`;
- events: `evqfull`, `wakedrain`, `dragui`, `deskdrag`;
- the file API's caller (inst_where / inst_vol_mark): `pkgrun`, `kdcwd`,
  `dosfile`;
- the About box: `stk0water` (launches it), and the `vesa*` rows for the
  VESA line (`vesa`, `vesacp`).

## DEFECTS FOUND

None in behaviour. One build-gate coincidence (CROSS-FILE 3), met and
cleared on this branch.
