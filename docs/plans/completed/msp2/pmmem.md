# msp2 agent "pmmem" - the pool's tables, and what only protected mode reads

kern_mega size pass 2 (BRIEF.md), agent **pmmem**: `kernel/mega.inc` lines
8036-end at the base `ead16c61`, and every `mx_tab`/`MX_*` access site in any
file. Branch `msp2-pmmem`. The headline was msp1/pmmem.md DEFERRED 3: the
1,184 bytes of `.lowbss` - `mx_tab` (960), `mega_wtab` (128), `mem_sel` (64),
`mega_ustab` (32) - that only protected mode reads and that every kern_mega
machine carries in conventional memory for ever, a refused one included.

**What landed is the MECHANISM and the two tables it could carry provably
this round** (`mega_wtab`, `mega_ustab`: 160 bytes). `mx_tab` and `mem_sel`
are written up below to the site, with what stops each; neither is a design
question any more, only a matter of who may edit which lines and which test
harnesses read the old address.

## BASE AND TIP

`tools/kernsize.py --build build/megak --json`, base `ead16c61` (equal to
`/tmp/msp2/base-mega.json` in every field) against the tip of `msp2-pmmem`:

| kern_mega | `.text` | `.bss` | `.cold` | `.lowbss` | `.vgabuf` | `.mega` (+scratch) | `.boot2` | `.ovl` | `KERN_SIZE` at boot | resident after the switch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 46,579 | 5,427 | 46,165 | 6,751 | 336 | 21,440 (+1,490) | 6,709 | 5,118 | 134,656 | 65,024 |
| tip | 46,579 | 5,427 | 46,165 | 6,591 | 336 | 21,472 (+1,490) | 6,709 | 5,118 | 134,144 | 64,512 |
| delta | 0 | 0 | 0 | **-160** | 0 | **+32** | 0 | 0 | **-512** | **-512** |

* **Conventional memory for ever** (`.text` + `.bss` + `.lowbss` +
  `.vgabuf`): **59,093 -> 58,933, -160 bytes.** `.lowbss` is not in the 64KB
  window, so `os88megaseg`'s overhead (3,627) does not move.
* **Above 1MB**: `.mega` **+32**. The tail itself (`MEGA_MXT_SIZE` = 192,
  whole 64-byte lines) is in the tables' block above 1MB, so `[mega_tblkb]`
  grows by one KB on a machine whose rounding was within 192 bytes of the
  next KB and by nothing otherwise - a KB of POOL at worst, never a
  conventional byte (on mega_tlowf's machine, too small for the block above
  1MB, the block is a conventional claim and the tail rides in it: no worse
  than `.lowbss` was).
* **`KERN_SIZE` at boot -512 and the resident footprint -512**: `.lowbss`
  crossed a rung back. Per the banner this is reported, not the point - the
  point is the 160 bytes.
* **kern_big BYTE-IDENTICAL**: `tools/os88rdiff.py kernel HEAD~1 .` at the
  code commit, **4,118 routines same, 0 at an odd shift**, and `kernsize
  --json` identical to `/tmp/msp2/base-big.json` in every field. Every line
  touched is inside `%ifdef KERN_MEGA` (`mega.inc` whole, `megados.inc` whole,
  `hiber.inc` from its line 3714), so **kern_small and kern_emu assemble none
  of it** (`make`'s `kernsize[small]` line: +0).

## TAKEN

One code commit plus this note. Bytes are assembled, kern_mega only.

### 1. THE TABLES' TAIL: `mega_wtab` and `mega_ustab` out of conventional memory - `.lowbss` -160, `.mega` +32

**Where**: in the tables' block itself, past the IDT's last gate - so it is
wherever the GDT is, above 1MB or in mega_tlowf's claim, and it is carried
by every mechanism that already carries the block:

* `mega_layoutf` sizes it in (`MEGA_TBL_TAIL` = `MEGA_IDT_SIZE` +
  `MEGA_MXT_SIZE` in the `[mega_tblkb]` sum). Still a pure function of
  `[mega_extkb]`, so a park's anchor and a hibernate's tables are still found
  where this kernel put them.
* **a hibernate's run 0** is `[mega_ldtend] + MEGA_TBL_TAIL` now
  (`hbm_xplan`), and `hbm_xruns`'s exact-size test agrees - so an image from
  before this change is REFUSED at resume rather than resumed with a tail it
  never saved (hiber.inc, two `add`s; CROSS-FILE).
* **the DOS park's sum** covers it with the IDT's last region, whose 17 lines
  ended exactly at the IDT's end: `17 + MEGA_MXT_LINES` (megados.inc's
  `mega_dsave`, one constant; CROSS-FILE). No new region, so `MPK_RMAX` and
  the park's header do not move. The tail is preserved across a trip exactly
  as the LDT whose selectors its rows name is, which is more consistent than
  before (the rows were in the parked conventional image, the descriptors
  they named above 1MB).

