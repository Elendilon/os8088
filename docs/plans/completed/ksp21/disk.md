# Kernel size pass 21: disk (dsk_xfer, the mount, the BPB rules, FIND, the LZ decoder)

The **disk** agent's record (BRIEF.md section 2). Owned: `disk.inc`,
`drvvol.inc`, `lz.inc`, `lzfilt.inc`, `fsck.inc`, `clu.inc`. Branch
`ksp21-disk`, cut from the brief commit `3fc4e9d09`. TAKEN outside those
files: nothing. `drvvol.inc`, `lzfilt.inc`, `clu.inc` and `fsck.inc` were read
and are unchanged (`fsck.inc`'s resident part is a 47-byte stub; the rest is
FSCHECK.DRV's image). No ABI moved: `apps/os88api.inc`, `drivers/os88drv.inc`,
the C SDK and `tools/abi.lock.json` are untouched; no module image changed.
`dostools/os88cz.asm` includes `lz.inc` and is 5,170 -> 5,167 bytes.

## BASE AND TIP

Assembled, `tools/kernsize.py --json` on all four kernels in this worktree.
Resident = `.text` + `.bss` + `.cold` + `.lowbss` + `.vgabuf` + `.vga`
(+ `.mega`).

| kernel | `.text` | `.bss` | `.cold` base -> tip | resident base -> tip | delta | `KERN_SIZE` |
|---|---:|---:|---:|---:|---:|---|
| **kern_big** | 39,510 -> 39,512 | 4,973 | 37,830 -> **37,699** | 90,225 -> **90,096** | **-129** | 95,744, unchanged |
| **kern_small** | 29,101 | 2,843 | 20,860 -> **20,779** | 55,672 -> **55,591** | **-81** | 57,344, unchanged |
| kern_emu | 39,756 -> 39,758 | 4,973 | 37,830 -> **37,699** | 90,471 -> **90,342** | **-129** | 95,744, unchanged |
| kern_mega | 45,275 -> 45,277 | 5,204 -> 5,200 | 53,078 -> **52,950** | 134,293 -> **134,163** (`.mega` 24,800) | **-130** | conventional 61,952 of 68,096, unchanged |

kern_mega's **conventional sections** (`.text` + `.bss` + `.lowbss` +
`.vgabuf`) are 56,415 -> 56,413 (-2): the *.IMG table's +2 `.text` (item 30)
against the FAT32 scratch alias's -4 `.bss` (item 34). Everything else it
saved is `.cold`, above 1MB. `.lowbss`, `.vgabuf`, `.vga`, `.boot2`, `.ovl`
and every module and driver image are unchanged.

## TAKEN

Per routine, `kern_big` (base `3fc4e9d09` against the tip, both assembled
here): disk_mount_x -30, dsk_docpass -22, dsk_find_x -22, lz_lz4 -17
(+10 lz_l4end), dsk_rah_flush -7, dsk_bpb_check -6, dsk_xfer -6,
dsk_free_clus_x -5, dsk_vol_fixed_x -5, dsk_fatw_pick -4, dsk_read_chain_x -4,
dsk_vol_add -4, dsk_bpb_bank -3, dsk_vol_row_x -3, and 18 routines at -1 or -2;
new: dsk_mquiet +14, lz_l4end +10, dsk_ico_img +9, dsk_img16 +2 `.text`.
"all" = the four kernels.

