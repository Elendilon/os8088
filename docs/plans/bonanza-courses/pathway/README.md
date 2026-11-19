# Bounce Bonanza: the pathway, initial-look options

*Options for the owner, 2026-11-19: "Lets work on the pathway, before the
next course. Here is my original concept. We don't have to be quite this
dense, but I would like a few options. 1-2 are the tutorials and then 3 is
'Downhill Decision', which is the first course with two exits into a split
pathway." Nothing here ships. The shipped prototype is still
`apps/bonanza/courses/path.bbc` (SPEC.md 130.22), and it is unchanged.*

## How the sketch was read

- Numbered shapes are courses and the ovals beside them are each course's
  title and artwork. The red circle by 1 is where the marble starts: pad 0
  and a new game.
- **1 -> 2 -> 3 along the bottom** on a broad road. 3 sits at the right.
- **3 is the split.** Its two exits open two routes:
  - one climbs the right-hand side, past 4 to 5;
  - one runs up-left into the middle, past 6 to 7, then on to 8 at the far
    left.
- The routes that run off the sketch's top edge are read as "the map goes
  on". No sheet adds pads for them.
- **The graph the sheets use**:
  - ROLL 1 -> HOP 2 -> TRIAL 3.
  - TRIAL's exit 0 -> MILL 4 -> PEAK 5.
  - TRIAL's exit 1 -> MOON 6 -> PLAY 7 -> FIRST 8.
  - 5 and 8 are the two ends.
- **Every course but TRIAL has one exit**, so a split can only happen at 3.
  TRIAL is the stand-in for Downhill Decision because it is the only
  course with two exits.

**Stand-ins**:

- Courses 4 - 8 are the old test courses.
- Course 3 is TRIAL with the title "Downhill Decision".
- Course 8 is FIRST titled "Bounce Trial", because FIRST and ROLL are both
  "First Roll" today.
- The icons are placeholders:
  - `tools/bbicons.py`'s drawings, redrawn at each size (the shapes are
    scaled, not the pixels);
  - two new ones in `gen.py`: a frog for Little Hop, whose clocks are
    frogs, and a signpost on a slope for Downhill Decision.

## The options

| | A - Faithful | B - Roomy | C - Causeway |
|---|---|---|---|
| the idea | the sketch's arrangement, as dense as the rules allow | fewer pads a screen, today's sizes | a different route style: no crystal, the routes stand on walls and ramp |
| pages | 2 | 4 (page 3 left for what follows 8) | 3 |
| routes | crystal, floating (today's look) | crystal, floating | the floor's own look (`rail normal`), not floating, ramps up 5 units |
| the split at 3 | in from below; Up to 4; a long up-left diagonal to 6 | a T: Left to 6, Right to 4, two columns | in from below; Up to 4; Left then a steep ramp to 6 |
| titles | 5 x 7 small caps | today's 8 x 8 | 5 x 7 small caps |
| icons | 32 x 24 (2/3 of today's) | 48 x 32, Downhill Decision 64 x 40 | 32 x 24 and 40 x 28 |
| part, RAM | 22,710 | 35,012 | 31,188 |
| part, LZB | 6,570 | 8,314 | 8,715 |

Today's BZROLL=1 map, the baseline, is 21,788 RAM and 6,470 LZB. It has 6
pads on 2 pages, with 48 x 32 icons and 8 x 8 titles. All figures are the
tool's own (`path_costs`, `packed_len`), MEASURED on 2026-11-19.

### The title face, priced

The same layout was built with each face, at one commit:

| | 8 x 8 | 5 x 7 | 5 x 7 costs |
|---|---|---|---|
| A | 22,070 / 6,308 LZB, 236 picture blocks | 22,710 / 6,570, 274 | +640 RAM, +262 LZB |
| B | 35,012 / 8,314, 311 | 35,748 / 8,616, 357 | +736, +302 |
| C | 30,420 / 8,417, 349 | 31,188 / 8,715, 395 | +768, +298 |

**A smaller face costs bytes rather than saving them.** An 8 x 8 letter is
exactly one picture block, and the pool shares identical blocks: every "E"
on the map that lands on a block boundary is one block. A 6-pixel pitch puts
nearly every letter across two blocks, and each such pair is unique. What
the 5 x 7 face buys is width: DOWNHILL DECISION is 102 px rather than 136,
so titles fit between two route columns. A and C would not fit without it.

## What shaped every option (the tool's rules, met)

- **The key map decides the junction (130.22.4.5).** A three-way pad needs
  a STRAIGHT direction among its routes. Three diagonal routes always leave
  some arrow claimed by two of them, and the tool refuses that. At 3 the
  shapes that work are:
  - in from below, with Up and an up-left diagonal (A, C);
  - in from below, with Left and Right (B's T);
  - in from the left, with Up and an up-right diagonal.
- **A straight route is a FAT band**, three cells wide (64 px across a
  vertical climb). A diagonal is one cell. Titles therefore have to fit
  between bands, and that is the main pressure on density.
- **A pad's cell is at least 24 lines inside its page** (130.22.2), and
  **every page has a LIVES counter**. A layout cannot crowd the page edges.
- **Every non-secret route has a gate**, and the gate needs room on the
  route clear of the pads' lanes. A 1-2-cell route between two pads is
  refused, which is why the sketch's 4-5 pair cannot sit as close as drawn.
- **Titles are centred over their icon**, 10 lines above it. With a long
  title the icon is placed by where its TITLE fits, not where the icon
  would look best (`gen.py` nudges each one).

## Guest changes

**None, for any option.** Titles and the static parts of icons are picture
pixels. An icon of any size is cut into lanes the guest already plays. The
5 x 7 face is a tool-side swap (`gen.py` replaces `bbcourse.text_pixels` for
the sheet). Taking it into the build means a face argument on
`text_pixels` in `tools/bbcourse.py` and its 5 x 7 glyphs in the tool,
which is also a tool-side change. The LIVES label stays in the 8 x 8 face
in every option.

Bigger parts do cost the guest RAM. A held pathway (130.22.1, "memory") is
B's 35 KB or C's 31 KB rather than today's 22 KB, and `BZ_PATH_CLAIM`
grows with it, which decides on more machines whether the pathway is
dropped before a course. Every option is well inside the 65,024-byte part
limit.

## Files

- `gen.py`: the options (`OPTIONS`: pads, routes, icon sizes and sides,
  lives, face, material), the icon redraws and the sheets. It writes:
  - `optA.bbc`, `optB.bbc` and `optC.bbc`, generated. Each compiles with
    `tools/bbcourse.py`'s own checks and its `path_proofs` against the
    BZROLL=1 course list. Each also compiles in the plain 8 x 8 face,
    unpatched.
  - `icons/*.bba`, generated.
  - the sheets.
- Run it with:

  ```
  python3 docs/plans/bonanza-courses/pathway/gen.py --out DIR
  ```

  It writes `opt<X>-sheet.png` (every page, CGA palette 1 and the
  Hercules, the windows marked, pads tagged 1 - 8), `overview.png` and
  `titles.png` (both faces, both cards). The default DIR is
  `build/bonanza-pathway/`.
- The first run compiles the BZROLL=1 courses, which takes about 3 minutes.
  What the pathway reads of them is remembered in
  `build/bonanza-pathway/courses.json`.
