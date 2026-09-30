# The stream writer's resident cost, before and after its size pass (2026-09-30)

**A MEASUREMENT** (docs/README.md): true of the trees below and of no other.
A later measurement is a new file.

- **Base**: `origin/elendilon` at `4164ecd`, which carries none of
  docs/plans/STREAM-WRITER-PLAN.md (its kernel is `492114c`'s: the nine
  commits between touch no kernel file).
- **Before**: `stream-writer-and-copy` at `8ed32fa` - the stream writer,
  the bank (SPEC.md 18.8.5), the copy's room check (22.5.2.1), the paste's
  narrower re-list (22.3.1) and the three converted writers.
- **After**: `stream-writer-size-optimization`, this pass.
- **Instrument**: `tools/kernsize.py` (sections) and `--modules` (per file),
  both assembling the tree in place. RESIDENT = `.text` + `.bss` + `.cold` +
  `.lowbss` + `.vgabuf`; `.ovl`/`.ovlw` go away after boot and
  `compress.inc` is `CLONE.DRV`, a module, so neither counts.

## The totals, `kern_big`

| | `.text` | `.bss` | `.cold` | resident | vs base |
|---|---|---|---|---|---|
| base | 47,491 | 5,543 | 40,484 | 100,220 | - |
| before | 47,524 | 5,597 | 41,474 | 101,297 | **+1,077** |
| after | 47,522 | 5,564 | 40,919 | 100,707 | **+487** |

The brief was under 500. `kern_small` is +6 on both, the API cell.

## Where the 590 bytes went

Each row is one step of the pass, and the figure is the resident total
`kernsize` printed after it, against the base:

| step | after | delta |
|---|---|---|
| (the branch as it came in) | +1,077 | |
| ONE kernel stream record and a one-word TOKEN (`DI` in and out, `AL` = flags, `ES:BX` = the bytes - APPEND's registers) in place of a 16-byte cursor copied in and out; the held stream's second copy of the same fields gone; READ_SEQ's door back to its own frame; the commit entering the append body at `.seal`; one gate routine | +731 | -346 |
| the copy's and the join's cursors become a token | +704 | -27 |
| the grow stores the entry's TAIL, so the record keeps 16 bytes of it and not 32 | +684 | -20 |
| the copy's room check sets its own goal; `dskw_dfree_to` gone | +660 | -24 |
| the bank's shed and eviction hazards met at the one LOAD that follows them; the commit reads the poison after its hop | +613 | -47 |
| the seal restructured, `.stamp` into the body, a failed rollback flush poisons, the park's claim test by `dsk_fatw_slot` | +585 | -28 |
| the close through the door's cold path; one predicate (`dws_ours`) for gate, park and bank; the commit hops to the volume's root; the mount's commit hook dropped; the copy's token in `DI`; the goal in sectors | +534 | -51 |
| the held chain's head rides in the record; stage 1 WITHDRAWN (SPEC.md 18.4.7.6, +16 to restore); smaller encodings | +499 | -35 |
| a latent defect fixed (a lost bank emptied only its bottom half); the park banks on the incoming volume's claim alone | +496 | -3 |
| ONE media generation for READ_SEQ and WRITE_SEQ; `[dsk_wgen]` gone | +484 | -12 |
| `ovlchk`: the tail store names `dsk_secbuf` as an offset, not through `lea` | +485 | +1 |
| the tail store's parameters survive `DSK_RD1D`, which loads BX (the first soak found it: every join said `No such file`) | **+487** | +2 |

## What changed in behaviour

- **The ABI** (SPEC.md 18.4.9): `ES:BX` bytes, `AL` flags, `DI` the token.
  Every caller in the tree moved with it: the copy (`fcp_xfer`), the join
  (`cmz_*`, `CLONE.DRV`), FTPD's STOR and VIDDISK's W.
- **Two streams at once** are both correct and each goes cold when the
  other wrote; before, each caller's cursor stayed hot across the other's
  plain writes only until the generation moved, which was every write -
  the same thing.
- **READ_SEQ goes cold less often**: a quiet hop and a fixed disk's mount no
  longer move its generation. Its cursor keeps its volume check.
- **A held stream's banked window taken by a SHED** now loses the stream
  (`FERR_IO` at its next call) instead of refusing the shed.
- **A mount outside a batch no longer commits a hold**; the unlock does, and
  a volume RE-READ on the way back loses the bank rather than trusting it.
- **A held call whose rollback flush also fails** now POISONS the stream,
  so its next call answers `FERR_IO`; before, the stream was abandoned to its
  last commit and the next call appended past the chunks that never reached
  the disk.
- **Stage 1** (one FAT flush when one sector is the whole update) is gone:
  a plain append flushes twice again, as before the branch.
- **The copy's room check** stops at the first FAT sector that brings the
  count past the file's sectors, where it stopped at its clusters plus one:
  the same single window load on any partition with room.