**How it is reached**: `MEGA_SEL_MXT`, a GDT data selector at `MEGA_GDT_SCR -
3` - the padding between the identity map and the scratches that the GDT
build already writes as zero (`.gz`), checked by an `%error` that it stays
above `MEGA_GDT_ID`. Its limit is exactly the tail (`MEGA_MXT_SIZE - 1`), so
nothing written through it reaches anything else, as `MEGA_SEL_LDTD` is cut
to the LDT. `mega_mxtinit` (new, 59 bytes of `.mega`) aims it and zeroes the
tail, FIRST in `mega_pmtail` - before `mega_frames_fix`, before anything can
read a row. It is past the park's line 0 and summed with the GDT; its
accessed bit is set by `mega_dacc` with every other present entry.

**The sites** (every one in this agent's range), each loading the tail once:

* `mx_relall`'s window walk, `mega_wfind`, `mega_wslot`, `mega_iswin`,
  `mega_useg`, and `mega_wset`'s own-row test: **through DS** - none of them
  reads a kernel variable while it holds it, and every row access loses its
  `ss:` prefix, which pays for most of the load. `mx_relall` keeps ES the
  caller's on purpose: `mega_ldt_free`'s KERN-MEGA-PLAN 14.46 test reads the
  CALLER'S ES off its frame, and that ES must still be the caller's there.
* `mega_ldt_free`'s walk: **through ES**, which it had pushed and restores
  anyway.
* **`mega_wnew`** (new, 47 bytes): `mega_wset`'s `.new` and `mega_segbw`'s
  free-row-and-fresh-entry bodies were the same nineteen instructions
  differing in byte 3 - one body now, BH = BOUND, the owner and BOUND stored
  as one word. `mega_wset` (BH is now clobbered; both callers saved BX) falls
  into it; `mega_segbw` calls it.
* `mx_relall` and SEG_FREE (`mega_segf .free`) no longer clear the row after
  `mega_ldt_free`: `mega_ldt_free`'s own walk already empties every row
  naming the freed entry, and every row's selector came from
  `mega_ldt_alloc` (TI = 1, at or above `MEGA_LDT_FREE0`), the only case in
  which `mega_ldt_free` does not refuse. -5 bytes each, behaviour identical.

**SEG_AIM, the rate hook's verb, is FASTER, not slower** (the one hot path
here: SPEC.md 53.2.2 makes it the one verb legal in an `FSXF_RATE` hook, and
the Video Player's ring uses it there). `mega_segaim` now calls
`mega_segown` first (no side effects, BL only; the not-a-window path pays it
where it did not, an error path), then loads ES = the tail once
(`mov ax, imm` / `mov es, ax`, 2 + 17 clocks on a 286 in protected mode) and
walks the rows inline. Against that: `mega_wslot`'s `call`/`ret` (7 + 11),
a `mov si, di` (2) and a `push cx`/`pop cx` round `mega_selbase`, which
keeps CX (3 + 5) are gone, and the old `push es` before the descriptor write
is the same push, earlier. **Net -9 clocks a call on a 286** (386: about the
same, `mov sreg` 18 there). **Stack**: the `push es` now sits under
`mega_blkof`, so a PACKAGE caller's deepest chain goes 10 -> 12 bytes below
`mega_segaim`'s frame - but a DRIVER caller's `mega_segown` chain
(`drv_row_ixf`'s far call into `drv_row_ix_of`, which pushes two) was
already 16 there, so **the worst case the SDK's "~40 bytes" describes does
not move**.

Every other site costs a segment load it did not (~40 clocks on a 286:
`mega_wfind`, `mega_wslot`, `mega_iswin`, `mega_useg`, `mx_relall`;
~23 for `mega_ldt_free`) on paths that create, find or free a window or a
real-segment selector - none per byte, none in an ISR. `mega_useg` is reached
from the reflection's back half (`mega_svc` via `mega_rseg`) only when a BIOS
hands back a segment that is not on the identity map, a ROM table.

`mega_vfixall` no longer zeroes `mega_ustab` (mega_mxtinit has, earlier, and
nothing between calls `mega_useg`: its callers are `mega_rseg` at run time,
`mega_vword` from this very walk and the VESA arm after it).

**Equivalence, by reading** (no row was run; the brief's rule). The
hibernate and the park are argued above; the remaining points:
(a) the zero is earlier than it was for `mega_ustab` and is NEW for
`mega_wtab`, which nothing ever zeroed (DEFECTS FOUND); (b) nothing reads a
row before `mega_pmtail` - every row reader is `.mega` (protected mode
only), and `mega_frames_fix`, the first thing `mega_pmtail` did, runs after
the tail is aimed now; (c) a refused switch never aims the selector and never
runs a row reader; (d) the 286 reset route reflects with every table in
memory, unchanged - but `mega_useg` is on the reflection's back half, so the
86Box check below is named for it.

`tests/megatbl.py` assertion 3 now also reads `MEGA_SEL_MXT`'s descriptor
out of the GDT and asserts its base is the IDT's end and its limit the
tail's, and the block's KB includes the tail - so the row goes red if
`mega_mxtinit` is taken out (the descriptor stays zero) or the layout and
the tail disagree. **Written, not run.**

SPEC.md's two sentences that said `mega_wtab` was `.lowbss` and that run 0
was the GDT, LDT and IDT are corrected (50.6.11's window paragraph, 87.6's
run 0).

## REFUSED

* **The tail through `MEGA_SEL_LDTD` with its limit extended** (no new
  selector): every row reader that already holds ES = LDTD would have had
  the rows for free - but the alias is cut to exactly the LDT so that
  "nothing written through it can reach the IDT or `.cold` beyond it"
  (mega_enterf's comment), and the IDT sits between the LDT and the tail.
  Putting the tail BETWEEN the LDT and the IDT instead moves the IDT, which
  touches mega_tset (bootonce's), the park's three IDT regions and
  `tests/megatbl.py`'s assertion 3 - for perhaps 20 bytes. Not taken.
* **Parallel arrays for `mega_wtab`** (selectors, then owner/BOUND bytes) so
  `mega_wslot` is a `repne scasw` - ~15 clocks a row faster, but every row
  pointer in nine routines changes meaning. Not this round.
* **`mega_xmsel`'s banked window on the stack** (msp1 DEFERRED 9): built on
  paper - the original CX and DX are already pushed, so only AX needs a slot
  and the exit pops it into DI twice - -8 `.mega`, -6 `.text`; refused for
  now because it puts the whole `OSAPI_XMEM_SEL` / claim chain 2 bytes
  deeper on a task slice, the same argument msp1 refused `pusha` on.
  Stays in DEFERRED with that number.
* **`mov cx, bp / shl cx, 10 / call MEGA_SEL_CODE:mega_xmself` x 3 in
  `mega_claimregrowf` into a local helper** (msp1 DEFERRED 7's half that is
  left): -10 `.cold`, refused for the same reason (+2 bytes under
  `mega_xmself` on a regrow).

## DEFERRED

Estimates are labelled; this is pass 3's list.

1. **`mx_tab` into the tail - 960 bytes of conventional memory.** The
   mechanism is built: grow the tail (`MEGA_MXT_SIZE` takes it with no other
   change to the layout, the hibernate or the park: one more KB of
   `[mega_tblkb]`), make `mx_tab` an offset in it, and convert the sites.
   **The census, assembled-source counts**: 46 routines, ~205 sites -
   `mega.inc` 41 routines (31 `.mega` / 120 sites, 9 `.cold` / 63 sites),
   `megados.inc` 2 (`mega_dosclaimf`, `mega_dosparkf`, 7 sites, megados's
   file), `memory.inc` 1 (`mx_shedf`, `.cold`, 8, shared's), `hiber.inc` 1
   (`hbm_xplan`, `.modh` - HIBER.DRV - 3), `fsx.inc` 2 (`rms_xcaps`,
   `rms_xchk`, 11). **Estimated -960 conventional, +~250 `.mega`/`.cold`**
   (a load and a restore per routine, ~6 bytes, less a prefix per access
   where DS is free). Four things stop it being a mechanical sweep, and each
   has its answer:
   * **The real-mode twins read `mx_tab` in REAL MODE** (`rms_xcaps`,
     `rms_xchk`, inside a real-mode fsx bracket, through SS = LOW_SEG). Above
     1MB they cannot. The answer is not a 960-byte snapshot in the bracket's
     service claim (a bigger claim inside a bracket can refuse a tight
     machine - a behaviour change) but the two facts they need, computed in
     protected mode as `fsx_rsvcf` copies the twins out: `rms_xcaps`'s
     answer (AX, BL; ~4 bytes) and the bracket package's OWN blocks
     (`MX_AUX`, `MX_OFF`, `MX_KB` of every entry whose owner is
     `[rms_slot]`, 6 bytes each, at most the package's own count), read
     through CS like the rest of the twins' data. ~+60 `.mega`, est.
   * **Eighteen test and tool files read `mx_tab` by SYMBOL as a
     conventional address, and five WRITE it through the debugger** to pin
     memory (`megashed`, `megadosroom`, `megahiber`, `megahma`,
     `hdnoclaim` ...; `tools/heapmap.py`, `tools/megaconvres.py`; full list:
     `grep -rln mx_tab tests tools`). Each needs `mx_tab`'s linear address
     computed as `[mega_tbllin] + [mega_ldtend] + 0x800 + offset` - one
     helper in `tools/os88sym.py` or `os88bochs.py` (`box.mxt(name)`) and a
     one-line change per file. **That is the reason it is not in this
     round**: twenty harness edits nobody here may run.
   * **The hot readers**: `mx_chk` (every `OSAPI_XMEM_COPY`, and the DOS
     trip's XMS moves) and `mx_inblk` (SEG_AIM's `mega_blkof`, in the rate
     hook). `mega_segaim` already holds ES = the tail across `mega_blkof`
     now, so with `mx_tab` in the same tail `mx_inblk` reads it through ES
     for nothing - the one-selector design is what makes the hook path free.
     `mx_chk` pays one load a copy (~20 clocks against a copy of up to 32KB).
   * **Ownership**: `megados.inc`, `memory.inc`, `hiber.inc` and `fsx.inc`
     sites are other agents' files; one agent should take the whole sweep in
     one round with the harness helper.
2. **`mem_sel` into the tail - 64 bytes of conventional memory.** Sites:
   `mega_p2d` (mega.inc:4847, pmcore's range), `mega_hugec` (5677-5723,
   pmfd's, `.cold`), `mega_rgnconv`/`mega_mpix`/`mega_mpnewf`/`mega_mpsyncf`/`mega_mpfreef`/
   `mega_mpall` (mine), and `mem_val` (memory.inc:4315, shared's, `.text`,
   behind `[mega_on]` - five callers in the heap layer, so a load there is
   ~20 clocks on every claim/free/regrow in protected mode). Two readers by
   symbol: `tools/heapmap.py` and `tests/os88qmpmega.py`. Est. -64
   conventional, +~40 `.mega`/`.cold`/`.text` (the `.text` door in
   `mem_val`). Not taken: three agents' ranges.
3. **`mx_tab` walk idiom** (msp1 DEFERRED 5), now best taken WITH item 1 -
   the sweep rewrites every walk anyway. est. -40.
4. **`pusha`/`popa` in the run-time preserve-everything routines** (msp1
   DEFERRED 6, est. -70 `.mega`): still wants `tools/stkwater.py` on the
   claim paths first.
5. **`mega_xmsel`'s window on the stack** (REFUSED above): -8 `.mega`, -6
   `.text`, +2 stack.
6. **`mega_claimregrowf .copy`'s re-find** (msp1 DEFERRED 8): `mega_mxat`
   answers it only with the new block's base and owner in registers, and
   both are on the stack under the scratch selector there - est. -6, not the
   -15 msp1 said.
7. **`mega_claimregrowf`'s three `mega_xmself` tails** (REFUSED above):
   -10 `.cold`, +2 stack.
8. **Initialized `.text` data written before it is read** (msp1 DEFERRED
   12): `mxs_*`, `mega_xsrc`/`mega_xdst`, `mega_bf*`, `mega_cpry`,
   `mega_mxflr` - ~30 bytes off `kernel.sys`, no resident change. They are
   PM-only state too, so the tail could take them - but each is read
   through DS = KDATA in a routine that would then need a second segment,
   and the bytes do not pay at this size.
9. **`mega_segaim`'s descriptor through ES = LDTD**: with the tail and the
   LDT one segment apart, a routine that reads a row and then writes a
   descriptor loads ES twice. A tail AFTER the LDT and BEFORE the IDT with
   `MEGA_SEL_LDTD` covering both would make those one load (REFUSED's first
   item) - a speed note for SEG_AIM, not bytes.

## WANTS THE OWNER

Nothing taken changes what anyone sees. One consequence to know: a
**hibernate image written by a kernel before this change is refused at
resume** by `hbm_xruns`'s size test (run 0 is 192 bytes longer). That is
the existing cross-version rule working (both kernels carry one
`BUILD_NUM`, SPEC.md 87.6), not a new refusal - but it is now also a
refusal by layout. Likewise a DOS park left standing across an upgrade
whose `[mega_tblkb]` rounding crossed a KB is not found by the next boot's
anchor probe.

## WANTS AN ABI BREAK

* **The SDK's "~40 bytes of stack" for SEG_AIM** (`apps/os88api.inc` at
  `SEG_AIM`, SPEC.md 53.2.2) is an approximation nobody can check. A stated
  WORST CASE (driver caller, `drv_row_ix_of` included) would let a change
  like this one be judged against a number rather than argued. Breaks
  nothing; a contract wording change in the SDK file, so it rides a flag
  day.
* **`OSAPI_SEG`'s window rows are 32, fixed** (`MEGA_WTN`, SPEC.md 50.6.11
  documents "32 rows"): with the rows above 1MB the count costs pool, not
  conventional memory, so 64 would be ~128 bytes of pool and no resident
  byte - but "32" is in the SPEC's contract, and a package that sized itself
  to it would not notice. Cleans the refusal `AX = 1 no ... mega_wtab row`
  for the C64 and RealDMG's many windows. Est. 0 resident.

## CROSS-FILE

* **megados** (`kernel/megados.inc`): `mega_dsave`'s IDT-tail region is
  `17 + MEGA_MXT_LINES` lines (was 17) - **taken in this diff** because the
  move is unsound without it; one constant, 0 bytes. Merge-check it if your
  branch touches `mega_dsave`'s `.tbl` calls.
* **shared** (`kernel/hiber.inc`, KERN_MEGA arm): `hbm_xplan`'s and
  `hbm_xruns`'s `MEGA_IDT_SIZE` are `MEGA_TBL_TAIL` - **taken in this diff**
  for the same reason; 0 bytes. `hbm_xplan`'s `mx_tab` walk is DEFERRED 1's.
* **bootonce**: `mega_mxtinit` runs ONCE, at the switch (`mega_pmtail`'s
  first call). It is `.mega`, 59 bytes; if you build a `.mega` init tail the
  kernel drops after `mega_pmtail`, it belongs there - its only constraint is
  that it runs before anything reads a window or a real-segment row
  (`mega_frames_fix` onward). It reads `[mega_tbllin]` and `[mega_ldtend]`
  (mega_layoutf's), so it must run after `mega_tset`.
* **pmcore / pmfd / shared**: `mem_sel`'s sites in your ranges (DEFERRED 2).
* **coordinator**: SPEC.md 98492 still describes the tables as `MEGA_TBL_SIZE`
  = 82K with `MEGA_LDT_OFF`/`MEGA_IDT_OFF` - stale since MC7's step 6, and no
  such symbol exists. Not this pass's to rewrite.

## ROWS TO RUN

Named, not run (the brief's rule). Bochs: `megatbl` (the tail's descriptor
and the block's size, on 1, 4 and 16MB - **the row for this change**),
`megahiber`, `megahibfull`, `megap2hiber` (run 0 now carries the tail; an
image round trip must bring every window back), `megadosp`, `megadosroom`,
`mega-doscom`, `mega-dosxmsq`, `mega-dosram` (the park's sum now covers the
tail), `megainst`, `megaflt` (an instance's end frees its windows through
`mx_relall`), `megashed`, `megahuge`, `megaxmove`, `megaown` (`mega_ldt_free`
on every free), `megavidbig`, `megavidring`, `megavidtier`, `mega-vidvga4`,
`mega-vidmodex` (SEG_AIM in the Video Player's hook), `mega-c64part`,
`mega-c64move` (the C64's ROM-bank windows - KERN-MEGA-PLAN 14.80's
aliasing, `mega_wset`'s own-row rule), `megapixel`, `megafont` and
`megarmb` (`mega_useg` over ROM segments), `mega-skiesworlds`.

**86Box** (the coordinator's note: the 286 reset path is testable there):
`vm/286-mega` booted to the desktop, the Video Player playing a clip from
the apps disk and the C64 started - the reset route's reflections run
`mega_rseg` -> `mega_useg` on the back half of every BIOS call that hands
back a ROM segment, and SEG_BWIN/SEG_AIM build and re-aim windows. Any FAULT
line is this change.

## DEFECTS FOUND

* **`mega_wtab` was never zeroed.** `.lowbss` is not zeroed at boot (its own
  comments say so for `mega_pm`, `mx_tab` and `mega_ustab`, each of which
  has its zeroing), and nothing wrote `mega_wtab` before its first read, so
  a BIOS that left that RAM non-zero - or, more likely, a WARM RESTART
  (`int 19h` clears nothing, so the last session's rows are still there,
  naming selectors the new LDT will hand to somebody else) - handed
  `mega_wset` rows it took for
  taken (a row refused early: `AX = 1`) and, worse, `mega_iswin` and
  `mega_wslot` rows that matched real selectors - a SUB taken for a window
  is not freed with its block. QEMU and Bochs clear RAM, which is why no row
  saw it. **Fixed by this change** (`mega_mxtinit` zeroes the tail), not
  separately.
* SPEC.md 98492's table entry is stale (CROSS-FILE).
