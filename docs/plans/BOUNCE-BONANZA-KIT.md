# BOUNCE BONANZA: the standard kit

*The contract is SPEC.md 128.33; where this plan and it disagree, it wins.
The pricing is `docs/reports/BONANZA-KIT-2026-11-17.md`. The diary entries
are in [BOUNCE-BONANZA-DIARY.md](BOUNCE-BONANZA-DIARY.md) under "the standard
kit".*

The owner (2026-11-17): build the held kit the report recommends - courses
name the kit's pieces, the pieces are copied into the course at its load,
the kit is held for the session - with ONE alignment for every play course,
and the F library as its first content. The disk is "a priority; one of
many": the goal is 14 - 20 courses, possibly on one disk.

## Where it stands

**K0 written** (SPEC.md 128.33). **K1 BUILT** (128.33.11: the tool, the kit cut, the demos re-stamped; `make bonanza` assembles again at K2, whose expander the form needs). K2 below.

Branch `bounce-kit`, cut from `bounce-bonanza` at `03e864602`. Not merged
into `bounce-bonanza`: the owner merges.

## The shape of the work

| wave | what | depends on |
|---|---|---|
| K0 | the contract (SPEC.md 128.33 and its amendments to 128.11.4.2, 128.15.4.4, 128.22.7, 128.25.3), this plan, the diary | the report |
| K1 | the tool: the kit's source and generator, kit order, form 8, the one alignment, `--sizes`, `--selfcheck` item 16, the demos re-stamped | K0 |
| K2 | the guest: the kit's row, its fetch and hold, `bz_cxkit`, `bz_phrel`; the unicorn harnesses | K1 |
| final | the rows once (the owner's), `test-full` | K2 |
| (K3) | the designed kit and the F library's standard chutes; courses re-authored to use them | the owner's design work |

## The stories

### Wave K0: the contract

| # | story | verified by |
|---|---|---|
| K0.1 [x] | SPEC.md 128.33: the kit's source, generator and part; kit order; form 8 and its in-place argument; the hold and the memory order with the owner's high-water reasoning and every claim after a course's load; the one alignment; the tool's rules and item 16; kern_mega, kern_small, the Hercules; the report's predictions | `tools/checkdocs.py` |
| K0.2 [x] | the amendments: 128.11.4.2 (the 4-a-block bound is the author's), 128.15.4.4 (form 8), 128.22.7 (`BZ_KIT_CLAIM` in `bz_phrel`), 128.25.3 (the search superseded) | `tools/checkdocs.py` |
| K0.3 [x] | this plan; the diary's entry; the report brought onto the branch | `tools/checkdocs.py` |

### Wave K1: the tool

| # | story | verified by |
|---|---|---|
| K1.1 [x] | `bbcourse.py kit` generates `apps/bonanza/courses/kit.bzk` from KIT_POOL's nine courses compiled without the kit: blocks and masks in 3+, every FIELD table | the file; `kit_check` |
| K1.2 [x] | a play course's blocks, masks and tables in kit order; nothing else moves | item 16: the RAM form is the kit-less compile's, piece order aside, on every play course |
| K1.3 [x] | form 8 `KITREF` in `stored_form`, `expand`, `decode_part(s)`, `read_part(s)` | item 16: expands in place; red arms (a bit cleared, a kit short, a piece changed, the bitmap in place) red |
| K1.4 [x] | the one alignment: no Y0 search, `Y0` = 4 (mod 8); what changed per course reported | item 16's alignment line; item 6 |
| K1.5 [x] | `BZKIT.BIN` written, `BZ_KIT_CLAIM` and `BZ_KIT_BMB` emitted, the Makefile's row and prerequisite | `make bonanzadisk` |
| K1.6 [x] | `--sizes`: per course the kit's pieces and its own, LZB against the kit-less compile; the kit's figures | `bbcourse.py --sizes` |
| K1.7 [x] | the identities and demos re-stamped once (`author` for MOON, PEAK, PLAYGROUND) | the build's demo checks; the `ident` lines alone changed |

### Wave K2: the guest

| # | story | verified by |
|---|---|---|
| K2.1 [ ] | the kit's row; fetched QUIET at the open before the bundle, held; again at a play course's load if refused; given back on kern_small | `make bonanza`; the rows `bonanzaexit`, `bonanzapath` |
| K2.2 [ ] | `bz_cxkit`: the tag to the form, the bitmap to `bz_boxbuf`, the pieces from the kit | unicorn: `bz_cexp` on every shipped part equals the tool's expand; `tests/bonanza_dfield.py` |
| K2.3 [ ] | `bz_phrel` counts `BZ_KIT_CLAIM` while the kit is not here | read; `bonanzapath` |
| K2.4 [ ] | kern_mega: the kit's selector through `bz_kseg`, nothing through CS | `bonanzamega` |
| K2.5 [ ] | the image and bss MEASURED; the copy's clocks PRICED | `make bonanza`; unicorn pricing |

### The final pass (the owner's)

`bonanzacourse`, `bonanzaexit`, `bonanzapath`, `bonanzagame`, `bonanzademo`,
`bonanzaring`, `bonanzaphys`, `bonanzamega`, `bonanzaperf`, once, after K2;
then `test-full`.
