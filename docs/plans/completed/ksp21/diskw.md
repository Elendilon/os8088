# ksp21 agent "diskw" - the directory mutations, the FAT write path, the loader

Kernel size pass 21 (`docs/plans/completed/ksp21/BRIEF.md`, row `diskw`): `diskw.inc`,
`diskmut.inc`, `diskops.inc`, `loader.inc`, `compress.inc`, `ascw.inc`.
Branch `ksp21-diskw`, base `3fc4e9d09` (the brief). Figures are ASSEMBLED,
`tools/kernsize.py --json` absolutes on each kernel's own build, and
`tools/os88rdiff.py kernel 3fc4e9d09 .` (with `-D KERN_SMALL`, `-D KERN_BIG
-D KERN_EMU`, `-D KERN_BIG -D KERN_MEGA`) per routine. Resident = `.text` +
`.bss` + `.cold` + `.lowbss` + `.vgabuf` + `.vga` (+ `.mega`).

Of the six files only `diskw.inc` (5.0KB of kern_big's `.cold`), `loader.inc`
(1.3KB) and three `clo_*` thunks of `diskops.inc` are resident; `diskmut.inc`
and `compress.inc` are DISKOPS.DRV's image and `ascw.inc` is FORMAT.DRV's.
**TAKEN outside the row**: one line of `tests/dskwstage.py`, which borrows
`dskw_rt_name` as a name buffer and now asserts its eleven bytes. `SPEC.md`
18.5.3 and 96.44.8 move with the internals they describe.

**The finding.** `7f08a100b` put Rename, New Folder and the empty rmdir back
in the kernel as the bodies they had been before #396 - and those bodies were
still SHAPED for the tree that used to share them. `dskw_fdir`, `dskw_isempty`
and `dskw_scan1` had one caller each left, and the scan's wrapper banked five
registers for a caller whose ladder restores all seven. `dskw_dircall` was a
second seven-push ladder that called `dskw_wck` back with a body inside
itself. The rename held an 11-byte copy of a name whose pointer a free
register could hold. The rest is the usual three shapes: banks no caller reads
(`dskw_alloc`, `dskw_now`, kern_small's `dskw_stat_x` and `dskw_read_at_x`),
state spent where it is read (`[dskw_isdir]`), and arithmetic in the unit the
next step wants (the loader's clear prefix, in paragraphs).

## BASE AND TIP

| kernel | base `3fc4e9d09` | tip | delta | where |
|---|---:|---:|---:|---|
| **kern_big** | 90,225 | **90,067** | **-158** | `.cold` 37,830 -> 37,684 (-146), `.bss` 4,973 -> 4,961 (-12), `.text` 39,510 unchanged; `KERN_SIZE` 95,744 -> 95,232 (accrued 113 at the base) |
| **kern_small** | 55,672 | **55,594** | **-78** | `.cold` 20,860 -> 20,794 (-66), `.bss` 2,843 -> 2,831 (-12), `.text` 29,101 unchanged |
| kern_emu | 90,471 | **90,313** | **-158** | as kern_big |
| kern_mega (`.mega` 24,800) | 134,293 | **134,106** | **-187** | `.cold` 53,078 -> 52,903 (-175, above 1MB), `.bss` 5,204 -> 5,192 (-12); conventional `MEGA_RESIDENT` -12 (the 61,952 rung unchanged); `.mega` unchanged |

`.text`, `.lowbss`, `.vgabuf`, `.vga`, `.boot2` and `.ovl` are unchanged on
all four. `.bss` moves by -12, an EVEN amount, on every kernel, so every
`.bss` word after `diskw.inc`'s keeps its parity (item 13 is the byte that
pairs item 4's eleven). DISKOPS.DRV (`.modl`): kern_small 8,020 -> 8,003 (-17, item 14; not resident); kern_big's, kern_emu's and kern_mega's unchanged. FORMAT.DRV and every other module image unchanged. The one package that
assembles these files, kern_dos's `DOS.O88` (`kerndos/` includes `diskw.inc`),
is smaller with them: 55,923 -> 55,843 bytes on the disk against the
coordinator tree's build. No ABI moved:
`apps/os88api.inc`, `drivers/os88drv.inc`, `apps/cc/` and
`tools/abi.lock.json` are untouched.

## TAKEN

Bytes are big / small / emu / mega, read off `os88rdiff` per routine. Every
item is H4 (per write, per directory operation, per launch) or colder; none is
on khp1's H1/H2 lists, and `hotpar` (fast tier) is green at every commit - no
pinned routine moved (`dsk_xfer`, `dsk_runcap` and `dsk_next_clus_x` sit
before `diskw.inc` in `.cold`; the shift past the last changed routine is
even on every kernel).

### Batch 1 (`c7a242fd0`) - the three bodies `7f08a100b` brought back, and their door

1. **`dskw_wck` banks AX and DX once for every arm** (-18 / 0 / -18 / -18).
   The gate and `[dsk_mvok]` are one word read (`dsk_mntok` and `dsk_mvok`
   are adjacent - `.publish` sets them with one store - and an `%error` now
   says so); DL is loaded once and rides `dsk_media_ok`, which keeps every
   register; the quiet mount is `call dsk_chdir_q_x.go`, disk.inc's own
   `[dsk_quiet]` bracket round `dsk_chdir_x`, where it was spelled out. The
   decisions are the old ones, in the old order. Cycles: the common case (a
   write with the motor running, `[dsk_mvok]` = 1) is ~+21 clocks for the
   extra push/pop pair, ~4 us against the write's >= 400 ms of int 13h.
2. **The tree's dispatch is a `dskw_wrap7` body** (-32 / -5 / -32 / -32).
   `dskw_dircall` had its own seven pushes and called `dskw_wck` back with a
   label inside itself as the body; `dskw_dirbody` is wrap7's body like any
   resident write body's, `dskw_rmtree` sits in wrap7's short reach and
   `dwf_dskw_rmany` picks between the two bodies with a `mov` under ZF. The
   gate is tested INSIDE the body, after `dskw_wck` - which passes a shut
   gate straight through with no I/O, and whose quiet mount either opens the
   gate again or refuses - so it is still tested before anything loads, and
   its refusal is `dskw_wck`'s own `FERR_NODISK` tail. On every kernel the
   load's `FERR_IO` is loaded before the `jc` (no DISKOPS verb reads AX:
   `clo_disp_x` dispatches on DL) and the hold test is `shr bp, 1` (-2, -2:
   kern_small's five).
3. **`dskw_rmbody_n83` is one body** (-35 / -1 / -35 / -43: kern_mega's `CLU_LD` is six bytes more). `dskw_fdir`,
   `dskw_isempty` and `dskw_scan1` were its single-caller helpers once the
   tree went into DISKOPS.DRV, and they are written in: the scan's bank of
   five (the caller's `dskw_wrap7` restores all seven, and nothing after the
   scan reads one), the `CLU_LD` of a cluster still in AX:`[dsk_ch]`
   (`dskw_clok` keeps both), the LBA `xchg` only `dskw_rt_scan` wanted, and
   the `jnc dskw_relold` / `ret` (relold follows now; the refusals take
   `dskw_dotents`' `ret`). `dskw_isempty` is left as the pop tail drvvol.inc
   shares (`STKBALANCE-OK`, the reason on the line). kern_small keeps only the
   relold fall-in: its tree and empty rmdir are DISKOPS.DRV's.
4. **`dskw_nbody` holds the new name's pointer in BX** (-14 `.cold`, -11
   `.bss` / -2, then -11 `.bss` in batch 3 / as big / as big). It parses the
   new name, proves it free, finds the old one, and parses the new name a
   SECOND time out of BX straight into the staged entry's 11 name bytes,
   where it copied it to `dskw_n83b` and back. BX survives `dskw_find`,
   `dskw_gate83` and `dskw_imgro`. Its `stc`/`ret` is `.badarg`'s, which
   `dskw_size32`'s `jnz dskw_nbody.out` shares (-2 every kernel). Cycles: one
   `dskw_name83` (~600 clocks) for two `dskw_copy11`s (~500): neutral, on a
   rename.
5. **`dskw_commit` spends `[dskw_isdir]` at its last read** (-11 / -8 / -11
   / -16). `xchg al, [dskw_isdir]` with AL = 0 leaves the flag clear on every
   way out of the commit, so `dskw_mkbody` neither clears it after the call
   nor on `.rollax`, whose bank of AX and `stc` kept nothing (`dskw_refat`
   keeps every register and flag, and every way into `.rollax` arrives with
   CF = 1). kern_small keeps the `cmp` (its New Folder is the module's, which
   clears the flag itself) and takes `.rollax`'s -8; kern_mega's `.czgo`
   `xor ax, ax` re-zeroed a register nothing had spent (-2), and there
   `dskw_dirgrow`'s jump to `dskw_mkbody.dirfull` came into short reach, NASM
   relaxing it once `dskw_mkbody` shrank (-3).

### Batch 2 (`e77e39b11`) - the loader, and banks nobody reads

6. **`ld_run_body_x` counts the clear prefix in PARAGRAPHS** (-5 all): the
   association block and the glyph are an `inc` each, the card
   `LD_STIK_SIZE / 16`, and one `shl` makes the byte count the copy and the
   two lengths want. An `%error` says every block is a multiple of 16.
   `t_stikcard` still finds its ladder (`add bx, LD_STIK_SIZE ...`).
7. **`ld_alloc`'s `clc`** (-1 all): `shl ax, cl` of a paragraph count
   (<= 0FFFh, a 16-bit byte count shifted down 4) shifts out bit 12, a 0.
8. **`ld_take`'s `clc`** (-1 all): the range test turned round,
   `dskw_clok`'s way, so the `jb` not taken IS CF = 0 (the REDIR `je` and the
   FAT32 `jc` already were).
9. **`dskw_alloc` banks nothing** (-11 / -11 / -11 / -14). Its two callers
   spend BX, CX, DX, DI and ES on every path after it: `dskw_mkclus` says so
   in its header, and `dskw_wdata`'s walk (`dskw_xclus`, `dskw_one`) writes
   each before it reads it, round the per-cluster loop too. Its exits are
   `ret`s; kern_mega's FAT32 arm is a tail jump to `dskw_alloc32`. Faster.
10. **`dskw_now` banks nothing** (-5 all): `dskw_dotents` and `dskw_commit`
    load AX, BX and CX before reading them, and FSCK.DRV's lost-chain save
    (`KC dskw_now`) reloads AX, pops CX, and holds a spent digit index in BX.
    ES is still kept (`dskw_dotents` relies on it).
11. **`dwf_dskw_read_seq` without the run** (-2 / 0 / -2 / -2): a cursor
    without `FSEQF_RUN` gets its own +10..+15 copied over the run's six bytes
    (`sub si, 6`, inside the 16 it is known to have) instead of a jump and
    `add di, 6`. Nothing reads +16..+21 without the flag: `.norun` zeroes +18
    and `dsk_next_clus_x` answers nothing off a 0 there; +20 is read only
    under the flag.
12. **`dskw_mkdir_x` sits in `dskw_wrap7`'s short reach** (-1 / 0 / -1 / -1).

### Batch 3 (`f1df2362c`) - kern_small's door, and the `.bss` pair

13. **`dskw_rt_name` is eleven bytes** (-1 `.bss` all): its twelfth kept it
    even-sized for a bus this target has not got. With item 4's eleven that
    is twelve, which keeps every `.bss` word after them at its parity.
    `tests/dskwstage.py` borrows the buffer for a name and asserts 11.
14. **kern_small's `dmo_nbody` holds the pointer in BX too** (-11 `.bss`
    small; DISKOPS.DRV -17): `dskw_n83b` goes on every kernel (`wm_cbd` keeps
    BX).
15. **kern_small's four verbs are ONE `dskw_wrap7` body, `dskw_dirb`** (-10
    small). wrap7's `call ax` leaves AX = the entry, so the body is entered at
    the verb's own byte: three `nop`s, `sub ax, dskw_dirb - CLV_MKDIR` and
    `xchg dx, ax` make DL the CLV_* (diskops.inc asserts the four
    consecutive). `dskw_dircall`'s own seven pushes and the four `mov ax,
    CLV_*` / `jmp` stubs go; Rename falls into wrap7, New Folder and the tree
    reach it short. The two arms of the four stubs and `dwf_dskw_rmany` are
    one source through `DSKW_B_*`. **Stack: the verb runs one return
    address deeper (+2 bytes) than `dskw_dircall` ran it**, on the UI task's
    512-byte stack (`tests/stk0water.py` reads 238 of it, though not on this
    path). Worth the coordinator's eye: `fcpsmall` (a folder Copy and Cut on
    kern_small, so `dskw_dirb`'s New Folder and tree) is the row that runs
    it; no row runs kern_small's Rename - `diskmut` is kern_big's, and its
    "succeeds with DISKOPS.DRV absent" legs would refuse by design there.

### Batch 4 (`06ed5de5d`)

16. **`dskw_dotents` stores both clusters in the run** (-6 all): '.'s with
    the `stosw` run that writes its entry, then 26 bytes (13 words, up to the
    cluster) copied to '..', whose cluster is stored where that copy leaves
    DI. The sector is the same 512 bytes. `%error` extended to `DSK_R_CLUS`.
17. **`loader_run_x` compares the poster's folder in BX** (-3 all): DL is
    still its drive at `.move`, so the reload goes. BX is the KENT frame's.
18. **kern_mega crumbs** (-13 mega): `dskw_flush_x`'s FAT32 arm pops DI once
    and falls into `.done` (the FAT2 test is `cmp [dsk_nfats], 1 / je`, mount
    rule 6 being "1 or 2", and the equal compare is CF = 0; -5); `ld_start`'s
    re-home turns the keep into bytes through AX, which `ld_hisi` reloads
    before reading (-2; AX at the re-homed entry proc is garbage either way -
    no entry contract names it); six `mov word [m], 0` whose flags nobody
    reads are `and` (`dskw_alloc` x2, `dskw_read_at_x`, `dskw_czexp.bad`,
    `dskw_subsrc`, `ld_pkg_byname`; -6).

### Batch 5 (`8f193805b`)

19. **kern_small's `dskw_stat_x` banks SI only for the driver** (-2 small):
    `push si` is for the REDIR arm's `FSV_STAT`, which may spend every
    register; the FAT arm's `dskw_name83n` and `dskw_find` keep SI.
20. **kern_small's `dskw_read_at_x` banks DI and BP only where they are
    written** (-4 small): DI is the hot cursor's links (DSK_STREAM) and BP the
    driver's verb (OS88_REDIR); with neither, `dskw_stat_x`,
    `dsk_next_clus_x` and `dsk_read_chain_x` keep both. kern_dos keeps DI
    (DSK_STREAM) and loses BP's pair.
21. **`dskw_append_x` stores its `-1` before the ladder** (-1 / -2 / -1 /
    -1): `or word [dwr_off+2], -1` ahead of the shared three pushes, which
    now bank the caller's DX in both doors.

**Per routine, kern_big** (`os88rdiff kernel 3fc4e9d09 .`):

| routine | base | tip | delta |
|---|---:|---:|---:|
| `dskw_wck` | 78 | 60 | -18 |
| `dskw_dircall` -> `dskw_dirbody` | 67 | 40 | -27 |
| `dskw_rmtree` | 6 | 5 | -1 |
| `dwf_dskw_rmany` | 18 | 14 | -4 |
| `dskw_mkdir_x` | 6 | 5 | -1 |
| `dskw_mkbody` (with its shared tails) | 93 | 80 | -13 |
| `dskw_commit` | 172 | 174 | +2 |
| `dskw_dotents` | 75 | 69 | -6 |
| `dskw_rmbody_n83` + `dskw_fdir` + `dskw_isempty` + `dskw_scan1` | 142 | 107 | -35 |
| `dskw_nbody` | 88 | 74 | -14 |
| `dwf_dskw_read_seq` | 232 | 230 | -2 |
| `dskw_append_x` + `dskw_write_at_x` + `dskw_wat` | 26 | 25 | -1 |
| `dskw_alloc` | 139 | 128 | -11 |
| `dskw_now` | 68 | 63 | -5 |
| `loader_run_x` | 80 | 77 | -3 |
| `ld_take` | 52 | 51 | -1 |
| `ld_run_body_x` | 201 | 196 | -5 |
| `ld_alloc` | 103 | 102 | -1 |
| **`.cold`** | | | **-146** |
| `dskw_n83b`, `dskw_rt_name`'s 12th byte | 12 | 0 | **`.bss` -12** |

kern_small's per routine (`-D KERN_SMALL`): `dskw_dircall` 60 -> `dskw_dirb`
50, `dskw_rename_x` 6 -> 3, `dskw_mkdir_x` and `dskw_rmtree` 6 -> 5 each,
`dskw_mkbody`'s tails 31 -> 23, `dskw_rmbody_n83` 16 -> 15, `dskw_nbody` 7
-> 5, `dskw_stat_x` 46 -> 44, `dskw_read_at_x` 181 -> 177, append 18 -> 16,
`dskw_alloc` 139 -> 128, `dskw_now` 68 -> 63, `dskw_dotents` 75 -> 69, and the
loader's four as kern_big's: `.cold` -66, `.bss` -12.

## THE int 13h BAR

No item changes an I/O decision, so no operation gains or loses a call. By
scenario, read off the code:

| scenario | before | after | why |
|---|---|---|---|
| a write (any body through `dskw_wck`), floppy motor running, no unchecked transfer since the mount | 0 extra | 0 extra | the same three tests answer "go" |
| the same with the motor stopped, or `[dsk_mvok]` = 0 | one quiet mount (LBA 0; the FAT window kept on a matching signature) | the same mount | `dsk_chdir_q_x.go` IS the three instructions it replaces |
| the tree (`OSAPI_FILE_RMDIR` AL=1) on a shut gate | 0, `FERR_NODISK` | 0, `FERR_NODISK` | `dskw_wck` passes a shut gate with no I/O; the body refuses before the load |
| the tree on an open gate | wck, then DISKOPS.DRV's load (or the kept image) | the same, in the same order | |
| empty rmdir | find + one read per folder sector + the entry write + the FAT flush | the same | the scan's walk is `dskw_scan1`'s, written in |
| Rename | two finds + the entry write + the flush | the same | the second parse is CPU only |
| New Folder | find (+ grow) + the cluster's `spc` writes + flush + entry + flush | the same | the dot sector holds the same bytes |
| a launch (`loader_run_x`, `ld_run_body_x`) | khp1 disk-4's counts | the same | `dsk_chdir_q_x` gets the same DL and AX; step 6a is arithmetic |
| kern_mega FAT32 flush | FAT1, then FAT2 when NumFATs = 2 | the same | |

## REFUSED / NOT TAKEN

* **`dskw_rt_*` out of resident `.bss`** (22 bytes every kernel, 28 on
  kern_mega): the cells are DISKOPS.DRV's tree's alone now, but
  `dskw_rt_name` is handed to `dskw_name83`/`dskw_copy11` through DS, so it
  cannot be the module's (CS) scratch, and the other ten would need CSDO on
  kern_mega. Overlaying them on another lifetime fails the proof: the tree
  mounts (`dsk_chdir_x`) and a mount may read ASSOC.DAT through
  `dskw_read_x`, which spends the transfer cells; kern_mega's `dwr_sh*`
  survive between calls. Not taken.
* **`dskw_wck` through `dsk_chdir_q_x`'s full entry** (about -5 more): on
  kern_mega q_x compares `[dsk_ch]` with `[dsk_cwd+2]`, and with a stale
  `[dsk_ch]` it would add a mount - an int 13h call - to a FAT32 write.
* **`dskw_mounted` as `dskw_dirbody`'s gate** (-4): it runs `dws_gate` (a
  held stream's commit, disk writes) before the module load rather than
  after it, which moves I/O on a load the module then refuses.
* **kern_small's verbs through `dskw_wrap7` before item 15's form**: a
  `mov dl, CLV_*` at each stub would be pushed by wrap7 and come back as the
  caller's DX - a broken contract. The entry-byte body is what makes it free.
* **`ld_say_status`'s `[ld_said]` as `shr` / `jnc`** (-6): the flags it
  leaves change on the said path (CF 1, ZF 1 for CF 0, ZF 0), and
  `stm_a_launch` returns them through `drv_vol_back` to its action
  dispatcher. Not proved harmless.
* **`dskw_read_x` and `dskw_wrp` sharing their prologue** (12 bytes in
  common): DX is `dskw_read_x`'s output, so its pops differ.
* **`ld_res_name` written into `ld_run_name_x`**: 0 net.
* **`dskw_rmbody_n83`'s `.prot` trampoline straight to `dskw_wbody.prot`**:
  133+ bytes, out of short reach.
* **`dskw_runadd`'s `.done: clc`** (-1): CF = 0 at the `jcxz` entry is true
  on every path I read, but one (`.stg`'s `add word [dskw_wseg], 32`) rests
  on no segment past 0FFE0h, which the HMA arm would need proving.
* Still refused for their old reasons: `ld_unreserve`'s `mov word [ld_base],
  0` (pass 19: flags reach a caller); `mod_needi` (pass 18).

## WANTS THE OWNER

None. Every refusal, message and limit is as it was.

## WANTS AN ABI BREAK

None.

## CROSS-FILE

* **disk.inc (disk)**: `dskw_wck` now calls `dsk_chdir_q_x.go` - the
  `[dsk_quiet] = 1 / dsk_chdir_x / [dsk_quiet] = 0` arm of `dsk_chdir_q_x`.
  Keep `.go` exactly that, or a write's media check changes. (An `equ` or a
  rename fails the build; a change of body would not.)
* **fsck.inc (disk)**: `KC dskw_now` now clobbers AX, BX and CX (item 10);
  `fsk_save` reloads AX, pops CX and holds only a spent digit index in BX -
  read through before taking it.
* **drvvol.inc (disk)**: `jmp dskw_isempty.out` still lands on `pop es /
  jmp dskw_find.psi`, its five pops.
* **mod.inc (sys)**: `clo_need`, `dskw_fmt_load` and `fm_fmt_drop` are three
  copies of `push ax / mov al, ID / call mod_need|mod_drop / pop ax / ret`
  (8 bytes each); pass 18's `mod_needi` refusal still prices a shared form.

## ROWS (named, not run)

* The directory mutations and their door (items 1-5, 12-16, 21):
  `diskmut`, `imgswap` (a swapped floppy under New Folder: `dskw_wck`),
  `appdata` (writes with the motor let stop, sectors counted: `dskw_wck`'s
  quiet mount), `dosfcbwr`, `dosfcb`, `dosfcbio`, `dosdir`, `dosdirsw`,
  `dosmedia`, `fdswap`, `stikswap`, `stiknote`, `stiknotevga`,
  `stiknotesmall` (BR-60's growth: `dskw_alloc`, `dskw_dirgrow`), `fcpcopy`,
  `fcpapi`, `fcpsmall`, `fcproom`, `hddcp`, `pxfolder`, `win16file` (skips
  without its fixtures), `imgmount`, `rdmount`, `dskwstage`.
* The write path (9, 10, 21): `wseq`, `wseqheld`, `wsequnclosed`,
  `wseqinter`, `wseqdeleted`, `wseqcut`, `wseqioerr`, `wseqfull`, `viddisk`,
  `viddiskfd`, `dirwsize`, `dirwshed`, `cpnameshdd`.
* READ_SEQ and READ_AT (11, 20): `xtmp3eng`, `xtmp3xt`, `dosbar`,
  `thewire`, `kdhdd`, `kdcylrun`.
* The loader (6-8, 17, 18): `pkgrun`, `pkgbig`, `rehome`, `rehomemove`,
  `rehomemove360`, `rehomeabort`, `megarehome`, `smalllaunch`, `ldcost`,
  `lzship`, `lzship-lzb`, `navcalls`.
* kern_mega's FAT32 flush and crumbs (18): `fsckmega`, `megacurdisk`,
  `megahddtick`.
* FSCK.DRV's `dskw_now` (10): `fsckdisk`, `fsckhd`.
* The loader's prefix ladder's source reader (6): `stikcard` (soak; it
  still finds `add bx, LD_STIK_SIZE` after `test al, LD_HF_STIK`).
* full: `small128`. fast (green at every commit): `hotpar`, `stkbalance`
  and the rest of the tier.

Host checks at every batch: `make -j2` (the fast tier), `make -j2 small`;
`make emu` and `make mega` at batches 4 and 5; `tools/stkbalance.py` over the
kernel sources (0 unbalanced, base and tip); `checkdocs`.

## DEFECTS FOUND

* **Latent, kern_mega, not fixed (no behaviour change taken)**: `dskw_wck`'s
  quiet mount loads AX = `[dsk_cwd]` alone, and `dsk_chdir_x` stores
  AX:`[dsk_ch]` back as the folder, so on a FAT32 volume a stale `[dsk_ch]`
  would re-stand in the wrong folder. Unreachable as far as I can see: the
  check runs only for a medium `dsk_media_ok` calls removable, and FAT32
  (>= 65,525 clusters) is never on one. `CLU_LD dsk_cwd` there would be +6 on
  kern_mega; recorded for the owner rather than built.
* `tests/dskwstage.py`'s docstring still says diskw.inc holds
  `dskw_rt_name`'s three references; they are DISKOPS.DRV's (diskmut.inc).
