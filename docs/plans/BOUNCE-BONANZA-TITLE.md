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

- [ ] **T5.1** `bonanzatitle` (new), the selfcheck controls, the music row's
      length check.
- [ ] **T5.2** The final pass: the deduplicated BONANZA rows once.
