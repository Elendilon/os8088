# BOUNCE BONANZA — the title screen (plan and stories)

The contract is SPEC.md 128.23; this file is the work list and what has
actually been checked. The game's own plan is
[BOUNCE-BONANZA-PLAN.md](BOUNCE-BONANZA-PLAN.md), the running diary
[BOUNCE-BONANZA-DIARY.md](BOUNCE-BONANZA-DIARY.md) (its entries from
2026-11-16 on carry this work too).

## The brief (the owner, 2026-11-16)

> Another session is working on the pathway rework, currently. This session
> will work on Bounce Bonanza's title screen. The title screen will be a
> "course", but not played by the player - one of a handful of builtin demos
> will randomly play. User input will take them into the game - P to play, S
> (or 1/2/3) to change save slot.
>
> The screen will never scroll - it will be fixed in place, so we may need a
> new camera type for that.
>
> The title will just be artwork baked in, the same as the key hints, with an
> item handling the 1/2/3 draw change.
>
> My mspaint is very rough - I did not always get perspective right. There
> are currently four features - a tunnel connecting the bottom brown to the
> upper brown, a windmill connected behind the vertical pillar, and two
> springs. You can recommend other objects, or different objects, or we may
> refine once we have more than the handful in the game that we do today.
>
> A ramp leads from the upper platform on the right, to the lower right
> platform. You can roll behind it.
>
> Once a title demo ends, a demo from a random level is loaded and played.
> Any key exits this demo and goes back to the title screen. The title screen
> needs a catchy music that ends at the same time as the demos, which are
> ~15s and all the same length.

The four demos, as the owner wrote them:

1. **Rubber.** After ~1 s of nothing, a rubber ball drops from offscreen onto
   the centre of the upper right platform, and then bounces to a stop. It
   then rolls over and down the ramp, ending slightly offscreen to the
   front. It rolls back onscreen, pauses shortly, then rolls onto the spring
   and bounces back up to the upper right platform (springs may need a
   custom bounce power for this). Once it is back on top, it rolls right
   offscreen and the demo ends.
2. **Steel.** A steel ball falls from above in the left-centre of the
   screen, landing on the lower left platform. It is stunned. After a moment
   it rolls over to the spring and tries to get across, but falls in the gap
   and dies. It respawns on the lower centre platform, and instead rolls
   over to the lower tube entry. It comes out on top. It rolls down the
   ramp, turning to go offscreen at the bottom and the demo ends.
3. **Glass.** A glass ball rolls onto the lower left platform. It briefly
   pauses, then rolls forward. It goes over the edge. At speed, it rolls to
   the lower brown tube, and emerges on top. It rolls to the edge of the
   ramp, and then stops. It goes to the centre of the upper platform and
   does a circle - after gaining some speed it gets too close to the front
   edge, falls off, shatters and the demo ends.
4. **Rubber at speed.** A rubber ball already travelling at a speed bounces
   onto the lower left upper platform. It bounces forward, and boost
   bounces. It lands on the spring, and carries successfully over to the
   lower right bottom platform. It carries across, behind the ramp, and
   rolls offscreen. After a moment (and a sound effect? hidden tube
   offscreen?) it emerges on the upper right platform. It rolls across the
   upper right platform, enters the windmill, and then boost bounces over
   the lower tube entry. As it falls offscreen the demo ends.

The sketch is [bounce-bonanza/title-sketch.png](bounce-bonanza/title-sketch.png).

## What the tree already had (read before designing, 2026-11-16)

- **The boxes are clipped to the window** (SPEC.md 128.4, `bz_addbox`), so a
  ball outside a fixed window is simply not drawn: the fixed camera needs no
  clip of its own, only a window that does not follow the ball.
- **Every course picture is at least 512 px wide** (`width 64|128`), so a
  fixed camera has to be pinned on the guest; the 192 px the CGA cannot see
  (152 on the Hercules) is where the balls roll off and the hidden tube
  lives.
- **A demo is inputs only**, from the course's `start`: a title demo needs a
  start state (a drop from above, a ball already moving) and a respawn cell.
- **A spring's power is per spring already** (`spring wx wy gvz`, 256 - 768).
- **A clock lane always carries the crystal ball**: the slot digit needs a
  bare-glyph lane kind (`label`).
- **Songs always loop**, step-locked to the physics in a replay: a one-shot
  is a last order row of silence with `loop` pointing at it.
- **S is the SOUND key on the desktop face**; inside the bracket it is free,
  so the title's S is the slot's.
- **The course identity is over the whole picture**: every pixel of art
  moves it, so the title demos carry no identity in their source; the build
  writes it.

## The stories

Each wave is a commit (or a few) on `bounce-bonanza` and a bonanza disk set.
A box is ticked only for what was built AND checked as its line says.

