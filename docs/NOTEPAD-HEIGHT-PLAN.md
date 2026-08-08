# Note Pad's lazy height count — handover

**Status: designed, attempted, REVERTED. Nothing is on the branch.** The
problem is diagnosed with numbers, the design is settled and the one piece of
new plumbing is identified. The attempt failed for a reason that is narrowed
to about three candidate lines. Read this before starting, and especially
read "How the attempt failed", because the failure mode passes a casual look.

## The problem, measured

Opening `README.TXT` (15,889 bytes) on the 5150: a quick file load, a
reasonably quick first screenful, then **a long freeze with nothing on the
disk and nothing on the glass**.

It is not I/O. `make DISKCNT=1` counters are flat across the freeze. It is
not the drawing either: counted at `font_char`/`gfx_fill`, the paint is 549
glyphs and 115 fills, which at PERFORMANCE.md's ~1 ms a cell and ~756 us a
call is about **0.65 s** — real, but not the freeze.

It is `np_height`. `np_paint`'s walk already stops at the bottom of the view
(SPEC.md 27.7.1), so the first screenful is cheap; `np_height` is the one
walk with no bound. It is seeded at index 0, run to the last character, and
called from the worker **inside one gfx-lock hold**. A load raises
`[np_hdirty]` (`notepad.asm`, "a whole new note is a whole new height"), so
the worker's next pass walks the whole note with the machine frozen behind
it.

## What has already shipped (do not redo)

A separate bug in the same area is FIXED and merged: `np_bounds` compared the
content box's **absolute** `np_tx`/`np_ty` against their shadows, so simply
DRAGGING the window set `[np_gchg]` and made `np_paint` pay `np_measure` — a
second unbounded walk. It compares the wrap WIDTH (`np_rgt - np_tx`) and the
view HEIGHT now. That is a different stall from this one; both were real.

## The design

Chunk the count. `NP_HCHUNK` rows per worker pass, resuming where the last
one stopped. The walk's two exits already do the bookkeeping:

- `.done` (natural end) clears `[np_hdirty]` and sets an exact `[np_drows]`
- `.stop` (bounded) leaves `[np_hdirty]` raised and raises `[np_drows]` as a
  monotone lower bound

So "am I finished" is `[np_hdirty]` and needs no new flag.

### Why the gfx lock does not prevent this

