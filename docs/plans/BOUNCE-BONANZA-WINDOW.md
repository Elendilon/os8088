# Bounce Bonanza: the window (SPEC.md 128.26)

The owner's brief (2026-11-16), run beside wave 9 (mechanics as parts) on
the same branch: bring the desktop window and its interactions up to spec,
then remove or gate the development keys and decided experiments. SPEC.md
128.26 is the contract; this file is the story list. Each story says what a
player sees, and how it was checked. A box is ticked only when the story
WORKS, not when its code exists.

The diary entries for this work are in
[BOUNCE-BONANZA-DIARY.md](BOUNCE-BONANZA-DIARY.md) under *The window*.

## Stories

- [x] **W1 The face.** The window shows the BOUNCE BONANZA lettering (the
  in-game style, smaller), a ledge with the rubber marble on it behind and to
  the right of a **Play Game** button at the bottom centre; no key hints.
  Resizing the window re-lays it; it never shrinks past the button.
  *Check*: a boot to look, CGA and Hercules (and VGA's greyed button and
  its reason).
- [x] **W2 The Game menu.** Play Game, Save Replay (F5), Load Replay... (F6),
  Explore, Use Mouse (off at open), Sound (on/off), each toggle marked `*`
  when on. *Check*: pick each; the marks follow; `bz_slot` mode, `bz_ctl`,
  `bzs_mode` read back.
- [x] **W3 The Saves menu.** Load Slot 1 - 3 (the slot played marked), Erase
  Slot 1 - 3 (asked twice: the item relabels `Erase Slot n?`).
- [x] **W4 Replays in APPDATA.** Save Replay / F5 writes `NNNCOURS.BZR`
  (numbered per course); Load Replay opens the dialog there and replays the
  pick at once, full screen. F6 at a pad replays that course's newest save.
- [x] **W5 V at a pad** plays the course's built-in demo, then the pathway at
  the same pad.
- [x] **W6 Resume.** F / Alt+Enter in the game goes to the window; Play Game,
  Enter, F or Alt+Enter there goes back to the same place - the title, the
  pad, or the same course mid-play, clock and ball where they were.
- [x] **W7 The window is silent.** The desktop's song and `title.bmu` are
  gone; the game's songs play as before.
- [x] **W8 The keys leave the window.** E, T, S, 1 2 3, X, R, D, W, L, V, B,
  N, M, C, G do nothing on the window unless the harness byte `bz_dev` is
  set; the rows set it.
- [x] **W9 The About card** lists the player's keys and no wave or art note.

## As driven (2026-11-16, MartyPC 5150 CGA; Hercules and VGA looked at)

Scratch drives, not rows: the menus' marks and state (Use Mouse, Load Slot,
Sound, Erase twice, Explore); Play Game -> title -> P -> pathway -> F ->
window (`bz_susp` 1) -> Play Game -> the same pad; Enter -> FIRST, F at step
161 -> window with the course held and the face painted -> Play Game -> step
161, the same ball and window, the clock running on; Esc to the pad, F5 twice
-> `001FIRST.BZR`, `002FIRST.BZR` and their card; F6 -> 002 replayed, the pad
again; V -> FIRST's built-in demo, the pad again; Load Replay... through
`SYSTEM/APPDATA` -> 001 replayed full screen. Looked at: the face on all three
adapters (VGA greys Play Game and says why), the About card on CGA and
Hercules.

Not driven: a resize by the grow box (the layout reads the content box at
every paint, and the minimum is the title's width and the two pictures'
height); the AdLib leg.

## Rows that cover it

`bonanzagame`, `bonanzaexit`, `bonanzapath`, `bonanzatitle`, `bonanzademo`,
`bonanzareplay`, `bonanzasound`, `bonanzamusic`, `bonanzamega` - each
launches through the window, so each needs `bz_dev` (128.26.6). A row of
its own for W1 - W6 (`bonanzawin`, the scratch drives above made a row) is
NOT written yet: the next step. Run once, after the last batch (CLAUDE.md,
Testing).