**THE int 13h BAR.** No item changes an I/O decision, so no operation gains or
loses a call - by construction, read off the code: the read-ahead's gate,
pick, fill and flush answer and write exactly as before (the flush clears the
same records; only its register bank went); the mount reads the same sectors
in the same order (the quiet gate is the same predicate, item 28; the FAT
window's pick reloads in exactly the cases it did, item 31); the chain read
coalesces the same runs and advances by the same bytes (item 13); the BPB
rules accept exactly the same heads (item 18). The disk-3 / disk-5 / disk-4
counts stand as khp1 measured them.

**Parity** (`hotpar`, fast tier): green at every commit on both gated kernels.
Three pads went, each with an odd saving beside it: `dsk_bytes_secs_x`'s nop
(dsk_xfer's entry), kern_small's `%ifndef DSK_PMHD` nop in dsk_xfer's retry
path, and kern_big's nop at disk_mount_x's `.publish`. Inside dsk_xfer the
code between `.success` and the cache gate now sits one byte odd (kern_big;
kern_small from `.success` to its retry path) - a few clocks a run on a 16-bit
bus against the int 13h beside it, none on the 5150's 8088.

### Batch 1 (`b135426f1`): big -28, small -20, emu -28, mega -32

1. **dsk_xfer's BR-16 miss test sits under the hit's jump** (-3 big, emu,
   mega). `jnc .rahhit / cmp / jnb .nocache / jmp .fail / .rahhit: jmp .count`
   became `jc .rahmiss / jmp .count / .rahmiss: cmp / jb .jfail`. A served
   run is 12 clocks faster (a `jc` not taken where a `jnc` was taken); a
   refusal takes `.jfail`'s existing trampoline.
2. **dsk_xfer `.success`'s `clc`** (-1 all): CF is 0 out of `cmp word
   [dsk_bnc_si], 0`. On kern_small the `%ifndef DSK_PMHD` parity nop it
   balanced goes too (-1 small).
3. **dsk_bpb_bank's PUT stores the row before doubling the index** (-2 all):
   no `shr bx, 1` undoes the `add bx, bx`. **GET jumps to the shared `rep
   movsw / ret`** (-1 all; pass 15 wrote it out for parity) and
   **dsk_bytes_secs_x's parity nop goes** (-1 all). A banked mount pays one
   jump.
4. **dsk_vol_add's scan steps before it tests** (-2 big, emu, mega) from a
   row below the first, one jump a row fewer; **its tail is CLC_OR_STC**
   (-2): every caller reads CF alone (osapi_vol_add_x's packages, CLV's
   clo_mount).
5. **dsk_synth_name's `or bx, bx`** (-2 all): `sub bx, cx` already set ZF.
   Per listing entry, faster.
6. **dsk_rah_flush banks nothing** (-7 all): every caller holds neither BX,
   CX nor the flags across it (disk_mount_x's listing arm, dsk_rah_pre's
   failed fill under kretc_bp, dsk_rah_want's and dsk_rah_wanthi's fresh
   claim, CLO_KCALL's cmz_jfresh - "clobbers BX CX, flags" - and HIBER.DRV
   through hbm_cb, where `xor ax, ax` and hbm_psum's own pushes follow). The
   field offset folds into the base. Same records cleared.
7. **dsk_read_chain_x's pop pairs are one** (-2 big, emu, mega): DI = the
   byte count's high word is taken for both arms (the walk sets its own DI;
   FAT32's walk leaves it dead while CX = 0).
8. **dsk_read_chain_x's run advance is `mov ah, cl / shl ah, 1 / mov al, 0`**
   (-2 all): `len * 512 mod 64K` is `(len mod 128) * 512` at any CX, so AH =
   CL*2 is all of it - no push, no `shl ax, cl` (~50 clocks a run faster).
9. **dsk_ico_stage's sentinel test rides the `mov`** (-2 all).
10. **dsk_goto's `.ok` needs no `clc`** (-1 all): the FAT12/16 range test is
    asked `cmp [dsk_maxclus], bx / jb .bad`, which falls on with CF = 0 as
    every other way into `.ok` already does.

### Batch 2 (`5979bb27b`): big -39, small -34

11. **dsk_find_x stores the record in order** (-21 big, small, emu; -17 mega).
    +13..+23 are sequential, so `xchg ax, cx / stosb / movsw / movsw / xchg /
    stosw / xchg ax, dx / stosw / mov al, ch / mov ah, 0 / stosw` off a
    walking DI, which `.out`'s `pop di` hands back; AX and DX ride through,
    so their bank goes. kern_mega's FAR fix-up writes `[es:di-8]` and
    `[es:di-2]`. **A unicorn A/B over base and tip** (3,000 trials a kernel,
    random dsk_ent, sizes, flags, fattype 0/1/2 with the FAR cases forced):
    identical buffer, CF and SP on kern_big, kern_small and kern_mega. AX on
    success is now the flags word where it was the size's low word: the
    contract says AX is clobbered there, the C thunk zeroes it, and no
    kernel caller reads it (desksc, stikmenu, the API cell).
12. **dsk_bpb_check rule 4 as "spc-1 <= 63" with the power test** (-3 all),
    **rule 13's x80 as a byte multiply** (-1 all; AL = spt*heads <= 72),
    **rule 15 as "count-1 < 65524"**, the FAT-type compare asked of count-1
    too (-2 all). **A unicorn A/B over 20,000 BPBs a kernel** (templates of
    every floppy format and four hard-disk layouts, 0-3 fields mutated to
    boundary or random values, vflop 0/1/2, vsecs around TotSec16): 0
    differences in CF, SP or any of the variables the routine writes; 28% of
    the heads pass, so rules 13-16 run.
13. **dsk_free_clus_x's `.counted` is SKIPF1 over `.bad`** (-1 all): every
    caller reads CF alone. SKIPF1 plus an explicit `.bad:` rather than
    CLC_OR_STC, because dsk_fc_bad jumps to `.bad` from outside and
    `tools/stkbalance.py` does not see a label the macro defines (it read
    that jump as a tail call at depth +6).
14. **The FAT12 vetoes reach `.slow` short** (-3 big, emu; -2 small): the
    `.slowj` relays go. kern_mega keeps its (`.f32` sits between).
15. **disk_mount_x `.publish` needs no `clc`** (-1 all): `.quiet` arrives off
    `xor bp, bp` and `.done`'s every way in is a `jae` that took. **kern_dos
    keeps it** (`%ifdef KD_BUILD`): it has no harvest, and its selection
    sort's 0-or-1-entry `jb .sd_out` reaches `.done` with CF = 1. kern_big's
    parity nop there goes with item 14's odd byte (-1 big, emu, mega).
16. **dsk_xfer `.drv` stores the class out of AL** (-2 big, emu, mega), the
    lookup's own register; kern_mega's `push ax` arm moves first.
17. **The kernel segment out of DS** at dsk_copy_in_x, dsk_get_dir_x,
    dsk_put_dir and dsk_docpass's ico_put (-1 each; dsk_docpass is kern_big's):
    SPEC.md 2.6's sanctioned spelling, and on kern_mega the writable alias,
    which spares dsk_copy_seg_x's KDATAR_C.

### Batch 3 (`f979ff046`): big -23, small -14

18. **lz_decomp_big unwinds with `lea sp, [bp+16]`** (+14 on the plain arm)
    (-2 all): `lea` writes no flag, so CF rides through where `lahf / add sp /
    sahf` carried it; BP is the frame on every way to `.fin` (`.out` reads
    it; every arm's exit re-derives it with lz_fsync, and the plain arm never
    moves it). stkbalance reads the `lea` as the `add`. ~8 clocks faster a
    decode.
19. **KHP_LZ's lz_lz4 end path and its own lz_tail sit ABOVE the entry**
    (lz_l4end, -6 big, emu, mega). The per-token `jae .end` was relaxed to
    `jb $+5 / jmp near` - a TAKEN jump on every token that was not the end -
    and is now a short `jae` NOT taken: **~12 clocks a token faster**, on the
    path KHP_LZ was measured for (Note Pad's 1,252 tokens: ~15,000 clocks a
    launch). `jb .fast` is short and the end falls into the tail. The plain
    arm keeps its `.end` and its tail below the loop, where the LZB arm's
    `jmp lz_tail` is two bytes; the tail is written twice and exactly one
    copy assembles (`LZ_TAIL_HERE`, which also covers a KHP_LZ build with no
    LZ4 arm - kernels with `-DLZ_HAVE_LZB` and `-DLZ_HAVE_LZ4` alone were
    assembled to check).
20. **lz_lz4's `.bad` is a bare `ret`** (-1 all): the CF = 0 refusal past the
    tail goes to lz_match's `stc / ret` beside it; every other way in is a
    `jc` or lz_match's fall. **A unicorn A/B over 430 streams** (244 valid,
    LZ4 and LZB, filtered and not, corrupted and short-declared) and 9 over
    32KB (the checkpoint slide): identical output, CF, SP, BP, DS, ES and DI
    on kern_big, kern_small and kern_mega.
21. **dsk_bpb_zap clears a row with CH** (-1 all), 0 for the whole loop.
22. **dsk_vol_row_x answers a free row through dsk_vol_slot_x's own refusal**
    (-3 all) and **dsk_vol_fixed_x asks dsk_vol_row_x** (-5 all). On CF = 1
    AH is no longer 0FFh for a free row; the contract makes AX the output on
    CF = 0 only, and dskw's WSQF_KEEP site stores AL, which neither version
    touched before the refusal.
23. **Four shared pop runs**: dsk_rah_want into dsk_bpb_zap's (-2 all),
    ico_need into dsk_fatw_drop's (-1 big), ico_key_stem into dsk_ncopy's
    (-1 big), dsk_find_x into dsk_path_x's `retf` (-1 big). Each is the same
    return kind (SPEC.md 2.6.1.1) and the same depth; a jump each, on per-
    mount or per-icon paths.

### Batch 4 (`505f740e2`): big -19, small -7

24. **The *.IMG icon through dsk_ico_stage's run decoder** (-10 big, emu,
    mega: `.cold` -12, `.text` +2). dsk_docpass's 24-byte inline decoder
    becomes `call dsk_ico_img`, a 9-byte entry with dsk_ico_stage's frame;
    dsk_img16 is re-laid in dsk_folder_ico's (count, word) shape, which needs
    a zero count, and its `align 2` (kept for the `.text` routines after it,
    the door among them) turns that byte into two. The rows decoded are the
    same seven runs.
25. **LOW_SEG out of SS** at dsk_copy_in_x and the harvest's ico_put (-1
    each, all): SPEC.md 2.1, and kern_dos sets SS = LOW_SEG at both entries.
26. **dsk_fatw_pick drops its "nothing banked" test** (-4 all): [dsk_sigcur]
    is never 0 at a mount - dsk_bpb_sig's `inc` on a zero sum, and its only
    other writer is the bank's GET, from a row only a PUT of a signed mount
    filled - so a 0 is "a different disk" to the compare already.
27. **dsk_fatw_demote: AX = BX - MEM_P_FATW as one `lea`** (-1 all).
28. **dsk_media_ok's IMG arm needs no `xor bh, bh`** (-2 big, emu, mega):
    dsk_vol_rmv answers CF = 1 only for BX = kind:unit below 80h (BH 0) or
    its orphan's 0FFFFh, which `cmp bl, 4` refuses.

### Batch 5 (`d7b8df9cc`) and 6 (`52078d627`, `e4183d4dd`): big -20, small -6

29. **dsk_mquiet** (-13 big, emu, mega; -4 small): "[dsk_quiet] raised, or no
    listing to write" as CF, for disk_mount_x's three spelt-out copies (the
    read-ahead's listing cap, 2b, the redirected arm's 2b): 14 bytes a site,
    5 as a call, a 14-byte body. Same predicate, a call a mount.
30. **dsk_synth_x loads CL alone** (-1 all): both of dsk_synth_name's exits
    are a `loop` run out. **dsk_up_open stores the parent link's type as a
    byte** over dsk_ent_zero's zero (-1 all).
31. **dsk_free_clus_x's redirected arm saturates with `neg / sbb / or`** (-1
    big, emu, mega): DX is dead, popped by the shared six.
32. **dsk_vol_drop_drv_x's `jc` is dead** (-2 big, emu, mega): the index runs
    2..DVOL_MAX-1 and dsk_vol_slot_x refuses only DVOL_MAX and up.
33. **osapi_vol_mount_x puts the index in DL once** (-2 big, emu, mega), for
    dsk_vol_row_dl's lookup and the mount both.
34. **kern_mega: dsk_fcih/dsk_fcnh share dsk_rcsh/dsk_rcdh** (-4 `.bss`,
    kern_mega alone). Each routine writes the words before reading them and
    reads none past its return; dsk_free_clus_x walks the FAT window and
    dsk_read_chain_x goes through dsk_xfer, which calls neither, so neither
    reaches the other; and file operations are the UI task's alone (SPEC.md
    20.6 rule 7), so two cannot interleave.

## REFUSED / NOT TAKEN

* **`dsk_quiet` and `dsk_keepcwd` by `inc` / `dec`** (-4): equal while the
  byte starts at 0, but a mount that never returns (its task closed mid-mount
  between transfers) would leave the byte raised for ever, where the `mov 1`
  of the next dsk_chdir_q_x heals it now.
* **dsk_fat_ofs_x's `.bad` tail as CLC_OR_STC** (-1) and **dsk_next_clus_x's
  `.bad` folded over the FAT16 load** (-1): each puts a `test` on the
  per-cluster path (dsk_next_clus_x is pinned hot) - the speed rule.
* **dsk_ent_zero by `and word [di], 0`** (-1): +11 clocks a word, 176 a
  listing entry. Kept in hand as a parity byte and not needed.
* **`.drvcut`'s x32 as `mov ah, 32 / mul ah`** (-2): `.dcnall` hands back the
  whole count when the buffer is page-aligned, so AX can pass 255.
* **dsk_xfer re-testing PicoMEM's unit from DL after int 13h** (-3): it
  assumes the BIOS kept DL, which the code deliberately does not.
* **dsk_batch_end_x as `sub / adc / clc`** (0 net), **lz_lzb's `.bad` as a
  bare `ret` behind a `cmc`** (0 net), **dsk_dscan's `.take` as CLC_OR_STC**
  (0 net), **dsk_path_x's `.fail` as CLC_OR_STC** (-1: OSAPI_FILE_PATH is a
  package's, and its success would answer a different ZF - not proved
  unread).
* **dsk_rah_reloc and ico_reloc as one proc** (-1, kern_mega): each exists
  because its word can hold a pool SELECTOR that must not be compared with
  another claim's base; one proc compares both words on every move.
* **dsk_img16's terminator overlapped with a neighbour** (-1 `.text`): no
  constant zero byte follows any place the table could sit.
* Pass 20's REFUSED items in these files still hold and were not re-proposed
  (`dsk_rah_cap` as min(AL, RUNS), `dsk_bpb_bank_zap`'s AX, the fallback 9/2
  geometry as a helper, `dskw_read_at_x`'s answers above its entry); pass 19's
  "lz.inc not edited" no longer holds - items 18-20 make KHP_LZ's bodies
  smaller and the per-token path faster, its checks untouched.

## WANTS THE OWNER

None. No behaviour changed; every refusal answers as it did. Registers that
differ, all documented as clobbered at the point they differ: dsk_find_x's AX
on success (item 11), dsk_vol_fixed_x's AH on CF = 1 for a free row (item 22).

## WANTS AN ABI BREAK

None.

## CROSS-FILE

* **READ_SEQ (#387) is `dwf_dskw_read_seq` in `kernel/diskw.inc`** (the
  diskw agent's), not in disk.inc; dsk_xfer's +28 since pass 20 was the
  medium re-check (`[dsk_mvok]`, 4) and BR-16's cache gate (14) and 06h retry
  (7), and is now 6 smaller (items 1, 2, 16).
* **`tools/stkbalance.py` does not see a label that CLC_OR_STC defines**: a
  jump into it from outside the routine reads as a tail call (item 13's
  first spelling went red that way). Anyone using CLC_OR_STC as a shared
  refusal for an outside jump wants SKIPF1 and a written label.
* **`hiber.inc` calls dsk_rah_flush through hbm_cb** and now gets BX, CX and
  the flags back clobbered (item 6); nothing there reads them, but the sys
  agent owns that file.
* **disk.inc's parity window is shared**: `.cold` bytes saved in memory.inc,
  mod.inc, assoc.inc or anything else ahead of `lz.inc` move dsk_xfer,
  dsk_runcap and dsk_next_clus_x; this branch is even on its own, and a merge
  with an odd saving ahead of them needs a pad or a partner.

## ROWS NAMED (none run - the coordinator's union)

* dsk_xfer, the read-ahead, the chain read (1, 2, 6-8, 16, 29): `dirwsize`,
  `dirwshed`, `ldcost`, `dosbar`, `xtmp3eng`, `small128`, `smalllaunch`,
  `kdcylrun`, `megashed`, `megarsq`, `hdbounce`, `drvcut`, `dskwstage`,
  `fcpcopy`, `vidkeyclus`, `fdswap` (BR-16 and the swap detector), `picomem`.
* The mount, the BPB, the bank (3, 12, 15, 21, 25-27, 29, 30): `rdmount`,
  `imgmount`, `fatwpin`, `hdauto`, `bigvol`, `fat32`, `fat32big`, `volsig`,
  `mediadisk`, `kerndos`, `kdos`, `kdhdd`, `hibernate`, `megahiber`.
* The volume table (4, 22, 32, 33): `rdmount`, `imgmount`, `imgswap`,
  `hdauto`, `wirezone`, `megahddtick`, `fmrefuse`, `httpmount`.
* FIND, the listing, the path (5, 11, 23): `stiknote`, `stiknotesmall`,
  `thewire`, `assocfind`, `pathcost`, `dosdirsw`, `dosopen`, `bigdir`,
  `rdcz`, `win16file`.
* The free count (13, 14, 31, 34): `sysfree`, `fcproom`, `dosdirsw`, `fat32`.
* The LZ decoder (18-20): `lzship`, `lzship-lzb`, `lzfence`, `lzcomp`,
  `lzdrv`, `lzdrv-nohint`, `pkgrun`, `rehome`, `rehomeabort`, `megarehome`,
  `czto`, `czjoin`, `smalllaunch`, `ldcost`.
* Icons, goto, media (9, 10, 17, 24, 28): `icoclip`, `icoshed`, `rdicon`,
  `imgmount` (the *.IMG icon), `assocsweep`, `dosmedia`, `czto`.

Host checks at every batch: `make -j2` (fast tier 54 passed, `hotpar` and
`stkbalance` among them), `make -j2 small`, `tools/stkbalance.py` over every
kernel source (0 unbalanced; disk.inc alone 5 cross-file findings at base and
tip both), `checkdocs`. At the tip: `make -j2 small emu mega` green. The
unicorn harnesses (dsk_find_x's record, dsk_bpb_check, lz_decomp_x) ran the
base's and the tip's own assembled bytes; no emulator was booted.

## DEFECTS FOUND

* **dsk_find_x on a redirected volume reports a garbage flags word past
  ordinal 254** (kern_big, emu, mega; not fixed). On the DSK_DSCAN build the
  `.stage` arm (FSV_ENUM's answer) loads CL with the attribute and leaves CH
  as dsk_dscan's returned CX - the next slot - so +22 is `(slot+1) >> 8`:
  bit 0, OSAPI_FIND_CZ ("compressed"), set for entries 255..510 of a RAM disk
  or cable folder, and bit 1, OSAPI_FIND_FAR, from 511. Found by reading item
  11's ways in;
  the tip keeps the old bytes exactly. The fix is `mov ch, 0` at `.stage`,
  +2 bytes, and is the owner's or the file's next pass's to take.
