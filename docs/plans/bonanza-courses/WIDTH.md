# WIDTH: what raising the 1,024 px course width would cost (a costed study, 2026-11-20)

The owner, designing course 3 (DOWN, [DOWN.md](DOWN.md)): what would it cost
to raise the 1,024 px limit? DOWN is pressed against both edges. `origin 288`
is set by the glass leg's west reach, and [LIFT2.md](LIFT2.md) section 4
needs steel's lift at `wx - wy >= 45`. Its footprint is then
`16 x 45 + 288 +- 24` = px 984 - 1,032, which is past the last pixel.

**BUILT (2026-11-20): option A, `width` up to 160.** SPEC.md 130.10.4.2's
amendment is the contract and 130.54.8's TWIDE the test course; the sections
below are the study as it was written, and the measured cost of what was built
is in that amendment's commit. What changed from the plan: `width` takes any
multiple of 8 from 64 to 160 (not only 160), `BROWS` is bounded at
`BZ_MROWS` = 256 by the tool, and the `lock across` refusal at `c0 >= 128`
is unreachable at 160 (`cmax` 120) and stands as a guard.

This was a STUDY. Each figure is marked:

- **MEASURED**: the tool's own `--sizes` output, or a nasm assembly at this
  tree (`f72395607`, `bounce-bonanza`).
- **PREDICTED**: arithmetic or a reading of the code.

The prototypes in sections 3 and 4 were scratch copies outside the tree, and
neither was committed.

## 0. The answer

- **1,280 px (`width 160`) is feasible, cheap and clock-free.** The guest
  change is the map's row offset: a 256-word table in place of
  `<< MAPSH`. Its prototype is **+4 bytes of code (MEASURED) and +511 bytes
  of bss**. The frame cost is about 0 clk (PREDICTED). Every other reader
  already strides by `ROWB`. For DOWN as it stands, with no content added,
  **the picture part grows by 8,032 bytes to 62,032 (MEASURED), leaving
  2,992 bytes of headroom** under 65,024. LZ4 on disk grows by 41 bytes.
  The tool needs about 2 - 3 days of work, including the SPEC.md amendment
  and a wide test course.
- **The catch is DOWN's content.** The extra width costs no content. The
  steel leg that uses it does, and every block (16 bytes), record (4 bytes)
  and mask (16 bytes) it adds comes out of those 2,992 bytes. A spur of a
  few rooms probably fits (PREDICTED). A second room-sized leg does not.