### Wave T0: the contract

- [x] **T0.1** SPEC.md 128.23 written: the decisions, the statements, the
      demos' format, the loop, the layout, the rows. *Host: `checkdocs`.*
- [x] **T0.2** This plan, the sketch kept as source, the diary's entry.

### Wave T1: the tool - a title course on the host

- [x] **T1.1** `title`, `view SX SY`: the picture grown round both windows
      and the drop margin; the four window values and the flag in the grid
      header. *Host: `--selfcheck` controls (a view off the picture, an odd
      SX refused); the window drawn on the preview.* *Built; the window LOOKED
      AT on host previews of both cards and on MartyPC's CGA (R0 64, c0 51
      held for a whole demo). The selfcheck controls are T5.1's.*
- [x] **T1.2** `art FILE X Y` and the `.bba` pixmap; refused off the
      picture. *Host: a control; the preview.* *Built; a placeholder box
      LOOKED AT on the host and the guest. The control is T5.1's.*
- [x] **T1.3** `label N COL ROW glyphs "..." [ink C]`: one block, the desktop
      font's glyphs, a `PK_CLOCK` of ndig 0 with no OBS cell. *Host: the
      lane's poses equal the font; no cell of the grid OBS for it.* *Built;
      LOOKED AT on MartyPC's CGA: `SLOT 1`, then `SLOT 3` after the 3 key
      (the walk's clock skip had to be told, `bz_tlabel`). The host checks are
      T5.1's.*
- [x] **T1.4** The title art: the lettering and the key hints, generated
      once by a committed script into `title.bba`. *Looked at: the preview
      PNG, CGA and the Hercules translation.* *Built (`tools/bbtitle.py`);
      LOOKED AT on both host previews and on MartyPC's CGA. One line of
      lettering, not the sketch's two (SPEC.md 128.23.2).*
- [x] **T1.5** `title.bbc`: the layout of 128.23.5, its two tubes, the
      windmill, the two springs, the ramp, the label. *Looked at: the
      preview against the sketch; every reach inside the picture.* *Built,
      width 128 (a 64-word picture cannot hold the reach's corners and the
      off-glass margins); LOOKED AT on both cards' previews and the CGA
      guest. PROVISIONAL, the owner's to refine.*

### Wave T2: the guest - the fixed camera and the title loop

- [x] **T2.1** The title course as `BZ_CRS_TITLE`, its row last; the per-course
      tables' entries.
- [x] **T2.2** The FIXED camera from the header (`bz_camera`'s first frame and
      `.modes`). *Looked at on both cards: the window still while the ball
      moves; the ball leaving the glass and coming back.* *CGA LOOKED AT on
      MartyPC (a demo's frames, the window still); the Hercules still to
      look at.*
- [ ] **T2.3** The label lane posed by `bz_nst`, marked for the walk on a
      change.
- [x] **T2.4** `bz_title`: Enter on the face opens it; the keys (P, S, 1 2 3,
      Esc); the chain to a course demo and back; the game from P and back.
      *Built (`bz_title8`, `bz_tround`). Seen on MartyPC's CGA: Enter opens
      the title, a title demo plays its 832 steps, a course demo (TRIAL)
      follows with its own camera. The keys and the game's return are
      `bonanzatitle`'s to prove (T5.1).*

### Wave T3: the demos

- [x] **T3.1** The `.bzt` format, the part `BZTDEMO.BIN`, the model's start
      state and respawn cell, the build's checks.
- [x] **T3.2** The guest's start block and `bz_rspo`.
- [x] **T3.3** The four demos, authored on the model to the brief
      (`TITLE_AUTHOR`, `bbcourse.py tauthor`). *Host: every expect met at
      every build; their frames LOOKED AT as host GIFs. The guest's replay
      against the model is `bonanzatitle`'s (T5.1). Where the course made
      the brief bend: demo 2's steel is too slow to clear LL, so it lands at
      the pit's edge stunned and rolls in; demo 4's ball rolls off the glass
      to the right into the hidden tube rather than behind the ramp.*

### Wave T4: the song

- [x] **T4.1** `attract.bmu`: one pass of `BZ_TSTEPS` sub-ticks, catchy,
      ending with the demo; PLAY's `music fairway`. *Host: the music
      selfcheck; listened to as WAV on the host (speaker and OPL2).* *Built;
      the selfcheck's length and silence check passes and goes red on a
      groove of 6 6; both WAVs rendered for the owner. NOT listened to by
      the session (it cannot): the owner's ears are the check.*

### Wave T5: the rows and the final pass

- [x] **T5.1** `bonanzatitle` (new), the selfcheck controls, the music row's
      length check. *MEASURED PASS on both cards (CGA 26.3 s); red arm `view`
      red at check 2 (the window (0, 36), not (64, 51)). The selfcheck's item
      13 and its four controls pass on the host; the music check goes red on
      a groove of 6 6. The rows the title changed: `bonanzapath` goes through
      the title (Enter, P), `bonanza_sound`'s FIRST is F, and the harness counts
      the title's two rows after the shell's (`after_shell`, `path_ident`).*
- [x] **T5.2** The final pass: the deduplicated BONANZA rows once.
      *MEASURED 2026-11-16, `os88soak.py -k 'bonanza*'` on the merged tree
      (671f5dc8, with wave 8R), 20.6 min: 10 of 15 PASS - `bonanzatitle`,
      `bonanzapath` (through the title), `bonanzagame`, `bonanzademo`,
      `bonanzaphys`, `bonanzareplay`, `bonanzaperf`, `bonanzacourse` (item 13
      in it), `bonanzamusic`, `bonanzaassets`. FAIL: `bonanzaexit` - its row
      count did not know the title's two rows (fixed here, then PASS on the
      CGA) and its in-bracket claims did not know 8R's fanfare (8R's fix,
      b2d47f35); `bonanzamega` - 8R's fanfare claim (8R's fix, 8e372c47);
      `bonanzaring`'s probe and `bonanzawheel`'s leg (6), both failing before
      this work (SPEC.md 128.19.9); `bonanzasound`'s boost and w7 legs - the
      effects 8R reworked, passed to that session. A first run of the same
      scope was void: the tree was merged under it.*

