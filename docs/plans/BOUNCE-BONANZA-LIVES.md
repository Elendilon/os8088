# BOUNCE BONANZA — the pathway's lives counter (options, and one parked idea)

The owner, 2026-11-17: the pathway's lives counter should say what it is
("the clocks in the maps don't need this because their function is
obvious, but the Lives prop on the pathway is less so"), and fit in as
well as possible; the prop could be reworked completely.

Four options were mocked up on the real pathway picture, CGA and Hercules
side by side: [bounce-bonanza/lives-options.png](bounce-bonanza/lives-options.png),
drawn by [bounce-bonanza/livesmock.py](bounce-bonanza/livesmock.py) (run it
from the repository root with an output directory; it removes the counter's
art from the compiled pathway and draws each option in its place).

| | the option | the owner's word |
|---|---|---|
| A | the crystal ball kept, LIVES beside it at its height | liked; NOT the black box round the digit - black on the checker reads fine on the Hercules, and without the box the digit looks like part of the art rather than a BIOS number pasted on top |
| B | a signboard on two posts, the title's plaque style, LIVES over the digit | liked |
| C | LIVES over the player's marble on a plinth, "x" and the digit | **CHOSEN** (SPEC.md 130.22.2's `lives` frame) |
| D | the lives AS marbles resting on the crystal tile, one a life (5 at most), LIVES above, no digit | liked - **PARKED, below** |

## D, parked: a marble that breaks when a life is lost

The idea: the counter is the marbles themselves, and on returning to the
pathway after a life is lost, one of them shatters (as the glass ball does)
before the count settles. Recorded to revisit at the end of development -
if the release becomes two disks there may be room for it.

What it would take (ESTIMATED from the tree on 2026-11-17, not built):

- **The counter as a SIGN lane** (SPEC.md 130.22.4.1) per page instead of a
  clock digit: its poses the counts 0 - 5 as pictures, posed from `bz_lives`
  by `bz_nset` (bz_tdset's pathway branch goes). A few hundred bytes of
  the pathway part (pose blocks are shared), a handful of code bytes.
- **The shatter**: a lane holds at most `LANE_PMAX` = 16 poses, so ONE lane
  a counter fits the 6 counts plus 2 shatter frames (crack, burst) for each
  of the 4 marbles that can break while play goes on (5 -> 4 ... 2 -> 1; the
  last life goes to game over, not the map): 14 poses. One lane a MARBLE
  (5 a page, smoother frames) would add 8 lanes to the pathway, already the
  course with the most (24 against PLAYGROUND's 14), so every course would
  carry the larger lane tables.
- Each marble's shatter frames sit at a different pixel phase, so they share
  few blocks: very roughly 1 - 2KB of the pathway part's RAM over both pages
  (it is loaded only on the map), about half that packed.
- **The guest**: on entering the pathway after `BZ_PE_LIFE`, pose the old
  count, then step the breaking marble's frames on a small timer (~0.5 s),
  with the glass shatter's sound or the LIFE motif: perhaps 40 - 70 resident
  bytes and 2 of bss.
- **A row**: the frames in order and the count they settle on.

The 3 + 2 pile in the mock-up is a layout for the counts; a breaking marble
in it needs its frames drawn over whatever it overlaps, which a row of five
would avoid.
