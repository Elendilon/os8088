# MILL's see-saw "not see-sawing" in the game - handoff (2026-11-23)

The owner: *"Got it ingame, and the seesaw is not see-sawing."* MILL's plate is
`seesaw 22 17 24 21 along y pivot 17` (SPEC.md 130.42, F's teeter). Tree
measured: `efce8ee2f` (bb-editor = bounce-bonanza), the normal `make
bonanzadisk` build. SPEC.md 130.42.14 is the record; this is the working note.

## Status

**No guest or tool defect found. Nothing that changes behaviour is committed.**
Committed: the regression scenes (`tests/bonanza_phys.py`, `tilt_host`), SPEC.md
130.42.14, and this note with the scripts used.

## Evidence

1. **Physics, unicorn (guest vs model, every step).** `urun` on MILL's own part:
   - each ball poked at rest on F (22, 15), Down+Left (`K_D|K_L` = 9) held 150
     steps: rubber tips 0 -> 1 at step 87, -> 2 at 91; steel 118/122; glass
     101/105. Equal at every step (ball, slot, `bz_fst`, `bz_fref`, window,
     lane poses AND marks).
   - MILL's autopilot route (3,018 steps): equal; it never tips the plate.
   - route to step 600 (ball resting on F) then 9 held: tips at 682/686, equal.
2. **Picture, MartyPC.** `seesaw_look.py.txt` (BZDEV build, `F` free play of
   MILL via `bz_crsel`) and `seesaw_look_ship.py.txt` (SHIPPED BONANZA.O88:
   pathway, breakpoint at `bz_gcrs`, `bz_crs` := MILL). Ball parked on F,
   camera settled, then poked onto the plate (22, 18) with gvy 180: `bz_fst`
   0 -> 1 -> 2, all nine plate lanes (records 6, 8, 9, 11, 13-17) marked on
   the tipping step, committed one a frame, `bz_ldrw` = 2 for all ~10 frames
   later. Seen on CGA, Hercules (the owner's pc5150 card) and VGA (BZDEV) and
   Hercules (shipped). Screenshots show the three poses.
3. **Data.** Lane records are the first 40 records, sorted by row; the nine
   see-saw lanes' pose maps (picture part `L`) each differ between poses.
4. **Why play may not tip it** (`seesaw_route.py.txt`): the weight counts
   GROUNDED steps on one half (rubber 8, D3/D6). The autopilot rolls up the
   minus half (already down, nothing counted), HOPS before the pivot, lands on
   the plus half at (23, 20) and is grounded there 7 steps before rolling off
   onto the ramp - one short. Plain Down from F runs along x 24 and misses the
   plate; plain Left climbs the minus half and falls off its side short of the
   pivot. Test Roll runs the same `bbcourse.Physics`, so the same input gives
   the same result there. Also: once tipped (pose 2) the plate's far end is at
   16 units against the ramp's 18 - a 2-unit wall, so a tipped plate blocks
   the way to the plaza.

## Candidates ruled out

130.42.13 (`tilt_base_ops` for every plate: picture only, poses still differ),
130.42.12, 130.58.48 (builder only; guest lanes correctly ordered), camera
stops/span 130.45.5/6 (efce8ee2f is behaviour-identical to edeabad05 per its
own proof, and the lanes draw on MartyPC at efce8ee2f), tighter reach, form 9,
two-part MILL, bbgame (owner says the game was a normal build).

## What to try next

- Ask the owner exactly how the ball reached the plate in the game vs the Test
  Roll (rolled or hopped, from the drop tube or from rest on F, which keys).
- If the owner wants the plate to tip on a hop-over or a fast pass, that is a
  design change to the weights (130.42.10 item 1) or the course (`rest +`,
  a different `pivot` so the tipped end meets the ramp).
- `t_bbgame` was started (after `make bbgamebin`) but not seen to finish.

## Checks run

- `tilt_host` (unicorn): every TILT scene and red arm, plus the new
  `mill-rubber`, `mill-steel`, `mill-glass` green and red arms `tlmillmark`
  (red at step 87, never drawn) and `tlmillcarry` (red at step 122, the ball).
- `bbcourse.py --selfcheck --only tilt,tiltbase`: ok.
- `t_bbedit`: ok. `checkdocs.py`: 0 problems. `make bonanzadisk`: ok.
- No guest or tool change, so `bbcourse.py -o` output is unchanged by
  construction.

Soak rows for the lead: `bonanzaphys` (its `--check` runs `tilt_host`).
