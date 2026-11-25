# KITE HILL: signs and decals (2026-11-25, in the course; the owner may strike any piece)

*What [KITE.md](../KITE.md) section 9 asked the art step for, as built. Everything here is IN
`apps/bonanza/courses/kite.bbc` (`kite/sketch.py` writes it). The clocks are [CLOCKS.md](CLOCKS.md).
[art.py](art.py) is the artwork's SOURCE, with [../artkit.py](../artkit.py) the kit courses 5 - 7 share; the
`.bba` files it writes are committed, and `sketch.py` imports its `lines()`, so a re-emitted course keeps its
art. KITE is `palette 0`: ink 1 GREEN, ink 2 RED, ink 3 YELLOW; on the Hercules green and red are one grey
checker and yellow is white. Looked at in the tool's own picture on both cards, never on an emulator. (The
tool's `--png` draws every course in palette 1; `art.py --png` writes `picture-cga.png` in the course's own.)*

    python3 docs/plans/bonanza-courses/kite/art.py              # write the .bba files, print the `art` lines
    python3 docs/plans/bonanza-courses/kite/art.py --png DIR    # ...compile, and write DIR/art-*.png and picture-*.png

![the course, the tool's own picture in palette 0](picture-cga.png)

## The signs

![the great kite over the summit; the gust bridge's sign](art-signs.png)

| piece | file | where | what |
|---|---|---|---|
| the GREAT KITE | `kite_great.bba` | in the sky up-left of the summit (the picture's own void: no room was added and `origin` did not move); its string runs down to a peg in the crown's middle | a harlequin kite 45 x 63 px, yellow and red panels on black spars, a four-bow tail. It is the picture the player climbs toward. The string crosses the summit's rail and floor as paint: the ball rolls over it |
| FLYING: WAIT, LIMP: GO | `kite_calm.bba` | a signboard on the breezeway's last tile (39, 45), beside the gust bridge's mouth; only the void is behind it | two lines, each a pennant and a word: a pennant flying beside WAIT, a pennant hanging beside GO. The fan's own pennant is the one the player watches; the sign says what it means, before the first thing on the course that kills |

## The decals

![the fan plaza's arrows; the shelters; the launch plaza; two of the small kites](art-decals.png)

| piece | file | where | what |
|---|---|---|---|
| into the THERMAL | `kite_lift.bba` | the fan plaza's floor at (39, 36) and (39, 38) | two black arrows (a yellow line round each) pointing west into the strip of rising air at the cliff's foot. The sheet asked for an arrow up the cliff's FACE; the face is where the thermal's own squiggles are drawn, so the arrows are on the floor in front of it |
| the SHELTERS | `kite_shelter.bba` | the windbreaks' four sheltered tiles, (24 - 25, 38) and (28 - 29, 38) | each tile framed in red, and a small yellow and red banner hung from its rail's foot, over the bridge's face and the void. The shelters were the hardest thing on the course to see (a guard rail is thin lines) and are its designed answer |
| ROLL OFF HERE | `kite_launch.bba` | the launch plaza: (17, 35), between the flag and the open corner, and the corner tile (16, 34) itself | an arrow pointing straight up the screen, and a kite painted on the corner tile. From the flag the line is: arrow, kite, the great kite above |
| three small kites | `kite_small0.bba` - `kite_small2.bba` | in the void right of the plaza, right of terrace 3 and left of the launch plaza | scenery, a 17 x 24 px sail each with a two-bow tail: a backdrop, the ball is always drawn over them |

## What it costs (MEASURED: compiles of the course in this step, with its song)

| | part in RAM | blocks | masks (of 256) | LZ4 (1.5x line 18,825) |
|---|---|---|---|---|
| before the art step | 54,030 | 634 | 178 | 13,624 |
| + the kite clocks | about 54,590 | 666 | 180 | about 14,480 |
| + the signs and decals | **56,670** | **796** | **180** | **16,067** |

The signs and decals are 130 blocks (2,080 bytes of RAM, about 1,590 of LZ4) and no mask. The course is 8,354
bytes under one part and 2,758 LZ4 bytes under its budget's 1.5x line; it was 1,074 over its 60 s class before
and is 3,517 over it now (reported, never refused: every shipped course is over its class).

## Not done, and why

- **A windsock or bent grass at the breezeway**: the lesson's fan already flies a pennant while it blows
  (`flag`), and the windsock is the clocks' alternative ([CLOCKS.md](CLOCKS.md), B).
- **A footpath sign at the rope walk's foot**: the rope walk is the plain way and reads as one.
- **An arrow on the cliff's face**: see `kite_lift`.