- **1,536 and 2,048 px do not fit DOWN's height in a dense map.** DOWN at
  1,536 is a 70,112-byte picture part, over by 5,088. At 2,048 it is at
  least 76,542 bytes before any occluder, over by 11,518 (both MEASURED, the
  tool's own refusals). The map is `2 COLS BROWS` words, dense, and at
  2,048 px DOWN's map alone would be 64,512 of the 65,024 bytes.
- **The real lever is the MAP, not the width.** 67.5% of DOWN's map words
  are the black block (MEASURED). A map that stores each block row's span
  (section 5) would hold DOWN in **11,982 bytes instead of 32,256**. Width
  would then cost content only, up to the 2,048 px that byte columns allow.
  It costs a new map form, every map reader, and roughly 1 - 1.6k clk on
  each frame that writes a column (PREDICTED). That is about 1.5 - 2 weeks,
  and the column frames are the frames already nearest a miss on the CGA.
- **Rotating a course down the screen does not escape the limit.** The
  vertical limit is the same RAM, priced per block row (section 7). The dense
  map costs the picture's bounding box, W x H / 32 bytes, in whichever
  direction it runs.

**Recommendation.**

1. For DOWN now, build `width 160`: option A, section 3. Place steel's lift
   east of `wx - wy = 45` and let the tool say whether the content fits the
   2,992 bytes.
2. If it does not fit, the first fallback is LIFT2's option 2: give up
   glass's lift. It costs nothing. Option E (section 6) is the clocked
   fallback.
3. Do not go to 1,536 or 2,048 as dense maps. If the owner wants wide courses
   as a class, the sparse map (section 5) is the investment that pays.
   Measure its column cost on MILL's CGA demo before committing to it.

## 1. Where the limit lives

The width is `COLS` word columns (8 px each). Every place that bounds `COLS`
or depends on it:

| # | where | what it holds | the bound it sets | at 160 (1,280) | at 192 (1,536) | at 256 (2,048) |
|---|---|---|---|---|---|---|
| 1 | the grammar, `tools/bbcourse.py` `width` | 64 or 128 | the limit itself | widen | widen | widen |
| 2 | `COLS_MAX` (tool), ROWPLANES' scratch (`bz_cxmap`, SPEC.md 130.15.4.4) | `COLS / 4` high bytes in `bz_boxbuf` (1,024 bytes), the count in `DL`/`CH` | 128 by the constant; really `bz_boxbuf` and a byte, so 1,020; `COLS` a multiple of 4 | OK, a constant | OK | OK |
| 3 | `MAPSH` and `(L & ~7) << MAPSH`: **11 guest sites** (`bzvideo.inc` 4, `bzvga.asm` 3, `bzwheel.inc` 4) and the tool's header and `read_part` | a power-of-two map row | `COLS` a power of two; at 256, `L < 1,024` before the shift overflows 16 bits | **breaks**: option A's table | breaks: the table | works with `MAPSH` 6; rows < 128 |
| 4 | the column writers, the box fill, the wheel's commit (`add bx, [BZC_ROWB]`, `bz_rowb`) | the stride, read at run time | none: generic in `ROWB` already | OK | OK | OK |
| 5 | the VGA column writer, `mov bp, 8 / shl bp, cl` | the stride from `MAPSH` | power of two | `mov bp, [bz_rowb]` (in A) | same | same |
| 6 | the dense map, `M` = `2 COLS BROWS` bytes in the PICTURE part (SPEC.md 130.30) | every block cell | the part's 65,024 bytes | +64 a block row | +128 | +256 |
| 7 | the 4-byte occluder record +0 (130.15.5.1), `bz_occ`'s `DL`/`DH` and `bz_olay`'s byte compare (`bzvideo.inc` "x0 under 128") | a word column in a BYTE | **256 columns (2,048 px)**; the "under 128" comments are a stronger claim than the code needs (`c - x0` mod 256 stays past any `w` while `COLS <= 252`) | OK; re-prove the comments | OK | OK at 256 exactly; past it RECB grows |
| 8 | a lane's `BZP_LCOL` (record +10, a byte) | its first word column | 256 columns | OK | OK | OK |
| 9 | `BZ_CRS_LOCKS` (130.45) and `bz_vinit`'s `cbw` | the locked `c0`, a byte | `c0 < 128` | OK (`cmax` 120 CGA, 115 Hercules) | a lock at `c0 >= 128` misreads: **the tool refuses it** (0 guest bytes; a lock only suits a course one window wide) | same |
| 10 | `KW_MAX` 33 and `BZ_CXRW` 36 (`bz_cxcel`, 130.15.6) | the grid row's cells: the `a = wx - wy` span / 2 | about 1,024 px of reach | KW about 41: `BZ_CXRW` 44 (an equate) | 49: 52 | 65: 68, past disp8 at `2 BZ_CXRW + 1`, so about +10 bytes of launch code |
| 11 | the grid `C`, `4 KW NROWS` in the WORLD part | dense across the row | the world part (DOWN: 46,620 bytes free) | about +3.4KB if the width is used (86 rows) | +6.9KB | +13.8KB |
| 12 | the world: tiles `0 - 255`, `gx`, `gy < 4,096` (130.10.2, 130.10.7.1), ways in two bytes | the `a` span, at most about 250 diagonals | about 4,000 px | OK | OK | OK |
| 13 | the camera (`bz_c0`, `bz_cmax` = `COLS - W`, LATTICE, GLIDE, `bz_px`) | words | none | OK | OK | OK |
| 14 | the rings: the CGA's and Hercules' `(W R0 + c0) mod 4096` (130.2), the VGA's `(P L + b) mod 65536` (130.46.3) | the world sheared into a ring | none: a cell's address never depends on the world's width | OK | OK | OK |
| 15 | the route (`W`, pairs of px words), the demos and replays (key runs, no positions) | | none | OK | OK | OK |
| 16 | the tool: the render, the reach, the occluder cut, `foot_x` against `width` | per-pixel buffers `8 COLS` wide | runtime grows with width (DOWN 2 m 44 s at 1,024, MEASURED) | widen | widen | widen |
| 17 | kern_mega | one LDT selector a part, offsets under 65,024 | nothing width-specific | OK | OK | OK |

So the hard ceilings are these.

- **The dense map's RAM** (#6). It binds DOWN at 1,536.
- **Byte columns** (#7, #8). They allow 256 columns, 2,048 px. Past that,
  every record grows a byte, and so does the occluder pass's register
  allocation.
- **The world's 256-tile range** (#12). It allows about 4,000 px.

Everything else is a constant, an equate or a refusal in the tool.

## 2. DOWN at each width (MEASURED)

These were compiled by a scratch copy of `tools/bbcourse.py`. Its only
changes were these:

- `width` accepts 160, 192 and 256;
- `COLS_MAX` 256 and `KW_MAX` 65;
- `MAPSH` written as 5 for 160 and 192, and 6 for 256.

The input was `down.bbc` with only `width` and `origin` changed. The origin
was moved by half the added px (416, 544, 800), so **no content changed**.

| width | picture part (RAM) | headroom under 65,024 | LZ4 (LZB), whole course | map `M` |
|---|---|---|---|---|
| 1,024 (today) | 54,000 | 11,024 | 17,604 (14,426) | 32,256, LZ4 3,100 |
| **1,280** | **62,032** | **2,992** | **17,645 (14,538)**: +41 (+112) | 40,320, LZ4 3,129 |
| 1,536 | 70,112 | **refused, over by 5,088** | - | 48,384 |
| 2,048 | at least 76,542 before occluders | **refused, over by 11,518** | - | 64,512 |

The world part is 18,404 bytes at every width (46,620 free), because KW does
not grow until cells use the width. The picture part's non-map sections come
to 21,744 bytes, and those scale with CONTENT, not width:

- the header (48 bytes);
- `B`, the blocks;
- `I R K O Y`, the occluders;
- `L`, the lanes;
- the directory.

**How tall a course at DOWN's content density can be** (PREDICTED,
`(65,024 - 21,744) / 2 COLS`, holding the content fixed):

| width | rows | lines |
|---|---|---|
| 1,024 | 169 | 1,352 |
| 1,280 | 135 | 1,080 |
| 1,536 | 112 | 896 |
| 2,048 | 84 | 672 |

The tool's own estimate, which grows the content with the rows, is about 151
rows at 1,024. DOWN is 126 rows (1,008 lines).

## 3. Option A: a dense map at any width a multiple of 4 (the one to build for DOWN)

**The change.** `bz_crshdr` builds `bz_mrow`, a word for each block row
holding `BZC_MAP + br x ROWB`. Each of the 11 sites then reads it instead of
shifting:

    and al, 0f8h            ; AX = 8 br            (was: mov cl, [bz_mapsh]
    shr ax, 1                                      ;      shl ax, cl
    shr ax, 1               ; AX = 2 br            ;      add ax, BZC_MAP)
    xchg ax, bx
    mov bx, [bz_mrow + bx]  ; (es: where DS is the part)
    xchg ax, bx             ; AX = the row's map entry, BX kept, CL kept

The `br << (MAPSH + 3)` sites take `shl ax, 1` and the same read. The VGA
column writer's `mov bp, 8 / shl bp, cl` becomes `mov bp, [bz_rowb]`.
`bz_mapsh` goes. The column writers, the box fill and the wheel's commit do
not change (section 1, #4).

**The prototype.** All 11 sites, the table build, the VGA part's three, and
`VAR bz_mrow, 512` for `bz_mapsh`. It assembled against this tree's art and
was relinked with `pxlink`. MEASURED:

| | today | the prototype | delta |
|---|---|---|---|
| `bonanza.bin` (image) | 50,954 | 50,964 | **+10** |
| `bzvga.bin` (the VGA part) | 5,259 | 5,253 | **-6** |
| bss | 8,819 | 9,330 | **+511** (the table 512, less `bz_mapsh`) |

The package as a whole is then 60,294 of `APP_MAX_SIZE`'s 65,024, 4,730 free
(MEASURED for today's 59,773, PREDICTED for the sum). The table could be
sized to the tool's row bound and not 256, but the picture part allows 254
rows at width 128. The `BZDEV=1` build carries the same 511.

**Clocks** (PREDICTED, 8088 timings with the fetch floor). The old sequence
is `mov cl, [mem]`, `shl ax, cl` at 5, and `add ax, imm`: about 56 - 60 clk.
The new one is two `shr`, two `xchg` and an indexed `mov`: about 45. The
sites are entry and setup code: a row, a column, a box, an occluder
row-prep, a lane. They run about 10 - 20 times a frame, so the net is
**0 to -0.2k clk a frame**. Nothing in any per-block loop changes.

**The part's format.** `COLS` is any multiple of 4 up to 256, and `ROWB` =
`2 COLS` as now. Keep writing `MAPSH` 4 or 5 for 64 and 128, so every
shipped part stays byte for byte the same, with the same identity and the
same demos. Write 0 for the other widths; the guest no longer reads it.
SPEC.md 130.10.4.2, 130.10.5.1 and 130.15.4.2 are amended to say so.

**The tool** (about 2 - 3 days, with the SPEC.md amendment and a test
course; PREDICTED):

- the `width` grammar;
- `COLS_MAX` and the `read_part` checks (`cols in (64, 128)`, the `MAPSH`
  check);
- `KW_MAX` with `BZ_CXRW`, and the `%if` guard that ties them;
- `lock across` refused at `c0 >= 128`;
- `--selfcheck` grammar strings for a 160-column course, and a decode
  round-trip at a width that is not a power of two;
- one wide test course, so the rows that read the map walk a 160-column
  part.

The rows that reach this are `bonanzacourse`, `bonanzaring` (the writers'
bytes on the card), `bonanzaperf`, `bonanzamega` and the VGA arm's rows. They
are named here, not run (a sub-agent does not soak).

**DOWN's identity moves.** A new `X0` is a new `BZG1` header and new cells.
The tool regenerates DOWN's route demo itself, but any saved `.BZR` of DOWN
is stale. DOWN has not shipped, so nothing is lost.

## 4. 2,048 px as a power of two (the dense shortcut, and why it does not help DOWN)

`COLS` 256 is `MAPSH` 6. The shift form survives as long as
`(L & ~7) << 6` stays under 64KB, which means fewer than 128 block rows. On
the guest it costs nothing but the equates and the tool's refusals
(PREDICTED). But the map is 512 bytes a block row. At DOWN's content a part
holds about 84 rows (672 lines). DOWN is 126 rows, and its map alone would
be 64,512 bytes.

A map in a part of its own is no help either. The writers read a map word
and then its block through one DS, so a map in another segment puts a
segment switch in every block of every column. That is the cost 130.30.3
refused for the occluders.

So 2,048 px dense is only for short courses (under about 670 lines at
DOWN's density). It is not the answer for DOWN.

## 5. Option D: a sparse map (the investment that makes width cheap)

**MEASURED on DOWN's RAM map** (the tool's own `expand()` of `BZ0.BIN`):

- 16,128 words, of which **10,888 (67.5%) are the black block**;
- the non-black words in each block row span 5,739 words in all, against
  5,240 non-black, so the content in a row is nearly contiguous;
- 206 runs over 126 rows;
- the drawn columns are 10 - 117. It is the reachable FOOTPRINTS, not the
  drawn pixels, that press on 0 and 1,023.

| map form | DOWN, bytes of RAM |
|---|---|
| dense, today | 32,256 |
| a dense band of 16 block rows, each its own column origin | 15,616 |
| a dense band of 8 rows | 13,200 |
| **a span per block row** (`lo`, `hi`, a biased base: 4 bytes a row plus the words) | **11,982** |

A span map's RAM is the CONTENT's, whatever the width. DOWN would drop by
about 20KB at 1,024 px, and could then go to 2,048 (the byte-column ceiling)
for the price of its added rooms. One caution: a course whose two legs sit at
opposite edges ON THE SAME ROWS has a row span as wide as the picture. A
single span per row saves nothing there, and it needs runs instead.

**What it costs** (PREDICTED):

- **A new map form.** The ROWPLANES successor and its in-place proof
  (130.15.4.4), the row table, and the tool's model, `read_part`,
  `decode_part` and `expand`.
- **Every map reader:**
  - the CGA, Hercules and VGA column writers (`bzvideo.inc`, `bzvga.asm`);
  - the row writer;
  - the box fill;
  - the occluder row-prep;
  - the wheel's `bz_lmap`, `bz_wprect`, `bz_wspan` and `bz_ltmo` (it WRITES
    pose maps into `M`, so every lane must lie inside its rows' spans: a
    tool rule).
- **Rule out reads outside a span.** The tool pads each span to cover every
  reachable footprint, so the box fill and the occluder lay never read
  outside one. The row and column writers can still be shown a column
  outside it, and they clip: black for a column outside `[lo, hi]`.
- **About 300 - 500 bytes of guest code.** Most of it is the column
  writers' clip, three times over.
- **Clocks.** The column writer's per-block step today is
  `add bx, [BZC_ROWB] / mov si, [bx]`. With row-dependent bases it becomes
  a table step plus an unsigned range test, about +40 - 60 clk a block, so
  **about +1.0 - 1.6k clk a column** (25 - 27 block rows). The alternative
  computes the column's block pointers into a list once, then reads them
  through CS in the loop. That is about the same total, moved to the
  column's start.

The risk is real. SPEC.md 130.16's MILL CGA figures put the column frames at
the miss threshold already, "some 1.4 misses per column a second". The +15
clk a block that `ROWB` cost in wave 1 was priced at +0.4k a column.
**Effort: about 1.5 - 2 weeks**, plus a MartyPC measurement of MILL's CGA
column frames before deciding.

## 6. Option E: occluders out of the picture part (a third part)

130.30.3's option (e): `I R K O Y` move to a third part. At 1,536, DOWN's
picture part would lose 9,352 bytes (MEASURED sizes) and fit at about
60,760. That is about 4,260 bytes of headroom (PREDICTED). The cost is
130.30.3's (b): two DS switches for each laid group, **about 100 - 150 clk a
laid group**, at most 9 a frame. The owner's constraint ("must not hurt frame
performance") refused exactly this split for the two-part form. It does not
reach 2,048 for DOWN, because the map and blocks alone are about 76KB there.

## 7. The vertical limit

There is no format constant for height. Height is bounded by the same RAM,
and by three softer limits:

- **The picture part.** The map is 256 bytes a block row at width 128. At
  DOWN's density a part holds **about 151 block rows, 1,208 lines**: the
  tool's figure, against DOWN's 126 rows and 1,008 lines. At width 64 the map
  is half as dear, so a narrow course goes about twice as far down for the
  same content. Width 160 leaves DOWN-like content about 135 rows; see
  section 2.
- **The shift form** (`(L & ~7) << MAPSH` in 16 bits). The limit is 2,047
  lines at width 128 and 1,023 at 256. Option A replaces it with the table,
  whose size is the bound (256 rows, 2,048 lines).
- **The world.** Rows are `s = wx + wy <= 510`: about 4,080 lines plus
  heights. The grid's `ROWTAB`, `Y0`, `bz_rmax` and the rings are all words
  or modular.
- **Fixed windows only.** The title's `view` stores the window's top line in
  a byte x 4 (1,020 lines). No play course uses it.

**Rotating a course to run down the screen** therefore trades width for
height at the same price. The dense map costs the bounding box's area,
W x H / 32 bytes. A straight leg along `+wx` or `+wy` moves 2 px across for
every line down, so a course only runs straight down by zig-zagging its legs.
DOWN's split sends the legs in opposite screen directions, steel down-right
and glass down-left, and that is what spends the width.

The layout alternative is to turn each leg back toward the middle after the
split. That costs rows instead of columns, at the same 256 bytes a block row,
and LIFT2 section 4 already found that separating the lifts vertically needs
about 240 lines. DOWN has about 200 lines of room before the part is full
(PREDICTED). It is a design question, not an engine one, and it is tight.

## 8. Summary table

| width | feasible for DOWN? | guest bytes | per-course RAM (DOWN) | disk (DOWN) | XT risk | effort |
|---|---|---|---|---|---|---|
| 1,280 (A) | **yes**, 2,992 bytes of headroom for new content | **+4 code (MEASURED), +511 bss** | picture 62,032 (+8,032, MEASURED); grid +3.4KB if used | LZ4 +41 (MEASURED) | about 0 clk | 2 - 3 days |
| 1,536 (A) | no: 70,112, over by 5,088 (MEASURED) | as A | +16,112 | - | 0 | as A, plus E or D |
| 1,536 (A + E) | yes, about 4.3KB of headroom | as A, plus the third part's fetch and claim (about 100 - 200 bytes) | +16,112 picture, about 9.4KB moved | small | **+100 - 150 clk a laid group** | about 1 week |
| 2,048 (dense, MAPSH 6) | no: over 76,542 (MEASURED) | about 0 | +32,256 | - | 0 | 2 days, short courses only |
| any to 2,048 (D, sparse) | yes, about 20KB smaller than today | about +300 - 500 | DOWN's map 11,982 instead of 32,256 (MEASURED model) | about the same | **about +1 - 1.6k clk a column frame** | 1.5 - 2 weeks, plus a MartyPC A/B |
| past 2,048 | - | record and lane columns become words (RECB 5) | +1 byte a record | | | not recommended |
