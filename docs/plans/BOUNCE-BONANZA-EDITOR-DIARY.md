# How It Was Built: the Bounce Bonanza course builder

*The plan is [BOUNCE-BONANZA-EDITOR.md](BOUNCE-BONANZA-EDITOR.md); the
contract SPEC.md 130.55. Entries are dated, newest last. Each separates what
was OBSERVED from what was INTENDED, and names what was actually tested.*

## 2026-11-21 - mockups, three rounds, and the contract

**The ask.** A visual course builder for every tile and prop the format has,
easy to use, with a separate shape editor tab.

**Round 1: an os8088 package.** The first mockups were a COURSE package on
the VGA desktop, drawn in the System 1 style at 2x. The owner's reply: an
in-OS builder "would be very cool, but likely not viable", because the
course compiler agents run takes minutes on modern machines. The owner suggested a
Python window like the Video Battle builder.

**What looking further found (observed).** The compiler's cost is not
parsing: parse, tiles and cells take milliseconds. It is the checks:
occluders, the reach, NO TRAP's physics runs, the visibility audit. Under
cProfile the Playground's compile spent 41 s of 92 in the trap check, about
1.08 million `Physics.step` calls. Without the profiler, at the tree of the
day, MILL's full compile took 3.5 s and PLAY's 181 s. The XT estimate (tens
of minutes to hours an edit) is a prediction from those numbers, not a
measurement.

**Round 2: a Tk window.** The window copies the battle builder's layers.
The isometric view is the compiler's own `render()`, and two facts in the
compiler made the owner's "this obstructs that" concrete:
- `owners_canvas` records which course cell drew every pixel;
- the visibility audit already names what covers a mark. For MILL it reports
  the tube mouth at (17, 20) as 50% seen, against a 50% limit, the rest
  under cells (18, 20) and (18, 21), the bounce wall in front.

The X-ray mockup recolours the real MILL picture from those two facts.

**Round 3: host play.** The model has everything a game needs except the
drawing of a frame:
- `Physics.step` on keys;
- the families' `pose()`;
- `sprite()` and `shadow()`;
- `Glide`.

100 s of play stepped in 0.03 s for MILL. A mockup frame was made by poking
the rubber ball onto MILL's ramp, stepping it, and drawing
`bonanza_assets.material_frame` onto the rendered picture.

**A trap found while measuring (observed).** `Physics` reads the compiled
part, and compiling without occluders is not always valid: PLAY's makes
1,123 blocks, over the 1,024 a map word indexes. So "compile fast and play"
is not free. It is wave 0's question.

**The owner's decisions** are listed in the plan. Two shaped the contract
most:
- only unplayable problems stop a build, and every visual check warns;
- a hidden checkpoint is a legitimate design (secret routes), so the format
  gains a `hidden` word that agents' `--strict` runs honour.

**Tested today:** the timings above, the renders and the audit on MILL, and
`tools/checkdocs.py` on the new SPEC section. No builder code exists.

## 2026-11-21 - strict is opt-in, course by course

**Decided.** The owner expects to ship courses that do not pass `--strict`.
The shipped build therefore never runs it. Agents' course runs do. A course
records its own exceptions:
- `hidden` on an element;
- `accept <warning>` for a warning it keeps, with the reason in the comment
  above;
- `strict`, once the course is finished, so it is held to `--strict` even in
  the plain build.

The goal, in the owner's words, is good courses in the end, not a gate today.

**Process.** This fork makes no pull requests; the plan carries what a PR body
would have (fork rule 11, added to CLAUDE.md and AGENTS.md).