### Round 2: the owner's notes (2026-11-16)

- [x] **R2.1** The letters lower, clear of the top (`TOP` 16). *Host:
      `bbtitle.py --check`; 9 px to the nearest scene pixel.*
- [x] **R2.2** No black flash: no respawn cut on a fixed window; black
      between plays (SPEC.md 128.23.3). *MEASURED: `bonanzatitle` 4b, one
      full write in a demo with a fall, both cards.*
- [x] **R2.3** The course: the LL-LS step, LS off the glass to the left, the
      spring at LL's pit edge (128.23.2's waiver), the hidden tube's mouth on
      the south rail. *Host: the selfcheck.*
- [x] **R2.4** The four demos re-authored to the notes (128.23.5). *Host:
      every expect met; MEASURED on the guest: the demo `bonanzatitle` drew
      on each card equals the model at its end. How they READ is the
      owner's to judge.*

### Round 3: the owner's drawn changes (2026-11-16)

- [x] **R3.1** The plaque a row down and a column over (`label 0 11 9`).
      *LOOKED AT on MartyPC's CGA; `bonanzatitle` check 3 both cards.*
- [x] **R3.2** The pit cleared: LC's corner (12 - 13, 13 - 14) and the south
      rail's (12 - 13, 17) taken out. *Host: the selfcheck; looked at.*
- [x] **R3.3** The windmill's exit an arch in the pillar's +x face, out +x;
      the hidden tube's mouth at (23, 11). *Host: the selfcheck; looked at.*
- [x] **R3.4** Demo 4 on the owner's red line, a smooth windmill entry, off
      the bottom right at the end; demo 3 down the step. *Host: every expect;
      MEASURED: `bonanzatitle` replayed demo 4 on the CGA equal to the model.*

### Round 4: demo 3, the glass ball, again (the owner, 2026-11-17)

The owner kept the entry, the short pause and the ending on a shattered
ball, and dropped the rest: the steel ball's tube, the waiting on UR, the
circles and the roll off the edge that did not look like an accident.
The middle was designed with the owner: glass finds a hidden bridge steel
never saw, cannot climb the ramp, and tries the spring.

- [x] **R4.1** The pit a real gap: the strip in front of the pillar
      (12 - 13, 12) taken out. *Host: demos 1, 2 and 4 replay step for
      step identical on the model against the course before.*
- [x] **R4.2** The GLASS BRIDGE: LL's back row over the pit at LL's height,
      two `glass` tiles (128.25.8); `uses ... glass`. *Looked at: the
      course preview (the gap, the jagged-edge hint at LL).*
- [x] **R4.3** Demo 3 re-authored (`tauthor -n 3`): the bridge, a run at
      the ramp that fails, the spring tried, short of UR by its lip, the
      shatter on the spring (128.23.5). *Host: its expects (spring 1,
      shatter 1) met by the build's replay; a host preview GIF looked at.*
      Breaking ON UR was asked for and is not reachable: the launch cap
      BZ_VZMAX 768 lands glass there at 443, under its 552; the owner chose
      the lip.
- [ ] **R4.4** Looked at on the guest (MartyPC, both cards): the bridge
      revealing tile by tile, the jump and the shards; `bonanzatitle`'s
      replay equal to the model.