`np_height` runs with `np_draw` and `np_sigup` clear and writes no
framebuffer. **The lock is a mutex over the walk's scratch**, not a drawing
lock: `np_row`, `np_curx`, `np_i`, `np_rows` and the rest are module globals,
and nine of `np_walk`'s ten call sites are UI callbacks, which hold the lock
already (SPEC.md 49's rule).

The consequence is the whole design: the hold is needed for a CHUNK and never
for the COUNT. Take the lock, walk `NP_HCHUNK` rows, release, sleep. A UI
action behind it waits a bounded number of rows instead of a whole note, and
"give up its time if the CPU is busy" falls out of the release — the worker
never has to ask whether anyone else wants to run.

### Why the resume pair survives an interleaved UI walk

`(row, index-that-row-starts-at)` is safe across a lock release because
**wrapping is deterministic**: row *R* begins at index *I* whoever computed
it. An intervening `W_PAINT` scribbles over the walk's in-flight scratch and
cannot touch those two words. Only the note CHANGING invalidates them, and
that already raises `[np_hdirty]`, which means start over.

### The one piece of new plumbing

`.stop` must publish the index it stopped at, because **`np_seedrow` cannot
reconstruct it**: `np_rows` is `NP_MAXROWS` long and `NP_MAXROWS` is **60,
one slot per VISIBLE row**. It describes the view; it can never name row 300
of a 500-row note. `np_seedrow` refuses any row `>= [np_rowsn]` for exactly
that reason.

At `.stop` the pair is `[np_row] + [np_top]` (absolute row) and `[np_i]`.
`[np_i]` IS live — `inc word [np_i]` is in the loop body — that was checked.

### Readers need no new rule

`[np_drows]` is a monotone lower bound while the count is unfinished
(SPEC.md 27.7: "never lowered ... one blank row at the end rather than a
caret nobody can see"). A half-counted note gives a thumb slightly too small
and a scroll range slightly too generous, never a caret that cannot be
reached. Nothing has to block and nothing has to test whether the count "got
there yet".

## How the attempt failed — READ THIS

The implementation assembled, booted, and loaded and rendered README
correctly. It was reverted because **the count did not progress**.

The tell is the scroll thumb. For a 15,889-byte note in a ~20-row window the
true height is ~400+ rows, so the thumb should be about 5% of the track. It
stayed at roughly **75%**, which means `[np_drows]` was stuck near
`[np_vrows]` — each pass re-walked the same rows, the no-forward-progress
guard fired, and the count was abandoned.

**That is worse than the freeze it removes**: the pause goes away and the
height stays permanently short, so a long document cannot be scrolled to the
end. Do not ship a version that has not been checked against the thumb.

The resume is not taking effect. Ruled out already: `[np_i]` is maintained,
and the seed fields (`np_resume`, `np_sdi`, `np_sdr`) are the ones
`np_walk`'s resume branch reads. The prime remaining suspect is
**`[np_lastrow]` being clobbered between the set and the walk** — the worker
calls `np_bounds` immediately before `np_height`, and there is a
`mov [np_lastrow], ax` at about `notepad.asm:1050` that was never attributed
to a routine. If `np_lastrow` is reset to `[np_vrows]`, every chunk stops at
the bottom of the VIEW regardless of the seed, which produces exactly the
observed symptom.

Second suspect, cheaper to check: whether anything between `np_height`'s
stores and `call np_walk` clears `[np_resume]`.

## The scrollbar refinement (asked for, not implemented)

A bar click should only force the count to finish when it scrolls somewhere
the count has not reached. `np_onclick` currently calls `np_height`
synchronously before any bar click — "the one place the height must be exact
rather than generous".

The wrinkle: the click-to-row mapping *itself* uses `[np_drows]`, so with a
lower bound the thumb and the mapping stay consistent with each other —
clicking halfway takes you to half of what is COUNTED, which is not wrong,
merely relative to a document that looks shorter than it is. So "has the walk
reached there" is not a simple boundary test. The honest rule is closer to
*if the click targets the last screenful of the counted extent, finish the
count first*. Cheap to add once chunking works.

## How to verify

1. `make` then `make test`, open Drive A, double-click `README.TXT`.
2. Let the worker run ~10 s, then zoom the Note Pad scroll bar:
   `python3 tools/shot.py build/qmp.sock out.png --crop 300,70,30,175 --zoom 4`
   **A large thumb means the count is stuck.** This is the check the failed
   attempt was caught by, and it is the one that matters.
3. Scroll to the end and confirm the last line is reachable.
4. Resize the window (grow box) and confirm the text re-wraps — the count and
   the re-wrap share `[np_hdirty]`.

**MartyPC is built in this container** (`make marty`, `tools/martypc/`) and is
the right instrument for the before/after, because it is a cycle-accurate
4.77 MHz 8088 and QEMU cannot show this stall at all — under QEMU the whole
freeze is microseconds. docs/MARTYPC-DEBUG.md is the recipe.

## Files

- `apps/notepad/notepad.asm` — `np_height`, `np_walk`'s `.stop`, the worker's
  `.go` block, and the `NPVAR` bss block at the foot of the file (use `NPVAR`
  for new state; the hand-computed `equ os88_image_end + N` block above it is
  legacy and must not be extended)
- SPEC.md 27.7 / 27.7.1 — the bounded walk and `[np_drows]`'s lower-bound rule
- SPEC.md 27.4 / 27.5 — the seed machinery this reuses
- SPEC.md 49 — the shared-scratch rule that explains the lock
